"""Runtime Backend abstraction — MySQL ↔ Postgres dual-write 의 단일 진입점.

TASK-0109 Phase 2 AR plan 의 M2 cycle. M2-a (TASK-0113) 에서 ABC + skeleton,
M2-b (TASK-0114) 에서 method body + dual-write wrapper + caller 수정,
M2-c (TASK-0115) 에서 cross-DB audit + SLA 검증 도구 (본 cycle),
M2-d (TASK-0116) 에서 xmax pg_branch tagging (본 cycle).

KB backend (kb_backend.py, TASK-0019 M2-a) 패턴 답습.

설계 원칙 (ADR-0027 + KB패턴 정합):
1. **단일 RuntimeBackend ABC** — 6 method group:
   - core_conversations: save_conversation (upsert)
   - core_messages:      save_core_message (insert)
   - kv:                 save_kv (upsert)
   - messages:           save_memory_message (insert)
   - steps:              save_memory_step (insert)
   - summary:            save_memory_summary (upsert)
2. **Dual-write = Postgres mirror 패턴** — caller 의 기존 MySQL cursor.execute 는
   그대로 유지. `_dual_write_runtime_mirror()` 가 그 직후에 PgRuntimeBackend 만 호출.
3. **Partial failure 격리** — Postgres mirror 실패가 MySQL caller 흐름에 영향 없음
   (AGENT_RUNTIME_PG_REQUIRED=0 시 silent log, =1 시 fail-loud).
4. **Idempotency** — core_conversations/kv/summary 는 ON CONFLICT DO UPDATE,
   core_messages/messages/steps 는 INSERT (append-only, 멱등 불필요).
5. **search_path 전역 변경 없음 (ADR-0027)** — 모든 Postgres SQL은
   `agent_runtime.table_name` schema-qualified 명시.

Method 그룹 매핑 (caller 위치 → ABC method):
- core_conversations: agent_core.py:_ensure_conversation / _update_conversation_topic
                      → save_conversation()
- core_messages:      agent_core.py:_save_message
                      → save_core_message()
- kv:                 memory.py:save_memory_kv
                      → save_kv()
- messages:           memory.py:save_memory_message
                      → save_memory_message()
- steps:              memory.py:save_memory_step
                      → save_memory_step()
- summary:            memory.py:save_memory_summary
                      → save_memory_summary()
"""

from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger("agent_core.runtime_backend")

# ─────────────────────────────────────────────────────────────────────────────
# Env-driven config (M2-b 진입 전 .env 에 추가 예정)
# ─────────────────────────────────────────────────────────────────────────────

def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default


AGENT_RUNTIME_PG_REQUIRED: bool = _env_bool("AGENT_RUNTIME_PG_REQUIRED", False)

# M4: read backend 선택 ("mysql" default, "postgres" = cutover 활성)
AGENT_RUNTIME_READ_BACKEND: str = (
    os.environ.get("AGENT_RUNTIME_READ_BACKEND", "mysql").strip() or "mysql"
).lower()

# M2-b: dual-write 활성 여부 (default: False, M2-b 활성 시 .env 에 설정)
AGENT_RUNTIME_DUAL_WRITE: bool = _env_bool("AGENT_RUNTIME_DUAL_WRITE", False)


# ─────────────────────────────────────────────────────────────────────────────
# Postgres SQL constants (agent_runtime schema-qualified, ADR-0027)
# ─────────────────────────────────────────────────────────────────────────────

_PG_UPSERT_CONVERSATION = """
INSERT INTO agent_runtime.core_conversations
    (conversation_id, topic, owner_account_id, product_id, product_mode)
VALUES
    (%(conversation_id)s, %(topic)s, %(owner_account_id)s, %(product_id)s, %(product_mode)s)
ON CONFLICT (conversation_id) DO UPDATE SET
    topic            = COALESCE(EXCLUDED.topic, core_conversations.topic),
    owner_account_id = COALESCE(EXCLUDED.owner_account_id, core_conversations.owner_account_id),
    product_id       = COALESCE(EXCLUDED.product_id, core_conversations.product_id),
    product_mode     = COALESCE(EXCLUDED.product_mode, core_conversations.product_mode),
    updated_at       = now()
RETURNING conversation_id, (xmax = 0) AS pg_inserted
"""

_PG_INSERT_CORE_MESSAGE = """
INSERT INTO agent_runtime.core_messages
    (conversation_id, role, content, tool_calls, tool_call_id, name, sender_account_id, recall_floor_created_at)
VALUES
    (%(conversation_id)s, %(role)s, %(content)s, %(tool_calls)s::jsonb, %(tool_call_id)s, %(name)s, %(sender_account_id)s, %(recall_floor_created_at)s)
RETURNING id
"""

# deploy-gap fallback: recall_floor_created_at 컬럼(alembic 0036) 부재 시(pre-mig) 사용.
_PG_INSERT_CORE_MESSAGE_LEGACY = """
INSERT INTO agent_runtime.core_messages
    (conversation_id, role, content, tool_calls, tool_call_id, name, sender_account_id)
VALUES
    (%(conversation_id)s, %(role)s, %(content)s, %(tool_calls)s::jsonb, %(tool_call_id)s, %(name)s, %(sender_account_id)s)
RETURNING id
"""

# feature-0019 message-editing (alembic 0041): 브랜치 포인터를 함께 기록하는 INSERT.
#   branch 인자(parent_message_id/edit_root/edit_version) 가 지정될 때만 사용 — 미분기 정상 append
#   는 위 _PG_INSERT_CORE_MESSAGE 그대로(회귀 0). 컬럼 부재(pre-0041) 시 caller 가 42703 처리.
_PG_INSERT_CORE_MESSAGE_BRANCH = """
INSERT INTO agent_runtime.core_messages
    (conversation_id, role, content, tool_calls, tool_call_id, name, sender_account_id,
     recall_floor_created_at, parent_message_id, edit_root_message_id, edit_version)
VALUES
    (%(conversation_id)s, %(role)s, %(content)s, %(tool_calls)s::jsonb, %(tool_call_id)s, %(name)s,
     %(sender_account_id)s, %(recall_floor_created_at)s, %(parent_message_id)s,
     %(edit_root_message_id)s, %(edit_version)s)
RETURNING id
"""

