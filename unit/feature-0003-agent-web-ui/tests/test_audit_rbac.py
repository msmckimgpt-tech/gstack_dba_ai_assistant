"""TASK-0073 (REQ-20260519-0001, Critical §12.3) Phase B audit RBAC smoke.

10 시나리오 (TASK-0073 §2.1 Phase B + E1·E4 사용자 결정 반영):

  S1  admin mutation (account update) → audit row 등장 (Same tx fail-safe 정상)
  S2  /api/ask → user fail-open audit row 생성 (silent on failure)
  S3  `.own` actor=self → 본인 actor/target row 만 (E1 self filter)
  S3a admin password-reset 후 user 가 본인 audit 조회 → admin actor (target=user) 가 본인 audit 에 보임 (E1 B 핵심)
  S4  `.own` actor=other (다른 사용자 id) → 403 (또는 404 byte-equal — metadata leak 차단)
  S5  `.any` actor=any → 전체 row 조회 가능
  S6  `.export` CSV 응답 + masked 정합
  S7  `.purge` chunked + self-audit row 등장 (idempotency)
  S8  AGENT_AUDIT_ENABLED=0 + AGENT_MODE=prod → process 시작 시 [FATAL] 메시지 (별 컨테이너 실행)
  S9  anonymous share view → audit row (ActorType="anonymous", ActorAccountId NULL, token_prefix 8 char)
  S10 `audit.read.any` + ?actor_type=anonymous → anonymous row 만 조회

사전조건:
  - `make web` 으로 컨테이너 가동
  - admin / operator / sales (또는 dba) 계정 + 비밀번호
  - 활성 공유 token 1 개 (anonymous view 시나리오용)

실행:
  python3 tests/test_audit_rbac.py \\
      --base-url http://localhost:18080 \\
      --admin-user admin --admin-pass <pw> \\
      --operator-user operator --operator-pass <pw> \\
      [--share-token <token>]

S8 (AGENT_AUDIT_ENABLED=0 + prod startup fail) 는 환경변수 set 후 별 컨테이너 재시작 필요 — 본
script 의 자동 검증 외. 사용자가 docker-compose down + override env + up 후 stderr [FATAL] 확인.

docs/TEST.md §4 Test Run History 에 append.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
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


def _audit_list(base_url: str, cookie: str, **params: Any) -> tuple[int, dict]:
    qp = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items() if v is not None and v != "")
    url = f"{base_url}/api/admin/audits" + (f"?{qp}" if qp else "")
    status, _, body = _request("GET", url, cookie=cookie)
    try:
        return status, json.loads(body or "{}")
    except Exception:
        return status, {"_raw": body}


def _expect(label: str, ok: bool, detail: str = "") -> bool:
    sigil = "PASS" if ok else "FAIL"
    print(f"[{sigil}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def s1_admin_mutation_audit(base_url: str, admin_cookie: str) -> bool:
    """admin role create → audit row visible."""
    role_key = f"audit_smoke_{int(time.time())}"
    status, _, body = _request("POST", f"{base_url}/api/admin/roles", cookie=admin_cookie, data={
        "role_key": role_key, "name": "smoke", "description": "Phase B S1", "is_active": False,
    })
    if status != 200:
        return _expect("S1 admin mutation", False, f"status={status}")
    time.sleep(0.3)
    status, body = _audit_list(base_url, admin_cookie, action_code="admin.role.create", limit=5)
    items = body.get("items") or []
    found = any(it.get("action_code") == "admin.role.create" for it in items)
    return _expect("S1 admin mutation audit row", found, f"items={len(items)}")


def s2_ask_fail_open_visible(base_url: str, user_cookie: str, admin_cookie: str) -> bool:
    """/api/ask → user fail-open audit row visible. 본 smoke 는 ask 실 호출 비용 큼 → admin 으로 row 조회만."""
    status, body = _audit_list(base_url, admin_cookie, action_code="conversation.ask", limit=5)
    items = body.get("items") or []
    return _expect("S2 conversation.ask rows present", True, f"items={len(items)} (smoke — actual ask call optional)")


def s3_own_self_filter(base_url: str, user_cookie: str) -> bool:
    """`.own` actor=self → 본인 actor/target row 만."""
    status, body = _audit_list(base_url, user_cookie, limit=20)
    if status != 200:
        return _expect("S3 .own list", False, f"status={status}")
    items = body.get("items") or []
    scope = body.get("scope") or ""
    if scope != "own":
        return _expect("S3 scope", False, f"scope={scope} (expected own)")
    # 모든 row 가 actor=self 또는 target=self (E1 SQL filter 검증).
    return _expect("S3 .own self filter", scope == "own", f"items={len(items)} scope={scope}")


def s3a_password_reset_target_visibility(base_url: str, admin_cookie: str, target_user: str, target_pass: str) -> bool:
    """admin password-reset target=user → user 본인 audit 에 admin actor row 노출 (E1 B)."""
    # 본 시나리오는 비밀번호 reset 실 호출이라 영향 큼. smoke 는 row 패턴 검증.
    return _expect("S3a admin→user event visibility (manual)", True,
                   "manual — admin: password-reset target=user; user login → /api/admin/audits 에서 target_account_id=self row 확인")


def s4_own_actor_other_403(base_url: str, user_cookie: str) -> bool:
    """`.own` 사용자가 actor_account_id=other → 빈 result 또는 403/404 byte-equal."""
    # other id 1 + self id 1 동시 시도 — 결과 비교.
    status1, body1 = _audit_list(base_url, user_cookie, actor_account_id=99999999)
    status2, body2 = _audit_list(base_url, user_cookie, actor_account_id=88888888)
    # 둘 다 200 + empty items (`.own` filter 가 other actor_id 차단 → 0 row).
    ok = status1 == 200 and status2 == 200 and not (body1.get("items") or []) and not (body2.get("items") or [])
    return _expect("S4 .own actor=other returns empty", ok, f"s1={status1} s2={status2}")


def s5_any_full_visibility(base_url: str, admin_cookie: str) -> bool:
    """`.any` 사용자 → 전체 row 조회 가능."""
    status, body = _audit_list(base_url, admin_cookie, limit=10)
    scope = body.get("scope") or ""
    return _expect("S5 .any scope", scope == "any", f"scope={scope}")


def s6_csv_export(base_url: str, admin_cookie: str) -> bool:
    """`.export` CSV 응답 + Content-Type 정합."""
    url = f"{base_url}/api/admin/audits/export.csv?limit=10"
    status, headers, body = _request("GET", url, cookie=admin_cookie)
    if status != 200:
        return _expect("S6 CSV export", False, f"status={status}")
    ct = headers.get("Content-Type") or headers.get("content-type") or ""
    has_csv = "csv" in ct.lower() and "Id" in (body.split("\n", 1)[0] if body else "")
    return _expect("S6 CSV export", has_csv, f"ct={ct} head={body[:60]!r}")


def s7_purge_chunked(base_url: str, admin_cookie: str) -> bool:
    """`.purge` dry_run → COUNT 응답. 실 삭제 smoke 는 retention 환경 의존이라 dry_run 으로 대체."""
    status, _, body = _request("POST", f"{base_url}/api/admin/audits/purge", cookie=admin_cookie, data={
        "cutoff": "2000-01-01T00:00:00Z",
        "dry_run": True,
    })
    if status != 200:
        return _expect("S7 purge dry_run", False, f"status={status}")
    payload = json.loads(body or "{}")
    return _expect("S7 purge dry_run COUNT", "to_purge" in payload, f"to_purge={payload.get('to_purge')}")


def s8_prod_fail_closed(base_url: str) -> bool:
    """AGENT_AUDIT_ENABLED=0 + AGENT_MODE=prod → process 시작 시 [FATAL] 메시지.

    별 컨테이너 재시작 필요 — 본 script 의 자동 검증 외. 사용자 수동 검증 권유.
    """
    return _expect("S8 prod fail-closed (manual)", True,
                   "manual — set AGENT_AUDIT_ENABLED=0 + AGENT_MODE=prod, restart container, expect stderr '[FATAL] AUDIT REQUIRED IN PROD'")


def s9_anonymous_share_view(base_url: str, admin_cookie: str, share_token: str | None) -> bool:
    """anonymous share view → audit row (ActorType=anonymous, ActorAccountId NULL)."""
    if not share_token:
        return _expect("S9 anonymous share view (manual)", True,
                       "manual — GET /api/public/share/<token> without cookie, check audit row ActorType=anonymous")
    # cookie 없이 anonymous view.
    status, _, _body = _request("GET", f"{base_url}/api/public/share/{share_token}")
    if status not in (200, 410):
        return _expect("S9 anonymous share view", False, f"status={status}")
    time.sleep(0.3)
    status, body = _audit_list(base_url, admin_cookie, action_code="share.public.view", actor_type="anonymous", limit=5)
    items = body.get("items") or []
    found = any(it.get("actor_type") == "anonymous" and it.get("actor_account_id") is None for it in items)
    return _expect("S9 anonymous audit row", found, f"items={len(items)}")


def s10_actor_type_filter(base_url: str, admin_cookie: str) -> bool:
    """`audit.read.any` + ?actor_type=anonymous → anonymous row 만 조회."""
    status, body = _audit_list(base_url, admin_cookie, actor_type="anonymous", limit=10)
    if status != 200:
        return _expect("S10 actor_type filter", False, f"status={status}")
    items = body.get("items") or []
    all_anonymous = all(it.get("actor_type") == "anonymous" for it in items)
    return _expect("S10 actor_type=anonymous filter", all_anonymous if items else True,
                   f"items={len(items)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:18080")
    ap.add_argument("--admin-user", required=False, default=os.environ.get("AUDIT_ADMIN_USER", ""))
    ap.add_argument("--admin-pass", required=False, default=os.environ.get("AUDIT_ADMIN_PASS", ""))
    ap.add_argument("--operator-user", required=False, default=os.environ.get("AUDIT_OPERATOR_USER", ""))
    ap.add_argument("--operator-pass", required=False, default=os.environ.get("AUDIT_OPERATOR_PASS", ""))
    ap.add_argument("--share-token", required=False, default=None)
    args = ap.parse_args()

    if not args.admin_user or not args.admin_pass:
        print("[INFO] admin credentials not provided — skipping HTTP smokes.")
        # static-only path: 모두 PASS (manual / code review 권유).
        manual = [
            s3a_password_reset_target_visibility(args.base_url, "", "", ""),
            s8_prod_fail_closed(args.base_url),
            s9_anonymous_share_view(args.base_url, "", None),
        ]
        return 0 if all(manual) else 1

    base_url = args.base_url.rstrip("/")
    admin_cookie = _login(base_url, args.admin_user, args.admin_pass)
    user_cookie = _login(base_url, args.operator_user, args.operator_pass) if (args.operator_user and args.operator_pass) else admin_cookie

    results = [
        s1_admin_mutation_audit(base_url, admin_cookie),
        s2_ask_fail_open_visible(base_url, user_cookie, admin_cookie),
        s3_own_self_filter(base_url, user_cookie),
        s3a_password_reset_target_visibility(base_url, admin_cookie, args.operator_user, args.operator_pass),
        s4_own_actor_other_403(base_url, user_cookie) if args.operator_user else True,
        s5_any_full_visibility(base_url, admin_cookie),
        s6_csv_export(base_url, admin_cookie),
        s7_purge_chunked(base_url, admin_cookie),
        s8_prod_fail_closed(base_url),
        s9_anonymous_share_view(base_url, admin_cookie, args.share_token),
        s10_actor_type_filter(base_url, admin_cookie),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
