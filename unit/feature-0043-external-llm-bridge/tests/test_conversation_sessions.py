"""실제 번들 호출과 영속 세션/그룹 이력 계약을 검증한다."""
import ast
import hashlib
import importlib.util
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

UNIT = Path(__file__).resolve().parents[2]
SID = "12345678-1234-1234-1234-123456789abc"
SID2 = "22345678-1234-1234-1234-123456789abc"


@pytest.fixture
def runner(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("session_runner", UNIT / "feature-0043-external-llm-bridge/src/bridge_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "_CONF_DIR", str(tmp_path))
    monkeypatch.setattr(mod, "_session_supported", lambda kind: kind in ("codex", "claude"))
    monkeypatch.setattr(mod, "_resolve_exe", lambda cmd: cmd)
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    mod.reset_ai_health()
    return mod


def claim(account=10, conv="conv-1", chain=None):
    return {"task_id": "t-1", "conversation_id": conv, "question": "질문", "system_prompt": "규칙",
            "conversation_context": "공동 대화 기록", "conversation_session": {
                "account_id": account, "context_key": "scope", "history_chain": chain or ["a" * 64]}}


def api():
    return SimpleNamespace(base="https://dqa.test", token="secret-token", ca=None,
                           call=lambda *a, **k: {"delivered_to_conversation": True})


def completed(binding, native=SID):
    binding.result.update(native_id=native, completed=True)
    binding.commit({"history_chain": binding.history + ["f" * 64]})


@pytest.mark.parametrize("kind", ["claude", "codex"])
def test_persistent_binding_is_exact_and_new_messages_preserve_it(runner, kind):
    task = claim()
    with runner.conversation_session(api(), task, kind, None) as binding:
        assert not binding.result.get("resume")
        completed(binding)
    task["conversation_session"]["history_chain"].extend(["f" * 64, "b" * 64])
    with runner.conversation_session(api(), task, kind, None) as binding:
        assert binding.result["resume"] == SID
        cmd = runner.session_command([kind, "exec", "Q"] if kind == "codex" else [kind, "-p", "Q"], binding.result)
        assert SID in cmd and "--last" not in cmd and "--continue" not in cmd
        assert cmd[-1] == "Q"
        if kind == "codex":
            assert cmd[:3] == ["codex", "exec", "resume"]


@pytest.mark.parametrize("axis", ["account", "conversation", "scope", "origin", "location"])
def test_different_scope_never_inherits_native_session(runner, monkeypatch, axis):
    task, client = claim(), api()
    with runner.conversation_session(client, task, "codex", None) as binding:
        completed(binding)
    if axis == "account":
        task["conversation_session"]["account_id"] = 11
    elif axis == "conversation":
        task["conversation_id"] = "other"
    elif axis == "scope":
        task["conversation_session"]["context_key"] = "new-role"
    elif axis == "origin":
        client.base = "https://other.test"
    else:
        monkeypatch.setattr(runner, "_resolve_exe", lambda cmd: ["wsl", "-u", "other", *cmd])
    with runner.conversation_session(client, task, "codex", None) as binding:
        assert not binding.result.get("resume")


@pytest.mark.parametrize("chain", [["b" * 64], ["a" * 64]])
def test_edited_or_deleted_history_starts_fresh(runner, chain):
    with runner.conversation_session(api(), claim(chain=["a" * 64, "c" * 64]), "claude", None) as binding:
        completed(binding)
    with runner.conversation_session(api(), claim(chain=chain), "claude", None) as binding:
        assert not binding.result.get("resume")


def test_uncommitted_execution_cannot_be_resumed_after_restart(runner):
    with runner.conversation_session(api(), claim(), "codex", None) as binding:
        completed(binding)
    with runner.conversation_session(api(), claim(chain=["a" * 64, "f" * 64]), "codex", None) as binding:
        assert binding.result["resume"] == SID
        # 실패/취소/프로세스 종료: commit을 호출하지 않음
    with runner.conversation_session(api(), claim(), "codex", None) as binding:
        assert not binding.result.get("resume")


def test_disappearing_runtime_selection_uses_normal_cli_error_path(runner, monkeypatch):
    def missing(cmd):
        raise FileNotFoundError("DQA에서 선택한 AI 위치를 확인할 수 없습니다.")
    monkeypatch.setattr(runner, "_resolve_exe", missing)
    with runner.conversation_session(api(), claim(), "codex", None) as binding:
        assert binding is None


def test_parallel_process_cannot_open_same_native_session(runner):
    with runner.conversation_session(api(), claim(), "codex", None) as binding:
        script = "import fcntl,sys; f=open(sys.argv[1], 'a+b'); fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)"
        result = subprocess.run([sys.executable, "-c", script, binding.path + ".install.lock"], capture_output=True)
        assert result.returncode != 0
        with runner.conversation_session(api(), claim(), "codex", None) as concurrent:
            assert concurrent is None


def test_state_has_only_native_id_and_hashes(runner):
    with runner.conversation_session(api(), claim(), "claude", None) as binding:
        completed(binding)
        state = json.loads(Path(binding.path).read_text())
        assert set(state) == {"native_id", "history_count", "history_digest"}
        if os.name != "nt":
            assert os.stat(binding.path).st_mode & 0o777 == 0o600


def codex_output(native=SID):
    return "\n".join(json.dumps(event) for event in [
        {"type": "thread.started", "thread_id": native}, {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "reasoning", "text": "비공개 추론"}},
        {"type": "item.completed", "item": {"type": "agent_message", "phase": "commentary", "text": "중간"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "최종 답변"}},
        {"type": "turn.completed"}])


@pytest.mark.parametrize("kind", ["claude", "codex"])
def test_real_child_process_json_becomes_only_final_answer(runner, kind):
    data = codex_output() if kind == "codex" else json.dumps({"type": "result", "subtype": "success", "result": "최종 답변", "session_id": SID, "is_error": False})
    state = {"kind": kind}
    ok, answer = runner._run_cli_cancelable([sys.executable, "-c", "import sys; print(sys.argv[1])", data], lambda: False, session_result=state)
    assert ok and answer == "최종 답변"
    assert state["native_id"] == SID and state["completed"]


@pytest.mark.parametrize("out", ["plain text", '{}', '{"type":"turn.completed"}', '{"type":"turn.failed"}', '{"type":"item.completed","item":{"type":"agent_message","text":"partial"}}'])
def test_incomplete_or_malformed_output_is_not_success(runner, out):
    assert runner.decode_session_output({"kind": "codex"}, out, "", 0)[0] is False


def test_claude_is_error_never_commits_even_with_zero_exit(runner):
    state = {"kind": "claude"}
    ok, _ = runner.decode_session_output(state, json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True, "result": "partial", "session_id": SID}), "", 0)
    assert not ok and not state["completed"]


