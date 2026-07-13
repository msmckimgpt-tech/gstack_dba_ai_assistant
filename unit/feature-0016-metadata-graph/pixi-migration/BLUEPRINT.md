---
doc_type: MIGRATION_BLUEPRINT
feature_id: feature-0016-metadata-graph
status: plan-review
created_at: 2026-07-13
source_of_truth: true
---

# 그래프 뷰 렌더링 엔진 교체 — AntV G6 v5(Canvas) → PixiJS v8(WebGL/WebGPU)

관리콘솔 `메타데이터 > 그래프 뷰`(cross-cut 코드 거주: feature-0003
`src/static/graph/` 7모듈, ITEM-09 분리 후)의 렌더 계층을 **PixiJS v8(MIT)** 로
교체하는 마이그레이션 계획. **§7.1 Major — plan-review 상태, 사람 승인 후 실행.**

사용자 결정(2026-07-13): G6 계열 유지 경로(WebGL 재번들 스파이크)는 과거 디자인
실패 이력(WebGL 텍스처 왜곡·점선 소실·오버레이 비동기 — ADR-004 배경 ③⑤)으로
기각. **기존 디자인이 무너지지 않는 형태로 정합 + 성능 확보**가 양대 완료 조건.

## 1. 배경 — 왜 교체하나

여러 차례의 최적화(§57 엣지 LOD → §61 컬럼 LOD → §63/§65/§67 집계·뷰포트 컬링 →
§73 배치 메모이즈 7.4× → §74 미니맵 재사용 → §76 컬링 참조 보존)로 **rebuild
축과 방출 수 축은 해소**됐으나, 노드가 많은 상태의 **카메라 이동(팬) 버벅임**이
잔존한다는 사용자 리포트 다수.

- 근본 원인: G6 Canvas 렌더러는 immediate-mode — 카메라가 움직이는 **매 프레임
  화면 안 전 도형을 CPU 벡터 래스터로 재도장**(실측 ~1ms/노드, ADR-030). 화면 안
  500+ 요소면 프레임 예산 16.6ms 구조 초과. 뷰포트 컬링은 화면 **밖**만 줄이므로
  이 축을 못 건드림.
- 가중 요인: §76 실시간 드래그 컬링이 팬 도중 rAF 스로틀 재-emit(`setData`+`draw`)
  을 추가.
- PixiJS v8 은 씬을 GPU 에 상주시키고 팬/줌 = 카메라(루트 Container) 행렬 갱신 1회
  → 팬 프레임당 CPU ≈ 0. 요구 도형이 rect/circle/line/text 4종뿐이라 적합.

결합도 실측(2026-07-13 인벤토리): 그래프 JS ≈5,491줄 중 **G6 직접 결합은
~700–900줄(15–20%)** — init config·apply/draw·카메라 API ~45지점·이벤트 15종·
스타일 생성기·드래그 핸들러. 레이아웃(masonry/seriation/simgroups)·메모이즈·
LOD 판정·데이터 모델·DOM 패널 전부(graph-ctxmenu 2,237줄)는 엔진-중립.

## 2. 디자인 보존 계약 (사용자 핵심 요구 — hard gate)

과거 WebGL 실패 모드별 구조적 회피를 명시한다. **아래 체크리스트가 Phase A POC 와
Phase C PB-0008 의 공통 게이트**이며, 1항이라도 FAIL 이면 다음 Phase 진입 금지.

