#!/usr/bin/env python3
# verify_db_rule_logic.py
# TASK-20260618T044318 (REQ-20260618-0321): DB allowlist 정규식 규칙 자동 동기화의 보안 핵심
#   순수 로직을 app.py import 없이(=DB/FastAPI 부팅 없이) 격리 검증한다.
#   대상: _validate_db_rule_pattern(B2 ReDoS/검증) · _db_rule_excluded_lower(M2 제외셋) ·
#         _match_db_rule(B5 엔진별 case-folding · M1 exclude 우선 · 인젝션/시스템 제외).
#   reconcile/엔드포인트/백그라운드(DB·네트워크 의존)는 라이브 + PB-0008 + outside-voice 재리뷰로 검증.
#
# 실행: python3 verify_db_rule_logic.py
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, "..", "src")

# ── ITEM-10 p13/p15: db_rule 순수 로직은 routers/admin_products.py 로 이동 —
#    AST 로 상수(app.py)+대상 함수(다중 파일)를 추출해 격리 exec (전체 import 회피). ──
_TARGETS = ("_validate_db_rule_pattern", "_db_rule_excluded_lower", "_match_db_rule")
_CONST_PREFIXES = ("_DB_RULE_",)  # app.py 잔류 상수 (_DB_RULE_PATTERN_MAX·_DB_RULE_BACKREF_RE 등)

