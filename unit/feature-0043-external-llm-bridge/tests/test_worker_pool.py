"""동시 처리 슬롯이 **수요에 맞춰 늘고, 안 쓰면 줄어드는가** (사용자 요구 2026-08-28).

> "워커는 1개부터 시작하고, 현재 실행중인 워커 개수를 초과하는 동시 요청이 구성될 때 마다
>  동적으로 확장되도록 구성해주세요. 특정 시간 이상 사용되지 않는 오래된 워커부터 비활성화
>  하는 처리도 진행해주세요."

## 이 파일이 잠그는 것

    시작 1개      기본이 1이다 — 질문이 하나뿐인 대부분의 시간에 쓰지 않을 용량을 안 든다
    수요 확장      관측된 대기 질문 수만큼만, 상한까지
    오래된 것부터  회수 순서가 `last_used` 오름차순이다(LRU)
    최소 1개      0이 되면 다음 질문을 받을 창구가 사라지고 스스로 풀리지 않는다
    사용 중 보호   진행 중인 슬롯은 회수하지 않는다(오래 걸리는 조사의 답이 사라진다)
    폴링 금지      확장·축소에 타이머 스레드도 sleep 도 쓰지 않는다

**실제로 돌려서** 검증한다. 소스 문자열 검사는 "그 줄이 있는가" 만 보므로, LIFO/LRU 처럼
순서가 본질인 계약은 동작으로만 확인된다.
"""
from __future__ import annotations

import importlib.util
import pathlib
import threading

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
CANON = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


