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


def ask_jobs_table_exists(conn) -> bool:
    """ask_jobs 테이블 존재 여부. 정상 운영(마이그레이션 적용)에서는 app role(agent_kb_rw)
    이 DDL 권한이 없어 _ensure_ask_jobs 가 'permission denied for schema' 로 실패하는데,
    그건 오해를 부르는 경고다(테이블은 이미 있음). 이 체크로 존재 시 DDL 시도를 건너뛴다."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('agent_runtime.ask_jobs') IS NOT NULL")
        row = cur.fetchone()
    return bool(row and row[0])


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
    dedup_message: Optional[str] = None,
) -> Optional[int]:
    """pending job 을 enqueue. 계정 활성 슬롯이 limit 미만일 때만 INSERT.

    Returns: job id (성공) / None (슬롯 가득 → caller 가 429, **또는** dedup 억제 →
    caller 가 find_active_dup_ask_job 으로 기존 job 에 attach).

    INSERT … SELECT … WHERE (count < limit) 단일문이라 두 동시 요청이 모두 통과하는
    TOCTOU 가 불가능하다(인메모리 _ACTIVE_REQUESTS 의 atomic 패리티 — MAJOR 5).

    멱등성(dedup_message, ask-dedup-idempotency): 같은 (conversation_id, account_id,
    user_message) 로 이미 활성(pending/running) job 이 있으면 INSERT 를 억제한다(WHERE
    절의 NOT EXISTS — INSERT 와 동일 statement 라 commit 된 중복에 대해 atomic). 워커
    모드의 /api/ask 는 long-poll 로 연결을 수십 초~분 잡으므로, web 재배포/프록시 EOF 로
    그 연결이 끊겨 사용자가 같은 메시지를 재전송하면 두 번째 run 이 떠 요청·답변이 2회
    처리되던 결함(중복 전송)을 차단한다. INSERT 가 None 을 반환하면 caller 는
    find_active_dup_ask_job 으로 기존 job_id 를 찾아 그 run 에 attach 한다(새 job 미생성).
    """
    dedup_clause = ""
    if dedup_message is not None:
        # commit 된 활성 중복에 대해서만 억제(자기 자신이 될 행은 아직 미INSERT).
        # 활성 판정은 slot 예약과 동일한 _ACTIVE_SLOT_PREDICATE 재사용 — stale(heartbeat
        # 끊긴 running)은 제외해, 죽은 run 에 dedup-attach 하지 않고 새 run 을 띄운다(REV MINOR).
        # 전용 파라미터(%(dcid)s)를 쓴다 — %(cid)s 는 INSERT SELECT 의 첫 항목(=conversation_id
        # 컬럼, character varying 으로 추론)으로도 쓰여, 같은 $param 을 여기 비교(text 추론)에
        # 재사용하면 PG 가 "inconsistent types deduced ... text versus character varying"
        # (AmbiguousParameter)로 거부한다. 별도 이름이면 각 파라미터가 단일 컨텍스트라 안전.
        dedup_clause = (
            "  AND NOT EXISTS ( "
            "    SELECT 1 FROM agent_runtime.ask_jobs AS d "
            "    WHERE d.conversation_id = %(dcid)s AND d.account_id = %(daccount)s "
            "      AND (" + _ACTIVE_SLOT_PREDICATE + ") "
            "      AND d.payload->>'user_message' = %(dedup_message)s "
            "  ) "
        )
    sql = (
        "INSERT INTO agent_runtime.ask_jobs "
        "(conversation_id, run_id, account_id, status, payload) "
        "SELECT %(cid)s, %(run_id)s, %(account_id)s, 'pending', %(payload)s::jsonb "
        "WHERE ( SELECT count(*) FROM agent_runtime.ask_jobs "
        "        WHERE account_id = %(account_id)s AND (" + _ACTIVE_SLOT_PREDICATE + ") "
        "      ) < %(limit)s "
        + dedup_clause +
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
                "dedup_message": dedup_message,
                # dedup NOT EXISTS 전용(%(cid)s/%(account_id)s 와 타입추론 충돌 회피).
                "dcid": conversation_id,
                "daccount": int(account_id),
            },
        )
        row = cur.fetchone()
    return int(row[0]) if row else None


def find_active_dup_ask_job(
    conn, *, conversation_id: str, account_id: int, user_message: str,
    stale_seconds: int,
) -> Optional[int]:
    """같은 (conversation_id, account_id, user_message) 로 활성 job 의 id 를 반환(없으면
    None). enqueue_ask_job(dedup_message=...) 가 INSERT 를 억제해 None 을 돌려줬을 때,
    caller 가 '슬롯 가득(429)' 과 '중복 억제(기존 run attach)' 를 구분하기 위해 쓴다. 활성
    판정은 enqueue 의 dedup 절과 동일한 _ACTIVE_SLOT_PREDICATE — stale(heartbeat 끊긴
    running)은 제외해 죽은 run 에 attach 하지 않는다(예약·억제·재사용 술어 일치). 가장 최근
    (가장 큰 id) 활성 job 을 고른다(보통 1건)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM agent_runtime.ask_jobs "
            "WHERE conversation_id = %(cid)s AND account_id = %(account_id)s "
            "  AND (" + _ACTIVE_SLOT_PREDICATE + ") "
            "  AND payload->>'user_message' = %(um)s "
            "ORDER BY id DESC LIMIT 1",
            {"cid": conversation_id, "account_id": int(account_id), "um": user_message,
             "stale": int(stale_seconds)},
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
          j.lease_epoch, j.attempts, j.created_at
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
        # TASK-0289: enqueue 시각 — worker 가 claim 시점과 비교해 큐 대기시간(queued_ms)을
        # 산출하고 run_agent 에 seed 로 넘긴다(수행시간 end-to-end 집계). RETURNING 에 추가됐으나
        # 구(舊) 행/테스트 fixture(7-tuple) 호환 위해 길이 가드(부재=None=큐 대기 미집계).
        "created_at": row[7] if len(row) > 7 else None,
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


