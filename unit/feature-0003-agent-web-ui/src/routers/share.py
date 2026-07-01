"""feature-0012 P5b Final — share 도메인 APIRouter (완전-DI 추출).

핸들러 2종. uniform `import app`+`app.X` 동적참조(app 헬퍼 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). 경로/응답 byte-동치.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from web_context import _get_client_ip
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


@router.get("/api/public/share/{token}")
def public_share_view(token: str, request: Request) -> JSONResponse:
    """anonymous accessible share view. revoked 면 410 Gone, 미존재 면 404.

    View 카운터 증가는 revoke 체크와 동일 UPDATE 로 race-free 처리.
    노출 범위: messages (text + SQL + result 포함), owner display name, conversation topic,
    product context. file attachments 는 `conversation.file.read.*` gated 이므로 공유 view 에서 hide.
    """
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        # race-free: 활성(취소 안 됨 + 만료 안 됨) share 일 때만 ViewCount++ + LastViewedAt 갱신.
        # TASK-20260619T012028-share-link-expiry: 만료 predicate 추가 — 만료된 링크 조회는
        # ViewCount 를 부풀리지 않는다 (DB NOW() 평가).
        cur = conn.cursor()
        try:
            cur.execute(
                """
UPDATE WebConversationShares
SET ViewCount = ViewCount + 1, LastViewedAt = CURRENT_TIMESTAMP
WHERE Token = %s AND RevokedAt IS NULL
  AND (ExpiresAt IS NULL OR ExpiresAt > NOW())
                """,
                (token,),
            )
            bumped = int(cur.rowcount or 0)
        finally:
            cur.close()
        share = app._share_load_active(conn, token)
        if not share:
            return app._json_error("공유 링크를 찾을 수 없습니다.", 404)
        if share.get("RevokedAt") is not None:
            return app._json_error("이 공유 링크는 취소되었습니다.", 410)
        if bumped == 0:
            # UPDATE 가 매칭 안 됨 = 취소 아님(위에서 처리) → 만료 또는 revoke race.
            # 만료는 명시적 메시지로 구분 (DB NOW() 기준 재확인).
            if app._share_row_expired(conn, int(share.get("Id") or 0)):
                return app._json_error("이 공유 링크는 만료되었습니다.", 410)
            # race 가드: revoke 가 load 직후 끼어든 경우.
            return app._json_error("이 공유 링크는 취소되었습니다.", 410)
        conversation_id = str(share.get("ConversationId") or "")
        anchor_id = share.get("AnchorMessageId")
        anchor_id_int = int(anchor_id) if anchor_id is not None else None
        # 대화 topic + product context 조회 (cutover: core_conversations 는 PG,
        # WebProducts/WebAccounts 는 MySQL → backend-aware merge helper).
        # TASK-0176 (F1, REV-20260609-0001): 데이터 로드(PG core_conversations/messages) 실패 시
        # bare 500 대신 graceful JSON 500 으로 일관된 에러 계약을 준다 (fork 의 명시 500 래핑과 대칭).
        # 주의: 상단 ViewCount++ 는 revoke race 가드 겸용이라 그대로 두며 — 로드 실패 시 1 과대
        # 카운트는 허용 가능한 soft-metric 오차(race 정합 우선). 빈 공유뷰를 렌더하느니 명시 실패.
        try:
            conv_meta = app._conv_load_share_meta(conn, conversation_id)
            # TASK-0094 Sprint 1 Phase 8 (D9 + R-F7): share token row 의 PolicyVersion 추출 후 redact 결정.
            share_policy_version_raw = share.get("PolicyVersion")
            share_policy_version: int | None
            try:
                share_policy_version = int(share_policy_version_raw) if share_policy_version_raw is not None else None
            except Exception:
                share_policy_version = None
            messages = app._share_load_messages(
                conn,
                conversation_id,
                anchor_id_int,
                share_token_policy_version=share_policy_version,
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "public_share_view: 공유 대화 로드 실패 (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
            return app._json_error("공유 대화를 불러오지 못했습니다.", 500)
        # R-F7 audit dispatch — stale token (PolicyVersion < CURRENT) 의 자동 redact 활성 기록.
        if share_policy_version is None or int(share_policy_version or 0) < app.SHARE_POLICY_VERSION_CURRENT:
            try:
                app._audit_user_action(
                    conn,
                    request,
                    None,  # actor_type='anonymous' / 'account' 는 본 turn 의 viewer 로 결정 (아래 다시 호출)
                    action="share.policy.redact_applied",
                    resource_type="share",
                    resource_id=str(int(share.get("Id") or 0)) if share.get("Id") is not None else None,
                    request_ctx={
                        "share_id": int(share.get("Id") or 0) if share.get("Id") is not None else None,
                        "token_prefix": str(token)[:8],
                        "token_policy_version": share_policy_version,
                        "current_policy_version": app.SHARE_POLICY_VERSION_CURRENT,
                        "redact_reason": "policy_version_mismatch",
                    },
                    actor_type="anonymous",
                )
            except Exception:
                # fail-open: redact audit dispatch 실패는 공유 뷰 렌더를 막지 않으나 가시화.
                logging.getLogger(__name__).warning(
                    "public_share_view: redact audit dispatch failed", exc_info=True,
                )
        # 로그인 상태 + conversation.create 보유 시 fork 가능 flag.
        viewer = app._optional_account(request, conn)
        can_fork = bool(viewer and app._account_has_permission(viewer, "conversation.create"))
        # feature-0009: 공유 링크 참여(join) — 링크가 Joinable + 로그인 + 아직 멤버/소유자 아님일 때 가능.
        joinable = bool(int(share.get("Joinable") if share.get("Joinable") is not None else 1))
        already_member = bool(viewer) and (
            app._conversation_owned_by_account(conn, conversation_id, int(viewer["id"]))
            or app._account_is_conversation_member(conversation_id, int(viewer["id"]))
        )
        can_join = bool(viewer) and joinable and not already_member
        created_at = share.get("CreatedAt")
        last_viewed = share.get("LastViewedAt")
        share_expires_at = share.get("ExpiresAt")
        # TASK-0073 Phase A6 (Eng review E4): anonymous share view audit.
        # ActorType='anonymous' (viewer is None) 또는 'account' (logged in viewer).
        # ChangeJson 에 share_token_prefix 8 char 만 — full token X (PII 차단).
        actor_type = "anonymous" if not viewer else "account"
        app._audit_user_action(
            conn,
            request,
            viewer,
            action="share.public.view",
            resource_type="share",
            resource_id=str(int(share.get("Id") or 0)) if share.get("Id") is not None else None,
            request_ctx={
                "share_id": int(share.get("Id") or 0) if share.get("Id") is not None else None,
                "token_prefix": str(token)[:8],
                "view_count_after": int(share.get("ViewCount") or 0) + 1,
                "remote_addr": _get_client_ip(request),
            },
            actor_type=actor_type,
        )
        return JSONResponse(
            {
                "share": {
                    "token": token,
                    "scope_mode": str(share.get("ScopeMode") or "full"),
                    "anchor_message_id": anchor_id_int,
                    "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else (str(created_at) if created_at else None),
                    "view_count": int(share.get("ViewCount") or 0) + 1,
                    "last_viewed_at": last_viewed.isoformat() if hasattr(last_viewed, "isoformat") else (str(last_viewed) if last_viewed else None),
                    "expires_at": share_expires_at.isoformat() if hasattr(share_expires_at, "isoformat") else (str(share_expires_at) if share_expires_at else None),
                },
                "conversation": {
                    "topic": str(conv_meta.get("topic") or "대화"),
                    "owner_username": str(conv_meta.get("owner_username") or ""),
                    "product_key": str(conv_meta.get("product_key") or ""),
                    "product_name": str(conv_meta.get("product_name") or ""),
                    "product_mode": str(conv_meta.get("product_mode") or "pinned"),
                },
                "messages": messages,
                "viewer": {
                    "is_authenticated": bool(viewer),
                    "can_fork": can_fork,
                    "can_join": can_join,
                    "already_member": already_member,
                    "joinable": joinable,
                },
            }
        )
    finally:
        conn.close()

@router.post("/api/public/share/{token}/fork")
def public_share_fork(token: str, request: Request, account=Depends(app.require_permission("conversation.create", message="요청을 수행할 수 없습니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """공유 링크 viewer 가 로그인 상태일 때 본인 계정으로 대화 fork.

    권한: `conversation.create`. share-token 자체가 source 접근의 grant 역할이므로
    `_account_can_access_conversation` 우회 (helper 직접 호출).
    """
    share = app._share_load_active(conn, token)
    if not share:
        return app._json_error("공유 링크를 찾을 수 없습니다.", 404)
    if share.get("RevokedAt") is not None:
        return app._json_error("이 공유 링크는 취소되었습니다.", 410)
    # TASK-20260619T012028-share-link-expiry: 만료된 링크는 fork 도 차단 (DB NOW() 기준).
    if app._share_row_expired(conn, int(share.get("Id") or 0)):
        return app._json_error("이 공유 링크는 만료되었습니다.", 410)
    conversation_id = str(share.get("ConversationId") or "")
    # feature-0009 member-kick-ban: 원본 대화에서 차단(ban)된 account 는 fork 로도 콘텐츠를
    # 회수할 수 없다 — ban 의 목적("추가 접근 영구 차단")을 share-token fork 우회로부터 보호한다.
    # (적대 리뷰 BLOCKER: fork 는 멤버십/join 을 거치지 않고 콘텐츠를 복제하므로 별도 게이트 필요.)
    # 보안 게이트라 fail-closed — 차단 여부 불명(PG 오류) 시 거부(가용성보다 ban 무결성 우선).
    _fk_actor_id = int(account["id"])
    try:
        from shared.db import _pg_connect as _pg_connect_fk
        from modules import group_members as _gm_fk
        _pg_fk = _pg_connect_fk()
        try:
            _fk_banned = _gm_fk.is_banned(_pg_fk, conversation_id, _fk_actor_id)
        finally:
            _pg_fk.close()
    except Exception:
        logging.getLogger(__name__).warning(
            "public_share_fork: is_banned check failed — fail-closed", exc_info=True
        )
        _fk_banned = True
    if _fk_banned:
        app._audit_user_action(
            conn,
            request,
            account,
            action="conversation.member.fork_blocked",
            resource_type="conversation",
            resource_id=str(conversation_id),
            request_ctx={"conversation_id": conversation_id, "via": "share_fork", "reason": "banned"},
        )
        return app._json_error("이 대화에서 차단되어 복제(fork)할 수 없습니다.", 403)
    anchor_id = share.get("AnchorMessageId")
    anchor_id_int = int(anchor_id) if anchor_id is not None else None
    payload, err = app._fork_conversation_impl(conn, account, conversation_id, anchor_id_int)
    if err:
        return err
    # TASK-0073 Phase A6: share fork audit (TASK-0058 fork 는 이미 logged-in 필수).
    new_cid = payload.get("conversation_id") if isinstance(payload, dict) else None
    app._audit_user_action(
        conn,
        request,
        account,
        action="share.fork",
        resource_type="conversation",
        resource_id=str(new_cid) if new_cid else None,
        request_ctx={
            "source_share_id": int(share.get("Id") or 0) if share.get("Id") is not None else None,
            "source_token_prefix": str(token)[:8],
            "new_conversation_id": str(new_cid) if new_cid else None,
            # REV-20260609-0004 #5: 교차계정 fork 가 원본 첨부/문맥을 forker 계정으로
            # 복제하는 보안민감 이벤트의 forensics — 건수만 기록(파일명/바이트 비노출, D12).
            "attachments_copied": int(payload.get("attachments_copied") or 0) if isinstance(payload, dict) else 0,
            "core_messages_copied": int(payload.get("core_copied") or 0) if isinstance(payload, dict) else 0,
        },
    )
    return JSONResponse(payload)
