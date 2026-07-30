"""공유 자원 예산·격리 + 워커 자원 계측 (feature-0025 worker-resource-isolation, T0).

## 왜 필요한가 (근본 이슈 RI-0)

백그라운드 워커는 각자 독립 루프다 — `insight.run_insight_cycle`(노드 분석 배치),
`_semantic_cluster_loop`, `_product_classify_loop`, 관계 프로브, conn-health probe.
각 루프는 자기 동시성만 알고 **공유 자원(pgbouncer 풀·LLM 한도·소스 DB 커넥션)의 총량은
아무도 모른다.** 2026-07-14 §82 사건(무가드 graph-sync cron 누적 실행이 pgbouncer 풀을
소진해 서비스 전역 장애)의 해법이 그 cron 한 곳의 flock 이었던 이유가 이것이다 — 작업별
가드는 그 작업만 막고, 다른 루프는 계속 자원을 먹는다.

본 모듈은 자원을 **작업이 아니라 자원 종류 단위**로 예산화한다:

    with resource_budget.acquire("llm") as ok:
        if not ok:
            return          # fail-soft — 다음 tick 에 재시도 (백그라운드는 대기보다 스킵)
        ...LLM 호출...

## 설계 계약

- **기본값 = 현행 동등(byte-동치)**: 상한 기본값을 현행 최대 동시성 이상으로 둔다. 게이트가
  발동하지 않으므로 배포 시점 동작은 변하지 않는다. 운영자가 콘솔에서 조이면 격리가 발동한다
  (feature-0025 "기본 동시성 1 = 현행 직렬 byte-동치 opt-in" 규약 답습).
- **fail-soft 게이트 / fail-open 계측**: 획득 실패는 작업을 *스킵*한다(대기 아님 — 백그라운드
  루프가 락에 매달리면 tick 이 밀려 lease·heartbeat 가 깨진다). 계측 예외는 전부 삼킨다
  (계측이 작업을 죽이면 본말전도 — `shared/perf_counters` 규약 동형).
- **web 무영향**: 게이트는 호출측이 **명시**해야 발동한다. `shared/db` 의 커넥션 헬퍼에는
  게이트를 넣지 않는다 — 넣으면 web 요청 경로(같은 헬퍼 사용)가 백그라운드 예산에 걸린다.
  커넥션 헬퍼에는 **계측만** 붙는다(프로세스 전역 카운터 — 워커 컨테이너와 web 컨테이너는
  별 프로세스라 서로 오염되지 않는다).
- **프로세스 내 조율**: 한 프로세스(=한 컨테이너)의 스레드 사이에서만 유효하다. 프로세스 간
  (insight-worker ↔ ask-worker ↔ web-a/b) 총량은 본 T0 범위 밖이며 pgbouncer 풀 상한이
  backstop 이다. 프로세스 간 예산이 필요해지면 PG advisory lock 또는 토큰 테이블로 승격한다.
- **kill-switch 는 claim 단계에서도 게이트한다**: `AGENT_BACKGROUND_ANALYSIS_ENABLED=0` 은
  신규 트리거만 막는 것이 아니라 이미 적재된 잡의 claim 도 막아야 한다. change-reanalysis
  `cap==0` 이 "신규만 차단"이라 이미 큐에 있던 잡이 계속 LLM 을 소진했던 결함(적대 리뷰 C2)
  을 반복하지 않는다.
- **세마포어 대신 카운터**: `available()` 로 여유를 조회해야 호출측이 *잡을 실패시키지 않고*
  claim 수를 미리 조일 수 있다. `threading.Semaphore` 는 잔량 조회가 비공개(`_value`)라
  Lock+int 로 직접 관리한다.

## 자원 키

| 키 | 대상 | 상한 knob | 게이트 지점 |
|---|---|---|---|
| `llm` | 백그라운드 LLM 동시 호출 | `AGENT_WORKER_LLM_BUDGET` | 노드 분석·클러스터 라벨(직렬·병렬)·분류 제안 |
| `ds` | 소스 DB(운영 데이터소스) **동시 연결** | `AGENT_WORKER_DS_BUDGET` | 컬럼 introspect · 루틴 backfill(MSSQL/MySQL) |
| `task` | **동시 진행 백그라운드 작업 수** | `AGENT_WORKER_TASK_BUDGET` | 노드 분석 tick · 클러스터 pass · 분류 pass |

> ⚠ `task` 는 PG 커넥션 총량의 **근사**다. 정확한 PG 동시 점유를 강제하려면 커넥션 수명과 예산
> 수명을 묶어야 하는데, 워커 모듈은 `conn=None 이면 열고 주어지면 재사용` 패턴을 쓰고 close 는
> 호출측 `finally` 에 있어 광범위 리팩터가 필요하다. 대신 **작업 단위**로 상한을 둔다 — 작업 하나가
> 여는 PG 연결은 1~2개이므로 `task` 상한이 곧 PG 점유의 상한 근사다. 이름·설명을 그 의미로
> 정직하게 유지한다(`AGENT_WORKER_PG_BUDGET` 이라는 이름을 쓰지 않는 이유).

상한 변경은 live 반영된다 — 다음 `acquire()`/`available()` 이 새 상한으로 판정한다. 상한을
내리는 순간 이미 점유 중인 분은 그대로 유지되고(강제 회수 없음) 신규 획득만 막힌다.
"""
from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import Any, Iterator

