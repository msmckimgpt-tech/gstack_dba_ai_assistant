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
