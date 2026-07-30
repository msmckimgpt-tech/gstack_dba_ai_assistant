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
    "GROUP_FOLDER",
    "GROUP_PERF",
    "folder_max_depth",
    "node_analysis_concurrency",
    "cluster_label_concurrency",
    "ask_worker_concurrency",
    "ask_worker_idle_poll_sec",
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
    # feature-0030: 위 실행 상한에 근접했을 때 "이번 요청만 끝까지" 를 사용자에게 묻는 장치.
    {
        "key": "AGENT_TIMEOUT_EXTENSION_ENABLED",
        "category": "쿼리·에이전트 실행",
        "label": "타임아웃 임박 시 사용자 확인 후 연장",
        "description": "요청 처리가 실행 상한에 근접하면 작업 화면에 '계속 추론할까요?'를 띄우고, 사용자가 승인한 그 요청에 한해 상한을 넘겨 끝까지 추론합니다 (1=사용, 0=중지). 승인이 없으면 종전처럼 타임아웃 처리됩니다.",
        "unit": "0/1",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_TIMEOUT_EXTENSION_PROMPT_PCT",
        "category": "쿼리·에이전트 실행",
        "label": "연장 확인을 띄우는 시점",
        "description": "요청의 실행 예산을 몇 % 소진했을 때 연장 확인을 띄울지. 기본 80 — 남은 20% 가 사용자가 알림을 보고 승인을 누를 여유입니다. 너무 높이면 승인 전에 요청이 먼저 종료됩니다.",
        "unit": "%",
        "default": 80,
        "minimum": 10,
        "maximum": 95,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_TIMEOUT_EXTENSION_MAX_SEC",
        "category": "쿼리·에이전트 실행",
        "label": "연장 승인 시 추가 허용 시간",
        "description": "사용자가 연장을 승인했을 때 추가로 허용할 시간 상한(초). 기본 0 = 무제한(사용자 정책 — 답변 완주 우선). 도구 호출 횟수 상한과 '중단'·'즉시 답변' 버튼은 연장 중에도 그대로 작동합니다.",
        "unit": "초",
        "default": 0,
        "minimum": 0,
        "maximum": 86400,
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
    # opus5-model(2026-07-27): Opus 5 도 native 128K 이지만 라운드당 출력 default 는 sonnet 과 동일한
    # 40000 으로 둔다 — native 근처 값은 라운드마다 느려져 '에이전트/쿼리 실행 타임아웃'을 넘기고
    # (스펙 description 참조) Opus 단가($5/$25)에서 비용도 함께 뛴다. 필요 시 관리 콘솔
    # '설정 > 모델 총 출력' 에서 모델별로 상향(상한 = native 128000).
    "claude-opus-5": 40000,
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


def _budget_thinking_models() -> tuple[str, ...]:
    """thinking budget_tokens override 가 **실제 의미가 있는** 모델만(budget 스타일 한정).

    sonnet5-upgrade(2026-07-24) 이후 adaptive 계열(Sonnet 5)은 budget_tokens 대신
    output_config.effort 로 추론 강도를 제어하며(agent_core._call_llm adaptive 분기는
    reasoning_budget_override / model_thinking_budget_override 를 **조회조차 안 함**),
    관리 콘솔의 '추론 강도별 예산'·'모델 기본 thinking budget' 슬라이더는 adaptive 모델에서
    저장해도 무효과인 죽은 컨트롤이 된다. 이 함수는 그 두 그룹의 스펙 생성 대상을 **budget 스타일로
    한정**해, 죽은 슬라이더가 registry→API→admin UI 로 새어나가지 않게 한다(guide-note 전환).

    ⚠️ 필터는 `== "budget"`(agent_core `_call_llm` 의 budget 분기 조건과 **동형**)로 둔다. `!= "adaptive"`
    로 두면 style=None 인 미상/미래 claude(예: claude-opus-4-8 — model_catalog 는 미상 claude 를 안전하게
    None 으로 분류; budget_tokens 주입 시 400)가 budget 스펙에 포함돼, `_call_llm` 이 None 스타일엔 아무
    thinking override 도 주입하지 않으므로 **또다시 죽은 슬라이더**가 생긴다(적대리뷰 Finding D). budget 계열만
    통과시키면 미상 claude 는 ②③ 슬라이더도 guide-note 도 없이 ①(총 출력, live)만 노출 — 죽은 컨트롤 0.
    총 출력(agent_max_output)은 adaptive/None 도 live 로 읽으므로 _thinking_models() 전체를 유지한다.
    """
    return tuple(
        m for m in _thinking_models()
        if model_catalog.model_thinking_style(m) == "budget"
    )


def _adaptive_thinking_models() -> tuple[str, ...]:
    """adaptive thinking 계열(effort 로 제어, budget 미적용) — admin UI 가 guide-note 를 띄울 대상."""
    return tuple(m for m in _thinking_models() if model_catalog.model_thinking_style(m) == "adaptive")


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
    for model in _budget_thinking_models():  # adaptive(Sonnet 5) 제외 — effort 로 제어, budget 죽은 컨트롤
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
    for model in _budget_thinking_models():  # adaptive(Sonnet 5) 제외 — budget 죽은 컨트롤(effort 로 제어)
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
        "description": "리뷰가 BLOCK 결함을 찾았을 때 답변을 수정하는 최대 횟수. 0 이면 기록만 하고 수정하지 않습니다(반복 수정 설정보다 우선하는 차단 스위치). 아래 '결함 해소까지 반복 수정'이 켜져 있고 이 값이 1 이상이면, 이 상한 대신 결함이 사라질 때까지 반복합니다.",
        "unit": "회",
        "default": 1,
        "minimum": 0,
        "maximum": 10,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_REVISE_UNTIL_RESOLVED",
        "category": "자가 리뷰",
        "label": "결함 해소까지 반복 수정",
        "description": "재검증에서 BLOCK 결함이 또 검출되면 위 '수정 상한'과 무관하게 결함이 사라질 때까지 수정→재검증을 반복합니다 (1=사용, 0=중지=상한 적용). 신뢰성 우선 정책 — 응답이 길어질 수 있으며, 사용자는 작업 화면의 '즉시 답변'으로 언제든 그 시점 답변을 받을 수 있습니다. 비용/지연 급증 시 0 으로 즉시 차단하세요.",
        "unit": "0/1",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_WALL_BUDGET_SEC",
        "category": "자가 리뷰",
        "label": "반복 수정 전체 시간 예산",
        "description": "'결함 해소까지 반복 수정'이 한 답변에서 쓸 수 있는 총 시간 상한(초). 기본 0 = 무제한(사용자 정책 — 신뢰성 우선, 대신 사용자가 '즉시 답변'으로 중단). 반복이 길어지면 답변 처리 슬롯을 오래 점유해 다른 사용자의 대기가 길어질 수 있으므로, 대기열 지연이 관측되면 이 값을 설정해 상한을 두세요.",
        "unit": "초",
        "default": 0,
        "minimum": 0,
        "maximum": 3600,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_VERIFY_MIN_LEVEL",
        "category": "자가 리뷰",
        "label": "수정본 재검증 최소 추론 강도",
        "description": "수정된 답변을 리뷰어가 다시 검증할 최소 추론 강도 (0=낮음, 1=일반, 2=높음, 3=매우높음, 4=사실상 비활성). 기본 0 — 모든 강도에서 수정본을 재검증합니다. 재검증이 없으면 수정이 결함을 실제로 고쳤는지 확인되지 않은 채 답변이 전달됩니다.",
        "unit": "level",
        "default": 0,
        "minimum": 0,
        "maximum": 4,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_HISTORY_CONV_LIMIT",
        "category": "자가 리뷰",
        "label": "리뷰어 대화 기억 건수",
        "description": "리뷰어가 같은 대화의 직전 답변에서 자기가 내렸던 판정을 몇 건까지 이어받을지 (0=기억 안 함). 리뷰어는 이 기억으로 '이 대화에서 반복되는 문제'를 인지해 맥락에 맞게 판단하고, 이미 해소된 지적을 다시 올리지 않습니다. 같은 답변 안의 수정 라운드 이력은 이 값과 무관하게 항상 이어받습니다. 다른 대화의 내용은 절대 포함되지 않습니다.",
        "unit": "건",
        "default": 3,
        "minimum": 0,
        "maximum": 10,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_UNRESOLVED_NOTICE",
        "category": "자가 리뷰",
        "label": "미해소 결함 답변 고지",
        "description": "반복 수정에도 결함이 남은 채 답변이 전달될 때(즉시 답변·취소·수정 실패 등), 답변 말미에 내부 검증에서 결함이 남았다는 짧은 고지를 덧붙입니다 (1=사용, 0=중지). 결함 잔존 답변이 조용히 전달되는 것을 막는 정직성 장치입니다.",
        "unit": "0/1",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_ANSWER_REALIGN",
        "category": "자가 리뷰",
        "label": "원 요청 기준 답변 정합 교정",
        "description": "내부 검증으로 수정된 답변의 서두가 '사용자 질문'이 아니라 '내부 지적'에 응답하는 투로 남으면, 사실·수치·근거·고지를 그대로 둔 채 원 요청에 답하는 서술로 1회만 다시 쓰게 합니다 (1=사용, 0=중지). 사용자는 내부 검증을 볼 수 없으므로 그런 답변은 자기 질문과 어긋나 보입니다. 정상 답변에는 추가 호출이 발생하지 않으며(문제가 탐지될 때만 1회), 다시 쓴 결과가 짧아지거나 여전히 어긋나면 원문을 유지합니다.",
        "unit": "0/1",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_TIMEOUT_SEC",
        "category": "자가 리뷰",
        "label": "리뷰어 호출 타임아웃",
        "description": "리뷰어 LLM 1회 호출 상한. 초과 시 원 답변을 그대로 전달합니다(fail-open). 리뷰가 자주 '리뷰 실패'(타임아웃)로 잘리면 이 값을 올리세요 — 단 리뷰는 답변 전달 직전 단계라 값만큼 사용자 대기가 늘 수 있습니다.",
        "unit": "초",
        "default": 25,
        "minimum": 5,
        "maximum": 300,
        "apply_mode": "live",
    },
    {
        "key": "REDTEAM_MAX_TOKENS",
        "category": "자가 리뷰",
        "label": "리뷰어 토큰 할당량",
        "description": "리뷰어 LLM 1회 호출의 최대 출력 토큰(모델 thinking + 판정 JSON 포함). 리뷰어 모델은 답변에 쓰인 모델에 정합합니다(haiku 답변→haiku 리뷰, sonnet 답변→sonnet 리뷰; AGENT_REDTEAM_MODEL 로 고정 가능). haiku 리뷰어는 고정 thinking 예산(현 5000)을 쓰므로 그보다 커야 하는 하한(6000)을 둡니다. sonnet 리뷰어는 adaptive thinking(effort=low 로 낮춰 truncation·지연 완화)입니다. 값을 올려도 호출 지연은 줄지 않습니다(지연은 위 타임아웃으로 조절). 0/미설정이면 기존 기본 상한(8192)을 사용합니다.",
        "unit": "토큰",
        "default": 8192,
        "minimum": 6000,
        "maximum": 32000,
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


# ── 대화 폴더(프로젝트) (feature-0024) ────────────────────────────────────
GROUP_FOLDER = "folder"

_FOLDER_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "folder_max_depth",
        "category": "대화 폴더",
        "label": "폴더 최대 중첩 깊이",
        "description": "대화 폴더를 몇 단계까지 중첩할 수 있는지의 상한(1=중첩 없음). 이 값을 낮춰도 이미 더 깊어진 기존 폴더는 그대로 보존되며, 앞으로 그보다 더 깊게 만들거나 옮기는 것만 막힙니다(같거나 얕은 이동은 항상 허용).",
        "unit": "단계",
        "default": 4,
        "minimum": 1,
        "maximum": 20,
        "apply_mode": "live",
    },
)


