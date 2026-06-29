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
    # 0021: 역할 차원 추가 — UNIQUE(scope_key, role_key, term), role_key 기본 '*'(공용), source 기본 'manual'.
    conn = _FakeConn()
    G.upsert_glossary_term(conn, "ds:sales", "MAU", "월간 활성 사용자")
    sql, params = conn.captured[-1]
    assert "INSERT INTO kb_glossary" in sql
    assert "ON CONFLICT (scope_key, role_key, term)" in sql
    # params: (scope_key, role_key, term, definition, source)
    assert params[1] == "*" and params[2] == "MAU" and params[3] == "월간 활성 사용자"
    assert params[4] == "manual"


def test_upsert_glossary_term_role_scoped_sql():
    # 역할 지정 시 role_key 가 정규화(소문자)되어 들어간다.
    conn = _FakeConn()
    G.upsert_glossary_term(conn, "ds:sales", "리드", "영업 잠재고객", role_key="Sales", source="auto")
    _, params = conn.captured[-1]
    assert params[1] == "sales" and params[2] == "리드" and params[4] == "auto"


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


# ── 0021: 역할 차원 read 격리 ─────────────────────────────────────────────────
def test_role_scoped_read_sql():
    # role_key 지정 시 read SQL 에 role_key = ANY(%s) 추가 + [그 역할, '*'(공용)] 캐스케이드.
    conn = _FakeConn(glossary=[("status", "x")], enums=[])
    G.load_glossary_enum_context("status", scope_key="ds:sales", conn=conn, role_key="Operator")
    gloss_reads = [(sql, p) for (sql, p) in conn.captured
                   if sql.strip().upper().startswith("SELECT") and "kb_glossary" in sql]
    assert gloss_reads, "glossary read SQL 미발생"
    sql, params = gloss_reads[0]
    assert "role_key = ANY(%s)" in sql
    roles = params[1]
    assert "operator" in roles and "*" in roles   # 정규화(소문자) + 공용 캐스케이드


def test_role_none_read_keeps_legacy_sql():
    # role_key 미지정(하위호환) → role 절 없음(기존 SQL 그대로).
    conn = _FakeConn(glossary=[("status", "x")], enums=[])
    G.load_glossary_enum_context("status", scope_key="ds:sales", conn=conn)
    gloss_reads = [sql for (sql, p) in conn.captured
                   if sql.strip().upper().startswith("SELECT") and "kb_glossary" in sql]
    assert gloss_reads and "role_key" not in gloss_reads[0]


# ── 0021: 검토 큐 + 하이브리드 자동승급 ──────────────────────────────────────────
class _ScriptedCursor:
    def __init__(self, state):
        self._state = state
        self.rowcount = state.get("rowcount", 1)

    def execute(self, sql, params=None):
        self._state["captured"].append((sql, params))
        self.rowcount = self._state.get("rowcount", 1)

    def fetchone(self):
        q = self._state["fetchone_queue"]
        return q.pop(0) if q else None

    def fetchall(self):
        return self._state.get("rows", [])

    def close(self):
        pass


class _ScriptedConn:
    def __init__(self, fetchone_queue=None, rowcount=1):
        self.state = {"captured": [], "fetchone_queue": list(fetchone_queue or []), "rowcount": rowcount}

    def cursor(self):
        return _ScriptedCursor(self.state)

    @property
    def captured(self):
        return self.state["captured"]


def test_record_glossary_suggestion_sql():
    conn = _ScriptedConn(rowcount=1)
    ok = G.record_glossary_suggestion(conn, "common", "*", "리드", "영업 잠재고객", confidence=0.6)
    assert ok is True
    sql, params = conn.captured[-1]
    assert "INSERT INTO glossary_feedback" in sql
    assert "ON CONFLICT (scope_key, role_key, term)" in sql
    # 거부/승급된 행은 재제안돼도 되살아나지 않는다(WHERE pending).
    assert "WHERE glossary_feedback.status = 'pending'" in sql
    assert "pending" in params   # status 파라미터