_PG_UPSERT_KV = """
INSERT INTO agent_runtime.kv (conversation_id, key, value)
VALUES (%(conversation_id)s, %(key)s, %(value)s)
ON CONFLICT (conversation_id, key) DO UPDATE SET
    value      = EXCLUDED.value,
    updated_at = now()
RETURNING conversation_id, (xmax = 0) AS pg_inserted
"""

_PG_INSERT_MEMORY_MESSAGE = """
INSERT INTO agent_runtime.messages
    (conversation_id, role, content, meta_json)
VALUES
    (%(conversation_id)s, %(role)s, %(content)s, %(meta_json)s::jsonb)
RETURNING id
"""

# feature-0019 message-editing: 표시 store 브랜치 포인터 + core 짝 링크를 함께 기록하는 INSERT.
#   branch 인자 지정 시만 사용 — 미분기 정상 append 는 위 _PG_INSERT_MEMORY_MESSAGE 그대로.
_PG_INSERT_MEMORY_MESSAGE_BRANCH = """
INSERT INTO agent_runtime.messages
    (conversation_id, role, content, meta_json,
     parent_message_id, edit_root_message_id, edit_version, core_message_id)
VALUES
    (%(conversation_id)s, %(role)s, %(content)s, %(meta_json)s::jsonb,
     %(parent_message_id)s, %(edit_root_message_id)s, %(edit_version)s, %(core_message_id)s)
RETURNING id
"""

_PG_INSERT_STEP = """
INSERT INTO agent_runtime.steps
    (conversation_id, run_id, step_index, action, tool, intent,
     work_text, work_source, reason_text, reason_source,
     args_json, sql_text, result_summary_json, error_text)
VALUES
    (%(conversation_id)s, %(run_id)s, %(step_index)s, %(action)s, %(tool)s, %(intent)s,
     %(work_text)s, %(work_source)s, %(reason_text)s, %(reason_source)s,
     %(args_json)s, %(sql_text)s, %(result_summary_json)s, %(error_text)s)
"""

_PG_UPSERT_SUMMARY = """
INSERT INTO agent_runtime.summary (conversation_id, summary)
VALUES (%(conversation_id)s, %(summary)s)
ON CONFLICT (conversation_id) DO UPDATE SET
    summary    = EXCLUDED.summary,
    updated_at = now()
RETURNING conversation_id, (xmax = 0) AS pg_inserted
"""

# ─────────────────────────────────────────────────────────────────────────────
# M4: Postgres read SQL (agent_runtime schema-qualified, ADR-0027)
# ─────────────────────────────────────────────────────────────────────────────

_PG_LOAD_KV = """
SELECT value FROM agent_runtime.kv
WHERE conversation_id = %(conversation_id)s AND key = %(key)s
LIMIT 1
"""

_PG_LOAD_KV_ALL = """
SELECT key, value FROM agent_runtime.kv
WHERE conversation_id = %(conversation_id)s
"""

_PG_LOAD_KV_BY_KEY_VALUE = """
SELECT DISTINCT conversation_id FROM agent_runtime.kv
WHERE key = %(key)s AND value = %(value)s
"""

_PG_LOAD_KV_BY_KEY = """
SELECT conversation_id, value FROM agent_runtime.kv
WHERE key = %(key)s
"""

_PG_LOAD_SUMMARY = """
SELECT summary FROM agent_runtime.summary
WHERE conversation_id = %(conversation_id)s
LIMIT 1
"""

_PG_LOAD_MESSAGES = """
SELECT role, content, meta_json, created_at
FROM agent_runtime.messages
WHERE conversation_id = %(conversation_id)s
ORDER BY created_at DESC
LIMIT %(limit)s
"""

_PG_LOAD_STEPS = """
SELECT
    step_index, action, tool, intent,
    work_text, work_source, reason_text, reason_source,
    args_json, sql_text, result_summary_json, error_text,
    run_id, created_at
FROM agent_runtime.steps
WHERE conversation_id = %(conversation_id)s
ORDER BY created_at DESC
LIMIT %(limit)s
"""

# gc-assistant-dialect-context (RC-2): sender_account_id 를 함께 로드한다 — 그룹대화에서 LLM 이
# 누가 무슨 말을 했는지(발신자 라벨)를 맥락으로 받도록(REQ-GC-R5). 유일 소비처는 agent_core
# _load_conversation_messages 의 PG read path (tuple index 5 로 매핑).
_PG_LOAD_CORE_MESSAGES = """
SELECT role, content, tool_calls, tool_call_id, name, sender_account_id
FROM agent_runtime.core_messages
WHERE conversation_id = %(conversation_id)s
ORDER BY id ASC
LIMIT %(limit)s
"""

# share-visibility-window: 멤버별 가시 경계(created_at 로 bridge)를 적용한 LLM recall.
#   floor_ca  = 하단 경계("여기부터 공유") — created_at >= floor_ca (NULL=하단 무제한).
#   ceil_ca   = 상단 경계("여기까지 공유") — created_at <= ceil_ca (NULL=상단 무제한).
#   joined_ca = 라이브 참여 시점 — 멤버가 자기 참여 이후 대화(post-join tail)는 계속 봐야 하므로
#               가시범위 = [floor,ceiling] ∪ [joined,∞). 중간 갭(ceiling, joined)만 은닉.
# 가려진 pre-floor/중간 구간의 core_messages 행은 애초에 로드되지 않아 프롬프트 인젝션으로도
# 추출 불가(물리 배제, SECURITY.md §14 — 대화 history 는 datamark 대상 아님이라 이 배제가 유일 방어).
_PG_LOAD_CORE_MESSAGES_WINDOWED = """
SELECT role, content, tool_calls, tool_call_id, name, sender_account_id
FROM agent_runtime.core_messages
WHERE conversation_id = %(conversation_id)s
  AND (%(floor_ca)s IS NULL OR created_at >= %(floor_ca)s)
  AND (%(ceil_ca)s IS NULL OR created_at <= %(ceil_ca)s
       OR (%(joined_ca)s IS NOT NULL AND created_at >= %(joined_ca)s))
  AND NOT (recall_floor_created_at IS NOT NULL
           AND %(floor_ca)s IS NOT NULL
           AND recall_floor_created_at < %(floor_ca)s)
ORDER BY id ASC
LIMIT %(limit)s
"""

# feature-0019 message-editing: 대화의 브랜치 게이트 상태(첫 편집에서만 has_branches=true).
#   has_branches=false(거의 모든 대화) → 로더가 기존 linear 경로 그대로(회귀 0, AC-ME-2).
_PG_LOAD_BRANCH_STATE = """
SELECT has_branches, active_leaf_message_id
FROM agent_runtime.core_conversations
WHERE conversation_id = %(conversation_id)s
LIMIT 1
"""

