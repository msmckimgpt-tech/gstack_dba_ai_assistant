"""취소 원장 (`CancelRegistry`).

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import threading

# ── 취소 원장 ────────────────────────────────────────────────────────────────


class CancelRegistry:
    """서버가 알려준 **취소된 task** 를 워커에게 전달하는 통로.

    대기 스레드(`wait_for_request`)와 워커 스레드가 함께 읽고 쓰므로 락으로 감싼다.
    락 없이 `set` 을 공유해도 CPython 에서는 대개 동작하지만, "대개" 로 두면 취소가 가끔
    안 먹는 버그가 되고 그건 재현이 거의 불가능하다.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids: set[str] = set()

    def add_many(self, task_ids) -> list[str]:
        """새로 취소된 것만 골라 기록하고 그 목록을 돌려준다(로그용)."""
        fresh: list[str] = []
        with self._lock:
            for raw in task_ids or []:
                tid = str(raw or "")
                if tid and tid not in self._ids:
                    self._ids.add(tid)
                    fresh.append(tid)
        return fresh

    def is_canceled(self, task_id: str) -> bool:
        with self._lock:
            return str(task_id) in self._ids

    def forget(self, task_id: str) -> None:
        """처리를 마친 task 는 원장에서 뺀다 — 무한히 자라지 않게."""
        with self._lock:
            self._ids.discard(str(task_id))
