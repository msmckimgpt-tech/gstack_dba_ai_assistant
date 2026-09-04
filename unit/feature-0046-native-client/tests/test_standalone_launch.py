"""**아이콘만 눌러도 앱이 뜬다** — 인자 없는 실행의 계약 (사용자 제보 2026-09-04).

## 무엇이 잘못돼 있었나

사용자가 그대로 적어 보낸 두 문장이 이 파일의 이유다:

> 테스트를 위해 설치된 DQA를 삭제 후, 다시 실행해봤지만 스크린샷과 같은 화면과 함께
> 반응이 없는것으로 확인되었습니다.
> … 여전히 해당 서비스를 사용하기 위해서는 해당 주소에 들어가야하는것으로 확인됩니다.

즉 이 프로그램은 **웹의 부속물**이었다. 딥링크로 켜질 때만 성립했고, 시작 메뉴·바탕화면·
설치 직후의 [지금 실행]·자동 시작은 전부 「연결 정보가 없습니다」로 끝났다.

## 왜 종전 테스트가 못 잡았나

진입점 테스트가 있었지만 그 단정이 **「인자가 없으면 안내를 낸다」였다.** 그것이 그때의
계약이었으므로 테스트는 옳게 통과했다 — 계약 자체가 사용자의 요구와 어긋나 있었던 것이고,
그 어긋남은 테스트가 아니라 **실행해 본 사람**만 볼 수 있었다.

여기서는 갈래를 본다: 아는 서버가 있으면 **앱 창 갈래**로, 없으면 **첫 연결 안내**로.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_UNIT / "src"))

from client import core  # noqa: E402
from client import gui  # noqa: E402


def _plan_home() -> Path:
    """진입점이 실제로 쓰는 홈 — `conftest` 가 격리한 `HOME` 아래.

    ⚠ `ConnectPlan.home` 을 monkeypatch 로 갈아 끼우려 하면 **안 걸린다**. 그 필드는
    `default_factory` 라 클래스 속성을 바꿔도 인스턴스가 팩토리를 다시 부른다 — 그러면
    테스트는 엉뚱한 폴더를 들여다보며 「기록되지 않았다」고 말한다(실측 2026-09-04).
    """
    return core.ConnectPlan(base="", token="").home


@pytest.fixture()
def home(tmp_path):
    h = tmp_path / ".dqa-connect"
    h.mkdir(parents=True)
    return h


@pytest.fixture()
def ran(monkeypatch):
    """`run_client` 를 가로채 **어떤 plan 으로 나아갔는지** 기록한다."""
    seen: list[core.ConnectPlan] = []
    monkeypatch.setattr(gui, "run_client", lambda plan: seen.append(plan) or 0)
    monkeypatch.setattr(gui, "tell", lambda *a, **k: None)
    return seen


# ── 1. 어느 주소를 여는가 — 세 출처의 우선순위 ────────────────────────────────────

def test_nothing_known_yields_no_base(home):
    assert core.startup_base(home) == ""


def test_a_remembered_link_is_enough_to_open(home):
    core.remember_base(home, "https://svc.example")
    assert core.startup_base(home) == "https://svc.example"


def test_a_successful_connection_wins_over_a_mere_link(home):
    """고정은 **연결에 성공한 곳**이다 — 눌러만 본 링크보다 강한 근거다."""
    core.remember_base(home, "https://clicked.example")
    core.pin_server(home, "https://worked.example")
    assert core.startup_base(home) == "https://worked.example"


def test_pinning_does_not_erase_the_remembered_link(home):
    """한 파일에 두 키다 — 통째로 덮으면 한쪽이 다른 쪽을 지운다."""
    core.remember_base(home, "https://clicked.example")
    core.pin_server(home, "https://worked.example")
    assert core.remembered_base(home) == "https://clicked.example"
    core.remember_base(home, "https://later.example")
    assert core.pinned_server(home) == "https://worked.example"


def test_the_bundled_default_is_what_a_fresh_install_opens(home, monkeypatch, tmp_path):
    """설치본에 동봉된 주소 — 이것이 「설치 직후 첫 실행」의 근거다.

    ⚠ 이 값은 **클릭으로 받아들인 링크(`last`)를 이긴다** (codex 적대 리뷰 2026-09-04).
    종전 순서는 그 반대였고, 그러면 악성 링크 한 번이 그 뒤 모든 무인 실행의 목적지를
    조용히 바꾼다. 링크는 클릭 한 번이고 동봉값은 설치 시점에 우리가 넣은 것이다.
    """
    app = tmp_path / "app"
    app.mkdir()
    (app / "service.json").write_text('{"base": "https://built-in.example"}',
                                      encoding="utf-8")
    monkeypatch.setattr(core, "app_dir", lambda: app)
    assert core.startup_base(home) == "https://built-in.example"
    core.remember_base(home, "https://clicked.example")
    assert core.startup_base(home) == "https://built-in.example", "링크가 동봉값을 이겼다"


def test_no_service_file_is_not_an_error(home, monkeypatch, tmp_path):
    monkeypatch.setattr(core, "app_dir", lambda: tmp_path / "nope")
    assert core.bundled_service_base() is None
    assert core.startup_base(home) == ""


# ── 2. 저장된 문자열이 그대로 창의 목적지가 된다 ─────────────────────────────────

@pytest.mark.parametrize("bad", [
    "file:///etc/passwd",         # 로컬 파일 열람
    "javascript:alert(1)",        # 창 안에서의 스크립트 실행
    "dqa-connect://start?x=1",    # 우리 스킴이지만 웹 주소가 아니다
    # ⚠ 접두 비교(`startswith("http")`)로는 이 둘이 통과한다. 지켜야 하는 것은
    #   「http 로 시작한다」가 아니라 **스킴이 http(s) 다** 이다.
    "http-evil://x",
    "httpx://x",
    "not-a-url",
    # ⚠ 이 문자열은 `--app=<여기>` 로 브라우저의 **명령줄**에 들어간다.
    'https://h" --headless --dump-dom "',
    "https://h --headless",
    "https://h\n--headless",
    "https://",                   # 호스트가 없다
    "",
])
def test_only_web_addresses_are_opened(bad, home):
    """⚠ 이 값은 **브라우저 창의 목적지**다. 디스크를 만질 수 있는 상대가 한 줄로
    로컬 파일 열람이나 스크립트 실행을 얻어서는 안 된다."""
    (home / "server.json").write_text(json.dumps({"base": bad}), encoding="utf-8")
    assert core.startup_base(home) == ""


def test_an_empty_base_leaves_no_trace(tmp_path):
    """빈 값으로 부르면 **아무것도 만들지 않는다** — 없는 기록 때문에 폴더가 생기지 않는다."""
    home = tmp_path / "never"
    core.remember_base(home, "")
    assert not home.exists()


def test_a_bad_entry_falls_through_instead_of_stopping(home, monkeypatch, tmp_path):
    """망가진 첫 출처가 **뒤의 성한 출처를 가리면 안 된다** — 그러면 앱이 영영 안 열린다."""
    app = tmp_path / "app"
    app.mkdir()
    (app / "service.json").write_text('{"base": "https://built-in.example"}',
                                      encoding="utf-8")
    monkeypatch.setattr(core, "app_dir", lambda: app)
    (home / "server.json").write_text(
        json.dumps({"base": "file:///etc/passwd"}), encoding="utf-8")
    assert core.startup_base(home) == "https://built-in.example"


def test_a_broken_bundled_value_falls_through_to_the_link(home, monkeypatch, tmp_path):
    """반대 방향도 본다 — 동봉값이 망가졌다고 마지막 출처까지 버리면 앱이 안 열린다."""
    app = tmp_path / "app"
    app.mkdir()
    (app / "service.json").write_text('{"base": "javascript:1"}', encoding="utf-8")
    monkeypatch.setattr(core, "app_dir", lambda: app)
    core.remember_base(home, "https://clicked.example")
    assert core.startup_base(home) == "https://clicked.example"


# ── 3. 진입점이 실제로 그 갈래로 가는가 ───────────────────────────────────────────

def test_bare_launch_with_a_known_server_opens_the_app(monkeypatch, tmp_path, ran):
    """**이 단정이 사용자 제보를 잡는다.** 인자 없이 켜도 나아가야 한다."""
    monkeypatch.setattr(core, "startup_base", lambda home: "https://svc.example")
    assert gui.main([]) == 0
    assert [p.base for p in ran] == ["https://svc.example"]
    assert ran[0].token == "", "인자 없는 실행에 토큰이 있을 리 없다 — 창의 세션이 발급한다"


def test_bare_launch_without_a_known_server_still_guides(monkeypatch, ran):
    """대조군 — 아는 서버가 없으면 여전히 안내로 떨어진다(vacuous pass 방지)."""
    monkeypatch.setattr(core, "startup_base", lambda home: "")
    assert gui.main([]) == 2
    assert ran == []


def test_bare_launch_never_asks_the_server_change_question(monkeypatch, ran):
    """⚠ 매 실행마다 확인창이 뜨면 사용자는 그것을 **습관적으로 넘기게** 되고, 정작 남이
    만든 링크가 왔을 때의 확인도 같이 넘어간다."""
    monkeypatch.setattr(core, "startup_base", lambda home: "https://svc.example")
    monkeypatch.setattr(core, "server_changed",
                        lambda home, base: "https://other.example")
    asked: list[str] = []
    monkeypatch.setattr(gui, "confirm", lambda msg, **k: asked.append(msg) or False)
    assert gui.main([]) == 0
    assert asked == [], f"인자 없는 실행이 물었다: {asked}"


def test_a_deep_link_to_a_new_server_still_asks(monkeypatch, ran):
    """딥링크는 남이 만들었을 수 있다 — 그 확인은 **그대로 남는다**."""
    monkeypatch.setattr(core, "server_changed",
                        lambda home, base: "https://other.example")
    monkeypatch.setattr(gui, "confirm", lambda msg, **k: False)
    url = "dqa-connect://start?token=t&base=https%3A%2F%2Fevil.example"
    assert gui.main([url]) == 3
    assert ran == []


def test_an_accepted_deep_link_is_remembered_but_not_pinned(monkeypatch, ran):
    """다음 실행이 열 곳으로 적되, **고정하지는 않는다** — 연결에 성공한 적이 없다."""
    home = _plan_home()
    monkeypatch.setattr(core, "server_changed", lambda h, base: None)
    url = "dqa-connect://start?token=t&base=https%3A%2F%2Fsvc.example"
    assert gui.main([url]) == 0
    assert core.remembered_base(home) == "https://svc.example"
    assert core.pinned_server(home) is None, "연결 전에 고정하면 실패한 주소가 신뢰받는다"


def test_a_declined_deep_link_is_not_remembered(monkeypatch, ran):
    home = _plan_home()
    monkeypatch.setattr(core, "server_changed", lambda h, base: "https://old.example")
    monkeypatch.setattr(gui, "confirm", lambda msg, **k: False)
    assert gui.main(["dqa-connect://start?token=t&base=https%3A%2F%2Fevil.example"]) == 3
    assert core.remembered_base(home) is None


# ── 4. 두 벌이 뜨지 않는다 ────────────────────────────────────────────────────────
#
# 인자 없는 실행이 **실제로 무언가를 하게 되면서** 생긴 문제다. 종전에는 두 번째 실행이
# 대화상자 하나로 끝났지만, 이제는 브리지·앱 창·트레이·러너가 한 벌 더 뜬다.

def test_a_second_instance_is_refused(home):
    first = core.acquire_single_instance(home)
    assert first is not None
    assert core.acquire_single_instance(home) is None
    first.close()
    again = core.acquire_single_instance(home)
    assert again is not None, "먼저 뜬 쪽이 끝났는데도 막힌다 — 영영 실행 못 하는 상태다"
    again.close()


def test_the_lock_is_released_when_the_process_dies(home):
    """⚠ PID 파일이 아니라 **OS 잠금**이어야 하는 이유. 비정상 종료 뒤에도 다시 떠야 한다."""
    import subprocess
    import textwrap
    code = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(_UNIT / "src")!r})
        from pathlib import Path
        from client import core
        fh = core.acquire_single_instance(Path({str(home)!r}))
        assert fh is not None
        os._exit(9)          # 정리 없이 죽는다 — 크래시와 같은 모양
    """)
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=60)
    assert p.returncode == 9, p.stderr.decode()
    got = core.acquire_single_instance(home)
    assert got is not None, "죽은 프로세스의 잠금이 남아 다음 실행을 막는다"
    got.close()


