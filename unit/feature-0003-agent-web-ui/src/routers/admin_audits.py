"""feature-0012 P5b Final — admin_audits 도메인 APIRouter (감사 로그 조회/내보내기/검증).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import hashlib
import json
import time

from datetime import datetime
from datetime import timezone
from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from typing import Any

import app

INCLUDE_ORDER = 160  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/admin/audits")
def list_audit_events(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4): audit event 조회 (filter + cursor).

    권한: `audit.read.own` 또는 `audit.read.any`. `.own` 은 `WHERE ActorAccountId=:self`
    강제 (TASK-0293 Actor-only — 본인 수행 행위만). `.any` 는 전체 row 조회.

    Query params: action_code / resource_type / actor_account_id / actor_type / from_at /
    to_at / q (ActionCode + ResourceId substring) / cursor (Id) / limit (≤500).

    Response: `{items: [...], next_cursor: <id>|None, scope: 'own'|'any'}`.
    """
    scope = app._audit_resolve_read_scope(account)
    if not scope:
        return app._json_error("감사 로그 조회 권한이 필요합니다.", 403)
    params = app._audit_parse_filter_params(request)
    cursor_id = app._audit_parse_cursor(params["cursor"])
    limit = app._audit_clamped_limit(params["limit"])
    where_clause, args = app._audit_compose_where(
        scope=scope,
        account_id=int(account["id"]),
        params=params,
        cursor_id=cursor_id,
    )
    sql = (
        "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
        "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
        "RemoteAddr, UserAgent, RequestId, OccurredAt "
        f"FROM WebAuditEvents{where_clause} "
        "ORDER BY Id DESC LIMIT %s"
    )
    args.append(int(limit) + 1)
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, tuple(args))
        rows = cur.fetchall() or []
    finally:
        cur.close()
    has_more = len(rows) > limit
    items = [app._audit_row_to_dict(r) for r in rows[:limit]]
    next_cursor = str(items[-1]["id"]) if has_more and items else None
    return JSONResponse({"items": items, "next_cursor": next_cursor, "scope": scope})

