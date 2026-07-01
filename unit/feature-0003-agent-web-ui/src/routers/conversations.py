"""feature-0012 P5b Final — conversations 도메인 APIRouter (대화 조작: 생성·전환·이력·삭제·취소·완료·상태).

DI 전환 완료 핸들러 10종(new_conversation RP + use_conversation·history·history_anchor·history_dates·
delete_conversation·delete_conversations·cancel_request·finalize_request·ask_status AO). 동반 테스트
직접참조 0(검증). uniform `import app`+`app.X` 동적참조(app 헬퍼 17 + DI seam) → monkeypatch·override 보존.
shared/modules import 는 본문 내 유지. 순환 안전(app 정의 후 맨 끝 include_router). 경로/응답 byte-동치.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

router = APIRouter()


@router.post("/api/new_conversation")
async def new_conversation(request: Request, account=Depends(app.require_permission("conversation.create")), conn=Depends(app.get_conn)) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        data = {}
    # TASK-0047: body 확장 — `mode='auto'|'pinned'`. 생략 시 기존 동작(pinned + default product) 보존.
    raw_mode = (data or {}).get("mode") if isinstance(data, dict) else None
    req_mode = app._normalize_product_mode(raw_mode, default="pinned")
    req_product_id: int | None = None
    raw_product = (data or {}).get("product_id")
    if raw_product is not None and str(raw_product).strip() != "":
        try:
            req_product_id = int(raw_product)
        except Exception:
            req_product_id = None
    if req_mode == "auto":
        # auto 의도면 product_id 를 hint cache 로만 두고 명시 핀은 해제.
        req_product_id = None
    elif not req_product_id:
        # pinned 인데 명시 product_id 가 없으면 기존 default 채움 동작 유지.
        req_product_id = app._get_default_product_id(conn) or None
    # TASK-0052 Phase 1C G2: pinned 모드 + 명시적 product_id 의 경우 접근 권한 검사.
    # default product 채움 분기 (req_product_id 가 default 로 채워졌을 때) 도 동일 적용 — 권한 없으면
    # auto 강등 (사용자가 default 에도 접근 못하는 케이스 방어).
    if req_mode == "pinned" and req_product_id:
        if not app._account_has_product_access(account, int(req_product_id), conn=conn):
            # explicit body 에 명시했는데 권한 없으면 403 (보안 명확성). default 가 강등된 경우는 auto.
            if (data or {}).get("product_id") not in (None, "", 0):
                return app._json_error("요청을 수행할 수 없습니다.", 403)
            # default product 권한도 없는 케이스 → auto 강등 (운영 가능성 유지).
            req_mode = "auto"
            req_product_id = None
    from agent_core import create_new_conversation as _create_conv
    cid = _create_conv(conv_file=app._account_conv_file(int(account["id"])))
    app._assign_conversation_owner(conn, cid, int(account["id"]), force=True)
    app._set_account_current_conversation(conn, int(account["id"]), cid)
    try:
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            from shared.db import _pg_connect
            _pg_nc = _pg_connect()
            with _pg_nc.cursor() as _pgcnc:
                _pgcnc.execute(
                    "UPDATE agent_runtime.core_conversations SET product_id = %s, product_mode = %s "
                    "WHERE conversation_id = %s",
                    (int(req_product_id) if req_product_id else None, req_mode, cid),
                )
            _pg_nc.close()
        else:
            cur = conn.cursor()
            cur.execute(
                "UPDATE AgentCoreConversations SET product_id = %s, product_mode = %s "
                "WHERE conversation_id = %s",
                (int(req_product_id) if req_product_id else None, req_mode, cid),
            )
            cur.close()
    except Exception:
        # fail-open: 새 대화 product 정보 기록 실패는 생성을 막지 않으나 조용한 쓰기 실패를 가시화.
        logging.getLogger(__name__).warning(
            "new_conversation: product info write failed (conversation_id=%s mode=%s)",
            cid, req_mode, exc_info=True,
        )
    # 사용자 직전 선택을 서버에 보존 (재로그인 시 hydrate 용).
    app._save_account_product_pref(
        conn, int(account["id"]), mode=req_mode, pinned_id=req_product_id
    )
    return JSONResponse({
        "conversation_id": cid,
        "output": f"새 대화: {cid}",
        "product_id": req_product_id,
        "product_mode": req_mode,
    })


@router.post("/api/use_conversation")
async def use_conversation(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    conversation_id = str(data.get("conversation_id", "")).strip()
    if not conversation_id:
        return app._json_error("empty conversation_id", 400)
    if not app._account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.read.own",
        "conversation.read.any",
    ):
        return app._json_error("conversation not found", 404)
    app._set_account_current_conversation(conn, int(account["id"]), conversation_id)
    try:
        Path(app._account_conv_file(int(account["id"]))).write_text(conversation_id, encoding="utf-8")
    except Exception:
        return app._json_error("failed to set conversation", 500)
    return JSONResponse({"conversation_id": conversation_id})


@router.get("/api/history")
def history(
    request: Request,
    conversation_id: str | None = None,
    before_id: int | None = None,
    limit: int = 10,
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    requested_id = (conversation_id or "").strip()
    if requested_id:
        conv_id = (
            requested_id
            if app._account_can_access_conversation(
                conn,
                account,
                requested_id,
                "conversation.read.own",
                "conversation.read.any",
            )
            else ""
        )
    else:
        # TASK-0048 후속 fix: /api/history 응답 조립 시 자동으로 빈 대화를 만들지 않는다 (lazy 정책).
        conv_id = app._repair_current_conversation(
            conn,
            account,
            create_if_missing=False,
        )
    if conv_id:
        messages, has_more, oldest_id, total_count, user_count = app._get_history(
            conv_id, limit=limit, before_id=before_id
        )
        # 새로고침·대화 전환 후에도 이미 부여한 👍/👎 를 복원해 중복 부여를 막는다(고유 피드백).
        # best-effort: 피드백 상태 복원 실패는 history 응답을 막지 않는다(첨부 영속과 동형 fail-soft).
        try:
            app._attach_user_feedback(
                messages,
                app._load_user_feedback_by_message(
                    conv_id, str((account or {}).get("username") or "") or None
                ),
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "history: user feedback enrich failed (conversation_id=%s)",
                conv_id, exc_info=True,
            )
    else:
        messages, has_more, oldest_id, total_count, user_count = [], False, None, 0, 0
    # 대화의 현재 처리 상태를 포함 (progress bubble 복원용)
    last_status = ""
    last_run_id = ""
    last_run_started_at = ""
    if conv_id:
        try:
            last_status = str(load_memory_kv(conn, conv_id, "last_status") or "").strip()
            if last_status == "processing":
                last_run_id = str(load_memory_kv(conn, conv_id, "last_status_run_id") or "").strip()
                # 새로고침 후 pending bubble 의 경과시간이 0 으로 초기화되지 않도록 run
                # 시작 시각(last_status_at)을 함께 반환한다. set_run_status 는 'processing'
                # 전이 시 last_status_at 을 1 회만 기록하고 terminal(done/error/canceled)
                # 시점까지 갱신하지 않으므로, processing 상태에서의 last_status_at 은 곧
                # run 시작 시각이다(클라이언트가 elapsed 기준점으로 사용).
                last_run_started_at = str(load_memory_kv(conn, conv_id, "last_status_at") or "").strip()
        except Exception:
            # best-effort: 상태 bubble 복원용 KV 조회 실패는 history 응답을 막지 않는다.
            logging.getLogger(__name__).warning(
                "history: status KV read failed (conversation_id=%s)",
                conv_id, exc_info=True,
            )
    payload = {
        "conversation_id": conv_id,
        "messages": messages,
        "last_status": last_status,
        "last_run_id": last_run_id,
        "last_run_started_at": last_run_started_at,
        "has_more": has_more,
        "next_before_id": oldest_id,
        "total_messages": total_count,
        "total_user_messages": user_count,
    }
    return JSONResponse(payload)


@router.get("/api/history_anchor")
def history_anchor(
    request: Request,
    conversation_id: str | None = None,
    at: str | None = None,
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    conv_id = app._resolve_conversation_for_account(conn, account, conversation_id or "")
    when = str(at or "").strip()
    if not conv_id or not when:
        return app._json_error("missing conversation_id or at", 400)
    # AR-M5 cutover: 메시지 정본이 MySQL AgentMemoryMessages → PG agent_runtime.messages 로
    # 이전되며 MySQL 테이블이 DROP 되었다. 캘린더 점프가 반환하는 message_id 는
    # /api/history(app._get_history) 가 DOM 에 부여한 id(`message-<id>`)와 동일 id-space 여야
    # 매칭되므로, app._get_history 와 동일하게 AGENT_RUNTIME_READ_BACKEND 로 분기한다.
    # 비교는 history_dates 의 시각 라벨과 동일한 to_char(세션 tz) wall-clock 문자열로 수행 —
    # timestamptz 직접 cast 의 tz 모호성을 피하고, 라벨과 정확히 같은 기준으로 매칭한다.
    # **분(minute) 단위** 비교(`HH24:MI` vs `left(at,16)`)인 이유: 프런트가 보내는 at 은
    # 캘린더 시각 라벨(분 정밀)에 ':00' 을 붙인 값(`YYYY-MM-DD HH:MM:00`)인데, 실제 메시지
    # created_at 의 초는 0 이 아니다. 초 단위(`HH24:MI:SS <= ...:00`)로 비교하면 클릭한 분의
    # 메시지(초>0)가 제외돼 직전 메시지로 점프하는 결함이 생긴다(원본 MySQL `CreatedAt <= when`
    # 의 잠재 결함). 분 단위로 비교하면 클릭한 분의 (마지막) 메시지에 정확히 착지한다.
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        row = None
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT id, created_at FROM agent_runtime.messages "
                        "WHERE conversation_id = %s "
                        "AND to_char(created_at, 'YYYY-MM-DD HH24:MI') <= left(%s, 16) "
                        "ORDER BY created_at DESC LIMIT 1",
                        (conv_id, when),
                    )
                    row = pgcur.fetchone()
                    if not row:
                        pgcur.execute(
                            "SELECT id, created_at FROM agent_runtime.messages "
                            "WHERE conversation_id = %s "
                            "ORDER BY created_at ASC LIMIT 1",
                            (conv_id,),
                        )
                        row = pgcur.fetchone()
            finally:
                pg.close()
        except Exception:
            return app._json_error("failed to locate anchor", 500)
        if not row:
            return app._json_error("no messages", 404)
        return JSONResponse({"message_id": int(row[0]), "created_at": str(row[1])})
    try:
        cur = conn.cursor()
        cur.execute(
            """
