"""feature-0012 P5b Final — admin/metadata 도메인 APIRouter (메타데이터 거버넌스: 용어사전/ENUM/테이블·컬럼 설명/샘플/그래프/부트스트랩/AI 자동완성).

DI 전환 33 핸들러(require_permission RP: kb.ingest.manual / kb.glossary.curate / kb.sample.curate)
+ 이연 1(admin_metadata_suggest — 동적 perm + pre-auth 404 gate, inline auth 유지). uniform
`import app`+`app.X` 동적참조(_metadata_* 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

router = APIRouter()


@router.get("/api/admin/metadata/glossary")
def admin_list_glossary(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """용어 목록 — 단일 scope(역할 차원 포함). 권한 kb.ingest.manual.

    ?scope_key= (기본 'common'). ?role_key= 지정 시 그 역할 행만(공용 '*' 미포함) 필터 — 역할별
    조회. 미지정이면 scope 의 모든 역할 행(role_key 필드로 구분 표시).
    """
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    role_filter = None
    rk_param = request.query_params.get("role_key")
    if rk_param is not None and str(rk_param).strip() != "":
        role_filter, rerr = app._metadata_check_role_key(rk_param)
        if rerr:
            return rerr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_glossary_admin(pg, scope_key, role_key=role_filter)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_glossary 조회 실패", exc_info=True)
        return app._json_error("용어 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, role_key, term, definition, source, created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "role_key": str(r[2] or "*"),
        "term": str(r[3] or ""), "definition": str(r[4] or ""), "source": str(r[5] or "manual"),
        "created_at": app._metadata_iso(r[6]), "updated_at": app._metadata_iso(r[7]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key,
                         "role_key": role_filter})

@router.post("/api/admin/metadata/glossary")
async def admin_create_glossary(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """용어 생성(upsert). 권한 kb.ingest.manual. body: scope_key, term, definition."""
    data = await app._metadata_read_json(request)
    scope_key, serr = app._metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    role_key, rerr = app._metadata_check_role_key(data.get("role_key"))
    if rerr:
        return rerr
    term, terr = app._metadata_str_field(data, "term")
    if terr:
        return terr
    definition, derr = app._metadata_str_field(data, "definition")
    if derr:
        return derr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _kg.upsert_glossary_term(pg, scope_key, term, definition, role_key=role_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_glossary 실패", exc_info=True)
        return app._json_error("용어 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="glossary.term.create",
                    resource_id=f"{scope_key}:{role_key}:{term}",
                    change_json={"scope_key": scope_key, "role_key": role_key, "term": term})
    return JSONResponse({"ok": True, "scope_key": scope_key, "role_key": role_key, "term": term})

@router.put("/api/admin/metadata/glossary/{term_id}")
async def admin_update_glossary(term_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """용어 수정(by id, scope 가드). 권한 kb.ingest.manual. body: scope_key, term, definition."""
    data = await app._metadata_read_json(request)
    scope_key, serr = app._metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    # role_key 는 선택 — 본문에 있으면 역할 귀속까지 변경(공용↔역할 이동), 없으면 기존 유지.
    role_key = None
    if "role_key" in (data or {}) and str(data.get("role_key") or "").strip() != "":
        role_key, rerr = app._metadata_check_role_key(data.get("role_key"))
        if rerr:
            return rerr
    term, terr = app._metadata_str_field(data, "term")
    if terr:
        return terr
    definition, derr = app._metadata_str_field(data, "definition")
    if derr:
        return derr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.update_glossary_term(pg, int(term_id), scope_key, term, definition,
                                            role_key=role_key)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 용어를 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        # UNIQUE(scope,role,term) 충돌 → 409 (같은 역할에 동일 용어 존재).
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("같은 역할에 동일 용어가 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_glossary 실패 id=%s", term_id, exc_info=True)
        return app._json_error("용어 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="glossary.term.update",
                    resource_id=int(term_id),
                    change_json={"scope_key": scope_key, "role_key": role_key, "term": term})
    return JSONResponse({"ok": True, "id": int(term_id)})

@router.delete("/api/admin/metadata/glossary/{term_id}")
def admin_delete_glossary(term_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """용어 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.delete_glossary_term(pg, int(term_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_glossary 실패 id=%s", term_id, exc_info=True)
        return app._json_error("용어 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # 멱등 — affected=0(이미 없음)도 성공. audit 은 실제 삭제(affected>0)만 기록.
    if affected > 0:
        app._metadata_audit(request, account, action="glossary.term.delete",
                        resource_id=int(term_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(term_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/glossary-feedback")
def admin_list_glossary_feedback(request: Request, account=Depends(app.require_permission('kb.glossary.curate'))) -> JSONResponse:
    """검토 큐 목록. 권한 kb.glossary.curate. ?status=(기본 pending, 'all'=전체) &scope_key= &role_key=."""
    status = str(request.query_params.get("status") or "pending").strip().lower()
    if status in ("all", ""):
        status = None
    elif status not in ("pending", "auto_promoted", "promoted", "rejected"):
        return app._json_error("허용되지 않은 status 입니다.", 400)
    scope_filter = None
    sk_param = request.query_params.get("scope_key")
    if sk_param is not None and str(sk_param).strip() != "":
        scope_filter, serr = app._metadata_check_scope(sk_param)
        if serr:
            return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_glossary_feedback(pg, status=status, scope_key=scope_filter)
        pending_count = _kg.count_glossary_feedback(pg, status="pending")
    except Exception:
        logging.getLogger(__name__).warning("admin_list_glossary_feedback 조회 실패", exc_info=True)
        return app._json_error("검토 큐 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, role_key, term, suggested_definition, confidence, status,
    #       source_run_id, conversation_id, promoted_glossary_id, approved_by, created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "role_key": str(r[2] or "*"),
        "term": str(r[3] or ""), "suggested_definition": str(r[4] or ""),
        "confidence": float(r[5]) if r[5] is not None else None, "status": str(r[6] or ""),
        "source_run_id": (str(r[7]) if r[7] is not None else None),
        "conversation_id": (str(r[8]) if r[8] is not None else None),
        "promoted_glossary_id": (int(r[9]) if r[9] is not None else None),
        "approved_by": (str(r[10]) if r[10] is not None else None),
        "created_at": app._glossary_feedback_iso(r[11]), "updated_at": app._glossary_feedback_iso(r[12]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items),
                         "pending_count": int(pending_count), "status": status})

@router.post("/api/admin/metadata/glossary-feedback/{feedback_id}/promote")
def admin_promote_glossary_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.glossary.curate'))) -> JSONResponse:
    """검토 큐(pending) → 용어사전 승급. 권한 kb.glossary.curate."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        gid = _kg.promote_glossary_feedback(
            pg, int(feedback_id), approved_by=str((account or {}).get("username") or "") or None)
        if gid is None:
            pg.rollback()
            return app._json_error("해당 후보를 찾을 수 없거나 이미 처리되었습니다.", 404)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_promote_glossary_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("용어 승급 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="glossary.feedback.promote",
                    resource_id=int(feedback_id),
                    change_json={"feedback_id": int(feedback_id), "glossary_id": int(gid)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "glossary_id": int(gid)})

@router.post("/api/admin/metadata/glossary-feedback/{feedback_id}/reject")
def admin_reject_glossary_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.glossary.curate'))) -> JSONResponse:
    """검토 큐 거부(pending) 또는 자동등록 되돌리기(auto_promoted → source='auto' 행 회수).
    권한 kb.glossary.curate. 멱등."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.reject_glossary_feedback(pg, int(feedback_id))
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_reject_glossary_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("용어 후보 거부 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        app._metadata_audit(request, account, action="glossary.feedback.reject",
                        resource_id=int(feedback_id), change_json={"feedback_id": int(feedback_id)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "rejected": int(affected)})

@router.get("/api/admin/metadata/glossary/{term_id}/relations")
def admin_list_glossary_relations(term_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """해당 용어의 인접 참조(유사어/동의어/see_also) 목록. 권한 kb.ingest.manual."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_glossary_relations(pg, int(term_id))
    except Exception:
        logging.getLogger(__name__).warning("admin_list_glossary_relations 실패 id=%s", term_id, exc_info=True)
        return app._json_error("유사어 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (relation_id, relation_type, from_id, to_id, other_id, other_scope, other_role, other_term, other_def)
    items = [{
        "relation_id": int(r[0]), "relation_type": str(r[1] or ""),
        "from_id": int(r[2]), "to_id": int(r[3]),
        "other_id": int(r[4]), "other_scope_key": str(r[5] or ""), "other_role_key": str(r[6] or "*"),
        "other_term": str(r[7] or ""), "other_definition": str(r[8] or ""),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "term_id": int(term_id)})

@router.post("/api/admin/metadata/glossary/{term_id}/relations")
async def admin_add_glossary_relation(term_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """유사어 참조 추가. 권한 kb.ingest.manual. body: to_id(필수), relation_type(synonym|similar|see_also)."""
    data = await app._metadata_read_json(request)
    try:
        to_id = int(data.get("to_id"))
    except (TypeError, ValueError):
        return app._json_error("to_id 는 필수(정수)입니다.", 400)
    if int(to_id) == int(term_id):
        return app._json_error("자기 자신은 참조로 연결할 수 없습니다.", 400)
    relation_type = str(data.get("relation_type") or "similar").strip().lower()
    if relation_type not in ("synonym", "similar", "see_also"):
        return app._json_error("relation_type 은 synonym|similar|see_also 중 하나여야 합니다.", 400)
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        # 두 용어 존재 확인(FK 위반 전 명시 404).
        if _kg.get_glossary_term(pg, int(term_id)) is None or _kg.get_glossary_term(pg, int(to_id)) is None:
            pg.rollback()
            return app._json_error("연결 대상 용어를 찾을 수 없습니다.", 404)
        _kg.add_glossary_relation(pg, int(term_id), int(to_id), relation_type,
                                  created_by=str((account or {}).get("username") or "") or None)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_add_glossary_relation 실패 from=%s to=%s", term_id, to_id, exc_info=True)
        return app._json_error("유사어 추가 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="glossary.relation.create",
                    resource_id=int(term_id),
                    change_json={"from_id": int(term_id), "to_id": int(to_id), "relation_type": relation_type})
    return JSONResponse({"ok": True, "from_id": int(term_id), "to_id": int(to_id),
                         "relation_type": relation_type})

@router.delete("/api/admin/metadata/glossary/relations/{relation_id}")
def admin_delete_glossary_relation(relation_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """유사어 참조 삭제(by relation id, 멱등). 권한 kb.ingest.manual."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.delete_glossary_relation(pg, int(relation_id))
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_glossary_relation 실패 id=%s", relation_id, exc_info=True)
        return app._json_error("유사어 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        app._metadata_audit(request, account, action="glossary.relation.delete",
                        resource_id=int(relation_id), change_json={"relation_id": int(relation_id)})
    return JSONResponse({"ok": True, "id": int(relation_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/enums")
def admin_list_enums(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """ENUM 목록 — 단일 scope. 권한 kb.ingest.manual. ?scope_key= (기본 'common')."""
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_enum_admin(pg, scope_key)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_enums 조회 실패", exc_info=True)
        return app._json_error("ENUM 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
        "table_name": str(r[3] or ""), "column_name": str(r[4] or ""),
        "code": str(r[5] or ""), "label": str(r[6] or ""),
        "created_at": app._metadata_iso(r[7]), "updated_at": app._metadata_iso(r[8]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key})

@router.post("/api/admin/metadata/enums")
async def admin_create_enum(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """ENUM 생성(upsert). 권한 kb.ingest.manual. body: scope_key, table_name, column_name, code, label, schema_name?."""
    data = await app._metadata_read_json(request)
    scope_key, serr = app._metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    fields, ferr = app._metadata_enum_fields(data)
    if ferr:
        return ferr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _kg.upsert_enum_entry(pg, scope_key, fields["table_name"], fields["column_name"],
                              fields["code"], fields["label"], schema_name=fields["schema_name"])
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_enum 실패", exc_info=True)
        return app._json_error("ENUM 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="enum.entry.create",
                    resource_id=f"{scope_key}:{fields['table_name']}.{fields['column_name']}={fields['code']}",
                    change_json={"scope_key": scope_key, "table_name": fields["table_name"],
                                 "column_name": fields["column_name"], "code": fields["code"]})
    return JSONResponse({"ok": True, "scope_key": scope_key})

@router.put("/api/admin/metadata/enums/{entry_id}")
async def admin_update_enum(entry_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """ENUM 수정(by id, scope 가드). 권한 kb.ingest.manual. body 동일."""
    data = await app._metadata_read_json(request)
    scope_key, serr = app._metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    fields, ferr = app._metadata_enum_fields(data)
    if ferr:
        return ferr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.update_enum_entry(
            pg, int(entry_id), scope_key, fields["table_name"], fields["column_name"],
            fields["code"], fields["label"], schema_name=fields["schema_name"])
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 ENUM 항목을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        # UNIQUE(scope,schema,table,column,code) 충돌 → 409 (다른 행과 key 중복).
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 key(스키마/테이블/컬럼/코드)의 ENUM 항목이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_enum 실패 id=%s", entry_id, exc_info=True)
        return app._json_error("ENUM 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="enum.entry.update",
                    resource_id=int(entry_id),
                    change_json={"scope_key": scope_key, "table_name": fields["table_name"],
                                 "column_name": fields["column_name"], "code": fields["code"]})
    return JSONResponse({"ok": True, "id": int(entry_id)})

@router.delete("/api/admin/metadata/enums/{entry_id}")
def admin_delete_enum(entry_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """ENUM 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.delete_enum_entry(pg, int(entry_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_enum 실패 id=%s", entry_id, exc_info=True)
        return app._json_error("ENUM 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        app._metadata_audit(request, account, action="enum.entry.delete",
                        resource_id=int(entry_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(entry_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/tables")
def admin_list_table_desc(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """테이블 설명 목록 — 단일 scope. 권한 kb.ingest.manual. ?scope_key= (기본 'common')."""
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _km.list_table_desc_admin(pg, scope_key)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_table_desc 조회 실패", exc_info=True)
        return app._json_error("테이블 설명 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, description, source, created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
        "table_name": str(r[3] or ""), "description": str(r[4] or ""), "source": str(r[5] or ""),
        "created_at": app._metadata_iso(r[6]), "updated_at": app._metadata_iso(r[7]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key})

@router.post("/api/admin/metadata/tables")
async def admin_create_table_desc(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """테이블 설명 생성(upsert). 권한 kb.ingest.manual. body: scope_key, table_name, description, schema_name?."""
    data = await app._metadata_read_json(request)
    scope_key, serr = app._metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    table_name, e = app._metadata_str_field(data, "table_name")
    if e:
        return e
    description, e = app._metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    schema_name, e = app._metadata_str_field(data, "schema_name", required=False)
    if e:
        return e
    source = "manual" if str(data.get("source") or "").strip().lower() != "bootstrap" else "bootstrap"
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _km.upsert_table_desc(pg, scope_key, table_name, description,
                              schema_name=schema_name, source=source,
                              created_by=str((account or {}).get("username") or "") or None)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_table_desc 실패", exc_info=True)
        return app._json_error("테이블 설명 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="table_desc.create",
                    resource_id=f"{scope_key}:{schema_name}.{table_name}",
                    change_json={"scope_key": scope_key, "schema_name": schema_name,
                                 "table_name": table_name, "source": source})
    return JSONResponse({"ok": True, "scope_key": scope_key, "table_name": table_name})

@router.put("/api/admin/metadata/tables/{desc_id}")
async def admin_update_table_desc(desc_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """테이블 설명 수정(by id, scope 가드). 권한 kb.ingest.manual. body: scope_key, description, schema_name?, table_name?."""
    data = await app._metadata_read_json(request)
    scope_key, serr = app._metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    description, e = app._metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    # key 컬럼(schema/table)은 선택 — 둘 다 주어질 때만 key 수정(부분 제공 거부).
    has_schema = "schema_name" in data
    has_table = "table_name" in data
    schema_name = table_name = None
    if has_table:
        table_name, e = app._metadata_str_field(data, "table_name")
        if e:
            return e
        schema_name, e = app._metadata_str_field(data, "schema_name", required=False)
        if e:
            return e
    elif has_schema:
        return app._json_error("table_name 없이 schema_name 만 수정할 수 없습니다.", 400)
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.update_table_desc(pg, int(desc_id), scope_key, description,
                                         schema_name=schema_name, table_name=table_name)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 테이블 설명을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 (스키마/테이블)의 설명이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_table_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("테이블 설명 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="table_desc.update",
                    resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id)})

@router.delete("/api/admin/metadata/tables/{desc_id}")
def admin_delete_table_desc(desc_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """테이블 설명 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.delete_table_desc(pg, int(desc_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_table_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("테이블 설명 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        app._metadata_audit(request, account, action="table_desc.delete",
                        resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/columns")
def admin_list_column_desc(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """컬럼 설명 목록 — 단일 scope. 권한 kb.ingest.manual. ?scope_key= (기본 'common')."""
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _km.list_column_desc_admin(pg, scope_key)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_column_desc 조회 실패", exc_info=True)
        return app._json_error("컬럼 설명 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, column_name, description, source, created_at, updated_at, ordinal)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
        "table_name": str(r[3] or ""), "column_name": str(r[4] or ""),
        "description": str(r[5] or ""), "source": str(r[6] or ""),
        "created_at": app._metadata_iso(r[7]), "updated_at": app._metadata_iso(r[8]),
        "ordinal": (int(r[9]) if len(r) > 9 and r[9] is not None else None),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key})

@router.post("/api/admin/metadata/columns")
async def admin_create_column_desc(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """컬럼 설명 생성(upsert). 권한 kb.ingest.manual. body: scope_key, table_name, column_name, description, schema_name?."""
    data = await app._metadata_read_json(request)
    scope_key, serr = app._metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    table_name, e = app._metadata_str_field(data, "table_name")
    if e:
        return e
    column_name, e = app._metadata_str_field(data, "column_name")
    if e:
        return e
    description, e = app._metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    schema_name, e = app._metadata_str_field(data, "schema_name", required=False)
    if e:
        return e
    source = "manual" if str(data.get("source") or "").strip().lower() != "bootstrap" else "bootstrap"
    # feature-0016 graphux5: 실제 스키마 컬럼 순서(1-based). 부트스트랩 저장이 골격(DDL) 순서를 전송.
    ordinal = data.get("ordinal")
    try:
        ordinal = int(ordinal) if ordinal is not None and str(ordinal).strip() != "" else None
    except (TypeError, ValueError):
        ordinal = None
    if ordinal is not None and not (0 < ordinal <= 100000):
        ordinal = None   # 비정상 범위(PG int 초과·음수·0)는 미지정 처리(500 회피)
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _km.upsert_column_desc(pg, scope_key, table_name, column_name, description,
                               schema_name=schema_name, source=source,
                               created_by=str((account or {}).get("username") or "") or None,
                               ordinal=ordinal)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_column_desc 실패", exc_info=True)
        return app._json_error("컬럼 설명 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="column_desc.create",
                    resource_id=f"{scope_key}:{schema_name}.{table_name}.{column_name}",
                    change_json={"scope_key": scope_key, "schema_name": schema_name,
                                 "table_name": table_name, "column_name": column_name, "source": source})
    return JSONResponse({"ok": True, "scope_key": scope_key, "table_name": table_name, "column_name": column_name})

@router.put("/api/admin/metadata/columns/{desc_id}")
async def admin_update_column_desc(desc_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """컬럼 설명 수정(by id, scope 가드). 권한 kb.ingest.manual. body: scope_key, description, schema_name?/table_name?/column_name?."""
    data = await app._metadata_read_json(request)
    scope_key, serr = app._metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    description, e = app._metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    has_table = "table_name" in data
    has_column = "column_name" in data
    schema_name = table_name = column_name = None
    if has_table or has_column:
        # key 수정 시 table+column 둘 다 필수(부분 제공 거부).
        table_name, e = app._metadata_str_field(data, "table_name")
        if e:
            return e
        column_name, e = app._metadata_str_field(data, "column_name")
        if e:
            return e
        schema_name, e = app._metadata_str_field(data, "schema_name", required=False)
        if e:
            return e
    # feature-0016 graphux5: ordinal(실제 스키마 컬럼 순서) 선택 수정. 미제공 → 미변경.
    ordinal = data.get("ordinal")
    if ordinal is not None and str(ordinal).strip() != "":
        try:
            ordinal = int(ordinal)
        except (TypeError, ValueError):
            ordinal = None
        if ordinal is not None and not (0 < ordinal <= 100000):
            ordinal = None   # 비정상 범위는 미지정 처리(500 회피)
    else:
        ordinal = None
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.update_column_desc(pg, int(desc_id), scope_key, description,
                                          schema_name=schema_name, table_name=table_name,
                                          column_name=column_name, ordinal=ordinal)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 컬럼 설명을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 (스키마/테이블/컬럼)의 설명이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_column_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("컬럼 설명 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="column_desc.update",
                    resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id)})

@router.delete("/api/admin/metadata/columns/{desc_id}")
def admin_delete_column_desc(desc_id: int, request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """컬럼 설명 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.delete_column_desc(pg, int(desc_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_column_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("컬럼 설명 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        app._metadata_audit(request, account, action="column_desc.delete",
                        resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/graph")
def admin_metadata_graph(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """메타데이터 지식그래프 투영(Apache AGE metadata_kb) — UI(Cytoscape)·검색 공급.

    권한 kb.ingest.manual. 8K 노드 규모라 **전체 덤프 금지** — 세 모드:
      - 이웃:    ?node=<key>&depth=1..3      → 해당 노드 k-hop (cap 적용)
      - 검색:    ?q=<부분일치>[&scope=<ds>]  → 이름/FQN CONTAINS (scope 지정 시 그 datasource 만)
      - 진입:    ?scope=<ds>                 → 그 datasource 의 Schema→Table 서브그래프(초기 뷰)
    셋 다 없으면 빈 그래프. AGE cutover 전(확장 부재)엔 모듈이 graceful no-op → 빈 결과.
    scope 는 datasource scope_key(예: mssql-06656002eda6) — 각 데이터소스별 그래프 분리.
    """
    q = (request.query_params.get("q") or "").strip()
    node = (request.query_params.get("node") or "").strip()
    scope = (request.query_params.get("scope") or "").strip() or None
    try:
        depth = int(request.query_params.get("depth") or "1")
    except (TypeError, ValueError):
        depth = 1
    depth = max(1, min(depth, 3))
    try:
        limit = int(request.query_params.get("limit") or "50")
    except (TypeError, ValueError):
        limit = 50

    from modules import metadata_graph as _mg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("그래프 저장소(PG) 연결 실패", 503)
    try:
        if node:
            data = _mg.neighborhood(node, depth=depth, conn=pg)
            mode = "neighborhood"
        elif q:
            data = {"nodes": _mg.search_nodes(q, limit=limit, scope=scope, conn=pg), "edges": []}
            mode = "search"
        elif scope:
            data = _mg.scope_roots(scope, conn=pg)
            mode = "scope_roots"
        else:
            data = {"nodes": [], "edges": []}
            mode = "empty"
    except Exception:
        logging.getLogger(__name__).warning("admin_metadata_graph 조회 실패", exc_info=True)
        return app._json_error("그래프 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    return JSONResponse({
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", []),
        "mode": mode,
        "q": q, "node": node, "scope": scope or "", "depth": depth,
        "node_count": len(data.get("nodes", [])), "edge_count": len(data.get("edges", [])),
    })

@router.post("/api/admin/metadata/graph/analyze")
async def admin_metadata_graph_analyze(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """그래프 노드 AI 능동 분석 트리거(항목2). 권한 kb.ingest.manual.

    body: {node_key, scope_key?, depth?, node_budget?}. run 을 만들고 즉시 202 반환 — 실제 분석은
    insight-worker 백그라운드가 선택 노드에서 관련 노드를 재귀 탐색하며 노드별 수행(부하 분산).
    진행은 GET .../graph/analyze?run_id= 로 폴링, 노드 결과는 GET .../graph/analyze/node?node= 로 조회.
    """
    data = await app._metadata_read_json(request)
    node_key = str(data.get("node_key") or data.get("node") or "").strip()
    if not node_key or ":" not in node_key:
        return app._json_error("node_key(그래프 노드 키)는 필수입니다.", 400)
    scope_key = str(data.get("scope_key") or node_key.split(":", 1)[0] or "common").strip().lower()
    depth = data.get("depth")
    node_budget = data.get("node_budget")
    from modules import node_analysis as _na
    res = _na.enqueue_analysis(scope_key, node_key, depth_budget=depth, node_budget=node_budget,
                               requested_by=str((account or {}).get("username") or "") or None)
    if not res.get("ok"):
        reason = res.get("reason") or "분석 시작 실패"
        # fix: 서버측 실패(PG 미가용/disabled/enqueue 실패)는 5xx. 클라 입력 오류만 400(라우트가 이미
        #   node_key 를 검증하므로 'node_key 필수'는 사실상 발생 안 함).
        code = 400 if reason == "node_key 필수" else 503
        return app._json_error(f"AI 능동 분석 시작 실패: {reason}", code)
    app._metadata_audit(request, account, action="node_analysis.enqueue", resource_id=node_key,
                    change_json={"scope_key": scope_key, "run_id": res.get("run_id"),
                                 "depth": depth, "node_budget": node_budget,
                                 "reused": res.get("reused", False)})
    return JSONResponse({"ok": True, "run_id": res.get("run_id"), "status": res.get("status"),
                         "reused": res.get("reused", False)}, status_code=202)

@router.get("/api/admin/metadata/graph/analyze")
def admin_metadata_graph_analyze_status(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """분석 run 진행률 폴링(항목2). 권한 kb.ingest.manual. ?run_id=<hex>.
    반환 {status, enqueued, done, failed, done_keys[...]} — 프론트가 done_keys 로 분석 마커 표시."""
    run_id = (request.query_params.get("run_id") or "").strip()
    if not run_id:
        return app._json_error("run_id 는 필수입니다.", 400)
    from modules import node_analysis as _na
    st = _na.get_run_status(run_id)
    if st is None:
        return app._json_error("run 을 찾을 수 없습니다.", 404)
    return JSONResponse(st)

@router.get("/api/admin/metadata/graph/analyze/node")
def admin_metadata_graph_analyze_node(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """노드의 최신 분석 상태/결과(상세 패널, 항목2). 권한 kb.ingest.manual. ?node=<key>[&scope=<ds>].
    반환 {status:'none'|'pending'|'running'|'done'|'failed', analysis:{summary,relationships,usage,caveats}}."""
    node = (request.query_params.get("node") or "").strip()
    if not node:
        return app._json_error("node 는 필수입니다.", 400)
    scope = (request.query_params.get("scope") or "").strip() \
        or (node.split(":", 1)[0] if ":" in node else "common")
    from modules import node_analysis as _na
    res = _na.get_node_analysis(scope, node)
    if res is None:
        return app._json_error("조회 실패", 503)
    return JSONResponse(res)

@router.get("/api/admin/metadata/graph/columns")
def admin_metadata_graph_columns(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """더블클릭 컬럼 즉석 introspection(항목3). 권한 kb.ingest.manual. ?node=<table key `scope:schema.table`>.

    그래프 투영(SSOT=column_descriptions)에 Column 노드가 없어(큐레이션/분석 미진행) 더블클릭해도
    컬럼이 안 펼쳐지던 문제를 해소한다. 그래프에 컬럼이 없으면 **데이터소스 information_schema 를 즉석
    조회**해 Column 노드 + HAS_COLUMN 엣지로 반환한다(read-only, 그래프 미저장). 실패 시 introspected=False
    + reason 으로 명확 피드백(silent no-op 금지)."""
    node = (request.query_params.get("node") or "").strip()
    if not node or ":" not in node:
        return app._json_error("node(테이블 키 `scope:schema.table`)는 필수입니다.", 400)
    scope_key = node.split(":", 1)[0]
    fqn = node.split(":", 1)[1]
    parts = [p for p in fqn.split(".") if p]
    if len(parts) < 2:
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node,
                             "reason": "테이블 노드가 아니거나 스키마.테이블 형식이 아닙니다."})
    schema = parts[0]
    table = parts[-1]
    import re as _re
    _ident = r"^[A-Za-z0-9_$\- ]+$"
    if not _re.match(_ident, schema) or not _re.match(_ident, table):
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node,
                             "reason": "식별자에 허용되지 않는 문자가 있어 조회를 건너뜁니다."})
    ds, derr = app._graph_resolve_ds_by_scope(scope_key)
    if derr:
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node, "reason": derr})
    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    conn = None
    engine = ""
    rows = []
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        if engine == "mssql":
            # MSSQL: fqn 첫 세그먼트가 DB(카탈로그) — 그 DB 에 연결 후 테이블명으로 컬럼 조회(스키마 무관).
            conn = _db.connect(datasource=ds, database=schema, autocommit=True)
            cur = conn.cursor()
            cur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                        f"WHERE TABLE_NAME = '{table}' ORDER BY ORDINAL_POSITION")
            rows = cur.fetchall()
            cur.close()
        else:
            # MySQL: schema == database. information_schema 는 서버 전역 → 무-database 연결 + WHERE 필터.
            conn = _db.connect(datasource=ds, autocommit=True)
            dialect = _dialects.active()
            cur = conn.cursor()
            cur.execute(dialect.describe_columns(schema, table))  # SELECT COLUMN_NAME, COLUMN_TYPE, ...
            rows = cur.fetchall()
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("graph columns introspect 실패 node=%s", node, exc_info=True)
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node,
                             "reason": "데이터소스 컬럼 조회 실패(권한/연결 확인, 또는 AI 능동 분석 사용)."})
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)
        except Exception:
            pass
    nodes, edges = [], []
    ord_i = 0
    for r in rows[:500]:
        cname = str(r[0]) if r and r[0] is not None else ""
        if not cname:
            continue
        ctype = str(r[1]) if len(r) > 1 and r[1] is not None else ""
        ckey = f"{scope_key}:{fqn}.{cname}"
        ord_i += 1   # describe_columns 는 ORDINAL_POSITION 순 → 인덱스가 실제 스키마 컬럼 순서(ERD 카드 정렬키)
        nodes.append({"label": "Column", "key": ckey, "name": cname,
                      "fqn": f"{fqn}.{cname}", "description": ctype, "source": "introspect", "ordinal": ord_i})
        edges.append({"source": node, "target": ckey, "type": "HAS_COLUMN",
                      "cardinality": None, "edge_source": "introspect"})
    return JSONResponse({"nodes": nodes, "edges": edges, "introspected": True,
                         "count": len(nodes), "engine": engine, "node": node})

@router.get("/api/admin/metadata/samples")
def admin_list_samples(request: Request, account=Depends(app.require_permission('kb.sample.curate'))) -> JSONResponse:
    """샘플 목록 — 단일 scope. 권한 kb.sample.curate. ?scope_key= (기본 'common')."""
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import sample_queries as _sq
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("샘플 저장소(PG) 연결 실패", 503)
    try:
        rows = _sq.list_samples_admin(pg, scope_key)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_samples 조회 실패", exc_info=True)
        return app._json_error("샘플 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, nl_question, sql, domain, weight, approved, status, source_type, created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "nl_question": str(r[2] or ""),
        "sql": str(r[3] or ""), "domain": str(r[4] or ""), "weight": int(r[5] or 0),
        "approved": bool(r[6]), "status": str(r[7] or ""), "source_type": str(r[8] or ""),
        "created_at": app._metadata_iso(r[9]), "updated_at": app._metadata_iso(r[10]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key})

@router.put("/api/admin/metadata/samples/{sample_id}")
async def admin_update_sample(sample_id: int, request: Request, account=Depends(app.require_permission('kb.sample.curate'))) -> JSONResponse:
    """샘플 수정(by id, scope 가드). 권한 kb.sample.curate. body: scope_key, nl_question?, sql?, domain?, weight?, approved?.

    하이브리드 C 임베딩: nl_question 변경 시에만 kb_retrieval._embed_query_vector 동기 시도 →
    성공이면 embedding 갱신(status='active'), 실패면 embedding 무효화(status='stale', 재임베딩 대기).
    nl 미변경 시 embedding touch 안 함. weight 1~1000 clamp. nl 중복(UNIQUE) → 409.
    """
    data = await app._metadata_read_json(request)
    scope_key, serr = app._metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr

    # 부분 수정 — 본문에 키가 있을 때만 해당 필드 변경. 전부 미제공이면 400(no-op 거부).
    kwargs: dict = {}
    if "nl_question" in data:
        nlq, e = app._metadata_str_field(data, "nl_question")
        if e:
            return e
        kwargs["nl_question"] = nlq
    if "sql" in data:
        sql_v = str(data.get("sql") or "").strip()
        if not sql_v:
            return app._json_error("sql 은 비울 수 없습니다.", 400)
        if len(sql_v) > 8000:  # 샘플 SQL 길이 cap(프롬프트 예시 전용 — 비대 방지)
            return app._json_error("sql 이 너무 깁니다 (최대 8000자).", 400)
        kwargs["sql"] = sql_v
    if "domain" in data:
        kwargs["domain"] = str(data.get("domain") or "").strip()
    if "weight" in data:
        try:
            w = int(data.get("weight"))
        except Exception:
            return app._json_error("weight 는 정수여야 합니다.", 400)
        kwargs["weight"] = max(app._SAMPLE_WEIGHT_MIN, min(app._SAMPLE_WEIGHT_MAX, w))  # 1~1000 clamp
    if "approved" in data:
        kwargs["approved"] = bool(data.get("approved"))
    if not kwargs:
        return app._json_error("수정할 필드가 없습니다.", 400)

    # 하이브리드 C: nl_question 변경 시에만 임베딩 동기 시도. 실패→None(코어가 status='stale').
    embed_changed = "nl_question" in kwargs
    embed_status = None  # 응답 진단용: 'active' | 'stale' | None(미변경)
    if embed_changed:
        vec = None
        try:
            from modules.kb_retrieval import _embed_query_vector
            vec = _embed_query_vector(kwargs["nl_question"])  # dim=1024(titan-embed v2)
        except Exception:
            vec = None
        kwargs["embedding"] = vec if vec else None
        embed_status = "active" if vec else "stale"

    from modules import sample_queries as _sq
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("샘플 저장소(PG) 연결 실패", 503)
    try:
        affected = _sq.update_sample(pg, int(sample_id), scope_key, **kwargs)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 샘플을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 질문(nl_question)의 샘플이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_sample 실패 id=%s", sample_id, exc_info=True)
        return app._json_error("샘플 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    app._metadata_audit(request, account, action="sample.update",
                    resource_id=int(sample_id),
                    change_json={"scope_key": scope_key, "fields": sorted(k for k in kwargs if k != "embedding"),
                                 "embedding": embed_status})
    return JSONResponse({"ok": True, "id": int(sample_id), "embedding_status": embed_status})

@router.delete("/api/admin/metadata/samples/{sample_id}")
def admin_delete_sample(sample_id: int, request: Request, account=Depends(app.require_permission('kb.sample.curate'))) -> JSONResponse:
    """샘플 삭제(by id, scope 가드, 멱등). 권한 kb.sample.curate. ?scope_key= 필수."""
    scope_key, serr = app._metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import sample_queries as _sq
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("샘플 저장소(PG) 연결 실패", 503)
    try:
        affected = _sq.delete_sample(pg, int(sample_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_sample 실패 id=%s", sample_id, exc_info=True)
        return app._json_error("샘플 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        app._metadata_audit(request, account, action="sample.delete",
                        resource_id=int(sample_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(sample_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/bootstrap/schemas")
def admin_bootstrap_schemas(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """선택 datasource 의 골격 단위(unit) 목록. 권한 kb.ingest.manual. ?datasource=<key>.

    엔진별 unit 차이(metadata-table-desc-fix):
      - **MySQL**: schema == database. information_schema/mysql/performance_schema/sys 시스템
        스키마 + __invalid_default_db__ 센티넬을 제외한 schema 목록.
      - **MSSQL**: server > database > schema 4계층. unit = **database**(list_server_databases,
        master/model/msdb/tempdb 제외). 과거엔 database 미선택 시 중립 tempdb 에 연결되어 임시테이블
        (#A0A50030 …)이 골격으로 잡혀 "테이블 명칭이 모두 올바르지 않은 값"으로 보였다.
    응답: {schemas:[...], datasource, engine, unit_kind:"database"|"schema"} — 프론트가 unit_kind 로 라벨 분기.
    """
    ds, scope_key, derr = app._bootstrap_resolve_datasource(request.query_params.get("datasource") or "")
    if derr:
        return derr
    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    from modules import schema as _schema
    conn = None
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        if engine == "mssql":
            # MSSQL unit = database. 시스템 DB(master/model/msdb/tempdb) 제외.
            dialect = _dialects.active()
            sys_db = {str(n).strip().lower() for n in dialect.system_databases()}
            units = [str(n) for n in (_db.list_server_databases(ds) or [])
                     if str(n).strip().lower() not in sys_db]
            unit_kind = "database"
        else:
            conn = _db.connect(datasource=ds, autocommit=True)  # RO 유저(데이터소스 좌표는 least-priv)
            raw = _schema.load_known_schemas(conn) or []  # dialect-aware(schema.py:788)
            units = [str(n) for n in raw
                     if str(n).strip().lower() not in app._BOOTSTRAP_MYSQL_SYS_SCHEMAS]
            unit_kind = "schema"
    except Exception:
        logging.getLogger(__name__).warning("admin_bootstrap_schemas 실패 ds=%s", scope_key, exc_info=True)
        return app._json_error("스키마 조회 실패", 503)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)  # 요청 컨텍스트 dialect 리셋
        except Exception:
            pass
    return JSONResponse({"schemas": units, "datasource": scope_key, "engine": engine, "unit_kind": unit_kind})

@router.post("/api/admin/metadata/bootstrap")
async def admin_bootstrap(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """선택 datasource+schema 의 테이블/컬럼 골격(미영속). 권한 kb.ingest.manual. body: datasource, schema.

    골격은 저장하지 않는다 — UI 가 설명 빈칸을 prefill, 사람이 채워 tables/columns POST(source='bootstrap')
    로 저장한다. dialect-aware: MSSQL 은 set_active_datasource(engine=) 로 활성화 후 dialect.describe_columns
    경유(MySQL 백틱 하드코딩 load_schema_metadata 우회). 자동 1행 샘플/list_indexes 호출 안 함(부하/PII).
    """
    data = await app._metadata_read_json(request)
    ds, scope_key, derr = app._bootstrap_resolve_datasource(data.get("datasource") or "")
    if derr:
        return derr
    schema_name = str(data.get("schema") or "").strip()
    if not schema_name:
        return app._json_error("schema 는 필수입니다.", 400)
    if len(schema_name) > app._METADATA_FIELD_CAPS["schema_name"]:
        return app._json_error("schema 가 너무 깁니다.", 400)

    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    from modules import schema as _schema
    from modules.tools import _safe_ident as _safe_ident_fn
    # REV B1(BLOCKER) — SQLi 차단: dialect.describe_schema_tables 는 schema 를 f-string 으로 SQL 에
    # 삽입(dialects.py `WHERE … = '{schema}'`)하므로, 구조화 도구(tools.py)와 동일하게
    # ① _safe_ident 로 인용 구분자 제거 + ② allowlist 멤버십으로만 통과시킨다.
    safe_schema = _safe_ident_fn(schema_name)
    conn = None
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        if engine == "mssql":
            # MSSQL: schema 파라미터는 **database**. 시스템 DB 제외 allowlist 로 검증 후 해당 DB 로
            # 직접 연결(database 미지정 시 중립 tempdb 폴백 → 임시테이블 회귀)하고, 그 DB 안의 비시스템
            # SQL 스키마 테이블을 평탄 수집한다(저장 schema_name = database).
            dialect = _dialects.active()
            sys_db = {str(n).strip().lower() for n in dialect.system_databases()}
            db_units = {str(n) for n in (_db.list_server_databases(ds) or [])
                        if str(n).strip().lower() not in sys_db}
            if safe_schema not in db_units:
                return app._json_error("알 수 없는 database 이거나 접근할 수 없습니다.", 404)
            conn = _db.connect(datasource=ds, database=safe_schema, autocommit=True)
            tables = app._bootstrap_collect_skeleton_mssql(conn, _dialects, safe_schema)
        else:
            conn = _db.connect(datasource=ds, autocommit=True)
            known_schemas = set(_schema.load_known_schemas(conn) or [])
            if safe_schema not in known_schemas:
                return app._json_error("알 수 없는 schema 이거나 접근할 수 없습니다.", 404)
            tables = app._bootstrap_collect_skeleton(conn, _dialects, safe_schema)
    except Exception:
        logging.getLogger(__name__).warning("admin_bootstrap 실패 ds=%s schema=%s", scope_key, schema_name, exc_info=True)
        return app._json_error("스키마 골격 조회 실패", 503)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)
        except Exception:
            pass
    return JSONResponse({"tables": tables, "datasource": scope_key, "schema": schema_name})

@router.post("/api/admin/metadata/{sub}/suggest")
async def admin_metadata_suggest(sub: str, request: Request) -> JSONResponse:
    """메타데이터 단건 AI 자동완성 — 식별 필드 → 설명/정의/라벨/질문 1건(영속 안 함).

    RBAC 는 서브뷰별(glossary/enums/tables/columns=kb.ingest.manual, samples=kb.sample.curate).
    tables/columns 는 datasource 지정 시 실제 스키마(컬럼)에 best-effort grounding.
    """
    sub = str(sub or "").strip().lower()
    target = app._METADATA_SUGGEST_TARGET.get(sub)
    if not target:
        return app._json_error("알 수 없는 메타데이터 서브뷰입니다.", 404)
    perm = app._METADATA_SUBTAB_PERM_SERVER.get(sub, "kb.ingest.manual")
    account, error = app._metadata_resolve_account_perm(request, perm)
    if error:
        return error
    # per-account rate-limit(429) — LLM dispatch 비용 DoS 방어(fix-with-ai 와 동일 패턴). RBAC 통과 후 검사.
    if not app._search_rate_limit_check(int(account.get("id") or 0), max_per_min=app._METADATA_AI_RATE_PER_MIN):
        return app._json_error("자동완성 요청이 너무 잦습니다. 잠시 후 다시 시도하세요.", 429)
    data = await app._metadata_read_json(request)
    fields: dict = {}
    for k in ("term", "schema_name", "table_name", "column_name", "code", "sql", "nl_question"):
        if k in data:
            v, ferr = app._metadata_str_field(data, k, required=False)
            if ferr:
                return ferr
            fields[k] = v
    for req_k in app._METADATA_SUGGEST_REQUIRES.get(sub, []):
        if not fields.get(req_k):
            return app._json_error(f"자동완성하려면 먼저 '{req_k}' 를 입력하세요.", 400)
    grounding = None
    if sub in ("tables", "columns"):
        grounding = app._metadata_introspect_table(
            str(data.get("datasource") or ""), fields.get("schema_name") or "", fields.get("table_name") or ""
        )
    messages = app._metadata_suggest_messages(sub, fields, grounding)
    text, meta, lerr = await app._metadata_llm_complete(messages, task="summary")
    if lerr:
        return lerr
    cap = app._METADATA_FIELD_CAPS.get(target)
    suggestion = text or ""
    if cap and len(suggestion) > cap:
        suggestion = suggestion[:cap].rstrip()
    return JSONResponse({
        "target": target,
        "suggestion": suggestion,
        "meta": {**(meta or {}), "grounded": bool(grounding and grounding.get("columns"))},
    })

@router.post("/api/admin/metadata/bootstrap/describe")
async def admin_metadata_bootstrap_describe(request: Request, account=Depends(app.require_permission('kb.ingest.manual'))) -> JSONResponse:
    """부트스트랩 일괄 AI 자동완성 — 골격(테이블/컬럼)의 설명을 1 LLM 호출로 생성(영속 안 함).

    프론트가 청크 단위(≤_METADATA_BULK_MAX_TABLES)로 호출해 진행률을 표면화한다. RBAC kb.ingest.manual.
    골격 식별자는 프롬프트 텍스트로만 사용(SQL 미사용)하므로 클라 제공 골격을 cap 후 신뢰한다.
    반환 results 는 {schema_name, table_name[, column_name], description} 리스트 — 프론트가 입력란에 채움.
    """
    # per-account rate-limit(429) — 청크 일괄 LLM dispatch 비용 DoS 방어. RBAC 통과 후 검사.
    if not app._search_rate_limit_check(int(account.get("id") or 0), max_per_min=app._METADATA_AI_RATE_PER_MIN):
        return app._json_error("일괄 자동완성 요청이 너무 잦습니다. 잠시 후 다시 시도하세요.", 429)
    data = await app._metadata_read_json(request)
    mode = str(data.get("mode") or "tables").strip().lower()
    if mode not in ("tables", "columns"):
        return app._json_error("mode 는 tables/columns 중 하나여야 합니다.", 400)
    raw_tables = data.get("tables")
    if not isinstance(raw_tables, list) or not raw_tables:
        return app._json_error("tables 골격이 필요합니다.", 400)
    if len(raw_tables) > app._METADATA_BULK_MAX_TABLES:
        return app._json_error(f"1회 호출은 테이블 {app._METADATA_BULK_MAX_TABLES}개 이하만 처리합니다.", 400)
    tables: list = []
    for t in raw_tables:
        if not isinstance(t, dict):
            continue
        tname = str(t.get("table_name") or "").strip()[:128]
        if not tname:
            continue
        sname = str(t.get("schema_name") or "").strip()[:128]
        cols: list = []
        for c in (t.get("columns") or [])[:app._BOOTSTRAP_MAX_COLS_PER_TABLE]:
            if not isinstance(c, dict):
                continue
            cn = str(c.get("column_name") or "").strip()[:128]
            if cn:
                cols.append({"column_name": cn, "data_type": str(c.get("data_type") or "").strip()[:64]})
        tables.append({"schema_name": sname, "table_name": tname, "columns": cols})
    if not tables:
        return app._json_error("유효한 테이블이 없습니다.", 400)
    messages = app._metadata_bulk_describe_messages(mode, tables)
    text, meta, lerr = await app._metadata_llm_complete(messages, task="prompt_gen", temperature=0.2)
    if lerr:
        return lerr
    parsed = app._metadata_parse_json_object(text)
    if parsed is None:
        return app._json_error("AI 응답을 해석할 수 없습니다. 다시 시도하세요.", 502)
    results = app._metadata_bulk_shape_results(mode, tables, parsed)
    return JSONResponse({"mode": mode, "results": results, "meta": {**(meta or {}), "count": len(results)}})
