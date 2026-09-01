"""브리지 진행 단계: 추론 구간 기록 + 최신 쪽 창 + 절단 고지 (2026-08-31 제보).

제보 두 갈래:

1. 「각 도구에 대한 수행시간은 확인되었지만, 추론을 진행하는 부분은 확인되지 않아」
2. 「시간이 지날때마다 각 실행 단계의 갱신이 멈추는 이슈」

여기서 잠그는 것은 **서버 쪽 두 계약**이다(프런트 계약은
`tests/verify_bridge_live_step_progress.mjs`):

  W1 도구 단계 뒤에 **추론 구간**(`action='activity'`)이 하나 더 남는다 — 이것이 없으면
     도구 사이의 시간이 어느 단계에도 붙지 않아 타임라인에서 사라진다.
  W2 진행 단계 창은 **최신 쪽**이고, 잘린 앞 단계 수를 함께 돌려준다.
     종전 `ORDER BY step_index ASC LIMIT` 은 상한에 닿는 순간 가장 오래된 N 건에 고정돼
     진행 갱신이 영영 멎었다(새로고침해도 같은 화면).
  W3 커넥션을 닫는다 — tick(1초)마다 도는 조회가 열린 커넥션을 남기지 않는다.

가짜 커서로 **실제 함수를 실행**해 확인한다(소스 문자열 검사가 아니다).
"""
from __future__ import annotations

import datetime
import importlib
import json
import re
import sys

import pytest


def _import_ai_tools():
    try:
        return importlib.import_module("routers.ai_tools")
    except ModuleNotFoundError:
        sys.path.insert(0, "/app")
        return importlib.import_module("routers.ai_tools")


ai_tools = _import_ai_tools()


# ── 가짜 PG ───────────────────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, owner):
        self._owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._owner.executed.append((sql, params))

    def fetchall(self):
        return self._owner.rows

    def close(self):
        pass


class _FakePg:
    def __init__(self, rows):
        self.rows = rows
        self.executed: list[tuple[str, object]] = []
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def close(self):
        self.closed = True


def _row(step_index: int, *, action: str = "tool", tool: str = "execute_sql"):
    """`_bridge_live_steps` 가 읽는 13열 튜플."""
    return (
        step_index, action, tool, f"{tool}: 조회", "테이블을 조회한다", "derived",
        "질문에 필요한 컬럼을 확인하기 위해", "external-ai",
        json.dumps({"datasource": "ds1", "schema_name": "dbo"}),
        "SELECT 1", json.dumps({"rows_returned": 3, "elapsed_ms": 420}), "",
        datetime.datetime(2026, 8, 31, 11, 0, step_index % 60),
    )


# ── W1 추론 구간이 도구 단계 뒤에 남는다 ──────────────────────────────────────

def test_w1_tool_step_is_followed_by_a_reasoning_gap_step(monkeypatch):
    """도구 1회 = tool 단계 1건 + 추론 구간 activity 1건."""
    recorded: list[dict] = []
    monkeypatch.setattr(ai_tools, "_insert_bridge_step",
                        lambda conv, run, entry: recorded.append(entry) or 1)

    ai_tools._record_bridge_step(
        conn=None, task={"conversation_id": "c1", "task_id": "t_abc"},
        tool_name="execute_sql", args={"datasource": "ds1"},
        tool_result="rows", work="테이블을 조회한다", reason="컬럼 확인",
        elapsed_ms=420.0)

    actions = [str(e.get("action") or "") for e in recorded]
    assert actions == ["step", "activity"], (
        f"도구 단계 뒤에 추론 구간이 남지 않는다 — 기록된 단계: {actions}. "
        "이것이 없으면 도구 사이의 시간이 어느 단계에도 귀속되지 않는다.")