def requeue_ask_job_for_resume(
    conn, job_id: int, lease_epoch: int, *, attempts_cap: int
) -> bool:
    """일시 LLM 장애로 소진된 run 을 **재개용으로 재큐**한다 (conv-audit 2차).

    terminal(error) 로 닫지 않고 `pending` 으로 되돌린다 — 누적 도구 호출·결과는 이미
    `core_messages` 에 영속돼 있고 히스토리 로더가 replay 하므로, 재claim 된 run 이 그
    맥락을 이어받아 **처음부터 다시 하지 않는다**(payload 에 `resume_hint` 를 심어 재개
    run 이 그 사실을 알고 "이미 조회한 것 재조회 금지" 지시를 받는다).

    가드:
      - **자기 lease 일 때만**(fencing) — 박탈된 run 이 새 소유자의 상태를 되돌리지 못한다.
      - `attempts < cap` — attempts 는 claim 시점에 증가하므로 여기서 더하지 않는다.
        cap 을 넘긴 행은 재큐하지 않고 False 를 돌려 호출측이 정상 terminal 로 닫게 한다
        (`release_worker_jobs_on_shutdown` 과 같은 규율 — 무한 재큐 방지).
      - `lease_epoch++` — 아직 살아 있을 수 있는 자기 executor 스레드를 fencing.

    Returns: True(재큐됨 — 호출측은 terminal 을 찍지 말아야 한다) / False(재큐 안 됨).
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE agent_runtime.ask_jobs "
            "SET status = 'pending', claimed_by = NULL, claimed_at = NULL, "
            "    started_at = NULL, heartbeat_at = NULL, finished_at = NULL, "
            "    lease_epoch = lease_epoch + 1, "
            "    payload = coalesce(payload, '{}'::jsonb) || '{\"resume_hint\": true}'::jsonb "
            "WHERE id = %(id)s AND lease_epoch = %(lease)s "
            "  AND status = 'running' AND attempts < %(cap)s "
            "RETURNING id",
            {"id": int(job_id), "lease": int(lease_epoch), "cap": int(attempts_cap)},
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


def has_other_active_job_for_conversation(
    conn, conversation_id: str, exclude_job_id: int
) -> bool:
    """이 job 을 **제외한** 활성(pending/claimed/running) job 이 같은 대화에 있는지.

    conv-audit FR-early-return-kv-never-finalized(봉인 A 의 sentinel race 가드, §18.8 codex [P1]).
    종료하는 run 이 KV 의 `enqpre-` sentinel 을 보고 마감할 때, 그 sentinel 이 **자기 것이 아니라
    방금 들어온 새 요청의 것**일 수 있다(취소→즉시 재요청 등). 그 상태를 덮으면 새 요청이 시작도
    전에 error 로 표시된다. 자기 외 활성 job 이 있으면 sentinel 은 그쪽 소유로 보고 건드리지 않는다.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM agent_runtime.ask_jobs "
            "WHERE conversation_id = %(cid)s AND id <> %(jid)s "
            "  AND status IN ('pending','claimed','running') LIMIT 1",
            {"cid": conversation_id, "jid": int(exclude_job_id)},
        )
        return cur.fetchone() is not None