SELECT Id, CreatedAt
FROM AgentMemoryMessages
WHERE ConversationId = %s AND CreatedAt <= %s
ORDER BY CreatedAt DESC
LIMIT 1
            """,
            (conv_id, when),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
SELECT Id, CreatedAt
FROM AgentMemoryMessages
WHERE ConversationId = %s
ORDER BY CreatedAt ASC
LIMIT 1
                """,
                (conv_id,),
            )
            row = cur.fetchone()
        cur.close()
    except Exception:
        return app._json_error("failed to locate anchor", 500)
    if not row:
        return app._json_error("no messages", 404)
    return JSONResponse({"message_id": int(row[0]), "created_at": str(row[1])})


@router.get("/api/history_dates")
def history_dates(
    request: Request,
    conversation_id: str | None = None,
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """Return message timestamps grouped by date for calendar highlighting."""
    conv_id = app._resolve_conversation_for_account(conn, account, conversation_id or "")
    if not conv_id:
        return JSONResponse({"dates": {}, "first": None, "last": None})
    # TASK-0061 Phase 5 (REQ-20260515-0007 / AC-0088): 메시지 정본은 AgentMemoryMessages 이므로
    # 캘린더 source 를 그쪽으로 일치시킨다 (이전: AgentCoreMessages — 일부 경로에서 비어 있음).
    # AR-M5 cutover: 메시지 정본이 PG agent_runtime.messages 로 이전되고 MySQL
    # AgentMemoryMessages 테이블이 DROP 되었다. app._get_history 와 동일하게
    # AGENT_RUNTIME_READ_BACKEND 로 분기하지 않으면 삭제된 테이블을 조회해 캘린더가
    # 항상 빈 dates 를 반환(=날짜 점프 기능 누락)한다. history_anchor 와 동일한
    # to_char(세션 tz) 기준으로 날짜/시각 라벨을 만들어 점프 매칭과 일관성을 보장한다.
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT to_char(created_at, 'YYYY-MM-DD') AS d,"
                        " string_agg(to_char(created_at, 'HH24:MI'), ',' ORDER BY created_at)"
                        " FROM agent_runtime.messages"
                        " WHERE conversation_id = %s"
                        " GROUP BY to_char(created_at, 'YYYY-MM-DD')"
                        " ORDER BY d",
                        (conv_id,),
                    )
                    rows = pgcur.fetchall() or []
            finally:
                pg.close()
        except Exception:
            return JSONResponse({"dates": {}, "first": None, "last": None})
        dates_pg: dict[str, list[str]] = {}
        for row in rows:
            day_str = str(row[0])
            times = [t.strip() for t in str(row[1]).split(",") if t.strip()]
            dates_pg[day_str] = sorted(set(times))
        first = str(rows[0][0]) if rows else None
        last = str(rows[-1][0]) if rows else None
        return JSONResponse({"dates": dates_pg, "first": first, "last": last})
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DATE(CreatedAt) AS d,"
            " GROUP_CONCAT(DATE_FORMAT(CreatedAt, %s) ORDER BY CreatedAt SEPARATOR ',')"
            " FROM AgentMemoryMessages"
            " WHERE ConversationId = %s"
            " GROUP BY DATE(CreatedAt)"
            " ORDER BY d",
            ("%H:%i", conv_id),
        )
        rows = cur.fetchall() or []
        cur.close()
    except Exception:
        return JSONResponse({"dates": {}, "first": None, "last": None})
    dates: dict[str, list[str]] = {}
    for row in rows:
        day_str = str(row[0])
        times = [t.strip() for t in str(row[1]).split(",") if t.strip()]
        dates[day_str] = sorted(set(times))
    first = str(rows[0][0]) if rows else None
    last = str(rows[-1][0]) if rows else None
    return JSONResponse({"dates": dates, "first": first, "last": last})


