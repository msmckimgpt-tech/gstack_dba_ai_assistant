# DESIGN — Account-scoped Cross-conversation Insight Recall

| 항목 | 값 |
|---|---|
| TASK | TASK-20260617T082131-ai-claude-account-insight-recall |
| feature | feature-0002-agent-core (KB/recall 서브시스템 enhancement) |
| 등급 | **Major** (cross-account 보안 경계) |
| 상태 | 설계 확정 + Phase 1 착수 (shadow, flag default OFF) |
| outside-voice | 보안(NOT-SHIP→가드 시 SHIP-WITH-FIXES) + 정합성(SOUND-WITH-FIXES) 2명 검증 완료 |

## 1. 목적

사용자가 **새 대화를 시작하면 과거 대화에서 쌓은 인사이트가 통째로 사라지는** 문제를 해소한다.
같은 `owner_account_id` 의 과거 대화 맥락을 **의미적으로(어렴풋이) 회상**해 LLM 컨텍스트에
주입하되, **계정 경계는 절대 격리**한다 (특정 명칭/alias 기억이 아니라 문맥/인사이트 이월).

## 2. 배경 — 현 구조와 정확한 gap

- 회상 엔진은 이미 가동: `_embed_query_vector` ([kb_retrieval.py](../src/modules/kb_retrieval.py)) +
  pgvector cosine `<=>` `search_rag_documents_vector` ([kb_backend.py](../src/modules/kb_backend.py),
  TASK-0135). 임베딩 dim = **1536, OpenAI text-embedding-3-small** (`AGENT_KB_EMBEDDING_MODEL`).
- 계정 축도 이미 존재: `agent_runtime.core_conversations.owner_account_id` + idx `ix_core_conv_owner`.
- **gap (한 줄)**: 회상 scope 가 `conversation_id = ANY(conv_ids)` 이고 conv_ids =
  `_global_fact_conversation_ids` = {현재 대화, 워커 세션 샤드, `__global__`} 뿐 →
  **계정의 타 대화가 회상 대상에서 배제**됨.
- `public.texts`/`public.rag_documents` 와 `agent_runtime.*` 는 **동일 DB `agent_kb`** →
  cross-schema JOIN 가능 (단 ADR-0027: 전역 search_path 없음 → 모든 SQL **schema-qualified** 필수).

### Prior art
- `file_ops.convo_search` — 에이전트가 **명시 호출**하는 타 대화 검색 도구(messages/summary/kv ILIKE).
  본 설계는 그와 달리 **자동 회상**이며, convo_search 의 계정 스코핑 여부는 별도 점검 대상(아래 §8).

## 3. 설계 (v2 — outside-voice 반영)

### 3.1 핵심 원칙
- **신규 테이블/컬럼 0** — `owner_account_id` 로 account→conv_ids 도출 후 **기존 벡터 회상에 주입**.
  (rag_documents 에 account_id 컬럼 추가는 dual-write·이중진실 유발 → 기각.)
- **계정 경계 = 보안 경계** (cross-account 누출 0).
- **flag-gated, shadow-first**: 회상 활성(`RECALL`)과 실제 주입(`INJECT`)을 분리. 둘 다 default OFF.

### 3.2 회상 메커니즘
신규 모듈 [`modules/account_recall.py`](../src/modules/account_recall.py):
1. `_load_account_scoped_conv_ids(account_id, exclude_conversation_id, limit)` →
   `SELECT conversation_id FROM agent_runtime.core_conversations
    WHERE owner_account_id = %s AND owner_account_id IS NOT NULL
      AND archived_at IS NULL AND conversation_id <> %s
      AND conversation_id NOT LIKE '\_\_global\_\_%' ORDER BY updated_at DESC LIMIT %s`
   (schema-qualified, ADR-0027).
2. 도출된 conv_ids 를 기존 `search_rag_documents_vector(conversation_ids=...)` 에 주입 →
   계정의 과거 대화 fact 를 의미 회상.
3. 결과를 knowledge payload 의 **별도 블록** ("이전 대화에서 파악한 맥락 — 참고용, 확실치 않으면 무시")
   으로 주입. 주입 지점 = `agent_core._build_knowledge_context` (account_id/conversation_id 가
   호출부 [agent_core.py:2731](../src/agent_core.py) 에 이미 가용).

### 3.3 account_id 신뢰
`account_id` 는 ask job claim 시 결정되어 전파(ask.py `_payload_to_kwargs`, app.py 10073/9423) —
**클라이언트 payload 위조 불가**. owner 채움은 web(app.py:1748)이 담당, core 는 안 함 →
신규 대화 첫 턴은 자기 과거가 없으므로 무해(회상 0).

## 4. 필수 보안 가드 (BLOCKER 대응)

