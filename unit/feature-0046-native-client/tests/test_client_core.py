"""네이티브 클라이언트 코어 — 계약 잠금 (ROADMAP ITEM-08).

## 이 스위트가 지키는 것

1. **§0.1 ToS 경계** — 토큰을 읽지도 저장하지도 중계하지도 않는다. 로그인은 벤더 공식 명령의
   **대행 실행**뿐이다. 이 선을 넘는 코드가 들어오면 여기서 실패한다.
2. **무결성 계약** — CA 지문은 **DER** 기준(파일 해시가 아니다), 불일치는 **중단**이지 경고가 아니다.
3. **런타임 목록 정본** — 러너 `_RUNTIME_SPECS` 와 일치. 넓으면 「설치 통과 후 런타임 실패」가
   재발한다(feature-0043 P0-Z6.1-a).
4. **연결 축과 AI 축 분리** — `--check` 종료코드 4 는 「AI 없음」이지 「연결 실패」가 아니다.

GUI(`gui.py`)는 tkinter 를 import 하므로 헤드리스에서 돌지 않는다. 그래서 로직이 `core` 에 있고
이 스위트가 **실제 동작을 구동**한다(소스 문자열 검사가 아니라).
"""

from __future__ import annotations

import base64
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from client import core  # noqa: E402

_RUNNER_SPECS = (Path(__file__).resolve().parents[2]
                 / "feature-0043-external-llm-bridge" / "src" / "agent" / "runtimes.py")


# ── 1. ToS 경계 (§0.1) ─────────────────────────────────────────────────────────

def _code(path: Path) -> str:
    """주석·docstring 을 제외한 실행 코드. 자기 주석이 자기 단언을 통과시키지 않게(§16.7 G11-a)."""
    src = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines()
                    if not l.lstrip().startswith("#"))
    return re.sub(r'"""[\s\S]*?"""', "", src)


def test_client_never_touches_vendor_credentials():
    """**이 프로젝트에서 가장 비싼 실수를 막는 테스트다.**

    2026년에 Anthropic·Google 이 구독 OAuth 의 제3자 사용을 차단했고 Google 은 **유료 구독자
    계정을 정지**했다. 클라이언트가 벤더 자격증명 파일·키체인을 읽는 코드가 들어오면 사용자
    계정이 정지될 수 있다 — 그래서 「안 한다」를 검사한다.
    """
    code = _code(_SRC / "client" / "core.py") + _code(_SRC / "client" / "gui.py")
    forbidden = (
        ".credentials.json", "auth.json", "keychain", "Keychain",
        "CLAUDE_CODE_OAUTH", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
        "access_token", "refresh_token", "id_token",
    )
    for bad in forbidden:
        assert bad not in code, (
            f"클라이언트가 벤더 자격증명(`{bad}`)에 닿는다 — §0.1 ToS 경계 위반. "
            f"로그인은 «대행 실행» 이어야 한다(벤더 명령을 띄우고 종료코드만 본다).")


def test_login_only_runs_vendor_official_commands():
    """로그인 경로가 실행하는 것이 **벤더 공식 명령뿐**임을 동작으로 확인한다."""
    seen: list[list[str]] = []

    def fake_run(argv, **kw):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    orig_run, orig_which = subprocess.run, core.which_runtime
    subprocess.run = fake_run
    core.which_runtime = lambda n: f"/fake/{n}"
    try:
        ok, _ = core.login("claude")
    finally:
        subprocess.run, core.which_runtime = orig_run, orig_which

    assert ok
    assert seen == [["/fake/claude", "auth", "login"]], (
        f"로그인이 벤더 공식 명령 외의 것을 실행했다: {seen}")


def test_login_refuses_runtime_without_known_command():
    """모르는 로그인 절차를 **지어내지 않는다** — gemini 는 SPIKE-02 에서 미실측이다."""
    orig = core.which_runtime
    core.which_runtime = lambda n: f"/fake/{n}"
    try:
        ok, msg = core.login("gemini")
    finally:
        core.which_runtime = orig
    assert ok is False
    assert "직접 로그인" in msg, "커버리지를 과장하지 않는 안내여야 한다"


# ── 2. 무결성 계약 ─────────────────────────────────────────────────────────────

