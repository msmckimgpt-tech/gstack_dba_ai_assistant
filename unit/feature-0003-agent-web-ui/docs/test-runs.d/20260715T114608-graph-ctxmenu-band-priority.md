---
run_at: 2026-07-15T11:46:08+09:00
session: graph-ctxmenu-band-priority (ai/claude/feature-0003-graph-ctxmenu-band-priority)
scope: 제품 카테고리 밴드 우클릭 band-wins — 밴드 위 스키마 클러스터 박스 우클릭도 카테고리 메뉴(우클릭 전용, 좌클릭/드래그 불변)
verdict: PASS (코드/문법/단위 회귀 + POST-DEPLOY Windows-browser 라이브 — 밴드 박스→카테고리·테이블→노드·좌클릭 펼치기 실증)
---

### Run (2026-07-15) — graph-ctxmenu-band-priority: _pickContext band-wins — **Environment: node --check(ES module) + 단위 회귀(vm) + 라이브 진단 근거**

- **라이브 진단(선행, win-browser Chrome 150, hittest fix 배포본)**: 제품-매핑 데이터소스(mysql-kr-an2-auth) 스키마그래프 "킹스레이드 - 국내 QA" 밴드 정밀 우클릭 스윕 — y=320 라인: x283-323 → 카테고리(밴드 tint 좌여백), x333-765 → 스키마(dbAuth 박스), x785 → 카테고리. **hit 경계 = 가시 박스 경계와 일치**(hittest fix 정상). 그러나 dbAuth 박스가 밴드 내부를 시각적으로 거의 채워 사용자가 "밴드"로 우클릭하는 지점이 곧 박스 → 스키마 메뉴. → hit-test 결함 아닌 **겹침 우선순위 UX**. 사용자 결정 "밴드 우선".
- **수정**: `_pickContext(mx,my)` = `_pick()` 이 combo/schema-card 반환 + 그 지점 cat-bg 피복 시 cat-bg 승격, else `_pick()`. `up()` 우클릭(button===2)만 사용. 좌클릭/드래그는 `_pick` 불변.
- **node --check**(ES module, `.mjs` 복사): `graph-renderer-pixi.js` OK.
- **단위 회귀** `tests/headless/test_pixi_adapter.js` T22 (vm 로 실제 `PixiGraphAdapter._pickContext` 을 `.call(ctx,…)` 결정적 호출; CAT 밴드 + 밴드 내 카드/테이블/combo + 헤더 + 밴드 밖 standalone 카드 합성 배치):
  - 밴드 내 스키마 카드(200,200) → **CAT:prod**(카테고리 밴드 승격).
  - 밴드 내 combo 빈배경(365,270) → **CAT:prod**(승격).
  - 밴드 내 테이블 노드(450,250) → **t1**(밴드 흡수 안 함).
  - 밴드 헤더칩(100,120) → **CATH:prod**(카테고리 그대로).
  - 밴드 고유 여백(50,450) → **CAT:prod**(카테고리).
  - 밴드 밖 standalone 카드(900,300) → **SC:s9**(스키마, 승격 안 함).
  - 결과: **ALL PASS — 68 PASS / 0 FAIL**(T21 6 + T22 6 포함).
- **좌클릭/드래그 불변 근거**: `up`/`onMove`/dblclick 경로는 `_pick`(또는 d.hit) 사용 — band-wins 는 button===2 (contextmenu) 한정. T21(=`_pick` 층서: 카드/테이블→그 요소, combo→스키마, 밴드여백→카테고리)이 좌클릭/드래그 hit 계약을 여전히 잠금.
- 회귀 표면: dispatch·메뉴 함수·노드 방출·시각 z·백엔드/RBAC/스키마 0. 밴드 내 클러스터 우클릭 스키마 메뉴(펼치기·AI분석·복사)는 좌클릭 드릴로 대체 접근(트레이드오프, 사용자 수용).
- 결과: 코드/문법/단위 회귀 PASS.

### Run (2026-07-15) — POST-DEPLOY 라이브 검증 — **Environment: Windows-browser (win-browser.py relay, 배포 6a950a20)**

- **배포 전달 확인 (PASS)**: 서빙 web-a·web-b 모두 `GIT_COMMIT=6a950a20` + baked `graph-renderer-pixi.js` 에 `_pickContext` 3회. 페이지 리로드 후 서빙 JS fetch 에 `_pickContext` 포함 확인. soak 통과.
- **band-wins 라이브 실증 (PASS)** — 제품-매핑 데이터소스 mysql-kr-an2-auth("킹스레이드 - 국내 QA") 스키마그래프의 CAT 밴드 2개(킹스레이드·미분류). 합성 우클릭+메뉴 배지 판독:
  - **밴드 위 스키마 클러스터 박스 우클릭 → "카테고리" 메뉴**: dbAuth 박스(550,318·좌상 440,295) → 카테고리(킹스레이드) / dbTest 박스(510,648) → 카테고리(미분류). ✅ **이전(hittest fix)엔 "스키마" 였음 → band-wins 로 카테고리 귀속**.
  - 밴드 헤더(490,228)·tint 여백(330,320) → "카테고리". ✅
- **보존 동작 실증 (PASS)**:
  - **좌클릭 = 클러스터 펼치기**: dbAuth 좌클릭 → "dbAuth: 테이블 로딩…"(펼침) — 우클릭 전용 band-wins, 좌클릭 어포던스 보존. ✅
  - **펼친 클러스터 개별 테이블 노드 우클릭 → 그 테이블 메뉴**(밴드 흡수 안 함): (400,330) DeviceId·(680,330) AccountLoginMethodInfo → "테이블". ✅ 테이블 사이 빈 영역(550,330·500,430) → 카테고리(band-wins).
- **판정: PASS** — 밴드 영역(클러스터 박스 포함) 우클릭 → 카테고리, 개별 테이블 노드 → 그 노드, 좌클릭 펼치기 정상. 사용자 결정("밴드 우선 — 박스 위도 카테고리") 라이브 충족. 증거 스크린샷 `scratchpad/evidence-bandwins-box-category.png`(dbAuth 박스 우클릭 → "카테고리" 메뉴). healthz 200.
- 회귀 0: 좌클릭·헤더·테이블 노드 정상 관측.
