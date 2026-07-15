---
run_at: 2026-07-15T10:29:00+09:00
session: graph-ctxmenu-hittest (ai/claude/feature-0003-graph-ctxmenu-hittest)
scope: 그래프 뷰 우클릭 메뉴 오라우팅(스키마 클러스터↔제품 카테고리 밴드 뒤바뀜) — _pick hit-test 층서 수정(구체요소 > combo > cat-bg)
verdict: PASS (코드/문법/단위 회귀 + POST-DEPLOY Windows-browser 라이브 — 3대상 우클릭 실증)
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

### Run (2026-07-15) — POST-DEPLOY 라이브 검증 — **Environment: Windows-browser (win-browser.py relay, 배포 6ec5da4b→8098aee1)**

- **배포 전달 확인 (PASS)**: 서빙 컨테이너 web-a·web-b 모두 baked `graph-renderer-pixi.js` 에 fix 반영 실측 — `_isCatBg` 3회(정의+tier 필터 2), `if (filter && !filter(n)) continue`, tier3 주석. 배포 직후 `GIT_COMMIT=6ec5da4b`, 이후 병렬 머지로 `8098aee1` 재배포(fix 포함, `_isCatBg` 잔존 재확인). soak 통과.
- **라이브 도달성 (PASS)**: 실 Windows Chrome(relay, Chrome 150) `https://localhost/admin` 그래프 뷰 → 데이터소스 노드(mysql-kr-an2-auth, 제품 "킹스레이드 - 국내 QA") 좌클릭 드릴 → **스키마 그래프에 제품 카테고리 밴드 2개 렌더**: "🚚 킹스레이드 - 국내 QA"(파랑, 멤버 클러스터 dbAuth) · "🚚 미분류 · 1 DB · 3 테이블"(초록, 멤버 클러스터 dbTest). = 사용자 보고 시나리오(밴드+클러스터 공존) 재현.
- **우클릭 3대상 라이브 실증 (PASS — 합성 우클릭 `pointerdown/up{button:2}`+`contextmenu`, 메뉴 `.admin-meta-graph-ctxmenu` 배지 판독)**:
  - **스키마 클러스터** dbAuth(550,318)·dbTest(510,648) 우클릭 → 배지 **"스키마"** (dbAuth·테이블 10 / dbTest·테이블 3 + 펼치기·클러스터 상세·DB 전체 AI 능동 분석·스키마명 복사). ✅ **이전 결함("스키마 클러스터 우클릭 → 카테고리 메뉴") 해소** — 배지 카테고리 미노출.
  - **카테고리 밴드 헤더** 킹스레이드(490,228)·미분류(490,559) 우클릭 → 배지 **"카테고리"** (카테고리 상세·접기(밴드)·카테고리명 복사). ✅
  - **카테고리 밴드 tint 고유 여백** 3지점(350,255 / 600,255 / 320,320, dbAuth 클러스터 밖) 우클릭 → 배지 **"카테고리"** (tier3). ✅ **이전 결함("제품 카테고리 우클릭 → 스키마 메뉴") 해소**.
  - 빈 캔버스(밴드 밖) 우클릭 → canvas 메뉴('전체 맞춤'/'그래프 초기화'/'데이터소스 진입 뷰'). 정상.
- **판정: PASS** — 세 사용자 증상(스키마↔카테고리 뒤바뀜) 라이브에서 전부 해소. "보이는 대로 클릭"(WYSIWYG): 밴드 위 클러스터 → 스키마 메뉴 / 밴드 고유 영역·헤더 → 카테고리 메뉴. 증거 스크린샷 `scratchpad/evidence-cluster-schema-menu.png`(CAT 밴드 "킹스레이드 - 국내 QA" 안의 dbAuth 클러스터 우클릭 → "스키마" 메뉴).
- 회귀 0: 좌클릭(드릴/상세)·엣지/canvas 메뉴 정상 관측. healthz 200.
