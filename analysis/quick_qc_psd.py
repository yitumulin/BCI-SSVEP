# analysis/quick_qc_psd.py
import argparse, os, json, numpy as np, matplotlib.pyplot as plt
from pylsl import StreamInlet
try:
    from pylsl.stream import resolve_stream
except:
    from pylsl import resolve_stream
from scipy.signal import welch
from pathlib import Path

def band_power(f, Pxx, f0, bw=0.5):
    m = (f>=f0-bw) & (f<=f0+bw)
    return np.trapz(Pxx[m], f[m]) if np.any(m) else 0.0

def neighbor_power(f, Pxx, f0, inner=0.5, outer=2.0):
    m = ((f>=f0-outer)&(f<=f0-inner)) | ((f>=f0+inner)&(f<=f0+outer))
    return np.trapz(Pxx[m], f[m]) if np.any(m) else 1e-12

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dur", type=float, default=15.0)
    ap.add_argument("--freqs", type=str, default="10,12,15,20")
    ap.add_argument("--out", type=str, default="data/logs/qc")
    ap.add_argument("--topk", type=int, default=4)
    args = ap.parse_args()

    print("Resolving EEG stream...")
    eeg = resolve_stream('type','EEG')
    if not eeg: raise RuntimeError("No EEG stream found.")
    inlet = StreamInlet(eeg[0], max_buflen=int(args.dur)+2)
    fs = int(round(inlet.info().nominal_srate()))
    n_ch = inlet.info().channel_count()
    n = int(args.dur * fs)
    print(f"EEG fs={fs}Hz, n_ch={n_ch}, capture {args.dur}s")

    data = []
    while len(data) < n:
        chunk, _ = inlet.pull_chunk(timeout=0.2)
        if chunk: data.extend(chunk)
    X = np.asarray(data)[:n, :]  # (n, n_ch)
    X = X - X.mean(axis=0, keepdims=True)

    freqs = [float(x) for x in args.freqs.split(",")]
    # Welch
    f, P = welch(X, fs=fs, nperseg=min(1024, n), axis=0)

    # SNR per channel
    ch_scores = np.zeros(n_ch, dtype=float)
    for ch in range(n_ch):
        score = 0.0
        for f0, w in [(f_,1.0) for f_ in freqs] + [(2*f_,0.5) for f_ in freqs]:
            p_sig = band_power(f, P[:,ch], f0, bw=0.5)
            p_nb  = neighbor_power(f, P[:,ch], f0, inner=0.5, outer=2.0)
            score += w * (p_sig / max(p_nb, 1e-12))
        ch_scores[ch] = score

    order = np.argsort(ch_scores)[::-1]
    topk = order[:args.topk].tolist()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    # save selected channels
    (outdir/"selected_chs.txt").write_text(",".join(map(str, topk)), encoding="utf-8")
    # save json
    json.dump({"fs":fs,"n_ch":n_ch,"scores":ch_scores.tolist(),"order":order.tolist(),"topk":topk},
              open(outdir/"qc.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    # plot
    plt.figure()
    plt.bar(np.arange(n_ch), ch_scores)
    plt.xlabel("Channel index"); plt.ylabel("SNR score")
    plt.title(f"QC SNR (Top{args.topk}={topk})")
    plt.tight_layout()
    plt.savefig(outdir/"qc_report.png", dpi=200)
    plt.close()
    print("QC done. Selected channels:", topk)

if __name__ == "__main__":
    main()
