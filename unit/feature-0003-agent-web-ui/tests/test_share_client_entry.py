"""share-client-entry — 「참여·fork 는 DQA 앱에서」의 **계약** 회귀.

요청(2026-09-08): 공유 링크를 일반 웹브라우저로 열면 **내용은 볼 수 있고**, 대화에
참여하거나 fork 하려면 **DQA 클라이언트를 거치게** 한다.

본 파일이 보는 것 (동작 분기는 `verify_share_client_entry.mjs` 가 jsdom 으로 실측한다):

  C1  서버가 앱 딥링크를 **정본으로** 조립한다 — 프런트가 문자열을 만들지 않는다.
  C2  그 링크에 **베어러 토큰이 실리지 않는다** (연결용 `scheme_url` 과 다른 축).
  C3  받기 URL 은 **실물 판정 정본**(`oauth_as._client_download_url`)에 위임한다.
  C4  조립 실패가 공유 **열람**을 막지 않는다.
  C5  `share.js` 가 스킴 문자열을 직접 조립하지 않는다 (개명이 도달하지 않는 자리 방지).
  C6  `share.html` 의 스크립트 **순서 계약** — 컨텍스트 모듈이 `share.js` 보다 먼저 돈다.
  C7  좌표 해석 규약을 베끼지 않는다 — 어댑터가 정본 모듈을 import 한다.
"""
from __future__ import annotations

import inspect
import os
import re
import sys


def _import_app():
    try:
        import app  # type: ignore
        return app
    except ModuleNotFoundError:
        sys.path.insert(0, "/app")
        try:
            import app  # type: ignore
            return app
        except ModuleNotFoundError:
            import web.app as app  # type: ignore
            return app


app = _import_app()

from routers import share as share_router  # noqa: E402


