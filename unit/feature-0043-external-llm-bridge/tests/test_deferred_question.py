"""feature-0043 — 연결이 끊긴 동안 보낸 질문을 **다시 입력하지 않아도** 되는가.

라이브 실측(2026-08-27, admin):

    19:07:58  로그아웃 → 세션 폐기 + AI 연결 토큰 동시 폐기(P0-R 의 의도된 동작)
    19:08:0x  질문 전송 → 그 시점 연결 없음 → **적재조차 되지 않음** + "다시 질문해 주세요"
    19:09:04  AI 재인증

사용자에게 이건 "LLM 이 막혔다" 로 보였다. 실제로는 판정이 정확했고, **재입력을 요구한 것이
마찰**이었다. 로그아웃이 AI 연결을 함께 끊으므로 재로그인 직후가 정확히 그 창이다.

## 계약 (사용자 결정 2026-08-28)

| | 종전 | 지금 |
|---|---|---|
| 미연결 질문 | 적재 안 함 · 재입력 요구 | `Status='deferred'` 로 **보관** |
| 연결 성립 시 | (없음) | **최근 1건만** `open` 승격, 나머지 `expired` |
| 밀린 질문 폭주 | 막힘(적재를 안 하니까) | 막힘(1건만 올리니까) |

"전부 처리" 도 "전부 버림" 도 아니다 — 사용자가 그 순간 원하는 것은 **마지막으로 물은 것**이다.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_REPO = _UNIT.parent

BRIDGE_TASKS = _REPO / "shared" / "bridge_tasks.py"
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
CONVS = WEB_SRC / "routers" / "conversations.py"
AI_TOOLS = WEB_SRC / "routers" / "ai_tools.py"


def _func_source(path: pathlib.Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{path.name}: 함수 {name} 를 찾지 못했다(이름이 바뀌었나?)")


def _load_bridge_tasks():
    """`shared.bridge_tasks` 를 단독 로드한다(웹 앱 import 없이 — 상수·순수 로직 검사용)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_bridge_tasks_under_test", BRIDGE_TASKS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# ── 상태 정본 ─────────────────────────────────────────────────────────────────


def test_deferred_and_expired_statuses_exist():
    mod = _load_bridge_tasks()
    assert mod.STATUS_DEFERRED == "deferred"
    assert mod.STATUS_EXPIRED == "expired"
    # VARCHAR(16) 에 들어가야 한다 — 넘치면 INSERT 가 조용히 잘리거나 실패한다.
    for value in (mod.STATUS_DEFERRED, mod.STATUS_EXPIRED):
        assert len(value) <= 16


def test_deferred_is_cancelable():
    """새 질문을 보내면 이전 **보류** 질문도 함께 정리돼야 한다.

    빼면: 연결되는 순간 사용자가 방금 고쳐 물은 질문 대신 **엉뚱한 옛 질문**이 승격된다.
    """
    mod = _load_bridge_tasks()
    assert mod.STATUS_DEFERRED in mod.CANCELABLE_STATUSES
    assert mod.STATUS_OPEN in mod.CANCELABLE_STATUSES

    src = _func_source(BRIDGE_TASKS, "cancel_bridge_tasks")
    assert "CANCELABLE_STATUSES" in src, "취소 대상이 여전히 open 하나로 고정돼 있다"
    # DELETE 갈래도 보류를 포함해야 한다(보류는 점유될 수 없어 항상 이 갈래로 온다).
    assert src.count("CANCELABLE_STATUSES") >= 2, "DELETE 문이 보류 질문을 지우지 못한다"


def test_deferred_has_an_age_limit():
    """사흘 전 질문이 오늘 연결하는 순간 답변으로 돌아오면 '이어받기' 가 아니라 기억에 없는 응답이다."""
    mod = _load_bridge_tasks()
    assert isinstance(mod.DEFERRED_MAX_AGE_HOURS, int) and mod.DEFERRED_MAX_AGE_HOURS > 0
    src = _func_source(BRIDGE_TASKS, "promote_latest_deferred")
    assert "DEFERRED_MAX_AGE_HOURS" in src, "승격 후보 조회에 기간 상한이 없다"


