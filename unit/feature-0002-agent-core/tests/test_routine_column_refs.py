"""feature-0016 routine-column-edges (2026-07-28) 단위 테스트 — 함수/프로시저 **참조 컬럼** 추출·투영.

사용자 요청: 그래프 뷰에서 테이블 노드가 펼쳐졌을 때 사용 관계선이 테이블이 아니라 실제
[읽기/쓰기] 참조하는 **컬럼**에 붙어야 한다. 그 입력이 되는 계약을 잠근다.

  A. 보수적 채택 — alias 수식 참조(read) · INSERT 컬럼리스트(write) · UPDATE SET 좌변(write) 만.
     비수식 컬럼은 추정하지 않고, 실재하지 않는 컬럼은 폐기하며, 모호 alias 는 통째로 버린다.
  B. SSOT 통합 — referenced_tables entry 에 `cols` 동봉(기존 fqn/kind/cross 계약 무회귀).
  C. 그래프 투영 — ROUTINE_USES 엣지 속성 `ref_columns`(JSON) + 조회 응답 정제(_ref_columns_of).
"""
import json

from modules import routines as rt
from modules import metadata_graph as mg


TABLES = ["T_User", "T_Order", "T_Log"]
COLS = {
    "t_user": {"userid": "UserID", "name": "Name", "point": "Point"},
    "t_order": {"orderid": "OrderID", "userid": "UserID", "amount": "Amount"},
    "t_log": {"logid": "LogID", "msg": "Msg"},
}


def _parse(body, tables=None, cols=None, label="dbo"):
    refs = rt.parse_referenced_tables(body, tables if tables is not None else TABLES,
                                      local_label=label)
    return refs, rt.parse_referenced_columns(body, refs, cols if cols is not None else COLS)


# ── A. 보수적 채택 규칙 ──────────────────────────────────────────────────────
def test_alias_qualified_columns_are_read():
    body = ("SELECT u.UserID, u.Name FROM [dbo].[T_User] u "
            "JOIN T_Order AS o ON o.UserID = u.UserID WHERE u.Point > 0")
    _, cols = _parse(body)
    assert cols["t_user"] == [{"n": "Name", "k": "read"},
                              {"n": "Point", "k": "read"},
                              {"n": "UserID", "k": "read"}]
    assert cols["t_order"] == [{"n": "UserID", "k": "read"}]


def test_table_name_qualifier_without_alias():
    """`T_User.UserID` 처럼 테이블명으로 직접 수식한 참조도 자기참조 alias 로 해소된다."""
    body = "SELECT T_User.UserID FROM T_User"
    _, cols = _parse(body)
    assert cols == {"t_user": [{"n": "UserID", "k": "read"}]}


def test_insert_column_list_is_write():
    body = "INSERT INTO T_Log (LogID, Msg) VALUES (1, 2)"
    _, cols = _parse(body)
    assert cols == {"t_log": [{"n": "LogID", "k": "write"}, {"n": "Msg", "k": "write"}]}


def test_insert_select_subquery_paren_not_treated_as_column_list():
    """`INSERT INTO T (SELECT …)` 의 괄호는 컬럼 리스트가 아니다 — 오채택 금지."""
    body = "INSERT INTO T_Log (SELECT LogID FROM T_Log)"
    _, cols = _parse(body)
    assert "t_log" not in cols or all(c["k"] != "write" for c in cols.get("t_log", []))


def test_update_set_lhs_is_write():
    body = "UPDATE T_User SET Point = Point + 1, Name = 0 WHERE UserID = 1"
    _, cols = _parse(body)
    by = {c["n"]: c["k"] for c in cols["t_user"]}
    assert by["Point"] == "write" and by["Name"] == "write"
    # WHERE 절의 비수식 UserID 는 추정하지 않는다(보수적 채택).
    assert "UserID" not in by


def test_alias_update_set_lhs_resolves_through_alias():
    body = "UPDATE u SET u.Point = 1 FROM T_User u WHERE u.UserID = 3"
    _, cols = _parse(body)
    by = {c["n"]: c["k"] for c in cols["t_user"]}
    assert by["Point"] == "write"
    assert by["UserID"] == "read"      # 조건절 수식 참조는 read


