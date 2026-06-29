"""ITEM-02+03 PR-A — 샘플쿼리 저장소 + 피드백 flywheel 코어 단위 테스트.

LLM·라이브DB 무관: FakeConn 으로 등록/검색(approved∧active∧ds-scope∧weight)/주입/PII 마스킹/
승급/거부/신선도(validate_sample_sql)를 검증. 임베딩은 mock. 측정(A/B)은 별도(harness).
"""
from modules import sample_queries as SQ
from modules import sample_feedback as SF


# ── 라우팅 FakeConn ──────────────────────────────────────────────────────────
class _FakeCursor:
    def __init__(self, state):
        self.state = state
        self._mode = None  # 'one' | 'many'

    def execute(self, sql, params=None):
        self.state["captured"].append((sql, params))
        self._mode = None
        if "FROM sample_queries" in sql and "<=>" in sql:
            self._mode = ("many", self.state.get("search_rows", []))
        elif "SELECT scope_key, nl_question, generated_sql, vote FROM sample_feedback" in sql:
            self._mode = ("one", self.state.get("feedback_row"))
        elif "SELECT id FROM sample_queries WHERE scope_key" in sql:
            self._mode = ("one", self.state.get("sample_id_row"))
        elif "FROM sample_feedback WHERE status = 'pending'" in sql:
            self._mode = ("many", self.state.get("pending_rows", []))

    def fetchone(self):
        return self._mode[1] if self._mode and self._mode[0] == "one" else None

    def fetchall(self):
        return list(self._mode[1]) if self._mode and self._mode[0] == "many" else []

    def close(self):
        pass


class _FakeConn:
    def __init__(self, **state):
        self.state = {"captured": [], **state}

    def cursor(self):
        return _FakeCursor(self.state)

    @property
    def captured(self):
        return self.state["captured"]


# ── sample_queries: 등록/검색/주입 ───────────────────────────────────────────
def test_register_sample_upsert_with_explicit_embedding():
    conn = _FakeConn()
    SQ.register_sample(conn, "ds:sales", "활성 고객 수?", "SELECT count(*) FROM c WHERE active=1",
                       domain="customers", approved=True, embedding=[0.1] * 4)
    sql, params = conn.captured[-1]
    assert "INSERT INTO sample_queries" in sql
    assert "ON CONFLICT (scope_key, nl_question)" in sql
    assert params[1] == "활성 고객 수?" and params[7] is True  # approved


def test_search_samples_sql_approved_active_scoped_weighted():
    conn = _FakeConn(search_rows=[("q", "SELECT 1", "d", 100, 0.9)])
    SQ.search_samples(conn, [0.1, 0.2], "ds:sales", top_k=3)
    sql, params = conn.captured[-1]
    assert "approved = true" in sql and "status = 'active'" in sql
    assert "scope_key = ANY(%(scopes)s)" in sql
    assert "* (weight / 100.0)" in sql            # weight 가중 랭킹
    assert "common" in params["scopes"]           # ds 캐스케이드
    assert params["k"] == 3


def test_load_example_context_injects_examples(monkeypatch):
    monkeypatch.setattr(SQ, "_embed", lambda t, **k: [0.1] * 4)
    conn = _FakeConn(search_rows=[
        ("활성 고객 수?", "SELECT count(*) FROM customers WHERE is_active=1", "customers", 100, 0.95),
    ])
    out = SQ.load_example_queries_context("활성 고객이 몇 명이야", scope_key="ds:sales", conn=conn)
    assert "-- Q: 활성 고객 수?" in out
    assert "SELECT count(*) FROM customers WHERE is_active=1" in out


def test_load_example_context_empty_when_embed_fails(monkeypatch):
    monkeypatch.setattr(SQ, "_embed", lambda t, **k: None)  # 임베딩 미가용
    conn = _FakeConn(search_rows=[("q", "SELECT 1", "d", 100, 0.9)])
    assert SQ.load_example_queries_context("질문", scope_key="ds:sales", conn=conn) == ""


