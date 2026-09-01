"""ENUM 코드사전 대화 자율수집 큐(0039) — 코어 로직 단위 테스트 (용어사전 0021 대칭).

LLM·라이브DB 무관: _ScriptedConn 으로 fetchone 시퀀스를 스크립팅해 record/auto_promote/promote/
reject 의 SQL·분기(하이브리드 자동승급·poisoning 방어·되돌리기)를 검증한다. test_kb_glossary_enum.py
의 용어사전 코어 테스트와 동형(대상 테이블만 enum_feedback/enum_dictionary).
"""
import sys
import types

from modules import kb_glossary as G


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


# ── source 컬럼(0039) — upsert_enum_entry 가 source 를 쓴다 ────────────────────
def test_upsert_enum_entry_writes_source():
    conn = _ScriptedConn(rowcount=1)
    G.upsert_enum_entry(conn, "ds:sales", "orders", "status", "P", "결제대기",
                        schema_name="public", source="auto")
    sql, params = conn.captured[-1]
    assert "INSERT INTO enum_dictionary" in sql
    assert "source" in sql and "source = EXCLUDED.source" in sql
    # params: (scope, schema, table, column, code, label, source)
    assert params[2] == "orders" and params[4] == "P" and params[6] == "auto"


# ── record_enum_suggestion ────────────────────────────────────────────────────
def test_record_enum_suggestion_sql():
    conn = _ScriptedConn(rowcount=1)
    ok = G.record_enum_suggestion(conn, "common", "", "orders", "status", "P", "결제대기", confidence=0.6)
    assert ok is True
    sql, params = conn.captured[-1]
    assert "INSERT INTO enum_feedback" in sql
    assert "ON CONFLICT (scope_key, schema_name, table_name, column_name, code)" in sql
    # 거부/승급된 행은 재제안돼도 되살아나지 않는다(WHERE pending).
    assert "WHERE enum_feedback.status = 'pending'" in sql
    assert "pending" in params


# ── auto_promote_or_queue_enum — 하이브리드 자동승급 ───────────────────────────
def test_enum_auto_promote_high_confidence_registers():
    # confidence ≥ threshold → enum_dictionary 자동 등록(source='auto') + enum_feedback(auto_promoted).
    # fetchone_queue: [_enum_feedback_status=None(신규), _insert_enum_auto RETURNING=(123,)].
    conn = _ScriptedConn(fetchone_queue=[None, (123,)], rowcount=1)
    res = G.auto_promote_or_queue_enum(conn, "common", "", "orders", "status", "P", "결제대기",
                                       confidence=0.95, threshold=0.9)
    assert res == "auto_promoted"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO enum_dictionary" in joined and "'auto'" in joined
    fb = [(sql, p) for (sql, p) in conn.captured if "enum_feedback" in sql and "INSERT" in sql]
    assert fb and "auto_promoted" in fb[-1][1]


def test_enum_auto_promote_low_confidence_queues_pending():
    conn = _ScriptedConn(rowcount=1)   # _enum_feedback_status fetchone → None(신규)
    res = G.auto_promote_or_queue_enum(conn, "common", "", "orders", "flag", "9", "불명",
                                       confidence=0.4, threshold=0.9)
    assert res == "pending"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO enum_dictionary" not in joined   # 라이브 미반영
    assert "INSERT INTO enum_feedback" in joined


def test_enum_auto_promote_skips_rejected():
    # poisoning 방어 회귀: 과거 거부된 코드가 고신뢰로 재추론돼도 enum_dictionary 재유입 금지.
    # 2026-09-01: 판정 조회가 `(status, scope_key)` 를 돌려준다(어느 scope 의 판정인지 로그에 남긴다).
    conn = _ScriptedConn(fetchone_queue=[("rejected", "common")], rowcount=1)
    res = G.auto_promote_or_queue_enum(conn, "common", "", "orders", "status", "X", "재유입",
                                       confidence=0.99, threshold=0.9)
    assert res == "skipped"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO enum_dictionary" not in joined
    assert "INSERT INTO enum_feedback" not in joined


def test_enum_auto_promote_skips_already_promoted():
    conn = _ScriptedConn(fetchone_queue=[("auto_promoted", "common")], rowcount=1)
    res = G.auto_promote_or_queue_enum(conn, "common", "", "orders", "status", "P", "결제대기",
                                       confidence=0.99, threshold=0.9)
    assert res == "skipped"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO enum_dictionary" not in joined


