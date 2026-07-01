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


# ══════════════════════════════════════════════════════════════════════════
# feature-0016 implicit-edges: 추론 + 강화(reinforcement) + 프로브 순수 로직 테스트
# ══════════════════════════════════════════════════════════════════════════

# ── next_reinforcement_state (강화 상태 전이) ─────────────────────────────
def test_reinforce_positive_asymptotic_increase():
    w0 = 0.30
    w1, pos, neg, st = R.next_reinforcement_state(w0, 0, 0, "candidate", "inferred", True)
    assert w1 > w0 and w1 < 1.0           # 상승하되 1.0 초과 안 함
    assert pos == 1 and neg == 0
    # 여러 번 양성 → 1.0 으로 점근(도달·초과 없음)
    w = 0.3
    for _ in range(50):
        w, *_ = R.next_reinforcement_state(w, 0, 0, "candidate", "inferred", True)
    assert 0.99 <= w <= 1.0


def test_reinforce_negative_decay_and_break():
    """음성 신호 누적 → weight 감쇠 → floor 이하에서 broken 파단(추론 시작 0.30 에서 2회면 파단)."""
    w, pos, neg, st = 0.30, 3, 0, "candidate"
    seen_broken = False
    for _ in range(6):
        w, pos, neg, st = R.next_reinforcement_state(w, pos, neg, st, "inferred", False)
        if st == "broken":
            seen_broken = True
            break
    assert seen_broken, f"음성 누적이 broken 으로 이어져야 함 (w={w})"
    assert w <= R._BREAK_FLOOR


def test_reinforce_negative_faster_than_positive_across_band():
    """비대칭 불변식: **동작 구간 전체**에서 1회 음성 감쇠폭 > 1회 양성 상승폭. 특히 추론 시작
    weight(0.30)·floor 바로 위에서도 성립해야 틀린 엣지가 확실히 끊어진다.

    (과거 곱셈 감쇠 `w*(1-0.34)` 는 [0.15, 0.306] 에서 down<up 으로 역전돼 틀린 엣지가 오히려
    상승하는 결함이 있었다 — 이 테스트가 그 구간을 강제 커버해 회귀를 잡는다.)"""
    ws = [R.CONFIDENCE["inferred"], R._BREAK_FLOOR + 0.001, 0.2, 0.306, 0.31, 0.5, 0.85, 0.99]
    for w in ws:
        up = R.next_reinforcement_state(w, 0, 0, "candidate", "inferred", True)[0] - w
        down = w - R.next_reinforcement_state(w, 0, 0, "candidate", "inferred", False)[0]
        assert down > up, f"asymmetry violated at w={w}: up={up:.4f}, down={down:.4f}"


def test_reinforce_wrong_edge_with_half_spurious_positives_still_breaks():
    """핵심 시나리오: ~50% 잘못된 양성이 섞여도 순 방향은 하강(틀린 엣지는 결국 끊어진다).

    과거 결함에서는 alternating neg/pos 가 순 +0.018/쌍 으로 상승했다. 감산 음성으로 순 하강 보장."""
    w, pos, neg, st = R.CONFIDENCE["inferred"], 0, 0, "candidate"
    for _ in range(6):   # neg, pos 교대 6쌍
        w, pos, neg, st = R.next_reinforcement_state(w, pos, neg, st, "inferred", False)
        if st == "broken":
            break
        w, pos, neg, st = R.next_reinforcement_state(w, pos, neg, st, "inferred", True)
    assert st == "broken" or w < R.CONFIDENCE["inferred"], f"틀린 엣지가 상승하면 안 됨 (w={w}, st={st})"


def test_reinforce_promotes_to_trusted():
    """높은 weight + 충분한 양성 누적 → trusted 승격."""
    w, pos, neg, st = 0.80, 1, 0, "candidate"
    for _ in range(10):
        w, pos, neg, st = R.next_reinforcement_state(w, pos, neg, st, "inferred", True)
    assert st == "trusted"
    assert w >= R._TRUST_CEIL and pos >= R._MIN_POS_FOR_TRUST


