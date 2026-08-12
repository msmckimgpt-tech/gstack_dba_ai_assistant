"""feature-0016 graph-search-content 단위 테스트 — 그래프 뷰 검색이 이름/FQN 외에
컨텐츠 카테고리(semantic_cluster_label) 와 AI 능동 분석 본문(node_analysis_jobs.analysis)
까지 매칭하도록 확장한 search_nodes / _analysis_match_keys 검증. DB/AGE/LLM 불요(fake).

검증 축:
  A. _analysis_match_keys 가 node_analysis_jobs 를 status='done' + position() 부분일치로 조회하고,
     scope 지정 시 scope_key 조건을 붙이며, bind param 으로 query.lower() 를 전달한다.
     1자 질의는 조회 자체를 스킵(노이즈·풀스캔 방지)한다.
  B. search_nodes 의 Cypher WHERE 가 name/fqn 에 더해 semantic_cluster_label CONTAINS 를 포함하고,
     분석 매칭 key 를 n.key IN [...] 로 합류하며, RETURN 에 semantic_cluster_label 을 싣는다.
  C. 반환 노드에 match_via(category/analysis) 와 cluster_label 이 실린다.
"""
import pytest

from modules import metadata_graph as mg


# ── fakes ─────────────────────────────────────────────────────────────────────
class FakeCursor:
    """SQL substring → fetch 결과 매핑. 매칭 없으면 빈 결과(fetchall=[])."""

    def __init__(self, rows=None):
        self.rows = rows or {}
        self.executed = []
        self._last = None

    def execute(self, sql, params=None):
        flat = " ".join(str(sql).split())
        self.executed.append((flat, params))
        self._last = None
        for pat, row in self.rows.items():
            if pat in flat:
                self._last = row
                break

    def fetchall(self):
        if self._last is None:
            return []
        return self._last if isinstance(self._last, list) else [self._last]

    def fetchone(self):
        if isinstance(self._last, list):
            return self._last[0] if self._last else None
        return self._last

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursor):
        self._cur = cursor

    def cursor(self):
        return self._cur

    def close(self):
        pass


def _cypher_sql(cur):
    for q, _p in cur.executed:
        if "ag_catalog.cypher" in q:
            return q
    return ""


def _analysis_sql(cur):
    for q, p in cur.executed:
        if "node_analysis_jobs" in q:
            return q, p
    return "", None


# ── A: _analysis_match_keys ────────────────────────────────────────────────────
def test_analysis_match_keys_sql_and_params():
    cur = FakeCursor(rows={"node_analysis_jobs": [["cc_data_main:dt_orders"], ["gamedb:t_pay"]]})
    keys = mg._analysis_match_keys(cur, "결제", scope="mssql-abc", limit=50)
    assert keys == ["cc_data_main:dt_orders", "gamedb:t_pay"]
    sql, params = _analysis_sql(cur)
    assert "node_analysis_jobs" in sql
    assert "status = 'done'" in sql
    assert "position(%s in lower(analysis::text))" in sql
    assert "scope_key = %s" in sql
    # bind param: (…검색어 후보…, scope, limit) — injection-safe.
    # hangul-qwerty-search: 후보 = 원문 + 반대 자판 변환본('결제' → 'rufwp'). 플레이스홀더
    #   수와 파라미터 수가 어긋나면 실행 자체가 깨지므로 그 정합을 단언한다.
    assert params[0] == "결제"
    assert "rufwp" in params                       # 반대 자판 후보가 실제로 실렸다
    assert params[-2] == "mssql-abc" and params[-1] == 50
    assert sql.count("%s") == len(params)


def test_analysis_match_keys_no_scope_omits_scope_clause():
    cur = FakeCursor(rows={"node_analysis_jobs": [["k1"]]})
    keys = mg._analysis_match_keys(cur, "spawn", scope=None, limit=10)
    assert keys == ["k1"]
    sql, params = _analysis_sql(cur)
    assert "scope_key" not in sql
    # hangul-qwerty-search: 원문 + 반대 자판 후보('spawn' → '넴주') 뒤에 limit 하나.
    assert params[0] == "spawn" and params[-1] == 10
    assert "넴주" in params
    assert sql.count("%s") == len(params)


def test_analysis_match_keys_short_query_skipped():
    cur = FakeCursor(rows={"node_analysis_jobs": [["k1"]]})
    assert mg._analysis_match_keys(cur, "a", scope=None, limit=10) == []
    assert cur.executed == []   # 1자 질의는 조회 자체를 하지 않음(노이즈·풀스캔 방지)


def test_analysis_match_keys_graceful_on_error():
    class Boom(FakeCursor):
        def execute(self, sql, params=None):
            raise RuntimeError("no such table")
    assert mg._analysis_match_keys(Boom(), "결제", scope=None, limit=10) == []


# ── B+C: search_nodes 매칭 확장 ────────────────────────────────────────────────
def _q(s):
    return '"' + s + '"'   # agtype 문자열 리터럴(따옴표 포함) — _unwrap 이 json.loads


