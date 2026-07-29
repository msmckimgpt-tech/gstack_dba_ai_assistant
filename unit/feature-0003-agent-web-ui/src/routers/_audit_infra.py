"""feature-0012 ITEM-10 p7 — 감사(audit) 인프라 헬퍼 (비-라우트 공용 모듈).

app.py 에서 이동. 전 라우터가 소비하는 공용 계층 — `_` 접두라 register_all 제외.
**record_audit_event 는 app.py 에 잔류**(테스트 setattr 12× 패치-단일점) — 본 모듈의
호출은 전부 `app.record_audit_event` 동적 참조라 패치가 관통한다(판정표 §4 규약).
"""

import hashlib
import json
import logging
import re
import time
from typing import Any

from fastapi import Request

import app  # noqa: F401 — app.X 동적 참조(꼬리 rebind 시점 import — 순환 안전)


def _audit_product_snapshot(conn, product_id: int) -> dict | None:
    """REQ-20260520-0006 (TASK-0091): single-row WebProducts snapshot for admin.product.update audit.

    SECURITY.md §9.2 정합 — `system_prompt.content` full body 제외 (`{present, content_len,
    updated_at}` summary 만 포함). `WebProductDatabases` 도 제외 (별 endpoint
    `admin.product.databases.update` 의 audit 으로 분리, Codex C3).

    `SELECT ... FOR UPDATE` 로 row lock (Codex C2 — 명시 transaction).
    """
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT Id AS id, ProductKey AS product_key, Name AS name, Description AS description,
       IsActive AS is_active, IsDefault AS is_default, SortOrder AS sort_order,
       DefaultRoleAccess AS default_role_access
