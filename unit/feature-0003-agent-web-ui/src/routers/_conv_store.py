"""feature-0012 ITEM-10 p4 — 대화 저장소(conversation store) 공용 헬퍼 (비-라우트 모듈).

app.py 에서 이동. share/conversations 두 도메인이 소비하는 공용 데이터 계층 — `_` 접두라
routers.register_all 자동 등록에서 제외. app 전역은 `app.X` 동적 참조(패치-단일점, 판정표 §4),
app.py 꼬리 rebind 가 기존 `app._conv_*`·app 내부 bare 호출을 보존한다.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any

from fastapi import Request

import app  # noqa: F401 — app.X 동적 참조(꼬리 rebind 시점 import — register_all 이후, 순환 안전)


def _conv_load_topic(conn, conversation_id: str) -> str:
    """원본 대화 topic. core_conversations.topic 우선, kv 'topic' fallback. 실패 시 '새 대화'."""
    if app._runtime_backend_is_pg():
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        """
SELECT COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.value), ''), '새 대화')
FROM agent_runtime.core_conversations c
LEFT JOIN agent_runtime.kv kv
  ON kv.conversation_id = c.conversation_id AND kv.key = 'topic'
WHERE c.conversation_id = %s
LIMIT 1
                        """,
                        (conversation_id,),
                    )
                    row = pgcur.fetchone()
            finally:
                pg.close()
            return str(row[0]) if row and row[0] is not None else "새 대화"
        except Exception:
            return "새 대화"
    try:
        cur = conn.cursor()
        cur.execute(
            """
SELECT COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.`Value`), ''), '새 대화') AS topic
FROM AgentCoreConversations c
LEFT JOIN AgentMemoryKv kv
  ON kv.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id COLLATE utf8mb4_unicode_ci
 AND kv.`Key` = 'topic'
WHERE c.conversation_id = %s
LIMIT 1
            """,
            (conversation_id,),
        )
        row = cur.fetchone()
        cur.close()
        return str(row[0]) if row and row[0] is not None else "새 대화"
    except Exception:
        return "새 대화"

def _conv_load_product(conn, conversation_id: str) -> tuple[int | None, Any]:
    """(product_id, product_mode_raw). 미존재/실패 시 (None, None)."""
    row = None
    if app._runtime_backend_is_pg():
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT product_id, product_mode FROM agent_runtime.core_conversations "
                        "WHERE conversation_id = %s",
                        (conversation_id,),
                    )
                    row = pgcur.fetchone()
            finally:
                pg.close()
        except Exception:
            return None, None
    else:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT product_id, product_mode FROM AgentCoreConversations WHERE conversation_id = %s",
                (conversation_id,),
            )
            row = cur.fetchone()
            cur.close()
        except Exception:
            return None, None
    if not row:
        return None, None
    return (int(row[0]) if row[0] is not None else None, row[1])

def _conv_load_messages_raw(
    conn, conversation_id: str, upto_id: int | None, from_id: int | None = None
) -> list[tuple]:
    """대화의 (id, role, content, created_at, meta_json) 행 목록 (id ASC).

    upto_id 가 주어지면 id <= upto_id inclusive ("여기까지 공유" 상단 경계).
    from_id 가 주어지면 id >= from_id inclusive ("여기부터 공유" 하단 경계, share-visibility-window).
    둘 다 DISPLAY id-space (agent_runtime.messages.id / AgentMemoryMessages.Id). 이 함수는 익명
    공유 뷰(_share_load_messages)와 fork-source 로더 양쪽을 지탱하므로 여기에 하단 경계를 두면
    가려진 pre-floor 구간이 두 표면 모두에서 배제된다. meta_json 은 PG(jsonb)면 dict,
    MySQL(longtext)이면 str 로 올 수 있어 호출자가 app._meta_json_to_dict 로 정규화한다.
    """
    if app._runtime_backend_is_pg():
        from shared.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                clauses = ["conversation_id = %s"]
                params: list[Any] = [conversation_id]
                if from_id is not None:
                    clauses.append("id >= %s")
                    params.append(int(from_id))
                if upto_id is not None:
                    clauses.append("id <= %s")
                    params.append(int(upto_id))
                pgcur.execute(
                    "SELECT id, role, content, created_at, meta_json "
                    "FROM agent_runtime.messages "
                    "WHERE " + " AND ".join(clauses) + " ORDER BY id ASC",
                    tuple(params),
                )
                return list(pgcur.fetchall() or [])
        finally:
            pg.close()
    cur = conn.cursor()
    try:
        clauses = ["ConversationId = %s"]
        params = [conversation_id]
        if from_id is not None:
            clauses.append("Id >= %s")
            params.append(int(from_id))
        if upto_id is not None:
            clauses.append("Id <= %s")
            params.append(int(upto_id))
        cur.execute(
            "SELECT Id, Role, Content, CreatedAt, MetaJson FROM AgentMemoryMessages "
            "WHERE " + " AND ".join(clauses) + " ORDER BY Id ASC",
            tuple(params),
        )
        return list(cur.fetchall() or [])
    finally:
        cur.close()

def _conv_message_exists(conn, conversation_id: str, message_id: int) -> bool:
    """message_id 가 conversation_id 의 메시지인지 검증."""
    if app._runtime_backend_is_pg():
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT 1 FROM agent_runtime.messages WHERE conversation_id = %s AND id = %s LIMIT 1",
                        (conversation_id, int(message_id)),
                    )
                    return pgcur.fetchone() is not None
            finally:
                pg.close()
        except Exception:
            return False
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM AgentMemoryMessages WHERE ConversationId = %s AND Id = %s LIMIT 1",
            (conversation_id, int(message_id)),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()

def _conv_message_created_at(conn, conversation_id: str, message_id: int):
    """message_id(DISPLAY id-space)의 created_at 반환 (backend-aware). 없으면 None.

    share-visibility-window: join stamp 시 경계 메세지(DISPLAY messages.id)의 created_at 을
    스냅샷해 conversation_members.visible_floor/ceiling_created_at 에 비정규화한다. 이 값이
    독립 id-space 인 core_messages(LLM recall)를 필터하는 유일한 bridge다(anchored fork 동형).
    """
    if app._runtime_backend_is_pg():
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT created_at FROM agent_runtime.messages "
                        "WHERE conversation_id = %s AND id = %s LIMIT 1",
                        (conversation_id, int(message_id)),
                    )
                    row = pgcur.fetchone()
                    return row[0] if row else None
            finally:
                pg.close()
        except Exception:
            return None
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT CreatedAt FROM AgentMemoryMessages WHERE ConversationId = %s AND Id = %s LIMIT 1",
            (conversation_id, int(message_id)),
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()

def _conv_update_topic_product(
    conn, conversation_id: str, topic: str, product_id: int | None, product_mode: str
) -> None:
    """새 대화 topic/product 갱신 (fork)."""
    if app._runtime_backend_is_pg():
        from shared.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "UPDATE agent_runtime.core_conversations "
                    "SET topic = %s, product_id = %s, product_mode = %s, updated_at = now() "
                    "WHERE conversation_id = %s",
                    (topic, int(product_id) if product_id else None, product_mode, conversation_id),
                )
        finally:
            pg.close()
        return
    cur = conn.cursor()
    cur.execute(
        """
UPDATE AgentCoreConversations
SET topic = %s, product_id = %s, product_mode = %s, updated_at = CURRENT_TIMESTAMP
WHERE conversation_id = %s
        """,
        (topic, int(product_id) if product_id else None, product_mode, conversation_id),
    )
    cur.close()

def _conv_update_topic(conn, conversation_id: str, topic: str) -> None:
    """대화 topic 만 갱신 (duplicate '사본:' prefix 적용)."""
    if app._runtime_backend_is_pg():
        from shared.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "UPDATE agent_runtime.core_conversations "
                    "SET topic = %s, updated_at = now() WHERE conversation_id = %s",
                    (topic, conversation_id),
                )
        finally:
            pg.close()
        return
    cur = conn.cursor()
    cur.execute(
        """
UPDATE AgentCoreConversations
SET topic = %s, updated_at = CURRENT_TIMESTAMP
WHERE conversation_id = %s
        """,
        (topic, conversation_id),
    )
    cur.close()

def _conv_copy_messages(
    conn, new_cid: str, src_rows: list[tuple], source_id: str, from_id: int | None
) -> int:
    """src_rows((id, role, content, created_at, meta_json))를 new_cid 로 복제. 복제 수 반환.

    내부/시스템 메시지(app._is_internal_message)는 제외. 실패 시 예외를 전파하여 호출자가
    delete_conversation_records 로 cleanup 하도록 한다.
    """
    use_pg = app._runtime_backend_is_pg()
    pg = None
    if use_pg:
        from shared.db import _pg_connect
        pg = _pg_connect()
        writer = pg.cursor()
    else:
        writer = conn.cursor()
    copied = 0
    try:
        for row in src_rows:
            msg_id, role, content, created_at, meta_json = row
            meta = app._meta_json_to_dict(meta_json)
            # app._is_internal_message 는 str|None 시그니처 — PG dict 는 직렬화해서 전달.
            meta_str_for_filter = json.dumps(meta) if meta else None
            if app._is_internal_message(role, content, meta_str_for_filter):
                continue
            meta["forked_from_conversation_id"] = source_id
            meta["forked_from_message_id"] = int(msg_id) if msg_id is not None else None
            if from_id is not None:
                meta["forked_cut_message_id"] = int(from_id)
            try:
                meta_out = json.dumps(meta, ensure_ascii=False, default=str)
            except Exception:
                meta_out = json.dumps({"forked_from_conversation_id": source_id})
            if use_pg:
                writer.execute(
                    "INSERT INTO agent_runtime.messages "
                    "(conversation_id, role, content, created_at, meta_json) "
                    "VALUES (%s, %s, %s, %s, %s::jsonb)",
                    (new_cid, role, content, created_at, meta_out),
                )
            else:
                writer.execute(
                    """
INSERT INTO AgentMemoryMessages (ConversationId, Role, Content, CreatedAt, MetaJson)
VALUES (%s, %s, %s, %s, %s)
                    """,
                    (new_cid, role, content, created_at, meta_out),
                )
            copied += 1
        return copied
    finally:
        try:
            writer.close()
        except Exception:
            pass
        if pg is not None:
            pg.close()

def _conv_load_core_messages_raw(
    conn, conversation_id: str, upto_created_at, from_created_at=None
) -> list[tuple]:
    """대화의 LLM 문맥 턴 (role, content, tool_calls, tool_call_id, name, created_at) 목록 (id ASC).

    TASK-0170 Phase 1 (ADR-WEB-0005 하이브리드): fork 가 LLM 문맥을 복원하도록 복사할
    소스. 어시스턴트는 `agent_runtime.core_messages` 에서 문맥을 읽으므로(agent_core.
    _load_conversation_messages) 이 테이블을 복사해야 fork 본이 이전 문맥을 인지한다.
    upto_created_at 가 주어지면 created_at <= upto_created_at 만 (anchored fork cut, 상단).
    from_created_at 가 주어지면 created_at >= from_created_at 만 (share-visibility-window, 하단).
    created_at 은 DISPLAY id-space 와 core id-space 를 잇는 유일한 bridge — 경계값은 호출자가
    이미 window-clip 된 display src_rows 에서 유도하며(발명 금지), fork 가 가려진 pre-floor core
    행을 복제하지 않도록 막는다. tool_calls 는 PG(jsonb)면 dict/list 로 반환됨 — 호출자가 직렬화한다.

    PG 런타임 전용: cutover 후 MySQL AgentCoreMessages 는 DROP 됐고 비-postgres 배포에는
    core_messages 개념이 없으므로 [] 반환(fork 는 표시 메시지만으로 진행).
    """
    if not app._runtime_backend_is_pg():
        return []
    from shared.db import _pg_connect
    pg = _pg_connect()
    try:
        with pg.cursor() as pgcur:
            clauses = ["conversation_id = %s"]
            params: list[Any] = [conversation_id]
            if from_created_at is not None:
                clauses.append("created_at >= %s")
                params.append(from_created_at)
            if upto_created_at is not None:
                clauses.append("created_at <= %s")
                params.append(upto_created_at)
            pgcur.execute(
                "SELECT role, content, tool_calls, tool_call_id, name, created_at "
                "FROM agent_runtime.core_messages "
                "WHERE " + " AND ".join(clauses) + " ORDER BY id ASC",
                tuple(params),
            )
            return list(pgcur.fetchall() or [])
    finally:
        pg.close()

def _conv_copy_core_messages(conn, new_cid: str, src_core_rows: list[tuple]) -> int:
    """src_core_rows((role, content, tool_calls, tool_call_id, name, created_at))를 new_cid 의
    core_messages 로 복제. 복제 수 반환. 실패 시 예외 전파(호출자가 cleanup).

    이것이 fork 문맥 복원의 핵심 — agent_core 가 읽는 LLM 문맥을 새 대화에 채운다.
    created_at 보존(로더는 id ASC 정렬이라 삽입순=소스순으로 순서 보존되며, created_at 은
    향후 Phase 의 cut 계산·표시 정합용). tool_calls(jsonb)는 직렬화 후 ::jsonb 재삽입.
    """
    if not app._runtime_backend_is_pg() or not src_core_rows:
        return 0
    from shared.db import _pg_connect
    pg = _pg_connect()
    writer = pg.cursor()
    copied = 0
    try:
        for row in src_core_rows:
            role, content, tool_calls, tool_call_id, name, created_at = row
            if tool_calls is None:
                tc_param = None
            elif isinstance(tool_calls, (dict, list)):
                tc_param = json.dumps(tool_calls, ensure_ascii=False, default=str)
            else:
                tc_param = str(tool_calls)
            writer.execute(
                "INSERT INTO agent_runtime.core_messages "
                "(conversation_id, role, content, tool_calls, tool_call_id, name, created_at) "
                "VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)",
                (new_cid, role, content, tc_param, tool_call_id, name, created_at),
            )
            copied += 1
        return copied
    finally:
        try:
            writer.close()
        except Exception:
            pass
        pg.close()

def _conv_load_share_meta(conn, conversation_id: str) -> dict[str, Any]:
    """public share view 용 대화 메타.

    topic / product_id / product_mode / owner_account_id 는 PG(core_conversations) 에서,
    product_key / product_name(WebProducts) + owner_username(WebAccounts) 는 MySQL 에서
    읽어 merge 한다 (web* 테이블은 Phase 3 이관 전까지 MySQL 잔존 → cross-DB join 불가).
    반환 dict 키: topic, product_id, product_mode, product_key, product_name, owner_username.
    """
    if app._runtime_backend_is_pg():
        meta: dict[str, Any] = {}
        owner_account_id: int | None = None
        product_id: int | None = None
        row = None
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT topic, product_id, product_mode, owner_account_id "
                        "FROM agent_runtime.core_conversations WHERE conversation_id = %s LIMIT 1",
                        (conversation_id,),
                    )
                    row = pgcur.fetchone()
            finally:
                pg.close()
        except Exception:
            logging.getLogger(__name__).warning(
                "_conv_load_share_meta: PG core_conversations read failed (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
        if row:
            meta["topic"] = row[0]
            product_id = int(row[1]) if row[1] is not None else None
            meta["product_id"] = product_id
            meta["product_mode"] = row[2]
            owner_account_id = int(row[3]) if row[3] is not None else None
        # MySQL enrichment: product (WebProducts) + owner display name (WebAccounts).
        try:
            if product_id is not None:
                cur = conn.cursor(dictionary=True)
                try:
                    cur.execute(
                        "SELECT ProductKey, Name FROM WebProducts WHERE Id = %s LIMIT 1",
                        (product_id,),
                    )
                    prow = cur.fetchone() or {}
                finally:
                    cur.close()
                meta["product_key"] = prow.get("ProductKey")
                meta["product_name"] = prow.get("Name")
        except Exception:
            logging.getLogger(__name__).warning(
                "_conv_load_share_meta: product enrichment failed (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
        try:
            if owner_account_id is not None:
                cur = conn.cursor(dictionary=True)
                try:
                    cur.execute(
                        "SELECT Username FROM WebAccounts WHERE Id = %s LIMIT 1",
                        (owner_account_id,),
                    )
                    orow = cur.fetchone() or {}
                finally:
                    cur.close()
                meta["owner_username"] = orow.get("Username")
        except Exception:
            logging.getLogger(__name__).warning(
                "_conv_load_share_meta: owner enrichment failed (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
        return meta
    # MySQL legacy fallback (cutover 전 / 비-postgres 배포).
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
SELECT c.topic AS topic, c.product_id AS product_id, c.product_mode AS product_mode,
       p.ProductKey AS product_key, p.Name AS product_name,
       owner.Username AS owner_username
FROM AgentCoreConversations c
LEFT JOIN WebProducts p ON p.Id = c.product_id
LEFT JOIN WebAccounts owner ON owner.Id = c.owner_account_id
WHERE c.conversation_id = %s
LIMIT 1
            """,
            (conversation_id,),
        )
        return cur.fetchone() or {}
    finally:
        cur.close()


