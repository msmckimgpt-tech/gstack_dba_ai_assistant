from __future__ import annotations

import logging
import os
from typing import Any

_log = logging.getLogger("model_catalog")

__all__ = [
    "API_DEFAULT_MODEL",
    "API_MODEL_OPTIONS",
    "PUBLIC_API_MODEL_OPTIONS",
    "REASONING_LEVELS",
    "REASONING_LEVEL_OPTIONS",
    "DEFAULT_REASONING_LEVEL",
    "get_api_model_meta",
    "is_allowed_api_model",
    "is_local_llm_model",
    "conversation_answer_model",
    "max_tokens_for_model",
    "model_native_max_output",
    "model_supports_temperature",
    "model_supports_thinking",
    "model_supports_vision",
    "normalize_reasoning_level",
    "thinking_budget_for_level",
]


API_DEFAULT_MODEL = "claude-haiku-4"

# ── 로컬 LLM 게이트웨이 모델 (LOCAL_LLM_API_BASE 설정 시 자동 추가) ──
# supports_vision: 보수적 false. 로컬 게이트웨이 모델별 vision 지원은 배포 환경
# 따라 다르고, D11 (file_image consent) 가 false 면 첨부 image 가 송신되지 않
# 으므로 안전한 기본값.
_LOCAL_LLM_MODELS: tuple[dict[str, Any], ...] = (
    {
        "value": "auto",
        "label": "auto (로컬 LLM)",
        "group": "Local LLM",
        "description": "게이트웨이 자동 라우팅",
        "supports_temperature": False,
        "supports_vision": False,
    },
    {
        "value": "edge",
        "label": "edge (로컬 LLM)",
        "group": "Local LLM",
        "description": "경량 Edge 모델",
        "supports_temperature": False,
        "supports_vision": False,
    },
    {
        "value": "core",
        "label": "core (로컬 LLM)",
        "group": "Local LLM",
        "description": "Core 모델",
        "supports_temperature": False,
        "supports_vision": False,
    },
    {
        "value": "code",
        "label": "code (로컬 LLM)",
        "group": "Local LLM",
        "description": "코드 특화 모델",
        "supports_temperature": False,
        "supports_vision": False,
    },
)

# feature-0007 (REQ-20260521-0001~3): API Vault (사용자별 OpenAI API key) 폐기 후
# AWS Bedrock (Seoul region `ap-northeast-2`) 의 Anthropic Claude 4.x 시리즈로
# 카탈로그 교체. backend 가 보내는 `model` 필드는 본 alias 만 허용하고, LiteLLM
# proxy gateway 가 alias → 실 Bedrock model ID (예: `bedrock/anthropic.claude-
# haiku-4-20250514-v1:0`) 로 라우팅한다. 실 model ID 정합은
# `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml` 에서
# 단일 source-of-truth 로 관리.
API_MODEL_OPTIONS: tuple[dict[str, Any], ...] = (
    {
        "value": "claude-sonnet-4",
        "label": "claude-sonnet-4",
        "group": "Claude 4",
        "description": "Anthropic Claude Sonnet 4.x (frontier, 고품질)",
        # Extended thinking (effort=high) 활성화 — temperature 는 반드시 1 이어야
        # 하므로 _temperature_kwargs 에서 temperature=0 을 주입하지 않도록 False.
        "supports_temperature": False,
        # TASK-0094 Sprint 2 (D13) — Claude Sonnet 4.x 는 native multimodal.
        # _build_attachment_context_section 의 kind=image 분기 routing 활성.
        "supports_vision": True,
    },
    {
        "value": "claude-haiku-4",
        "label": "claude-haiku-4",
        "group": "Claude 4",
        "description": "Anthropic Claude Haiku 4.x (가성비, 기본값)",
        # Extended thinking 활성화 — temperature=1 고정 요구사항으로 False.
        "supports_temperature": False,
        # TASK-0094 Sprint 2 (D13) — Claude Haiku 4.x 는 native multimodal.
        "supports_vision": True,
    },
)

