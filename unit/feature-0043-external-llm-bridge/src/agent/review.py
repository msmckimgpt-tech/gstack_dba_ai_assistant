"""자가 검증 — 같은 AI 에게 검증자 역할로 한 번 더.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import time

from .invoke import CANCELED, ask_local_ai
from .logs import _log

# ── 자가 검증 (TASK-20260901T110000) ─────────────────────────────────────────
#
# 답변을 내보내기 전에 **같은 AI 에게 검증자 역할로 한 번 더** 묻는다. 전환 전에는 서버가
# 이 일을 했고(`modules/redteam.py`), 게이트가 닫힌 뒤 아무도 하지 않게 됐다 — 그런데
# 관리 콘솔은 여전히 "본인 AI 가 검증한다" 고 말하고 있었다.
#
# **축·형식은 서버가 준다**(`claim_request` 응답의 `self_review.instruction`). 여기에 적어
# 두면 규약을 고칠 때마다 전 사용자가 재설치해야 하고, 재설치하지 않은 러너는 낡은 축의
# 판정을 같은 컬럼에 쓴다.


def run_self_review(directive: dict, draft: str, kind: str, argv: list[str],
                    custom: str | None, cancel_check=None,
                    model: str | None = None, effort: str | None = None,
                    runtimes: list | None = None, caps: dict | None = None) -> dict | None:
    """초안을 자기 AI 에게 되물어 5축 판정을 받는다. 실패·미수행이면 `None`.

    **답변을 만든 것과 같은 (런타임·모델·등급)** 으로 묻는다. 더 싼 모델로 검증하면 그
    검증은 답변을 만든 사고를 따라가지 못하고, 따라가지 못하는 검증은 표면적인 지적만 낸다
    (서버 시절에도 리뷰어를 별도 저비용 모델로 두었을 때 같은 성질이 관측됐다).

    ⚠ **실패를 위로 던지지 않는다.** 검증은 관측이고 답변은 사용자의 것이다 — 검증이
    실패했다고 이미 만들어 둔 답을 버리면, 관측을 위해 서비스를 끊는 셈이 된다.
    """
    if not isinstance(directive, dict) or not directive.get("enabled"):
        return None
    instruction = str(directive.get("instruction") or "")
    slot = str(directive.get("draft_slot") or "")
    if not instruction or not slot or slot not in instruction:
        # 서버가 준 지시문에 초안 자리가 없다 = 계약이 어긋났다. 지어내서 이어 붙이면
        # 검증자가 무엇을 검증하는지 모르는 채로 답한다.
        _log("자가 검증: 서버 지시문에 초안 자리가 없어 건너뜁니다.")
        return None
    if callable(cancel_check) and cancel_check():
        return None
    t0 = time.time()
    ok, raw = ask_local_ai(kind, argv, instruction.replace(slot, draft), custom,
                           cancel_check, model=model, effort=effort,
                           runtimes=runtimes, caps=caps)
    if not ok or raw == CANCELED or not str(raw or "").strip():
        return None
    # **파싱은 서버가 한다.** 여기서 JSON 을 뜯어 스키마를 강제하면 그 스키마가 러너에
    # 박히고, 서버의 것과 갈리는 순간 어느 쪽이 정본인지 알 수 없어진다. 러너는 원문을
    # 그대로 나른다 — 서버의 `self_review.sanitize` 가 형태를 못 갖춘 응답을 버린다.
    return {
        "raw": str(raw),
        "latency_ms": int((time.time() - t0) * 1000),
        # 무엇으로 검증했는지. 콘솔이 「답변 모델 ≠ 검증 모델」을 구분해야 할 날을 위해
        # 지금 남긴다(지금은 같지만, 같다는 사실도 기록되어야 확인할 수 있다).
        "model": model or "",
        "reasoning_level": effort or "",
    }
