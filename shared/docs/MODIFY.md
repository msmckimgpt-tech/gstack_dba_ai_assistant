---
doc_type: SHARED_MODIFY
scope: shared
status: active
edit_policy: append-only
source_of_truth: true
---

# shared/ Modify Log

<!--
shared 코드 변경 시 아래 형식으로 기록한다.
기능별 MODIFY.md에도 교차 참조를 남긴다.
-->

<!-- 예시:
## CHG-YYYYMMDD-0001
- Date: YYYY-MM-DD
- Changed By: feature-xxxx (AI)
- Summary: 공통 유틸리티 함수 추가
- Files: shared/utils.py
- Affected Features: feature-0001, feature-0003
- Cross-ref: feature-xxxx/docs/MODIFY.md CHG-YYYYMMDD-0001
-->

## CHG-20260703T085511-ds-avg-latency
- Date: 2026-07-03
- Changed By: feature-0003-agent-web-ui (AI) — 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0003-ds-avg-latency`
- Summary: 연결 응답 시간 이동평균 추가. `config.py` 에 `AGENT_CONN_AVG_WINDOW`(기본 20) + `__all__` 등록. `conn_health.py` 에 `_SAMPLES` deque window + `_sample_avg_elapsed` + `_apply_result` 성공 probe-db 표본화 → `avg_elapsed_ms`/`sample_count` 를 `snapshot()` 에 additive 노출(좌표·표본 비노출 불변식 보존, `_prune_state`/`_reset_state` lockstep 정리). status 분류·gating·`last_elapsed_ms` 무변경(비파괴 additive, in-memory only).
- Files: `shared/config.py`, `shared/conn_health.py`
- Affected Features: feature-0002-agent-core(conn_health 소비: ask-worker/insight-worker gate — 무영향), feature-0003-agent-web-ui(관리 콘솔 표시 — 신규 소비)
- Cross-ref: unit/feature-0003-agent-web-ui/docs/MODIFY.md CHG-20260703T085511-ds-avg-latency · REVIEW.md REV-20260703T085511-ds-avg-latency

## CHG-20260706T013532-reasoning-effort
- Date: 2026-07-06
- Changed By: feature-0003-agent-web-ui (AI) — 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0003-reasoning-effort`
- Summary: 사용자 지정 추론 강도(extended thinking budget) 매핑 추가. `model_catalog.py` 에 `REASONING_LEVELS`(유효 레벨 튜플 low/normal/high/max)·override budget map `_REASONING_BUDGETS`(**낮음=2000/높음=10000/매우높음=16000** — **'일반'은 의도적 부재 = override 없음**, B1 회귀 방지)·`REASONING_LEVEL_OPTIONS`·`DEFAULT_REASONING_LEVEL` + 헬퍼 `normalize_reasoning_level`·`thinking_budget_for_level`('normal'→None)·`model_supports_thinking`(claude-* 만) + `__all__` 등록. 순수 additive(기존 max_tokens/temperature/vision 로직 무변경). override 값 전부 Anthropic 제약(1024 ≤ budget < agent max_tokens 20000) 만족.
- Files: `shared/model_catalog.py`
- Affected Features: feature-0002-agent-core(_call_llm 요청 단위 thinking 주입 — 신규 소비), feature-0003-agent-web-ui(/api/ask normalize·프론트 선택기 — 신규 소비)
- Cross-ref: unit/feature-0003-agent-web-ui/docs/MODIFY.md CHG-20260706T013532-reasoning-effort(정본) · unit/feature-0002-agent-core/docs/MODIFY.md CHG-20260706T013532-reasoning-effort · feature-0003 REVIEW.md REV-20260706T013532-reasoning-effort