def test_reinforce_fk_is_authoritative_immutable():
    """FK(fk_introspect)는 음성 신호를 받아도 강등되지 않는다(권위적)."""
    w, pos, neg, st = R.next_reinforcement_state(0.2, 0, 5, "trusted", "fk_introspect", False)
    assert w == 1.0 and st == "trusted"
    assert neg == 6   # 신호는 카운트하되 상태 불변


# ── classify_probe (실데이터 겹침 판정) ───────────────────────────────────
def test_classify_probe_positive_negative_neutral():
    assert R.classify_probe(50, 50) == "positive"     # 100% 겹침
    assert R.classify_probe(50, 30) == "positive"     # 60% ≥ 0.5
    assert R.classify_probe(50, 0) == "negative"      # 0% + 충분표본
    assert R.classify_probe(50, 10) == "neutral"      # 20% (0.5 미만, 0 초과)
    assert R.classify_probe(0, 0) == "neutral"        # 표본 없음 — 판정 보류
    assert R.classify_probe(2, 0) == "neutral"        # 표본 부족(< min) — 음성 오판 방지


# ── 명명 규칙 헬퍼 ────────────────────────────────────────────────────────
def test_col_key_base_variants():
    assert R._col_key_base("customer_id") == "customer"
    assert R._col_key_base("AccountSN") == "account"
    assert R._col_key_base("nItemNo") == "item"       # 헝가리안 n 제거
    assert R._col_key_base("id") is None              # base 너무 짧음
    assert R._col_key_base("name") is None            # 키 형태 아님


def test_norm_table_token_prefix_and_plural():
    assert R._norm_table_token("T_Account") == "account"
    assert R._norm_table_token("orders") == "order"   # 복수 s 제거
    assert R._norm_table_token("tbl_Items") == "item"


# ── infer_implicit_relationships (암묵 관계 추론) ─────────────────────────
def test_infer_name_fk_heuristic():
    """<base>_id 컬럼 → 같은 이름 테이블의 PK 로 추론."""
    tc = {"orders": ["id", "customer_id", "amount"],
          "customers": ["id", "name"]}
    edges = R.infer_implicit_relationships("sales", tc)
    pairs = {(e["src_table"], e["src_column"], e["tgt_table"], e["tgt_column"]) for e in edges}
    assert ("orders", "customer_id", "customers", "id") in pairs
    assert all(e["src_schema"] == "sales" for e in edges)
    assert any(e["heuristic"] == "name_fk" for e in edges)


def test_infer_excludes_self_and_generic():
    """자기참조·범용 컬럼(id 단독)은 후보로 만들지 않는다."""
    tc = {"orders": ["id", "order_id"], "products": ["id"]}
    edges = R.infer_implicit_relationships("s", tc)
    for e in edges:
        assert e["src_table"].lower() != e["tgt_table"].lower()


def test_infer_shared_key_heuristic():
    """접두 있는 키 컬럼이 두 테이블에 공유되면 후보 join."""
    tc = {"item_log": ["seq", "world_no", "item_uid"],
          "world_state": ["world_no", "flag"]}
    edges = R.infer_implicit_relationships("game", tc)
    got = {tuple(sorted([f'{e["src_table"]}.{e["src_column"]}',
                         f'{e["tgt_table"]}.{e["tgt_column"]}'])) for e in edges}
    assert tuple(sorted(["item_log.world_no", "world_state.world_no"])) in got


def test_infer_shared_key_skips_overshared_generic_dimension():
    """너무 많은 테이블이 공유하는 키(범용 차원)는 pairwise 후보에서 제외 — 폭주 방지."""
    tc = {f"t{i}": ["region_id", "val"] for i in range(R._SHARED_KEY_MAX_OWNERS + 3)}
    edges = R.infer_implicit_relationships("s", tc)
    assert all(e["heuristic"] != "shared_key" for e in edges)


