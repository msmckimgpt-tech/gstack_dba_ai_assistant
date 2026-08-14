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

import hashlib
import json
import logging
import os
import re
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
    AGENT_ASK_RESUME_ON_TRANSIENT,
    AGENT_ASK_WORKER_JITTER_SEC,
    AGENT_ASK_WORKER_DRAIN_SEC,
    AGENT_ASK_WORKER_ROLE_STALE_SEC,
    AGENT_ASK_WORKER_HEARTBEAT_KEY,
    AGENT_ASK_WORKER_ALIVE_FILE,
    AGENT_ASK_WORKER_LIVENESS_SEC,
    GLOBAL_CONVERSATION_ID,
)
from .utils import utc_now_iso
from . import ask_jobs
from .memory import set_run_status, save_memory_kv, mark_cancel_requested, load_memory_kv

log = logging.getLogger("agent_core.ask_worker")

# SIGTERM/SIGINT → graceful: 현재 job 을 마저 끝내고(stop_grace_period 내) 루프 종료.
_SHUTDOWN = threading.Event()

# liveness 갱신 스레드 종료 신호 — `_SHUTDOWN` 과 **별개**여야 한다. drain 중에도 컨테이너는
# 살아서 run 을 마치는 중이고, 그 사실을 healthcheck 에 계속 알려야 하기 때문이다(feature-0020).
_LIVENESS_STOP = threading.Event()

# /shared 볼륨(web·worker 공통 마운트) 상의 첨부 inline temp 파일 디렉토리.
# web 이 worker mode 에서 여기에 쓰고, worker 가 읽은 뒤 terminal 시 정리한다(M6).
_SHARED_INLINE_DIR = os.getenv("ASK_SHARED_INLINE_DIR", "/shared/ask-inline").rstrip("/")
# 고아 temp 파일 reaper: 이 나이(sec)보다 오래됐고 활성 job 이 없는 inline 파일 GC.
_INLINE_REAP_AGE_SEC = int((os.getenv("ASK_INLINE_REAP_AGE_SEC", "3600") or "3600").strip())


# role 로 그대로 쓸 수 있는 문자셋. 대괄호는 **의도적으로 제외** — id 의 role 구분자다.
_SAFE_ROLE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _sanitize_role(value: str) -> str:
    """role 을 대괄호가 없는 안전한 토큰으로. 벗어나면 결정적 해시로 치환(단사 보존)."""
    v = str(value or "").strip()
    if not v:
        return "unknown"
    if _SAFE_ROLE_RE.match(v):
        return v
    return "h" + hashlib.sha1(v.encode("utf-8", "replace")).hexdigest()[:12]


def _worker_role() -> str:
    """재배포(컨테이너 재생성)에 **불변**인 worker role 식별자.

    conv-audit FR-ask-orphan-redeploy-dead-air: 종전 worker id 는 `gethostname()`(=컨테이너
    id) 기반이라 배포마다 값이 바뀌었고, 그래서 `reclaim_worker_jobs_on_boot` 의 자기-이름
    일치가 **배포 경로에서 항상 0행**이었다. role 을 분리해 "같은 역할의 이전 인스턴스"를
    식별할 수 있게 한다.

    우선순위는 feature-0025 T0c(워커 스냅샷 identity) 선례와 동일 —
    `AGENT_WORKER_ROLE` > `AGENT_SESSION`(compose 가 이미 주입, 재생성 불변) > hostname.

    id 가 role 을 대괄호로 감싸므로(아래) role 안에 `[`/`]` 가 있으면 경계가 모호해진다
    (적대 리뷰 security H2). 단순 제거는 **비단사**라 `x-y` 와 `x]-y` 가 같은 값이 되므로
    (재리뷰 P2), 안전 문자셋을 벗어나면 role 전체를 결정적 해시로 치환한다 — 대괄호가
    role 안에 들어올 수 없고 서로 다른 role 이 같은 prefix 를 갖지 않는다.
    """
    for _key in ("AGENT_WORKER_ROLE", "AGENT_SESSION"):
        _v = (os.environ.get(_key) or "").strip()
        if _v:
            return _sanitize_role(_v)
    # env 미주입 배포 — hostname 으로 폴백하면 재생성마다 값이 바뀌어 본 봉인의 전제가 깨진다.
    # 조용히 회귀하지 않도록 경고를 남긴다(적대 리뷰 qa H2).
    log.warning(
        "ask-worker: AGENT_WORKER_ROLE/AGENT_SESSION 미주입 — role 을 hostname 으로 폴백. "
        "컨테이너 재생성 시 이전 인스턴스 고아 회수가 전역 stale 창까지 지연될 수 있다."
    )
    return _sanitize_role(socket.gethostname())


