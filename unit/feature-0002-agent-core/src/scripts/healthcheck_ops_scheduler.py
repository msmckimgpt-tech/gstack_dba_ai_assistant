#!/usr/bin/env python3
"""feature-0039: ops-scheduler Docker HEALTHCHECK.

스케줄러 루프가 매 tick 갱신하는 heartbeat 파일의 신선도만 본다. 임계는
OPS_SCHED_HEARTBEAT_MAX_AGE_SEC(기본 120s) — tick 기본 20s 의 6배라 일시적 지연에
오탐하지 않는다.

**DB 를 보지 않는 이유**: 스케줄러의 책임은 "제 시각에 잡을 띄우는 것"이고 DB 가용성은
각 잡이 스스로 판정한다. DB 를 healthcheck 에 엮으면 DB 순단이 스케줄러 재시작으로
번져 그 창의 잡을 통째로 잃는다(워커 healthcheck 와 의도적으로 다른 설계).

Exit: 0 healthy / 1 unhealthy.
"""
import os
import sys
import time
from pathlib import Path

HEARTBEAT = Path(os.getenv("OPS_SCHED_HEARTBEAT_FILE", "/tmp/ops-scheduler.heartbeat"))
MAX_AGE = int(os.getenv("OPS_SCHED_HEARTBEAT_MAX_AGE_SEC", "120"))


def main() -> int:
    try:
        raw = HEARTBEAT.read_text(encoding="utf-8").strip()
        age = time.time() - float(raw)
    except (OSError, ValueError) as exc:
        print(f"heartbeat 판독 불가 ({HEARTBEAT}): {exc!r}", file=sys.stderr)
        return 1
    if age > MAX_AGE:
        print(f"heartbeat stale: {age:.0f}s > {MAX_AGE}s", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