_log = logging.getLogger("resource_budget")

#: 예산 대상 자원 키 — **실제 게이트가 배선된 자원만** 등재한다(ADR-0025-06: 게이트 없는 상한
#: knob 은 거짓 컨트롤이다 — 이 repo 가 `attachment.execute_sql_on.*` 를 같은 이유로 제거한 선례).
#:
#: `pg`(PG 커넥션 동시 점유)는 **여전히 등재하지 않는다** — 정확한 강제에 커넥션 수명·예산 수명
#: 결합이 필요해(위 `task` 주석) 근사 자원 `task` 로 대체했다. `incr_conn` 은 커넥션 **누적 생성
#: 횟수**만 센다(동시 점유가 아님).
RESOURCES = ("llm", "ds", "task")

#: 자원 키 → 상한 런타임 설정 키
_BUDGET_KNOB = {
    "llm": "AGENT_WORKER_LLM_BUDGET",
    "ds": "AGENT_WORKER_DS_BUDGET",
    "task": "AGENT_WORKER_TASK_BUDGET",
}

#: 런타임 설정 미가용(부트스트랩 창·PG 미가용) 시 폴백 상한 — 현행 최대 동시성 이상이라
#: 게이트가 발동하지 않는다(설정 조회 실패가 작업을 조이지 않게 — fail-open 방향).
_FALLBACK_LIMIT = {"llm": 16, "ds": 8, "task": 8}

_LOCK = threading.Lock()
_COND = threading.Condition(_LOCK)
#: 자원 키 → 현재 점유 수
_IN_USE: dict[str, int] = {}

#: 프로세스 전역 계측 (워커 컨텍스트 — perf_counters 의 요청-스코프가 no-op 인 공백을 메운다).
#:   acquired/rejected: 예산 게이트 통과·거절 수
#:   wait_ms_total: 획득까지 대기한 총 시간(비차단 획득이라 통상 0, 경합 관측용)
#:   held_ms_total: 자원 점유 총 시간 — 자원별 실효 사용량(동시성 × 시간)의 근사
#:   peak: 관측된 최대 동시 점유 — 상한을 얼마로 조여야 하는지의 1차 근거
_COUNTERS_LOCK = threading.Lock()
_COUNTERS: dict[str, dict[str, float]] = {}

