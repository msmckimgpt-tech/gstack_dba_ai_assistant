"""기동이 **능력 협상에 막혀 4분간 침묵**하던 것 (TASK-20260902T140000).

## 이 파일이 고정하는 라이브 결함

2026-09-02 사용자 제보의 나머지 절반 — *"연결은 수행되었는데 … 러너 로그에도 별도의 기록이
쌓이지 않는다"*. 그 계정의 러너 로그(`bridge.log`)가 남긴 것:

    12:27:53  run.start
    12:27:53  쓸 수 있는 모델·추론 수준을 물어보는 중… (claude — 최초 1회, 수십 초)
    (침묵 4분 — 하트비트 0건 · 질문 미수령)
    12:31:53  run.ready … startup_ms=240896

12:28:12 에 들어온 질문은 **12:31:54 에야** 점유됐다. 그동안 웹은 「연결 안 됨」이었고,
설치 스크립트는 `--check` 성공 뒤 **2초**만 보고 「완료」를 선언한 상태였다.

원인: 능력 협상(`resolve_caps`)이 하트비트·대기 루프보다 **앞**에 있었고, 협상은 실패해도
데드라인(240초)을 전부 소진한다. 그 계정의 `claude` 는 로그인이 만료돼 있어서 매번 만료까지
갔다 — 그리고 실패한 협상은 캐시되지 않으므로 **재기동할 때마다** 4분이 반복됐다.

## 무엇을 잠그는가

협상이 **아직 끝나지 않은 상태에서** 러너가 이미 (a) 하트비트를 띄웠고 (b) 질문 대기에
들어가 있어야 한다. 협상이 정하는 것은 «웹 선택기에 무엇을 띄울까» 이고, 그것은 나중에
도착해도 된다 — 표 안 런타임은 호출 형태를 이미 알기 때문이다.
"""
from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"

#: 라이브에서 관측된 침묵 길이(초). 이 테스트는 그만큼 기다리지 않는다 — 협상을 붙잡아 두고
#: 「그 사이에 대기까지 갔는가」만 본다.
_LIVE_SILENCE_SEC = 240


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_startup", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def ba():
    return _load_runner()


class _StopWaiting(Exception):
    """대기 루프에 도달했다 — 여기서 `main()` 을 끝낸다(무한 루프이므로)."""


def _run_main_until_wait(ba, monkeypatch, tmp_path, caps_gate: threading.Event):
    """`main()` 을 띄우고, **협상을 붙잡은 채** 대기 루프 도달 여부를 관측한다.

    Returns:
        `(timeline, reached_wait, done)` — `timeline` 은 사건 순서, `reached_wait` 는
        대기 루프 도달 신호, `done` 은 `main()` 종료 신호.
    """
    timeline: list[str] = []
    reached_wait = threading.Event()
    done = threading.Event()

    def _fake_resolve_caps(*_a, **_k):
        timeline.append("caps:start")
        # 라이브의 240초 침묵을 **시간이 아니라 게이트로** 재현한다(테스트가 4분을 기다리지
        # 않으면서 같은 인과를 만든다).
        caps_gate.wait(timeout=30)
        timeline.append("caps:done")
        return [], {}

    def _fake_start_heartbeat(_api, _stop, _runtimes=None, **_k):
        timeline.append("heartbeat")
        return threading.Thread(target=lambda: None)

    def _fake_call(_self, tool, args=None, timeout=None):  # noqa: ANN001
        if tool == "list_open_requests":
            return {}                      # 연결 확인 통과 (`_http`·`_failed` 없음)
        if tool == "wait_for_request":
            timeline.append("wait")
            reached_wait.set()
            raise _StopWaiting
        return {}

    monkeypatch.setattr(ba.Api, "call", _fake_call)
    monkeypatch.setattr(ba, "resolve_caps", _fake_resolve_caps)
    monkeypatch.setattr(ba, "start_heartbeat", _fake_start_heartbeat)
    monkeypatch.setattr(ba, "_ensure_strict_mcp_supported", lambda *a, **k: False)
    monkeypatch.setattr(ba, "_which_ai", lambda name: "/fake/claude")
    monkeypatch.setattr(ba, "_CONF_DIR", str(tmp_path / "conf"))
    monkeypatch.setattr(ba, "_CONF_PATH", str(tmp_path / "conf" / "config.json"))
    monkeypatch.setattr(sys, "argv",
                        ["bridge_agent.py", "--base", "https://example.invalid",
                         "--token", "mat_test"])

    def _main() -> None:
        try:
            ba.main()
        except _StopWaiting:
            pass
        finally:
            done.set()

    threading.Thread(target=_main, daemon=True).start()
    return timeline, reached_wait, done