def test_session_missing_retries_once_and_preserves_network_flags(runner, monkeypatch):
    calls = []
    def run(cmd, *a, **kw):
        calls.append((cmd, kw))
        if len(calls) == 1:
            return False, runner._SESSION_MISSING
        return True, "final"
    monkeypatch.setattr(runner, "_run_cli_cancelable", run)
    state = {"kind": "codex", "resume": SID}
    ok, answer = runner.ask_local_ai("codex", ["codex", "exec", "--skip-git-repo-check", "{prompt}"], "Q", None, session=state, token="secret", api_base="https://dqa.test")
    assert ok and len(calls) == 2
    assert "resume" in calls[0][0] and "resume" not in calls[1][0]
    for cmd, kw in calls:
        assert 'default_permissions="dqa-task"' in cmd
        assert kw["env"]["BRIDGE_TOKEN"] == "secret"
        assert "secret" not in " ".join(cmd)


def test_ordinary_errors_and_cancel_do_not_retry(runner, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "_run_cli_cancelable", lambda *a, **k: (calls.append(a) or False, "quota"))
    assert not runner.ask_local_ai("codex", ["codex", "exec", "{prompt}"], "Q", None, session={"kind": "codex", "resume": SID})[0]
    assert len(calls) == 1


@pytest.mark.parametrize("delivered", [True, False])
def test_handler_commits_only_delivered_success_and_reuses_first_session(runner, monkeypatch, delivered):
    received = []
    def ask(*args, **kwargs):
        state = kwargs["session"]
        received.append((dict(state), args[2]))
        state.update(native_id=SID, completed=True)
        return True, "answer"
    monkeypatch.setattr(runner, "ask_local_ai", ask)
    client = api()
    client.call = lambda *a, **k: {"delivered_to_conversation": delivered,
                                   "conversation_session": {"history_chain": ["a" * 64, "f" * 64]}}
    for n in range(2):
        assert runner.handle_one(client, "t1", claim(chain=["a" * 64] if n == 0 else ["a" * 64, "f" * 64]), "codex", ["codex", "exec", "{prompt}"], None, self_review=False)
    assert bool(received[1][0].get("resume")) is delivered
    assert "공동 대화 기록" in received[1][1]


