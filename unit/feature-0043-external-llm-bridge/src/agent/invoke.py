"""내 AI 호출 — 취소 가능 실행·실패 서술.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import threading
import time

from .base import _AI_TIMEOUT_SEC, _CANCEL_TICK_SEC
from .discovery import _resolve_exe
from .events import _EV_AI_FAIL, _EV_AI_SPAWN_FAIL, _EV_AI_TIMEOUT
from .logs import _SECRET_PATTERNS, _log, _log_exc, log_event
from .runtimes import _APPEND_SYSTEM_FLAG, _KEEP_MCP, _RUNTIME_SPECS, _STRICT_MCP_FLAG

#: `ask_local_ai` 가 "사용자가 취소했다" 를 알리는 신호.
#:
#: 실패 문자열로 섞지 않는 이유: 실패는 **답을 제출해서 알려야 하고**(침묵보다 낫다), 취소는
#: **제출하면 안 된다**(사용자가 안 보겠다고 한 것이다). 두 결과를 같은 값으로 돌려주면
#: 호출측이 그것을 구분하지 못해 둘 중 하나가 반드시 틀린 동작을 한다.
CANCELED = "__canceled__"


#: 실패 사유로 실어 보낼 자식 출력의 최대 길이(문자).
_FAIL_DETAIL_MAX = 400

#: **stderr 에 있어도 실패 원인이 아닌** 줄 — 이것만 남으면 stderr 는 «비었다» 로 본다.
#:
#: 라이브에서 관측된 형태: claude CLI 는 파이프 stdin 을 3초 기다린 뒤 그 사실을 stderr 로
#: 알린다. 그 줄은 종료코드와 무관한 안내인데, 그것만 보고 "stderr 가 비지 않았다" 로 판단하면
#: 진짜 사유(stdout 에 있다)를 덮어쓴다.
_STDERR_NOISE = (
    re.compile(r"^\s*warning:\s*no stdin data received", re.I),
    re.compile(r"^\s*$"),
)

#: 자식 CLI 의 실패 출력 → **사용자가 다음에 할 행동**. 런타임 이름이 아니라 *증상 어휘* 로
#: 잡는다 — 어느 CLI 든 같은 부류의 실패는 같은 말을 쓰기 때문이고, 새 런타임이 붙어도 표를
#: 고칠 필요가 없다. 하나도 안 맞으면 안내 없이 원문만 전달한다(추측해 오도하지 않는다).
_FAILURE_HINTS: tuple[tuple[object, str], ...] = (
    (re.compile(r"usage limit|session limit|quota|rate.?limit|too many requests|"
                r"사용 한도|한도에 도달", re.I),
     "연결된 AI 의 사용 한도에 걸렸습니다. 위에 적힌 초기화 시각이 지난 뒤 같은 질문을 다시 "
     "보내면 처리됩니다(질문은 그대로 다시 보내면 됩니다)."),
    (re.compile(r"not logged in|not authenticated|please\s+(run\s+)?/?log\s?in|"
                r"unauthorized|invalid api key|\b401\b", re.I),
     "연결된 AI 에 로그인돼 있지 않습니다. 러너를 띄운 컴퓨터에서 그 CLI 에 로그인한 뒤 "
     "다시 질문해 주세요."),
    (re.compile(r"unknown option|unrecognized (option|argument)|"
                r"invalid (option|argument)|unexpected argument", re.I),
     "연결된 AI 가 이 호출의 옵션을 알지 못합니다(구버전일 수 있습니다). 그 CLI 를 업데이트하거나 "
     "웹의 「연결 준비」로 러너를 최신 사본으로 다시 받아 실행해 주세요."),
    (re.compile(r"command not found|no such file or directory|not recognized as", re.I),
     "연결된 AI 의 실행 파일을 찾지 못했습니다. 러너를 띄운 컴퓨터에 그 CLI 가 설치돼 있고 "
     "PATH 에서 보이는지 확인해 주세요."),
)

#: 실패 원문에 섞여 나갈 수 있는 자격증명 형태. 사유를 살리려다 토큰을 대화에 흘리지 않는다.
_SECRET_PATTERNS = (
    re.compile(r"\bmat_[A-Za-z0-9_\-]{4,}"),
    re.compile(r"(?i)\b(bearer|authorization:\s*bearer)\s+\S+"),
    re.compile(r"(?i)\b(sk|api)[-_][A-Za-z0-9_\-]{8,}"),
)


def _redact_secrets(text: str) -> str:
    """실패 원문에서 자격증명 형태를 지운다. 사유를 살리는 일이 토큰 유출이 되면 안 된다."""
    out = text or ""
    for pat in _SECRET_PATTERNS:
        out = pat.sub("<가려짐>", out)
    return out


def _meaningful_lines(text: str) -> str:
    """잡음 줄을 걷어낸 나머지. 전부 잡음이면 빈 문자열."""
    keep = [ln for ln in (text or "").splitlines()
            if not any(p.search(ln) for p in _STDERR_NOISE)]
    return "\n".join(keep).strip()


def describe_cli_failure(returncode: int, out: str, err: str) -> str:
    """자식 CLI 가 0 이 아닌 코드로 끝났을 때 **사용자에게 나갈 한 덩어리**를 만든다.

    ## 왜 stdout 도 보는가 (라이브 실측 2026-09-01)

    종전에는 stderr 만 실어 보냈다. 그런데 실패 사유를 **stdout 으로 내는 CLI 가 있다** —
    claude 는 사용 한도에 걸리면 `You've hit your session limit · resets 5:30pm` 을 stdout 에
    쓰고 exit 1 로 끝나며, stderr 에는 stdin 안내만 남는다. 그래서 사용자가 받은 답은

        AI 가 오류로 끝났습니다(exit 1):

    — 콜론 뒤가 **빈** 문장이었다. 원인이 화면에 없으니 사용자는 같은 질문을 그대로 다시
    보냈고(대화 `…d7010dcf`, 15:38 · 15:39), 같은 빈 문장을 다시 받은 뒤 대화를 떠났다.
    한도는 몇 분 뒤 풀리는 **회복 가능한** 상태였다.

    즉 고칠 것은 한도 자체가 아니라 **사유를 버리는 경로**다. 채널(어느 파이프로 나오는가)은
    CLI 마다 다르고 버전마다 바뀌므로, 채널을 맞히려 들지 않고 **둘 다 보고 의미 있는 쪽을
    고른다** — 이 선택은 CLI 가 무엇이든 성립한다.

    ## 무엇을 어떤 순서로 담나

    1. `exit <코드>` — 기계적 사실.
    2. 사유 원문(잡음 제거 · 자격증명 마스킹 · `_FAIL_DETAIL_MAX` 자름). stderr 에 의미 있는
       줄이 있으면 그것, 없으면 stdout. 둘 다 없으면 "출력이 없었다" 를 **명시**한다 —
       빈 콜론으로 끝내지 않는다(그게 이 결함의 표면이었다).
    3. 다음 행동 1줄(`_FAILURE_HINTS` 가 맞을 때만). 맞는 것이 없으면 붙이지 않는다.
    """
    detail = _meaningful_lines(err) or _meaningful_lines(out)
    detail = _redact_secrets(detail)
    if len(detail) > _FAIL_DETAIL_MAX:
        detail = detail[:_FAIL_DETAIL_MAX] + "…"
    head = f"AI 가 오류로 끝났습니다(exit {returncode})."
    body = f" 연결된 AI 가 남긴 사유: {detail}" if detail else \
        " 연결된 AI 가 아무 출력도 남기지 않아 사유를 알 수 없습니다."
    for pat, hint in _FAILURE_HINTS:
        if detail and pat.search(detail):
            return head + body + "\n\n" + hint
    return head + body


def _run_cli_cancelable(cmd: list[str], cancel_check, cwd: str | None = None,
                        env: dict | None = None) -> tuple[bool, str]:
    """CLI 를 돌리되 **취소되면 죽인다**. (성공여부, 본문 | CANCELED)

    왜 `subprocess.run` 이 아닌가: `run` 은 끝날 때까지 블로킹이라 그동안 도착한 취소를 볼 수
    없다. 그러면 사용자가 중단을 눌러도 개인 계정 토큰이 그 조사가 끝날 때까지 계속 탄다 —
    취소의 실질 목적이 바로 그 낭비를 막는 것이다.

    ⚠ 여기에도 sleep 은 없다. 자식이 끝나기를 `Thread.join(timeout)` 으로 **블로킹 대기**하고,
    그 반환 틈에 취소를 확인할 뿐이다. 서버를 두드리지 않으므로 폴링이 아니다.
    """
    # 이 호출의 **소요와 결말**을 남긴다 (TASK-20260901T163000). 종전에는 자식이 실패해도
    # 사유 400자가 사용자 답변에 실려 나갈 뿐, 로그에는 아무것도 남지 않았다 — 「내 AI 가
    # 오류로 끝났습니다」를 받은 사용자가 원인을 물어와도 우리 쪽에 볼 것이 없었다.
    _t0 = time.monotonic()
    _exe = (cmd[0] if cmd else "")
    try:
        proc = subprocess.Popen(_resolve_exe(cmd), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                cwd=cwd, env=env)
    except Exception as e:  # noqa: BLE001
        # 여기서 터지는 것은 대개 「그 실행 파일이 없다·권한이 없다」이고, 예외 형이 그
        # 둘을 정확히 가른다(FileNotFoundError vs PermissionError). 문자열로 뭉개지 않는다.
        _log_exc(_EV_AI_SPAWN_FAIL, "AI 를 실행하지 못했다", e, exe=_exe, cwd=cwd or "")
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
            log_event("ai.canceled", "취소되어 AI 를 중단했다", level="WARN",
                      exe=_exe, dur_ms=int((time.monotonic() - _t0) * 1000))
            return False, CANCELED
        if _AI_TIMEOUT_SEC and waited >= _AI_TIMEOUT_SEC:
            _kill(proc)
            pump.join(5.0)
            log_event(_EV_AI_TIMEOUT, "AI 호출이 상한을 넘겨 중단했다", level="ERROR",
                      exe=_exe, limit_sec=int(_AI_TIMEOUT_SEC),
                      dur_ms=int((time.monotonic() - _t0) * 1000),
                      stderr_tail=(box.get("err") or "")[-2000:])
            return False, f"AI 호출이 {int(_AI_TIMEOUT_SEC)}초를 넘겨 중단했습니다."

    _dur = int((time.monotonic() - _t0) * 1000)
    if proc.returncode != 0:
        # ⚠ 자식의 출력 **전문**(각 상한 2KB)은 원장에만 남긴다. 사용자 답변에 실리는 400자는
        #   잘려 있어서, 정작 원인이 적힌 뒷부분이 사라지는 일이 잦았다.
        # ⚠ stderr 뿐 아니라 **stdout 꼬리도** 남긴다 (TASK-20260901T160000): 사용 한도 같은
        #   정책성 실패의 사유를 stdout 으로 내는 CLI 가 있고, stderr 만 적는 원장은 그 실패를
        #   「사유 없음」으로 기록한다 — 사용자 화면에서 사라진 것과 같은 정보가 원장에서도
        #   사라지면 사후 진단이 불가능해진다.
        log_event(_EV_AI_FAIL, "AI 가 오류로 끝났다", level="ERROR",
                  exe=_exe, exit=proc.returncode, dur_ms=_dur,
                  stdout_bytes=len(box.get("out") or ""),
                  stdout_tail=_redact_secrets((box.get("out") or "")[-2000:]),
                  stderr_tail=_redact_secrets((box.get("err") or "")[-2000:]))
        return False, describe_cli_failure(int(proc.returncode), box.get("out", ""),
                                           box.get("err", ""))
    log_event("ai.ok", level="DEBUG", exe=_exe, exit=0, dur_ms=_dur,
              stdout_bytes=len(box.get("out") or ""))
    return True, (box.get("out") or "").strip()


def _kill(proc) -> None:
    """자식을 확실히 끝낸다. 이미 죽었으면 조용히 지나간다."""
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


def offered_options(runtimes: list | None, runtime: str) -> tuple[list, list]:
    """**이 러너가 실제로 신고한** 그 런타임의 (모델, 등급) 목록. 없으면 빈 목록.

    정적 표(`_RUNTIME_SPECS`)가 아니라 신고를 보는 이유 (codex REV-20260828T170000 P1-5):
    둘은 갈릴 수 있다 —

      - `--ai codex` 로 제한하면 신고는 codex 뿐이지만 표에는 claude 도 있다
      - PATH 에 없는 런타임은 신고에서 빠지지만 표에는 남아 있다

    표를 대조하면 "자기가 신고한 값만 실행한다" 가 거짓이 되고, 실제로는 "소스에 적혀 있고
    PATH 에 있으면 실행한다" 가 된다. 그 차이는 사용자가 `--ai` 로 세운 제한을 서버 응답이
    넘어서는 형태로 드러난다.

    `runtimes` 가 `None` 이면(신고 자체를 안 하는 `--cmd` 모드) 빈 목록 — 어차피 그 경로는
    지정값을 쓰지 않는다.
    """
    for rt in (runtimes or []):
        if str(rt.get("runtime") or "") == runtime:
            return list(rt.get("models") or []), list(rt.get("efforts") or [])
    return [], []


def build_cmd(runtime: str, prompt: str, model: str | None = None,
              effort: str | None = None, runtimes: list | None = None,
              caps: dict | None = None) -> list[str]:
    """지정 (런타임, 모델, 추론등급) 을 **그 CLI 의 실제 인자**로 옮긴다 (P0-Z3).

    대조 대상은 **이 러너가 신고한 목록**(`runtimes`)이다 — 서버가 뭘 돌려주든 우리가 고를 수
    있다고 말한 것만 실행한다. `runtimes` 를 주지 않으면 정적 표로 폴백한다(단위 테스트·
    구 호출부 호환). 그 폴백은 신고보다 넓을 수 있으므로 **운영 경로는 반드시 신고를 넘긴다**.

    표 밖 값은 **조용히 버린다** — 알 수 없는 문자열을 인자로 넘기면 CLI 가 통째로 실패하고,
    그러면 답이 아예 오지 않는다. 버린 사실은 호출측(`ask_local_ai`)이 사용자에게 밝힌다.

    프롬프트는 **인자로** 넘긴다(셸 미경유) — 질문에 셸 메타문자가 섞여도 그대로 전달되고
    명령 주입 경로가 생기지 않는다. 모델·등급도 같은 규칙을 따른다.
    """
    spec = _RUNTIME_SPECS.get(runtime) or {}
    # 호출 형태의 출처: 우리 표 → 없으면 **질의 때 통했던 형태**(표 밖 CLI). 둘 다 없으면
    # 인자를 만들 수 없으므로 빈 목록이 되고, 호출측이 종전 경로로 떨어진다.
    argv = list(spec.get("argv") or (caps or {}).get("argv") or [])
    flags: list[str] = []

    # 호출법(플래그 형태)의 출처 — **그 AI 가 스스로 답한 것**이 우선이고, 없으면 내장 표
    # (P0-Z4). 이 값은 로컬 `config.json` 에서만 오고 서버를 거치지 않는다.
    local = caps or {}
    model_flag = local.get("model") if local.get("model") is not None else spec.get("model")
    effort_flag = local.get("effort") if local.get("effort") is not None else spec.get("effort")

    if runtimes is None:
        allowed_models = list(local.get("models") or spec.get("models") or [])
        allowed_efforts = list(local.get("efforts") or spec.get("efforts") or [])
    else:
        allowed_models, allowed_efforts = offered_options(runtimes, runtime)

    def _valid(options: list, value: str | None) -> bool:
        if not value:
            return False
        return any(str(o.get("value")) == value for o in options)

    if model and model_flag and _valid(allowed_models, model):
        flags += [a.replace("{model}", model) for a in model_flag]
    if effort and effort_flag and _valid(allowed_efforts, effort):
        flags += [a.replace("{effort}", effort) for a in effort_flag]

    # 플래그는 **프롬프트 앞**에 둔다. 서브커맨드(`codex exec`)와 위치 인자(프롬프트) 사이가
    # 옵션의 자리이고, 프롬프트 뒤에 붙이면 CLI 에 따라 프롬프트의 일부로 먹힌다.
    out: list[str] = []
    for a in argv:
        if a == "{prompt}" or "{prompt}" in a:
            out += flags
            flags = []
            out.append(prompt if a == "{prompt}" else a.replace("{prompt}", prompt))
        else:
            out.append(a)
    return out + flags


def _ensure_strict_mcp_supported(kind: str, exe: str = "claude") -> bool:
    """claude 가 `--strict-mcp-config` 를 아는지 기동 시 1회 확인한다. (플래그가 남으면 True)

    모르는 버전에 넘기면 **모든 질문이** unknown option 으로 죽는다 — 사용자에게는 "AI 가
    답을 안 한다" 로만 보인다 (codex P2-2). 그래서 확인하고, 없으면 표에서 빼고 말한다.

    **확인 자체가 실패하면(미설치·타임아웃) 플래그를 남긴다.** 두 오류의 값이 다르기
    때문이다 — 잘못 남기면 즉시·시끄럽게 실패해서 고칠 수 있고, 잘못 빼면 원 결함이
    조용히 돌아와 아무도 모른다. 드러나는 쪽을 고른다.
    """
    if kind != "claude" or _KEEP_MCP:
        return False
    spec_argv = list((_RUNTIME_SPECS.get("claude") or {}).get("argv") or [])
    if _STRICT_MCP_FLAG not in spec_argv:
        return False
    try:
        proc = subprocess.run(_resolve_exe([exe, "--help"]), capture_output=True,
                              text=True, timeout=30)
        helptext = (proc.stdout or "") + (proc.stderr or "")
    except Exception:  # noqa: BLE001  (미설치·타임아웃·권한 — 전부 "확인 못 했다" 로 같다)
        _log(f"참고: {exe} --help 로 {_STRICT_MCP_FLAG} 지원을 확인하지 못했습니다. "
             "플래그는 그대로 씁니다(문제가 있으면 첫 질문에서 곧바로 드러납니다).")
        return True
    if _STRICT_MCP_FLAG in helptext:
        return True
    _RUNTIME_SPECS["claude"]["argv"] = [a for a in spec_argv if a != _STRICT_MCP_FLAG]
    _log(f"경고: 이 claude 는 {_STRICT_MCP_FLAG} 를 지원하지 않습니다(구버전). 플래그를 빼고 "
         "진행하지만, 이 머신에 설정된 MCP 서버가 그대로 붙습니다 — 같은 서비스의 상주 토큰이 "
         "만료돼 있으면 조사가 401 로 막힐 수 있습니다. claude 를 업데이트하는 것을 권합니다.")
    return False


#: `--append-system-prompt` 지원 여부 캐시. `None` = 아직 확인 안 함.
_system_channel_cache: dict[str, bool] = {}


def system_channel_supported(kind: str, custom: str | None = None,
                             exe: str | None = None) -> bool:
    """이 런타임에서 운영자 지침을 **시스템 채널**로 넘길 수 있는가 (TASK-20260901T140000).

    ## 실패 기본값이 `--strict-mcp-config` 와 **반대**인 이유

    `_ensure_strict_mcp_supported` 는 확인 실패 시 플래그를 **남긴다** — 잘못 남기면 첫
    질문에서 시끄럽게 터져 고칠 수 있고, 잘못 빼면 원 결함이 조용히 돌아오기 때문이다.

    여기는 반대다. 잘못 남기면 unknown option 으로 **모든 질문이 죽고**, 잘못 빼면 종전
    동작(지침을 본문에 싣는다)으로 떨어질 뿐이다 — 오탐 위험은 남지만 서비스는 돈다.
    즉 «드러나는 쪽» 이 아니라 «답이 오는 쪽» 을 고른다. 두 함수의 비대칭은 의도적이다.

    `--cmd`(사용자가 명령을 통째로 준 경우)는 대상이 아니다 — 그 명령에 우리가 플래그를
    얹으면 중복 지정으로 CLI 가 거절할 수 있고, `--cmd` 의 의미도 사라진다.
    """
    if custom or kind != "claude":
        return False
    spec = _RUNTIME_SPECS.get(kind) or {}
    if not spec.get("system"):
        return False
    exe = exe or str((spec.get("argv") or [kind])[0])
    if exe in _system_channel_cache:
        return _system_channel_cache[exe]
    try:
        proc = subprocess.run(_resolve_exe([exe, "--help"]), capture_output=True,
                              text=True, timeout=30)
        helptext = (proc.stdout or "") + (proc.stderr or "")
    except Exception:  # noqa: BLE001  (미설치·타임아웃·권한 — 전부 "확인 못 했다")
        _system_channel_cache[exe] = False
        _log(f"참고: {exe} --help 로 {_APPEND_SYSTEM_FLAG} 지원을 확인하지 못했습니다. "
             "운영자 지침은 종전대로 프롬프트 본문에 싣습니다.")
        return False
    ok = _APPEND_SYSTEM_FLAG in helptext
    _system_channel_cache[exe] = ok
    if not ok:
        _log(f"참고: 이 {exe} 는 {_APPEND_SYSTEM_FLAG} 를 지원하지 않습니다(구버전). 운영자 "
             "지침을 프롬프트 본문에 싣습니다 — 일부 AI 가 이를 인젝션으로 오판할 수 있으니 "
             "업데이트를 권합니다.")
    return ok


def _with_system_prompt(cmd: list[str], kind: str, system: str | None) -> list[str]:
    """조립된 명령에 `--append-system-prompt <지침>` 을 끼운다. 자리는 **프롬프트 바로 앞**.

    프롬프트 뒤에 붙이면 CLI 에 따라 프롬프트의 일부로 먹힌다(`build_cmd` 의 플래그 배치와
    같은 이유). 프롬프트 자리를 못 찾으면 **끼우지 않는다** — 위치를 추측해 넣느니 종전
    동작으로 떨어지는 편이 안전하다(본문 폴백은 `compose_prompt` 가 이미 갖고 있다).
    """
    tmpl = list(((_RUNTIME_SPECS.get(kind) or {}).get("system")) or [])
    if not system or not tmpl or not cmd:
        return cmd
    flags = [a.replace("{system}", system) for a in tmpl]
    # 프롬프트는 `ask_local_ai`/`build_cmd` 가 이미 치환해 넣었으므로 자리표시자가 없다.
    # 마지막 인자가 프롬프트인 것이 모든 런타임 명세의 공통 형태다(`{prompt}` 가 argv 끝).
    return cmd[:-1] + flags + cmd[-1:]


def _child_workdir() -> str | None:
    """자식 AI CLI 를 띄울 **중립 작업 디렉토리** (TASK-20260901T140000).

    ## 왜 필요한가

    `Popen` 은 cwd 를 주지 않으면 러너의 것을 상속한다. 러너를 코드 저장소 안에서 띄운
    사용자는 그 저장소의 `CLAUDE.md`·`AGENTS.md` 와 «코딩 에이전트» 정체성이 얹힌 채로
    질문을 받게 되고, 그러면 「내 역할은 이 저장소의 코딩이지 사내 DB 질의가 아니다」가
    거부 논거가 된다 — 라이브 거부문이 실제로 "저는 지금 `/root` 저장소에서 Claude Code로
    동작 중" 이라고 밝히며 그 논거를 폈다(2026-09-01).

    빈 디렉토리 하나면 그 상속이 끊긴다. 만들지 못하면 `None` 을 돌려 **종전대로** 상속한다
    (작업 디렉토리 때문에 답변 자체를 막지는 않는다).
    """
    path = os.path.join(os.path.expanduser("~"), ".mysql-ai-bridge", "work")
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except Exception:  # noqa: BLE001
        return None


#: `--cmd` 경고를 이미 냈는가 (매 질문마다 같은 줄을 찍지 않는다).
_custom_cmd_warned = False


def _warn_custom_cmd_without_mcp_isolation(argv: list[str]) -> bool:
    """claude 를 부르는 `--cmd` 에 MCP 배제가 없으면 **1회** 경고한다. (경고했으면 True)

    판정은 실행 파일 이름으로만 한다 — 경로(`/usr/local/bin/claude`)로 줄 수도 있어서
    basename 을 본다. 다른 CLI 를 부르는 `--cmd` 는 대상이 아니다(그 CLI 에는 이 플래그가
    없다).
    """
    global _custom_cmd_warned
    if _custom_cmd_warned or _KEEP_MCP or not argv:
        return False
    if os.path.basename(str(argv[0])).lower() not in ("claude", "claude.exe"):
        return False
    if _STRICT_MCP_FLAG in [str(a) for a in argv]:
        return False
    _custom_cmd_warned = True
    _log(f"경고: --cmd 의 claude 명령에 {_STRICT_MCP_FLAG} 가 없습니다. 이 머신에 설정된 MCP "
         "서버(같은 서비스의 상주 토큰 포함)가 그대로 붙어, 만료된 토큰이 조사를 401 로 "
         f"막을 수 있습니다. 명령에 {_STRICT_MCP_FLAG} 를 추가하는 것을 권합니다.")
    return True


def ask_local_ai(kind: str, argv: list[str], prompt: str, custom: str | None,
                 cancel_check=None, model: str | None = None,
                 effort: str | None = None,
                 runtimes: list | None = None,
                 caps: dict | None = None,
                 system: str | None = None,
                 token: str | None = None) -> tuple[bool, str]:
    """내 AI 에게 물어 답 문자열을 얻는다. (성공여부, 본문)

    `model`·`effort` 는 사용자가 **웹에서 고른 것**이다 (P0-Z3). 유효성은 `runtimes`(이 러너가
    하트비트로 신고한 목록)로 판정한다 — 서버가 준 값을 그대로 믿지 않는다. 지정이 없거나
    신고 밖이면 이 머신의 AI 설정이 정한다.

    `custom`(`--cmd`)이 있으면 그것이 이긴다 — 사용자가 명령 전체를 직접 준 것이므로 그 위에
    우리가 플래그를 얹으면 중복 지정으로 CLI 가 거절할 수 있다.

    `cancel_check` 는 "지금 취소됐는가" 를 묻는 함수다. 취소되면 본문 자리에 `CANCELED` 를
    돌려준다 — 실패와 구분해야 호출측이 "제출하지 않는다" 를 선택할 수 있다.
    """
    _canceled = cancel_check or (lambda: False)
    if custom:
        argv = shlex.split(custom)
        kind = "custom"
        # ⚠ `--cmd` 는 사용자가 명령을 **통째로** 준 것이라 우리가 플래그를 얹지 않는다(얹으면
        #   중복 지정으로 CLI 가 거절한다). 그래서 claude 를 부르는 custom 명령에는 MCP 배제가
        #   빠지고, 그 사용자는 라이브 사고와 **같은 경합**을 그대로 만난다 (codex P1-2).
        #   명령을 자동으로 고치지는 않는다 — 사용자가 준 것을 우리가 바꾸면 `--cmd` 의 의미가
        #   사라진다. 대신 **말한다**. 조용히 놔두면 그 사용자만 원인 모를 재발을 겪는다.
        _warn_custom_cmd_without_mcp_isolation(argv)
    _local = (caps or {}).get(kind) or {}
    if (kind in _RUNTIME_SPECS or _local.get("argv")) and (model or effort):
        cmd = build_cmd(kind, prompt, model, effort, runtimes, _local)
    else:
        # 프롬프트는 **인자로** 넘긴다(셸을 거치지 않는다) — 질문 본문에 셸 메타문자가 섞여도
        # 그대로 전달되고, 명령 주입 경로가 생기지 않는다.
        cmd = [prompt if a == "{prompt}" else a.replace("{prompt}", prompt) for a in argv]
    # 운영자 지침을 실제 시스템 채널로 (TASK-20260901T140000). 호출측이 지원 여부를 이미
    # 판정해 `system` 을 넘겼을 때만 실린다 — 여기서 다시 판정하면 프롬프트를 만든 판정과
    # 갈릴 수 있고, 그러면 지침이 **두 벌**이거나 **한 벌도 없는** 상태가 된다.
    cmd = _with_system_prompt(cmd, kind, system)
    if _canceled():
        return False, CANCELED
    # 토큰은 **환경변수로** 준다 (TASK-20260901T140000). 프롬프트 본문에 실린 평문 자격증명이
    # 인젝션 오판의 근거 2번이었고, 같은 노출은 `/proc/<pid>/cmdline`·CLI 세션 기록으로도
    # 샜다(`FUNCTION.md` 가 잔여 노출면으로 인정하던 항목). 자식은 이 값을 그대로 상속한다.
    child_env = None
    if token:
        child_env = {**os.environ, "BRIDGE_TOKEN": str(token)}
    return _run_cli_cancelable(cmd, _canceled, cwd=_child_workdir(), env=child_env)
