"""「아직 확인되지 않았다」를 **정상으로 말하지 않는다** (TASK-20260903T200000).

## 이 파일이 고정하는 라이브 결함

사용자 지적(2026-09-03): *"연결되지 않은 상황이 정상 연결되었다고 거짓으로 출력되는 부분을
수정하는 작업입니다. claude 인증 상태는 현상일 뿐입니다."*

직전 cycle(TASK-20260903T180000)은 「**관측된** 불가」를 화면에 올렸다 — 협상이 실패해
`note_ai_unusable` 이 불린 경우다. 남아 있던 거짓은 그 **앞** 구간이었다:

    러너 기동 → 원장 초기값 `True`(fail-open) → 하트비트 `ai_ready=1`
             → 서버 `RunnerAiReady=1` → 화면 「대기 중」(정상)

이 구간에 AI 가 실은 응답 불가여도 사용자는 그 사실을 협상이 끝날 때까지(실측 ~200초)
듣지 못했다. 그리고 **캐시된 caps 가 있으면 협상은 아예 돌지 않아**(`ask` 가 빈다) 관측
기회조차 없었다 — 사용자 라이브가 정확히 그 경로였다(config.json 에 지난 성공의 caps +
만료된 claude OAuth).

## 무엇을 잠그는가

1. 원장은 3상태다 — `None`(미확인) · `True`(답을 받아냈다) · `False`(못 쓴다는 관측).
2. **표시 축**(`ai_health` → 하트비트)은 `None` 을 정상으로 말하지 않는다.
3. **게이트 축**(`ai_blocked`)은 `None` 을 막지 않는다 — 접으면 첫 질문이 전부 죽는다.
4. 「모른다」가 **영구 상태로 남지 않는다** — 협상이 아무것도 묻지 않아도 짧은 생존 확인
   1회가 반드시 `True`/`False` 중 하나로 떨어뜨린다.
"""
from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
_AGENT_SRC = _UNIT / "feature-0043-external-llm-bridge" / "src" / "agent"

#: 사용자가 말한 체감 상한. *"사실, 10초 이상 소요되는 부분도 길다고 체감됩니다."*
#: 생존 확인은 화면이 「확인 중」에 머무는 시간이므로 협상 데드라인(240초)과 같은 자리에
#: 둘 수 없다. 여유를 두되 **자릿수가 다르다**는 것을 잠근다.
_FELT_LONG_SEC = 60


