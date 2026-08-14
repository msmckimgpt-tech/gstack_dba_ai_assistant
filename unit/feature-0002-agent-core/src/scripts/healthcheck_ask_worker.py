#!/usr/bin/env python3
"""TASK-0169: ask-worker Docker HEALTHCHECK.

ask-worker 는 HTTP endpoint 가 없으므로 liveness 스탬프의 신선도로 생존을 판정한다.
스탬프가 ASK_WORKER_HEARTBEAT_MAX_AGE_SEC(기본 60s)보다 오래되면 exit 1 (unhealthy).

**판정 소스는 컨테이너 로컬 파일**(`AGENT_ASK_WORKER_ALIVE_FILE`, 기본 `/tmp/ask-worker.alive`).
feature-0020 surge drain 이 이 분리를 요구한다 — 종전의 KV `ask_worker_last_cycle_at` 은
**role 전역 단일 키**라 본체와 surge 가 공존하는 배포 창에서 두 컨테이너가 같은 값을 갱신했다:

  - 한쪽이 죽어도 다른 쪽이 키를 갱신하므로 **죽은 쪽도 healthy 로 보인다**(false-pass).
    배포 스파인은 이 신호로 "교체 성공" 을 판정하므로 오탐이 곧 잘못된 배포 완료 보고다.
  - drain 중인 본체는 신규 claim 을 멈춘 상태다. 그 상태는 정상(진행 중 run 을 마치는 중)인데
    갱신 주체가 아니면 **살아 있는 컨테이너가 unhealthy 로 보인다**(false-fail).

로컬 파일은 컨테이너 경계로 자연 격리되고, PG 왕복이 없어 DB blip 이 워커를 unhealthy 로
만들던 결합(라이브 오탐 이력)도 함께 끊긴다.

KV 폴백은 **구 이미지 호환**용으로만 남긴다 — 파일이 아직 없는 부팅 순간(워커가 첫 스탬프를
쓰기 전)과, 이 변경 이전 이미지로 롤백된 컨테이너를 덮는다. 파일이 존재하면 KV 는 보지 않는다
(공존 시 공유 키가 다시 판정에 끼어들면 위 false-pass 가 되살아난다).
"""
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/app")

THRESH = int(os.getenv("ASK_WORKER_HEARTBEAT_MAX_AGE_SEC", "60"))
ALIVE_FILE = (
    os.getenv("AGENT_ASK_WORKER_ALIVE_FILE", "/tmp/ask-worker.alive") or "/tmp/ask-worker.alive"
).strip()


def _from_alive_file() -> "float | None":
    """로컬 스탬프 age(초). 파일 없음 → None(폴백 신호)."""
    try:
        return max(0.0, time.time() - os.path.getmtime(ALIVE_FILE))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _from_kv() -> "float | None":
    """구 이미지 호환 폴백 — role 전역 KV heartbeat age(초)."""
    conn = None
    try:
        from shared.db import _pg_connect
        from shared.config import GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY
    except Exception:
        return None
    try:
        conn = _pg_connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM agent_runtime.kv WHERE conversation_id = %s AND key = %s",
                (GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY),
            )
            row = cur.fetchone()
        if not row or not row[0]:
            return None
        ts = str(row[0]).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def main() -> int:
    age = _from_alive_file()
    if age is None:
        age = _from_kv()
    if age is None:
        return 1
    return 0 if age <= THRESH else 1


if __name__ == "__main__":
    sys.exit(main())