def test_w1_reasoning_gap_is_attributed_to_the_runtime_not_the_ai(monkeypatch):
    """관측한 구간만 적는다 — 개인 AI 의 사고 내용을 지어내지 않는다."""
    recorded: list[dict] = []
    monkeypatch.setattr(ai_tools, "_insert_bridge_step",
                        lambda conv, run, entry: recorded.append(entry) or 1)

    ai_tools._record_bridge_step(
        conn=None, task={"conversation_id": "c1", "task_id": "t_abc"},
        tool_name="list_schemas", args={}, tool_result="ok")

    gap = recorded[-1]
    assert gap["work_source"] == "bridge-runtime", "출처가 우리 관측으로 표시되지 않는다"
    assert not gap["reason"], (
        "사유를 채우고 있다 — 그 AI 가 왜 그렇게 판단했는지는 우리가 모른다")
    assert gap["tool"] == "", "추론 구간에 도구명이 붙어 도구 단계로 읽힌다"


def test_w1_failed_tool_calls_also_open_a_reasoning_gap(monkeypatch):
    """실패한 조사 뒤에도 AI 는 다음 작업을 정한다 — 그 구간이 사라지면 안 된다."""
    recorded: list[dict] = []
    monkeypatch.setattr(ai_tools, "_insert_bridge_step",
                        lambda conv, run, entry: recorded.append(entry) or 1)

    ai_tools._record_bridge_step(
        conn=None, task={"conversation_id": "c1", "task_id": "t_abc"},
        tool_name="execute_sql", args={}, tool_result="", error="구문 오류")

    assert [e["action"] for e in recorded] == ["step", "activity"]


def test_w1_no_web_conversation_records_nothing(monkeypatch):
    """외부 AI 가 스스로 연 task(웹 대화 없음)에는 그릴 화면이 없다 — 무회귀."""
    recorded: list[dict] = []
    monkeypatch.setattr(ai_tools, "_insert_bridge_step",
                        lambda conv, run, entry: recorded.append(entry) or 1)

    ai_tools._record_bridge_step(
        conn=None, task={"conversation_id": "", "task_id": "t_abc"},
        tool_name="execute_sql", args={}, tool_result="ok")

    assert recorded == []


# ── W2 최신 쪽 창 + 절단 고지 ────────────────────────────────────────────────

def test_w2_window_takes_the_newest_steps_in_chronological_order(monkeypatch):
    """상한을 넘으면 **최신** N 건을, 화면 순서(시간순)로 돌려준다."""
    cap = ai_tools._BRIDGE_LIVE_STEPS_MAX
    total = cap + 7
    # DB 는 `step_index DESC` 로 돌려준다 — 함수가 뒤집어야 시간순이 된다.
    rows = [_row(total - i) for i in range(cap)]
    pg = _FakePg(rows)
    monkeypatch.setattr(ai_tools, "_pg", lambda: pg)

    steps, omitted = ai_tools._bridge_live_steps("t_abc")

    assert [s["step_index"] for s in steps] == sorted(s["step_index"] for s in steps), (
        "화면에 역순으로 나간다")
    assert steps[-1]["step_index"] == total, "가장 최근 단계가 빠졌다 — 창이 앞쪽에 고정됐다"
    assert omitted == 7, f"생략 수를 잘못 셌다: {omitted}"


def test_w2_query_orders_desc_so_the_window_follows_progress(monkeypatch):
    """정렬이 ASC 로 되돌아가면 상한에 닿는 순간 갱신이 멎는다 — 쿼리 축을 잠근다."""
    pg = _FakePg([_row(1)])
    monkeypatch.setattr(ai_tools, "_pg", lambda: pg)

    ai_tools._bridge_live_steps("t_abc")

    sql = " ".join(" ".join(x[0].split()) for x in pg.executed).lower()
    assert re.search(r"order by\s+step_index\s+desc", sql), (
        "진행 단계 창이 오래된 쪽에 고정된다(ORDER BY ... ASC LIMIT)")
    # 생략 수는 조밀한 step_index 에서 파생한다. `count(*) OVER ()` 로 세면 LIMIT 이 DB
    # 작업량을 줄이지 못해 매 tick 그 run 전체를 훑는다(codex 적대 리뷰 P2).
    assert "count(*) over ()" not in sql, (
        "창(LIMIT)보다 먼저 전체를 세고 있다 — tick 마다 full scan 이 된다")


