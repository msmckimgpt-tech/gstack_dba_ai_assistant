---
run_at: 2026-07-16T10:03:49+0900
session: ai/claude/feature-0016-graph-detail-nav-hover-fade
scope: unit/feature-0003-agent-web-ui/src/static/graph
verdict: PASS
---

### Run (2026-07-16) — graph-detail-nav-hover-fade: 상세 패널 [뒤로/앞으로] 바 hover 페이드 — **Environment: Windows-browser**

- 방법: PB-0008 — `bin/win-browser.py`(실 Windows Chrome 150.0.7871.115, CDP relay) + `docker cp` 로 web-a/web-b 의 `graph.css` 를 본 변경 서빙 사본으로 교체(hover-fade/`:focus-within`/`prefers-reduced-motion` 규칙 존재 확인) + `<link graph.css>` 캐시버스터 강제 재적용 → 그래프 뷰. nav 강제 표시 + 더미 콘텐츠 주입. hover 는 win-browser `click`(실 포인터 이동)으로 유발, 전환(0.18s) 완료 대기 후 측정.
- 확인(PASS):
  - **기본(비-hover) 반투명**: 포인터를 바에서 먼 검색창으로 이동한 상태에서 `getComputedStyle(nav).opacity` = **0.3**, `transition` = **opacity 0.18s** — hover 아닐 때 부드럽게 흐림.
  - **hover 복원**: 포인터를 바(`#metaGraphDetailNavLabel`)로 이동 → `opacity` = **1**, `nav.matches(":hover")` = **true** — 마우스 올리면 완전 불투명.
  - **키보드 접근성(focus-within)**: 포인터를 멀리 둔 채 `#metaGraphDetailBack.focus()` → (전환 완료 후) `opacity` = **1**, `:focus-within` = true, `:hover` = false — 키보드 포커스에도 복원.
  - **전환 부드러움**: `.focus()` 직후 동기 측정 시 0.3(전환 시작 시점)→ 지연 후 1 로 관측, transition 이 실제 애니메이트됨을 확증.
  - 스크린샷: scratchpad fade-idle.png(바 흐림 — 아래 콘텐츠 진함과 대비) / fade-hover.png(바 실선 불투명). 두 컷 대비로 hover 페이드 육안 확인.
- 결과: **PASS** — 마우스 hover 가 아닐 땐 바가 부드럽게 반투명(0.3), hover/키보드 포커스 시 불투명(1) 복원. 접근성 가드(focus-within·reduced-motion) 포함.