# ── ITEM-10 p5: 대화 목록/히스토리 조회 (conversations 도메인 read 계층) ──

def _list_conversations_pg(
    limit: int,
    *,
    has_any: bool,
    self_id: int | None,
    self_username: str | None = None,
    owner_id: int | None,
    hidden_ids: list,
    normalized_q: str | None,
    date_from: str | None,
    date_to: str | None,
    parsed_cursor: tuple | None,
    mysql_conn,
) -> list[dict[str, Any]]:
    """AR-M4-T4 (TASK-0118): AGENT_RUNTIME_READ_BACKEND=postgres 활성 시 PG read path.

    agent_runtime.core_conversations + agent_runtime.kv 를 PG 에서 읽고,
    owner_username 조회만 MySQL WebAccounts 에서 수행 (Phase 3 web* 이관 전까지).
    """
    from shared.db import _pg_connect
    try:
        pg = _pg_connect()
    except Exception:
        return []

    try:
        query = """
SELECT
    c.conversation_id AS id,
    COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv_topic.value), ''), '새 대화') AS topic,
    c.created_at AS created_at,
    c.updated_at AS last_activity_at,
    c.owner_account_id AS owner_account_id,
    c.blocked_at AS blocked_at,
    c.blocked_reason AS blocked_reason
FROM agent_runtime.core_conversations c
LEFT JOIN agent_runtime.kv kv_topic
  ON kv_topic.conversation_id = c.conversation_id AND kv_topic.key = 'topic'
"""
        where_clauses: list[str] = []
        params: list[Any] = []

        # TASK-0273: 보관(archived) 대화는 일반 대화 목록에서 항상 숨긴다(소유자·admin 브라우징
        # 공통). 보관 대화는 전용 admin 엔드포인트(/api/admin/conversations/archived)로만 조회.
        where_clauses.append("c.archived_at IS NULL")

        if has_any:
            if owner_id is not None:
                where_clauses.append("c.owner_account_id = %s")
                params.append(int(owner_id))
        else:
            if self_id is not None:
                # feature-0009: owner OR 그룹 멤버십 — 멤버인 대화도 목록에 포함(열람 ≠ 발화).
                where_clauses.append(
                    "(c.owner_account_id = %s OR c.conversation_id IN ("
                    "SELECT conversation_id FROM agent_runtime.conversation_members "
                    "WHERE account_id = %s))"
                )
                params.append(int(self_id))
                params.append(int(self_id))

        if hidden_ids:
            where_clauses.append("c.conversation_id != ALL(%s)")
            params.append(list(str(h) for h in hidden_ids))

        if normalized_q:
            pattern = f"%{normalized_q}%"
            where_clauses.append("""(
                c.topic ILIKE %s OR kv_topic.value ILIKE %s
                OR EXISTS (
                    SELECT 1 FROM agent_runtime.messages m
                    WHERE m.conversation_id = c.conversation_id AND m.content ILIKE %s
                )
                OR EXISTS (
                    SELECT 1 FROM agent_runtime.core_messages cm
                    WHERE cm.conversation_id = c.conversation_id AND cm.content ILIKE %s
                )
            )""")
            params.extend([pattern, pattern, pattern, pattern])

        if date_from:
            where_clauses.append("c.updated_at >= %s")
            params.append(date_from)
        if date_to:
            where_clauses.append("c.updated_at <= %s")
            params.append(date_to)

        if parsed_cursor:
            cur_at, cur_id = parsed_cursor
            where_clauses.append(
                "(c.updated_at < %s OR (c.updated_at = %s AND c.conversation_id < %s))"
            )
            params.extend([cur_at, cur_at, cur_id])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY c.updated_at DESC, c.conversation_id DESC LIMIT %s"
        params.append(int(limit))

        with pg.cursor() as pgcur:
            pgcur.execute(query, params)
            rows = pgcur.fetchall() or []

        # owner_username — still in MySQL WebAccounts (Phase 3 이관 전).
        owner_ids_needed = list({r[4] for r in rows if r[4] is not None})
        owner_map: dict[int, str] = {}
        if owner_ids_needed and mysql_conn:
            try:
                mcur = mysql_conn.cursor()
                placeholders_o = ",".join(["%s"] * len(owner_ids_needed))
                mcur.execute(
                    f"SELECT Id, Username FROM WebAccounts WHERE Id IN ({placeholders_o})",
                    tuple(owner_ids_needed),
                )
                for oid, uname in mcur.fetchall() or []:
                    owner_map[int(oid)] = str(uname or "")
                mcur.close()
            except Exception:
                # best-effort: owner 이름 enrichment 실패는 목록 반환을 막지 않는다 (이름 공란).
                logging.getLogger(__name__).warning(
                    "_list_conversations_pg: owner name enrichment failed", exc_info=True,
                )

        items: list[dict[str, Any]] = []
        for row in rows:
            conv_id, topic, created_at, updated_at, oid, blocked_at, blocked_reason = row
            items.append({
                "id": str(conv_id or ""),
                "topic": app._normalize_topic(topic, "새 대화"),
                "created_at": str(created_at or ""),
                "last_activity_at": str(updated_at or ""),
                "owner_account_id": int(oid or 0) or None,
                "owner_username": owner_map.get(int(oid or 0), "") if oid else "",
                # TASK-0248: 참조 제품 삭제로 차단된 대화. blocked=True 면 프런트가 입력/전송을
                # 비활성화하고 배지·안내를 표시한다(이력 열람·공유는 가능).
                "blocked": blocked_at is not None,
                "blocked_at": str(blocked_at or "") if blocked_at is not None else "",
                "blocked_reason": str(blocked_reason or "") if blocked_at is not None else "",
            })

        # KV 상태/메타 (last_status / duration / run_id) — agent_runtime.kv 에서 읽기.
        conv_ids = [it["id"] for it in items]
        status_map: dict[str, dict[str, str]] = {}
        count_map: dict[str, dict[str, int]] = {}
        run_id_map: dict[str, str] = {}
        # feature-0009: 멤버십 신호(member_count + viewer is_member) — 프론트 send 게이트/멘션 라우팅용.
        member_map: dict[str, dict[str, Any]] = {}
        group_flag_set: set[str] = set()  # feature-0009 gc-group-authz-flag: is_group=true 인 cid 집합
        # feature-0009 gc-unread-badge: 멤버별 안 읽은 메세지 수 + 안 읽은 @멘션 수(사이드바 배지).
        unread_map: dict[str, dict[str, int]] = {}
        if conv_ids:
            with pg.cursor() as pgcur:
                placeholders_pg = ",".join(["%s"] * len(conv_ids))
                try:
                    pgcur.execute(
                        f"""
SELECT conversation_id, COUNT(*) AS cnt, BOOL_OR(account_id = %s) AS is_member
FROM agent_runtime.conversation_members
WHERE conversation_id IN ({placeholders_pg})
GROUP BY conversation_id
                        """,
                        (int(self_id or 0), *conv_ids),
                    )
                    for cid, cnt, ismem in pgcur.fetchall() or []:
                        member_map[str(cid)] = {"count": int(cnt or 0), "is_member": bool(ismem)}
                except Exception:
                    member_map = {}
                # feature-0009 gc-group-authz-flag: 그룹 플래그(is_group) — 공유/join 시 set.
                # 별도 defensive 쿼리(마이그레이션 미적용 시 컬럼 부재 → except 로 빈 set 폴백 = 비그룹).
                try:
                    pgcur.execute(
                        f"""
SELECT conversation_id FROM agent_runtime.core_conversations
WHERE conversation_id IN ({placeholders_pg}) AND COALESCE(is_group, false) = true
                        """,
                        tuple(conv_ids),
                    )
                    for (gcid,) in pgcur.fetchall() or []:
                        group_flag_set.add(str(gcid))
                except Exception:
                    group_flag_set = set()
                pgcur.execute(
                    f"""
SELECT conversation_id, key, value FROM agent_runtime.kv
WHERE conversation_id IN ({placeholders_pg})
  AND key IN ('last_status', 'last_status_at', 'last_duration_ms', 'last_status_run_id')
                    """,
                    tuple(conv_ids),
                )
                for cid, k, v in pgcur.fetchall() or []:
                    if k == 'last_status_run_id':
                        run_id_map[str(cid)] = str(v or "")
                    else:
                        status_map.setdefault(str(cid), {})[str(k)] = str(v or "")

                pgcur.execute(
                    f"""
SELECT conversation_id,
       COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM agent_runtime.messages
WHERE conversation_id IN ({placeholders_pg})
GROUP BY conversation_id
                    """,
                    tuple(conv_ids),
                )
                for cid, total, user in pgcur.fetchall() or []:
                    count_map[str(cid)] = {"total": int(total or 0), "user": int(user or 0)}

                pgcur.execute(
                    f"""
SELECT conversation_id,
       COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM agent_runtime.core_messages
WHERE conversation_id IN ({placeholders_pg})
  AND role IN ('user', 'assistant')
  AND (tool_calls IS NULL OR tool_calls::text = 'null')
  AND content IS NOT NULL AND content <> ''
GROUP BY conversation_id
                    """,
                    tuple(conv_ids),
                )
                for cid, total, user in pgcur.fetchall() or []:
                    existing = count_map.get(str(cid), {})
                    count_map[str(cid)] = {
                        "total": max(int(existing.get("total", 0) or 0), int(total or 0)),
                        "user": max(int(existing.get("user", 0) or 0), int(user or 0)),
                    }

                # feature-0009 gc-unread-badge: 멤버별 안 읽은(새) 메세지 수 + 안 읽은 @멘션 수.
                # conversation_members(본인) JOIN → 멤버인 대화만 집계(비멤버 admin 열람은 배지 없음).
                # unread = id > last_read 이고 본인(sender) 미발신 user/assistant 메세지.
                # _mention_re=None(username 없음) 이면 멘션 조건은 FALSE(0).
                _mention_re = app._mention_count_regex(self_username)
                _mention_frag = "AND m.content ~* %s" if _mention_re else "AND FALSE"
                try:
                    _uparams: list[Any] = [int(self_id or 0), int(self_id or 0)]
                    if _mention_re:
                        _uparams.append(_mention_re)
                    _uparams.append(int(self_id or 0))
                    _uparams.extend(conv_ids)
                    pgcur.execute(
                        f"""
SELECT m.conversation_id,
       SUM(CASE WHEN m.id > COALESCE(mem.last_read_message_id, 0)
                 AND m.sender_account_id IS DISTINCT FROM %s THEN 1 ELSE 0 END) AS unread,
       SUM(CASE WHEN m.id > COALESCE(mem.last_read_message_id, 0)
                 AND m.sender_account_id IS DISTINCT FROM %s
                 {_mention_frag} THEN 1 ELSE 0 END) AS unread_mention
FROM agent_runtime.core_messages m
JOIN agent_runtime.conversation_members mem
  ON mem.conversation_id = m.conversation_id AND mem.account_id = %s
WHERE m.conversation_id IN ({placeholders_pg})
  AND m.role IN ('user', 'assistant')
  AND (m.tool_calls IS NULL OR m.tool_calls::text = 'null')
  AND m.content IS NOT NULL AND m.content <> ''
GROUP BY m.conversation_id
                        """,
                        tuple(_uparams),
                    )
                    for cid, unread, unread_mention in pgcur.fetchall() or []:
                        unread_map[str(cid)] = {
                            "unread": int(unread or 0),
                            "unread_mention": int(unread_mention or 0),
                        }
                except Exception:
                    # best-effort: 마이그레이션 미적용(컬럼 부재) 등은 배지 미표시로 폴백.
                    unread_map = {}

        for item in items:
            info = status_map.get(item["id"], {})
            counts = count_map.get(item["id"], {})
            raw_status = info.get("last_status") or ""
            status_at = info.get("last_status_at") or ""
            run_id = run_id_map.get(item["id"], "")
            display_status, is_stale = app._compute_display_status(
                mysql_conn, item["id"], raw_status, status_at, run_id
            )
            item["status"] = display_status
            item["raw_status"] = raw_status
            item["display_status"] = display_status
            item["is_stale"] = is_stale
            item["status_at"] = status_at
            try:
                item["duration_ms"] = float(info.get("last_duration_ms")) if info.get("last_duration_ms") else None
            except Exception:
                item["duration_ms"] = None
            item["message_count"] = counts.get("total", 0)
            item["user_message_count"] = counts.get("user", 0)
            _ur = unread_map.get(item["id"], {})
            item["unread_count"] = int(_ur.get("unread", 0))
            item["unread_mention_count"] = int(_ur.get("unread_mention", 0))
            _mm = member_map.get(item["id"], {})
            item["member_count"] = int(_mm.get("count", 0))
            item["is_member"] = bool(_mm.get("is_member", False))
            # feature-0009 gc-group-authz-flag: 그룹 판정 = is_group 플래그(공유/join) OR 멤버 2+.
            # 프론트 send-routing(#2)·사이드바 배지(#3)의 단일 그룹 신호.
            item["is_group"] = (item["id"] in group_flag_set) or (int(_mm.get("count", 0)) > 1)

        return items
    finally:
        try:
            pg.close()
        except Exception:
            pass

