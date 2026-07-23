"""feature-0024-conversation-folders — 대화 폴더 PG 스토어 (agent_runtime).

대화 정본이 PG(agent_kb.agent_runtime)이므로 폴더 write/read 는 모두 `_pg_connect()` 를 쓴다
(MySQL conn 사용 금지 — DECISIONS AR-M1~M5). 두 테이블:
  - conversation_folders       : 계정 소유 재귀 폴더(self-FK parent_folder_id·archived_at soft-delete).
  - folder_conversation_map    : **계정별** 대화↔폴더 배정 PK(account_id, conversation_id).

재귀 깊이는 런타임 설정 folder_max_depth 로 create/move 시점에만 강제(grandfathering — 기존
깊이 보존, 더 깊어지는 조작만 차단). 순환은 하향 서브트리 CTE 로 방지.

폴더 삭제 = soft-delete 서브트리(archived_at) + undo(restore). archived 폴더의 대화는 트리에서
빠져 root 로 표시되고, 대화 자체는 core_conversations 에 그대로 보존된다(REQ-folder-delete-keep).

RBAC/접근 게이트(폴더 소유·대화 접근)는 라우터(folders.py)가 수행하고, 본 스토어는 순수 데이터.
"""
from __future__ import annotations

from typing import Any

from shared import runtime_settings

# 무변경 vs 명시적 NULL("지우기") 을 구분하는 sentinel.
_KEEP = "__keep__"


class FolderError(Exception):
    def __init__(self, message: str, code: int = 422):
        super().__init__(message)
        self.message = message
        self.code = code


def _pg():
    from shared.db import _pg_connect
    return _pg_connect()


def _to_int(v: Any) -> int | None:
    return int(v) if v is not None else None


# ── 조회 ────────────────────────────────────────────────────────────────

def list_folders(owner_account_id: int, *, all_owners: bool = False) -> list[dict[str, Any]]:
    """활성(archived_at IS NULL) 폴더 + 계산된 절대 depth 를 반환(트리 조립은 호출측).

    all_owners=True(folder.list.any 운영자)면 전 계정 폴더. 아니면 owner 스코프.
    depth: 루트=1, 자식=부모+1. archived 폴더는 제외되며, archived 부모의 서브트리도
    체인이 끊겨 함께 제외된다(soft-delete 서브트리와 정합).
    """
    pg = _pg()
    try:
        with pg.cursor() as cur:
            if all_owners:
                root_pred = "parent_folder_id IS NULL AND archived_at IS NULL"
                params: list[Any] = []
            else:
                root_pred = "parent_folder_id IS NULL AND archived_at IS NULL AND owner_account_id = %s"
                params = [int(owner_account_id)]
            cur.execute(
                f"""
WITH RECURSIVE tree AS (
    SELECT folder_id, parent_folder_id, owner_account_id, name, instructions,
           datasource_id, product_id, sort_order, 1 AS depth
    FROM agent_runtime.conversation_folders
    WHERE {root_pred}
    UNION ALL
    SELECT f.folder_id, f.parent_folder_id, f.owner_account_id, f.name, f.instructions,
           f.datasource_id, f.product_id, f.sort_order, t.depth + 1
    FROM agent_runtime.conversation_folders f
    JOIN tree t ON f.parent_folder_id = t.folder_id
    WHERE f.archived_at IS NULL
)
SELECT folder_id, parent_folder_id, owner_account_id, name, instructions,
       datasource_id, product_id, sort_order, depth
FROM tree
ORDER BY depth, sort_order, name
""",
                params,
            )
            rows = cur.fetchall()
    finally:
        pg.close()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "folder_id": int(r[0]),
            "parent_folder_id": _to_int(r[1]),
            "owner_account_id": _to_int(r[2]),
            "name": r[3],
            "instructions": r[4],
            "datasource_id": _to_int(r[5]),
            "product_id": _to_int(r[6]),
            "sort_order": int(r[7] or 0),
            "depth": int(r[8]),
        })
    return out