# feature-0019 message-editing: 활성 브랜치 leaf 전진(정상 append) — has_branches 대화만 호출.
_PG_SET_ACTIVE_LEAF = """
UPDATE agent_runtime.core_conversations
SET active_leaf_message_id = %(leaf_id)s
WHERE conversation_id = %(conversation_id)s
"""

# feature-0019 message-editing: 표시 store 전용 활성 leaf 전진(정상 append) — has_branches 대화만.
_PG_SET_ACTIVE_DISPLAY_LEAF = """
UPDATE agent_runtime.core_conversations
SET active_display_leaf_message_id = %(leaf_id)s
WHERE conversation_id = %(conversation_id)s
"""

# feature-0019 message-editing: 표시 store 브랜치 게이트 상태(active_display_leaf).
_PG_LOAD_DISPLAY_BRANCH_STATE = """
SELECT has_branches, active_display_leaf_message_id
FROM agent_runtime.core_conversations
WHERE conversation_id = %(conversation_id)s
LIMIT 1
"""

# feature-0019 message-editing: 첫 편집에서 브랜치 게이트 활성 + core/display 활성 leaf 확정(원자).
#   core leaf = 전달값(호출자가 max_core_message_id 로 산출), display leaf = 표시 store tail.
_PG_ENABLE_BRANCHES = """
UPDATE agent_runtime.core_conversations
SET has_branches = true,
    active_leaf_message_id = %(leaf_id)s,
    active_display_leaf_message_id = (
        SELECT MAX(id) FROM agent_runtime.messages WHERE conversation_id = %(conversation_id)s
    )
WHERE conversation_id = %(conversation_id)s
"""

# feature-0019 message-editing: 첫 편집 시 기존 linear 메시지의 parent 체인 backfill(각 메시지의
#   parent = 직전 메시지 by id). 이후 active-path CTE 가 성립한다. 이미 parent 있는 행은 보존.
#   (core_messages 와 messages 각각 자기 id-space 로 backfill — ANCHOR INV-5.)
_PG_BACKFILL_CORE_PARENTS = """
WITH ord AS (
    SELECT id, LAG(id) OVER (ORDER BY id) AS prev_id
    FROM agent_runtime.core_messages
    WHERE conversation_id = %(conversation_id)s
)
UPDATE agent_runtime.core_messages c
SET parent_message_id = ord.prev_id
FROM ord
WHERE c.id = ord.id AND ord.prev_id IS NOT NULL AND c.parent_message_id IS NULL
"""

_PG_BACKFILL_MSG_PARENTS = """
WITH ord AS (
    SELECT id, LAG(id) OVER (ORDER BY id) AS prev_id
    FROM agent_runtime.messages
    WHERE conversation_id = %(conversation_id)s
)
UPDATE agent_runtime.messages c
SET parent_message_id = ord.prev_id
FROM ord
WHERE c.id = ord.id AND ord.prev_id IS NOT NULL AND c.parent_message_id IS NULL
"""

# conv-audit FR-ask-orphan-redeploy-dead-air(RC-2): ask job requeue 재실행이 사용자 메시지를
# 중복 저장하는지 판정. `since`(job.created_at) 이후 구간만 본다 — 그 전의 동일 문구는 사용자가
# 실제로 반복한 과거 turn 이므로 억제 대상이 아니다. sender_account_id 는 NULL 도 동일 취급.
_PG_USER_MESSAGE_EXISTS_CORE = """
SELECT 1
FROM agent_runtime.core_messages
WHERE conversation_id = %(conversation_id)s
  AND role = 'user'
  AND content = %(content)s
  AND created_at >= %(since)s
  AND sender_account_id IS NOT DISTINCT FROM %(sender_account_id)s
LIMIT 1
"""

# 표시 store 미러(agent_runtime.messages)는 sender **컬럼**이 없고 content 가 strip 되어 저장된다.
# 그룹 대화 미러는 발신자를 meta_json 에 싣는다(`sender_account_id`) — 그룹에서 다른 멤버가 같은
# 문장을 보낸 행을 "이미 저장됨" 으로 오인해 진짜 미러를 빠뜨리지 않도록, 미러가 발신자를
# 싣는 경우(그룹)엔 그 값까지 일치해야 한다(적대 리뷰 security H3). 1:1 미러는 발신자를 싣지
# 않고 발신자도 한 명뿐이라 %(mirror_sender)s=NULL 로 들어와 종전 판정 그대로다.
_PG_USER_MESSAGE_EXISTS_DISPLAY = """
SELECT 1
FROM agent_runtime.messages
WHERE conversation_id = %(conversation_id)s
  AND role = 'user'
  AND content = %(content)s
  AND created_at >= %(since)s
  AND (%(mirror_sender)s IS NULL
       OR (meta_json ->> 'sender_account_id') = %(mirror_sender)s)
LIMIT 1
"""

# feature-0019 message-editing: 대화 tail(현재 활성 leaf 초기값) = MAX(core_messages.id).
_PG_MAX_CORE_MESSAGE_ID = """
SELECT MAX(id) FROM agent_runtime.core_messages WHERE conversation_id = %(conversation_id)s
"""