@router.get("/api/admin/audits/export.csv")
def export_audit_events_csv(request: Request) -> Any:
    """REQ-20260519-0001 (TASK-0073 Phase A4) + REQ-20260520-0005 (TASK-0090): audit event CSV streaming export.

    권한: `audit.export` (admin/dba). `.any` 와 동일 SQL — 전체 row 조회. masked field
    는 ChangeJson 안의 redact policy 그대로 (`MaskedFields` column 에 redact 대상 명시).

    TASK-0090 (Codex outside voice 5 findings 흡수):
      - **StreamingResponse + sync generator** (Codex C1 — async generator 안 sync mysql.connector 호출 시 event loop blocking).
      - **streaming-only connection** (Codex C1 — endpoint conn 은 auth + max_id capture + start self-audit 후 close, generator 내부에서 별 conn open + finally cleanup).
      - **max_id high-water mark** (Codex C2 — long transaction 회피, append-only audit 정합. 시작 시 `MAX(Id)` 잡고 모든 page `Id <= max_id`).
      - **chunk_size = 500** + **64KiB byte-threshold flush** (Codex minimum-fix — 1 row yield = uvicorn buffering 불효율).
      - **try/finally cleanup** (Codex C5 — client disconnect / timeout 시 cursor/conn 누설 차단).
      - **export self-audit** (start + complete 2 event, Codex C4 — DoS 운영 제어). `audit.purge` 와 동일 패턴 답습.
      - **hard cap 50k 제거** (Codex C4 — cap → max_id high-water + streaming 으로 memory bounded. SECURITY.md §9.5 갱신 정합).
    """
    import csv as _csv
    import io as _io
    import time as _time

    # === Phase 1: 짧은 auth conn — auth + permission + params + max_id capture + start self-audit ===
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    started_at = _time.time()
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_has_permission(account, "audit.export"):
            return app._json_error("감사 로그 export 권한이 필요합니다.", 403)
        params = app._audit_parse_filter_params(request)
        scope = "any"  # CSV export 는 .any superset.
        filter_hash = app._audit_export_filter_hash(params)
        # max_id high-water mark (Codex C2) — 같은 WHERE 의 시작 시점 MAX(Id) 잡음.
        where_clause_initial, args_initial = app._audit_compose_where(
            scope=scope,
            account_id=int(account["id"]),
            params=params,
            cursor_id=None,
        )
        cur = conn.cursor()
        try:
            sql_max = f"SELECT COALESCE(MAX(Id), 0) FROM WebAuditEvents{where_clause_initial}"
            cur.execute(sql_max, tuple(args_initial))
            row = cur.fetchone()
            max_id = int(row[0] if row else 0)
        finally:
            cur.close()
        # start self-audit.
        try:
            actor = {
                "account_id": int(account["id"]),
                "actor_type": "account",
                "role_id": account.get("role_id"),
                "session_id": account.get("session_id"),
            }
            app.record_audit_event(
                conn,
                actor=actor,
                action="audit.export.start",
                resource_type="audit_range",
                resource_id=None,
                change_json={
                    "scope": scope,
                    "filter_hash": filter_hash,
                    "max_id": max_id,
                    "chunk_size": app._AUDIT_EXPORT_CHUNK_SIZE,
                    "started_at": started_at,
                },
            )
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return app._json_error(f"export start audit failed: {exc}", 500)
        # capture for generator (account info, params, max_id).
        actor_for_complete = dict(actor)
    finally:
        conn.close()

    # === Phase 2: sync generator with streaming-only connection ===
    def csv_iter():
        sio = _io.StringIO()
        writer = _csv.writer(sio)
        # header.
        writer.writerow([
            "Id", "ActorAccountId", "ActorRoleId", "ActorType", "TargetAccountId",
            "SessionId", "ActionCode", "ResourceType", "ResourceId", "ChangeJson",
            "MaskedFields", "RemoteAddr", "UserAgent", "RequestId", "OccurredAt",
        ])
        yield sio.getvalue()
        sio.seek(0)
        sio.truncate(0)

        stream_conn = None
        stream_cur = None
        exported_row_count = 0
        aborted = False
        try:
            stream_conn = app._connect_memory()
            stream_cur = stream_conn.cursor(dictionary=True)
            cursor_id: int | None = None  # keyset cursor (descending).
            while True:
                # max_id high-water + Id < cursor_id (None first page).
                page_where_args: list[Any] = []
                # filter where (별 args copy — initial 의 args 재사용 안전).
                where_clause_page, args_page = app._audit_compose_where(
                    scope=scope,
                    account_id=int(actor_for_complete["account_id"]),
                    params=params,
                    cursor_id=cursor_id,
                )
                # max_id 조건 강제 추가 (append-only high-water mark).
                if where_clause_page:
                    where_clause_page = where_clause_page + " AND Id <= %s"
                else:
                    where_clause_page = " WHERE Id <= %s"
                args_page.append(max_id)
                sql_page = (
                    "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
                    "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
                    "RemoteAddr, UserAgent, RequestId, OccurredAt "
                    f"FROM WebAuditEvents{where_clause_page} "
                    "ORDER BY Id DESC LIMIT %s"
                )
                args_page.append(app._AUDIT_EXPORT_CHUNK_SIZE)
                stream_cur.execute(sql_page, tuple(args_page))
                rows = stream_cur.fetchall() or []
                if not rows:
                    break
                for r in rows:
                    d = app._audit_row_to_dict(r)
                    writer.writerow([
                        d["id"], d["actor_account_id"], d["actor_role_id"], d["actor_type"],
                        d["target_account_id"], d["session_id"], d["action_code"], d["resource_type"],
                        d["resource_id"],
                        json.dumps(d["change_json"], ensure_ascii=False, sort_keys=True) if d["change_json"] is not None else "",
                        json.dumps(d["masked_fields"], ensure_ascii=False, sort_keys=True) if d["masked_fields"] is not None else "",
                        d["remote_addr"], d["user_agent"], d["request_id"], d["occurred_at"],
                    ])
                    exported_row_count += 1
                    # byte-threshold flush.
                    if sio.tell() >= app._AUDIT_EXPORT_FLUSH_BYTES:
                        yield sio.getvalue()
                        sio.seek(0)
                        sio.truncate(0)
                cursor_id = int(rows[-1]["Id"])
                if len(rows) < app._AUDIT_EXPORT_CHUNK_SIZE:
                    break
            # final flush.
            if sio.tell() > 0:
                yield sio.getvalue()
        except Exception:
            aborted = True
            raise
        finally:
            # try/finally cleanup (Codex C5).
            try:
                if stream_cur is not None:
                    stream_cur.close()
            except Exception:
                pass
            try:
                if stream_conn is not None:
                    stream_conn.close()
            except Exception:
                pass
            # complete self-audit (별 short conn).
            try:
                done_at = _time.time()
                done_conn = app._connect_memory()
                try:
                    app.record_audit_event(
                        done_conn,
                        actor=actor_for_complete,
                        action="audit.export.complete" if not aborted else "audit.export.aborted",
                        resource_type="audit_range",
                        resource_id=None,
                        change_json={
                            "scope": scope,
                            "filter_hash": filter_hash,
                            "max_id": max_id,
                            "exported_row_count": exported_row_count,
                            "elapsed_ms": int((done_at - started_at) * 1000),
                            "aborted": aborted,
                        },
                    )
                    done_conn.commit()
                finally:
                    done_conn.close()
            except Exception:
                # complete audit 실패는 client 응답에 영향 X (이미 yield 진행). stderr 만.
                try:
                    import sys as _sys
                    _sys.stderr.write("[TASK-0090] audit.export.complete failed\n")
                except Exception:
                    pass

    return StreamingResponse(
        app._counted_stream_sync(csv_iter()),  # feature-0014: 무중단 배포 pre-drain 용 스트림 카운트
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit_events.csv"'},
    )

