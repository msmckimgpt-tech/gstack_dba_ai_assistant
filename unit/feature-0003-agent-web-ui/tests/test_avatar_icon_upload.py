"""TASK-0268 — 프로필 아바타 / 제품 아이콘 이미지 업로드 검증.

검증 대상(`make test` agent 이미지, DB/MinIO 없이 monkeypatch):
  S1  _sniff_image: PNG/JPEG/WEBP 매직바이트 허용, SVG/GIF/임의바이트 거부(클라이언트 MIME 불신).
  S2  _store_image_upload: 빈 파일·초과 크기·미지원 형식 거부, 정상 PNG 는 prefix/owner/uuid.ext object key.
  S3  _avatar_url_for / _product_icon_url_for: object key 있으면 /api/... URL + 해시 캐시버스터, 없으면 None.
  S4  서빙 엔드포인트 컨텐츠타입 역추론(_serve_image_object): 확장자→content-type, 미설정 404.
  A1  제품 아이콘 업로드/삭제 권한 게이트(product.manage 없으면 403).
"""
from __future__ import annotations

import sys
import types

import app


def _install_storage(monkeypatch, **funcs):
    """`from web.modules import storage_minio` 가 fake 를 잡도록 web/web.modules 패키지 체인 등록.

    런타임은 src 가 /app/web 로 매핑돼 `web.modules.storage_minio` 인데, 테스트 env(PYTHONPATH=src)
    엔 web 패키지가 없으므로 sys.modules 에 web → web.modules → storage_minio 체인을 가짜로 심는다.
    """
    fake = types.ModuleType("web.modules.storage_minio")
    for k, v in funcs.items():
        setattr(fake, k, v)
    # 예외 클래스도 노출(코드가 storage_minio.StorageConfigError 등 참조 가능)
    fake.StorageConfigError = type("StorageConfigError", (RuntimeError,), {})
    fake.StorageOperationError = type("StorageOperationError", (RuntimeError,), {})
    web_pkg = sys.modules.get("web") or types.ModuleType("web")
    web_mods = sys.modules.get("web.modules") or types.ModuleType("web.modules")
    setattr(web_mods, "storage_minio", fake)
    setattr(web_pkg, "modules", web_mods)
    monkeypatch.setitem(sys.modules, "web", web_pkg)
    monkeypatch.setitem(sys.modules, "web.modules", web_mods)
    monkeypatch.setitem(sys.modules, "web.modules.storage_minio", fake)
    return fake


# 최소 유효 이미지 매직바이트
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
_JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
_WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 12
_SVG = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
_GIF = b"GIF89a" + b"\x00" * 20


# ── S1: 매직바이트 판별 ──────────────────────────────────────────────────────

def test_s1_sniff_allows_real_images():
    assert app._sniff_image(_PNG, "image/png") == ("png", "image/png")
    assert app._sniff_image(_JPG, "image/jpeg") == ("jpg", "image/jpeg")
    assert app._sniff_image(_WEBP, "image/webp") == ("webp", "image/webp")


def test_s1_sniff_rejects_svg_gif_and_lying_mime():
    # SVG(스크립트 가능)·GIF 거부
    assert app._sniff_image(_SVG, "image/svg+xml") is None
    assert app._sniff_image(_GIF, "image/gif") is None
    # 클라이언트가 image/png 라 주장해도 실제 바이트가 아니면 거부(MIME 불신)
    assert app._sniff_image(b"not an image at all", "image/png") is None
    assert app._sniff_image(b"", "image/png") is None


# ── S2: 저장 검증 ────────────────────────────────────────────────────────────

def test_s2_store_rejects_empty_oversize_unsupported(monkeypatch):
    puts = []
    _install_storage(monkeypatch, put_object_bytes=lambda key, body, **kw: puts.append((key, len(body))))

    # 빈
    k, err = app._store_image_upload(b"", prefix="avatars", owner_id=1, max_bytes=100, mime_hint="image/png")
    assert k is None and "빈" in err
    # 초과
    k, err = app._store_image_upload(_PNG + b"x" * 1000, prefix="avatars", owner_id=1, max_bytes=10, mime_hint="image/png")
    assert k is None and "큽" in err
    # 미지원(SVG)
    k, err = app._store_image_upload(_SVG, prefix="avatars", owner_id=1, max_bytes=10_000, mime_hint="image/svg+xml")
    assert k is None and "형식" in err
    assert puts == []  # 거부 시 MinIO put 안 함


