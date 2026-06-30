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
    mg.sync_column(cur, "ds1", "dbo", "orders", "id", "PK", "manual")
    mg.sync_column(cur, "ds1", "dbo", "orders", "customer_id", "고객 FK", "manual")
    mg.sync_table(cur, "ds1", "dbo", "customers", "고객 마스터", "manual")
    mg.sync_column(cur, "ds1", "dbo", "customers", "id", "PK", "manual")
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

    # ── 검증 5: 멱등 — orders Table 노드 정확히 1개 ──
    cnt = mg._cypher(cur, "MATCH (t:Table {fqn:'dbo.orders'}) RETURN t.key", 1)
    assert len(cnt) == 1, f"orders Table duplicated: {len(cnt)}"

    print("ALL ASSERTS PASS", {
        "search_orders": len(res), "search_주문": len(res_kr),
        "nb_nodes": len(nb["nodes"]), "nb_edges": len(nb["edges"]),
        "orders_node_count": len(cnt),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
