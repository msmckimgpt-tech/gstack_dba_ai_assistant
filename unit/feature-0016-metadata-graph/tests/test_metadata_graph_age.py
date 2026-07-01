"""feature-0016 Phase 1b 검증: metadata_graph 모듈을 라이브 AGE 인스턴스에 대해 행위 검증.

standalone 실행(throwaway AGE 컨테이너 대상):
    DSN="host=localhost port=5432 dbname=agent_kb user=postgres password=v" \
        PYTHONPATH=/app python /app/test_metadata_graph_age.py

모듈은 conn 주입 시 shared.db/config 를 import 하지 않으므로 단독 import 가능(상단 import=logging 뿐).
검증: 노드/엣지 MERGE · 멱등 · 한국어 · Cypher injection 방어 · 검색 · k-hop 이웃.
"""
import os
import sys

import psycopg
import metadata_graph as mg


def main() -> int:
    dsn = os.environ["DSN"]
    conn = psycopg.connect(dsn, autocommit=True)
    cur = conn.cursor()
    mg._set_age_path(cur)

    # ── sync 샘플 (게임 도메인 모사) ──
    mg.sync_table(cur, "ds1", "dbo", "orders", "주문 테이블 — 고객 구매 거래", "manual")
    # graphux5: ordinal(실제 스키마 순서) 투영 검증 — id=1, customer_id=2.
    mg.sync_column(cur, "ds1", "dbo", "orders", "id", "PK", "manual", ordinal=1)
    mg.sync_column(cur, "ds1", "dbo", "orders", "customer_id", "고객 FK", "manual", ordinal=2)
    mg.sync_table(cur, "ds1", "dbo", "customers", "고객 마스터", "manual")
    mg.sync_column(cur, "ds1", "dbo", "customers", "id", "PK", "manual", ordinal=1)
    mg.sync_relationship(cur, "ds1", "dbo.orders", "customer_id",
                         "dbo.customers", "id", "N:1", "fk_introspect", 1.0)
    mg.sync_glossary_term(cur, "ds1", "주문", "고객이 구매한 거래")

    # ── 멱등: 동일 sync 재실행 → 노드 중복 없어야 ──
    for _ in range(3):
        mg.sync_table(cur, "ds1", "dbo", "orders", "주문 테이블 — 고객 구매 거래", "manual")
        mg.sync_relationship(cur, "ds1", "dbo.orders", "customer_id",
                             "dbo.customers", "id", "N:1", "fk_introspect", 1.0)

    # ── Cypher injection 방어: 따옴표·중괄호·역슬래시 포함 설명 ──
    mg.sync_table(cur, "ds1", "dbo", "evil",
                  "it's a \"test\" } RETURN 1 // \\ DROP", "manual")

    # ── 검증 1: 검색 (영문 fqn) ──
    res = mg.search_nodes("orders", conn=conn)
    assert any(n["fqn"] == "dbo.orders" for n in res), f"search orders: {res}"

    # ── 검증 2: 검색 (한국어 용어 이름) ──
    res_kr = mg.search_nodes("주문", conn=conn)
    assert any(n["name"] == "주문" for n in res_kr), f"search 주문: {res_kr}"

    # ── 검증 3: injection 표가 정상 노드로 1개만 존재 (escape 성공 = 깨지지 않음) ──
    res_evil = mg.search_nodes("evil", conn=conn)
    assert any(n["fqn"] == "dbo.evil" for n in res_evil), f"search evil: {res_evil}"

    # ── 검증 4: k-hop 이웃 (orders 중심 depth=2) ──
    nb = mg.neighborhood("ds1:dbo.orders", depth=2, conn=conn)
    fqns = {n["fqn"] for n in nb["nodes"]}
    assert "dbo.orders" in fqns, f"nb fqns: {fqns}"
    assert "dbo.orders.customer_id" in fqns, f"nb missing column: {fqns}"
    etypes = {e["type"] for e in nb["edges"]}
    assert "HAS_COLUMN" in etypes, f"nb etypes: {etypes}"
    # depth 2 에서 customer_id -[REFERENCES]-> customers.id 도달
    assert "dbo.customers.id" in fqns, f"nb 2-hop missing: {fqns}"
    assert "REFERENCES" in etypes, f"nb REFERENCES missing: {etypes}"
    # ── 검증 4d (graphux5): Column 노드가 ordinal(실제 스키마 순서) 을 투영으로 보유 ──
    ordby_fqn = {n["fqn"]: n.get("ordinal") for n in nb["nodes"] if n["label"] == "Column"}
    assert ordby_fqn.get("dbo.orders.id") == 1, f"ordinal id!=1: {ordby_fqn}"
    assert ordby_fqn.get("dbo.orders.customer_id") == 2, f"ordinal customer_id!=2: {ordby_fqn}"

    # ── 검증 4b (graphux4 raw-graphid 재작성): 엣지 방향 보존 ──
    # neighborhood 는 start_id=source·end_id=target 로 물리 저장 방향을 유지해야 한다. 라벨로 검증
    # (HAS_COLUMN=Table→Column, REFERENCES=Column→Column FK 방향). 무방향 -[r]- 프론티어 역전 회귀 방지.
    lblof = {n["key"]: n["label"] for n in nb["nodes"]}
    for e in nb["edges"]:
        if e["type"] == "HAS_COLUMN":
            assert lblof.get(e["source"]) == "Table" and lblof.get(e["target"]) == "Column", \
                f"HAS_COLUMN 방향(Table→Column) 위반: {e}"
        if e["type"] == "REFERENCES":
            assert lblof.get(e["source"]) == "Column" and lblof.get(e["target"]) == "Column", \
                f"REFERENCES 방향(Column→Column) 위반: {e}"

    # ── 검증 4c: 자식(Column) 노드에서 시작해도 방향 보존 + 역중복 0 ──
    nbc = mg.neighborhood("ds1:dbo.orders.customer_id", depth=2, conn=conn)
    lblc = {n["key"]: n["label"] for n in nbc["nodes"]}
    hc2 = [e for e in nbc["edges"] if e["type"] == "HAS_COLUMN"]
    assert hc2, f"자식시작 HAS_COLUMN 없음: {nbc['edges']}"
    for e in hc2:
        assert lblc.get(e["source"]) == "Table" and lblc.get(e["target"]) == "Column", \
            f"자식시작 HAS_COLUMN 역전: {e}"
    seen_e = set(); dups = []
    for e in nbc["edges"]:
        k = (e["source"], e["type"], e["target"])
        if k in seen_e:
            dups.append(k)
        seen_e.add(k)
    assert not dups, f"역중복 엣지(양끝점 프론티어): {dups}"

    # ── 검증 5: 멱등 — orders Table 노드 정확히 1개 ──
    cnt = mg._cypher(cur, "MATCH (t:Table {fqn:'dbo.orders'}) RETURN t.key", 1)
    assert len(cnt) == 1, f"orders Table duplicated: {len(cnt)}"

    # ── 검증 6 (B1): dollar-quote breakout 인젝션 방어 ──
    # $$ 포함 페이로드가 외곽 SQL 을 탈출하면 sentinel 테이블이 DROP 된다. 방어 시 그대로 생존.
    cur.execute("CREATE TABLE IF NOT EXISTS _b1_sentinel (x int)")
    inj = "x$$) AS (k ag_catalog.agtype); DROP TABLE _b1_sentinel; --"
    try:
        mg.search_nodes(inj, conn=conn)          # 검색어 경로
        mg.neighborhood(inj, depth=1, conn=conn)  # node key 경로
    except Exception:
        pass
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = '_b1_sentinel'")
    assert cur.fetchone() is not None, "B1 injection: sentinel dropped — dollar-quote breakout!"
    # $$ 포함 값이 정상 노드로 저장·검색되는지(escape 성공, 데이터 무손상)
    mg.sync_table(cur, "ds1", "dbo", "ev$$il", "desc $$ with dollars", "manual")
    r_ev = mg.search_nodes("ev$$il", conn=conn)
    assert any((n.get("name") or "") == "ev$$il" for n in r_ev), f"dollar value lost: {r_ev}"

    print("ALL ASSERTS PASS", {
        "search_orders": len(res), "search_주문": len(res_kr),
        "nb_nodes": len(nb["nodes"]), "nb_edges": len(nb["edges"]),
        "orders_node_count": len(cnt),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
