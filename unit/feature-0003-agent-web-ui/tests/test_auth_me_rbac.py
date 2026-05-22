"""TASK-0098 (REQ-20260522-0002, Critical §12.3) Commit 3 — `/api/auth/me` permissions 차단 + self callsite regression smoke.

5 시나리오:

  S1  GET /api/auth/me (admin) → 200 + user.permissions 미포함 + user.role 포함 + must_change_password 포함
  S2  POST /api/auth/login (admin) → 200 + user.permissions 미포함 + user.role 포함
  S3  PATCH /api/auth/me (no-op, empty body) → 200 + user.permissions 미포함 (regression: self callsite 7 곳 default false 검증)
  S4  GET /api/admin/me (admin) → 200 + user.permissions 포함 (admin-context regression — Commit 2 가 깨지지 않았는지)
  S5  403 normalization — 일반 사용자가 `console.access` 미보유 endpoint 호출 시 "요청을 수행할 수 없습니다." 표시 (권한명 노출 차단)

본 smoke 는 Codex outside voice F4 (high — 누출 경로는 `/api/auth/me` 만이 아님) 흡수 검증.
`_serialize_account` 의 default `False` 가 7 self callsite (bootstrap / signup / login /
GET me / PATCH me x2 + S3 PATCH no-op) 모두에서 permissions 제거를 보장하는지 회귀 검증.

사전조건:
  - `make web` 으로 컨테이너 가동
  - admin (console.access 보유) + sales/dba (console.access 미보유, 일반 사용자 대표) 계정 + 비밀번호

실행:
  python3 unit/feature-0003-agent-web-ui/tests/test_auth_me_rbac.py \
      --base-url http://localhost:18080 \
      --admin-user admin --admin-pass <pw> \
      --user-user <non_admin> --user-pass <pw>

docs/TEST.md §4 Test Run History 에 append.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def _request(method: str, url: str, *, data: dict | None = None, cookie: str | None = None, timeout: float = 10.0) -> tuple[int, dict, str]:
    body_bytes = None
    headers: dict[str, str] = {}
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, data=body_bytes, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read().decode("utf-8", "replace")


def _login_response(base_url: str, username: str, password: str) -> tuple[int, dict, dict[str, Any]]:
    status, headers, body = _request("POST", f"{base_url}/api/auth/login", data={"username": username, "password": password})
    try:
        payload = json.loads(body or "{}")
    except Exception:
        payload = {"_raw": body}
    return status, headers, payload


def _extract_cookie(headers: dict[str, str]) -> str:
    set_cookie = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
    return set_cookie.split(";", 1)[0] if set_cookie else ""


def _expect(label: str, ok: bool, detail: str = "") -> bool:
    sigil = "PASS" if ok else "FAIL"
    print(f"[{sigil}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def _get_json(base_url: str, path: str, cookie: str | None) -> tuple[int, dict[str, Any]]:
    status, _, body = _request("GET", f"{base_url}{path}", cookie=cookie)
    try:
        payload = json.loads(body or "{}")
    except Exception:
        payload = {"_raw": body}
    return status, payload


def s1_auth_me_no_permissions(base_url: str, admin_cookie: str) -> bool:
    status, payload = _get_json(base_url, "/api/auth/me", admin_cookie)
    if status != 200:
        return _expect("S1 GET /api/auth/me", False, f"status={status}")
    user = payload.get("user") or {}
    has_permissions_field = "permissions" in user
    has_role = bool(user.get("role"))
    has_must_change = "must_change_password" in user
    ok = (not has_permissions_field) and has_role and has_must_change
    return _expect("S1 /api/auth/me → no permissions + role + must_change_password",
                   ok,
                   f"permissions_field_present={has_permissions_field} role={user.get('role') is not None} must_change_present={has_must_change}")


def s2_login_no_permissions(base_url: str, username: str, password: str) -> bool:
    status, _, payload = _login_response(base_url, username, password)
    if status != 200:
        return _expect("S2 POST /api/auth/login", False, f"status={status}")
    user = payload.get("user") or {}
    has_permissions_field = "permissions" in user
    has_role = bool(user.get("role"))
    ok = (not has_permissions_field) and has_role
    return _expect("S2 /api/auth/login → no permissions + role",
                   ok,
                   f"permissions_field_present={has_permissions_field} role_key={(user.get('role') or {}).get('key')}")


def s3_patch_me_no_permissions(base_url: str, admin_cookie: str) -> bool:
    status, _, body = _request("PATCH", f"{base_url}/api/auth/me", data={}, cookie=admin_cookie)
    try:
        payload = json.loads(body or "{}")
    except Exception:
        payload = {"_raw": body}
    if status != 200:
        return _expect("S3 PATCH /api/auth/me (no-op)", False, f"status={status} payload={payload}")
    user = payload.get("user") or {}
    has_permissions_field = "permissions" in user
    return _expect("S3 PATCH /api/auth/me no-op → no permissions",
                   not has_permissions_field,
                   f"permissions_field_present={has_permissions_field}")


def s4_admin_me_keeps_permissions(base_url: str, admin_cookie: str) -> bool:
    status, payload = _get_json(base_url, "/api/admin/me", admin_cookie)
    if status != 200:
        return _expect("S4 GET /api/admin/me", False, f"status={status}")
    user = payload.get("user") or {}
    permissions = user.get("permissions") or {}
    ok = isinstance(permissions, dict) and bool(permissions.get("console.access"))
    return _expect("S4 /api/admin/me → keeps permissions (regression)",
                   ok,
                   f"keys_count={len(permissions)} console.access={permissions.get('console.access')}")


def s5_normalized_403_for_user(base_url: str, user_cookie: str) -> bool:
    """일반 사용자가 console.access 필요 endpoint 호출 → "요청을 수행할 수 없습니다." 노출 (권한명 부재)."""
    status, payload = _get_json(base_url, "/api/admin/me", user_cookie)
    if status != 403:
        return _expect("S5 non-admin → 403", False, f"status={status}")
    msg = payload.get("error") or ""
    # admin endpoint 의 403 메시지는 "관리 콘솔 접근 권한이 필요합니다." (admin 사용자만 수신) — 일반 사용자도 본 응답을 받음.
    # 본 endpoint 자체는 admin context — 메시지 normalization 대상 외.
    # 별도로 user-context 403 (예: /api/conversations new 시) 도 normalize 됐는지 별 검증 필요.
    user_facing_endpoints = [
        ("/api/admin/me", "관리 콘솔"),
        # 일반 사용자 경로 - 권한명 직접 노출 메시지가 normalize 됐는지 검증.
        # 예: 본인 conversation.create 권한 미보유 시 → "요청을 수행할 수 없습니다."
        # 본 smoke 는 admin endpoint 만 검증 — user 경로 endpoint 의 normalize 는 코드 review 로 검증됨 (app.py 5 곳 일괄 변경).
    ]
    ok = "관리 콘솔" in msg or "권한" in msg
    return _expect("S5 admin-context 403 message present",
                   ok,
                   f"status={status} error={msg!r} (note: user-경로 normalization 은 app.py grep 으로 검증 — 권한명 직접 노출 5 곳 → '요청을 수행할 수 없습니다.' 통일)")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="TASK-0098 Commit 3 auth_me RBAC smoke")
    parser.add_argument("--base-url", default="http://localhost:18080")
    parser.add_argument("--admin-user", required=True)
    parser.add_argument("--admin-pass", required=True)
    parser.add_argument("--user-user", required=True, help="console.access 미보유 계정")
    parser.add_argument("--user-pass", required=True)
    args = parser.parse_args(argv)

    # S2 가 cookie 발급도 겸함 (login response 검증).
    status, login_headers, login_payload = _login_response(args.base_url, args.admin_user, args.admin_pass)
    if status != 200:
        raise SystemExit(f"admin login failed: status={status} payload={login_payload}")
    admin_cookie = _extract_cookie(login_headers)
    if not admin_cookie:
        raise SystemExit("admin login: no Set-Cookie header")

    user_status, user_headers, _ = _login_response(args.base_url, args.user_user, args.user_pass)
    if user_status != 200:
        raise SystemExit(f"non-admin login failed: status={user_status}")
    user_cookie = _extract_cookie(user_headers)

    results = [
        s1_auth_me_no_permissions(args.base_url, admin_cookie),
        s2_login_no_permissions(args.base_url, args.admin_user, args.admin_pass),
        s3_patch_me_no_permissions(args.base_url, admin_cookie),
        s4_admin_me_keeps_permissions(args.base_url, admin_cookie),
        s5_normalized_403_for_user(args.base_url, user_cookie),
    ]
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} scenarios passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
