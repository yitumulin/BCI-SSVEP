import csv, collections, argparse

def eval_file(p, method=None):
    tot=cor=0
    per=collections.defaultdict(lambda:[0,0])
    with open(p,encoding="utf-8") as f:
        r=csv.DictReader(f)
        for row in r:
            if method and row.get("method")!=method: 
                continue
            tf=row.get("true_freq","")
            pf=row.get("pred_freq","")
            if tf in ("","None","nan") or pf in ("","None","nan"):
                continue
            tf=float(tf); pf=float(pf)
            tot+=1; per[tf][0]+=1; per[tf][1]+= (abs(tf-pf)<1e-6)
            cor += (abs(tf-pf)<1e-6)
    return tot, cor, per

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--csv", default=r"C:\Users\23842\Desktop\bci\data\logs\latency.csv")
    args=ap.parse_args()
    for m in (None,"CCA+","FBCCA","CCA"):
        name = m if m else "ALL"
        tot, cor, per = eval_file(args.csv, m)
        if tot==0:
            print(f"{name}: no trials")
            continue
        print(f"{name}: ACC={cor/tot*100:.1f}% (n={tot})")
        for f,(n,c) in sorted(per.items()):
            print(f"  {int(f)} Hz: {c/n*100:.1f}% (n={n})")