def _folder_specs() -> tuple[dict[str, Any], ...]:
    return tuple(dict(spec, group=GROUP_FOLDER) for spec in _FOLDER_SPECS)


def folder_max_depth() -> int:
    """대화 폴더 최대 중첩 깊이(런타임 override 반영, 기본 4). create/move 에서만 강제(grandfathering)."""
    return get_int("folder_max_depth")


# ── 워커 성능·병렬 처리 (feature-0025) ─────────────────────────────────────
# 백그라운드 워커(insight-worker 의 그래프 노드 분석·cluster_label, ask-worker 의 사용자 답변)의
# 처리 병렬도·페이싱·배치를 관리 콘솔에서 조절한다. 조사 결과 세 워크로드 모두 실효 병렬도 = 1
# (단일 컨테이너·직렬 루프)이라, 아래 CONCURRENCY 계열은 **신규** 병렬도 knob(기본 1 = 현행 byte-동치,
# opt-in)이고 나머지는 기존 페이싱/배치 상수를 노출한다.
#
# ⚠ 자원 한계(공격도 상향 시 병목 순서 — 각 설명에도 명시):
#   ① pgbouncer 풀(compose DEFAULT_POOL_SIZE) — 2026-07-14 §82 사건의 근본 자원. 병렬도×잡별
#      PG 커넥션이 이 풀을 잠식하면 전역 워커 장애. 상한(maximum)을 풀 여유 이하로 보수적 설정.
#   ② Bedrock gateway LLM RPM/TPM — 능동 rate-limit 부재. 동시 LLM 호출이 곧 429 노출.
#   ③ 소스 DB 커넥션 / 컨테이너 메모리(mem_limit).
# 기본값은 shared/config.py 의 env 기본값과 반드시 일치(byte-동치). 값 변경 시 양쪽 함께 수정.
GROUP_PERF = "performance"

