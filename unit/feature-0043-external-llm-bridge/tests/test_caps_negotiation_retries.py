"""능력 협상이 **한 번 실패하면 영영 끝**이던 것 (사용자 제보 2026-09-07).

## 이 파일이 고정하는 라이브 결함

사용자 신고: *"클라이언트에서, AI가 연결되었음에도 모델 목록이 나타나지 않고 있습니다."*

그 시점 라이브 실측 (계정 `admin`, 러너 `--ai codex`, build `ee0453d7c445`):

    14:02:17  run.start / run.ready            ← 연결·질문 처리는 정상
    14:02:17  쓸 수 있는 모델·추론 수준을 물어보는 중… (codex)
    14:03:36  codex: 사유 — 응답에 모델 목록이 없습니다.
    14:03:36  고를 수 있는 AI 를 찾지 못했습니다 — 웹 선택기는 표시되지 않습니다.
    (이후 9분간 하트비트는 계속, `RunnerCapabilities` 는 `[]` 로 고정)

즉 **연결은 살아 있는데 목록만 영영 비어 있는** 상태다. 서버가 그 자리에 내보내는 문구는
「연결된 본인 AI 에게 쓸 수 있는 모델을 확인하는 중입니다」인데, 실제로는 아무것도 다시
확인하지 않았다 — 협상이 기동 시 **1회**뿐이었기 때문이다.

관측된 실패 사유는 다시 물으면 풀리는 종류가 흔하다: `OAuth access token has expired`
(그 CLI 에 로그인하면 풀린다) · `TimeoutExpired`(그때 그 머신이 느렸다) · 그리고
`caps.py` 가 이미 기록한 「codex 는 같은 조건에서 성공과 실패를 오간다」.

## 무엇을 잠그는가

1. 협상이 빈손이면 **다시 묻는다** — 목록이 도착하면 하트비트가 든 그 리스트에 반영된다.
2. 목록을 얻으면 **멈춘다** — 성공한 뒤에도 계속 물으면 그 AI 의 토큰을 이유 없이 태운다.
3. 러너가 내려가면 **멈춘다** — 대기 중이라도 즉시. (`time.sleep` 이면 최대 15분을 붙잡는다.)
4. 재시도는 **아직 못 얻은 것만** 묻는다 — 앞 회차에 성공한 런타임을 다시 묻지 않는다.
"""
from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"

#: 신고 항목은 **항상 `source` 를 갖는다** — `_assemble` 이 provenance 게이트를 통과한 값만
#: 내보내며 그 자리에 출처를 싣는다. 대역이 그 필드를 빠뜨리면 재시도 판정이 「확인되지
#: 않음」으로 읽어 이 파일이 대상의 계약이 아니라 자기 누락을 시험하게 된다.
_LIST = [{"runtime": "codex", "label": "Codex", "source": "probe",
          "models": [{"value": "gpt-5-codex", "label": "GPT-5 Codex"}], "efforts": []}]
_DETAIL = {"codex": {"source": "probe", "argv": ["codex", "exec", "{prompt}"],
                     "models": [{"value": "gpt-5-codex", "label": "GPT-5 Codex"}],
                     "efforts": [], "model": ["-m", "{model}"], "effort": None}}


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_caps_retry", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def ba():
    return _load_runner()


class _StopWaiting(Exception):
    """대기 루프에 도달했다 — 여기서 `main()` 을 끝낸다(무한 루프이므로)."""


class _Harness:
    """`main()` 을 띄우고 협상 호출을 세는 관측대.

    ⚠ 재시도 간격은 **테스트에서 줄인다**. 실제 값(60초~15분)을 기다리면 이 파일이 게이트가
      아니라 타이머가 된다 — 그러나 «간격이 있다» 는 사실 자체는 줄여도 남는다(대기 뒤에
      다시 호출된다는 인과를 본다).
    """

    def __init__(self) -> None:
        self.calls = 0
        self.cached_seen: list = []
        self.runtimes = None
        self.stop = None
        self.done = threading.Event()
        self.reached_wait = threading.Event()


