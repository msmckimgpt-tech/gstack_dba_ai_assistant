"""ITEM-10 — 용어사전(kb_glossary) + ENUM 코드사전(enum_dictionary) 단위 테스트.

LLM·라이브DB 무관: FakeConn 으로 upsert SQL·ds-scoped read·질문 매칭·프롬프트 조립 검증.
측정(ENUM 정확도 수치)은 bedrock-auth 복구 후 ITEM-01 harness 로(별도).
"""
from modules import kb_glossary as G


class _FakeCursor:
    def __init__(self, state):
        self._state = state
        self._rows = []

    def execute(self, sql, params=None):
        self._state["captured"].append((sql, params))
        if "kb_glossary" in sql and sql.strip().upper().startswith("SELECT"):
            self._rows = self._state["glossary"]
        elif "enum_dictionary" in sql and sql.strip().upper().startswith("SELECT"):
            self._rows = self._state["enums"]
        else:
            self._rows = []

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, glossary=(), enums=()):
        self.state = {"captured": [], "glossary": list(glossary), "enums": list(enums)}

    def cursor(self):
        return _FakeCursor(self.state)

    @property
    def captured(self):
        return self.state["captured"]


# ── upsert SQL ──────────────────────────────────────────────────────────────
def test_upsert_glossary_term_sql():
    conn = _FakeConn()
    G.upsert_glossary_term(conn, "ds:sales", "MAU", "월간 활성 사용자")
    sql, params = conn.captured[-1]
    assert "INSERT INTO kb_glossary" in sql
    assert "ON CONFLICT (scope_key, term)" in sql
    assert params[1] == "MAU" and params[2] == "월간 활성 사용자"


def test_upsert_enum_entry_sql():
    conn = _FakeConn()
    G.upsert_enum_entry(conn, "ds:sales", "orders", "status", "P", "결제대기", schema_name="public")
    sql, params = conn.captured[-1]
    assert "INSERT INTO enum_dictionary" in sql
    assert "ON CONFLICT (scope_key, schema_name, table_name, column_name, code)" in sql
    assert params[2] == "orders" and params[3] == "status" and params[4] == "P" and params[5] == "결제대기"


# ── ds-scoped read + 매칭 + 조립 ─────────────────────────────────────────────
def test_load_injects_matched_term_and_enum():
    conn = _FakeConn(
        glossary=[("status", "주문 처리 상태")],
        enums=[("orders", "status", "P", "결제대기"), ("orders", "status", "D", "배송완료")],
    )
    out = G.load_glossary_enum_context("최근 status 별 주문 건수", scope_key="ds:sales", conn=conn)
    assert "용어:" in out and "status: 주문 처리 상태" in out
    assert "ENUM 코드" in out
    assert "orders.status:" in out
    assert "P=결제대기" in out and "D=배송완료" in out


def test_read_sql_is_ds_scoped():
    conn = _FakeConn(glossary=[("status", "x")], enums=[])
    G.load_glossary_enum_context("status", scope_key="ds:sales", conn=conn)
    # 두 read SQL 모두 scope_key = ANY(%s) 로 ds 격리. scopes 에 'common' 캐스케이드 포함.
    reads = [(sql, p) for (sql, p) in conn.captured if sql.strip().upper().startswith("SELECT")]
    assert reads, "read SQL 미발생"
    for sql, params in reads:
        assert "scope_key = ANY(%s)" in sql
        assert "common" in params[0]  # _scope_candidates 캐스케이드


def test_non_matching_returns_empty():
    conn = _FakeConn(glossary=[("status", "x")], enums=[("orders", "status", "P", "결제대기")])
    # 질문에 term/column/table 미등장 → 주입 없음.
    assert G.load_glossary_enum_context("오늘 날씨 알려줘", scope_key="ds:sales", conn=conn) == ""


def test_empty_message_returns_empty():
    conn = _FakeConn(glossary=[("status", "x")])
    assert G.load_glossary_enum_context("", scope_key="ds:sales", conn=conn) == ""


def test_enum_matched_by_table_name():
    conn = _FakeConn(glossary=[], enums=[("invoices", "kind", "A", "정기")])
    out = G.load_glossary_enum_context("invoices 테이블 분석", scope_key="ds:fin", conn=conn)
    assert "invoices.kind:" in out and "A=정기" in out


# ── ds 격리 (REV BLOCKER B1 회귀) ────────────────────────────────────────────
def test_scope_excludes_other_datasource():
    from modules.utils import _normalize_scope_key
    conn = _FakeConn(glossary=[("status", "x")], enums=[])
    G.load_glossary_enum_context("status", scope_key="ds:sales", conn=conn)
    reads = [p for (sql, p) in conn.captured if sql.strip().upper().startswith("SELECT")]
    assert reads
    scopes = reads[0][0]
    assert _normalize_scope_key("ds:sales") in scopes       # 활성 ds 포함
    assert "common" in scopes                                # 공용 캐스케이드
    assert _normalize_scope_key("ds:fin") not in scopes      # 타 ds 미요청(격리)


def test_default_scope_derives_from_active_datasource():
    # 운영 경로: scope_key 미지정 → cfg.get_active_datasource() 로 도출(CURRENT_FACT_SCOPE_KEY 아님).
    from shared import config as cfg
    from modules.utils import _normalize_scope_key
    cfg.set_active_datasource("ds_sales")
    try:
        conn = _FakeConn(glossary=[("status", "x")], enums=[])
        G.load_glossary_enum_context("status", conn=conn)  # scope 미지정 = 운영 호출 형태
        reads = [p for (sql, p) in conn.captured if sql.strip().upper().startswith("SELECT")]
        scopes = reads[0][0]
        assert _normalize_scope_key("ds_sales") in scopes   # 활성 ds 가 scope 에 반영
        assert scopes != ["common", ""]                      # 'common' 만으로 폴백되지 않음(B1 회귀)
    finally:
        cfg.set_active_datasource(None)
