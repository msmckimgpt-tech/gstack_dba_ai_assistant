"""feature-0013 relationship-diagrams — relationships.py 순수 로직 단위 테스트.

DB 연결 없이 검증 가능한 부분만 다룬다(JOIN 파서·digest 빌더·FK row 추출·alias 해석).
upsert/introspect/load 의 PG I/O 경로는 라이브 스택 통합검증 대상(TEST.md §4 참조).
"""
from modules import relationships as R


# ── parse_join_relationships ────────────────────────────────────────────
def test_simple_inner_join_with_aliases():
    sql = ("SELECT o.id FROM orders o "
           "JOIN customers c ON o.customer_id = c.id")
    edges = R.parse_join_relationships(sql)
    assert len(edges) == 1
    e = edges[0]
    # 무방향 정규화라 (orders.customer_id, customers.id) 한 edge — 방향 라벨은 src/tgt 둘 중 하나
    tables = {e["src_table"].lower(), e["tgt_table"].lower()}
    assert tables == {"orders", "customers"}
    cols = {f'{e["src_table"].lower()}.{e["src_column"].lower()}',
            f'{e["tgt_table"].lower()}.{e["tgt_column"].lower()}'}
    assert cols == {"orders.customer_id", "customers.id"}


def test_multiple_joins():
    sql = ("SELECT * FROM orders o "
           "JOIN customers c ON o.customer_id = c.id "
           "JOIN products p ON o.product_id = p.id")
    edges = R.parse_join_relationships(sql)
    pairs = {tuple(sorted([f'{e["src_table"].lower()}', f'{e["tgt_table"].lower()}'])) for e in edges}
    assert ("customers", "orders") in pairs
    assert ("orders", "products") in pairs
    assert len(edges) == 2


def test_where_style_equijoin():
    sql = ("SELECT * FROM orders o, customers c "
           "WHERE o.customer_id = c.id")
    edges = R.parse_join_relationships(sql)
    assert len(edges) == 1
    assert {edges[0]["src_table"].lower(), edges[0]["tgt_table"].lower()} == {"orders", "customers"}


def test_backtick_and_bracket_identifiers():
    sql = ("SELECT * FROM `sales`.`orders` o "
           "JOIN [dbo].[customers] c ON o.`customer_id` = c.[id]")
    edges = R.parse_join_relationships(sql)
    assert len(edges) == 1
    assert {edges[0]["src_table"].lower(), edges[0]["tgt_table"].lower()} == {"orders", "customers"}


def test_self_join_excluded():
    sql = "SELECT * FROM emp e JOIN emp m ON e.mgr_id = m.id"
    # 같은 leaf 테이블(emp) 끼리는 관계 edge 로 학습하지 않음(self-eq 제외)
    assert R.parse_join_relationships(sql) == []


def test_no_join_returns_empty():
    assert R.parse_join_relationships("SELECT 1") == []
    assert R.parse_join_relationships("SELECT * FROM orders WHERE id = 5") == []
    assert R.parse_join_relationships("") == []
    assert R.parse_join_relationships(None) == []


def test_dedup_directionless():
    sql = ("SELECT * FROM orders o JOIN customers c "
           "ON o.customer_id = c.id AND c.id = o.customer_id")
    edges = R.parse_join_relationships(sql)
    assert len(edges) == 1


def test_comment_stripping():
    sql = ("SELECT * FROM orders o -- comment\n"
           "JOIN customers c /* block */ ON o.customer_id = c.id")
    edges = R.parse_join_relationships(sql)
    assert len(edges) == 1


def test_function_compare_ignored():
    # 함수/상수 비교(테이블.컬럼 형태 아님)는 edge 아님
    sql = "SELECT * FROM orders o JOIN customers c ON LOWER(o.name) = 'x'"
    assert R.parse_join_relationships(sql) == []


# ── _alias_map ──────────────────────────────────────────────────────────
def test_alias_map_three_part_leaf():
    amap = R._alias_map("from db.sales.orders o join customers c")
    assert amap.get("o") == "orders"
    assert amap.get("c") == "customers"
    assert amap.get("orders") == "orders"  # 테이블명 자신도 키


def test_alias_map_no_alias():
    amap = R._alias_map("from orders join customers on orders.cid = customers.id")
    assert amap.get("orders") == "orders"
    assert amap.get("customers") == "customers"