def _spawn(ba, monkeypatch, tmp_path, results, *, backoff=(0.05,), ceiling=0.05,
           asked=("codex",)) -> _Harness:
    """`results` 는 회차별 `resolve_caps` 반환값 목록(모자라면 마지막 값을 반복).

    `asked` 는 대역이 「이번 회차에 물어본 런타임」으로 신고할 이름들이다 — 재시도 판정의
    모수이고, 대역이 그것을 채우지 않으면 이 하네스가 **대상의 계약을 따라가지 않게 된다**
    (실제 `resolve_caps` 는 `asked_out` 을 채운다).
    """
    h = _Harness()

    def _fake_resolve_caps(_only, cached, _refresh, baseline=None, on_settled=None,
                           asked_out=None):
        h.cached_seen.append(None if cached is None else sorted(cached))
        idx = min(h.calls, len(results) - 1)
        h.calls += 1
        got, detail = results[idx]
        if asked_out is not None:
            asked_out[:] = list(asked)
        if on_settled is not None:
            on_settled(list(got), dict(detail))
        return list(got), dict(detail)

    def _fake_start_heartbeat(_api, _stop, runtimes=None, **_k):
        h.runtimes = runtimes
        h.stop = _stop
        ready = _k.get("baseline_ready")
        if ready is not None:
            ready.set()
        return threading.Thread(target=lambda: None)

    def _fake_call(_self, tool, args=None, timeout=None):  # noqa: ANN001
        if tool == "wait_for_request":
            h.reached_wait.set()
            raise _StopWaiting
        return {}

    monkeypatch.setattr(ba.Api, "call", _fake_call)
    monkeypatch.setattr(ba, "resolve_caps", _fake_resolve_caps)
    monkeypatch.setattr(ba, "start_heartbeat", _fake_start_heartbeat)
    monkeypatch.setattr(ba, "_ensure_strict_mcp_supported", lambda *a, **k: False)
    monkeypatch.setattr(ba, "_which_ai", lambda name: "/fake/codex")
    # 생존 확인은 실제 CLI 를 부른다 — 이 파일의 관심사가 아니므로 막아 둔다.
    monkeypatch.setattr(ba, "confirm_ai_or_report", lambda *a, **k: None)
    monkeypatch.setattr(ba, "_CAPS_RETRY_BACKOFF_SEC", tuple(backoff))
    monkeypatch.setattr(ba, "_CAPS_RETRY_CEILING_SEC", ceiling)
    # ⚠ 천장은 **둘**이다 (2026-09-07). 「보여줄 목록이 이미 있을 때」의 천장(1시간)을 함께
    #   줄이지 않으면, 원장 폴백처럼 `runtimes` 가 차 있는 시나리오에서 하네스가 그 1시간을
    #   기다리게 되어 «재시도가 멎었다» 로 오진한다 — 대역이 대상의 축을 따라가야 한다.
    monkeypatch.setattr(ba, "_CAPS_RETRY_CEILING_SHOWING_SEC", ceiling)
    monkeypatch.setattr(ba, "_CONF_DIR", str(tmp_path / "conf"))
    monkeypatch.setattr(ba, "_CONF_PATH", str(tmp_path / "conf" / "config.json"))
    monkeypatch.setattr(sys, "argv",
                        ["bridge_agent.py", "--base", "https://example.invalid",
                         "--token", "mat_test", "--ai", "codex"])

    def _main() -> None:
        try:
            ba.main()
        except _StopWaiting:
            pass
        finally:
            h.done.set()

    threading.Thread(target=_main, daemon=True).start()
    assert h.done.wait(timeout=20), "main() 이 대기 루프에 도달하지 못했다"
    return h


def _await(pred, timeout=10.0) -> bool:
    ev = threading.Event()
    waited = 0.0
    while waited < timeout:
        if pred():
            return True
        ev.wait(0.05)
        waited += 0.05
    return pred()


def test_empty_negotiation_is_retried_until_a_list_arrives(ba, monkeypatch, tmp_path):
    """⭐ 정본 — 빈손 협상은 **다시 묻는다**. 도착한 목록은 하트비트가 든 그 리스트에 실린다.

    이것이 실패하면 라이브 증상이 그대로다: 연결은 살아 있는데 웹 선택기만 영영 비어 있고,
    화면은 「확인하는 중」이라고 말한다.
    """
    h = _spawn(ba, monkeypatch, tmp_path,
               [([], {}), ([], {}), (_LIST, _DETAIL)])

    assert _await(lambda: bool(h.runtimes)), (
        f"빈손 협상 뒤 다시 묻지 않았다 — 목록이 영영 오지 않는다 (호출 {h.calls}회)")
    assert [r["runtime"] for r in h.runtimes] == ["codex"]
    assert h.calls >= 3, f"재시도가 두 번 미만이다: {h.calls}회"