def test_search_nodes_matches_category_and_analysis():
    # cypher 결과: (1) 이름·FQN 엔 '결제' 없지만 cluster_label='결제 관련' → category 매칭,
    #             (2) 분석 key 로 합류된 노드 → analysis 매칭.
    cypher_rows = [
        [_q("Table"), _q("gamedb:t_user"), _q("t_user"), _q("gamedb.t_user"),
         "null", "null", "null", "null", _q("결제 관련")],
        [_q("Table"), _q("cc_data_main:dt_orders"), _q("dt_orders"), _q("cc_data_main.dt_orders"),
         "null", "null", "null", "null", "null"],
    ]
    cur = FakeCursor(rows={
        "node_analysis_jobs": [["cc_data_main:dt_orders"]],
        "ag_catalog.cypher": cypher_rows,
    })
    out = mg.search_nodes("결제", limit=50, scope="mssql-abc", conn=FakeConn(cur))

    # Cypher WHERE 에 컨텐츠 카테고리 CONTAINS + 분석 key IN 합류 + RETURN 확장.
    csql = _cypher_sql(cur)
    assert "toLower(n.semantic_cluster_label) CONTAINS" in csql
    assert "n.key IN [" in csql and "cc_data_main:dt_orders" in csql
    assert "n.semantic_cluster_label LIMIT" in csql   # RETURN 마지막 컬럼
    assert "n.scope_key = 'mssql-abc'" in csql        # scope 격리 유지

    by_key = {n["key"]: n for n in out}
    assert by_key["gamedb:t_user"].get("cluster_label") == "결제 관련"
    assert by_key["gamedb:t_user"].get("match_via") == ["category"]
    assert by_key["cc_data_main:dt_orders"].get("match_via") == ["analysis"]


def test_search_nodes_name_match_still_flagged():
    cypher_rows = [
        [_q("Table"), _q("gamedb:t_pay"), _q("t_pay"), _q("gamedb.t_pay"),
         "null", "null", "null", "null", "null"],
    ]
    cur = FakeCursor(rows={"ag_catalog.cypher": cypher_rows})   # 분석 매칭 없음
    out = mg.search_nodes("pay", limit=50, scope=None, conn=FakeConn(cur))
    assert out[0]["match_via"] == ["name"]
    # 분석 매칭 없으면 key IN 절 미포함.
    assert "n.key IN [" not in _cypher_sql(cur)


def test_search_nodes_empty_query_noop():
    cur = FakeCursor()
    assert mg.search_nodes("", conn=FakeConn(cur)) == []
    assert cur.executed == []


# ── P2: 넓힌 후보 풀 → 점수 정렬 후 limit 재절단(이름-정확 매칭 보존) ─────────────
def test_search_nodes_post_sort_truncates_and_keeps_high_score():
    # 후보 2개(스캔순서: 저점수 먼저, 이름-정확 뒤). limit=1 이어도 절단이 정렬 이후라
    # 고점수(이름-정확) 노드가 살아남아야 한다(구 동작=스캔순서 절단이면 저점수가 남아 회귀).
    cypher_rows = [
        [_q("Table"), _q("gamedb:t_zebra"), _q("t_zebra"), _q("gamedb.t_zebra"),
         "null", "null", "null", "null", "null"],
        [_q("Table"), _q("gamedb:t_pay"), _q("t_pay"), _q("gamedb.t_pay"),
         "null", "null", "null", "null", "null"],
    ]
    cur = FakeCursor(rows={
        "ag_catalog.cypher": cypher_rows,
        "GREATEST(similarity": [[0, 0.10], [1, 0.95]],   # index1(t_pay)=이름-정확 고점수
    })
    out = mg.search_nodes("pay", limit=1, scope=None, conn=FakeConn(cur))
    assert len(out) == 1
    assert out[0]["key"] == "gamedb:t_pay"   # 저점수 t_zebra 가 아니라 고점수 t_pay 생존
    # 후보 풀은 limit(1)보다 넓게 떴다(LIMIT 4 = min(240, 1*4)).
    assert "LIMIT 4" in _cypher_sql(cur)


# ── P4: non-autocommit 커넥션에서 분석 쿼리 실패 시 SAVEPOINT 로 트랜잭션 복원 ──────
class _RaiseOnAnalysisCursor(FakeCursor):
    def execute(self, sql, params=None):
        flat = " ".join(str(sql).split())
        self.executed.append((flat, params))
        if "node_analysis_jobs" in flat:
            raise RuntimeError("relation node_analysis_jobs does not exist")
        self._last = None


def _flat_sqls(cur):
    return [q for q, _p in cur.executed]


def test_analysis_match_keys_savepoint_rollback_on_non_autocommit():
    cur = _RaiseOnAnalysisCursor()
    keys = mg._analysis_match_keys(cur, "결제", scope=None, limit=10, autocommit=False)
    assert keys == []
    sqls = _flat_sqls(cur)
    assert any("SAVEPOINT _amk_sp" in s and "ROLLBACK" not in s for s in sqls)      # 진입 시 savepoint
    assert any("ROLLBACK TO SAVEPOINT _amk_sp" in s for s in sqls)                  # 실패 시 복원


def test_analysis_match_keys_autocommit_no_savepoint():
    cur = FakeCursor(rows={"node_analysis_jobs": [["k1"]]})
    keys = mg._analysis_match_keys(cur, "결제", scope=None, limit=10, autocommit=True)
    assert keys == ["k1"]
    assert not any("SAVEPOINT" in s for s in _flat_sqls(cur))   # autocommit 은 savepoint 미사용