@router.get("/api/admin/audits/actors")
def list_audit_actors(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4): facet — distinct actor 목록."""
    scope = app._audit_resolve_read_scope(account)
    if not scope:
        return app._json_error("감사 로그 조회 권한이 필요합니다.", 403)
    # `.own` 사용자는 본인 actor 만 (계정 enumeration 차단).
    if scope == "own":
        return JSONResponse({"items": [{"actor_account_id": int(account["id"])}]})
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT wae.ActorAccountId, wa.Username "
            "FROM (SELECT DISTINCT ActorAccountId FROM WebAuditEvents WHERE ActorAccountId IS NOT NULL) wae "
            "LEFT JOIN WebAccounts wa ON wa.Id = wae.ActorAccountId "
            "ORDER BY wa.Username ASC LIMIT 500"
        )
        rows = cur.fetchall() or []
    finally:
        cur.close()
    items = [
        {
            "actor_account_id": int(r.get("ActorAccountId")) if r.get("ActorAccountId") is not None else None,
            "username": str(r.get("Username") or ""),
        }
        for r in rows
    ]
    return JSONResponse({"items": items})

@router.get("/api/admin/audits/resources")
def list_audit_resources(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4): facet — distinct resource_type 목록."""
    scope = app._audit_resolve_read_scope(account)
    if not scope:
        return app._json_error("감사 로그 조회 권한이 필요합니다.", 403)
    cur = conn.cursor(dictionary=True)
    try:
        # `.own` 사용자도 본인이 actor 인 row 의 resource_type 만 — extra SQL 분기.
        # TASK-0293: Actor-only (TargetAccountId 제외 — _audit_build_self_filter_sql 정합).
        if scope == "own":
            cur.execute(
                "SELECT DISTINCT ResourceType FROM WebAuditEvents "
                "WHERE ActorAccountId = %s "
                "ORDER BY ResourceType ASC LIMIT 100",
                (int(account["id"]),),
            )
        else:
            cur.execute(
                "SELECT DISTINCT ResourceType FROM WebAuditEvents "
                "ORDER BY ResourceType ASC LIMIT 100"
            )
        rows = cur.fetchall() or []
    finally:
        cur.close()
    items = [{"resource_type": str(r.get("ResourceType") or "")} for r in rows if r.get("ResourceType")]
    return JSONResponse({"items": items})