wanted: dict = {}
consts: list = []
for path in (os.path.join(SRC_DIR, "app.py"), os.path.join(SRC_DIR, "routers", "admin_products.py")):
    file_src = open(path, encoding="utf-8").read()
    tree = ast.parse(file_src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in _TARGETS:
            wanted.setdefault(node.name, ast.get_source_segment(file_src, node))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            tgt = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(tgt, ast.Name) and tgt.id.startswith(_CONST_PREFIXES):
                consts.append(ast.get_source_segment(file_src, node))
missing = [n for n in _TARGETS if n not in wanted]
if missing:
    raise AssertionError(f"src 에서 db_rule 대상을 찾지 못함: {missing}")

block = "\n\n".join(consts + [wanted[n] for n in _TARGETS])


class _AppProxy:
    """이동된 함수의 `app.X` 동적 참조를 검증 ns 로 위임하는 최소 shim."""

    def __init__(self, ns):
        self._ns = ns

    def __getattr__(self, name):
        try:
            return self._ns[name]
        except KeyError:
            raise AttributeError(name) from None


# 순수 함수가 참조하는 모듈 상수 주입(실제 app.py 정의값과 동일).
ns = {
    "re": re,
    "MEMORY_DB": "agent_memory",
    "_DATABASES_AVAILABLE_METADATA": ("information_schema", "mysql", "sys", "performance_schema"),
    "_DATABASES_AVAILABLE_INTERNAL": ("agent_memory",),
    "_DATABASES_AVAILABLE_SYSTEM_MSSQL": ("master", "model", "msdb", "tempdb"),
}
ns["app"] = _AppProxy(ns)
exec(compile(block, "app_db_rule_block", "exec"), ns)
validate = ns["_validate_db_rule_pattern"]
excluded = ns["_db_rule_excluded_lower"]
match = ns["_match_db_rule"]

passed = 0
failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")


# ── 1. 패턴 검증(B2) ──
ok("validate: 정상 패턴 ok", validate("^prod_")[0] is True)
ok("validate: 빈 패턴 거부", validate("")[0] is False)
ok("validate: 과길이 거부", validate("a" * 201)[0] is False)
ok("validate: backreference 거부", validate(r"(a)\1")[0] is False)
ok("validate: 중첩수량자(ReDoS) 거부", validate("(a+)+")[0] is False and validate("(ab*)*")[0] is False)
# BLOCKER1(재리뷰): alternation/그룹 수량자 catastrophic backtracking 차단.
ok("validate: alternation 그룹수량자 (a|a)* 거부", validate("(a|a)*")[0] is False)
ok("validate: alternation 그룹수량자 (a|a)+ 거부", validate("(a|a)+")[0] is False)
ok("validate: counted 그룹반복 (.*a){20} 거부", validate("(.*a){20}")[0] is False)
ok("validate: 그룹뒤 수량자 )? 거부", validate("(ab)?c*d*")[0] is False)
ok("validate: 무한수량자 과다(>8) 거부", validate(".*.*.*.*.*.*.*.*.*x")[0] is False)
ok("validate: 정상 char-class 수량자는 허용", validate("^[a-z0-9_]+$")[0] is True and validate("^prod_|_live$")[0] is True)
ok("validate: 잘못된 정규식 거부", validate("[")[0] is False)
# match 가 안전하지 않은 저장 패턴(우회분)도 방어 심층으로 무효화.
ok("match: 안전하지 않은 include 는 [] (방어심층)",
   match(["aaaaaaaaaaaaaaaaaaaa!"], "(a|a)*", None, "mysql", excluded("mysql")) == [])

# ── 2. 제외셋(M2) ──
em = excluded("mysql")
ok("excluded mysql: 메타+내부+memory", {"information_schema", "mysql", "sys", "performance_schema", "agent_memory"} <= em)
es = excluded("mssql")
ok("excluded mssql: 시스템DB+내부", {"master", "model", "msdb", "tempdb", "agent_memory"} <= es)
ok("excluded mssql: mysql 메타 미포함(엔진 격리)", "information_schema" not in es)

# ── 3. 매칭(B5 case-folding · M1 exclude 우선 · 시스템/인젝션 제외) ──
mysql_names = ["prod_orders", "prod_log", "staging_main", "mysql", "agent_memory", "information_schema"]
exm = excluded("mysql")
ok("match mysql: '^prod_' → 2건(시스템/내부 제외)",
   match(mysql_names, "^prod_", None, "mysql", exm) == ["prod_orders", "prod_log"])
ok("match mysql: exclude '_log$' 우선",
   match(mysql_names, "^prod_", "_log$", "mysql", exm) == ["prod_orders"])
ok("match mysql: IGNORECASE(이름 소문자, 대문자 패턴도 일치)",
   match(["prod_a"], "^PROD_", None, "mysql", exm) == ["prod_a"])
ok("match mysql: 시스템/내부는 패턴 일치해도 제외",
   match(["mysql", "agent_memory"], ".*", None, "mysql", exm) == [])

# MSSQL 대소문자 구분(B5): 'salesdb' 패턴이 'SalesDB' 를 GRANT 하지 않아야(over-grant 방지).
exs = excluded("mssql")
ok("match mssql: 대소문자 구분 — 'salesdb' 는 'salesdb' 만(‘SalesDB’ 제외)",
   match(["SalesDB", "salesdb"], "salesdb", None, "mssql", exs) == ["salesdb"])
ok("match mssql: 대문자 패턴은 대문자 DB만",
   match(["SalesDB", "salesdb"], "SalesDB", None, "mssql", exs) == ["SalesDB"])

# 인젝션 위험 이름 제외 + 잘못된 exclude → 전체 무효(over-grant 방지).
ok("match: 인젝션 이름(세미콜론/대괄호) 제외",
   match(["good_db", "we;ird", "ev[il]"], ".*", None, "mysql", exm) == ["good_db"])
ok("match: 잘못된 exclude 패턴 → 전체 [] (over-grant 금지)",
   match(["prod_a"], "^prod_", "[", "mysql", exm) == [])
ok("match: 빈/None include 안전",
   match(["a"], "", None, "mysql", exm) == [] and match([], "^x", None, "mysql", exm) == [])

# ── 4. audit action 등록(PB-0008 적발 회귀 가드): build_audit_change_json 이 5종 action 을
#       'unknown audit action' raise 이전에 처리해야 _audit_admin_mutation 경로(db_rule.set 등)가 깨지지 않는다.
# ITEM-10 p7: build_audit_change_json 은 routers/_audit_infra.py 로 이동.
_audit_src = open(os.path.join(SRC_DIR, "routers", "_audit_infra.py"), encoding="utf-8").read()
_bi = _audit_src.index("def build_audit_change_json(")
_bj = _audit_src.index('raise ValueError(f"unknown audit action')
_bbody = _audit_src[_bi:_bj]
for _act in ("admin.product.db_rule.set", "admin.product.db_rule.delete",
             "admin.product.db_rule.approve", "admin.product.db.autoadd", "admin.product.db.staged"):
    ok(f"audit: '{_act}' build_audit_change_json 등록", _act in _bbody)

print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
