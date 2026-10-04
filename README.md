# 제주경마 레이스카드 (Jeju Race Card)

제주 조랑말 경주를 한국어·영어로 보여 주는 레이스카드입니다.

- 사이트: https://jokim90.github.io/jeju-racecard/
- `site/index.html` — 레이스카드 페이지. 열 때마다 같은 폴더의 `latest.json`을 자동으로 불러옵니다.
- `collector/jeju_collect.py` — 한국마사회 공공데이터 API를 모아 묶음 파일을 만드는 스크립트
- `.github/workflows/update.yml` — 매일 05:50, 금·토·일 20:50(한국시간)에 수집해서 `latest.json`을 갱신하고 사이트를 다시 배포

인증키는 저장소 Secrets의 `JEJU_API_KEY`에 있습니다. 수동 갱신은 Actions 탭 → "데이터 갱신 및 배포" → Run workflow.
