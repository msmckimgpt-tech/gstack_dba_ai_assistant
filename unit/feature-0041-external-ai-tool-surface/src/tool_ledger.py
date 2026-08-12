"""feature-0041 — 부하 원장 기록 · 상한 게이트 (codex REV-20260812-0001 P1: fail-closed).

## 왜 별도 원장인가

외부 AI 가 자기 계정 LLM 으로 추론하므로 `agent_runtime.llm_usage` 에는 행이 남지 않는다.
그 말은 **토큰 축에 얹힌 모든 한도**(`WebRoleTokenQuotas`/`WebAccountTokenQuotas`, feature-0032
백그라운드 예산)가 이 트래픽에 대해 항상 0 으로 읽혀 통과한다는 뜻이다. 비용은 우리가 안 내지만
부하는 우리 DB 가 내므로, 토큰이 아니라 **호출·행수·바이트** 를 세는 축이 필요하다.

## fail-closed 인 이유

원장이 곧 누적 상한의 원천이다. 기록 실패를 best-effort 로 두면 그 실패가 곧 상한 우회가 되고,
"모든 호출이 기록되고 상한 초과 시 429"(AC-6)와 정면으로 모순된다. 그래서 `record()` 는
예외를 삼키지 않으며, 호출측은 **결과를 반환하기 전에** 기록을 커밋하고 실패 시 5xx 를 낸다.

관측 전용 필드(지연·detail)의 결손만 무해하다 — 그것들은 상한에 들어가지 않는다.
"""
from __future__ import annotations

from typing import Any

# 상한 기본값. 운영 조절은 shared/runtime_settings 의 동명 키가 덮는다(콘솔 live).
DEFAULTS: dict[str, int] = {
    "AGENT_EXT_TOOL_RPM": 120,             # 계정·분당 호출
    "AGENT_EXT_TOOL_CONCURRENCY": 4,       # client 동시 실행
    "AGENT_EXT_TOOL_ROWS_PER_HOUR": 200_000,   # 계정·시간당 누적 반환 행수
    "AGENT_EXT_TOOL_BYTES_PER_HOUR": 64 * 1024 * 1024,
    "AGENT_EXT_TASK_OPEN_MAX": 20,         # 미제출 task 상한(소프트 강제)
}


class LedgerUnavailable(Exception):
    """원장에 쓸 수 없다 = 상한을 집행할 수 없다 → 호출을 거절해야 한다(5xx)."""


class RateLimited(Exception):
    def __init__(self, message: str, *, retry_after: int = 60, limit: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after
        self.limit = limit


def record(pg_conn, *, account_id: int, tool: str, outcome: str = "ok",
           client_id: str | None = None, task_id: str | None = None,
           conversation_id: str | None = None, datasource_key: str | None = None,
           schema_name: str | None = None, rows_returned: int = 0, bytes_out: int = 0,
           est_scanned_rows: int | None = None, latency_ms: int | None = None,
           detail: str | None = None) -> None:
    """원장 1행. **예외를 삼키지 않는다** — 실패는 호출측이 5xx 로 옮겨야 하는 사건이다."""
    if pg_conn is None:
        raise LedgerUnavailable("원장 연결이 없습니다.")
    sql = (
        "INSERT INTO agent_runtime.tool_call_usage "
        "(account_id, client_id, task_id, conversation_id, tool, datasource_key, schema_name, "
        " rows_returned, bytes_out, est_scanned_rows, latency_ms, outcome, detail) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    params = (int(account_id), _cap(client_id, 64), _cap(task_id, 64), _cap(conversation_id, 255),
              _cap(tool, 64), _cap(datasource_key, 96), _cap(schema_name, 255),
              max(0, int(rows_returned or 0)), max(0, int(bytes_out or 0)),
              est_scanned_rows, latency_ms, _cap(outcome, 16) or "ok", _cap(detail, 255))
    try:
        with pg_conn.cursor() as cur:
            cur.execute(sql, params)
    except Exception as exc:  # noqa: BLE001
        raise LedgerUnavailable(f"원장 기록 실패: {exc}") from exc


def check_limits(pg_conn, *, account_id: int, client_id: str | None,
                 limits: dict[str, int] | None = None) -> None:
    """호출 **전** 게이트. 초과면 RateLimited, 조회 불가면 LedgerUnavailable(둘 다 거절).

    조회 불가를 통과시키지 않는 이유는 record() 와 같다 — 집행할 수 없는 상한은 상한이 아니다.
    """
    conf = dict(DEFAULTS)
    conf.update(limits or {})
    if pg_conn is None:
        raise LedgerUnavailable("원장 연결이 없습니다.")
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM agent_runtime.tool_call_usage "
                "WHERE account_id = %s AND created_at > now() - interval '1 minute'",
                (int(account_id),))
            rpm = int((cur.fetchone() or [0])[0] or 0)
            cur.execute(
                "SELECT COALESCE(SUM(rows_returned),0), COALESCE(SUM(bytes_out),0) "
                "FROM agent_runtime.tool_call_usage "
                "WHERE account_id = %s AND created_at > now() - interval '1 hour'",
                (int(account_id),))
            row = cur.fetchone() or (0, 0)
            rows_h, bytes_h = int(row[0] or 0), int(row[1] or 0)
    except Exception as exc:  # noqa: BLE001
        raise LedgerUnavailable(f"상한 조회 실패: {exc}") from exc

    if rpm >= conf["AGENT_EXT_TOOL_RPM"]:
        raise RateLimited("분당 도구 호출 상한을 초과했습니다.", retry_after=60, limit="rpm")
    if rows_h >= conf["AGENT_EXT_TOOL_ROWS_PER_HOUR"]:
        raise RateLimited("시간당 반환 행수 상한을 초과했습니다.", retry_after=600, limit="rows")
    if bytes_h >= conf["AGENT_EXT_TOOL_BYTES_PER_HOUR"]:
        raise RateLimited("시간당 반환 바이트 상한을 초과했습니다.", retry_after=600, limit="bytes")


def _cap(value: Any, n: int) -> str | None:
    if value is None:
        return None
    s = str(value)
    return s[:n] if s else None