def _list_conversations(
    limit: int = 200,
    *,
    account: dict[str, Any] | None = None,
    conn=None,
    q: str | None = None,
    owner_id: int | None = None,
    product_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
) -> list[dict[str, Any]]:
    """REQ-20260518-0010 (TASK-0072): extended with search/filter params for
    cross-account search modal. When q/owner_id/product_id/date_from/date_to/cursor
    are all None, behaviour is backward-compatible with pre-TASK-0072 callers.

    3 sub-spec enforced (adversarial review):
    1. SQL composition order — owner_id WHERE always AND'd BEFORE q clauses.
    2. hidden_ids SQL push — `c.conversation_id NOT IN (...)` not Python post-filter.
    3. Python re-sort deleted — SQL `ORDER BY updated_at DESC, conversation_id DESC` authoritative.
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = app._connect_memory()
        except Exception:
            return []
    try:
        app.cleanup_pending_delete_conversations(conn)
    except Exception:
        # best-effort: pending-delete 정리 실패는 목록 조회를 막지 않는다 (fail-open).
        logging.getLogger(__name__).warning(
            "_list_conversations: pending-delete cleanup failed", exc_info=True,
        )
    try:
        # Permission gate.
        if account and not (
            app._account_has_permission(account, "conversation.list.any")
            or app._account_has_permission(account, "conversation.list.own")
        ):
            return []
        has_any = bool(account and app._account_has_permission(account, "conversation.list.any"))
        self_id = int(account["id"]) if account and account.get("id") else None

        # REQ-20260518-0010 sub-spec 2: hidden_ids SQL push.
        hidden_ids = list(app.list_delete_requested_conversation_ids(conn) or [])

        # REQ-20260518-0010: body-search activation gate + collation audit (once per process).
        normalized_q = app._normalize_search_query(q)
        if normalized_q:
            app._audit_message_table_collations(conn)

        # AR-M4-T4 (TASK-0118): AGENT_RUNTIME_READ_BACKEND=postgres 시 PG 경로 사용.
        # AgentCoreConversations / AgentMemoryKv / AgentCoreMessages / AgentMemoryMessages
        # 가 MySQL에서 DROP 된 이후 PG 단독으로 읽어야 함.
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            return _list_conversations_pg(
                limit,
                has_any=has_any,
                self_id=self_id,
                self_username=(account.get("username") if account else None),
                owner_id=owner_id,
                hidden_ids=hidden_ids,
                normalized_q=normalized_q,
                date_from=date_from,
                date_to=date_to,
                parsed_cursor=app._parse_search_cursor(cursor),
                mysql_conn=conn,
            )

        cur = conn.cursor(dictionary=True)
        query = """
SELECT
    c.conversation_id AS id,
    COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(topic_kv.`Value`), ''), '새 대화') AS topic,
    c.created_at AS created_at,
    c.updated_at AS last_activity_at,
    c.owner_account_id AS owner_account_id,
    c.blocked_at AS blocked_at,
    c.blocked_reason AS blocked_reason,
    owner.Username AS owner_username
FROM AgentCoreConversations c
LEFT JOIN AgentMemoryKv topic_kv
  ON topic_kv.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id COLLATE utf8mb4_unicode_ci
 AND topic_kv.`Key` = 'topic'
LEFT JOIN WebAccounts owner
  ON owner.Id = c.owner_account_id
        """
        where_clauses: list[str] = []
        params: list[Any] = []

        # TASK-0273: 보관(archived) 대화는 일반 목록에서 항상 숨긴다(PG 경로와 동일).
        where_clauses.append("c.archived_at IS NULL")

        # REQ-20260518-0010 sub-spec 1 (SQL composition order):
        # Owner filter ALWAYS first. For .own-only callers, ALWAYS overwrite
        # owner_id to self (explicit overwrite, not 'ignore'). For .any callers,
        # owner_id (if provided) is a strict filter.
        if has_any:
            if owner_id is not None:
                where_clauses.append("c.owner_account_id = %s")
                params.append(int(owner_id))
        else:
            if self_id is not None:
                # feature-0009: owner OR 그룹 멤버십 (MySQL parity, 레거시 경로).
                where_clauses.append(
                    "(c.owner_account_id = %s OR c.conversation_id IN ("
                    "SELECT conversation_id FROM AgentCoreConversationMembers "
                    "WHERE account_id = %s))"
                )
                params.append(int(self_id))
                params.append(int(self_id))
            # else: account-less internal call — no owner filter (admin tooling).

        # REQ-20260518-0010 risk 1: WebAccounts.DeletedAt filter — hide deleted owners.
        where_clauses.append("(owner.DeletedAt IS NULL OR c.owner_account_id IS NULL)")

        # REQ-20260518-0010 sub-spec 2 (hidden_ids SQL push):
        if hidden_ids:
            placeholders_hidden = ",".join(["%s"] * len(hidden_ids))
            where_clauses.append(f"c.conversation_id NOT IN ({placeholders_hidden})")
            params.extend(str(h) for h in hidden_ids)

        # Body / title / owner-username search.
        if normalized_q:
            escaped = app._escape_like_for_search(normalized_q)
            pattern = f"%{escaped}%"
            search_subclauses = [
                "c.topic LIKE %s ESCAPE '!'",
                "topic_kv.`Value` LIKE %s ESCAPE '!'",
            ]
            sp_params: list[Any] = [pattern, pattern]
            # owner.Username search — .any only (risk 3: prevent .own user from
            # probing account existence cross-account via row presence).
            if has_any:
                search_subclauses.append("owner.Username LIKE %s ESCAPE '!'")
                sp_params.append(pattern)
            # Body EXISTS subqueries (AgentMemoryMessages + AgentCoreMessages).
            search_subclauses.append(
                "EXISTS (SELECT 1 FROM AgentMemoryMessages m "
                "WHERE m.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id COLLATE utf8mb4_unicode_ci "
                "AND m.Content LIKE %s ESCAPE '!')"
            )
            sp_params.append(pattern)
            search_subclauses.append(
                "EXISTS (SELECT 1 FROM AgentCoreMessages cm "
                "WHERE cm.conversation_id = c.conversation_id "
                "AND cm.content LIKE %s ESCAPE '!')"
            )
            sp_params.append(pattern)
            where_clauses.append("(" + " OR ".join(search_subclauses) + ")")
            params.extend(sp_params)

        # Date range on c.updated_at.
        if date_from:
            where_clauses.append("c.updated_at >= %s")
            params.append(str(date_from))
        if date_to:
            where_clauses.append("c.updated_at <= %s")
            params.append(str(date_to))

        # Cursor pagination — keyset on (updated_at, conversation_id) DESC.
        parsed_cursor = app._parse_search_cursor(cursor)
        if parsed_cursor:
            cur_at, cur_id = parsed_cursor
            where_clauses.append(
                "(c.updated_at < %s OR (c.updated_at = %s AND c.conversation_id < %s))"
            )
            params.extend([cur_at, cur_at, cur_id])

        # product_id filter — schema not yet linking conversations to products.
        # Reserved param for future cycle; ignored silently to keep API stable.
        _ = product_id

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        # REQ-20260518-0010 sub-spec 3: SQL ORDER BY is authoritative; no Python re-sort.
        query += " ORDER BY c.updated_at DESC, c.conversation_id DESC LIMIT %s"
        params.append(int(limit))
        cur.execute(query, tuple(params))
        items = cur.fetchall() or []
        cur.close()

        items = [
            {
                "id": str(item.get("id") or ""),
                "topic": app._normalize_topic(item.get("topic"), "새 대화"),
                "created_at": str(item.get("created_at") or ""),
                "last_activity_at": str(item.get("last_activity_at") or item.get("created_at") or ""),
                "owner_account_id": int(item.get("owner_account_id") or 0) or None,
                "owner_username": str(item.get("owner_username") or ""),
                # TASK-0248: 참조 제품 삭제 차단 상태 (PG 경로와 동일 계약).
                "blocked": item.get("blocked_at") is not None,
                "blocked_at": str(item.get("blocked_at") or "") if item.get("blocked_at") is not None else "",
                "blocked_reason": str(item.get("blocked_reason") or "") if item.get("blocked_at") is not None else "",
            }
            for item in items
            if str(item.get("id") or "")
        ]
        conv_ids = [item["id"] for item in items]
        status_map: dict[str, dict[str, str]] = {}
        count_map: dict[str, dict[str, int]] = {}
        # feature-0009 gc-unread-badge: 안 읽은(새) 메세지 + 안 읽은 @멘션 수 (MySQL parity).
        unread_map: dict[str, dict[str, int]] = {}
        if conv_ids:
            placeholders = ",".join(["%s"] * len(conv_ids))
            cur = conn.cursor()
            cur.execute(
                f"""
SELECT ConversationId, `Key`, `Value`
FROM AgentMemoryKv
WHERE ConversationId IN ({placeholders})
  AND `Key` IN ('last_status', 'last_status_at', 'last_duration_ms')
                """,
                tuple(conv_ids),
            )
            for conv_id, key, value in cur.fetchall() or []:
                status_map.setdefault(str(conv_id), {})[str(key)] = str(value)
            cur.execute(
                f"""
