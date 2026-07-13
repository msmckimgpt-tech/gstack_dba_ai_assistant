---
run_at: 2026-07-13
session: ai/root/feature-0016-graph-pixi
scope: §78 Phase B-early — SceneAdapter(PixiJS v8) 신설·실증
verdict: PASS
---

### Run — SceneAdapter 순수 로직 (Environment: node vm)
- `test_pixi_adapter.js` **28 PASS / 0 FAIL** — 카메라 변환(model↔screen 왕복·clampZoom·fitCamera 중앙정합·minReadZoom·커서고정 줌)·대시 세그먼트(on 총길이·경계)·노드/combo bbox(중심·지름·자식 auto-fit)·contentBounds·hit-grid picking(최상위 z·빈공간·원거리 셀)·scene diff(add/keep/remove)·실 build shape 소비. 결함 1 적발·수정(fitCamera `pad:0` falsy 덮임 → `!= null` 가드).
- 그래프 headless 회귀 11 스위트 **279 PASS / 0 FAIL**(graph/ 무변경 — 어댑터는 신규 파일 graph-renderer-pixi.js, 결합 없음).

### Run — 어댑터 setScene 렌더·성능·이벤트 (Environment: Windows-browser, PB-0008 relay)
- 방법: `adapter-poc.html`(PixiGraphAdapter 실 import → scene-spec(=_metaG6Build 출력형태) setScene). win-browser.py 실 Windows Chrome 150 CDP relay + Playwright(트러스트 마우스 이벤트).
- **디자인 보존(D1~D5)** PASS: 노드 6종(테이블 역할색·컬럼 dot·루틴 보라칩·SC 카드·combo 점선 auto-fit)·엣지 6종(trusted 갈색실선·candidate 골드점선·crossds 마젠타점선·routine 보라 startArrow·SCHEMA_REF 슬레이트+count 27)·**상태 오버레이**(selected 검은 halo·analyzed 보라 dot·dim opacity 0.38)·한글 라벨("확률형 아이템 지급"·"지급 로그 · 결제 연결 컬럼") 전부 정본 수치 등가. 과거 WebGL 실패 모드(텍스처 왜곡·점선 소실) 재현 없음. 스크린샷 adapter_winchrome.png.
- **성능** PASS: 845 등가 씬(5스키마×24T×6C) 팬/줌 **p50 16.7 / p95 16.8ms = 60fps vsync-perfect**(idle 기준선 동일). pageerror 0.
- **이벤트 합성**(spatial hit-grid picking, per-object 이벤트 없이) PASS: node:click(정확 id)·canvas:click(빈공간)·node:dblclick(같은 노드 재클릭만)·드래그=팬(클릭 억제). 결함 2 적발·수정: ① panButton="any" 가 좌클릭을 항상 팬 처리해 클릭 소실 → 이동 임계(4px)로 정지=클릭/드래그=팬 분리 ② dblclick 이 노드 무관 시간만 판정(다른 노드 연속클릭 오판) → `_lastTapId` 동일 노드 게이트.
- headless(SwiftShader) 수치는 소프트웨어 GL 이라 참고 배제 — 정본은 실 Windows Chrome.
