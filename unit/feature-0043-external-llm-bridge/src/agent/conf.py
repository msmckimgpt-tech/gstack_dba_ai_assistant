"""설정 파일 저장·로드 (재기동 시 `--resume` 한 줄로 끝나게).

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import json
import os

from .base import _CONF_DIR, _CONF_PATH
from .logs import _log_exc
from .state import runner_instance

def save_conf(base: str, ca: str | None, ai: str, cmd: str | None,
              caps: dict | None = None) -> None:
    """다음 실행이 `--resume` 한 줄로 끝나게 한다.

    머신을 재시작하면 이 프로세스는 사라진다(사용자 지적 2026-08-27). 그때 사용자가 다시
    챙겨야 하는 것이 많을수록 **아무도 다시 띄우지 않는다.** 토큰만 새로 받으면 되게 한다.

    `caps` 는 각 AI 가 스스로 답한 능력(P0-Z4)이다. 여기 저장하는 이유는 **매 기동마다 다시
    묻지 않기 위해서**다 — 그 질의는 사용자 계정의 토큰을 쓰고 수십 초가 걸린다. 갱신은
    `--refresh-caps` 로 사용자가 명시할 때만(모델 목록이 바뀌는 일은 드물다).

    ⚠ 여기에는 **플래그 형태(`model`/`effort`)도 함께** 남지만 그것은 서버로 나가지 않는다.
    호출법을 아는 것은 이 파일과 러너뿐이다(P0-Z3 신뢰 경계).
    """
    try:
        os.makedirs(_CONF_DIR, exist_ok=True)
        payload = {"base": base, "ca": ca, "ai": ai, "cmd": cmd}
        # ⚠ 이 함수는 파일을 **통째로 다시 쓴다**. 여기서 이어 나르지 않는 키는 사라진다 —
        #   `runner_instance` 가 사라지면 다음 기동이 "직전 프로세스" 를 몰라 고아 점유 회수가
        #   조용히 죽는다(그리고 그 죽음은 30분 뒤에야 증상으로 나타나 원인을 짚기 어렵다).
        if runner_instance():
            payload["runner_instance"] = runner_instance()
        else:
            _prev_inst = load_conf().get("runner_instance")
            if _prev_inst:
                payload["runner_instance"] = _prev_inst
        if caps is not None:
            payload["caps"] = caps
        else:
            # 이번 실행이 능력을 새로 구하지 않았다면(예: `--cmd` 모드) 기존 캐시를 지우지
            # 않는다 — 다음 일반 기동이 다시 묻는 비용을 물지 않게.
            prev = load_conf().get("caps")
            if prev:
                payload["caps"] = prev
        with open(_CONF_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.chmod(_CONF_PATH, 0o600)
    except Exception as e:  # noqa: BLE001
        # 여기 실패는 **다음 기동**을 망친다(주소·CA·능력 캐시를 잃는다). 그런데 증상은
        # 지금이 아니라 다음에 나타나므로, 예외 형까지 남겨 두지 않으면 그때 원인에
        # 닿지 못한다 — 권한(PermissionError)과 디스크 가득(OSError)은 조치가 다르다.
        _log_exc("conf.save_fail", "설정 저장 실패(무시)", e, path=_CONF_PATH)


def load_conf() -> dict:
    try:
        with open(_CONF_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}
