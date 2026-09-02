#!/usr/bin/env python3
"""브리지 러너 배포본 빌드 — `agent/` 패키지를 단일 파일 `bridge_agent.py` 로 연접한다.

## 왜 빌드 단계인가 (AGENTS.md §13.1 v3.35.1 «1순위»)

러너는 **사용자 머신이 파일 하나를 내려받아 그대로 실행**하는 산출물이다(무설치 계약,
`unit/feature-0043-external-llm-bridge/docs/ANCHOR.md` §1·§3). 그래서 소스를 관심사별로
쪼개도 배포되는 실물은 여전히 단일 파일이어야 한다 — 이 스크립트가 그 간극을 메운다.

동시에 이것은 **병렬 작업 충돌 표면의 제거**이기도 하다. 종전 배치는 정본
(`feature-0043/src/bridge_agent.py`)과 배포본(`feature-0003/src/static/agent/bridge_agent.py`)
이 **바이트 동일한 두 커밋 대상**이었고, 최근 90일 49개 커밋이 **예외 없이 둘 다** 고쳤다
(49/49). 관심사가 서로 다른 두 세션도 264KB 짜리 같은 파일에서 반드시 만났다. 생성물을
소스에 커밋하지 않고 빌드가 만들게 하면 그 표면이 통째로 사라진다 — `inject_asset_stamp.py`
가 `?v=` 스탬프에 대해 이미 같은 처방을 적용한 선례를 그대로 따른다.

## 무엇을 하는가

`agent/__init__.py` 의 `_EMIT_ORDER` 순서대로 각 모듈 본문을 잇는다. 모듈마다 제거하는 것은
**세 가지뿐**이다:

  1. 모듈 docstring — 소스 조각의 설명이지 러너의 설명이 아니다. 러너의 docstring 은
     `__init__.py` 의 것을 쓴다(단일 정본).
  2. `from __future__ import ...` — 번들 머리에 한 번만 둔다.
  3. 패키지 내부 import (`from .x import y`) — 연접 후에는 같은 네임스페이스라 불필요하다.
     남겨 두면 실행 시 `ImportError` 로 러너가 즉사한다.

stdlib import 는 **제거하지 않고 머리로 올린다**(합집합·중복 제거). 본문은 원본 텍스트를
그대로 옮긴다 — 이 코드베이스의 주석은 load-bearing 이라 `ast.unparse` 재생성을 쓰지 않는다.

## 계약

- **결정적**: 같은 입력 → 같은 바이트. 재실행해도 값이 흔들리지 않는다(멱등).
- **누락 불가**: 패키지의 `.py` 파일 집합과 `_EMIT_ORDER` 가 어긋나면 실패한다. 모듈을
  추가하고 목록에 넣지 않으면 그 코드가 배포본에서 조용히 사라지는데, 그 침묵이 가장 비싸다.
- **`--check`**: 빌드하지 않고 기존 산출물과 대조만 한다(배포 게이트·테스트용, exit 1 = 불일치).

Usage:
  python3 build_bridge_agent.py --src <agent 패키지 경로> --out <bridge_agent.py>
  python3 build_bridge_agent.py --src <...> --out <...> --check
Exit: 0 성공(또는 --check 일치) · 1 --check 불일치 · 2 usage/구조 오류
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys

BANNER_W = 78


def _emit_order(init_src: str) -> tuple[str, ...]:
    """`__init__.py` 에서 `_EMIT_ORDER` 만 꺼낸다 (패키지를 import 하지 않는다).

    import 하면 모듈 수준 코드가 실행된다 — 빌드가 대상 코드의 부작용에 의존하면 안 된다.
    """
    tree = ast.parse(init_src)
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(t, ast.Name) and t.id == "_EMIT_ORDER" for t in targets):
            return tuple(ast.literal_eval(node.value))
    raise SystemExit("build_bridge_agent: __init__.py 에 _EMIT_ORDER 가 없다")


def _strip(src: str) -> tuple[str, list[str]]:
    """모듈 본문에서 docstring·`__future__`·패키지 내부 import 를 뺀다.

    반환: `(본문, 호이스팅할 stdlib import 문 목록)`.

    행 삭제로 처리하는 이유: AST 재생성은 주석을 통째로 버린다. 이 코드베이스에서 주석은
    설명이 아니라 **결정의 근거**라 잃으면 안 된다.
    """
    tree = ast.parse(src)
    lines = src.split("\n")
    drop: set[int] = set()          # 1-based
    hoist: list[str] = []

    body = list(tree.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        drop.update(range(body[0].lineno, body[0].end_lineno + 1))
        body = body[1:]

    for node in body:
        if isinstance(node, ast.ImportFrom):
            if node.level:                        # `from .x import y` — 연접 후 불필요
                drop.update(range(node.lineno, node.end_lineno + 1))
                continue
            if node.module == "__future__":       # 번들 머리에 한 번만
                drop.update(range(node.lineno, node.end_lineno + 1))
                continue
            hoist.append(f"from {node.module} import "
                         + ", ".join(a.name for a in node.names))
            drop.update(range(node.lineno, node.end_lineno + 1))
        elif isinstance(node, ast.Import):
            hoist += [f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
                      for a in node.names]
            drop.update(range(node.lineno, node.end_lineno + 1))

    kept = [l for i, l in enumerate(lines, 1) if i not in drop]
    return "\n".join(kept).strip("\n"), hoist


def build(pkg: pathlib.Path) -> str:
    init = pkg / "__init__.py"
    if not init.is_file():
        raise SystemExit(f"build_bridge_agent: 패키지가 아니다 — {init} 부재")
    init_src = init.read_text(encoding="utf-8")
    order = _emit_order(init_src)

    on_disk = {p.stem for p in pkg.glob("*.py")} - {"__init__"}
    missing, extra = set(order) - on_disk, on_disk - set(order)
    if missing or extra:
        raise SystemExit(
            "build_bridge_agent: _EMIT_ORDER 와 패키지 파일이 어긋난다 — "
            f"목록에만 있음={sorted(missing)} 파일만 있음={sorted(extra)}\n"
            "  (목록에서 빠진 모듈은 배포본에서 조용히 사라진다. __init__.py 를 갱신하라)")

    docstring = ast.get_docstring(ast.parse(init_src), clean=False)
    if not docstring:
        raise SystemExit("build_bridge_agent: __init__.py 에 러너 docstring 이 없다")

    bodies, hoist = [], []
    for name in order:
        text, imports = _strip((pkg / f"{name}.py").read_text(encoding="utf-8"))
        hoist += imports
        if text:
            bodies.append(text)

    # stdlib import — 중복 제거 후 정렬. `import x` 를 `from x import y` 앞에 둔다(관례).
    uniq = sorted(set(hoist), key=lambda s: (s.startswith("from "), s))

    out = ["#!/usr/bin/env python3", f'"""{docstring}"""',
           "from __future__ import annotations", ""]
    out += uniq
    out.append("")                       # import 블록 뒤 빈 줄 1개
    for i, text in enumerate(bodies):
        if i:
            out += ["", ""]              # 모듈 이음매는 빈 줄 2개 (PEP8 최상위 구분)
        out.append(text)
    return "\n".join(out).rstrip("\n") + "\n"


#: `--stage-assets` 로 함께 배치하는 파일 — 러너와 **같은 곳에서 내려받는** 설치 스크립트.
#: 번들 대상이 아니라 단순 복사다(셸/PowerShell 이라 연접할 것이 없다). 그래도 여기서 함께
#: 다루는 이유는 같은 이유로 중복 커밋되고 있었기 때문이다 — 정본 1부, 배포본은 빌드 생성.
STAGED_ASSETS = ("bridge_setup.sh", "bridge_setup.ps1")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="agent 패키지 디렉터리")
    ap.add_argument("--out", required=True, help="산출물 bridge_agent.py 경로")
    ap.add_argument("--stage-assets", metavar="DIR",
                    help=f"{' · '.join(STAGED_ASSETS)} 를 DIR 에서 --out 의 디렉터리로 함께 복사")
    ap.add_argument("--check", action="store_true",
                    help="빌드하지 않고 기존 산출물과 대조만 (exit 1 = 불일치)")
    args = ap.parse_args()

    pkg = pathlib.Path(args.src)
    if not pkg.is_dir():
        print(f"build_bridge_agent: --src 부재 {pkg}", file=sys.stderr)
        return 2
    built = build(pkg)

    out = pathlib.Path(args.out)
    # (산출물 경로, 기대 내용) — 러너 + (요청 시) 설치 스크립트
    want: list[tuple[pathlib.Path, str]] = [(out, built)]
    if args.stage_assets:
        adir = pathlib.Path(args.stage_assets)
        for fn in STAGED_ASSETS:
            srcf = adir / fn
            if not srcf.is_file():
                print(f"build_bridge_agent: 자산 부재 {srcf}", file=sys.stderr)
                return 2
            dstf = out.parent / fn
            if srcf.resolve() == dstf.resolve():
                continue                      # 정본 자리 = 배포 자리 (복사 불필요)
            want.append((dstf, srcf.read_text(encoding="utf-8")))

    if args.check:
        bad = []
        for path, content in want:
            cur = path.read_text(encoding="utf-8") if path.is_file() else None
            if cur != content:
                bad.append(f"{path} ({'부재' if cur is None else '소스와 불일치'})")
        if bad:
            print("build_bridge_agent: FAIL — 재빌드 필요: " + ", ".join(bad),
                  file=sys.stderr)
            return 1
        print(f"build_bridge_agent: OK — 산출물 {len(want)}개가 소스와 일치")
        return 0

    for path, content in want:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    n_mod = len(_emit_order((pkg / "__init__.py").read_text(encoding="utf-8")))
    print(f"build_bridge_agent: {out} ({len(built.splitlines())}행) ← {n_mod} 모듈"
          + (f" · 자산 {len(want) - 1}개 배치" if len(want) > 1 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
