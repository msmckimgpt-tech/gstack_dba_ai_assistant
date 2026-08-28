"""검증용 로그인 세션(`win-browser.py session-*`) 계약 고정 — **동작 구동** 검증.

## 왜 이 스위트가 필요한가

PB-0008 은 **전용 격리 프로필**로 브라우저를 띄운다(사용자 개인 브라우저 무접촉). 옳은 설계지만
그 프로필에는 로그인 세션이 없어서, 검증이 도달할 수 있는 화면이 **로그인 폼뿐**이었다 —
실측 2026-08-27~28, 웹/UI cycle 두 건이 연속으로 "로그인 세션 부재"를 사유로 화면 실측을
미수행 처리했다. 완료 게이트(check #13)가 형식적으로만 통과하던 상태다.

## 왜 소스 문자열 검사가 아니라 가짜 page 인가

초안은 이 계약들을 `ast` / `src.index(...)` 로 검사했다. **적대 리뷰가 그 스위트를 무력화하는
뮤턴트 5종을 동시에 적용하고도 26건 전건 통과시켰다** — `eprint(pw)` 로 비밀번호를 stderr 에
찍고, 대기 루프 **밖**에서 폼을 다시 제출하고, 멱등 분기를 `if False and ...` 로 죽이고,
실패 exit code 를 0 으로 바꾸고, `HANDLERS["session-logout"]` 을 로그인으로 바꿔도 전부 초록.
문자열이 그 자리에 있는지는 **동작이 그러한지와 다른 질문**이었다.

그래서 브라우저 대신 **스크립트된 가짜 page** 를 주입해 `cmd_session_*` 를 실제로 돌리고,
관측 가능한 사실만 단언한다 — 어떤 호출이 몇 번 일어났는가, 무엇이 출력됐는가, exit code 는
무엇인가. 브라우저가 필요한 부분은 라이브 PB-0008 Run 이 담당한다(TEST.md).
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
DRIVER = REPO / "bin" / "win-browser.py"


def _load_driver():
    """하이픈 파일명이라 일반 import 불가 — 경로로 로드한다."""
    spec = importlib.util.spec_from_file_location("win_browser_driver", DRIVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 가짜 page: 실제 조작을 기록하고 스크립트된 상태를 돌려준다 ────────────────

class FakePage:
    """`cmd_session_*` 가 쓰는 표면만 흉내낸다. 모든 조작을 `calls` 에 남긴다."""

    def __init__(self, states, *, totp_modal=False, login_error=""):
        # states: evaluate(_SESSION_STATE_JS) 가 순서대로 돌려줄 값(마지막 값은 반복).
        self._states = list(states)
        self._totp = totp_modal
        self._login_error = login_error
        self.calls = []

    def _next_state(self):
        return self._states[0] if len(self._states) == 1 else self._states.pop(0)

    # -- playwright page 표면 --
    def goto(self, url, **_kw):
        self.calls.append(("goto", url))

    def wait_for_timeout(self, _ms):
        self.calls.append(("wait",))

    def fill(self, selector, value, **_kw):
        self.calls.append(("fill", selector, value))

    def click(self, selector, **_kw):
        self.calls.append(("click", selector))

    def close(self):
        self.calls.append(("close",))

    def evaluate(self, script, *_a):
        if "totpLoginModal" in script:
            self.calls.append(("eval", "totp"))
            return self._totp
        if "loginError" in script:
            self.calls.append(("eval", "loginError"))
            return self._login_error
        if "auth/logout" in script:
            self.calls.append(("eval", "logout"))
            return None
        self.calls.append(("eval", "session"))
        return self._next_state()

    # -- 편의 --
    def count(self, kind):
        return sum(1 for c in self.calls if c[0] == kind)

    def filled_values(self):
        return [c[2] for c in self.calls if c[0] == "fill"]


def _run(mod, cmd_fn, page, monkeypatch, **argattrs):
    """`_drive_new_page` 를 가짜 page 로 갈아끼우고 명령을 돌린다. (rc, emitted_dict).

    ⚠ 게이트(origin 거부·DEBUG 거부·자격증명 부재)는 `_drive_new_page` 를 **타지 않고**
    `emit()` 으로 직접 끝난다 — 그 경로를 놓치면 "차단됐다" 를 확인하지 못한 채 KeyError 로만
    보인다. 그래서 `emit` 도 함께 기록한다(출력은 그대로 흘려보내 capsys 검사가 살아 있게 한다).
    """
    emitted = {}
    real_emit = mod.emit

    def rec_emit(obj):
        if isinstance(obj, dict):
            emitted.update(obj)
        real_emit(obj)

    def fake_drive(_ep, fn):
        result = fn(page)
        out = {"ok": True}
        if isinstance(result, dict):
            out.update(result)
        rec_emit(out)
        return 0 if out.get("ok") else 1

    monkeypatch.setattr(mod, "emit", rec_emit)
    monkeypatch.setattr(mod, "_resolve_endpoint", lambda: "http://fake")
    monkeypatch.setattr(mod, "_drive_new_page", fake_drive)
    monkeypatch.setattr(mod, "TIMEOUT_MS", 1500)  # 대기 루프를 짧게

    class Args:
        pass

    args = Args()
    args.origin = argattrs.pop("origin", "https://localhost")
    for k, v in argattrs.items():
        setattr(args, k, v)
    rc = cmd_fn(args)
    return rc, emitted


AUTHED = {"authenticated": True, "username": "bootstrap_admin", "role": "admin",
          "must_change_password": False, "totp_enabled": False}
ANON = {"authenticated": False, "username": None, "role": None,
        "must_change_password": False, "totp_enabled": False}


@pytest.fixture()
def mod():
    return _load_driver()


@pytest.fixture()
def creds(mod, monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("WEB_BOOTSTRAP_ADMIN_USERNAME=bootstrap_admin\n"
                   "WEB_BOOTSTRAP_ADMIN_PASSWORD=s3cr3t-pw\n"
                   "WEB_ALLOWED_HOSTS=localhost,mysql-ai.company.local\n", encoding="utf-8")
    monkeypatch.setattr(mod, "SESSION_ENV_FILE", str(env))
    monkeypatch.delenv("DEBUG", raising=False)
    return "s3cr3t-pw"


# ── 배선 ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cmd,attr", [("session-check", "cmd_session_check"),
                                      ("session-login", "cmd_session_login"),
                                      ("session-logout", "cmd_session_logout")])
def test_subcommand_maps_to_its_own_handler(mod, cmd, attr):
    """등록만이 아니라 **어디로** 연결됐는지 본다 — 이름만 맞고 logout 이 login 을 부르면 재앙이다."""
    assert mod.HANDLERS[cmd] is getattr(mod, attr)
    args = mod.build_parser().parse_args([cmd])
    assert args.cmd == cmd and hasattr(args, "origin")


# ── 멱등 ─────────────────────────────────────────────────────────────────────

def test_already_authenticated_never_touches_the_form(mod, monkeypatch, creds):
    page = FakePage([AUTHED])
    rc, out = _run(mod, mod.cmd_session_login, page, monkeypatch, allow_remote_origin=False)
    assert rc == 0 and out["already"] is True and out["authenticated"] is True
    assert page.count("fill") == 0 and page.count("click") == 0, \
        "이미 로그인돼 있는데 폼을 조작했다 — 매 검증마다 실패 카운터를 흔든다"


def test_already_path_reports_blocking_flags(mod, monkeypatch, creds):
    """99% 의 호출이 지나가는 경로 — 강제 변경 모달에 갇힌 상태를 여기서도 말해야 한다."""
    page = FakePage([dict(AUTHED, must_change_password=True)])
    _, out = _run(mod, mod.cmd_session_login, page, monkeypatch, allow_remote_origin=False)
    assert out["must_change_password"] is True
    assert "totp_enabled" in out


# ── 무재시도 (계정 잠금 방지) ────────────────────────────────────────────────

def test_exactly_one_submit_even_when_server_rejects(mod, monkeypatch, creds):
    page = FakePage([ANON], login_error="로그인에 실패했습니다.")
    rc, out = _run(mod, mod.cmd_session_login, page, monkeypatch, allow_remote_origin=False)
    assert rc == 1 and out["error"] == "login_rejected"
    assert page.count("click") == 1, f"제출이 {page.count('click')}회 — 재시도는 계정을 잠근다"
    assert page.filled_values().count(creds) == 1, "비밀번호를 두 번 이상 입력했다"


def test_exactly_one_submit_even_when_server_is_silent(mod, monkeypatch, creds):
    """응답도 오류표시도 없을 때(느린 서버·미배선 폼)도 다시 누르지 않는다."""
    page = FakePage([ANON], login_error="")
    rc, out = _run(mod, mod.cmd_session_login, page, monkeypatch, allow_remote_origin=False)
    assert rc == 1 and out["error"] == "login_no_response"
    assert page.count("click") == 1


def test_silent_failure_is_not_reported_as_credential_problem(mod, monkeypatch, creds):
    """무응답을 '자격증명 확인' 으로 안내하면 그 안내가 곧 재시도를 부른다."""
    page = FakePage([ANON], login_error="")
    _, out = _run(mod, mod.cmd_session_login, page, monkeypatch, allow_remote_origin=False)
    assert out["error"] != "login_rejected"
    assert "비밀번호 재입력으로 대응하지 마세요" in out["hint"]


def test_totp_account_is_named_not_timed_out(mod, monkeypatch, creds):
    """2FA 는 비밀번호가 맞아도 세션이 안 난다 — 자격증명 문제로 오인시키지 않는다."""
    page = FakePage([ANON], totp_modal=True)
    rc, out = _run(mod, mod.cmd_session_login, page, monkeypatch, allow_remote_origin=False)
    assert rc == 1 and out["error"] == "totp_required"
    assert page.count("click") == 1


def test_successful_login_submits_once_and_reports(mod, monkeypatch, creds):
    page = FakePage([ANON, AUTHED])
    rc, out = _run(mod, mod.cmd_session_login, page, monkeypatch, allow_remote_origin=False)
    assert rc == 0 and out["authenticated"] is True and out["already"] is False
    assert out["username"] == "bootstrap_admin"
    assert page.count("click") == 1


# ── 비밀번호 누출 ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("page_factory,attrs", [
    (lambda: FakePage([ANON], login_error="로그인에 실패했습니다."), {}),
    (lambda: FakePage([ANON], login_error=""), {}),
    (lambda: FakePage([ANON], totp_modal=True), {}),
    (lambda: FakePage([ANON, AUTHED]), {}),
    (lambda: FakePage([AUTHED]), {}),
])
def test_password_never_appears_in_output_streams(mod, monkeypatch, creds, capsys,
                                                  page_factory, attrs):
    """성공·거부·무응답·2FA·멱등 **모든 경로**에서 stdout/stderr 에 비밀번호가 없어야 한다.

    (초안은 반환 dict 만 봤다 — `eprint(pw)` 뮤턴트가 그대로 통과했다.)
    """
    page = page_factory()
    _, out = _run(mod, mod.cmd_session_login, page, monkeypatch,
                  allow_remote_origin=False, **attrs)
    captured = capsys.readouterr()
    blob = captured.out + captured.err + json.dumps(out, ensure_ascii=False)
    assert creds not in blob, "출력 스트림에 비밀번호가 있다"


def test_password_reaches_only_the_password_field(mod, monkeypatch, creds):
    """비밀번호가 채워진 곳은 비밀번호 입력칸 1곳뿐."""
    page = FakePage([ANON, AUTHED])
    _run(mod, mod.cmd_session_login, page, monkeypatch, allow_remote_origin=False)
    targets = [c[1] for c in page.calls if c[0] == "fill" and c[2] == creds]
    assert targets == ["#loginPassword"], f"비밀번호가 {targets} 로 갔다"


def test_debug_protocol_channel_is_refused(mod, monkeypatch, creds):
    """playwright protocol 디버그가 켜져 있으면 평문이 stderr 로 나간다 — 진행 자체를 막는다."""
    monkeypatch.setenv("DEBUG", "pw:protocol")
    page = FakePage([ANON, AUTHED])
    rc, out = _run(mod, mod.cmd_session_login, page, monkeypatch, allow_remote_origin=False)
    assert rc == 1 and out["error"] == "debug_channel_would_leak_password"
    assert page.count("fill") == 0, "차단했다면서 비밀번호를 이미 입력했다"


# ── origin 게이트 (자격증명 유출 차단) ───────────────────────────────────────

@pytest.mark.parametrize("origin", [
    "https://attacker.example",
    "http://evil.test",
    "https://localhost.attacker.example",   # 접두만 같은 host
    "ftp://localhost",
])
def test_password_is_not_sent_to_unapproved_origin(mod, monkeypatch, creds, origin):
    page = FakePage([ANON, AUTHED])
    rc, out = _run(mod, mod.cmd_session_login, page, monkeypatch,
                   origin=origin, allow_remote_origin=False)
    assert rc == 1 and out["error"] == "origin_not_allowed"
    assert page.count("goto") == 0 and page.count("fill") == 0, \
        "허용되지 않은 origin 인데 페이지를 열고 비밀번호를 입력했다"


@pytest.mark.parametrize("origin", ["https://localhost", "https://127.0.0.1",
                                    "https://mysql-ai.company.local"])
def test_approved_origins_pass(mod, monkeypatch, creds, origin):
    page = FakePage([ANON, AUTHED])
    rc, _ = _run(mod, mod.cmd_session_login, page, monkeypatch,
                 origin=origin, allow_remote_origin=False)
    assert rc == 0


def test_remote_origin_requires_explicit_flag(mod, monkeypatch, creds):
    """넓히는 것은 사람이 명시해야 한다 — 그러나 명시하면 통과한다(막다른 길 아님)."""
    page = FakePage([ANON, AUTHED])
    rc, _ = _run(mod, mod.cmd_session_login, page, monkeypatch,
                 origin="https://staging.example", allow_remote_origin=True)
    assert rc == 0 and page.count("fill") == 2


# ── check / logout 의 정직성 ─────────────────────────────────────────────────

def test_check_require_auth_gates_with_exit_code(mod, monkeypatch, creds):
    page = FakePage([ANON])
    rc, out = _run(mod, mod.cmd_session_check, page, monkeypatch, require_auth=True)
    assert rc == 1 and out["error"] == "not_authenticated"
    rc2, out2 = _run(mod, mod.cmd_session_check, FakePage([AUTHED]), monkeypatch,
                     require_auth=True)
    assert rc2 == 0 and out2["authenticated"] is True


def test_check_distinguishes_probe_failure_from_anonymous(mod, monkeypatch, creds):
    """`/api/session` 이 죽은 것과 '로그인 안 됨' 은 다른 사실이다."""
    page = FakePage([{"authenticated": False, "error": "TypeError: Failed to fetch"}])
    rc, out = _run(mod, mod.cmd_session_check, page, monkeypatch, require_auth=False)
    assert rc == 1 and out["error"] == "session_probe_failed"


def test_logout_fails_when_session_survives(mod, monkeypatch, creds):
    """해제 안 됐는데 ok:true 면, 다음 검증이 남은 관리자 세션 위에서 돈다."""
    page = FakePage([AUTHED])          # logout 후에도 여전히 인증 상태
    rc, out = _run(mod, mod.cmd_session_logout, page, monkeypatch)
    assert rc == 1 and out["error"] == "logout_ineffective" and out["authenticated"] is True


def test_logout_succeeds_when_session_cleared(mod, monkeypatch, creds):
    page = FakePage([AUTHED, ANON])
    rc, out = _run(mod, mod.cmd_session_logout, page, monkeypatch)
    assert rc == 0 and out["authenticated"] is False


# ── .env 파싱 ────────────────────────────────────────────────────────────────

def test_env_parser_reads_only_requested_keys(mod, tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "WEB_BOOTSTRAP_ADMIN_USERNAME=bootstrap_admin\n"
        'WEB_BOOTSTRAP_ADMIN_PASSWORD="p@ss word=with=eq # not-a-comment"\n'
        "UNRELATED_SECRET=must-not-be-read\n"
        "MALFORMED_LINE\n",
        encoding="utf-8",
    )
    got = mod._read_env_keys(str(env), ("WEB_BOOTSTRAP_ADMIN_USERNAME",
                                        "WEB_BOOTSTRAP_ADMIN_PASSWORD"))
    assert got["WEB_BOOTSTRAP_ADMIN_USERNAME"] == "bootstrap_admin"
    # 인용된 값은 `#` 포함 그대로 — 비밀번호의 일부일 수 있다.
    assert got["WEB_BOOTSTRAP_ADMIN_PASSWORD"] == "p@ss word=with=eq # not-a-comment"
    assert "UNRELATED_SECRET" not in got


def test_unquoted_inline_comment_is_stripped(mod, tmp_path):
    """주석까지 비밀번호로 보내면 매 호출이 실패 1회로 기록돼 잠금에 가까워진다."""
    env = tmp_path / ".env"
    env.write_text("WEB_BOOTSTRAP_ADMIN_PASSWORD=secret # rotated 2026-08\n", encoding="utf-8")
    got = mod._read_env_keys(str(env), ("WEB_BOOTSTRAP_ADMIN_PASSWORD",))
    assert got["WEB_BOOTSTRAP_ADMIN_PASSWORD"] == "secret"


def test_unreadable_env_is_not_reported_as_missing_password(mod, monkeypatch, tmp_path):
    """'못 읽었다' 와 '값이 없다' 는 다른 진단이다."""
    env = tmp_path / ".env"
    env.write_text("WEB_BOOTSTRAP_ADMIN_PASSWORD=x\n", encoding="utf-8")
    monkeypatch.setattr(mod, "SESSION_ENV_FILE", str(env))
    monkeypatch.setattr(mod, "_read_env_keys", lambda *_a, **_k: None)
    _, _, _, problem = mod._session_credentials()
    assert problem == "env_file_unreadable"


def test_missing_env_file_reports_problem(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "SESSION_ENV_FILE", str(tmp_path / "nope.env"))
    user, pw, _, problem = mod._session_credentials()
    assert problem == "env_file_missing" and user is None and pw is None


def test_empty_password_reports_problem(mod, monkeypatch, tmp_path):
    """빈 비밀번호로 로그인 시도를 하지 않는다 — 그건 실패 카운터만 올린다."""
    env = tmp_path / ".env"
    env.write_text("WEB_BOOTSTRAP_ADMIN_USERNAME=bootstrap_admin\n"
                   "WEB_BOOTSTRAP_ADMIN_PASSWORD=\n", encoding="utf-8")
    monkeypatch.setattr(mod, "SESSION_ENV_FILE", str(env))
    _, _, _, problem = mod._session_credentials()
    assert problem == "password_not_set"


def test_username_defaults_when_absent(mod, monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("WEB_BOOTSTRAP_ADMIN_PASSWORD=x\n", encoding="utf-8")
    monkeypatch.setattr(mod, "SESSION_ENV_FILE", str(env))
    user, _, _, problem = mod._session_credentials()
    assert problem is None and user == "bootstrap_admin"


def test_credential_problem_blocks_before_any_browser_work(mod, monkeypatch, tmp_path):
    """자격증명이 없으면 브라우저를 열지도 않는다(빈 시도로 카운터를 올리지 않는다)."""
    monkeypatch.setattr(mod, "SESSION_ENV_FILE", str(tmp_path / "nope.env"))
    monkeypatch.delenv("DEBUG", raising=False)
    called = []
    monkeypatch.setattr(mod, "_resolve_endpoint", lambda: called.append(1) or "http://fake")

    class Args:
        origin = "https://localhost"
        allow_remote_origin = False

    rc = mod.cmd_session_login(Args())
    assert rc == 1 and not called, "자격증명이 없는데 브리지를 붙잡았다"


# ── 자기 탭 격리 (§16.6) ─────────────────────────────────────────────────────

def _fake_browser_stack(mod, monkeypatch):
    """실제 `_drive_new_page` 를 돌리기 위한 최소 브라우저 더블."""
    class P:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

        # 운영 코드는 "열려 있는 탭 수" 를 세어 마지막 탭을 남긴다(2bf63215). 더블에 이 메서드가
        # 없으면 그 계산이 AttributeError 로 죽고, `finally` 의 except 가 삼켜 **아무 탭도 닫히지
        # 않는다** — 테스트는 조용히 다른 것을 검증하게 된다.
        def is_closed(self):
            return self.closed

    class Ctx:
        def __init__(self):
            self.pages = [P()]

        def new_page(self):
            p = P()
            self.pages.append(p)
            return p

    ctx = Ctx()

    class Browser:
        contexts = [ctx]

        def close(self):
            pass

    class PW:
        def stop(self):
            pass

    # `_connect` 는 `want_created_flag` 를 받고, 참이면 `created` 를 덧붙인 4-tuple 을 준다
    # (2bf63215 에서 운영 코드가 그렇게 바뀌었다). 더블이 옛 서명이면 `_drive_new_page` 가
    # TypeError 로 죽어 **이 파일의 4건이 통째로 실패**한다.
    # 여기서는 탭이 미리 있는 상황이므로 `created=False` — 운영과 같은 의미다.
    def _fake_connect(_ep, *, want_created_flag: bool = False):
        base = (PW(), Browser(), ctx.pages[0])
        return (*base, False) if want_created_flag else base

    monkeypatch.setattr(mod, "_connect", _fake_connect)
    return ctx


@pytest.mark.parametrize("result,expected_rc", [
    ({"x": 1}, 0),
    ({"ok": False, "error": "login_rejected"}, 1),
])
def test_drive_new_page_exit_code_follows_ok(mod, monkeypatch, result, expected_rc):
    """실패를 exit 0 으로 돌려주면 `&&` 로 엮은 검증 파이프라인이 통과해 버린다.

    (적대 리뷰가 지적한 뮤턴트 — `return 0 if out.get("ok") else 1` → `return 0` 은 어떤
    테스트도 잡지 못했다. 명령 단위 테스트는 이 함수를 가짜로 갈아끼우므로 여기서 직접 본다.)
    """
    _fake_browser_stack(mod, monkeypatch)
    rc = mod._drive_new_page("http://fake", lambda _p: result)
    assert rc == expected_rc


def test_drive_new_page_reports_failure_on_exception(mod, monkeypatch):
    _fake_browser_stack(mod, monkeypatch)

    def boom(_p):
        raise RuntimeError("brittle")

    assert mod._drive_new_page("http://fake", boom) == 1


def test_drive_new_page_uses_and_closes_its_own_tab(mod):
    """기존 탭을 빼앗지 않고, `_connect` 가 만든 여분 빈 탭도 회수한다."""
    closed, created = [], []

    class P:
        def __init__(self, name):
            self.name = name
            self._closed = False

        def close(self):
            self._closed = True
            closed.append(self.name)

        def is_closed(self):
            return self._closed

    class Ctx:
        def __init__(self):
            self.pages = [P("connect-made")]

        def new_page(self):
            p = P("mine")
            created.append(p)
            self.pages.append(p)
            return p

    ctx = Ctx()

    class Browser:
        contexts = [ctx]

        def close(self):
            pass

    class PW:
        def stop(self):
            pass

    # 이 시나리오의 `connect-made` 탭은 **`_connect` 가 만든** 여분 탭이다 → `created=True`.
    # 그 사실을 `_drive_new_page` 에게 전달해야 "내가 만든 것만 치운다" 판정이 성립한다.
    def _fake_connect(_ep, *, want_created_flag: bool = False):
        base = (PW(), Browser(), ctx.pages[0])
        return (*base, True) if want_created_flag else base

    mod._connect = _fake_connect
    seen = {}
    mod._drive_new_page("http://fake", lambda page: seen.setdefault("page", page) or {"x": 1})
    assert seen["page"] is created[0], "기존 탭에서 동작했다 — 앞선 검증 화면을 빼앗는다"
    # 2bf63215 이후 계약: **마지막 탭은 남긴다**. 다 닫으면 Chrome 이 통째로 종료돼
    # 다음 명령이 `no_bridge` 로 끊긴다(라이브 3회 재현). 그래서 내 탭만 닫고, 그 결과
    # 하나 남는 `connect-made` 는 회수하지 않는다 — 쌓이는 빈 탭보다 죽은 브라우저가 비싸다.
    assert closed == ["mine"], f"내 탭만 닫아야 한다: {closed}"
    assert not ctx.pages[0].is_closed(), "마지막 탭까지 닫았다 — 브라우저가 죽는다"
