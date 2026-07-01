# Report

## 2026-07-01 · 컬럼 blob·프레임 거침·느린 줌 수정 (graph-perf2, WebGL 후속)

### 배경 (WebGL 배포 후 사용자 육안 3건)
(1) 프레임 여전히 거침, (3) 17컬럼 테이블 더블클릭 시 컬럼이 세로 스택 아닌 **원형 뭉치(blob)**, (4) 휠 줌 너무 느림.
(2 라벨유지=OK.) → WebGL 로도 거침이 안 잡혀, 병목이 렌더가 아님을 시사.

### 진단 (5에이전트 워크플로: 3렌즈 진단 → 통합설계 → 적대검증)
- blob·거침 **동일 뿌리**: 컬럼 세로정렬을 fcose 제약(alignment/relativePlacement)에 위임 + 화면 전체 테이블 제약을
  numIter 1000 동기 tick 마다 재구성·적용. (a) fcose 가 신규 컬럼 **ring seed**(반경 90 원)를 세로로 못 펼쳐 blob
  잔존, (b) 제약 동기 계산(cose-base runSpringEmbedder while-loop, rAF/yield 0건)이 rAF 를 굶겨 프레임 거침.
  **WebGL 은 렌더만 GPU 화 → 이 계산 병목과 무관**(거침 개선 없던 게 정합). 줌=독립(wheelSensitivity 0.3=기본 1/3 스텝).
- verify(적대): go-with-fixes. 컬럼정렬 공백경로 없음, 제약 '키 제거'가 fcose tile-off 취약성 오히려 제거(더 안전).

### 수정 (admin.js)
- 컬럼 세로정렬을 fcose 제약에서 **제거** → layoutstop `_metaGraphPlaceColumns` **결정론적 세로 배치**(batched, ordinal,
  무게중심 상하대칭·x통일, 전 경로 공통). 신규 컬럼 seed ring→세로. `wheelSensitivity` 제거(기본 1). 박스 겹침 상쇄
  PITCH 22→18 + nodeSeparation 150→220.

### de-risk (실 Windows 브라우저)
17컬럼 + 6이웃 ERD 렌더 → **컬럼 x-spread 0.0px(완벽 세로스택·blob 소멸)** + **박스겹침 2→0**(PITCH18/nodeSep220). 스크린샷 확인.

### 검증
- node --check PASS. 적대 리뷰 BLOCKING 0(REV-20260701T220000). **실 FPS·대규모 겹침·줌 체감은 사용자 실 하드웨어 재확인이 최종.**

## 2026-07-01 · 렌더러 canvas-2D → WebGL 전환 (graph-webgl, 프레임레이트 근본 해소)

### 배경 (사용자 육안 후속)
camfps(카메라 애니 중 라벨 숨김) 배포 후 사용자 육안: "여전히 거친 프레임 + 애니 시작 시 라벨 사라짐(불호) +
렌더링 엔진이 부드러운 프레임 지원하는지 검토". 사용자 직감이 정확했음.

### 진단 확정 — 렌더링 엔진이 구조적 상한
- vendored **Cytoscape 3.30.2 = canvas-2D 렌더러 전용**(`getContext("2d")`, `webgl` grep 0건). 매 프레임 그래프
  전체를 CPU 재래스터.
- 트레이스 재분석: 병목은 레이아웃 계산(fcose self 64ms) 아님 → **Cytoscape 코어 렌더 1040ms**(캔버스 재그리기).
  rAF 60fps인데 표시 ~36fps 드롭. GPU(276ms)·컴포지터 유휴. chrome://gpu HW 가속 ON. = canvas-2D 재그리기+합성
  체인의 지연 상한 → 라벨 숨김 등 미세 튜닝으로 못 넘음.

### 결정 (AskUserQuestion 2단)
① canvas 유지·애니 최소화(A) vs WebGL 업그레이드(B) vs 라벨만 복구(C) → **B**. ② WebGL 은 taxi→bezier·dashed→
미지원 강등이 따름 → 강등 수용(A) / 엣지 재설계(B) / 보류(C) → **엣지 재설계(B)**.

### de-risk (실 GPU) — make-or-break 통과
그래프가 ERD-card compound(스키마>Table>컬럼 2단 중첩)로 진화 → WebGL compound 지원이 관건. **실 Windows 브라우저
(win-browser)에서 cytoscape 3.34.0 + webgl:true + 2단 compound 최소 페이지 렌더** → webglContextDetected=true,
compound 박스·라벨·bezier 엣지 전부 정상(스크린샷). 전체 구현 전 리스크 제거.

### 구현
- vendor cytoscape 3.30.2→**3.34.0**(unpkg 정품, fcose 2.2.0 호환 유지). `renderer:{name:"canvas",webgl:_webglOk}`
  + feature-detect 폴백. 엣지 재설계(bezier·색/투명도 구분). 애니 중 라벨/엣지 숨김 전면 제거(항상 표시). pixelRatio 제거.

