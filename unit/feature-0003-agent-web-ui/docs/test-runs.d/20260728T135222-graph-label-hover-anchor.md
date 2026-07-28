---
run_at: 2026-07-28T13:52:22+09:00
session: ai/claude/feature-0003-graph-label-hover-anchor
scope: 그래프 뷰 hover 확장 기준점 — 중앙 대칭 → **좌변 고정 + 우측 확장**(사용자 정정)
verdict: PASS (PRE-COMMIT 단위·정적 + POST-DEPLOY PB-0008 라이브)
---

### Run — 앵커 기하 순수 로직 (Environment: node vm)
- `node --check --input-type=module` PASS · `test_pixi_adapter.js` **190 PASS / 0 FAIL**(직전 186 + 앵커 4).
- 신규/갱신 계약:
  - `hoverExpandGeom` 이 `left = s.x - w0/2`(원 칩 좌변) 를 반환 — 확장 앵커.
  - `hoverCardCenterX(g, w) = g.left + w/2` — 폭이 커져도 **좌변 불변**(`center - w/2 === g.left` 단정),
    t=0 중심 = 원 칩 중심(픽셀 동일 시작), `left` 부재 구 geom 은 중앙 고정 폴백.
  - `hoverTextOffsetX(g, w, textLeft)` — 라벨의 **world 좌측을 절대 고정**(카드 중심 이동분 상쇄).
    t=0·t=1 모두 `centerX + offset === textLeft` 단정 → 확장 내내 앞글자 이동 0.
  - 루틴 칩(labelMaxWidth 176 > 칩 폭 150) 회귀 케이스 포함 — `left + pad/2 !== textLeft` 대조 단정으로
    "pad 추정 금지, 실렌더 폭 역산 필수" 를 잠금.
- 그래프 headless 전 스위트 회귀: 번들계열 **449 PASS / 0 FAIL** + pixi 190 = **639 PASS / 0 FAIL**.

### Run — §18.8 적대 검증 (Environment: CLI, codex review --uncommitted)
- 1차: **P2 1건 적발** — 좌측 정렬 기준을 `카드 좌변 + pad/2` 로 잡아, 라벨이 칩보다 넓은 루틴 칩에서
  hover 순간 라벨이 ~17px 튄다(주장한 "t=0 픽셀 동일" 위반). → 실렌더 폭 역산(`hoverTextOffsetX`)으로 수정.
- 2차: "no discrete regressions found" 수렴.

### Run — Environment: Windows-browser (PB-0008) — **POST-DEPLOY PASS**
- 미수행 사유(PRE-COMMIT, 기록 보존): WebGL 캔버스 rAF 애니는 headless 픽셀 실측 정본이 아니고, 정적 자산은
  web 이미지 baked 라 배포 전 라이브 화면에 없다.
- **배포**: PR #1000 → main `9158551b` → `make deploy-web-only` 무중단 롤링(web-a·web-b `git_commit=9158551b`,
  asset stamp `6fd0965e5b49` 재주입, 90s soak 통과). 서빙 자산에 `hoverCardCenterX`·`hoverTextOffsetX` 존재 확인.
- **방법**: `bin/win-browser.py` relay(실 Windows Chrome 150) → 그래프 뷰 → `mysql-local`.
  대상 = 잘려 있던 스키마 카드 `agent_attachment_5f6353c47…`(캔버스 x 250..367, y 388..413).

| # | 확인 항목 | 결과 |
|---|---|---|
| ① | **좌변 고정** | PASS — 확장 전/후 카드 좌측 모서리 픽셀 동일. 애니 전 구간(15 프레임, t=24~704ms) **좌측 x = 249 단일값** — 앞글자 1px 도 이동 없음 |
| ② | **우측 모서리만 확장** | PASS — 전/후 유의 픽셀 diff 가 **캔버스 x 354~449(=원 카드 우측 끝 이후)** 에만 발생. 좌측 절반은 diff 0 |
| ③ | 전체 명칭 노출 | PASS — `agent_attachment_5f6353c47…` → **`agent_attachment_5f6353c47c315cff1945d6b92f941c09`** |
| ④ | z-order | PASS — 확장분이 **우측 이웃 카드 위**에 그려짐(이웃이 `ent_6b2129…` 로 가려짐), 이웃 카드 자체 위치는 불변 |
| ⑤ | 이탈 원복 | PASS — 커서 이탈 후 hover 이전과 **픽셀 동치**(유의 diff `None`) |
| ⑥ | pageerror | PASS — 0건 |

- 증적: `evidence/pb0008-graph-hover-anchor-{before,after}-20260728.png` · 원본·프레임 로그
  `artifacts/feature-0003-graph-label-hover-anchor/`.