## CHG-20260707T100640-no-edge-conversation-answer
- Date: 2026-07-07
- Changed By: feature-0002-agent-core (AI) — 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0002-agent-core`, conversation_audit(FR-edge-fallback-conversation-context-loss)
- Summary: `model_catalog.py` 에 대화 답변(task='agent') 전용 edge-free 라우팅 헬퍼 `conversation_answer_model()` + `_CONVERSATION_ANSWER_ALIAS`(claude-haiku-4→claude-haiku-4-chat) + `__all__` 등록. 순수 additive(기존 max_tokens/temperature/vision/thinking 로직 무변경). 매핑 밖 model(claude-sonnet-4 등 — litellm fallbacks 목록에 없어 edge 강등 無)은 identity 반환(무회귀). 목적: 두 claude 계정 429/401 완전 장애 시 대화 답변이 edge-fallback(gemma4:e2b, ctx 4096)으로 silent 강등돼 히스토리를 잘라 맥락을 파괴하는 것을 원천 차단(사용자 결정 2026-07-07: 명백한 실패처리).
- Files: `shared/model_catalog.py`
- Affected Features: feature-0002-agent-core(_call_llm 이 litellm 호출 model 을 이 헬퍼로 치환 — 신규 소비), feature-0007-bedrock-llm-provider(litellm_config -chat/-chat-root alias·fallback 신설)
- Cross-ref: unit/feature-0002-agent-core/docs/MODIFY.md CHG-20260707T100640-no-edge-conversation-answer(정본) · unit/feature-0007-bedrock-llm-provider/docs/MODIFY.md 동일 · feature-0002 REVIEW.md REV-20260707T100640-no-edge-conversation-answer
## CHG-20260706T094937-runtime-settings (TASK-20260706T094937-runtime-settings — 런타임 설정 레지스트리·resolver + config restart 적용, cross-unit: 정본 feature-0003, Major §12.3)
- Date: 2026-07-06. 문서 정본/전체 맥락은 feature-0003/docs (관리 콘솔 `시스템 > 설정`).
- 신규 `shared/runtime_settings.py`: 관리 콘솔에서 조정하는 운영 값(실행 타임아웃 22 + 모델별 thinking budget 카탈로그 자동생성) 레지스트리 + resolver(`get_int` live TTL / `startup_int` restart frozen) + `/shared/runtime_settings.json` 스냅샷 원자적 I/O + `validate_value`/`serialize_registry`. 의존성 경량(os·json·time·threading·model_catalog) — shared.config 미import(순환 없음). fail-open + kill-switch(RUNTIME_SETTINGS_DISABLED).
- `shared/config.py`: restart-mode 22 timeout 상수를 `_startup_int(key, env_default)` 로 감싸 import 시 스냅샷 override 반영. 방어적 import(runtime_settings 실패해도 무손상), override 부재 시 env 기본값 byte-동치, CONN_PROBE max() 불변식 보존.
- `shared/model_catalog.py`: 변경 없음(runtime_settings 가 `API_MODEL_OPTIONS`·`model_supports_thinking` 를 순회해 모델 예산 항목을 자동 생성 — 참조만).

## CHG-20260707T130000-reasoning-budgets (TASK-20260707T130000-reasoning-budgets — runtime_settings 추론 강도별 예산 레지스트리, cross-unit: 정본 feature-0003, Major §12.3)
- Date: 2026-07-07. `shared/runtime_settings.py`: `reasoning_budget:{low,high,max}` 스펙(`_reasoning_budget_specs` — model_catalog.REASONING_LEVELS 순회, thinking_budget_for_level None(=normal) 제외, 기본값=그 함수값 2000/10000/16000, min1024 max16000, group=reasoning_budget, apply_mode live) + `reasoning_budget_override(level)` resolver(clamp, 미등록/normal→None) + serialize `reasoning_budgets` 버킷 + `__all__`(reasoning_budget_override·REASONING_BUDGET_KEY_PREFIX·GROUP_REASONING_BUDGET). model_catalog(os/typing 만 import) 순회라 순환 없음. 검증·validate·스냅샷·audit 는 기존 경로 재사용(신규 키만).
- Cross-ref: feature-0003·feature-0002 MODIFY 동일 slug.

## CHG-20260724T085937-sonnet-reasoning-budget-guide (runtime_settings: adaptive(Sonnet 5) 죽은 budget 스펙 제거 + adaptive_models 표면화, cross-unit: 정본 feature-0003, Minor §12.3)
- Date: 2026-07-24. `shared/runtime_settings.py`: `_budget_thinking_models()`(= `_thinking_models()` − adaptive) + `_adaptive_thinking_models()` 신설. `_reasoning_budget_specs()`·`_model_budget_specs()` 가 `_budget_thinking_models()` 순회로 전환(adaptive 모델 ②③ 스펙 미생성). `agent_max_output`(①)은 전체 thinking 모델 유지. `serialize_registry` 에 `adaptive_models` 버킷 추가. model_catalog.model_thinking_style 판정 재사용(순환 없음 — model_catalog 는 os/typing 만 import). override resolver 는 spec 부재 시 이미 None 반환이라 무변경(죽은 sonnet override 는 조회 시 None).
- 이유: adaptive(Sonnet 5)는 output_config.effort 로 추론 강도 제어 → budget_tokens override 무의미(agent_core._call_llm adaptive 분기 미조회). 관리 콘솔 죽은 슬라이더를 registry 레벨에서 차단.
- Cross-ref: feature-0003·feature-0002 MODIFY 동일 slug · 선행 CHG-20260707T130000-reasoning-budgets.

## CHG-20260727T175800-false-truncation-belief (config: `AGENT_ROUTINE_DEF_CHUNK_CHARS` 신설 — describe_routine 정의 offset 페이징 창 크기, cross-unit: 정본 feature-0002, Major §12.3)
- Date: 2026-07-27
- Changed By: feature-0002-agent-core (AI) — 단일 mutator(§13.2.2 F2), worktree `ai/root/feature-0002-agent-core`, conversation_audit(FR-false-truncation-belief)
- Summary: `shared/config.py` 에 `AGENT_ROUTINE_DEF_CHUNK_CHARS`(env override, 기본 **0 = auto**) 신설 + `__all__` 등록. 순수 additive 상수 1개 — 기존 상수·resolver·순환 의존 무변경. 소비처는 `tools._routine_chunk_limit()` 단일 지점. 의미(§18.8 적대 패널 반영 후 확정): **0=auto** → 실효 창 = `AGENT_TOOL_RESULT_MAX_CHARS - 1000`, 즉 **전역 backstop 캡이 어차피 자를 지점부터만** 쪼갠다(창을 캡보다 작게 고정하면 캡 이하 정의까지 불필요하게 조각나 부분 열람 위험이 새로 생긴다). **양수** → 명시 창(하한 4000, 상한 `캡-여유`). **음수** → 윈도잉 비활성 kill-switch. 캡이 무제한(`<=0`)이거나 `캡-여유 <= 0` 이면 윈도잉 비활성 — 창이 캡 이상이면 캡이 조각 꼬리("다음 offset" 안내)를 잘라 **전량 도달 경로 자체가 사라지므로**, 그 구간은 캡의 `... (truncated)` 가 정직한 절단 신호로 남는 편이 낫다. `0`/음수 의미는 형제 상수 `AGENT_TOOL_RESULT_MAX_CHARS`("0/음수=무제한")의 "그 값으로는 자르지 않는다" 규약과 정합한다.
- 이유: 사용자 결정(2026-07-27 AskUserQuestion) — 전역 도구결과 캡의 무제한화는 **범위에서 제외**하고, 캡보다 큰 초대형 저장 루틴 정의는 `describe_routine(offset)` 반복 호출로 전량 도달하게 한다. 창 크기를 env 로 조정 가능하게 두어 컨텍스트 예산과 호출 횟수의 trade-off 를 운영에서 튜닝할 수 있게 했다.
- Files: `shared/config.py`
- Affected Features: feature-0002-agent-core(`modules/tools._routine_chunk_limit` 신규 소비 — 유일 소비처)
- Cross-ref: unit/feature-0002-agent-core/docs/MODIFY.md CHG-20260727T175800-false-truncation-belief(정본) · 동 feature REVIEW.md REV-20260727T175800-false-truncation-belief · FRICTION_LEDGER FR-false-truncation-belief · 선행 CHG-20260724T155534-tool-result-cap-raise(`AGENT_TOOL_RESULT_MAX_CHARS` backstop — 유지)

## CHG-20260727T184425-opus5-model (model_catalog·runtime_settings: Claude Opus 5 카탈로그 추가, cross-unit: 정본 feature-0007, Major §12.3 외부비용)
- Date: 2026-07-27. 사용자 요청("서비스 내 assistant 의 llm 모델에 claude opus 도 포함 … claude-corp 및 root 계정 포함"). 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0007-opus5-model`.
- `shared/model_catalog.py` (순수 additive):
  - `API_MODEL_OPTIONS` 선두에 `claude-opus-5`(label `claude-opus`, group `Claude`, supports_temperature=False — Opus 5 는 sampling 파라미터 400, supports_vision=True).
  - `_CONVERSATION_ANSWER_ALIAS["claude-opus-5"] = "claude-opus-5-chat"` — 도입 시점부터 edge-free 2계정 체인(sonnet 의 bare 단일계정 429 결함 선반영 차단).
  - `_ADAPTIVE_THINKING_PREFIXES` 에 **`claude-opus`**(넓은 prefix) — Opus 계열 전체가 adaptive-only(budget_tokens 400)라 미분류로 떨어지는 회귀를 원천 차단. `requires_oauth_frontier_identity()` 가 동일 집합이라 CC identity 주입도 자동 적용(2026-07-27 라이브 실증: Opus 5 도 system 첫 블록 CC 없으면 429).
  - `_CLAUDE_MODEL_MAX_OUTPUT["claude-opus-5"] = 128000`(native).
  - `canonical_usage_model`/`_sql` 에 **`claude-opus-5`(버전-정확)** fold — thinking-style 의 넓은 prefix 와 의도적 비대칭: 미등록 Opus 버전을 Opus 5 단가·비중으로 오귀속하지 않고 self-surface 시킨다(기존 규약 보존).
  - ⚠ 부작용(의도): `model_thinking_style("claude-opus-4-8")` 이 None → `"adaptive"`. Opus 4.8 도 실제 adaptive-only 라 사실 정합 개선(테스트 1건 갱신).