@router.get("/api/admin/audits/verify")
def verify_audit_chain(request: Request, actor=Depends(app.require_permission("audit.read.any", message="감사 무결성 검증 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-20260619T023922-audit-tamper-evidence (보안 ③, Critical §12.3): 감사 로그 해시 체인 무결성 검증.

    봉인 catch-up 후 Id 순으로 walk 하며 (1) 각 행 PrevHash == 직전 봉인행 EventHash(링크),
    (2) EventHash == SHA256(PrevHash | 정규화행)(내용) 을 검사. 첫 파손 위치를 반환. purge 경계는
    최신 checkpoint 로 재앵커(잔존 최古행 PrevHash == checkpoint). 권한: `audit.read.any`(admin/dba).
    walk 는 keyset 페이지네이션으로 메모리 bound.
    """
    # 검증 전 봉인 catch-up(미봉인 행 포함). 실패해도 검증은 진행(미봉인=break 로 보고).
    try:
        sealed_now = app._seal_audit_chain_drain(conn)
    except Exception:
        sealed_now = 0
    cur = conn.cursor(dictionary=True)
    try:
        # purge 경계 genesis = 최신 checkpoint hash(없으면 "").
        cur.execute(
            "SELECT ThroughEventId, CheckpointHash FROM WebAuditChainCheckpoint ORDER BY Id DESC LIMIT 1"
        )
        cp = cur.fetchone()
        prev_event_hash = str(cp["CheckpointHash"]) if cp and cp.get("CheckpointHash") else ""
        checkpoint_through = int(cp["ThroughEventId"]) if cp and cp.get("ThroughEventId") is not None else None
        # 첫 잔존행 PrevHash 가 checkpoint(또는 genesis "")와 일치하는지 검사용.
        last_id = 0
        verified = 0
        first_break: dict | None = None
        while first_break is None:
            cur.execute(
                f"SELECT {app._AUDIT_CHAIN_SELECT}, EventHash, PrevHash FROM WebAuditEvents "
                "WHERE Id > %s ORDER BY Id ASC LIMIT 1000",
                (last_id,),
            )
            batch = cur.fetchall() or []
            if not batch:
                break
            for row in batch:
                rid = int(row["Id"])
                last_id = rid
                stored = row.get("EventHash")
                if not stored:
                    first_break = {"id": rid, "reason": "unsealed"}
                    break
                stored_prev = str(row.get("PrevHash") or "")
                if stored_prev != str(prev_event_hash or ""):
                    first_break = {
                        "id": rid, "reason": "prev_hash_mismatch",
                        "expected_prev": (prev_event_hash or None), "stored_prev": (stored_prev or None),
                    }
                    break
                recomputed = app._audit_compute_hash(stored_prev, app._audit_canonical_string(row))
                if recomputed != str(stored):
                    first_break = {"id": rid, "reason": "content_modified"}
                    break
                prev_event_hash = str(stored)
                verified += 1
    finally:
        cur.close()
    ok = first_break is None
    return JSONResponse({
        "ok": ok,
        "verified_count": verified,
        "first_break": first_break,
        "sealed_during_verify": int(sealed_now or 0),
        "checkpoint_through_event_id": checkpoint_through,
    })

@router.post("/api/admin/audits/purge")
async def purge_audit_events(request: Request) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4, Eng review E8): chunked PK purge.

    권한: `audit.purge` (admin only). retention 초과 audit row 삭제.

    Body: `{cutoff: ISO8601, chunk_size?: int, dry_run?: bool}`.
    - cutoff: `OccurredAt < cutoff` 인 row 삭제.
    - chunk_size: 기본 1000 (clamp [100, 5000]).
    - dry_run: true 시 count 만 반환 + 실 삭제 X.

    각 chunk = 별 tx (Long Running Transaction 회피). start + complete self-audit
    event 2건 기록 (idempotency_key = hash(cutoff, started_at_minute) — 1 분 내
    중복 purge 차단).

    Response: `{purged: int, idempotency_key: str, dry_run: bool, started_at: ISO,
    completed_at: ISO|None}`.
    """
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    cutoff = str(data.get("cutoff") or "").strip()
    if not cutoff:
        return app._json_error("cutoff required (ISO8601)", 400)
    try:
        chunk_size = int(data.get("chunk_size") or app._AUDIT_PURGE_CHUNK_SIZE)
    except (ValueError, TypeError):
        chunk_size = app._AUDIT_PURGE_CHUNK_SIZE
    chunk_size = max(100, min(chunk_size, 5000))
    dry_run = bool(data.get("dry_run"))

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_has_permission(account, "audit.purge"):
            return app._json_error("감사 로그 purge 권한이 필요합니다.", 403)

        # dry_run: count only.
        if dry_run:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM WebAuditEvents WHERE OccurredAt < %s",
                    (cutoff,),
                )
                row = cur.fetchone()
                count = int(row[0] if row else 0)
            finally:
                cur.close()
            return JSONResponse({
                "purged": 0,
                "to_purge": count,
                "dry_run": True,
                "cutoff": cutoff,
                "chunk_size": chunk_size,
            })

        started_at = datetime.now(timezone.utc)
        idempotency_seed = f"{cutoff}|{started_at.strftime('%Y-%m-%dT%H:%M')}"
        idempotency_key = hashlib.sha256(idempotency_seed.encode("utf-8")).hexdigest()[:32]
        actor = app._build_actor_from_request(request, account, actor_type="account")
        actor["session_id"] = actor.get("session_id") or None
        # start self-audit (별 tx).
        try:
            app.record_audit_event(
                conn,
                actor=actor,
                action="audit.purge.start",
                resource_type="audit_range",
                resource_id=None,
                change_json={
                    "cutoff": cutoff,
                    "chunk_size": chunk_size,
                    "idempotency_key": idempotency_key,
                    "started_at": started_at.isoformat(),
                },
            )
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return app._json_error(f"purge start audit failed: {exc}", 500)

        # TASK-20260619T023922-audit-tamper-evidence (보안 ③): purge 경계 체인 재앵커.
        # 삭제 전 (1) 전체 봉인 catch-up → (2) 삭제될 마지막 행(최대 Id)의 EventHash 를 checkpoint
        # 로 기록. 삭제 후 잔존 최古행의 PrevHash 가 이 checkpoint 와 일치해야 검증 통과(정당 purge
        # 경계 인지). start self-audit 행(방금 INSERT, OccurredAt=now)은 cutoff 밖이라 미삭제.
        try:
            app._seal_audit_chain_drain(conn)
            _cpcur = conn.cursor(dictionary=True)
            try:
                _cpcur.execute(
                    "SELECT Id, EventHash FROM WebAuditEvents WHERE OccurredAt < %s AND EventHash IS NOT NULL "
                    "ORDER BY Id DESC LIMIT 1",
                    (cutoff,),
                )
                _last = _cpcur.fetchone()
            finally:
                _cpcur.close()
            if _last and _last.get("EventHash"):
                _ins = conn.cursor()
                try:
                    _ins.execute(
                        "INSERT INTO WebAuditChainCheckpoint (ThroughEventId, CheckpointHash, Reason) "
                        "VALUES (%s, %s, 'purge')",
                        (int(_last["Id"]), str(_last["EventHash"])),
                    )
                finally:
                    _ins.close()
                conn.commit()
        except Exception as _cp_exc:
            # 체크포인트 실패 시 purge 중단(체인 단절 방지) — 재시도 가능.
            return app._json_error(f"purge chain checkpoint failed: {_cp_exc}", 500)

        # Chunked DELETE loop.
        total_deleted = 0
        deadline_ts = time.time() + app._AUDIT_PURGE_MAX_RUNTIME_SEC
        while True:
            if time.time() > deadline_ts:
                break
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT Id FROM WebAuditEvents "
                    "WHERE OccurredAt < %s ORDER BY Id LIMIT %s",
                    (cutoff, int(chunk_size)),
                )
                rows = cur.fetchall() or []
            finally:
                cur.close()
            if not rows:
                break
            ids = [int((r[0] if isinstance(r, (list, tuple)) else r.get("Id")) or 0) for r in rows]
            ids = [i for i in ids if i > 0]
            if not ids:
                break
            placeholders = ",".join(["%s"] * len(ids))
            cur = conn.cursor()
            try:
                cur.execute(
                    f"DELETE FROM WebAuditEvents WHERE Id IN ({placeholders})",
                    tuple(ids),
                )
                conn.commit()
                total_deleted += len(ids)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                break
            finally:
                cur.close()

        completed_at = datetime.now(timezone.utc)
        # complete self-audit (별 tx).
        try:
            app.record_audit_event(
                conn,
                actor=actor,
                action="audit.purge.complete",
                resource_type="audit_range",
                resource_id=None,
                change_json={
                    "cutoff": cutoff,
                    "total_deleted": total_deleted,
                    "idempotency_key": idempotency_key,
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                },
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        return JSONResponse({
            "purged": total_deleted,
            "idempotency_key": idempotency_key,
            "dry_run": False,
            "cutoff": cutoff,
            "chunk_size": chunk_size,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        })
    finally:
        conn.close()

@router.get("/api/admin/audits/{event_id}")
def get_audit_event(event_id: int, request: Request) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4): audit event 단건 detail.

    `.own` 보유자는 ActorAccountId 가 본인일 때만 조회 가능 (TASK-0293 Actor-only;
    404 metadata leak 차단 — 권한 부족 시 무조건 404, byte-equal 응답).
    """
    if event_id <= 0:
        return app._json_error("invalid event_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        scope = app._audit_resolve_read_scope(account)
        if not scope:
            return app._json_error("감사 로그 조회 권한이 필요합니다.", 403)
        where_clause = " WHERE Id = %s"
        args: list[Any] = [int(event_id)]
        if scope == "own":
            cond, scope_args = app._audit_build_self_filter_sql(int(account["id"]))
            where_clause = f" WHERE Id = %s AND {cond}"
            args.extend(scope_args)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
                "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
                "RemoteAddr, UserAgent, RequestId, OccurredAt "
                f"FROM WebAuditEvents{where_clause} LIMIT 1",
                tuple(args),
            )
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return app._json_error("audit event not found", 404)
        return JSONResponse({"item": app._audit_row_to_dict(row), "scope": scope})
    finally:
        conn.close()
