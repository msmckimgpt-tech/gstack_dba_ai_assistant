import re
__all__ = [
    "_cancel_requested",
    "_clear_cancel_request",
    "_finalize_requested",
    "_clear_finalize_request",
    "mark_finalize_requested",
    "_purge_run_steps",
    "_record_step_summary",
    "clear_memory_tables",
    "cleanup_pending_delete_conversations",
    "create_conversation",
    "delete_conversation",
    "delete_all_conversations",
    "ensure_memory_schema",
    "is_delete_requested",
    "is_processing_conversation",
    "list_conversations",
    "list_delete_requested_conversation_ids",
    "list_processing_conversation_ids",
    "load_memory_context",
    "load_memory_kv",
    "load_memory_kv_all",
    "load_recent_steps",
    "load_step_trace_from_kv",
    "mark_cancel_requested",
    "mark_delete_requested",
    "save_memory_kv",
    "save_memory_message",
    "save_memory_step",
    "save_memory_summary",
    "set_run_status",
]


"""Memory table CRUD operations and conversation management."""
from shared.config import *
from shared import config as cfg
import json, re
from datetime import datetime, timezone
from typing import Any


def _is_truthy_flag(value: Any) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes")

def ensure_memory_schema() -> None:
    pass  # PG cutover 완료 — MySQL schema 재생성 불필요

def load_memory_context(conn, conversation_id: str, max_turns: int):
    # M4: PG read path — summary + messages + kv 를 각각 PgRuntimeBackend read method 로.
    from .runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        max_fetch = max(10, max_turns * 3)
        summary_pg = _read_runtime_pg("load_summary", conversation_id=conversation_id)
        msgs_pg = _read_runtime_pg("load_messages", conversation_id=conversation_id, limit=max_fetch)
        kv_pg = _read_runtime_pg("load_kv_all", conversation_id=conversation_id)
        if summary_pg is not None and msgs_pg is not None and kv_pg is not None:
            rows: list = []
            for role, content, meta_json, created_at in msgs_pg:
                if _is_internal_message(role, content, meta_json):
                    continue
                rows.append((role, content, created_at))
                if len(rows) >= max_turns:
                    break
            rows.reverse()
            kv = {k: v for k, v in kv_pg}
            return summary_pg, rows, kv
        # one of the PG reads returned None (connection/method failure) — log and fall through to MySQL
        import logging as _lg
        _lg.getLogger("agent_core.memory").warning(
            "load_memory_context: PG partial failure (summary=%s msgs=%s kv=%s), falling back to MySQL",
            summary_pg is not None, msgs_pg is not None, kv_pg is not None,
        )

    cur = conn.cursor()

    cur.execute(
        """
SELECT Summary
FROM AgentMemorySummary
WHERE ConversationId = %s
LIMIT 1
        """,
        (conversation_id,),
    )
    row = cur.fetchone()
    summary = row[0] if row else None

    max_fetch = max(10, max_turns * 3)
    cur.execute(
        """
SELECT Role, Content, MetaJson, CreatedAt
FROM AgentMemoryMessages
WHERE ConversationId = %s
ORDER BY CreatedAt DESC
LIMIT %s
        """,
        (conversation_id, max_fetch),
    )
    fetched = cur.fetchall() or []
    rows: list[tuple[str, str, datetime]] = []
    for role, content, meta_json, created_at in fetched:
        if _is_internal_message(role, content, meta_json):
            continue
        rows.append((role, content, created_at))
        if len(rows) >= max_turns:
            break
    rows.reverse()

    cur.execute(
        """
SELECT `Key`, `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s
        """,
        (conversation_id,),
    )
    kv_rows = cur.fetchall() or []
    cur.close()

    kv = {k: v for k, v in kv_rows}
    return summary, rows, kv


def save_memory_message(
    conn,
    conversation_id: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
    core_message_id: int | None = None,
    parent_message_id: int | None = None,
    edit_root_message_id: int | None = None,
    edit_version: int = 1,
) -> int:
    """표시 store(messages) 쓰기 choke-point.

    feature-0019 message-editing: 편집으로 브랜치가 생긴 대화(has_branches=true)면 이 append 를
    display 활성 leaf(active_display_leaf)에 체인하고 leaf 를 전진시킨다 — 정상 대화는 조회 후
    즉시 기존 INSERT 경로(회귀 0). parent/edit/core_message_id 명시(엔드포인트 sibling 생성) 시
    그 값으로 브랜치 포인터·링크를 기록. 반환 = 신규 display 메시지 id(internal-skip 시 0).
    """
    meta_json = None
    auto_meta = dict(meta) if isinstance(meta, dict) else {}
    is_internal = False
    if role == "assistant":
        internal_flag = auto_meta.get("internal")
        if internal_flag is True:
            is_internal = True
            auto_meta["internal"] = True
        elif internal_flag is not False and _should_mark_internal_message(content):
            is_internal = True
            auto_meta["internal"] = True
    if is_internal and not AGENT_STORE_INTERNAL_MESSAGES:
        return 0
    if cfg.CURRENT_RUN_ID and "run_id" not in auto_meta:
        auto_meta["run_id"] = cfg.CURRENT_RUN_ID
    if auto_meta:
        try:
            meta_json = json.dumps(auto_meta, ensure_ascii=False)
        except Exception:
            meta_json = json.dumps({"value": str(auto_meta)}, ensure_ascii=False)
    from .runtime_backend import (
        _get_pg_runtime_backend, _get_pg_runtime_conn,
        branch_run_active, branch_chain_get, branch_chain_set,
    )
    pg_conn = _get_pg_runtime_conn()
    new_id = 0
    if pg_conn:
        try:
            backend = _get_pg_runtime_backend()
            _chain_parent = parent_message_id
            _advance_leaf = False
            # 명시 브랜치 인자(엔드포인트 sibling 생성)가 없으면 정상 append — 브랜치 대화면 체이닝.
            if _chain_parent is None and edit_version == 1 and edit_root_message_id is None:
                # feature-0019 branch-chain-race: 브랜치 run 이면 active_display_leaf 를 매 write 마다
                # 재-read 하지 않고 이 run 의 직전 display write id(커서)에 이어붙인다. 표시 store 는
                # 한 run 에 user·답변 2개만 쓰므로, 재-read 시 리셋된 active_display_leaf 때문에 답변이
                # user 의 형제로 붙어 active-path 걷기에서 user 가 사라지던 결함을 봉인한다.
                if branch_run_active():
                    _cur = branch_chain_get("disp")
                    if _cur is not None:
                        _chain_parent = _cur
                        _advance_leaf = True
                    else:
                        try:  # run 첫 display write: 분기점(active_display_leaf)만 1회 read
                            _bs = backend.load_display_branch_state(pg_conn, conversation_id=conversation_id)
                            if isinstance(_bs, dict) and _bs.get("has_branches"):
                                _chain_parent = _bs.get("active_leaf_id")
                            _advance_leaf = True
                        except Exception:
                            _chain_parent = None
                else:
                    try:
                        _bs = backend.load_display_branch_state(pg_conn, conversation_id=conversation_id)
                        if isinstance(_bs, dict) and _bs.get("has_branches"):
                            _chain_parent = _bs.get("active_leaf_id")
                            _advance_leaf = True
                    except Exception:
                        _chain_parent = None  # fail-soft → 기존 linear append
            new_id = backend.save_memory_message(pg_conn,
                conversation_id=conversation_id, role=role,
                content=content, meta_json=meta_json,
                parent_message_id=_chain_parent, edit_root_message_id=edit_root_message_id,
                edit_version=edit_version, core_message_id=core_message_id)
            if _advance_leaf and new_id:
                try:
                    backend.set_active_display_leaf(pg_conn, conversation_id=conversation_id, leaf_id=new_id)
                except Exception as _exc2:
                    import logging as _log
                    _log.getLogger("agent_core.memory").warning("display active_leaf advance failed: %s", _exc2)
                if branch_run_active():
                    branch_chain_set("disp", new_id)  # 다음 display write 가 이 id 에 이어붙도록 커서 전진
        except Exception as _exc:
            import logging as _log
            _log.getLogger("agent_core.memory").warning("save_memory_message PG write failed: %s", _exc)
        finally:
            pg_conn.close()
    return new_id


