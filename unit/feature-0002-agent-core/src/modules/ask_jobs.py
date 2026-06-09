"""ask_jobs 큐 헬퍼 — out-of-process ask-worker (TASK-0169).

web(app.py) 와 worker(ask.py) 가 공유하는 `agent_runtime.ask_jobs` 큐 연산.
모든 mutation 은 **단일문 atomic** 으로 설계됐다 — 프로젝트의 PG 커넥션은 기본
autocommit=True (db.py:_pg_connect / runtime_backend.py:_get_pg_runtime_conn) 이라
`SELECT ... FOR UPDATE SKIP LOCKED` 후 별도 `UPDATE` 는 행 락을 유지하지 못해
double-claim 이 생긴다(adversarial review BLOCKER 2). 따라서 claim/enqueue/sweep 을
모두 한 statement 로 처리해 트랜잭션 모드와 무관하게 정확하다.

동시성 불변식:
  - claim: pending → running 을 단일 UPDATE…WHERE id=(SELECT…FOR UPDATE SKIP LOCKED)
    로만. exactly-once.
  - lease_epoch: 매 claim/requeue 마다 ++. worker 의 heartbeat/finish 는 자기 lease 를
    조건에 포함 → stale sweeper 가 requeue 로 빼앗았으면(lease 불일치) write 가 no-op
    (fencing — 살아있는 느린 worker 와 새 worker 의 동시 double-run 무해화).
  - slot: 계정별 활성(pending/running, stale running 제외) count < limit 을 INSERT…SELECT
    단일문으로 강제(TOCTOU 차단).
  - attempts: requeue 시 ++, cap 도달 시 terminal error(무한 requeue 차단).

연결: 호출자가 psycopg3 conn(autocommit) 을 제공·관리한다. 본 모듈은 cursor 만 연다.
"""
from __future__ import annotations

import json
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────────────────
# 멱등 DDL (마이그레이션 0003_ask_jobs 와 동일 — dev/cold-boot fast-path 보조)
# ──────────────────────────────────────────────────────────────────────────
_ENSURE_ASK_JOBS_SQL = """
CREATE TABLE IF NOT EXISTS agent_runtime.ask_jobs (
    id bigint GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME agent_runtime.ask_jobs_id_seq
        START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1
    ),
    conversation_id character varying(128) NOT NULL,
    run_id character varying(64),
    account_id bigint NOT NULL,
    status character varying(16) NOT NULL DEFAULT 'pending',
    claimed_by character varying(128),
    claimed_at timestamp with time zone,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    attempts integer NOT NULL DEFAULT 0,
    lease_epoch integer NOT NULL DEFAULT 0,
    heartbeat_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb NOT NULL,
    result_json jsonb,
    CONSTRAINT ask_jobs_pkey PRIMARY KEY (id),
    CONSTRAINT ask_jobs_status_chk CHECK (
        status IN ('pending','claimed','running','done','error','canceled')
    )
);
CREATE INDEX IF NOT EXISTS ix_ask_jobs_claim
    ON agent_runtime.ask_jobs (status, created_at);
CREATE INDEX IF NOT EXISTS ix_ask_jobs_account
    ON agent_runtime.ask_jobs (account_id, status);
CREATE INDEX IF NOT EXISTS ix_ask_jobs_heartbeat
    ON agent_runtime.ask_jobs (heartbeat_at);
CREATE INDEX IF NOT EXISTS ix_ask_jobs_conv
    ON agent_runtime.ask_jobs (conversation_id);
"""

# 활성 슬롯 판정 술어 — pending/running 이되 stale running 은 제외.
# %(stale)s 초 이상 heartbeat 가 없는 running 은 죽은 worker 소유로 보고 슬롯에서 제외
# (그래야 크래시한 job 이 계정을 영구 429 로 가두지 않는다 — MAJOR 5).
_ACTIVE_SLOT_PREDICATE = """
    status IN ('pending','running')
    AND NOT (
        status = 'running'
        AND heartbeat_at IS NOT NULL
        AND heartbeat_at < now() - make_interval(secs => %(stale)s)
    )
"""


def _ensure_ask_jobs(conn) -> None:
    """ask_jobs 테이블 + 인덱스를 멱등 생성(IF NOT EXISTS). 재호출 안전."""
    with conn.cursor() as cur:
        cur.execute(_ENSURE_ASK_JOBS_SQL)