#: 커넥션 수립 계측 (`shared/db` 훅) — 프로세스 전역. 요청-스코프(perf_counters)와 직교.
#: `ds_conns` = 소스 DB(운영 데이터소스) 연결 수립 — MySQL/MSSQL 양 엔진 모두 배선(codex 재검증
#: NEW P2: 증분되지 않는 키를 노출하면 '0 = 부하 없음' 으로 오독된다).
_CONN_KEYS = ("pg_conns", "pg_ro_conns", "ds_conns")

#: timeout>0 대기 시 재평가 주기(초).
#: ⚠ 이 값이 곧 상한-상향 반영 지연은 **아니다** — `runtime_settings` 는 override 를 TTL 캐시로
#: 읽으므로(`_live_overrides`) 실효 반영 지연은 `max(_WAIT_POLL_SEC, 설정 캐시 TTL)` 이다(codex
#: 재검증 P2-a). 폴링은 "깨울 이벤트가 없어 timeout 까지 잠드는" 것만 막는다. 현재 모든 호출자가
#: 비차단(timeout=0)이라 실질 영향은 없고, 캐시를 우회하면 acquire 마다 스냅샷을 읽어 hot path
#: 비용이 커지므로 우회하지 않는다.
_WAIT_POLL_SEC = 0.5


def _counters_for(key: str) -> dict[str, float]:
    row = _COUNTERS.get(key)
    if row is None:
        row = {"acquired": 0.0, "rejected": 0.0, "wait_ms_total": 0.0,
               "held_ms_total": 0.0, "peak": 0.0}
        _COUNTERS[key] = row
    return row


def limit_for(key: str) -> int:
    """자원 상한(런타임 override 반영). 조회 실패 시 폴백(게이트 미발동 방향)."""
    knob = _BUDGET_KNOB.get(key)
    fallback = int(_FALLBACK_LIMIT.get(key, 16))
    if not knob:
        return fallback
    try:
        from shared import runtime_settings as _rts
        return max(1, int(_rts.get_int(knob)))
    except Exception:
        return fallback


def available(key: str) -> int:
    """자원 `key` 의 현재 여유(상한 − 점유). 미등록 키는 큰 수(게이트 없음).

    호출측이 claim 수를 미리 조이는 데 쓴다 — 잡을 claim 한 뒤 예산에서 거절하면 그 잡이
    실패·재시도 상태를 오가므로, **claim 전에 여유만큼만 집어오는** 편이 깔끔하다.
    경합으로 실제 획득 시점 여유가 달라질 수 있으므로 `acquire()` 가 최종 게이트다.
    """
    if key not in RESOURCES:
        return 1 << 20
    limit = limit_for(key)
    with _LOCK:
        return max(0, limit - int(_IN_USE.get(key, 0)))


@contextlib.contextmanager
def acquire(key: str, *, timeout: float = 0.0) -> Iterator[bool]:
    """자원 `key` 예산을 획득한다. **획득 성공 여부를 yield** 한다 (fail-soft).

    호출측 계약:

        with acquire("llm") as ok:
            if not ok:
                return            # 스킵 — 다음 tick 에 재시도
            ...작업...

    `timeout=0.0`(기본)은 **비차단** — 여유가 없으면 즉시 False. 백그라운드 루프가 락에
    매달려 tick 이 밀리는 것(lease·heartbeat 깨짐)을 원천 차단한다. 짧은 대기가 유의미한
    지점은 호출측이 `timeout` 을 명시한다.

    미등록 자원 키는 게이트 없이 True — 오타가 작업을 조용히 막지 않게 한다(fail-open, 1회 warn).
    """
    if key not in RESOURCES:
        _warn_unknown_resource(key)
        yield True
        return
    t0 = time.perf_counter()
    got = False
    try:
        deadline = (t0 + timeout) if (timeout and timeout > 0) else None
        with _COND:
            while True:
                limit = limit_for(key)
                cur = int(_IN_USE.get(key, 0))
                if cur < limit:
                    _IN_USE[key] = cur + 1
                    got = True
                    break
                if deadline is None:
                    break
                remain = deadline - time.perf_counter()
                if remain <= 0:
                    break
                # notify() 는 release 시점에만 온다 — 상한을 **live 로 올린** 경우에는 깨울 이벤트가
                # 없어 대기자가 timeout 까지 잠든다(codex P2). 폴링 상한을 둬 상한 상향도 최대
                # _WAIT_POLL_SEC 안에 반영된다.
                _COND.wait(min(remain, _WAIT_POLL_SEC))
    except Exception as exc:      # 예산 관리 자체 실패는 관측 불가 영역 — fail-open
        _log.debug("resource_budget acquire 실패(무시) key=%s err=%r", key, exc)
        yield True
        return
    wait_ms = (time.perf_counter() - t0) * 1000.0
    _record(key, acquired=bool(got), wait_ms=wait_ms,
            in_use=(int(_IN_USE.get(key, 0)) if got else None))
    if not got:
        yield False
        return
    held_t0 = time.perf_counter()
    try:
        yield True
    finally:
        _record(key, held_ms=(time.perf_counter() - held_t0) * 1000.0)
        try:
            with _COND:
                _IN_USE[key] = max(0, int(_IN_USE.get(key, 0)) - 1)
                _COND.notify()
        except Exception:
            pass


