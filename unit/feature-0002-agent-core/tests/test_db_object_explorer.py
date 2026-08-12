"""feature-0040 db-object-explorer — 역할 기반 DB 객체 탐색 도구·수집·투영 회귀 잠금.

본 스위트가 지키는 **핵심 불변식은 허위 부재 방지**다. 역할 축을 도입하면
`FR-false-absence-zero-row-catalog-scope` 와 같은 함정이 역할 단위로 재발할 수 있다 —
MySQL 에 별칭(SYNONYM)을 물으면 카탈로그가 0행을 내지만 그것은 "없다" 가 아니라 "MySQL 에
그 개념이 없다" 이고, 둘을 구분하지 않으면 모델이 사용자에게 거짓을 말한다.

따라서 아래 테스트는 "동작한다" 를 확인하는 데 그치지 않고, **미지원·위임·권한 3상태가
0건으로 뭉개지지 않는지**를 문자열 수준에서 단정한다(§16.7 G10 — 재발 클래스의 구조 가드).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from modules import db_object_roles as roles          # noqa: E402
from modules import dialects as _dialects             # noqa: E402
from modules import tools as _tools                   # noqa: E402


# ══════════════════════════════════════════════════════════════════════
#  taxonomy — 역할 정의와 어휘 정규화
# ══════════════════════════════════════════════════════════════════════

def test_taxonomy_declares_six_roles_and_collects_five():
    """역할은 6종이고 수집 대상은 5종 — `routine` 은 routine_objects(0034) 소유."""
    assert set(roles.ALL_ROLES) == {
        "routine", "view", "trigger", "schedule", "alias", "generator"}
    assert set(roles.COLLECTED_ROLES) == set(roles.ALL_ROLES) - {"routine"}
    assert roles.OWNED_ELSEWHERE == frozenset({"routine"})


@pytest.mark.parametrize("raw,expected", [
    # 벤더 어휘가 역할로 흡수되는지 — 모델은 `object_role="event"` 처럼 자기 방언으로 부른다.
    ("event", "schedule"), ("EVENT", "schedule"), ("job", "schedule"),
    ("SQL Agent Job", "schedule"), ("agent_job", "schedule"), ("pg_cron", "schedule"),
    ("dbms_scheduler", "schedule"),
    ("synonym", "alias"), ("dblink", "alias"),
    ("sequence", "generator"), ("auto_increment", "generator"),
    ("procedure", "routine"), ("function", "routine"),
    ("materialized_view", "view"),
    # 한국어
    ("트리거", "trigger"), ("이벤트", "schedule"), ("시퀀스", "generator"), ("뷰", "view"),
])
def test_normalize_role_absorbs_vendor_and_korean_vocabulary(raw, expected):
    assert roles.normalize_role(raw) == expected


def test_normalize_role_rejects_unknown():
    """미상은 빈 문자열 — 호출측이 '유효 역할 목록' 안내로 분기한다(조용한 폴백 금지)."""
    assert roles.normalize_role("지구본") == ""
    assert roles.normalize_role("") == ""
    assert roles.normalize_role(None) == ""


def test_unsupported_notice_never_says_absent():
    """UNSUPPORTED 안내문은 '없다' 가 아니라 '지원하지 않는다' 로 서술해야 한다.

    이 문장이 곧 모델이 사용자에게 옮길 서술이므로, 여기서 '0건'·'없습니다' 로 새면
    그 자체가 허위 부재의 발원지가 된다.
    """
    msg = roles.unsupported_notice("alias", "MySQL")
    assert "존재하지 않는 객체 종류" in msg
    assert "0건인 것이 아니라" in msg
    assert "지원하지 않는다" in msg


def test_delegated_notice_routes_instead_of_denying():
    """DELEGATED 는 거부가 아니라 전용 도구로의 재라우팅이어야 한다."""
    msg = roles.delegated_notice("routine")
    assert "존재하며 조회할 수 있습니다" in msg
    assert "search_routines" in msg and "describe_routine" in msg
    assert "없다' 는 뜻이 아닙니다" in msg


# ══════════════════════════════════════════════════════════════════════
#  dialect capability matrix
# ══════════════════════════════════════════════════════════════════════

def test_routine_is_delegated_on_every_dialect():
    """**회귀 잠금**: `routine` 이 어떤 방언에서도 UNSUPPORTED 로 떨어지면 안 된다.

    초판이 정확히 이 결함을 가졌다 — 하위클래스 지원표에 routine 이 없어 기본값
    UNSUPPORTED 로 낙하했고, 도구가 "MySQL 은 프로시저를 지원하지 않습니다" 라는 명백한
    거짓을 냈다. base 클래스가 OWNED_ELSEWHERE 를 선점 처리해 구조적으로 막았으므로,
    새 방언이 추가돼도 이 단언이 자동으로 지킨다.
    """
    for d in (_dialects.MySQLDialect(), _dialects.MSSQLDialect()):
        assert d.object_support("routine") == roles.DELEGATED, d.name
        assert d.object_support("procedure") == roles.DELEGATED, d.name


def test_mysql_capability_matrix():
    d = _dialects.MySQLDialect()
    assert d.object_support("view") == roles.SUPPORTED
    # 트리거·이벤트는 MySQL 에서 각각 TRIGGER/EVENT 권한이 있어야 카탈로그에 보인다.
    assert d.object_support("trigger") == roles.PRIVILEGED
    assert d.object_support("schedule") == roles.PRIVILEGED
    # MySQL 에는 SYNONYM·SEQUENCE 객체가 없다(AUTO_INCREMENT 는 컬럼 속성).
    assert d.object_support("alias") == roles.UNSUPPORTED
    assert d.object_support("generator") == roles.UNSUPPORTED


def test_mssql_capability_matrix():
    d = _dialects.MSSQLDialect()
    assert d.object_support("view") == roles.SUPPORTED
    assert d.object_support("trigger") == roles.SUPPORTED
    assert d.object_support("alias") == roles.SUPPORTED
    assert d.object_support("generator") == roles.SUPPORTED
    # Agent 작업은 sysadmin 이 아니면 자기 소유분만 보인다 → PRIVILEGED.
    assert d.object_support("schedule") == roles.PRIVILEGED
    assert "sysadmin" in d.object_privilege_note("schedule")


def test_unsupported_roles_produce_no_sql():
    """미지원 역할은 SQL 자체를 만들지 않는다 — 0행 질의를 돌려 '없음' 처럼 보이게 하지 않는다."""
    d = _dialects.MySQLDialect()
    assert d.list_objects("alias") is None
    assert d.list_objects("generator") is None
    assert d.object_definition("alias", "x", schema="s") is None


# ══════════════════════════════════════════════════════════════════════
#  dialect SQL — 경계·주입 방어
# ══════════════════════════════════════════════════════════════════════

def test_mysql_enumeration_excludes_internal_schemas():
    """schema 미지정 전량 열거는 시스템·내부 스키마를 **반드시** 잘라내야 한다.

    `search_routines` 의 §18.8 BLOCKER 와 동형 — 누락 시 allowlist 무관 영구차단 대상인
    `agent_memory` 의 뷰·트리거까지 열거된다.
    """
    d = _dialects.MySQLDialect()
    excl = frozenset({"agent_memory", "mysql", "sys", "performance_schema"})
    for role in ("view", "trigger", "schedule"):
        sql = d.list_objects(role, sys_exclude_schemas=excl)
        assert sql, role
        for bad in excl:
            assert f"!= '{bad}'" in sql, f"{role} 열거가 {bad} 를 제외하지 않는다"


def test_mysql_enumeration_with_schema_scopes_to_it():
    d = _dialects.MySQLDialect()
    sql = d.list_objects("trigger", schema="shop", sys_exclude_schemas=frozenset({"mysql"}))
    assert "TRIGGER_SCHEMA = 'shop'" in sql
    # 스키마를 지정했으면 제외 목록은 불필요(이미 한 스키마로 좁혀졌다).
    assert "!= 'mysql'" not in sql


def test_agent_jobs_sql_is_bounded_by_allow_dbs():
    """Agent 작업은 msdb(서버 스코프)라 **허용 DB 필터가 유일한 제품 경계**다."""
    d = _dialects.MSSQLDialect()
    sql = d.list_objects("schedule", allow_dbs=("shop", "kr_live"))
    assert "msdb.dbo.sysjobs" in sql
    assert "LOWER(st.database_name) IN ('shop', 'kr_live')" in sql


def test_agent_jobs_sql_fails_closed_on_empty_allow_dbs():
    """허용 DB 가 비면 **아무것도 매칭되지 않아야** 한다 — 경계 불명 시 열지 않고 닫는다.

    빈 `IN ()` 을 만들면 구문 오류이거나(엔진에 따라) 필터가 사라져 전 서버 작업이 노출된다.
    """
    d = _dialects.MSSQLDialect()
    sql = d.list_objects("schedule", allow_dbs=())
    assert "LOWER(st.database_name) IN ('')" in sql


def test_synonym_target_outside_allowlist_is_masked():
    """별칭의 대상이 허용 범위 밖 DB·원격 서버면 **이름을 노출하지 않는다**.

    `sys.synonyms` 가 freeform 화이트리스트(`_SAFE_SYS_VIEWS`)에서 의도적으로 제외된 사유가
    정확히 `base_object_name` 의 allowlist 밖 DB·linked server 명 노출이다. 구조화 경로가
    그 결정을 우회하면 안 된다 — 존재는 알리되 대상 이름은 가린다.
    """
    d = _dialects.MSSQLDialect()
    sql = d.list_objects("alias", allow_dbs=("shop",))
    assert "PARSENAME(sy.base_object_name, 4) IS NOT NULL" in sql   # 원격 서버 4-part 차단
    assert "허용 범위 밖 DB" in sql
    assert "IN ('shop')" in sql


def test_sql_str_list_escapes_quotes():
    """caller 가 `_safe_ident` 로 정제하지만 방어적 이중화가 있어야 한다(심층 방어)."""
    assert _dialects._sql_str_list(["a'b"]) == "'a''b'"
    assert _dialects._sql_str_list([]) == "''"
    assert _dialects._sql_str_list(None) == "''"


def test_schema_with_braces_does_not_crash_sql_builder():
    """`_safe_ident` 는 중괄호를 제거하지 않는다 — 초판의 `str.format` 조립이 여기서 죽었다.

    구조화 도구는 예외로 죽으면 안 된다(도구 실행 오류는 모델에게 '조회 불가' 로 읽힌다).
    """
    d = _dialects.MySQLDialect()
    sql = d.list_objects("view", schema="we{ird}")
    assert "TABLE_SCHEMA = 'we{ird}'" in sql
    sql2 = d.object_definition("trigger", "t{0}", schema="s{1}")
    assert "t{0}" in sql2 and "s{1}" in sql2


# ══════════════════════════════════════════════════════════════════════
#  도구 — search_db_objects / describe_db_object
# ══════════════════════════════════════════════════════════════════════

def test_tools_are_registered_with_handlers():
    names = [d["function"]["name"] for d in _tools.TOOL_DEFINITIONS_FULL]
    assert "search_db_objects" in names
    assert "describe_db_object" in names
    for n in ("search_db_objects", "describe_db_object"):
        assert n in _tools._TOOL_HANDLERS, f"{n} 정의는 있는데 핸들러가 없다"


def test_search_tool_enum_matches_collected_roles():
    """도구 스키마 enum 이 taxonomy 와 어긋나면 모델이 유효 역할을 거부당한다."""
    d = next(x for x in _tools.TOOL_DEFINITIONS_FULL
             if x["function"]["name"] == "search_db_objects")
    enum = d["function"]["parameters"]["properties"]["object_role"]["enum"]
    assert set(enum) == set(roles.COLLECTED_ROLES)


def test_search_unsupported_role_reports_concept_absence(monkeypatch):
    """MySQL 에 별칭을 물으면 '0건' 이 아니라 '개념 부재' 로 답해야 한다."""
    out = _tools._tool_search_db_objects(None, {"object_role": "synonym"})
    assert "존재하지 않는 객체 종류" in out
    assert "검색 결과가 없습니다" not in out


def test_search_delegated_role_points_to_routine_tools():
    out = _tools._tool_search_db_objects(None, {"object_role": "procedure"})
    assert "search_routines" in out
    assert "없다' 는 뜻이 아닙니다" in out


def test_search_unknown_role_lists_valid_options():
    out = _tools._tool_search_db_objects(None, {"object_role": "무엇"})
    assert out.startswith("오류:")
    for r in roles.ALL_ROLES:
        assert f"`{r}`" in out


def test_describe_requires_role_and_name():
    assert "object_role 은 필수" in _tools._tool_describe_db_object(None, {"object_name": "x"})
    assert "object_name 은 필수" in _tools._tool_describe_db_object(
        None, {"object_role": "view"})


def _fake_rows(monkeypatch, rows):
    monkeypatch.setattr(_tools, "_raw_execute_sql",
                        lambda conn, sql: ([("rows", [], list(rows))], None))


def test_search_renders_role_specific_columns(monkeypatch):
    """역할별 ATTR 표제가 실제 표 머리글로 나와야 한다(위치 계약 → 표제 환원)."""
    _fake_rows(monkeypatch, [
        ("shop", "trg_order_ai", "TRIGGER", "t_order", "AFTER", "INSERT", "활성", ""),
    ])
    out = _tools._tool_search_db_objects(None, {"object_role": "trigger"})
    assert "대상 테이블" in out and "시점" in out and "이벤트" in out
    assert "| shop | trg_order_ai | t_order | TRIGGER | AFTER | INSERT | 활성 |" in out


def test_search_privileged_role_always_carries_ambiguity_caveat(monkeypatch):
    """PRIVILEGED 역할은 **결과가 있든 없든** 권한 모호성을 같은 응답에 실어야 한다(§16.7 G7-c)."""
    _fake_rows(monkeypatch, [])
    out = _tools._tool_search_db_objects(None, {"object_role": "trigger"})
    assert "보이는 범위가 달라집니다" in out
    assert "단정할 수 없습니다" in out


def test_search_surfaces_row_cap_saturation(monkeypatch):
    """표시 상한 포화는 **표면화**해야 한다 — 무음 절단은 곧 허위 부재(§16.7 G9-b)."""
    rows = [(f"s{i}", f"v{i}", "VIEW", "", "YES", "", "3", "") for i in range(200)]
    _fake_rows(monkeypatch, rows)
    out = _tools._tool_search_db_objects(None, {"object_role": "view"})
    assert "더 있습니다" in out
    assert "단정하지 말고" in out


def test_search_all_roles_overview_separates_unsupported(monkeypatch):
    """역할 미지정 = 전 역할 개관. 미지원 역할은 결과 0건이 아니라 별도 절로 분리된다."""
    _fake_rows(monkeypatch, [])
    out = _tools._tool_search_db_objects(None, {})
    assert "조회 대상이 아닌 역할" in out
    assert "MYSQL 에 없는 객체 종류" in out
    # 지원 역할은 실제로 조회 절이 생긴다.
    assert "### ▤ 뷰" in out and "### ⚡ 트리거" in out


def test_search_query_failure_is_not_reported_as_absence(monkeypatch):
    """조회 실패를 '없음' 으로 보고하면 안 된다 — 미확인으로 명시한다."""
    def _boom(conn, sql):
        raise RuntimeError("permission denied")
    monkeypatch.setattr(_tools, "_raw_execute_sql", _boom)
    out = _tools._tool_search_db_objects(None, {"object_role": "view"})
    assert "미확인" in out
    assert "검색 결과가 없습니다" not in out


def test_describe_renders_parts_for_multi_step_objects(monkeypatch):
    """Agent 작업처럼 본문이 여러 조각인 객체는 조각마다 정의 절이 나와야 한다."""
    _fake_rows(monkeypatch, [
        ("nightly", "AGENT_JOB", "shop", "활성", "매일(1일 간격)", "2026-08-11",
         "1. 정리 [TSQL @ shop]", "DELETE FROM t_tmp"),
        ("nightly", "AGENT_JOB", "shop", "활성", "매일(1일 간격)", "2026-08-11",
         "2. 집계 [TSQL @ shop]", "INSERT INTO t_stat SELECT 1"),
    ])
    out = _tools._tool_describe_db_object(
        None, {"object_role": "schedule", "object_name": "nightly", "schema_name": "shop"})
    assert "### 정의 — 1. 정리 [TSQL @ shop]" in out
    assert "### 정의 — 2. 집계 [TSQL @ shop]" in out
    assert "DELETE FROM t_tmp" in out and "INSERT INTO t_stat" in out


def test_describe_empty_definition_is_not_claimed_absent(monkeypatch):
    """정의 열람 권한이 없어 본문이 비면 '정의가 없다' 로 단정하지 않는다."""
    _fake_rows(monkeypatch, [
        ("v_x", "VIEW", "", "YES", "", "3", "", ""),
    ])
    out = _tools._tool_describe_db_object(
        None, {"object_role": "view", "object_name": "v_x", "schema_name": "shop"})
    assert "정의가 비어 있다는 뜻이 아닙니다" in out


def test_describe_not_found_does_not_swallow_crossdb_possibility(monkeypatch):
    _fake_rows(monkeypatch, [])
    out = _tools._tool_describe_db_object(
        None, {"object_role": "view", "object_name": "nope", "schema_name": "shop"})
    assert "없습니다" in out and "이름을 확인하세요" in out


def test_windowing_helper_names_the_calling_tool():
    """이어읽기 안내가 `describe_routine` 로 고정되면 모델이 **다른 도구를 부르라**로 읽는다."""
    long_text = "x" * 200_000
    out = _tools._window_routine_output(long_text, {}, tool_name="describe_db_object")
    if "이어읽기" in out:          # 윈도잉이 켜진 설정에서만 의미 있는 단언
        assert "describe_db_object" in out
        assert "describe_routine 을 다시 호출" not in out


# ══════════════════════════════════════════════════════════════════════
#  수집(db_objects) — 속성 환원과 prune 안전
# ══════════════════════════════════════════════════════════════════════

def test_attr_dict_labels_positional_attrs():
    """ATTR_A/B/C 위치 계약이 저장 시점에 **표제**로 환원돼야 한다."""
    from modules import db_objects as dbo
    d = _dialects.MySQLDialect()
    row = ("shop", "trg", "TRIGGER", "t_order", "AFTER", "INSERT", "활성", "")
    assert dbo._attr_dict(d, "trigger", row) == {
        "시점": "AFTER", "이벤트": "INSERT", "활성": "활성"}


def test_attr_dict_skips_blank_slots():
    from modules import db_objects as dbo
    d = _dialects.MySQLDialect()
    row = ("shop", "v", "VIEW", "", "YES", "", "-", "")
    # 빈 값·'-' 는 제외 — 상세 패널이 빈 행을 렌더하지 않게.
    assert dbo._attr_dict(d, "view", row) == {"갱신가능": "YES"}


def test_collected_roles_exclude_routine_from_introspection():
    """수집 루프가 routine 을 건드리면 routine_objects 와 이중 소유가 된다."""
    from modules import db_objects as dbo
    assert "routine" not in dbo._roles.COLLECTED_ROLES
    assert dbo._PARSE_REFS_ROLES == frozenset({"view", "trigger", "schedule"})


# ══════════════════════════════════════════════════════════════════════
#  그래프 투영 — 라벨 화이트리스트와 key 네임스페이스
# ══════════════════════════════════════════════════════════════════════

def test_graph_labels_registered():
    """AGE 라벨 화이트리스트에 등재돼야 런타임 MERGE 가 허용된다(동적 라벨 생성 금지 규약)."""
    from modules import metadata_graph as mg
    assert "DbObject" in mg._VLABELS
    for e in ("HAS_OBJECT", "OBJECT_USES", "OBJECT_ON"):
        assert e in mg._ELABELS, e
    for p in ("object_role", "object_type", "owner_object", "object_attrs"):
        assert p in mg._PROP_KEYS, p


def test_object_edges_classified_as_relation_not_hierarchy():
    """OBJECT_USES/OBJECT_ON 은 **관계** 엣지 — 2-hop 예산에서 형제 나열보다 먼저 배정된다."""
    from modules import metadata_graph as mg
    assert "OBJECT_USES" in mg._REL_ELABELS
    assert "OBJECT_ON" in mg._REL_ELABELS
    assert "HAS_OBJECT" in mg._HIER_ELABELS


def test_dbobject_key_namespace_includes_role(monkeypatch):
    """key 에 역할이 없으면 동명 뷰·트리거가 한 정점을 공유해 서로의 엣지를 덮어쓴다.

    ⚠ 모듈 전역 교체는 **반드시 `monkeypatch` 로** 한다 — 직접 대입하면 세션 내 후속 테스트가
    가짜 `_merge_vertex`/`_cypher` 를 물려받아, 실패가 이 파일이 아닌 엉뚱한 곳에서 난다.
    """
    from modules import metadata_graph as mg
    calls = []

    class _Cur:
        def execute(self, *a, **k):
            pass
        def fetchall(self):
            return []
        def close(self):
            pass

    monkeypatch.setattr(mg, "_merge_vertex",
                        lambda cur, label, key, props: calls.append(("V", label, key)))
    monkeypatch.setattr(mg, "_merge_edge", lambda *a, **k: calls.append(("E",) + a[1:]))
    monkeypatch.setattr(mg, "_cypher", lambda cur, q, n: [])
    mg.sync_db_object(_Cur(), "ds1", "shop", "v_stat", "view")
    keys = [c[2] for c in calls if c and c[0] == "V" and c[1] == "DbObject"]
    assert keys == ["ds1:shop.v_stat[view]"]


def test_dbobject_trigger_emits_owner_edge(monkeypatch):
    """트리거는 대상 테이블에 **OBJECT_ON**(소유)으로 붙어야 한다 — OBJECT_USES 와 구분.

    합치면 "이 테이블에 뭐가 걸려 있나" 를 답할 수 없다(정의가 그 테이블을 읽기만 하는 객체와
    구별 불가). 분리 투영이 이 기능의 설계 근거 중 하나다.
    """
    from modules import metadata_graph as mg
    edges = []

    class _Cur:
        def execute(self, *a, **k):
            pass
        def fetchall(self):
            return []
        def close(self):
            pass

    monkeypatch.setattr(mg, "_merge_vertex", lambda *a, **k: None)
    monkeypatch.setattr(mg, "_merge_edge",
                        lambda cur, sl, sk, et, tl, tk, props=None: edges.append((et, tk)))
    monkeypatch.setattr(mg, "_cypher", lambda cur, q, n: [])
    mg.sync_db_object(_Cur(), "ds1", "shop", "trg_ai", "trigger",
                      owner_object="t_order",
                      refs=[{"fqn": "shop.t_log", "kind": "write"}])
    assert ("OBJECT_ON", "ds1:shop.t_order") in edges
    assert ("OBJECT_USES", "ds1:shop.t_log") in edges
    assert ("HAS_OBJECT", "ds1:shop.trg_ai[trigger]") in edges


def test_node_from_props_exposes_role_fields():
    from modules import metadata_graph as mg
    d = mg._node_from_props("DbObject", {
        "key": "k", "name": "trg", "object_role": "trigger",
        "object_type": "DML_TRIGGER", "owner_object": "t_order",
        "object_attrs": json.dumps({"시점": "AFTER"}, ensure_ascii=False)})
    assert d["object_role"] == "trigger"
    assert d["owner_object"] == "t_order"
    assert json.loads(d["object_attrs"])["시점"] == "AFTER"
