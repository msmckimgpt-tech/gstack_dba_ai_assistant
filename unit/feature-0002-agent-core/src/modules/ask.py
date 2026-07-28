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
        "sender_username": payload.get("sender_username"),  # gc-ask-sender-attrib: 그룹 발신자 귀속(worker 경로)
        "allowed_schemas": payload.get("allowed_schemas"),
        "product_mode": payload.get("product_mode", "pinned"),
        "attachment_ids": payload.get("attachment_ids") or [],
        "new_attachment_ids": payload.get("new_attachment_ids") or [],
        "image_inline_path": payload.get("image_inline_path"),
        "text_inline_path": payload.get("text_inline_path"),
        "reasoning_level": payload.get("reasoning_level"),  # feature-0003: 추론 강도(worker 경로 패리티)
        "run_id": run_id,
        # FR-brandnew-script-attachment-delivery-gap 후속: 성공 경로의 KV terminal(done)을 워커가
        # **첨부 후처리 뒤** 직접 찍는다(_finalize_deferred_terminal). run_agent 가 미리 찍으면 web
        # long-poll 이 후처리 전 raw 블록을 읽어 노출된다(§18.8 BLOCKER).
        "defer_terminal_status": True,
    }


def _slim_result(result: Optional[dict[str, Any]]) -> dict[str, Any]:
    """run_agent 결과를 result_json 으로 영속화(web 내부 attach 가 응답 shape 패리티를
    위해 읽음 — M7). 큰 필드는 보존하되 직렬화 가능 형태로만."""
    if not isinstance(result, dict):
        return {"error": "worker: 결과 없음"}
    keep = ("answer", "conversation_id", "run_id", "executed_sql",
            "result_csv_paths", "rationale", "error", "steps",
            # FR-brandnew-script-attachment-delivery-gap (worker 후처리, 2026-07-27):
            # worker 가 materialize 한 첨부를 web 응답 shape 로 그대로 전달(inproc 패리티).
            "edited_attachments", "new_attachments")
    slim: dict[str, Any] = {}
    for k in keep:
        if k in result:
            slim[k] = result[k]
    return slim


# ──────────────────────────────────────────────────────────────────────────
# 답변 첨부 블록 후처리 (materialize + strip) — worker 소유
# ──────────────────────────────────────────────────────────────────────────
def _warm_attachment_postprocess_deps() -> None:
    """`web.app` 을 워커 **기동 시** 1회 import 해 sys.modules 에 적재(§18.8 MAJOR).

    후처리는 `import web.app` 을 지연 import 하는데, 첫 job 에서 그 비용(FastAPI/starlette/전
    라우터 로드, ~1s)을 답변 완료 직후의 민감 구간에서 치르면 사용자가 후처리 지연을 체감한다.
    기동 시 미리 데워 두면 job 경로에서는 sys.modules 캐시 히트(비용 ~0)다.
    import 실패는 치명(첨부 전달 기능 전면 무력화)이라 **error** 로 남긴다 — 조용한 무력화 금지.
    """
    try:
        import web.app  # noqa: F401
        log.info("ask-worker: 첨부 후처리 의존(web.app) 워밍업 완료")
    except Exception:
        log.error("ask-worker: web.app import 실패 — 답변 첨부 전달(materialize)이 동작하지 않는다",
                  exc_info=True)