def test_write_wins_over_read_for_same_column():
    body = "SELECT u.Point FROM T_User u; UPDATE T_User SET Point = 2;"
    _, cols = _parse(body)
    assert cols["t_user"] == [{"n": "Point", "k": "write"}]


def test_unqualified_columns_are_not_guessed():
    """비수식 컬럼은 다중 테이블 구문에서 오귀속하므로 아예 채택하지 않는다(사용자 결정)."""
    body = "SELECT UserID, Amount FROM T_User, T_Order"
    _, cols = _parse(body)
    assert cols == {}


def test_nonexistent_column_dropped():
    body = "SELECT u.NoSuchColumn FROM T_User u"
    _, cols = _parse(body)
    assert cols == {}


def test_ambiguous_alias_dropped_entirely():
    """같은 alias 가 서로 다른 테이블에 바인딩되면 그 alias 참조는 전부 폐기(오귀속 차단)."""
    body = ("SELECT a.UserID FROM T_User a; "
            "SELECT a.Amount FROM T_Order a;")
    _, cols = _parse(body)
    assert cols == {}


def test_schema_qualifier_is_not_an_alias():
    """`dbo.T_User` 의 `dbo` 는 alias 가 아니므로 컬럼 참조로 오인되지 않는다."""
    body = "SELECT * FROM dbo.T_User"
    _, cols = _parse(body)
    assert cols == {}


def test_comment_bodies_ignored():
    body = "-- SELECT u.Point FROM T_User u\n/* u.Name */\nSELECT u.UserID FROM T_User u"
    _, cols = _parse(body)
    assert cols == {"t_user": [{"n": "UserID", "k": "read"}]}


def test_cross_db_refs_excluded_from_column_promotion():
    """크로스-DB 참조는 현재 연결로 컬럼 실재를 검증할 수 없어 테이블 단위 유지."""
    ext = {("otherdb", "t_user"): ("otherdb", "T_User")}
    body = "SELECT x.UserID FROM [otherdb].[dbo].[T_User] x"
    refs = rt.parse_referenced_tables(body, TABLES, external_tables=ext, local_label="dbo")
    assert refs and refs[0].get("schema") == "otherdb"
    assert rt.parse_referenced_columns(body, refs, COLS) == {}


def test_column_cap_is_guard_not_truncation():
    """graph-cap-audit(사용자 결정 2026-07-29): 참조 컬럼 상한은 **비현실 극단 전용 안전 가드**다.

    종전 계약은 `len == _COLS_CAP_PER_TABLE`(24) 로 **실사용 규모에서 잘리는 것**을 고정하고 있었다.
    개수를 줄여 출력하는 것은 최적화가 아니라 데이터 누락(오류)이므로, 실사용 규모(200 컬럼)는 전량
    통과해야 하고 가드는 그보다 훨씬 위에서만 작동해야 한다.
    """
    many = {f"c{i:03d}": f"C{i:03d}" for i in range(200)}
    cols_map = {"t_user": many}
    body = "SELECT " + ", ".join(f"u.C{i:03d}" for i in range(200)) + " FROM T_User u"
    _, cols = _parse(body, cols=cols_map)
    assert len(cols["t_user"]) == 200, "실사용 규모(200)는 잘리지 않아야 한다"
    assert rt._COLS_CAP_PER_TABLE >= 2000, "가드는 실사용 최대치보다 충분히 커야 한다"
    # 결정적 — 같은 입력이면 같은 결과
    _, again = _parse(body, cols=cols_map)
    assert cols == again


def test_column_guard_still_bounds_pathological_input():
    """가드 자체는 살아 있다 — 손상 메타데이터·무한 생성 방어(전량 원칙의 backstop)."""
    n = rt._COLS_CAP_PER_TABLE + 50
    many = {f"c{i:05d}": f"C{i:05d}" for i in range(n)}
    body = "SELECT " + ", ".join(f"u.C{i:05d}" for i in range(n)) + " FROM T_User u"
    _, cols = _parse(body, cols={"t_user": many})
    assert len(cols["t_user"]) == rt._COLS_CAP_PER_TABLE