# ── 승격 규칙 ─────────────────────────────────────────────────────────────────


def test_promotion_takes_exactly_one_and_expires_the_rest():
    """최근 1건만 올리고 나머지는 만료 — '전부 처리'(폭주) 와 '전부 버림'(재입력) 사이."""
    src = _func_source(BRIDGE_TASKS, "promote_latest_deferred")
    assert "ORDER BY CreatedAt DESC" in src and "LIMIT 1" in src, (
        "가장 최근 1건을 고르지 않는다")
    assert "STATUS_EXPIRED" in src, "밀린 보류 질문을 만료시키지 않는다 — 다음 연결 때 되살아난다"


def test_promotion_update_is_atomic():
    """조건을 UPDATE 안에 둬야 두 세션이 동시에 연결해도 한 번만 승격된다.

    상세 계약은 `test_promotion_and_expiry_are_one_statement` 가 본다 — 여기서는 "조건 없는
    UPDATE 가 아니다" 라는 최소선만 지킨다.
    """
    src = _func_source(BRIDGE_TASKS, "promote_latest_deferred")
    assert "WHERE AccountId = %s AND Origin = 'web' AND Status = %s" in src, (
        "승격이 조건 없는 UPDATE 다 — 동시 연결에서 같은 질문이 두 번 답변될 수 있다")
    assert "rowcount" in src, "실제로 승격됐는지 확인하지 않고 성공으로 단정한다"


def test_promotion_failure_never_breaks_the_tool_call():
    """승격은 편의 기능이다 — 여기서 예외를 올리면 도구 호출 자체가 실패한다."""
    src = _func_source(BRIDGE_TASKS, "promote_latest_deferred")
    assert "except Exception" in src and "return \"\", []" in src


# ── 적재 경로 ─────────────────────────────────────────────────────────────────


def test_runner_off_question_is_stored_as_deferred():
    """⚠ 축이 바뀌었다 (P0-AB, 사용자 결정 2026-08-28).

    종전 보류 사유는 **토큰 없음**이었다. 지금 그 상태는 화면이 막고 서버가 409 로 거절하므로
    적재 자체가 없다. 남은 보류 사유는 **토큰은 살아 있는데 러너가 꺼진 창** 뿐이다 —
    사용자 결정: *"이미 로그인 된 상태(연결 완료 상태)에서 질문이 진행되었다면 보관하여 다시
    처리합니다."*

    지켜지는 것은 그대로다: 게이트를 통과해 전송된 질문은 **재입력을 요구하지 않는다.**
    """
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert '"open" if listening else "deferred"' in src, (
        "러너 생존으로 상태를 가르지 않는다 — 러너가 꺼진 사이의 질문이 보관되지 않는다")
    assert "_account_ai_is_listening(" in src, (
        "러너 생존을 재지 않는다 — 토큰만 보고 open 으로 넣으면 아무도 안 가져간다")


def test_deferred_reply_does_not_poll():
    """보류 질문은 언제 승격될지 모른다 — 5초마다 묻게 두면 종일 빈 요청을 보낸다."""
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    assert '"bridge_pending": listening' in src, (
        "러너가 꺼진 상태에서도 폴링을 켠다(또는 대기 중인데 폴링이 꺼졌다)")


def test_notice_promises_no_reentry():
    """안내가 여전히 '다시 질문해 주세요' 면, 고친 동작을 사용자가 알 방법이 없다.

    P0-AB 이후 보류 말풍선은 `_BRIDGE_NOTICE_NOT_LISTENING` 이다(사유가 '토큰 없음' 에서
    '러너 꺼짐' 으로 바뀌었으므로 문구도 바뀐다 — 사용자가 할 일이 다르다). 계약 자체는
    그대로: **이어받는다**는 사실과 **1건 규칙**을 말해야 한다.
    """
    text = CONVS.read_text(encoding="utf-8")
    start = text.index("_BRIDGE_NOTICE_NOT_LISTENING")
    notice = text[start:start + 400]
    assert "이 질문부터" in notice, "연결 후 이어받는다는 사실을 안내하지 않는다"
    assert "다시 질문해 주세요" not in notice, "재입력을 요구하는 옛 문구가 남아 있다"
    assert "마지막 질문 1건" in notice, "여러 번 물었을 때의 규칙을 밝히지 않는다"


