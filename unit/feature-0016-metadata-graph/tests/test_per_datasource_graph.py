"""feature-0016 per-datasource: rag_objects 투영 + scope 필터 + scope_roots + 큐레이션 설명 보존 검증.

throwaway AGE(+rag_objects·table_descriptions, 2 datasource) 대상. 각 데이터소스가 자기 그래프를
갖고, scope 가 격리되며, table_descriptions 설명이 rag_objects 투영에 덮어쓰이지 않음을 확인.
"""
import os
import sys

import psycopg
import metadata_graph as mg


def main() -> int:
    conn = psycopg.connect(os.environ["DSN"], autocommit=True)
    rep = mg.sync_graph(conn=conn)
    assert rep["errors"] == 0, rep
    assert rep["rag_tables"] >= 4, rep            # dsA 2 + dsB 2
    assert rep["tables"] >= 1, rep                # 큐레이션 1건(dsA orders)

    # ── 데이터소스별 진입 그래프(scope_roots) ──
    ra = mg.scope_roots("dsA", conn=conn)
    rb = mg.scope_roots("dsB", conn=conn)
    fa = {n["fqn"] for n in ra["nodes"]}
    fb = {n["fqn"] for n in rb["nodes"]}
    assert "dbo.orders" in fa and "dbo.customers" in fa, f"dsA roots: {fa}"
    assert "dbo.orders" in fb and "dbo.items" in fb, f"dsB roots: {fb}"
    # scope 격리: dsA roots 는 dsA 노드만, dsB 는 dsB 만
    assert all(n["key"].startswith("dsA:") for n in ra["nodes"]), ra["nodes"]
    assert all(n["key"].startswith("dsB:") for n in rb["nodes"]), rb["nodes"]
    # HAS_TABLE 엣지 존재(Schema→Table)
    assert any(e["type"] == "HAS_TABLE" for e in ra["edges"]), ra["edges"]

    # ── 검색 scope 격리 ──
    sa = mg.search_nodes("orders", scope="dsA", conn=conn)
    assert sa and all(n["key"].startswith("dsA:") for n in sa), sa

    # ── 큐레이션 설명 보존(rag_objects 가 덮어쓰지 않음) ──
    oa = [n for n in mg.search_nodes("orders", scope="dsA", conn=conn) if n["fqn"] == "dbo.orders"][0]
    assert oa["description"] == "주문(큐레이션)", f"dsA orders desc: {oa}"
    ob = [n for n in mg.search_nodes("orders", scope="dsB", conn=conn) if n["fqn"] == "dbo.orders"][0]
    assert not ob.get("description"), f"dsB orders 는 큐레이션 없음이어야: {ob}"

    # ── 멱등 재sync ──
    rep2 = mg.sync_graph(conn=conn)
    assert rep2["errors"] == 0, rep2
    oa2 = [n for n in mg.search_nodes("orders", scope="dsA", conn=conn) if n["fqn"] == "dbo.orders"][0]
    assert oa2["description"] == "주문(큐레이션)", f"재sync 후 설명 보존 실패: {oa2}"

    print("PER-DATASOURCE GRAPH: PASS",
          {"rag_tables": rep["rag_tables"], "tables": rep["tables"],
           "dsA_roots": len(ra["nodes"]), "dsB_roots": len(rb["nodes"]), "dsA_search": len(sa)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
