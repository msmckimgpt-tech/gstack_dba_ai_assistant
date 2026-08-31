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
    (bindir / "powershell.exe").write_text(textwrap.dedent(f"""\
        #!/bin/sh
        # 등록 실행(-File)과 사후검증(-Command)을 구분해 각각의 종료코드를 낸다.
        for a in "$@"; do
          case "$prev" in
            -File) cp "$a" "{tmp_path}/captured.ps1"; exit {ps_file_rc} ;;
            -Command) printf '%s' "$a" > "{tmp_path}/captured.cmd"; exit {ps_command_rc} ;;
          esac
          prev="$a"
        done
        exit 0
        """))
    for f in bindir.iterdir():
        f.chmod(0o755)
    return bindir


def _run_register(tmp_path: Path, *, distro: str | None = "StubDistro",
                  user: str = "tester", launch_name: str = "launch.sh",
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
        f'PATH="{bindir}:$PATH"\n'
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
    """쓰기가 성공해도 **조회로 확인**하기 전에는 등록됐다고 하지 않는다.

    이 절 전체가 「등록했다고 말했지만 브라우저는 못 본다」 를 고치는 것이다. 여기서 다시
    «썼으니 됐겠지» 로 끝내면 같은 종류의 거짓말을 한 층 아래에 만든다.
    """
    rc, why, _ = _run_register(tmp_path, ps_command_rc=1)   # 쓰기 OK, 사후검증 FAIL
    assert rc != 0, "사후검증이 실패했는데 등록 성공으로 처리했다"
    assert why, "사후검증 실패 사유가 비어 있다"


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
