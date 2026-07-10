#!/usr/bin/env bash
# =============================================================================
# migrate-lint.sh — feature-0014 (P0a): 무중단(롤링) 배포의 마이그레이션 안전 게이트.
#
# 무중단 배포는 두 web 버전(OLD/NEW)이 공유 DB 에 잠시 공존하는 창을 만든다. 그 창에서
# 안전하려면 모든 alembic revision 이 **expand/contract(backward-compatible)** 여야 한다:
# OLD 코드가 보지 못하는 컬럼/테이블 추가(expand)는 안전하지만, OLD 코드가 여전히 쓰는
# 컬럼/테이블/제약을 DROP/RENAME/타입변경(contract)하면 롤아웃 중 OLD replica 가 깨진다.
#
# 본 스크립트는 신규/변경된 alembic revision 의 `upgrade()` 본문을 스캔해 비가산(non-additive)
# DDL 을 적발한다. downgrade() 의 drop 은 정상(역연산)이라 스캔하지 않는다.
#
# contract 단계가 정말 필요하면(= NEW 코드 배포 후 별도 cycle 에서 떼는 2-phase) revision
# 파일에 서명 annotation 을 남겨 escape 한다:
#     # migrate-lint: contract-deferred — <사유> (서명: <name> <YYYY-MM-DD>)
#   또는
#     # migrate-lint: allow <op> — <사유> (서명: <name> <YYYY-MM-DD>)
#
# 사용:
#   bin/migrate-lint.sh                 # origin/main 대비 added/modified revision 린트 (+head 검사)
#   bin/migrate-lint.sh --base <ref>    # 다른 base 대비
#   bin/migrate-lint.sh --all           # 전체 revision 감사 (+head 검사)
#   bin/migrate-lint.sh --files a.py b.py
#   bin/migrate-lint.sh --heads         # head 단일성·번호 중복·MAX_MIGRATION 정합만 검사
#                                       #   (라이브 DB 불필요 — 정적 파싱, CI 머지 게이트용.
#                                       #    parallel-work-structure ITEM-02)
#   bin/migrate-lint.sh --self-test     # 내장 양성/음성 케이스 자가 검증 (CI 용)
#   bin/migrate-lint.sh --help
#
# Exit codes:
#   0 — 모든 대상이 expand-safe 또는 서명 annotation 으로 acknowledged (+head 단일)
#   1 — 비가산 DDL 발견(서명 annotation 없음) 또는 multi-head/번호중복/MAX_MIGRATION 불일치 → 배포/머지 차단
#   2 — usage error
#
# Requires: bash >= 4, awk, grep, git.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS_DIR="unit/feature-0002-agent-core/alembic/versions"

BASE_REF="origin/main"
MODE="diff"   # diff | all | files | self-test
FILES=()

log()  { printf '[migrate-lint] %s\n' "$*" >&2; }
die()  { printf '[migrate-lint] ERROR: %s\n' "$*" >&2; exit 2; }

usage() {
  sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

# ── arg parse ──────────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --base)  BASE_REF="${2:?--base 인자 필요}"; shift 2 ;;
    --all)   MODE="all"; shift ;;
    --files) MODE="files"; shift; while [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; do FILES+=("$1"); shift; done ;;
    --heads) MODE="heads"; shift ;;
    --self-test) MODE="self-test"; shift ;;
    --help|-h) usage 0 ;;
    *) die "알 수 없는 인자: $1" ;;
  esac
done

# ── 서명 annotation 존재 여부 ───────────────────────────────────────────────
has_signed_annotation() {
  grep -Eq '#[[:space:]]*migrate-lint:[[:space:]]*(contract-deferred|allow)\b.*(서명|signed)' "$1"
}

# ── AST 기반 분석기 (python3) ───────────────────────────────────────────────
# upgrade() 만 분석하고 downgrade() 는 제외한다. op.execute(IDENT) 의 IDENT 가
# 모듈 레벨 문자열 상수면 그 본문(raw SQL)까지 따라가 검사한다 (0009/0015 패턴).
ANALYZER_PY='
import ast, sys, re
path = sys.argv[1]
try:
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
except SyntaxError as e:
    print("  - 파일 파싱 실패: %s — 수동 확인 필요" % e); sys.exit(1)

