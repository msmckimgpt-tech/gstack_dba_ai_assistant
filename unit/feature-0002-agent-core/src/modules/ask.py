"""ask-worker — out-of-process ask 실행 루프 (TASK-0169, DESIGN-ask-worker.md).

`/api/ask` 가 web 프로세스 안에서 `asyncio.to_thread(run_agent, …)` 로 돌리던 agent
실행을, ask_jobs 큐에서 claim 해 web 밖 전용 worker 프로세스가 실행한다. 그 결과
web 재배포/SIGTERM 이 in-flight run 을 죽이지 않는다(orphan 구조 제거).

설계는 insight-worker(`run_insight_worker_loop`)를 답습하되, 큐는 advisory-lock 이
아니라 ask_jobs 의 `FOR UPDATE SKIP LOCKED` 단일문 claim 을 쓴다.

핵심 안전장치(adversarial review 흡수):
  - exactly-once claim: ask_jobs.claim_ask_job 단일문(BLOCKER 2).
  - lease fencing: claim 마다 새 run_id + lease_epoch. 별도 heartbeat 스레드가 시간
    기반(step 무관)으로 heartbeat_at 갱신 → 긴 LLM step 중에도 stale 오판이 없다
    (BLOCKER 3 / E). heartbeat 스레드가 lease 박탈(requeue 로 빼앗김)을 감지하면 해당
    run 의 KV cancel 플래그를 set → 기존 cancel 폴링으로 agent 루프가 스스로 멈춘다
    (agent 루프 무수정으로 double-run 무해화).
  - stale sweeper: 죽은 worker 의 running job 을 requeue(<cap) 또는 error(>=cap).
  - terminal-only temp cleanup + 고아 reaper(M6).
"""
from __future__ import annotations

import json
import logging
import os
import random
import signal
import socket
import threading
import time
from typing import Any, Optional

from shared.config import (
    AGENT_ASK_WORKER_ENABLED,
    AGENT_ASK_WORKER_TICK_SEC,
    AGENT_ASK_WORKER_IDLE_POLL_SEC,
    AGENT_ASK_WORKER_HEARTBEAT_SEC,
    AGENT_ASK_WORKER_STALE_SEC,
    AGENT_ASK_WORKER_SWEEP_EVERY_SEC,
    AGENT_ASK_WORKER_ATTEMPTS_CAP,
    AGENT_ASK_WORKER_JITTER_SEC,
    AGENT_ASK_WORKER_HEARTBEAT_KEY,
    GLOBAL_CONVERSATION_ID,
)
from .utils import utc_now_iso
from . import ask_jobs
from .memory import set_run_status, save_memory_kv, mark_cancel_requested

log = logging.getLogger("agent_core.ask_worker")

# SIGTERM/SIGINT → graceful: 현재 job 을 마저 끝내고(stop_grace_period 내) 루프 종료.
_SHUTDOWN = threading.Event()

# /shared 볼륨(web·worker 공통 마운트) 상의 첨부 inline temp 파일 디렉토리.
# web 이 worker mode 에서 여기에 쓰고, worker 가 읽은 뒤 terminal 시 정리한다(M6).
_SHARED_INLINE_DIR = os.getenv("ASK_SHARED_INLINE_DIR", "/shared/ask-inline").rstrip("/")
# 고아 temp 파일 reaper: 이 나이(sec)보다 오래됐고 활성 job 이 없는 inline 파일 GC.
_INLINE_REAP_AGE_SEC = int((os.getenv("ASK_INLINE_REAP_AGE_SEC", "3600") or "3600").strip())


def _worker_id() -> str:
    return f"ask-worker-{socket.gethostname()}-{os.getpid()}"


def _pg():
    """ask_jobs 용 PG 연결(psycopg3, autocommit). 단일문 atomic 연산이므로 autocommit 안전."""
    from shared.db import _pg_connect
    return _pg_connect()


