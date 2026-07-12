#!/usr/bin/env python3
"""gen-routemap.py — routers/*.py 정적 AST 스캔으로 LLM-navigation ROUTEMAP 자동 생성.

목적(AGENTS.md §21.11 Code-Navigation Map): AI 작업자가 "route/기능 X → 어느 router
파일:handler → 어떤 인증/권한" 을 O(1) 조회하는 정본 인덱스. routers/__init__.register_all
의 INCLUDE_ORDER 를 SSOT 로, @router 데코레이터·Depends(require_permission|get_current_account
|get_conn)·본문 _account_has_permission 을 정적 추출한다(수기 drift 차단·freshness stamp).

출력: docs/ROUTEMAP.md (정본, 고우선). 재실행 idempotent — 구조 리팩터 후 재생성.
사용: python3 bin/gen-routemap.py [--check]  (--check: 재생성 결과가 커밋본과 다르면 exit 3)
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROUTERS = os.path.join(REPO, "unit/feature-0003-agent-web-ui/src/routers")
OUT = os.path.join(REPO, "docs/ROUTEMAP.md")

_HTTP = {"get", "post", "put", "patch", "delete", "head", "options"}
_DI_AUTH = {"get_current_account", "get_optional_account", "require_permission"}


def _dep_name(call):
    """Depends(X) 또는 Depends(X(...)) 의 X 이름."""
    if not (isinstance(call, ast.Call) and _fname(call.func) == "Depends" and call.args):
        return None
    inner = call.args[0]
    if isinstance(inner, ast.Call):
        return _fname(inner.func), _first_str(inner.args)
    return _fname(inner), None


def _fname(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _first_str(args):
    for a in args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            return a.value
    return None


def _route_decorators(fn):
    """[(method, path), ...] — @router.<method>("path")."""
    out = []
    for d in fn.decorator_list:
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) \
                and isinstance(d.func.value, ast.Name) and d.func.value.id == "router" \
                and d.func.attr in _HTTP:
            path = _first_str(d.args) or (d.keywords and _first_str([kw.value for kw in d.keywords if kw.arg == "path"]))
            out.append((d.func.attr.upper(), path or "?"))
    return out


def _handler_auth(fn, src_seg):
    """핸들러의 인증/권한 표기 문자열."""
    perms = []
    di_kind = None
    for arg in fn.args.args + fn.args.kwonlyargs + fn.args.posonlyargs:
        pass
    for d in fn.args.defaults + fn.args.kw_defaults:
        if d is None:
            continue
        nm = _dep_name(d)
        if not nm:
            continue
        fname, perm = nm
        if fname == "require_permission":
            di_kind = "perm"
            if perm:
                perms.append(perm)
        elif fname == "get_current_account":
            di_kind = di_kind or "auth"
        elif fname == "get_optional_account":
            di_kind = di_kind or "optional"
    # 본문 _account_has_permission("x") — 인라인 perm gate
    import re
    body_perms = re.findall(r'_account_has_permission\([^,]+,\s*"([^"]+)"', src_seg)
    inline_auth = "_require_account(" in src_seg or "_get_authenticated_account(" in src_seg or "_optional_account(" in src_seg
    all_perms = sorted(set(perms) | set(body_perms))
    if di_kind == "perm":
        tag = "DI:require_permission"
    elif di_kind == "auth":
        tag = "DI:get_current_account"
    elif di_kind == "optional":
        tag = "DI:get_optional_account"
    elif inline_auth:
        tag = "inline-auth"
    else:
        tag = "public/none"
    return tag, all_perms


def scan():
    rows = []
    modmeta = {}
    for f in sorted(os.listdir(ROUTERS)):
        if not f.endswith(".py") or f == "__init__.py" or f.startswith("_"):
            continue
        path = os.path.join(ROUTERS, f)
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        # INCLUDE_ORDER + 헤더 docstring 첫 줄
        include_order = None
        for n in tree.body:
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "INCLUDE_ORDER" for t in n.targets):
                if isinstance(n.value, ast.Constant):
                    include_order = n.value.value
        doc = ast.get_docstring(tree) or ""
        modmeta[f] = {"include_order": include_order if include_order is not None else 10000,
                      "purpose": doc.strip().splitlines()[0].strip() if doc.strip() else ""}
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decs = _route_decorators(n)
                if not decs:
                    continue
                seg = ast.get_source_segment(src, n) or ""
                tag, perms = _handler_auth(n, seg)
                for method, rpath in decs:
                    rows.append({"file": f, "handler": n.name, "method": method, "path": rpath,
                                 "auth": tag, "perms": perms, "include_order": modmeta[f]["include_order"]})
    return rows, modmeta


def head_commit():
    try:
        return subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def render(rows, modmeta):
    rows_sorted = sorted(rows, key=lambda r: (r["include_order"], r["file"], r["path"], r["method"]))
    by_mod = {}
    for r in rows_sorted:
        by_mod.setdefault(r["file"], []).append(r)
    L = []
    # frontmatter — DOC_REGISTRY ai_read_priority 등재의 정본(§21.11.3·§21.11.7). 고정 리터럴이라
    # --check 비교에서 source_commit 처럼 normalize 할 필요 없음(휘발성 아님).
    L.append("---")
    L.append("doc_type: ROUTEMAP")
    L.append("source_of_truth: true")
    L.append("lifecycle: active")
    L.append("edit_policy: generated")
    L.append("ai_read_priority: 4")
    L.append("---")
    L.append("# ROUTEMAP — route → router:handler → auth 인덱스 (자동 생성)")
    L.append("")
    L.append(f"<!-- GENERATED by bin/gen-routemap.py — DO NOT EDIT BY HAND. source_commit: {head_commit()} · routes: {len(rows_sorted)} · modules: {len(by_mod)} -->")
    L.append("> **정본(SSOT)**: `routers/__init__.register_all` INCLUDE_ORDER + `@router` 데코레이터 정적 스캔. 재생성: `python3 bin/gen-routemap.py`. drift 검사: `--check`.")
    L.append("> **AI 탐색(L0 INDEX)**: 바꾸려는 route/기능의 method+path 를 여기서 찾아 → **router 파일:handler** 로 직행. auth 열이 권한 게이트를 선고지. 재귀 탐색은 [CODE_NAVIGATION.md](CODE_NAVIGATION.md) L1~L3.")
    L.append("")
    L.append("## 도메인 라우터 색인 (INCLUDE_ORDER 순)")
    L.append("")
    L.append("| INCLUDE_ORDER | router 파일 | route 수 | 담당 도메인 |")
    L.append("|---:|---|---:|---|")
    for f in sorted(by_mod, key=lambda x: modmeta[x]["include_order"]):
        L.append(f"| {modmeta[f]['include_order']} | [`routers/{f}`](../unit/feature-0003-agent-web-ui/src/routers/{f}) | {len(by_mod[f])} | {modmeta[f]['purpose']} |")
    L.append("")
    L.append("## 전체 route → handler → auth")
    L.append("")
    for f in sorted(by_mod, key=lambda x: modmeta[x]["include_order"]):
        L.append(f"### `routers/{f}`  (INCLUDE_ORDER={modmeta[f]['include_order']})")
        if modmeta[f]["purpose"]:
            L.append(f"_{modmeta[f]['purpose']}_")
        L.append("")
        L.append("| method | path | handler | auth | 권한(RBAC) |")
        L.append("|---|---|---|---|---|")
        for r in sorted(by_mod[f], key=lambda x: (x["path"], x["method"])):
            perms = "·".join(r["perms"]) if r["perms"] else "—"
            L.append(f"| {r['method']} | `{r['path']}` | `{r['handler']}` | {r['auth']} | {perms} |")
        L.append("")
    return "\n".join(L) + "\n"


def main():
    rows, modmeta = scan()
    out = render(rows, modmeta)
    if "--check" in sys.argv:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        # source_commit 라인은 비교 제외(휘발성)
        import re
        norm = lambda s: re.sub(r"source_commit: \w+", "source_commit: X", s)
        if norm(cur) != norm(out):
            print("ROUTEMAP.md STALE — run: python3 bin/gen-routemap.py", file=sys.stderr)
            sys.exit(3)
        print(f"ROUTEMAP.md up-to-date ({len(rows)} routes)")
        return
    open(OUT, "w", encoding="utf-8").write(out)
    print(f"ROUTEMAP.md 생성: {len(rows)} routes, {len(modmeta)} modules → {OUT}")


if __name__ == "__main__":
    main()
