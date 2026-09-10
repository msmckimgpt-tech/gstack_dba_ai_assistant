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
    """모듈에서 함수 하나의 소스만 떼어낸다 — **docstring 과 주석을 뺀 코드만**.

    ⚠ 종전에는 `ast.get_source_segment` 결과를 그대로 돌려줬고 거기엔 **docstring 이
    포함**됐다. 그래서 이 헬퍼를 경유하는 모든 「X 가 있다」 단언을 그 함수 자신의 설명
    문장이 통과시켰다 — qa 적대리뷰가 뮤턴트로 실증했다: `_profile.get("caps" "_trusted")`
    (동작 동일, 토큰은 코드에서 사라짐)를 넣어도 `assert "caps_trusted" in body` 가 green.
    §16.7 **G11-a** 가 「가장 위험한 형태」로 지목한 바로 그것이다.

    ⚠ **`ast.unparse` 로 재출력하지 않는다.** 그러면 포맷이 정규화돼(따옴표·줄바꿈·괄호)
    이 헬퍼를 쓰는 **무관한 단언들이 무더기로 깨진다**(실측: 15건). 원문 형식은 보존하고
    **docstring 이 차지한 줄만** 잘라낸다 — 잘라낼 범위는 파서가 준 `lineno`/`end_lineno`
    라서 행 단위 휴리스틱(`grep -v '^\\s*#'`)의 오탐(블록 주석·멀티라인 문자열)이 없다.

    ⚠ 주석(`#`)은 **남긴다**. 「X 가 없다」류 부재 단언이 이 헬퍼를 쓸 수 있고, 그 경우
    리터럴·주석을 지우면 찾으려는 결함 라인을 건너뛴다(G11-a 의 부재-단언 예외). 존재
    단언에서 주석이 문제가 되면 그 단언은 AST 로 올려야 한다 — 그것이 정답이다.
    """
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            seg = ast.get_source_segment(src, node) or ""
            body = node.body
            if not (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                return seg
            # docstring 이 차지한 줄 범위를 함수 시작 기준으로 환산해 제거한다.
            lo = body[0].lineno - node.lineno
            hi = (body[0].end_lineno or body[0].lineno) - node.lineno
            lines = seg.splitlines()
            out = "\n".join(lines[:lo] + lines[hi + 1:])
            # ⚠ `def f(): """doc"""` 처럼 docstring 이 **시그니처와 같은 줄**이면 `lo == hi == 0`
            #   이라 위 슬라이스가 시그니처까지 지워 **빈 문자열**을 돌려준다. 그러면 이 헬퍼를
            #   쓰는 「X 가 없다」 단언이 전부 vacuous 하게 통과한다(qa 적대리뷰 — 검사 대상이
            #   비어 있을 때 PASS). 그런 함수는 잘라낼 것이 없으므로 원문을 그대로 준다.
            if not out.strip() or f"def {name}" not in out:
                return seg
            return out
    raise AssertionError(f"{path.name}: 함수 {name} 를 찾지 못했다(이름이 바뀌었나?)")


def _bridge_enqueue_kwarg(name: str) -> ast.expr:
    """`_enqueue_web_bridge_task(...)` 호출이 그 이름으로 넘기는 **값 노드**.

    ⚠ 문자열 자르기(`call[:call.index(")\\n")]`)를 쓰지 않는다 (2026-08-31). 인자 사이 주석에
    닫는 괄호가 하나만 있어도 호출이 거기서 잘려, 실제로는 넘기고 있는 인자를 "안 넘긴다" 고
    보고한다 — 실제로 그렇게 깨졌다. 계약("이 인자를 넘긴다")은 그대로 두고 읽는 방법만
    구조 기반으로 바꾼다.
    """
    src = CONVS.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_enqueue_web_bridge_task"):
            for kw in node.keywords:
                if kw.arg == name:
                    return kw.value
            raise AssertionError(f"적재 호출이 {name} 를 넘기지 않는다")
    raise AssertionError("브리지 적재 호출을 찾지 못했다 — 경로가 사라졌나?")


def _js_func_source(path: pathlib.Path, name: str) -> str:
    """JS 파일에서 `function <name>(` 하나의 본문만 떼어낸다(중괄호 균형 기준).

    파일 전역 문자열 검색은 **다른 함수의 코드**를 근거로 통과할 수 있다 — 특히 composer.js 는
    한 파일에 수십 개 함수가 산다. 문자열·주석 안의 중괄호까지 세지는 않지만(그러면 파서를
    새로 쓰는 셈이다), 함수 경계를 넘어가는 오검출은 이것으로 충분히 막힌다.
    """
    src = path.read_text(encoding="utf-8")
    for pattern in (f"function {name}(", f"async function {name}("):
        at = src.find(pattern)
        if at >= 0:
            break
    else:
        raise AssertionError(f"{path.name}: JS 함수 {name} 를 찾지 못했다(이름이 바뀌었나?)")
    start = src.index("{", at)
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[at:i + 1]
    raise AssertionError(f"{path.name}: {name} 의 중괄호가 닫히지 않는다")


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
    # 이 계약은 **적재가 있는 연결 분기**의 것이다 — 미연결 분기는 되돌릴 적재가 없다.
    connected = src[src.index("# ① 대기 작업 적재"):]
    assert "if not saved:" in connected
    assert connected.index("if not saved:") < connected.index("_bridge_save_core_message("), (
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


def test_node_analysis_refuses_before_enqueue_only_when_nowhere_to_delegate(monkeypatch):
    """분석은 **큐에 넣기 전에** 판정한다 — 그러나 판정 대상이 바뀌었다.

    ## 무엇이 바뀌었나 (TASK-20260901T190000)

    종전 계약은 「서버 계정 LLM 이 닫혀 있으면 거절」이었다. 그 계약대로 라이브는 그래프
    'AI 능동 분석' 을 **통째로 막고 있었고**, 사용자가 그것을 제보했다:

    > "'그래프 뷰' 내 'AI 능동 분석'에 대한 기능이 막혀있는것으로 확인되었습니다.
    >  서비스 내 AI 관련 모든 작동사항을 다시 활성화 후, 연결한 AI를 통해 작동하도록 배선"

    새 계약은 「**두 경로 중 하나라도** 있으면 진행, 둘 다 없으면 시작 전에 거절」이다.
    지켜야 할 것은 그대로다 — *큐에 넣어 놓고 한참 뒤 알 수 없는 실패로 끝내지 않는다.*

    소스가 아니라 **판정 결과**를 본다: 게이트 함수를 실제로 돌려 세 경우를 모두 확인한다.
    """
    import types

    namespace = {}
    exec(_func_source(NODE_ANALYSIS, "_analysis_gate"), namespace)
    na = types.SimpleNamespace(_analysis_gate=namespace["_analysis_gate"], delegation_possible=None)

    # (1) 서버 LLM 닫힘 + 위임할 곳 없음 → **거절**(종전 계약의 핵심은 여기서 유지된다)
    monkeypatch.setenv("AGENT_SERVER_LLM_ENABLED", "")
    monkeypatch.setitem(namespace, "delegation_possible", lambda who: False)
    reason = na._analysis_gate("alice")
    assert reason, "위임할 곳도 없는데 통과시키면 잡마다 재시도를 태우고 실패로 끝난다"

    # (2) 서버 LLM 닫힘 + 연결된 AI 있음 → **진행**(제보된 결함이 고쳐진 지점)
    monkeypatch.setitem(namespace, "delegation_possible", lambda who: True)
    assert na._analysis_gate("alice") == "", "연결된 AI 가 있는데도 막고 있다"

    # (3) 게이트를 되돌린 운영 → 진행
    monkeypatch.setenv("AGENT_SERVER_LLM_ENABLED", "1")
    monkeypatch.setitem(namespace, "delegation_possible", lambda who: False)
    assert na._analysis_gate("alice") == ""

    # 두 진입점 모두 **그 판정 함수를 부른다**(한쪽만 고치면 스키마 단위 분석이 계속 막힌다).
    for func in ("enqueue_analysis", "enqueue_schema_analysis"):
        body = _func_source(NODE_ANALYSIS, func)
        assert "_analysis_gate(" in body, f"{func}: 게이트 판정을 부르지 않는다"


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


def test_insight_tick_runs_job_processing_unconditionally():
    """워커 틱은 잡 처리를 **게이트 없이** 부른다 (TASK-20260901T190000).

    ## 이 테스트는 종전에 결함을 계약으로 못박고 있었다

    옛 이름은 `test_insight_skips_only_llm_work` 였고, 단정은
    `assert "process_pending() if _llm_open else {}" in src` 였다. 전환 이전에는 **옳았다** —
    적재 자체가 게이트로 막혀 있었으므로 대기 잡이 생기지 않았고, 차단 중에 claim 하면
    재시도 상한만 태웠다.

    그 전제가 깨졌다. 이제 게이트가 닫혀 있어도 적재된다(연결된 개인 AI 가 처리한다).
    그 상태에서 호출부가 게이트 안에 남아 있으면:

      · 적재된 그래프 분석을 **아무도 처리하지 않는다** — 사용자 제보("막혀 있다")가 형태만
        바꿔 되돌아온다(202 는 뜨는데 결과가 영영 안 온다)
      · stale `running` 회수가 **영원히 돌지 않는다** — run 이 굳어 재트리거까지 막힌다

    라이브 실측(2026-09-02): lease 900초를 **1424초**까지 넘겼는데 회수되지 않았다.

    판정은 **잡 단위로 함수 안에서** 한다(열림=직접 호출 · 닫힘=위임 · 맡길 곳 없음=상한 있는
    유예). 그러므로 호출부에는 조건이 없어야 한다.
    """
    src = _func_source(NODE_ANALYSIS.parent / "insight.py", "run_insight_cycle")
    assert "process_pending()" in src, "잡 처리를 아예 부르지 않는다"
    assert "process_pending() if " not in src, (
        "잡 처리가 다시 게이트 안으로 들어갔다 — 위임도 회수도 영영 돌지 않는다")
    # 종전 계약 중 **여전히 유효한 축**: LLM 무관 정비까지 끄지 않는다.
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
    # ⚠ 문자열 슬라이스로 보지 않는다. 분기가 둘이 되자(연결/미연결) 앞 분기의 안내 뒤에
    #   뒤 분기의 **질문** core 기록이 걸려 오탐이 났다. 호출의 **인자**를 직접 본다.
    import ast

    src = CONVS.read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
              and n.name == "_enqueue_web_bridge_task")
    roles = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_bridge_save_core_message":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    roles.append(a.value)
                elif isinstance(a, ast.Name):
                    roles.append(f"<{a.id}>")
    assert roles, "회수 store 기록이 아예 없다"
    assert "assistant" not in roles, (
        "안내를 회수 store 에 썼다 — LLM 문맥에 가짜 assistant turn 이 생긴다")
    assert "<notice_text>" not in roles


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
    body = src[src.index("_BRIDGE_NOTICE_NOT_CONNECTED = ("):src.index("#: 승격 경쟁에서 밀렸거나")]
    assert "연결되어 있지 않습니다" in body
    assert "[AI 연결하기](/ai/connect)" in body, (
        "누를 수 있는 링크가 없다 — 경로 문자열은 사용자가 어떻게 할 수 없다")
    # 질문이 사라지지 않았다는 사실을 반드시 말한다(설정하러 가는 동안 불안하지 않게).
    #
    # ⚠ 2026-08-28 계약 변경: 이제 **보관**한다(`deferred`) — 연결하면 그 질문부터 처리한다.
    # 그래서 "다시 질문하라" 가 아니라 "다시 입력하지 않아도 된다" 가 맞다. 다만 여러 번 물은
    # 경우 1건만 처리되므로 **그 규칙까지** 말해야 기대가 어긋나지 않는다.
    assert "이 질문부터" in body
    assert "다시 입력하지" in body
    assert "마지막 질문 1건" in body


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
    # 러너가 안 듣는 사용자에게 "내 AI 에게 보냈습니다" 는 거짓이다 — 가져갈 프로세스가 없다.
    # 대신 보관 사실과 다음 행동을 말한다. P0-AB 로 그 '다음 행동' 이 바뀌었다: 토큰은 이미
    # 있으므로 새로 연결할 필요가 없고, **실행만** 하면 된다.
    assert "내 AI 를 실행하면" in src, "러너가 꺼진 사용자에게도 '내 AI 가 처리' 라고 말한다"
    assert "보관했습니다" in src, "질문이 보관됐다는 사실을 알리지 않는다"
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
    # ⚠ 기준 버튼이 바뀌었다 — 「연결 준비」가 사라졌으므로(2026-09-07) 주 버튼은 실행이다.
    assert html.index("aic-why") < html.index("launchClient"), "안내가 버튼 뒤에 있다"


def test_connect_page_tells_where_to_paste():
    """붙여넣을 **대상**을 말한다.

    ⚠ 대상이 바뀌었다 (P0-AC, 사용자 결정 2026-08-28). 기본 경로가 AI 지시문에서 **터미널
    명령**으로 교체됐으므로 1차 대상은 터미널이다. AI 는 접힌 보조 경로에 남아 있고, 그쪽
    안내도 여전히 대상을 말해야 한다 — 계약(대상을 밝힌다)은 그대로, 대상만 둘이 됐다.
    """
    html = CONNECT_HTML.read_text(encoding="utf-8")
    # ⚠ **경로가 하나만 남았다** (사용자 결정 2026-09-07): 터미널·AI 지시문 전면 제거.
    #   붙여넣을 것이 없으므로 계약도 「대상을 밝힌다」에서 **「할 일을 밝힌다」** 로 옮긴다 —
    #   지키려던 성질(사용자가 다음에 무엇을 하는지 안다)은 그대로다.
    assert "내 AI 실행" in html, "무엇을 눌러야 하는지 알려주지 않는다"
    assert "DQA 앱 받기" in html, "아직 앱이 없는 사용자가 무엇을 해야 하는지 말하지 않는다"
    body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    assert "붙여넣" not in body, "사라진 붙여넣기 경로를 아직 안내한다"


def test_connect_page_promises_the_human_is_done_after_pasting():
    """붙여넣은 뒤로는 **사람이 할 일이 없다**고 명시한다(사용자 결정 2026-08-27).

    문구는 짧게 유지하되(슬롭 제거 2026-08-27) 이 약속 자체는 남는다 — 이게 없으면 사용자는
    "그다음엔 뭘 해야 하지" 를 계속 찾는다.

    ⚠ P0-AC 로 **기본 경로에서는 AI 가 아니라 스크립트가** 나머지를 한다. 그래서 약속의 주어가
    바뀌었다: "붙여넣으면 끝" + "끝나면 입력창이 열린다". AI 경로의 약속은 보조 경로에 남는다.
    """
    html = CONNECT_HTML.read_text(encoding="utf-8")
    # ⚠ 문구가 또 바뀌었다(2026-09-07) — 붙여넣을 것이 없어졌으므로 약속의 주어도 바뀐다:
    #   「연결은 DQA 앱이 합니다」. 보조 경로(AI 가 판단합니다)는 **사라졌다**.
    #   약속 자체(사람이 할 일이 여기서 끝난다)는 그대로 남는다.
    assert "DQA 앱에서 이 컴퓨터의 AI를 연결하세요" in html, (
        "주 경로에서 사람이 할 일의 끝을 말하지 않는다")
    assert "내 AI 실행" in html, "끝난 뒤 무엇이 달라지는지 말하지 않는다"


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
    # ⚠ **전제가 뒤집혔다 (사용자 결정 2026-09-07).** 이 화면은 토큰을 보여주지 않으므로
    #   「토큰이라는 말을 유지하되 풀어 설명한다」의 대상이 없다. 남은 절반 — **새 이름을
    #   지어내지 않는다** — 은 되살아날 때를 위해 그대로 잠근다.
    assert "열쇠" not in html, "용어를 두 벌로 만들면 사용자가 매칭에 실패한다"
    if "비밀번호처럼" in html:
        assert "토큰" in html, "설명만 있고 매칭에 쓰이는 말(토큰)이 없다"


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

    ⚠ P0-AC 로 경로가 둘이 됐다(명령 · AI 지시문). 그래도 **한 화면에 나란히 놓지는 않는다** —
    지시문은 `<details>` 안에 접혀 있어, 펼치기 전까지 사용자가 보는 복사 버튼은 여전히 하나다.
    "선택을 시키지 않는다" 는 원래 계약은 개수가 아니라 **동시 노출**의 문제였다.
    """
    html = CONNECT_HTML.read_text(encoding="utf-8")
    visible = re.sub(r"<details.*?</details>", "", html, flags=re.S)
    # ⚠ **0 이 됐다** (사용자 결정 2026-09-07). 복사할 것(명령·지시문)이 통째로 사라졌으므로
    #   「어느 걸 복사하지?」라는 선택도 함께 사라졌다. 계약의 상한(≤1)은 그대로 두고 —
    #   0 도 만족한다 — 되살아나는 것만 막는다.
    assert visible.count("복사</button>") == 0, (
        "복사 버튼이 되살아났다 — 복사할 대상은 이 화면에 없다")
    assert "주소만 복사" not in html


def test_connect_page_does_not_send_humans_to_the_api_reference():
    """사람에게 `/api/ai/guide`(API 레퍼런스)를 권하지 않는다(사용자 제보 2026-08-27).

    그 문서가 필요한 쪽은 **AI** 이고, 지시문에 이미 URL 이 실려 있다. 사람이 눌러 가면
    스펙 문서를 만난다.
    """
    html = CONNECT_HTML.read_text(encoding="utf-8")
    assert "/api/ai/guide" not in html, "사람용 화면이 API 레퍼런스로 보낸다"
    # 2026-08-28: 지시문이 서버로 이동했다(프런트 사본이 서버 문안과 갈려 라이브에서 옛 안내가
    # 나갔다 — PB-0008). 계약의 뒷절(“AI 용 지시문에는 남아 있어야 한다”)은 그대로 유효하므로
    # **대상만** 정본으로 옮긴다. 프런트에는 이제 그 URL 이 없는 것이 정상이다.
    handoff = _func_source(WEB_SRC / "routers" / "oauth_as.py", "compose_connect_handoff")
    assert "/api/ai/guide" in handoff, "지시문(AI 용)에서는 가이드 URL 이 빠지면 안 된다"
    assert "/api/ai/guide" not in CONNECT_JS.read_text(encoding="utf-8"), (
        "프런트에 가이드 URL 이 남아 있다 — 지시문 사본이 되살아났다는 신호다")


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
    expected = structural + 3 + 4 + 1  # get_tool_catalog
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


#: 지시문을 표시하는 화면 **전부**. 하나라도 빠지면 그 화면만 옛 문안을 내보낸다.
_HANDOFF_SURFACES = [
    ("대화 화면 모달", MODAL_JS),
    ("단독 페이지 /ai/connect", WEB_SRC / "static" / "ai-connect.js"),
]


@pytest.mark.parametrize("label,path", _HANDOFF_SURFACES, ids=lambda v: getattr(v, "name", v))
def test_every_surface_uses_the_server_composed_handoff(label, path):
    """지시문을 **서버에서 받는다** — 화면이 조립하면 문안이 갈린다.

    종전 이 계약은 **모달에만** 걸려 있었고, 그동안 `/ai/connect` 단독 페이지는 자체 조립본을
    내보내고 있었다. 서버 문안이 CA 지문·러너 체크섬·상주 러너 절차·TLS 신뢰 범위를 담도록
    여러 차례 개정되는 사이 그 사본은 **몇 세대 뒤처진 문안**(러너·TLS·검증 값 전무 +
    거절 사유였던 '나한테 더 묻지 않아도 돼')을 그대로 보여줬다.

    소스 테스트는 전부 green 이었다 — **검사 대상 목록에 그 화면이 없었기** 때문이다.
    라이브 PB-0008 이 화면을 열어 보고서야 드러났다(2026-08-28). 그래서 계약을 화면 하나가
    아니라 **표시하는 곳 전부**에 건다.
    """
    js = path.read_text(encoding="utf-8")
    # ⚠ **전제가 뒤집혔다 (사용자 결정 2026-09-07).** 종전 계약은 「지시문을 서버에서 받아라」
    #   였다 — 프런트가 조립하면 문안이 갈리기 때문이다. 지금은 **어느 화면도 지시문을 보여
    #   주지 않는다.** 그러므로 지켜야 하는 것은 「서버에서 받는가」가 아니라 **「되살아나지
    #   않는가」** 다. 원래 걱정(사본이 산다)은 그대로이고, 사본이 없으려면 표시가 없어야 한다.
    assert "body.handoff" not in js, f"{label}: 지시문 표시가 되살아났다"
    # 자체 조립의 지문 — 이 조각이 있으면 서버 문안과 별개의 사본이 산다(계약 그대로).
    for token in ("mcpServers", "Authorization: Bearer \" +", "list_open_requests 로"):
        assert token not in js, f"{label}: 지시문 조각을 직접 조립한다({token!r})"


def test_modal_never_puts_a_token_in_the_dom():
    """⚠ **전제가 뒤집혔다 (사용자 결정 2026-09-07).**

    종전 계약은 「창을 열고 닫을 때 토큰이 실린 본문을 비워라」였다 — 화면에 토큰을 그렸기
    때문이다. 지금은 **그리지 않는다.** 토큰은 스킴 URL 안에 실려 프로그램으로 바로 건네지고
    사용자가 그 값을 보거나 복사할 일이 없다.

    지키려던 성질(토큰이 DOM 에 남지 않는다)은 **더 강하게** 만족된다 — 애초에 넣지 않으므로
    지울 것도 없다. 그래서 「지우는가」가 아니라 **「넣는 자리가 있는가」** 를 잰다.
    """
    js = MODAL_JS.read_text(encoding="utf-8")
    # 토큰을 그리던 자리들. 하나라도 되살아나면 지우는 계약도 함께 되살려야 한다.
    for gone in ("connectModalText", "connectModalCmd", "connectModalProbe", "body.handoff"):
        assert gone not in js, f"토큰 표시 자리가 되살아났다({gone}) — 지우는 계약도 필요하다"


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
    """시간이 다 되면 200 + timed_out — 오류로 돌려주면 호출측이 재시도를 주저한다.

    2026-08-28: 취소 통보가 같은 응답에 실리면서 `timed_out` 이 상수에서 **조건**이 되었다.
    취소로 대기가 풀린 것은 시간이 다 된 것이 아니기 때문이다(기다림이 끝난 이유가 다르다).
    """
    src = _func_source(AI_TOOLS, "wait_for_request")
    assert '"timed_out": not canceled' in src, (
        "취소로 풀린 대기까지 timed_out 으로 보고한다 — 호출측이 취소를 못 알아본다")
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
# 모델·추론 강도 — **브리지 모드에서는 조작면 자체를 제거한다** (P0-T, 사용자 결정 2026-08-28)
#
# 앞선 계약(P0-M, 2026-08-27)은 "전달 + 못 맞추면 밝히기" 였다. 라이브에서 그 계약은 이렇게
# 작동했다: 화면 값은 서비스 내부 alias(`claude-haiku-4`)이고 그것을 아는 CLI 는 없다 —
# 기본값이 haiku 이므로 사실상 **모든** 브리지 요청이 모델 지정 실패 → 기본 모델 폴백이었다.
# 요청은 반영되지 않으면서 "못 맞췄다" 는 고지만 매번 붙는, 있으나 마나 한 왕복.
#
# 게다가 서버는 연결된 런타임이 claude 인지 codex·gemini·ollama 인지 **알 방법이 없다**
# (MCP 어댑터가 별도 컨테이너라 clientInfo 가 오지 않는다). 맞는 값으로 번역할 수도 없다.
#
# 사용자 결정: 제어할 수 없으면 보여주지 않는다. 여기서 잠그는 것은 **네 지점**이다 —
# 카탈로그(서버) · 조작면(화면) · 적재(DB) · 전달(도구/러너). 한 곳이라도 살아 있으면
# 사용자는 다시 "고를 수 있는데 반영은 안 되는" 상태를 만난다.
#
# ⚠ 이중 계약: 게이트를 되돌리면(`AGENT_SERVER_LLM_ENABLED=1`) 선택기는 **복원돼야** 한다.
# 숨김만 검사하면 "영구 제거" 뮤턴트가 통과한다.
# ══════════════════════════════════════════════════════════════════════════════


def test_catalog_gates_selector_on_server_llm_state():
    """카탈로그 핸들러가 **게이트를 매 호출 읽고** 양방향으로 분기한다.

    한쪽만 검사하면 뮤턴트가 통과한다 — 숨김만 보면 '영구 제거' 가, 복원만 보면 '차단 중에도
    목록 노출' 이 살아남는다. 반환값 대조는 DB 연결이 필요하므로 feature-0003 스위트
    (`test_model_catalog_bridge_mode.py`)가 담당하고, 여기서는 **배선**을 잠근다.

    P0-Z3(2026-08-28) 이후 차단 상태의 분기가 하나 더 생겼다 — 러너 신고가 있으면 `visible`,
    없으면 종전대로 `hidden`. 그래서 "차단 = 항상 숨김" 을 잠그던 종전 단언은 **거짓이 된다**
    (그대로 두면 새 계약이 회귀로 보고된다). 대신 세 갈래가 모두 배선돼 있는지를 잠근다.
    """
    src = (WEB_SRC / "routers" / "system.py").read_text(encoding="utf-8")
    body = _func_source(WEB_SRC / "routers" / "system.py", "get_api_vault_options")
    assert "server_llm_enabled()" in body, "핸들러가 게이트를 호출하지 않는다(상수로 굳으면 못 되돌린다)"
    assert '"visible" if visible else "hidden"' in body, (
        "차단 상태의 숨김/노출이 러너 신고 유무로 갈리지 않는다 — 한쪽으로 굳으면 "
        "'고를 게 없는데 선택기가 뜨거나' '신고했는데 영영 숨는다'")
    assert "account_runner_profile(" in body, (
        "카탈로그가 러너 신고를 읽지 않는다 — 목록의 출처가 서버로 되돌아간 것이다(P0-T 재발)")
    assert '"model_selector": "visible"' in body, "게이트 해제 시 선택기를 복원하는 분기가 없다"
    assert "from shared.llm_gate import server_llm_enabled" in src
    # 숨김의 **이유**를 값으로 말한다 — 프런트가 사유 문구를 파싱하지 않게.
    # (2026-09-01 재설계: 종전 `caps_contract_declared`·`runner_mixed` 두 축은 철회하고
    #  「러너가 듣고 있는가」 한 축만 남겼다. 능력 게이트는 수신 시점에 있다.)
    assert '"runner_listening": runner_listening' in body, (
        "숨김의 이유를 값으로 말하지 않는다 — 프런트가 사유 문구를 파싱하게 된다")


def test_catalog_never_guesses_runner_models_on_failure():
    """능력 조회가 실패하면 목록을 **추측으로 채우지 않는다** (P0-Z3).

    권한 필터 실패는 fail-soft 로 전체 목록을 주지만(부트스트랩 경로라 선택기를 비우지 않는
    쪽이 낫다), 러너 능력은 다르다 — 여기서 추측한 이름은 그 러너에 없을 수 있고, 고른 순간
    반영되지 않는다. 그것이 정확히 P0-T 가 지운 상태다.
    """
    body = _func_source(WEB_SRC / "routers" / "system.py", "get_api_vault_options")
    # 핸들러 자신의 except/finally 만 본다 — 들여쓰기를 앵커에 포함해 **안쪽 try** 의
    # except 를 집지 않게 한다(2026-08-31: 계정 기본값 조회를 감싸는 중첩 try 가 생기면서
    # 종전 앵커가 그쪽을 먼저 잡아 거짓 실패했다).
    except_block = body[body.index("\n    except Exception:"):]
    except_block = except_block[:except_block.index("\n    finally:")]
    assert "runner_caps = []" in except_block, (
        "능력 조회 실패 시 빈 목록으로 닫지 않는다 — fail-soft 가 fail-open 이 된다")


def test_composer_hides_selector_on_explicit_server_signal():
    """화면 숨김은 **서버가 실어 준 명시 값**으로만 판정한다.

    카탈로그 로드 실패(null)로 숨기면 일시적 네트워크 장애가 조작면을 지우고, 사용자는
    기능이 사라진 것으로 읽는다.
    """
    src = COMPOSER_JS.read_text(encoding="utf-8")
    fn = src[src.index("function _composerModelSelectorHidden("):]
    fn = fn[:fn.index("\n}")]
    assert 'model_selector' in fn and '"hidden"' in fn
    apply_fn = src[src.index("function _applyComposerSelectorVisibility("):]
    apply_fn = apply_fn[:apply_fn.index("\n}\n")]
    for dom_id in ("composerActionsModelItem", "composerActionsReasoningItem"):
        assert dom_id in apply_fn, f"{dom_id} 가 숨김 대상에 없다"
    assert 'classList.toggle("hidden"' in apply_fn, "숨김이 토글이 아니면 복원되지 않는다"


def test_composer_menus_refuse_to_open_while_hidden():
    """숨김 상태에서 메뉴를 여는 경로가 남아 있으면 키보드·직접 호출로 되살아난다."""
    src = COMPOSER_JS.read_text(encoding="utf-8")
    for fn_name in ("_openComposerModelMenu", "_openComposerReasoningMenu"):
        body = src[src.index(f"function {fn_name}("):]
        body = body[:body.index("\n}\n")]
        assert "_composerModelSelectorHidden()" in body, f"{fn_name} 에 숨김 가드가 없다"


def test_ask_payload_omits_model_and_reasoning_while_hidden():
    """보여주지도 않은 값을 전송하지 않는다.

    싣는 순간 대화 KV 에 저장되고, 게이트를 되돌렸을 때 **사용자가 고른 적 없는 모델**이
    그 대화의 설정으로 되살아난다.
    """
    send = _js_func_source(COMPOSER_JS, "sendPrompt")
    assert "_composerModelSelectorHidden()" in send, "전송 경로가 숨김 상태를 모른다"
    assert "askBody.reasoning_level = _composerCurrentReasoningLevel()" in send, (
        "추론 강도를 조건부로 싣는 형태가 아니다")
    # 재답변(요청사항 수정) 경로도 같은 판정을 써야 한다 — 한쪽만 막으면 그쪽으로 샌다.
    edit = _js_func_source(APP_JS, "_submitMessageEdit")
    assert "_composerModelSelectorHidden()" in edit, "재답변 경로에 숨김 판정이 없다"


def test_bridge_task_persists_the_picked_runtime_model_and_level():
    """적재 SQL 이 고른 값 **셋 다**를 굳힌다 (P0-Z3 — P0-T 의 미적재를 되돌린다).

    셋인 이유: 모델 이름만으로는 어느 CLI 의 것인지 정해지지 않는다(한 머신에 claude·codex 가
    함께 있을 수 있다). 런타임이 빠지면 러너가 같은 것을 실행한다는 보장이 사라진다.

    요청 시점에 굳히는 것이 계약이다 — 나중에 대화 설정을 바꿔도 이 질문에 무엇이 요구됐는지는
    변하지 않아야 한다(각인과 같은 이유).
    """
    enq = _func_source(CONVS, "_enqueue_web_bridge_task")
    insert = enq[enq.index("INSERT INTO WebAiTasks"):]
    insert = insert[:insert.index("VALUES")]
    for col in ("RequestedRuntime", "RequestedModel", "ReasoningLevel"):
        assert col in insert, f"{col} 을 적재하지 않는다 — 고른 값이 러너에 닿지 않는다"
    # 호출부가 실제로 넘긴다(시그니처만 받고 호출부가 안 주면 항상 NULL 이 굳는다).
    # 값의 **모양**까지는 여기서 보지 않는다 — 무지정을 무지정으로 넘기는 계약은
    # `test_bridge_request_pins.py` 가 AST 로 따로 잠근다(2026-08-31).
    _bridge_enqueue_kwarg("requested_model")
    _bridge_enqueue_kwarg("reasoning_level")
    # 런타임·모델은 화면 값(`runtime:model`)을 **적재 시점에** 가른다.
    assert "_split_runtime_model(" in enq, "런타임과 모델의 짝을 가르지 않는다"
    # 이력 보존: 스키마에서 컬럼을 지우지 않았다.
    boot = BOOTSTRAP.read_text(encoding="utf-8")
    for col in ("RequestedRuntime", "RequestedModel", "ReasoningLevel"):
        assert f'("{col}", "ALTER TABLE WebAiTasks ADD COLUMN {col}' in boot, (
            f"{col} 컬럼이 없다(또는 삭제됐다) — 과거 행의 값이 사라진다(이력 파괴)")


def test_split_runtime_model_keeps_the_pair_together():
    """`"<runtime>:<model>"` 을 가르되, 접두 없는 값은 **런타임을 지어내지 않는다** (P0-Z3)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_convs_probe", CONVS)
    # 모듈 전체 import 는 app 의존이 무거우므로 함수 소스만 떼어 실행한다.
    src = CONVS.read_text(encoding="utf-8")
    start = src.index("def _split_runtime_model(")
    end = src.index("\n\n\n", start)
    ns: dict = {"Any": object}
    exec(src[start:end], ns)  # noqa: S102 — 테스트가 대상 함수를 격리 실행
    split = ns["_split_runtime_model"]
    assert split("claude:sonnet") == ("claude", "sonnet")
    assert split("codex:gpt-5.1-codex") == ("codex", "gpt-5.1-codex")
    # 접두 없음(구 대화 KV 의 서버 alias) → 런타임 None. 러너는 자기 표에 없는 모델을 버린다.
    assert split("claude-haiku-4") == (None, "claude-haiku-4")
    assert split("") == (None, None)
    assert split(None) == (None, None)
    # 콜론만 있고 모델이 빈 값이면 런타임을 만들지 않는다(빈 `-m` 인자가 생기지 않게).
    assert split("claude:") == (None, "claude:")


def test_bridge_mode_skips_server_model_gates_and_kv_writes():
    """브리지 모드에서 **서버 모델 게이트가 질문을 막지 않는다** (codex 리뷰 P1, 2026-08-28).

    화면에서 모델을 고를 수 없게 되면 `/api/ask` 의 `model` 은 항상 `API_DEFAULT_MODEL`(haiku)로
    채워진다. 그 상태로 모델 RBAC 를 태우면 **haiku 권한만 없는 계정은 개인 AI 처리와 무관하게
    질문 자체가 403** 이 된다 — 서버가 그 모델을 쓰지도 않는데 막는 것이다(바로 위 토큰 쿼터
    게이트를 조건부화한 것과 같은 형태의 모순).

    KV 저장은 **P0-Z3 에서 되살렸다**(아래 별도 테스트) — 화면이 선택기를 보여주고 사용자가
    실제로 고르므로 "고른 적 없는 값" 이 아니게 됐다. 되살아남은 저장이 아니라 복원 쪽에서
    막는다. 반면 이 두 게이트를 건너뛰는 이유는 그대로다 — 서버가 그 모델을 쓰지 않는다.
    """
    src = "\n".join(ln for ln in CONVS.read_text(encoding="utf-8").split("\n")
                    if not ln.strip().startswith("#"))
    assert "elif _server_llm_enabled() and not app._is_allowed_api_model(model):" in src, (
        "카탈로그 allowlist(400) 가 브리지 모드에서도 적용된다")
    assert "elif _server_llm_enabled() and not app._account_has_model_access(" in src, (
        "모델 RBAC(403) 가 브리지 모드에서도 적용된다 — haiku 권한 없는 계정이 질문을 못 한다")


def test_bridge_mode_persists_picks_but_refuses_to_restore_stale_ones():
    """브리지 모드에서 선택을 **저장하고**, 복원은 **지금 유효한 것만** 한다 (P0-Z3).

    두 축이 함께 있어야 한다. 저장만 있으면 러너를 바꾼 뒤 없는 모델이 선택된 채로 보이고
    (P0-T 가 지적한 형태), 복원 검증만 있으면 애초에 저장되는 것이 없어 매번 다시 골라야 한다.
    """
    src = "\n".join(ln for ln in CONVS.read_text(encoding="utf-8").split("\n")
                    if not ln.strip().startswith("#"))
    # 저장: 게이트 조건이 빠졌다(브리지에서도 저장한다).
    assert "if conv_id and reasoning_level:" in src, (
        "브리지 모드에서 추론 강도가 저장되지 않는다 — 매 요청 다시 골라야 한다")
    assert "if conv_id and model_explicit and _model_save_key:" in src, (
        "브리지 모드에서 모델이 저장되지 않는다")
    # 복원: 브리지면 **러너 신고 목록**과 대조한다(서버 카탈로그가 아니라).
    hist = _func_source(CONVS, "history") if "def history(" in src else src
    assert "_bridge_model_offered(" in hist, (
        "복원이 러너 신고와 대조하지 않는다 — 러너를 바꿔도 옛 선택이 되살아난다")
    offered = _func_source(CONVS, "_bridge_model_offered")
    assert "account_runner_capabilities" in offered, "신고 목록을 읽지 않는다"
    assert "return False" in offered, "조회 실패가 복원 허용으로 기울면 없는 모델이 되살아난다"


def test_claim_delivers_the_pick_from_request_time():
    """점유 응답이 고른 값 셋을 **요청 시점 그대로** 전달한다 (P0-Z3 — P0-T 의 미전달을 되돌린다).

    P0-T 가 끊었던 이유는 화면 값이 서버 alias 라 러너가 알아듣지 못해서였다. 이제 목록이
    러너의 자기 신고이므로 여기서 돌려주는 값은 그 CLI 의 어휘다.

    '요청 시점' 이 계약이다 — 지금의 대화 설정이 아니라 그 질문이 적재될 때 굳은 값을 읽는다.
    """
    src = "\n".join(ln for ln in _func_source(AI_TOOLS, "claim_request").split("\n")
                    if not ln.strip().startswith("#"))
    assert '"requested"' in src, "점유 응답이 고른 값을 싣지 않는다 — 러너가 알 방법이 없다"
    for col in ("RequestedRuntime", "RequestedModel", "ReasoningLevel"):
        assert col in src, f"{col} 을 읽지 않는다"
    # 값의 출처가 `WebAiTasks`(요청 시점 각인)여야 한다 — 대화 KV(현재 설정)를 읽으면
    # 질문한 뒤 설정을 바꾼 사용자에게 다른 값이 적용된다.
    assert "FROM WebAiTasks WHERE TaskId=%s AND AccountId=%s" in src


def test_runner_only_accepts_models_it_itself_offered():
    """러너가 **자기 표에 있는 값만** 인자로 만든다 (P0-Z3).

    서버가 돌려주는 값은 사용자가 골랐다고는 하나 네트워크 너머에서 온 문자열이다. 그것이
    그대로 `Popen` 인자가 되면 옵션처럼 보이는 값(`--dangerously-skip-permissions`)이 실행
    플래그가 될 수 있다. 표 대조가 그 경로를 닫는 지점이고, 이 테스트가 그 대조를 잠근다.

    P0-T 시절의 "러너는 모델 인자를 만들지 않는다" 는 이 대조로 대체됐다 — 만들되, 자기가
    신고한 것 중에서만 만든다.
    """
    runner = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
    src = runner.read_text(encoding="utf-8")
    code = _code_lines(runner, "#")
    assert "_RUNTIME_SPECS" in code, "런타임 명세 표가 없다"
    build = _func_source(runner, "build_cmd")
    assert "_valid(" in build, "표 대조 없이 값을 인자로 만든다"
    # 대조 대상이 **실제 신고 목록**이어야 한다. 정적 표(`_RUNTIME_SPECS`)만 보면 `--ai` 로
    # 좁힌 사용자의 제한을 서버 응답이 넘어선다 (codex REV-20260828T170000 P1-5).
    assert "offered_options(runtimes, runtime)" in build, (
        "대조가 신고 목록이 아니라 정적 표를 본다")
    # 런타임 전환도 신고를 거친다 — 표 + PATH 만으로는 `--ai` 제한을 넘어선다.
    handle = _func_source(runner, "handle_one")
    assert 'rt.get("runtime")' in handle and "runtimes or []" in handle, (
        "런타임 전환이 신고를 보지 않는다 — 표에 있고 PATH 에 있으면 전환된다")
    # P0-Z4: 표 밖 CLI 도 지원하므로 조건이 "표에 있는가" 에서 "아는 호출법이 있는가" 로
    # 넓어졌다. 넓어진 만큼 **신고 대조와 PATH 실재**가 그대로 남아야 한다.
    # `_which` → `_which_ai` (2026-09-01): 실재 확인의 범위가 PATH 밖 표준 설치 위치까지
    # 넓어졌다. 「검증 없이 실행하지 않는다」는 계약은 그대로다.
    assert "_known or _learned" in handle and "_which_ai(want_runtime)" in handle, (
        "서버가 준 런타임 이름을 검증 없이 실행한다")
    # ollama 는 `build_cmd` 를 타지 않는다 — 그 경로에도 대조가 있어야 한다.
    ask = _func_source(runner, "ask_local_ai")
    # 2026-09-01: ollama HTTP 경로가 제거돼 `build_cmd` 를 우회하는 분기가 **없다** —
    # 그래서 대조를 따로 심을 자리도 없어졌다(경로가 하나면 게이트도 하나). 되살아나면
    # `build_cmd` 밖에서 모델명을 쓰게 되므로 그 사실을 잡는다.
    assert '"ollama"' not in ask, (
        "제거한 ollama 분기가 되살아났다 — build_cmd 를 우회하면 대조가 사라진다")
    # 반영 못 한 지정은 조용히 버리지 않는다(사용자가 오해하지 않게).
    assert "unmet" in handle, "미반영 지정을 사용자에게 알리지 않는다"
    # 사용자가 명령을 통째로 고정하는 길은 그대로 남는다(기능을 없애지 않았다).
    assert "--cmd 'claude --model opus -p {prompt}'" in src


def test_runner_build_cmd_drops_unoffered_values():
    """`build_cmd` 실행 동작 — 표 밖 값은 **버려지고**, 표 안 값만 인자가 된다 (P0-Z3).

    소스 검사만 두면 `_valid` 가 항상 True 를 돌려주도록 바뀌어도 통과한다. 여기서는 함수를
    실제로 돌려 결과 argv 를 본다.
    """
    import importlib.util

    runner = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
    spec = importlib.util.spec_from_file_location("_runner_probe", runner)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 신고 목록에 있는 값 → 실제 인자가 된다.
    # base argv 는 표에서 유도한다 — 호출 형태(`--strict-mcp-config` 등)가 바뀌어도 이 테스트가
    # 지키려는 것("표 안 값만 인자가 된다")은 그대로여야 한다.
    _claude_base = [a for a in mod._RUNTIME_SPECS["claude"]["argv"] if a != "{prompt}"]
    assert mod.build_cmd("claude", "Q", "sonnet", "low") == \
        _claude_base + ["--model", "sonnet", "--effort", "low", "Q"]
    # codex 는 effort 플래그가 config override 형태다(런타임마다 다르다).
    # 모델 값은 표에서 유도한다 — 표가 실측으로 갱신돼도(2026-08-31 gpt-5.1-* → gpt-5.6-*)
    # 이 테스트가 지키려는 것("표 안 값이 그 런타임의 인자 형태로 조립된다")은 그대로다.
    _codex_model = mod._RUNTIME_SPECS["codex"]["models"][0]["value"]
    assert mod.build_cmd("codex", "Q", _codex_model, "high") == [
        "codex", "exec", "--skip-git-repo-check",
        "-m", _codex_model, "-c", "model_reasoning_effort=high", "Q"]
    # gemini 는 추론등급 플래그가 없다 — 등급을 줘도 인자가 생기지 않는다.
    assert mod.build_cmd("gemini", "Q", "gemini-2.5-pro", "high") == [
        "gemini", "-p", "-m", "gemini-2.5-pro", "Q"]
    # 표 밖 값(옵션 위장·주입 시도)은 **조용히 버려진다** — 프롬프트만 남는다.
    assert mod.build_cmd("claude", "Q", "--dangerously-skip-permissions", "$(rm -rf /)") == \
        _claude_base + ["Q"]
    assert mod.build_cmd("claude", "Q", "claude-haiku-4", None) == _claude_base + ["Q"], (
        "서버 alias 가 인자로 새어 나간다 — P0-T 가 겪은 바로 그 실패 경로")
    # 프롬프트는 항상 마지막 위치 인자이고, 플래그는 그 앞에 온다(뒤에 붙으면 프롬프트에 먹힌다).
    assert mod.build_cmd("claude", "Q", "opus", None)[-1] == "Q"


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
    """LLM 사고 과정을 **관측한 것처럼 표시하지 않는다** — 그러면 패널 전체가 못 믿을 것이 된다.

    ⚠ 계약이 한 번 바뀌었다(2026-08-27, 사용자 제보 "실행 단계에 「어떤 이유로 어떤 작업」
    구조가 없다"). 처음엔 사유 칸을 통째로 비웠는데, 그 결과 화면에는 `SQL을 실행한다` 만
    남아 **왜 그 단계가 있었는지 읽을 수 없었다**.

    지금은 사유를 채우되 **출처를 구분한다**:
      - `external-ai` — 개인 AI 가 도구 호출에 실어 보낸 진짜 사유
      - `derived`     — 도구의 목적에서 서버가 파생한 문구(내부 LLM 경로가 쓰던 것과 같은 헬퍼)
    즉 금지되는 것은 "사유를 쓰는 것" 이 아니라 **파생 문구를 AI 의 사고인 양 각인하는 것**이다.
    """
    body = _func_source(AI_TOOLS, "_materialize_bridge_steps")
    assert "'derived'" in body, "이관 경로가 사유 출처를 표시하지 않는다"
    assert "'llm'" not in body and "'external-ai'" not in body, (
        "원장 이관에는 AI 의 사고가 없다 — 그 출처로 각인하면 관측하지 않은 것을 관측했다고 말한다")

    # 호출 시점 기록도 같은 규칙: AI 가 실제로 보냈을 때만 external-ai.
    live = _func_source(AI_TOOLS, "_record_bridge_step")
    assert '"external-ai" if reason else "derived"' in live, (
        "사유 출처가 실제 제공 여부와 무관하게 각인된다")


def test_steps_exclude_bridge_plumbing():
    """대기·점유·제출은 조사 내역이 아니다 — 사용자에게는 소음이다.

    2026-08-28: 필터가 `_BRIDGE_PROGRESS_TOOLS` 상수로 올라갔다. 진행 중 표시
    (`_bridge_live_steps`)와 제출 시 이관이 **같은 집합**을 써야 하기 때문이다 —
    갈리면 제출 순간 단계 목록이 달라져 사용자가 "단계가 사라졌다" 고 본다.
    """
    src = AI_TOOLS.read_text(encoding="utf-8")
    idx = src.index("_BRIDGE_PROGRESS_TOOLS = frozenset({")
    decl = src[idx:src.index("})", idx)]
    for noise in ("wait_for_request", "claim_request", "submit_answer", "list_open_requests"):
        assert noise in decl, f"{noise} 를 걸러내지 않는다"
    body = _func_source(AI_TOOLS, "_materialize_bridge_steps")
    assert "_BRIDGE_PROGRESS_TOOLS" in body, "제출 경로가 공용 필터를 쓰지 않는다"


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
    """국면을 **서버가 한 단어로** 정한다 — 프런트가 조합하면 화면마다 갈린다.

    2026-08-28: 판정이 `_bridge_phase` 로 올라갔다. 소비처가 폴링(`bridge_status`)과
    스트리밍(`_bridge_stream_snapshot`) 둘이 되었기 때문이다 — 각자 조합하면 전송 방식에
    따라 화면이 달라져 폴백이 곧 UX 회귀가 된다.
    """
    decide = _func_source(AI_TOOLS, "_bridge_phase")
    for ph in ("not_connected", "waiting", "working", "done", "canceled"):
        assert ph in decide, f"국면 {ph} 가 없다"
    for consumer in ("bridge_status", "_bridge_stream_snapshot"):
        src = _func_source(AI_TOOLS, consumer)
        assert "_bridge_phase(" in src, f"{consumer} 이 국면을 자체 조합한다"
        assert "connected" in src, "연결 여부를 알리지 않으면 영원히 오지 않을 답을 기다린다"


def test_status_connection_probe_fails_open():
    src = _func_source(AI_TOOLS, "bridge_status")
    tail = src[src.index("except Exception"):]
    assert "connected = True" in tail, "판정 실패 시 '연결 없음' 으로 단정하면 거짓 경보가 된다"


def test_frontend_reacts_to_phase_change_only():
    """전환된 순간에만 다시 읽는다 — 매 tick 갱신은 스크롤을 흔들고 요청을 배로 만든다.

    2026-08-28: 반응이 `_applyBridgePhase` 로 올라갔다(폴링·스트리밍 공용). 두 전송 경로가
    각자 반응하면 폴백 시 사용자가 다른 화면을 본다.
    """
    js = COMPOSER_JS.read_text(encoding="utf-8")
    # 전환 감지: 폴링은 `_lastPhase`, 스트리밍은 `lastPhase` 로 직전 국면을 들고 비교한다.
    assert 'status.phase !== _lastPhase' in js, "폴링이 매 tick 반응한다"
    assert "phase === prev" in js, "스트리밍이 매 프레임 반응한다"
    react = js[js.index("function _applyBridgePhase"):]
    react = react[:react.index("\n}")]
    assert 'phase === "working"' in react, "처리 중 전환을 화면에 반영하지 않는다"
    assert 'phase === "not_connected"' in react, "연결 없음을 사용자에게 알리지 않는다"
    assert 'phase === "canceled"' in react, "취소 전환을 화면에 반영하지 않는다"


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
    role = _bridge_enqueue_kwarg("role_id")
    assert isinstance(role, ast.Name) and role.id == "role_id_for_run", (
        f"역할을 넘기지 않는다(넘기는 값: {ast.dump(role)})")


def test_runner_puts_system_prompt_first():
    """운영자 지침이 기본 지시를 **이긴다**.

    계약은 그대로이나 **이기는 방법이 둘**이 됐다 (TASK-20260901T140000):

      (a) 시스템 채널 — `--append-system-prompt`. 본문 밖이라 애초에 경쟁하지 않는다.
      (b) 폴백(미지원 런타임·`--cmd`) — 종전대로 본문 **맨 앞**.

    옛 검사는 (b)의 머리말 문자열 하나만 봤다. 그 문구(「시스템 프롬프트로 삼아 답하라」)는
    본문 속 역할 재지정이라 인젝션 서명과 동형이어서 제거됐고, 문구를 그대로 요구하면 이
    검사가 **결함을 되돌리라고 요구하는** 게이트가 된다. 그래서 문구가 아니라 **순서**를 본다.
    """
    src = (_UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py").read_text(
        encoding="utf-8")
    body = src[src.index("def compose_prompt("):src.index("# ── 한 건 처리")]
    # ⚠ **주석을 제외하고** 본다 (TASK-20260831T100000). 이 검사는 본문 문자열의 **위치**를
    #   비교하는데, 같은 문구가 설명 주석에도 나타나면 순서 판정이 그대로 뒤집힌다 — 실제로
    #   콘솔 작업 분기를 설명하는 주석이 추가되자 거짓 실패가 났다. 계약("지침이 맨 앞")은
    #   그대로 두고, 판정 대상만 코드로 좁힌다.
    body = "\n".join(_l for _l in body.split("\n") if not _l.lstrip().startswith("#"))
    assert "system_prompt" in body
    # (b) 폴백 순서 — 운영자 지침 블록이 기본 지시보다 **먼저** 조립된다.
    assert body.index("관리 콘솔 설정값") < body.index("이 요청은 사내 DB 질의다"), (
        "운영자 지침이 기본 지시보다 뒤에 온다")
    # (a) 시스템 채널 — 지원 런타임에서는 본문에 싣지 않고 플래그로 넘긴다.
    assert "system_channel" in body, "시스템 채널 분기가 사라졌다(폴백만 남으면 오탐이 돌아온다)"
    assert '"system": [_APPEND_SYSTEM_FLAG' in src, "claude 명세에 시스템 채널이 없다"


def test_prompt_failure_cannot_silently_drop_configured_layers():
    body = _func_source(AI_TOOLS, "_bridge_system_prompt")
    assert "strict=True" in body and "raise RuntimeError" in body
    claim = _func_source(AI_TOOLS, "claim_request")
    assert '_json_err(503,' in claim and '_release_claim(conn, task_id, account_id)' in claim


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