| # | 과거 실패 모드 (G6 이전 WebGL) | PixiJS 에서의 구조적 회피 | 게이트 |
|---|---|---|---|
| D1 | sprite-atlas 텍스처 업스케일 왜곡(테두리 뭉개짐) | 스프라이트 스케일링 미사용 — `Graphics` **벡터 테셀레이션** + `resolution=devicePixelRatio`. 줌 배율별 재테셀레이션 정책(POC 확정) | 줌 0.05~4 전 배율 스크린샷: 테두리/라운드 선명도 현행 Canvas 동등 |
| D2 | 점선(추정 관계) 렌더 불가 | 대시 세그먼트 자작 헬퍼(폴리라인 분할, ~50줄) — candidate 골드 `[6,4]`·cross-DB 마젠타·ROUTINE_USES 보라 잔점선 3종 패턴 등가 | 3종 점선 side-by-side 시각 등가 |
| D3 | HTML 오버레이-캔버스 갱신 비동기 | 오버레이 hack 재도입 없음 — 라벨/컨트롤/밴드 전부 Pixi 씬 내 렌더(G6 이관 때 확립한 캔버스-네이티브 구조 유지) | 줌/팬 중 라벨-도형 동기 이동 |
| D4 | (신규 위험) 한글 라벨 수천 개 선명도/메모리 | POC 에서 `Text`(per-string 텍스처 캐시) vs `BitmapText`(동적 한글 glyph atlas/MSDF) 실측 비교 후 확정. 극단 줌인 blur 시 zoom-bucket 재래스터 | 라벨 선명도 전 배율 육안 + JS heap 상한 |
| D5 | 시각 상태(선택/dim/역할색/마커) 회귀 | ADR-027/028 **base-style bake 철학 그대로** — build 시 스타일 확정 후 씬 반영(상태 apply/revert 의존 없음). `_META_GRAPH_COLOR`/`_META_ROLE`(Okabe-Ito)/`_METZ` z-order 상수 무변경 소비 | 하이라이트/dim 0.38/역할칩/마커(주황·보라) 현행 동등 |
| D6 | 미니맵 파손 | 커스텀 미니맵(오프스크린 `RenderTexture` 1회 렌더 + 뷰포트 마스크) — §74 기하 서명 재사용 로직 이식, §77(nodePosAll 전체 위치 맵) 계획과 정합 | 미니맵 렌더·마스크 추종·구성 변경 반영 |

시각 스펙의 정본은 현행 스타일 생성기(`graph-roleviz.js:223-313`)의 출력값 —
색·선폭·라운드·라벨 폰트/배치/maxWidth·zIndex 를 **수치 그대로** 이식한다
(재해석 금지).

## 3. 아키텍처 — SceneAdapter 경계

```
[불변] graph-state.js(모델·상수) / graph-rellayout.js / graph-simgroups.js
[불변] graph-ctxmenu.js(상세·관계 패널·컨텍스트 메뉴·검색·AI 분석 DOM)
[불변] _metaG6Build 좌표 계산부(masonry/shelf-pack/realH/컬링·LOD 판정) + _metaTopoSig 메모이즈
────────────────── scene-spec (엔진-중립: {id,kind,x,y,w,h,style,z,label,states}) ──────────────────
[신설] graph-renderer-pixi.js  = SceneAdapter
        ├ init(container,cfg) / setScene(spec) / destroy
        ├ 카메라: getZoom·zoomTo·zoomBy·translateBy·fitView·focusElement·
        │        getCanvasByViewport·getViewportByCanvas·getElementRenderBounds·
        │        getElementPosition·getSize·resize  (루트 Container transform ≈ 카메라)
        ├ 이벤트: node/combo/edge/canvas × click·dblclick(320ms 자체판정)·contextmenu·drag,
        │        중간버튼 팬(_metaCanvasDragEnable 등가), wheel 줌(zoomRange [0.05,4]),
        │        aftertransform 등가 카메라 이벤트
        ├ 오브젝트 풀: id-key 재사용 + diff 적용(G6 setData diff 등가 — GC churn 억제)
        ├ 히트테스트: per-object eventMode 대신 모델 좌표 spatial grid 커스텀 picking
        └ 미니맵: RenderTexture + 마스크(§74 서명 게이트 이식)
[교체] graph-core.js 의 G6 접점(~700줄): _metaInitGraph/_metaG6Apply(Once)/
       _metaGraphAnimateFocusRun/드래그 핸들러/aftertransform 핸들러 → adapter 호출로 치환
[제거(단계적)] vendor/g6.min.js(1.38MB) → vendor/pixi.min.js(v8 UMD, ~450KB — 순감)
```