def _worker_role_prefix() -> str:
    """같은 role 의 모든 인스턴스가 공유하는 claimed_by prefix.

    role 을 대괄호로 감싸 경계를 못박는다 — `ask-worker[a]-` 는 `ask-worker[ab]-…` 의
    prefix 가 될 수 없고, `_sanitize_role` 이 role 안에 `]` 가 들어오지 못하게 한다.
    종전 `ask-worker-<role>-` 형식은 role `x` 의 prefix 가 role `x-y` 의 id 에도 걸렸다.
    """
    return f"ask-worker[{_worker_role()}]-"


def _worker_id() -> str:
    """이 프로세스 인스턴스의 claim 소유자 id.

    형식: `ask-worker[<role>]-<instance>-<pid>` — role 은 재생성 불변, instance(hostname)+pid
    가 인스턴스 유일성을 준다. 병렬 executor 는 여기에 `#<slot>` 을 덧붙여 claim 한다.
    """
    return f"{_worker_role_prefix()}{socket.gethostname()}-{os.getpid()}"


def _pg():
    """ask_jobs 용 PG 연결(psycopg3, autocommit). 단일문 atomic 연산이므로 autocommit 안전."""
    from shared.db import _pg_connect
    return _pg_connect()


# lease 반납이 이미 끝났음을 알리는 신호(shutdown 타이머 ↔ 메인 종료 경로 중복 작업 억제).
_LEASE_RELEASED = threading.Event()


def _release_own_leases(worker_id: str, *, reason: str) -> Optional[int]:
    """자기 소유(running) job 의 lease 를 즉시 반납해 다음 worker 가 바로 집게 한다.

    반납이 없으면 고아 job 은 전역 stale sweeper 의 STALE_SEC(수백초) 창을 통째로 기다린다
    (conv-audit 실측 dead-air 142~1649s). 전용 단발 연결을 쓴다 — 호출 시점이 종료 경로/타이머
    스레드라 루프 conn 을 공유하면 안 된다.

    반납 직후 그 run 들을 **즉시 cancel 마킹**한다. lease_epoch++ 만으로는 heartbeat 주기
    (기본 10s)가 지나야 구 executor 가 박탈을 눈치채는데, 새 인스턴스는 ~0.5s 안에 재claim
    하므로 그 사이 두 run 이 같은 대화에 동시 기록할 수 있다(적대 리뷰 backend H1 — 종전
    수백초 지연 회수에는 없던 새 겹침 창). heartbeat 가 쓰는 것과 같은 fencing 경로다.

    Returns: 반납 건수. **실패 시 None** — 호출자가 "0건 반납" 과 구분해 재시도/폴백을
    판단한다(적대 리뷰 backend H3: 실패를 성공으로 오인해 메인 종료 경로가 반납을 건너뛰던 결함).
    """
    conn = None
    try:
        conn = _pg()
        rows = ask_jobs.release_worker_jobs_on_shutdown(
            conn, worker_id, attempts_cap=int(AGENT_ASK_WORKER_ATTEMPTS_CAP))
        if rows:
            log.info("ask-worker: lease 반납(%s) — job %s requeue",
                     reason, [r["id"] for r in rows])
        for r in rows:
            try:
                mark_cancel_requested(None, r["conversation_id"], run_id=r.get("run_id") or "")
            except Exception as exc:
                log.warning("ask-worker: 반납 후 fencing cancel 마킹 실패 job=%s: %s",
                            r.get("id"), exc)
        return len(rows)
    except Exception as exc:
        log.warning("ask-worker: lease 반납 실패(%s): %s — stale sweeper 폴백", reason, exc)
        return None
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def _arm_shutdown_lease_release(worker_id: str, drain_sec: int) -> None:
    """SIGTERM 후 drain 예산이 지나면 남은 자기 lease 를 반납하는 1회성 타이머.

    직렬 모드는 메인 스레드가 `_execute_job` 안에서 블록되므로 이 타이머가 **유일한** 반납
    창이다. 병렬 모드는 drain join 종료 후 메인 경로도 반납을 시도하며, 둘 다 같은 단일문
    UPDATE 라 중복 호출이 무해하다(두 번째는 0행).
    """
    if _LEASE_RELEASED.is_set():
        return

    def _wait_then_release() -> None:
        # 반납이 메인 경로에서 먼저 끝나면(_LEASE_RELEASED) 조용히 빠진다.
        if _LEASE_RELEASED.wait(max(1, int(drain_sec))):
            return
        # 실패(None)면 신호를 세우지 않는다 — 메인 종료 경로가 한 번 더 시도한다.
        if _release_own_leases(worker_id, reason=f"drain {drain_sec}s 초과") is not None:
            _LEASE_RELEASED.set()

    threading.Thread(target=_wait_then_release,
                     name="ask-lease-release", daemon=True).start()


