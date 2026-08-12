"""feature-0041 — 부하 원장 fail-closed 계약 (codex P1 회귀 게이트 · AC-6).

이 파일이 지키는 한 문장: **기록할 수 없으면 호출도 없다.** 원장이 누적 상한의 원천이므로
기록 실패를 통과시키는 순간 상한이 우회된다.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "feature-0003-agent-web-ui", "src"))

import tool_ledger as tl  # noqa: E402


class _Cur:
    def __init__(self, owner, fail=False):
        self.owner, self.fail = owner, fail

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        if self.fail:
            raise RuntimeError("pg down")
        s = " ".join(str(sql).split())
        if s.startswith("INSERT INTO agent_runtime.tool_call_usage"):
            self.owner.rows.append(params)
        elif "COUNT(*)" in s:
            self.owner._result = (self.owner.rpm,)
        else:
            self.owner._result = (self.owner.rows_h, self.owner.bytes_h)

    def fetchone(self):
        return self.owner._result


class FakePg:
    def __init__(self, *, fail=False, rpm=0, rows_h=0, bytes_h=0):
        self.rows, self.fail = [], fail
        self.rpm, self.rows_h, self.bytes_h = rpm, rows_h, bytes_h
        self._result = None

    def cursor(self):
        return _Cur(self, self.fail)


def test_record_writes_row():
    pg = FakePg()
    tl.record(pg, account_id=7, tool="describe_table", task_id="t_1", rows_returned=12,
              bytes_out=340, client_id="mac_x", outcome="ok")
    assert len(pg.rows) == 1
    assert pg.rows[0][0] == 7 and pg.rows[0][4] == "describe_table"


def test_record_raises_when_ledger_unavailable():
    """★ 삼키면 상한 우회가 된다 — 호출측이 5xx 로 옮길 수 있게 반드시 올린다."""
    with pytest.raises(tl.LedgerUnavailable):
        tl.record(FakePg(fail=True), account_id=7, tool="x")
    with pytest.raises(tl.LedgerUnavailable):
        tl.record(None, account_id=7, tool="x")


def test_record_captures_denied_and_gated_outcomes():
    """거절이 원장에 안 남으면 남용 패턴을 사후 재구성할 수 없다."""
    pg = FakePg()
    tl.record(pg, account_id=7, tool="describe_table", outcome="denied", detail="scope")
    tl.record(pg, account_id=7, tool="describe_table", outcome="gated", detail="rpm")
    assert [r[11] for r in pg.rows] == ["denied", "gated"]


def test_check_limits_passes_under_threshold():
    tl.check_limits(FakePg(rpm=1, rows_h=10, bytes_h=10), account_id=7, client_id="c")


def test_check_limits_blocks_rpm():
    with pytest.raises(tl.RateLimited) as exc:
        tl.check_limits(FakePg(rpm=tl.DEFAULTS["AGENT_EXT_TOOL_RPM"]),
                        account_id=7, client_id="c")
    assert exc.value.limit == "rpm" and exc.value.retry_after == 60


def test_check_limits_blocks_row_budget():
    with pytest.raises(tl.RateLimited) as exc:
        tl.check_limits(FakePg(rows_h=tl.DEFAULTS["AGENT_EXT_TOOL_ROWS_PER_HOUR"]),
                        account_id=7, client_id="c")
    assert exc.value.limit == "rows"


def test_check_limits_blocks_byte_budget():
    with pytest.raises(tl.RateLimited) as exc:
        tl.check_limits(FakePg(bytes_h=tl.DEFAULTS["AGENT_EXT_TOOL_BYTES_PER_HOUR"]),
                        account_id=7, client_id="c")
    assert exc.value.limit == "bytes"


def test_check_limits_fails_closed_when_unreadable():
    """조회할 수 없는 상한은 상한이 아니다 — 통과가 아니라 거절."""
    with pytest.raises(tl.LedgerUnavailable):
        tl.check_limits(FakePg(fail=True), account_id=7, client_id="c")


def test_limits_are_overridable():
    with pytest.raises(tl.RateLimited):
        tl.check_limits(FakePg(rpm=3), account_id=7, client_id="c",
                        limits={"AGENT_EXT_TOOL_RPM": 3})


def test_long_values_are_capped_not_rejected():
    pg = FakePg()
    tl.record(pg, account_id=7, tool="x" * 200, detail="d" * 900)
    assert len(pg.rows[0][4]) == 64 and len(pg.rows[0][12]) == 255
