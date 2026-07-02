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


# ── parse_join_relationships: qualifier 캡처 (rel-selfheal) ────────────────
def test_parse_join_captures_explicit_qualifier():
    """SQL 이 명시한 스키마/DB qualifier 를 edge 에 보존한다 — 미해석('') 저장은 AGE 고아 노드."""
    sql = ("SELECT * FROM dk_data_release.Achievement a "
           "JOIN dk_data_release.AchievementQuest q ON a.UniqueID = q.AchievementID")
    edges = R.parse_join_relationships(sql)
    assert len(edges) == 1
    assert edges[0]["src_schema"] == "dk_data_release"
    assert edges[0]["tgt_schema"] == "dk_data_release"


def test_parse_join_unqualified_emits_empty_schema():
    """미qualify 테이블은 schema='' — learn_relationships_from_sql 의 default_schema 가 채운다."""
    sql = "SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id"
    edges = R.parse_join_relationships(sql)
    assert len(edges) == 1
    assert edges[0]["src_schema"] == ""
    assert edges[0]["tgt_schema"] == ""


def test_parse_join_three_part_uses_db_and_dbo_dropped():
    """3-part `db.dbo.table` → qualifier=db (MSSQL 스키마-slot=DB명 규약). 2-part dbo.x → ''."""
    sql = ("SELECT * FROM dk_data_release.dbo.Achievement a "
           "JOIN dbo.AchievementReward r ON a.UniqueID = r.AchievementID")
    edges = R.parse_join_relationships(sql)
    assert len(edges) == 1
    schemas = {edges[0]["src_schema"], edges[0]["tgt_schema"]}
    assert "dk_data_release" in schemas
    assert "" in schemas


# ── _alias_map ──────────────────────────────────────────────────────────
def test_alias_map_three_part_leaf():
    # rel-selfheal: 값 = (leaf, qualifier). 3-part 는 qualifier=db(첫 segment — MSSQL DB명 규약).
    amap = R._alias_map("from db.sales.orders o join customers c")
    assert amap.get("o") == ("orders", "db")
    assert amap.get("c") == ("customers", "")
    assert amap.get("orders") == ("orders", "db")  # 테이블명 자신도 키


def test_alias_map_no_alias():
    amap = R._alias_map("from orders join customers on orders.cid = customers.id")
    assert amap.get("orders") == ("orders", "")
    assert amap.get("customers") == ("customers", "")


def test_alias_map_two_part_schema_and_dbo():
    # 2-part: qualifier 보존(MySQL schema). 단 'dbo' 는 DB 차원 소실이라 미채택('').
    amap = R._alias_map("from sales.orders o join dbo.customers c")
    assert amap.get("o") == ("orders", "sales")
    assert amap.get("c") == ("customers", "")


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


def test_infer_name_fk_uniqueid_pk():
    """rel-selfheal: `<X>ID` 컬럼 → X 테이블의 관용 PK `UniqueID` (dk_data_release 실측 패턴).

    'uniqueid' 가 _pk_like 후보에 없으면 이 게임 DB 계열(PK=UniqueID)에서 name_fk 추론이
    전면 불가였다 — Achievement/AchievementQuest/AchievementReward 는 사용자 검증 시나리오.
    """
    tc = {"Achievement": ["UniqueID", "Type", "Title", "DLC"],
          "AchievementQuest": ["UniqueID", "AchievementID", "QuestType"],
          "AchievementReward": ["UniqueID", "AchievementID", "RewardType"]}
    edges = R.infer_implicit_relationships("dk_data_release", tc)
    pairs = {(e["src_table"], e["src_column"], e["tgt_table"], e["tgt_column"]) for e in edges}
    assert ("AchievementQuest", "AchievementID", "Achievement", "UniqueID") in pairs
    assert ("AchievementReward", "AchievementID", "Achievement", "UniqueID") in pairs
    assert all(e["src_schema"] == "dk_data_release" for e in edges)


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
    # probe-mssqlfix 리뷰 MINOR-2: 신 SQL 의 EXISTS 상관 위치(s0.<src_col>)에 사용자 유래
    # 식별자가 새로 노출 — 그 자리의 q() 이스케이프도 봉인한다.
    ms2 = D.get("mssql").probe_relationship_overlap("", "src", "c]ol", "", "t", "d", 10)
    assert "= s0.[c]]ol]" in ms2


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


# ── rel-selfheal 적대 패널 반영 (B-F2/B-F3/B-F4/Sec-F2/QA-F2) ─────────────────

