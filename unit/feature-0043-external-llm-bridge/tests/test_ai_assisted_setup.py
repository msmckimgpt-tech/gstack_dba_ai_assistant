"""feature-0043 P0-AD — 환경 판단만 그 머신의 AI 에게, 실행은 스크립트가.

## 왜 이 경로가 생겼나

P0-AC 는 **실행**의 비결정성을 없앴다("LLM에 요청함에 따라 구축하는 방식이 모두 달라 사용자의
경험이 일정하지 않다" — 사용자 제보 2026-08-28). 그런데 **판단**은 여전히 스크립트에 박혀
있었다. python 은 `python3 → python` 순으로 찍고, 핸들러는 `uname` 으로 갈랐다.

그 고정값이 틀리는 조합이 실측됐다(2026-08-28): 브라우저는 Windows, `claude` 는 WSL 안.
어떤 `uname` 분기도 그것을 맞히지 못한다. 조합은 열려 있어 우리가 열거할 수 없다.

## 이 스위트가 잠그는 경계

    AI 가 채운다 → `BRIDGE_PROBED_*`  (조사해서 알아내는 값)
    스크립트가 한다 → 대조·설치·기동     (무엇을 할지는 고정)

경계가 무너지는 방향은 둘이고, 둘 다 여기서 막는다:

1. **AI 쪽으로 넘어가기** — 채운 값이 검증 없이 명령이 되는 것. `--cmd`(임의 명령 실행)·
   `--base`/`--token`(다른 서버로 돌리기)가 그 칸으로 들어오면 이 설계가 보장한다는 것이
   전부 무너진다. → allowlist 테스트.
2. **스크립트 쪽으로 넘어가기** — 지시문이 "연결해줘" 로 되돌아가는 것. 그러면 P0-AC 가
   고친 문제가 그대로 재발한다. → 지시문 계약 테스트.

계약은 **동작으로** 잠근다 — 실제 `sh` 에 슬라이스를 먹여 결과 argv 를 보고, 서버 함수는
실제로 호출해 산출물을 본다.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_SETUP_SH = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.sh"
_SETUP_PS1 = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.ps1"
_WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
_OAUTH_AS = _WEB_SRC / "routers" / "oauth_as.py"
_INDEX_HTML = _WEB_SRC / "static" / "index.html"
_AIC_HTML = _WEB_SRC / "static" / "ai-connect.html"
_MODAL_JS = _WEB_SRC / "static" / "app" / "connect-modal.js"
_AIC_JS = _WEB_SRC / "static" / "ai-connect.js"

#: 러너 인자 중 **이 칸으로 절대 들어오면 안 되는** 것. 각각이 무너뜨리는 것을 함께 적는다.
_FORBIDDEN_RUNNER_ARGS = [
    ("--cmd", "임의 명령을 AI 호출로 실행"),
    ("--base", "다른 서버로 질문·답변을 돌림"),
    ("--token", "다른 자격증명으로 동작"),
    ("--ca", "신뢰 앵커 교체"),
    ("--once", "상주하지 않고 끝남(연결이 유지되지 않음)"),
    ("--check", "상주하지 않고 끝남"),
]


def _slice_probe_section() -> str:
    """설치 스크립트에서 **검증 구역만** 떼어낸다 (`set -eu` → `RUNNER_ARGS=`).

    전체를 돌리면 네트워크·설치·프로세스 기동이 일어난다. 검증 로직은 순수하므로 이 구간만
    실행해도 계약이 그대로 확인된다 — 그리고 **실제 `sh` 가 파싱**하므로 소스 검사보다 세다.
    """
    out, on = [], False
    for line in _SETUP_SH.read_text(encoding="utf-8").split("\n"):
        if line.strip() == "set -eu":
            on = True
        if on:
            out.append(line)
        if line.startswith("RUNNER_ARGS="):
            break
    assert out and out[-1].startswith("RUNNER_ARGS="), "슬라이스 경계를 찾지 못했다"
    # 네트워크·설치 명령이 슬라이스에 섞이면 테스트가 실제로 무언가를 내려받게 된다.
    body = "\n".join(out)
    assert "curl -fsS" not in body, "슬라이스에 네트워크 호출이 섞였다"
    return body


#: 진행 로그(`say`)와 결과를 가르는 표식. 마커 없이 stdout 을 통째로 읽으면 정상 경로의
#: 안내문("러너 인자: … (조사값)")이 결과에 섞여 **정상 케이스만 실패**한다(구현 중 겪음).
_MARK = "__RUNNER_ARGS__"


def _run_probe(env: dict) -> tuple[str, str]:
    """검증 구역을 실행하고 `(RUNNER_ARGS, stderr)` 를 돌려준다."""
    script = _slice_probe_section() + f'\nprintf "\\n{_MARK}%s" "$RUNNER_ARGS"\n'
    # ⚠ PATH 를 고정하지 않는다. 재현성 때문에 `/usr/bin:/bin` 으로 박았더니 컨테이너
    #   (`python` 이 `/usr/local/bin`)에서 파이썬 탐색이 실패해 스크립트가 `die` 로 죽고,
    #   **37건이 환경 문제로 빨개졌다**(로컬은 green). 이 스위트가 보려는 것은 검증 로직이지
    #   호스트의 PATH 배치가 아니다.
    base = {"BRIDGE_BASE": "https://h.example", "BRIDGE_TOKEN": "mat_x",
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp"}
    base.update(env)
    proc = subprocess.run(["sh", "-c", script], capture_output=True, text=True,
                          env=base, timeout=60)
    assert proc.returncode == 0, f"검증 구역이 죽었다(rc={proc.returncode}): {proc.stderr[:300]}"
    assert _MARK in proc.stdout, f"결과 표식이 없다 — 중간에 멈췄다: {proc.stdout[:300]}"
    return proc.stdout.split(_MARK, 1)[1].strip(), proc.stderr


# ── 경계 ①: AI 가 채운 값은 검증을 통과해야만 명령이 된다 ────────────────────


@pytest.mark.parametrize("flag,why", _FORBIDDEN_RUNNER_ARGS)
def test_probed_args_cannot_carry_dangerous_runner_flags(flag, why):
    """`BRIDGE_PROBED_ARGS` 로 위험 인자를 실을 수 없다.

    이 칸은 **프롬프트 인젝션의 착지점**이다 — 서버가 준 텍스트를 읽은 AI 가 채우는 자리이고,
    setup 단계는 러너와 달리 아직 신뢰가 성립하기 **전**이다.
    """
    args, err = _run_probe({"BRIDGE_PROBED_ARGS": f"{flag} something"})
    assert flag not in args, f"{flag} 가 러너 인자가 됐다 — {why}"
    assert args == "", f"위험 인자가 섞인 목록은 통째로 버려야 한다: {args!r}"
    assert "⚠" in err, "버린 사실이 사용자에게 도달하지 않는다"


def test_dropped_values_are_reported_on_stderr_not_swallowed():
    """거른 사실이 **도달한다**.

    구현 중 실제로 겪은 형태: `drop()` 이 stdout 이라 `$(...)` 명령치환 안에서 부른 경고가
    치환값에 먹혀 **차단은 되는데 경고만 사라졌다**. 「조용히 버리지 않는다」를 주석에 적어
    두고 그 반대를 구현한 형태라, 값을 거르는 것만큼 거른 사실이 보이는 것도 계약이다.
    """
    _args, err = _run_probe({"BRIDGE_PROBED_ARGS": "--cmd evil"})
    assert "허용 목록에 없습니다" in err
    # stdout(치환 대상)이 아니라 stderr 여야 한다.
    assert "drop() { printf" in _SETUP_SH.read_text(encoding="utf-8")
    assert ">&2" in _SETUP_SH.read_text(encoding="utf-8").split("drop() {")[1].split("\n")[0]


@pytest.mark.parametrize("raw,expect", [
    ("--workers 4", "--workers 4"),
    ("--refresh-caps", "--refresh-caps"),
    ("--workers 4 --ai-timeout 300 --refresh-caps", "--workers 4 --ai-timeout 300 --refresh-caps"),
    ("--max-workers 8", "--max-workers 8"),
    ("--worker-idle-sec 90", "--worker-idle-sec 90"),
])
def test_allowlisted_numeric_axes_pass_through(raw, expect):
    """허용 축(이 머신 사양·속도에 맞추는 수치)은 그대로 통과한다.

    이 단언이 없으면 금지 목록을 넓히다가 정당한 값까지 죽이고, 그러면 AI 가 조사한 것이
    아무것도 반영되지 않아 이 기능이 **있으나 마나**가 된다.
    """
    args, _err = _run_probe({"BRIDGE_PROBED_ARGS": raw})
    assert args.split() == expect.split(), f"정당한 값이 버려졌다: {raw}"


@pytest.mark.parametrize("raw", [
    "--workers",              # 값 누락
    "--workers --refresh-caps",  # 값 자리에 플래그
    "--workers abc",          # 값이 숫자가 아님
    "--workers 4; rm -rf /",  # 셸 메타
    "--unknown-flag 1",
])
def test_malformed_probed_args_are_rejected_wholesale(raw):
    """형태가 어긋나면 **통째로** 버린다 — 일부만 살리면 의도와 다른 조합이 실행된다."""
    args, err = _run_probe({"BRIDGE_PROBED_ARGS": raw})
    assert args == "", f"버려지지 않았다: {raw!r} -> {args!r}"
    assert "⚠" in err


@pytest.mark.parametrize("val", ["python3; rm -rf /", "--version", "py`id`", "a b", "$(whoami)"])
def test_probed_py_shape_is_enforced(val):
    """`BRIDGE_PROBED_PY` 는 명령의 **첫 토큰**이 된다 — 옵션·메타문자를 받지 않는다."""
    args, err = _run_probe({"BRIDGE_PROBED_PY": val})
    assert "⚠" in err, f"형태 검사를 통과했다: {val!r}"
    assert args == ""


def test_probed_py_must_actually_run_and_be_38_plus():
    """이름이 아니라 **실행해서** 판정한다.

    `python` 이 2.7 인 머신에서 이름만 보고 넘기면 러너가 문법 오류로 죽고, 그 죽음은
    사용자에게 "AI 가 답을 안 한다" 로만 보인다.
    """
    _args, err = _run_probe({"BRIDGE_PROBED_PY": "/no/such/python"})
    assert "미실존 또는 3.8 미만" in err
    src = _SETUP_SH.read_text(encoding="utf-8")
    assert "sys.version_info >= (3, 8)" in src, "버전을 실제로 확인하지 않는다"


@pytest.mark.parametrize("val", ["claude;id", "claude rm", "--ai", "a|b"])
def test_probed_ai_rejects_non_identifier(val):
    """`--ai` 로 넘어가는 값은 식별자 형태만."""
    args, err = _run_probe({"BRIDGE_PROBED_AI": val})
    assert "⚠" in err
    assert "--ai" not in args


def test_probed_ai_must_exist_on_path():
    """알려진 이름이어도 **PATH 에 없으면** 넘기지 않는다.

    실측된 사례가 정확히 이것이다(2026-08-28): Windows 에 `claude` 가 없는데 그쪽으로
    러너를 세우면 "쓸 수 있는 AI 를 찾지 못했습니다" 로 뜨자마자 죽는다.
    """
    missing = next((n for n in ("gemini", "ollama", "codex", "claude")
                    if shutil.which(n) is None), None)
    if missing is None:
        pytest.skip("알려진 AI CLI 가 모두 설치돼 있어 '부재' 를 만들 수 없다")
    args, err = _run_probe({"BRIDGE_PROBED_AI": missing})
    assert "PATH 에 없습니다" in err
    assert args == ""


def test_probed_ai_that_exists_is_passed_through():
    """알려진 목록에 있고 실재하면 그대로 `--ai` 인자가 된다 (반쪽 계약 방지)."""
    present = next((n for n in ("claude", "codex", "gemini", "ollama")
                    if shutil.which(n)), None)
    if present is None:
        pytest.skip("이 환경에 알려진 AI CLI 가 하나도 없다")
    args, _err = _run_probe({"BRIDGE_PROBED_AI": present})
    assert args.split() == ["--ai", present]


def test_human_args_win_over_probed_args():
    """사람 칸(`BRIDGE_ARGS`)이 **뒤에** 온다 — 겹치면 사람이 이긴다.

    자기 머신에서 자기가 준 값이 조사값보다 우선하는 것이 맞다. 그리고 사람 칸은 무검증이라
    (기존 호환) 이 순서가 뒤집히면 검증된 값이 무검증 값을 덮는 이상한 우선순위가 된다.
    """
    args, _err = _run_probe({"BRIDGE_PROBED_ARGS": "--workers 2", "BRIDGE_ARGS": "--workers 9"})
    assert args.split() == ["--workers", "2", "--workers", "9"], args


def test_human_args_stay_unvalidated_for_backward_compatibility():
    """사람 칸은 좁히지 않는다 — `--cmd` 로 자기 AI 를 지정하던 사용자를 깨지 않는다.

    이 테스트는 "왜 칸을 둘로 나눴는가" 를 고정한다. 하나로 합치면 둘 중 하나가 반드시
    희생된다(기존 사용자 파손 또는 인젝션 표면).
    """
    args, _err = _run_probe({"BRIDGE_ARGS": "--cmd 'my-ai -p {prompt}'"})
    assert "--cmd" in args, "사람이 직접 준 인자까지 막으면 기존 사용례가 깨진다"


@pytest.mark.parametrize("val,expect_drop", [
    ("auto", False), ("none", False), ("", False),
    ("native", True),   # 구현이 auto 와 같아 공개하지 않는다 (codex P2-8)
    ("wsl", True), ("../x", True),
])
def test_probed_handler_is_whitelisted(val, expect_drop):
    """핸들러 모드는 화이트리스트. 벗어나면 `auto` 로 되돌린다."""
    _args, err = _run_probe({"BRIDGE_PROBED_HANDLER": val})
    assert ("auto|none" in err) is expect_drop, f"{val!r}: {err!r}"


def test_handler_none_is_a_choice_not_a_failure():
    """`none` 은 실패가 아니라 선택이다 — 실패 문구를 쓰면 사용자가 고칠 것을 찾는다.

    실측된 조합: 러너는 WSL 안, 브라우저는 Windows. 여기 등록해 봐야 그 브라우저는 보지
    못하므로, 헛된 등록물을 남기는 대신 안 하는 것을 고를 수 있어야 한다.
    """
    src = _SETUP_SH.read_text(encoding="utf-8")
    assert 'BRIDGE_PROBED_HANDLER" = "none"' in src
    assert "핸들러 등록을 건너뜁니다" in src
    # 반환값이 실패(1)와 구분되어야 그 분기가 성립한다.
    assert "return 2" in src


def test_launch_handler_bakes_the_same_args_as_the_installer():
    """브라우저 버튼이 띄우는 러너도 **같은 인자**를 받는다.

    여기만 빠지면 버튼으로 뜬 러너와 스크립트가 띄운 러너가 다르게 동작하고, 그 차이는
    화면에서 구분되지 않는다.
    """
    src = _SETUP_SH.read_text(encoding="utf-8")
    # 굽는 자리(핸들러 스크립트)와 이 실행(상주 기동) 둘 다 같은 변수를 써야 한다.
    assert src.count("$RUNNER_ARGS") >= 2, "핸들러 스크립트가 검증된 인자를 굽지 않는다"
    handler_body = src.split('cat > "$LAUNCH_SH"')[1].split("LAUNCHEOF")[1]
    assert "$RUNNER_ARGS" in handler_body, "핸들러가 띄우는 러너만 인자가 다르다"


# ── 경계 ②: 지시문이 "연결해줘" 로 되돌아가지 않는다 ─────────────────────────


def _load_launch_ns():
    """`compose_launch_commands` 구역만 격리 실행 (앱 의존 회피)."""
    src = _OAUTH_AS.read_text(encoding="utf-8")
    start = src.index("def compose_launch_commands")
    end = src.index("def compose_connect_handoff")
    ns = {"_ca_fingerprint": lambda: "aa" * 32,
          "_runner_checksum": lambda: "bb" * 32,
          "_setup_checksum": lambda n: ("cc" if n.endswith(".sh") else "dd") * 32}
    exec(src[start:end], ns)  # noqa: S102 — 대상 구역을 격리 실행
    return ns


def _launch(**kw):
    ns = _load_launch_ns()
    return ns["compose_launch_commands"](
        endpoint=kw.get("endpoint", "https://h.example/api/ai/mcp"),
        token=kw.get("token", "mat_TESTONLY"))  # verify-secret-allow: 테스트 더미


def test_probe_command_actually_contains_the_blanks():
    """「빈칸을 채워라」라고 말하면서 **채울 자리를 주지 않는** 형태를 막는다.

    구현 중 실제로 그랬다 — 지시문은 빈칸을 요구하는데 명령에는 `BRIDGE_PROBED_*` 가 없었다.
    그러면 AI 는 변수를 스스로 지어 붙이고, 오타 하나로 조용히 무시된다(셸은 모르는 변수를
    그냥 환경에 실어 보내고 스크립트는 읽지 않는다). 그 순간 이 설계가 없애려던 비결정성이
    되돌아온다.
    """
    probe = _launch()["probe"]
    # PY·AI·ARGS 는 빈 칸으로, HANDLER 는 기본값(`auto`)이 보이는 칸으로 준다 — 후자는
    # 「무엇을 넣을 수 있는지」가 값 자체에 드러나야 AI 가 `none` 을 고를 수 있다.
    for var in ("BRIDGE_PROBED_PY", "BRIDGE_PROBED_AI", "BRIDGE_PROBED_ARGS"):
        assert f"{var}=''" in probe, f"{var} 빈칸이 POSIX 명령에 없다"
        assert f"$env:{var}=''" in probe, f"{var} 빈칸이 Windows 명령에 없다"
    assert "BRIDGE_PROBED_HANDLER='auto'" in probe
    assert "$env:BRIDGE_PROBED_HANDLER='auto'" in probe


def test_default_command_has_no_blanks():
    """사람이 쓰는 기본 경로에는 빈칸을 넣지 않는다 — 채울 사람이 없는 칸은 노이즈다."""
    out = _launch()
    for key in ("posix", "windows"):
        assert "BRIDGE_PROBED_" not in out[key], f"{key} 에 빈칸이 새어 들어갔다"


def test_probe_and_default_run_the_same_script():
    """조사 경로와 기본 경로는 **같은 스크립트**를 부른다.

    이것이 P0-AC 와의 정합 지점이다 — 실행 경로가 하나이므로 「같은 입력이면 같은 결과」가
    유지되고, AI 가 바꾸는 것은 입력뿐이다. 다른 스크립트를 부르기 시작하면 그 순간
    "매번 다른 설치" 가 되돌아온다.
    """
    out = _launch()
    assert "sh bridge_setup.sh" in out["posix"]
    assert "sh bridge_setup.sh" in out["probe"]
    assert ".\\bridge_setup.ps1" in out["windows"]
    assert ".\\bridge_setup.ps1" in out["probe"]


def test_probe_instruction_forbids_delegating_the_trust_anchor():
    """대조·명령형태·판정은 **넘기지 않는다** — 지시문이 직접 금지한다.

    AI 가 "대조했습니다" 라고 말하는 것과 실제 대조는 다르고, 그 차이는 검증할 표면이 없어
    사후에도 드러나지 않는다.
    """
    probe = _launch()["probe"]
    assert "하지 말 것" in probe
    assert "네가 대조하고 넘어가기" in probe, "무결성 대조 위임 금지가 빠졌다"
    assert "명령을 다른 형태로 바꾸" in probe, "명령 형태 고정이 빠졌다"
    assert "판정은 스크립트의 종료 코드" in probe, "성공 판정 위임 금지가 빠졌다"


def test_probe_instruction_advertises_only_the_allowlisted_args():
    """지시문이 안내하는 인자 = 스크립트가 받는 allowlist.

    더 많이 안내하면 AI 가 그 값을 채우고 스크립트가 버려서, 사용자는 "왜 반영이 안 되지" 를
    겪는다(그리고 버린 사실은 stderr 경고로만 보인다).
    """
    probe = _launch()["probe"]
    sh = _SETUP_SH.read_text(encoding="utf-8")
    advertised = set(re.findall(r"--[a-z-]+", probe.split("허용:")[1].split("\n")[0]))
    for flag in advertised:
        assert flag in sh, f"지시문이 안내하는 {flag} 를 스크립트가 모른다"
    for flag, _why in _FORBIDDEN_RUNNER_ARGS:
        assert flag not in advertised, f"지시문이 위험 인자 {flag} 를 안내한다"


def test_probe_instruction_tells_the_ai_to_surface_dropped_values():
    """버려진 값을 사용자에게 전달하라고 지시한다.

    스크립트가 stderr 로 말해도 AI 가 삼키면 사용자에게 도달하지 않는다 — 도달 경로가
    두 겹이어야 끊기지 않는다.
    """
    probe = _launch()["probe"]
    assert "⚠" in probe and "버려졌다" in probe


def test_probe_instruction_covers_the_measured_wsl_windows_split():
    """실측된 조합(WSL 셸 + Windows 브라우저)에 무엇을 해야 하는지 적혀 있다.

    이 조합이 이 기능이 생긴 계기다. 지시문에 없으면 AI 는 그것을 알 방법이 없다.
    """
    probe = _launch()["probe"]
    assert "WSL" in probe and "Windows" in probe
    assert "none" in probe


# ── 두 스크립트가 같은 계약을 갖는가 ────────────────────────────────────────


@pytest.mark.parametrize("var", [
    "BRIDGE_PROBED_PY", "BRIDGE_PROBED_AI", "BRIDGE_PROBED_ARGS", "BRIDGE_PROBED_HANDLER",
])
def test_both_installers_accept_the_same_blanks(var):
    """POSIX 판과 Windows 판이 **같은 칸**을 받는다.

    두 파일이 갈리면 OS 마다 다른 연결 절차가 되고, 그것이 정확히 이 기능이 없애려는 마찰이다.
    """
    assert var in _SETUP_SH.read_text(encoding="utf-8"), f"sh 에 {var} 없음"
    assert var in _SETUP_PS1.read_text(encoding="utf-8"), f"ps1 에 {var} 없음"


@pytest.mark.parametrize("flag,_why", _FORBIDDEN_RUNNER_ARGS)
def test_windows_installer_has_the_same_allowlist(flag, _why):
    """ps1 의 allowlist 도 같은 축만 연다 — 정규식이 위험 인자를 잡아내지 못하면 안 된다."""
    ps1 = _SETUP_PS1.read_text(encoding="utf-8")
    allow = re.search(r"'\^--\((?P<body>[a-z|-]+)\)\$'", ps1)
    assert allow, "ps1 에서 allowlist 정규식을 찾지 못했다"
    names = set(allow.group("body").split("|"))
    assert flag.lstrip("-") not in names, f"ps1 allowlist 가 {flag} 를 허용한다"


def test_windows_installer_drops_to_stderr_too():
    """ps1 도 거른 사실을 stderr 로 낸다 (sh 와 같은 이유)."""
    ps1 = _SETUP_PS1.read_text(encoding="utf-8")
    assert "[Console]::Error.WriteLine" in ps1


def test_windows_installer_keeps_a_utf8_bom():
    """`.ps1` 은 **UTF-8 BOM 을 유지**해야 한다 (사용자 제보 2026-08-31).

    Windows PowerShell 5.1(윈도우 기본)은 BOM 없는 `.ps1` 을 UTF-8 이 아니라 **시스템 ANSI
    코드페이지**(한국어 윈도우면 CP949)로 읽는다. 그러면 한글 주석·메시지가 깨지고, 깨진
    바이트가 인접한 `'`·`)` 를 삼켜 **파서가 죽는다**:

        식에 닫는 ')'가 없습니다.

    실측(2026-08-31, 실 Windows): BOM 없음 → `ParseFile` 오류 **6건** / BOM 있음 → PARSE OK.
    디코딩도 함께 확인했다 — BOM 있으면 `U+B7EC`(러)가 그대로 읽히고, 없으면 그 문자가 없다.

    ⚠ **왜 바이트를 직접 보는가.** 아래 `pwsh` 파서 검사는 이 결함을 **원리적으로 못 본다** —
    PowerShell 7 은 BOM 없이도 UTF-8 로 읽으므로 통과한다. 게다가 그 테스트는 `pwsh` 미설치
    환경에서 늘 skip 이었다(=아무것도 검사하지 않았다). 실제로 이 결함은 그 게이트를 그대로
    통과해 사용자에게 도달했다 (§16.7 G11-b).
    """
    for f in (_SETUP_PS1,
              _WEB_SRC / "static" / "agent" / "bridge_setup.ps1"):
        head = f.read_bytes()[:3]
        assert head == b"\xef\xbb\xbf", (
            f"{f.name}: UTF-8 BOM 이 없다 — Windows PowerShell 5.1 이 CP949 로 읽어 파서가 죽는다 "
            f"(첫 3바이트={head!r})")


def test_generated_registration_ps1_gets_a_bom():
    """설치 중 **생성**하는 등록 PS1 에도 BOM 을 쓴다.

    그 생성물도 한글 주석을 담으므로 같은 위험이 있다. 지금 우연히 파싱되는 것에 기대지 않는다.
    """
    src = _SETUP_SH.read_text(encoding="utf-8")
    # BOM 을 쓰는 줄이 heredoc(`cat >> "$_ps1" <<PSEOF`)보다 **앞에** 있어야 한다 —
    # 뒤에 있으면 스크립트 본문 뒤에 BOM 이 붙어 아무 효과가 없다.
    i_bom = src.find(r"""printf '\357\273\277' > "$_ps1" """.rstrip())
    i_here = src.find('cat >> "$_ps1" <<PSEOF')
    assert i_bom != -1, "등록 PS1 생성 시 UTF-8 BOM 을 쓰지 않는다"
    assert i_here != -1, "등록 PS1 을 append(>>)로 이어 쓰지 않는다 — BOM 이 덮인다"
    assert i_bom < i_here, "BOM 을 본문 뒤에 썼다 — 선두가 아니면 효과가 없다"


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh 미설치 — 파서 검사 생략")
def test_windows_installer_parses():
    """ps1 이 실제로 파싱된다(문법 회귀 방지).

    ⚠ 이것은 **PowerShell 7** 검사다. 7 은 BOM 없는 UTF-8 도 정상으로 읽으므로 «윈도우 기본
    5.1 에서 깨지는» 클래스는 여기서 안 잡힌다 — 그 축은 위 `..._keeps_a_utf8_bom` 이 본다.
    """
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-Command",
         f"$e=$null;[System.Management.Automation.Language.Parser]::ParseFile("
         f"'{_SETUP_PS1}',[ref]$null,[ref]$e)|Out-Null;if($e){{exit 1}}"],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr


# ── 화면: 세 경로가 모두 도달하는가 ─────────────────────────────────────────


@pytest.mark.parametrize("html", [_INDEX_HTML, _AIC_HTML])
def test_both_screens_expose_the_third_path(html):
    """대화 화면 모달과 단독 페이지 **양쪽**에 조사 경로가 있다.

    한쪽만 고치면 어떤 사용자는 옛 안내를 받는다 — 이 프로젝트가 지시문을 서버에서 조립하는
    이유와 같다.
    """
    src = html.read_text(encoding="utf-8")
    assert "조사만 맡기기" in src, "조사 경로 블록이 없다"
    assert "똑같은 스크립트" in src, "설치·검증이 같은 스크립트라는 사실이 안 보인다"


@pytest.mark.parametrize("js,el", [(_MODAL_JS, "connectModalProbe"), (_AIC_JS, "probeText")])
def test_screens_hide_the_block_when_server_has_no_probe(js, el):
    """구 서버(probe 미지원)면 그 블록을 **감춘다**.

    빈 칸을 남기면 사용자는 복사할 것이 없는 자리를 보고 고장으로 읽는다.
    """
    src = js.read_text(encoding="utf-8")
    assert el in src, f"{el} 를 렌더하지 않는다"
    assert "hidden = !probe" in src, "probe 부재 시 감추는 처리가 없다"
