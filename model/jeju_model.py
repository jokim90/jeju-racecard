"""제주 출마표 분석 모형 — 피처 계산의 단일 출처.

배당은 쓰지 않는다. 모든 피처는 그 경주일 이전 기록만 쓴다(출마표 시점에 알 수 있는 정보).
당일 마체중 변화와 당일 주로 상태는 출마표 시점에 알 수 없으므로 쓰지 않는다.

    history/results.csv.gz   경주성적·구간기록 (API4_3, meet=2)
    history/horses.csv.gz    마필 정보 (API42_1)
    history/training.csv.gz  일일 훈련, 말·날짜별 합계 (API18_1)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
HIST = HERE / "history"
COEF = HERE / "coef.json"

Z_FEATS = ["fig_last", "fig_avg3", "fig_best5", "early_avg3", "fin_speed_avg3", "jk_rate", "tr_rate", "wgBudam",
           "rating", "lnprev", "ldays", "win_prev", "place_rate", "pct_last", "cls_drop", "wg_chg", "dist_fit",
           "sire_rate", "age", "gate", "tr14", "trm14", "tr30", "trm30"]
RAW_FEATS = ["age_z2", "debut", "first_up", "small"]
COLS = [c + "_z" for c in Z_FEATS] + RAW_FEATS

num = lambda s: pd.to_numeric(s, errors="coerce")


def _str7(s):
    return s.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)


def _load(name: str) -> pd.DataFrame:
    """기본 파일(name.csv.gz) + 매일 갱신분(name_new.csv). 같은 행은 갱신분을 남긴다."""
    base = pd.read_csv(HIST / f"{name}.csv.gz", dtype=str)
    new = HIST / f"{name}_new.csv"
    if new.exists() and new.stat().st_size > 0:
        base = pd.concat([base, pd.read_csv(new, dtype=str)], ignore_index=True)
    keys = {"results": ["rcDate", "rcNo", "chulNo"], "training": ["hrNo", "trDate"], "horses": ["hrNo"]}[name]
    return base.drop_duplicates(keys, keep="last").reset_index(drop=True)


def load_history() -> pd.DataFrame:
    return _load("results")


def load_horses() -> pd.DataFrame:
    return _load("horses")


def load_training() -> pd.DataFrame:
    return _load("training")


def sheet_rows(sheet: list[dict]) -> pd.DataFrame:
    """출마표(API26_2) 항목을 이력과 같은 열 구조로 바꾼다. 결과 열은 비워 둔다."""
    s = pd.DataFrame(sheet)
    if s.empty:
        return s
    out = pd.DataFrame({
        "rcDate": s.rcDate.astype(str), "rcNo": s.rcNo.astype(str), "chulNo": s.chulNo.astype(str),
        "hrNo": _str7(s.hrNo), "hrName": s.hrName, "jkNo": s.jkNo.astype(str), "jkName": s.jkName,
        "trNo": s.trNo.astype(str), "trName": s.trName, "age": s.age.astype(str), "sex": s.sex,
        "rank": s["rank"], "rating": s.rating.astype(str), "rcDist": s.rcDist.astype(str),
        "wgBudam": s.wgBudam.astype(str), "rcName": s.rcName,
    })
    out["ord"] = ""
    return out


def build(results: pd.DataFrame, horses: pd.DataFrame, training: pd.DataFrame) -> pd.DataFrame:
    """이력(+ 아직 결과가 없는 출마표 행)에서 경주 전 피처를 계산한다."""
    r = results.copy()
    r["hrNo"] = _str7(r.hrNo)
    r["rk"] = "J_" + r.rcDate.astype(str) + "_" + r.rcNo.astype(str)
    r["chulNo"] = num(r.chulNo).astype(int)
    r["date"] = pd.to_datetime(r.rcDate.astype(str))
    r["rcNo_i"] = num(r.rcNo)
    r["dist"] = num(r.rcDist)
    r["grp"] = np.where(r["rank"].fillna("").str.startswith("한"), "H", "J")
    r["ordn"] = num(r.ord)
    r["t"] = num(r.get("rcTime")); r["late"] = num(r.get("jeG3fTime")); r["s1o"] = num(r.get("sjS1fOrd"))
    done = (r.ordn > 0) & (r.ordn < 90)
    ok = done & (r.t > 0) & (r.late > 0) & (r.t > r.late)
    r.loc[~ok, ["t", "late"]] = np.nan
    r["early"] = r.t - r.late
    r["fs"] = r.groupby("rk").chulNo.transform("size")
    r["started"] = done
    r["win"] = (r.ordn == 1).astype(int)
    r["early_pct"] = ((r.s1o - 1) / (r.fs - 1).clip(lower=1)).where(r.s1o > 0)
    r["wgBudam"] = num(r.wgBudam)
    r["rating"] = num(r.rating)
    r["cls"] = num(r["rank"].str.extract(r"(\d)")[0])
    r["han"] = (r.grp == "H").astype(float)
    r["age_given"] = num(r.get("age"))

    # 스피드 지수: 마종 그룹 × 거리 기준 기록(2019-2022 완주마 중앙값) 대비, 당일 주로 보정, 0.1초/km
    base = r[r.date < "2023-01-01"]
    par = base.groupby(["grp", "dist"]).agg(pt=("t", "median"), n=("t", "count"))
    r = r.join(par, on=["grp", "dist"])
    r["dev"] = (r.t - r.pt) / r.dist * 1000
    day_var = r.groupby("rk").agg(date=("date", "first"), dev=("dev", "median")).groupby("date").dev.median()
    r["fig"] = -(r.dev - r.date.map(day_var)) * 10
    r.loc[r.n < 30, "fig"] = np.nan
    r["fin_speed"] = r.groupby("rk").late.transform("median") - r.late       # + = 필드보다 빠른 마지막 600m(초)
    r["pct"] = (1 - (r.ordn.clip(upper=r.fs) - 1) / (r.fs - 1).clip(lower=1)).where(done)
    r["top3"] = (done & (r.ordn <= 3)).astype(int)

    # 말별 이전 기록
    r = r.sort_values(["hrNo", "date", "rcNo_i"]).reset_index(drop=True)
    h = r.groupby("hrNo")
    roll = lambda c, k, f="mean": h[c].transform(lambda s: getattr(s.shift(1).rolling(k, min_periods=1), f)())
    r["fig_last"] = h.fig.shift(1)
    r["fig_avg3"] = roll("fig", 3)
    r["fig_best5"] = roll("fig", 5, "max")
    r["early_avg3"] = roll("early_pct", 3)
    r["fin_speed_avg3"] = roll("fin_speed", 3)
    r["n_prev"] = h.cumcount()
    r["days"] = (r.date - h.date.shift(1)).dt.days
    cum = lambda c: h[c].transform(lambda s: s.shift(1).fillna(0).cumsum())
    r["win_prev"] = cum("win")
    r["place_rate"] = (cum("top3") + 0.3) / (r.n_prev + 1)
    r["pct_last"] = h.pct.shift(1)
    r["cls_drop"] = (r.cls - h.cls.shift(1)).where(r.han == h.han.shift(1))
    r["wg_chg"] = r.wgBudam - h.wgBudam.shift(1)
    r["last_dist"] = h.dist.shift(1); r["last_date"] = h.date.shift(1)
    r["last_ord"] = h.ordn.shift(1); r["last_fs"] = h.fs.shift(1)

    # 거리 적성: 이전 경주 중 ±100m 경주의 평균 스피드 지수 - 최근 3전 평균
    out = np.full(len(r), np.nan)
    figs, dists = r.fig.values, r.dist.values
    for _, idx in r.groupby("hrNo").indices.items():
        for k in range(1, len(idx)):
            prev = idx[:k]
            m = (np.abs(dists[prev] - dists[idx[k]]) <= 100) & ~np.isnan(figs[prev])
            if m.any():
                out[idx[k]] = figs[prev][m].mean()
    r["dist_fit"] = out - r.fig_avg3

    # 기수·조교사·부마: 그 날 이전 승률 (경험적 베이즈 수축)
    base_rate = r.loc[r.started, "win"].mean()

    def prior_rate(key, k):
        x = r[r[key].notna() & (r[key].astype(str) != "-")]
        dd = x.groupby([key, "date"]).agg(w=("win", "sum"), n=("started", "sum")).reset_index().sort_values("date")
        dd["W"] = dd.groupby(key).w.cumsum() - dd.w
        dd["N"] = dd.groupby(key).n.cumsum() - dd.n
        dd["rate"] = (dd.W + base_rate * k) / (dd.N + k)
        dd["starts"] = dd.N
        return r[[key, "date"]].merge(dd[[key, "date", "rate", "starts"]], on=[key, "date"], how="left")

    jk = prior_rate("jkNo", 50); r["jk_rate"] = jk.rate.fillna(base_rate).values; r["jk_starts"] = jk.starts.values
    tr = prior_rate("trNo", 50); r["tr_rate"] = tr.rate.fillna(base_rate).values
    H = horses.copy(); H["hrNo"] = _str7(H.hrNo)
    r = r.merge(H[["hrNo", "breed", "birthDt", "fhrNo", "fhrNm"]].drop_duplicates("hrNo"), on="hrNo", how="left")
    sr = prior_rate("fhrNo", 100); r["sire_rate"] = sr.rate.fillna(base_rate).values
    r["age"] = (r.date - pd.to_datetime(r.birthDt, format="%Y%m%d", errors="coerce")).dt.days / 365.25
    r["age"] = r.age.fillna(r.age_given)
    r["small"] = (r.breed == "소형마").astype(float)
    r["gate"] = r.chulNo / r.fs

    # 일일 훈련: 경주 전 14일·30일 횟수와 시간(분)
    T = training.copy(); T["hrNo"] = _str7(T.hrNo); T["tday"] = pd.to_datetime(T.trDate.astype(str))
    T["cnt"] = num(T.cnt); T["mins"] = num(T.mins)
    tg = {k: (v.tday.values, v.cnt.values, v.mins.values) for k, v in T.groupby("hrNo")}
    res = np.zeros((len(r), 4))
    for i, (hr, dt) in enumerate(zip(r.hrNo.values, r.date.values)):
        t = tg.get(hr)
        if t is None:
            continue
        for j, days in enumerate((14, 30)):
            m = (t[0] < dt) & (t[0] >= dt - np.timedelta64(days, "D"))
            res[i, 2 * j] = t[1][m].sum(); res[i, 2 * j + 1] = t[2][m].sum()
    r["tr14"], r["trm14"], r["tr30"], r["trm30"] = res.T

    r["debut"] = (r.n_prev == 0).astype(float)
    r["first_up"] = (r.days > 60).astype(float)
    r["ldays"] = np.log1p(r.days.fillna(0))
    r["lnprev"] = np.log1p(r.n_prev)
    return r.sort_values(["rk", "chulNo"]).reset_index(drop=True)


def zscore(d: pd.DataFrame) -> pd.DataFrame:
    """경주 안에서 표준화. 값이 없으면 0(그 경주 평균)으로 둔다."""
    d = d.copy()
    for c in Z_FEATS:
        s = d.groupby("rk")[c]
        d[c + "_z"] = ((d[c] - s.transform("mean")) / s.transform("std").replace(0, np.nan)).fillna(0)
    d["age_z2"] = d.age_z ** 2
    return d


def race_probs(score: np.ndarray, rk: pd.Series) -> np.ndarray:
    s = pd.Series(score, index=rk.index)
    e = np.exp(s - s.groupby(rk).transform("max"))
    return (e / e.groupby(rk).transform("sum")).values


def fit(d: pd.DataFrame, lam: float = 1.0) -> np.ndarray:
    from scipy.optimize import minimize
    codes = d.rk.astype("category").cat.codes.values
    X, win, nr = d[COLS].values, d.win.values, codes.max() + 1

    def f(w):
        s = X @ w
        mx = np.full(nr, -np.inf); np.maximum.at(mx, codes, s)
        e = np.exp(s - mx[codes]); den = np.bincount(codes, e, nr)
        return -(s[win == 1] - mx[codes][win == 1] - np.log(den[codes][win == 1])).sum() + 0.5 * lam * (w ** 2).sum()

    return minimize(f, np.zeros(len(COLS)), method="L-BFGS-B").x
