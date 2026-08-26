"""feature-0043 — 서버 보유 계정 LLM 호출의 fail-closed 게이트 (단일 정본).

## 왜 이 모듈이 있는가

이 서비스는 `claude-corp` · `root` 두 Claude 계정의 OAuth 토큰으로 LLM 을 호출해 왔다.
2026-08-07 claude-corp 7일 쿼터 100% 소진으로 서비스가 멈춘 뒤, 사용자 결정(2026-08-26)으로
**추론 주체를 뒤집는다** — 서버는 도구·컨텍스트·데이터만 제공하고, 추론은 각 사용자의 개인 머신
AI 런타임이 자기 계정 LLM 으로 수행한다(feature-0041 도구 표면 + feature-0043 pull 브리지).

그 전환의 차단선이 이 모듈이다. `litellm_config.yaml` 의 alias 주석처리는 **두 번째 자물쇠**일 뿐이고,
여기가 첫 번째이자 정본이다.

## 왜 코드 기본값이 '차단' 인가

`.env` 는 gitignore 대상이고 `config/` 는 배포에 포함되지 않는다(운영 실측). 설정 파일이 정본이면
"설정이 안 실린 환경에서는 잠금이 풀린다" 는 뒤집힌 안전성이 생긴다. 그래서 **코드 기본값을 차단**으로
두고, 해제는 env 로 명시할 때만 일어나게 한다 — 잊으면 잠기는 쪽으로 실패한다.

## 적용 범위

- **차단**: 대화 답변 · 대화 보조 단계 · insight 배치 · node_analysis · cluster_label · redteam · probe
  — 즉 `modules/llm._get_llm_client()` 와 `agent_core` 의 직접 클라이언트 생성부를 지나는 모든 chat 호출.
- **비차단**: KB 임베딩(로컬 `bge-m3`/ollama). 계정 자격증명과 무관하며 별도 클라이언트 경로를 쓴다.
  임베딩까지 끄면 검색이 죽는데, 그건 사용자가 요청한 "계정 사용 차단" 과 무관한 부수 피해다.

## 되돌리기

`AGENT_SERVER_LLM_ENABLED=1` (env) → 이 게이트가 열린다. `litellm_config.yaml` 의 alias 주석까지
해제하면 전환 이전 동작으로 완전히 복귀한다. 두 자물쇠 모두 풀어야 열리는 것이 의도다.
"""
from __future__ import annotations

import logging
import os
import threading
import time

__all__ = [
    "SERVER_LLM_ENABLED_ENV",
    "server_llm_enabled",
    "server_llm_blocked_message",
    "note_server_llm_blocked",
    "reset_gate_cache_for_tests",
]

logger = logging.getLogger(__name__)

#: 해제 knob. 이 env 가 참 값일 때만 서버 계정 LLM 호출이 허용된다(기본 = 차단).
SERVER_LLM_ENABLED_ENV = "AGENT_SERVER_LLM_ENABLED"

_TRUTHY = frozenset({"1", "true", "yes", "on"})

#: 차단 로그 throttle — 워커 루프가 초당 수십 회 두드려도 로그가 폭주하지 않게 한다.
#: 무음(silent) 실패는 금지지만(§AC-8), 같은 사유를 무한 반복하는 것도 진단을 가린다.
_LOG_INTERVAL_SEC = 60.0
_last_logged: dict[str, float] = {}
_log_lock = threading.Lock()


def server_llm_enabled() -> bool:
    """서버 보유 계정으로 LLM 을 호출해도 되는가.

    **기본값은 False(차단)** — env 가 없거나 비어 있으면 잠긴다. 매 호출마다 env 를 읽는다
    (모듈 로드 시점에 상수로 굳히면 컨테이너 재기동 없이 값을 바꿀 수 없고, 테스트에서
    monkeypatch 한 env 가 반영되지 않아 vacuous pass 가 생긴다).
    """
    return str(os.getenv(SERVER_LLM_ENABLED_ENV, "") or "").strip().lower() in _TRUTHY


def server_llm_blocked_message() -> str:
    """사용자 대면 안내 문구 (한 문장).

    호출측이 이 문자열을 그대로 노출해도 되도록 내부 용어(alias·env 이름)를 담지 않는다.
    """
    return (
        "이 서비스는 서버 계정으로 AI 답변을 생성하지 않습니다. "
        "질문은 본인 AI(MCP 연결)가 처리하며, 연결 방법은 '외부 AI 연결' 안내를 참고하세요."
    )


def note_server_llm_blocked(caller: str) -> None:
    """차단 사실을 로그로 남긴다 (caller 별 60초 throttle).

    `caller` 는 차단된 지점의 식별자(예: ``"modules.llm._get_llm_client"``). 사유를 남기지 않고
    조용히 ``None`` 을 반환하면 "왜 답이 없지" 를 추적할 단서가 사라진다 — 정직한 실패 계약.
    """
    key = str(caller or "unknown")
    now = time.monotonic()
    with _log_lock:
        prev = _last_logged.get(key)
        if prev is not None and (now - prev) < _LOG_INTERVAL_SEC:
            return
        _last_logged[key] = now
    logger.warning(
        "[llm-gate] 서버 계정 LLM 호출 차단 caller=%s — feature-0043 전환(추론은 사용자 개인 "
        "AI 런타임이 수행). 되돌리려면 env %s=1.",
        key,
        SERVER_LLM_ENABLED_ENV,
    )


def reset_gate_cache_for_tests() -> None:
    """throttle 상태 초기화 — 테스트가 로그 호출을 여러 번 단정할 수 있게 한다."""
    with _log_lock:
        _last_logged.clear()
