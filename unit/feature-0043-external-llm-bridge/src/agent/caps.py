"""능력 협상 — AI 에게 자기 능력을 직접 묻는다.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import threading
import time

from .discovery import _resolve_exe, _which_ai
from .logs import _log
from .runtimes import _FORBIDDEN_FLAG_FRAGMENTS, _RUNTIME_SPECS

#: AI 가 답한 **값**(모델·등급)에 요구하는 모양. 서버 쪽 `_CAPS_VALUE_RE` 와 같은 집합이다.
#:
#: 내용은 보지 않는다 — 어떤 모델이 있는지는 그 AI 의 소관이고, 우리가 아는 목록으로 거르면
#: "관대하게 수용" 이 아니게 된다(P0-Z4). 여기서 보는 것은 **모양뿐**이다: 이 값은 곧
#: `Popen` 인자가 되므로, 옵션으로 해석될 수 있는 것(선행 `-`)과 셸 메타문자·공백을 막는다.
#: 실제 모델 이름은 이 집합 안에 다 들어온다(`gpt-5.1-codex` · `llama3:8b` · `gemini-2.5-pro`).
_CAPS_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,63}$")

#: 연결된 AI 에게 **자기 능력을 직접 묻는** 질문 (P0-Z4, 사용자 결정 2026-08-28).
#:
#: ## 왜 묻는가
#:
#: 종전에는 `_RUNTIME_SPECS` 에 우리가 적어 둔 목록을 신고했다. 그 목록은 우리가 아는 시점에
#: 멈춰 있어서 — CLI 가 새 모델을 얻어도, 사용자가 쓰는 런타임이 우리 표에 없어도 화면은
#: 모른다. **자기가 무엇을 쓸 수 있는지 가장 잘 아는 것은 그 AI 자신**이므로 직접 묻는다.
#:
#: ## 형식을 요구하되 관대하게 받는다
#:
#: 형식을 주지 않으면 파싱이 불가능하고, 형식을 엄격히 강제하면 조금만 어긋나도 그 런타임이
#: 통째로 사라진다. 그래서 **요구는 정확히, 수용은 관대하게** 한다 — 코드블록·머리말·설명이
#: 섞여도 `_extract_json` 이 본문에서 객체를 찾아낸다.
#:
#: ## 플래그도 함께 묻는 이유
#:
#: 플랫폼마다 모델·추론 지정 방법이 다르다(`--model` / `-m` / `-c key=value`). 우리가 표로
#: 갖고 있으면 새 플랫폼은 우리 배포를 기다려야 한다. AI 가 자기 호출법을 말하면 그 종속이
#: 사라진다 — 사용자가 어떤 CLI 를 쓰든 우리 코드는 그대로다.
_CAPS_PROBE_PROMPT = """\
너 자신에 대해 답하라. 지금 이 CLI 를 **비대화형으로 한 번 실행할 때**, 어떤 모델과 어떤
추론 수준(reasoning effort / thinking level)을 인자로 지정할 수 있는가?

아래 JSON 객체 **하나만** 출력하라. 설명·머리말·맺음말을 붙이지 마라.

{
  "label": "이 CLI 를 사람에게 보여줄 짧은 이름 (예: Claude, Codex, Gemini)",
  "models": [
    {"value": "인자에 그대로 넣을 실제 값", "label": "사람이 읽을 이름"}
  ],
  "efforts": [
    {"value": "인자에 그대로 넣을 실제 값", "label": "사람이 읽을 이름"}
  ],
  "model_flag": ["모델을 지정하는 인자 형태. {model} 자리에 위 value 가 들어간다"],
  "effort_flag": ["추론 수준을 지정하는 인자 형태. {effort} 자리에 위 value 가 들어간다"]
}

규칙:
- `value` 는 **네가 실제로 받아들이는 문자열**이어야 한다. 버전이 올라가도 유지되는 별칭
  (alias)이 있으면 그것을 우선하라 — 풀네임은 세대가 바뀌면 죽는다.
- 지정할 수 없는 항목은 **빈 배열**로 둬라. 없는 기능을 있다고 답하면, 사용자는 고를 수
  있는데 반영되지 않는 화면을 보게 된다.
- `model_flag` / `effort_flag` 는 인자를 **배열로** 쓴다.
  예: ["--model", "{model}"] · ["-m", "{model}"] · ["-c", "reasoning={effort}"]
- 모르는 것은 지어내지 마라. 확실한 것만 넣어라.
"""

#: 추론등급 축만 **다시** 묻는 좁은 질의 (2026-08-31).
#:
#: 위 `_CAPS_PROBE_PROMPT` 는 다섯 필드를 한 객체로 요구한다. 실측에서 claude 는 모델과
#: `model_flag` 는 답하고 `effort_flag` 를 빠뜨렸다 — 요구가 많으면 일부가 떨어진다.
#: 축 하나만 물으면 그 하나에 집중해 답한다. 1차에서 그 축을 못 받았을 때만 쓰므로 평상시
#: 추가 비용은 없다.
_CAPS_EFFORT_PROMPT = """\
너 자신에 대해 답하라. 지금 이 CLI 를 **비대화형으로 한 번 실행할 때**, 추론 수준
(reasoning effort / thinking level)을 인자로 지정할 수 있는가?

아래 JSON 객체 **하나만** 출력하라. 설명·머리말·맺음말을 붙이지 마라.

{
  "efforts": [
    {"value": "인자에 그대로 넣을 실제 값", "label": "사람이 읽을 이름"}
  ],
  "effort_flag": ["추론 수준을 지정하는 인자 형태. {effort} 자리에 위 value 가 들어간다"]
}

규칙:
- `effort_flag` 는 인자를 **배열로** 쓴다.
  예: ["--effort", "{effort}"] · ["-c", "model_reasoning_effort={effort}"]
- 지정할 수 **없다면** `"efforts": []` 와 `"effort_flag": []` 로 답하라. 그것도 답이다 —
  없는 기능을 있다고 답하면 사용자는 고를 수 있는데 반영되지 않는 화면을 보게 된다.
