#!/usr/bin/env bash
# =============================================================================
# alembic-reparent.sh — 병렬 브랜치 마이그레이션 번호 경합(multi-head) 해소 자동화.
# (parallel-work-structure ITEM-02 — 0036 실충돌의 수동 re-parent(6263e641)를 스크립트화)
#
# 병렬 브랜치 두 개가 같은 번호(예: 0040)로 마이그레이션을 만들면, 늦게 머지되는 쪽이
# 본 스크립트로 자기 revision 을 새 번호로 재부모화(re-parent)한다:
#   1. 파일명 번호 치환      : YYYYMMDD_<old>_slug.py → YYYYMMDD_<new>_slug.py (git mv)
#   2. revision id 치환      : "<old>_slug" → "<new>_slug"
#   3. down_revision 치환    : 현 head(대상 파일 제외 그래프의 단일 head)를 가리키도록
#   4. MAX_MIGRATION.txt 갱신: 새 revision id (의도적 충돌 파일 — migrate-lint 정합 검사)
#   5. migrate-lint --heads 재실행으로 해소 확인
#
# 사용:
#   bin/alembic-reparent.sh <versions/파일.py | 파일명> <new-number(4자리)>
#
# GUARD (MIGRATIONS.md 규약): 아직 origin/main 에 머지되지 않은 자기 브랜치 파일만 대상.
# 머지된 마이그레이션 재번호는 라이브 alembic_version stamp 를 파손하므로 금지한다.
#
# Exit codes: 0 성공 / 1 lint 재검 실패 / 2 usage·guard 위반
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS_DIR="unit/feature-0002-agent-core/alembic/versions"

log() { printf '[alembic-reparent] %s\n' "$*" >&2; }
die() { printf '[alembic-reparent] ERROR: %s\n' "$*" >&2; exit 2; }

[ $# -eq 2 ] || die "usage: bin/alembic-reparent.sh <versions/파일.py> <new-number(4자리)>"
TARGET_IN="$1"
NEW_NUM="$2"

[[ "$NEW_NUM" =~ ^[0-9]{4}$ ]] || die "new-number 는 4자리 숫자여야 함: '$NEW_NUM'"

base="$(basename "$TARGET_IN")"
TARGET="$REPO_ROOT/$VERSIONS_DIR/$base"
[ -f "$TARGET" ] || die "대상 파일 없음: $VERSIONS_DIR/$base"

[[ "$base" =~ ^([0-9]{8})_([0-9]{4})_(.+)\.py$ ]] || die "파일명 규약(YYYYMMDD_NNNN_slug.py) 위반: $base"
DATE_PART="${BASH_REMATCH[1]}"
OLD_NUM="${BASH_REMATCH[2]}"
SLUG="${BASH_REMATCH[3]}"

# ── GUARD: origin/main 에 이미 존재하는(머지된) revision 재번호 금지 ─────────
if git -C "$REPO_ROOT" cat-file -e "origin/main:$VERSIONS_DIR/$base" 2>/dev/null; then
  die "origin/main 에 이미 머지된 revision — 재번호 금지 (라이브 stamp 파손). 미머지 자기 브랜치 파일만 대상."
fi

NEW_BASE="${DATE_PART}_${NEW_NUM}_${SLUG}.py"
NEW_TARGET="$REPO_ROOT/$VERSIONS_DIR/$NEW_BASE"
[ -e "$NEW_TARGET" ] && die "새 파일명이 이미 존재: $NEW_BASE"

# ── 현 head 계산 (대상 파일 제외 그래프 — 정적 파싱, 라이브 DB 불필요) ───────
CUR_HEAD="$(python3 - "$REPO_ROOT/$VERSIONS_DIR" "$base" <<'PY'
import ast, os, sys
vdir, exclude = sys.argv[1], sys.argv[2]
revs, downs = {}, {}
for fn in sorted(os.listdir(vdir)):
    if not fn.endswith(".py") or fn == exclude:
        continue
    tree = ast.parse(open(os.path.join(vdir, fn), encoding="utf-8").read())
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
            down = val.value
    if rev:
        revs[rev] = fn
        downs[rev] = down
referenced = {d for d in downs.values() if d}
heads = sorted(r for r in revs if r not in referenced)
if len(heads) != 1:
    print("ERROR: 대상 제외 그래프의 head 가 %d개 (%s) — 다른 경합부터 해소 필요" % (len(heads), ", ".join(heads)), file=sys.stderr)
    sys.exit(1)
print(heads[0])
PY
)" || die "현 head 계산 실패"

OLD_REV="${OLD_NUM}_${SLUG}"
NEW_REV="${NEW_NUM}_${SLUG}"
log "re-parent: $base → $NEW_BASE"
log "  revision:      $OLD_REV → $NEW_REV"
log "  down_revision: → $CUR_HEAD (현 head)"

# ── 파일 내부 revision / down_revision 치환 (annotation 유무 양쪽 대응) ───────
python3 - "$TARGET" "$OLD_REV" "$NEW_REV" "$CUR_HEAD" <<'PY'
import re, sys
path, old_rev, new_rev, new_down = sys.argv[1:5]
src = open(path, encoding="utf-8").read()
src2, n1 = re.subn(
    r'(?m)^(revision(?:\s*:[^=]+)?\s*=\s*)["\']%s["\']' % re.escape(old_rev),
    lambda m: '%s"%s"' % (m.group(1), new_rev), src)
src2, n2 = re.subn(
    r'(?m)^(down_revision(?:\s*:[^=]+)?\s*=\s*)(["\'][^"\']*["\']|None)',
    lambda m: '%s"%s"' % (m.group(1), new_down), src2)
if n1 != 1 or n2 != 1:
    print("ERROR: revision(%d)/down_revision(%d) 치환 실패 — 수동 확인 필요" % (n1, n2), file=sys.stderr)
    sys.exit(1)
open(path, "w", encoding="utf-8").write(src2)
PY

# ── git mv (추적 중이면) / 일반 mv (미추적) ──────────────────────────────────
if git -C "$REPO_ROOT" ls-files --error-unmatch "$VERSIONS_DIR/$base" >/dev/null 2>&1; then
  git -C "$REPO_ROOT" mv "$VERSIONS_DIR/$base" "$VERSIONS_DIR/$NEW_BASE"
else
  mv "$TARGET" "$NEW_TARGET"
fi

# ── MAX_MIGRATION.txt 갱신 (re-parent 후 새 revision 이 head) ─────────────────
printf '%s\n' "$NEW_REV" >"$REPO_ROOT/$VERSIONS_DIR/MAX_MIGRATION.txt"
log "MAX_MIGRATION.txt → $NEW_REV"

# ── lint 재실행으로 해소 확인 ─────────────────────────────────────────────────
if bash "$REPO_ROOT/bin/migrate-lint.sh" --heads; then
  log "완료 — head 단일성 복원"
  exit 0
fi
log "re-parent 후에도 lint FAIL — 위 항목 수동 확인 필요"
exit 1