def _postprocess_attachment_blocks(cid: str, account_id: Any,
                                   result: Optional[dict[str, Any]],
                                   run_id: str = "") -> None:
    """assistant 답변의 ```attachment-edit```/```attachment-new``` 블록을 첨부로 materialize
    하고 답변 본문에서 블록을 strip 한다(worker 모드 정본).

    FR-brandnew-script-attachment-delivery-gap 후속(conversation_audit 2026-07-27): 이 후처리는
    원래 web `/api/ask` 동기 핸들러에만 있었다. worker 모드에서 답변 생성은 **이 워커**가 하고
    web 은 long-poll 로 붙어 있을 뿐이라, 장기 run(수 분~십수 분) 중 클라이언트/프록시 연결이
    끊기면 web 핸들러가 후처리 지점에 도달하지 못해 **첨부가 만들어지지 않고 raw 블록이 답변에
    그대로 노출**됐다(라이브 관측: 11분 run, `attachment-new` 블록 미materialize). 답변 완료
    시점을 아는 워커가 후처리를 소유하는 것이 옳다 — 연결 수명과 무관하게 항상 실행된다.

    **terminal 전이(finish_ask_job) 전에 호출**해야 한다. web long-poll 은 terminal 을 보고
    빠져나와 저장된 메시지를 읽으므로, 그 전에 strip·materialize 가 끝나 있어야 사용자가 raw
    블록을 보지 않는다. 모든 실패는 fail-soft(로깅만) — 후처리 실패가 답변 전달을 막지 않는다.
    """
    if not cid or not isinstance(result, dict):
        return
    # 실패/취소 run: 첨부 생성(materialize)은 하지 않되 **strip 은 수행**한다(§18.8 MINOR).
    # web 경로의 기존 정책이 "error 무관 — 블록이 남아 있으면 항상 제거(본문 노출 방지)" 였고,
    # 취소 시 부분 답변(preserve_reasoning)에 블록이 실려 저장될 수 있다.
    _failed = bool(str(result.get("error") or "").strip())

    conn = None
    try:
        # web 헬퍼 재사용(지연 import — worker 이미지에 web 코드가 동봉돼 있고, 순환/기동 비용 회피).
        # 첨부 정본은 MySQL(agent_memory)이고 MinIO 자격증명도 worker env 에 있어 동일 동작 가능.
        import web.app as _web

        conn = _web._connect_memory()
        account = _web._load_account_by_id(conn, int(account_id or 0))
        if not account:
            log.warning("ask-worker: 첨부 후처리 account 미해소(account_id=%s) — skip", account_id)
            return

        latest = _web._load_latest_assistant_message(conn, cid) or {}
        message_id = int(latest.get("id") or 0)
        content = str(latest.get("content") or "")
        if not content or message_id <= 0:
            return
        if ("attachment-edit" not in content) and ("attachment-new" not in content):
            return  # 블록 없음 — 흔한 경로에서 조기 반환(비용 0)

        # request=None: worker 에는 HTTP 요청 컨텍스트가 없어 web audit dispatch 는 생략된다
        # (materialize 내부가 request None 이면 audit skip). 첨부 row 자체의 CreatedByRole=
        # 'assistant' + MetaJson 이 provenance 를 남기고, 아래 로그가 워커 경로를 기록한다.
        edited: list = []
        created: list = []
        if not _failed:
            edited = _web._materialize_assistant_attachment_edits(
                conn, account=account, conversation_id=cid, answer=content,
                message_id=message_id, request=None,
            ) or []
            remaining = max(0, int(_web._ASSISTANT_EDIT_COUNT_CAP) - len(edited))
            created = _web._materialize_assistant_attachment_new(
                conn, account=account, conversation_id=cid, answer=content,
                message_id=message_id, request=None, remaining_count=remaining,
            ) or []

        # strip 은 materialize 성패와 무관하게 수행 — 전체 파일 본문이 채팅에 노출되는 것을 막는다
        # (web 경로와 동일 정책). 두 태그를 순차 적용.
        stripped = _web._strip_attachment_edit_blocks(content, edited)
        stripped = _web._strip_attachment_new_blocks(stripped, created)
        if stripped != content:
            # 영속 성공 시에만 result.answer 를 교체한다(§18.8 MINOR): UPDATE 가 실패했는데
            # result_json 만 stripped 로 두면 ops view 와 실제 저장 메시지가 어긋난다.
            try:
                _web._update_assistant_message_content(conn, cid, message_id, stripped)
                result["answer"] = stripped
            except Exception:
                log.warning("ask-worker: 첨부 strip content 갱신 실패 cid=%s mid=%s",
                            cid, message_id, exc_info=True)

        if edited or created:
            result["edited_attachments"] = edited
            result["new_attachments"] = created
            log.info("ask-worker: 첨부 후처리 완료 cid=%s mid=%s edited=%d new=%d",
                     cid, message_id, len(edited), len(created))
            # 진행 단계(step) 기록 — TASK-0285 ④ 패리티. web inproc 경로는 첨부 materialize 를
            # "단계 보기"에 노출하는데, worker 경로에서 누락되면 사용자가 첨부 생성 사실을 단계로
            # 확인할 수 없다(§18.8 MINOR). run_id 없으면(=단순 답변) skip. fail-soft.
            _record_attachment_step(cid, run_id, result, edited, created)
    except Exception:
        log.warning("ask-worker: 첨부 후처리 실패 cid=%s — 답변 전달은 계속", cid, exc_info=True)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _record_attachment_step(cid: str, run_id: str, result: dict[str, Any],
                            edited: list, created: list) -> None:
    """첨부 materialize 를 진행 단계(step)로 기록 — web inproc 경로(TASK-0285 ④)와 패리티.

    step_index 는 이 run 의 마지막 step 다음. run_id 가 없으면(단순 답변) 기록하지 않는다.
    fail-soft: 실패해도 첨부 전달·답변에 영향 없음.
    """
    if not run_id:
        return
    try:
        from .memory import save_memory_step
        steps = result.get("steps")
        max_idx = -1
        if isinstance(steps, list):
            for s in steps:
                if isinstance(s, dict):
                    try:
                        max_idx = max(max_idx, int(s.get("step_index", 0) or 0))
                    except Exception:
                        pass
        names = ", ".join(
            f"'{a.get('original_filename') or '파일'}'"
            for a in list(edited) + list(created) if isinstance(a, dict)
        )
        action = "attachment_create" if created and not edited else "attachment_edit"
        work = (f"새 첨부 {names}을(를) 파일로 저장했습니다." if created and not edited
                else f"첨부 {names}을(를) 저장했습니다.")
        save_memory_step(None, cid, run_id, {
            "step_index": max_idx + 1,
            "action": action,
            "tool": "materialize_attachment",
            "work": work,
            "reason": "생성·수정한 파일을 사용자에게 다운로드 첨부로 제공합니다.",
            "args": {"attachment_ids": [int(a.get("id") or 0)
                                        for a in list(edited) + list(created)
                                        if isinstance(a, dict)]},
        })
    except Exception:
        log.warning("ask-worker: 첨부 step 기록 실패 cid=%s run=%s", cid, run_id, exc_info=True)