_LOCAL_LLM_ENABLED = bool(os.getenv("LOCAL_LLM_API_BASE", "").strip())
_LOCAL_LLM_VALUES: frozenset[str] = frozenset(item["value"] for item in _LOCAL_LLM_MODELS)
# 내부 유효성 검사 (is_allowed_api_model) 에는 로컬 LLM 포함 — insight-worker 가
# edge/core/auto/code 를 사용하므로 허용 목록에서 제거하면 안 됨.
_ALL_MODEL_OPTIONS = (
    API_MODEL_OPTIONS + _LOCAL_LLM_MODELS if _LOCAL_LLM_ENABLED else API_MODEL_OPTIONS
)
_API_MODEL_INDEX = {item["value"]: item for item in _ALL_MODEL_OPTIONS}

# 웹 UI 모델 선택기에는 Bedrock Claude 모델만 노출 — 로컬 LLM(auto/edge/core/code)은
# insight-worker 전용이므로 사용자 선택 목록에서 제외.
PUBLIC_API_MODEL_OPTIONS: tuple[dict[str, Any], ...] = tuple(
    {
        "value": str(item["value"]),
        "label": str(item["label"]),
        "group": str(item["group"]),
        "description": str(item["description"]),
        "supports_vision": bool(item.get("supports_vision", False)),
    }
    for item in API_MODEL_OPTIONS
)


def get_api_model_meta(value: str | None) -> dict[str, Any] | None:
    return _API_MODEL_INDEX.get(str(value or "").strip())


def is_allowed_api_model(value: str | None) -> bool:
    return get_api_model_meta(value) is not None


def is_local_llm_model(value: str | None) -> bool:
    """로컬 LLM 게이트웨이를 경유해야 하는 모델인지 판별한다."""
    return str(value or "").strip().lower() in _LOCAL_LLM_VALUES


# ── 대화 답변(task='agent') 전용 라우팅 alias (2026-07-07, FR-edge-fallback-conversation-context-loss) ──
# 사용자 대면 assistant 답변은 edge(gemma) 폴백이 걸린 alias 로 litellm 에 보내지면 안 된다. 두 claude
# 계정이 모두 401/429 면 litellm 이 edge-fallback(gemma4:e2b, ctx 4096)으로 강등하는데, 이 2B 모델은
# ~30K 토큰 대화 히스토리를 잘라 맥락을 파괴하고 자신 있게 틀린 답을 silent 로 낸다(실측 conv …9e0883bb).
# 사용자 결정(2026-07-07): 대화 답변에 edge 는 고려 대상이 아니며 fallback 도 구성돼선 안 된다 —
# 두 계정 실패 시 gemma 강등 대신 429/401 을 raise 해 "명백한 실패처리"(agent_core LLM-error 핸들러가
# "서비스 요청량 한도… 잠시 후 다시 시도"로 안내)가 되게 한다.
#
# _call_llm(정의상 task='agent' 경로)이 litellm 에 보내는 model 만 edge-free alias 로 치환한다. 저장/표시/
# usage `model` 컬럼은 원본 alias(claude-haiku-4)를 유지하고, 실제 서빙 모델은 resolved_model(resp.model)
# 로 추적한다. 매핑에 없는 model(예: claude-sonnet-4 — 애초에 litellm fallbacks 목록에 없어 edge 강등이
# 없음)은 identity 로 그대로 반환한다(무회귀).
_CONVERSATION_ANSWER_ALIAS: dict[str, str] = {
    "claude-haiku-4": "claude-haiku-4-chat",
}
# 대화 답변 경로가 Bedrock 프록시로 보낼 때 쓸 기본 chat 모델(edge-free, litellm 등록 model_name).
# haiku 는 API_MODEL_OPTIONS 상 "기본값" 이며 claude-haiku-4-chat 가 그 edge-free chat alias 다.
_CONVERSATION_ANSWER_DEFAULT_CHAT = "claude-haiku-4-chat"