consts = {}
for n in tree.body:
    if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
        for t in n.targets:
            if isinstance(t, ast.Name):
                consts[t.id] = n.value.value

up = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade"), None)
if up is None:
    sys.exit(0)

OPS = {
  "drop_table": "DROP TABLE (op.drop_table)",
  "drop_column": "DROP COLUMN (op.drop_column) — OLD 코드가 쓰면 깨짐; 2-phase 로 분리",
  "drop_constraint": "DROP CONSTRAINT (op.drop_constraint)",
  "rename_table": "RENAME TABLE (op.rename_table) — expand(새 이름 추가)+백필 후 contract",
}
def _exec_strings(node):
    # op.execute 인자에서 raw SQL 문자열을 재귀 수집. 반환 (strings, fully_resolved).
    # text("...")/sa.text("...")(Call), f-string(JoinedStr), 문자열 concat(BinOp) 까지 따라간다.
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value], True
    if isinstance(node, ast.Name):
        return ([consts[node.id]], True) if node.id in consts else ([], False)
    if isinstance(node, ast.Call):
        out, res = [], bool(node.args)
        for arg in node.args:
            s, r = _exec_strings(arg); out += s; res = res and r
        return out, res
    if isinstance(node, ast.JoinedStr):  # f-string — 보간부는 동적이라 resolved=False
        return [v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)], False
    if isinstance(node, ast.BinOp):  # "A" + "B" 류 concat
        l, lr = _exec_strings(node.left); r, rr = _exec_strings(node.right)
        return l + r, (lr and rr)
    return [], False

findings, raw_chunks = [], []
for node in ast.walk(up):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        m = node.func.attr
        if m in OPS:
            findings.append(OPS[m])
        elif m == "alter_column":
            kw = {k.arg for k in node.keywords}
            if "new_column_name" in kw:
                findings.append("RENAME COLUMN (op.alter_column new_column_name=) — 2-phase 필요")
            if "type_" in kw:
                findings.append("ALTER COLUMN TYPE (op.alter_column type_=) — in-place 타입 변경 OLD 비호환 위험")
            nn = any(k.arg == "nullable" and isinstance(k.value, ast.Constant) and k.value.value is False for k in node.keywords)
            if nn and "server_default" not in kw:
                findings.append("ADD NOT NULL without server_default (op.alter_column nullable=False) — OLD INSERT 깨짐")
        elif m == "execute" and node.args:
            strs, resolved = _exec_strings(node.args[0])
            raw_chunks.extend(strs)
            if not resolved:
                findings.append("op.execute(...) 동적/래핑 인자(text()/f-string/concat/미해석 상수) — 비가산 여부 수동 확인 필요")

RAW = [
  (r"\bDROP\s+(TABLE|COLUMN|CONSTRAINT|VIEW|MATERIALIZED\s+VIEW)\b", "raw DROP TABLE/COLUMN/CONSTRAINT/VIEW (op.execute)"),
  (r"\bALTER\s+TABLE\b.*\bDROP\b", "raw ALTER TABLE ... DROP (op.execute)"),
  (r"\bALTER\s+(TABLE|COLUMN)\b.*\b(TYPE|RENAME)\b", "raw ALTER ... TYPE/RENAME (op.execute)"),
  (r"\bRENAME\s+(TO|COLUMN)\b", "raw RENAME (op.execute)"),
  (r"\bSET\s+NOT\s+NULL\b", "raw SET NOT NULL (op.execute) — server_default 확인 필요"),
]
# statement(;) 단위로 분리해 cross-statement greedy 오탐 방지.
for chunk in raw_chunks:
    for stmt in chunk.split(";"):
        u = " ".join(stmt.upper().split())
        for pat, label in RAW:
            if re.search(pat, u):
                findings.append(label)

