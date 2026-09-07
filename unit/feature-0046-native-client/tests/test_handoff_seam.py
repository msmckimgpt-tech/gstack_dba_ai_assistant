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


# ⚠ **전제가 뒤집혔다 (사용자 결정 2026-09-07).**
#
#   여기에는 두 테스트가 있었다 — `test_terminal_path_is_collapsed`(접어 둔다)와
#   `test_terminal_path_is_not_deleted`(**없애지는 않는다**). 뒤엣것은 「프로그램 없는
#   사용자가 막다른 길에 선다」를 근거로 삭제를 막고 있었다.
#
#   사용자가 그 근거를 알고 반대로 골랐다:
#
#       "이제 '연결 준비' 의 역할은 클라이언트가 모두 수행하도록 구성될 부분이니,
#        터미널 및 AI에게 연결을 요청하는 부분은 제거해주세요."
#
#   그래서 두 테스트를 **지우는 대신 뒤집는다.** 지우면 「이제 무엇이 참인가」를 아무도 지키지
#   않고, 다음 사람이 지운 경로를 되살려도 초록이다. 그리고 옛 테스트의 걱정(막다른 길)은
#   여전히 옳으므로, 그 자리를 **받기 안내가 메우는지** 함께 고정한다.

_GONE = (
    # 터미널 경로
    "터미널로 연결하기", "connectModalCmd", "launchCmd", "명령 복사",
    "connectModalTerminal", "terminalPath",
    # AI 지시문 두 갈래(전부 맡기기 · 조사만 맡기기)
    "지시문 복사", "조사 지시문 복사", "connectModalText", "handoffText",
    "connectModalProbe", "probeText", "probeBox",
    # 발급 버튼
    "연결 준비", "connectModalMake", "makeHandoff",
)


@pytest.mark.parametrize("path", [_MODAL, _PAGE])
def test_terminal_and_ai_instruction_paths_are_gone(path):
    """터미널·AI 지시문·「연결 준비」가 **두 화면 모두**에서 사라졌다.

    한 화면만 지우면 링크를 새 탭으로 연 사용자와 모달에서 본 사용자가 다른 것을 본다 —
    P0-X 가 닫은 결함 클래스다. 그래서 `parametrize` 로 둘 다 건다.
    """
    html = path.read_text(encoding="utf-8")
    # 주석에는 「무엇을 왜 지웠는가」가 남아 있어야 하므로, 마크업 본문만 본다.
    body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    left = [t for t in _GONE if t in body]
    assert not left, f"{path.name}: 지운 경로가 아직 있다 — {left}"


@pytest.mark.parametrize("path", [_MODAL, _PAGE])
def test_removing_them_did_not_leave_a_dead_end(path):
    """지운 자리를 **받기 안내가 메운다.**

    옛 `test_terminal_path_is_not_deleted` 의 걱정은 옳았다 — 프로그램이 없는 사용자에게
    아무 길도 남기지 않으면 그 사람은 막다른 길에 선다. 경로를 바꾼 것이지 없앤 것이
    아니라는 사실을 여기서 지킨다.
    """
    html = path.read_text(encoding="utf-8")
    body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    assert "DQA 앱 받기" in body, f"{path.name}: 프로그램을 받을 길이 화면에 없다"


@pytest.mark.parametrize("path", [_MODAL, _PAGE])
def test_lead_text_points_at_the_client(path):
    """안내가 **앱 창 경로**를 주 경로로 말하는가.

    ⚠ 문구는 2026-09-04 에 「연결 프로그램이 열리고」 → 「DQA 앱 창이 열리고」로 바뀌었다.
    이 프로그램이 창을 직접 그리게 되면서 «별도 프로그램»이라는 인상이 틀린 것이 됐기
    때문이다(사용자 지적). 지켜야 하는 성질은 문구가 아니라 **무엇을 주 경로로 가리키는가**다.
    """
    html = path.read_text(encoding="utf-8")
    assert "내 AI 실행" in html, f"{path.name}: 실행 경로를 가리키지 않는다"
    # ⚠ 문구가 또 바뀌었다(2026-09-07). 「연결 준비를 누른 뒤 내 AI 실행을 누르면 앱 창이
    #   열리고」가 사라지고 「연결은 DQA 앱이 합니다」가 됐다 — 누를 것이 하나뿐이기 때문이다.
    #   지켜야 하는 성질은 여전히 문구가 아니라 **무엇을 주 경로로 가리키는가**다.
    assert "연결은 <strong>DQA 앱</strong>이 합니다" in html, \
        f"{path.name}: 안내가 앱을 주 경로로 말하지 않는다"


