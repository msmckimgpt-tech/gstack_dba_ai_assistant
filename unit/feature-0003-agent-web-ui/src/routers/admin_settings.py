"""feature-0018 runtime-settings — admin_settings 도메인 APIRouter.

관리 콘솔 `시스템 > 설정` 의 운영 값(실행 타임아웃 · 모델별 thinking budget) 조회/수정/초기화.
저장소는 memory DB(MySQL) `WebRuntimeSettings` KV(진실원본 + audit), 유효값은 공유 볼륨
스냅샷(/shared)으로 전 프로세스에 전파된다(shared.runtime_settings). 값은 스펙 [min,max]
범위에서만 저장된다(위험값 차단).

패턴 정합: quota 라우터와 동일하게 `import app`+`app.X` 동적참조, get_conn DI + commit,
동일-tx audit hook, 조회 종속 write 게이트(read + write 권한 동시 요구).
"""
from __future__ import annotations


from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

INCLUDE_ORDER = 230  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/admin/settings/runtime")
def admin_get_runtime_settings(
    request: Request,
    actor=Depends(app.require_permission("console.access", "system.runtime.read", message="런타임 설정 조회 권한이 필요합니다.")),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """실행 타임아웃 + 모델별 thinking budget 레지스트리와 현재 유효값(DB override 반영).

    표시 유효값은 DB(진실원본)의 override 를 권위값으로 사용한다(스냅샷 지연/유실 무관 정확).
    """
    overrides = app._load_runtime_setting_overrides(conn) if conn is not None else {}
    payload = app._runtime_settings.serialize_registry(overrides)
    return JSONResponse(payload)


@router.put("/api/admin/settings/runtime")
async def admin_set_runtime_setting(
    request: Request,
    actor=Depends(app.require_permission("console.access", "system.runtime.read", "system.runtime.write", message="런타임 설정 수정 권한이 필요합니다.")),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """단일 설정 override 저장. body {key, value:int}. 스펙 [min,max] 범위 검증 후 upsert.

    조절은 조회 종속(read + write 동시 요구, quota 정합). 저장 후 스냅샷 reconcile 로 전 프로세스
    전파 — live 값은 즉시(≤TTL), restart 값은 다음 재배포 시 반영.
    """
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    if not isinstance(data, dict):
        return app._json_error("invalid json", 400)
    key = str(data.get("key") or "").strip()
    ok, value, err = app._runtime_settings.validate_value(key, data.get("value"))
    if not ok:
        return app._json_error(err or "유효하지 않은 값입니다.", 400)
    if conn is None:
        return app._json_error("db connection failed", 500)
    # before-state 캡처(audit) — 기존 override(없으면 기본값 아님, override 부재 표시).
    before_overrides = app._load_runtime_setting_overrides(conn)
    before_value = before_overrides.get(key)
    # 원자적 save+audit: _connect_memory 기본 autocommit=True 라, 명시 tx 로 감싸지 않으면
    # save 가 즉시 커밋돼 audit 실패 시 rollback 이 무효(미감사 변경 잔존). gold-standard
    # (app.py auto-prompt save) 정합 — autocommit=False 로 부분 commit 방지, finally 복원.
    try:
        conn.autocommit = False
        app._save_runtime_setting(conn, key, int(value), int(actor["id"]))
        app._audit_admin_mutation(
            conn, request, actor,
            action="system.runtime.update", resource_type="runtime_setting",
            resource_id=key,
            before={"value": before_value},
            after={"value": int(value)},
            request_ctx={"key": key, "value": int(value)},
        )
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return app._json_error(f"설정 저장에 실패했습니다: {exc}", 500)
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
    # DB commit 성공 후 스냅샷 전파(best-effort — 실패해도 DB 진실원본은 보존, 다음 기동 reconcile).
    app._reconcile_runtime_settings_snapshot(conn)
    return JSONResponse({"ok": True, "key": key, "value": int(value)})


@router.delete("/api/admin/settings/runtime")
def admin_reset_runtime_setting(
    request: Request,
    key: str,
    actor=Depends(app.require_permission("console.access", "system.runtime.read", "system.runtime.write", message="런타임 설정 수정 권한이 필요합니다.")),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """설정 override 삭제(기본값으로 초기화). key 는 query param."""
    key = str(key or "").strip()
    if app._runtime_settings.spec_for(key) is None:
        return app._json_error("등록되지 않은 설정 키입니다.", 400)
    if conn is None:
        return app._json_error("db connection failed", 500)
    before_overrides = app._load_runtime_setting_overrides(conn)
    before_value = before_overrides.get(key)
    # 원자적 delete+audit (PUT 과 동일 — autocommit=False 로 부분 commit 방지).
    try:
        conn.autocommit = False
        app._delete_runtime_setting(conn, key)
        app._audit_admin_mutation(
            conn, request, actor,
            action="system.runtime.reset", resource_type="runtime_setting",
            resource_id=key,
            before={"value": before_value},
            after={"value": None},
            request_ctx={"key": key},
        )
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return app._json_error(f"설정 초기화에 실패했습니다: {exc}", 500)
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
    app._reconcile_runtime_settings_snapshot(conn)
    return JSONResponse({"ok": True, "key": key, "reset": True})


# ==== feature-0012 ITEM-10 p13 — app.py 에서 이동 (2종). app 전역은 app.X 동적 참조. ====

def _load_runtime_setting_overrides(conn) -> dict[str, int]:
    """WebRuntimeSettings 의 모든 override 를 {key: int} 로 로드. 실패/부재는 {} (fail-open).

    등록 스펙에 없는 키·정수 아님·범위 밖 값은 조용히 제외한다(방어적 — 스냅샷 오염 방지)."""
    result: dict[str, int] = {}
    cur = conn.cursor()
    try:
        cur.execute("SELECT SettingKey, SettingValue FROM WebRuntimeSettings")
        rows = cur.fetchall()
    except Exception:
        return {}
    finally:
        try:
            cur.close()
        except Exception:
            pass
    for key, raw in rows or []:
        ok, val, _err = app._runtime_settings.validate_value(str(key), raw)
        if ok and val is not None:
            result[str(key)] = int(val)
    return result

def _reconcile_runtime_settings_snapshot(conn) -> None:
    """DB override 를 공유 볼륨 스냅샷으로 재작성(best-effort). endpoint PUT 후 + web 기동 시 호출.

    스냅샷 쓰기 실패(공유 볼륨 부재 등)는 로깅만 하고 삼킨다 — DB 가 진실원본이며, 소비처는
    스냅샷 부재 시 기본값으로 fail-open 한다.
    """
    try:
        overrides = app._load_runtime_setting_overrides(conn)
        app._runtime_settings.write_snapshot(overrides)
    except Exception:
        app.logging.getLogger(__name__).warning(
            "runtime-settings snapshot reconcile failed", exc_info=True
        )


# ==== feature-0012 ITEM-10 p14 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _save_runtime_setting(conn, key: str, value: int, account_id: int | None) -> None:
    """단일 override upsert. 값은 반드시 호출측에서 validate_value 로 검증한 정수여야 한다."""
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO WebRuntimeSettings (SettingKey, SettingValue, UpdatedByAccountId) "
            "VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE SettingValue = VALUES(SettingValue), "
            "UpdatedByAccountId = VALUES(UpdatedByAccountId)",
            (str(key), str(int(value)), int(account_id) if account_id else None),
        )
    finally:
        try:
            cur.close()
        except Exception:
            pass


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _delete_runtime_setting(conn, key: str) -> None:
    """override 삭제(기본값으로 초기화)."""
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM WebRuntimeSettings WHERE SettingKey = %s", (str(key),))
    finally:
        try:
            cur.close()
        except Exception:
            pass
