"""Per-datasource connection health monitor (TASK: conn-health-monitor).

목적: 한 datasource 의 연결 불안정이 다른 정상 datasource 의 요청을 지연시키는 것을 근본
차단한다. 연결 가능 여부를 **요청과 분리해 백그라운드에서 미리 유지**하고, 소비자(agent
런타임·관리 콘솔)는 미리 계산된 상태를 **즉시 읽기만** 한다 — 살아있는 연결을 직접 안 기다림.

probe 2단 (REV-20260612 적대 리뷰 B1 흡수 — "TCP 성공 ≠ DB 연결 가능"):
  1) **TCP 선검사** (raw socket, ~100ms): 서버 도달성 빠른 판정. 실패 시 즉시 unstable
     (드라이버 connect 의 긴 timeout 을 낭비하지 않음 — 죽은 서버 fast-fail).
  2) **실제 DB connect + `SELECT 1`** (db.probe_datasource, 적응형 1s→×2→10s): TCP 는
     열렸지만 DB 가 max_connections 소진·재시작·인증 실패 등으로 **실제 연결이 안 되는**
     경우를 잡는다. 이게 직렬 worker 점유의 진짜 원인이라 TCP 만으로는 부족.
  성공해야만 healthy. 둘 중 하나라도 실패면 unstable. recheck 간격은 실패에 따라 backoff.

foreground 피드백: 실제 데이터 연결 결과를 record_foreground_result 로 받아 즉시 반영
  (연결 수립 실패 → unstable 로 다음 요청 fast-fail, 성공 → healthy). 복구 판정은 background
  실제 DB probe 가 담당 → foreground half-open trial 불요(thundering-herd 함정 제거).

gate(should_fast_fail): unstable 이면 즉시 fast-fail. 모니터가 도는 한 복구는 background 가
  담당하므로 unstable 을 그대로 신뢰한다. **모니터가 정지**(start 실패/예외)했다고 추정되면
  (monitor_running()=False + status stale) unknown 으로 강등해 1회 시도를 허용(영구 차단 방지).

비밀번호 취급: 실제 DB probe 는 자격증명이 필요하므로 모니터 내부 `_targets`(provider 가 매
  refresh 마다 채우는 전체 ds dict)에만 보유한다. **상태맵 `_STATE`·`snapshot`·로그에는 좌표/
  비밀번호를 절대 넣지 않는다**(status/elapsed/errno 만). 프로세스는 이미 같은 자격증명을 보유.

프로세스별 in-memory: ask-worker(직렬 병목 1차 수혜)·web(admin 표시)·insight-worker 가 각자
  모니터를 띄운다(공유 PG 불요 — 각자 동일 현실을 probe). daemon 스레드 — 프로세스 종료 안전.
"""

from __future__ import annotations

import ipaddress
import logging
import queue
import socket
import threading
import time
from collections import deque
from typing import Any, Callable, Optional

from .config import *  # noqa: F401,F403 — AGENT_CONN_* 등

_log = logging.getLogger("agent_core.conn_health")

HEALTHY = "healthy"    # 연결 성공 + 빠름(elapsed < SLOW) — 초록("연결 정상")
UNSTABLE = "unstable"  # 연결은 되지만 느림(elapsed >= SLOW) 또는 1회성 blip — 빨강("연결 불안정")
DOWN = "down"          # 연결 자체가 연속 실패(도달 불가) — 회색("연결 끊김")
UNKNOWN = "unknown"    # probe 전 — 중립("상태 확인 중")

# scope_key -> entry(좌표/비번 없음): {status, fails, last_elapsed_ms, avg_elapsed_ms, last_error,
#                                     checked_at, next_due, source, host, port, engine, label}
_STATE: dict[str, dict[str, Any]] = {}
# scope_key -> 성공 background DB probe elapsed_ms 표본 window(deque, maxlen=AGENT_CONN_AVG_WINDOW).
# _STATE 와 분리 — 원시 표본은 여기에만 두고 _STATE 에는 산술평균(avg_elapsed_ms)만 둔다(snapshot/
# status 좌표·표본 비노출 불변식 보존). 접근은 항상 _LOCK 안(_apply_result / _prune_state / _reset_state).
_SAMPLES: dict[str, "deque[float]"] = {}
_LOCK = threading.RLock()


def _now() -> float:
    return time.time()


def _tcp_timeout_sec() -> float:
    """TCP 선검사 timeout(초). conn-tristate: 구 100ms(BASE)는 다른 리전 datasource 의 핸드셰이크
    RTT 를 못 견뎌 **연결 가능한 느린 서버까지 죽은 것으로 오판**했다. AGENT_CONN_TCP_TIMEOUT_MS
    (기본 2000ms)로 현실화 — 진짜 죽은 서버(ECONNREFUSED)는 timeout 무관 즉답이라 fast-fail 은 유지,
    원거리 RTT/SYN-drop 만 더 기다려준다."""
    return max(0.02, float(AGENT_CONN_TCP_TIMEOUT_MS) / 1000.0)


def classify(ok: bool, elapsed_ms: "float | None", fails: int) -> str:
    """연결 probe 결과 → 3단계 상태 단일 분류(백그라운드 probe·foreground 피드백·/test 공용).

    - ok=True  + elapsed < SLOW  → HEALTHY (연결 정상, 초록)
    - ok=True  + elapsed >= SLOW → UNSTABLE(연결 불안정 — 느림, 빨강)
    - ok=False + fails >= DOWN_AFTER_FAILS → DOWN (연결 끊김 — 반복 실패, 회색)
    - ok=False + fails <  DOWN_AFTER_FAILS → UNSTABLE(연결 불안정 — 1회성 blip, 빨강)

    elapsed_ms=None(예: foreground 성공은 elapsed 미측정)이면 느림 판정 불가 → 성공은 HEALTHY 로
    둔다(background probe 가 elapsed 를 측정해 느림을 권위적으로 확정)."""
    if ok:
        if elapsed_ms is not None and float(elapsed_ms) >= float(AGENT_CONN_SLOW_MS):
            return UNSTABLE
        return HEALTHY
    if int(fails) >= max(1, int(AGENT_CONN_DOWN_AFTER_FAILS)):
        return DOWN
    return UNSTABLE


def _driver_timeout_sec(fails: int) -> int:
    """실제 DB probe(연결+SELECT 1) timeout(초, 정수). 드라이버 connect_timeout 은 정수초.
    base → 실패마다 ×2 → cap(AGENT_CONN_PROBE_TIMEOUT_MS_MAX/1000, 기본 10s).

    conn-tristate: base 를 구 1s 고정에서 **느림 임계(SLOW)의 3배**(올림)로 키운다. 구 1s 는
    SLOW(1000ms)를 초과하는 연결(예: 다른 리전 1745ms)을 첫 probe 에서 timeout 시켜 unstable(느림)
    대신 blip 실패로 떨어뜨렸다. base ≥ SLOW×3 이면 '느린 성공'을 첫 probe 부터 안정적으로 측정한다."""
    cap = max(1, int(AGENT_CONN_PROBE_TIMEOUT_MS_MAX / 1000))
    base = max(1, (int(AGENT_CONN_SLOW_MS) * 3 + 999) // 1000)
    t = base * (2 ** max(0, int(fails)))
    return int(min(cap, t))


def _unstable_recheck_sec(fails: int) -> float:
    """unstable 재probe 간격(초). base(AGENT_CONN_UNSTABLE_RECHECK_SEC) → ×2 → max(MAX).
    오래 죽은 서버는 드물게 probe(pool 점유·SYN 빈도 억제)."""
    base = max(1, int(AGENT_CONN_UNSTABLE_RECHECK_SEC))
    cap = max(base, int(AGENT_CONN_UNSTABLE_RECHECK_MAX_SEC))
    return float(min(cap, base * (2 ** max(0, int(fails) - 1))))


def _scope_key_of(ds: "dict | None") -> "str | None":
    if not ds:
        return None
    try:
        from . import datasources as _dsr
        k = _dsr.scope_key(ds)
        if k:
            return str(k)
    except Exception:
        pass
    host = ds.get("host")
    if not host:
        return None
    engine = (ds.get("engine") or "mysql").strip().lower()
    try:
        port = int(ds.get("port") or 0)
    except Exception:
        port = 0
    return f"{engine}:{str(host).strip().lower()}:{port}"


def _default_port(engine: str) -> int:
    return 1433 if (engine or "").strip().lower() == "mssql" else 3306


def _is_blocked_target(host: "str | None") -> bool:
    """probe 직전 SSRF 상시-차단(토글 무관) 가드 — DNS rebinding 으로 등록 host 가 메타데이터/
    loopback/link-local 로 재해석되는 것을 막는다(사설 RFC1918 은 운영 정책상 허용 — 차단 안 함).
    해석 실패는 차단(fail-closed). app._ssrf_check_host 의 상시-차단 불변식과 동형(축소판)."""
    if not host:
        return True
    try:
        infos = socket.getaddrinfo(str(host), None)
    except Exception:
        return True  # 해석 불가 → 차단
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except Exception:
            return True
        mapped = getattr(ip, "ipv4_mapped", None)
        if mapped is not None:
            ip = mapped
        if (ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
                or ip.is_unspecified):
            return True
        # 클라우드 메타데이터 IP(IMDS) 상시 차단.
        if str(ip) in ("169.254.169.254", "fd00:ec2::254"):
            return True
    return False


# ── 상태 갱신 ────────────────────────────────────────────────────────────────
def _ensure_entry(key: str, ds: "dict | None") -> dict[str, Any]:
    e = _STATE.get(key)
    if e is None:
        engine = ((ds or {}).get("engine") or "mysql").strip().lower()
        try:
            port = int((ds or {}).get("port") or _default_port(engine))
        except Exception:
            port = _default_port(engine)
        e = {
            "status": UNKNOWN, "fails": 0, "last_elapsed_ms": None, "avg_elapsed_ms": None,
            "last_error": "", "checked_at": 0.0, "next_due": 0.0, "source": "",
            "host": (ds or {}).get("host"), "port": port, "engine": engine,
            "label": str((ds or {}).get("key") or "").strip().lower() or key,
        }
        _STATE[key] = e
    elif ds:
        if ds.get("host"):
            e["host"] = ds.get("host")
        try:
            if ds.get("port"):
                e["port"] = int(ds.get("port"))
        except Exception:
            pass
        if ds.get("engine"):
            e["engine"] = (ds.get("engine") or "mysql").strip().lower()
        lab = str(ds.get("key") or "").strip().lower()
        if lab:
            e["label"] = lab
    return e


def _sample_avg_elapsed(key: str, elapsed_ms: float) -> "float | None":
    """성공 probe 응답시간 표본을 window(deque, maxlen=AGENT_CONN_AVG_WINDOW)에 넣고 최근 N회의
    산술평균(ms, 소수1)을 재계산해 반환. 반드시 _LOCK 안에서 호출(_apply_result). window 크기가
    런타임에 달라졌으면(config reload) 기존 표본을 보존한 채 새 maxlen 으로 재생성한다."""
    win = max(1, int(AGENT_CONN_AVG_WINDOW))
    dq = _SAMPLES.get(key)
    if dq is None or dq.maxlen != win:
        dq = deque(dq or (), maxlen=win)
        _SAMPLES[key] = dq
    dq.append(round(float(elapsed_ms), 1))
    return round(sum(dq) / len(dq), 1) if dq else None


def _apply_result(key: str, ds: "dict | None", ok: bool, elapsed_ms: float,
                  err: str, source: str) -> None:
    now = _now()
    with _LOCK:
        e = _ensure_entry(key, ds)
        e["checked_at"] = now
        e["last_elapsed_ms"] = round(float(elapsed_ms), 1) if elapsed_ms is not None else None
        e["source"] = source
        if ok:
            # 연결 성공 → fails 리셋. elapsed 가 SLOW 이상이면 healthy 가 아니라 unstable(느림).
            was = e["status"]
            e["fails"] = 0
            e["last_error"] = ""
            e["status"] = classify(True, e["last_elapsed_ms"], 0)
            # 평균 연결 응답 시간: **background DB probe(연결+SELECT 1)의 성공 elapsed 만** 표본에 반영한다.
            # foreground 성공 피드백은 elapsed 미측정(0.0 coerce)이라 대표성이 없어 제외, TCP 선검사(probe-tcp)는
            # 실패 경로 전용이라 여기 안 옴. 느린 성공(unstable)도 응답시간은 유효하므로 status 무관하게 표본화.
            if source == "probe-db" and e["last_elapsed_ms"] is not None and e["last_elapsed_ms"] > 0.0:
                e["avg_elapsed_ms"] = _sample_avg_elapsed(key, e["last_elapsed_ms"])
            # 성공(느려도 연결됨)은 healthy 주기로 재확인 — 느림은 실패가 아니므로 backoff 안 함.
            e["next_due"] = now + max(1, int(AGENT_CONN_HEALTHY_RECHECK_SEC))
            if was in (UNSTABLE, DOWN) and e["status"] == HEALTHY:
                _log.info("conn_health recovered scope=%s via=%s", key, source)
        else:
            # 연결 실패 → fails 누적. 임계 이상이면 down(끊김 확정), 미만이면 unstable(1회 blip).
            e["fails"] = int(e["fails"]) + 1
            e["last_error"] = str(err or "")[:80]
            was = e["status"]
            e["status"] = classify(False, None, e["fails"])
            e["next_due"] = now + _unstable_recheck_sec(e["fails"])
            if was != e["status"] and e["status"] in (UNSTABLE, DOWN):
                _log.warning("conn_health %s scope=%s fails=%d via=%s err=%s",
                             e["status"], key, e["fails"], source, e["last_error"])


def _prune_state(keep_keys: "set[str]") -> None:
    """registry 에 더 이상 없는 datasource 의 상태 제거(메모리 누수·삭제된 datasource 의
    잔류 probe 대상 방지)."""
    with _LOCK:
        for k in [k for k in _STATE if k not in keep_keys]:
            _STATE.pop(k, None)
            _SAMPLES.pop(k, None)  # 삭제 datasource 의 응답시간 표본도 정리(메모리 누수 방지).


# ── TCP liveness probe ───────────────────────────────────────────────────────
def _tcp_probe(host: str, port: int, timeout: float) -> "tuple[bool, float, str]":
    start = time.time()
    sock = None
    try:
        sock = socket.create_connection((str(host), int(port)), timeout=float(timeout))
        return True, (time.time() - start) * 1000.0, ""
    except socket.timeout:
        return False, (time.time() - start) * 1000.0, "timeout"
    except OSError as exc:
        return False, (time.time() - start) * 1000.0, f"errno={getattr(exc, 'errno', None)}"
    except Exception as exc:  # pragma: no cover
        return False, (time.time() - start) * 1000.0, type(exc).__name__
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


# ── public: foreground gate + feedback ───────────────────────────────────────
def should_fast_fail(scope_key: "str | None") -> bool:
    """실제 연결 직전 게이트. conn-tristate(사용자 결정 Q2 "연결되면 허용"): **status=down 일 때만**
    True(즉시 fast-fail). unstable(연결은 되지만 느림/1회 blip)은 차단하지 않고 실제 연결을 시도하게
    둔다 — 다른 리전 등 느린(하지만 살아있는) datasource 를 작업 화면에서 그대로 사용 가능. 완전히
    도달 불가(down, 연속 실패 확정)일 때만 worker 점유를 막는다."""
    if not AGENT_CONN_HEALTH_ENABLED or not scope_key:
        return False
    with _LOCK:
        e = _STATE.get(scope_key)
        if not e or e["status"] != DOWN:
            return False
        # 모니터가 돌면 복구는 background 담당 → down 신뢰. 모니터 정지 추정 시(stale)만
        # unknown 강등해 1회 시도 허용(영구 차단 방지 — pool 기아가 아닌 모니터 사망 한정).
        if not monitor_running():
            stale_grace = max(float(AGENT_CONN_HEALTHY_RECHECK_SEC) * 2.0,
                              float(AGENT_CONN_STALE_GRACE_SEC))
            if (_now() - float(e.get("checked_at") or 0.0)) > stale_grace:
                return False
        return True


def record_foreground_result(ds: "dict | None", ok: bool,
                             elapsed_ms: "float | None" = None, err: str = "") -> None:
    """실제 데이터 연결 결과 피드백 — 모니터 없이도 gate 가 즉시 반응(연결실패→다음 요청 fast-fail)."""
    if not AGENT_CONN_HEALTH_ENABLED:
        return
    key = _scope_key_of(ds)
    if not key:
        return
    _apply_result(key, ds, bool(ok), elapsed_ms if elapsed_ms is not None else 0.0,
                  err, source="foreground")


def register(ds: "dict | None") -> None:
    if not AGENT_CONN_HEALTH_ENABLED:
        return
    key = _scope_key_of(ds)
    if not key:
        return
    with _LOCK:
        _ensure_entry(key, ds)


def status_for(ds: "dict | None") -> "dict | None":
    key = _scope_key_of(ds)
    if not key:
        return None
    with _LOCK:
        e = _STATE.get(key)
        return dict(e) if e else None


def snapshot() -> "dict[str, dict]":
    """관리 콘솔용 — 좌표/비밀번호 비노출. status/elapsed/avg/checked_at/error(errno)/fails 만.

    avg_elapsed_ms: 최근 sample_count(≤AGENT_CONN_AVG_WINDOW)회 성공 DB probe 응답시간의 산술평균(ms).
    표본이 아직 없으면(신규·미probe·연속 실패만) None + sample_count=0 — 소비자(admin.js)가 "측정 중"으로 표시."""
    out: dict[str, dict] = {}
    with _LOCK:
        for k, e in _STATE.items():
            dq = _SAMPLES.get(k)
            out[k] = {
                "label": e.get("label"), "engine": e.get("engine"), "status": e.get("status"),
                "last_elapsed_ms": e.get("last_elapsed_ms"), "avg_elapsed_ms": e.get("avg_elapsed_ms"),
                "sample_count": (len(dq) if dq else 0),
                "checked_at": e.get("checked_at"),
                "last_error": e.get("last_error"), "fails": e.get("fails"),
            }
    return out


def _reset_state() -> None:
    """테스트 전용."""
    with _LOCK:
        _STATE.clear()
        _SAMPLES.clear()


# ── background monitor (daemon scheduler + daemon worker pool + queue) ────────
class _Monitor:
    def __init__(self, provider: Callable[[], list]):
        self._provider = provider
        self._stop = threading.Event()
        self._sched: Optional[threading.Thread] = None
        self._workers: list[threading.Thread] = []
        self._q: "queue.Queue[Optional[str]]" = queue.Queue()
        self._inflight: set[str] = set()
        self._inflight_lock = threading.Lock()
        self._targets: dict[str, dict] = {}   # scope_key -> full ds(좌표+비번) — private, 미노출
        self._targets_lock = threading.Lock()

    def start(self) -> None:
        n = max(1, int(AGENT_CONN_PROBE_WORKERS))
        self._stop.clear()
        for i in range(n):
            t = threading.Thread(target=self._worker, name=f"conn-probe-{i}", daemon=True)
            t.start()
            self._workers.append(t)
        self._sched = threading.Thread(target=self._loop, name="conn-health-monitor", daemon=True)
        self._sched.start()
        _log.info("conn_health monitor 시작 (workers=%d tick=%ss)", n, AGENT_CONN_HEALTH_TICK_SEC)

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        for _ in self._workers:
            self._q.put(None)  # worker wake/exit
        if self._sched:
            self._sched.join(timeout=timeout)
        # worker 는 daemon — in-flight probe(bounded)가 끝나면 종료. 프로세스 종료 차단 안 함.

    def _refresh_targets(self) -> None:
        try:
            dss = self._provider() or []
        except Exception as exc:
            # errno/타입만(좌표·자격증명 verbatim 비노출 — provider 가 미래에 raise 해도 안전).
            _log.warning("conn_health get_datasources 실패: %s", type(exc).__name__)
            return
        new: dict[str, dict] = {}
        for ds in dss:
            key = _scope_key_of(ds)
            if not key:
                continue
            new[key] = ds
            with _LOCK:
                _ensure_entry(key, ds)
        with self._targets_lock:
            self._targets = new
        _prune_state(set(new.keys()))

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                key = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if key is None:
                break
            try:
                self._probe_target(key)
            finally:
                with self._inflight_lock:
                    self._inflight.discard(key)

    def _probe_target(self, key: str) -> None:
        with self._targets_lock:
            ds = self._targets.get(key)
        if not ds:
            return
        host = ds.get("host")
        try:
            port = int(ds.get("port") or _default_port((ds.get("engine") or "mysql")))
        except Exception:
            port = _default_port((ds.get("engine") or "mysql"))
        if _is_blocked_target(host):
            _apply_result(key, ds, False, 0.0, "blocked_target", source="probe-ssrf")
            return
        # 1단: TCP 선검사(빠른 도달성). 실패 → unstable, 드라이버 probe 생략(죽은 서버 fast-fail).
        ok_tcp, ms_tcp, err_tcp = _tcp_probe(host, port, _tcp_timeout_sec())
        if not ok_tcp:
            _apply_result(key, ds, False, ms_tcp, err_tcp, source="probe-tcp")
            return
        # 2단: 실제 DB connect + SELECT 1(권위 검증 — TCP 열렸어도 DB 연결 가능 확인).
        with _LOCK:
            e = _STATE.get(key)
            fails = int(e.get("fails", 0)) if e else 0
        try:
            from . import db as _db
            ok_db, ms_db, err_db = _db.probe_datasource(ds, timeout=_driver_timeout_sec(fails))
        except Exception as exc:  # pragma: no cover — 방어
            ok_db, ms_db, err_db = False, 0.0, type(exc).__name__
        _apply_result(key, ds, ok_db, ms_db, err_db, source="probe-db")

    def _loop(self) -> None:
        tick = max(0.2, float(AGENT_CONN_HEALTH_TICK_SEC))
        refresh_every = max(30.0, tick)
        last_refresh = -1e9
        while not self._stop.is_set():
            now = _now()
            if now - last_refresh >= refresh_every:
                self._refresh_targets()
                last_refresh = now
            # due 한 대상을 next_due 오름차순(급한 것 우선)으로 enqueue. in-flight 제외.
            with _LOCK:
                due = sorted(((float(e.get("next_due") or 0.0), k)
                              for k, e in _STATE.items()
                              if float(e.get("next_due") or 0.0) <= now))
            for _, key in due:
                with self._inflight_lock:
                    if key in self._inflight:
                        continue
                    self._inflight.add(key)
                self._q.put(key)
            self._stop.wait(tick)
        _log.info("conn_health monitor 종료")


_MONITOR: Optional[_Monitor] = None
_MONITOR_LOCK = threading.Lock()


def start_monitor(get_datasources: Callable[[], list]) -> None:
    """프로세스에서 1회 호출 — 백그라운드 health 모니터 시작. get_datasources()=현재 ds dict 목록
    (좌표+비밀번호 포함 — 실제 DB probe 에 필요. 모니터 내부 _targets 에만 보유, 미노출)."""
    global _MONITOR
    if not AGENT_CONN_HEALTH_ENABLED:
        _log.info("conn_health 비활성(AGENT_CONN_HEALTH_ENABLED=0) — 모니터 미시작")
        return
    with _MONITOR_LOCK:
        if _MONITOR is not None:
            return
        m = _Monitor(get_datasources)
        m.start()
        _MONITOR = m


def stop_monitor() -> None:
    global _MONITOR
    with _MONITOR_LOCK:
        if _MONITOR is None:
            return
        try:
            _MONITOR.stop()
        finally:
            _MONITOR = None


def monitor_running() -> bool:
    with _MONITOR_LOCK:
        return _MONITOR is not None
