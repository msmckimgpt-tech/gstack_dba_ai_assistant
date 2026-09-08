"""저장된 여섯 계층 → 서버 조립 → 배포 러너 → CLI 전달 경계 회귀."""
from __future__ import annotations

import ast
import importlib.util
import logging
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

UNIT = Path(__file__).resolve().parents[2]
CORE = UNIT / "feature-0002-agent-core" / "src"
sys.path.insert(0, str(CORE))
import agent_core


class PromptDB:
    def __init__(self, *, fail=None, empty=(), large=False):
        self.fail = fail
        self.empty = empty
        self.large = large
        self.cursors = []

    def cursor(self):
        if self.fail == "cursor":
            raise OSError("private SQL detail")
        cursor = PromptCursor(self)
        self.cursors.append(cursor)
        return cursor


class PromptCursor:
    def __init__(self, db):
        self.db, self.row, self.closed = db, None, False

    def execute(self, sql, params=()):
        self.row = None
        if "FROM WebProducts" in sql:
            key, text = "product_label", "product-name"
        elif "FROM WebRoles" in sql:
            key, text = "role_label", "role-name"
        elif "Scope='global'" in sql:
            key, text = "global", "[[global]]"
        elif "Scope='product'" in sql:
            key, text = "product", f"[[product:{params[0]}]]"
        elif "FROM WebSystemPrompts" in sql:
            scope, owner, *product = params
            key = f"{scope}_{'product' if product else 'global'}"
            text = f"[[{key}:{owner}:{product[0] if product else 0}]]"
        else:
            return
        if key == self.db.fail:
            raise OSError("private SQL detail")
        if key not in self.db.empty:
            if self.db.large and key == "account_product":
                text += "한글 긴 지침\n" * 6000
            self.row = (text,)

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


@pytest.fixture(scope="module")
def runner():
    path = UNIT / "feature-0043-external-llm-bridge/src/bridge_agent.py"
    spec = importlib.util.spec_from_file_location("prompt_layer_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def compose_bridge(monkeypatch):
    # 실제 조립 함수 본문을 실행하되 거대한 웹 앱 bootstrap/실 DB 연결은 불러오지 않는다.
    path = UNIT / "feature-0003-agent-web-ui/src/routers/ai_tools.py"
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_bridge_system_prompt")
    namespace = {"logging": logging}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    monkeypatch.setattr(agent_core, "_folder_instructions_for", lambda *args: "")
    return namespace["_bridge_system_prompt"]


def compose(fn, db, *, product=11, account=21, role=31, mode="pinned"):
    return fn(db, product_id=product, role_id=role, account_id=account,
              product_mode=mode, conversation_id=None)


def markers(product=11, account=21, role=31):
    return ["[[global]]", f"[[product:{product}]]", f"[[role_global:{role}:0]]",
            f"[[role_product:{role}:{product}]]", f"[[account_global:{account}:0]]",
            f"[[account_product:{account}:{product}]]"]


@pytest.mark.parametrize("system_channel", [False, True])
@pytest.mark.parametrize("large", [False, True])
def test_all_six_layers_reach_cli_once_in_order(compose_bridge, runner, system_channel, large):
    system = compose(compose_bridge, PromptDB(large=large))
    api = SimpleNamespace(base="https://dqa.invalid", token="test-only")
    task = {"system_prompt": system, "question": "[[current-question]]", "task_id": "test"}
    body = runner.compose_prompt(api, task, system_channel=system_channel)
    kind = "claude" if system_channel else "codex"
    cmd = runner.build_cmd(kind, body)
    cmd = runner._with_system_prompt(cmd, kind, system if system_channel else None)
    carried = cmd[cmd.index("--append-system-prompt") + 1] if system_channel else body
    offsets = [carried.index(value) for value in markers()]
    assert offsets == sorted(offsets)
    assert all(carried.count(value) == 1 for value in markers())
    assert system in carried  # 긴 한국어 원문도 절단 없이 전달한다.
    assert body.count("[[current-question]]") == 1
    if system_channel:
        assert "[[global]]" not in body
    else:
        assert body.index(markers()[-1]) < body.index("[[current-question]]")


def test_auto_only_loads_three_global_layers(compose_bridge):
    prompt = compose(compose_bridge, PromptDB(), mode="auto")
    for marker in markers()[::2]:
        assert marker in prompt
    for marker in markers()[1::2]:
        assert marker not in prompt


def test_sequential_accounts_products_and_roles_do_not_share_instructions(compose_bridge):
    first = compose(compose_bridge, PromptDB())
    second = compose(compose_bridge, PromptDB(), product=12, account=22, role=32)
    assert all(value in first and value not in second for value in markers()[1:])
    assert all(value in second for value in markers(12, 22, 32))


@pytest.mark.parametrize("layer", ["global", "product", "role_global", "role_product", "account_global", "account_product", "cursor"])
def test_query_failures_never_become_missing_configuration(compose_bridge, layer, caplog):
    db = PromptDB(fail=layer)
    with pytest.raises(RuntimeError, match="System prompt unavailable"):
        compose(compose_bridge, db)
    assert all(cursor.closed for cursor in db.cursors)
    assert "private SQL detail" not in caplog.text
    assert "[[global]]" not in caplog.text


def test_no_connection_cannot_pass_as_complete_prompt(compose_bridge):
    with pytest.raises(RuntimeError):
        compose(compose_bridge, None)


@pytest.mark.parametrize("label", ["product_label", "role_label"])
def test_label_failure_does_not_drop_prompt_contents(compose_bridge, label):
    prompt = compose(compose_bridge, PromptDB(fail=label))
    assert all(value in prompt for value in markers())


def test_unconfigured_layers_are_valid_and_global_uses_code_default(compose_bridge):
    prompt = compose(compose_bridge, PromptDB(empty=("global", "role_product", "account_product")))
    assert prompt.startswith(agent_core.SYSTEM_PROMPT)
    assert "[[role_global:31:0]]" in prompt
    assert "[[account_global:21:0]]" in prompt
    assert "[[role_product:31:11]]" not in prompt


def test_legacy_non_strict_bootstrap_remains_available():
    assert agent_core.SYSTEM_PROMPT in agent_core.compose_system_prompt(None)


@pytest.fixture
def claim_prompt_gate():
    """claim_request의 실제 try/except를 실행해 DB 외 주변 절차만 격리한다."""
    import asyncio
    path = UNIT / "feature-0003-agent-web-ui/src/routers/ai_tools.py"
    tree = ast.parse(path.read_text())
    claim = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "claim_request")
    gate = next(n for n in claim.body if isinstance(n, ast.Try) and any(
        isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "_bridge_system_prompt"
        for c in ast.walk(ast.Module(body=n.body, type_ignores=[]))))
    wrapper = ast.parse("async def run():\n    pass\n").body[0]
    wrapper.body = [gate, ast.Return(value=ast.Name(id="system_prompt", ctx=ast.Load()))]
    module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
    state = {"events": [], "fail": True, "cancel": False}

    def compose_fake(*args, **kwargs):
        if state["fail"]:
            raise RuntimeError("unavailable")
        return "complete-prompt"

    async def sleep_fake(seconds):
        state["events"].append(("sleep", seconds))
        if state["cancel"]:
            raise asyncio.CancelledError()

    namespace = {
        "row": [None, None, 11, None, None, 31, "pinned"],
        "conn": object(), "task_id": "task-one", "conversation_id": "conv-one", "account_id": 21, "_prompt_claim_client": "client#old",
        "_bridge_system_prompt": compose_fake,
        "_mark_bridge_working": lambda *args, **kw: state["events"].append(("notice", kw["text"])),
        "_release_claim": lambda *args, **kw: state["events"].append(("release", args[1:], kw)),
        "_json_err": lambda status, msg: SimpleNamespace(status_code=status, message=msg, headers={}),
        "asyncio": SimpleNamespace(sleep=sleep_fake),
    }
    exec(compile(module, str(path), "exec"), namespace)
    return namespace["run"], state