SELECT ConversationId,
       COUNT(*) AS total_count,
       SUM(CASE WHEN Role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM AgentMemoryMessages
WHERE ConversationId IN ({placeholders})
GROUP BY ConversationId
                """,
                tuple(conv_ids),
            )
            for conv_id, total_count, user_count in cur.fetchall() or []:
                count_map[str(conv_id)] = {
                    "total": int(total_count or 0),
                    "user": int(user_count or 0),
                }
            try:
                cur.execute(
                    f"""
SELECT conversation_id,
       COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM AgentCoreMessages
WHERE conversation_id IN ({placeholders})
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
GROUP BY conversation_id
                    """,
                    tuple(conv_ids),
                )
                core_counts = cur.fetchall() or []
            except Exception:
                core_counts = []
            cur.close()
            for conv_id, total_count, user_count in core_counts:
                existing = count_map.get(str(conv_id), {})
                count_map[str(conv_id)] = {
                    "total": max(int(existing.get("total", 0) or 0), int(total_count or 0)),
                    "user": max(int(existing.get("user", 0) or 0), int(user_count or 0)),
                }
            # feature-0009 gc-unread-badge: 안 읽은(새) 메세지 + 안 읽은 @멘션 수 (MySQL parity,
            # 레거시 경로 — production 은 PG). 본인 미발신 + last_read 이후. _mention_re=None 이면 0.
            try:
                _mention_re = app._mention_count_regex(account.get("username") if account else None)
                _mention_re = _mention_re.lower() if _mention_re else None
                _mention_frag = "AND LOWER(m.content) REGEXP %s" if _mention_re else "AND 0"
                _me = int(self_id or 0)
                _uparams: list[Any] = [_me, _me]
                if _mention_re:
                    _uparams.append(_mention_re)
                _uparams.append(_me)
                _uparams.extend(conv_ids)
                cur = conn.cursor()
                cur.execute(
                    f"""
SELECT m.conversation_id,
       SUM(CASE WHEN m.id > COALESCE(mem.last_read_message_id, 0)
                 AND NOT (m.sender_account_id <=> %s) THEN 1 ELSE 0 END) AS unread,
       SUM(CASE WHEN m.id > COALESCE(mem.last_read_message_id, 0)
                 AND NOT (m.sender_account_id <=> %s)
                 {_mention_frag} THEN 1 ELSE 0 END) AS unread_mention
FROM AgentCoreMessages m
JOIN AgentCoreConversationMembers mem
  ON mem.conversation_id = m.conversation_id AND mem.account_id = %s
WHERE m.conversation_id IN ({placeholders})
  AND m.role IN ('user', 'assistant')
  AND m.tool_calls IS NULL
  AND COALESCE(m.content, '') <> ''
GROUP BY m.conversation_id
                    """,
                    tuple(_uparams),
                )
                for conv_id, unread, unread_mention in cur.fetchall() or []:
                    unread_map[str(conv_id)] = {
                        "unread": int(unread or 0),
                        "unread_mention": int(unread_mention or 0),
                    }
                cur.close()
            except Exception:
                unread_map = {}
        # TASK-0061 Phase 3 (REQ-20260515-0005): stale 판정에 last_status_run_id 도 필요하므로
        # 단일 추가 쿼리로 모은다 (KV 한 번 더 조회 — N 회 fan-out 회피).
        run_id_map: dict[str, str] = {}
        if conv_ids:
            placeholders2 = ",".join(["%s"] * len(conv_ids))
            cur = conn.cursor()
            try:
                cur.execute(
                    f"""
SELECT ConversationId, `Value`
FROM AgentMemoryKv
WHERE ConversationId IN ({placeholders2})
  AND `Key` = 'last_status_run_id'
                    """,
                    tuple(conv_ids),
                )
                for conv_id, value in cur.fetchall() or []:
                    run_id_map[str(conv_id)] = str(value or "")
            except Exception:
                # best-effort: run_id enrichment 실패는 목록 반환을 막지 않는다.
                logging.getLogger(__name__).warning(
                    "_list_conversations: last_status_run_id enrichment failed", exc_info=True,
                )
            cur.close()
        for item in items:
            info = status_map.get(item["id"], {})
            counts = count_map.get(item["id"], {})
            raw_status = info.get("last_status") or ""
            status_at = info.get("last_status_at") or ""
            run_id = run_id_map.get(item["id"], "")
            display_status, is_stale = app._compute_display_status(
                conn, item["id"], raw_status, status_at, run_id
            )
            item["status"] = display_status
            item["raw_status"] = raw_status
            item["display_status"] = display_status
            item["is_stale"] = is_stale
            item["status_at"] = status_at
            try:
                item["duration_ms"] = float(info.get("last_duration_ms")) if info.get("last_duration_ms") else None
            except Exception:
                item["duration_ms"] = None
            item["message_count"] = counts.get("total", 0)
            item["user_message_count"] = counts.get("user", 0)
            _ur = unread_map.get(item["id"], {})
            item["unread_count"] = int(_ur.get("unread", 0))
            item["unread_mention_count"] = int(_ur.get("unread_mention", 0))
        # REQ-20260518-0010 sub-spec 3: Python re-sort deleted. SQL ORDER BY
        # `c.updated_at DESC, c.conversation_id DESC LIMIT N` is authoritative.
        # The prior `_sort_dt_key` re-sort produced incoherent pages when combined
        # with cursor pagination (page 2 would be a stale subset of page 1).
        return items
    finally:
        if own_conn and conn is not None:
            conn.close()

def _get_agent_core_history(
    conn,
    conversation_id: str,
    limit: int = 5,
    before_id: int | None = None,
) -> tuple[list[dict[str, Any]], bool, int | None, int, int]:
    fetch_limit = max(10, int(limit) * 3)
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                if before_id:
                    pgcur.execute(
                        """
SELECT id, role, content, created_at
FROM agent_runtime.core_messages
WHERE conversation_id = %s AND id < %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
ORDER BY id DESC
LIMIT %s
                        """,
                        (conversation_id, int(before_id), int(fetch_limit) + 1),
                    )
                else:
                    pgcur.execute(
                        """
SELECT id, role, content, created_at
FROM agent_runtime.core_messages
WHERE conversation_id = %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
ORDER BY id DESC
LIMIT %s
                        """,
                        (conversation_id, int(fetch_limit) + 1),
                    )
                pg_rows = pgcur.fetchall() or []
                has_more_pg = len(pg_rows) > fetch_limit
                pg_rows = pg_rows[:fetch_limit]
                pg_rows_rev = list(reversed(pg_rows))
                pgcur.execute(
                    """
SELECT COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM agent_runtime.core_messages
WHERE conversation_id = %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
                    """,
                    (conversation_id,),
                )
                count_row_pg = pgcur.fetchone() or (0, 0)
            pg.close()
        except Exception:
            return [], False, None, 0, 0
        messages_pg: list[dict[str, Any]] = []
        for msg_id, role, content, created_at in pg_rows_rev:
            meta: dict[str, Any] = {}
            if str(role or "").lower() == "assistant":
                intent_val = app._extract_intent_from_content(str(content or ""))
                meta = app._load_step_meta(conn, conversation_id, intent_val, created_at) or {}
                steps_val = app._load_steps_for_message(conn, conversation_id, created_at, meta)
                if steps_val:
                    meta = dict(meta) if isinstance(meta, dict) else {}
                    meta["steps"] = steps_val
                    meta["rationale"] = app._summarize_rationale(steps_val)
                    meta["run_id"] = steps_val[0].get("run_id")
            messages_pg.append({
                "id": int(msg_id),
                "id_space": "core",  # core_messages.id 공간 — 피드백 고유성 키 모호성 차단(표시 store id 와 숫자 겹침 가능)
                "role": str(role),
                "content": app._normalize_output(str(content or "")),
                "created_at": str(created_at),
                "meta": meta,
            })
        oldest_id_pg = messages_pg[0]["id"] if messages_pg else None
        return (
            messages_pg,
            has_more_pg,
            oldest_id_pg,
            int(count_row_pg[0] or 0),
            int(count_row_pg[1] or 0),
        )
    cur = conn.cursor()
    if before_id:
        cur.execute(
            """
SELECT id, role, content, created_at
FROM AgentCoreMessages
WHERE conversation_id = %s
  AND id < %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
ORDER BY id DESC
LIMIT %s
            """,
            (conversation_id, int(before_id), int(fetch_limit) + 1),
        )
    else:
        cur.execute(
            """
SELECT id, role, content, created_at
FROM AgentCoreMessages
WHERE conversation_id = %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
ORDER BY id DESC
LIMIT %s
            """,
            (conversation_id, int(fetch_limit) + 1),
        )
    rows = cur.fetchall() or []
    has_more = len(rows) > fetch_limit
    rows = rows[:fetch_limit]
    rows.reverse()
    messages: list[dict[str, Any]] = []
    for msg_id, role, content, created_at in rows:
        meta: dict[str, Any] = {}
        if str(role or "").lower() == "assistant":
            intent = app._extract_intent_from_content(str(content or ""))
            meta = app._load_step_meta(conn, conversation_id, intent, created_at) or {}
            steps = app._load_steps_for_message(conn, conversation_id, created_at, meta)
            if steps:
                meta = dict(meta) if isinstance(meta, dict) else {}
                meta["steps"] = steps
                meta["rationale"] = app._summarize_rationale(steps)
                meta["run_id"] = steps[0].get("run_id")
        messages.append(
            {
                "id": int(msg_id),
                "id_space": "core",  # AgentCoreMessages.id 공간 — 피드백 고유성 키 모호성 차단
                "role": str(role),
                "content": app._normalize_output(str(content or "")),
                "created_at": str(created_at),
                "meta": meta,
            }
        )
    cur.execute(
        """
SELECT COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM AgentCoreMessages
WHERE conversation_id = %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
        """,
        (conversation_id,),
    )
    count_row = cur.fetchone() or (0, 0)
    cur.close()
    oldest_id = messages[0]["id"] if messages else None
    return (
        messages,
        has_more,
        oldest_id,
        int(count_row[0] or 0),
        int(count_row[1] or 0),
    )

def _get_history(
    conversation_id: str, limit: int = 5, before_id: int | None = None, window=None
) -> tuple[list[dict[str, Any]], bool, int | None, int, int]:
    if not conversation_id:
        return [], False, None, 0, 0
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            conn = app._connect_memory()
        except Exception:
            return [], False, None, 0, 0
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                if before_id:
                    pgcur.execute(
                        "SELECT id, role, content, created_at, meta_json FROM agent_runtime.messages "
                        "WHERE conversation_id = %s AND id < %s ORDER BY id DESC LIMIT %s",
                        (conversation_id, int(before_id), max(10, int(limit) * 3) + 1),
                    )
                else:
                    pgcur.execute(
                        "SELECT id, role, content, created_at, meta_json FROM agent_runtime.messages "
                        "WHERE conversation_id = %s ORDER BY id DESC LIMIT %s",
                        (conversation_id, max(10, int(limit) * 3) + 1),
                    )
                pg_rows = pgcur.fetchall() or []
            pg.close()
        except Exception:
            pg_rows = []
        fetch_limit_pg = max(10, int(limit) * 3)
        has_more_pg = len(pg_rows) > fetch_limit_pg
        pg_rows = pg_rows[:fetch_limit_pg]
        pg_rows_rev = list(reversed(pg_rows))
        messages_pg: list[dict[str, Any]] = []
        for row in pg_rows_rev:
            msg_id, role, content, created_at, meta_json = row
            if app._is_internal_message(role, content, meta_json):
                continue
            meta: dict[str, Any] = {}
            if meta_json:
                try:
                    meta = json.loads(meta_json) if isinstance(meta_json, str) else (meta_json or {})
                except Exception:
                    meta = {}
            if str(role or "").lower() == "assistant":
                if not meta:
                    intent_v = app._extract_intent_from_content(str(content or ""))
                    meta = app._load_step_meta(conn, conversation_id, intent_v, created_at) or meta
                steps_v = app._load_steps_for_message(conn, conversation_id, created_at, meta)
                if steps_v:
                    meta = dict(meta) if isinstance(meta, dict) else {}
                    meta["steps"] = steps_v
                    meta["rationale"] = app._summarize_rationale(steps_v)
                    meta["run_id"] = steps_v[0].get("run_id")
            if window and app._msg_outside_window(msg_id, created_at, meta, role, window):
                continue  # share-visibility-window: 가려진 구간은 표시(view)에서도 배제.
            messages_pg.append({
                "id": int(msg_id),
                "id_space": "display",  # agent_runtime.messages.id(표시 store) — 피드백 고유성 키 공간
                "role": str(role),
                "content": app._normalize_output(str(content or "")),
                "created_at": str(created_at),
                "meta": meta,
            })
        needs_core_pg = not messages_pg or not any(str(i.get("role", "")).lower() == "assistant" for i in messages_pg)
        # share-visibility-window: bounded 멤버(window 지정)는 core fallback(core_messages 직접
        # 읽기 — window 미적용)을 건너뛴다. 표시 store 만으로 window 정합 응답을 준다(유출 방지).
        if needs_core_pg and window is None:
            core_msgs, core_hm, core_oid, core_tc, core_uc = _get_agent_core_history(
                conn, conversation_id, limit=limit, before_id=before_id
            )
            if core_msgs and any(str(i.get("role", "")).lower() == "assistant" for i in core_msgs):
                conn.close()
                return core_msgs, core_hm, core_oid, core_tc, core_uc
            if not messages_pg and (core_msgs or core_tc or app._conversation_exists(conversation_id)):
                conn.close()
                return core_msgs, core_hm, core_oid, core_tc, core_uc
        # ③ TASK-0285: assistant 말풍선 첨부 칩 영속 — assistant 생성 첨부를 message_id 로 주입.
        app._attach_assistant_attachments(messages_pg, app._load_assistant_attachments_by_message(conn, conversation_id))
        oldest_id_pg = messages_pg[0]["id"] if messages_pg else None
        conn.close()
        return messages_pg, has_more_pg, oldest_id_pg, len(messages_pg), sum(1 for m in messages_pg if str(m.get("role", "")).lower() == "user")
    try:
        conn = app._connect_memory()
    except Exception:
        return [], False, None, 0, 0
    cur = conn.cursor()
    fetch_limit = max(10, int(limit) * 3)
    if before_id:
        cur.execute(
            """
SELECT Id, Role, Content, CreatedAt, MetaJson
FROM AgentMemoryMessages
WHERE ConversationId = %s AND Id < %s
ORDER BY Id DESC
LIMIT %s
            """,
            (conversation_id, int(before_id), int(fetch_limit) + 1),
        )
    else:
        cur.execute(
            """
SELECT Id, Role, Content, CreatedAt, MetaJson
FROM AgentMemoryMessages
WHERE ConversationId = %s
ORDER BY Id DESC
LIMIT %s
            """,
            (conversation_id, int(fetch_limit) + 1),
        )
    rows = cur.fetchall() or []
    has_more = len(rows) > fetch_limit
    rows = rows[:fetch_limit]
    rows.reverse()
    messages: list[dict[str, Any]] = []
    for row in rows:
        msg_id, role, content, created_at, meta_json = row
        if app._is_internal_message(role, content, meta_json):
            continue
        meta = {}
        if meta_json:
            try:
                meta = json.loads(meta_json)
            except Exception:
                meta = {}
        if str(role or "").lower() == "assistant":
            if not meta:
                intent = app._extract_intent_from_content(str(content or ""))
                meta = app._load_step_meta(conn, conversation_id, intent, created_at) or meta
            steps = app._load_steps_for_message(conn, conversation_id, created_at, meta)
            if steps:
                meta = dict(meta) if isinstance(meta, dict) else {}
                meta["steps"] = steps
                meta["rationale"] = app._summarize_rationale(steps)
                meta["run_id"] = steps[0].get("run_id")
        if window and app._msg_outside_window(msg_id, created_at, meta, role, window):
            continue  # share-visibility-window: 가려진 구간은 표시(view)에서도 배제 (parity).
        messages.append(
            {
                "id": int(msg_id),
                "id_space": "display",  # AgentMemoryMessages.Id(표시 store) — 피드백 고유성 키 공간
                "role": str(role),
                "content": app._normalize_output(str(content or "")),
                "created_at": str(created_at),
                "meta": meta,
            }
        )
    cur.close()
    # ③ TASK-0285: assistant 말풍선 첨부 칩 영속 — assistant 생성 첨부를 message_id 로 주입 (MySQL 경로).
    app._attach_assistant_attachments(messages, app._load_assistant_attachments_by_message(conn, conversation_id))
    needs_core_fallback = not messages or not any(str(item.get("role", "")).lower() == "assistant" for item in messages)
    if needs_core_fallback and window is None:  # share-visibility-window: bounded 멤버는 core fallback skip.
        core_messages, core_has_more, core_oldest_id, core_total_count, core_user_count = _get_agent_core_history(
            conn,
            conversation_id,
            limit=limit,
            before_id=before_id,
        )
        if core_messages and any(str(item.get("role", "")).lower() == "assistant" for item in core_messages):
            conn.close()
            return core_messages, core_has_more, core_oldest_id, core_total_count, core_user_count
        if not messages and (core_messages or core_total_count or app._conversation_exists(conversation_id)):
            conn.close()
            return core_messages, core_has_more, core_oldest_id, core_total_count, core_user_count
        cur = conn.cursor()
    else:
        cur = conn.cursor()
    cur.execute(
        """
SELECT COUNT(*) AS total_count,
       SUM(CASE WHEN Role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM AgentMemoryMessages
WHERE ConversationId = %s
        """,
        (conversation_id,),
    )
    count_row = cur.fetchone() or (0, 0)
    total_count = int(count_row[0] or 0)
    user_count = int(count_row[1] or 0)
    cur.close()
    conn.close()
    oldest_id = messages[0]["id"] if messages else None
    return messages, has_more, oldest_id, total_count, user_count


# ── ITEM-10 p6: fork·steps 로드·assistant 첨부 편집 렌더 (conversations 도메인) ──

def _materialize_assistant_attachment_edits(
    conn,
    *,
    account: dict[str, Any],
    conversation_id: str,
    answer: str,
    message_id: int | None = None,
    request: "Request | None" = None,
) -> list[dict[str, Any]]:
    """assistant 답변의 attachment-edit 블록을 새 첨부 버전으로 materialize.

    Returns: 생성된 새 버전들의 직렬화 dict 리스트(0개면 빈 리스트). 모든 실패는
    fail-open(로깅만) — materialize 실패가 사용자 답변을 막지 않는다.
    """
    blocks = app._parse_attachment_edit_blocks(answer)
    if not blocks:
        return []
    try:
        from web.modules import storage_minio
    except Exception:
        return []

    account_id = int(account.get("id") or 0)
    created: list[dict[str, Any]] = []
    import uuid as _uuid

    for block in blocks[:app._ASSISTANT_EDIT_COUNT_CAP]:
        src_id = int(block["source_attachment_id"])
        content = str(block.get("content") or "")
        body_bytes = content.encode("utf-8")

        # 가드 4: 내용 size cap(텍스트 계열).
        if not body_bytes:
            continue
        if len(body_bytes) > app._ASSISTANT_EDIT_SIZE_CAP_BYTES:
            logging.getLogger(__name__).warning(
                "attachment-edit: content too large (src=%s, %d bytes) — skip",
                src_id, len(body_bytes),
            )
            continue

        # source 첨부 로드 + 가드 2: 같은 conversation + 같은 account scope.
        src = app._load_attachment_row(conn, src_id)
        if not src:
            continue
        if str(src.get("ConversationId") or "") != str(conversation_id):
            logging.getLogger(__name__).warning(
                "attachment-edit: source conv mismatch (src=%s) — skip", src_id)
            continue
        if int(src.get("AccountId") or 0) != account_id:
            logging.getLogger(__name__).warning(
                "attachment-edit: source account mismatch (src=%s) — skip", src_id)
            continue
        if src.get("DeletedAt") or src.get("DeletePending"):
            continue

        # 가드 1: 텍스트 계열 kind 만(csv/text). 바이너리(xlsx/pdf/image)는 거부.
        src_kind = str(src.get("Kind") or "")
        if src_kind not in ("text", "csv"):
            logging.getLogger(__name__).warning(
                "attachment-edit: non-text kind '%s' (src=%s) — skip", src_kind, src_id)
            continue

        # 가드 3: size cap(per_file/conv/account) 재사용.
        ok, _reason = app._check_attachment_size_caps(
            conn, account_id=account_id, conversation_id=conversation_id,
            new_size_bytes=len(body_bytes),
        )
        if not ok:
            logging.getLogger(__name__).warning(
                "attachment-edit: size cap exceeded (src=%s) — skip", src_id)
            continue

        # 버전 체인: root = source 의 root(없으면 source 자신). 체인 내 최대 VersionNumber+1.
        root_id = int(src.get("RootAttachmentId") or 0) or src_id
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT COALESCE(MAX(VersionNumber), 1)
                FROM WebConversationAttachments
                WHERE RootAttachmentId = %s OR Id = %s
                """,
                (root_id, root_id),
            )
            row = cur.fetchone()
            next_version = int((row[0] if row else 1) or 1) + 1
        finally:
            cur.close()

        # MINOR(보안리뷰 V3): 새 파일명은 source 확장자를 강제 보존 — LLM 이 filename 에
        # `.exe` 등을 줘도 다운로드 Content-Disposition 에 실행파일류 확장자가 실리지 않게.
        src_filename = str(src.get("OriginalFilename") or "")
        src_ext = src_filename.rsplit(".", 1)[1].lower() if "." in src_filename else ""
        raw_filename = block.get("filename") or app._next_version_filename(src_filename, next_version)
        # base name 만 취하고(디렉토리 구분자 제거) source 확장자로 정규화.
        base_name = str(raw_filename).replace("/", "_").replace("\\", "_").strip()
        if src_ext:
            stem = base_name.rsplit(".", 1)[0] if "." in base_name else base_name
            filename = f"{stem}.{src_ext}"
        else:
            filename = base_name or app._next_version_filename(src_filename, next_version)
        # kind 는 source kind 를 그대로 따른다(텍스트 계열만 여기 도달 — 가드 1).
        new_kind = src_kind
        mime_type = "text/csv" if new_kind == "csv" else "text/plain; charset=utf-8"
        sha256_hex = hashlib.sha256(body_bytes).hexdigest()
        attachment_uuid = str(_uuid.uuid4())
        object_key = storage_minio.make_object_key(conversation_id, attachment_uuid, filename)

        # 보안리뷰 V8(원자성): MinIO put 을 INSERT **전에** 수행 — put 성공 후에만 DB row 를
        # 만든다. 이로써 "DB row 있는데 MinIO 객체 없음" orphan(다운로드 404)을 제거. put 만
        # 성공하고 INSERT 실패하면 MinIO 고아 객체만 남는데, 이는 정상 업로드 경로와 동일 특성
        # 이라 reconciliation worker 가 정리(무해).
        try:
            storage_minio.put_object_bytes(
                object_key, body_bytes, content_type=mime_type,
                metadata={
                    "conversation-id": conversation_id,
                    "uploader-account-id": str(account_id),
                    "assistant-edit-of": str(src_id),
                },
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "attachment-edit: MinIO put failed (src=%s) — skip", src_id)
            continue

        # INSERT 새 버전 row. 보안리뷰 V6(race): IX_WCA_VersionChain 가 UNIQUE 이므로 동시
        # ask 가 같은 (root, version) 을 INSERT 하면 한쪽이 IntegrityError 로 실패 → skip(데이터
        # 오염 방지). 실패해도 위 MinIO 객체만 고아로 남아 무해.
        new_id = 0
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO WebConversationAttachments (
                    ConversationId, AccountId, ObjectKey, OriginalFilename,
                    FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                    UploadStatus, MetaJson, RootAttachmentId, VersionNumber, CreatedByRole
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploaded', %s, %s, %s, 'assistant')
                """,
                (
                    conversation_id, account_id, object_key, filename,
                    app._hmac_filename(filename), mime_type, len(body_bytes),
                    app._size_bucket(len(body_bytes)), sha256_hex, new_kind,
                    # message_id_space="display": message_id 은 _load_latest_assistant_message 가
                    # 표시 store(agent_runtime.messages / AgentMemoryMessages)에서만 읽어 항상 display
                    # 공간이다. 첨부 영속도 피드백(H5(b))과 대칭으로 id_space 를 저장해, history 표시
                    # 시 (message_id, id_space) 복합 키로만 매칭 → core 공간 숫자 겹침에 의한 wrong-bubble 차단.
                    json.dumps({"assistant_edit_of": src_id, "message_id": int(message_id or 0),
                                "message_id_space": "display"}),
                    root_id, next_version,
                ),
            )
            new_id = int(cur.lastrowid or 0)
        except Exception:
            # version 충돌(UNIQUE) 또는 기타 INSERT 실패 — skip.
            logging.getLogger(__name__).warning(
                "attachment-edit: INSERT failed (src=%s, root=%s, v=%s) — skip",
                src_id, root_id, next_version)
        finally:
            cur.close()
        if not new_id:
            continue

        # 직전 최신 버전을 superseded 마킹 — 새 버전만 목록 노출. 보안리뷰 V8: WHERE 를
        # `VersionNumber < new_version` 기준으로 둬, 직전 supersede 가 일부 실패해 비-superseded
        # 구버전이 남아 있어도 다음 materialize 가 자가 정정(더 옛 버전 전부 끔).
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE WebConversationAttachments
                SET SupersededAt = UTC_TIMESTAMP(6)
                WHERE (RootAttachmentId = %s OR Id = %s)
                  AND VersionNumber < %s AND SupersededAt IS NULL AND DeletedAt IS NULL
                """,
                (root_id, root_id, next_version),
            )
        finally:
            cur.close()
        try:
            conn.commit()
        except Exception:
            pass

        # TASK-0277: dual-write — 새 버전 + supersede 된 직전 버전(체인 전체)을 PG 로 미러(flag-gated, fail-soft).
        try:
            from web.modules import attachment_pg_mirror as _apm
            if _apm.dual_write_enabled():
                _chcur = conn.cursor()
                _chcur.execute(
                    "SELECT Id FROM WebConversationAttachments WHERE RootAttachmentId = %s OR Id = %s",
                    (root_id, root_id),
                )
                _chain_ids = [int(r[0]) for r in (_chcur.fetchall() or []) if r and r[0] is not None]
                _chcur.close()
                _apm.mirror_attachments(conn, list({*_chain_ids, int(new_id)}))
        except Exception:
            pass

        # 보안리뷰 V10(추적성): assistant 자동 materialize 를 audit. D12 정합 — raw filename/
        # bytes 미노출(categorical 메타만). fail-open: audit 실패는 materialize 를 막지 않음.
        new_row = app._load_attachment_row(conn, new_id)
        try:
            _audit_ctx = app._serialize_attachment_for_audit(new_row)
            _audit_ctx.update({
                "assistant_edit_of": src_id,
                "version_number": next_version,
                "root_attachment_id": root_id,
                "created_by_role": "assistant",
            })
            app._audit_user_action(
                conn, request, account,
                action="attachment.version.create",
                resource_type="attachment",
                resource_id=str(new_id),
                request_ctx=_audit_ctx,
            ) if request is not None else None
        except Exception:
            logging.getLogger(__name__).warning(
                "attachment-edit: version audit dispatch failed (new=%s)", new_id, exc_info=True)

        if new_row:
            created.append(app._serialize_attachment_for_api(new_row))
    return created

def _load_step_meta(
    conn,
    conversation_id: str,
    intent: str,
    created_at,
) -> dict[str, Any]:
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            pg_row = None
            with pg.cursor() as pgcur:
                if intent:
                    pgcur.execute(
                        "SELECT sql_text, result_summary_json FROM agent_runtime.steps "
                        "WHERE conversation_id = %s AND intent = %s AND created_at <= %s "
                        "ORDER BY created_at DESC LIMIT 1",
                        (conversation_id, intent, str(created_at)),
                    )
                    pg_row = pgcur.fetchone()
                if not pg_row:
                    pgcur.execute(
                        "SELECT sql_text, result_summary_json FROM agent_runtime.steps "
                        "WHERE conversation_id = %s AND created_at <= %s "
                        "ORDER BY created_at DESC LIMIT 1",
                        (conversation_id, str(created_at)),
                    )
                    pg_row = pgcur.fetchone()
            pg.close()
        except Exception:
            return {}
        if not pg_row:
            return {}
        sql_text, result_json = pg_row
        meta: dict[str, Any] = {}
        if sql_text:
            meta["sql"] = str(sql_text)
        if result_json:
            try:
                parsed = json.loads(result_json) if isinstance(result_json, str) else (result_json or {})
            except Exception:
                parsed = {}
            if isinstance(parsed, dict):
                parsed = app.normalize_step_result_summary("execute_sql" if sql_text else "", parsed)
                csv_paths = parsed.get("csv_paths")
                if isinstance(csv_paths, list) and csv_paths:
                    meta["csv_paths"] = csv_paths
        return meta
    cur = conn.cursor()
    row = None
    if intent:
        cur.execute(
            """
SELECT SqlText, ResultSummaryJson
FROM AgentMemorySteps
WHERE ConversationId = %s AND Intent = %s AND CreatedAt <= %s
ORDER BY CreatedAt DESC
LIMIT 1
            """,
            (conversation_id, intent, created_at),
        )
        row = cur.fetchone()
    if not row:
        cur.execute(
            """
SELECT SqlText, ResultSummaryJson
FROM AgentMemorySteps
WHERE ConversationId = %s AND CreatedAt <= %s
ORDER BY CreatedAt DESC
LIMIT 1
            """,
            (conversation_id, created_at),
        )
        row = cur.fetchone()
    cur.close()
    if not row:
        return {}
    sql_text, result_json = row
    meta: dict[str, Any] = {}
    if sql_text:
        meta["sql"] = str(sql_text)
    if result_json:
        try:
            parsed = json.loads(result_json)
        except Exception:
            parsed = {}
        if isinstance(parsed, dict):
            parsed = app.normalize_step_result_summary("execute_sql" if sql_text else "", parsed)
            csv_paths = parsed.get("csv_paths")
            if isinstance(csv_paths, list) and csv_paths:
                meta["csv_paths"] = csv_paths
    return meta

def _load_steps_for_run(
    conn,
    conversation_id: str,
    run_id: str,
    *,
    after_step: int = 0,
) -> list[dict[str, Any]]:
    if not conversation_id or not run_id:
        return []
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            params_pg: list[Any] = [conversation_id, run_id]
            step_clause_pg = ""
            if int(after_step or 0) > 0:
                step_clause_pg = " AND step_index > %s"
                params_pg.append(int(after_step))
            with pg.cursor() as pgcur:
                pgcur.execute(
                    f"""
SELECT step_index, action, tool, intent, work_text, work_source,
       reason_text, reason_source, args_json, sql_text,
       result_summary_json, error_text, created_at
FROM agent_runtime.steps
WHERE conversation_id = %s AND run_id = %s{step_clause_pg}
ORDER BY step_index ASC, created_at ASC
                    """,
                    tuple(params_pg),
                )
                pg_rows = pgcur.fetchall() or []
            pg.close()
        except Exception:
            pg_rows = []
        steps: list[dict[str, Any]] = []
        for (
            step_index, action, tool, intent, work_text, work_source,
            reason_text, reason_source, args_json, sql_text,
            result_json, error_text, created_at,
        ) in pg_rows:
            try:
                args = json.loads(args_json) if args_json else {}
            except Exception:
                args = {}
            result_summary: Any = None
            if result_json:
                try:
                    result_summary = json.loads(result_json) if isinstance(result_json, str) else result_json
                except Exception:
                    result_summary = result_json
            result_summary = app.normalize_step_result_summary(str(tool or ""), result_summary)
            steps.append(
                app._resolve_step_display({
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
                    "created_at": str(created_at),
                    "run_id": str(run_id),
                })
            )
        return steps
    cur = conn.cursor()
    params: list[Any] = [conversation_id, run_id]
    step_clause = ""
    if int(after_step or 0) > 0:
        step_clause = " AND StepIndex > %s"
        params.append(int(after_step))
    cur.execute(
        f"""
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
    CreatedAt
FROM AgentMemorySteps
WHERE ConversationId = %s AND RunId = %s
{step_clause}
ORDER BY StepIndex ASC, CreatedAt ASC
        """,
        tuple(params),
    )
    rows = cur.fetchall() or []
    cur.close()
    steps: list[dict[str, Any]] = []
    for (
        step_index,
        action,
        tool,
        intent,
        work_text,
        work_source,
        reason_text,
        reason_source,
        args_json,
        sql_text,
        result_json,
        error_text,
        created_at,
    ) in rows:
        try:
            args = json.loads(args_json) if args_json else {}
        except Exception:
            args = {}
        result_summary: Any = None
        if result_json:
            try:
                result_summary = json.loads(result_json)
            except Exception:
                result_summary = result_json
        result_summary = app.normalize_step_result_summary(str(tool or ""), result_summary)
        steps.append(
            app._resolve_step_display(
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
                    "created_at": str(created_at),
                    "run_id": str(run_id),
                }
            )
        )
    return steps