- `shared/runtime_settings.py`: `_AGENT_MAX_OUTPUT_DEFAULT["claude-opus-5"] = 40000`. budget 계열 스펙(②③)은 `_budget_thinking_models()` 가 adaptive 를 제외하므로 자동 미생성 → admin UI 는 guide-note(죽은 슬라이더 0, CHG-20260724T085937 규약 그대로 적용).
- Affected Features: feature-0007-bedrock-llm-provider(정본 — litellm 3 deployment + fallback), feature-0002-agent-core(`_call_llm` adaptive/CC 분기·redteam 리뷰어 정합 — 코드 무변경, 카탈로그 자동 파급), feature-0003-agent-web-ui(모델 선택기·runtime-settings pane 자동 파급 + `admin_usage._LLM_PRICE_USD_PER_1M` 단가 등록).
- Cross-ref: unit/feature-0007-bedrock-llm-provider/docs/MODIFY.md CHG-20260727T184425-opus5-model(정본) · 동 REVIEW.md REV-20260727T184425-opus5-model · TEST.md Run 2026-07-27-opus5-model.

## CHG-20260727T234439-model-picker-copy (model_catalog: 모델 선택기 description 축약, cross-unit: 정본 feature-0003, Minor §12.3)
- Date: 2026-07-27. 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0003-model-picker-copy`.
- `shared/model_catalog.py`: `API_MODEL_OPTIONS` 3개 항목의 **`description` 문자열만** 축약(`value`/`label`/`group`/`supports_*` 무변경). label·group 배지와 겹치는 "Anthropic Claude <tier>" 접두 제거 + tier 간 중복어(`frontier`) 제거 + 세 항목을 동일 축(성능 등급 · 용도)으로 병렬 서술. 사용자 지적(선택기 부자연스러운 줄바꿈·가독성) 대응.
- 표시 전용 필드라 라우팅·단가·runtime_settings 키·저장 대화 영향 0.
- Affected Features: feature-0003-agent-web-ui(정본 — 렌더 규약·CSS), feature-0007-bedrock-llm-provider(카탈로그 소유 cycle — 선행 CHG-20260727T184425-opus5-model 이 도입한 문구를 다듬음).
- Cross-ref: unit/feature-0003-agent-web-ui/docs/MODIFY.md CHG-20260727T234439-model-picker-copy(정본) · 동 REVIEW · test-runs.d/20260727T234439-model-picker-copy.md.

## CHG-20260728T024258-model-access-rbac (model_catalog: 모델 접근 권한 코드 namespace, cross-unit: 정본 feature-0003, Critical §12.3)
- Date: 2026-07-28. 사용자 요청("계정/역할 별 권한 범위를 구성"). 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0003-model-access-rbac`.
- `shared/model_catalog.py` (순수 additive): `MODEL_ACCESS_PERMISSION_PREFIX`("model.access.") · `MODEL_ACCESS_PERMISSION_GROUP`("model_access") 상수 + `model_permission_code(value)` · `is_model_permission_code(code)` + `__all__` 등록. 기존 심볼·동작 무변경.
- 배치 근거: 권한 코드 namespace 가 **카탈로그 value 에서 파생**하므로 SSOT 인 model_catalog 에 둔다. `shared/` 는 web_context(feature-0003)를 import 하지 않아 단방향이고, 반대 배치는 순환이 된다. 모델 추가 시 코드가 자동 확장돼 별도 매핑 테이블이 필요 없다.
- `model_permission_code("")` 는 빈 문자열 — 호출측이 `permissions.get("")` 로 조용히 True 를 얻는 경로를 만들지 않는 방어.
- Affected Features: feature-0003-agent-web-ui(정본 — 부트스트랩 seed·판정 함수·집행 게이트·표시 필터·권한 grid), feature-0007-bedrock-llm-provider(카탈로그 소유 — 모델 추가 시 권한 row 자동 확장), feature-0023-conversation-api-access(API 토큰 scope 면제 규약).
- Cross-ref: unit/feature-0003-agent-web-ui/docs/MODIFY.md CHG-20260728T024258-model-access-rbac(정본) · 동 REVIEW · docs/SECURITY.md §28 · docs/CONVENTIONS.md §10.6.

