"""feature-0012 P5b Final — auth 도메인 APIRouter (인증(회원가입/로그인/OAuth/TOTP/아바타/시스템프롬프트)).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import hmac
import json
import secrets

from datetime import datetime
from datetime import timezone
from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Request
from fastapi import UploadFile
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from typing import Any
from web_context import _get_client_ip
from web_context import _hash_session_token
from web_context import _sanitize_session_id

import app

router = APIRouter()


@router.put("/api/auth/me/avatar")
async def upload_my_avatar(request: Request, file: UploadFile = File(...), account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """본인 프로필 아바타 업로드(self-service — 별도 RBAC 없음, 로그인만). 이전 아바타는 교체."""
    aid = int(account.get("id") or 0)
    if aid <= 0:
        return app._json_error("계정 식별 실패", 403)
    body = await file.read()
    object_key, info = app._store_image_upload(
        body, prefix="avatars", owner_id=aid, max_bytes=app._AVATAR_MAX_BYTES,
        mime_hint=(file.content_type or ""),
    )
    if not object_key:
        return app._json_error(info, 400)
    # 이전 아바타 object key 회수(best-effort 삭제).
    cur = conn.cursor()
    try:
        cur.execute("SELECT AvatarObjectKey FROM WebAccounts WHERE Id = %s", (aid,))
        row = cur.fetchone()
        old_key = row[0] if row else None
        cur.execute("UPDATE WebAccounts SET AvatarObjectKey = %s WHERE Id = %s", (object_key, aid))
        conn.commit()
    finally:
        cur.close()
    if old_key and old_key != object_key:
        try:
            from web.modules import storage_minio
            storage_minio.delete_object(str(old_key))
        except Exception:
            pass
    return JSONResponse({"ok": True, "avatar_url": app._avatar_url_for(aid, object_key)})

@router.delete("/api/auth/me/avatar")
def delete_my_avatar(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """본인 아바타 제거 → Identicon 폴백."""
    aid = int(account.get("id") or 0)
    cur = conn.cursor()
    try:
        cur.execute("SELECT AvatarObjectKey FROM WebAccounts WHERE Id = %s", (aid,))
        row = cur.fetchone()
        old_key = row[0] if row else None
        cur.execute("UPDATE WebAccounts SET AvatarObjectKey = NULL WHERE Id = %s", (aid,))
        conn.commit()
    finally:
        cur.close()
    if old_key:
        try:
            from web.modules import storage_minio
            storage_minio.delete_object(str(old_key))
        except Exception:
            pass
    return JSONResponse({"ok": True, "avatar_url": None})

@router.post("/api/auth/signup")
async def auth_signup(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
    username = app._sanitize_username(data.get("username", ""))
    password = str(data.get("password", "") or "")
    confirm_password = str(data.get("confirm_password", "") or "")
    if not app._is_valid_username(username):
        return JSONResponse({"ok": False, "error": "사용자 ID는 3~64자 영문/숫자/._- 조합이어야 합니다."}, status_code=400)
    if not app._is_valid_password(password):
        return JSONResponse({"ok": False, "error": "비밀번호는 10~128자여야 합니다."}, status_code=400)
    if confirm_password and password != confirm_password:
        return JSONResponse({"ok": False, "error": "비밀번호 확인이 일치하지 않습니다."}, status_code=400)
    try:
        conn = app._connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM WebAccounts WHERE Username = %s LIMIT 1", (username,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return JSONResponse({"ok": False, "error": "이미 존재하는 사용자 ID입니다."}, status_code=409)
        password_hash = app._hash_password(password)
        signup_role_id = app._default_signup_role_id(conn)
        if signup_role_id <= 0:
            cur.close()
            conn.close()
            return JSONResponse({"ok": False, "error": "기본 가입 역할이 설정되지 않았습니다."}, status_code=500)
        signup_role = app._load_role_by_id(conn, signup_role_id)
        signup_permissions = dict((signup_role or {}).get("permissions") or {})
        cur.execute(
            """
