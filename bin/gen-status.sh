#!/usr/bin/env bash
# =============================================================================
# gen-status.sh — docs/STATUS.md 기능현황표 자동 생성 (parallel-work-structure ITEM-08).
#
# 문제(F-004): STATUS.md 가 30일 109회 변경 — 모든 feature 가 같은 표의 행을 편집하는
# 공유 착지점. 사람이 고치는 파일을 기계가 만드는 파일로 바꾸면 충돌 대상에서 제외된다.
#
# source of truth: `unit/<feature>/docs/TASK.md` frontmatter 의 진행 상태 키(선택):
#   feature_status:      planned|in-progress|blocked|review|done|deprecated
#   feature_status_date: YYYY-MM-DD (최종 갱신)
#   feature_status_note: 한 줄 요지
# (기존 `status:` 키는 문서 lifecycle(active 등)로 이미 점유 — 충돌 회피를 위해
#  feature_* prefix 를 규약으로 한다. ROADMAP ITEM-08 명세의 `status:·phase:` 취지 동일.)
#
# 동작: STATUS.md 의 <!-- AI-EDITABLE:STATUS-TABLE:START/END --> 마커 구간 안의 표를
# 재생성한다. frontmatter 키가 있는 feature 행만 frontmatter 로 대체하고, 없는 feature
# 행은 기존 행 그대로 보존(passthrough — 점진 도입, 일괄 강제 없음). 구간 밖 본문 불변.
# 연속 실행 idempotent(diff 0).
#
# 사용: bin/gen-status.sh [--check]
#   --check : 변경이 필요한지만 판정(exit 0=최신, 1=재생성 필요) — doc_sync/CI 용
# Exit: 0 성공(또는 --check 최신) / 1 --check 재생성 필요 / 2 오류
# =============================================================================
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODE="write"
[ "${1:-}" = "--check" ] && MODE="check"

python3 - "$MODE" <<'PY'
import os, re, sys

mode = sys.argv[1]
STATUS = "docs/STATUS.md"
START = "<!-- AI-EDITABLE:STATUS-TABLE:START -->"
END = "<!-- AI-EDITABLE:STATUS-TABLE:END -->"
NOTICE = "<!-- 이 표는 bin/gen-status.sh 생성물 — 수기 편집 금지. 상태 정본 = unit/<feature>/docs/TASK.md frontmatter(feature_status*) -->"

src = open(STATUS, encoding="utf-8").read()
if START not in src or END not in src:
    print(f"[gen-status] ERROR: {STATUS} 에 마커 구간 없음 ({START})", file=sys.stderr)
    sys.exit(2)

head, rest = src.split(START, 1)
block, tail = rest.split(END, 1)

# 기존 표 파싱: | feature-id | ... | 행 수집 (헤더/구분선 제외)
rows = {}          # fid -> 원본 행
order = []         # 표 등장 순서
header_lines = []
for line in block.strip().splitlines():
    s = line.strip()
    if not s.startswith("|"):
        continue
    cells = [c.strip() for c in s.strip("|").split("|")]
    if not cells or cells[0] in ("기능 ID", "---", ""):
        header_lines.append(s)
        continue
    fid = cells[0]
    rows[fid] = s
    order.append(fid)

# frontmatter 수집
def frontmatter(path):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for ln in m.group(1).splitlines():
        km = re.match(r"^(feature_status|feature_status_date|feature_status_note):\s*(.+?)\s*$", ln)
        if km:
            out[km.group(1)] = km.group(2).strip("'\"")
    return out

VALID = {"planned", "in-progress", "blocked", "review", "done", "deprecated"}
gen, kept, added = 0, 0, 0
units = sorted(
    d for d in os.listdir("unit")
    if d.startswith("feature-") and os.path.isfile(os.path.join("unit", d, "docs", "TASK.md"))
)
for fid in units:
    fm = frontmatter(os.path.join("unit", fid, "docs", "TASK.md"))
    st = fm.get("feature_status")
    if not st:
        if fid in rows:
            kept += 1
        continue  # passthrough — frontmatter 없는 feature 는 기존 행 유지(또는 표 밖 유지)
    if st not in VALID:
        print(f"[gen-status] ERROR: {fid} feature_status={st!r} 는 유효값 아님 {sorted(VALID)}", file=sys.stderr)
        sys.exit(2)
    date = fm.get("feature_status_date", "")
    note = fm.get("feature_status_note", "").replace("|", "\\|")
    row = f"| {fid} | {st} | {date} | [TASK](../unit/{fid}/docs/TASK.md) | {note} |"
    if fid in rows:
        rows[fid] = row
    else:
        rows[fid] = row
        order.append(fid)
        added += 1
    gen += 1

new_block = "\n".join(
    [
        "",
        NOTICE,
        "",
        "| 기능 ID | 상태 | 최종 갱신 | 정본(상세) | 최근 작업 요지 |",
        "|---|---|---|---|---|",
    ]
    + [rows[f] for f in order]
    + [""]
)
out = head + START + new_block + END + tail

if out == src:
    print(f"[gen-status] 최신 상태 (frontmatter {gen} · passthrough {kept} · 신규 {added}) — 변경 없음")
    sys.exit(0)
if mode == "check":
    print(f"[gen-status] 재생성 필요 (frontmatter {gen} · passthrough {kept} · 신규 {added})")
    sys.exit(1)
open(STATUS, "w", encoding="utf-8").write(out)
print(f"[gen-status] 재생성 완료 — frontmatter {gen}행 · passthrough {kept}행 · 신규 {added}행 (마커 구간 밖 불변)")
PY