def _install_signal_handlers(worker_id: str = "", drain_sec: int = 0) -> None:
    def _handler(signum, _frame):
        log.info("ask-worker: signal %s 수신 — graceful shutdown 예약", signum)
        _SHUTDOWN.set()
        # drain 예산이 끝나도 프로세스가 살아 있으면(=아직 SIGKILL 전) 남은 lease 를 반납한다.
        if worker_id and int(drain_sec) > 0:
            _arm_shutdown_lease_release(worker_id, int(drain_sec))
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
        # conv-audit 2차: `resume_hint` 는 **재큐된 job 에만** 심겨 있다 — 재개 run 이 누적 도구
        # 결과를 이어쓰도록 지시받는다. `resume_allowed` 는 attempts 여유에 달렸으므로 호출측
        # (_process_job)이 주입한다.
        "resume_hint": bool(payload.get("resume_hint")),
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
        # FR-attach-delivery-truncated-by-output-cap (§18.8 [P1]): `update_attachment` 도구로
        # 전달한 첨부는 답변 본문에 블록이 없다. 조기 반환하면 그 첨부들이 message_id 에
        # 바인딩되지 않아 **사용자 말풍선에 칩이 하나도 뜨지 않는다**(파일은 존재하는데 보이지
        # 않는 상태). 도구 전달분이 있으면 계속 진행한다.
        _tool_ids = [int(i) for i in (result.get("tool_delivered_attachment_ids") or [])]
        if not _tool_ids and ("attachment-edit" not in content) and ("attachment-new" not in content):
            return  # 블록도 도구 전달도 없음 — 흔한 경로에서 조기 반환(비용 0)

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
        # 도구 전달분을 답변 메시지에 바인딩 — 칩·step 노출의 전제. 블록 경로 결과와 합쳐
        # web inproc 경로와 동일한 응답 shape 를 만든다.
        if _tool_ids:
            try:
                bound = _web._bind_tool_delivered_attachments(
                    conn, conversation_id=cid, account_id=int(account.get("id") or 0),
                    attachment_ids=_tool_ids, message_id=message_id,
                ) or []
                if bound:
                    edited = list(bound) + list(edited)
                else:
                    log.warning("ask-worker: 도구 전달 첨부 %d건 바인딩 결과 0 — 칩 미노출 가능",
                                len(_tool_ids))
            except Exception:
                log.error("ask-worker: 도구 전달 첨부 바인딩 실패 — 사용자 말풍선에 칩이 뜨지 않는다",
                          exc_info=True)

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


# KV terminal 로 인정하는 상태(web `_ASK_TERMINAL_STATUSES` 와 동형).
_KV_TERMINAL_STATUSES = ("done", "error", "canceled")
# enqueue~claim 갭 동안만 존재하는 가교 run_id 접두어(_conv_store 의 `enqpre-` sentinel).
_ENQ_SENTINEL_PREFIX = "enqpre-"