def _self_signed_der() -> bytes:
    return b"\x30\x82\x01\x0a" + b"fake-der-body" * 7


def test_ca_fingerprint_is_der_not_file_hash():
    """⚠ **PEM 파일 해시와 DER 지문은 다르다.**

    초기 설치 스크립트가 이 둘을 혼동해 지문이 **항상 불일치**했다(feature-0006 REQ-0286).
    같은 함정을 반복하지 않는지 PEM 과 그 DER 를 같은 값으로 접는지로 확인한다.
    """
    der = _self_signed_der()
    pem = (b"-----BEGIN CERTIFICATE-----\n"
           + base64.encodebytes(der)
           + b"-----END CERTIFICATE-----\n")
    assert core.ca_fingerprint(pem) == core.ca_fingerprint(der) == hashlib.sha256(der).hexdigest()
    assert core.ca_fingerprint(pem) != hashlib.sha256(pem).hexdigest(), (
        "PEM **파일** 해시를 지문으로 쓰고 있다 — 서버가 주는 DER 지문과 영원히 불일치한다")


def test_mismatched_ca_stops_and_does_not_write(tmp_path, monkeypatch):
    """대조 실패는 **중단**이다. 「계속 진행」 선택지가 없고, 파일도 남기지 않는다."""
    plan = core.ConnectPlan(base="https://h", token="t",
                            ca_sha256="0" * 64, home=tmp_path / "h")
    monkeypatch.setattr(core, "fetch", lambda *a, **k: _self_signed_der())
    with pytest.raises(core.IntegrityError):
        core.install_ca(plan)
    assert not (plan.home / "rootCA.crt").exists(), "대조 실패인데 CA 를 디스크에 남겼다"


def test_mismatched_runner_stops(tmp_path, monkeypatch):
    plan = core.ConnectPlan(base="https://h", token="t",
                            agent_sha256="f" * 64, home=tmp_path / "h")
    plan.home.mkdir(parents=True)
    monkeypatch.setattr(core, "fetch", lambda *a, **k: b"print('runner')")
    with pytest.raises(core.IntegrityError):
        core.install_runner(plan, plan.home / "rootCA.crt")
    assert not (plan.home / "bridge_agent.py").exists()


def test_matching_checksums_write_the_files(tmp_path, monkeypatch):
    """대조가 **맞을 때는 통과한다** — 항상 거부하면 테스트는 통과하고 제품은 못 쓴다."""
    der = _self_signed_der()
    body = b"print('runner')"
    plan = core.ConnectPlan(base="https://h", token="t",
                            ca_sha256=core.ca_fingerprint(der),
                            agent_sha256=hashlib.sha256(body).hexdigest(),
                            home=tmp_path / "h")
    monkeypatch.setattr(core, "fetch", lambda url, **k: der if "rootCA" in url else body)
    ca = core.install_ca(plan)
    runner = core.install_runner(plan, ca)
    assert ca.read_bytes() == der and runner.read_bytes() == body


def test_ca_is_fetched_over_plain_http_by_design(tmp_path, monkeypatch):
    """CA 는 **평문 HTTP** 로 받는다 — 부트스트랩 데드락 때문이고, 지문 대조가 그 위험을 덮는다.

    누가 「https 가 안전하니 바꾸자」고 고치면 CA 없는 머신이 CA 를 못 받는 상태가 된다.
    """
    der = _self_signed_der()
    urls: list[str] = []
    monkeypatch.setattr(core, "fetch", lambda url, **k: (urls.append(url), der)[1])
    plan = core.ConnectPlan(base="https://host.example", token="t",
                            ca_sha256=core.ca_fingerprint(der), home=tmp_path / "h")
    core.install_ca(plan)
    assert urls and urls[0].startswith("http://"), f"CA 를 평문으로 받지 않는다: {urls}"
    assert urls[0].endswith("/trust/rootCA.crt")


# ── 3. 런타임 목록 정본 동기화 ──────────────────────────────────────────────────