# ── build_relationship_digest ───────────────────────────────────────────
def _row(src_fqn, src_col, tgt_fqn, tgt_col, card="", source="fk_introspect", conf=1.0):
    return (src_fqn, src_col, tgt_fqn, tgt_col, card, source, conf)


def test_digest_basic_and_source_tag():
    rows = [
        _row("sales.orders", "customer_id", "sales.customers", "id", card="N:1"),
        _row("sales.orders", "product_id", "sales.products", "id", source="conversation", conf=0.4),
    ]
    out = R.build_relationship_digest(rows, "")
    assert "sales.orders.customer_id → sales.customers.id [N:1]" in out
    assert "(conversation)" in out  # 비-introspect 출처는 태그
    assert out.count("\n") == 1


def test_digest_message_filter():
    rows = [
        _row("sales.orders", "customer_id", "sales.customers", "id"),
        _row("hr.employees", "dept_id", "hr.departments", "id"),
    ]
    out = R.build_relationship_digest(rows, "주문(orders) 흐름 알려줘")
    assert "orders" in out
    assert "employees" not in out  # 질문에 없는 테이블 edge 는 제외


def test_digest_empty():
    assert R.build_relationship_digest([], "") == ""
    assert R.build_relationship_digest([_row("a.x", "c", "b.y", "d")], "zzz nomatch") == ""


# ── _rows_from_outgoing ─────────────────────────────────────────────────
def test_rows_from_outgoing_dict_shape():
    results = [{"columns": ["CONSTRAINT_NAME", "COLUMN_NAME", "REFERENCED_TABLE_SCHEMA",
                            "REFERENCED_TABLE_NAME", "REFERENCED_COLUMN_NAME"],
                "rows": [["fk_o_c", "customer_id", "sales", "customers", "id"]]}]
    edges = R._rows_from_outgoing(results)
    assert edges == [{"constraint_name": "fk_o_c", "src_column": "customer_id",
                      "tgt_schema": "sales", "tgt_table": "customers", "tgt_column": "id"}]


def test_rows_from_outgoing_tuple_shape():
    results = [(["c0", "c1", "c2", "c3", "c4"],
                [["fk1", "a_id", "", "a", "id"]])]
    edges = R._rows_from_outgoing(results)
    assert len(edges) == 1
    assert edges[0]["tgt_table"] == "a"


def test_rows_from_outgoing_skips_incomplete():
    results = [{"columns": [], "rows": [["only", "two"], ["fk", "col", "s", "t", "c"]]}]
    edges = R._rows_from_outgoing(results)
    assert len(edges) == 1  # 5컬럼 미만 row 는 skip


# ── 불변식: upsert ON CONFLICT 대상 == migration UNIQUE 제약 (desync = 런타임 오류) ──
def test_onconflict_target_matches_unique_constraint():
    """REV 패널 백엔드 최고위험 항목 lock — 둘 중 한쪽만 수정되면 ON CONFLICT 런타임 실패."""
    import os
    import re
    base = os.path.join(os.path.dirname(__file__), "..")
    rel = open(os.path.join(base, "src/modules/relationships.py")).read()
    mig = open(os.path.join(base, "alembic/versions/20260629_0024_table_relationships.py")).read()
    on_conf = re.search(r"ON CONFLICT \(([^)]+)\)", rel).group(1)
    uniq = re.search(r"ux_table_relationships_edge\s+UNIQUE \(([^)]+)\)", mig).group(1)
    norm = lambda s: [c.strip() for c in s.replace("\n", " ").split(",")]
    assert norm(on_conf) == norm(uniq), f"ON CONFLICT {norm(on_conf)} != UNIQUE {norm(uniq)}"


def test_apostrophe_identifier_handled_conservatively():
    """비정상 식별자(작은따옴표 포함)는 보수적으로 처리 — 깨진 이름이 edge 로 새지 않는다 (보안 패널 제안).

    저장 경로(upsert_relationship)는 %s 파라미터화라 어떤 이름도 SQL 주입이 불가하지만,
    파서가 잘못된 edge 를 만들지 않음을 추가로 보증한다.
    """
    sql = "SELECT * FROM orders o JOIN customers c ON o.`cust'id` = c.id"
    edges = R.parse_join_relationships(sql)
    for e in edges:
        for v in (e["src_table"], e["tgt_table"], e["src_column"], e["tgt_column"]):
            assert "'" not in v and "`" not in v and "[" not in v
