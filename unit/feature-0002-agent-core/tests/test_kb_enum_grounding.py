"""ENUM 자동등록 schema-grounding 게이트 단위 테스트.

배경: _enum_autopropose 가 LLM 이 답변에서 뽑은 (schema, table) 을 그대로 신뢰해, 해당 datasource 에
실재하지 않는 DB/테이블(예: auth scope 에 없는 dbLog.Currency)까지 등록해 온 결함(재현: scope
mysql-kr-an1-auth 에 dbLog 없음). build_known_table_index/is_enum_grounded 는 실제 카탈로그
(table_insight fact)와 (schema, table) 를 대조하는 순수 함수, sweep_ungrounded_enum 은 소급 정리.

LLM·라이브DB 무관: 순수 함수 + FakeConn(SQL 캡처)으로 검증.
"""
from modules import kb_glossary as G


# ── build_known_table_index (정규화 전개) ────────────────────────────────────
def test_index_mysql_schema_table():
    idx = G.build_known_table_index(["dbAuth.AccountBasicInfo"])
    # full / bare / (first.last==full for 2-seg) / (last two==full) — 모두 소문자
    assert "dbauth.accountbasicinfo" in idx
    assert "accountbasicinfo" in idx


def test_index_mssql_db_schema_table():
    # MSSQL 3계층: enum 은 (schema_name=db, table_name) 로 저장 → db.table 로 대조돼야
    idx = G.build_known_table_index(["Sales.dbo.Orders"])
    assert "sales.dbo.orders" in idx     # full
    assert "orders" in idx               # bare table
    assert "sales.orders" in idx         # first.last (db.table) — MSSQL enum 대조 형태
    assert "dbo.orders" in idx           # last two (schema.table)


def test_index_empty_input():
    assert G.build_known_table_index([]) == set()
    assert G.build_known_table_index(None) == set()
    assert G.build_known_table_index(["", "  ", "."]) == set()


# ── is_enum_grounded (판정) ──────────────────────────────────────────────────
def test_grounded_none_idx_failopen():
    # 카탈로그 미가용 → True(등록 허용, false-reject 방지)
    assert G.is_enum_grounded(None, "dbLog", "Currency") is True


def test_grounded_schema_present_hit_and_miss():
    idx = G.build_known_table_index(["dbAuth.AccountBasicInfo"])
    # 실존 (schema, table) → 통과
    assert G.is_enum_grounded(idx, "dbAuth", "AccountBasicInfo") is True
    # 존재하지 않는 DB prefix(dbLog) → 차단 (재현된 버그의 핵심)
    assert G.is_enum_grounded(idx, "dbLog", "AccountBasicInfo") is False


def test_grounded_reported_scenario_auth_scope():
    # scope=mysql-kr-an1-auth: 카탈로그는 dbAuth 계열만 보유(게임 재화 Currency 는 이 scope 에 없음).
    idx = G.build_known_table_index(["dbAuth.AccountBasicInfo", "dbAuth.AccountStatus"])
    # 정상 항목(스크린샷의 dbAuth.AccountBasicInfo.CountryCode)만 통과
    assert G.is_enum_grounded(idx, "dbAuth", "AccountBasicInfo") is True
    # 환각 항목 3종 모두 차단
    assert G.is_enum_grounded(idx, "dbLog", "Currency") is False       # 없는 DB + 없는 table
    assert G.is_enum_grounded(idx, "", "Currency") is False            # db prefix 無 + 없는 table
    assert G.is_enum_grounded(idx, "dbLog", "AccountBasicInfo") is False  # 실존 table 이나 없는 DB


def test_grounded_empty_schema_uses_bare_table():
    idx = G.build_known_table_index(["dbAuth.AccountBasicInfo"])
    # schema 미지정 + 어떤 schema 든 그 table 이 있으면 통과
    assert G.is_enum_grounded(idx, "", "AccountBasicInfo") is True
    # schema 미지정 + 존재하지 않는 table → 차단
    assert G.is_enum_grounded(idx, "", "GhostTable") is False


def test_grounded_missing_table_name_rejected():
    idx = G.build_known_table_index(["dbAuth.AccountBasicInfo"])
    assert G.is_enum_grounded(idx, "dbAuth", "") is False
    assert G.is_enum_grounded(idx, "dbAuth", None) is False


def test_grounded_case_insensitive():
    idx = G.build_known_table_index(["dbAuth.AccountBasicInfo"])
    # 서버 실제 case 와 LLM 표기 case 가 달라도 매칭(schema-name case drift 대비)
    assert G.is_enum_grounded(idx, "DBAUTH", "accountbasicinfo") is True