INSERT INTO WebAccounts (
    Username,
    PasswordHash,
    RoleId,
    ApprovedAt,
    IsActive
) VALUES (%s, %s, %s, %s, 1)
            """,
            (
                username,
                password_hash,
                signup_role_id,
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                if signup_permissions.get("conversation.ask") or signup_permissions.get("console.access")
                else None,
            ),
        )
        account_id = int(cur.lastrowid or 0)
        cur.close()
        session_token = app._issue_auth_session(conn, account_id, request)
        account = app._load_account_by_id(conn, account_id)
    except Exception as exc:
        conn.close()
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    conn.close()
    resp = JSONResponse({"ok": True, "user": app._serialize_account(account)})
    app._set_session_cookie(resp, request, session_token)
    return resp

@router.post("/api/auth/login")
async def auth_login(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
    username = app._sanitize_username(data.get("username", ""))
    password = str(data.get("password", "") or "")
    if not username or not password:
        return JSONResponse({"ok": False, "error": "username and password are required"}, status_code=400)
    # TASK-20260619T021356-login-attempt-limit (보안 ②): IP throttle — DB 접근 전 무차별 대입 IP 차단.
    client_ip = _get_client_ip(request)
    if app._login_ip_throttled(client_ip):
        return JSONResponse(
            {"ok": False, "error": "너무 많은 로그인 시도가 감지되었습니다. 잠시 후 다시 시도해 주세요."},
            status_code=429,
        )
    try:
        conn = app._connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)
    try:
        account = app._load_account_by_username(conn, username)
        # 미존재/비활성/삭제 — 일반 메시지(계정 열거 방지) + IP 실패 기록.
        if not account or not bool(account.get("is_active")) or account.get("deleted_at"):
            app._login_ip_record_failure(client_ip)
            return JSONResponse({"ok": False, "error": "로그인에 실패했습니다."}, status_code=401)
        # 계정 잠금 확인 (is_locked = `_fetch_account_rows` 의 DB NOW() 평가 — clock skew 무관).
        # NOTE(soft threshold, outside-voice MAJOR accept): is_locked 는 비밀번호 검증(느린
        # PBKDF2) 직전 스냅샷이라, 동시 요청 버스트는 잠금 기록 전 임계를 초과할 수 있다.
        # LOGIN_MAX_FAILED_ATTEMPTS 는 "연속(sequential)" 한도이며 절대 상한이 아니다.
        # 1차 방어=DB 잠금(cross-worker 영속), 2차=IP throttle(단일 IP 버스트 제한) + 느린 해시.
        # 분산(botnet) 공격은 사내 LAN 위협모델 외 — 외부 노출 시 별 cycle 에서 원자적 재검사
        # (SELECT ... FOR UPDATE) 또는 per-account in-memory pre-gate 검토.
        if bool(account.get("is_locked")):
            app._login_ip_record_failure(client_ip)
            return JSONResponse(
                {"ok": False, "error": "비밀번호를 여러 번 잘못 입력하여 계정이 일시적으로 잠겼습니다. 잠시 후 다시 시도하거나 관리자에게 문의해 주세요."},
                status_code=429,
            )
        # 비밀번호 검증.
        if not app._verify_password(password, str(account.get("password_hash") or "")):
            locked_now = app._login_record_failure(conn, int(account["id"]))
            app._login_ip_record_failure(client_ip)
            if locked_now:
                # 잠금 발생 — best-effort audit(anonymous actor, target=계정). fail-open.
                app._audit_user_action(
                    conn,
                    request,
                    None,
                    action="auth.lockout",
                    resource_type="account",
                    resource_id=str(int(account["id"])),
                    request_ctx={
                        "username": str(account.get("username") or ""),
                        "lockout_minutes": int(app.LOGIN_LOCKOUT_MINUTES),
                        "remote_addr": client_ip,
                    },
                    actor_type="anonymous",
                    target_account_id=int(account["id"]),
                )
                return JSONResponse(
                    {"ok": False, "error": f"비밀번호 오류가 반복되어 계정이 약 {app.LOGIN_LOCKOUT_MINUTES}분간 잠겼습니다. 잠시 후 다시 시도하거나 관리자에게 문의해 주세요."},
                    status_code=429,
                )
            return JSONResponse({"ok": False, "error": "로그인에 실패했습니다."}, status_code=401)
        # 비밀번호 검증 통과.
        # TASK-20260619T040000-two-factor-auth (보안 ⑥): TOTP 활성 계정은 완전 세션 미발급 —
        # pending token 반환 후 /api/auth/login/totp 로 2단계 검증을 요구한다(2-step login).
        # outside-voice MAJOR 흡수: 2FA 분기에서는 잠금/IP 리셋을 **미룬다**(2단계 미완료).
        # 비밀번호만 통과시켜 IP 버킷·계정 잠금을 리셋하면 비밀번호 보유 공격자가 step1 반복으로
        # throttle 을 무한 리셋하며 6자리 TOTP 를 brute-force 할 수 있다 → 리셋은 2단계 완료 시에만.
        if app._totp_is_enabled(conn, int(account["id"])):
            pending = app._totp_pending_token(conn, int(account["id"]))
            if not pending:
                return JSONResponse(
                    {"ok": False, "error": "2단계 인증 처리 중 오류가 발생했습니다. 관리자에게 문의해 주세요."},
                    status_code=500,
                )
            return JSONResponse({"ok": False, "totp_required": True, "totp_token": pending}, status_code=200)
        # 2FA 미사용 — 즉시 완료: 실패 카운터/잠금 + IP 버킷 초기화 후 세션 발급.
        app._login_reset_lockout(conn, int(account["id"]))
        app._login_ip_clear(client_ip)
        session_token = app._issue_auth_session(conn, int(account["id"]), request)
        account = app._load_account_by_id(conn, int(account["id"]))
    finally:
        conn.close()
    resp = JSONResponse({"ok": True, "user": app._serialize_account(account)})
    app._set_session_cookie(resp, request, session_token)
    return resp

@router.post("/api/auth/login/totp")
async def auth_login_totp(request: Request) -> JSONResponse:
    """TASK-20260619T040000-two-factor-auth (보안 ⑥): 로그인 2단계 — TOTP 코드(또는 백업코드) 검증.

    body: {totp_token, code}. pending token(DEK-HMAC, 5분) 검증 → TOTP/백업코드 일치 시 세션 발급.
    IP throttle + 코드 실패 IP 기록(2단계도 무차별 대입 차단). 백업코드는 1회용 소비.
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
    token = str(data.get("totp_token", "") or "")
    code = str(data.get("code", "") or "").strip()
    client_ip = _get_client_ip(request)
    if app._login_ip_throttled(client_ip):
        return JSONResponse(
            {"ok": False, "error": "너무 많은 로그인 시도가 감지되었습니다. 잠시 후 다시 시도해 주세요."},
            status_code=429,
        )
    if not token or not code:
        return JSONResponse({"ok": False, "error": "인증 코드를 입력해 주세요."}, status_code=400)
    try:
        conn = app._connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)
    try:
        account_id = app._totp_verify_pending_token(conn, token)
        if not account_id:
            app._login_ip_record_failure(client_ip)
            return JSONResponse(
                {"ok": False, "error": "인증 세션이 만료되었습니다. 다시 로그인해 주세요.", "totp_expired": True},
                status_code=401,
            )
        # outside-voice MAJOR 흡수: 2단계 brute-force 방어 — 계정 잠금(② 인프라, DB·cross-IP)도
        # TOTP 단계에 적용. 잠긴 계정은 코드 검증 전에 차단.
        acct_full = app._load_account_by_id(conn, int(account_id))
        if acct_full and bool(acct_full.get("is_locked")):
            app._login_ip_record_failure(client_ip)
            return JSONResponse(
                {"ok": False, "error": "인증 시도가 반복되어 계정이 일시적으로 잠겼습니다. 잠시 후 다시 시도하거나 관리자에게 문의해 주세요."},
                status_code=429,
            )
        row = app._totp_load(conn, int(account_id))
        if not row or int(row.get("Enabled") or 0) != 1:
            return JSONResponse({"ok": False, "error": "2단계 인증이 설정되어 있지 않습니다."}, status_code=400)
        secret = app._totp_decrypt_secret(
            conn, int(account_id), str(row.get("SecretEnc") or ""), int(row.get("EncryptionVersion") or 0),
        )
        ok_code = bool(secret and app._totp_verify(secret, code))
        used_backup = False
        if not ok_code:
            # TOTP 불일치 → 백업코드 시도(1회용, row-lock 원자 소비).
            used_backup = app._totp_consume_backup_code(conn, int(account_id), code)
        if not ok_code and not used_backup:
            # 코드 실패 → IP 기록 + 계정 잠금 누적(② 인프라, brute-force 무한 시도 차단).
            app._login_ip_record_failure(client_ip)
            app._login_record_failure(conn, int(account_id))
            return JSONResponse({"ok": False, "error": "인증 코드가 올바르지 않습니다."}, status_code=401)
        # 통과 — 실패 카운터/잠금 + IP 버킷 초기화(2단계 완료) 후 세션 발급.
        app._login_reset_lockout(conn, int(account_id))
        app._login_ip_clear(client_ip)
        session_token = app._issue_auth_session(conn, int(account_id), request)
        account = app._load_account_by_id(conn, int(account_id))
        app._audit_user_action(
            conn, request, account, action="auth.login.totp", resource_type="account",
            resource_id=str(int(account_id)),
            request_ctx={"method": "backup_code" if used_backup else "totp", "remote_addr": client_ip},
            target_account_id=int(account_id),
        )
    finally:
        conn.close()
    resp = JSONResponse({"ok": True, "user": app._serialize_account(account), "used_backup_code": used_backup})
    app._set_session_cookie(resp, request, session_token)
    return resp