def save_memory_kv(conn, conversation_id: str, key: str, value: str) -> None:
    # TASK-0127 (#1): 2026-05-27 MySQL→PG cutover 잔재 수정. 이전엔 DROP 된 MySQL
    # `AgentMemoryKV` 에 raw INSERT 를 하고 (`except: pass` 로 오류를 삼킴) PG mirror 는
    # `AGENT_RUNTIME_DUAL_WRITE`(기본 off) 게이트라, KV 쓰기가 2026-05-27 부터 조용히
    # 동결돼 run status/topic/last_sql/insight heartbeat 가 갱신되지 않았다. message/step/
    # summary 와 동일하게 PG 런타임 백엔드로 직접 쓴다 (conn 인자는 시그니처 호환용으로 유지).
    from .runtime_backend import _get_pg_runtime_backend, _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if pg_conn:
        try:
            _get_pg_runtime_backend().save_kv(pg_conn,
                conversation_id=conversation_id, key=key, value=value)
        except Exception as _exc:
            import logging as _log
            _log.getLogger("agent_core.memory").warning("save_memory_kv PG write failed: %s", _exc)
        finally:
            pg_conn.close()


def load_memory_kv(conn, conversation_id: str, key: str) -> str:
    # M4: PG read path (fail-soft, AGENT_RUNTIME_READ_BACKEND=postgres 시 활성)
    from .runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        result = _read_runtime_pg("load_kv", conversation_id=conversation_id, key=key)
        if result is not None:
            return result

    cur = conn.cursor()
    cur.execute(
        """
SELECT `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s AND `Key` = %s
LIMIT 1
        """,
        (conversation_id, key),
    )
    row = cur.fetchone()
    cur.close()
    return str(row[0]) if row else ""


def load_memory_kv_all(conn, conversation_id: str) -> dict[str, str]:
    # M4: PG read path
    from .runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        rows_pg = _read_runtime_pg("load_kv_all", conversation_id=conversation_id)
        if rows_pg is not None:
            return {k: v for k, v in rows_pg}

    cur = conn.cursor()
    cur.execute(
        """
SELECT `Key`, `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s
        """,
        (conversation_id,),
    )
    rows = cur.fetchall() or []
    cur.close()
    return {k: v for k, v in rows}


def set_run_status(
    conn,
    conversation_id: str,
    status: str,
    run_id: str = "",
    duration_ms: float | None = None,
    error: str | None = None,
    only_if_current_run: bool = False,
) -> None:
    if not conversation_id:
        return
    # TASK-0241: supersede 가드 — 취소→즉시 재요청 흐름에서, 뒤늦게 종료하는
    # old(superseded) run 이 새 run 이 인계한 상태(last_status_run_id)를 덮어쓰지 못하게 한다.
    # only_if_current_run=True 면 저장된 last_status_run_id 가 *다른* run 을 가리킬 때 write 를
    # 통째로 건너뛴다. (_clear_cancel_request 의 run_id-gating 과 동형 — read-then-write 는
    # 비원자적이나, orphan 의 terminal write 는 새 run claim 보다 수 초 뒤라 실질 race 가 없다.)
    # claim/heartbeat/enqueue 선기록 등 takeover 가 정당한 write 는 only_if_current_run=False(기본)
    # 로 기존 무조건 semantics 를 유지한다.
    if only_if_current_run and str(run_id or "").strip():
        try:
            cur_rid = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        except Exception:
            cur_rid = ""
        if cur_rid and cur_rid != str(run_id).strip():
            # feature-0009 그룹대화 동시 run 충돌: 다른 run 이 대화 상태 슬롯(last_status_run_id)을
            # 점유 중이라 이 run 의 terminal write 가 통째로 유실된다. 단일 run 대화에선 이게 옳지만
            # (취소→재요청 supersede 가드), 그룹대화는 계정별 동시 run 이 설계상 허용(REQ-GC-R3)이라
            # run1 의 done/error 가 영영 기록 안 돼 그 run 을 추적하는 클라이언트가 '처리 중' 에 갇힌다.
            # → 작성자가 완료를 *기다리는* 종료(done/error)만 per-run marker 로 남겨, /api/progress 가
            # client_run_id 로 자기 run 을 해소하게 한다. canceled 는 작성자가 이미 추적을 멈춘
            # (취소→재요청 supersede 포함) 상태라 해소 대상이 없어 기록하지 않는다 → 1:1 취소-재요청
            # 등에서의 불필요한 키 누적을 차단. (충돌 시에만, done/error 만 기록 → 단일 run 정상 흐름엔
            # 미기록. 잔여 done/error 충돌 marker 의 일괄 정리는 FUNCTION §4 S6 per-thread 재키잉으로 이연.)
            _st = str(status).strip().lower()
            if _st in ("done", "error"):
                _rid = str(run_id).strip()
                try:
                    save_memory_kv(conn, conversation_id, f"run_term_status:{_rid}", str(status))
                    save_memory_kv(conn, conversation_id, f"run_term_at:{_rid}", utc_now_iso())
                except Exception:
                    pass
            return
    # TASK-0169 (M4): run_id 를 status 보다 먼저 기록한다. set_run_status 는 멀티-tx
    # (save_memory_kv 마다 독립 PG tx) 라, status 를 먼저 쓰면 reader 가 terminal status
    # 를 직전 run 의 run_id 로 잘못 귀속해 읽는 torn-read 창이 생긴다. run_id→status
    # 순서면 reader 가 보는 terminal status 는 항상 올바른 run_id 와 짝지어진다.
    if run_id:
        save_memory_kv(conn, conversation_id, "last_status_run_id", run_id)
    save_memory_kv(conn, conversation_id, "last_status", str(status))
    save_memory_kv(conn, conversation_id, "last_status_at", utc_now_iso())
    if duration_ms is not None:
        save_memory_kv(conn, conversation_id, "last_duration_ms", str(duration_ms))
    if error is not None:
        save_memory_kv(conn, conversation_id, "last_error", str(error))


