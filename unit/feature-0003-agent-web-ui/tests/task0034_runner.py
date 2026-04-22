"""TASK-0034 complex QA performance test runner.

Runs 5 complex Q&A conversations against both:
  - Local LLM (model=core, sequential)
  - Commercial API (model=gpt-5.4-mini, parallel)

Each conversation continues up to 20 turns using heuristic follow-ups
based on what the assistant has produced so far. Results (turn-by-turn
SQL/answer/timings) are saved as JSON per conversation for later
analysis and DB truth verification.

Usage:
  python3 tests/task0034_runner.py --target local
  python3 tests/task0034_runner.py --target api
  python3 tests/task0034_runner.py --target all

Environment:
  Reads OPENAI_API_KEY from repo's .env.
  Uses WEB_BOOTSTRAP_ADMIN_USERNAME / WEB_BOOTSTRAP_ADMIN_PASSWORD
  from .env for login.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[2]
RUNS_DIR = THIS_DIR / "task0034_runs"
ENV_FILE = REPO_ROOT / ".env"

sys.path.insert(0, str(THIS_DIR))
from task0034_questions import QUESTIONS  # noqa: E402

BASE_URL = os.environ.get("TASK0034_BASE_URL", "https://localhost:18080")
VERIFY_TLS = False
MAX_TURNS_DEFAULT = 20
# 서버 run_timeout_sec = max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)
# = max(300*3, 180) = 900s (현재 .env 기준). 클라이언트가 서버보다 먼저 포기하면
# 서버 쪽에 좀비 agent 스레드가 남아 다음 턴/질문 요청을 막으므로, 클라이언트
# 예산을 60s 여유를 두고 서버 self-timeout 이후까지 기다리도록 한다.
ASK_TIMEOUT_SEC = 960.0
PER_TURN_SLEEP = 0.5
# TASK-0041: /api/ask 가 httpx.ReadTimeout 으로 끊긴 후에도 서버에서 agent 는 계속
# 돌 수 있다. 이 경우 /api/ask_status + /api/ask_result long-poll 로 최종 응답을
# 회수해 해당 턴에 병합한다. 서버 run_timeout_sec=900s 이므로 여유 60s.
ATTACH_TIMEOUT_SEC = float(os.environ.get("TASK0034_ATTACH_TIMEOUT_SEC", "960.0"))
ATTACH_POLL_WAIT_SEC = 45


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
            v = v[1:-1]
        data[k.strip()] = v
    return data


def encrypt_api_key(plain: str, passphrase: str) -> str:
    salt = secrets.token_bytes(16)
    iv = secrets.token_bytes(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
    key = kdf.derive(passphrase.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, plain.encode("utf-8"), None)
    return "v1:{}:{}:{}".format(
        base64.b64encode(salt).decode(),
        base64.b64encode(iv).decode(),
        base64.b64encode(ct).decode(),
    )


def short(text: str, n: int = 280) -> str:
    text = str(text or "")
    return text if len(text) <= n else text[:n] + f"…(+{len(text) - n}c)"


def _answer_summary(ans: str) -> dict[str, Any]:
    a = ans or ""
    has_md_table = bool(re.search(r"^\s*\|.+\|.*\n\s*\|[-: |]+\|", a, re.MULTILINE))
    has_csv_ref = bool(re.search(r"\.csv|전체 결과|CSV 전체|shared/out|resultset", a))
    return {
        "length": len(a),
        "has_table": has_md_table or has_csv_ref,
        "has_md_table": has_md_table,
        "has_csv_ref": has_csv_ref,
        "has_percent": ("%" in a) or ("백분율" in a) or ("비중" in a) or ("채택률" in a),
        "has_ranking": bool(re.search(r"(rank|\bTop\b|\bTOP\b|[1-9]위|상위)", a)),
    }


def _pick_follow_up(question: dict, turns: list[dict]) -> str | None:
    """Decide the next user prompt based on assistant behavior.

    Returns None to signal "we should stop — assistant produced enough".
    """
    if not turns:
        return None
    last = turns[-1]
    ans = (last.get("answer") or "").strip()
    steps = last.get("steps_count", 0)
    sqls = last.get("sql_count", 0)
    summary = _answer_summary(ans)
    already_prompted = {t.get("user") for t in turns}
    for trigger, prompt in question["follow_ups"]:
        if prompt in already_prompted:
            continue
        if trigger == "no_sql" and sqls == 0:
            return prompt
        if trigger == "no_aggregate" and sqls > 0 and not summary["has_table"]:
            return prompt
        if trigger == "no_ranking" and not summary["has_ranking"]:
            return prompt
        if trigger == "missing_pct" and not summary["has_percent"]:
            return prompt
        if trigger == "ambiguous" and summary["has_table"] and summary["length"] < 600:
            return prompt
        if trigger == "need_summary" and summary["has_table"] and summary["has_ranking"] and "요약" not in ans[-400:]:
            return prompt
    # Stop condition: answer has table + ranking + decent length and error empty.
    if summary["has_table"] and summary["has_ranking"] and summary["length"] >= 400 and not last.get("error"):
        return None
    # Fallback: if we still have unused follow-ups in order, take the next one.
    for _, prompt in question["follow_ups"]:
        if prompt not in already_prompted:
            return prompt
    return None


async def login(client: httpx.AsyncClient, username: str, password: str) -> None:
    resp = await client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("ok"):
        raise RuntimeError(f"login failed: {body}")


async def new_conversation(client: httpx.AsyncClient) -> str:
    resp = await client.post(f"{BASE_URL}/api/new_conversation", json={})
    resp.raise_for_status()
    return str(resp.json().get("conversation_id", ""))


def _steps_from_attach(meta: dict | None) -> list:
    if not isinstance(meta, dict):
        return []
    steps = meta.get("steps")
    return steps if isinstance(steps, list) else []


async def _attach_run(
    client: httpx.AsyncClient,
    conversation_id: str,
    message: str,
    t0: float,
) -> dict[str, Any]:
    """client-read-timeout 이후 서버의 현재 run 결과를 long-poll 로 회수."""
    run_id = ""
    initial_status = ""
    try:
        r = await client.get(
            f"{BASE_URL}/api/ask_status",
            params={"conversation_id": conversation_id},
            timeout=15.0,
        )
        if r.status_code == 200:
            snap = r.json()
            run_id = str(snap.get("run_id") or "")
            initial_status = str(snap.get("status") or "")
    except Exception:
        pass
    deadline = time.monotonic() + ATTACH_TIMEOUT_SEC
    last_error = ""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        wait_s = max(1, min(ATTACH_POLL_WAIT_SEC, int(remaining)))
        try:
            r = await client.get(
                f"{BASE_URL}/api/ask_result",
                params={
                    "conversation_id": conversation_id,
                    "run_id": run_id,
                    "wait": wait_s,
                },
                timeout=wait_s + 10.0,
            )
        except Exception as exc:
            last_error = f"attach-http-error: {exc!r}"
            await asyncio.sleep(1.0)
            continue
        if r.status_code != 200:
            last_error = f"attach-http-status-{r.status_code}"
            await asyncio.sleep(1.0)
            continue
        try:
            body = r.json()
        except Exception:
            last_error = "attach-non-json"
            await asyncio.sleep(1.0)
            continue
        if body.get("timeout"):
            # not yet terminal — loop again
            if not run_id and body.get("run_id"):
                run_id = str(body["run_id"])
            continue
        assistant = body.get("assistant") or {}
        meta = assistant.get("meta") if isinstance(assistant, dict) else None
        steps = _steps_from_attach(meta)
        answer = str(assistant.get("content") or "") if isinstance(assistant, dict) else ""
        sql_count = sum(
            1 for s in steps if isinstance(s, dict) and s.get("tool") == "execute_sql"
        )
        status = str(body.get("status") or "")
        error = str(body.get("error") or "")
        verdict_tag = "succeeded-via-attach" if status == "done" else f"attach-status-{status}"
        return {
            "user": message,
            "answer": answer,
            "steps": steps,
            "steps_count": len(steps),
            "executed_sql": "",
            "sql_count": sql_count,
            "csv_paths": [],
            "error": error or ("client-read-timeout" if not answer else ""),
            "elapsed_s": round(time.time() - t0, 2),
            "http_status": 200,
            "attached_after_timeout": True,
            "attach_verdict": verdict_tag,
            "attach_run_id": str(body.get("run_id") or run_id),
            "attach_initial_status": initial_status,
        }
    return {
        "user": message,
        "answer": "",
        "steps": [],
        "steps_count": 0,
        "executed_sql": "",
        "sql_count": 0,
        "csv_paths": [],
        "error": last_error or "attach-deadline-exceeded",
        "elapsed_s": round(time.time() - t0, 2),
        "http_status": None,
        "attached_after_timeout": True,
        "attach_verdict": "attach-timeout",
        "attach_run_id": run_id,
        "attach_initial_status": initial_status,
    }


async def ask_turn(
    client: httpx.AsyncClient,
    message: str,
    model: str,
    conversation_id: str,
    api_key_plain: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message": message,
        "model": model,
        "conversation_id": conversation_id,
    }
    if api_key_plain:
        passphrase = secrets.token_hex(16)
        payload["api_key_cipher"] = encrypt_api_key(api_key_plain, passphrase)
        payload["api_key_passphrase"] = passphrase
    t0 = time.time()
    status = 0
    resp = None
    # Retry-on-429 with exponential backoff — server rate-limits concurrent
    # requests per-account (WEB_PARALLEL_LIMIT), and a follow-up can race with
    # upstream completion release.
    for attempt in range(6):
        try:
            resp = await client.post(
                f"{BASE_URL}/api/ask",
                json=payload,
                timeout=ASK_TIMEOUT_SEC,
            )
        except httpx.ReadTimeout:
            # TASK-0041: client-read-timeout 상황에서도 서버의 agent 스레드는
            # 계속 실행 중이므로, /api/ask_status + /api/ask_result long-poll 로
            # 동일 run 의 최종 결과를 회수한다.
            return await _attach_run(client, conversation_id, message, t0)
        status = resp.status_code
        if status != 429:
            break
        await asyncio.sleep(2 ** attempt)  # 1,2,4,8,16,32s
    elapsed = round(time.time() - t0, 2)
    if resp is None:
        return {
            "user": message, "answer": "", "steps": [], "steps_count": 0,
            "executed_sql": "", "sql_count": 0, "csv_paths": [],
            "error": "no-response", "elapsed_s": elapsed, "http_status": None,
        }
    try:
        body = resp.json()
    except Exception:
        return {
            "user": message, "answer": "", "steps": [], "steps_count": 0,
            "executed_sql": "", "sql_count": 0, "csv_paths": [],
            "error": f"non-json-response-status-{status}",
            "elapsed_s": elapsed, "http_status": status,
        }
    steps = body.get("steps") or []
    sql_count = 0
    for s in steps if isinstance(steps, list) else []:
        tool = (s or {}).get("tool") if isinstance(s, dict) else None
        if tool == "execute_sql":
            sql_count += 1
    answer = str(body.get("output", ""))
    return {
        "user": message,
        "answer": answer,
        "steps": steps if isinstance(steps, list) else [],
        "steps_count": len(steps) if isinstance(steps, list) else 0,
        "executed_sql": str(body.get("executed_sql", "")),
        "sql_count": sql_count,
        "csv_paths": body.get("result_csv_paths") or [],
        "error": str(body.get("error", "")),
        "elapsed_s": elapsed,
        "http_status": status,
    }


async def run_one_conversation(
    question: dict,
    model: str,
    username: str,
    password: str,
    api_key_plain: str | None,
    max_turns: int = MAX_TURNS_DEFAULT,
    label: str = "",
) -> dict[str, Any]:
    out_path = RUNS_DIR / f"{label}.json"
    result: dict[str, Any] = {
        "qid": question["qid"],
        "title": question["title"],
        "model": model,
        "label": label,
        "conversation_id": None,
        "turns": [],
        "final_verdict": "",
        "total_elapsed_s": 0.0,
    }
    start = time.time()
    async with httpx.AsyncClient(verify=VERIFY_TLS, timeout=60.0) as client:
        try:
            await login(client, username, password)
            conv_id = await new_conversation(client)
            result["conversation_id"] = conv_id
            next_prompt: str | None = question["main"]
            for turn_idx in range(max_turns):
                if next_prompt is None:
                    result["final_verdict"] = "stopped-by-heuristic (answer sufficient)"
                    break
                turn = await ask_turn(client, next_prompt, model, conv_id, api_key_plain)
                turn["turn_idx"] = turn_idx + 1
                result["turns"].append(turn)
                result["total_elapsed_s"] = round(time.time() - start, 2)
                # Persist progress after every turn.
                out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                if turn.get("http_status") and turn["http_status"] >= 500:
                    result["final_verdict"] = f"server-error-{turn['http_status']}"
                    break
                if turn.get("error"):
                    result["final_verdict"] = f"assistant-error: {short(turn['error'], 120)}"
                    # Don't break — give follow-up a chance unless it's auth.
                    if "auth" in str(turn["error"]).lower():
                        break
                await asyncio.sleep(PER_TURN_SLEEP)
                next_prompt = _pick_follow_up(question, result["turns"])
            else:
                result["final_verdict"] = "max-turns-reached"
        except Exception as exc:
            result["final_verdict"] = f"runner-exception: {exc!r}"
    if not result["final_verdict"]:
        result["final_verdict"] = "loop-exited-unknown"
    result["total_elapsed_s"] = round(time.time() - start, 2)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[{label}] model={model} qid={question['qid']} turns={len(result['turns'])} "
        f"verdict={result['final_verdict']} elapsed={result['total_elapsed_s']}s",
        flush=True,
    )
    return result


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["local", "api", "all"], default="all")
    ap.add_argument("--max-turns", type=int, default=MAX_TURNS_DEFAULT)
    ap.add_argument("--only", help="comma-separated qid filter (e.g. Q1,Q3)")
    args = ap.parse_args()

    env = load_env_file(ENV_FILE)
    username = env.get("WEB_BOOTSTRAP_ADMIN_USERNAME", "bootstrap_admin")
    password = env.get("WEB_BOOTSTRAP_ADMIN_PASSWORD", "")
    api_key = env.get("OPENAI_API_KEY", "")
    if not password:
        print("ERROR: WEB_BOOTSTRAP_ADMIN_PASSWORD not in .env", file=sys.stderr)
        return 2
    if args.target in ("api", "all") and not api_key:
        print("ERROR: OPENAI_API_KEY not in .env", file=sys.stderr)
        return 2
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    only = set((args.only or "").split(",")) if args.only else None
    picked = [q for q in QUESTIONS if (not only) or (q["qid"] in only)]
    if not picked:
        print("ERROR: no question matched --only", file=sys.stderr)
        return 2

    # NOTE: server rate-limits concurrent requests per account
    # (WEB_PARALLEL_LIMIT default=6). When 5 conversations all start turn 1
    # simultaneously they hog the slots, and any follow-up turn from a
    # conversation that finished first gets 429 because the remaining 4+
    # in-flight turns fill the limit. Even with client-side retry-on-429
    # backoff, they all pile up together and never catch a gap. Therefore
    # we run sequentially by default (same for API and local). Set
    # TASK0034_PARALLEL_API=1 to try parallel anyway.
    parallel_api = os.environ.get("TASK0034_PARALLEL_API") == "1"

    if args.target in ("api", "all"):
        if parallel_api:
            tasks = [
                run_one_conversation(
                    q, "gpt-5.4-mini", username, password, api_key,
                    max_turns=args.max_turns, label=f"api-{q['qid']}",
                )
                for q in picked
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            for q in picked:
                await run_one_conversation(
                    q, "gpt-5.4-mini", username, password, api_key,
                    max_turns=args.max_turns, label=f"api-{q['qid']}",
                )
    if args.target in ("local", "all"):
        for q in picked:
            await run_one_conversation(
                q, "core", username, password, None,
                max_turns=args.max_turns, label=f"local-{q['qid']}",
            )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