def _install_signal_handlers() -> None:
    def _handler(signum, _frame):
        log.info("ask-worker: signal %s 수신 — graceful shutdown 예약", signum)
        _SHUTDOWN.set()
    try:
        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)
    except Exception:
        # 메인 스레드가 아니면(테스트 등) signal 등록 불가 — 무시.
        pass


# ──────────────────────────────────────────────────────────────────────────
# payload → run_agent kwargs
# ──────────────────────────────────────────────────────────────────────────
def _payload_to_kwargs(payload: dict[str, Any], account_id: int, run_id: str) -> dict[str, Any]:
    """ask_jobs.payload(jsonb) 를 run_agent kwargs 로 복원. conv_file 은 account_id 에서
    재계산, output_mode 는 'json' 고정, temperature 는 루프가 내부 재계산(미전달)."""
    return {
        "user_message": payload.get("user_message", ""),
        "conversation_id": payload.get("conversation_id") or None,
        "model": payload.get("model"),
        "output_mode": "json",
        "product_id": payload.get("product_id"),
        "role_id": payload.get("role_id"),
        "account_id": account_id,
        "allowed_schemas": payload.get("allowed_schemas"),
        "product_mode": payload.get("product_mode", "pinned"),
        "attachment_ids": payload.get("attachment_ids") or [],
        "new_attachment_ids": payload.get("new_attachment_ids") or [],
        "image_inline_path": payload.get("image_inline_path"),
        "text_inline_path": payload.get("text_inline_path"),
        "run_id": run_id,
    }


def _slim_result(result: Optional[dict[str, Any]]) -> dict[str, Any]:
    """run_agent 결과를 result_json 으로 영속화(web 내부 attach 가 응답 shape 패리티를
    위해 읽음 — M7). 큰 필드는 보존하되 직렬화 가능 형태로만."""
    if not isinstance(result, dict):
        return {"error": "worker: 결과 없음"}
    keep = ("answer", "conversation_id", "run_id", "executed_sql",
            "result_csv_paths", "rationale", "error", "steps")
    slim: dict[str, Any] = {}
    for k in keep:
        if k in result:
            slim[k] = result[k]
    return slim


# ──────────────────────────────────────────────────────────────────────────
# 첨부 inline temp 파일 정리 (M6: terminal-only)
# ──────────────────────────────────────────────────────────────────────────
def _cleanup_inline_paths(payload: dict[str, Any]) -> None:
    """job 의 inline temp 파일을 삭제. terminal(done/error/canceled) 전이 직전에만 호출
    — requeue 시 read-after-delete 를 막기 위해 실행 도중/requeue 경로에선 삭제 안 함."""
    for key in ("image_inline_path", "text_inline_path"):
        p = payload.get(key)
        if not p:
            continue
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning("ask-worker: inline temp 삭제 실패 %s: %s", p, exc)


def _reap_orphan_inline_files(conn) -> int:
    """활성 job 이 없는 오래된 /shared inline 파일 GC. web 크래시로 enqueue 후 정리
    주인이 사라진 누수 파일을 회수(M6 — GC 주인)."""
    reaped = 0
    try:
        if not os.path.isdir(_SHARED_INLINE_DIR):
            return 0
        # MJ-1: 활성(pending/claimed/running) job 의 첨부 경로는 절대 삭제하지 않는다
        # (장기 대기/requeue 로 mtime 나이가 임계를 넘은 활성 job 의 read-after-delete 방지).
        # 조회 실패 시엔 안전 우선으로 reaper 를 건너뛴다(파일 보존).
        try:
            active = ask_jobs.active_inline_paths(conn)
        except Exception as exc:
            log.warning("ask-worker: active inline path 조회 실패 — reaper skip: %s", exc)
            return 0
        now = time.time()
        for name in os.listdir(_SHARED_INLINE_DIR):
            path = os.path.join(_SHARED_INLINE_DIR, name)
            if path in active:
                continue  # 활성 job 의 첨부 — 보존
            try:
                if not os.path.isfile(path):
                    continue
                age = now - os.path.getmtime(path)
                if age < _INLINE_REAP_AGE_SEC:
                    continue
                os.unlink(path)
                reaped += 1
            except OSError:
                continue
    except Exception as exc:
        log.warning("ask-worker: inline reaper 실패: %s", exc)
    return reaped