@router.post("/api/delete_conversation")
async def delete_conversation(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    conversation_id = str(data.get("conversation_id", "")).strip()
    force = bool(data.get("force"))
    confirm_text = str(data.get("confirm_text", "")).strip()
    if not conversation_id:
        return app._json_error("empty conversation_id", 400)
    result = app._delete_conversation_impl(
        conn, account, conversation_id, force=force, confirm_text=confirm_text
    )
    if result["status"] == "failed":
        reason = result.get("reason", "")
        if reason == "forbidden":
            return app._json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
        if reason == "processing":
            return app._json_error("처리 중 대화입니다. 강제 보관하려면 확인 입력이 필요합니다.", 409)
        if reason == "confirm_text_mismatch":
            return app._json_error("확인 입력이 올바르지 않습니다. 보관을 입력해주세요.", 400)
        return app._json_error("failed to archive conversation", 500)
    # TASK-0048 후속 fix: 대화 보관 후 자동으로 빈 새 대화를 만들지 않는다 (lazy 정책).
    current_after = app._repair_current_conversation(
        conn,
        account,
        items=[],
        create_if_missing=False,
    )
    # TASK-0273: 응답 키는 기존 프론트 호환을 위해 deleted/deleted_pending 유지(보관도 "목록에서
    # 사라짐" 으로 동일 UX). archived 플래그도 함께 노출.
    if result["status"] in ("archived_pending", "deleted_pending"):
        return JSONResponse({"deleted_pending": conversation_id, "archived_pending": conversation_id, "current": current_after})
    return JSONResponse({"deleted": conversation_id, "archived": conversation_id, "current": current_after})


@router.post("/api/delete_conversations")
async def delete_conversations(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    raw_ids = data.get("conversation_ids", [])
    if not isinstance(raw_ids, list) or not raw_ids:
        return app._json_error("conversation_ids required", 400)
    force = bool(data.get("force"))
    confirm_text = str(data.get("confirm_text", "")).strip()
    deleted: list[str] = []
    deleted_pending: list[str] = []
    failed: list[dict[str, str]] = []
    for raw in raw_ids:
        cid = str(raw or "").strip()
        if not cid:
            failed.append({"conversation_id": "", "reason": "empty_conversation_id"})
            continue
        result = app._delete_conversation_impl(
            conn, account, cid, force=force, confirm_text=confirm_text
        )
        # TASK-0273: 보관(archived/archived_pending)도 기존 deleted 버킷에 매핑(프론트 호환).
        if result["status"] in ("archived", "deleted"):
            deleted.append(cid)
        elif result["status"] in ("archived_pending", "deleted_pending"):
            deleted_pending.append(cid)
        else:
            failed.append({"conversation_id": cid, "reason": result.get("reason", "unknown")})
    current_after = app._repair_current_conversation(
        conn,
        account,
        items=[],
        create_if_missing=False,
    )
    return JSONResponse({
        "deleted": deleted,
        "deleted_pending": deleted_pending,
        "failed": failed,
        "current": current_after,
    })


@router.post("/api/cancel")
async def cancel_request(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    conversation_id = app._resolve_conversation_for_account(
        conn,
        account,
        str(data.get("conversation_id", "")).strip(),
    )
    if not conversation_id:
        return app._json_error("empty conversation_id", 400)
    if not app._account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.cancel.own",
        "conversation.cancel.any",
    ):
        return app._json_error("권한이 없습니다.", 403)
    # composer-nonblock-interrupt R3: 1:1 인터럽트 재요청은 preserve_reasoning=true 로 취소 →
    # agent_core 가 이 run 의 부분 추론을 메시지로 보존(가시 + 다음 run 맥락). 명시 '중단' 버튼(미지정)
    # 은 기존대로 폐기 — 동작 무변경.
    _preserve_reasoning = bool(data.get("preserve_reasoning"))
    try:
        run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        # running run 은 KV cancel_requested 플래그를 run_agent 가 폴링해 처리(§2.6 무변경).
        mark_cancel_requested(conn, conversation_id, run_id=run_id, preserve_reasoning=_preserve_reasoning)
        # TASK-0169 (2g): worker mode 에서 아직 claim 안 된 pending job 은 run_id 매칭
        # 대상이 없어 KV 플래그가 유실된다. 큐 레벨로 취소(canceled)해 취소 유실 방지.
        if app._is_worker_mode():
            try:
                from shared.db import _pg_connect
                from modules import ask_jobs as _aj
                _pgc = _pg_connect()
                try:
                    _aj.cancel_pending_jobs(_pgc, conversation_id)
                finally:
                    _pgc.close()
            except Exception:
                pass  # 큐 취소 실패는 KV 플래그 폴링 경로가 backstop
        # TASK-0241: pending/running 무관하게 KV last_status 를 즉시 canceled 로 기록한다
        # (사용자 체감 '곧바로 취소처리'). running run 은 agent 루프가 다음 체크포인트에서
        # 답변 없이 종료하지만, 이 즉시 기록으로 (a) 원래 /api/ask 의 attach long-poll 이
        # terminal(canceled)을 보고 per-account 슬롯을 즉시 반납 → 취소 직후 재요청 가능,
        # (b) 다른 탭/상태 dot 도 즉시 '취소됨' 을 본다. only_if_current_run=True 로, 사용자가
        # 취소 후 같은 대화에 이미 재요청해 새 run 이 last_status_run_id 를 인계한 상태라면 이
        # write 를 건너뛰어 새 run 의 processing 을 클로버하지 않는다(취소 시점엔 run_id 가
        # 현재 run 이라 정상 기록). agent 루프의 terminal write 도 동일 가드를 쓴다(TASK-0241).
        try:
            set_run_status(conn, conversation_id, "canceled", run_id=run_id, only_if_current_run=True)
        except Exception:
            pass
    except Exception:
        return app._json_error("cancel failed", 500)
    return JSONResponse({"conversation_id": conversation_id, "run_id": run_id, "output": "요청 취소를 진행합니다."})


@router.post("/api/finalize")
async def finalize_request(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """사용자가 '즉시 답변'을 요청 — 현재 루프를 마무리하고 텍스트 답변 생성."""
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    conversation_id = app._resolve_conversation_for_account(
        conn,
        account,
        str(data.get("conversation_id", "")).strip(),
    )
    if not conversation_id:
        return app._json_error("empty conversation_id", 400)
    if not app._account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.finalize.own",
        "conversation.finalize.any",
    ):
        return app._json_error("권한이 없습니다.", 403)
    try:
        run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        mark_finalize_requested(conn, conversation_id, run_id=run_id)
    except Exception:
        return app._json_error("finalize failed", 500)
    return JSONResponse({"conversation_id": conversation_id, "run_id": run_id, "output": "즉시 답변을 요청합니다."})


@router.get("/api/ask_status")
def ask_status(request: Request, conversation_id: str = "", account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """현재 대화의 agent 실행 상태 snapshot.

    client disconnect 이후에도 서버에서 돌고 있는 run 의 상태를 확인하는 read-only
    엔드포인트. `/api/ask` 슬롯을 점유하지 않는다.
    """
    cid = app._resolve_conversation_for_account(conn, account, conversation_id.strip())
    if not cid:
        return app._json_error("empty conversation_id", 400)
    if not app._account_can_access_conversation(
        conn,
        account,
        cid,
        "conversation.read.own",
        "conversation.read.any",
    ):
        return app._json_error("권한이 없습니다.", 403)
    snapshot = app._build_ask_status_snapshot(conn, cid)
    snapshot.pop("_latest_assistant", None)
    return JSONResponse(snapshot)