def _ensure_kv_terminal(cid: str, run_id: str, result: Optional[dict[str, Any]],
                        raised: bool, conn=None, job_id: Optional[int] = None) -> None:
    """run 이 KV terminal 을 남기지 않고 끝났으면 **여기서 반드시 남긴다** (최종 방어선).

    conv-audit FR-early-return-kv-never-finalized: 이 워커의 KV 마감은 종전 세 갈래
    (`raised` 예외 · `_deferred_terminal` · resume-giveup)뿐이었고, 그 전제는
    "run_agent 는 정상 종료 시 KV last_status 를 이미 기록했다" 였다. 그런데 `run_agent`
    에는 KV 를 실제 run_id 로 인계(`set_run_status(processing, run_id)`)하기 **전**에
    `result["error"]` 만 채우고 **예외 없이 정상 return** 하는 조기 종료 경로가 여럿 있다
    (datasource 선연결 실패·회로차단·해석 오류 등). 그 경로는 세 갈래 어디에도 안 걸려
    KV 가 `processing` + enqueue sentinel 로 **영구 고착**했고, `/api/ask_result` 는 KV 를
    terminal 판정 소스로 쓰므로 프런트가 45초 주기로 무한 폴링했다(실측: 조기 종료
    22 job / 20 대화, 사용자 체감 dead-air 는 stale 임계 18분).

    그래서 `finish_ask_job` 직전에 **결과가 무엇이든** KV terminal 을 보장한다. 이미
    terminal 이면 no-op 이므로 정상 경로의 값(첨부 후처리 뒤 done 등)을 덮지 않는다.

    supersede 안전: KV 의 `last_status_run_id` 가 **다른 실제 run** 을 가리키면 write 를
    건너뛴다(그 run 이 대화 상태 슬롯을 인계했다는 뜻 — TASK-0241 가드와 동형). 다만
    `enqpre-` sentinel 은 "아직 아무 run 도 인계하지 못했다" 는 표시라 마감 대상이다 —
    조기 종료가 정확히 이 상태를 남기므로, 이걸 제외하면 봉인이 성립하지 않는다.
    """
    if not cid:
        return
    try:
        cur_status = str(load_memory_kv(None, cid, "last_status") or "").strip().lower()
    except Exception:
        # 판정 불가 — 무조건 write 는 다른 run 의 상태를 덮을 위험이 있어 하지 않는다.
        log.warning("ask-worker: KV terminal 보장 판정 실패 cid=%s run=%s", cid, run_id,
                    exc_info=True)
        return
    if cur_status in _KV_TERMINAL_STATUSES:
        return   # 정상 경로가 이미 마감함
    try:
        cur_rid = str(load_memory_kv(None, cid, "last_status_run_id") or "").strip()
    except Exception:
        cur_rid = ""
    _rid = str(run_id or "").strip()
    _is_sentinel = cur_rid.startswith(_ENQ_SENTINEL_PREFIX)
    if cur_rid and cur_rid != _rid and not _is_sentinel:
        return   # 다른 실제 run 이 인계 — supersede 가드 존중(no-op)
    if _is_sentinel and cur_rid and conn is not None and job_id is not None:
        # §18.8 codex [P1]: 이 sentinel 이 **내 enqueue 의 것이라는 보장이 없다**. 취소→즉시
        # 재요청처럼 새 요청이 막 sentinel 을 심은 창이면, 그것을 내 terminal 로 덮는 순간
        # 새 요청이 시작도 전에 실패로 표시된다. 자기 외 활성 job 이 있으면 그쪽 소유로 본다.
        try:
            if ask_jobs.has_other_active_job_for_conversation(conn, cid, job_id):
                log.info(
                    "ask-worker: KV sentinel 마감 보류 — 다른 활성 job 존재 cid=%s run=%s", cid, run_id
                )
                return
        except Exception:
            # 판정 불가면 보수적으로 보류한다(무한 폴링은 stale 창이 backstop 으로 받는다).
            log.warning("ask-worker: sentinel 소유 판정 실패 cid=%s run=%s", cid, run_id,
                        exc_info=True)
            return
    err = str((result or {}).get("error") or "").strip()
    answer = str((result or {}).get("answer") or "").strip()
    # 답변이 있는데 KV 마감만 실패한 run 을 error 로 적으면 **성공한 턴을 실패로 날조**한다.
    # 오류 문구가 있거나 답변이 아예 없을 때만 error, 그 외에는 done 으로 마감한다.
    # `raised`(run_agent 예외)면 answer 가 남아 있어도 성공이 아니다 — job 전이도 error 다.
    if raised or err or not answer:
        _status = "error"
        err = err or ("요청을 완료하지 못했습니다." if raised
                      else "요청이 시작되지 못한 채 종료되었습니다.")
    else:
        _status = "done"
        err = ""
    try:
        # KV 가 이미 **내 run** 을 가리키면 supersede 가드를 켠다 — 판정~write 사이에 다른 run 이
        # 인계하면 write 를 건너뛴다(§18.8 codex [P1] read-then-write race 창 축소). sentinel·빈 값
        # 이면 가드가 곧 skip 을 뜻하므로(=봉인 무력화) 무조건 write 를 유지한다.
        _guard = bool(cur_rid) and cur_rid == _rid
        set_run_status(None, cid, _status, run_id=_rid, error=err,
                       only_if_current_run=_guard)
        log.warning(
            "ask-worker: KV terminal 미기록 run 을 %s 로 마감 cid=%s run=%s prev_status=%s "
            "prev_run=%s (조기 종료 경로 추정)", _status, cid, run_id, cur_status or "<empty>",
            cur_rid or "<empty>",
        )
    except Exception:
        log.warning("ask-worker: KV terminal 보장 기록 실패 cid=%s run=%s", cid, run_id,
                    exc_info=True)