def test_retry_stops_once_the_list_is_reported(ba, monkeypatch, tmp_path):
    """목록을 얻으면 **멈춘다** — 성공 뒤에도 계속 물으면 그 AI 의 토큰만 태운다."""
    h = _spawn(ba, monkeypatch, tmp_path, [(_LIST, _DETAIL)])

    assert _await(lambda: bool(h.runtimes))
    threading.Event().wait(0.6)          # 간격 0.05초 × 여러 회분을 지나 보낸다
    assert h.calls == 1, f"첫 회차에 성공했는데 계속 물었다: {h.calls}회"


def test_retry_stops_when_the_runner_goes_down(ba, monkeypatch, tmp_path):
    """러너가 내려가면 **대기 중이라도** 멈춘다.

    간격을 길게 준 회차에서 `stop` 을 세운다 — `time.sleep` 이었다면 그 간격이 끝날 때까지
    붙잡혀 종료·자기갱신이 그만큼 늦어진다(`Event.wait` 여야 즉시 깨어난다).
    """
    h = _spawn(ba, monkeypatch, tmp_path, [([], {})], backoff=(3600.0,), ceiling=3600.0)

    assert _await(lambda: h.calls >= 1)
    assert h.stop is not None, "하트비트 대역이 stop 이벤트를 받지 못했다"
    h.stop.set()
    threading.Event().wait(0.3)
    frozen = h.calls
    threading.Event().wait(0.5)
    assert h.calls == frozen, f"내려가는 중에도 계속 물었다: {frozen} → {h.calls}"


def test_retry_does_not_re_ask_what_already_succeeded(ba, monkeypatch, tmp_path):
    """재시도는 **아직 못 얻은 것만** 묻는다 — 앞 회차 성공분을 `cached` 로 넘긴다.

    넘기지 않으면 회차마다 성공한 런타임을 다시 물어 토큰을 태우고, 흔들리는 새 답이 이미
    안정된 목록을 덮을 수도 있다(«실행할 때마다 목록이 다르다» 제보의 재현 경로).
    """
    partial = ({"claude": {"source": "probe", "models": [{"value": "opus"}], "efforts": [],
                           "argv": ["claude", "-p", "{prompt}"], "model": ["--model", "{model}"],
                           "effort": None}})
    # 1회차: 신고 목록은 비었지만 상세는 얻었다(그 런타임의 모델 축이 비어 신고에서 빠진 경우).
    h = _spawn(ba, monkeypatch, tmp_path, [([], partial), (_LIST, _DETAIL)])

    assert _await(lambda: h.calls >= 2)
    assert h.cached_seen[0] in (None, []), \
        f"첫 회차가 이미 무언가를 캐시로 들고 갔다: {h.cached_seen[0]}"
    assert h.cached_seen[1] == ["claude"], \
        f"재시도가 앞 회차의 성공분을 넘기지 않았다: {h.cached_seen[1]}"


_BASELINE_ONLY = [{"runtime": "codex", "label": "Codex", "source": "baseline",
                   "models": [{"value": "gpt-5-codex", "label": "GPT-5 Codex"}], "efforts": []}]


def test_a_baseline_only_list_still_counts_as_not_yet(ba, monkeypatch, tmp_path):
    """⭐ 원장 폴백뿐인 목록은 **«얻었다» 가 아니다** — 실조회를 계속 시도한다.

    폴백은 화면을 비우지 않으려고 얹은 임시 표시다(사용자 결정 2026-09-07). 그것을 성공으로
    세면 그 세션은 확인된 목록을 **영영 갖지 못한다** — 폴백을 도입하면서 재시도를 죽이는
    형태이고, 두 수정이 서로를 무력화한다.
    """
    h = _spawn(ba, monkeypatch, tmp_path,
               [(_BASELINE_ONLY, {}), (_BASELINE_ONLY, {}), (_LIST, _DETAIL)])

    assert _await(lambda: bool(h.runtimes) and h.runtimes[0].get("source") != "baseline"), (
        f"원장 폴백에서 멈춰 실조회를 다시 시도하지 않았다 (호출 {h.calls}회)")
    assert h.calls >= 3


