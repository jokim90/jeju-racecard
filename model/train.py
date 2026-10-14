"""출마표 모형 학습. 2025-01~2026-09 성능을 먼저 확인(2024까지로 학습)한 뒤, 전체 기간으로 다시 학습해 coef.json에 저장한다.
python3 model/train.py"""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import jeju_model as M

t0 = time.time()
d = M.build(M.load_history(), M.load_horses(), M.load_training())
d = d[d.started & (d.groupby("rk").win.transform("sum") == 1)].reset_index(drop=True)
d = M.zscore(d)
d["year"] = d.date.dt.year
use = d.year != 2020                       # 2020: 무관중·배당 이상 시기
tr = d[use & (d.year <= 2024)]; te = d[(d.date >= "2025-01-01") & (d.date < "2026-10-01")].copy()
w = M.fit(tr)
te["p"] = M.race_probs(te[M.COLS].values @ w, te.rk)
rank = te.groupby("rk").p.rank(ascending=False, method="first"); win = te.win == 1
wv = np.where(M.num(te.winOdds) > 0, 1 / M.num(te.winOdds), np.nan)
te["m"] = (pd.Series(wv, index=te.index) / pd.Series(wv, index=te.index).groupby(te.rk).transform("sum")).fillna(1 / te.fs)
mrank = te.groupby("rk").m.rank(ascending=False, method="first")
check = {"races": int(te.rk.nunique()), "loglik": float(np.log(te.p[win]).mean()),
         "top1": float((rank[win] == 1).mean()), "top2": float((rank[win] <= 2).mean()), "top4": float((rank[win] <= 4).mean()),
         "market_top1": float((mrank[win] == 1).mean()), "market_top4": float((mrank[win] <= 4).mean())}
print("검증 2025-01~2026-09 (2024까지 학습):", {k: round(v, 3) for k, v in check.items()})
w_all = M.fit(d[use])
json.dump({"cols": M.COLS, "coef": [float(x) for x in w_all], "trained_through": str(d.date.max().date()),
           "validation": check}, open(M.COEF, "w"), ensure_ascii=False, indent=1)
print("저장:", M.COEF.name, "학습 기간 ~", d.date.max().date(), f"({time.time()-t0:.0f}초)")
for k, v in sorted(zip(M.COLS, w_all), key=lambda kv: -abs(kv[1]))[:10]:
    print(f"  {k:18s} {v:+.3f}")
