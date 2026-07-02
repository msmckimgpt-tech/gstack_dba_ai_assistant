---
doc_type: FEATURE_DECISIONS
feature_id: feature-xxxx-template
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-001
- Status:
- Date:
- Context:
- Decision:
- Consequences:
- Supersedes:
- Superseded By:

## ADR-002 — 암묵 관계: 정적 confidence ↔ 동적 weight 분리 + 관찰·프로브 하이브리드 자기교정
- Status: Accepted
- Date: 2026-07-01
- Context: 게임 운영 DB 8,122 테이블이 FK 를 거의 선언 안 해 `table_relationships` 엣지가 0. FK 없이도
  "뉘앙스적(암묵) JOIN 관계" 를 파악해 사람·AI 가 쉽게 보되, **암묵 관계라 항상 올바른지 검증**되어 틀리면
  약해져 끊어지고 맞으면 강해져 신뢰로 재구성되어야 한다(사용자 요청). 기존 `confidence` 는 `GREATEST(...)`
  단조 증가라 감쇠·파단이 불가능했다.
- Decision:
  1. 정적 `confidence`(출처 prior)와 동적 `weight`(관찰·프로브로 갱신)를 **분리**. read·주입·그래프는 weight 기준.
  2. FK 미선언 관계를 **명명 규칙 휴리스틱**(name_fk: `<base>_id`→동명 테이블 PK / shared_key: 접두 키 공유)
     으로 추론(source='inferred', status='candidate'). 정밀도는 사후 검증이 보정.
  3. **검증 = 관찰 + 능동프로브 하이브리드**(사용자 결정): (a) 성공한 대화 JOIN 사용 = 양성, (b) insight
     워커가 실데이터 겹침(EXISTS 표본) 프로브로 candidate 를 검증(겹침률 ≥0.5 양성 / ==0 음성).
  4. **비대칭 전이**: 양성 점근 상승, 음성 곱셈 감쇠(더 빠름) → 틀린 관계가 안전하게 빨리 파단(broken).
     w≤0.15 broken(주입·그래프 제외), w≥0.85+양성누적 trusted. **FK 는 권위적 — 강등 불가.**
  5. 스키마 확장은 **비파괴 ADD COLUMN**(alembic 0026)만. 재추론 upsert 는 강화상태 보존(파단 부활 없음).
- Consequences: 그래프가 FK 0 이어도 추정 엣지(점선)로 채워지고, 사용·프로브로 신뢰 엣지(실선)로 승격되거나
  파단(숨김)된다. AI 는 `[추정 w=…]`/`[신뢰]` 태그로 신뢰 수준을 구분해 SQL 정확도 왜곡을 줄인다. 프로브는
  운영 DB read-only(키 컬럼 표본 LIMIT 50, cap)라 부하가 제한적. 라이브 e2e 는 cutover 된 AGE 스택 필요.
- Alternatives:
  - 관찰 기반만(프로브 없음): 추가 DB부하 0이나 미사용 엣지 검증 불가 → 하이브리드 대비 자기교정 느림(기각).
  - 능동 프로브 전수: 가장 엄밀하나 8K 테이블 운영 DB 부하 과다(기각). → candidate 한정 + cap 절충.
  - confidence 재사용(weight 미분리): 단조성 깨면 FK prior 손상 → 정적/동적 분리로 해소.
- Supersedes: (feature-0013 CONFIDENCE 단조 증가 모델을 weight 분리로 확장 — 대체 아님, 상위호환)
- Superseded By:

## ADR-003 — AI 능동 분석 재귀: 앵커-상대 관련도 게이팅(원래 대상 기준 탐색)
- Status: Accepted
- Date: 2026-07-01
- Context: 그래프뷰 "AI 능동 분석" 재귀가 방문 노드의 이웃 **전부**를 무차별 재큐(게이트=depth/node 예산 +
  visited dedupe 뿐)해, 일반 허브 컬럼(예 `UniqueID`)이나 부모 Schema 노드를 만나면 그 노드를 **새 중심**으로
  무관 테이블까지 fan-out 했다(무방향 BFS — 원래 분석 대상에 대한 기억·편향 부재). 사용자 관찰: "대상 노드
  (UniqueID)를 기준으로 다시 탐색". 요구: 처음 분석하려던 대상(예 dk_data_release.Achievement) 기준으로 탐색,
  하위 컬럼은 기본 분석하되 깊은 확장은 "dk 제품·Achievement" 연관 높은 대상으로만, 단순 컬럼명 일치·상위객체
  무연관은 낮은 우선순위.