FROM WebProducts
WHERE Id = %s
FOR UPDATE
        """,
        (int(product_id),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    product: dict[str, Any] = {
        "id": int(row.get("id") or 0),
        "product_key": str(row.get("product_key") or ""),
        "name": str(row.get("name") or ""),
        "description": str(row.get("description") or ""),
        "is_active": bool(row.get("is_active")),
        "is_default": bool(row.get("is_default")),
        "sort_order": int(row.get("sort_order") or 0),
        "default_role_access": bool(row.get("default_role_access", True)),
    }
    sp = app._load_system_prompt(conn, scope="product", product_id=int(product_id))
    if sp:
        content = str(sp.get("content") or "")
        product["system_prompt_summary"] = {
            "present": True,
            "content_len": len(content),
            "updated_at": str(sp.get("updated_at") or ""),
        }
    else:
        product["system_prompt_summary"] = {"present": False}
    return product

def _audit_canonical_string(row: dict) -> str:
    """감사 행의 결정적 정규화 문자열 — 해시 입력. 필드 순서/구분자 고정.

    None 은 빈 문자열, JSON 컬럼은 이미 문자열(dispatcher 가 sort_keys 직렬화)이라 그대로.
    OccurredAt(datetime) 은 마이크로초까지 ISO 로 안정화.
    """
    parts: list[str] = []
    for f in app._AUDIT_CHAIN_FIELDS:
        v = row.get(f)
        if v is None:
            parts.append("")
        elif hasattr(v, "isoformat"):
            parts.append(v.isoformat())
        else:
            parts.append(str(v))
    # \x1f (unit separator) — 본문에 나타나지 않는 제어문자로 필드 경계 모호성 차단.
    return "\x1f".join(parts)

def _audit_compute_hash(prev_hash: str, canonical: str) -> str:
    import hashlib as _hl
    return _hl.sha256((str(prev_hash or "") + "\x1e" + canonical).encode("utf-8")).hexdigest()

def _audit_message_table_collations(conn) -> None:
    """REQ-20260518-0010 (TASK-0072) adversarial risk 2: warn on stderr if
    message body columns are not utf8mb4_unicode_ci. Runs once per process."""
    global _COLLATION_AUDIT_DONE
    if _COLLATION_AUDIT_DONE:
        return
    _COLLATION_AUDIT_DONE = True
    cur = conn.cursor()
    rows: list[Any] = []
    try:
        cur.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, COLLATION_NAME "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME IN ('AgentMemoryMessages', 'AgentCoreMessages') "
            "AND COLUMN_NAME IN ('Content', 'content')"
        )
        rows = cur.fetchall() or []
    except Exception:
        return
    finally:
        cur.close()
    expected = "utf8mb4_unicode_ci"
    for row in rows:
        tbl, col, coll = row[0], row[1], row[2]
        if coll and coll != expected:
            try:
                import sys as _sys
                _sys.stderr.write(
                    f"[TASK-0072 audit] collation mismatch: {tbl}.{col} = {coll} "
                    f"(expected {expected}). Body search LIKE may trigger conversion scan.\n"
                )
            except Exception:
                pass

def _audit_pick_fields(source: dict | None, fields: tuple[str, ...]) -> dict:
    """Builder helper — 명시 화이트리스트 field 만 추출. None 입력 시 empty dict."""
    if not source:
        return {}
    return {k: source.get(k) for k in fields if k in source}

def _audit_redact_sensitive(d: dict | None) -> dict:
    """Builder helper — sensitive field 값을 '<redacted>' 로 치환. shallow 만 처리."""
    if not d:
        return {}
    out: dict[str, Any] = {}
    for k, v in d.items():
        if str(k).lower() in app._AUDIT_MASKED_FIELDS_ALL:
            out[k] = "<redacted>"
        else:
            out[k] = v
    return out

def build_audit_change_json(
    *,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    request_ctx: dict | None = None,
) -> tuple[dict, list[str]]:
    """ActionCode-specific ChangeJson builder dispatch.

    raw request 검증 X — 각 ActionCode 별 화이트리스트만 select. unknown action 은
    raise ValueError (caller 가 catch 해 fail-safe — admin tx rollback / user fail-open).

    Returns: (change_json, masked_fields).
    """
    action = str(action or "").strip()
    request_ctx = request_ctx or {}
    if action == "admin.account.update":
        return (
            {
                "target_account_id": (before or {}).get("id") or (after or {}).get("id"),
                "before": _audit_redact_sensitive(_audit_pick_fields(before, app._AUDIT_BUILDER_ACCOUNT_FIELDS)),
                "after": _audit_redact_sensitive(_audit_pick_fields(after, app._AUDIT_BUILDER_ACCOUNT_FIELDS)),
            },
            [],
        )
    if action == "admin.account.delete":
        return (
            {
                "target_account_id": (before or {}).get("id"),
                "deleted": _audit_redact_sensitive(_audit_pick_fields(before, app._AUDIT_BUILDER_ACCOUNT_FIELDS)),
            },
            [],
        )
    if action == "admin.account.password-reset":
        # PasswordHash / temporary_password 명시 redact — builder 단계에서 제외.
        return (
            {
                "target_account_id": (before or {}).get("id"),
                "target_username": (before or {}).get("username"),
                "must_change_password": True,
                "sessions_revoked": bool(request_ctx.get("sessions_revoked")),
            },
            list(app._AUDIT_MASKED_FIELDS_PASSWORD) + list(app._AUDIT_MASKED_FIELDS_TOKEN),
        )
    if action == "admin.role.create":
        return (
            {
                "created_role": _audit_pick_fields(after, app._AUDIT_BUILDER_ROLE_FIELDS),
            },
            [],
        )
    if action == "admin.role.update":
        return (
            {
                "target_role_id": (before or {}).get("id") or (after or {}).get("id"),
                "before": _audit_pick_fields(before, app._AUDIT_BUILDER_ROLE_FIELDS),
                "after": _audit_pick_fields(after, app._AUDIT_BUILDER_ROLE_FIELDS),
            },
            [],
        )
    if action == "admin.role.delete":
        return (
            {
                "target_role_id": (before or {}).get("id"),
                "deleted": _audit_pick_fields(before, app._AUDIT_BUILDER_ROLE_FIELDS),
            },
            [],
        )
    if action == "admin.product.create":
        return (
            {"created_product": _audit_pick_fields(after, app._AUDIT_BUILDER_PRODUCT_FIELDS)},
            [],
        )
    if action == "admin.product.update":
        # TASK-0091 (Codex C4): is_default=true 시 다른 product 들의 IsDefault=0 side
        # effect 도 audit ChangeJson 에 기록. caller (admin_update_product) 가
        # after dict 에 `_default_cleared_product_ids` 키로 명시 전달.
        cleared_ids = (after or {}).get("_default_cleared_product_ids") if isinstance(after, dict) else None
        body: dict[str, Any] = {
            "target_product_id": (before or {}).get("id") or (after or {}).get("id"),
            "before": _audit_pick_fields(before, app._AUDIT_BUILDER_PRODUCT_FIELDS),
            "after": _audit_pick_fields(after, app._AUDIT_BUILDER_PRODUCT_FIELDS),
        }
        if isinstance(cleared_ids, list) and cleared_ids:
            body["default_cleared_product_ids"] = [int(x) for x in cleared_ids]
        return (body, [])
    if action == "admin.product.delete":
        return (
            {
                "target_product_id": (before or {}).get("id"),
                "deleted": _audit_pick_fields(before, app._AUDIT_BUILDER_PRODUCT_FIELDS),
            },
            [],
        )
    if action == "admin.product.databases.update":
        return (
            {
                "target_product_id": (before or {}).get("id") or request_ctx.get("product_id"),
                "before_schemas": list((before or {}).get("schemas") or []),
                "after_schemas": list((after or {}).get("schemas") or []),
            },
            [],
        )
    # TASK-20260618T044318: DB allowlist 정규식 규칙 자동 동기화 audit actions.
    if action in ("admin.product.db_rule.set", "admin.product.db_rule.delete",
                  "admin.product.db_rule.approve", "admin.product.db.autoadd",
                  "admin.product.db.staged"):
        return (
            {
                "target_product_id": request_ctx.get("product_id") or (after or {}).get("product_id"),
                "datasource_key": request_ctx.get("datasource_key") or (after or {}).get("datasource_key")
                or (before or {}).get("datasource_key"),
                "before": before or {},
                "after": after or {},
            },
            [],
        )
    if action == "admin.system_prompt.update":
        # system_prompt 본문 자체는 length 만 — full content 는 redact 가 아닌 size cap.
        body_before = str((before or {}).get("content") or "")
        body_after = str((after or {}).get("content") or "")
        return (
            {
                "scope": request_ctx.get("scope"),
                "target_role_id": request_ctx.get("role_id"),
                "target_account_id": request_ctx.get("account_id"),
                "target_product_id": request_ctx.get("product_id"),
                "content_len_before": len(body_before),
                "content_len_after": len(body_after),
                "content_preview_after": body_after[:120],
            },
            ["system_prompt.content_full"],
        )
    # user endpoint actions (Phase A6) — builder 도 같은 catalog 에서 정의.
    if action == "conversation.ask":
        return (
            {
                "conversation_id": request_ctx.get("conversation_id"),
                "model": request_ctx.get("model"),
                "product_mode": request_ctx.get("product_mode"),
                "product_key": request_ctx.get("product_key"),
                "lazy_create": bool(request_ctx.get("lazy_create")),
                "prompt_length": int(request_ctx.get("prompt_length") or 0),
            },
            ["conversation.ask.prompt_full", "conversation.ask.final_sql_full"],
        )
    if action == "conversation.share.create":
        return (
            {
                "conversation_id": request_ctx.get("conversation_id"),
                "scope_mode": request_ctx.get("scope_mode"),
                "anchor_message_id": request_ctx.get("anchor_message_id"),
                "share_id": request_ctx.get("share_id"),
                "token_prefix": str(request_ctx.get("token_prefix") or "")[:8],
                "expires_in_seconds": request_ctx.get("expires_in_seconds"),
            },
            ["share.token_full"],
        )
    if action == "conversation.share.revoke":
        return (
            {
                "conversation_id": request_ctx.get("conversation_id"),
                "share_id": request_ctx.get("share_id"),
                "already_revoked": bool(request_ctx.get("already_revoked")),
            },
            [],
        )
    if action == "share.public.view":
        return (
            {
                "share_id": request_ctx.get("share_id"),
                "token_prefix": str(request_ctx.get("token_prefix") or "")[:8],
                "view_count_after": int(request_ctx.get("view_count_after") or 0),
                "remote_addr_present": bool(request_ctx.get("remote_addr")),
            },
            ["share.token_full"],
        )
    if action == "share.fork":
        return (
            {
                "source_share_id": request_ctx.get("source_share_id"),
                "source_token_prefix": str(request_ctx.get("source_token_prefix") or "")[:8],
                "new_conversation_id": request_ctx.get("new_conversation_id"),
            },
            ["share.token_full"],
        )
    # TASK-0094 Sprint 1 Phase 12 (D14): sandbox SQL audit case 3.
    # D12 정합 — raw SQL 절대 ChangeJson 미포함. AST normalized + denied_patterns 만.
    if action == "attachment.sandbox.sql_exec":
        return (
            {
                "attachment_ids": list(request_ctx.get("attachment_ids") or []),
                "conversation_id": request_ctx.get("conversation_id"),
                "statement_type": str(request_ctx.get("statement_type") or ""),
                "table_refs": list(request_ctx.get("table_refs") or []),
                "row_count": int(request_ctx.get("row_count") or 0),
                "elapsed_ms": float(request_ctx.get("elapsed_ms") or 0.0),
            },
            ["attachment.raw_sql"],
        )
    if action == "attachment.sandbox.sql_denied":
        return (
            {
                "attachment_ids": list(request_ctx.get("attachment_ids") or []),
                "conversation_id": request_ctx.get("conversation_id"),
                "denied_reason": str(request_ctx.get("denied_reason") or ""),
                "denied_patterns": list(request_ctx.get("denied_patterns") or []),
            },
            ["attachment.raw_sql"],
        )
    # DEPRECATED (feature-0003 attach-full-scope, 2026-07-29): "이 대화의 모든 첨부 사용" 토글이
    # 제거되어 이 action 을 새로 dispatch 하는 경로는 없다. 과거 감사 기록의 렌더링 정합을 위해
    # case 자체는 남긴다(ActionCode 카탈로그 하위호환).
    if action == "attachment.scope.all":
        return (
            {
                "conversation_id": request_ctx.get("conversation_id"),
                "attachment_count": int(request_ctx.get("attachment_count") or 0),
            },
            [],
        )
    if action == "share.policy.redact_applied":
        # TASK-0094 Sprint 1 Phase 8 (R-F7): 기존 token 의 자동 redact 적용 기록.
        return (
            {
                "share_id": request_ctx.get("share_id"),
                "token_prefix": str(request_ctx.get("token_prefix") or "")[:8],
                "token_policy_version": request_ctx.get("token_policy_version"),
                "current_policy_version": request_ctx.get("current_policy_version"),
                "redact_reason": str(request_ctx.get("redact_reason") or "policy_version_mismatch"),
            },
            ["share.token_full"],
        )
    # TASK-0094 Sprint 1 Phase 5 — 첨부 audit ActionCode 4 종 (D12 masking 정합).
    # raw filename / SQL / bytes 는 절대 ChangeJson 에 포함 안 함. HMAC + size bucket
    # + extension bucket + status 같은 categorical 메타만.
    if action == "attachment.upload":
        return (
            {
                "attachment_id": (after or {}).get("id"),
                "conversation_id": (after or {}).get("conversation_id"),
                "filename_hmac": (after or {}).get("filename_hmac"),
                "extension_bucket": (after or {}).get("extension_bucket"),
                "size_bucket": (after or {}).get("size_bucket"),
                "kind": (after or {}).get("kind"),
                "mime_type": (after or {}).get("mime_type"),
                "sha256": (after or {}).get("sha256"),
                "upload_status": (after or {}).get("upload_status"),
            },
            ["attachment.original_filename", "attachment.bytes"],
        )
    if action == "attachment.delete":
        return (
            {
                "attachment_id": (before or {}).get("id"),
                "conversation_id": (before or {}).get("conversation_id"),
                "filename_hmac": (before or {}).get("filename_hmac"),
                "extension_bucket": (before or {}).get("extension_bucket"),
                "size_bucket": (before or {}).get("size_bucket"),
                "delete_reason": (before or {}).get("delete_reason") or "user",
            },
            ["attachment.original_filename", "attachment.bytes"],
        )
    # TASK-0094 Sprint 2 (S2.5) — vision invoke audit. D12 정합:
    # raw bytes / raw filename / raw object_key 절대 미노출. attachment_metas 는
    # [{attachment_id, mime_type, size_bucket}] 만 — categorical 버킷 한정.
    # provider/model 은 catalog alias (e.g., 'anthropic' / 'claude-sonnet-4') 만.
    if action == "attachment.vision.invoke":
        return (
            {
                "provider": request_ctx.get("provider"),
                "model": request_ctx.get("model"),
                "conversation_id": request_ctx.get("conversation_id"),
                "attachment_count": int(request_ctx.get("attachment_count") or 0),
                "attachment_metas": list(request_ctx.get("attachment_metas") or []),
                "status": str(request_ctx.get("status") or "success"),
                "error_reason": request_ctx.get("error_reason"),
            },
            ["attachment.bytes", "attachment.original_filename", "attachment.object_key"],
        )
    # TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 / 관리자 잠금 해제 audit.
    if action == "auth.lockout":
        return (
            {
                "target_username": request_ctx.get("username"),
                "lockout_minutes": int(request_ctx.get("lockout_minutes") or 0),
                "remote_addr_present": bool(request_ctx.get("remote_addr")),
            },
            [],
        )
    if action == "auth.unlock":
        return (
            {
                "target_account_id": request_ctx.get("target_account_id"),
                "target_username": request_ctx.get("username"),
                "was_locked": bool(request_ctx.get("was_locked")),
            },
            [],
        )
    # TASK-20260619T030500-llm-usage-quota (보안 ④): LLM 사용량 한도 설정 변경 audit.
    if action == "quota.role.update":
        return (
            {
                "target_role_id": request_ctx.get("role_id"),
                "daily": request_ctx.get("daily"),
                "monthly": request_ctx.get("monthly"),
            },
            [],
        )
    if action == "quota.account.update":
        return (
            {
                "target_account_id": request_ctx.get("account_id"),
                "daily": request_ctx.get("daily"),
                "monthly": request_ctx.get("monthly"),
            },
            [],
        )
    # TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA 활성/해제/관리자 해제 + 로그인 TOTP audit.
    if action == "auth.totp.enable":
        return ({"backup_codes_issued": int(request_ctx.get("backup_codes_issued") or 0)}, [])
    if action == "auth.totp.disable":
        return ({"by": request_ctx.get("by") or "self"}, [])
    if action == "auth.totp.admin_disable":
        return (
            {
                "target_account_id": request_ctx.get("target_account_id"),
                "target_username": request_ctx.get("username"),
                "was_enabled": bool(request_ctx.get("was_enabled")),
            },
            [],
        )
    if action == "auth.login.totp":
        return (
            {
                "method": request_ctx.get("method"),
                "remote_addr_present": bool(request_ctx.get("remote_addr")),
            },
            [],
        )
    # feature-0018 runtime-settings: 실행 타임아웃·모델별 추론 예산 설정 변경/초기화 audit.
    # 값은 운영 튜닝 파라미터(비민감) — masked_fields 없음. before/after(value)는 caller 가 전달하나
    # 본 builder 는 request_ctx 기반으로 요약(선례 정합). PB-0008 라이브 검증에서 미등록 raise 로
    # write 경로가 fail-closed(audit 실패→rollback) 된 것을 적발해 등록(Codex C6 allowlist 준수).
    if action == "system.runtime.update":
        # previous_value: caller 가 캡처한 직전 override 값(before)을 감사에 보존한다(포렌식 —
        # "무엇에서 무엇으로 바뀌었나"). override 없던 상태면 None.
        return (
            {
                "setting_key": request_ctx.get("key"),
                "value": request_ctx.get("value"),
                "previous_value": (before or {}).get("value"),
            },
            [],
        )
    if action == "system.runtime.reset":
        return (
            {
                "setting_key": request_ctx.get("key"),
                "previous_value": (before or {}).get("value"),
            },
            [],
        )
    # Unknown ActionCode — explicit raise (Codex C6 builder allowlist policy).
    raise ValueError(f"unknown audit action: {action}")

def _audit_admin_mutation(
    conn,
    request: Request,
    actor_account: dict,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    before: dict | None = None,
    after: dict | None = None,
    request_ctx: dict | None = None,
    target_account_id: int | None = None,
) -> None:
    """Phase A5 helper: admin endpoint same-tx audit hook. builder dispatch + dispatcher 호출.

    caller 가 commit 직전에 1 line 으로 호출. 실패 = caller tx rollback (Same tx fail-safe).
    """
    change_json, masked_fields = build_audit_change_json(
        action=action,
        before=before,
        after=after,
        request_ctx=request_ctx,
    )
    actor = app._build_actor_from_request(request, actor_account, actor_type="account")
    app.record_audit_event(
        conn,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        change_json=change_json,
        masked_fields=masked_fields or None,
        target_account_id=target_account_id,
    )

def _audit_user_action(
    conn,
    request: Request,
    account: dict | None,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    request_ctx: dict | None = None,
    target_account_id: int | None = None,
    actor_type: str = "account",
) -> None:
    """Phase A6 helper: user endpoint best-effort audit (fail-open).

    TASK-0072 `_log_search_activity` 패턴 답습 — 실패 시 stderr log + main flow 진행.
    `/api/ask` 의 long-running LLM 실행 / share view 의 anonymous flow 등 audit 실패가
    user 응답을 차단하면 안 되는 경로 전용.
    """
    try:
        change_json, masked_fields = build_audit_change_json(
            action=action,
            before=None,
            after=None,
            request_ctx=request_ctx,
        )
        actor = app._build_actor_from_request(request, account, actor_type=actor_type)
        app.record_audit_event(
            conn,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            change_json=change_json,
            masked_fields=masked_fields or None,
            target_account_id=target_account_id,
        )
        try:
            conn.commit()
        except Exception:
            pass
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            import sys as _sys
            _sys.stderr.write(f"[TASK-0073 Phase A6] {action} audit failed: {exc}\n")
        except Exception:
            pass

def _audit_row_to_dict(row: dict) -> dict[str, Any]:
    """WebAuditEvents row dict 를 JSON 응답 shape 로 변환."""
    occurred_at = row.get("OccurredAt")
    try:
        change_json_raw = row.get("ChangeJson")
        if isinstance(change_json_raw, (bytes, bytearray)):
            change_json_raw = change_json_raw.decode("utf-8", errors="replace")
        change_obj = json.loads(change_json_raw) if change_json_raw else None
    except Exception:
        change_obj = None
    try:
        masked_raw = row.get("MaskedFields")
        if isinstance(masked_raw, (bytes, bytearray)):
            masked_raw = masked_raw.decode("utf-8", errors="replace")
        masked_obj = json.loads(masked_raw) if masked_raw else None
    except Exception:
        masked_obj = None
    return {
        "id": int(row.get("Id") or 0),
        "actor_account_id": int(row["ActorAccountId"]) if row.get("ActorAccountId") is not None else None,
        "actor_role_id": int(row["ActorRoleId"]) if row.get("ActorRoleId") is not None else None,
        "actor_type": str(row.get("ActorType") or "account"),
        "target_account_id": int(row["TargetAccountId"]) if row.get("TargetAccountId") is not None else None,
        "session_id": str(row.get("SessionId") or "") or None,
        "action_code": str(row.get("ActionCode") or ""),
        "resource_type": str(row.get("ResourceType") or ""),
        "resource_id": str(row.get("ResourceId") or "") or None,
        "change_json": change_obj,
        "masked_fields": masked_obj,
        "remote_addr": str(row.get("RemoteAddr") or "") or None,
        "user_agent": str(row.get("UserAgent") or "") or None,
        "request_id": str(row.get("RequestId") or "") or None,
        "occurred_at": occurred_at.isoformat() if hasattr(occurred_at, "isoformat") else (str(occurred_at) if occurred_at else None),
    }

def _audit_build_self_filter_sql(account_id: int) -> tuple[str, tuple[Any, ...]]:
    """`.own` self filter: `ActorAccountId = :self` (본인이 **수행한** 행위만).

    TASK-0293 (사용자 결정 2026-06-16): 기존 `ActorAccountId OR TargetAccountId`
    (TASK-0073 E1 / 사용자 결정 B — admin→user 이벤트 투명성)를 반전. "내 감사
    로그" 는 내가 actor 인 행위만 노출하고, 내가 단지 대상(target)인 타인의 행위
    (관리자의 비밀번호 초기화·역할 변경·계정 비활성화 등)는 노출하지 않는다.
    그런 이벤트는 `audit.read.any` 보유자만 조회한다(로깅 자체는 유지). SECURITY.md §9.1."""
    return ("ActorAccountId = %s", (int(account_id),))

def _audit_resolve_read_scope(actor: dict[str, Any]) -> str:
    """`audit.read.any` 보유 시 'any', `audit.read.own` 보유 시 'own', 둘 다 없으면 ''."""
    if app._account_has_permission(actor, "audit.read.any"):
        return "any"
    if app._account_has_permission(actor, "audit.read.own"):
        return "own"
    return ""

def _audit_parse_filter_params(request: Request) -> dict[str, Any]:
    """공통 filter 파라미터 파싱 — action_code, resource_type, actor_account_id, actor_type, from_at, to_at, q, cursor, limit."""
    qp = request.query_params
    def _trim(v: str | None) -> str:
        return str(v or "").strip()
    return {
        "action_code": _trim(qp.get("action_code"))[:64],
        "resource_type": _trim(qp.get("resource_type"))[:32],
        "actor_account_id": _trim(qp.get("actor_account_id"))[:32],
        "actor_type": _trim(qp.get("actor_type")).lower()[:16],
        "from_at": _trim(qp.get("from_at"))[:64],
        "to_at": _trim(qp.get("to_at"))[:64],
        "q": _trim(qp.get("q"))[:128],
        "cursor": _trim(qp.get("cursor"))[:64],
        "limit": _trim(qp.get("limit"))[:8],
    }

def _audit_compose_where(
    *,
    scope: str,
    account_id: int,
    params: dict[str, Any],
    cursor_id: int | None = None,
) -> tuple[str, list[Any]]:
    """WHERE clause + parameter list. scope='any' 면 self filter 미적용."""
    conds: list[str] = []
    args: list[Any] = []
    # 1. Scope gate (E1).
    if scope == "own":
        cond, scope_args = _audit_build_self_filter_sql(account_id)
        conds.append(cond)
        args.extend(scope_args)
    # 2. Filters.
    if params.get("action_code"):
        conds.append("ActionCode = %s")
        args.append(params["action_code"])
    if params.get("resource_type"):
        conds.append("ResourceType = %s")
        args.append(params["resource_type"])
    if params.get("actor_account_id"):
        try:
            args.append(int(params["actor_account_id"]))
            conds.append("ActorAccountId = %s")
        except (ValueError, TypeError):
            pass
    if params.get("actor_type"):
        conds.append("ActorType = %s")
        args.append(params["actor_type"])
    if params.get("from_at"):
        conds.append("OccurredAt >= %s")
        args.append(params["from_at"])
    if params.get("to_at"):
        conds.append("OccurredAt <= %s")
        args.append(params["to_at"])
    if params.get("q"):
        # ActionCode + ResourceId substring (PII 노출 면적 최소화 — ChangeJson body 미검색).
        conds.append("(ActionCode LIKE %s OR ResourceId LIKE %s)")
        like_pat = f"%{params['q']}%"
        args.append(like_pat)
        args.append(like_pat)
    # 3. Cursor (Id DESC pagination).
    if cursor_id is not None and cursor_id > 0:
        conds.append("Id < %s")
        args.append(int(cursor_id))
    where_clause = " WHERE " + " AND ".join(conds) if conds else ""
    return where_clause, args

def _audit_parse_cursor(cursor: str) -> int | None:
    if not cursor:
        return None
    try:
        return int(cursor)
    except (ValueError, TypeError):
        return None

def _audit_clamped_limit(raw: str) -> int:
    try:
        n = int(raw)
    except (ValueError, TypeError):
        return app._AUDIT_LIST_DEFAULT_LIMIT
    if n <= 0:
        return app._AUDIT_LIST_DEFAULT_LIMIT
    return min(n, app._AUDIT_LIST_MAX_LIMIT)

def _audit_export_filter_hash(params: dict) -> str:
    """TASK-0090: export self-audit 용 filter hash (PII 회피 — raw filter value 대신 hash)."""
    import hashlib as _h
    serialized = json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)
    return _h.sha256(serialized.encode("utf-8")).hexdigest()[:16]


# ==== feature-0012 ITEM-10 p17 — app.py 에서 이동한 도메인 상수 (2종). ====

# TASK-20260619T023922-audit-tamper-evidence (보안 ③): 해시 체인 정규화 + 봉인.
# 정규화 행 필드는 INSERT 시 불변 컬럼만 — EventHash/PrevHash 자신은 제외(봉인 UPDATE 가
# 해시를 무효화하지 않도록). OccurredAt 은 ISO 문자열로 안정 직렬화.
_AUDIT_CHAIN_FIELDS = (
    "Id", "ActorAccountId", "ActorRoleId", "ActorType", "TargetAccountId",
    "SessionId", "ActionCode", "ResourceType", "ResourceId",
    "ChangeJson", "MaskedFields", "RemoteAddr", "UserAgent", "RequestId", "OccurredAt",
)

# TASK-0091 (REQ-20260520-0006, Codex outside voice C1+C4): allowlist 정정.
# - `is_default` + `sort_order` 추가 (Codex C4 — endpoint 가 갱신 가능한데 누락이던 결함).
# - `system_prompt_summary` 신설 (Codex C1 + SECURITY.md §9.2 — full content 금지,
#   `{present, content_len, updated_at}` summary 만).
# - `databases` 제거 (Codex C3 — 별 endpoint `admin.product.databases.update` 의
#   audit 으로 분리, admin.product.update 의 ChangeJson 에서 noise + state mismatch).
# - `system_prompt` 제거 (Codex C1 — full content 금지). admin.system_prompt.update
#   는 별 builder branch (line 8990~) 가 `system_prompt.content_full` masked 처리.
_AUDIT_BUILDER_PRODUCT_FIELDS = (
    "product_key", "name", "description", "is_active", "is_default", "sort_order",
    "default_role_access", "system_prompt_summary",
)
