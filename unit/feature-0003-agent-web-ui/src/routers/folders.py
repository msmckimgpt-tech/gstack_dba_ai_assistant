"""feature-0024-conversation-folders — 대화 폴더(프로젝트) APIRouter.

폴더는 **엄격한 개인(per-user)** 조직 오버레이다. 모든 엔드포인트는 요청 계정 스코프로만
동작하며(크로스-계정 가시성·관리 없음 — folder.*.any 폐지, 프라이버시), folder.list.own /
folder.manage.own RBAC + 폴더 소유 게이트를 적용한다. 대화 배정은 폴더 소유(요청자) + 대화
접근권(read own/any) 둘 다 통과해야 한다.

저장은 routers/_folder_store.py(PG agent_runtime). app 정본 헬퍼(get_current_account/get_conn/
require_permission/_account_can_access_conversation/_account_has_permission/_json_error)를 재사용한다.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app
from routers import _folder_store as store

INCLUDE_ORDER = 95
router = APIRouter()


def _acct_id(account: dict[str, Any]) -> int:
    return int(account.get("id") or 0)


def _folder_err(e: store.FolderError) -> JSONResponse:
    return app._json_error(e.message, e.code)


def _require_folder_owner(account: dict[str, Any], folder_id: int) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    """폴더 존재 + **소유자 전용** 게이트. (folder, error) 반환.

    ★ 폴더는 엄격한 개인 오버레이 — folder.manage.any 크로스-계정 우회 없음(프라이버시 수정).
    타 계정 폴더는 어떤 권한으로도 조회·수정·삭제·이동할 수 없다. 존재 여부도 404 로 단일화해
    타 계정 folder_id 존재 oracle 을 주지 않는다."""
    folder = store.get_folder(int(folder_id))
    if not folder or folder.get("archived_at") is not None:
        return None, app._json_error("폴더를 찾을 수 없습니다.", 404)
    if int(folder.get("owner_account_id") or 0) != _acct_id(account):
        return None, app._json_error("폴더를 찾을 수 없습니다.", 404)
    return folder, None


# ── 폴더 트리 ──────────────────────────────────────────────────────────────

@router.get("/api/folders")
async def list_folders(
    account=Depends(app.require_permission("folder.list.own")),
) -> JSONResponse:
    # ★ 항상 요청 계정 소유 폴더만 — 크로스-계정 가시성 없음(프라이버시 수정, folder.list.any 폐지).
    try:
        folders = store.list_folders(_acct_id(account))
    except Exception:
        return app._json_error("폴더 목록을 불러오지 못했습니다.", 500)
    from shared import runtime_settings
    return JSONResponse({"folders": folders, "max_depth": runtime_settings.folder_max_depth()})


@router.post("/api/folders")
async def create_folder(
    request: Request,
    account=Depends(app.require_permission("folder.manage.own")),
) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    name = str((data or {}).get("name") or "").strip()
    if not name:
        return app._json_error("폴더 이름을 입력하세요.", 400)
    if len(name) > 120:
        return app._json_error("폴더 이름이 너무 깁니다(최대 120자).", 400)
    parent = (data or {}).get("parent_folder_id")
    parent_id = int(parent) if parent not in (None, "", "null") else None
    instructions = (data or {}).get("instructions")
    if instructions is not None:
        instructions = str(instructions)
    try:
        # datasource_id/product_id 핀은 Phase 2b(접근 게이트 동반)로 이연 — 현재 저장하지 않는다
        # (inert 필드에 무권한 값 저장 방지, REV LOW-2). 스키마 컬럼은 향후 배선용으로 존치.
        folder = store.create_folder(
            _acct_id(account), name, parent_folder_id=parent_id,
            instructions=instructions,
        )
    except store.FolderError as e:
        return _folder_err(e)
    except Exception:
        return app._json_error("폴더 생성에 실패했습니다.", 500)
    return JSONResponse({"ok": True, "folder": folder})


@router.patch("/api/folders/{folder_id}")
async def update_folder(
    folder_id: int,
    request: Request,
    account=Depends(app.require_permission("folder.manage.own")),
) -> JSONResponse:
    _folder, err = _require_folder_owner(account, folder_id)
    if err:
        return err
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    kwargs: dict[str, Any] = {}
    if "name" in (data or {}):
        nm = str(data.get("name") or "").strip()
        if not nm:
            return app._json_error("폴더 이름을 입력하세요.", 400)
        if len(nm) > 120:
            return app._json_error("폴더 이름이 너무 깁니다(최대 120자).", 400)
        kwargs["name"] = nm
    if "instructions" in (data or {}):
        iv = data.get("instructions")
        kwargs["instructions"] = None if iv in (None, "") else str(iv)
    # datasource_id/product_id 핀은 Phase 2b(접근 게이트 동반)로 이연 — 여기서 받지 않는다(REV LOW-2).
    if "parent_folder_id" in (data or {}):
        pv = data.get("parent_folder_id")
        kwargs["parent_folder_id"] = None if pv in (None, "", "null") else int(pv)
    if not kwargs:
        return app._json_error("변경할 내용이 없습니다.", 400)
    try:
        store.update_folder(int(folder_id), _acct_id(account), **kwargs)
    except store.FolderError as e:
        return _folder_err(e)
    except Exception:
        return app._json_error("폴더 수정에 실패했습니다.", 500)
    return JSONResponse({"ok": True, "folder_id": int(folder_id)})


@router.delete("/api/folders/{folder_id}")
async def delete_folder(
    folder_id: int,
    account=Depends(app.require_permission("folder.manage.own")),
) -> JSONResponse:
    _folder, err = _require_folder_owner(account, folder_id)
    if err:
        return err
    try:
        archived = store.soft_delete_folder(int(folder_id))
    except Exception:
        return app._json_error("폴더 삭제에 실패했습니다.", 500)
    # archived = undo 대상(서브트리). 대화는 core_conversations 에 보존.
    return JSONResponse({"ok": True, "archived_folder_ids": archived})


@router.post("/api/folders/{folder_id}/restore")
async def restore_folder(
    folder_id: int,
    request: Request,
    account=Depends(app.require_permission("folder.manage.own")),
) -> JSONResponse:
    # undo — 방금 삭제 응답의 archived_folder_ids 를 되돌린다. 소유 검증(대상 폴더).
    try:
        data = await request.json()
    except Exception:
        data = {}
    ids = (data or {}).get("archived_folder_ids") or [int(folder_id)]
    try:
        ids = [int(x) for x in ids]
    except Exception:
        return app._json_error("잘못된 folder id 목록입니다.", 400)
    # 소유 검증: 대상 루트 폴더가 요청자 소유여야(archived 상태라 _require_folder_owner 우회 — 직접 조회).
    root = store.get_folder(int(folder_id))
    if not root:
        return app._json_error("폴더를 찾을 수 없습니다.", 404)
    if int(root.get("owner_account_id") or 0) != _acct_id(account):
        return app._json_error("폴더를 찾을 수 없습니다.", 404)
    # ★ 프라이버시/IDOR: body 의 ids 는 공격자 통제 + folder_id 열거 가능(IDENTITY 순차 PK)이므로,
    #    restore 를 **항상** 요청자 owner 스코프로 SQL 강제한다(크로스-계정 복구 불가, manage.any 폐지).
    try:
        store.restore_folders(ids, owner_account_id=_acct_id(account))
    except Exception:
        return app._json_error("폴더 복구에 실패했습니다.", 500)
    return JSONResponse({"ok": True, "restored_folder_ids": ids})


# ── 대화 배정 ──────────────────────────────────────────────────────────────

@router.patch("/api/conversations/{conversation_id}/folder")
async def assign_conversation_folder(
    conversation_id: str,
    request: Request,
    account=Depends(app.require_permission("folder.manage.own")),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    raw = (data or {}).get("folder_id")
    target_folder_id = None if raw in (None, "", "null") else int(raw)

    # 게이트 1: 요청자가 그 대화에 접근 가능해야(read own/any). 계정별 배정이라도 남의 대화를
    #           자기 폴더에 끌어오는 것은 열람 권한이 전제.
    if not app._account_can_access_conversation(
        conn, account, conversation_id,
        "conversation.read.own", "conversation.read.any",
    ):
        return app._json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)

    # 게이트 2: 배정 대상 폴더가 요청자 소유여야(또는 manage.any).
    if target_folder_id is not None:
        _folder, err = _require_folder_owner(account, target_folder_id)
        if err:
            return err

    try:
        store.assign_conversation(_acct_id(account), conversation_id, target_folder_id)
    except Exception:
        return app._json_error("폴더 배정에 실패했습니다.", 500)
    return JSONResponse({"ok": True, "conversation_id": conversation_id, "folder_id": target_folder_id})