def test_failure_messages_no_longer_point_at_a_path_that_is_gone():
    """⚠ **전제가 뒤집혔다.** 종전 계약은 「실패 안내가 「1단계 명령」으로 되돌려 보내니 그
    블록을 펼쳐라」였다(`_revealCommand`). 그 블록이 사라졌으므로 이제 지켜야 하는 것은
    반대다 — **없는 곳을 가리키지 않는가.**

    이것이 더 중요한 축이다. 사라진 경로를 계속 가리키는 안내는 «막다른 길» 을 만드는데,
    화면에는 아무 흔적도 남지 않아 소스만 보면 멀쩡해 보인다.
    """
    js = (_REPO / "unit/feature-0003-agent-web-ui/src/static/app/connect-modal.js"
          ).read_text(encoding="utf-8")
    # 사용자에게 보이는 문자열만 본다 — 주석에는 「왜 지웠는가」가 남아 있어야 한다.
    quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', js)
    speaking = [q for q in quoted if any(w in q for w in ("터미널", "1단계", "붙여넣"))]
    assert not speaking, f"사라진 경로를 아직 가리킨다: {speaking}"
    assert "_revealCommand" not in js, "지운 함수의 호출이 남아 있다"


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
def test_launch_button_never_lies_about_what_it_can_do(page, script):
    """없는데 보이면 누른 뒤 아무 일도 없고, 사용자는 그것을 고장으로 읽는다.

    ⚠ **두 화면이 갈렸다 (2026-09-07).** 종전에는 둘 다 「[연결 준비] 가 프로토콜 URL 을
    만들어 준 뒤에만 보인다」였고, 그래서 둘 다 `hidden` 이었다. 그 버튼이 사라지면서:

    - **모달**은 창을 여는 순간이 있으므로 그때 미리 받아 두고(`_offerLaunch`), 받아졌을
      때만 버튼을 드러낸다 — 종전 계약 그대로 `hidden`.
    - **단독 페이지**는 창을 여는 계기가 없다. 그래서 버튼이 **스스로 받는다** — 숨겨 두면
      영영 드러날 계기가 없어 「없는 버튼을 가리키는 안내」가 된다.

    지켜야 하는 성질은 `hidden` 이라는 구현이 아니라 **누르면 실제로 무슨 일이 일어나는가**
    다. 두 구현을 각각 그 성질로 잰다.
    """
    html = page.read_text(encoding="utf-8")
    if "내 AI 실행" not in html:
        pytest.skip(f"{page.name}: 해당 없음")
    bid = re.findall(r'<button[^>]*id="([A-Za-z]+)"[^>]*>\s*내 AI 실행', html)[0]
    decl = re.search(rf'<button[^>]*id="{bid}"[^>]*>', html).group(0)
    js = script.read_text(encoding="utf-8")
    if "hidden" in decl:
        # 숨겨 두는 쪽은 **드러내는 자리**가 있어야 한다 — 없으면 영영 안 보인다.
        assert "hidden = false" in js, f"{script.name}: 숨겨 놓고 드러내는 곳이 없다"
    else:
        # 늘 보이는 쪽은 **누를 때 받아야** 한다 — 안 그러면 눌러도 아무 일이 없다.
        idx = js.find(f'$("{bid}")')
        assert idx >= 0, f"{script.name}: {bid} 가 배선되지 않았다"
        assert "/api/ai/connect/token" in js[idx:idx + 1200], \
            f"{script.name}: 늘 보이는 버튼인데 눌러도 연결 정보를 받지 않는다"
    assert "protocol" in js, f"{script.name}: 프로토콜 유무로 동작을 정하지 않는다"


def test_page_handler_is_registered_once_not_per_repaint():
    """⚠ 처음 넣을 때 `paintOsTab()` 안에 들어가 **탭을 그릴 때마다** 등록됐다.

    중복 등록은 조용하다 — 화면은 멀쩡하고 클릭 한 번에 핸들러가 여러 번 돈다.

    ⚠ 그 `paintOsTab` 은 2026-09-07 에 사라졌다(OS 탭이 없어졌다). 그래서 「저 함수 안에
    있지 않은가」로는 더 이상 잴 수 없다 — 재는 것을 **성질 자체**로 옮긴다: 등록은 모듈
    최상위에서 **정확히 한 번** 일어난다.
    """
    js = (_STATIC / "ai-connect.js").read_text(encoding="utf-8")
    regs = re.findall(r'\$\("launchClient"\)[^\n]*addEventListener', js)
    assert len(regs) == 1, f"실행 버튼 등록이 {len(regs)} 곳이다 — 1 이어야 한다"
    # 등록 줄의 들여쓰기가 2칸(IIFE 최상위)인가 — 함수 안이면 4칸 이상이 된다.
    line = next(ln for ln in js.splitlines() if 'addEventListener' in ln
                and '$("launchClient")' in ln)
    assert len(line) - len(line.lstrip()) <= 2, \
        f"실행 버튼 등록이 어떤 함수 안에 있다: {line.strip()[:60]}"


def test_silent_scheme_failure_is_explained():
    """스킴 핸들러가 없으면 브라우저는 **아무 일도 하지 않고 오류도 주지 않는다**."""
    js = (_STATIC / "ai-connect.js").read_text(encoding="utf-8")
    idx = js.find('$("launchClient")')
    body = js[idx - 800:idx + 900]
    assert "설치되지 않은" in body or "창이 뜨지 않으면" in body, \
        "조용한 실패를 사용자가 「고장」으로만 읽게 둔다"
    # ⚠ 되돌아갈 곳도 함께 본다. 종전 문구는 「아래 [터미널로 연결하기] 를 펼쳐 주세요」
    #   였는데 그 블록이 사라졌다 — 안내만 남으면 없는 곳을 가리킨다.
    assert "터미널" not in body, "사라진 경로를 아직 가리킨다"
