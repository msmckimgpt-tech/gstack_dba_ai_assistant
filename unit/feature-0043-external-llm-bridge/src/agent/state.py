"""러너 인스턴스 전역 — 「이 프로세스」의 신원을 담는 **가변 상태**.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.

## 왜 별도 모듈인가 (모듈 분할의 구조적 요구)

단일 파일이던 시절 이 두 값은 그냥 모듈 전역이었고, `init_runner_instance` 가 `global` 로
재바인딩하면 같은 파일 안의 `save_conf`·`log_event` 가 **갱신된 값**을 보았다. 파일을 쪼개면
그 성질이 조용히 깨진다 — `from .identity import _RUNNER_INSTANCE` 는 import 시점의 값을
**복사해 묶으므로**, 이후 재바인딩이 반영되지 않는다(빈 문자열로 굳는다). 그러면 감사 원장의
`run` 필드와 설정 파일의 `runner_instance` 가 통째로 비고, 87분 고아 점유 사고를 고친
회수 경로가 **조용히** 되돌아간다(증상은 30분 뒤에야 나타난다).

`global` 은 모듈을 넘지 못한다. 그래서 값을 직접 내보내지 않고 **접근자로만** 노출한다 —
읽는 쪽이 호출 시점에 현재 값을 보게 되어 단일 파일 시절의 의미가 그대로 보존된다.
번들 산출물에서는 이 모듈도 같은 네임스페이스에 연접되므로 동작이 동일하다.
"""
from __future__ import annotations

#: 이 프로세스의 id. 서버의 `_sanitize_instance` 가 영숫자만 받으므로 hex 로 만든다.
_RUNNER_INSTANCE = ""

#: 직전 프로세스의 id(설정 파일에서 읽은 값). 없으면 빈 문자열 — 첫 실행이거나 인스턴스 축이
#: 없던 버전에서 올라온 것이다. 그때는 회수할 것이 없으므로 아무 일도 하지 않는다.
_PREV_RUNNER_INSTANCE = ""


def runner_instance() -> str:
    """지금 이 프로세스의 id. 아직 발급 전이면 빈 문자열."""
    return _RUNNER_INSTANCE


def prev_runner_instance() -> str:
    """직전 프로세스의 id. 없으면 빈 문자열."""
    return _PREV_RUNNER_INSTANCE


def set_runner_instance(current: str, prev: str) -> None:
    """`init_runner_instance` 전용 — 발급 결과를 한 번에 굳힌다.

    쓰는 곳이 하나뿐이라 setter 를 하나만 둔다. 둘로 나누면 「현재만 갱신되고 직전은 옛
    값」인 중간 상태가 생기고, 그 상태로 하트비트가 나가면 서버가 엉뚱한 인스턴스의 점유를
    놓아 준다.
    """
    global _RUNNER_INSTANCE, _PREV_RUNNER_INSTANCE
    _RUNNER_INSTANCE, _PREV_RUNNER_INSTANCE = current, prev


# AI 관측은 런타임과 DQA가 선택한 실행 위치 세대에만 적용한다.
# None은 미확인(표시상 정상 아님), False만 실행 차단, True는 실제 응답 성공이다.
import json
import os
import threading

from .runtimes import client_runtime_selection

_AI_FAIL_STREAK_MAX = 2
_AI_HEALTH_LOCK = threading.RLock()
_AI_HEALTH: dict[tuple[str, str, str], tuple[bool | None, str, int]] = {}


def ai_health_scope(runtime=None, model=None) -> tuple[str, str, str]:
    """느린 호출 전에 캡처하면 이전 위치의 늦은 결과가 새 위치를 덮지 않는다."""
    if isinstance(runtime, tuple):
        return runtime
    name = str(runtime or "")
    selected = client_runtime_selection()
    location = ((selected or {}).get(name) if selected is not None else
                os.environ.get(f"BRIDGE_AI_PATH_{name.upper()}", ""))
    return name, json.dumps(location, sort_keys=True, ensure_ascii=True), str(model or "")


def ai_health(runtime=None) -> tuple[bool | None, str]:
    """특정 AI의 관측 또는 현재 선택 위치들의 heartbeat 요약."""
    with _AI_HEALTH_LOCK:
        if runtime is not None:
            key = ai_health_scope(runtime)
            base = _AI_HEALTH.get((*key[:2], ""), (None, "", 0))
            if key[2] and base[0] is False:
                return base[:2]
            return _AI_HEALTH.get(key, base)[:2]
        selected = client_runtime_selection()
        if selected is not None:
            keys = [ai_health_scope(name) for name in selected]
        else:
            keys = [key for key in _AI_HEALTH
                    if key[:2] == ai_health_scope(key[0])[:2]]
        rows = [_AI_HEALTH.get(key, (None, "", 0)) for key in keys]
        if any(row[0] is True for row in rows):
            return True, ""
        if not rows or any(row[0] is None for row in rows):
            return None, ""
        return False, next((row[1] for row in rows if row[1]), "")


def ai_blocked(runtime=None) -> tuple[bool, str]:
    ready, reason = ai_health(runtime)
    return ready is False, reason


def note_ai_probing(reason: str = "", *, runtime=None) -> None:
    key = ai_health_scope(runtime)
    with _AI_HEALTH_LOCK:
        ready, old_reason, streak = _AI_HEALTH.get(key, (None, "", 0))
        if ready is not False:
            _AI_HEALTH[key] = (None, str(reason or "").strip()[:300], streak)


def note_ai_unusable(reason: str, *, runtime=None) -> None:
    key = ai_health_scope(runtime)
    with _AI_HEALTH_LOCK:
        streak = _AI_HEALTH.get(key, (None, "", 0))[2]
        _AI_HEALTH[key] = (False, str(reason or "").strip()[:300], streak)


def note_ai_outcome(ok: bool, reason: str = "", *, runtime=None) -> None:
    key = ai_health_scope(runtime)
    with _AI_HEALTH_LOCK:
        if ok:
            _AI_HEALTH[key] = (True, "", 0)
            if key[2]:
                _AI_HEALTH[(*key[:2], "")] = (True, "", 0)
            return
        ready, old_reason, streak = _AI_HEALTH.get(key, (None, "", 0))
        streak += 1
        if streak >= _AI_FAIL_STREAK_MAX:
            ready = False
            old_reason = str(reason or "").strip()[:300] or "연결된 AI 가 응답하지 않습니다."
        _AI_HEALTH[key] = (ready, old_reason, streak)


def reset_ai_health() -> None:
    """테스트 전용: 미확인 상태로 초기화."""
    with _AI_HEALTH_LOCK:
        _AI_HEALTH.clear()