def test_client_runtimes_match_the_runner_canon():
    """클라이언트 목록 == 러너 `_RUNTIME_SPECS`.

    넓으면 「설치는 통과하고 런타임에서 실패」한다 — feature-0043 P0-Z6.1-a 가 겪은 그 결함을
    새 컴포넌트가 물려받지 않게 한다(`reuse-inherits-defects`).
    """
    import ast
    tree = ast.parse(_RUNNER_SPECS.read_text(encoding="utf-8"))
    canon: set[str] = set()
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(t, ast.Name) and t.id == "_RUNTIME_SPECS" for t in targets):
            canon = {k.value for k in node.value.keys}
            break
    assert canon, "러너 정본을 읽지 못했다"
    assert set(core.RUNTIMES) == canon, (
        f"클라이언트 런타임 목록이 러너 정본과 다르다.\n"
        f"  정본에만: {sorted(canon - set(core.RUNTIMES))}\n"
        f"  클라이언트에만: {sorted(set(core.RUNTIMES) - canon)}")


# ── 4. 감지 · 상태 판정 ────────────────────────────────────────────────────────

def test_windowsapps_stub_is_rejected():
    """Store 앱 실행 별칭 스텁은 「있다」로 세지 않는다 — 실행하면 Store 를 연다."""
    assert core._is_rejected(r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\claude.exe")
    assert not core._is_rejected(r"C:\Users\x\.local\bin\claude.exe")


def test_probe_reads_claude_json_status(monkeypatch):
    """claude 는 JSON 을 낸다 — 계정까지 보여 줄 수 있다 (SPIKE-02 실측 형태)."""
    monkeypatch.setattr(core, "which_runtime", lambda n: "/fake/claude" if n == "claude" else None)
    monkeypatch.setattr(core, "_run", lambda *a, **k:
                        (0, '{"loggedIn": true, "email": "u@example.com"}'))
    st = core.probe_runtime("claude")
    assert st.installed and st.logged_in is True and "u@example.com" in st.detail


def test_probe_marks_not_logged_in(monkeypatch):
    monkeypatch.setattr(core, "which_runtime", lambda n: "/fake/claude")
    monkeypatch.setattr(core, "_run", lambda *a, **k: (1, '{"loggedIn": false}'))
    st = core.probe_runtime("claude")
    assert st.logged_in is False


def test_probe_of_missing_runtime_says_so(monkeypatch):
    monkeypatch.setattr(core, "which_runtime", lambda n: None)
    st = core.probe_runtime("codex")
    assert not st.installed and "설치" in st.detail


def test_runtime_without_status_command_is_undetermined(monkeypatch):
    """판정 명령이 없으면 `logged_in` 은 **None**(모른다)이다 — False(로그인 안 됨)가 아니다."""
    monkeypatch.setattr(core, "which_runtime", lambda n: "/fake/gemini")
    st = core.probe_runtime("gemini")
    assert st.installed and st.logged_in is None
    assert st.can_login_here is False


# ── 5. 토큰 취급 ───────────────────────────────────────────────────────────────

def test_token_goes_through_env_never_argv(monkeypatch, tmp_path):
    """토큰을 명령줄에 실으면 **프로세스 목록에 뜬다**. 환경변수로만 넘긴다."""
    captured: dict = {}

    class FakePopen:
        def __init__(self, argv, **kw):
            captured["argv"], captured["env"] = argv, kw.get("env", {})
            self.stdout = None

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(core.subprocess, "Popen", FakePopen)
    plan = core.ConnectPlan(base="https://h", token="mat_secret", home=tmp_path)
    core.spawn_runner(plan, tmp_path / "bridge_agent.py", tmp_path / "rootCA.crt")
    assert "mat_secret" not in " ".join(captured["argv"]), "토큰이 명령줄에 실렸다"
    assert captured["env"].get("BRIDGE_TOKEN") == "mat_secret"


def test_check_connection_passes_token_by_env(monkeypatch, tmp_path):
    seen: dict = {}

    def fake_run(argv, **kw):
        seen["argv"], seen["env"] = argv, kw.get("env", {})
        return subprocess.CompletedProcess(argv, 0, "ok", "")

    monkeypatch.setattr(core.subprocess, "run", fake_run)
    plan = core.ConnectPlan(base="https://h", token="mat_x", home=tmp_path)
    rc, _ = core.check_connection(plan, tmp_path / "r.py", tmp_path / "ca.crt")
    assert rc == 0
    assert "mat_x" not in " ".join(seen["argv"])
    assert seen["env"]["BRIDGE_TOKEN"] == "mat_x"
    assert "--check" in seen["argv"], "상주 전에 연결을 확인하지 않는다"


# ── 6. 연결 축 ≠ AI 축 ─────────────────────────────────────────────────────────

def test_exit_4_is_ai_missing_not_connection_failure(monkeypatch, tmp_path):
    """종료코드 4 = 「서버 연결은 정상인데 쓸 수 있는 AI 가 없다」.

    이것을 「연결 확인 실패」로 뭉치면 사용자는 서버를 의심한다 — 실제 제보가 그것이었다
    (feature-0043 REQ-20260901-win-ai-detect).
    """
    monkeypatch.setattr(core.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 4, "", "no ai"))
    plan = core.ConnectPlan(base="https://h", token="t", home=tmp_path)
    rc, _ = core.check_connection(plan, tmp_path / "r.py", tmp_path / "ca.crt")
    assert rc == 4


