---
doc_type: INSIGHTS
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: true
---

# Schema / Table Insight System

## 1. 이 문서의 목적

`agent-core`에는 사용자가 질문하지 않은 상황에서도 **스키마/테이블 메타데이터를 자동으로 분석·캐싱하는 백그라운드 시스템**이 존재한다. 이 시스템은 질의 품질과 응답 속도에 직접 영향을 주지만, 지금까지 코드 주석 외에는 공식 문서가 없었고, 로그와 워커 프로세스가 관측될 때 사용자가 "서비스 오류"로 오해하는 경우가 있었다.

이 문서는 그 오해를 걷어내기 위해 **Insight 시스템이 무엇이며, 어떤 경로로 실행되고, 어느 로그·신호가 정상이며, 어떻게 상태를 점검할 수 있는지**를 정리한다.

## 2. 한 줄 요약

> Insight 시스템은 **DB 스키마와 주요 테이블의 역할을 LLM으로 요약해 에이전트 메모리에 캐싱**하는 기능이다. 캐싱된 요약은 매 질의에 `KNOWN SCHEMAS & TABLES` 블록으로 주입되어, LLM이 `search_tables`/`describe_table` 같은 탐색 도구를 호출하지 않고 곧바로 `execute_sql`로 답을 만들 수 있게 한다.

## 3. 사용자 영향 (왜 필요한가)