## CHG-20260730T1105-node-analysis-retry-knobs (config: 노드 분석 일시 실패 재시도·회로차단 knob, cross-unit: 정본 feature-0016)
- Date: 2026-07-30. 사용자 리포트("AI 능동 분석이 주기적인 네트워크 단절로 중단되면 복구 후에도 아무 작업이 없다"). 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0016-analysis-retry-resilience`.
- `shared/config.py` (순수 additive): `AGENT_NODE_ANALYSIS_MAX_ATTEMPTS`(4) · `AGENT_NODE_ANALYSIS_RETRY_BASE_SEC`(60) · `AGENT_NODE_ANALYSIS_RETRY_MAX_SEC`(600) · `AGENT_NODE_ANALYSIS_CIRCUIT_FAILS`(3) + **`__all__` 등록**. 기존 심볼·동작 무변경.
- 배치 근거: 기존 `AGENT_NODE_ANALYSIS_*` 계열(LEASE_SEC·BATCH_PER_TICK 등)과 같은 워커 예산 축이라 같은 블록에 둔다. `RETRY_MAX_SEC` 는 **`LEASE_SEC` 미만** 이어야 한다 — backoff 대기가 lease 를 넘기면 enqueue dedup 이 run 을 stale 로 보고 중복 run 을 만든다(주석에 불변식 명시).
- `__all__` 등록은 rel-selfheal(ADR-007) 교훈의 직접 적용 — `AGENT_RELATIONSHIP_*` 누락이 `from shared.config import *` 소비처에서 NameError 를 내 자기교정 파이프라인을 3일 조용히 정지시킨 전례가 있다.
- Affected Features: feature-0016-metadata-graph(정본 — 재시도 상태머신·회로차단), feature-0002-agent-core(코드 거주 `node_analysis.py`·`llm.py`·`insight.py`).
- Cross-ref: unit/feature-0016-metadata-graph/docs/MODIFY.md CHG-20260730T1105-ai-claude-feature-0016-analysis-retry-resilience(정본) · 동 DECISIONS ADR-20260730T1105-analysis-retry-resilience · 동 TEST.md.

## CHG-20260730T1235-worker-resource-budget (shared: 공유 자원 예산·워커 계측 모듈 신설, cross-unit: 정본 feature-0025)
- Date: 2026-07-30. 상위 설계 트랙 0(RI-0 공유 자원 전역 예산·직렬화 부재). 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0025-worker-resource-isolation`.
- `shared/resource_budget.py` **신규**: 자원 종류(현재 `llm`) 단위 예산 게이트 + 프로세스 전역 워커 계측 + 전역 kill-switch + JSON 파일 flush. 소비처는 백그라운드 워커(node_analysis·semantic_cluster·product_classify·insight)와 `bin/perf-snapshot.sh`.
- `shared/runtime_settings.py` (additive): `performance` 그룹에 `자원 격리·관측` 카테고리 **2 knob** — `AGENT_BACKGROUND_ANALYSIS_ENABLED` · `AGENT_WORKER_LLM_BUDGET`. 커넥션 총량(PG/DS) knob 은 게이트가 T0b 라 노출하지 않는다(거짓 컨트롤 금지, ADR-0025-06). 전부 `apply_mode: live`(정지 스위치가 재배포를 요구하면 무의미). `shared/config.py` 무변경 — 신규 knob 은 spec default 만으로 동작하며 노출 대상 env 상수가 아니다.
- `shared/db.py` (additive): `_worker_conn_incr` 훅을 `_pg_connect`/`_pg_connect_ro` 에 추가. **계측만이고 게이트가 아니다** — 게이트를 커넥션 헬퍼에 넣으면 같은 헬퍼를 쓰는 web 요청 경로가 백그라운드 예산에 걸린다. lazy import + 예외 삼킴(이미지/마운트 skew 로 신규 모듈이 없는 배포 창에도 커넥션 수립이 실패하지 않아야 한다 — `_perf_counters` 스텁 폴백과 동일 정합).
- 설계 경계: 프로세스 **내** 조율이다(한 컨테이너의 스레드). 프로세스 간 총량(insight-worker ↔ ask-worker ↔ web-a/b)은 본 슬라이스 범위 밖이며 pgbouncer 풀 상한이 backstop — 필요해지면 PG advisory lock 또는 토큰 테이블로 승격.
- Affected Features: feature-0025-worker-parallelism(정본 — 자원 총량 축), feature-0016-metadata-graph(게이트 대상 워크로드), feature-0026-perf-observability(`perf_counters` 요청-스코프와 직교하는 워커 계측 축).
- Cross-ref: unit/feature-0025-worker-parallelism/docs/MODIFY.md CHG-20260730T1235-ai-claude-feature-0025-worker-resource-isolation(정본) · 동 TASK.md `## 20260730T1235-worker-resource-isolation` · 동 REVIEW.md.