seen, out = set(), []
for f in findings:
    if f not in seen:
        seen.add(f); out.append(f)
for f in out:
    print("  - " + f)
sys.exit(1 if out else 0)
'

# ── head 단일성/번호 중복/MAX_MIGRATION 정합 검사 (parallel-work-structure ITEM-02) ──
# 병렬 브랜치가 같은 번호(예: 0040)로 마이그레이션을 만들면 머지 후에야 multi-head 로
# 발각되던 것(0036 실충돌, 6263e641 수동 re-parent)을 머지 전(CI)에 정적 적발한다.
# 라이브 DB 불필요 — versions/*.py 의 revision/down_revision 만 AST 파싱.
# MAX_MIGRATION.txt(의도적 충돌 파일, django-linear-migrations 패턴 — RESEARCH W-005):
# 최신 head revision id 1줄. 병렬 브랜치가 각자 head 를 만들면 git 머지 시점에 이 파일에서
# 반드시 충돌 → CI 도달 전 fail-fast. lint 는 파일↔실제 head 일치도 검사.
HEAD_CHECK_PY='
import ast, os, re, sys
vdir = sys.argv[1]
maxfile = os.path.join(vdir, "MAX_MIGRATION.txt")
revs, downs, numbers, errs = {}, {}, {}, []
for fn in sorted(os.listdir(vdir)):
    if not fn.endswith(".py"):
        continue
    m = re.match(r"^(\d{8})_(\d{4})_.+\.py$", fn)
    if m:
        numbers.setdefault(m.group(2), []).append(fn)
    else:
        errs.append("파일명 규약(YYYYMMDD_NNNN_slug.py) 위반: %s" % fn)
    try:
        tree = ast.parse(open(os.path.join(vdir, fn), encoding="utf-8").read())
    except SyntaxError as e:
        errs.append("파싱 실패 %s: %s" % (fn, e)); continue
    rev = down = None
    for n in tree.body:
        tgt = val = None
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            tgt, val = n.target.id, n.value
        elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            tgt, val = n.targets[0].id, n.value
        if tgt == "revision" and isinstance(val, ast.Constant) and isinstance(val.value, str):
            rev = val.value
        elif tgt == "down_revision" and isinstance(val, ast.Constant):
            down = val.value  # str 또는 None(baseline)
    if rev is None:
        errs.append("revision 식별자 없음: %s" % fn); continue
    if rev in revs:
        errs.append("revision id 중복: %r (%s ↔ %s)" % (rev, revs[rev], fn))
        continue
    revs[rev] = fn
    downs[rev] = down
for num, fns in sorted(numbers.items()):
    if len(fns) > 1:
        errs.append("revision 번호 %s 중복: %s (병렬 브랜치 번호 경합 — bin/alembic-reparent.sh 로 재번호)" % (num, ", ".join(fns)))
for rev, d in sorted(downs.items()):
    if d and d not in revs:
        errs.append("down_revision %r (%s) 가 존재하지 않는 revision 을 가리킴" % (d, revs[rev]))
referenced = {d for d in downs.values() if d}
heads = sorted(r for r in revs if r not in referenced)
if revs and not heads:
    errs.append("head 없음 — down_revision 그래프에 순환 존재")
elif len(heads) > 1:
    errs.append("multi-head: head %d개 — %s (병렬 마이그레이션 경합; 나중 브랜치를 bin/alembic-reparent.sh 로 re-parent)" % (len(heads), ", ".join(heads)))
if not os.path.isfile(maxfile):
    errs.append("MAX_MIGRATION.txt 없음 — 최신 head revision id 1줄로 생성 필요 (%s)" % maxfile)
elif len(heads) == 1:
    recorded = open(maxfile, encoding="utf-8").read().strip()
    if recorded != heads[0]:
        errs.append("MAX_MIGRATION.txt(%r) != 실제 head(%r) — 신규 마이그레이션/re-parent 시 함께 갱신" % (recorded, heads[0]))
for e in errs:
    print("  - " + e)
