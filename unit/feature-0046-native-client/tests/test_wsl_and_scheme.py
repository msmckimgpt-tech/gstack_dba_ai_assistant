"""**쓸 수 있는 AI 에 도달하는가**, 그리고 **웹의 인계를 받는가**.

## 왜 이 파일이 생겼나 (실측, 2026-09-03)

사용자 제보 두 가지가 같은 뿌리였다.

1. 웹에서 [연결 준비] → [내 AI 실행] 을 눌렀는데 프로그램이 **「연결 정보가 없습니다」**만
   띄웠다. 진입점이 스킴 URL 을 읽지 않았고, 설치기는 `dqa-connect://` 를 등록하지도 않았다.
   브라우저는 **스킴 핸들러 부재를 감지하지 못하므로** 버튼은 조용히 죽는다.
2. 「기존에 쓰던 LLM 접근 수단(WSL)에 진입할 수 없다」. 클라이언트가 Windows 쪽만 봤다.

그리고 그 위에 더 나쁜 것이 있었다 — 클라이언트는 Windows `claude` 를 **「로그인됨 · 연결할
준비가 되었습니다」**로 표시했는데, 그 런타임은 `-p` 에 180초 무응답이었다(WSL 쪽은 정상).
**인증 상태를 가용성의 증거로 읽은 것**이다.

| 자리 | 버전 | `auth status` | `-p` |
|---|---|---|---|
| Windows | 2.1.70 | rc=0 · `loggedIn:true` | **180초 무응답** |
| WSL | 2.1.258 | rc=0 | 정상 응답 |
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
sys.path.insert(0, str(_SRC))

import urllib.parse  # noqa: E402

from client import core  # noqa: E402


def _canon(key: str) -> str:
    """명칭 정본(`shared/dqa_identity.py`)에서 값을 읽는다.

    ⚠ 옛 스킴을 **리터럴로 적지 않는다.** `test_name_ssot.py` 가 허용 목록 밖 소스에서 옛
    이름을 찾으면 실패시키는데(개명이 도달하지 않은 경로를 잡는 게이트), 그 게이트에
    예외를 뚫는 것보다 정본을 읽는 쪽이 옳다 — 정본이 바뀌면 이 테스트도 따라간다.
    """
    src = (_UNIT.parents[1] / "shared" / "dqa_identity.py").read_text(encoding="utf-8")
    for line in src.splitlines():
        if line.startswith(f"{key} "):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise AssertionError(f"정본에 {key} 가 없다")


_LEGACY_SCHEME = _canon("LEGACY_SCHEME")


# ── 1. 자리(Windows/WSL) 를 구분해 실행하는가 ─────────────────────────────────────

def test_windows_runtime_runs_directly():
    st = core.RuntimeState(name="claude", path=r"C:\x\claude.exe", where="windows")
    assert st.argv("auth", "status") == [r"C:\x\claude.exe", "auth", "status"]


def test_wsl_runtime_goes_through_wsl_exe(monkeypatch):
    monkeypatch.setattr(core, "_wsl_exe", lambda: "wsl.exe")
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    assert st.argv("auth", "status") == [
        "wsl.exe", "-e", "/usr/local/bin/claude", "auth", "status"]


def test_label_discloses_where_it_lives():
    """같은 CLI 가 두 자리에 있을 수 있다 — 어느 쪽인지 사용자가 알아야 고를 수 있다."""
    assert core.RuntimeState(name="claude", where="wsl").label == "claude (WSL)"
    assert core.RuntimeState(name="claude", where="windows").label == "claude"


def test_discover_returns_both_places(monkeypatch):
    """**첫 자리에서 멈추지 않는다.** 멈추면 하필 그 자리가 못 쓰는 쪽일 때 「없다」가 된다."""
    monkeypatch.setattr(core, "which_runtime", lambda n: r"C:\x\claude.exe")
    monkeypatch.setattr(core, "wsl_available", lambda: True)
    monkeypatch.setattr(core, "wsl_which", lambda n: "/usr/local/bin/claude")
    found = core.discover_runtime("claude")
    assert [s.where for s in found] == ["windows", "wsl"]


def test_discover_skips_wsl_when_unavailable(monkeypatch):
    monkeypatch.setattr(core, "which_runtime", lambda n: r"C:\x\claude.exe")
    monkeypatch.setattr(core, "wsl_available", lambda: False)
    monkeypatch.setattr(core, "wsl_which",
                        lambda n: pytest.fail("WSL 이 없는데 안을 들여다봤다"))
    assert [s.where for s in core.discover_runtime("claude")] == ["windows"]


def test_wsl_available_requires_a_working_distro(monkeypatch):
    """`wsl.exe` 파일 존재로 판정하지 않는다 — 배포판이 없어도 그 파일은 있다."""
    monkeypatch.setattr(core.os, "name", "nt")
    monkeypatch.setattr(core.shutil, "which", lambda n: r"C:\Windows\wsl.exe")
    monkeypatch.setattr(core, "_run", lambda argv, timeout=30, **kw: (1, "배포판 없음"))
    assert core.wsl_available() is False


def test_wsl_which_rejects_non_absolute_output(monkeypatch):
    """`command -v` 가 경로가 아닌 것을 뱉으면 「찾았다」로 읽지 않는다."""
    monkeypatch.setattr(core, "_run", lambda argv, timeout=30, **kw: (0, "claude: not found"))
    assert core.wsl_which("claude") is None


# ── 2. 인증 상태 ≠ 가용성 (핵심 결함) ─────────────────────────────────────────────

def test_logged_in_runtime_that_cannot_answer_is_not_usable(monkeypatch):
    """**이 단정이 종전 화면을 잡는다.** 로그인됐다고 「준비됨」이라 말하면 안 된다."""
    st = core.RuntimeState(name="claude", path="C:/x/claude.exe", logged_in=True)
    monkeypatch.setattr(core, "_run", lambda argv, timeout=60, **kw: (124, "응답이 없어 중단했습니다."))
    core.verify_answers(st)
    assert st.answers is False
    assert st.usable is False
    assert "쓸 수 없습니다" in st.detail


def test_answering_runtime_is_usable(monkeypatch):
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude",
                           where="wsl", logged_in=True)
    monkeypatch.setattr(core, "_run", lambda argv, timeout=60, **kw: (0, "OK"))
    core.verify_answers(st)
    assert st.answers is True and st.usable is True


def test_empty_answer_is_not_an_answer(monkeypatch):
    """rc 만 보면 조용히 아무것도 안 낸 런타임을 「답한다」고 읽는다."""
    st = core.RuntimeState(name="claude", path="C:/x/claude.exe", logged_in=True)
    monkeypatch.setattr(core, "_run", lambda argv, timeout=60, **kw: (0, "   \n "))
    core.verify_answers(st)
    assert st.answers is False


def test_verify_uses_the_runtimes_own_argv(monkeypatch):
    """WSL 런타임은 **WSL 을 거쳐** 물어봐야 한다 — 아니면 확인 자체가 틀린 것을 잰다."""
    seen: list[list[str]] = []
    monkeypatch.setattr(core, "_wsl_exe", lambda: "wsl.exe")
    monkeypatch.setattr(core, "_run",
                        lambda argv, timeout=60, **kw: (seen.append(argv), (0, "OK"))[1])
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    core.verify_answers(st)
    assert seen[0][:3] == ["wsl.exe", "-e", "/usr/local/bin/claude"]
    assert "-p" in seen[0]


def test_not_installed_is_not_usable():
    st = core.RuntimeState(name="claude", path=None)
    core.verify_answers(st)
    assert st.answers is False and st.usable is False


# ── 3. 러너가 WSL 런타임을 쓰게 만드는가 ──────────────────────────────────────────

def test_windows_runtime_passes_plain_ai_name():
    st = core.RuntimeState(name="claude", path=r"C:\x\claude.exe", where="windows")
    assert core.runner_runtime_args(st) == ["--ai", "claude"]


def test_wsl_runtime_is_named_not_scripted():
    """⚠ **`--cmd` 를 쓰지 않는다** (2026-09-04).

    러너는 `--cmd` 를 받으면 **능력 협상을 돌지 않는다** — 그 명령에 모델이 이미 박혀
    있다는 전제다. 그래서 답변은 정상인데 웹의 「답할 AI 있음」이 ❌ 로 남았다. 이제 러너가
    WSL 자리를 직접 알므로 **이름만** 준다.
    """
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    assert core.runner_runtime_args(st) == ["--ai", "claude"]


def test_wsl_choice_is_pinned_for_the_runner():
    """같은 CLI 가 양쪽에 있을 때 **어느 쪽인지**는 우리가 정한다 — 실제로 물어보고 골랐다."""
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    assert core.runner_runtime_env(st) == {"BRIDGE_AI_PATH_CLAUDE": "/usr/local/bin/claude"}


def test_windows_choice_is_pinned_too():
    st = core.RuntimeState(name="codex", path=r"C:\x\codex.exe", where="windows")
    assert core.runner_runtime_env(st) == {"BRIDGE_AI_PATH_CODEX": r"C:\x\codex.exe"}


def test_no_runtime_pins_nothing():
    assert core.runner_runtime_env(None) == {}


def test_no_runtime_passes_nothing():
    assert core.runner_runtime_args(None) == []


@pytest.mark.parametrize("fname", ["check_connection", "spawn_runner"])
def test_both_runner_entrypoints_use_the_shared_arg_builder(fname):
    """한쪽만 고치면 `--check` 는 WSL 로 가고 상주는 Windows 로 가는 상태가 된다."""
    src = (_SRC / "client" / "core.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == fname)
    calls = {getattr(c.func, "id", None) for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert "runner_runtime_args" in calls


# ── 4. 로그인 대행이 WSL 에도 닿는가 ──────────────────────────────────────────────

def test_login_delegates_into_wsl(monkeypatch):
    """종전에는 이름만 받아 Windows 쪽만 찾았다 — WSL 사용자는 [로그인] 이 헛돌았다."""
    seen: list[list[str]] = []
    monkeypatch.setattr(core, "_wsl_exe", lambda: "wsl.exe")
    monkeypatch.setattr(core, "_run",
                        lambda argv, timeout=300, **kw: (seen.append(argv), (0, ""))[1])
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    ok, _ = core.login(st)
    assert ok
    assert seen[0] == ["wsl.exe", "-e", "/usr/local/bin/claude", "auth", "login"]


def test_login_still_accepts_a_bare_name(monkeypatch):
    """호환 — 이름만 주면 Windows 자리로 간주한다(종전 동작)."""
    monkeypatch.setattr(core, "which_runtime", lambda n: r"C:\x\claude.exe")
    monkeypatch.setattr(core, "_run", lambda argv, timeout=300, **kw: (0, ""))
    assert core.login("claude")[0] is True


def test_login_refuses_when_vendor_command_unknown(monkeypatch):
    """`gemini` 는 로그인 명령을 실측하지 않았다 — 커버리지를 과장하지 않는다."""
    st = core.RuntimeState(name="gemini", path="/usr/bin/gemini", where="wsl")
    ok, msg = core.login(st)
    assert ok is False and "직접 로그인" in msg


# ── 5. 웹의 인계를 받는가 (스킴) ──────────────────────────────────────────────────

def _gui():
    from client import gui
    return gui


def test_scheme_url_is_parsed():
    """**이 단정이 「연결 정보가 없습니다」를 잡는다.**"""
    got = _gui().parse_scheme_url(
        "dqa-connect://start?base=https%3A%2F%2Fh&token=mat_x&ca_sha256=AA%3ABB")
    assert got == {"base": "https://h", "token": "mat_x", "ca_sha256": "AA:BB"}


@pytest.mark.parametrize("url", ["", "not-a-url", "https://evil/start?token=x",
                                 f"{_LEGACY_SCHEME}://start?token=x"])
def test_other_schemes_are_ignored(url):
    """옛 스킴으로 온 것도 받지 않는다 — 옛 등록이 남은 머신에서 값이 섞이면 안 된다."""
    assert _gui().parse_scheme_url(url) == {}


def test_unknown_query_keys_are_dropped():
    got = _gui().parse_scheme_url("dqa-connect://start?token=t&cmd=calc.exe&home=/x")
    assert got == {"token": "t"}


def test_scheme_values_win_over_stale_environment(monkeypatch):
    """스킴으로 온 값이 **방금 만든** 연결 정보다 — 환경변수의 옛 값이 이기면 안 된다."""
    monkeypatch.setenv("BRIDGE_BASE", "https://old")
    monkeypatch.setenv("BRIDGE_TOKEN", "mat_old")
    captured = {}
    gui = _gui()
    monkeypatch.setattr(gui, "ClientApp",
                        lambda plan: captured.update(base=plan.base, token=plan.token)
                        or type("X", (), {"run": lambda self: None})())
    gui.main(["dqa-connect://start?base=https://new&token=mat_new"])
    assert captured == {"base": "https://new", "token": "mat_new"}


def test_entry_still_works_without_a_url(monkeypatch):
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    assert _gui().main([]) == 2


# ── 5-a. 「이 화면을 앱에서 열기」 딥링크 — 조립(서버)과 수용(클라이언트)이 한 표를 본다 ──
#
# 공유 링크를 받은 사람이 브라우저에서 [DQA 앱에서 참여] 를 누르면, 서버가 조립한
# `dqa-connect://open?base=…&path=/share/<token>` 이 OS 를 거쳐 이 프로그램에 온다.
# 조립은 `shared/dqa_identity.app_open_url`, 수용은 `client/core.parse_scheme_url` 인데
# **두 벌은 서로를 import 하지 않는다**(배포본이 동결되는 stdlib 경로 — `SCHEME` 리터럴과
# 같은 사정). 그래서 여기서 실제로 왕복시켜 둘이 갈리지 않았음을 단정한다.

def _canon_module():
    """정본 모듈을 파일에서 직접 로드한다 — 이 테스트는 `shared/` 를 패키지로 두지 않는다."""
    import importlib.util

    path = _UNIT.parents[1] / "shared" / "dqa_identity.py"
    spec = importlib.util.spec_from_file_location("_dqa_identity_canon", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: 두 구현이 **같은 답을 내야 하는** 입력표. 왼쪽이 입력, 오른쪽이 기대값(`None` = 거부).
_PATH_TABLE = [
    ("/share/tok123", "/share/tok123"),
    ("/", "/"),
    ("", "/"),
    ("//evil.example/x", None),          # protocol-relative — 다른 origin 이 열린다
    ("/\\evil.example/x", None),           # 일부 브라우저가 역슬래시를 `/` 로 정규화한다
    ("relative/x", None),                # origin 기준이 아니면 목적지를 특정할 수 없다
    ("/a/../../b", None),                # 목적지를 흐리는 경로를 받아 둘 이유가 없다
    # ⚠ 아래 두 줄이 적대 리뷰 2026-09-08 F1 이다. 이 값의 싱크는 origin 이 아니라
    #   `panel_url` 이 **브리지 좌표를 붙이는 자리**이고, `?` 가 통과하면 쿼리가 두 벌이
    #   되어 `URLSearchParams.get()` 이 취하는 **첫 값**을 링크 제작자가 지배한다 —
    #   즉 앱 창이 공격자가 지정한 로컬 포트로 자기 자격을 배달한다(실행으로 재현했다).
    ("/share/x?client_port=1337&client_nonce=EVIL", None),
    ("/share/x#", None),                 # 진짜 좌표를 프래그먼트로 밀어내는 변종
    ("/share/a\nSet-Cookie: x", None),   # 제어문자 — 로그·argv 경계를 넘는 주입 표면
    # ── 길이 상한의 **경계 양측** (적대 리뷰 2026-09-08 qa-C3) ────────────────────
    # 종전에는 `("/" + "a"*4096, None)` 한 줄뿐이었고, 표에서 가장 긴 **수용** 입력이
    # 13자(`/share/tok123`)라 상한을 13~4096 어느 값으로 바꿔도 표가 전부 초록이었다 —
    # 「상한이 있다」는 잡지만 「그 상한이 512 다」는 아무도 지키지 않았다. 잘못 좁히면
    # 긴 공유 토큰이 조용히 `None` 이 되어 **앱은 뜨는데 늘 루트로** 가고, 넓히면
    # 레지스트리·argv 절단 위험이 돌아온다. ⚠ 리터럴을 다시 적지 않는다 — 상수에서 센다.
    ("/" + "a" * (core.MAX_APP_PATH - 1), "/" + "a" * (core.MAX_APP_PATH - 1)),
    ("/" + "a" * core.MAX_APP_PATH, None),
    # 표기 변종 — 두 사본이 **같은 답**을 내는지가 이 표의 목적이다.
    ("  /share/spaced  ", "/share/spaced"),      # 현행 계약: 양끝 공백은 strip 후 통과
    ("/share/%2F%2Fevil", "/share/%2F%2Fevil"),  # 인코딩된 슬래시는 경로 문자다(브라우저 미해석)
    ("/share/tab\tx", None),                     # 탭은 제어문자 — 거부
]


@pytest.mark.parametrize("raw,expected", _PATH_TABLE)
def test_both_implementations_judge_the_same_path_the_same_way(raw, expected):
    assert core.safe_app_path(raw) == expected, "클라이언트 사본이 표와 다르다"
    assert _canon_module().safe_app_path(raw) == expected, "정본이 표와 다르다"


def test_the_two_path_limits_are_the_same_number():
    assert core.MAX_APP_PATH == _canon_module().MAX_APP_PATH


def test_the_path_limit_is_the_number_we_chose():
    """상한 **값 자체**를 못박는다 — 이것이 없으면 위 경계 행들이 항진명제가 된다.

    ⚠ 실측으로 확인한 함정이다(2026-09-08). 경계 행을 `MAX_APP_PATH - 1` / `MAX_APP_PATH`
    로 «상수에서 계산» 하면, 상수를 64 로 좁혀도 **표가 함께 움직여** 전건 초록이 된다.
    즉 「상한이 지켜진다」는 잡지만 「그 상한이 512 다」는 여전히 아무도 지키지 않는다.
    두 축이 모두 필요하다 — 여기서 값을, 위 표에서 경계 동작을.

    ⚠ 이 숫자를 바꾸려면 **의도적으로** 바꿔라. 좁히면 긴 공유 토큰 경로가 조용히 `None` 이
    되어 앱은 뜨는데 늘 루트로 가고(사용자만 안다), 넓히면 레지스트리·argv 절단 위험이
    돌아온다.
    """
    assert core.MAX_APP_PATH == 512


def test_the_link_the_server_builds_is_the_link_the_client_reads():
    """왕복 — 서버가 만든 문자열을 클라이언트가 그대로 되읽는다."""
    url = _canon_module().app_open_url("https://svc.example", "/share/tok123")
    assert core.parse_scheme_url(url) == {"base": "https://svc.example",
                                          "path": "/share/tok123"}


def test_the_open_link_carries_no_token():
    """이 링크는 **남이 보낸 공유 링크**의 화면에서 만들어진다 — 베어러를 실을 이유가 없다."""
    url = _canon_module().app_open_url("https://svc.example", "/share/tok123")
    assert "token" not in url
    assert "token" not in core.parse_scheme_url(url)


def test_the_sink_survives_a_path_that_slipped_past_the_validator():
    """**방어 이중화** — 검증기가 뚫려도 조립이 다시 막는다 (적대 리뷰 F1).

    `safe_app_path` 하나에 기대면 그 함수의 다음 구멍이 곧 자격 유출이 된다. `panel_url` 은
    경로에 무엇이 섞여 오든 파싱해 분리한 뒤 **우리 좌표를 마지막 값으로** 만든다.
    """
    from client import appwindow

    url = appwindow.panel_url("https://svc.example", 51234, "REAL-NONCE",
                              "/share/abc?client_port=1337&client_nonce=EVIL")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert q["client_port"] == ["51234"], f"공격자 포트가 이겼다: {url}"
    assert q["client_nonce"] == ["REAL-NONCE"], f"공격자 nonce 가 이겼다: {url}"


def test_the_sink_keeps_a_clean_path_intact():
    """양성 대조군 — 정상 경로에서 조립이 종전과 같은 결과를 낸다."""
    from client import appwindow

    url = appwindow.panel_url("https://svc.example", 51234, "n-abc", "/share/abc")
    assert url == "https://svc.example/share/abc?client_port=51234&client_nonce=n-abc"


# ── 5-b. 액션(`open`/`start`)별 수용 키 — 문서가 주장하는 분리를 **수용 측이 집행한다** ──

def test_an_open_link_cannot_smuggle_a_token():
    """P0-AJ 표의 «open 은 토큰을 싣지 않는다» 를 **파서가** 집행한다 (적대 리뷰 F3).

    조립 측 관례만으로는 부족하다 — 이 cycle 부터 제품은 «남이 보낸 공유 링크를 받은 사람»
    에게 스킴 클릭을 정상 동작으로 학습시킨다. 그 사람에게
    `open?base=<진짜 서버>&token=<공격자 토큰>` 은 진짜와 구분되지 않고, `base` 가 같으니
    서버 변경 확인창도 뜨지 않는다.
    """
    got = core.parse_scheme_url(
        "dqa-connect://open?base=https%3A%2F%2Fsvc.example"
        "&token=mat_ATTACKER&ca_sha256=AA&agent_sha256=BB&path=%2Fshare%2Fa")
    assert got == {"base": "https://svc.example", "path": "/share/a"}, got


def test_the_start_link_still_carries_the_four_connection_values():
    """양성 대조군 — 연결 경로의 계약은 그대로다."""
    got = core.parse_scheme_url(
        "dqa-connect://start?base=https%3A%2F%2Fsvc.example&token=mat_x"
        "&ca_sha256=AA&agent_sha256=BB")
    assert got == {"base": "https://svc.example", "token": "mat_x",
                   "ca_sha256": "AA", "agent_sha256": "BB"}


def test_the_server_refuses_to_build_a_link_it_would_not_accept():
    """막을 값이면 **조립 단계에서** 없앤다 — 부적격 링크를 손에 쥐여 주지 않는다."""
    assert _canon_module().app_open_url("https://svc.example", "//evil.example/x") is None


def test_a_bad_path_degrades_to_root_instead_of_killing_the_launch():
    """손으로 만든 나쁜 링크가 **앱 실행 자체**를 막으면 「눌렀는데 아무 일도 없다」가 된다."""
    got = core.parse_scheme_url(
        "dqa-connect://open?base=https%3A%2F%2Fsvc.example&path=%2F%2Fevil")
    assert got == {"base": "https://svc.example"}, "base 까지 잃으면 앱이 서버를 모른다"


def test_an_old_client_still_opens_the_app_on_an_open_link():
    """구버전은 `path` 를 모른다 — 그래도 `base` 를 읽어 **루트를 연다**(의도된 degrade).

    파서는 host(`start`/`open`)가 아니라 **스킴만** 본다. 그래서 구버전에 새 링크가 와도
    「모르는 주소라 무시」가 아니라 「목적지만 모른 채 앱은 뜬다」가 된다.
    """
    url = _canon_module().app_open_url("https://svc.example", "/share/tok123")
    q = url.split("?", 1)[1]
    legacy_keys = ("base", "token", "ca_sha256", "agent_sha256")
    got = {k: v for k, v in (kv.split("=", 1) for kv in q.split("&")) if k in legacy_keys}
    assert got, "구버전이 읽을 수 있는 키가 하나도 없다 — 앱이 서버를 모른다"


def test_the_destination_reaches_the_plan(monkeypatch):
    """진입점이 목적지를 **plan 까지** 나른다 — 여기서 끊기면 창은 루트로 열린다."""
    captured = {}
    gui = _gui()
    monkeypatch.setattr(gui.core, "acquire_single_instance", lambda h: _Lock())
    monkeypatch.setattr(gui, "run_client",
                        lambda plan: captured.update(base=plan.base, path=plan.path) or 0)
    gui.main(["dqa-connect://open?base=https://svc.example&path=/share/tok123"])
    assert captured == {"base": "https://svc.example", "path": "/share/tok123"}


class _Lock:
    def close(self) -> None:
        return None


def test_a_link_to_another_server_is_questioned_even_before_the_first_pin(monkeypatch):
    """**설치 직후**(pin 없음)에도 동봉값과 다른 주소는 묻는다 (적대 리뷰 2R-C2).

    `server_changed` 는 pin 이 없으면 `None` 이라 첫 연결을 통과시킨다 — 그 자체는 옳지만,
    그 상태의 클라이언트에 남이 만든 `open?base=https://evil…` 이 오면 확인창 **없이**
    DQA 브랜드 창에 남의 origin 이 뜬다. 설치 시 우리가 넣은 값이 더 강한 근거다.
    """
    gui = _gui()
    asked: list = []
    monkeypatch.setattr(gui.core, "acquire_single_instance", lambda h: _Lock())
    monkeypatch.setattr(gui.core, "bundled_service_base", lambda: "https://ours.example")
    monkeypatch.setattr(gui.core, "server_changed", lambda home, base: None)
    monkeypatch.setattr(gui, "confirm", lambda msg: asked.append(msg) or False)
    monkeypatch.setattr(gui, "run_client", lambda plan: 0)
    rc = gui.main(["dqa-connect://open?base=https://evil.example&path=/share/a"])
    assert rc == 3, "남의 서버로 여는 링크가 확인 없이 통과했다"
    assert asked and "이 링크" in asked[0]


def test_a_link_to_the_bundled_server_is_not_questioned(monkeypatch):
    """양성 대조군 — 정상 사용에서는 이 창이 뜨지 않는다(매번 뜨면 사람이 습관적으로 넘긴다)."""
    gui = _gui()
    asked: list = []
    captured: dict = {}
    monkeypatch.setattr(gui.core, "acquire_single_instance", lambda h: _Lock())
    monkeypatch.setattr(gui.core, "bundled_service_base", lambda: "https://ours.example")
    monkeypatch.setattr(gui.core, "server_changed", lambda home, base: None)
    monkeypatch.setattr(gui.core, "remember_base", lambda home, base: None)
    monkeypatch.setattr(gui, "confirm", lambda msg: asked.append(msg) or True)
    monkeypatch.setattr(gui, "run_client",
                        lambda plan: captured.update(path=plan.path) or 0)
    rc = gui.main(["dqa-connect://open?base=https://ours.example&path=/share/a"])
    assert rc == 0 and asked == [], f"정상 링크에 확인창이 떴다: {asked}"
    assert captured == {"path": "/share/a"}


# ── 6. 설치기가 스킴을 등록하는가 ─────────────────────────────────────────────────

def test_installer_registers_the_scheme():
    """등록이 없으면 웹의 [내 AI 실행] 은 **조용히** 아무 일도 하지 않는다."""
    iss = (_SRC / "installer" / "DQAConnect.iss").read_text(encoding="utf-8")
    assert "Software\\Classes\\dqa-connect" in iss
    assert "URL Protocol" in iss
    assert '""%1""' in iss, "URL 을 프로그램에 넘기지 않으면 등록해도 값이 안 온다"


def test_scheme_registration_is_per_user_and_removed_on_uninstall():
    iss = (_SRC / "installer" / "DQAConnect.iss").read_text(encoding="utf-8")
    reg = [l for l in iss.splitlines() if l.startswith("Root:")]
    assert reg and all(l.startswith("Root: HKCU") for l in reg), \
        "HKLM 에 쓰면 관리자 권한이 필요해진다(per-user 설치 계약 위반)"
    assert any("uninsdeletekey" in l for l in reg), "제거해도 스킴이 남는다"


def test_registered_scheme_matches_the_canon():
    """스킴 이름은 `shared/dqa_identity.SCHEME` 정본과 같아야 한다."""
    canon = (_UNIT.parents[1] / "shared" / "dqa_identity.py").read_text(encoding="utf-8")
    scheme = next(l.split("=")[1].strip().strip('"\'')
                  for l in canon.splitlines() if l.startswith("SCHEME"))
    iss = (_SRC / "installer" / "DQAConnect.iss").read_text(encoding="utf-8")
    assert f"Software\\Classes\\{scheme}" in iss


# ── 7. 런타임별 호출 형태가 러너 정본과 같은가 ────────────────────────────────────

def test_ask_argv_matches_the_runner_canon():
    """클라이언트의 질문 인자가 러너 `_RUNTIME_SPECS` 와 **같은 모양**인지 대조한다.

    ⚠ 갈리면 클라이언트는 「이 AI 는 답하지 못한다」고 판정하고 러너는 잘 부른다 — 또는
    반대다. 실측 2026-09-03: 모든 런타임에 `-p` 를 써서 WSL `codex` 가 0.1초에 실패했고,
    쓸 수 있는 런타임이 배제됐다.
    """
    canon_src = (_UNIT.parents[1]
                 / "unit/feature-0043-external-llm-bridge/src/agent/runtimes.py"
                 ).read_text(encoding="utf-8")
    for name, ask in core._ASK_ARGV.items():
        # 정본에서 그 런타임의 argv 줄을 찾아 우리 인자가 전부 들어 있는지 본다.
        idx = canon_src.find(f'"{name}": {{')
        assert idx >= 0, f"러너 정본에 {name} 이 없다"
        block = canon_src[idx:idx + 2000]
        argv_line = block[block.find('"argv"'):][:200]
        for token in ask:
            if token == "{prompt}":
                continue
            assert f'"{token}"' in argv_line, \
                f"{name}: 클라이언트가 쓰는 {token!r} 이 러너 정본 argv 에 없다"


def test_every_runtime_has_an_ask_form():
    assert set(core._ASK_ARGV) == set(core.RUNTIMES)


def test_codex_is_not_asked_with_dash_p():
    """실측에서 오판의 원인이던 바로 그것."""
    assert "-p" not in core._ASK_ARGV["codex"]
    assert core._ASK_ARGV["codex"][0] == "exec"


def test_unknown_runtime_is_not_silently_marked_answering(monkeypatch):
    st = core.RuntimeState(name="mystery", path="/x/mystery", logged_in=True)
    monkeypatch.setattr(core, "_run",
                        lambda *a, **k: pytest.fail("모르는 런타임을 실행하려 했다"))
    core.verify_answers(st)
    assert st.answers is False


def test_every_place_gets_the_same_shape():
    """자리에 관계없이 러너에는 **이름**을 준다 — 형태가 갈리면 한쪽만 협상이 돈다."""
    for where, path in (("wsl", "/usr/local/bin/codex"), ("windows", r"C:\x\codex.exe")):
        st = core.RuntimeState(name="codex", path=path, where=where)
        assert core.runner_runtime_args(st) == ["--ai", "codex"]


@pytest.mark.parametrize("fname", ["check_connection", "spawn_runner"])
def test_both_entrypoints_pin_the_chosen_path(fname):
    """한쪽만 고정하면 확인은 WSL 로 가고 상주는 Windows 로 간다."""
    src = (_SRC / "client" / "core.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == fname)
    calls = {getattr(c.func, "id", None) for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert "runner_runtime_env" in calls
