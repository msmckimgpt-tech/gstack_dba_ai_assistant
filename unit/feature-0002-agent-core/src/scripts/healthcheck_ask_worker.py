#!/usr/bin/env python3
"""TASK-0169: ask-worker Docker HEALTHCHECK.

ask-worker 는 HTTP endpoint 가 없으므로 agent_runtime.kv 의 ask_worker_last_cycle_at
heartbeat 신선도로 생존을 판정한다(insight-worker healthcheck 와 동형). heartbeat 가
ASK_WORKER_HEARTBEAT_MAX_AGE_SEC(기본 60s)보다 오래되면 exit 1 (unhealthy).

worker 는 메인 루프 매 tick 마다 liveness heartbeat 를 쓰므로(claim 유무 무관), job 이
없어도 살아있으면 heartbeat 가 신선하다. job heartbeat(ask_jobs.heartbeat_at)와는 별개 —
이건 worker 프로세스 자체의 생존 신호다.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")

THRESH = int(os.getenv("ASK_WORKER_HEARTBEAT_MAX_AGE_SEC", "60"))


def main() -> int:
    try:
        from modules.db import _pg_connect
        from shared.config import GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY
    except Exception:
        return 1
    conn = None
    try:
        conn = _pg_connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM agent_runtime.kv WHERE conversation_id = %s AND key = %s",
                (GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY),
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