| ID | 가드 | 대응 BLOCKER | Phase |
|---|---|---|---|
| **G1** | **fork/공유 대화 회상 제외** — fork 는 소스(타 계정) 메시지를 복사하고 owner=포크계정으로 재귀속(app.py:11156/11163/11176) → owner 격리가 콘텐츠 출처 격리와 어긋남. fork 식별 표식(신규 `forked_from` 컬럼 또는 `owner_assigned_at vs created_at` 휴리스틱) 후 모집단 배제. | cross-account 누출 | **INJECT 전 필수** |
| **G2** | **owner NOT NULL + deny-list** — `owner_account_id IS NOT NULL`, `__global__`/`__global__:session:*`/NULL-owner 배제. `_global_fact_conversation_ids`·`cross_session_anchor` import 금지(CI lint). | system/global 누출 | **Phase 1 구현** |
| **G3** | **PII 차단** — `agent_runtime.summary`/answer 는 마스킹 안 됨(`_mask_rows` 호출처 0건, prose 무력). 값-패턴 PII 마스커(이메일/전화/주민번호 정규식) 적용 **또는** PII-free 구조화 인사이트만 회상. | PII 전파 | **INJECT 전 필수** |
| **G4** | **방어심층 owner 재검증** — 회상된 각 conv_id 를 `_conversation_owned_by_account(account_id)` 재확인 후 주입. | 필터 우회 2차 방어 | INJECT 전 권장 |

## 5. Capture 전략 (단계)

- **Phase 1 (본 cycle 착수)**: 회상 *경로* 만 — `_load_account_scoped_conv_ids` + 기존 rag_documents
  벡터 회상 재사용 + **shadow(log-only, default OFF)**. 신규 capture 없음(기존 fact 재사용).
- **Phase 2 (후속)**: insight worker(`run_insight_cycle`)에 **PII-free 구조화 인사이트 추출 pass**
  추가 — "사용자는 X 도메인 Y 지표에 반복 관심" 류를 `rag_documents`/`texts`(임베딩 노출, KV 아님)에
  기록. PII 회피의 본령. (worker 기본 `__global__` 스코프 우회 필요.)

> Capture 전략 최종 확정은 outside-voice 결론(PII 때문에 raw summary 회상은 G3 필수)에 따라
> **Phase 2(구조화)가 권장 본령**, Phase 1 은 G3 마스킹과 함께만 INJECT.

## 6. Flags / Rollout

| flag | default | 역할 |
|---|---|---|
| `AGENT_ACCOUNT_INSIGHT_RECALL` | `0` (OFF) | 회상 경로 활성 (shadow 포함) |
| `AGENT_ACCOUNT_INSIGHT_INJECT` | `0` (OFF) | 실제 LLM 주입 (OFF = shadow log-only) |
| `AGENT_ACCOUNT_INSIGHT_MAX_CONVS` | `20` | account conv_ids 상한 |
| `AGENT_ACCOUNT_INSIGHT_TOP_K` | `3` | 주입 인사이트 상한 |
| `AGENT_ACCOUNT_INSIGHT_MIN_SIM` | `0.75` | 최소 유사도 (노이즈 억제) |

Rollout: shadow(RECALL=1, INJECT=0) → 로그 품질 평가 → G1·G3 완료 → INJECT=1.

## 7. 관측 / 품질
- 회상 conv 수·결과 수·유사도·주입 여부 로깅.
- 노이즈: `MIN_SIM` 임계 + `TOP_K` + "참고용" 프레이밍.
- 임베딩 미충전 silent degradation: 인사이트→벡터 노출 사이 `kb_embedding_worker` 배치 지연 인지.

## 8. 위험 / 후속
- **R1 (Critical)**: cross-account 누출 — G1·G2·G4 + 격리 회귀 테스트.
- **R2**: PII 전파 — G3.
- **R3**: runtime MySQL fallback 시 cross-schema JOIN 불가 — recall 은 PG 필수, fail-closed.
- **R4 (부수 발견)**: `_mask_rows` 호출처 0건 — 기존에도 PII 가 KB 로 유입 가능. 독립 버그로 별도 처리 후보.
- **R5 (점검)**: `convo_search` 도구의 계정 스코핑 여부 — cross-account 누출 가능성 별도 검토.
- 주석 정정: [kb_backend.py](../src/modules/kb_backend.py) 의 "vector(1024) Titan v2" → 실제 1536/text-embedding-3-small (stale).

## 9. Phase 1 범위 (본 cycle)
1. `modules/account_recall.py` — `_load_account_scoped_conv_ids` (G2 가드) + `recall_account_conv_facts` (shadow).
2. `_build_knowledge_context` 에 account_id/conversation_id optional 파라미터 + shadow 호출 (default no-op).
3. config flags (전부 default OFF).
4. 단위 테스트 — 계정 격리·owner NULL 제외·현재 대화 제외·`__global__` 제외·flag OFF no-op.
5. kb_backend.py stale 주석 정정.

**INJECT 활성화는 본 cycle 범위 밖** — G1(fork 표식)·G3(PII 마스커) 완료 후 별 cycle.