def test_expired_notice_exists_and_is_honest():
    text = CONVS.read_text(encoding="utf-8")
    assert "_BRIDGE_NOTICE_DEFERRED_EXPIRED" in text
    start = text.index("_BRIDGE_NOTICE_DEFERRED_EXPIRED = (")
    notice = text[start:start + 400]
    assert "처리되지 않았습니다" in notice, (
        "만료를 알리지 않으면 '연결하면 처리합니다' 가 화면에 영원히 박제된다")


# ── 승격 배선 ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("handler", ["list_open_requests", "wait_for_request"])
def test_tool_surface_promotes_on_connect(handler: str):
    """개인 AI 가 '가져갈 질문 있나' 를 묻는 순간이 연결 성립의 유일한 증거다."""
    src = _func_source(AI_TOOLS, handler)
    assert "_promote_deferred_for" in src, (
        f"{handler} 가 보류 질문을 올리지 않는다 — 연결해도 이어받기가 일어나지 않는다")


def test_promotion_is_called_once_not_per_loop():
    """`wait_for_request` 의 0.5초 루프 **안**에서 부르면 같은 판정을 초당 두 번 반복한다."""
    src = _func_source(AI_TOOLS, "wait_for_request")
    assert src.index("_promote_deferred_for") < src.index("while True:"), (
        "승격이 대기 루프 안에 있다")


def test_expired_placeholders_reuse_the_web_notice_helper():
    """말풍선 정정 SQL 을 여기서 다시 쓰면 두 벌이 되어 언젠가 갈린다."""
    src = _func_source(AI_TOOLS, "_settle_expired_deferred")
    assert "_mark_bridge_placeholders_canceled" in src, "웹 쪽 정본을 재사용하지 않는다"
    assert "UPDATE agent_runtime.messages" not in src, "말풍선 SQL 이 두 벌이 됐다"


def test_settling_failure_does_not_undo_promotion():
    src = _func_source(AI_TOOLS, "_settle_expired_deferred")
    assert "except Exception" in src, "말풍선 정정 실패가 승격을 무르게 한다"


# ── 대기열 격리 ───────────────────────────────────────────────────────────────


def test_deferred_never_appears_in_the_queue():
    """보류는 대기열에 보이면 안 된다 — 보이는 순간 '밀린 것 한꺼번에' 가 그대로 재발한다."""
    for handler in ("list_open_requests", "wait_for_request", "claim_request"):
        src = _func_source(AI_TOOLS, handler)
        assert "Status='open'" in src or "Status = 'open'" in src, (
            f"{handler} 가 상태를 좁히지 않는다 — 보류 질문이 대기열에 샌다")
        assert "deferred" not in src.replace("_promote_deferred_for", ""), (
            f"{handler} 의 조회 술어에 deferred 가 섞였다")


# ── codex 적대 리뷰 조치 (REV-20260828T070000) ────────────────────────────────


def test_promotion_and_expiry_are_one_statement():
    """승격과 만료가 한 문장인가 — 나누면 동시 연결에서 서로 다른 행을 각자 승격한다.

    요청 커넥션은 autocommit 이라 문장마다 즉시 확정된다. A 가 T2 를 올리고 T1 을 읽은 직후
    B 가 T1 을 올리면, "최근 1건" 약속이 깨져 두 질문이 모두 답변된다(codex P1).
    """
    src = _func_source(BRIDGE_TASKS, "promote_latest_deferred")
    assert "CASE WHEN TaskId = %s THEN %s ELSE %s END" in src, (
        "승격과 만료가 별도 UPDATE 다 — 동시 연결에서 중복 승격이 가능하다")
    # 그 계정의 보류 **전부**를 한 번에 소진해야 뒤이은 실행이 0행으로 끝난다.
    assert "AND Status = %s" in src and "AccountId = %s" in src
    assert "changed" in src, "실제로 바꾼 것이 있는지 보지 않고 승격됐다고 단정한다"


