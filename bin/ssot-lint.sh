#!/usr/bin/env bash
# ssot-lint.sh — Single Source of Truth structural lint (initiative: ssot-consolidation, Phase 0)
#
# SSOT 계약(docs/DECISIONS.md ADR-0031 + docs/DOC_REGISTRY.md)을 기계적으로 강제한다.
# 적대 리뷰(2026-06-23) 확정 결함 #15/#16 의 'tracked .env*.bak* 0건' 가드 포함.
#
# 현재 = 골격(WARN-only). 구현 완료 check:
#   - secret   : tracked .env 백업/.bak-task 0건 (#15/#16, 노출 종료 게이트의 워킹트리 부분)
#   - archived : status|lifecycle: archived 문서가 docs/archive/ 밖에 있으면 위반
#   - wiki-sot : wiki/ 의 source_of_truth:true 가 allowlist(Log.md) 밖이면 거짓 SOT
# TODO(P1+): registry(도메인당 sot=true 1개) 정밀 검사 — DOC_REGISTRY 파싱 후 구현.
#
# Usage:
#   bash bin/ssot-lint.sh                 # WARN-only, exit 0
#   bash bin/ssot-lint.sh --strict        # 발견 시 exit 1
#   bash bin/ssot-lint.sh --check secret|archived|wiki-sot
#   bash bin/ssot-lint.sh --selftest      # 린트 자체 단위검증(오탐·미탐, 리뷰 #9)
#   bash bin/ssot-lint.sh --help
#
# Exit: 0 = clean(또는 WARN-only) / 1 = 발견(--strict) 또는 selftest 실패 / 2 = usage

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../AGENTS.md" ]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif git rev-parse --show-toplevel >/dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(pwd)"
fi

# tracked .env 백업 / .bak-task / *.secret.bak 패턴 (.example 은 .bak 미포함이라 자동 제외)
SECRET_BAK_RE='(^|/)\.env[^/]*\.bak|\.bak-task[0-9]|\.secret\.bak'
# wiki 안에서 source_of_truth:true 가 허용되는 정본(자체 ledger) allowlist
WIKI_SOT_ALLOW='wiki/Log.md'

STRICT=0
ONLY_CHECK=""
TOTAL=0

warn() { printf '  [WARN] %s\n' "$1"; TOTAL=$((TOTAL+1)); }
hdr()  { printf '\n== %s ==\n' "$1"; }

check_secret() {
  hdr "secret — tracked .env 백업/.bak-task (노출 자산, ADR-0031 §4)"
  local hits
  hits="$(git -C "$REPO_ROOT" ls-files 2>/dev/null | grep -iE "$SECRET_BAK_RE" || true)"
  if [ -n "$hits" ]; then
    while IFS= read -r f; do
      [ -n "$f" ] && warn "tracked secret 백업: $f  → rotation(ADR-0031/P3) 후 git rm + .gitignore 글롭"
    done <<< "$hits"
  fi
}

checkarchived() {
  hdr "archived — status|lifecycle: archived 가 docs/archive/ 밖 (ADR-0031 §3)"
  local f hd
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    case "$f" in */archive/*) continue;; esac
    hd="$(head -20 "$f" 2>/dev/null)"
    if printf '%s' "$hd" | grep -qiE '^(status|lifecycle): *archived'; then
      warn "archived 문서가 archive/ 밖: ${f#$REPO_ROOT/}  → docs/archive/ 로 이동"
    fi
  done < <(find "$REPO_ROOT" -name '*.md' -not -path '*/.git/*' -not -path '*/.template-backups/*' 2>/dev/null)
}

check_wiki_sot() {
  hdr "wiki-sot — wiki/ 의 source_of_truth:true 거짓 SOT (ADR-0031 §1)"
  local f rel
  [ -d "$REPO_ROOT/wiki" ] || { printf '  (wiki/ 없음 — skip)\n'; return; }
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    if head -15 "$f" 2>/dev/null | grep -qiE '^source_of_truth: *true'; then
      rel="${f#$REPO_ROOT/}"
      case " $WIKI_SOT_ALLOW " in *" $rel "*) continue;; esac
      warn "wiki 거짓 SOT: $rel  → source_of_truth:false + mirrors: 선언"
    fi
  done < <(find "$REPO_ROOT/wiki" -name '*.md' 2>/dev/null)
}

run_checks() {
  case "$ONLY_CHECK" in
    secret)   check_secret;;
    archived) checkarchived;;
    wiki-sot) check_wiki_sot;;
    "")       check_secret; checkarchived; check_wiki_sot;;
    *) echo "unknown --check: $ONLY_CHECK" >&2; exit 2;;
  esac
  printf '\n총 %d건 발견.\n' "$TOTAL"
  if [ "$TOTAL" -gt 0 ] && [ "$STRICT" -eq 1 ]; then exit 1; fi
  exit 0
}

selftest() {
  # 리뷰 #9: 린트 자체가 오탐·미탐 없이 도는지 fixture 로 검증.
  local fail=0
  echo "== selftest: secret 패턴 =="
  # 미탐 금지 (반드시 매치)
  for bad in ".env.bak-task0211" ".env.secret.bak-task0228" "sub/.env.prod.bak"; do
    if printf '%s\n' "$bad" | grep -qiE "$SECRET_BAK_RE"; then echo "  ok detect: $bad"; else echo "  MISS: $bad"; fail=1; fi
  done
  # 오탐 금지 (매치되면 안 됨)
  for good in ".env.example" ".env.secret.example" ".env" "docs/backup-notes.md"; do
    if printf '%s\n' "$good" | grep -qiE "$SECRET_BAK_RE"; then echo "  FALSE-POSITIVE: $good"; fail=1; else echo "  ok ignore: $good"; fi
  done
  echo "== selftest: archived 패턴 =="
  if printf 'status: archived\n' | grep -qiE '^(status|lifecycle): *archived'; then echo "  ok detect archived"; else echo "  MISS archived"; fail=1; fi
  if printf 'status: active\n' | grep -qiE '^(status|lifecycle): *archived'; then echo "  FALSE-POSITIVE active"; fail=1; else echo "  ok ignore active"; fi
  if [ "$fail" -eq 0 ]; then echo "SELFTEST PASS"; exit 0; else echo "SELFTEST FAIL"; exit 1; fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --strict) STRICT=1;;
    --check) ONLY_CHECK="${2:-}"; shift;;
    --selftest) selftest;;
    --help|-h) sed -n '2,18p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
  shift
done

echo "ssot-lint (REPO_ROOT=$REPO_ROOT) — WARN-only$([ "$STRICT" -eq 1 ] && echo ', --strict')"
run_checks