def test_main_refuses_to_run_twice(monkeypatch, home, ran):
    monkeypatch.setattr(core, "startup_base", lambda h: "https://svc.example")
    monkeypatch.setattr(core, "acquire_single_instance", lambda h: None)
    assert gui.main([]) == 0
    assert ran == [], "이미 떠 있는데 한 벌 더 띄웠다"


def test_the_lock_is_held_for_the_whole_run(monkeypatch, home):
    """⚠ 이름 없는 값으로 받으면 즉시 수거되어 잠금이 풀린다 — 실행 **중에** 확인한다."""
    monkeypatch.setattr(core, "startup_base", lambda h: "https://svc.example")
    monkeypatch.setattr(gui, "tell", lambda *a, **k: None)
    inner: list = []
    monkeypatch.setattr(gui, "run_client",
                        lambda plan: inner.append(
                            core.acquire_single_instance(plan.home)) or 0)
    assert gui.main([]) == 0
    assert inner == [None], "실행 중인데 두 번째 인스턴스가 잠금을 잡았다"


def test_an_unlockable_home_does_not_block_the_app(monkeypatch, tmp_path):
    """잠금은 편의이지 안전 장치가 아니다 — 잠글 수 없다고 앱이 죽으면 안 된다."""
    def _boom(*a, **k):
        raise OSError("읽기 전용")
    monkeypatch.setattr(core.Path, "mkdir", _boom)
    got = core.acquire_single_instance(tmp_path / "nope")
    assert got is not None and got is not None
    got.close()