def _load():
    spec = importlib.util.spec_from_file_location("_runner_unknown", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    m = _load()
    m.reset_ai_health()
    m.reset_health_recheck()
    return m


# ── 1. 3상태 원장 ────────────────────────────────────────────────────────────

def test_probing_marks_unknown_not_ready(mod):
    """협상 시작은 「확인 중」이다 — 정상이 아니다."""
    mod.note_ai_outcome(True)
    assert mod.ai_health()[0] is True, "전제: 한 번 확인된 상태"
    mod.note_ai_probing("확인하는 중입니다.")
    assert mod.ai_health()[0] is None, "재협상에 들어갔는데 직전 판정을 정상으로 유지했다"


def test_probing_does_not_launder_an_observed_failure(mod):
    """⭐ 「확인 중」이 **관측된 불가를 세탁하지 않는다**.

    이것이 없으면 재협상마다 「답할 수 없음」이 「확인 중」으로 바뀐다 — 사용자는 매번
    「곧 정상이 될 것」이라는 인상만 받고, 실제로 무엇을 해야 하는지(재로그인)는 영영
    듣지 못한다. 조치 «방향»이 역전되는 부류다.
    """
    mod.note_ai_unusable("이 컴퓨터의 claude 가 응답하지 않습니다 — 401")
    mod.note_ai_probing("확인하는 중입니다.")
    ok, why = mod.ai_health()
    assert ok is False, "관측된 불가가 「확인 중」으로 세탁됐다"
    assert "401" in why, "세탁되며 사유까지 사라졌다 — 사용자는 고칠 방법을 잃는다"


def test_gate_and_display_are_separate_axes(mod):
    """⚠ 같은 원장을 두 소비자가 **다르게** 읽는다."""
    assert mod.ai_health()[0] is None, "표시: 정상이라고 말하지 않는다"
    assert mod.ai_blocked()[0] is False, "게이트: 그러나 막지 않는다"
    mod.note_ai_unusable("응답 없음")
    assert mod.ai_health()[0] is False
    assert mod.ai_blocked()[0] is True, "관측된 불가는 게이트도 막아야 한다"


def test_reset_starts_from_production_initial_state(mod):
    """테스트 초기화가 **프로덕션 기동과 같은** 값에서 출발한다.

    여기가 `True` 면 모든 테스트가 「이미 확인된」 상태에서 시작해, 방금 고친 결함을
    어떤 테스트도 재현할 수 없다(테스트가 결함을 감추는 부류).
    """
    mod.note_ai_outcome(True)
    mod.reset_ai_health()
    assert mod.ai_health() == (None, "")


# ── 2. 생존 확인 — 「모른다」를 떨어뜨리는 장치 ──────────────────────────────

def test_liveness_true_when_the_cli_answers(mod, monkeypatch):
    monkeypatch.setattr(mod, "_ask_json", lambda *a, **k: {"alive": True})
    ok, why = mod.verify_ai_liveness("claude", ["claude", "-p"])
    assert ok is True and why == ""


def test_liveness_false_carries_the_reason(mod, monkeypatch):
    """실패는 **사유와 함께** 돌아온다 — 사유 없는 실패는 사용자가 고칠 수 없다."""
    def _fail(_argv, _prompt, _timeout, reason_out=None):
        if reason_out is not None:
            reason_out["reason"] = "OAuth access token has expired."
        return None

    monkeypatch.setattr(mod, "_ask_json", _fail)
    ok, why = mod.verify_ai_liveness("claude", ["claude", "-p"])
    assert ok is False
    assert "claude" in why, f"어느 런타임인지 없다: {why!r}"
    assert "expired" in why, f"실제 사유가 유실됐다: {why!r}"


def test_confirm_settles_the_ledger_both_ways(mod, monkeypatch):
    """⭐ 확인 결과가 **원장에 반영된다** — 여기가 화면이 갈리는 지점이다.

    계산만 맞고 이 배선이 없으면 관측은 했는데 사용자에게 도달하지 않는다(이 저장소가
    반복해 만든 부류: 「지식이 화면에 도달하지 않는 배선 결함」).
    """
    monkeypatch.setattr(mod, "_ask_json", lambda *a, **k: {"alive": True})
    assert mod.confirm_ai_or_report("claude", ["claude", "-p"]) is True
    assert mod.ai_health()[0] is True, "성공했는데 원장이 「모른다」에 머물렀다"

    mod.reset_ai_health()
    monkeypatch.setattr(mod, "_ask_json", lambda *a, **k: None)
    assert mod.confirm_ai_or_report("claude", ["claude", "-p"]) is False
    ok, why = mod.ai_health()
    assert ok is False, "실패했는데 원장이 「모른다」에 머물렀다 — 화면은 「확인 중」에 굳는다"
    assert "claude" in why


def test_liveness_timeout_is_an_order_of_magnitude_below_negotiation(mod):
    """사용자 체감 — 「확인 중」에 머무는 시간이 협상 데드라인이면 안 된다.

    사용자 지적(2026-09-03): *"150는 너무 깁니다. (사실, 10초 이상 소요되는 부분도 길다고
    체감됩니다.)"*
    """
    assert mod._LIVENESS_TIMEOUT_SEC <= _FELT_LONG_SEC, (
        f"생존 확인 상한이 {mod._LIVENESS_TIMEOUT_SEC}초 — 그 시간이 곧 화면이 「확인 중」에"
        " 머무는 시간이다")
    assert mod._LIVENESS_TIMEOUT_SEC < mod._CAPS_PROBE_TIMEOUT_SEC, (
        "생존 확인이 협상만큼 오래 걸린다 — 그러면 협상을 건너뛴 의미가 없다")


# ── 3. 배선 — 협상 경로가 「모른다」를 남기지 않는가 ─────────────────────────
#
# ⚠ 위 §2 는 함수의 «계산»만 본다. 그 함수를 부르는 자리가 사라지면 전부 통과하면서
#   화면은 「확인 중」에 영구히 굳는다. 그래서 **러너를 실제로 띄워** 본다.

class _StopWaiting(Exception):
    """대기 루프 도달 — 무한 루프이므로 여기서 `main()` 을 끝낸다."""


def _run_runner(mod, monkeypatch, tmp_path, ask_json, resolve_caps=None):
    """`main()` 을 띄워 **협상까지 끝낸 뒤** 원장 상태를 관측한다.

    협상은 캐시가 없어도 `_ask_json` 을 우리 것으로 바꿔 두므로 실제 CLI 를 부르지 않는다.
    """
    reached = threading.Event()

    def _fake_call(_self, tool, args=None, timeout=None):  # noqa: ANN001
        if tool == "wait_for_request":
            reached.set()
            raise _StopWaiting
        return {}

    monkeypatch.setattr(mod.Api, "call", _fake_call)
    monkeypatch.setattr(mod.Api, "heartbeat", lambda *a, **k: {})
    monkeypatch.setattr(mod, "_ensure_strict_mcp_supported", lambda *a, **k: False)
    monkeypatch.setattr(mod, "_which_ai", lambda n: "/fake/claude" if n == "claude" else None)
    monkeypatch.setattr(mod, "_ask_json", ask_json)
    if resolve_caps is not None:
        monkeypatch.setattr(mod, "resolve_caps", resolve_caps)
    monkeypatch.setattr(mod, "_CONF_DIR", str(tmp_path / "conf"))
    monkeypatch.setattr(mod, "_CONF_PATH", str(tmp_path / "conf" / "config.json"))
    monkeypatch.setattr(sys, "argv",
                        ["bridge_agent.py", "--base", "https://example.invalid",
                         "--token", "mat_test"])
    done = threading.Event()

    def _main() -> None:
        try:
            mod.main()
        except _StopWaiting:
            pass
        except BaseException:  # noqa: BLE001  (기동 실패도 관측 대상이다)
            pass
        finally:
            done.set()

    t = threading.Thread(target=_main, daemon=True)
    t.start()
    reached.wait(timeout=30)
    return reached, done


def test_runner_never_leaves_the_state_unknown_after_startup(mod, monkeypatch, tmp_path):
    """⭐ 기동이 끝나면 원장은 **`None` 이 아니다** — 「확인 중」이 영구 상태가 되지 않는다.

    캐시된 caps 로 협상이 아무것도 묻지 않는 경로가 라이브의 그 경로였다. 이 단정이 없으면
    화면이 「대기 중」(종전 거짓) 대신 「확인 중」(새로운 무용)으로 굳는다.
    """
    monkeypatch.setattr(mod, "_LIVENESS_TIMEOUT_SEC", 2.0)
    reached, _done = _run_runner(mod, monkeypatch, tmp_path, lambda *a, **k: None)
    assert reached.is_set(), "질문 대기에 도달하지 못했다 — 기동 자체가 막혔다"

    for _ in range(120):                      # 협상은 배경 스레드다 — 결말을 기다린다
        if mod.ai_health()[0] is not None:
            break
        threading.Event().wait(0.25)
    ok, why = mod.ai_health()
    assert ok is not None, (
        "기동이 끝났는데 원장이 「모른다」에 남았다 — 화면은 「확인 중」에 영구히 굳는다")
    assert ok is False and why, f"응답하지 않는 AI 인데 사유 없이 판정됐다: {ok!r}/{why!r}"


def test_renegotiation_marks_unknown_while_it_runs(mod, monkeypatch, tmp_path):
    """⭐ **협상이 도는 동안** 원장은 「모른다」다 — 행위로 잠근다.

    이미 `True` 로 확인된 러너가 재협상에 들어가면 직전 판정은 낡은 것이다. 그때도 화면이
    「대기 중」을 유지하면, 그 구간에 AI 가 응답 불가로 바뀌어도 사용자는 종전과 똑같이
    침묵을 겪는다 — 같은 거짓의 작은 판본이다.

    ⚠ 이 테스트는 **소스 문자열 단정을 대체한다**. 종전 형태(`"note_ai_probing(" in body`)는
      호출부가 두 곳이라 **협상 경로 하나를 지워도 통과했다**(뮤테이션 M6 실측 생존) —
      이 저장소가 반복해 만든 「죽은 가드」를 테스트 쪽에서 재현한 셈이다. 그래서 협상이
      실제로 시작된 **그 순간의 원장 값**을 본다.
    """
    mod.note_ai_outcome(True, runtime="claude")
    assert mod.ai_health()[0] is True, "전제: 이미 확인된 러너"

    seen: dict = {}

    def _resolve(*_a, **_k):
        # 협상 본체가 불린 순간의 원장 — `note_ai_probing` 이 그 **앞**에 있어야 None 이다.
        seen["at_negotiation"] = mod.ai_health()[0]
        return [], {}

    monkeypatch.setattr(mod, "_LIVENESS_TIMEOUT_SEC", 2.0)
    reached, _done = _run_runner(mod, monkeypatch, tmp_path,
                                 lambda *a, **k: None, resolve_caps=_resolve)
    assert reached.is_set(), "질문 대기에 도달하지 못했다"
    for _ in range(120):
        if "at_negotiation" in seen:
            break
        threading.Event().wait(0.25)

    assert "at_negotiation" in seen, "협상이 시작되지 않았다 — 이 테스트가 아무것도 증명 못 한다"
    assert seen["at_negotiation"] is None, (
        "협상이 도는 동안 원장이 「정상」이었다 — 그 구간의 화면은 거짓이다"
        f" (관측: {seen['at_negotiation']!r})")


def test_settling_call_is_wired(mod):
    """협상이 끝나면 「모른다」를 떨어뜨리는 호출이 있다.

    ⚠ 이것은 **구조 단정**이다. 행위 쪽은 위 `test_cached_caps_path_still_settles_the_state`
      가 캐시 경로로 잡는다 — 그쪽이 배선의 실증이고, 이 단정은 읽는 사람을 위한 표지다.
    """
    body = (_AGENT_SRC / "lifecycle.py").read_text(encoding="utf-8")
    assert "confirm_ai_or_report(" in body, (
        "협상이 끝나도 「모른다」를 떨어뜨리는 호출이 없다 — 「확인 중」이 굳는다")


def test_all_runtime_initial_values_are_unknown(mod):
    for runtime in ("claude", "codex", "gemini"):
        assert mod.ai_health(runtime) == (None, "")
        assert mod.ai_blocked(runtime) == (False, "")


def test_cached_caps_path_still_settles_the_state(mod, monkeypatch, tmp_path):
    """⭐⭐ **라이브의 그 경로** — 캐시된 caps 로 협상이 아무것도 묻지 않아도 판정이 난다.

    이것이 이 cycle 의 핵심 단정이다. 위 테스트는 캐시가 **없는** 경로를 보는데, 그 경로는
    협상 요약(`note_ai_unusable`)이 이미 직전 cycle 부터 처리했다. 사용자 라이브는 달랐다:

        config.json 에 지난 성공의 caps 있음  →  `ask` 가 빈다  →  아무것도 묻지 않는다
                                              →  관측 기회 없음  →  화면은 「정상」

    캐시가 있으면 협상 요약 루프(`for n in ask`)가 **한 번도 돌지 않는다**. 그래서 여기서
    원장이 `False` 로 떨어졌다면 그것을 한 것은 **생존 확인**뿐이다 — 즉 이 단정이 곧
    `confirm_ai_or_report` 배선의 증거다.
    """
    import json

    conf_dir = tmp_path / "conf"
    conf_dir.mkdir(parents=True, exist_ok=True)
    # 지난 성공이 남긴 캐시. `effort_probed` 를 달아 축 재확정도 일어나지 않게 한다 —
    # 그래야 `ask` 가 완전히 비고, 「아무것도 묻지 않는」 라이브 조건이 재현된다.
    (conf_dir / "config.json").write_text(json.dumps({
        "base": "https://example.invalid",
        "caps": {"claude": {"runtime": "claude", "label": "Claude",
                            "models": [{"value": "opus", "label": "Opus"}],
                            "efforts": [], "effort": None, "effort_probed": True,
                            "source": "probe",
                            "argv": ["claude", "-p", "{prompt}"]}},
    }), encoding="utf-8")

    asked: list = []

    def _ask(argv, prompt, timeout, reason_out=None):
        asked.append(prompt)
        if reason_out is not None:
            reason_out["reason"] = "OAuth access token has expired."
        return None

    monkeypatch.setattr(mod, "_LIVENESS_TIMEOUT_SEC", 2.0)
    reached, _done = _run_runner(mod, monkeypatch, tmp_path, _ask)
    assert reached.is_set(), "질문 대기에 도달하지 못했다 — 기동 자체가 막혔다"

    for _ in range(120):
        if mod.ai_health()[0] is not None:
            break
        threading.Event().wait(0.25)

    ok, why = mod.ai_health()
    assert ok is False, (
        "캐시된 caps 경로에서 원장이 「모른다」에 남았다 — 화면은 「확인 중」에 영구히 굳고,"
        " 종전 코드였다면 「대기 중」(거짓)에 굳었다")
    assert "expired" in why, f"실제 사유가 화면까지 나르지 못했다: {why!r}"
    assert asked, "아무것도 묻지 않았다 — 생존 확인 자체가 불리지 않았다(죽은 배선)"
    assert any("alive" in p for p in asked), (
        f"협상은 건너뛴 것이 맞는데 생존 확인 질문이 없다: {asked!r}")


@pytest.mark.parametrize('answer', [{'error': 'Permission denied'}, {'alive': False}, {'alive': 'true'}, {}])
def test_liveness_rejects_diagnostics_and_false_payloads(mod, monkeypatch, answer):
    monkeypatch.setattr(mod, '_ask_json', lambda *a, **kw: answer)
    assert mod.verify_ai_liveness('codex', ['codex', 'exec'])[0] is False


@pytest.mark.parametrize('alive', [False, True])
def test_catalog_health_recovery_requires_actual_answer(mod, monkeypatch, alive):
    import threading
    done = threading.Event()
    calls = []
    monkeypatch.setattr(mod, 'detect_runtimes', lambda *a, **kw: [{'runtime': 'codex', 'source': 'catalog'}])
    def verify(name, argv):
        calls.append(name)
        done.set()
        return alive, ''
    monkeypatch.setattr(mod, 'verify_ai_liveness', verify)
    mod.note_ai_unusable('unavailable')
    mod.reset_health_recheck()
    assert mod.schedule_health_recheck('codex')
    assert done.wait(2)
    for thread in list(threading.enumerate()):
        if thread.name == 'bridge-health-recheck': thread.join(2)
    assert calls == ['codex']
    assert mod.ai_health()[0] is alive
