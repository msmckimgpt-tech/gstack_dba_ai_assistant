"""feature-0016 Phase 1c 검증: sync_graph 의 관계형 read 경로 (table_descriptions 등 → AGE).

throwaway AGE(+관계형 테이블·샘플) 대상. test_metadata_graph_age 가 저수준 sync_* op 을 검증한다면,
본 테스트는 sync_graph() 가 실제 관계형 테이블을 읽어 그래프로 투영하는 전체 경로를 검증한다.
"""
import os
import sys

import psycopg
import metadata_graph as mg


def main() -> int:
    conn = psycopg.connect(os.environ["DSN"], autocommit=True)

    rep = mg.sync_graph(conn=conn)
    assert rep["errors"] == 0, f"sync errors: {rep}"
    assert rep["tables"] >= 2, f"tables: {rep}"
    assert rep["columns"] >= 2, f"columns: {rep}"
    assert rep["relationships"] >= 1, f"relationships: {rep}"
    assert rep["glossary"] >= 1, f"glossary: {rep}"

    # 멱등: 재실행 후 동일 노드 수
    rep2 = mg.sync_graph(conn=conn)
    assert rep2["errors"] == 0, f"resync errors: {rep2}"

    # 그래프 투영 확인
    res = mg.search_nodes("orders", conn=conn)
    assert any(n["fqn"] == "dbo.orders" for n in res), f"search: {res}"

    nb = mg.neighborhood("dsX:dbo.orders", depth=2, conn=conn)
    fqns = {n["fqn"] for n in nb["nodes"]}
    etypes = {e["type"] for e in nb["edges"]}
    assert "dbo.orders.customer_id" in fqns, f"nb cols: {fqns}"
    assert "dbo.customers.id" in fqns, f"nb 2hop: {fqns}"
    assert "REFERENCES" in etypes, f"nb etypes: {etypes}"

    # orders Table 단일(멱등) — scope-specific key 로 매칭(fqn 은 scope 간 공유라 부적합).
    cur = conn.cursor()
    mg._set_age_path(cur)
    cnt = mg._cypher(cur, "MATCH (t:Table {key:'dsX:dbo.orders'}) RETURN t.key", 1)
    assert len(cnt) == 1, f"orders dup: {len(cnt)}"

    print("SYNC_GRAPH FROM RELATIONAL: PASS", {**rep, "search": len(res),
          "nb_nodes": len(nb["nodes"]), "nb_edges": len(nb["edges"])})
    return 0


if __name__ == "__main__":
    sys.exit(main())
