# analysis/compute_metrics.py
import argparse, glob, os, math, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
from sklearn.metrics import confusion_matrix

def itr_bits_per_min(P, N, T):
    P = max(1e-9, min(1-1e-9, float(P)))
    return (60.0 / T) * (math.log2(N) + P*math.log2(P) + (1-P)*math.log2((1-P)/(N-1)))

def read_csv(csv_path):
    df = pd.read_csv(csv_path)
    for c in ("true_freq","pred_freq","latency_sec","window_s"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["correct"] = (df.get("true_freq") == df.get("pred_freq"))
    return df

def compute_idle_fp_rate(df):
    """计算REST段的Idle误报率"""
    if "state" not in df.columns:
        return np.nan
    
    # 识别REST段：true_freq为NaN或者在REST_START/REST_END之间
    rest_mask = df["true_freq"].isna()
    
    if not rest_mask.any():
        return np.nan
    
    rest_df = df[rest_mask]
    if len(rest_df) == 0:
        return np.nan
    
    # 计算REST段中state!=IDLE的比例（误报率）
    non_idle_count = (rest_df.get("state", "CONTROL") != "IDLE").sum()
    idle_fp_rate = non_idle_count / len(rest_df)
    return float(idle_fp_rate)

def compute_per_freq_stats(df_trial):
    """按频率计算统计信息"""
    if len(df_trial) == 0:
        return {}
    
    stats = {}
    mask = (~df_trial["true"].isna()) & (~df_trial["pred"].isna())
    
    if not mask.any():
        return stats
    
    for freq in df_trial.loc[mask, "true"].unique():
        freq_mask = df_trial["true"] == freq
        freq_data = df_trial[freq_mask]
        
        if len(freq_data) == 0:
            continue
            
        # 准确率
        acc = float(np.mean(freq_data["true"] == freq_data["pred"]))
        
        # 延迟统计
        lats = freq_data["lat_first"].dropna().values
        lat_median = float(np.median(lats)) if len(lats) > 0 else np.nan
        lat_mean = float(np.mean(lats)) if len(lats) > 0 else np.nan
        
        stats[freq] = {
            "accuracy": acc,
            "latency_median": lat_median,
            "latency_mean": lat_mean,
            "n_trials": len(freq_data)
        }
    
    return stats

def plot_per_freq_acc(per_freq_stats, out_path, title="Per-frequency Accuracy"):
    """绘制各频率准确率条形图"""
    if not per_freq_stats:
        return
    
    freqs = sorted(per_freq_stats.keys())
    accs = [per_freq_stats[f]["accuracy"] for f in freqs]
    
    fig = plt.figure(figsize=(8, 5))
    plt.bar(range(len(freqs)), accs, alpha=0.7)
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Trial Accuracy")
    plt.title(title)
    plt.xticks(range(len(freqs)), [f"{f:.0f}" for f in freqs])
    plt.ylim(0, 1.1)
    
    # 添加数值标签
    for i, acc in enumerate(accs):
        plt.text(i, acc + 0.02, f"{acc:.2f}", ha="center", va="bottom")
    
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)

def trial_aggregate(df):
    if "lsl_trial_start" not in df.columns:
        return pd.DataFrame(columns=["trial_id","true","pred","lat_first"])
    df2 = df.dropna(subset=["lsl_trial_start"]).copy()
    rows = []
    for tid, g in df2.groupby("lsl_trial_start"):
        true_vals = g["true_freq"].dropna().values
        true = Counter(true_vals).most_common(1)[0][0] if len(true_vals) else np.nan
        pred_vals = g["pred_freq"].dropna().values
        pred = Counter(pred_vals).most_common(1)[0][0] if len(pred_vals) else np.nan
        lat_first = g["latency_sec"].dropna().min() if "latency_sec" in g else np.nan
        rows.append({"trial_id": tid, "true": true, "pred": pred, "lat_first": lat_first})
    return pd.DataFrame(rows)

def plot_confmat(cm, classes, out_path, title="Confusion (trial)"):
    fig = plt.figure()
    plt.imshow(cm, interpolation="nearest")
    plt.title(title); plt.xlabel("Predicted"); plt.ylabel("True")
    plt.xticks(range(len(classes)), classes); plt.yticks(range(len(classes)), classes)
    plt.colorbar()
    for i in range(len(classes)):
        for j in range(len(classes)):
            plt.text(j, i, f"{cm[i,j]:.2f}", ha="center", va="center")
    plt.tight_layout(); fig.savefig(out_path, dpi=200); plt.close(fig)

def latency_hist(latencies, out_path):
    fig = plt.figure()
    plt.hist(latencies, bins=20)
    plt.xlabel("First-decision latency (s)"); plt.ylabel("Count"); plt.grid(True, alpha=0.3)
    plt.tight_layout(); fig.savefig(out_path, dpi=200); plt.close(fig)