def is_processing_conversation(conn, conversation_id: str) -> bool:
    if not conversation_id:
        return False
    return str(load_memory_kv(conn, conversation_id, "last_status") or "").strip().lower() == "processing"


def is_delete_requested(conn, conversation_id: str) -> bool:
    if not conversation_id:
        return False
    return _is_truthy_flag(load_memory_kv(conn, conversation_id, "delete_requested"))


def list_processing_conversation_ids(conn) -> list[str]:
    # M4: PG read path
    from .runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        result = _read_runtime_pg("load_kv_by_key_value", key="last_status", value="processing")
        if result is not None:
            return result

    cur = conn.cursor()
    cur.execute(
        """
SELECT ConversationId
FROM AgentMemoryKv
WHERE `Key` = 'last_status' AND `Value` = 'processing'
        """
    )
    rows = cur.fetchall() or []
    cur.close()
    return [str(row[0]) for row in rows if row and row[0]]


def list_delete_requested_conversation_ids(conn) -> list[str]:
    # M4: PG read path — fetch all delete_requested rows, filter truthy client-side (MySQL 패리티).
    # load_kv_by_key returns (conversation_id, value) tuples; _is_truthy_flag mirrors MySQL semantics.
    from .runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        kv_rows = _read_runtime_pg("load_kv_by_key", key="delete_requested")
        if kv_rows is not None:
            return [conv_id for conv_id, val in kv_rows if _is_truthy_flag(val)]

    cur = conn.cursor()
    cur.execute(
        """
SELECT ConversationId, `Value`
FROM AgentMemoryKv
WHERE `Key` = 'delete_requested'
        """
    )
    rows = cur.fetchall() or []
    cur.close()
    ids: list[str] = []
    for row in rows:
        conv_id = str(row[0] or "").strip() if row else ""
        raw_value = row[1] if row and len(row) > 1 else ""
        if conv_id and _is_truthy_flag(raw_value):
            ids.append(conv_id)
    return ids


def mark_cancel_requested(conn, conversation_id: str, run_id: str = "", preserve_reasoning: bool = False) -> None:
    if not conversation_id:
        return
    effective_run_id = str(run_id or "").strip() or load_memory_kv(conn, conversation_id, "last_status_run_id")
    save_memory_kv(conn, conversation_id, "cancel_requested", "1")
    save_memory_kv(conn, conversation_id, "cancel_run_id", str(effective_run_id or "").strip())
    save_memory_kv(conn, conversation_id, "cancel_at", utc_now_iso())
    # composer-nonblock-interrupt R3: 1:1 인터럽트 재요청은 이 run 의 부분 추론을 폐기하지 않고 보존한다.
    # run_agent 의 canceled 분기가 이 플래그(cancel_run_id 와 짝)를 읽어 부분 추론을 메시지로 저장한다.
    # 명시 '중단'(preserve=False)은 "0" 으로 덮어 이전 인터럽트 잔재 플래그가 오해석되지 않게 한다.
    save_memory_kv(conn, conversation_id, "cancel_preserve", "1" if preserve_reasoning else "0")


def mark_delete_requested(conn, conversation_id: str, run_id: str = "") -> None:
    if not conversation_id:
        return
    effective_run_id = str(run_id or "").strip() or load_memory_kv(conn, conversation_id, "last_status_run_id")
    save_memory_kv(conn, conversation_id, "delete_requested", "1")
    save_memory_kv(conn, conversation_id, "delete_run_id", str(effective_run_id or "").strip())
    save_memory_kv(conn, conversation_id, "delete_requested_at", utc_now_iso())


def _cancel_requested(conn, conversation_id: str, run_id: str) -> bool:
    if not conversation_id:
        return False
    try:
        flag = load_memory_kv(conn, conversation_id, "cancel_requested")
        if str(flag or "").strip() not in ("1", "true", "yes"):
            return False
        cancel_run = load_memory_kv(conn, conversation_id, "cancel_run_id")
        cancel_run = str(cancel_run or "").strip()
        if cancel_run and cancel_run != run_id:
            return False
        return True
    except Exception:
        return False


def _clear_cancel_request(conn, conversation_id: str, run_id: str = "") -> None:
    # TASK-0169 (MJ-2): run_id 지정 시, 저장된 cancel_run_id 가 *다른* run 을 겨냥하면
    # 지우지 않는다. ask-worker fencing 은 lease 박탈된 worker(run R1)를 멈추려 cancel 을
    # R1 으로 마킹하는데, 같은 conversation 의 새 worker(run R2)가 종료하며 무조건 clear
    # 하면 R1 대상 cancel 이 지워져 R1 이 계속 돌 수 있다(double-run). cancel_run_id 가
    # 빈값이거나 내 run 과 같을 때만 clear 한다.
    rid = str(run_id or "").strip()
    if rid:
        try:
            cancel_run = str(load_memory_kv(conn, conversation_id, "cancel_run_id") or "").strip()
        except Exception:
            cancel_run = ""
        if cancel_run and cancel_run != rid:
            return
    save_memory_kv(conn, conversation_id, "cancel_requested", "")
    save_memory_kv(conn, conversation_id, "cancel_run_id", "")
    save_memory_kv(conn, conversation_id, "cancel_at", "")
    # composer-nonblock-interrupt R3: preserve 플래그도 함께 정리(위생) — cancel_requested 와 짝으로
    # 매 cancel 마다 mark_cancel_requested 가 새로 세팅하므로 stale read 는 없으나, lingering 키 누적을 차단.
    save_memory_kv(conn, conversation_id, "cancel_preserve", "")