### 검증
- node --check PASS. 적대 리뷰 패널(§18.8) → REVIEW.md. PB-0008 실 Windows 브라우저(WebGL 활성·compound·라벨·엣지·
  부드러움·대규모 이웃). **실 FPS 효과는 사용자 실 하드웨어 재측정이 유일 검증**.

## 2026-07-01 · 그래프 애니 프레임레이트 저하 — 카메라 애니 구간 라벨/엣지 숨김 (graphux-camfps, resume 인계)

### 배경 (resume)
이전 세션(2597e01c)이 "노드 수 무관 애니 FPS 저하" 를 8회 반복 진단하다 headless 로 실 FPS 재현 불가 →
사용자에게 DevTools 실측 요청 직후 **컨텍스트 초과("Prompt is too long")로 중단**. 사용자가 트레이스+환경+GPU
샷 제공. resume persona 로 인계해 트레이스 분석부터 재개.

### 진단 (DevTools Performance 트레이스 실측 — Trace-20260701T134334, 10.4s / 70,418 events)
- 메인스레드 busy = 전체의 **20%** (한가). 그중 **Scripting 65%(FunctionCall 1180ms)**, Rendering·Painting 각 1%.
- JS 핫스팟 = Cytoscape 내부: `ts`(캔버스 draw 162ms)·`Cs.apply`/`parsedStyle`/`updateStyleHints`(스타일 재계산)·
  `calculateLabelDimensions`/`boundingBox`(라벨 텍스트 측정·렌더).
- **rAF(메인 JS) = 60fps(median 16.7ms) 로 정상**인데 **실제 표시 프레임(Swap) = ~36fps(median 27.8ms)** → 프레임 드롭.
  대형 잭 189/105/76ms = 데이터 로드/레이아웃 시작 fcose 동기계산.
- chrome://gpu: Canvas·Compositing·Rasterization **HW 가속 ON** (GPU 폴백 아님). rAF 16.7ms 고정 = 사실상 60Hz(144Hz 가설 기각).
- **근본원인**: 레이아웃 애니는 라벨/엣지 숨김 최적화됨(기존)이나 layoutstop 즉시 복원 후 **450ms 카메라 fit 애니가
  라벨·엣지를 켠 채** 돌아 per-frame 텍스트 래스터+엣지 지오메트리 재계산 재발.

### 수정 (admin.js)
- `_metaGraphLayout` layoutstop: 숨김 해제를 카메라 fit 애니 `complete` 후로 지연(`restoreMotion`, guard `!_layoutRunning`,
  setTimeout 650ms fallback). 즉시맞춤/예외 경로는 동기 복원. 이미 레이아웃 애니에 검증된 패턴의 카메라 애니 확장 —
  예전 hideEdgesOnViewport 전역옵션 버그와 무관. 등급 Minor(프론트·비파괴). 캐시버스터 graphux-camfps.

### 검증
- node --check PASS. 적대 리뷰 패널(§18.8) → REVIEW.md. verify-completion → commit/PR/merge → web 재배포.
- **한계(정직)**: 실 FPS 개선은 **사용자 실브라우저에서만 확인 가능** — headless/WSL 은 실 GPU 프레임 미측정(세션이
  막힌 근본 이유). 배포 후 사용자 재측정 필수. PB-0008 은 렌더 정합만 확인.

## 2026-07-01 · 그래프 뷰 컬럼 테이블 하단 실제순서 세로배치 + 부드럽게 꺾이는 엣지 (graphux9/10, 배포 완료)

**요청**: `관리 콘솔 > 메타데이터 > 그래프 뷰` 에서 청색(테이블) 노드에 연결된 회색(컬럼) 노드가 흩어져
순서 판독이 안 되고 타 테이블 엣지와 교차 → (1) **테이블 노드 하단으로 컬럼을 실제 순서대로** 세로 배치,
(2) 연결선을 직선이 아닌 **부드럽게 꺾이는 선**으로.

