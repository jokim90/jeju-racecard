"""출마표(latest.json의 sheet)로 출전마별 승리 확률과 이야기 재료(근거)를 계산해 latest.json의 "model"에 기록한다.
배당은 쓰지 않는다. 각 경주는 그 경주일 이전 기록만으로 계산한다.

python3 model/predict.py site/latest.json
"""
import json, math, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jeju_model as M  # noqa: E402

LABEL = {  # 근거 키 (화면에서 한국어·영어 문장으로 바꾼다)
    "fig_last_z": "fig_last", "fig_avg3_z": "fig_avg3", "fig_best5_z": "fig_best", "fin_speed_avg3_z": "kick",
    "jk_rate_z": "jockey", "tr_rate_z": "trainer", "first_up": "fresh", "debut": "debut", "lnprev_z": "unexposed",
    "gate_z": "gate", "dist_fit_z": "distance", "early_avg3_z": "early", "place_rate_z": "consistency",
    "pct_last_z": "last_run", "win_prev_z": "wins", "sire_rate_z": "sire", "cls_drop_z": "class", "wg_chg_z": "weight_chg",
    "wgBudam_z": "weight", "rating_z": "rating", "age_z": "age", "age_z2": "age", "tr14_z": "work", "trm14_z": "work",
    "tr30_z": "work", "trm30_z": "work", "ldays_z": "layoff", "small": "breed",
}


def r1(x, nd=1):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), nd)


def main(path):
    t0 = time.time()
    bundle = json.loads(Path(path).read_text(encoding="utf-8"))
    sheet = bundle.get("sheet") or []
    if not sheet:
        print("출마표가 비어 있어 예측을 건너뜁니다."); return
    coef = json.loads(M.COEF.read_text(encoding="utf-8"))
    w = np.array(coef["coef"]); assert coef["cols"] == M.COLS, "coef.json과 피처 목록이 다릅니다. train.py를 다시 실행하세요."

    hist = M.load_history()
    hist_keys = set(zip(hist.rcDate.astype(str), hist.rcNo.astype(str)))
    srows = M.sheet_rows(sheet)
    new = srows[~srows.apply(lambda x: (x.rcDate, x.rcNo) in hist_keys, axis=1)]
    allr = pd.concat([hist, new], ignore_index=True)
    want = {f"J_{a}_{b}" for a, b in zip(srows.rcDate, srows.rcNo)}
    d = M.build(allr, M.load_horses(), M.load_training())
    hist_by_horse = d[d.started].sort_values("date").groupby("hrNo")
    d = d[d.rk.isin(want)].copy()
    # 결과가 이미 있는 지난 경주는 실제 출주마만, 다가오는 경주는 출마표 전원
    d = d[d.started | d.ordn.isna()]
    d = M.zscore(d)
    d["score"] = d[M.COLS].values @ w
    d["prob"] = M.race_probs(d.score.values, d.rk)
    d["rank"] = d.groupby("rk").prob.rank(ascending=False, method="first").astype(int)
    contrib = d[M.COLS].values * w
    fld = d.groupby("rk")

    def frank(col, asc=False):   # 필드 안 순위 (1=가장 좋음), 값 없으면 None
        return fld[col].rank(ascending=asc, method="min")

    d["fig_last_rk"] = frank("fig_last"); d["kick_rk"] = frank("fin_speed_avg3"); d["work_rk"] = frank("trm14")
    d["jk_rk"] = frank("jk_rate")
    races = {}
    for i, (_, x) in enumerate(d.iterrows()):
        c = contrib[i]
        order = np.argsort(-c)
        pros, seen = [], set()
        for j in order:
            if c[j] <= 0.02: break
            k = LABEL.get(M.COLS[j], M.COLS[j])
            if k not in seen: pros.append(k); seen.add(k)
        cons = []
        for j in np.argsort(c):
            if c[j] >= -0.02: break
            k = LABEL.get(M.COLS[j], M.COLS[j])
            if k not in cons and k not in seen: cons.append(k)
        prev = []
        if x.hrNo in hist_by_horse.groups:
            ph = hist_by_horse.get_group(x.hrNo)
            ph = ph[ph.date < x.date].tail(3).iloc[::-1]
            prev = [{"date": p.date.strftime("%Y%m%d"), "dist": int(p.dist), "ord": int(p.ordn), "fs": int(p.fs),
                     "fig": r1(p.fig, 0), "kick": r1(p.fin_speed), "early": r1(p.early_pct, 2)} for p in ph.itertuples()]
        e = x.early_avg3
        style = None if pd.isna(e) else ("front" if e <= 0.2 else "stalk" if e <= 0.45 else "mid" if e <= 0.75 else "closer")
        key = f"{x.date.strftime('%Y%m%d')}|{int(x.rcNo_i)}"
        races.setdefault(key, []).append({
            "no": int(x.chulNo), "hrNo": x.hrNo, "name": x.hrName, "prob": r1(x.prob * 100), "rank": int(x["rank"]),
            "pros": pros[:4], "cons": cons[:2], "prev": prev,
            "f": {"figLast": r1(x.fig_last, 0), "figAvg3": r1(x.fig_avg3, 0), "figBest": r1(x.fig_best5, 0),
                  "figLastRk": r1(x.fig_last_rk, 0), "kick": r1(x.fin_speed_avg3, 2), "kickRk": r1(x.kick_rk, 0),
                  "style": style, "days": r1(x.days, 0), "debut": bool(x.debut), "fresh": bool(x.first_up),
                  "starts": int(x.n_prev), "wins": int(x.win_prev), "placeRate": r1(x.place_rate * 100, 0) if x.n_prev >= 3 else None,
                  "jk": x.jkName, "jkRate": r1(x.jk_rate * 100), "jkRk": r1(x.jk_rk, 0), "tr": x.trName, "trRate": r1(x.tr_rate * 100),
                  "distFit": r1(x.dist_fit, 0), "clsDrop": r1(x.cls_drop, 0), "wgt": r1(x.wgBudam), "wgChg": r1(x.wg_chg),
                  "sire": None if pd.isna(x.fhrNm) or x.fhrNm == "-" else x.fhrNm, "sireRate": r1(x.sire_rate * 100),
                  "age": r1(x.age, 0), "gate": int(x.chulNo), "field": int(x.fs), "work14": r1(x.trm14 / 60, 0), "workRk": r1(x.work_rk, 0)}})
    for v in races.values():
        v.sort(key=lambda a: a["rank"])
    bundle["model"] = {"version": 1, "trained_through": coef["trained_through"], "validation": coef["validation"],
                       "built": time.strftime("%Y-%m-%d %H:%M"), "races": races}
    Path(path).write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"모형 예측: {len(races)}경주, {sum(len(v) for v in races.values())}두 ({time.time()-t0:.0f}초)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "site/latest.json")
