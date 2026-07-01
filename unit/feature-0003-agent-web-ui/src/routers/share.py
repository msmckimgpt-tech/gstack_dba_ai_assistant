"""feature-0012 P5b Final — share 도메인 APIRouter (완전-DI 추출).

핸들러 2종. uniform `import app`+`app.X` 동적참조(app 헬퍼 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). 경로/응답 byte-동치.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

router = APIRouter()


@router.delete("/api/share/{share_id}")
def revoke_share(share_id: int, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """공유 링크 revoke. CreatedBy 본인 또는 admin (`conversation.read.any` 가진 자) 만 가능."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT Id, ConversationId, CreatedBy, RevokedAt FROM WebConversationShares WHERE Id = %s LIMIT 1",
            (int(share_id),),
        )
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        return app._json_error("공유 링크를 찾을 수 없습니다.", 404)
    if row.get("RevokedAt") is not None:
        return JSONResponse({"id": int(row.get("Id")), "already_revoked": True})
    is_creator = int(row.get("CreatedBy") or 0) == int(account["id"])
    is_admin = app._account_has_permission(account, "conversation.read.any")
    if not (is_creator or is_admin):
        return app._json_error("요청을 수행할 수 없습니다.", 403)
    cur = conn.cursor()
    try:
        cur.execute(
            """
UPDATE WebConversationShares
SET RevokedAt = CURRENT_TIMESTAMP, RevokedBy = %s
WHERE Id = %s AND RevokedAt IS NULL
            """,
            (int(account["id"]), int(share_id)),
        )
        updated = int(cur.rowcount or 0)
    finally:
        cur.close()
    # TASK-0073 Phase A6: user endpoint best-effort audit.
    app._audit_user_action(
        conn,
        request,
        account,
        action="conversation.share.revoke",
        resource_type="share",
        resource_id=str(share_id),
        request_ctx={
            "conversation_id": str(row.get("ConversationId") or ""),
            "share_id": int(share_id),
            "already_revoked": updated == 0,
        },
    )
    return JSONResponse({"id": int(share_id), "revoked": updated > 0})


@router.post("/api/share/{token}/join")
def join_conversation_via_share(token: str, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """feature-0009: 공유 링크로 그룹 대화에 **참여(join)** — 로그인 viewer 를 멤버로 추가.

    조건(전부 충족): 로그인 + 링크 활성(revoked/expired 아님) + Joinable=1 + 대화 비차단/비보관.
    참여 시 발신자(actor)는 대화 전체(권한 멤버가 만든 datasource 결과 포함)를 열람하게 된다
    (열람 ≠ 발화, AR-1). datasource 발화/쿼리는 여전히 본인 RBAC 게이트(S4). audit: conversation.member.join.
    """
    share = app._share_load_active(conn, token)
    if not share:
        return app._json_error("공유 링크를 찾을 수 없습니다.", 404)
    if share.get("RevokedAt") is not None:
        return app._json_error("이 공유 링크는 취소되었습니다.", 410)
    if app._share_row_expired(conn, int(share.get("Id") or 0)):
        return app._json_error("이 공유 링크는 만료되었습니다.", 410)
    if not bool(int(share.get("Joinable") if share.get("Joinable") is not None else 1)):
        return app._json_error("이 공유 링크는 대화 참여가 허용되지 않습니다.", 403)
    cid = str(share.get("ConversationId") or "")
    if not cid or not app._conversation_exists(cid, conn=conn):
        return app._json_error("대화를 찾을 수 없습니다.", 404)
    _is_blocked, _block_reason = app._conversation_block_info(cid, conn=conn)
    if _is_blocked:
        return app._json_error(_block_reason or app._BLOCKED_PRODUCT_DELETED_REASON, 403)
    # feature-0009 gc-group-authz-flag: join = 그룹 협업 확정 → owner 멤버십 보장(member_count
    # under-count → 공유 직후 assistant 오호출 #2 자가치유) + is_group 플래그 set(#4). 기존
    # backfill 미적용 대화도 이 시점에 정상화. best-effort(헬퍼가 예외 무시).
    app._ensure_owner_membership(cid)
    app._mark_conversation_group(cid)
    actor_id = int(account["id"])
    # feature-0009 member-kick-ban: 차단된 account 는 공유 링크로 재참여 불가(owner ban).
    # owner 는 차단 불가(ban 엔드포인트 가드)라 owner self-join 은 영향 없음. app._ensure_owner_membership
    # 위에서 이미 owner 멤버십을 보장했고, 본 게이트는 차단된 비-owner actor 만 막는다.
    try:
        from shared.db import _pg_connect as _pg_connect_ban
        from modules import group_members as _gm_ban
        _pg_b = _pg_connect_ban()
        try:
            _is_banned = _gm_ban.is_banned(_pg_b, cid, actor_id)
        finally:
            _pg_b.close()
    except Exception:
        # 보안 게이트 fail-closed — 차단 여부 불명 시 참여 거부(가용성보다 ban 무결성 우선).
        # join 은 어차피 add_member(동일 PG)를 요구하므로 PG 장애 시 추가 가용성 손실 없음.
        logging.getLogger(__name__).warning(
            "join: is_banned check failed — fail-closed", exc_info=True
        )
        return app._json_error("참여 처리 중 오류가 발생했습니다. 다시 시도해 주세요.", 500)
    if _is_banned:
        app._audit_user_action(
            conn,
            request,
            account,
            action="conversation.member.join_blocked",
            resource_type="conversation_member",
            resource_id=str(actor_id),
            request_ctx={"conversation_id": cid, "via": "share_link", "reason": "banned"},
        )
        return app._json_error("이 대화에서 차단되어 참여할 수 없습니다.", 403)
    # 이미 소유자/멤버면 멱등 성공(중복 참여 무해).
    already = app._conversation_owned_by_account(conn, cid, actor_id) or app._account_is_conversation_member(cid, actor_id)
    if not already:
        try:
            from shared.db import _pg_connect
            from modules import group_members
            pg = _pg_connect()
            try:
                inviter = int(share.get("CreatedBy")) if share.get("CreatedBy") is not None else None
                group_members.add_member(pg, cid, actor_id, role="member", invited_by_account_id=inviter)
            finally:
                pg.close()
        except Exception:
            # 진단 가시성: 실제 예외를 로깅(상위 ban 체크와 동일 정책). silent 500 은
            # 근본원인 파악을 막는다(gc-join-ambiguous-param-fix 사례 — 멤버 INSERT 실패가
            # 일반 500 으로만 표면화되어 진단이 지연됨).
            logging.getLogger(__name__).warning(
                "join: add_member failed — conversation_id=%s actor_id=%s", cid, actor_id,
                exc_info=True,
            )
            return app._json_error("대화 참여에 실패했습니다.", 500)
        app._audit_user_action(
            conn,
            request,
            account,
            action="conversation.member.join",
            resource_type="conversation_member",
            resource_id=str(actor_id),
            request_ctx={
                "conversation_id": cid,
                "via": "share_link",
                "share_id": int(share.get("Id") or 0) if share.get("Id") is not None else None,
                "token_prefix": str(token)[:8],
            },
        )
    return JSONResponse({"ok": True, "conversation_id": cid, "already_member": already})
