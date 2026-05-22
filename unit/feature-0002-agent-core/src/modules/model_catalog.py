from __future__ import annotations

import os
from typing import Any

__all__ = [
    "API_DEFAULT_MODEL",
    "API_MODEL_OPTIONS",
    "PUBLIC_API_MODEL_OPTIONS",
    "get_api_model_meta",
    "is_allowed_api_model",
    "is_local_llm_model",
    "max_tokens_for_model",
    "model_supports_temperature",
]


API_DEFAULT_MODEL = "claude-sonnet-4"

# ── 로컬 LLM 게이트웨이 모델 (LOCAL_LLM_API_BASE 설정 시 자동 추가) ──
_LOCAL_LLM_MODELS: tuple[dict[str, Any], ...] = (
    {
        "value": "auto",
        "label": "auto (로컬 LLM)",
        "group": "Local LLM",
        "description": "게이트웨이 자동 라우팅",
        "supports_temperature": False,
    },
    {
        "value": "edge",
        "label": "edge (로컬 LLM)",
        "group": "Local LLM",
        "description": "경량 Edge 모델",
        "supports_temperature": False,
    },
    {
        "value": "core",
        "label": "core (로컬 LLM)",
        "group": "Local LLM",
        "description": "Core 모델",
        "supports_temperature": False,
    },
    {
        "value": "code",
        "label": "code (로컬 LLM)",
        "group": "Local LLM",
        "description": "코드 특화 모델",
        "supports_temperature": False,
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
        "supports_temperature": True,
    },
    {
        "value": "claude-haiku-4",
        "label": "claude-haiku-4",
        "group": "Claude 4",
        "description": "Anthropic Claude Haiku 4.x (가성비, 기본값)",
        "supports_temperature": True,
    },
)

_LOCAL_LLM_ENABLED = bool(os.getenv("LOCAL_LLM_API_BASE", "").strip())
_LOCAL_LLM_VALUES: frozenset[str] = frozenset(item["value"] for item in _LOCAL_LLM_MODELS)
_ALL_MODEL_OPTIONS = (
    API_MODEL_OPTIONS + _LOCAL_LLM_MODELS if _LOCAL_LLM_ENABLED else API_MODEL_OPTIONS
)
_API_MODEL_INDEX = {item["value"]: item for item in _ALL_MODEL_OPTIONS}

PUBLIC_API_MODEL_OPTIONS: tuple[dict[str, str], ...] = tuple(
    {
        "value": str(item["value"]),
        "label": str(item["label"]),
        "group": str(item["group"]),
        "description": str(item["description"]),
    }
    for item in _ALL_MODEL_OPTIONS
)


def get_api_model_meta(value: str | None) -> dict[str, Any] | None:
    return _API_MODEL_INDEX.get(str(value or "").strip())


def is_allowed_api_model(value: str | None) -> bool:
    return get_api_model_meta(value) is not None


def is_local_llm_model(value: str | None) -> bool:
    """로컬 LLM 게이트웨이를 경유해야 하는 모델인지 판별한다."""
    return str(value or "").strip().lower() in _LOCAL_LLM_VALUES


def model_supports_temperature(value: str | None) -> bool:
    meta = get_api_model_meta(value)
    return bool(meta and meta.get("supports_temperature"))


# ── 모델별 max_tokens 관리 ──
# 로컬 LLM: 4K 컨텍스트 내에서 reasoning + content 수용
# Claude (Bedrock): default cap 미명시 시 비용 폭주 worst-case (codex blindspot
# #4, CHG-0004) — task 별 명시 cap 추가. Bedrock Sonnet 4.6 의 native max output
# 은 64K 이지만 본 backend 의 agent loop turn 단위에서는 그보다 훨씬 작아도 충분.
_LOCAL_LLM_MAX_TOKENS: dict[str, int] = {
    "insight": 1024,   # 인사이트: JSON 출력, reasoning ~700 + content ~200
    "agent": 2048,     # 에이전트 루프: tool calls + 복잡한 응답
    "summary": 512,    # 요약/토픽: 짧은 출력
    "sql_fix": 1024,   # SQL 수정: 중간 복잡도
    "validate": 512,   # 스텝 검증: 짧은 JSON
}

# Claude (Bedrock) 의 task 별 default cap. backend 가 OpenAI Chat Completions
# 의 max_tokens param 을 LiteLLM 에 전달 → Anthropic API 의 max_tokens 로 변환.
# 비용 폭주 worst-case (사용자 query 가 long context 또는 model hallucination
# 으로 max output 까지 채우는 case) 차단. plan / summary 등 짧은 출력은 작게,
# agent loop 응답은 크게.
_CLAUDE_MAX_TOKENS: dict[str, int] = {
    "insight": 2048,   # 인사이트 JSON
    "agent": 8192,     # agent loop tool calls + 복잡한 응답
    "summary": 1024,   # 요약 / topic 짧은 출력
    "sql_fix": 2048,   # SQL 수정
    "validate": 1024,  # step validation
}


def max_tokens_for_model(model: str | None, task: str = "agent") -> int | None:
    """모델별 max_tokens 반환. Bedrock Claude 도 명시 cap (비용 폭주 차단)."""
    if is_local_llm_model(model):
        return _LOCAL_LLM_MAX_TOKENS.get(task, 1024)
    # Claude alias (Bedrock) 인 경우 명시 cap (CHG-0004)
    if model and str(model).startswith("claude-"):
        return _CLAUDE_MAX_TOKENS.get(task, 8192)
    # 그 외 (OpenAI direct legacy 등) 은 무제한 (API default)
    return None