# feature-0019 message-editing: 활성 브랜치 경로만 로드하는 active-path recursive CTE.
#   active_leaf 에서 parent_message_id 를 root 까지 역추적 → 활성 가지만(옛 브랜치 배제).
#   window 술어(floor/ceil/joined + recall_floor)는 _PG_LOAD_CORE_MESSAGES_WINDOWED 와 동일하게
#   최종 SELECT 에 합성(가려진 구간 물리 배제 유지, SECURITY §21). floor/ceil/joined 가 전부 NULL
#   이면 술어가 항상 TRUE → 비-windowed 와 동치. ORDER BY id ASC LIMIT = 기존 로더 tail 의미 유지.
#   **명시 캐스팅 필수(POST-DEPLOY hotfix)**: 비-windowed 브랜치 대화는 floor/ceil/joined 가 전부
#   None → psycopg 가 untyped NULL 로 전송 → `$n IS NULL` 에서 PG "could not determine data type of
#   parameter" 로 로더 전체 실패(WINDOWED 쿼리는 windowed 시에만 호출돼 항상 non-None 이라 무사).
#   active_leaf_id 도 첫 메시지 편집 시 None 가능 → 동일. 각 파라미터에 ::bigint/::timestamptz 캐스팅.
_PG_LOAD_CORE_MESSAGES_BRANCH = """
WITH RECURSIVE path AS (
    SELECT id, role, content, tool_calls, tool_call_id, name, sender_account_id,
           parent_message_id, created_at, recall_floor_created_at
    FROM agent_runtime.core_messages
    WHERE conversation_id = %(conversation_id)s AND id = %(active_leaf_id)s::bigint
    UNION ALL
    SELECT m.id, m.role, m.content, m.tool_calls, m.tool_call_id, m.name, m.sender_account_id,
           m.parent_message_id, m.created_at, m.recall_floor_created_at
    FROM agent_runtime.core_messages m
    JOIN path p ON m.id = p.parent_message_id
    WHERE m.conversation_id = %(conversation_id)s
)
SELECT role, content, tool_calls, tool_call_id, name, sender_account_id
FROM path
WHERE (%(floor_ca)s::timestamptz IS NULL OR created_at >= %(floor_ca)s::timestamptz)
  AND (%(ceil_ca)s::timestamptz IS NULL OR created_at <= %(ceil_ca)s::timestamptz
       OR (%(joined_ca)s::timestamptz IS NOT NULL AND created_at >= %(joined_ca)s::timestamptz))
  AND NOT (recall_floor_created_at IS NOT NULL
           AND %(floor_ca)s::timestamptz IS NOT NULL
           AND recall_floor_created_at < %(floor_ca)s::timestamptz)
ORDER BY id ASC
LIMIT %(limit)s
"""

# share-visibility-window: restricted 게이트 + 발신자 멤버 window 를 1 쿼리로(LEFT JOIN).
#   has_restricted_members=false(거의 모든 대화) → resolver 가 즉시 None(필터 우회).
#   account_id=NULL(시스템)이면 m.* 미매칭 → role NULL(비멤버).
_PG_LOAD_MEMBER_VISIBILITY = """
SELECT c.has_restricted_members,
       m.role, m.visible_floor_created_at, m.visible_ceiling_created_at, m.joined_at
FROM agent_runtime.core_conversations c
LEFT JOIN agent_runtime.conversation_members m
       ON m.conversation_id = c.conversation_id AND m.account_id = %(account_id)s
WHERE c.conversation_id = %(conversation_id)s
LIMIT 1
"""

_PG_LIST_CONVERSATIONS = """
SELECT conversation_id, COALESCE(topic, '(미설정)') AS topic, created_at
FROM agent_runtime.core_conversations
ORDER BY created_at DESC
LIMIT %(limit)s
"""
# No owner_account_id filter — intentional parity with MySQL list_conversations which
# also returns all conversations without per-owner scoping (single-tenant CLI context).
# Multi-tenant web UI _list_conversations (feature-0003 app.py) is a separate code path
# with its own RBAC; it is NOT migrated in AR-M4 due to cross-DB JOIN dependency.

_PG_GET_CONV_MESSAGES_FULL = """
SELECT id, role, content, tool_calls, tool_call_id, name, created_at
FROM agent_runtime.core_messages
WHERE conversation_id = %(conversation_id)s
ORDER BY id ASC
LIMIT %(limit)s
"""

# feature-0009 gc-join-notice: 시스템/멤버십 이벤트(참여 알림 등) core_message 의 `name` sentinel.
# 이런 이벤트는 unread 배지 집계(role IN ('user','assistant'))에 포함되도록 role='user' 로
# 기록하되, LLM 대화 히스토리 조립(_normalize_history_rows)에서는 이 name 을 보고 완전히
# 배제한다 — 안 그러면 "X님이 참여했습니다" 가 발신자 라벨 붙은 user 턴으로 LLM 에 주입돼
# assistant 오응답·맥락 오염을 일으킨다(§18.8 적대 패널 BLOCKING). writer(feature-0003
# app._save_group_join_event_pg)와 filter(feature-0002 agent_core)가 이 단일 상수를 공유한다.
EVENT_MESSAGE_NAME = "__event__"



# ─────────────────────────────────────────────────────────────────────────────
# RuntimeBackend ABC — 6 method group (KB 패턴 답습, TASK-0113 M2-a).
# ─────────────────────────────────────────────────────────────────────────────

class RuntimeBackend(ABC):
    """Agent runtime write 추상화 — MySQL ↔ Postgres dual-write 단일 진입점."""

    backend_name: str = "abstract"

    @abstractmethod
    def save_conversation(
        self, conn: Any, *, conversation_id: str, topic: Optional[str] = None,
        owner_account_id: Optional[int] = None, product_id: Optional[int] = None,
        product_mode: str = "pinned",
    ) -> None: ...

    @abstractmethod
    def save_core_message(
        self, conn: Any, *, conversation_id: str, role: str,
        content: Optional[str] = None, tool_calls: Optional[Any] = None,
        tool_call_id: Optional[str] = None, name: Optional[str] = None,
        sender_account_id: Optional[int] = None,
    ) -> int: ...

    @abstractmethod
    def save_kv(
        self, conn: Any, *, conversation_id: str, key: str, value: str,
    ) -> None: ...

    @abstractmethod
    def save_memory_message(
        self, conn: Any, *, conversation_id: str, role: str, content: str,
        meta_json: Optional[str] = None,
    ) -> None: ...

    @abstractmethod
    def save_memory_step(
        self, conn: Any, *, conversation_id: str, run_id: str, step_index: int,
        action: str, tool: str, intent: str,
        work_text: Optional[str] = None, work_source: Optional[str] = None,
        reason_text: Optional[str] = None, reason_source: Optional[str] = None,
        args_json: str = "{}", sql_text: Optional[str] = None,
        result_summary_json: Optional[str] = None, error_text: Optional[str] = None,
    ) -> None: ...

    @abstractmethod
    def save_memory_summary(
        self, conn: Any, *, conversation_id: str, summary: str,
    ) -> None: ...


# ─────────────────────────────────────────────────────────────────────────────
# MysqlRuntimeBackend — M4 cutover 이전의 backward-compat placeholder.
# M4 완료 시점에 caller 가 본 backend 로 routing (현재는 caller 가 raw SQL 직접 실행).
# ─────────────────────────────────────────────────────────────────────────────