class FakeClock:
    """결정적 시계. 슬롯 시각이 락 안에서 만들어지므로 주입은 이 훅으로만 가능하다."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> "FakeClock":
        self.t += dt
        return self


def _load():
    spec = importlib.util.spec_from_file_location("_bridge_agent_pool", CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ba():
    return _load()


# ── 시작·확장 ────────────────────────────────────────────────────────────────


def test_starts_at_one_by_default(ba):
    """기본 시작 개수는 1 — 사용자 요구의 출발점이다."""
    assert ba._DEFAULT_WORKERS == 1, "종전 기본(2)이 남아 있다"
    pool = ba.WorkerPool(ba._DEFAULT_WORKERS, ba._DEFAULT_MAX_WORKERS,
                         ba._DEFAULT_WORKER_IDLE_SEC, 1000.0)
    assert pool.capacity == 1


def test_grows_to_observed_demand(ba):
    """대기 질문 수만큼 늘린다 — **관측된** 수요에만 반응한다(예측 확장 없음)."""
    pool = ba.WorkerPool(1, 8, 300.0, 1000.0)
    assert pool.grow_for(3) == 2, "3건 대기인데 1→3 으로 늘리지 않았다"
    assert pool.capacity == 3
    # 같은 수요가 다시 와도 더 늘지 않는다(수요 = 목표치이지 증분이 아니다).
    assert pool.grow_for(3) == 0
    assert pool.capacity == 3


def test_growth_stops_at_the_ceiling(ba):
    """상한을 넘지 않는다 — 넘으면 개인 머신에 수십 개가 뜨고 쿼터가 한 번에 소진된다."""
    pool = ba.WorkerPool(1, 4, 300.0, 1000.0)
    pool.grow_for(99)
    assert pool.capacity == 4, f"상한 4 를 넘었다: {pool.capacity}"


def test_demand_below_capacity_does_not_shrink(ba):
    """수요가 적다고 **즉시** 줄이지 않는다 — 축소는 시간(idle) 기준이지 순간 수요가 아니다.

    순간 수요로 줄이면 질문이 하나씩 번갈아 올 때 확장·축소를 반복한다(진동).
    """
    pool = ba.WorkerPool(1, 8, 300.0, 1000.0)
    pool.grow_for(4)
    pool.grow_for(1)
    assert pool.capacity == 4


# ── 사용·반납 ────────────────────────────────────────────────────────────────


def test_acquire_and_release_track_usage(ba):
    pool = ba.WorkerPool(2, 8, 300.0, 1000.0)
    a = pool.try_acquire()
    b = pool.try_acquire()
    assert a is not None and b is not None and a != b
    assert pool.in_use == 2 and pool.capacity == 2
    assert pool.try_acquire() is None, "없는 자리를 내줬다"
    pool.release(a)
    assert pool.in_use == 1
    assert pool.try_acquire() is not None


def test_acquire_prefers_the_most_recently_used_slot(ba):
    """유휴 슬롯 중 **가장 최근에 쓴 것**을 준다(LIFO).

    돌아가며 쓰면(FIFO) 모든 슬롯이 조금씩 최근이 되어 idle 임계를 넘는 것이 영영 생기지
    않는다 — 그러면 "오래된 워커부터 비활성화" 가 **작동하지 않는다**. 이 순서가 축소의 전제다.
    """
    clk = FakeClock()
    pool = ba.WorkerPool(3, 8, 300.0, clk.t, clk)
    ids = [pool.try_acquire() for _ in range(3)]
    pool.release(ids[0]); clk.advance(10)      # 가장 오래 전에 반납
    pool.release(ids[1]); clk.advance(10)
    pool.release(ids[2])                        # 가장 최근
    assert pool.try_acquire() == ids[2], "가장 오래된 것을 꺼냈다 — 축소가 무력해진다"


def test_release_of_an_unknown_slot_does_not_inflate_capacity(ba):
    """모르는 슬롯 반납이 용량을 부풀리지 않는다(조용한 증식은 재현이 어렵다)."""
    pool = ba.WorkerPool(1, 8, 300.0, 1000.0)
    before = pool.capacity
    pool.release(9999)
    assert pool.capacity == before


# ── 축소(회수) ───────────────────────────────────────────────────────────────


def test_reaps_only_after_the_idle_threshold(ba):
    """임계 **전에는** 회수하지 않는다."""
    clk = FakeClock()
    pool = ba.WorkerPool(1, 8, 300.0, clk.t, clk)
    pool.grow_for(3)
    assert pool.reap(1000.0 + 299.0) == 0, "임계 전에 회수했다"
    assert pool.capacity == 3
    assert pool.reap(1000.0 + 301.0) == 2, "임계를 넘었는데 회수하지 않았다"
    assert pool.capacity == 1


def test_reaps_oldest_first(ba):
    """**오래된 것부터** 회수한다 — 사용자 요구의 문면 그대로."""
    clk = FakeClock()
    pool = ba.WorkerPool(3, 8, 100.0, clk.t, clk)
    ids = [pool.try_acquire() for _ in range(3)]
    pool.release(ids[0]); clk.advance(100)     # 가장 오래
    pool.release(ids[1]); clk.advance(100)
    pool.release(ids[2])                        # 가장 최근
    # 1250 기준: ids[0](250초 유휴)·ids[1](150초)만 임계(100초) 초과, ids[2](50초)는 아니다.
    assert pool.reap(1250.0) == 2
    assert pool.try_acquire() == ids[2], "가장 최근 것이 아니라 오래된 것을 남겼다"


def test_never_reaps_below_one(ba):
    """0이 되면 다음 질문을 받을 창구가 사라지고, 그 상태는 스스로 풀리지 않는다.

    (확장은 수요를 봐야 하는데, 수요를 보려면 자리가 있어야 한다.)
    """
    pool = ba.WorkerPool(1, 8, 10.0, 1000.0)
    assert pool.reap(1_000_000.0) == 0
    assert pool.capacity == 1
    assert pool.try_acquire() is not None, "회수 뒤 자리가 없다"


def test_busy_slots_are_never_reaped(ba):
    """진행 중인 슬롯은 건드리지 않는다 — 오래 걸리는 조사의 답이 사라진다."""
    pool = ba.WorkerPool(1, 8, 10.0, 1000.0)
    pool.grow_for(3)
    busy = pool.try_acquire()
    assert pool.reap(1_000_000.0) == 2, "유휴 2개만 회수해야 한다"
    assert pool.in_use == 1 and pool.capacity == 1
    pool.release(busy)
    assert pool.capacity == 1


def test_reap_uses_last_used_not_creation_time(ba):
    """쓰고 반납한 슬롯은 **반납 시각**부터 다시 센다(생성 시각이 아니다)."""
    clk = FakeClock()
    pool = ba.WorkerPool(2, 8, 100.0, clk.t, clk)
    sid = pool.try_acquire()
    clk.advance(4000)
    pool.release(sid)          # 한참 뒤에 반납 = 방금 쓴 것
    assert pool.reap(5050.0) == 1, "오래된 나머지 하나만 회수해야 한다"
    assert pool.try_acquire() == sid, "방금 쓴 슬롯이 회수됐다"


# ── 자리가 없을 때 ───────────────────────────────────────────────────────────


def test_try_acquire_never_blocks(ba):
    """자리 취득은 **비차단**이다.

    블로킹으로 막으면 그동안 `wait_for_request` 를 부르지 못해 **취소 인지가 자리 반납에
    묶인다** — 워커가 다 찬 동안 사용자가 중단을 눌러도 러너가 모른다(feature-0043 이 이미
    한 번 겪은 결함). 짧은 간격으로 되돌아와 서버를 다시 읽는 편이 취소를 빨리 본다.
    """
    pool = ba.WorkerPool(1, 8, 300.0, 1000.0)
    pool.try_acquire()
    import time as _t
    t0 = _t.monotonic()
    assert pool.try_acquire() is None
    assert _t.monotonic() - t0 < 0.05, "자리가 없을 때 블로킹했다"


def test_runner_does_not_block_on_a_full_pool(ba):
    """러너가 포화 상태에서 **블로킹하지 않는다** — 서버를 계속 읽어야 취소를 본다."""
    src = CANON.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    loop = main[main.index("while True:"):]
    assert "wait_for_free" not in loop, (
        "자리를 기다리며 막는다 — 그동안 취소 통보를 받지 못한다")
    assert "sid = pool.try_acquire()" in loop and "if sid is None:" in loop, (
        "비차단 취득 경로가 없다")


# ── 러너 배선 ────────────────────────────────────────────────────────────────


def test_runner_wires_the_pool_into_the_wait_loop(ba):
    """풀이 맞더라도 루프가 쓰지 않으면 없는 것과 같다(배선 회귀 방어)."""
    src = CANON.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    assert "WorkerPool(" in main, "루프가 풀을 만들지 않는다"
    assert "threading.Semaphore(" not in src, "고정 세마포어가 남아 있다"
    loop = main[main.index("while True:"):]
    # ⚠ **서버를 먼저 읽고**, 자리는 그 뒤에 비차단으로 잡는다(2026-08-28 codex 리뷰 P1).
    #
    # 자리 확보를 앞에 두면 슬롯 1개가 작업 중일 때 대기 루프가 통째로 멈춰 **새 질문도 취소
    # 통보도 받지 못한다**. 취소는 이 응답 채널로만 오므로 중단을 눌러도 최대
    # `_AI_TIMEOUT_SEC` 동안 개인 계정 토큰이 탄다. 순서가 되돌아가면 그 회귀가 살아난다.
    assert loop.index('api.call("wait_for_request"') < loop.index("pool.try_acquire()"), (
        "자리를 잡은 뒤에 서버를 읽는다 — 포화 중 취소·새 질문을 놓친다")
    # 확장·회수가 실제로 호출되는가.
    assert "pool.grow_for(" in loop and "pool.reap(" in loop, "확장·회수를 부르지 않는다"
    # 회수는 매 라운드(long-poll 반환이 tick) — 별도 타이머 스레드를 만들지 않는다.
    assert "Timer(" not in src, "타이머 스레드를 쓴다 — long-poll 반환이 tick 이어야 한다"


def test_runner_dispatches_one_task_per_round_without_spinning(ba):
    """한 라운드에 한 건씩 집되, 자리가 없으면 **간격을 두고** 되돌아온다.

    다건 루프도 가능하지만 이 구조가 더 낫다: 자리가 있으면 다음 라운드가 곧바로 오고(서버가
    대기 질문을 즉시 돌려준다), 자리가 없으면 짧은 간격으로 되돌아와 **취소를 계속 확인한다**.
    """
    src = CANON.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    loop = main[main.index("while True:"):]
    assert "task_id = pending[0]" in loop, "대기 목록에서 집는 지점이 없다"
    guard = loop[loop.index("if sid is None:"):]
    assert "time.sleep(_DRAINING_RETRY_FLOOR_SEC)" in guard[:200], (
        "자리가 없을 때 간격 없이 되돌아온다 — 서버를 두드리는 hot loop 가 된다")


def test_pool_knobs_are_configurable(ba):
    """상한·유휴 임계를 사용자가 정할 수 있다 — 실질 한계(쿼터·런타임)는 우리가 모른다."""
    src = CANON.read_text(encoding="utf-8")
    for flag in ("--max-workers", "--worker-idle-sec"):
        assert flag in src, f"{flag} 이 없다"
    for env in ("BRIDGE_MAX_WORKERS", "BRIDGE_WORKER_IDLE_SEC"):
        assert env in src, f"{env} 이 없다"


def test_pool_uses_monotonic_time(ba):
    """벽시계가 아니라 `monotonic` 을 쓴다 — NTP 보정·서머타임에 시간이 뒤로 가면 회수가 멈춘다."""
    src = CANON.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    assert "time.monotonic()" in main, "단조 시계를 쓰지 않는다"
    assert "time.time()" not in main, "벽시계를 쓴다 — 뒤로 갈 수 있다"


# ══════════════════════════════════════════════════════════════════════════════
# codex 적대 리뷰(2026-08-28)가 **결정적 재현으로 증명한** 결함들. 전부 조치했고, 여기서
# 회귀를 잠근다. 이 블록이 없었다면 위 18건은 전부 green 인 채로 아래 5가지를 놓쳤다.
# ══════════════════════════════════════════════════════════════════════════════


def test_growth_counts_work_already_running(ba):
    """확장 목표는 **진행 중 + 대기**다 — 대기 수만 보면 과소 확장한다.

    codex 재현: capacity=4 · busy=3 · pending=3 → 총 동시 수요 6인데 `grow_to(3)` 은 하나도
    늘리지 않고, 결국 한 건만 시작되고 나머지 둘은 기존 작업이 끝날 때까지 기다렸다.
    """
    pool = ba.WorkerPool(4, 8, 300.0, 1000.0)
    for _ in range(3):
        pool.try_acquire()
    assert pool.in_use == 3 and pool.capacity == 4
    added = pool.grow_for(3)
    assert added == 2, f"진행 중 3 + 대기 3 = 6 이어야 하는데 {pool.capacity} 로 그쳤다"
    assert pool.capacity == 6
    # 대기 3건이 **모두** 자리를 얻는다(그것이 확장의 목적이다).
    assert [pool.try_acquire() is not None for _ in range(3)] == [True, True, True]


def test_release_order_survives_out_of_order_callers(ba):
    """반납 시각을 **락 안에서** 만든다 — 호출측이 먼저 시각을 재면 정렬이 뒤집힌다.

    codex 재현: `release(A, 200)` 뒤에 `release(B, 100)` 이 들어오면 `_free` 가 시각 역순이
    되고, `reap` 이 맨 앞(A)만 보고 "아직 임계 전" 이라 판단해 **뒤에 갇힌 B 를 영영 회수하지
    못한다**. 지속 트래픽에서 오래된 슬롯이 계속 살아남는 경로다.

    지금은 시각 인자를 받지 않으므로 이 역전이 **구조적으로 불가능**하다. 그 사실을 잠근다.
    """
    import inspect

    sig = inspect.signature(ba.WorkerPool.release)
    assert list(sig.parameters) == ["self", "sid"], (
        f"release 가 시각을 인자로 받는다{tuple(sig.parameters)} — 락 밖 시각은 정렬을 깬다")
    # 동작으로도 확인: 반납 순서대로 정렬이 유지되고 회수가 오래된 것부터 일어난다.
    clk = FakeClock()
    pool = ba.WorkerPool(2, 8, 50.0, clk.t, clk)
    a, b = pool.try_acquire(), pool.try_acquire()
    pool.release(a)
    clk.advance(100)
    pool.release(b)
    assert pool.reap(clk.t + 60) == 1, "먼저 반납된 슬롯이 회수되지 않았다"
    assert pool.try_acquire() == b, "최근 반납된 슬롯이 회수됐다"


def test_start_count_is_clamped_to_the_ceiling(ba):
    """`--workers` 가 상한을 밀어올리지 못한다.

    codex 재현: `--workers 100 --max-workers 8` 이 effective_max=100 · 시작 100 이 됐다.
    기존 `BRIDGE_WORKERS` 가 큰 머신에서 새 안전장치가 통째로 무력화되는 경로다.
    """
    src = CANON.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    assert "max(workers, int(args.max_workers" not in main, "시작값이 상한을 밀어올린다"
    assert "min(int(args.workers or 1), max_workers)" in main, "시작값을 상한으로 clamp 하지 않는다"
    # 풀 자신도 방어한다(호출측 실수와 무관하게).
    pool = ba.WorkerPool(100, 8, 300.0, 1000.0)
    assert pool.capacity == 8, f"상한 8 인데 {pool.capacity} 로 시작했다"


def test_claim_connection_failure_is_treated_as_failure(ba):
    """`claim_request` 의 **연결 실패**를 성공으로 읽지 않는다.

    codex 재현: `Api.call` 의 연결 실패 계약은 `{"_http": 0, "_failed": True}` 인데 claim 경로가
    `_http` 의 truthiness 만 봤다. `0` 은 falsy 라 **점유하지도 못한 작업**이 워커로 넘어갔고,
    그 task 는 서버에서 계속 open 이라 다음 대기가 같은 것을 즉시 돌려주며, `skip` 에도 안
    들어가 무한 반복이 된다. 대기·`--check` 경로는 이미 같은 술어를 쓰고 있었다.
    """
    src = CANON.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    claim = main[main.index('api.call("claim_request"'):]
    claim = claim[:claim.index("def _work(")]
    assert '_failed' in claim, "claim 실패 판정이 연결 실패(_http=0)를 놓친다"


def test_thread_start_failure_releases_the_slot(ba):
    """워커 스레드 시작이 실패해도 슬롯이 새지 않는다.

    codex 재현: 슬롯은 이미 busy 이고 서버 claim 도 끝난 뒤 `Thread.start()` 가
    `RuntimeError("can't start new thread")` 로 터지면, 반납이 워커 `finally` 안에만 있어
    **실행되지 않는다** — 예외가 main 까지 올라가 러너가 죽고, 그 task 는 lease 만료(30분)까지
    묶인 채 남는다.
    """
    src = CANON.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    seg = main[main.index("threading.Thread(target=_work"):]
    seg = seg[:seg.index("if args.once:")] if "if args.once:" in seg else seg[:600]
    assert "except" in seg and "pool.release(" in seg, (
        "스레드 시작 실패 시 슬롯을 반납하지 않는다 — 자리와 서버 점유가 함께 샌다")


# ══════════════════════════════════════════════════════════════════════════════
# 라이브 실측(2026-08-28)이 잡은 것: `--check` 가 **정상 연결에서도 항상 실패**했다.
# ══════════════════════════════════════════════════════════════════════════════


def test_check_probe_uses_a_tool_that_answers_immediately(ba):
    """연결 확인은 **즉시 답하는 도구**로 한다 — `wait_for_request` 로 하면 항상 실패한다.

    그 도구는 질문이 없으면 **55초를 보류하도록 설계**돼 있다(그것이 '폴링 아님' 의 실체다).
    `--check` 는 10초 timeout 으로 불렀으므로 **대기 질문이 없는 정상 상태에서 반드시 read
    timeout** 이 났고, 그때 "연결 실패" 를 출력했다. 온보딩 시점이 정확히 그 상태이고,
    지시문이 ③단계로 `--check` 를 권하므로 **외부 AI 는 거기서 멈춘다**.

    실측: `list_open_requests` 0.0초/200(연결 정상) · `wait_for_request` 10초 timeout ·
    같은 호출 90초로는 55.3초 뒤 `timed_out: true`.
    """
    src = CANON.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    head = main[:main.index("if args.check:")]
    assert 'api.call("list_open_requests"' in head, (
        "연결 확인이 즉시 답하는 도구를 쓰지 않는다")
    assert 'api.call("wait_for_request", {}, timeout=10' not in head, (
        "확인용 호출이 55초 보류 도구를 짧은 timeout 으로 부른다 — 정상 상태에서 항상 실패한다")


def test_check_probe_timeout_exceeds_a_normal_round_trip(ba):
    """확인용 timeout 이 정상 왕복보다 넉넉하다 — 느린 링크를 고장으로 오인하지 않는다."""
    src = CANON.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    line = next(l for l in main.split("\n") if 'api.call("list_open_requests"' in l)
    timeout = float(line.split("timeout=")[1].rstrip(")").strip())
    assert timeout >= 15.0, f"확인용 timeout 이 {timeout}s 로 빡빡하다"