def conversation_answer_model(value: str | None) -> str:
    """사용자 대면 assistant 답변(task='agent')을 litellm 에 보낼 때 쓸 edge-free alias 를 반환한다.

    edge(gemma) 폴백이 걸린 대화 모델(claude-haiku-4)은 대화 전용 edge-free alias
    (claude-haiku-4-chat)로 치환한다. 반환값은 litellm 호출 kwarg('model')로만 쓰고,
    표시/저장/usage 기록에는 원본 문자열을 유지한다(호출측 책임).

    TASK-alias-leak-guard: 대화 답변 경로는 고정 Bedrock 클라이언트로 나간다(`_call_llm` 은
    tier-resolve 하지 않음 — FR-edge-fallback 정합상 gemma 강등 금지). 따라서 로컬 게이트웨이
    alias(auto/edge/core/code)나 미등록 bare family alias('claude')가 **identity 로 통과하면
    Bedrock 프록시가 "Invalid model name passed in model=..." 400** 을 반환한다(실측: 다수 대화의
    `LLM 호출 오류` + `__ask_worker__`). 운영 `.env` 의 `OPENAI_MODEL=auto` 가 대표 트리거.
    이들을 대화 기본 chat 모델(claude-haiku-4-chat)로 fail-loud 해소해 raw alias 가 Bedrock 으로
    새지 않게 한다(대화는 Claude 유지 — gemma 로 강등하지 않음). 등록된 Claude 모델
    (claude-sonnet-4 등)과 이미 해소된 chat alias 는 identity(무회귀).
    """
    name = str(value or "").strip()
    mapped = _CONVERSATION_ANSWER_ALIAS.get(name)
    if mapped is not None:
        return mapped
    # 로컬 게이트웨이 alias 또는 미등록 bare family alias 'claude' → Bedrock 400 유발. 기본 chat 로 해소.
    if is_local_llm_model(name) or name.lower() == "claude":
        _log.warning(
            "conversation_answer_model: 비대화 alias %r 를 Bedrock 대화 경로로 보낼 수 없어 "
            "%s 로 해소(Bedrock 'Invalid model name' 400 방지).",
            name, _CONVERSATION_ANSWER_DEFAULT_CHAT,
        )
        return _CONVERSATION_ANSWER_DEFAULT_CHAT
    return name


def model_supports_temperature(value: str | None) -> bool:
    meta = get_api_model_meta(value)
    return bool(meta and meta.get("supports_temperature"))


def model_supports_vision(value: str | None) -> bool:
    """TASK-0094 Sprint 2 — 첨부 image kind 의 base64 inline 분기 routing 결정.

    True 인 모델만 `_build_attachment_context_section` 이 image kind 첨부의 MinIO
    bytes 를 fetch + base64 inline 으로 content array 에 주입한다. False 인 모델
    은 image 첨부를 무시하고 사용자에게 toast 안내 ("이 모델은 이미지 분석 불가").

    D11 (file_image consent) + D13 (server-side bytes + base64 inline only,
    signed URL 외부 송신 금지) 의 정합 gate 의 모델 측 prerequisite.

    feature-0007 (bedrock) 정합: backend 는 OpenAI Chat Completions spec 의
    `image_url` content-array 로 작성, LiteLLM proxy gateway 가 Anthropic vision
    spec (`{"type":"image","source":{"type":"base64",...}}`) 로 자동 normalize.
    Claude Sonnet 4.x / Haiku 4.x 는 native multimodal 이므로 둘 다 True.
    """
    meta = get_api_model_meta(value)
    return bool(meta and meta.get("supports_vision"))


# ── 모델별 max_tokens 관리 ──
# 로컬 LLM: 4K 컨텍스트 내에서 reasoning + content 수용
# Claude (Bedrock): default cap 미명시 시 비용 폭주 worst-case (codex blindspot
# #4, CHG-0004) — task 별 명시 cap 추가. Claude native max output 은 Sonnet 4.6=128K /
# Haiku 4.5=64K 이며, 대화(agent) 경로는 아래 _CLAUDE_MODEL_MAX_OUTPUT 로 모델별 관리한다.
_LOCAL_LLM_MAX_TOKENS: dict[str, int] = {
    "insight": 1024,   # 인사이트: JSON 출력, reasoning ~700 + content ~200
    "agent": 2048,     # 에이전트 루프: tool calls + 복잡한 응답
    "summary": 512,    # 요약/토픽: 짧은 출력
    "prompt_gen": 3072,  # 제품 시스템 프롬프트 자동작성: 완성된 본문(스키마·테이블·가이드) — 4K 컨텍스트 내 최대 (TASK-0232)
    "sql_fix": 1024,   # SQL 수정: 중간 복잡도
    "validate": 512,   # 스텝 검증: 짧은 JSON
}