- **combo 해방**: G6 combo auto-fit(`getContentBBox(children)`) 제약이 소멸 —
  스키마 카드 bbox 를 직접 그리므로 §65/§67 이 감수하던 combo-safe 제약(테이블
  칩 상시 방출 등)이 불필요해진다. 단 **이관 단계에서는 LOD/컬링 장치를
  behavior-neutral 로 보존**(한 번에 한 변수 — 렌더러 교체와 최적화 제거를 분리),
  제거·단순화는 라이브 실측 후 별도 § 후속.
- **폴백 플래그**: `graph-core.js` 에 렌더러 선택 seam(`_META_RENDERER =
  'pixi'|'g6'`, admin.html cache-buster 로 전환) — 회귀 시 즉시 G6 복귀.
  g6.min.js 제거는 라이브 soak 후 후속 커밋.

## 4. Phase 계획

### Phase A — POC (디자인-등가 실증 우선, exit gate 부착)
1. A1 PixiJS v8 최신 안정판 UMD/ESM 번들 vendoring(`vendor/pixi.min.js`) + 라이선스(MIT) 확인.
2. A2 POC 하네스(`pixi-migration/poc/`): 실 admin.html 그래프 마크업 + mock API
   (g6-migration/poc 방법론 재사용, Playwright headless + 스크린샷).
3. A3 대표 씬 렌더: 스키마 카드(펼침 combo 등가/접힘 SC:)·테이블 칩(역할색)·컬럼
   circle+라벨·루틴 ƒ⚙·카테고리 밴드(CAT/CATH/CATX)·sim-group 박스·엣지 6종
   (trusted/candidate/inferred/cross-DB/SCHEMA_REF/ROUTINE_USES)·미니맵 스텁.
4. A4 **디자인 게이트**: §2 체크리스트 D1~D6 — 줌 [0.05, 0.15, 0.35, 0.5, 1, 2.5,
   4] × 2x DPR 스크린샷을 현행 G6 과 side-by-side 비교 + win-browser 실 Windows 육안.
5. A5 **성능 게이트**: 882노드/5스키마 펼침 등가 합성 모델(mssql-qa-idc 실측 재현)
   + 10k 요소 스트레스 — 연속 팬/줌 프레임타임 **p95 < 16.6ms**, 히트테스트 < 2ms.
6. A6 텍스트 전략 확정(D4) + 대시 헬퍼 확정(D2).
- **Exit A**: 디자인 체크리스트 전항 PASS + 성능 게이트 PASS → 사용자 육안 승인
  후 Phase B. FAIL 시 결과 보고 후 중단(G6 잔류 + 팬-경로 국소 개선으로 후퇴).

### Phase B — 어댑터 통합 (graph/ 모듈)
1. B1 `graph-renderer-pixi.js` 신설(§3 SceneAdapter 전체 표면).
2. B2 `_metaG6Build` emission 절을 엔진-중립 scene-spec 으로 정리(좌표 계산부
   무변경 — headless 기존 스위트가 좌표 불변을 잠금).
3. B3 `graph-core.js` G6 접점 치환: `_metaInitGraph`(config 45줄)·
   `_metaG6Apply/ApplyOnce`·카메라 애니팬(`_metaGraphAnimateFocusRun`)·드래그
   핸들러(216줄)·`aftertransform` 핸들러(LOD 밴드·컬링 재-emit — 동일 로직,
   이벤트 소스만 adapter).
4. B4 스타일 생성기(`graph-roleviz.js`) scene-spec 중립화(수치 무변경).
5. B5 커스텀 미니맵(D6) + §74 서명 게이트 이식.
6. B6 렌더러 토글 seam + admin.html vendor 교체 + cache-buster bump.
7. B7 headless 신설: `test_pixi_adapter_*.js`(scene-spec→씬 매핑·카메라 수학·
   히트테스트·대시 세그먼트) + 기존 `test_g6build_*` 249+ PASS 회귀 0
   (build 계층 무변경 잠금).