- Decision:
  1. 재귀를 **원래 루트(anchor)** 에 고정. 후보 이웃을 *현재 노드 인접성*이 아니라 *루트와의 관련도*(0~1)로 채점.
  2. 관련도 신호: **같은 제품(scope)** 강가산/다른 제품 곱셈 감쇠(CROSS_SCOPE_FACTOR) · **루트 테이블 서브트리**
     (같은 테이블 소속) 강가산 · **이름/설명 토큰 겹침**(일반어 stoplist 제외 — id/uniqueid/seq/regdate 등 관용
     컬럼명·구조어는 관련도 불인정) · GlossaryTerm 소폭 · REFERENCES **신뢰**(ADR-002 weight/status). Schema 허브·
     broken 엣지는 0(확장 제외).
  3. **하위 컬럼 기본 분석**: 루트 직속 컬럼(depth 0 child)은 일반명이라도 relevance 1.0 무조건 통과. 그 외는
     관련도 임계 이상만 재귀 — 이웃 depth≥2 는 _DEEP 임계(0.34)로 상향해 허브 재탐색 억제.
  4. **우선순위 영속**: `node_analysis_jobs.relevance`(alembic 0029) 저장 + claim `ORDER BY depth ASC, relevance
     DESC` → node_budget 을 가장 관련 높은 노드에 우선 소비(= "낮은 우선순위로 판단"의 구현).
- Consequences: Achievement 분석 시 (a) Achievement 의 하위 컬럼은 전부 분석되고, (b) 재귀 확장은 dk 제품 안
  Achievement 연관(같은 테이블·이름/설명 연관·신뢰 관계) 대상으로 좁혀지며, (c) 일반 컬럼 UniqueID·부모 Schema
  를 통한 무관 테이블 fan-out 은 차단된다. 임계·감쇠·스키마확장은 env 로 튜닝 가능. 관련도는 휴리스틱이라
  드물게 진짜 연관을 놓칠 수 있어 임계를 보수적으로(낮게) 두고 라이브 관측으로 조정. PG 미가용/앵커 로드 실패
  시 하위 컬럼만 통과하는 안전 저하.
- Alternatives:
  - LLM 로 매 이웃 관련도 판정: 정밀하나 노드마다 추가 LLM 호출 = 비용/지연 폭증(기각). 휴리스틱 스코어로 절충.
  - 하드 depth=1 제한(재귀 사실상 제거): 하위 컬럼만 보고 연관 테이블 미탐 → 사용자 "관련 노드 재귀" 요구 위배(기각).
  - 관련도 비영속(틱 내 정렬만): claim 이 tick 간 SQL 이라 우선순위 유지 불가 → relevance 컬럼 영속 채택.
- Supersedes: (0028 node_analysis 무차별 이웃 재큐 → 앵커 관련도 게이팅으로 확장, 상위호환. 예산 캡·dedupe 유지.)
- Superseded By:

## ADR-004 — 그래프 뷰 렌더링 엔진 교체: Cytoscape(WebGL) → AntV G6 v5(Canvas) + 결정론적 배치
- Status: Accepted
- Date: 2026-07-02
- Context: 관리콘솔 그래프 뷰에서 사용자 관찰 5건 — ① 펼친 테이블 클릭 시 접힘, ② 펼침이 다른 위치서
  일어나고 카메라 점프, ③ 스크롤/줌 시 HTML 오버레이(클러스터명·닫힘버튼)와 캔버스의 갱신 단위 불일치
  (오버레이가 먼저 줌, 나머지 지연), ④ 유사 스키마 클러스터(dk_game_release_*)가 순서 뒤섞여 난립,
  ⑤ 테두리가 크기에 따라 왜곡. 근본원인: ③⑤ 는 이전 커밋의 **WebGL 렌더러**(sprite-atlas 텍스처 스케일링 +
  render 이벤트 미emit 로 오버레이 동기화 불가). Cytoscape 는 리치 노드(닫힘버튼·컬럼)를 네이티브 지원 못 해
  HTML 오버레이 hack 이 강제됐고 이것이 ③ 유발. ①②④ 는 상호작용·fcose 힘배치 로직. 사용자 결정: 엔진 단위
  개선 — 세련된 디자인 + 성능 안정 반응형 UI 를 만족하는 상용/프로덕션급 렌더러 채택.