def _load_steps_for_message(
    conn,
    conversation_id: str,
    created_at,
    meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    run_id = ""
    if isinstance(meta, dict):
        run_id = str(meta.get("run_id") or "").strip()
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        if run_id:
            return _load_steps_for_run(conn, conversation_id, run_id)
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT run_id FROM agent_runtime.steps "
                    "WHERE conversation_id = %s AND created_at <= %s "
                    "ORDER BY created_at DESC LIMIT 1",
                    (conversation_id, str(created_at)),
                )
                row = pgcur.fetchone()
            pg.close()
            run_id = str(row[0]) if row else ""
        except Exception:
            run_id = ""
        return _load_steps_for_run(conn, conversation_id, run_id)
    if run_id:
        return _load_steps_for_run(conn, conversation_id, run_id)
    cur = conn.cursor()
    cur.execute(
        """
SELECT RunId
FROM AgentMemorySteps
WHERE ConversationId = %s AND CreatedAt <= %s
ORDER BY CreatedAt DESC
LIMIT 1
        """,
        (conversation_id, created_at),
    )
    row = cur.fetchone()
    cur.close()
    run_id = str(row[0]) if row else ""
    if not run_id:
        cur = conn.cursor()
        cur.execute(
            """
SELECT RunId
FROM AgentMemorySteps
WHERE ConversationId = %s
  AND CreatedAt >= %s
  AND CreatedAt <= DATE_ADD(%s, INTERVAL 5 SECOND)
ORDER BY CreatedAt ASC
LIMIT 1
            """,
            (conversation_id, created_at, created_at),
        )
        row = cur.fetchone()
        cur.close()
        run_id = str(row[0]) if row else ""
    return _load_steps_for_run(conn, conversation_id, run_id)

