"""동시 처리 슬롯 (`WorkerPool`·`ActiveTasks`).

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import threading
import time

# ── 동시 처리 슬롯 ───────────────────────────────────────────────────────────


class WorkerPool:
    """동시 처리 슬롯을 **수요에 맞춰 늘리고, 쉬는 것부터 회수한다**(사용자 결정 2026-08-28).

    왜 `Semaphore` 가 아닌가: 세마포어는 크기를 바꿀 수 없다. 종전에는 고정 N 이었고, 그래서
    질문이 하나뿐인 대부분의 시간에도 N 개를 들고 있었다.

    ## 슬롯을 목록으로 두는 이유

    카운터 하나로도 개수는 셀 수 있다. 그런데 "**오래된** 슬롯부터 회수" 는 개수만으로는
    표현되지 않는다 — 어느 것이 얼마나 쉬었는지 알아야 한다. 그래서 슬롯마다 `last_used` 를
    들고, 회수는 그 순서로 한다.

    ## 왜 LIFO 로 꺼내는가

    유휴 슬롯 중 **가장 최근에 쓴 것**을 준다. 돌아가며 쓰면(FIFO) 전부 조금씩 최근이 되어
    idle 임계를 넘는 슬롯이 영영 생기지 않고, 그러면 축소가 작동하지 않는다. 한쪽만 계속 쓰면
    나머지는 자연히 오래되어 회수 대상이 된다.

    ## 시간

    `time.monotonic()` 을 쓴다(벽시계는 NTP 보정·서머타임에 뒤로 갈 수 있다). 슬롯은 생성
    시각으로 초기화한다 — 0 같은 센티넬로 두면 "프로세스 시작 직후" 가 곧 "아주 오래 쉼" 이
    되어 첫 라운드에 회수된다.
    """

    def __init__(self, start: int, maximum: int, idle_sec: float, now: float,
                 clock=time.monotonic) -> None:
        # `clock` 은 **테스트 훅**이다. 시각을 락 안에서 만들어야 정렬 불변식이 지켜지는데
        # (아래 `release` 참조), 그러면 호출측이 시각을 주입할 수 없어 회수 순서를 결정적으로
        # 검증할 방법이 사라진다. 시계 자체를 갈아끼우면 둘 다 만족한다.
        self._clock = clock
        self._cv = threading.Condition()
        self._max = max(1, int(maximum))
        self._idle = float(idle_sec)
        self._next_id = 1
        #: 유휴 슬롯 `(last_used, id)` — **last_used 오름차순**(앞이 가장 오래 쉰 것).
        self._free: list[tuple[float, int]] = []
        #: 사용 중 슬롯 id.
        self._busy: set[int] = set()
        for _ in range(max(1, min(int(start), self._max))):
            self._free.append((now, self._next_id))
            self._next_id += 1

    # ── 조회 ────────────────────────────────────────────────────────────────

    @property
    def capacity(self) -> int:
        with self._cv:
            return len(self._free) + len(self._busy)

    @property
    def in_use(self) -> int:
        with self._cv:
            return len(self._busy)

    # ── 사용 ────────────────────────────────────────────────────────────────

    def try_acquire(self) -> int | None:
        """유휴 슬롯 하나를 잡는다. 없으면 `None`(블로킹하지 않는다)."""
        with self._cv:
            if not self._free:
                return None
            _, sid = self._free.pop()      # 가장 최근에 쓴 것 — 위 'LIFO' 참조
            self._busy.add(sid)
            return sid

    def release(self, sid: int) -> None:
        """슬롯을 돌려준다. 그 사이 축소로 사라진 슬롯이면 조용히 버린다.

        ⚠ **반납 시각을 락 안에서 만든다.** 호출측이 `time.monotonic()` 을 먼저 계산해 넘기면,
        먼저 시간을 얻은 스레드가 늦게 락을 잡는 순간 `_free` 가 시각 역순으로 쌓인다. 그러면
        `reap` 이 맨 앞만 보고 "아직 임계 전" 이라 판단해 **뒤에 갇힌 오래된 슬롯을 영영 회수하지
        못한다**(codex 리뷰 P2). 정렬 불변식은 이 한 줄에 걸려 있다.

        모르는 슬롯을 버리는 이유: 반납이 조용히 용량을 부풀리는 버그는 재현이 어렵다.
        """
        with self._cv:
            if sid not in self._busy:
                return
            self._busy.discard(sid)
            self._free.append((self._clock(), sid))     # 락 안 — 단조 증가가 보장된다
            self._cv.notify_all()

    # ── 확장·축소 ───────────────────────────────────────────────────────────

    def grow_for(self, pending: int) -> int:
        """대기 질문 `pending` 건을 **지금 진행 중인 것과 함께** 소화할 만큼 늘린다(상한까지).

        ⚠ 목표는 `in_use + pending` 이다. 대기 수만 보면 **진행 중인 작업이 쓰는 자리를 빼고**
        세어 과소 확장한다 — capacity 4 · busy 3 · pending 3 이면 총수요가 6인데 `grow_to(3)` 은
        아무것도 늘리지 않고, 결국 한 건만 시작된다(codex 리뷰 P1).

        **관측된 수요에만** 반응한다 — 예측해서 미리 늘리지 않는다. 예측이 빗나가면 그 비용은
        사용자 계정의 쿼터로 나간다.
        """
        added = 0
        with self._cv:
            now = self._clock()                      # 락 안에서 — `release` 와 같은 이유
            target = min(len(self._busy) + int(pending), self._max)
            while len(self._free) + len(self._busy) < target:
                self._free.append((now, self._next_id))
                self._next_id += 1
                added += 1
            if added:
                self._cv.notify_all()
        return added

    def reap(self, now: float) -> int:
        """`idle_sec` 넘게 쉰 유휴 슬롯을 **오래된 것부터** 회수한다. 회수 개수를 돌려준다.

        **최소 1개는 남긴다.** 0이 되면 다음 질문을 받을 창구가 사라지고, 그 상태는 스스로
        풀리지 않는다(확장은 수요를 봐야 하는데 수요를 보려면 슬롯이 있어야 한다).

        사용 중인 슬롯은 건드리지 않는다 — 오래 걸리는 조사가 회수되면 그 답변이 사라진다.
        """
        removed = 0
        with self._cv:
            while self._free and (len(self._free) + len(self._busy)) > 1:
                last_used, sid = self._free[0]
                if now - last_used <= self._idle:
                    break                    # 정렬돼 있으므로 뒤는 볼 필요 없다
                self._free.pop(0)
                removed += 1
        return removed


class ActiveTasks:
    """지금 처리 중인 task 들. **'유휴' 를 관측 가능한 사실로 만든다**(TASK-20260828T150000).

    사용자 요구(2026-08-28): "로그아웃 + 모든 요청이 완료되어 유휴 상태면 러너도 안전하게
    종료되게." 그 판정을 하려면 "지금 몇 건이 돌고 있는가" 를 물을 수 있어야 하는데, 종전에는
    워커 자리(세마포어)만 있고 **셀 수 있는 것이 없었다** — 세마포어는 잔여 자리를 알려줄 뿐
    누가 무엇을 하고 있는지 말해 주지 않는다.

    id 를 들고 있는 이유: 유예가 지났을 때 그 작업들을 **취소로 전환**해야 하고(그래야 자식 AI
    프로세스가 죽어 개인 계정 토큰이 계속 타지 않는다), 취소 통로는 task_id 로 말한다.
    """

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._ids: set[str] = set()

    def enter(self, task_id: str) -> None:
        with self._cv:
            self._ids.add(str(task_id))

    def leave(self, task_id: str) -> None:
        with self._cv:
            self._ids.discard(str(task_id))
            self._cv.notify_all()

    def snapshot(self) -> list[str]:
        with self._cv:
            return sorted(self._ids)

    def count(self) -> int:
        with self._cv:
            return len(self._ids)

    def wait_idle(self, timeout: float) -> bool:
        """유휴가 될 때까지 기다린다. 유휴면 True, 유예가 먼저 끝나면 False.

        ⚠ 폴링하지 않는다 — 워커가 끝나면서 깨운다(`Condition`). 남은 시간을 매번 다시 계산하는
        이유: `wait` 는 깨어난 이유를 말해 주지 않으므로, 재계산 없이 반복하면 유예가 사실상
        무한이 된다(자주 깨는 워커가 있으면 영원히 기다린다).
        """
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._cv:
            while self._ids:
                remain = deadline - time.monotonic()
                if remain <= 0:
                    return False
                self._cv.wait(remain)
            return True