def test_infer_uniqueid_excluded_from_shared_key():
    """B-F3: 보편 PK 'UniqueID' 는 heuristic-2(shared_key) 제외 — PK≡PK 쓰레기 pairwise 차단.

    _pk_like 의 FK **타깃** 역할(name_fk)은 유지된다(test_infer_name_fk_uniqueid_pk).
    """
    tc = {"Achievement": ["UniqueID", "Type", "Title", "DLC"],
          "AchievementQuest": ["UniqueID", "AchievementID", "QuestType"],
          "AchievementReward": ["UniqueID", "AchievementID", "RewardType"]}
    edges = R.infer_implicit_relationships("dk_data_release", tc)
    assert not any(
        e["heuristic"] == "shared_key"
        and e["src_column"].lower() in ("uniqueid", "unique_id")
        and e["tgt_column"].lower() in ("uniqueid", "unique_id")
        for e in edges
    ), f"PK≡PK shared_key garbage: {edges}"
    # name_fk 2건은 그대로 살아 있어야 한다(회귀 방지)
    pairs = {(e["src_table"], e["src_column"], e["tgt_table"], e["tgt_column"]) for e in edges}
    assert ("AchievementQuest", "AchievementID", "Achievement", "UniqueID") in pairs


class _CapturingCursor:
    def __init__(self, rows=None):
        self.executed = []
        self._rows = rows or []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _CapturingConn:
    def __init__(self, rows=None):
        self.cursors = []
        self._rows = rows

    def cursor(self):
        cur = _CapturingCursor(self._rows)
        self.cursors.append(cur)
        return cur


def test_apply_signal_schema_slot_constraint_present():
    """B-F2: a_schema/b_schema 지정 시 스키마-slot 매칭 한정('' 레거시는 wildcard).

    미지정이면 기존 leaf-only 매칭(하위호환)."""
    conn = _CapturingConn(rows=[])
    R.apply_relationship_signal(conn, "scope", "A", "a", "B", "b", True,
                                a_schema="db1", b_schema="db1")
    sel = next(s for s, p in conn.cursors[0].executed if s.lstrip().startswith("SELECT"))
    params = next(p for s, p in conn.cursors[0].executed if s.lstrip().startswith("SELECT"))
    assert "lower(source_schema)=lower(%s)" in sel and "source_schema=''" in sel
    assert list(params).count("db1") == 4  # 양방향 × (source, target)

    conn2 = _CapturingConn(rows=[])
    R.apply_relationship_signal(conn2, "scope", "A", "a", "B", "b", True)
    sel2 = next(s for s, p in conn2.cursors[0].executed if s.lstrip().startswith("SELECT"))
    assert "source_schema" not in sel2  # 미지정 = 제약 없음


def test_probe_missing_object_error_is_negative(monkeypatch):
    """B-F4: '객체 부재' 실행오류는 negative 신호 — 실행 불가 edge 의 영구 미파단 차단."""
    monkeypatch.setattr(R, "fetch_probe_candidates",
                        lambda conn, scope, limit, db_scope=None:
                        [(7, "db1", "A", "a", "db1", "B", "b")])
    monkeypatch.setattr(R, "_rw_conn", lambda c: (object(), False))
    signals = []
    monkeypatch.setattr(R, "apply_relationship_signal",
                        lambda *a, **k: signals.append((a, k)) or 1)
    touched = []
    monkeypatch.setattr(R, "_touch_validated", lambda kc, rid: touched.append(rid))

    class _D:
        def probe_relationship_overlap(self, *a, **k):
            return "SELECT 1"

    def _raise_missing(conn, sql):
        raise RuntimeError("('42S02', \"Invalid object name 'A'\")")

    rep = R.probe_and_reinforce(None, _D(), "scope", kb_conn=object(),
                                raw_execute=_raise_missing)
    assert rep["negative"] == 1 and rep["failed"] == 0
    assert touched == [7]                      # 큐 rotation 전진(head 고착 차단)
    assert signals and signals[0][0][6] is False
    assert signals[0][1] == {"a_schema": "db1", "b_schema": "db1"}


def test_probe_transient_error_touches_and_counts_failed(monkeypatch):
    """B-F4: transient 오류(타임아웃 등)는 신호 없이 timestamp 전진 + failed 집계."""
    monkeypatch.setattr(R, "fetch_probe_candidates",
                        lambda conn, scope, limit, db_scope=None:
                        [(8, "db1", "A", "a", "db1", "B", "b")])
    monkeypatch.setattr(R, "_rw_conn", lambda c: (object(), False))
    signals = []
    monkeypatch.setattr(R, "apply_relationship_signal",
                        lambda *a, **k: signals.append(a) or 1)
    touched = []
    monkeypatch.setattr(R, "_touch_validated", lambda kc, rid: touched.append(rid))

    class _D:
        def probe_relationship_overlap(self, *a, **k):
            return "SELECT 1"

    def _raise_transient(conn, sql):
        raise RuntimeError("timeout expired")

    rep = R.probe_and_reinforce(None, _D(), "scope", kb_conn=object(),
                                raw_execute=_raise_transient)
    assert rep["failed"] == 1 and rep["negative"] == 0 and not signals
    assert touched == [8]


