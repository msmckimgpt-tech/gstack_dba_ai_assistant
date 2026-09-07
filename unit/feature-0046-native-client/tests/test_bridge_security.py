"""로컬 브리지의 방어를 **실제 HTTP 요청으로** 구동해 단정한다.

## 왜 이 파일이 중요한가

이 브리지는 이 클라이언트가 여는 **유일한 새 공격 표면**이다. 서비스 origin 의 어떤 페이지든
부를 수 있고, 성공하면 **사용자 머신에서 프로세스가 뜬다**. 그래서 방어를 소스 문자열로
확인하지 않는다 — 서버를 띄우고 진짜 요청을 보내 **거절되는지**를 본다.

⚠ 이 프로젝트가 반복해 겪은 실패가 「내가 만든 것끼리 맞춰 보고 검증했다고 말한 것」이다.
여기서는 **브라우저가 실제로 보내는 헤더 조합**을 재현한다(`Origin`·`Sec-Fetch-Site`·
커스텀 nonce 헤더). 그 조합이 아니면 통과하지 못해야 한다.
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
ORIGIN = "https://svc.example"


@pytest.fixture()
def confirmed():
    """알림을 기록한다.

    ⚠ 이름이 `confirmed` 인 것은 이력이다. 2026-09-07 에 **묻기 → 알리기**로 바뀌었다
    (사용자 결정: "연결을 되묻는것은 사용자에게 위협으로 다가올 수 있습니다").
    """
    calls: list[str] = []
    yield calls, (lambda title, body: calls.append(f"{title}|{body}"))


@pytest.fixture()
def br(tmp_path, confirmed, monkeypatch):
    calls, confirm = confirmed
    monkeypatch.setattr(core, "discover_runtime", lambda n: [])
    plan = core.ConnectPlan(base=BASE, token="mat_t", home=tmp_path)
    b = bridge_mod.Bridge(plan, notify=confirm)
    b.start()
    b._confirm_calls = calls
    yield b
    b.stop()


def _post(b, action, *, origin=ORIGIN, nonce=None, site="cross-site",
          body=None, method="POST"):
    url = f"http://127.0.0.1:{b.port}/{action}"
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(url, data=data, method=method)
    if origin is not None:
        req.add_header("Origin", origin)
    if nonce is not None:
        req.add_header("X-DQA-Nonce", nonce)
    if site is not None:
        req.add_header("Sec-Fetch-Site", site)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# ── 1. 정상 경로 ──────────────────────────────────────────────────────────────────

def test_correct_headers_pass(br):
    code, body = _post(br, "status", nonce=br.nonce)
    assert code == 200 and body["ok"] is True
    assert body["base"] == BASE


# ── 2. 세 겹 검문 — 하나라도 빠지면 거절 ──────────────────────────────────────────

def test_missing_nonce_is_rejected(br):
    code, body = _post(br, "status", nonce=None)
    assert code == 403 and body["error"] == "nonce"


def test_wrong_nonce_is_rejected(br):
    code, body = _post(br, "status", nonce="deadbeef")
    assert code == 403 and body["error"] == "nonce"


def test_other_origin_is_rejected(br):
    """**핵심** — 다른 사이트가 부르면 nonce 를 알아도 통과 못 한다."""
    code, body = _post(br, "status", origin="https://evil.example", nonce=br.nonce)
    assert code == 403 and body["error"] == "origin"


def test_missing_origin_is_rejected(br):
    code, body = _post(br, "status", origin=None, nonce=br.nonce)
    assert code == 403 and body["error"] == "origin"


def test_missing_sec_fetch_site_is_rejected(br):
    """브라우저가 아닌 클라이언트(curl 등)는 이 헤더를 안 붙인다 — 상대는 브라우저뿐이다."""
    code, body = _post(br, "status", nonce=br.nonce, site=None)
    assert code == 403 and body["error"] == "fetch-site"


def test_nonce_is_per_launch(tmp_path):
    """재시작하면 옛 링크가 죽어야 한다 — 흘러나간 nonce 가 영원히 유효하면 안 된다."""
    plan = core.ConnectPlan(base=BASE, token="t", home=tmp_path)
    a = bridge_mod.Bridge(plan, notify=lambda t, m: None)
    c = bridge_mod.Bridge(plan, notify=lambda t, m: None)
    try:
        assert a.nonce != c.nonce and len(a.nonce) >= 24
    finally:
        a.stop(); c.stop()  # noqa: E702


def test_get_is_not_a_way_in(br):
    """GET 은 `<img>`·`<script>` 로도 발사되어 preflight 없이 나간다."""
    code, body = _post(br, "status", nonce=br.nonce, method="GET")
    assert code == 405 and body["error"] == "use_post"


def test_preflight_only_answers_the_allowed_origin(br):
    code, _ = _post(br, "status", origin="https://evil.example", nonce=None,
                    site=None, method="OPTIONS")
    assert code == 403


def test_preflight_declares_private_network(br):
    """이 헤더가 없으면 최신 브라우저가 https→127.0.0.1 을 차단한다(실측 2026-09-04)."""
    url = f"http://127.0.0.1:{br.port}/status"
    req = urllib.request.Request(url, method="OPTIONS")
    req.add_header("Origin", ORIGIN)
    with urllib.request.urlopen(req, timeout=15) as r:
        assert r.headers.get("Access-Control-Allow-Private-Network") == "true"
        assert r.headers.get("Access-Control-Allow-Origin") == ORIGIN


def test_bridge_binds_loopback_only(br):
    assert br._srv.server_address[0] == "127.0.0.1"


# ── 3. 위험 동작은 **끝난 뒤 알린다** (2026-09-07 전제 변경) ─────────────────────
#
# 종전 계약: 프로세스를 띄우는 동작 **앞에** 네이티브 확인 창을 띄운다. 그 확인은 서비스에
# XSS 가 생겼을 때 「사람 없이 사용자 머신에서 프로세스가 뜨는 것」을 막던 마지막 겹이었다.
#
# 사용자 결정(2026-09-07): *"연결을 되묻는것은 사용자에게 위협으로 다가올 수 있습니다.
# 별도의 확인 창 없이 수행되도록 구성해주세요."* — 실제로 그 창은 사용자가 방금 [이 서비스에
# 연결] 을 누른 **직후** 떴고, 문구가 「웹 화면이 이 컴퓨터에서 …」로 시작해 경고처럼 읽혔다.
#
# ⚠ **막는 겹은 사라졌다.** 남은 것은 「모르게 일어나지는 않는다」 — 끝난 뒤 알림 영역으로
#   알린다. 이 파일은 그 약속을 잠근다: 성공하면 알리고, 실패하면 알리지 않고, 조회는 조용하다.


def test_process_spawning_actions_report_afterwards(br, monkeypatch):
    monkeypatch.setattr(core, "login", lambda st, **kw: (True, "ok"))
    br._states = [core.RuntimeState(name="claude", path="/x/claude", where="wsl")]
    code, body = _post(br, "login", nonce=br.nonce, body={"id": "claude (WSL)"})
    assert code == 200 and body["ok"] is True
    assert br._confirm_calls, "실행해 놓고 아무 말도 하지 않는다 — 모르게 일어난다"
    assert "claude (WSL)" in br._confirm_calls[0]


def test_a_failed_action_is_not_reported_as_done(tmp_path, monkeypatch):
    """⚠ 실패까지 알리면 그 알림은 **확인할 수 없는 소음**이 된다."""
    calls: list = []
    monkeypatch.setattr(core, "login", lambda *a, **k: (False, "로그인 실패"))
    plan = core.ConnectPlan(base=BASE, token="t", home=tmp_path)
    b = bridge_mod.Bridge(plan, notify=lambda t, m: calls.append(m))
    b.start()
    try:
        b._states = [core.RuntimeState(name="claude", path="/x/claude")]
        code, body = _post(b, "login", nonce=b.nonce, body={"id": "claude"})
        assert code == 200 and body["ok"] is False
        assert calls == [], "실패했는데 «했다» 고 알렸다"
    finally:
        b.stop()


def test_a_broken_notifier_does_not_undo_the_action(tmp_path, monkeypatch):
    """알림은 **통지이지 관문이 아니다** — 알리지 못했다고 연결이 취소되면 안 된다."""
    ran: list = []
    monkeypatch.setattr(core, "login", lambda *a, **k: ran.append(1) or (True, "ok"))
    plan = core.ConnectPlan(base=BASE, token="t", home=tmp_path)

    def _boom(*_a):
        raise RuntimeError("트레이 없음")

    b = bridge_mod.Bridge(plan, notify=_boom)
    b.start()
    try:
        b._states = [core.RuntimeState(name="claude", path="/x/claude")]
        code, body = _post(b, "login", nonce=b.nonce, body={"id": "claude"})
        assert code == 200 and body["ok"] is True
        assert ran == [1]
    finally:
        b.stop()


def test_read_only_actions_stay_quiet(br):
    """조회까지 알리면 알림이 소음이 되고, 사람은 그것을 끄는 법을 배운다."""
    _post(br, "status", nonce=br.nonce)
    _post(br, "discover", nonce=br.nonce)
    assert br._confirm_calls == []


def test_dangerous_set_covers_every_process_spawning_action():
    """프로세스를 띄우는 동작이 목록 밖에 생기면 **알리지 않고** 실행된다."""
    import ast
    src = (_UNIT / "src" / "client" / "bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    spawning = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_do_"):
            seg = ast.get_source_segment(src, node) or ""
            if any(k in seg for k in ("core.login", "core.spawn_runner",
                                      "core.install_runner", "core.check_connection")):
                spawning.add(node.name[len("_do_"):])
    assert spawning <= set(bridge_mod.NOTIFIED), \
        f"확인 없이 프로세스를 띄우는 동작: {sorted(spawning - set(bridge_mod.NOTIFIED))}"


# ── 4. 알 수 없는 동작·깨진 입력 ──────────────────────────────────────────────────

def test_unknown_action_is_refused(br):
    code, body = _post(br, "rm_rf", nonce=br.nonce)
    assert body["error"] == "unknown_action"


def test_broken_json_does_not_crash_the_bridge(br):
    url = f"http://127.0.0.1:{br.port}/status"
    req = urllib.request.Request(url, data=b"{not json", method="POST")
    for k, v in (("Origin", ORIGIN), ("X-DQA-Nonce", br.nonce),
                 ("Sec-Fetch-Site", "cross-site")):
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    assert code == 400
    # 그 뒤에도 살아 있어야 한다
    assert _post(br, "status", nonce=br.nonce)[0] == 200


def test_origin_comparison_is_origin_not_prefix(tmp_path):
    """`https://svc.example.evil.com` 이 통과하면 안 된다."""
    plan = core.ConnectPlan(base=BASE, token="t", home=tmp_path)
    b = bridge_mod.Bridge(plan, notify=lambda t, m: None)
    b.start()
    try:
        for bad in ("https://svc.example.evil.com", "http://svc.example",
                    "https://svc.example:8443"):
            code, body = _post(b, "status", origin=bad, nonce=b.nonce)
            assert code == 403 and body["error"] == "origin", f"{bad} 가 통과했다"
    finally:
        b.stop()


# ── 5. 수명 — 기동하지 않은 브리지도 안전하게 끝난다 ─────────────────────────────

def test_stop_without_start_does_not_hang(tmp_path):
    """⚠ `shutdown()` 은 `serve_forever()` 루프를 전제로 **블록한다**.

    루프가 시작된 적 없으면 영원히 기다린다 — 기동에 실패한 앱이 종료되지 않는 결함이다.
    실측 2026-09-04: 이 형태로 테스트가 그대로 멎었다.
    """
    import threading as _t
    plan = core.ConnectPlan(base=BASE, token="t", home=tmp_path)
    b = bridge_mod.Bridge(plan, notify=lambda t, m: None)
    done = _t.Event()
    _t.Thread(target=lambda: (b.stop(), done.set()), daemon=True).start()
    assert done.wait(10), "기동하지 않은 브리지의 stop() 이 블록했다"


def test_double_start_is_idempotent(tmp_path):
    plan = core.ConnectPlan(base=BASE, token="t", home=tmp_path)
    b = bridge_mod.Bridge(plan, notify=lambda t, m: None)
    b.start(); b.start()
    try:
        assert _post(b, "status", nonce=b.nonce)[0] == 200
    finally:
        b.stop()


def test_stop_is_idempotent(tmp_path):
    plan = core.ConnectPlan(base=BASE, token="t", home=tmp_path)
    b = bridge_mod.Bridge(plan, notify=lambda t, m: None)
    b.start(); b.stop(); b.stop()