def test_a_runtime_that_never_answers_keeps_retrying_beside_one_that_did(ba, monkeypatch,
                                                                        tmp_path):
    """⭐ 회귀 — **한 런타임이 성공해도** 못 얻은 런타임의 재시도는 멎지 않는다.

    codex 적대리뷰 P2-1(2026-09-07): 판정이 「신고가 비었는가」였을 때, claude 가 답하고
    codex 가 못 답하는 조합에서 codex 의 빈 목록이 **영구화**됐다. 이 프로젝트의 라이브가
    정확히 그 조합이다(같은 머신에 claude·codex 가 함께 있다).
    """
    only_claude = [{"runtime": "claude", "label": "Claude Code", "source": "probe",
                    "models": [{"value": "opus", "label": "Opus"}], "efforts": []}]
    both = only_claude + [{"runtime": "codex", "label": "Codex", "source": "catalog",
                           "models": [{"value": "gpt-5.6-sol", "label": "Sol"}],
                           "efforts": []}]
    h = _spawn(ba, monkeypatch, tmp_path,
               [(only_claude, {}), (only_claude, {}), (both, {})],
               asked=("claude", "codex"))

    assert _await(lambda: h.runtimes is not None and len(h.runtimes) == 2), (
        f"claude 가 답하자 codex 의 재시도가 멎었다 (호출 {h.calls}회)")
    assert h.calls >= 3


def test_a_stale_round_cannot_overwrite_a_newer_list(ba, monkeypatch, tmp_path):
    """⭐ 앞 회차의 지각 스레드가 **지금 목록을 되덮지 않는다** (적대리뷰 P2, 2026-09-07).

    `resolve_caps` 는 데드라인이 지나면 `t.join(...)` 을 포기하고 반환하는데, 남은 질의
    스레드는 살아 있다가 **다음 회차 중에** `on_settled` 를 부른다. 종전엔 협상이 1회뿐이라
    이 겹침 자체가 없었다 — 재시도가 그 창을 새로 열었다. 되덮이면 방금 성공한 목록이 앞
    회차의 짧은 부분 목록으로 후퇴하고, 사용자는 이유 없이 목록이 줄어드는 것을 본다.
    """
    captured: dict = {}

    def _fake_resolve_caps(_only, cached, _refresh, baseline=None, on_settled=None,
                           asked_out=None):
        captured.setdefault("cbs", []).append(on_settled)
        if asked_out is not None:
            asked_out[:] = ["codex"]
        idx = len(captured["cbs"]) - 1
        got, detail = ([], {}) if idx == 0 else (_LIST, _DETAIL)
        if on_settled is not None:
            on_settled(list(got), dict(detail))
        return list(got), dict(detail)

    h = _Harness()

    def _fake_start_heartbeat(_api, _stop, runtimes=None, **_k):
        h.runtimes = runtimes
        h.stop = _stop
        ready = _k.get("baseline_ready")
        if ready is not None:
            ready.set()
        return threading.Thread(target=lambda: None)

    def _fake_call(_self, tool, args=None, timeout=None):  # noqa: ANN001
        if tool == "wait_for_request":
            raise _StopWaiting
        return {}

    monkeypatch.setattr(ba.Api, "call", _fake_call)
    monkeypatch.setattr(ba, "resolve_caps", _fake_resolve_caps)
    monkeypatch.setattr(ba, "start_heartbeat", _fake_start_heartbeat)
    monkeypatch.setattr(ba, "_ensure_strict_mcp_supported", lambda *a, **k: False)
    monkeypatch.setattr(ba, "_which_ai", lambda name: "/fake/codex")
    monkeypatch.setattr(ba, "confirm_ai_or_report", lambda *a, **k: None)
    monkeypatch.setattr(ba, "_CAPS_RETRY_BACKOFF_SEC", (0.05,))
    monkeypatch.setattr(ba, "_CAPS_RETRY_CEILING_SEC", 0.05)
    monkeypatch.setattr(ba, "_CONF_DIR", str(tmp_path / "conf"))
    monkeypatch.setattr(ba, "_CONF_PATH", str(tmp_path / "conf" / "config.json"))
    monkeypatch.setattr(sys, "argv",
                        ["bridge_agent.py", "--base", "https://example.invalid",
                         "--token", "mat_test", "--ai", "codex"])
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
    assert _await(lambda: bool(h.runtimes)), "두 번째 회차가 목록을 싣지 못했다"
    assert len(captured["cbs"]) >= 2, "회차가 겹치는 상황을 만들지 못했다"

    # 1회차의 지각 스레드가 **지금** 빈 목록을 게시하려 한다 — 버려져야 한다.
    captured["cbs"][0]([], {})
    assert [r["runtime"] for r in h.runtimes] == ["codex"], (
        "앞 회차의 지각 게시가 지금 목록을 되덮었다 — 목록이 이유 없이 사라진다")
