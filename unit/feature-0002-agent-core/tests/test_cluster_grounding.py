"""feature-0034-analysis-consumption — L2 요약의 대화 grounding 주입 단위 테스트.

검증 축:
  A(정직성): 근거 수를 반드시 함께 싣는다. 라이브 실측상 요약의 85%가 상세분석 근거 0(이름 규칙
    기반)이라, 근거를 숨기면 LLM 이 추정을 실측 결론으로 오독하고 그 오독이 답변에 실린다.
  B(매칭): 질문에 등장한 테이블의 묶음만 — 짧은 이름 오탐 방지, scope 격리.
  C(fail-soft): 답변 경로에 있는 코드라 어떤 실패도 답변을 막지 않는다.
  D(배선): 답변 컨텍스트 조립부가 실제로 이 로더를 호출하고 datamark 를 씌운다.
"""
import pathlib

import pytest

from modules import cluster_context as cc

_AGENT_CORE = pathlib.Path(__file__).resolve().parents[1] / "src" / "agent_core.py"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setattr(cc, "enabled", lambda: True)


# ── A: 정직성 ───────────────────────────────────────────────────────────────
def test_render_states_evidence_count():
    out = cc.render([("결제 기록", "결제와 환불을 다루는 묶음이다.", 20, 3)])
    assert "결제 기록" in out and "20개 중 3개" in out


def test_render_marks_unevidenced_summary_as_estimate():
    """근거 0 요약은 '추정'임을 명시해야 한다 — 라이브 요약의 85%가 이 경우다."""
    out = cc.render([("로그 아카이브", "백업과 장기 보관을 담당한다.", 42, 0)])
    assert "근거 없음" in out and "추정" in out
    assert "42개" in out


def test_render_clips_long_summary():
    long_text = "가" * 2000
    out = cc.render([("x", long_text, 5, 5)])
    assert len(out) < 1200


def test_render_respects_limit():
    rows = [(f"L{i}", f"요약{i}", 5, 1) for i in range(5)]
    assert len(cc.render(rows, limit=2).splitlines()) == 2


def test_render_skips_malformed_rows():
    rows = [("", "요약", 1, 1), ("라벨", "", 1, 1), ("정상", "정상 요약", 2, 1), (None,)]
    out = cc.render(rows, limit=10)
    assert out.count("\n") == 0 and "정상" in out


def test_render_normalizes_whitespace():
    out = cc.render([("L", "여러\n줄로   된\t요약", 1, 1)])
    assert "\n" not in out.split("] ")[-1][:50]


# ── B: 매칭 ─────────────────────────────────────────────────────────────────
class _Cur:
    """2단계 쿼리(테이블 매칭 → 요약 조회)를 흉내내는 커서 stub."""

    def __init__(self, match_rows=None, summary_rows=None):
        self.calls = []
        self._match = match_rows if match_rows is not None else [
            ("ds1", "dbo", "ds1:mydb.dbo.characteritem", "결제 기록")]
        self._summaries = summary_rows if summary_rows is not None else [
            ("결제 기록", "요약", 10, 2)]
        self._last = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if "FROM rag_objects" in sql:
            self._last = self._match
        elif "FROM cluster_summaries" in sql:
            self._last = self._summaries
        else:
            self._last = []

    def fetchall(self):
        return self._last

    def close(self):
        pass


class _Conn:
    def __init__(self, **kw):
        self.cur = _Cur(**kw)

    def cursor(self):
        return self.cur


def _sql_of(conn, marker):
    return [c for c in conn.cur.calls if marker in c[0]][0]


def test_query_matches_table_names_inside_the_question():
    """매칭은 '질문 안에 테이블명이 등장하는가'다 — 기존 grounding 로더와 동형."""
    conn = _Conn()
    cc.fetch_summaries(conn, "characteritem 테이블 알려줘", ["ds1"], 2)
    sql, params = _sql_of(conn, "FROM rag_objects")
    assert "strpos" in sql and "table_name" in sql
    assert "characteritem 테이블 알려줘" in params


def test_query_does_not_use_ilike_wildcards():
    """테이블명의 `_`(예 backup_log_trade)가 ILIKE 에서 '임의의 1문자'로 해석되면
    `backup-log-trade` 같은 문자열에도 걸린다 — strpos 는 순수 부분문자열 검사다."""
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    sql, _p = _sql_of(conn, "FROM rag_objects")
    assert "ILIKE" not in sql.upper()


def test_result_is_ordered_by_evidence_not_label():
    """DISTINCT ON 은 ORDER BY 첫 컬럼이 label 이어야 해서, 그대로 LIMIT 하면 결과가
    '근거 많은 순'이 아니라 라벨 알파벳 순으로 잘린다."""
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    sql, _p = _sql_of(conn, "FROM cluster_summaries")
    assert "ORDER BY analyzed_count DESC" in sql and "LIMIT" in sql


