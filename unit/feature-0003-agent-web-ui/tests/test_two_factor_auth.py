"""TASK-20260619T040000-two-factor-auth (Critical §12.3) — 2단계 인증(TOTP) 회귀 테스트.

요청(보안 보강 6종 중 ⑥): 2단계 인증. pyotp 없이 stdlib RFC 6238 TOTP. secret 은 cred_crypto
(DEK/KEK, AAD=totp:{account_id})로 암호화 저장. 로그인 2단계(pending token=DEK-HMAC). 백업코드.
사용자 opt-in self-service + 관리자 강제 해제(분실 복구). 기본 미설정=2FA 미사용(무회귀).

검증(`make test` agent 이미지, DB 없이 — TOTP/백업코드 순수함수 실 동작 + inspect.getsource):
  B1 TOTP roundtrip: 같은 시각 코드 검증 True·오답 False·drift 창 밖(±2 step) False.
  B2 _totp_generate_secret base32 + _totp_otpauth_uri(secret/issuer/digits).
  B3 백업코드: 해시 결정성·생성 개수/유일성.
  B4 schema 헬퍼 WebAccountTotp + 양 경로 호출.
  B5 등록 엔드포인트 setup/confirm/disable(비번 재확인) + cred_crypto 암호화.
  B6 로그인 2단계: auth_login totp_required 분기 + /api/auth/login/totp(pending token·백업코드).
  B7 admin 강제 해제 + audit auth.totp.*.
  B8 serialize totp_enabled + _fetch_account_rows 노출.
  F1 frontend: 로그인 TOTP 프롬프트 + 프로필 2FA + admin 배지/해제.
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


# ── B1: TOTP roundtrip (pure, real behavior) ────────────────────────────────
def test_b1_totp_roundtrip_and_drift():
    secret = app._totp_generate_secret()
    ts = 1_700_000_000.0
    code = app._totp_code_at(secret, ts)
    assert len(code) == app._TOTP_DIGITS and code.isdigit()
    # 같은 시각 → 검증 통과
    assert app._totp_verify(secret, code, ts) is True
    # 오답 → 실패
    wrong = "000000" if code != "000000" else "111111"
    assert app._totp_verify(secret, wrong, ts) is False
    # drift 창 안(±1 step) → 통과
    assert app._totp_verify(secret, code, ts + app._TOTP_STEP) is True
    # drift 창 밖(+2 step) → 실패
    assert app._totp_verify(secret, code, ts + 2 * app._TOTP_STEP + 1) is False
    # 형식 불량 → 실패
    assert app._totp_verify(secret, "abc", ts) is False


def test_b2_secret_and_otpauth():
    import base64
    s = app._totp_generate_secret()
    # base32 디코드 가능(패딩 보정).
    base64.b32decode(s + "=" * ((8 - len(s) % 8) % 8), casefold=True)
    uri = app._totp_otpauth_uri(s, "alice", issuer="DQA")
    assert uri.startswith("otpauth://totp/")
    assert f"secret={s}" in uri
    assert "issuer=DQA" in uri and f"digits={app._TOTP_DIGITS}" in uri


def test_b3_backup_codes():
    assert app._totp_backup_hash("ABC-123") == app._totp_backup_hash("abc123")  # 정규화(대문자·하이픈 제거)
    codes = app._totp_generate_backup_codes()
    assert len(codes) == app._TOTP_BACKUP_CODE_COUNT
    assert len(set(codes)) == len(codes)  # 유일


# ── B4~B8: source ────────────────────────────────────────────────────────────
def test_b4_schema():
    src = inspect.getsource(app._ensure_web_account_totp_schema)
    assert "WebAccountTotp" in src and "SecretEnc" in src and "BackupCodesJson" in src
    seed = inspect.getsource(app._ensure_seed_catchup)
    assert "_ensure_web_account_totp_schema(conn)" in seed


def test_b5_enrollment_endpoints():
    for fn in ("auth_totp_setup", "auth_totp_confirm", "auth_totp_disable"):
        assert hasattr(auth, fn), fn
    setup = inspect.getsource(auth.auth_totp_setup)
    assert "_totp_encrypt_secret" in setup and "otpauth_uri" in setup
    confirm = inspect.getsource(auth.auth_totp_confirm)
    assert "_totp_verify" in confirm and "backup_codes" in confirm and "Enabled=1" in confirm
    disable = inspect.getsource(auth.auth_totp_disable)
    assert "_verify_password" in disable  # 비번 재확인


def test_b6_login_two_step():
    login = inspect.getsource(auth.auth_login)
    assert "_totp_is_enabled" in login and "totp_required" in login and "_totp_pending_token" in login
    assert hasattr(auth, "auth_login_totp")
    step2 = inspect.getsource(auth.auth_login_totp)
    assert "_totp_verify_pending_token" in step2
    assert "_totp_verify" in step2 and "_totp_consume_backup_code" in step2
    assert "_issue_auth_session" in step2


def test_b7_admin_disable_and_audit():
    assert hasattr(admin_accounts, "admin_account_totp_disable")
    adm = inspect.getsource(admin_accounts.admin_account_totp_disable)
    assert "console.manage" in adm and "auth.totp.admin_disable" in adm
    builder = inspect.getsource(app.build_audit_change_json)
    for act in ("auth.totp.enable", "auth.totp.disable", "auth.totp.admin_disable", "auth.login.totp"):
        assert f'action == "{act}"' in builder


def test_b8_serialize_and_fetch():
    ser = inspect.getsource(app._serialize_account)
    assert '"totp_enabled"' in ser
    fetch = inspect.getsource(app._fetch_account_rows)
    assert "WebAccountTotp" in fetch and "totp_enabled" in fetch


# ── F1: frontend ─────────────────────────────────────────────────────────────
def test_b9_bruteforce_absorption():
    # outside-voice MAJOR 흡수: 2FA 분기는 잠금/IP 리셋을 미룬다(2단계 완료 시에만).
    login = inspect.getsource(auth.auth_login)
    # totp_required return 이 _login_ip_clear 보다 앞 — 2FA 분기에선 리셋 안 함.
    assert login.index("totp_required") < login.index("_login_ip_clear")
    # step-2: TOTP 실패 시 계정 잠금 누적 + 잠긴 계정 차단.
    step2 = inspect.getsource(auth.auth_login_totp)
    assert "_login_record_failure" in step2
    assert "is_locked" in step2
    # MINOR 흡수: 백업코드 소비 row-lock.
    assert "FOR UPDATE" in inspect.getsource(app._totp_consume_backup_code)


def test_f1_frontend():
    js = _read_static("app.js")
    assert "showTotpLoginPrompt" in js and "/api/auth/login/totp" in js
    assert "renderProfileTotp" in js and "/api/auth/totp/setup" in js
    adm = _read_static("admin.js")
    assert "triggerAccountTotpDisableFlow" in adm and "/totp/disable" in adm
    assert 'statusBadge("2FA"' in adm
    html = _read_static("index.html")
    assert 'id="profileTotpBody"' in html
