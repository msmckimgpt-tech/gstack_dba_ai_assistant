#!/usr/bin/env python3
"""mysql-ai 브리지 상주 러너 — 웹 질문을 **내 머신의 AI** 로 처리한다.

## 무엇을 하는가

    wait_for_request (응답 보류)  ─── 사용자가 웹에서 질문을 보내는 그 순간 반환
        → claim_request           ─── 원자적 점유
        → 내 AI 를 호출해 답을 만든다
        → submit_answer           ─── 원 대화에 표시

## 왜 폴링이 아닌가 (사용자 요구 2026-08-27)

`list_open_requests` 를 N 초마다 부르면 두 가지가 나빠진다 — 질문이 최대 N 초 늦게 인지되고,
그 N 이 사람마다 달라 **환경 차이**가 된다. `wait_for_request` 는 호출이 한 번이고 응답이
**질문이 들어온 그 순간** 온다. 상한은 서버가 정하므로 모든 머신이 동일하게 동작한다.

여기에는 sleep 이 없다. 대기는 서버가 한다.

## 왜 런타임 무관인가

claude·codex·gemini 는 전부 "프롬프트를 주면 stdout 으로 답을 주는 CLI" 다. 그래서 **명령
템플릿 하나**로 덮인다. 로컬 LLM(ollama 등)만 HTTP 라 어댑터가 따로 있다. 어느 쪽도 이 파일
밖에 설치물을 만들지 않는다.

## 설치물이 이 파일 하나인 이유

표준 라이브러리만 쓴다. `pip install` 이 필요하면 그 순간 파이썬 환경마다 결과가 갈리고,
그것이 곧 우리가 없애려는 환경 차이다.

## 실행

    python3 bridge_agent.py --base https://<host> --token mat_... [--ca rootCA.crt]

AI 는 자동 감지한다(claude → codex → gemini → ollama 순). 고정하려면:

    --ai claude            # 또는 codex / gemini / ollama
    --cmd 'my-ai -p {prompt}'   # 완전 수동. {prompt} 자리에 질문이 들어간다

한 번만 처리하고 끝내려면 `--once`. 연결만 확인하려면 `--check`.

## 동시 처리 (2026-08-28)

기본으로 **2건을 동시에** 처리한다(`--workers`). 직렬이면 5분짜리 조사 하나가 뒤따르는
10초짜리 질문을 통째로 막는다 — 서버는 애초에 병렬이다(`claim_request` 는 원자적 점유이고
`wait_for_request` 는 여러 건을 한 번에 돌려준다). 직렬이던 것은 이 러너뿐이었다.

상한을 사용자가 정하게 두는 이유: 실질 한계는 **개인 계정의 쿼터**와 AI 런타임의 동시성인데,
그건 우리가 알 수 없다. `--workers 1` 로 종전 동작(직렬)으로 되돌린다.

## 취소 (2026-08-28)

웹에서 중단을 누르거나 새 질문으로 갈아타면 서버가 그 작업을 취소한다. 러너는 그것을
`wait_for_request` 응답의 `canceled_task_ids` 로 **즉시** 알고(별도 채널이 아니다),
진행 중이던 AI 프로세스를 **죽인다** — 죽이지 않으면 아무도 볼 수 없는 답을 위해 개인 계정
토큰이 계속 탄다. 제출도 하지 않는다(해도 서버가 409 로 거절한다).
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

_UA = "mysql-ai-bridge-agent/1"

#: 서버가 최대 55초 보류한다. 그보다 넉넉히 잡아야 **정상 대기**를 타임아웃으로 오인하지 않는다.
_WAIT_TIMEOUT_SEC = 90.0
#: 조사·응답 생성은 오래 걸릴 수 있다(도구 여러 번 호출). 점유 lease 30분보다 짧게 잡는다.
_AI_TIMEOUT_SEC = 900.0
#: 진행 중인 AI 프로세스의 **취소 확인 간격**.
#:
#: ⚠ 이건 폴링이 아니다 — 서버를 두드리지 않는다. 자식 프로세스가 끝나기를 `Thread.join(timeout)`
#: 으로 기다리면서 그 틈에 취소 여부를 보는 것이고, 대기 자체는 여전히 블로킹이다(sleep 없음).
_CANCEL_TICK_SEC = 1.0
#: 기본 동시 처리 수. 1 = 종전 직렬.
_DEFAULT_WORKERS = 2
#: 대기 질문이 있는데 한 건도 처리하지 못한 채 반복되는 라운드의 상한.
#: 넘으면 조용히 도는 대신 **크게 실패**한다 — 간격 없는 재시도는 서버를 두드리는 폴링이다.
_MAX_STALLED_ROUNDS = 20


def _log(msg: str) -> None:
    sys.stderr.write(f"[bridge] {msg}\n")
    sys.stderr.flush()


# ── 서버 호출 ────────────────────────────────────────────────────────────────


class Api:
    def __init__(self, base: str, token: str, ca: str | None):
        self.base = base.rstrip("/")
        self.token = token
        self.ctx = ssl.create_default_context(cafile=ca) if ca else None

    def call(self, tool: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}/api/ai/tools/{tool}", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json", "User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as resp:
                return json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            # 상태코드를 뭉개지 않는다 — 401(재발급 필요)·409(남이 점유)·429(상한)는
            # 호출측이 서로 다르게 대응해야 하는 신호다.
            return {"_http": e.code, "error": detail}
        except Exception as e:  # noqa: BLE001
            return {"_http": 0, "error": str(e)[:300]}


# ── 취소 원장 ────────────────────────────────────────────────────────────────


class CancelRegistry:
    """서버가 알려준 **취소된 task** 를 워커에게 전달하는 통로.

    대기 스레드(`wait_for_request`)와 워커 스레드가 함께 읽고 쓰므로 락으로 감싼다.
    락 없이 `set` 을 공유해도 CPython 에서는 대개 동작하지만, "대개" 로 두면 취소가 가끔
    안 먹는 버그가 되고 그건 재현이 거의 불가능하다.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids: set[str] = set()

    def add_many(self, task_ids) -> list[str]:
        """새로 취소된 것만 골라 기록하고 그 목록을 돌려준다(로그용)."""
        fresh: list[str] = []
        with self._lock:
            for raw in task_ids or []:
                tid = str(raw or "")
                if tid and tid not in self._ids:
                    self._ids.add(tid)
                    fresh.append(tid)
        return fresh

    def is_canceled(self, task_id: str) -> bool:
        with self._lock:
            return str(task_id) in self._ids

    def forget(self, task_id: str) -> None:
        """처리를 마친 task 는 원장에서 뺀다 — 무한히 자라지 않게."""
        with self._lock:
            self._ids.discard(str(task_id))