def _read_static(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    with open(os.path.join(base, "static", name), "r", encoding="utf-8") as fh:
        return fh.read()


class _Req:
    """`_share_client_entry` 가 보는 것은 `base_url` 하나다."""

    def __init__(self, base: str = "https://svc.example/"):
        self.base_url = base


# ── C1: 링크는 정본이 만든다 ──────────────────────────────────────────────────
def test_c1_app_link_comes_from_the_canonical_builder():
    """프런트도, 이 라우터도 스킴 문자열을 **조립하지 않는다** — 정본을 부른다.

    ⚠ 기대값을 문자열 리터럴로 적지 않는다. 그렇게 적으면 정본이 바뀌었을 때 이 테스트가
    **옛 형식을 지키는 쪽**이 되어, 개명이 도달하지 않은 자리를 되레 고정한다.
    """
    from shared import dqa_identity as ident

    got = share_router._share_client_entry(_Req(), "tok123")
    assert got["app_link"] == ident.app_open_url("https://svc.example", "/share/tok123")


def test_c1_the_link_points_at_this_very_share():
    """앱이 여는 곳은 서비스 루트가 아니라 **이 대화**다."""
    got = share_router._share_client_entry(_Req(), "tok123")
    assert "%2Fshare%2Ftok123" in got["app_link"]


def test_c1_a_token_with_url_characters_is_encoded_not_injected():
    """토큰이 경로 구분자를 품어도 다른 페이지를 가리키게 되면 안 된다."""
    got = share_router._share_client_entry(_Req(), "a/b?x=1")
    assert got["app_link"] is not None
    assert "a%2Fb" in got["app_link"] or "a%252Fb" in got["app_link"]


# ── C2: 이 링크는 자격증명을 나르지 않는다 ─────────────────────────────────────
def test_c2_the_open_link_carries_no_bearer_token():
    """공유 링크를 **받은 사람**의 화면에서 만들어지는 링크다 — 베어러를 실을 이유가 없다.

    앱 창은 기본 브라우저 프로필(또는 내장 창 자신의 세션)로 열리므로 로그인 세션이
    따라온다. 토큰을 한 번 더 실으면 얻는 것 없이 노출 지점만 늘어난다.
    """
    got = share_router._share_client_entry(_Req(), "tok123")
    assert "token=" not in got["app_link"]


# ── C3: 받기 URL 은 실물 판정 정본에 위임 ──────────────────────────────────────
def test_c3_download_url_delegates_to_the_single_prober(monkeypatch):
    from routers import oauth_as

    monkeypatch.setattr(oauth_as, "_client_download_url", lambda origin: f"{origin}/dl.exe")
    got = share_router._share_client_entry(_Req(), "tok123")
    assert got["download_url"] == "https://svc.example/dl.exe"


def test_c3_no_installer_means_no_download_url(monkeypatch):
    """**없는 다운로드를 안내하지 않는다** — 화면은 이 `None` 으로 받기 버튼을 감춘다."""
    from routers import oauth_as

    monkeypatch.setattr(oauth_as, "_client_download_url", lambda origin: None)
    got = share_router._share_client_entry(_Req(), "tok123")
    assert got["download_url"] is None


# ── C4: 조립 실패가 열람을 막지 않는다 ────────────────────────────────────────
def test_c4_a_broken_prober_does_not_break_the_share_view(monkeypatch):
    """받기 판정이 던져도 링크는 나오고, 응답은 성립한다."""
    from routers import oauth_as

    def _boom(origin):
        raise RuntimeError("release channel down")

    monkeypatch.setattr(oauth_as, "_client_download_url", _boom)
    got = share_router._share_client_entry(_Req(), "tok123")
    assert got["app_link"] is not None
    assert got["download_url"] is None


def test_c4_an_unusable_base_yields_no_link_instead_of_an_exception():
    """base 를 알 수 없으면 링크가 `None` 이고, 화면은 종전 웹 경로로 열화한다."""
    class _NoBase:
        @property
        def base_url(self):
            raise RuntimeError("no base")

    got = share_router._share_client_entry(_NoBase(), "tok123")
    assert got == {"app_link": None, "download_url": None}


def test_c4_the_view_response_carries_the_client_block():
    """핸들러가 그 값을 실제로 응답에 **싣는지** — 만들어 놓고 안 보내면 화면은 못 쓴다."""
    src = inspect.getsource(share_router.public_share_view)
    assert '"client": _share_client_entry(request, token)' in src


# ── C5: 프런트는 스킴 문자열을 만들지 않는다 ──────────────────────────────────
def test_c5_share_js_does_not_assemble_the_scheme_itself():
    """리터럴이 하나라도 있으면 개명·규칙 변경이 도달하지 않는 자리가 생긴다.

    실측 배경: 이 스킴은 2026-09-03 에 개명됐고, 그 전 이름이 리터럴로 21곳에 흩어져 있었다.
    한 곳을 놓치면 «웹은 새 스킴으로 열고 OS 엔 옛 스킴이 등록된» 상태가 되는데,
    브라우저는 스킴 핸들러 부재를 **감지하지 못한다** — 버튼이 조용히 죽는다.

    ⚠ 여기서도 **스킴 이름을 리터럴로 적지 않는다** — 정본에서 읽는다. 옛 이름은 물론이고
    현재 이름도 마찬가지다: `test_name_ssot.py` 가 허용 목록 밖 소스의 옛 이름을 잡는데,
    거기에 예외를 뚫으면 그 파일이 **다음 개명의 사각지대**가 된다(이 테스트가 처음 작성될 때
    실제로 그 게이트에 걸렸다).
    """
    from shared import dqa_identity as ident

    # ⚠ **모수는 파일 하나가 아니라 공유 화면 계열 전체**다 (적대 리뷰 qa-F2).
    #   `share.js` 만 보던 동안, `share-client-context.js` 에 손으로 조립한 스킴 URL 을
    #   넣어도 웹 pytest·jsdom 하네스·저장소 전역 개명 가드가 **전부 초록**이었다(뮤턴트
    #   실증). 가드가 있어도 모수가 노출면보다 좁으면 없는 것과 같다(§16.7 G12).
    import glob
    import os

    base = os.path.join(os.path.dirname(inspect.getfile(app)), "static")
    targets = sorted(
        glob.glob(os.path.join(base, "share*.js"))
        + glob.glob(os.path.join(base, "share*.html"))
        + glob.glob(os.path.join(base, "share*.css")))
    assert len(targets) >= 4, f"공유 화면 자산을 찾지 못했다: {targets}"

    offenders = []
    for path in targets:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        # 주석은 규약을 **설명**할 수 있다 — 금지 대상은 코드가 조립하는 리터럴이다.
        haystack = _code_only(text) if path.endswith(".js") else _strip_html_comments(text)
        if ident.SCHEME in haystack:
            offenders.append(os.path.basename(path))
    assert not offenders, (
        f"공유 화면 자산이 스킴을 직접 조립한다: {offenders}. 서버가 준 `client.app_link` 를 쓰라 "
        "— 리터럴을 두면 개명이 그 경로에 도달하지 않고, 브라우저는 스킴 핸들러 부재를 "
        "알려 주지 않으므로 버튼이 조용히 죽는다.")
    assert "app_link" in _read_static("share.js"), "서버가 준 링크를 읽지 않는다."


def test_c5_the_scheme_scan_would_catch_a_literal():
    """양성 대조군 — 순회가 깨지면 위 단정은 «찾은 것이 없어서» 통과한다."""
    from shared import dqa_identity as ident

    sample_code = f'const u = "{ident.SCHEME}://open?path=/x";'
    assert ident.SCHEME in _code_only(sample_code)
    assert ident.SCHEME not in _code_only(f"// {ident.SCHEME} 설명 주석")
    assert ident.SCHEME in _strip_html_comments(f'<a href="{ident.SCHEME}://x">')
    assert ident.SCHEME not in _strip_html_comments(f"<!-- {ident.SCHEME} 설명 -->")


# ── C6: 스크립트 순서 계약 ────────────────────────────────────────────────────
def test_c6_the_context_module_runs_before_share_js():
    """어댑터가 늦게 돌면 앱 창 안에서도 「앱에서 열기」가 뜬다 — 무한 왕복이다.

    `type="module"` 은 암묵 defer 이고 `share.js` 도 defer 라, 둘은 같은 큐에 **문서
    순서대로** 들어간다. 그래서 순서와 `defer` 를 함께 잠근다 — 하나만 지키면 계약이 깨진다.
    """
    html = _read_static("share.html")
    ctx = re.search(r'<script[^>]*type="module"[^>]*src="[^"]*share-client-context\.js[^"]*"', html)
    shr = re.search(r'<script[^>]*src="[^"]*/share\.js[^"]*"[^>]*>', html)
    assert ctx, "share-client-context.js 를 module 로 싣지 않는다."
    assert shr, "share.js 를 찾지 못했다."
    assert ctx.start() < shr.start(), "컨텍스트 모듈이 share.js 뒤에 있다 — 판정이 늦는다."
    assert "defer" in shr.group(0), "share.js 에 defer 가 없으면 모듈보다 먼저 실행된다."


def test_c6_the_context_module_is_stamped():
    """`?v=` 없는 참조는 캐시버스터 대상 자체가 아니다 — 구 모듈이 계속 실린다."""
    html = _read_static("share.html")
    assert re.search(r'share-client-context\.js\?v=', html)


# ── C7: 좌표 해석 규약을 베끼지 않는다 ────────────────────────────────────────
def _strip_html_comments(html: str) -> str:
    """HTML 주석을 걷어낸다 — 마크업이 «무엇을 하는가» 와 주석이 «왜 그런가» 는 다른 축이다."""
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def _code_only(js: str) -> str:
    """주석을 걷어낸 코드 라인만. **규약을 설명하는 문장**과 **규약을 구현하는 코드**는 다르다 —
    걷지 않으면 이 파일의 금지 단정이 자기 주석에 걸려 거짓 적색을 낸다(실측)."""
    out, in_block = [], False
    for line in js.splitlines():
        t = line.strip()
        if in_block:
            if "*/" in t:
                in_block = False
                t = t.split("*/", 1)[1]
            else:
                continue
        if t.startswith("/*"):
            if "*/" not in t:
                in_block = True
            continue
        if t.startswith("//") or t.startswith("*"):
            continue
        out.append(t)
    return "\n".join(out)


def test_c7_the_adapter_imports_the_canonical_bridge_module():
    """규약이 갈리면 「앱 안인데 앱 밖으로 보이는」 화면이 생긴다."""
    js = _read_static("share-client-context.js")
    assert re.search(r'from\s+"\./app/client-bridge\.js\?v=[^"]*"', js), \
        "정본 모듈을 import 하지 않는다 — 규약 사본이 하나 더 생겼다."
    code = _code_only(js)
    assert "sessionStorage" not in code, "어댑터가 저장 규약을 다시 구현한다."
    assert "client_port" not in code, "어댑터가 쿼리 규약을 다시 구현한다."


def test_c7_share_js_reads_the_adapter_not_the_raw_query():
    """판정의 1차 근거는 어댑터가 얹은 전역이다 — 규약을 세 번째로 **구현**하지 않는다.

    ⚠ `client_port` **한 키만** 2차 신호로 읽는 것은 의도다(적대 리뷰 UX-2차신호):
    어댑터 모듈이 적재에 실패하면 전역이 비는데, 그때 앱 창은 자기를 앱 밖으로 판정해
    지금 보고 있는 페이지로 딥링크를 다시 쏜다 — 빠져나올 수 없는 왕복이다. 모듈이 안
    돌았다면 좌표는 주소에 남아 있으므로 그것을 존재 판정에만 쓴다. **값을 쓰거나 저장하지는
    않는다** — 그것이 규약 복제와 다른 점이다.
    """
    js = _read_static("share.js")
    code = _code_only(js)
    assert "__dqaClientBridge" in js
    assert "sessionStorage" not in code, "share.js 가 좌표 저장 규약을 다시 구현한다."
    assert "client_nonce" not in code, \
        "share.js 가 nonce 를 읽는다 — 이 화면은 브리지를 부르지 않으므로 필요 없다."
    assert code.count("client_port") == 1, \
        "2차 신호는 존재 판정 1회뿐이어야 한다(값 사용은 규약 복제다)."


def test_c7_the_comment_stripper_actually_strips():
    """양성 대조군 — 걷어내기가 깨지면 위 두 단정이 **아무것도 검사하지 않는다**."""
    sample = "/* sessionStorage 설명 */\n// client_port 설명\nconst x = 1;\n"
    assert _code_only(sample).strip() == "const x = 1;"
    assert "sessionStorage" in _code_only('const s = sessionStorage;')


# ── C8: 익명 응답이 **조용히 자라지 않는다** (§7.3 SEC-20260811 규율) ─────────
#
# 이 endpoint 는 이 제품이 바깥을 향해 여는 유일한 표면이다. 그 응답에 필드를 얹는 것은
# 그때마다 심사를 거쳐야 하는데, 심사를 강제하는 것은 문서가 아니라 **적색으로 바뀌는
# 테스트**다. 아래 집합을 고정해 다음 cycle 이 필드를 하나 더 얹을 때 여기서 걸리게 한다.
_ANON_SHARE_TOP_LEVEL_KEYS = {"share", "conversation", "messages", "viewer", "client"}


def test_c8_the_anonymous_response_shape_is_pinned():
    """최상위 키 집합이 바뀌면 적색 — 바꾸려면 이 목록과 `docs/SECURITY.md` §7 을 함께 고친다.

    ⚠ **들여쓰기로 세지 않는다** (적대 리뷰 2026-09-08 2R-§3). 첫 구현은
    `^\s{16}"(\w+)":` 정규식이었는데, 그것은 (a) 16칸에 있는 **중첩 dict 키**를 최상위로
    오인하고 (b) 포매팅이 바뀌면 조용히 0건을 세며 (c) 그 0건이 기대 집합과 다르니 적색은
    나지만 **이유가 엉뚱**하다. 지금은 AST 로 `JSONResponse(...)` 의 첫 인자 dict 를 직접 읽는다.

    ⚠ 남은 한계는 명시한다 — `**extra` 전개나 `payload["x"] = …` 같은 사후 대입은 이 방법도
    보지 못한다. 그래서 그 두 형태가 **없다는 것**을 아래에서 함께 단정한다.
    """
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(share_router.public_share_view)))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "JSONResponse"]
    payloads = [c.args[0] for c in calls
                if c.args and isinstance(c.args[0], ast.Dict)
                and any(isinstance(k, ast.Constant) and k.value == "share" for k in c.args[0].keys)]
    assert len(payloads) == 1, f"공유 응답 dict 를 특정하지 못했다 (후보 {len(payloads)}개)"
    payload = payloads[0]
    assert all(k is not None for k in payload.keys), \
        "응답에 `**` 전개가 있다 — 키 집합을 이 방법으로 셀 수 없다."
    found = {k.value for k in payload.keys if isinstance(k, ast.Constant)}
    assert found == _ANON_SHARE_TOP_LEVEL_KEYS, (
        f"익명 응답의 최상위 키가 바뀌었다: {found ^ _ANON_SHARE_TOP_LEVEL_KEYS}. "
        "docs/SECURITY.md §7 표와 이 목록을 함께 갱신하라.")


