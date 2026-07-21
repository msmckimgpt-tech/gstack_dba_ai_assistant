"""feature-0018 runtime-settings — 관리 콘솔(`시스템 > 설정`)에서 조정하는 런타임 설정의
레지스트리 + resolver + 프로세스 간 전파 스냅샷.

무엇을 담는가
--------------
assistant 가 작동할 때 참조하는 운영 값 중, 현재 코드에 **이미 구성된** 것만 등록한다
(요청: "아직 구성되지 않은 부분은 억지로 추가하지 말 것"):

- **TIME_OUT 계열**: shared/config.py 에 정의된 `*_TIMEOUT*` 상수들(쿼리·에이전트 실행,
  인사이트/플랜, 지식베이스, DB 연결, 커넥션 상태 프로브, MCP). 스케줄 tick·recheck
  간격·backoff 처럼 "timeout 이 아닌" 값은 제외한다.
- **모델별 thinking budget_tokens**: shared/model_catalog.py 의 카탈로그를 순회해 extended
  thinking 지원 모델(`claude-*`)마다 1 항목을 **자동 생성**한다. 카탈로그에 모델이 추가되면
  본 레지스트리도 자연히 확장된다(코드 변경 불필요).

어떻게 저장·적용되는가 (하이브리드)
-------------------------------------
- **source of truth = memory DB(MySQL) `WebRuntimeSettings`** — 관리 콘솔 endpoint 가 RBAC·
  audit 와 함께 기록한다. 본 모듈은 **DB 를 직접 다루지 않는다**(저결합; config.py 가 import
  하는 shared 모듈이므로 import-time DB 접근을 배제).
- **프로세스 간 전파 = 공유 볼륨 스냅샷 파일** `RUNTIME_SETTINGS_SNAPSHOT_PATH`
  (기본 `/shared/runtime_settings.json`). web·worker 컨테이너가 `/shared` 를 공유 마운트하므로
  endpoint 가 DB commit 후 이 파일을 원자적으로 재작성하면 모든 프로세스가 읽는다.
- **적용 시점**:
  * `apply_mode="live"` 값 — 소비처가 `get_int(key)` 로 매 호출 짧은 TTL 캐시로 읽어 **즉시**
    (≤TTL 초) 반영. 재시작 불필요.
  * `apply_mode="restart"` 값 — shared/config.py 가 import 시 `startup_int()` 로 스냅샷을 1회만
    읽어 상수에 반영한다. 프로세스 수명 내 고정 → **다음 재배포/재시작 시** 반영. 저수준
    커넥션 timeout 등 라이브 변경 위험이 큰 값에 사용.

안전장치
----------
- 스냅샷 파일이 없거나(개발/CI) 파싱 실패면 조용히 기본값으로 폴백한다(fail-open).
- `RUNTIME_SETTINGS_DISABLED=1` 이면 override 를 일절 적용하지 않는다(kill-switch).
- 모든 override 는 스펙의 [minimum, maximum] 로 clamp 되어 위험값 주입을 차단한다.

의존성: os·json·time·threading·shared.model_catalog 만. shared.config 를 import 하지 않아
`config → runtime_settings → model_catalog` 단방향 DAG(순환 없음)를 유지한다.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from shared import model_catalog

__all__ = [
    "list_specs",
    "spec_for",
    "get_int",
    "startup_int",
    "effective_value",
    "model_thinking_budget_override",
    "reasoning_budget_override",
    "agent_max_output",
    "validate_value",
    "serialize_registry",
    "snapshot_path",
    "read_overrides",
    "write_snapshot",
    "invalidate_cache",
    "MODEL_BUDGET_KEY_PREFIX",
    "REASONING_BUDGET_KEY_PREFIX",
    "AGENT_MAX_OUTPUT_KEY_PREFIX",
    "GROUP_TIMEOUT",
    "GROUP_MODEL_BUDGET",
    "GROUP_REASONING_BUDGET",
    "GROUP_AGENT_MAX_OUTPUT",
    "GROUP_REDTEAM",
]

GROUP_TIMEOUT = "timeout"
GROUP_MODEL_BUDGET = "model_thinking_budget"
MODEL_BUDGET_KEY_PREFIX = "model_thinking_budget:"

_SNAPSHOT_ENV = "RUNTIME_SETTINGS_SNAPSHOT_PATH"
_DEFAULT_SNAPSHOT_PATH = "/shared/runtime_settings.json"
_DISABLED_ENV = "RUNTIME_SETTINGS_DISABLED"
_TTL_ENV = "RUNTIME_SETTINGS_CACHE_TTL_SEC"
_DEFAULT_TTL_SEC = 10.0


# ── TIME_OUT 레지스트리 ────────────────────────────────────────────────────
# default 값은 shared/config.py 의 env 기본값과 **동일하게 유지**해야 한다(단일 진실원본은
# config.py 이나, 순환 import 방지를 위해 여기 리터럴로 복제 — config.py 가 override 없을 때
# 반환하는 값과 반드시 일치해야 byte-동치가 보장됨). 값 변경 시 양쪽을 함께 수정한다.
#
# apply_mode:
#   "live"    — 소비처가 get_int() 로 읽어 즉시 반영(재시작 불필요). 요청/연산 단위로 안전.
#   "restart" — config.py 가 import 시 반영. 저수준 커넥션/프로브 timeout 등 라이브 변경 위험.
_TIMEOUT_SPECS: tuple[dict[str, Any], ...] = (
    # ── 쿼리·에이전트 실행 ──
    {
        "key": "AGENT_TIMEOUT_SEC",
        "category": "쿼리·에이전트 실행",
        "label": "에이전트/쿼리 실행 타임아웃",
        "description": "LLM 호출·쿼리 실행 등 기본 실행 상한. 서비스 응답 지연에 가장 직접적인 값. LLM 요청 경로는 즉시 반영되며, 저수준 DB 연결 설정에 재사용되는 경로는 재배포 시 반영됩니다.",
        "unit": "초",
        "default": 60,
        "minimum": 5,
        "maximum": 3600,
        "apply_mode": "live",
    },
    # ── 인사이트·플랜 ──
    {
        "key": "AGENT_INSIGHT_TIMEOUT_SEC",
        "category": "인사이트·플랜",
        "label": "인사이트 LLM 타임아웃",
        "description": "스키마/테이블/계정 인사이트 생성 LLM 호출 상한.",
        "unit": "초",
        "default": 30,
        "minimum": 5,
        "maximum": 1800,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_PLAN_TIMEOUT_SEC",
        "category": "인사이트·플랜",
        "label": "플랜 생성 타임아웃",
        "description": "질의 계획(plan) 생성 LLM 호출 상한.",
        "unit": "초",
        "default": 35,
        "minimum": 5,
        "maximum": 1800,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_PLAN_TIMEOUT_RECOVERY_SEC",
        "category": "인사이트·플랜",
        "label": "플랜 복구 타임아웃",
        "description": "플랜 실패 후 복구 재시도 시 적용하는 축소 상한(기본 타임아웃보다 작게).",
        "unit": "초",
        "default": 20,
        "minimum": 3,
        "maximum": 1800,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_PLAN_TIMEOUT_MIN_SEC",
        "category": "인사이트·플랜",
        "label": "플랜 최소 타임아웃",
        "description": "남은 예산이 적을 때 보장하는 플랜 호출 최소 상한(하한 바닥값).",
        "unit": "초",
        "default": 8,
        "minimum": 1,
        "maximum": 600,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_RAG_PRIORITY_TIMEOUT_SEC",
        "category": "인사이트·플랜",
        "label": "RAG 우선탐색 타임아웃",
        "description": "우선순위 RAG(지식 우선 조회) 단계 상한.",
        "unit": "초",
        "default": 12,
        "minimum": 2,
        "maximum": 600,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_OBJECT_RESOLVE_TIMEOUT_SEC",
        "category": "인사이트·플랜",
        "label": "객체 해석 타임아웃",
        "description": "질의 대상 DB 객체(테이블/컬럼) 해석 단계 상한.",
        "unit": "초",
        "default": 8,
        "minimum": 2,
        "maximum": 600,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC",
        "category": "인사이트·플랜",
        "label": "인사이트 SQL 작성 타임아웃",
        "description": "인사이트용 SQL 자동 작성 LLM 호출 상한.",
        "unit": "초",
        "default": 20,
        "minimum": 3,
        "maximum": 600,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_SQL_GROUNDED_REVIEW_TIMEOUT_SEC",
        "category": "인사이트·플랜",
        "label": "SQL 근거검토 타임아웃",
        "description": "생성 SQL 의 스키마 근거 검토(grounded review) 단계 상한.",
        "unit": "초",
        "default": 12,
        "minimum": 2,
        "maximum": 600,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC",
        "category": "인사이트·플랜",
        "label": "지식 SQL 폴백 타임아웃",
        "description": "지식 기반 SQL 폴백 경로 상한.",
        "unit": "초",
        "default": 20,
        "minimum": 3,
        "maximum": 600,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_INSIGHT_OBJECT_VERIFY_TIMEOUT_MS",
        "category": "인사이트·플랜",
        "label": "인사이트 객체 검증 타임아웃",
        "description": "인사이트 대상 객체 존재 검증 쿼리 상한.",
        "unit": "밀리초",
        "default": 1500,
        "minimum": 100,
        "maximum": 60000,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC",
        "category": "인사이트·플랜",
        "label": "인사이트 워커 락 타임아웃",
        "description": "인사이트 워커 advisory-lock 획득 대기 상한.",
        "unit": "초",
        "default": 1,
        "minimum": 1,
        "maximum": 120,
        "apply_mode": "restart",
    },
    # ── 지식베이스(임베딩·락) ──
    {
        "key": "AGENT_KB_EMBEDDING_TIMEOUT_SEC",
        "category": "지식베이스",
        "label": "KB 임베딩 타임아웃",
        "description": "지식베이스 오프라인/배치 임베딩 호출 상한.",
        "unit": "초",
        "default": 60,
        "minimum": 5,
        "maximum": 1800,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_KB_QUERY_EMBED_TIMEOUT_SEC",
        "category": "지식베이스",
        "label": "KB 질의 임베딩 타임아웃",
        "description": "상호작용 준비 단계의 질의 임베딩(빠른 실패) 상한.",
        "unit": "초",
        "default": 20,
        "minimum": 2,
        "maximum": 600,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_GLOBAL_KB_LOCK_TIMEOUT_SEC",
        "category": "지식베이스",
        "label": "전역 KB 락 타임아웃",
        "description": "전역 지식베이스 쓰기 락 획득 대기 상한.",
        "unit": "초",
        "default": 3,
        "minimum": 1,
        "maximum": 120,
        "apply_mode": "restart",
    },
    # ── DB 연결 ──
    {
        "key": "AGENT_DB_CONNECT_TIMEOUT_SEC",
        "category": "DB 연결",
        "label": "데이터플레인 연결 타임아웃",
        "description": "대상 datasource(TCP/로그인) 연결 수립 상한. 쿼리 예산과 분리된 짧은 상한.",
        "unit": "초",
        "default": 10,
        "minimum": 1,
        "maximum": 300,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC",
        "category": "DB 연결",
        "label": "컨트롤플레인 연결 타임아웃",
        "description": "메모리/컨트롤플레인 DB 연결 수립 상한. 컨트롤플레인은 breaker 가 없어(fast-fail=전체 마비) 너무 짧으면 순간 지연에도 앱 전역 실패 위험 — 최소 3초.",
        "unit": "초",
        "default": 10,
        "minimum": 3,
        "maximum": 300,
        "apply_mode": "restart",
    },
    # ── 커넥션 상태 프로브 ──
    {
        "key": "AGENT_RELATIONSHIP_PROBE_TIMEOUT_MS",
        "category": "커넥션 상태 프로브",
        "label": "관계 프로브 락 타임아웃",
        "description": "관계 다이어그램 프로브의 락 대기 상한(MSSQL LOCK_TIMEOUT 등). 0 이면 미적용.",
        "unit": "밀리초",
        "default": 5000,
        "minimum": 0,
        "maximum": 120000,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_CONN_PROBE_TIMEOUT_MS_BASE",
        "category": "커넥션 상태 프로브",
        "label": "연결 프로브 기본 타임아웃",
        "description": "datasource 상태 프로브의 적응형 시작 상한(base).",
        "unit": "밀리초",
        "default": 100,
        "minimum": 10,
        "maximum": 60000,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_CONN_PROBE_TIMEOUT_MS_MAX",
        "category": "커넥션 상태 프로브",
        "label": "연결 프로브 최대 타임아웃",
        "description": "datasource 상태 프로브의 적응형 상한(max). base 이상으로 보정된다.",
        "unit": "밀리초",
        "default": 10000,
        "minimum": 10,
        "maximum": 120000,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_CONN_TCP_TIMEOUT_MS",
        "category": "커넥션 상태 프로브",
        "label": "연결 TCP 선검사 타임아웃",
        "description": "상태 프로브의 TCP 핸드셰이크 선검사 상한. 원거리 datasource RTT 를 흡수.",
        "unit": "밀리초",
        "default": 5000,
        "minimum": 10,
        "maximum": 120000,
        "apply_mode": "restart",
    },
    # ── MCP ──
    {
        "key": "MCP_TIMEOUT_SEC",
        "category": "MCP",
        "label": "MCP 요청 타임아웃",
        "description": "MCP(execute_sql 등) 요청 상한.",
        "unit": "초",
        "default": 20,
        "minimum": 2,
        "maximum": 600,
        "apply_mode": "live",
    },
)


# ── 모델별 thinking budget 레지스트리 (카탈로그 순회 자동 생성) ──────────────
# 알려진 모델의 표시 기본값 = litellm_config.yaml 의 alias 별 고정 thinking budget.
# (feature-0007 litellm_config: claude-sonnet-4=16000, claude-haiku-4=5000.)
# 카탈로그에 새 thinking 지원 모델이 추가되면 아래 맵에 없더라도 자동으로 1 항목이 생긴다
# (표시 기본값 = _MODEL_BUDGET_FALLBACK_DEFAULT, override 를 저장하기 전까지는 주입하지 않아
#  모델 config 기본값을 유지 — B1 무회귀).
_MODEL_BUDGET_DEFAULTS: dict[str, int] = {
    "claude-sonnet-4": 16000,
    "claude-haiku-4": 5000,
}
_MODEL_BUDGET_FALLBACK_DEFAULT = 8000
# Anthropic 제약(budget_tokens ≥ 1024) 하한. 상한(maximum)은 reasoning-budget-per-model 이후
# 모델별 native max output − 1024 로 산출한다(_thinking_budget_max). backend agent 경로가 주입
# 직전 min(budget, max_tokens − 1024) 로 clamp 하므로 budget < max_tokens 는 항상 보장된다.
_MODEL_BUDGET_MIN = 1024

# ── 대화(agent) 모델별 총 출력 레지스트리 (reasoning-budget-per-model) ────────
# 대화 답변 경로(task='agent')의 max_tokens 를 모델별로 관리. default = model_catalog 의 보수적
# 모델별 default, maximum = 모델 native max output(Sonnet 128K / Haiku 64K). 이 총 출력 안에서
# thinking(추론)과 content(본문)가 나뉜다 — thinking 은 아래 예산, content 는 총 − thinking(파생).
GROUP_AGENT_MAX_OUTPUT = "agent_max_output"
AGENT_MAX_OUTPUT_KEY_PREFIX = "agent_max_output:"
_AGENT_MAX_OUTPUT_MIN = 4096
# 대화 총 출력의 모델별 보수적 default(기존 20000 상회 + 상향 여지 + 비-streaming 타임아웃 안전).
# maximum(ceiling)은 model_catalog.model_native_max_output(모델 native). 미등록 모델은 task cap fallback.
# (plan/insight 등 "agent" task 공유 소비자와 분리 — model_catalog.max_tokens_for_model 은 무변경.)
_AGENT_MAX_OUTPUT_DEFAULT: dict[str, int] = {
    "claude-sonnet-4": 40000,
    "claude-haiku-4": 24000,
}


def _agent_max_output_default(model: str) -> int:
    return _AGENT_MAX_OUTPUT_DEFAULT.get(
        model, int(model_catalog.max_tokens_for_model(model, "agent") or 20000)
    )

# ── 추론 강도별 예산 레지스트리 (reasoning-budgets → 모델별 분리) ─────────────
# 대화 화면 '추론 강도' 선택(낮음/일반/높음/매우 높음) 중 명시 레벨(low/high/max)의 요청 단위
# thinking budget 을 관리자가 **모델별로** 조정. key = reasoning_budget:{model}:{level}.
# 표시 기본값 = model_catalog.thinking_budget_for_level(level)(모델 무관 base: low2000/high10000/max16000).
# '일반(normal)'은 의도적 no-override(B1)라 설정 대상이 아니다(thinking_budget_for_level 이 None → 제외).
# 상한(maximum)은 모델별 native max output − 1024.
GROUP_REASONING_BUDGET = "reasoning_budget"
REASONING_BUDGET_KEY_PREFIX = "reasoning_budget:"
_REASONING_BUDGET_MIN = 1024


def _thinking_budget_max(model: str) -> int:
    """모델별 thinking budget 상한 = native max output − 1024(content 최소 1024 확보)."""
    return max(_REASONING_BUDGET_MIN, int(model_catalog.model_native_max_output(model)) - 1024)


def _agent_max_output_key(model: str) -> str:
    return f"{AGENT_MAX_OUTPUT_KEY_PREFIX}{model}"


def _reasoning_budget_key(model: str, level: str) -> str:
    return f"{REASONING_BUDGET_KEY_PREFIX}{model}:{level}"


def _thinking_models() -> tuple[str, ...]:
    """카탈로그에서 extended thinking 지원 모델 value 목록(중복 제거, 표시 순서 보존)."""
    seen: list[str] = []
    for item in model_catalog.API_MODEL_OPTIONS:
        value = str(item.get("value") or "").strip()
        if value and model_catalog.model_supports_thinking(value) and value not in seen:
            seen.append(value)
    return tuple(seen)


def _agent_max_output_specs() -> tuple[dict[str, Any], ...]:
    """thinking 지원 모델마다 대화 총 출력(max_tokens) 스펙 1개. maximum = 모델 native."""
    specs: list[dict[str, Any]] = []
    for model in _thinking_models():
        meta = model_catalog.get_api_model_meta(model) or {}
        default = _agent_max_output_default(model)
        native = int(model_catalog.model_native_max_output(model))
        specs.append(
            {
                "key": _agent_max_output_key(model),
                "group": GROUP_AGENT_MAX_OUTPUT,
                "category": "모델 총 출력",
                "model": model,
                "label": str(meta.get("label") or model),
                "description": (
                    "추론 라운드(단계)당 출력 상한(max_tokens) — 추론(thinking)+본문의 합. "
                    "어시스턴트는 한 요청을 다회차로 처리하므로 실제 총량 ≈ 이 값 × 회차. native 근처로 "
                    "크게 잡으면 라운드마다 느려져 '에이전트/쿼리 실행 타임아웃'을 넘거나 오히려 회차 수가 "
                    "줄 수 있으니 보수적으로 시작하고 필요 시 타임아웃도 함께 올리세요."
                ),
                "unit": "tokens",
                "default": default,
                "minimum": _AGENT_MAX_OUTPUT_MIN,
                "maximum": native,
                "apply_mode": "live",
                "default_known": True,
            }
        )
    return tuple(specs)


def _reasoning_budget_specs() -> tuple[dict[str, Any], ...]:
    """(모델 × 명시 레벨) 마다 예산 스펙 1개. 카탈로그 순회로 자동 확장(normal 제외)."""
    specs: list[dict[str, Any]] = []
    labels = {
        str(o.get("value")): str(o.get("label") or o.get("value"))
        for o in model_catalog.REASONING_LEVEL_OPTIONS
    }
    for model in _thinking_models():
        meta = model_catalog.get_api_model_meta(model) or {}
        model_label = str(meta.get("label") or model)
        budget_max = _thinking_budget_max(model)
        for level in model_catalog.REASONING_LEVELS:
            default = model_catalog.thinking_budget_for_level(level)
            if default is None:
                continue  # normal/미상 = no-override(B1) → 설정 대상 아님
            label = labels.get(level, level)
            specs.append(
                {
                    "key": _reasoning_budget_key(model, level),
                    "group": GROUP_REASONING_BUDGET,
                    "category": "추론 강도별 예산",
                    "model": model,
                    "level": level,
                    "label": f"{model_label} · {label}",
                    "description": f"대화에서 추론 강도 '{label}' 선택 시 이 모델에 적용되는 요청 단위 thinking budget.",
                    "unit": "tokens",
                    "default": int(default),
                    "minimum": _REASONING_BUDGET_MIN,
                    "maximum": budget_max,
                    "apply_mode": "live",
                    "default_known": True,
                }
            )
    return tuple(specs)


def _model_budget_key(model: str) -> str:
    return f"{MODEL_BUDGET_KEY_PREFIX}{model}"


def _model_budget_specs() -> tuple[dict[str, Any], ...]:
    specs: list[dict[str, Any]] = []
    for model in _thinking_models():
        meta = model_catalog.get_api_model_meta(model) or {}
        default = _MODEL_BUDGET_DEFAULTS.get(model, _MODEL_BUDGET_FALLBACK_DEFAULT)
        known = model in _MODEL_BUDGET_DEFAULTS
        specs.append(
            {
                "key": _model_budget_key(model),
                "group": GROUP_MODEL_BUDGET,
                "category": "모델 추론 예산",
                "model": model,
                "label": str(meta.get("label") or model),
                "description": str(meta.get("description") or ""),
                "unit": "tokens",
                "default": int(default),
                "minimum": _MODEL_BUDGET_MIN,
                "maximum": _thinking_budget_max(model),
                "apply_mode": "live",
                # 표시 기본값이 litellm alias 실측값에 근거하는지 여부(false 면 UI 가 "모델 기본값" 힌트).
                "default_known": known,
            }
        )
    return tuple(specs)


def _timeout_specs() -> tuple[dict[str, Any], ...]:
    return tuple(dict(spec, group=GROUP_TIMEOUT) for spec in _TIMEOUT_SPECS)


# ── 자가 적대 리뷰(red-team) 레지스트리 (feature-0021) ─────────────────────
# assistant 답변 전달 전 fresh-context 적대 리뷰 오케스트레이션의 게이트/예산.
# 전부 live — 답변 단위로 읽으므로 재시작 없이 즉시 반영. 0/1 스위치도 int 스펙으로 표현.
GROUP_REDTEAM = "redteam"

_REDTEAM_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "REDTEAM_ENABLED",
        "category": "자가 리뷰",
        "label": "답변 자가 적대 리뷰 사용",
        "description": "답변 전달 전 별도 저비용 LLM 이 grounding·SQL·권한·완전성·정직성 5축으로 적대 리뷰를 수행합니다 (1=사용, 0=중지). 리뷰 실패는 답변을 막지 않습니다(fail-open).",
        "unit": "0/1",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_MIN_LEVEL",
        "category": "자가 리뷰",
        "label": "리뷰 최소 추론 강도",
        "description": "이 강도 이상 대화에서만 리뷰 수행 (0=낮음, 1=일반, 2=높음, 3=매우높음). 기본 1 — 낮음 강도는 비용 절약을 위해 건너뜁니다.",
        "unit": "level",
        "default": 1,
        "minimum": 0,
        "maximum": 3,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_MAX_REVISIONS",
        "category": "자가 리뷰",
        "label": "BLOCK 결함 수정 상한",
        "description": "리뷰가 BLOCK 결함을 찾았을 때 답변을 수정하는 최대 횟수. 0 이면 기록만 하고 수정하지 않습니다.",
        "unit": "회",
        "default": 1,
        "minimum": 0,
        "maximum": 2,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_TIMEOUT_SEC",
        "category": "자가 리뷰",
        "label": "리뷰어 호출 타임아웃",
        "description": "리뷰어 LLM 1회 호출 상한. 초과 시 원 답변을 그대로 전달합니다(fail-open).",
        "unit": "초",
        "default": 25,
        "minimum": 5,
        "maximum": 300,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_REDERIVE_ENABLED",
        "category": "자가 리뷰",
        "label": "BLOCK 재도출(도구 재추론) 사용",
        "description": "재도출이 필요한 축(sql 등)의 BLOCK 결함을 만나면, 문장만 다듬는 대신 도구(execute_sql 등)를 다시 호출해 올바른 근거를 수집한 뒤 답을 재도출합니다 (1=사용, 0=중지=기존 텍스트 재작성만). 재도출은 메인 모델+도구 루프라 비용/지연이 큽니다 — 급증 시 0 으로 즉시 차단하세요.",
        "unit": "0/1",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_REDERIVE_MAX_TOOL_ROUNDS",
        "category": "자가 리뷰",
        "label": "재도출 도구 라운드 상한",
        "description": "재도출 1회에서 허용하는 최대 도구 호출 라운드(LLM↔도구 사이클). 초과하면 그 시점 정보로 최종 답변을 확정합니다. 비용/지연 상한.",
        "unit": "회",
        "default": 3,
        "minimum": 1,
        "maximum": 6,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_REDERIVE_COMPLETENESS_MIN_LEVEL",
        "category": "자가 리뷰",
        "label": "completeness 재도출 최소 강도",
        "description": "completeness(완전성) 축 BLOCK 을 도구 재추론으로 승격할 최소 추론 강도 (0=낮음, 1=일반, 2=높음, 3=매우높음). 기본 3 — completeness 는 가장 모호한 축이라 비용/드리프트 위험이 커, 사용자가 최대 사양을 명시한 '매우 높음'에서만 재도출합니다 (4 로 두면 사실상 비활성). sql 축은 이 설정과 무관하게 항상 재도출 대상입니다.",
        "unit": "level",
        "default": 3,
        "minimum": 0,
        "maximum": 4,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_NOTES_ENABLED",
        "category": "자가 리뷰 메모리",
        "label": "세션/제품 메모리 노트 사용",
        "description": "답변 후 자가 리뷰 결과·핵심 사실을 세션(대화)/제품 노트 파일로 축적하고 다음 답변 프롬프트에 참조합니다 (1=사용, 0=중지).",
        "unit": "0/1",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_NOTES_SESSION_TTL_DAYS",
        "category": "자가 리뷰 메모리",
        "label": "세션 노트 보존 기간",
        "description": "세션(대화) 노트 임시 파일의 TTL. 마지막 갱신 후 이 기간이 지나면 주기 정리에서 삭제됩니다.",
        "unit": "일",
        "default": 7,
        "minimum": 1,
        "maximum": 90,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_NOTES_PRODUCT_TTL_DAYS",
        "category": "자가 리뷰 메모리",
        "label": "제품 노트 보존 기간",
        "description": "제품 노트 임시 파일의 TTL. 마지막 갱신 후 이 기간이 지나면 주기 정리에서 삭제됩니다.",
        "unit": "일",
        "default": 30,
        "minimum": 1,
        "maximum": 365,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_NOTES_INJECT_MAX_CHARS",
        "category": "자가 리뷰 메모리",
        "label": "노트 프롬프트 주입 상한",
        "description": "세션+제품 노트를 답변 프롬프트에 주입할 때의 합산 문자 상한 (토큰 절약 캡). 0 이면 주입하지 않습니다.",
        "unit": "자",
        "default": 4000,
        "minimum": 0,
        "maximum": 20000,
        "apply_mode": "live",
    },
)


def _redteam_specs() -> tuple[dict[str, Any], ...]:
    return tuple(dict(spec, group=GROUP_REDTEAM) for spec in _REDTEAM_SPECS)


GROUP_SCRATCH = "scratch"

# feature-0022: agent PG scratch workspace. assistant 가 PG 안 자기 전용 낙서장 DB 에서
# 자율적으로 테이블을 만들고, 외부 데이터소스 데이터를 반입해 JOIN 하고, TTL 주기로 비운다.
_SCRATCH_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "AGENT_SCRATCH_ENABLED",
        "category": "작업공간(스크래치)",
        "label": "PG 스크래치 작업공간 사용",
        "description": "assistant 가 PG 전용 낙서장 DB(agent_scratch)에서 대화별 테이블을 자율적으로 만들고, 외부 데이터소스 데이터를 반입해 cross-source JOIN 을 수행하도록 허용합니다 (1=사용, 0=중지). 사용 전 bin/scratch-pg-bootstrap.sh 로 DB/role 이 준비돼야 합니다. 기본 0(안전).",
        "unit": "0/1",
        "default": 0,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_SCRATCH_TTL_HOURS",
        "category": "작업공간(스크래치)",
        "label": "임시데이터 삭제 주기",
        "description": "대화별 스크래치 스키마의 TTL. 마지막 사용 후 이 시간이 지나면 주기 정리(ask-worker reaper)에서 DROP 됩니다. 반입 데이터는 임시이므로 짧게 두는 것을 권장합니다.",
        "unit": "시간",
        "default": 24,
        "minimum": 1,
        "maximum": 720,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_SCRATCH_MAX_IMPORT_ROWS",
        "category": "작업공간(스크래치)",
        "label": "1회 반입 최대 행수",
        "description": "scratch_import 로 외부 데이터소스에서 한 번에 반입할 수 있는 최대 행수. 초과분은 잘리고 그 사실이 assistant 에 통지됩니다(디스크 폭주 방지).",
        "unit": "행",
        "default": 100000,
        "minimum": 100,
        "maximum": 5000000,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_SCRATCH_MAX_TABLES_PER_CONV",
        "category": "작업공간(스크래치)",
        "label": "대화당 최대 테이블 수",
        "description": "한 대화의 스크래치 스키마가 보유할 수 있는 최대 테이블 수. 초과 시 scratch_reset 로 정리해야 합니다.",
        "unit": "개",
        "default": 50,
        "minimum": 1,
        "maximum": 500,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_SCRATCH_MAX_SCHEMAS",
        "category": "작업공간(스크래치)",
        "label": "전역 최대 대화 스키마 수",
        "description": "agent_scratch DB 전체가 동시에 보유할 수 있는 대화 스키마 수 상한(디스크 폭주 방지). 도달 시 만료분을 먼저 정리하며, 그래도 초과면 새 작업공간 생성이 잠시 거부됩니다.",
        "unit": "개",
        "default": 500,
        "minimum": 10,
        "maximum": 10000,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_SCRATCH_STMT_TIMEOUT_MS",
        "category": "작업공간(스크래치)",
        "label": "scratch_sql 문당 타임아웃",
        "description": "scratch_sql 한 문(SELECT/JOIN/DDL)의 실행 상한(밀리초). 초과 시 해당 문이 취소됩니다(폭주 backstop).",
        "unit": "ms",
        "default": 30000,
        "minimum": 1000,
        "maximum": 600000,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_SCRATCH_QUERY_PREVIEW_ROWS",
        "category": "작업공간(스크래치)",
        "label": "scratch_sql 미리보기 행수",
        "description": "scratch_sql 이 SELECT 결과를 assistant 에 돌려줄 때의 미리보기 행수 상한(토큰 절약). 초과 시 잘린 사실이 통지됩니다.",
        "unit": "행",
        "default": 200,
        "minimum": 10,
        "maximum": 2000,
        "apply_mode": "live",
    },
)


def _scratch_specs() -> tuple[dict[str, Any], ...]:
    return tuple(dict(spec, group=GROUP_SCRATCH) for spec in _SCRATCH_SPECS)


# 스펙은 프로세스 수명 내 정적이다(타임아웃=리터럴, 모델 예산=import-time 고정 카탈로그 순회).
# get_int·model_thinking_budget_override 가 매 MCP 요청·매 timeout 해석마다 spec_for 를 호출하므로
# 전체 스펙/인덱스를 1회 계산 후 메모이즈한다(적대 backend MINOR — hot-path 재빌드 제거).
_SPECS_CACHE: tuple[dict[str, Any], ...] | None = None
_SPEC_INDEX_CACHE: dict[str, dict[str, Any]] | None = None


def list_specs() -> tuple[dict[str, Any], ...]:
    """전체 설정 스펙(타임아웃 + 모델 예산). 프로세스 1회 계산 후 메모이즈."""
    global _SPECS_CACHE
    if _SPECS_CACHE is None:
        _SPECS_CACHE = (
            _timeout_specs()
            + _agent_max_output_specs()
            + _model_budget_specs()
            + _reasoning_budget_specs()
            + _redteam_specs()
            + _scratch_specs()
        )
    return _SPECS_CACHE


def _spec_index() -> dict[str, dict[str, Any]]:
    global _SPEC_INDEX_CACHE
    if _SPEC_INDEX_CACHE is None:
        _SPEC_INDEX_CACHE = {str(spec["key"]): spec for spec in list_specs()}
    return _SPEC_INDEX_CACHE


def spec_for(key: str) -> dict[str, Any] | None:
    return _spec_index().get(str(key or "").strip())


# ── 스냅샷 I/O ─────────────────────────────────────────────────────────────
_lock = threading.Lock()
# live 캐시: (load_monotonic, overrides). restart 는 최초 1회 스냅샷을 고정 보관.
_cache: dict[str, Any] = {"loaded_at": 0.0, "overrides": None, "frozen": None}


def snapshot_path() -> str:
    return os.getenv(_SNAPSHOT_ENV, _DEFAULT_SNAPSHOT_PATH)


def _disabled() -> bool:
    return os.getenv(_DISABLED_ENV, "").strip().lower() in ("1", "true", "yes")


def _ttl_sec() -> float:
    raw = os.getenv(_TTL_ENV, "").strip()
    if not raw:
        return _DEFAULT_TTL_SEC
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return _DEFAULT_TTL_SEC


def _read_file_overrides() -> dict[str, Any]:
    """스냅샷 파일을 읽어 {key: raw_value} dict. 부재/파싱실패/kill-switch → {} (fail-open)."""
    if _disabled():
        return {}
    path = snapshot_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    # 스냅샷은 {"overrides": {...}} 또는 평문 {key: val} 둘 다 허용.
    overrides = data.get("overrides") if "overrides" in data else data
    return overrides if isinstance(overrides, dict) else {}


def _live_overrides() -> dict[str, Any]:
    """TTL 캐시된 최신 override(live 소비용)."""
    now = time.monotonic()
    with _lock:
        overrides = _cache.get("overrides")
        loaded_at = float(_cache.get("loaded_at") or 0.0)
        if overrides is None or (now - loaded_at) >= _ttl_sec():
            overrides = _read_file_overrides()
            _cache["overrides"] = overrides
            _cache["loaded_at"] = now
            if _cache.get("frozen") is None:
                _cache["frozen"] = dict(overrides)
        return dict(overrides)


def _frozen_overrides() -> dict[str, Any]:
    """프로세스 최초 로드 스냅샷(restart 소비용 — 수명 내 고정)."""
    with _lock:
        frozen = _cache.get("frozen")
        if frozen is None:
            frozen = _read_file_overrides()
            _cache["frozen"] = frozen
            if _cache.get("overrides") is None:
                _cache["overrides"] = dict(frozen)
                _cache["loaded_at"] = time.monotonic()
        return dict(frozen)


def invalidate_cache() -> None:
    """live 캐시를 즉시 무효화(PUT 직후 endpoint 가 호출 — 동일 프로세스 즉시 반영).

    frozen(restart) 스냅샷은 의도적으로 유지한다(재시작 semantics)."""
    with _lock:
        _cache["overrides"] = None
        _cache["loaded_at"] = 0.0


def read_overrides() -> dict[str, Any]:
    """현재 스냅샷의 raw override dict(진단/직렬화용)."""
    return _live_overrides()


def write_snapshot(overrides: dict[str, Any]) -> None:
    """override dict 를 스냅샷 파일에 원자적으로 기록(temp write + rename).

    관리 콘솔 endpoint 가 DB commit 성공 후 호출한다. 디렉토리 부재/쓰기 실패는 예외를
    올린다(호출측이 로깅) — DB 는 이미 커밋됐고 다음 재기동 reconcile 이 스냅샷을 복구한다.
    """
    path = snapshot_path()
    clean = {str(k): v for k, v in dict(overrides or {}).items()}
    payload = json.dumps({"overrides": clean}, ensure_ascii=False, sort_keys=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    invalidate_cache()


# ── 값 해석 ────────────────────────────────────────────────────────────────
def _coerce_int(raw: Any) -> int | None:
    if isinstance(raw, bool):  # bool 은 int 서브클래스 — 명시적으로 배제.
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and float(raw).is_integer():
        return int(raw)
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _clamp(value: int, spec: dict[str, Any]) -> int:
    lo = int(spec.get("minimum", value))
    hi = int(spec.get("maximum", value))
    return max(lo, min(hi, value))


def _baseline_int(key: str, spec: dict[str, Any] | None) -> int:
    """console override 가 없을 때의 기준값 = 배포 env 변수(있으면) → 스펙 리터럴 default.

    **중요(byte-동치)**: 운영 배포는 `.env` 로 이 값을 설정한다(예: AGENT_TIMEOUT_SEC=300).
    override 미설정 시 env 를 존중해야 기존 동작(config.py 의 `int(os.getenv(key, ...))`)과
    동치가 유지된다. 스펙 리터럴 default(예: 60)만 쓰면 운영 env(300)를 무시하는 회귀가 난다.
    env 값은 operator 의 명시 배포 선택이므로 clamp 하지 않는다(config 의 raw read 와 동치).
    """
    raw = os.getenv(key)
    if raw is not None:
        coerced = _coerce_int(raw)
        if coerced is not None:
            return coerced
    if spec is not None:
        return int(spec.get("default", 0))
    return 0


def _resolve_int(key: str, overrides: dict[str, Any], default: int | None = None) -> int:
    """console override(있으면 clamp) → default(명시 인자) → env → 스펙 리터럴 순으로 정수 반환."""
    spec = spec_for(key)
    if spec is None:
        # 미등록 키: 스냅샷 override 를 신뢰하지 않는다(오염/변조 방어 — startup_int 와 정합).
        # 등록 키만 override·clamp 대상. default 인자만 반영(있으면).
        return int(default) if default is not None else 0
    if key in overrides:
        coerced = _coerce_int(overrides.get(key))
        if coerced is not None:
            return _clamp(coerced, spec)
    if default is not None:
        return int(default)
    return _baseline_int(key, spec)


def get_int(key: str) -> int:
    """live 소비처용 — 최신(TTL) override 를 반영해 정수 반환. override 없으면 스펙 default.

    호출측은 기존 상수 대신 이 함수로 읽는다. override 미설정 시 스펙 default == config.py 의
    env 기본값이므로 byte-동치가 유지된다.
    """
    return _resolve_int(key, _live_overrides())


def startup_int(key: str, env_default: int) -> int:
    """config.py 가 import 시 restart-mode 상수를 결정할 때 호출.

    frozen 스냅샷(프로세스 최초 로드)에서 override 를 읽어 clamp 후 반환. override 없거나
    kill-switch/파일부재면 `env_default`(호출측이 os.getenv 로 계산한 값)를 그대로 반환한다.
    DB 를 만지지 않으므로 import-time 안전. 예외 발생 시에도 env_default 로 폴백한다.
    """
    try:
        spec = spec_for(key)
        if spec is None:
            # 미등록 키는 스냅샷 값을 신뢰하지 않는다(방어 — 오염/변조 스냅샷 차단).
            return int(env_default)
        frozen = _frozen_overrides()
        if key not in frozen:
            return int(env_default)
        coerced = _coerce_int(frozen.get(key))
        if coerced is None:
            return int(env_default)
        return _clamp(coerced, spec)
    except Exception:
        return int(env_default)


def model_thinking_budget_override(model: str | None) -> int | None:
    """해당 모델에 관리자가 설정한 thinking budget override(정수, clamp 됨). 없으면 None.

    None 이면 호출측(_call_llm)은 주입하지 않아 모델 config 기본 thinking 을 유지한다(B1 무회귀).
    """
    name = str(model or "").strip()
    if not name:
        return None
    key = _model_budget_key(name)
    spec = spec_for(key)
    if spec is None:
        return None
    overrides = _live_overrides()
    if key not in overrides:
        return None
    coerced = _coerce_int(overrides.get(key))
    if coerced is None:
        return None
    return _clamp(coerced, spec)


def reasoning_budget_override(model: str | None, level: str | None) -> int | None:
    """(모델, 추론 강도 레벨)에 관리자가 설정한 budget override(정수, clamp). 없으면 None.

    None 이면 호출측(_call_llm)은 model_catalog 기본 budget(thinking_budget_for_level)을 그대로 쓴다.
    'normal' 등 미등록 레벨/모델은 spec 이 없어 항상 None(B1 — 일반은 no-override 유지).
    """
    name_m = str(model or "").strip()
    name_l = str(level or "").strip().lower()
    if not name_m or not name_l:
        return None
    key = _reasoning_budget_key(name_m, name_l)
    spec = spec_for(key)
    if spec is None:
        return None
    overrides = _live_overrides()
    if key not in overrides:
        return None
    coerced = _coerce_int(overrides.get(key))
    if coerced is None:
        return None
    return _clamp(coerced, spec)


def agent_max_output(model: str | None) -> int:
    """대화(agent) 총 출력 상한(max_tokens). override 있으면 clamp 후 반환, 없으면 모델별 default.

    default = _agent_max_output_default(model)(모델별 보수값, plan 등 task cap 과 분리). 등록 spec 이
    있으면 관리자 override 를 [min, native] 로 clamp 한다. (순환 import 방지 — 조회는 여기 호출측 계층.)
    """
    name = str(model or "").strip()
    if not name:
        return int(model_catalog.max_tokens_for_model(name, "agent") or 20000)
    default = _agent_max_output_default(name)
    key = _agent_max_output_key(name)
    if spec_for(key) is None:
        return default
    # override 있으면 [min, native] clamp, 없으면 default(모델별 보수값).
    return _resolve_int(key, _live_overrides(), default=default)


def effective_value(key: str) -> int:
    """현재 유효값(override 있으면 그 값, 없으면 default) — API 표시용."""
    return _resolve_int(key, _live_overrides())


# ── 검증 (endpoint PUT 용) ─────────────────────────────────────────────────
def validate_value(key: str, raw: Any) -> tuple[bool, int | None, str | None]:
    """(ok, int_value, error_msg). 등록 키 + 정수 + [min,max] 범위 검사. 성공 시 정규화된 int 반환."""
    spec = spec_for(key)
    if spec is None:
        return (False, None, "등록되지 않은 설정 키입니다.")
    coerced = _coerce_int(raw)
    if coerced is None:
        return (False, None, "정수 값이 필요합니다.")
    lo = int(spec.get("minimum"))
    hi = int(spec.get("maximum"))
    if coerced < lo or coerced > hi:
        return (False, None, f"허용 범위({lo} ~ {hi})를 벗어났습니다.")
    return (True, coerced, None)


# ── 직렬화 (endpoint GET registry 용) ──────────────────────────────────────
def serialize_registry(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """레지스트리 + 현재 유효값 + override 여부를 그룹별로 직렬화한다.

    overrides 를 넘기지 않으면 스냅샷에서 읽는다(단, 관리 콘솔은 DB 값을 넘겨 권위 있는 표시를
    보장하는 것을 권장).
    """
    ov = _live_overrides() if overrides is None else {str(k): v for k, v in dict(overrides).items()}
    timeouts: list[dict[str, Any]] = []
    agent_outputs: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    reasoning: list[dict[str, Any]] = []
    redteam: list[dict[str, Any]] = []
    for spec in list_specs():
        key = str(spec["key"])
        has_override = key in ov
        effective = _resolve_int(key, ov)
        # default = console override 없을 때의 기준값(env 배포값 반영) — '초기화' 가 되돌리는 값.
        baseline = _baseline_int(key, spec)
        row = {
            "key": key,
            "group": spec.get("group"),
            "category": spec.get("category"),
            "label": spec.get("label"),
            "description": spec.get("description"),
            "unit": spec.get("unit"),
            "default": int(baseline),
            "code_default": int(spec.get("default")),
            "minimum": int(spec.get("minimum")),
            "maximum": int(spec.get("maximum")),
            "apply_mode": spec.get("apply_mode"),
            "effective": int(effective),
            "has_override": has_override,
            "override_value": _coerce_int(ov.get(key)) if has_override else None,
        }
        if spec.get("group") == GROUP_AGENT_MAX_OUTPUT:
            row["model"] = spec.get("model")
            row["default_known"] = bool(spec.get("default_known"))
            agent_outputs.append(row)
        elif spec.get("group") == GROUP_MODEL_BUDGET:
            row["model"] = spec.get("model")
            row["default_known"] = bool(spec.get("default_known"))
            models.append(row)
        elif spec.get("group") == GROUP_REASONING_BUDGET:
            row["model"] = spec.get("model")
            row["level"] = spec.get("level")
            row["default_known"] = bool(spec.get("default_known"))
            reasoning.append(row)
        elif spec.get("group") == GROUP_REDTEAM:
            redteam.append(row)
        else:
            timeouts.append(row)
    return {
        "timeouts": timeouts,
        "agent_max_outputs": agent_outputs,
        "model_thinking_budgets": models,
        "reasoning_budgets": reasoning,
        "redteam": redteam,
        "meta": {
            "snapshot_path": snapshot_path(),
            "disabled": _disabled(),
            "cache_ttl_sec": _ttl_sec(),
        },
    }