_UNKNOWN_WARNED: set[str] = set()


def _warn_unknown_resource(key: str) -> None:
    if key in _UNKNOWN_WARNED:
        return
    _UNKNOWN_WARNED.add(key)
    _log.warning("resource_budget: 미등록 자원 키 %r — 게이트 없이 통과(fail-open). "
                 "RESOURCES 에 추가하거나 호출측 오타를 확인하세요.", key)


def _record(key: str, *, acquired: bool | None = None, wait_ms: float = 0.0,
            held_ms: float = 0.0, in_use: int | None = None) -> None:
    """계측 누적. **어떤 예외도 전파하지 않는다**(fail-open)."""
    try:
        with _COUNTERS_LOCK:
            row = _counters_for(key)
            if acquired is True:
                row["acquired"] += 1.0
            elif acquired is False:
                row["rejected"] += 1.0
            if wait_ms:
                row["wait_ms_total"] += float(wait_ms)
            if held_ms:
                row["held_ms_total"] += float(held_ms)
            if in_use is not None and float(in_use) > row.get("peak", 0.0):
                row["peak"] = float(in_use)
    except Exception:
        pass


def incr_conn(key: str, n: int = 1) -> None:
    """커넥션 수립 카운터(`shared/db` 훅). 프로세스 전역 — 요청-스코프와 직교. fail-open."""
    if key not in _CONN_KEYS:
        return
    try:
        with _COUNTERS_LOCK:
            row = _counters_for("conns")
            row[key] = float(row.get(key, 0.0)) + float(n)
    except Exception:
        pass


def background_enabled() -> bool:
    """백그라운드 분석 전역 kill-switch. 0 이면 모든 분석 루프가 진입 즉시 중단해야 한다.

    **claim 단계에서도 이 함수를 확인한다** — 신규 트리거만 막고 적재된 잡을 계속 처리하면
    "즉시 정지" 라는 운영 기대와 어긋난다(change-reanalysis cap==0 결함 반복 금지).
    설정 조회 실패 시 **활성**으로 본다(fail-open) — 설정 장애가 워커를 통째로 멈추면
    복구 수단이 재배포뿐이 된다.
    """
    try:
        from shared import runtime_settings as _rts
        return bool(int(_rts.get_int("AGENT_BACKGROUND_ANALYSIS_ENABLED")))
    except Exception:
        return True