# ──────────────────────────────────────────────────────────────────────────
# enqueue (web) — 단일문 slot enforce (MAJOR 5 TOCTOU 차단)
# ──────────────────────────────────────────────────────────────────────────
def enqueue_ask_job(
    conn,
    *,
    conversation_id: str,
    run_id: str,
    account_id: int,
    payload: dict[str, Any],
    account_limit: int,
    stale_seconds: int,
) -> Optional[int]:
    """pending job 을 enqueue. 계정 활성 슬롯이 limit 미만일 때만 INSERT.

    Returns: job id (성공) / None (슬롯 가득 → caller 가 429).

    INSERT … SELECT … WHERE (count < limit) 단일문이라 두 동시 요청이 모두 통과하는
    TOCTOU 가 불가능하다(인메모리 _ACTIVE_REQUESTS 의 atomic 패리티 — MAJOR 5).
    """
    sql = (
        "INSERT INTO agent_runtime.ask_jobs "
        "(conversation_id, run_id, account_id, status, payload) "
        "SELECT %(cid)s, %(run_id)s, %(account_id)s, 'pending', %(payload)s::jsonb "
        "WHERE ( SELECT count(*) FROM agent_runtime.ask_jobs "
        "        WHERE account_id = %(account_id)s AND (" + _ACTIVE_SLOT_PREDICATE + ") "
        "      ) < %(limit)s "
        "RETURNING id"
    )
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {
                "cid": conversation_id,
                "run_id": run_id,
                "account_id": int(account_id),
                "payload": json.dumps(payload),
                "limit": int(account_limit),
                "stale": int(stale_seconds),
            },
        )
        row = cur.fetchone()
    return int(row[0]) if row else None


def count_active_jobs_for_account(conn, account_id: int, stale_seconds: int) -> int:
    """계정의 활성(pending/running, stale 제외) job 수 — 진단/테스트용."""
    sql = (
        "SELECT count(*) FROM agent_runtime.ask_jobs "
        "WHERE account_id = %(account_id)s AND (" + _ACTIVE_SLOT_PREDICATE + ")"
    )
    with conn.cursor() as cur:
        cur.execute(sql, {"account_id": int(account_id), "stale": int(stale_seconds)})
        row = cur.fetchone()
    return int(row[0]) if row else 0


# ──────────────────────────────────────────────────────────────────────────
# claim (worker) — 단일문 atomic (BLOCKER 2)
# ──────────────────────────────────────────────────────────────────────────
_CLAIM_SQL = """
UPDATE agent_runtime.ask_jobs AS j
SET status = 'running',
    claimed_by = %(worker)s,
    claimed_at = now(),
    started_at = now(),
    heartbeat_at = now(),
    attempts = attempts + 1,
    lease_epoch = lease_epoch + 1
WHERE j.id = (
    SELECT id FROM agent_runtime.ask_jobs
    WHERE status = 'pending'
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING j.id, j.conversation_id, j.run_id, j.account_id, j.payload,
          j.lease_epoch, j.attempts
"""


def claim_ask_job(conn, worker_id: str) -> Optional[dict[str, Any]]:
    """pending job 1건을 atomic 하게 claim(→running). 없으면 None.

    단일 UPDATE…WHERE id=(SELECT…FOR UPDATE SKIP LOCKED LIMIT 1) 이라 autocommit
    에서도 exactly-once (별도 SELECT/UPDATE 분리 시 double-claim — BLOCKER 2).
    """
    with conn.cursor() as cur:
        cur.execute(_CLAIM_SQL, {"worker": worker_id})
        row = cur.fetchone()
    if not row:
        return None
    payload = row[4]
    if isinstance(payload, (str, bytes, bytearray)):
        payload = json.loads(payload)
    return {
        "id": int(row[0]),
        "conversation_id": row[1],
        "run_id": row[2],
        "account_id": int(row[3]) if row[3] is not None else None,
        "payload": payload or {},
        "lease_epoch": int(row[5]),
        "attempts": int(row[6]),
    }


# ──────────────────────────────────────────────────────────────────────────
# heartbeat / lease fencing (BLOCKER 3)
# ──────────────────────────────────────────────────────────────────────────
def heartbeat_ask_job(conn, job_id: int, lease_epoch: int) -> bool:
    """running job 의 heartbeat_at 갱신. 자기 lease 일 때만.

    Returns: True(여전히 소유) / False(lease 박탈됨 — requeue 로 빼앗김 또는 종료).
    worker 는 False 면 즉시 실행을 중단해야 한다(fencing — double-run 무해화).
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE agent_runtime.ask_jobs SET heartbeat_at = now() "
            "WHERE id = %(id)s AND lease_epoch = %(lease)s AND status = 'running' "
            "RETURNING id",
            {"id": int(job_id), "lease": int(lease_epoch)},
        )
        return cur.fetchone() is not None


def owns_lease(conn, job_id: int, lease_epoch: int) -> bool:
    """write 없이 lease 소유 여부만 확인(긴 step 진입 전 가드)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM agent_runtime.ask_jobs "
            "WHERE id = %(id)s AND lease_epoch = %(lease)s AND status = 'running'",
            {"id": int(job_id), "lease": int(lease_epoch)},
        )
        return cur.fetchone() is not None


