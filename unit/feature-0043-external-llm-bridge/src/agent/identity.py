"""러너 인스턴스 — 「이 프로세스」의 신원 발급.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import json
import os
import secrets

from .base import _CONF_DIR, _CONF_PATH
from .conf import load_conf
from .logs import _log_exc
from .state import prev_runner_instance, runner_instance, set_runner_instance

# ── 러너 인스턴스 — 「이 프로세스」의 신원 (TASK-20260901T140000) ──────────────────
#
# ## 무엇을 고치는가 (라이브 실측 2026-09-01)
#
# 러너가 질문을 점유한 뒤 **프로세스가 사라지면**(재설치·재부팅·토큰 만료로 인한 종료·크래시)
# 그 점유는 서버에 그대로 남는다. 서버의 lease 는 도구 호출마다 갱신되므로 마지막 갱신값에서
# 30분을 더 기다려야 풀리고, 그동안 그 질문은 대기 목록에서 보이지 않는다 — **재기동한 자기
# 자신조차 되찾지 못한다.** 사용자 화면은 그 30분을 「처리 중」으로 그린다.
#
# 실측: 12:07 전달 → 12:13 러너 재기동 → 12:43 lease 만료로 재배달 → 재조사 중 토큰 만료로
# 또 종료 → 또 고아 → 13:34 사용자가 포기하고 재전송 → **80초 만에 완료**. 대기 87분.
#
# ## 어떻게 고치는가
#
# 프로세스마다 고유 id 를 만들어 **점유에 새기고**(`claim_request`), 설정 파일에 남긴다.
# 다음 기동이 그 값을 읽어 "직전 프로세스는 죽었다" 를 하트비트에 실으면, 서버는 그 id 로
# 점유된 미제출 작업만 정확히 놓아준다. 30분이 **다음 하트비트까지**로 줄어든다.
#
# 왜 서버가 알아서 못 하는가: 서버가 볼 수 있는 것은 "언제 마지막으로 도구를 불렀나" 뿐이고,
# 그것만으로는 **오래 생각하는 러너**와 **죽은 러너**가 구분되지 않는다. 살아 있는 쪽을 끊으면
# 조사가 통째로 버려지므로 서버는 보수적으로 기다릴 수밖에 없다. 「죽었다」는 사실을 확실히
# 아는 것은 그 자리에 새로 뜬 프로세스뿐이다.

#: 두 id 의 **저장소는 `state` 모듈**이다 — 여기서 `global` 로 들고 있으면 파일이 쪼개진 뒤
#: 읽는 쪽(`conf.save_conf`·`logs.log_event`)이 import 시점 값에 묶여 갱신을 못 본다.
#: 자세한 근거는 `state.py` 모듈 docstring 참조.


def init_runner_instance() -> tuple[str, str]:
    """이 프로세스의 id 를 발급하고 직전 id 를 돌려준다. `(현재, 직전)`.

    **설정을 읽은 직후·서버와 말을 트기 전에** 부른다 — 점유에 새길 값이 준비돼 있어야 하고,
    직전 id 는 이 함수가 덮어쓰기 전에만 읽을 수 있다.

    파일 저장이 실패해도 진행한다: 그때 잃는 것은 *다음* 기동의 회수뿐이고, 이번 실행의 점유
    표시와 종료 시 자기 해제는 메모리 값만으로 동작한다.
    """
    prev = str(load_conf().get("runner_instance") or "").strip()
    set_runner_instance(secrets.token_hex(6),   # 12자 — 서버 상한(16) 안
                        prev if (prev.isalnum() and prev.isascii()) else "")
    try:
        conf = load_conf()
        conf["runner_instance"] = runner_instance()
        os.makedirs(_CONF_DIR, exist_ok=True)
        with open(_CONF_PATH, "w", encoding="utf-8") as f:
            json.dump(conf, f, ensure_ascii=False)
        os.chmod(_CONF_PATH, 0o600)
    except Exception as e:  # noqa: BLE001
        _log_exc("conf.instance_save_fail",
                 "러너 인스턴스 저장 실패(무시) — 다음 기동의 고아 점유 회수가 동작하지 않는다",
                 e, path=_CONF_PATH)
    return runner_instance(), prev_runner_instance()