def _resume_giveup_finalize(cid: str, run_id: str, result: Optional[dict[str, Any]]) -> None:
    """재개 재큐가 성립하지 않았을 때 **KV terminal 을 반드시 남긴다** (§18.8 패널 P1-3).

    resume 경로의 run 은 "재큐될 것" 을 전제로 KV terminal 을 찍지 않고 지연 마커도 만들지
    않는다. 그런데 재큐가 실패(예외)하거나 no-op(lease 박탈·cap) 이면 `last_status` 가
    **`processing` 에 고착**돼 프런트가 무한 '처리 중' 이 되고 이후 활성 판정도 오염된다.
    `only_if_current_run=True` 로 새 소유자의 상태를 덮지 않는다(lease 박탈 시 안전 no-op).
    """
    if not isinstance(result, dict):
        return
    _err = str(result.get("error") or "").strip() or "일시적인 LLM 오류로 요청을 완료하지 못했습니다."
    try:
        set_run_status(None, cid, "error", run_id=run_id, error=_err, only_if_current_run=True)
    except Exception:
        log.warning("ask-worker: 재개 포기 KV terminal 기록 실패 cid=%s run=%s",
                    cid, run_id, exc_info=True)


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
        # 재시도(requeue 후 재claim)면 이전 attempt 가 이미 사용자 메시지를 저장했을 수 있다.
        # job.created_at 이후 구간만 대조해 중복 저장을 막는다(conv-audit RC-2). 첫 attempt 는
        # None → 종전 동작 그대로.
        if int(job.get("attempts") or 1) > 1 and _created_at is not None:
            kwargs["dedup_user_message_since"] = _created_at
        # conv-audit 2차: 재개 가능 여부를 **여기서** 결정해 run 에 알린다. attempts 여유가
        # 없으면(cap 도달) run 은 종전대로 오류 turn 을 남겨 사용자에게 실패를 알리고, 여유가
        # 있으면 오류 turn·KV terminal 을 보류해 아래 재큐가 이어받는다. 이렇게 두면 "재큐는
        # 못 했는데 사용자에게 아무 것도 안 남는" 창이 **구조적으로** 생기지 않는다.
        kwargs["resume_allowed"] = bool(
            AGENT_ASK_RESUME_ON_TRANSIENT
            and int(job.get("attempts") or 1) < int(AGENT_ASK_WORKER_ATTEMPTS_CAP)
        )
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
        # conv-audit 2차(자체 적발): 이 전제가 **재개 재큐로 깨졌다**. `resumable` run 은 아래에서
        # pending 으로 되돌려 재claim 이 같은 payload 로 다시 도는데, 여기서 inline 임시파일을
        # 지우면 재개 run 이 첨부 인라인 본문을 read-after-delete 로 잃는다(사고 대화는 첨부 6건).
        # 그래서 resumable 이면 보류하고, 재큐가 실패해 정상 terminal 로 내려갈 때 그 자리에서 지운다.
        if not (isinstance(result, dict) and result.get("resumable")):
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

    # ── 일시 LLM 장애 소진 → terminal 대신 재개 재큐 (conv-audit 2차) ─────────────
    # **반드시 `_finalize_deferred_terminal` 앞에 온다.** 그 함수는 KV terminal(error/done)을
    # 찍는데, 재큐할 run 에 대해 그것이 찍히면 프런트가 "끝났다"로 보고 스피너를 내려 재개
    # 결과를 못 받는다(= 사용자에겐 여전히 실패). 후처리(첨부 materialize)도 이 경로에는 답변이
    # 없어 할 일이 없으므로 함께 건너뛴다.
    # run 이 `resumable` 을 세웠다는 것은 "원인이 일시적이고, 누적 작업이 저장소에 남아 있다" 는
    # 뜻이다. error 로 닫으면 154초 추론·도구 결과가 통째로 버려지고 사용자는 처음부터 다시
    # 물어야 한다(2026-08-12 17:30 사고). attempts cap 안에서 pending 으로 되돌린다.
    if (not raised) and AGENT_ASK_RESUME_ON_TRANSIENT and isinstance(result, dict) \
       and result.get("resumable"):
        try:
            if ask_jobs.requeue_ask_job_for_resume(
                conn, job_id, lease, attempts_cap=int(AGENT_ASK_WORKER_ATTEMPTS_CAP)
            ):
                # 지연 terminal 마커를 **버린다** — 이 run 은 종료가 아니라 인계다.
                result.pop("_deferred_terminal", None)
                log.warning(
                    "ask-worker: 일시 장애로 run 재개 재큐 job=%s run=%s reason=%s "
                    "(누적 도구 결과 보존 — 재claim 이 이어받는다)",
                    job_id, run_id, result.get("resume_reason"),
                )
                return   # terminal 미기록 — 재claim 이 이 job 을 이어서 처리한다.
            # 여기 오는 경우는 (a) lease 박탈 — 새 소유자가 이 job 을 이어받았으므로 사용자에게
            # 공백이 없다, 또는 (b) 경합으로 attempts 가 cap 에 닿았다.
            log.warning(
                "ask-worker: 재개 재큐 no-op(lease 박탈 또는 attempts cap) job=%s — "
                "정상 terminal 경로로 진행.", job_id,
            )
            _resume_giveup_finalize(cid, run_id, result)
            # 재큐하지 않으므로 이제 실제 종료다 — 위 finally 가 보류한 정리를 여기서 수행.
            _cleanup_inline_paths(payload)
        except Exception as exc:
            log.warning("ask-worker: 재개 재큐 실패 job=%s: %s", job_id, exc)
            _resume_giveup_finalize(cid, run_id, result)
            _cleanup_inline_paths(payload)

    if not raised:
        try:
            _postprocess_attachment_blocks(cid, account_id, result, run_id)
        finally:
            _finalize_deferred_terminal(cid, run_id, result)

    # conv-audit FR-early-return-kv-never-finalized: KV terminal 최종 보장 — 위 세 갈래
    # (raised / _deferred_terminal / resume-giveup) 중 어디에도 걸리지 않은 조기 종료 run 을
    # 여기서 마감한다. `finish_ask_job` **앞**에 둔다 — web long-poll(`/api/ask`·
    # `/api/ask_result`)의 1차 terminal 판정 소스가 KV 이므로, job 전이보다 먼저 풀어야
    # 사용자 대기가 즉시 끝난다. 이미 terminal 이면 no-op(정상 경로 무영향).
    # 재개 재큐 경로는 위에서 `return` 하므로 여기 도달하지 않는다(terminal 미기록 유지).
    _ensure_kv_terminal(cid, run_id, result, raised, conn=conn, job_id=job_id)

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