def get_folder(folder_id: int) -> dict[str, Any] | None:
    pg = _pg()
    try:
        with pg.cursor() as cur:
            cur.execute(
                "SELECT folder_id, owner_account_id, parent_folder_id, name, instructions, "
                "datasource_id, product_id, archived_at "
                "FROM agent_runtime.conversation_folders WHERE folder_id = %s",
                (int(folder_id),),
            )
            r = cur.fetchone()
    finally:
        pg.close()
    if not r:
        return None
    return {
        "folder_id": int(r[0]),
        "owner_account_id": _to_int(r[1]),
        "parent_folder_id": _to_int(r[2]),
        "name": r[3],
        "instructions": r[4],
        "datasource_id": _to_int(r[5]),
        "product_id": _to_int(r[6]),
        "archived_at": r[7],
    }


def _folder_depth(cur, folder_id: int) -> int:
    """폴더의 절대 depth(루트=1) — 조상 체인을 위로 세는 재귀 CTE."""
    cur.execute(
        """
WITH RECURSIVE up AS (
    SELECT folder_id, parent_folder_id, 1 AS d
    FROM agent_runtime.conversation_folders WHERE folder_id = %s
    UNION ALL
    SELECT f.folder_id, f.parent_folder_id, u.d + 1
    FROM agent_runtime.conversation_folders f
    JOIN up u ON f.folder_id = u.parent_folder_id
)
SELECT max(d) FROM up
""",
        (int(folder_id),),
    )
    row = cur.fetchone()
    return int(row[0] or 1)


def _subtree_abs_max_depth(cur, folder_id: int, start_abs_depth: int) -> int:
    """folder_id 와 그 활성 후손 중 절대 depth 최댓값(하향 재귀). start_abs_depth = folder_id 의 현재 절대 depth."""
    cur.execute(
        """
WITH RECURSIVE t AS (
    SELECT folder_id, %s::int AS abs_depth
    FROM agent_runtime.conversation_folders WHERE folder_id = %s
    UNION ALL
    SELECT f.folder_id, t.abs_depth + 1
    FROM agent_runtime.conversation_folders f
    JOIN t ON f.parent_folder_id = t.folder_id
    WHERE f.archived_at IS NULL
)
SELECT max(abs_depth) FROM t
""",
        (int(start_abs_depth), int(folder_id)),
    )
    row = cur.fetchone()
    return int(row[0] or start_abs_depth)


def _descendant_ids(cur, folder_id: int) -> set[int]:
    """folder_id 포함 모든 후손 id(순환 방지·서브트리 삭제용)."""
    cur.execute(
        """
WITH RECURSIVE down AS (
    SELECT folder_id FROM agent_runtime.conversation_folders WHERE folder_id = %s
    UNION ALL
    SELECT f.folder_id FROM agent_runtime.conversation_folders f
    JOIN down d ON f.parent_folder_id = d.folder_id
)
SELECT folder_id FROM down
""",
        (int(folder_id),),
    )
    return {int(x[0]) for x in cur.fetchall()}


# ── 쓰기 ────────────────────────────────────────────────────────────────

def create_folder(owner_account_id: int, name: str, *, parent_folder_id: int | None = None,
                  instructions: str | None = None, datasource_id: int | None = None,
                  product_id: int | None = None) -> dict[str, Any]:
    max_depth = runtime_settings.folder_max_depth()
    pg = _pg()
    try:
        with pg.cursor() as cur:
            new_depth = 1
            if parent_folder_id is not None:
                cur.execute(
                    "SELECT owner_account_id FROM agent_runtime.conversation_folders "
                    "WHERE folder_id = %s AND archived_at IS NULL",
                    (int(parent_folder_id),),
                )
                pr = cur.fetchone()
                if not pr:
                    raise FolderError("상위 폴더를 찾을 수 없습니다.", 404)
                if int(pr[0] or 0) != int(owner_account_id):
                    raise FolderError("상위 폴더에 대한 권한이 없습니다.", 403)
                new_depth = _folder_depth(cur, int(parent_folder_id)) + 1
                if new_depth > max_depth:
                    raise FolderError(f"폴더 최대 중첩 깊이({max_depth}단)를 초과합니다.", 422)
            cur.execute(
                """
INSERT INTO agent_runtime.conversation_folders
    (owner_account_id, parent_folder_id, name, instructions, datasource_id, product_id)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING folder_id
""",
                (int(owner_account_id), _to_int(parent_folder_id), name, instructions,
                 _to_int(datasource_id), _to_int(product_id)),
            )
            fid = int(cur.fetchone()[0])
        pg.commit()
    finally:
        pg.close()
    return {"folder_id": fid, "name": name, "parent_folder_id": parent_folder_id, "depth": new_depth}