class MysqlRuntimeBackend(RuntimeBackend):
    backend_name = "mysql"

    def save_conversation(self, conn, *, conversation_id, topic=None,
                          owner_account_id=None, product_id=None, product_mode="pinned"):
        raise NotImplementedError("M4 cutover 이전: caller 가 raw SQL 직접 실행")

    def save_core_message(self, conn, *, conversation_id, role, content=None,
                          tool_calls=None, tool_call_id=None, name=None,
                          sender_account_id=None):
        raise NotImplementedError("M4 cutover 이전: caller 가 raw SQL 직접 실행")

    def save_kv(self, conn, *, conversation_id, key, value):
        raise NotImplementedError("M4 cutover 이전: caller 가 raw SQL 직접 실행")

    def save_memory_message(self, conn, *, conversation_id, role, content, meta_json=None):
        raise NotImplementedError("M4 cutover 이전: caller 가 raw SQL 직접 실행")

    def save_memory_step(self, conn, *, conversation_id, run_id, step_index,
                         action, tool, intent, work_text=None, work_source=None,
                         reason_text=None, reason_source=None, args_json="{}",
                         sql_text=None, result_summary_json=None, error_text=None):
        raise NotImplementedError("M4 cutover 이전: caller 가 raw SQL 직접 실행")

    def save_memory_summary(self, conn, *, conversation_id, summary):
        raise NotImplementedError("M4 cutover 이전: caller 가 raw SQL 직접 실행")


# ─────────────────────────────────────────────────────────────────────────────
# PgRuntimeBackend — Postgres agent_runtime write.
# M2-a skeleton: NotImplementedError. M2-b 에서 실제 SQL 구현.
# search_path 전역 변경 없음 (ADR-0027) — 모든 SQL schema-qualified.
# ─────────────────────────────────────────────────────────────────────────────