# ── 인스턴스-local liveness (feature-0020 surge drain) ──────────────────────
# KV heartbeat 는 **role 전역 단일 키**다. 그것으로 "이 role 이 살아 있나" 는 답할 수 있지만
# (web UI 의 워커 생존 표시가 그 용도다) "**이 컨테이너**가 살아 있나" 는 답할 수 없다.
# surge 교대 창에서는 본체와 surge 가 동시에 뛰므로 그 구분이 곧 배포 판정의 근거가 된다:
#   - 공유 키만 보면 한쪽이 죽어도 다른 쪽이 갱신해 **양쪽 다 healthy 로 보인다**(false-pass).
#   - 반대로 drain 중인 본체는 신규 claim 을 멈춘 상태라 메인 루프가 돌지 않는데, 그 사이
#     공유 키 갱신이 끊기면 **살아서 run 을 마치는 중인 컨테이너가 unhealthy 로 보인다**
#     (false-fail — 배포 스파인이 이 신호로 롤백을 판정하므로 그냥 오탐이 아니다).
# 그래서 컨테이너 로컬 파일에 인스턴스 전용 스탬프를 남기고 healthcheck 가 그것을 본다.
# PG 왕복도 사라져 DB blip 이 워커를 unhealthy 로 만들던 결합도 함께 끊긴다.
def _touch_alive_file() -> None:
    try:
        tmp = f"{AGENT_ASK_WORKER_ALIVE_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(utc_now_iso())
        os.replace(tmp, AGENT_ASK_WORKER_ALIVE_FILE)   # 원자 교체 — 판독측이 반쪽 파일을 보지 않는다
    except Exception as exc:
        log.warning("ask-worker: alive 파일 기록 실패(%s): %s", AGENT_ASK_WORKER_ALIVE_FILE, exc)