# Claude (Bedrock) 의 task 별 default cap. backend 가 OpenAI Chat Completions
# 의 max_tokens param 을 LiteLLM 에 전달 → Anthropic API 의 max_tokens 로 변환.
# Extended thinking 활성화 시 max_tokens 가 budget_tokens 보다 커야 하며, 실제
# 출력 = thinking_tokens + content_tokens 를 포함한다.
# Sonnet: budget=16000 → max_tokens≥16001. Haiku: budget=5000 → max_tokens≥5001.
# plan/insight/agent 등 thinking 을 소비하는 task 는 넉넉하게 설정.
_CLAUDE_MAX_TOKENS: dict[str, int] = {
    "insight": 18000,  # thinking(≤16000) + 인사이트 JSON 출력
    "agent": 20000,    # thinking(≤16000) + agent loop tool calls + 복잡한 응답
    "summary": 7000,   # thinking(≤5000, haiku) + 요약 출력
    "prompt_gen": 20000,  # thinking + 완성된 제품 시스템 프롬프트 본문 — "summary"(7000) 로는 본문이 중간 잘림 (TASK-0232)
    "sql_fix": 18000,  # thinking + SQL 수정
    "validate": 7000,  # thinking + step validation
}

# ── 모델별 native max output (대화 총 출력 상한의 ceiling) ────────────────────
# reasoning-budget-per-model: 관리 콘솔 '모델 총 출력' 슬라이더/입력의 상한(maximum)으로 쓴다.
# 실제 대화 총 출력 default·override 는 runtime_settings(agent_max_output) 계층이 관리한다 —
# 순환 import(config→runtime_settings→model_catalog) 방지를 위해 여기서는 native ceiling 만 노출하고,
# max_tokens_for_model 의 task 별 cap 은 건드리지 않는다(plan/insight 등 "agent" task 공유 소비자 무회귀).
_CLAUDE_MODEL_MAX_OUTPUT: dict[str, int] = {
    "claude-sonnet-4": 128000,  # Sonnet 4.6 native max output
    "claude-haiku-4": 64000,    # Haiku 4.5 native max output
}
_CLAUDE_MODEL_MAX_OUTPUT_FALLBACK = 20000  # 미등록 claude 모델 — 보수 fallback


def model_native_max_output(model: str | None) -> int:
    """모델의 native max output token(대화 총 출력 상한의 ceiling). 미등록 claude 는 보수 fallback.

    관리 콘솔의 '모델 총 출력' 슬라이더/입력 상한(maximum)으로 사용된다.
    """
    name = str(model or "").strip()
    return _CLAUDE_MODEL_MAX_OUTPUT.get(name, _CLAUDE_MODEL_MAX_OUTPUT_FALLBACK)


def max_tokens_for_model(model: str | None, task: str = "agent") -> int | None:
    """모델별 max_tokens 반환. Bedrock Claude 도 명시 cap (비용 폭주 차단).

    task 별 cap(_CLAUDE_MAX_TOKENS)은 무변경 — 대화 총 출력의 모델별 상향은 runtime_settings 의
    agent_max_output(model) 계층이 담당하므로 이 함수는 plan/insight 등 "agent" task 공유 소비자에
    회귀를 주지 않는다.
    """
    if is_local_llm_model(model):
        return _LOCAL_LLM_MAX_TOKENS.get(task, 1024)
    # Claude alias (Bedrock) 인 경우 명시 cap (CHG-0004)
    if model and str(model).startswith("claude-"):
        return _CLAUDE_MAX_TOKENS.get(task, 8192)
    # 그 외 (알 수 없는 모델 — local/claude alias 어디에도 매칭 안 됨) 은 cap 미적용 (API default).
    # TASK-0237: 구 주석 "OpenAI direct legacy" 정정 — 카탈로그에 GPT 모델 0개라 GPT 경로는 없으나,
    # 잘못된/미등록 model 문자열 입력에 대한 fallback 으로 None(무제한) 유지 (동작 무변경).
    return None