def test_runner_takes_questions_while_negotiation_is_still_running(ba, monkeypatch, tmp_path):
    """협상이 **끝나기 전에** 하트비트와 질문 대기가 이미 살아 있다.

    이것이 실패하면 라이브 증상이 그대로 돌아온다 — 「연결됐다는데 답도 로그도 없다」.
    """
    gate = threading.Event()          # 닫아 둔다 = 협상이 아직 안 끝났다
    timeline, reached_wait, done = _run_main_until_wait(ba, monkeypatch, tmp_path, gate)

    assert reached_wait.wait(timeout=20), (
        "협상이 끝나기 전에는 질문 대기에 도달하지 못했다 — "
        f"기동이 협상에 막혀 있다(라이브: {_LIVE_SILENCE_SEC}초 침묵). timeline={timeline}"
    )
    assert "heartbeat" in timeline, f"하트비트가 협상 뒤로 밀렸다: {timeline}"
    assert "caps:done" not in timeline, (
        f"협상이 이미 끝나 버려 이 테스트가 아무것도 증명하지 못한다: {timeline}")
    assert timeline.index("heartbeat") < timeline.index("wait")

    gate.set()
    assert done.wait(timeout=20)


def test_negotiation_still_runs_and_updates_the_reported_list(ba, monkeypatch, tmp_path):
    """뒤로 미룬 협상이 **실제로 수행되고**, 그 결과가 신고 목록에 제자리로 반영된다.

    미루기만 하고 반영하지 않으면 웹 선택기가 영영 비어 있다 — 고치려던 것과 다른 결함을
    새로 만드는 셈이다. `start_heartbeat` 이 받은 **바로 그 리스트 객체**가 갱신돼야 한다
    (새 리스트를 대입하면 하트비트는 옛 객체를 계속 싣는다).
    """
    gate = threading.Event()
    seen: dict = {}

    def _fake_start_heartbeat(_api, _stop, runtimes=None, **_k):
        seen["runtimes"] = runtimes       # 하트비트가 매 tick 읽는 그 객체
        return threading.Thread(target=lambda: None)

    def _fake_resolve_caps(*_a, **_k):
        gate.wait(timeout=30)
        return ([{"name": "claude", "label": "Claude",
                  "models": [{"value": "opus", "label": "Opus"}], "efforts": []}],
                {"claude": {"source": "probe", "models": [{"value": "opus"}]}})

    def _fake_call(_self, tool, args=None, timeout=None):  # noqa: ANN001
        if tool == "wait_for_request":
            gate.set()                    # 대기까지 왔으니 이제 협상을 풀어 준다
            raise _StopWaiting
        return {}

    monkeypatch.setattr(ba.Api, "call", _fake_call)
    monkeypatch.setattr(ba, "resolve_caps", _fake_resolve_caps)
    monkeypatch.setattr(ba, "start_heartbeat", _fake_start_heartbeat)
    monkeypatch.setattr(ba, "_ensure_strict_mcp_supported", lambda *a, **k: False)
    monkeypatch.setattr(ba, "_which_ai", lambda name: "/fake/claude")
    monkeypatch.setattr(ba, "_CONF_DIR", str(tmp_path / "conf"))
    monkeypatch.setattr(ba, "_CONF_PATH", str(tmp_path / "conf" / "config.json"))
    monkeypatch.setattr(sys, "argv",
                        ["bridge_agent.py", "--base", "https://example.invalid",
                         "--token", "mat_test"])

    done = threading.Event()

    def _main() -> None:
        try:
            ba.main()
        except _StopWaiting:
            pass
        finally:
            done.set()

    threading.Thread(target=_main, daemon=True).start()
    assert done.wait(timeout=20)

    reported = seen.get("runtimes")
    assert reported is not None, "하트비트가 신고 목록을 받지 못했다"
    for _ in range(100):                  # 배경 협상이 반영될 때까지
        if reported:
            break
        threading.Event().wait(0.05)
    assert [r["name"] for r in reported] == ["claude"], (
        f"협상 결과가 하트비트가 든 그 리스트에 반영되지 않았다: {reported}")