def _start_liveness_thread(interval_sec: int) -> threading.Thread:
    """liveness 갱신을 메인 루프에서 **떼어낸** 데몬 스레드.

    종전엔 `_run_maintenance` 안에서만 갱신했다 — 즉 "루프가 돌고 있다" 가 곧 liveness 였다.
    drain(`_SHUTDOWN` set)에 들어가면 루프는 의도적으로 멈추고 실행 중 job 만 마치는데,
    그 상태는 **정상**이지 죽은 게 아니다. 갱신이 루프에 묶여 있으면 그 정상 상태가
    unhealthy 로 보이고, 완주에 걸리는 시간이 길수록 오탐이 확실해진다(최악 실측 run 2,024s
    vs healthcheck 임계 60s). 그래서 프로세스가 살아 있는 동안은 무조건 뛰게 한다.
    """
    def _loop() -> None:
        while True:
            _touch_alive_file()
            _write_worker_heartbeat()
            if _LIVENESS_STOP.wait(interval_sec):
                return

    th = threading.Thread(target=_loop, name="ask-liveness", daemon=True)
    th.start()
    return th


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


def _do_role_reclaim(conn, worker_id: str) -> None:
    """같은 role 의 **죽은 이전 인스턴스**가 남긴 running job 을 짧은 창으로 회수.

    A(종료 시 lease 반납)가 못 도는 경로 — SIGKILL/OOM/노드 crash — 의 backstop.
    전역 sweep 의 STALE_SEC(수백초)을 기다리지 않고 ROLE_STALE_SEC(기본 60s)만에 회수한다.
    heartbeat 는 시간 기반(10s 주기, step 무관)이라 이 창을 넘겼으면 그 프로세스는 죽은 것이다.
    자기 자신(및 자기 슬롯) 소유 행은 대상에서 제외된다.
    """
    try:
        out = ask_jobs.reclaim_role_orphan_jobs(
            conn,
            role_prefix=_worker_role_prefix(),
            self_prefix=worker_id,
            stale_seconds=int(AGENT_ASK_WORKER_ROLE_STALE_SEC),
            attempts_cap=int(AGENT_ASK_WORKER_ATTEMPTS_CAP),
        )
    except Exception as exc:
        log.warning("ask-worker: role 고아 회수 실패: %s — 전역 sweep 폴백", exc)
        return
    for row in out.get("errored", []):
        # cap 도달 → KV 도 error 로 정리(전역 sweep 과 동일 문구·경로, 프런트 '처리중' 해제).
        try:
            set_run_status(None, row["conversation_id"], "error",
                           run_id=row.get("run_id") or "",
                           error="요청 처리가 반복 실패하여 중단되었습니다. 다시 질의해 주세요.")
        except Exception:
            pass
    for row in out.get("requeued", []):
        # 구 인스턴스가 만약 아직 살아 있다면(=heartbeat 만 지연) fencing cancel 로 겹침 차단.
        try:
            mark_cancel_requested(None, row["conversation_id"], run_id=row.get("run_id") or "")
        except Exception:
            pass
    if out.get("requeued") or out.get("errored"):
        log.info("ask-worker: role 고아 회수 requeued=%d errored=%d (이전 인스턴스 잔재)",
                 len(out.get("requeued", [])), len(out.get("errored", [])))