def test_empty_inputs_are_noop():
    assert rt.parse_referenced_columns("", [{"fqn": "T_User", "kind": "read"}], COLS) == {}
    assert rt.parse_referenced_columns("SELECT 1", [], COLS) == {}
    assert rt.parse_referenced_columns("SELECT 1", [{"fqn": "T_User", "kind": "read"}], {}) == {}


# ── B. 컬럼 인벤토리 조회 ────────────────────────────────────────────────────
class _FakeCur:
    def __init__(self, rows, sink):
        self._rows = rows
        self._sink = sink

    def execute(self, sql, params=None):
        self._sink.append((sql, params))

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def cursor(self):
        return _FakeCur(self.rows, self.executed)


def test_fetch_columns_only_queries_wanted_tables():
    conn = _FakeConn([("T_User", "UserID"), ("T_User", "Point"), ("T_Order", "Amount")])
    out = rt._fetch_columns(conn, "dbo", {"T_User", "T_Order"})
    assert out == {"t_user": {"userid": "UserID", "point": "Point"},
                   "t_order": {"amount": "Amount"}}
    sql, params = conn.executed[0]
    assert "information_schema.COLUMNS" in sql and "TABLE_NAME IN (" in sql
    assert params[0] == "dbo" and set(params[1:]) == {"T_User", "T_Order"}


def test_fetch_columns_batches_repeat_to_cover_all_tables():
    """graph-cap-audit: `IN` 절 크기는 **배치 크기**이지 상한이 아니다 — 배치를 반복해 전량 조회한다.

    종전에는 `names[:_COLUMNS_TABLE_CAP]` 로 목록을 잘라, 400개를 넘는 참조 테이블의 컬럼 승격이
    조용히 누락됐다(사용 관계선이 테이블-레벨로 폴백). 배치 수와 파라미터 합집합으로 전량 커버를 잠근다.
    """
    n = rt._COLUMNS_TABLE_BATCH * 2 + 7
    wanted = {f"T{i:05d}" for i in range(n)}
    conn = _FakeConn([])
    rt._fetch_columns(conn, "dbo", wanted)
    assert len(conn.executed) == 3, f"배치 3회여야 한다(실제 {len(conn.executed)})"
    seen = set()
    for sql, params in conn.executed:
        assert params[0] == "dbo"
        seen.update(params[1:])
    assert seen == wanted, "모든 테이블이 어느 배치엔가 포함돼야 한다(절단 0)"


def test_fetch_columns_batch_failure_is_isolated():
    """한 배치가 실패해도 나머지 배치는 계속한다 — 부분 결과가 전무보다 낫다."""
    class _FlakyCur(_FakeCur):
        def execute(self, sql, params=None):
            self._sink.append((sql, params))
            if len(self._sink) == 1:
                raise RuntimeError("boom")

    class _FlakyConn(_FakeConn):
        def cursor(self):
            return _FlakyCur(self.rows, self.executed)

    n = rt._COLUMNS_TABLE_BATCH + 1
    conn = _FlakyConn([("T_User", "UserID")])
    out = rt._fetch_columns(conn, "dbo", {f"T{i:05d}" for i in range(n)})
    assert len(conn.executed) == 2, "첫 배치 실패가 두 번째 배치를 막지 않아야 한다"
    assert out == {"t_user": {"userid": "UserID"}}


def test_fetch_columns_empty_wanted_is_noop():
    conn = _FakeConn([])
    assert rt._fetch_columns(conn, "dbo", set()) == {}
    assert conn.executed == []      # 조회 자체를 하지 않는다(비용 통제)


def test_fetch_columns_failure_is_nonblocking():
    class _Boom(_FakeConn):
        def cursor(self):
            raise RuntimeError("no such table")

    assert rt._fetch_columns(_Boom([]), "dbo", {"T_User"}) == {}


# ── C. 그래프 투영 ───────────────────────────────────────────────────────────
class _CypherCur:
    """_cypher 가 실행하는 SQL 을 수집하는 최소 스텁(test_graph_funcproc_uxfix 동형)."""

    def __init__(self):
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return [(None,)]

    def close(self):
        pass