# ──────────────────────────────────────────────────────────────────────────
# heartbeat 스레드 (시간 기반 — lease fencing)
# ──────────────────────────────────────────────────────────────────────────
def _heartbeat_loop(job_id: int, lease_epoch: int, conversation_id: str,
                    run_id: str, stop: threading.Event) -> None:
    """실행 중 ask_jobs.heartbeat_at 를 주기적으로 갱신(자기 lease 일 때만).

    lease 가 박탈되면(stale sweeper 가 requeue 로 회수) heartbeat 가 False 를 반환 →
    이 run 의 KV cancel 플래그를 set 해서 agent 루프가 기존 cancel 폴링으로 스스로
    멈추게 한다(double-run 무해화). 자기 전용 PG 연결 사용(스레드 안전)."""
    hb_conn = None
    interval = max(2, int(AGENT_ASK_WORKER_HEARTBEAT_SEC))
    try:
        hb_conn = _pg()
        while not stop.wait(interval):
            try:
                still_own = ask_jobs.heartbeat_ask_job(hb_conn, job_id, lease_epoch)
            except Exception as exc:
                log.warning("ask-worker: heartbeat 갱신 실패 job=%s: %s", job_id, exc)
                # 연결 깨졌으면 재연결 시도
                try:
                    hb_conn.close()
                except Exception:
                    pass
                try:
                    hb_conn = _pg()
                except Exception:
                    hb_conn = None
                continue
            if not still_own:
                # lease 박탈 — 이 run 을 cancel 마킹해 agent 루프 종료 유도.
                log.warning(
                    "ask-worker: lease 박탈 감지 job=%s run=%s — cancel 마킹(fencing)",
                    job_id, run_id,
                )
                try:
                    mark_cancel_requested(None, conversation_id, run_id=run_id)
                except Exception as exc:
                    log.warning("ask-worker: fencing cancel 마킹 실패: %s", exc)
                return
    finally:
        if hb_conn is not None:
            try:
                hb_conn.close()
            except Exception:
                pass


