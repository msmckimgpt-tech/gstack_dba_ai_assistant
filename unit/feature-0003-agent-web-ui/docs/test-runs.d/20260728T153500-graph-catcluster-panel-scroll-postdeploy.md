---
run_at: 2026-07-28T15:35:00+09:00
session: ai/claude/feature-0016-catcluster-scroll-postverify (postdeploy)
scope: POST-DEPLOY live — graph-catcluster-scroll (PR #1008 / main 4a0174e5)
verdict: PASS
---

# Run (2026-07-28) — graph-catcluster-scroll POST-DEPLOY 라이브 실증 + PB-0008 — Environment: Windows-browser

pre-commit 검증은 격리 컨테이너(§13.2.9)에서 수행했으므로, **main 기반 이미지가 실제로 서빙되는
사용자 경로**에서 다시 확인한다(§16.3 deploy-backed 완료 기준 — 머지 ≠ 배포 완료).

- 배포: PR **#1008** 머지(main **4a0174e5**) → `make deploy-web` 무중단 전체 롤아웃 —
  web-a/web-b 롤링(`mysql-ai-web:4a0174e5`) · post-cutover soak 90s **통과** ·
  insight-worker/ask-worker 재빌드(`GIT_COMMIT=4a0174e5`) · Caddyfile 무변경(blip 0) · gateway 드리프트 없음.
- **서빙 baked 확인**(Caddy 경유 라이브): `https://localhost/static/graph/graph-ctxmenu.js` 에
  `_metaGraphFocusPanelGroup` **2건**, `graph-core.js` 에 `gk.slice(sep + 1)` **1건**,
  `graph.css` 에 `amgrCtGroupFocus` **2건**. 서빙 HTML entry = `admin.js?v=28b8c65898a7`(신 스탬프).
- Runner: AI (`bin/win-browser.py`) · Bridge: `relay` @ `http://172.26.144.1:9223` · Chrome/150.0.7871.115
- 대상: `https://localhost/admin` → 그래프 뷰 → 데이터소스 `mssql-web-qa` → `masangsoftweb` 펼침
  (컨텐츠 카테고리 **93** · 패널 그룹 **93** · 행 **595** · `scrollHeight` **17,277px** · 시작 `scrollTop` 0).

| # | 시나리오 | 결과 |
|---|---|---|
| 1 | 캔버스 `문피아 계정 이전`(be:2) 헤더 좌클릭 | 패널 `scrollTop` 0 → **1,673 정착**, 해당 헤딩 뷰포트 **+6px**(이력 바 숨김 → navH 0), 첫 가시 그룹 = `be:2 문피아 계정 이전` **PASS** |
| 2 | 도착 강조 | 클릭 1.1s 후 `.amgr-ct-group.is-focus` **1건**(라벨 `문피아 계정 이전`) **PASS** |
| 3 | 상태줄 | `클러스터: masangsoftweb · 테이블 295개 · 함수·프로시저 300개 · 목록을 '문피아 계정 이전' 위치로 이동` **PASS** |
| 4 | 콘솔 | `window.onerror` **0건** |

- Evidence: `artifacts/shared/win-browser-shots-catcluster-scroll/`
  `06_postdeploy_before.png`(클릭 전) · `07_postdeploy_highlight.png`(**도착 강조 순간** — 패널 최상단
  `문피아 계정 이전 4` 파란 강조 + 캔버스의 동명 그룹 박스 동시 가시 + 상태줄 이동 안내) ·
  `08_postdeploy_settled.png`(정착).
- 정리: `win-browser.py down`(relay 포함) 완료. 라이브 자산·컨테이너 주입 **없음**(순수 배포본 관측이라 원복 대상 없음).
- 사전(격리 컨테이너) Run 과의 차이: 이력 바가 숨김 상태라 상단 여백이 `+53px`(navH 47 + 6) 대신
  **`+6px`** 로 관측됐다 — 보정식이 nav 높이를 실측하므로 **두 경우 모두 설계대로**다(AC-CPS-1).