def update_folder(folder_id: int, owner_account_id: int, *, name: str | None = None,
                  instructions: Any = _KEEP, datasource_id: Any = _KEEP,
                  product_id: Any = _KEEP, parent_folder_id: Any = _KEEP) -> None:
    """이름/지침/스코프/부모(이동) 갱신. 이동은 depth(grandfathering)+순환 검증.

    instructions/datasource_id/product_id/parent_folder_id 는 _KEEP=무변경. None=지우기(부모는 root 이동).
    """
    max_depth = runtime_settings.folder_max_depth()
    pg = _pg()
    try:
        with pg.cursor() as cur:
            cur.execute(
                "SELECT owner_account_id FROM agent_runtime.conversation_folders "
                "WHERE folder_id = %s AND archived_at IS NULL",
                (int(folder_id),),
            )
            r = cur.fetchone()
            if not r:
                raise FolderError("폴더를 찾을 수 없습니다.", 404)

            sets: list[str] = []
            params: list[Any] = []
            if name is not None:
                sets.append("name = %s"); params.append(name)
            if instructions is not _KEEP:
                sets.append("instructions = %s"); params.append(instructions)
            if datasource_id is not _KEEP:
                sets.append("datasource_id = %s"); params.append(_to_int(datasource_id))
            if product_id is not _KEEP:
                sets.append("product_id = %s"); params.append(_to_int(product_id))

            if parent_folder_id is not _KEEP:
                new_parent = None if parent_folder_id is None else int(parent_folder_id)
                if new_parent is not None:
                    if new_parent == int(folder_id):
                        raise FolderError("폴더를 자기 자신의 하위로 옮길 수 없습니다.", 422)
                    cur.execute(
                        "SELECT owner_account_id FROM agent_runtime.conversation_folders "
                        "WHERE folder_id = %s AND archived_at IS NULL",
                        (new_parent,),
                    )
                    pr = cur.fetchone()
                    if not pr:
                        raise FolderError("이동 대상 상위 폴더를 찾을 수 없습니다.", 404)
                    if int(pr[0] or 0) != int(owner_account_id):
                        raise FolderError("이동 대상 폴더에 대한 권한이 없습니다.", 403)
                    if new_parent in _descendant_ids(cur, int(folder_id)):
                        raise FolderError("폴더를 자신의 하위 폴더로 옮길 수 없습니다(순환).", 422)
                    # grandfathering: 더 깊어지는 이동만 상한 검사(같음/얕아짐은 항상 허용)
                    old_depth = _folder_depth(cur, int(folder_id))
                    new_depth = _folder_depth(cur, new_parent) + 1
                    if new_depth > old_depth:
                        subtree_abs_max = _subtree_abs_max_depth(cur, int(folder_id), old_depth)
                        if subtree_abs_max + (new_depth - old_depth) > max_depth:
                            raise FolderError(f"이동 시 폴더 최대 중첩 깊이({max_depth}단)를 초과합니다.", 422)
                sets.append("parent_folder_id = %s"); params.append(new_parent)

            if not sets:
                return
            sets.append("updated_at = now()")
            params.append(int(folder_id))
            cur.execute(
                f"UPDATE agent_runtime.conversation_folders SET {', '.join(sets)} WHERE folder_id = %s",
                params,
            )
        pg.commit()
    finally:
        pg.close()