@pytest.fixture
def history():
    path = UNIT / "feature-0003-agent-web-ui/src/routers/ai_tools.py"
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_recent_conversation_context")
    rows = []
    ns = {"app": SimpleNamespace(_conv_load_messages_raw=lambda *a, **kw: rows),
          "json": json, "hashlib": hashlib, "logging": logging,
          "_guard": SimpleNamespace(flag_injection_refusal=lambda text: False),
          "_BRIDGE_HISTORY_TURNS": 80, "_BRIDGE_HISTORY_CHARS": 48000}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    return rows, ns["_recent_conversation_context"], ns


def test_group_preserves_every_participant_and_assistant_and_repeated_question(history):
    rows, render, _ = history
    rows.extend([
        (1, "user", "같은 질문", None, {"sender_username": "A"}),
        (2, "assistant", "A의 응답", None, {"requested_by_username": "A"}),
        (3, "user", "B 질문", None, json.dumps({"sender_username": "B"})),
        (4, "assistant", "B의 응답", None, {"requested_by_username": "B"}),
        (5, "user", "사람끼리 논의", None, {"sender_username": "C"}),
        (6, "user", "같은 질문", None, {"sender_username": "A", "bridge": {"task_id": "t1"}}),
        (7, "assistant", "처리 중", None, {"bridge": {"task_id": "t1", "placeholder": True}})])
    state = {}
    text = render(None, "group", "같은 질문", task_id="t1", context_state=state)
    assert text.count("같은 질문") == 1
    assert all(x in text for x in ['사용자 "A"', '사용자 "B"', '사용자 "C"', '호출자 "A"', '호출자 "B"', "A의 응답", "B의 응답"])
    assert "처리 중" not in text and len(state["history_chain"]) == 6


def test_history_changes_have_different_chain_and_append_keeps_prefix(history):
    rows, render, _ = history
    rows.append((1, "user", "original", None, {}))
    first = {}
    render(None, "c", context_state=first)
    rows.append((2, "assistant", "answer", None, {}))
    second = {}
    render(None, "c", context_state=second)
    assert second["history_chain"][:1] == first["history_chain"]
    rows[0] = (1, "user", "edited", None, {})
    third = {}
    render(None, "c", context_state=third)
    assert third["history_chain"][0] != first["history_chain"][0]


def test_history_failure_does_not_silently_send_empty_context(history):
    _, render, ns = history
    def fail(*a, **kw):
        raise OSError("offline")
    ns["app"]._conv_load_messages_raw = fail
    with pytest.raises(RuntimeError):
        render(None, "c")


def test_history_caps_report_both_turn_and_character_omissions(history):
    rows, render, ns = history
    ns["_BRIDGE_HISTORY_TURNS"] = 2
    rows.extend((i, "assistant", str(i), None, {}) for i in range(3))
    assert "일부 생략" in render(None, "c")
    ns["_BRIDGE_HISTORY_CHARS"] = 5
    assert "일부 생략" in render(None, "c")


def test_most_recent_assistant_edit_or_delete_invalidates_session(runner):
    for next_chain in (["a" * 64], ["a" * 64, "e" * 64]):
        with runner.conversation_session(api(), claim(), "codex", None) as binding:
            completed(binding)
        with runner.conversation_session(api(), claim(chain=next_chain), "codex", None) as binding:
            assert not binding.result.get("resume")