### Phase C — 검증·배포
1. C1 PB-0008 실 Windows 시각검증(hard gate, `visual_verification_scope: always`):
   §2 디자인 체크리스트 + 상호작용 전 플로우(단일/더블클릭·우클릭 4종 메뉴·노드/
   클러스터/그룹 드래그·검색 badge·상대 하이라이트/dim·컬럼 선택·관계행 카메라 팬·
   스키마 점프·깊이 select·AI 분석 마커/진행 패널·범례·미니맵) + **팬 프레임타임
   before/after 실측**(win-browser 함수분해 레시피 재사용).
2. C2 배포(deploy_scope: included — `bin/deploy-web.sh`) + soak + POST-DEPLOY 육안.
3. C3 문서 정합: ADR 신설(**ADR-004 supersede**)·TASK/REPORT/TEST/MODIFY·릴리즈노트.
4. C4 (후속 별도 §) LOD/컬링 장치 단순화 — GPU 상주로 불필요해진 §61/§65/§67/§76
   경로 실측 기반 제거.

## 5. 리스크 레지스터

| # | 리스크 | 완화 |
|---|---|---|
| R1 | 한글 라벨 수천 개 텍스처 메모리/선명도(D4) — **G6-WebGL 실패의 재발 지점** | Phase A 선행 게이트. BitmapText 동적 atlas vs Text 캐시 실측 비교. zoom-bucket 재래스터 정책 |
| R2 | 점선 시각 등가(D2) | 대시 헬퍼 POC 선행 + side-by-side |
| R3 | 히트테스트 규모(수천 오브젝트) | per-object 이벤트 비활성 + spatial grid picking(모델 좌표는 이미 순수 JS 에 존재) |
| R4 | 풀 rebuild 패턴의 GC churn(3k+ 오브젝트) | id-key 오브젝트 풀 + diff 적용(G6 setData diff 등가) |
| R5 | WebGL 컨텍스트 상실 | Pixi 컨텍스트 복구 이벤트에서 `setScene` 재적용 |
| R6 | **병렬 세션 충돌**: `feature-0016-minimap-fullview` worktree 가 `graph-core.js` 미커밋 수정 중(§77 계열), `content-cluster` ahead 커밋 존재. TASK §번호 충돌 관례적 발생 | **순서 게이트: Phase B 착수는 minimap-fullview·content-cluster cycle 착지 후**(F2 단일 mutator). §번호는 머지 시 scoped-renumber(§13.1 관례). 미니맵 fullview 산출물은 B5 에서 Pixi 로 재이식 |
| R7 | ITEM-09(graph/ 모듈 분리) 브라우저 QA 미완 위에 쌓음 | Phase B 전 ITEM-09 QA 사인오프 확인(또는 Phase C 에서 합산 검증 명시) |

## 6. 완료 판정 기준 (acceptance criteria)

1. §2 디자인 체크리스트 D1~D6 전항 PASS(PB-0008 실 Windows, 스크린샷 증적).
2. 팬/줌 프레임타임 p95 < 16.6ms @ 882노드/5스키마 펼침 등가 씬(win-browser 실측,
   현행 대비 개선 수치 병기).
3. 상호작용 전 플로우(§4 C1 목록) 현행과 동작 동등, pageerror 0.
4. headless: 기존 build 스위트 회귀 0 + pixi-adapter 신설 스위트 PASS.
5. 렌더러 토글 폴백(G6 복귀) 동작 실증 후, soak 통과 시 g6.min.js 제거 커밋.

## 7. 일정·등급

- Phase A 1~2일 / Phase B 3~5일 / Phase C 1~2일 (AI cycle, PB-0008 게이트 포함).
- 위험도 **Major**(§12.3 — 다중 파일·사용자-대면 대형 UI 교체·배포). 인증/데이터/
  마이그레이션 무관(frontend-only, 마이그 0).
- §7.1: 본 계획 승인(`PLAN-APPROVED` 마커, TASK §78) 후 Phase A 착수.