# ── sweep_ungrounded_enum (소급 정리 SQL) ────────────────────────────────────
class _SweepCursor:
    def __init__(self, state):
        self.state = state
        self._rows = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        self.state["captured"].append((sql, params))
        norm = " ".join(sql.split()).upper()
        if norm.startswith("SELECT DISTINCT SCHEMA_NAME, TABLE_NAME FROM ENUM_DICTIONARY"):
            self._rows = list(self.state["pairs"])
            self.rowcount = len(self._rows)
        elif norm.startswith("DELETE FROM ENUM_DICTIONARY"):
            self.rowcount = self.state["delete_rc"]
        elif norm.startswith("UPDATE ENUM_FEEDBACK"):
            self.rowcount = self.state["update_rc"]
        else:
            self._rows = []
            self.rowcount = 0

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _SweepConn:
    def __init__(self, pairs, delete_rc=1, update_rc=1):
        self.state = {"captured": [], "pairs": list(pairs),
                      "delete_rc": delete_rc, "update_rc": update_rc}

    def cursor(self):
        return _SweepCursor(self.state)

    @property
    def captured(self):
        return self.state["captured"]


def _dml(captured):
    """DELETE/UPDATE 문만 추출(정리 side-effect 검사용)."""
    out = []
    for sql, params in captured:
        norm = " ".join(sql.split()).upper()
        if norm.startswith("DELETE FROM ENUM_DICTIONARY") or norm.startswith("UPDATE ENUM_FEEDBACK"):
            out.append((sql, params))
    return out


def test_sweep_none_idx_is_noop():
    conn = _SweepConn([("dbLog", "Currency")])
    res = G.sweep_ungrounded_enum(conn, "mysql-kr-an1-auth", None, dry_run=False)
    assert res["scanned"] == 0 and res["ungrounded"] == []
    assert res["dict_deleted"] == 0 and res["feedback_rejected"] == 0
    # 카탈로그 없으면 SELECT 조차 안 함(아무것도 건드리지 않음)
    assert conn.captured == []


def test_sweep_empty_idx_is_noop():
    # 빈 set(모든 (schema,table) 이 is_enum_grounded False) 주입 시에도 파괴 금지(footgun 가드).
    conn = _SweepConn([("dbAuth", "AccountBasicInfo")])
    res = G.sweep_ungrounded_enum(conn, "mysql-kr-an1-auth", set(), dry_run=False)
    assert res["scanned"] == 0 and res["ungrounded"] == []
    assert res["dict_deleted"] == 0 and res["feedback_rejected"] == 0
    assert conn.captured == []  # SELECT/DELETE/UPDATE 전부 미발행


def test_sweep_dry_run_reports_without_mutation():
    idx = G.build_known_table_index(["dbAuth.AccountBasicInfo"])
    conn = _SweepConn([("dbAuth", "AccountBasicInfo"), ("dbLog", "Currency"), ("", "Currency")])
    res = G.sweep_ungrounded_enum(conn, "mysql-kr-an1-auth", idx, dry_run=True)
    assert res["scanned"] == 3
    ung = {(u["schema_name"], u["table_name"]) for u in res["ungrounded"]}
    assert ung == {("dbLog", "Currency"), ("", "Currency")}   # 정상 dbAuth 는 제외
    assert res["dict_deleted"] == 0 and res["feedback_rejected"] == 0
    # dry-run 은 DELETE/UPDATE 를 발행하지 않는다
    assert _dml(conn.captured) == []


def test_sweep_execute_deletes_auto_and_rejects_feedback():
    idx = G.build_known_table_index(["dbAuth.AccountBasicInfo"])
    conn = _SweepConn([("dbAuth", "AccountBasicInfo"), ("dbLog", "Currency")],
                      delete_rc=2, update_rc=3)
    res = G.sweep_ungrounded_enum(conn, "mysql-kr-an1-auth", idx, dry_run=False)
    assert [(u["schema_name"], u["table_name"]) for u in res["ungrounded"]] == [("dbLog", "Currency")]
    assert res["dict_deleted"] == 2 and res["feedback_rejected"] == 3
    dml = _dml(conn.captured)
    # ungrounded 1건에 대해서만 DELETE(source='auto') + UPDATE(rejected) 각 1회
    assert len(dml) == 2
    del_sql, del_params = dml[0]
    assert "DELETE FROM enum_dictionary" in del_sql and "source='auto'" in del_sql
    assert del_params == ("mysql-kr-an1-auth", "dbLog", "Currency")
    upd_sql, upd_params = dml[1]
    assert "UPDATE enum_feedback SET status='rejected'" in upd_sql
    assert "IN ('pending','auto_promoted')" in upd_sql
    assert upd_params == ("mysql-kr-an1-auth", "dbLog", "Currency")


def test_sweep_all_grounded_no_mutation():
    idx = G.build_known_table_index(["dbAuth.AccountBasicInfo"])
    conn = _SweepConn([("dbAuth", "AccountBasicInfo")])
    res = G.sweep_ungrounded_enum(conn, "mysql-kr-an1-auth", idx, dry_run=False)
    assert res["ungrounded"] == [] and res["dict_deleted"] == 0
    assert _dml(conn.captured) == []


