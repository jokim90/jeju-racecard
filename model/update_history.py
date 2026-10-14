"""모형 이력 갱신: 기본 파일 이후의 새 경주성적·일일 훈련·새 마필을 history/*_new.csv에 붙인다.
API 호출이 실패해도 지금까지의 이력으로 예측할 수 있게 오류만 알리고 정상 종료한다.

JEJU_API_KEY=... python3 model/update_history.py [YYYYMMDD 오늘]
"""
import datetime as dt, os, sys, time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collector"))
import jeju_model as M  # noqa: E402
import jeju_collect as C  # noqa: E402

C.ENDPOINTS["train"] = ("API18_1/dailyTraining_1", "json")
RES_COLS = list(pd.read_csv(M.HIST / "results.csv.gz", dtype=str, nrows=0).columns)


def append(name, rows, keys):
    if rows is None or rows.empty:
        return 0
    path = M.HIST / f"{name}_new.csv"
    old = pd.read_csv(path, dtype=str) if path.exists() and path.stat().st_size else pd.DataFrame(columns=rows.columns)
    allr = pd.concat([old, rows.astype(str)], ignore_index=True).drop_duplicates(keys, keep="last")
    allr.to_csv(path, index=False)
    return len(allr) - len(old)


def main():
    key = os.environ.get("JEJU_API_KEY") or os.environ.get("KRA_API_KEY")
    if not key:
        print("인증키가 없어 이력 갱신을 건너뜁니다."); return
    today = dt.datetime.strptime(sys.argv[1], "%Y%m%d").date() if len(sys.argv) > 1 else dt.date.today()
    errors = []

    # 1) 경주성적·구간기록: 이력의 마지막 날 다음날부터 오늘까지 (최대 60일)
    hist = M.load_history()
    last = dt.datetime.strptime(hist.rcDate.astype(str).max(), "%Y%m%d").date()
    start = max(last + dt.timedelta(days=1), today - dt.timedelta(days=60))
    rows, day = [], start
    while day <= today:
        try:
            rows += C.fetch_all(key, "pace", {"meet": C.MEET_JEJU, "rc_date": day.strftime("%Y%m%d")}, max_pages=3)
        except C.ApiError as e:
            errors.append(str(e)); break
        day += dt.timedelta(days=1)
    res = pd.DataFrame(rows)
    if not res.empty:
        res = res[[c for c in RES_COLS if c in res.columns]]
        res = res[pd.to_numeric(res.get("ord"), errors="coerce").fillna(0) > 0]
    n_res = append("results", res, ["rcDate", "rcNo", "chulNo"])
    print(f"· 경주성적 {start}~{today}: 새 {n_res}건")

    # 2) 일일 훈련: 이번 달과 지난달 (말·날짜별 합계)
    trows = []
    for m in {today.strftime("%Y%m"), (today.replace(day=1) - dt.timedelta(days=1)).strftime("%Y%m")}:
        try:
            trows += C.fetch_all(key, "train", {"meet": C.MEET_JEJU, "tr_month": m}, max_pages=40, rows=1000)
        except C.ApiError as e:
            errors.append(f"일일 훈련(API18_1): {e}"); break
    if trows:
        t = pd.DataFrame(trows)
        t["trTerm"] = pd.to_numeric(t.trTerm, errors="coerce")
        t = t.groupby(["hrNo", "trDate"]).agg(cnt=("trTerm", "size"), mins=("trTerm", "sum")).reset_index()
        print(f"· 일일 훈련: 새 {append('training', t, ['hrNo', 'trDate'])}건")

    # 3) 새 마필: 이력·출마표에 있으나 마필 정보가 없는 말
    import json
    known = set(M._str7(M.load_horses().hrNo))
    nos = set(M._str7(M.load_history().hrNo))
    lj = HERE.parent / "site" / "latest.json"
    if lj.exists():
        nos |= {str(r.get("hrNo")).zfill(7) for r in json.loads(lj.read_text(encoding="utf-8")).get("sheet", []) if r.get("hrNo")}
    hrows = []
    for n in sorted(nos - known)[:300]:
        try:
            items, _ = C.call(key, "horse", {"hr_no": n, "pageNo": 1, "numOfRows": 10})
            if items:
                hrows.append(items[0])
        except C.ApiError as e:
            errors.append(f"마필 정보: {e}"); break
    if hrows:
        h = pd.DataFrame(hrows)
        h = h[[c for c in ["hrNo", "hrNm", "breed", "birthDt", "sex", "fhrNm", "fhrNo", "mhrNm"] if c in h.columns]]
        print(f"· 마필 정보: 새 {append('horses', h, ['hrNo'])}두")
    for e in dict.fromkeys(errors):
        print("  확인 필요:", e)


if __name__ == "__main__":
    main()
