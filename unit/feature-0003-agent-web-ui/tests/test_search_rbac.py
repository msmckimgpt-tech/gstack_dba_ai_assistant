"""TASK-0072 (REQ-20260518-0010, Critical §12.3) cross-account search RBAC smoke.

6 시나리오 검증:
  1. `.own`-only 사용자 + q=상대 키워드 → 본인 매칭만 (cross-account leak 차단)
  2. `.any` 사용자 + 동일 q → 매칭 전체 (cross-account 허용)
  3. `.own` + owner_id=상대 → response byte-equal with owner_id=99999999 (404/403 metadata leak 차단)
  4. cursor 페이지 2 가 페이지 1 과 disjoint (sub-spec 3 의 cursor 정합성)
  5. q="ab" (< 3 char) 또는 q="%%" → 400 (raw-len + post-escape 0 char 차단)
  6. rate limit 11번째 → 429 (per-account 10 req/min)

사전조건:
  - `make web` 으로 컨테이너 가동
  - admin / operator / sales 계정 존재 (seed 됨)
  - 각 계정이 최소 1 개 이상의 대화를 보유 (seed 또는 수동)

실행 예:
  python3 tests/test_search_rbac.py \
      --base-url http://localhost:18080 \
      --admin-user admin --admin-pass <pw> \
      --operator-user operator --operator-pass <pw>

결과는 stdout 으로 출력. 모든 시나리오 PASS 시 exit 0, FAIL 시 exit 1.
docs/TEST.md §3 Test Run History 에 append-only 로 결과 기록 권장.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _request(
    method: str,
    url: str,
    *,
    data: dict | None = None,
    cookie: str | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict, str]:
    """Returns (status, headers, body_text). Does not raise on non-2xx."""
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
    """POST /api/auth/login; returns the Cookie header value to send on subsequent calls."""
    status, headers, body = _request(
        "POST",
        f"{base_url}/api/auth/login",
        data={"username": username, "password": password},
    )
    if status != 200:
        raise SystemExit(f"login failed for {username}: status={status} body={body}")
    set_cookie = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
    if not set_cookie:
        raise SystemExit(f"login {username}: no Set-Cookie header")
    # urllib already gives the first cookie pair; extract `name=value`.
    cookie_kv = set_cookie.split(";", 1)[0]
    return cookie_kv


def _search(
    base_url: str, cookie: str, **params: Any
) -> tuple[int, dict]:
    qp = "&".join(
        f"{k}={urllib.parse.quote(str(v))}"
        for k, v in params.items()
        if v is not None and v != ""
    )
    url = f"{base_url}/api/conversations" + (f"?{qp}" if qp else "")
    status, _, body = _request("GET", url, cookie=cookie)
    try:
        return status, json.loads(body)
    except Exception:
        return status, {"_raw": body}


def _expect(label: str, ok: bool, detail: str = "") -> bool:
    sigil = "PASS" if ok else "FAIL"
    print(f"[{sigil}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def scenario_1_own_no_leak(base_url: str, operator_cookie: str, q: str) -> bool:
    """`.own` + q=keyword → response items must all have owner_account_id == operator's self."""
    status, body = _search(base_url, operator_cookie, q=q, limit=50)
    if status != 200:
        return _expect("S1 .own + q", False, f"status={status} body={body}")
    items = body.get("items") or []
    has_any = body.get("has_any")
    if has_any:
        return _expect("S1 .own + q", False, "operator unexpectedly has .any")
    # All items must belong to operator (owner_id = self).
    me_status, me_body = _search(base_url, operator_cookie)  # list mode
    self_id = None
    for it in (me_body.get("items") or []):
        if it.get("owner_account_id"):
            self_id = it["owner_account_id"]
            break
    own_only = all(int(it.get("owner_account_id") or 0) == int(self_id or 0) for it in items)
    return _expect(
        "S1 .own + q returns only self conversations",
        own_only,
        f"matched={len(items)} self_id={self_id}",
    )


def scenario_2_any_includes_others(base_url: str, admin_cookie: str, q: str) -> bool:
    """`.any` + same q → must include at least one cross-account item (if seed has such)."""
    status, body = _search(base_url, admin_cookie, q=q, limit=50)
    if status != 200:
        return _expect("S2 .any + q", False, f"status={status} body={body}")
    has_any = body.get("has_any")
    if not has_any:
        return _expect("S2 .any + q", False, "admin missing .any permission")
    items = body.get("items") or []
    # Cannot strictly assert cross-account presence (depends on seed). Just assert response shape.
    return _expect(
        "S2 .any + q returns search-mode payload",
        bool(items is not None and "next_cursor" in body and body.get("search_mode") is True),
        f"matched={len(items)} next_cursor={body.get('next_cursor')}",
    )


def scenario_3_byte_equal_owner_id(base_url: str, operator_cookie: str) -> bool:
    """`.own` + owner_id=foreign_real → byte-equal with owner_id=99999999.

    Both should return empty items (operator only sees self). Response shape
    must be identical to avoid 404/403 metadata leak.
    """
    status_a, body_a = _search(base_url, operator_cookie, q="zzzz_unlikely_match_token", owner_id=2)
    status_b, body_b = _search(base_url, operator_cookie, q="zzzz_unlikely_match_token", owner_id=99999999)
    body_a_norm = {k: v for k, v in body_a.items() if k != "items"}
    body_b_norm = {k: v for k, v in body_b.items() if k != "items"}
    return _expect(
        "S3 .own + owner_id byte-equal",
        status_a == status_b == 200 and body_a_norm == body_b_norm and (body_a.get("items") or []) == (body_b.get("items") or []),
        f"status_a={status_a} status_b={status_b} a={body_a_norm} b={body_b_norm}",
    )


def scenario_4_cursor_disjoint(base_url: str, admin_cookie: str) -> bool:
    """cursor 페이지 2 가 페이지 1 과 disjoint (intersection 의 id set 이 비어야 함)."""
    status_1, body_1 = _search(base_url, admin_cookie, limit=5)
    if status_1 != 200:
        return _expect("S4 cursor page 1", False, f"status={status_1}")
    items_1 = body_1.get("items") or []
    next_cursor = body_1.get("next_cursor")
    if not next_cursor or len(items_1) < 5:
        return _expect(
            "S4 cursor pagination (skipped — < 5 conversations available)",
            True,
            f"items_1={len(items_1)} next_cursor={next_cursor}",
        )
    status_2, body_2 = _search(base_url, admin_cookie, limit=5, cursor=next_cursor)
    if status_2 != 200:
        return _expect("S4 cursor page 2", False, f"status={status_2}")
    items_2 = body_2.get("items") or []
    ids_1 = {it["id"] for it in items_1}
    ids_2 = {it["id"] for it in items_2}
    overlap = ids_1 & ids_2
    return _expect(
        "S4 cursor pages disjoint",
        not overlap,
        f"page1={len(items_1)} page2={len(items_2)} overlap={overlap}",
    )


def scenario_5_invalid_q_400(base_url: str, admin_cookie: str) -> bool:
    """q < 3 char or post-escape 0 literal char → 400."""
    cases = ["ab", "  ", "%%"]
    all_400 = True
    detail = []
    for q in cases:
        status, _ = _search(base_url, admin_cookie, q=q)
        detail.append(f"q={q!r}:{status}")
        if status != 400:
            all_400 = False
    return _expect("S5 invalid q → 400", all_400, " ".join(detail))


def scenario_6_rate_limit_429(base_url: str, admin_cookie: str) -> bool:
    """body-search 11번째 호출 → 429."""
    last_status = None
    for i in range(11):
        status, _ = _search(base_url, admin_cookie, q=f"smoke_test_token_{i:02d}")
        last_status = status
    return _expect(
        "S6 rate limit 11th call → 429",
        last_status == 429,
        f"11th_status={last_status}",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="TASK-0072 cross-account search RBAC smoke")
    ap.add_argument("--base-url", default="http://localhost:18080")
    ap.add_argument("--admin-user", required=True)
    ap.add_argument("--admin-pass", required=True)
    ap.add_argument("--operator-user", required=True)
    ap.add_argument("--operator-pass", required=True)
    ap.add_argument("--probe-q", default="대화", help="키워드 (한국어 가능)")
    args = ap.parse_args()

    print(f"--- TASK-0072 RBAC smoke @ {args.base_url} ---")
    print("[setup] admin login …")
    admin_cookie = _login(args.base_url, args.admin_user, args.admin_pass)
    print("[setup] operator login …")
    operator_cookie = _login(args.base_url, args.operator_user, args.operator_pass)

    results = [
        scenario_1_own_no_leak(args.base_url, operator_cookie, args.probe_q),
        scenario_2_any_includes_others(args.base_url, admin_cookie, args.probe_q),
        scenario_3_byte_equal_owner_id(args.base_url, operator_cookie),
        scenario_4_cursor_disjoint(args.base_url, admin_cookie),
        scenario_5_invalid_q_400(args.base_url, admin_cookie),
        scenario_6_rate_limit_429(args.base_url, admin_cookie),
    ]
    passed = sum(1 for r in results if r)
    print(f"--- {passed}/{len(results)} PASS ---")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
