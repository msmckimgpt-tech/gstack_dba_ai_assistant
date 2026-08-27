"""feature-0043 — 대화 제목과 실행 단계가 브리지 경로에서도 **기존과 같은 모양**인가.

라이브 제보(2026-08-27, 스크린샷 동반):

| 증상 | 원인 |
|---|---|
| 대화 제목이 계속 "새 대화" | 서버 LLM 경로의 `agent_core._try_update_topic` 을 브리지가 타지 않는다 |
| 실행 단계에 사유가 없고 문구가 뭉뚱그려짐 | 단계를 **원장에서** 만들어 인자·사유가 애초에 없었다 |

두 결함 모두 계산이 아니라 **연결**이 없어서 생긴다 — 헬퍼는 전부 정상이고 단위 테스트도 통과한다
(feature-0043 이 이미 한 번 겪은 실패 형태다). 그래서 여기서도 **배선을 단정**한다: 진입점이 그
헬퍼를 실제로 부르는가, 도구 스키마가 사유를 받을 자리를 갖고 있는가.

순수 함수(`bridge_agent.split_title`)만 값으로 검사한다 — 표준 라이브러리만 쓰므로 실행 가능하다.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]

WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
AI_TOOLS = WEB_SRC / "routers" / "ai_tools.py"
CONVS = WEB_SRC / "routers" / "conversations.py"
CONV_STORE = WEB_SRC / "routers" / "_conv_store.py"
APP_PY = WEB_SRC / "app.py"
MCP_STDIO = _UNIT / "feature-0041-external-ai-tool-surface" / "src" / "external_tool_mcp_server.py"
MCP_HTTP = _UNIT / "feature-0041-external-ai-tool-surface" / "src" / "external_tool_mcp_http.py"
RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"

#: 웹 대화 질문을 조사할 때 개인 AI 가 쓰는 도구들. 여기 있는 것은 전부 사용자 화면의
#: 「실행 단계」로 그려지므로, 사유를 받을 자리(`reason`)가 있어야 한다.
_INVESTIGATION_TOOLS = (
    "get_task_context", "read_task_attachment", "list_schemas", "describe_schema",
    "describe_table", "search_tables", "get_foreign_keys", "get_table_indexes", "execute_sql",
)


def _func_source(path: pathlib.Path, name: str) -> str:
    """모듈에서 함수 하나의 소스만 떼어낸다(파일 전역 검색이 남의 코드를 오검출하지 않게)."""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{path.name}: 함수 {name} 를 찾지 못했다(이름이 바뀌었나?)")


def _params(path: pathlib.Path, name: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            args = node.args
            return [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    raise AssertionError(f"{path.name}: 함수 {name} 를 찾지 못했다")


def _load_runner():
    spec = importlib.util.spec_from_file_location("_bridge_agent_under_test", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# ── 제목 축 ───────────────────────────────────────────────────────────────────


def test_enqueue_sets_topic_from_question():
    """질문을 적재하는 그 자리에서 제목이 붙는가.

    답변까지 미루면 전송 직후의 사이드바에 "새 대화" 만 여러 줄 쌓여 서로 구분되지 않는다.
    """
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert "_conv_apply_auto_topic" in src, (
        "브리지 적재 경로가 자동 제목을 붙이지 않는다 — 대화 제목이 '새 대화' 로 굳는다")
    # 연결이 없어 적재를 건너뛰는 분기에서도 질문은 저장된다 → 제목도 붙어야 한다.
    assert src.count("_conv_apply_auto_topic") >= 2, (
        "AI 미연결 분기에 제목 적용이 없다 — 질문만 쌓이고 목록에서 구분되지 않는다")


def test_submit_answer_forwards_title_to_delivery():
    """개인 AI 가 제안한 제목이 전달 경로까지 흘러가는가(중간에서 삼켜지지 않는가)."""
    submit = _func_source(AI_TOOLS, "submit_answer")
    assert 'body.get("title")' in submit, "submit_answer 가 title 을 읽지 않는다"
    assert "title=" in submit, "title 이 _deliver_web_bridge_answer 로 전달되지 않는다"

    deliver = _func_source(AI_TOOLS, "_deliver_web_bridge_answer")
    assert "title" in _params(AI_TOOLS, "_deliver_web_bridge_answer"), (
        "_deliver_web_bridge_answer 가 title 을 받지 않는다")
    assert "_conv_apply_auto_topic" in deliver, "제안된 제목이 대화에 반영되지 않는다"
    assert "supersedes=" in deliver, (
        "supersedes 없이 덮어쓰면 **사용자가 손으로 바꾼 제목**까지 답변마다 지워진다")


def test_auto_topic_helper_protects_manual_titles():
    """자동 제목은 placeholder 이거나 '우리가 붙인 제목' 위에만 얹힌다."""
    src = _func_source(CONV_STORE, "_conv_apply_auto_topic")
    assert "_PLACEHOLDER_TOPICS" in src, "placeholder 판정 없이 무조건 덮어쓴다"
    assert "supersedes" in src, "직전 자동 제목을 승급시킬 경로가 없다"
    assert "save_memory_kv" in src, (
        "kv 'topic' 을 함께 쓰지 않으면 목록과 상세가 서로 다른 제목을 말한다")


def test_auto_topic_guard_is_inside_the_update_statement():
    """보호 조건이 `WHERE` 에 있는가 — 읽고-판단-쓰기로 나누면 그 사이가 새는가.

    나뉘어 있으면 (a) 조회 직후 사용자가 제목을 바꾼 경우와 (b) 조회만 실패해 placeholder 로
    오인한 경우 모두 **사용자 제목이 지워진다**(codex REV-20260828T040000 P1). 조건을 UPDATE
    안에 두면 두 경우 다 행이 안 잡혀 아무 일도 일어나지 않는다.
    """
    src = _func_source(CONV_STORE, "_conv_update_topic_if_auto")
    assert "UPDATE agent_runtime.core_conversations" in src and "WHERE conversation_id" in src
    assert "rowcount" in src, "갱신 여부를 rowcount 로 판정하지 않는다(적용됐다고 단정)"
    apply_src = _func_source(CONV_STORE, "_conv_apply_auto_topic")
    assert "_conv_load_topic" not in apply_src, (
        "여전히 현재 제목을 먼저 읽는다 — 그 사이가 TOCTOU 창이다")


def test_auto_topic_helpers_are_exported_to_app():
    """라우터들은 `app.X` 로 부른다 — app.py 에 재수출되지 않으면 런타임에 AttributeError."""
    src = APP_PY.read_text(encoding="utf-8")
    for name in ("_conv_apply_auto_topic", "_clean_auto_topic"):
        assert name in src, f"app.py 가 {name} 를 재수출하지 않는다(런타임 배선 끊김)"


@pytest.mark.parametrize("answer,expect_body,expect_title", [
    ("본문입니다.\n#TITLE: 파티션 자동화 점검", "본문입니다.", "파티션 자동화 점검"),
    ("본문입니다.\n#title: 소문자도 허용", "본문입니다.", "소문자도 허용"),
    ('본문입니다.\n#TITLE: "따옴표 제거"', "본문입니다.", "따옴표 제거"),
    ("마커가 없다", "마커가 없다", ""),
    # 중간에 등장하는 같은 문자열은 답변 내용이지 제목이 아니다.
    ("#TITLE: 이건 본문\n실제 마지막 줄", "#TITLE: 이건 본문\n실제 마지막 줄", ""),
    # `#` 없는 정상 마지막 줄을 제목으로 오인해 **본문에서 지우면** 안 된다(codex P2).
    ("본문입니다.\nTitle: 실제 데이터 열", "본문입니다.\nTitle: 실제 데이터 열", ""),
    # 제목 줄이 전부면 떼지 않는다 — 떼면 빈 답변이 되어 제출이 400 으로 거절된다.
    ("#TITLE: 제목만 왔다", "#TITLE: 제목만 왔다", ""),
])
def test_runner_splits_title_without_damaging_answer(answer, expect_body, expect_title):
    """규약을 안 지키는 런타임이 있어도 **답변은 상하지 않는다**(제목만 없을 뿐)."""
    mod = _load_runner()
    body, title = mod.split_title(answer)
    assert body == expect_body
    assert title == expect_title


def test_runner_prompt_asks_for_title_and_reason():
    src = RUNNER.read_text(encoding="utf-8")
    assert "_TITLE_MARK" in src and "split_title" in src
    # 프롬프트 안의 JSON 예시라 소스에는 이스케이프된 형태로 있다.
    assert '\\"reason\\"' in src, "러너 프롬프트가 도구 호출 사유를 요구하지 않는다"
    # 제출 payload 에 실려야 서버가 받는다(프롬프트만 고치고 배선을 빼먹는 실패 방지).
    submit = _func_source(RUNNER, "handle_one")
    assert 'payload["title"]' in submit, "떼어낸 제목이 제출 payload 에 실리지 않는다"


# ── 실행 단계 축 ──────────────────────────────────────────────────────────────


def test_structure_tool_records_step_at_call_time():
    """도구를 실행한 **그 시점에** 단계를 남기는가 — 인자와 사유를 둘 다 가진 유일한 순간."""
    src = _func_source(AI_TOOLS, "run_structure_tool")
    assert "_bridge_step_narration" in src, "개인 AI 가 보낸 사유를 꺼내지 않는다"
    assert "_record_bridge_step" in src, "도구 호출이 실행 단계로 남지 않는다"
    assert "step_args" in src, (
        "실행 전 인자 사본이 없다 — execute_tool 이 datasource 를 pop 하므로 화면 문구가 빈다")


def test_recorded_step_carries_work_and_reason():
    """단계에 「어떤 이유로 → 어떤 작업」 두 축이 모두 실리는가."""
    src = _func_source(AI_TOOLS, "_record_bridge_step")
    assert "_build_step_payload" in src, (
        "내부 경로와 같은 payload 빌더를 쓰지 않는다 — 결과 요약·미리보기 형태가 갈린다")
    assert "work_text=" in src and "reason_text=" in src, "work/reason 이 저장되지 않는다"
    assert "external-ai" in src and "derived" in src, (
        "출처 구분이 없다 — AI 가 말한 사유와 서버가 파생한 사유를 화면이 구분하지 못한다")


def test_step_index_is_assigned_atomically():
    """번호 채번과 적재가 같은 트랜잭션인가.

    따로 조회한 뒤 다른 연결로 INSERT 하면, 도구 두 개를 동시에 부른 AI 의 단계가 같은 번호로
    저장되고 증분 폴링(`step_index > after_step`)이 뒤늦게 커밋된 행을 영구히 건너뛴다
    (codex REV-20260828T040000 P1).
    """
    src = _func_source(AI_TOOLS, "_insert_bridge_step")
    assert "pg_advisory_xact_lock" in src, "run 단위 직렬화가 없다 — 번호가 겹친다"
    assert "COALESCE(MAX(s.step_index), 0) + 1" in src, (
        "채번이 INSERT 문 안에 없다 — 조회와 적재 사이가 갈린다")
    # 락을 잡고도 별도 연결로 INSERT 하면 의미가 없다(같은 커서에서 끝나야 한다).
    assert src.index("pg_advisory_xact_lock") < src.index("INSERT INTO agent_runtime.steps")


def test_narration_is_stripped_from_tool_arguments():
    """narration 은 조사 인자가 아니다 — 남겨두면 execute_tool 이 모르는 인자를 받는다."""
    src = _func_source(AI_TOOLS, "_bridge_step_narration")
    assert "arguments.pop" in src, "narration 을 인자에서 제거하지 않는다"


def test_derived_narration_reuses_internal_helpers():
    """문구를 새로 짓지 않는다 — 같은 도구가 경로에 따라 다르게 표현되면 한쪽은 반드시 낡는다."""
    src = _func_source(AI_TOOLS, "_bridge_derived_narration")
    assert "_derive_step_work" in src and "_derive_step_reason" in src


def test_ledger_materialization_is_now_a_fallback():
    """호출 시점 기록이 있으면 원장 이관은 돌지 않는다(같은 조사가 두 벌로 보이면 안 된다)."""
    src = _func_source(AI_TOOLS, "_materialize_bridge_steps")
    assert "FROM agent_runtime.steps" in src and "LIMIT 1" in src, (
        "기존 단계 존재 검사가 없다 — 제출 시점에 단계가 중복 적재된다")
    # fallback 이더라도 사유 칸을 비워두지 않는다(그게 원래 결함이었다).
    assert "work_text" in src and "reason_text" in src, (
        "이관 경로가 여전히 사유 없는 단계를 만든다")
    # 사후 기록 표식은 그대로 유지해야 한다 — `_conv_store._BRIDGE_LEDGER_WORK_SOURCE` 가
    # 이 값으로 "끝난 답변" 을 걸러 진행 중 run 추론에서 뺀다. 바꾸면 끝난 답변이 '진행 중'
    # 으로 보인다(병렬 세션 #1370 이 세운 계약).
    assert "'bridge-ledger'" in src, (
        "사후 기록 표식이 사라졌다 — 진행 중 run 제외가 조용히 무효가 된다")


# ── 도구 스키마 축 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("adapter", [MCP_STDIO, MCP_HTTP], ids=["stdio", "http"])
@pytest.mark.parametrize("tool", _INVESTIGATION_TOOLS)
def test_mcp_tools_accept_reason(adapter: pathlib.Path, tool: str):
    """도구가 사유를 받을 자리를 갖고 있는가.

    서버가 받을 준비만 하고 스키마에 인자가 없으면, 개인 AI 에게 그 필드는 **존재하지 않는다** —
    보낼 방법이 없으니 사유는 영원히 서버 파생값이다.
    """
    assert "reason" in _params(adapter, tool), (
        f"{adapter.name}: {tool} 에 reason 인자가 없다 — 개인 AI 가 사유를 보낼 방법이 없다")


@pytest.mark.parametrize("adapter", [MCP_STDIO, MCP_HTTP], ids=["stdio", "http"])
def test_mcp_tools_forward_reason_to_server(adapter: pathlib.Path):
    """인자를 받기만 하고 본문에 안 실으면 배선이 끊긴 것과 같다."""
    for tool in _INVESTIGATION_TOOLS:
        src = _func_source(adapter, tool)
        assert '"reason": reason' in src, (
            f"{adapter.name}: {tool} 이 reason 을 서버로 전달하지 않는다")


@pytest.mark.parametrize("adapter", [MCP_STDIO, MCP_HTTP], ids=["stdio", "http"])
def test_mcp_submit_answer_accepts_title(adapter: pathlib.Path):
    assert "title" in _params(adapter, "submit_answer"), (
        f"{adapter.name}: submit_answer 에 title 이 없다 — 맥락 제목 제안 경로가 없다")
    assert '"title": title' in _func_source(adapter, "submit_answer"), (
        f"{adapter.name}: title 이 서버로 전달되지 않는다")


@pytest.mark.parametrize("adapter", [MCP_STDIO, MCP_HTTP], ids=["stdio", "http"])
def test_tool_descriptions_tell_the_ai_to_send_reason(adapter: pathlib.Path):
    """스키마에 자리만 있고 설명이 없으면 AI 는 채우지 않는다(선택 인자는 대개 비어 온다)."""
    src = adapter.read_text(encoding="utf-8")
    assert "_REASON_HINT" in src, f"{adapter.name}: 사유 요청 안내가 도구 설명에 없다"