- **탐색 단계 감소** — 캐싱된 인사이트 없이 질문이 들어오면, LLM은 테이블을 찾기 위해 `search_tables` → `describe_table`을 여러 번 반복한다. 인사이트가 있으면 첫 도구 호출이 바로 `execute_sql`이 된다. 이 최적화는 `SYSTEM_PROMPT`의 "CRITICAL DIRECTIVE"와 `TOOL_DEFINITIONS` 우선순위와 짝을 이룬다([AGENT_CORE_INTERNALS.md](./AGENT_CORE_INTERNALS.md#2-system_prompt-%EC%A4%91%EC%9D%98-%EB%8B%A4%EC%84%AF-%EB%B8%94%EB%A1%9D)).
- **응답 품질 향상** — 스키마의 도메인(예: "Account/Auth")과 테이블의 용도가 컨텍스트로 주입되므로, LLM이 잘못된 테이블을 선택할 확률이 줄어든다.
- **사용자 설정 불필요** — 운영자가 테이블을 일일이 기술할 필요가 없다. 워커가 스키마를 스캔하고 LLM이 요약한다.

## 4. 아키텍처 개요

```
┌───────────────────────────────────────────────────────────────┐
│ repo-insight-worker (컨테이너)                                │
│   └─ run_insight_worker_loop()   ← tick_sec 간격 무한 루프    │
│        └─ run_insight_cycle()     ← 한 번의 사이클            │
│             ├─ _acquire_advisory_lock()  (MySQL GET_LOCK)     │
│             ├─ _bootstrap_schema_insights()  (초기 1회)        │
│             └─ _scan_instance_schema_insights()  (주기 변경분) │
│                                                               │
│  ┌── MEMORY DB (agent_memory) ───────────────────────────┐    │
│  │ AgentMemoryFactEntries + AgentMemoryTexts             │    │
│  │   - schema_insight:<schema>                           │    │
│  │   - table_insight:<schema>.<table>                    │    │
│  │ agentmemorykv                                         │    │
│  │   - schema_fp:<schema>               (fingerprint)    │    │
│  │   - table_fp:<schema>.<table>        (fingerprint)    │    │
│  │   - schema_insights_bootstrap_at                      │    │
│  │   - schema_instance_scan_at                           │    │
│  │   - insight_worker_last_cycle_at / _status / _error   │    │
│  └───────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────┘
                          │ 질의 시
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ agent_core._build_knowledge_context()                         │
│   → "## KNOWN SCHEMAS & TABLES" 블록을 system 프롬프트에 주입  │
└───────────────────────────────────────────────────────────────┘
```

## 5. 실행 경로

### 5.1 백그라운드 워커 — 정상 경로

- 엔트리포인트: [insight.py:1400 `run_insight_worker_loop()`](../src/modules/insight.py#L1400)
- 사이클 본체: [insight.py:1260 `run_insight_cycle()`](../src/modules/insight.py#L1260)
- 주기: `AGENT_INSIGHT_WORKER_TICK_SEC`(기본 8초, 최소 5초). 시작 시 `AGENT_INSIGHT_WORKER_JITTER_SEC`만큼 랜덤 지연.
- 동시 실행 방지: 사이클 진입 시 `_acquire_advisory_lock()`으로 MySQL `GET_LOCK(:name, :timeout)`을 건다. 다른 인스턴스가 이미 사이클을 돌고 있으면 `status=skip_locked`로 즉시 종료한다.

### 5.2 사이클 내부 단계

1. **Known schemas 로드**: `load_known_schemas()`로 `AgentMemoryFactEntries`에 기록된 알려진 스키마 목록을 읽는다.
2. **Bootstrap(최초 1회)**: [insight.py:556 `_bootstrap_schema_insights()`](../src/modules/insight.py#L556). `AGENT_SCHEMA_BOOTSTRAP=1`이고 `schema_insights_bootstrap_at` KV가 비어있을 때만 실행. 스키마 목록과 상위 `AGENT_SCHEMA_BOOTSTRAP_MAX_TABLES`(기본 50)개 테이블에 대해 **초기 인사이트를 LLM으로 생성**하고, 완료 시 `schema_insights_bootstrap_at` KV에 ISO 시각을 기록해 재진입을 차단한다.
3. **Instance scan(주기적 변경 감지)**: [insight.py:617 `_scan_instance_schema_insights()`](../src/modules/insight.py#L617). 각 스키마에 대해 현재 fingerprint를 계산([insight.py:28 `_compute_schema_fingerprint()`](../src/modules/insight.py#L28))하고, KV에 저장된 이전 fingerprint와 비교한다. 동일하면 스킵, 달라지면 해당 스키마의 변경된 테이블만 LLM으로 재요약한다.
4. **Heartbeat 기록**: 사이클 종료 시 `insight_worker_last_cycle_at`, `insight_worker_last_status`(`ok` / `skip_locked` / `error`), `insight_worker_last_run_id`, `insight_worker_last_error`, `insight_worker_last_duration_ms` KV를 갱신한다.
5. **로그**: `artifacts/shared/logs/insight_worker.log`에 JSON 라인으로 사이클 결과를 append한다.

### 5.3 Fingerprint 기반 변경 감지

LLM 호출 비용을 줄이는 핵심 메커니즘이다.

- **Schema fingerprint**: `information_schema.TABLES`에서 해당 스키마의 테이블 이름을 읽어 정렬 후 SHA-256의 앞 32자를 취한다. 테이블이 추가/삭제되면 해시가 바뀐다.
- **Table fingerprint**: `information_schema.COLUMNS`에서 컬럼의 이름·타입·nullable·key 메타를 ordinal 순서대로 읽어 SHA-256의 앞 32자. 컬럼 구조가 바뀌면 해시가 바뀐다.
- **Batch 최적화**: [insight.py:64 `_compute_table_fingerprints_batch()`](../src/modules/insight.py#L64)는 테이블 다수의 fingerprint를 `IN (...)` 한 번으로 계산해 정보 스키마 라운드트립을 줄인다.
- **스킵 통계**: 사이클 당 `skipped_schemas` / `skipped_tables` 수가 `insight_worker.log`에 이벤트로 남는다. 이 값이 증가한다는 것은 "LLM 호출을 피했다"는 긍정 신호다.

### 5.4 인라인 fallback (워커 부재 / 장애)

워커 컨테이너가 내려가 있거나 heartbeat가 stale이면, 사용자 질의 시점에 에이전트가 **인라인으로 인사이트를 생성**한다.

- 결정 함수: [insight.py:1246 `_should_run_inline_insight_scan()`](../src/modules/insight.py#L1246).
- 판단 기준:
  - `AGENT_INLINE_INSIGHT_ON_ASK=1` → 항상 인라인 실행(개발 모드).
  - `AGENT_INSIGHT_WORKER_ENABLED=0` → 워커 비활성화 상태이므로 인라인 실행.
  - heartbeat 신선도 확인: `insight_worker_last_cycle_at`이 `AGENT_INSIGHT_WORKER_STALE_SEC`(기본 15초, 최소 30초로 clamp) 이내면 "fresh"로 보고 인라인 스킵.
  - 그 외(heartbeat 없음/error) → 인라인 실행.
- 효과: 사용자는 워커 장애 중에도 인사이트 기반 응답을 받을 수 있다. 단, 인라인 경로는 첫 질의 응답이 다소 느려진다.

## 6. 데이터 저장 형식

| 저장소 | 키/팩트 | 내용 |
|---|---|---|
| `AgentMemoryFactEntries` + `AgentMemoryTexts` | `FactKey = 'schema_insight:<schema>'` | LLM이 생성한 스키마 도메인 설명(영문, `domain: <X> / <description>` 포맷) |
| `AgentMemoryFactEntries` + `AgentMemoryTexts` | `FactKey = 'table_insight:<schema>.<table>'` | 테이블 용도 + 주요 컬럼 요약 |
| `agentmemorykv` | `schema_fp:<schema>` | 해당 스키마의 최근 fingerprint |
| `agentmemorykv` | `table_fp:<schema>.<table>` | 해당 테이블의 최근 fingerprint |
| `agentmemorykv` | `schema_insights_bootstrap_at` | 최초 bootstrap 완료 시각 (재진입 차단 플래그) |
| `agentmemorykv` | `schema_instance_scan_at` | 마지막 instance scan 완료 시각 |
| `agentmemorykv` | `insight_worker_last_*` | heartbeat / status / duration / run_id / error |

`ConversationId`는 모두 `'__global__'` 이다. 특정 대화에 종속되지 않는 전역 메타데이터다.

## 7. 질의 시점 주입

사용자 질의가 들어오면 [agent_core.py:232 `_build_knowledge_context()`](../src/agent_core.py#L232)가 위 캐시를 읽어 시스템 프롬프트에 두 블록을 주입한다.

1. `## KNOWN SCHEMAS & TABLES (authoritative — prefer these over tool-based discovery)` — 스키마별 테이블 수 + 도메인 요약.
2. `## RELEVANT TABLES FOR THIS QUESTION` — 사용자 메시지의 영문 토큰과 매칭되는 테이블 인사이트 상위 15건.

이 블록이 들어가야 LLM이 `search_tables`를 건너뛰고 `execute_sql`로 직행한다. 해당 동작의 근거가 되는 프롬프트/도구 설계는 [AGENT_CORE_INTERNALS.md §2–§3](./AGENT_CORE_INTERNALS.md#2-system_prompt-%EC%A4%91%EC%9D%98-%EB%8B%A4%EC%84%AF-%EB%B8%94%EB%A1%9D) 참고.

## 8. 환경변수 레퍼런스

| 변수 | 기본값 | 설명 |
|---|---|---|
| `AGENT_SCHEMA_INSIGHT` | `1` | 스키마 인사이트 생성 전체 활성화 여부. `0`이면 `_bootstrap_schema_insights()`와 `_scan_instance_schema_insights()`가 no-op. |
| `AGENT_SCHEMA_BOOTSTRAP` | `1` | 최초 부트스트랩 단계 수행 여부. |
| `AGENT_SCHEMA_BOOTSTRAP_MAX_TABLES` | `50` | 부트스트랩 단계에서 스키마당 요약할 상위 테이블 개수. |
| `AGENT_SCHEMA_INSIGHT_MAX_COLS` | `20` | 스키마 요약 시 LLM에 넘기는 컬럼 수 상한. |
| `AGENT_TABLE_INSIGHT_MAX_COLS` | `15` | 테이블 요약 시 LLM에 넘기는 컬럼 수 상한. |
| `AGENT_SCHEMA_INSIGHT_RESCAN_SEC` | `3600` | 스키마 재요약 최소 간격. |
| `AGENT_TABLE_INSIGHT_RESCAN_SEC` | `3600` | 테이블 재요약 최소 간격. |
| `AGENT_INSIGHT_MODEL` | `OPENAI_MODEL` | 인사이트 생성에 쓸 LLM 모델 이름 (비워두면 기본 LLM). |
| `AGENT_INSIGHT_TIMEOUT_SEC` | `30` | 개별 LLM 인사이트 호출 타임아웃. |
| `AGENT_INSIGHT_WORKER_ENABLED` | `1` | 백그라운드 워커 루프 활성화. `0`이면 `run_insight_worker_loop()`이 즉시 반환. |
| `AGENT_INSIGHT_WORKER_TICK_SEC` | `8` | 사이클 간 간격(초). 최소 5로 clamp. |
| `AGENT_INSIGHT_WORKER_JITTER_SEC` | `0` | 시작 시 랜덤 지연(초). 동시 실행되는 여러 인스턴스가 락을 두고 경쟁할 때 유용. |
| `AGENT_INSIGHT_WORKER_LOCK_NAME` | `agent_insight_worker_scan` | MySQL advisory lock 이름. 멀티 인스턴스 배포 시 공유. |
| `AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC` | `1` | `GET_LOCK` 대기 시간. 초과 시 이번 사이클은 `skip_locked`. |
| `AGENT_INSIGHT_WORKER_STALE_SEC` | `15` | heartbeat가 이 시간 이내면 fresh로 판정. 초과 시 인라인 경로가 개입. 최소 30으로 clamp됨. |
| `AGENT_INLINE_INSIGHT_ON_ASK` | `0` | 질의 시 인라인 인사이트 실행을 항상 강제. 워커 상태와 무관하게 최신 반영이 필요한 개발용 플래그. |

환경변수 소스: [config.py](../src/modules/config.py).

## 9. 로그 / 신호 → 사용자 해석 가이드

아래는 사용자·운영자가 "오류 같다"고 잘못 읽기 쉬운 정상 신호다.

| 관측되는 것 | 의미 | 조치 |
|---|---|---|
| `repo-insight-worker` 컨테이너가 5초마다 DB에 접속 | 정상 — 사이클 tick. | 없음. |
| `insight_worker.log`에 `"status": "skip_locked"` | 정상 — 다른 인스턴스가 같은 사이클을 돌고 있어 건너뛴 것. | 없음. |
| `insight_worker.log`에 `"event": "fingerprint_skip"` + 큰 `skipped_tables` 수 | 정상 — 변경이 없어 LLM을 호출하지 않고 스킵한 것. 비용 절감 긍정 신호. | 없음. |
| `insight_worker_last_status = ok`, `duration_ms` 수십 ms | 정상 — 변경 없어서 빠르게 완료. | 없음. |
| 사용자가 질문했는데 응답이 평소보다 느림 + 로그에 "인라인 인사이트" | 비정상 가능성 — 워커 heartbeat가 stale이거나 비활성. | `AGENT_INSIGHT_WORKER_ENABLED`, 컨테이너 상태 확인. |
| `insight_worker_last_status = error` + `insight_worker_last_error` 비어있지 않음 | 실패 — 마지막 사이클 에러. | 해당 에러 메시지 + `insight_worker.log`의 해당 `run_id` 확인. |
| `schema_insight:*` 수가 0 | 부트스트랩 미완료 또는 모든 스키마가 시스템 스키마. | `schema_insights_bootstrap_at` KV, `AGENT_SCHEMA_BOOTSTRAP=1` 확인. |

## 10. 헬스 체크 snippet

운영자가 메모리 DB에서 직접 워커 상태를 확인하는 SQL.

```sql
-- heartbeat 요약
SELECT `Key`, Value, UpdatedAt
FROM agent_memory.agentmemorykv
WHERE ConversationId = '__global__'
  AND `Key` LIKE 'insight_worker_last_%'
ORDER BY `Key`;

-- 수집된 인사이트 건수
SELECT
  SUM(FactKey LIKE 'schema_insight:%') AS schema_insights,
  SUM(FactKey LIKE 'table_insight:%')  AS table_insights
FROM agent_memory.AgentMemoryFactEntries
WHERE ConversationId = '__global__';
```

**2026-04-21 런타임 확인 결과 (본 문서 작성 시점):**

```
Key                              Value
insight_worker_last_cycle_at     2026-04-21T01:07:26+00:00
insight_worker_last_duration_ms  27.74
insight_worker_last_error
insight_worker_last_run_id       20260421010726-iwb890c8
insight_worker_last_status       ok

schema_insights  table_insights
5                28
```

## 11. 코드 참조 요약

| 구성요소 | 경로 |
|---|---|
| 워커 루프 | [insight.py:1400 `run_insight_worker_loop()`](../src/modules/insight.py#L1400) |
| 한 사이클 실행 | [insight.py:1260 `run_insight_cycle()`](../src/modules/insight.py#L1260) |
| Bootstrap | [insight.py:556 `_bootstrap_schema_insights()`](../src/modules/insight.py#L556) |
| Instance scan | [insight.py:617 `_scan_instance_schema_insights()`](../src/modules/insight.py#L617) |
| Fingerprint 계산 (schema) | [insight.py:28 `_compute_schema_fingerprint()`](../src/modules/insight.py#L28) |
| Fingerprint 계산 (table batch) | [insight.py:64 `_compute_table_fingerprints_batch()`](../src/modules/insight.py#L64) |
| Advisory lock 획득/해제 | [knowledge.py:523 `_acquire_advisory_lock()`](../src/modules/knowledge.py#L523) / [knowledge.py:538 `_release_advisory_lock()`](../src/modules/knowledge.py#L538) |
| Heartbeat 판정 | [insight.py:1219 `_is_insight_worker_heartbeat_fresh()`](../src/modules/insight.py#L1219) |
| Inline 결정 | [insight.py:1246 `_should_run_inline_insight_scan()`](../src/modules/insight.py#L1246) |
| 질의 시 주입 | [agent_core.py:232 `_build_knowledge_context()`](../src/agent_core.py#L232) |
| LLM 호출 (schema) | [llm.py:1534 `llm_schema_insight()`](../src/modules/llm.py#L1534) |
| LLM 호출 (table) | [llm.py:1568 `llm_table_insight()`](../src/modules/llm.py#L1568) |
