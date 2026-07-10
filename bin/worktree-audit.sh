#!/usr/bin/env bash
# =============================================================================
# worktree-audit.sh — AGENTS.md §13.2.3-A worktree/branch 만료 판정 구현.
# (parallel-work-structure ITEM-04, META-0025 — F-006: 원격 ai/* 223·미머지 73 방치 해소)
#
# 전 로컬/원격 ai/* 브랜치·worktree 를 4분류:
#   SAFE_REMOVE    — merged 이중확인: ① tip 이 main ancestor (git branch --merged 동치)
#                    ② merged PR 의 headRefOid == tip (squash-merge 대응 — 머지 후 추가
#                      커밋이 있으면 tip 불일치 → 오삭제 방지, §13.2.3-A 원문 요건)
#   LIKELY_ABANDON — 점검 트리거(behind ≥ 50 OR last commit ≥ 7일) + BLOCKED/HOLD 무
#                    → 보고만 (폐기는 사람 확인, §13.2.3-A 맥락 판정 위임)
#   NEEDS_REVIEW   — 점검 트리거 + worktree TASK.md 에 BLOCKED/HOLD → 보고만
#   ACTIVE         — Open PR 존재(무조건) 또는 트리거 미해당
#
# 모드:
#   (기본)        dry-run 리포트 — 4분류 출력 + TODOS.md 후보 블록 + SAFE_REMOVE 를
#                 상태파일에 노출 기록(통지 후 유예 — W-009 정리봇 안전장치)
#   --apply       SAFE_REMOVE 만 실제 제거(worktree remove → branch -d → 원격 push --delete).
#                 **직전 리포트에 노출된 브랜치만** 대상(상태파일 대조) + 적용 시점 재검증.
#   --branch <b>  대상을 특정 브랜치로 한정(테스트/표적 적용)
#   --json        기계 판독용 TSV 출력(분류\t브랜치\tahead\tbehind\tage\t사유)
#
# 안전장치 (ROADMAP ITEM-04 guards):
#   - dry-run 이 기본값. 삭제는 SAFE_REMOVE + --apply 명시 + 직전 리포트 노출분만.
#   - dirty worktree 는 어떤 모드에서도 건드리지 않음(DIRTY 표기 — FOREIGN_CHANGE_ALERT 대상).
#   - Open PR 브랜치는 무조건 ACTIVE.
#   - worktree remove Permission denied(root 소유 __pycache__ 등) → sudo rm 후 재시도(F-006 quirk).
#   - 실행 중 세션 worktree 불가침: 프로세스 CWD 스캔(/proc)으로 IN-USE 감지 — clean/ahead=0
#     인 "커밋 전" 라이브 세션(doc-sync cron 등) 보호. 한계: 타 계정(root 등) 프로세스의
#     CWD 는 비가시 — 그 세션은 DIRTY 가드·commit 후 ahead>0 로만 보호됨.
#
# cron: bin/install-worktree-audit-cron.sh (평일 1회 리포트 — doc-sync cron 패턴).
# 상태파일: $(git rev-parse --git-common-dir)/worktree-audit-exposed.txt (working tree 밖).
# Exit: 0 정상 / 1 apply 중 일부 실패 / 2 usage
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log() { printf '[worktree-audit] %s\n' "$*" >&2; }
die() { printf '[worktree-audit] ERROR: %s\n' "$*" >&2; exit 2; }

MODE="report"
ONLY_BRANCH=""
OUT_TSV=0
while [ $# -gt 0 ]; do case "$1" in
  --apply)  MODE="apply"; shift ;;
  --branch) ONLY_BRANCH="${2:?--branch 인자 필요}"; shift 2 ;;
  --json|--tsv) OUT_TSV=1; shift ;;
  --help|-h) sed -n '2,38p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) die "알 수 없는 인자: $1" ;;
esac; done

GIT_COMMON="$(git rev-parse --git-common-dir)"
STATE_FILE="$GIT_COMMON/worktree-audit-exposed.txt"
MAIN_REF="origin/main"

git fetch --prune origin >/dev/null 2>&1 || log "경고: git fetch 실패 — 로컬 캐시 기준 판정"
git rev-parse --verify --quiet "$MAIN_REF" >/dev/null || die "$MAIN_REF 없음"

# ── PR 메타데이터 일괄 수집 (per-branch gh 호출 회피 — rate limit) ────────────
PR_MERGED_TSV="$(gh pr list --state merged --limit 500 --json headRefName,headRefOid,number,title \
  --jq '.[] | [.headRefName, .headRefOid, (.number|tostring), .title] | @tsv' 2>/dev/null || true)"