_PERF_SPECS: tuple[dict[str, Any], ...] = (
    # ── 그래프 노드 분석 (insight-worker process_pending) ──
    {
        "key": "AGENT_NODE_ANALYSIS_CONCURRENCY",
        "category": "그래프 노드 분석",
        "label": "노드 분석 동시 처리 수",
        "description": "insight-worker 가 한 tick 에서 claim 한 노드들을 동시에 분석하는 개수. 1 이면 현행처럼 노드마다 순차 LLM 호출, 2 이상이면 그만큼 병렬로 분석해 '그래프 노드 분석' 진행이 빨라집니다. 각 병렬 작업이 PG 커넥션 1개를 점유하므로, 값이 클수록 pgbouncer 풀·Bedrock LLM 한도를 더 소모합니다(과도하면 전역 지연). 보수적으로 시작해 관측하며 올리세요.",
        "unit": "개",
        "default": 1,
        "minimum": 1,
        "maximum": 8,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_NODE_ANALYSIS_BATCH_PER_TICK",
        "category": "그래프 노드 분석",
        "label": "tick 당 노드 처리량",
        "description": "insight-worker 가 한 tick 에서 한 번에 claim(집어오는) 하는 노드 잡 수. 높이면 tick 당 더 많은 노드를 처리해 대기열이 빨리 줄지만, 동시 처리 수와 곱해져 LLM/DB 부하가 커집니다.",
        "unit": "개",
        "default": 10,
        "minimum": 1,
        "maximum": 64,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_INSIGHT_WORKER_TICK_SEC",
        "category": "그래프 노드 분석",
        "label": "insight-worker tick 주기",
        "description": "insight-worker 메인 사이클(스캔·노드 분석 배치 처리) 사이의 대기 시간. 낮추면 더 자주 처리해 공격적이지만, 소스 DB·LLM 재접속 빈도가 함께 늘어납니다. (배포 env 는 60초로 설정돼 있습니다.)",
        "unit": "초",
        "default": 8,
        "minimum": 5,
        "maximum": 3600,
        "apply_mode": "live",
    },
    # ── 구조 변동 자동 재분석 (change-reanalysis) ──
    #   사람 confirm 게이트가 없는 자동 LLM 지출 경로라 **라이브 kill switch 가 필수**다
    #   (적대 리뷰 C1/C2: env-only 면 폭주 시 재배포해야 멈춘다). 상한 0 = 자동 트리거 완전 비활성.
    {
        "key": "AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP",
        "category": "그래프 노드 분석",
        "label": "구조 변동 자동 재분석 1회 시드 상한",
        "description": "'DB 전체 AI 능동 분석'을 마친 DB 에서 구조 변동(테이블 신규·컬럼 구성 변경·프로시저/함수 정의 변경)이 감지됐을 때, 사용자 실행 없이 자동으로 분석할 노드 수의 1회 상한입니다. 초과분은 다음 감지 사이클로 이월됩니다. 값이 클수록 변경 반영은 빨라지지만 승인 없는 LLM 호출이 늘어납니다. **0 = 완전 정지**(신규 발동 차단 + 이미 대기 중인 자동 분석 작업도 보류 — 값을 되돌리면 그대로 재개). **-1 = 관찰 모드**(감지 규모만 기록하고 분석은 하지 않음 — 비용 0). 재배포 없이 즉시 적용됩니다.",
        "unit": "개",
        "default": 50,
        "minimum": -1,
        "maximum": 500,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC",
        "category": "그래프 노드 분석",
        "label": "구조 변동 자동 재분석 쿨다운",
        "description": "같은 DB 에서 자동 재분석을 다시 시작하기까지 기다리는 최소 시간. 마이그레이션처럼 짧은 시간에 DDL 이 몰릴 때 분석 run 이 남발되는 것을 막습니다. 짧게 하면 변경이 더 빨리 반영되고, 길게 하면 비용이 더 촘촘히 묶입니다.",
        "unit": "초",
        "default": 1800,
        "minimum": 60,
        "maximum": 86400,
        "apply_mode": "live",
    },
    # ── cluster_label (semantic_cluster 데몬) ──
    {
        "key": "AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY",
        "category": "cluster_label(클러스터 라벨)",
        "label": "클러스터 라벨 동시 생성 수",
        "description": "cluster_label 생성 시 라벨 배치(≤40 클러스터/호출)를 동시에 LLM 호출하는 개수. 1 이면 현행처럼 배치 순차, 2 이상이면 병렬로 라벨을 생성해 클러스터 라벨링이 빨라집니다. 동시 LLM 호출이 늘어 Bedrock 한도를 더 씁니다.",
        "unit": "개",
        "default": 1,
        "minimum": 1,
        "maximum": 4,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_METADATA_CLUSTER_INTERVAL_SEC",
        "category": "cluster_label(클러스터 라벨)",
        "label": "클러스터링 데몬 주기",
        "description": "의미 클러스터링·라벨 데몬이 한 pass 후 다음 pass 까지 쉬는 시간. 낮추면 새 분석 결과가 더 빨리 클러스터·라벨에 반영되지만 임베딩/LLM 부하가 늘어납니다.",
        "unit": "초",
        "default": 900,
        "minimum": 60,
        "maximum": 86400,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS",
        "category": "cluster_label(클러스터 라벨)",
        "label": "시그니처 백필 배치 크기",
        "description": "클러스터링 전 단계인 메타데이터 시그니처 임베딩 백필의 pass 당 최대 행수. 높이면 백필이 빨리 따라잡지만 임베딩 호출 부하가 커집니다.",
        "unit": "행",
        "default": 2000,
        "minimum": 50,
        "maximum": 5000,
        "apply_mode": "live",
    },
    # ── 사용자 답변 처리 (ask-worker) ──
    {
        "key": "AGENT_ASK_WORKER_CONCURRENCY",
        "category": "사용자 답변 처리",
        "label": "답변 동시 처리 수",
        "description": "ask-worker 한 컨테이너가 동시에 처리하는 사용자 답변(run) 수. 1 이면 현행처럼 한 번에 한 답변만 직렬 처리, 2 이상이면 여러 사용자의 답변을 병렬로 처리해 대기 시간이 줄어듭니다. 각 병렬 답변이 PG 커넥션(하트비트)+소스 DB 커넥션을 점유하고 동시 LLM 호출이 늘므로, pgbouncer 풀·LLM 한도·메모리(mem_limit) 여유 안에서 올리세요. 이 값은 워커 재시작/재배포 시 반영됩니다.",
        "unit": "개",
        "default": 1,
        "minimum": 1,
        "maximum": 8,
        "apply_mode": "restart",
    },
    {
        "key": "AGENT_ASK_WORKER_IDLE_POLL_MS",
        "category": "사용자 답변 처리",
        "label": "유휴 폴링 간격",
        "description": "처리할 답변이 없을 때 ask-worker 가 큐를 다시 확인하기까지의 간격(밀리초). 낮추면 새 요청을 더 빨리 집어와 큐 대기가 줄지만, 유휴 시 DB 폴링이 잦아집니다. (기존 0.5초 = 500ms 와 동일한 기본값.)",
        "unit": "밀리초",
        "default": 500,
        "minimum": 100,
        "maximum": 5000,
        "apply_mode": "live",
    },
    # ── 지식베이스 임베딩 (기타 워커 기능) ──
    {
        "key": "AGENT_KB_EMBEDDING_BATCH_MAX_ROWS",
        "category": "지식베이스 임베딩",
        "label": "임베딩 백필 pass 당 행수",
        "description": "insight-worker 임베딩 백필 데몬이 한 pass 에서 처리하는 최대 행수. 높이면 임베딩이 빨리 따라잡지만 embedding gateway 부하가 커집니다.",
        "unit": "행",
        "default": 100,
        "minimum": 10,
        "maximum": 2000,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_KB_EMBEDDING_INTERVAL_SEC",
        "category": "지식베이스 임베딩",
        "label": "임베딩 데몬 주기",
        "description": "임베딩 백필 데몬이 한 pass 후 다음 pass 까지 쉬는 시간. 낮추면 임베딩이 더 자주 갱신되지만 부하가 늘어납니다.",
        "unit": "초",
        "default": 60,
        "minimum": 10,
        "maximum": 3600,
        "apply_mode": "live",
    },
    # ── 자원 격리·관측 (worker-resource-isolation T0) ──────────────────────────
    #   위 CONCURRENCY 계열은 **작업별** 병렬도다. 아래는 여러 작업이 함께 쓰는 **자원 총량**의
    #   상한이다 — 작업별 상한만으로는 "노드 분석 8 + 라벨 4 + 프로브 N" 이 동시에 같은 풀을
    #   먹는 상황을 막지 못한다(§82 사건의 구조). 기본값은 현행 최대 동시성 이상이라 게이트가
    #   발동하지 않는다(배포 시점 byte-동치). 값을 내리면 그 순간부터 격리가 작동한다.
    {
        "key": "AGENT_BACKGROUND_ANALYSIS_ENABLED",
        "category": "자원 격리·관측",
        "label": "백그라운드 분석 전역 사용",
        "description": "0 으로 내리면 노드 분석·클러스터 라벨·분류 제안이 즉시 멈춥니다(대기 중인 작업까지 보류 — 값을 되돌리면 그대로 재개). 부하 급증 시 재배포 없이 쓰는 정지 스위치입니다.",
        "unit": "",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_WORKER_LLM_BUDGET",
        "category": "자원 격리·관측",
        "label": "백그라운드 LLM 동시 호출 총량",
        "description": "여러 백그라운드 작업이 합쳐서 동시에 낼 수 있는 LLM 호출 수의 상한입니다. 작업별 병렬도의 합보다 낮게 내리면 그 순간부터 초과분이 다음 주기로 밀립니다(대기 없이 건너뜀).",
        "unit": "개",
        "default": 16,
        "minimum": 1,
        "maximum": 32,
        "apply_mode": "live",
    },
    # T0b: 게이트가 배선된 자원만 knob 을 둔다(ADR-0025-06). 아래 2개는 실제 게이트 지점이 있다 —
    #   DS = 소스 DB 연결 3지점(컬럼 introspect·루틴 backfill MSSQL/MySQL), TASK = 백그라운드 작업
    #   진입 3지점(노드 분석 tick·클러스터 pass·분류 pass).
    #   ⚠ `AGENT_WORKER_PG_BUDGET` 은 **여전히 없다** — PG 동시 점유를 정확히 강제하려면 커넥션
    #   수명과 예산 수명을 묶어야 하고(워커는 `conn=None 이면 열고 주어지면 재사용` + 호출측 finally
    #   close 패턴) 광범위 리팩터가 된다. 대신 TASK(작업 단위)로 근사한다 — 작업 하나가 여는 PG
    #   연결이 1~2개라 TASK 상한이 PG 점유 상한의 근사다. 이름을 PG_BUDGET 으로 쓰지 않는 이유다.
    {
        "key": "AGENT_WORKER_DS_BUDGET",
        "category": "자원 격리·관측",
        "label": "소스 DB 동시 연결 총량",
        "description": "백그라운드 작업이 운영 데이터소스에 동시에 여는 연결 수의 상한입니다. 낮추면 운영 DB 부하가 줄고, 대신 메타데이터 수집·루틴 backfill 이 여러 주기에 나눠 진행됩니다.",
        "unit": "개",
        "default": 8,
        "minimum": 1,
        "maximum": 32,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_WORKER_TASK_BUDGET",
        "category": "자원 격리·관측",
        "label": "동시 진행 백그라운드 작업 수",
        "description": "노드 분석·클러스터링·분류 제안이 동시에 진행되는 개수의 상한입니다. 작업 하나가 지식베이스 PG 커넥션 1~2개를 쓰므로, 이 값을 낮추면 워커가 pgbouncer 풀을 잠식해 서비스 전역이 느려지는 상황을 억제합니다.",
        "unit": "개",
        "default": 8,
        "minimum": 1,
        "maximum": 16,
        "apply_mode": "live",
    },
    # ── 분석 증거 수집 (feature-0031 analysis-grounding L0) ─────────────────────
    #   노드 분석의 LLM 입력에 데이터 실측을 붙이기 위한 통계 수집. **원시 값은 저장하지도
    #   주입하지도 않는다** — 집계값과 문자열 형태 분류만 남는다(DB CHECK 제약이 강제).
    #   부하는 위 `AGENT_WORKER_DS_BUDGET` 게이트 위에서 나며, 첫 접촉은 카탈로그만 읽어
    #   사용자 테이블 read 가 0 이다. 아래 두 상한이 "얼마나 깊이 파는가"를 정한다.
    {
        "key": "AGENT_METADATA_CLUSTER_SUMMARY",
        "category": "자원 격리·관측",
        "label": "클러스터 요약 생성 사용",
        "description": "비슷한 테이블끼리 묶인 그룹마다 '이 묶음이 함께 무엇을 하는지'를 2~4문장으로 요약해 둡니다. 그룹 이름만으로는 알 수 없는 도메인 맥락이 쌓여, 나중에 전체를 파악할 때 개별 분석문을 일일이 읽지 않아도 됩니다. 0 으로 내리면 생성이 멈추고 기존 요약은 그대로 남습니다.",
        "unit": "",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_BACKGROUND_LLM_TOKEN_CAP_24H",
        "category": "자원 격리·관측",
        "label": "백그라운드 LLM 토큰 상한(24시간)",
        "description": "사람이 요청하지 않은 자동 분석·요약·분류가 최근 24시간 동안 쓸 수 있는 토큰 총량입니다. 넘어서면 새 백그라운드 작업이 다음 주기로 밀립니다(진행 중 작업은 끝까지 갑니다). 대화 답변처럼 사용자가 기다리는 호출은 이 상한과 무관하게 항상 나갑니다. 0 으로 두면 상한 없음.",
        "unit": "토큰",
        "default": 20000000,
        "minimum": 0,
        "maximum": 500000000,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_METADATA_STATS_ENABLED",
        "category": "자원 격리·관측",
        "label": "분석 증거 수집 사용",
        "description": "노드 분석 직전에 대상 테이블의 통계(행 수 추정·컬럼 타입·NULL 비율·값 분포)를 수집해 분석 입력에 붙입니다. 0 으로 내리면 수집이 멈추고 분석은 종전처럼 이름·관계만 보고 진행합니다. 컬럼 값 자체는 어떤 경우에도 저장하지 않습니다.",
        "unit": "",
        "default": 1,
        "minimum": 0,
        "maximum": 1,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_METADATA_STATS_MAX_STAGE",
        "category": "자원 격리·관측",
        "label": "증거 수집 깊이 상한",
        "description": "0=구조 정보만(운영 테이블 조회 없음) · 1=100행 표본 · 2=1,000행 표본 · 3=정밀. 테이블마다 0 에서 시작해 하루 한 단계씩만 올라가며 이 값에서 멈춥니다. 3 은 대형 테이블 전수 집계라 운영자가 부하를 감안해 직접 올릴 때만 쓰세요.",
        "unit": "단계",
        "default": 2,
        "minimum": 0,
        "maximum": 3,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_METADATA_STATS_DAY_MAX_STAGE",
        "category": "자원 격리·관측",
        "label": "주간 증거 수집 깊이 상한",
        "description": "업무시간(08~22시)에 허용하는 수집 깊이입니다. 야간에는 위의 상한까지 올라가고 주간에는 이 값에서 멈춥니다 — 사용자가 붐비는 시간대에 표본 조회가 커지지 않게 합니다.",
        "unit": "단계",
        "default": 1,
        "minimum": 0,
        "maximum": 3,
        "apply_mode": "live",
    },
    {
        "key": "AGENT_METADATA_STATS_REFRESH_HOURS",
        "category": "자원 격리·관측",
        "label": "증거 재수집 간격",
        "description": "같은 테이블을 다시 살펴보기까지 기다리는 시간입니다. 이 간격이 지나야 깊이가 한 단계 올라가므로, 값을 늘리면 승격이 그만큼 느려지고 운영 DB 조회도 드물어집니다.",
        "unit": "시간",
        "default": 24,
        "minimum": 1,
        "maximum": 720,
        "apply_mode": "live",
    },
)