def test_load_example_context_empty_no_rows(monkeypatch):
    monkeypatch.setattr(SQ, "_embed", lambda t, **k: [0.1] * 4)
    conn = _FakeConn(search_rows=[])
    assert SQ.load_example_queries_context("질문", scope_key="ds:sales", conn=conn) == ""


# ── 신선도 validate_sample_sql ──────────────────────────────────────────────
def test_validate_sample_sql_active_for_readonly():
    assert SQ.validate_sample_sql("SELECT * FROM t")[0] == "active"


def test_validate_sample_sql_retired_for_non_readonly():
    assert SQ.validate_sample_sql("DELETE FROM t")[0] == "retired"


def test_validate_sample_sql_stale_when_explain_fails():
    def boom(sql):
        raise RuntimeError("Unknown column 'x'")
    status, reason = SQ.validate_sample_sql("SELECT x FROM t", explain_fn=boom)
    assert status == "stale" and "Unknown column" in reason


# ── sample_feedback: record(PII)/promote/reject ─────────────────────────────
def test_record_feedback_masks_pii():
    conn = _FakeConn()
    SF.record_feedback(conn, "ds:sales", "이 고객 정보?",
                       "SELECT * FROM users WHERE email='alice@example.com'",
                       vote="up", suggested=True, created_by="curator1", message_id=999)
    sql, params = conn.captured[-1]
    assert "INSERT INTO sample_feedback" in sql
    # 답변당 사용자별 고유 피드백(👍/👎) — (created_by, message_id) UPSERT(마이그 0021).
    assert "ON CONFLICT (created_by, message_id)" in sql
    # 컬럼 순서: scope_key, conversation_id, message_id, run_id, nl_question, generated_sql, vote, suggested, created_by
    masked_sql = params[5]
    assert "alice@example.com" not in masked_sql   # PII 마스킹됨
    assert params[2] == 999                          # message_id
    assert params[6] == "up" and params[7] is True   # vote, suggested


def test_record_feedback_vote_upsert_keys_user_and_message():
    """투표(suggested=false)는 (created_by, message_id) 부분 UNIQUE 로 답변당 1행 — UPSERT 갱신."""
    conn = _FakeConn()
    SF.record_feedback(conn, "ds:sales", "활성 고객?", "SELECT 1",
                       vote="down", suggested=False, created_by="userA", message_id=12)
    sql, params = conn.captured[-1]
    assert "ON CONFLICT (created_by, message_id)" in sql
    assert "suggested = false" in sql                 # 부분 인덱스 술어(투표만 대상)
    assert "DO UPDATE SET" in sql and "RETURNING id" in sql
    assert params[2] == 12 and params[6] == "down" and params[7] is False


def test_promote_feedback_creates_approved_sample(monkeypatch):
    conn = _FakeConn(
        feedback_row=("ds:sales", "활성 고객 수?", "SELECT count(*) FROM customers WHERE is_active=1", "up"),
        sample_id_row=(42,),
    )
    sid = SF.promote_feedback(conn, 7, approved_by="curator1", embedding=[0.1] * 4)
    assert sid == 42
    caps = " || ".join(s for s, _ in conn.captured)
    assert "INSERT INTO sample_queries" in caps             # 승급 = approved 샘플 생성
    assert "status = 'promoted'" in caps                    # 피드백 promoted 표기


def test_promote_downvote_not_promoted():
    conn = _FakeConn(feedback_row=("ds:sales", "q", "SELECT 1", "down"))
    assert SF.promote_feedback(conn, 7, embedding=[0.1] * 4) is None


def test_reject_feedback_marks_rejected():
    conn = _FakeConn()
    SF.reject_feedback(conn, 7)
    sql, _ = conn.captured[-1]
    assert "status = 'rejected'" in sql
