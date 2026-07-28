"""feature-0014 asset-stamp-cache-integrity: 롤링 배포 창의 캐시 오염 차단 계약.

불변식 — **응답이 `immutable` 로 표시되려면 요청 `?v=` 가 이 replica 의 빌드 스탬프와
같아야 한다.** 불일치면 `no-store`. 이게 없으면 롤링 창에 구 replica 가 신 스탬프 URL 에
구 바이트로 200 응답한 것이 브라우저 캐시에 1년 고착된다(2026-07-28 라이브 실측).

여기서 검증하는 것은 **정책 판정(decide_cache_control)** 과 **ASGI 래퍼가 실제 응답 헤더에
그 판정을 싣는지**다. 엣지(Caddy)가 이 헤더를 덮어쓰지 않는다는 짝 계약은
`test_caddyfile_no_static_cache_override` 가 설정 파일로 고정한다.

`make test`(agent 이미지, --no-deps) 에서 DB 없이 실행된다.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

import static_cache

STAMP = "728b9767fdad"
OLD_STAMP = "67eaf1a90cf0"

IMMUTABLE = b"public, max-age=31536000, immutable"
NO_STORE = b"no-store"


# ── 1. 정책 판정 ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "path,qs,stamp,expected",
    [
        # 스탬프 없는 요청 = 기존 동작(ETag/304) 유지 — 헤더 미설정.
        ("/graph/graph.js", b"", STAMP, None),
        ("/styles.css", b"foo=1", STAMP, None),
        # 내 빌드와 일치 → immutable (URL 이 내용에 결합된 경우에만 안전).
        ("/graph/graph.js", f"v={STAMP}".encode(), STAMP, IMMUTABLE),
        # 다른 빌드의 스탬프 → no-store. **본 수정의 핵심** — 롤링 창의 구 replica 응답.
        ("/graph/graph.js", f"v={OLD_STAMP}".encode(), STAMP, NO_STORE),
        ("/admin.js", b"v=dev", STAMP, NO_STORE),
        # vendor 는 라이브러리 pin(별개 버전 축) — 빌드 해시와 비교하면 상시 불일치가 되어
        # 캐시를 통째로 잃는다. 종전 동작 유지. **두 mount 규약 모두** 커버 — Starlette 버전에
        # 따라 하위 앱이 받는 path 가 잘린 형태/전체 형태로 갈린다(통합 테스트가 적발한 접합부).
        ("/vendor/g6.min.js", b"v=5.1.1", STAMP, IMMUTABLE),
        ("/static/vendor/g6.min.js", b"v=5.1.1", STAMP, IMMUTABLE),
        ("/static/vendor/pixi.min.js", b"v=8.19.0", STAMP, IMMUTABLE),
        # 반대로 vendor 가 아닌 빌드 자산은 두 규약 모두에서 스탬프 판정을 받아야 한다.
        ("/static/graph/graph.js", f"v={OLD_STAMP}".encode(), STAMP, NO_STORE),
        ("/static/graph/graph.js", f"v={STAMP}".encode(), STAMP, IMMUTABLE),
        # 스탬프 미주입 빌드(dev) → fail-safe 로 헤더 미설정(캐싱은 잃되 오염은 없음).
        ("/graph/graph.js", f"v={STAMP}".encode(), None, None),
        ("/graph/graph.js", b"v=dev", "", None),
    ],
)
def test_decide_cache_control(path, qs, stamp, expected):
    assert static_cache.decide_cache_control(path=path, query_string=qs, build_stamp=stamp) == expected


def test_mismatch_is_the_default_for_unknown_stamps():
    """알 수 없는 스탬프는 전부 no-store — allowlist 가 아니라 '일치할 때만 허용' 이어야 한다."""
    for bogus in ("", "x", "0" * 12, STAMP[:-1], STAMP + "0", STAMP.upper()):
        got = static_cache.decide_cache_control(
            path="/app.js", query_string=f"v={bogus}".encode(), build_stamp=STAMP
        )
        assert got == NO_STORE, (bogus, got)


def test_duplicate_v_params_use_first_and_do_not_crash():
    got = static_cache.decide_cache_control(
        path="/app.js", query_string=f"v={STAMP}&v={OLD_STAMP}".encode(), build_stamp=STAMP
    )
    assert got == IMMUTABLE
    got = static_cache.decide_cache_control(
        path="/app.js", query_string=f"v={OLD_STAMP}&v={STAMP}".encode(), build_stamp=STAMP
    )
    assert got == NO_STORE


def test_malformed_query_does_not_raise():
    for qs in (b"v=%", b"\xff\xfe", b"v", b"=v", b"v=" + b"a" * 5000):
        static_cache.decide_cache_control(path="/app.js", query_string=qs, build_stamp=STAMP)


# ── 2. 빌드 스탬프 사이드카 로드 ───────────────────────────────────────────────

def test_read_build_stamp(tmp_path: Path):
    (tmp_path / static_cache.STAMP_SIDECAR).write_text(STAMP + "\n", encoding="utf-8")
    assert static_cache.read_build_stamp(tmp_path) == STAMP


def test_read_build_stamp_absent_is_none(tmp_path: Path):
    assert static_cache.read_build_stamp(tmp_path) is None


def test_read_build_stamp_blank_is_none(tmp_path: Path):
    (tmp_path / static_cache.STAMP_SIDECAR).write_text("  \n", encoding="utf-8")
    assert static_cache.read_build_stamp(tmp_path) is None


# ── 3. ASGI 래퍼가 실제 응답 헤더에 판정을 싣는가 ──────────────────────────────

def _run_asgi(mw, path: str, query: bytes, status: int = 200, headers=None):
    """미들웨어를 1 요청 태우고 http.response.start 헤더를 돌려준다."""
    sent: list[dict] = []

    async def inner_app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": list(headers or [(b"content-type", b"application/javascript")]),
        })
        await send({"type": "http.response.body", "body": b"x"})

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    mw.app = inner_app
    scope = {"type": "http", "path": path, "query_string": query, "method": "GET"}
    asyncio.run(mw(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    return {k.lower(): v for k, v in start["headers"]}


def _mw(stamp=STAMP):
    return static_cache.StaticCacheHeadersMiddleware(None, static_dir="/nonexistent", build_stamp=stamp)


def test_wrapper_sets_immutable_on_match():
    h = _run_asgi(_mw(), "/graph/graph.js", f"v={STAMP}".encode())
    assert h[b"cache-control"] == IMMUTABLE
    assert b"x-asset-stamp" not in h


def test_wrapper_sets_no_store_on_mismatch():
    h = _run_asgi(_mw(), "/graph/graph.js", f"v={OLD_STAMP}".encode())
    assert h[b"cache-control"] == NO_STORE
    # 관측용 마커 — 롤아웃 창의 버전 스큐 발생량을 엣지 로그로 셀 수 있어야 한다.
    assert h[b"x-asset-stamp"] == b"mismatch"


def test_wrapper_replaces_upstream_cache_control_not_appends():
    """StaticFiles 가 먼저 Cache-Control 을 달았어도 중복 헤더가 생기면 안 된다(모호한 캐싱)."""
    h_list: list = []

    async def inner_app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"cache-control", b"public, max-age=60"), (b"etag", b'"abc"')],
        })
        await send({"type": "http.response.body", "body": b"x"})

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    mw = _mw()
    mw.app = inner_app
    asyncio.run(mw({"type": "http", "path": "/app.js", "query_string": f"v={STAMP}".encode()}, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    cc = [v for (k, v) in start["headers"] if k.lower() == b"cache-control"]
    assert cc == [IMMUTABLE], cc
    h_list.extend(start["headers"])
    assert (b"etag", b'"abc"') in h_list   # 다른 헤더는 보존


def test_wrapper_leaves_headers_alone_without_v():
    h = _run_asgi(_mw(), "/graph/graph.js", b"")
    assert b"cache-control" not in h


def test_wrapper_applies_to_304_revalidation():
    """조건부 GET 의 304 에도 같은 정책이 실려야 클라이언트 freshness 가 갱신된다."""
    h = _run_asgi(_mw(), "/app.js", f"v={OLD_STAMP}".encode(), status=304, headers=[(b"etag", b'"a"')])
    assert h[b"cache-control"] == NO_STORE


def test_wrapper_skips_non_cacheable_status():
    h = _run_asgi(_mw(), "/missing.js", f"v={STAMP}".encode(), status=404)
    assert b"cache-control" not in h


def test_wrapper_is_fail_open_on_non_http_scope():
    """websocket/lifespan scope 는 그대로 통과(헤더 조작 없음)."""
    seen = []

    async def inner_app(scope, receive, send):
        seen.append(scope["type"])

    async def send(_m):
        pass

    async def receive():
        return {}

    mw = _mw()
    mw.app = inner_app
    asyncio.run(mw({"type": "lifespan"}, receive, send))
    assert seen == ["lifespan"]


# ── 4. 엣지가 판정을 덮어쓰지 않는다 (짝 계약) ─────────────────────────────────

def _caddyfile_text() -> str:
    here = Path(__file__).resolve()
    # …/unit/feature-0003-agent-web-ui/tests/<this>  →  parents[2] == unit/
    unit_dir = here.parents[2]
    cf = unit_dir / "feature-0006-lan-proxy-access" / "src" / "caddy" / "Caddyfile"
    if not cf.exists():   # 컨테이너 레이아웃(unit 트리 미동봉)에서는 skip
        pytest.skip(f"Caddyfile 미동봉 레이아웃: {cf}")
    return cf.read_text(encoding="utf-8")


def test_caddyfile_no_static_cache_override():
    """엣지가 `/static` 에 Cache-Control 을 강제하면 본 모듈의 불변식이 무력화된다.

    feature-0027 이 두었던 `header @static_versioned Cache-Control immutable` 은
    feature-0014 에서 제거됐다. 되살아나면 롤링 창 캐시 오염이 그대로 재발하므로 FAIL.
    """
    # 주석 줄은 제외 — 제거 사유 설명이 규칙 잔존으로 오탐되면 안 된다(설명은 오히려 보존 대상).
    active = [ln.strip() for ln in _caddyfile_text().splitlines() if not ln.strip().startswith("#")]

    offenders = [ln for ln in active if ln.startswith("header ") and "Cache-Control" in ln]
    assert not offenders, f"엣지가 Cache-Control 을 강제하면 스탬프 일치 판정이 무력화된다: {offenders}"

    matcher = [ln for ln in active if ln.startswith("@static_versioned")]
    assert not matcher, f"matcher 잔존 — 규칙 부활 위험: {matcher}"


# ── 5. 통합: 실 injector → 실 static 트리 → 실 StaticFiles 서빙 ────────────────
#
# 위 1~4 는 각 절반을 격리 검증한다. 실제 사고는 **두 절반의 접합부**(빌드가 쓴 스탬프 ≠
# 런타임이 읽는 스탬프, 사이드카가 이미지에 안 들어감, mount 경로 불일치)에서 난다.
# 여기서는 저장소의 **실제 static 트리 사본**에 **실제 injector** 를 돌리고, 그 결과를
# **실제 StaticFiles + 래퍼**로 서빙해 헤더를 확인한다 — DB 불요.

def _real_static_dir() -> Path:
    d = Path(__file__).resolve().parents[1] / "src" / "static"
    if not (d / "admin.js").exists():
        pytest.skip(f"static 트리 미동봉 레이아웃: {d}")
    return d


def _injector():
    import importlib.util

    # …/unit/feature-0003-agent-web-ui/tests/<this>  →  parents[2] == unit/
    script = (
        Path(__file__).resolve().parents[2]
        / "feature-0002-agent-core" / "src" / "scripts" / "inject_asset_stamp.py"
    )
    if not script.exists():
        pytest.skip(f"injector 미동봉: {script}")
    spec = importlib.util.spec_from_file_location("inject_asset_stamp", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_end_to_end_build_then_serve(tmp_path: Path):
    import shutil
    import sys

    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.testclient import TestClient

    src = _real_static_dir()
    root = tmp_path / "static"
    shutil.copytree(src, root)

    mod = _injector()
    argv = sys.argv
    sys.argv = ["inject_asset_stamp.py", "--root", str(root)]
    try:
        assert mod.main() == 0
    finally:
        sys.argv = argv

    stamp = static_cache.read_build_stamp(root)
    assert stamp and re.fullmatch(r"[0-9a-f]{12}", stamp), stamp

    app = FastAPI()
    app.mount(
        "/static",
        static_cache.StaticCacheHeadersMiddleware(StaticFiles(directory=root), static_dir=root),
        name="static",
    )
    client = TestClient(app)

    # (a) 내 빌드 스탬프 → immutable
    r = client.get(f"/static/admin.js?v={stamp}")
    assert r.status_code == 200
    assert r.headers["cache-control"] == IMMUTABLE.decode()

    # (b) 다른 빌드 스탬프 → no-store. **롤링 창의 구 replica 응답이 여기 해당** — 이게
    #     immutable 로 나가면 브라우저 캐시가 1년 오염된다(2026-07-28 라이브 사고).
    r = client.get(f"/static/admin.js?v={OLD_STAMP}")
    assert r.status_code == 200
    assert r.headers["cache-control"] == NO_STORE.decode()
    assert r.headers["x-asset-stamp"] == "mismatch"

    # (c) placeholder(?v=dev) 도 불일치 — 미주입 HTML 이 참조해도 오염되지 않는다
    assert client.get("/static/admin.js?v=dev").headers["cache-control"] == NO_STORE.decode()

    # (d) 스탬프 없는 요청 → 기존 ETag/304 경로 (Cache-Control 미설정)
    assert "cache-control" not in client.get("/static/admin.js").headers

    # (e) HTML 이 실제로 참조하는 URL 이 바로 (a) 경로여야 한다 — 빌드가 쓴 값과 런타임이
    #     읽는 값이 어긋나면 전 자산이 상시 no-store 가 된다(캐시 전면 상실).
    admin_html = (root / "admin.html").read_text(encoding="utf-8")
    assert f"/static/admin.js?v={stamp}" in admin_html

    # (f) vendor pin 은 별개 버전 축 — 종전대로 immutable.
    #     (여기서 no-store 가 나오면 라이브러리 캐시를 통째로 잃는다 — 실제로 초판이 이 경로에서
    #      깨졌고 본 통합 테스트가 적발했다: Mount 가 하위 앱에 넘기는 path 규약 차이.)
    r = client.get("/static/vendor/g6.min.js?v=5.1.1")
    assert r.status_code == 200, "vendor 자산이 트리에 없으면 이 계약을 검증할 수 없다"
    assert r.headers["cache-control"] == IMMUTABLE.decode()

    # (g) 마운트가 하위 앱에 넘기는 path 규약과 무관하게 동작해야 한다 — 실제 서빙 경로로
    #     빌드 자산/vendor 양쪽을 모두 확인했으므로 규약이 바뀌어도 여기서 잡힌다.
    assert client.get(f"/static/graph/graph.js?v={stamp}").headers["cache-control"] == IMMUTABLE.decode()
    assert client.get(f"/static/graph/graph.js?v={OLD_STAMP}").headers["cache-control"] == NO_STORE.decode()
