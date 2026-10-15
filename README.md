# 제주경마 레이스카드 (Jeju Race Card)

제주 조랑말 경주를 한국어·영어로 보여 주는 레이스카드입니다.

- 사이트: https://jokim90.github.io/jeju-racecard/
- `site/index.html` — 레이스카드 페이지. 열 때마다 같은 폴더의 `latest.json`을 자동으로 불러옵니다.
- `collector/jeju_collect.py` — 한국마사회 공공데이터 API를 모아 묶음 파일을 만드는 스크립트
- `.github/workflows/update.yml` — 매일 05:50, 금·토·일 20:50(한국시간)에 수집해서 `latest.json`을 갱신하고 사이트를 다시 배포

- `model/` — 출마표 분석 모형 (배당 미사용). 2019년부터의 제주 경주 기록으로 출전마마다 경주 전 정보 22개 항목을 계산해 승률과 '탑 4 이야기' 재료를 만듭니다.
  - `jeju_model.py` 피처 계산 · `train.py` 학습(2025~26 검증 후 전체 재학습 → `coef.json`) · `predict.py` 출마표 예측 → `latest.json`의 `model`
  - `update_history.py` 매일 새 경주성적·일일 훈련·새 마필을 `history/*_new.csv`에 붙입니다. 기본 이력(`history/*.csv.gz`)은 그대로 둡니다.
  - 검증(2024년까지 학습, 2025-01~2026-09, 1,249경주): 1순위 우승 30.7%, 상위 4두 안 우승마 72.2%. 같은 경주 인기 1위 우승 37.6%.
  - 계수 다시 학습: `pip install pandas numpy scipy && python3 model/train.py`

인증키는 저장소 Secrets의 `JEJU_API_KEY`에 있습니다. 수동 갱신은 Actions 탭 → "데이터 갱신 및 배포" → Run workflow.
