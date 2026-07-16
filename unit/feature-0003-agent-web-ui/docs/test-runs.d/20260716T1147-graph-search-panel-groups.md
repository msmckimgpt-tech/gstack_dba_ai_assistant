---
run_at: 2026-07-16T11:47:05+09:00
session: ai/claude/feature-0003-graph-search-panel-groups
scope: 검색 결과 패널 3개선 — 2단 접기(스키마 클러스터→컨텐츠 카테고리)·검색 이력(뒤로/앞으로)·설명문 간결화 (20260716T1147-graph-search-panel-groups)
verdict: 정적 PASS · POST-DEPLOY PB-0008 라이브 DEFERRED (Environment: Windows-browser)
---

### Run 1 — 문법/균형 (Environment: node --check + CSS balance)
- `graph-ctxmenu.js` ESM `node --input-type=module --check` PASS(import·호이스트 정상).
- `graph.css` brace 245:245 · comment `/*`:`*/` 76:76 밸런스.

### Run 2 — 정적·로직 + §18.8 적대 리뷰 (Environment: 코드 리뷰)
- **item1 2단 접기**: `_metaSchemaComboOf`(스키마)→`cluster_label`(카테고리, 없으면 미분류) 2단 그룹, 정렬(스키마 매칭수↓·카테고리 수↓ 미분류맨끝·노드 유사도↓), nested `.amgr-srch-sc`/`.amgr-srch-cat` + `is-collapsed` CSS, 헤딩 role/caret/aria/Enter·Space 토글, `_searchGroupCollapsed` 유지 + 렌더마다 currentIds prune, 모두 접기/펼치기.
- **item2 검색 이력**: `_metaGraphRecordSearch`(top=search in-place+forward절단 / 비-search push+캐시) · `_metaGraphRestoreSearch`(재fetch 없이 input+mode+searchMatchNodes 복원) · `_metaGraphHistoryGo` search 분기(focus skip). finding#5 해소.
- **item3 간결화**: 상태줄 `'q' — N건`(+상한/숨김 힌트), 부제 삭제, 행 title=fqn.
- **§18.8 적대 리뷰** REV-20260716T114705 — CONFIRMED 2(C1 forward절단·C2 stale collapsed prune) + PLAUSIBLE 2(P1 상태복원·P2 focus 가드) 흡수, P3 수용. XSS/구분자/재검색루프/회귀 CLEAN. 재검증 node --check PASS.
- 결과 **PASS(정적)**.

### Run 3 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — DEFERRED (배포 후 실행)
- PB-0008 실 Windows Chrome relay(win-browser.py)로 배포본에서 검증 예정:
  1. 검색(예: 플루토스) → 상세 패널에 **스키마 클러스터 → 컨텐츠 카테고리** 2단 그룹·정렬 렌더.
  2. 스키마/카테고리 헤딩 클릭 → 접힘/펼침(caret·body 숨김), "모두 접기/펼치기" 동작.
  3. 결과 행 클릭 → 노드 상세 → [뒤로] → 검색 결과 복원(입력값·리스트) → [앞으로] → 노드 상세.
  4. 검색 상태줄·행 툴팁 간결.
  5. pageerror 0.
- visual_verification_scope: always — POST-DEPLOY Run 완료 시 PASS 로 갱신.