def latest_terminal_job_for_conversation(
    conn, conversation_id: str
) -> Optional[dict[str, Any]]:
    """활성 job 이 **없는** 대화의 마지막 terminal job(status/run_id/error) 조회.

    conv-audit FR-early-return-kv-never-finalized(봉인 B). `/api/ask_result` 는 terminal
    판정을 KV `last_status` **단일 소스**로 했다. 그런데 KV 는 run 이 남기는 값이라, run 이
    KV 를 마감하지 못하고 끝나면(조기 종료·프로세스 소실) 프런트가 45초 주기로 무한 폴링한다.
    `ask_jobs` 에는 그때도 `status='error'` 라는 **더 권위적인 종료 사실**이 이미 있으므로,
    KV 가 비-terminal 이어도 이쪽을 backstop 으로 읽는다(내부 attach 루프가 job_id 로 하는
    것과 동일한 보증을 재접속 폴백 경로에도 대칭으로 준다).

    **활성(pending/running) job 이 하나라도 있으면 None** — 새 요청이 막 시작된 대화에서
    직전 run 의 terminal 을 보고 "끝났다" 고 오판하면 진행 중 답변을 놓치기 때문이다.
    이 가드가 backstop 의 안전 조건이다.
    """
    with conn.cursor() as cur:
        # `claimed` 포함이 계약이다(§18.8 codex [P1]) — claim~running 사이 상태를 활성에서
        # 빠뜨리면 그 창에 들어온 backstop 이 **직전 run 의 terminal** 을 돌려주어 진행 중
        # 답변을 끊는다. 테이블 CHECK 제약과 sweep 의 활성 집합도 셋을 함께 본다.
        cur.execute(
            "SELECT 1 FROM agent_runtime.ask_jobs "
            "WHERE conversation_id = %(cid)s "
            "  AND status IN ('pending','claimed','running') LIMIT 1",
            {"cid": conversation_id},
        )
        if cur.fetchone() is not None:
            return None
        cur.execute(
            "SELECT id, run_id, status, result_json, finished_at "
            "FROM agent_runtime.ask_jobs "
            "WHERE conversation_id = %(cid)s AND status IN ('done','error','canceled') "
            "ORDER BY id DESC LIMIT 1",
            {"cid": conversation_id},
        )
        row = cur.fetchone()
    if not row:
        return None
    result_json = row[3]
    if isinstance(result_json, (str, bytes, bytearray)):
        try:
            result_json = json.loads(result_json)
        except Exception:
            result_json = None
    err = ""
    if isinstance(result_json, dict):
        err = str(result_json.get("error") or "").strip()
    return {
        "id": int(row[0]),
        "run_id": row[1] or "",
        "status": row[2],
        "error": err,
        "finished_at": row[4],
    }


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