def one_run(csv_path, classes, selection_time):
    run_dir = os.path.dirname(os.path.abspath(csv_path))
    run_name = os.path.basename(run_dir)
    df = read_csv(csv_path)
    # 从 meta.json（若存在）补充 method / window / vote
    meta_path = os.path.join(run_dir, "meta.json")
    meta = {}
    if os.path.isfile(meta_path):
        try:
            meta = json.load(open(meta_path, "r", encoding="utf-8"))
        except Exception:
            meta = {}
    method = meta.get("method", df.get("method", pd.Series(["UNK"])).iloc[0] if "method" in df.columns else "UNK")
    window = float(meta.get("window_s", pd.to_numeric(df.get("window_s")).dropna().iloc[0] if "window_s" in df.columns and df["window_s"].notna().any() else selection_time))

    # window-level
    df_eval = df.dropna(subset=["true_freq"]) if "true_freq" in df.columns else pd.DataFrame()
    acc_win = float(np.mean(df_eval["correct"])) if len(df_eval) else np.nan
    lat_mean_win = float(np.nanmean(df_eval["latency_sec"])) if "latency_sec" in df_eval else np.nan
    lat_med_win  = float(np.nanmedian(df_eval["latency_sec"])) if "latency_sec" in df_eval else np.nan
    itr_win = itr_bits_per_min(acc_win, len(classes), window) if not np.isnan(acc_win) else np.nan

    # trial-level
    df_trial = trial_aggregate(df)
    mask = (~df_trial["true"].isna()) & (~df_trial["pred"].isna())
    acc_trial = float(np.mean(df_trial.loc[mask, "true"] == df_trial.loc[mask, "pred"])) if mask.any() else np.nan
    lats = df_trial["lat_first"].dropna().values if "lat_first" in df_trial else np.array([])
    lat_mean_trial = float(np.mean(lats)) if lats.size else np.nan
    lat_median_trial = float(np.median(lats)) if lats.size else np.nan
    itr_trial = itr_bits_per_min(acc_trial, len(classes), selection_time) if not np.isnan(acc_trial) else np.nan
    
    # Idle误报率
    idle_fp_rate = compute_idle_fp_rate(df)
    
    # 分频率统计
    per_freq_stats = compute_per_freq_stats(df_trial)

    # 保存单 run 结果
    xlsx = os.path.join(run_dir, "metrics.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="raw")
        df_trial.to_excel(xw, index=False, sheet_name="trial_level")
        
        # 汇总表增加新指标
        summary_data = {
            "run": run_name, "method": method, "window_s": window,
            "acc_window": acc_win, "lat_mean_window": lat_mean_win, "lat_median_window": lat_med_win, "itr_window": itr_win,
            "acc_trial": acc_trial, "lat_mean_trial": lat_mean_trial, "lat_median_trial": lat_median_trial, "itr_trial": itr_trial,
            "idle_fp_rate": idle_fp_rate
        }
        
        # 添加分频率统计
        for freq, stats in per_freq_stats.items():
            summary_data[f"acc_freq_{freq:.0f}"] = stats["accuracy"]
            summary_data[f"lat_median_freq_{freq:.0f}"] = stats["latency_median"]
        
        pd.DataFrame([summary_data]).to_excel(xw, index=False, sheet_name="summary")
        
        # 分频率详情表
        if per_freq_stats:
            per_freq_df = pd.DataFrame([
                {"frequency": freq, **stats} for freq, stats in per_freq_stats.items()
            ])
            per_freq_df.to_excel(xw, index=False, sheet_name="per_frequency")

    # 图：混淆矩阵 & 延迟直方图
    if mask.any():
        # map labels
        lbl2idx = {c:i for i,c in enumerate(classes)}
        yt = np.array([lbl2idx.get(float(v), -1) for v in df_trial.loc[mask,"true"].values])
        yp = np.array([lbl2idx.get(float(v), -1) for v in df_trial.loc[mask,"pred"].values])
        ok = (yt>=0)&(yp>=0)
        if np.any(ok):
            cm = confusion_matrix(yt[ok], yp[ok], labels=list(range(len(classes)))).astype(float)
            cm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1e-9)
            plot_confmat(cm, classes, os.path.join(run_dir, "confmat.png"), title=f"Confusion (trial) {run_name}")
    if lats.size:
        latency_hist(lats, os.path.join(run_dir, "latency_hist.png"))
    
    # 绘制分频率准确率图
    if per_freq_stats:
        plot_per_freq_acc(per_freq_stats, os.path.join(run_dir, "per_freq.png"), title=f"Per-frequency Accuracy - {run_name}")

    # 返回汇总行（包含新指标）
    result = {
        "run": run_name, "dir": run_dir, "method": method, "window_s": window,
        "acc_window": acc_win, "lat_mean_window": lat_mean_win, "lat_median_window": lat_med_win, "itr_window": itr_win,
        "acc_trial": acc_trial, "lat_mean_trial": lat_mean_trial, "lat_median_trial": lat_median_trial, "itr_trial": itr_trial,
        "idle_fp_rate": idle_fp_rate
    }
    
    # 添加分频率统计到汇总
    for freq, stats in per_freq_stats.items():
        result[f"acc_freq_{freq:.0f}"] = stats["accuracy"]
        result[f"lat_median_freq_{freq:.0f}"] = stats["latency_median"]
    
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", nargs="*", help="one or more csv paths")
    ap.add_argument("--glob", type=str, help="e.g. data\\logs\\**\\latency.csv", default=None)
    ap.add_argument("--classes", type=str, default="10,12,15,20")
    ap.add_argument("--selection_time", type=float, default=3.0, help="per-trial selection time (s) for ITR")
    ap.add_argument("--batch_out", type=str, default=r"C:\Users\23842\Desktop\bci\data\logs\batch_summary.xlsx")
    args = ap.parse_args()

    classes = [float(x) for x in args.classes.split(",")]

    paths = []
    if args.glob: paths += glob.glob(args.glob, recursive=True)
    if args.csv:  paths += args.csv
    paths = [p for p in paths if os.path.isfile(p)]
    if not paths:
        print("No CSV found. Use --glob or --csv."); return

    rows = []
    for p in sorted(set(paths)):
        print("Processing:", p)
        try:
            rows.append(one_run(p, classes, args.selection_time))
        except Exception as e:
            print("  WARN failed:", e)

    if len(rows) >= 1:
        df = pd.DataFrame(rows)
        os.makedirs(os.path.dirname(args.batch_out), exist_ok=True)
        with pd.ExcelWriter(args.batch_out, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="summary")
        print("Batch summary saved to:", args.batch_out)

if __name__ == "__main__":
    main()