def test_query_filters_short_table_names():
    """'id'·'log' 같은 짧은 이름은 질문 아무 데나 걸려 오탐한다."""
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    _sql, params = _sql_of(conn, "FROM rag_objects")
    assert cc._MIN_TABLE_NAME_LEN in params and cc._MIN_TABLE_NAME_LEN >= 4


def test_query_is_scope_isolated():
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds-a"], 2)
    sql, params = _sql_of(conn, "FROM rag_objects")
    assert "datasource_key = ANY" in sql and ["ds-a"] in params


def test_lookup_uses_label_not_cluster_id():
    """`semantic_cluster_id` 는 pass 마다 재부여되어 churn 한다 — 그것으로 조회하면 엉뚱한
    묶음의 요약이 붙는다. 라벨은 스키마 내 유일화돼 있어 안정적인 키다."""
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    m_sql, _ = _sql_of(conn, "FROM rag_objects")
    s_sql, _ = _sql_of(conn, "FROM cluster_summaries")
    assert "semantic_cluster_label" in m_sql
    assert "semantic_cluster_id" not in m_sql and "semantic_cluster_id" not in s_sql


def test_lookup_is_schema_isolated():
    """cluster_summaries 식별자는 (scope, schema, …) 다. schema 없이 조회하면 같은 datasource
    의 **다른 스키마**가 같은 라벨을 가질 때 엉뚱한 요약이 붙는다(codex P1)."""
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    sql, params = _sql_of(conn, "FROM cluster_summaries")
    assert "(scope_key, schema_name, label)" in sql
    # 1단계에서 유도한 effective schema 가 실제로 바인딩된다(MSSQL: object_key 의 DB명).
    assert ["mydb"] in params


def test_effective_schema_matches_the_clustering_rule():
    """`cluster_summaries.schema_name` 은 effective schema 다. rag_objects.schema_name 을
    그대로 쓰면 MSSQL(리터럴 'dbo')에서 한 건도 매칭되지 않는다.

    복제 구현이므로 원본과의 드리프트를 여기서 잡는다."""
    from modules import semantic_cluster as sc
    cases = [
        ("ds1", "ds1:mydb.dbo.tbl", "dbo"),      # MSSQL 3-part → DB명
        ("ds1", "ds1:mydb.tbl", "mydb"),         # MySQL 2-part → DB명
        ("ds1", "ds1:tbl", "fallback"),          # 파싱 불가 → schema_name
        ("ds1", "", "fallback"),
    ]
    for ds, ok, schema in cases:
        assert cc.effective_schema(ds, ok, schema) == sc._effective_schema(ds, ok, schema), \
            f"드리프트: {ok}"


def test_match_rows_are_capped():
    """짧은 이름이 광범위 매칭될 때 2단계 IN 절이 비대해지지 않게."""
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    _sql, params = _sql_of(conn, "FROM rag_objects")
    assert cc._MATCH_ROW_CAP in params


def test_no_match_skips_the_second_query():
    conn = _Conn(match_rows=[])
    assert cc.fetch_summaries(conn, "질문", ["ds1"], 2) == []
    assert not any("FROM cluster_summaries" in c[0] for c in conn.cur.calls)


def test_query_sets_and_resets_statement_timeout():
    """답변 경로다 — 느려지면 주입을 포기하는 편이 낫다.

    `SET LOCAL` 은 트랜잭션 안에서만 유효한데 RO 연결은 autocommit 이라 무효다(codex P1).
    세션 레벨 SET 을 쓰되, 호출측 커넥션에 설정이 누출되지 않게 RESET 이 짝을 이뤄야 한다."""
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    sqls = [c[0] for c in conn.cur.calls]
    assert any(s.startswith("SET statement_timeout") for s in sqls), "SET LOCAL 은 autocommit 에서 무효"
    assert any("RESET statement_timeout" in s for s in sqls), "세션 설정이 누출된다"


def test_empty_scope_or_message_short_circuits():
    conn = _Conn()
    assert cc.fetch_summaries(conn, "질문", [], 2) == []
    assert cc.fetch_summaries(conn, "", ["ds1"], 2) == []
    assert conn.cur.calls == []


# ── C: fail-soft ────────────────────────────────────────────────────────────
def test_fetch_failure_returns_empty():
    class _Boom(_Conn):
        def cursor(self):
            raise RuntimeError("pg down")

    assert cc.fetch_summaries(_Boom(), "질문", ["ds1"], 2) == []


def test_missing_table_returns_empty():
    class _NoTable(_Conn):
        def cursor(self):
            cur = _Cur()

            def _ex(sql, params=None):
                if "cluster_summaries" in sql:
                    raise RuntimeError('relation "cluster_summaries" does not exist')

            cur.execute = _ex
            return cur

    assert cc.fetch_summaries(_NoTable(), "질문", ["ds1"], 2) == []


def test_loader_returns_empty_without_scope(monkeypatch):
    monkeypatch.setattr(cc, "_scope_candidates", lambda s: [])
    assert cc.load_cluster_summary_context("질문") == ""