def _copy_conversation_attachments(
    conn, source_conversation_id: str, new_cid: str, fork_account_id: int,
    *, window_lower_ca=None, window_upper_ca=None,
) -> tuple[int, list[tuple[int, str, str]]]:
    """TASK-0171 Phase 2 (ADR-WEB-0005 하이브리드): 원본 대화의 활성 첨부를 fork 본으로 복사.

    - `WebConversationAttachments` 행을 새 ConversationId + fork 소유 AccountId 로 복사
      → fork 소유자가 목록/다운로드 게이트(`_account_can_access_attachment`, conversation
      소유 기반)를 그대로 통과(IDOR 게이트 변경 0).
    - blob 은 **독립 복사**(get_object_bytes → put_object_bytes, 새 ObjectKey). ObjectKey
      공유 시 원본 삭제→reconciliation 이 공유 blob 을 hard-delete 해 fork 가 404 되는
      refcount 위험이 있고, storage_minio 에 server-side copy 가 없어 get+put 으로 복사한다
      (DESIGN §6 / ADR-WEB-0005 의 "blob 재업로드 0" 에서 안전상 이탈 — 근거 주석).
    - CSV/XLSX 는 fork 전용 sandbox 를 위해 재적재 대상으로 표시(UploadStatus='uploaded' +
      MetaJson NULL)하고 (new_att_id, new_object_key, kind) 를 반환 → 호출자가 background
      ingest 를 spawn(조상 sandbox 공유 금지 — DESIGN §15 F5).
    - 첨부는 보조물이므로 **per-attachment fail-open**: 단일 첨부 복사 실패가 fork 전체를
      막지 않는다(대화·문맥은 이미 복사됨). 실패는 log + skip, 성공분만 카운트.

    반환: (copied_count, reingest_specs). reingest_specs = csv/xlsx 의 [(new_att_id, new_object_key, kind), ...].
    `WebConversationAttachments` 는 MySQL web 테이블이므로 conn(MySQL) 사용.
    """
    import uuid as _uuid
    from web.modules import storage_minio

    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT Id, ObjectKey, OriginalFilename, FilenameHmac, MimeType, SizeBytes, "
            "SizeBucket, Sha256, Kind, UploadStatus, MetaJson, CreatedAt "
            "FROM WebConversationAttachments "
            "WHERE ConversationId = %s AND DeletedAt IS NULL ORDER BY Id ASC",
            (source_conversation_id,),
        )
        src_atts = cur.fetchall() or []
    finally:
        cur.close()

    _att_windowed = window_lower_ca is not None or window_upper_ca is not None
    copied = 0
    reingest: list[tuple[int, str, str]] = []
    for att in src_atts:
        old_att_id = att.get("Id")
        # share-visibility-window: 가려진 구간(pre-floor/post-ceiling) 첨부는 fork 로 복사 안 함.
        #   첨부는 fail-open 보조물이나, windowed fork 에서는 유출 방지를 위해 out-of-window skip(fail-closed).
        if _att_windowed and app._attachment_outside_window(att.get("CreatedAt"), window_lower_ca, window_upper_ca):
            continue
        kind = str(att.get("Kind") or "other")
        old_key = str(att.get("ObjectKey") or "")
        filename = str(att.get("OriginalFilename") or "file")
        mime = str(att.get("MimeType") or "application/octet-stream")
        size_bytes = int(att.get("SizeBytes") or 0)
        try:
            # 0) 용량 cap 검사 (per-file / per-conv / per-account, D8). 업로드와 동일 게이트로
            #    반복 fork 를 통한 quota/storage 우회를 차단(REV-20260609-0004 #6). 누적 측정이라
            #    같은 fork 안에서 이미 복사한 첨부도 다음 검사에 반영된다. 초과분은 skip(fail-open).
            cap_ok, cap_reason = app._check_attachment_size_caps(
                conn,
                account_id=int(fork_account_id),
                conversation_id=new_cid,
                new_size_bytes=size_bytes,
            )
            if not cap_ok:
                logging.getLogger(__name__).warning(
                    "_copy_conversation_attachments: 용량 cap 초과로 첨부 skip "
                    "(source=%s old_att_id=%s size=%s reason=%s)",
                    source_conversation_id, old_att_id, size_bytes, cap_reason,
                )
                continue
            new_key = storage_minio.make_object_key(new_cid, _uuid.uuid4().hex, filename)
            is_sandbox_kind = kind in ("csv", "xlsx")
            new_status = "uploaded" if is_sandbox_kind else str(att.get("UploadStatus") or "uploaded")
            meta_raw = att.get("MetaJson")
            if is_sandbox_kind:
                new_meta = None
            elif isinstance(meta_raw, (dict, list)):
                new_meta = json.dumps(meta_raw, ensure_ascii=False, default=str)
            else:
                new_meta = meta_raw
            # 1) 행 INSERT 먼저 (업로드 endpoint 패턴 — REV-20260609-0004 #2 orphan 방지).
            wcur = conn.cursor()
            try:
                wcur.execute(
                    "INSERT INTO WebConversationAttachments "
                    "(ConversationId, AccountId, ObjectKey, OriginalFilename, FilenameHmac, "
                    " MimeType, SizeBytes, SizeBucket, Sha256, Kind, UploadStatus, MetaJson) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        new_cid, int(fork_account_id), new_key, filename,
                        att.get("FilenameHmac"), mime, size_bytes,
                        att.get("SizeBucket"), att.get("Sha256"), kind, new_status, new_meta,
                    ),
                )
                new_att_id = int(wcur.lastrowid or 0)
            finally:
                wcur.close()
            # 2) blob 독립 복사 (get → put). 실패 시 방금 INSERT 한 행을 보상 삭제 —
            #    blob 없는 고아 행도, 행 없는 고아 blob 도 남기지 않는다(reconciliation 정합).
            try:
                blob = storage_minio.get_object_bytes(old_key)
                storage_minio.put_object_bytes(new_key, blob, content_type=mime)
            except Exception:
                try:
                    dcur = conn.cursor()
                    dcur.execute("DELETE FROM WebConversationAttachments WHERE Id = %s", (new_att_id,))
                    dcur.close()
                except Exception:
                    logging.getLogger(__name__).warning(
                        "_copy_conversation_attachments: blob 실패 후 행 보상삭제 실패 (att_id=%s)",
                        new_att_id, exc_info=True,
                    )
                raise
            copied += 1
            # TASK-0277: dual-write — fork 으로 복사된 새 첨부 행을 PG 로 미러(flag-gated, fail-soft).
            try:
                from web.modules import attachment_pg_mirror as _apm
                _apm.mirror_attachments(conn, [new_att_id])
            except Exception:
                pass
            if is_sandbox_kind and new_att_id:
                reingest.append((new_att_id, new_key, kind))
        except Exception:
            # fail-open: 단일 첨부 복사 실패는 fork 를 막지 않는다(가시화 후 skip).
            logging.getLogger(__name__).warning(
                "_copy_conversation_attachments: 첨부 복사 실패 skip "
                "(source=%s old_att_id=%s kind=%s)",
                source_conversation_id, old_att_id, kind, exc_info=True,
            )
            continue
    return copied, reingest

def _fork_conversation_impl(
    conn,
    account: dict[str, Any],
    source_id: str,
    from_id: int | None,
    share_floor_id: int | None = None,
) -> tuple[dict[str, Any] | None, app.JSONResponse | None]:
    """REQ-20260514-0001: fork 본체 로직. 호출자가 source 접근 권한 + create 권한을 사전 검증한다.

    from_id = 상단(ceiling, "여기까지"/anchor) inclusive 컷. share_floor_id = 하단("여기부터")
    inclusive 컷(share-visibility-window). 실제 복사 window 는 요청자 멤버 window 와의 교집합.

    Returns: (success_dict, None) on success, (None, app.JSONResponse) on error.
    """
    # share-visibility-window: 요청자 멤버 window ∩ share window 로 복사 범위 확정 (fail-closed).
    _cw_status, lower_id, upper_id = app._resolve_copy_window(
        conn, source_id, int(account["id"]), share_floor_id=share_floor_id, share_ceiling_id=from_id
    )
    if _cw_status == "deny":
        return None, app._json_error("복제 처리 중 오류가 발생했습니다.", 500)
    if _cw_status == "empty":
        return None, app._json_error("공유된 범위에 복제할 대화가 없습니다.", 400)

    # cutover 후 topic/메시지/product 는 PG(agent_runtime) 에서 읽는다 (backend-aware helper).
    source_topic = app._conv_load_topic(conn, source_id)

    # 복사 대상 메시지 조회 (내부/시스템 메시지는 app._conv_copy_messages 가 제외). [lower_id, upper_id] clip.
    try:
        src_rows = app._conv_load_messages_raw(conn, source_id, upto_id=upper_id, from_id=lower_id)
    except Exception:
        return None, app._json_error("failed to load source messages", 500)
    # share-visibility-window: window 의 core(created_at) 경계 — clip 된 src_rows 에서 유도(발명 금지).
    # core_messages(LLM 문맥) 와 첨부(WebConversationAttachments.CreatedAt) clip 에 공유.
    _win_lower_ca = src_rows[0][3] if (lower_id is not None and src_rows) else None
    _win_upper_ca = src_rows[-1][3] if (upper_id is not None and src_rows) else None
    # REVIEW m1: window(하단/상단 경계) 활성인데 표시 행이 비어 있으면(경계 안 메세지 전부 삭제 등)
    # created_at 경계가 None 으로 떨어져 core 를 무필터 전량 복사하던 폴백 봉인 — core 도 복사 안 함.
    _win_bounded_empty = (lower_id is not None or upper_id is not None) and not src_rows

    # 원본 대화의 product_id / product_mode 조회 (없으면 기본 Product).
    # TASK-0052 Phase 1C G5 (Codex Claim 4 fork product_mode 복사 fix): product_mode 도 함께 조회하여 'auto' 보존.
    forked_product_mode = "pinned"
    forked_product_id, _src_product_mode = app._conv_load_product(conn, source_id)
    if _src_product_mode is not None:
        forked_product_mode = app._normalize_product_mode(_src_product_mode, default="pinned")
    # auto 모드는 product_id 가 의미 없으므로 명시적으로 NULL 유지. pinned 인데 product_id 없으면 default 채움.
    if forked_product_mode == "auto":
        forked_product_id = None
    elif not forked_product_id:
        forked_product_id = app._get_default_product_id(conn) or None

    # TASK-0052 Phase 1C G5: fork 대상 계정이 source product 에 접근 권한이 없으면 auto 강등 (운영 가능성 유지).
    # account 자체가 source 대화 read 권한이 있어 여기까지 도달했지만, fork 후 ask 단계에서 G4 로 차단되면
    # 사용자가 의문을 가지므로 fork 시점에 의도 명확화. pinned + product_id 가 있는 경우만 검사.
    if forked_product_mode == "pinned" and forked_product_id:
        if not app._account_has_product_access(account, int(forked_product_id), conn=conn):
            forked_product_mode = "auto"
            forked_product_id = None

    # 새 대화 생성 + 소유권 부여 + topic 세팅.
    from agent_core import create_new_conversation as _create_conv
    try:
        new_cid = _create_conv(conv_file=app._account_conv_file(int(account["id"])))
        app._assign_conversation_owner(conn, new_cid, int(account["id"]), force=True)
        # G1 (TASK-20260617T082131): fork 본 표식 — account insight 추출/회상에서 배제(소스가
        # 타 계정일 수 있어 owner 격리만으론 콘텐츠 출처가 격리 안 됨).
        app._mark_conversation_forked(new_cid, source_id)
        new_topic = f"[Fork] {source_topic}"[:256]
        app._conv_update_topic_product(conn, new_cid, new_topic, forked_product_id, forked_product_mode)
    except Exception:
        return None, app._json_error("failed to create forked conversation", 500)

    try:
        copied = app._conv_copy_messages(conn, new_cid, src_rows, source_id, upper_id)
    except Exception:
        # 중간 실패 시 새 대화 기록을 정리하고 error 반환.
        try:
            app.delete_conversation_records(conn, new_cid)
        except Exception:
            pass
        return None, app._json_error("failed to copy messages", 500)

    # TASK-0170 Phase 1 (ADR-WEB-0005 하이브리드): LLM 문맥(core_messages)도 복사한다.
    # 어시스턴트는 agent_runtime.core_messages 에서 대화 문맥을 읽으므로(agent_core.
    # _load_conversation_messages), 이를 복사하지 않으면 fork 본의 문맥이 비어 어시스턴트가
    # 이전 대화를 인지 못 한다(보고된 버그). anchored fork 는 앵커 메시지 시각까지, full
    # fork/duplicate 는 전체 복사. 교차계정(공유 fork)도 이 복사로 snapshot 이 된다(상시
    # 참조 아님 — DESIGN §15 F4). 경계 턴의 미세 불일치는 로드 시 _normalize_history_rows
    # 가 정규화한다(DESIGN §15 F1).
    core_copied = 0
    try:
        # share-visibility-window: core(LLM 문맥)도 [lower, upper] 로 clip (공유 created_at 경계).
        if _win_bounded_empty:
            src_core_rows = []  # window 활성 + 표시 행 0 → core 무필터 복사 방지(REVIEW m1).
        else:
            src_core_rows = app._conv_load_core_messages_raw(
                conn, source_id, _win_upper_ca, from_created_at=_win_lower_ca
            )
        core_copied = app._conv_copy_core_messages(conn, new_cid, src_core_rows)
    except Exception:
        # core_messages 복사 실패 시 fork 를 통째로 정리하고 fail-loud — 문맥 없는 반쪽
        # fork(보고된 버그 상태)를 남기지 않는다. delete 는 PG CASCADE 로 messages+core 정리.
        try:
            app.delete_conversation_records(conn, new_cid)
        except Exception:
            pass
        return None, app._json_error("failed to copy conversation context", 500)

    # TASK-0171 Phase 2 (ADR-WEB-0005 하이브리드): 첨부 복사 — 행 + 독립 blob.
    # 사용자가 fork 본에서 첨부 파일을 열람/다운로드할 수 있도록 WebConversationAttachments
    # 행을 fork 소유로 복사하고 blob 을 독립 복사한다(IDOR 게이트 무변경). CSV/XLSX 는
    # fork 전용 sandbox 를 background 재적재로 생성(조상 sandbox 공유 금지). 첨부는 보조물
    # 이라 fail-open — 복사 실패가 대화/문맥 fork 를 막지 않는다(대화·문맥은 이미 복사됨).
    att_copied = 0
    reingest_specs: list[tuple[int, str, str]] = []
    try:
        att_copied, reingest_specs = _copy_conversation_attachments(
            conn, source_id, new_cid, int(account["id"]),
            window_lower_ca=_win_lower_ca, window_upper_ca=_win_upper_ca,
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "_fork_conversation_impl: 첨부 복사 단계 실패 (new_cid=%s source=%s)",
            new_cid, source_id, exc_info=True,
        )
    # CSV/XLSX fork sandbox 재적재 (upload endpoint 와 동일 background 패턴).
    for _att_id, _obj_key, _kind in reingest_specs:
        try:
            app.threading.Thread(
                target=app._ingest_attachment_background,
                kwargs={
                    "attachment_id": int(_att_id),
                    "conversation_id": new_cid,
                    "object_key": str(_obj_key),
                    "kind": str(_kind),
                },
                name=f"fork-reingest-{_att_id}",
                daemon=True,
            ).start()
        except Exception:
            logging.getLogger(__name__).warning(
                "_fork_conversation_impl: fork sandbox 재적재 spawn 실패 (att_id=%s)",
                _att_id, exc_info=True,
            )

    try:
        app._set_account_current_conversation(conn, int(account["id"]), new_cid)
    except Exception:
        # best-effort: fork 후 현재 대화 전환 실패는 fork 결과 반환을 막지 않는다 (fail-open).
        logging.getLogger(__name__).warning(
            "_fork_conversation_impl: set current conversation failed (new_cid=%s)",
            new_cid, exc_info=True,
        )
    return (
        {
            "conversation_id": new_cid,
            "source": source_id,
            "copied": copied,
            "core_copied": core_copied,
            "attachments_copied": att_copied,
            "from_message_id": int(from_id) if from_id is not None else None,
            "topic": new_topic,
        },
        None,
    )


# ── ITEM-10 p9: 첨부 인제스트·vision 인라인 이미지 (conversations 도메인) ──

