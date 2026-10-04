#!/usr/bin/env python3
"""
제주경마 레이스카드용 데이터 수집 스크립트

공공데이터포털(한국마사회) API 7종을 한 번에 호출해서
레이스카드 앱에 바로 불러올 수 있는 파일 하나(jeju_bundle_YYYYMMDD.json)로 합칩니다.

사용법 (Mac 터미널):
    export JEJU_API_KEY="발급받은_일반_인증키"
    python3 jeju_collect.py 20240817

    # 다가오는 경주 출전표만 받고 싶으면 날짜에 오늘 날짜를 넣으면 됩니다.
    # 출전표(API26_2)는 날짜와 관계없이 최근 한 달 치 제주 경주를 모두 받습니다.

    # 경주 결과 이력을 최대 몇 페이지까지 받을지 지정 (기본 20페이지 = 2,000건)
    python3 jeju_collect.py 20240817 --result-pages 50

    # 마필종합정보 조회를 건너뛰기 (트래픽 절약)
    python3 jeju_collect.py 20240817 --no-horses

필요한 것: Python 3.8 이상. 추가 설치 없음.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://apis.data.go.kr/B551015"
MEET_JEJU = 2
PAUSE = 0.15  # 호출 사이 대기(초). 초당 호출 제한(오류 23)을 피하기 위함

ENDPOINTS = {
    "sheet":    ("API26_2/entrySheet_2", "json"),           # 출전표 (시행 예정 경주, 최근 한 달)
    "races":    ("API312/textDataHoldJeRaceInfo", "json"),  # 제주경주정보
    "reg":      ("API324/textDataHoldJeRegInfo",  "json"),  # 제주출전등록
    "runs":     ("API315/textDataHoldJePtinInfo", "json"),  # 제주출전마
    "results":  ("jejuhorseresult/getjejuhorseresult", "json"),  # 제주경주마 경주성적
    "pace":     ("API4_3/raceResult_3", "json"),             # 전국 경주기록 (구간 통과 순위, 배당)
    "horse":    ("API42_1/totalHorseInfo_1", "xml"),         # 마필종합정보
    "jockeys":  ("jktresult/getjktresult", "xml"),           # 기수통산전적
    "trainers": ("trtresult/gettrtresult", "xml"),           # 조교사통산전적
}

ERRORS = {
    "12": "API 주소가 없습니다. 엔드포인트 이름을 확인하세요.",
    "20": "이 API에 대한 활용신청이 안 되어 있거나 승인 대기 중입니다.",
    "22": "오늘 호출 한도를 넘었습니다. 내일 다시 실행하세요.",
    "23": "초당 호출이 너무 많습니다. PAUSE 값을 늘리세요.",
    "30": "등록되지 않은 인증키입니다. 키를 확인하거나 승인 후 1~2시간 기다리세요.",
    "31": "인증키 사용 기한이 만료됐습니다.",
}


class ApiError(Exception):
    pass


def call(key, name, params):
    path, fmt = ENDPOINTS[name]
    q = {"ServiceKey": key, **params}
    if fmt == "json":
        q["_type"] = "json"
    url = f"{BASE}/{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "jeju-racecard/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8", "replace")
            break
        except Exception as e:  # 네트워크 일시 오류는 두 번까지 재시도
            if attempt == 2:
                raise ApiError(f"{name}: 연결 실패 ({e})")
            time.sleep(1.5)
    time.sleep(PAUSE)
    return parse(name, raw, fmt)


def parse(name, raw, fmt):
    text = raw.strip()
    if text.startswith("<"):
        root = ET.fromstring(text.replace("<script/>", ""))
        code = root.findtext(".//returnReasonCode") or root.findtext(".//resultCode")
        if code and code not in ("00", "0"):
            raise ApiError(f"{name}: 오류 {code} - {ERRORS.get(code, root.findtext('.//errMsg') or '')}")
        items = [{c.tag: (c.text or "") for c in it} for it in root.iter("item")]
        total = int(root.findtext(".//totalCount") or len(items))
        return items, total
    data = json.loads(text)
    if "OpenAPI_ServiceResponse" in data:
        h = data["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {})
        code = str(h.get("returnReasonCode", ""))
        raise ApiError(f"{name}: 오류 {code} - {ERRORS.get(code, h.get('errMsg', ''))}")
    body = data.get("response", {}).get("body", {})
    items = body.get("items") or {}
    items = items.get("item", []) if isinstance(items, dict) else []
    if isinstance(items, dict):
        items = [items]
    return items, int(body.get("totalCount") or 0)


def fetch_all(key, name, params, max_pages=1, rows=100):
    out = []
    for page in range(1, max_pages + 1):
        items, total = call(key, name, {**params, "pageNo": page, "numOfRows": rows})
        out.extend(items)
        if len(out) >= total or not items:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description="제주경마 레이스카드 데이터 수집")
    ap.add_argument("race_dt", help="경주일자 YYYYMMDD (예: 20240817)")
    ap.add_argument("--result-pages", type=int, default=20, help="경주성적 최대 페이지 수 (1페이지=100건)")
    ap.add_argument("--no-horses", action="store_true", help="마필종합정보 조회 생략")
    ap.add_argument("--key", default=os.environ.get("JEJU_API_KEY"), help="인증키 (기본: 환경변수 JEJU_API_KEY)")
    ap.add_argument("--out", help="저장할 파일 이름")
    a = ap.parse_args()

    if not a.key:
        sys.exit("인증키가 없습니다. export JEJU_API_KEY=\"...\" 로 설정하거나 --key 를 쓰세요.")
    if not (len(a.race_dt) == 8 and a.race_dt.isdigit()):
        sys.exit("경주일자는 YYYYMMDD 형식이어야 합니다. 예: 20240817")

    bundle = {"bundle": 1, "race_dt": a.race_dt, "collected": time.strftime("%Y-%m-%d %H:%M")}
    errors = []

    def step(label, fn):
        print(f"· {label} ...", end=" ", flush=True)
        try:
            v = fn()
            print(f"{len(v)}건")
            return v
        except ApiError as e:
            print("실패")
            errors.append(str(e))
            return []

    bundle["sheet"] = step("출전표 (예정 경주)", lambda: fetch_all(a.key, "sheet", {"meet": MEET_JEJU}, max_pages=10))
    d = {"race_dt": a.race_dt}
    bundle["races"] = step("경주정보", lambda: fetch_all(a.key, "races", d))
    bundle["reg"] = step("출전등록", lambda: fetch_all(a.key, "reg", d, max_pages=3))
    bundle["runs"] = step("출전마", lambda: fetch_all(a.key, "runs", d, max_pages=3))
    bundle["results"] = step("경주성적 이력", lambda: fetch_all(a.key, "results", {}, max_pages=a.result_pages))
    # 구간 기록: 경주성적에 나온 경주일마다 한 번씩 호출
    dates = sorted({str(r.get("rcDate", "")).replace("/", "") for r in bundle["results"] if r.get("gbn") == "R"})
    pace = []
    for d8 in dates:
        try:
            pace.extend(fetch_all(a.key, "pace", {"meet": MEET_JEJU, "rc_date": d8}, max_pages=2))
        except ApiError as e:
            errors.append(str(e)); break
    print(f"· 구간 기록 ({len(dates)}일) ... {len(pace)}건")
    bundle["pace"] = pace
    bundle["jockeys"] = step("기수 통산성적", lambda: fetch_all(a.key, "jockeys", {"meet": MEET_JEJU}))
    bundle["trainers"] = step("조교사 통산성적", lambda: fetch_all(a.key, "trainers", {"meet": MEET_JEJU}))

    horses = []
    if not a.no_horses:
        # 경주성적에 나온 마번 + 출전마 마명으로 마필종합정보 조회
        nos = {str(r.get("hrNo")) for r in bundle["results"] if r.get("hrNo")}
        nos |= {str(r.get("hrNo")) for r in bundle["sheet"] if r.get("hrNo")}
        names = {r.get("hrnm") for r in bundle["runs"] if r.get("hrnm")}
        print(f"· 마필종합정보 (마번 {len(nos)}두, 출전마 {len(names)}두) ...", flush=True)
        seen = set()
        targets = [("hr_no", n) for n in sorted(nos)] + [("hr_name", n) for n in sorted(names)]
        for i, (k, v) in enumerate(targets, 1):
            try:
                items, _ = call(a.key, "horse", {k: v, "pageNo": 1, "numOfRows": 10})
            except ApiError as e:
                errors.append(str(e))
                if "22" in str(e):
                    break
                continue
            for h in items:
                if h.get("hrNo") not in seen:
                    seen.add(h.get("hrNo"))
                    horses.append(h)
            if i % 25 == 0:
                print(f"  {i}/{len(targets)}", flush=True)
        print(f"  완료: {len(horses)}두")
    bundle["horses"] = horses

    out = a.out or f"jeju_bundle_{a.race_dt}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False)
    print(f"\n저장: {out} ({os.path.getsize(out)/1024:.0f}KB)")
    if errors:
        print("\n확인이 필요한 오류:")
        for e in dict.fromkeys(errors):
            print("  -", e)
    print("레이스카드 페이지 아래 '파일 불러오기'로 이 파일을 열면 됩니다.")


if __name__ == "__main__":
    main()
