"""Group conversation membership — feature-0009-group-conversation (S1 Foundations).

그룹 대화 멤버십 데이터 접근 계층. 정본은 PostgreSQL `agent_runtime.conversation_members`
(스키마: feature-0002 `scripts/agent_runtime_schema.sql`). core_conversations.owner_account_id
는 backward-compat 로 유지하되, 멤버십이 "열람" 권한의 정본이 된다("열람 ≠ 발화",
FUNCTION.md §2 REQ-GC-R7).

설계 원칙 (runtime_backend.py / memory.py 패턴 답습):
- 본 모듈 함수는 호출자가 넘긴 psycopg connection(`pg_conn`)으로만 동작한다(순수 DB 접근,
  연결 수명은 호출자 관리). 호출자는 `from modules.db import _pg_connect` 로 연결을 얻는다.
- 모든 SQL 은 `agent_runtime.` schema-qualified (ADR-0027, search_path 전역 변경 없음).
- INSERT 는 ON CONFLICT DO NOTHING 으로 멱등 (append-only 멤버십).

S1 범위: 멱등 backfill + 읽기 헬퍼 + add/remove(S2 엔드포인트가 사용). 멤버십 기반
열람 게이트(_account_can_access_conversation 확장)·멤버 관리 엔드포인트·audit 는 S2,
actor 발화 게이트는 S3/S4 에서 본 헬퍼를 소비한다.

⚠ backfill 호출 wiring: 본 함수는 agent_runtime 스키마(conversation_members 테이블)가
생성된 직후 1회(또는 멱등 반복) 호출되어야 한다. 호출 지점 연결은 S2 초입에서
schema-ensure 경로에 추가한다(S1 은 스키마 + 멱등 함수까지).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("agent_core.group_members")

VALID_ROLES = ("owner", "member")

# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL SQL constants (agent_runtime schema-qualified, ADR-0027)
# ─────────────────────────────────────────────────────────────────────────────

# 기존 단일소유 대화 → owner member 1행 backfill. owner_account_id 가 있는 대화만.
# ON CONFLICT DO NOTHING 으로 멱등 (이미 멤버면 건너뜀, role 덮어쓰지 않음).
_PG_BACKFILL_MEMBERS = """
INSERT INTO agent_runtime.conversation_members
    (conversation_id, account_id, role, invited_by_account_id)
SELECT
    c.conversation_id, c.owner_account_id, 'owner', c.owner_account_id
FROM agent_runtime.core_conversations AS c
WHERE c.owner_account_id IS NOT NULL
ON CONFLICT (conversation_id, account_id) DO NOTHING
"""

_PG_LIST_MEMBER_ACCOUNT_IDS = """
SELECT account_id
FROM agent_runtime.conversation_members
WHERE conversation_id = %(conversation_id)s
ORDER BY joined_at ASC, account_id ASC
"""

_PG_MEMBER_ROLE = """
SELECT role
FROM agent_runtime.conversation_members
WHERE conversation_id = %(conversation_id)s AND account_id = %(account_id)s
LIMIT 1
"""

_PG_ADD_MEMBER = """
INSERT INTO agent_runtime.conversation_members
    (conversation_id, account_id, role, invited_by_account_id)
VALUES
    (%(conversation_id)s, %(account_id)s, %(role)s, %(invited_by_account_id)s)
ON CONFLICT (conversation_id, account_id) DO UPDATE SET
    role = EXCLUDED.role
"""

_PG_REMOVE_MEMBER = """
DELETE FROM agent_runtime.conversation_members
WHERE conversation_id = %(conversation_id)s AND account_id = %(account_id)s
"""

# ── feature-0009 member-kick-ban: 차단(ban) 목록 ─────────────────────────────
# ban = 멤버 제거(remove_member) + 이 테이블 등재. 재참여(join) 시 is_banned 로 거부.
# 재차단(re-ban)은 ON CONFLICT DO UPDATE 로 banned_at/by/reason 갱신(멱등).
_PG_BAN_MEMBER = """
INSERT INTO agent_runtime.conversation_member_bans
    (conversation_id, account_id, banned_by_account_id, reason)
VALUES
    (%(conversation_id)s, %(account_id)s, %(banned_by_account_id)s, %(reason)s)
ON CONFLICT (conversation_id, account_id) DO UPDATE SET
    banned_at            = now(),
    banned_by_account_id = EXCLUDED.banned_by_account_id,
    reason               = EXCLUDED.reason