def test_c8_the_shape_check_actually_reads_the_dict():
    """양성 대조군 — 추출이 깨지면 위 단정은 «찾은 것이 없어서» 다른 이유로 죽는다."""
    assert "client" in _ANON_SHARE_TOP_LEVEL_KEYS
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(share_router.public_share_view)))
    dicts = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "JSONResponse"]
    assert dicts, "JSONResponse 호출을 찾지 못했다 — 응답 조립 방식이 바뀌었다."


def test_c8_security_md_records_the_new_anonymous_fields():
    """표에 없으면 다음 사람이 못 본다 — §7.3 이 남긴 교훈이 정확히 그것이다."""
    import os

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        inspect.getfile(app)))))
    with open(os.path.join(root, "docs", "SECURITY.md"), encoding="utf-8") as fh:
        sec = fh.read()
    row = next((l for l in sec.splitlines()
                if l.startswith("| `/api/public/share/{token}` | GET")), "")
    assert "app_link" in row and "download_url" in row, \
        "익명 응답에 필드를 더했는데 SECURITY.md §7 표가 그것을 모른다."


# ── C9: 익명 페이지는 브리지 좌표를 **심지 못한다** ───────────────────────────
def test_c9_the_share_page_cannot_plant_bridge_coordinates():
    """공유 링크 한 줄로 origin 전역 상태가 오염되면 안 된다.

    이 흡수 로직은 원래 **로그인해야 도달하는 앱 루트**에만 있었다. 공유 화면이 같은 모듈을
    쓰게 되면서 익명 페이지에서도 돌게 됐고, 그대로 두면
    `…/share/<tok>?client_port=1&client_nonce=EVIL` 한 줄이 `sessionStorage["dqa.bridge"]`
    를 심는다 — 피해자가 같은 탭에서 앱 루트로 이동하면 세션 결속 베어러가 그 좌표로 나간다.
    """
    js = _read_static("app/client-bridge.js")
    code = _code_only(js)
    assert "_PERSIST_SURFACES" in code, "보관 허용 표면 판정이 없다."
    # ⚠ **한 줄 리터럴이 아니라 «분기 안에 있는가» 를 본다** (2026-09-10). 종전 단정은
    #   `if (persist) sessionStorage.setItem` 한 줄이었는데, quota 실패를 다루려고 그 자리가
    #   `if (persist) { try { … } catch … }` 로 바뀌면서 문자열이 깨졌다. 계약은 그대로다 —
    #   **동기 보관은 persist 분기 안에서만** 일어난다. 그 위치를 구조로 확인한다.
    #   모수는 **흡수 IIFE 안**이다 — 그 위의 `_adoptIfTheBridgeAcceptsIt` 도 저장하지만
    #   그쪽은 «로컬 브리지가 수용할 때만» 이라 별개 방어선이다(그 계약은 아래 C9b·하네스).
    absorb = code[code.index("clientBridge = (function"):]
    branch = absorb.index("if (persist)")
    else_at = absorb.index("} else {", branch)
    assert 'sessionStorage.setItem("dqa.bridge"' in absorb[branch:else_at], \
        "익명 페이지에서도 좌표를 저장한다 — 링크 발신자가 origin 전역 상태를 심을 수 있다."
    assert 'sessionStorage.setItem("dqa.bridge"' not in absorb[:branch], \
        "분기 앞에서 이미 저장한다 — persist 판정이 무의미해진다."
    assert "getAll(\"client_nonce\").length > 1" in code, \
        "좌표 중복(쿼리 스머글링 신호)을 버리지 않는다."


