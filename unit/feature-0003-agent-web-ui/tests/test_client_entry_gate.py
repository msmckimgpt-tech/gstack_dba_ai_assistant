"""client-entry-gate — 「일반 브라우저는 설치 안내로」의 **계약** 회귀.

요청(2026-09-10): "DQA클라이언트 외, 일반적인 웹브라우저로 접속할 경우 클라이언트 설치
안내페이지로 연결해주세요." 사용자 결정: 게이트 대상은 **앱 루트 + 관리 콘솔**,
**탈출구 없음**(앱 전용 일관 — 2026-09-08 공유 참여·fork 결정과 같은 방향).

본 파일이 보는 것 (분기 동작은 `verify_client_entry_gate.mjs` 가 jsdom 으로 실측한다):

  C1  `/install` 이 실재하고 안내 문서를 서빙한다.
  C2  `/api/ai/client/entry` 가 익명으로 화면 한 벌을 준다 — 딥링크는 **정본**이 조립한다.
  C3  배포 중인 설치기가 없으면 `release: null` — 없는 것을 광고하지 않는다.
  C4  게이트가 두 셸(`index.html`·`admin.html`)에 **스타일시트보다 먼저** 실려 있다.
  C5  안내 페이지 자신은 게이트를 싣지 않는다 (자기 자신으로 되보내는 왕복 차단).
  C6  좌표 규약의 세 문자열이 정본 모듈과 **같다** — 사본이 갈리면 앱 창이 튕긴다.
  C7  게이트 대상 집합이 정본 모듈의 보관 표면 ∪ {관리 콘솔} 이고, 익명 표면을 포함하지 않는다.
  C8  `docs/SECURITY.md §7` 익명 표에 신규 두 경로가 등재됐다.
  C9  행위 하네스가 실제로 돌거나, 못 돌면 그 gap 이 문서에 기록됐다.

  N   음성 대조군 — 위 스캔들이 실제 위반을 잡는지 (§16.7 G11-b).
"""
from __future__ import annotations

import inspect
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


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

from routers import client_release as client_release_router  # noqa: E402

_TESTS = Path(__file__).resolve().parent
_FEATURE_DOCS = _TESTS.parent / "docs"
_HARNESS = _TESTS / "verify_client_entry_gate.mjs"
_CI_GAP_MARKER = "client-entry-gate 행위 하네스 미실행"

#: 게이트 스크립트의 배선 형태. `type="module"` 이면 deferred 라 계약이 깨진다.
_GATE_TAG = re.compile(r'<script\s+src="/static/client-gate\.js\?v=[^"]*"\s*>\s*</script>')