@router.get("/api/auth/me")
def auth_me(request: Request) -> JSONResponse:
    try:
        conn = app._connect_memory()
    except Exception:
        return JSONResponse({"ok": False})
    account = app._get_authenticated_account(conn, request)
    if not account:
        conn.close()
        return JSONResponse({"ok": False})
    try:
        products = app._list_products(conn, include_inactive=False)
        # TASK-0295: 작업 화면 제품 목록을 계정의 product.access.<key> 권한으로 게이트.
        # 역할에 접근 권한 없는 제품은 picker 에서 제외 (mutation 경로의 403 enforcement 와 정합).
        products = app._filter_products_for_account_access(account, products)
        default_pid = app._coerce_default_product_id(app._get_default_product_id(conn), products)
    except Exception:
        products = []
        default_pid = 0
    # TASK-0261: 제품 목록에 datasource 연결(네트워크) 상태 첨부 — 드롭업 배지 색.
    try:
        app._attach_product_conn_status(conn, products)
    except Exception:
        pass
    conn.close()
    return JSONResponse({
        "ok": True,
        "user": app._serialize_account(account),
        "products": products,
        "default_product_id": int(default_pid) if default_pid else None,
    })

@router.patch("/api/auth/me")
async def auth_me_patch(request: Request) -> JSONResponse:
    """자신의 계정 프로필을 수정한다. role/비밀번호 변경 지원."""
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    account = app._get_authenticated_account(conn, request)
    if not account:
        conn.close()
        return app._json_error("unauthorized", 401)

    updates: list[str] = []
    params: list[Any] = []

    # 비밀번호 변경
    current_password = str(data.get("current_password", "") or "").strip()
    new_password = str(data.get("new_password", "") or "").strip()
    if new_password:
        if not current_password:
            conn.close()
            return app._json_error("현재 비밀번호를 입력하세요.", 400)
        if not app._is_valid_password(new_password):
            conn.close()
            return app._json_error("새 비밀번호는 10자 이상이어야 합니다.", 400)
        # 현재 비밀번호 검증
        cur = conn.cursor()
        cur.execute("SELECT PasswordHash FROM WebAccounts WHERE Id = %s", (int(account["id"]),))
        row = cur.fetchone()
        cur.close()
        if not row or not app._verify_password(current_password, str(row[0])):
            conn.close()
            return app._json_error("현재 비밀번호가 올바르지 않습니다.", 400)
        updates.append("PasswordHash = %s")
        params.append(app._hash_password(new_password))
        # TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0095): 비밀번호 변경 성공 시 강제 변경 플래그 해제.
        updates.append("MustChangePassword = 0")

    if not updates:
        conn.close()
        # 변경 내용 없음 — 현재 프로필 반환
        return JSONResponse({"ok": True, "user": app._serialize_account(account)})

    params.append(int(account["id"]))
    cur = conn.cursor()
    cur.execute(
        f"UPDATE WebAccounts SET {', '.join(updates)} WHERE Id = %s",
        tuple(params),
    )
    conn.commit()
    cur.close()

    updated_account = app._load_account_by_id(conn, int(account["id"]))
    conn.close()
    if not updated_account:
        return app._json_error("account not found", 404)
    return JSONResponse({"ok": True, "user": app._serialize_account(updated_account)})