if not errs and heads:
    print("  head = %s (단일) · revision %d건 · 번호 중복 0 · MAX_MIGRATION 일치" % (heads[0], len(revs)))
sys.exit(1 if errs else 0)
'

# $1(옵션) = versions 디렉터리 (기본 $REPO_ROOT/$VERSIONS_DIR — self-test 가 임시 디렉터리 주입)
check_heads() {
  local dir="${1:-$REPO_ROOT/$VERSIONS_DIR}" out rc=0
  out="$(python3 -c "$HEAD_CHECK_PY" "$dir")" || rc=$?
  if [ "$rc" -ne 0 ]; then
    log "✗ FAIL head 단일성/번호 중복/MAX_MIGRATION 검사:"
    printf '%s\n' "$out" >&2
    return 1
  fi
  log "✓ PASS head 단일성 검사:"
  printf '%s\n' "$out" >&2
  return 0
}

# ── 비가산 DDL 검사. stdout=발견 목록, 반환=0 발견 / 1 없음(self-test 규약) ───
scan_destructive() {
  local file="$1" out rc
  out="$(python3 -c "$ANALYZER_PY" "$file")" && rc=0 || rc=$?
  printf '%s' "$out"
  [ -n "$out" ] && printf '\n'
  # python: exit 0=발견없음, 1=발견(파싱오류 포함)
  if [ "$rc" -ne 0 ]; then return 0; else return 1; fi
}

