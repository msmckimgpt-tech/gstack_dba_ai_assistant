"""feature-0043 — 인터럽트 · 맥락 전환 · 진행 스트리밍 · 병렬의 **계약 회귀** (2026-08-28).

## 이 스위트가 잠그는 것

전환 이후 브리지 경로에는 기존 경로가 가지고 있던 런타임 조작면 3종이 통째로 빠져 있었다.
빠진 방식이 특징적이다 — **계산이 아니라 연결이 끊긴 형태**라 헬퍼 단위 테스트로는 전부
통과했다(P0-E 가 겪은 것과 같은 부류):

- `/api/cancel` 은 멀쩡히 동작했다. 다만 `WebAiTasks` 를 **보지 않았다**.
- 중단 버튼 로직도 멀쩡했다. 다만 브리지에서는 그 판정원(`myAskInFlight`)이 **즉시 비었다**.
- 단계 이관 함수도 멀쩡했다. 다만 **제출 시점에만** 불렸다.

그래서 여기서 단언하는 것은 "함수가 올바른가" 가 아니라 **"그 함수가 그 자리에 배선돼
있는가"** 다. 라우터를 import 하지 않고 소스를 AST/텍스트로 보는 이유는 기존 스위트와 같다
(feature-0002·0003 이 둘 다 최상위 `modules` 를 가져 한 프로세스에서 동시 import 불가).

## 함께 보는 것: 술어 단일화

취소는 도구 표면(ai_tools)과 웹 표면(conversations) **둘 다** 판정한다. 두 벌이 되는 순간
"목록엔 없는데 취소는 안 되는" 어긋남이 생기고, 갈리는 쪽 중 **느슨한 쪽이 사용자가 보는
진실**이 된다(P0-R 에서 이미 한 번 겪었다). 그 이중화 재발을 구조로 막는다.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_REPO = _UNIT.parent

WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
TOOLS_PY = WEB_SRC / "routers" / "ai_tools.py"
CONV_PY = WEB_SRC / "routers" / "conversations.py"
COMPOSER_JS = WEB_SRC / "static" / "app" / "composer.js"
APP_JS = WEB_SRC / "static" / "app.js"
SHARED_BRIDGE = _REPO / "shared" / "bridge_tasks.py"
RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


def _src(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _pyfunc(path: pathlib.Path, name: str) -> str:
    text = _src(path)
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{name} 을 {path.name} 에서 찾지 못했다")


def _jsfunc(text: str, name: str) -> str:
    """JS 함수 본문 — 인자 목록을 건너뛴 뒤 중괄호 균형으로 자른다."""
    start = text.index(name)
    paren = text.index("(", start)
    depth, i = 0, paren
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    brace = text.index("{", i)
    depth, i = 0, brace
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise AssertionError(f"{name} 의 끝을 찾지 못했다")


# ── ① 취소가 한 곳에서만 판정된다 ────────────────────────────────────────────


def test_cancel_has_a_single_source_of_truth():
    """취소 술어가 `shared/bridge_tasks.py` 에만 있고, 소비처는 부르기만 한다."""
    shared = _src(SHARED_BRIDGE)
    assert "def cancel_bridge_tasks(" in shared, "취소 정본이 없다"

    conv = _src(CONV_PY)
    # 웹 축은 자기 DELETE/UPDATE 를 조립하지 않는다 — **적재 롤백 한 곳만** 예외다.
    entry = _pyfunc(CONV_PY, "_cancel_bridge_tasks_for")
    assert "cancel_bridge_tasks(" in entry, "웹 진입점이 정본을 부르지 않는다"
    assert "DELETE FROM WebAiTasks" not in entry and "UPDATE WebAiTasks" not in entry, (
        "웹 진입점이 SQL 을 자체 조립한다(술어 이중화)")
    # 롤백 전용 경로는 남아 있어도 되지만, 그 하나뿐이어야 한다.
    assert conv.count("DELETE FROM WebAiTasks") <= 1, (
        "웹 라우터에 취소 SQL 이 여러 벌이다 — 어디서 취소했느냐로 결과가 갈린다")


def test_cancel_splits_unclaimed_and_claimed():
    """미점유는 삭제, 점유는 `canceled` 표시 — 두 갈래가 실제로 구현돼 있다.

    점유된 것을 지우면 개인 AI 의 제출이 404 가 되어 *왜* 실패했는지 알 수 없다.
    `canceled` 로 남겨야 409 + 사유를 돌려주고, 러너를 제출 전에 하차시킬 수 있다.
    """
    fn = _pyfunc(SHARED_BRIDGE, "cancel_bridge_tasks")
    assert "DELETE FROM WebAiTasks" in fn, "미점유 삭제 갈래가 없다"
    assert "STATUS_CANCELED" in fn and "UPDATE WebAiTasks" in fn, "점유 취소표시 갈래가 없다"
    assert "claim_is_live(" in fn, "lease 판정 없이 갈래를 나눈다"
    assert '"deleted"' in fn and '"canceled"' in fn, "무엇을 했는지 돌려주지 않는다"


def test_cancel_scope_is_bounded():
    """계정 스코프가 **경계**다 — 빼면 남의 대기 질문을 취소할 수 있다."""
    fn = _pyfunc(SHARED_BRIDGE, "cancel_bridge_tasks")
    assert "AccountId = %s" in fn, "계정 스코프가 없다 — 남의 task 를 취소할 수 있다"
    assert "not conversation_id and not task_id" in fn, (
        "대상 미지정 시 그 계정의 전 대기열을 지운다")


def test_api_cancel_reaches_the_bridge_axis():
    """`/api/cancel` 이 브리지 대기도 취소한다.

    이것이 없으면 중단을 눌러도 개인 AI 는 계속 답을 만들고 그 답이 대화에 붙는다 —
    전환 이후 인터럽트가 브리지에서만 무력했던 바로 그 결함이다.
    """
    fn = _pyfunc(CONV_PY, "cancel_request")
    assert "_cancel_bridge_tasks_for(" in fn, "브리지 축을 취소하지 않는다"
    assert "_mark_bridge_placeholders_canceled(" in fn, "대기 말풍선을 갱신하지 않는다"
    # 서버 run 취소보다 **먼저** 해야 한다 — 그쪽은 예외를 500 으로 바꿔 반환하므로
    # 뒤에 두면 KV 조회 한 번 실패가 브리지 취소까지 통째로 건너뛴다.
    assert fn.index("_cancel_bridge_tasks_for(") < fn.index("mark_cancel_requested("), (
        "브리지 취소가 서버 run 취소 뒤에 있다 — 그쪽 실패가 이쪽을 삼킨다")
    assert "bridge_cancel_failed" in fn, "취소 실패를 응답으로 알리지 않는다"


def test_cancel_failure_is_not_swallowed():
    """취소 실패를 숨기면 화면은 '취소했습니다' 인데 잠시 뒤 답변이 나타난다."""
    front = _jsfunc(_src(APP_JS), "async function cancelCurrentRun")
    assert "bridge_cancel_failed" in front, "프런트가 취소 실패를 무시한다"
    assert "abandonBridgeTasks(" in front, "취소된 task 의 감시를 끊지 않는다(404 누적)"


# ── ② 맥락 전환(supersede) ───────────────────────────────────────────────────


def test_new_question_supersedes_previous_pending():
    """새 질문이 같은 대화의 이전 대기 질문을 대체한다.

    그냥 두면 `CreatedAt ASC` 로 **옛 질문이 먼저** 처리되고, 늦게 집힌 옛 질문이 그 뒤
    turn 까지 포함한 최신 문맥으로 답해져 대화 흐름과 어긋난다.
    """
    fn = _pyfunc(CONV_PY, "_enqueue_web_bridge_task")
    assert "_cancel_bridge_tasks_for(" in fn, "이전 대기 질문을 대체하지 않는다"
    assert "exclude_task_id=task_id" in fn, (
        "자기 자신을 제외하지 않는다 — 새 질문이 태어나자마자 스스로를 지운다")
    # 적재 **성공 뒤에** 대체한다. 먼저 취소하고 INSERT 가 실패하면 옛 질문도 새 질문도 없다.
    assert fn.index("INSERT INTO WebAiTasks") < fn.index("_cancel_bridge_tasks_for("), (
        "적재 전에 대체한다 — 적재 실패 시 이전 질문까지 잃는다")
    assert "bridge_superseded" in fn, "대체 결과를 프런트에 알리지 않는다"


def test_superseded_tasks_are_abandoned_by_the_frontend():
    """프런트가 대체된 task 의 감시를 **새 폴러를 걸기 전에** 끊는다."""
    fn = _jsfunc(_src(COMPOSER_JS), "export function handleBridgePending")
    assert "bridge_superseded" in fn and "abandonBridgeTasks(" in fn
    assert fn.index("abandonBridgeTasks(") < fn.index("_pollBridgeAnswer("), (
        "새 감시를 먼저 걸고 옛 것을 끊는다 — 옛 폴러가 404 를 받아 새 안내까지 지운다")


def test_supersede_notice_is_distinct_from_cancel():
    """대체와 취소는 **다른 문구**다 — 사용자는 중단 버튼을 누른 적이 없다."""
    conv = _src(CONV_PY)
    assert "_BRIDGE_NOTICE_SUPERSEDED" in conv and "_BRIDGE_NOTICE_CANCELED" in conv
    assert "새 질문" in conv, "대체를 '취소' 로만 말한다"


def test_cancel_notice_admits_what_we_cannot_stop():
    """"중단했습니다" 로 끝내지 않는다 — 이미 가져간 작업은 못 멈춘다.

    숨기면 개인 계정 토큰이 조용히 타는 동안 사용자는 아무 일도 없다고 믿는다.
    """
    conv = _src(CONV_PY)
    idx = conv.index("_BRIDGE_NOTICE_CANCELED = (")
    body = conv[idx:idx + 500]
    assert "반영되지" in body, "취소의 한계(이미 진행 중인 작업)를 말하지 않는다"


# ── ③ 협조적 취소 채널 ───────────────────────────────────────────────────────


def test_wait_returns_early_on_cancel():
    """`wait_for_request` 가 **취소에도 즉시 반환**한다(새 질문과 같은 채널).

    별도 도구를 만들면 러너가 채널을 하나 더 돌봐야 하고 그 주기가 사람마다 달라
    **환경 차이**가 된다 — P0-J 가 폴링을 버린 이유와 같다.
    """
    fn = _pyfunc(TOOLS_PY, "wait_for_request")
    assert "canceled_task_ids" in fn, "취소를 응답에 싣지 않는다"
    assert "if found or canceled or" in fn, "취소로는 대기가 풀리지 않는다"
    assert "ClaimedBy=%s" in fn, (
        "점유자 스코프가 없다 — 남이 집은 작업의 취소로 내 워커가 하차한다")


def test_cancel_channel_adds_no_new_tool():
    """도구 **개수가 늘지 않는다** — 늘면 매니페스트·가이드·capabilities 가 동시에 어긋난다.

    협조적 취소는 신규 도구가 아니라 기존 `wait_for_request` 응답의 필드로 전달된다.
    도구를 하나 더하면 P0-I 계약 4곳(매니페스트·가이드 열거·가이드 수·capabilities)이
    동시에 어긋날 입구가 열린다 — 라이브에서 이미 그 부류로 브리지 축이 통째로 끊긴 적이 있다.

    여기서 세는 것은 **명시 라우트**다(구조 조회 6종은 `{tool_name}` catch-all 이 dispatch
    하므로 이 수에 들어오지 않는다). 총 노출 수 대조는 `test_ux_parity` 의 가이드 수 테스트가 맡는다.
    """
    # 2026-09-09: 7 → 8. `get_tool_catalog`(구조 조회 도구의 현재 목록·인자를 알려 주는
    # 카탈로그) 가 더해졌고, 이 테스트가 요구하는 **4곳 정합이 실제로 되어 있음을 확인**한 뒤
    # 숫자를 옮겼다 — 매니페스트/OpenAPI(`routers/ai_discovery.py`)와 MCP 어댑터 2벌
    # (`external_tool_mcp_http.py` · `external_tool_mcp_server.py`)에 모두 등재돼 있고,
    # 총 노출 수를 보는 `test_ux_parity` 도 초록이다. 숫자만 stale 이었다(그 cycle 이 여기를
    # 함께 갱신하지 않아 base 가 붉은 채였다). 계약은 그대로다 — **개수가 또 늘면 여전히 잡는다.**
    tools = _src(TOOLS_PY)
    routes = [ln for ln in tools.split("\n") if '@router.post("/api/ai/tools/' in ln]
    named = [r for r in routes if "{tool_name}" not in r]
    assert len(named) == 8, (
        f"명시 도구 라우트 수가 바뀌었다({len(named)}종) — 가이드 열거·수 대조·매니페스트도 "
        "같은 cycle 에서 갱신해야 한다")
    assert any("{tool_name}" in r for r in routes), "구조 조회 dispatch 라우트가 사라졌다"


def test_submit_rejects_canceled_task():
    """취소된 요청의 답변은 **저장·전달되지 않는다**(409).

    러너는 `canceled_task_ids` 로 먼저 하차하지만 그 신호를 안 읽는 등록형 AI 도 있다.
    인지(러너)와 집행(서버)은 층이 다르며, 두 겹이지 이중 정의가 아니다.
    """
    fn = _pyfunc(TOOLS_PY, "submit_answer")
    assert "_STATUS_CANCELED" in fn, "취소 상태를 보지 않는다"
    assert fn.index("_STATUS_CANCELED") < fn.index("_guard.classify_injection("), (
        "취소 판정이 저장 준비 뒤에 있다 — 취소된 답변을 각인·보존하게 된다")
    assert "409" in fn


def test_submit_cancel_check_is_atomic_not_read_then_act():
    """취소 집행이 **확정 UPDATE 안**에 있다 — 조기 반환만으로는 못 막는다.

    ## 이 테스트가 잡는 실제 결함 (자체 리뷰 2026-08-28)

    초판은 `_load_task` 로 읽은 상태를 보고 조기 반환하는 것이 전부였다. 그 값은 **과거**다 —
    그 뒤로 인젝션 판정·형제 조회(여러 DB 왕복)가 이어지고, 그 사이 사용자가 중단하거나 새
    질문으로 갈아타면 검사를 그냥 지나친다.

    지나치면 어떻게 되나: 확정 UPDATE 에 Status 조건이 없으므로 `canceled` → `submitted` 로
    덮이고 `_deliver_web_bridge_answer` 가 대화에 쓴다. 게다가 취소 말풍선은
    `placeholder=false` 라 덮어쓰기 대상에서 빠져 **새 말풍선으로 append** 된다 —
    "취소했습니다" 아래에 답변이 나타난다. 사용자 결정(409 거절 + 대화 미전달)의 정반대다.

    같은 파일의 `SubmittedAt IS NULL` 가드가 정확히 같은 이유로 SQL 안에 있고, 그 주석이
    "조건을 SQL 에 둬야 TOCTOU 없이 원자적이다" 라고 적어 두었다 — 초판은 그 교훈을 옆에
    두고도 되풀이했다.
    """
    fn = _pyfunc(TOOLS_PY, "submit_answer")
    upd = fn[fn.index("UPDATE WebAiTasks SET Status = 'submitted'"):]
    upd = upd[:upd.index("affected = cur.rowcount")]
    assert "Status <> %s" in upd, (
        "확정 UPDATE 가 취소 상태를 보지 않는다 — 판정과 쓰기 사이에 취소되면 그대로 통과한다")
    assert "_STATUS_CANCELED" in upd, "취소 상태값이 UPDATE 파라미터로 넘어가지 않는다"
    # rowcount 0 의 사유를 구분해야 러너가 다음 행동을 정한다(취소=버리기 / 미점유=claim).
    tail = fn[fn.index("if not affected:"):]
    assert "task_canceled_race" in tail, "경합으로 막힌 경우를 '미점유' 로 오인해 안내한다"


def test_cancel_write_reconfirms_the_condition_in_sql():
    """취소의 DELETE/UPDATE 도 **쓰기 문장에서** 조건을 다시 확인한다.

    `cancel_bridge_tasks` 는 SELECT 로 분류한 뒤 쓴다. 그 사이 개인 AI 가 집거나(claim) 답을
    제출할 수 있다:

    - DELETE 가 조건 없이 id 로만 지우면 → 방금 점유된 작업이 사라져 러너의 제출이 404 가 된다
      (왜 실패했는지 모르는 에러).
    - UPDATE 가 조건 없이 쓰면 → 방금 제출된 작업의 `submitted` 를 `canceled` 로 덮어,
      **이미 화면에 실린 답변이 "취소됨" 으로 뒤집힌다.**
    """
    fn = _pyfunc(SHARED_BRIDGE, "cancel_bridge_tasks")
    dele = fn[fn.index("DELETE FROM WebAiTasks"):]
    dele = dele[:dele.index("if int(cur.rowcount or 0):")]
    assert "CLAIMABLE_SQL" in dele, "DELETE 가 점유 여부를 재확인하지 않는다"
    # 상태 재확인은 `Status IN (...)` 로 바뀌었다 — 취소 대상이 open 하나가 아니라
    # open·deferred 둘이기 때문(2026-08-28 보류 질문 도입). 재확인한다는 계약은 그대로다.
    assert "Status IN (" in dele, "DELETE 가 상태를 재확인하지 않는다"
    upd = fn[fn.index("UPDATE WebAiTasks SET Status = %s"):]
    assert "Status = %s" in upd, "UPDATE 가 상태를 재확인하지 않는다(제출본을 덮어쓴다)"


def test_cancel_reports_only_what_it_actually_changed():
    """**DML 이 바꾼 것만** 돌려준다 (codex P1-1).

    SELECT 로 분류한 뒤 쓰기 사이에 러너가 claim 하거나 답을 제출하면 재확인 조건에 걸려
    DELETE/UPDATE 가 0행이 된다. 그런데 미리 계산한 목록을 그대로 돌려주면, 호출측은 그 id 로
    말풍선을 "취소됨" 으로 바꾸고 task 는 멀쩡히 살아 있어 **취소 안내 아래에 답변이 붙는다.**
    재확인 조건을 넣은 바로 그 수정이 만든 회귀다 — 조건은 맞았고 **반환값이 따라오지 않았다.**

    그리고 지우지 못한 것은 **놓아주지 않고 취소로 승격**해야 한다. 거기서 포기하면 사용자는
    중단을 눌렀는데 답변이 그대로 온다.
    """
    fn = _pyfunc(SHARED_BRIDGE, "cancel_bridge_tasks")
    assert "confirmed_deleted" in fn and "confirmed_canceled" in fn, (
        "확인된 결과를 따로 모으지 않는다 — 미확인 id 를 성공으로 보고한다")
    assert "cur.rowcount" in fn, "DML 결과를 확인하지 않는다"
    assert "to_delete, to_cancel = confirmed_deleted, confirmed_canceled" in fn, (
        "반환값이 확인된 목록으로 교체되지 않는다")
    # 일괄 IN(...) 쓰기는 "몇 건" 만 주고 "어느 것" 을 안 준다 — 건별로 써야 한다.
    assert "TaskId = %s" in fn, "건별 확인이 아니라 일괄 쓰기다(어느 것이 바뀌었는지 모른다)"


def test_cancel_sql_uses_parameters_for_values():
    """상태값을 문자열 보간이 아니라 **파라미터**로 넘긴다.

    지금은 모듈 상수라 주입 위험이 없지만, f-string 으로 값을 SQL 에 박는 습관이 남아 있으면
    다음 사람이 변수를 같은 자리에 넣는다. 값은 파라미터로 간다.
    """
    fn = _pyfunc(SHARED_BRIDGE, "cancel_bridge_tasks")
    assert "{STATUS_CANCELED}" not in fn, "상태값을 f-string 으로 SQL 에 박는다"
    assert "{STATUS_OPEN}" not in fn, "상태값을 f-string 으로 SQL 에 박는다"


# ── ④ 진행 스트리밍 ──────────────────────────────────────────────────────────


def test_stream_is_counted_for_zero_downtime_deploy():
    """SSE 가 `_counted_stream` 을 통과한다.

    그것이 feature-0014 무중단 배포의 pre-drain 게이트(`/livez` 의 `active_streams`)가 세는
    카운터다. 빼먹으면 배포가 이 스트림을 **못 보고** 그냥 끊는다.
    """
    fn = _pyfunc(TOOLS_PY, "bridge_stream")
    assert "app._counted_stream(" in fn, "배포 pre-drain 이 이 스트림을 보지 못한다"
    assert 'media_type="text/event-stream"' in fn
    assert '"X-Accel-Buffering": "no"' in fn, "중간 단이 버퍼링하면 스트리밍이 무의미하다"


def test_stream_has_a_server_fixed_bound():
    """상한을 서버가 정하고, 배포 pre-drain(90초)보다 짧다.

    30분짜리 스트림을 열어 두면 배포마다 replica 당 90초를 버리고 **그러고도 끊긴다**
    (fetch/getReader 는 자동 재접속이 없다).
    """
    tools = _src(TOOLS_PY)
    assert "_BRIDGE_STREAM_MAX_HOLD_SEC = 55.0" in tools, "상한이 없거나 값이 바뀌었다"
    fn = _pyfunc(TOOLS_PY, "bridge_stream")
    assert 'app._sse_pack("reconnect"' in fn, "상한 도달을 오류가 아닌 재접속으로 알리지 않는다"
    # 클라이언트가 대기 시간을 정할 수 없다(환경 차이 금지).
    assert "query_params.get(\"wait\")" not in fn


def test_stream_authenticates_before_opening():
    """인증·소유 확인을 **스트림을 열기 전에** 끝낸다.

    제너레이터 안에서 하면 이미 200 + SSE 헤더가 나간 뒤라 401/403 을 돌려줄 수 없다.
    """
    fn = _pyfunc(TOOLS_PY, "bridge_stream")
    assert fn.index("app._require_account(") < fn.index("async def event_stream("), (
        "스트림을 연 뒤 인증한다 — 오류 상태코드를 돌려줄 수 없다")
    assert "AccountId=%s" in fn, "계정 스코프가 없다"


def test_stream_stops_when_client_disconnects():
    """끊긴 클라이언트를 위해 DB 를 계속 두드리지 않는다."""
    fn = _pyfunc(TOOLS_PY, "bridge_stream")
    assert "request.is_disconnected()" in fn


def test_live_steps_carry_only_observed_facts():
    """진행 단계는 **관측한 사실**만 옮긴다 — LLM 사고 과정은 우리 밖이다.

    ⚠ 계약이 한 번 정련됐다(2026-08-28). 종전 판정은 "원장에서 읽고 `reason_text` 가 없을
    것" 이었는데, 그 결과 진행 중 화면이 `list_schemas 3행` 같은 **평문 나열**이 됐다 —
    완료본은 「작업 + 근거」 카드인데 진행 중만 다른 모양이었다(사용자 제보).

    지금은 우리가 **도구 호출 시점에 직접 기록한** 단계(`agent_runtime.steps`)를 그대로
    돌려준다. 거기 실린 `reason` 은 개인 AI 가 보낸 것이거나 서버가 도구 목적에서 파생한
    것이고, **출처(`reason_source`)가 함께 나간다**. 금지선은 "사유를 싣지 않는다" 가 아니라
    **"출처 없이 AI 의 사고인 양 싣지 않는다"** 로 정확해졌다.
    """
    fn = _pyfunc(TOOLS_PY, "_bridge_live_steps")
    assert "FROM agent_runtime.steps" in fn, "우리가 기록한 단계가 아니라 다른 곳에서 만든다"
    assert '"reason_source"' in fn, "사유의 출처가 빠졌다 — 지어낸 것과 구분되지 않는다"
    assert '"work_source"' in fn, "작업 문구의 출처가 빠졌다"


def test_step_filter_is_shared_between_live_and_final():
    """진행 중 표시와 제출 시 이관이 **같은 필터**를 쓴다.

    갈리면 제출 순간 단계 목록이 달라져 사용자가 "단계가 사라졌다" 고 본다.
    """
    final = _pyfunc(TOOLS_PY, "_materialize_bridge_steps")
    assert "_BRIDGE_PROGRESS_TOOLS" in final, "이관 경로가 진행 도구를 걸러내지 않는다"
    assert 'skip = {"wait_for_request"' not in final, "제출 경로가 자체 집합을 갖는다"
    # 진행 표시는 이제 **필터가 필요 없다** — 진행 도구(wait·claim·submit)는 애초에
    # `agent_runtime.steps` 에 기록되지 않으므로, 조회 결과에 섞일 수 없다(구조적 배제).
    live = _pyfunc(TOOLS_PY, "_bridge_live_steps")
    # ⚠ **실행되는 SQL** 만 본다 — docstring 은 왜 원장을 떠났는지 설명하느라 그 이름을
    #   언급한다(주석이 검사를 좌우하면 그 테스트는 코드가 아니라 산문을 지키게 된다).
    live_code = "\n".join(
        ln for ln in live.splitlines()
        if "FROM " in ln or "SELECT " in ln or "cur.execute" in ln)
    assert "tool_call_usage" not in live_code, (
        "진행 표시가 다시 원장을 읽는다 — 그러면 진행 도구 필터가 또 필요해진다")


def test_phase_is_decided_by_the_server_in_one_word():
    """국면은 서버가 한 단어로 정한다 — 프런트가 조합하면 화면마다 갈린다.

    **두 cycle 의 축이 합쳐진 자리다**(2026-08-28 병합): 형제 cycle 이 `listening`(러너가 떠
    있는가)을, 이 cycle 이 `canceled` 를 더했다. 둘 중 하나라도 빠지면 그 cycle 이 고친 마찰이
    되살아나므로 **6종 전부**를 단정한다.
    """
    fn = _pyfunc(TOOLS_PY, "_bridge_phase")
    # `canceled` 가 맨 앞이어야 한다: 취소 뒤에도 ClaimedBy 는 남으므로 순서가 뒤면
    # 같은 행이 계속 `working` 으로 읽혀 "처리 중" 이 영원히 표시된다.
    assert fn.index('"canceled"') < fn.index('"working"'), (
        "취소 판정이 점유 판정 뒤에 있다 — 취소된 작업이 영원히 '처리 중' 으로 보인다")
    for phase in ("canceled", "done", "working", "waiting", "not_listening", "not_connected"):
        assert f'"{phase}"' in fn, f"국면 {phase} 가 사라졌다(병합 중 한쪽 축 유실)"
    # `connected` 와 `listening` 은 다른 사실이다 — 토큰은 DB 에, 러너는 프로세스에 있다.
    assert "listening: bool" in fn, "러너 대기 축이 판정 인자에 없다"
    # 관측 실패는 '있다' 쪽으로 — 없다고 단정하면 멀쩡한 사용자에게 매번 틀린 경고를 띄운다.
    assert "listening: bool = True" in fn, "러너 축의 fail-open 기본값이 없다"


def test_status_and_stream_agree():
    """폴링과 스트리밍이 **같은 판정 함수**를 쓴다 — 폴백이 화면을 바꾸지 않게."""
    for name in ("bridge_status", "_bridge_stream_snapshot"):
        fn = _pyfunc(TOOLS_PY, name)
        assert "_bridge_phase(" in fn, f"{name} 이 국면을 자체 조합한다"
        assert "_bridge_live_steps(" in fn, f"{name} 이 단계를 싣지 않는다"


def test_stream_transient_db_error_does_not_look_like_cancel():
    """일시 DB 장애를 '취소됨' 으로 읽지 않는다.

    `None` 은 "task 가 없다(=미점유 취소로 삭제됐다)" 는 뜻이다. 커넥션 실패에 그것을
    돌려주면 DB 가 잠깐 흔들릴 때마다 사용자 화면이 "취소됨" 으로 확정된다.
    """
    fn = _pyfunc(TOOLS_PY, "_bridge_stream_snapshot")
    connect_fail = fn[fn.index("except Exception:"):fn.index("try:", fn.index("except Exception:"))]
    assert "return None" not in connect_fail, "DB 장애를 취소로 오인한다"


# ── ⑤ 중단 버튼 노출 ─────────────────────────────────────────────────────────


def test_stop_button_appears_while_bridge_pending():
    """브리지 대기 중에도 중단 버튼이 뜬다.

    `_myAskInFlightHere()` 는 `/api/ask` 왕복 수명을 재는데 브리지에서는 그 왕복이 즉시
    끝난다 — 그래서 전환 이후 버튼이 한 번도 뜨지 않았고 인터럽트가 UI 에서 도달 불가였다.
    """
    composer = _src(COMPOSER_JS)
    assert "export function _bridgePendingHere(" in composer, "브리지 대기 판정원이 없다"
    render = _jsfunc(composer, "function renderComposer")
    assert "_bridgePendingHere()" in render, "중단 버튼이 브리지 대기를 보지 않는다"


def test_stop_button_and_click_handler_use_the_same_predicate():
    """버튼 모드와 클릭 동작이 같은 술어를 쓴다.

    갈리면 버튼은 '중단' 인데 눌러도 전송이 나가는(또는 그 반대) 상태가 된다.
    """
    app = _src(APP_JS)
    assert "(_myAskInFlightHere() || _bridgePendingHere()) && !hasText" in app, (
        "클릭 핸들러가 렌더와 다른 술어를 쓴다")


def test_bridge_pending_is_not_mixed_into_ask_inflight():
    """브리지 대기를 in-flight 집합에 **섞지 않는다**.

    그 집합은 전송 경로의 R2/R3 분기도 본다. 섞으면 브리지 대기 중 새 질문이 "이전 요청
    처리 중" 으로 막히거나, 취소 권한이 없는 사용자에게 전송이 거부된다 — 지금은 자유롭게
    보낼 수 있고 대체는 서버가 한다.
    """
    fn = _jsfunc(_src(COMPOSER_JS), "export function _bridgePendingHere")
    assert "myAskInFlight" not in fn, "브리지 대기를 ask in-flight 로 승격한다(전송이 막힌다)"
    send = _jsfunc(_src(COMPOSER_JS), "async function sendPrompt")
    assert "_bridgePendingHere()" not in send, (
        "전송 경로가 브리지 대기로 분기한다 — 대기 중 새 질문이 막힌다")


# ── ⑥ 병렬 러너 ─────────────────────────────────────────────────────────────


def test_runner_scales_concurrency_to_demand():
    """동시 처리가 **수요를 따라간다** — 긴 조사 하나가 뒤따르는 짧은 질문을 막지 않는다.

    계약이 2026-08-28 사용자 결정으로 바뀌었다. 종전은 "기본 2개 고정"(`Semaphore(workers)`)
    이었는데, 그러면 질문이 하나뿐인 대부분의 시간에도 쓰지 않을 용량을 들고 있다. 지금은
    **1에서 시작해 관측된 수요만큼 늘고, 안 쓰면 오래된 것부터 회수**한다.

    막지 않는다는 원래 의도는 유지된다 — 오히려 상한(8)까지 늘 수 있어 종전(2)보다 넓다.
    """
    src = _src(RUNNER)
    assert "_DEFAULT_WORKERS = 1" in src, "1개에서 시작하지 않는다"
    assert "--workers" in src and "--max-workers" in src
    assert "class WorkerPool" in src, "동시 처리 상한이 동적 풀로 잡히지 않는다"
    assert "threading.Semaphore(" not in src, "고정 세마포어가 남아 있다(용량이 안 변한다)"


def test_runner_cancel_registry_is_thread_safe():
    """취소 원장이 락으로 보호된다.

    대기 스레드와 워커가 함께 읽고 쓴다. 락 없이도 CPython 에서는 대개 동작하지만, "대개" 로
    두면 취소가 가끔 안 먹는 버그가 되고 그건 재현이 거의 불가능하다.
    """
    src = _src(RUNNER)
    assert "class CancelRegistry" in src
    reg = src[src.index("class CancelRegistry"):src.index("# ── 내 AI 호출")]
    assert "threading.Lock()" in reg, "공유 집합이 락 없이 쓰인다"
    assert reg.count("with self._lock") >= 3, "일부 접근이 락 밖에 있다"


def test_runner_once_waits_for_the_worker():
    """`--once` 가 그 한 건이 **끝날 때까지** 기다린다.

    바로 반환하면 daemon 스레드가 죽어 답이 제출되지 않는다 — `--once` 가 아무것도 하지
    않는 것과 같아진다.
    """
    src = _src(RUNNER)
    main = src[src.index("def main()"):]
    assert "done_once.wait()" in main, "--once 가 워커를 기다리지 않는다"


@pytest.mark.parametrize("needle,why", [
    ("skip.add(task_id)", "점유 실패가 반복되면 같은 task 를 무한히 다시 시도한다"),
    # 2026-08-28: 종전엔 `slots.release()` 를 검사했다. 지금은 실패 경로가 자리를 **잡기 전에**
    # 빠지므로 반납할 것이 없고(구조적 해소), 자리를 잡은 뒤 점유가 실패하는 경로만 반납한다.
    # 시각은 이제 락 안에서 만든다(락 밖 timestamp 가 정렬 불변식을 깼다 — codex P2).
    ("pool.release(sid)", "점유 실패 시 잡아 둔 자리를 반납하지 않는다(영구 고갈)"),
])
def test_runner_wait_loop_cannot_spin(needle: str, why: str):
    """대기 루프가 서버를 두드리는 tight loop 로 변하지 않는다."""
    src = _src(RUNNER)
    main = src[src.index("def main()"):]
    assert needle in main, why


def test_runner_skip_list_is_not_permanent():
    """`skip` 이 영구 블랙리스트가 되지 않는다.

    다른 러너가 집어 간 작업을 skip 에 넣었는데 그쪽이 죽어 lease 가 만료되면 그 작업은
    대기열로 돌아온다. 그때도 계속 건너뛰면 **러너가 돌고 있는데 사용자는 답을 못 받는다.**

    비우는 시점이 `timed_out` 인 것도 계약이다 — "남은 것이 전부 skip" 일 때 비우면
    비움→재시도→실패→다시 전부 skip 이 **간격 없이** 돌아 tight loop 가 된다.
    """
    src = _src(RUNNER)
    main = src[src.index("def main()"):]
    assert "skip.clear()" in main, "skip 이 영구 블랙리스트다"
    clear_at = main.index("skip.clear()")
    window = main[max(0, clear_at - 200):clear_at]
    assert 'res.get("timed_out")' in window, (
        "skip 을 타임아웃이 아닌 시점에 비운다 — 실패 반복 시 tight loop 가 된다")


def test_runner_backs_off_instead_of_spinning_and_stays_alive():
    """대기 질문이 있는데 한 건도 처리 못 하는 상태에서 **쉬되 죽지는 않는다**.

    두 가지를 동시에 만족해야 한다:

    1. **hot loop 금지** — 그 상태로 곧바로 `continue` 하면 `wait_for_request` 가 즉시 돌아와
       간격 없이 서버를 두드린다(우리가 없애려던 폴링의 최악 형태).
    2. **러너를 죽이지 않는다**(codex P1-4) — 종전에는 20라운드 뒤 `exit 4` 였는데, 그러면
       **진행 중이던 다른 워커의 답변까지 함께 사라진다**. 한 task 의 점유 실패로 러너 전체를
       끄는 것은 blast radius 가 과하다. 경고는 남기되 계속 산다.
    """
    src = _src(RUNNER)
    assert "_MAX_STALLED_ROUNDS" in src, "spin 감지 상한이 없다"
    main = src[src.index("def main()"):]
    blk = main[main.index("if not pending:"):]
    blk = blk[:blk.index("stalled = 0")]
    assert "time.sleep(" in blk, "쉬지 않고 다시 물어 hot loop 가 된다"
    assert "return 4" not in blk, (
        "stall 로 러너를 종료한다 — 진행 중이던 다른 워커의 답변까지 잃는다")
    # 잠그려는 성질은 「**눈에 띄는 심각도로** 알린다」이지 `WARN` 이라는 글자가 아니다.
    # 로그가 구조화되며(TASK-20260901T163000) 이 자리는 `level="ERROR"` 가 됐다 — 종전보다
    # 강한 신호인데 글자 검사만 보면 «알리지 않는다» 로 읽혔다. 성질로 검사한다.
    assert ('level="ERROR"' in blk or 'level="WARN"' in blk or "WARN" in blk), \
        "조용히 돌기만 하고 사용자에게 알리지 않는다"
    assert "task.stalled" in blk, "사건 코드가 없으면 이 상태를 로그에서 걸러낼 수 없다"


def test_runner_keeps_listening_for_cancels_while_workers_are_busy():
    """워커가 다 차 있어도 **취소 통보는 계속 받는다** (codex P1-2).

    취소와 새 질문은 같은 응답으로 온다. 자리를 `wait_for_request` **앞에서** 잡으면, 워커가
    다 찬 동안 그 호출 자체를 하지 않게 되어 **취소 채널이 함께 끊긴다** — 사용자가 중단을
    눌러도 러너는 최대 `_AI_TIMEOUT_SEC`(약 28분) 동안 모른 채 개인 계정 토큰을 태운다.
    취소를 즉시 인지시키려던 설계가 정작 가장 필요한 순간에 꺼져 있는 셈이다.
    """
    src = _src(RUNNER)
    main = src[src.index("def main()"):]
    # ⚠ 주석을 걸러낸 뒤 본다 — 이 구간의 주석은 고친 결함을 설명하느라 옛 표현
    #   (`slots.acquire()` 가 앞에 있었다)을 그대로 인용한다. 걸러내지 않으면 그 문장을
    #   코드로 오인해 "아직 결함이 있다" 고 오판한다.
    main = "\n".join(l for l in main.split("\n") if not l.strip().startswith("#"))
    loop = main[main.index("while True:"):]
    # 2026-08-28: 고정 세마포어 → 동적 `WorkerPool`. **계약은 그대로**(대기가 취득보다 앞 ·
    # 취득은 비차단) — 검사 대상만 따라간다. `try_acquire()` 는 이름 그대로 블로킹하지 않는다.
    wait_at = loop.index('api.call("wait_for_request"')
    acq_at = loop.index("pool.try_acquire()")
    assert wait_at < acq_at, (
        "워커 자리를 대기보다 먼저 잡는다 — 자리가 없으면 취소 통보도 함께 끊긴다")
    assert "sid = pool.try_acquire()" in loop and "if sid is None:" in loop, (
        "자리 획득이 차단형이다 — 거기서 멈추면 그동안 취소를 못 듣는다")


def test_stream_holds_one_connection_and_commits_each_tick():
    """SSE 가 tick 마다 커넥션을 새로 열지 않는다 — 그리고 스냅샷을 커밋으로 푼다.

    55초 스트림 하나가 커넥션을 55번 만들면 연결 비용이 조회 비용을 넘고, 동시 대화 수만큼
    선형으로 붙는다. 반대로 하나를 오래 들고 있으면 **트랜잭션 스냅샷이 고정돼 상태 변화가
    영영 안 보인다**(REPEATABLE READ) — `wait_for_request` 가 같은 이유로 매 확인마다 커밋한다.
    둘 다 만족해야 한다.
    """
    fn = _pyfunc(TOOLS_PY, "bridge_stream")
    inner = fn[fn.index("async def event_stream("):]
    # 루프 **안**의 연결 시도는 `sconn is None` 가드 뒤에만 허용된다(일시 장애 복구).
    # 가드 없이 매 tick 열면 그것이 곧 tick 당 커넥션이다.
    loop_body = inner[inner.index("while True:"):]
    for idx in range(len(loop_body)):
        idx = loop_body.find("app._connect_memory()", idx)
        if idx < 0:
            break
        preceding = loop_body[max(0, idx - 200):idx]
        assert "if sconn is None:" in preceding, (
            "루프 안에서 가드 없이 커넥션을 연다 — tick 마다 연결이 생긴다")
        break
    assert "sconn.close()" in inner, "스트림 종료 시 커넥션을 닫지 않는다(누수)"
    snap = _pyfunc(TOOLS_PY, "_bridge_stream_snapshot")
    assert "conn.commit()" in snap, "스냅샷을 풀지 않아 상태 변화가 안 보인다"


def test_stream_skips_pointless_queries_before_claim():
    """아직 아무도 안 집었으면 조사 내역을 뒤지지 않는다(있을 수 없다).

    tick 마다 도는 조회라 값이 싸지 않다. 마찬가지로 연결 여부 판정도 `waiting` 국면에서만
    의미가 있다 — 이미 집혔거나 끝난 뒤에는 `not_connected` 로 갈릴 일이 없다.
    """
    snap = _pyfunc(TOOLS_PY, "_bridge_stream_snapshot")
    # 반환 모양이 `(steps, 생략 수)` 로 바뀌었다(2026-08-31, 최신 쪽 창 + 절단 고지).
    # 잠그는 계약은 그대로다 — 점유 전에는 조회 자체를 하지 않는다.
    assert "if claimed_by is not None else ([], 0)" in snap, (
        "점유 전에도 매 tick 단계를 조회한다")
    assert "if not submitted and claimed_by is None" in snap, (
        "종결된 task 에도 매 tick 연결 여부를 조회한다")


# ── codex 적대 리뷰 조치 (2026-08-28) ────────────────────────────────────────


def test_stream_does_not_block_the_event_loop():
    """SSE tick 의 동기 DB 조회를 이벤트 루프에서 직접 돌리지 않는다 (codex P1-3).

    `_bridge_stream_snapshot` 은 mysql-connector·psycopg **동기** 호출을 한다 — 매초,
    열려 있는 스트림 수만큼. 루프에서 직접 부르면 그 시간 동안 **이 워커의 모든 요청**이
    멈춘다(DB 가 느려지면 브리지와 무관한 대화·콘솔까지 전면 정지).
    """
    fn = _pyfunc(TOOLS_PY, "bridge_stream")
    assert "asyncio.to_thread(" in fn, "동기 DB 조회가 이벤트 루프를 막는다"
    # 주석에도 함수명이 나오므로 **코드 줄만** 본다 — 안 그러면 주석을 호출로 오인한다.
    code = "\n".join(l for l in fn.split("\n") if not l.strip().startswith("#"))
    inner = code[code.index("async def event_stream("):]
    call_line = next(l for l in inner.split("\n") if "_bridge_stream_snapshot" in l)
    idx = inner.index(call_line)
    assert "to_thread" in inner[max(0, idx - 120):idx + len(call_line)], (
        "스냅샷 호출이 스레드로 밀려나지 않았다 — 매 tick 이벤트 루프를 막는다")


def test_stream_has_a_concurrency_cap_that_is_always_released():
    """동시 스트림 상한이 있고, **어떤 경로로 끝나도 반납**된다 (codex P1-3).

    스트림 하나가 커넥션 하나를 55초 붙든다. 상한이 없으면 뷰어 수만큼 커넥션이 늘어
    풀이 마르고 무관한 경로까지 죽는다. 반대로 카운터가 새면 상한이 **영구히 닫혀**
    이후 모두가 조용히 폴링으로 강등된다 — 그래서 반납은 `finally` 여야 한다.
    """
    tools = _src(TOOLS_PY)
    assert "_BRIDGE_STREAM_MAX_CONCURRENT" in tools, "동시 스트림 상한이 없다"
    fn = _pyfunc(TOOLS_PY, "bridge_stream")
    assert "503" in fn, "상한 초과를 거절(폴링 강등)하지 않는다"
    inner = fn[fn.index("async def event_stream("):]
    tail = inner[inner.index("finally:"):]
    assert "_BRIDGE_STREAM_LIVE" in tail, "상한 카운터를 finally 에서 반납하지 않는다(누수)"


def test_stream_drops_a_broken_connection():
    """죽은 커넥션을 상한이 끝날 때까지 재사용하지 않는다 (codex P2-3).

    종전에는 스냅샷 예외를 가짜 `waiting` 으로 바꾸기만 하고 `sconn` 을 그대로 뒀다 —
    커넥션이 죽으면 남은 55초 동안 같은 예외를 반복하며 **완료·취소 전환이 통째로 숨겨졌다.**
    """
    snap = _pyfunc(TOOLS_PY, "_bridge_stream_snapshot")
    assert "_conn_broken" in snap, "끊긴 커넥션을 호출측에 알리지 않는다"
    fn = _pyfunc(TOOLS_PY, "bridge_stream")
    assert '_conn_broken' in fn and "sconn = None" in fn, (
        "끊긴 커넥션을 버리고 다시 열지 않는다")


def test_cancel_notification_is_scoped_to_the_claiming_session():
    """취소 통보를 **점유한 세션**에게만 준다 (codex P2-1).

    계정 단위로만 좁히면 같은 계정의 러너 B 가 러너 A 의 취소를 먼저 받아 소비한다
    (통보 뒤 점유를 놓으므로 A 는 영원히 못 듣는다). A 는 생성이 끝날 때까지 계속 태운다.
    """
    fn = _pyfunc(TOOLS_PY, "wait_for_request")
    sel = fn[fn.index("SELECT TaskId FROM WebAiTasks"):]
    sel = sel[:sel.index("canceled = [")]
    assert "ClaimedClient" in sel, "점유 세션을 수신자 조건에 넣지 않는다"


def test_enqueue_rollback_cancels_an_already_claimed_task():
    """적재 롤백 중 이미 점유됐으면 **취소로 승격**한다 (codex P2-4).

    질문 저장이 실패해 API 가 500 을 돌려준 뒤에도 개인 AI 는 그 질문을 계속 처리한다.
    지우지 못한 채 두면 대화에 **질문 없는 고아 답변**이 나타난다(사용자는 묻지도 않은 답을 본다).
    """
    fn = _pyfunc(CONV_PY, "_delete_bridge_task")
    assert "cur.rowcount" in fn, "삭제 성공 여부를 확인하지 않는다"
    assert "STATUS_CANCELED" in fn, "지우지 못한 task 를 취소로 승격하지 않는다"


def test_runner_treats_connection_failure_as_failure_everywhere():
    """`_failed` 를 claim·submit 에서도 본다 (codex P2-2).

    앞선 수정은 대기 루프만 고쳤다. claim 중 끊기면 **빈 응답을 정상 점유로 읽어** AI 를
    돌리고, submit 중 끊기면 저장 여부를 모르는데 "제출 완료" 로 기록한다.
    """
    src = _src(RUNNER)
    main = src[src.index("def main()"):]
    assert 'claimed.get("_failed")' in main, "claim 실패를 성공으로 읽는다"
    handle = src[src.index("def handle_one("):]
    handle = handle[:handle.index("\ndef ")]
    assert 'res.get("_failed")' in handle, "submit 실패를 성공으로 읽는다"


def test_runner_does_not_permanently_skip_transient_claim_failures():
    """일시 장애(5xx·429·연결 실패)로 task 를 **영구 skip 하지 않는다** (codex P1-4).

    그 task 는 정상이고 잠시 뒤면 집을 수 있다. 영구 skip 은 409(이미 남이 가져감)처럼
    재시도해도 달라지지 않는 경우에만 쓴다.
    """
    src = _src(RUNNER)
    main = src[src.index("def main()"):]
    blk = main[main.index('if claimed.get("_http") or claimed.get("_failed"):'):]
    blk = blk[:blk.index("def _work(")]
    assert "_code < 500" in blk and "429" in blk, (
        "일시 장애까지 영구 skip 한다 — 러너가 도는데 그 질문만 영영 처리되지 않는다")
