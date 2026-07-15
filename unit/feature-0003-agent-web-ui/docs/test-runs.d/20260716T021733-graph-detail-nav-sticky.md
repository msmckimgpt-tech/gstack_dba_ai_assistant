---
run_at: 2026-07-16T02:17:33+0900
session: ai/claude/feature-0016-graph-detail-nav-sticky
scope: unit/feature-0003-agent-web-ui/src/static/graph
verdict: PASS
---

### Run (2026-07-16) — graph-detail-nav-sticky: 상세 패널 [뒤로/앞으로] 바 상단 고정 — **Environment: Windows-browser**

- 방법: PB-0008 — `bin/win-browser.py`(실 Windows Chrome 150.0.7871.115, CDP relay) + `docker cp` 로 web-a/web-b 의 `/app/web/static/graph/graph.css` 를 본 변경 서빙 사본으로 교체(sticky 규칙 존재 확인) + `<link graph.css>` 캐시버스터로 강제 재적용 → https://localhost/admin → 그래프 뷰. nav 바는 실 이력이 있어야 표시되므로, `#metadataGraphDetailNav` 를 강제 표시 + 40줄 더미 콘텐츠를 `#metadataGraphDetailBody` 에 주입해 스크롤을 유발하고 CSS sticky 동작을 직접 측정(그래프 데이터 무관 CSS-레벨 검증).
- 확인(PASS):
  - **상단 고정**: `getComputedStyle` = `position:sticky; top:0px; z-index:5`. 바 `getBoundingClientRect().top` = **180px 로 스크롤 전(scrollTop 0)·후(scrollTop 500) 불변** — 콘텐츠만 그 아래로 스크롤되고 바는 상단에 고정.
  - **바 위 콘텐츠 누출 없음**: 스크롤 상태에서 body 자식 중 바 상단(navTop)보다 위에서 보이는 요소를 전수 검사 → **`contentAboveBar: []`**(0건). aside 상단 padding 제거로 스크롤포트 최상단=바 위치가 되어 위로 비치는 틈 제거. (초기 음수마진-only 버전은 바 위 14px 에 콘텐츠 조각이 관측돼 수정.)
  - **불투명 배경**: `backgroundColor = rgb(255,255,255)` — 아래로 스크롤되는 콘텐츠가 바를 통해 비치지 않음. 하단 `border-bottom` 구분선으로 콘텐츠와 시각 분리.
  - 스크린샷: scratchpad sticky-scrolled.png(결함 재현) / sticky-precise.png(수정 확인 — 바 최상단 고정, 더미 라인 18~35 가 그 아래로 스크롤).
- 미수행(후속): 실제 방문 이력(노드 상세 2개+)을 통한 in-situ 확인은 그래프 투영 데이터 확보 시(TN.6). 본 Run 은 sticky CSS 자체를 실 브라우저 렌더에서 직접 측정·확증.
- 결과: **PASS** — 바가 스크롤 위치와 무관하게 상세 패널 상단에 고정되고 버튼이 항상 사용 가능, 바 위 콘텐츠 누출 없음.
