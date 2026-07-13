---
run_at: 2026-07-13
session: ai/root/feature-0016-graph-pixi
scope: §78 B-late graph-core seam 배선 통합 실증 (렌더러 G6→PixiJS)
verdict: PASS (라이브 admin PB-0008 = 배포 후 후속)
---

### Run — 통합 하네스 (Environment: Windows-browser, PB-0008 relay)
- 방법: `integration-harness.html`(실 admin.html 그래프 마크업 + Pixi UMD + graph 8모듈 번들(어댑터 포함) + mock apiFetch) — 로그인 없이 `_metaShowGraph()` → `_metaInitGraph` 가 seam 으로 PixiGraphAdapter 구성. win-browser.py 실 Windows Chrome 150 CDP relay.
- **seam**: `_metaRendererKind()`='pixi'(window.PIXI 존재), `_metaGraph.graph.constructor.name`=PixiGraphAdapter, renderer=webgl, pixi 8.19.0. PASS.
- **렌더**: roots 6 스키마 카드(인디고 테두리·한글 라벨) 정상 렌더(render-on-demand — ticker autoStart:false + 변경 시 _render(); preserveDrawingBuffer:true). PASS.
- **툴바 버튼**: 줌 +(1.25×)·−(0.8×)·100%·전체맞춤 전부 zoom 정확 변경. PASS.
- **성능**: 팬/줌 p50=p95=16.7/16.8ms = 60fps vsync-perfect. PASS.
- **적대리뷰(§18.8) 수정 실증**: B1 카드 200,150 이동 후 새 위치 `_pick` hit·옛 위치 miss(hit-grid 재구성). pixi 컬링 비활성(`_metaGraph._cullActive`=false — M3 미니맵 전역·M4 팬 rebuild 소거). PASS.
- **pageerror 0**(ResizeObserver loop 경고는 브라우저 양성 — 크기 가드 후 소강).
- headless(SwiftShader) 수치는 참고 배제. 정본=실 Windows Chrome.

### Run — 라이브 admin 그래프 뷰 실데이터 (Environment: Windows-browser) — 배포 후 후속(T78.4)
- 배포 후 https://localhost/admin 로그인 → 지식베이스 > 그래프 뷰: 실 데이터소스 스키마 카드·펼침(테이블/컬럼)·노드 클릭 상세·더블클릭 이웃확장·우클릭 컨텍스트 메뉴(전 항목)·드래그 자유배치·검색·kind 필터·상세 패널 카메라 이동·AI 능동분석 마커·미니맵·대형 스키마 팬 성능. 전 버튼·상호작용 정합 + 팬 before/after 실측 + pageerror 0.