def test_auto_promote_high_confidence_registers():
    # confidence ≥ threshold → kb_glossary 자동 등록(source='auto') + glossary_feedback(auto_promoted).
    # fetchone_queue: [_feedback_status=None(신규), _insert_glossary_auto RETURNING=(123,)].
    conn = _ScriptedConn(fetchone_queue=[None, (123,)], rowcount=1)
    res = G.auto_promote_or_queue(conn, "common", "리드", "영업 잠재고객",
                                  confidence=0.95, threshold=0.85)
    assert res == "auto_promoted"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" in joined and "'auto'" in joined
    fb = [(sql, p) for (sql, p) in conn.captured if "glossary_feedback" in sql and "INSERT" in sql]
    assert fb and "auto_promoted" in fb[-1][1]


def test_auto_promote_low_confidence_queues_pending():
    conn = _ScriptedConn(rowcount=1)   # _feedback_status fetchone → None(신규)
    res = G.auto_promote_or_queue(conn, "common", "모호용어", "불확실 정의",
                                  confidence=0.4, threshold=0.85)
    assert res == "pending"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" not in joined   # 라이브 미반영
    assert "INSERT INTO glossary_feedback" in joined


def test_auto_promote_skips_rejected_term():
    # REV-20260629 BLOCKER 회귀: 과거 거부된 용어가 고신뢰로 재추론돼도 라이브 kb_glossary 에
    # 재유입되면 안 된다(poisoning 방어). _feedback_status='rejected' → kb_glossary INSERT 미발생.
    conn = _ScriptedConn(fetchone_queue=[("rejected",)], rowcount=1)
    res = G.auto_promote_or_queue(conn, "common", "거부된용어", "재유입 시도 정의",
                                  confidence=0.99, threshold=0.85)
    assert res == "skipped"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" not in joined        # 라이브 재유입 차단
    assert "INSERT INTO glossary_feedback" not in joined  # 큐 재적재도 안 함


def test_auto_promote_skips_already_promoted():
    # 이미 등록(promoted/auto_promoted)된 용어는 중복 자동 INSERT 안 함.
    conn = _ScriptedConn(fetchone_queue=[("auto_promoted",)], rowcount=1)
    res = G.auto_promote_or_queue(conn, "common", "기존용어", "정의",
                                  confidence=0.99, threshold=0.85)
    assert res == "skipped"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" not in joined


def test_reject_auto_promoted_reverts_live_term():
    # auto_promoted 거부 → 자동 추가된 source='auto' 행 회수 + status='rejected'.
    conn = _ScriptedConn(fetchone_queue=[("auto_promoted", 55)], rowcount=1)
    G.reject_glossary_feedback(conn, 7)
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "DELETE FROM kb_glossary" in joined and "source = 'auto'" in joined
    assert "status='rejected'" in joined


def test_reject_pending_no_live_delete():
    conn = _ScriptedConn(fetchone_queue=[("pending", None)], rowcount=1)
    G.reject_glossary_feedback(conn, 9)
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "DELETE FROM kb_glossary" not in joined
    assert "status='rejected'" in joined


def test_promote_glossary_feedback_inserts_and_marks():
    # pending → kb_glossary upsert(source='manual') + feedback status='promoted'.
    conn = _ScriptedConn(fetchone_queue=[("common", "*", "리드", "정의"), (321,)], rowcount=1)
    gid = G.promote_glossary_feedback(conn, 3, approved_by="curator")
    assert gid == 321
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" in joined and "'manual'" in joined
    assert "status='promoted'" in joined


# ── 0021: 유사어 관계 ────────────────────────────────────────────────────────
def test_add_glossary_relation_sql():
    conn = _ScriptedConn(rowcount=1)
    G.add_glossary_relation(conn, 1, 2, "synonym", created_by="curator")
    sql, params = conn.captured[-1]
    assert "INSERT INTO glossary_relations" in sql
    assert "ON CONFLICT (from_id, to_id, relation_type) DO NOTHING" in sql
    assert params[0] == 1 and params[1] == 2 and params[2] == "synonym"