def mark_finalize_requested(conn, conversation_id: str, run_id: str = "") -> None:
    """즉시 답변 요청 플래그 설정."""
    if not conversation_id:
        return
    effective_run_id = str(run_id or "").strip() or load_memory_kv(conn, conversation_id, "last_status_run_id")
    save_memory_kv(conn, conversation_id, "finalize_requested", "1")
    save_memory_kv(conn, conversation_id, "finalize_run_id", str(effective_run_id or "").strip())


def _finalize_requested(conn, conversation_id: str, run_id: str) -> bool:
    """즉시 답변 플래그가 설정되어 있는지 확인."""
    if not conversation_id:
        return False
    try:
        flag = load_memory_kv(conn, conversation_id, "finalize_requested")
        if str(flag or "").strip() not in ("1", "true", "yes"):
            return False
        fin_run = load_memory_kv(conn, conversation_id, "finalize_run_id")
        fin_run = str(fin_run or "").strip()
        if fin_run and fin_run != run_id:
            return False
        return True
    except Exception:
        return False


def _clear_finalize_request(conn, conversation_id: str) -> None:
    save_memory_kv(conn, conversation_id, "finalize_requested", "")
    save_memory_kv(conn, conversation_id, "finalize_run_id", "")


# ── feature-0030 실행 타임아웃 연장 시그널 ────────────────────────────────────
# cancel/finalize 와 동일한 memory KV 왕복 패턴. 방향이 둘이라는 점만 다르다:
#   prompted : 워커 → 사용자 ("예산 80% 소진 — 계속 추론할까요?")
#   granted  : 사용자 → 워커 ("이 run 은 타임아웃과 무관하게 끝까지")
# 두 플래그 모두 run_id 짝 검증으로 이전 run 을 겨냥한 stale 신호를 격리한다
# (검증 없으면 직전 요청의 승인이 다음 요청을 무기한 연장시킨다).

def mark_timeout_extension_prompted(
    conn, conversation_id: str, run_id: str = "", deadline_at: str = "",
) -> None:
    """실행 예산 임계 도달 — 사용자에게 연장 여부를 물었음을 기록(run 당 1회)."""
    if not conversation_id:
        return
    effective_run_id = str(run_id or "").strip() or load_memory_kv(conn, conversation_id, "last_status_run_id")
    # KV 는 conversation 당 단일 슬롯이다. 새 run 의 prompt 가 run_id 만 덮어쓰면 이전 run 의
    # granted=1 이 그대로 남아 **새 run 이 남의 승인을 상속**한다(codex 적대 리뷰 P1-2).
    # prompt 는 그 run 상태의 시작점이므로 승인 흔적을 함께 리셋한다.
    save_memory_kv(conn, conversation_id, "timeout_ext_granted", "")
    save_memory_kv(conn, conversation_id, "timeout_ext_granted_at", "")
    save_memory_kv(conn, conversation_id, "timeout_ext_prompted", "1")
    save_memory_kv(conn, conversation_id, "timeout_ext_run_id", str(effective_run_id or "").strip())
    save_memory_kv(conn, conversation_id, "timeout_ext_prompted_at", utc_now_iso())
    # deadline_at = 승인이 없을 때 실제로 타임아웃될 예상 시각(ISO). 프론트가 남은 시간을 표시.
    save_memory_kv(conn, conversation_id, "timeout_ext_deadline_at", str(deadline_at or "").strip())


def mark_timeout_extension_granted(conn, conversation_id: str, run_id: str) -> bool:
    """사용자가 '타임아웃과 무관하게 끝까지' 를 승인 — 워커 루프가 폴링해 소비한다.

    `run_id` 는 **필수**다. 빈 값을 허용하면 아래 짝 검증이 wildcard 로 퇴화해 사용자가 보지도
    않은 run 이 연장된다(codex 적대 리뷰 P1-1). 승인은 **사용자가 배너에서 본 그 run** 에만
    붙어야 하므로, 현재 prompt 가 걸린 run 과 다르면 기록하지 않고 False 를 돌려준다.
    """
    rid = str(run_id or "").strip()
    if not conversation_id or not rid:
        return False
    prompted_run = str(load_memory_kv(conn, conversation_id, "timeout_ext_run_id") or "").strip()
    if prompted_run and prompted_run != rid:
        return False  # 배너가 가리키던 run 이 이미 교체됨 — 승인 대상 불일치.
    save_memory_kv(conn, conversation_id, "timeout_ext_granted", "1")
    save_memory_kv(conn, conversation_id, "timeout_ext_run_id", rid)
    save_memory_kv(conn, conversation_id, "timeout_ext_granted_at", utc_now_iso())
    return True


def _timeout_extension_granted(conn, conversation_id: str, run_id: str) -> bool:
    """이 run 에 대한 연장 승인이 있는지. 실패는 fail-safe(승인 없음)로 흡수."""
    rid = str(run_id or "").strip()
    if not conversation_id or not rid:
        return False
    try:
        flag = load_memory_kv(conn, conversation_id, "timeout_ext_granted")
        if str(flag or "").strip() not in ("1", "true", "yes"):
            return False
        ext_run = str(load_memory_kv(conn, conversation_id, "timeout_ext_run_id") or "").strip()
        # 빈 ext_run 을 '일치'로 보면 정리 중이거나 유실된 상태가 wildcard 승인이 된다 —
        # 정확히 같은 run 일 때만 승인으로 인정한다(엄격 비교).
        return ext_run == rid
    except Exception:
        return False


def timeout_extension_state(conn, conversation_id: str) -> dict:
    """`/api/ask_status`·`/api/ask_result` 스냅샷용 연장 상태.

    run_id 는 그대로 실어 보내고 **짝 검증은 소비측(프론트)이 현재 run 과 대조**한다 —
    스냅샷 빌더는 자기가 어느 run 을 그리는지 이미 알고 있으므로 여기서 거르지 않는다.
    """
    empty = {"prompted": False, "granted": False, "deadline_at": "", "run_id": ""}
    if not conversation_id:
        return empty
    try:
        prompted = str(load_memory_kv(conn, conversation_id, "timeout_ext_prompted") or "").strip()
        granted = str(load_memory_kv(conn, conversation_id, "timeout_ext_granted") or "").strip()
        return {
            "prompted": prompted in ("1", "true", "yes"),
            "granted": granted in ("1", "true", "yes"),
            "deadline_at": str(load_memory_kv(conn, conversation_id, "timeout_ext_deadline_at") or "").strip(),
            "run_id": str(load_memory_kv(conn, conversation_id, "timeout_ext_run_id") or "").strip(),
        }
    except Exception:
        return empty


