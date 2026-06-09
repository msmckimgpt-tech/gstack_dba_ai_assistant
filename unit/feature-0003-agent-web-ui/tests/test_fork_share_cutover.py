"""TASK-0167 (Major §12.3) — 대화 분기(fork)/공유(share)/복제(duplicate) cutover 회귀 e2e.

배경: agent runtime 데이터(AgentCoreConversations / AgentMemoryMessages /
AgentMemoryKv)는 2026-05-27 MySQL→PG cutover 로 PostgreSQL `agent_runtime`
(core_conversations / messages / kv) 로 이관됐고 MySQL 원본 테이블은 DROP 됐다.
그런데 fork / share / duplicate / public-share-view 는 raw MySQL 경로가 남아
`Table 'agent_memory.agentmemorymessages' doesn't exist` 류 HTTP 500 을 던졌다.

본 smoke 는 5개 엔드포인트가 더 이상 500 을 던지지 않음을 라이브 컨테이너에서 검증한다:
  T1  POST /api/fork_conversation                       (분기)
  T2  POST /api/conversations/{cid}/share (full)         (공유 링크 생성)
  T3  GET  /api/public/share/{token}  (anonymous)        (공유 뷰 — cross-DB merge)
  T4  POST /api/conversations/{cid}/duplicate            (복제)
  T5  POST /api/conversations/{cid}/share (anchored)     (말풍선 단위 공유 + anchor 검증)

핵심 단언: 어떤 호출도 HTTP 500 을 반환하지 않는다 (fix 전 = 500, fix 후 = 200).

사전조건:
  - web 컨테이너 가동 + AGENT_RUNTIME_READ_BACKEND=postgres
  - 메시지가 1건 이상 있는 대화가 admin 계정으로 조회 가능

실행:
  python3 tests/test_fork_share_cutover.py \\
      --base-url https://localhost:18080 \\
      --admin-user admin --admin-pass <pw> [--insecure]

docs/TEST.md §4 Test Run History 에 append.
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any


def _request(
    method: str,
    url: str,
    *,
    data: dict | None = None,
    cookie: str | None = None,
    timeout: float = 15.0,
    ctx: ssl.SSLContext | None = None,
) -> tuple[int, dict, str]:
    body_bytes = None
    headers: dict[str, str] = {}
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, data=body_bytes, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read().decode("utf-8", "replace")


def _login(base_url: str, username: str, password: str, ctx: ssl.SSLContext | None) -> str:
    status, headers, body = _request(
        "POST", f"{base_url}/api/auth/login",
        data={"username": username, "password": password}, ctx=ctx,
    )
    if status != 200:
        raise SystemExit(f"login failed for {username}: status={status} body={body}")
    set_cookie = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
    return set_cookie.split(";", 1)[0]


def _json(body: str) -> Any:
    try:
        return json.loads(body)
    except Exception:
        return None


def _pick_source_conversation(base_url: str, cookie: str, ctx) -> str | None:
    """메시지가 있을 법한 대화를 우선 선택. 없으면 첫 대화라도 반환 (500 미발생만 검증해도 의미)."""
    status, _, body = _request("GET", f"{base_url}/api/conversations", cookie=cookie, ctx=ctx)
    if status != 200:
        raise SystemExit(f"/api/conversations 실패: status={status} body={body[:200]}")
    payload = _json(body) or {}
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return None

    def _msg_count(it: dict) -> int:
        for k in ("message_count", "msg_count", "messages", "user_message_count", "total"):
            v = it.get(k)
            if isinstance(v, int):
                return v
        return 0

    with_msgs = [it for it in items if isinstance(it, dict) and _msg_count(it) > 0]
    chosen = (with_msgs or [it for it in items if isinstance(it, dict)])[0]
    return str(chosen.get("id") or "") or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://localhost:18080")
    ap.add_argument("--admin-user", required=True)
    ap.add_argument("--admin-pass", required=True)
    ap.add_argument("--insecure", action="store_true", help="self-signed TLS 무시")
    args = ap.parse_args()

    ctx: ssl.SSLContext | None = None
    if args.insecure or args.base_url.startswith("https"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    base = args.base_url.rstrip("/")
    cookie = _login(base, args.admin_user, args.admin_pass, ctx)

    source_id = _pick_source_conversation(base, cookie, ctx)
    if not source_id:
        raise SystemExit("검증 가능한 대화가 없습니다 (admin 계정에 대화 0건).")
    print(f"[setup] source_conversation_id = {source_id}")

    results: list[tuple[str, bool, str]] = []

    def check(name: str, status: int, body: str, *, ok_statuses=(200,)) -> Any:
        passed = status != 500 and status in ok_statuses
        note = f"status={status}"
        if status == 500:
            note += f" (500 — cutover 회귀 재발!) {body[:160]}"
        elif status not in ok_statuses:
            note += f" body={body[:160]}"
        results.append((name, passed, note))
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {note}")
        return _json(body)

    # T1 fork
    s, _, b = _request("POST", f"{base}/api/fork_conversation",
                       data={"source_conversation_id": source_id}, cookie=cookie, ctx=ctx)
    fork_payload = check("T1 fork_conversation", s, b)
    if isinstance(fork_payload, dict):
        print(f"      copied={fork_payload.get('copied')} new_cid={fork_payload.get('conversation_id')}")

    # T2 share (full)
    s, _, b = _request("POST", f"{base}/api/conversations/{source_id}/share",
                       data={"scope_mode": "full"}, cookie=cookie, ctx=ctx)
    share_payload = check("T2 share(full)", s, b)
    token = share_payload.get("token") if isinstance(share_payload, dict) else None

    # T3 public share view (anonymous — no cookie)
    anchor_candidate: int | None = None
    if token:
        s, _, b = _request("GET", f"{base}/api/public/share/{token}", ctx=ctx)
        view_payload = check("T3 public_share_view(anon)", s, b)
        if isinstance(view_payload, dict):
            msgs = view_payload.get("messages") or []
            print(f"      messages={len(msgs)} topic={view_payload.get('conversation', {}).get('topic')!r}")
            if msgs and isinstance(msgs[-1], dict) and isinstance(msgs[-1].get("id"), int):
                anchor_candidate = msgs[-1]["id"]
    else:
        results.append(("T3 public_share_view(anon)", False, "T2 token 미발급으로 skip"))
        print("[FAIL] T3 public_share_view(anon): T2 token 미발급으로 skip")

    # T4 duplicate
    s, _, b = _request("POST", f"{base}/api/conversations/{source_id}/duplicate", cookie=cookie, ctx=ctx)
    check("T4 duplicate", s, b)

    # T5 anchored share (anchor 검증 경로 _share_anchor_belongs_to_conversation 통과)
    if anchor_candidate is not None:
        s, _, b = _request("POST", f"{base}/api/conversations/{source_id}/share",
                           data={"scope_mode": "anchored", "anchor_message_id": anchor_candidate},
                           cookie=cookie, ctx=ctx)
        check("T5 share(anchored)", s, b)
    else:
        print("[SKIP] T5 share(anchored): anchor 후보 없음 (빈 대화)")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n=== {passed}/{total} passed ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