@router.post("/api/auth/totp/setup")
async def auth_totp_setup(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """2FA 등록 시작 — secret 생성·암호화 저장(Enabled=0 미확인) + otpauth URI 반환.
    재호출(미확인 상태) 시 새 secret 으로 덮어쓴다. 이미 활성(Enabled=1)이면 409."""
    aid = int(account["id"])
    if app._totp_is_enabled(conn, aid):
        return app._json_error("이미 2단계 인증이 설정되어 있습니다. 먼저 해제 후 다시 설정하세요.", 409)
    secret = app._totp_generate_secret()
    enc = app._totp_encrypt_secret(conn, aid, secret)
    if not enc:
        return app._json_error("2단계 인증 암호화 인프라(KEK)가 구성되어 있지 않습니다. 관리자에게 문의해 주세요.", 503)
    secret_enc, ver = enc
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO WebAccountTotp (AccountId, SecretEnc, EncryptionVersion, Enabled, BackupCodesJson, ConfirmedAt) "
            "VALUES (%s, %s, %s, 0, NULL, NULL) "
            "ON DUPLICATE KEY UPDATE SecretEnc=VALUES(SecretEnc), EncryptionVersion=VALUES(EncryptionVersion), "
            "Enabled=0, BackupCodesJson=NULL, ConfirmedAt=NULL",
            (aid, secret_enc, int(ver)),
        )
    finally:
        cur.close()
    username = str(account.get("username") or "user")
    return JSONResponse({
        "ok": True,
        "secret": secret,  # 1회 노출 — 사용자가 authenticator 에 수동 입력 가능.
        "otpauth_uri": app._totp_otpauth_uri(secret, username),
        "digits": app._TOTP_DIGITS,
        "period": app._TOTP_STEP,
    })