- 모르는 것은 지어내지 마라. 확실한 것만 넣어라.
"""

#: 능력 질의에 주는 시간. 짧게 잡는다 — 이건 답변이 아니라 **기동 절차**이고, 여기서 오래
#: 걸리면 사용자는 러너가 멈춘 줄 안다. 초과하면 내장 기본값으로 진행한다(기동을 막지 않는다).
#:
#: ⚠ `float(env or 120)` 로 쓰지 마라 — `os.environ.get(k, "0")` 은 **문자열 "0"**(truthy)을
#: 돌려주므로 `or` 가 단락되지 않고 timeout 이 0 이 된다. 그러면 질의가 시작하자마자
#: `TimeoutExpired` 로 죽고, 폴백이 조용히 삼켜 "AI 가 답을 안 했다" 로 보인다(실측으로 발견).
#: 변환을 **먼저** 하고 그 결과로 기본값을 고른다.
#: 실측(2026-08-28): claude 22.7초 · codex 112.3초. 후자가 120 에 아슬아슬해 여유를 둔다 —
#: 여기서 잘리면 그 런타임은 조용히 내장 기본값으로 떨어지고, 사용자는 자기 AI 가 답한 목록
#: 대신 우리가 적어 둔 (틀릴 수 있는) 목록을 보게 된다.
def _probe_timeout_from_env() -> float:
    """`BRIDGE_CAPS_PROBE_TIMEOUT` 을 **유한 양수**로만 받는다 (codex P2-6).

    검사 없이 `float()` 하면 `abc` 하나로 **모듈 import 가 실패**해 러너가 아예 뜨지 않고,
    `inf`/`nan` 은 `Thread.join()` 에서 `OverflowError`/`ValueError` 로 터진다. 음수는
    "기다리지 않고 백그라운드 probe 를 방치" 라는 최악의 조용한 동작이 된다.
    설정 하나가 기동을 못 하게 만드는 것은 어떤 경우에도 옳지 않다 — 이상하면 기본값으로 간다.
    """
    raw = os.environ.get("BRIDGE_CAPS_PROBE_TIMEOUT")
    if raw:
        try:
            got = float(raw)
        except (TypeError, ValueError):
            got = 0.0
        # `nan` 은 어떤 비교도 False 라 아래 범위 검사에서 자연히 걸러진다.
        if 5.0 <= got <= 1800.0:
            return got
        _log(f"BRIDGE_CAPS_PROBE_TIMEOUT={raw!r} 은 5~1800초 범위가 아닙니다 — 기본값을 씁니다.")
    return 240.0


_CAPS_PROBE_TIMEOUT_SEC = _probe_timeout_from_env()

#: 축 재질의를 시작하기 위한 최소 잔여 시간. 이보다 적게 남았으면 시작하지 않는다 —
#: 시작해 놓고 중간에 잘리면 토큰만 쓰고 답은 못 받는다.
_CAPS_AXIS_MIN_SEC = 20.0

#: `--help` 에 주는 시간. 도움말은 즉시 나온다 — 여기서 오래 걸리는 CLI 는 비정상이므로
#: 기다릴 이유가 없고, 못 읽으면 "모른다" 로 다룬다(축을 비우는 근거로 쓰지 않는다).
_CAPS_HELP_TIMEOUT_SEC = 15.0

#: probe stdout 상한 (codex P2-5). 오작동한 CLI 가 대량 출력을 쏟으면 그것이 전부 메모리에
#: 쌓이고, 이어지는 JSON 탐색이 그 위에서 반복 스캔한다. 정상 응답은 수 KB 다.
_CAPS_PROBE_MAX_BYTES = 256 * 1024
#: `_extract_json` 이 시도할 후보 `{` 개수 상한. 닫히지 않은 중괄호가 많으면 각 시작점마다
#: 본문 끝까지 훑어 O(n²) 가 된다.
_CAPS_JSON_MAX_CANDIDATES = 64


def _extract_json(text: str) -> dict | None:
    """본문에서 JSON 객체 하나를 **관대하게** 꺼낸다. 못 찾으면 None.

    AI 는 형식을 지키라고 해도 코드펜스를 붙이거나("```json ... ```"), 한 줄 설명을 앞에
    두거나, 뒤에 요약을 덧붙인다. 그 정도로 그 런타임을 통째로 버리면 "관대하게 수용" 이
    아니다 — 중괄호 균형을 세어 **첫 완전한 객체**를 찾는다.
    """
    s = str(text or "")[:_CAPS_PROBE_MAX_BYTES]
    start = s.find("{")
    tried = 0
    while start != -1 and tried < _CAPS_JSON_MAX_CANDIDATES:
        tried += 1
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        got = json.loads(s[start:i + 1])
                    except ValueError:
                        break          # 이 후보는 깨졌다 — 다음 `{` 부터 다시
                    return got if isinstance(got, dict) else None
        start = s.find("{", start + 1)
    return None


def _coerce_options(raw: object, limit: int = 40) -> list[dict]:
    """AI 가 준 목록을 `[{value,label}]` 로 **관대하게** 맞춘다.

    받아들이는 모양(전부 실제로 관측되는 형태다):

        ["opus", "sonnet"]                        → value=label=문자열
        [{"value": "opus", "label": "Opus"}]      → 그대로
        [{"value": "opus"}]                       → label 은 value 로 채움
        [{"name": "opus", "description": "..."}]  → 흔한 키 이름 대체 수용
        {"opus": "Opus", "sonnet": "Sonnet"}      → 매핑도 목록으로

    모양이 어긋난 항목은 **그것만** 버린다. 하나가 이상하다고 나머지를 지우지 않는다.
    """
    items: list = []
    if isinstance(raw, dict):
        items = [{"value": k, "label": v} for k, v in raw.items()]
    elif isinstance(raw, list):
        items = list(raw)
    out: list[dict] = []
    seen: set = set()
    for it in items[:limit]:
        if isinstance(it, str):
            value, label = it, it
        elif isinstance(it, dict):
            value = it.get("value") or it.get("id") or it.get("name") or it.get("model") or ""
            label = it.get("label") or it.get("name") or it.get("title") or value
        else:
            continue
        value = str(value or "").strip()
        label = str(label or value).strip()
        # 값의 모양만 본다 — 내용(어떤 모델인가)은 AI 의 소관이다.
        if not value or not _CAPS_VALUE_RE.match(value) or value in seen:
            continue
        seen.add(value)
        out.append({"value": value, "label": (label or value)[:60]})
    return out


def _coerce_flag(raw: object, placeholder: str) -> list[str] | None:
    """AI 가 준 플래그 형태를 argv 조각으로 맞춘다. 쓸 수 없으면 None.

    ⚠ **이 값은 서버로 나가지 않는다.** 로컬 `config.json` 에만 남고 러너가 직접 쓴다 —
    그래서 서버가 손상되거나 응답이 변조돼도 여기에 임의 플래그를 밀어 넣을 수 없다
    (P0-Z3 가 세운 신뢰 경계를 P0-Z4 도 그대로 지킨다).

    받아들이는 모양: `["--model", "{model}"]` · `"--model {model}"` · `"--model={model}"`.
    치환 자리(`{model}`/`{effort}`)가 없으면 쓸 수 없다 — 값을 넣을 곳이 없기 때문이다.
    """
    if isinstance(raw, str):
        try:
            parts = shlex.split(raw)
        except ValueError:
            return None            # 따옴표가 안 닫힌 문자열
    elif isinstance(raw, list):
        parts = [str(p) for p in raw]
    else:
        return None
    parts = [p for p in (str(p).strip() for p in parts) if p]
    if not parts:
        return None
    # 인자 하나하나가 공백·따옴표 없는 단일 토큰이어야 한다(셸을 거치지 않으므로 공백이
    # 들어가면 그대로 한 인자가 되어 CLI 가 거절한다).
    if any((" " in p or '"' in p or "'" in p) for p in parts):
        return None

    # ⚠ 여기가 이 기능의 가장 날카로운 자리다. 이 값은 **검사 없이 `Popen` 인자가 된다** —
    #   모델·등급 값과 달리 신고 목록과 대조할 대상이 없기 때문이다(형태 그 자체이므로).
    #   그래서 형태를 좁게 고정한다:
    #
    #     ① 치환 자리(`{model}`)를 **정확히 하나** 포함한다 — 값을 넣을 곳이 없으면 쓸 수 없고,
    #        여럿이면 같은 값이 여러 인자로 퍼진다.
    #     ② 토큰은 **최대 2개**. 실존하는 형태가 전부 그 안에 든다
    #        (`--model {model}` · `-m {model}` · `--model={model}` · `-c key={effort}`).
    #     ③ 치환 자리가 아닌 토큰은 **`-` 로 시작**해야 한다(옵션이어야 한다).
    #
    #   ③이 없으면 `["sh", "-c", "{model}"]` 같은 답이 그대로 통과해 **셸을 실행**하고,
    #   ②가 없으면 `["--model", "{model}", "--dangerously-skip-permissions"]` 로 임의 플래그가
    #   따라붙는다. 둘 다 실측으로 통과하던 형태였다.
    #
    #   이 방어의 신뢰 모델: 플래그는 로컬 AI 가 답한 것이고 서버를 거치지 않는다. 그래도
    #   막는 이유는 (a) 캐시 파일이 오염될 수 있고 (b) AI 가 프롬프트를 오해할 수 있으며
    #   (c) 무엇보다 **이 값만은 대조할 목록이 없기** 때문이다 — 심층 방어가 필요한 정확한 지점.
    if len(parts) > 2:
        return None
    holders = [p for p in parts if placeholder in p]
    if len(holders) != 1:
        return None
    if any(not p.startswith("-") for p in parts if placeholder not in p):
        return None
    # ④ **위험한 축의 플래그 이름은 거부한다** (codex REV-20260828T171500 P1-1).
    #    ①~③ 은 "셸 실행" 과 "임의 플래그 따라붙기" 를 막지만, 형태가 멀쩡한 **한 개의 나쁜
    #    플래그**는 통과시킨다 — `["--mcp-config", "{model}"]` 는 토큰 2개·치환자 1개·옵션
    #    시작이라 ①~③ 을 전부 만족하면서 방금 우리가 없앤 MCP 표면을 되살리고,
    #    `["--permission-mode", "{model}"]` + 모델값 `bypassPermissions` 는 권한 경계를 연다.
    #    모델·등급을 지정하는 정당한 플래그에는 아래 조각이 들어갈 일이 없다.
    #    ⚠ 치환자를 **포함한 토큰도 검사한다** — `-c mcp_servers={effort}` 처럼 값 자리에
    #      숨는 형태가 있기 때문이다(codex 의 `-c` config override 축).
    low = " ".join(parts).lower()
    if any(bad in low for bad in _FORBIDDEN_FLAG_FRAGMENTS):
        return None
    return parts


def sanitize_caps(raw: object) -> dict:
    """저장된 능력을 **다시 강제한다** (P0-Z4 심층 방어).

    질의 응답은 `probe_runtime_caps` 가 강제하지만, 그 결과는 `config.json` 을 거쳐 다음
    기동으로 돌아온다. 로드 시점에 강제하지 않으면 **파일이 곧 우회 경로**가 된다 —
    거기 적힌 플래그는 검사 없이 `Popen` 인자가 되기 때문이다.

    그 파일은 0600 이고 사용자 소유라 실질 위험은 낮다(쓸 수 있는 자는 러너 자체를 고칠 수도
    있다). 그래도 막는 이유: 이 검사는 사실상 공짜이고, "믿는 입력" 을 하나 줄이면 다음 사람이
    캐시 경로를 새 기능의 통로로 쓸 때 그 통로가 이미 좁혀져 있다.
    """
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    for name, caps in raw.items():
        if not isinstance(name, str) or not _CAPS_VALUE_RE.match(name) or not isinstance(caps, dict):
            continue
        models = _coerce_options(caps.get("models"))
        if not models:
            continue
        model_flag = _coerce_flag(caps.get("model"), "{model}") if caps.get("model") else None
        effort_flag = _coerce_flag(caps.get("effort"), "{effort}") if caps.get("effort") else None
        argv = caps.get("argv")
        if argv is not None:
            # 호출 형태도 같은 규칙 — 첫 토큰은 실행 파일 이름(= 이 런타임)이어야 하고,
            # 프롬프트 자리가 정확히 하나 있어야 한다. 그 외 형태는 버리고 표로 폴백한다.
            argv = [str(a) for a in argv] if isinstance(argv, list) else []
            if (not argv or argv[0] != name
                    or sum(1 for a in argv if "{prompt}" in a) != 1
                    or len(argv) > 5
                    or any((" " in a or '"' in a or "'" in a) for a in argv)):
                argv = None
        entry = {
            "label": " ".join(str(caps.get("label") or name).split())[:60] or name,
            "models": models,
            "efforts": _coerce_options(caps.get("efforts"), limit=12) if effort_flag else [],
            "model": model_flag,
            "effort": effort_flag,
            # 축 확정 표지는 **보존한다** — 여기서 떨어뜨리면 확정을 마친 캐시가 매 기동마다
            # 미확정으로 되살아나 같은 질의를 반복한다(그리고 그 질의는 사용자 토큰을 쓴다).
            # ⚠ `bool(...)` 이 아니라 `is True` 다 (codex P2-1): 손으로 고친 캐시의
            #   `"effort_probed": "false"` 같은 **문자열**이 truthy 로 읽혀 재확정을 영구히
            #   억제하는 것을 막는다. 표지는 우리가 쓴 참값일 때만 표지다.
            "effort_probed": caps.get("effort_probed") is True,
            # ⚠ **기본값을 주지 않는다** (backend 적대리뷰 PROV-R1, 2026-09-01).
            #   한때 `or "cache"` 였는데 `cache` 는 허용집합 안이라, **출처를 모르는 항목이
            #   허용된 라벨을 자동으로 얻었다** — 게이트가 기본값에서 fail-open 이었다.
            #   `cache` 를 실제로 쓰는 writer 는 없다(생성 시점 값은 `probe`/`builtin`).
            #   그러니 여기서 붙는 `cache` 는 「probe 결과가 파일로 살아남았다」는 뜻이어야
            #   하고, 그 사실은 **원래 source 가 있을 때만** 참이다. 없으면 빈 문자열로
            #   두어 허용집합 밖에 남긴다 — 그 런타임은 다음 기동에 다시 물어보게 된다.
            "source": ("cache" if str(caps.get("source") or "") == "probe"
                       else str(caps.get("source") or "")[:16]),
        }
        if argv:
            entry["argv"] = argv
        out[name] = entry
    return out


def _ask_json(argv: list[str], prompt: str, timeout: float) -> dict | None:
    """이 CLI 에 프롬프트 하나를 주고 답에서 JSON 객체를 꺼낸다. 못 얻으면 None.

    `probe_runtime_caps` 의 1차 질의와 축 재질의가 같은 절차를 쓴다 — 두 벌로 두면
    한쪽만 고쳐지고, 그때 어느 쪽이 실제로 쓰이는지가 코드에서 안 보인다.
    """
    cmd = _resolve_exe(
        [prompt if a == "{prompt}" else a.replace("{prompt}", prompt) for a in argv])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=(timeout if timeout and timeout > 0
                                       else _CAPS_PROBE_TIMEOUT_SEC))
    except Exception:  # noqa: BLE001  (미설치·타임아웃·권한 — 전부 "못 물었다" 로 같다)
        return None
    if proc.returncode != 0:
        return None
    # 출력이 아무리 커도 여기서 자른다 — `capture_output` 은 전부 메모리에 담는다.
    return _extract_json((proc.stdout or "")[:_CAPS_PROBE_MAX_BYTES])


def _cli_help_text(name: str, timeout: float = _CAPS_HELP_TIMEOUT_SEC) -> str | None:
    """`<cli> --help` 의 출력. 못 읽으면 None — **"없다" 가 아니라 "모른다"** 다.

    이 구분이 load-bearing 이다: 도움말을 못 읽었다고 축을 비우면, `--help` 가 느리거나
    다른 관례를 쓰는 CLI 에서 멀쩡한 기능이 사라진다. 아래 호출부는 `True` 일 때만 채택하고
    `None` 은 "확인 못 함" 으로 따로 다룬다.

    ⚠ **성공한 도움말만 읽는다** (codex P1-3). 종료코드를 무시하면 `unknown option
    '--effort'` 같은 **에러 문구**를 도움말로 읽어, 없는 플래그를 있다고 판정한다 — 오탐의
    방향이 정확히 최악이다(고른 값이 CLI 에서 거부되어 답이 아예 오지 않는다).
    그리고 stderr 은 보지 않는다: 도움말을 stderr 로 내는 CLI 도 있지만, 그 관용을 주면 위
    에러 경로가 같은 문으로 들어온다. 못 읽으면 "모른다" 로 남는 편이 안전하다.
    """
    try:
        proc = subprocess.run(_resolve_exe([name, "--help"]), capture_output=True, text=True,
                              timeout=(timeout if timeout and timeout > 0
                                       else _CAPS_HELP_TIMEOUT_SEC))
    except Exception:  # noqa: BLE001
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "")[:_CAPS_PROBE_MAX_BYTES] or None


def _help_mentions_flag(help_text: str | None, flag: list[str] | None) -> bool | None:
    """이 플래그를 그 CLI 가 실제로 받는가. 확인할 수 없으면 None.

    `--effort` 가 `--effort-level` 에 부분일치해 참이 되지 않도록 낱말 경계를 건다 — 그
    오탐은 "있다고 판단했는데 CLI 가 거부하는" 형태라, 사용자에게는 고른 값이 조용히
    무시되는 것으로 보인다(P0-T 가 지운 상태와 같다).

    ⚠ **이 검사가 확인하는 것은 첫 토큰뿐이다.** codex 의 `["-c",
    "model_reasoning_effort={effort}"]` 같은 config-override 형태에서는 `-c` 의 존재만
    확인되고 그 **키가 유효한지는 확인되지 않는다**. 그래도 이 경로를 쓰는 이유: 여기서
    쓰는 값은 우리 내장 표뿐이고 그것은 실측으로 채운 것이며, 틀렸을 때의 결과도 "그 CLI 가
    모르는 config 키를 무시한다" 로 그친다(플래그 자체가 없을 때처럼 명령 전체가 죽지 않는다).
    """
    if not flag or help_text is None:
        return None
    head = str(flag[0] or "").split("=", 1)[0].strip()
    if not head.startswith("-"):
        # 값을 위치 인자로 받는 형태(`["{model}"]`)는 도움말로 확인할 방법이 없다.
        return None
    return re.search(r"(?<![\w-])" + re.escape(head) + r"(?![\w-])", help_text) is not None


def _caps_axis_unsettled(caps: object) -> bool:
    """캐시된 능력의 추론등급 축이 **확정된 적 없는가**.

    `effort: null` 은 두 가지 다른 사실을 뭉갠다 — "물어봤는데 이 CLI 는 지원하지 않는다"
    와 "축을 다룬 적이 없다"(2026-08-31 이전 러너가 남긴 캐시). 그 둘을 구분하지 않으면
    이번 복구 경로가 **기존 사용자에게는 영영 실행되지 않는다**: 캐시가 있으니 묻지 않고,
    묻지 않으니 축이 계속 빈 채로 신고되고, 화면의 등급 항목은 계속 사라져 있다.

    그래서 확정을 거친 캐시에는 `effort_probed` 를 남기고, 그 표지가 없는 캐시만 한 번 더
    확정한다. 확정 결과가 "지원하지 않음" 이어도 표지는 남으므로 다음 기동은 묻지 않는다.
    """
    if not isinstance(caps, dict):
        return False
    return not caps.get("effort") and not caps.get("effort_probed")


#: 추론등급 플래그로 **위장할 수 없는** 조각. `_coerce_flag` 는 치환자와 토큰 형태만 보므로
#: `["--model", "{effort}"]` 같은 **축이 뒤바뀐** 플래그가 형태 검사를 그대로 통과한다
#: (codex P1-4). 그러면 `build_cmd` 가 `--model low` 를 붙여 모델 지정을 덮어쓴다 — 사용자는
#: 등급을 골랐는데 모델이 바뀐다. 축을 넘는 이름은 여기서 끊는다.
_EFFORT_FLAG_FORBIDDEN = ("model", "-m ", "agent", "prompt", "file", "output")


def _flag_fits_axis(flag: list[str] | None, axis: str) -> bool:
    """이 플래그가 **그 축의** 플래그인가 (codex P1-4).

    값 목록은 신고와 대조되지만 플래그는 대조할 목록이 없다 — 형태만 본다. 그 형태 검사는
    "옵션처럼 생겼는가" 까지라, 다른 축의 정당한 플래그를 그대로 통과시킨다. 축을 넘는
    이름을 거부하는 것이 여기서 할 수 있는 최소한이다.
    """
    if not flag:
        return False
    low = " ".join(flag).lower()
    if axis == "effort":
        return not any(bad in low for bad in _EFFORT_FLAG_FORBIDDEN)
    return True


def _settle_effort_axis(
    name: str, argv: list[str], flag: list[str] | None, options: list[dict], left: float
) -> tuple[list[str] | None, list[dict], bool]:
    """추론등급 축을 확정한다 — 1차 질의가 이 축을 못 채웠을 때의 복구 경로.

    반환은 `(플래그, 값목록, 확정했는가)`. 셋째 값이 `False` 면 **결론을 내지 못한 것**이라
    캐시에 확정 표지를 남기지 않는다 — 일시적 실패(도움말을 못 읽음)가 "이 CLI 는 등급을
    지원하지 않는다" 로 영구히 굳지 않게 하는 자리다.

    ## 무엇을 고치는가 (실측 2026-08-31)

    1차 질의는 모델·등급·두 플래그를 **한 JSON 으로** 요구한다. claude 는 모델과 모델
    플래그는 답하고 `effort_flag` 를 빠뜨렸다. 종전 코드는 `efforts ... if effort_flag
    else []` 라 등급 목록을 통째로 버렸고, 그 부분 결과가 내장 표를 이겨(폴백은 질의
    자체가 실패했을 때만) **실제로 지원되는 `--effort` 가 화면에서 사라졌다.**
    사용자에게는 "쓸 수 있는 effort 가 확인되지 않는" 상태로 보인다.

    ## 짝을 섞지 않는다

    유효한 것은 (플래그, 값 목록) **짝**이다. AI 가 준 플래그에 우리 표의 값을 붙이거나
    그 반대로 하면, 그 CLI 가 받지 않는 조합이 만들어지고 고른 값이 조용히 무시된다.
    그래서 아래 세 경로는 각각 **짝째로** 채택한다.

    ## 순서 — 묻는 것이 먼저다 (사용자 결정 2026-08-31)

    목록의 출처는 연결된 AI 다. 그래서 ① 축만 좁게 **다시 묻고**, 그래도 못 받으면
    ② 우리 표의 짝을 **그 CLI 자신의 `--help` 로 검증**해서 쓴다(우리가 아는 값이라도
    실재를 확인하고 쓴다). ③ 도움말에 없으면 축을 비운다 — 지어내지 않는다.
    """
    if flag and options and _flag_fits_axis(flag, "effort"):
        return flag, options, True      # AI 가 짝을 다 줬다 — 그대로.

    # ① 축만 좁게 재질의. 큰 JSON 하나를 요구할 때 빠뜨린 필드를, 그것만 물으면 답한다.
    if left >= _CAPS_AXIS_MIN_SEC:
        _log(f"{name}: 추론 수준을 다시 물어보는 중…")
        got = _ask_json(argv, _CAPS_EFFORT_PROMPT, min(left, _CAPS_PROBE_TIMEOUT_SEC))
        if got is not None:
            re_flag = _coerce_flag(got.get("effort_flag"), "{effort}")
            re_opts = _coerce_options(got.get("efforts"), limit=12)
            if re_flag and re_opts and _flag_fits_axis(re_flag, "effort"):
                return re_flag, re_opts, True
            # ⚠ **명시적 부정만** 존중한다 (codex P1-2). 종전에는 "flag 도 없고 목록도 없다"
            #   를 전부 "이 CLI 는 지원하지 않는다" 로 읽었는데, 그 조건은 `{}`·필드 누락·
            #   형태 오류(거부된 플래그)까지 같이 삼킨다. 그러면 실제로는 지원하는 CLI 가
            #   빈 축으로 **확정**되어(표지까지 남아) 다시는 확인되지 않는다.
            #   두 키가 **실제로 있고 둘 다 비어 있을 때**만 "없다" 는 답으로 친다.
            if (isinstance(got.get("efforts"), list) and not got["efforts"]
                    and isinstance(got.get("effort_flag"), list) and not got["effort_flag"]):
                return None, [], True

    # ② 우리 표의 짝을 그 CLI 의 도움말로 검증해서 쓴다. 남은 시간 안에서만 — 도움말 하나가
    #    전체 deadline 을 넘기면 뒤에서 기다리는 쪽이 이미 폴백으로 떠난 뒤다 (codex P1-1).
    spec = _RUNTIME_SPECS.get(name) or {}
    spec_flag = _coerce_flag(spec.get("effort"), "{effort}")
    spec_opts = _coerce_options(spec.get("efforts"), limit=12)
    if spec_flag and spec_opts and left > 0:
        # ⚠ `left <= 0` 이면 도움말도 부르지 않는다 (codex P1-3). 종전에는 남은 시간이 없어도
        #   15초를 새로 줬는데, 그러면 "전체 deadline" 이라는 말이 거짓이 된다 — 호출측은 이미
        #   폴백으로 떠난 뒤이고, 그 15초는 아무도 읽지 않을 답을 기다리는 시간이다.
        #   시간이 없으면 축을 비우되 **확정으로 기록하지 않아**(아래 False) 다음 기동이 다시 본다.
        help_budget = min(_CAPS_HELP_TIMEOUT_SEC, left)
        seen = _help_mentions_flag(_cli_help_text(name, timeout=help_budget), spec_flag)
        if seen is True:
            _log(f"{name}: 추론 수준을 답하지 않아 내장 표로 보완했다 (--help 로 실재 확인).")
            return spec_flag, spec_opts, True
        if seen is None:
            # 도움말을 **못 읽었다** — "없다" 가 아니다 (codex P2-2). 축은 비우되 확정으로
            # 기록하지 않아, 다음 기동이 다시 확인한다. 일시적 실패가 영구 미지원으로
            # 굳는 것이 이 축에서 가장 되돌리기 어려운 상태다.
            return None, [], False

    # ③ 넘길 방법을 확인하지 못했다 — 축을 비운다. 화면에서 그 항목이 빠지고,
    #    반영되지 않을 조작면은 생기지 않는다.
    #
    #    확정 여부는 **왜 여기 왔는지**로 갈린다. 우리 표에 짝이 아예 없으면(표 밖 CLI) 더
    #    확인할 것이 없으니 결론이다. 짝은 있는데 시간이 없어 도움말을 못 봤다면 그것은
    #    결론이 아니다 — 확정으로 기록하면 "시간이 없어 못 본 것" 이 "이 CLI 는 지원하지
    #    않는다" 로 굳는다(P2-2 와 같은 부류).
    _unchecked = bool(spec_flag and spec_opts and left <= 0)
    return None, [], not _unchecked


def probe_runtime_caps(name: str, argv: list[str],
                       timeout: float | None = None) -> dict | None:
    """그 AI 에게 **직접 물어** 능력을 받는다 (P0-Z4). 실패하면 None.

    실패를 조용히 삼키지 않고 None 으로 알리는 이유: 호출측이 내장 기본값으로 폴백할지
    (표에 있는 런타임) 아니면 신고에서 뺄지(모르는 런타임) 정해야 한다.

    **부분 성공은 실패가 아니다** (2026-08-31): 모델은 받고 등급은 못 받은 답이 실제로
    관측된다. 그때 축 하나가 비었다고 전체를 버리면 모델 목록까지 잃고, 반대로 비운 채
    두면 지원되는 기능이 화면에서 사라진다 — `_settle_effort_axis` 가 그 축만 복구한다.
    """
    budget = timeout if timeout and timeout > 0 else _CAPS_PROBE_TIMEOUT_SEC
    started = time.monotonic()
    got = _ask_json(argv, _CAPS_PROBE_PROMPT, budget)
    if not got:
        return None
    models = _coerce_options(got.get("models"))
    if not models:
        # 모델을 하나도 못 받았으면 이 질의는 실패다 — 등급만으로는 선택기를 세울 수 없다.
        return None
    model_flag = _coerce_flag(got.get("model_flag"), "{model}")
    effort_flag, efforts, effort_settled = _settle_effort_axis(
        name, argv,
        _coerce_flag(got.get("effort_flag"), "{effort}"),
        _coerce_options(got.get("efforts"), limit=12),
        budget - (time.monotonic() - started),
    )
    label = " ".join(str(got.get("label") or name).split())[:60] or name
    # 모델 축도 **넘길 방법이 있어야 목록이 뜻을 갖는다** (codex P1-2). 목록만 신고하고
    # 플래그가 없으면 화면에는 고를 수 있는 것처럼 나오지만 `build_cmd` 는 인자를 붙이지
    # 못해 CLI 기본 모델로 답한다 — "고를 수 있는데 반영은 안 되는" 조작면이 이 경로로
    # 되살아난다. 우리 표에 그 CLI 의 플래그가 있으면 그것으로 메우고(호출법 폴백은 유지
    # 하기로 한 축이다), 표에도 없으면(표 밖 CLI) **목록을 비운다** — 그러면 그 런타임은
    # 신고되지 않고, 사용자는 없는 선택지를 보지 않는다.
    if not model_flag:
        model_flag = _coerce_flag((_RUNTIME_SPECS.get(name) or {}).get("model"), "{model}")
    if not model_flag:
        models = []
    return {
        "label": label,
        "models": models,
        "efforts": efforts,
        # 플래그가 없으면 그 축은 지정 불가 — 목록도 비운다(위 `efforts` 와 같은 이유).
        "model": model_flag,
        "effort": effort_flag,
        # 축 확정 절차를 **결론까지** 거쳤다는 표지. 결과가 "지원하지 않음"(둘 다 빈 값)이어도
        # 결론이면 남긴다 — 이 표지가 없으면 다음 기동이 같은 축을 또 묻는다
        # (`_caps_axis_unsettled`). 반대로 결론을 못 냈으면(도움말을 못 읽음) 남기지 않아
        # 다음 기동이 다시 확인한다 (codex P2-2).
        "effort_probed": bool(effort_settled),
        "source": "probe",
    }


def detect_runtimes(only: str | None = None, cached: dict | None = None,
                    detail_out: dict | None = None,
                    probe: bool = False) -> list[dict]:
    """이 머신에서 **쓸 수 있는 런타임 전부**와 각자가 고를 수 있는 것 (P0-Z3).

    종전 `detect_ai()` 는 첫 번째 하나만 골랐다. 그것은 "무엇으로 답할까" 의 답으로는
    충분했지만, 웹에 "무엇을 고를 수 있는가" 를 알려주려면 **전부**가 필요하다.

    `only` 가 주어지면 그 하나로 제한한다(`--ai` 의 의미: 자동 감지 대신 이것만 쓴다).
    표에 없는 이름이면 제한을 무시한다 — 사용자의 오타가 러너를 벙어리로 만들지 않게.

    ## 목록은 **그 AI 가 정한다** (P0-Z4, 사용자 결정 2026-08-28)

    각 런타임에 한 번 물어(`probe_runtime_caps`) 답을 그대로 쓴다.

    ⚠ **실패하면 그 런타임은 신고에서 통째로 빠진다** (2026-08-31 개정 · 이 docstring 은
    2026-09-01 에야 본문을 따라잡았다 — backend·qa 적대리뷰 C3). 종전에는 내장 표
    (`_RUNTIME_SPECS`)로 폴백했는데, 그 표가 곧 `gpt-5.1-codex`(폐기 세대)를 사용자 화면에
    올린 경로였다. 물어보지 못한 것을 「이것을 쓸 수 있다」로 말하면 사용자는 없는 모델을
    고르고 CLI 가 거부한다. 내장 값을 계속 쓰는 것은 **호출법(argv·플래그)뿐**이다 — 그것은
    값이 아니라 형태라 틀린 선택지를 만들지 않고, 없으면 실행 자체가 불가능하다.

    이 동작을 집행하는 것은 신고 항목의 `source`(provenance)다 — 아래 `_REPORTABLE_SOURCES`
    가 라이브 답이 아닌 출처를 신고에서 떨어뜨리고, 서버 `_SANITIZE_SOURCE_ALLOW` 가 수신
    시점에 한 번 더 거른다. **폴백을 되살리려면 그 두 집합부터 보라** — 되살린 목록은
    `builtin` 출처를 달게 되고, 그러면 어느 쪽 게이트도 통과하지 못한다.

    `cached` 를 주면 묻지 않고 그것을 쓴다(매 기동마다 사용자 토큰을 태우지 않기 위해).
    캐시 항목도 **provenance 검사를 다시 통과해야** 신고된다 — `config.json` 은 사용자가 쓸
    수 있는 파일이고, 캐시 포맷이 바뀌는 날 그 경로로 폴백이 되돌아오는 것을 막는다.
    """
    names = list(_RUNTIME_SPECS.keys())
    if only and only in _RUNTIME_SPECS:
        names = [only]
    elif only:
        # 표에 없는 런타임도 사용자가 지목했으면 물어본다 — 우리가 모르는 CLI 여도
        # 자기 능력은 스스로 말할 수 있다(그것이 P0-Z4 의 요지다).
        names = [only] if _which_ai(only) else names

    # ⚠ **출처를 모르는 캐시 항목은 «캐시 없음» 으로 다룬다** (2026-09-01).
    #   provenance 게이트를 켠 뒤 그런 항목은 신고에서 떨어지는데, 캐시로 남겨 두면 아래
    #   `ask` 가 "이미 안다" 고 판단해 다시 묻지 않는다 — 그 런타임이 사용자 화면에서
    #   **조용히 사라진 채 영영 돌아오지 않는다**(`--refresh-caps` 를 알기 전까지).
    #   축 재확정 분기(`prev is not None`)도 prev 의 출처를 그대로 물려주므로 그쪽으로
    #   새지 않게 **여기서** 걸러야 한다. 모르면 감추는 것이 아니라 다시 묻는다.
    cached = {n: c for n, c in (cached or {}).items()
              if str((c or {}).get("source") or "") in _REPORTABLE_SOURCES}
    present = [n for n in names if _which_ai(n)]
    # 우리 표에 없는 CLI 도 물어본다 (P0-Z4 — "플랫폼에 관계없이"). 호출법을 모르므로 가장
    # 흔한 두 형태를 시도한다: `<cli> -p <프롬프트>` 와 `<cli> <프롬프트>`. 둘 다 실패하면
    # 그 런타임은 신고에서 빠진다(사용자는 `--cmd` 로 직접 줄 수 있다).
    unknown_argvs: dict = {}
    for n in present:
        if n not in _RUNTIME_SPECS:
            unknown_argvs[n] = [[n, "-p", "{prompt}"], [n, "{prompt}"]]

    # 물어야 할 것들을 **동시에** 묻는다. 순차로 하면 기동이 각 런타임의 응답 시간을 모두
    # 더한 만큼 늦어진다(실측: claude 23초 + codex 112초 = 135초). 병렬이면 가장 느린 하나
    # (112초)로 끝난다 — 그리고 이건 최초 1회뿐이다(다음 기동은 캐시를 쓴다).
    probed: dict = {}
    ask = [n for n in present
           if (cached.get(n) is None or _caps_axis_unsettled(cached.get(n)))
           and ((_RUNTIME_SPECS.get(n) or {}).get("argv") or n in unknown_argvs)] if probe else []
    if ask:
        _log(f"쓸 수 있는 모델·추론 수준을 물어보는 중… ({', '.join(ask)} — 최초 1회, 수십 초)")

        # 전체 질의에 **하나의 절대 deadline** 을 둔다 (codex P2-4). 후보를 순차로 시도하는
        # 표 밖 CLI 는 후보마다 timeout 을 다 쓸 수 있어(240초 × 2) main 의 대기(250초)를
        # 넘긴다. 그러면 main 은 폴백으로 기동하고, 뒤에 남은 스레드가 아무도 읽지 않을 답을
        # 위해 계속 토큰과 CPU 를 태운다. deadline 을 공유해 남은 시간이 없으면 멈춘다.
        deadline = time.monotonic() + _CAPS_PROBE_TIMEOUT_SEC

        def _probe(nm: str) -> None:
            prev = cached.get(nm)
            if prev is not None:
                # 캐시는 있는데 **추론등급 축만** 미확정이다(구 러너가 만든 캐시). 모델 목록은
                # 이미 그 AI 가 답한 것이므로 전체를 다시 묻지 않는다 — 축 하나만 확정하고
                # 그 사실을 캐시에 남겨 다음 기동은 묻지 않게 한다.
                left = deadline - time.monotonic()
                argv = list(prev.get("argv") or (_RUNTIME_SPECS.get(nm) or {}).get("argv") or [])
                if left <= 5.0 or not argv:
                    # 표지를 남기지 않고 물러난다 — 다음 기동이 다시 시도한다. 여기서
                    # 확정으로 기록하면 "시간이 없어 못 물어본 것" 이 "물어봤는데 없다" 가 된다.
                    return
                flag, opts, settled = _settle_effort_axis(nm, argv, None, [], left)
                probed[nm] = {**prev, "effort": flag, "efforts": opts,
                              "effort_probed": bool(settled)}
                return
            attempts = list(unknown_argvs.get(nm) or [list(_RUNTIME_SPECS[nm]["argv"])])
            # 표 안 CLI 는 후보 호출 형태가 하나뿐이라 **한 번 실패하면 곧 포기**였다.
            # 실측(2026-08-31): codex 는 같은 조건에서 성공(6종 응답)과 실패를 오간다. 그 한
            # 번의 실패가 이제는 "그 런타임이 화면에서 통째로 사라짐" 을 뜻한다(내장 모델
            # 목록 폴백을 없앴으므로). 남은 시간이 있으면 한 번 더 묻는다 — 시간 검사는
            # 루프 안에 이미 있어 deadline 을 넘기지 않는다.
            if len(attempts) == 1:
                attempts = attempts * 2
            for argv in attempts:
                left = deadline - time.monotonic()
                if left <= 5.0:
                    return           # 남은 시간이 의미 없다 — 시작하지 않는 것이 유일한 절약
                got = probe_runtime_caps(nm, argv, timeout=left)
                if got:
                    # 어느 호출 형태가 통했는지 함께 남긴다 — 실제 질문도 그 형태로 보낸다.
                    got["argv"] = argv
                    probed[nm] = got
                    return

        threads = [threading.Thread(target=_probe, args=(n,), daemon=True) for n in ask]
        for t in threads:
            t.start()
        for t in threads:
            # deadline 이 공유되므로 여기서 기다릴 시간도 그 하나로 정해진다.
            t.join(max(1.0, deadline - time.monotonic()) + 5.0)
        for n in ask:
            got = probed.get(n)
            if got:
                _log(f"  {n}: 모델 {len(got['models'])}종"
                     + (f" · 추론 {len(got['efforts'])}단계" if got["efforts"] else
                        " · 추론 수준 지정 불가")
                     + " (본인 응답)")
            elif cached.get(n) is not None:
                # 축 재확정만 시도했고 그것도 못 얻었다 — 캐시를 지우지 않는다.
                _log(f"  {n}: 추론 수준을 확인하지 못해 이전 값을 유지합니다.")
            else:
                # ⚠ 종전 문구(내장 표로 대신한다는 안내)는 이제 거짓이다 (2026-08-31).
                #   모델 목록 폴백을 없앴으므로
                #   답을 못 받으면 **그 런타임은 화면에 나타나지 않는다**. 로그가 종전 문구를
                #   유지하면 사용자는 목록이 있는 줄 알고 선택기를 찾는다 — 그리고 없는 이유를
                #   어디서도 듣지 못한다. 다음 행동(재시도 방법)까지 여기서 말한다.
                _log(f"  {n}: 답을 받지 못했습니다 — 이 런타임은 목록에 나오지 않습니다. "
                     f"({n} 로그인·네트워크 확인 후 `--refresh-caps` 로 다시 시도)")

    out: list[dict] = []
    for name in present:
        spec = _RUNTIME_SPECS.get(name) or {}
        # ⚠ 새로 물어본 것이 캐시를 **이긴다**. 반대로 두면 축 재확정(위 `_probe` 의 캐시
        #   분기)이 매번 돌면서도 결과가 버려져, 사용자는 같은 빈 목록을 계속 본다.
        caps = probed.get(name) or cached.get(name)

        if caps is None:
            # 폴백 — **호출법만** 우리가 아는 것을 쓴다. 모델 목록은 넣지 않는다.
            #
            # ⚠ 종전에는 내장 표의 모델 이름까지 신고했다. 그 표는 우리가 적어 둔 시점에
            #   멈춰 있어서, 라이브에서 codex 가 `gpt-5.1-codex` 로 보였다 — 실제 그 계정이
            #   쓸 수 있는 것은 `gpt-5.6-sol`·`terra`·`luna`·`5.5`·`5.4` 였다(사용자 제보
            #   2026-08-31). **없는 모델을 고를 수 있다고 말하는 것**이라, 고른 순간 CLI 가
            #   거부하거나 조용히 다른 모델로 답한다.
            #
            #   목록의 출처는 연결된 AI 라는 것이 이 기능의 계약이고(사용자 결정), 그 계약을
            #   폴백이 뒷문으로 깨고 있었다. 물어보지 못했으면 **모른다고 하는 편이** 틀린
            #   목록을 확신 있게 보여주는 것보다 낫다 — 아래 `if not caps.get("models")` 가
            #   그 런타임을 신고에서 빼고, 화면에는 그 그룹이 나타나지 않는다.
            #
            #   호출법(argv·플래그)은 성격이 다르다: 잘 변하지 않고, 없으면 **실행 자체가**
            #   불가능하며, 값이 아니라 형태라 "틀린 선택지를 제시" 하는 문제가 생기지 않는다.
            #
            models = []
            caps = {
                "label": str(spec.get("label") or name),
                "models": models,
                "efforts": [],
                "model": spec.get("model"),
                "effort": spec.get("effort"),
                # ⚠ **항상 `builtin`** 이다. 이 값을 다른 이름으로 바꾸면 바로 아래 캐시 쓰기
                #   가드(`!= "builtin"`)가 뒤집혀 폴백이 영구 캐시된다 — 한 번 그렇게 만들었고
                #   ollama 목록이 굳는 결함이 됐다(security 적대리뷰 B1, 2026-09-01).
                "source": "builtin",
            }

        # ── provenance 게이트 (qa 적대리뷰 §3, 2026-09-01) ────────────────────────
        #
        # 목록이 **어떻게 얻어졌는지**를 신고 직전에 본다 — 이것이 「화면 목록의 출처는
        # 연결된 AI」 계약의 유일한 집행 지점이다.
        #
        # ⚠ 한때 여기에 더해 전역 자격 신고(`caps_self_report`)를 두고 서버가 그것으로
        #   목록 전체를 감췄다. 철회했다(2026-09-01, 적대 패널 3인) — 전역 불리언은 「이
        #   빌드가 계약을 아는가」에 답할 뿐이라 다음 포맷 변경에 다섯 번째 이름이 필요하고,
        #   그 대가로 다중 러너 fail-closed 라는 **제품 안에서 풀 수 없는 잠금**을 만들었다.
        #   런타임 **단위** provenance 는 같은 클래스를 더 좁게, 우아하게 열화하며 닫는다.
        #
        # ⚠ 캐시 경로가 이 검사의 요점이다. `caps = probed.get(name) or cached.get(name)`
        #   에서 `cached` 는 사용자가 쓸 수 있는 `config.json` 이고, 종전에는 그 항목의
        #   `source` 를 아무도 다시 보지 않았다 — 오늘은 안전하지만(폴백 캐싱 금지 가드가
        #   같은 커밋에 있었다) 캐시 포맷이 바뀌는 날 다시 열린다. 커밋 고고학이 아니라
        #   코드가 그것을 붙들게 한다.
        _prov = str(caps.get("source") or "")
        if _prov not in _REPORTABLE_SOURCES:
            continue
        if not caps.get("models"):
            # 고를 것이 없는 런타임은 신고하지 않는다 — 화면에 빈 그룹만 남는다.
            continue
        # 호출법을 포함한 **상세**는 여기 남긴다(서버로 나가지 않는다 — 아래 신고와 구분).
        #
        # ⚠ 폴백(`builtin`)은 **캐시하지 않는다**(codex P2-3). 캐시하면 최초 기동의 일시적
        #   실패(인증 지연·타임아웃)가 영구화된다 — 다음 기동은 캐시가 있다고 묻지 않으므로,
        #   인증이 복구돼도 낡은 내장 목록을 계속 보여준다. 사용자는 `--refresh-caps` 를
        #   알기 전까지 그것이 틀렸다는 사실조차 모른다. 물어서 얻은 것만 남긴다.
        if detail_out is not None and caps.get("source") != "builtin":
            detail_out[name] = caps
        # ⚠ 항목을 **재구성한다**(얕은 복사 금지 — codex P2-1). `list(caps["models"])` 는
        #   내부 dict 를 그대로 참조하므로, 오염된 항목에 붙은 여분 키(`{"value":…,
        #   "model":["--secret"]}`)가 하트비트 HTTP 본문에 실려 나간다. 서버 sanitizer 가
        #   저장 전에 지우더라도 **전송은 이미 일어났고**, 그러면 "호출법은 서버로 나가지
        #   않는다" 는 이 기능의 계약이 거짓이 된다.
        def _pair(o: dict) -> dict:
            return {"value": str(o.get("value") or ""), "label": str(o.get("label") or "")}

        out.append({
            "runtime": name,
            "label": str(caps.get("label") or name),
            "models": [_pair(o) for o in caps["models"]],
            # 플래그가 없으면 등급도 신고하지 않는다: 지정 수단이 없는데 목록을 주면
            # 다시 "고를 수 있는데 반영은 안 되는" 상태가 된다(P0-T 가 지운 바로 그것).
            "efforts": [_pair(o) for o in (caps.get("efforts") or [])] if caps.get("effort") else [],
            # **이 목록이 어떻게 얻어졌는가.** 서버가 런타임 단위로 다시 거른다 — 전역
            # 불리언 하나보다 엄격하고, 나쁜 런타임 하나만 숨고 나머지는 남는다.
            # 호출법(플래그)과 달리 이것은 **값이 아니라 출처**라 서버로 나가도 무해하다.
            "source": _prov,
        })
    return out


#: 서버에 신고해도 되는 목록 **출처**. 「그 AI 가 라이브로 답한 것」(`probe`)과 그것을
#: `config.json` 에 남긴 것(`cache`)뿐이다. `builtin`(우리가 소스에 적어 둔 표)은 여기 없다 —
#: 그것이 `gpt-5.1-codex` 가 화면에 뜬 경로였다.
#:
#: ⚠ **여기에 `builtin` 을 추가하지 마라.** 추가하는 순간 「목록의 출처는 연결된 AI」 계약이
#: 그 자리에서 깨지고, 서버는 그것을 검증할 수단이 없다. 정본 대조: 서버
#: `_SANITIZE_SOURCE_ALLOW` — 구조 테스트가 두 집합의 동일성을 잠근다.
_REPORTABLE_SOURCES: frozenset[str] = frozenset({"probe", "cache"})


def resolve_caps(only: str | None, cached: dict | None,
                 refresh: bool) -> tuple[list[dict], dict]:
    """신고할 목록과 **로컬에 남길 능력 상세**를 함께 만든다 (P0-Z4).

    두 값을 가르는 것이 이 함수의 존재 이유다:

      - 반환 `[0]` = 서버로 나가는 신고. 사람이 고를 목록만 담는다.
      - 반환 `[1]` = `config.json` 에 남는 상세. **호출법(플래그)이 여기 있다.**

    호출법을 서버에 보내지 않으므로, 서버가 손상되거나 응답이 변조돼도 러너가 실행할 인자의
    *형태* 는 바뀌지 않는다 — 바뀔 수 있는 것은 그 형태에 채울 값뿐이고, 그 값은 신고 목록과
    대조된다(P0-Z3 의 두 번째 자물쇠).
    """
    detail: dict = {}
    reported = detect_runtimes(only, cached=(None if refresh else (cached or None)),
                               detail_out=detail, probe=True)
    return reported, detail