def _finalize_deferred_terminal(cid: str, run_id: str, result: Optional[dict[str, Any]]) -> None:
    """지연된 KV terminal(`done`)을 기록한다 — 첨부 후처리 **뒤** 호출(§18.8 BLOCKER 대응).

    run_agent 를 `defer_terminal_status=True` 로 돌리면 성공 경로의 done 기록이 결과의
    `_deferred_terminal` 로 넘어온다. 이 함수가 반드시(=호출부 finally) 찍어야 프런트가 무한
    '처리중' 에 걸리지 않는다. 지연분이 없으면(에러/취소 경로 — run_agent 가 이미 기록) no-op.
    `_deferred_terminal` 은 내부 전달용이라 기록 후 결과에서 제거한다(result_json 오염 방지).
    """
    if not isinstance(result, dict):
        return
    deferred = result.get("_deferred_terminal")
    if not isinstance(deferred, dict):
        return
    # error 가 (지연 마커 생성 이후에) 설정된 경우에도 terminal 은 반드시 남긴다 — 마커만 버리면
    # KV 가 processing 에 고착돼 프런트가 무한 '처리중'(§18.8 LOW). 상태만 error 로 바꿔 기록한다.
    _err = str(result.get("error") or "").strip()
    try:
        set_run_status(None, cid, "error" if _err else "done",
                       run_id=str(deferred.get("run_id") or run_id or ""),
                       duration_ms=deferred.get("duration_ms"),
                       error=_err, only_if_current_run=True)
    except Exception:
        log.warning("ask-worker: 지연 KV terminal 기록 실패 cid=%s run=%s", cid, run_id, exc_info=True)
    finally:
        # 내부 전달용 마커 — 기록 시도 후 제거(result_json 오염 방지).
        result.pop("_deferred_terminal", None)


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

    # 답변 첨부 블록 후처리(materialize + strip) — **KV terminal(done) 기록 전**.
    # web long-poll(`/api/ask`·`/api/ask_result`)과 프런트 재조회는 KV terminal 을 보고 저장
    # 메시지를 읽으므로, 그 전에 후처리가 끝나야 raw 블록이 노출되지 않는다. run_agent 는
    # defer_terminal_status=True 로 done 을 미뤄 뒀고, 아래 finally 가 반드시 찍는다(무한 '처리중' 방지).
    # (FR-brandnew-script-attachment-delivery-gap 후속 — worker 가 후처리 소유자.)
    # feature-0027 (P0-A): 큐레이션 패키지는 job terminal 전이 **후** 실행하므로 먼저 분리.
    # (_slim_result 는 keep-allowlist 라 어차피 미영속이나, pop 으로 명시 위생.)
    _curation_pkg = result.pop("_post_answer_curation", None) if isinstance(result, dict) else None
    if not raised:
        try:
            _postprocess_attachment_blocks(cid, account_id, result, run_id)
        finally:
            _finalize_deferred_terminal(cid, run_id, result)

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

    # feature-0027 (P0-A): job terminal 전이 **후** 큐레이션(topic/용어/ENUM LLM 3건) — 종전엔
    # run_agent 내부(terminal 전)에서 직렬 실행돼 사용자 체감 지연 +25~35s. 이 시점엔
    # ① 사용자가 이미 답변 수신(KV done) ② job 도 terminal 이라 stale-sweep 이 requeue 할 수
    # 없다(§18.8 backend C2 — heartbeat 사각 무해화). 삭제/취소/오류 종결은 in-core 가 패키지를
    # 폐기했고(backend B1), 함수 내부 _writes_allowed 재검증이 최종 방어층. 실패는 흡수(fail-open).
    if not raised and _curation_pkg:
        try:
            from agent_core import run_post_answer_curation  # 지연 import(순환 회피, run_agent 동일)
            run_post_answer_curation(_curation_pkg)
        except Exception:
            log.warning("ask-worker: post-answer 큐레이션 실패 job=%s run=%s", job_id, run_id, exc_info=True)


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
    _warm_attachment_postprocess_deps()
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

    # feature-0025: 동시 처리 수(관리 콘솔 '답변 동시 처리 수'). restart 반영 — 루프 진입 시 1회 읽는다.
    #   1 이면 아래 단일 직렬 루프(기존 동작 byte-동치). 2 이상이면 전용 PG 커넥션을 가진 N 개 executor
    #   스레드가 각자 claim→execute 하고, main 스레드는 유지보수(heartbeat/sweep/reap) coordinator 로 분리된다.
    #   claim 은 FOR UPDATE SKIP LOCKED + per-claim run_id/lease_epoch 라 동시 실행이 exactly-once·fencing-safe
    #   (다중 워커 확장을 이미 상정한 설계). run_agent 는 web inprocess 모드가 asyncio.to_thread 로 이미
    #   동시 실행하는 검증된 경로이며, 각 스레드는 독립 ContextVar 컨텍스트를 가진다.
    #   ⚠ caveat(리뷰 MINOR-3, web inprocess 와 동일 기존 한계가 ask 병렬로 확장): run_agent 는 모듈 전역
    #   `cfg.CURRENT_RUN_ID` 를 설정한다 — 동시 run 간 이 전역이 덮어써지면 helper LLM 토큰 귀속·메시지
    #   run_id 메타가 오귀속될 수 있다(과금/계측 정확도 한정). **답변 라우팅은 명시 conversation_id 인자로
    #   이뤄져 사용자 간 오전달은 없다**(TASK-0163). 정밀 귀속이 필요하면 run_id 를 전역 대신 인자로 흐르게
    #   하는 후속 작업 필요.
    try:
        from shared import runtime_settings as _rts_ask
        _ask_conc = max(1, min(8, int(_rts_ask.ask_worker_concurrency())))
    except Exception:
        _ask_conc = 1

    def _current_idle_poll() -> float:
        # feature-0025: 관리 콘솔 override(AGENT_ASK_WORKER_IDLE_POLL_MS)가 설정돼 있으면 그 값(ms→초),
        #   없으면 **기존 env knob** AGENT_ASK_WORKER_IDLE_POLL_SEC(= idle_poll_sec)을 그대로 존중한다.
        #   신규 ms knob 이 기존 sec env 를 조용히 무력화하지 않도록(리뷰 MAJOR-2/FINDING-A byte-동치 보존).
        try:
            from shared import runtime_settings as _rts_ip
            if "AGENT_ASK_WORKER_IDLE_POLL_MS" in _rts_ip.read_overrides():
                return _rts_ip.ask_worker_idle_poll_sec()
        except Exception:
            pass
        return idle_poll_sec

    def _run_maintenance(mconn, mstate) -> None:
        """heartbeat + stale sweep + 고아 temp/notes/scratch reap. 단일(coordinator) 스레드에서만 호출."""
        _write_worker_heartbeat()
        now = time.monotonic()
        if now - mstate["sweep"] >= sweep_every:
            _do_sweep(mconn)
            mstate["sweep"] = now
        if now - mstate["reap"] >= max(sweep_every, 300):
            _reap_orphan_inline_files(mconn)
            # feature-0021: 세션/제품 자가리뷰 노트 TTL 정리 (/shared/agent-notes,
            # mtime 기준 — runtime settings 로 TTL 조정). 실패해도 워커 루프 무영향.
            try:
                from modules.agent_notes import sweep_expired_notes
                sweep_expired_notes()
            except Exception as exc:
                log.warning("ask-worker: agent-notes sweep 실패(무시): %s", exc)
            # feature-0022: agent PG scratch workspace TTL 정리 — 마지막 사용 후 TTL(기본 24h)
            # 초과 대화 스키마를 DROP. 인프라 미설정/비활성이면 no-op. 실패해도 워커 루프 무영향.
            try:
                from modules.scratch import sweep_expired_schemas
                sweep_expired_schemas()
            except Exception as exc:
                log.warning("ask-worker: scratch sweep 실패(무시): %s", exc)
            mstate["reap"] = now

    if _ask_conc <= 1:
        # ── 단일 직렬 루프(기존 동작 byte-동치) ──
        state = {"sweep": 0.0, "reap": 0.0}
        while not _SHUTDOWN.is_set():
            _run_maintenance(conn, state)
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
                _SHUTDOWN.wait(_current_idle_poll())
                continue

            log.info("ask-worker: claim job=%s conv=%s attempts=%s",
                     job["id"], job["conversation_id"], job["attempts"])
            _execute_job(conn, job)
    else:
        # ── 병렬: N executor 스레드(전용 conn·worker_id#k) + coordinator 유지보수 ──
        log.info("ask-worker: 병렬 모드 활성 concurrency=%d", _ask_conc)

        def _executor(wid: str) -> None:
            try:
                cx = _pg()
            except Exception as exc:
                log.error("ask-worker[%s]: PG 연결 실패 — 스레드 종료: %s", wid, exc)
                return
            # 동일 pid 재기동 대비 자가 소유 running job 회수(대개 no-op; 크로스-프로세스 stale 은 sweeper 담당).
            try:
                ask_jobs.reclaim_worker_jobs_on_boot(cx, wid)
            except Exception:
                pass
            while not _SHUTDOWN.is_set():
                try:
                    job = ask_jobs.claim_ask_job(cx, wid)
                except Exception as exc:
                    log.warning("ask-worker[%s]: claim 실패(재연결 시도): %s", wid, exc)
                    try:
                        cx.close()
                    except Exception:
                        pass
                    try:
                        cx = _pg()
                    except Exception:
                        _SHUTDOWN.wait(tick_sec)
                    continue
                if job is None:
                    _SHUTDOWN.wait(_current_idle_poll())
                    continue
                log.info("ask-worker[%s]: claim job=%s conv=%s attempts=%s",
                         wid, job["id"], job["conversation_id"], job["attempts"])
                _execute_job(cx, job)
            try:
                cx.close()
            except Exception:
                pass

        threads = []
        for _k in range(_ask_conc):
            t = threading.Thread(target=_executor, args=(f"{worker_id}#{_k}",),
                                 name=f"ask-exec-{_k}", daemon=True)
            t.start()
            threads.append(t)
        state = {"sweep": 0.0, "reap": 0.0}
        while not _SHUTDOWN.is_set():
            _run_maintenance(conn, state)
            _SHUTDOWN.wait(min(sweep_every, 5.0))
        # graceful drain(리뷰 MAJOR-1): SIGTERM 후 executor 들이 **현재 job 을 마칠 시간**을 compose
        #   stop_grace_period(ask-worker: 70s) 예산 안에서 준다 — 직렬 경로가 현재 job 을 grace 창 안에
        #   완주하는 것과 동치화(2초 만에 유기 → orphan → ~18분 재큐 회귀 방지). **공유 deadline** 이라
        #   스레드 합산이 예산을 넘지 않고, 예산 초과분만 daemon+SIGKILL 후 lease heartbeat 중단→sweeper requeue.
        _drain_deadline = time.monotonic() + 65.0
        for t in threads:
            _rem = _drain_deadline - time.monotonic()
            if _rem <= 0:
                break
            t.join(timeout=max(0.0, _rem))

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