# ── 5. 배포 기본 주소를 빌드가 적는다 ────────────────────────────────────────────
#
# ⚠ 두 축을 **모두** 본다: 헬퍼가 옳게 적는가, 그리고 **빌드가 그 헬퍼를 부르는가.**
#   앞쪽만 보면 「함수는 완벽한데 아무도 안 부른다」가 통과한다 — 이 저장소가 겪은 형태다.

def _build_mod():
    import importlib.util
    path = _UNIT / "src" / "scripts" / "build_client.py"
    spec = importlib.util.spec_from_file_location("build_client_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_writes_the_service_file(tmp_path):
    mod = _build_mod()
    app = tmp_path / "app"
    app.mkdir()
    assert mod.write_service_file(app, "https://svc.example/") == 0
    assert json.loads((app / "service.json").read_text(encoding="utf-8")) == {
        "base": "https://svc.example"}


def test_build_refuses_a_non_web_address(tmp_path):
    """막지 않으면 그 문자열이 그대로 **브라우저 창의 목적지**가 된다."""
    mod = _build_mod()
    app = tmp_path / "app"
    app.mkdir()
    assert mod.write_service_file(app, "file:///etc/passwd") != 0
    assert not (app / "service.json").exists()


def test_a_rebuild_without_the_flag_clears_the_stale_address(tmp_path):
    """지난 회차의 주소가 남으면 「주지 않았는데 그 주소가 열린다」."""
    mod = _build_mod()
    app = tmp_path / "app"
    app.mkdir()
    mod.write_service_file(app, "https://old.example")
    assert mod.write_service_file(app, "") == 0
    assert not (app / "service.json").exists()


def test_the_build_entry_actually_calls_it():
    """배선 확인 — 헬퍼만 옳고 아무도 안 부르면 설치본에는 아무것도 안 들어간다."""
    import ast as _ast
    src = (_UNIT / "src" / "scripts" / "build_client.py").read_text(encoding="utf-8")
    fn = next(n for n in _ast.walk(_ast.parse(src))
              if isinstance(n, _ast.FunctionDef) and n.name == "main")
    called = {getattr(c.func, "id", None) for c in _ast.walk(fn) if isinstance(c, _ast.Call)}
    assert "write_service_file" in called


def test_the_client_reads_what_the_build_writes(tmp_path, monkeypatch, home):
    """두 프로세스가 같은 파일을 서로 다르게 읽는 일이 없도록 **한 바퀴** 돌린다."""
    mod = _build_mod()
    app = tmp_path / "app"
    app.mkdir()
    mod.write_service_file(app, "https://svc.example")
    monkeypatch.setattr(core, "app_dir", lambda: app)
    assert core.startup_base(home) == "https://svc.example"


# ── 6. 아이콘을 다시 눌러도 창이 돌아온다 ────────────────────────────────────────
#
# 사용자가 앱 창을 닫고(브라우저 창이라 닫는 것이 자연스럽다) 아이콘을 다시 누르는 것은 흔한
# 경로다. 거기서 대화상자로 답하면 **아이콘을 눌렀는데 앱이 안 뜨는** 경험이 한 번 더 난다.

def test_a_second_launch_asks_the_first_to_show_itself(monkeypatch, home, ran):
    monkeypatch.setattr(core, "startup_base", lambda h: "https://svc.example")
    monkeypatch.setattr(core, "acquire_single_instance", lambda h: None)
    told: list = []
    monkeypatch.setattr(gui, "tell", lambda *a, **k: told.append(a))
    assert gui.main([]) == 0
    assert core.take_show_request(_plan_home()) is True, "요청을 남기지 않았다"
    assert told == [], "대화상자로 답했다 — 사용자는 앱을 열려고 눌렀다"


def test_the_request_is_consumed_once(home):
    core.request_show(home)
    assert core.take_show_request(home) is True
    assert core.take_show_request(home) is False, "지우지 않으면 창이 계속 열린다"


def test_a_stale_request_is_ignored(home, monkeypatch):
    """아무도 읽지 않은 요청이 남아 있다가 다음 실행에서 창을 하나 더 열면 안 된다."""
    import time
    core.request_show(home)
    later = time.time() + 10_000_000
    monkeypatch.setattr(time, "time", lambda: later)
    assert core.take_show_request(home) is False


def test_no_request_is_not_an_error(home):
    assert core.take_show_request(home) is False


def test_the_web_shell_loop_reopens_the_window(monkeypatch, home):
    """루프가 요청을 **실제로 소비해 창을 연다** — 배선까지 본다."""
    import queue
    import types
    opened: list = []

    class _Br:
        """한 바퀴만 돌게 한다 — 두 번째 읽기에서 유휴로 판정되어 루프가 끝난다."""
        plan = types.SimpleNamespace(home=home)
        connected = False

        def __init__(self):
            self._reads = 0

        @property
        def idle_seconds(self):
            self._reads += 1
            return 0.0 if self._reads == 1 else 999.0

    core.request_show(home)
    gui._serve_confirms(queue.Queue(), _Br(), idle_limit=90.0,
                        reopen=lambda: opened.append(1))
    assert opened == [1], "요청이 있는데 창을 열지 않았다"


def test_the_tkinter_shell_reads_the_same_request():
    """⚠ 한쪽 껍데기만 알면 그 화면에서는 아이콘이 죽은 채로 남는다."""
    import ast
    src = (_UNIT / "src" / "client" / "gui.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "ClientApp")
    fn = next(n for n in cls.body
              if isinstance(n, ast.FunctionDef) and n.name == "_poll_show_request")
    calls = {ast.unparse(c.func) for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert "core.take_show_request" in calls
    run = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    assert "_poll_show_request" in ast.unparse(run), "폴링을 걸지 않으면 영영 안 읽는다"


# ── 7. codex 적대 리뷰 2026-09-04 — 지적된 4건의 회귀 ────────────────────────────
#
# 외부 리뷰가 짚은 것 중 **실제 결함 4건**이다. 나머지 2건(첫 링크 TOFU 통과 · 잠글 수 없는
# 환경에서 fail-open)은 각각 종전부터의 문서화된 결정이라 그대로 둔다 — 왜 그런지는
# `docs/REVIEW.md` 에 적었다.

@pytest.mark.parametrize("bad", [
    "file:///C:/Users/Alice/secret.txt",
    "javascript:fetch('//evil')",
    'https://h" --headless --dump-dom "',
])
def test_a_deep_link_cannot_point_the_window_at_anything(bad, monkeypatch, ran):
    """⚠ **공격자가 가장 쉽게 넣는 값은 링크 쪽이다.**

    종전에는 파일에서 읽은 값만 걸렀다. 같은 문자열이 같은 곳(브라우저 창의 목적지)으로
    가는데 한쪽만 검사하고 있었다.
    """
    import urllib.parse
    url = "dqa-connect://start?token=t&base=" + urllib.parse.quote(bad, safe="")
    assert gui.main([url]) == 3
    assert ran == [], f"{bad!r} 가 앱 창의 목적지가 됐다"


def test_a_mere_link_cannot_outrank_the_bundled_address(home, monkeypatch, tmp_path):
    """악성 링크 한 번이 **그 뒤 모든 무인 실행**의 목적지를 바꾸면 안 된다."""
    app = tmp_path / "app"
    app.mkdir()
    (app / "service.json").write_text('{"base": "https://ours.example"}', encoding="utf-8")
    monkeypatch.setattr(core, "app_dir", lambda: app)
    core.remember_base(home, "https://evil.example")
    assert core.startup_base(home) == "https://ours.example"
    # 연결에 **성공한** 곳은 여전히 이긴다 — 서버가 진짜 옮겨 갔을 때의 경로다.
    core.pin_server(home, "https://moved.example")
    assert core.startup_base(home) == "https://moved.example"


def test_a_tampered_home_is_surfaced_before_the_window_opens(monkeypatch, ran):
    """홈의 기록은 **인증되지 않는다** — 동봉값과 다르면 주소를 눈에 보이게 한다."""
    monkeypatch.setattr(core, "startup_base", lambda h: "https://evil.example")
    monkeypatch.setattr(core, "bundled_service_base", lambda: "https://ours.example")
    asked: list[str] = []
    monkeypatch.setattr(gui, "confirm", lambda msg, **k: asked.append(msg) or False)
    assert gui.main([]) == 3
    assert ran == []
    assert asked and "evil.example" in asked[0] and "ours.example" in asked[0]


def test_the_normal_case_never_asks(monkeypatch, ran):
    """⚠ 매 실행 확인창은 답이 아니다 — 사람이 습관적으로 넘기면 정작 그때도 넘어간다."""
    monkeypatch.setattr(core, "startup_base", lambda h: "https://ours.example")
    monkeypatch.setattr(core, "bundled_service_base", lambda: "https://ours.example")
    asked: list[str] = []
    monkeypatch.setattr(gui, "confirm", lambda msg, **k: asked.append(msg) or True)
    assert gui.main([]) == 0
    assert asked == [], f"정상 사용에서 확인창이 떴다: {asked}"


def test_no_bundled_address_means_no_question(monkeypatch, ran):
    """동봉값이 없으면 대조할 것이 없다 — 물을 근거도 없다."""
    monkeypatch.setattr(core, "startup_base", lambda h: "https://svc.example")
    monkeypatch.setattr(core, "bundled_service_base", lambda: None)
    monkeypatch.setattr(gui, "confirm", lambda msg, **k: False)
    assert gui.main([]) == 0
    assert [p.base for p in ran] == ["https://svc.example"]


def test_the_second_instance_does_not_write_the_record(monkeypatch, home, ran):
    """잠금 밖에서 쓰면 두 실행이 같은 문서를 읽고 각자 덮어 한쪽 키가 사라진다."""
    monkeypatch.setattr(core, "server_changed", lambda h, base: None)
    monkeypatch.setattr(core, "acquire_single_instance", lambda h: None)
    assert gui.main(["dqa-connect://start?token=t&base=https%3A%2F%2Fsvc.example"]) == 0
    assert core.remembered_base(_plan_home()) is None
