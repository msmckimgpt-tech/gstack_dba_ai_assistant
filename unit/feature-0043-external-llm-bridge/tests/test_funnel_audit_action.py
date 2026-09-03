"""퍼널 ActionCode 가 **감사 원장 빌더에 등재돼 있는가** (라이브 실측 결함 2026-09-03).

## 무엇이 일어났나

`build_audit_change_json` 은 **명시적 allowlist** 다 — 등재되지 않은 ActionCode 는
`ValueError("unknown audit action: …")` 로 죽는다. ITEM-00 이 `ai.connect.funnel` 을 등재하지
않았고, `_audit_user_action` 이 그 예외를 **삼켜서(fail-open)** 아무 증상 없이 **퍼널 행이
0건**이었다. 배포 후 라이브 로그에서야 드러났다.

## 왜 기존 테스트가 못 잡았나 — **가짜 더블이 계약을 우회했다**

`test_connect_funnel.py` 는 `app._audit_user_action` 을 stub 으로 갈아끼운다. 그 더블은
「내가 부른다」를 검사할 뿐 **「받는 쪽이 받아 준다」를 검사하지 않는다.** 호출 형태가 맞아도
수신자가 거부하면 아무것도 남지 않는데, 더블은 항상 받아 준다.

그래서 이 스위트는 **진짜 빌더를 호출한다.** 더블 없이.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_WEB = _UNIT / "feature-0003-agent-web-ui" / "src"
_AUDIT_INFRA = _WEB / "routers" / "_audit_infra.py"
_FUNNEL = _WEB / "routers" / "_connect_funnel.py"


def _load(path: Path, name: str, stub_app=True):
    """모듈 단독 적재. `_audit_infra` 는 `app` 을 import 하므로 최소 stub 을 끼운다.

    ⚠ stub 은 **`app` 에만** 적용한다 — 검사 대상인 `build_audit_change_json` 자체는
    진짜를 쓴다. 그것이 이 스위트의 존재 이유다.
    """
    import types
    saved = sys.modules.get("app")
    if stub_app:
        sys.modules["app"] = types.ModuleType("app")
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if saved is not None:
            sys.modules["app"] = saved
        else:
            sys.modules.pop("app", None)


def _builder():
    return _load(_AUDIT_INFRA, "_audit_infra_under_test").build_audit_change_json


def _funnel():
    return _load(_FUNNEL, "_connect_funnel_under_test")


def test_funnel_action_is_registered_in_the_audit_builder():
    """**이 테스트가 없어서 라이브 행이 0건이었다.**

    빌더를 진짜로 부른다 — 등재가 빠지면 `ValueError` 로 여기서 죽는다.
    """
    f = _funnel()
    change, masked = _builder()(
        action=f.FUNNEL_ACTION, before=None, after=None,
        request_ctx={"step": "page_view", "path_kind": "runner_windows"},
    )
    assert change == {"step": "page_view", "path_kind": "runner_windows"}
    assert masked == []


@pytest.mark.parametrize("step", ("page_view", "handoff_issued", "first_heartbeat",
                                  "first_claim", "first_answer"))
def test_every_funnel_step_passes_the_builder(step):
    """다섯 단계 **전부** 빌더를 통과한다 — 하나만 검사하면 나머지가 조용히 샌다."""
    f = _funnel()
    change, _ = _builder()(action=f.FUNNEL_ACTION, before=None, after=None,
                           request_ctx={"step": step, "path_kind": "unknown"})
    assert change["step"] == step


def test_builder_output_carries_no_sensitive_fields():
    """빌더가 싣는 것은 `{step, path_kind}` 뿐이다 (SECURITY D12).

    `request_ctx` 에 실수로 민감값이 섞여 들어와도 빌더가 **그것을 옮기지 않는다**.
    """
    f = _funnel()
    change, _ = _builder()(
        action=f.FUNNEL_ACTION, before=None, after=None,
        request_ctx={"step": "page_view", "path_kind": "unknown",
                     "access_token": "mat_secret", "question": "비밀"},
    )
    assert set(change.keys()) == {"step", "path_kind"}
    assert "mat_secret" not in str(change) and "비밀" not in str(change)


def test_unknown_action_still_raises():
    """allowlist 정책 자체는 유지된다 — 이 수정이 빌더를 통과 일변도로 만들지 않았다."""
    with pytest.raises(ValueError):
        _builder()(action="ai.connect.notarealaction", before=None, after=None,
                   request_ctx={})


def test_every_builder_backed_action_is_registered():
    """**모수를 넓힌다** — 퍼널만 고치면 다음 신규 ActionCode 가 같은 함정에 빠진다.

    ⚠ **모수를 정확히 잡는 것이 이 검사의 핵심이다.** 초판은 `record_audit_event` 호출까지
    세어 27건을 «미등재» 로 보고했는데, 그쪽은 `change_json` 을 **호출자가 만들어 넘기므로
    빌더 allowlist 를 타지 않는다**. 과대 모수는 거짓 경보가 되고, 거짓 경보가 반복되면
    이 검사는 무시된다.

    빌더를 타는 것은 `_audit_user_action` 경로뿐이다 — 그것만 센다.
    """
    import ast

    build = _builder()
    seen: set[str] = set()
    for py in (_WEB / "routers").glob("*.py"):
        if py.name == "_audit_infra.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        # ⚠ `action=` 은 리터럴만이 아니라 **모듈 상수 참조**로도 온다
        #   (`action=FUNNEL_ACTION`). 리터럴만 세면 정작 이 결함을 낸 호출을 놓친다 —
        #   자기검증(`assert "ai.connect.funnel" in seen`)이 그것을 잡았다.
        consts: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        consts[t.id] = node.value.value
        # 다른 모듈에서 import 한 상수(`_funnel.FUNNEL_ACTION`)도 해석한다.
        for other in (_WEB / "routers").glob("*.py"):
            for node in ast.parse(other.read_text(encoding="utf-8")).body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                        and isinstance(node.value.value, str):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            consts.setdefault(t.id, node.value.value)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if "audit_user_action" not in ast.unparse(node.func):
                continue
            for kw in node.keywords:
                if kw.arg != "action":
                    continue
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    seen.add(kw.value.value)
                elif isinstance(kw.value, ast.Name) and kw.value.id in consts:
                    seen.add(consts[kw.value.id])
                elif isinstance(kw.value, ast.Attribute) and kw.value.attr in consts:
                    seen.add(consts[kw.value.attr])
    assert seen, "«_audit_user_action» 호출부를 하나도 찾지 못했다 — 검사 모수가 비었다"
    assert "ai.connect.funnel" in seen, "퍼널 호출부가 모수에 안 잡힌다 — 검사가 헛돈다"

    unregistered = []
    for action in sorted(seen):
        try:
            build(action=action, before=None, after=None, request_ctx={})
        except ValueError:
            unregistered.append(action)
        except Exception:
            pass    # 필드 부족 등 다른 예외는 이 검사의 관심사가 아니다
    #: **기존 격차 (이 cycle 범위 밖, 2026-09-03 발견)** — 빌더가 거부하므로 호출되면 감사가
    #: 조용히 사라진다. 라이브 로그에는 아직 안 나타났는데, 그 경로가 최근 실행되지 않았기
    #: 때문이지 «괜찮아서» 가 아니다. 각 ActionCode 의 change_json 모양은 그 기능 소유자가
    #: 정해야 하므로 **여기서 임의로 등재하지 않는다** — 별 cycle 로 분리하고, 그때까지
    #: 이 목록이 「알면서 두는 것」임을 명시한다.
    KNOWN_GAPS = {
        "attachment.assistant.create", "attachment.version.create",
        "conversation.member.ban", "conversation.member.fork_blocked",
        "conversation.member.join", "conversation.member.join_blocked",
        "conversation.member.remove", "conversation.member.unban",
    }
    new_gaps = sorted(set(unregistered) - KNOWN_GAPS)
    assert not new_gaps, (
        "감사 빌더에 등재되지 않은 **신규** ActionCode: " + ", ".join(new_gaps)
        + " — fail-open 이 삼켜 라이브에서 조용히 기록이 사라진다. "
        "`build_audit_change_json` 에 분기를 추가하라.")
    # 기존 격차가 **줄어들면** 이 목록도 줄여야 한다 — 낡은 면제는 새 결함을 숨긴다.
    stale = sorted(KNOWN_GAPS - set(unregistered))
    assert not stale, (
        "KNOWN_GAPS 에 남아 있지만 이미 등재된 ActionCode: " + ", ".join(stale)
        + " — 면제 목록에서 지워라(낡은 면제는 다음 결함을 숨긴다).")