def test_failed_claim_delays_before_release_then_recovers(claim_prompt_gate):
    import asyncio
    gate, state = claim_prompt_gate
    for _ in range(2):
        response = asyncio.run(gate())
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "5"
    assert [item[0] for item in state["events"]] == ["notice", "sleep", "release"] * 2
    assert sum(item[1] for item in state["events"] if item[0] == "sleep") == 10
    assert all("다시 시도" in item[1] for item in state["events"] if item[0] == "notice")
    state["fail"] = False
    assert asyncio.run(gate()) == "complete-prompt"
    assert len(state["events"]) == 6


def test_cancel_during_prompt_failure_backoff_still_releases_claim(claim_prompt_gate):
    import asyncio
    gate, state = claim_prompt_gate
    state["cancel"] = True
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(gate())
    assert state["events"][-1] == ("release", ("task-one", 21), {"claimed_client": "client#old"})


def test_windows_body_fallback_preserves_all_layers_at_process_boundary(compose_bridge, runner, monkeypatch):
    system = compose(compose_bridge, PromptDB(large=True))
    body = runner.compose_prompt(SimpleNamespace(base="https://dqa.invalid", token="test-only"),
                                 {"system_prompt": system, "question": "question", "task_id": "test"})
    monkeypatch.setattr(runner, "_cmdline_budget", lambda: 30000)
    monkeypatch.setattr(runner, "ai_blocked", lambda: (False, ""))
    captured = {}

    def run(cmd, cancel, **kwargs):
        captured.update(cmd=cmd, **kwargs)
        return True, "answer"

    monkeypatch.setattr(runner, "_run_cli_cancelable", run)
    monkeypatch.setattr(runner, "_child_workdir", lambda: None)
    assert runner.ask_local_ai("codex", runner._RUNTIME_SPECS["codex"]["argv"], body, None) == (True, "answer")
    assert captured["stdin_text"] == body
    assert captured["cmd"][-1] == "-"
    assert system in captured["stdin_text"]


@pytest.mark.parametrize("current,expected,released", [
    ("client#old", "client#old", True), ("client#new", "client#old", False),
    (None, None, True), ("client#new", None, False),
])
def test_stale_cleanup_does_not_release_a_new_runner_claim(current, expected, released):
    import sqlite3
    path = UNIT / "feature-0003-agent-web-ui/src/routers/ai_tools.py"
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_release_claim")
    namespace = {"logging": logging, "Any": object, "_CLAIM_CLIENT_UNSET": object()}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE WebAiTasks(TaskId TEXT, Status TEXT, AccountId INTEGER, ClaimedBy INTEGER, ClaimedAt TEXT, ClaimedClient TEXT)")
    db.execute("INSERT INTO WebAiTasks VALUES ('task', 'open', 21, 21, 'now', ?)", (current,))

    class Cursor:
        def execute(self, sql, params):
            # SQLite IS와 MySQL <=>는 이 NULL-safe equality fixture에서 같은 의미다.
            return db.execute(sql.replace("%s", "?").replace("<=>", "IS"), params)

        def close(self):
            pass

    conn = SimpleNamespace(cursor=Cursor, commit=db.commit)
    namespace["_release_claim"](conn, "task", 21, claimed_client=expected)
    row = db.execute("SELECT ClaimedBy, ClaimedClient FROM WebAiTasks").fetchone()
    assert row == ((None, None) if released else (21, current))
    db.close()
