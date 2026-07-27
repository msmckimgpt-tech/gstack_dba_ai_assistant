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