# ── 내 AI 호출 ───────────────────────────────────────────────────────────────

#: 자동 감지 순서와 호출 방법. 전부 "프롬프트 → stdout" 계약이라 한 틀로 덮인다.
_CLI_ADAPTERS: list[tuple[str, list[str]]] = [
    ("claude", ["claude", "-p", "{prompt}"]),
    ("codex", ["codex", "exec", "--skip-git-repo-check", "{prompt}"]),
    ("gemini", ["gemini", "-p", "{prompt}"]),
]


#: 런타임별 **모델 지정 방법**. 웹에서 고른 모델을 여기로 옮긴다 — 전달만 받고 쓰지 않으면
#: 사용자 선택은 여전히 무효다. 지원하지 않는 런타임은 빈 목록(요청은 프롬프트로만 전달된다).
_MODEL_FLAG: dict[str, list[str]] = {
    "claude": ["--model"],
    "codex": ["--model"],
    "gemini": ["-m"],
}


def _which(name: str) -> str | None:
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def detect_ai() -> tuple[str, list[str]] | None:
    for name, argv in _CLI_ADAPTERS:
        if _which(name):
            return name, argv
    if _which("ollama"):
        return "ollama", []
    return None


#: `ask_local_ai` 가 "사용자가 취소했다" 를 알리는 신호.
#:
#: 실패 문자열로 섞지 않는 이유: 실패는 **답을 제출해서 알려야 하고**(침묵보다 낫다), 취소는
#: **제출하면 안 된다**(사용자가 안 보겠다고 한 것이다). 두 결과를 같은 값으로 돌려주면
#: 호출측이 그것을 구분하지 못해 둘 중 하나가 반드시 틀린 동작을 한다.
CANCELED = "__canceled__"