def _sync_sql(refs):
    cur = _CypherCur()
    mg.sync_routine(cur, "ds1", "dbo", "sp_Test", "procedure", "", refs)
    return "\n".join(str(s) for s, _ in cur.executed)


def test_sync_routine_projects_ref_columns_property():
    joined = _sync_sql([{"fqn": "dbo.T_User", "kind": "write",
                         "cols": [{"n": "UserID", "k": "read"}, {"n": "Point", "k": "write"}]}])
    assert ":ROUTINE_USES" in joined and "ref_columns" in joined
    assert "UserID" in joined and "Point" in joined


def test_sync_routine_without_cols_omits_property():
    joined = _sync_sql([{"fqn": "dbo.T_User", "kind": "read"}])
    assert ":ROUTINE_USES" in joined
    assert "ref_columns" not in joined      # 속성 자체가 없어야 기존 엣지와 byte 동치(무회귀)


def test_ref_columns_prop_is_whitelisted():
    """_PROP_KEYS 화이트리스트에 없으면 _props_set 이 조용히 버린다 — 등재 회귀 잠금."""
    assert "ref_columns" in mg._PROP_KEYS


def test_ref_columns_of_parses_and_sanitizes():
    raw = json.dumps([{"n": "UserID", "k": "read"}, {"n": "Point", "k": "write"},
                      {"n": "", "k": "read"}, {"k": "read"}, "junk", {"n": "X", "k": "bogus"}])
    assert mg._ref_columns_of(raw) == [{"n": "UserID", "k": "read"},
                                       {"n": "Point", "k": "write"},
                                       {"n": "X", "k": "read"}]   # 미상 kind 는 read 로 폴백


def test_ref_columns_of_defends_against_garbage():
    for bad in (None, "", "not json", "{}", "[1,2]", 42):
        assert mg._ref_columns_of(bad) == []


# ── D. refs 서명 — cols 가 빠지면 기능이 조용히 죽는다 (perf-cyvol 상호작용) ─────
def test_refs_signature_includes_cols():
    """`sync_routine` 은 서명이 같으면 ROUTINE_USES 재작성을 통째로 생략한다(cyvol 최적화).
    참조 컬럼은 엣지 속성(`ref_columns`)이 되므로 **서명에 포함되어야** 한다 — 빠지면 참조
    테이블이 그대로인 기존 routine 전량이 생략에 걸려 `ref_columns` 가 영영 투영되지 않는다."""
    base = [{"fqn": "dbo.T_User", "kind": "read"}]
    with_cols = [{"fqn": "dbo.T_User", "kind": "read", "cols": [{"n": "UserID", "k": "read"}]}]
    assert mg.routine_refs_signature(base) != mg.routine_refs_signature(with_cols)


def test_refs_signature_sensitive_to_column_kind_and_set():
    a = [{"fqn": "dbo.T_User", "kind": "write", "cols": [{"n": "Point", "k": "read"}]}]
    b = [{"fqn": "dbo.T_User", "kind": "write", "cols": [{"n": "Point", "k": "write"}]}]
    c = [{"fqn": "dbo.T_User", "kind": "write",
          "cols": [{"n": "Point", "k": "write"}, {"n": "Name", "k": "write"}]}]
    assert len({mg.routine_refs_signature(x) for x in (a, b, c)}) == 3


def test_refs_signature_stable_under_column_order():
    a = [{"fqn": "dbo.T_User", "kind": "read",
          "cols": [{"n": "UserID", "k": "read"}, {"n": "Point", "k": "write"}]}]
    b = [{"fqn": "dbo.T_User", "kind": "read",
          "cols": [{"n": "Point", "k": "write"}, {"n": "UserID", "k": "read"}]}]
    assert mg.routine_refs_signature(a) == mg.routine_refs_signature(b)   # 정렬 정규화


def test_refs_signature_tolerates_garbage_cols():
    for bad in ("junk", {"n": "x"}, [1, 2], None, [{"k": "read"}]):
        mg.routine_refs_signature([{"fqn": "dbo.T", "kind": "read", "cols": bad}])   # raise 금지
