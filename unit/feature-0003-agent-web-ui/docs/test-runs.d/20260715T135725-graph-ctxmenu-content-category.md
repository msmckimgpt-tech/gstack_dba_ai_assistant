---
run_at: 2026-07-15T13:57:25+09:00
session: graph-ctxmenu-content-category (ai/claude/feature-0003-graph-ctxmenu-content-category)
scope: 그래프 우클릭 3대상 정합 — 컨텐츠 카테고리(sim-group GB/GH/GX) 전용 메뉴 신설 + band-wins(밴드 위 스키마 클러스터→카테고리 승격) 철회
verdict: PASS (코드/문법/단위 회귀) · POST-DEPLOY PB-0008 라이브 잔여
---

### Run (2026-07-15) — graph-ctxmenu-content-category: band-wins 철회 + 컨텐츠 카테고리 메뉴 — **Environment: node --check(ES module) + 단위 회귀(vm)**

- **배경(사용자 정정, band-wins 배포 후)**: "'제품 카테고리 밴드'를 '각 내부 노드를 컨텐츠 단위로 묶은 클러스터(=컨텐츠 카테고리)'로 착각하여 잘못 요청했다." → band-priority(TASK-20260715T114608, `_pickContext`)의 전제 무효. 사용자 재정의: 그래프 우클릭은 3층 대상 각자 자기 메뉴.
  - ① 제품 카테고리 밴드(cat-bg, CAT:/CATH:/CATX:) = 카테고리 메뉴 (기존 유지)
  - ② 스키마 클러스터(combo/SC:/XS:) = 스키마 메뉴 (기존 유지 — band-wins 로 밴드 위에선 카테고리로 새던 것 복원)
  - ③ 컨텐츠 카테고리(sim-group GB:/GH:/GX:, 스키마 내부 유사 테이블 그룹 = graph-simgroups "컨텐츠 신호") = **신설 전용 메뉴**
- **수정**:
  - band-wins 철회 — `PixiGraphAdapter._pickContext()` 제거, `up()` button===2 는 `d.hit`(=`_pick`, WYSIWYG) 사용. `_pick` 3-tier(hittest fix)는 불변.
  - `_metaGraphCtxForContentCategory(gk,x,y)` 신설 — 헤더 배지 '컨텐츠 카테고리'(#8a3f7a)+label·테이블수 / 소속 스키마 상세 / 접기·펼치기 묶음(`groupCollapsed` 토글+`_metaG6Apply`) / 묶음명 복사.
  - `graph-core.js` GB/GH/GX dispatch → `_metaGraphCtxForContentCategory(gk)`; `_metaGraph.groupInfo`(groupKey→{label,n,schema}) 신설·emission 전량 적재.
- **node --check**(ES module, `.mjs` 복사): `graph-renderer-pixi.js`·`graph-ctxmenu.js`·`graph-core.js`·`graph-state.js` 전부 OK.
- **단위 회귀** `tests/headless/test_pixi_adapter.js` T22 (band-wins → 컨텐츠 카테고리 회귀로 교체; vm 로 실제 `PixiGraphAdapter._pick` 을 `.call(ctx,…)` 결정적 호출; CAT 밴드 + 밴드 내 sim-group GB(z=1)/GH(z=5) + 스키마 카드 합성 배치):
  - 밴드 위 sim-group 박스 GB(450,400) → **GB:grp1**(밴드 흡수 안 함 → 컨텐츠 카테고리 라우팅).
  - sim-group 헤더 GH(400,370, z=5) → **GH:grp1**(컨텐츠 카테고리).
  - 밴드 위 스키마 카드(200,200) → **SC:s1**(스키마 메뉴 — band-wins 승격 제거).
  - `Adapter.prototype._pickContext === undefined`(band-wins 철회 회귀 잠금).
  - 결과: **ALL PASS — 66 PASS / 0 FAIL**(T21 3-tier 6종 유지 + T22 4종).
- **좌클릭/드래그 불변 근거**: T21(=`_pick` 층서: 카드/테이블/GB→그 요소, combo→스키마, 밴드여백→카테고리)이 좌클릭/드래그 hit 계약을 잠금. GB/GH 좌클릭(클러스터 상세)·GX 좌클릭(접기 토글)·sim-group 리지드 드래그(group-interact §50)는 graph-core 좌클릭 경로라 무변경.
- 회귀 표면: 제품 카테고리 밴드·스키마 클러스터 메뉴·dispatch 타 분기·시각 z·백엔드/RBAC/스키마 0.
- 결과: 코드/문법/단위 회귀 PASS.

### Run (2026-07-15) — POST-DEPLOY 라이브 검증 — **Environment: Windows-browser (win-browser.py relay)** — DEFERRED (배포 후 실측 교체)

- 예정 실증: (배포 전달) 서빙 web-a/b `GIT_COMMIT` + baked `graph-renderer-pixi.js` 에 `_pickContext` **부재** 확인. (라이브) 제품-매핑 데이터소스(예: mysql-kr-an2-auth) 스키마그래프 펼친 스키마 내 sim-group 박스/헤더 우클릭 → **"컨텐츠 카테고리" 메뉴** · 밴드 위 스키마 클러스터 박스 우클릭 → **"스키마" 메뉴**(band-wins 복원) · 제품 카테고리 밴드 여백 → **"카테고리" 메뉴** · 좌클릭 어포던스(클러스터 펼치기·그룹 접기) 보존.