# ── 대상 파일 집합 결정 ─────────────────────────────────────────────────────
collect_targets() {
  case "$MODE" in
    all)   ( cd "$REPO_ROOT" && ls "$VERSIONS_DIR"/*.py 2>/dev/null ) ;;
    files) printf '%s\n' "${FILES[@]}" ;;
    diff)
      ( cd "$REPO_ROOT"
        if git rev-parse --verify --quiet "$BASE_REF" >/dev/null 2>&1; then
          git diff --name-only --diff-filter=AM "$BASE_REF"...HEAD -- "$VERSIONS_DIR" 2>/dev/null
          # 미커밋(staged/working) 신규도 포함
          git diff --name-only --diff-filter=AM HEAD -- "$VERSIONS_DIR" 2>/dev/null
          git ls-files --others --exclude-standard -- "$VERSIONS_DIR" 2>/dev/null
        else
          log "base ref '$BASE_REF' 없음 — working tree 의 미커밋 revision 만 검사"
          git diff --name-only --diff-filter=AM HEAD -- "$VERSIONS_DIR" 2>/dev/null
          git ls-files --others --exclude-standard -- "$VERSIONS_DIR" 2>/dev/null
        fi
      ) | sort -u
      ;;
  esac
}

# ── self-test (CI 정적 검증) ────────────────────────────────────────────────
run_self_test() {
  local tmp rc=0
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # (1) 음성: expand-only revision → PASS 기대
  cat >"$tmp/good.py" <<'PY'
def upgrade():
    op.add_column('t', sa.Column('c', sa.Text(), nullable=True))
    op.create_index('ix_t_c', 't', ['c'])
def downgrade():
    op.drop_index('ix_t_c', 't')
    op.drop_column('t', 'c')
PY
  if scan_destructive "$tmp/good.py" >/dev/null; then
    log "self-test FAIL: expand-only revision 이 destructive 로 오탐"; rc=1
  else
    log "self-test ok: expand-only → safe"
  fi

  # (2) 양성: upgrade 에 drop_column → 적발 기대
  cat >"$tmp/bad.py" <<'PY'
def upgrade():
    op.drop_column('t', 'old_col')
def downgrade():
    op.add_column('t', sa.Column('old_col', sa.Text()))
PY
  if scan_destructive "$tmp/bad.py" >/dev/null; then
    log "self-test ok: contract(drop_column) → 적발"
  else
    log "self-test FAIL: drop_column 미적발"; rc=1
  fi

  # (3) downgrade-만-drop 은 무시(역연산은 정상)
  cat >"$tmp/dg.py" <<'PY'
def upgrade():
    op.create_table('t2', sa.Column('id', sa.Integer()))
def downgrade():
    op.drop_table('t2')
PY
  if scan_destructive "$tmp/dg.py" >/dev/null; then
    log "self-test FAIL: downgrade-only drop 이 오탐"; rc=1
  else
    log "self-test ok: downgrade-only drop → 무시"
  fi

  # (4) raw ALTER TABLE DROP 적발
  cat >"$tmp/raw.py" <<'PY'
def upgrade():
    op.execute("ALTER TABLE t DROP COLUMN x")
def downgrade():
    pass
PY
  if scan_destructive "$tmp/raw.py" >/dev/null; then
    log "self-test ok: raw ALTER...DROP → 적발"
  else
    log "self-test FAIL: raw ALTER...DROP 미적발"; rc=1
  fi

  # (5) text("DROP ...") 래퍼 적발 (false-negative 수정 — 백엔드 리뷰 must-fix)
  cat >"$tmp/textwrap.py" <<'PY'
def upgrade():
    op.execute(sa.text("DROP TABLE legacy"))
def downgrade():
    pass
PY
  if scan_destructive "$tmp/textwrap.py" >/dev/null; then
    log "self-test ok: op.execute(text('DROP...')) → 적발"
  else
    log "self-test FAIL: text() 래핑 DROP 미적발"; rc=1
  fi

  # (6) f-string/동적 인자는 '수동 확인' finding 으로 적발 (silent-safe 금지)
  cat >"$tmp/fstr.py" <<'PY'
def upgrade():
    t = "x"
    op.execute(f"ALTER TABLE {t} DROP COLUMN y")
def downgrade():
    pass
PY
  if scan_destructive "$tmp/fstr.py" >/dev/null; then
    log "self-test ok: f-string 동적 DDL → 적발(수동확인)"
  else
    log "self-test FAIL: f-string 동적 DDL 미적발"; rc=1
  fi

  # ── head 단일성 검사 self-test (ITEM-02) ──────────────────────────────────
  _mk_rev() {  # $1=dir $2=filename $3=revision $4=down_revision("None"이면 None)
    local down="$4"
    [ "$down" = "None" ] && down="None" || down="\"$down\""
    cat >"$1/$2" <<PY
revision = "$3"
down_revision = $down
def upgrade():
    pass
def downgrade():
    pass
PY
  }

  # (7) 정상 선형 체인 + MAX 일치 → PASS 기대
  mkdir -p "$tmp/h-good"
  _mk_rev "$tmp/h-good" "20260701_0001_a.py" "0001_a" "None"
  _mk_rev "$tmp/h-good" "20260702_0002_b.py" "0002_b" "0001_a"
  printf '0002_b\n' >"$tmp/h-good/MAX_MIGRATION.txt"
  if check_heads "$tmp/h-good" >/dev/null 2>&1; then
    log "self-test ok: 선형 체인+MAX 일치 → PASS"
  else
    log "self-test FAIL: 정상 체인이 head 검사 오탐"; rc=1
  fi

  # (8) 번호 중복(0040 x2) → FAIL 기대
  mkdir -p "$tmp/h-dup"
  _mk_rev "$tmp/h-dup" "20260701_0001_a.py" "0001_a" "None"
  _mk_rev "$tmp/h-dup" "20260710_0040_x.py" "0040_x" "0001_a"
  _mk_rev "$tmp/h-dup" "20260710_0040_y.py" "0040_y" "0001_a"
  printf '0040_x\n' >"$tmp/h-dup/MAX_MIGRATION.txt"
  if check_heads "$tmp/h-dup" >/dev/null 2>&1; then
    log "self-test FAIL: 번호 중복(0040 x2) 미적발"; rc=1
  else
    log "self-test ok: 번호 중복(0040 x2) → 적발"
  fi

  # (9) multi-head (분기 후 미수렴) → FAIL 기대
  mkdir -p "$tmp/h-multi"
  _mk_rev "$tmp/h-multi" "20260701_0001_a.py" "0001_a" "None"
  _mk_rev "$tmp/h-multi" "20260710_0002_x.py" "0002_x" "0001_a"
  _mk_rev "$tmp/h-multi" "20260710_0003_y.py" "0003_y" "0001_a"
  printf '0002_x\n' >"$tmp/h-multi/MAX_MIGRATION.txt"
  if check_heads "$tmp/h-multi" >/dev/null 2>&1; then
    log "self-test FAIL: multi-head 미적발"; rc=1
  else
    log "self-test ok: multi-head → 적발"
  fi

  # (10) MAX_MIGRATION.txt ↔ head 불일치 → FAIL 기대
  mkdir -p "$tmp/h-max"
  _mk_rev "$tmp/h-max" "20260701_0001_a.py" "0001_a" "None"
  _mk_rev "$tmp/h-max" "20260702_0002_b.py" "0002_b" "0001_a"
  printf '0001_a\n' >"$tmp/h-max/MAX_MIGRATION.txt"
  if check_heads "$tmp/h-max" >/dev/null 2>&1; then
    log "self-test FAIL: MAX_MIGRATION 불일치 미적발"; rc=1
  else
    log "self-test ok: MAX_MIGRATION 불일치 → 적발"
  fi

  [ "$rc" -eq 0 ] && log "self-test 전체 PASS" || log "self-test FAIL"
  return "$rc"
}

# ── main ────────────────────────────────────────────────────────────────────
if [ "$MODE" = "self-test" ]; then
  run_self_test; exit $?
fi

if [ "$MODE" = "heads" ]; then
  check_heads; exit $?
fi

mapfile -t targets < <(collect_targets)
# 빈 줄 제거
filtered=()
for f in "${targets[@]}"; do [ -n "$f" ] && filtered+=("$f"); done
targets=("${filtered[@]}")

overall=0
# head 단일성/번호 중복/MAX_MIGRATION 정합 — 변경 유무와 무관한 전역 속성 (ITEM-02)
check_heads || overall=1

if [ "${#targets[@]}" -eq 0 ]; then
  if [ "$overall" -ne 0 ]; then
    log "변경 revision 0건이나 head 검사 FAIL — 위 항목 해소 필요"
    exit 1
  fi
  log "검사 대상 revision 없음 (변경된 alembic revision 0건) → PASS"
  exit 0
fi

log "검사 대상 revision ${#targets[@]}건:"
for rel in "${targets[@]}"; do
  # diff 모드의 path 는 repo 루트 상대. files 모드는 그대로.
  if [ -f "$REPO_ROOT/$rel" ]; then path="$REPO_ROOT/$rel"; else path="$rel"; fi
  [ -f "$path" ] || { log "  (skip, 파일 없음) $rel"; continue; }

  findings="$(scan_destructive "$path" || true)"
  if [ -n "$findings" ]; then
    if has_signed_annotation "$path"; then
      log "  ⚠ ACK  $rel — 비가산 DDL 있으나 서명 annotation 으로 acknowledged (2-phase 전제):"
      printf '%s\n' "$findings" >&2
    else
      log "  ✗ FAIL $rel — 비가산(contract) DDL 발견, 서명 annotation 없음:"
      printf '%s\n' "$findings" >&2
      overall=1
    fi
  else
    log "  ✓ PASS $rel — expand-safe"
  fi
done

if [ "$overall" -ne 0 ]; then
  log ""
  log "비가산 마이그레이션이 무중단 롤아웃의 mixed-version 창을 깨뜨립니다."
  log "해결: (1) contract 단계를 NEW 코드 배포 후 별도 cycle 로 분리(2-phase)하거나,"
  log "      (2) 정말 필요하면 revision 파일에 서명 annotation 추가:"
  log "          # migrate-lint: contract-deferred — <사유> (서명: <name> <YYYY-MM-DD>)"
  exit 1
fi
log "전체 PASS — 모든 변경 revision 이 expand-safe 또는 acknowledged"
exit 0