def _ingest_attachment_background(
    *,
    attachment_id: int,
    conversation_id: str,
    object_key: str,
    kind: str,
) -> None:
    """TASK-0107 Phase A.2 — upload endpoint 가 spawn 하는 background ingest.

    sandbox schema 생성 → MinIO 다운로드 → ingest_attachment (csv/xlsx) →
    MetaJson 에 sandbox_schema_name + sheets 기록 + UploadStatus='ingested'.

    실패는 silent log (UploadStatus='failed' + degraded_reason). caller (upload
    endpoint) 는 응답 후이므로 background 실패가 사용자 응답을 막지 않는다.
    """
    try:
        from web.modules import storage_minio, sandbox_schema as ss
        from modules import sandbox_ingest as si  # feature-0002 unified ns
    except Exception as exc:  # pragma: no cover — import 실패는 fail-loud log
        try:
            _conn = app._connect_memory()
            _cur = _conn.cursor()
            _cur.execute(
                "UPDATE WebConversationAttachments SET UploadStatus='failed', "
                "MetaJson=JSON_OBJECT('degraded_reason', %s) WHERE Id = %s",
                (f"ingest module import failed: {exc}", attachment_id),
            )
            _cur.close()
            _conn.commit()
            # TASK-0277: dual-write — import 실패 degraded status 도 PG 로 미러(close 前).
            try:
                from web.modules import attachment_pg_mirror as _apm
                _apm.mirror_attachments(_conn, [attachment_id])
            except Exception:
                pass
            _conn.close()
        except Exception:
            pass
        return

    schema_name = ss.sandbox_schema_name_for(conversation_id)

    # 1) MinIO 에서 bytes 가져오기
    try:
        body_bytes = storage_minio.get_object_bytes(object_key)
    except Exception as exc:
        app._mark_ingest_failed(attachment_id, f"minio fetch failed: {exc}")
        return

    # 2) sandbox schema 생성 (idempotent — IF NOT EXISTS).
    #    단일-user MVP — root user 가 maintainer/writer/cleanup 모두 수행.
    #    database=None → database=MEMORY_DB 로 열어야 step 4 의 UPDATE 가 같은
    #    conn 으로 agent_memory.WebConversationAttachments 를 찾을 수 있다.
    #    CREATE SCHEMA DDL 은 current-database 와 무관하게 동작하므로 문제 없음.
    try:
        conn = app._open_memory_connection()
    except Exception as exc:
        app._mark_ingest_failed(attachment_id, f"db connect failed: {exc}")
        return

    try:
        cur = conn.cursor()
        try:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS `{schema_name}` DEFAULT CHARSET=utf8mb4")
        finally:
            cur.close()
        try:
            conn.commit()
        except Exception:
            pass
    except Exception as exc:
        app._mark_ingest_failed(attachment_id, f"schema create failed: {exc}")
        try:
            conn.close()
        except Exception:
            pass
        return

    # 3) sandbox 안에서 ingest. table_name base = t_<attachment_id>.
    base_table = f"t_{attachment_id}"
    try:
        sandbox_conn = app._open_memory_connection(database=schema_name)
    except Exception as exc:
        app._mark_ingest_failed(attachment_id, f"sandbox connect failed: {exc}")
        try:
            conn.close()
        except Exception:
            pass
        return
    try:
        result = si.ingest_attachment(
            body_bytes,
            kind=kind,
            attachment_id=attachment_id,
            sheet_table_base=base_table,
            writer_conn=sandbox_conn,
        )
    except Exception as exc:
        app._mark_ingest_failed(attachment_id, f"ingest failed: {exc}")
        try:
            sandbox_conn.close()
            conn.close()
        except Exception:
            pass
        return
    finally:
        try:
            sandbox_conn.close()
        except Exception:
            pass

    # 4) MetaJson 갱신 + UploadStatus='ingested'.
    meta = {"sandbox_schema_name": schema_name}
    if kind == "csv":
        meta["sandbox_table_name"] = base_table
        meta["columns"] = result.get("columns") or []
        meta["rows_inserted"] = int(result.get("rows_inserted") or 0)
        if result.get("degraded_reason"):
            meta["degraded_reason"] = result["degraded_reason"]
    else:  # xlsx
        meta["sheets"] = result.get("sheets") or []
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE WebConversationAttachments SET UploadStatus='ingested', "
            "MetaJson=%s WHERE Id = %s",
            (json.dumps(meta, ensure_ascii=False), attachment_id),
        )
        cur.close()
        conn.commit()
        # TASK-0277: dual-write — ingest 후 status='ingested' + MetaJson 변경을 PG 로 미러.
        try:
            from web.modules import attachment_pg_mirror as _apm
            _apm.mirror_attachments(conn, [attachment_id])
        except Exception:
            pass
    except Exception as exc:
        app._mark_ingest_failed(attachment_id, f"meta update failed: {exc}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def _prepare_vision_inline_images(
    conn,
    account_id: int,
    attachment_ids: list[int],
    *,
    model: str,
    conversation_id: str | None,
) -> tuple[str | None, int, list[dict[str, Any]]]:
    """vision 첨부 (kind=image) pre-fetch + 임시 file 작성.

    Returns:
        (temp_file_path, image_count, audit_attachments)

        - vision 미지원 모델 / image kind 0 → (None, 0, []).
        - 정상 → (path, count, audit_attachments). caller 가 env
          ATTACHMENT_IMAGE_INLINE_PATH 로 전달, finally 에서 cleanup.
          audit_attachments 는 S2.5 (attachment.vision.invoke) 의 ChangeJson 용
          metadata — D12 정합: filename / object_key 미포함, id 와 size_bucket
          만.

    D13 정합: server-side bytes read + base64 inline. signed URL 외부 송신 0.
    D12 정합: audit ChangeJson 은 metadata-only (별 caller 책임 — 본 helper 는
              결과만 제공).
    """
    if not attachment_ids or not app.model_supports_vision(model):
        return (None, 0, [])

    # image kind 첨부 선별 (count cap 적용)
    # TASK-0277: read cutover — PG 우선(IDOR AccountId 가드 동형), 실패 시 MySQL 폴백.
    rows = None
    try:
        from web.modules import attachment_pg_mirror as _apm
        if _apm.read_pg_enabled():
            rows = _apm.pg_select_vision_images(conversation_id, int(account_id), attachment_ids, int(app._VISION_IMAGE_COUNT_CAP))
    except Exception:
        rows = None
        logging.getLogger(__name__).warning(
            "_prepare_vision_inline_images: PG read failed → MySQL fallback", exc_info=True)
    if rows is None:
        try:
            cur = conn.cursor(dictionary=True)
            try:
                placeholders = ", ".join(["%s"] * len(attachment_ids))
                # TASK-0284: ConversationId 스코프(대화 접근권은 ask 핸들러가 게이트), 미전달 시 AccountId 폴백.
                # 타 대화 첨부 id 주입은 ConversationId 불일치로 차단(IDOR 안전망 유지) — TASK-0132 의
                # "타 계정 첨부 inject 차단" 의도를 대화 단위로 일반화한다.
                if conversation_id:
                    _sc_col, _sc_val = "ConversationId", str(conversation_id)
                else:
                    _sc_col, _sc_val = "AccountId", int(account_id)
                params = tuple(int(i) for i in attachment_ids) + (_sc_val, int(app._VISION_IMAGE_COUNT_CAP))
                cur.execute(
                    f"""
                    SELECT Id, ObjectKey, MimeType, OriginalFilename, SizeBytes, SizeBucket
                    FROM WebConversationAttachments
                    WHERE Id IN ({placeholders})
                      AND {_sc_col} = %s
                      AND Kind = 'image'
                      AND DeletedAt IS NULL
                      AND DeletePending = 0
                    ORDER BY Id ASC
                    LIMIT %s
                    """,
                    params,
                )
                rows = cur.fetchall() or []
            finally:
                cur.close()
        except Exception:
            return (None, 0, [])

    if not rows:
        return (None, 0, [])

    # bytes pre-fetch + base64 + size cap
    from web.modules import storage_minio
    import base64 as _b64

    inline_entries: list[dict[str, str]] = []
    audit_attachments: list[dict[str, Any]] = []
    for row in rows:
        object_key = str(row.get("ObjectKey") or "").strip()
        mime_type = str(row.get("MimeType") or "image/png").strip() or "image/png"
        filename = str(row.get("OriginalFilename") or "").strip()
        size_bytes = int(row.get("SizeBytes") or 0)
        size_bucket = str(row.get("SizeBucket") or "").strip()
        attachment_id = int(row.get("Id") or 0)
        if not object_key or attachment_id <= 0:
            continue
        if size_bytes > app._VISION_IMAGE_SIZE_CAP_BYTES:
            continue
        try:
            data_bytes = storage_minio.get_object_bytes(object_key)
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
            continue
        if len(data_bytes) > app._VISION_IMAGE_SIZE_CAP_BYTES:
            continue
        b64 = _b64.b64encode(data_bytes).decode("ascii")
        inline_entries.append({
            "filename": filename,  # caller (agent_core) 가 provider 미송신 — 로그용
            "mime_type": mime_type,
            "base64_data": b64,
        })
        # S2.5 audit ChangeJson 용 metadata (D12 정합 — filename / object_key 미포함)
        audit_attachments.append({
            "attachment_id": attachment_id,
            "mime_type": mime_type,
            "size_bucket": size_bucket,
        })

    if not inline_entries:
        return (None, 0, [])

    # 임시 file 작성 (caller 가 finally 에서 cleanup)
    suffix = uuid.uuid4().hex[:12]
    cid_seg = str(conversation_id or "no-cid")[:24].replace("/", "_")
    path = f"{app._inline_tmp_dir()}/mysql_ai_inline_{cid_seg}_{suffix}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(inline_entries, f, ensure_ascii=False)
    except OSError:
        return (None, 0, [])

    return (path, len(inline_entries), audit_attachments)


# ── ITEM-10 p11 ──

async def _dispatch_ask_run_worker(*, conn, account, conv_id, run_kwargs, request=None) -> dict[str, Any]:
    from shared.db import _pg_connect
    from modules import ask_jobs as _aj
    from shared.config import AGENT_ASK_WORKER_STALE_SEC

    account_id = int(account["id"])
    if not conv_id:
        return {"error": "대화 컨텍스트를 확인할 수 없습니다.", "conversation_id": "",
                "_http_status": 400}

    # readiness gate (M7) — 살아있는 worker 없으면 무한 대기 대신 즉시 503.
    if not app._ask_worker_ready(conn):
        return {"error": "요청 처리 워커가 일시적으로 준비되지 않았습니다. 잠시 후 다시 시도해 주세요.",
                "conversation_id": conv_id, "_http_status": 503}

    # enqueue payload = run_agent kwargs 13개 (conv_file/temperature/api_key/output_mode 제외).
    # gc-ask-sender-attrib: sender_username(그룹 발신자 귀속)도 worker 경로로 동등 전달 — 미포함 시
    # worker mode 에서만 발신자 미러 meta 가 누락돼 inproc 와 동작이 갈린다(_payload_to_kwargs 복원).
    payload = {
        "user_message": run_kwargs.get("user_message", ""),
        "conversation_id": conv_id,
        "model": run_kwargs.get("model"),
        "product_id": run_kwargs.get("product_id"),
        "role_id": run_kwargs.get("role_id"),
        "account_id": account_id,
        "sender_username": run_kwargs.get("sender_username"),
        "allowed_schemas": run_kwargs.get("allowed_schemas"),
        "product_mode": run_kwargs.get("product_mode", "pinned"),
        "attachment_ids": run_kwargs.get("attachment_ids") or [],
        "new_attachment_ids": run_kwargs.get("new_attachment_ids") or [],
        "image_inline_path": run_kwargs.get("image_inline_path"),
        "text_inline_path": run_kwargs.get("text_inline_path"),
        "reasoning_level": run_kwargs.get("reasoning_level"),  # feature-0003: 추론 강도(worker 경로 패리티)
    }

    _user_message = payload.get("user_message", "")

    def _enqueue() -> int | None:
        pg = _pg_connect()
        try:
            # 멱등성(ask-dedup-idempotency): 워커 모드 /api/ask 는 long-poll 로 연결을 수십
            # 초~분 잡으므로, web 재배포/프록시 EOF 로 그 연결이 끊겨 사용자가 같은 메시지를
            # 재전송하면 두 번째 run 이 떠 요청·답변이 2회 처리되던 결함이 있었다(중복 전송).
            # 같은 (conv, account, user_message) 로 활성(pending/running) job 이 이미 있으면
            # 새 job 을 만들지 않고 그 job_id 를 반환 → 아래 attach 루프가 기존 run 에 붙어
            # 동일 결과를 동기 응답한다. 사전 검사가 흔한 순차 재전송(끊김→재전송, 수백 ms~수십 s
            # 간격, 첫 job 이미 commit)을 조기 흡수하고, enqueue 의 dedup_message NOT EXISTS 가
            # *commit 된 중복* 에 대한 atomic backstop 이다(완전 동시 sub-ms 충돌까지 막으려면
            # partial unique index 가 필요 — 관측된 결함은 순차라 현 범위로 충분).
            try:
                _dup = _aj.find_active_dup_ask_job(
                    pg, conversation_id=conv_id, account_id=account_id,
                    user_message=_user_message,
                    stale_seconds=int(AGENT_ASK_WORKER_STALE_SEC),
                )
            except Exception:
                _dup = None
            if _dup is not None:
                logging.getLogger(__name__).info(
                    "ask-dedup: 활성 중복 ask_job 재사용 conv=%s job=%s (새 run 미생성)",
                    conv_id, _dup,
                )
                # 기존 run 의 KV 상태/run_id 를 보존 — 새 sentinel 로 덮어쓰지 않는다.
                return _dup
            # enqueue~claim 갭에도 프런트가 '처리중' 을 보도록 last_status 선기록(현행 race
            # 가드와 동등). worker 가 claim 시 run_id 와 함께 다시 processing 기록.
            # TASK-0241: 선기록의 last_status_run_id 를 직전 run(취소된 run 포함)이 아닌 *새 sentinel*
            # 으로 박는다. run_id 없이 쓰면 KV 의 run_id 가 직전(취소된) run 으로 남아, orphan 의
            # terminal canceled write 가 app.set_run_status(only_if_current_run) 가드를 우회해 이 새 요청의
            # processing 을 canceled 로 클로버한다(BLOCKER). sentinel(≠직전 run_id, 비어있지 않음)이면
            # 가드가 정확히 skip 한다. worker 가 claim 후 실제 run_id 로 (R_new, processing) 를 무조건
            # 덮어쓴다(agent_core 2472) — sentinel 은 갭 동안만 존재하는 가교다.
            try:
                _enq_sentinel = "enqpre-" + uuid.uuid4().hex
                app.set_run_status(conn, conv_id, "processing", run_id=_enq_sentinel)
            except Exception:
                pass
            _jid = _aj.enqueue_ask_job(
                pg, conversation_id=conv_id, run_id=None, account_id=account_id,
                payload=payload, account_limit=app.WEB_PARALLEL_LIMIT,
                stale_seconds=int(AGENT_ASK_WORKER_STALE_SEC),
                dedup_message=_user_message,
            )
            if _jid is not None:
                return _jid
            # INSERT 억제됨 — 슬롯 가득(429) vs dedup race(기존 attach) 구분. 사전 검사~enqueue
            # 사이에 동시 요청이 막 commit 한 중복일 수 있으므로 한 번 더 조회한다.
            try:
                return _aj.find_active_dup_ask_job(
                    pg, conversation_id=conv_id, account_id=account_id,
                    user_message=_user_message,
                    stale_seconds=int(AGENT_ASK_WORKER_STALE_SEC),
                )
            except Exception:
                return None
        finally:
            try:
                pg.close()
            except Exception:
                pass

    try:
        job_id = await asyncio.to_thread(_enqueue)
    except Exception as exc:
        return {"error": f"요청 큐 등록에 실패했습니다: {exc}", "conversation_id": conv_id,
                "_http_status": 500}
    if job_id is None:
        return {"error": "동시 요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요.",
                "conversation_id": conv_id, "_http_status": 429}

    # 내부 attach: KV last_status 가 terminal 될 때까지 long-poll. run budget 보다 길게
    # 대기(stale + margin) — to_thread 가 full run 을 await 하던 것과 동일하게 동기 블록.
    max_wait = int(AGENT_ASK_WORKER_STALE_SEC) + 30
    loop = asyncio.get_event_loop()
    deadline = loop.time() + max_wait
    while loop.time() < deadline:
        # TASK-0241: 클라이언트가 "중단" 으로 이 /api/ask fetch 를 abort 하면 attach 를 즉시 끝내
        # per-account 웹 슬롯(_acquire_request_slot)을 곧바로 반납한다 → 취소 직후 재요청이 슬롯에
        # 막히지 않는다. is_disconnected 미지원/예외 환경은 best-effort(아래 job/KV terminal 이 backstop).
        if request is not None:
            try:
                if await request.is_disconnected():
                    break
            except Exception:
                pass
        try:
            snap = await asyncio.to_thread(app._build_ask_status_snapshot, conn, conv_id)
        except Exception:
            snap = None
        if snap and (str(snap.get("raw_status") or "") in app._ASK_TERMINAL_STATUSES
                     or snap.get("is_stale")):
            break
        # TASK-0241: KV last_status 외에 *이 job 자체* 의 terminal 도 종료 조건으로 둔다. 사용자가
        # 취소 후 같은 대화에 즉시 재요청하면 KV last_status 는 새 run 이 인계(processing)하고
        # orphan 의 canceled write 는 supersede 가드로 건너뛰어져, 이 attach 가 자기 job 의 종료를
        # 영영 못 보고 max_wait 까지 슬롯을 점유할 수 있다. job_id 로 직접 terminal 을 확인해 attach
        # 수명을 자기 job 수명에 정확히 묶는다(슬롯 누수 차단).
        try:
            _job_status = await asyncio.to_thread(app._get_ask_job_status, job_id)
        except Exception:
            _job_status = None
        if _job_status in app._ASK_TERMINAL_STATUSES:
            break
        await asyncio.sleep(0.5)

    return await asyncio.to_thread(app._build_worker_agent_result, job_id, conv_id)

