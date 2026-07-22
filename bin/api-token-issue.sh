#!/usr/bin/env bash
#
# api-token-issue.sh — feature-0023 (REQ-20260722-conversation-api-access)
#
# 외부 AI 프로그래매틱 접근용 Bearer API 토큰을 발급/폐기/조회한다. 관리 콘솔이 아닌
# CLI 부트스트랩(사용자 요구: "관리 콘솔 제외"). 토큰은 저권한 서비스 계정에 귀속되고
# scope allowlist(기본 `conversation.,product.access.`)로 관리 엔드포인트가 원천 차단된다.
#
# 보안 설계:
#  - 토큰 원문은 저장하지 않는다 — SHA-256 해시(WebApiTokens.TokenHash)만 저장.
#  - 원문은 발급 시 stdout 에 1회만 출력된다(재확인 불가 — 분실 시 재발급).
#  - 파라미터라이즈드 쿼리(%s)로 SQL injection 차단.
#  - 발급/폐기는 WebAuditEvents(ActionCode apitoken.issue/apitoken.revoke)에 기록.
#
# Usage:
#   bin/api-token-issue.sh --account <username> [--label <라벨>] \
#       [--scopes <csv>] [--expires-days <N>]        # 발급
#   bin/api-token-issue.sh --list [--account <username>]         # 조회(원문 미노출)
#   bin/api-token-issue.sh --revoke <token-id|prefix>           # 폐기
#
# 예:
#   bin/api-token-issue.sh --account svc-bot --label "n8n integration"
#   bin/api-token-issue.sh --account svc-bot --scopes "conversation.,product.access." --expires-days 90
#   bin/api-token-issue.sh --list --account svc-bot
#   bin/api-token-issue.sh --revoke matk_ab12cd3
#
# 권장: 발급 대상은 conversation.ask/create + 필요한 product.access.* 만 가진 **전용
#       저권한 서비스 계정**. scope 는 그 위에 얹는 2차 방어선이다.
#
# Requires: docker compose 가 동작 중이고 web·mysql 서비스가 healthy 여야 함.

set -euo pipefail

MODE="issue"
ACCOUNT=""
LABEL=""
SCOPES="conversation.,product.access."
EXPIRES_DAYS=""
REVOKE_TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --account)   ACCOUNT="${2:-}"; shift 2 ;;
    --label)     LABEL="${2:-}"; shift 2 ;;
    --scopes)    SCOPES="${2:-}"; shift 2 ;;
    --expires-days)
      EXPIRES_DAYS="${2:-}"
      if ! [[ "$EXPIRES_DAYS" =~ ^[0-9]+$ ]]; then echo "--expires-days 는 정수여야 합니다." >&2; exit 2; fi
      shift 2 ;;
    --list)      MODE="list"; shift ;;
    --revoke)    MODE="revoke"; REVOKE_TARGET="${2:-}"; shift 2 ;;
    -h|--help)   sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

if [[ "$MODE" == "issue" && -z "$ACCOUNT" ]]; then
  echo "ERROR: 발급에는 --account <username> 가 필요합니다." >&2; exit 2
fi
if [[ "$MODE" == "revoke" && -z "$REVOKE_TARGET" ]]; then
  echo "ERROR: --revoke 에 token-id 또는 prefix 가 필요합니다." >&2; exit 2
fi

# 파이썬 로직을 web 컨테이너 안에서 실행(mysql.connector·env 보유). 값은 env 로 전달해
# 쿼리는 파라미터라이즈드(%s)로 조립 — injection 차단.
export TOK_MODE="$MODE" TOK_ACCOUNT="$ACCOUNT" TOK_LABEL="$LABEL" \
       TOK_SCOPES="$SCOPES" TOK_EXPIRES_DAYS="$EXPIRES_DAYS" TOK_REVOKE="$REVOKE_TARGET"

docker compose --ansi=never exec -T \
  -e TOK_MODE -e TOK_ACCOUNT -e TOK_LABEL -e TOK_SCOPES -e TOK_EXPIRES_DAYS -e TOK_REVOKE \
  web python3 - <<'PY'
import hashlib, json, os, secrets, sys

def _connect():
    import mysql.connector
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "mysql"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database="agent_memory",
        charset="utf8mb4",
        autocommit=False,
    )

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _resolve_account(cur, username):
    cur.execute(
        "SELECT Id, RoleId, IsActive FROM WebAccounts WHERE Username=%s AND DeletedAt IS NULL LIMIT 1",
        (username,),
    )
    return cur.fetchone()

# REV-20260722 MEDIUM-1: 발급 시 방어(런타임 절대 denylist 가 최종 보증이나, 혼동 방지 위해
# 발급 단계에서도 관리 scope 를 거부하고 privileged 계정 바인딩을 경고한다).
_ALLOWED_SCOPE_PREFIXES = ("conversation.", "product.access.")
_PRIVILEGED_ROLE_NAMES = ("admin", "operator", "dba")

def _validate_scopes(scopes_csv):
    """요청 scope 가 안전 allowlist 접두 내인지 검증. 관리/교차계정 scope 는 거부."""
    items = [s.strip() for s in (scopes_csv or "").split(",") if s.strip()]
    for s in items:
        if s.endswith(".any") or not any(s.startswith(p) or s == p.rstrip(".") for p in _ALLOWED_SCOPE_PREFIXES):
            print(f"ERROR: scope '{s}' 는 허용되지 않습니다. 대화 API 토큰은 "
                  f"{_ALLOWED_SCOPE_PREFIXES} 접두만 가능합니다(관리/교차계정 scope 금지).",
                  file=sys.stderr)
            sys.exit(2)
    return items

def _warn_if_privileged(cur, role_id, username):
    if not role_id:
        return
    cur.execute("SELECT Name FROM WebRoles WHERE Id=%s LIMIT 1", (role_id,))
    row = cur.fetchone()
    rname = (row[0] if row else "") or ""
    if rname.lower() in _PRIVILEGED_ROLE_NAMES:
        print(f"⚠ 경고: 계정 '{username}' 의 역할이 '{rname}'(관리 권한)입니다. API 토큰은 "
              f"**전용 저권한 서비스 계정**에 발급하길 권장합니다. (런타임 denylist 가 관리 "
              f"엔드포인트를 차단하나, 최소권한 원칙상 저권한 계정 사용이 안전합니다.)",
              file=sys.stderr)

def _audit(cur, action, actor_id, resource_id, change):
    # 최소 audit row — EventHash 는 백그라운드 sealer 가 봉인(§13). ResourceType='api_token'.
    cur.execute(
        """
        INSERT INTO WebAuditEvents
            (ActorAccountId, ActorType, ActionCode, ResourceType, ResourceId, ChangeJson)
        VALUES (%s, 'system', %s, 'api_token', %s, %s)
        """,
        (actor_id, action, str(resource_id) if resource_id is not None else None, json.dumps(change, ensure_ascii=False)),
    )

mode = os.getenv("TOK_MODE", "issue")
conn = _connect()
cur = conn.cursor()
try:
    if mode == "issue":
        username = os.getenv("TOK_ACCOUNT", "")
        acc = _resolve_account(cur, username)
        if not acc:
            print(f"ERROR: 계정 '{username}' 을 찾을 수 없습니다.", file=sys.stderr); sys.exit(1)
        acc_id, role_id, is_active = acc
        if not is_active:
            print(f"ERROR: 계정 '{username}' 이 비활성입니다.", file=sys.stderr); sys.exit(1)
        _warn_if_privileged(cur, role_id, username)
        label = (os.getenv("TOK_LABEL", "") or None)
        # REV-20260722 HIGH-2: 빈 scope 를 NULL(무제한)로 저장하지 않는다 — 안전 기본값으로 명시.
        scope_items = _validate_scopes(os.getenv("TOK_SCOPES", ""))
        if not scope_items:
            scope_items = list(_ALLOWED_SCOPE_PREFIXES)
        scopes = ",".join(scope_items)
        expires_days = os.getenv("TOK_EXPIRES_DAYS", "")
        raw = "matk_" + secrets.token_urlsafe(32)
        token_hash = _sha256(raw)
        prefix = raw[:12]
        expires_sql = "DATE_ADD(NOW(), INTERVAL %s DAY)" if expires_days else "NULL"
        params = [acc_id, token_hash, prefix, label, scopes]
        if expires_days:
            params.append(int(expires_days))
        params.append(acc_id)  # CreatedByAccountId (CLI = 서비스 계정 자기 발급 기록)
        cur.execute(
            f"""
            INSERT INTO WebApiTokens
                (AccountId, TokenHash, TokenPrefix, Label, Scopes, ExpiresAt, CreatedByAccountId)
            VALUES (%s, %s, %s, %s, %s, {expires_sql}, %s)
            """,
            tuple(params),
        )
        token_id = cur.lastrowid
        _audit(cur, "apitoken.issue", acc_id, token_id,
               {"prefix": prefix, "label": label, "scopes": scopes,
                "expires_days": (int(expires_days) if expires_days else None)})
        conn.commit()
        print("=== API 토큰 발급 완료 ===")
        print(f"  account   : {username} (id={acc_id})")
        print(f"  token_id  : {token_id}")
        print(f"  prefix    : {prefix}")
        print(f"  scopes    : {scopes}")
        print(f"  expires   : {('%s일 후' % expires_days) if expires_days else '무기한'}")
        print()
        print("  ⚠ 아래 토큰은 이번 1회만 표시됩니다. 안전한 곳(비밀 관리자·MCP .env)에 저장하세요.")
        print(f"  TOKEN     : {raw}")
        print()
        print("  사용: Authorization: Bearer <TOKEN>  → POST /api/ask")
    elif mode == "list":
        username = os.getenv("TOK_ACCOUNT", "")
        where, params = "1=1", []
        if username:
            acc = _resolve_account(cur, username)
            if not acc:
                print(f"ERROR: 계정 '{username}' 을 찾을 수 없습니다.", file=sys.stderr); sys.exit(1)
            where, params = "t.AccountId=%s", [acc[0]]
        cur.execute(
            f"""
            SELECT t.Id, t.TokenPrefix, t.Label, t.Scopes, t.ExpiresAt, t.LastUsedAt,
                   t.RevokedAt, t.CreatedAt, a.Username
            FROM WebApiTokens t JOIN WebAccounts a ON a.Id=t.AccountId
            WHERE {where}
            ORDER BY t.Id DESC
            """,
            tuple(params),
        )
        rows = cur.fetchall()
        print(f"=== API 토큰 {len(rows)}건 ===")
        import datetime as _dt
        now = _dt.datetime.now()
        for r in rows:
            (tid, pfx, lbl, scp, exp, used, rev, created, uname) = r
            if rev:
                state = "revoked"
            elif exp and exp <= now:
                state = "expired"
            else:
                state = "active"
            print(f"  #{tid} [{pfx}] {uname} | {lbl or '-'} | scopes={scp or '(전체)'} | "
                  f"exp={exp or '무기한'} | last_used={used or '없음'} | {state}")
    elif mode == "revoke":
        target = os.getenv("TOK_REVOKE", "")
        if target.isdigit():
            cur.execute("UPDATE WebApiTokens SET RevokedAt=NOW() WHERE Id=%s AND RevokedAt IS NULL", (int(target),))
            key = f"id={target}"
            cur2 = conn.cursor(); cur2.execute("SELECT Id, AccountId FROM WebApiTokens WHERE Id=%s", (int(target),)); found = cur2.fetchone(); cur2.close()
        else:
            cur.execute("UPDATE WebApiTokens SET RevokedAt=NOW() WHERE TokenPrefix=%s AND RevokedAt IS NULL", (target,))
            key = f"prefix={target}"
            cur2 = conn.cursor(); cur2.execute("SELECT Id, AccountId FROM WebApiTokens WHERE TokenPrefix=%s", (target,)); found = cur2.fetchone(); cur2.close()
        affected = cur.rowcount
        if found:
            _audit(cur, "apitoken.revoke", found[1], found[0], {"revoked_by": "cli", "key": key})
        conn.commit()
        print(f"=== 폐기: {key} — {affected}건 갱신 ===")
        if affected == 0:
            print("  (해당 토큰이 없거나 이미 폐기됨)")
    else:
        print(f"ERROR: 알 수 없는 MODE '{mode}'", file=sys.stderr); sys.exit(2)
finally:
    try:
        cur.close(); conn.close()
    except Exception:
        pass
PY