# ──────────────────────────────────────────────────────────────────────────
# job 실행
# ──────────────────────────────────────────────────────────────────────────
def _execute_job(conn, job: dict[str, Any]) -> None:
    from agent_core import run_agent, _new_run_id  # 지연 import(순환 회피)

    job_id = int(job["id"])
    cid = job["conversation_id"]
    lease = int(job["lease_epoch"])
    account_id = job["account_id"]
    payload = job["payload"] or {}

    # 이번 attempt 전용 run_id 생성(claim 별 — requeue 시 이전 worker 의 cancel-fencing
    # 이 새 worker 를 오염시키지 않도록 run_id 를 분리).
    run_id = _new_run_id()
    try:
        ask_jobs.set_job_run_id(conn, job_id, lease, run_id)
    except Exception as exc:
        log.warning("ask-worker: run_id 기록 실패 job=%s: %s", job_id, exc)

    stop_hb = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(job_id, lease, cid, run_id, stop_hb),
        name=f"ask-hb-{job_id}",
        daemon=True,
    )
    hb_thread.start()

    # TASK-0289: 큐 대기시간(enqueue→claim) 산출 — 표시 수행시간을 진짜 end-to-end 로
    # 집계하기 위한 seed. created_at(PG now(), UTC) 과 claim 시각(time.time(), UTC epoch)을
    # 비교 — 동일 호스트라 clock skew 무시 가능. 실패 시 0(=큐 대기 미집계, 안전 폴백).
    queued_ms = 0.0
    _created_at = job.get("created_at")
    if _created_at is not None:
        try:
            _ts = _created_at.timestamp() if hasattr(_created_at, "timestamp") else None
            if _ts is not None:
                queued_ms = max(0.0, (time.time() - _ts) * 1000.0)
        except Exception:
            queued_ms = 0.0

    result: Optional[dict[str, Any]] = None
    raised = False
    try:
        kwargs = _payload_to_kwargs(payload, account_id, run_id)
        kwargs["queued_ms_seed"] = queued_ms
        result = run_agent(**kwargs)
    except Exception as exc:
        raised = True
        log.exception("ask-worker: run_agent 예외 job=%s run=%s", job_id, run_id)
        result = {"error": f"실행 중 오류가 발생했습니다: {exc}", "conversation_id": cid,
                  "run_id": run_id}
    finally:
        stop_hb.set()
        hb_thread.join(timeout=3)
        # terminal-only cleanup (M6) — requeue 가 아니라 실제 종료 직전이므로 안전.
        _cleanup_inline_paths(payload)

    # run_agent 는 정상 종료 시 KV last_status(done/error/canceled)를 이미 기록했다.
    # 예외로 빠져나온 경우에만 KV 를 error 로 정리(프런트 무한 '처리중' 방지).
    if raised:
        try:
            set_run_status(None, cid, "error", run_id=run_id, error=result.get("error"))
        except Exception as exc:
            log.warning("ask-worker: KV error 기록 실패 job=%s: %s", job_id, exc)

    # ask_jobs terminal 전이(ops view + result_json). lease 박탈 시 no-op(fencing).
    err = str((result or {}).get("error") or "").strip()
    status = "error" if (raised or err) else "done"
    try:
        ok = ask_jobs.finish_ask_job(conn, job_id, lease, status,
                                     result_json=_slim_result(result))
        if not ok:
            log.warning(
                "ask-worker: terminal 전이 no-op(lease 박탈) job=%s — requeue 된 run 으로 추정",
                job_id,
            )
    except Exception as exc:
        log.warning("ask-worker: finish_ask_job 실패 job=%s: %s", job_id, exc)


# ──────────────────────────────────────────────────────────────────────────
# worker 생존 heartbeat + sweep
# ──────────────────────────────────────────────────────────────────────────
def _write_worker_heartbeat() -> None:
    try:
        save_memory_kv(None, GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY,
                       utc_now_iso())
    except Exception as exc:
        log.warning("ask-worker: liveness heartbeat 기록 실패: %s", exc)


def _do_sweep(conn) -> None:
    try:
        swept = ask_jobs.sweep_stale_jobs(
            conn,
            stale_seconds=int(AGENT_ASK_WORKER_STALE_SEC),
            attempts_cap=int(AGENT_ASK_WORKER_ATTEMPTS_CAP),
        )
    except Exception as exc:
        log.warning("ask-worker: sweep 실패: %s", exc)
        return
    for row in swept.get("errored", []):
        # cap 초과 stale → KV 도 error 로 정리(프런트 '처리중' 해제).
        try:
            set_run_status(None, row["conversation_id"], "error",
                           run_id=row.get("run_id") or "",
                           error="요청 처리가 반복 실패하여 중단되었습니다. 다시 질의해 주세요.")
        except Exception:
            pass
    if swept.get("requeued") or swept.get("errored"):
        log.info("ask-worker: sweep requeued=%d errored=%d",
                 len(swept.get("requeued", [])), len(swept.get("errored", [])))


