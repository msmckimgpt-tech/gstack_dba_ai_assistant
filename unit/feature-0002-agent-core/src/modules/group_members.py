"""Group conversation membership — feature-0009-group-conversation (S1 Foundations).

그룹 대화 멤버십 데이터 접근 계층. 정본은 PostgreSQL `agent_runtime.conversation_members`
(스키마: feature-0002 `scripts/agent_runtime_schema.sql`). core_conversations.owner_account_id
는 backward-compat 로 유지하되, 멤버십이 "열람" 권한의 정본이 된다("열람 ≠ 발화",
FUNCTION.md §2 REQ-GC-R7).

설계 원칙 (runtime_backend.py / memory.py 패턴 답습):
- 본 모듈 함수는 호출자가 넘긴 psycopg connection(`pg_conn`)으로만 동작한다(순수 DB 접근,
  연결 수명은 호출자 관리). 호출자는 `from shared.db import _pg_connect` 로 연결을 얻는다.
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

# feature-0009 gc-unread-baseline: 신규 가입 멤버의 last_read_message_id 를 가입 시점
# 대화 MAX(core_messages.id) 로 초기화한다 — 가입 *이전* 메세지는 unread 로 세지 않는다
# ("읽지 않은 신규 메세지만" 표시). 메세지 없는 대화면 MAX=NULL → 첫 메세지부터 unread.
# ON CONFLICT DO UPDATE 는 role 만 갱신 — 기존 멤버 재참여 시 이미 전진한 커서를 보존한다
# (last_read 를 덮어쓰지 않음). 기존 데이터 일괄 보정은 alembic 0020 backfill.
#
# ⚠ gc-join-ambiguous-param-fix: 서브쿼리의 conversation_id 비교는 **별도 파라미터 이름**
# (conversation_id_lookup)을 쓴다. INSERT VALUES 의 conversation_id 컬럼은 대상 타입
# (varchar)으로 추론되지만, 서브쿼리 `WHERE conversation_id = %s` 의 `=` 비교는 text
# 연산자를 거쳐 text 로 추론된다. 동일 named param 을 쓰면 psycopg3 가 둘을 같은 $1 로
# 합쳐 보내 "AmbiguousParameter: text versus character varying" 로 INSERT 전체가 실패
# (gc-unread-baseline 이 서브쿼리를 추가하며 발생한 회귀 — 공유 대화 join 불가 원인).
# 파라미터를 분리하면 각 위치가 독립적으로 타입 추론되어 충돌이 사라진다.
_PG_ADD_MEMBER = """
INSERT INTO agent_runtime.conversation_members
    (conversation_id, account_id, role, invited_by_account_id, last_read_message_id)
VALUES
    (%(conversation_id)s, %(account_id)s, %(role)s, %(invited_by_account_id)s,
     (SELECT MAX(id) FROM agent_runtime.core_messages WHERE conversation_id = %(conversation_id_lookup)s))
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

# ── feature-0009 gc-unread-badge: 멤버별 안 읽은 메세지 커서(last_read_message_id) ──
# 읽음 처리는 커서를 전진(GREATEST)만 한다 — 폴링/재진입으로 더 작은 message_id 가 와도
# 되돌리지 않는다(이미 읽은 메세지를 다시 unread 로 만들지 않음).
_PG_GET_LAST_READ = """
SELECT last_read_message_id
FROM agent_runtime.conversation_members
WHERE conversation_id = %(conversation_id)s AND account_id = %(account_id)s
LIMIT 1
"""

_PG_SET_LAST_READ = """
UPDATE agent_runtime.conversation_members
SET last_read_message_id = GREATEST(COALESCE(last_read_message_id, 0), %(message_id)s)
WHERE conversation_id = %(conversation_id)s AND account_id = %(account_id)s
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
                # gc-join-ambiguous-param-fix: 서브쿼리 비교용 별도 키(같은 값, 다른 $N).
                "conversation_id_lookup": conversation_id,
                "account_id": int(account_id),
                "role": role,
                "invited_by_account_id": (
                    int(invited_by_account_id) if invited_by_account_id is not None else None
                ),
            },
        )
    pg_conn.commit()


# ── share-visibility-window: 멤버별 가시 경계 window (floor/ceiling) ──────────
# 공유 링크의 [FloorMessageId, AnchorMessageId] window 를 join 시 멤버 행에 각인한다.
# DISPLAY id-space(visible_*_message_id) + core bridge 스냅샷(visible_*_created_at).
_PG_GET_MEMBER_VISIBILITY = """
SELECT role, visible_floor_message_id, visible_ceiling_message_id,
       visible_floor_created_at, visible_ceiling_created_at
FROM agent_runtime.conversation_members
WHERE conversation_id = %(conversation_id)s AND account_id = %(account_id)s
LIMIT 1
"""

_PG_SET_MEMBER_VISIBILITY = """
UPDATE agent_runtime.conversation_members
SET visible_floor_message_id    = %(floor_id)s,
    visible_ceiling_message_id  = %(ceiling_id)s,
    visible_floor_created_at    = %(floor_ca)s,
    visible_ceiling_created_at  = %(ceiling_ca)s
WHERE conversation_id = %(conversation_id)s AND account_id = %(account_id)s
"""

_PG_MARK_RESTRICTED = """
UPDATE agent_runtime.core_conversations
SET has_restricted_members = true
WHERE conversation_id = %(conversation_id)s
"""


def get_member_visibility(pg_conn, conversation_id: str, account_id: int) -> Optional[dict[str, Any]]:
    """멤버의 가시 경계 조회. 비멤버면 None.

    반환 dict: {role, floor_id, ceiling_id, floor_created_at, ceiling_created_at}
    (floor/ceiling 은 NULL 가능 = 그 방향 무제한). share-visibility-window 의 create-endpoint
    widen-guard(본인 window 밖 재공유 차단)와 recall/display 필터가 소비.
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_GET_MEMBER_VISIBILITY,
            {"conversation_id": conversation_id, "account_id": int(account_id)},
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "role": row[0],
        "floor_id": row[1],
        "ceiling_id": row[2],
        "floor_created_at": row[3],
        "ceiling_created_at": row[4],
    }