**구현** (PR #496, `column-ordinal`):
- **컬럼 순서(ordinal)를 관계형 SSOT 에 저장**: alembic **0027** `column_descriptions.ordinal`(비파괴 ADD +
  삽입순 backfill, expand-safe) → `metadata_graph.sync_column` 이 AGE Column 정점에 정수 투영 → 그래프 API →
  프론트 정렬키. 부트스트랩 골격 저장이 `describe_columns`(ORDINAL_POSITION) 순서를 ordinal 로 캡처.
- **프론트(admin.js graphux10)**: `_metaGraphPlaceColumns` 가 각 Table 의 HAS_COLUMN 자식을 ordinal(NULLS
  LAST→name) 정렬해 테이블 바로 아래(우측 54px 들여쓰기) 세로 스택 + lock, `dragfree` 로 테이블 이동 추종.
  `HAS_COLUMN` 엣지 = `round-taxi`(아래→오른쪽 부드럽게 꺾임), 그 외 = `unbundled-bezier`(완만 곡선).
- graphux8b/9(모션 성능·라벨/엣지 트윈 숨김) 정책과 정합(카메라 무애니 `cy.fit` 유지).

**검증**:
- 적대 리뷰 2패널(backend/security + frontend/ux) — 발견 결함 전건 수정(REVIEW.md REV-20260701-0003):
  update_column_desc param 정합·sync_graph graceful·Table drag 컬럼 추종(dragfree)·ordinal 범위가드.
- 순수함수 단위 8건 PASS(ordinal 직렬화·주입안전) · migrate-lint expand-safe · py_compile/node --check OK.
- **배포**(deploy_scope: included): migrate 0027(라이브 적용, 기존 1030 컬럼행 ordinal backfill) + insight-worker
  재빌드 + `metadata-graph-sync`(1030 컬럼 ordinal 투영, errors 0) + web 롤링 재배포(git_commit=47d0f1a,
  edge /healthz 200 안정). ※ 초기 롤링 1회는 동시 재sync 부하로 /healthz 순간 503 → 자동 롤백된 false-positive,
  재sync 종료 후 정상 배포 확정.
- **PB-0008 실 Windows 브라우저 시각검증 PASS**(TEST.md §3): Achievement(4컬럼) 테이블 하단 UniqueID→Type→
  Title→DLC 순 세로배치 + round-taxi 엣지, Item(75컬럼) ordinal 단조 정렬. API 도 1030 컬럼 ordinal 반환 확인.

**주의(발견·복구)**: 최초 작업이 stale `graphux4` base(main 대비 −16커밋) 위에서 진행됨을 배포 직전 발견 →
현재 main(graphux8b/9 + implicit-edges) 위로 재기반(충돌 6+1파일 해소, 성능 결정 존중, 마이그 0026→0027 재번호).

**후속**: MSSQL `column_descriptions.schema_name`(DB명, 예 `dk_data_release`)과 `rag_objects` 투영 테이블 fqn
(예 `dk_data_release_test.*`)의 **키 불일치**로, 일부 테이블은 그래프에서 rag-투영 노드와 curated-컬럼 노드가
서로 다른 Table 키에 걸린다(REPORT 2026-06-30 dbo→DB명 정규화 잔여와 동일 계열). 컬럼이 보이는 것은
curated schema_name 과 일치하는 Table 노드 확장 시 — 근본 정규화는 별도 initiative 권장.

## 2026-07-01 · 암묵 관계(FK 미선언) 추론 + 자기교정 강화 엔진 (implicit-edges cycle)

**요청**: `관리 콘솔 > 메타데이터 > 그래프 뷰` 가 저장하는 연결에서, insight 가 파악한 데이터소스 중
**FK 로 직접 확인 안 되는 뉘앙스적 연결(암묵 JOIN 관계)** 을 파악해 사람·AI 가 쉽게 보게 하되, 그 연결이
정말 올바른지 **항상 검증**해 틀리면 가중치가 약해져 끊어지고(broken) 맞으면 강해져 신뢰(trusted) 관계로
재구성되게 한다.

**배경**: feature-0016 이 남긴 미완 과제(REPORT 하단 "엣지 적재: 현 0 … 대화 JOIN 학습·LLM 추론으로
점증", "T1.6 FK 미선언 보완")의 본체. 게임 운영 DB 8,122 테이블이 FK 를 거의 선언 안 해 그래프에 선이 없다.

**사용자 결정 (2026-07-01, entry persona dispatch)**:
- 검증 방식 = **관찰 + 능동프로브 하이브리드**: AI JOIN 사용 성공(관찰) + insight 워커의 실데이터
  겹침(EXISTS) 프로브(능동)로 양성/음성 신호 생성.
- 범위 = **풀 슬라이스**: 추론 + 강화엔진 + 그래프 가중치 투영 + AI 컨텍스트 필터 + UI 신뢰/추정/파단 구분.

### 설계 (정적 confidence ↔ 동적 weight 분리)
- **스키마 (alembic 0026, 비파괴 ADD COLUMN)**: `table_relationships` 에 `weight`(동적 신뢰),
  `positive_signals`/`negative_signals`, `status`(candidate/trusted/broken), `last_validated_at` 추가 +
  source CHECK 에 `'inferred'` 추가 + 상태/가중 정렬 인덱스. 기존 행 backfill(weight←confidence).
- **추론** (`relationships.infer_implicit_relationships`, 순수): 명명 규칙 2 휴리스틱 — (1) `<base>_id`
  컬럼 → 동명 테이블 PK(name_fk), (2) 접두 있는 키 컬럼 공유(shared_key). 범용 컬럼·과다공유 차원 제외,
  cap 으로 8K 폭주 방지. source='inferred', status='candidate' 로 시작.
- **강화 엔진** (`next_reinforcement_state`, 순수 + `apply_relationship_signal`): 양성 `w+=step*(1-w)`(점근
  상승), 음성 `w*=(1-step)`(더 빠른 감쇠 — 비대칭). w≤0.15 → broken, w≥0.85+양성누적 → trusted.
  **FK 는 권위적 — 강등 없음.** upsert on-conflict 가 강화상태 보존(재추론이 파단 엣지 부활 안 함).
- **"항상 파악" 2 경로**: (a) 대화 — 성공한 JOIN = 양성(`learn_relationships_from_sql` 이 upsert+강화),
  (b) insight 워커 — candidate 를 실데이터 겹침 프로브로 검증(겹침률 ≥0.5 양성 / ==0 음성). 둘 다 guarded.
- **노출**: read·context 주입은 broken 제외 + weight 정렬 + `[추정 w=…]`/`[신뢰]` 태그(AI 가 신뢰수준 인지).
  그래프 투영은 REFERENCES 엣지에 weight/status → UI 신뢰=실선 / 추정=점선 / 파단=숨김 + 범례·상세 배지.
- **config**: `AGENT_RELATIONSHIP_INFERENCE_ENABLED`·`_PROBE_ENABLED`(기본 ON) + `_INFER_CAP`/`_PROBE_CAP`/
  `_PROBE_SAMPLE`.

### 변경 파일
- `feature-0002-agent-core`: `alembic/…0026_relationship_reinforcement.py`(신규), `modules/relationships.py`
  (추론·강화·프로브 엔진), `modules/insight.py`(추론+프로브 훅), `modules/metadata_graph.py`(weight/status
  투영·broken 제외), `modules/dialects.py`(probe_relationship_overlap MySQL/MSSQL).
- `shared/config.py`(플래그 5).
- `feature-0003-agent-web-ui`: `static/admin.js`(엣지 status/weight 데이터·신뢰 배지), `static/admin.html`
  (범례·캐시버스터), `static/styles.css`(신뢰 스타일).

### 검증
- **단위 테스트 PASS** (`test_relationships.py`, 총 38건): 강화 전이(점근 상승·**비대칭 전 구간**·broken
  파단·trusted 승격·FK 불변·50% 오양성에도 파단), 프로브 판정 임계·타임아웃, 추론 휴리스틱(name_fk·
  shared_key·범용/과다공유 제외·cap), digest 신뢰 태그·7-tuple 하위호환, dialect 프로브 SQL(LIMIT/TOP·
  식별자 이스케이프·시간상한).
- py_compile 6 모듈 OK · admin.js `node --check` OK · ruff clean · 전체 suite collection EXIT=0(import 무회귀).
- ON CONFLICT ↔ UNIQUE 불변식 테스트 유지(target 무변경).
- **§18.8 적대 패널(security + backend/qa) 2회 — REV-20260701-0002**: SECURITY 1 MINOR(프로브 statement
  timeout 부재) + BACKEND 4 MAJOR(비대칭 역전·테스트 은폐·파단 엣지 그래프 미회수·downgrade 실패) + 3 MINOR
  (signal race·dead cap config·FK 승격 카운터) — **전건 수정 후 SHIP**. 특히 MAJOR-1(추론 시작 weight 0.30
  구간에서 비대칭 역전 → 틀린 엣지 상승)은 곱셈 감쇠를 고정 감산으로 바꿔 전 구간 down>up 보장으로 해소.

### 잔여 / 후속
- **라이브 e2e = cutover 된 AGE 스택 필요**: alembic 0026 적용 + insight 워커 재빌드 후 `metadata-graph-sync
  --rebuild` → 그래프에 추정 엣지(점선) 출현 확인은 배포 게이트 대상. 프로브는 운영 DB read-only(키 컬럼
  표본 LIMIT 50, cap).
- 주기 re-probe: 현재는 스키마 구조 변경/신규 시 프로브. 상시 재검증은 sync cron 확장(후속).
- PB-0008 실제 브라우저에서 점선/실선·배지 시각 확인(배포 후).

## 2026-06-30 · 라벨 비겹침 펼침 + dbo→DB명 클러스터링

**요청1 (라벨 겹침)**: dbo 클러스터 노드 라벨이 겹쳐 판독 불가 → fcose `nodeDimensionsIncludeLabels:true`
(라벨 박스까지 충돌 회피 = 비겹침 핵심) + `animate:true`(펼침 애니메이션, ~600노드 이하) + nodeSeparation
80→150 · nodeRepulsion 7k→12k · idealEdgeLength 75→120 · tilingPadding 30. cose 폴백도 동일 적용.

**요청2 (dbo 집계 검토)**: **버그 확인 — 의도된 것 아님.** rag_objects(auto-insight)가 MSSQL 에서
schema_name 을 리터럴 'dbo'(기본 스키마)로 저장 → (a) DB 차원 소실(전 테이블 dbo 한 박스) (b) **다중 DB
동명 테이블 충돌**(예: 23개 DB 의 dbo.T_ErrorLog → 1 노드 붕괴, sysdiagrams 16 등). DB명은 object_key
(`<ds>:db.dbo.table`)에 존재. 큐레이션(table_descriptions)은 이미 DB명(AccountDB 등) 사용 → 경로 불일치.
**수정**: `_rag_effective()` 가 object_key 를 파싱해 **DB명을 스키마(클러스터)로 사용** + fqn=`db.table`
(충돌 제거). MySQL(2-seg)은 무변화. 단위 테스트 PASS. 잔여(미세): object_key DB명 소문자(accountdb) vs
큐레이션(AccountDB) 대소문자 차이로 동일 DB 가 2 클러스터 가능 — 후속 정규화 권장(insight-worker 근본수정 동반).

검증: admin.js node --check · metadata_graph.py py_compile · _rag_effective 단위 PASS. 그래프 rebuild 후 라이브 스크린샷.


## 2026-06-30 · 그래프 뷰 UX 개선 (반응형 · 관련도 사이징 · 카테고리 클러스터링)

**요청**: 그래프가 사람이 보기 까다로움 → 반응형 + 키워드 관련도별 노드 크기 + 유사 카테고리 집적.
**웹 리서치**(Neo4j Bloom·Linkurious·Cytoscape): 노드 크기=중요도/관련도·색=카테고리가 표준, 카테고리
집적은 **fcose**(compound force layout, 리서치 1순위)가 정석.

**구현** (admin.html/admin.js/styles.css + vendor):
- **fcose vendoring**(layout-base→cose-base→cytoscape-fcose) — compound 클러스터 force layout. 미등록 시 cose 폴백.
- **카테고리 클러스터링**: 노드를 스키마(scope:schema) compound parent 로 묶음(점선 박스). HAS_TABLE 엣지는
  컨테인먼트로 대체(생략). fcose gravityCompound 로 스키마 내부 집적 강화.
- **관련도 사이징**: 검색 시 노드별 관련도(exact>prefix>contains, name>fqn) 0~1 → 크기 +최대 40·rel≥0.8 테두리 강조.
- **반응형**: ResizeObserver→cy.resize/fit, 캔버스 clamp(420~760px·64vh), 상세패널 접기 토글 + ≤900px 세로 스택, 범례 추가.

**검증**: admin.js node --check OK. fcose 폴백·compound 는 cose 도 지원이라 견고. 라이브 렌더는 배포 후 스크린샷.

## 2026-06-30 · per-datasource 그래프 (rag_objects 투영 + scope 필터)

**배경**: cutover 후 "각 데이터소스 그래프 출현" 검증 중, table_descriptions(큐레이션)는 **단 1개
datasource**(mssql-06656002eda6, 153)만 커버해 나머지 19개 데이터소스 그래프가 비어있음을 발견.
반면 `rag_objects`(auto-insight)는 `datasource_key` 로 **~21개 datasource·8,122 테이블** 커버.

**구현** (metadata_graph.py + app.py + admin.js):
- `sync_graph` step0: **rag_objects 투영**(datasource_key 별 Schema/Table 노드). description=None 으로
  큐레이션 설명 비파괴(table_descriptions 가 같은 key 에 설명 layering). rag_objects 부재 graceful.
- `search_nodes(scope=)` + 신규 `scope_roots(scope)` (datasource 진입 그래프 = Schema→Table 서브그래프, cap).
- API `/api/admin/metadata/graph?scope=` (검색 scope 필터 + scope_roots 모드).
- admin.js 그래프뷰: datasource 선택 시 그 datasource 의 그래프(roots) 즉시 로드 + 검색 scope 격리.
- sync_table description=None 시 미설정(큐레이션 보존). 캐시버스터 bump.

**검증**(throwaway, test_per_datasource_graph.py): per-datasource 투영·scope 격리(dsA/dsB 키 분리)·
HAS_TABLE 엣지·검색 scope·**큐레이션 설명 보존**(rag 투영 무덮어쓰기)·멱등 재sync PASS.
기존 2 모듈 테스트 회귀 0(rag_objects graceful).

## 2026-06-30 · Phase 5 운영 cutover 완료 (사용자 승인 후 실행·검증)

**상태: AGE cutover 라이브 완료.** 사용자 명시 승인("남은 단계 진행 및 검증 완수") 하에 RUNBOOK-cutover.md 따라 실행.

### 실행 (순서대로, 모두 PASS)
1. 백업: `bin/backup.sh` → agent_kb 250M + agent_memory 32M (`artifacts/backups/20260630_154938`).
2. 이미지: `kb-pg-age:pg16` 태그(검증된 AGE 이미지). compose env-var 토글(KB_PG_IMAGE/PRELOAD/REPLICA_PRELOAD, 기본=현행).
3. main 머지: PR #477 → main `0c57e25`.
4. **DB cutover**: `.env` 토글 설정 → postgres·postgres-replica 재생성(AGE 이미지+`shared_preload=...,age`).
   - primary: age preload ✓, **데이터 무손상**(rag_objects=14889, table_descriptions=153), 1s 순단.
   - replica: age preload ✓, streaming ✓, **graph WAL 복제 ✓**, agent_kb_ro Cypher read ✓(pgbouncer-safe).
5. **alembic 0025**(postgres superuser 적용 + stamp): graph=1, labels=13, role search_path 양쪽 적용.
6. worker(ask/insight) 재빌드+재생성 → `bin/metadata-graph-sync.sh` 초기 적재: **153 tables, 0 errors**.
7. web 롤링 재배포(web-a→web-b one-at-a-time, 둘 다 healthy, 무중단). deploy-web.sh 는 본 세션 sandbox 의
   `/tmp` provenance-metadata 이슈로 ABORT(이미지는 정상 빌드) → 수동 health-gated 롤링으로 완수.

### 라이브 검증 (PASS)
- API 라우팅: `GET /api/admin/metadata/graph` → HTTP 401(auth gate, 등록됨).
- 그래프 투영(RO=replica): 실제 게임 테이블 `AccountDB.T_AccountAuth_2`(한국어 설명 포함) 검색 + 34노드 이웃.
- `graph_navigate` AI tool: 등록 ✓, 'AccountAuth' 검색 → 실제 테이블·설명·key 반환.
- 회귀(`make test` 등가): **feature-0016 신규 실패 0건**. route_parity 골든 갱신(+1 route, 정당).
  잔여 4건 `test_attachment_idor` 는 **사전존재**(base c5356a5 동일 실패, 첨부 함수 무관 — feature-0016 무관).

### 잔여 / 후속
- **PB-0008 실제 Windows 브라우저 그래프 UI 검증**: 인프라·API·tool 검증 완료, 시각 렌더는 운영자 브라우저 게이트 권장.
- 엣지 적재: 현 0(게임 DB FK 미선언) — 대화 JOIN 학습·LLM 추론으로 점증. 주기 sync cron 배선(RUNBOOK §4).
- rag_objects(8122 테이블 auto-insight) 그래프 투영 = 후속 enhancement(현 sync 는 curated 메타데이터 153).
- 사전존재 `test_attachment_idor` 4건은 별도 이슈(본 feature 범위 밖).
- 롤백: `.env` KB_PG_* 3줄 제거 + postgres/replica 재생성(관계형 SSOT 무변경). 백업 `20260630_154938`.

## 2026-06-30 · 착수 + Phase 0/1a 검증 (entry persona dispatch)

### 배경 / 결정
- 요청: 관리콘솔 메타데이터(테이블·컬럼 설명) 통합 + 관계 명시(Graph DB) + 그래프 UI·검색 + AI 정합.
- 리서치(4 explore agent + 웹) + 라이브 데이터 조회 → RFC(세션 아티팩트 v2-data-grounded).
- 사용자 결정(2026-06-30): **A3 AGE 즉시 도입 · 한 묶음 · 신규 feature-0016**(0015 선점됨).

### 실데이터 기준선 (라이브)
- 프로덕트 18 · 데이터소스 20(MySQL16/MSSQL4) · 제품DB 195.
- 노드: `rag_objects` 14,889 = 8,122 테이블·91 스키마. 자동 insight `fact_entries` table_insight 14,650.
- **엣지: `table_relationships` 0행** (FK introspection 미실행) — Phase 1c 적재 과제.
- 수작업: `table_descriptions` 153(MSSQL 1소스), columns/glossary/enum 0.

### Phase 0 — 커스텀 AGE+pgvector PG16 이미지 (de-risk) ✅ PASS
- `docker/Dockerfile.pg-age`: `pgvector/pgvector:pg16` + Apache AGE `release/PG16/1.6.0` 소스 빌드 +
  빌드 툴체인 동일 레이어 purge. 이미지 **496MB**, 빌드 ~4분(230s).
- 격리 컨테이너 `verify-age.sql` 검증: **AGE 1.6.0** create_graph + Cypher CREATE/MATCH
  (Table/Column/REFERENCES) + **pgvector 0.8.2**(vector+ivfflat+cosine) + **pg_trgm 1.6**(GIN+similarity)
  공존 회귀 0 = **AC-1 PASS**.

### Phase 1a — alembic 0025 그래프 스키마 + RBAC ✅ PASS
- `20260630_0025_age_metadata_graph.py`: CREATE EXTENSION age + create_graph('metadata_kb') 멱등 +
  **vlabel 6**(Product·Datasource·Schema·Table·Column·GlossaryTerm) + **elabel 7**(USES·HAS_SCHEMA·
  HAS_TABLE·HAS_COLUMN·REFERENCES·RELATED_TERM·DESCRIBES) 사전선언 + role-guarded GRANT. downgrade=drop_graph.
- throwaway 검증: 적용 + **멱등 재적용 OK** + 라벨 13개 확인.
- **RBAC 방어심층**: agent_kb_rw Cypher 쓰기(MERGE node+edge) ✓ · agent_kb_ro 읽기(MATCH) ✓ ·
  agent_kb_ro 쓰기 차단(`permission denied for table Product`) ✓ = **AC-2 부분 PASS**.

### 핵심 인프라 발견 (load-bearing)
1. **`shared_preload_libraries='age'` 필수** — PG 는 비superuser 의 `LOAD 'age'` 를 거부
   ("access to library age is not allowed"). 앱 role(agent_kb_rw/ro)이 AGE 를 쓰려면 서버 preload 필요.
   → Phase 5 cutover 시 postgres·postgres-replica `command:` 에 `-c shared_preload_libraries='age'` 추가
   + 재시작. 앱 코드는 세션마다 `SET search_path = ag_catalog,"$user",public`(LOAD 없이).
2. **create_vlabel/create_elabel 시그니처 = `(cstring, cstring)`** (name 아님). 변수는 `::cstring` 캐스트 필수.
   create_graph 는 `(name)`.
3. 마이그레이션은 AGE 이미지 cutover **이후**에만 적용 가능(현 pgvector 이미지에선 CREATE EXTENSION age 실패).

### 산출물 (worktree)
- `unit/feature-0016-metadata-graph/docs/{FUNCTION,TASK,ANCHOR,REPORT}.md`
- `unit/feature-0016-metadata-graph/docker/{Dockerfile.pg-age,verify-age.sql}`
- `unit/feature-0002-agent-core/alembic/versions/20260630_0025_age_metadata_graph.py`

### Phase 1b — 동기화 + 투영 모듈 (metadata_graph.py) ✅ PASS
- `modules/metadata_graph.py`: 관계형→AGE 동기화(sync_table/column/relationship/glossary/sync_graph) +
  투영(search_nodes·neighborhood). 멱등 MERGE, Cypher injection 방어(`_cq`), 라벨/속성 화이트리스트,
  8K 규모 보호 cap(_NEIGHBOR_NODE_CAP=300, _SEARCH_CAP=80). conn 주입 시 shared.db 미import(단독 가능).
- 라이브 AGE 행위검증(tests/test_metadata_graph_age.py): **ALL ASSERTS PASS**
  {search_orders:3, search_주문:1, nb_nodes:7, nb_edges:9, orders_node_count:1}.
  멱등(3회 재sync 중복 0) · 한국어 · injection escape · k-hop(depth2 REFERENCES 도달) 확인.

### 다음 (Phase 1c~)
- T1.4 `bin/metadata-graph-sync.sh` + insight-worker 주기 훅.
- T1.5/1.6 FK introspection 실행(엣지 적재 — 현 0행) + 대화 학습 + FK 미선언 보완.
- Phase 2 투영 API(app.py 엔드포인트) → Phase 3 Cytoscape UI → Phase 4 AI 정합 →
  Phase 5 측정·**cutover(게이트)**·배포.

## 2026-06-30 (cont.) · Phase 1c→4 순차 구축 (cutover 직전까지)

### Phase 1c — 동기화 파이프라인 ✅
- `scripts/metadata_graph_sync.py`(CLI) + `bin/metadata-graph-sync.sh`(워커 exec) + config
  `AGENT_METADATA_GRAPH_SYNC_ENABLED`(기본 OFF). sync_graph 관계형 read 경로 통합검증 PASS.
- FK introspection·대화학습 = 이미 가동(엣지 0=게임DB FK 미선언, 대화학습으로 점증).

### Phase 2 — 그래프 투영 API ✅
- `GET /api/admin/metadata/graph?q=&node=&depth=&limit=`(app.py, RBAC kb.ingest.manual, _pg_connect_ro,
  graceful). 검색·이웃 모드, cap 강제. py_compile OK. e2e=cutover 후.

### Phase 3 — Cytoscape UI ✅(구조 검증)
- vendor cytoscape 3.30.2 + '🕸 그래프 뷰' 서브탭 + 캔버스 + 통합 엔티티 카드(설명+컬럼+관계+용어) +
  검색(debounce)→투영 API, 노드 클릭→이웃 확장(cose). node --check OK, 요소 5/5. 라이브=cutover 후 PB-0008.

### Phase 4 — AI 정합 ✅
- `graph_navigate` tool(tools.py): read-only search/neighbor, metadata_graph 경유, 플래그 off/AGE 부재 시
  graceful. `_MERMAID_DIAGRAM_GUIDANCE` 에 graph_navigate 추가(대규모 스키마는 subgraph 만 pull). py_compile OK.

### 핵심 발견 2 — pgbouncer transaction-mode 안전성 (Phase 4 검증)
- AGE agtype 연산자(`@>`)는 search_path 로만 해소되고 schema-qualify 불가. pgbouncer 풀링은 세션 SET 을
  잃을 수 있음 → **마이그 0025 에 `ALTER ROLE agent_kb_rw/ro SET search_path = ag_catalog,"$user",public`**
  추가(role 기본값, DISCARD ALL 후에도 유지). 검증: agent_kb_rw 접속 + DISCARD ALL 후 @> 동작 PASS.
- metadata_graph `_cypher` 는 `ag_catalog.cypher`·`ag_catalog.agtype` 정규화 + 방어적 SET 병행.

### 회귀 검증 (adversarial)
- test_metadata_graph_age + test_sync_graph_from_relational 둘 다 fresh 컨테이너 PASS.
  (직전 "dup" 은 T1/T2 컨테이너 공유 + fqn-매칭 단언의 오염 — scope-key 단언으로 견고화, 제품 버그 아님.)

### 검증 상태 요약
- Phase 0·1a·1b·1c·2·3·4 = **격리/라이브 AGE 검증 완료**(worktree-local, 운영 무영향).
- 잔여 = Phase 5 운영 cutover(이미지 교체 + shared_preload + ALTER ROLE 반영 + 마이그 + sync + 재시작 +
  web 재빌드 + PB-0008 + cron). **비가역·외부영향 — 별도 게이트 + 롤백 플랜.** (RUNBOOK-cutover.md 참조)

### 검증 미결 / 리스크
- 이 단계 산출물은 worktree-local 비파괴(운영 무영향). 운영 cutover(이미지 교체+shared_preload+재시작)는
  비가역·외부영향 → Phase 5 별도 게이트 + 롤백 플랜(이미지 revert + drop_graph, 관계형 SSOT 무변경).
- 적대 검증 패널(backend/security/qa)은 Phase 1b 코드 작성 후 수행 예정.

### Post-cutover UX/성능 개선 — graphux3 (2026-06-30)
- **이웃 조회 성능 60x**: AGE 엣지 라벨에 `start_id`/`end_id` btree, vertex 라벨에 `properties` GIN 부재 →
  `(a)-[r]-(b)` traversal 과 `{key:'X'}` 앵커가 전 행 Seq Scan. 측정 Table depth1 **9454ms→151ms**,
  depth2 **18564ms→300ms**, Schema depth1 2673→159ms(Schema depth2 30178→5999ms; schema=compound 라
  클릭 비대상). RO(replica) 경로도 141/264ms — 물리복제로 인덱스 자동 전파(20개 확인).
- **인덱스 영구화**: `metadata_graph._ensure_graph_indexes(cur)` 를 `sync_graph` 시작에서 호출(멱등
  `CREATE INDEX IF NOT EXISTS`, drop_graph 재생성 생존). 인덱스명 = `ix_mkb_<label>_props|start|end`,
  라이브와 정합(`term`→`glossaryterm` 1건 ALTER RENAME, product/datasource GIN 보강). 중복 생성 없음 확인.
- **클릭 동작 분리**(admin.js): 단일 클릭 = `_metaGraphShowDetail`(depth=1 상세 카드만, 그래프 유지),
  더블 클릭 = `_metaGraphExpand`(이웃 그래프 확장/전환, 기존 단일클릭 동작). cytoscape 코어에 dbltap
  부재 → 350ms 윈도우 수동 감지. 힌트/주석/캐시버스터(graphux3) 갱신. node --check·py_compile OK.

### 더블클릭 확장 속도 — graphux4 (2026-07-01, ultracode 3축 조사→적대검증)
사용자 보고 "더블클릭 연결관계 펼치는 속도 느림". 3축 병렬 조사 + 적대 검증(회귀·정합·UX 렌즈)으로 진단:
- **지배 병목=클라이언트 레이아웃**: `_metaGraphLayout` 이 확장마다 fcose `randomize:true`·`quality:proof`·
  `numIter 2500`·`animate 1000ms`·`fit:true` 로 **전체 병합 그래프(루트+신규)를 spectral 재초기화**→기존 노드까지
  재배치·뷰포트 점프(벤더 fcose: `PURE_INCREMENTAL=!randomize`). **수정**: 확장 전용 증분 경로 — 기존 노드
  `fixedNodeConstraint` 고정 + `randomize:false`·`quality:default`·`numIter 400`·`animate 450ms`·`fit:false`,
  신규 노드는 앵커 근처 seed 후 신규 영역으로만 카메라 이동. **초기 로드/검색은 불변**(좌표 없는 재구축이라
  randomize:true 필수 — 검증 blocker: randomize:false 전역화 시 원점 뭉침).
- **서버 쿼리(부차)**: Cypher `MATCH (a)-[r]-(b) WHERE a.key IN [...]` 는 GIN 미활용 Seq Scan(332ms/hop),
  startNode/endNode 방향보존은 3.5x 악화, UNWIND `{key:k}`(변수 containment)는 hang — 실측 확인. **AGE 플래너
  우회 raw graphid id-bound SQL** 로 재작성: key→graphid(`@>` GIN, 파라미터화 injection-safe) → 엣지 라벨
  `start_id/end_id=ANY`(btree) → vertex 라벨 `id=ANY`(pk), UNION ALL 로 왕복 축약. depth2 660→~208ms(3x).
  **방향 버그 동시 해결**: 무방향 -[r]- 이 프론티어 기준 source/target 을 뒤집어 화살표 역전·역중복 엣지를
  만들던 잠재 버그를, start_id=source·end_id=target(물리 방향)+방향정규화 dedup 으로 제거. `ag_label` 앱 role
  권한 없음 → 라벨명은 `_VLABELS`/`_ELABELS` 상수 순회(gid 는 정확히 한 라벨 테이블 소속). 회귀 테스트 추가
  (Table·Column 시작 방향 보존 + 역중복 0). 컬럼 보유 테이블은 depth1 에 컬럼 노출(상세카드 개선).
- **범위 밖(별도 이슈로 보고)**: 형제 테이블 edge-type 필터 제거는 **미채택** — HAS_TABLE 은 이미 비가시
  (compound), 제거 시 노드만 사라지고 컬럼 미투영 99% 테이블 확장이 텅 빔("느림"→"빈 결과"). 데이터 완전성
  갭(REFERENCES=0, HAS_COLUMN 커버 0.78%)은 FK/컬럼 introspect 파이프라인 후속 initiative 로 분리.
