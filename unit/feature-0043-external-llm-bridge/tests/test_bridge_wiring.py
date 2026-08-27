"""feature-0043 — codex 리뷰 P1·P2 수정의 **배선** 회귀 (REV-20260826T142000).

이 스위트가 잠그는 것은 "함수가 올바른가" 가 아니라 **"그 함수가 실제로 그 자리에 배선돼
있는가"** 다. 리뷰가 잡은 5건 중 4건이 정확히 배선 결함이었다 — 로직은 맞는데 호출되지 않거나
(P1-1 어댑터 미등록), 잘못된 순서에 있거나(P1-2 쿼터 뒤), 결과가 버려졌다(P1-3 필드 유실).
헬퍼를 직접 호출하는 테스트는 그런 결함을 구조적으로 못 본다.

라우터를 import 해 실행하는 대신 **소스를 AST/텍스트로 검사**하는 이유: 이 저장소에서
feature-0002 와 feature-0003 은 둘 다 최상위 `modules` 패키지를 갖고 있어 한 프로세스에서
동시에 import 할 수 없다(conftest 주석 참조). 배선은 소스에 드러나므로 그 층에서 잠근다.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]

WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
TOOLS_PY = WEB_SRC / "routers" / "ai_tools.py"
CONV_PY = WEB_SRC / "routers" / "conversations.py"
SCHEMA_PY = WEB_SRC / "routers" / "_bootstrap_schema.py"
COMPOSER_JS = WEB_SRC / "static" / "app" / "composer.js"

MCP_SRC = _UNIT / "feature-0041-external-ai-tool-surface" / "src"
MCP_HTTP = MCP_SRC / "external_tool_mcp_http.py"
MCP_STDIO = MCP_SRC / "external_tool_mcp_server.py"

BRIDGE_TOOLS = ("list_open_requests", "claim_request")


def _tree(path: pathlib.Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _func(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    pytest.fail(f"함수 {name} 를 찾을 수 없다")


def _src(node: ast.AST, path: pathlib.Path) -> str:
    return ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""


# ── P1-1: 어댑터 등록 (주 접근 경로) ─────────────────────────────────────────


@pytest.mark.parametrize("tool", BRIDGE_TOOLS)
def test_http_mcp_adapter_registers_bridge_tools(tool):
    """`/api/ai/mcp`(무설치 주 경로)에 도구가 노출된다.

    REST 라우트만 추가하고 어댑터를 빠뜨리면 URL+토큰만 등록한 사용자에게는 **대기 질문이
    존재하지 않는 것과 같다** — 이 feature 의 핵심 요구가 조용히 죽는다.
    """
    names = {
        n.name for n in ast.walk(_tree(MCP_HTTP))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert tool in names, f"HTTP MCP 어댑터에 {tool} 미등록"


@pytest.mark.parametrize("tool", BRIDGE_TOOLS)
def test_stdio_mcp_adapter_registers_bridge_tools(tool):
    """stdio 어댑터도 같은 도구 집합을 노출한다(두 전송의 계약 일치)."""
    text = MCP_STDIO.read_text(encoding="utf-8")
    names = {
        n.name for n in ast.walk(_tree(MCP_STDIO))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert tool in names, f"stdio MCP 어댑터에 {tool} 함수 없음"
    # 정의만 하고 `_register` 를 안 부르면 등록되지 않는다 — 정의 ≠ 노출.
    assert f'_register("{tool}"' in text, f"stdio 어댑터가 {tool} 를 _register 하지 않는다"


def test_rest_routes_exist_for_bridge_tools():
    """REST 정본에도 두 도구가 있다(`curl` 만으로 전 구간 가능해야 한다 — AC-9)."""
    text = TOOLS_PY.read_text(encoding="utf-8")
    for tool in BRIDGE_TOOLS:
        assert f'@router.post("/api/ai/tools/{tool}")' in text, f"REST 라우트 {tool} 없음"


def test_bridge_tools_registered_before_catchall():
    """구체 라우트가 catch-all(`{tool_name}`)보다 **앞에** 등록된다.

    FastAPI 는 등록 순서로 매칭한다 — 뒤에 있으면 catch-all 이 먼저 잡아 404 를 낸다.
    """
    text = TOOLS_PY.read_text(encoding="utf-8")
    catchall = text.index('@router.post("/api/ai/tools/{tool_name}")')
    for tool in BRIDGE_TOOLS:
        assert text.index(f'@router.post("/api/ai/tools/{tool}")') < catchall, (
            f"{tool} 라우트가 catch-all 뒤에 있다"
        )


# ── P1-2: 쿼터 게이트가 브리지를 막지 않는다 ─────────────────────────────────


def test_llm_quota_gate_is_conditional_on_server_llm():
    """계정 **LLM 토큰** 한도가 브리지 요청을 막지 않는다.

    브리지는 우리 계정 토큰을 한 개도 쓰지 않는다. 무조건 게이트면 쿼터 소진 시 브리지까지
    429 가 되어, 쿼터 소진을 벗어나려 만든 전환이 바로 그 쿼터에 막힌다(P1-2).
    """
    text = CONV_PY.read_text(encoding="utf-8")
    idx = text.index("_check_account_token_quota")
    window = text[max(0, idx - 800):idx]
    assert "_server_llm_enabled()" in window, (
        "쿼터 게이트가 서버 LLM 활성 여부로 조건부화되지 않았다"
    )


def test_bridge_branch_precedes_dispatch():
    """브리지 분기가 `_dispatch_ask_run` **앞에** 있다 — 워커 enqueue·슬롯 점유 전에 갈라진다."""
    text = CONV_PY.read_text(encoding="utf-8")
    assert text.index("_enqueue_web_bridge_task(") < text.index("app._dispatch_ask_run(")


# ── P1-3: 반환 계약 ──────────────────────────────────────────────────────────


def test_bridge_enqueue_returns_contract_fields():
    """성공 반환에 `conversation_id`·`bridge_pending`·`bridge_task_id` 가 있다."""
    src = _src(_func(_tree(CONV_PY), "_enqueue_web_bridge_task"), CONV_PY)
    for key in ('"conversation_id"', '"bridge_pending"', '"bridge_task_id"'):
        assert key in src, f"브리지 반환에 {key} 없음"


def test_bridge_enqueue_failure_carries_http_status():
    """적재 실패가 **HTTP 200 으로 나가지 않는다** — dispatch 표준 실패 경로로 보낸다."""
    src = _src(_func(_tree(CONV_PY), "_enqueue_web_bridge_task"), CONV_PY)
    assert '"_http_status": 500' in src, "적재 실패에 _http_status 가 없다(200 으로 나간다)"


def test_ask_response_propagates_bridge_flags():
    """최종 JSON 조립이 브리지 플래그를 응답에 싣는다 — 떨어뜨리면 프런트가 폴링하지 않는다."""
    text = CONV_PY.read_text(encoding="utf-8")
    assert 'result["bridge_pending"] = True' in text
    assert 'result["bridge_task_id"]' in text


# ── P1-4: 사용자 메시지 · 대화 문맥 ──────────────────────────────────────────


def test_bridge_saves_user_message():
    """사용자 질문이 대화에 저장된다 — 기존 경로에서는 agent_core 가 하던 일이다."""
    src = _src(_func(_tree(CONV_PY), "_enqueue_web_bridge_task"), CONV_PY)
    assert "save_memory_message" in src, "브리지가 사용자 메시지를 저장하지 않는다"
    assert '"user"' in src


def test_claim_request_includes_conversation_context():
    """`claim_request` 가 이전 대화 문맥을 함께 준다 — 후속 질문은 앞 turn 없이 해석 불가."""
    src = _src(_func(_tree(TOOLS_PY), "claim_request"), TOOLS_PY)
    assert "_recent_conversation_context(" in src
    assert '"conversation_context"' in src


def test_conversation_context_is_marked():
    """대화 문맥도 나가는 데이터이므로 각인 규약을 탄다(L2 구획 유지)."""
    src = _src(_func(_tree(TOOLS_PY), "claim_request"), TOOLS_PY)
    assert "wrap_tool_output" in src


# ── P1-5: 점유 롤백 ──────────────────────────────────────────────────────────


def test_claim_releases_on_ledger_failure():
    """원장 실패 시 점유를 되돌린다 — 일시 장애 한 번이 질문을 영구 고착시키지 않는다."""
    src = _src(_func(_tree(TOOLS_PY), "claim_request"), TOOLS_PY)
    assert "LedgerUnavailable" in src
    assert "_release_claim(" in src, "원장 실패 경로에서 점유를 해제하지 않는다"


def test_release_claim_preserves_submitted_tasks():
    """해제는 `Status='open'` 인 것만 — 제출된 작업을 되살리면 확정 불변이 깨진다."""
    src = _src(_func(_tree(TOOLS_PY), "_release_claim"), TOOLS_PY)
    assert "Status='open'" in src or 'Status = \'open\'' in src


# ── P2-1: 제출 소유권 ────────────────────────────────────────────────────────


def test_submit_answer_requires_claim_for_web_tasks():
    """web task 는 **점유자만** 제출한다 — 아니면 원자적 claim 이 장식이 된다."""
    src = _src(_func(_tree(TOOLS_PY), "submit_answer"), TOOLS_PY)
    assert "Origin <> 'web' OR (ClaimedBy" in src, (
        "submit_answer 가 ClaimedBy 를 검사하지 않는다"
    )


# ── P2-2 / P2-3: 스키마 ──────────────────────────────────────────────────────


@pytest.mark.parametrize("col", ["Origin", "ClaimedBy", "ClaimedAt"])
def test_create_table_includes_bridge_columns(col):
    """신규 설치가 ALTER 없이 완성된다 — CREATE TABLE 에 컬럼이 있다."""
    text = SCHEMA_PY.read_text(encoding="utf-8")
    create_start = text.index("CREATE TABLE IF NOT EXISTS WebAiTasks")
    create_end = text.index("ENGINE=InnoDB", create_start)
    assert col in text[create_start:create_end], f"CREATE TABLE 에 {col} 없음"


def test_bridge_polling_index_exists():
    """폴링 전용 복합 인덱스가 CREATE TABLE 과 마이그레이션 양쪽에 있다."""
    text = SCHEMA_PY.read_text(encoding="utf-8")
    assert text.count("IX_WebAiTasks_Bridge") >= 2, (
        "브리지 인덱스가 신규 설치·기존 설치 양쪽에 있지 않다"
    )
    assert "AccountId, Origin, Status, ClaimedBy, CreatedAt" in text


def test_bridge_ddl_is_online():
    """추가된 DDL 이 online 절을 갖는다(CONVENTIONS §13.1 — 조용한 락 금지)."""
    text = SCHEMA_PY.read_text(encoding="utf-8")
    idx = text.index("ADD INDEX IX_WebAiTasks_Bridge")
    assert "ALGORITHM=INPLACE, LOCK=NONE" in text[idx:idx + 400]


# ── 프론트 배선 ──────────────────────────────────────────────────────────────


def test_frontend_consumes_bridge_pending():
    """프런트가 `bridge_pending` 을 읽어 폴링을 시작한다 — 안 읽으면 화면이 영영 갱신 안 된다."""
    text = COMPOSER_JS.read_text(encoding="utf-8")
    assert "payload.bridge_pending" in text
    assert "_pollBridgeAnswer(" in text
    assert "/api/ai/bridge_status" in text


def test_bridge_status_endpoint_is_session_authenticated():
    """상태 엔드포인트는 **웹 세션** 인증이다(외부 토큰으로 도달 불가) + 계정 스코프."""
    src = _src(_func(_tree(TOOLS_PY), "bridge_status"), TOOLS_PY)
    assert "_require_account(" in src, "웹 세션 인증을 거치지 않는다"
    assert "AccountId=%s" in src, "계정 스코프가 없다"
    assert "require_ai_token" not in src, "외부 OAuth 토큰 경로로 열려 있다"


def test_bridge_status_does_not_leak_answer_body():
    """상태 API 는 답변 **본문을 싣지 않는다** — 각인 블록이 두 경로로 새면 규약이 갈린다."""
    src = _src(_func(_tree(TOOLS_PY), "bridge_status"), TOOLS_PY)
    assert "Answer" not in src.replace("answered", "").replace("Answered", ""), (
        "상태 API 가 답변 본문 컬럼을 조회한다"
    )


# ══════════════════════════════════════════════════════════════════════════════
# codex 재리뷰(REV-20260827T…) 조치 — 상태 전이·장애·권한 축
#
# 1차 조치 뒤 재리뷰가 지적한 것: "핵심 회귀 테스트가 대부분 AST/문자열 배선 검사라 상태 전이·
# 장애·권한 결함을 검출하지 못한다." 맞는 지적이다. 아래는 그 축을 겨냥한다 — 여전히 소스
# 층이지만(두 feature 의 `modules` 충돌로 라우터 동시 import 불가), **검사 대상이 배선이
# 아니라 조건·순서·실패 경로**다.
# ══════════════════════════════════════════════════════════════════════════════


def test_poll_uses_history_reload_not_select_conversation():
    """폴링 성공 시 **현재 대화의 history 를 재조회**한다.

    `selectConversation()` 은 이미 활성인 대화면 즉시 return 하도록 설계돼 있어(읽음처리만),
    답변이 저장돼 있어도 화면이 갱신되지 않는다 — 폴링은 성공하고 토스트까지 뜨는데 답변은
    보이지 않는 상태가 된다.
    """
    text = COMPOSER_JS.read_text(encoding="utf-8")
    poll_start = text.index("async function _pollBridgeAnswer")
    poll_body = text[poll_start:poll_start + 2500]
    assert "loadHistory(" in poll_body, "폴링이 history 를 재조회하지 않는다"
    # 주석 안의 설명(왜 쓰면 안 되는지)은 통과시키고 **실제 호출**만 잡는다.
    calls = [ln for ln in poll_body.split("\n")
             if "selectConversation(" in ln and not ln.strip().startswith("//")]
    assert calls == [], (
        "폴링이 selectConversation 을 호출한다 — 활성 대화에서 no-op 이라 화면이 갱신되지 않는다"
    )


def test_poll_stops_on_4xx():
    """4xx 는 재시도 대상이 아니다 — 세션 만료·삭제된 task 에서 30분간 두드리지 않는다."""
    text = COMPOSER_JS.read_text(encoding="utf-8")
    poll_start = text.index("async function _pollBridgeAnswer")
    poll_body = text[poll_start:poll_start + 2500]
    assert "code >= 400 && code < 500" in poll_body


def test_claim_lease_predicate_is_shared():
    """`list_open_requests` 와 `claim_request` 가 **같은 점유가능 술어**를 쓴다.

    두 곳이 갈리면 "목록엔 보이는데 집으면 409" 또는 그 반대가 생긴다.
    """
    text = TOOLS_PY.read_text(encoding="utf-8")
    assert "_CLAIMABLE_SQL" in text
    # 정의 1 + 사용 2 이상
    assert text.count("_CLAIMABLE_SQL") >= 3, "점유가능 술어가 공유되지 않는다"
    assert "ClaimedAt < DATE_SUB(NOW(), INTERVAL" in text, "lease 만료 조건이 없다"


def test_claim_lease_has_bounded_window():
    """lease 가 상수로 고정돼 있다 — 무한 점유가 아니다."""
    text = TOOLS_PY.read_text(encoding="utf-8")
    assert "_BRIDGE_CLAIM_LEASE_MIN" in text


def test_claim_revalidates_conversation_access():
    """claim 이 대화 접근 권한을 **재검증**한다 — 질문 이후 권한 변화를 반영한다."""
    src = _src(_func(_tree(TOOLS_PY), "claim_request"), TOOLS_PY)
    assert "_conversation_access_denied(" in src
    # 거부 시 점유를 되돌려야 lease 만료까지 사라지지 않는다.
    assert "_release_claim(" in src


def test_submit_revalidates_conversation_access_before_write():
    """submit 이 대화에 **쓰기 전에** 권한을 재검증한다."""
    src = _src(_func(_tree(TOOLS_PY), "submit_answer"), TOOLS_PY)
    assert "_conversation_access_denied(" in src
    assert src.index("_conversation_access_denied(") < src.index("UPDATE WebAiTasks SET Status")


def test_access_check_is_fail_closed():
    """권한 판정 실패는 **거부**다 — 확인이 안 되는 상태로 대화를 열지 않는다."""
    src = _src(_func(_tree(TOOLS_PY), "_conversation_access_denied"), TOOLS_PY)
    assert "allowed = False" in src, "판정 예외가 fail-closed 가 아니다"
    assert "conversation.read.own" in src and "conversation.read.any" in src


def test_delivery_precedes_ledger_in_submit():
    """대화 전달이 원장 기록보다 **먼저** 일어난다.

    task 는 이미 `submitted` 로 확정됐고 재제출은 409 다. 원장 실패로 전달 전에 503 을 내면
    답변이 확정됐는데 화면엔 없고 복구 경로도 없는 상태가 굳는다.
    """
    src = _src(_func(_tree(TOOLS_PY), "submit_answer"), TOOLS_PY)
    assert src.index("_deliver_web_bridge_answer(") < src.index("_ledger.record(")


def test_delivery_checks_save_return_value():
    """`save_memory_message` 의 반환값을 확인한다 — 그 함수는 쓰기 실패를 내부에서 삼킨다."""
    src = _src(_func(_tree(TOOLS_PY), "_deliver_web_bridge_answer"), TOOLS_PY)
    assert "message_id" in src
    assert "if not message_id" in src, "저장 실패(0 반환)를 성공으로 보고한다"
    assert "SET Delivered=1" in src, "전달 성공이 task 에 기록되지 않는다"


def test_bridge_status_separates_answered_and_delivered():
    """`answered`(제출됨)와 `delivered`(대화에 실림)를 구분해 보고한다."""
    src = _src(_func(_tree(TOOLS_PY), "bridge_status"), TOOLS_PY)
    assert '"delivered"' in src
    assert "Delivered" in src


def test_submit_binds_to_claiming_session():
    """제출 소유권이 계정이 아니라 **세션**(OAuth client)까지 묶인다."""
    src = _src(_func(_tree(TOOLS_PY), "submit_answer"), TOOLS_PY)
    assert "ClaimedClient" in src, "같은 계정의 다른 세션이 제출할 수 있다"


def test_claim_records_client():
    """점유 시 세션 식별자를 기록한다(위 소유권 조건의 전제)."""
    src = _src(_func(_tree(TOOLS_PY), "claim_request"), TOOLS_PY)
    assert "ClaimedClient=%s" in src


def test_enqueue_rolls_back_task_when_user_message_fails():
    """사용자 메시지 저장 실패 시 적재를 **취소**한다 — 질문 없이 답변만 남지 않는다."""
    src = _src(_func(_tree(CONV_PY), "_enqueue_web_bridge_task"), CONV_PY)
    assert "_delete_bridge_task(" in src
    assert "saved" in src, "save 반환값을 확인하지 않는다"
    # 적재가 저장보다 먼저여야 재시도 시 사용자 메시지가 중복되지 않는다.
    # ⚠ 함수 전체에서 index() 로 재면 안 된다. 미연결 분기(2026-08-27 신설)가 앞에 있고
    #   그쪽은 적재 없이 저장만 하므로 순서가 뒤집힌 것처럼 보인다. 이 계약이 걸린 곳은
    #   **연결 분기**(적재 → 저장 → 실패 시 되돌림)이므로 그 구간만 본다.
    connected = src[src.index("# ① 대기 작업 적재"):]
    assert connected.index("INSERT INTO WebAiTasks") < connected.index("save_memory_message")


def test_delete_bridge_task_is_scoped():
    """취소는 미점유 open task 만 — 경합으로 이미 가져간 작업을 소멸시키지 않는다."""
    src = _src(_func(_tree(CONV_PY), "_delete_bridge_task"), CONV_PY)
    assert "ClaimedBy IS NULL" in src
    assert "Status='open'" in src


def test_runner_forwards_conversation_context():
    """러너가 `conversation_context` 를 AI 에게 전달한다 — API 까지만 오고 끊기지 않는다."""
    runner = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_runner.py"
    text = runner.read_text(encoding="utf-8")
    assert "_compose_prompt(" in text
    assert "conversation_context" in text
    watch_src = _src(_func(_tree(runner), "cmd_watch"), runner)
    assert "_compose_prompt(" in watch_src, "watch 루프가 문맥 없이 질문만 넘긴다"


@pytest.mark.parametrize("col", ["ClaimedClient", "Delivered"])
def test_second_round_columns_present(col):
    """2차 조치 컬럼이 CREATE TABLE·마이그레이션 양쪽에 있다."""
    text = SCHEMA_PY.read_text(encoding="utf-8")
    create_start = text.index("CREATE TABLE IF NOT EXISTS WebAiTasks")
    create_end = text.index("ENGINE=InnoDB", create_start)
    assert col in text[create_start:create_end], f"CREATE TABLE 에 {col} 없음"
    assert f'("{col}", "ALTER TABLE WebAiTasks ADD COLUMN {col}' in text, (
        f"{col} 마이그레이션 ALTER 없음"
    )