# ──────────────────────────────────────────────────────────────────────────
# 메인 루프
# ──────────────────────────────────────────────────────────────────────────
def run_ask_worker_loop() -> None:
    if not AGENT_ASK_WORKER_ENABLED:
        log.info("ask worker disabled: AGENT_ASK_WORKER_ENABLED=0")
        return
    worker_id = _worker_id()
    # drain 예산 — compose stop_grace_period(70s) 보다 작아야 반납이 SIGKILL 前에 끝난다.
    drain_sec = max(1, int(AGENT_ASK_WORKER_DRAIN_SEC))
    _LEASE_RELEASED.clear()
    _install_signal_handlers(worker_id, drain_sec)
    # liveness 는 메인 루프보다 **먼저** 뛰기 시작한다 — 부팅 중(role reclaim·warm-up)과
    # drain 중(루프 정지, run 완주 대기) 양쪽 다 컨테이너는 살아 있고, healthcheck 는 그
    # 사실을 알아야 한다(feature-0020 surge drain).
    _LIVENESS_STOP.clear()
    _start_liveness_thread(max(1, int(AGENT_ASK_WORKER_LIVENESS_SEC)))
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
    # 재배포(컨테이너 재생성)로 hostname 이 바뀌면 위 자기-이름 회수는 0행이다 — 같은 role 의
    # 죽은 이전 인스턴스 잔재를 부팅 즉시 한 번 더 훑는다(주기 회수는 _run_maintenance).
    _do_role_reclaim(conn, worker_id)

    log.info("ask-worker 시작: %s (tick=%ds stale=%ds role_stale=%ds drain=%ds heartbeat=%ds)",
             worker_id, tick_sec, AGENT_ASK_WORKER_STALE_SEC,
             AGENT_ASK_WORKER_ROLE_STALE_SEC, drain_sec, AGENT_ASK_WORKER_HEARTBEAT_SEC)

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
            # 같은 role 의 죽은 이전 인스턴스 잔재를 짧은 창으로 회수(재배포 dead-air 봉인 backstop).
            _do_role_reclaim(mconn, worker_id)
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
        #   스레드 합산이 예산을 넘지 않는다. 예산을 넘긴 job 은 아래에서 **lease 를 명시 반납**해
        #   다음 인스턴스가 즉시 집게 한다(종전엔 sweeper 의 STALE_SEC 창을 통째로 대기 —
        #   conv-audit FR-ask-orphan-redeploy-dead-air 실측 dead-air 142~1649s).
        _drain_deadline = time.monotonic() + float(drain_sec)
        for t in threads:
            _rem = _drain_deadline - time.monotonic()
            if _rem <= 0:
                break
            t.join(timeout=max(0.0, _rem))

    # ── 재배포 인계(A): 아직 자기 소유로 남은 running job 의 lease 를 명시 반납 ──
    # drain 을 넘겨 죽게 될 job 을 sweeper 의 STALE_SEC 창에 맡기지 않는다. 새 인스턴스가
    # ~idle_poll(0.5s) 안에 재claim → 사용자 dead-air 가 수백초에서 수초로 줄어든다.
    # 이미 타이머가 반납했으면(직렬 모드 등) 이 호출은 0행 no-op.
    if not _LEASE_RELEASED.is_set():
        if _release_own_leases(worker_id, reason="graceful shutdown") is not None:
            _LEASE_RELEASED.set()

    log.info("ask-worker 종료: %s", worker_id)
    # liveness 중단은 **여기까지 와서** 한다 — drain 을 마친 뒤가 진짜 종료 시점이다.
    # alive 파일도 지워 "프로세스는 죽었는데 컨테이너만 남은" 상태가 임계(60s)를 기다리지 않고
    # 즉시 unhealthy 로 드러나게 한다(배포 게이트가 그만큼 빨리 판정한다).
    _LIVENESS_STOP.set()
    try:
        os.unlink(AGENT_ASK_WORKER_ALIVE_FILE)
    except Exception:
        pass
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
