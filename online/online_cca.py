import argparse, csv, os, json
import numpy as np
from collections import deque
from datetime import datetime
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

def make_ref_single(fs, n, f, harmonics=3):
    """生成单个频率的参考矩阵"""
    t = np.arange(n)/fs
    cols = []
    for h in range(1, harmonics+1):
        cols += [np.sin(2*np.pi*h*f*t), np.cos(2*np.pi*h*f*t)]
    return np.stack(cols, axis=1)

def tune_one_freq(segf, fs, f0, cca, delta=0.2, step=0.05):
    """频率细调：在f0±delta范围内网格搜索最优频率"""
    cand = np.arange(f0-delta, f0+delta+1e-9, step)
    best, best_s = f0, -1
    n = segf.shape[0]
    for f in cand:
        R = make_ref_single(fs, n, f, harmonics=3)
        try:
            cca.fit(segf, R)
            U, V = cca.transform(segf, R)
            sc = float(np.corrcoef(U[:,0].ravel(), V[:,0].ravel())[0,1])
            if sc > best_s:
                best_s, best = sc, f
        except:
            continue
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

    # 创建run目录和文件路径
    method_name = "CCA"
    runname = args.runname or f"{method_name}_w{args.window:.1f}_v{getattr(args,'vote',1)}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = os.path.join(args.outdir, runname)
    os.makedirs(run_dir, exist_ok=True)
    latlog_path = args.latlog or os.path.join(run_dir, "latency.csv")

    # 通道选择
    sel = None
    if args.auto_chs and (not args.chs):
        try:
            txt = open(r"data/logs/qc/selected_chs.txt","r",encoding="utf-8").read().strip()
            sel = [int(x) for x in txt.split(",") if x.strip()!=""]
            print("Auto channels from QC:", sel)
        except Exception:
            print("WARN: auto_chs enabled but selected_chs.txt not found; fallback to all channels.")
    elif args.chs:
        sel = [int(i) for i in args.chs.split(",")]

    # 双窗环形缓冲
    buf = np.zeros((win_samp*2, n_ch))
    head = 0

    freqs = [float(f) for f in args.freqs.split(",")]
    refs = make_ref(fs, win_samp, freqs, harmonics=3)
    cca = CCA(n_components=1)
    
    # 频率细调相关
    freq_map = {f: f for f in freqs}  # 原频率 -> 细调后频率
    tuned_freqs_done = set()  # 已完成细调的频率

    # 日志
    out_csv = open(latlog_path, "w", newline="", encoding="utf-8")
    wr = csv.writer(out_csv)
    wr.writerow(["lsl_trial_start","lsl_pred_time","latency_sec","true_freq","pred_freq","raw_pred","method","window_s","note","score","r1","r2","margin","early","locked","state"])
    
    # 保存meta.json
    meta = {
        "method": method_name,
        "window_s": args.window,
        "freqs": args.freqs,
        "notch": args.notch,
        "vote": getattr(args, "vote", None),
        "chs": getattr(args, "chs", None),
        "earlystop": getattr(args, "earlystop", False),
        "rmin": getattr(args, "rmin", None),
        "margin": getattr(args, "margin", None),
        "patience": getattr(args, "patience", None),
        "minwin": getattr(args, "minwin", None),
        "idle": getattr(args, "idle", False),
        "idle_rmin": getattr(args, "idle_rmin", None),
        "idle_margin": getattr(args, "idle_margin", None),
        "auto_chs": getattr(args, "auto_chs", False),
        "freq_tune": getattr(args, "freq_tune", False),
        "tuned_freqs": freq_map if args.freq_tune else {},
        "timestamp": datetime.now().isoformat(timespec="seconds")
    }
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Run folder: {run_dir}")
    print(f"[INFO] Log CSV   : {latlog_path}")

    # 早停相关初始化
    last_trial_start = None
    last_true = None
    trial_locked = False
    locked_pred = None
    locked_time = None
    consec_pred = None
    consec_count = 0
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
                    trial_locked = False
                    locked_pred = None
                    locked_time = None
                    consec_pred = None
                    consec_count = 0
                    parts = s.split("|"); last_true = float(parts[1]) if len(parts)>1 else None
                elif s.startswith("TRIAL_END"):
                    trial_locked = False
                    locked_pred = None
                    locked_time = None
                    consec_pred = None
                    consec_count = 0
                    last_true = float("nan")  # REST 阶段 ground-truth 为空

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

            # 频率细调逻辑
            if args.freq_tune and last_trial_start is not None and last_true is not None and not np.isnan(last_true):
                if last_true not in tuned_freqs_done:
                    print(f"Fine-tuning frequency {last_true}Hz...")
                    tuned_freq = tune_one_freq(segf, fs, last_true, cca)
                    freq_map[last_true] = tuned_freq
                    tuned_freqs_done.add(last_true)
                    print(f"Tuned {last_true}Hz -> {tuned_freq:.2f}Hz")
                    # 更新参考信号
                    refs[last_true] = make_ref_single(fs, win_samp, tuned_freq, harmonics=3)

            # 逐频打分（谐波+窄带）使用细调后的频率
            r_scores = []
            best_f, best_score, best_raw = None, -1, None
            for f in freqs:
                tuned_f = freq_map.get(f, f)
                sc = score_one(segf, fs, tuned_f, refs[f], cca)
                r_scores.append((f, sc))  # 仍用原频率标识
                if sc > best_score:
                    best_score, best_f = sc, f

            pred_time = local_clock()

            # 计算第二名r2和margin
            r_sorted = sorted(r_scores, key=lambda t: t[1], reverse=True)
            r1 = r_sorted[0][1] if r_sorted else -1
            r2 = r_sorted[1][1] if len(r_sorted) > 1 else -1
            margin = r1 - r2

            # Idle门控
            state = "CONTROL"
            if args.idle and (r1 < args.idle_rmin or margin < args.idle_margin):
                # 进入IDLE：不输出控制类预测
                voted = None
                raw_pred = None
                pred_f = None
                state = "IDLE"
            else:
                # 维持现有的投票/早停逻辑
                hist.append(best_f)
                voted = majority_vote(hist)
                raw_pred = best_f
                pred_f = voted if voted is not None else raw_pred

            early = False
            if not state == "IDLE" and args.earlystop and (inlet_mk is not None) and (last_trial_start is not None) and (not trial_locked):
                elapsed = pred_time - last_trial_start
                # 连续一致计数
                if consec_pred is None or consec_pred != best_f:
                    consec_pred = best_f
                    consec_count = 1
                else:
                    consec_count += 1
                # 判定是否早停
                if (elapsed >= args.minwin) and (r1 >= args.rmin) and (margin >= args.margin) and (consec_count >= args.patience):
                    trial_locked = True
                    locked_pred = best_f
                    locked_time = pred_time
                    early = True

            # 若已锁定，本trial内忽略后续窗（但仍可记录日志行，note标记为LOCKED）
            note_flags = []
            if early: note_flags.append("EARLY")
            if trial_locked: note_flags.append("LOCKED")
            
            latency = (pred_time - last_trial_start) if last_trial_start is not None else np.nan
            
            base_note = ""
            if last_true is not None:
                base_note = "CORRECT" if abs(pred_f - last_true) < 1e-6 else "WRONG"
            
            if base_note and note_flags:
                note = base_note + "|" + "|".join(note_flags)
            elif note_flags:
                note = "|".join(note_flags)
            else:
                note = base_note
                
            pred_str = f"{pred_f:.1f}Hz" if pred_f is not None else "IDLE"
            print(f"[{pred_time:.3f}] Pred={pred_str} (score={best_score:.3f}) True={last_true}Hz Lat={latency:.3f}s {note} State={state}")
            wr.writerow([last_trial_start, pred_time, latency, last_true, pred_f, raw_pred, "CCA+", args.window, note, best_score, r1, r2, margin, early, trial_locked, state]); out_csv.flush()

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
    ap.add_argument("--outdir", type=str, default=r"C:\Users\23842\Desktop\bci\data\logs")
    ap.add_argument("--runname", type=str, default=None, help="run folder name; default auto by method/window/vote/timestamp")
    ap.add_argument("--latlog", type=str, default=None, help="(optional) direct csv path; overrides run folder if set")
    ap.add_argument("--earlystop", action="store_true", help="enable adaptive early stopping")
    ap.add_argument("--rmin", type=float, default=0.45, help="min absolute corr r1 to allow early stop")
    ap.add_argument("--margin", type=float, default=0.15, help="min (r1-r2) margin for early stop")
    ap.add_argument("--patience", type=int, default=2, help="need same prediction for k consecutive windows")
    ap.add_argument("--minwin", type=float, default=0.6, help="earliest time after TRIAL_START to allow early decision (s)")
    ap.add_argument("--idle", action="store_true", help="启用IDLE门控（无注视时输出IDLE）")
    ap.add_argument("--idle_rmin", type=float, default=0.50, help="IDLE门控的r1阈值")
    ap.add_argument("--idle_margin", type=float, default=0.12, help="IDLE门控的(r1-r2)阈值")
    ap.add_argument("--auto_chs", action="store_true", help="从 data/logs/qc/selected_chs.txt 自动选通道")
    ap.add_argument("--freq_tune", action="store_true", help="启用频率细调（每个目标±0.2Hz内网格搜索）")
    args = ap.parse_args()
    main(args)