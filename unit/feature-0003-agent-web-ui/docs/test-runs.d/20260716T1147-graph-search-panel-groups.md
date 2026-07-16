---
run_at: 2026-07-16T11:47:05+09:00
session: ai/claude/feature-0003-graph-search-panel-groups
scope: 검색 결과 패널 3개선 — 2단 접기(스키마 클러스터→컨텐츠 카테고리)·검색 이력(뒤로/앞으로)·설명문 간결화 (20260716T1147-graph-search-panel-groups)
verdict: 정적 PASS · POST-DEPLOY PB-0008 라이브 PASS (Environment: Windows-browser, main 89c1e7b0)
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

### Run 3 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — **PASS**
- 배포: PR #846 → main 89c1e7b0 + `sudo -E bin/deploy-web.sh` 무중단 롤링(web-a/web-b·워커·soak 통과). 서빙 자산(web-a): `graph-ctxmenu.js` `_metaGraphRecordSearch`/`amgr-srch-sc` grep=4 · `graph.css` `amgr-srch-subhead` grep=2.
- 방법: win-browser.py 실 Windows Chrome(Chrome/150) relay, https://localhost/admin(로그인) → 그래프 뷰(공용/common) → "플루토스" 검색.
- 결과 **PASS**:
  1. **item1 2단 접기**: "🔎 검색 결과 28건" + "모두 접기". **8 스키마 클러스터 그룹**(예 "🗂 cc_data_test" 6) → 각 하위 **컨텐츠 카테고리 그룹**(예 "🏷 플루토스 순위" 6, 들여쓰기) → 노드 행(더 들여쓰기, 유사도 63%·카테고리 배지). 스키마 헤딩 클릭 → 접힘(caret ▾→▸·body display:none·aria-expanded=false). "모두 접기"→8/8 접힘·0행 가시·라벨 "모두 펼치기", "모두 펼치기"→28행 복원·라벨 flip(C2 라벨 정합 실증).
  2. **item2 검색 이력**: 결과 행(sp_GetCharacterRanking) 클릭 → 노드 상세(마커 제거·ROUTINE 상세) + 뒤로/앞으로 nav "2/2". **[뒤로]** → 검색 결과 복원(28건·8그룹·입력값 "플루토스" 복원·nav "1/2", 재fetch 없음). **[앞으로]** → 노드 상세 재이동(nav "2/2").
  3. **item3 간결**: 검색 결과 패널 verbose 부제 부재(`.admin-meta-detail-note` 없음), 헤더 직후 바로 그룹. 상태줄 간결.
  4. **pageerror 0** · `document.readyState=complete`.
  5. 스크린샷 육안(search-panel-groups.png): 우측 패널 2단 들여쓰기 그룹(📁 스키마 / 🏷 카테고리 / 노드 행) + 상단 "← 뒤로 · 앞으로 → · 1/2" nav 공존.
- visual_verification_scope: always — 충족. (evidence: /tmp/win-browser-shots/search-panel-groups.png — PNG repo 미커밋 관례, 판정은 본 Run 실측.)