def test_infer_empty_and_cap():
    assert R.infer_implicit_relationships("s", {}) == []
    # cap 준수: 대량 후보라도 상한 이하
    tc = {f"tbl{i}": ["id", f"tbl{i-1}_id"] for i in range(1, 60)}
    edges = R.infer_implicit_relationships("s", tc, cap=10)
    assert len(edges) <= 10


# ── digest: weight/status 태그 (9-tuple, feature-0016) ────────────────────
def test_digest_trust_tags_and_broken_exclusion():
    rows = [
        # (src_fqn, src_col, tgt_fqn, tgt_col, card, source, conf, weight, status)
        ("s.orders", "customer_id", "s.customers", "id", "", "inferred", 0.3, 0.30, "candidate"),
        ("s.a", "x", "s.b", "y", "", "conversation", 0.4, 0.90, "trusted"),
        ("s.bad", "p", "s.zzz", "q", "", "inferred", 0.3, 0.10, "broken"),
    ]
    out = R.build_relationship_digest(rows, "")
    assert "[추정 w=0.30]" in out          # candidate → 추정 태그
    assert "[신뢰]" in out                  # trusted(비-FK) → 신뢰 태그
    assert "bad" not in out and "zzz" not in out   # broken 은 제외


def test_digest_backward_compat_7tuple():
    """기존 7-tuple(weight/status 없음) 호출도 그대로 동작 — 태그 없음."""
    rows = [("s.o", "cid", "s.c", "id", "N:1", "fk_introspect", 1.0)]
    out = R.build_relationship_digest(rows, "")
    assert "s.o.cid → s.c.id [N:1]" in out
    assert "추정" not in out and "신뢰" not in out


# ── dialect probe SQL (MySQL LIMIT / MSSQL TOP + 식별자 이스케이프) ────────
def test_dialect_probe_sql_shape():
    from modules import dialects as D
    my = D.get("mysql").probe_relationship_overlap("sales", "orders", "customer_id",
                                                    "sales", "customers", "id", 50)
    assert "LIMIT 50" in my and "`sales`.`orders`" in my and "EXISTS" in my
    ms = D.get("mssql").probe_relationship_overlap("dbo", "Orders", "CustomerId",
                                                   "dbo", "Customers", "Id", 50)
    assert "TOP 50" in ms and "[dbo].[Orders]" in ms and "EXISTS" in ms


def test_dialect_probe_sql_identifier_escaping():
    """식별자 내 인용문자는 이스케이프(백틱 이중화 / 대괄호 이중화) — 주입 방어."""
    from modules import dialects as D
    my = D.get("mysql").probe_relationship_overlap("", "we`ird", "c", "", "t", "d", 10)
    assert "we``ird" in my
    ms = D.get("mssql").probe_relationship_overlap("", "we]rd", "c", "", "t", "d", 10)
    assert "we]]rd" in ms


def test_dialect_probe_sql_statement_timeout():
    """timeout_ms>0 이면 프로브에 시간 상한(MySQL MAX_EXECUTION_TIME / MSSQL LOCK_TIMEOUT). 0 이면 미적용."""
    from modules import dialects as D
    my = D.get("mysql").probe_relationship_overlap("s", "o", "c", "s", "t", "d", 50, timeout_ms=3000)
    assert "MAX_EXECUTION_TIME(3000)" in my
    assert "MAX_EXECUTION_TIME" not in D.get("mysql").probe_relationship_overlap(
        "s", "o", "c", "s", "t", "d", 50, timeout_ms=0)
    ms = D.get("mssql").probe_relationship_overlap("s", "o", "c", "s", "t", "d", 50, timeout_ms=3000)
    assert ms.startswith("SET LOCK_TIMEOUT 3000;")
    assert "LOCK_TIMEOUT" not in D.get("mssql").probe_relationship_overlap(
        "s", "o", "c", "s", "t", "d", 50, timeout_ms=0)
