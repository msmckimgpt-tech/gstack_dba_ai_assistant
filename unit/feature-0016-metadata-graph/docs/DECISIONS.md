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

## ADR-007 — 관계 자기교정 파이프라인 상시화: 주기 cadence + 스키마-slot 규약(MSSQL=DB명) + config 노출 계약
- Status: Accepted
- Date: 2026-07-02
- Context: 사용자 검증(Achievement 신뢰/추정 관계)에서 파이프라인이 실제로는 미가동임이 실측됨 —
  inferred/trusted 0건. ① `AGENT_RELATIONSHIP_*` 가 config `__all__` 미등재 → star-import 소비자
  insight.py 에서 NameError → per-schema except 가 삼켜 06-29 부터 insight 스키마 처리 전체가 조용히
  정지(인사이트 갱신 포함). ② 훅 발화조건(구조변경/artifact 부재)이 기존 스키마에서 영원히 거짓.
  ③ 대화 학습·MSSQL introspect 의 스키마-slot 이 그래프 Table 키(`db.table`) 규약과 불일치 → AGE
  고아 엣지(그래프 점선 비가시). ④ `_pk_like` 가 게임 DB 관용 PK `UniqueID` 미인식.
- Decision:
  1. **주기 cadence**: `AGENT_RELATIONSHIP_REINFER_SEC`(기본 21600=6h, ≤0 off) — 스키마별
     `relationship_infer_at` kv + `_is_refresh_due` 를 기존 트리거에 OR. FK introspect·추론·프로브가
     같은 게이트(rel_maintenance_due)를 공유, 수행 후 스탬프. 첫 사이클 = 전 스키마 자연 백필.
  2. **스키마-slot 규약 통일 — MSSQL 은 DB(catalog)명**: 저장 라벨과 질의 스키마를 분리
     (introspect_and_store(store_schema=), 추론은 라벨만 사용). 근거: 그래프 Table 키(`db.table`,
     rag_objects object_key 파싱)·column_descriptions(schema_name=DB명, 사용자 결정 06-29)과 정합 —
     'dbo' 리터럴 저장은 고아 엣지. 프로브는 db_scope 로 현재 연결 DB 후보만 + qualifier 제거
     (MSSQL `[db명].[table]` 은 스키마 오해석; 교차-DB 동명 테이블 오검증 차단).
  3. **대화 학습 스키마 해석**: 파서가 SQL 명시 qualifier 보존(3-part=db, 2-part 비-dbo, dbo→'') +
     미qualify 는 `default_schema=get_active_database() or get_active_default_db()`.
  4. **config 노출 계약**: star-import 소비 모듈이 bare 로 쓰는 config 이름은 `__all__` 등재 의무 —
     AST 회귀 가드(test_config_star_export.py)가 봉인. 불변식은 "런타임 해석 가능"(modules/__init__
     주입 공급도 정당).
  5. `_pk_like` 관용 PK 후보에 `uniqueid`/`unique_id` 추가 — 단 heuristic-2(shared_key)에서는
     **제외**(`_GENERIC_KEY_COLS` — 보편 PK 라 PK≡PK pairwise 쓰레기 후보 방지, 'id' 와 대칭.
     적대 패널 B-F3 실행 재현으로 확정).
  6. **(적대 패널 반영, 2026-07-02)** instance-scan interval 커서를 DB(catalog)별 분리
     (`_instance_scan_cursor_key` — B-F1: ds-단위 단일 커서는 MSSQL multi-DB 에서 첫 DB 만 interval
     스캔을 영원히 독점, 본 cadence 목표가 DB#2+ 에서 구조적 미달성이었다). 강화/파단 write-back 도
     스키마-slot 으로 한정(`apply_relationship_signal(a_schema=,b_schema=)` — B-F2: 교차-DB 동명
     테이블 오염 차단, '' 레거시는 wildcard). 프로브 실행오류 중 객체-부재류는 negative 신호 +
     모든 실패에 last_validated_at 전진(B-F4: 실행 불가 edge 영구 미파단·큐 head 고착 차단).
     프로브 cap/sample/timeout 코드 상한 클램프(500/200/60s — Sec-F2). 대화 학습 MSSQL 경로는
     스키마-slot lower() 정규화(QA-F4: KB DB-slot 규약 lower 와 정합, phantom 중복 노드 차단;
     MySQL 은 실행-검증된 타이핑 케이스 보존). 재검증 라운드 반영: 객체-부재 negative 는
     **slot-확정 후보 한정**(R-1 — ''-wildcard×오답 catalog 오파단 차단), 대화 학습 컨텍스트는
     **execute_sql 실행-시점 스냅샷**에서 읽음(R-2 — 1:N 라우터 primary 복원 후 오각인 차단,
     tools.get_last_execute_sql_context).
- Consequences: 관계 추론·검증(ADR-002 자기교정)이 기존 스키마에서도 상시 가동 — 그래프에 추정 점선이
  실 테이블에 붙어 출현하고, 프로브·대화 사용으로 trusted/broken 전이가 실제로 발생. 운영 DB 에
  cadence 당 read-only EXISTS 프로브(cap 40/스키마·5s timeout)가 실발생 — env 로 조절(코드 상한
  500/200/60s). 스키마-slot 규약 변경으로 기존 ''-slot 2행은 1회 데이터 정정(정규화) 필요. insight
  인사이트 갱신 3일 정지의 부수 복구. 대화 SQL 이 잘못된 DB 를 명시하면 그 qualifier 가 저장될 수
  있으나 프로브가 객체-부재 오류를 negative 로 분류해 파단시킨다(자기교정 경로 — B-F4 수정으로 실제
  성립). **알려진 한계(적대 패널, 후속 initiative 범위)**: ① 스키마-slot=DB명 규약은 사실상
  dbo-only 가정 — MSSQL 비-dbo(2-part `sales.T` 대화 학습분)·같은 DB 내 교차-스키마 FK 는 slot 이
  규약과 달라 프로브 db_scope 필터에서 영구 제외(파단도 그래프 연결도 안 됨, QA-F3/B-F5). 현
  운영 DB 군은 dbo 표준이라 실영향 최소 — 비-dbo 도입 시 slot 2-세그먼트 규약 확장 필요.
  ② introspect 테이블명 케이스 플래핑(TASK-0305 실측)은 fqn 충돌키가 case-sensitive 라 중복 행
  가능 — SSOT 레벨 정규화 후속(B-F6). ③ 실효 cadence 는 스키마 window 회전(MAX_SCHEMAS=20)과
  곱해져 91-스키마 기준 ≈ REINFER × ceil(91/20) ≈ 30h (B-F8 — "6h" 는 스키마별 하한 아님).
  ④ 대화학습(LEARNING)을 켜면 프로브(PROBE)도 켜 두어야 한다 — 프로브 off 면 사용자 세공 SQL 의
  거짓 candidate 가 미검증 잔존(Sec-F4; candidate 는 [추정] 태그·w0.4 로 격리되나 자기교정은 프로브가 담당).
- Alternatives:
  - sync cron(metadata-graph-sync)에서 추론+프로브 실행: sync 는 PG 만 접속 — 프로브는 datasource
    연결 인프라(insight worker)가 필요해 기각.
  - 프로브 SQL 을 MSSQL 3-part(`[db].[dbo].[table]`)로 생성: 비-dbo 스키마 테이블 오패스, 연결 DB
    재사용이 더 견고 → db_scope 필터 채택.
  - config star-import 를 명시 import 로 전환(전 모듈): 안전하나 blast-radius 과대(수백 참조) —
    __all__ 계약 + AST 가드로 봉인.
- Supersedes: (ADR-002 의 발화 조건을 상시화로 확장 — 대체 아님, 상위호환)
- Superseded By:


## ADR-008 — 그래프 노드 더블클릭(이웃 확장) 카메라: 즉시 점프 대신 앵커-중심 애니메이션 팬
- Status: Accepted
- Date: 2026-07-02
- Context: 사용자 관찰(프리즈 해소 후) — 테이블 노드 **더블클릭 시 카메라가 순간이동 재배치되어 불편**. 진단: 더블클릭(`_metaGraphExpand`, additive 이웃 확장)은 graph-initview(A3)에서 이미 "전체-fit 대신 앵커 중심 국소 focus"로 바뀌어 있었으나, 그 `focusElement`/`zoomTo` 를 **`animation=false`(즉시)** 로 호출 → 앵커로 카메라가 순간 텔레포트. 사용자가 "카메라 [고정/애니메이션] 자율 판단" 을 위임.
- Decision: **애니메이션(부드러운 앵커-중심 팬) 채택.** 더블클릭 이웃 확장은 모델을 reset 하지 않고(additive) 앵커의 스키마를 `schemaExpanded` 로 펼쳐 앵커를 노드로 렌더한다. 그 앵커로의 `focusElement` 를 `{ duration: 420, easing: "ease-in-out" }` 로 애니메이션. 판독 하한 clamp(`z < _META_MIN_READ_ZOOM → zoomTo(_META_MIN_READ_ZOOM)`)는 **즉시 유지**(팬 애니와 중첩 회피). seq 토큰 가드로 연타 시 stale 카메라 애니 방지.
- 왜 "고정" 이 아닌가: 이웃 확장은 새 노드가 화면 밖 레이아웃 위치에 추가될 수 있어, 카메라를 완전 고정하면 사용자가 방금 더블클릭한 대상·새 이웃이 화면에서 벗어난다. 앵커-중심 focus 는 클릭 대상을 계속 프로미넌트하게 유지하면서(고정의 이점) 전환을 부드럽게(애니의 이점) 한다 — 두 요구의 절충이 "앵커-중심 애니 팬".
- Consequences: 더블클릭 시 카메라가 앵커로 부드럽게 팬(순간이동 제거). `focusElement`/`zoomTo` 는 순수 viewport transform(노드 재렌더 없음)이라 ADR-006 프리즈 수정과 무간섭. 변경 범위 = `_metaGraphExpand` 카메라 블록 1곳(더블클릭 + depth-select 재확장). loadRoots/검색/리사이즈의 즉시 fit(`_metaGraphFitClamped`)과 우클릭 "중심 보기"(`_metaGraphFocus`)는 **불변**(불편 대상 아님). 미렌더 앵커는 `if(fel)` 가드로 focus skip(throw 없음). 완료 게이트=PB-0008 실 Windows(더블클릭 시 부드러운 팬 육안).
- Alternatives:
  - 카메라 완전 고정(무이동): 새 이웃/앵커가 화면 밖일 수 있어 "확장을 봤다"는 피드백 상실(기각).
  - fitView(이웃 전체) 애니: 형제 테이블 다수에 맞춰 줌아웃돼 앵커가 작아짐 — additive 확장에서 이미 A3 가 폐기한 방향(기각).
  - 줌도 애니: zoom-anim + pan-anim 순차는 지연 체감(≈2×) — 팬만 애니, 판독 clamp 는 즉시(채택).
- Supersedes: (graph-initview A3 의 즉시 focus 를 애니로 — 대체 아님, 정제)
- Superseded By: (구현 메커니즘은 ADR-009 로 교정 — 결정 자체는 유지)


## ADR-009 — 카메라 애니 구현: G6 per-call 애니 대신 manual rAF tween (graph config `animation:false` 게이팅 회피)
- Status: Accepted
- Date: 2026-07-02
- Context: ADR-008(더블클릭 카메라 애니) 배포 후 사용자 재보고 — **애니 없이 여전히 순간이동**. 근본원인 실증: 그래프는 `new G6.Graph({animation:false})` 로 생성되는데(graph-g6 가 setData 레이아웃 셔플 방지 위해 의도적 설정), G6 v5 에서 이 **전역 `animation:false` 가 `focusElement`/`zoomTo` 의 per-call `animation` 인자까지 무효화**한다. 헤드리스 실증: 동일 그래프에서 `animation:false`→`focusElement({duration:400})`=2ms(즉시), `animation:true`→412ms(애니). 즉 ADR-008 의 `focusElement(fel, {duration:420})` 는 no-op 였다.
- Decision: 전역 `animation` 을 켜면 setData 레이아웃 셔플(graph-g6 가 제거한 문제)이 재발하므로 그 길은 막혀 있다. `setOptions({animation:true})` 로 focus 직전만 토글하는 방법도 실증했으나(동작함), 그 창(420ms) 동안 폴 `_metaGraphRefreshStates`→`_metaG6Apply` rebuild(setData)가 끼면 레이아웃이 애니(셔플)돼 회귀 위험. → **G6 애니 시스템을 우회하는 manual rAF tween** 채택: `_metaGraphAnimateFocus(key, seq)` 가 앵커 canvas 중심(`getElementRenderBounds`)에서 뷰포트 중앙(`getSize()`/2)까지 client-px delta 를 `getViewportByCanvas` 로 구해, requestAnimationFrame 루프로 이징 누적 `translateBy` 한다. setData 미사용·전역상태 무변경이라 셔플/동시성 무관, seq 로 연타 중단, 미렌더/API 실패는 즉시 focus 폴백.
- Consequences: 더블클릭 시 카메라가 앵커로 실제 부드럽게 팬(순간이동 제거) — ADR-008 의 의도가 비로소 실현. tween 수학이 G6 자체 `focus` 공식과 동일(뷰포트 delta·translateBy zoom-보정)임을 vendored 소스로 확증, 앵커 정중앙 안착(시뮬 오차 ≤1e-13px). §18.8 적대 6축(무한루프·중앙정확·seq/동시성·폴백·줌순서·회귀) BLOCKING 0. NIT 2건(420ms 중 2차 더블클릭+fetch실패 시 카메라 중간잔류 자가치유 / 동시 휠줌 시 정렬 어긋남) 수용. 완료 게이트=PB-0008 실 Windows(부드러운 팬 육안).
- Alternatives:
  - 전역 `animation:true`: setData 레이아웃 셔플 재발(graph-g6 회귀) — 기각.
  - focus 직전 `setOptions({animation:true})` 토글 후 복원: 동작하나 420ms 창의 동시 setData(폴 rebuild)가 셔플 — 전역상태 토글의 경합 위험(기각).
  - G6 per-call `focusElement({duration})`: 전역 animation:false 가 무효화(실증) — no-op(기각, ADR-008 의 잘못된 가정).
- Supersedes: ADR-008 의 구현 수단(focusElement per-call 애니) — 결정(애니 채택)은 유지, 수단만 교정.
- Superseded By:

## ADR-010 — AI 능동 분석 완료 테이블 역할 시각 표식: 8종 고정 분류 + Okabe-Ito 색·아이콘 이중 인코딩
- Status: Accepted
- Date: 2026-07-02
- Context: 사용자 관찰 — 그래프 뷰 노드가 "단순한 사각형+글자" 라 예측 어렵게 나열되어 가시성이 떨어짐.
  요청: **AI 능동 분석이 완료된 노드에 그 테이블이 수행하는 역할을 명시적으로 알 수 있는 시각 표식**을 웹
  리서치 기반으로 검토 후 자율 구성. 기존 분석 산출물({summary,relationships,usage,caveats})에는 역할
  분류 필드 자체가 없어 표식의 데이터 원천이 부재했다.
- Decision:
  1. **분류체계 = 8종 고정(NODE_ROLES)**: master 기준·정의 / account 계정·유저 / transaction 거래·행위 /
     log 로그·이력 / mapping 매핑·연결 / config 설정 / stats 집계·통계 / etc 기타. 근거: 고전 DB 테이블
     분류(master/reference/transaction/history)를 게임 운영 DB 도메인으로 조정 + 범주 색은 7~9종 이하가
     식별 한계(리서치: yFiles 지식그래프 가이드·Tom Sawyer).
  2. **인코딩 = 색+아이콘+범례+텍스트 4중**: 분석완료 테이블 칩 fill=역할색(**Okabe-Ito 8색** — 색약 안전
     표준 팔레트), 라벨 앞 역할 아이콘(📘👤💳📜🔗⚙️📊◽ — 색 지각 불가 환경 중복 인코딩, CatPAW 계열 근거),
     툴바 아래 역할 범례 행, 상세 패널·진행 패널에 역할 한글 라벨 칩. 미분석 테이블은 기존 teal 유지 —
     "역할색 = 분석됨+역할" 신호가 자연 성립(보라 분석완료 테두리는 유지). 밝은 색(account/log/stats)은
     라벨을 어두운 글자로(#161b22, 대비 확보).
  3. **데이터 경로**: LLM 분석 계약(NODE_ANALYSIS_PROMPT)에 `role`(enum) 추가 → worker 가 LLM 값 검증
     (`_role_valid`) 후 저장, 무효/누락은 `classify_role_heuristic`(이름 토큰 1-pass → 분석문 본문 2-pass,
     우선순위 log>stats>config>mapping>account>transaction>master) 폴백. **Table 노드만**(Column/Schema/
     GlossaryTerm 은 NULL). 저장 = `node_analysis_jobs.role`(alembic 0031 비파괴 ADD, §12 사전승인 범위).
  4. **기존 분석분 백필 = 휴리스틱**(LLM 재호출 없음): insight-worker 틱당 200행 `backfill_roles()`,
     'etc' 도 저장해 재선택 없음(멱등·자기 종결).
  5. **FE 반영 = rebuild 승격**: 역할은 G6 state 가 아니라 build 시 bake 되는 style(fill/labelText)이라
     setElementState 로 반영 불가 — 캐시 서명에 `#R=<role>` suffix(`_metaCacheSig`)를 넣어 refreshStates 가
     역할 도착을 감지하면 변화 수와 무관하게 `_metaG6Apply(false)` rebuild(ADR-006 실측 ~80–200ms,
     rAF coalesce)로 승격.
- Consequences: 분석 완료 테이블이 한눈에 역할별 색·아이콘으로 구분되고(범례 대조), 상세/진행 패널에서도
  역할이 명시된다. 분석이 진행될수록 그래프가 "단색 사각형 나열"에서 "역할 지도"로 점진 전환. LLM 은 이미
  호출하던 분석에 필드 1개 추가라 비용 증가 ≈ 0. 알려진 한계: ① 휴리스틱 이름 규칙의 도메인 모호성
  (예: WorldMap 은 게임 지도 정의=master 이나 'map' 토큰이 mapping 매칭 — LLM 값이 우선이라 신규 분석은
  자연 교정, 백필분은 재분석 시 갱신) ② 역할은 노드당 최신 done 잡 기준(재분석 시 갱신) ③ 캔버스 이모지는
  플랫폼 폰트에 따라 단색 렌더 가능(Windows Chrome 은 컬러) — 색·범례가 1차 채널이라 허용.
- Alternatives:
  - 노드 옆 badge pill(색+글자): 세로 스택 밀도(TROW=34px)에서 위 칩과 겹침 + 지면 경쟁 → 칩 fill 교체가
    더 시인성 높고 무겹침(기각).
  - 역할별 노드 모양(shape) 변경: 테이블=rect 칩 형태가 "테이블" 정체성 인코딩이라 유지 — 모양 변경은
    노드 타입(테이블/컬럼/용어) 채널과 충돌(기각).
  - LLM 으로 기존 분석분 전량 재분류: 비용/시간 대비 이득 낮음 — 휴리스틱 백필 + 재분석 시 LLM 교정(기각).
  - role 을 analysis JSON 내부에만 저장(컬럼 없이): scope 일괄 집계가 매 호출 JSON 파싱/캐스트 — 컬럼이
    조회 단순·견고(기각).
- Supersedes: (ADR-004 의 AI 마커(보라 테두리)를 대체하지 않음 — 분석완료 신호 유지, 역할 채널 추가)
- Superseded By:
