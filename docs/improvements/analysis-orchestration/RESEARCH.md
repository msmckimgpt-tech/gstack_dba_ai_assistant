# AI 능동 분석 구조 재설계 — 진단 · 리서치 · 설계안

작성: 2026-07-30 · 대상: feature-0016-metadata-graph (코드 거주 feature-0002 `modules/node_analysis.py`·`semantic_cluster.py`·`insight.py`)
상태: **설계 제안 (미구현)** — 실제 변경은 사용자 승인 후 worktree cycle

---

## 1. 현행 구조 실측 (코드 + 라이브 PG)

### 1.1 파이프라인 실체

```
[웹 트리거]  enqueue_analysis(node)            ← 그래프 뷰 노드 우클릭
             enqueue_schema_analysis(schema)   ← DB 단위 (테이블+루틴 전량 시드)
             enqueue_change_analysis(...)      ← 구조 변동 자동 재분석(SchemaAuto)
                    │
                    ▼  node_analysis_runs / node_analysis_jobs (PG 큐, FOR UPDATE SKIP LOCKED)
[insight-worker tick]  process_pending()
                    │  claim: ORDER BY depth ASC, relevance DESC, created_at ASC
                    ├─ _gather   : _fetch_context(1-hop) + _load_anchor + _build_payload
                    ├─ _run_llm  : llm_node_analysis (haiku, 1 call/노드, concurrency 1~8)
                    └─ _persist  : jobs.analysis 저장 → _ingest_suggested_links
                                   → _backrefine_neighbors(thin 재-pending)
                                   → _enqueue_neighbors(앵커 관련도 게이팅 BFS)
[별 스레드]  semantic_cluster.run_cluster_maintenance()  ← 시그니처 임베딩 + mutual-kNN 클러스터 + LLM 라벨(32자)
             product_classify.run_classify_pass()        ← 제품 분류 제안
```

사용자 진단("단발성 분석 후 유사 노드 재귀 = 일차원")은 **정확하다**. 단 그 일차원 안에서는 이미 상당히 정교하다:

- 앵커-상대 관련도 게이팅(`_relevance`) — content 신호(테이블 서브트리·토큰 겹침·용어·ROUTINE_USES) 없으면 재귀 탈락, 구조 신호는 부스터만
- depth 별 임계 상향(허브 fan-out 억제), 예산 캡(`depth_budget`/`node_budget`, `FOR UPDATE` 원자화)
- **refine-not-override** — `previous_analysis` 동봉 후 융합(덮어쓰기 금지)
- **back-refine** — 인접 노드가 나중에 분석되면 빈약(thin) 분석을 `pass_no+1` 로 재-pending
- suggested_links → `table_relationships` candidate 적재 → 프로브·자기교정이 판정(= 이미 부분적 검증 루프)
- 재시도 backoff + 회로차단 + lease reclaim + 병렬도 런타임 조절

### 1.2 라이브 수치 (2026-07-30, `agent_kb`)

| 지표 | 값 |
|---|---|
| jobs | 10,925 (done 10,215 · failed 580 · pending 130) |
| runs | 36 (running 9 · done 27) |
| 라벨별 done | Column 5,146 · Table 2,553 · Routine 2,506 · Schema 9 |
| depth 분포 | d0 3,607 · d1 4,590 · d2 2,018 (재귀 실작동) |
| back-refine | pass_no≥1 = 403 (4%) |
| summary 평균 길이 | **94자** · 120자 미만 = **8,984 / 10,215 (88%)** |
| relationships 공란·"연결 정보 없음" | 51 (0.5%) |
| caveats 비공란 | 4,092 (40%) |
| rag_objects | 17,532 (클러스터 부여 15,643 · 89%) |
| 컨텐츠 클러스터 | **727개** (라벨만 32자, 요약 없음) |
| LLM 비용 (task=node_analysis, 07-01~07-30) | **10,620 call · prompt 21.8M tok · completion 15.4M tok** — 전 task 중 1위 |
| 테이블 커버리지 | Table done 2,553 / rag_objects 17,532 ≈ **14.6%** |

### 1.3 구조적 공백 4가지

**(A) 상향 합성(집계) 층이 없다 — 사용자가 지적한 그 자리**
727개 컨텐츠 클러스터에 32자 라벨만 있고 **클러스터 요약이 없다**. 스키마(DB)·제품·플랫폼 수준 요약도 없다.
노드 1만 건의 분석문이 상위 의미로 접히지 않아, "이 DB 는 무엇을 하는가", "결제 도메인은 어떤 테이블군으로 구성되는가" 같은 **전역 질문에 답할 자산이 없다**. 노드→노드 재귀만으로는 원리적으로 만들 수 없는 정보다.

**(B) 증거(evidence) 층이 없다 — 정확도 상한의 근원**
`_build_payload` 가 싣는 것: label·name·fqn·description·이웃(컬럼 40·참조 30·용어 20·기타 20)·(Routine 은 params/returns/touches).
없는 것: **row count · 카디널리티 · null 비율 · 값 분포 · 샘플값 · 통계적 키 후보**.
프롬프트(`NODE_ANALYSIS_PROMPT`)는 그 공백을 "이름 규칙에서 추론하라"(`CT_*`/`DT_*`/`sp_*`/`*_log`)로 메우고, caveats 에 "불명확·확인 필요" 를 쓰지 말라고 **명시 억제**한다. 즉 모델은 모를 때 모른다고 말할 수 없고 이름에서 추측해야 한다.
summary 평균 94자·88% thin 은 그 결과의 지표다 (계약이 "1~2문장" 이라 짧은 것 자체는 의도지만, 밀도가 이름 수준을 넘지 못한다).

**(C) 검증 층이 없다**
분석문 자체의 사실성을 확인하는 단계가 없다. 검증되는 것은 `suggested_links`(끝점 실재 + 프로브)뿐이다.
feature-0021 red-team 자가 리뷰는 **대화 답변 전용 choke-point**(`agent_core` `result["answer"]` 직후)라 능동 분석에는 적용되지 않는다. 실패 580건 중 상당수는 transient 로 분류·회수 대상이지만, "성공했으나 틀린 분석문" 은 아무 게이트도 통과하지 않는다.

**(D) 전역 계획이 없다**
무엇을 먼저 분석할지 결정하는 전역 우선순위(중심성·실제 쿼리 사용 빈도·미분석 커버리지·신선도)가 없다. 트리거는 사용자 클릭 / DB 전량 / 구조 변동뿐이다. 그래서 커버리지 14.6% 가 "사람이 눌러본 곳" 편향으로 남는다.

**(E) 분석 산출물의 소비 경로가 얇다**
`node_analysis_jobs.analysis` 소비처: 그래프 뷰 표시(`get_node_analysis`) · `semantic_cluster` 시그니처 · `product_classify` 분류 근거 · `metadata_graph.search_nodes` 부분일치 · `graph_navigate` 도구.
**대화 답변의 자동 grounding 주입 경로에는 없다** (`kb_retrieval`/`knowledge` 에서 참조 0). 즉 1개월 $100 규모로 만든 지식이 assistant 의 기본 컨텍스트로 되돌아오지 않는다. 도구를 호출할 때만 닿는다.

---

## 2. 사용자 제안(오케스트레이터가 분석AI 파견 → 집계) 평가

**결론: 방향은 맞다. 다만 "LLM 오케스트레이터"는 최선이 아니다.**

### 2.1 근거

- Anthropic 멀티에이전트 실측: lead agent + subagents 가 단일 Opus 대비 **+90.2%**. 단 **chat 대비 토큰 15배**. 적합 조건 = 병렬화 가능 · 정보량이 단일 컨텍스트 초과 · 복잡한 도구 상호작용. 부적합 = shared context 필요 · 에이전트 간 강한 상호의존.
- 2026 프로덕션 조사: orchestrator-worker 가 토폴로지의 ~70%. 그러나 "승리 조합" 은 **결정적 백본이 흐름을 잡고 LLM 은 특정 스텝에만** 투입. 중앙집중 멀티에이전트는 토큰 오버헤드 ~285%.
- 스키마 분석은 노드 독립성이 높아 병렬화 이득이 크다 — 그런데 **우리는 그 fan-out 을 이미 갖고 있다**: PG 큐 + `SKIP LOCKED` claim + `node_analysis_concurrency` 1~8 + 예산 캡. "파견" 부분은 구현되어 있다.
- 따라서 LLM 오케스트레이터를 얹어서 **새로 얻는 것은 없고**, 비용·비결정성·디버깅 난이도만 올라간다. 특히 이 프로젝트는 라이브=운영이고 cache-key 변경 1건이 ~2,000 LLM 호출 폭주를 낸 이력이 있다(AGENTS.md §16.3 blast-radius 게이트의 배경).

### 2.2 오케스트레이터의 세 기능을 분리하면 답이 나온다

| 기능 | 결정적(코드)이 나은가 LLM 이 나은가 | 현행 |
|---|---|---|
| (a) 계획·예산 배분 (무엇을 먼저·얼마나) | **결정적** — 중심성·커버리지·신선도·사용빈도는 계산 문제. 재현 가능·무료 | 없음 |
| (b) 집계·합성 (하위 분석 → 상위 의미) | **LLM** — 자연어 합성은 LLM 고유 영역 | 없음 |
| (c) 검증 (사실성·일관성) | **LLM(소형) + 결정적 프로브 혼합** | suggested_links 만 |

→ 권고: **결정적 오케스트레이터(코드) + 계층 LLM 워커 + LLM 합성·검증**.
LLM 리드 에이전트는 "사용자가 특정 의문을 던지는 탐색 모드" 에만 선택적으로 둔다(§4 Phase 6).

---

## 3. 웹 리서치 — 대규모 관계 구조 분석의 모범 구조 (DB 밖 포함)

| 패턴 | 출처 | 핵심 메커니즘 | 우리 프로젝트 적용점 |
|---|---|---|---|
| **GraphRAG (Local→Global)** | MS Research, arXiv 2404.16130 | Leiden **계층** 커뮤니티 탐지(C0~C3) → 커뮤니티 요약 사전 생성 → 질의 시 map-reduce(부분답변 → 순위 → 통합). 루트 요약이 원문 대비 **토큰 97% 절감** | 727 클러스터 위에 **계층 요약** 신설. (A) 공백의 정본 해법 |
| **LazyGraphRAG** | MS Research | 사전 요약 **0**. 인덱싱 비용 = 벡터 RAG 수준(full GraphRAG 의 0.1%), 전역 질의 **700배 저렴**, 품질은 동급~상위 | 상위 요약을 **전량 사전생성하지 말고 필요 시 합성 + 캐시**. 비용 폭주 방지의 핵심 교훈 |
| **RAPTOR** | 재귀 요약 트리 | GMM 클러스터 → 재귀 요약 트리, 다층 질의 | 계층 구성의 대안 형태(우리는 이미 임베딩 클러스터가 있어 GraphRAG 형에 가깝다) |
| **DBAutoDoc** | arXiv 2603.23050 (2026) | **미문서화 스키마 자동 문서화**: 통계 키 발견 ↔ 반복 LLM 정제의 **양방향 피드백 루프**, 스키마 의존 그래프로 의미 전파, **수렴까지 다중 패스**. 결정적 파이프라인이 LLM-only FK 탐지 대비 **F1 +23p**, 종합 96.1% | 우리 문제와 **정확히 같은 문제**. (B) 증거층 + 우리 refine 루프의 레퍼런스 |
| **Semantic layer for LLM** | Coalesce / arXiv 2604.25149 | 엔티티·메트릭·조인·정책을 한 번 정의해 전역 재사용 → LLM 정확도·환각 개선 | 우리 KB 메타데이터가 이미 그 방향. 계층 요약이 그 층의 상단 |
| **대규모 스키마 text-to-SQL** | Spider 2.0 / CHESS / AutoLink / LinkAlign | 스키마 700~3,000 컬럼. **스키마 프루닝이 미해결 문제**. CHESS = retrieval·pruning·후보생성·검증 다중 에이전트 | 분석 산출물의 **최종 소비처** = 프루닝 품질. (E) 공백 해소의 목적지 |
| **LLM-as-judge / self-consistency** | Zylos 2026 조사 | 프로덕션 팀 절반 이상이 런타임 판정 LLM 사용. 소형 판정자(3~8B)가 **비용 97% 절감 · 정확도 0.88~0.95**. 6 패턴(offline eval / online verifier / self-consistency / reflexion / constitutional / inference-time RM) | (C) 검증층을 **haiku 급 소형 판정자**로. 우리 red-team 패턴 재사용 |
| **증분 인덱싱** | GraphRAG update(0.4+) / EraRAG / CocoIndex | delta 계산 후 **영향 부분만** 재분할·재요약(surgical update) | 이미 `enqueue_change_analysis` 있음 → **상위 요약 무효화**로 확장 |
| **결정적 백본 + LLM 스텝** | Anthropic "Building Effective Agents" / 2026 워크플로 조사 | 순서를 미리 쓸 수 있으면 워크플로(코드), 목표만 주고 판단이 필요하면 에이전트. 3단계 초과 순서를 자연어로 강제하면 신뢰성 붕괴 | 오케스트레이터를 **코드로**. 모델 라우팅(경량 스텝=소형 모델)로 비용 60~80% 절감 |

---

## 4. 제안 아키텍처 — 결정적 오케스트레이터 + 4층 상향 파이프라인 + 직교 2축

```
                    ┌──────────────────────────────────────────────┐
                    │  결정적 오케스트레이터 (코드, LLM 0)          │
                    │  · 대상 선정: 중심성 · 사용빈도 · 커버리지 ·  │
                    │    신선도 · 사용자 지정 스코프                │
                    │  · 예산 배분(제품/DB별 캡) · 단계 게이트      │
                    │  · 무효화 전파(delta → 영향 상위 요약)        │
                    └───────┬───────────────────────┬──────────────┘
                            │ 작업 발주             │ 게이트 판정
   ┌────────────────────────▼───────────┐   ┌───────▼───────────────────┐
   │ L0 증거 수집  (LLM 0, 결정적)      │   │ 직교 A — 검증층            │
   │  row count · 카디널리티 · null 비율│   │  소형 판정자(haiku)         │
   │  값 분포 · 샘플값 · 통계 키 후보   │   │  + 결정적 프로브(EXISTS·FK) │
   │  → evidence 저장 (TTL·샘플링)      │   │  → confidence / 재작업 유발 │
   └────────────────────────┬───────────┘   └───────▲───────────────────┘
                            │ 증거 주입                     │ 검증 대상
   ┌────────────────────────▼─────────────────────────┴─────┐
   │ L1 노드 분석  (현행 유지 + 증거 주입 + 렌즈 선택)      │
   │  기존 앵커 게이팅 재귀 · refine-not-override · back-   │
   │  refine 그대로. payload 에 L0 증거 추가.               │
   │  렌즈(선택): 도메인 / 데이터흐름 / 품질·위험           │
   └────────────────────────┬───────────────────────────────┘
                            │ map (노드 분석문)
   ┌────────────────────────▼───────────────────────────────┐
   │ L2 클러스터 합성  (727 컨텐츠 클러스터)                │
   │  멤버 분석문 → 클러스터 요약(역할·핵심 테이블·조인     │
   │  경로·주의) — map-reduce. 라벨(32자)의 상위 자산       │
   └────────────────────────┬───────────────────────────────┘
                            │ reduce
   ┌────────────────────────▼───────────────────────────────┐
   │ L3 도메인 합성  (스키마/DB → 제품 → 플랫폼)            │
   │  "이 DB 는 무엇인가" · 도메인 지도 · 크로스-DB 흐름     │
   └────────────────────────┬───────────────────────────────┘
                            │
   ┌────────────────────────▼───────────────────────────────┐
   │ 소비처 (E 공백 해소)                                    │
   │  · 그래프 뷰: 클러스터·스키마 카드에 요약 표출          │
   │  · 대화 grounding: knowledge context 에 계층 요약 주입  │
   │  · 스키마 프루닝: 대규모 스키마에서 후보 축약           │
   │  · product_classify / 용어사전 자율수집 근거 강화       │
   └────────────────────────────────────────────────────────┘
   직교 B — 증분 무효화: 구조/데이터 변동 → 영향 노드 재분석
            → 그 노드가 속한 클러스터·스키마 요약만 재합성 (전량 금지)
```

### 4.1 각 층의 설계 요지

**L0 증거층 (LLM 0) — 적응형 부하 (사용자 결정 2026-07-30)**
- 수집: `row_count`(근사 우선), 컬럼별 `distinct_count`/`null_ratio`/`min·max`/대표 샘플값 N개, 통계적 키 후보(UNIQUE 성립, 포함 관계 FK 후보)
- 저장: 신규 테이블(expand-only). TTL + 변동 감지로 재수집 억제
- 기대: **LLM 비용 증가 0** 으로 정확도·caveats 실질화. DBAutoDoc 의 "결정적 FK 탐지 +23p F1" 이 근거
- **부하 정책 = 보수적 시작 → 관측 기반 점진 상향 (§4.3 별항)**. 관측층이 **선행 조건**이며, 관측 없이 수집 단계를 올리지 않는다

### 4.3 L0 부하 관측 + 적응형 제어 (사용자 결정: "보수적 시작 → 점진적 적극 탐색, 부하 관측 구조 선행")

**Phase 0 — 관측층 (선행 필수, LLM 0)**

datasource 별 부하 신호를 상시 수집·노출한다. 신규 계측을 처음부터 만들지 않고 **기존 자산을 우선 재사용**한다:

| 신호 | 원천 | 신규 부하 |
|---|---|---|
| 평균 연결 응답시간 (이동평균 20) | `conn_health` — feature-0003 `ds-avg-latency` 가 이미 계산 | **0** (추가 probe 없음) |
| 워커 자체 쿼리 지연 p50/p95 | feature-0026 계측 패턴(`perf_counters`) 을 datasource 축으로 확장 | 0 (자기 계측) |
| 활성 세션·실행 중 쿼리 수 | MySQL `SHOW GLOBAL STATUS`(`Threads_running`) · MSSQL `sys.dm_exec_requests` count | 극소 (초당 1회 미만, 카탈로그 조회) |
| 잠금·대기 | MySQL `Innodb_row_lock_waits` 델타 · MSSQL `sys.dm_os_wait_stats` 델타 | 극소 |
| 복제 지연(있으면) | `SHOW REPLICA STATUS` / MSSQL AG 지연 | 극소 |
| 우리 쪽 풀 압력 | pgbouncer/`db_per_req`(feature-0026) — §82 풀 소진 사고의 조기 신호 | 0 |

- **baseline 학습**: 신호별로 유휴 구간 분포를 학습해 기준선을 잡는다(초기 N일). 절대 임계 대신 **baseline 대비 상대 악화율**로 판정 — 데이터소스별 성능 차이를 하드코딩하지 않는다.
- **노출**: 관리 콘솔 `감사 > AI 운영 현황` 에 datasource 별 [현재 단계 · 최근 신호 · 감속/승격 이력] pane. 신규 권한 0(`console.aiops.read` 재사용).
- **원칙**: 관측 자체가 부하가 되지 않아야 한다 — 카탈로그·상태변수 조회만, 사용자 테이블 스캔 금지.

**Phase 1 — 적응형 수집 제어 (AIMD)**

```
Stage 0  메타데이터만        : information_schema / sys 카탈로그 (근사 row count·인덱스·NULL 허용). 사용자 테이블 read 0
Stage 1  경량 샘플          : 테이블당 LIMIT 100 · 동시 1 · datasource 당 초당 1 쿼리 이하
Stage 2  표준 샘플          : LIMIT 1,000 (업계 기본값) · 동시 2
Stage 3  컬럼 실계산        : 표본 위 distinct/null 집계 · 동시 2~4
Stage 4  정밀              : 대형 테이블 근사 대신 실계산(운영자 명시 승격만)
```

- **승격(additive increase)**: 직전 창(예 15분) 동안 모든 신호가 안전 구간이고 자체 쿼리 실패 0 이면 **한 단계만** 올린다. 단계 건너뛰기 금지.
- **감속(multiplicative decrease)**: 신호 하나라도 악화 임계 초과 → **즉시 Stage 0~1 로 강하** + cooldown(기본 10분, 기존 `AGENT_INSIGHT_AUTH_COOLDOWN_SEC` 패턴 답습). 감속은 승격보다 항상 빠르다(비대칭 — 안전 방향).
- **하드 상한**: 런타임 설정으로 datasource 별 최대 Stage 를 운영자가 고정 가능(기본 Stage 2). 야간 창은 별 상한.
- **강제 안전장치**(단계와 무관하게 항상):
  - read-only 계정 + 쿼리 타임아웃 강제(MySQL `SET SESSION max_execution_time` — §8.4 선례, MSSQL 쿼리 힌트/`LOCK_TIMEOUT`)
  - `COUNT(*)` 전수 스캔 금지 → 카탈로그 근사 우선, 정밀은 Stage 4 명시 승격만
  - 회로차단: 연속 타임아웃·오류 시 datasource cooldown (MSSQL 18456 조기 skip 패턴 답습)
  - **kill-switch**: 설정 0 = 완전 정지. ⚠️ change-reanalysis `cap==0` 의 기존 결함(신규 트리거만 막고 적재분은 계속 소진)을 반복하지 않도록 **claim 단계에서도 게이트**한다
- **관측 실패 시 동작(fail-safe)**: 부하 신호를 못 읽으면 승격하지 않고 **현재 단계 유지 또는 강하**. "관측 불가 = 안전" 으로 해석하지 않는다.
- **판정 주체는 코드**(결정적). 부하 판단에 LLM 을 넣지 않는다 — 재현성·비용·지연 모두 불리하다.

**L1 노드 분석 (현행 최소 변경)**
- payload 에 `evidence` 블록 추가. 프롬프트의 "이름에서 추론" 지시를 "증거 우선, 증거 없으면 이름 규칙" 으로 완화
- caveats 규칙 유지(자기-불평 금지, ADR-034)하되, **증거 기반 위험**(고카디널리티 개인정보 컬럼·null 비율 이상·orphan FK 실측)을 쓸 근거가 생긴다
- thin 판정(`_analysis_is_thin`, 120자) 재정의 — 현행 88% thin 은 판정 기준과 계약("1~2문장")의 불일치. 길이 대신 **정보 항목 충족도**(역할·조인·용도·위험 중 몇 개가 증거로 뒷받침되나)로 전환 검토
- 렌즈(관점) 분리는 **선택**: 비용 3배가 되므로 기본은 단일 렌즈 유지, 고중요도 노드만 다중 렌즈

**L2 클러스터 합성**
- 입력: 클러스터 멤버(테이블+루틴)의 L1 분석문 요약 + 클러스터 내 조인 그래프 + 대표 통계
- 출력: 클러스터 요약(역할 / 핵심 엔티티 / 대표 조인 경로 / 운영 주의 / 대표 질의 패턴)
- 비용: 727 클러스터 × 1콜 ≈ **노드 1만 건 대비 7%**. 계층 요약은 싸다
- 무효화: 멤버셋 해시 + 멤버 분석 버전 해시(이미 `semantic_cluster` 가 멤버셋-해시 캐시 패턴 보유)

**L3 도메인 합성**
- 스키마(DB) 요약 ~370 + 제품 요약 ~17. LazyGraphRAG 교훈 적용 → **사전 전량 생성 대신 요청·질의 유발 시 합성 + 캐시**
- 크로스-DB 흐름(이미 `ROUTINE_USES` 크로스 참조 1,041건 자산)을 도메인 서사로 승격

**직교 A 검증층**
- 대상 표본화: 고중요도(중심성 상위·개인정보/결제 도메인·suggested_links 보유) + 무작위 표본 N%
- 판정 항목: 분석문의 각 주장이 payload·증거로 뒷받침되는가 / 이웃 분석문과 모순되는가 / 금지 패턴(자기-불평·추측 단정)
- 결과: `confidence` 라벨 + 실패 시 재작업(pass_no+1) 유발. **fail-open**(검증 실패가 분석 소실을 만들지 않음 — feature-0021 규약 답습)
- 모델: 소형(haiku). 근거: 소형 판정자 비용 97% 절감·정확도 0.88~0.95

**직교 B 증분 무효화**
- 기존 `enqueue_change_analysis`(SchemaAuto)를 상위로 확장: 노드 재분석 → 그 노드의 클러스터·스키마 요약만 stale 표시 → 다음 캐드런스에 재합성
- 전량 재생성 금지 게이트(AGENTS.md §16.3 blast-radius 사전측정과 정합)

**오케스트레이터(결정적)**
- 입력 신호: 그래프 중심성(degree·PageRank — AGE 로 계산 가능), 실제 사용빈도(대화 JOIN 학습·`sample_queries`·쿼리 로그), 커버리지 결손, 신선도(구조 변동·데이터 변동), 사용자 지정 스코프·지침
- 출력: 다음 tick 의 작업 목록 + 층별 예산 + 게이트 판정(L1 커버리지 X% 미달이면 L2 합성 보류 등)
- 관측: 층별 진행률·비용·검증 통과율을 관리 콘솔에 노출(feature-0026 perf·ai-ops 자산 재사용)

### 4.2 비용 모델 (현행 실측 기준 추정)

| 항목 | 콜 수 | 비고 |
|---|---|---|
| 현행 L1 (1개월) | 10,620 | prompt 21.8M · completion 15.4M tok |
| L0 증거층 | **0** | SQL 프로파일링 (DB 부하만) |
| L2 클러스터 요약 (1회 전량) | ~727 | 현행의 7% |
| L3 스키마 요약 (1회 전량) | ~370 | 현행의 3.5% |
| L3 제품 요약 | ~17 | 무시 가능 |
| 검증층 (표본 10%) | ~1,000 | 소형 모델 |
| **L1 커버리지 100% 확대** | **+15,000** | 14.6%→100%. **가장 비싼 항목** — 권장하지 않음 |

→ 결론: **계층 합성·검증·증거층은 저렴하고 효과가 크다. 비싼 것은 L1 전량 확대다.**
LazyGraphRAG 교훈대로 L1 은 "중요도 상위 + 질의 유발 lazy" 로 두고, 전역 이해는 L2/L3 계층 요약이 담당하는 것이 비용-품질 최적점.

---

## 4.9 근본 이슈 정의 + 범위 재산정 (설계 리뷰 Step 0 결과, 사용자 지시 2026-07-30)

사용자 지시: **"저렴한 설계보다 근본적인 이슈 해소를 우선"**. 그 기준으로 재정의한다.

### 근본 이슈 (RI) — 실측 근거 동반

| ID | 근본 이슈 | 실측 근거 | 의존 |
|---|---|---|---|
| **RI-1** | **접지 부재** — 분석 입력에 데이터 증거가 없어 *이름 추측*이 사실상 정본. 프롬프트가 "이름 규칙에서 추론" 을 지시하고 "불명확" 표현을 금지 | summary 평균 94자 · payload 에 통계·샘플 0 | RI-2·RI-3 의 **전제** |
| **RI-2** | **합성 부재** — 727 클러스터·~370 스키마에 요약 없음. 노드 1만 건이 상위 의미로 접히지 않음 | 클러스터 라벨 32자만 · 상위 요약 테이블 없음 | RI-1 에 품질 의존 |
| **RI-3** | **검증 부재** — 틀린 분석이 아무 게이트도 통과. RI-1 때문에 틀릴 확률이 구조적으로 높은데 게이트가 없다 | 검증되는 것은 suggested_links 뿐 | RI-1 이후 의미 |
| **RI-4** | **계획 부재** — 전역 우선순위 없음 → 커버리지가 "사람이 눌러본 곳" 편향 | Table 커버리지 14.6% | 독립 |
| **RI-5** | **소비 부재** — 만든 지식이 답변 grounding 에 자동 주입되지 않아 그래프 뷰 안에 갇힘 | `kb_retrieval`/`knowledge` 의 node_analysis 참조 0 | 독립·저렴 |

### 정합성 검토 — 리뷰 Step 0 의 "최소 세트" 권고를 철회

리뷰 Step 0 에서 "L2 클러스터 요약 2슬라이스만" 을 최소 세트로 권고했다. 사용자 우선순위와 대조하면 **불정합**이다:

- L2 만 하면 **RI-2 만** 해소되고 RI-1·RI-3·RI-5 는 남는다.
- 더 중요한 것: **RI-1 을 방치한 채 L2 를 얹으면 "추측의 요약"** 이 된다 (garbage in → summarized garbage out). 접지 없는 상위 요약은 틀린 내용을 *더 권위 있게* 보이게 만들어 오히려 위험하다.
- 따라서 근본 순서는 **RI-1(접지) → RI-2(합성)** 이며, "L2 를 먼저 해서 가치를 앞당긴다" 는 비용 논거는 근본 해소 우선순위에 종속된다. 권고 철회.

### 유효하게 남는 리뷰 findings (비용 논거가 아니라 정확성·안정성 논거)

1. **기존 자산 재사용**은 유지된다 — 신규 모듈을 만들지 않고 `_llm_content_labels`·`conn_health`·`perf_counters`·`enqueue_change_analysis` 를 확장하는 것은 *비용 절감이 아니라 정합성*(SSOT·중복 제거·회귀 표면 축소)이다.
2. **AIMD 반증**도 유지된다 — 비용이 아니라 **발진 위험**이 근거다. AIMD 의 전제(우리가 지배적 부하원 · 빠른 피드백)가 성립하지 않는다: 주간 사용자 트래픽이 지배적이고 신호는 이동평균(지연 큼)이다.
   → **대안(적응형 유지 + 발진 제거)**: 관측 기반 승격을 쓰되 ① 승격은 **하루 최대 1단계**, ② **시간창별 상한 캡**(주간 ≤ Stage1 · 야간 ≤ Stage3), ③ **비대칭 히스테리시스**(승격 판정창 ≫ 감속 판정창), ④ 승격은 관측이 제안하고 **운영자 승인**(콘솔) — 사용자 결정("보수적 시작 → 점진 상향")을 충족하면서 자동 발진을 구조적으로 제거한다.

### 재산정된 범위 — 7 Phase → 3 트랙

| 트랙 | 해소 RI | 내용 | 독립 출하 | 게이트 |
|---|---|---|---|---|
| **A. 접지** | RI-1 | 부하 관측 확장(기존 자산) → L0 증거 수집(적응형·승격 승인제) → L1 payload/프롬프트 접지 → thin 판정 재정의 | 가능 | A 완료 후 **표본 재분석으로 접지 효과 실측**(summary 밀도·caveats 실질성) → B 착수 |
| **B. 합성·소비** | RI-2 + RI-5 | L2 클러스터 요약(`_llm_content_labels` 확장) → L3 스키마/제품 lazy 요약 → 그래프 뷰·`knowledge context`·`graph_navigate` 소비 배선 | 가능 (품질은 A 의존) | 요약에 "멤버 N 중 M 상세분석 근거" 명시 |
| **C. 신뢰·계획** | RI-3 + RI-4 | 검증층(소형 판정자 + confidence, fail-open 이 "미검증"을 "검증됨" 으로 표시하지 않을 것) → 결정적 플래너 → 증분 무효화 상위 확장 | 가능 | A 없이 C 를 먼저 하면 "추측을 검증" 하는 셈 |

- 트랙별 1 cycle(worktree) — 라이브=운영 리스크를 cycle 경계로 관리한다.
- 복잡도 게이트(8파일/2모듈 초과)는 **인지 후 수용**: 사용자가 근본 해소 우선을 명시했고, 트랙 분할로 각 cycle 의 blast radius 를 제한한다.

## 5. 단계적 로드맵 (트랙 A~C 내부 순서)

| Phase | 내용 | 비용 | 기대 효과 | 위험도 |
|---|---|---|---|---|
| **0** | **데이터소스 부하 관측층** (신호 수집 + baseline + 콘솔 pane) — L0 의 **선행 조건** | LLM 0 · DB 부하 극소 | 적응형 제어의 전제. §82 풀 소진류 조기 신호 | Minor |
| **1** | L0 적응형 증거 수집 (Stage 0→4 AIMD · kill-switch · 회로차단) | LLM 0 · DB 부하 통제됨 | 증거 자산 확보 | Major (운영 DB read) |
| **2** | L1 payload 증거 주입 + 프롬프트 완화 + thin 판정 재정의 | LLM +0 (콜 수 불변) | 정확도·caveats 실질화. 88% thin 개선 | Minor~Major |
| **3** | L2 클러스터 요약 + 그래프 뷰·대화 grounding 소비 배선 | ~727 콜 | 전역 질문 응답 가능. "집계" 공백 해소 | Major (신규 LLM 경로) |
| **4** | 결정적 오케스트레이터(플래너) + 층별 진행·비용 관측 | LLM 0 | 커버리지 편향 해소·예산 통제 | Major |
| **5** | 검증층(소형 판정자) + confidence 노출 | ~표본 | "성공했으나 틀린 분석" 게이트 | Major |
| **6** | L3 도메인 합성(lazy) + 증분 무효화 확장 | ~390 콜 | 제품·플랫폼 서사 | Major |
| 7 (선택) | 탐색 모드 LLM 리드 에이전트 (사용자 질문 기반 조사) | 높음 | 사용자 지정 의문 해소 | Major |

우선순위 근거: **Phase 0 이 사용자 결정에 따른 선행 게이트**(관측 없이 수집 상향 금지). Phase 1~2 가 LLM 비용 0 으로 최대 정확도 이득, Phase 3 이 지적하신 "집계" 공백의 직접 해소.
Phase 0~1 을 분리하는 이유: 관측층은 그 자체로 운영 가치가 있고(데이터소스 상태 가시화) L0 없이도 독립 출하 가능 — 리뷰에서 L0 가 반려돼도 Phase 0 산출물은 남는다.

---

## 6. 프로젝트 제약 정합 체크

- **F0 / worktree**: 구현은 `bin/cycle-init.sh` worktree cycle (AGENTS.md §13.2.7)
- **expand/contract**: 신규 테이블·컬럼은 additive only, `bin/migrate-lint.sh` 게이트 (CONVENTIONS §12)
- **blast-radius 사전측정**: 시그니처·캐시키 변경 시 재생성 규모 추정 필수 (§16.3) — 특히 `semantic_cluster` 시그니처에 증거를 넣으면 **전량 재임베딩·재클러스터**가 유발된다. 넣지 않거나 별 필드로 분리
- **기본 OFF opt-in**: 신규 LLM 경로는 런타임 설정 게이트 + 기본값 현행 동등 (feature-0018/0025 관례)
- **권한**: 신규 실행 표면은 `metadata.graph.analyze` 하위 또는 재사용 (SECURITY §19)
- **시각검증**: 그래프 뷰 표출 변경은 PB-0008 필수 (`visual_verification_scope: always`)
- **성능**: L0 프로파일링은 운영 DB read → pgbouncer 풀 소진 이력(§82 flock 사건) 고려, 동시성 캡·야간 창

---

## 7. 사용자 결정 (2026-07-30) 및 잔여 결정

**결정됨**
1. **범위**: 구현 전 **전체 설계 리뷰 선행** — 본 문서를 리뷰에 태운 뒤 구현 착수 여부 결정
2. **L0 부하 정책**: **적응형** — 보수적 시작 → 점진적 적극 탐색. 단 **운영 DB 부하 관측 구조가 선행 조건** → Phase 0 신설, §4.3 설계

**잔여 (리뷰 후 결정)**
3. **커버리지 전략**: L1 전량(+15,000콜) vs 중요도 상위 + lazy(권장)
4. **오케스트레이터 형태**: 결정적만(권장) vs 결정적 + 탐색용 LLM 리드 하이브리드
5. **적응형 승격 판정 파라미터**: baseline 학습 기간·악화 임계·창 길이·기본 최대 Stage

## 9. 리뷰 대상 쟁점 (리뷰어에게 명시)

1. Phase 0 관측층이 **정말 부하 없이** 신호를 얻는가 — `SHOW GLOBAL STATUS`/DMV 폴링 주기와 datasource 수(~21)의 곱
2. AIMD 승격/감속 비대칭이 **운영 시간대 변동**(주간 피크 ↔ 야간)에서 발진(oscillation)하지 않는가
3. baseline 상대 판정이 **점진적 성능 저하**(baseline 자체가 나빠지는 경우)를 놓치지 않는가
4. L2 클러스터 요약의 **무효화 정확성** — 멤버셋 해시만으로 충분한가, 멤버 분석 갱신도 트리거해야 하는가
5. 증거를 `semantic_cluster` 시그니처에 넣지 않는 결정이 **정확도 손실**을 만들지 않는가 (재임베딩 비용 회피 vs 클러스터 품질)
6. 검증층 fail-open 이 "검증 안 된 분석"을 **검증됨으로 오인 표시**하지 않는가
7. L1 커버리지 14.6% 를 유지하는 선택이 **전역 요약(L2/L3)의 대표성**을 훼손하지 않는가 — 미분석 85%가 요약에서 누락되는 문제

---

## 8. 출처

- GraphRAG: https://arxiv.org/pdf/2404.16130 · LazyGraphRAG: https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- DBAutoDoc: https://arxiv.org/abs/2603.23050
- Anthropic 멀티에이전트: https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them · https://www.anthropic.com/research/building-effective-agents
- Spider 2.0: https://spider2-sql.github.io/ · AutoLink: https://arxiv.org/pdf/2511.17190 · LinkAlign: https://arxiv.org/pdf/2503.18596
- LLM-as-judge 프로덕션: https://zylos.ai/research/2026-04-10-llm-as-judge-production-agent-verification-2026/
- 증분 인덱싱: https://www.falkordb.com/news-updates/incremental-knowledge-graph-indexing/
- 세만틱 레이어: https://arxiv.org/pdf/2604.25149

---

## 10. 설계 리뷰 결과 반영 (2026-07-30) — 범위 3차 재산정

### 10.1 리뷰가 무너뜨린 전제 4개 (codex outside voice, 코드 근거)

| # | 무너진 전제 | 코드 근거 | 결과 |
|---|---|---|---|
| 1 | "L2 = `_llm_content_labels` 확장으로 저렴" | `semantic_cluster.py:600`(32자 라벨 계약)·`:668`(labels[] JSON)·`:1009` — 저장 테이블·버전·stale/delete·그래프 투영 계약 없음 | L2 는 **신규 저장 계약 필요**. 단순 재사용 시 32자 절단 또는 라벨 경로 오염 |
| 2 | "Phase 0 관측은 기존 자산으로 추가 부하 0" | `shared/perf_counters.py:1` — 요청 ContextVar 밖은 **no-op**(insight-worker 미제공) · `shared/conn_health.py:438` — 평균은 connect+`SELECT 1` **probe 시간**이지 workload 부하가 아님 | **신규 worker 계측·저장·집계 계약 필요** |
| 3 | "검증층은 feature-0021 red-team 인프라 재사용" | `redteam.py:666`(question+draft answer+evidence digest 전용 프롬프트)·`:1223`(`review_plan()` 이 대화 추론강도 종속) | 능동 분석엔 conversation/question/answer 가 없음 → **사실상 신규 검증 인프라**. 그대로 호출하면 answer 원장 오염 |
| 4 | "플래너 중심성은 AGE 로 계산" | `metadata_graph.py:1538` — 실제 경로는 multi-hop 집계를 **최악 82초**로 판단해 1-hop+Python 우회 | **신규 materialized metric + 갱신주기 + 비용상한 필요** |

### 10.2 리뷰가 추가한 P1 결함 (설계 미비)

- **R-1 보안 미설계 (최중대)**: L0 가 대표 샘플값을 저장하고 L2/L3 가 대화 컨텍스트에 주입하는데, **마스킹·민감컬럼 분류·허용목록·retention·datasource/account RBAC·cross-scope 누출 방지가 정의되지 않았다**. read-only 는 PII 방어가 아니다. 이 프로젝트는 계정·결제·현금성 데이터를 다루고 SECURITY.md §14(datamark)·§30(제품 스코프 격리)를 이미 갖췄으므로, 미설계 주입은 그 경계를 우회한다.
  → **해소: L0 기본 산출물에서 원시 샘플값을 제외한다.** 통계(카디널리티·null 비율·min/max·타입·길이 분포·통계적 키 후보)만 쓴다. DBAutoDoc 의 결정적 이득(FK 탐지 F1 +23p)은 **통계**에서 나오고 샘플값에서 나오지 않는다 — 즉 근본 이슈(RI-1 접지) 해소에 샘플값은 **필수가 아니다**. 샘플값이 필요하면 기존 `kb.sample.curate` 검수 큐(사람 승인)를 경유한다.
- **R-2 증거 변경이 L2 로 전파되지 않는다**: RC4 시그니처에는 L1 `summary+usage` 만 들어가고 `_llm_content_labels` 캐시는 `signature_text_hash` 만 본다. 증거만 갱신되면 임베딩·클러스터·L2 요약이 **stale 인 채 최신처럼 보인다**.
  → 해소: **두 해시를 분리한다.** ① 임베딩 입력 시그니처에는 증거·요약을 **넣지 않는다**(재임베딩 폭주·순환 차단) ② L2 요약 캐시 키 = `member_set_hash + evidence_version + l1_version`. 무효화는 요약 층에서만 일어난다.
- **R-3 클러스터↔요약 일관성 경계 없음**: 멤버를 읽고 LLM 호출 후 나중에 DB 갱신하는 사이 L1 완료·재임베딩·재클러스터가 발생 가능. `_fresh_embeddings_since_mark()`(`:1061`)는 시작 시점 due 검사일 뿐이고 유지보수 루프에 락이 없다(`:1137`) → 서로 다른 클러스터 버전의 멤버·분석문을 합성할 수 있다.
  → 해소: 요약은 **클러스터 버전 스냅샷**(member_set_hash 고정) 위에서만 커밋. 커밋 시 스냅샷 불일치면 폐기·재시도.
- **R-4 입력 순서 비결정적**: 테이블·루틴 조회에 `ORDER BY` 없음(`:833`), 분석문은 앞 5개만(`:949`), 캐시 해시는 멤버 키를 정렬하지만 **payload 순서는 정렬하지 않는다** → 같은 멤버셋인데 DB 반환 순서만 달라도 입력 대표성이 바뀌고 캐시 적중 시 잘못된 이전 결과를 재사용.
  → 해소: payload 구성 전 **결정적 정렬**(key ASC) + 근거 선택도 결정적 규칙(relevance DESC, key ASC).
- **R-5 kill-switch 가 공유 자원 장애를 격리하지 못한다**: 설계의 kill-switch 는 L0 만 멈춘다. 워커에는 conn-health probe·node-analysis 병렬 LLM·embedding·semantic-cluster·관계 추론 스레드가 **별도로** 돈다(`insight.py:3727`·`:3569`). §82 교훈(`docs/LEARNINGS.md:35`)은 작업별 제어가 아니라 **공유 자원 단위 직렬화·격리**를 요구한다.
  → 해소: **트랙 0 신설**(아래).
- **R-6 저부하 프로파일링의 쿼리 안전성 미입증**: `LIMIT 100/1000`·`DISTINCT`·NULL 비율·min/max 는 실행계획에 따라 전체 스캔·대량 I/O 가 된다. timeout·read-only 는 **동시 연결의 풀 점유**를 해결하지 않는다. 테이블별 제한만 있고 **datasource 전체의 쿼리 수·실행비용·동시연결·bytes 예산이 없다**.
  → 해소: Stage 정의를 "행 수"에서 **자원 예산**(datasource 당 동시연결 1 · 분당 쿼리 N · 누적 bytes/시간 상한 · 실행계획 사전 확인 또는 인덱스 있는 컬럼만)으로 재정의.
- **R-7 검증 재작업을 `pass_no` 에 얹으면 상태 의미 충돌**: `pass_no`/`REFINE_MAX`(`node_analysis.py:2085`·`:1461`)는 back-refine(맥락 보강) 전용이다. 검증 실패 재작업까지 같은 필드를 쓰면 "맥락 보강"과 "사실성 실패"를 구분할 수 없고, 재작업마다 RC4 시그니처·임베딩·클러스터가 연쇄 갱신된다.
  → 해소: **별 verification state/version 컬럼** + 독립 비용 상한.

### 10.3 최종 범위 — 4 트랙 (전제 게이트 포함)

```
T0 자원 격리·계측  ──필수 전제──▶  T1 접지  ──품질 전제──▶  T2 합성·소비
   (RI-0 신설)                      (RI-1)                    (RI-2+RI-5)
                                                                  │
                                        T3 신뢰·계획 ◀────────────┘ (독립 출하 가능)
                                        (RI-3+RI-4)
```

| 트랙 | 해소 | 핵심 작업 | 전제 |
|---|---|---|---|
| **T0 자원 격리·계측** (신설) | **RI-0** 공유 자원 전역 예산·직렬화 부재 | 워커 전체(probe·node LLM·embedding·cluster·관계추론·L0)를 **공유 자원 단위**로 직렬화·예산화 + datasource 별 워커 계측 **신설**(perf_counters 재사용 불가 확인) + 전역 kill-switch | — (독립 가치: §82 잔여 위험 해소) |
| **T1 접지** | RI-1 | L0 **통계 전용**(샘플값 배제·검수 큐 경유 옵션) + 자원 예산형 Stage + L1 payload/프롬프트 접지 + thin 판정 재정의 + (결정) 증거 기반 관련도 신호 | T0 |
| **T2 합성·소비** | RI-2 + RI-5 | L2 **신규 저장 계약**(2중 버전 키·시그니처 미유입 불변식·스냅샷 일관성·결정적 입력) + L3 lazy + 소비 배선(주입 상한) | T1 + **일일 토큰 cap**(TODOS.md:39 stale 항목 재평가) |
| **T3 신뢰·계획** | RI-3 + RI-4 | 검증층 **신규**(별 state/version, red-team 원장 미오염) + 플래너(materialized metric·degree+사용빈도부터) | T1 (접지 없이 검증하면 추측을 검증) |

### 10.4 비용 추정 정정

당초 "L0 = LLM 0 이라 싸다 / L2 = 727콜로 현행의 7%" 는 **LLM 비용만 본 추정**이었다. 리뷰 결과 실제 비용 구조는:

- L0: LLM 0 은 맞지만 **보안 설계 + 자원 예산 + 신규 계측**이 붙어 **가장 무거운 트랙**
- L2: `_LABEL_CLUSTERS_PER_CALL=40` 은 32자 라벨 기준이라 요약은 5~8 배치가 상한 → 콜 수는 727 유지되나 **신규 저장 계약·버전·일관성 경계** 구현이 본체
- T0: LLM 0, 순수 구조 작업이나 워커 전역을 건드려 회귀 표면이 넓다

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 12 issues (A 6 · Q 4 · P 3, 중복 제외), test gaps 8 (★필수 2) |
| Outside Voice | codex (독립 적대) | Independent 2nd opinion | 1 | issues_found | 11 findings (P1 8 · P2 3) |

- **CODEX**: 설계의 "기존 자산 재사용" 전제 4개를 코드 근거로 반박 + 보안(샘플 PII) P1 신규 적발 + 무효화/일관성/결정성 3건 적발.
- **CROSS-MODEL**: 3건 tension — ① red-team 재사용(리뷰 A-4 가능 ↔ codex 불가) → **codex 채택** ② `_llm_content_labels` 확장(리뷰 최소세트 ↔ codex 신규계약 필요) → **codex 채택**(사용자 근본해소 우선과도 정합) ③ Phase 0 무부하(문서 주장 ↔ codex no-op/probe 반박) → **codex 채택**. 나머지 8건은 tension 아닌 순수 추가.
- **UNRESOLVED**: 4 — 트랙 착수 순서 승인 · 샘플값 배제 확정 · 증거 기반 관련도 신호 포함 여부 · 일일 토큰 cap 도입 시점.
- **VERDICT**: ENG REVIEW 완료(issues_open) — 범위 3차 재산정 완료, **구현 착수 전 사용자 승인 대기**. 근본 이슈 5개(RI-1~5) + 신설 RI-0 에 4 트랙 매핑, 전제 게이트 명시.

---

## 11. T1 접지 상세 설계 (구현 직전 확정본, 2026-07-30)

트랙 0(T0·T0b·T0c)이 닫혔으므로 자원 게이트(`ds`)와 관측이 갖춰졌다. T1 은 그 위에서 **RI-1 접지**를
해소한다 — 분석 입력에 데이터 증거가 없어 이름 추측이 정본인 구조.

### 11.1 수집 항목 — **통계 전용**(원시 샘플값 배제, 사용자 확정 2026-07-30)

| 대상 | 항목 | 수집원 |
|---|---|---|
| 테이블 | 근사 row count · 인덱스 구성 · PK/FK 선언 | `information_schema.tables/statistics/key_column_usage` (MSSQL `sys.*`) |
| 컬럼 | 타입 · NULL 허용 · 문자 길이 상한 | 카탈로그 |
| 컬럼(표본) | `distinct` 추정 · null 비율 · min/max(수치·날짜) · 길이 분포(문자열) | 표본 `SELECT` |
| 키 후보 | UNIQUE 성립(distinct ≈ row_count) · FK 후보(포함 관계) | 위 산출물의 결정적 판정 |

**원시 샘플값은 저장하지도 주입하지도 않는다.** DBAutoDoc 의 결정적 이득(FK 탐지 F1 +23p)은 통계에서
나오며 샘플값이 아니다. 샘플이 필요하면 기존 `kb.sample.curate` 검수 큐(사람 승인)를 경유한다.
→ PII 표면이 구조적으로 없다(SECURITY §14·§30 경계와 무충돌).

### 11.2 수집 단계 (부하 순 — `ds` 예산 게이트 위에서)

```
Stage 0  카탈로그만        : information_schema / sys — 사용자 테이블 read 0
Stage 1  경량 표본         : 테이블당 LIMIT 100 · 컬럼 집계는 그 표본 위에서
Stage 2  표준 표본         : LIMIT 1,000 (업계 기본값)
Stage 3  정밀(운영자 승격) : 전수 집계 — 대형 테이블은 명시 승격만
```

- 승격은 **하루 최대 1단계** + **시간창 상한**(주간 ≤ Stage1 / 야간 ≤ Stage2) + **운영자 승인**.
  AIMD 를 쓰지 않는 근거는 §4.9(전제 불성립·발진 위험).
- 모든 단계에서 `COUNT(*)` 전수 스캔 금지(카탈로그 근사 우선), 쿼리 타임아웃 강제, `ds` 예산 게이트.

### 11.3 저장 (expand-only)

신규 테이블 `agent_kb.metadata_column_stats` — `(scope_key, schema_name, table_name, column_name)` PK +
카탈로그(`data_type`·`is_nullable`·`char_max_len`) + 표본 통계(`distinct_est`·`null_ratio`·
`num_min`/`num_max`·`ts_min`/`ts_max`·`len_min`/`len_max`/`len_avg`·`value_pattern`) +
`sampled_rows`·`stage`·`collected_at`.
테이블 수준은 `metadata_table_stats`(row_count_est·column_count·pk_columns·index_columns·fk_out·fk_in·
stage·sampled_rows·collected_at·error).
alembic additive(§12 expand/contract) · downgrade 가역.

⚠ **문자열 컬럼의 min/max 값은 저장하지 않는다**(설계 정정 2026-07-30, 구현 시점). 문자열 극단값은
사실상 원시 샘플 1건이며 이름·이메일·주소 컬럼에서는 곧 PII 다 — "원시 샘플값 배제" 확정과 정합하지
않는다. 숫자·시각 타입만 `num_min/num_max`·`ts_min/ts_max` 를 남기고, 문자열은 **길이 분포 +
패턴 클래스**(`value_pattern` ∈ digits|hex|uuid|email_like|mixed|empty — 값이 아니라 형태 분류)로
대체한다. 접지 가치(형식 판별·개인정보 의심 신호)는 유지되고 PII 표면은 사라진다.

⚠ **시그니처에 넣지 않는다** — `semantic_cluster` 의 RC4 시그니처에 증거를 넣으면 전량 재임베딩·
재클러스터가 유발된다(§16.3 blast-radius). 증거 변경은 **L2 요약 캐시 키**로만 전파한다(§10.2 R-2).

### 11.4 L1 주입 + 프롬프트

- `_build_payload` 에 `evidence` 블록 추가(테이블 통계 + 컬럼별 통계 상위 N).
- `NODE_ANALYSIS_PROMPT`: "이름 규칙에서 추론" → **"증거 우선, 증거 없으면 이름 규칙"**.
  `caveats` 규칙은 유지하되 **증거 기반 위험**(고카디널리티 개인정보 의심 컬럼·null 비율 이상·
  orphan FK 실측)을 쓸 근거가 생긴다.
- `_analysis_is_thin`: 길이(120자) → **항목 충족도**(역할·조인·용도·위험 중 몇 개가 증거로 뒷받침되나).
  현행 88% thin 은 계약("1~2문장")과 판정의 모순이며, 캡을 올리면 대량 재분석이 폭주한다(§10.2 Q-1).

### 11.5 미결(구현 중 판정)

- `_relevance` 의 content 신호에 **증거 기반 항**(FK 실측 카디널리티·값 겹침)을 넣을지 —
  넣지 않으면 접지가 L1 서술에만 들어가고 탐색 방향은 이름이 계속 결정한다(§10.2 Q-2).
  1차는 넣지 않고(회귀 표면 축소), 접지 효과 실측 후 별 슬라이스로 판단한다.

### 11.6 완료 판정

- 표본 재분석에서 summary 밀도·caveats 실질성이 개선됨을 **실측 대조**(전/후 동일 노드 N개).
- 증거 수집이 `ds` 예산 안에서 동작(거절 시 다음 주기 이월, 운영 DB 부하 신호 무변화).
- 원시 샘플값이 저장·주입되지 않음을 구조 테스트로 단정(PII 표면 부재).