## CHG-20260730T1430-worker-ds-task-budget (shared: ds·task 자원 등재 + knob 2, cross-unit: 정본 feature-0025)
- Date: 2026-07-30. T0b — T0 에서 이연한 커넥션 축을 닫는다(T1 접지의 전제). 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0025-worker-ds-budget`.
- `shared/resource_budget.py`: `RESOURCES = ("llm", "ds", "task")` — `ds`(소스 DB 동시 연결, 게이트 3지점) · `task`(동시 진행 백그라운드 작업, 진입 3지점). 자원 표에 게이트 지점을 명기해 "등재 = 배선됨" 을 문서로도 고정.
- `shared/runtime_settings.py` (additive): `AGENT_WORKER_DS_BUDGET`(8) · `AGENT_WORKER_TASK_BUDGET`(8), 둘 다 `apply_mode: live`.
- **`AGENT_WORKER_PG_BUDGET` 은 만들지 않았다** — PG 동시 점유를 정확히 강제하려면 커넥션 수명과 예산 수명을 묶어야 하고, 워커는 `conn=None 이면 열고 주어지면 재사용` 패턴에 close 가 호출측 `finally` 라 광범위 리팩터가 된다. `task`(작업당 PG 1~2개)로 근사하며 이름·설명을 그 의미로 유지한다(ADR-0025-06 의 연장 — 게이트 없는 이름을 쓰지 않는다).
- Affected Features: feature-0025-worker-parallelism(정본), feature-0016-metadata-graph(게이트 대상 워크로드), feature-0003-agent-web-ui(콘솔 섹션 — 공유 볼륨 파일 읽기), feature-0026-perf-observability(계측 축 직교).
- Cross-ref: unit/feature-0025-worker-parallelism/docs/MODIFY.md CHG-20260730T1430-ai-claude-feature-0025-worker-ds-budget(정본) · 동 TASK.md `## 20260730T1430-worker-ds-budget` · 동 DECISIONS ADR-0025-07.

