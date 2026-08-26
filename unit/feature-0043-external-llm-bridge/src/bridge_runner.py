#!/usr/bin/env python3
"""feature-0043 — 개인 머신 브리지 러너 (표준 라이브러리 전용).

웹 대화창에 쌓인 **내 계정의 대기 질문**을 가져와, 내 AI 런타임으로 답하고 제출한다.

## 무설치 계약 (사용자 결정 2026-08-26)

이 파일은 **Python 표준 라이브러리만** 쓴다 — `pip install` 이 필요한 모듈(`mcp`, `requests`,
`httpx` …)을 import 하지 않는다. 파일 하나를 내려받아 `python3 bridge_runner.py` 로 실행하면 끝이다.
(`unit/feature-0043-external-llm-bridge/tests/test_bridge_runner_stdlib.py` 가 AST 로 이 계약을 잠근다.)

주 경로는 애초에 러너조차 필요 없다: `https://<host>/api/ai/mcp` 를 AI 클라이언트에 URL+토큰으로
등록하고 "대기 중인 질문을 처리해줘" 라고 말하면 같은 도구를 그 AI 가 직접 호출한다. 이 러너는
**그 과정을 상주시켜 자동화**하고 싶을 때 쓰는 보조 수단이다.

## 사용

    export BRIDGE_API_BASE=https://mysql-ai.company.local
    export BRIDGE_TOKEN=<OAuth access token — /ai/connect 에서 발급>

    # (1) 대기 질문만 확인 — 기본. 가져오지 않는다(점유 없음).
    python3 bridge_runner.py

    # (2) 한 건 가져와 출력 — 내 AI 에게 붙여넣어 답을 만들고 (3) 으로 제출
    python3 bridge_runner.py --claim
    python3 bridge_runner.py --submit <task_id> --answer-file answer.txt

    # (4) 완전 자동 — 질문을 명령의 stdin 으로 넘기고 stdout 을 답변으로 제출
    python3 bridge_runner.py --watch --exec "claude -p"

`--exec` 가 특정 CLI 를 강제하지 않는 이유: 개인 머신마다 AI 런타임 진입 방식이 다르다.
"stdin 으로 질문을 받아 stdout 으로 답을 내는 것" 만 만족하면 무엇이든 된다.

## 왜 폴링인가

MCP `sampling`(서버→클라이언트 push)은 프로토콜 2026-07-28 에서 폐기됐고(SEP-2577), Claude Code 가
미지원이다(anthropics/claude-code#1785). 표준 도구로 당겨오는 편이 오늘 동작하고 내일도 남는다.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_POLL_SEC = 20
DEFAULT_TIMEOUT_SEC = 120


def _base_url() -> str:
    raw = (os.getenv("BRIDGE_API_BASE") or "").strip().rstrip("/")
    if not raw:
        _die("환경변수 BRIDGE_API_BASE 가 필요합니다 (예: https://mysql-ai.company.local)")
    parsed = urllib.parse.urlparse(raw)
    # https 강제 — Bearer 토큰이 평문으로 나가지 않게 한다. loopback 만 예외(로컬 개발).
    if parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost"):
        _die(f"BRIDGE_API_BASE 는 https 여야 합니다 (현재: {parsed.scheme}). "
             "토큰이 평문으로 전송됩니다.")
    return raw


def _token() -> str:
    tok = (os.getenv("BRIDGE_TOKEN") or "").strip()
    if not tok:
        _die("환경변수 BRIDGE_TOKEN 이 필요합니다 (웹의 '외부 AI 연결' 에서 발급).")
    return tok


def _ssl_context() -> ssl.SSLContext | None:
    """사내 사설 CA 지원. 검증을 끄는 옵션은 두지 않는다 — Bearer 토큰이 MITM 에 노출된다."""
    ca = (os.getenv("BRIDGE_CA_BUNDLE") or "").strip()
    if ca:
        return ssl.create_default_context(cafile=ca)
    return None


def _post(path: str, payload: dict, timeout: int = 30) -> dict:
    url = f"{_base_url()}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8") or "{}").get("error", "")
        except Exception:
            pass
        raise BridgeError(f"HTTP {exc.code} {path}: {detail or exc.reason}") from None
    except urllib.error.URLError as exc:
        raise BridgeError(f"연결 실패 {path}: {exc.reason}") from None


class BridgeError(RuntimeError):
    pass


def _die(msg: str) -> "None":
    print(f"[bridge-runner] {msg}", file=sys.stderr)
    raise SystemExit(2)


# ── 동작 ─────────────────────────────────────────────────────────────────────


def cmd_list(args) -> int:
    data = _post("/api/ai/tools/list_open_requests", {"limit": args.limit})
    count = int(data.get("count") or 0)
    print(f"대기 질문 {count}건")
    if count:
        print(data.get("requests") or "")
    return 0


def _compose_prompt(claimed: dict) -> str:
    """점유 결과 → AI 에게 넘길 프롬프트.

    `conversation_context` 를 빼먹으면 후속 질문("그럼 그건?")이 앞 turn 없이 도착해 서버가
    애써 실어 보낸 문맥이 버려진다 — API 까지만 연결되고 러너에서 끊기는 결함이었다
    (codex 재리뷰 P1).
    """
    parts = []
    context = str(claimed.get("conversation_context") or "").strip()
    if context:
        parts.append("[이전 대화]\n" + context)
    parts.append("[질문]\n" + str(claimed.get("question") or "").strip())
    return "\n\n".join(parts)


def cmd_claim(args) -> int:
    task_id = args.task_id
    if not task_id:
        listing = _post("/api/ai/tools/list_open_requests", {"limit": 1})
        ids = listing.get("task_ids") or []
        if not ids:
            print("대기 질문이 없습니다.")
            return 0
        task_id = ids[0]
    data = _post("/api/ai/tools/claim_request", {"task_id": task_id})
    print(f"task_id: {data.get('task_id')}")
    print(_compose_prompt(data))
    return 0


def cmd_submit(args) -> int:
    if args.answer_file:
        with open(args.answer_file, encoding="utf-8") as fh:
            answer = fh.read()
    else:
        answer = sys.stdin.read()
    if not answer.strip():
        _die("빈 답변은 제출하지 않습니다.")
    data = _post("/api/ai/tools/submit_answer", {
        "task_id": args.task_id,
        "answer": answer,
        # 근거 선언 — 이 러너는 도구 조회 없이 질문만 넘겼으므로 자기 task 만 선언한다.
        # 내 AI 가 도구로 조사했다면 그 task_id 들을 여기 넣어야 교차오염 대조가 의미를 갖는다.
        "source_tasks": [args.task_id],
    }, timeout=60)
    delivered = data.get("delivered_to_conversation")
    print(f"제출 완료 (대화 전달: {'예' if delivered else '아니오'})")
    findings = data.get("cross_session_findings") or []
    if findings:
        print(f"⚠ 교차오염 판정: {findings}", file=sys.stderr)
    return 0


def _run_exec(command: str, question: str, timeout: int) -> str:
    """질문을 명령의 stdin 으로 넘기고 stdout 을 답변으로 받는다."""
    proc = subprocess.run(
        command, shell=True, input=question, capture_output=True,
        text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise BridgeError(
            f"--exec 명령이 {proc.returncode} 로 종료: {(proc.stderr or '').strip()[:400]}")
    return proc.stdout


def cmd_watch(args) -> int:
    if not args.exec_cmd:
        _die("--watch 에는 --exec 이 필요합니다 (질문을 stdin 으로 받아 답을 stdout 으로 내는 명령).")
    print(f"[bridge-runner] 감시 시작 — {args.poll}초 주기, exec={args.exec_cmd!r}")
    while True:
        try:
            listing = _post("/api/ai/tools/list_open_requests", {"limit": 1})
            ids = listing.get("task_ids") or []
            if not ids:
                time.sleep(args.poll)
                continue
            claimed = _post("/api/ai/tools/claim_request", {"task_id": ids[0]})
            task_id = str(claimed.get("task_id") or "")
            prompt = _compose_prompt(claimed)
            print(f"[bridge-runner] 처리 중 task={task_id}")
            answer = _run_exec(args.exec_cmd, prompt, args.timeout)
            if not answer.strip():
                print(f"[bridge-runner] 빈 답변 — 건너뜀 task={task_id}", file=sys.stderr)
                time.sleep(args.poll)
                continue
            _post("/api/ai/tools/submit_answer", {
                "task_id": task_id, "answer": answer, "source_tasks": [task_id],
            }, timeout=60)
            print(f"[bridge-runner] 제출 완료 task={task_id}")
        except KeyboardInterrupt:
            print("\n[bridge-runner] 중단")
            return 0
        except BridgeError as exc:
            # 일시 장애로 러너가 죽지 않게 한다 — 대기 질문은 서버에 남아 있고 다음 주기에 다시 온다.
            print(f"[bridge-runner] {exc}", file=sys.stderr)
            time.sleep(args.poll)
        except subprocess.TimeoutExpired:
            print(f"[bridge-runner] --exec 시간 초과({args.timeout}s)", file=sys.stderr)
            time.sleep(args.poll)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="bridge_runner.py",
        description="웹 대화 대기 질문을 내 AI 로 처리하는 브리지 러너 (표준 라이브러리 전용)")
    p.add_argument("--limit", type=int, default=20, help="목록 조회 건수 (기본 20)")
    p.add_argument("--claim", action="store_true", help="대기 질문 1건을 가져온다")
    p.add_argument("--task-id", default="", help="대상 task_id")
    p.add_argument("--submit", dest="submit", action="store_true", help="답변을 제출한다")
    p.add_argument("--answer-file", default="", help="답변 본문 파일 (없으면 stdin)")
    p.add_argument("--watch", action="store_true", help="상주하며 자동 처리")
    p.add_argument("--exec", dest="exec_cmd", default="",
                   help="질문을 stdin 으로 받아 답을 stdout 으로 내는 명령 (예: 'claude -p')")
    p.add_argument("--poll", type=int, default=DEFAULT_POLL_SEC, help="폴링 주기(초)")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SEC, help="--exec 시간 제한(초)")
    args = p.parse_args(argv)

    try:
        if args.watch:
            return cmd_watch(args)
        if args.submit:
            if not args.task_id:
                _die("--submit 에는 --task-id 가 필요합니다.")
            return cmd_submit(args)
        if args.claim:
            return cmd_claim(args)
        return cmd_list(args)
    except BridgeError as exc:
        print(f"[bridge-runner] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