def test_probe_clamps_cap_sample_timeout(monkeypatch):
    """Sec-F2: cap/sample/timeout misconfig 폭주를 코드 상한으로 클램프(dialect sample 클램프와 대칭)."""
    seen = {}

    def _fetch(conn, scope, limit, db_scope=None):
        seen["limit"] = limit
        return []

    monkeypatch.setattr(R, "fetch_probe_candidates", _fetch)

    class _D:
        def probe_relationship_overlap(self, *a, **k):
            return ""

    R.probe_and_reinforce(None, _D(), "s", kb_conn=object(),
                          raw_execute=lambda c, q: ([], None),
                          cap=10**6, sample=10**7, timeout_ms=10**9)
    assert seen["limit"] == 500


def test_learn_fills_default_schema_and_normalizes_lower(monkeypatch):
    """QA-F2a/QA-F4: 미qualify 테이블은 default_schema 로 채우고, MSSQL 경로
    (normalize_schema_lower=True)는 slot 을 lower() 정규화(phantom 중복 노드 차단)."""
    ups = []
    monkeypatch.setattr(R, "upsert_relationship", lambda c, s, **kw: ups.append(kw) or True)
    sigs = []
    monkeypatch.setattr(R, "apply_relationship_signal",
                        lambda *a, **k: sigs.append(k) or 1)
    monkeypatch.setattr(R, "_rw_conn", lambda c: (object(), False))
    sql = ("SELECT * FROM Achievement a "
           "JOIN AchievementQuest q ON a.UniqueID = q.AchievementID")
    n = R.learn_relationships_from_sql(sql, "scope", default_schema="DK_Data_Release",
                                       normalize_schema_lower=True)
    assert n == 1
    assert ups[0]["src_schema"] == "dk_data_release"
    assert ups[0]["tgt_schema"] == "dk_data_release"
    assert sigs[0] == {"a_schema": "dk_data_release", "b_schema": "dk_data_release"}


def test_learn_keeps_typed_case_without_normalize(monkeypatch):
    """QA-F4 대조군: MySQL 경로(normalize 미지정)는 실행 성공한 SQL 의 타이핑 케이스 보존."""
    ups = []
    monkeypatch.setattr(R, "upsert_relationship", lambda c, s, **kw: ups.append(kw) or True)
    monkeypatch.setattr(R, "apply_relationship_signal", lambda *a, **k: 1)
    monkeypatch.setattr(R, "_rw_conn", lambda c: (object(), False))
    sql = ("SELECT * FROM GameLogs.orders o "
           "JOIN GameLogs.customers c ON o.customer_id = c.id")
    n = R.learn_relationships_from_sql(sql, "scope")
    assert n == 1
    assert ups[0]["src_schema"] == "GameLogs" and ups[0]["tgt_schema"] == "GameLogs"


def test_probe_missing_object_unresolved_slot_not_negative(monkeypatch):
    """재검증 R-1: db_scope 순회에서 ''-slot(레거시 wildcard) 후보의 객체-부재 오류는
    negative 가 아니라 failed — 소속 아닌 catalog 프로브 2회로 실관계가 broken 되는 오파단 차단."""
    monkeypatch.setattr(R, "fetch_probe_candidates",
                        lambda conn, scope, limit, db_scope=None:
                        [(9, "", "A", "a", "", "B", "b")])
    monkeypatch.setattr(R, "_rw_conn", lambda c: (object(), False))
    signals = []
    monkeypatch.setattr(R, "apply_relationship_signal",
                        lambda *a, **k: signals.append(a) or 1)
    touched = []
    monkeypatch.setattr(R, "_touch_validated", lambda kc, rid: touched.append(rid))

    class _D:
        def probe_relationship_overlap(self, *a, **k):
            return "SELECT 1"

    def _raise_missing(conn, sql):
        raise RuntimeError("('42S02', \"Invalid object name 'A'\")")

    rep = R.probe_and_reinforce(None, _D(), "scope", kb_conn=object(),
                                raw_execute=_raise_missing, db_scope="db1")
    assert rep["failed"] == 1 and rep["negative"] == 0 and not signals
    assert touched == [9]  # rotation 은 전진(head 고착 차단 유지)


