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
