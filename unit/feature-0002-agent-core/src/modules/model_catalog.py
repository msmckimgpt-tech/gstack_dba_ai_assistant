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


API_DEFAULT_MODEL = "gpt-5.4-nano"

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

API_MODEL_OPTIONS: tuple[dict[str, Any], ...] = (
    {
        "value": "gpt-5.4",
        "label": "gpt-5.4",
        "group": "GPT-5",
        "description": "최신 GPT-5 base 모델",
        "supports_temperature": False,
    },
    {
        "value": "gpt-5.4-mini",
        "label": "gpt-5.4-mini",
        "group": "GPT-5",
        "description": "GPT-5.4 mini 모델",
        "supports_temperature": False,
    },
    {
        "value": "gpt-5.4-nano",
        "label": "gpt-5.4-nano",
        "group": "GPT-5",
        "description": "GPT-5.4 nano 모델",
        "supports_temperature": False,
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
# 상용 LLM: 제한 없음 (None) — API 기본값 사용
# 로컬 LLM: 4K 컨텍스트 내에서 reasoning + content 수용
_LOCAL_LLM_MAX_TOKENS: dict[str, int] = {
    "insight": 1024,   # 인사이트: JSON 출력, reasoning ~700 + content ~200
    "agent": 2048,     # 에이전트 루프: tool calls + 복잡한 응답
    "summary": 512,    # 요약/토픽: 짧은 출력
    "sql_fix": 1024,   # SQL 수정: 중간 복잡도
    "validate": 512,   # 스텝 검증: 짧은 JSON
}


def max_tokens_for_model(model: str | None, task: str = "agent") -> int | None:
    """모델별 max_tokens를 반환한다.

    상용 LLM은 None(제한 없음), 로컬 LLM은 태스크별 제한값을 반환.
    """
    if not is_local_llm_model(model):
        return None
    return _LOCAL_LLM_MAX_TOKENS.get(task, 1024)
