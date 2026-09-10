#!/usr/bin/env python3
"""product-access-repair — 접근 주체가 0인 «고립 Product» 를 진단하고, 운영자가 지정한 계정
1개에만 접근 권한을 복구한다.

배경 (DQA-03, `docs/improvements/dqa-field-audit-20260910/EVIDENCE.md` E-03a~e):
    비공개 Product(`WebProducts.DefaultRoleAccess = 0`) 를 만들면 동적 권한 코드
    `product.access.<key>` 는 생성되지만 **어느 역할·계정에도 부여되지 않은 채 commit** 됐다.
    그리고 부여 경로 2곳(`_enforce_override_self_scope` · `_enforce_role_permission_self_scope`)
    은 「행위자가 보유한 코드만 부여」라 아무도 보유하지 않은 코드는 **모든 부여 시도가 403** 이다
    (권한상승 차단으로서 올바른 동작이므로 그대로 유지한다 — `docs/SECURITY.md` §28.6).
    코드는 ITEM-03 에서 고쳐졌고(생성 트랜잭션 안에서 생성자에게 grant), 본 스크립트는
    **그 수정 이전에 이미 고립된 기존 데이터**를 다룬다.

진단 (기본 동작, 읽기 전용 — **활성·비활성 제품 전부**):
    Product ⟕ 동적 권한(`WebPermissions.IsDynamic = 1 AND ProductId = <제품>`) 을 훑어
    각 제품의 **유효 grantee 수**를 센다. 유효 grantee =
      활성 계정(`IsActive = 1 AND DeletedAt IS NULL`) 중
        · 계정 override 가 `allow` 인 계정, 또는
        · **활성 역할**(`WebRoles.IsActive = 1`)의 역할 grant 를 가지며 override 가 `deny` 가 아닌 계정.
    (이 판정은 런타임 정본 `web_context._apply_permission_overrides` 와 같은 규칙이다 —
     deny override 가 역할 grant 를 덮고, 비활성 역할의 grant 는 세지 않는다.)
    유효 grantee 0 이면 고립으로 보고하고, 생성 감사행
    (`WebAuditEvents` ActionCode='admin.product.create' · ResourceType='product')의
    **actor** 를 「복구 후보로 검토할 계정」으로 함께 출력한다. 동적 권한 행 자체가 없는
    제품은 `missing_permission` 으로 구분해 보고한다(부트스트랩 backfill 대상).

복구 (`--apply`):
    **운영자가 지정한 계정 1개**에만 `WebAccountPermissionOverrides` allow 행 **1개**를 넣는다.
      python product_access_repair.py --apply --product <제품Id> --grant-account <계정Id> \
          --operator <수행자 계정Id>
    - `--operator` 는 **이 복구를 수행하는 사람의 계정**이며 감사행의 actor 로 기록된다.
      생략할 수 없다 — 인가 데이터를 만드는 조작이라 「누가 했는지」가 감사 시스템 안에서
      답해져야 한다(actor_type='system' 은 ActorAccountId 를 NULL 로 남긴다).
    - 자동 선택하지 않는다. 감사행 actor 는 «출력»일 뿐 기본값이 아니다 — 인가 데이터를
      스크립트 추론으로 부여하지 않는다(§12.3 Critical).
    - `_set_account_overrides` 의 «DELETE 후 전체 재삽입» 로직을 쓰지 않는다. 그것을 쓰면
      대상 계정의 **기존 override 가 모두 지워진다**. 여기서는 INSERT 1행만 한다.
    - 이미 allow 면 무변경(멱등)으로 종료한다. `deny` 가 걸려 있으면 **자동으로 뒤집지 않고**
      중단한다 — 명시적 거부를 스크립트가 덮는 것은 운영자 의도의 역전이다.
    - 단일 트랜잭션(권한 행 + 감사행) 1 commit. 영향 행 0 이면 전체 rollback.
    - 적용 후 같은 진단을 다시 돌려 해당 제품이 목록에서 사라졌는지 **결과로 대조**한다.

실행 (web 컨테이너 안 — `bin/product-access-repair.sh` 가 감싼다):
    python /app/web/scripts/product_access_repair.py                      # 진단(활성+비활성 전부)
    python /app/web/scripts/product_access_repair.py --json               # 진단(기계 판독)
    python /app/web/scripts/product_access_repair.py --active-only        # 활성 제품만으로 좁힘
    python /app/web/scripts/product_access_repair.py --apply --product 990002 \
        --grant-account 1 --operator 1

Exit: 0 정상(진단 성공 / 복구 성공) · 1 인자·대상 오류 · 2 복구 후 고립 잔존 또는 구세대 이미지
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from typing import Any

sys.path.insert(0, "/app/web")
sys.path.insert(0, "/app")

import app  # noqa: E402  (경로 주입 후 import — 컨테이너 실행 전제)

# 패널 security P3: 이 스크립트는 **호스트의 worktree 사본**이 stdin 으로 들어와 컨테이너의
# `app` 위에서 돈다. 롤링 배포 창에서는 replica 가 서로 다른 세대일 수 있으므로, 필요한 심볼이
# 없으면 raw traceback 대신 **닫히는 방향으로** 사유를 남기고 종료한다(조용한 동작 변화 금지).
_REQUIRED_APP_SYMBOLS = ("OVERRIDE_ALLOW", "OVERRIDE_DENY", "_connect_memory", "record_audit_event")
_missing = [n for n in _REQUIRED_APP_SYMBOLS if not hasattr(app, n)]
if _missing:
    sys.stderr.write(
        "ERROR: 대상 컨테이너의 app 모듈에 필요한 심볼이 없습니다: "
        + ", ".join(_missing)
        + "\n       구세대 이미지로 보입니다 — 배포 완료 후 재시도하세요.\n"
    )
    raise SystemExit(2)


# ── 진단 ─────────────────────────────────────────────────────────────────────

# 유효 grantee 수. 런타임 판정(`_apply_permission_overrides`)과 같은 규칙:
#   allow override → 접근 / deny override → 차단(역할 grant 를 덮음) / 그 외 → 활성 역할 grant.
_EFFECTIVE_GRANTEE_SQL = """
SELECT COUNT(*)
FROM WebAccounts a
LEFT JOIN WebAccountPermissionOverrides o
       ON o.AccountId = a.Id AND o.PermissionId = %s
