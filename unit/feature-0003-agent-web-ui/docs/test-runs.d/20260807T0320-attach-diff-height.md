---
run_at: 2026-08-07T03:20:00+09:00
session: ai/claude-corp/feature-0003-attach-diff-height
scope: unit/feature-0003-agent-web-ui/src/static/css/chat.css (모달 높이 1선언)
verdict: PASS (headless) / PENDING (Windows-browser — 배포 후)
---

### Run (2026-08-07) — attach-diff-height: 모달 높이를 고정에서 상한으로

#### 1. 적발 — **Environment: Windows-browser** (선행 cycle 배포본 `b23df012`)

선행 cycle 의 PB-0008 자동 44축은 전부 PASS 했다. 그런데 캡처를 판독하니 짧은 diff 에서
표 아래에 큰 빈 영역이 남았다 — **내용 y≈495 종료 / 패널 940**. 원인은 결함이 아니라
**내가 세운 계약**(`height: 94vh` 고정)이었고, 그 고정을 선행 T9("높이 ≥ 88vh")가 요구사항으로
굳혀 자동 검증이 정상으로 인증했다.

#### 2. 수정 후 — **Environment: WSL-headless (chromium)**

| # | 항목 | 결과 |
|---|---|---|
| T9 | 모달 폭이 뷰포트의 95% 이상 | PASS `1416 / 1440` |
| T9b | **짧은 diff 는 높이 상한 미만**(빈 영역 없음) | PASS `panelH=244 / 94vh=846` |
| T9c | **긴 diff(120행)는 상한에 닿는다** | PASS `panelH=846 / vh=900` |
| T9d | 넘치는 내용은 **표 컨테이너**가 스크롤(페이지 스크롤 아님) | PASS `scroller=True docOverflowY=False` |

전체 **25/25 PASS**(선행 22 + 신설 3). 전수 mjs 44 suite OK. pytest 무영향(CSS 단독).

#### 3. **Environment: Windows-browser** — 배포 후 재검증 잔여

짧은 diff(빈 영역 없음)와 긴 diff(상한 도달 + 표 스크롤) 두 케이스를 실 화면에서 확인한다.
