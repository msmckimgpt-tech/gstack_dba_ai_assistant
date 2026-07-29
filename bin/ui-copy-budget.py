#!/usr/bin/env python3
"""ui-copy-budget.py — 사용자 대면 텍스트 분량 예산 검사 (AGENTS.md §16.8 D).

`bin/verify-completion.sh` check #17 가 호출한다. 단독 실행도 가능하다:

    python3 bin/ui-copy-budget.py --conf .template/ui-copy-budget.conf --staged
    python3 bin/ui-copy-budget.py --conf <conf> --files a.html b.js   # 전체 스캔

**무엇을 검사하나**: 기본은 `--staged` — 이번 cycle 의 staged diff 에서 **추가된 라인(+)** 만
스캔한다. 손대지 않은 기존 문단은 통과하므로, 게이트 도입이 누적 부채를 한 번에 강제하지
않는다(§16.8 D). 전체 스캔(`--files`)은 정리 작업에서 대상을 찾을 때 쓴다.

**왜 이 게이트가 필요한가**: 기존 검증은 전부 정확성 축이라(테스트=동작, 적대 검증=결함,
verify-completion=문서 정합) 안내 문단은 "틀린 말이 아니고 diff 도 작아" 전부 통과한다.
분량을 보는 축이 없으면 정확하지만 아무도 원치 않는 문장이 누적된다.

**conf 형식** (1규칙 1행, `#` 주석, 빈 줄 무시):

    <최대문자수><TAB><정규식>

정규식의 **캡처그룹 1**이 검사 대상 텍스트다. 길이 판정 전에 HTML 태그와 템플릿 보간
(`${…}`)을 제거하고 공백을 정규화한다 — 마크업·변수는 사용자가 읽는 글자가 아니다.

exit code: 0 = PASS(또는 conf 부재로 skip), 1 = 예산 초과 발견, 2 = usage/conf 오류.
"""
from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys

_TAG = re.compile(r"<[^>]+>")
_INTERP = re.compile(r"\$\{[^}]*\}")
_WS = re.compile(r"\s+")


def visible_len(raw: str) -> tuple[str, int]:
    """마크업·보간을 벗겨 사용자가 실제로 읽는 문자열과 그 길이를 돌려준다."""
    txt = _INTERP.sub("…", raw)
    txt = _TAG.sub("", txt)
    txt = html.unescape(txt)
    txt = _WS.sub(" ", txt).strip()
    return txt, len(txt)


def load_rules(conf_path: str) -> list[tuple[int, "re.Pattern[str]"]]:
    rules: list[tuple[int, re.Pattern[str]]] = []
    with open(conf_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "\t" not in line:
                raise ValueError(f"{conf_path}:{lineno}: TAB 구분자가 없습니다 — '<최대문자수><TAB><정규식>'")
            head, _, pattern = line.partition("\t")
            try:
                limit = int(head.strip())
            except ValueError as exc:
                raise ValueError(f"{conf_path}:{lineno}: 최대문자수가 정수가 아닙니다: {head!r}") from exc
            try:
                compiled = re.compile(pattern, re.S)
            except re.error as exc:
                raise ValueError(f"{conf_path}:{lineno}: 정규식 오류: {exc}") from exc
            if compiled.groups < 1:
                # 캡처그룹이 없으면 마크업 전체가 검사 대상이 되어 길이가 부풀고, 규칙을
                # 쓴 사람의 의도(텍스트만 재기)와 어긋난다 — conf 오타를 조용히 통과시키지 않는다.
                raise ValueError(f"{conf_path}:{lineno}: 캡처그룹 1 이 없습니다 — 검사 대상 텍스트를 (...) 로 감싸세요")
            rules.append((limit, compiled))
    return rules


class GitError(RuntimeError):
    """git diff 실패 — 검사 불능. PASS 로 흘리지 않는다(fail-open 금지, codex P1)."""


def added_lines(rev: str | None) -> list[tuple[str, str]]:
    """검사 대상 diff 의 추가 라인을 파일별로 합쳐 [(파일경로, 본문)] 으로 돌려준다.

    rev=None → staged(`--cached`), rev="HEAD" → 그 커밋(post-commit 검증). 파일별로 이어
    붙이는 이유: 한 문단이 여러 줄에 걸쳐 있으면 라인 단위 검사로는 매칭되지 않는다.
    git 이 실패하면 GitError — 인덱스·권한 오류를 "위반 없음" 으로 오인하면 게이트가
    조용히 무력화된다."""
    cmd = ["git", "diff", "--unified=0", "--no-color"]
    cmd += ["HEAD~1", "HEAD"] if rev else ["--cached"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise GitError((proc.stderr or "").strip() or f"git diff rc={proc.returncode}")
    current = "?"
    per_file: dict[str, list[str]] = {}
    for line in proc.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+++ ") or line.startswith("--- "):
            continue
        elif line.startswith("+"):
            per_file.setdefault(current, []).append(line[1:])
    return [(path, "\n".join(rows)) for path, rows in per_file.items()]


def scan(rules, chunks: list[tuple[str, str]]) -> list[tuple[str, int, int, str]]:
    """[(파일, 예산, 실제길이, 텍스트발췌)] — 예산 초과분만."""
    violations = []
    for path, blob in chunks:
        for limit, pattern in rules:
            for m in pattern.finditer(blob):
                raw = m.group(1) if m.groups() else m.group(0)
                txt, n = visible_len(raw)
                if n > limit:
                    violations.append((path, limit, n, txt[:100]))
    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description="사용자 대면 텍스트 분량 예산 검사 (AGENTS.md §16.8)")
    ap.add_argument("--conf", default=".template/ui-copy-budget.conf")
    ap.add_argument("--staged", action="store_true", help="staged diff 의 추가 라인만 검사 (기본)")
    ap.add_argument("--commit", action="store_true", help="직전 커밋(HEAD)의 추가 라인 검사 (post-commit)")
    ap.add_argument("--files", nargs="*", help="지정 파일 전체를 검사 (정리 작업용)")
    args = ap.parse_args()

    if not os.path.exists(args.conf):
        # opt-in 게이트 — conf 가 없으면 이 프로젝트는 채택하지 않은 것이다.
        print(f"ui-copy-budget: conf 없음 ({args.conf}) — skip", file=sys.stderr)
        return 0

    try:
        rules = load_rules(args.conf)
    except (OSError, ValueError) as exc:
        print(f"ui-copy-budget: conf 오류 — {exc}", file=sys.stderr)
        return 2
    if not rules:
        print(f"ui-copy-budget: conf 에 규칙이 없음 ({args.conf}) — skip", file=sys.stderr)
        return 0

    if args.files:
        chunks = []
        for p in args.files:
            try:
                with open(p, encoding="utf-8") as fh:
                    chunks.append((p, fh.read()))
            except OSError as exc:
                # 읽기 실패를 흘리면 "검사했는데 위반 없음" 과 구별되지 않는다 (codex P2).
                print(f"ui-copy-budget: 읽기 실패 {p}: {exc}", file=sys.stderr)
                return 2
        scope = f"{len(chunks)} file(s)"
    else:
        try:
            chunks = added_lines("HEAD" if args.commit else None)
        except GitError as exc:
            print(f"ui-copy-budget: git diff 실패 — {exc}", file=sys.stderr)
            return 2
        scope = f"{len(chunks)} changed file(s)"

    violations = scan(rules, chunks)
    if not violations:
        print(f"ui-copy-budget: PASS ({scope}, {len(rules)} rule(s))", file=sys.stderr)
        return 0

    print(f"ui-copy-budget: {len(violations)}건 예산 초과 (AGENTS.md §16.8)", file=sys.stderr)
    for path, limit, n, txt in violations:
        print(f"  {path}: {n}자 > 예산 {limit}자 — \"{txt}…\"", file=sys.stderr)
    print("  넣지 않는 4종: 조작법 · 다른 화면 경로 · 내부 계약 · 설계 정당화 (§16.8 A)",
          file=sys.stderr)
    print("  자문: \"이 문장이 없으면 사용자가 무엇을 못 하는가?\" 답이 '없음'이면 지운다.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