LEFT JOIN WebRoles r
       ON r.Id = a.RoleId AND r.IsActive = 1
LEFT JOIN WebRolePermissions rp
       ON rp.RoleId = r.Id AND rp.PermissionId = %s
WHERE a.IsActive = 1
  AND a.DeletedAt IS NULL
  AND (
        o.OverrideValue = 'allow'
        OR (rp.PermissionId IS NOT NULL
            AND (o.OverrideValue IS NULL OR o.OverrideValue <> 'deny'))
      )
"""

_PRODUCT_ROWS_SQL = """
SELECT p.Id, p.ProductKey, p.Name, p.IsActive, p.DefaultRoleAccess, perm.Id, perm.Code
FROM WebProducts p
LEFT JOIN WebPermissions perm
       ON perm.IsDynamic = 1 AND perm.ProductId = p.Id
ORDER BY p.Id
"""

_CREATE_ACTOR_SQL = """
SELECT ev.ActorAccountId, ev.OccurredAt, a.Username
FROM WebAuditEvents ev
LEFT JOIN WebAccounts a ON a.Id = ev.ActorAccountId
WHERE ev.ActionCode = 'admin.product.create'
  AND ev.ResourceType = 'product'
  AND ev.ResourceId = %s
ORDER BY ev.OccurredAt DESC
LIMIT 1
"""


def count_effective_grantees(conn, permission_id: int) -> int:
    """권한 코드 1건에 실제로 접근 가능한 활성 계정 수."""
    pid = int(permission_id or 0)
    if pid <= 0:
        return 0
    cur = conn.cursor()
    try:
        cur.execute(_EFFECTIVE_GRANTEE_SQL, (pid, pid))
        row = cur.fetchone()
    finally:
        cur.close()
    return int((row or (0,))[0] or 0)


def find_create_actor(conn, product_id: int) -> dict[str, Any] | None:
    """제품 생성 감사행의 actor(계정 id·이름·시각). 감사 보존기간을 지났으면 None."""
    cur = conn.cursor()
    try:
        cur.execute(_CREATE_ACTOR_SQL, (str(int(product_id)),))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        return None
    account_id = int(row[0] or 0)
    return {
        "account_id": account_id or None,
        "occurred_at": str(row[1]) if len(row) > 1 and row[1] is not None else None,
        "username": str(row[2]) if len(row) > 2 and row[2] else None,
    }


def diagnose(conn, *, active_only: bool = False) -> list[dict[str, Any]]:
    """접근 주체가 0인 제품 목록. **기본은 활성·비활성 전부**를 훑는다.

    ⚠️ 기본값을 「활성만」으로 두면 안 된다 — 실측(2026-09-10 라이브 dry-run)에서 요구서가
    지목한 고립 제품(990002 `DK_KR_S3_20260903`)이 **비활성**이라, 활성만 훑는 기본값은
    「고립 Product 없음」을 출력했다. 진단 도구가 자기가 만들어진 이유인 데이터를 숨기는
    형태였다. 좁히려면 `active_only=True`(CLI `--active-only`)를 명시한다.

    각 항목: {product_id, product_key, name, is_active, default_role_access,
              permission_id, permission_code, grantees, reason, create_actor}
      reason ∈ {"no_grantee", "missing_permission"}
    """
    cur = conn.cursor()
    try:
        cur.execute(_PRODUCT_ROWS_SQL)
        rows = list(cur.fetchall() or [])
    finally:
        cur.close()

    orphans: list[dict[str, Any]] = []
    for row in rows:
        product_id = int(row[0] or 0)
        is_active = bool(row[3])
        if active_only and not is_active:
            continue
        permission_id = int(row[5] or 0) if len(row) > 5 and row[5] is not None else 0
        if permission_id > 0:
            grantees = count_effective_grantees(conn, permission_id)
            if grantees > 0:
                continue
            reason = "no_grantee"
        else:
            grantees = 0
            reason = "missing_permission"
        orphans.append({
            "product_id": product_id,
            "product_key": str(row[1] or ""),
            "name": str(row[2] or ""),
            "is_active": is_active,
            "default_role_access": bool(row[4]),
            "permission_id": permission_id or None,
            "permission_code": str(row[6]) if len(row) > 6 and row[6] else None,
            "grantees": grantees,
            "reason": reason,
            "create_actor": find_create_actor(conn, product_id),
        })
    return orphans


# ── 복구 ─────────────────────────────────────────────────────────────────────

def _load_orphan(conn, product_id: int, *, active_only: bool) -> dict[str, Any] | None:
    for entry in diagnose(conn, active_only=active_only):
        if int(entry["product_id"]) == int(product_id):
            return entry
    return None


def _host_os_user() -> str:
    """호스트/컨테이너의 실행 OS 사용자 — 감사행의 보조 추적점(없으면 빈 문자열)."""
    for getter in (lambda: os.environ.get("SUDO_USER") or "",
                   lambda: os.environ.get("REPAIR_OPERATOR_OS_USER") or "",
                   getpass.getuser):
        try:
            value = str(getter() or "").strip()
        except Exception:
            value = ""
        if value:
            return value[:64]
    return ""


def _account_state(conn, account_id: int) -> dict[str, Any] | None:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT Id, Username, IsActive, DeletedAt FROM WebAccounts WHERE Id = %s",
            (int(account_id),),
        )
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        return None
    return {
        "id": int(row[0] or 0),
        "username": str(row[1] or ""),
        "is_active": bool(row[2]),
        "deleted": bool(len(row) > 3 and row[3] is not None),
    }


def _existing_override(conn, account_id: int, permission_id: int) -> str | None:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT OverrideValue FROM WebAccountPermissionOverrides "
            "WHERE AccountId = %s AND PermissionId = %s",
            (int(account_id), int(permission_id)),
        )
        row = cur.fetchone()
    finally:
        cur.close()
    return str(row[0]) if row and row[0] is not None else None


def repair(conn, product_id: int, account_id: int, *, operator_id: int, active_only: bool = False) -> dict[str, Any]:
    """고립 제품 1건에 대해 계정 1건에만 allow override 를 넣는다 (단일 트랜잭션).

    `operator_id` = **이 복구를 수행하는 사람의 계정 Id**. 감사행의 actor 로 기록된다 —
    인가 데이터를 만드는 조작이므로 「누가 했는지」가 감사 시스템 안에서 답해져야 한다
    (패널 security P2: `actor_type='system'` 만 남기면 ActorAccountId 가 NULL 이라
    docker exec 권한자 누구든 흔적 없이 부여할 수 있었다).

    반환: {status, ...}. status ∈
      ok | already_allowed | not_orphan | product_not_found | missing_permission
      | account_not_found | account_inactive | deny_override_present
      | operator_not_found | operator_inactive
    `ok` 외에는 **아무 것도 쓰지 않는다**.
    """
    operator = _account_state(conn, operator_id)
    if operator is None:
        return {"status": "operator_not_found", "operator_id": int(operator_id)}
    if operator["deleted"] or not operator["is_active"]:
        return {"status": "operator_inactive", "operator_id": int(operator_id),
                "username": operator["username"]}
    entry = _load_orphan(conn, product_id, active_only=active_only)
    if entry is None:
        cur = conn.cursor()
        try:
            cur.execute("SELECT Id FROM WebProducts WHERE Id = %s", (int(product_id),))
            exists = bool(cur.fetchone())
        finally:
            cur.close()
        return {"status": "not_orphan" if exists else "product_not_found",
                "product_id": int(product_id)}
    if entry["reason"] == "missing_permission":
        # 권한 행 자체가 없다 — 부여할 대상이 없으므로 부트스트랩(`_ensure_product_access_permissions`)
        # 이 먼저 돌아야 한다. 스크립트가 권한 카탈로그를 새로 만들지는 않는다(범위 밖).
        return {"status": "missing_permission", "product_id": int(product_id),
                "hint": "web 컨테이너 재기동으로 _ensure_product_access_permissions 백필 후 재시도"}

    permission_id = int(entry["permission_id"] or 0)
    acct = _account_state(conn, account_id)
    if acct is None:
        return {"status": "account_not_found", "account_id": int(account_id)}
    if acct["deleted"] or not acct["is_active"]:
        return {"status": "account_inactive", "account_id": int(account_id),
                "username": acct["username"]}

    current = _existing_override(conn, account_id, permission_id)
    if current == app.OVERRIDE_ALLOW:
        return {"status": "already_allowed", "product_id": int(product_id),
                "account_id": int(account_id)}
    if current == app.OVERRIDE_DENY:
        return {"status": "deny_override_present", "product_id": int(product_id),
                "account_id": int(account_id),
                "hint": "명시적 거부가 걸려 있습니다 — 관리 콘솔에서 먼저 해제하세요(스크립트가 뒤집지 않습니다)"}

    previous_autocommit = getattr(conn, "autocommit", True)
    try:
        conn.autocommit = False
    except Exception:
        pass
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO WebAccountPermissionOverrides "
                "(AccountId, PermissionId, OverrideValue) VALUES (%s, %s, %s)",
                (int(account_id), permission_id, app.OVERRIDE_ALLOW),
            )
            affected = int(getattr(cur, "rowcount", 0) or 0)
        finally:
            cur.close()
        if affected < 1:
            raise RuntimeError("override insert affected 0 rows")
        # 인가 데이터 변경이므로 감사행을 같은 트랜잭션에 남긴다. actor 는 **운영자 계정**
        # (`--operator`) 이다 — 스크립트를 actor 로 두면 ActorAccountId 가 NULL 이라 감사
        # 시스템 안에서 「누가 부여했는가」를 영원히 답할 수 없다(패널 security P2).
        # 호스트 OS 사용자도 보조로 남긴다(컨테이너 밖 추적의 접합점).
        app.record_audit_event(
            conn,
            actor={
                "actor_type": "account",
                "account_id": int(operator_id),
                "username": operator["username"],
                "request_id": "product-access-repair",
            },
            action="admin.product.access.repair",
            resource_type="product",
            resource_id=str(int(product_id)),
            change_json={
                "product_id": int(product_id),
                "product_key": entry["product_key"],
                "permission_code": entry["permission_code"],
                "granted_account_id": int(account_id),
                "granted_username": acct["username"],
                "override_value": app.OVERRIDE_ALLOW,
                "operator_account_id": int(operator_id),
                "operator_username": operator["username"],
                "host_os_user": _host_os_user(),
                "tool": "scripts/product_access_repair.py",
            },
            target_account_id=int(account_id),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.autocommit = previous_autocommit
        except Exception:
            pass
    try:
        app.invalidate_permission_catalog_cache()
    except Exception:
        pass
    return {"status": "ok", "product_id": int(product_id), "account_id": int(account_id),
            "username": acct["username"], "permission_code": entry["permission_code"],
            "operator_account_id": int(operator_id), "operator_username": operator["username"]}


# ── CLI ──────────────────────────────────────────────────────────────────────

def _print_orphans(orphans: list[dict[str, Any]]) -> None:
    if not orphans:
        print("고립 Product 없음 — 모든 제품에 접근 가능한 활성 계정이 1명 이상 있습니다.")
        return
    print(f"고립 Product {len(orphans)}건:")
    for o in orphans:
        actor = o.get("create_actor") or {}
        actor_text = "감사 기록 없음"
        if actor.get("account_id"):
            actor_text = f"생성자 후보 account={actor['account_id']}"
            if actor.get("username"):
                actor_text += f"({actor['username']})"
            if actor.get("occurred_at"):
                actor_text += f" @{actor['occurred_at']}"
        print(
            f"  - #{o['product_id']} {o['product_key']} {o['name']!r} "
            f"active={'Y' if o['is_active'] else 'N'} "
            f"default_role_access={'Y' if o['default_role_access'] else 'N'} "
            f"code={o['permission_code'] or '-'} reason={o['reason']} · {actor_text}"
        )
    print("\n복구: --apply --product <제품Id> --grant-account <계정Id>  (계정은 운영자가 지정)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="접근 주체 0인 고립 Product 진단·복구 (기본 dry-run — 진단만)")
    ap.add_argument("--apply", action="store_true",
                    help="실제 반영. --product 와 --grant-account 필수")
    ap.add_argument("--product", type=int, default=0, help="복구할 제품 Id")
    ap.add_argument("--grant-account", type=int, default=0,
                    help="접근 권한을 부여할 계정 Id (운영자 지정 — 자동 선택 없음)")
    ap.add_argument("--operator", type=int, default=0,
                    help="이 복구를 수행하는 **사람의 계정 Id** — 감사행의 actor. --apply 필수")
    ap.add_argument("--active-only", action="store_true",
                    help="활성 제품(IsActive=1)만 진단 — 기본은 비활성까지 전부")
    ap.add_argument("--json", action="store_true", help="진단 결과를 JSON 으로 출력")
    args = ap.parse_args(argv)

    conn = app._connect_memory()
    try:
        if not args.apply:
            orphans = diagnose(conn, active_only=args.active_only)
            if args.json:
                print(json.dumps({"dry_run": True, "orphans": orphans},
                                 ensure_ascii=False, indent=2, default=str))
            else:
                _print_orphans(orphans)
                print("\n(dry-run — 반영하려면 --apply --product … --grant-account …)")
            return 0

        if args.product <= 0 or args.grant_account <= 0 or args.operator <= 0:
            print("ERROR: --apply 는 --product <제품Id> · --grant-account <계정Id> · "
                  "--operator <수행자 계정Id> 가 모두 필요합니다.", file=sys.stderr)
            print("       대상 계정은 자동 선택하지 않습니다 — 먼저 dry-run 으로 후보를 확인하세요.",
                  file=sys.stderr)
            print("       --operator 는 감사행의 actor 입니다. 보통 --grant-account 와 같은 값이지만 "
                  "명시해야 합니다(누가 부여했는지가 감사에 남아야 합니다).", file=sys.stderr)
            return 1

        result = repair(conn, args.product, args.grant_account,
                        operator_id=args.operator, active_only=args.active_only)
        print(json.dumps(result, ensure_ascii=False, default=str))
        if result.get("status") not in ("ok", "already_allowed"):
            return 1

        # 사후 대조 — 같은 진단을 다시 돌려 그 제품이 목록에서 사라졌는지 «결과로» 확인한다
        # (AGENTS §16.7 G14: 처방을 수행한 절차는 결과 대조로 끝난다).
        remaining = diagnose(conn)
        still = [o for o in remaining if int(o["product_id"]) == int(args.product)]
        print(f"사후 검증: 이 제품의 잔여 고립 {len(still)}건 (0 이어야 정상) · "
              f"전체 잔여 고립 {len(remaining)}건")
        return 0 if not still else 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