- Decision:
  1. 렌더러를 **AntV G6 v5.1.1(MIT, vendored UMD `vendor/g6.min.js`)** 로 교체. 후보 비교(yFiles/GoJS/Ogma
     유료·Sigma compound 약함) 중 G6 가 네이티브 Combo(2단 중첩)·리치 노드·멀티 렌더러·폴리시로 요구 최적합·무료.
  2. 렌더러 **Canvas**(벡터·2x DPR) — WebGL 텍스처 왜곡(⑤) 소멸, 모든 줌 선명.
  3. **모델 B(2단)**: 스키마=combo(점선 카드), 테이블=rect 노드(teal 칩), 컬럼=circle 노드, "−"=rect 컨트롤 노드.
     클러스터명·접기컨트롤·컬럼을 **G6 네이티브 요소로 렌더 → HTML 오버레이 전량 제거**(③ 동기화 지연 구조 소멸).
  4. **결정론적 배치**: JS 모델 → `_metaG6Build()`(위치 x/y 포함 전체 데이터) → `graph.setData()`+`draw()`.
     스키마 클러스터 자연정렬 grid + 테이블 세로 스택 + 컬럼 세로열(④ 무-shuffle, ② 제자리 펼침 — 힘배치·점프 없음).
  5. **상호작용**: 단일클릭=상세+테이블 펼침 전용(이미 펼침이면 no-op — ① 해소), "−" 컨트롤만 접기,
     더블클릭(320ms)=이웃 확장. AI 마커=노드 state(보라 analyzed / 주황 running). 점선(candidate)·실선(trusted) 엣지 복원.
- Consequences: 5개 관찰 전부 구조적 해소 + 점선 엣지 복원. 데이터 API(`/api/admin/metadata/graph*`) 불변 —
  렌더/레이아웃/상호작용 계층(admin.js `_metaGraph*`)만 재작성, DOM/API 함수(상세·진행·분석)는 유지. Cytoscape·
  fcose vendor 4종 제거, G6 vendor 1종 추가. 검증: Playwright headless harness(실 admin.html 마크업 + mock API)로
  전 플로우 PASS(roots/제자리펼침/재클릭-무접힘/접기/검색/마커/엣지, 에러 0). 완료 게이트=PB-0008 실 Windows 시각검증.
  설계·함정·POC 는 `../g6-migration/BLUEPRINT.md` + `../g6-migration/poc/`.
- Alternatives:
  - canvas-2D 로만 복귀(Cytoscape 유지): ③⑤ 는 해소되나 오버레이 hack·힘배치 뒤섞임(①②④) 잔존 → 사용자 "엔진 단위" 요구 위배(기각, 부분해).
  - 유료 상용(yFiles/Ogma): 최상급 폴리시이나 라이선스 비용 + G6 가 무료로 요구 충족(보류 — 향후 필요 시).
  - Sigma.js v3(WebGL 초고속): compound/리치노드 약함 → ERD 카드 부적합(기각).
- Supersedes: (graph-webgl 코드결정 — WebGL 렌더러 도입, 정식 ADR 아니었음. 본 ADR 로 대체.)
- Superseded By:


## ADR-005 — 그래프 뷰 테이블 노드 펼침 논블로킹 + O(1) 펼침 인덱스·상태 diff·컬럼 introspect TTL 캐시
- Status: Accepted
- Date: 2026-07-02
- Context: 사용자 관찰 — 관리콘솔 > 메타데이터 > 그래프 뷰에서 **테이블 노드를 선택해 컬럼을 펼치면 브라우저 렌더링 엔진이
  멈춘다**(dead-frozen). 진단: 펼침 임계경로가 (a) `/graph?node=&depth=1` + (b) 미분석 테이블이면 `/graph/columns`
  즉석 introspection(information_schema **라이브 조회 1~5초, 무캐시**) 2왕복을 **요청 스레드 블로킹**으로 돌린 뒤,
  결과를 받아 `setData()`+`draw()`(전체 재구성) — 이 전 구간이 busy 페인트 없이 동기적으로 이어져 메인스레드가 얼었다.
  부수 병목: ① `_metaTableHasCols` 가 매 클릭·토글마다 전 노드 O(N) 선형 스캔, ② `_metaGraphRefreshStates` 가 2.5s
  폴 포함 매 호출 전 노드 개별 `setElementState`(큰 그래프 stutter). 사용자 요청: "병목 구간을 백그라운드에서
  진행되도록 + 별도 성능 이슈 추가 검증."