def _clear_timeout_extension(conn, conversation_id: str, run_id: str = "") -> None:
    """run terminal 시 정리. run_id 지정 시 *다른* run 을 겨냥한 신호는 남긴다
    (_clear_cancel_request 와 동일 사유 — 늦게 끝난 run 이 새 run 의 승인을 지우지 않게)."""
    if not conversation_id:
        return
    rid = str(run_id or "").strip()
    if rid:
        try:
            ext_run = str(load_memory_kv(conn, conversation_id, "timeout_ext_run_id") or "").strip()
        except Exception:
            ext_run = ""
        if ext_run and ext_run != rid:
            return
    save_memory_kv(conn, conversation_id, "timeout_ext_prompted", "")
    save_memory_kv(conn, conversation_id, "timeout_ext_granted", "")
    save_memory_kv(conn, conversation_id, "timeout_ext_run_id", "")
    save_memory_kv(conn, conversation_id, "timeout_ext_prompted_at", "")
    save_memory_kv(conn, conversation_id, "timeout_ext_granted_at", "")
    save_memory_kv(conn, conversation_id, "timeout_ext_deadline_at", "")


def _clear_delete_request(conn, conversation_id: str) -> None:
    save_memory_kv(conn, conversation_id, "delete_requested", "")
    save_memory_kv(conn, conversation_id, "delete_run_id", "")
    save_memory_kv(conn, conversation_id, "delete_requested_at", "")


def _purge_run_steps(conn, conversation_id: str, run_id: str) -> None:
    if not conversation_id or not run_id:
        return
    # TASK-0127 (#1): agent_runtime.steps (PG) 에서 삭제. MySQL AgentMemorySteps 는 DROP 됨.
    # 이전 코드는 except 없이 DROP 된 테이블에 DELETE → 호출 시 예외 전파(잠재 크래시)였다.
    from .runtime_backend import _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if not pg_conn:
        return
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM agent_runtime.steps WHERE conversation_id = %s AND run_id = %s",
                (conversation_id, run_id),
            )
        pg_conn.commit()
    except Exception as exc:
        import logging as _log
        _log.getLogger("agent_core.memory").warning("_purge_run_steps PG delete failed: %s", exc)
        try:
            pg_conn.rollback()
        except Exception:
            pass
    finally:
        try:
            pg_conn.close()
        except Exception:
            pass


def save_memory_summary(conn, conversation_id: str, summary: str) -> None:
    from .runtime_backend import _get_pg_runtime_backend, _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if pg_conn:
        try:
            _get_pg_runtime_backend().save_memory_summary(pg_conn,
                conversation_id=conversation_id, summary=summary)
        except Exception as _exc:
            import logging as _log
            _log.getLogger("agent_core.memory").warning("save_memory_summary PG write failed: %s", _exc)
        finally:
            pg_conn.close()


def save_memory_step(
    conn,
    conversation_id: str,
    run_id: str,
    entry: dict[str, Any],
) -> None:
    action = str(entry.get("action", "")).strip() or "step"
    tool = str(entry.get("tool", "")).strip()
    intent = str(entry.get("intent", "")).strip()
    work_text = str(entry.get("work", "") or "").strip()
    work_source = str(entry.get("work_source", "") or "").strip()
    reason_text = str(entry.get("reason", "") or "").strip()
    reason_source = str(entry.get("reason_source", "") or "").strip()
    args = entry.get("args", {})
    sql_text = str(entry.get("sql", "")).strip()
    result_summary = entry.get("result_summary", None)
    error_text = str(entry.get("error", "")).strip()

    try:
        args_json = json.dumps(args, ensure_ascii=False)
    except Exception:
        args_json = json.dumps({"value": str(args)}, ensure_ascii=False)

    result_json = None
    if result_summary is not None:
        try:
            result_json = json.dumps(result_summary, ensure_ascii=False)
        except Exception:
            result_json = json.dumps({"value": str(result_summary)}, ensure_ascii=False)

    step_index = int(entry.get("step_index", 0) or 0)
    from .runtime_backend import _get_pg_runtime_backend, _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if pg_conn:
        try:
            _get_pg_runtime_backend().save_memory_step(pg_conn,
                conversation_id=conversation_id, run_id=run_id,
                step_index=step_index, action=action, tool=tool, intent=intent,
                work_text=work_text or None, work_source=work_source or None,
                reason_text=reason_text or None, reason_source=reason_source or None,
                args_json=args_json, sql_text=sql_text or None,
                result_summary_json=result_json, error_text=error_text or None)
        except Exception as _exc:
            import logging as _log
            _log.getLogger("agent_core.memory").warning("save_memory_step PG write failed: %s", _exc)
        finally:
            pg_conn.close()


def _assemble_steps(rows: list) -> list[dict[str, Any]]:
    """step 행 튜플 목록 → dict 목록. MySQL + PG 공용 (컬럼 순서 동일).

    컬럼 순서: step_index, action, tool, intent, work_text, work_source,
               reason_text, reason_source, args_json, sql_text,
               result_summary_json, error_text, run_id, created_at
    """
    steps: list[dict[str, Any]] = []
    for (
        step_index, action, tool, intent, work_text, work_source,
        reason_text, reason_source, args_json, sql_text,
        result_json, error_text, run_id, created_at,
    ) in rows:
        try:
            args = json.loads(args_json) if args_json else {}
        except Exception:
            args = {}
        result_summary = None
        if result_json:
            try:
                result_summary = json.loads(result_json)
            except Exception:
                result_summary = result_json
        steps.append(
            {
                "step_index": int(step_index or 0),
                "action": str(action or ""),
                "tool": str(tool or ""),
                "intent": str(intent or ""),
                "work": str(work_text or ""),
                "work_source": str(work_source or ""),
                "reason": str(reason_text or ""),
                "reason_source": str(reason_source or ""),
                "args": args,
                "sql": str(sql_text or ""),
                "result_summary": result_summary,
                "error": str(error_text or ""),
                "run_id": str(run_id or ""),
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
            }
        )
    return steps


