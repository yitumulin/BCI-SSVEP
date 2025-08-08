import argparse, csv
import numpy as np
from collections import deque
from pylsl import StreamInlet, local_clock
try:
    # pylsl >=1.16
    from pylsl.stream import resolve_stream
except Exception:
    # pylsl <=1.14
    from pylsl import resolve_stream
from scipy.signal import butter, filtfilt, iirnotch
from sklearn.cross_decomposition import CCA

def butter_band(lo, hi, fs, order=4):
    b,a = butter(order, [lo/(fs/2), hi/(fs/2)], btype='band')
    return b,a

def narrow_band(seg, fs, f, bw=3.0, order=4):
    lo = max(1.0, f - bw/2.0)
    hi = min(fs/2.0 - 1.0, f + bw/2.0)
    b,a = butter_band(lo, hi, fs, order=order)
    return filtfilt(b,a,seg, axis=0)

def apply_filter(seg, fs, notch=50.0):
    x = seg.copy()
    if notch:
        b,a = iirnotch(w0=notch/(fs/2), Q=30)
        x = filtfilt(b,a,x, axis=0)
    x -= x.mean(axis=0, keepdims=True)
    return x

def make_ref(fs, n, freqs, harmonics=3):
    t = np.arange(n)/fs
    refs={}
    for f in freqs:
        cols=[]
        for h in range(1, harmonics+1):
            cols += [np.sin(2*np.pi*h*f*t), np.cos(2*np.pi*h*f*t)]
        refs[f] = np.stack(cols, axis=1)
    return refs

def score_one(segf, fs, f, ref, cca):
    # 谐波权重
    weights = [1.0, 0.6, 0.4]
    score = 0.0
    for h, w in zip([1,2,3], weights):
        Y = ref[:, 2*(h-1):2*h]   # 当前谐波的两列
        seg_nb = narrow_band(segf, fs, h*f, bw=3.0)
        cca.fit(seg_nb, Y)
        U, V = cca.transform(seg_nb, Y)
        r = np.corrcoef(U[:,0].ravel(), V[:,0].ravel())[0,1]
        score += w * max(0.0, float(r))
    return score

def majority_vote(hist):
    # 简单多数；平票时取最新
    if not hist: return None
    vals = list(hist)
    best = max(set(vals), key=vals.count)
    return best

def main(args):
    print("Resolving EEG stream...")
    eeg_streams = resolve_stream('type', 'EEG')
    if not eeg_streams: raise RuntimeError("No EEG stream found.")
    inlet_eeg = StreamInlet(eeg_streams[0], max_buflen=5)

    inlet_mk = None
    if not args.no_markers:
        print("Resolving Markers stream...")
        mk_streams = resolve_stream('type', 'Markers')
        inlet_mk = StreamInlet(mk_streams[0]) if mk_streams else None
        if inlet_mk is None:
            print("WARNING: no Markers stream; latency & ground-truth unavailable.")

    fs = int(round(inlet_eeg.info().nominal_srate()))
    n_ch = inlet_eeg.info().channel_count()
    win_samp = int(args.window * fs)
    print(f"EEG fs={fs} Hz, n_ch={n_ch}, window={args.window}s ({win_samp} samples)")

    # 通道选择
    sel = None
    if args.chs:
        sel = [int(i) for i in args.chs.split(",")]

    # 双窗环形缓冲
    buf = np.zeros((win_samp*2, n_ch))
    head = 0

    freqs = [float(f) for f in args.freqs.split(",")]
    refs = make_ref(fs, win_samp, freqs, harmonics=3)
    cca = CCA(n_components=1)

    # 日志
    out_csv = open(args.latlog, "w", newline="", encoding="utf-8")
    wr = csv.writer(out_csv)
    wr.writerow(["lsl_trial_start","lsl_pred_time","latency_sec","true_freq","pred_freq","raw_pred","method","window_s","note","score"])

    last_trial_start = None
    last_true = None
    hist = deque(maxlen=max(1, args.vote))

    print("Start online decoding...")
    try:
        while True:
            # 读 Markers（非阻塞）
            if inlet_mk:
                while True:
                    m, ts = inlet_mk.pull_sample(timeout=0.0)
                    if m is None: break
                    s = str(m[0])
                    if s.startswith("TRIAL_START"):
                        last_trial_start = ts
                        parts = s.split("|"); last_true = float(parts[1]) if len(parts)>1 else None
                    elif s.startswith("TRIAL_END"):
                        parts = s.split("|"); last_true = float(parts[1]) if len(parts)>1 else last_true

            # 取 EEG 块
            chunk, ts = inlet_eeg.pull_chunk(timeout=0.2)
            if not chunk: continue
            x = np.asarray(chunk)
            nnew = x.shape[0]

            # 写环形缓冲
            if nnew >= buf.shape[0]:
                buf[:] = x[-buf.shape[0]:,:]; head = 0
            else:
                end = head + nnew
                if end <= buf.shape[0]:
                    buf[head:end,:] = x
                else:
                    part = buf.shape[0] - head
                    buf[head:,:] = x[:part,:]; buf[:nnew-part,:] = x[part:,:]
                head = (head + nnew) % buf.shape[0]

            # 取末尾一个窗
            if head >= win_samp:
                seg = buf[head-win_samp:head,:]
            else:
                seg = np.vstack([buf[buf.shape[0]-(win_samp-head):,:], buf[:head,:]])

            # 通道子集
            if sel: seg = seg[:, sel]

            # 预处理：陷波+去直流（带通在窄带步骤内做）
            segf = apply_filter(seg, fs, notch=args.notch)

            # 逐频打分（谐波+窄带）
            best_f, best_score, best_raw = None, -1, None
            for f in freqs:
                sc = score_one(segf, fs, f, refs[f], cca)
                if sc > best_score:
                    best_score, best_f = sc, f

            # 多数投票
            hist.append(best_f)
            voted = majority_vote(hist)
            raw_pred = best_f
            pred_f = voted if voted is not None else raw_pred

            pred_time = local_clock()
            latency = (pred_time - last_trial_start) if last_trial_start is not None else np.nan
            note = ""
            if last_true is not None:
                note = "CORRECT" if abs(pred_f - last_true) < 1e-6 else "WRONG"

            print(f"[{pred_time:.3f}] Pred={pred_f:.1f}Hz (score={best_score:.3f}) True={last_true}Hz Lat={latency:.3f}s {note}")
            wr.writerow([last_trial_start, pred_time, latency, last_true, pred_f, raw_pred, "CCA+", args.window, note, best_score]); out_csv.flush()

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        out_csv.close()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=float, default=1.5)
    ap.add_argument("--freqs", type=str, default="10,12,15,20")
    ap.add_argument("--notch", type=float, default=50.0)  # 北京 50Hz
    ap.add_argument("--chs", type=str, default="", help="使用的通道索引（逗号分隔），例如 0,1,2,3")
    ap.add_argument("--vote", type=int, default=3, help="多数投票窗口大小，=1 关闭投票")
    ap.add_argument("--no-markers", action="store_true", help="不连接 Markers 流（纯预测）")
    ap.add_argument("--latlog", type=str, default=r"C:\Users\23842\Desktop\bci\data\logs\latency.csv")
    args = ap.parse_args()
    main(args)