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

from fastapi import File
from fastapi import UploadFile
import hashlib
import secrets
import asyncio
from shared.model_catalog import API_DEFAULT_MODEL, normalize_reasoning_level
from pathlib import Path
import json
import threading
import time
import app

INCLUDE_ORDER = 90  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


def _model_kv_key(account: Any) -> str:
    """feature-0003 model-persist: 대화별 '마지막 요청 모델' KV 키 (요청자 계정별로 분리).

    그룹 대화는 여러 계정이 같은 conversation_id 를 공유하므로, 대화 단위로만 저장하면 멤버 A 의
    모델 선택이 멤버 B 의 composer 를 바꾸고 B 의 토큰 한도로 청구된다. 사용자 요구가
    "assistant 에게 **내가** 마지막으로 요청했던 모델" 이므로 계정별로 분리한다. 1:1 대화는
    참여자가 1명이라 대화 단위 저장과 동작이 동일하다.

    계정 id 를 해석할 수 없으면 **빈 문자열**을 돌려준다(fail-closed). 공유 sentinel 키
    (`model:unknown`)를 쓰면 식별 불가 호출자들이 한 슬롯을 공유해, 계정별 분리로 막으려던
    "타인의 선택이 내 composer 를 조종" 을 그대로 재현한다(2R 적대 리뷰 C-D). 호출부는 빈 키면
    저장·복원을 모두 건너뛰어 기본값으로 동작한다.
    """
    try:
        return f"model:{int((account or {}).get('id'))}"
    except Exception:
        return ""


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
    branch_view: int | None = None,
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
        # share-visibility-window: 발신자의 표시 가시 window(DISPLAY id-space + joined_at)를 해석해
        # 가려진 pre-floor/중간 구간을 view 에서 배제. DENY(제약 대화인데 window 미해석) → 빈 응답.
        _display_window = app._resolve_display_window(conn, conv_id, (account or {}).get("id"))
        if _display_window == "DENY":
            messages, has_more, oldest_id, total_count, user_count = [], False, None, 0, 0
        else:
            # feature-0019 shared-readonly-paging: branch_view 가 주어지면 읽기전용으로 그 버전의
            # 브랜치를 렌더한다(active_leaf 미변경 — 공유 근거 불변). 대상이 멤버 가시 window 내 user
            # 메시지인지 검증 후에만 leaf override(fail-closed — 범위 밖 버전 열람·프로빙 차단, SEC).
            _override_leaf = None
            if branch_view is not None:
                _override_leaf = app._branch_resolve_readonly_leaf(
                    conv_id, branch_view,
                    window=(_display_window if isinstance(_display_window, dict) else None),
                )
            messages, has_more, oldest_id, total_count, user_count = app._get_history(
                conv_id, limit=limit, before_id=before_id,
                window=(_display_window if isinstance(_display_window, dict) else None),
                override_active_leaf=_override_leaf,
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
    # feature-0003 reasoning-effort-selector: 이 대화에 마지막으로 저장된 추론 강도(KV) 를 함께
    # 반환해, 대화 전환·새로고침 후 프론트 선택기가 저장값으로 복원되게 한다(hydration).
    reasoning_level = ""
    # feature-0003 model-persist: 이 대화에 마지막으로 **명시 요청된 모델**(KV) 도 함께 반환해,
    # 새로고침·대화 전환 후 복귀 시 composer 모델 선택기가 그 대화 기준으로 복원되게 한다
    # (reasoning_level 과 동형 hydration). 저장값이 현재 allowlist 밖(카탈로그 개편·로컬 LLM
    # alias 등)이면 빈 문자열로 내려 프론트가 기본값(API_DEFAULT_MODEL=haiku)으로 폴백하게 한다
    # — stale alias 를 복원해 /api/ask 400 을 유발하지 않기 위한 서버측 단일 검증점.
    # 저장은 **요청자(계정)별**이다(_model_kv_key) — 그룹 대화에서 다른 멤버의 선택이 내 composer 를
    # 바꾸고 내 토큰 한도로 청구되는 것을 막는다(사용자 표현 "assistant 에게 **내가** 마지막으로
    # 요청했던 모델"). 1:1 은 참여자가 1명이라 대화 단위 저장과 동작이 같다.
    model = ""
    if conv_id:
        try:
            last_status = str(app.load_memory_kv(conn, conv_id, "last_status") or "").strip()
            if last_status == "processing":
                last_run_id = str(app.load_memory_kv(conn, conv_id, "last_status_run_id") or "").strip()
                # 새로고침 후 pending bubble 의 경과시간이 0 으로 초기화되지 않도록 run
                # 시작 시각(last_status_at)을 함께 반환한다. set_run_status 는 'processing'
                # 전이 시 last_status_at 을 1 회만 기록하고 terminal(done/error/canceled)
                # 시점까지 갱신하지 않으므로, processing 상태에서의 last_status_at 은 곧
                # run 시작 시각이다(클라이언트가 elapsed 기준점으로 사용).
                last_run_started_at = str(app.load_memory_kv(conn, conv_id, "last_status_at") or "").strip()
            reasoning_level = str(app.load_memory_kv(conn, conv_id, "reasoning_level") or "").strip()
            # DENY(가시 window 미해석 제약 대화)는 messages 를 비워 내려주는 경로다. 그 경우
            # 모델도 내려주지 않는다 — 열람이 차단된 대화의 상태로 composer 를 재조준하지 않는다.
            _model_key = _model_kv_key(account)
            if _display_window != "DENY" and _model_key:
                _saved_model = str(
                    app.load_memory_kv(conn, conv_id, _model_key) or ""
                ).strip()
                if (
                    _saved_model
                    and app._is_safe_model_name(_saved_model)
                    and app._is_allowed_api_model(_saved_model)
                ):
                    model = _saved_model
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
        "reasoning_level": reasoning_level,
        "model": model,  # feature-0003 model-persist: 대화별 마지막 명시 모델(빈 문자열 = 미저장 → FE 기본값)
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
        run_id = str(app.load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        # running run 은 KV cancel_requested 플래그를 run_agent 가 폴링해 처리(§2.6 무변경).
        app.mark_cancel_requested(conn, conversation_id, run_id=run_id, preserve_reasoning=_preserve_reasoning)
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
            app.set_run_status(conn, conversation_id, "canceled", run_id=run_id, only_if_current_run=True)
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
        run_id = str(app.load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        app.mark_finalize_requested(conn, conversation_id, run_id=run_id)
    except Exception:
        return app._json_error("finalize failed", 500)
    return JSONResponse({"conversation_id": conversation_id, "run_id": run_id, "output": "즉시 답변을 요청합니다."})


@router.post("/api/extend")
async def extend_request(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """feature-0030 — 사용자가 '타임아웃과 무관하게 끝까지 추론'을 승인.

    KV 플래그만 세팅하고 즉시 반환한다(finalize 와 동일 계약). 워커의 agent 루프가 실행
    예산 100% 도달 시점에 이 플래그를 읽어 그 run 에 한해 컷을 넘긴다 — 승인이 늦게 도착해
    이미 종료된 run 에는 효과가 없고, 다음 요청에도 전이되지 않는다(run 단위 수명).
    """
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
        "conversation.extend.own",
        "conversation.extend.any",
    ):
        return app._json_error("권한이 없습니다.", 403)
    # 기능 게이트(관리 콘솔). OFF 인데 stale 프론트가 호출하면 승인을 남기지 않는다 —
    # 남기면 다음 ON 전환 때 의도 없는 연장으로 되살아난다. 조회 자체가 실패하면 워커의
    # `_timeout_extension_settings()` 와 동일하게 **fail-closed** 로 거절한다(양쪽 대칭).
    try:
        if int(app._runtime_settings.get_int("AGENT_TIMEOUT_EXTENSION_ENABLED")) != 1:
            return app._json_error("실행시간 연장 기능이 꺼져 있습니다.", 409)
    except Exception:
        return app._json_error("실행시간 연장 설정을 확인할 수 없습니다.", 503)
    # 승인은 **사용자가 배너에서 본 그 run** 에만 붙어야 한다. 클라이언트가 보낸 run_id 가
    # 현재 run 과 다르면(그 사이 새 요청이 시작됐거나 lease reclaim 으로 run 이 교체됨)
    # 승인을 기록하지 않는다 — 기록하면 사용자가 보지도 않은 run 이 연장된다.
    try:
        current_run_id = str(app.load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
    except Exception:
        return app._json_error("extend failed", 500)
    if not current_run_id:
        return app._json_error("진행 중인 요청이 없습니다.", 409)
    client_run_id = str(data.get("run_id", "") or "").strip()
    if client_run_id and client_run_id != current_run_id:
        return app._json_error("확인 대상 요청이 이미 종료되었습니다.", 409)
    try:
        granted = app.mark_timeout_extension_granted(conn, conversation_id, run_id=current_run_id)
    except Exception:
        return app._json_error("extend failed", 500)
    if not granted:
        return app._json_error("확인 대상 요청이 이미 종료되었습니다.", 409)
    return JSONResponse({
        "conversation_id": conversation_id,
        "run_id": current_run_id,
        "output": "이번 요청은 시간 제한 없이 끝까지 추론합니다.",
    })


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


@router.patch("/api/conversations/{cid}/product")
async def update_conversation_product(
    cid: str,
    request: Request,
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """대화의 product_id / product_mode 를 변경한다 (TASK-0047).

    body: { product_id: int|null, mode: 'auto'|'pinned' }
    - mode='auto' ⇒ product_id 는 무시되고 NULL 로 저장된다 (사용자 의도: 일반 대화).
    - mode='pinned' ⇒ product_id 가 활성 product 여야 한다.
    - 처리 중에도 변경을 허용한다 (REQ-20260626-product-chip-always-enabled, ADR-WEB-0006).
      과거 turn 단위 immutability 409 가드(TASK-0047, Codex 검토 1차 구현)는 제거됨 —
      제품은 `/api/ask` enqueue 시점에 run_kwargs(product_id/product_mode)로 캡처되어
      in-flight 답변은 영향받지 않고, 이 변경은 '다음 요청'부터 반영된다(데이터 정합성 위험 0).
    """
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    if not cid or not isinstance(cid, str):
        return app._json_error("invalid conversation id", 400)
    raw_mode = data.get("mode") if isinstance(data, dict) else None
    raw_pid = data.get("product_id") if isinstance(data, dict) else None
    mode = app._normalize_product_mode(raw_mode, default="pinned")
    # ITEM-11 batch8: _require_account→account+conn 완전 DI. perm/게이트는 본문 유지.
    # get_conn finally:close 가 게이트 헬퍼·UPDATE·pref raise 시 conn leak 을 해소.
    # 권한: 자기 대화에 ask 가능한 사용자만 변경 허용.
    if not app._account_has_permission(account, "conversation.ask"):
        return app._json_error("권한이 없습니다.", 403)
    if not app._conversation_exists(cid, conn=conn):
        return app._json_error("conversation not found", 404)
    if not app._conversation_owned_by_account(conn, cid, int(account["id"])):
        return app._json_error("타 계정 대화는 변경할 수 없습니다.", 403)
    # REQ-20260626-product-chip-always-enabled (ADR-WEB-0006): 처리 중에도 제품 변경 허용.
    #  과거 turn 단위 immutability 409 가드(TASK-0047)는 제거됐다 — in-flight 답변은 enqueue
    #  시점에 캡처된 product 로 끝까지 실행되므로 영향받지 않고, 이 변경은 다음 /api/ask 부터
    #  반영된다(setActiveProduct 토스트 "다음 답변부터 적용됩니다"와 정합).
    pinned_id: int | None = None
    if mode == "pinned":
        if raw_pid in (None, "", 0):
            return app._json_error("pinned 모드에서는 product_id 가 필요합니다.", 400)
        try:
            pinned_id = int(raw_pid)
        except Exception:
            return app._json_error("invalid product_id", 400)
        # 활성 + 권한 가능성 검사.
        try:
            cur_v = conn.cursor()
            cur_v.execute(
                "SELECT IsActive FROM WebProducts WHERE Id = %s LIMIT 1",
                (pinned_id,),
            )
            row_v = cur_v.fetchone()
            cur_v.close()
        except Exception:
            row_v = None
        if not row_v or not int(row_v[0] or 0):
            return app._json_error("선택한 제품을 사용할 수 없습니다.", 400)
        # TASK-0052 Phase 1C G1: product 접근 권한 검사 (briefing §3.4).
        # 기존 코드는 IsActive 만 검사 → 모든 logged-in account 가 임의 product 에 pin 가능했음.
        if not app._account_has_product_access(account, pinned_id, conn=conn):
            return app._json_error("요청을 수행할 수 없습니다.", 403)

    # msg-speaker-attribution: 바인딩을 바꾸기 **전에**, 아직 발화자 미각인인 과거 답변을
    #  **직전 제품**으로 고정한다. 이 시점이 "그 답변들이 어느 제품에서 나왔는지" 를 알 수 있는
    #  마지막 순간이다 — 놓치면 FE 폴백이 대화 바인딩을 보고 과거 답변까지 새 제품으로 표시한다
    #  (사용자 보고: "product 를 바꾸면 이전 대화의 발화자가 실시간으로 바뀐다").
    #  각인 도입 이후 저장된 답변은 이미 자기 제품을 갖고 있어 여기서 건드리지 않는다.
    #  fail-open — 보정 실패가 제품 전환 자체를 막지 않는다(전환은 사용자 의도).
    try:
        _prev_pid, _prev_mode = app._conv_load_product(conn, cid)
        app._conv_backfill_attribution(
            conn, cid, "assistant",
            app._conv_product_attribution(conn, _prev_pid, _prev_mode),
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "update_conversation_product: 직전 제품 귀속 보정 실패 (cid=%s)", cid, exc_info=True,
        )

    try:
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            from shared.db import _pg_connect
            _pg_patch = _pg_connect()
            with _pg_patch.cursor() as _pgpatch:
                _pgpatch.execute(
                    "UPDATE agent_runtime.core_conversations SET product_id = %s, product_mode = %s "
                    "WHERE conversation_id = %s",
                    (pinned_id, mode, cid),
                )
            _pg_patch.close()
        else:
            cur_u = conn.cursor()
            cur_u.execute(
                "UPDATE AgentCoreConversations SET product_id = %s, product_mode = %s "
                "WHERE conversation_id = %s",
                (pinned_id, mode, cid),
            )
            cur_u.close()
    except Exception:
        return app._json_error("대화 제품 정보를 변경하지 못했습니다.", 500)
    # 사용자 직전 선택 보존.
    app._save_account_product_pref(conn, int(account["id"]), mode=mode, pinned_id=pinned_id)
    payload = app._load_conversation_product(conn, cid) or {
        "product_id": pinned_id,
        "product_mode": mode,
        "product_key": None,
        "product_name": None,
    }
    payload["conversation_id"] = cid
    return JSONResponse(payload)

@router.post("/api/conversations/{cid}/duplicate")
def duplicate_conversation(cid: str, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """REQ-20260518-0001: 본인 대화 또는 (.any) 타 사용자 대화를 본 계정 소유의 새 대화로 복제.

    fork (`/api/fork_conversation`) 와의 차이:
    - cid 가 path parameter (per-conversation "···" menu UX 정합).
    - 메시지 전체 복제 (from_message_id 없음).
    - 신규 권한 `conversation.duplicate.own` / `.any` 별도 gate. `.any` 가 superset.
    - topic prefix = `사본:` (fork 의 `[Fork]` 와 구분되어 추적성 보존).
    - 본체 복제는 `_fork_conversation_impl` 재활용 (share-token fork 와 helper 공유).
    """
    # Codex risk 5/6: read-gate 를 먼저 수행. 404 단일 메시지로 metadata leak 차단.
    # (rename/delete 와 동일 wording — `_account_can_access_conversation` 이 존재성 + own/any 권한을 한 번에 검사)
    if not app._account_can_access_conversation(
        conn,
        account,
        cid,
        "conversation.read.own",
        "conversation.read.any",
    ):
        return app._json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
    # Codex risk 7: .any superset semantics. mirror `_account_can_access_conversation` (app.py §3004-3008).
    is_own = app._conversation_owned_by_account(conn, cid, int(account["id"]))
    if not (
        app._account_has_permission(account, "conversation.duplicate.any")
        or (is_own and app._account_has_permission(account, "conversation.duplicate.own"))
    ):
        return app._json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
    if not app._account_has_permission(account, "conversation.create"):
        return app._json_error("요청을 수행할 수 없습니다.", 403)
    payload, err = app._fork_conversation_impl(conn, account, cid, None)
    if err:
        return err
    # Codex risk 10: 그래프임 단위 안전 truncation. helper 가 만든 "[Fork] " 를 "사본: " 로 교체.
    source_topic = str(payload.get("topic") or "")
    base = source_topic[len("[Fork] "):] if source_topic.startswith("[Fork] ") else source_topic
    max_base = max(0, 256 - len("사본: "))
    new_topic = f"사본: {base[:max_base]}"
    try:
        app._conv_update_topic(conn, str(payload["conversation_id"]), new_topic)
    except Exception:
        # best-effort: 사본 topic 갱신 실패는 응답을 막지 않으나 조용한 쓰기 실패를 가시화.
        logging.getLogger(__name__).warning(
            "duplicate_conversation: topic update failed (conversation_id=%s)",
            payload.get("conversation_id"), exc_info=True,
        )
    payload["topic"] = new_topic
    return JSONResponse(payload)

@router.post("/api/conversations/{cid}/share")
async def create_conversation_share(cid: str, request: Request) -> JSONResponse:
    """공유 링크 생성. body: {scope_mode: 'full'|'anchored', anchor_message_id?: int}.

    권한: `conversation.share.create` + (`conversation.read.own` 또는 `conversation.read.any`).
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    scope_mode = str(data.get("scope_mode") or "full").strip().lower()
    if scope_mode not in ("full", "anchored", "windowed"):
        return app._json_error("invalid scope_mode", 400)
    # feature-0009: 공유 링크 참여(join) 허용 여부. 기본 ON(사용자 결정) — 명시 false 일 때만 OFF.
    joinable = 0 if (data.get("joinable") is False) else 1
    raw_anchor = data.get("anchor_message_id")  # 상단 경계("여기까지 공유"), inclusive ceiling
    raw_floor = data.get("floor_message_id")    # 하단 경계("여기부터 공유"), inclusive floor
    anchor_id: int | None = None
    floor_id: int | None = None
    if scope_mode == "anchored":
        if raw_anchor is None or str(raw_anchor).strip() == "":
            return app._json_error("anchor_message_id required for scope_mode=anchored", 400)
        try:
            anchor_id = int(raw_anchor)
        except Exception:
            return app._json_error("invalid anchor_message_id", 400)
    elif scope_mode == "windowed":
        # share-visibility-window: floor/ceiling 중 최소 1개 필요. anchor(ceiling) 없으면 라이브 끝까지.
        if raw_anchor is not None and str(raw_anchor).strip() != "":
            try:
                anchor_id = int(raw_anchor)
            except Exception:
                return app._json_error("invalid anchor_message_id", 400)
        if raw_floor is not None and str(raw_floor).strip() != "":
            try:
                floor_id = int(raw_floor)
            except Exception:
                return app._json_error("invalid floor_message_id", 400)
        if anchor_id is None and floor_id is None:
            return app._json_error("windowed 공유는 floor_message_id 또는 anchor_message_id 가 필요합니다.", 400)
        if anchor_id is not None and floor_id is not None and floor_id > anchor_id:
            return app._json_error("여기부터 지점은 여기까지 지점 이전이어야 합니다.", 400)
    # TASK-20260619T012028-share-link-expiry (SECURITY.md §7.2): 만료 옵션.
    # `expires_in_seconds` 누락 / null / 0 이하 = 무기한 (NULL, 기존 동작 무회귀).
    # 상한 365 일 — 초과 시 400 (절대시각 폭주 차단).
    raw_expires = data.get("expires_in_seconds")
    expires_in_seconds: int | None = None
    if raw_expires is not None and str(raw_expires).strip() != "":
        try:
            expires_in_seconds = int(raw_expires)
        except Exception:
            return app._json_error("invalid expires_in_seconds", 400)
        if expires_in_seconds <= 0:
            expires_in_seconds = None  # 0/음수 = 무기한 취급
        elif expires_in_seconds > app._SHARE_EXPIRY_MAX_SECONDS:
            return app._json_error("만료 기간이 너무 깁니다 (최대 365일).", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_has_permission(account, "conversation.share.create"):
            return app._json_error("요청을 수행할 수 없습니다.", 403)
        if not app._account_can_access_conversation(
            conn,
            account,
            cid,
            "conversation.read.own",
            "conversation.read.any",
        ):
            return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        # feature-0009-share-joinable-guard: '참여 허용(joinable)' 링크는 대화 생성자(owner)만
        # 발급할 수 있다. 프런트는 비소유자에게 체크박스를 disabled 로 표시하지만, 브라우저
        # 조작으로 joinable=true 를 보내도 백엔드에서 무조건 차단(403)한다. owner-only 엄격 적용
        # — admin(conversation.read.any) 도 본인이 생성한 대화가 아니면 예외 없음(사용자 결정).
        # joinable=0(view-only) 링크는 기존대로 conversation.share.create 권한자 누구나 발급 가능.
        if joinable and not app._conversation_owned_by_account(conn, cid, int(account["id"])):
            return app._json_error("참여 허용 링크는 대화 생성자만 만들 수 있습니다.", 403)
        if anchor_id is not None and not app._share_anchor_belongs_to_conversation(conn, cid, anchor_id):
            return app._json_error("anchor_message_id 가 대화에 속하지 않습니다.", 400)
        if floor_id is not None and not app._share_anchor_belongs_to_conversation(conn, cid, floor_id):
            return app._json_error("floor_message_id 가 대화에 속하지 않습니다.", 400)
        # share-visibility-window widen-guard: bounded 멤버(제한된 열람 범위)는 자기 window 밖으로
        # 재공유할 수 없다(전이적 재공유 권한상승 차단). 요청 window ⊄ 본인 window 면 403.
        # owner/full 멤버/비멤버는 (None,None) → 무영향. PG 오류('DENY') → 안전하게 거부.
        _mw = app._member_visibility_window(conn, cid, int(account["id"]))
        if _mw == "DENY":
            return app._json_error("공유 범위를 확인할 수 없습니다.", 500)
        _m_floor, _m_ceil = _mw
        if _m_floor is not None and (floor_id is None or int(floor_id) < int(_m_floor)):
            return app._json_error("공유 범위가 본인 열람 범위를 벗어납니다.", 403)
        if _m_ceil is not None and (anchor_id is None or int(anchor_id) > int(_m_ceil)):
            return app._json_error("공유 범위가 본인 열람 범위를 벗어납니다.", 403)
        # Token UNIQUE 충돌 retry loop (확률은 극히 낮지만 cheap).
        # 만료: expires_in_seconds 가 있으면 ExpiresAt = DATE_ADD(NOW(), INTERVAL %s SECOND)
        # (DB 시계 도메인 — view/fork 의 NOW() 비교와 정합). 무기한이면 NULL.
        # 주의: expires_expr 는 코드 상수 (사용자 데이터 미포함) — SQL injection 무관.
        if expires_in_seconds is None:
            expires_expr = "NULL"
            expires_params: tuple = ()
        else:
            expires_expr = "DATE_ADD(NOW(), INTERVAL %s SECOND)"
            expires_params = (int(expires_in_seconds),)
        share_id: int | None = None
        token: str = ""
        for _attempt in range(5):
            token = app._share_generate_token()
            cur = conn.cursor()
            try:
                cur.execute(
                    f"""
INSERT INTO WebConversationShares
    (ConversationId, Token, ScopeMode, AnchorMessageId, FloorMessageId, CreatedBy, PolicyVersion, Joinable, ExpiresAt)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, {expires_expr})
                    """,
                    (
                        cid,
                        token,
                        scope_mode,
                        int(anchor_id) if anchor_id is not None else None,
                        int(floor_id) if floor_id is not None else None,
                        int(account["id"]),
                        app.SHARE_POLICY_VERSION_CURRENT,
                        int(joinable),
                        *expires_params,
                    ),
                )
                share_id = int(cur.lastrowid or 0)
                cur.close()
                break
            except Exception:
                cur.close()
                continue
        if not share_id:
            return app._json_error("공유 링크 생성 실패", 500)
        # feature-0009 gc-group-authz-flag: joinable 공유 링크 생성 = 협업(그룹) 의도 → 대화를 즉시
        # 그룹으로 전환한다(#4). owner 멤버십 보장(member_count 정합 — 공유 직후 비멘션 메시지가
        # assistant 로 오라우팅되는 #2 버그 예방) + is_group 플래그 set. best-effort(헬퍼가 예외 무시).
        if joinable:
            app._ensure_owner_membership(cid)
            app._mark_conversation_group(cid)
        # 응답/감사에 실제 ExpiresAt (DB 계산값) 반환 — DATE_ADD 결과를 read-back.
        expires_at_iso: str | None = None
        if expires_in_seconds is not None:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT ExpiresAt FROM WebConversationShares WHERE Id = %s LIMIT 1",
                    (int(share_id),),
                )
                _row = cur.fetchone()
                _exp = _row[0] if _row else None
                expires_at_iso = _exp.isoformat() if hasattr(_exp, "isoformat") else (str(_exp) if _exp else None)
            except Exception:
                expires_at_iso = None
            finally:
                cur.close()
        # TASK-0073 Phase A6: user endpoint best-effort audit (token full X — prefix 8 char 만).
        app._audit_user_action(
            conn,
            request,
            account,
            action="conversation.share.create",
            resource_type="share",
            resource_id=str(share_id),
            request_ctx={
                "conversation_id": cid,
                "scope_mode": scope_mode,
                "anchor_message_id": int(anchor_id) if anchor_id is not None else None,
                "floor_message_id": int(floor_id) if floor_id is not None else None,
                "share_id": int(share_id),
                "token_prefix": token[:8],
                "expires_in_seconds": int(expires_in_seconds) if expires_in_seconds is not None else None,
            },
        )
        return JSONResponse(
            {
                "id": share_id,
                "token": token,
                "conversation_id": cid,
                "scope_mode": scope_mode,
                "anchor_message_id": int(anchor_id) if anchor_id is not None else None,
                "floor_message_id": int(floor_id) if floor_id is not None else None,
                "url": f"/share/{token}",
                "expires_at": expires_at_iso,
                "expires_in_seconds": int(expires_in_seconds) if expires_in_seconds is not None else None,
            }
        )
    finally:
        conn.close()

@router.get("/api/conversations/{cid}/members")
def list_conversation_members(cid: str, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """그룹 대화 멤버 roster. 조회 권한: 대화 접근(멤버/owner/read.any)."""
    if not app._account_can_access_conversation(
        conn, account, cid, "conversation.read.own", "conversation.read.any"
    ):
        return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            member_ids = group_members.list_member_account_ids(pg, cid)
            roles = {
                aid: (group_members.account_member_role(pg, cid, aid) or "member")
                for aid in member_ids
            }
        finally:
            pg.close()
    except Exception:
        return app._json_error("멤버 조회 실패", 500)
    uname_map: dict[int, str] = {}
    if member_ids:
        cur = conn.cursor()
        ph = ",".join(["%s"] * len(member_ids))
        cur.execute(
            f"SELECT Id, Username FROM WebAccounts WHERE Id IN ({ph})", tuple(member_ids)
        )
        for mid, un in cur.fetchall() or []:
            uname_map[int(mid)] = str(un or "")
        cur.close()
    owner_id = app._conversation_owner_account_id(conn, cid)
    members = [
        {
            "account_id": aid,
            "username": uname_map.get(aid, ""),
            "role": roles.get(aid, "member"),
        }
        for aid in member_ids
    ]
    return JSONResponse(
        {"conversation_id": cid, "owner_account_id": owner_id, "members": members}
    )

@router.delete("/api/conversations/{cid}/members/{account_id}")
def remove_conversation_member(cid: str, account_id: int, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """그룹 대화 멤버 제거 또는 본인 나가기.

    권한: owner/conversation.member.manage(타인 제거) 또는 본인(나가기). 대화 소유자는
    멤버에서 제거 불가(409, 소유권 이전/대화 삭제는 별도 흐름). 메시지·첨부는 잔존(tombstone
    author), 향후 접근만 차단 → audit conversation.member.remove.
    """
    if not app._account_can_access_conversation(
        conn, account, cid, "conversation.read.own", "conversation.read.any"
    ):
        return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
    actor_id = int(account["id"])
    target_id = int(account_id)
    is_owner = app._conversation_owned_by_account(conn, cid, actor_id)
    is_self_leave = target_id == actor_id
    if not (
        is_self_leave
        or is_owner
        or app._account_has_permission(account, "conversation.member.manage")
    ):
        return app._json_error("멤버를 관리할 권한이 없습니다.", 403)
    conv_owner = app._conversation_owner_account_id(conn, cid)
    if conv_owner is not None and target_id == int(conv_owner):
        return app._json_error("대화 소유자는 멤버에서 제거할 수 없습니다.", 409)
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            removed = group_members.remove_member(pg, cid, target_id)
        finally:
            pg.close()
    except Exception:
        return app._json_error("멤버 제거 실패", 500)
    app._audit_user_action(
        conn,
        request,
        account,
        action="conversation.member.remove",
        resource_type="conversation_member",
        resource_id=str(target_id),
        request_ctx={
            "conversation_id": cid,
            "target_account_id": target_id,
            "self_leave": is_self_leave,
            "removed": removed,
        },
    )
    return JSONResponse(
        {"conversation_id": cid, "account_id": target_id, "removed": removed}
    )

@router.post("/api/conversations/{cid}/members/{account_id}/ban")
async def ban_conversation_member(cid: str, account_id: int, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """그룹 대화 멤버 차단(ban) — 멤버십 제거 + 재참여 차단 목록 등재. **소유자 전용**.

    추방(kick=DELETE /members/{id}, 재참여 가능)과 달리, 차단은 공유 링크로도 재참여 불가
    (POST /api/share/{token}/join 의 is_banned 게이트). owner 자신/소유자는 차단 불가(409).
    body: {reason?: str(<=512)}. audit: conversation.member.ban.
    """
    if not app._account_can_access_conversation(
        conn, account, cid, "conversation.read.own", "conversation.read.any"
    ):
        return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
    actor_id = int(account["id"])
    target_id = int(account_id)
    if target_id <= 0:
        return app._json_error("유효하지 않은 대상입니다.", 400)
    # 엄격 owner 전용(사용자 결정) — conversation.member.manage 보유자도 불가.
    if not app._conversation_owned_by_account(conn, cid, actor_id):
        return app._json_error("대화 소유자만 멤버를 차단할 수 있습니다.", 403)
    conv_owner = app._conversation_owner_account_id(conn, cid)
    if conv_owner is not None and target_id == int(conv_owner):
        return app._json_error("대화 소유자는 차단할 수 없습니다.", 409)
    if target_id == actor_id:
        return app._json_error("자기 자신은 차단할 수 없습니다.", 409)
    try:
        data = await request.json()
    except Exception:
        data = {}
    reason = (str(data.get("reason") or "").strip()[:512]) or None
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            # ban 먼저, remove 나중 — 비원자 fail-window 를 안전 방향(차단 등재됨+멤버 잔존)으로.
            # remove 먼저였다면 ban 실패 시 "제거됨+미차단=자유 재참여"(fail-open)였다(적대 리뷰 MINOR).
            group_members.ban_member(
                pg, cid, target_id, banned_by_account_id=actor_id, reason=reason
            )
            removed = group_members.remove_member(pg, cid, target_id)
        finally:
            pg.close()
    except Exception:
        return app._json_error("멤버 차단 실패", 500)
    app._audit_user_action(
        conn,
        request,
        account,
        action="conversation.member.ban",
        resource_type="conversation_member",
        resource_id=str(target_id),
        request_ctx={
            "conversation_id": cid,
            "target_account_id": target_id,
            "removed": removed,
            "reason": reason or "",
        },
    )
    return JSONResponse(
        {"conversation_id": cid, "account_id": target_id, "banned": True, "removed": removed}
    )

@router.delete("/api/conversations/{cid}/members/{account_id}/ban")
def unban_conversation_member(cid: str, account_id: int, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """그룹 대화 멤버 차단 해제(unban). **소유자 전용**. audit: conversation.member.unban.

    해제만 수행 — 멤버십 자동 복원은 없다(account 가 다시 공유 링크로 참여할 수 있게 될 뿐).
    """
    if not app._account_can_access_conversation(
        conn, account, cid, "conversation.read.own", "conversation.read.any"
    ):
        return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
    actor_id = int(account["id"])
    target_id = int(account_id)
    if not app._conversation_owned_by_account(conn, cid, actor_id):
        return app._json_error("대화 소유자만 차단을 해제할 수 있습니다.", 403)
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            removed = group_members.unban_member(pg, cid, target_id)
        finally:
            pg.close()
    except Exception:
        return app._json_error("차단 해제 실패", 500)
    app._audit_user_action(
        conn,
        request,
        account,
        action="conversation.member.unban",
        resource_type="conversation_member",
        resource_id=str(target_id),
        request_ctx={"conversation_id": cid, "target_account_id": target_id, "unbanned": removed},
    )
    return JSONResponse(
        {"conversation_id": cid, "account_id": target_id, "unbanned": removed}
    )

@router.get("/api/conversations/{cid}/bans")
def list_conversation_bans(cid: str, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """그룹 대화 차단(ban) 목록. **소유자 전용** — '차단된 사용자' UI 가 소비."""
    if not app._account_can_access_conversation(
        conn, account, cid, "conversation.read.own", "conversation.read.any"
    ):
        return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
    actor_id = int(account["id"])
    if not app._conversation_owned_by_account(conn, cid, actor_id):
        return app._json_error("대화 소유자만 차단 목록을 조회할 수 있습니다.", 403)
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            bans = group_members.list_bans(pg, cid)
        finally:
            pg.close()
    except Exception:
        return app._json_error("차단 목록 조회 실패", 500)
    uname_map: dict[int, str] = {}
    ban_ids = [int(b["account_id"]) for b in bans]
    if ban_ids:
        cur = conn.cursor()
        ph = ",".join(["%s"] * len(ban_ids))
        cur.execute(
            f"SELECT Id, Username FROM WebAccounts WHERE Id IN ({ph})", tuple(ban_ids)
        )
        for mid, un in cur.fetchall() or []:
            uname_map[int(mid)] = str(un or "")
        cur.close()
    out = [
        {
            "account_id": b["account_id"],
            "username": uname_map.get(b["account_id"], ""),
            "banned_at": b["banned_at"],
            "reason": b["reason"] or "",
        }
        for b in bans
    ]
    return JSONResponse({"conversation_id": cid, "bans": out})

@router.post("/api/conversations/{cid}/messages")
async def post_group_chat_message(cid: str, request: Request) -> JSONResponse:
    """그룹 대화 사람-사람 채팅 메시지 저장 (LLM 미호출). @assistant 호출은 /api/ask.

    권한: 대화 접근(멤버/owner/read.any). datasource 미접촉이라 무권한 멤버도 채팅 가능
    (열람 ≠ 발화 — 사람 채팅은 '발화'(제품 사용)가 아니다). 발신자 귀속(sender_account_id).
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    content = str(data.get("content") or data.get("message") or "").strip()
    if not content:
        return app._json_error("empty message", 400)
    if len(content) > 8000:
        return app._json_error("메시지가 너무 깁니다.", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_can_access_conversation(
            conn, account, cid, "conversation.read.own", "conversation.read.any"
        ):
            return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        # 차단(blocked)·보관(archived) 대화는 진행 불가(채팅 포함).
        _is_blocked, _block_reason = app._conversation_block_info(cid, conn=conn)
        if _is_blocked:
            return app._json_error(_block_reason or app._BLOCKED_PRODUCT_DELETED_REASON, 403)
        mid = app._save_group_chat_message_pg(
            cid, int(account["id"]), content, username=str(account.get("username") or "")
        )
        if not mid:
            return app._json_error("메시지 저장 실패", 500)
        return JSONResponse(
            {"ok": True, "conversation_id": cid, "message_id": mid, "role": "user"}
        )
    finally:
        conn.close()

@router.post("/api/conversations/{cid}/read")
async def mark_conversation_read(cid: str, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """그룹 대화 읽음 처리 — 멤버의 last_read_message_id 커서를 전진(GREATEST) (feature-0009 gc-unread-badge).

    사이드바 "안 읽은 메세지" 배지의 기준점. 대화를 열거나 활성 상태에서 새 메세지를 받으면
    프론트가 호출한다. **서버는 요청 body 의 last_read_message_id 를 신뢰하지 않고, 항상 그 대화
    core_messages 의 최대 id(=현재까지 전부 읽음)로 커서를 전진시킨다** (gc-unread-read-idspace-fix).
    이유: FE 가 보내는 id 는 표시 store(agent_runtime.messages) 공간이고 읽음 커서·unread 집계는
    core_messages 공간이라 두 id 공간이 분리되어, FE 값을 쓰면 GREATEST 가 항상 전진을 거부했다.
    커서는 전진만(set_last_read 의 GREATEST) — 폴링/재진입 경합에도 되돌리지 않는다.

    멤버십 게이트(read.own/.any) 통과 + 멤버 행이 있을 때만 갱신된다. 멤버가 아닌 admin(.any)
    열람은 멤버 행이 없어 no-op (그들은 unread 추적 대상이 아님 — FE 도 본인/멤버 그룹대화만 배지 표시).
    """
    if not app._account_can_access_conversation(
        conn, account, cid, "conversation.read.own", "conversation.read.any"
    ):
        return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
    account_id = int(account["id"])
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            # feature-0009 gc-unread-read-idspace-fix: 읽음 커서(conversation_members.last_read_message_id)
            # 와 unread 집계는 agent_runtime.core_messages.id 공간을 기준으로 한다. 그러나 FE 가 읽음
            # 처리로 보내던 last_read_message_id 는 /api/history 가 채운 표시 store(agent_runtime.messages)
            # 의 id 였고, 두 테이블은 별개 base table 로 id 공간이 분리(disjoint)되어 있다(같은 대화라도
            # messages 는 수백 단위, core_messages 는 수천 단위). 그래서 FE 가 보낸 값은 커서보다 항상
            # 작아 set_last_read 의 GREATEST(되돌림 방지)가 전진을 영구 거부했다 — 읽어도 사이드바 unread
            # 배지가 줄지 않고 대화 전환 시 회귀하던 근본 원인. 대화 열람은 "현재까지 전부 읽음"이므로,
            # FE 가 보낸 값과 무관하게 항상 이 대화 core_messages 의 MAX(id) 로 커서를 전진시킨다.
            # (표시/카운트 store 가 분리된 현 구조상 FE 는 정확한 core id 를 알 수 없어 부분 읽음은
            #  원래 불가능 — '열면 전부 읽음' 시맨틱. set_last_read 의 GREATEST 는 그대로 두어 폴링/
            #  재진입 경합에도 커서가 되돌아가지 않는다.)
            with pg.cursor() as _cur:
                _cur.execute(
                    "SELECT COALESCE(MAX(id), 0) FROM agent_runtime.core_messages "
                    "WHERE conversation_id = %s",
                    (cid,),
                )
                _row = _cur.fetchone()
                target_id = int(_row[0]) if _row and _row[0] is not None else 0
            updated = group_members.set_last_read(pg, cid, account_id, target_id)
        finally:
            pg.close()
    except Exception:
        return app._json_error("읽음 처리 실패", 500)
    return JSONResponse(
        {
            "ok": True,
            "conversation_id": cid,
            "last_read_message_id": int(target_id),
            "updated": int(updated),
        }
    )

@router.post("/api/conversations/{cid}/sample-feedback")
async def post_sample_feedback(cid: str, request: Request) -> JSONResponse:
    """답변 피드백 적재 (👍/👎 + "샘플 등록"). sample_feedback(pending) 에 기록.

    권한: 대화 접근(멤버/owner/read.any) — 발화 권한과 무관(피드백은 열람자도 가능).
    body: {vote: "up"|"down", suggested: bool, nl_question: str, generated_sql?: str}.
    generated_sql 은 코어(record_feedback)가 PII 마스킹 후 저장한다.
    승급(promote)은 별도 관리 콘솔 검수 큐(명시 호출)만 — 본 endpoint 는 적재까지(자동학습 금지).
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return app._json_error("invalid body", 400)
    vote = "down" if str(data.get("vote") or "up").strip().lower() in ("down", "negative", "0", "false") else "up"
    suggested = bool(data.get("suggested"))
    nl_question = str(data.get("nl_question") or "").strip()
    generated_sql = str(data.get("generated_sql") or "")
    # 답변(메시지) 식별자 — (created_by, message_id, message_id_space) 단위 고유 피드백 강제용.
    # message_id = /api/history 가 m["id"] 로 노출하는 표시 store/core 메시지 id. 부재 시 None.
    try:
        message_id = int(data.get("message_id")) if str(data.get("message_id") or "").strip() != "" else None
    except (TypeError, ValueError):
        message_id = None
    # id_space = m["id_space"]("display"|"core") — message_id 숫자가 두 store 공간서 겹쳐도 답변을
    # 명확히 구분(H5(b) 해소). 미지정/비정상은 "display" 로 정규화(대다수 경로).
    message_id_space = "core" if str(data.get("message_id_space") or "").strip().lower() == "core" else "display"
    if not nl_question:
        return app._json_error("nl_question 은 필수입니다.", 400)
    if len(nl_question) > 8000:
        return app._json_error("질문이 너무 깁니다.", 400)
    if len(generated_sql) > 100_000:
        return app._json_error("SQL 본문이 너무 깁니다.", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_can_access_conversation(
            conn, account, cid, "conversation.read.own", "conversation.read.any"
        ):
            return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        # share-visibility-window: bounded 멤버는 가려진 pre-floor 메세지를 샘플/피드백 대상으로
        # 지정할 수 없다(존재 probe 차단). display id-space 하단 경계만 게이트(상단은 post-join tail
        # 모호성 때문에 표시 필터에 위임). core space 는 표시와 별공간이라 스킵.
        if message_id is not None and message_id_space == "display":
            _sf_win = app._resolve_display_window(conn, cid, (account or {}).get("id"))
            if _sf_win == "DENY":
                return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
            if isinstance(_sf_win, dict):
                _sf_floor = _sf_win.get("floor_id")
                if _sf_floor is not None and int(message_id) < int(_sf_floor):
                    return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        # REV-…-item03-security MAJOR-1: 적재 endpoint per-account rate-limit — 미적용 시
        # 열람자가 suggested 피드백을 spam 해 검수 큐를 채워 curator DoS. body-search 와 동형.
        if not app._search_rate_limit_check(
            int(account.get("id") or 0), max_per_min=10, scope=app.RATE_SCOPE_SAMPLE_FEEDBACK,
        ):
            return app._json_rate_limited(
                "피드백 요청이 너무 잦습니다.",
                app._rate_limit_retry_after(int(account.get("id") or 0), app.RATE_SCOPE_SAMPLE_FEEDBACK),
            )
        scope_key = app._conversation_scope_key(conn, cid)
    finally:
        conn.close()

    # 적재는 PG(agent_kb) conn — 코어 정본 modules.sample_feedback.record_feedback.
    from modules import sample_feedback as _sfb
    from shared.db import _pg_connect
    feedback_id: int | None = None
    try:
        # autocommit=False — UPSERT + RETURNING 을 한 트랜잭션으로 묶어 id 회수 정확성 보장.
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("피드백 저장소(PG) 연결 실패", 503)
    try:
        # record_feedback 가 UPSERT(ON CONFLICT (created_by, message_id, message_id_space) … DO UPDATE)
        # RETURNING id 로 적재/갱신된 행 id 직접 반환 — lastval() 은 DO UPDATE 경로 부정확하므로 미사용.
        feedback_id = _sfb.record_feedback(
            pg, scope_key, nl_question, generated_sql,
            vote=vote, suggested=suggested, conversation_id=cid,
            created_by=str((account or {}).get("username") or "") or None,
            message_id=message_id, message_id_space=message_id_space,
        )
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        import sys as _sys
        _sys.stderr.write(f"[ITEM-03] sample-feedback 적재 실패 cid={cid}: {exc}\n")
        return app._json_error("피드백 저장 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass

    # best-effort audit (user endpoint 패턴, fail-open — 적재 성공을 막지 않는다).
    try:
        mconn = app._connect_memory()
        try:
            app.record_audit_event(
                mconn,
                actor=app._build_actor_from_request(request, account, actor_type="account"),
                action="sample.feedback.submit",
                resource_type="sample_feedback",
                resource_id=str(feedback_id) if feedback_id is not None else None,
                change_json={"vote": vote, "suggested": suggested,
                             "scope_key": scope_key, "conversation_id": cid,
                             "has_sql": bool(generated_sql)},
            )
            mconn.commit()
        finally:
            mconn.close()
    except Exception:
        pass

    return JSONResponse({"ok": True, "feedback_id": feedback_id})

@router.post("/api/conversations/{cid}/fix-with-ai")
async def post_fix_with_ai(cid: str, request: Request) -> JSONResponse:
    """ITEM-08 "AI 로 고치기" — 실패한 SQL 결과를 표적 정정(1회 dispatch).

    가드 순서 = post_sample_feedback 동형: _require_account → _account_can_access_conversation
    (미보유 404) → _search_rate_limit_check(429) → scope(발화 권한) → record_audit_event.
    body: {executed_sql: str, error_message: str}. 서버가 정정 지시문을 구성하고 client 입력은
    데이터 인용 블록으로만 삽입(프롬프트 인젝션 방어). 동일 conversation_id 로 기존 /api/ask
    파이프라인에 1회 dispatch — self-reflection(ITEM-07, agent_core 무변경)이 표적 정정을 수행한다.
    응답은 /api/ask 와 동일 result dict(프론트 부분 갱신용).
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return app._json_error("invalid body", 400)
    executed_sql = str(data.get("executed_sql") or "")
    error_message = str(data.get("error_message") or "")
    # 빈 값 거절(400) — 정정 대상이 없으면 의미 없는 full run 방지.
    if not executed_sql.strip() and not error_message.strip():
        return app._json_error("정정할 SQL 또는 오류 정보가 필요합니다.", 400)
    # 과대 입력 거절(400) — 정제 cap 보다 한참 큰 입력은 조기 차단(악의적 페이로드/오용).
    if len(executed_sql) > app._FIX_WITH_AI_SQL_CAP * 4 or len(error_message) > app._FIX_WITH_AI_ERR_CAP * 4:
        return app._json_error("입력이 너무 깁니다.", 400)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        # 대화 접근 가드(미보유 404) — sample-feedback 와 동일 wording.
        if not app._account_can_access_conversation(
            conn, account, cid, "conversation.read.own", "conversation.read.any"
        ):
            return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        # per-account rate-limit(429) — 1회 dispatch 가 full LLM run 을 점유하므로 보수적 상한.
        if not app._search_rate_limit_check(
            int(account.get("id") or 0),
            max_per_min=app._FIX_WITH_AI_RATE_PER_MIN,
            scope=app.RATE_SCOPE_FIX_WITH_AI,
        ):
            return app._json_rate_limited(
                "재수정 요청이 너무 잦습니다.",
                app._rate_limit_retry_after(int(account.get("id") or 0), app.RATE_SCOPE_FIX_WITH_AI),
            )
        # scope: 발화(질의) 권한이 있어야 정정 dispatch 가능(열람자는 불가) — ask 의 actor RBAC 와 정합.
        if not app._account_has_permission(account, "conversation.ask"):
            return app._json_error("이 대화에 발화(질의) 권한이 없습니다.", 403)
        # best-effort audit — 정정 트리거 자체를 기록(LLM 응답 전, fail-open).
        try:
            app.record_audit_event(
                conn,
                actor=app._build_actor_from_request(request, account, actor_type="account"),
                action="conversation.fix_with_ai",
                resource_type="conversation",
                resource_id=str(cid),
                change_json={"conversation_id": cid,
                             "has_sql": bool(executed_sql.strip()),
                             "has_error": bool(error_message.strip())},
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        conn.close()

    # 서버 구성 정정 메시지(client 입력은 nonce-봉인 데이터 블록으로만 삽입 — 프롬프트 인젝션 방어, REV M1).
    import secrets
    fix_message = app._build_fix_with_ai_message(executed_sql, error_message, nonce=secrets.token_hex(8))
    # 동일 conversation_id 로 기존 /api/ask 핸들러에 1회 재dispatch.
    #  - 원본 NL 질문 재전송이 아니라 표적 정정 지시만 보낸다(대화 맥락은 cid 가 보유).
    #  - product/role/allowed_schemas 해석·동시성 슬롯·worker 분기·self-reflection 모두 ask 가 재사용.
    #  - 추가 루프 없음(1회) — 재실패해도 self-reflection 내부 cap(AGENT_SELF_REFLECTION_MAX)이 처리.
    # model 미지정 → ask 가 API_DEFAULT_MODEL 로 채움(정정도 동일 web 기본 모델 사용).
    ask_body = {"message": fix_message, "conversation_id": cid}
    internal_req = app._make_internal_ask_request(request, ask_body)
    return await ask(internal_req)  # feature-0012 P5b: 동일 모듈 내 ask (cross-call)


@router.post("/api/conversations/{cid}/messages/{mid}/edit")
async def post_edit_message(cid: str, mid: int, request: Request) -> JSONResponse:
    """feature-0019 메시지 편집 — 자신이 보낸 user 메시지를 수정.

    body: {mode: 'simple'|'reanswer', new_content: str}.
      - simple   : 제자리 내용 갱신('편집됨' 표식), 재답변 없음, 하위 불변.
      - reanswer : 편집 지점에서 새 브랜치 + /api/ask 재dispatch(형제 버전, ChatGPT식 분기).
    Phase 1 = 1:1 전용(그룹 편집은 Phase 2). authz = 대화 접근 + ask 권한 + 본인 소유(IDOR) + user 메시지.
    가드 순서 = fix-with-ai 동형.
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return app._json_error("invalid body", 400)
    mode = str(data.get("mode") or "").strip()
    new_content = str(data.get("new_content") or "")
    if mode not in ("simple", "reanswer"):
        return app._json_error("mode 는 simple 또는 reanswer 여야 합니다.", 400)
    if not new_content.strip():
        return app._json_error("수정할 내용이 비어 있습니다.", 400)
    if len(new_content) > 100_000:
        return app._json_error("입력이 너무 깁니다.", 400)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_can_access_conversation(
            conn, account, cid, "conversation.read.own", "conversation.read.any"
        ):
            return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        if not app._account_has_permission(account, "conversation.ask"):
            return app._json_error("이 대화에 발화(질의) 권한이 없습니다.", 403)
        # reanswer 모드는 /api/ask 를 재dispatch 해 full LLM run 을 점유하므로 fix-with-ai 와
        # 동일한 보수적 상한(5)을 유지한다. 단 버킷은 자기 scope 로 격리 — 버전 페이징·피드백
        # 같은 이웃 기능의 소비가 편집 예산을 태우던 결함 제거(TASK-20260729T152000-ratelimit-scope).
        if not app._search_rate_limit_check(
            int(account.get("id") or 0),
            max_per_min=app._FIX_WITH_AI_RATE_PER_MIN,
            scope=app.RATE_SCOPE_MESSAGE_EDIT,
        ):
            return app._json_rate_limited(
                "메시지 수정 요청이 너무 잦습니다.",
                app._rate_limit_retry_after(int(account.get("id") or 0), app.RATE_SCOPE_MESSAGE_EDIT),
            )
        # 편집 대상 로드(그룹/1:1 공통) — sender·내용 검증에 선행 필요.
        from shared.db import _pg_connect
        _pg = _pg_connect()
        try:
            disp = app._branch_get_display_message(_pg, cid, mid)
        finally:
            _pg.close()
        if not disp:
            return app._json_error("메시지를 찾을 수 없습니다.", 404)
        if str(disp.get("role") or "").lower() != "user":
            return app._json_error("assistant 메시지는 수정할 수 없습니다.", 400)
        # feature-0019 Phase 2: 대화 유형별 편집 규칙.
        if app._conversation_is_group(cid):
            # 그룹/공유 대화: 단순 수정만(브랜치/재답변은 1:1 전용 — 공유 답변 무결성).
            if mode != "simple":
                return app._json_error("그룹 대화는 단순 수정만 가능합니다.", 400)
            # @assistant 를 호출한(유발한) 메시지는 편집 잠금 — 공유 답변의 전제 변조 차단(REQ-ME-R3).
            try:
                from modules.mentions import message_invokes_assistant as _invokes
                if _invokes(str(disp.get("content") or "")):
                    return app._json_error("@assistant 를 호출한 메시지는 수정할 수 없습니다.", 400)
            except Exception:
                pass
            # IDOR(그룹): 본인이 발신한 메시지만(per-message sender). meta_json.sender_account_id 비교.
            _sender = None
            try:
                _mj = disp.get("meta_json")
                _meta = json.loads(_mj) if isinstance(_mj, str) else (_mj or {})
                _sender = (_meta or {}).get("sender_account_id") if isinstance(_meta, dict) else None
            except Exception:
                _sender = None
            if _sender is None:
                # 발신자 미상(레거시/시스템) → owner 만 허용(보수적 fail-closed).
                if not app._conversation_owned_by_account(conn, cid, int(account["id"])):
                    return app._json_error("본인이 보낸 메시지만 수정할 수 있습니다.", 403)
            elif int(_sender) != int(account["id"]):
                return app._json_error("본인이 보낸 메시지만 수정할 수 있습니다.", 403)
        else:
            # 1:1 대화: owner = 발신자(IDOR). simple/reanswer 모두 허용.
            if not app._conversation_owned_by_account(conn, cid, int(account["id"])):
                return app._json_error("본인이 보낸 메시지만 수정할 수 있습니다.", 403)
        # best-effort audit (편집 트리거 기록).
        try:
            app.record_audit_event(
                conn, actor=app._build_actor_from_request(request, account, actor_type="account"),
                action="conversation.message_edit", resource_type="conversation", resource_id=str(cid),
                change_json={"conversation_id": cid, "message_id": int(mid), "mode": mode},
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        conn.close()

    if mode == "simple":
        try:
            app._branch_simple_edit(cid, disp, new_content)
        except Exception:
            logging.getLogger(__name__).warning("branch simple edit failed (cid=%s mid=%s)", cid, mid, exc_info=True)
            return app._json_error("수정 처리 중 오류가 발생했습니다.", 500)
        return JSONResponse({"ok": True, "mode": "simple", "message_id": int(mid)})

    # reanswer: 브랜치 준비(active_leaf = M.parent) 후 동일 conversation_id 로 /api/ask 재dispatch.
    #   워커가 새 user 메시지(M 형제)+답변을 활성 브랜치에 체인(feature-0002 검증된 write 경로).
    try:
        _prior = app._branch_reanswer_setup(cid, disp)
    except Exception:
        logging.getLogger(__name__).warning("branch reanswer setup failed (cid=%s mid=%s)", cid, mid, exc_info=True)
        return app._json_error("재답변 준비 중 오류가 발생했습니다.", 500)
    ask_body = {"message": new_content, "conversation_id": cid}
    # feature-0019 reanswer-model-select: 재답변은 정상 /api/ask 와 동일하게 사용자가 현재
    # 선택한 model + 추론 강도(reasoning_level)로 재요청한다. 클라이언트가 전달하면 forward,
    # 부재 시 ask() 가 API_DEFAULT_MODEL(claude-haiku-4) / 모델 config 기본 추론으로 폴백(구
    # 클라이언트 하위호환). model 형식·allowlist·reasoning 정규화는 ask() 가 재검증하므로 여기선
    # 원문만 전달한다(부재 필드를 기본값으로 강제 대입하지 않음 — ask() reasoning override 계약 보존).
    _sel_model = str(data.get("model") or "").strip()
    if _sel_model:
        ask_body["model"] = _sel_model
    _sel_reasoning = data.get("reasoning_level")
    if _sel_reasoning not in (None, ""):
        ask_body["reasoning_level"] = _sel_reasoning
    internal_req = app._make_internal_ask_request(request, ask_body)
    try:
        resp = await ask(internal_req)
    except Exception:
        # /api/ask 재dispatch 가 raise(워커 오류·disconnect 등) → active_leaf 가 M.parent 에 고착돼
        # 대화 tail 이 사라지므로 편집 직전 상태로 보상 복원(SEC MAJOR #2).
        app._branch_restore_state(cid, _prior)
        logging.getLogger(__name__).warning("reanswer ask dispatch raised (cid=%s mid=%s)", cid, mid, exc_info=True)
        return app._json_error("재답변 생성에 실패했습니다. 잠시 후 다시 시도하세요.", 500)
    # ask() 가 검증 실패(400 — 예: forward 된 model 이 allowlist 위반)·쿼터(429)를 **예외가 아닌
    # non-2xx JSONResponse** 로 반환하면, 이는 ask() 상단 게이트(= 새 user 메시지 저장 이전)에서
    # 나온 것이라 active_leaf 가 M.parent 에 고착(tail 은닉)된다 → 예외 경로와 동일하게 편집 직전
    # 브랜치 상태로 보상 복원한다. ask() 계약상 message 저장 이후의 실패는 200+error 본문으로 오므로
    # (위 except 주석 참조), status>=400 은 저장-전 게이트 실패와 1:1 대응 — 저장된 재답변을 잘못
    # 되돌리지 않는다. (reanswer-model-select 가 model forward 로 400 도달 경로를 신설했으므로 이
    # 보상을 함께 확장 — REV-20260724T0641-reanswer-model-select MINOR.)
    try:
        _status = int(getattr(resp, "status_code", 200) or 200)
    except Exception:
        _status = 200
    if _status >= 400:
        app._branch_restore_state(cid, _prior)
        logging.getLogger(__name__).warning(
            "reanswer ask returned %s (cid=%s mid=%s) — 편집 직전 브랜치 상태 복원", _status, cid, mid)
    return resp


@router.post("/api/conversations/{cid}/branch/switch")
async def post_branch_switch(cid: str, request: Request) -> JSONResponse:
    """feature-0019 브랜치 전환(페이징) — 편집된 메시지의 다른 버전으로 활성 브랜치 이동.

    body: {message_id: int} — 전환할 버전(표시 user 메시지 id). 두 store 의 active_leaf 를 그
    브랜치 leaf 로 이동한다(화면·LLM recall 정합). Phase 1 = 1:1 전용, 본인 소유.
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return app._json_error("invalid body", 400)
    try:
        target_id = int(data.get("message_id"))
    except Exception:
        return app._json_error("message_id(정수)가 필요합니다.", 400)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_can_access_conversation(
            conn, account, cid, "conversation.read.own", "conversation.read.any"
        ):
            return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        if app._conversation_is_group(cid):
            return app._json_error("그룹 대화는 브랜치 전환을 지원하지 않습니다.", 400)
        if not app._conversation_owned_by_account(conn, cid, int(account["id"])):
            return app._json_error("본인 대화만 전환할 수 있습니다.", 403)
        # SEC MINOR-C: 재귀 CTE(_branch_leaf_of/_branch_active_display_ids) 무제한 유발 방지.
        # TASK-20260729T152000-ratelimit-scope: edit(LLM run 가능)과 같은 버킷·같은 상한(5)을
        # 쓰던 것을 페이징 전용 scope + 상한으로 분리한다. 본 endpoint 는 DB 읽기 4쿼리 +
        # UPDATE 1회(실측 p50 8ms)로 끝나는 네비게이션 op 라 LLM 비용 등급이 아니다.
        # 스크립트 연사 차단이라는 SEC MINOR-C 의 목적은 60/min 으로도 그대로 유지된다.
        if not app._search_rate_limit_check(
            int(account.get("id") or 0),
            max_per_min=app._BRANCH_NAV_RATE_PER_MIN,
            scope=app.RATE_SCOPE_BRANCH_NAV,
        ):
            return app._json_rate_limited(
                "버전 전환 요청이 너무 잦습니다.",
                app._rate_limit_retry_after(int(account.get("id") or 0), app.RATE_SCOPE_BRANCH_NAV),
            )
    finally:
        conn.close()

    try:
        ok = app._branch_switch(cid, target_id)
    except Exception:
        logging.getLogger(__name__).warning("branch switch failed (cid=%s mid=%s)", cid, target_id, exc_info=True)
        return app._json_error("브랜치 전환 중 오류가 발생했습니다.", 500)
    if not ok:
        return app._json_error("전환할 버전을 찾을 수 없습니다.", 404)
    return JSONResponse({"ok": True, "active_version_id": int(target_id)})


@router.get("/api/conversations/{cid}/shares")
def list_conversation_shares(cid: str, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """해당 대화의 share 목록. owner/`.any` 감사자는 전체, 그 외(멤버·API 토큰)는 **본인 생성분만**.

    보안(SEC-20260723 REV-share-window): share 토큰은 anonymous 접근을 부여하는 민감 자격이다.
    이전엔 `read.own` 멤버도 **전** share 토큰을 볼 수 있어, 윈도우 제한 멤버가 owner 의
    `scope_mode="full"` share 토큰을 얻어 자기 가시성 윈도우를 escape할 수 있었다(SECURITY.md
    §21.4/§21.6 위반; API 토큰 멤버로도 악용). 수정: owner(또는 감사용 `.any`)가 아니면 반환
    목록을 `CreatedBy = 본인`으로 필터 — 타인(owner 포함) 토큰은 숨기되(escape 봉인) 비-owner
    멤버가 백엔드 허용대로 만든 view-only 자기 공유의 목록/취소 관리는 보존한다(REV FINDING-1).
    """
    if not app._account_can_access_conversation(
        conn,
        account,
        cid,
        "conversation.read.own",
        "conversation.read.any",
    ):
        return app._json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
    # owner/`.any` 감사자만 전체 열람. 그 외(멤버·토큰)는 본인 생성 share 로 한정(escape 봉인).
    is_owner_or_auditor = bool(
        app._conversation_owned_by_account(conn, cid, int(account["id"]))
        or app._account_has_permission(account, "conversation.read.any")
    )
    cur = conn.cursor(dictionary=True)
    try:
        if is_owner_or_auditor:
            cur.execute(
                """
SELECT Id, Token, ScopeMode, AnchorMessageId, CreatedBy, CreatedAt,
       RevokedAt, RevokedBy, ViewCount, LastViewedAt, ExpiresAt,
       (ExpiresAt IS NOT NULL AND ExpiresAt <= NOW()) AS IsExpired
FROM WebConversationShares
WHERE ConversationId = %s
ORDER BY CreatedAt DESC, Id DESC
                """,
                (cid,),
            )
        else:
            cur.execute(
                """
SELECT Id, Token, ScopeMode, AnchorMessageId, CreatedBy, CreatedAt,
       RevokedAt, RevokedBy, ViewCount, LastViewedAt, ExpiresAt,
       (ExpiresAt IS NOT NULL AND ExpiresAt <= NOW()) AS IsExpired
FROM WebConversationShares
WHERE ConversationId = %s AND CreatedBy = %s
ORDER BY CreatedAt DESC, Id DESC
                """,
                (cid, int(account["id"])),
            )
        rows = cur.fetchall() or []
    finally:
        cur.close()
    items = []
    for row in rows:
        created_at = row.get("CreatedAt")
        revoked_at = row.get("RevokedAt")
        last_viewed_at = row.get("LastViewedAt")
        expires_at = row.get("ExpiresAt")
        # TASK-20260619T012028-share-link-expiry: 만료는 DB NOW() 평가(IsExpired)로 판정.
        is_revoked = row.get("RevokedAt") is not None
        is_expired = bool(row.get("IsExpired"))
        items.append(
            {
                "id": int(row.get("Id") or 0),
                "token": str(row.get("Token") or ""),
                "scope_mode": str(row.get("ScopeMode") or "full"),
                "anchor_message_id": int(row["AnchorMessageId"]) if row.get("AnchorMessageId") is not None else None,
                "created_by": int(row.get("CreatedBy") or 0),
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else (str(created_at) if created_at else None),
                "revoked_at": revoked_at.isoformat() if hasattr(revoked_at, "isoformat") else (str(revoked_at) if revoked_at else None),
                "revoked_by": int(row["RevokedBy"]) if row.get("RevokedBy") is not None else None,
                "view_count": int(row.get("ViewCount") or 0),
                "last_viewed_at": last_viewed_at.isoformat() if hasattr(last_viewed_at, "isoformat") else (str(last_viewed_at) if last_viewed_at else None),
                "expires_at": expires_at.isoformat() if hasattr(expires_at, "isoformat") else (str(expires_at) if expires_at else None),
                "is_expired": is_expired,
                "url": f"/share/{row.get('Token')}",
                # is_active = 활성(취소 안 됨 + 만료 안 됨). revoke 버튼 노출 조건.
                "is_active": (not is_revoked) and (not is_expired),
                "is_revoked": is_revoked,
            }
        )
    return JSONResponse({"items": items})

@router.post("/api/conversations/{cid}/attachments")
async def upload_conversation_attachment(
    cid: str,
    request: Request,
    file: UploadFile = File(...),
) -> JSONResponse:
    """첨부 multipart upload (BRIEFING §5.4 row 1).

    권한: `conversation.attachment.upload.{own,any}` + 대상 conv 접근 권한.
    검증: D7 서비스 자체 kind 추론(확장자 우선) + D8 size cap (per_file/conv/account) + D12 HMAC.
    부작용: MinIO put_object + WebConversationAttachments INSERT + audit
    `attachment.upload` dispatch.

    Response: `{id, kind, signed_url (사내망 다운로드 전용), size, sha256, status}`
    """
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)

    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        # RBAC: upload.{own,any} + 대상 conv 접근.
        if not app._account_can_access_conversation(
            conn,
            account,
            cid,
            "conversation.attachment.upload.own",
            "conversation.attachment.upload.any",
        ):
            return app._json_error("이 대화에 첨부를 업로드할 권한이 없습니다.", 403)

        # D7 — 서비스 자체 kind 추론 (확장자 우선, MIME 힌트 fallback).
        # 클라이언트 MIME 을 신뢰하지 않으며 확장자 + MIME 조합으로 판단한다.
        mime_type = (file.content_type or "").strip().lower()
        filename = (file.filename or "unnamed").strip()
        kind = app._infer_kind(filename, mime_type)

        # 본문 read — D8 size cap pre-check 위해 in-memory read.
        # Phase 11 (ingest pipeline) 진입 시 streaming upload + spool-to-disk 옵션 검토.
        try:
            body_bytes = await file.read()
        except Exception as exc:
            return app._json_error(f"첨부 본문 read 실패: {exc}", 400)
        if not body_bytes:
            return app._json_error("첨부 파일이 비어 있습니다.", 400)

        # D8 size cap (per_file / per_conv / per_account).
        ok, reason = app._check_attachment_size_caps(
            conn,
            account_id=int(account["id"]),
            conversation_id=cid,
            new_size_bytes=len(body_bytes),
        )
        if not ok:
            return app._json_error(reason, 413)

        # D12 categorical 메타.
        # filename 은 위 kind 추론 단계에서 이미 추출.
        filename_hmac = app._hmac_filename(filename)
        ext_bucket = app._extension_bucket(filename)
        size_bucket = app._size_bucket(len(body_bytes))
        sha256_hex = hashlib.sha256(body_bytes).hexdigest()

        # REQ-20260713-attach-user-version: 같은 파일명 재업로드 → 버전 체인 편입.
        # 대화 내 동일 파일명·동일 account 의 최신 버전(head)을 찾아 sha256 대조:
        #   - 내용 동일(해시 일치) → 새 row/MinIO 미생성, 기존 최신 버전 재사용(멱등).
        #     "완전히 같은 파일이 아니라면 버전을 올린다"(사용자 요청) — 동일하면 버전 불변.
        #   - 내용 다름 → 같은 root 체인의 새 버전(CreatedByRole='user')으로 INSERT + 직전 supersede.
        # 체인 스코프 = (conversation_id, account_id, filename) — cross-account/conv 혼입 차단(IDOR).
        prior_att = app._find_latest_same_name_attachment(conn, cid, int(account["id"]), filename)
        version_root_id: int | None = None
        version_number = 1
        version_meta: dict | None = None
        if prior_att:
            if str(prior_att.get("Sha256") or "") == sha256_hex:
                # 내용 동일(멱등) — 기존 최신 버전 재사용. 새 객체/row 미생성.
                _reuse_signed: str | None = None
                if not app._account_is_pending(account):
                    try:
                        _reuse_signed = storage_minio.generate_presigned_get(
                            str(prior_att.get("ObjectKey") or ""),
                            response_filename=filename,
                        )
                    except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                        _reuse_signed = None
                _reuse_payload = app._serialize_attachment_for_api(
                    prior_att, include_signed_url=bool(_reuse_signed), signed_url=_reuse_signed)
                _reuse_payload["reused_existing_version"] = True
                return JSONResponse(_reuse_payload)
            # 내용 다름 — 새 버전. root = prior 의 root(없으면 prior 자신). 체인 MAX(VersionNumber)+1.
            version_root_id = int(prior_att.get("RootAttachmentId") or 0) or int(prior_att.get("Id") or 0)
            _vcur = conn.cursor()
            try:
                _vcur.execute(
                    """
                    SELECT COALESCE(MAX(VersionNumber), 1)
                    FROM WebConversationAttachments
                    WHERE RootAttachmentId = %s OR Id = %s
                    """,
                    (version_root_id, version_root_id),
                )
                _vrow = _vcur.fetchone()
                version_number = int((_vrow[0] if _vrow else 1) or 1) + 1
            finally:
                _vcur.close()
            version_meta = {
                "version_of": int(prior_att.get("Id") or 0),
                "from_version": int(prior_att.get("VersionNumber") or 1),
                "to_version": version_number,
            }
            # 변경점 diff(텍스트 계열만) — 이전 버전 MinIO 본문 대비. fail-soft(diff 실패해도 버전은 생성).
            _prev_kind = str(prior_att.get("Kind") or "")
            if kind in ("text", "csv") and _prev_kind in ("text", "csv"):
                try:
                    _prev_bytes = storage_minio.get_object_bytes(str(prior_att.get("ObjectKey") or ""))
                    version_meta["version_diff"] = app._compute_version_diff(
                        _prev_bytes.decode("utf-8", "replace"),
                        body_bytes.decode("utf-8", "replace"),
                        prev_version=int(prior_att.get("VersionNumber") or 1),
                        new_version=version_number,
                        filename=filename,
                    )
                except Exception:
                    logging.getLogger(__name__).warning(
                        "upload_conversation_attachment: version diff compute failed (prior=%s) — version without diff",
                        prior_att.get("Id"), exc_info=True)

        # ObjectKey: <cid>/<attachment_uuid>/<safe_filename>.
        import uuid as _uuid
        attachment_uuid = str(_uuid.uuid4())
        object_key = storage_minio.make_object_key(cid, attachment_uuid, filename)

        # INSERT row first (uploaded 상태) — MinIO put 실패 시 rollback.
        # REQ-20260713: 버전 컬럼을 명시 INSERT. prior 없음 → RootAttachmentId=NULL,
        # VersionNumber=1, MetaJson=NULL, CreatedByRole='user' — 기존 스키마 default 와 byte-동치.
        # prior 있고 내용 다름 → root/version/version_meta 반영(사용자 버전).
        _ATTACH_INSERT_SQL = """
                INSERT INTO WebConversationAttachments (
                    ConversationId, AccountId, ObjectKey, OriginalFilename,
                    FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                    UploadStatus, MetaJson, RootAttachmentId, VersionNumber, CreatedByRole
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploaded', %s, %s, %s, 'user')
                """

        def _insert_attachment_row(_ver: int) -> int:
            _meta = None
            if version_meta is not None:
                version_meta["to_version"] = int(_ver)
                if isinstance(version_meta.get("version_diff"), dict):
                    version_meta["version_diff"]["to_version"] = int(_ver)
                _meta = json.dumps(version_meta)
            _c = conn.cursor()
            try:
                _c.execute(_ATTACH_INSERT_SQL, (
                    cid, int(account["id"]), object_key, filename, filename_hmac,
                    mime_type, len(body_bytes), size_bucket, sha256_hex, kind,
                    _meta, version_root_id, int(_ver),
                ))
                return int(_c.lastrowid or 0)
            finally:
                _c.close()

        try:
            attachment_id = _insert_attachment_row(version_number)
        except Exception:
            # REQ-20260713: 동시 재업로드가 같은 (root, version) 을 선점하면 UNIQUE(UQ_WCA_VersionChain)
            # 위반 → 버전 케이스만 체인 MAX+1 재계산 후 1회 재시도(assistant materialize 경로와 대칭, raw 500 회피).
            # 표준 업로드(version_root_id 없음)의 실패는 그대로 아래 rollback+500 으로 처리.
            attachment_id = 0
            if version_root_id:
                logging.getLogger(__name__).warning(
                    "upload_conversation_attachment: version INSERT race (root=%s, v=%s) — recompute+retry",
                    version_root_id, version_number, exc_info=True)
                try:
                    _rc = conn.cursor()
                    try:
                        _rc.execute(
                            "SELECT COALESCE(MAX(VersionNumber), 1) FROM WebConversationAttachments "
                            "WHERE RootAttachmentId = %s OR Id = %s",
                            (version_root_id, version_root_id),
                        )
                        _rr = _rc.fetchone()
                        version_number = int((_rr[0] if _rr else 1) or 1) + 1
                    finally:
                        _rc.close()
                    attachment_id = _insert_attachment_row(version_number)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "upload_conversation_attachment: version INSERT retry failed (root=%s) — abort",
                        version_root_id, exc_info=True)
                    attachment_id = 0
        if not attachment_id:
            try:
                conn.rollback()
            except Exception:
                pass
            return app._json_error("첨부 row 생성 실패", 500)

        # MinIO put — D13 정합 (signed URL 송신 금지, server-side write).
        try:
            storage_minio.put_object_bytes(
                object_key,
                body_bytes,
                content_type=mime_type,
                metadata={
                    "attachment-id": str(attachment_id),
                    "conversation-id": cid,
                    "uploader-account-id": str(account["id"]),
                    "filename-hmac": filename_hmac,
                },
            )
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError) as exc:
            try:
                # MinIO put 실패 → row 즉시 hard-delete (orphan 방지).
                _cur = conn.cursor()
                _cur.execute(
                    "DELETE FROM WebConversationAttachments WHERE Id = %s",
                    (attachment_id,),
                )
                _cur.close()
                conn.commit()
            except Exception:
                pass
            return app._json_error(f"MinIO 업로드 실패: {exc}", 502)

        try:
            conn.commit()
        except Exception:
            pass

        # REQ-20260713: 새 버전이면 직전 버전들을 superseded 마킹 — 목록엔 최신만 노출.
        # WHERE VersionNumber < new 로 둬, 직전 supersede 가 일부 실패해 비-superseded 구버전이
        # 남아도 다음 업로드가 자가 정정(더 옛 버전 전부 끔) — 어시스턴트 materialize 경로와 동형.
        if version_root_id:
            _scur = conn.cursor()
            try:
                _scur.execute(
                    """
                    UPDATE WebConversationAttachments
                    SET SupersededAt = UTC_TIMESTAMP(6)
                    WHERE (RootAttachmentId = %s OR Id = %s)
                      AND VersionNumber < %s AND SupersededAt IS NULL AND DeletedAt IS NULL
                    """,
                    (version_root_id, version_root_id, version_number),
                )
                conn.commit()
            except Exception:
                logging.getLogger(__name__).warning(
                    "upload_conversation_attachment: supersede prior versions failed (root=%s, v=%s)",
                    version_root_id, version_number, exc_info=True)
            finally:
                _scur.close()

        # TASK-0277: dual-write — 업로드 직후 MySQL 상태를 PG core_attachments 로 미러(flag-gated, fail-soft).
        # REQ-20260713: 새 버전이면 supersede 된 이전 버전(체인 전체)도 함께 미러 — PG 목록/버전 정합.
        try:
            from web.modules import attachment_pg_mirror as _apm
            _mirror_ids = [attachment_id]
            if version_root_id:
                _ccur = conn.cursor()
                try:
                    _ccur.execute(
                        "SELECT Id FROM WebConversationAttachments WHERE RootAttachmentId = %s OR Id = %s",
                        (version_root_id, version_root_id),
                    )
                    _mirror_ids = sorted({attachment_id} | {int(r[0]) for r in (_ccur.fetchall() or [])})
                finally:
                    _ccur.close()
            _apm.mirror_attachments(conn, _mirror_ids)
        except Exception:
            pass

        # audit dispatch — D12 raw filename / bytes 절대 제외.
        attachment_row = app._load_attachment_row(conn, attachment_id)
        try:
            app._audit_user_action(
                conn,
                request,
                account,
                action="attachment.upload",
                resource_type="attachment",
                resource_id=str(attachment_id),
                request_ctx=app._serialize_attachment_for_audit(attachment_row),
            )
        except Exception:
            # fail-open: attachment.upload audit dispatch 실패는 업로드 응답을 막지 않으나 가시화.
            logging.getLogger(__name__).warning(
                "upload_conversation_attachment: upload audit dispatch failed (attachment_id=%s)",
                attachment_id, exc_info=True,
            )

        # TASK-0107 Phase A.2 (수정): csv/xlsx kind 면 동기 ingest.
        # 업로드 응답 전에 sandbox schema 생성 + table INSERT + MetaJson 갱신 완료.
        # ingest 결과는 LLM prompt 의 ATTACHED FILES section 에서 즉시 활용된다.
        if kind in ("csv", "xlsx"):
            app._ingest_attachment_background(
                attachment_id=attachment_id,
                conversation_id=cid,
                object_key=object_key,
                kind=kind,
            )
            # 동기 ingest 후 최신 row 재조회 (UploadStatus='ingested' 반영)
            try:
                refreshed = app._load_attachment_row(conn, attachment_id)
                if refreshed:
                    attachment_row = refreshed
            except Exception:
                # best-effort: ingest 후 row 재조회 실패는 응답을 막지 않는다 (기존 row 사용).
                logging.getLogger(__name__).warning(
                    "upload_conversation_attachment: post-ingest row refresh failed (attachment_id=%s)",
                    attachment_id, exc_info=True,
                )

        # signed URL 발급 (사내망 다운로드 전용 — D13). pending 은 발급 안 함 (D21).
        signed_url: str | None = None
        if not app._account_is_pending(account):
            try:
                signed_url = storage_minio.generate_presigned_get(
                    object_key,
                    response_filename=filename,
                )
            except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                signed_url = None

        payload = app._serialize_attachment_for_api(
            attachment_row,
            include_signed_url=bool(signed_url),
            signed_url=signed_url,
        )
        return JSONResponse(payload)
    finally:
        conn.close()

def _natural_filename_key(name: Any) -> tuple:
    """파일명을 '사람이 읽는 순서'로 비교하는 정렬 키 (숫자 구간은 수치 비교).

    사전순만 쓰면 `..._02_...` 다음에 `..._10_...` 이 아니라 `..._100_...` 이 오고
    (`"10" < "2"`), 실제 첨부는 `01_`, `02_`, `10_` 처럼 자리수가 섞인 접두를 달고
    올라온다 — 목록이 이름순인데도 사용자가 기대한 순서가 아니게 된다. 숫자 조각은
    int 로, 그 밖은 casefold 문자열로 비교한다(대소문자만 다른 이름이 갈라지지 않게).
    한글은 완성형 코드포인트가 곧 가나다순이라 별도 collation 없이 정합한다.

    DB collation 이 아니라 파이썬에서 정하는 이유: 첨부 목록의 read 경로가 MySQL 정본과
    PG mirror 두 벌이라(§attachment_pg_mirror) `ORDER BY` 에 맡기면 두 경로의 collation
    차이가 그대로 순서 차이로 새어 나온다. 정렬 규칙을 한 함수로 모으면 어느 경로로
    읽히든 같은 순서가 나온다.
    """
    import re as _re
    parts = _re.split(r"(\d+)", str(name or ""))
    key: list[tuple] = []
    for idx, part in enumerate(parts):
        if idx % 2:                      # 정규식 캡처 그룹 = 숫자 조각
            # 파이썬은 4,300 자리를 넘는 int↔str 변환을 거부한다(CVE-2020-10735 완화).
            # 파일명 컬럼이 255자라 정상 경로에서는 닿지 않지만, legacy·malformed 행 하나가
            # 목록·휴지통·일괄 다운로드를 통째로 500 으로 떨어뜨리는 것은 정렬이 감수할 위험이
            # 아니다 — 변환 불가한 초장문 숫자는 "아주 큰 수"(inf)로 두고 자기들끼리는 문자열로
            # 가른다. 0 으로 강등하면 4,300 자리 숫자가 `1` 보다 앞에 서는 거짓 순서가 된다.
            key.append((0, int(part), "") if len(part) <= 4_000 else (0, float("inf"), part))
        elif part:
            key.append((1, 0, part.casefold()))
    return tuple(key)


def _sort_attachment_rows_by_name(rows: list) -> list:
    """첨부 행을 파일명 순으로 정렬한다 (동명이인은 버전 → id 로 결정적 tie-break).

    행은 MySQL(dictionary cursor)·PG mirror(alias 로 같은 키) 양쪽 모두 PascalCase 키를
    쓴다 — `_PG_ATTACH_SELECT` 가 `original_filename AS "OriginalFilename"` 으로 맞춰 둔
    덕에 한 함수가 두 경로를 모두 받는다.
    """
    def _key(r):
        d = r if isinstance(r, dict) else dict(r)
        # 키 이름은 PascalCase 가 계약이지만, 어느 read 경로가 snake_case 로 바뀌어도 정렬이
        # **조용히 무의미해지지 않게**(전부 빈 이름 → 원래 순서 유지) 두 표기를 모두 받는다.
        name = d.get("OriginalFilename") or d.get("original_filename") or ""
        return (
            _natural_filename_key(name),
            str(name),                                   # casefold 동률(A.sql vs a.sql) 안정화
            int(d.get("VersionNumber") or d.get("version_number") or 1),
            int(d.get("Id") or d.get("id") or 0),
        )
    return sorted(rows, key=_key)


def _sort_attachment_rows_for_bulk(rows: list) -> list:
    """일괄 다운로드용 정렬 — 목록 패널과 같은 이름순, 단 버전 체인은 한 덩어리로 유지.

    화면에서 이름순으로 본 것을 ZIP·개별 저장 목록에서 업로드 순으로 다시 만나면 같은
    대화의 같은 첨부인데 순서가 두 벌이 된다. 그렇다고 `scope=all` 에서 정렬 키를 행별
    이름으로 잡으면 AI 편집으로 이름이 바뀐 버전이 제 체인에서 떨어져 나간다 — 그래서
    그룹(root) 사이만 그 체인의 **최신 이름**(목록 패널에 보이는 이름)으로 줄 세우고,
    그룹 안은 `VersionNumber` ASC 를 유지한다.
    """
    def _root_of(r) -> int:
        return int(r.get("RootAttachmentId") or r.get("Id") or 0)

    chain_name: dict[int, tuple[int, str]] = {}
    for r in rows:
        root = _root_of(r)
        ver = int(r.get("VersionNumber") or 1)
        if ver >= chain_name.get(root, (0, ""))[0]:
            chain_name[root] = (ver, str(r.get("OriginalFilename") or ""))

    def _key(r):
        name = chain_name.get(_root_of(r), (0, ""))[1]
        return (
            _natural_filename_key(name),
            name,
            _root_of(r),
            int(r.get("VersionNumber") or 1),
            int(r.get("Id") or 0),
        )
    return sorted(rows, key=_key)


@router.get("/api/conversations/{cid}/attachments")
def list_conversation_attachments(cid: str, request: Request, state: str = "active", account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """대화의 첨부 목록. 권한: read.{own,any}.

    - `state=active`(기본) — 현행 계약 그대로: 미삭제 × 최신 버전만.
    - `state=deleted` — REQ-20260806-attach-manage 휴지통. soft-delete 되었으나 아직
      reconciliation worker 가 실 객체를 지우지 않은 행(`UploadStatus <> 'deleted'`)만
      VersionNumber 를 포함해 반환한다. 각 항목의 `restorable_until` 로 남은 복구
      기간이 드러난다(`_serialize_attachment_for_api` 가 계산).
    """
    state_norm = str(state or "active").strip().lower()
    if state_norm not in ("active", "deleted"):
        return app._json_error("state 는 active 또는 deleted 여야 합니다.", 400)

    if not app._account_can_access_conversation(
        conn,
        account,
        cid,
        "conversation.attachment.read.own",
        "conversation.attachment.read.any",
    ):
        return app._json_error("이 대화의 첨부를 조회할 권한이 없습니다.", 403)

    if state_norm == "deleted":
        # 휴지통은 PG mirror read 경로가 없다(mirror helper 는 active 전용) — 첨부 정본인
        # MySQL 을 직접 읽는다. 최신 버전만이 아니라 삭제된 **모든 버전**을 보여야
        # "이 버전만 삭제" 를 되돌릴 수 있다.
        return _list_deleted_conversation_attachments(conn, cid, account)

    # TASK-0277: read cutover — PG 우선(권한은 위 _account_can_access_conversation 로 이미 게이트),
    # PG read 실패 시 MySQL 폴백. PG helper 의 WHERE 는 MySQL 판과 동형(최신·미삭제).
    rows = None
    try:
        from web.modules import attachment_pg_mirror as _apm
        if _apm.read_pg_enabled():
            rows = _apm.pg_list_conversation_attachments(cid)
    except Exception:
        rows = None
        logging.getLogger(__name__).warning(
            "list_conversation_attachments: PG read failed → MySQL fallback (cid=%s)", cid, exc_info=True)
    if rows is None:
        cur = conn.cursor(dictionary=True)
        try:
            # TASK-0274: 버전 체인의 최신 버전만 목록에 노출(SupersededAt IS NULL).
            # 구버전은 /api/attachments/{id}/versions 로 조회. 기존 단일 첨부는
            # SupersededAt NULL + VersionNumber=1 이라 동작 동일(하위호환).
            cur.execute(
                """
                SELECT
                    Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                    FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                    UploadStatus, AttachmentDerivedMessages, CreatedAt, DeletedAt,
                    DeletePending, DeleteReason, MetaJson,
                    RootAttachmentId, VersionNumber, CreatedByRole, SupersededAt
                FROM WebConversationAttachments
                WHERE ConversationId = %s AND DeletedAt IS NULL AND SupersededAt IS NULL
                ORDER BY Id ASC
                """,
                (cid,),
            )
            rows = cur.fetchall() or []
        finally:
            cur.close()

    # 표시 순서 = 파일명 순(REQ-20260813-attach-name-sort). 종전에는 업로드 순(Id ASC)이라
    # 같은 작업의 `01_`~`09_` 파일이 올린 차례대로 흩어져, 사용자가 이름으로 찾으려면 목록
    # 전체를 훑어야 했다. 정렬은 두 read 경로(MySQL 정본·PG mirror)가 합류한 **뒤** 한 번만
    # 적용해 경로별 collation 차이가 순서로 새지 않게 한다.
    rows = _sort_attachment_rows_by_name(list(rows or []))

    # ② TASK-0285: 각 첨부의 버전 체인 길이(version_count) + AI 수정본 개수(ai_version_count)를
    # 집계해 목록에 표면화한다. 목록 SQL 은 최신 버전만 노출(SupersededAt IS NULL)하므로, 같은
    # 대화의 전체(미삭제) 버전에서 root 별 카운트를 한 번의 GROUP BY 로 구한다(N+1 회피). 첨부
    # 정본은 MySQL(dual-write, TASK-0279) 이라 conn(MySQL) 집계가 정확. fail-soft — 집계 실패는
    # 목록 자체를 막지 않는다(version_count 필드만 생략).
    version_counts: dict[int, dict[str, int]] = {}
    try:
        vcur = conn.cursor()
        try:
            vcur.execute(
                """
                SELECT COALESCE(RootAttachmentId, Id) AS RootId,
                       COUNT(*) AS Cnt,
                       SUM(CASE WHEN CreatedByRole = 'assistant' THEN 1 ELSE 0 END) AS AiCnt
                FROM WebConversationAttachments
                WHERE ConversationId = %s AND DeletedAt IS NULL
                GROUP BY COALESCE(RootAttachmentId, Id)
                """,
                (cid,),
            )
            for vr in (vcur.fetchall() or []):
                if vr and vr[0] is not None:
                    version_counts[int(vr[0])] = {
                        "count": int(vr[1] or 1),
                        "ai_count": int(vr[2] or 0),
                    }
        finally:
            vcur.close()
    except Exception:
        version_counts = {}

    # REQ-20260806-attach-manage: 삭제 어포던스 표시 여부를 서버가 계산해 내린다 —
    # 표시 판정과 집행 판정이 같은 술어를 쓰도록(§16.7 G6). 프론트가 소유권을 따로
    # 추정하면 두 벌이 어긋나 "보이는데 404" 또는 "숨겨졌는데 권한 있음" 이 된다.
    _gate = app._manage_gate_for_conversation(conn, account, cid)
    results = []
    for row in rows:
        ser = app._serialize_attachment_for_api(dict(row))
        _vc = version_counts.get(int(ser.get("root_attachment_id") or ser.get("id") or 0))
        if _vc:
            ser["version_count"] = _vc["count"]
            ser["ai_version_count"] = _vc["ai_count"]
        ser["can_manage"] = bool(_gate(dict(row)))
        results.append(ser)
    return JSONResponse({"attachments": results})


def _list_deleted_conversation_attachments(conn, cid: str, account=None) -> JSONResponse:
    """REQ-20260806-attach-manage: 휴지통 목록 (사용자가 삭제한, 실 객체 잔존분).

    첨부 정본은 MySQL(dual-write, TASK-0279). 두 가지를 제외한다 — 되살릴 수 없는
    항목을 휴지통에 보이면 사용자는 복구 가능하다고 믿는다:
      - `UploadStatus='deleted'` — worker 가 객체까지 지운 종착 상태.
      - `DeleteReason <> 'user'` — `conv_soft`(대화 삭제 cascade)·`admin_purge`/`legal`
        은 이 경로의 복구 대상이 아니다(`_is_restorable` 과 같은 경계).
    """
    from routers import attachments as _att
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT
                Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                UploadStatus, AttachmentDerivedMessages, CreatedAt, DeletedAt,
                DeletePending, DeleteReason, MetaJson,
                RootAttachmentId, VersionNumber, CreatedByRole, SupersededAt
            FROM WebConversationAttachments
            WHERE ConversationId = %s
              AND DeletePending = 1
              AND DeleteReason = 'user'
              AND UploadStatus <> 'deleted'
              AND DeletedAt > UTC_TIMESTAMP(6) - INTERVAL %s DAY
            ORDER BY DeletedAt DESC, Id DESC
            LIMIT 200
            """,
            (cid, _att._retention_days()),
        )
        rows = cur.fetchall() or []
    finally:
        cur.close()

    # 활성 목록과 같은 규칙으로 이름순 표시(REQ-20260813-attach-name-sort). 위 SQL 의
    # `DeletedAt DESC` + `LIMIT 200` 은 **무엇을 가져올지**(최근 삭제분)를 정하는 절단
    # 기준이라 그대로 두고, 가져온 것의 표시 순서만 바꾼다 — 정렬을 SQL 로 옮기면 이름이
    # 앞선 오래된 삭제분이 200 칸을 채워 방금 지운 파일이 휴지통에서 사라진다.
    rows = _sort_attachment_rows_by_name(list(rows or []))

    # 관리 권한이 있는 행만 **반환**한다 — 표시만 숨기면 응답에는 원본 파일명·크기·
    # sha256 이 그대로 실려, 삭제 전에는 전원이 보던 것이 삭제 **후에도** 계속 보인다.
    # 파일명 자체가 PII 인 사례가 SECURITY §8.2.1 잔여 리스크로 기록돼 있다.
    _gate = app._manage_gate_for_conversation(conn, account, cid)
    results = []
    for r in rows:
        d = dict(r)
        if not _gate(d):
            continue
        ser = app._serialize_attachment_for_api(d)
        ser["can_manage"] = True
        results.append(ser)
    return JSONResponse({"attachments": results, "state": "deleted"})


# ==== REQ-20260806-attach-manage — 일괄 다운로드 (ZIP / 개별 매니페스트) ====

def _bulk_zip_max_bytes() -> int:
    """ZIP 총량 상한. 초과분을 조용히 잘라내지 않고 413 으로 알린다(§16.7 G9-b —
    무음 절단 금지). 개별 다운로드(`format=manifest`)가 상한 없는 경로다."""
    import os
    try:
        return max(1, int(os.getenv("ATTACHMENT_BULK_ZIP_MAX_BYTES") or str(512 * 1024 * 1024)))
    except Exception:
        return 512 * 1024 * 1024


def _zip_entry_name(row: dict, *, mode: str, used: set[str]) -> str:
    """ZIP 안 파일명. 전 버전 모드는 버전 번호를 붙이고, 그래도 겹치면 id 를 덧붙인다
    — 같은 이름이 두 번 들어가면 압축 해제 시 한쪽이 조용히 덮인다.

    `mode` 는 `app._download_filename_with_version` 의 keep/strip/force — 개별 다운로드와
    같은 규칙 함수를 쓴다(REQ-20260806-attach-suffix-toggle). 특히 `force` 는 저장명에 이미
    있는 접미를 떼고 다시 붙여, AI 편집본(`report_v2.csv`)이 `report_v2_v2.csv` 로 나가던
    이중접미를 없앤다."""
    import os as _os
    import re as _re
    raw = str(row.get("OriginalFilename") or "") or f"attachment-{row.get('Id')}"
    # 경로 구분자·상위 참조 제거 (zip-slip 방지) + 제어문자 제거.
    raw = raw.replace("\\", "/").split("/")[-1]
    raw = _re.sub(r"[\x00-\x1f\x7f]", "", raw).strip().lstrip(".") or f"attachment-{row.get('Id')}"
    name = app._download_filename_with_version(raw, int(row.get("VersionNumber") or 1), mode)
    stem, ext = _os.path.splitext(name)
    # id 접미 **한 번**으로는 부족하다 — 다른 첨부가 이미 `a_4.csv` 라는 이름을 갖고
    # 있으면 id=4 의 fallback 이 그것과 다시 충돌해 압축 해제 시 한쪽이 조용히 덮인다.
    # 충돌이 풀릴 때까지 접미를 늘린다.
    if name.lower() in used:
        base = f"{stem}_{int(row.get('Id') or 0)}"
        name = f"{base}{ext}"
        n = 2
        while name.lower() in used:
            name = f"{base}-{n}{ext}"
            n += 1
    used.add(name.lower())
    return name


@router.get("/api/conversations/{cid}/attachments/download")
def bulk_download_conversation_attachments(
    cid: str,
    request: Request,
    format: str = "zip",
    scope: str = "latest",
    ids: str = "",
    version_suffix: str = "",
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
):
    """REQ-20260806-attach-manage: 대화 첨부 일괄 다운로드.

    - `format=zip`(기본) — 한 개의 ZIP 스트림. `format=manifest` — 각 첨부의 앱-내부
      다운로드 URL 목록(JSON). 프론트가 개별 저장에 쓴다.
    - `scope=latest`(기본) — 첨부별 최신 버전 1개. `scope=all` — 버전 체인 전량
      (파일명에 `_v<n>`).
    - `ids=1,2,3` — 부분 선택(첨부 id 기준, 위 scope 결과와 교집합).
    - `version_suffix=auto|keep|strip|force` — 파일명의 버전 접미사 처리
      (REQ-20260806-attach-suffix-toggle). 미지정 시 종전 동작을 그대로 재현하는 값
      (`scope=all`→force, `latest`→auto)을 쓴다. `auto` 는 개별 다운로드와 같은 규칙(v2 이상만
      부착)이라 같은 파일을 ⬇ 로 받든 ⤓ '최신 버전만' 으로 받든 이름이 같다.

    권한은 개별 다운로드(`download_attachment`)와 동형 — 대화 단위 read.{own,any} +
    승인 대기 계정 본문 차단(D21). 즉 이 엔드포인트는 **한 번에 받는 편의**를 줄 뿐
    개별 경로로 이미 받을 수 있는 것 이상을 열지 않는다.
    """
    fmt = str(format or "zip").strip().lower()
    scope_norm = str(scope or "latest").strip().lower()
    if fmt not in ("zip", "manifest"):
        return app._json_error("format 은 zip 또는 manifest 여야 합니다.", 400)
    if scope_norm not in ("latest", "all"):
        return app._json_error("scope 는 latest 또는 all 이어야 합니다.", 400)
    suffix_mode = app._normalize_version_suffix_mode(
        version_suffix, default=("force" if scope_norm == "all" else "auto"))
    if not suffix_mode:
        return app._json_error("version_suffix 는 auto, keep, strip, force 중 하나여야 합니다.", 400)

    if not app._account_can_access_conversation(
        conn,
        account,
        cid,
        "conversation.attachment.read.own",
        "conversation.attachment.read.any",
    ):
        return app._json_error("이 대화의 첨부를 조회할 권한이 없습니다.", 403)
    if app._account_is_pending(account):
        return app._json_error("승인 대기 계정은 첨부 본문을 다운로드할 수 없습니다.", 403)

    id_filter: set[int] = set()
    _ids_raw = str(ids or "").strip()
    for tok in _ids_raw.split(","):
        tok = tok.strip()
        if tok.isdigit():
            id_filter.add(int(tok))
    if _ids_raw and not id_filter:
        # 무음 확대 금지 — 파싱 실패를 "필터 없음"으로 흘리면 3개를 고른 사용자가 대화
        # 전량을 받는다. scope 오타를 400 으로 막는 것과 같은 원칙의 반대 방향이다.
        return app._json_error("ids 파라미터에 유효한 첨부 id 가 없습니다.", 400)

    # share-visibility-window (SECURITY §21.2 · AR-2 / CSO F3): "여기부터 공유" 로 들어온
    # bounded 멤버는 floor 이전 구간을 볼 수 없다. 개별 다운로드·목록에 선재하는 갭이
    # 있더라도, 한 요청으로 전량이 나가는 이 경로에 clip 이 없으면 그 갭이 산업화된다.
    # 판정은 fork 와 **같은 헬퍼**를 쓴다 — 별도 구현은 두 벌이 어긋난다.
    win_lower_ca = win_upper_ca = None
    try:
        _cw_status, _lower_id, _upper_id = app._resolve_copy_window(conn, cid, int(account["id"]))
    except Exception:
        _cw_status, _lower_id, _upper_id = "deny", None, None
    if _cw_status == "deny":
        return app._json_error("열람 범위를 확인할 수 없어 다운로드를 중단했습니다.", 403)
    if _cw_status == "empty":
        return app._json_error("공유된 범위에 다운로드할 첨부가 없습니다.", 404)
    if _lower_id is not None or _upper_id is not None:
        # window 의 created_at 경계는 clip 된 표시 행에서 유도한다(발명 금지 — fork 와 동일).
        try:
            _win_rows = app._conv_load_messages_raw(conn, cid, upto_id=_upper_id, from_id=_lower_id)
        except Exception:
            return app._json_error("열람 범위를 확인할 수 없어 다운로드를 중단했습니다.", 403)
        if not _win_rows:
            return app._json_error("공유된 범위에 다운로드할 첨부가 없습니다.", 404)
        win_lower_ca = _win_rows[0][3] if _lower_id is not None else None
        win_upper_ca = _win_rows[-1][3] if _upper_id is not None else None

    where_latest = "" if scope_norm == "all" else " AND SupersededAt IS NULL"
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""
            SELECT Id, ObjectKey, OriginalFilename, SizeBytes, VersionNumber,
                   RootAttachmentId, CreatedByRole, UploadStatus, CreatedAt
            FROM WebConversationAttachments
            WHERE ConversationId = %s AND DeletedAt IS NULL{where_latest}
            ORDER BY COALESCE(RootAttachmentId, Id) ASC, VersionNumber ASC, Id ASC
            """,
            (cid,),
        )
        rows = [dict(r) for r in (cur.fetchall() or [])]
    finally:
        cur.close()

    if id_filter:
        rows = [r for r in rows if int(r.get("Id") or 0) in id_filter]
    clipped_count = 0
    if win_lower_ca is not None or win_upper_ca is not None:
        _kept = [r for r in rows
                 if not app._attachment_outside_window(r.get("CreatedAt"), win_lower_ca, win_upper_ca)]
        clipped_count = len(rows) - len(_kept)
        rows = _kept
    if not rows:
        return app._json_error(
            "다운로드할 첨부가 없습니다." if not clipped_count
            else "열람 가능한 범위에 첨부가 없습니다.", 404)

    rows = _sort_attachment_rows_for_bulk(rows)

    if fmt == "manifest":
        # 저장할 최종 이름은 **서버가 정한다** — 프론트가 같은 규칙을 복제하면 ZIP 경로와
        # 개별 저장 경로의 결과물이 서로 어긋난다. 이름 함수도 ZIP 과 **같은 것**을 쓴다:
        # 접미를 떼면 같은 이름이 여럿 나오는데, 여기서만 중복을 허용하면 모달이 약속한
        # "이름이 겹치는 파일에는 구분 번호가 붙습니다" 가 개별 저장에서만 거짓이 된다
        # (브라우저가 붙이는 `(1)` 은 어느 버전인지 말해주지 않는다).
        manifest_names: set[str] = set()
        files = [
            {
                "id": int(r.get("Id") or 0),
                "filename": str(r.get("OriginalFilename") or ""),
                "download_filename": _zip_entry_name(r, mode=suffix_mode, used=manifest_names),
                "size": int(r.get("SizeBytes") or 0),
                "version_number": int(r.get("VersionNumber") or 1),
                # presigned MinIO URL 이 아니라 앱 경로 — presigned 는 내부 endpoint 호스트가
                # 박혀 외부 브라우저가 열지 못한다(TASK-0284 배경).
                "url": (f"/api/attachments/{int(r.get('Id') or 0)}/download"
                        f"?version_suffix={suffix_mode}"),
            }
            for r in rows
        ]
        _audit_bulk_download(conn, request, account, cid, rows, fmt, scope_norm, 0, clipped_count)
        return JSONResponse({
            "files": files, "count": len(files), "scope": scope_norm,
            "clipped_count": clipped_count,
        })

    total_bytes = sum(int(r.get("SizeBytes") or 0) for r in rows)
    cap = _bulk_zip_max_bytes()
    if total_bytes > cap:
        # 부분 ZIP 을 주지 않는다 — 받은 사람은 그것이 전부라고 믿는다(§16.7 G9-b).
        return app._json_error(
            f"선택한 첨부의 합계 용량({total_bytes // (1024 * 1024)}MB)이 압축 다운로드 상한"
            f"({cap // (1024 * 1024)}MB)을 넘습니다. 파일을 나눠 선택하거나 개별 다운로드를 사용하세요.",
            413,
        )

    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)

    import tempfile
    import zipfile
    from urllib.parse import quote as _quote
    from starlette.responses import StreamingResponse as _Stream

    # SpooledTemporaryFile — 작은 묶음은 메모리, 임계 초과 시 디스크로 자동 전환.
    # 전량을 bytes 로 들고 있으면 큰 대화에서 web 프로세스 RSS 가 곧바로 튄다.
    spool = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)
    used_names: set[str] = set()
    packed = 0
    try:
        with zipfile.ZipFile(spool, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for r in rows:
                # 이름은 **건너뛸 행까지 포함해** 미리 확정한다. 실패 행을 `used` 에서
                # 빼면 뒤 행들의 충돌 재배정이 밀려, 같은 요청의 manifest(전 행 소비)와
                # ZIP 이 같은 첨부에 다른 이름을 준다(§18.8 backend/qa 패널 P3).
                entry_name = _zip_entry_name(r, mode=suffix_mode, used=used_names)
                object_key = str(r.get("ObjectKey") or "")
                if not object_key:
                    continue
                try:
                    data = storage_minio.get_object_bytes(object_key)
                except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                    # 한 파일의 실패로 전체를 버리지 않되, 빠진 사실을 사용자에게 남긴다
                    # — 조용히 적은 파일 수를 주면 누락을 알 길이 없다.
                    logging.getLogger(__name__).warning(
                        "bulk_download: object fetch failed (id=%s, key=%s)", r.get("Id"), object_key)
                    zf.writestr(
                        f"_다운로드_실패_{int(r.get('Id') or 0)}.txt",
                        f"{r.get('OriginalFilename') or ''} 파일을 저장소에서 가져오지 못했습니다.\n"
                        f"개별 다운로드(/api/attachments/{int(r.get('Id') or 0)}/download)로 다시 시도하세요.\n",
                    )
                    continue
                zf.writestr(entry_name, data)
                packed += 1
    except Exception:
        spool.close()
        logging.getLogger(__name__).warning("bulk_download: zip build failed (cid=%s)", cid, exc_info=True)
        return app._json_error("압축 파일을 만들지 못했습니다.", 500)

    spool.seek(0)
    zip_size = spool.seek(0, 2)
    spool.seek(0)
    _audit_bulk_download(conn, request, account, cid, rows, fmt, scope_norm, packed, clipped_count)

    # `download_attachment` 과 같은 정제를 거친다 — 지금은 cid 가 서버 생성이라 발동
    # 불가하지만, cid 출처가 하나라도 늘면 즉시 헤더 인젝션 면이 된다.
    filename = _sanitize_disposition_filename(f"attachments-{cid[:8]}.zip")
    failed_count = max(0, len(rows) - packed)

    def _iter():
        try:
            while True:
                chunk = spool.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            spool.close()

    return _Stream(
        _iter(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"; '
                f"filename*=UTF-8''{_quote(filename, safe='')}"
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            # 완성 크기를 알고 있으므로 준다 — 없으면 브라우저 진행률이 안 나온다.
            "Content-Length": str(zip_size),
            "X-Attachment-Count": str(packed),
            # 빠진 것이 있으면 헤더로도 말한다(프론트가 토스트에 반영).
            "X-Attachment-Clipped": str(clipped_count),
            "X-Attachment-Failed": str(failed_count),
        },
    )


def _sanitize_disposition_filename(name: str) -> str:
    """Content-Disposition 의 ASCII fallback 정제 (REV-20260616-0291 동형).

    따옴표와 모든 비출력 제어문자(CR/LF 포함)를 제거해 헤더 인젝션을 차단한다.
    `download_attachment` 이 같은 처리를 인라인으로 하고 있었고, 신규 ZIP 경로만
    빠져 있었다 — 두 곳이 같은 규칙을 쓰도록 헬퍼로 뺀다.
    """
    import re as _re
    s = str(name or "").replace('"', "")
    s = _re.sub(r"[\x00-\x1f\x7f]", "", s)
    s = "".join(c for c in s if c.isprintable()).strip()
    return s or "download"


def _audit_bulk_download(conn, request, account, cid, rows, fmt, scope_norm, packed, clipped=0) -> None:
    """일괄 반출은 개별 다운로드보다 흔적이 필요하다 — 무엇을 몇 건 가져갔는지 남긴다.

    `attachment.bulk_download` 는 `_audit_infra.build_audit_change_json` 에 분기가
    **있어야** 기록된다 — 없으면 그 함수가 `ValueError` 를 올리고 `_audit_user_action`
    이 삼켜 감사 행이 0 이 된다(라우터의 except 는 재-raise 가 없어 발화조차 안 함).
    """
    try:
        app._audit_user_action(
            conn,
            request,
            account,
            action="attachment.bulk_download",
            resource_type="conversation",
            resource_id=str(cid),
            request_ctx={
                "conversation_id": str(cid),
                "format": fmt,
                "scope": scope_norm,
                "attachment_ids": [int(r.get("Id") or 0) for r in rows],
                "requested_count": len(rows),
                "packed_count": packed,
                "clipped_count": int(clipped or 0),
                "total_bytes": sum(int(r.get("SizeBytes") or 0) for r in rows),
            },
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "bulk_download: audit dispatch failed (cid=%s)", cid, exc_info=True)


@router.get("/api/conversations")
def conversations(
    request: Request,
    q: str | None = None,
    owner_id: int | None = None,
    product_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """REQ-20260518-0010 (TASK-0072): list mode (no params) is backward-compatible.
    Search mode triggered when any of {q, owner_id, product_id, date_from, date_to,
    cursor} is provided. Body-search (q) requires rate limit + audit log."""
    search_mode = any(
        [q, owner_id is not None, product_id is not None, date_from, date_to, cursor]
    )
    if not search_mode:
        # TASK-0124: 고아 대화 (topic=NULL, 메시지 없음, 1시간 이상 경과) 자동 soft-delete.
        # early_cid 패턴으로 생성된 후 메시지가 오지 않은 빈 대화를 정리한다.
        # fail-open: 정리 실패는 목록 조회를 차단하지 않는다.
        try:
            app._cleanup_orphan_conversations(conn, int(account["id"]))
        except Exception:
            logging.getLogger(__name__).warning(
                "conversations: orphan cleanup failed (account_id=%s)",
                account.get("id"), exc_info=True,
            )
        payload = app._build_conversations_payload(conn, account)
        return JSONResponse(payload)

    # REQ-20260518-0010 risk 4: reject q that fails the normalize gate (covers
    # q="%%"" post-escape 0 char, q="ab" < 3 char, etc.). 400 response body is
    # generic to avoid distinguishing failure modes.
    if q is not None and app._normalize_search_query(q) is None:
        return app._json_error("invalid search query", 400)

    has_any = app._account_has_permission(account, "conversation.list.any")
    # adversarial risk 5: 404/403 metadata leak. For non-.any caller, owner_id
    # is silently coerced to self (no error) so response shape is byte-equal
    # regardless of input owner_id. _list_conversations sub-spec 1 enforces the
    # same overwrite at SQL composition time; this layer makes the intent explicit
    # for audit.
    effective_owner_id: int | None
    if has_any:
        effective_owner_id = owner_id
    else:
        effective_owner_id = int(account["id"]) if account.get("id") else None

    # Body-search rate limit (per-account, 10 req/min in-process token bucket).
    body_search_active = bool(q and app._normalize_search_query(q))
    if body_search_active:
        if not app._search_rate_limit_check(
            int(account["id"]), max_per_min=10, scope=app.RATE_SCOPE_CONVERSATION_SEARCH,
        ):
            return app._json_rate_limited(
                "대화 검색 요청이 너무 잦습니다.",
                app._rate_limit_retry_after(int(account["id"]), app.RATE_SCOPE_CONVERSATION_SEARCH),
            )
        # SET SESSION max_execution_time=3s for runaway query protection.
        try:
            cur_set = conn.cursor()
            cur_set.execute("SET SESSION max_execution_time = 3000")
            cur_set.close()
        except Exception:
            pass

    try:
        clamped_limit = max(1, min(int(limit or 50), 100))
    except Exception:
        clamped_limit = 50

    items = app._list_conversations(
        limit=clamped_limit,
        account=account,
        conn=conn,
        q=q,
        owner_id=effective_owner_id,
        product_id=product_id,
        date_from=date_from,
        date_to=date_to,
        cursor=cursor,
    )

    next_cursor: str | None = None
    if len(items) >= clamped_limit and items:
        last = items[-1]
        last_at = last.get("last_activity_at") or last.get("created_at") or ""
        if last_at and last.get("id"):
            next_cursor = f"{last_at}|{last['id']}"

    if body_search_active:
        try:
            app._log_search_activity(
                conn,
                account_id=int(account["id"]),
                action="conversation.search.body",
                target_owner_id=effective_owner_id,
                query=q,
                matched_count=len(items),
            )
        except Exception:
            # fail-open: 검색 활동 audit 실패는 검색 응답을 막지 않으나 가시화.
            logging.getLogger(__name__).warning(
                "conversations: search activity audit failed (account_id=%s)",
                account.get("id"), exc_info=True,
            )

    # REQ-20260519-0005 (TASK-0077): body-search 시 각 conv 의 매칭 message excerpt 첨부.
    matched_excerpts: dict[str, str] = {}
    # 첨부 파일명 축(SECURITY §8.2): 제목·본문에 검색어가 없어도 첨부 파일명 매칭으로 결과에
    # 뜰 수 있으므로, 그 매칭 근거(파일명)를 함께 실어 "왜 이 대화가 나왔나"를 설명한다.
    matched_attachments: dict[str, list[str]] = {}
    if body_search_active and items:
        normalized_q = app._normalize_search_query(q)
        if normalized_q:
            conv_ids = [str(it.get("id") or "") for it in items if it.get("id")]
            try:
                matched_excerpts = app._collect_matched_excerpts(conn, conv_ids, normalized_q)
            except Exception:
                matched_excerpts = {}
            # 첨부 근거는 **첨부 조회 권한 스코프 안에서만** 싣는다(SECURITY §8.2.1). 대화 목록
            # 권한과 첨부 조회 권한은 독립이라, 목록에 떴다는 사실만으로 파일명을 돌려주면
            # `conversation.attachment.read.*` 게이트가 우회된다. `.own` 이면 본인 소유·멤버
            # 대화로 좁히되, 그 판정은 **SQL 안에서**(scope_account_id) 수행한다 — items 의
            # owner_account_id/is_member 로 거르면 그 필드를 채우지 않는 백엔드(MySQL 폴백)에서
            # 멤버 대화의 근거가 조용히 비기 때문(PG/MySQL 동작 불일치).
            att_axis = app._search_attachment_axis(account)
            if att_axis in ("any", "own"):
                att_scope_id = None
                if att_axis == "own":
                    att_scope_id = int(account["id"]) if account.get("id") else None
                    if att_scope_id is None:
                        att_scope_id = -1  # 스코프 확정 불가 → 아무 대화도 매칭 안 됨(fail-closed)
                try:
                    matched_attachments = app._collect_matched_attachment_names(
                        conn, conv_ids, normalized_q, scope_account_id=att_scope_id
                    )
                except Exception:
                    matched_attachments = {}

    payload = {
        "items": items,
        "current": None,
        "next_cursor": next_cursor,
        "matched_count": len(items),
        "search_mode": True,
        "has_any": bool(has_any),
        "matched_excerpts": matched_excerpts,
        "matched_attachments": matched_attachments,
    }
    return JSONResponse(payload)

@router.patch("/api/conversations/{conversation_id}/title")
async def rename_conversation_title(
    conversation_id: str,
    request: Request,
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    # ITEM-11 batch2: 인라인 auth → DI(get_current_account/get_conn). get_conn finally:close 가
    # 게이트 헬퍼(_account_can_access_conversation 등) raise 시에도 conn 을 닫아 leak 을 해소.
    # byte-동치: get_conn 흡수→get_current_account "db connection failed" 500·unauth 401 인라인 동일.
    # 유일 차이=malformed/empty-title body+unauth 400→401 선행(§18.8 "benign"; 401/403/404 자체 불변).
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    title = app._normalize_topic(data.get("title"), "").strip()
    if not title:
        return app._json_error("empty title", 400)
    if len(title) > 256:
        return app._json_error("title too long", 400)
    if not app._account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.rename.own",
        "conversation.rename.any",
    ):
        return app._json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
    # feature-0009 gc-group-authz-flag (#1): 제목 변경은 대화 보유자(owner) 전용. 위 게이트는 그룹
    # 대화 '열람' 경계(멤버 포함)라 conversation.rename.own 권한 멤버도 통과하므로, 소유 메타 변경(제목)
    # 에는 2차 owner 게이트를 둔다. (delete 와 동일 패턴이나, update_conversation_product 와 달리
    # admin(.any) 우회를 허용한다.) owner 미기록(NULL) 레거시 대화는 1차 게이트 판정을 존중해 fail-open.
    _rename_owner_id = app._conversation_owner_account_id(conn, conversation_id)
    if (
        not app._account_has_permission(account, "conversation.rename.any")
        and _rename_owner_id is not None
        and _rename_owner_id != int(account.get("id") or 0)
    ):
        return app._json_error("소유자만 대화 제목을 변경할 수 있습니다.", 403)
    # AR-M5 cutover: AgentCoreConversations MySQL 테이블이 DROP 됨. raw UPDATE 는 500 →
    # 이미 PG 라우팅된 게이트 헬퍼 _conv_update_topic 재사용(PG agent_runtime.core_conversations).
    try:
        app._conv_update_topic(conn, conversation_id, title)
    except Exception:
        return app._json_error("제목 변경에 실패했습니다.", 500)
    return JSONResponse({"ok": True, "conversation_id": conversation_id, "title": title})


@router.post("/api/fork_conversation")
async def fork_conversation(request: Request) -> JSONResponse:
    """원본 대화를 현재 계정 소유의 새 대화로 스냅샷 복제한다.

    body: {source_conversation_id: str, from_message_id?: int}
    - 원본에 대한 read 권한 + 현재 계정의 conversation.create 권한이 모두 필요하다.
    - 실제 복제 로직은 `_fork_conversation_impl` 헬퍼가 수행한다 (share-token fork 와 공유).
    """
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    source_id = str(data.get("source_conversation_id") or "").strip()
    if not source_id:
        return app._json_error("empty source_conversation_id", 400)
    raw_from = data.get("from_message_id")
    from_id: int | None = None
    if raw_from is not None and str(raw_from).strip() != "":
        try:
            from_id = int(raw_from)
        except Exception:
            return app._json_error("invalid from_message_id", 400)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_has_permission(account, "conversation.create"):
            return app._json_error("요청을 수행할 수 없습니다.", 403)
        if not app._account_can_access_conversation(
            conn,
            account,
            source_id,
            "conversation.read.own",
            "conversation.read.any",
        ):
            return app._json_error("원본 대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        payload, err = app._fork_conversation_impl(conn, account, source_id, from_id)
        if err:
            return err
        return JSONResponse(payload)
    finally:
        conn.close()

@router.post("/api/clear_memory")
def clear_memory(request: Request) -> JSONResponse:
    return app._json_error("전체 정리 기능은 제거되었습니다.", 410)

@router.get("/api/progress")
def progress(
    request: Request,
    conversation_id: str = "",
    after_step: int = 0,
    client_run_id: str = "",
) -> JSONResponse:
    """처리 중인 대화의 실시간 step 진행 상황을 반환."""
    empty = JSONResponse({"steps": [], "status": "", "step_count": 0})
    try:
        conn = app._connect_memory()
    except Exception:
        return empty
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    cid = app._resolve_conversation_for_account(conn, account, conversation_id.strip())
    try:
        if not cid:
            conn.close()
            return empty
        status, status_at, run_id = app._load_progress_status(conn, cid)
        # feature-0009 그룹대화: 클라이언트가 추적 중인 run(client_run_id)이 대화의 현재 슬롯 run 과
        # 다르면, 그 run 이 동시 run 충돌로 terminal write 를 잃었을 수 있다. per-run marker 로 자기
        # run 의 종료를 해소해, 다른 사용자의 동시 run(슬롯 점유) 때문에 '처리 중' 에 갇히지 않게 한다.
        _client_rid = str(client_run_id or "").strip()
        if _client_rid and run_id and _client_rid != run_id:
            _term_status, _term_at = app._load_run_terminal_marker(conn, cid, _client_rid)
            if _term_status:
                run_id = _client_rid
                status = _term_status
                status_at = _term_at or status_at
        # KV 에 run_id 가 없는 경우 steps 테이블에서 최신 run 을 fallback 조회.
        fallback_status = ""
        if not run_id:
            fallback_run_id, is_recent = app._load_latest_run_id_from_steps(cid)
            if fallback_run_id:
                run_id = fallback_run_id
                fallback_status = "processing" if is_recent else "done"
                status = fallback_status
        next_after_step = max(0, int(after_step or 0))
        if not run_id or str(client_run_id or "").strip() != run_id:
            next_after_step = 0
        step_count = app._load_step_count_for_run(conn, cid, run_id) if run_id else 0
        new_steps = (
            app._load_steps_for_run(conn, cid, run_id, after_step=next_after_step)
            if run_id else []
        )
        # TASK-0061 Phase 3: stale 판정 — processing 이지만 만료 시간 동안 갱신 없음.
        if fallback_status:
            display_status, is_stale = fallback_status, False
        else:
            display_status, is_stale = app._compute_display_status(conn, cid, status, status_at, run_id)
        # feature-0030: 연장 확인 상태를 진행 폴링에 실어 보낸다 — 프론트가 이미 처리 중
        # 내내 도는 채널이라 새 폴링 경로를 만들지 않는다. 처리 중이 아니면 조회 생략.
        timeout_extension = {"prompted": False, "granted": False, "deadline_at": "", "run_id": ""}
        if display_status == "processing" and not is_stale:
            try:
                timeout_extension = app.timeout_extension_state(conn, cid)
            except Exception:
                pass
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return empty
    return JSONResponse({
        "steps": new_steps,
        "status": display_status,
        "raw_status": status,
        "display_status": display_status,
        "is_stale": is_stale,
        "status_at": status_at,
        "step_count": step_count,
        "run_id": run_id,
        "conversation_id": cid,
        "timeout_extension": timeout_extension,
    })

@router.get("/api/ask_result")
async def ask_result(
    request: Request,
    conversation_id: str = "",
    run_id: str = "",
    wait: int = 30,
) -> JSONResponse:
    """대화의 terminal 상태를 long-poll 로 기다려 최종 assistant 응답을 반환.

    - `run_id` 가 지정되면 그 run 이 terminal 에 도달할 때까지, 미지정이면 현재 run 이
      terminal 에 도달할 때까지 대기.
    - `wait` 은 초 단위, 기본 30s / 최대 60s. 초과 시 `{timeout: true}` 반환.
    - read-only 경로. `/api/ask` 슬롯·cancel/finalize 플래그를 건드리지 않음.
    """
    wait_s = max(1, min(60, int(wait or 30)))
    requested_run_id = str(run_id or "").strip()

    # 권한 검사 (첫 커넥션 1 회만)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    cid = app._resolve_conversation_for_account(conn, account, conversation_id.strip())
    if not cid:
        conn.close()
        return app._json_error("empty conversation_id", 400)
    if not app._account_can_access_conversation(
        conn,
        account,
        cid,
        "conversation.read.own",
        "conversation.read.any",
    ):
        conn.close()
        return app._json_error("권한이 없습니다.", 403)
    conn.close()

    loop = asyncio.get_event_loop()
    deadline = loop.time() + wait_s
    poll_interval = 0.5
    # 봉인 B: ask_jobs terminal backstop 의 다음 확인 시각(0=첫 tick 에서 즉시). KV 가 이미
    # 마감된 정상 대화에서는 위 판정이 먼저 return 하므로 이 조회 자체가 일어나지 않는다.
    _job_backstop_at = 0.0
    last_snapshot: dict[str, Any] = {}
    def _poll_once() -> "dict[str, Any] | None":
        """스냅샷 1회 — **동기 DB 구간 전체**를 워커 스레드에서 실행 (feature-0028 P1-A).

        종전엔 `async def` 본문에서 blocking MySQL/PG 드라이버를 직접 호출해, 답변 대기 중인
        사용자 1명이 0.5s 마다 이 replica 의 **이벤트 루프를 통째로 정지**시켰다(전수 조사
        S0-1 — uvicorn 워커가 replica 당 1개라 다른 모든 요청이 함께 stall). 실패는 None
        반환 → 호출측이 종전과 동일하게 다음 tick 재시도.
        """
        try:
            poll_conn = app._connect_memory()
        except Exception:
            return None
        try:
            return app._build_ask_status_snapshot(poll_conn, cid)
        finally:
            try:
                poll_conn.close()
            except Exception:
                pass

    while True:
        snapshot = await asyncio.to_thread(_poll_once)
        if snapshot is None:
            await asyncio.sleep(poll_interval)
            if loop.time() >= deadline:
                break
            continue
        last_snapshot = snapshot
        # TASK-0061 Phase 3: snapshot.status 는 display_status 이므로 raw_status 로 terminal 판정.
        server_status = str(snapshot.get("raw_status") or snapshot.get("status") or "")
        server_run_id = str(snapshot.get("run_id") or "")
        run_ok = (not requested_run_id) or (requested_run_id == server_run_id)
        is_stale = bool(snapshot.get("is_stale"))
        # stale 도 terminal 로 취급해 attach long-poll 무한 대기 방지.
        if run_ok and (server_status in app._ASK_TERMINAL_STATUSES or is_stale):
            latest = snapshot.pop("_latest_assistant", {}) or {}
            payload = {
                "conversation_id": cid,
                "status": snapshot.get("status", ""),
                "raw_status": server_status,
                "display_status": snapshot.get("display_status", ""),
                "is_stale": is_stale,
                "status_at": snapshot.get("status_at", ""),
                "run_id": server_run_id,
                "step_count": snapshot.get("step_count", 0),
                "duration_ms": snapshot.get("duration_ms", 0),
                "error": snapshot.get("error"),
                "has_answer": snapshot.get("has_answer", False),
                "assistant": latest if snapshot.get("has_answer") else None,
                "timeout": False,
            }
            return JSONResponse(payload)
        # conv-audit FR-early-return-kv-never-finalized(봉인 B): KV 가 마감되지 않았어도
        # worker job 이 이미 terminal 이면 **그쪽이 권위**다. run 이 KV 를 남기지 못하고 끝나면
        # (조기 종료·프로세스 소실) 위 판정이 영원히 성립하지 않아 프런트가 45초 폴링을 무한
        # 반복했다(실측 dead-air 는 stale 임계 18분까지). 내부 attach 루프가 job_id 로 갖는
        # 보증을 재접속 폴백 경로에도 대칭으로 준다. 활성 job 이 있으면 헬퍼가 None 을 주므로
        # 진행 중 답변을 끊지 않는다. 매 tick 조회는 PG 연결 낭비라 5초 주기로만 확인한다.
        if loop.time() >= _job_backstop_at:
            # 첫 tick 은 즉시(고아는 곧바로 해소), 그 뒤 10초 주기. 진행 중 대화에서는 헬퍼가
            # 활성 job 조회 1회로 None 을 주고 끝나지만, feature-0028 P1-A 가 줄여 둔 호출당
            # PG 연결 수를 되돌리지 않도록 간격을 둔다.
            _job_backstop_at = loop.time() + 10.0
            job_term = await asyncio.to_thread(app._latest_ask_job_terminal, cid)
            if job_term and ((not requested_run_id)
                             or requested_run_id == str(job_term.get("run_id") or "")):
                job_status = str(job_term.get("status") or "error")
                job_run_id = str(job_term.get("run_id") or "")
                latest = snapshot.pop("_latest_assistant", {}) or {}
                # §18.8 codex [P1]: 저장된 마지막 assistant 가 **이 job 의 답변이라는 보장이
                # 없다**(직전 run 의 답변·진행 중 partial). KV 경로의 has_answer 와 동일하게
                # run_id 를 대조해, 일치할 때만 답변으로 싣는다.
                _latest_run_id = ""
                if isinstance(latest, dict):
                    _meta = latest.get("meta") or {}
                    if isinstance(_meta, dict):
                        _latest_run_id = str(_meta.get("run_id") or "").strip()
                has_answer = (bool(latest) and job_status == "done"
                              and bool(job_run_id) and _latest_run_id == job_run_id)
                logging.getLogger(__name__).info(
                    "ask_result: KV 미마감 run 을 ask_jobs terminal 로 해소 cid=%s job=%s "
                    "job_status=%s kv_status=%s", cid, job_term.get("id"), job_status,
                    server_status or "<empty>",
                )
                return JSONResponse({
                    "conversation_id": cid,
                    "status": job_status,
                    "raw_status": job_status,
                    "display_status": job_status,
                    "is_stale": False,
                    "status_at": snapshot.get("status_at", ""),
                    "run_id": str(job_term.get("run_id") or ""),
                    "step_count": snapshot.get("step_count", 0),
                    "duration_ms": snapshot.get("duration_ms", 0),
                    "error": str(job_term.get("error") or "") or None,
                    "has_answer": has_answer,
                    "assistant": latest if has_answer else None,
                    "timeout": False,
                })
        if loop.time() >= deadline:
            break
        await asyncio.sleep(poll_interval)

    last_snapshot.pop("_latest_assistant", None)
    return JSONResponse({
        "conversation_id": cid,
        "status": last_snapshot.get("status", "") or "processing",
        "raw_status": last_snapshot.get("raw_status", ""),
        "display_status": last_snapshot.get("display_status", ""),
        "is_stale": bool(last_snapshot.get("is_stale")),
        "status_at": last_snapshot.get("status_at", ""),
        "run_id": last_snapshot.get("run_id", ""),
        "step_count": last_snapshot.get("step_count", 0),
        "duration_ms": last_snapshot.get("duration_ms", 0),
        "error": last_snapshot.get("error"),
        "has_answer": last_snapshot.get("has_answer", False),
        "assistant": None,
        "timeout": True,
    })

@router.get("/api/suggestions")
def suggestions(request: Request, limit: int = 40) -> JSONResponse:
    try:
        conn = app._connect_memory()
    except Exception:
        return JSONResponse({"items": []})
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return JSONResponse({"items": []})
    if not app._account_has_permission(account, "conversation.ask"):
        conn.close()
        return JSONResponse({"items": []})
    conv_ids = [item["id"] for item in app._list_conversations(limit=200, account=account, conn=conn)]
    if not conv_ids:
        conn.close()
        return JSONResponse({"items": []})
    placeholders = ",".join(["%s"] * len(conv_ids))
    # AR-M5 cutover: 메시지 정본이 MySQL AgentMemoryMessages → PG agent_runtime.messages 로
    # 이전되며 MySQL 테이블이 DROP 되었다. _get_history 와 동일하게
    # AGENT_RUNTIME_READ_BACKEND 로 분기하지 않으면 삭제된 테이블을 조회해 500 (입력
    # 추천이 죽는다). 예외는 fail-soft 로 빈 items 처리(함수 기존 계약 유지).
    rows: list = []
    try:
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        f"SELECT content FROM agent_runtime.messages "
                        f"WHERE role = 'user' AND conversation_id IN ({placeholders}) "
                        f"ORDER BY created_at DESC LIMIT %s",
                        tuple(conv_ids) + (int(limit) * 3,),
                    )
                    rows = pgcur.fetchall() or []
            finally:
                pg.close()
        else:
            cur = conn.cursor()
            cur.execute(
                f"""
SELECT Content
FROM AgentMemoryMessages
WHERE Role = 'user'
  AND ConversationId IN ({placeholders})
ORDER BY CreatedAt DESC
LIMIT %s
                """,
                tuple(conv_ids) + (int(limit) * 3,),
            )
            rows = cur.fetchall() or []
            cur.close()
    except Exception:
        rows = []
    conn.close()
    items: list[str] = []
    seen = set()
    for (content,) in rows:
        text = app._unwrap_followup_user_request(str(content or ""))
        if len(text) < 6:
            continue
        if text in seen:
            continue
        seen.add(text)
        items.append(text)
        if len(items) >= int(limit):
            break
    return JSONResponse({"items": items})


@router.post("/api/ask")
async def ask(request: Request) -> JSONResponse:
    start_ts = time.time()
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    message = str(data.get("message", "")).strip()
    # feature-0007 (REQ-20260521-0001): `api_key_cipher` / `api_key_passphrase`
    # 파라미터 폐기. backend 가 보유한 BEDROCK_GATEWAY_API_KEY (service-managed)
    # 가 단일 자격증명. 구 클라이언트가 cipher 를 보내도 silently 무시.
    model = str(data.get("model", "") or API_DEFAULT_MODEL).strip()
    # feature-0003 model-persist: 클라이언트가 **명시로** model 을 실었는지(=사용자 선택 신호).
    # 부재 시 위에서 API_DEFAULT_MODEL 로 폴백하므로 `model` 만으로는 명시/폴백을 구분할 수 없다.
    # 이 플래그가 true 일 때만 대화별 KV 에 저장한다 — 'AI 로 고치기'(fix_with_ai) 처럼 서버가
    # model 없이 재dispatch 하는 내부 경로가 대화의 선택 모델을 haiku 로 조용히 되돌리는 회귀 차단
    # (reasoning_level 의 "명시 값일 때만 저장" 계약과 동형).
    model_explicit = bool(str(data.get("model", "") or "").strip())
    request_conversation_id = str(data.get("conversation_id", "")).strip()
    # feature-0003 reasoning-effort-selector: 사용자가 대화 화면에서 고른 추론 강도.
    # 유효 레벨(low/normal/high/max)만 통과, 그 외(부재·미상)는 None → **override 안 함**(각 모델
    # config 기본 thinking 유지). B1 회귀 방지(REV 적대검증): 부재 필드를 기본값으로 강제 대입하면
    # 선택기 미상호작용·구 클라이언트의 sonnet 이 config 16000 → 강등되는 회귀 발생 → 강제 대입 금지.
    reasoning_level = normalize_reasoning_level(data.get("reasoning_level"))
    # ── 기본 입력 검증 ──
    if not message:
        conn.close()
        return app._json_error("empty message", 400)
    elif not model:
        conn.close()
        return app._json_error("모델 설정이 필요합니다.", 400)
    elif not app._is_safe_model_name(model):
        conn.close()
        return app._json_error("모델 이름 형식이 올바르지 않습니다.", 400)
    elif not app._is_allowed_api_model(model):
        conn.close()
        return app._json_error("허용되지 않은 모델입니다.", 400)
    # model-access-rbac(2026-07-28, Critical §12.3): 계정/역할별 모델 사용 권한 게이트.
    # **단일 choke-point** — 재답변(`_reanswer`)·'AI 로 고치기' 등 내부 재dispatch 경로도 모두
    # `ask()` 를 다시 타므로 여기 한 곳이 클라이언트 지정 model 의 전 진입면을 덮는다
    # (`_is_allowed_api_model` 이 카탈로그 allowlist=400, 본 게이트가 계정 인가=403 — 축 분리).
    # 표시(모델 선택기)는 `/api/session` 의 `_filter_models_for_account_access` 가 함께 닫는다.
    elif not app._account_has_model_access(account, model, conn=conn):
        conn.close()
        return app._json_error("이 모델을 사용할 권한이 없습니다. 관리자에게 문의하세요.", 403)
    # 자격증명 검증은 backend 단일 env 소스로 이동 (config.py 의 LLM_API_KEY).
    # 호출 시점에 자격증명이 미설정이면 `_run_agent_core` 가 result["error"] 로
    # 보고 → user 에게 503 안내.
    # TASK-20260619T030500-llm-usage-quota (보안 ④): LLM 토큰 사용량 한도 사전 게이트(역할 기본 + 계정 특수).
    # 무제한/미설정/인프라장애=통과(fail-open). 초과 시 429(slot 획득 전 조기 차단).
    _quota_ok, _quota_msg = app._check_account_token_quota(conn, account)
    if not _quota_ok:
        conn.close()
        return app._json_error(_quota_msg, 429)
    # feature-0009 gc-participant-product-select: 공유 대화 참가자의 per-message 제품 override.
    # 기존 대화 + 비-owner 멤버 분기에서만 채워진다(아래). owner·신규 대화 경로는 None 유지.
    _participant_product_override: dict[str, Any] | None = None
    if request_conversation_id:
        if not app._conversation_exists(request_conversation_id, conn=conn):
            conn.close()
            return app._json_error("conversation not found", 404)
        if not app._account_has_permission(account, "conversation.ask"):
            conn.close()
            return app._json_error("권한이 없습니다.", 403)
        if not app._conversation_owned_by_account(conn, request_conversation_id, int(account["id"])):
            # feature-0009 S4 (열람 ≠ 발화): 그룹 대화 멤버도 @assistant 발화 가능. 비-멤버는 차단.
            if not app._account_is_conversation_member(request_conversation_id, int(account["id"])):
                conn.close()
                return app._json_error("타 계정 대화에는 요청을 이어서 보낼 수 없습니다.", 403)
            # actor RBAC 게이트: 발신 멤버 본인이 이 대화의 데이터소스(pinned product)에 접근 권한이
            # 있어야 발화(쿼리) 가능. 무권한 멤버는 열람만 — 결과·SQL 은 볼 수 있으나 새 질의는 거부.
            # auto 모드(미고정)는 다운스트림 execute_sql 가 actor 접근 datasource 로 제한하므로 허용.
            _ask_conv_prod = app._load_conversation_product(conn, request_conversation_id)
            # feature-0009 gc-participant-product-select: 참가자가 이 요청에 대해 제품을 바꿔 보냈으면
            # (body product override) 그 선택으로 발화한다. 선택 제품은 본인 RBAC 로 검증된 것만
            # 통과(아래 helper)하므로, 대화 공통 pinned product 에 본인 접근권이 없어도 본인이 권한 가진
            # 다른 제품으로 질의할 수 있다(ANCHOR §1 보존 — 권한 상속 아님, 본인 권한 범위 내 선택).
            _participant_product_override = app._parse_participant_product_override(conn, account, data)
            if _participant_product_override is not None and not _participant_product_override.get("ok"):
                conn.close()
                return app._json_error(
                    _participant_product_override.get("error") or "요청을 수행할 수 없습니다.", 403
                )
            # override 가 없을 때만 대화 공통 pinned product 접근권을 게이트(기존 열람-전용 정책).
            if _participant_product_override is None and (
                _ask_conv_prod
                and _ask_conv_prod.get("product_mode") == "pinned"
                and _ask_conv_prod.get("product_id")
                and not app._account_has_product_access(account, int(_ask_conv_prod["product_id"]), conn=conn)
            ):
                conn.close()
                return app._json_error("이 대화의 데이터소스에 발화(질의) 권한이 없습니다. 열람만 가능합니다.", 403)
        # TASK-0248: 참조 제품이 삭제되어 차단(blocked)된 대화는 진행 불가. 이력 열람·공유는
        # 가능하나 새 메시지 전송은 거부. slot 획득 전(조기 차단)이라 동시성 카운터 영향 없음.
        _is_blocked, _block_reason = app._conversation_block_info(request_conversation_id, conn=conn)
        if _is_blocked:
            conn.close()
            return app._json_error(_block_reason or app._BLOCKED_PRODUCT_DELETED_REASON, 403)
        # feature-0009 gc-group-authz-flag (#2 서버 방어선): 그룹 대화에서 @assistant 멘션이 없는
        # 메시지는 사람-사람 채팅이므로 assistant 를 실행하지 않는다. 클라이언트 send-routing 이 이미
        # store-only 로 보내지만(is_group/member_count), stale·직접 API 호출로 /api/ask 에 도달하면
        # 여기서 거부(422 code=group_requires_mention)해 오호출을 차단한다(단일 실패점 제거). 멘션
        # 판정은 서버측 재파싱(클라이언트 플래그 불신). 클라이언트는 이 code 수신 시 store-only 로 재라우팅.
        try:
            from modules.mentions import message_invokes_assistant as _msg_invokes_assistant
            _server_invokes_assistant = bool(_msg_invokes_assistant(message))
        except Exception:
            _server_invokes_assistant = True  # 파서 장애 시 보수적으로 통과(기존 동작 유지)
        if not _server_invokes_assistant and app._conversation_is_group(request_conversation_id):
            conn.close()
            return JSONResponse(
                {
                    "error": "그룹 대화에서는 @assistant 를 멘션해야 AI 가 응답합니다. (멘션 없는 메시지는 참여자 간 채팅으로 전송됩니다.)",
                    "code": "group_requires_mention",
                },
                status_code=422,
            )
        conv_id = request_conversation_id
    else:
        if not app._account_has_permission(account, "conversation.create"):
            conn.close()
            return app._json_error("요청을 수행할 수 없습니다.", 403)
        if not app._account_has_permission(account, "conversation.ask"):
            conn.close()
            return app._json_error("권한이 없습니다.", 403)
        # TASK-0059: frontend "새 대화" 버튼 lazy 경로의 명시적 신규 의도. hint 가 있으면 직전
        # 대화 (account.last_conversation_id) 로 폴백하지 않고 신규 cid 를 강제 생성한다.
        # hint 없는 legacy client (세션 부트스트랩 후 직전 대화 자동 이어받기) 는 force_new=False
        # 로 기존 동작 유지.
        lazy_create_requested = bool(data.get("lazy_create"))
        conv_id = app._resolve_conversation_for_account(
            conn,
            account,
            request_conversation_id,
            create_if_missing=True,
            force_new=lazy_create_requested,
        )
        # TASK-0048: client (특히 사이드바 "새 대화" 버튼이 lazy 화된 frontend) 가 첫 메시지에 함께 보낸
        # product hint 를 이 시점에 적용한다. /api/new_conversation 의 동등한 분기를 ask body 안으로 이식.
        # 기존 대화(`request_conversation_id` 명시) 경로에는 적용하지 않는다 — 대화 product 는 이미 결정된
        # 상태이며, 변경 경로는 `PATCH /api/conversations/{cid}/product` 의 race 가드 단독 진실(TASK-0047).
        try:
            hint_raw_mode = data.get("product_mode") if isinstance(data, dict) else None
            hint_raw_pid = data.get("product_id") if isinstance(data, dict) else None
            if hint_raw_mode is not None or hint_raw_pid is not None:
                hint_mode = app._normalize_product_mode(hint_raw_mode, default="pinned")
                hint_pid: int | None = None
                if hint_raw_pid is not None and str(hint_raw_pid).strip() != "":
                    try:
                        hint_pid = int(hint_raw_pid)
                    except Exception:
                        hint_pid = None
                if hint_mode == "auto":
                    hint_pid = None
                elif not hint_pid:
                    hint_pid = app._get_default_product_id(conn) or None
                # TASK-0052 Phase 1C G3: hint product_id 의 접근 권한 검사.
                # 권한 없으면 auto 로 강등 + 사용자 직접 명시 hint 였다면 403 으로 차단.
                if hint_mode == "pinned" and hint_pid:
                    if not app._account_has_product_access(account, int(hint_pid), conn=conn):
                        if hint_raw_pid not in (None, "", 0):
                            conn.close()
                            return app._json_error("요청을 수행할 수 없습니다.", 403)
                        hint_mode = "auto"
                        hint_pid = None
                if conv_id:
                    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
                        try:
                            from shared.db import _pg_connect
                            _pg_tmp = _pg_connect()
                            with _pg_tmp.cursor() as _pgc:
                                _pgc.execute(
                                    "UPDATE agent_runtime.core_conversations SET product_id = %s, product_mode = %s WHERE conversation_id = %s",
                                    (int(hint_pid) if hint_pid else None, hint_mode, conv_id),
                                )
                            _pg_tmp.close()
                        except Exception:
                            # fail-open: product hint 적용 실패는 ask 를 막지 않으나 조용한 PG 쓰기 실패를 가시화.
                            logging.getLogger(__name__).warning(
                                "ask: PG product hint update failed (conversation_id=%s mode=%s)",
                                conv_id, hint_mode, exc_info=True,
                            )
                    else:
                        cur_h = conn.cursor()
                        cur_h.execute(
                            "UPDATE AgentCoreConversations SET product_id = %s, product_mode = %s "
                            "WHERE conversation_id = %s",
                            (int(hint_pid) if hint_pid else None, hint_mode, conv_id),
                        )
                        cur_h.close()
                    app._save_account_product_pref(
                        conn, int(account["id"]), mode=hint_mode, pinned_id=hint_pid
                    )
        except Exception:
            # hint 적용 실패는 ask 자체를 막지 않는다 — default('pinned' + default product) 로 fallback.
            pass
    # TASK-0073 Phase A6: user endpoint best-effort audit hook (fail-open).
    # conv_id 결정 직후, LLM 호출 전 시점에 audit row INSERT. 실패 = stderr only.
    app._audit_user_action(
        conn,
        request,
        account,
        action="conversation.ask",
        resource_type="conversation",
        resource_id=str(conv_id) if conv_id else None,
        request_ctx={
            "conversation_id": str(conv_id) if conv_id else None,
            "model": model,
            "lazy_create": bool(data.get("lazy_create")) if not request_conversation_id else False,
            "prompt_length": len(message or ""),
        },
    )
    slot_key = f"account:{int(account['id'])}"
    if not app._acquire_request_slot(slot_key):
        conn.close()
        return app._json_error("동시 요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요.", 429)
    try:
        # feature-0007: per-request api_key 분기 제거. LLM 자격증명은 service env
        # 단일 소스 (config.py 의 LLM_API_KEY → BEDROCK_GATEWAY_API_KEY chain).
        from agent_core import run_agent as _run_agent_core

        temp_value = 0.0 if app._model_supports_temperature(model) else None

        # ── Product / Role / Account 기반 system prompt depth 컨텍스트 해결 ──
        # TASK-0047: 대화의 product_mode 까지 함께 조회. mode='auto' 면 product 한정 prompt/allowed schemas 를
        # 주입하지 않고, 메타데이터 4 스키마만 허용한다(빈 리스트). 향후 LLM resolver 가 도입되면 그 시점에
        # 한해 turn-local product 가 추론된다 (BRIEFING-product-selector-v1.md 참조).
        product_mode_for_run: str = "pinned"
        try:
            product_id_for_run: int | None = None
            if conv_id:
                if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
                    try:
                        from shared.db import _pg_connect
                        _pg_tmp2 = _pg_connect()
                        with _pg_tmp2.cursor() as _pgc2:
                            _pgc2.execute(
                                "SELECT product_id, product_mode FROM agent_runtime.core_conversations WHERE conversation_id = %s",
                                (conv_id,),
                            )
                            row_p = _pgc2.fetchone()
                        _pg_tmp2.close()
                    except Exception:
                        row_p = None
                else:
                    cur_p = conn.cursor()
                    cur_p.execute(
                        "SELECT product_id, product_mode FROM AgentCoreConversations WHERE conversation_id = %s",
                        (conv_id,),
                    )
                    row_p = cur_p.fetchone()
                    cur_p.close()
                if row_p:
                    if row_p[0] is not None:
                        product_id_for_run = int(row_p[0])
                    product_mode_for_run = app._normalize_product_mode(row_p[1], default="pinned")
            # feature-0009 gc-participant-product-select: 참가자 per-message override 적용.
            # 대화 공통 바인딩(row_p)을 읽은 뒤, 이 요청에 한해 참가자가 고른 제품으로 run product 를
            # 덮어쓴다. 선택 제품은 member 분기에서 본인 RBAC 로 이미 검증됨. 대화 product_id 는
            # persist 하지 않는다(아래 backfill UPDATE 를 override 시 skip) — 공통 바인딩 비파괴.
            if _participant_product_override is not None and _participant_product_override.get("ok"):
                if _participant_product_override.get("mode") == "pinned":
                    product_mode_for_run = "pinned"
                    product_id_for_run = int(_participant_product_override["product_id"])
                else:
                    product_mode_for_run = "auto"
                    product_id_for_run = None
            if product_mode_for_run == "auto":
                # auto 모드: 기존 default 자동 채움 경로를 우회한다 (의도 보존).
                product_id_for_run = None
                allowed_schemas_for_run = []  # 메타 4 스키마만 허용 (cross-product leak 차단)
            else:
                if not product_id_for_run:
                    product_id_for_run = app._get_default_product_id(conn) or None
                # TASK-0052 Phase 1C G4 (Codex Claim 3): 기존 대화의 product_id_for_run 시점에도 권한 검사.
                # 권한 회수 후에도 pinned 대화가 그대로 실행되던 갭 차단. α 정책 (briefing §3.4):
                # 권한 없으면 403 + "이 대화의 제품 접근 권한이 회수되었습니다" 안내. frontend 에서 사용자가
                # auto 모드로 전환하거나 admin 에게 권한 요청 후 재시도하도록 가이드.
                if product_id_for_run and not app._account_has_product_access(account, int(product_id_for_run), conn=conn):
                    # TASK-0169 (BL-1, outside-voice): slot 은 finally 가 단일 release 한다.
                    # 여기서 명시 release 하면 finally 와 합쳐 이중 감산 → 계정 동시성 카운터
                    # 손상(다른 in-flight 요청의 슬롯을 훔침). 다른 early-return 처럼 finally 에 위임.
                    conn.close()
                    return app._json_error(
                        "이 대화의 제품 접근 권한이 회수되었습니다. 사이드바에서 auto 모드로 전환하거나 관리자에게 권한 요청 후 다시 시도해 주세요.",
                        403,
                    )
                # feature-0009 gc-participant-product-select: 참가자 override 가 적용된 요청은 대화
                # 공통 product_id 를 backfill 하지 않는다(per-message 선택이 대화 바인딩을 바꾸면 안 됨).
                if product_id_for_run and conv_id and _participant_product_override is None:
                    try:
                        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
                            from shared.db import _pg_connect
                            _pg_tmp3 = _pg_connect()
                            with _pg_tmp3.cursor() as _pgc3:
                                _pgc3.execute(
                                    "UPDATE agent_runtime.core_conversations SET product_id = %s "
                                    "WHERE conversation_id = %s AND (product_id IS NULL OR product_id = 0)",
                                    (int(product_id_for_run), conv_id),
                                )
                            _pg_tmp3.close()
                        else:
                            cur_u = conn.cursor()
                            cur_u.execute(
                                "UPDATE AgentCoreConversations SET product_id = %s "
                                "WHERE conversation_id = %s AND (product_id IS NULL OR product_id = 0)",
                                (int(product_id_for_run), conv_id),
                            )
                            cur_u.close()
                    except Exception:
                        # fail-open: 대화 product_id backfill 실패는 ask 를 막지 않으나 조용한 쓰기 실패를 가시화.
                        logging.getLogger(__name__).warning(
                            "ask: conversation product_id backfill failed "
                            "(conversation_id=%s product_id=%s)",
                            conv_id, product_id_for_run, exc_info=True,
                        )
                # re-gate(5차) BLOCKER5: "데이터소스 미바인딩/제품 없음 = 접근 0" (DB-단위 모델, flag ON).
                #  - 제품 없음(default 도 없음) → allowed=[] (과거 None=무제한 → 데이터계정 GRANT 전체 누출).
                #  - 제품이 datasource 미바인딩(DatasourceKey NULL) → allowed=[] (데이터는 데이터소스 종속).
                # flag OFF(레거시 단일 MySQL)에서는 종전대로 None(제품 allowlist 미적용 경로 보존).
                # re-gate(6차) MAJOR: config 와 **동일 파서** 사용(1/true/yes). 과거 web 은 "0/false/False"
                # 외 전부 활성으로 봐 FALSE/no/off 에서 agent-core(OFF)와 불일치→레거시 정상조회 과차단.
                _multi_ds = str(os.getenv("AGENT_MULTI_DATASOURCE_ENABLED", "0")).strip().lower() in ("1", "true", "yes")
                if product_id_for_run:
                    if _multi_ds and not app._product_has_datasource(conn, int(product_id_for_run)):
                        allowed_schemas_for_run = []  # 미바인딩 = 접근 0
                    else:
                        allowed_schemas_for_run = app._product_allowed_schemas(conn, int(product_id_for_run))
                elif _multi_ds:
                    allowed_schemas_for_run = []  # 제품 없음 = 접근 0
                else:
                    allowed_schemas_for_run = None  # 레거시 단일 MySQL
            role_id_for_run: int | None = None
            try:
                role_payload = app._role_payload(account) or {}
                if role_payload.get("id"):
                    role_id_for_run = int(role_payload["id"])
            except Exception:
                role_id_for_run = None
        except Exception:
            # re-gate BLOCKER5(2차): product/allowlist 해석 중 예외 → **ask 전면 중단(fail-closed)**.
            # 과거엔 allowed=None(또는 [])로 폴백했으나, product_id=None + datasource 비활성 상태에서는
            # 무자격 쿼리(SELECT * FROM Secrets)가 데이터 계정 GRANT 의 기본 DB 로 그대로 실행됐다(차단 우회).
            # 권한 컨텍스트를 신뢰할 수 없는 상태에서 어떤 쿼리도 돌리지 않는다 — 사용자에게 재시도 안내.
            logging.getLogger(__name__).error(
                "ask: product/allowlist 해석 실패 — 권한 컨텍스트 불명, ask 중단(fail-closed)", exc_info=True,
            )
            try:
                conn.close()  # 슬롯은 outer finally 가 해제, conn 은 per-return 정리 패턴 따름
            except Exception:
                pass
            return app._json_error("권한 컨텍스트를 확인할 수 없어 요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.", 503)

        # feature-0007: api_key 인자 제거. agent_core 가 env 단일 소스로 자격증명
        # 결정 (LLM_API_KEY → BEDROCK_GATEWAY_API_KEY chain).
        # TASK-0094 Sprint 1 Phase 11: attachment_ids 를 env 로 전달.
        # compose_system_prompt 가 ATTACHMENT_IDS env 를 읽어 prompt 에 section 주입.
        # feature-0003 attach-full-scope (2026-07-29): 클라이언트가 보낸 목록은 **이번 턴 신규
        # 첨부 신호**로만 쓰고, 실제 참조 스코프는 아래에서 대화 전체로 해소한다(D16 supersede).
        client_attachment_ids: list[int] = []
        attachment_ids_raw = data.get("attachment_ids") if isinstance(data.get("attachment_ids"), list) else []
        for v in attachment_ids_raw[:50]:  # cap 50 per request
            try:
                iv = int(v)
                if iv > 0:
                    client_attachment_ids.append(iv)
            except Exception:
                continue
        attachment_ids_clean: list[int] = list(client_attachment_ids)
        # TASK-0137: 첨부 메타는 os.environ 전역 대신 run_agent 의 contextvar kwarg 로 전달
        # (동시 요청 격리). attachment_ids_clean 은 아래 to_thread 호출에서 kwarg 로 넘긴다.

        # new_attachment_ids: 이번 요청에 새로 첨부된 파일 ID (프론트에서 source="new" 기준).
        # agent_core 가 LLM 컨텍스트에서 신규/세션 파일을 구분해 라벨링하는 데 사용.
        new_attachment_ids_raw = data.get("new_attachment_ids") if isinstance(data.get("new_attachment_ids"), list) else []
        new_attachment_ids_clean: list[int] = []
        for v in new_attachment_ids_raw[:50]:
            try:
                iv = int(v)
                if iv > 0:
                    new_attachment_ids_clean.append(iv)
            except Exception:
                continue
        # TASK-0137: new_attachment_ids 도 contextvar kwarg 로 전달 (아래 to_thread 참조).

        # feature-0003 attach-full-scope (2026-07-29 사용자 결정): 참조 스코프를 프론트 selection
        # 에서 **이 대화의 활성 첨부 전량**으로 옮긴다. 첨부가 걸린 대화를 이어서 진행할 때 이전
        # 턴 첨부가 통째로 빠지던 마찰(프론트 bucket 이 비는 진입 경로)을 구조적으로 제거한다.
        # 공유(그룹) 대화의 축소 여부는 **window 게이트가 단독 판정**한다(`shared.share_window`).
        # 여기서 `_conversation_is_group()` 으로 선-게이팅하지 않는 이유: 그 함수는 PG 오류 시
        # False 를 돌려주므로, 판정 실패가 곧 "게이트 건너뛰고 대화 전체" 라는 fail-open 이 된다
        # (§18.8 적대 리뷰 [P1]). 게이트는 멤버 수·소유자·window 를 한 쿼리에서 함께 읽고,
        # 하나라도 확인 못 하면 발신자 본인 첨부로 좁힌다. 1:1·fork 는 멤버 ≤ 1 로 판정돼 무회귀.
        attachment_ids_clean = app._resolve_conversation_attachment_scope(
            conn,
            conv_id,
            int(account["id"]),
            client_ids=client_attachment_ids + new_attachment_ids_clean,
            sender_scope=True,
        )

        # TASK-0107 hotfix: UploadStatus 가 'uploaded' (ingest 미완) 또는 'failed' 인
        # csv/xlsx attachment 를 /api/ask 진입 시점에 동기 ingest 해 LLM 호출 전에
        # sandbox table 이 준비되도록 한다. timeout (최대 30s) 이내 완료 못 하면
        # background 로 fallback — 이번 turn 은 metadata 만, 다음 turn 부터 full context.
        # feature-0003 attach-full-scope: 동기 ingest 대기는 **이번 턴에 올라온 첨부**로 한정한다.
        # 스코프가 대화 전량으로 넓어진 뒤에도 이전 턴의 failed 첨부를 매 턴 재시도하며 최대 25s
        # 를 기다리는 지연 회귀가 생기지 않게 한다(과거 실패분은 아래 background ingest 대상).
        _sync_ingest_ids: list[int] = []
        for _v in (client_attachment_ids + new_attachment_ids_clean):
            if _v not in _sync_ingest_ids:
                _sync_ingest_ids.append(_v)
        if _sync_ingest_ids:
            try:
                _placeholders = ", ".join(["%s"] * len(_sync_ingest_ids))
                # TASK-0284: ConversationId 스코프(대화에 속한 csv/xlsx 만 ingest), 미결정 시 AccountId 폴백.
                if conv_id:
                    _pi_col, _pi_val = "ConversationId", str(conv_id)
                else:
                    _pi_col, _pi_val = "AccountId", int(account["id"])
                _pending_cur = conn.cursor(dictionary=True)
                _pending_cur.execute(
                    f"SELECT Id, ConversationId, ObjectKey, Kind FROM WebConversationAttachments "
                    f"WHERE Id IN ({_placeholders}) AND {_pi_col} = %s AND UploadStatus IN ('uploaded','failed') "
                    f"AND Kind IN ('csv','xlsx') AND DeletedAt IS NULL AND DeletePending = 0 LIMIT 10",
                    tuple(_sync_ingest_ids) + (_pi_val,),
                )
                _pending_rows = _pending_cur.fetchall() or []
                _pending_cur.close()
            except Exception:
                _pending_rows = []
            _ingest_threads = []
            for _pr in _pending_rows:
                try:
                    _t = threading.Thread(
                        target=app._ingest_attachment_background,
                        kwargs={
                            "attachment_id": int(_pr["Id"]),
                            "conversation_id": str(_pr["ConversationId"]),
                            "object_key": str(_pr["ObjectKey"]),
                            "kind": str(_pr["Kind"]),
                        },
                        name=f"sandbox-sync-{_pr['Id']}",
                        daemon=True,
                    )
                    _t.start()
                    _ingest_threads.append(_t)
                except Exception:
                    # fail-open: 첨부 ingest 스레드 기동 실패는 ask 를 막지 않으나 가시화 (해당 첨부 미처리).
                    logging.getLogger(__name__).warning(
                        "ask: attachment ingest thread spawn failed (attachment_id=%s)",
                        _pr.get("Id"), exc_info=True,
                    )
            # LLM 호출 전 최대 25s 대기 — 대부분의 소형 파일은 이 내에 완료.
            for _t in _ingest_threads:
                try:
                    _t.join(timeout=25)
                except Exception:
                    pass

        # TASK-0107: attachment sandbox 스키마를 allowed_schemas_for_run 에 추가.
        # WebProductDatabases 기반 whitelist 는 동적 생성 sandbox 스키마를 모르므로
        # 요청된 attachment_ids 의 MetaJson 에서 sandbox_schema_name 을 읽어 보충한다.
        # allowed_schemas_for_run 이 None (whitelist 미적용) 이면 아무 작업 없음.
        if attachment_ids_clean and allowed_schemas_for_run is not None:
            try:
                # TASK-0277: read cutover — PG 우선(IDOR AccountId 가드 동형, fail-closed: 누락 시
                # 해당 sandbox 미허용=쿼리 거부로 안전). 실패 시 MySQL 폴백. 행 shape 는 (MetaJson,) 유지.
                _sb_rows = None
                try:
                    from web.modules import attachment_pg_mirror as _apm
                    if _apm.read_pg_enabled():
                        _sb_rows = [
                            (_m,) for _m in _apm.pg_select_ingested_meta(
                                conv_id, int(account["id"]), attachment_ids_clean)
                        ]
                except Exception:
                    _sb_rows = None
                    logging.getLogger(__name__).warning(
                        "ask: sandbox allowlist PG read failed → MySQL fallback", exc_info=True)
                if _sb_rows is None:
                    _sb_placeholders = ", ".join(["%s"] * len(attachment_ids_clean))
                    # TASK-0284: ConversationId 스코프(대화 접근권은 ask 가 게이트), 미결정 시 AccountId 폴백.
                    if conv_id:
                        _sb_col, _sb_val = "ConversationId", str(conv_id)
                    else:
                        _sb_col, _sb_val = "AccountId", int(account["id"])
                    _sb_cur = conn.cursor()
                    _sb_cur.execute(
                        f"SELECT MetaJson FROM WebConversationAttachments "
                        f"WHERE Id IN ({_sb_placeholders}) AND {_sb_col} = %s AND UploadStatus = 'ingested' "
                        f"AND Kind IN ('csv','xlsx') AND DeletedAt IS NULL",
                        # TASK-0284: 타 대화 ingested 첨부의 sandbox 스키마를 allowlist 에 추가하지 못하도록
                        # ConversationId 한정 (sandbox 교차-대화 접근 차단 — TASK-0132 의 계정 가드를 대화 단위로 일반화).
                        tuple(attachment_ids_clean) + (_sb_val,),
                    )
                    _sb_rows = _sb_cur.fetchall() or []
                    _sb_cur.close()
                _sandbox_schemas: list[str] = []
                for _sbr in _sb_rows:
                    try:
                        _meta = json.loads(_sbr[0] or "{}") if _sbr[0] else {}
                        _sn = str(_meta.get("sandbox_schema_name") or "").strip()
                        if _sn.startswith("agent_attachment_") and _sn not in _sandbox_schemas:
                            _sandbox_schemas.append(_sn)
                    except Exception:
                        pass
                if _sandbox_schemas:
                    allowed_schemas_for_run = list(allowed_schemas_for_run) + _sandbox_schemas
            except Exception:
                pass

        # TASK-0094 Sprint 2 (S2.4) — vision inline image pre-fetch.
        # vision 미지원 모델 / image kind 0 → (None, 0, []) — 본 분기 skip.
        # 정상 → env ATTACHMENT_IMAGE_INLINE_PATH 로 path 전달 + finally cleanup.
        vision_inline_path: str | None = None
        vision_inline_count = 0
        vision_audit_attachments: list[dict[str, Any]] = []
        try:
            (
                _vision_path,
                _vision_count,
                _vision_audit,
            ) = app._prepare_vision_inline_images(
                conn,
                int(account["id"]),
                attachment_ids_clean,
                model=model,
                conversation_id=conv_id,
            )
        except Exception:
            _vision_path, _vision_count, _vision_audit = None, 0, []
        if _vision_path:
            vision_inline_path = _vision_path
            vision_inline_count = int(_vision_count or 0)
            vision_audit_attachments = list(_vision_audit or [])
            # TASK-0137: inline image path 는 contextvar kwarg (image_inline_path) 로 전달.

        # TASK-0124 — text kind 첨부파일 내용 pre-fetch.
        # SQL/코드/텍스트 파일은 sandbox ingest 대상이 아니므로 MinIO 에서 직접 읽어
        # env ATTACHMENT_TEXT_INLINE_PATH 로 agent_core 에 전달.
        text_inline_path: str | None = None
        if attachment_ids_clean:
            try:
                text_inline_path = app._prepare_text_inline_attachments(
                    conn,
                    int(account["id"]),
                    attachment_ids_clean,
                    conversation_id=conv_id,
                )
            except Exception:
                text_inline_path = None
        # TASK-0137: inline text path 는 contextvar kwarg (text_inline_path) 로 전달.

        # gc-ask-sender-attrib (feature-0009): 그룹 대화 발신이면 actor username 을 sender_username
        # 으로 실어, _run_agent_core 의 user 메시지 표시 store 미러 meta 가 실제 발신자 프로필로
        # 표시되게 한다(미주입 시 FE 가 대화 owner=생성자 프로필로 폴백 → 오귀속). 1:1·신규 대화는
        # None → 기존 동작(미러 meta 없음) 무변경. 조회 실패 시 _conversation_is_group=False 폴백.
        _sender_username_for_run = (
            str(account.get("username") or "")
            if app._conversation_is_group(conv_id or "") else None
        )

        # feature-0003 reasoning-effort-selector: 이 요청의 추론 강도를 대화별로 영구 저장(KV)해,
        # 새로고침·재접속·대화 전환 후에도 마지막 선택이 복원되게 한다(/api/history 가 hydration).
        # product 의 turn-단위 캡처 패턴과 정합 — 저장은 '다음 로드'용이고, 이번 run 은 run_kwargs
        # 로 캡처한 값으로 끝까지 실행된다(in-flight 영향 0). best-effort: 저장 실패는 답변을 막지 않음.
        # 명시 레벨(reasoning_level 이 진리값)일 때만 저장 — 부재(None)면 기존 저장값·모델 기본을 보존.
        if conv_id and reasoning_level:
            try:
                app.save_memory_kv(conn, conv_id, "reasoning_level", reasoning_level)
            except Exception:
                logging.getLogger(__name__).warning(
                    "ask: reasoning_level KV save failed (conversation_id=%s)",
                    conv_id, exc_info=True,
                )

        # feature-0003 model-persist: 이 요청에 **명시 지정된** 모델을 (대화, 요청 계정)별로 영구
        # 저장(KV)해, 새로고침·재접속·대화 전환 후 복귀 시 composer 선택기가 마지막 요청 모델로
        # 복원되게 한다(/api/history 가 hydration). 위 reasoning_level 저장과 동일 계약:
        #   - 저장은 '다음 로드'용이고 이번 run 은 run_kwargs 로 캡처한 값으로 끝까지 실행(in-flight 영향 0)
        #   - best-effort — 저장 실패는 답변을 막지 않는다
        #   - model_explicit=False(내부 재dispatch 등)면 기존 저장값을 보존한다(덮어쓰지 않음)
        # 신규 대화(+ 새 대화)는 KV 가 비어 있으므로 첫 요청 전까지 프론트 기본값(haiku)이 유지된다.
        #
        # **세션 기본값과 같으면 빈 값으로 지운다(= '기본값에서의 이탈'만 저장, 적대 리뷰 C2)**:
        # 웹 클라이언트는 사용자가 선택기를 건드리지 않아도 항상 model 을 실어 보내므로, 값을 그대로
        # 저장하면 모든 대화가 "첫 전송 시점의 기본값"에 영구 고정되어 이후 운영이 기본 모델을 올려도
        # 기존 대화에는 영원히 반영되지 않는다. 기본값과 같을 때 지우면 복원 결과(=기본값)는 동일하면서
        # 기본값 변경이 자연히 따라온다. 사용자가 명시로 기본값을 다시 고른 경우에도 같은 경로로 해제된다.
        _model_save_key = _model_kv_key(account)  # "" = 계정 식별 불가 → 저장 skip(fail-closed)
        if conv_id and model_explicit and _model_save_key:
            try:
                _default_model = app._resolve_session_default_model()
            except Exception:
                _default_model = API_DEFAULT_MODEL
            try:
                app.save_memory_kv(
                    conn, conv_id, _model_save_key,
                    "" if model == _default_model else model,
                )
            except Exception:
                logging.getLogger(__name__).warning(
                    "ask: model KV save failed (conversation_id=%s)",
                    conv_id, exc_info=True,
                )

        # TASK-0169: 실행 dispatch — inprocess(현행 to_thread) | worker(ask_jobs enqueue +
        # 내부 attach). 두 경로 모두 동일 shape 의 agent_result dict 반환(동기 응답 계약 유지).
        agent_result = await app._dispatch_ask_run(
            conn=conn,
            account=account,
            conv_id=conv_id,
            request=request,  # TASK-0241: attach 루프의 client-disconnect 감지용(웹 슬롯 즉시 반납).
            inproc_fn=_run_agent_core,
            run_kwargs=dict(
                user_message=message,
                conversation_id=conv_id or None,
                conv_file=app._account_conv_file(int(account["id"])),
                model=model,
                temperature=temp_value,
                output_mode="json",
                product_id=product_id_for_run,
                role_id=role_id_for_run,
                account_id=int(account["id"]),
                sender_username=_sender_username_for_run,  # gc-ask-sender-attrib: 그룹 한정 발신자 귀속
                allowed_schemas=allowed_schemas_for_run,
                product_mode=product_mode_for_run,
                # TASK-0137: 첨부 메타를 os.environ 전역 대신 요청별 contextvar kwarg 로 전달.
                attachment_ids=attachment_ids_clean,
                new_attachment_ids=new_attachment_ids_clean,
                image_inline_path=vision_inline_path,
                text_inline_path=text_inline_path,
                reasoning_level=reasoning_level,  # feature-0003: 사용자 지정 추론 강도
            ),
        )
        # worker mode 의 빠른 실패(readiness 503 / slot 429 / enqueue 500)는 표준 에러로 표면화.
        _dispatch_http_status = int(agent_result.get("_http_status") or 0)
        if _dispatch_http_status and _dispatch_http_status != 200:
            conn.close()
            return app._json_error(
                str(agent_result.get("error") or "요청 처리에 실패했습니다."),
                _dispatch_http_status,
            )
        # 첨부 inline temp cleanup. worker mode 는 worker 가 terminal 시 정리(+고아 reaper)
        # 하므로 web 은 손대지 않는다(requeue read-after-delete 방지 — M6). inprocess 만 정리.
        if not app._is_worker_mode():
            app._cleanup_vision_inline(vision_inline_path)
            app._cleanup_text_inline(text_inline_path)
        vision_inline_path = None
        text_inline_path = None

        # Sprint 2 (S2.5) — attachment.vision.invoke audit dispatch.
        # vision_inline_count > 0 일 때만 (실제로 image 가 inline 송신된 경우).
        # agent_result.error 가 있으면 status='failure' + error_reason 기록.
        _agent_error = str(agent_result.get("error") or "").strip()
        _vision_conv_id = str(agent_result.get("conversation_id") or conv_id or "")
        if vision_inline_count > 0:
            try:
                app._audit_user_action(
                    conn,
                    request,
                    account,
                    action="attachment.vision.invoke",
                    resource_type="conversation",
                    resource_id=_vision_conv_id,
                    request_ctx={
                        "provider": app._model_to_llm_provider(model),
                        "model": model,
                        "conversation_id": _vision_conv_id,
                        "attachment_count": vision_inline_count,
                        "attachment_metas": vision_audit_attachments,
                        "status": "failure" if _agent_error else "success",
                        "error_reason": _agent_error or None,
                    },
                )
            except Exception:
                # audit 실패는 사용자 응답을 막지 않음 (fail-open, Sprint 1 패턴).
                pass

            # Sprint 2 (S2.6, D19) — vision invoke 성공 시 WebAttachmentDerivedMessages
            # join row INSERT. D9 share redact 가 `_meta_has_attachment_derived` 검사
            # (agent_core 가 mirror 시 MetaJson.attachment_derived=True 추가) +
            # 본 join 으로 어떤 attachment 가 derive 했는지 추적.
            # fail-open: INSERT 실패는 사용자 응답 차단 안 함.
            if not _agent_error and _vision_conv_id:
                try:
                    _latest_msg = app._load_latest_assistant_message(conn, _vision_conv_id)
                    _msg_id = int(_latest_msg.get("id") or 0)
                    if _msg_id > 0 and vision_audit_attachments:
                        _cur_d = conn.cursor()
                        _derived_ids: list[int] = []
                        try:
                            for _att in vision_audit_attachments:
                                _att_id = int(_att.get("attachment_id") or 0)
                                if _att_id <= 0:
                                    continue
                                _cur_d.execute(
                                    """
                                    INSERT INTO WebAttachmentDerivedMessages
                                        (AttachmentId, MessageId, DerivationType)
                                    VALUES (%s, %s, 'vision_analysis')
                                    """,
                                    (_att_id, _msg_id),
                                )
                                try:
                                    _derived_ids.append(int(_cur_d.lastrowid or 0))
                                except Exception:
                                    pass
                            conn.commit()
                            # TASK-0277: dual-write — vision 파생 join 행을 PG 로 미러(flag-gated, fail-soft).
                            try:
                                from web.modules import attachment_pg_mirror as _apm
                                _apm.mirror_derived_messages(conn, [i for i in _derived_ids if i])
                            except Exception:
                                pass
                        finally:
                            _cur_d.close()
                except Exception:
                    # best-effort: vision 파생 메시지 provenance 기록 실패는 응답을 막지 않는다.
                    logging.getLogger(__name__).warning(
                        "ask: vision derived-message link write failed (conversation_id=%s)",
                        _vision_conv_id, exc_info=True,
                    )
        conversation_id = str(agent_result.get("conversation_id") or "").strip()
        if conversation_id:
            app._assign_conversation_owner(conn, conversation_id, int(account["id"]))
            app._set_account_current_conversation(conn, int(account["id"]), conversation_id)
            account["last_conversation_id"] = conversation_id
            try:
                Path(app._account_conv_file(int(account["id"]))).write_text(conversation_id, encoding="utf-8")
            except Exception:
                # best-effort: 계정별 현재 대화 포인터 파일 기록 실패는 응답을 막지 않는다 (fail-open).
                logging.getLogger(__name__).warning(
                    "ask: account current-conversation pointer write failed (account_id=%s)",
                    account.get("id"), exc_info=True,
                )

        render_output = agent_result.get("answer", "")
        render_sql = agent_result.get("executed_sql", "")
        render_steps = agent_result.get("steps", [])
        render_csv_paths = agent_result.get("result_csv_paths", [])
        render_rationale = agent_result.get("rationale", "")
        if conversation_id:
            latest_message = app._load_latest_assistant_message(conn, conversation_id)
            latest_meta = latest_message.get("meta") if isinstance(latest_message, dict) else {}
            if latest_message.get("content"):
                render_output = latest_message.get("content", render_output)
            if isinstance(latest_meta, dict):
                if latest_meta.get("sql"):
                    render_sql = latest_meta.get("sql", render_sql)
                latest_steps = latest_meta.get("steps")
                if isinstance(latest_steps, list) and latest_steps:
                    render_steps = latest_steps
                latest_csv_paths = latest_meta.get("csv_paths")
                if isinstance(latest_csv_paths, list) and latest_csv_paths:
                    render_csv_paths = latest_csv_paths
                if latest_meta.get("rationale"):
                    render_rationale = latest_meta.get("rationale", render_rationale)

        # TASK-0274 (Task⑥): assistant 가 답변 본문에 ```attachment-edit``` 블록을 넣었으면
        # 텍스트 계열 첨부의 새 버전으로 자동 materialize(사용자 결정). fail-open — 실패해도
        # 사용자 답변은 그대로 반환. 생성된 버전은 응답 edited_attachments 로 표면화.
        # FR-brandnew-script-attachment-delivery-gap 후속(2026-07-27): worker 모드에서는 첨부
        # 후처리(materialize+strip)를 **ask-worker 가 terminal 전이 전에 이미 수행**한다
        # (modules/ask.py `_postprocess_attachment_blocks`). 장기 run 중 이 요청이 끊겨도 첨부가
        # 만들어지도록 소유자를 워커로 옮긴 것 — 여기서 또 하면 이중 materialize 위험이 있으므로
        # inproc 모드(웹이 직접 run_agent 실행)에서만 수행하고, worker 모드는 워커 결과를 전달만 한다.
        # 게이트는 **모드가 아니라 증거** 기준(§18.8 MAJOR — 혼합 버전 배포 창): worker 가 이미
        # 후처리했다면 저장 답변에 블록이 남아있지 않으므로 여기서 할 일이 없다(no-op). 반대로
        # 블록이 **아직 남아 있다**면 워커가 구버전이거나(web 먼저 롤아웃되는 deploy 순서·
        # `deploy-web-only`) 후처리에 실패한 것이므로 web 이 self-heal 한다. 모드만으로 게이팅하면
        # 그 창에서 첨부 미생성 + 원문 영구 잔존이 된다.
        # 동시 이중 materialize 는 구조적으로 차단된다: worker 는 후처리를 마친 **뒤** KV terminal 을
        # 찍고, 이 핸들러는 그 terminal 을 보고서야 답변을 읽는다. 조기 탈출(stale/timeout)이면
        # `_build_worker_agent_result` 가 error 를 채우고 아래 조건의 `not agent_result.error` 가 막는다.
        _raw_block_left = (
            isinstance(render_output, str)
            and ("attachment-edit" in render_output or "attachment-new" in render_output)
        )
        _attach_postprocess_here = (not app._is_worker_mode()) or _raw_block_left
        if _raw_block_left and app._is_worker_mode():
            logging.getLogger(__name__).warning(
                "ask: worker 후처리 미완(첨부 블록 잔존) — web self-heal 수행 (conversation_id=%s)",
                conversation_id,
            )
        materialized_attachments: list[dict[str, Any]] = []
        if _attach_postprocess_here and conversation_id and render_output and not agent_result.get("error"):
            try:
                _edit_msg_id = int((latest_message or {}).get("id") or 0) if conversation_id else 0
                materialized_attachments = app._materialize_assistant_attachment_edits(
                    conn,
                    account=account,
                    conversation_id=conversation_id,
                    answer=str(render_output),
                    message_id=_edit_msg_id,
                    request=request,
                )
                # FR-attach-delivery-truncated-by-output-cap (§18.8 [P1]): `update_attachment`
                # 도구로 전달한 첨부는 답변 본문에 블록이 없어 위 materialize 가 잡지 못한다.
                # message_id 가 확정된 지금 바인딩하지 않으면 **말풍선에 칩이 뜨지 않는다**
                # (파일은 존재하는데 보이지 않는 상태 — 도구 결과의 "칩으로 받습니다" 가 거짓이 된다).
                _tool_ids = [int(i) for i in (agent_result.get("tool_delivered_attachment_ids") or [])]
                if _tool_ids:
                    _bound = app._bind_tool_delivered_attachments(
                        conn, conversation_id=conversation_id,
                        account_id=int(account.get("id") or 0),
                        attachment_ids=_tool_ids, message_id=_edit_msg_id,
                    ) or []
                    if _bound:
                        materialized_attachments = list(_bound) + list(materialized_attachments)
                    else:
                        logging.getLogger(__name__).warning(
                            "ask: 도구 전달 첨부 %d건 바인딩 결과 0 — 칩 미노출 가능 (conversation_id=%s)",
                            len(_tool_ids), conversation_id)
            except Exception:
                # best-effort: materialize 실패는 사용자 응답을 막지 않는다.
                logging.getLogger(__name__).warning(
                    "ask: assistant attachment-edit materialize failed (conversation_id=%s)",
                    conversation_id, exc_info=True,
                )
            # ④ TASK-0285: 첨부 수정을 진행 단계(step)로 명시 출력. "단계 보기"/progress 에 노출되고
            # history 재로드에도 영속(PG agent_runtime.steps). run_id 는 이 답변 run 의 step 에서
            # 추출(step 이 없는 단순 답변이면 run_id 부재 → 기록 skip). fail-soft.
            if materialized_attachments:
                try:
                    _edit_run_id = ""
                    _edit_max_idx = -1
                    for _s in (render_steps or []):
                        if _s.get("run_id"):
                            _edit_run_id = str(_s.get("run_id") or "")
                        try:
                            _edit_max_idx = max(_edit_max_idx, int(_s.get("step_index", 0) or 0))
                        except Exception:
                            pass
                    if _edit_run_id:
                        _edit_names = ", ".join(
                            f"'{a.get('original_filename') or '파일'}'(v{a.get('version_number') or 2})"
                            for a in materialized_attachments
                        )
                        _edit_step = {
                            "step_index": _edit_max_idx + 1,
                            "action": "attachment_edit",
                            "tool": "materialize_attachment",
                            "work": f"첨부 {_edit_names}을(를) 새 버전으로 저장했습니다.",
                            "reason": "수정한 첨부를 사용자에게 새 버전으로 제공합니다.",
                            "args": {"attachment_ids": [int(a.get("id") or 0) for a in materialized_attachments]},
                        }
                        from modules.memory import save_memory_step as _save_step
                        _save_step(conn, conversation_id, _edit_run_id, _edit_step)
                        # 응답 steps 에도 즉시 반영 — 프론트가 새로고침 없이 단계로 표시.
                        render_steps = list(render_steps or []) + [
                            {**_edit_step, "run_id": _edit_run_id, "work_source": "llm", "reason_source": "llm"}
                        ]
                except Exception:
                    logging.getLogger(__name__).warning(
                        "ask: materialize step record failed (conversation_id=%s)",
                        conversation_id, exc_info=True,
                    )

        # FR-brandnew-script-attachment-delivery-gap (conversation_audit 2026-07-24): assistant 가
        # 답변 본문에 ```attachment-new``` 블록을 넣었으면(사용자가 새로 생성한 스크립트/쿼리를
        # 다운로드 첨부로 요청) source 없이 root 첨부로 materialize. 편집 경로와 동일 fail-open,
        # 응답 new_attachments 로 표면화. 편집(수정본)과 신규(새 파일)를 별도 리스트로 추적한다.
        new_attachments: list[dict[str, Any]] = []
        if _attach_postprocess_here and conversation_id and render_output and not agent_result.get("error"):
            try:
                _new_msg_id = int((latest_message or {}).get("id") or 0) if conversation_id else 0
                new_attachments = app._materialize_assistant_attachment_new(
                    conn,
                    account=account,
                    conversation_id=conversation_id,
                    answer=str(render_output),
                    message_id=_new_msg_id,
                    request=request,
                    # turn 당 개수 cap 을 편집 경로와 합산(§18.8 MINOR): 이미 materialize 된 편집 수를 뺀 잔여.
                    remaining_count=app._ASSISTANT_EDIT_COUNT_CAP - len(materialized_attachments),
                )
            except Exception:
                logging.getLogger(__name__).warning(
                    "ask: assistant attachment-new materialize failed (conversation_id=%s)",
                    conversation_id, exc_info=True,
                )
            if new_attachments:
                try:
                    _new_run_id = ""
                    _new_max_idx = -1
                    for _s in (render_steps or []):
                        if _s.get("run_id"):
                            _new_run_id = str(_s.get("run_id") or "")
                        try:
                            _new_max_idx = max(_new_max_idx, int(_s.get("step_index", 0) or 0))
                        except Exception:
                            pass
                    if _new_run_id:
                        _new_names = ", ".join(
                            f"'{a.get('original_filename') or '파일'}'" for a in new_attachments
                        )
                        _new_step = {
                            "step_index": _new_max_idx + 1,
                            "action": "attachment_create",
                            "tool": "materialize_attachment",
                            "work": f"새 첨부 {_new_names}을(를) 파일로 저장했습니다.",
                            "reason": "생성한 스크립트를 사용자에게 다운로드 첨부로 제공합니다.",
                            "args": {"attachment_ids": [int(a.get("id") or 0) for a in new_attachments]},
                        }
                        from modules.memory import save_memory_step as _save_step
                        _save_step(conn, conversation_id, _new_run_id, _new_step)
                        render_steps = list(render_steps or []) + [
                            {**_new_step, "run_id": _new_run_id, "work_source": "llm", "reason_source": "llm"}
                        ]
                except Exception:
                    logging.getLogger(__name__).warning(
                        "ask: attachment-new step record failed (conversation_id=%s)",
                        conversation_id, exc_info=True,
                    )

        # ★ TASK-0286: attachment-edit 블록을 답변에서 제거 → 전체 수정본 본문이 채팅에 노출되지
        # 않게 한다(변경점은 diff 블록으로, 전체 수정본은 첨부 새 버전으로 전달). materialize 성공분은
        # "📎 수정본 전달" 명시 문구로 치환. render_output(응답)뿐 아니라 DB content 도 갱신해
        # history 재로드·LLM 재컨텍스트에서도 전체 본문이 사라지게 한다. error 무관 — 블록 텍스트가
        # 남아 있으면 항상 제거(본문 노출 방지).
        # ⚠ worker 모드에서는 이 strip 도 수행하지 않는다(§18.8 BLOCKER). 후처리 소유자는 워커이고,
        # 여기서 빈 materialize 목록으로 strip 하면 **첨부를 만들지 않은 채 블록만 지워 DB 에 저장**
        # → 워커가 뒤이어 읽을 때 블록이 사라져 첨부가 영영 생성되지 않고 스크립트 본문도 소실된다
        # (원 결함보다 악화). 워커의 후처리가 strip 까지 책임진다.
        if _attach_postprocess_here and conversation_id and isinstance(render_output, str) and "attachment-edit" in render_output:
            _stripped_out = app._strip_attachment_edit_blocks(render_output, materialized_attachments)
            if _stripped_out != render_output:
                render_output = _stripped_out
                try:
                    _strip_msg_id = int((latest_message or {}).get("id") or 0)
                    if _strip_msg_id > 0:
                        app._update_assistant_message_content(conn, conversation_id, _strip_msg_id, _stripped_out)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "ask: attachment-edit strip content update failed (conversation_id=%s)",
                        conversation_id, exc_info=True,
                    )

        # FR-brandnew-script-attachment-delivery-gap: attachment-new 블록도 답변에서 제거 →
        # 전체 스크립트 본문이 채팅에 노출되지 않게 하고 "📎 첨부 전달" 안내로 치환(전체 파일은
        # 다운로드 첨부로 전달). 편집 strip 과 동일 정책 — DB content 도 갱신.
        # worker 모드 미수행 이유는 위 attachment-edit strip 주석과 동일(§18.8 BLOCKER).
        if _attach_postprocess_here and conversation_id and isinstance(render_output, str) and "attachment-new" in render_output:
            _stripped_new = app._strip_attachment_new_blocks(render_output, new_attachments)
            if _stripped_new != render_output:
                render_output = _stripped_new
                try:
                    _strip_new_msg_id = int((latest_message or {}).get("id") or 0)
                    if _strip_new_msg_id > 0:
                        app._update_assistant_message_content(conn, conversation_id, _strip_new_msg_id, _stripped_new)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "ask: attachment-new strip content update failed (conversation_id=%s)",
                        conversation_id, exc_info=True,
                    )

        result = {
            "output": render_output,
            "executed_sql": render_sql,
            "conversation_id": conversation_id,
            "steps": render_steps,
            "result_csv_paths": render_csv_paths,
            "rationale": render_rationale,
            "error": agent_result.get("error", ""),
            "duration_ms": round((time.time() - start_ts) * 1000, 2),
        }
        # worker 모드: 후처리는 워커가 수행했으므로 그 결과(첨부 목록)를 응답으로 전달(inproc 패리티
        # — 프런트 토스트/표면화). inproc 모드면 위에서 web 이 직접 materialize 한 목록을 쓴다.
        if not _attach_postprocess_here:
            _w_edited = agent_result.get("edited_attachments")
            _w_new = agent_result.get("new_attachments")
            if isinstance(_w_edited, list) and _w_edited:
                materialized_attachments = _w_edited
            if isinstance(_w_new, list) and _w_new:
                new_attachments = _w_new
        if materialized_attachments:
            result["edited_attachments"] = materialized_attachments
        if new_attachments:
            result["new_attachments"] = new_attachments
        conn.close()
        return JSONResponse(result)
    finally:
        app._release_request_slot(slot_key)
        # TASK-0124: exception 경로에서도 text inline temp file 정리.
        # TASK-0169 (M6): worker mode 는 worker 가 terminal 시 정리(+고아 reaper)하므로
        # web 은 손대지 않는다(enqueue 후 worker 가 아직 읽는 중이면 read-after-delete).
        if not app._is_worker_mode():
            try:
                app._cleanup_text_inline(locals().get("text_inline_path"))
            except Exception:
                pass


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (19종). app 전역은 app.X 동적 참조. ====

def _set_account_current_conversation(conn, account_id: int, conversation_id: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE WebAccounts SET LastConversationId = %s WHERE Id = %s",
        (str(conversation_id or "").strip() or None, int(account_id)),
    )
    cur.close()

def _assign_conversation_owner(conn, conversation_id: str, account_id: int, *, force: bool = False) -> None:
    if not conversation_id:
        return
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        app._ensure_conversation_row(conn, conversation_id)
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                if force:
                    pgcur.execute(
                        "UPDATE agent_runtime.core_conversations "
                        "SET owner_account_id = %s, owner_assigned_at = COALESCE(owner_assigned_at, NOW()) "
                        "WHERE conversation_id = %s",
                        (int(account_id), conversation_id),
                    )
                else:
                    pgcur.execute(
                        "UPDATE agent_runtime.core_conversations "
                        "SET owner_account_id = %s, owner_assigned_at = COALESCE(owner_assigned_at, NOW()) "
                        "WHERE conversation_id = %s AND owner_account_id IS NULL",
                        (int(account_id), conversation_id),
                    )
            pg.close()
        except Exception:
            # fail-open: 소유자 지정 실패는 흐름을 막지 않으나 조용한 PG 쓰기 실패를 가시화.
            logging.getLogger(__name__).warning(
                "_assign_conversation_owner: PG owner update failed "
                "(conversation_id=%s account_id=%s force=%s)",
                conversation_id, account_id, force, exc_info=True,
            )
        return
    app._ensure_conversation_row(conn, conversation_id)
    cur = conn.cursor()
    if force:
        cur.execute(
            """
UPDATE AgentCoreConversations
SET owner_account_id = %s,
    owner_assigned_at = COALESCE(owner_assigned_at, CURRENT_TIMESTAMP)
WHERE conversation_id = %s
            """,
            (int(account_id), conversation_id),
        )
    else:
        cur.execute(
            """
UPDATE AgentCoreConversations
SET owner_account_id = %s,
    owner_assigned_at = COALESCE(owner_assigned_at, CURRENT_TIMESTAMP)
WHERE conversation_id = %s
  AND owner_account_id IS NULL
            """,
            (int(account_id), conversation_id),
        )
    cur.close()

def _repair_current_conversation(
    conn,
    account: dict[str, Any],
    items: list[dict[str, Any]] | None = None,
    *,
    create_if_missing: bool = True,
    force_new: bool = False,
) -> str:
    current_id = str(account.get("last_conversation_id") or "").strip()
    visible_items = items if items is not None else app._list_conversations(limit=200, account=account, conn=conn)
    visible_ids = {str(item.get("id") or "") for item in visible_items if str(item.get("id") or "").strip()}
    if not force_new and current_id and current_id in visible_ids:
        return current_id
    next_id = ""
    if not force_new:
        next_id = next((str(item.get("id") or "").strip() for item in visible_items if str(item.get("id") or "").strip()), "")
    if not next_id and create_if_missing and app._account_has_permission(account, "conversation.create"):
        from agent_core import create_new_conversation as _create_conv

        next_id = _create_conv(conv_file=app._account_conv_file(int(account["id"])))
        app._assign_conversation_owner(conn, next_id, int(account["id"]), force=True)
    app._set_account_current_conversation(conn, int(account["id"]), next_id)
    account["last_conversation_id"] = next_id
    return next_id

def _model_supports_temperature(value: str) -> bool:
    return app.model_supports_temperature(value)

def _acquire_request_slot(session_id: str) -> bool:
    with app._ACTIVE_REQUESTS_LOCK:
        current = app._ACTIVE_REQUESTS.get(session_id, 0)
        if current >= app.WEB_PARALLEL_LIMIT:
            return False
        app._ACTIVE_REQUESTS[session_id] = current + 1
        return True

def _release_request_slot(session_id: str) -> None:
    with app._ACTIVE_REQUESTS_LOCK:
        current = app._ACTIVE_REQUESTS.get(session_id, 0) - 1
        if current <= 0:
            app._ACTIVE_REQUESTS.pop(session_id, None)
        else:
            app._ACTIVE_REQUESTS[session_id] = current

def _get_default_product_id(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
SELECT Id FROM WebProducts
WHERE IsActive = 1
ORDER BY IsDefault DESC, SortOrder ASC, Id ASC
LIMIT 1
        """
    )
    row = cur.fetchone()
    cur.close()
    return int((row or (0,))[0] or 0)

def _product_allowed_schemas(conn, product_id: int) -> list[str]:
    if product_id <= 0:
        return []
    cur = conn.cursor()
    cur.execute(
        "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s ORDER BY SortOrder, SchemaName",
        (int(product_id),),
    )
    rows = cur.fetchall() or []
    cur.close()
    return [str(r[0]) for r in rows if r and r[0]]

def _product_has_datasource(conn, product_id: int) -> bool:
    """TASK-0206 re-gate(5차): 제품에 datasource 가 바인딩(WebProducts.DatasourceKey 비-NULL)되어 있는지.

    DB-단위 모델에서 데이터는 데이터소스에 종속된다 — 미바인딩 제품은 접근 0(allowed=[]). 조회 실패 시
    보수적으로 False(미바인딩 취급, fail-closed).

    TASK-0228 (1:N): primary(WebProducts.DatasourceKey) 가 NULL 이어도 join 테이블(WebProductDatasources)에
    바인딩이 있으면 True. 단일 바인딩(레거시) 제품은 종전과 동일하게 primary 만으로 True."""
    if product_id <= 0:
        return False
    cur = conn.cursor()
    try:
        cur.execute("SELECT DatasourceKey FROM WebProducts WHERE Id = %s LIMIT 1", (int(product_id),))
        r = cur.fetchone()
        if r and r[0] and str(r[0]).strip():
            return True
        # 1:N: primary 미설정이어도 join 바인딩이 있으면 datasource 보유로 본다.
        try:
            cur.execute(
                "SELECT 1 FROM WebProductDatasources WHERE ProductId = %s LIMIT 1", (int(product_id),)
            )
            return bool(cur.fetchone())
        except Exception:
            return False
    except Exception:
        return False
    finally:
        cur.close()

def _log_search_activity(
    conn,
    account_id: int,
    action: str,
    target_owner_id: int | None,
    query: str | None,
    matched_count: int,
) -> None:
    """REQ-20260518-0010 (TASK-0072): cross-account body search audit. PIPA §29.

    TASK-0086 (2026-05-20): legacy `WebAccountActivity` INSERT 제거 — TASK-0073
    Phase A2 의 dual write 종료. dispatcher mirror (`record_audit_event` →
    WebAuditEvents) 가 단일 source-of-truth. signature transparent 보존 (caller
    변경 0). dispatcher fail 시 stderr log 만 + main flow 진행 (user endpoint
    fail-open 패턴 TASK-0072 답습).

    query 평문 저장 금지 — SHA-256 hex 만 저장.
    `ChangeJson._legacy_source="WebAccountActivity"` 표식은 TASK-0086 backup
    (`artifacts/mysql-backup/WebAccountActivity-*.sql`) cross-reference 위해 보존.
    """
    import hashlib
    query_hash: str | None = None
    if query:
        normalized = query.strip()
        if normalized:
            query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    # TASK-0086 (2026-05-20): dispatcher only — WebAccountActivity legacy table DROP 완료.
    try:
        app.record_audit_event(
            conn,
            actor={
                "account_id": int(account_id),
                "actor_type": "account",
            },
            action=str(action)[:64],
            resource_type="conversation",
            resource_id=str(target_owner_id) if target_owner_id is not None else None,
            change_json={
                "query_hash": query_hash,
                "matched_count": int(matched_count),
                "_legacy_source": "WebAccountActivity",
            },
            target_account_id=int(target_owner_id) if target_owner_id is not None else None,
        )
        try:
            conn.commit()
        except Exception:
            pass
    except Exception as exc:
        try:
            import sys as _sys
            _sys.stderr.write(
                f"[TASK-0086] _log_search_activity dispatcher failed: {exc}\n"
            )
        except Exception:
            pass

def _normalize_search_query(q: str | None) -> str | None:
    """Returns sanitized q (strip + length 2-200) or None if it fails the gate.
    None signals 'no body search'. REQ-20260519-0005 (TASK-0077): min char gate
    3 → 2 (사용자 결정 — 한국어 grapheme 2 char 도 의미 있는 검색어). adversarial
    risk 4: gate is applied to the *raw* user input before escape so `q="%%"`
    (post-escape len 4 but 0 literal chars) is rejected for falling under the
    raw-len-2 minimum."""
    if not q:
        return None
    s = str(q).strip()
    if len(s) < 2:
        return None
    if len(s) > 200:
        s = s[:200]
    return s

def _infer_kind(filename: str, mime_type: str) -> str:
    """서비스 자체 kind 추론. 확장자 우선 → MIME 힌트 → text/* 패턴 → 'other'.
    클라이언트 MIME 을 신뢰하지 않으므로 확장자가 일치하면 확장자 결과를 사용한다."""
    name = (filename or "").strip().lower()
    ext = name.rsplit(".", 1)[1] if "." in name else ""
    if ext:
        kind = app._EXTENSION_KIND_MAP.get(ext)
        if kind:
            return kind
    mime_lower = (mime_type or "").lower().strip()
    kind = app._MIME_KIND_HINTS.get(mime_lower)
    if kind:
        return kind
    if mime_lower.startswith("text/"):
        return "text"
    return "other"

def _strip_attachment_edit_blocks(answer: str, materialized: list[dict[str, Any]]) -> str:
    """답변에서 ```attachment-edit``` 블록을 제거하고 "📎 수정본 전달" 명시 문구로 치환(TASK-0286).

    사용자에게 전체 수정본 본문이 텍스트로 노출되는 것을 막는다 — 변경점은 diff 블록으로, 전체
    수정본은 다운로드 가능한 첨부 새 버전(materialize)으로 전달한다. materialize 가 실패(파싱은
    됐으나 가드 거부 등)한 블록도 제거해 본문 노출을 막는다(fail-open 일관). 전부 제거돼 본문이
    비면(블록만 있고 materialize 실패한 드문 경우) 원문을 유지해 빈 답변을 방지한다.
    """
    spans = app._attachment_edit_block_spans(answer)
    if not spans:
        return answer
    lines = (answer or "").split("\n")
    # 각 블록의 (open..close) 라인 전체를 제거 — 본문 내 ``` 가 있어도 절단/잔여 노출이 없다.
    remove: set[int] = set()
    for _oi, _ci, _h, _b in spans:
        remove.update(range(_oi, _ci + 1))
    stripped = "\n".join(ln for i, ln in enumerate(lines) if i not in remove)
    # 블록 제거로 생긴 과도한 빈 줄 정리.
    stripped = app.re.sub(r"\n{3,}", "\n\n", stripped).strip()
    if materialized:
        notes = "\n".join(
            f"📎 수정본 **{a.get('original_filename') or '파일'}** (v{a.get('version_number') or 2}) 을(를) "
            f"첨부 파일로 전달했습니다. 위 변경점을 확인하고 첨부에서 다운로드하세요."
            for a in materialized
        )
        stripped = (stripped + ("\n\n" if stripped else "") + notes).strip()
    return stripped or answer

def _strip_attachment_new_blocks(answer: str, materialized: list[dict[str, Any]]) -> str:
    """답변에서 ```attachment-new``` 블록을 제거하고 "📎 첨부 전달" 안내 문구로 치환.

    FR-brandnew-script-attachment-delivery-gap (conversation_audit 2026-07-24): assistant 가 새로
    생성한 전체 스크립트 본문이 채팅에 그대로 노출되는 것을 막고(사용자가 명시적으로 "본문이
    아닌 첨부로" 요청), 전체 파일은 다운로드 첨부(materialize)로 전달한다. materialize 가 실패한
    블록도 제거해 본문 노출을 막는다(fail-open 일관). 전부 제거돼 본문이 비면 원문을 유지한다.
    편집 strip(_strip_attachment_edit_blocks)과 동일 규율, 신규 첨부용 안내 문구만 다르다.
    """
    spans = app._attachment_new_block_spans(answer)
    if not spans:
        return answer
    lines = (answer or "").split("\n")
    remove: set[int] = set()
    for _oi, _ci, _h, _b in spans:
        remove.update(range(_oi, _ci + 1))
    stripped = "\n".join(ln for i, ln in enumerate(lines) if i not in remove)
    stripped = app.re.sub(r"\n{3,}", "\n\n", stripped).strip()
    if materialized:
        notes = "\n".join(
            f"📎 **{a.get('original_filename') or '파일'}** 을(를) 첨부 파일로 전달했습니다. "
            f"첨부 목록·말풍선에서 다운로드하세요."
            for a in materialized
        )
        stripped = (stripped + ("\n\n" if stripped else "") + notes).strip()
    return stripped or answer

def _update_assistant_message_content(conn, conversation_id: str, message_id: int, content: str) -> bool:
    """assistant 메시지 content 갱신(TASK-0286 attachment-edit strip 반영을 DB 에도 영속).

    `_load_latest_assistant_message` 와 동일 라우팅(PG 우선·MySQL fallback)을 따른다 — message_id 는
    그 backend 의 id 이므로 정합. history 재로드·LLM 재컨텍스트에서도 전체 본문이 사라지게 한다.
    best-effort: 실패해도 사용자 응답을 막지 않는다(render_output 은 이미 strip 됨).

    Returns: 영속 성공 여부(§18.8 MINOR — 내부에서 예외를 삼키므로 try/except 로는 실패를 알 수
    없다. 호출자가 "저장 성공했을 때만 result.answer 를 stripped 로 교체" 같은 판단을 할 수 있게
    bool 을 돌려준다). 기존 호출자는 반환값을 무시하므로 하위호환.
    """
    if not message_id or not conversation_id:
        return False
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "UPDATE agent_runtime.messages SET content = %s WHERE id = %s AND conversation_id = %s",
                    (content, int(message_id), conversation_id),
                )
            pg.commit()
        finally:
            pg.close()
        return True
    except Exception:
        logging.getLogger(__name__).warning(
            "_update_assistant_message_content: PG update failed (msg=%s) — MySQL fallback", message_id, exc_info=True)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE AgentMemoryMessages SET Content = %s WHERE Id = %s AND ConversationId = %s",
                (content, int(message_id), conversation_id),
            )
            conn.commit()
        finally:
            cur.close()
        return True
    except Exception:
        logging.getLogger(__name__).warning(
            "_update_assistant_message_content: MySQL update failed (msg=%s)", message_id, exc_info=True)
    return False

def _model_to_llm_provider(model: str | None) -> str | None:
    """vision invoke 모델 → LLM provider 식별자 매핑 (audit 용).

    feature-0007 (bedrock) 머지 후 catalog 는 claude-* 만 → 'anthropic'. backward
    -compat: gpt-* → 'openai'. Local LLM (auto/edge/core/code) 은 supports_vision
    =False 라 본 매핑이 호출되기 전 차단되지만 안전하게 'local' 매핑. catalog
    미등록 alias → None (vision 진입 안 함).
    """
    if not model:
        return None
    m = str(model).strip().lower()
    if m.startswith("claude-"):
        return "anthropic"
    if m.startswith("gpt-"):
        return "openai"
    if m in ("auto", "edge", "core", "code"):
        return "local"
    return None

async def _dispatch_ask_run(*, conn, account, conv_id, run_kwargs, inproc_fn, request=None):
    """agent 실행을 mode 에 따라 분기. 두 경로 모두 동일 shape 의 agent_result dict 반환.

    - inprocess(기본): 현행 asyncio.to_thread(run_agent, …). 동작 무변경.
    - worker: ask_jobs enqueue 후 KV last_status 를 내부 long-poll attach 해 동기 응답
      계약 유지(클라 무변경). 결과 shape 는 ask_jobs.result_json 으로 패리티.
    """
    if not app._is_worker_mode():
        return await asyncio.to_thread(inproc_fn, **run_kwargs)
    return await app._dispatch_ask_run_worker(conn=conn, account=account,
                                          conv_id=conv_id, run_kwargs=run_kwargs,
                                          request=request)

def _make_internal_ask_request(request: Request, body: dict[str, Any]) -> Request:
    """원본 request 의 scope(쿠키/헤더/클라이언트 IP 포함)를 복제하고, body 만 새 JSON 으로 교체한
    내부 재dispatch 용 Starlette Request 를 만든다. `ask()` 가 `await request.json()` 으로 읽는다.

    auth(_get_authenticated_account)·audit(_build_actor_from_request) 는 scope 의 headers 에서
    세션 쿠키·UA·IP 를 읽으므로, scope 복제만으로 동일 인증 컨텍스트가 유지된다(별도 토큰 전달 불필요).
    """
    from starlette.requests import Request as _StarletteRequest

    raw = json.dumps(body).encode("utf-8")
    # scope 의 path/route 는 ask 의 본문 로직과 무관(핸들러를 직접 호출). headers 만 보존되면 충분.
    new_scope = dict(request.scope)
    new_scope["type"] = "http"

    _orig_receive = request._receive  # 원본 client 의 ASGI receive(연결 상태 진실).
    _sent = {"done": False}

    async def _receive():
        # 1) 첫 호출: 정정 메시지 body 를 1회 공급(ask 의 await request.json()).
        if not _sent["done"]:
            _sent["done"] = True
            return {"type": "http.request", "body": raw, "more_body": False}
        # 2) 이후 호출(worker mode attach 루프의 is_disconnected 폴링): 원본 client 의 receive 로
        #    위임 → 실제 브라우저가 fix-with-ai fetch 를 끊으면 그대로 disconnect 가 전파된다.
        #    (synthetic 이 즉시 http.disconnect 를 돌려주면 run 이 조기 중단되는 버그 방지.)
        return await _orig_receive()

    return _StarletteRequest(new_scope, _receive)

def _delete_conversation_impl(
    conn,
    account: dict[str, Any],
    conversation_id: str,
    *,
    force: bool = False,
    confirm_text: str = "",
) -> dict[str, Any]:
    """TASK-0273: "삭제" 를 soft-archive(보관)로 전환. 데이터·첨부 hard-delete 안 함.

    보관 = (1) 소유자 목록 숨김(_list_conversations archived_at IS NULL) + (2) 진행 차단
    (_conversation_block_info) + (3) 데이터 보존(admin 조회·fork 참조 가능). 진행 중 대화는
    force+confirm 시 run 취소 후 보관(첨부는 보존 — cascade soft-delete 안 함).
    반환 status: 'archived' | 'archived_pending' | 'failed'(기존 호환 위해 'deleted*' 도 매핑).
    """
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return {"status": "failed", "reason": "empty_conversation_id"}
    if not app._account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.delete.own",
        "conversation.delete.any",
    ):
        return {"status": "failed", "reason": "forbidden"}
    # feature-0009 gc-group-authz-flag (#1): 보관(archive)은 대화 보유자(owner) 전용. 위 게이트는
    # 그룹 대화 '열람' 경계(멤버 포함, '열람 ≠ 발화')라 conversation.delete.own 권한 멤버도 통과하므로,
    # 소유 메타 변경(보관)에는 2차 owner 게이트를 둔다. admin(.any)은 오용 방지 관리 일관성으로 우회 허용.
    # owner_account_id 가 *확정된* 대화에서 actor 가 그 owner 가 아닐 때만 차단 — owner 미기록(NULL)
    # 레거시 대화는 1차 게이트(소유/멤버) 판정을 존중해 fail-open(실소유자 lockout 방지).
    _archive_owner_id = app._conversation_owner_account_id(conn, conversation_id)
    if (
        not app._account_has_permission(account, "conversation.delete.any")
        and _archive_owner_id is not None
        and _archive_owner_id != int(account.get("id") or 0)
    ):
        return {"status": "failed", "reason": "forbidden"}
    try:
        app.cleanup_pending_delete_conversations(conn)
        acct_id = int(account.get("id") or 0)
        if app.is_processing_conversation(conn, conversation_id):
            if not force:
                return {"status": "failed", "reason": "processing"}
            if confirm_text not in ("삭제", "보관"):
                return {"status": "failed", "reason": "confirm_text_mismatch"}
            # 진행 중 run 은 취소하되, 데이터는 hard-delete 하지 않고 보관으로 동결.
            run_id = str(app.load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
            app.mark_cancel_requested(conn, conversation_id, run_id=run_id)
            app._archive_conversation(conn, conversation_id, acct_id)
            app._clear_accounts_current_conversation(conn, conversation_id)
            return {"status": "archived_pending"}
        # TASK-0273: 정상 대화 → 보관(UPDATE archived_at). 첨부 cascade soft-delete 안 함
        # (admin 조회·fork 참조 위해 데이터 보존). hard-delete(delete_conversation_records) 폐기.
        ok = app._archive_conversation(conn, conversation_id, acct_id)
        if not ok:
            return {"status": "failed", "reason": "db_error"}
        app._clear_accounts_current_conversation(conn, conversation_id)
        return {"status": "archived"}
    except Exception:
        return {"status": "failed", "reason": "db_error"}

def _archive_conversation(conn, conversation_id: str, account_id: int) -> bool:
    """TASK-0273: 대화를 soft-archive(보관)로 전환 — hard-delete 대신 archived_at 마킹.

    데이터·첨부는 **보존**한다(오용 방지 admin 조회·맥락 참조 fork 위해). backend-aware:
    PG 정본(agent_runtime.core_conversations) + MySQL 폴백(AgentCoreConversations).
    이미 보관된 대화는 시각·수행자 보존(archived_at IS NULL 일 때만 set). 반환 성공 여부.
    """
    ok = False
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "UPDATE agent_runtime.core_conversations "
                        "SET archived_at = now(), archived_by_account_id = %s "
                        "WHERE conversation_id = %s AND archived_at IS NULL",
                        (int(account_id) if account_id else None, conversation_id),
                    )
                pg.commit()
                ok = True
            finally:
                pg.close()
        except Exception:
            logging.getLogger(__name__).warning(
                "_archive_conversation: PG archive failed (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
            ok = False
    # MySQL 폴백 parity(production 은 PG 라 보통 미경유, 비-PG 환경 대비).
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE AgentCoreConversations "
            "SET archived_at = NOW(), archived_by_account_id = %s "
            "WHERE conversation_id = %s AND archived_at IS NULL",
            (int(account_id) if account_id else None, conversation_id),
        )
        conn.commit()
        ok = ok or True
    except Exception:
        # PG 가 정본이면 MySQL 폴백 실패는 무해(테이블 부재 등).
        pass
    return ok


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (2종). app 전역은 app.X 동적 참조. ====

def _search_rate_limit_check(
    account_id: int,
    max_per_min: int = 10,
    scope: str = "conversation_search",
) -> bool:
    """REQ-20260518-0010 (TASK-0072): in-process token bucket per (account, scope).
    True if allowed, False if quota exhausted (60s window). Single-process
    only; multi-worker deployment will allow `max_per_min` per worker.

    TASK-20260729T152000-ratelimit-scope: `scope` 가 버킷 격리 단위다. 이전에는 키가
    account_id 뿐이라 호출부 6곳이 계정당 단일 버킷을 공유했고(app.py `_RATE_LIMIT_BUCKETS`
    주석 참조), 상한이 큰 기능의 소비가 상한이 작은 기능을 즉시 차단했다. 호출부는 반드시
    자기 scope 를 명시한다 — 기본값은 본 함수의 최초 도입 호출부(본문 검색)와 동일하게 둬
    하위호환을 유지하되, 신규 호출부에서 기본값에 기대는 것은 금지(조용한 버킷 병합).
    """
    import time as _time
    now = _time.time()
    window_start = now - 60.0
    key = (int(account_id), str(scope))
    with app._RATE_LIMIT_LOCK:
        buckets = app._RATE_LIMIT_BUCKETS
        # 메모리 가드: 키 공간이 상한을 넘으면 만료(전량 window 밖) 버킷을 먼저 회수한다.
        if len(buckets) > app._RATE_LIMIT_BUCKETS_MAX_KEYS:
            for _k in [k for k, v in buckets.items() if not v or v[-1] < window_start]:
                if _k != key:
                    buckets.pop(_k, None)
        bucket = buckets.setdefault(key, [])
        while bucket and bucket[0] < window_start:
            bucket.pop(0)
        if len(bucket) >= max_per_min:
            return False
        bucket.append(now)
        return True


def _rate_limit_retry_after(account_id: int, scope: str = "conversation_search") -> int:
    """해당 (account, scope) 버킷에서 슬롯 1개가 회복될 때까지 남은 초(1~60).

    가장 오래된 소비 기록이 60s window 를 벗어나는 시점까지의 잔여 시간. 버킷이 비었으면
    (= 다른 이유로 차단됐거나 이미 회복) 1 을 반환한다. 사용자에게 "얼마나 기다리면 되는지"
    를 알려주고 `Retry-After` 헤더를 채우는 용도 — 판정 자체는 하지 않는다(읽기 전용).
    """
    import time as _time
    now = _time.time()
    with app._RATE_LIMIT_LOCK:
        bucket = app._RATE_LIMIT_BUCKETS.get((int(account_id), str(scope))) or []
        oldest = bucket[0] if bucket else None
    if oldest is None:
        return 1
    return max(1, min(60, int(60.0 - (now - oldest)) + 1))

def _clear_accounts_current_conversation(conn, conversation_id: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE WebAccounts SET LastConversationId = NULL WHERE LastConversationId = %s",
        (conversation_id,),
    )
    cur.close()


# ==== feature-0012 ITEM-10 p17 — app.py 에서 이동한 도메인 상수 (2종). ====

# D7 — 확장자 우선 kind 추론 (클라이언트 MIME 보다 신뢰도 높음).
# MIME 은 클라이언트가 잘못 보내는 경우가 많으므로 fallback 역할만 한다.
_EXTENSION_KIND_MAP: dict[str, str] = {
    "csv": "csv",
    "xlsx": "xlsx",
    "xls": "xlsx",
    "pdf": "pdf",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "webp": "image",
    "gif": "image",
    "bmp": "image",
    "tiff": "image",
    "tif": "image",
    "svg": "image",
    # 텍스트 계열 — SQL, 소스코드, 설정, 마크업 포함.
    "txt": "text",
    "md": "text",
    "markdown": "text",
    "sql": "text",
    "json": "text",
    "yaml": "text",
    "yml": "text",
    "xml": "text",
    "log": "text",
    "sh": "text",
    "bash": "text",
    "py": "text",
    "js": "text",
    "ts": "text",
    "jsx": "text",
    "tsx": "text",
    "html": "text",
    "htm": "text",
    "css": "text",
    "java": "text",
    "go": "text",
    "rb": "text",
    "php": "text",
    "c": "text",
    "cpp": "text",
    "h": "text",
    "ini": "text",
    "toml": "text",
    "conf": "text",
    "cfg": "text",
    "env": "text",
}

# MIME 힌트 테이블 — 확장자 판별 실패 시 fallback.
_MIME_KIND_HINTS: dict[str, str] = {
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xlsx",
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
    "image/gif": "image",
    "image/bmp": "image",
    "image/svg+xml": "image",
    "text/plain": "text",
    "text/markdown": "text",
    "text/html": "text",
    "application/json": "text",
    "application/xml": "text",
    "text/xml": "text",
    "text/x-sql": "text",
    "application/sql": "text",
    "text/sql": "text",
}