def stamp_member_visibility(
    pg_conn,
    conversation_id: str,
    account_id: int,
    *,
    is_new_member: bool,
    floor_id: Optional[int],
    ceiling_id: Optional[int],
    floor_created_at=None,
    ceiling_created_at=None,
) -> None:
    """share window([floor_id, ceiling_id])를 멤버 가시경계에 각인 (never-widen, fail-closed 정합).

    규칙 (권한상승·의도치 않은 강등 동시 차단):
      - role='owner'                : 각인 안 함(소유자는 본인 콘텐츠 전체 접근 정당).
      - is_new_member=True          : share window 를 **그대로** 각인(신규 참여자는 딱 그만큼 열람).
      - 기존 full 멤버(floor·ceiling 모두 NULL) : 각인 안 함(이미 정당한 전체 접근 — 좁히지 않음).
      - 기존 windowed 멤버            : **교집합**(floor=더 높은 id, ceiling=더 낮은 id) — 절대 넓히지 않음.
    각인 결과가 windowed(floor 또는 ceiling 존재)면 core_conversations.has_restricted_members=true 로
    게이트를 켠다(loader 가 이 대화에서 actor window 를 해석하도록).

    created_at 스냅샷은 id 승자를 따라간다(id 순서 == created_at 순서). 교집합에서 기존 값이 이기면
    기존 스냅샷 보존, share 값이 이기면 share 스냅샷 사용.
    """
    existing = get_member_visibility(pg_conn, conversation_id, account_id)
    if existing is None:
        return  # 멤버가 아님 — 각인 대상 없음(호출자가 add_member 선행).
    if existing["role"] == "owner":
        return

    if is_new_member:
        new_floor_id, new_floor_ca = floor_id, floor_created_at
        new_ceiling_id, new_ceiling_ca = ceiling_id, ceiling_created_at
    else:
        ex_floor, ex_ceiling = existing["floor_id"], existing["ceiling_id"]
        if ex_floor is None and ex_ceiling is None:
            return  # 기존 full 멤버 — 좁히지 않음(least-restrictive for pre-existing full access).
        # 교집합: floor = 더 제약적인(더 높은 id), ceiling = 더 제약적인(더 낮은 id). 절대 넓히지 않음.
        if floor_id is None:
            new_floor_id, new_floor_ca = ex_floor, existing["floor_created_at"]
        elif ex_floor is None or int(floor_id) >= int(ex_floor):
            new_floor_id, new_floor_ca = floor_id, floor_created_at
        else:
            new_floor_id, new_floor_ca = ex_floor, existing["floor_created_at"]
        if ceiling_id is None:
            new_ceiling_id, new_ceiling_ca = ex_ceiling, existing["ceiling_created_at"]
        elif ex_ceiling is None or int(ceiling_id) <= int(ex_ceiling):
            new_ceiling_id, new_ceiling_ca = ceiling_id, ceiling_created_at
        else:
            new_ceiling_id, new_ceiling_ca = ex_ceiling, existing["ceiling_created_at"]

    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_SET_MEMBER_VISIBILITY,
            {
                "conversation_id": conversation_id,
                "account_id": int(account_id),
                "floor_id": int(new_floor_id) if new_floor_id is not None else None,
                "ceiling_id": int(new_ceiling_id) if new_ceiling_id is not None else None,
                "floor_ca": new_floor_ca,
                "ceiling_ca": new_ceiling_ca,
            },
        )
        if new_floor_id is not None or new_ceiling_id is not None:
            cur.execute(_PG_MARK_RESTRICTED, {"conversation_id": conversation_id})
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


# ─────────────────────────────────────────────────────────────────────────────
# feature-0009 gc-unread-badge: 안 읽은 메세지 커서(last_read_message_id) 읽기/전진.
# 사이드바 unread 배지의 멤버별 읽음 기준점. 읽음 API(POST /api/conversations/{cid}/read)가
# set_last_read 로 커서를 전진시키고, _list_conversations 가 이 커서 이후 메세지를 unread 로 센다.
# ─────────────────────────────────────────────────────────────────────────────

def get_last_read(pg_conn, conversation_id: str, account_id: int) -> Optional[int]:
    """멤버의 마지막 읽은 메세지 id. 멤버 아니거나 한 번도 안 읽었으면 None."""
    if not conversation_id or not account_id:
        return None
    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_GET_LAST_READ,
            {"conversation_id": conversation_id, "account_id": int(account_id)},
        )
        row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def set_last_read(pg_conn, conversation_id: str, account_id: int, message_id: int) -> int:
    """멤버의 읽음 커서를 message_id 로 전진(GREATEST). 멤버 행이 있을 때만 갱신.

    되돌림 없음 — 더 작은 message_id 가 와도 기존 커서를 유지한다(폴링/재진입 경합 안전).
    Returns: 갱신된 행 수(0 = 멤버 아님 → 호출자가 멤버십 게이트를 선행해야 함).
    """
    if not conversation_id or not account_id or message_id is None:
        return 0
    with pg_conn.cursor() as cur:
        cur.execute(
            _PG_SET_LAST_READ,
            {
                "conversation_id": conversation_id,
                "account_id": int(account_id),
                "message_id": int(message_id),
            },
        )
        updated = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    pg_conn.commit()
    return updated