def soft_delete_folder(folder_id: int) -> list[int]:
    """폴더 + 활성 후손을 soft-delete(archived_at). 대화는 core_conversations 에 보존.
    반환 = 이번에 archive 된 folder_id 목록(undo 대상). undo=restore_folders."""
    pg = _pg()
    try:
        with pg.cursor() as cur:
            sub = _descendant_ids(cur, int(folder_id))
            if not sub:
                return []
            ids = tuple(sub)
            cur.execute(
                "UPDATE agent_runtime.conversation_folders SET archived_at = now(), updated_at = now() "
                "WHERE folder_id = ANY(%s) AND archived_at IS NULL RETURNING folder_id",
                (list(ids),),
            )
            archived = [int(x[0]) for x in cur.fetchall()]
        pg.commit()
    finally:
        pg.close()
    return archived


def restore_folders(folder_ids: list[int], owner_account_id: int | None = None) -> None:
    """undo — 방금 삭제된 서브트리를 복구. ★ owner_account_id 지정 시 SQL 에서 소유 스코프 강제
    (restore IDOR 차단 — body 의 folder_ids 를 무검증 복구하면 타 계정 archived 폴더를 열거·부활
    시킬 수 있으므로 반드시 owner 필터. manage.any 운영자만 None 으로 전역 복구)."""
    if not folder_ids:
        return
    ids = [int(x) for x in folder_ids]
    pg = _pg()
    try:
        with pg.cursor() as cur:
            if owner_account_id is None:
                cur.execute(
                    "UPDATE agent_runtime.conversation_folders SET archived_at = NULL, updated_at = now() "
                    "WHERE folder_id = ANY(%s)",
                    (ids,),
                )
            else:
                cur.execute(
                    "UPDATE agent_runtime.conversation_folders SET archived_at = NULL, updated_at = now() "
                    "WHERE folder_id = ANY(%s) AND owner_account_id = %s",
                    (ids, int(owner_account_id)),
                )
        pg.commit()
    finally:
        pg.close()


# ── 계정별 대화 배정 ──────────────────────────────────────────────────────

def assign_conversation(account_id: int, conversation_id: str, folder_id: int | None) -> None:
    """요청 계정의 대화↔폴더 배정 upsert(folder_id=None → 배정 해제=root)."""
    pg = _pg()
    try:
        with pg.cursor() as cur:
            if folder_id is None:
                cur.execute(
                    "DELETE FROM agent_runtime.folder_conversation_map "
                    "WHERE account_id = %s AND conversation_id = %s",
                    (int(account_id), conversation_id),
                )
            else:
                cur.execute(
                    """
INSERT INTO agent_runtime.folder_conversation_map (account_id, conversation_id, folder_id)
VALUES (%s, %s, %s)
ON CONFLICT (account_id, conversation_id)
DO UPDATE SET folder_id = EXCLUDED.folder_id, assigned_at = now()
""",
                    (int(account_id), conversation_id, int(folder_id)),
                )
        pg.commit()
    finally:
        pg.close()


def folder_id_for(account_id: int, conversation_id: str) -> int | None:
    """요청 계정이 그 대화를 배정한 활성 폴더. archived/미배정이면 None(=root)."""
    pg = _pg()
    try:
        with pg.cursor() as cur:
            cur.execute(
                """
SELECT m.folder_id FROM agent_runtime.folder_conversation_map m
JOIN agent_runtime.conversation_folders f ON f.folder_id = m.folder_id AND f.archived_at IS NULL
WHERE m.account_id = %s AND m.conversation_id = %s
""",
                (int(account_id), conversation_id),
            )
            r = cur.fetchone()
    finally:
        pg.close()
    return int(r[0]) if r else None


def folder_map_for_account(account_id: int) -> dict[str, int]:
    """요청 계정의 {conversation_id: folder_id}(활성 폴더만) — 목록 payload 배치 보강용."""
    pg = _pg()
    try:
        with pg.cursor() as cur:
            cur.execute(
                """
SELECT m.conversation_id, m.folder_id FROM agent_runtime.folder_conversation_map m
JOIN agent_runtime.conversation_folders f ON f.folder_id = m.folder_id AND f.archived_at IS NULL
WHERE m.account_id = %s
""",
                (int(account_id),),
            )
            rows = cur.fetchall()
    finally:
        pg.close()
    return {str(r[0]): int(r[1]) for r in rows}
