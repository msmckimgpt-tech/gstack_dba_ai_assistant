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