- Decision:
  1. **논블로킹 펼침/확장 파이프라인**(`_metaGraphToggleColumns`·`_metaGraphExpand`): busy 하이라이트(teal 점선)를
     먼저 칠하고 **double-rAF(`_metaYieldPaint`)로 페인트를 양보**한 뒤 무거운 fetch·재구성을 수행 — 얼음 구간 제거.
     단일 rAF 는 같은 프레임 병합, microtask 는 페인트 미유발이라 double-rAF 채택.
  2. **stale-render 무효화 토큰(`_opSeq`)**: 조작마다 monotonic 시퀀스를 캡처하고 **모든 await(fetch·yield) 경계에서
     대조** — 그 사이 다른 조작·모델 교체가 시작됐으면 그 continuation 을 폐기. **모델 교체(`_metaGraphResetModel`)도
     `_opSeq` 를 올려** in-flight 펼침·확장을 무효화(reset 후 stale ingest 가 화면을 되돌리거나 인덱스를 오염시키는 것 차단).
  3. **O(1) 펼침 인덱스(`colsByTable`)**: Table→펼친 Column 수 Map 을 `_metaTableHasCols` 단일소스로. ingest(증가)·
     collapse(해제)·resetModel(초기화) 세 경로에서만 갱신 → 클릭당 O(N) 스캔 제거.
  4. **상태 적용 diff + batch(`_metaGraphRefreshStates`)**: 마지막 적용 signature 와 대조해 **변화분만** `setElementState`
     + `startBatch`/`endBatch` 일괄. busy 는 `_metaNodeStates` 가 아닌 **`_busyKeys`(소유 op 추적) + `_metaStateSig`**
     로 표현해 rebuild 재-bake·폴 덮어쓰기·캐시 불일치를 원천 차단(_metaApplyState 단일 진입점이 요소 적용과 `_stateCache`
     signature 를 항상 동기화).
  5. **BE `/graph/columns` introspection TTL 캐시**(`admin_metadata.py`): 성공 introspection payload 를
     `(scope_key, fqn)` 키로 짧은 TTL(기본 300s, env `METADATA_GRAPH_COLUMNS_CACHE_TTL`) 동안 **프로세스 내** 캐시 —
     반복 펼침·다중 사용자·재진입의 두 번째 왕복(라이브 information_schema 조회) 제거. **실패/빈 결과는 미캐시**(일시오류
     재시도 보장), DDL 변경은 TTL 만료 후 자동 반영, 상한 512(만료 청소 + 최소-만료 축출). TTL≤0 이면 비활성. 프로세스별
     캐시라 **마이그레이션 불필요**(alembic 병렬 충돌 회피).
- Consequences: 펼침 임계경로가 (1)(2)로 논블로킹화(busy 피드백 + 렌더 프리즈 해소), (5)로 반복 introspection 왕복
  제거, (3)(4)로 클릭·폴당 상수시간 상태 갱신. 데이터 API 계약·그래프 스키마 **불변** — 프론트 렌더/상호작용 계층
  (admin.js `_metaGraph*`) + BE 라우터 캐시 층만. 권한(`Depends(require_permission)`)·스코프 격리 불변(캐시-히트는
  권한 dependency 해소 **이후**, 페이로드는 물리 스키마만). 검증: §18.8 적대 패널(race/index-drift/layout/cache 3렌즈
  + 5-agent 재검증 + reset-vs-reset 후속) — 4+1 BLOCKING 적발·수정·재검증 PASS(REV-20260702T120000). 완료 게이트
  = PB-0008 실 Windows 시각검증(펼침 시 무프리즈 + busy 피드백).
- Alternatives:
  - Web Worker 로 fetch 오프로드: fetch 는 이미 비동기라 얼음의 원인이 아님(원인은 페인트 미양보 + O(N) 스캔 + 무캐시
    introspection). 렌더(setData/draw)는 메인스레드 전용이라 워커로 못 옮김 → 과설계(기각).
  - introspection 결과 DB/Redis 영속 캐시: 크로스-프로세스 공유·영속 이점이나 운영 의존(Redis)·무효화 복잡·마이그레이션
    부담. 펼침 재진입은 **동일 프로세스·짧은 창**이 지배적이라 프로세스-로컬 TTL 로 충분(보류 — 필요 시 승격).
  - busy 를 `_metaNodeStates` 에 포함: rebuild 마다 재-bake 되어 영구 하이라이트로 굳음 → `_busyKeys` 별도 추적(기각).
