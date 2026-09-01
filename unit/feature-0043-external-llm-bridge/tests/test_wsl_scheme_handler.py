"""feature-0043 — `[내 AI 실행]` 핸들러는 «브라우저가 도는 OS» 에 등록돼야 한다.

## 무엇이 잘못돼 있었나 (사용자 제보 2026-08-31)

    "'내 AI 실행' 을 통해 연결을 시도했지만, 연결이 진행되지 않는것으로 확인되었습니다."

라이브 실측으로 원인이 갈렸다:

  · Windows 레지스트리 `HKCU\\Software\\Classes\\mysql-ai-bridge` — **없음**
  · WSL `~/.local/share/applications/mysql-ai-bridge.desktop` — **있음**
  · 러너는 WSL 안에 설치돼 정상 동작한 이력이 있고, 브라우저는 Windows

설치 스크립트가 `uname` 으로 갈라 **이 셸이 도는 OS** 에 등록했기 때문이다. 그런데 그 버튼을
누르는 주체는 셸이 아니라 **브라우저**다. 등록은 성공했고, 스크립트는 "등록했습니다" 라고
말했고, 브라우저는 그것을 보지 못했다 — 그래서 사용자는 동작한다고 믿고 눌렀고 아무 일도
일어나지 않았다.

## 이 스위트가 잠그는 것

L1 WSL 감지 시 **Windows 쪽(HKCU)** 등록을 시도한다.
L2 등록 명령의 `-d`/`-u` 값에 **따옴표를 붙이지 않는다** — 실측된 함정이다(아래).
L3 표현할 수 없는 이름은 **조용히 생략하지 않고** 거절하고 사유를 남긴다.
L4 쓰기 성공을 등록 성공으로 갈음하지 않는다(사후검증).
L5 Windows 등록이 실패한 WSL 에서 **"등록했습니다" 라고 말하지 않는다**.
L6 정본과 서빙본이 같다 — 사용자가 내려받는 것은 서빙본이다.
L7 핸들러가 부르는 `launch.sh` 는 오류를 콘솔 깜빡임 속에 잃지 않는다.

## 실측된 함정 — `-d "Ubuntu"` (L2)

레지스트리 커맨드라인은 ShellExecute 가 wsl.exe 에 **원문 그대로** 넘기고, wsl.exe 의 자체
파서는 이 두 옵션의 값에서 따옴표를 벗기지 않는다. `-d "Ubuntu"` 는 이름이 `"Ubuntu"` 인
배포판을 찾다가 rc=-1 로 죽고, 그 오류는 즉시 닫히는 콘솔에 찍혀 사라진다 — 즉 **버튼을
눌러도 아무 일도 일어나지 않는** 형태가 되어 원래 결함과 화면상 구별되지 않는다.

    실측 (2026-08-31, 실 Windows + WSL Ubuntu):
      -d "Ubuntu" -u "claude-corp"  → 핸들러 무동작 (2회)
      -d Ubuntu   -u claude-corp    → 러너 기동 (3/3)

계약은 **동작으로** 잠근다 — 실제 `sh` 가 함수를 실행하고, 스텁 `powershell.exe` 가 받은
스크립트를 그대로 읽어 확인한다. 소스에 그 문자열이 있는지 보는 검사는 자기 주석이 자기
단언을 통과시킨다(AGENTS.md §16.7 G11-a).
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_SETUP_SH = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.sh"
_SETUP_PS1 = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.ps1"
_SERVED_SH = _UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "agent" / "bridge_setup.sh"
_SERVED_PS1 = _UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "agent" / "bridge_setup.ps1"


def _slice_functions(*names: str) -> str:
    """이름으로 셸 함수 정의만 떼어낸다.

    전체를 돌리면 네트워크·설치·프로세스 기동이 일어난다. 등록 로직은 순수하므로 함수만
    떼어 **실제 `sh` 에 먹인다** — 그러면 파싱·전개·인용까지 진짜로 검증된다.
    """
    lines = _SETUP_SH.read_text(encoding="utf-8").split("\n")
    out: list[str] = []
    for name in names:
        start = next((i for i, l in enumerate(lines) if l.startswith(f"{name}() {{")), None)
        assert start is not None, f"{name}() 정의를 찾지 못했다 — 슬라이스 경계가 깨졌다"
        end = next((j for j in range(start + 1, len(lines)) if lines[j] == "}"), None)
        assert end is not None, f"{name}() 의 끝을 찾지 못했다"
        out.extend(lines[start:end + 1])
        out.append("")
    return "\n".join(out)


def _stub_bin(tmp_path: Path, *, ps_file_rc: int = 0, ps_command_rc: int = 0,
              distro_listing: str | None = None) -> Path:
    """Windows 실행파일 스텁. `powershell.exe` 는 받은 스크립트를 통째로 갈무리한다."""
    bindir = tmp_path / "winbin"
    bindir.mkdir()
    listing = distro_listing if distro_listing is not None else "StubDistro\\n"
    (bindir / "wsl.exe").write_text(textwrap.dedent(f"""\
        #!/bin/sh
        echo wsl >> "{tmp_path}/launch-count.txt"
        # `-l -q` 만 흉내낸다 (배포판 목록). 실물처럼 UTF-16LE BOM 을 앞에 붙인다 —
        # BOM 을 걷어내지 않으면 정상 이름이 거절된다(codex P2 의 실패 모드).
        case "$1" in -l) printf '\\377\\376{listing}' ;; esac
        exit 0
        """))
    (bindir / "wslpath").write_text(textwrap.dedent("""\
        #!/bin/sh
        # `-w` 는 여기서 항등이다 — 스텁 powershell 이 같은 경로를 다시 읽어야 하기 때문.
        shift
        printf '%s' "$1"
        """))
    # ⚠ Windows exe **기동 횟수**를 남긴다 — 부하 시 회당 3초대라 횟수가 체감을 지배한다.
    launch_log = f"{tmp_path}/launch-count.txt"
    (bindir / "powershell.exe").write_text(textwrap.dedent(f"""\
        #!/bin/sh
        echo powershell >> "{launch_log}"
        # 등록 실행(-File)과 (구) 사후검증(-Command)을 구분해 각각의 종료코드를 낸다.
        for a in "$@"; do
          case "$prev" in
            -File) printf '%s' "$a" > "{tmp_path}/captured.file"; cp "$a" "{tmp_path}/captured.ps1"; exit {ps_file_rc} ;;
            -Command) printf '%s' "$a" > "{tmp_path}/captured.cmd"; exit {ps_command_rc} ;;
          esac
          prev="$a"
        done
        exit 0
        """))
    (bindir / "cmd.exe").write_text(textwrap.dedent(f"""\
        #!/bin/sh
        echo cmd >> "{launch_log}"
        printf 'C:\\NoTemp\\r\\n'
        """))
    for f in bindir.iterdir():
        f.chmod(0o755)
    return bindir


def _run_register(tmp_path: Path, *, distro: str | None = "StubDistro",
                  user: str = "tester", launch_name: str = "launch.sh",
                  extra_path: str | None = None,
                  **stub_kw) -> tuple[int, str, str]:
    """`register_handler_windows` 를 실제로 실행한다. 반환: (rc, HANDLER_WIN_WHY, 등록 커맨드라인)"""
    bindir = _stub_bin(tmp_path, **stub_kw)
    home = tmp_path / "bridgehome"
    home.mkdir()
    launch = home / launch_name
    launch.write_text("#!/bin/sh\nexit 0\n")
    script = tmp_path / "run.sh"
    script.write_text(
        "set -eu\n"
        f'PATH="{bindir}:{extra_path or ""}:$PATH"\n'
        # `id` 를 대체해 사용자명을 고정한다 — 테스트가 도는 계정 이름에 좌우되지 않게.
        f'id() {{ printf "{user}"; }}\n'
        + _slice_functions("is_wsl", "win_exe", "register_handler_windows")
        # ⚠ `LAUNCH_SH` 는 **env 로** 넘긴다 — 경로에 따옴표가 든 케이스(L9)를 스크립트에
        #   인라인 대입하면 하네스 자신이 문법 오류로 죽어 테스트가 결함을 못 본다.
        + f'\nBRIDGE_HOME="{home}"\n'
        'HANDLER_WIN_WHY=""\nHANDLER_WIN_DISTRO=""\n'
        'if register_handler_windows; then rc=0; else rc=$?; fi\n'
        'printf "RC=%s\\nWHY=%s\\n" "$rc" "$HANDLER_WIN_WHY"\n'
    )
    env = dict(os.environ, BRIDGE_FORCE_WSL="1", LAUNCH_SH=str(launch))
    if distro is None:
        env.pop("WSL_DISTRO_NAME", None)
    else:
        env["WSL_DISTRO_NAME"] = distro
    proc = subprocess.run(["sh", str(script)], capture_output=True, text=True,
                          env=env, timeout=60)
    out = proc.stdout
    rc = int(out.split("RC=")[1].split("\n")[0])
    why = out.split("WHY=")[1].split("\n")[0]
    captured = tmp_path / "captured.ps1"
    cmdline = ""
    if captured.exists():
        for line in captured.read_text(encoding="utf-8").split("\n"):
            if "shell\\open\\command" in line and "-Value" in line:
                cmdline = line
    return rc, why, cmdline


# ── L1·L2 ────────────────────────────────────────────────────────────────────

def test_l1_wsl_registers_on_the_windows_side(tmp_path: Path):
    """WSL 이면 Windows 쪽(HKCU)에 등록한다 — 브라우저가 보는 곳이 거기다."""
    rc, why, cmdline = _run_register(tmp_path)
    assert rc == 0, f"Windows 등록이 실패했다: {why}"
    captured = (tmp_path / "captured.ps1").read_text(encoding="utf-8")
    assert "HKCU:\\Software\\Classes\\mysql-ai-bridge" in captured, "HKCU 스킴 키를 만들지 않는다"
    assert "URL Protocol" in captured, "`URL Protocol` 값이 없으면 크롬이 스킴으로 인식하지 않는다"
    assert "wsl.exe" in cmdline, "핸들러가 WSL 러너를 되부르지 않는다"


def test_l2_distro_and_user_are_passed_unquoted(tmp_path: Path):
    """`-d`/`-u` 값에 따옴표를 붙이면 wsl.exe 가 이름의 일부로 읽는다 (실측 함정).

    이 단언이 무너지면 등록은 «성공» 하고 버튼은 무동작이 된다 — 원래 결함과 같은 모양이라
    화면으로는 구별되지 않는다. 그래서 여기서 잠근다.
    """
    _rc, _why, cmdline = _run_register(tmp_path, distro="StubDistro", user="tester")
    assert "-d StubDistro" in cmdline, f"배포판이 넘어가지 않는다: {cmdline}"
    assert "-u tester" in cmdline, f"사용자가 넘어가지 않는다: {cmdline}"
    assert '-d "' not in cmdline, f'`-d` 값이 따옴표로 감싸였다 — wsl.exe 가 못 찾는다: {cmdline}'
    assert '-u "' not in cmdline, f'`-u` 값이 따옴표로 감싸였다 — wsl.exe 가 못 찾는다: {cmdline}'


# ── L3 ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("distro", ["My Ubuntu", 'Ub"untu', "Ubuntu;rm"])
def test_l3_unrepresentable_distro_is_refused_with_a_reason(tmp_path: Path, distro: str):
    """표현할 수 없는 이름은 **조용히 생략하지 않는다**.

    `-d` 를 말없이 빼면 기본 배포판이 뜬다 — 배포판이 여럿인 머신에서 엉뚱한 쪽에 러너가
    뜨고, 사용자에게는 "실행했다는데 여전히 대기 안 함" 으로만 보인다.
    """
    rc, why, _cmdline = _run_register(tmp_path, distro=distro)
    assert rc != 0, "표현 불가한 이름인데 등록을 성공으로 처리했다"
    assert why, "거절했는데 사유가 비어 있다 — 사용자는 무엇을 고칠지 모른다"
    assert distro in why, f"사유가 어느 이름 때문인지 말하지 않는다: {why!r}"


def test_l3b_unsafe_user_is_refused(tmp_path: Path):
    """사용자명도 같다 — 기본 사용자로 뜨면 `$HOME` 이 달라 러너가 설치물을 못 찾는다."""
    rc, why, _cmdline = _run_register(tmp_path, user="odd user")
    assert rc != 0 and why, f"이상한 사용자명을 통과시켰다 (rc={rc}, why={why!r})"


# ── L4 ───────────────────────────────────────────────────────────────────────

def test_l4_write_success_is_not_registration_success(tmp_path: Path):
    """쓰기가 성공해도 **되읽어 대조**하기 전에는 등록됐다고 하지 않는다.

    이 절 전체가 「등록했다고 말했지만 브라우저는 못 본다」 를 고치는 것이다. 여기서 다시
    «썼으니 됐겠지» 로 끝내면 같은 종류의 거짓말을 한 층 아래에 만든다.

    ⚠ 사후검증은 **PS1 안에서** 끝난다(2026-08-31 속도 개선). 종전엔 PowerShell 을 한 번 더
    띄워 `Test-Path` 했는데, 같은 보장을 두 번 하면서 Windows 프로세스 기동(부하 시 3초대)을
    하나 더 썼다. 보장은 그대로, 호출만 줄였다 — 그래서 이 테스트는 **PS1 이 되읽고 던지는지**
    를 본다.
    """
    captured = None
    rc, why, _ = _run_register(tmp_path, ps_file_rc=1)   # 등록 실행(=쓰기+대조)이 실패
    assert rc != 0, "등록·대조가 실패했는데 성공으로 처리했다"
    assert why, "실패 사유가 비어 있다"
    del captured


def test_l4b_write_failure_is_reported(tmp_path: Path):
    rc, why, _ = _run_register(tmp_path, ps_file_rc=1)
    assert rc != 0 and why, f"레지스트리 쓰기 실패를 삼켰다 (rc={rc}, why={why!r})"


# ── L5 ───────────────────────────────────────────────────────────────────────

def test_l5_failed_windows_registration_does_not_claim_success():
    """WSL 인데 Windows 등록만 실패한 상태에서 «등록했습니다» 라고 말하면 결함이 재생산된다.

    보고 구간을 실제로 실행한다 — 분기가 실제로 그 문구를 내는지는 조건을 넣어 돌려 봐야 안다.
    """
    src = _SETUP_SH.read_text(encoding="utf-8")
    block = src.split("register_handler && _handler_rc=0 || _handler_rc=$?")[1]
    block = block.split("\n# ── 4.")[0]
    script = (
        "set -eu\n"
        'say() { printf "%s\\n" "$1"; }\n'
        '_handler_rc=3\nHANDLER_WIN="fail"\nHANDLER_LINUX="ok"\n'
        'HANDLER_WIN_WHY="테스트 사유"\nHANDLER_WIN_DISTRO=""\n'
        "_handler_rc=3\n" + block
    )
    proc = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=30)
    out = proc.stdout
    assert "등록했습니다" not in out, f"실패했는데 등록 성공으로 안내한다:\n{out}"
    assert "테스트 사유" in out, f"실패 사유를 사용자에게 전달하지 않는다:\n{out}"
    assert "동작하지 않습니다" in out, f"버튼이 동작하지 않는다는 사실을 말하지 않는다:\n{out}"


def test_l5b_windows_success_says_where_it_registered():
    """성공 문구도 사실보다 넓어지면 안 된다 — 어디에 등록했는지 말한다."""
    src = _SETUP_SH.read_text(encoding="utf-8")
    block = src.split("register_handler && _handler_rc=0 || _handler_rc=$?")[1].split("\n# ── 4.")[0]
    script = (
        "set -eu\n"
        'say() { printf "%s\\n" "$1"; }\n'
        '_handler_rc=0\nHANDLER_WIN="ok"\nHANDLER_LINUX="ok"\n'
        'HANDLER_WIN_WHY=""\nHANDLER_WIN_DISTRO="StubDistro"\n' + block
    )
    proc = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=30)
    assert "Windows" in proc.stdout, f"어디에 등록했는지 말하지 않는다:\n{proc.stdout}"
    assert "StubDistro" in proc.stdout, f"어느 배포판을 띄우는지 말하지 않는다:\n{proc.stdout}"


# ── L6 ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("src,served", [(_SETUP_SH, _SERVED_SH), (_SETUP_PS1, _SERVED_PS1)])
def test_l6_served_copy_matches_source(src: Path, served: Path):
    """사용자가 내려받는 것은 **서빙본**이고 체크섬도 서빙본에서 계산된다.

    둘이 갈리면 체크섬은 맞는데 내용은 옛것인 상태가 되고, 그 상태는 어떤 게이트도 잡지
    않는다 — 대조가 «맞다» 고 말하기 때문이다.
    """
    assert src.read_bytes() == served.read_bytes(), (
        f"{src.name}: 정본과 서빙본이 다르다 — 배포되는 것은 서빙본이다")


# ── L7 ───────────────────────────────────────────────────────────────────────

def test_l7_launch_script_reports_bad_token_instead_of_vanishing(tmp_path: Path):
    """핸들러가 부르는 `launch.sh` 는 오류를 말하고 끝난다 (콘솔 깜빡임 속에 잃지 않는다).

    생성된 스크립트를 실제로 실행한다. tty 가 없으므로 붙잡아 두지 않고 즉시 끝나야 한다 —
    테스트가 20초 멈추면 그 홀드가 tty 조건에 걸려 있지 않다는 뜻이다.
    """
    src = _SETUP_SH.read_text(encoding="utf-8")
    body = src.split('cat > "$LAUNCH_SH" <<LAUNCHEOF\n')[1].split("\nLAUNCHEOF")[0]
    # 설치 시점에 전개되는 자리만 채운다 (`$PY`·`$BRIDGE_BASE`·`$RUNNER_ARGS`).
    body = (body.replace("$PY", "true").replace("$BRIDGE_BASE", "https://example.test")
                .replace("$RUNNER_ARGS", "").replace("\\$", "$").replace("\\\\\n", "\n"))
    script = tmp_path / "launch.sh"
    script.write_text(body)
    script.chmod(0o755)
    proc = subprocess.run(["sh", str(script), "mysql-ai-bridge://start?token=NOT_A_MAT_TOKEN"],
                          capture_output=True, text=True, timeout=25)
    assert proc.returncode == 2, f"형식이 아닌 토큰을 걸러내지 못했다 (rc={proc.returncode})"
    assert "형식" in proc.stderr, f"무엇이 잘못됐는지 말하지 않는다: {proc.stderr!r}"


# ── codex 적대 리뷰 반영 (REV-20260831T124500) ───────────────────────────────

def test_l8_distro_is_not_guessed_from_the_list(tmp_path: Path):
    """`wsl.exe -l -q` **첫 줄 = 현재 배포판** 은 성립하지 않는다 (codex P1-4).

    배포판이 여럿인 머신에서 첫 줄을 현재 셸로 가정하면, 핸들러가 **엉뚱한 배포판의**
    `launch.sh` 를 부른다 — 그 경로엔 파일이 없으니 클릭해도 아무 일이 없고, 설치는
    성공으로 표시된다. 이 절이 고치는 「조용한 무동작」 이 형태만 바꿔 되돌아온다.
    """
    rc, why, _ = _run_register(tmp_path, distro=None,
                               distro_listing="Ubuntu\\nArch\\nDebian\\n")
    assert rc != 0, "후보가 여럿인데 첫 줄을 현재 배포판으로 간주했다"
    assert why, "확정 실패 사유가 비어 있다"


def test_l8b_single_distro_fallback_still_works(tmp_path: Path):
    """배포판이 **하나뿐**이면 그것이 현재 셸일 수밖에 없다 — 그때는 폴백을 쓴다.

    함께: 목록에 UTF-16LE BOM 이 붙어 와도 이름을 읽어야 한다(codex P2-5).
    """
    rc, why, cmdline = _run_register(tmp_path, distro=None, distro_listing="OnlyOne\\n")
    assert rc == 0, f"단일 배포판 폴백이 죽었다: {why}"
    assert "-d OnlyOne" in cmdline, f"BOM 을 걷어내지 못했다: {cmdline!r}"


def test_l9_broken_quoting_in_path_is_refused(tmp_path: Path):
    """경로의 큰따옴표는 커맨드라인 인용을 깨뜨린다 — 등록은 되고 클릭은 무동작 (codex P2-6)."""
    rc, why, _ = _run_register(tmp_path, launch_name='la"unch.sh')
    assert rc != 0 and why, f"인용을 깨뜨리는 경로를 통과시켰다 (rc={rc}, why={why!r})"


def test_l10_registration_reads_back_and_compares(tmp_path: Path):
    """「키가 있다」는 「우리가 쓴 값이 있다」가 아니다 — 되읽어 대조한다 (codex P2-6)."""
    _rc, _why, _cmd = _run_register(tmp_path)
    captured = (tmp_path / "captured.ps1").read_text(encoding="utf-8")
    assert "GetValue('')" in captured, "등록 후 값을 되읽지 않는다"
    assert "-ne" in captured and "throw" in captured, "되읽은 값을 대조해 실패시키지 않는다"


def test_l11_xdg_step_failures_are_not_swallowed():
    """`xdg-mime` 만 보면 desktop 파일 쓰기 실패가 성공으로 보고된다 (codex P1-3).

    실제로 `cat >` 를 실패시키고(대상 경로를 디렉토리로 만든다) 분기가 `fail` 로 떨어지는지
    본다 — 소스에 검사 코드가 있는지가 아니라 **결과가 갈리는지**를 확인한다.
    """
    import tempfile
    src = _SETUP_SH.read_text(encoding="utf-8")
    body = src.split("    Linux)\n", 1)[1].split("\n      ;;", 1)[0]
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        # 쓰기 대상 경로를 **디렉토리**로 만들어 `cat >` 를 실패시킨다.
        (home / ".local" / "share" / "applications" / "mysql-ai-bridge.desktop").mkdir(parents=True)
        stub = home / "bin"
        stub.mkdir()
        (stub / "xdg-mime").write_text("#!/bin/sh\nexit 0\n")          # 이쪽은 성공시킨다
        (stub / "update-desktop-database").write_text("#!/bin/sh\nexit 0\n")
        for f in stub.iterdir():
            f.chmod(0o755)
        script = (
            "set -eu\n"
            f'PATH="{stub}:$PATH"\nHOME="{home}"\n'
            'is_wsl() { return 1; }\n'
            f'LAUNCH_SH="{home}/launch.sh"\nHANDLER_WIN="na"\nHANDLER_LINUX="na"\n'
            "run() {\n" + body + "\n}\nrun || true\n"
            'printf "HANDLER_LINUX=%s\\n" "$HANDLER_LINUX"\n'
        )
        proc = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=30)
        assert "HANDLER_LINUX=fail" in proc.stdout, (
            f"desktop 파일 쓰기가 실패했는데 등록 성공으로 처리했다:\n{proc.stdout}\n{proc.stderr}")


# ── 사용자 재제보 반영 (2026-08-31 2차) ──────────────────────────────────────

def _render_launch(tmp_path: Path) -> Path:
    """설치 스크립트의 heredoc 을 **실제 sh 로 전개해** `launch.sh` 를 만든다.

    파이썬 문자열 치환으로 흉내내면 이스케이프가 실물과 갈리고(실측: `\\n` 이 두 겹으로
    남았다), 그러면 테스트가 «실물이 아닌 것» 을 검사하게 된다. 생성 자체를 셸에 맡긴다.
    """
    src = _SETUP_SH.read_text(encoding="utf-8")
    blk = src.split('cat > "$LAUNCH_SH" <<LAUNCHEOF\n')[1].split("\nLAUNCHEOF")[0]
    out = tmp_path / "launch.sh"
    gen = tmp_path / "gen.sh"
    gen.write_text(
        "set -eu\nPY=python3\nBRIDGE_BASE='https://example.test'\nRUNNER_ARGS=''\n"
        f'LAUNCH_SH="{out}"\n'
        'cat > "$LAUNCH_SH" <<LAUNCHEOF\n' + blk + "\nLAUNCHEOF\n"
    )
    r = subprocess.run(["sh", str(gen)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"launch.sh 생성 실패: {r.stderr}"
    out.chmod(0o755)
    return out


def _stub_runner(tmp_path: Path, resume_body: str) -> Path:
    """러너·pkill 스텁. `--check` 는 통과시키고 `--resume` 거동만 시나리오로 바꾼다."""
    bh = tmp_path / "home" / ".mysql-ai-bridge"
    bh.mkdir(parents=True, exist_ok=True)
    (bh / "bridge_agent.py").write_text("#!/bin/sh\nexit 0\n")
    (bh / "rootCA.crt").write_text("stub\n")
    b = tmp_path / "bin"
    b.mkdir(exist_ok=True)
    (b / "python3").write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        '  [ "$a" = "--check" ] && exit 0\n'
        f'  [ "$a" = "--resume" ] && {{ {resume_body} }}\n'
        "done\nexit 0\n"
    )
    (b / "pkill").write_text("#!/bin/sh\nexit 0\n")   # 실제 프로세스를 죽이지 않는다
    for f in b.iterdir():
        f.chmod(0o755)
    return b


def test_l12_launcher_waits_until_the_runner_is_established(tmp_path: Path):
    """`wsl.exe` 는 **부모가 끝나는 순간 자식까지 죽인다** (실측 2026-08-31).

    핸들러가 부르는 `launch.sh` 가 러너를 띄우고 곧바로 끝나면, WSL 이 세션을 정리하면서
    그 러너를 함께 거둬간다. 증상은 앞선 결함과 똑같은 «아무 일도 일어나지 않음» 이고,
    그 앞의 `pkill` 은 이미 실행됐으므로 **돌던 러너까지 사라져 누르기 전보다 나빠진다.**

    실측: `nohup` · `setsid` · stdin 차단 **셋 다 막지 못했고**, 부모가 3초 이상 살아 있는
    경우에만 자식이 살아남았다. 그래서 계약은 「부모가 자식이 자리잡을 때까지 기다린다」다.
    """
    import time
    launch = _render_launch(tmp_path)
    b = _stub_runner(tmp_path, 'sleep 2; echo "[bridge] AI = stub"; sleep 60; exit 0;')
    t0 = time.time()
    proc = subprocess.run(["sh", str(launch), "mysql-ai-bridge://start/?token=mat_STUBTOKEN"],
                          capture_output=True, text=True, timeout=60,
                          env=dict(os.environ, HOME=str(tmp_path / "home"),
                                   PATH=f"{b}:{os.environ['PATH']}"))
    elapsed = time.time() - t0
    assert proc.returncode == 0, f"정상 경로인데 실패: rc={proc.returncode} {proc.stderr!r}"
    assert elapsed >= 3, (
        f"부모가 {elapsed:.1f}초만에 끝났다 — wsl.exe 가 자식을 거둬갈 창을 그대로 둔 것이다")
    assert "대기 중" in proc.stdout, f"실행 결과를 말하지 않는다: {proc.stdout!r}"


def test_l13_launcher_reports_when_the_runner_dies(tmp_path: Path):
    """러너가 바로 죽으면 **그 사실을 말한다** — 조용히 성공으로 끝내지 않는다."""
    launch = _render_launch(tmp_path)
    b = _stub_runner(tmp_path, "exit 9;")
    proc = subprocess.run(["sh", str(launch), "mysql-ai-bridge://start/?token=mat_STUBTOKEN"],
                          capture_output=True, text=True, timeout=60,
                          env=dict(os.environ, HOME=str(tmp_path / "home"),
                                   PATH=f"{b}:{os.environ['PATH']}"))
    assert proc.returncode != 0, "러너가 죽었는데 성공으로 끝냈다"
    assert "종료" in proc.stderr or "로그" in proc.stderr, f"사유를 말하지 않는다: {proc.stderr!r}"


# ── 속도·타임스탬프 (사용자 요청 2026-08-31 3차) ─────────────────────────────

def test_l14_ps1_goes_to_a_windows_local_dir_not_a_wsl_unc_path(tmp_path: Path):
    """등록 스크립트는 **Windows 로컬 디스크**에 둔다.

    `powershell -File` 에 WSL 경로(`\\\\wsl.localhost\\…`)를 주면 UNC 해석이 걸려 **80초**가
    든다(실측). 같은 스크립트를 Windows 로컬 경로로 주면 0.4초다 — 200배 차이이고, 사용자에게는
    "러너 체크섬 일치" 뒤로 설치가 멈춘 것처럼 보인다(제보 2026-08-31).

    스텁 powershell 이 받은 `-File` 인자를 그대로 갈무리해, 그 경로가 WSL 홈이 아니라
    Windows 임시 폴더인지 본다.
    """
    win_tmp = tmp_path / "mnt" / "c" / "Users" / "tester" / "AppData" / "Local" / "Temp"
    win_tmp.mkdir(parents=True)
    # PATH 에 WindowsApps 경로를 심어 «Windows 호출 없이» 프로필을 찾게 한다(빠른 경로).
    fake_path = str(win_tmp.parent.parent / "Microsoft" / "WindowsApps")
    (win_tmp.parent.parent / "Microsoft" / "WindowsApps").mkdir(parents=True)
    rc, why, _ = _run_register(tmp_path, extra_path=fake_path)
    assert rc == 0, f"등록 실패: {why}"
    used = (tmp_path / "captured.file").read_text(encoding="utf-8").strip()
    assert str(win_tmp) in used, f"PS1 을 Windows 로컬 폴더에 두지 않았다: {used!r}"
    assert ".mysql-ai-bridge" not in used, f"WSL 홈(UNC 경로)에 두었다 — 80초 경로다: {used!r}"


def test_l15_windows_process_launches_are_minimised(tmp_path: Path):
    """Windows 프로세스 기동 **횟수**를 센다 — 부하 시 exe 하나가 3초대다(실측).

    빠른 경로(PATH 에서 프로필을 얻고 `WSL_DISTRO_NAME` 이 있음)에서는 **등록 실행 1회**만
    있어야 한다. 종전 3회(TEMP 조회 · 등록 · 별도 `Test-Path` 검증)가 체감 지연의 본체였다.
    """
    win_tmp = tmp_path / "mnt" / "c" / "Users" / "tester" / "AppData" / "Local" / "Temp"
    win_tmp.mkdir(parents=True)
    apps = win_tmp.parent.parent / "Microsoft" / "WindowsApps"
    apps.mkdir(parents=True)
    rc, why, _ = _run_register(tmp_path, extra_path=str(apps))
    assert rc == 0, f"등록 실패: {why}"
    launches = (tmp_path / "launch-count.txt").read_text(encoding="utf-8").strip().split("\n")
    launches = [l for l in launches if l]
    assert len(launches) == 1, (
        f"Windows 프로세스를 {len(launches)}회 띄웠다(기대 1) — 부하 시 회당 3초다: {launches}")


def test_l16_logs_carry_a_timestamp():
    """설치·러너 로그에 **시각**이 붙는다 (사용자 요청 2026-08-31).

    시각이 없으면 「어느 단계가 오래 걸리는지」를 로그로 읽을 수 없다 — 실제로 이번 지연도
    사용자 제보를 받고서야 단계별로 재 봤다. 실행해서 확인한다(문자열 검사가 아니라).
    """
    import re
    src = _SETUP_SH.read_text(encoding="utf-8")
    # 설치 로그: say/die/drop 정의 구간만 떼어 실제로 출력시킨다.
    defs = "\n".join(l for l in src.split("\n")
                     if l.startswith(("_ts()", "die()", "say()", "drop()")))
    proc = subprocess.run(["sh", "-c", defs + '\nsay "러너 체크섬 일치."\n'],
                          capture_output=True, text=True, timeout=20)
    assert re.search(r"\[bridge-setup \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", proc.stdout), \
        f"설치 로그에 시각이 없다: {proc.stdout!r}"

    # 러너 로그: 정본 `_log` 를 **모듈째 불러** 그대로 실행한다.
    #
    # ⚠ 종전에는 소스에서 `_log` 정의를 정규식으로 오려 내 `exec` 했다. 그 방식은 함수의
    #   **모양**에 묶여 있어서, 로그가 구조화되며 시그니처가 바뀌자(TASK-20260901T163000)
    #   「시각이 없다」가 아니라 「정의를 찾지 못했다」로 깨졌다 — 검사하려던 성질(시각)과
    #   무관한 이유로 실패하는 검사는 신호가 아니라 소음이다. 실물을 부른다.
    agent_dir = _UNIT / "feature-0043-external-llm-bridge" / "src"
    env = {**os.environ, "PYTHONPATH": str(agent_dir),
           "BRIDGE_LOG_FILE": "-"}   # 이 검사는 stderr 만 본다 — 파일은 남기지 않는다
    got = subprocess.run(
        [sys.executable, "-c", "import bridge_agent as B; B._log('AI = claude')"],
        capture_output=True, text=True, timeout=60, env=env).stderr
    # 형식: `[bridge <지역시각><오프셋>] <레벨> <사건코드> | <문장>`
    assert re.match(
        r"\[bridge \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[+-]\d{4}\] \w+\s+\S+ \| AI = claude",
        got), f"러너 로그에 시각이 없다: {got!r}"
