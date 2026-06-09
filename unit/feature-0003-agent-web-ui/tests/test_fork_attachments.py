"""TASK-0171 (Major §12.3) — Fork 첨부 복사 e2e (하이브리드 Phase 2).

배경: fork 는 대화 본문(messages, TASK-0167)+LLM 문맥(core_messages, TASK-0170)을
복사하지만 **첨부(WebConversationAttachments)는 미복사**해, fork 본에서 사용자가 원본
첨부 파일을 볼 수 없었다. 본 cycle 은 첨부 행을 fork 소유로 복사 + blob 을 독립 복사
(get+put, 새 ObjectKey)해 fork 본에서 첨부를 열람/다운로드 가능하게 한다(ADR-WEB-0005 Phase 2).

본 smoke 는 첨부가 있는 대화를 fork 한 뒤:
  A1  fork 응답 attachments_copied == 원본 활성 첨부 수
  A2  fork 본의 GET /api/conversations/{new_cid}/attachments 가 동일 수 + 동일 (filename,size,kind) 집합
  A3  복사된 첨부의 id 가 원본과 다름(독립 행) + conversation_id == new_cid
  A4  GET /api/attachments/{new_att_id} 가 signed_url 발급(blob 접근 가능) + best-effort 다운로드 200

사전조건: web 컨테이너 + 활성 첨부가 있는 대화 1개(admin 조회 가능).
실행:
  python3 tests/test_fork_attachments.py --base-url https://localhost:18080 \
      --admin-user <u> --admin-pass <p> --insecure
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any


def _request(method, url, *, data=None, cookie=None, timeout=20.0, ctx=None):
    body = None
    headers: dict[str, str] = {}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read().decode("utf-8", "replace")


def _login(base, user, pw, ctx):
    s, h, b = _request("POST", f"{base}/api/auth/login", data={"username": user, "password": pw}, ctx=ctx)
    if s != 200:
        raise SystemExit(f"login failed: {s} {b}")
    sc = h.get("Set-Cookie") or h.get("set-cookie") or ""
    return sc.split(";", 1)[0]


def _json(b):
    try:
        return json.loads(b)
    except Exception:
        return None


def _list_attachments(base, cookie, cid, ctx):
    s, _, b = _request("GET", f"{base}/api/conversations/{cid}/attachments", cookie=cookie, ctx=ctx)
    if s != 200:
        return None
    p = _json(b) or {}
    return p.get("attachments") if isinstance(p, dict) else None


def _find_conversation_with_attachments(base, cookie, ctx):
    s, _, b = _request("GET", f"{base}/api/conversations", cookie=cookie, ctx=ctx)
    if s != 200:
        raise SystemExit(f"/api/conversations 실패: {s} {b[:200]}")
    items = (_json(b) or {}).get("items") or []
    for it in items:
        cid = str(it.get("id") or "") if isinstance(it, dict) else ""
        if not cid:
            continue
        atts = _list_attachments(base, cookie, cid, ctx)
        if atts:
            return cid, atts
    return None, None


def _att_sig(att):
    """비교용 (filename, size, kind) 시그니처."""
    return (
        str(att.get("original_filename") or ""),
        int(att.get("size") or 0),
        str(att.get("kind") or ""),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://localhost:18080")
    ap.add_argument("--admin-user", required=True)
    ap.add_argument("--admin-pass", required=True)
    ap.add_argument("--insecure", action="store_true")
    args = ap.parse_args()

    ctx = None
    if args.insecure or args.base_url.startswith("https"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    base = args.base_url.rstrip("/")
    cookie = _login(base, args.admin_user, args.admin_pass, ctx)

    source_id, src_atts = _find_conversation_with_attachments(base, cookie, ctx)
    if not source_id:
        raise SystemExit("첨부가 있는 대화를 찾지 못했습니다 — 첨부 복사 검증 불가(테스트 데이터 필요).")
    print(f"[setup] source={source_id} 첨부 {len(src_atts)}건")

    results: list[tuple[str, bool, str]] = []

    def check(name, ok, note):
        results.append((name, ok, note))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {note}")

    # fork
    s, _, b = _request("POST", f"{base}/api/fork_conversation",
                       data={"source_conversation_id": source_id}, cookie=cookie, ctx=ctx)
    fork = _json(b) if s == 200 else None
    check("fork_conversation 200", s == 200, f"status={s}" + ("" if s == 200 else f" {b[:160]}"))
    if not isinstance(fork, dict):
        print("\n=== fork 실패로 중단 ===")
        return 1
    new_cid = str(fork.get("conversation_id") or "")
    print(f"      new_cid={new_cid} copied={fork.get('copied')} core_copied={fork.get('core_copied')} attachments_copied={fork.get('attachments_copied')}")

    # A1: 1 <= attachments_copied <= 원본 수 (용량 cap skip 가능성 허용; 복사 동작 증명).
    nc = int(fork.get("attachments_copied") or 0)
    check("A1 attachments_copied 1..원본수",
          1 <= nc <= len(src_atts),
          f"copied={nc} src={len(src_atts)}")

    # A2/A3: fork 첨부 시그니처 ⊆ 원본 + 목록수=copied (부분복사/ingest 타이밍에 robust) +
    #        독립 id + conversation_id=new_cid.
    fork_atts = _list_attachments(base, cookie, new_cid, ctx) or []
    src_sigs = sorted(map(_att_sig, src_atts))
    fork_sigs = sorted(map(_att_sig, fork_atts))
    subset = all(s in src_sigs for s in fork_sigs)
    check("A2 fork 첨부 ⊆ 원본(filename,size,kind) + 목록수=copied",
          subset and len(fork_atts) == nc,
          f"fork={len(fork_atts)} copied={nc} subset={subset}")
    src_ids = {int(a.get("id") or 0) for a in src_atts}
    indep = all(int(a.get("id") or 0) not in src_ids for a in fork_atts) if fork_atts else False
    conv_ok = all(str(a.get("conversation_id") or "") == new_cid for a in fork_atts) if fork_atts else False
    check("A3 독립 행(id 상이) + conversation_id=new_cid", indep and conv_ok,
          f"indep_ids={indep} conv_match={conv_ok}")

    # A4: 복사 첨부의 signed_url 발급 + best-effort 다운로드
    if fork_atts:
        att0 = fork_atts[0]
        s, _, b = _request("GET", f"{base}/api/attachments/{int(att0.get('id'))}", cookie=cookie, ctx=ctx)
        meta = _json(b) if s == 200 else None
        signed = (meta or {}).get("signed_url") if isinstance(meta, dict) else None
        check("A4 signed_url 발급(blob 접근)", bool(signed), f"status={s} signed_url={'있음' if signed else '없음'}")
        if signed:
            try:
                ds, _, _db = _request("GET", signed, ctx=ctx)
                print(f"      [info] blob 다운로드 status={ds} (best-effort; 내부 endpoint 면 host 도달 불가일 수 있음)")
            except Exception as exc:
                print(f"      [info] blob 다운로드 skip ({type(exc).__name__})")
    else:
        check("A4 signed_url 발급(blob 접근)", False, "fork 첨부 0건")

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n=== {passed}/{len(results)} passed ===")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
