"""연결값을 **이 창의 로그인 세션**이 준다 — 그 이음매의 계약 (2026-09-04).

## 왜 바꿨나

종전에는 브리지가 **딥링크로 받아 온 토큰만** 썼다. 그래서 시작 메뉴에서 그냥 켠 앱 창은
토큰이 없어 연결을 걸지 못했고, 사용자는 「여전히 웹 주소에 들어가야 한다」를 겪었다.

토큰을 발급하는 주체는 원래부터 로그인 세션이고 앱 창은 그 세션을 갖고 있다. 그러니 값을
주는 쪽은 패널이 자연스럽다. 딥링크가 실어 온 값은 이제 **폴백**이다.

## 이 파일이 지키는 두 가지

1. **패널이 준 값이 실제로 쓰인다.** 받아 놓고 `self.plan` 을 계속 쓰면 화면은 성공처럼
   보이는데 옛 토큰으로 붙는다 — 「배선은 green, 동작은 0」의 그 형태다.
2. **`base` 는 우리가 아는 그 서버여야 한다.** 그 값으로 CA·러너를 내려받으므로, 여기가
   열려 있으면 XSS 한 번이 「고정(TOFU)을 우회해 남의 서버에서 실행」이 된다.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_UNIT / "src"))

from client import bridge as bridge_mod  # noqa: E402
from client import core  # noqa: E402

BASE = "https://svc.example"
FRESH = ("dqa-connect://start?token=mat_fresh&base=https%3A%2F%2Fsvc.example"
         "&ca_sha256=aa11&agent_sha256=bb22")


@pytest.fixture()
def spy(monkeypatch, tmp_path):
    """연결 절차의 바깥(네트워크·프로세스)을 막고 **어떤 plan 이 흘렀는지** 기록한다."""
    seen: dict = {"plans": []}

    def _ca(plan):
        seen["plans"].append(("ca", plan))
        return tmp_path / "rootCA.crt"

    def _runner(plan, ca):
        seen["plans"].append(("runner", plan))
        return tmp_path / "bridge_agent.py"

    def _check(plan, runner, ca, st):
        seen["plans"].append(("check", plan))
        return 0, ""

    def _spawn(plan, runner, ca, st):
        seen["plans"].append(("spawn", plan))
        return None

    monkeypatch.setattr(core, "install_ca", _ca)
    monkeypatch.setattr(core, "install_runner", _runner)
    monkeypatch.setattr(core, "check_connection", _check)
    monkeypatch.setattr(core, "spawn_runner", _spawn)
    monkeypatch.setattr(core, "pin_server",
                        lambda home, base: seen.setdefault("pinned", base))
    return seen


def _bridge(tmp_path, token: str, notify=lambda title, body: None):
    plan = core.ConnectPlan(base=BASE, token=token, home=tmp_path)
    return bridge_mod.Bridge(plan, notify=notify)


# ── 1. 어떤 값이 실제로 흐르는가 ──────────────────────────────────────────────────

def test_the_panels_token_is_the_one_that_gets_used(tmp_path, spy):
    """**이 단정이 「받아 놓고 안 쓰는」 결함을 잡는다.**"""
    b = _bridge(tmp_path, token="mat_stale")
    assert b.act("connect", {"launch": FRESH})["ok"] is True
    used = {name: plan.token for name, plan in spy["plans"]}
    assert used == {"ca": "mat_fresh", "runner": "mat_fresh",
                    "check": "mat_fresh", "spawn": "mat_fresh"}, used


def test_the_fingerprints_travel_with_it(tmp_path, spy):
    """지문이 옛 값으로 남으면 **대조가 통과하지 못한다** — 토큰만 바꾸면 반쪽이다."""
    b = _bridge(tmp_path, token="mat_stale")
    b.act("connect", {"launch": FRESH})
    plan = dict(spy["plans"])["ca"]
    assert (plan.ca_sha256, plan.agent_sha256) == ("aa11", "bb22")


def test_a_bare_launch_has_no_token_of_its_own(tmp_path, spy):
    """인자 없이 켠 창 — 브리지의 plan 에는 토큰이 없다. 패널이 준 값으로 성립해야 한다."""
    b = _bridge(tmp_path, token="")
    assert b.act("connect", {"launch": FRESH})["ok"] is True
    assert dict(spy["plans"])["spawn"].token == "mat_fresh"


def test_the_deep_link_path_still_works_without_a_panel_envelope(tmp_path, spy):
    """대조군 — 봉투가 없으면 딥링크로 받아 둔 값을 쓴다(종전 경로가 깨지지 않았다)."""
    b = _bridge(tmp_path, token="mat_link")
    assert b.act("connect", {})["ok"] is True
    assert dict(spy["plans"])["spawn"].token == "mat_link"


def test_no_token_anywhere_is_a_clear_refusal(tmp_path, spy):
    b = _bridge(tmp_path, token="")
    res = b.act("connect", {})
    assert res["ok"] is False and res["error"] == "no_token"
    assert spy["plans"] == [], "값도 없는데 CA 부터 받으러 갔다"
    assert "로그인" in res["detail"], "사용자가 무엇을 해야 하는지 말하지 않는다"


# ── 2. 서버는 우리가 아는 그 서버여야 한다 ────────────────────────────────────────

@pytest.mark.parametrize("other", [
    "https://evil.example",
    "http://svc.example",          # 스킴만 다르다
    "https://svc.example.evil.io",  # 접두가 같다
])
def test_an_envelope_pointing_elsewhere_is_refused(tmp_path, spy, other):
    """⚠ 여기가 열려 있으면 XSS 한 번이 **남의 서버에서 러너 실행**이 된다."""
    import urllib.parse
    url = ("dqa-connect://start?token=mat_x&base="
           + urllib.parse.quote(other, safe=""))
    b = _bridge(tmp_path, token="mat_link")
    res = b.act("connect", {"launch": url})
    assert res["ok"] is False and res["error"] == "no_base"
    assert spy["plans"] == [], "거절해 놓고 네트워크는 이미 나갔다"


def test_a_trailing_slash_is_not_a_different_server(tmp_path, spy):
    """같은 서버를 다르게 적었다고 막으면 정상 사용자가 막힌다."""
    b = _bridge(tmp_path, token="")
    res = b.act("connect", {
        "launch": "dqa-connect://start?token=t&base=https%3A%2F%2Fsvc.example%2F"})
    assert res["ok"] is True, res


def test_an_envelope_without_a_base_is_taken_as_ours(tmp_path, spy):
    """옛 웹(토큰만 싣던 판)이 보낸 봉투 — 서버를 바꾸지 않으므로 받아들인다."""
    b = _bridge(tmp_path, token="")
    assert b.act("connect", {"launch": "dqa-connect://start?token=mat_o"})["ok"] is True
    assert dict(spy["plans"])["spawn"].token == "mat_o"


def test_garbage_in_the_envelope_falls_back_rather_than_crashing(tmp_path, spy):
    b = _bridge(tmp_path, token="mat_link")
    assert b.act("connect", {"launch": "not a url at all"})["ok"] is True
    assert dict(spy["plans"])["spawn"].token == "mat_link"


# ── 3. 끝난 뒤 알린다 (2026-09-07 전제 변경) ────────────────────────────────────
#
# 종전 계약은 「연결 전에 사람에게 묻는다」였고, 그 확인이 XSS 시나리오의 마지막 방어선
# 이었다. 사용자 결정(2026-09-07)으로 **묻기를 없애고 알리기로** 바꿨다 — 막지는 못하지만
# 모르게 일어나지는 않는다. 잃은 것은 `docs/REVIEW.md` 에 적었다.


def test_connect_reports_afterwards(tmp_path, spy):
    told: list[str] = []
    b = _bridge(tmp_path, token="", notify=lambda t, m: told.append(m))
    assert b.act("connect", {"launch": FRESH})["ok"] is True
    assert told and "연결" in told[0], "연결해 놓고 아무 말도 하지 않는다"


def test_a_refused_connect_is_not_announced(tmp_path, spy):
    """대조군 — 거절된 연결까지 «했다» 고 알리면 그 알림은 믿을 수 없게 된다."""
    told: list[str] = []
    b = _bridge(tmp_path, token="", notify=lambda t, m: told.append(m))
    res = b.act("connect", {"launch": "dqa-connect://start?token=t&base=https%3A%2F%2Fevil.example"})
    assert res["ok"] is False
    assert told == []


def test_pin_records_the_server_we_actually_reached(tmp_path, spy):
    b = _bridge(tmp_path, token="")
    b.act("connect", {"launch": FRESH})
    assert spy["pinned"] == BASE


# ── 4. codex 적대 리뷰 2026-09-04 — 무결성 기준을 지우지 않는다 ──────────────────

def test_an_envelope_without_fingerprints_keeps_the_ones_we_have(tmp_path, spy):
    """⚠ **빈 값으로 덮으면 무결성 검사가 조용히 꺼진다.**

    `install_ca`·`install_runner` 는 기대값이 비면 대조를 **건너뛴다**(`if plan.ca_sha256 and …`).
    서버가 지문을 못 낸 회차에 봉투가 그 칸을 비워 오면, 종전 코드는 딥링크로 이미 받아 둔
    기준까지 지워 「받아서 그냥 실행」이 됐다.
    """
    b = _bridge(tmp_path, token="mat_link")
    b.plan = core.ConnectPlan(base=BASE, token="mat_link", ca_sha256="old_ca",
                              agent_sha256="old_agent", home=tmp_path)
    b.act("connect", {"launch": "dqa-connect://start?token=mat_new"})
    plan = dict(spy["plans"])["ca"]
    assert plan.token == "mat_new", "새 토큰은 반영돼야 한다"
    assert (plan.ca_sha256, plan.agent_sha256) == ("old_ca", "old_agent")


def test_a_fresh_fingerprint_still_wins(tmp_path, spy):
    """대조군 — 값이 오면 그것이 이긴다(위 테스트가 '항상 옛 값'을 통과시키지 않게)."""
    b = _bridge(tmp_path, token="mat_link")
    b.plan = core.ConnectPlan(base=BASE, token="mat_link", ca_sha256="old_ca",
                              agent_sha256="old_agent", home=tmp_path)
    b.act("connect", {"launch": FRESH})
    plan = dict(spy["plans"])["ca"]
    assert (plan.ca_sha256, plan.agent_sha256) == ("aa11", "bb22")
