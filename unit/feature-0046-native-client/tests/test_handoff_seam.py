"""**서버가 실제로 보내는 딥링크**를 클라이언트가 쓸 수 있는지 단정한다.

## 왜 이 파일이 생겼나 (실측, 2026-09-03)

사용자가 재설치 후 웹의 [연결 준비] → [내 AI 실행] 을 눌렀는데 프로그램은 여전히
**「연결 정보가 없습니다」**를 띄웠다.

원인: 서버가 여는 URL 은 `dqa-connect://start?token=<토큰>` 으로 **토큰만** 실려 있었다.
클라이언트는 서버 주소(`base`)도 있어야 하는데 그것이 없었다. 이 딥링크는 원래 **셸
설치본**을 위한 것이고, 그 경로는 설치 때 서버 주소와 CA 를 디스크에 심어 두므로 토큰만
받으면 됐다. 네이티브 클라이언트에는 그 사전 상태가 없다.

## 내 검증이 왜 이것을 놓쳤나 — 이 파일의 설계 근거

직전 cycle 에서 나는 스킴 인계를 「검증했다」고 보고했다. 그러나 그때 쓴 URL 은 **내가 직접
조립한 것**이었다:

    url = f"dqa-connect://start?{urlencode({'base':…, 'token':…, …})}"   # ← 내가 만든 것

즉 나는 **내 조립기가 내 파서와 맞는지**를 시험했다. 제품이 실제로 보내는 것은 한 번도
넣어 보지 않았다. 봉투는 **상대 소스에서 가져와야** 한다 — 그래서 이 파일은
`shared/dqa_identity.scheme_url()` 을 **직접 호출**해 URL 을 만들고 그것을 파서에 넣는다.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
_REPO = _UNIT.parents[1]
sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(_REPO))

from client import core  # noqa: E402
from client import gui  # noqa: E402
from shared import dqa_identity as ident  # noqa: E402


# ── 1. 서버가 만든 URL → 클라이언트가 쓸 수 있는가 (핵심 이음매) ──────────────────

def test_client_can_use_the_url_the_server_actually_builds():
    """**이 단정이 「연결 정보가 없습니다」를 잡는다.**

    URL 을 손으로 적지 않는다 — 정본 헬퍼가 만든 것을 그대로 넣는다.
    """
    url = ident.scheme_url("mat_abc", base="https://112.185.196.20",
                           ca_sha256="F5:B9:C5", agent_sha256="ba3cead4")
    got = gui.parse_scheme_url(url)
    assert got.get("base") == "https://112.185.196.20", \
        f"서버가 보낸 URL 에서 base 를 못 읽는다: {url}"
    assert got.get("token") == "mat_abc"
    assert got.get("ca_sha256") == "F5:B9:C5"
    assert got.get("agent_sha256") == "ba3cead4"


def test_the_client_entry_accepts_that_url_end_to_end(monkeypatch):
    """파싱만이 아니라 **진입점이 실제로 뜨는지** — 안내창으로 떨어지지 않아야 한다."""
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    seen: dict = {}
    monkeypatch.setattr(gui, "ClientApp",
                        lambda plan: seen.update(base=plan.base, token=plan.token)
                        or type("X", (), {"run": lambda self: None})())
    monkeypatch.setattr(core, "server_changed", lambda home, base: None)
    url = ident.scheme_url("mat_z", base="https://h.example",
                           ca_sha256="AA:BB", agent_sha256="cc")
    assert gui.main([url]) == 0
    assert seen == {"base": "https://h.example", "token": "mat_z"}


def test_token_only_url_still_lands_on_the_guidance(monkeypatch):
    """대조군 — 옛 모양(토큰만)은 **여전히** 안내로 떨어진다.

    이 단정이 없으면 위 테스트가 「원래 통과하던 것」을 확인하는 vacuous pass 일 수 있다.
    """
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    assert gui.main([ident.scheme_url("mat_only")]) == 2


def test_helper_carries_every_value_the_client_needs():
    """클라이언트가 `ConnectPlan` 에 넣는 값이 전부 URL 에 실리는가."""
    url = ident.scheme_url("t", base="b", ca_sha256="c", agent_sha256="a")
    for key in ("token", "base", "ca_sha256", "agent_sha256"):
        assert f"{key}=" in url, f"{key} 가 딥링크에 실리지 않는다"


def test_values_are_url_encoded():
    """`base` 에는 `://` 가, 지문에는 `:` 가 들어간다 — 그대로 실으면 파싱이 깨진다."""
    url = ident.scheme_url("t", base="https://h:8443/x", ca_sha256="AA:BB")
    assert "https%3A%2F%2F" in url
    assert gui.parse_scheme_url(url)["base"] == "https://h:8443/x"
    assert gui.parse_scheme_url(url)["ca_sha256"] == "AA:BB"


def test_shell_handler_regex_still_finds_the_token():
    """셸 설치본은 `[?&]token=([^&]+)` 로 토큰만 뽑는다 — 파라미터 추가가 그것을 깨면 안 된다."""
    import re
    url = ident.scheme_url("mat_shell", base="https://h", ca_sha256="AA:BB")
    m = re.search(r"[?&]token=([^&]+)", url)
    assert m and m.group(1) == "mat_shell"


def test_web_passes_the_real_values_not_placeholders():
    """라우터가 헬퍼에 **그 자리의 실제 값**을 넘기는지 소스로 확인한다."""
    src = (_REPO / "unit/feature-0003-agent-web-ui/src/routers/oauth_as.py"
           ).read_text(encoding="utf-8")
    call = src[src.find("_ident.scheme_url("):][:200]
    for arg in ("base=base", "ca_sha256=ca_fp", "agent_sha256=agent_sha"):
        assert arg in call, f"라우터가 {arg} 를 넘기지 않는다 — 딥링크가 다시 반쪽이 된다"


# ── 2. 서버 주소 고정 (남이 만든 링크 방어) ───────────────────────────────────────

def test_first_connection_has_nothing_to_compare(tmp_path):
    assert core.server_changed(tmp_path, "https://a") is None


def test_same_server_is_not_a_change(tmp_path):
    core.pin_server(tmp_path, "https://a")
    assert core.server_changed(tmp_path, "https://a") is None


def test_different_server_is_reported(tmp_path):
    core.pin_server(tmp_path, "https://a")
    assert core.server_changed(tmp_path, "https://evil") == "https://a"


def test_broken_pin_file_is_not_a_change(tmp_path):
    """깨진 파일을 「다른 서버」로 읽으면 정상 사용자가 매번 질문을 받는다."""
    (tmp_path / "server.json").write_text("not json", encoding="utf-8")
    assert core.server_changed(tmp_path, "https://a") is None


def test_pin_is_written_only_after_a_working_connection():
    """실패한 주소를 고정하면 다음번에 그 주소가 「전에 쓰던 곳」으로 신뢰받는다."""
    src = (_SRC / "client" / "gui.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_connect")
    seg = ast.get_source_segment(src, fn) or ""
    idx_check = seg.find("check_connection")
    idx_pin = seg.find("pin_server")
    assert idx_pin > idx_check >= 0, "연결 확인 **전에** 서버를 고정한다"


def test_entry_asks_before_using_a_different_server(monkeypatch):
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    asked: list[str] = []
    monkeypatch.setattr(core, "server_changed", lambda home, base: "https://old")
    monkeypatch.setattr(gui, "confirm", lambda msg, **kw: asked.append(msg) or False)
    monkeypatch.setattr(gui, "ClientApp",
                        lambda plan: pytest.fail("사용자가 거절했는데 진행했다"))
    assert gui.main([ident.scheme_url("t", base="https://new")]) == 3
    assert "https://old" in asked[0] and "https://new" in asked[0], \
        "어느 주소에서 어느 주소로 바뀌는지 보여 주지 않으면 판단할 수 없다"


def test_entry_proceeds_when_user_confirms(monkeypatch):
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    monkeypatch.setattr(core, "server_changed", lambda home, base: "https://old")
    monkeypatch.setattr(gui, "confirm", lambda msg, **kw: True)
    monkeypatch.setattr(gui, "ClientApp",
                        lambda plan: type("X", (), {"run": lambda self: None})())
    assert gui.main([ident.scheme_url("t", base="https://new")]) == 0


def test_confirm_defaults_to_no_when_it_cannot_ask(monkeypatch):
    """물을 수 없는 환경에서 「예」로 떨어지면 물어보려던 이유가 통째로 무력화된다."""
    monkeypatch.setitem(sys.modules, "tkinter", None)
    assert gui.confirm("정말?") is False


# ── 3. 화면이 클라이언트를 주 경로로 두는가 ───────────────────────────────────────

_MODAL = _REPO / "unit/feature-0003-agent-web-ui/src/static/index.html"
_PAGE = _REPO / "unit/feature-0003-agent-web-ui/src/static/ai-connect.html"


@pytest.mark.parametrize("path", [_MODAL, _PAGE])
def test_terminal_path_is_collapsed(path):
    """사용자 결정 2026-09-03: 1·2·3단계는 클라이언트가 하므로 웹에 노출할 필요가 없다."""
    html = path.read_text(encoding="utf-8")
    assert "터미널로 연결하기" in html, f"{path.name}: 터미널 경로를 접어 두지 않았다"


@pytest.mark.parametrize("path", [_MODAL, _PAGE])
def test_terminal_path_is_not_deleted(path):
    """⚠ **없애지는 않는다.** 연결 프로그램이 없는 사용자에게는 이것이 유일한 길이다."""
    html = path.read_text(encoding="utf-8")
    assert ("connectModalCmd" in html) or ("launchCmd" in html), \
        f"{path.name}: 터미널 경로가 사라졌다 — 프로그램 없는 사용자가 막다른 길에 선다"


@pytest.mark.parametrize("path", [_MODAL, _PAGE])
def test_lead_text_points_at_the_client(path):
    html = path.read_text(encoding="utf-8")
    assert "내 AI 실행" in html and "연결 프로그램이 열리고" in html, \
        f"{path.name}: 안내가 아직 터미널을 주 경로로 말한다"


def test_failure_path_opens_the_collapsed_block():
    """실패 안내가 「1단계 명령」으로 되돌려 보내는데 그 블록이 접혀 있으면 막다른 길이다."""
    js = (_REPO / "unit/feature-0003-agent-web-ui/src/static/app/connect-modal.js"
          ).read_text(encoding="utf-8")
    fn_start = js.find("function _revealCommand()")
    assert fn_start >= 0
    body = js[fn_start:fn_start + 900]
    assert "connectModalTerminal" in body and "open = true" in body, \
        "되돌아갈 경로를 가리키면서 그 경로를 닫아 둔다"


# ── 4. 안내가 가리키는 것이 그 화면에 **실재하는가** ──────────────────────────────
#
# ⚠ 실측 2026-09-03: 나는 두 화면의 안내 문구를 「[내 AI 실행] 을 누르면」 으로 바꾸면서
#   `/ai/connect` 페이지에는 **그 버튼이 없다는 사실**을 확인하지 않았다(모달에만 있었다).
#   테스트도 문구만 봤기 때문에 통과했다 — 문구가 있다는 것과 그것이 가리키는 것이 있다는
#   것은 다른 축이다. P0-AC 가 닫은 결함 클래스(「표시하는 화면 전부」)의 재발이다.

_STATIC = _REPO / "unit/feature-0003-agent-web-ui/src/static"


@pytest.mark.parametrize("page, script", [
    (_STATIC / "ai-connect.html", _STATIC / "ai-connect.js"),
    (_STATIC / "index.html", _STATIC / "app/connect-modal.js"),
])
def test_launch_button_exists_where_the_text_points_at_it(page, script):
    html = page.read_text(encoding="utf-8")
    if "내 AI 실행" not in html:
        pytest.skip(f"{page.name}: 이 화면은 실행을 안내하지 않는다")
    buttons = re.findall(r'<button[^>]*id="([A-Za-z]+)"[^>]*>\s*내 AI 실행', html)
    assert buttons, f"{page.name}: 「내 AI 실행」 을 말하면서 그 버튼이 없다"
    js = script.read_text(encoding="utf-8")
    for bid in buttons:
        assert bid in js, f"{page.name}: {bid} 버튼이 어디에도 배선되지 않았다"


@pytest.mark.parametrize("page, script", [
    (_STATIC / "ai-connect.html", _STATIC / "ai-connect.js"),
    (_STATIC / "index.html", _STATIC / "app/connect-modal.js"),
])
def test_launch_button_is_hidden_until_a_protocol_url_exists(page, script):
    """없는데 보이면 누른 뒤 아무 일도 없고, 사용자는 그것을 고장으로 읽는다."""
    html = page.read_text(encoding="utf-8")
    if "내 AI 실행" not in html:
        pytest.skip(f"{page.name}: 해당 없음")
    bid = re.findall(r'<button[^>]*id="([A-Za-z]+)"[^>]*>\s*내 AI 실행', html)[0]
    decl = re.search(rf'<button[^>]*id="{bid}"[^>]*>', html).group(0)
    assert "hidden" in decl, f"{page.name}: {bid} 가 기본 숨김이 아니다"
    js = script.read_text(encoding="utf-8")
    assert "protocol" in js, f"{script.name}: 프로토콜 유무로 노출을 정하지 않는다"


def test_page_handler_is_registered_once_not_per_repaint():
    """⚠ 처음 넣을 때 `paintOsTab()` 안에 들어가 **탭을 그릴 때마다** 등록됐다.

    중복 등록은 조용하다 — 화면은 멀쩡하고 클릭 한 번에 핸들러가 여러 번 돈다.
    """
    js = (_STATIC / "ai-connect.js").read_text(encoding="utf-8")
    i_lb = js.find('$("launchClient")')
    i_paint = js.find("function paintOsTab")
    assert i_lb >= 0 and i_paint >= 0
    end = js.find("\n  }", i_paint)
    assert not (i_paint < i_lb < end), "실행 버튼 등록이 다시 그리는 함수 안에 있다"


def test_silent_scheme_failure_is_explained():
    """스킴 핸들러가 없으면 브라우저는 **아무 일도 하지 않고 오류도 주지 않는다**."""
    js = (_STATIC / "ai-connect.js").read_text(encoding="utf-8")
    idx = js.find('$("launchClient")')
    body = js[idx - 800:idx + 900]
    assert "설치되지 않은" in body or "창이 뜨지 않으면" in body, \
        "조용한 실패를 사용자가 「고장」으로만 읽게 둔다"
