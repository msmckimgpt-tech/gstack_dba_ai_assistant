"""feature-0012 ITEM-10 p4 — 대화 저장소(conversation store) 공용 헬퍼 (비-라우트 모듈).

app.py 에서 이동. share/conversations 두 도메인이 소비하는 공용 데이터 계층 — `_` 접두라
routers.register_all 자동 등록에서 제외. app 전역은 `app.X` 동적 참조(패치-단일점, 판정표 §4),
app.py 꼬리 rebind 가 기존 `app._conv_*`·app 내부 bare 호출을 보존한다.
"""

import json
import logging
from typing import Any

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