def snapshot() -> dict[str, Any]:
    """계측 스냅샷 (프로세스 기동 이후 누적). 조회·flush 용. 부작용 없음."""
    out: dict[str, Any] = {"resources": {}, "conns": {}}
    try:
        with _COUNTERS_LOCK:
            rows = {k: dict(v) for k, v in _COUNTERS.items()}
        with _LOCK:
            in_use = dict(_IN_USE)
    except Exception:
        return out
    for key in RESOURCES:
        row = rows.get(key) or {}
        acquired = int(row.get("acquired", 0.0))
        rejected = int(row.get("rejected", 0.0))
        entry = {
            "limit": limit_for(key),
            "in_use": int(in_use.get(key, 0)),
            "peak": int(row.get("peak", 0.0)),
            "acquired": acquired,
            "rejected": rejected,
            "wait_ms_total": round(float(row.get("wait_ms_total", 0.0)), 1),
            "held_ms_total": round(float(row.get("held_ms_total", 0.0)), 1),
        }
        # 거절률 — 상한이 실제 병목인지 판정하는 1차 신호(0 이면 게이트 미발동 = 현행 동등).
        total = acquired + rejected
        entry["reject_ratio"] = round(rejected / total, 4) if total else 0.0
        out["resources"][key] = entry
    conns = rows.get("conns") or {}
    for ck in _CONN_KEYS:
        out["conns"][ck] = int(conns.get(ck, 0.0))
    out["background_enabled"] = background_enabled()
    return out


#: 워커 자원 스냅샷 flush 디렉토리 (컨테이너 `/shared` = 호스트 `artifacts/shared`).
#: 왜 파일인가: 카운터는 **워커 프로세스 메모리**에 있고 조회자(호스트 CLI·web 콘솔)는 다른
#: 프로세스다. PG 테이블로 올리려면 마이그레이션·flush 주기·조회 라우트가 붙는데, 관측
#: 1차 목적(상한을 조여도 되는지 판단)에는 주기 파일 스냅샷이면 충분하다 —
#: `bin/perf-snapshot.sh` 가 다른 성능 신호와 함께 수집한다(사용자 결정 2026-07-30).
_SNAPSHOT_DIR_ENV = "AGENT_WORKER_RESOURCE_SNAPSHOT_DIR"
_SNAPSHOT_DIR_DEFAULT = "/shared/perf"


#: 죽은 워커의 스냅샷 회수 임계(초). 이 시간 넘게 갱신되지 않은 파일은 그 워커가 사라진 것으로
#: 보고 flush 시 정리한다 — 안 하면 목록이 유령 워커로 채워지고 표시 상한을 잠식한다.
#:
#: **7일**을 쓰는 이유(codex P2): 워커가 정당하게 오래 멈출 수 있다(장기 유지보수·비활성 배치).
#: 24h 는 그런 워커를 죽은 것으로 오판하기 쉽다. 회수가 늦어도 손해는 목록에 유령 1줄이 더 남는
#: 것뿐이고, 반대로 오판 삭제는 살아 있는 워커를 콘솔에서 지운다 — 비대칭이라 보수적으로 잡는다.
#: 삭제되더라도 그 워커의 다음 flush 가 파일을 **재생성**하므로 자기복구된다(데이터 손실 없음).
#:
#: mtime 시계: 모든 워커가 **같은 호스트 볼륨**(`artifacts/shared` bind mount)에 쓰므로 mtime 은
#: 단일 호스트 파일시스템 시계다 — 컨테이너 간 clock skew 가 판정에 끼어들지 않는다.
_SNAPSHOT_REAP_SEC = 7 * 24 * 3600


def _worker_role_default() -> str:
    """스냅샷 파일명에 쓸 **안정 role**.

    ⚠ HOSTNAME 을 쓰면 컨테이너를 재생성할 때마다 파일명이 바뀌어 **재배포마다 스냅샷이 누적**된다
    (라이브 실측: 3개 누적 — 유령 워커가 콘솔에 stale 로 표시되고, 표시 상한에 도달하면 현행 워커가
    밀려난다). compose 가 이미 주입하는 `AGENT_SESSION`(`insight_worker`/`ask_worker`)이 재생성에
    불변인 안정 식별자라 그것을 1순위로 쓴다 — compose 변경 없이 파일명이 고정된다.
    """
    import os
    for env in ("AGENT_WORKER_ROLE", "AGENT_SESSION", "HOSTNAME"):
        v = str(os.getenv(env) or "").strip()
        if v:
            return v
    return "worker"


