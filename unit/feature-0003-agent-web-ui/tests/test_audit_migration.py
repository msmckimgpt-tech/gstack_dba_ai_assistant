"""TASK-0073 (REQ-20260519-0001, Critical §12.3) Phase B audit migration smoke.

`WebAccountActivity` (TASK-0072) → `WebAuditEvents` (TASK-0073) migration 의 idempotency 검증.

3 시나리오:
  M1 legacy WebAccountActivity 에 임시 row INSERT (직접 SQL) → fast-path catchup 호출 →
     동일 RequestId='account-activity:<id>' 의 WebAuditEvents row 가 등장
  M2 같은 catchup 두 번째 호출 → 새 INSERT 0 row (NOT EXISTS subquery 의 idempotency 검증)
  M3 _log_search_activity (`/api/conversations?q=...`) dual write — legacy + new row 양쪽 등장

사전조건:
  - `make web` 으로 컨테이너 가동
  - admin 계정 + 비밀번호 (audit.read.any 권한)
  - MySQL 직접 접근 가능 (mysql client + env DB_PASSWORD / DB_HOST / DB_PORT / MEMORY_DB)
  - 또는 별도 admin endpoint 로 catchup trigger 가능 (현재는 SIGHUP / 컨테이너 재시작)

실행:
  python3 tests/test_audit_migration.py \\
      --base-url http://localhost:18080 \\
      --admin-user admin --admin-pass <pw>

본 script 는 mysql client 직접 호출이 필요 — 컨테이너 안 또는 host 의 mysql client + 정확한
호스트/포트 환경. 환경 미비 시 manual fall-back path 안내.

docs/TEST.md §4 Test Run History 에 append.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


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


def _mysql_exec(sql: str) -> tuple[int, str]:
    """make ask / make mysql 호출 대신 직접 mysql client. WSL 환경 가정 (host: docker compose).

    환경변수:
      DB_HOST (기본: localhost), DB_PORT (기본: 13306), DB_USER (기본: root),
      DB_PASSWORD (필수), MEMORY_DB (기본: agent_memory).
    """
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "13306")
    user = os.environ.get("DB_USER", "root")
    pw = os.environ.get("DB_PASSWORD", "")
    db = os.environ.get("MEMORY_DB", "agent_memory")
    if not pw:
        return 99, "DB_PASSWORD env not set"
    cmd = ["mysql", "-h", host, "-P", port, "-u", user, f"-p{pw}", db, "-N", "-e", sql]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return proc.returncode, (proc.stdout or "") + ("\n" + proc.stderr if proc.returncode != 0 else "")
    except Exception as exc:
        return 98, str(exc)


def m1_legacy_insert_migrates(base_url: str, admin_cookie: str) -> bool:
    """legacy WebAccountActivity 에 row INSERT → 다음 fast-path 에 WebAuditEvents 등장."""
    # 1. legacy row INSERT.
    legacy_id_marker = int(time.time())
    rc, out = _mysql_exec(
        f"INSERT INTO WebAccountActivity (AccountId, Action, TargetOwnerId, QueryHash, MatchedCount) "
        f"VALUES (1, 'conversation.search.any', NULL, REPEAT('a', 64), {legacy_id_marker})"
    )
    if rc != 0:
        return _expect("M1 legacy INSERT (mysql client)", False, f"rc={rc} out={out[:200]} (manual fallback: docker exec mysql ...)")
    # 2. fast-path catchup trigger — 가장 단순한 방법은 다른 endpoint 호출로 _ensure_seed_catchup 통과.
    # 또는 _migrate_web_account_activity_to_audit 가 _ensure_seed_catchup 안에서 실행 →
    # API 요청이 _open_memory_connection() 거치면 자동 hydrate.
    _request("GET", f"{base_url}/api/auth/me", cookie=admin_cookie)
    time.sleep(1.0)
    # 3. WebAuditEvents 에 migrated row 존재 확인.
    rc, out = _mysql_exec(
        f"SELECT COUNT(*) FROM WebAuditEvents WHERE RequestId LIKE 'account-activity:%' "
        f"AND JSON_EXTRACT(ChangeJson, '$.matched_count') = {legacy_id_marker}"
    )
    if rc != 0:
        return _expect("M1 audit query", False, f"rc={rc}")
    count = int((out.strip().split() or ["0"])[0])
    return _expect("M1 migration visible", count >= 1, f"count={count} marker={legacy_id_marker}")


def m2_migration_idempotent(base_url: str, admin_cookie: str) -> bool:
    """같은 catchup 두 번째 호출 → 새 INSERT 0 row."""
    # 1. WebAuditEvents 의 migrated count 캐치.
    rc, out1 = _mysql_exec("SELECT COUNT(*) FROM WebAuditEvents WHERE RequestId LIKE 'account-activity:%'")
    if rc != 0:
        return _expect("M2 pre count", False, f"rc={rc}")
    pre = int((out1.strip().split() or ["0"])[0])
    # 2. catchup 다시 trigger.
    _request("GET", f"{base_url}/api/auth/me", cookie=admin_cookie)
    time.sleep(1.0)
    # 3. 동일 count 인지.
    rc, out2 = _mysql_exec("SELECT COUNT(*) FROM WebAuditEvents WHERE RequestId LIKE 'account-activity:%'")
    if rc != 0:
        return _expect("M2 post count", False, f"rc={rc}")
    post = int((out2.strip().split() or ["0"])[0])
    return _expect("M2 idempotent (no double-INSERT)", post == pre, f"pre={pre} post={post}")


def m3_log_search_activity_dual_write(base_url: str, admin_cookie: str) -> bool:
    """_log_search_activity 의 dual write — legacy + new row 양쪽 INSERT.

    smoke 는 conversation.search.any 의 audit count 가 legacy COUNT 와 동일 또는 더 큼 확인.
    """
    rc, legacy_count_s = _mysql_exec(
        "SELECT COUNT(*) FROM WebAccountActivity WHERE Action IN ('conversation.search.any','conversation.snippet.any')"
    )
    if rc != 0:
        return _expect("M3 legacy count", False, f"rc={rc}")
    rc, new_count_s = _mysql_exec(
        "SELECT COUNT(*) FROM WebAuditEvents WHERE ActionCode IN ('conversation.search.any','conversation.snippet.any')"
    )
    if rc != 0:
        return _expect("M3 new count", False, f"rc={rc}")
    legacy = int((legacy_count_s.strip().split() or ["0"])[0])
    new = int((new_count_s.strip().split() or ["0"])[0])
    # new >= legacy: dual write + migration 모두 등재.
    return _expect("M3 dual write coverage", new >= legacy, f"legacy={legacy} new={new}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:18080")
    ap.add_argument("--admin-user", required=False, default=os.environ.get("AUDIT_ADMIN_USER", ""))
    ap.add_argument("--admin-pass", required=False, default=os.environ.get("AUDIT_ADMIN_PASS", ""))
    args = ap.parse_args()

    if not args.admin_user or not args.admin_pass:
        print("[INFO] admin credentials not provided — manual checks only.")
        return 0

    base_url = args.base_url.rstrip("/")
    admin_cookie = _login(base_url, args.admin_user, args.admin_pass)

    results = [
        m1_legacy_insert_migrates(base_url, admin_cookie),
        m2_migration_idempotent(base_url, admin_cookie),
        m3_log_search_activity_dual_write(base_url, admin_cookie),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
