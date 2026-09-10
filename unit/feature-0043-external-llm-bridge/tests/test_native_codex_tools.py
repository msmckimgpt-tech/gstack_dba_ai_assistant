"""Windows shell restrictions must not prevent authorized DQA read tools."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tomllib

import pytest


@pytest.fixture
def runner():
    path = Path(__file__).resolve().parents[1] / "src" / "bridge_agent.py"
    spec = importlib.util.spec_from_file_location("_native_codex_tools", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("platform,kind,custom,target,expected", [
    ("nt", "codex", None, [r"C:\Apps\codex.exe"], True),
    ("nt", "codex", None, ["wsl.exe", "-e", "/bin/codex"], False),
    ("posix", "codex", None, ["/bin/codex"], False),
    ("nt", "claude", None, ["claude.exe"], False),
    ("nt", "codex", "custom command", ["codex.exe"], False),
])
def test_selected_runtime_controls_transport(runner, monkeypatch, platform, kind, custom, target, expected):
    monkeypatch.setattr(runner, "os", SimpleNamespace(name=platform))
    monkeypatch.setattr(runner, "_resolve_exe", lambda argv: target)
    assert runner.native_codex_tools(kind, custom) is expected


def test_mcp_config_replaces_stale_server_and_limits_delegation(runner):
    original = ["codex", "exec", "question"]
    cmd = runner._with_dqa_mcp(original, "https://dqa.example")
    config = tomllib.loads("\n".join(cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-c"))
    server = config["mcp_servers"]["dqa_task"]
    assert server["url"] == "https://dqa.example/api/ai/mcp"
    assert server["bearer_token_env_var"] == "BRIDGE_TOKEN"
    assert set(server["enabled_tools"]) == {"get_tool_catalog", "run_read_tool", "read_task_attachment"}
    assert server["required"] is True
    assert server["default_tools_approval_mode"] == "prompt"
    assert set(server["tools"]) == set(server["enabled_tools"])
    assert all(v == {"approval_mode": "approve"} for v in server["tools"].values())
    assert "http_headers" not in server
    assert "command" not in server
    assert original == ["codex", "exec", "question"] and cmd[-1] == "question"


@pytest.mark.parametrize("url", ["http://dqa.example", "https://user@dqa.example", "https://dqa.example?x=1", "https://dqa.example/#x"])
def test_mcp_rejects_ambiguous_or_insecure_base(runner, url):
    with pytest.raises(ValueError):
        runner._with_dqa_mcp(["codex", "exec", "question"], url)


def test_mcp_prompt_and_attachment_use_tools_without_shell_or_credentials(runner):
    api = SimpleNamespace(base="https://dqa.example", token="TEST_SECRET")
    task = {"task_id": "t_test", "question": "inspect", "attachments": [{"attachment_id": 12, "filename": 'FGT 한글 "현황".sql'}]}
    prompt = runner.compose_prompt(api, task, tool_transport="mcp")
    assert "dqa_task" in prompt and "get_tool_catalog" in prompt and "run_read_tool" in prompt
    assert "read_task_attachment" in prompt and "t_test" in prompt
    assert 'FGT 한글 "현황".sql' in prompt and "id=12" in prompt
    assert "None" not in prompt
    assert "POST " not in prompt and "Bearer" not in prompt
    assert "TEST_SECRET" not in prompt and "BRIDGE_TOKEN" not in prompt
    assert "tc-" in prompt


def test_required_mcp_failure_has_no_shell_fallback(runner, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "_child_workdir", lambda: None)
    monkeypatch.setattr(runner, "_run_cli_cancelable", lambda cmd, cancel, **kw:
                        (calls.append((cmd, kw)) or (False, "required MCP server denied")))
    result = runner.ask_local_ai("codex", ["codex", "exec", "{prompt}"], "question", None,
                                 token="TEST_SECRET", api_base="https://dqa.example", tool_mcp=True)
    assert result == (False, "required MCP server denied") and len(calls) == 1
    cmd, kwargs = calls[0]
    assert "features.network_proxy=true" in cmd
    assert any("extends=\":read-only\"" in arg for arg in cmd)
    assert any(arg.startswith("mcp_servers=") for arg in cmd)
    assert "TEST_SECRET" not in repr(cmd)
    assert kwargs["env"]["BRIDGE_TOKEN"] == "TEST_SECRET"


@pytest.fixture(scope="module")
def ca_pair(tmp_path_factory):
    import subprocess
    root = tmp_path_factory.mktemp("native-mcp-ca")
    paths = []
    for name in ("original", "dqa"):
        cert, key = root / (name + ".pem"), root / (name + ".key")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=" + name, "-keyout", str(key), "-out", str(cert)],
                       check=True, capture_output=True)
        paths.append(cert)
    return paths


@pytest.mark.parametrize("previous_key", ["CODEX_CA_CERTIFICATE", "SSL_CERT_FILE"])
def test_ca_merge_preserves_trust_parent_and_cleans_up(runner, ca_pair, previous_key):
    import ssl
    old, dqa = ca_pair
    env = {previous_key: str(old), "BRIDGE_CA": str(dqa), "BRIDGE_TOKEN": "TEST_SECRET"}
    before = dict(env)
    with runner._codex_mcp_ca(env, True) as child:
        bundle = Path(child["CODEX_CA_CERTIFICATE"])
        actual = set(ssl.create_default_context(cafile=str(bundle)).get_ca_certs(binary_form=True))
        expected = set().union(*(ssl.create_default_context(cafile=str(p)).get_ca_certs(binary_form=True)
                                 for p in ca_pair))
        assert actual == expected and len(actual) == 2
        assert "PRIVATE KEY" not in bundle.read_text() and "TEST_SECRET" not in bundle.read_text()
        assert child[previous_key] == str(old) if previous_key == "SSL_CERT_FILE" else bundle != old
        assert env == before
    assert not bundle.exists()


def test_ca_lifecycle_is_independent_between_tasks(runner, ca_pair):
    first, second = ca_pair
    env = {"CODEX_CA_CERTIFICATE": str(first), "BRIDGE_CA": str(second)}
    with runner._codex_mcp_ca(env, True) as child1:
        one = Path(child1["CODEX_CA_CERTIFICATE"])
        with runner._codex_mcp_ca(env, True) as child2:
            two = Path(child2["CODEX_CA_CERTIFICATE"])
            assert one != two and one.exists() and two.exists()
        assert one.exists() and not two.exists()
    assert not one.exists()


def test_invalid_ca_stops_before_cli_and_leaves_other_transports_alone(runner, monkeypatch, tmp_path):
    bad = tmp_path / "bad.pem"
    bad.write_text("not a certificate")
    monkeypatch.setattr(runner, "_run_cli_cancelable", lambda *a, **k: pytest.fail("invalid CA reached CLI"))
    ok, answer = runner.ask_local_ai("codex", ["codex", "exec", "{prompt}"], "question", None,
                                     token="TEST_SECRET", api_base="https://dqa.example", api_ca=str(bad),
                                     tool_mcp=True)
    assert not ok and "인증서" in answer
    env = {"BRIDGE_CA": str(bad)}
    with runner._codex_mcp_ca(env, False) as same:
        assert same is env


def test_handler_wires_selected_mcp_prompt_and_invocation(runner, monkeypatch):
    calls, submitted = [], []
    monkeypatch.setattr(runner, "native_codex_tools", lambda kind, custom: kind == "codex" and not custom)
    monkeypatch.setattr(runner, "_which_ai", lambda name: "/bin/" + name)
    monkeypatch.setattr(runner, "ask_local_ai", lambda kind, argv, prompt, custom, *a, **kw:
                        (calls.append((prompt, kw)) or (True, "VERIFIED_RESULT")))
    api = SimpleNamespace(base="https://dqa.example", token="TEST_SECRET", ca=None,
                          call=lambda name, payload, **kwargs: (submitted.append((name, payload)) or
                                                               {"delivered_to_conversation": True}))
    assert runner.handle_one(api, "t_test", {"question": "inspect data"}, "codex",
                             runner._RUNTIME_SPECS["codex"]["argv"], None, self_review=False)
    assert calls[0][1]["tool_mcp"] is True and "dqa_task" in calls[0][0]
    assert "POST " not in calls[0][0]
    assert next(p["answer"] for n, p in submitted if n == "submit_answer") == "VERIFIED_RESULT"


def test_session_resume_retains_required_mcp_and_token_scope(runner, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "_child_workdir", lambda: None)
    monkeypatch.setattr(runner, "_run_cli_cancelable", lambda cmd, cancel, **kw:
                        (calls.append((cmd, kw)) or (True, "answer")))
    session = {"kind": "codex", "resume": "00000000-0000-4000-8000-000000000001"}
    runner.ask_local_ai("codex", ["codex", "exec", "{prompt}"], "question", None,
                        token="TEST_SECRET", api_base="https://dqa.example", tool_mcp=True, session=session)
    cmd, kw = calls[0]
    assert cmd[1:3] == ["exec", "resume"]
    assert any(arg.startswith("mcp_servers=") for arg in cmd)
    assert kw["session_result"] is session and kw["env"]["BRIDGE_TOKEN"] == "TEST_SECRET"


def test_ca_merge_preserves_explicit_non_ca_trust_anchor(runner, ca_pair, tmp_path):
    import ssl
    import subprocess
    pinned, key = tmp_path / "pinned.pem", tmp_path / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=pinned", "-addext", "basicConstraints=critical,CA:FALSE",
                    "-keyout", str(key), "-out", str(pinned)], check=True, capture_output=True)
    assert not ssl.create_default_context(cafile=str(pinned)).get_ca_certs()
    certificate = pinned.read_text()
    pinned.write_text(certificate + key.read_text())
    with runner._codex_mcp_ca({"CODEX_CA_CERTIFICATE": str(pinned),
                                "BRIDGE_CA": str(ca_pair[1])}, True) as env:
        contents = Path(env["CODEX_CA_CERTIFICATE"]).read_text()
        assert certificate.strip() in contents
        assert ca_pair[1].read_text().strip() in contents
        assert "PRIVATE KEY" not in contents


def test_ca_merge_preserves_openssl_trust_attributes(runner, ca_pair, tmp_path):
    import subprocess
    trusted = tmp_path / "trusted.pem"
    subprocess.run(["openssl", "x509", "-in", str(ca_pair[0]), "-addtrust", "serverAuth",
                    "-trustout", "-out", str(trusted)], check=True, capture_output=True)
    assert "BEGIN TRUSTED CERTIFICATE" in trusted.read_text()
    with runner._codex_mcp_ca({"CODEX_CA_CERTIFICATE": str(trusted),
                                "BRIDGE_CA": str(ca_pair[1])}, True) as env:
        contents = Path(env["CODEX_CA_CERTIFICATE"]).read_text()
        assert trusted.read_text().strip() in contents
        assert ca_pair[1].read_text().strip() in contents
