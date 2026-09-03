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


# ── AI 사용 가능성 — 관측된 사실로 신고한다 (TASK-20260903T140000) ─────────────
#
# ## 무엇이 깨져 있었나 (사용자 지적 2026-09-03)
#
# 능력 협상이 실패해도 그 사실은 **모델 선택기를 숨기는 데만** 쓰였다. 「이 러너는 답할 수
# 없다」로는 취급되지 않았으므로 러너는 질문을 정상 점유했고, 그 뒤 `claude.exe` 가 무한
# 응답 없음(실측 300초 timeout·출력 0바이트, `oauth/token 400` 반복)이라 **사용자는 아무
# 안내도 없이 영원히 기다렸다.**
#
# 사용자 지적: *"모델을 탐색하는데 실패했다는 사실이 사용자에게는 알려지지 않고 영원히
# 기다리게 됩니다. 작동에 이슈가 나타난 사실이 해소되지 않았으니 명백한 오류입니다."*
#
# ## 무엇을 신고하는가
#
# **추측이 아니라 관측**이다 — 이 러너가 실제로 AI 를 부른 결과만 반영한다:
#
#   - 능력 협상이 그 런타임에서 실패했다  → 「응답이 없다」의 첫 관측(질문 전에 알 수 있는 유일한 신호)
#   - 실제 질문 처리가 연속 `_AI_FAIL_STREAK_MAX` 회 실패했다 → 계속 실패한다
#   - **한 번이라도 성공하면 즉시 복귀한다** — 낡은 판정으로 멀쩡한 러너를 막지 않는다.
#
# ## fail-open 으로 시작하는 이유
#
# 초기값은 «사용 가능»이다. 「증명될 때까지 불가」로 두면 첫 질문을 받을 방법이 없어(성공의
# 근거가 질문 처리뿐이라) 교착이 된다. 대신 협상 실패가 **질문 전에** 첫 관측을 준다.

#: 연속 실패를 몇 번 보면 「못 쓴다」로 판정할지. 1회는 일시적 오류(순단·한도)일 수 있고,
#: 그 한 번으로 계정의 질문을 막으면 오탐 비용이 사용자 차단이 된다.
_AI_FAIL_STREAK_MAX = 2

_AI_READY = True
_AI_UNREADY_REASON = ""
_AI_FAIL_STREAK = 0


def ai_health() -> "tuple[bool, str]":
    """(쓸 수 있는가, 못 쓰는 사유). 사유는 사용자에게 보일 수 있는 문장이다."""
    return _AI_READY, _AI_UNREADY_REASON


def note_ai_unusable(reason: str) -> None:
    """질문 **전에** 얻은 관측(능력 협상 실패)으로 곧바로 「못 쓴다」로 표시한다."""
    global _AI_READY, _AI_UNREADY_REASON
    _AI_READY = False
    _AI_UNREADY_REASON = str(reason or "").strip()[:300]


def note_ai_outcome(ok: bool, reason: str = "") -> None:
    """실제 AI 호출 결과 1건을 반영한다.

    성공은 **즉시** 복귀시킨다(스트릭도 함께 지운다) — 한 번 통하면 그 러너는 쓸 수 있고,
    낡은 실패 기록으로 계속 막는 것은 사용자에게 거짓이다.
    """
    global _AI_READY, _AI_UNREADY_REASON, _AI_FAIL_STREAK
    if ok:
        _AI_FAIL_STREAK = 0
        _AI_READY = True
        _AI_UNREADY_REASON = ""
        return
    _AI_FAIL_STREAK += 1
    if _AI_FAIL_STREAK >= _AI_FAIL_STREAK_MAX:
        _AI_READY = False
        _AI_UNREADY_REASON = str(reason or "").strip()[:300] or "연결된 AI 가 응답하지 않습니다."


def reset_ai_health() -> None:
    """테스트 전용 — 프로세스 전역이라 케이스 간 누수를 막는다."""
    global _AI_READY, _AI_UNREADY_REASON, _AI_FAIL_STREAK
    _AI_READY, _AI_UNREADY_REASON, _AI_FAIL_STREAK = True, "", 0