def finish_ask_job(
    conn, job_id: int, lease_epoch: int, status: str, result_json: Optional[dict] = None
) -> bool:
    """terminal 전이(done/error/canceled). 자기 lease 일 때만(fencing).

    Returns: True(전이 성공) / False(lease 박탈 — 새 worker 가 소유, write 무시).
    """
    if status not in ("done", "error", "canceled"):
        raise ValueError(f"invalid terminal status: {status}")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE agent_runtime.ask_jobs "
            "SET status = %(status)s, finished_at = now(), "
            "    result_json = %(result)s::jsonb "
            "WHERE id = %(id)s AND lease_epoch = %(lease)s "
            "RETURNING id",
            {
                "id": int(job_id),
                "lease": int(lease_epoch),
                "status": status,
                "result": json.dumps(result_json) if result_json is not None else None,
            },
        )
        return cur.fetchone() is not None


def set_job_run_id(conn, job_id: int, lease_epoch: int, run_id: str) -> bool:
    """claim 직후 worker 가 생성한 run_id 를 job 에 기록(ops 가시성 + sweeper 가 KV 정리
    시 사용). 자기 lease 일 때만. Returns: True(기록) / False(lease 박탈)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE agent_runtime.ask_jobs SET run_id = %(run_id)s "
            "WHERE id = %(id)s AND lease_epoch = %(lease)s AND status = 'running' "
            "RETURNING id",
            {"id": int(job_id), "lease": int(lease_epoch), "run_id": run_id},
        )
        return cur.fetchone() is not None


def get_ask_job(conn, job_id: int) -> Optional[dict[str, Any]]:
    """job 행 조회(내부 attach / 테스트). result_json 포함."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, conversation_id, run_id, account_id, status, attempts, "
            "       lease_epoch, result_json "
            "FROM agent_runtime.ask_jobs WHERE id = %(id)s",
            {"id": int(job_id)},
        )
        row = cur.fetchone()
    if not row:
        return None
    result_json = row[7]
    if isinstance(result_json, (str, bytes, bytearray)):
        result_json = json.loads(result_json)
    return {
        "id": int(row[0]),
        "conversation_id": row[1],
        "run_id": row[2],
        "account_id": int(row[3]) if row[3] is not None else None,
        "status": row[4],
        "attempts": int(row[5]),
        "lease_epoch": int(row[6]),
        "result_json": result_json,
    }


# ──────────────────────────────────────────────────────────────────────────
# stale sweeper (worker) — requeue vs terminal error (attempts cap)
# ──────────────────────────────────────────────────────────────────────────
def sweep_stale_jobs(
    conn, *, stale_seconds: int, attempts_cap: int
) -> dict[str, list[dict[str, Any]]]:
    """heartbeat 가 끊긴 running job 을 회수.

    - attempts < cap → requeue(pending, lease_epoch++ 로 기존 worker fencing).
    - attempts >= cap → terminal error(무한 requeue 차단).

    Returns: {"requeued": [...], "errored": [...]} (각 {id, conversation_id, run_id}).
    caller(worker) 는 errored 행에 대해 set_run_status('error') 로 KV 도 정리한다.

    stale_seconds 는 정상 장기 run(run_timeout_sec) 보다 충분히 커야 false-positive
    requeue 가 없다(MAJOR/BLOCKER 3·E).
    """
    errored: list[dict[str, Any]] = []
    requeued: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        # 1) cap 초과 stale → terminal error
        cur.execute(
            "UPDATE agent_runtime.ask_jobs "
            "SET status = 'error', finished_at = now(), lease_epoch = lease_epoch + 1 "
            "WHERE status = 'running' AND heartbeat_at IS NOT NULL "
            "  AND heartbeat_at < now() - make_interval(secs => %(stale)s) "
            "  AND attempts >= %(cap)s "
            "RETURNING id, conversation_id, run_id",
            {"stale": int(stale_seconds), "cap": int(attempts_cap)},
        )
        for r in cur.fetchall():
            errored.append({"id": int(r[0]), "conversation_id": r[1], "run_id": r[2]})
        # 2) cap 미만 stale → requeue (lease_epoch++ 가 기존 worker 의 fencing 신호)
        cur.execute(
            "UPDATE agent_runtime.ask_jobs "
            "SET status = 'pending', claimed_by = NULL, claimed_at = NULL, "
            "    started_at = NULL, heartbeat_at = NULL, lease_epoch = lease_epoch + 1 "
            "WHERE status = 'running' AND heartbeat_at IS NOT NULL "
            "  AND heartbeat_at < now() - make_interval(secs => %(stale)s) "
            "  AND attempts < %(cap)s "
            "RETURNING id, conversation_id, run_id",
            {"stale": int(stale_seconds), "cap": int(attempts_cap)},
        )
        for r in cur.fetchall():
            requeued.append({"id": int(r[0]), "conversation_id": r[1], "run_id": r[2]})
    return {"requeued": requeued, "errored": errored}