# ── sweep_unknown_schema_enum (self-heal 안전판 — 실제 스키마 목록 기준 DB 존재) ──────
class _SchemaSweepCursor:
    def __init__(self, state):
        self.state = state
        self._rows = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        self.state["captured"].append((sql, params))
        norm = " ".join(sql.split()).upper()
        if norm.startswith("SELECT DISTINCT SCHEMA_NAME FROM ENUM_DICTIONARY"):
            self._rows = [(s,) for s in self.state["schemas"]]
            self.rowcount = len(self._rows)
        elif norm.startswith("DELETE FROM ENUM_DICTIONARY"):
            self.rowcount = self.state["delete_rc"]
        elif norm.startswith("UPDATE ENUM_FEEDBACK"):
            self.rowcount = self.state["update_rc"]
        else:
            self._rows = []
            self.rowcount = 0

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _SchemaSweepConn:
    def __init__(self, schemas, delete_rc=1, update_rc=1):
        self.state = {"captured": [], "schemas": list(schemas),
                      "delete_rc": delete_rc, "update_rc": update_rc}

    def cursor(self):
        return _SchemaSweepCursor(self.state)

    @property
    def captured(self):
        return self.state["captured"]


def test_schema_sweep_empty_known_failopen():
    conn = _SchemaSweepConn(["dbLog"])
    res = G.sweep_unknown_schema_enum(conn, "mysql-kr-an1-auth", [], dry_run=False)
    assert res["scanned"] == 0 and res["ungrounded"] == []
    assert conn.captured == []   # known 없으면 SELECT 조차 안 함


def test_schema_sweep_dry_run_lists_unknown():
    conn = _SchemaSweepConn(["dbAuth", "dbLog"])
    res = G.sweep_unknown_schema_enum(conn, "mysql-kr-an1-auth", ["dbAuth", "dbGame"], dry_run=True)
    assert res["scanned"] == 2
    assert [u["schema_name"] for u in res["ungrounded"]] == ["dbLog"]  # 실존 dbAuth 제외
    assert res["dict_deleted"] == 0
    assert _dml(conn.captured) == []


def test_schema_sweep_execute_removes_unknown_db():
    conn = _SchemaSweepConn(["dbAuth", "dbLog"], delete_rc=5, update_rc=1)
    res = G.sweep_unknown_schema_enum(conn, "mysql-kr-an1-auth", ["dbauth"], dry_run=False)  # 대소문자 무시
    assert [u["schema_name"] for u in res["ungrounded"]] == ["dbLog"]
    assert res["dict_deleted"] == 5 and res["feedback_rejected"] == 1
    dml = _dml(conn.captured)
    assert len(dml) == 2
    assert "source='auto'" in dml[0][0]
    assert dml[0][1] == ("mysql-kr-an1-auth", "dbLog")
    assert "status='rejected'" in dml[1][0]
    assert dml[1][1] == ("mysql-kr-an1-auth", "dbLog")


def test_schema_sweep_all_known_no_mutation():
    conn = _SchemaSweepConn(["dbAuth", "dbGame"])
    res = G.sweep_unknown_schema_enum(conn, "mysql-kr-an1-auth", ["dbAuth", "dbGame"], dry_run=False)
    assert res["ungrounded"] == [] and res["dict_deleted"] == 0
    assert _dml(conn.captured) == []


def _deleted_schemas(captured):
    return {p[1][1] for p in _dml(captured) if "DELETE" in " ".join(p[0].split()).upper()}


def test_schema_sweep_confirm_gate_defers_first_seen():
    # catalog-shrink 가드: confirm_lower 에 있는(직전 tick 도 unknown) dbLog 만 삭제, 처음 본 dbTmp 는 보류
    conn = _SchemaSweepConn(["dbAuth", "dbLog", "dbTmp"], delete_rc=1, update_rc=1)
    res = G.sweep_unknown_schema_enum(conn, "s", ["dbAuth"], dry_run=False, confirm_lower={"dblog"})
    assert {u["schema_name"] for u in res["ungrounded"]} == {"dbLog", "dbTmp"}  # 후보 전체 기록
    assert _deleted_schemas(conn.captured) == {"dbLog"}                         # 확인된 것만 삭제


def test_schema_sweep_confirm_none_deletes_all_unknown():
    # confirm_lower=None(게이트 없음, 운영자 경로) → unknown 전체 삭제
    conn = _SchemaSweepConn(["dbAuth", "dbLog", "dbTmp"], delete_rc=1, update_rc=1)
    G.sweep_unknown_schema_enum(conn, "s", ["dbAuth"], dry_run=False, confirm_lower=None)
    assert _deleted_schemas(conn.captured) == {"dbLog", "dbTmp"}


def test_schema_sweep_select_excludes_empty_schema():
    # 빈 schema_name enum(bare-schema)은 조회에서 제외 → 절대 미터치(안전)
    conn = _SchemaSweepConn(["dbLog"])
    G.sweep_unknown_schema_enum(conn, "s", ["dbAuth"], dry_run=True)
    sel = [sql for sql, _ in conn.captured
           if "SELECT DISTINCT SCHEMA_NAME" in " ".join(sql.split()).upper()]
    assert sel and "schema_name <> ''" in sel[0]
