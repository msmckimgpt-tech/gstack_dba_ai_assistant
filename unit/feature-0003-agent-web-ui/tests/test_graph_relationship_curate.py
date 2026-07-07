"""feature-0016 §55 B — 관계 큐레이션(trust/break) 라우터 유닛: Column key 파싱 + 합성 로직 가드.

라이브 PG/AGE 불요 — 파싱 헬퍼와 schema_products 합성의 순수 로직만 검증(엔드포인트 e2e 는 배포 후
PB-0008/수동). 파싱 규약: 그래프 Column 노드 key `<scope>:<schema>.<table>.<column>`.
"""
from routers import admin_metadata as am


def test_parse_graph_column_key_three_part():
    r = am._parse_graph_column_key("mssql-x:accountdb.T_Account.UserID")
    assert r == {"scope": "mssql-x", "schema": "accountdb", "table": "T_Account",
                 "column": "UserID", "table_fqn": "accountdb.T_Account"}


def test_parse_graph_column_key_two_part_no_schema():
    r = am._parse_graph_column_key("ds1:T.col")
    assert r and r["schema"] == "" and r["table"] == "T" and r["column"] == "col"
    assert r["table_fqn"] == "T"


def test_parse_graph_column_key_scope_lowercased():
    r = am._parse_graph_column_key("MSSQL-X:db.T.c")
    assert r and r["scope"] == "mssql-x"


def test_parse_graph_column_key_invalid():
    assert am._parse_graph_column_key("no-colon") is None
    assert am._parse_graph_column_key("ds1:onlytable") is None
    assert am._parse_graph_column_key("") is None
    assert am._parse_graph_column_key(None) is None
