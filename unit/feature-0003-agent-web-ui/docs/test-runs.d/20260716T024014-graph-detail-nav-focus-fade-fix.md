---
run_at: 2026-07-16T11:40:14+0900
session: ai/claude/feature-0016-graph-detail-nav-focus-fade-fix
scope: unit/feature-0003-agent-web-ui/src/static/graph
verdict: PASS
---

### Run (2026-07-16) — graph-detail-nav-focus-fade-fix: [뒤로/앞으로] 클릭 후 바 페이드 미적용 버그 수정 — **Environment: Windows-browser**

- 방법: PB-0008 — `bin/win-browser.py`(실 Windows Chrome 150.0.7871.115, CDP relay) + `docker cp` 로 web-a/web-b 의 `graph.css` 교체 + `<link>` 캐시버스터. nav 강제 표시 + 더미 콘텐츠. 실 마우스 클릭은 win-browser `click`(실 포인터), 키보드 modality 는 `type`(실 키 이벤트)로 유발. `matches(:focus-within|:has(:focus-visible)|:focus-visible|:hover)` + `getComputedStyle(opacity)` 로 상태 계측.
- **재현(수정 전, 현 배포본 `:focus-within`)**: 실 마우스로 `#metaGraphDetailBack` 클릭 → `activeEl=metaGraphDetailBack`·`nav:focus-within=true`·`nav:has(:focus-visible)=false`·`back:focus-visible=false`. → 마우스 클릭 포커스를 `:focus-within` 이 매칭해 opacity 1 고착(포인터가 떠나도 투명 미적용). 사용자 리포트 재현.
- **수정 후 확인(PASS)**:
  - **버그 해소(핵심)**: 실 마우스로 검색창 클릭(포인터를 바 밖으로) + `#metaGraphDetailBack` 포커스 유지 상태 → `nav:hover=false`·`back:focus-visible=false`·`nav:has(:focus-visible)=false` → **`opacity=0.3`**(페이드). 기존 `:focus-within` 이면 1.0 고착이던 시나리오가 정상 페이드로 해소.
  - **키보드 접근성 유지**: `type` 로 키보드 modality 활성 후 버튼 포커스 → `back:focus-visible=true`·`nav:has(:focus-visible)=true` → opacity 0.3→1 transition 관측 후 **`opacity=1`**(불투명 유지). 키보드 사용자 회귀 없음.
  - **기존 정상 동작 보존**: 실 마우스로 버튼 클릭(포인터 버튼 위) → `nav:hover=true` → `opacity=1`(hover 복원 유지).
  - CSS: brace balance OK, `:has(:focus-visible)` 존재, `.admin-meta-graph-detailnav:focus-within` 잔존 0.
- 결과: **PASS** — 마우스 클릭 포커스는 더 이상 바를 고착시키지 않고 포인터가 떠나면 정상 페이드(버그 해소), 키보드 포커스는 불투명 유지(접근성). `:has` 미지원 브라우저는 hover 규칙 분리로 코어 페이드 보존.
