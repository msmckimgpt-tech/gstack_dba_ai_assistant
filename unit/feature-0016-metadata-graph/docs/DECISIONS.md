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
- Superseded By: (구현 정제는 ADR-011 — 결정 유지, 지연 제거)


## ADR-011 — 더블클릭 카메라 팬 반응 지연 제거: fetch 전 즉시 시작 + 적응형 follow tween
<!-- 병렬 재번호(§13.1): 최초 ADR-010 으로 작성했으나 상류 main 의 node-role-viz cycle 이 ADR-010 선점 → ADR-011 로 재번호. -->
- Note(재번호): 초기 작성 시 ADR-010, 병합 시 상류 node-role-viz 가 ADR-010 선점하여 **ADR-011** 로 재번호(§13.1). 하위 정본(TASK §34·MODIFY CHG·REPORT·REVIEW·TEST) 참조 동기화됨.
- Status: Accepted
- Date: 2026-07-03
- Context: ADR-009(manual rAF tween) 배포 후 사용자 관찰 — 팬이 부드럽게 되긴 하나 **더블클릭 직후가 아닌 ~350ms 텀을 두고** 시작돼 답답. 원인: 더블클릭(`_metaGraphExpand`)이 팬을 파이프라인 **맨 끝**(busy → `await _metaYieldPaint` → `await /graph?depth=2` fetch(~135ms+) → ingest → `await _metaG6Apply(false)` setData+draw(~200ms) → **그제서야** `await _metaGraphAnimateFocus`)에서 시작. 앵커(클릭 노드)는 이미 렌더돼 있는데 fetch·rebuild 를 기다린 뒤 움직임.
- Decision: 두 가지를 함께 적용.
  1. **fetch 전 즉시 시작(fire-and-forget)**: `_metaGraphExpand` 가 busy 페인트 직후, fetch/rebuild 를 await 하기 전에 `_metaGraphAnimateFocus(key, seq)` 를 await 없이 호출 → 팬이 클릭 즉시 시작. 파이프라인 끝의 await 호출은 제거(중복 tween 방지).
  2. **적응형 follow tween**: 고정-duration(delta 1회 캡처) 대신 매 프레임 앵커의 **현재** 뷰포트 위치를 재조회해 뷰포트 중앙까지 잔여 delta 의 K(0.24)만큼 translateBy(ease-out). fetch·rebuild 로 앵커가 이동/재생성돼도 최종 위치로 수렴. 종료 = 수렴(<1.2px) / seq 폐기 / MAXMS(1200ms) 단일 시간상한(프레임카운트 조기포기 없음 — 저사양 rAF 탈동조 대비). W/H 매 프레임 재조회(팬 중 리사이즈 대응). API 부재 번들은 focusElement 즉시 폴백.
- Consequences: 더블클릭↔팬 시작 사이 ~350ms 텀 제거(즉시 반응). rebuild 동안 앵커가 이동해도 follow 가 최종 위치로 매끄럽게 수렴(헤드리스 실증: 중간 setData 이동 후 24프레임에 중앙 안착). §18.8 적대 7축(종료·동시성·이동수렴·fetch실패/seq·미렌더·회귀·K/임계) BLOCKING 0; MEDIUM(missStreak 조기포기)→제거, NIT(API폴백·W/H 스테일)→반영. 카메라 transform 만(ADR-006 프리즈 무관). 완료 게이트=PB-0008 실 Windows(더블클릭 즉시 부드러운 팬).
- Alternatives:
  - rebuild 후에만 팬 시작(기존): 앵커 이미 렌더인데 대기 → ~350ms 텀(기각).
  - 고정-duration tween 을 즉시 시작: rebuild 로 앵커 이동 시 캡처한 delta 가 스테일 → 빗나감(기각 — 적응형 follow 필요).
  - missStreak 프레임카운트 조기포기: rebuild 프리즈로 rAF 탈동조돼 저사양서 팬 조기중단(텀 재발) → 제거, MAXMS 단일상한(채택).
- Supersedes: ADR-009 의 팬 시작 시점(rebuild 후 await) + 고정-duration — 결정(manual tween 애니) 유지, 지연·적응성 정제.
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

## ADR-012 — 그래프 뷰 관계 기반 배치: greedy seriation + 컴포넌트 군집 + barycenter sweep (force 레이아웃 재도입 기각)
- Status: accepted (2026-07-03)
- Context: 관계(REFERENCES)가 쌓일수록 그래프 뷰 가시성이 저하된다는 사용자 보고. 원인은 배치가 관계를
  전혀 반영하지 않는 것 — 스키마 클러스터는 자연정렬 shelf-packing, 클러스터 내 테이블도 자연정렬 masonry
  라서 연결된 노드가 화면 반대편에 흩어지고 엣지가 장거리 교차를 양산한다. 교차 최소화는 NP-hard 라
  휴리스틱이 표준이며, ADR-004 가 확립한 결정론 grid(무-shuffle·펼침-불변) 불변식을 깨지 않아야 한다.
- Decision: `_metaG6Build` 의 **순서 입력만** 관계 가중치의 순수 함수로 교체(배치 기하·게이팅·masonry 는
  불변). 3단 휴리스틱:
  1. **스키마 seriation**(greedy attachment): 스키마쌍 관계 가중 합 기준, 배치 집합과 가장 강하게 연결된
     스키마를 반복 선택 → 연결 스키마가 shelf 순서상 인접(교차 엣지 단축). 무관계 스키마는 자연정렬 후미.
  2. **클러스터 내 군집**: 스키마 내부 관계의 연결 컴포넌트를 BFS(간선 가중 내림차순)로 이어 붙임 —
     masonry Pass1 이 균등높이 최단열(행 우선)이라 순서 인접 = 화면 인접.
  3. **barycenter 4-sweep**: 각 테이블을 이웃(내부+외부)의 전역 위치(gpos = schemaIdx + 로컬 rank, SPAN=1)
     가중평균 순으로 재정렬 — 나란한 두 클러스터 사이의 상호 교차(a↔d, b↔c)를 푸는 층별 표준 휴리스틱.
  유사도 = 관계 수 × 신뢰 가중(trusted=2, candidate/기타=1). 관계 0 이면 결과가 기존 자연정렬과 완전 동일.
