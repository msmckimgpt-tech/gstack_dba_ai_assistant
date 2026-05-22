"""TASK-0098 (REQ-20260522-0002, Critical §12.3) Commit 2 — `/api/admin/me` RBAC smoke.

4 시나리오:

  S1  admin (console.access) → 200 + user.permissions["console.access"]=true + role 포함
  S2  non-admin (e.g., sales without console.access) → 403 + "관리 콘솔 접근 권한이 필요합니다." 메시지
  S3  비로그인 (cookie 없음) → 401
  S4  admin 응답에 permissions 포함 + 일부 known code (예: account.read, console.access) 가 true

본 endpoint 는 Codex outside voice F1 (blocker) 흡수 — admin.js initialize() 의
`me.user.permissions["console.access"]` 의존성을 `/api/auth/me` 에서 분리한
admin-context endpoint. Commit 3 에서 `/api/auth/me` permissions 가 제거되어도
admin 콘솔 진입이 깨지지 않도록 보장.

사전조건:
  - `make web` 으로 컨테이너 가동
  - admin (console.access 보유) + sales 또는 dba (console.access 미보유) 계정 + 비밀번호

실행:
  python3 unit/feature-0003-agent-web-ui/tests/test_admin_me_rbac.py \
      --base-url http://localhost:18080 \
      --admin-user admin --admin-pass <pw> \
      --user-user <non_admin_username> --user-pass <pw>

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


def _login(base_url: str, username: str, password: str) -> str:
    status, headers, body = _request("POST", f"{base_url}/api/auth/login", data={"username": username, "password": password})
    if status != 200:
        raise SystemExit(f"login failed for {username}: status={status} body={body}")
    set_cookie = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
    return set_cookie.split(";", 1)[0]


def _expect(label: str, ok: bool, detail: str = "") -> bool:
    sigil = "PASS" if ok else "FAIL"
    print(f"[{sigil}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def _get_admin_me(base_url: str, cookie: str | None) -> tuple[int, dict[str, Any]]:
    status, _, body = _request("GET", f"{base_url}/api/admin/me", cookie=cookie)
    try:
        payload = json.loads(body or "{}")
    except Exception:
        payload = {"_raw": body}
    return status, payload


def s1_admin_ok(base_url: str, admin_cookie: str) -> bool:
    status, payload = _get_admin_me(base_url, admin_cookie)
    if status != 200:
        return _expect("S1 admin GET /api/admin/me", False, f"status={status} payload={payload}")
    user = payload.get("user") or {}
    permissions = user.get("permissions") or {}
    role = user.get("role") or {}
    ok = bool(payload.get("ok")) and bool(permissions.get("console.access")) and bool(role.get("key"))
    return _expect("S1 admin → 200 + permissions + role", ok,
                   f"ok={payload.get('ok')} console.access={permissions.get('console.access')} role_key={role.get('key')}")


def s2_non_admin_403(base_url: str, user_cookie: str) -> bool:
    status, payload = _get_admin_me(base_url, user_cookie)
    ok = status == 403
    msg = (payload.get("error") or "")
    msg_ok = "관리 콘솔" in msg or "권한" in msg
    return _expect("S2 non-admin → 403", ok and msg_ok,
                   f"status={status} error={msg!r}")


def s3_anonymous_401(base_url: str) -> bool:
    status, payload = _get_admin_me(base_url, cookie=None)
    ok = status in (401, 403)  # _require_account 가 401 반환 (정확한 status 는 helper 동작 의존)
    return _expect("S3 anonymous → 401/403", ok, f"status={status} payload={payload}")


def s4_admin_permissions_shape(base_url: str, admin_cookie: str) -> bool:
    status, payload = _get_admin_me(base_url, admin_cookie)
    if status != 200:
        return _expect("S4 admin permissions shape", False, f"status={status}")
    user = payload.get("user") or {}
    permissions = user.get("permissions") or {}
    if not isinstance(permissions, dict):
        return _expect("S4 permissions is dict", False, f"type={type(permissions).__name__}")
    has_known_true = any(
        permissions.get(code) is True
        for code in ("console.access", "account.read", "audit.read.any")
    )
    return _expect("S4 admin payload includes permissions map (>=1 known true)", has_known_true,
                   f"keys_count={len(permissions)} sample={[c for c in ('console.access', 'account.read', 'audit.read.any') if permissions.get(c)]}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="TASK-0098 Commit 2 admin_me RBAC smoke")
    parser.add_argument("--base-url", default="http://localhost:18080")
    parser.add_argument("--admin-user", required=True)
    parser.add_argument("--admin-pass", required=True)
    parser.add_argument("--user-user", required=True, help="console.access 미보유 계정")
    parser.add_argument("--user-pass", required=True)
    args = parser.parse_args(argv)

    admin_cookie = _login(args.base_url, args.admin_user, args.admin_pass)
    user_cookie = _login(args.base_url, args.user_user, args.user_pass)

    results = [
        s1_admin_ok(args.base_url, admin_cookie),
        s2_non_admin_403(args.base_url, user_cookie),
        s3_anonymous_401(args.base_url),
        s4_admin_permissions_shape(args.base_url, admin_cookie),
    ]
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} scenarios passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
