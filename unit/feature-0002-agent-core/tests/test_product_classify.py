"""feature-0016 §59(product-classify-suggest) — 분류 제안 파이프라인 격리 검증 (ADR-025).

핵심 계약: LLM 산출은 **승인 대기(Pending, RuleId NULL·reason 'ai_suggest:<conf>')에만** 적재되고
(allowlist 직접 기록 금지), 환각 차단 3중 게이트(입력 스키마 실재·화이트리스트 제품 id·신뢰도
임계)를 통과한 것만 채택한다. DB 없이 fake cursor + monkeypatch 로 검증한다.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules import product_classify as pc  # noqa: E402


class _MemCur:
    """마커 매칭 fake cursor — INSERT 는 (sql, params) 캡처 + rowcount 1."""

    def __init__(self, rows_by_marker=None):
        self.rows_by_marker = list(rows_by_marker or [])
        self.executed = []
        self._rows = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        self.executed.append((str(sql), params))
        self._rows = []
        self.rowcount = 1 if "INSERT" in str(sql) else 0
        for marker, rows in self.rows_by_marker:
            if marker in str(sql):
                self._rows = list(rows)
                break

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

    def close(self):
        pass


class _MemConn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self):
        return self._cur

    def close(self):
        pass


def _patch_inputs(monkeypatch, suggestions):
    from shared import datasources as dsr
    from modules import metadata_graph as mg
    from modules import node_analysis as na
    from modules import llm as llm_mod
    monkeypatch.setattr(dsr, "resolve", lambda conn, k: {"scope_key": "mssql-abc"})
    monkeypatch.setattr(mg, "scope_schemas", lambda scope, conn=None: {"nodes": [
        {"key": "mssql-abc:fhgame1", "name": "fhgame1", "table_count": 61},
        {"key": "mssql-abc:mappeddb", "name": "mappeddb", "table_count": 3},
        {"key": "mssql-abc:pendingdb", "name": "pendingdb", "table_count": 2},
    ]})
    monkeypatch.setattr(mg, "schema_table_keys",
                        lambda scope, sk, limit=12, conn=None: [{"name": "FH_CHAR"}, {"name": "FH_ITEM"}])
    monkeypatch.setattr(na, "get_node_analysis",
                        lambda scope, nk, conn=None: {"analysis": {"summary": "낚시 게임 캐릭터/아이템 DB"}})
    captured = {}

    def _fake_llm(payload, **_kw):   # 0047: scope_key kwarg 수용(사용 기록 데이터소스 귀속)
        captured["payload"] = payload
        captured["scope_key"] = _kw.get("scope_key")
        return {"suggestions": suggestions}

    monkeypatch.setattr(llm_mod, "llm_product_classify", _fake_llm)
    return captured


def _mem(rows_extra=None):
    cur = _MemCur(rows_by_marker=[
        ("JOIN WebProductDatasources", [(1, "출조낚시왕", "낚시 MMO", "mssql-qa")]),
        ("COALESCE(DatasourceKey,'')", []),
        ("FROM WebProductDatabases", [("mappeddb",)]),
        ("FROM WebProductDatabasePending", [("pendingdb",)]),
    ] + (rows_extra or []))
    return cur, _MemConn(cur)


def test_classify_pass_inserts_pending_with_null_rule_and_conf_reason(monkeypatch):
    """정상 제안 → Pending INSERT(RuleId NULL·reason 'ai_suggest:<conf>'). 매핑/대기 스키마는
    LLM 입력에서 선제 제외(taken), allowlist(WebProductDatabases) 직접 기록 없음."""
    cap = _patch_inputs(monkeypatch, [
        {"schema": "fhgame1", "product_id": 1, "confidence": 0.87, "reason": "낚시 테이블 다수"},
    ])
    cur, conn = _mem()
    rep = pc.run_classify_pass(kb_conn=object(), mem_conn=conn)
    ins = [(s, p) for s, p in cur.executed if "INSERT" in s]
    assert len(ins) == 1
    sql, params = ins[0]
    assert "WebProductDatabasePending" in sql and "NULL" in sql
    assert "WebProductDatabases " not in sql          # allowlist 직접 기록 금지
    assert params == (1, "mssql-qa", "fhgame1", "ai_suggest:0.87|낚시 테이블 다수")
    assert rep["suggested_total"] == 1
    # taken(매핑 mappeddb·대기 pendingdb)은 LLM 입력에서 제외 — 유일 입력은 fhgame1.
    sent = [s["name"] for s in cap["payload"]["schemas"]]
    assert sent == ["fhgame1"]


def test_classify_pass_hallucination_gates(monkeypatch):
    """환각 차단 3중 게이트: 미입력 스키마·비화이트리스트 제품 id·임계 미만 신뢰도 전부 폐기,
    같은 스키마 다중 제안은 최고 신뢰도 1건만."""
    _patch_inputs(monkeypatch, [
        {"schema": "ghost_db", "product_id": 1, "confidence": 0.99, "reason": "x"},   # 미입력 스키마
        {"schema": "fhgame1", "product_id": 77, "confidence": 0.99, "reason": "x"},   # 비화이트리스트 pid
        {"schema": "fhgame1", "product_id": 1, "confidence": 0.30, "reason": "x"},    # 임계 미만
        {"schema": "fhgame1", "product_id": 1, "confidence": 0.65, "reason": "a"},
        {"schema": "fhgame1", "product_id": 1, "confidence": 0.91, "reason": "b"},    # 최고 — 채택
    ])
    cur, conn = _mem()
    rep = pc.run_classify_pass(kb_conn=object(), mem_conn=conn)
    ins = [(s, p) for s, p in cur.executed if "INSERT" in s]
    assert len(ins) == 1 and ins[0][1][3].startswith("ai_suggest:0.91")
    assert rep["suggested_total"] == 1


def test_classify_pass_nonfinite_and_out_of_range_conf_rejected(monkeypatch):
    """패널 MAJOR 회귀 잠금: json.loads 가 수용하는 NaN/Infinity 와 (0,1] 범위 밖 신뢰도는
    MIN_CONF 게이트를 우회하지 못한다(NaN 은 < 비교 항상 False — isfinite 로 차단)."""
    _patch_inputs(monkeypatch, [
        {"schema": "fhgame1", "product_id": 1, "confidence": float("nan"), "reason": "x"},
        {"schema": "fhgame1", "product_id": 1, "confidence": float("inf"), "reason": "x"},
        {"schema": "fhgame1", "product_id": 1, "confidence": 7.5, "reason": "x"},
        {"schema": "fhgame1", "product_id": 1, "confidence": -0.5, "reason": "x"},
    ])
    cur, conn = _mem()
    rep = pc.run_classify_pass(kb_conn=object(), mem_conn=conn)
    assert rep["suggested_total"] == 0
    assert not any("INSERT" in s for s, _ in cur.executed)


def test_classify_pass_system_schema_and_inject_name_excluded(monkeypatch):
    """패널 MINOR 회귀 잠금: 시스템 스키마·주입 문자/과길이 이름은 LLM 후보에서 원천 제외."""
    from modules import metadata_graph as mg
    cap = _patch_inputs(monkeypatch, [])
    monkeypatch.setattr(mg, "scope_schemas", lambda scope, conn=None: {"nodes": [
        {"key": "mssql-abc:master", "name": "master", "table_count": 1},
        {"key": "mssql-abc:bad;db", "name": "bad;db", "table_count": 1},
        {"key": "mssql-abc:okdb", "name": "okdb", "table_count": 1},
    ]})
    cur, conn = _mem()
    pc.run_classify_pass(kb_conn=object(), mem_conn=conn)
    sent = [s["name"] for s in cap["payload"]["schemas"]]
    assert sent == ["okdb"]


def test_classify_pass_dry_run_no_write(monkeypatch):
    _patch_inputs(monkeypatch, [
        {"schema": "fhgame1", "product_id": 1, "confidence": 0.9, "reason": "x"},
    ])
    cur, conn = _mem()
    rep = pc.run_classify_pass(kb_conn=object(), mem_conn=conn, dry_run=True)
    assert not any("INSERT" in s for s, _ in cur.executed)   # 핵심 계약: 쓰기 0
    assert rep["dry_run"] is True and rep["suggested_total"] == 1   # 집계는 '제안될 건수' 그대로
    assert rep["datasources"]["mssql-qa"]["suggested"] == 1


def test_classify_pass_llm_failure_is_soft(monkeypatch):
    from modules import llm as llm_mod
    _patch_inputs(monkeypatch, [])
    monkeypatch.setattr(llm_mod, "llm_product_classify", lambda payload, **_kw: None)   # LLM 실패
    cur, conn = _mem()
    rep = pc.run_classify_pass(kb_conn=object(), mem_conn=conn)
    assert rep["suggested_total"] == 0 and not rep["errors"]
    assert not any("INSERT" in s for s, _ in cur.executed)