def test_loader_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(cc, "enabled", lambda: False)
    called = []
    monkeypatch.setattr(cc, "_ro_conn", lambda c: called.append(1) or (None, False))
    assert cc.load_cluster_summary_context("질문") == ""
    assert called == [], "비활성인데 연결을 열었다"


def test_loader_returns_empty_on_blank_message():
    assert cc.load_cluster_summary_context("   ") == ""


# ── D: 배선 ─────────────────────────────────────────────────────────────────
def test_agent_core_calls_the_loader():
    """로더가 있어도 답변 경로가 부르지 않으면 주입이 아니다 — 실제 호출을 소스로 단정한다."""
    src = _AGENT_CORE.read_text(encoding="utf-8")
    assert "load_cluster_summary_context" in src


def test_agent_core_wraps_injection_in_untrusted_datamark():
    """요약은 LLM 이 생성한 텍스트다 — 지시로 읽히면 프롬프트 인젝션 표면이 된다."""
    src = _AGENT_CORE.read_text(encoding="utf-8")
    idx = src.index("load_cluster_summary_context")
    window = src[idx:idx + 2000]
    assert "_datamark_untrusted" in window
    assert "지시 아님" in window


def test_agent_core_warns_the_model_about_unevidenced_summaries():
    """근거 없는 요약을 사실로 단정하지 말라는 지시가 프롬프트에 있어야 한다 — 근거 표기를
    실어 보내도 모델에게 그 의미를 알려주지 않으면 무용지물이다."""
    src = _AGENT_CORE.read_text(encoding="utf-8")
    idx = src.index("TABLE GROUP SUMMARIES")
    window = src[idx:idx + 1200]
    assert "단정하지" in window and "근거 없음" in window


def test_agent_core_measures_the_injection_latency():
    """답변 경로 추가는 지연 계측이 따라야 한다(feature-0026 M3 계약)."""
    src = _AGENT_CORE.read_text(encoding="utf-8")
    assert 'cluster_summary_ms' in src


def test_agent_core_injection_is_failsoft():
    src = _AGENT_CORE.read_text(encoding="utf-8")
    idx = src.index("load_cluster_summary_context")
    window = src[max(0, idx - 300):idx + 300]
    assert "except Exception" in window


# ── 라벨 네임스페이스 (2026-08-06) ───────────────────────────────────────────
def test_render_marks_the_schema_of_each_label():
    """라벨은 datasource 안에서 유일하지 않다 — 어느 DB 이야기인지 함께 적는다.

    라이브 실측: `메일 시스템` 9개 스키마 · `길드 관리` 8개 · `경매 시스템` 7개. 스키마를 빼면
    서로 다른 DB 의 같은 이름 클러스터 요약이 나란히 실려 모델이 한 DB 의 사실로 읽는다."""
    out = cc.render([("메일 시스템", "메일 보관·발송을 다룬다.", 12, 4, "atum2_db_1")])
    assert "[atum2_db_1] 메일 시스템" in out


def test_render_separator_survives_labels_that_contain_the_separator():
    """라벨 자체가 `" · "` 를 품는다(`_disambiguate_labels` 가 동명 라벨에 접미를 붙인다).

    같은 구분자로 스키마를 이으면 `[web_statistics · 일일 경험치 · dayexp]` 가 되어 어디까지가
    스키마인지 사라진다 — 스키마는 대괄호로 따로 묶는다."""
    out = cc.render([("일일 경험치 · dayexp", "요약", 5, 0, "web_statistics")])
    assert "[web_statistics] 일일 경험치 · dayexp" in out


def test_render_stays_backward_compatible_without_schema():
    """5번째 원소가 없으면 기존 형태 — 호출부·저장 행 형태 변화에 대해 fail-soft."""
    out = cc.render([("메일 시스템", "메일 보관·발송을 다룬다.", 12, 4)])
    assert "[메일 시스템]" in out


def test_summary_query_breaks_ties_deterministically():
    """(label, member_count, analyzed_count) 완전 동률 그룹이 라이브에 실재한다 — 최종 tie-breaker
    가 없으면 같은 질문이 매번 다른 행을 받는다."""
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    sql, _p = _sql_of(conn, "FROM cluster_summaries")
    assert "label, member_set_hash" in sql


def test_summary_query_selects_schema():
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    sql, _p = _sql_of(conn, "FROM cluster_summaries")
    assert "analyzed_count, schema_name" in sql


def test_match_query_is_deterministic_under_the_row_cap():
    """정렬 없는 LIMIT 은 어느 200행이 오는지 비결정적이다.

    테이블명 하나가 24개 eff-schema(DB 사본군)에 걸리는 라이브에서는 상한에 실제로 닿고,
    그때 같은 질문이 매번 다른 근거를 받는다."""
    conn = _Conn()
    cc.fetch_summaries(conn, "질문", ["ds1"], 2)
    sql, _p = _sql_of(conn, "FROM rag_objects")
    assert "ORDER BY o.datasource_key, o.object_key" in sql
    assert sql.index("ORDER BY") < sql.index("LIMIT")