# ──────────────────────────────────────────────────────────────────────────
# 재배포 인계 (conv-audit FR-ask-orphan-redeploy-dead-air)
#
# 배포는 ask-worker 컨테이너를 --force-recreate 한다(bin/deploy-web.sh). 그러면
#   (1) 실행 중이던 run 이 죽고,
#   (2) 새 컨테이너의 hostname 이 바뀌어 위 `reclaim_worker_jobs_on_boot` 의
#       `claimed_by = worker_id` 정확일치가 **항상 0행**이 되며,
#   (3) 고아 job 은 전역 stale sweeper 의 STALE_SEC(수백초) 창을 통째로 기다린다.
# 실측 dead-air 142~1649s(60일 8대화). 아래 두 함수가 그 창을 봉인한다:
#   - release_worker_jobs_on_shutdown: 죽기 **전에** 자기 소유 lease 를 명시 반납(정상 종료 경로)
#   - reclaim_role_orphan_jobs:        SIGKILL 로 반납을 못 한 경우의 backstop(같은 role 의 죽은 이전 인스턴스)
# 둘 다 기존 requeue 와 동일한 상태 전이(pending + lease_epoch++ fencing)를 쓴다 — 새 전이 없음.
# ──────────────────────────────────────────────────────────────────────────
def release_worker_jobs_on_shutdown(
    conn, worker_id_prefix: str, *, attempts_cap: int
) -> list[dict[str, Any]]:
    """graceful shutdown 시 자기 소유 running job 의 lease 를 즉시 반납(requeue).

    `worker_id_prefix` 는 `_worker_id()` 값. 병렬 모드의 executor 는 `<worker_id>#<k>`
    로 claim 하므로 **prefix 매칭**(자기 자신 + 자기 슬롯 전부)이다. 다른 인스턴스/role 의
    행은 prefix 가 달라 매칭되지 않는다(오회수 불가).

    attempts 는 건드리지 않는다 — claim 시점에 증가하므로 여기서 더하면 cap 을 이중 소모한다.
    대신 **`attempts < cap` 인 행만 반납**한다(claim SQL 에 cap 게이트가 없어, cap 초과 행을
    pending 으로 돌리면 무한 재실행이 된다 — 적대 리뷰 backend H2). cap 도달 행은 running 인
    채 남겨 전역 sweeper 의 terminal-error 분기가 KV 정리까지 맡는다(기존 계약).

    lease_epoch++ 는 아직 살아 있는 자기 executor 스레드를 fencing 한다. 호출부
    (`_release_own_leases`)가 반납 직후 cancel 도 마킹해 겹침 창을 heartbeat 주기가 아니라
    cancel 폴링 주기로 좁힌다.

    Returns: 반납된 행 [{id, conversation_id, run_id}].
    """
    if not str(worker_id_prefix or "").strip():
        return []
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE agent_runtime.ask_jobs "
            "SET status = 'pending', claimed_by = NULL, claimed_at = NULL, "
            "    started_at = NULL, heartbeat_at = NULL, lease_epoch = lease_epoch + 1 "
            "WHERE status = 'running' "
            "  AND (claimed_by = %(worker)s OR claimed_by LIKE %(worker_like)s) "
            "  AND attempts < %(cap)s "
            "RETURNING id, conversation_id, run_id",
            {"worker": worker_id_prefix,
             "worker_like": _like_prefix(worker_id_prefix) + "#%",
             "cap": int(attempts_cap)},
        )
        return [{"id": int(r[0]), "conversation_id": r[1], "run_id": r[2]}
                for r in cur.fetchall()]