def test_child_io_is_utf8_explicit():
    """자식 입출력 인코딩을 로케일에 맡기지 않는다.

    한국어 윈도우(`cp949`)에서 인코딩 불가 문자가 파이프 예외를 냈고, 그 실패는 「AI 가 답을
    안 한다」로만 보였다(feature-0043 TASK-20260902T160000 실측).

    ⚠ **검사 시야 주의.** 호출식만 보면 `subprocess.Popen(argv, **kw)` 처럼 kwargs 를 미리
    조립하는 정당한 코드를 「빠졌다」로 오판한다(초판이 그랬다). 자식을 띄우는 **함수 본문
    전체**를 모수로 삼는다 — 지정이 어디에 적혔든 그 함수 안에 있으면 된다.
    """
    import ast
    tree = ast.parse((_SRC / "client" / "core.py").read_text(encoding="utf-8"))
    spawners: list[str] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = ast.unparse(fn)
        if not any(c in body for c in ("subprocess.run(", "subprocess.Popen(")):
            continue
        spawners.append(fn.name)
        assert "utf-8" in body, f"자식을 띄우는 `{fn.name}` 에 UTF-8 명시가 없다"
        assert "errors" in body, f"`{fn.name}` 에 디코드 실패 대비(errors=)가 없다"
    assert len(spawners) >= 3, (
        f"자식을 띄우는 함수를 {len(spawners)}개만 찾았다({spawners}) — 검사 모수가 좁다")


# ── 7. GUI 앱은 콘솔로 말하지 않는다 (실 Windows 실측 2026-09-03) ────────────────

def test_gui_entrypoint_never_prints_to_missing_console():
    """`--windowed` 빌드는 `sys.stdout` 이 `None` 이다.

    그 상태에서 `print()` 를 부르면 예외 → 미처리 예외 대화상자 → **프로세스가 사용자 입력을
    기다리며 멈춘다.** 실 Windows 에서 실제로 그렇게 걸려 강제 종료해야 했다. 사용자에게 말하는
    경로는 창(`tell`)이어야 한다.
    """
    import ast
    src = (_SRC / "client" / "gui.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name != "main":
            continue
        body = ast.unparse(fn)
        assert "print(" not in body, (
            "GUI 진입점이 `print()` 로 사용자에게 말한다 — windowed 빌드에서 멈춘다. "
            "`tell()` 을 쓰라.")
        assert "tell(" in body, "사용자 안내 경로(`tell`)가 없다"
        return
    raise AssertionError("gui.main 을 찾지 못했다")


def test_tell_survives_without_stdout_and_without_display(monkeypatch):
    """`tell()` 은 콘솔도 디스플레이도 없을 때 **예외를 내지 않는다**.

    둘 다 없는 환경(서비스 계정·CI)에서 안내 한 줄 때문에 프로세스가 죽으면 안 된다.
    """
    sys.path.insert(0, str(_SRC))
    import importlib
    gui = importlib.import_module("client.gui")
    monkeypatch.setattr(gui, "sys", type("S", (), {"stdout": None})())
    monkeypatch.setitem(sys.modules, "tkinter", None)   # import tkinter → TypeError
    gui.tell("아무 말")     # 예외가 나면 테스트 실패