# ── 사용자 지정 추론 강도 (extended thinking budget) ──────────────────────────
# feature-0003 reasoning-effort-selector (REQ-20260704-reasoning-effort):
# 대화 화면에서 사용자가 4단계(낮음/일반/높음/매우 높음)로 추론 강도를 직접 고른다.
# 상용 서비스(Claude extended thinking · ChatGPT reasoning effort)와 동형.
#
# 명시 레벨(낮음/높음/매우 높음)은 요청 단위 thinking budget_tokens 로 매핑되어, backend
# `_call_llm` 이 `extra_body={"thinking": {"type":"enabled","budget_tokens":N}}` 로 전달 →
# LiteLLM 이 litellm_config.yaml 의 alias 별 고정 thinking 값을 **이 요청에 한해 override**.
#
# ── '일반' = override 없음(모델 config 기본 thinking 유지) — B1 회귀 방지(REV 적대검증) ──
#   '일반' 은 의도적으로 budget map 에서 제외한다. 매핑에 고정값(예: 5000)을 두면, 선택기를
#   한 번도 건드리지 않은 사용자·구 클라이언트의 모든 요청이 그 값으로 강등돼 **claude-sonnet-4
#   의 config 기본 thinking(16000)이 조용히 5000 으로 떨어지는 회귀**가 발생한다. '일반'을
#   no-override 로 두면 각 모델이 자기 config 기본값(haiku 5000 / sonnet 16000)을 그대로 쓰고
#   (하위호환·무회귀), 사용자가 '낮음'으로 속도를, '높음'/'매우 높음'으로 심도를 명시 조정한다.
#   '일반' = "normal" = 모델 기본 = 가장 자연스러운 중립 라벨.
#
# Anthropic 제약: budget_tokens ≥ 1024 且 budget < max_tokens. 아래 값은 요청 단위 override 의
#   **base default** 이며(모델 무관), reasoning-budget-per-model 이후 관리 콘솔에서 모델별로
#   상향할 수 있다(상한 = 모델 native max output − 1024). backend agent 경로는 주입 직전
#   min(budget, max_tokens − 1024) 로 clamp 하므로 budget < max_tokens 는 항상 보장된다.
REASONING_LEVELS: tuple[str, ...] = ("low", "normal", "high", "max")

DEFAULT_REASONING_LEVEL = "normal"

# 명시 thinking budget override(요청 단위). "normal" 은 의도적 부재 → thinking_budget_for_level
# 이 None 반환 → _call_llm 이 주입 안 함 → alias config 기본 thinking 유지(위 B1 주석 참조).
_REASONING_BUDGETS: dict[str, int] = {
    "low": 2000,     # 낮음 — 최소 추론(빠름), Anthropic 하한(1024) 여유 상회
    "high": 10000,   # 높음 — 심층 추론
    "max": 16000,    # 매우 높음 — base default(모델별 상한까지 관리 콘솔에서 상향 가능)
}

# 웹 UI 선택기 노출용 (value → 한국어 라벨). 표시 순서 = 낮음→매우 높음.
REASONING_LEVEL_OPTIONS: tuple[dict[str, str], ...] = (
    {"value": "low", "label": "낮음"},
    {"value": "normal", "label": "일반"},
    {"value": "high", "label": "높음"},
    {"value": "max", "label": "매우 높음"},
)


def normalize_reasoning_level(value: str | None) -> str | None:
    """입력 추론 강도 레벨을 유효 키로 정규화한다.

    유효 레벨(low/normal/high/max)만 통과시키고, 그 외(빈 값·미상 문자열)는 None 반환
    → 호출측이 override 없이 config 기본값을 쓰도록(안전한 무시). 값 검증 겸 정규화.
    """
    key = str(value or "").strip().lower()
    return key if key in REASONING_LEVELS else None


def thinking_budget_for_level(level: str | None) -> int | None:
    """추론 강도 레벨 → thinking budget_tokens.

    'normal'/미지정/미상 레벨은 None → config 의 alias 별 고정 thinking 을 override 하지 않는다
    (B1 회귀 방지 — '일반'은 모델 기본값 유지). 명시 레벨(low/high/max)만 정수 budget 반환.
    """
    return _REASONING_BUDGETS.get(normalize_reasoning_level(level) or "")


def model_supports_thinking(model: str | None) -> bool:
    """extended thinking(요청 단위 budget override) 지원 모델인지 판별한다.

    Claude alias(claude-*)만 지원. 로컬 LLM(gemma/edge-fallback 등)은 thinking 미지원이라
    LiteLLM drop_params 가 thinking 파라미터를 제거하므로, 애초에 주입하지 않는다(무의미한
    파라미터 방지 + 프론트 선택기 비활성화 판정에도 사용).
    """
    return str(model or "").strip().lower().startswith("claude-")