## CHG-20260730T191535-llm-edge-free-routing (shared/config.py — off-hours 강등 기본 비활성)
- Date: 2026-07-30. 정본: `unit/feature-0007-bedrock-llm-provider/docs/MODIFY.md` 동일 CHG · ADR-003.
- 변경: `shared/config.py` 의 `AGENT_INSIGHT_OFFHOURS_MODEL` 기본값 `"edge"` → `""`(빈 값). 빈 값이면
  `llm._effective_insight_model()` 이 시각과 무관하게 base(`AGENT_INSIGHT_MODEL`=claude)를 반환하므로
  **배경 insight 배치의 야간·주말 gemma 강등이 기본 비활성**이 된다. 사용자 결정 2026-07-30("더 이상
  로컬 LLM 을 사용하지 않는다") — 2026-07-04 ADR-002 결정 2의 override.
- 강등 로직·환경변수는 보존한다(운영자가 값을 채우면 재활성 = 결정 override). 게이트웨이 층에서도
  litellm `fallbacks` 의 `edge-fallback` 참조를 전량 제거해, 앱·게이트웨이 양쪽에서 자동 강등 경로가 없다.
- Affected Features: feature-0007-bedrock-llm-provider(정본 — litellm_config), feature-0002-agent-core
  (`_effective_insight_model` docstring · 회귀 테스트 `test_llm_edge_free_routing.py` 5건 신규),
  feature-0016-metadata-graph(node_analysis 는 이미 `-meta` edge-free — 무영향).
- Cross-ref: feature-0007 DECISIONS ADR-003 · TASK `## TASK-20260730T191535-llm-edge-free-routing` ·
  TEST Run 2026-07-30-llm-edge-free-routing.