# ──────────────────────────────────────────────────────────────────────────
# cancel-pending (web /api/cancel) — pending job 취소 유실 방지
# ──────────────────────────────────────────────────────────────────────────
def cancel_pending_jobs(conn, conversation_id: str) -> list[dict[str, Any]]:
    """conversation 의 pending(아직 미실행) job 을 canceled 로 전이.

    running job 은 기존 KV cancel_requested 플래그를 run_agent 가 폴링해 처리하므로
    무변경(§2.6). pending job 은 아직 run_id 매칭 대상이 없어 KV 플래그가 유실되므로
    여기서 큐 레벨로 취소한다(adversarial review — cancel-while-pending).

    Returns: 취소된 행 [{id, run_id}].
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE agent_runtime.ask_jobs "
            "SET status = 'canceled', finished_at = now() "
            "WHERE conversation_id = %(cid)s AND status = 'pending' "
            "RETURNING id, run_id",
            {"cid": conversation_id},
        )
        return [{"id": int(r[0]), "run_id": r[1]} for r in cur.fetchall()]


# ──────────────────────────────────────────────────────────────────────────
# ownership lookup (B1) — backstop 이 worker-owned run 을 건드리지 않게
# ──────────────────────────────────────────────────────────────────────────
def has_active_job_for_conversation(conn, conversation_id: str) -> bool:
    """conversation 에 활성(pending/running) ask_jobs 가 있는지.

    TASK-0159 boot reconcile / TASK-0164 SIGTERM finalizer 가 worker mode 에서
    이 conversation 을 'orphan' 으로 오인해 error 마킹하지 않도록 가드한다(BLOCKER 1 —
    worker run 은 web 수명과 무관하므로 web 재배포가 건드리면 안 됨).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM agent_runtime.ask_jobs "
            "WHERE conversation_id = %(cid)s AND status IN ('pending','running') LIMIT 1",
            {"cid": conversation_id},
        )
        return cur.fetchone() is not None


def active_inline_paths(conn) -> set[str]:
    """비-terminal(pending/claimed/running) job 의 payload 내 inline temp 파일 경로 집합.

    TASK-0169 (MJ-1): 고아 temp reaper 가 mtime 나이만 보고 삭제하면, 장기 대기/requeue
    로 수명이 reaper 임계(기본 3600s)를 넘긴 활성 job 의 첨부를 지워 read-after-delete 가
    난다. reaper 는 이 집합에 든 경로를 제외해야 한다."""
    paths: set[str] = set()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT payload->>'image_inline_path', payload->>'text_inline_path' "
            "FROM agent_runtime.ask_jobs "
            "WHERE status IN ('pending','claimed','running')"
        )
        for r in cur.fetchall():
            for p in r:
                if p:
                    paths.add(str(p))
    return paths


def reclaim_worker_jobs_on_boot(conn, worker_id: str) -> int:
    """worker 부팅 시 자기 이름으로 남은 running job 을 requeue(이전 인스턴스 잔재).

    SIGKILL 등으로 finally 가 못 돈 경우의 자가 정리. lease_epoch++ 로 혹시 살아있는
    이전 프로세스를 fencing. Returns: requeue 된 건수.
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE agent_runtime.ask_jobs "
            "SET status = 'pending', claimed_by = NULL, claimed_at = NULL, "
            "    started_at = NULL, heartbeat_at = NULL, lease_epoch = lease_epoch + 1 "
            "WHERE status = 'running' AND claimed_by = %(worker)s "
            "RETURNING id",
            {"worker": worker_id},
        )
        return len(cur.fetchall())