@router.post("/api/auth/totp/confirm")
async def auth_totp_confirm(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """2FA 등록 확정 — setup 의 secret 으로 첫 코드 검증 → Enabled=1 + 백업코드 10개(1회 노출) 발급."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    code = str(data.get("code", "") or "").strip()
    aid = int(account["id"])
    row = app._totp_load(conn, aid)
    if not row or not row.get("SecretEnc"):
        return app._json_error("먼저 2단계 인증 설정을 시작해 주세요.", 400)
    if int(row.get("Enabled") or 0) == 1:
        return app._json_error("이미 활성화되어 있습니다.", 409)
    secret = app._totp_decrypt_secret(conn, aid, str(row.get("SecretEnc") or ""), int(row.get("EncryptionVersion") or 0))
    if not secret or not app._totp_verify(secret, code):
        return app._json_error("인증 코드가 올바르지 않습니다. authenticator 앱의 현재 코드를 입력해 주세요.", 400)
    backup_codes = app._totp_generate_backup_codes()
    backup_json = json.dumps([{"hash": app._totp_backup_hash(c), "used": False} for c in backup_codes])
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE WebAccountTotp SET Enabled=1, BackupCodesJson=%s, ConfirmedAt=NOW() WHERE AccountId=%s",
            (backup_json, aid),
        )
    finally:
        cur.close()
    app._audit_user_action(
        conn, request, account, action="auth.totp.enable", resource_type="account",
        resource_id=str(aid), request_ctx={"backup_codes_issued": len(backup_codes)}, target_account_id=aid,
    )
    return JSONResponse({"ok": True, "enabled": True, "backup_codes": backup_codes})

@router.post("/api/auth/totp/disable")
async def auth_totp_disable(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """2FA 해제 — 비밀번호 재확인 후 삭제(self-service)."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    password = str(data.get("password", "") or "")
    aid = int(account["id"])
    full = app._load_account_by_username(conn, str(account.get("username") or ""))
    if not full or not app._verify_password(password, str(full.get("password_hash") or "")):
        return app._json_error("비밀번호가 올바르지 않습니다.", 403)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM WebAccountTotp WHERE AccountId=%s", (aid,))
    finally:
        cur.close()
    app._audit_user_action(
        conn, request, account, action="auth.totp.disable", resource_type="account",
        resource_id=str(aid), request_ctx={"by": "self"}, target_account_id=aid,
    )
    return JSONResponse({"ok": True, "enabled": False})

@router.post("/api/auth/logout")
def auth_logout(request: Request) -> JSONResponse:
    token = _sanitize_session_id(request.cookies.get(app.SESSION_COOKIE, ""))
    try:
        conn = app._connect_memory()
        cur = conn.cursor()
        if token:
            cur.execute(
                "UPDATE WebAuthSessions SET IsRevoked = 1 WHERE SessionTokenHash = %s",
                (_hash_session_token(token),),
            )
        cur.close()
        conn.close()
    except Exception:
        pass
    resp = JSONResponse({"ok": True})
    app._clear_session_cookie(resp, request)
    return resp

@router.get("/api/auth/oauth/config")
def auth_oauth_config(request: Request) -> JSONResponse:
    """로그인 화면이 외부 IdP 버튼 노출 여부를 판단하기 위한 공개 설정.

    민감값(client_secret 등) 미노출 — enabled 플래그만. anonymous(로그인 전 호출).
    """
    return JSONResponse({"google": {"enabled": app._oauth_google_configured()}})

@router.get("/api/auth/oauth/google/start")
def auth_oauth_google_start(request: Request) -> Any:
    if not app._oauth_google_configured():
        return app._json_error("google 로그인이 활성화되어 있지 않습니다.", 404)
    verifier, challenge = app._oauth_pkce_pair()
    nonce = app._oauth_b64url(secrets.token_bytes(16))
    # MAJOR-1(login-CSRF/세션 고정 차단): state 를 개시 브라우저에 바인딩한다. random binding 을
    # state payload(b)에 넣고 동일 값을 단명 httponly 쿠키로 심어, callback 에서 둘이 일치할 때만 수락.
    bind = app._oauth_b64url(secrets.token_bytes(16))
    state = app._oauth_state_encode(
        {"v": verifier, "n": nonce, "b": bind, "ts": int(datetime.now(timezone.utc).timestamp())}
    )
    import urllib.parse
    params = urllib.parse.urlencode(
        {
            "client_id": app.OAUTH_GOOGLE_CLIENT_ID,
            "redirect_uri": app.OAUTH_GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    resp = RedirectResponse(f"{app.OAUTH_GOOGLE_AUTH_ENDPOINT}?{params}", status_code=302)
    resp.set_cookie(
        app.OAUTH_BIND_COOKIE,
        bind,
        max_age=app.OAUTH_STATE_TTL_SEC,
        httponly=True,
        samesite="lax",
        secure=app._request_is_https(request),
    )
    return resp

@router.get("/api/auth/oauth/google/callback")
def auth_oauth_google_callback(request: Request) -> Any:
    if not app._oauth_google_configured():
        return app._json_error("google 로그인이 활성화되어 있지 않습니다.", 404)
    if str(request.query_params.get("error") or "").strip():
        return RedirectResponse("/?oauth_error=denied", status_code=302)
    code = str(request.query_params.get("code") or "").strip()
    state = app._oauth_state_decode(str(request.query_params.get("state") or "").strip())
    if not code or not state:
        return app._oauth_callback_redirect(request, "/?oauth_error=state")
    # MAJOR-1: state 가 이 브라우저에서 개시됐는지 — 단명 바인딩 쿠키 == state.b (constant-time).
    bind_cookie = str(request.cookies.get(app.OAUTH_BIND_COOKIE) or "")
    if not bind_cookie or not hmac.compare_digest(bind_cookie, str(state.get("b") or "")):
        return app._oauth_callback_redirect(request, "/?oauth_error=state")
    try:
        tokens = app._oauth_google_exchange_code(code, str(state.get("v") or ""))
    except Exception:
        return app._oauth_callback_redirect(request, "/?oauth_error=exchange")
    claims = app._oauth_decode_id_token_claims(str(tokens.get("id_token") or ""))
    ok, _reason = app._oauth_validate_claims(claims or {}, str(state.get("n") or ""))
    if not ok:
        return app._oauth_callback_redirect(request, "/?oauth_error=claims")
    sub = str((claims or {}).get("sub") or "").strip()
    email = str((claims or {}).get("email") or "").strip()
    if not sub:
        return app._oauth_callback_redirect(request, "/?oauth_error=subject")
    try:
        conn = app._connect_memory()
    except Exception:
        return app._oauth_callback_redirect(request, "/?oauth_error=server")
    try:
        account_id, mode = app._oauth_resolve_or_provision_account(
            conn, provider="google", sub=sub, email=email
        )
        if mode == "email-conflict":
            return app._oauth_callback_redirect(request, "/?oauth_error=email_conflict")
        if account_id <= 0:
            return app._oauth_callback_redirect(request, "/?oauth_error=provision")
        acct = app._load_account_by_id(conn, account_id)
        if not acct or not bool(acct.get("is_active")) or acct.get("deleted_at"):
            return app._oauth_callback_redirect(request, "/?oauth_error=inactive")
        session_token = app._issue_auth_session(conn, account_id, request)
    finally:
        conn.close()
    resp = app._oauth_callback_redirect(request, "/")
    app._set_session_cookie(resp, request, session_token)
    return resp

@router.post("/api/auth/me/system-prompt/generate")
async def me_generate_account_prompt(request: Request) -> JSONResponse:
    """비스트리밍 개인 프롬프트 자동작성(호환 경로). body: {product_id?}."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    pid_raw = (data or {}).get("product_id")
    product_id: "int | None" = None
    if pid_raw is not None and str(pid_raw).strip() != "":
        try:
            product_id = int(pid_raw)
        except Exception:
            return app._json_error("invalid product_id", 400)
    error, ctx = await app._collect_account_prompt_context(product_id, request)
    if error:
        return error
    return await app._prompt_generate_json_response(
        ctx, log_label="me_generate_account_prompt", log_ctx=f"account_prompt product_id={product_id}"
    )

@router.get("/api/auth/me/system-prompt/generate/stream")
async def me_generate_account_prompt_stream(request: Request, product_id: "int | None" = None):
    """프로필 '제품별 개인 프롬프트' 자동작성 LLM 토큰 스트리밍(SSE)."""
    error, ctx = await app._collect_account_prompt_context(product_id, request)
    if error:
        return error
    return app._prompt_generate_stream_response(
        ctx, log_label="me_generate_account_prompt_stream", log_ctx=f"account_prompt product_id={product_id}"
    )

@router.get("/api/auth/me/system-prompt")
def me_get_system_prompt(request: Request, product_id: int | None = None, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    # TASK-0052 Phase 1C G7: product_id query param 이 주어졌으면 그 product 의 접근 권한 검사.
    if product_id is not None and int(product_id) > 0:
        if not app._account_has_product_access(account, int(product_id), conn=conn):
            return app._json_error("요청을 수행할 수 없습니다.", 403)
    # 계정 스코프: 개인 프롬프트는 product 별 혹은 product 무관 하나씩 보유 가능.
    row = app._load_system_prompt(
        conn,
        scope="account",
        product_id=int(product_id) if product_id else None,
        role_id=None,
        account_id=int(account["id"]),
    )
    return JSONResponse({"prompt": row, "product_id": int(product_id) if product_id else None})

@router.put("/api/auth/me/system-prompt")
async def me_put_system_prompt(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    content = str(data.get("content") or "")
    product_id_raw = data.get("product_id")
    product_id: int | None = None
    if product_id_raw is not None and str(product_id_raw).strip() != "":
        try:
            product_id = int(product_id_raw)
        except Exception:
            conn.close()
            return app._json_error("invalid product_id", 400)
    # TASK-0052 Phase 1C G8: PUT body 의 product_id 가 주어졌으면 접근 권한 검사.
    if product_id is not None and int(product_id) > 0:
        if not app._account_has_product_access(account, int(product_id), conn=conn):
            conn.close()
            return app._json_error("요청을 수행할 수 없습니다.", 403)
    new_id = app._upsert_system_prompt(
        conn,
        scope="account",
        content=content,
        product_id=product_id,
        role_id=None,
        account_id=int(account["id"]),
        updated_by_account_id=int(account["id"]),
    )
    conn.close()
    return JSONResponse({"ok": True, "id": new_id, "deleted": new_id == 0})