def test_missing_or_nonextending_receipt_cannot_commit(runner):
    for receipt in (None, {}, {"history_chain": ["a" * 64]}, {"history_chain": ["e" * 64, "f" * 64]}):
        with runner.conversation_session(api(), claim(), "codex", None) as binding:
            binding.result.update(native_id=SID, completed=True)
            binding.commit(receipt)
            assert not Path(binding.path).exists()


@pytest.mark.parametrize("kind,event", [
    ("claude", {"type": "result", "subtype": "error_during_execution", "is_error": True, "num_turns": 1}),
    ("codex", {"type": "item.completed", "item": {"type": "command_execution"}}),
    ("codex", {"type": "turn.started"}),
])
def test_execution_evidence_prevents_missing_session_retry(runner, kind, event):
    state = {"kind": kind, "resume": SID}
    ok, answer = runner.decode_session_output(state, json.dumps(event), "Session not found: " + SID, 1)
    assert not ok and answer != runner._SESSION_MISSING


def test_missing_session_must_name_exact_resumed_id(runner):
    state = {"kind": "codex", "resume": SID}
    assert runner.decode_session_output(state, "", "Session not found: " + SID2, 1)[1] != runner._SESSION_MISSING
    assert runner.decode_session_output(state, "", "Session not found: " + SID, 1)[1] == runner._SESSION_MISSING


def test_messages_added_during_generation_are_sent_on_next_resume(runner, monkeypatch):
    prompts = []
    state_chain = ["a" * 64]
    def ask(*args, **kwargs):
        prompts.append((kwargs["session"].get("resume"), args[2]))
        kwargs["session"].update(native_id=SID, completed=True)
        state_chain.extend(["b" * 64, "c" * 64])
        return True, "A assistant answer"
    monkeypatch.setattr(runner, "ask_local_ai", ask)
    client = api()
    client.call = lambda *a, **k: {"delivered_to_conversation": True, "conversation_session": {"history_chain": list(state_chain)}}
    first = claim(chain=list(state_chain))
    runner.handle_one(client, "t1", first, "codex", ["codex", "exec", "{prompt}"], None, self_review=False)
    second = claim(chain=list(state_chain))
    second["conversation_context"] = '[사용자 B] 생성 중 질문\n[assistant / 호출자 B] B의 답변'
    runner.handle_one(client, "t2", second, "codex", ["codex", "exec", "{prompt}"], None, self_review=False)
    assert prompts[1][0] == SID
    assert '생성 중 질문' in prompts[1][1] and 'B의 답변' in prompts[1][1]


def test_old_refusal_does_not_permanently_disable_clean_session(history):
    rows, render, ns = history
    ns["_guard"].flag_injection_refusal = lambda text: text == "refusal"
    rows.extend([(1, "assistant", "refusal", None, {}), (2, "user", "current", None, {})])
    state = {}
    text = render(None, "c", context_state=state)
    assert "refusal" not in text and "제외했습니다" in text
    assert len(state["history_chain"]) == 2


@pytest.mark.parametrize("message", [
    "Error: thread/resume: thread/resume failed: no rollout found for thread id " + SID + " (code -32600)",
    "No conversation found with session ID: " + SID,
])
def test_live_cli_missing_session_signatures(runner, message):
    assert runner.decode_session_output({"kind": "codex", "resume": SID}, "", message, 1)[1] == runner._SESSION_MISSING


def test_structured_quota_failure_preserves_cause_without_metadata(runner):
    state = {"kind": "claude"}
    data = json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                       "result": "You have hit your session limit", "session_id": SID})
    ok, answer = runner._run_cli_cancelable([sys.executable, "-c", "import sys;print(sys.argv[1]);sys.exit(1)",data],lambda:False,session_result=state)
    assert not ok and "session limit" in answer and SID not in answer