def test_c9_the_persist_gate_is_an_allow_list_not_a_deny_list():
    """**극성**이 계약이다 — 열거하지 않은 자리는 저장하지 않는다.

    ⚠ 첫 조치는 익명 표면을 열거해 막는 deny-list 였고, 그것은 **실제로 뚫렸다**: 같은 문서가
    정적 마운트를 통해 `/static/share.html` 로도 익명 200 으로 서빙되어(라이브 실측) 정규식을
    그냥 비껴갔다. allow-list 는 새 페이지가 생겨도 기본값이 「저장 안 함」이라 같은 구멍이
    다시 열리지 않는다. 실제 동작은 `verify_share_client_entry.mjs` 가 경로 표로 확인한다.
    """
    code = _code_only(_read_static("app/client-bridge.js"))
    assert "_PERSIST_SURFACES" in code, "보관 허용 표면 목록이 없다."
    assert "_PERSIST_SURFACES.has(" in code, \
        "allow-list 를 **포함 판정**으로 쓰지 않는다 — deny-list 로 되돌아갔을 수 있다."
    assert not re.search(r"_ANONYMOUS_SURFACE|!\s*_PERSIST_SURFACES", code), \
        "익명 표면을 열거해 막는 방식(deny-list)으로 되돌아갔다 — 2R B1 이 그 형태를 깼다."