def test_rollback_deletes_deferred_too():
    """미연결 적재의 보상 삭제가 보류를 못 지우면, 화면에 없는 질문이 나중에 승격된다."""
    src = _func_source(CONVS, "_delete_bridge_task")
    assert "CANCELABLE_STATUSES" in src, "삭제 술어가 open 하나로 고정돼 있다"
    # 주석에는 옛 술어가 설명으로 남을 수 있다 — **실행되는 SQL** 만 본다.
    sql_lines = [ln for ln in src.splitlines()
                 if "DELETE FROM WebAiTasks" in ln or "AND Status" in ln]
    assert sql_lines, "삭제 SQL 을 찾지 못했다"
    assert not any("Status='open'" in ln for ln in sql_lines), "삭제가 여전히 open 만 지운다"


def test_expired_placeholder_settling_is_retried():
    """상태(MySQL)와 말풍선(PG)은 다른 저장소다 — 한 번 실패하면 화면이 영구히 거짓말한다."""
    src = _func_source(AI_TOOLS, "_promote_deferred_for")
    assert "_recent_unsettled_expired" in src, (
        "이미 만료된 것의 말풍선을 다시 정정하지 않는다 — 일시 장애가 영구 잔존이 된다")
    helper = _func_source(AI_TOOLS, "_recent_unsettled_expired")
    assert "_STATUS_EXPIRED" in helper and "DEFERRED_MAX_AGE_HOURS" in helper.replace("_D", "D"), (
        "재정정 범위가 최근으로 좁혀지지 않는다")


def test_deferred_reply_reaches_the_frontend():
    """`bridge_pending` 하나로 조건을 걸면 미연결 응답이 조립에서 통째로 빠진다.

    그러면 프런트는 task·연결 상태·서버 토스트를 전부 잃고 '완료' 토스트를 띄운다(codex P2).
    """
    src = CONVS.read_text(encoding="utf-8")
    assert 'agent_result.get("bridge_pending") or agent_result.get("bridge_deferred")' in src, (
        "응답 조립이 보류 적재를 프런트에 전달하지 않는다")
    body = _func_source(CONVS, "_enqueue_web_bridge_task")
    # P0-AB: 판정 축이 `connected`(토큰) → `listening`(러너)로 옮겨졌다. 토큰 축은 이 함수에
    # 도달하기 전에 이미 참으로 확정돼 있다(아니면 409 로 거절됐다).
    assert '"bridge_deferred": not listening' in body
    assert '"bridge_queued": listening' in body, (
        "프런트가 폴링 여부·토스트 강조를 가를 신호가 없다")


def test_expired_is_a_terminal_phase():
    """만료를 종결로 다루지 않으면 DB 는 끝났다는데 화면은 '대기 중' 을 그린다."""
    src = _func_source(AI_TOOLS, "_bridge_phase")
    assert "_STATUS_EXPIRED" in src and '"expired"' in src
    # 취소와 같은 자리에서 걸러야 한다 — `claimed_by` 판정보다 앞.
    assert src.index("_STATUS_EXPIRED") < src.index("claimed_by is not None")
    assert "_STATUS_DEFERRED" in src, "보류 상태의 국면이 '연결 없음' 과 뭉뚱그려진다"


def test_frontend_treats_expired_as_terminal():
    composer = WEB_SRC / "static" / "app" / "composer.js"
    src = composer.read_text(encoding="utf-8")
    assert 'phase === "canceled" || phase === "expired"' in src, (
        "프런트가 만료를 종결로 다루지 않는다 — 폴러가 계속 돌고 '대기 중' 이 남는다")
