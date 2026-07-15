---
run_at: 2026-07-15T10:29:00+09:00
session: graph-ctxmenu-hittest (ai/claude/feature-0003-graph-ctxmenu-hittest)
scope: 그래프 뷰 우클릭 메뉴 오라우팅(스키마 클러스터↔제품 카테고리 밴드 뒤바뀜) — _pick hit-test 층서 수정(구체요소 > combo > cat-bg)
verdict: PASS (코드/문법/단위 회귀) · DEFERRED (Windows-browser 라이브 — 배포 후)
---

### Run (2026-07-15) — graph-ctxmenu-hittest: _pick 3-tier 층서 — **Environment: node --check(ES module) + 단위 회귀(vm) + dispatch 정합 trace**

- **결함 재현(진단)**: `PixiGraphAdapter._pick()` 이 `hitTest(built.nodes)` 로 어떤 node 든 먼저 반환 → CAT 밴드 배경(node, `data.kind:"cat-bg"`, z=`_METZ.CAT_BG`=-1, size=멤버 클러스터 전체 bbox+패딩)이 스키마 클러스터 빈 배경(combo, z=0, 폴백 대상) 우클릭을 가로채 '카테고리 메뉴'로 오라우팅. 반대로 밴드 위 카드/클러스터(z=4)가 CAT 를 눌러 '스키마 메뉴'로 샘. 헤더 CATH(z=5)만 정상.
- **수정**: `_pick` 3-tier — ① 실 요소(cat-bg 제외) → ② combo(스키마 클러스터) → ③ cat-bg. `hitTest` 에 filter 인자 + `_isCatBg` 헬퍼.
- **node --check**(ES module, `.mjs` 복사): `graph-renderer-pixi.js` OK.
- **단위 회귀** `tests/headless/test_pixi_adapter.js` T21 (vm 로 실제 `PixiGraphAdapter._pick` 을 `.call(ctx,…)` 결정적 호출; CAT 밴드가 SC 카드 + 펼친 클러스터 combo(s2)를 덮는 합성 배치):
  - (witness) 수정 전 결함: 필터 없는 `hitTest(365,270)` = combo 영역인데 `CAT:prod` node 반환 → 오라우팅 근원 확인.
  - 스키마 카드(200,200) → `SC:s1`(카테고리 아님) · 클러스터 멤버 테이블(450,250) → `t1`.
  - **스키마 클러스터 빈배경(365,270) → combo `s2`(`__combo`) = 스키마 메뉴** — CAT 가로채기 제거(핵심 fix).
  - **카테고리 밴드 고유 여백(50,130) → `CAT:prod` = 카테고리 메뉴**.
  - 밴드 밖(2000,2000) → null(canvas).
  - 결과: **ALL PASS — 62 PASS / 0 FAIL**(신규 6 포함).
- **dispatch 정합 trace**: graph-core `node:contextmenu`(L2133~) — `SC:`/`XS:`/`GB:GH:GX:` → `_metaGraphCtxForSchema`(스키마 메뉴), `CAT:/CATH:/CATX:` → `_metaGraphCtxForCategory`(카테고리 메뉴), combo:contextmenu → `_metaGraphCtxForCombo`(클러스터 메뉴). 즉 hit-test 가 올바른 노드/combo 를 집으면 메뉴는 정확. 본 수정은 hit-test 층서만 교정.
- 회귀 표면: 좌클릭·드래그·엣지/canvas 메뉴·노드 방출·시각 z 무변경. 백엔드/RBAC/스키마 0.
- 결과: 코드/문법/단위 회귀 PASS.

### Run (2026-07-15) — POST-DEPLOY 라이브 시각검증 — **Environment: Windows-browser (배포 후 라이브로 이연)**

- **미수행 사유(§15.4.1 baked 자산)**: 그래프 static JS 는 이미지 baked — 배포(web 재빌드/재시작) 후에만 라이브 반영. 배포 전 headless 는 실 반영 검증 불가.
- **배포 후 계획(PB-0008, visual_verification_scope: always)**: web 재배포 후 win-browser relay(또는 Playwright MCP)로 **제품 카테고리 밴드가 렌더되는 스키마 scope**(제품-매핑 데이터소스) 진입 →
  - (a) **스키마 클러스터(빈 배경) 우클릭 = 클러스터/스키마 메뉴**('클러스터 상세'/'DB 전체 AI 능동 분석' 등), 카테고리 메뉴 미노출.
  - (b) **카테고리 밴드 고유 영역(헤더 🗂 칩·밴드 여백) 우클릭 = 카테고리 메뉴**('카테고리 상세'/'접기·펼치기 (밴드)'/'카테고리명 복사'), 클러스터 메뉴 미노출.
  - (c) 클러스터 멤버 카드/테이블 우클릭 = 해당 노드 메뉴.
  - (d) 회귀 0: 좌클릭·드래그(밴드 리지드 이동 via 헤더)·엣지/canvas 메뉴 종전대로.
- 결과: 정적/문법/단위 회귀 PASS · 라이브 시각검증은 배포 후 POST-DEPLOY Run 으로 수행.