PR_OPEN_TSV="$(gh pr list --state open --limit 200 --json headRefName,number,title \
  --jq '.[] | [.headRefName, (.number|tostring), .title] | @tsv' 2>/dev/null || true)"
[ -z "$PR_MERGED_TSV" ] && log "경고: merged PR 목록 비어있음/조회실패 — squash 판정은 ancestry 만"

# ── worktree 맵: branch → path ────────────────────────────────────────────────
declare -A WT_PATH
current_wt_path=""
while IFS= read -r line; do
  case "$line" in
    "worktree "*) current_wt_path="${line#worktree }" ;;
    "branch refs/heads/"*) WT_PATH["${line#branch refs/heads/}"]="$current_wt_path" ;;
  esac
done < <(git worktree list --porcelain)

# ── 브랜치 집합: 로컬 + 원격 ai/* (main checkout 브랜치 제외) ─────────────────
mapfile -t LOCAL_BRANCHES < <(git for-each-ref 'refs/heads/ai/**' --format='%(refname:short)')
mapfile -t REMOTE_BRANCHES < <(git for-each-ref 'refs/remotes/origin/ai/**' --format='%(refname:short)' | sed 's|^origin/||')
declare -A SEEN LOCAL_HAS REMOTE_HAS
BRANCHES=()
for b in "${LOCAL_BRANCHES[@]:-}"; do [ -n "$b" ] || continue; LOCAL_HAS[$b]=1; [ -n "${SEEN[$b]:-}" ] || { SEEN[$b]=1; BRANCHES+=("$b"); }; done
for b in "${REMOTE_BRANCHES[@]:-}"; do [ -n "$b" ] || continue; REMOTE_HAS[$b]=1; [ -n "${SEEN[$b]:-}" ] || { SEEN[$b]=1; BRANCHES+=("$b"); }; done

[ -n "$ONLY_BRANCH" ] && BRANCHES=("$ONLY_BRANCH")

NOW_EPOCH="$(date +%s)"
declare -A CLASS REASON AHEAD BEHIND AGE_DAYS TIP DIRTY INUSE

