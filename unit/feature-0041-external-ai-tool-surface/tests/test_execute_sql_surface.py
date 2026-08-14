"""feature-0041 P1 — 자유 SELECT(`execute_sql`) 노출 계약.

## 왜 P1 이었나 · 왜 지금 여는가

계획 단계에서 "행수 예산·추출 원장이 선행 조건" 이라 미뤘다. 실사용 제보가 그 값을 확정했다 —
FK 가 0건인 스키마에서는 **구조만으로 관계 주장을 검증할 수 없고**, 뷰 정의·실제 행수·고아행
확인이 전부 막혀 "뷰가 증거" 수준에서 멈춘다.

## 여기서 고정하는 것

방어는 **새로 만들지 않는다** — 내부 경로의 sqlglot AST 가드·제품 스키마 allowlist·무거운 쿼리
게이트·시간 cap 을 그대로 통과한다. 외부 표면이 추가로 지는 책임은 둘이고, 둘 다 틀리면
조용히 무너지는 종류다.

1. **서버 CSV 경로가 나가지 않는다** — 내부 경로는 결과를 파일로 저장하고 web UI 가 다운로드로
   준다. 외부 호출자에겐 그 UI 도, 파일을 읽을 방법도 없다. 경로만 새고 지키지 못할 약속이 남는다.
2. **원장에 실제 행수가 기록된다** — 렌더 문자열의 줄 수로 세면 미리보기 50행만 잡혀
   시간당 행 상한(200,000)이 사실상 걸리지 않는다. 그건 "존재하지 않는 방어" 다.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "unit", "feature-0003-agent-web-ui", "src"))
sys.path.insert(0, _REPO)

from shared import runtime_settings as rs  # noqa: E402

sys.path.insert(0, _HERE)
from _srcutil import code_only  # noqa: E402


def _read(*parts: str) -> str:
    with open(os.path.join(_REPO, *parts), encoding="utf-8") as fh:
        return fh.read()


_ROUTER = ("unit", "feature-0003-agent-web-ui", "src", "routers", "ai_tools.py")
_TOOLS = ("unit", "feature-0002-agent-core", "src", "modules", "tools.py")
_ADAPTERS = ["external_tool_mcp_server.py", "external_tool_mcp_http.py"]


def _router_fn(name: str) -> str:
    src = _read(*_ROUTER)
    body = src[src.index(f"def {name}("):]
    nxt = body.find("\n\n\n")
    return body[:nxt] if nxt > 0 else body


# ── 노출면 ────────────────────────────────────────────────────────────────────

def test_execute_sql_is_exposed_but_kept_separate_from_p0():
    """P0(구조 조회)와 한 덩어리로 묶으면 운영자가 **데이터 추출만** 끌 수 없다."""
    src = _read(*_ROUTER)
    assert 'P1_TOOLS = frozenset({"execute_sql"})' in src
    assert "EXPOSED_TOOLS = P0_TOOLS | P1_TOOLS" in src
    assert "execute_sql" not in src[src.index("P0_TOOLS = frozenset({"):
                                    src.index("# P1 (2026-08-14)")]


def test_write_tools_are_still_not_exposed():
    """★ 쓰기·첨부·scratch 계열은 영구 제외다 — allowlist 가 늘어난 김에 새는 것을 막는다."""
    src = _read(*_ROUTER)
    exposed = src[src.index("P0_TOOLS = frozenset({"):src.index("EXPOSED_TOOLS =")]
    for forbidden in ("execute_write", "run_scratch", "save_", "insert", "update_", "delete_",
                      "read_attachment", "write_"):
        assert forbidden not in exposed, f"노출 목록에 {forbidden} 가 들어갔다"


def test_sql_can_be_turned_off_by_an_operator():
    src = _read(*_ROUTER)
    assert "_SQL_ENABLED_KEY = \"AGENT_EXT_TOOL_SQL_ENABLED\"" in src
    assert "if tool_name in P1_TOOLS and not _sql_enabled():" in src
    keys = {s["key"] for s in rs.list_specs() if s.get("group") == "external_tool_surface"}
    assert "AGENT_EXT_TOOL_SQL_ENABLED" in keys, "콘솔에서 끌 수 없다"


def test_disabled_switch_returns_403_not_404():
    """404 는 '그런 도구 없음' 이라 클라이언트가 재시도·우회를 시도한다. 403 은 '있는데 막힘'."""
    body = _router_fn("run_structure_tool")
    seg = body[body.index("if tool_name in P1_TOOLS"):][:300]
    assert "403" in seg


# ── ① 서버 경로가 나가지 않는다 ──────────────────────────────────────────────

def test_router_actually_calls_the_sanitizer():
    """★ 함수만 있고 **호출하지 않으면** 아무것도 막지 않는다 — 뮤테이션이 여기서 살아남았다."""
    body = _router_fn("run_structure_tool")
    assert "_sanitize_sql_output(rendered, sql_stats.get(\"csv_paths\")" in body, \
        "라우터가 정화를 호출하지 않는다"
    # 정화 결과가 실제로 응답에 실려야 한다(정화하고 버리면 같은 결함).
    assert "rendered, account=" in body or "wrap_tool_output(\n        rendered" in body


def test_csv_paths_are_stripped_from_external_output():
    """★ 내부 렌더는 `CSV 저장: /shared/out/...` 를 붙인다 — 서버 파일 경로다."""
    src = _read(*_ROUTER)
    assert "def _sanitize_sql_output(" in src
    body = src[src.index("def _sanitize_sql_output("):src.index("# ── 인증")]
    assert 'f"CSV 저장: {path}' in body

    ns: dict = {}
    exec(compile(body, "<sanitize>", "exec"), {"str": str}, ns)
    fn = ns["_sanitize_sql_output"]
    raw = ("| id | name |\n| 1 | a |\n"
           "CSV 저장: /shared/out/20260814_resultset1_ab12cd34.csv\n"
           "(저장된 CSV 는 사용자에게 다운로드 버튼으로 자동 제공됩니다 — 당신이 다운로드 "
           "링크/URL 을 직접 만들 필요는 없습니다.)")
    out = fn(raw, ["/shared/out/20260814_resultset1_ab12cd34.csv"])
    assert "/shared/out" not in out, "서버 경로가 응답에 남는다"
    assert "다운로드 버튼" not in out, "없는 다운로드를 약속한다"
    assert "| 1 | a |" in out, "결과 자체가 지워졌다"


def test_download_only_wording_is_replaced_not_left_dangling():
    """절단 안내의 'CSV 는 사용자 다운로드 전용' 문구는 외부 호출자에게 dead-end 다."""
    src = _read(*_ROUTER)
    body = src[src.index("def _sanitize_sql_output("):src.index("# ── 인증")]
    ns: dict = {}
    exec(compile(body, "<sanitize>", "exec"), {"str": str}, ns)
    out = ns["_sanitize_sql_output"](
        "(전체 900행 — 위 표는 미리보기 50행입니다. "
        "CSV 는 사용자 다운로드 전용이라 당신은 읽을 수 없습니다.)", [])
    assert "다운로드 전용" not in out
    assert "SQL 로 좁혀" in out, "다음 행동을 알려주지 않는다"
    assert "전체 900행" in out, "절단 사실 자체는 남아야 한다(단정 금지 신호)"


# ── ② 원장에 실제 행수가 기록된다 ────────────────────────────────────────────

def test_backend_reports_real_row_count_through_a_sink():
    """★ 렌더 문자열 역파싱은 절단이 없을 때 값이 없고 문구가 바뀌면 조용히 틀린다."""
    tools = _read(*_TOOLS)
    seg = tools[tools.index('_sink = args.get("_stats_out")'):][:400]
    assert '_sink["total_rows"] = int(total_row_count)' in seg
    assert '_sink["csv_paths"] = list(csv_paths)' in seg


def test_router_records_the_real_row_count():
    body = _router_fn("run_structure_tool")
    assert 'arguments["_stats_out"] = sql_stats' in body
    assert 'int(sql_stats["total_rows"])' in body
    # 구조 도구는 종전대로 줄 수 근사 — 그쪽은 백엔드가 행수를 모른다.
    assert 'rendered.count("\\n")' in body


def test_reserved_argument_keys_cannot_come_from_the_caller():
    """★ `_stats_out` 은 내부 out-param 이다. 호출자가 심어 보내면 내부 규약과 충돌한다."""
    body = _router_fn("run_structure_tool")
    assert 'if not str(k).startswith("_")' in body, "밑줄 키를 걸러내지 않는다"

    src = _read(*_ROUTER)
    line = [l for l in src.splitlines() if 'startswith("_")' in l]
    assert line, "필터가 없다"

    # 실제로 걸러지는지 실행해서 본다.
    body_args = {"sql": "SELECT 1", "_stats_out": {"total_rows": 999999}, "datasource": "x"}
    filtered = {k: v for k, v in body_args.items() if not str(k).startswith("_")}
    assert "_stats_out" not in filtered and filtered["sql"] == "SELECT 1"


def test_hourly_row_limit_actually_sees_sql_rows():
    """상한이 원장 `rows_returned` 합으로 판정되므로, 실제 행수가 거기 들어가야 의미가 있다."""
    ledger = _read("unit", "feature-0003-agent-web-ui", "src", "tool_ledger.py")
    assert "rows_returned" in ledger and "AGENT_EXT_TOOL_ROWS_PER_HOUR" in ledger


# ── 방어 재사용 (fork 금지) ──────────────────────────────────────────────────

def test_sql_guard_is_reused_not_reimplemented():
    """★ 가드를 외부 표면에서 다시 구현하면 두 개가 갈린다 — 내부 경로 것을 그대로 통과시킨다."""
    router = code_only(_read(*_ROUTER))
    for reimpl in ("sqlglot", "validate_sql_for_sandbox", "DROP", "DELETE FROM"):
        assert reimpl not in router, f"라우터가 SQL 가드를 자체 구현한다({reimpl})"
    tools = _read(*_TOOLS)
    seg = tools[tools.index("def _tool_execute_sql("):][:3000]
    assert "validate_sql_for_sandbox(" in seg, "AST 가드를 안 통과한다"
    assert "_freeform_sql_access_error(" in seg, "제품 스키마 allowlist 를 안 통과한다"


@pytest.mark.parametrize("adapter", _ADAPTERS)
def test_adapters_expose_execute_sql_with_honest_description(adapter):
    src = _read("unit", "feature-0041-external-ai-tool-surface", "src", adapter)
    assert "def execute_sql(" in src
    # 설명 문구는 HTTP 는 데코레이터, stdio 는 `_register(...)` 에 있다 — 파일 전체에서 찾는다.
    assert "단일 SELECT/CTE" in src
    assert "거부된다" in src, "쓰기가 막힌다는 사실을 안 알린다"
    assert "상한" in src, "반환 행수가 상한에 걸린다는 사실을 안 알린다"


@pytest.mark.parametrize("adapter", _ADAPTERS)
def test_adapters_send_sql_under_the_name_the_backend_reads(adapter):
    """계약 대조 — 백엔드는 `args.get("sql")` 을 읽는다."""
    src = _read("unit", "feature-0041-external-ai-tool-surface", "src", adapter)
    seg = src[src.index("def execute_sql("):][:600]
    assert '"sql": sql' in seg
    tools = _read(*_TOOLS)
    head = tools[tools.index("def _tool_execute_sql("):][:200]
    assert 'args.get("sql"' in head


def test_guide_documents_the_new_tool_and_its_bounds():
    guide = _read("unit", "feature-0003-agent-web-ui", "src", "static", "ai-api-guide.md")
    assert "execute_sql" in guide
    # 과거 가이드는 "execute_sql 은 아직 없다" 고 적혀 있었다 — 그 문장이 남으면 안 된다.
    assert "아직 열려 있지 않" not in guide and "execute_sql 은 P1" not in guide
    for needle in ("단일 SELECT", "행수"):
        assert needle in guide, f"가이드에 '{needle}' 설명이 없다"


# ── codex 2차 리뷰 (P1×3 · P2×3) ─────────────────────────────────────────────

def test_operator_switch_actually_calls_the_real_api():
    """★ `get_int(key, default)` 는 **TypeError** 다(인자 1개). except 가 True 를 돌려주면
    스위치가 **항상 켜진 상태**가 된다 — 문자열 검사로는 안 잡힌다. 실제로 호출해 본다."""
    src = _read(*_ROUTER)
    body = src[src.index("def _sql_enabled("):src.index("def _sanitize_sql_output(")]
    assert "get_int(_SQL_ENABLED_KEY)" in body, "기본값을 넘겨 TypeError 를 만든다"
    assert "return False" in body, "설정을 못 읽는데 데이터 추출을 여는 것은 fail-open 이다"

    # 실제 API 로 호출해 본다 — 시그니처가 어긋나면 여기서 TypeError 가 난다.
    import inspect
    assert len(inspect.signature(rs.get_int).parameters) == 1, \
        "get_int 시그니처가 바뀌었다 — 호출부를 함께 고쳐라"
    assert int(rs.get_int("AGENT_EXT_TOOL_SQL_ENABLED")) == 1, "스펙 기본값이 1이 아니다"
    with pytest.raises(TypeError):
        rs.get_int("AGENT_EXT_TOOL_SQL_ENABLED", 1)   # ← 이게 예전 호출 형태였다


def test_per_query_row_cap_bounds_the_overshoot():
    """★ 시간당 상한은 **실행 전 누적 확인**이라 원자적이지 않다(상한 직전 대형 쿼리 1회,
    동시 요청이 같은 잔여를 봄). 건당 상한이 그 초과분을 유계로 만든다 — hard cap 이라
    부르지 않고 '초과분이 유계' 라고 부른다."""
    src = _read(*_ROUTER)
    assert "_SQL_MAX_ROWS_KEY" in src and "get_int(_SQL_MAX_ROWS_KEY)" in src
    body = _router_fn("run_structure_tool")
    assert "cap > 0 and got > cap" in body
    assert "status_code=413" in body, "초과를 성공으로 돌려주면 상한이 무의미하다"
    assert 'outcome="gated"' in body and "rows_returned=got" in body, \
        "부하는 발생했는데 원장에 안 남으면 다음 요청이 같은 잔여를 본다"
    keys = {s["key"] for s in rs.list_specs() if s.get("group") == "external_tool_surface"}
    assert "AGENT_EXT_TOOL_SQL_MAX_ROWS" in keys


def test_scope_yields_a_datasource_connection_not_the_memory_conn():
    """★ 단일 바인딩 제품(대부분)에서 memory DB 연결이 도구로 갔다 — 구조 조회가 내부 서버를
    향해 다른 대화의 첨부 샌드박스까지 목록에 나왔다(라이브 실측)."""
    flat = " ".join(code_only(_router_fn("run_structure_tool")).split())
    assert "as _ds_conn:" in flat and "execute_tool(_ds_conn," in flat
    assert "None if _router else conn" not in flat, "메모리 연결을 그대로 넘긴다"
    assert "app_mod=app" in flat, "허용 스키마 해석 seam 을 안 넘긴다"

    authz = _read("unit", "feature-0003-agent-web-ui", "src", "tool_authz.py")
    scope = authz[authz.index("def scoped_execution("):authz.index("# ── L4:")]
    assert "set_active_schema_allowlist(allowed)" in scope, "allowlist 를 안 건다"
    assert "_resolve_product_datasource(" in scope, "단일 경로 연결을 안 잡는다"
    assert "set_active_datasource(" in scope, "방언·기본DB 컨텍스트를 안 건다"
    assert 'code="datasource_unbound"' in scope, "미바인딩에서 fail-closed 가 아니다"


def test_scope_cleanup_covers_every_axis():
    """스코프를 세운 모든 축은 finally 에서 되돌아야 한다 — 웹은 요청 간 스레드를 재사용한다."""
    authz = _read("unit", "feature-0003-agent-web-ui", "src", "tool_authz.py")
    scope = authz[authz.index("def scoped_execution("):authz.index("# ── L4:")]
    fin = scope[scope.index("finally:"):]
    for axis in ("reset_active_ds_router", "close_all", "single_conn.close",
                 "clear_active_schema_allowlist", "set_active_datasource(None)"):
        assert axis in fin, f"finally 가 {axis} 를 안 되돌린다"


def test_external_calls_do_not_write_csv_files():
    """★ 응답에서 경로만 지우면 파일은 계속 쌓이고(디스크), 소유 대화와 무관한 전체 결과가
    서버에 남으며, 저장 실패 시 절대경로가 예외 문구로 샌다. 애초에 안 만든다."""
    tools = _read(*_TOOLS)
    seg = tools[tools.index("csv_paths.append(save_csv(") - 400:
                tools.index("csv_paths.append(save_csv(") + 200]
    assert 'if not args.get("_suppress_csv")' in seg
    body = _router_fn("run_structure_tool")
    assert 'arguments["_suppress_csv"] = True' in body


def test_ledger_keeps_the_datasource_even_though_execute_tool_pops_it():
    """★ `execute_tool` 이 `arguments` 에서 `datasource` 를 pop 한다 — 실행 뒤에 읽으면 항상
    빈 값이라 추출 원장의 datasource 추적이 통째로 죽는다."""
    body = _router_fn("run_structure_tool")
    assert "requested_ds = str(arguments.get(\"datasource\")" in body
    assert "datasource_key=requested_ds" in body
    assert body.index("requested_ds =") < body.index("execute_tool("), \
        "실행 뒤에 읽으면 이미 pop 된 뒤다"
    tools = _read(*_TOOLS)
    assert 'arguments.pop("datasource"' in tools, "전제가 바뀌었다 — 이 테스트를 재검토하라"


# ── 실사용 제보 2차 — 게이트·거부 메시지 (2026-08-14) ────────────────────────

def test_catalog_function_block_points_at_the_standard_alternative():
    """★ 차단 자체는 유지하되(권한 탐침 함수와 한 목록이라 선별 완화는 경계를 흐린다),
    같은 정보를 얻는 표준 경로를 알려준다 — 안 알려주면 sys 카탈로그 조합을 반복 시도한다."""
    # `modules` 를 스텁으로 갈아끼우는 다른 테스트가 있어 import 순서에 따라 실패한다
    # — 소스에서 함수만 떼어 **실행**한다(문자열 검사가 아니라 동작을 본다).
    src = _read(*_TOOLS)
    seg = src[src.index("_CATALOG_NAME_FUNCS = ("):src.index("def _heavy_query_coach(")]
    ns: dict = {"str": str, "any": any}
    exec(compile(seg, "<catalog>", "exec"), ns)
    fn = ns["_catalog_function_redirect"]
    hint = fn("forbidden function: object_name")
    assert "INFORMATION_SCHEMA" in hint
    assert "REFERENTIAL_CONSTRAINTS" in hint, "외래키 경로를 안 알려준다"
    assert fn("multi-statement not allowed") == "", "무관한 거부에도 안내가 붙는다"

    assert "_catalog_function_redirect(guard.error_reason)" in src, "거부 메시지에 안 붙는다"


def test_estimate_failure_message_does_not_blame_query_size():
    """★ '범위를 좁혀라' 는 오도다 — 계획을 못 받아온 것이지 쿼리가 무거운 게 아니다.
    라이브 제보: 같은 논리를 다른 형태로 재작성하니 통과했다."""
    src = code_only(_read(*_TOOLS))
    seg = src[src.index("⚠ 사전 부하추정에 실패했습니다") - 200:]
    seg = seg[:seg.index("elif est >")]
    assert "쿼리가 무거워서가 아닙니다" in seg
    assert "다른 형태로 재작성" in seg
