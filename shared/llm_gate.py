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
- **비차단(설계상)**: KB 임베딩. 계정 자격증명과 무관하며 별도 클라이언트 경로를 쓴다.
  임베딩까지 끄면 검색이 죽는데, 그건 사용자가 요청한 "계정 사용 차단" 과 무관한 부수 피해다.
  ⚠ local-llm-decommission(2026-09-07): 그 임베딩의 백엔드였던 로컬 `bge-m3`/ollama(embed-ollama)가
  사용자 결정("로컬 LLM 미사용")으로 제거됐다. 따라서 본 게이트가 임베딩을 막지 않는다는 사실은
  그대로지만, **막을 임베딩 호출 자체가 없다** — `AGENT_KB_EMBEDDING_MODEL` 기본값이 빈 값이라
  `_embed_query_vector` 가 호출 전에 None 을 반환하고 `kb_retrieval` 이 pg_trgm 로 흐른다.
  즉 검색은 죽지 않고 **벡터 축만 강등**됐다(기존 임베딩 154,365행은 보존, 미사용).

## ⚠ 이 게이트는 **기존 테스트의 전제를 깬다** (2026-08-27 실측)

게이트가 닫히면 그 뒤의 코드는 실행되지 않는다. 그러니 그 뒤를 검사하던 테스트는 실패하거나 —
더 나쁘게는 — "차단됨" 한 줄만 확인하고 **통과한다**(vacuous pass). 전환을 되돌리는 날 방어가
사라진 것을 그때 알게 된다.

`pytest.skip` 은 오답이다. 계약을 영원히 안 보게 만든다. 대신 **이중 계약**:

1. 대상이 게이트 **뒤** 로직이면 그 테스트/픽스처가 `AGENT_SERVER_LLM_ENABLED=1` 로 명시적으로 연다
   (모듈 전체면 autouse 픽스처 — autouse 는 파일 전역임을 주석에 밝힌다).
2. 게이트 **자체** 는 별도 테스트가 **반환값으로** 검사한다. 소스 문자열 검사만으로는
   `if not enabled` → `if enabled` 조건 반전을 못 잡는다.

실제로 이 전환이 깬 것: `test_routine_dbanalysis` · `test_graph_funcproc_uxfix`(node_analysis) ·
`test_llm_provider_health`(probe) · `test_mssql_auth_cooldown`(insight cycle) ·
`bin/smoke-conversation.sh`(배포 게이트 — 스크립트를 모드 인지형으로 고쳤다).

**새 차단 지점을 추가할 때는 그 지점 뒤를 검사하던 것을 먼저 찾아라** — 테스트뿐 아니라
배포 검증 스크립트까지. 첫 전환의 blast-radius 목록에 검증 스크립트가 빠져 배포가 멈췄다.

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
    "feature_blocked_message",
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


def feature_blocked_message(feature: str) -> str:
    """**대화가 아닌** 기능(관리 콘솔 자동완성·분석 등)이 차단됐을 때의 안내.

    왜 별도인가: `server_llm_blocked_message()` 는 "본인 AI 가 대신 처리한다" 고 말한다. 그 말은
    대화 질문에만 참이다 — 관리 콘솔의 자동완성·분석은 브리지로 넘어가지 않으므로, 같은 문구를
    쓰면 오지 않을 결과를 기다리게 만든다.

    그리고 **"초기화할 수 없습니다" 같은 장애 문구를 쓰지 않는다.** 이것은 고장이 아니라 운영
    결정이고, 장애로 읽히면 사용자는 무한히 재시도하며 원인을 찾는다(전환 전에는 되던 기능이라
    더욱 그렇다). 무엇이·왜·어떻게 되돌리는지를 한 번에 말한다.
    """
    label = str(feature or "이 기능").strip() or "이 기능"
    return (
        f"{label}은(는) 서버 계정 AI 를 쓰던 기능이라 현재 제공되지 않습니다. "
        "이 서비스는 서버 계정으로 AI 를 호출하지 않도록 전환됐습니다(고장이 아닙니다). "
        "대화 화면의 질문은 본인 AI(MCP 연결)가 처리하며, 이 기능이 필요하면 운영자에게 문의하세요."
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