# 실행 중 세션의 worktree 보호 (단일 호스트 전제): 어떤 프로세스든 CWD 가 해당 worktree
# 안이면 불가침 — clean/ahead=0 인 "아직 커밋 전" 라이브 세션(예: doc-sync cron 헤드리스)을
# DIRTY 가드가 못 잡는 gap 봉인. (실측: 2026-07-10 doc-sync 세션 worktree 가 SAFE_REMOVE 오분류)
PROC_CWDS="$(for p in /proc/[0-9]*/cwd; do readlink "$p" 2>/dev/null; done | sort -u || true)"
wt_in_use() {
  local wt="$1" c
  while IFS= read -r c; do
    [ -n "$c" ] || continue
    case "$c" in "$wt"|"$wt"/*) return 0 ;; esac
  done <<< "$PROC_CWDS"
  return 1
}

SAFE_LIST=() ABANDON_LIST=() REVIEW_LIST=() ACTIVE_LIST=()

for b in "${BRANCHES[@]:-}"; do
  [ -n "$b" ] || continue
  # tip: 로컬 우선, 없으면 원격
  if [ -n "${LOCAL_HAS[$b]:-}" ]; then tip="$(git rev-parse "refs/heads/$b")"
  elif [ -n "${REMOTE_HAS[$b]:-}" ]; then tip="$(git rev-parse "refs/remotes/origin/$b")"
  else log "skip: $b (ref 없음)"; continue; fi
  TIP[$b]="$tip"

  read -r behind ahead < <(git rev-list --left-right --count "$MAIN_REF...$tip" 2>/dev/null || echo "0 0")
  AHEAD[$b]="$ahead"; BEHIND[$b]="$behind"
  last_epoch="$(git log -1 --format=%ct "$tip" 2>/dev/null || echo "$NOW_EPOCH")"
  AGE_DAYS[$b]=$(( (NOW_EPOCH - last_epoch) / 86400 ))

  # dirty / in-use worktree 판정
  wt="${WT_PATH[$b]:-}"
  DIRTY[$b]=0; INUSE[$b]=0
  if [ -n "$wt" ] && [ -d "$wt" ]; then
    [ -n "$(git -C "$wt" status --porcelain 2>/dev/null | head -1)" ] && DIRTY[$b]=1
    wt_in_use "$wt" && INUSE[$b]=1
  fi

  # Open PR → 무조건 ACTIVE
  open_pr="$(printf '%s\n' "$PR_OPEN_TSV" | awk -F'\t' -v b="$b" '$1==b && !f {print $2; f=1}')"
  if [ -n "$open_pr" ]; then
    CLASS[$b]="ACTIVE"; REASON[$b]="Open PR #$open_pr"; ACTIVE_LIST+=("$b"); continue
  fi

  # SAFE_REMOVE ① ancestry (branch --merged 동치)
  if git merge-base --is-ancestor "$tip" "$MAIN_REF" 2>/dev/null; then
    CLASS[$b]="SAFE_REMOVE"; REASON[$b]="merged(ancestry, ahead=0)"
    SAFE_LIST+=("$b"); continue
  fi
  # SAFE_REMOVE ② squash-merge: merged PR headRefOid == tip (추가 커밋 있으면 불일치 → 보호)
  m_pr="$(printf '%s\n' "$PR_MERGED_TSV" | awk -F'\t' -v b="$b" -v t="$tip" '$1==b && $2==t && !f {print $3; f=1}')"
  if [ -n "$m_pr" ]; then
    CLASS[$b]="SAFE_REMOVE"; REASON[$b]="merged(PR #$m_pr squash, tip 일치)"
    SAFE_LIST+=("$b"); continue
  fi
  # squash-merge 인데 tip 불일치(머지 후 추가 커밋) — 명시 보호 사유 기록
  m_pr_stale="$(printf '%s\n' "$PR_MERGED_TSV" | awk -F'\t' -v b="$b" '$1==b && !f {print $3; f=1}')"

  # 점검 트리거: behind ≥ 50 OR last commit ≥ 7일
  if [ "${BEHIND[$b]}" -ge 50 ] || [ "${AGE_DAYS[$b]}" -ge 7 ]; then
    marker=""
    if [ -n "$wt" ] && [ -d "$wt" ]; then
      marker="$(grep -rlE 'BLOCKED|HOLD' "$wt"/unit/*/docs/TASK.md 2>/dev/null | head -1 || true)"
    fi
    extra=""
    [ -n "$m_pr_stale" ] && extra=" · merged PR #$m_pr_stale 후 추가 커밋(tip 불일치 — 오삭제 보호)"
    if [ -n "$marker" ]; then
      CLASS[$b]="NEEDS_REVIEW"; REASON[$b]="behind=${BEHIND[$b]} age=${AGE_DAYS[$b]}d BLOCKED/HOLD 마커$extra"
      REVIEW_LIST+=("$b")
    else
      CLASS[$b]="LIKELY_ABANDON"; REASON[$b]="behind=${BEHIND[$b]} age=${AGE_DAYS[$b]}d ahead=${AHEAD[$b]}$extra"
      ABANDON_LIST+=("$b")
    fi
    continue
  fi

  CLASS[$b]="ACTIVE"; REASON[$b]="트리거 미해당 (behind=${BEHIND[$b]} age=${AGE_DAYS[$b]}d)"
  ACTIVE_LIST+=("$b")
done

# ── 출력 ─────────────────────────────────────────────────────────────────────
print_group() {  # $1=제목 $2...=브랜치들
  local title="$1"; shift
  local real=() b
  for b in "$@"; do [ -n "$b" ] && real+=("$b"); done
  printf '\n== %s (%d) ==\n' "$title" "${#real[@]}"
  for b in "${real[@]:-}"; do
    [ -n "$b" ] || continue
    local wt_note=""
    [ -n "${WT_PATH[$b]:-}" ] && wt_note=" wt=${WT_PATH[$b]}"
    [ "${DIRTY[$b]:-0}" = "1" ] && wt_note="$wt_note [DIRTY — 불가침]"
    [ "${INUSE[$b]:-0}" = "1" ] && wt_note="$wt_note [IN-USE — 실행 중 세션, 불가침]"
    printf '  %-58s %s%s\n' "$b" "${REASON[$b]}" "$wt_note"
  done
}

if [ "$OUT_TSV" = "1" ]; then
  for b in "${BRANCHES[@]:-}"; do
    [ -n "${CLASS[$b]:-}" ] || continue
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "${CLASS[$b]}" "$b" "${AHEAD[$b]}" "${BEHIND[$b]}" "${AGE_DAYS[$b]}" "${REASON[$b]}"
  done
  exit 0
fi

log "브랜치 ${#BRANCHES[@]}개 감사 (로컬 ${#LOCAL_BRANCHES[@]} · 원격 ${#REMOTE_BRANCHES[@]}) — main=$(git rev-parse --short "$MAIN_REF")"
print_group "SAFE_REMOVE — merged 이중확인, --apply 시 제거" "${SAFE_LIST[@]:-}"
print_group "LIKELY_ABANDON — 보고만 (폐기는 사람 확인)" "${ABANDON_LIST[@]:-}"
print_group "NEEDS_REVIEW — 보고만 (BLOCKED/HOLD — TASK/PR 검토 필요)" "${REVIEW_LIST[@]:-}"
print_group "ACTIVE — 유지" "${ACTIVE_LIST[@]:-}"