def _run_cli_cancelable(cmd: list[str], cancel_check) -> tuple[bool, str]:
    """CLI 를 돌리되 **취소되면 죽인다**. (성공여부, 본문 | CANCELED)

    왜 `subprocess.run` 이 아닌가: `run` 은 끝날 때까지 블로킹이라 그동안 도착한 취소를 볼 수
    없다. 그러면 사용자가 중단을 눌러도 개인 계정 토큰이 최대 15분(`_AI_TIMEOUT_SEC`) 더 탄다 —
    취소의 실질 목적이 바로 그 낭비를 막는 것이다.

    ⚠ 여기에도 sleep 은 없다. 자식이 끝나기를 `Thread.join(timeout)` 으로 **블로킹 대기**하고,
    그 반환 틈에 취소를 확인할 뿐이다. 서버를 두드리지 않으므로 폴링이 아니다.
    """
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:  # noqa: BLE001
        return False, f"AI 실행 실패: {e}"

    # 파이프를 비우는 일은 별도 스레드에 맡긴다. 여기서 직접 읽으면 자식이 큰 출력을 낼 때
    # 파이프 버퍼가 차서 서로 기다리는 교착이 된다(고전적인 Popen 함정).
    box: dict[str, str] = {}

    def _drain() -> None:
        out, err = proc.communicate()
        box["out"] = out or ""
        box["err"] = err or ""

    pump = threading.Thread(target=_drain, daemon=True)
    pump.start()

    waited = 0.0
    while pump.is_alive():
        pump.join(_CANCEL_TICK_SEC)
        waited += _CANCEL_TICK_SEC
        if cancel_check():
            _kill(proc)
            pump.join(5.0)
            return False, CANCELED
        if waited >= _AI_TIMEOUT_SEC:
            _kill(proc)
            pump.join(5.0)
            return False, f"AI 호출이 {int(_AI_TIMEOUT_SEC)}초를 넘겨 중단했습니다."

    if proc.returncode != 0:
        return False, f"AI 가 오류로 끝났습니다(exit {proc.returncode}): {box.get('err', '')[:400]}"
    return True, (box.get("out") or "").strip()


def _kill(proc) -> None:
    """자식을 확실히 끝낸다. 이미 죽었으면 조용히 지나간다."""
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


def ask_local_ai(kind: str, argv: list[str], prompt: str, custom: str | None,
                 want_model: str = "", cancel_check=None) -> tuple[bool, str]:
    """내 AI 에게 물어 답 문자열을 얻는다. (성공여부, 본문)

    `want_model` 은 사용자가 웹에서 고른 모델이다. 이 런타임이 모델 지정을 지원하면 인자로
    옮기고, 아니면 프롬프트의 요청 문구에만 남는다(그 경우 AI 가 답변에 못 맞춘 사실을 밝힌다).

    `cancel_check` 는 "지금 취소됐는가" 를 묻는 함수다. 취소되면 본문 자리에 `CANCELED` 를
    돌려준다 — 실패와 구분해야 호출측이 "제출하지 않는다" 를 선택할 수 있다.
    """
    _canceled = cancel_check or (lambda: False)
    if custom:
        argv = shlex.split(custom)
        kind = "custom"
    if kind == "ollama":
        # 웹에서 고른 모델이 로컬에 있을 수도 있다 — 있으면 그것을 쓴다.
        model = want_model or os.environ.get("BRIDGE_OLLAMA_MODEL", "llama3")
        # 이미 취소됐다면 호출 자체를 하지 않는다(HTTP 는 중간에 끊어도 서버 쪽 생성이 계속될
        # 수 있어, 시작하지 않는 것이 유일하게 확실한 절약이다).
        if _canceled():
            return False, CANCELED
        req = urllib.request.Request(
            os.environ.get("BRIDGE_OLLAMA_URL", "http://127.0.0.1:11434/api/generate"),
            data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_AI_TIMEOUT_SEC) as r:
                return True, str(json.loads(r.read().decode("utf-8", "replace")).get("response") or "")
        except Exception as e:  # noqa: BLE001
            return False, f"로컬 LLM 호출 실패: {e}"

    # 프롬프트는 **인자로** 넘긴다(셸을 거치지 않는다) — 질문 본문에 셸 메타문자가 섞여도
    # 그대로 전달되고, 명령 주입 경로가 생기지 않는다.
    cmd = [prompt if a == "{prompt}" else a.replace("{prompt}", prompt) for a in argv]
    flag = _MODEL_FLAG.get(kind) or []
    if want_model and flag:
        # 실행 파일 바로 뒤에 끼운다 — 프롬프트 뒤에 붙이면 위치 인자로 먹히는 CLI 가 있다.
        cmd = cmd[:1] + flag + [want_model] + cmd[1:]
    if _canceled():
        return False, CANCELED
    return _run_cli_cancelable(cmd, _canceled)


# ── 프롬프트 ─────────────────────────────────────────────────────────────────


def compose_prompt(api: Api, task: dict) -> str:
    """내 AI 에게 줄 프롬프트. **조사 도구 사용법을 함께 준다** — 그래야 DB 를 실제로 본다."""
    q = str(task.get("question") or "")
    ctxt = str(task.get("conversation_context") or "")
    want = str((task.get("requested") or {}).get("instruction") or "")
    sysp = str(task.get("system_prompt") or "")
    scope = task.get("scope") or {}
    atts = task.get("attachments") or []
    parts: list[str] = []
    if sysp:
        # 운영자가 설정한 5단계 지침(전역·제품·역할·계정·개인). **맨 앞**에 둔다 — 뒤에 두면
        # 앞의 지시가 이기고, 그러면 운영자 설정이 사실상 무시된다.
        parts += ["── 아래 지침을 시스템 프롬프트로 삼아 답하라 ──", sysp,
                  "── 지침 끝 ──", ""]
    if scope.get("product_name") or scope.get("datasources"):
        # 어떤 제품·어떤 DB 를 보고 있는지 모르면 엉뚱한 스키마를 찾아 헤맨다.
        who = scope.get("product_name") or ""
        key = scope.get("product_key") or ""
        ds = ", ".join(str(d) for d in (scope.get("datasources") or []))
        parts += [f"대상 제품: {who}" + (f" ({key})" if key else "")
                  + (f" · 데이터소스: {ds}" if ds else ""), ""]
    parts += [
        "너는 사내 DB 질의 어시스턴트다. 아래 사용자 질문에 답하라.",
        "",
        "필요하면 이 도구들을 HTTP 로 직접 호출해 실제 DB 를 조사하라"
        " (POST 로 JSON 본문, 헤더에 Authorization: Bearer <아래 토큰>):",
        f"  {api.base}/api/ai/tools/list_schemas        {{}}",
        f"  {api.base}/api/ai/tools/describe_schema     {{\"schema_name\":\"...\"}}",
        f"  {api.base}/api/ai/tools/describe_table      {{\"schema_name\":\"...\",\"table_name\":\"...\"}}",
        f"  {api.base}/api/ai/tools/search_tables       {{\"keyword\":\"...\"}}",
        f"  {api.base}/api/ai/tools/execute_sql         {{\"sql\":\"SELECT ...\"}}",
        f"  토큰: {api.token}",
        "",
        "추측하지 말고 조사한 사실만 쓰라. 확인하지 못한 것은 '미확인' 이라고 밝혀라.",
        "답변만 출력하라(머리말·맺음말 없이).",
    ]
    if ctxt:
        parts += ["", "── 이전 대화 ──", ctxt]
    if atts:
        names = ", ".join(f"{a.get('filename')}(id={a.get('attachment_id')})" for a in atts)
        parts += ["", f"첨부 {len(atts)}건: {names}",
                  f"  본문 읽기: POST {api.base}/api/ai/tools/read_task_attachment "
                  f"{{\"task_id\":\"{task.get('task_id')}\",\"attachment_id\":<id>}}",
                  "  첨부가 있는 질문은 반드시 본문을 읽고 답하라."]
    if want:
        parts += ["", "── 사용자 요청 품질 ──", want]
    parts += ["", "── 질문 ──", q]
    return "\n".join(parts)


# ── 한 건 처리 ───────────────────────────────────────────────────────────────


def handle_one(api: Api, task_id: str, claimed: dict, kind: str, argv: list[str],
               custom: str | None, cancels: "CancelRegistry | None" = None) -> bool:
    """이미 **점유된** task 하나를 처리한다.

    점유(`claim_request`)를 여기서 하지 않고 호출측(대기 루프)이 하는 이유: 점유가 늦으면 그
    task 가 `wait_for_request` 결과에 계속 남아, 워커가 다 찼을 때 같은 것을 반복해서 받게 된다
    (그리고 그 반복이 곧 서버를 두드리는 tight loop 다). 점유는 값싸고 즉시 끝나므로 대기
    루프에서 처리하고, 오래 걸리는 AI 호출만 워커로 넘긴다.
    """
    _canceled = (lambda: cancels.is_canceled(task_id)) if cancels else (lambda: False)

    prompt = compose_prompt(api, {**claimed, "task_id": task_id})
    req = claimed.get("requested") or {}
    want_model = str(req.get("model") or "")
    _log(f"{task_id}: 내 AI({kind})에게 전달"
         + (f" · 요청 모델 {want_model}" if want_model else "")
         + (f" · 추론 {req.get('reasoning_level')}" if req.get("reasoning_level") else ""))
    ok, answer = ask_local_ai(kind, argv, prompt, custom, want_model, _canceled)
    if answer == CANCELED:
        # 사용자가 취소했다. **제출하지 않는다** — 서버도 409 로 거절하지만, 여기서 멈추는 것이
        # 토큰과 왕복을 아끼는 지점이다.
        _log(f"{task_id}: 사용자가 취소했다 — 중단(제출 안 함)")
        return False
    if not ok and want_model and kind in _MODEL_FLAG:
        # 요청 모델이 이 런타임에 없을 수 있다. 그 하나 때문에 답을 아예 못 주는 것보다는
        # 기본 모델로 답하고 **그 사실을 밝히는** 편이 낫다.
        _log(f"{task_id}: 요청 모델로 실패 — 기본 모델로 재시도")
        ok, answer = ask_local_ai(kind, argv, prompt, custom, "", _canceled)
        if answer == CANCELED:
            _log(f"{task_id}: 사용자가 취소했다 — 중단(제출 안 함)")
            return False
        if ok:
            answer += (f"\n\n(요청하신 모델 `{want_model}` 을 이 환경에서 쓸 수 없어 "
                       f"기본 모델로 답했습니다.)")
    if not ok or not answer.strip():
        # 실패해도 **답을 제출한다** — 제출하지 않으면 사용자 화면은 30분간 대기 말풍선인 채로
        # 남고, 무엇이 잘못됐는지 아무도 모른다. 실패를 말하는 것이 침묵보다 낫다.
        answer = (answer or "내 AI 가 빈 응답을 돌려주었습니다.") + \
            "\n\n(이 답변은 연결된 AI 에서 생성하지 못해 자동 안내로 대체된 것입니다.)"

    # 답을 만드는 동안 취소됐을 수 있다 — 제출 **직전**에 한 번 더 본다.
    if _canceled():
        _log(f"{task_id}: 답변 완료 직전에 취소됨 — 제출하지 않는다")
        return False

    res = api.call("submit_answer",
                   {"task_id": task_id, "answer": answer, "source_tasks": [task_id]},
                   timeout=120.0)
    if res.get("_http") == 409:
        # 취소 신호를 못 본 채 여기까지 왔다(서버가 마지막 관문). 정상 흐름이다.
        _log(f"{task_id}: 서버가 제출을 거절했다(취소된 요청) — 버린다")
        return False
    if res.get("_http"):
        _log(f"{task_id}: 제출 실패 {res.get('_http')} {res.get('error')}")
        return False
    _log(f"{task_id}: 제출 완료 (대화 반영={res.get('delivered_to_conversation')})")
    return True


# ── 메인 ─────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description="mysql-ai 브리지 상주 러너")
    ap.add_argument("--base", default=os.environ.get("BRIDGE_BASE", ""), help="서비스 베이스 URL")
    ap.add_argument("--token", default=os.environ.get("BRIDGE_TOKEN", ""), help="mat_ 토큰")
    ap.add_argument("--ca", default=os.environ.get("BRIDGE_CA", "") or None, help="사설 CA 인증서 경로")
    ap.add_argument("--ai", default=os.environ.get("BRIDGE_AI", ""), help="claude|codex|gemini|ollama")
    ap.add_argument("--cmd", default=os.environ.get("BRIDGE_CMD", "") or None,
                    help="직접 지정할 AI 명령. {prompt} 자리에 질문이 들어간다")
    ap.add_argument("--once", action="store_true", help="한 건만 처리하고 종료")
    ap.add_argument("--check", action="store_true", help="연결만 확인하고 종료")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("BRIDGE_WORKERS", 0))
                    or _DEFAULT_WORKERS,
                    help=f"동시 처리 수 (기본 {_DEFAULT_WORKERS}, 1 = 직렬)")
    args = ap.parse_args()
    workers = max(1, int(args.workers or 1))

    if not args.base or not args.token:
        _log("FATAL: --base 와 --token 이 필요합니다.")
        return 2
    if not args.base.startswith("https://") and not args.base.startswith("http://127.0.0.1"):
        # 토큰이 이 채널로 나간다. loopback 만 예외.
        _log("FATAL: --base 는 https 여야 합니다(loopback 예외).")
        return 2

    api = Api(args.base, args.token, args.ca)

    if args.cmd:
        kind, argv = "custom", []
    else:
        picked = (args.ai, dict(_CLI_ADAPTERS).get(args.ai, [])) if args.ai else None
        if picked and args.ai == "ollama":
            picked = ("ollama", [])
        if not picked or (args.ai and args.ai not in dict(_CLI_ADAPTERS) and args.ai != "ollama"):
            picked = detect_ai()
        if not picked:
            _log("FATAL: 쓸 수 있는 AI 를 찾지 못했습니다. --ai 또는 --cmd 로 지정하세요.")
            return 2
        kind, argv = picked
    _log(f"AI = {kind}" + (f" ({args.cmd})" if args.cmd else ""))

    probe = api.call("wait_for_request", {}, timeout=10.0)
    if probe.get("_http") == 401:
        _log("FATAL: 토큰이 무효합니다(발급자가 로그아웃했거나 만료). 재발급이 필요합니다.")
        return 3
    if args.check:
        _log("연결 정상." if not probe.get("_http") else f"연결 실패: {probe.get('error')}")
        return 0 if not probe.get("_http") else 1

    cancels = CancelRegistry()
    #: 빈 워커 자리. **`wait_for_request` 를 부르기 전에** 하나를 잡는다 — 자리가 없는데
    #: 대기만 하면, 열린 질문이 남아 있는 한 서버가 즉시 응답해 tight loop 가 된다.
    #: 세마포어는 블로킹이라 여기서도 sleep 이 필요 없다.
    slots = threading.Semaphore(workers)
    #: 점유가 반복 실패한 task — 같은 것을 무한히 다시 시도해 서버를 두드리지 않도록 건너뛴다.
    skip: set[str] = set()
    #: 서버에 대기 질문이 있는데 한 건도 처리하지 못한 연속 라운드 수(spin 감지).
    stalled = 0
    done_once = threading.Event()

    _log(f"대기 시작 — 웹에서 질문이 오면 즉시 처리합니다. (동시 {workers}건, Ctrl+C 로 종료)")
    while True:
        slots.acquire()
        # ⚠ 여기에 sleep 이 없다. 대기는 서버가 한다 — 그것이 '폴링 아님' 의 실체다.
        res = api.call("wait_for_request", {}, timeout=_WAIT_TIMEOUT_SEC)
        code = res.get("_http")
        if code == 401:
            _log("토큰이 무효해졌습니다(로그아웃/만료). 재발급 후 다시 실행하세요.")
            return 3
        if code:
            _log(f"대기 실패 {code}: {res.get('error')} — 다시 대기합니다.")
            slots.release()
            continue

        # 취소는 **새 질문과 같은 응답**으로 온다(별도 채널이 아니다 — P0-J 의 즉시 인지가
        # 취소에도 그대로 적용된다). 진행 중인 워커가 다음 확인 시점에 이것을 보고 하차한다.
        fresh = cancels.add_many(res.get("canceled_task_ids") or [])
        if fresh:
            _log(f"취소 통보: {', '.join(fresh)} — 진행 중이면 중단합니다.")

        # skip 은 영구 블랙리스트가 아니다 — **대기가 실제로 비어서 타임아웃했을 때만** 비운다.
        #
        # 왜 비워야 하나: 다른 러너가 집어 간 작업을 skip 에 넣었는데 그쪽이 죽어 lease 가
        # 만료되면 그 작업은 대기열로 돌아온다. 그때도 계속 건너뛰면 **러너가 돌고 있는데도
        # 사용자는 답을 못 받는다.**
        #
        # 왜 하필 타임아웃 시점인가: "남은 것이 전부 skip" 일 때 비우면, 실패가 반복될 경우
        # 비움 → 재시도 → 실패 → 다시 전부 skip → 비움 … 이 간격 없이 돌아 tight loop 가 된다.
        # 타임아웃은 서버가 55초를 붙들었다는 뜻이라 그 자체가 자연스러운 재시도 간격이다.
        if res.get("timed_out"):
            skip.clear()
            stalled = 0

        pending = [str(t) for t in (res.get("task_ids") or []) if str(t) not in skip]
        if not pending:
            # 서버는 대기 질문이 **있다**고 했는데(즉시 반환) 우리가 전부 건너뛰는 중이다.
            # 이 상태로 `continue` 하면 `wait_for_request` 가 또 즉시 돌아와 **간격 없이 서버를
            # 두드린다** — 우리가 없애려던 바로 그 폴링이, 그것도 최악의 형태로 생긴다.
            #
            # 정상 상황에서는 오래가지 않는다(남이 집은 작업은 점유 즉시 목록에서 빠진다).
            # 오래간다는 것은 claim 이 계속 실패한다는 뜻이고, 그건 러너가 제 일을 못 하고 있다는
            # 뜻이다 — 조용히 도는 것보다 **크게 실패하는 편이 낫다**(사용자가 원인을 알 수 있다).
            if not res.get("timed_out"):
                stalled += 1
                if stalled >= _MAX_STALLED_ROUNDS:
                    _log(f"FATAL: 대기 질문이 {len(res.get('task_ids') or [])}건 있는데 "
                         f"{stalled}회 연속 하나도 처리하지 못했습니다(점유 실패 반복). "
                         "서버 상태와 토큰 권한을 확인하세요.")
                    return 4
            slots.release()
            continue
        stalled = 0

        # 점유는 **여기서** 한다(값싸고 즉시 끝난다). 점유하는 순간 그 task 는 다음
        # `wait_for_request` 결과에서 빠지므로, 워커가 다 찼을 때 같은 것을 다시 받지 않는다.
        task_id = pending[0]
        claimed = api.call("claim_request", {"task_id": task_id})
        if claimed.get("_http") == 409:
            _log(f"{task_id}: 이미 다른 세션이 가져갔다 — 건너뜀")
            skip.add(task_id)
            slots.release()
            continue
        if claimed.get("_http"):
            _log(f"{task_id}: 점유 실패 {claimed.get('_http')} {claimed.get('error')}")
            skip.add(task_id)
            slots.release()
            continue

        def _work(tid: str = task_id, payload: dict = claimed) -> None:
            try:
                handle_one(api, tid, payload, kind, argv, args.cmd, cancels)
            finally:
                cancels.forget(tid)
                slots.release()
                done_once.set()

        threading.Thread(target=_work, daemon=True).start()
        if args.once:
            # 그 한 건이 **끝날 때까지** 기다린다. 바로 반환하면 daemon 스레드가 죽어
            # 답이 제출되지 않는다(`--once` 가 아무것도 안 하는 것과 같아진다).
            done_once.wait()
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _log("종료합니다.")
        sys.exit(0)