# ── AI 활동 taxonomy (AI 운영 관제 패널 — 확장 레지스트리, TASK-AIOPS) ────────────
# llm_usage.task literal 을 관제 카테고리로 매핑한다. 신규 AI 활동은 아래 dict 에 한 줄만
# 추가하면 패널 드릴다운에 편입되고, 미등록 task 는 taxonomy_for() 가 ai.other.unmapped 로
# self-surface 한다 (등록 누락·오타·신규 task 도 사라지지 않고 패널 Attention 에 노출).
# 스키마/마이그레이션 불필요 — task 는 llm_usage.task(VARCHAR64) 자유 문자열이므로 DISTINCT
# 후 매핑만 하면 된다.
#
# 계측 커버리지 주의: 임베딩(client.embeddings.create) 과 provider health probe 는 응답에
# usage 필드가 없어(SDK 한계) llm_usage 에 기록되지 않는다 → taxonomy 등록 대상 아님.
# 패널의 '계측 커버리지' 각주에서 미계측으로 정직하게 노출한다('전체 비용' 오해 방지).
TASK_TAXONOMY: dict[str, dict[str, Any]] = {
    # 메인 추론 (사용자 대면)
    "agent":               {"category": "ai.reasoning.agent",       "label": "에이전트 추론"},
    # 보조 추론 (대화 파이프라인 내부 소량 호출)
    "validate":            {"category": "ai.reasoning.aux",         "label": "단계 JSON 검증"},
    "summary":             {"category": "ai.reasoning.aux",         "label": "대화 요약"},
    "classify":            {"category": "ai.reasoning.aux",         "label": "주제 이탈 판정"},
    "topic":               {"category": "ai.reasoning.aux",         "label": "대화 주제 추론"},
    "sql_fix":             {"category": "ai.reasoning.aux",         "label": "SQL 오류 수정"},
    # 지식베이스 보강
    "glossary_suggest":    {"category": "ai.kb.enrich",             "label": "용어사전 후보"},
    # 인사이트 분석
    "schema_insight":      {"category": "ai.insight.analyze",       "label": "스키마 분석"},
    "table_insight":       {"category": "ai.insight.analyze",       "label": "테이블 분석"},
    "account_insight":     {"category": "ai.insight.analyze",       "label": "계정 분석"},
    "node_analysis":       {"category": "ai.insight.analyze",       "label": "그래프 노드 분석"},
    # 프롬프트 자동생성 (신규 계측 — 제품/역할/계정 생성 + 자율 sweep 워커)
    "prompt_gen":          {"category": "ai.prompt.autogen",        "label": "프롬프트 자동생성"},
    # 메타데이터 자동완성 (신규 계측)
    "metadata_summary":    {"category": "ai.metadata.autocomplete", "label": "메타 설명 자동완성"},
    "metadata_prompt_gen": {"category": "ai.metadata.autocomplete", "label": "메타 프롬프트 자동생성"},
}

# 카테고리 → 표시 라벨 (패널 드릴다운 accordion 상위 그룹 라벨). 표시 순서는 dict 삽입 순서.
AI_CATEGORY_LABELS: dict[str, str] = {
    "ai.reasoning.agent":       "에이전트 추론",
    "ai.reasoning.aux":         "보조 추론",
    "ai.kb.enrich":             "지식베이스 보강",
    "ai.insight.analyze":       "인사이트 분석",
    "ai.prompt.autogen":        "프롬프트 자동생성",
    "ai.metadata.autocomplete": "메타데이터 자동완성",
    "ai.other.unmapped":        "미분류 활동",
}

_UNMAPPED_CATEGORY = "ai.other.unmapped"


def taxonomy_for(task: str | None) -> dict[str, Any]:
    """llm_usage.task → 관제 taxonomy 항목 {task, category, label}.

    미등록/오타/신규 task 는 ai.other.unmapped 로 self-surface (패널에서 '미분류 활동'으로
    노출 — 등록 누락도 조용히 사라지지 않는다). label 은 원본 task 문자열을 그대로 보존해
    운영자가 어떤 미등록 활동인지 식별할 수 있게 한다."""
    key = str(task or "").strip()
    entry = TASK_TAXONOMY.get(key)
    if entry is not None:
        return {"task": key, "category": entry["category"], "label": entry["label"]}
    return {
        "task": key or "(none)",
        "category": _UNMAPPED_CATEGORY,
        "label": key or "(미상)",
    }


def ai_categories() -> dict[str, str]:
    """카테고리 코드 → 표시 라벨 (패널 드릴다운 그룹 라벨). 등록 category 의 상위 그룹핑."""
    return dict(AI_CATEGORY_LABELS)