- Supersedes:
- Superseded By:


## ADR-006 — 그래프 상태 갱신은 per-node setElementState 대신 setData rebuild (테이블 노드 더블클릭 프리즈 해소)
- Status: Accepted
- Date: 2026-07-02
- Context: ADR-005(논블로킹 펼침) 배포 후에도 사용자 관찰 — `mssql-qa-idc.dk_data_release.Achievement`(analyzed, 형제 246테이블 스키마) **더블클릭 시 2~3초 프리즈** 잔존. 실측 진단(헤드리스 harness + web 컨테이너 서버측 계측): (a) AGE 이웃 depth=2 = **135ms**(128노드/127엣지 반환), (b) G6 `setData`+`draw` 200노드+127엣지 = **~200ms**, (c) introspection 은 Achievement 가 analyzed 라 **SKIP** — 즉 fetch·render 는 병목 아님. **진짜 병목**: `_metaGraphRefreshStates` 가 **전 노드마다 `g.setElementState` 를 개별 호출**하는데 G6 v5 에서 이 호출이 **건당 ~50ms**(startBatch 로도 안 배칭) → 실측 **200노드 재적용 = 10,046ms**. 더블클릭 → `_metaG6Apply` 가 `_stateCache` 를 clear → 직후 `_metaGraphSyncAnalysisMarkers`(및 2.5s 폴)가 cold 로 전 노드 재-setElementState = 프리즈.
- Decision:
  1. **rebuild 직후 refresh 를 no-op 화**: `_metaG6Apply` 가 `setData`(build 의 `states:` 로 전 노드 상태 이미 bake) 후 `_stateCache` 를 **clear 만 하지 않고 방금 bake 된 signature 로 populate**. 직후 `_metaGraphRefreshStates` 는 변화 0 → setElementState 0회.
  2. **대량 상태변화는 per-node 대신 단일 rebuild**: `_metaGraphRefreshStates` 는 변화분(sig≠cache)만 모으고, 변화 노드 수 > THRESHOLD(4)면 per-node 루프 대신 `_metaG6Apply(false)` 1회(setData 가 전 상태를 한 번에 bake, fit=false 카메라 유지, ~80–200ms 상수). 소수(≤4)만 per-node.
  3. **폴 tick 이중 refresh coalescing**: `_metaGraphMarkAnalyzed`+`_metaGraphMarkRunning` 이 한 tick 에 refresh 를 2회 부르고 syncMarkers 와도 겹친다 → `_metaGraphRefreshStates` 를 rAF 로 coalesce(같은 프레임 다중 호출 1회 실행) → tick 당 rebuild 1회 + in-flight setData/draw 재진입 방지.
- Consequences: 더블클릭 프리즈 **~9초 → ~0–80ms**(헤드리스 실측: post-rebuild refresh 0ms, bulk 55마커 rebuild 82ms, 구 per-node 200노드 8,890ms). setElementState 사용처는 단일노드(`_metaApplyState`: busy/selected) + refreshStates(변화분/폴백) 둘로 한정. 데이터 API·스키마·마커 시맨틱 불변. §18.8 적대 2렌즈(정확성+프리즈재발) — 상태유실 BLOCKING 0, 폴 이중 refresh 지적 → coalescing 반영. 완료 게이트=PB-0008 실 Windows(대량 스키마 노드 더블클릭 무프리즈).
- Alternatives:
  - G6 setElementState 를 배치 API 로: startBatch/endBatch 로도 건당 비용(상태 attr diff+스타일 재계산 ~50ms)이 안 줄어듦(실측) → setData 경로가 유일한 벌크 최적화(기각).
  - 폴 tick 에서 markAnalyzed/markRunning 의 refresh 를 제거하고 tick 이 1회만 호출: 타 caller(수동 트리거)가 refresh 를 잃음 → rAF coalescing 이 더 견고(채택).
  - THRESHOLD 를 1(항상 rebuild): 단일 selection 변화도 rebuild flicker → 소수는 per-node 유지가 부드러움(기각, 4 채택).
- Supersedes:
- Superseded By:
