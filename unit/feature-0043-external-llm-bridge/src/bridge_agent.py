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
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

_UA = "mysql-ai-bridge-agent/1"

#: 답변 끝에서 대화 제목을 실어 오는 한 줄 규약. CLI 런타임은 stdout 하나뿐이라 별도 채널이
#: 없다 — 제출 전에 이 줄을 떼어내므로 사용자 화면에는 남지 않는다.
_TITLE_MARK = "#TITLE:"

#: 서버가 최대 55초 보류한다. 그보다 넉넉히 잡아야 **정상 대기**를 타임아웃으로 오인하지 않는다.
_WAIT_TIMEOUT_SEC = 90.0
#: 조사·응답 생성은 오래 걸릴 수 있다(도구 여러 번 호출). 점유 lease 30분보다 짧게 잡는다.
_AI_TIMEOUT_SEC = 900.0


#: 재시작 대비 설정 파일. **토큰은 넣지 않는다** — 비밀이고, 어차피 세션과 함께 죽는다.
#: 저장하는 것은 다시 물어보기 번거로운 것들(주소·CA 경로·AI 선택)뿐이다.
_CONF_DIR = os.path.join(os.path.expanduser("~"), ".mysql-ai-bridge")
_CONF_PATH = os.path.join(_CONF_DIR, "config.json")


def save_conf(base: str, ca: str | None, ai: str, cmd: str | None) -> None:
    """다음 실행이 `--resume` 한 줄로 끝나게 한다.

    머신을 재시작하면 이 프로세스는 사라진다(사용자 지적 2026-08-27). 그때 사용자가 다시
    챙겨야 하는 것이 많을수록 **아무도 다시 띄우지 않는다.** 토큰만 새로 받으면 되게 한다.
    """
    try:
        os.makedirs(_CONF_DIR, exist_ok=True)
        with open(_CONF_PATH, "w", encoding="utf-8") as f:
            json.dump({"base": base, "ca": ca, "ai": ai, "cmd": cmd}, f, ensure_ascii=False)
        os.chmod(_CONF_PATH, 0o600)
    except Exception as e:  # noqa: BLE001
        _log(f"설정 저장 실패(무시): {e}")


def load_conf() -> dict:
    try:
        with open(_CONF_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


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


def ask_local_ai(kind: str, argv: list[str], prompt: str, custom: str | None,
                 want_model: str = "") -> tuple[bool, str]:
    """내 AI 에게 물어 답 문자열을 얻는다. (성공여부, 본문)

    `want_model` 은 사용자가 웹에서 고른 모델이다. 이 런타임이 모델 지정을 지원하면 인자로
    옮기고, 아니면 프롬프트의 요청 문구에만 남는다(그 경우 AI 가 답변에 못 맞춘 사실을 밝힌다).
    """
    if custom:
        argv = shlex.split(custom)
        kind = "custom"
    if kind == "ollama":
        # 웹에서 고른 모델이 로컬에 있을 수도 있다 — 있으면 그것을 쓴다.
        model = want_model or os.environ.get("BRIDGE_OLLAMA_MODEL", "llama3")
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
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=_AI_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return False, f"AI 호출이 {int(_AI_TIMEOUT_SEC)}초를 넘겨 중단했습니다."
    except Exception as e:  # noqa: BLE001
        return False, f"AI 실행 실패: {e}"
    if out.returncode != 0:
        return False, f"AI 가 오류로 끝났습니다(exit {out.returncode}): {(out.stderr or '')[:400]}"
    return True, (out.stdout or "").strip()


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
        # ⚠ 본문 형태를 **정확히** 준다. 종전 예시는 `task_id` 가 없고 인자를 `arguments` 로
        #   감싸지 않아, 그대로 따르면 400("task_id 가 필요합니다") 또는 "schema_name과
        #   table_name은 필수" 만 돌아왔다 — 러너 경로의 조사가 통째로 실패하는 형태였다
        #   (codex REV-20260828T040000 P1).
        "필요하면 이 도구들을 HTTP 로 직접 호출해 실제 DB 를 조사하라"
        " (POST · JSON 본문 · 헤더에 Authorization: Bearer <아래 토큰>).",
        f"  공통 본문 = {{\"task_id\":\"{task.get('task_id')}\","
        " \"reason\":\"지금 이걸 왜 조사하는지 한 문장\", \"arguments\":{...}}",
        f"  {api.base}/api/ai/tools/list_schemas      arguments: {{}}",
        f"  {api.base}/api/ai/tools/describe_schema   arguments: {{\"schema_name\":\"...\"}}",
        f"  {api.base}/api/ai/tools/describe_table    arguments:"
        " {\"schema_name\":\"...\",\"table_name\":\"...\"}",
        f"  {api.base}/api/ai/tools/search_tables     arguments: {{\"keyword\":\"...\"}}",
        f"  {api.base}/api/ai/tools/get_table_indexes arguments:"
        " {\"schema_name\":\"...\",\"table_name\":\"...\"}",
        f"  {api.base}/api/ai/tools/get_foreign_keys  arguments:"
        " {\"schema_name\":\"...\",\"table_name\":\"...\"}",
        f"  {api.base}/api/ai/tools/execute_sql       arguments: {{\"sql\":\"SELECT ...\"}}",
        f"  토큰: {api.token}",
        "",
        # 조사 내역은 사용자 화면의 「실행 단계」에 그대로 그려진다. 사유가 없으면 서버가
        # 도구의 일반적 목적으로 채우는데, 그건 *이 질문에서의* 이유가 아니다.
        "`reason` 은 매 호출에 넣어라 — 사용자 화면의 실행 단계에 「어떤 이유로 → 어떤 작업」"
        " 으로 표시된다.",
        "",
        "추측하지 말고 조사한 사실만 쓰라. 확인하지 못한 것은 '미확인' 이라고 밝혀라.",
        "답변만 출력하라(머리말·맺음말 없이).",
        # 제목 축: 러너는 CLI 의 stdout 만 받으므로 별도 채널이 없다. 마지막 한 줄을 규약으로
        # 삼고 제출 전에 떼어낸다 — 마커가 없으면 답변은 그대로다(파싱 실패가 답을 망치지 않음).
        f"답변의 **맨 마지막 줄**에 `{_TITLE_MARK} <이 대화를 요약한 30자 안팎의 제목>` 을"
        " 한 줄 덧붙여라. 이 줄은 사용자에게 보이지 않고 대화 제목으로만 쓰인다.",
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


def split_title(answer: str) -> tuple[str, str]:
    """답변에서 `#TITLE:` 마지막 줄을 떼어 `(본문, 제목)` 으로 가른다.

    마커가 없으면 본문은 **손대지 않는다** — 규약을 지키지 않는 런타임이 있어도 답변이
    상하지 않아야 한다(제목이 없을 뿐이다). 마지막 줄만 본다: 중간에 같은 문자열이 있으면
    그건 답변 내용이지 제목이 아니다.
    """
    body = str(answer or "")
    lines = body.rstrip().split("\n")
    if not lines:
        return body, ""
    tail = lines[-1].strip()
    # `#` 를 요구한다 — `lstrip("#")` 로 느슨하게 받으면 답변의 정상적인 마지막 줄
    # `Title: 실제 데이터 열` 까지 제목으로 오인해 **본문에서 지운다**(codex P2).
    if not tail.upper().startswith(_TITLE_MARK.upper()):
        return body, ""
    rest = "\n".join(lines[:-1]).rstrip()
    if not rest:
        # 제목 줄이 전부라면 떼어낼 수 없다 — 떼면 빈 답변이 되어 제출이 400 으로 거절되고
        # 사용자 화면에는 대기 말풍선만 남는다. 제목을 포기하고 본문을 지킨다.
        return body, ""
    title = tail[len(_TITLE_MARK):].strip().strip("\"'`").strip()
    return rest, title[:120]


# ── 한 건 처리 ───────────────────────────────────────────────────────────────


def handle_one(api: Api, task_id: str, kind: str, argv: list[str], custom: str | None) -> bool:
    claimed = api.call("claim_request", {"task_id": task_id})
    if claimed.get("_http") == 409:
        _log(f"{task_id}: 이미 다른 세션이 가져갔다 — 건너뜀")
        return False
    if claimed.get("_http"):
        _log(f"{task_id}: 점유 실패 {claimed.get('_http')} {claimed.get('error')}")
        return False

    prompt = compose_prompt(api, {**claimed, "task_id": task_id})
    req = claimed.get("requested") or {}
    want_model = str(req.get("model") or "")
    _log(f"{task_id}: 내 AI({kind})에게 전달"
         + (f" · 요청 모델 {want_model}" if want_model else "")
         + (f" · 추론 {req.get('reasoning_level')}" if req.get("reasoning_level") else ""))
    ok, answer = ask_local_ai(kind, argv, prompt, custom, want_model)
    if not ok and want_model and kind in _MODEL_FLAG:
        # 요청 모델이 이 런타임에 없을 수 있다. 그 하나 때문에 답을 아예 못 주는 것보다는
        # 기본 모델로 답하고 **그 사실을 밝히는** 편이 낫다.
        _log(f"{task_id}: 요청 모델로 실패 — 기본 모델로 재시도")
        ok, answer = ask_local_ai(kind, argv, prompt, custom, "")
        if ok:
            answer += (f"\n\n(요청하신 모델 `{want_model}` 을 이 환경에서 쓸 수 없어 "
                       f"기본 모델로 답했습니다.)")
    if not ok or not answer.strip():
        # 실패해도 **답을 제출한다** — 제출하지 않으면 사용자 화면은 30분간 대기 말풍선인 채로
        # 남고, 무엇이 잘못됐는지 아무도 모른다. 실패를 말하는 것이 침묵보다 낫다.
        answer = (answer or "내 AI 가 빈 응답을 돌려주었습니다.") + \
            "\n\n(이 답변은 연결된 AI 에서 생성하지 못해 자동 안내로 대체된 것입니다.)"

    # 제목 줄은 답변에서 떼어 별도 필드로 보낸다 — 본문에 남기면 사용자가 규약 문자열을 본다.
    answer, title = split_title(answer)
    payload = {"task_id": task_id, "answer": answer, "source_tasks": [task_id]}
    if title:
        payload["title"] = title
    res = api.call("submit_answer", payload, timeout=120.0)
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
    ap.add_argument("--resume", action="store_true",
                    help="지난 설정을 불러온다(주소·CA·AI). 토큰만 새로 주면 된다")
    args = ap.parse_args()

    # 재시작 후 복귀 경로 — 명시 인자가 우선이고, 빈 것만 지난 설정으로 채운다.
    if args.resume:
        conf = load_conf()
        args.base = args.base or conf.get("base") or ""
        args.ca = args.ca or conf.get("ca")
        args.ai = args.ai or conf.get("ai") or ""
        args.cmd = args.cmd or conf.get("cmd")
        if not args.token:
            _log("토큰이 필요합니다 — 웹에서 '연결 정보 만들기' 로 새로 받아 --token 에 주세요.")
            return 2

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
    save_conf(args.base, args.ca, kind, args.cmd)

    probe = api.call("wait_for_request", {}, timeout=10.0)
    if probe.get("_http") == 401:
        _log("FATAL: 토큰이 무효합니다(발급자가 로그아웃했거나 만료). 재발급이 필요합니다.")
        return 3
    if args.check:
        _log("연결 정상." if not probe.get("_http") else f"연결 실패: {probe.get('error')}")
        return 0 if not probe.get("_http") else 1

    _log("대기 시작 — 웹에서 질문이 오면 즉시 처리합니다. (Ctrl+C 로 종료)")
    while True:
        # ⚠ 여기에 sleep 이 없다. 대기는 서버가 한다 — 그것이 '폴링 아님' 의 실체다.
        res = api.call("wait_for_request", {}, timeout=_WAIT_TIMEOUT_SEC)
        code = res.get("_http")
        if code == 401:
            # 여기서 조용히 죽으면 사용자는 "왜 답이 안 오지" 만 남는다. 다시 띄우는 **정확한
            # 명령**을 준다 — 설정은 이미 저장돼 있으므로 토큰만 새로 받으면 된다.
            _log("토큰이 무효해졌습니다(로그아웃 또는 만료).")
            _log("  1) 웹 대화 화면에서 'AI 연결하기' → [연결 정보 만들기] → 토큰 복사")
            _log(f"  2) python3 {os.path.basename(__file__)} --resume --token <새 토큰>")
            return 3
        if code:
            _log(f"대기 실패 {code}: {res.get('error')} — 다시 대기합니다.")
            continue
        for task_id in (res.get("task_ids") or []):
            handle_one(api, str(task_id), kind, argv, args.cmd)
            if args.once:
                return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _log("종료합니다.")
        sys.exit(0)