class PgRuntimeBackend:
    """PostgreSQL agent_kb.agent_runtime write backend.

    psycopg3 conn 으로 INSERT / UPSERT SQL 실행 (autocommit=True).
    모든 SQL은 `agent_runtime.table_name` schema-qualified (ADR-0027, search_path 전역 변경 없음).
    """

    backend_name: str = "postgres"

    def save_conversation(
        self,
        conn: Any,
        *,
        conversation_id: str,
        topic: Optional[str] = None,
        owner_account_id: Optional[int] = None,
        product_id: Optional[int] = None,
        product_mode: str = "pinned",
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(_PG_UPSERT_CONVERSATION, {
                "conversation_id": conversation_id,
                "topic": topic,
                "owner_account_id": owner_account_id,
                "product_id": product_id,
                "product_mode": product_mode or "pinned",
            })

    def save_core_message(
        self,
        conn: Any,
        *,
        conversation_id: str,
        role: str,
        content: Optional[str] = None,
        tool_calls: Optional[Any] = None,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None,
        sender_account_id: Optional[int] = None,
        recall_floor_created_at=None,
        parent_message_id: Optional[int] = None,
        edit_root_message_id: Optional[int] = None,
        edit_version: int = 1,
    ) -> int:
        import json as _json
        tc_json = _json.dumps(tool_calls, ensure_ascii=False) if tool_calls is not None else None
        params = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "tool_calls": tc_json,
            "tool_call_id": tool_call_id,
            "name": name,
            "sender_account_id": int(sender_account_id) if sender_account_id is not None else None,
            "recall_floor_created_at": recall_floor_created_at,
        }
        # feature-0019 message-editing: 브랜치 인자가 지정되면 브랜치 포인터를 함께 기록.
        #   미분기 정상 append(parent=None·edit_root=None·edit_version=1)는 기존 경로 그대로(회귀 0).
        _branch_write = (
            parent_message_id is not None
            or edit_root_message_id is not None
            or edit_version != 1
        )
        with conn.cursor() as cur:
            if _branch_write:
                cur.execute(_PG_INSERT_CORE_MESSAGE_BRANCH, {
                    **params,
                    "parent_message_id": int(parent_message_id) if parent_message_id is not None else None,
                    "edit_root_message_id": int(edit_root_message_id) if edit_root_message_id is not None else None,
                    "edit_version": int(edit_version),
                })
                row = cur.fetchone()
                return int(row[0]) if row else 0
            try:
                cur.execute(_PG_INSERT_CORE_MESSAGE, params)
            except Exception as exc:  # noqa: BLE001
                # deploy-gap: recall_floor_created_at 컬럼 부재(42703, pre-mig 0036) → 그 컬럼 없이 재삽입.
                # (windowed 멤버는 컬럼 존재 후에만 생성되므로 이 fallback 로 답변이 유실되지 않는다.)
                if getattr(exc, "sqlstate", None) == "42703":
                    cur.execute(_PG_INSERT_CORE_MESSAGE_LEGACY, {
                        k: v for k, v in params.items() if k != "recall_floor_created_at"
                    })
                else:
                    raise
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def save_kv(
        self,
        conn: Any,
        *,
        conversation_id: str,
        key: str,
        value: str,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(_PG_UPSERT_KV, {
                "conversation_id": conversation_id,
                "key": key,
                "value": value,
            })

    def save_memory_message(
        self,
        conn: Any,
        *,
        conversation_id: str,
        role: str,
        content: str,
        meta_json: Optional[str] = None,
        parent_message_id: Optional[int] = None,
        edit_root_message_id: Optional[int] = None,
        edit_version: int = 1,
        core_message_id: Optional[int] = None,
    ) -> int:
        # feature-0019 message-editing: 브랜치 인자 지정 시 표시 store 브랜치 포인터 + core 링크를
        #   함께 기록하고 신규 id 반환. 미분기 정상 append 는 기존 INSERT 그대로(회귀 0). 반환 id 는
        #   display active_leaf 전진·core 링크에 사용(기존 caller 는 반환값 무시 → 무영향).
        _branch_write = (
            parent_message_id is not None
            or edit_root_message_id is not None
            or edit_version != 1
            or core_message_id is not None
        )
        with conn.cursor() as cur:
            if _branch_write:
                cur.execute(_PG_INSERT_MEMORY_MESSAGE_BRANCH, {
                    "conversation_id": conversation_id, "role": role, "content": content,
                    "meta_json": meta_json,
                    "parent_message_id": int(parent_message_id) if parent_message_id is not None else None,
                    "edit_root_message_id": int(edit_root_message_id) if edit_root_message_id is not None else None,
                    "edit_version": int(edit_version),
                    "core_message_id": int(core_message_id) if core_message_id is not None else None,
                })
            else:
                cur.execute(_PG_INSERT_MEMORY_MESSAGE, {
                    "conversation_id": conversation_id,
                    "role": role,
                    "content": content,
                    "meta_json": meta_json,
                })
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def set_active_display_leaf(self, conn: Any, *, conversation_id: str, leaf_id: int) -> None:
        """feature-0019: 표시 store 정상 append 후 display 활성 leaf 전진(has_branches 대화만)."""
        with conn.cursor() as cur:
            cur.execute(_PG_SET_ACTIVE_DISPLAY_LEAF, {"conversation_id": conversation_id, "leaf_id": int(leaf_id)})

    def load_display_branch_state(self, conn: Any, *, conversation_id: str) -> dict:
        """feature-0019: 표시 store 브랜치 게이트 상태. 반환 {"has_branches", "active_leaf_id"}(display id).

        컬럼 부재(pre-migration 42703) → has_branches=False(무회귀 기본).
        """
        try:
            with conn.cursor() as cur:
                cur.execute(_PG_LOAD_DISPLAY_BRANCH_STATE, {"conversation_id": conversation_id})
                row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "sqlstate", None) == "42703":
                return {"has_branches": False, "active_leaf_id": None}
            raise
        if row is None:
            return {"has_branches": False, "active_leaf_id": None}
        return {"has_branches": bool(row[0]), "active_leaf_id": row[1]}

    def save_memory_step(
        self,
        conn: Any,
        *,
        conversation_id: str,
        run_id: str,
        step_index: int,
        action: str,
        tool: str,
        intent: str,
        work_text: Optional[str] = None,
        work_source: Optional[str] = None,
        reason_text: Optional[str] = None,
        reason_source: Optional[str] = None,
        args_json: str = "{}",
        sql_text: Optional[str] = None,
        result_summary_json: Optional[str] = None,
        error_text: Optional[str] = None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(_PG_INSERT_STEP, {
                "conversation_id": conversation_id,
                "run_id": run_id,
                "step_index": step_index,
                "action": action,
                "tool": tool,
                "intent": intent,
                "work_text": work_text,
                "work_source": work_source,
                "reason_text": reason_text,
                "reason_source": reason_source,
                "args_json": args_json,
                "sql_text": sql_text,
                "result_summary_json": result_summary_json,
                "error_text": error_text,
            })

    def save_memory_summary(
        self,
        conn: Any,
        *,
        conversation_id: str,
        summary: str,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(_PG_UPSERT_SUMMARY, {
                "conversation_id": conversation_id,
                "summary": summary,
            })

    # ── M4 read methods ──────────────────────────────────────────────────────

    def load_kv(self, conn: Any, *, conversation_id: str, key: str) -> str:
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_KV, {"conversation_id": conversation_id, "key": key})
            row = cur.fetchone()
        return str(row[0]) if row and row[0] is not None else ""

    def load_kv_all(self, conn: Any, *, conversation_id: str) -> list:
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_KV_ALL, {"conversation_id": conversation_id})
            return cur.fetchall() or []

    def load_kv_by_key(self, conn: Any, *, key: str) -> list:
        """(conversation_id, value) 튜플 리스트 반환 — value 필터 없음 (client-side 필터용)."""
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_KV_BY_KEY, {"key": key})
            return cur.fetchall() or []

    def load_kv_by_key_value(self, conn: Any, *, key: str, value: str) -> list:
        """conversation_id 리스트 반환 — key + value 양쪽 일치."""
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_KV_BY_KEY_VALUE, {"key": key, "value": value})
            rows = cur.fetchall() or []
        return [str(r[0]) for r in rows if r and r[0]]

    def load_summary(self, conn: Any, *, conversation_id: str) -> Optional[str]:
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_SUMMARY, {"conversation_id": conversation_id})
            row = cur.fetchone()
        return str(row[0]) if row and row[0] is not None else None

    def load_messages(self, conn: Any, *, conversation_id: str, limit: int = 50) -> list:
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_MESSAGES, {"conversation_id": conversation_id, "limit": limit})
            return cur.fetchall() or []

    def load_steps(self, conn: Any, *, conversation_id: str, limit: int = 50) -> list:
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_STEPS, {"conversation_id": conversation_id, "limit": limit})
            return cur.fetchall() or []

    def load_branch_state(self, conn: Any, *, conversation_id: str) -> dict:
        """feature-0019 message-editing: 대화의 브랜치 게이트 상태.

        반환: {"has_branches": bool, "active_leaf_id": int|None}.
        컬럼 부재(pre-migration, UndefinedColumn 42703) → has_branches=False(무회귀 기본).
        그 외 예외는 상위(_read_runtime_pg)로 전파 → None → 로더가 기존 linear 경로.
        """
        try:
            with conn.cursor() as cur:
                cur.execute(_PG_LOAD_BRANCH_STATE, {"conversation_id": conversation_id})
                row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "sqlstate", None) == "42703":  # UndefinedColumn (pre-migration)
                return {"has_branches": False, "active_leaf_id": None}
            raise
        if row is None:
            return {"has_branches": False, "active_leaf_id": None}
        return {"has_branches": bool(row[0]), "active_leaf_id": row[1]}

    def set_active_leaf(self, conn: Any, *, conversation_id: str, leaf_id: int) -> None:
        """feature-0019: 정상 append 후 활성 브랜치 leaf 를 전진(has_branches 대화만 호출)."""
        with conn.cursor() as cur:
            cur.execute(_PG_SET_ACTIVE_LEAF, {"conversation_id": conversation_id, "leaf_id": int(leaf_id)})

    def enable_branches(self, conn: Any, *, conversation_id: str, leaf_id: int) -> None:
        """feature-0019: 첫 편집 — parent 체인 backfill(core+display) + 게이트 활성 + 활성 leaf 확정.

        idempotent: 이미 parent 있는 행은 보존, 이미 has_branches 여도 leaf 재확정만.
        """
        with conn.cursor() as cur:
            cur.execute(_PG_BACKFILL_CORE_PARENTS, {"conversation_id": conversation_id})
            cur.execute(_PG_BACKFILL_MSG_PARENTS, {"conversation_id": conversation_id})
            cur.execute(_PG_ENABLE_BRANCHES, {"conversation_id": conversation_id, "leaf_id": int(leaf_id)})

    def user_message_persisted_since(
        self, conn: Any, *, conversation_id: str, content: str,
        sender_account_id: Any = None, since: Any = None,
        mirror_sender_account_id: Any = None,
    ) -> dict:
        """이 job 수명(since 이후) 안에 동일 user 메시지가 이미 저장됐는지.

        conv-audit FR-ask-orphan-redeploy-dead-air(RC-2): ask job 이 requeue 되면 재실행이
        `_save_message(user)` 를 다시 돌아 **사용자 메시지가 화면에 두 번 보인다**(실측 60일
        9대화). 재시도에서만 이 확인을 거쳐 중복 저장을 건너뛴다. `since` 는 job.created_at —
        그 이전의 동일 문구(사용자가 진짜로 같은 말을 반복한 과거 turn)는 대상이 아니다.

        `mirror_sender_account_id`: 표시 미러가 발신자를 meta 에 싣는 경우(그룹)의 그 값.
        None(1:1) 이면 미러에 발신자 정보가 없으므로 content+시각만으로 판정한다.

        반환: {"core": bool, "display": bool} — 두 store 를 각각 판정한다(한쪽만 저장된
        부분 실패에서 나머지 한쪽을 잃지 않도록).
        """
        out = {"core": False, "display": False}
        if since is None:
            return out
        text = str(content or "")
        _mirror_sender = (None if mirror_sender_account_id is None
                          else str(int(mirror_sender_account_id)))
        with conn.cursor() as cur:
            cur.execute(_PG_USER_MESSAGE_EXISTS_CORE, {
                "conversation_id": conversation_id, "content": text,
                "sender_account_id": sender_account_id, "since": since,
            })
            out["core"] = cur.fetchone() is not None
            cur.execute(_PG_USER_MESSAGE_EXISTS_DISPLAY, {
                "conversation_id": conversation_id, "content": text.strip(),
                "since": since, "mirror_sender": _mirror_sender,
            })
            out["display"] = cur.fetchone() is not None
        return out

    def max_core_message_id(self, conn: Any, *, conversation_id: str):
        """feature-0019: 대화의 현재 tail(활성 leaf 초기값). 없으면 None."""
        with conn.cursor() as cur:
            cur.execute(_PG_MAX_CORE_MESSAGE_ID, {"conversation_id": conversation_id})
            row = cur.fetchone()
            return row[0] if row and row[0] is not None else None

    def load_core_messages(
        self, conn: Any, *, conversation_id: str, limit: int = 200,
        floor_ca=None, ceil_ca=None, joined_ca=None, use_branch: bool = False, active_leaf_id=None,
    ) -> list:
        # feature-0019 message-editing: use_branch=True(has_branches 대화)면 active_leaf 에서 시작하는
        #   active-path CTE 로 활성 브랜치 경로만 로드(옛 브랜치 배제). window 술어는 CTE 최종 SELECT
        #   에 그대로 합성. active_leaf_id=None(첫 메시지 편집 브랜치 전이 window)이면 CTE anchor 가
        #   없어 empty(정확: 새 첫 메시지 이전엔 문맥 없음). use_branch=False(거의 모든 대화) →
        #   아래 기존 linear 경로 그대로(회귀 0, AC-ME-2).
        # share-visibility-window: floor/ceiling 이 하나라도 있으면 windowed 쿼리로 가려진 구간 배제.
        windowed = floor_ca is not None or ceil_ca is not None
        with conn.cursor() as cur:
            if use_branch:
                cur.execute(
                    _PG_LOAD_CORE_MESSAGES_BRANCH,
                    {
                        "conversation_id": conversation_id, "limit": limit,
                        "active_leaf_id": active_leaf_id,
                        "floor_ca": floor_ca, "ceil_ca": ceil_ca, "joined_ca": joined_ca,
                    },
                )
            elif windowed:
                cur.execute(
                    _PG_LOAD_CORE_MESSAGES_WINDOWED,
                    {
                        "conversation_id": conversation_id, "limit": limit,
                        "floor_ca": floor_ca, "ceil_ca": ceil_ca, "joined_ca": joined_ca,
                    },
                )
            else:
                cur.execute(_PG_LOAD_CORE_MESSAGES, {"conversation_id": conversation_id, "limit": limit})
            return cur.fetchall() or []

    def load_member_visibility(self, conn: Any, *, conversation_id: str, account_id) -> dict:
        """share-visibility-window: 대화의 restricted 게이트 + 발신자 멤버 window 를 1 쿼리로.

        반환 dict:
          {"schema_missing": True}                — visible_* 컬럼 부재(pre-migration, UndefinedColumn
                                                    42703). windowed 멤버가 존재할 수 없어 안전(None 처리).
          {"has_restricted": bool, "role": str|None,
           "floor_ca": ts|None, "ceil_ca": ts|None, "joined_ca": ts|None}
        account_id 가 None(시스템/CLI)이면 LEFT JOIN 미매칭 → role None(비멤버 취급).
        컬럼부재 외 예외는 상위(_read_runtime_pg)로 전파 → None → resolver 가 fail-closed DENY.
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    _PG_LOAD_MEMBER_VISIBILITY,
                    {"conversation_id": conversation_id, "account_id": account_id},
                )
                row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "sqlstate", None) == "42703":  # UndefinedColumn (pre-migration)
                return {"schema_missing": True}
            raise
        if row is None:
            return {"has_restricted": False, "role": None}
        return {
            "has_restricted": bool(row[0]),
            "role": row[1],
            "floor_ca": row[2],
            "ceil_ca": row[3],
            "joined_ca": row[4],
        }

    def list_conversations(self, conn: Any, *, limit: int = 50) -> list:
        """(conversation_id, topic, created_at_isoformat) 튜플 리스트 반환."""
        with conn.cursor() as cur:
            cur.execute(_PG_LIST_CONVERSATIONS, {"limit": limit})
            raw = cur.fetchall() or []
        return [
            (row[0], row[1], row[2].isoformat() if hasattr(row[2], "isoformat") else row[2])
            for row in raw
        ]

    def get_conv_messages_full(self, conn: Any, *, conversation_id: str, limit: int = 1000) -> list:
        """(id, role, content, tool_calls, tool_call_id, name, created_at) 튜플 리스트 반환."""
        with conn.cursor() as cur:
            cur.execute(_PG_GET_CONV_MESSAGES_FULL, {"conversation_id": conversation_id, "limit": limit})
            return cur.fetchall() or []


# Module-level singleton (thread-safe lazy init, kb_backend.py 패턴 답습).
# ─────────────────────────────────────────────────────────────────────────────

_pg_backend_instance: Optional[PgRuntimeBackend] = None
_pg_backend_lock: threading.Lock = threading.Lock()


def _get_pg_runtime_backend() -> PgRuntimeBackend:
    global _pg_backend_instance
    if _pg_backend_instance is None:
        with _pg_backend_lock:
            if _pg_backend_instance is None:
                _pg_backend_instance = PgRuntimeBackend()
    return _pg_backend_instance


# ─────────────────────────────────────────────────────────────────────────────
# feature-0019 message-editing — run-scoped branch chain cursor (thread-local)
#
# 브랜치 대화(has_branches=true)의 재답변 run 에서 새 메시지(user·tool 스텝·답변)의
# parent 를 **대화 단위 공유 포인터 active_leaf 를 매 write 마다 재-read** 하는 대신,
# 한 run 안에서 직전에 쓴 메시지 id 를 이 thread-local 커서로 이어붙인다. 그래야 run 이
# 겹치거나(이전 답변 생성 중 다음 재답변) active_leaf 가 다른 turn/분기점 값으로 리셋돼도
# `user → (tool…) → 답변` 체인이 자기 run 안에서 무결하게 유지된다(답변이 user 의 형제로
# 붙어 user 가 active-path 에서 사라지던 결함 봉인). 워커 스레드는 한 번에 run 하나만 처리
# 하므로 thread-local 로 충분하다. `_run_agent_core` 가 run 시작 시 begin(has_branches),
# 종료 teardown 에서 end() 를 호출해 스레드 재사용 stale 을 방지한다.
# 비분기 대화(active=False, 거의 모든 대화)는 이 경로를 타지 않고 기존 auto append 그대로(회귀 0).
# ─────────────────────────────────────────────────────────────────────────────

import threading as _threading

_branch_run_chain = _threading.local()


def branch_run_begin(active: bool) -> None:
    """run 시작: 브랜치 체인 커서 초기화. active = 이 대화 has_branches 여부."""
    _branch_run_chain.active = bool(active)
    _branch_run_chain.core = None
    _branch_run_chain.disp = None


def branch_run_end() -> None:
    """run 종료(teardown): 커서 해제 — 워커 스레드 재사용 시 stale 커서 leak 방지."""
    _branch_run_chain.active = False
    _branch_run_chain.core = None
    _branch_run_chain.disp = None


def branch_run_active() -> bool:
    return bool(getattr(_branch_run_chain, "active", False))


def branch_chain_get(store: str):
    """store in ('core','disp'). 이 run 이 해당 store 에 직전에 쓴 메시지 id(없으면 None)."""
    return getattr(_branch_run_chain, store, None)


def branch_chain_set(store: str, message_id) -> None:
    setattr(_branch_run_chain, store, message_id)


# ─────────────────────────────────────────────────────────────────────────────
# internal connection helper (kb_backend.py _get_pg_conn 패턴 답습)
# ─────────────────────────────────────────────────────────────────────────────

def _get_pg_runtime_conn():
    """매 호출마다 Postgres connection open (RW). process-level pool 은 M3+ cycle 책임."""
    from shared.db import _pg_available, _pg_connect
    if not _pg_available():
        return None
    try:
        return _pg_connect()
    except Exception as exc:
        if AGENT_RUNTIME_PG_REQUIRED:
            raise
        logger.warning("runtime_backend: pg connection failed: %s", exc)
        return None


def _get_pg_runtime_conn_ro():
    """매 호출마다 Postgres read-only connection open (agent_kb_ro role, M4).

    _pg_connect_ro() 미설정 시 _pg_connect() fallback (같은 패턴: KB M4 _pg_connect_ro).
    """
    from shared.db import _pg_available, _pg_connect_ro, _pg_connect
    if not _pg_available():
        return None
    try:
        try:
            return _pg_connect_ro()
        except Exception:
            return _pg_connect()
    except Exception as exc:
        logger.warning("runtime_backend: pg RO connection failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# M4: PG read dispatcher — memory.py / agent_core.py 가 호출.
# AGENT_RUNTIME_READ_BACKEND != "postgres" 이면 None 반환 (caller 가 MySQL fallback).
# ─────────────────────────────────────────────────────────────────────────────

def _read_runtime_pg(method_name: str, **kwargs):
    """PgRuntimeBackend read method 호출. fail-soft — exception 시 None 반환.

    caller pattern (memory.py / agent_core.py):
        if AGENT_RUNTIME_READ_BACKEND == "postgres":
            result = _read_runtime_pg("load_kv", conversation_id=cid, key=k)
            if result is not None:
                return result
        # MySQL fallback path...
    """
    if AGENT_RUNTIME_READ_BACKEND != "postgres":
        return None

    conn = _get_pg_runtime_conn_ro()
    if conn is None:
        return None

    backend = _get_pg_runtime_backend()
    method = getattr(backend, method_name, None)
    if method is None:
        logger.error("_read_runtime_pg: unknown method %s", method_name)
        try:
            conn.close()
        except Exception:
            pass
        return None

    try:
        return method(conn, **kwargs)
    except Exception as exc:
        logger.warning(
            "runtime_read_pg_fallback: method=%s error=%s",
            method_name, str(exc)[:200],
        )
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# M2-b: dual-write mirror — MySQL write 직후 PgRuntimeBackend 동일 method 호출.
# AGENT_RUNTIME_DUAL_WRITE=0 (default) 시 no-op.
# ─────────────────────────────────────────────────────────────────────────────

def _dual_write_runtime_mirror(method_name: str, **kwargs) -> None:
    """PgRuntimeBackend write mirror. AGENT_RUNTIME_DUAL_WRITE=0 이면 no-op.

    AGENT_RUNTIME_PG_REQUIRED=0 (default): 실패 시 silent log.
    AGENT_RUNTIME_PG_REQUIRED=1: 실패 시 exception propagate (fail-loud).
    """
    if not AGENT_RUNTIME_DUAL_WRITE:
        return None

    conn = None
    try:
        conn = _get_pg_runtime_conn()
    except Exception as exc:
        if AGENT_RUNTIME_PG_REQUIRED:
            raise
        logger.warning("dual_write_runtime_mirror: PG conn failed [%s]: %s", method_name, exc)
        return None

    if conn is None:
        return None

    try:
        backend = _get_pg_runtime_backend()
        method = getattr(backend, method_name)
        method(conn, **kwargs)
    except Exception as exc:
        if AGENT_RUNTIME_PG_REQUIRED:
            raise
        logger.warning("dual_write_runtime_mirror: PG call failed [%s]: %s", method_name, exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass

