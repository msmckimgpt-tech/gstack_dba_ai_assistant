#!/usr/bin/env bash
# =============================================================================
# mysql-ddl-lint.sh — feature-0015 (②): MySQL DDL online-safety 게이트.
#
# MySQL 단일 인스턴스(agent_memory, replica 없음)에서 ALTER TABLE 이 silent COPY 알고리즘
# 으로 떨어지면 그 테이블 DML 이 락에 걸려 사용자 체감 중단이 난다. 8.0 online DDL 을
# 강제하기 위해, 신규/변경된 MySQL ALTER 는 `LOCK=NONE`(+ 가급적 `ALGORITHM=INPLACE`)을
# 명시해야 한다. LOCK=NONE 이면 online 불가 시 **에러로 표면화**(silent COPY-lock 차단)되어
# gh-ost/정비창으로 전환 판단이 가능하다.
#
# 적용 범위(휴리스틱): 스키마 비수식(non-schema-qualified) ALTER TABLE — 즉 MySQL agent_memory
# 의 Web* 등. 다음은 제외: alembic/versions(PG), `agent_runtime.`/`agent_kb` 수식(PG),
# 사용자 업로드 SQL 실행 경로(file_ops sandbox), 본 lint 자신.
#
# 기존(이미 적용된) try/except 멱등 가드는 grandfathered — diff 모드라 변경 라인만 검사한다.
# 불가피한 예외는 라인 끝/위에 `# mysql-ddl-lint: allow — <사유> (서명: <name> <YYYY-MM-DD>)`.
#
# 사용:
#   bin/mysql-ddl-lint.sh                 # origin/main 대비 added/changed 라인 검사
#   bin/mysql-ddl-lint.sh --base <ref>
#   bin/mysql-ddl-lint.sh --all           # 전체 감사(기존 사이트 포함 — 참고용)
#   bin/mysql-ddl-lint.sh --self-test
# Exit: 0 통과 / 1 위반 / 2 usage.
# =============================================================================
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASE_REF="origin/main"; MODE="diff"
log() { printf '[mysql-ddl-lint] %s\n' "$*" >&2; }
die() { printf '[mysql-ddl-lint] ERROR: %s\n' "$*" >&2; exit 2; }

while [ $# -gt 0 ]; do case "$1" in
  --base) BASE_REF="${2:?}"; shift 2 ;;
  --all) MODE="all"; shift ;;
  --self-test) MODE="self-test"; shift ;;
  --help|-h) sed -n '2,33p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) die "unknown arg: $1" ;;
esac; done

# 한 라인이 "검사 대상 MySQL ALTER" 인지 + 위반인지 판정. echo 위반사유 / 반환 0=위반.
# stdin: "파일:라인내용" 형태.
is_violation() {  # $1 = line content
  # 단일 라인 검사 — online 절(ALGORITHM/LOCK=NONE)은 ALTER TABLE 과 **같은 소스 라인**에 둘 것.
  # (multi-line 문자열 concat 으로 쪼개면 첫 라인이 false-positive 로 잡힌다 → escape 또는 한 줄로.)
  local line="$1"
  printf '%s' "$line" | grep -qiE 'ALTER[[:space:]]+TABLE' || return 1            # ALTER TABLE 아님
  printf '%s' "$line" | grep -qiE 'agent_runtime\.|agent_kb|information_schema|pg_' && return 1   # PG/메타 — 제외
  printf '%s' "$line" | grep -qiE 'mysql-ddl-lint:[[:space:]]*allow' && return 1   # 서명 escape
  # online 절(LOCK=NONE) 있으면 통과
  printf '%s' "$line" | grep -qiE 'LOCK[[:space:]]*=[[:space:]]*NONE' && return 1
  return 0   # ALTER TABLE 인데 LOCK=NONE 없음 + escape 없음 → 위반
}

run_self_test() {
  local rc=0
  is_violation 'cur.execute("ALTER TABLE WebProducts ADD COLUMN X INT NULL")' \
    && log "self-test ok: bare MySQL ALTER → 적발" || { log "self-test FAIL: bare ALTER 미적발"; rc=1; }
  is_violation 'cur.execute("ALTER TABLE WebProducts ADD COLUMN X INT NULL, ALGORITHM=INPLACE, LOCK=NONE")' \
    && { log "self-test FAIL: LOCK=NONE 오탐"; rc=1; } || log "self-test ok: LOCK=NONE → 통과"
  is_violation 'op.execute("ALTER TABLE agent_runtime.core_messages ADD COLUMN y int")' \
    && { log "self-test FAIL: PG(agent_runtime) 오탐"; rc=1; } || log "self-test ok: PG agent_runtime → 제외"
  is_violation 'cur.execute("ALTER TABLE Foo DROP COLUMN bar")  # mysql-ddl-lint: allow — FK only (서명: ops 2026-06-30)' \
    && { log "self-test FAIL: 서명 escape 오탐"; rc=1; } || log "self-test ok: 서명 escape → 통과"
  [ "$rc" -eq 0 ] && log "self-test 전체 PASS" || log "self-test FAIL"
  return "$rc"
}

collect_lines() {  # echo "path:content" for candidate lines
  case "$MODE" in
    all)
      grep -rnE 'ALTER[[:space:]]+TABLE' --include='*.py' --include='*.sql' \
        unit/ 2>/dev/null | grep -vE '/alembic/|/_archive/|mysql-ddl-lint' || true
      ;;
    diff)
      if git rev-parse --verify --quiet "$BASE_REF" >/dev/null 2>&1; then
        git diff "$BASE_REF"...HEAD -- 'unit/**/*.py' 'unit/**/*.sql' 2>/dev/null
        git diff HEAD -- 'unit/**/*.py' 'unit/**/*.sql' 2>/dev/null
      else
        git diff HEAD -- 'unit/**/*.py' 'unit/**/*.sql' 2>/dev/null
      fi | grep -E '^\+' | grep -vE '^\+\+\+' | sed 's/^\+//' | grep -iE 'ALTER[[:space:]]+TABLE' \
        | grep -vE '/alembic/|mysql-ddl-lint' || true
      ;;
  esac
}

[ "$MODE" = "self-test" ] && { run_self_test; exit $?; }

violations=0
while IFS= read -r raw; do
  [ -n "$raw" ] || continue
  # all 모드는 "path:lineno:content", diff 모드는 "content".
  content="$raw"; loc=""
  if [ "$MODE" = "all" ]; then loc="${raw%%:*}"; content="${raw#*:}"; fi
  if is_violation "$content"; then
    log "✗ online 절(LOCK=NONE) 없는 MySQL ALTER: ${loc:+$loc — }$(printf '%s' "$content" | sed 's/^[[:space:]]*//' | cut -c1-100)"
    violations=$((violations+1))
  fi
done < <(collect_lines)

if [ "$violations" -gt 0 ]; then
  log ""
  log "$violations 건 — MySQL ALTER 에 'ALGORITHM=INPLACE, LOCK=NONE' 명시 필요(silent COPY-lock 차단)."
  log "online 불가한 변경이면 gh-ost/정비창. 불가피하면 라인에 '# mysql-ddl-lint: allow — <사유> (서명: <name> <date>)'."
  log "규칙: docs/CONVENTIONS.md §13."
  exit 1
fi
log "통과 — 신규/변경 MySQL ALTER 없음 또는 모두 online 명시."
exit 0