def test_post_submit_receipt_uses_actual_final_history(history):
    rows, render, _ = history
    path = UNIT / "feature-0003-agent-web-ui/src/routers/ai_tools.py"
    tree = ast.parse(path.read_text())
    submit = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "submit_answer")
    start = next(i for i,n in enumerate(submit.body) if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == "committed_history")
    body = ast.parse("def receipt():\n pass").body[0]
    body.body = submit.body[start:]
    ns = {"delivered":True,"findings":[],"injection_refused":False,
          "_recent_conversation_context":render,"conn":None,"task":{"conversation_id":"c"},
          "task_id":"t1","glossary_stats":{},"review_recorded":False,"JSONResponse":lambda value:value}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[body],type_ignores=[])),str(path),"exec"),ns)
    rows.extend([(1,"user","question",None,{}),(2,"assistant","final",None,{})])
    receipt = ns["receipt"]()["conversation_session"]
    assert len(receipt["history_chain"])==2
    ns["injection_refused"]=True
    assert ns["receipt"]()["conversation_session"]=={}


def test_claim_response_contains_authenticated_binding_contract():
    path = UNIT / "feature-0003-agent-web-ui/src/routers/ai_tools.py"
    tree=ast.parse(path.read_text())
    claim_fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=="claim_request")
    response=next(n for n in claim_fn.body if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=="JSONResponse")
    payload=response.value.args[0]
    contract=next(v for k,v in zip(payload.keys,payload.values) if isinstance(k,ast.Constant) and k.value=="conversation_session")
    code=compile(ast.Expression(contract),str(path),'eval')
    ns={"account_id":10,"history_state":{"history_chain":["a"*64]},"hashlib":hashlib,"json":json,
        "row":[None,None,11,None,None,31,"pinned"],"system_prompt":"rules","scope":{"datasources":["allowed"]},"ctx":{"client_id":"client","session_id":"login1"}}
    first=eval(code,ns)
    assert first["account_id"]==10 and first["history_chain"]==["a"*64]
    assert first==eval(code,ns)
    ns["ctx"]["session_id"]="login2"
    assert eval(code,ns)["context_key"]!=first["context_key"]


def test_non_json_execution_output_cannot_trigger_recreation(runner):
    state = {"kind": "claude", "resume": SID}
    assert runner.decode_session_output(state, "malformed execution output", "Session not found: " + SID, 1)[1] != runner._SESSION_MISSING


def test_actual_claim_payload_reaches_runner_session_binding(runner, monkeypatch):
    path = UNIT / "feature-0003-agent-web-ui/src/routers/ai_tools.py"
    tree = ast.parse(path.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "claim_request")
    response = next(n for n in fn.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                    and isinstance(n.value.func, ast.Name) and n.value.func.id == "JSONResponse")
    code = compile(ast.Expression(response.value.args[0]), str(path), "eval")
    ns = {"account_id": 10, "history_state": {"history_chain": ["a" * 64]},
          "hashlib": hashlib, "json": json, "task_id": "t1", "conversation_id": "conv-real",
          "marked": "question", "marked_history": "", "question": "question",
          "row": [None, None, 11, None, None, 31, "pinned", "codex", "", ""],
          "system_prompt": "rules", "scope": {}, "ctx": {"client_id": "client", "session_id": "login1"},
          "attachments": [], "_tool_catalog": lambda: {}, "kb_context": "", "kb_notes": [],
          "_self_review_directive": lambda question: {}}
    resumes = []
    def ask(*args, **kwargs):
        session = kwargs["session"]
        assert session is not None, "실제 claim 응답의 대화 식별자가 러너에 도달해야 한다"
        resumes.append(session.get("resume"))
        session.update(native_id=SID, completed=True)
        return True, "answer"
    monkeypatch.setattr(runner, "ask_local_ai", ask)
    client = api()
    client.call = lambda *a, **k: {"delivered_to_conversation": True,
                                 "conversation_session": {"history_chain": ns["history_state"]["history_chain"] + ["f" * 64]}}
    for turn in (1, 2):
        payload = eval(code, ns)
        runner.handle_one(client, f"t{turn}", payload, "codex", ["codex", "exec", "{prompt}"], None, self_review=False)
        ns["history_state"]["history_chain"].extend(["f" * 64, "b" * 64])
    assert resumes == [None, SID]
