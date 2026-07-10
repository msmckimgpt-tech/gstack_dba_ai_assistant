"""rel-selfheal: sync_relationship 끝점 앵커링 라이브 AGE 행위검증 (throwaway).

sibling 라이브 테스트(test_metadata_graph_age.py 등)와 동형 — 본문을 main() 에 넣고
`if __name__ == "__main__"` 로만 실행한다. pytest 가 이 디렉토리를 수집해도
import 시점 부작용(DSN KeyError / 라이브 DB 변조)이 없다(적대 패널 QA-F1).
"""
import os


def main():
    import psycopg
    import metadata_graph as mg

    conn = psycopg.connect(os.environ["DSN"], autocommit=True)
    cur = conn.cursor()

    # 라벨 사전선언 (0025 동형 — 필요 라벨만)
    cur.execute("SET search_path=ag_catalog,public")
    for v in ("Product", "Datasource", "Schema", "Table", "Column", "GlossaryTerm"):
        try:
            cur.execute("SELECT create_vlabel('metadata_kb', %s::cstring)", (v,))
        except Exception:
            pass
    for e in ("USES", "HAS_SCHEMA", "HAS_TABLE", "HAS_COLUMN", "REFERENCES",
              "RELATED_TERM", "DESCRIBES"):
        try:
            cur.execute("SELECT create_elabel('metadata_kb', %s::cstring)", (e,))
        except Exception:
            pass

    # 1) qualified fqn — 앵커링 체인 생성 검증
    mg.sync_relationship(cur, "scopeX", "db1.TableA", "ColA", "db1.TableB", "ColB",
                         source="inferred", confidence=0.3, weight=0.3, status="candidate")

    def q(cy, cols=1):
        names = ", ".join(f"c{i} agtype" for i in range(cols))
        cur.execute(
            "SELECT * FROM ag_catalog.cypher('metadata_kb', $$ " + cy + " $$) AS (" + names + ")")
        return cur.fetchall()

    rows = q("MATCH (s:Schema {key:'scopeX:db1'})-[:HAS_TABLE]->(t:Table {key:'scopeX:db1.TableA'})"
             "-[:HAS_COLUMN]->(c:Column {key:'scopeX:db1.TableA.ColA'}) RETURN c.key")
    assert len(rows) == 1, f"src anchor chain: {rows}"
    rows = q("MATCH (t:Table {key:'scopeX:db1.TableB'})-[:HAS_COLUMN]->"
             "(c:Column {key:'scopeX:db1.TableB.ColB'}) RETURN c.key")
    assert len(rows) == 1, f"tgt anchor chain: {rows}"
    rows = q("MATCH (:Column {key:'scopeX:db1.TableA.ColA'})-[r:REFERENCES]->"
             "(:Column {key:'scopeX:db1.TableB.ColB'}) RETURN r.status")
    assert len(rows) == 1 and "candidate" in str(rows[0][0]), f"ref edge: {rows}"

    # 2) 기존 Table 의 description/source 비파괴 (SET 생략 확인)
    mg.sync_table(cur, "scopeX", "db1", "TableC", description="큐레이션 설명", source="manual")
    mg.sync_relationship(cur, "scopeX", "db1.TableC", "Cid", "db1.TableA", "ColA",
                         source="conversation", confidence=0.4, weight=0.49, status="candidate")
    rows = q("MATCH (t:Table {key:'scopeX:db1.TableC'}) RETURN t.description, t.source", cols=2)
    assert "큐레이션 설명" in str(rows[0][0]) and "manual" in str(rows[0][1]), f"non-destructive: {rows}"

    # 3) 레거시 ''-slot (fqn 에 스키마 없음) — Table 미생성(잘못된 키 방지), Column 만
    mg.sync_relationship(cur, "scopeX", "Legacy", "L1", "Legacy2", "L2",
                         source="conversation", confidence=0.4, weight=0.4, status="candidate")
    rows = q("MATCH (t:Table {key:'scopeX:Legacy'}) RETURN t.key")
    assert len(rows) == 0, f"legacy table must not exist: {rows}"
    rows = q("MATCH (c:Column {key:'scopeX:Legacy.L1'}) RETURN c.key")
    assert len(rows) == 1, f"legacy column: {rows}"

    # 4) 멱등 — 재실행 후 중복 없음
    mg.sync_relationship(cur, "scopeX", "db1.TableA", "ColA", "db1.TableB", "ColB",
                         source="inferred", confidence=0.3, weight=0.35, status="candidate")
    rows = q("MATCH (t:Table {key:'scopeX:db1.TableA'}) RETURN count(t)")
    assert "1" == str(rows[0][0]), f"idempotent table: {rows}"
    rows = q("MATCH (:Column {key:'scopeX:db1.TableA.ColA'})-[r:REFERENCES]->"
             "(:Column {key:'scopeX:db1.TableB.ColB'}) RETURN count(r), r.weight", cols=2)
    assert "1" == str(rows[0][0]), f"idempotent edge: {rows}"

    print("ANCHOR LIVE: ALL ASSERTS PASS")


if __name__ == "__main__":
    main()
