"""feature-0043 — **사용감 패리티**: 브리지 전환이 기존 동작을 바꾸지 않았는가.

사용자 요구(2026-08-27): "기존의 LLM 작동에 관련된 기능들(DB 요청사항 수행, 대화 내역 보존,
그룹 대화 Assistant 호출 등) 에 대한 사용감은 동일하게 유지되어야 합니다." 이어서 "LLM 요청구조가
변경되면서 사용자 경험이 바뀐 부분이 기존의 동작 및 경험과 정합하도록 전수적으로" 수정할 것.

## 이 파일이 검사하는 것 — **배선**이지 헬퍼 정확도가 아니다

전환에서 실제로 깨진 것은 계산이 아니라 **연결**이었다. 기존 경로가 하던 일 중 브리지 경로가
"그냥 안 하는" 것들:

| 깨진 연결 | 사용자에게 보이는 모습 |
|---|---|
| 질문 meta 에 발신자 각인 누락 | 그룹 대화에서 **누가 물었는지 사라짐** |
| 답변 meta 에 제품 귀속 각인 누락 | 제품을 바꾸면 **과거 답변 발화자가 소급 변경** |
| `core_messages` 미기록 | 대화 복제·분기본에서 **브리지 turn 만 유실** |
| 첨부 미전달 | "이 파일 분석해줘" 가 **조용히 오답** |
| 재답변·AI로 고치기가 브리지 미인지 | **거짓 성공 토스트** + 답이 와도 화면 그대로 |
| 관리 콘솔 기능이 장애 문구로 죽음 | 고장으로 오인 → 무한 재시도 |
| provider 제한 배너 고착 | 전송에 영향 없는데 **거짓 경보**, 복구 ping 불가로 영구 |

헬퍼를 직접 호출하는 테스트는 이 중 어느 것도 못 본다(헬퍼는 다 정상이었다). 그래서 **소스에서
연결을 단정**한다 — 연결을 끊는 뮤턴트만 잡히면 그것으로 충분하다.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_REPO = _UNIT.parent

WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
CORE_SRC = _UNIT / "feature-0002-agent-core" / "src"
CONVS = WEB_SRC / "routers" / "conversations.py"
AI_TOOLS = WEB_SRC / "routers" / "ai_tools.py"
BOOTSTRAP = WEB_SRC / "routers" / "_bootstrap_schema.py"
APP_JS = WEB_SRC / "static" / "app.js"
COMPOSER_JS = WEB_SRC / "static" / "app" / "composer.js"
GATE = _REPO / "shared" / "llm_gate.py"
HEALTH = CORE_SRC / "modules" / "llm_provider_health.py"
NODE_ANALYSIS = CORE_SRC / "modules" / "node_analysis.py"
MCP_HTTP = _UNIT / "feature-0041-external-ai-tool-surface" / "src" / "external_tool_mcp_http.py"
MCP_STDIO = _UNIT / "feature-0041-external-ai-tool-surface" / "src" / "external_tool_mcp_server.py"


def _func_source(path: pathlib.Path, name: str) -> str:
    """모듈에서 함수 하나의 소스만 떼어낸다(파일 전역 검색이 남의 코드를 오검출하지 않게)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
    raise AssertionError(f"{path.name}: 함수 {name} 를 찾지 못했다(이름이 바뀌었나?)")


def _code_lines(path: pathlib.Path, comment: str) -> str:
    """주석을 걷어낸 본문 — 주석에 적힌 단어가 '배선됨' 으로 오판되지 않게."""
    out = []
    for ln in path.read_text(encoding="utf-8").split("\n"):
        s = ln.strip()
        if not s or s.startswith(comment):
            continue
        out.append(ln)
    return "\n".join(out)


# ── 그룹 발신자 귀속 ──────────────────────────────────────────────────────────


def test_bridge_saves_user_message_with_sender_meta():
    """질문 저장이 **meta 를 동반**한다 — 그룹에서 발신자를 그리는 유일한 근거다."""
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert "_bridge_user_message_meta(" in src, (
        "브리지가 질문을 meta 없이 저장한다 — 그룹 대화에서 발신자가 사라진다")


def test_sender_meta_keys_match_existing_path():
    """각인 키가 기존 경로(`agent_core._persist_early_exit`)와 같은 이름이어야 한다.

    키가 갈리면 FE 는 한쪽만 읽어 그린다 — '있는데 안 보이는' 가장 찾기 어려운 형태가 된다.
    """
    src = _func_source(CONVS, "_bridge_user_message_meta")
    for key in ("sender_account_id", "sender_username", "group_chat"):
        assert key in src, f"각인 키 {key} 누락 — FE 표시 계약과 어긋난다"


def test_ask_handler_forwards_sender_to_bridge():
    """핸들러가 **이미 계산해 둔** 발신자를 브리지에 넘긴다(배선 끊기 방지)."""
    src = CONVS.read_text(encoding="utf-8")
    call = src[src.index("agent_result = _enqueue_web_bridge_task("):]
    call = call[:call.index(")\n")]
    assert "sender_username=" in call, "발신자를 넘기지 않는다 — 그룹 각인이 항상 비어 있게 된다"
    assert "product_mode=" in call, "제품 모드를 넘기지 않는다 — 답변 각인이 auto/pinned 를 구분 못 한다"
    assert "attachment_ids=" in call, "첨부를 넘기지 않는다 — 첨부 질문이 조용히 오답이 된다"


# ── 답변 제품 귀속 각인 ───────────────────────────────────────────────────────


def test_delivery_stamps_product_attribution():
    """답변 저장이 `_answer_product_attribution` 각인을 싣는다."""
    src = _func_source(AI_TOOLS, "_deliver_web_bridge_answer")
    assert "_answer_product_attribution(" in src, (
        "제품 귀속 각인 없이 저장한다 — 제품 변경 시 과거 답변 발화자가 소급 변경된다")
    assert "ProductMode" in src, "각인에 필요한 mode 를 읽지 않는다(auto/pinned 구분 불가)"


# ── core store(대화 내역 보존) ────────────────────────────────────────────────


@pytest.mark.parametrize("path,func", [
    (CONVS, "_enqueue_web_bridge_task"),
    (AI_TOOLS, "_deliver_web_bridge_answer"),
])
def test_both_sides_write_core_store(path, func):
    """질문·답변 **양쪽 모두** 회수 store 에 남는다 — 한쪽만 남으면 복제본이 반쪽이 된다."""
    src = _func_source(path, func)
    assert ("_bridge_save_core_message(" in src) or ("_save_message(" in src), (
        f"{func}: core_messages 기록이 없다 — 대화 복제·분기에서 이 turn 이 통째로 사라진다")


def test_core_write_comes_after_display_write():
    """순서 계약: 표시 저장 성공을 **확인한 뒤** 회수 store 에 쓴다.

    반대면, 표시 저장 실패로 요청을 취소했을 때 회수 store 에만 유령 turn 이 남는다.
    """
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert "if not saved:" in src
    assert src.index("if not saved:") < src.index("_bridge_save_core_message("), (
        "표시 저장 판정 전에 core 를 쓴다 — 취소된 요청이 회수 store 에 유령으로 남는다")


# ── 첨부 도달 ────────────────────────────────────────────────────────────────


def test_schema_has_parity_columns():
    """각인·첨부에 필요한 컬럼이 온라인 DDL 로 추가된다(운영 중 락 없이)."""
    src = BOOTSTRAP.read_text(encoding="utf-8")
    for col in ("ProductMode", "SenderUsername", "AttachmentIds"):
        assert f'("{col}", "ALTER TABLE WebAiTasks ADD COLUMN {col}' in src, f"{col} 컬럼 미추가"
    block = src[src.index('("ProductMode"'):src.index('("AttachmentIds"') + 400]
    assert block.count("ALGORITHM=INPLACE, LOCK=NONE") >= 3, (
        "온라인 DDL 이 아니다 — 운영 테이블에 락이 걸린다")


