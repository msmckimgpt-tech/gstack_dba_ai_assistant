"""TASK-20260619T012028-share-link-expiry (Major §12.3, SECURITY.md §7.2) —
대화 공유 링크 시간 기반 만료(설정 가능) 회귀 테스트.

요청: 대화공유 링크 만료처리(설정 가능하도록). SECURITY.md §7.2 의 명시 방안:
WebConversationShares 에 ExpiresAt DATETIME NULL 추가, public GET/fork 시
NOW() > ExpiresAt → 410, 기본 NULL=무기한(기존 동작 무회귀, 명시 revoke 유지).

검증(`make test` agent 이미지, DB 없이 — inspect.getsource 함수 단위 + 동작 가드):
  B1 _SHARE_EXPIRY_MAX_SECONDS = 365일.
  B2 _share_row_expired 가드: 비-int share_id → DB 접근 없이 False.
  B3 schema 헬퍼 _ensure_web_share_links_expiry_column 존재 + ExpiresAt ALTER.
  B4 create 엔드포인트: expires_in_seconds 파싱 + 상한 400 + INSERT ExpiresAt DATE_ADD.
  B5 public_share_view: 만료 predicate(ViewCount UPDATE) + 만료 410 구분 메시지 + expires_at 응답.
  B6 public_share_fork: 만료 410 차단.
  B7 list 엔드포인트: IsExpired SELECT + is_expired/expires_at/is_revoked 노출.
  B8 audit builder conversation.share.create: expires_in_seconds 기록.
  B9 _share_load_active SELECT 에 ExpiresAt 포함.
  F1 frontend app.js: promptShareExpiry + SHARE_EXPIRY_PRESETS + expires_in_seconds body.
  F2 frontend share.js: shareExpiry 렌더 + 410 body.error 구분.
  F3 frontend share.html: shareExpiry span.
"""
from __future__ import annotations

import inspect
import os
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


def _static_path(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    return os.path.join(base, "static", name)


def _read_static(name: str) -> str:
    with open(_static_path(name), "r", encoding="utf-8") as fh:
        return fh.read()


# ── B: backend ──────────────────────────────────────────────────────────────
def test_b1_max_seconds_is_365_days():
    assert app._SHARE_EXPIRY_MAX_SECONDS == 365 * 24 * 60 * 60


def test_b2_share_row_expired_guard_non_int_returns_false():
    # 비-int share_id 는 conn 접근 전에 False — conn=None 으로도 안전(DB 불요).
    assert app._share_row_expired(None, "not-an-int") is False
    assert app._share_row_expired(None, None) is False


def test_b3_schema_helper_alters_expires_at():
    assert callable(app._ensure_web_share_links_expiry_column)
    src = inspect.getsource(app._ensure_web_share_links_expiry_column)
    assert "ADD COLUMN ExpiresAt DATETIME NULL" in src
    # 멱등(try/except) — 기존 배포 재실행 안전.
    assert "except Exception" in src


def test_b4_create_endpoint_parses_and_inserts_expiry():
    src = inspect.getsource(app.create_conversation_share)
    assert 'data.get("expires_in_seconds")' in src
    # 상한 초과 거부.
    assert "_SHARE_EXPIRY_MAX_SECONDS" in src
    assert "만료 기간이 너무 깁니다" in src
    # 0/음수 = 무기한 취급.
    assert "무기한" in src
    # INSERT 가 ExpiresAt 컬럼 + DATE_ADD(NOW()) 사용.
    assert "ExpiresAt" in src
    assert "DATE_ADD(NOW(), INTERVAL %s SECOND)" in src
    # 응답에 expires_at.
    assert '"expires_at"' in src


def test_b5_public_view_enforces_expiry():
    src = inspect.getsource(app.public_share_view)
    # ViewCount UPDATE 가 만료 predicate 포함 — 만료뷰 카운트 인플레 차단.
    assert "ExpiresAt IS NULL OR ExpiresAt > NOW()" in src
    # 만료 시 취소와 구분된 410 메시지.
    assert "만료되었습니다" in src
    assert "_share_row_expired" in src
    # 응답 share 에 expires_at.
    assert '"expires_at"' in src


def test_b6_fork_blocks_expired():
    src = inspect.getsource(app.public_share_fork)
    assert "_share_row_expired" in src
    assert "만료되었습니다" in src


def test_b7_list_exposes_expiry_fields():
    src = inspect.getsource(app.list_conversation_shares)
    assert "IsExpired" in src
    assert '"is_expired"' in src
    assert '"expires_at"' in src
    assert '"is_revoked"' in src


def test_b8_audit_builder_records_expiry():
    src = inspect.getsource(app.build_audit_change_json)
    # conversation.share.create 분기가 expires_in_seconds 화이트리스트.
    assert 'request_ctx.get("expires_in_seconds")' in src


def test_b9_share_load_active_selects_expires_at():
    src = inspect.getsource(app._share_load_active)
    assert "ExpiresAt" in src


# ── F: frontend ─────────────────────────────────────────────────────────────
def test_f1_app_js_expiry_picker():
    js = _read_static("app.js")
    assert "function promptShareExpiry" in js
    assert "SHARE_EXPIRY_PRESETS" in js
    assert "expires_in_seconds" in js
    # 만료 선택 취소 시 생성 중단.
    assert "choice.cancelled" in js


def test_f2_share_js_renders_expiry_and_distinct_410():
    js = _read_static("share.js")
    assert "shareExpiry" in js
    assert "share.expires_at" in js
    # 410 에서 서버 메시지(body.error)로 만료/취소 구분.
    assert "body.error" in js


def test_f3_share_html_has_expiry_span():
    html = _read_static("share.html")
    assert 'id="shareExpiry"' in html