def _prepare_text_inline_attachments(
    conn,
    account_id: int,
    attachment_ids: list[int],
    *,
    conversation_id: str | None = None,
) -> str | None:
    """text kind 첨부파일의 raw content 를 MinIO 에서 읽어 임시 JSON file 저장.

    Returns: 임시 file path (env 로 전달) 또는 None (text 파일 없음 / 오류).
    성공 시 caller 는 env["ATTACHMENT_TEXT_INLINE_PATH"] 를 설정하고,
    LLM 호출 완료 후 _cleanup_text_inline(path) 로 정리해야 한다.
    """
    if not attachment_ids:
        return None
    try:
        from web.modules import storage_minio
    except (ImportError, Exception):
        return None

    # TASK-0277: read cutover — PG 우선(IDOR AccountId 가드 동형), 실패 시 MySQL 폴백.
    rows = None
    try:
        from web.modules import attachment_pg_mirror as _apm
        if _apm.read_pg_enabled():
            rows = _apm.pg_select_text_inline(conversation_id, int(account_id), attachment_ids, app._TEXT_INLINE_COUNT_CAP)
    except Exception:
        rows = None
        logging.getLogger(__name__).warning(
            "_prepare_text_inline_attachments: PG read failed → MySQL fallback", exc_info=True)
    if rows is None:
        try:
            cur = conn.cursor(dictionary=True)
            placeholders = ", ".join(["%s"] * len(attachment_ids))
            # TASK-0284: ConversationId 스코프(대화 접근권은 ask 핸들러가 게이트), 미전달 시 AccountId 폴백.
            if conversation_id:
                _sc_col, _sc_val = "ConversationId", str(conversation_id)
            else:
                _sc_col, _sc_val = "AccountId", int(account_id)
            cur.execute(
                f"SELECT Id, OriginalFilename, ObjectKey, Kind, SizeBytes, AccountId "
                f"FROM WebConversationAttachments "
                f"WHERE Id IN ({placeholders}) AND {_sc_col} = %s AND Kind = 'text' "
                f"AND UploadStatus = 'uploaded' AND DeletedAt IS NULL AND DeletePending = 0 "
                # count cap 초과 시 가장 최근(=방금 첨부한) 파일을 보존하도록 DESC. 이전엔 ASC 라
                # 한 대화에 cap(20) 초과 첨부 시 방금 올린 파일이 조용히 누락됐다(사용자 불만).
                f"ORDER BY Id DESC LIMIT %s",
                # TASK-0284: 타 대화 text 첨부 inject 차단(ConversationId), TASK-0132 의 계정 단위 가드를 대화 단위로 일반화.
                tuple(int(i) for i in attachment_ids) + (_sc_val, app._TEXT_INLINE_COUNT_CAP),
            )
            rows = cur.fetchall() or []
            cur.close()
        except Exception:
            return None

    if not rows:
        return None

    inline_entries: list[dict] = []
    for row in rows:
        aid = int(row.get("Id") or 0)
        filename = str(row.get("OriginalFilename") or "")
        object_key = str(row.get("ObjectKey") or "").strip()
        size_bytes = int(row.get("SizeBytes") or 0)
        if not object_key:
            continue
        # TASK-0284: account 폴백 경로에서만 AccountId 재검증(D16). conversation 스코프(기본)는 SQL
        # WHERE ConversationId 가 이미 보장하므로, 같은 대화에 타 계정이 올린 첨부도 정상 주입한다.
        if not conversation_id:
            row_account_id = int(row.get("AccountId") or 0)
            if row_account_id != account_id:
                continue
        # size cap — 큰 파일은 skip (prompt overflow 방지)
        if size_bytes > app._TEXT_INLINE_SIZE_CAP_BYTES:
            # 용량 초과 파일은 잘려서 주입 (앞 64KB 만)
            cap_note = True
        else:
            cap_note = False
        try:
            data_bytes = storage_minio.get_object_bytes(object_key)
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
            continue
        try:
            text_content = data_bytes[:app._TEXT_INLINE_SIZE_CAP_BYTES].decode("utf-8", errors="replace")
        except Exception:
            continue
        if not text_content.strip():
            continue
        inline_entries.append({
            "attachment_id": aid,
            "filename": filename,
            "content": text_content,
            "truncated": cap_note or (len(data_bytes) > app._TEXT_INLINE_SIZE_CAP_BYTES),
        })

    if not inline_entries:
        return None

    # DESC 로 최신 우선 선별했으므로, 표시는 시간순(오래된→최신)으로 되돌린다.
    inline_entries.reverse()

    suffix = uuid.uuid4().hex[:12]
    cid_seg = str(conversation_id or "no-cid")[:24].replace("/", "_")
    path = f"{app._inline_tmp_dir()}/mysql_ai_text_{cid_seg}_{suffix}.json"
    try:
        with open(path, "w", encoding="utf-8") as _tf:
            json.dump(inline_entries, _tf, ensure_ascii=False)
    except OSError:
        return None
    return path


# ── ITEM-10 p12: 공유(share) 링크/정책 헬퍼 ──

def _share_generate_token() -> str:
    """256-bit URL-safe token. UNIQUE 충돌 시 호출자가 retry."""
    return app._share_secrets.token_urlsafe(32)

def _share_load_active(conn, token: str) -> dict[str, Any] | None:
    """Token 으로 share row 조회 (revoked/expired 도 row 반환 — 호출자가 상태 판정).

    이름은 historical (`active`) 이나 실제로는 token 일치 row 를 그대로 반환한다.
    RevokedAt / ExpiresAt 판정은 호출자(public view / fork)가 수행한다.
    """
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
SELECT Id, ConversationId, Token, ScopeMode, AnchorMessageId, FloorMessageId,
       CreatedBy, CreatedAt, RevokedAt, ViewCount, LastViewedAt, PolicyVersion, ExpiresAt,
       Joinable
FROM WebConversationShares
WHERE Token = %s
LIMIT 1
            """,
            (token,),
        )
        row = cur.fetchone()
        return row
    finally:
        cur.close()

def _share_row_expired(conn, share_id: int) -> bool:
    """DB 시계 기준 share 만료 여부 (`ExpiresAt IS NOT NULL AND ExpiresAt <= NOW()`).

    만료 판정을 항상 DB NOW() 로 평가해 web 프로세스 ↔ DB 간 clock skew 를 차단한다
    (생성 시 `DATE_ADD(NOW(), ...)` 와 동일 시계 도메인). 무기한(NULL) share 는 False.
    """
    try:
        sid = int(share_id)
    except Exception:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM WebConversationShares "
            "WHERE Id = %s AND ExpiresAt IS NOT NULL AND ExpiresAt <= NOW() LIMIT 1",
            (sid,),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()

def _share_anchor_belongs_to_conversation(conn, conversation_id: str, anchor_message_id: int) -> bool:
    """AnchorMessageId 가 해당 ConversationId 의 메시지인지 검증 (backend-aware)."""
    return app._conv_message_exists(conn, conversation_id, int(anchor_message_id))

def _share_sanitize_step(step: Any) -> dict[str, Any]:
    """단일 step 을 share 익명 노출용 화이트리스트로 재구성.

    - step: {tool, sql, reason, intent, work, result_summary} 만 통과.
    - result_summary: {preview_table} 만 통과 — csv_paths(서버 경로)·preview(결과 전문)·
      기타 키 제거. preview_table 자체는 columns/rows/truncated 의 표 데이터로 share.js 가
      이미 표로 렌더하는 (공유 의도된) 결과 미리보기다.
    - step 의 args(원본 tool 인자)·error(원본 오류 본문)·csv_paths 등은 통과 목록에 없어 제거.
    """
    if not isinstance(step, dict):
        return {}
    clean: dict[str, Any] = {k: step[k] for k in app._SHARE_STEP_ALLOWED_KEYS if k in step}
    rs = clean.get("result_summary")
    if isinstance(rs, dict):
        rs_clean = {k: rs[k] for k in app._SHARE_RESULT_SUMMARY_ALLOWED_KEYS if k in rs}
        if rs_clean:
            clean["result_summary"] = rs_clean
        else:
            clean.pop("result_summary", None)
    elif "result_summary" in clean:
        # dict 아닌 result_summary 는 통째 제거 (예측 못한 형태의 raw payload 누출 차단).
        clean.pop("result_summary", None)
    return clean

def _share_attach_sanitized_steps(conn, conversation_id: str, created_at, meta_obj: Any) -> Any:
    """assistant 메시지 meta 에 share 익명 노출용으로 sanitize 한 steps 를 주입 후 meta 반환.

    share API 는 저장 meta_json(보통 {run_id, duration_ms})만 읽어 steps 가 비어 있다.
    실행 단계(쿼리/결과)는 일반 대화 로드 경로처럼 agent_runtime.steps 에서 동적 조립해야
    "결과셋에 따라 실행된 쿼리 전환" navigator 가 공유 페이지에서도 동작한다. 단, 익명 노출이므로
    각 step 을 _share_sanitize_step 으로 화이트리스트 통과시킨다 (csv_paths/preview/args/error 제거).

    meta_obj 가 None 이면 steps 가 실제로 조립될 때만 새 dict 를 만들어 반환(없으면 None 유지).
    """
    try:
        raw_steps = app._load_steps_for_message(conn, conversation_id, created_at, meta_obj if isinstance(meta_obj, dict) else None)
    except Exception:
        # steps 조립 실패는 공유 뷰 렌더를 막지 않는다 — 본문/폴백만 표시.
        logging.getLogger(__name__).warning(
            "_share_attach_sanitized_steps: steps 조립 실패 (conversation_id=%s)",
            conversation_id, exc_info=True,
        )
        return meta_obj
    sanitized = [_share_sanitize_step(s) for s in (raw_steps or []) if isinstance(s, dict)]
    sanitized = [s for s in sanitized if s]
    if not sanitized:
        return meta_obj
    if not isinstance(meta_obj, dict):
        meta_obj = {}
    meta_obj["steps"] = sanitized
    return meta_obj

def _share_redact_message_content(content: str, meta_obj) -> tuple[str, bool, dict | None]:
    """attachment_derived 메시지 본문을 redact. 반환: (redacted_content, was_redacted, meta_obj_clean).

    raw attachment payload (CSV sample / vision 분석 결과 / PDF excerpt) 가 share view
    에 노출되지 않도록 본문을 가림. meta 의 sensitive 필드도 함께 redact (final_sql /
    result_rows / steps 등은 D12 정합으로 별도 categorical 메타만 유지).
    """
    if not app._meta_has_attachment_derived(meta_obj):
        return content, False, meta_obj
    meta_clean = None
    if isinstance(meta_obj, dict):
        meta_clean = {k: v for k, v in meta_obj.items() if k not in app._SHARE_REDACTED_META_KEYS}
        meta_clean["attachment_derived"] = True
        meta_clean["redacted_by_share_policy"] = True
    return app.SHARE_POLICY_REDACT_TEXT, True, meta_clean

def _share_load_messages(conn, conversation_id: str, anchor_message_id: int | None, *, floor_message_id: int | None = None, share_token_policy_version: int | None = None) -> list[dict[str, Any]]:
    """공유 view 용 메시지 목록. anchor 가 주어지면 `Id <= anchor` (inclusive, "여기까지 공유").

    share-visibility-window: floor_message_id 가 주어지면 `Id >= floor` (inclusive, "여기부터 공유").
    익명 공유 스냅샷은 hard window — 라이브 tail 병합 없음(익명 뷰어는 라이브 멤버 아님).

    fork 의 `app._is_internal_message` 와 동일 필터를 적용해 내부/시스템 메시지를 숨긴다.

    TASK-0094 Sprint 1 Phase 8 (D9 + R-F7): share_token_policy_version 이 NULL 또는
    app.SHARE_POLICY_VERSION_CURRENT 보다 작으면 attachment_derived 메시지 본문 자동 redact.
    기존 token (PolicyVersion=1 또는 NULL) 도 배포 즉시 새 정책 적용.
    """
    # cutover 후 메시지는 PG(agent_runtime.messages) 에서 읽는다 (backend-aware helper).
    # 반환 행은 (id, role, content, created_at, meta_json) tuple. meta_json 은 PG 면 dict.
    rows = app._conv_load_messages_raw(conn, conversation_id, anchor_message_id, from_id=floor_message_id)
    visible: list[dict[str, Any]] = []
    # R-F7: 정책 version 비교 — token 발급 시 version < 현재 면 자동 redact 대상.
    redact_active = (
        share_token_policy_version is None
        or int(share_token_policy_version or 0) < app.SHARE_POLICY_VERSION_CURRENT
    )
    for row in rows:
        msg_id, role_raw, content_raw, created_at, meta_json = row
        role = str(role_raw or "")
        content = str(content_raw or "")
        meta_str = meta_json if isinstance(meta_json, str) else (
            json.dumps(meta_json) if isinstance(meta_json, dict) else None
        )
        if app._is_internal_message(role, content, meta_str):
            continue
        # feature-0009 gc-join-notice: 멤버십 이벤트(참여 알림)는 대화 내부 멤버 전용 in-room
        # 표식이다. anonymous 공유 스냅샷에는 노출하지 않는다(멤버 username 비노출 + share.js
        # 는 pill 렌더 분기가 없어 정합성도 깨짐). in-room /api/history 경로에서만 pill 로 보인다.
        _ev_meta = meta_json if isinstance(meta_json, dict) else None
        if _ev_meta is None and isinstance(meta_json, str) and meta_json:
            try:
                _parsed_ev = json.loads(meta_json)
                _ev_meta = _parsed_ev if isinstance(_parsed_ev, dict) else None
            except Exception:
                _ev_meta = None
        if _ev_meta and _ev_meta.get("event_type"):
            continue
        meta_obj: Any = None
        if isinstance(meta_json, dict):
            meta_obj = dict(meta_json)
        elif meta_json:
            try:
                meta_obj = json.loads(meta_json)
            except Exception:
                meta_obj = None
        # D9 + R-F7: attachment_derived 메시지 redact (token PolicyVersion 무관, 현 정책 v2 부터 활성).
        was_redacted = False
        if redact_active:
            content, was_redacted, meta_obj = _share_redact_message_content(content, meta_obj)
        # 실행된 쿼리 전환 navigator 데이터: assistant 메시지에 한해 agent_runtime.steps 에서
        # sanitize 한 steps 를 동적 조립한다. redact 된 attachment_derived 메시지는 제외(steps 까지
        # 가려야 하므로 — _share_redact_message_content 가 이미 steps 키를 제거했고 재조립도 안 함).
        if role == "assistant" and not was_redacted:
            meta_obj = _share_attach_sanitized_steps(conn, conversation_id, created_at, meta_obj)
        visible.append(
            {
                "id": int(msg_id or 0),
                "role": role,
                "content": content,
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else (str(created_at) if created_at else None),
                "meta": meta_obj,
            }
        )
    return visible