def _perf_specs() -> tuple[dict[str, Any], ...]:
    return tuple(dict(spec, group=GROUP_PERF) for spec in _PERF_SPECS)


def node_analysis_concurrency() -> int:
    """insight-worker 노드 분석 tick 당 병렬 처리 수(런타임 override 반영, 기본 1=순차)."""
    return max(1, get_int("AGENT_NODE_ANALYSIS_CONCURRENCY"))


def cluster_label_concurrency() -> int:
    """cluster_label 배치 LLM 호출 병렬 수(런타임 override 반영, 기본 1=순차)."""
    return max(1, get_int("AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY"))


def ask_worker_concurrency() -> int:
    """ask-worker 컨테이너 내 동시 답변 처리 수(런타임 override 반영, 기본 1=직렬)."""
    return max(1, get_int("AGENT_ASK_WORKER_CONCURRENCY"))


def ask_worker_idle_poll_sec() -> float:
    """ask-worker 유휴 폴링 간격(초). 런타임 override(ms)를 초로 환산, 기본 0.5초."""
    return max(0.05, get_int("AGENT_ASK_WORKER_IDLE_POLL_MS") / 1000.0)


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
            + _folder_specs()
            + _perf_specs()
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
    performance: list[dict[str, Any]] = []
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
        elif spec.get("group") == GROUP_PERF:
            performance.append(row)
        else:
            timeouts.append(row)
    return {
        "timeouts": timeouts,
        "agent_max_outputs": agent_outputs,
        "model_thinking_budgets": models,
        "reasoning_budgets": reasoning,
        # adaptive(Sonnet 5) 계열: budget_tokens 미적용(effort 로 제어). 위 model_thinking_budgets/
        # reasoning_budgets 에 이 모델들의 행은 없으며(스펙 미생성), admin UI 가 이 목록으로 해당
        # 모델 카드에 죽은 슬라이더 대신 guide-note 를 렌더한다(총 출력 agent_max_outputs 는 유지).
        "adaptive_models": list(_adaptive_thinking_models()),
        "redteam": redteam,
        "performance": performance,
        "meta": {
            "snapshot_path": snapshot_path(),
            "disabled": _disabled(),
            "cache_ttl_sec": _ttl_sec(),
        },
    }
