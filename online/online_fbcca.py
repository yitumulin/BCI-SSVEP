import argparse, csv
import numpy as np
from collections import deque
from pylsl import StreamInlet, local_clock
try:
    from pylsl.stream import resolve_stream
except Exception:
    from pylsl import resolve_stream
from scipy.signal import butter, filtfilt, iirnotch
from sklearn.cross_decomposition import CCA

def bandpass(x, fs, lo, hi, order=4):
    b,a = butter(order, [lo/(fs/2), hi/(fs/2)], btype='band')
    return filtfilt(b,a,x, axis=0)

def apply_filter(x, fs, notch=50.0):
    x = x.copy()
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

def fbcca_score(seg, fs, refs_f, cca, fb_bands):
    scores=[]
    for lo,hi,w in fb_bands:
        segb = bandpass(seg, fs, lo, hi)
        cca.fit(segb, refs_f)
        U, V = cca.transform(segb, refs_f)
        r = np.corrcoef(U[:,0].ravel(), V[:,0].ravel())[0,1]
        scores.append(max(0.0, float(r)) * w)
    return sum(scores)

def main(args):
    print("Resolving EEG stream...")
    eeg_streams = resolve_stream('type','EEG')
    if not eeg_streams: raise RuntimeError("No EEG stream found.")
    inlet = StreamInlet(eeg_streams[0], max_buflen=5)

    inlet_mk = None
    if not args.no_markers:
        print("Resolving Markers stream...")
        mk_streams = resolve_stream('type','Markers')
        inlet_mk = StreamInlet(mk_streams[0]) if mk_streams else None
        if inlet_mk is None:
            print("WARNING: no Markers stream; latency & ground-truth unavailable.")

    fs = int(round(inlet.info().nominal_srate()))
    n_ch = inlet.info().channel_count()
    win = int(args.window * fs)
    print(f"EEG fs={fs} Hz, n_ch={n_ch}, window={args.window}s ({win} samples)")

    freqs = [float(f) for f in args.freqs.split(",")]
    refs = make_ref(fs, win, freqs, harmonics=3)
    cca = CCA(n_components=1)

    # filter bank（经验值，可微调；低频权重大）
    fb_bands = [
        (8,14, 1.0),
        (14,20, 0.8),
        (20,26, 0.6),
        (26,32, 0.4),
    ]

    # 通道选择
    sel = [int(i) for i in args.chs.split(",")] if args.chs else None

    # 缓冲 & 日志
    buf = np.zeros((win*2, n_ch)); head=0
    out = open(args.latlog,"w",newline="",encoding="utf-8"); wr=csv.writer(out)
    wr.writerow(["lsl_trial_start","lsl_pred_time","latency_sec","true_freq","pred_freq","method","window_s","note","score"])

    hist = deque(maxlen=max(1,args.vote))
    last_trial_start=None; last_true=None

    try:
        while True:
            # markers
            if inlet_mk:
                while True:
                    m, ts = inlet_mk.pull_sample(timeout=0.0)
                    if m is None: break
                    s=str(m[0])
                    if s.startswith("TRIAL_START"):
                        last_trial_start = ts
                        parts = s.split("|"); last_true = float(parts[1]) if len(parts)>1 else None
                    elif s.startswith("TRIAL_END"):
                        parts = s.split("|"); last_true = float(parts[1]) if len(parts)>1 else last_true

            # eeg
            chunk, ts = inlet.pull_chunk(timeout=0.2)
            if not chunk: continue
            x = np.asarray(chunk); nnew = x.shape[0]
            if nnew >= buf.shape[0]:
                buf[:] = x[-buf.shape[0]:,:]; head=0
            else:
                end = head + nnew
                if end <= buf.shape[0]:
                    buf[head:end,:] = x
                else:
                    part = buf.shape[0] - head
                    buf[head:,:] = x[:part,:]; buf[:nnew-part,:] = x[part:,:]
                head = (head + nnew) % buf.shape[0]

            seg = buf[head-win:head,:] if head>=win else np.vstack([buf[buf.shape[0]-(win-head):,:], buf[:head,:]])
            if sel: seg = seg[:, sel]
            seg = apply_filter(seg, fs, notch=args.notch)

            best_f, best_s = None, -1
            for f in freqs:
                s = fbcca_score(seg, fs, refs[f], cca, fb_bands)
                if s > best_s:
                    best_s, best_f = s, f

            hist.append(best_f)
            pred_f = max(set(hist), key=hist.count) if len(hist)==hist.maxlen else best_f

            pred_time = local_clock()
            lat = (pred_time - last_trial_start) if last_trial_start is not None else np.nan
            note = ""
            if last_true is not None:
                note = "CORRECT" if abs(pred_f - last_true) < 1e-6 else "WRONG"

            print(f"[{pred_time:.3f}] Pred={pred_f:.1f}Hz (score={best_s:.3f}) True={last_true}Hz Lat={lat:.3f}s {note}")
            wr.writerow([last_trial_start, pred_time, lat, last_true, pred_f, "FBCCA", args.window, note, best_s]); out.flush()

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        out.close()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=float, default=1.5)
    ap.add_argument("--freqs", type=str, default="10,12,15,20")
    ap.add_argument("--notch", type=float, default=50.0)
    ap.add_argument("--chs", type=str, default="", help="使用的通道索引（逗号分隔）")
    ap.add_argument("--vote", type=int, default=3, help="多数投票窗口大小")
    ap.add_argument("--no-markers", action="store_true", help="不连接 Markers 流（纯预测）")
    ap.add_argument("--latlog", type=str, default=r"C:\Users\23842\Desktop\bci\data\logs\latency.csv")
    args = ap.parse_args()
    main(args)