def test_probe_missing_object_resolved_slot_under_db_scope_is_negative(monkeypatch):
    """재검증 R-1 대조군: db_scope 하에서 slot 이 그 catalog 로 확정된 후보의 객체-부재는
    구조적 negative(선언된 DB 에 테이블이 실제 없음)."""
    monkeypatch.setattr(R, "fetch_probe_candidates",
                        lambda conn, scope, limit, db_scope=None:
                        [(10, "db1", "A", "a", "db1", "B", "b")])
    monkeypatch.setattr(R, "_rw_conn", lambda c: (object(), False))
    signals = []
    monkeypatch.setattr(R, "apply_relationship_signal",
                        lambda *a, **k: signals.append(a) or 1)
    monkeypatch.setattr(R, "_touch_validated", lambda kc, rid: None)

    class _D:
        def probe_relationship_overlap(self, *a, **k):
            return "SELECT 1"

    def _raise_missing(conn, sql):
        raise RuntimeError("Invalid object name 'db1.A'")

    rep = R.probe_and_reinforce(None, _D(), "scope", kb_conn=object(),
                                raw_execute=_raise_missing, db_scope="db1")
    assert rep["negative"] == 1 and rep["failed"] == 0 and signals


def test_probe_missing_object_unresolved_slot_stays_failed(monkeypatch):
    """재검증 R-1: db_scope(MSSQL catalog 순회) 하의 ''-slot 레거시 후보는 wildcard 로 모든
    catalog 에 fetch 되므로, 소속 아닌 catalog 의 객체-부재 오류를 negative 로 먹이면
    실관계가 오답 catalog 프로브 2회만에 영구 broken — failed/touch-only 로 남아야 한다."""
    monkeypatch.setattr(R, "fetch_probe_candidates",
                        lambda conn, scope, limit, db_scope=None:
                        [(9, "", "A", "a", "", "B", "b")])
    monkeypatch.setattr(R, "_rw_conn", lambda c: (object(), False))
    signals = []
    monkeypatch.setattr(R, "apply_relationship_signal",
                        lambda *a, **k: signals.append(a) or 1)
    touched = []
    monkeypatch.setattr(R, "_touch_validated", lambda kc, rid: touched.append(rid))

    class _D:
        def probe_relationship_overlap(self, *a, **k):
            return "SELECT 1"

    def _raise_missing(conn, sql):
        raise RuntimeError("Invalid object name 'A'")

    rep = R.probe_and_reinforce(None, _D(), "scope", kb_conn=object(),
                                raw_execute=_raise_missing, db_scope="db1")
    assert rep["failed"] == 1 and rep["negative"] == 0 and not signals
    assert touched == [9]


def test_probe_missing_object_resolved_slot_under_db_scope_is_negative(monkeypatch):
    """재검증 R-1 대조군: db_scope 하에서 양쪽 slot 이 채워진(=현 catalog 소속 확정) 후보의
    객체-부재는 구조적 negative — 자기교정(B-F4) 유지."""
    monkeypatch.setattr(R, "fetch_probe_candidates",
                        lambda conn, scope, limit, db_scope=None:
                        [(10, "db1", "A", "a", "db1", "B", "b")])
    monkeypatch.setattr(R, "_rw_conn", lambda c: (object(), False))
    signals = []
    monkeypatch.setattr(R, "apply_relationship_signal",
                        lambda *a, **k: signals.append(a) or 1)
    monkeypatch.setattr(R, "_touch_validated", lambda kc, rid: None)

    class _D:
        def probe_relationship_overlap(self, *a, **k):
            return "SELECT 1"

    def _raise_missing(conn, sql):
        raise RuntimeError("Invalid object name 'A'")

    rep = R.probe_and_reinforce(None, _D(), "scope", kb_conn=object(),
                                raw_execute=_raise_missing, db_scope="db1")
    assert rep["negative"] == 1 and rep["failed"] == 0
    assert signals and signals[0][6] is False


def test_dialect_mssql_probe_no_subquery_inside_aggregate():
    """probe-mssqlfix: MSSQL 은 집계식 내 서브쿼리 금지(오류 130) — SUM 인자는 파생 테이블의
    단순 컬럼이어야 하고 CASE/EXISTS 는 파생 테이블 안에 있어야 한다(라이브 전면 실패 회귀 봉인)."""
    import re as _re
    from modules import dialects as D
    ms = D.get("mssql").probe_relationship_overlap("db1", "Achievement", "UniqueID",
                                                   "db1", "AchievementQuest", "AchievementID", 50)
    assert _re.search(r"SUM\(\s*CASE", ms) is None      # 집계가 서브쿼리 식을 직접 감싸면 안 됨
    assert "SUM(s.m)" in ms and "CASE WHEN EXISTS" in ms
    assert ms.index("CASE WHEN EXISTS") > ms.index("FROM (")  # CASE 는 파생 테이블 내부
    assert "TOP 50" in ms and "IS NOT NULL" in ms