def _reap_stale_snapshots(base: str, keep: str) -> int:
    """`_SNAPSHOT_REAP_SEC` 넘게 갱신되지 않은 스냅샷 파일 정리. 반환: 지운 수(fail-open).

    자기 파일(`keep`)은 절대 지우지 않는다. 대상은 우리 워커가 쓴 `worker-resources-*.json` 뿐이며
    symlink 는 건드리지 않는다(공유 볼륨이라 타 주체가 만든 링크를 따라가지 않는다).
    """
    import glob
    import os
    import time
    removed = 0
    try:
        now = time.time()
        for path in glob.glob(os.path.join(base, "worker-resources-*.json")):
            try:
                if os.path.abspath(path) == os.path.abspath(keep) or os.path.islink(path):
                    continue
                if (now - os.stat(path).st_mtime) <= _SNAPSHOT_REAP_SEC:
                    continue
                # TOCTOU 완화(codex P2): stat 과 unlink 사이에 그 워커가 되살아나 `os.replace` 로
                #   최신 파일을 놓을 수 있다. 삭제 직전 mtime 을 **다시 확인**해 창을 좁힌다.
                #   완전 제거는 불가하지만(파일시스템 원자 조건부 삭제 없음) 삭제되더라도 다음
                #   flush 가 재생성하므로 최악이 "한 주기 표시 누락" 이다.
                if (time.time() - os.stat(path).st_mtime) <= _SNAPSHOT_REAP_SEC:
                    continue
                os.unlink(path)
                removed += 1
            except Exception:
                continue
    except Exception:
        pass
    return removed


def flush_snapshot(role: str = "", *, directory: str = "") -> str:
    """자원 스냅샷을 JSON 파일로 원자 write. 반환: 기록한 경로(실패 시 빈 문자열).

    파일명 = `worker-resources-<role>.json`. role 미지정 시 `_worker_role_default()` —
    **안정 식별자**(`AGENT_SESSION`)를 우선 써서 재배포에도 파일명이 불변이다.
    **fail-open**: 디렉토리 부재·권한 오류 등 어떤 예외도 삼킨다(계측 flush 가 워커 tick 을
    죽이면 본말전도). 같은 파일을 매 주기 덮어쓴다 — 누적 이력이 아니라 *현재 상태* 관측용이며,
    시계열이 필요하면 호출측(perf-snapshot)이 타임스탬프 디렉토리에 복사한다.
    쓰기 후 오래 갱신되지 않은 남의 스냅샷(죽은 워커)을 정리한다.
    """
    import json
    import os
    import tempfile
    try:
        base = str(directory or os.getenv(_SNAPSHOT_DIR_ENV) or _SNAPSHOT_DIR_DEFAULT)
        name = str(role or _worker_role_default()).strip() or "worker"
        # 경로 조립 안전: role 은 컨테이너 이름 유래라 구분자가 섞이면 디렉토리를 벗어날 수 있다.
        name = "".join(ch if (ch.isalnum() or ch in "._-") else "-" for ch in name)[:64]
        os.makedirs(base, exist_ok=True)
        target = os.path.join(base, f"worker-resources-{name}.json")
        payload = dict(snapshot())
        payload["flushed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload["role"] = name
        fd, tmp = tempfile.mkstemp(dir=base, prefix=".wr-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, target)          # 원자 교체 — 반쯤 쓰인 JSON 을 읽히지 않게
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
        _reap_stale_snapshots(base, target)   # 죽은 워커 스냅샷 회수(자기 것은 보존)
        return target
    except Exception as exc:
        _log.debug("resource_budget flush_snapshot 실패(무시) err=%r", exc)
        return ""


def _reset_for_test() -> None:
    """테스트 전용 — 점유·카운터 초기화."""
    with _LOCK:
        _IN_USE.clear()
    with _COUNTERS_LOCK:
        _COUNTERS.clear()
    _UNKNOWN_WARNED.clear()