def test_w2_no_truncation_reports_zero_omitted(monkeypatch):
    """상한 미만이면 생략은 0 이다(있지도 않은 절단을 고지하지 않는다)."""
    pg = _FakePg([_row(2), _row(1)])
    monkeypatch.setattr(ai_tools, "_pg", lambda: pg)

    steps, omitted = ai_tools._bridge_live_steps("t_abc")

    assert len(steps) == 2 and omitted == 0


def test_w2_omitted_is_derived_from_the_dense_step_index(monkeypatch):
    """창의 첫 단계가 41번이면 앞의 40건이 밀려난 것이다 — 별도 count 없이 알 수 있다."""
    pg = _FakePg([_row(43), _row(42), _row(41)])
    monkeypatch.setattr(ai_tools, "_pg", lambda: pg)

    steps, omitted = ai_tools._bridge_live_steps("t_abc")

    assert [s["step_index"] for s in steps] == [41, 42, 43]
    assert omitted == 40, f"생략 수를 잘못 셌다: {omitted}"


def test_w2_empty_run_is_safe(monkeypatch):
    pg = _FakePg([])
    monkeypatch.setattr(ai_tools, "_pg", lambda: pg)
    assert ai_tools._bridge_live_steps("t_abc") == ([], 0)


# ── W3 커넥션 위생 ───────────────────────────────────────────────────────────

def test_w3_connection_is_closed_after_each_read(monkeypatch):
    """tick(1초)마다 도는 조회다 — 열어 두면 idle-in-transaction 이 스트림 수만큼 쌓인다."""
    pg = _FakePg([_row(1)])
    monkeypatch.setattr(ai_tools, "_pg", lambda: pg)

    ai_tools._bridge_live_steps("t_abc")

    assert pg.closed, "진행 단계 조회가 커넥션을 닫지 않는다"


def test_w3_connection_is_closed_even_when_the_query_fails(monkeypatch):
    class _Boom(_FakePg):
        def cursor(self):
            raise RuntimeError("연결 끊김")

    pg = _Boom([])
    monkeypatch.setattr(ai_tools, "_pg", lambda: pg)

    assert ai_tools._bridge_live_steps("t_abc") == ([], 0)
    assert pg.closed, "실패 경로에서 커넥션이 샌다"


# ── 상태/스트림이 같은 필드를 낸다 ────────────────────────────────────────────

@pytest.mark.parametrize("claimed_by,expect_query", [(None, False), (7, True)])
def test_snapshot_carries_steps_omitted(monkeypatch, claimed_by, expect_query):
    """폴링(`bridge_status`)과 스트리밍이 갈리면 폴백이 곧 화면 회귀다."""
    calls: list[str] = []

    def _fake_live(task_id):
        calls.append(task_id)
        return ([{"step_index": 3}], 11)

    monkeypatch.setattr(ai_tools, "_bridge_live_steps", _fake_live)
    monkeypatch.setattr(ai_tools, "_bridge_phase",
                        lambda *a, **k: "working")
    monkeypatch.setattr(ai_tools, "_age_sec", lambda *_a: 0)
    monkeypatch.setattr(ai_tools._store, "account_has_live_token", lambda *a: True)
    monkeypatch.setattr(ai_tools, "account_is_listening", lambda *a: True)

    class _MyCur:
        def execute(self, *a):
            pass

        def fetchone(self):
            # 실물 SELECT 는 6열이다: Status · ClaimedBy · SubmittedAt · Delivered ·
            # ClaimedAt · ConversationId (뒤 둘은 TASK-20260901T140000 무진행 판정용).
            # 더블이 열 수를 줄이면 스냅샷이 IndexError 로 죽고, 그 죽음이 이 계약과
            # 무관한 실패로 나타난다 — 같은 부류를 이번 cycle 에 두 번 겪었다.
            return ("open", claimed_by, None, 0, None, "c1")

        def close(self):
            pass

    class _MyConn:
        def commit(self):
            pass

        def cursor(self):
            return _MyCur()

    snap = ai_tools._bridge_stream_snapshot(_MyConn(), "t_abc", 7)

    assert "steps_omitted" in snap, "절단 고지가 스냅샷에 실리지 않는다"
    assert bool(calls) is expect_query
    assert snap["steps_omitted"] == (11 if expect_query else 0)