def test_enum_auto_promote_honors_verdict_from_another_scope():
    """제품 A 에서 거부된 코드가 제품 B 의 자율수집으로 되살아나지 않는다.

    ⚠ `_ScriptedConn` 은 SQL 과 무관하게 큐의 다음 값을 돌려준다 — 그래서 "skipped 가 나왔다"
      만으로는 **교차 scope 를 실제로 조회했는지** 증명되지 않는다(scope 를 좁힌 뮤턴트도 통과).
      조회에 실린 scope 목록 자체를 검사한다.
    """
    conn = _ScriptedConn(fetchone_queue=[("rejected", "product.a")], rowcount=1)
    res = G.auto_promote_or_queue_enum(conn, "product.b", "dbSales", "orders", "status", "X",
                                       "재유입", confidence=0.99, threshold=0.9)
    assert res == "skipped"
    sql, params = conn.captured[0]
    assert "FROM enum_feedback" in sql and "scope_key = ANY(" in sql
    scopes = params[0]
    assert "product.b" in scopes and G.GLOBAL_SCOPE in scopes, (
        f"판정 조회가 자기 scope 에 갇혀 있다: {scopes}")
    assert len(scopes) == len(set(scopes)), f"scope 목록에 중복이 있다: {scopes}"


def test_enum_auto_promote_skips_incomplete_key():
    # table/column/code/label 중 하나라도 비면 skipped(추론 잡음 방어).
    conn = _ScriptedConn(rowcount=1)
    res = G.auto_promote_or_queue_enum(conn, "common", "", "orders", "", "P", "결제대기",
                                       confidence=0.99, threshold=0.9)
    assert res == "skipped"
    assert conn.captured == []   # SQL 자체를 실행하지 않음


# ── reject_enum_feedback — 되돌리기 ────────────────────────────────────────────
def test_reject_enum_auto_promoted_reverts_live():
    conn = _ScriptedConn(fetchone_queue=[("auto_promoted", 55)], rowcount=1)
    G.reject_enum_feedback(conn, 7)
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "DELETE FROM enum_dictionary" in joined and "source = 'auto'" in joined
    assert "status='rejected'" in joined


def test_reject_enum_pending_no_live_delete():
    conn = _ScriptedConn(fetchone_queue=[("pending", None)], rowcount=1)
    G.reject_enum_feedback(conn, 9)
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "DELETE FROM enum_dictionary" not in joined
    assert "status='rejected'" in joined


# ── promote_enum_feedback ──────────────────────────────────────────────────────
def test_promote_enum_feedback_inserts_and_marks():
    # pending → enum_dictionary upsert(source='manual') + feedback status='promoted'.
    conn = _ScriptedConn(
        fetchone_queue=[("common", "", "orders", "status", "P", "결제대기"), (321,)], rowcount=1)
    eid = G.promote_enum_feedback(conn, 3, approved_by="curator")
    assert eid == 321
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO enum_dictionary" in joined and "'manual'" in joined
    assert "status='promoted'" in joined


# ── bulk_promote_enum_feedback (구조 묶음 단위 '등록') ──────────────────────────
def test_bulk_promote_enum_feedback_multi():
    # 다건 연속 승급 — 각 건마다 SELECT(row) + INSERT RETURNING(eid) 시퀀스. 요청 순서 보존.
    conn = _ScriptedConn(fetchone_queue=[
        ("common", "", "orders", "status", "P", "결제대기"), (101,),
        ("common", "", "orders", "status", "S", "배송중"), (102,),
    ], rowcount=1)
    results = G.bulk_promote_enum_feedback(conn, [3, 4], approved_by="curator")
    assert results == [{"feedback_id": 3, "enum_id": 101}, {"feedback_id": 4, "enum_id": 102}]


def test_bulk_promote_enum_feedback_skips_missing():
    # pending 아님/없음(SELECT fetchone=None) → enum_id=None skip(예외 아님, 부분 skip 정상).
    conn = _ScriptedConn(fetchone_queue=[
        None,                                                       # id 5: 대상 아님 → None
        ("common", "", "orders", "status", "P", "결제대기"), (201,),   # id 6: 정상 승급
    ], rowcount=1)
    results = G.bulk_promote_enum_feedback(conn, [5, 6])
    assert results == [{"feedback_id": 5, "enum_id": None}, {"feedback_id": 6, "enum_id": 201}]


# ── infer_enum_suggestions — LLM 위임 + 필터링(fake 모듈 주입) ──────────────────
def test_infer_enum_suggestions_filters(monkeypatch):
    fake = types.ModuleType("modules.llm")
    fake.llm_enum_suggest = lambda payload: [
        {"table_name": "orders", "column_name": "status", "code": "P", "label": "결제대기", "confidence": 0.9},
        {"table_name": "", "column_name": "status", "code": "X", "label": "결측"},          # table 없음 → drop
        {"table_name": "orders", "column_name": "status", "code": "S", "label": ""},         # label 없음 → drop
    ]
    monkeypatch.setitem(sys.modules, "modules.llm", fake)
    ans = "주문 상태 컬럼 status 는 코드값 P 가 결제대기를 의미합니다. 자세한 설명을 덧붙입니다. " * 2
    out = G.infer_enum_suggestions("status 코드 의미?", ans)
    assert len(out) == 1
    assert out[0]["table_name"] == "orders" and out[0]["code"] == "P" and out[0]["label"] == "결제대기"


def test_infer_enum_suggestions_short_answer_skips():
    # 80자 미만 답변은 LLM 호출 자체를 건너뛴다(비용 가드) → [].
    assert G.infer_enum_suggestions("q", "짧은 답변") == []