def test_s2_store_accepts_png_object_key(monkeypatch):
    puts = []
    _install_storage(monkeypatch, put_object_bytes=lambda key, body, **kw: puts.append((key, kw.get("content_type"))))

    key, ctype = app._store_image_upload(_PNG, prefix="avatars", owner_id=42, max_bytes=10_000, mime_hint="image/png")
    assert key is not None
    assert key.startswith("avatars/42/") and key.endswith(".png")
    assert ctype == "image/png"
    assert len(puts) == 1 and puts[0][1] == "image/png"


# ── S3: URL 헬퍼 ─────────────────────────────────────────────────────────────

def test_s3_url_helpers():
    assert app._avatar_url_for(0, "k") is None       # invalid id
    assert app._avatar_url_for(5, None) is None       # no key → Identicon
    u = app._avatar_url_for(5, "avatars/5/abc.png")
    assert u.startswith("/api/avatars/5?v=") and len(u.split("v=")[1]) == 12

    assert app._product_icon_url_for(0, "k") is None
    assert app._product_icon_url_for(3, None) is None
    u = app._product_icon_url_for(3, "product-icons/3/x.webp")
    assert u.startswith("/api/products/3/icon?v=")


def test_s3_url_cachebuster_changes_with_key():
    u1 = app._avatar_url_for(5, "avatars/5/a.png")
    u2 = app._avatar_url_for(5, "avatars/5/b.png")
    assert u1 != u2  # object key 바뀌면 캐시버스터도 바뀜(즉시 갱신)


# ── S4: 서빙 컨텐츠타입 ──────────────────────────────────────────────────────

def test_s4_serve_content_type_and_404(monkeypatch):
    _install_storage(monkeypatch, get_object_bytes=lambda key: _PNG)

    resp = app._serve_image_object("avatars/1/x.png")
    assert resp.media_type == "image/png"
    resp2 = app._serve_image_object("avatars/1/y.webp")
    assert resp2.media_type == "image/webp"
    # 미설정 → 404 JSON
    resp3 = app._serve_image_object(None)
    assert resp3.status_code == 404


# ── A1: 제품 아이콘 권한 게이트 ──────────────────────────────────────────────

class _Conn:
    def cursor(self, *a, **k):
        class _C:
            def execute(self, *a, **k): pass
            def fetchone(self): return None
            def close(self): pass
        return _C()
    def close(self): pass


class _Req:
    def __init__(self):
        self.query_params = {}


def test_a1_product_icon_delete_requires_manage(client, as_account):
    # P5b DI seam Phase 3: delete_product_icon 가 account=Depends(require_permission("product.manage")) 로
    # 마이그됨 → 직접 함수호출 대신 TestClient + as_account override. require_permission 은 override 하지 않고
    # 실제 _account_has_permission 검사를 그대로 타므로, product.manage 없는 계정이면 403.
    as_account(perms={"console.access": True})  # product.manage 없음
    resp = client.delete("/api/admin/products/7/icon")
    assert resp.status_code == 403


# ── TASK-0293: 역할 아이콘 URL 헬퍼 + 관리 콘솔 아바타/아이콘 권한 게이트 ──────────

def test_s3_role_icon_url_helper():
    # _role_icon_url_for: object key 있으면 /api/roles/<id>/icon URL + 12자 해시 캐시버스터, 없으면 None.
    assert app._role_icon_url_for(0, "k") is None         # invalid id
    assert app._role_icon_url_for(5, None) is None        # no key → Identicon
    u = app._role_icon_url_for(5, "role-icons/5/abc.png")
    assert u.startswith("/api/roles/5/icon?v=") and len(u.split("v=")[1]) == 12
    # object key 바뀌면 캐시버스터도 바뀜(즉시 갱신).
    assert app._role_icon_url_for(5, "role-icons/5/a.png") != app._role_icon_url_for(5, "role-icons/5/b.png")


def test_a1_role_icon_delete_requires_role_update(monkeypatch):
    # console.access + console.manage 보유, role.update 없음 → 403 (RBAC 게이트).
    actor = {"id": 1, "permissions": {"console.access": True, "console.manage": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _Conn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (actor, None))
    resp = app.admin_delete_role_icon(3, _Req())
    assert resp.status_code == 403


def test_a1_role_icon_delete_requires_console_manage(monkeypatch):
    # console.access 만(console.manage 없음) → 403.
    actor = {"id": 1, "permissions": {"console.access": True, "role.update": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _Conn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (actor, None))
    resp = app.admin_delete_role_icon(3, _Req())
    assert resp.status_code == 403


def test_a1_account_avatar_delete_requires_account_update(monkeypatch):
    # console.access + console.manage 보유, account.update 없음 → 403 (perm 체크가 _load 전에 선차단).
    actor = {"id": 1, "permissions": {"console.access": True, "console.manage": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _Conn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (actor, None))
    resp = app.admin_delete_account_avatar(9, _Req())
    assert resp.status_code == 403