def load_recent_steps(
    conn,
    conversation_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    # M4: PG read path
    from .runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        pg_rows = _read_runtime_pg("load_steps", conversation_id=conversation_id, limit=limit)
        if pg_rows is not None:
            return _assemble_steps(list(reversed(list(pg_rows))))

    cur = conn.cursor()
    cur.execute(
        """
SELECT
    StepIndex,
    Action,
    Tool,
    Intent,
    WorkText,
    WorkSource,
    ReasonText,
    ReasonSource,
    ArgsJson,
    SqlText,
    ResultSummaryJson,
    ErrorText,
    RunId,
    CreatedAt
FROM AgentMemorySteps
WHERE ConversationId = %s
ORDER BY CreatedAt DESC
LIMIT %s
        """,
        (conversation_id, limit),
    )
    rows = cur.fetchall() or []
    cur.close()
    rows = list(rows)
    rows.reverse()
    return _assemble_steps(rows)


def load_step_trace_from_kv(kv: dict[str, str]) -> list[dict[str, Any]]:
    raw = kv.get("step_trace") if isinstance(kv, dict) else None
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            cleaned.append(item)
    return cleaned


def _record_step_summary(conn, conversation_id: str, summary_text: str | None) -> None:
    if not summary_text:
        return
    try:
        save_memory_kv(conn, conversation_id, "last_step_summary", summary_text)
    except Exception:
        pass


def create_conversation(conn, conversation_id: str, topic: str | None = None) -> None:
    topic_text = (topic or "").strip()
    if topic_text:
        save_memory_kv(conn, conversation_id, "topic", topic_text)
    save_memory_kv(conn, conversation_id, "created_at", utc_now_iso())


def list_conversations(conn, limit: int = 50):
    # M4: PG read path — core_conversations 테이블 사용 (proper created_at column)
    from .runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        rows_pg = _read_runtime_pg("list_conversations", limit=limit)
        if rows_pg is not None:
            return rows_pg

    cur = conn.cursor()
    cur.execute(
        """
SELECT
    c.ConversationId,
    COALESCE(t.`Value`, '(미설정)') AS Topic,
    c.`Value` AS CreatedAt
FROM AgentMemoryKv c
LEFT JOIN AgentMemoryKv t
    ON c.ConversationId = t.ConversationId
   AND t.`Key` = 'topic'
WHERE c.`Key` = 'created_at'
ORDER BY c.`Value` DESC
LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall() or []
    cur.close()
    return rows


def _pg_delete_conversation(conversation_id: str) -> None:
    """PG agent_runtime + public KB 테이블에서 대화 데이터 삭제."""
    import logging as _log
    from .runtime_backend import _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if pg_conn is None:
        return
    try:
        with pg_conn.cursor() as cur:
            # kv는 CASCADE 제외 — 수동 삭제
            cur.execute("DELETE FROM agent_runtime.kv WHERE conversation_id = %s", (conversation_id,))
            # core_conversations 삭제 시 CASCADE: core_messages, messages, steps, summary
            cur.execute("DELETE FROM agent_runtime.core_conversations WHERE conversation_id = %s", (conversation_id,))
            # KB public 테이블
            cur.execute("DELETE FROM public.fact_entries WHERE conversation_id = %s", (conversation_id,))
            cur.execute("DELETE FROM public.rag_documents WHERE conversation_id = %s", (conversation_id,))
            cur.execute("DELETE FROM public.rag_objects WHERE conversation_id = %s", (conversation_id,))
        pg_conn.commit()
    except Exception as exc:
        _log.getLogger(__name__).warning("_pg_delete_conversation: %s", exc)
        try:
            pg_conn.rollback()
        except Exception:
            pass
    finally:
        try:
            pg_conn.close()
        except Exception:
            pass


def delete_conversation(conn, conversation_id: str) -> None:
    # TASK-0127 (#1): 모든 런타임/KB 데이터는 PG (agent_kb) 에 있다. MySQL Agent*/AgentCore*
    # 테이블은 2026-05-27 DROP 됐으므로 기존 MySQL DELETE 루프는 dead no-op 이라 제거.
    # _pg_delete_conversation 이 agent_runtime.kv/core_conversations(CASCADE) + public.fact_entries/
    # rag_documents/rag_objects 를 모두 삭제한다. conn 인자는 caller 시그니처 호환용으로 유지.
    _pg_delete_conversation(conversation_id)


def _list_all_conversation_ids(conn) -> list[str]:
    # TASK-0127 (#1): PG (agent_kb) 에서 conversation_id 수집. MySQL Agent*/AgentCore* DROP 됨
    # → 이전 MySQL 조회는 항상 [] 반환 → delete_all_conversations 가 무동작이었다.
    from .runtime_backend import _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if not pg_conn:
        return []
    ids: set[str] = set()
    table_specs = (
        ("agent_runtime.core_conversations", "conversation_id"),
        ("agent_runtime.kv", "conversation_id"),
        ("public.fact_entries", "conversation_id"),
        ("public.rag_documents", "conversation_id"),
        ("public.rag_objects", "conversation_id"),
    )
    try:
        with pg_conn.cursor() as cur:
            for table_name, column_name in table_specs:
                try:
                    cur.execute(
                        f"SELECT DISTINCT {column_name} FROM {table_name} "
                        f"WHERE {column_name} IS NOT NULL AND {column_name} <> ''"
                    )
                    for row in cur.fetchall() or []:
                        conv_id = str(row[0] or "").strip() if row else ""
                        if conv_id:
                            ids.add(conv_id)
                except Exception:
                    continue
    finally:
        try:
            pg_conn.close()
        except Exception:
            pass
    return sorted(ids)


def delete_all_conversations(conn, preserve_ids: tuple[str, ...] | list[str] | set[str] = ()) -> int:
    preserve = {str(item or "").strip() for item in preserve_ids if str(item or "").strip()}
    deleted = 0
    for conversation_id in _list_all_conversation_ids(conn):
        if conversation_id in preserve:
            continue
        delete_conversation(conn, conversation_id)
        deleted += 1
    return deleted


def cleanup_pending_delete_conversations(conn) -> int:
    deleted = 0
    for conversation_id in list_delete_requested_conversation_ids(conn):
        if is_processing_conversation(conn, conversation_id):
            continue
        delete_conversation(conn, conversation_id)
        deleted += 1
    return deleted


def clear_memory_tables(conn) -> None:
    processing_ids = list_processing_conversation_ids(conn)
    preserve_ids = sorted({*processing_ids, *AGENT_MEMORY_CLEAR_KEEP_IDS})
    delete_all_conversations(conn, preserve_ids=preserve_ids)


# ─────────────────────────────────────────────────────────────────────────────
# TASK-0015 §2.1.3 M1 (TASK-0018 cycle): KB Postgres pgvector schema 적용 함수.
#
# 본 함수는 multi-cycle plan 의 M2 dual-write phase 시작 시점에 1회 호출되어 KB
# Postgres database 의 5 KB 테이블 + VIEW + index + role grant 를 멱등 적용한다.
# M1 cycle 에서는 함수 정의만 — 호출 없음. M2 cycle 에서 memory-init service 또는
# bin/kb-pg-role-bootstrap.sh --apply-schema 가 호출.
#
# Idempotency: agent_kb_schema.sql 의 모든 DDL 이 IF NOT EXISTS / CREATE OR REPLACE
# 패턴이므로 반복 실행 안전. M3 backfill 후에도 다시 호출 가능 (schema 변경 없음).
#
# ADR-0021 (KB Postgres 분리 후 RBAC catalog 재정의) 의 실행 도구. 본 함수 호출 후
# `agent_kb_rw` / `agent_kb_ro` role 이 schema 권한을 가진다 (sql 의 DO $$ block).
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_pg_schema(conn=None, *, schema_sql_path: str | None = None) -> dict:
    """KB Postgres database 의 schema 를 멱등 적용한다.

    M2 dual-write phase 시작 시점에 1회 호출. 본 함수는 4 KB 테이블 +
    index + role grant 를 모두 적용하며 idempotent (다시 호출해도 안전).
    (TASK-0140: agent_memory_facts matview 폐기 — fact_entries 가 정본.)

    Args:
        conn: psycopg connection. None 이면 `_pg_connect()` 로 새 connection 열고
              종료 시 close. 호출자가 connection 을 외부에서 관리하려면 명시.
        schema_sql_path: agent_kb_schema.sql 의 절대 경로. None 이면 본 모듈 위치
                         기준으로 자동 탐색 (`../scripts/agent_kb_schema.sql`).

    Returns:
        dict: {
            "schema_applied": True,
            "tables_present": ["fact_entries", "texts", "rag_documents", "rag_objects"],
            "extensions": ["vector", "pg_trgm"],
        }

    Raises:
        RuntimeError: psycopg 또는 pgvector import 실패, 또는 agent_kb_schema.sql
                      파일 부재 (M1 cycle 의 산출 누락 신호).
        psycopg.errors.*: schema 적용 중 SQL 오류 (예: pgvector extension 미설치).
    """
    import os
    # B-3 (REV-20260526-0001 흡수): relative import 컨텍스트 부재 (__package__ is None,
    # agent_core.py 가 `python /app/agent_core.py` 로 직접 실행되는 경로) 일 때만
    # absolute import 로 fallback. `.db` 내부에서 발생한 실제 ImportError
    # (psycopg 부재 등) 까지 덮지 않도록 e.name 조건으로 범위 좁힘.
    try:
        from shared.db import _pg_connect, _pg_available
    except ImportError as _imp_err:
        if not (_imp_err.name is None or _imp_err.name == __package__):
            raise
        from db import _pg_connect, _pg_available  # type: ignore[no-redef]

    if not _pg_available():
        raise RuntimeError(
            "_ensure_pg_schema() 호출 시점에 _pg_available() == False. "
            "psycopg import + AGENT_KB_PG_* 환경변수 둘 다 갖춰져야 한다."
        )

    if schema_sql_path is None:
        # 본 모듈 위치 기준 ../scripts/agent_kb_schema.sql.
        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.normpath(os.path.join(here, "..", "scripts", "agent_kb_schema.sql"))
        if not os.path.isfile(candidate):
            raise RuntimeError(
                f"agent_kb_schema.sql 미발견: {candidate}. "
                f"M1 cycle 의 산출이 누락됐을 가능성 — git checkout 확인."
            )
        schema_sql_path = candidate

    with open(schema_sql_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # DDL (schema SQL) 적용: superuser connection 이 있으면 사용, 없으면 skip.
    # agent_kb_rw 는 DML 전용 role 이라 DDL (CREATE TABLE / EXTENSION 등) 권한 없음.
    # `kb-pg-role-bootstrap.sh --apply-schema` 가 이미 schema 를 적용했다면 skip 해도 무방.
    #
    # B-1 (REV-20260526-0001 흡수): runtime DDL credential 이름은 `AGENT_KB_PG_SUPERUSER` /
    # `AGENT_KB_PG_SUPERPASSWORD` 가 1순위. unset 인 경우 bootstrap.sh 가 사용하는
    # `AGENT_KB_PG_USER` / `AGENT_KB_PG_PASSWORD` 를 legacy fallback 으로 시도 — 운영자가
    # bootstrap 환경을 그대로 재사용해도 silent skip 되지 않도록 보강.
    # 권장 운영: 별 SUPER* 변수 사용 (`.env.example` 참조). USER/PASSWORD fallback 은
    # legacy compat 만, 신규 배포는 SUPER* 명시 설정.
    import os as _os
    su_host = _os.environ.get("AGENT_KB_PG_SUPERUSER_HOST") or _os.environ.get("AGENT_KB_PG_HOST", "")
    su_user = _os.environ.get("AGENT_KB_PG_SUPERUSER") or _os.environ.get("AGENT_KB_PG_USER", "postgres")
    su_pw   = _os.environ.get("AGENT_KB_PG_SUPERPASSWORD") or _os.environ.get("AGENT_KB_PG_PASSWORD", "")
    if su_pw:
        try:
            from shared.db import _pg_connect, _pg_available, AGENT_KB_PG_PORT, AGENT_KB_PG_DB, AGENT_KB_PG_SSLMODE
        except ImportError as _imp_err:
            if not (_imp_err.name is None or _imp_err.name == __package__):
                raise
            from db import _pg_connect, _pg_available, AGENT_KB_PG_PORT, AGENT_KB_PG_DB, AGENT_KB_PG_SSLMODE  # type: ignore[no-redef]
        try:
            import psycopg as _psycopg_mod
        except ImportError as _e:
            raise RuntimeError(f"psycopg not importable: {_e}") from _e
        su_conninfo = (
            f"host={su_host} port={AGENT_KB_PG_PORT} dbname={AGENT_KB_PG_DB or 'agent_kb'} "
            f"user={su_user} password={su_pw} sslmode={AGENT_KB_PG_SSLMODE} "
            f"connect_timeout=30 application_name=agent_core_schema_init"
        )
        su_conn = _psycopg_mod.connect(su_conninfo)
        su_conn.autocommit = True
        try:
            with su_conn.cursor() as su_cur:
                su_cur.execute(schema_sql)
        finally:
            su_conn.close()
    # else: bootstrap 에서 이미 schema 적용됨 — DDL skip, 검증만 수행.

    own_conn = False
    if conn is None:
        conn = _pg_connect()
        own_conn = True

    try:
        with conn.cursor() as cur:
            # 검증: 5 KB 테이블 + VIEW + extension 존재 확인.
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('fact_entries', 'texts', 'rag_documents', 'rag_objects')
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]

            # TASK-0140: agent_memory_facts matview 폐기 — 존재 검증 제거.
            # fact_entries 가 정본 (matview 는 중복 스냅샷, 자동 refresh 없어 drift).

            cur.execute("""
                SELECT extname
                FROM pg_extension
                WHERE extname IN ('vector', 'pg_trgm')
                ORDER BY extname
            """)
            extensions = [row[0] for row in cur.fetchall()]

            # TASK-0019 (M2) outside-voice Blocker B-3 해소: agent_kb_rw / agent_kb_ro
            # 의 schema 권한 정합 검증. ADR-0021 의 2-layer hybrid 의 Layer 1 인
            # connection-level 권한이 schema sql 의 DO $$ block 으로 자연 적용되었는지
            # 확인. `--apply-schema` 단독 호출 시 role 미존재 → grant skip 의 silent
            # failure 를 본 검증 query 가 detect. M2-a outside-voice REV-20260520-0007
            # Critical 권고 흡수: USAGE on SCHEMA + sequence USAGE + TRUNCATE 명시 검증
            # 추가 — silent failure hot path 차단.
            grants_present: dict[str, dict[str, bool]] = {}
            for role_name in ("agent_kb_rw", "agent_kb_ro"):
                role_grants: dict[str, bool] = {}
                try:
                    cur.execute(
                        "SELECT 1 FROM pg_roles WHERE rolname = %s",
                        (role_name,),
                    )
                    role_grants["role_exists"] = cur.fetchone() is not None
                    if role_grants["role_exists"]:
                        # USAGE on SCHEMA — table 권한 활성화 prerequisite (Critical)
                        cur.execute(
                            "SELECT has_schema_privilege(%s, 'public', 'USAGE')",
                            (role_name,),
                        )
                        role_grants["public_usage"] = bool(cur.fetchone()[0])
                        # 4 KB 테이블 × SELECT (모든 role) + INSERT/UPDATE/DELETE (rw 만)
                        # + TRUNCATE negative assertion (defense in depth)
                        for tbl in ("fact_entries", "texts", "rag_documents", "rag_objects"):
                            cur.execute(
                                "SELECT has_table_privilege(%s, %s, 'SELECT')",
                                (role_name, tbl),
                            )
                            role_grants[f"{tbl}_select"] = bool(cur.fetchone()[0])
                            if role_name == "agent_kb_rw":
                                cur.execute(
                                    "SELECT has_table_privilege(%s, %s, 'INSERT, UPDATE, DELETE')",
                                    (role_name, tbl),
                                )
                                role_grants[f"{tbl}_mutate"] = bool(cur.fetchone()[0])
                            # TRUNCATE 가 명시적으로 부재인지 확인 (REV-20260520-0007 Critical)
                            cur.execute(
                                "SELECT has_table_privilege(%s, %s, 'TRUNCATE')",
                                (role_name, tbl),
                            )
                            role_grants[f"{tbl}_truncate_denied"] = not bool(cur.fetchone()[0])
                            # IDENTITY sequence USAGE — INSERT 시 자동 ID 부여에 필수
                            # (Critical — outside-voice REV-20260520-0007 Section A)
                            if role_name == "agent_kb_rw":
                                seq_name = f"{tbl}_id_seq"
                                try:
                                    cur.execute(
                                        "SELECT has_sequence_privilege(%s, %s, 'USAGE')",
                                        (role_name, seq_name),
                                    )
                                    role_grants[f"{seq_name}_usage"] = bool(cur.fetchone()[0])
                                except Exception:
                                    # 일부 Postgres 환경에서 IDENTITY sequence 가
                                    # pg_class 의 sequence 가 아니라 owned column 으로
                                    # 표현될 수 있음 — graceful skip
                                    role_grants[f"{seq_name}_usage"] = None
                        # TASK-0140: agent_memory_facts matview 폐기 — VIEW SELECT 권한 검증 제거.
                except Exception as grant_err:  # pragma: no cover — undefined_object 등
                    role_grants["query_error"] = str(grant_err)[:200]
                grants_present[role_name] = role_grants

        # B-2 (REV-20260526-0001 흡수): schema 검증을 fail-loud 로 격상.
        # 누락 시 raise — agent_core.py 의 init_memory() 가 `AGENT_KB_PG_REQUIRED=1`
        # 환경에서 sys.exit(1) 로 변환. SUPERPASSWORD 미설정 + schema 미적용 조합에서
        # "KB Postgres schema 적용 완료" 라고 출력하면서 통과하는 silent failure 차단.
        expected_tables = {"fact_entries", "texts", "rag_documents", "rag_objects"}
        missing_tables = sorted(expected_tables - set(tables))
        missing_extensions = sorted({"vector", "pg_trgm"} - set(extensions))
        # TASK-0140: agent_memory_facts matview 폐기 — view_present 검증 제거.
        if missing_tables or missing_extensions:
            ddl_hint = (
                "DDL 적용이 필요합니다. 다음 중 하나를 수행하세요: "
                "(a) 환경변수에 `AGENT_KB_PG_SUPERPASSWORD` (또는 legacy `AGENT_KB_PG_PASSWORD`) "
                "를 설정 후 memory-init 재시작 — runtime DDL 자동 적용, "
                "(b) `bin/kb-pg-role-bootstrap.sh --apply-schema` 를 사전 실행."
            )
            raise RuntimeError(
                "KB Postgres schema verification failed: "
                f"missing_tables={missing_tables}, "
                f"missing_extensions={missing_extensions}. {ddl_hint}"
            )

        # psycopg autocommit 가 True 이므로 별도 commit 불요.
        return {
            "schema_applied": True,
            "tables_present": tables,
            "extensions": extensions,
            "grants_present": grants_present,
        }
    finally:
        if own_conn:
            conn.close()


__all__.append("_ensure_pg_schema")
