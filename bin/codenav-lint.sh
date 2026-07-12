#!/usr/bin/env bash
# =============================================================================
# codenav-lint.sh — Code-Navigation Map 앵커 resolvability 정적 검증.
#
# docs/CODE_NAVIGATION.md·docs/CODE_TASKS.md 는 손유지(rewrite) 정본이라 어떤 자동
# 검사도 없이 drift 한다(핸들러 rename·도메인 내부 이동은 경로 불변이라 ROUTEMAP 정합을
# 유지하면서 file:symbol 앵커를 무효화 — AGENTS.md §21.11.4 (앵커) 트리거). 본 린트가
# 그 사각지대를 닫는다: 문서가 지목하는 앵커가 소스에서 실제 resolve 되는지 정적 grep 으로 확인.
#
# 검증 대상:
#   (1) routers/<mod>.py  모듈 참조        → 파일 실재
#   (2) <file>.py:<line> <symbol> 앵커     → file 실재 + `def <symbol>` 존재(line 무시 — 휘발성)
#   (3) DI seam 심볼(get_conn·get_current_account·require_permission·register_all)
#       문서가 app 정본으로 지목             → app.py / routers/__init__.py 에 def 실재
#
# exit 0 = 전부 resolve · exit 3 = STALE(미해결 앵커 목록을 stderr 로).
# 런타임/컨테이너 불요(gen-routemap.py 와 동형의 순수 정적 스캐너) — CI blocking 또는
# verify-completion.sh check #16 로 배선. (AGENTS.md §21.11.4·§21.11.7 순환 폐쇄)
# =============================================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/unit/feature-0003-agent-web-ui/src"
ROUTERS="$SRC/routers"
APP="$SRC/app.py"
INIT="$ROUTERS/__init__.py"
DOCS=("$REPO_ROOT/docs/CODE_NAVIGATION.md" "$REPO_ROOT/docs/CODE_TASKS.md")

fail=0
declare -a unresolved
note() { unresolved+=("$1"); fail=1; }

# 문서/소스 트리 부재 시 non-fatal skip(예: 부분 checkout).
for d in "${DOCS[@]}"; do
  [ -f "$d" ] || { echo "codenav-lint: SKIP — 문서 부재 $d" >&2; exit 0; }
done
[ -d "$ROUTERS" ] || { echo "codenav-lint: SKIP — routers/ 부재 $ROUTERS" >&2; exit 0; }

# (1) routers/<mod>.py 모듈 참조 → 파일 실재
while IFS= read -r m; do
  [ -z "$m" ] && continue
  [ -f "$SRC/$m" ] || note "module: $m (문서 참조, 파일 부재)"
done < <(grep -rhoE 'routers/[a-z_][a-z0-9_]*\.py' "${DOCS[@]}" 2>/dev/null | sort -u)

# (2) <file>.py:<line> <symbol> 앵커 → file 실재 + def <symbol>
while IFS= read -r anchor; do
  [ -z "$anchor" ] && continue
  afile="${anchor%%:*}"        # e.g. conversations.py
  sym="${anchor##* }"          # e.g. use_conversation
  fpath=""
  [ -f "$ROUTERS/$afile" ] && fpath="$ROUTERS/$afile"
  [ -z "$fpath" ] && [ -f "$SRC/$afile" ] && fpath="$SRC/$afile"
  if [ -z "$fpath" ]; then
    note "anchor-file: $afile (앵커 '$anchor', 파일 부재)"; continue
  fi
  grep -qE "def[[:space:]]+$sym\b" "$fpath" \
    || note "anchor-symbol: $sym in $afile (앵커 '$anchor', def 부재)"
done < <(grep -rhoE '[a-z_][a-z0-9_]*\.py:[0-9]+ [a-z_][a-z0-9_]*' "${DOCS[@]}" 2>/dev/null | sort -u)

# (3) DI seam 심볼 → app.py / routers/__init__.py 에 def 실재
for sym in get_conn get_current_account require_permission register_all; do
  if grep -qE "\b$sym\b" "${DOCS[@]}" 2>/dev/null; then
    grep -qhE "def[[:space:]]+$sym\b" "$APP" "$INIT" 2>/dev/null \
      || note "di-seam: $sym (문서 정본 지목, def 부재 in app.py/routers/__init__.py)"
  fi
done

if [ "$fail" -ne 0 ]; then
  printf 'codenav-lint: STALE — %d 앵커 미해결 (AGENTS.md §21.11.4 재정합 필요: 문서 앵커 수정 또는 코드 복원)\n' "${#unresolved[@]}" >&2
  printf '  - %s\n' "${unresolved[@]}" >&2
  exit 3
fi
echo "codenav-lint: OK — CODE_NAVIGATION/CODE_TASKS 앵커 전부 resolve (모듈·file:symbol·DI seam)"
exit 0