def reclaim_role_orphan_jobs(
    conn, *, role_prefix: str, self_prefix: str, stale_seconds: int, attempts_cap: int
) -> dict[str, list[dict[str, Any]]]:
    """같은 worker role 의 **죽은 이전 인스턴스**가 남긴 running job 을 회수.

    전역 `sweep_stale_jobs` 의 STALE_SEC 은 정상 장기 run 오회수를 막으려 매우 크게 잡혀
    있다. 그러나 heartbeat 는 시간 기반(HEARTBEAT_SEC=10s, step 무관)이라 그보다 훨씬 짧은
    창으로도 "프로세스가 죽었다" 를 안전하게 판정할 수 있다. 그 짧은 창을 **자기 role 의
    다른 인스턴스** 로만 좁혀 적용한다(cross-role 오판 없음).

    `self_prefix` 소유 행은 제외한다 — 자기 executor 는 살아 있고, 자기 잔재는 boot
    self-reclaim(`reclaim_worker_jobs_on_boot`)이 이미 처리한다. `self_prefix` 가 비면
    제외 술어가 무력해져 자기 행까지 회수하므로 **호출 자체를 거부**한다.

    cap 회계는 `sweep_stale_jobs` 와 동일 — `attempts >= cap` 은 requeue 가 아니라 terminal
    error(무한 재실행 차단, 적대 리뷰 backend H2). 두 분기 모두 `lease_epoch++` 로 fencing.

    Returns: {"requeued": [...], "errored": [...]} (각 {id, conversation_id, run_id}).
    """
    role_prefix = str(role_prefix or "").strip()
    self_prefix = str(self_prefix or "").strip()
    if not role_prefix or not self_prefix:
        return {"requeued": [], "errored": []}
    params = {
        "role_like": _like_prefix(role_prefix) + "%",
        "self": self_prefix,
        "self_like": _like_prefix(self_prefix) + "#%",
        "stale": int(stale_seconds),
        "cap": int(attempts_cap),
    }
    _scope = (
        "WHERE status = 'running' "
        "  AND claimed_by LIKE %(role_like)s "
        "  AND NOT (claimed_by = %(self)s OR claimed_by LIKE %(self_like)s) "
        "  AND heartbeat_at IS NOT NULL "
        "  AND heartbeat_at < now() - make_interval(secs => %(stale)s) "
    )
    errored: list[dict[str, Any]] = []
    requeued: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        # 1) cap 도달 → terminal error (전역 sweeper 와 동일 회계)
        cur.execute(
            "UPDATE agent_runtime.ask_jobs "
            "SET status = 'error', finished_at = now(), lease_epoch = lease_epoch + 1 "
            + _scope + "  AND attempts >= %(cap)s "
            "RETURNING id, conversation_id, run_id",
            params,
        )
        for r in cur.fetchall():
            errored.append({"id": int(r[0]), "conversation_id": r[1], "run_id": r[2]})
        # 2) cap 미만 → requeue
        cur.execute(
            "UPDATE agent_runtime.ask_jobs "
            "SET status = 'pending', claimed_by = NULL, claimed_at = NULL, "
            "    started_at = NULL, heartbeat_at = NULL, lease_epoch = lease_epoch + 1 "
            + _scope + "  AND attempts < %(cap)s "
            "RETURNING id, conversation_id, run_id",
            params,
        )
        for r in cur.fetchall():
            requeued.append({"id": int(r[0]), "conversation_id": r[1], "run_id": r[2]})
    return {"requeued": requeued, "errored": errored}


def _like_prefix(s: str) -> str:
    """LIKE 패턴에서 리터럴로 다뤄야 할 와일드카드(`%`/`_`)와 escape 문자를 이스케이프.

    worker id 는 hostname/role 파생이라 통상 와일드카드가 없지만, 오염된 값이 들어와도
    매칭 범위가 넓어지지 않도록 봉인한다(기본 escape 문자 `\\`).
    """
    return (str(s or "").replace("\\", "\\\\")
            .replace("%", "\\%").replace("_", "\\_"))