- Consequences: 합성 벤치(시드 3종 × 랜덤/허브 토폴로지 6구성)에서 2D 세그먼트 교차 12~30% 감소, 1D 층간
  역전 59→52. 배치가 (nodes, edges)의 순수 함수라 결정론·펼침-불변(ADR-004 ②) 유지 — schemaExpanded 를
  읽지 않는다. 관계 데이터가 새로 로드된 rebuild 에서만 순서가 변하며(사용자 요청 "관계가 확보될수록 기준
  배치"의 구현), 이는 기존 "shelf 재배치 대비 시야 고정(무애니)" 경로가 흡수한다. 계산 비용 O(4·(N log N + E)) —
  수천 노드에서 ms 단위(마이크로 벤치 확인). 알려진 한계: 전역 최적 아님(휴리스틱), 2D 교차의 1D 순서 근사.
- Alternatives:
  - **force-directed(d3-force/G6 force) 재도입**: 관계 기반 배치의 정석이나 ADR-004 가 기각한 셔플·비결정론
    ·클러스터 뒤섞임을 재유발(BLUEPRINT §2 divergence 주석의 회귀 방지 대상) — 기각.
  - **SPAN=4096(스키마 원거리 지배 barycenter)**: 벤치에서 같은 스키마쌍 엣지들의 상호 정렬이 무너져 1D
    역전이 되레 증가(59→74) — 기각(SPAN=1 이 6구성 중 5 최선).
  - **G6 내장 layout(dagre 등) 위임**: combo(스키마 카드)·masonry·카드 게이팅과 비호환, 결정론 보장 없음 — 기각.
  - **엣지 곡선/번들링만으로 완화**: 배치가 그대로면 장거리 교차 자체가 남음 — 배치 우선, 곡선은 후속 옵션.
- Supersedes: (ADR-004 의 "자연정렬 grid" 순서 부분만 대체 — 결정론 grid 골격·불변식은 계승)
- Superseded By:

## ADR-013 — 그래프 뷰 유사 속성 그룹: 이름 affix family 휴리스틱 + 가시적 영역(배경 박스) 렌더 (백엔드 시맨틱 클러스터링 이연)
- Status: accepted (2026-07-03)
- Context: graph-rel-layout(ADR-012)이 관계 기반 '순서'는 만들었으나, 균일 칩의 평면 나열이라 군집이
  화면에서 '영역'으로 읽히지 않는다는 사용자 후속 보고("유사한 속성끼리 배치 + 속성 범위가 가시적으로").
  라이브 데이터 특성: 게임 DB 는 구분자 없는 소문자 연접 테이블명(charactercurrency, cashshopnewitem)이
  지배적이고, FK 미선언이라 관계는 부분적이며, 역할(role)은 AI 분석 완료 노드에만 존재한다.
- Decision: 클라이언트 순수 함수 3-신호 그룹핑 + 그룹 블록 렌더.
  1. **이름 affix family(1차)**: 정규화(소문자·view_ 제거) 이름의 접두/접미 토큰(4~16자) 중 지원도(공유
     테이블 수) ≥2 에서 지원도×길이 최대 토큰을 family 로. 구분자 없는 연접 이름에서 동작하는 유일한
     실용 신호가 공유 affix — underscore/camel 분할은 무력. 라벨은 멤버 실명의 최장 공통 접두/접미
     (자연 스템) + 방향 말줄임(`character…`/`…shop`).
  2. **관계 attach(2차)**: family 없는 테이블은 관계 가중 최대 family 로 1-pass 부착(무연쇄 — 블롭 방지).
  3. **역할 family(3차)** → **기타(후미 고정)**. 싱글턴 named family 는 흡수(1개짜리 박스 노이즈 방지).
  렌더: 그룹 = 배경 박스(연틴트 8종 순환, zIndex -2) + 헤더 칩(`라벨 · n`) — "범위의 가시화". 그룹 내부
  1~3열 2-pass masonry(Pass1 collapsed 배정=펼침-불변 / Pass2 실높이 push-down, ADR-004 ② 계승) + 블록
  shelf-pack(행 배정=폭, 행 y=실높이). 그룹 순서/그룹 내 순서는 ADR-012 의 seriation·barycenter 를
  "컨테이너=그룹" 으로 재사용. 그룹 <2 스키마·terms 는 기존 평면 masonry 그대로(회귀 0).
- Consequences: 스키마 클러스터가 "균일 칩 나열" → "라벨 붙은 유사 속성 영역들"로 읽힌다. 클러스터 상세
  목록도 동일 그룹 헤딩으로 정합. 실측(gunzgame 68 테이블·145 관계): character(14)·item(17)·characterinfo(4)·
  battletimereward…(4)·…shop(3)·mission(4)·clanmember(3) 등 13 그룹 + 기타(2), 빌드 5.1ms. 알려진 한계:
  ① affix 휴리스틱은 시맨틱 임베딩이 아니다 — 컬럼 시그니처·설명 임베딩 기반 백엔드 클러스터링은 별도
  initiative(이연 사유: 서버 계산·저장 스키마 필요, 프론트만으로 즉시 가치 전달 우선) ② 역할 도착·관계
  증가 시 rebuild 에서 그룹이 재편될 수 있음(기존 role-chip rebuild 관용구와 동일 흡수) ③ 관계 attach 된
  멤버는 그룹 라벨과 이름이 다를 수 있음(의도 — 관계 소속).
- Alternatives:
  - **백엔드 시맨틱 클러스터링(임베딩·컬럼 시그니처)**: 정확도 최상이나 서버 계산/저장/동기화 필요 —
    후속 initiative 로 이연(본 ADR 의 그룹 렌더 계층은 재사용 가능).
  - **G6 중첩 combo(그룹=combo-in-combo)**: G6 v5 중첩 combo + 수동 좌표의 상호작용이 미검증(ADR-004
    setData diff 취약점) — 장식 rect 노드가 저위험·결정론(기각).
  - **역할(role)만으로 그룹핑**: 라이브 대부분 미분석(role 부재) — 커버리지 부족(보조 신호로만).
  - **underscore/camelCase 토큰화**: 연접 소문자 이름에서 무력(기각 — affix 가 상위 호환).
- Supersedes: (ADR-012 의 순서 계층은 그룹 내부/그룹 간 순서로 계승 — 대체 아님)
- Superseded By:

## ADR-014 — 그래프 뷰 제품(Products) 단위 카테고리: 투영 API 질의시점 합성(AGE 미저장) + 제품 개요 랜딩
- Status: accepted (2026-07-03)
- Context: 사용자 요청 3대 개선 中 A — "구분해둔 제품(Products)에 따른 카테고리 단위로 구분". 실측: 그래프 모델은
  `Product`/`Datasource` 라벨·`USES` 엣지를 **예약만** 하고 `sync_graph` 는 실제로 Schema→Table→Column+REFERENCES
  만 투영한다. scope 선택은 datasource 단위뿐이고, Product 노드가 온다 해도 프론트가 `_META_TERMS_COMBO`("용어·기타")로
  흘려 카테고리 컨테이너가 되지 못한다. Product↔Datasource SSOT(`WebProducts`·`WebProductDatasources` N:M·
  `WebProductDatabases`)는 MySQL(web-ui runtime)에 완비. 그래프(AGE)는 Postgres `agent_kb` — 두 스토어가 분리.
- Decision: 제품 카테고리를 **투영 API 계층(web-ui, MySQL 접근)에서 질의시점에 합성**한다. AGE 에 Product/Datasource
  정점을 물리 저장하지 않는다.
  1. **백엔드**: `GET /api/admin/metadata/graph?mode=products`(전체) · `?product=<id>`(단일) → `_product_overview_graph`
     가 MySQL SSOT 로부터 `Product`(key=`product:<id>`)·`Datasource`(key=`ds:<scope_key>`) 노드 + `USES` 엣지 합성.
     datasource-scoped 진입(scope_roots/schemas) 응답에 `_products_for_scope` 로 소속 제품(`products`) 첨부(배너).
  2. **프론트**: `_metaG6BuildProducts` 전용 2-열 결정론 배치(Product 좌·Datasource 우, USES 엣지, combo 미사용 —
     기존 스키마 masonry 무간섭). 그래프 진입 랜딩(공용/미선택)을 제품 개요로 전환. Datasource 노드 클릭 → 그
     데이터소스 스키마 그래프로 drill(scope 전환), Product 노드 클릭 → 단일 제품 focus. 툴바 "🗂 제품 카테고리" 버튼.
  3. **read-axis 정렬(불변식)**: datasource 그래프 scope 는 `admin_datasources` 가 노출하는 read 축
     `scope_key or key`(DB-등록=엔드포인트 해시, .env 레거시=라벨)와 **반드시 일치**한다. `shared.datasources.scope_key`
     (.env 도 해시 계산)를 쓰면 어긋나 빈 그래프를 부르므로 **금지**(REV-20260703T091737 MAJOR).
- Consequences: 그래프 뷰가 "데이터소스 나열" → "제품(카테고리)→데이터소스 계층"으로 진입한다. **DB 스키마 변경·마이그
  레이션 0**(합성은 read-only, AGE 투영 로직 불변), 권한 `metadata.graph.read` 보존, mutation 0. 후속 Phase C(의미
  임베딩)·B(크로스-데이터소스 관계)가 이 제품 경계를 재사용할 수 있다(제품=관련 데이터소스 묶음). 한계: 개요는 제품→
  datasource 2계층까지(스키마/테이블은 drill 후 기존 뷰); 제품별 통합 스키마 union 뷰는 미도입(후속 여지).
- Alternatives:
  - **AGE 에 Product/Datasource 정점 물리 저장(sync_graph 확장)**: FUNCTION.md 모델 의도엔 부합하나 MySQL→Postgres
    브리지 sync 경로·이중 정합·마이그레이션 필요. 질의시점 합성이 "projection(진실의 사본)" 원칙에 더 정합하고 즉시
    가치(비파괴). AI 컨텍스트가 Product 노드를 그래프에서 탐색해야 하는 요구가 서면 그때 승격(후속).
  - **공유 scope select 에 제품 옵션 추가**: scope select 는 그래프+비그래프 메타데이터 뷰가 공유 → `product:` 값이
    list/bootstrap 경로를 오염. 툴바 버튼 + 랜딩 전환으로 분리(select 는 datasource 전용 유지).
- Supersedes:
- Superseded By:

## ADR-015 — 그래프 뷰 자유 배치 상호작용 persistence(결정론 배치 위에 사용자 드래그 offset 레이어)
- Status: accepted (2026-07-03)
- Context: 사용자 회귀 보고 — 데이터소스 스키마 클러스터 화면에서 "분류 접기/펼치기·분류 drag&drop 위치 이동·분류 내부
  노드 이동 반응형 크기 조정"이 사라짐. 조사(git bisect): 마지막 정상(abc78b00 graph-simgroups, T42.8 PASS) 이후 admin.js
  변경은 ds-avg-latency(데이터소스 상세 패널 전용)·graph-product-cat(제품모드 전용) 2건뿐 — **둘 다 클러스터 상호작용 코드
  미변경**. 근본원인은 ADR-004 **Cytoscape→G6 결정론 배치**(매 rebuild `setData+draw` 로 위치 재계산) 전환이 Cytoscape 시절
  자유 배치(드래그 위치 유지·노드이동 리사이즈)를 이관하지 않은 것(graph-drag T41 은 세션 내 테이블 드래그만 추가, persistence 부재).
- Decision: 결정론 배치를 유지하되 그 **위에 사용자 드래그 offset 레이어**를 얹어 자유 배치를 persistence 한다(둘의 정합).
  - **clusterOffset**(comboId→{dx,dy}): 클러스터(combo) 또는 접힌 카드 드래그의 누적 델타. build 가 shelf-packing 후
    L.x0/L.y0(카드·테이블·컬럼·장식·combo 공통 기준)에 가산 → 클러스터 전체 coherent 이동, 펼침/접기 후 유지.
  - **nodePos**(nodeId→[x,y]): 개별 테이블/용어 드래그의 절대 위치(center 프레임 = build tx/ty). build place-loop 이 델타로
    테이블+종속(컬럼·"X:" ctl) 시프트. combo 는 명시 size 없이 자식 auto-fit → **노드 이동 시 반응형 리사이즈**(#3).
  - 접기/펼치기(#1): 기존 SC:↔combo 유지. 위치는 스코프 전환·초기화(resetModel)에서 리셋, 펼침/접기 rebuild 에선 유지.
  - **정합 불변식**: 클러스터를 통째로 옮기면 소속 nodePos 도 동반 가산(절대좌표가 clusterOffset 를 덮어써 개별노드가
    분리되지 않게 — REV-20260703T101622 MAJOR).
- Consequences: ADR-004 의 "결정론 배치(무-shuffle·제자리)" 는 **초기/rebuild 기본 배치로 유지**되고, 사용자가 명시적으로
  드래그한 것만 offset 로 덮어쓴다(force layout 재도입 아님 — ④ 클러스터 뒤섞임 회귀 없음). 프론트 전용·마이그레이션 0.
  한계(수용): 검색은 자유배치 리셋(model 교체), 펼친 그룹 스키마 combo 드래그 표면 얇음(접힌 카드 드래그가 주 경로),
  카드 드래그 offset 은 펼침 시 변위만 유지(결정론 재packing 본질). 라이브 canvas 드래그 자동화 곤란 → PB-0008 수동 게이트.
- Alternatives:
  - **Cytoscape 로 롤백**: ADR-004 가 해소한 5개 관찰 결함(클릭접힘·위치점프·줌지연·클러스터뒤섞임·테두리왜곡) 재발 — 기각.
  - **force layout 재도입**: ④ 클러스터 뒤섞임 재유발(ADR-004 기각 사유) — 기각. offset 레이어가 결정론 유지하며 자유배치 제공.
- Supersedes: (ADR-004 의 결정론 배치를 대체하지 않음 — 그 위에 opt-in offset 레이어 추가)
## ADR-016 — 함수·프로시저 노드: routine_objects SSOT + AGE Routine 라벨 + INFORMATION_SCHEMA 공통 경로 + 정의 파싱 참조
- Status: Accepted
- Date: 2026-07-03
- Context: 사용자 요청(REQ-20260703-graph-funcproc-uxfix ①) — 그래프 뷰에 **함수 & 프로시저 노드**를
  구성하고 분석·관계도 구성. 기존 그래프는 Table/Column/GlossaryTerm 만 다뤄 DB 의 코드 객체(프로시저·
  함수)가 완전히 비가시였다 — 게임 운영 DB 는 지급/정산 로직이 프로시저에 있는 경우가 많아 "이 테이블을
  누가 읽고 쓰는가"의 큰 축이 빠져 있었다.
- Decision:
  1. **SSOT = 신규 관계형 `routine_objects`**(alembic 0034, 비파괴 추가) — AGE 는 투영(FUNCTION §4.3
     원칙 불변). insight-worker 가 관계 유지보수 게이트(rel_maintenance_due, ADR-007 cadence)에서
     `INFORMATION_SCHEMA.ROUTINES/PARAMETERS`(MySQL·MSSQL **공통 뷰**)를 조회해 upsert(`modules/
     routines.py`). 반환형은 방언별 컬럼이 갈려(MySQL DTD_IDENTIFIER vs MSSQL DATA_TYPE) PARAMETERS
     의 ORDINAL_POSITION=0(공통 규약)에서 얻는다. 스키마-slot 은 ADR-007 규약(MySQL=schema/MSSQL=DB명,
     store/query 분리). 변경 없는 행은 updated_at 불변(IS DISTINCT FROM 가드 — 증분 sync 정합).
  2. **참조 테이블 = 정의 텍스트 보수적 파싱**: FROM/JOIN(read)·INSERT INTO/UPDATE/DELETE FROM/
     MERGE INTO(write) 뒤 식별자를 leaf 정규화해 **그 스키마에 실재하는 테이블만** 채택(임시 #·변수 @·
     미존재·자기자신 제외, 테이블당 1 entry — write 우선). MSSQL 정의는 4000자 절단본이라 부분 커버
     수용(정확도보다 안전 우선).
  3. **그래프 모델**: vlabel `Routine`(props: routine_type function|procedure, params) + elabel
     `HAS_ROUTINE`(Schema→Routine)·`ROUTINE_USES`(Routine→Table, relation_type read|write).
     key/fqn = `schema.name()` — 뒤의 `()` 가 동명 테이블 키(`schema.name`)와의 전역 key 충돌을 막는
     네임스페이스(GlossaryTerm `term:` prefix 와 동형 발상)이자 사람이 읽는 함수 표기. 참조 Table 은
     최소 MERGE 앵커링(고아 엣지 방지 — _anchor_relationship_column 동형).
  4. **노출**: schema_tables 가 Routine+ROUTINE_USES 를 함께 반환(클러스터 펼침 시 테이블과 나란히
     ƒ/⚙ 보라 칩 #7b5cd6, 사용 엣지=보라 잔점선) · 검색(routine_type 포함) · 상세 패널(유형·파라미터·
     사용 테이블/사용 루틴 상호 이동) · AI 능동 분석(ROUTINE_USES = content 신호 0.35, NODE_ANALYSIS_PROMPT
     에 Routine 라벨 계약 추가).
- Consequences: 프로시저/함수가 스키마 클러스터 안에 테이블과 나란히 출현하고, 어떤 테이블을 읽고
  쓰는지가 그래프·상세·AI 분석에서 관측된다. introspection 은 read-only + 스키마당 cap
  (`AGENT_ROUTINE_INTROSPECT_CAP` 300) + cadence 게이트라 부하 제한적. 알려진 한계: ① 정의 접근 권한
  부재 시 ROUTINE_DEFINITION NULL — 노드는 생기고 참조만 빈다(graceful). ② 동적 SQL(EXEC(@s))·절단
  정의의 참조는 누락 가능 — MSSQL sys.sql_expression_dependencies 승격은 후속. ③ routine→routine
  호출(EXEC) 관계는 v1 범위 밖. ④ ROUTINE_USES 엣지는 양끝이 렌더된 경우만 표시(접힌 스키마 카드로의
  승격은 후속).
- Alternatives:
  - rag_objects 에 object_type='routine' 편입: 기존 object_type='table' 가정 소비처(그래프 sync·검색·
    insight)의 blast-radius 큼 + referenced_tables/params 필드 부재 → 전용 테이블(기각).
  - 라벨 2개(Function/Procedure): 화이트리스트·색·범례 2배 — routine_type 속성 1개가 단순(기각).
  - MSSQL sys.sql_expression_dependencies: 정확하나 방언 분기 확대 — v1 은 공통 뷰 단일 경로, 정확도
    요구 확인 후 승격(보류).
- Supersedes:
- Superseded By:

## ADR-017 — AI 능동 분석 정제: 참조 컬럼의 부모 테이블 same-depth 승격 + hover 지침(user_prompt) 주입 + '재분석' 제거
- Status: Accepted
- Date: 2026-07-03
- Context: 사용자 관찰 3건(REQ-20260703 ③④⑤). ③ 앵커 게이팅(ADR-003) 이후, 재귀가 참조 **컬럼**까지는
  분석하지만 그 컬럼의 **소속 테이블**은 이름·설명이 앵커와 무관하면 content=0 으로 탈락 — "컬럼은
  분석됐는데 그 부모 테이블은 미분석"인 어색한 절단(예: Achievement.ItemID→ItemMaster.ItemID 컬럼은
  분석, ItemMaster 테이블은 미분석). ④ 분석 완료 box 의 '↻ 재분석' 버튼은 헤더 '✨ 능동 분석' 재실행과
  중복(UX). ⑤ 분석 의도를 전달할 입력이 없어 항상 같은 관점의 분석문만 생성.
- Decision:
  1. **부모 테이블 same-depth 승격**: 분석되는 노드가 Column 이면 그 HAS_COLUMN 부모 Table 을 임계와
     무관하게 승격 enqueue — 관련도는 고정 0.5(교차 제품은 CROSS_SCOPE_FACTOR 감쇠, env
     `AGENT_NODE_ANALYSIS_PARENT_TABLE_REL`), **depth 는 컬럼과 같은 층**("소속"은 추가 hop 이 아니다 —
     depth_budget 마지막 층 컬럼의 테이블도 분석됨). 그 테이블의 *다음* 확장은 여전히 앵커 게이팅이
     막아 재귀 심화를 억제(사용자 요구 "테이블까진 분석하되 너무 깊어지진 않게"의 구현). node_budget·
     dedupe(UNIQUE run_id,node_key) 불변.
  2. **'재분석' 제거**: box 의 '↻ 재분석' 버튼·ctxmenu 'AI 재분석' 라벨 삭제 — 능동 분석 재실행이 곧
     재분석(단일 진입점).
  3. **hover 지침**: '✨ 능동 분석' 버튼 hover 시 툴팁형 입력(≤400자, Esc 닫기·Ctrl+Enter 시작) →
     `analyze POST prompt` → `node_analysis_runs.user_prompt`(alembic 0034) 저장 → (a) **앵커 토큰에
     합류**(관련도 채점이 지침 어휘를 따라 재귀 방향에 반영) + (b) LLM payload `user_intent` 주입
     (NODE_ANALYSIS_PROMPT 에 "분석 관점으로 자율 반영하되 출력 계약·데이터 불변" 가드 명문화 —
     사용자 요구 "llm의 자율적인 판단 하에" 정합). 진행 중 run 재사용 시 새 지침은 무시(앞뒤 분석문
     관점 혼합 방지). 마이그 창(컬럼 부재)은 role(B1) 동형 legacy 폴백 + 1회 경고.
- Consequences: 참조 컬럼이 분석되면 소속 테이블도 같은 run 에서 분석돼 "테이블까지" 완결되고, 무관
  fan-out 은 앵커 게이팅·예산이 그대로 차단. 지침 입력 시 재귀 방향·분석문이 사용자 의도를 따른다
  (soft 신호 — 강제 아님). UI 는 버튼 1개로 단순화. 알려진 한계: 승격은 Column→Table 1단만(Schema
  허브 차단 불변). audit 에는 prompt_len + 120자 preview 만 기록.
- Alternatives:
  - depth+1 로 부모 enqueue: depth_budget 마지막 층에서 여전히 탈락 — 사용자 관찰 그대로 재발(기각).
  - 관련도 상속(컬럼 rel×계수): claim 쿼리에 rel 반환 추가 필요 + 깊을수록 0 수렴해 승격 실패 —
    고정값 + 교차 제품 감쇠가 단순·예측 가능(기각).
  - 지침을 노드 필터로 강제: LLM 자율성 상실 + 빈 결과 위험 — soft 신호(토큰 합류 + user_intent)로
    절충(기각).
- Supersedes: (ADR-003 게이팅에 승격 예외 1종 추가 — 대체 아님, 정제)
- Superseded By:

## ADR-018 — 메타데이터 객체 의미 임베딩·클러스터링 (Phase C, ADR-013 후속 initiative 이행)
- Status: accepted (2026-07-03)
- Context: ADR-013 이 "affix 휴리스틱은 시맨틱 임베딩이 아니다 — 컬럼 시그니처·설명 임베딩 기반 백엔드 클러스터링은
  별도 initiative(서버 계산·저장 스키마 필요)"로 이연한 후속 과제. 사용자 3대 개선 中 C. 임베딩 인프라는 이미 완비
  (texts 저장소·bge-m3 1024d·embedding 데몬·pgvector HNSW)이나 **메타데이터 객체(테이블/컬럼)는 미임베딩**.
- Decision: 결정론 배치·affix 위에 **서버측 의미 클러스터 신호**를 additive 로 얹는다.
  1. **시그니처 임베딩(재사용)**: 테이블별 시그니처 텍스트(이름+설명+정렬 컬럼명+역할/도메인, DB-distinct=object_key
     effective schema 포함)를 기존 `texts` 저장소에 적재(dedup by sha256) → **기존 embedding 데몬이 자동 임베딩**
     (신규 embedding 경로 0, ADR-0021 "one embedding per text_hash" 계약). rag_objects 에 `signature_text_hash`
     (texts join 키·변경감지) 컬럼. **write-key=join-key 정합**: `_text_hash(sig.strip())`(리뷰 MAJOR-1 — 컬럼 없는
     테이블 trailing space divergence 방지).
  2. **저장(비파괴, alembic 0035)**: rag_objects 에 `signature_text_hash`·`semantic_cluster_id`·`semantic_cluster_label`
     3 nullable 컬럼 + 인덱스 2개. category_* denormalization 과 대칭(신규 테이블 회피 — 0017/0028 GRANT trap 회피).
  3. **클러스터링(insight-worker 데몬 스레드)**: scope(scope_key,datasource_key)별 kNN(코사인 τ)+union-find 단일연결.
     노드당 이웃 상한(MAX_DEGREE)로 chaining 억제(리뷰 MAJOR). numpy N×N(FULLMATRIX_MAX_N 이하), 초과 scope 는
     skip→affix 폴백(OOM 가드, 리뷰 MINOR). cluster_id=멤버 min(object_key) 순 결정 배정. 6h cadence(PG kv).
  4. **투영·프론트**: sync_table/sync_graph 가 클러스터를 AGE Table 정점에 실어 scope_roots/schema_tables 가 RETURN
     (`cluster_id`/`cluster_label`). 프론트 `_metaSimGroups` 가 backend 클러스터(`be:`) 우선, 없으면 affix 폴백
     (namespace 1회, ≥2 게이팅). **un-cluster(→NULL)는 명시 clear**(_NULLABLE_PROP_KEYS → `= null`, phantom be: 그룹
     방지, 리뷰 MAJOR-2).
- Consequences: affix(클라 휴리스틱) → 의미 임베딩(서버) 상위 신호로 sim-group 정밀도 향상. **DB 스키마 비파괴
  (nullable 추가)·기존 pgvector RAG 무영향·kill switch(AGENT_METADATA_CLUSTER_AUTO=0)·fail-soft·affix 폴백**.
  임베딩·클러스터는 eventual(데몬 cadence — 배포 직후엔 affix, 몇 cycle 후 클러스터 채워짐). Phase B(크로스-데이터소스
  관계)가 이 시그니처 임베딩을 재사용해 크로스-ds 후보를 유사도로 발굴한다.
- Alternatives: 신규 테이블(중복 keying·GRANT·인덱스·sync 표면↑, 기각) / rag_objects 자체 vector 컬럼(texts dedup
  이점 상실, 기각) / sklearn·scipy(신규 heavy dep, 기각 — numpy만) / LLM 라벨(비용, 후속 옵션 — 현재 commonAffix 서버포트).
- Supersedes: (ADR-013 의 이연분 이행 — affix 계층은 폴백으로 계승, 대체 아님)
- Superseded By:

## ADR-019 — 크로스-데이터소스 관계 (Phase B, 의미 임베딩 구동 후보 + 신뢰 게이팅)
- Status: accepted (2026-07-04)
- Context: 사용자 3대 개선 中 B — "다른 DB 간 관계가 구성될 수 있으니 그 구조를 위한 연결 구축". 실측상 관계 엔진은 3중
  경계(table_relationships 단일 scope_key/datasource_key·추론 per-schema·프로브 단일 커넥션)로 datasource 내부에만
  갇혀 있었다(조사 확인). 크로스-데이터소스 조인은 FK·프로브가 불가능(다른 엔드포인트)하므로 **의미 유사도**로만
  후보 발굴 가능 — Phase C(ADR-018) 시그니처 임베딩이 그 토대.
- Decision: 사용자 결정(크로스-데이터소스까지)대로 데이터소스 경계를 넘는 관계를 additive 로 표현·발굴·표시.
  1. **data model(alembic 0036, 비파괴)**: table_relationships 에 source/target_datasource_key(default '', 기존 행
     backfill=datasource_key) + UNIQUE 7-col 진화(intra-ds refine) + CHECK 에 'manual' 추가. upsert ON CONFLICT 7-col.
  2. **추론(insight-worker 데몬, 기본 OFF)**: Phase C 시그니처 임베딩 pgvector 코사인으로 서로 다른 datasource 의
     의미-유사 테이블을 찾고, 양쪽 공통 join-key 컬럼(동명·식별자형)을 후보(source='inferred', status='candidate')로.
     effective schema(MSSQL DB명) 사용(그래프 노드 정합). AGENT_XDS_RELATIONSHIP_INFER_AUTO=0 로 ship — 임베딩
     populate 후 flip.
  3. **신뢰 게이팅**: 크로스-ds 는 프로브 검증 불가 → fetch_probe_candidates 가 src_ds=tgt_ds 만 프로브(영구 candidate,
     오분류 파단 방지) + apply_relationship_signal 도 intra-ds 전용(오염 감쇠 방지). **승격은 manual 큐레이션(source=
     'manual'→trusted)만**(대화 JOIN 은 단일 커넥션이라 실질 불가). AI 컨텍스트는 크로스-ds 는 **trusted 만 주입**
     (미검증 candidate 오염 차단, load_relationship_context). 주입 시 [교차DB] 마커.
  4. **그래프 투영·완화**: sync_relationship 이 각 끝점을 **자기 datasource scope**(_vkey)로 앵커(cross_ds edge 속성).
     neighborhood BFS 는 scope-무관이라 크로스 엣지 자동 노출. node_analysis 는 **의도적 cross_ds REFERENCES** 로 도달한
     이웃의 cross-scope 감쇠를 완화(1.0, 우연 교차는 0.25 유지) + 이웃 job 을 자기 scope 로 기록.
  5. **UI**: 크로스-ds 엣지 = 마젠타 점선(same-ds candidate 골드와 구분) + [교차DB] 데이터.
- Consequences: 데이터소스 경계를 넘는 관계가 표현·발굴·표시된다. **비파괴·데몬 OFF ship(스키마·UI·완화만 즉시,
  추론 inert)**. 마이그 mixed-version 창은 fail-soft(OLD 5-col ON CONFLICT 가 7-col DB 에서 실패해도 upsert try/except).
  크로스-ds 는 검증 불가라 보수적(높은 MIN_SIM·trusted-only 주입·manual 승격). Phase C 임베딩 populate 후 AUTO=1 flip.
- Alternatives: 데이터소스 내 카탈로그 크로스만(프로브 가능·안전하나 사용자 "다른 DB 간" 미충족, 기각) / cross-ds 를
  probe(불가 — 다른 엔드포인트, 기각) / auto-promote to trusted(검증 없이 신뢰=오염 위험, 기각 — manual/대화만).
- Supersedes:
- Superseded By:

## ADR-020 — 카테고리 그룹(sim-group) 상호작용: 드래그·접기·반응형 리사이즈 (ADR-015 자유배치를 그룹 계층으로 확장)
- Status: accepted (2026-07-04)
- Context: 사용자 회귀 재보고 — ADR-015(freeplace)가 자유배치 드래그·접기를 **스키마 클러스터(combo)** 와 **개별 테이블
  노드** 레벨에만 복원했으나, 사용자 첫 의도는 그 사이 계층인 **카테고리 그룹**(= 스키마 클러스터 내부에서 유사 테이블을
  묶는 유사 속성 그룹 / sim-group, ADR-013 의 색 배경 박스 GB + 헤더 칩 GH)이었다. 당시 sim-group 은 `_metaElementDragEnable`
  에서 드래그가 차단된 **비상호작용 장식**(클릭·우클릭은 소속 스키마로 위임만)이라, 사용자가 기대한 [그룹 드래그 이동]·
  [그룹 접기/펼치기]·[그룹 내부 노드 이동에 따른 박스 반응형 리사이즈]가 동작하지 않았다.
- Decision: sim-group 을 combo·테이블 노드와 동일한 자유배치 상호작용 대상으로 승격(ADR-015 offset 레이어를 그룹 계층으로 확장).
  좌표는 **3계층 offset**: cluster `L.x0/L.y0`(clusterOffset 포함) → group `groupOffset` → node `nodePos`.
  - **groupOffset**(groupKey→{dx,dy}): GB/GH 드래그의 누적 델타. build 가 그룹 블록 위치(bxRel/byRel)와 그 멤버 place
    (lx/top)에 공통 가산 → 박스·헤더·멤버·컬럼이 coherent 이동, rebuild(펼침/접기) 후 유지. 리지드 드래그는 grabbed 요소를
    anchor 로 그룹 전 요소(GB·GH·GX·멤버 테이블·종속)를 고정 오프셋으로 묶어 이동(graph-drag 테이블-종속 기전 재사용).
  - **groupCollapsed**(Set): 접힌 그룹은 멤버 place 미방출·블록 높이를 헤더만(GHH+GPB)으로 축소 → shelf-pack 자동 reflow.
    헤더 칩(개수 표시)은 유지. 전용 토글 컨트롤 **GX**("−"/"+", 그룹 헤더 우측 — 스키마 XS: 패턴 재사용) 클릭으로 토글.
    검색 매칭 멤버가 있는 그룹은 접힘 상태여도 build 가 강제 펼침(결과 가시 — schemaExpanded 자동추가와 동형, 사용자 의도 보존).
  - **반응형 리사이즈(#3)**: 펼친 그룹의 GB 박스 기하를 **멤버(테이블+펼친 컬럼)의 최종 place bbox + 패딩**에서 파생 —
    개별 노드 이동(nodePos)·그룹 이동(groupOffset) 양쪽에 박스가 자동으로 맞춰진다(드래그·리사이즈 단일 메커니즘 통합).
    무-offset 시 이 파생 박스는 packGroup 기하와 정확히 일치(회귀 0). 그룹 소속 테이블 단독 드래그 dragend 는 rebuild 를
    트리거해 박스 재파생(평면·비그룹 테이블은 기존대로 combo auto-fit 만 — rebuild 없음).
  - **정합 불변식**: 그룹을 통째로 옮기면 소속 멤버 nodePos(절대좌표)도 동반 가산(ADR-015 clusterOffset MAJOR fix 동형).
- Consequences: ADR-013 sim-group 이 '가시적 영역'에서 '조작 가능한 그룹'으로 승격. ADR-004 결정론 배치·§49 순서 안정화는
  불변(offset·방출여부만 개입, 배정/순서 미변경). 프론트 전용·마이그레이션 0. 한계(수용): GB 배경이 combo 내부를 덮어
  combo(클러스터) 드래그 표면은 헤더/여백으로 얇아짐(접힌 카드·헤더 경로 유지). 라이브 canvas 드래그 자동화는 PB-0008
  Playwright real mouse 로 검증.
- Alternatives:
  - **GB 를 G6 combo 로 승격(자식 자동 fit)**: combo 중첩(그룹⊂스키마) — setData diff·이벤트 복잡도·회귀 위험 큼, 기각.
    파생 bbox 가 combo 없이 반응형 리사이즈 제공.
  - **헤더 칩 클릭으로 접기 토글**(GX 컨트롤 없이): 기존 GB/GH 클릭=스키마 상세 위임(데드존 방지)과 충돌 — 기각, 전용 GX.
  - **접기 시 그룹 블록 폭도 축소**: 펼침/접힘 간 가로 reflow 요동 — 안정성 위해 폭 유지(헤더 높이만 축소), 기각.
- Supersedes: (ADR-015 를 대체하지 않음 — 그 offset 레이어를 그룹 계층으로 확장)
- Superseded By:

## ADR-021 — §55 graph-category-recursive-refine: 제품 카테고리 밴드 + 크로스-DB 관계 일반화 + DB 단위 분석 재귀·refine (REQ-20260706)
- Status: accepted (2026-07-06)
- Context: 사용자 4대 요구 — ① 데이터소스 진입 시 스키마 클러스터가 명칭순 평면 나열(관계 희소 시 seriation 폴백)
  → 제품(Products)·DB 매핑 기반 카테고리 구분 필요. ② 'AI 능동 분석'·관계가 스키마 내부에 갇힘(라이브 실측:
  관계 11,056행 中 크로스-DS 0·같은 DS 크로스 스키마 0 — 추론 per-schema 고정(relationships.py _add 양끝 고정),
  MSSQL 프로브 2-part 만, 크로스-DS manual 승격 호출자 0 = 영구 candidate·AI 미주입 dead-end). ③ DB(스키마) 단위
  분석이 재귀 0(§53 설계 — node_budget==planned)·컬럼 미시드·분석 저장이 사실상 override(이전 분석 미참조)·빈약
  분석 후속 보충 부재. ④ ADR-018(Phase C) 시그니처 백필이 3%(497/16,023)에서 정체 — `updated_at DESC LIMIT N`
  이 미처리 행을 우선하지 않아 처리된 최신 N 행만 매 pass 재스캔(no-op).
- Decision:
  1. **A(카테고리)**: `WebProductDatabases`(ProductId, DatasourceKey, SchemaName — 제품별 접근 DB SSOT)를 투영 API
     질의시점 합성(`_schema_products_for_scope`, ADR-014 원칙 계승 — AGE 미저장)으로 `schema_products` 응답 부착.
     프론트 `_metaCatAssign` 이 클러스터를 catKey(`PC:<제품id>`|미분류)로 배정하고 shelf-pack 을 **카테고리 밴드별
     분할**(세로 스택·헤더 CATHH), `CAT:`(배경, 신설 z 밴드 CAT_BG=-1 — combo 아래)+`CATH:`(헤더 칩, GROUP_HD)+
     `CATX:`(접기, CTL) 방출 — sim-group GB/GH/GX 패턴 재사용. CATH 드래그=멤버 클러스터 clusterOffset 일괄 누적
     (신규 offset 계층 없이 ① 계층 재사용 — ADR-015/020 정합), 접기=멤버 미방출+헤더 밴드, §49 catOrder 안정화,
     검색 매칭 카테고리 강제 펼침. 다제품 스키마는 대표 제품(SortOrder 1순위) 배정 + 상세에 전 제품 노출.
     매핑 전무 시 완전 무개입(기존 배치 — 회귀 0).
  2. **B(크로스-DB)**: (a) `infer_cross_datasource_relationships` 일반화 — 후보를 "다른 datasource"(XDS, min_sim
     0.90 보수) OR "같은 DS 다른 effective schema"(XSCHEMA 신설, 기본 ON, min_sim 0.86 — 프로브 검증 가능해 완화)
     로 확장. intra-DS 크로스 스키마 후보는 src_ds==tgt_ds 로 저장돼 기존 프로브·강화/파단 파이프라인에 자연 편입.
     (b) MSSQL 프로브 3-part `[db].[dbo].[table]`(스키마-slot=DB명 ADR-007) — 같은 서버 다른 DB 끝점을 한 연결에서
     검증. slot='dbo'(레거시 대화학습)는 실 스키마로 보고 2-part 유지(오파단 방지). fetch_probe_candidates db_scope
     필터 양끝 AND→한끝 OR 완화. (c) **manual 승격 배선**: `POST /api/admin/metadata/graph/relationship/curate`
     (trust|break, 권한 metadata.table.manage) + 관계 상세 패널 행 버튼 — 관계형 SSOT(upsert source='manual'→
     trusted / status='broken'+역방향)와 AGE(즉시 sync/delete) 동시 정합. (d) XDS 데몬 flip(compose
     AGENT_XDS_RELATIONSHIP_INFER_AUTO=1 — ADR-019 의 "임베딩 populate 후 flip" 이행, D 가 populate 가동).
  3. **C(재귀·refine)**: alembic **0038**(비파괴 ADD 2컬럼 — jobs.anchor_key TEXT DEFAULT ''·pass_no INT DEFAULT 0.
     **UNIQUE(run_id,node_key) 불변** — 구 워커 ON CONFLICT 와 mixed-version 안전). (a) 스키마 단위 분석 재귀 전개:
     시드 depth=0(직계 컬럼 게이트 면제 편입 — "테이블·컬럼·함수·프로시저 전부") + **per-seed 앵커**(anchor_key=
     자기 자신 — ADR-003 게이팅이 Schema 명칭이 아닌 각 시드 기준으로 동작, 이웃은 anchor_key 상속) +
     depth_budget=SCHEMA_DEPTH(2)·node_budget=min(SCHEMA_RUN_BUDGET_MAX 2500, planned×EXPAND_FACTOR 12).
     (b) **refine-not-override(전역)**: 모든 잡이 노드의 최신 done 분석문을 payload.previous_analysis 로 동봉 —
     LLM 프롬프트 refine 계약("비교 후 정확한 쪽 채택, 다른-but-not-틀린 융합, 유효 사실 폐기 금지") 명문화.
     (c) **back-refine**: 잡 완료 시 같은 run 의 인접 선행 done 中 빈약(thin: summary<THIN_CHARS 120 또는
     relationships·usage 공란) 노드를 재-pending(pass_no+1, run 당 REFINE_MAX 30 캡, enqueued+=n 로 카운터 단조) —
     refine 잡은 related_findings(같은 run 인접 done 요약 ≤6)를 동봉받아 후속 발견으로 보충. (d) **관계 보충**:
     LLM 출력 계약에 optional suggested_links(≤4) — 컨텍스트 실재 테이블 화이트리스트 + root 연루 강제 + root 측
     컬럼 실재 검증 통과분만 source='llm_insight' candidate 적재(기존 프로브·자기교정이 후속 판정 — 환각 차단 3중 가드).
     0038 미적용 창은 전 지점 legacy 폴백(재귀 0·단일 앵커·refine 비활성 — role/user_prompt 창 방어와 동형).
  4. **D(백필 정체)**: `run_signature_backfill_pass` 를 미처리(hash NULL/'') 우선 정렬로 수정 + remaining 카운트
     +info 로그 1줄(관측성 — 정체 재발 감지) + SIG_BATCH 200→500(16k 백로그 ~8h 소진). Phase C 클러스터가 채워지며
     sim-group `be:` 신호·XDS/XSCHEMA 추론이 실동작으로 전환된다(ADR-013→018 계보 완결).
- Consequences: 그래프 뷰가 "명칭순 평면 나열" → "제품 카테고리 밴드 > 스키마 클러스터 > 유사 속성 그룹 > 테이블"
  4계층 시각 구조가 되고, 관계·분석이 DB/DS 경계를 넘는다. DB 스키마 변경은 0038 비파괴 2컬럼뿐. 비용 경계:
  스키마 run 예산 상한(2500)·REFINE_MAX·SUGGEST_LINKS_MAX·XSCHEMA min_sim/캡. 알려진 한계: ① 카테고리 밴드
  자체의 자유 위치 저장은 멤버 clusterOffset 로 표현(밴드 전용 offset 없음 — 멤버 재배치와 정합) ② 다제품
  스키마는 대표 제품 밴드에만 배치 ③ suggested_links 는 root 연루 관계만(제3자 간 제안 배제 — 보수) ④ MSSQL
  dbo 외 실스키마는 관계 파이프라인 전반 미추적(기존 플랫폼 가정 유지).
- Alternatives:
  - 카테고리를 AGE Product 정점으로 물리 저장: ADR-014 에서 기각한 이중 정합 부담 재유입 — 질의시점 합성 유지.
  - 크로스 스키마를 명명규칙(per-schema heuristic)의 전 스키마 O(N²) 확장으로: 8k 테이블 조합 폭발 + 프로브 부하 —
    임베딩 유사도 게이트(Phase C 재사용)가 후보를 소수로 압축(기각).
  - refine 을 신규 행(UNIQUE 3-col 진화)으로: 구 워커 ON CONFLICT (run_id,node_key) 가 마이그 직후 크래시 —
    mixed-version 롤링 창 안전을 위해 재-pending 방식 채택(기각).
  - 빈약 판정을 LLM 재평가로: 판정 자체가 LLM 비용 — 길이·공란 휴리스틱으로 충분(기각, 후속 여지).
- Supersedes: (§53/§54 의 "재귀 0" 계약을 대체 — 예산·게이팅 경계는 계승. ADR-017 승격, ADR-018/019 는 불변 토대)
- Superseded By:

## ADR-022 — §56 routine-sync-crossdb: sync_graph 행 격리(SAVEPOINT) + 프로시저 크로스-DB 참조 해석 (fhgame1 실측 이슈)
- Status: accepted (2026-07-07)
- Context: 사용자 실측(mssql-qa-idc/fhgame1) — DB 능동 분석에서 ① 함수·프로시저 노드 부재 ② 크로스-DB 관계
  부재 ③ '보충설명 필요' 다수(재귀 부실). 라이브 진단: routine_objects SSOT 는 완비(11,973행)이나 AGE 9행 —
  sync_graph batched 트랜잭션에서 한 행 실패 → 오염 연쇄(InFailedSqlTransaction) + 배치 롤백 소실(full sync
  errors 18,698, 단건 전행 성공=불량행 0). errors>0 이 워터마크를 고착시켜 증분 sync 무한 전량 재스캔.
  또한 parse_referenced_tables 가 qualified 참조를 leaf 정규화해 크로스-DB 참조 폐기 + 동명 로컬 오귀속 —
  프로시저 중심 환경의 관계 substrate 소실이 분석 빈약(caveats)의 근인.
- Decision:
  1. **행 격리**: sync_graph 전 단계 per-row 를 `_sync_row_guard`(SAVEPOINT→성공 RELEASE/실패 ROLLBACK TO)로
     격리 — 실패는 그 행에 국한, 성공분 소실 0. 실패 첫 5건 샘플을 warning 으로 노출(최초 오염원 식별).
     step-레벨 실패는 신설 step_failures 로 분리 집계.
  2. **워터마크 게이트 교체**: per-row errors(결정적 데이터 오류 — 재스캔 무익)는 전진을 막지 않고,
     step_failures(SELECT 불가·트랜잭션 붕괴 = 커버리지 구멍)만 차단. ok=errors==0 AND step_failures==0(가시성 불변).
  3. **크로스-DB 참조 해석(4규칙)**: qualifier ①'dbo'/자기 라벨→로컬 ②(qualifier,leaf)∈external_tables
     (rag_objects 의 같은 ds 타 effective 스키마 테이블 집합, TTL 600s 캐시)→**크로스-DB 참조**(entry 에
     schema 필드, 저장 fqn=`타스키마.T`+cross 플래그) ③알려진 타 스키마인데 미실재→폐기(동명 로컬 오귀속
     차단) ④미상→레거시 로컬 폴백(recall 보존). sync_routine 은 fqn 그대로 `<scope>:<fqn>` 앵커라 크로스
     클러스터 ROUTINE_USES 가 코드 불변으로 성립 — 그래프 가시화 + node_analysis routine_use(0.35) 전파.
  4. **thin 동치**: "연결 정보 없음" 문구=공란 — substrate 가 뒤늦게 채워지는 스키마에서 back-refine 이 발화.
  5. **backfill read-axis 정규화(RC4)**: routine_backfill 의 SSOT/그래프 키를 registry 라벨에서 read-axis
     scope(`ds.scope_key or 라벨lower`)로 교체 — 라벨/해시 이중 적재(실측 4쌍)·label 고아 그래프·RC2 rag
     불일치 해소. 기존 라벨-키 중복 행은 운영 정리(해시 twin 존재 시 삭제)로 회수.
- Consequences: 프로시저 중심 DB(fhgame1 류)의 함수·프로시저와 그 크로스-DB 사용 관계가 그래프·능동 분석에
  진입한다. sync 는 부분 실패에 견고(연쇄 0)·관측 가능(샘플 로그)·증분 정상화(워터마크). 마이그 0·비파괴.
  한계: SAVEPOINT per-row 오버헤드(로컬 PG, fsync 없음 — 수 μs/행, batched commit 불변) · qualified 2-part
  의 MSSQL 실스키마 vs MySQL db 모호성은 실재 검증으로 해소(미실재 시 ④/③ 규칙) · 재파싱은 정의 재-introspect
  경유(routine-backfill/cadence — definition 미저장, IS DISTINCT FROM 이 refs 변화를 감지해 upsert).
- Alternatives: (a) 오염 시 배치 전체 재시도(autocommit 강등) — 성공분 보존 못 하고 부하 2배(기각, SAVEPOINT 가
  정밀) (b) 크로스 참조를 table_relationships 로도 적재 — 컬럼 정보 없는 read/write 는 REFERENCES 의미와 불일치
  (기각 — ROUTINE_USES 가 정위치, 조인 후보는 Phase B 임베딩 경로) (c) 정의 원문 저장 후 재파싱 — SSOT 비대·
  민감 코드 저장(기각, definition_hash 만 유지).
- Supersedes: (ADR-016 의 "그 스키마 실재 테이블만" 참조 규칙을 4규칙으로 대체 — 보수성은 실재 검증으로 계승)
- Superseded By:

## ADR-023 — §56 RC5: routine store label(MSSQL DB명) lowercase 정규화 — set_active_database 계약 준수
- Status: accepted (2026-07-07)
- Context: fhgame1 e2e(ADR-022 후속) 재-introspect 에서 fhgame1 300→600행 — cadence 는
  `set_active_database`(TASK-0220, `str(db).strip().lower()`)를 경유해 routine·relationship·table
  전 경로가 lowercase store label 을 쓰는데, routine_backfill 은 `list_server_databases()`(sys.databases
  원본 케이스)를 무가공 store. RC4(ADR-022 D5)의 scope 통일 전엔 서로 다른 scope 라 충돌이 잠복,
  통일 후 같은 scope 에 케이스-변형 이중행(라이브 qa-idc 1,912쌍·mixed 6,320행)·그래프 중복
  Schema/Routine 클러스터로 표면화.
- Decision: backfill mssql 분기에서 `store_label = str(dbname).strip().lower()` 로 정규화해
  introspect_and_store(store_schema=…)에 전달. 질의 연결(connect(database=dbname))은 원본 유지
  (store/query 분리 — ADR-007 스키마-slot 규약과 동일 구도). MySQL 은 스키마 케이스 구분
  (lower_case_table_names=0)이 유효해 비적용. insight/cadence 는 이미 계약 준수 — 무수정.
- Consequences: 두 writer 의 store label 이 단일 계약(`normalize_db_label`, shared/config — §18.8
  패널 반영으로 set_active_database 와 공유·parity 테스트 잠금)으로 수렴 — 케이스-변형 이중 적재
  재발 차단. 기존 mixed-case 행은 backfill 이 introspect 성공 직후 `purge_case_variant_labels` 로
  **멱등 자동 회수**(패널 MAJOR 반영 — 수동 runbook 코드화·stale pre-RC5 writer 재발 자기치유),
  그래프 mixed-key 고아는 AGE DETACH DELETE 운영 정리 후 full sync 재투영. 한계: ① CS collation
  MSSQL 서버에서 케이스만 다른 두 DB 는 한 label 로 병합(실환경 미관측) — prune 강등으로 교차-삭제
  진동은 차단, 진단은 리포트 slot(원본 케이스)+store_labels 매핑 ② routine_name·refs 테이블명 축의
  information_schema 케이스 플래핑(pre-existing, TASK-0305 RC2 계열)과 backfill(DB 전체)·cadence
  (스키마 단위) refs 입력 발산 churn 은 본 ADR 범위 외 — §56 후속.
- Alternatives: (a) 설정 라벨 역매핑(config casing 추종) — 서버 전수 DB 는 설정에 없어 미상 라벨엔
  규칙 부재(기각) (b) introspect_and_store 내부 무조건 lower — MySQL 케이스 구분 파괴(기각)
  (c) 케이스-무시 unique 인덱스 마이그 — 쓰기 계약 정리 없인 첫 writer 케이스에 종속(기각, D 가 선행).
- Supersedes: — / Superseded By: —

## ADR-024 — §57 graph-edge-visibility: 접힘 카드 집계 연결선 + 상대 하이라이트 + 크로스 시각 구분 + LOD
- Status: accepted (2026-07-08)
- Context: PB-0008 시각검증(§56) 후 사용자 요청 — 접힘 카드 상태에서 연결 구조 불가시, 선택 시 전역
  동일 강조로 관계 추적 곤란, 크로스-DB 사용선 미구분, 중간 줌 엣지 스파게티. 진단: scope_schemas 가
  edges 미반환 + renderEndpoint 의 카드 승격 부재(2중 근본원인).
- Decision: ① 카드간 연결 구조는 **질의시점 1-hop 전량 스캔 + Python 스키마-쌍 무향 집계**(SCHEMA_REF,
  cap 400)로 동봉 — 멀티-hop cypher(82s 실측)·sync 시 materialize(스테일·복잡도) 기각, 1-hop 0.2s 실측.
  ② 렌더는 3단 승격(컬럼→테이블→SC: 카드)으로 혼합 상태(펼침↔접힘)까지 연속 — SCHEMA_REF 는 양쪽
  접힘일 때만(이중 표현 방지). ③ 크로스 구분은 색 단일 축(마젠타, REFERENCES cross 와 어휘 공유) —
  관계 종류는 dash·화살표, 교차 여부는 색(직교 인코딩). zIndex 불변(_metaEdgeZFor 1:1 계약 보존).
  ④ 상대 하이라이트는 rebuild-bake(dimmed state + 엣지 opacity) — setElementState 전역 루프 금지(§33).
  ⑤ LOD 는 의미 신호 보존 축약 + 밴드 전이 디바운스(경계 왕복 rebuild 방지).
- Consequences: 초기 카드 뷰에서 DB 간 연결 구조가 즉시 보이고(요청 ①), 선택 시 1-hop 만 선명(요청 ②),
  크로스-DB 선이 클릭 없이 식별되며(검토 ②), 대형 스코프 중간 줌 노이즈 감소(검토 ①). 한계:
  (a) 한쪽만 펼친 스키마의 **미로드 incoming 방향**(상대 스키마를 펼친 적 없으면 모델에 관계 자체가
  없음)은 여전히 비표시 — schema_tables outgoing-only 는 본 ADR 범위 외 (b) SCHEMA_REF 집계 엣지의
  우클릭 상세는 canvas 메뉴 폴백(기존 agg: 갭과 동일 — 후속) (c) LOD 축약 규모의 상태줄 안내 미표출
  (_lodDropped 만 집계 — 후속).
- Alternatives: (a) sync 시 SCHEMA_REF materialize — 30분 스테일+증분 복잡도, 질의시점 0.2s 로 불필요
  (b) 상대 하이라이트를 G6 setElementState 루프로 — 건당 ~50ms 실측 프리즈(기각, §33) (c) 크로스 구분을
  별도 dash 패턴으로 — 관계 종류 인코딩과 충돌(기각).
- Supersedes: — (ADR-019 색 어휘·§32 테이블-레벨 승격을 확장) / Superseded By: —

## ADR-025 — §59 product-classify-suggest: 분석 기반 제품 분류는 '제안→사람 승인' 스테이징으로
- Status: accepted (2026-07-08)
- Context: 카테고리 밴드의 스키마→제품 매핑이 이름 기반(정규식 규칙+수동)이라는 사용자 지적 —
  분석(테이블 구성·node_analysis 요약) 신호로 개선 요구. 단 매핑 테이블(WebProductDatabases)은
  에이전트 접근 allowlist 겸용(admin_products 게이트)이라 자동 기록 = 접근 권한 자동 부여.
- Decision: ① LLM 분류는 **Pending(RuleId NULL·Reason 'ai_suggest:<conf>') 적재까지만** — 승격은
  product.manage 보유자의 명시 승인(Source='ai') ② 후보 화이트리스트 = 그 datasource 에 이미
  연결된 제품만(미연결 제품 제안 = 접근면 확장이라 원천 배제) ③ 환각 차단: 입력 스키마 실재 +
  제품 id 화이트리스트 + 신뢰도 임계(0.6) 3중 게이트 ④ 데몬 기본 OFF(XDS 선례) — 운영 확인 후
  flip ⑤ 기존 rule pending 파이프라인·검증(제외 DB·이름 주입) 재사용.
- Consequences: 미분류 스키마가 분석 근거와 신뢰도를 달고 승인 큐에 오른다 — 밴드 분류가 이름
  의존에서 벗어나되 사람 통제 유지. 한계: (a) 거부 행은 pending 에서 삭제되므로 다음 pass 재제안
  가능(반복 소음 시 수동/규칙 확정이 정본 — 거부 이력 테이블은 후속) (b) 다제품 스키마는 최고
  신뢰도 1건만 제안(밴드 대표 배치 규약과 정합) (c) 분석 미보유 스키마는 테이블명 표본만으로
  판단(신뢰도 자연 하락 기대).
- Alternatives: (a) 규칙-우회 자동 기록(Source='ai' 즉시) — allowlist 자동 확장(기각, 보안)
  (b) 시각화 전용 매핑 테이블 분리(안3) — 접근·표시 이원화 관리 부담, 승인 파이프라인 재사용이
  더 단순(대안으로 보류) (c) 임베딩 군집 기반(Phase C) — 분석 요약 축적 후 후속 후보.
- Supersedes: — (ADR-021 카테고리 밴드의 매핑 원천을 확장) / Superseded By: —

## ADR-026 — §57.7 고립 노드 선택은 상대 하이라이트를 발동하지 않음
- 상태: 채택 (2026-07-09)
- 맥락: 관계가 0인 노드를 선택하면 "자기만 밝고 전체 침강"이 규칙상 정확하지만, 사용자 실측에서 "UI 구성이 무너졌다"로 인지됨(정보 이득 0 + 파괴적 외관).
- 결정: 1-hop 관계가 하나도 없는 선택은 `focusAdj = null`(하이라이트 모드 자체 미발동) — 선택 테두리·상세 패널만 제공. 관계가 늦게 적재되면 build 시점 재산출(§57.5)이 자동으로 하이라이트를 켠다.
- 기각 대안: 고립 시 dim 강도 완화(0.38→0.7) — 모드가 늘어나 예측 불가; 같은 스키마만 점등 — 관계 없음을 관계 있음처럼 오독시킴.
- Supersedes: ADR-024 의 상대 하이라이트 규칙을 정련 / Superseded By: —

## ADR-027 — §57.8 그래프 시각 상태의 단일 진실은 직렬화된 bake
- 상태: 채택 (2026-07-09)
- 맥락: 상대 하이라이트 시각 적용이 즉시 setElementState + 조건부 rebuild + 2.5s 폴의 3계층 패치워크로 진화하며, busy fail-closed 게이트 3곳과 setData/draw 경합·_stateCache 오기록이 겹치면 dim 이 영구 고착(사용자 실측 4차 리포트 "선택한 노드도 흐림 유지"). 사용자 의도의 최상위는 "무엇을 선택했는지 시각적으로 편안하게 확인".
- 결정: ① 전역 시각 상태(dim·엣지·라벨)의 단일 진실은 _metaG6Apply bake — 선택 전환마다 무조건 1회, 직렬화(겹침은 재실행 1회 병합, fit OR)로 경합 자체를 제거. ② busy 는 build states 로 bake 되어 rebuild 를 넘어 보존(소유 op 가 해제, stale 은 TTL 30s) — busy 를 이유로 bake 를 미루는 게이트를 전부 폐지. ③ 즉시 setElementState 는 순수 피드백 가속용(정확성은 bake 가 보장).
- 기각 대안: 재시도 체인 파라미터 튜닝(12→N) — fail-closed 구조 자체가 원인; dim 을 엣지도 state 화 — G6 v5 엣지 state 로 화살촉·라벨까지 일관 제어 불가(§57.6 화살촉 사건) + 전역 setElementState 루프 금지(§33)와 충돌.
- Supersedes: ADR-024 상대 하이라이트 적용 경로(§57.5 재시도 체인) / Superseded By: —

## ADR-028 — §60 graph-vpack: 클러스터 레이아웃은 고정 캡이 아닌 실높이 기반 종횡비 타깃
- 상태: 채택 (2026-07-09)
- 맥락: 사용자 리포트 — 스키마 노드를 펼치면 "스키마 클러스터가 너무 세로로 펼쳐지고", 여러 개 펼치면 "알아보기 힘든" 극단적 세로 띠가 된다(실측 aspect 0.19, 폭 ~2400 고정 × 높이 수천~수만 px → fitView 가 얇은 세로 슬라이버로 압축). 근본 원인은 레이아웃이 "폭은 고정 상한, 높이는 무한 증가" 철학이었던 것: ① 전역 shelf 폭 `MAXROWW=2400` 고정 → 클러스터가 여러 개 높아져도 폭은 고정된 채 행만 세로로 쌓임 ② 클러스터 내부 열 수 `innerColsFor` 최대 4열 캡 → 테이블 많은 스키마(이 DB 는 ~8,122 테이블/21 DS)가 4열로 눌려 세로로 길어짐 ③ 배정을 collapsed 높이로 고정(펼침-불변)해 펼친 테이블 열만 홀로 세로 폭주.
- 결정(사용자 명시 "전체 범위 — 컬럼 재분배 포함" 선택): ① **적응형 shelf 폭** — `MAXROWW = max(2400, maxClusterW, round(sqrt(총콘텐츠면적 × 2.0)))`. 많이 펼칠수록 가로로 퍼져 높이를 억제, landscape 종횡비를 겨냥. floor 2400 으로 소량 펼침 배치는 현행 보존. ② **실높이 기반 열 수** — `ic = clamp(round(sqrt(Σ realH / 100)), 1, 10)`(ASPECT_K=100→클러스터 aspect≈2.2). 펼친 컬럼을 반영해 큰/펼친 스키마는 넓고 낮게(구 4열 캡 제거), 작은 스키마(≤4T)는 1열 유지. ③ **실높이 balance 재분배** — 열 배정을 collapsed 고정에서 realH 최단 열로 전환. 펼친 테이블 열은 형제를 덜 받아 클러스터가 넓고 낮아짐. 대가로 펼침 시 형제 재배치(약간의 churn)를 수용(ADR-004 ② 재선회 — 사용자 우선순위: 가시성·비겹침 > 펼침 애니 안정).
- **비겹침 불변식 보존**(사용자 제약 "성질이 다른 노드·클러스터가 겹치지 않아야"): 열은 COLW(224) 간격, 항목은 realH push-down, 클러스터 (w,h)=실제 bbox 를 shelf-packer 가 소비 — 세 규칙 모두 유지해 노드·클러스터 pairwise 비겹침이 성립(headless T3~T6 + sim 극단 1T×100컬럼까지 겹침 0 단언).
- 기각 대안: 적응형 폭만(①) — 단일 스키마 세로 폭주 미해결; 열 캡만 상향(구 innerColsFor 4→N) — 컬럼-펼친 단일 테이블의 세로 폭주(③) 미해결; 전역 종횡비 상수 1.6 — 이산 패킹에서 넓은 클러스터가 행당 2개만 담겨 세로형 잔존(실측 aspect 0.69) → 2.0 채택.
- 실측(실 _metaG6Build before/after): 단일 12T×15컬럼 896→391 높이(56%↓, aspect 0.42→2.10) · 16스키마×40T 4372→2124(51%↓, 0.41→1.77) · 24스키마×60T 9380→3800(59%↓, 0.19→1.22).
- Supersedes: ADR-004 ②(배정 collapsed 고정으로 형제 열-점프 제거)를 재선회 / Superseded By: —
- **§60.2 addendum (PB-0008 라이브 회귀)**: 초기 수정(flat masonry + 전역 shelf 폭)은 **simGroups 경로**
  (유사속성 그룹 ≥2 스키마 — 관계 있는 제품 스키마 다수)를 놓쳤다. 그룹 블록이 고정 `TRW`(4열 상당 ≈938)
  폭으로만 래핑돼 그룹 행이 세로로 스택 → 라이브 실측 cc_*(557T) 822×10272 aspect 0.08. 결정: TRW 도 **총
  블록 면적 기반 적응**(`max(TRW, round(sqrt(ΣblockArea×2.0)))`, 클러스터-내부판 ①) + packGroup 열 상한 4→6.
  겹침 불변식 동일(블록 shelf-pack 구조·COLW·realH). 실측 557T/20그룹 0.11→1.06·4그룹 0.13→1.18. 교훈:
  적응형-폭 철학을 **모든 패킹 경로**(전역 shelf·flat masonry·simGroups 블록·group 내부)에 일관 적용해야 함.

## ADR-028 — §57.9 상대 하이라이트 침강은 G6 상태가 아니라 base style opacity 로 bake
- 상태: 채택 (2026-07-09)
- 맥락: 침강을 G6 node 상태(dimmed:{opacity:0.38})로 구현했더니, 상태 제거 시 G6 v5 가 base 에 opacity 값이 없어 되돌리지 못해 재선택 노드가 0.38 로 stale(사용자 5차 실측 — getElementState=selected 인데 실제 keyShape opacity=0.38). 사용자 지시: "재선택 대상의 비선택 상태 해제가 핵심".
- 결정: 침강 opacity 를 매 build 각 노드 base style 에 직접 bake(dim=0.38/lit=1). setData 가 keyShape 에 값을 직접 기입하므로 상태 apply/revert 동작에 의존하지 않아 dim↔lit 양방향 결정적. dimmed G6 상태 config 는 제거(base 와 이중 적용 시 곱셈 과침강 위험). 'dimmed' 문자열은 상태 서명(rebuild 감지)·base bake 입력으로만 유지.
- 기각 대안: base opacity:1 만 명시하고 dimmed 상태 유지(revert 의존 — G6 동작 불확실 + 곱셈 위험); 상태 제거 시 setElementState 로 opacity 강제 리셋(전역 루프 = §33 프리즈 금지 위반).
- Supersedes: §57.5 의 dimmed 상태 기반 침강 / Superseded By: —

## ADR-029 — §61 col-lod: 노드-레벨 LOD 로 개요 줌에서 컬럼 circle 방출 억제 (draw 지배항 절감)
- 상태: 채택 (2026-07-09)
- 맥락: 사용자 리포트 — "관리 콘솔 > 지식베이스 > 그래프 뷰에서 노드 개수가 많아질수록 부하가 늘고 지연이 발생한다." 병목 진단(read-only) + 웹 리서치(Sigma.js/Cosmograph/KeyLines/G6 native — 뷰포트 컬링·LOD·shape 감축) + 19개 후보 최적화의 적대적 검증(코드·번들 실측) 결과, **살아남은 유일한 안전·유효한 최적화 = 노드-레벨 컬럼 LOD** 로 수렴. 확정 병목: (INV-COLUMN-CAP-DRAW) draw 지배항은 테이블당 최대 500 Column circle 이고, 현행 LOD 는 **엣지만** 축약(§57, `_META_EDGE_LOD_ZOOM 0.35`)해 노드 축은 줌 무관하게 전량 draw. 라이브 실측 5스키마=2,618노드·단일 `cc_*`=557테이블.
- 기각된 대안(적대적 검증이 반증):
  - **WebGL/GPU 인스턴싱** — 번들 Canvas 전용(@antv/g-canvas, webgl 심볼 0). WebGL 이탈은 점선·테두리 품질 회귀(ADR-004)라 재-vendoring+품질 재검증 비용 → drop-in 아님.
  - **`optimize-viewport-transform` drop-in** — 번들에 behavior 로 존재하나, 지배 병목은 pan/zoom 프레임이 아니라 펼침/선택/마커의 full-rebuild 라 top-3 미해결.
  - **뷰포트 컬링/가상화** — `_metaG6Build` 가 방출 전 전 노드 좌표를 계산(seriation O(S²)·masonry)하므로 컬링해도 레이아웃 비용 잔존 + pan 재방출 churn + combo 자식 auto-fit 축소로 좌표 비동일 → net negative.
  - **topology-diff 증분 갱신(ADR-004 재검토)** — G6 증분 데이터 API(addData/updateData/draw)는 번들에 실재하고 `draw()`는 layout-free(BLUEPRINT §3 크래시는 `+render()` 였음)이나: ① G6 `setData` 는 이미 draw 단계에서 diff(변경 요소만 재렌더 — 스칼라 스타일 Column circle 포함)라 증분이 지배 draw 를 못 줄임 ② ADR-028 §60 vpack 이 펼침을 형제 ~43% re-column(O(N))으로 만들어 "bounded-delta" 무효 ③ combo 는 자식 auto-fit(`getComboPosition=getContentBBox(children).center`)이라 명시 bbox push 무효 → coordinate-identity 불가. 실이득 marginal·결정론/soak 위험 → 사용자 결정으로 A(본 ADR)로 전환.
- 결정: **개요 줌 밴드에서 Column circle·Routine 파라미터 circle·per-table "X:" 접기 ctl 의 방출(emission)을 억제**한다. `colLodActive = getZoom() < _META_COL_LOD_ZOOM(0.5) && 전체 펼친 컬럼 수 > _META_COL_LOD_MIN(200)`. 테이블·스키마 칩·관계선은 유지.
  - **결정론 보존(핵심)**: `realH`(펼친 컬럼 높이 포함 공간 예약)는 **불변** — 억제는 `nodes.push` 단계에서만 일어나고 masonry/shelf-pack/좌표 계산은 억제 여부와 무관. 따라서 테이블 tx/ty 가 **band-invariant**(reflow 0, headless T2 이동 0 단언). combo 는 자식 auto-fit 이나 테이블 위치가 combo 범위를 정의하므로 카드 배치 안정(억제 시 하단 여백만 tighter — content 이동 아님).
  - **정보 손실 방지**: 억제 테이블 라벨에 `▤N` 컬럼수 배지(`labelMaxWidth` 클램프가 overflow 차단). realH 예약 gap 도 '펼침' 시각 신호.
  - **엣지 무결성**: 컬럼 끝점 REFERENCES/ROUTINE_USES 는 기존 `renderEndpoint` 가 소속 테이블로 승격(접힌 스키마와 동일 경로) → dangling 0(headless T4).
  - **밴드 churn 억제**: `_lodBand` 를 2단→3단(full ≥0.5 / collod 0.35~0.5 / lod <0.35)으로 확장, 어느 임계 교차든 기존 300ms 디바운스 rebuild(INV-EDGE-LOD-DEBOUNCE 계승). 상태줄에 밴드별 축약 안내.
- 게이트 근거: 줌 ≥ 0.5(판독 가능 배율)에서는 억제 안 함(정보 유지) — `_META_MIN_READ_ZOOM 0.55` 클램프 하에서 초기 fit 은 억제 밴드 밖. 컬럼 ≤ 200 이면 draw 저렴 → 억제 안 함(불필요 정보손실 방지, headless T5/T6).
- 검증: headless `test_g6build_collod.js` **18 PASS**(억제 0방출·좌표 band-invariant·▤N 배지·엣지 re-anchor·줌/컬럼 게이트·루틴 파라미터) + 기존 `test_g6build_vpack/category/edge_visibility` **105 PASS 회귀 0**. 실 Windows 브라우저(PB-0008) 대형 그래프 줌아웃 before/after 는 TEST.md §61.
- Supersedes: — (§57 엣지 LOD 를 노드 축으로 확장·병존) / Superseded By: —

## ADR-030 — §63 agg-lod: 극단 줌아웃에서 클러스터를 단일 집계 카드로 강등 (semantic zoom)
- 상태: 채택 (2026-07-10)
- 맥락: 사용자 후속 요청 — "줌아웃으로 개별 객체 식별이 무의미해질 정도면, 객체들을 일반화한 상위(집계) 객체로 묶어 draw 횟수를 줄여라." + 실측: 헤드리스로 `_metaG6Build` **JS 실행은 18–50ms**(대형 모델도) → **레이아웃 재계산은 병목 아님**. 병목은 브라우저 `setData`+`draw`(Canvas)이고 **방출 노드 수에 비례**(ADR-006 ~1ms/node). col-LOD(§61)는 컬럼만 줄여 대형 스키마의 **테이블 수 floor**(cc_* 557T)가 남아 사용자 "여전히 느림" 체감. 근본 해결 = 방출 요소 수 자체 감축.
- 결정: **줌 < `_META_AGG_ZOOM`(0.15) + 모델 노드 > `_META_AGG_MIN`(60)** 이면 확장 클러스터를 **단일 집계 카드(SC:id)로 강등** — 수천 노드 방출을 클러스터 수(~수십)로 축약. 기존 접힌-카드 emission(schema-card, table_count 배지) 재사용.
  - **reflow-free(핵심)**: `layouts` 산정(gatedTables·masonry·shelf-pack·슬롯 좌표)은 **불변** — 집계는 emission 에서만 카드로 대체(슬롯 좌상단 배치). 다른 클러스터 위치 불변, agg↔full 전이 점프 0(headless T3). 사용자 위치-민감성 존중.
  - **타입 안전**: `SC:id`↔combo `id` 는 다른 네임스페이스 → setData add/remove(타입전환·자식유실 회피, 카드 계약 admin.js:4976).
  - **엣지**: 집계 시 테이블 미방출 → REFERENCES 끝점 `renderEndpoint` SC: 카드 승격, 양끝 SC: skip(SCHEMA_REF 중복 방지, 기존) → 카드-카드 aggregate 관계만.
  - **계층**: agg(0.15) < edge-LOD(0.35) < col-LOD(0.5) < full. 4단 밴드(`_lodBand`) 300ms 디바운스. 상태줄 "개요 — 클러스터 집계".
- 기각/대안: (a) 뷰포트 컬링으로 테이블까지 줌인에서 감축 — combo auto-fit(`getComboPosition=getContentBBox(children).center`)이 테이블 컬링 시 카드 축소/점프 → combo-safe 아님, 별도 검토(잔여). (b) compact 카드-그리드 재배치 — 위치 점프(사용자 민감) → reflow-free 슬롯 유지 채택(대가: agg 뷰 다소 sparse).
- 검증: headless `test_g6build_agglod.js` **9 PASS**(카드 방출·draw 급감>10x·reflow-free·비-agg 유지·게이트) + 회귀 125 = **134 PASS**. diff 2렌즈 적대 리뷰 PASS(BLOCKING/MAJOR 0, MINOR 1 수정: 상태줄 마커를 밴드→실제 억제 플래그 게이트해 §57 오독-가드 코너 재발 차단). PB-0008 극단 줌아웃 before/after 는 TEST §63.
- Supersedes: — (§57 엣지·§61 컬럼 LOD 를 클러스터 축으로 확장·병존) / Superseded By: —

## ADR-031 — §64 lod-hl-declutter: 하이라이트 상태의 줌아웃 LOD 축약 예외를 "선택 노드 직접선"으로 축소 (dim 과 분리)
- 상태: 채택 (2026-07-10)
- 맥락: 사용자 리포트 — "줌아웃 시 관계선이 간소화되던 최적화가 상대적 하이라이트(특정 노드 클릭) 상태에서는 작동하지 않는 것으로 추측." 코드 추적으로 근본원인 확정: 노드 클릭은 `_metaGraphSetSelected`→`_metaG6Apply(false)`(fit=false)로 full rebuild → §57 edge-LOD 자체는 재실행되고 줌도 불변(즉 "LOD 미실행"·"선택이 줌 리셋" 아님). 진짜 원인은 LOD 드롭 예외 술어 `keep = lit(rs) && lit(rt)` 가 **dim(§57.5 "양끝 밝음") 규칙을 그대로 재사용**한 점. `lit` 의 "밝은 부분그래프" = 선택 노드 + **1-hop 이웃 전체 + 컨테이너**(`_metaFocusAdjacency`)이므로, 선택 노드에 직접 닿지 않는 **이웃↔이웃 엣지까지 전부 LOD 예외**가 된다. 허브 테이블(이웃 다수·상호연결) 선택 시 사실상 전량 보존 → 간소화 무력화(적대검증 실측: 허브 선택 시 `_lodDropped=0`).
- 결정: **dim(밝기)과 LOD-keep(축약 예외)을 분리**한다.
  - `dimIf` 인자 `keep = lit && lit`(양끝 밝음) — **불변**. 유도 부분그래프(선택+이웃)는 계속 선명(§57.5 규칙 보존).
  - LOD 드롭 예외는 신설 `keepLodFor(a,b) = litSelf(a) || litSelf(b)` — 끝점 하나라도 **선택 노드 자체**(`fa.self`; 테이블이면 자기 컬럼 포함)면 보존. 이웃(`fa.nodes`)은 제외. SC: 접두 벗김·컬럼→소속테이블 접기는 `lit` 과 동일.
  - 적용: LOD 드롭 4경로(ROUTINE_USES 직접·집계, 비-REFERENCES 직접, REFERENCES colLevel·집계, aggMap.forEach)를 `keep`→`keepLod`/`agg.keepLod`. 집계 엣지는 멤버 중 하나라도 self-incident 면 보존(`agg.keepLod ||=`).
  - 효과: 하이라이트 상태에서도 줌아웃 축약이 정상 작동(이웃↔이웃 클러터 정리) + 선택 노드의 관계선은 항상 보임 + 밝기 대비는 유지.
- 기각/대안: (a) 하이라이트와 무관하게 완전 축약 — 선택 노드의 단건 FK 도 줌아웃 시 사라져 "선택한 것의 관계를 못 봄"(사용자 A안 선택으로 기각). (b) 현행 유지 — 사용자가 오작동으로 인지(기각). (c) 이웃 hop 수 파라미터화 — 과설계, 현 요구엔 self-직접선으로 충분.
- Supersedes: §57(TASK §57.5)의 "하이라이트 인접 보존"의 **LOD 예외 범위**를 "인접 전체 부분그래프"→"self-직접선"으로 개정(dim 은 §57.5 그대로 보존) / Superseded By: —
- 검증: headless `test_g6build_edge_visibility.js` **T22 신설 4 PASS** + 회귀 = **138 PASS(edge 64·collod 20·agglod 9·category 26·vpack 19) 회귀 0** · `node --check` PASS · **적대검증**(수정 되돌린 OLD 동작에서 T22 정확히 FAIL 재현). diff 적대 리뷰(REV-…lod-hl-declutter). PB-0008 하이라이트+줌아웃 실측은 TEST §64.

## ADR-032 — §65 viewport-cull + 집계 supernode 크기 + 집계 마커 제거 (사용자 육안 피드백 반영)
- 상태: 채택 (2026-07-10)
- 맥락: agg-lod(§63, ADR-030) 배포 후 사용자 실화면 피드백 — ① 집계 카드가 줌아웃 크기라 작아 읽기 힘듦 ② 펼침 정상 ③ **집계 상태 성능 확연 상승**(집계 접근 유효 확인) ④ 상태줄 "클러스터 집계" 안내는 그래프 사용에 무의미(노이즈). + "남은 작업(줌인 대형모델) 검토" + **"시각 검증 가능(선례 참조)"**. → win-browser.py relay(실 Windows Chrome, `https://localhost/admin` 로그인)로 그래프뷰 시각검증이 가능함을 확인(메모리의 무인-blocker 는 outdated) → 줌인 컬링을 combo 거동까지 육안 확인하며 구현 가능.
- 결정:
  - **(1) 집계 supernode 크기**: 집계 카드를 ≈1/zoom(목표 화면폭 ~120px, [1.6,6] 클램프)로 스케일업 + 슬롯 중앙 배치 + 슬롯 안으로 클램프(겹침 억제) + 라벨/배지 폰트 동반 확대. 줌아웃에서도 읽히는 supernode.
  - **(2) 집계 상태 마커 제거**: aftertransform 마커에서 `aggCut ? ""`(집계는 카드로 자명 — 노이즈 제거). col/edge LOD 마커는 §57 오독-가드 목적이라 유지(비-집계 밴드).
  - **(3) viewport-cull(§65)**: 줌인 대형모델(nodes>`_META_CULL_MIN`=400, !aggActive, 뷰포트 API 존재)에서 **화면(뷰포트+마진 `_META_CULL_MARGIN`=0.6) 밖 테이블의 컬럼/파라미터 방출 억제**. 병목=setData/draw 방출 요소 수라, 보이지 않는 컬럼을 안 그리면 줌인 클릭/팬이 가벼워진다. col-LOD(개요 전체 컬럼억제)와 동일 억제 메커니즘(realH 예약·▤N 배지·**테이블 칩 항상 유지**)을 뷰포트 축으로 확장, OR 결합.
    - **combo-safe**: 테이블 칩은 화면 안팎 무관하게 항상 방출 → combo extent 불변(테이블이 combo 범위 정의, col-LOD 와 동일 계약). 좌표 band-invariant(realH 유지).
    - **엣지**: 미방출 컬럼 끝점은 renderEndpoint 가 소속 테이블(항상 방출)로 승격 → dangling 0.
    - **팬 재-emit**: 컬링 활성 중 팬으로 뷰포트 중심이 build 커버(_cullVp) 를 크게 벗어나면 260ms 디바운스 rebuild(컬링으로 방출 적어 저렴)로 새로 보이는 컬럼 표시. 마진 0.6 이 소폭 팬을 버퍼.
- 기각/한계: 테이블 자체 컬링은 combo auto-fit(getContentBBox(children))이 카드 축소/점프를 유발해 combo-safe 아님 → 컬럼 컬링으로 한정(테이블 칩 유지). 테이블 수 자체가 지배적인 극단(단일 557T 스키마)의 클릭 floor 는 잔존 — 테이블 칩 draw 는 남음. 후속(combo 분리 필요, 시각검증 하에).
- 검증: headless `test_g6build_viewportcull.js` **6 PASS**(컬럼 컬링·**combo-safe 테이블 유지**·band-invariant·게이트) + 회귀 134 = **140 PASS**. diff 2렌즈 적대 리뷰 + **win-browser 실 Windows Chrome 육안 검증**(집계 카드 가독·마커 없음·줌인 컬링 draw 감축·combo 유지 — TEST §65).
- Supersedes: — (§63 집계에 크기·마커 피드백 반영 + §61 col-LOD 를 뷰포트 축으로 확장) / Superseded By: —


## ADR-033 — §67 집계-카드 폐기 + 카테고리 밴드 규모표시 + 테이블/클러스터 뷰포트 컬링 (사용자 육안 피드백)
- 상태: 채택 (2026-07-10)
- 맥락: §65 배포 후 사용자 실화면 피드백 — 집계-카드(§63/§65)가 클러스터를 작은 카드로 강등해 **규모·구조 파악을 어렵게** 한다("사람이 알아보기 힘들며 기존 규모를 알기 어렵다"). 요청: **스키마 클러스터는 펼친 상태 유지 + 제품 카테고리 밴드에 각 요소 개수 표시(규모 명시) + 관계선 유지**. 또한 '줌인 성능 저하'는 여전히 잔존(§65 컬럼 컬링은 테이블 칩 floor 를 못 줄임). **시각검증 가능**(win-browser relay) 확인 → combo 거동 육안 확인하며 테이블 컬링 구현.
- 결정:
  - **(A1) 집계-카드 폐기**: `aggActive` 상시 false(§63/§65 집계 강등·supernode 경로 비활성화, 코드 보존·가역). 클러스터는 극단 줌아웃에서도 펼침 유지.
  - **(A2) 카테고리 밴드 규모표시**: 제품 카테고리 밴드 헤더(CATH)를 "🗂 label · N DB" → "🗂 label · N DB · M 테이블"(M=멤버 schemaTotals 합, 천단위). 규모를 상위 밴드 카운트로 전달.
  - **(B) 테이블/클러스터 뷰포트 컬링(§65 컬럼→테이블 확장)**: `_cullActive`(nodes>400·!agg·뷰포트 API) 시 화면(뷰포트+마진 0.6) 밖 **테이블 칩 자체**(+컬럼·ctl)와 **전체 화면 밖 클러스터 통째**(combo 포함)를 미방출 → 줌인 대형모델 draw 급감(병목=방출 요소 수). 화면 밖이라 시각 손실 0. 엣지 끝점은 renderEndpoint 로 승격/드롭. 부분 가시 클러스터는 combo 방출 + 가시 테이블만(combo auto-fit). 카테고리 밴드 bbox 는 선산정이라 컬링 무관(규모 밴드 유지). 팬 재-emit(_cullVp, 260ms 디바운스).
- 트레이드오프: 클러스터 펼침 유지로 극단 줌아웃(전체 in-view)은 집계보다 무거움(사용자가 구조·규모 이해를 우선). 완화: 카테고리 접기(기존 §55) + 줌인은 컬링으로 경량. 부분 가시 클러스터의 combo auto-fit 축소는 시각 트레이드오프(육안 확인).
- 검증: headless `test_g6build_viewportcull.js` **6 PASS**(테이블 컬링·band-invariant·게이트) + `test_g6build_agglod.js` **8 PASS**(집계 비활성 잠금) + 회귀 = **150 PASS**. diff 2렌즈 적대 리뷰 + **win-browser 실 Windows Chrome 육안**(집계off·밴드 카운트·테이블 컬링 perf·combo — TEST §67).
- Supersedes: **§63 ADR-030 집계-카드 + §65 ADR-032 supernode(비활성)** / Superseded By: —


## ADR-034 — §69 AI 능동 분석 "주의" 계약 재설계 + 루틴 payload 보강 + 시드 커버리지 (사용자 전수 피드백)
- 상태: 채택 (2026-07-10)
- 맥락: 사용자가 그래프뷰에서 mssql-qa-idc/cc_data_main 능동 분석(run 1519cf95) 결과 "대부분 노드의 '주의' 항목이 불명확하다는 내용"이라 보고. PG 전수 조사(done 536): caveats 가 **Table 71%·Routine 56%** 가 "메타데이터 불완전·직접 검토 필요·불명확" 계열 자기-불평이며 Table/Routine 빈 caveats 0건. params·참조테이블이 payload 에 정상 도달한 루틴조차 불평 — 도메인 위험이 명확한 DELETE 프로시저 등만 양질 주의 생성. 근본원인: **caveats 프롬프트 계약이 모호해("데이터 품질/민감정보/주의점, 없으면 빈 문자열") LLM 이 도메인적으로 할 말이 적을 때 "내가 받은 입력이 불완전하다"는 자기-불평으로 필드를 채우고, "메타데이터 불완전"은 항상 참이라 절대 비지 않음.** 증폭요인 ① 루틴 `returns` 미투영 + 참조테이블이 무구분 `other` 로만 흘러 read/write 소실(프롬프트 "the tables it touches" 약하게만 뒷받침) ② `SCHEMA_CAP=200` 시드 캡이 cc_data_main(555객체) 등 대형 스키마에서 156객체를 조용히 미커버(run 은 done 표시 — "중단" 오인). 원천 데이터 공백(cc_data_main 은 column_descriptions·table_descriptions 0행 — 큐레이션 미적재)은 별개 상류 이슈로 후속 분리.
- 위험등급: Major(다중파일 백엔드 + 출하 기능 + 재생성 LLM 외부비용). 사용자 결정(AskUserQuestion 2026-07-10): 코드 P1+P2, 재생성 cc_data_main.
- 결정:
  - **(P1) caveats 프롬프트 계약 재설계** [`llm.py` NODE_ANALYSIS_PROMPT]: caveats 를 **운영자 대상 데이터/도메인 리스크**(민감·개인·현금성 데이터, 파괴적/비가역 작업, 입력에서 가시적인 데이터품질 위험, 핫패스·대용량)로 엄격 한정. **입력 메타데이터의 불완전/누락/공백 언급, "스키마·정의·소스 직접 확인/검토 필요", "불명확·판단 불가" 류 자기-불평 절대 금지.** 진짜 위험 없으면 빈 문자열(대부분 평범한 노드는 빈 값이 정답·filler 문장보다 강하게 선호). 병행 "Analyze-from-what-is-visible" 규칙 — 희소 컬럼/파라미터/빈 설명은 큐레이션 subset 의 정상 상태이지 결함 아님, 명명 관례로 도메인 의미 추론.
  - **(P2) 루틴 payload 보강** [`node_analysis.py`]: Routine focus 에 대해 ROUTINE_USES `relation_type` 로 `touches:[{table, access:read|write}]` 구조화 투영 + `returns`(routine_objects SSOT 1회 조회 — 그래프 Routine 노드는 returns 미투영). 프롬프트가 약속한 "name, parameters and the tables it touches" 를 실제로 뒷받침해 루틴 분석이 이름만으로 굶주리지 않게 함.
  - **(P3) 시드 커버리지** [`shared/config.py`]: `AGENT_NODE_ANALYSIS_SCHEMA_CAP` 200→1000, `SCHEMA_MAX` 500→2000, `SCHEMA_RUN_BUDGET_MAX` 2500→4000, `BATCH_PER_TICK` 4→10. 현실적 게임 스키마(수백 객체)를 1회 run 으로 전량 시드(§55 "DB 하위 전 노드 분석" 목표 정합). 비용 가드는 UI dry_run confirm(대상 수 표시) + node_budget(재귀 폭증 캡) 이 유지. BATCH 상향은 순차 처리량 개선(워커는 틱 내 순차 호출 — 동시 LLM 부하 무증가).
- 트레이드오프/한계: caveats 를 빈 값 허용으로 바꾸면 "정보 없음" 신호가 줄지만, 그 신호는 원래 운영자에게 무가치한 노이즈였음(자기-불평). 원천 데이터 공백(컬럼·테이블 설명 미적재)은 이 변경 범위 밖 — 프롬프트가 불평을 멈출 뿐 실질 풍부화는 상류 큐레이션/인트로스펙션 후속 필요. 초대형(>SCHEMA_MAX=2000) 스키마는 여전히 capped 표시 + 재실행 드레인. 기존 저장된 나쁜 caveats 는 재분석(only_missing=false) 으로만 교체됨.
- 검증: `make test`/직접 pytest **PYTEST_RC=0**(feature-0002+0003 전체 회귀 0). **라이브 LLM**(container shadow-load + 프롬프트 monkeypatch): 희소 Table 주의 `''`, Get 루틴 → 민감데이터 권한/감사 주의, Delete 루틴 → 비가역 손실 주의(양질 유지) — 자기-불평 전멸. **라이브 payload**: touches read/write 정확 구분 + returns 투영. POST-DEPLOY: cc_data_main 재생성 후 표본 caveats + 커버리지(555) 재확인(T69.5).
- Supersedes: — / Superseded By: —
