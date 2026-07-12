#!/usr/bin/env python3
"""ITEM-09 what#3 (AGENTS.md §13.1 v3.35.1 1순위): 빌드 시 정적 자산 ?v= 스탬프 자동 주입.

배경 — hand-edit ?v= 스탬프는 병렬 브랜치 충돌 자석이었다(admin.html 을 만진 최근 200커밋 중
193개가 스탬프 라인 편집, 머지 충돌 30건 실측). 소스는 고정 placeholder(`?v=dev`)를 유지하고,
이미지 빌드가 본 스크립트로 스탬프를 주입해 충돌 표면 자체를 제거한다.

스탬프 값 = static 트리 전체의 content-hash(sorted (상대경로, 내용) sha256 12자).
- git SHA 가 아닌 content-hash 인 이유: backend-only 배포는 자산 캐시를 불필요하게 안 깨고,
  자산이 하나라도 바뀌면 전 참조가 일괄 갱신된다(§13.1 "content-hash 로 자동 생성" 문언 그대로).
- per-file hash 를 쓰지 않는 이유: ES module 순환 import(admin.js↔graph/*.js) 때문에
  참조 그래프 위상 정렬이 불가능하다. 전역 단일 스탬프는 cycle-안전 + transitive 무효화 보장.
- HTML 은 Cache-Control: no-cache 서빙(TASK-0256d)이라 재검증 시 새 스탬프 참조를 즉시 집는다.

치환 대상과 제외(스탬프 census 2026-07-12 실측 근거):
- 대상: *.html 의 href/src `?v=` 토큰 + first-party *.js 의 ES import specifier `?v=` 토큰.
  ES import 에도 스탬프를 다는 이유: HTML 이 admin.js?v=X 로 entry 를 로드하는데 하위 모듈이
  `../admin.js`(무버전)를 import 하면 브라우저가 다른 URL = **별개 모듈 인스턴스**로 이중
  인스턴스화한다(상태 분기 잠복 버그) + 모듈 서브트리에 캐시버스터가 전파되지 않는 gap.
  전 참조가 같은 ?v= 를 갖게 해 단일 인스턴스와 transitive 무효화를 동시에 보장한다.
- 제외 1: `vendor/` 디렉토리 파일 자체(미니파이 코드 내부에 우연한 '?v=' 문자열 존재 —
  cytoscape 1·g6 1·mermaid 10건 실측. 재작성하면 라이브러리 오염).
- 제외 2: HTML 의 vendor 자산 참조 pin(`vendor/g6.min.js?v=5.1.1` 등) — 라이브러리 버전
  pin 은 수동 유지(업그레이드 시 pin bump 가 관례). URL 에 'vendor/' 가 포함된 매치는 보존.

멱등 — 해시는 '?v= 토큰을 placeholder 로 정규화한 내용' 기준이라 주입 후 재실행도 동일 값.

Usage: python3 inject_asset_stamp.py --root /app/web/static [--stamp <값>] [--check]
  --stamp 생략 시 content-hash 자동 계산. --check 는 주입 없이 스탬프 값만 출력.
Exit: 0 성공 · 2 usage/대상 부재.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

STAMP_RE = re.compile(r"\?v=[A-Za-z0-9._-]+")
REWRITE_EXTS = (".html", ".js")
VENDOR_SEG = os.sep + "vendor" + os.sep
# 매치 직전 최대 120자 안에 vendor/ 경로가 보이면 라이브러리 pin — 보존.
_URL_CTX = 120


def is_vendor_path(path: str) -> bool:
    return VENDOR_SEG in path or path.replace("/", os.sep).find(VENDOR_SEG) >= 0


def iter_files(root):
    for dirpath, _dirs, files in os.walk(root):
        for f in sorted(files):
            yield os.path.join(dirpath, f)


def _rewrite(src: str, stamp: str) -> str:
    out = []
    last = 0
    for m in STAMP_RE.finditer(src):
        ctx = src[max(0, m.start() - _URL_CTX):m.start()]
        # 참조 URL 이 vendor 자산이면 pin 보존(마지막 따옴표 이후 조각만 검사).
        tail = re.split(r"[\"'()\s]", ctx)[-1]
        out.append(src[last:m.start()])
        if "vendor/" in tail:
            out.append(m.group(0))
        else:
            out.append(f"?v={stamp}")
        last = m.end()
    out.append(src[last:])
    return "".join(out)


def content_stamp(root):
    """static 트리 전체의 content-hash. 재작성 대상 파일은 ?v= 를 placeholder 로 정규화 후 해싱(멱등성)."""
    h = hashlib.sha256()
    for path in sorted(iter_files(root)):
        rel = os.path.relpath(path, root)
        h.update(rel.encode())
        with open(path, "rb") as fh:
            data = fh.read()
        if path.endswith(REWRITE_EXTS) and not is_vendor_path(path):
            try:
                data = _rewrite(data.decode("utf-8"), "dev").encode("utf-8")
            except UnicodeDecodeError:
                pass  # 바이너리 취급
        h.update(data)
    return h.hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--stamp", default=None)
    ap.add_argument("--check", action="store_true", help="주입 없이 스탬프 값만 출력")
    args = ap.parse_args()
    root = args.root
    if not os.path.isdir(root):
        print(f"inject_asset_stamp: root 부재 {root}", file=sys.stderr)
        return 2
    stamp = args.stamp or content_stamp(root)
    if args.check:
        print(stamp)
        return 0
    rewritten = 0
    for path in iter_files(root):
        if not path.endswith(REWRITE_EXTS) or is_vendor_path(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as fh:
            src = fh.read()
        out = _rewrite(src, stamp)
        if out != src:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(out)
            rewritten += 1
    print(f"inject_asset_stamp: stamp={stamp} files_rewritten={rewritten}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