# TODOS.md 후보 블록 (LIKELY_ABANDON/NEEDS_REVIEW 만 — 사람 확인 대기열)
if [ "${#ABANDON_LIST[@]}" -gt 0 ] || [ "${#REVIEW_LIST[@]}" -gt 0 ]; then
  printf '\n-- TODOS.md 후보 블록 (붙여넣기용) --\n'
  printf '## worktree-audit %s — 사람 확인 대기\n' "$(date +%Y-%m-%d)"
  for b in "${ABANDON_LIST[@]:-}" "${REVIEW_LIST[@]:-}"; do
    [ -n "$b" ] || continue
    last_pr="$(printf '%s\n' "$PR_MERGED_TSV" | awk -F'\t' -v b="$b" '$1==b && !f {print "PR #"$3" "$4; f=1}')"
    printf -- '- [ ] `%s` — %s: %s%s\n' "$b" "${CLASS[$b]}" "${REASON[$b]}" "${last_pr:+ · 최근 $last_pr}"
  done
fi

if [ "$MODE" = "report" ]; then
  # 통지 후 유예: SAFE_REMOVE 노출 기록 → 다음 --apply 가 이 목록만 대상
  : > "$STATE_FILE"
  for b in "${SAFE_LIST[@]:-}"; do [ -n "$b" ] && printf '%s\n' "$b" >> "$STATE_FILE"; done
  log ""
  log "리포트 완료 (dry-run). SAFE_REMOVE ${#SAFE_LIST[@]}건을 상태파일에 노출 기록: $STATE_FILE"
  log "제거하려면: bin/worktree-audit.sh --apply  (직전 리포트 노출분만 제거)"
  exit 0
fi

# ── --apply: SAFE_REMOVE 만, 직전 리포트 노출분만, 적용 시점 재검증 ───────────
[ -f "$STATE_FILE" ] || die "--apply 전에 리포트 1회 필요 (상태파일 없음: $STATE_FILE)"
declare -A EXPOSED
while IFS= read -r b; do [ -n "$b" ] && EXPOSED[$b]=1; done < "$STATE_FILE"

fail=0 removed=0
for b in "${SAFE_LIST[@]:-}"; do
  [ -n "$b" ] || continue
  if [ -z "${EXPOSED[$b]:-}" ]; then
    log "skip(유예): $b — 직전 리포트에 미노출 (다음 리포트 후 제거 가능)"
    continue
  fi
  if [ "${DIRTY[$b]:-0}" = "1" ]; then
    log "skip(DIRTY): $b — dirty worktree 불가침 (FOREIGN_CHANGE_ALERT 대상)"
    continue
  fi
  if [ "${INUSE[$b]:-0}" = "1" ]; then
    log "skip(IN-USE): $b — 실행 중 세션의 worktree (프로세스 CWD 감지) 불가침"
    continue
  fi
  log "제거: $b (${REASON[$b]})"
  wt="${WT_PATH[$b]:-}"
  if [ -n "$wt" ] && [ -d "$wt" ]; then
    if ! git worktree remove "$wt" 2>/dev/null; then
      log "  worktree remove 실패 — root 소유 잔여물 sudo 정리 후 재시도 (F-006 quirk)"
      sudo find "$wt" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
      sudo find "$wt" \( -user root -o ! -writable \) -exec rm -rf {} + 2>/dev/null || true
      if ! git worktree remove --force "$wt" 2>/dev/null; then
        log "  ✗ worktree remove 재시도 실패: $wt — 수동 확인 필요"; fail=1; continue
      fi
    fi
  fi
  if [ -n "${LOCAL_HAS[$b]:-}" ]; then
    git branch -D "$b" >/dev/null 2>&1 || { log "  ✗ 로컬 브랜치 삭제 실패: $b"; fail=1; }
  fi
  if [ -n "${REMOTE_HAS[$b]:-}" ]; then
    git push origin --delete "$b" >/dev/null 2>&1 || { log "  ✗ 원격 브랜치 삭제 실패: $b"; fail=1; }
  fi
  removed=$((removed+1))
done
git worktree prune 2>/dev/null || true
log ""
log "apply 완료: 제거 ${removed}건 (SAFE_REMOVE 총 ${#SAFE_LIST[@]}건 중 노출분만) · 실패 $fail"
# 노출 소진 — apply 1회가 exposure 를 소비한다. 다음 apply 전에 리포트 재실행 필수
# (skip 된 DIRTY/미노출분은 다음 리포트가 다시 기록 — 통지 후 유예 불변식 유지).
: > "$STATE_FILE"
exit "$fail"
