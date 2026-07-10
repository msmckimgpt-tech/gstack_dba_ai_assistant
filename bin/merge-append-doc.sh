#!/usr/bin/env bash
# =============================================================================
# merge-append-doc.sh — append-only 문서 말미 블록 병합 custom merge driver.
# (parallel-work-structure ITEM-03, META-0024 — AGENTS.md §13.1 2026-07-11 개정 근거)
#
# git merge driver 호출 규약: %O(ancestor) %A(ours — 결과를 여기에 씀) %B(theirs) %L(marker size) %P(경로)
#   .gitattributes: unit/*/docs/MODIFY.md merge=append-doc  등 (path-scoped 한정)
#   등록: bin/setup-git-parallel.sh (clone-로컬, git config merge.append-doc.driver)
#
# 병합 규칙 (보수적 — 오병합 금지가 제1원칙):
#   - 양측(A·B)이 모두 "base(O) 내용 그대로 + 끝에 append" 형태일 때만 자동 병합:
#     suffix 들을 `## ` 시작 블록 단위로 분해해 ours→theirs 순 연접(중복 블록 dedup,
#     각 블록 종단 개행 정규화 — 헤더 접합 파괴 방지 [패널 B-2]).
#   - 그 외 전부 `git merge-file` 로 위임 — **default 3-way text merge 와 정확히 동일**:
#     겹치지 않는 변경은 깨끗이 병합되고, 진짜 충돌만 표준 marker 로 남는다 [패널 B-1 —
#     단순 exit 1 은 marker 없는 UU 로 theirs 를 은닉하고 clean-merge 케이스를 개악].
# Exit: 0 = 병합 성공 / >0 = 충돌(merge-file 규약 — marker 가 %A 에 기록됨)
# =============================================================================
set -euo pipefail

O="${1:?ancestor}"; A="${2:?ours}"; B="${3:?theirs}"; L="${4:-7}"; P="${5:-<unknown>}"

rc=0
python3 - "$O" "$A" "$B" "$P" <<'PY' || rc=$?
import re, sys

o_path, a_path, b_path, rel = sys.argv[1:5]
read = lambda p: open(p, encoding="utf-8", errors="surrogateescape").read()
base, ours, theirs = read(o_path), read(a_path), read(b_path)

FALLBACK = 2  # bash 가 git merge-file 로 위임

def suffix_of(full, prefix):
    """full 이 'prefix 그대로 + append' 형태면 suffix 반환, 아니면 None.
    prefix 말미 개행 유무 흔들림(append 시 개행 추가)만 관대하게 허용."""
    if full == prefix:
        return ""
    for pre in (prefix, prefix.rstrip("\n") + "\n", prefix.rstrip("\n")):
        if full.startswith(pre):
            return full[len(pre):]
    return None

def blocks(s):
    """suffix 를 '## ' 시작 라인 기준 블록으로 분해(각 블록 종단 개행 정규화).
    '## ' 없는 비공백 잡텍스트가 있으면 병합 불가(None) — merge-file 위임."""
    if not s.strip():
        return []
    out, cur = [], []
    for ln in s.splitlines(keepends=True):
        if ln.startswith("## "):
            if cur:
                out.append("".join(cur))
            cur = [ln]
        else:
            if not cur:
                if ln.strip():
                    return None
                continue  # 블록 앞 공백 라인
            cur.append(ln)
    if cur:
        out.append("".join(cur))
    # 종단 개행 정규화 — 무개행 블록이 다음 블록 헤더와 접합되는 corruption 방지 (패널 B-2)
    return [b if b.endswith("\n") else b + "\n" for b in out]

sa = suffix_of(ours, base)
sb = suffix_of(theirs, base)
if sa is None or sb is None:
    print(f"[merge-append-doc] {rel}: 말미-append 아님(본문 변경 감지) → git merge-file 위임", file=sys.stderr)
    sys.exit(FALLBACK)

ba, bb = blocks(sa), blocks(sb)
if ba is None or bb is None:
    print(f"[merge-append-doc] {rel}: suffix 가 '## ' 블록 규약 밖 → git merge-file 위임", file=sys.stderr)
    sys.exit(FALLBACK)

# ours 블록 순서 보존 → theirs 신규 블록 뒤에 연접(dedup). timestamp 재정렬은 하지 않는다
# (무 timestamp 블록 재배열·dashed-date 헤더 미매칭 리스크가 정렬 가치보다 큼 — 패널 m-1).
merged_blocks = list(ba)
seen = set(ba)
for b in bb:
    if b not in seen:
        merged_blocks.append(b)
        seen.add(b)

stem = base if base.endswith("\n") or not base else base + "\n"
result = stem + "".join(merged_blocks)
open(a_path, "w", encoding="utf-8", errors="surrogateescape").write(result)
print(f"[merge-append-doc] {rel}: 말미 블록 병존 병합 완료 (ours {len(ba)} + theirs 신규 {len(merged_blocks)-len(ba)})", file=sys.stderr)
sys.exit(0)
PY

if [ "$rc" -eq 0 ]; then
  exit 0
fi
if [ "$rc" -ne 2 ]; then
  printf '[merge-append-doc] %s: driver 내부 오류(rc=%s) — 안전하게 git merge-file 위임\n' "$P" "$rc" >&2
fi
# default text merge 와 동일 동작: 겹치지 않으면 clean, 겹치면 표준 marker (%A 에 기록)
exec git merge-file --marker-size="$L" -L ours -L base -L theirs "$A" "$O" "$B"