# ──────────────────────────────────────────────────────────────────────────
# 메인 루프
# ──────────────────────────────────────────────────────────────────────────
def run_ask_worker_loop() -> None:
    if not AGENT_ASK_WORKER_ENABLED:
        log.info("ask worker disabled: AGENT_ASK_WORKER_ENABLED=0")
        return
    worker_id = _worker_id()
    _install_signal_handlers()
    tick_sec = max(1, int(AGENT_ASK_WORKER_TICK_SEC))
    # TASK-0289: 유휴(claim 대기) 폴링 주기를 reconnect backoff(tick_sec)와 분리. 단일 직렬
    # worker 가 idle 상태일 때 새 job 을 발견하는 지연이 곧 사용자 큐 대기시간 → sub-second 화
    # (기본 0.5s)로 최대 ~2s 였던 큐 대기를 ~0.5s 로 단축. sweep/reconnect 타이밍은 불변.
    idle_poll_sec = max(0.1, float(AGENT_ASK_WORKER_IDLE_POLL_SEC))
    sweep_every = max(5, int(AGENT_ASK_WORKER_SWEEP_EVERY_SEC))
    jitter_sec = max(0, int(AGENT_ASK_WORKER_JITTER_SEC))
    if jitter_sec > 0:
        time.sleep(random.uniform(0, float(jitter_sec)))

    conn = None
    try:
        conn = _pg()
    except Exception as exc:
        log.error("ask-worker: PG 연결 실패 — 종료: %s", exc)
        return

    # 콜드부트 안전: 마이그레이션이 권위이나 dev/미적용 환경 대비 멱등 ensure.
    # 정상 운영(테이블 존재)에서는 app role 이 DDL 권한이 없어 _ensure 가 오해성
    # 'permission denied' 경고를 내므로, 테이블이 실제로 없을 때만 시도한다.
    try:
        if ask_jobs.ask_jobs_table_exists(conn):
            log.info("ask-worker: ask_jobs 테이블 확인됨 (DDL ensure skip — least-privilege)")
        else:
            ask_jobs._ensure_ask_jobs(conn)
    except Exception as exc:
        log.warning("ask-worker: ask_jobs 테이블 준비 실패(마이그레이션 미적용 + DDL 권한 없음?): %s", exc)
    # 이전 인스턴스가 SIGKILL 등으로 남긴 자기 소유 running job 자가 정리.
    try:
        n = ask_jobs.reclaim_worker_jobs_on_boot(conn, worker_id)
        if n:
            log.info("ask-worker: boot self-reclaim — running job %d건 requeue", n)
    except Exception as exc:
        log.warning("ask-worker: boot self-reclaim 실패: %s", exc)

    log.info("ask-worker 시작: %s (tick=%ds stale=%ds heartbeat=%ds)",
             worker_id, tick_sec, AGENT_ASK_WORKER_STALE_SEC, AGENT_ASK_WORKER_HEARTBEAT_SEC)

    # conn-health-monitor: 직렬 ask-worker 가 1차 수혜 — 불안정 datasource 를 백그라운드로
    # 미리 판정해 agent 연결이 fast-fail 하게 한다(정상 datasource job 무지연). 종료 시 stop.
    try:
        from shared import conn_health
        from shared import datasources as _ds
        conn_health.start_monitor(_ds.health_probe_provider())
    except Exception as exc:
        log.warning("ask-worker: conn_health 모니터 시작 실패(무시하고 진행): %s", exc)

    last_sweep = 0.0
    last_reap = 0.0
    while not _SHUTDOWN.is_set():
        _write_worker_heartbeat()
        now = time.monotonic()
        if now - last_sweep >= sweep_every:
            _do_sweep(conn)
            last_sweep = now
        if now - last_reap >= max(sweep_every, 300):
            _reap_orphan_inline_files(conn)
            last_reap = now

        try:
            job = ask_jobs.claim_ask_job(conn, worker_id)
        except Exception as exc:
            log.warning("ask-worker: claim 실패(재연결 시도): %s", exc)
            try:
                conn.close()
            except Exception:
                pass
            try:
                conn = _pg()
            except Exception:
                time.sleep(tick_sec)
            continue

        if job is None:
            # pending 없음 — idle_poll 만큼 쉬되 shutdown 즉시 반응(TASK-0289: 큐 대기 단축).
            _SHUTDOWN.wait(idle_poll_sec)
            continue

        log.info("ask-worker: claim job=%s conv=%s attempts=%s",
                 job["id"], job["conversation_id"], job["attempts"])
        _execute_job(conn, job)

    log.info("ask-worker 종료: %s", worker_id)
    try:
        from shared import conn_health
        conn_health.stop_monitor()
    except Exception:
        pass
    try:
        if conn is not None:
            conn.close()
    except Exception:
        pass
