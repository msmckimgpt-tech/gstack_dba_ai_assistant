"""TASK-20260619T021356-login-attempt-limit (Critical §12.3) — 로그인 시도 제한 회귀 테스트.

요청(보안 보강 6종 중 ②): 잘못된 로그인 시도 제한. 사용자 결정(2026-06-19):
계정 잠금 + IP throttle 둘 다, 보수적 프로파일(계정 5회→15분 자동해제, IP 20회/10분),
전부 env 설정 가능.

검증(`make test` agent 이미지, DB 없이 — IP throttle 은 실 동작, 나머지는 inspect.getsource):
  B1  config 기본값(5 / 15분 / 20 / 600초).
  B2  IP throttle 실 동작: MAX 실패 누적→throttled, clear→해제, window 밖 만료.
  B3  schema 헬퍼 _ensure_login_lockout_schema — 3 컬럼 ALTER + 멱등 + 양 경로 호출.
  B4  auth_login: IP throttle→is_locked→실패누적→성공리셋+IP clear, audit auth.lockout.
  B5  _login_record_failure: 증가 + 임계 도달 시 DATE_ADD 잠금 + 카운터 리셋.
  B6  _fetch_account_rows: is_locked DB NOW() 평가 컬럼.
  B7  _serialize_account: is_locked/locked_until/failed_login_attempts 노출.
  B8  admin unlock 엔드포인트: 권한 게이트 + _login_reset_lockout + audit auth.unlock.
  B9  password-reset 가 잠금도 해제(FailedLoginAttempts=0, LockedUntilAt=NULL).
  B10 audit builder: auth.lockout + auth.unlock 분기.
  F1  admin.js: 잠금 배지 + 해제 버튼 + triggerAccountUnlockFlow.
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
from routers import admin_accounts, auth  # feature-0012 P5b


def _read_static(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    with open(os.path.join(base, "static", name), "r", encoding="utf-8") as fh:
        return fh.read()


# ── B: backend ──────────────────────────────────────────────────────────────
def test_b1_config_defaults():
    assert app.LOGIN_MAX_FAILED_ATTEMPTS == 5
    assert app.LOGIN_LOCKOUT_MINUTES == 15
    assert app.LOGIN_IP_MAX_ATTEMPTS == 20
    assert app.LOGIN_IP_WINDOW_SEC == 600


def test_b2_ip_throttle_behavior():
    ip = "203.0.113.77"  # TEST-NET-3, 충돌 없는 고유 키
    app._login_ip_clear(ip)
    # 처음엔 throttle 아님
    assert app._login_ip_throttled(ip) is False
    # MAX-1 실패까지는 허용
    for _ in range(app.LOGIN_IP_MAX_ATTEMPTS - 1):
        app._login_ip_record_failure(ip)
    assert app._login_ip_throttled(ip) is False
    # MAX 번째 실패 → throttle 발동
    app._login_ip_record_failure(ip)
    assert app._login_ip_throttled(ip) is True
    # 성공 시 clear → 해제
    app._login_ip_clear(ip)
    assert app._login_ip_throttled(ip) is False


def test_b3_schema_helper():
    assert callable(app._ensure_login_lockout_schema)
    src = inspect.getsource(app._ensure_login_lockout_schema)
    assert "ADD COLUMN FailedLoginAttempts" in src
    assert "ADD COLUMN LockedUntilAt DATETIME NULL" in src
    assert "ADD COLUMN LastFailedLoginAt" in src
    assert "except Exception" in src  # 멱등
    # 양 경로 호출 (fast _ensure_seed_catchup + slow _ensure_web_tables)
    seed = inspect.getsource(app._ensure_seed_catchup)
    assert "_ensure_login_lockout_schema(conn)" in seed


def test_b4_auth_login_flow():
    src = inspect.getsource(auth.auth_login)
    assert "_login_ip_throttled" in src          # IP throttle 선검사
    assert 'account.get("is_locked")' in src      # 계정 잠금 게이트
    assert "_login_record_failure" in src         # 실패 누적
    assert "_login_reset_lockout" in src          # 성공 리셋
    assert "_login_ip_clear" in src               # 성공 IP clear
    assert "_login_ip_record_failure" in src      # 실패 IP 기록
    assert "auth.lockout" in src                  # 잠금 audit
    assert "429" in src                           # throttle/lock 응답


def test_b5_record_failure_locks_at_threshold():
    src = inspect.getsource(app._login_record_failure)
    assert "FailedLoginAttempts = FailedLoginAttempts + 1" in src
    assert "LOGIN_MAX_FAILED_ATTEMPTS" in src
    assert "DATE_ADD(NOW(), INTERVAL %s MINUTE)" in src   # DB 시계 잠금
    assert "FailedLoginAttempts = 0" in src               # 임계 시 리셋


def test_b6_fetch_account_rows_db_computed_lock():
    src = inspect.getsource(app._fetch_account_rows)
    assert "a.LockedUntilAt IS NOT NULL AND a.LockedUntilAt > NOW()" in src
    assert "AS is_locked" in src
    assert "failed_login_attempts" in src


def test_b7_serialize_exposes_lock():
    src = inspect.getsource(app._serialize_account)
    assert '"is_locked"' in src
    assert '"locked_until"' in src
    assert '"failed_login_attempts"' in src


def test_b8_admin_unlock_endpoint():
    assert hasattr(admin_accounts, "admin_account_unlock")
    src = inspect.getsource(admin_accounts.admin_account_unlock)
    assert "console.manage" in src and "account.update" in src   # 권한 게이트
    assert "_login_reset_lockout" in src
    assert "auth.unlock" in src


def test_b9_password_reset_clears_lockout():
    src = inspect.getsource(admin_accounts.admin_account_password_reset)
    assert "FailedLoginAttempts = 0" in src
    assert "LockedUntilAt = NULL" in src


def test_b10_audit_builder_auth_actions():
    src = inspect.getsource(app.build_audit_change_json)
    assert 'action == "auth.lockout"' in src
    assert 'action == "auth.unlock"' in src


# ── F: frontend ─────────────────────────────────────────────────────────────
def test_f1_admin_js_unlock_ui():
    # feature-0038 Cycle 4: 계정 pane 은 admin/accounts.js 로 분리(byte-동치 이동) — 합본 검사.
    js = _read_static("admin.js") + _read_static("admin/accounts.js")
    assert "triggerAccountUnlockFlow" in js
    assert "/unlock" in js
    assert "잠금 해제" in js
    assert 'statusBadge("잠김"' in js
    assert "base.is_locked" in js
