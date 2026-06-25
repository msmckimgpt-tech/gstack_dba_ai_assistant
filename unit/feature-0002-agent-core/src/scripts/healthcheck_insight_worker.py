#!/usr/bin/env python3
"""TASK-0130 (#4/#5): insight-worker Docker HEALTHCHECK.

워커는 HTTP endpoint 가 없으므로 agent_runtime.kv 의 insight_worker_last_cycle_at
heartbeat 신선도로 생존을 판정한다. heartbeat 가 INSIGHT_HEARTBEAT_MAX_AGE_SEC(기본 180s)
보다 오래되면 exit 1 (unhealthy) — 이전엔 advisory-lock 버그로 매 사이클 skip_locked 라
heartbeat 가 24h+ 동결돼도 Docker 는 healthy 로 표기했다 (TASK-0129 가 lock 을, 본 체크가
가시성을 제공).
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")

THRESH = int(os.getenv("INSIGHT_HEARTBEAT_MAX_AGE_SEC", "180"))


def main() -> int:
    try:
        from shared.db import _pg_connect
        from shared.config import GLOBAL_CONVERSATION_ID
    except Exception:
        return 1
    conn = None
    try:
        conn = _pg_connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM agent_runtime.kv WHERE conversation_id = %s AND key = %s",
                (GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at"),
            )
            row = cur.fetchone()
        if not row or not row[0]:
            return 1
        ts = str(row[0]).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - dt).total_seconds()
        return 0 if age <= THRESH else 1
    except Exception:
        return 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