def _static(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    with open(os.path.join(base, "static", name), "r", encoding="utf-8") as fh:
        return fh.read()


def _repo_doc(rel: str) -> str:
    """`repo/docs/...` — 이 테스트 파일 기준 상대 경로로 찾는다(컨테이너/호스트 공통)."""
    for base in (_TESTS.parents[2], Path("/app").parent, Path.cwd()):
        p = base / rel
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise AssertionError(f"{rel} 을 찾지 못했다")


class _Req:
    """`client_entry` 가 보는 것은 `base_url` 하나다."""

    def __init__(self, base: str = "https://svc.example/"):
        self.base_url = base


# ── C1: 안내 페이지가 실재한다 ────────────────────────────────────────────────
def test_c1_the_guide_page_is_served(client):
    """게이트가 보내는 자리에 **실제 문서**가 있어야 한다.

    보내는 코드만 있고 목적지가 404 면, 브라우저 사용자는 제품 대신 오류를 본다 —
    「안내가 가리키는 것은 그 화면에 실재해야 한다」(feature-0046 §P0-R)의 라우트 판.
    """
    res = client.get("/install")
    assert res.status_code == 200, "게이트의 목적지가 200 이 아니다"
    assert "text/html" in res.headers.get("content-type", "")
    assert "DQA" in res.text and "설치" in res.text


def test_c1_the_guide_page_is_anonymous(client):
    """로그인하지 않은 사람이 도착하는 자리다 — 인증을 요구하면 아무도 못 본다."""
    res = client.get("/install")
    assert res.status_code == 200
    # 미인증 세션에서 로그인 화면으로 되돌리지 않는다.
    assert res.headers.get("location") is None


# ── C2: 화면 한 벌 · 딥링크는 정본이 만든다 ──────────────────────────────────
def test_c2_the_entry_payload_has_both_halves(client):
    body = client.get("/api/ai/client/entry").json()
    assert set(body.keys()) == {"app_link", "release"}, (
        "응답 셰이프가 바뀌면 화면이 조용히 한쪽을 잃는다"
    )


def test_c2_app_link_comes_from_the_canonical_builder():
    """⚠ 기대값을 리터럴로 적지 않는다 — 그러면 정본이 바뀌었을 때 이 테스트가

    「정본을 따라가는가」가 아니라 「옛 문자열 그대로인가」를 잠근다.
    """
    from shared import dqa_identity as ident

    out = client_release_router.client_entry(_Req())
    got = __import__("json").loads(out.body)["app_link"]
    assert got == ident.app_open_url("https://svc.example", "/")
    assert got.startswith(ident.SCHEME + "://")


def test_c2_the_open_link_carries_no_bearer_token():
    """이 링크는 미로그인 방문자의 화면에도 뜬다 — 자격증명이 실리면 안 된다."""
    out = client_release_router.client_entry(_Req())
    got = __import__("json").loads(out.body)["app_link"]
    assert "mat_" not in got and "token" not in got.lower()


def test_c2_a_broken_builder_does_not_break_the_guide(monkeypatch):
    """딥링크 조립이 실패해도 **설치 안내는 떠야 한다** — 받으러 온 사람이 우선이다."""
    import shared.dqa_identity as ident

    monkeypatch.setattr(ident, "app_open_url",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    body = __import__("json").loads(client_release_router.client_entry(_Req()).body)
    assert body["app_link"] is None
    assert "release" in body


# ── C3: 없는 것을 광고하지 않는다 ────────────────────────────────────────────
def test_c3_no_installer_means_no_release_block(monkeypatch):
    monkeypatch.setattr(client_release_router, "current_release", lambda: None)
    body = __import__("json").loads(client_release_router.client_entry(_Req()).body)
    assert body["release"] is None


def test_c3_the_release_block_is_reassembled_not_forwarded(monkeypatch):
    """매니페스트의 **모르는 필드가 그대로 흘러가지 않는다** (`current_release` 의 규율)."""
    monkeypatch.setattr(client_release_router, "current_release", lambda: {
        "version": "9.9.9", "filename": "DQAConnect-Setup-9.9.9.exe",
        "sha256": "f" * 64, "size": 123, "published_at": "2026-09-10T00:00:00+00:00",
        "notes": "n", "path": "/client/DQAConnect-Setup-9.9.9.exe",
        "update": {"filename": "x"}, "secret_internal_field": "LEAK",
    })
    rel = __import__("json").loads(client_release_router.client_entry(_Req()).body)["release"]
    assert "secret_internal_field" not in rel and "update" not in rel
    assert rel["download_url"] == "https://svc.example/client/DQAConnect-Setup-9.9.9.exe", (
        "받기 URL 은 현재 origin + 정본이 준 상대 경로여야 한다"
    )


# ── C4: 두 셸에 · 스타일시트보다 먼저 ────────────────────────────────────────
def test_c4_the_gate_is_wired_into_both_shells():
    for shell in ("index.html", "admin.html"):
        assert _GATE_TAG.search(_static(shell)), (
            f"{shell} 에 게이트가 없다 — 그 화면은 브라우저에 그대로 열린다"
        )


def test_c4_the_gate_runs_before_any_stylesheet():
    """뒤에 두면 CSS 를 기다리는 동안 화면이 반쯤 그려졌다가 튕긴다."""
    for shell in ("index.html", "admin.html"):
        html = _static(shell)
        gate = _GATE_TAG.search(html)
        first_css = re.search(r'<link[^>]+rel="stylesheet"', html)
        assert gate and first_css
        assert gate.start() < first_css.start(), f"{shell}: 게이트가 스타일시트 뒤에 있다"


def test_c4_the_gate_is_not_deferred():
    """`type="module"`·`defer`·`async` 는 전부 실행을 미룬다 — 동기여야 한다."""
    for shell in ("index.html", "admin.html"):
        html = _static(shell)
        tag = _GATE_TAG.search(html).group(0)
        assert "module" not in tag and "defer" not in tag and "async" not in tag


def test_c4_the_gate_asset_is_stamped():
    """`?v=` 없는 자산은 배포가 브라우저에 도달하지 못한다 (§13.1 자산 스탬프 규약)."""
    for shell in ("index.html", "admin.html"):
        assert '/static/client-gate.js?v=' in _static(shell)


# ── C5: 안내 페이지는 자기를 되보내지 않는다 ────────────────────────────────
def test_c5_the_guide_page_does_not_load_the_gate():
    assert "client-gate.js" not in _static("install.html"), (
        "설치 안내가 게이트를 실으면 자기 자신으로 무한히 되보낸다"
    )


# ── C6: 좌표 규약은 정본과 같은 문자열 ──────────────────────────────────────
def test_c6_the_gate_and_the_canonical_module_agree_on_the_signal():
    """사본이 갈리면 「앱 안인데 앱 밖으로 보이는」 화면이 생기고, 그 화면은 앱 창을 튕긴다.

    (`shared/dqa_identity.py` + `test_name_ssot.py` 가 명칭에 대해 하는 일과 같은 형태.)
    """
    gate = _static("client-gate.js")
    canonical = _static("app/client-bridge.js")
    for token in ('"client_port"', '"client_nonce"', '"dqa.bridge"'):
        assert token in gate, f"게이트가 {token} 을 쓰지 않는다"
        assert token in canonical, f"정본 모듈이 {token} 을 쓰지 않는다 — 규약이 옮겨갔다"


def test_c6_the_admin_shell_runs_the_canonical_module():
    """관리 콘솔에서도 좌표가 다음 화면으로 이어져야 한다 — 없으면 새로고침이 관리자를 튕긴다."""
    assert '/static/app/client-bridge.js?v=' in _static("admin.html")


# ── C7: 무엇을 막고 무엇을 막지 않는가 ──────────────────────────────────────
def _gated_paths() -> set[str]:
    block = re.search(r"var GATED = \{(.*?)\};", _static("client-gate.js"), re.S)
    assert block, "게이트 대상 집합을 읽지 못했다"
    return set(re.findall(r'"([^"]+)"\s*:', block.group(1)))


def _persist_surfaces() -> set[str]:
    block = re.search(r"_PERSIST_SURFACES = new Set\(\[(.*?)\]\)",
                      _static("app/client-bridge.js"), re.S)
    assert block, "정본 모듈의 보관 표면 집합을 읽지 못했다"
    return set(re.findall(r'"([^"]+)"', block.group(1)))


def test_c7_the_gated_set_is_the_app_shells_plus_admin():
    """사용자 결정 2026-09-10: 앱 루트 + 관리 콘솔."""
    assert _gated_paths() == _persist_surfaces() | {"/admin"}


def test_c7_anonymous_surfaces_are_not_gated():
    """공유 열람·외부 AI 연결·설치 안내는 **브라우저가 정상 경로**다 (2026-09-08 결정)."""
    gated = _gated_paths()
    for path in ("/install", "/healthz", "/ai/connect", "/ai/oauth/callback", "/share"):
        assert path not in gated


def test_c7_the_gate_has_no_escape_hatch():
    """사용자 결정 2026-09-10: 탈출구 없음. 우회 질의 파라미터를 슬쩍 두지 않는다."""
    gate = _static("client-gate.js")
    for hatch in ("browser=1", "skip_gate", "force_web", "nogate"):
        assert hatch not in gate


# ── C8: 익명 표 등재 ────────────────────────────────────────────────────────
def test_c8_security_md_records_the_new_anonymous_paths():
    """신규 익명 endpoint 는 `docs/SECURITY.md §7` 표 등재가 필수다 (§7.1 규칙)."""
    sec = _repo_doc("docs/SECURITY.md")
    for path in ("`/install`", "`/api/ai/client/entry`"):
        assert path in sec, f"{path} 가 익명 allowlist 표에 없다 — 정책·코드 drift"


# ── C9: 행위 하네스 배선 또는 gap 기록 ──────────────────────────────────────
def test_c9_behaviour_harness_runs_or_ci_gap_is_documented():
    """하네스를 돌리거나, 돌릴 수 없으면 그 **gap 이 문서에 기록**돼 있어야 한다.

    조용한 `skip` 은 운영에서만 통과하는 형태다 — skip 대신 «기록» 을 강제한다.
    """
    assert _HARNESS.exists(), "행위 하네스 파일 부재"
    node = shutil.which("node")
    if node:
        proc = subprocess.run(
            [node, str(_HARNESS)], cwd=str(_TESTS),
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "NODE_OPTIONS": ""},
        )
        if proc.returncode != 2:      # 2 = jsdom 미설치 → 아래 gap 경로로 강등
            assert proc.returncode == 0, (
                f"행위 하네스 FAIL:\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}"
            )
            return
    recorded = any(
        _CI_GAP_MARKER in p.read_text(encoding="utf-8")
        for p in [_FEATURE_DOCS / "REVIEW.md",
                  *sorted((_FEATURE_DOCS / "test-runs.d").glob("*.md"))]
        if p.exists()
    )
    assert recorded, (
        "행위 하네스를 실행할 수 없는데(node/jsdom 부재) 그 gap 이 문서에 없다. "
        f'REVIEW.md 또는 test-runs.d fragment 에 "{_CI_GAP_MARKER}" 를 기록하라 — '
        "조용한 skip 은 «검증했다» 로 오인된다"
    )


# ── N: 음성 대조군 (§16.7 G11-b) ────────────────────────────────────────────
def test_n1_the_tag_scan_rejects_a_deferred_gate():
    """C4 의 정규식이 실제로 «동기 classic» 만 통과시키는지 — 검사 자체의 유효성."""
    assert not _GATE_TAG.search(
        '<script type="module" src="/static/client-gate.js?v=dev"></script>')
    assert not _GATE_TAG.search('<script src="/static/client-gate.js"></script>')
    assert _GATE_TAG.search('<script src="/static/client-gate.js?v=dev"></script>')


def test_n2_the_gated_set_parser_reads_real_values():
    """C7 의 파서가 빈 집합을 내고도 통과하는 형태가 아닌지 확인한다."""
    got = _gated_paths()
    assert got and "/" in got, "게이트 대상 집합이 비었다 — 파서가 아무것도 못 읽었다"


# ── C10: 인가 로그인 착지점 예외가 실제 서버 동작과 맞물린다 ────────────────
def test_c10_the_oauth_login_landing_is_let_through():
    """게이트의 예외 접두가 **서버가 실제로 보내는 곳**과 같아야 한다.

    ⚠ 기대값을 리터럴로 적지 않는다 — `oauth_as.oauth_authorize` 가 미로그인일 때 만드는
    `next` 는 그 라우트의 경로다. 둘이 갈리면 예외가 조용히 무효가 되고, 외부 AI 연결이
    브라우저에서 끝나지 않는다(codex 적대 리뷰 2026-09-10 P1-1).
    """
    from routers import oauth_as as oauth_router

    route = next(r for r in oauth_router.router.routes
                 if getattr(r, "name", "") == "oauth_authorize")
    gate = _static("client-gate.js")
    prefix = re.search(r'var LOGIN_RETURN_PREFIX = "([^"]+)"', gate).group(1)
    assert route.path.startswith(prefix), (
        f"게이트 예외 접두({prefix})가 인가 라우트({route.path})를 덮지 않는다"
    )


def test_c10_the_exception_is_narrow():
    """예외는 그 접두에만 걸린다 — 아무 `next` 나 게이트를 여는 형태가 아니어야 한다."""
    gate = _static("client-gate.js")
    assert "indexOf(LOGIN_RETURN_PREFIX) === 0" in gate, (
        "접두 «시작» 검사가 아니면 `?next=/evil/api/ai/oauth/authorize` 가 통과한다"
    )


# ── C11: 저장소 판정은 읽기만 보지 않는다 ───────────────────────────────────
def test_c11_the_gate_probes_writability_not_just_readability():
    """`getItem` 은 되는데 `setItem` 이 던지는 창에서 정상 앱이 쫓겨나지 않아야 한다.

    (codex 적대 리뷰 2026-09-10 P2-3 — 동작 자체는 하네스 ⑦ 이 실측한다.)
    """
    gate = _static("client-gate.js")
    assert "storageIsUsable" in gate and "setItem" in gate


# ── C12: 판정 전에는 좌표를 지우지 않는다 (정본 모듈) ───────────────────────
def test_c12_the_canonical_module_defers_the_strip_until_adoption_settles():
    """비동기 보관이 끝나기 전에 주소를 비우면, 그 사이 새로고침한 앱 창에 신호가 0 이 된다.

    (codex 적대 리뷰 2026-09-10 P1-2 — 동작 자체는 하네스 ⑦ 이 실측한다.)
    """
    src = _static("app/client-bridge.js")
    assert "deferStrip" in src and "stripCoords" in src
    assert "_adoptIfTheBridgeAcceptsIt(port, nonce, stripCoords)" in src, (
        "보관 판정이 끝난 뒤 지우도록 콜백이 연결돼 있어야 한다"
    )


# ── C13: 「못 물어봤다」와 「없다」를 가른다 ─────────────────────────────────
def test_c13_the_guide_separates_unreachable_from_absent():
    """통신 장애를 «서버에 파일이 없음» 으로 확정 표시하지 않는다 (P2-5)."""
    html = _static("install.html")
    js = _static("install.js")
    assert 'id="actUnavailable"' in html and 'id="retryBtn"' in html
    assert 'only("actUnavailable")' in js


def test_c13_the_app_link_survives_a_withdrawn_release():
    """배포본을 철회해도 이미 설치한 사람의 «앱 열기» 는 남아야 한다 (P2-4)."""
    html = _static("install.html")
    js = _static("install.js")
    # 앱 열기 줄이 받기 블록 **밖**에 있다 — 안에 있으면 받기와 함께 숨는다.
    download_open = html.index('id="actDownload"')
    download_close = html.index("</section>", download_open)
    already = html.index('id="alreadyInstalled"')
    assert already > download_close, "앱 열기 줄이 받기 블록 안에 있다"
    assert "renderAppLink" in js