"""

_PG_UNBAN_MEMBER = """
DELETE FROM agent_runtime.conversation_member_bans
WHERE conversation_id = %(conversation_id)s AND account_id = %(account_id)s
"""

_PG_IS_BANNED = """
SELECT 1
FROM agent_runtime.conversation_member_bans
WHERE conversation_id = %(conversation_id)s AND account_id = %(account_id)s
LIMIT 1
"""

_PG_LIST_BANS = """
SELECT account_id, banned_at, banned_by_account_id, reason
FROM agent_runtime.conversation_member_bans
WHERE conversation_id = %(conversation_id)s
ORDER BY banned_at DESC, account_id ASC
"""


# ─────────────────────────────────────────────────────────────────────────────
# Data access (호출자가 pg_conn 제공)
# ─────────────────────────────────────────────────────────────────────────────

def backfill_conversation_members(pg_conn) -> int:
    """기존 단일소유 대화를 owner member 로 backfill (멱등).

    owner_account_id 가 있는 모든 core_conversations 에 대해 owner role 멤버 1행을
    INSERT 한다. 이미 멤버면 ON CONFLICT DO NOTHING 으로 건너뛴다 — 다시 호출해도 안전.

    Returns: 이번 호출에서 새로 삽입된 멤버 행 수.
    """
    with pg_conn.cursor() as cur:
        cur.execute(_PG_BACKFILL_MEMBERS)
        inserted = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
    pg_conn.commit()
    logger.info("backfill_conversation_members: inserted=%d", inserted)
    return inserted


def list_member_account_ids(pg_conn, conversation_id: str) -> list[int]:
    """대화의 멤버 account_id 목록 (joined_at 순)."""
    with pg_conn.cursor() as cur:
        cur.execute(_PG_LIST_MEMBER_ACCOUNT_IDS, {"conversation_id": conversation_id})
        rows = cur.fetchall() or []
    return [int(r[0]) for r in rows]


def account_member_role(pg_conn, conversation_id: str, account_id: int) -> Optional[str]:
    """account 의 멤버 role ('owner'|'member') 반환. 멤버 아니면 None."""
    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_MEMBER_ROLE,
            {"conversation_id": conversation_id, "account_id": int(account_id)},
        )
        row = cur.fetchone()
    return str(row[0]) if row else None


def is_member(pg_conn, conversation_id: str, account_id: int) -> bool:
    """account 가 대화의 멤버인지 여부 (열람 게이트의 기반, S2 에서 소비)."""
    return account_member_role(pg_conn, conversation_id, account_id) is not None


def add_member(
    pg_conn,
    conversation_id: str,
    account_id: int,
    role: str = "member",
    invited_by_account_id: Optional[int] = None,
) -> None:
    """멤버 추가/역할 갱신 (S2 초대 엔드포인트가 호출). role 검증 포함."""
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role!r} (allowed: {VALID_ROLES})")
    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_ADD_MEMBER,
            {
                "conversation_id": conversation_id,
                "account_id": int(account_id),
                "role": role,
                "invited_by_account_id": (
                    int(invited_by_account_id) if invited_by_account_id is not None else None
                ),
            },
        )
    pg_conn.commit()


def remove_member(pg_conn, conversation_id: str, account_id: int) -> int:
    """멤버 제거 (S2 제거/나가기 엔드포인트가 호출).

    메시지·첨부는 잔존(FUNCTION.md §8 tombstone author), 향후 접근만 차단된다.
    Returns: 삭제된 행 수(0 = 멤버 아니었음).
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_REMOVE_MEMBER,
            {"conversation_id": conversation_id, "account_id": int(account_id)},
        )
        removed = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    pg_conn.commit()
    return removed


# ─────────────────────────────────────────────────────────────────────────────
# feature-0009 member-kick-ban: 차단(ban) — owner 가 특정 account 의 재참여를 영구 차단.
# 추방(kick)=remove_member(재참여 가능). 차단(ban)=ban_member(+ remove_member, 엔드포인트에서).
# ─────────────────────────────────────────────────────────────────────────────

def ban_member(
    pg_conn,
    conversation_id: str,
    account_id: int,
    banned_by_account_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> None:
    """account 를 이 대화에서 차단(ban) — 공유 링크 재참여를 거부 목록에 등재.

    멤버십 제거(remove_member)는 호출자(엔드포인트)가 별도 수행한다 — 본 함수는 ban 목록만
    담당(단일 책임). 재차단은 ON CONFLICT 로 banned_at/by/reason 갱신(멱등).
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_BAN_MEMBER,
            {
                "conversation_id": conversation_id,
                "account_id": int(account_id),
                "banned_by_account_id": (
                    int(banned_by_account_id) if banned_by_account_id is not None else None
                ),
                "reason": (str(reason)[:512] if reason else None),
            },
        )
    pg_conn.commit()


def unban_member(pg_conn, conversation_id: str, account_id: int) -> int:
    """차단 해제 — ban 목록에서 제거. Returns: 삭제된 행 수(0 = 차단 아니었음)."""
    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_UNBAN_MEMBER,
            {"conversation_id": conversation_id, "account_id": int(account_id)},
        )
        removed = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    pg_conn.commit()
    return removed


def is_banned(pg_conn, conversation_id: str, account_id: int) -> bool:
    """account 가 이 대화에서 차단되었는지 여부 (join 거부 게이트가 소비)."""
    if not conversation_id or not account_id:
        return False
    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_IS_BANNED,
            {"conversation_id": conversation_id, "account_id": int(account_id)},
        )
        row = cur.fetchone()
    return row is not None


def list_bans(pg_conn, conversation_id: str) -> list[dict[str, Any]]:
    """대화의 차단 목록 (banned_at 최신순). '차단된 사용자' UI 가 소비."""
    with pg_conn.cursor() as cur:
        cur.execute(_PG_LIST_BANS, {"conversation_id": conversation_id})
        rows = cur.fetchall() or []
    return [
        {
            "account_id": int(r[0]),
            "banned_at": r[1].isoformat() if r[1] is not None else None,
            "banned_by_account_id": (int(r[2]) if r[2] is not None else None),
            "reason": (str(r[3]) if r[3] is not None else None),
        }
        for r in rows
    ]