def test_claim_returns_attachment_list():
    """점유 응답이 첨부 **목록**을 준다 — 존재를 모르면 AI 는 없다고 전제하고 답한다."""
    src = _func_source(AI_TOOLS, "claim_request")
    assert "_task_attachment_list(" in src
    assert '"attachments"' in src


def test_read_attachment_tool_enforces_claim_and_access():
    """첨부 읽기가 소유·점유·현재권한 **3겹**을 모두 건다."""
    src = _func_source(AI_TOOLS, "read_task_attachment")
    assert "AccountId=%s AND Origin='web'" in src, "소유 경계 없음 — 남의 질문 첨부가 열린다"
    assert "claimed_by" in src, "점유 검사 없음 — 집지 않고 훔쳐볼 수 있다"
    assert "_conversation_access_denied(" in src, "권한 재검증 없음 — 퇴출된 멤버가 계속 읽는다"


def test_read_attachment_restores_context_scope():
    """스코프 contextvar 를 **반드시 되돌린다** — 안 되돌리면 다음 요청이 남의 대화를 물려받는다."""
    src = _func_source(AI_TOOLS, "read_task_attachment")
    assert ".reset(" in src, "contextvar 복원 없음 — 워커 스레드 재사용 시 스코프가 샌다"
    assert "finally:" in src, "복원이 finally 밖이면 예외 경로에서 새어나간다"


@pytest.mark.parametrize("path", [MCP_HTTP, MCP_STDIO])
def test_attachment_tool_registered_in_mcp_adapters(path):
    """두 어댑터 **모두**에 등록 — 한쪽만 하면 그 클라이언트에서만 조용히 죽는다.

    (전환 초기에 실제로 이 형태로 브리지 도구가 통째로 죽었다 — REST 만 추가했었다.)
    """
    src = path.read_text(encoding="utf-8")
    assert "read_task_attachment" in src, f"{path.name}: 첨부 읽기 도구 미등록"


# ── 프론트: 답변을 유발하는 모든 화면 동작이 브리지를 안다 ────────────────────


def test_bridge_handling_is_a_single_helper():
    """브리지 처리는 헬퍼 하나로 — 진입점마다 복붙하면 하나를 빠뜨린다(실제로 빠뜨렸다)."""
    src = COMPOSER_JS.read_text(encoding="utf-8")
    assert "export function handleBridgePending(" in src


@pytest.mark.parametrize("marker", [
    "handleBridgePending(payload, cid, \"내 AI 가 고칠 요청으로 등록했습니다.\")",   # fix-with-ai
    "handleBridgePending(payload, cid, \"내 AI 가 재답변할 요청으로 등록했습니다.\")",  # 재답변
])
def test_secondary_answer_entrypoints_handle_bridge(marker):
    """`/api/ask` 를 재dispatch 하는 화면 동작(AI로 고치기·재답변)도 브리지를 처리한다."""
    src = APP_JS.read_text(encoding="utf-8")
    assert marker in src, (
        "이 진입점이 브리지를 모른다 — 대기 안내를 받고도 '추가했습니다' 라는 거짓 성공을 "
        "띄우고, 답이 도착해도 화면이 갱신되지 않는다")


def test_no_false_success_toast_when_bridged():
    """브리지일 때 성공 토스트가 `else` 로 밀려야 한다(둘 다 뜨면 거짓 보고)."""
    src = APP_JS.read_text(encoding="utf-8")
    for phrase in ("AI 가 수정한 결과를 추가했습니다.", "재답변을 추가했습니다."):
        idx = src.index(phrase)
        window = src[max(0, idx - 700):idx]
        assert "_bridged" in window, f'"{phrase}" 가 브리지 분기 밖에 있다 — 거짓 성공 보고'


# ── 차단된 기능의 안내 문구 ───────────────────────────────────────────────────


def test_gate_has_distinct_message_for_non_chat_features():
    """대화 안내와 **다른** 문구가 있어야 한다.

    대화용 문구는 "본인 AI 가 처리한다" 고 말한다 — 관리 콘솔 자동완성에는 거짓이고,
    오지 않을 결과를 기다리게 만든다.
    """
    src = GATE.read_text(encoding="utf-8")
    assert "def feature_blocked_message(" in src
    body = _func_source(GATE, "feature_blocked_message")
    assert "고장이 아닙니다" in body, "고장이 아님을 말하지 않으면 무한 재시도를 유발한다"


@pytest.mark.parametrize("path,label", [
    (WEB_SRC / "routers" / "_prompt_context.py", "시스템 프롬프트 자동작성"),
    (WEB_SRC / "routers" / "admin_metadata.py", "메타데이터 AI 자동완성"),
])
def test_console_features_say_why_not_just_failure(path, label):
    """차단(운영 결정)과 초기화 실패(장애)를 **구분해서** 말한다."""
    src = path.read_text(encoding="utf-8")
    assert "feature_blocked_message(" in src, f"{path.name}: 차단 안내가 장애 문구로 뭉뚱그려진다"
    assert label in src, f"{path.name}: 어떤 기능인지 이름을 말하지 않는다"
    # 장애 문구가 사라지면 안 된다 — 게이트가 열린 뒤의 진짜 초기화 실패를 가릴 수 없다.
    assert "LLM 클라이언트를 초기화할 수 없습니다" in src, (
        "장애 문구를 통째로 대체했다 — 게이트를 되돌린 뒤 진짜 장애를 차단으로 오인하게 된다")


def test_node_analysis_refuses_before_enqueue():
    """분석은 **큐에 넣기 전에** 거절한다 — 넣으면 재시도를 태우고 알 수 없는 실패로 끝난다."""
    src = NODE_ANALYSIS.read_text(encoding="utf-8")
    assert src.count("feature_blocked_message(") >= 2, "노드·스키마 두 진입점 모두 게이트가 필요하다"
    for func in ("enqueue_analysis", "enqueue_schema_analysis"):
        body = _func_source(NODE_ANALYSIS, func)
        assert "server_llm_enabled()" in body, f"{func}: 게이트 검사 없음"


# ── provider 제한 배너 ───────────────────────────────────────────────────────


def test_provider_health_masks_restriction_while_blocked():
    """차단 중에는 restricted 로 표면화하지 않는다 — 전송에 영향 없는 거짓 경보다."""
    src = HEALTH.read_text(encoding="utf-8")
    assert "def _gate_override(" in src
    body = _func_source(HEALTH, "_gate_override")
    assert "STATE_OK" in body, "non-restricted 로 만들지 않으면 배너가 영구 고착된다"
    assert "llm-gate" in body, "이유를 남기지 않으면 운영자가 '왜 ok 인지' 를 알 수 없다"
    assert "server_llm_blocked" in body, "차단 사실 자체는 표면에 남아야 한다(숨기는 것이 아니다)"


def test_probe_does_not_ping_while_blocked():
    """차단 중에는 실제 ping 을 시도하지 않는다(비용·로그 낭비 + 어차피 분류 불가)."""
    body = _func_source(HEALTH, "probe_provider")
    assert "server_llm_enabled" in body
    gate_pos = body.index("_gate_open()")
    assert gate_pos < body.index("_probe_enabled()"), "게이트 검사가 probe 판정보다 뒤에 있다"


def test_raw_health_read_still_available_for_operators():
    """원본 읽기 경로는 남는다 — 마스킹이 곧 은폐가 되면 운영 진단이 불가능해진다."""
    src = HEALTH.read_text(encoding="utf-8")
    assert "def _read_provider_health_raw(" in src


# ── 유지되어야 하는 것(회귀 방지) ─────────────────────────────────────────────


def test_group_mention_gate_still_precedes_bridge():
    """그룹 비멘션 메시지는 여전히 사람-사람 채팅으로 남는다(브리지로 새지 않는다)."""
    src = CONVS.read_text(encoding="utf-8")
    # 정의부(파일 상단)가 아니라 **호출부**와 비교한다 — 정의 위치는 순서 계약과 무관하다.
    call_pos = src.index("agent_result = _enqueue_web_bridge_task(")
    assert src.index("group_requires_mention") < call_pos, (
        "브리지 분기가 멘션 게이트보다 앞에 있다 — 그룹의 일반 채팅이 AI 질문으로 적재된다")


def test_bridge_branch_precedes_dispatch():
    """브리지 분기는 dispatch **앞**에 있어야 한다 — 뒤면 슬롯·워커를 점유한 뒤 되돌려야 한다."""
    src = CONVS.read_text(encoding="utf-8")
    assert src.index("_enqueue_web_bridge_task(\n") < src.index("await app._dispatch_ask_run(")


def test_embedding_path_untouched():
    """로컬 임베딩은 차단 대상이 아니다 — 끄면 KB 검색이 죽는 부수 피해."""
    src = GATE.read_text(encoding="utf-8")
    assert re.search(r"비차단.*임베딩|임베딩.*비차단", src, re.S), (
        "임베딩 비차단 계약이 정본에서 사라졌다")


# ══════════════════════════════════════════════════════════════════════════════
# codex 적대 리뷰 조치 (2026-08-27, P1 1건 + P2 6건)
#
# 공통 교훈: **최적화가 방어를 껐다.** "차단 중이니 어차피 안 될 일을 하지 말자" 는 판단이
# 매번 그 경로에 얹혀 있던 다른 것(heartbeat·비-LLM 정비·운영자 가시성)을 함께 껐다.
# ══════════════════════════════════════════════════════════════════════════════


def test_insight_gate_does_not_swallow_heartbeat():
    """cycle **전체** 를 조기 반환하면 `finally` 의 heartbeat 가 죽어 컨테이너가 상시 unhealthy.

    게이트는 LLM 구간에만 건다. cycle 진입부의 early-return 이 되살아나면 이 테스트가 잡는다.
    """
    src = _func_source(NODE_ANALYSIS.parent / "insight.py", "run_insight_cycle")
    head = src[:src.index("cycle_run_id =")]
    assert "return {" not in head, (
        "cycle 진입부에서 조기 반환한다 — heartbeat(finally)와 비-LLM 정비가 함께 멈춘다")
    assert "_llm_open" in src, "LLM 구간 게이트가 없다"


def test_insight_skips_only_llm_work():
    """순수 LLM 작업(잡 처리)만 건너뛰고, LLM 무관 정비는 그대로 돈다."""
    src = _func_source(NODE_ANALYSIS.parent / "insight.py", "run_insight_cycle")
    assert "process_pending() if _llm_open else {}" in src, "LLM 잡 처리가 게이트 밖에 있다"
    assert "backfill_roles()" in src, "LLM 무관 backfill 까지 껐다"


def test_attachment_read_matches_submit_boundary():
    """읽기 경계가 `submit_answer` 와 같은 모양 — 한쪽만 느슨하면 그쪽이 실질 경계다."""
    src = _func_source(AI_TOOLS, "read_task_attachment")
    for needle, why in (
        ("claimed_client", "점유 세션(client) 미검사 — 같은 계정의 다른 세션이 타고 읽는다"),
        ("_claim_lease_valid(", "lease 미검사 — 만료된 점유로 계속 읽는다"),
        ("submitted_at", "제출 여부 미검사 — 끝난 task 를 계속 읽는다"),
    ):
        assert needle in src, why


def test_attachment_read_checks_ledger_before_reading():
    """상한은 **읽기 전** 에 건다 — 사후 기록만으로는 상한이 집행되지 않는다."""
    src = _func_source(AI_TOOLS, "read_task_attachment")
    assert "_ledger.check_limits(" in src, "원장 상한 우회 — 첨부 본문으로 bytes 상한을 넘길 수 있다"
    assert src.index("_ledger.check_limits(") < src.index("read_attachment_content("), (
        "상한 검사가 본문 읽기보다 뒤에 있다 — 이미 읽은 뒤에 막아봐야 소용없다")


def test_attachment_read_restores_provenance_context():
    """스코프 id 뿐 아니라 **provenance 판정 결과**까지 복원한다."""
    src = _func_source(AI_TOOLS, "read_task_attachment")
    assert "_UNTRUSTED_ATTACH_BODY_CTX" in src, (
        "provenance 플래그를 복원하지 않는다 — 같은 Context 재사용 시 남의 판정을 물려받는다")
    assert "_ACTIVE_ACCOUNT_ID_CTX" in src, (
        "계정을 세우지 않으면 provenance 판정 자체가 안 돌아 '타 멤버 파일' 표시가 사라진다")
    assert "reversed(_ctx_tokens)" in src, "역순 복원이 아니면 중첩 Context 가 어긋난다"


def test_admin_ops_reads_raw_provider_state():
    """관리자 관제는 **마스킹되지 않은** 상태를 본다 — 전환 전 위험 확인 경로다."""
    src = (WEB_SRC / "routers" / "ai_ops.py").read_text(encoding="utf-8")
    assert "_read_llm_provider_status_admin" in src, (
        "관제가 대화 UI 용(마스킹된) 읽기를 쓴다 — 게이트를 되돌리는 순간 숨은 제한이 되살아난다")
    assert "server_llm_blocked" in src, "차단 사실을 관제에 싣지 않으면 ok 의 의미를 알 수 없다"
    # seam 이 실제로 원본을 읽는지까지 확인 — 이름만 바꾸고 안에서 마스킹본을 읽으면 무의미하다.
    sysmod = (WEB_SRC / "routers" / "system.py").read_text(encoding="utf-8")
    admin_fn = _func_source(WEB_SRC / "routers" / "system.py", "_read_llm_provider_status_admin")
    assert "_read_provider_health_raw" in admin_fn, "관제 seam 이 원본을 읽지 않는다"
    assert "def _read_llm_provider_status(" in sysmod, "대화 UI 용 읽기가 사라졌다"


def test_bridge_polling_resumes_on_conversation_reentry():
    """대화를 떠났다 돌아오면 대기 질문의 폴링이 되살아난다."""
    comp = COMPOSER_JS.read_text(encoding="utf-8")
    assert "export function resumeBridgePolling(" in comp
    assert "_rememberPendingBridgeTask(" in comp, "대기 task 를 기억하지 않으면 되살릴 수 없다"
    for done in ("_forgetPendingBridgeTask(convId, taskId); return;",
                 "_forgetPendingBridgeTask(convId, taskId);\n      return;"):
        if done in comp:
            break
    else:
        raise AssertionError("종료 시 registry 를 비우지 않는다 — 죽은 task 를 영원히 재폴링한다")
    app = APP_JS.read_text(encoding="utf-8")
    assert "resumeBridgePolling(String(conversationId" in app, "대화 열기 경로에 배선되지 않았다"


def test_bridge_polling_is_not_duplicated():
    """전송 직후 폴링과 재진입 복구가 겹쳐도 같은 task 를 두 번 돌리지 않는다."""
    comp = COMPOSER_JS.read_text(encoding="utf-8")
    assert "_activeBridgePolls" in comp, "중복 폴링 가드 없음 — 토스트가 두 번 뜨고 요청이 2배가 된다"


# ══════════════════════════════════════════════════════════════════════════════
# 라이브 제보(2026-08-27): "대화를 전송했지만 답변 진행 or 가이드라인이 제공되지 않았습니다"
#
# task 는 정상 적재됐고 질문도 각인과 함께 저장됐다. 빠진 것은 **대기 안내를 대화에 남기는
# 것**이었다 — 응답 payload 로만 돌려주고 저장하지 않으니, 이력을 그리는 프런트에는 질문만
# 남았다(토스트는 몇 초 뒤 사라져 근거가 되지 못한다).
#
# 교훈: 브리지가 `agent_core` 를 우회한다는 것은 "답변을 만들지 않는다" 만이 아니라
# **"답변을 저장하지도 않는다"** 는 뜻이다. 그 저장은 누군가 다시 해야 한다.
# ══════════════════════════════════════════════════════════════════════════════


def test_bridge_persists_wait_notice_as_assistant_message():
    """대기 안내가 **대화에 저장**된다 — 저장하지 않으면 화면에 질문만 남는다."""
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert '"assistant", notice_text' in src, (
        "대기 안내를 assistant 말풍선으로 저장하지 않는다 — 사용자에겐 '아무 일도 안 일어난' 것으로 보인다")
    assert '"placeholder": True' in src, (
        "placeholder 각인이 없으면 답변 도착 시 덮어쓸 대상을 찾을 수 없다")


def test_wait_notice_is_single_source():
    """저장 본문과 응답 `answer` 가 **같은 상수** — 갈리면 화면과 응답이 다른 말을 한다."""
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    # 저장 본문과 응답 `answer` 가 **같은 변수** — 갈리면 화면과 응답이 다른 말을 한다.
    assert '"assistant", notice_text' in src
    assert '"answer": notice_text,' in src, "응답이 같은 변수를 쓰지 않는다(문구 두 벌)"


def test_wait_notice_not_written_to_core_store():
    """안내는 **회수 store 에 넣지 않는다** — 시스템 안내이지 대화 내용이 아니다.

    넣으면 나중 LLM 문맥에 "AI 가 대기 안내를 했다" 는 가짜 turn 이 섞인다.
    """
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    tail = src[src.index('"assistant", notice_text'):]
    assert "_bridge_save_core_message(" not in tail, (
        "안내를 회수 store 에도 썼다 — LLM 문맥에 가짜 assistant turn 이 생긴다")


def test_delivery_overwrites_placeholder_not_appends():
    """답변은 대기 말풍선 **자리에 덮어쓴다** — append 면 안내가 답변 위에 영구히 남는다."""
    src = _func_source(AI_TOOLS, "_deliver_web_bridge_answer")
    assert "_replace_bridge_placeholder(" in src
    assert "if not message_id:" in src, "덮어쓰기 실패 시 append 폴백이 없다(구 task 가 답변을 못 받는다)"
    assert '_meta["bridge"]["placeholder"] = False' in src, (
        "placeholder 각인을 지우지 않으면 이 답변이 다음 전달의 덮어쓰기 대상이 된다")


def test_placeholder_replace_is_scoped_to_one_task():
    """덮어쓰기가 **이 task 의 placeholder** 만 고른다 — 아니면 남의 말풍선을 덮는다."""
    src = _func_source(AI_TOOLS, "_replace_bridge_placeholder")
    assert "task_id" in src and "'placeholder'" in src
    assert "role = 'assistant'" in src, "역할 제한 없이 갱신하면 사용자 질문까지 덮어쓸 수 있다"
    assert "conversation_id = %s" in src, "대화 경계 없이 갱신한다"


# ══════════════════════════════════════════════════════════════════════════════
# 라이브 제보 2건째(2026-08-27): "가이드 메시지를 확인했지만, 일반적인 사용자는
# '외부 AI 연결( /ai/connect )' 라는 의미 자체를 인지하지 못합니다."
#
# 맞는 지적이다. `MCP`·`/ai/connect` 는 **만든 사람의 언어**이고, 경로 문자열은 누를 수도 없다.
# 그리고 안내가 **한 가지뿐**이라 상태와 무관하게 같은 말을 했다 — 연결이 없는 사람에게
# "기다리세요" 는 영원히 오지 않을 것을 기다리라는 말이다.
# ══════════════════════════════════════════════════════════════════════════════


def test_notice_has_two_states():
    """연결 여부에 따라 **다른 안내**를 한다 — 하나로는 둘 중 한쪽에게 반드시 틀린 말이 된다."""
    src = CONVS.read_text(encoding="utf-8")
    assert "_BRIDGE_NOTICE_NOT_CONNECTED = (" in src
    assert "_BRIDGE_NOTICE_CONNECTED = (" in src
    assert "def _account_has_connected_ai(" in src, "연결 여부를 판정하지 않는다"


def test_unconnected_notice_leads_with_action_not_waiting():
    """연결이 없으면 첫 줄이 **'기다리세요' 가 아니라 '설정이 필요하다'** 여야 한다."""
    src = CONVS.read_text(encoding="utf-8")
    body = src[src.index("_BRIDGE_NOTICE_NOT_CONNECTED = ("):src.index("#: 이미 연결한 계정")]
    assert "연결되어 있지 않습니다" in body
    assert "[AI 연결하기](/ai/connect)" in body, (
        "누를 수 있는 링크가 없다 — 경로 문자열은 사용자가 어떻게 할 수 없다")
    # 질문이 사라지지 않았다는 사실을 반드시 말한다(설정하러 가는 동안 불안하지 않게).
    assert "저장해 두었습니다" in body


def test_notice_avoids_builder_jargon():
    """안내 본문에 `MCP` 같은 내부 용어를 쓰지 않는다."""
    src = CONVS.read_text(encoding="utf-8")
    for const in ("_BRIDGE_NOTICE_NOT_CONNECTED", "_BRIDGE_NOTICE_CONNECTED"):
        start = src.index(f"{const} = (")
        body = src[start:src.index(")\n", start)]
        assert "MCP" not in body, f"{const}: 'MCP' 는 사용자의 언어가 아니다"


def test_connection_probe_fails_open():
    """조회 실패는 '연결됨' 으로 본다 — 틀렸을 때 덜 성가신 방향."""
    src = _func_source(CONVS, "_account_has_connected_ai")
    tail = src[src.index("except Exception"):]
    assert "return True" in tail, (
        "조회 실패 시 '연결 없음' 으로 단정하면 이미 연결한 사용자에게 매번 설정하라고 떠든다")


def test_notice_decided_once_per_request():
    """저장 본문·응답·토스트가 **같은 판정**을 쓴다(따로 조회하면 갈린다)."""
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert src.count("_account_has_connected_ai(") == 1, "연결 여부를 두 번 이상 조회한다"
    assert "notice_text = " in src


def test_toast_text_comes_from_server():
    """토스트도 상태에 따라 달라진다 — 판정은 서버만 할 수 있다(토큰 조회)."""
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert '"bridge_toast"' in src
    assert "AI 연결이 필요합니다" in src, "연결 없는 사용자에게도 '내 AI 가 처리' 라고 말한다"
    comp = COMPOSER_JS.read_text(encoding="utf-8")
    assert "payload.bridge_toast" in comp, "프런트가 서버 문구를 무시하고 고정 문구를 쓴다"


# ── /ai/connect 화면도 사용자 눈높이로 (사용자 결정 2026-08-27) ────────────────
#
# 안내 말풍선의 링크를 눌러 도착한 화면이 또 전문 용어투성이면 안내를 고친 의미가 없다.

CONNECT_HTML = WEB_SRC / "static" / "ai-connect.html"
CONNECT_JS = WEB_SRC / "static" / "ai-connect.js"


def test_connect_page_explains_why_before_how():
    """'무엇을 하는 화면인지' 를 단계 설명보다 **먼저** 말한다."""
    html = CONNECT_HTML.read_text(encoding="utf-8")
    assert 'class="aic-why"' in html, "무엇을 하면 되는지 알려주는 도입부가 없다"
    assert html.index("aic-why") < html.index("makeHandoff"), "안내가 버튼 뒤에 있다"


def test_connect_page_tells_where_to_paste():
    """붙여넣을 **대상**을 말한다 — 그 대상은 설정 화면이 아니라 **AI 자신**이다."""
    html = CONNECT_HTML.read_text(encoding="utf-8")
    assert "AI에 붙여넣" in html, "어디에 붙여넣는지 알려주지 않는다"


def test_connect_page_promises_the_human_is_done_after_pasting():
    """붙여넣은 뒤로는 **사람이 할 일이 없다**고 명시한다(사용자 결정 2026-08-27).

    문구는 짧게 유지하되(슬롭 제거 2026-08-27) 이 약속 자체는 남는다 — 이게 없으면 사용자는
    "그다음엔 뭘 해야 하지" 를 계속 찾는다.
    """
    html = CONNECT_HTML.read_text(encoding="utf-8")
    assert "AI가 알아서 합니다" in html, "나머지 인증을 AI 가 한다는 약속이 없다"


def test_connect_page_is_a_single_flow():
    """사람에게 방법을 **고르게 하지 않는다** — 판정 불가능한 선택을 시키지 않는다."""
    html = CONNECT_HTML.read_text(encoding="utf-8")
    import re

    visible = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    for gone in ("방법 ①", "방법 ②", "connectAuto", "connectManual"):
        assert gone not in visible, f"두 갈래 구조가 남아 있다: {gone}"
    assert 'id="connectFlow"' in html, "단일 흐름 섹션이 없다"


def test_connect_page_glosses_token_once_and_keeps_the_word():
    """'토큰' 이라는 말을 **버리지 않고 설명**한다.

    '열쇠' 같은 새 이름을 만들면 정작 AI 도구 설정 화면의 `token` 칸과 매칭이 끊긴다.
    """
    html = CONNECT_HTML.read_text(encoding="utf-8")
    assert "비밀번호처럼" in html, "토큰을 어떻게 다뤄야 하는지 말하지 않는다"
    assert "열쇠" not in html, "용어를 두 벌로 만들면 사용자가 매칭에 실패한다"


def test_connect_page_no_unexplained_mcp_in_visible_text():
    """사용자가 **보는 텍스트**에 설명 없는 `MCP` 가 없다(주석은 무관)."""
    import re

    html = CONNECT_HTML.read_text(encoding="utf-8")
    visible = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    assert "MCP" not in visible, "화면 텍스트에 내부 용어가 남아 있다"


def test_connect_page_dom_contract_preserved():
    """JS 가 `$("...")` 로 잡는 id 가 **전부** HTML 에 있는가 — 하나라도 빠지면 버튼이 죽는다.

    ⚠ 이전 판은 고정 목록 + `if dom_id in js:` 였다. 그래서 id 를 **삭제하면 단언이 조용히
    건너뛰어졌다**(vacuous pass — 실제로 `copyEndpoint` 제거 때 그렇게 통과했다).
    이제 목록을 JS 에서 **추출**한다: JS 가 참조하는 것만 검사하되, 목록 자체가 코드에서 오므로
    "검사 대상이 사라져서 통과" 가 성립하지 않는다.
    """
    import re

    html = CONNECT_HTML.read_text(encoding="utf-8")
    js = CONNECT_JS.read_text(encoding="utf-8")
    referenced = set(re.findall(r'\$\("([A-Za-z0-9_]+)"\)', js))
    assert referenced, "JS 에서 DOM 참조를 추출하지 못했다(추출 정규식이 코드와 어긋났다)"
    missing = sorted(i for i in referenced if f'id="{i}"' not in html)
    assert not missing, f"JS 가 참조하는데 HTML 에 없다: {missing}"


def test_connect_page_has_exactly_one_copy_action():
    """복사 버튼은 **하나**다(사용자 제보 2026-08-27).

    둘이면 "어느 걸 복사하지?" 라는 선택이 다시 생긴다 — 방법 ①/② 를 통합한 이유와 같은 결함이다.
    주소는 이미 지시문 본문에 들어 있다.
    """
    html = CONNECT_HTML.read_text(encoding="utf-8")
    assert html.count("복사</button>") == 1, "복사 버튼이 하나가 아니다"
    assert "주소만 복사" not in html


def test_connect_page_does_not_send_humans_to_the_api_reference():
    """사람에게 `/api/ai/guide`(API 레퍼런스)를 권하지 않는다(사용자 제보 2026-08-27).

    그 문서가 필요한 쪽은 **AI** 이고, 지시문에 이미 URL 이 실려 있다. 사람이 눌러 가면
    스펙 문서를 만난다.
    """
    html = CONNECT_HTML.read_text(encoding="utf-8")
    assert "/api/ai/guide" not in html, "사람용 화면이 API 레퍼런스로 보낸다"
    js = CONNECT_JS.read_text(encoding="utf-8")
    assert "/api/ai/guide" in js, "지시문(AI 용)에서는 가이드 URL 이 빠지면 안 된다"


# ══════════════════════════════════════════════════════════════════════════════
# 라이브 e2e 제보(2026-08-27, 다른 세션): `list_open_requests` 가 **항상 500**.
#
#   TypeError: record() got an unexpected keyword argument 'rows'
#
# 조회는 끝난 뒤 **원장 기록 단계**에서 터졌다. 대기 질문이 있든 없든 100% 실패했고,
# `claim_request` 는 이 도구가 주는 task_id 를 요구하므로 **웹 브리지 축 전체가 끊겨** 있었다.
#
# 왜 못 잡았나: 내 테스트는 "도구가 등록됐는가"·"SQL 술어가 맞는가"·"권한 경계가 있는가" 를
# 봤지만, **그 핸들러를 한 번도 끝까지 실행해 보지 않았다.** 등록과 동작은 다른 사실이다.
#
# 그래서 문자열이 아니라 **시그니처로** 검사한다 — 오타·이름 변경 어느 쪽이든 잡힌다.
# ══════════════════════════════════════════════════════════════════════════════


def test_every_ledger_record_call_matches_the_signature():
    """`_ledger.record(...)` 호출의 키워드가 실제 시그니처와 일치하는가 — **전 호출부**.

    한 곳만 고치면 다음에 같은 실수가 다른 곳에서 난다. AST 로 전수 대조한다.
    """
    import ast
    import inspect
    import sys

    src_dir = str(WEB_SRC)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    import tool_ledger

    valid = set(inspect.signature(tool_ledger.record).parameters) - {"pg_conn"}
    offenders = []
    for path in (_UNIT).rglob("*.py"):
        if "/tests/" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", None) != "record":
                continue
            mod = str(getattr(getattr(node.func, "value", None), "id", ""))
            if "ledger" not in mod.lower():
                continue
            unknown = {k.arg for k in node.keywords if k.arg} - valid
            if unknown:
                offenders.append(f"{path.name}:{node.lineno} {sorted(unknown)}")
    assert not offenders, (
        "원장 기록 인자가 시그니처와 불일치 — 호출 시점에 TypeError 로 500 이 된다: "
        + "; ".join(offenders))


def test_bridge_list_records_rows_returned():
    """대기 질문 목록이 반환 행수를 원장에 남긴다(사용량 상한의 입력)."""
    src = _func_source(AI_TOOLS, "list_open_requests")
    assert "rows_returned=" in src, "행수를 기록하지 않으면 상한 판정의 입력이 비어 있다"
    assert "rows=" not in src.replace("rows_returned=", ""), "잘못된 인자명이 남아 있다"


def test_capabilities_accepts_the_token_the_manifest_advertises():
    """매니페스트가 안내하는 `/api/ai/capabilities` 에 `mat_` 토큰으로 도달할 수 있는가.

    쿠키 전용이면 **안내받은 곳에 갈 수 없는 불일치**가 된다(라이브 제보: 토큰만 가진 AI 가 401).
    """
    disc = (WEB_SRC / "routers" / "ai_discovery.py").read_text(encoding="utf-8")
    assert "def _account_from_ai_token(" in disc
    handler = _func_source(WEB_SRC / "routers" / "ai_discovery.py", "ai_capabilities")
    assert "_account_from_ai_token(" in handler, "토큰 축을 보지 않는다"
    # 토큰 해석은 도구 표면과 **같은 해석기**를 써야 한다 — 두 벌이면 갈린다.
    helper = _func_source(WEB_SRC / "routers" / "ai_discovery.py", "_account_from_ai_token")
    assert "require_ai_token" in helper, "토큰 해석을 따로 구현했다(만료·폐기 판정이 두 벌)"


def test_guide_lists_the_bridge_tools():
    """가이드가 실제 서빙 도구를 다 열거하는가.

    가이드만 읽은 외부 AI 는 열거되지 않은 축의 **존재 자체를 모른다**(라이브 제보 ③).
    """
    guide = (WEB_SRC / "static" / "ai-api-guide.md").read_text(encoding="utf-8")
    for tool in ("wait_for_request", "list_open_requests", "claim_request",
                 "read_task_attachment"):
        assert tool in guide, f"가이드에 {tool} 이 없다 — 외부 AI 가 이 축을 못 찾는다"


def test_guide_tool_count_matches_exposed_surface():
    """가이드가 적은 도구 수 = 실제 노출 집합 크기. 숫자만 갱신하고 목록을 빼먹지 않게."""
    import re

    src = AI_TOOLS.read_text(encoding="utf-8")
    p0 = re.search(r"P0_TOOLS = frozenset\(\{(.*?)\}\)", src, re.S).group(1)
    p1 = re.search(r"P1_TOOLS = frozenset\(\{(.*?)\}\)", src, re.S).group(1)
    structural = len(re.findall(r'"([a-z_]+)"', p0 + p1))
    # 구조·SQL 도구 + 작업 3종(open_task/get_task_context/submit_answer)
    # + 브리지 4종(wait_for_request/list_open_requests/claim_request/read_task_attachment)
    expected = structural + 3 + 4
    guide = (WEB_SRC / "static" / "ai-api-guide.md").read_text(encoding="utf-8")
    assert f"({expected}종)" in guide, (
        f"가이드의 도구 수가 실제({expected}종)와 다르다")


# ── 인증창 모달 (사용자 결정 2026-08-27) ──────────────────────────────────────
#
# 안내 말풍선의 링크가 페이지를 **이동**시키면 질문을 써 놓고 화면을 벗어난다.
# 연결은 대화의 곁가지이지 목적지가 아니다.

INDEX_HTML = WEB_SRC / "static" / "index.html"
MODAL_JS = WEB_SRC / "static" / "app" / "connect-modal.js"


def test_connect_modal_exists_and_is_wired():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="connectModalOverlay"' in html, "모달 마크업이 없다"
    app = APP_JS.read_text(encoding="utf-8")
    assert "bindConnectModal()" in app, "모달이 배선되지 않았다(마크업만 있고 열리지 않는다)"


def test_modal_intercepts_the_notice_link():
    """말풍선 링크를 **문서 수준 위임**으로 가로챈다 — 개별 앵커에 달면 재렌더마다 사라진다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    assert 'a[href="/ai/connect"]' in js
    assert "document.addEventListener" in js, "문서 위임이 아니다"
    assert "preventDefault()" in js


def test_modal_respects_new_tab_intent():
    """중클릭·수식키(새 탭 의도)는 가로채지 않는다 — 사용자가 원한 동작을 빼앗지 않는다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    for key in ("metaKey", "ctrlKey", "shiftKey", "ev.button !== 0"):
        assert key in js, f"{key} 를 존중하지 않는다"


def test_modal_uses_server_composed_handoff():
    """지시문을 **서버에서 받는다** — 화면이 조립하면 단독 페이지와 문안이 갈린다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    assert "body.handoff" in js, "지시문을 프런트가 만든다(두 벌 관리)"
    assert "mcpServers" not in js, "모달이 설정 JSON 을 직접 조립한다"


def test_modal_clears_token_from_dom_on_close():
    """닫으면 본문을 비운다 — DOM 에 토큰을 남기지 않고, '다시 볼 수 없다' 를 참으로 만든다."""
    close = MODAL_JS[:0] if False else None  # noqa: F841  (가독용 no-op)
    js = MODAL_JS.read_text(encoding="utf-8")
    body = js[js.index("export function closeConnectModal("):js.index("async function _make(")]
    assert 'textContent = ""' in body, "닫을 때 토큰이 DOM 에 남는다"
    opened = js[js.index("export function openConnectModal("):js.index("export function closeConnectModal(")]
    assert 'textContent = ""' in opened, "열 때 이전 토큰이 남아 새것으로 오인된다"


def test_standalone_page_still_exists():
    """모달은 **가로채는 개선**이지 유일 경로가 아니다 — 직접 방문·새 탭·JS 실패 경로가 남아야 한다."""
    assert CONNECT_HTML.exists()
    js = MODAL_JS.read_text(encoding="utf-8")
    assert "/ai/connect" in js


# ── 블로킹 대기 (사용자 요구 2026-08-27: 즉시 인지 · 폴링 금지) ────────────────


def test_wait_tool_holds_instead_of_polling():
    src = _func_source(AI_TOOLS, "wait_for_request")
    assert "asyncio.sleep" in src, "대기 루프가 없다"
    assert "_WAIT_MAX_HOLD_SEC" in src, "보류 상한이 서버 상수가 아니다"
    # 상한을 요청 본문에서 받으면 그게 곧 클라이언트 knob = 환경 차이다.
    assert "body.get(\"timeout\")" not in src and "body.get('timeout')" not in src, (
        "대기 시간을 클라이언트가 정한다 — 사람마다 다른 지연이 생긴다")


def test_wait_tool_commits_between_checks():
    """루프마다 커밋한다 — 없으면 트랜잭션 스냅샷이 고정돼 **새 행이 영원히 안 보인다**."""
    src = _func_source(AI_TOOLS, "wait_for_request")
    assert "conn.commit()" in src, "스냅샷 고정 함정(REPEATABLE READ)에 빠진다"


def test_wait_tool_timeout_is_not_an_error():
    """시간이 다 되면 200 + timed_out — 오류로 돌려주면 호출측이 재시도를 주저한다."""
    src = _func_source(AI_TOOLS, "wait_for_request")
    assert '"timed_out": True' in src
    assert "간격" in src, "곧바로 다시 호출하면 된다는 안내가 없다"


def test_wait_tool_stops_when_client_disconnects():
    src = _func_source(AI_TOOLS, "wait_for_request")
    assert "is_disconnected()" in src, "끊긴 클라이언트를 위해 DB 를 계속 두드린다"


@pytest.mark.parametrize("path", [MCP_HTTP, MCP_STDIO])
def test_wait_tool_registered_in_both_adapters(path):
    assert "wait_for_request" in path.read_text(encoding="utf-8")


def test_handoff_tells_ai_to_wait_not_poll():
    """지시문이 폴링 대신 대기를 지시하는가."""
    src = (WEB_SRC / "routers" / "oauth_as.py").read_text(encoding="utf-8")
    body = _func_source(WEB_SRC / "routers" / "oauth_as.py", "compose_connect_handoff")
    assert "wait_for_request" in body
    assert "폴링" in body, "왜 반복 호출하면 안 되는지 말하지 않는다"


def test_handoff_includes_self_install_of_the_runner():
    """설치까지 AI 가 하도록 **명령을 그대로** 준다(사용자 요구 2026-08-27)."""
    body = _func_source(WEB_SRC / "routers" / "oauth_as.py", "compose_connect_handoff")
    assert "bridge_agent.py" in body, "러너 설치 안내가 없다"
    assert "curl" in body and "--check" in body, "AI 가 실행할 수 있는 형태가 아니다"
    assert "/trust/rootCA.crt" in body, "사설 CA 안내가 없다 — 여기서 대부분 막힌다"


# ══════════════════════════════════════════════════════════════════════════════
# 모델·추론 강도 정합 (사용자 제보 2026-08-27)
#
# 웹 컴포저의 모델·추론 강도 선택은 기존 경로에서 그 요청의 LLM 호출을 지배한다.
# 브리지는 둘을 통째로 버려, 무엇을 고르든 답변이 달라지지 않았다 — 화면은 선택지를 주는데
# 실제로는 아무 효과가 없는 **거짓 조작면**이었다.
#
# 답은 개인 AI 가 만들므로 서버가 강제할 수 없다. 그래서 계약은 "강제" 가 아니라
# **"전달 + 못 맞추면 밝히기"** 다. 조용히 무시하는 것만 막는다.
# ══════════════════════════════════════════════════════════════════════════════


def test_task_persists_requested_model_and_reasoning():
    """요청 시점의 선택을 task 에 굳힌다 — 나중에 대화 설정을 바꿔도 이 요청의 요구는 안 변한다."""
    src = BOOTSTRAP.read_text(encoding="utf-8")
    for col in ("RequestedModel", "ReasoningLevel"):
        assert f'("{col}", "ALTER TABLE WebAiTasks ADD COLUMN {col}' in src, f"{col} 컬럼 미추가"
    enq = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert "RequestedModel, ReasoningLevel" in enq, "적재 SQL 이 두 값을 쓰지 않는다"


def test_ask_handler_forwards_model_and_reasoning():
    """핸들러가 **이미 계산해 둔** 값을 브리지에 넘긴다(dispatch 경로와 동형)."""
    src = CONVS.read_text(encoding="utf-8")
    call = src[src.index("agent_result = _enqueue_web_bridge_task("):]
    call = call[:call.index(")\n")]
    assert "requested_model=model" in call, "모델 선택이 버려진다"
    assert "reasoning_level=reasoning_level" in call, "추론 강도 선택이 버려진다"


def test_claim_returns_requested_quality():
    """점유 응답이 품질 요청을 전달한다 — 전달하지 않으면 AI 가 알 방법이 없다."""
    src = _func_source(AI_TOOLS, "claim_request")
    assert "_requested_quality(" in src
    assert '"requested": requested' in src


def test_requested_quality_asks_to_disclose_when_unmet():
    """맞출 수 없으면 **답변에 밝히라**고 지시한다.

    강제할 수 없는 것을 강제하는 척하면 안 된다. 하지만 조용히 무시하면 사용자는 자기 선택이
    반영된 줄 안다 — 그 착각만은 막아야 한다.
    """
    body = _func_source(AI_TOOLS, "_requested_quality")
    assert "밝히세요" in body or "밝혀" in body, "못 맞췄을 때 알릴 의무가 없다"
    assert "조용히 무시" in body, "왜 밝혀야 하는지가 없다(다음 사람이 지운다)"
    # 추론 강도는 런타임마다 이름이 달라 **값이 아니라 의도**로 전달해야 한다.
    assert "_REASONING_INTENT" in AI_TOOLS.read_text(encoding="utf-8")


def test_runner_actually_applies_the_requested_model():
    """러너가 받은 모델을 **실제 CLI 인자로 옮긴다** — 전달만 받고 안 쓰면 반쪽이다."""
    src = (_UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py").read_text(
        encoding="utf-8")
    assert "_MODEL_FLAG" in src, "런타임별 모델 지정 방법이 없다"
    for rt in ("claude", "codex", "gemini"):
        assert f'"{rt}": [' in src, f"{rt} 모델 플래그가 없다"
    assert "want_model" in src
    ask = src[src.index("def ask_local_ai("):src.index("# ── 프롬프트")]
    assert "cmd[:1] + flag" in ask, "모델 인자를 프롬프트 뒤에 붙이면 위치 인자로 먹힌다"


def test_runner_falls_back_when_model_unavailable():
    """요청 모델이 없으면 기본 모델로 답하되 **그 사실을 밝힌다**.

    모델 하나 때문에 답을 아예 못 주는 것보다 낫고, 조용히 바꾸는 것보다 낫다.
    """
    src = (_UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py").read_text(
        encoding="utf-8")
    assert "기본 모델로 재시도" in src
    assert "기본 모델로 답했습니다" in src, "모델이 바뀐 사실을 사용자에게 알리지 않는다"


# ── 실행 단계 노출 (사용자 제보 2026-08-27) ───────────────────────────────────
#
# 브리지 답변에는 서버 run 이 없어 'AI 추론' 탭이 비었다. 나는 그걸 "없는 것을 그리지 않는다"
# 며 그대로 뒀는데, 절반만 맞았다 — **답을 만든 추론은 우리 밖이지만, 그 AI 가 무엇을
# 조사했는지는 우리 안에 있다**(원장). 추측이 아니라 관측한 사실을 옮긴다.


def test_bridge_answer_carries_run_id():
    """`meta.run_id` 가 없으면 단계를 기록해도 화면이 찾지 못한다(프런트 조회 키)."""
    src = _func_source(AI_TOOLS, "_deliver_web_bridge_answer")
    assert '"run_id": task_id' in src, "단계 조회 키가 각인되지 않는다"


def test_steps_are_materialized_from_the_ledger():
    src = _func_source(AI_TOOLS, "_deliver_web_bridge_answer")
    assert "_materialize_bridge_steps(" in src
    body = _func_source(AI_TOOLS, "_materialize_bridge_steps")
    assert "tool_call_usage" in body, "관측 기록이 아니라 다른 곳에서 만들어낸다"
    assert "INSERT INTO agent_runtime.steps" in body


def test_steps_do_not_fabricate_reasoning():
    """LLM 사고 과정은 **비워 둔다** — 지어내면 이 패널 전체가 못 믿을 것이 된다."""
    body = _func_source(AI_TOOLS, "_materialize_bridge_steps")
    assert "'none'" in body, "reason_source 가 'none' 이 아니다(없는 사고를 있다고 표시)"
    assert "reason_text" not in body.split('"""')[2], "존재하지 않는 추론 텍스트를 채운다"


def test_steps_exclude_bridge_plumbing():
    """대기·점유·제출은 조사 내역이 아니다 — 사용자에게는 소음이다."""
    body = _func_source(AI_TOOLS, "_materialize_bridge_steps")
    for noise in ("wait_for_request", "claim_request", "submit_answer"):
        assert noise in body, f"{noise} 를 걸러내지 않는다"
    assert "skip" in body


def test_step_recording_never_blocks_delivery():
    """단계 기록 실패가 답변 전달을 막지 않는다 — 없으면 탭이 빌 뿐이다."""
    body = _func_source(AI_TOOLS, "_materialize_bridge_steps")
    assert "except Exception" in body and "return 0" in body


# ══════════════════════════════════════════════════════════════════════════════
# 사용자 제보 4건 (2026-08-27, 다른 세션 테스트 중)
#   ① 진행 상황을 알 방법이 없다  ② 5단계 시스템 프롬프트 미적용
#   ③ 첨부 배선 검토           ④ 제품 데이터소스 인지·표시
# ══════════════════════════════════════════════════════════════════════════════


# ── ① 진행 상황 ──────────────────────────────────────────────────────────────


def test_claim_marks_the_bubble_as_working():
    """점유하면 대기 말풍선이 **'처리 중'** 으로 바뀐다.

    토스트가 아니라 말풍선 본문을 바꾼다 — 토스트는 사라지고 새로고침하면 없다. 사용자가 알고
    싶은 것은 "지금 어떤 상태인가" 이고, 그건 화면에 남아 있어야 한다.
    """
    src = _func_source(AI_TOOLS, "claim_request")
    assert "_mark_bridge_working(" in src, "점유해도 화면에 아무 변화가 없다"
    body = _func_source(AI_TOOLS, "_mark_bridge_working")
    assert "UPDATE agent_runtime.messages" in body
    assert "'placeholder') = 'true'" in body, "대기 말풍선만 바꾸는 술어가 없다(남의 답변을 덮는다)"


def test_status_reports_a_single_phase():
    """국면을 **서버가 한 단어로** 정한다 — 프런트가 조합하면 화면마다 갈린다."""
    src = _func_source(AI_TOOLS, "bridge_status")
    assert '"phase"' in src
    for ph in ("not_connected", "waiting", "working", "done"):
        assert ph in src, f"국면 {ph} 가 없다"
    assert "connected" in src, "연결 여부를 알리지 않으면 영원히 오지 않을 답을 기다린다"


def test_status_connection_probe_fails_open():
    src = _func_source(AI_TOOLS, "bridge_status")
    tail = src[src.index("except Exception"):]
    assert "connected = True" in tail, "판정 실패 시 '연결 없음' 으로 단정하면 거짓 경보가 된다"


def test_frontend_reacts_to_phase_change_only():
    """전환된 순간에만 다시 읽는다 — 매 tick 갱신은 스크롤을 흔들고 요청을 배로 만든다."""
    js = COMPOSER_JS.read_text(encoding="utf-8")
    assert "_lastPhase" in js
    assert 'status.phase !== _lastPhase' in js
    assert 'status.phase === "working"' in js, "처리 중 전환을 화면에 반영하지 않는다"
    assert 'not_connected' in js, "연결 없음을 사용자에게 알리지 않는다"


# ── ② 5단계 시스템 프롬프트 ──────────────────────────────────────────────────


def test_claim_composes_the_layered_system_prompt():
    """전역·제품·역할·계정·개인 지침이 브리지 답변에도 적용된다.

    브리지는 `agent_core` 를 타지 않아 이 프롬프트가 통째로 빠져 있었다 — 같은 질문이 경로에
    따라 다른 규칙으로 답해졌다.
    """
    src = _func_source(AI_TOOLS, "claim_request")
    assert "_bridge_system_prompt(" in src
    assert '"system_prompt": system_prompt' in src, "조립하고도 AI 에게 주지 않는다"


def test_system_prompt_uses_the_same_composer_as_internal_path():
    """조립 로직을 다시 쓰지 않는다 — 두 벌이면 갈리고, 갈리면 한쪽이 낡는다."""
    body = _func_source(AI_TOOLS, "_bridge_system_prompt")
    assert "compose_system_prompt(" in body, "내부 경로와 다른 방식으로 조립한다"
    assert "role_id" in body and "account_id" in body and "product_id" in body


def test_task_persists_role_for_prompt_composition():
    """역할이 남아 있어야 역할별 지침을 조립할 수 있다."""
    src = BOOTSTRAP.read_text(encoding="utf-8")
    assert '("RoleId", "ALTER TABLE WebAiTasks ADD COLUMN RoleId' in src
    call = CONVS.read_text(encoding="utf-8")
    call = call[call.index("agent_result = _enqueue_web_bridge_task("):]
    assert "role_id=role_id_for_run" in call[:call.index(")\n")], "역할을 넘기지 않는다"


def test_runner_puts_system_prompt_first():
    """지침을 **맨 앞**에 둔다 — 뒤에 두면 앞의 지시가 이기고 운영자 설정이 무시된다."""
    src = (_UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py").read_text(
        encoding="utf-8")
    body = src[src.index("def compose_prompt("):src.index("# ── 한 건 처리")]
    assert "system_prompt" in body
    assert body.index("시스템 프롬프트로 삼아") < body.index("너는 사내 DB 질의 어시스턴트다"), (
        "운영자 지침이 기본 지시보다 뒤에 온다")


def test_prompt_failure_does_not_block_the_answer():
    """프롬프트 조립 실패가 답변을 막지 않는다 — 막으면 설정 하나가 서비스를 세운다."""
    body = _func_source(AI_TOOLS, "_bridge_system_prompt")
    assert 'return ""' in body and "logging" in body, "조용히 실패하거나, 실패로 답변을 막는다"


# ── ③ 첨부 ───────────────────────────────────────────────────────────────────


def test_attachment_wiring_is_end_to_end():
    """적재 → 목록 → 본문 읽기 → 프롬프트 고지까지 끊긴 데가 없는가."""
    enq = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert "AttachmentIds" in enq, "적재에서 끊긴다"
    claim = _func_source(AI_TOOLS, "claim_request")
    assert "_task_attachment_list(" in claim and '"attachments"' in claim, "목록에서 끊긴다"
    runner = (_UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py").read_text(
        encoding="utf-8")
    assert "read_task_attachment" in runner, "러너가 본문 읽는 법을 알려주지 않는다"
    assert "반드시 본문을 읽고 답하라" in runner, "첨부를 읽지 않고 답할 여지를 남긴다"


# ── ④ 제품·데이터소스 ────────────────────────────────────────────────────────


def test_claim_tells_which_product_and_datasource():
    """도구 경계는 이미 제품으로 묶인다(집행). 여기서 주는 것은 **인지**다 —
    무엇을 보고 있는지 모르면 엉뚱한 스키마를 찾아 헤맨다."""
    src = _func_source(AI_TOOLS, "claim_request")
    assert "_bridge_product_scope(" in src and '"scope": scope' in src
    body = _func_source(AI_TOOLS, "_bridge_product_scope")
    assert "WebProducts" in body, "제품 이름을 주지 않는다"
    assert "allowed_datasource_labels" in body, "데이터소스를 주지 않는다"


def test_runner_states_the_target_product():
    src = (_UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py").read_text(
        encoding="utf-8")
    assert "대상 제품" in src, "프롬프트에 대상 제품이 없다"


def test_answer_keeps_product_attribution_for_the_web_view():
    """웹 화면이 '어느 제품이 답했는지' 를 보이려면 각인이 있어야 한다(이미 세운 계약의 유지)."""
    src = _func_source(AI_TOOLS, "_deliver_web_bridge_answer")
    assert "_answer_product_attribution(" in src
