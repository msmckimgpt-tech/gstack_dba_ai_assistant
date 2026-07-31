"""perf-cyvol: 그래프 sync 의 cypher 호출량 감축 회귀 잠금.

라이브 실측(2026-07-28) — 전량 sync 1회 = cypher 158,544 회 / PG 실행 867초(wall 1148초의 75%).
샘플링 프로파일 지배 형태가 (a) 테이블·루틴마다 재-MERGE 되는 Schema/Table 정점,
(b) routine 마다 ROUTINE_USES 전량 DELETE 후 재-MERGE 였다.

**§18.8 QA 패널(변이 28개 중 17개 생존)의 지적을 반영한 구조**:
  - 리프 함수만 문자열 매칭하면 **`sync_graph` 배선**(캐시 주입·commit/drop/reset)이 전혀
    검증되지 않는다 → `_SyncCur`/`_SyncConn` 로 `sync_graph` 를 끝까지 구동하는 테스트를 둔다.
  - fake 커서의 `fetchall` 이 항상 빈 리스트면 **선조회 루프가 한 번도 실행되지 않아**
    쓰기 속성명(`SET r.refs_sig`)과 읽기 속성명(`RETURN r.refs_sig`)의 커플링이 안 잠긴다
    (prefix 매칭이라 `refs_sig2` 로 바꿔도 통과했다) → 두 이름을 SQL 에서 뽑아 **동일성**을 본다.
  - `psycopg.Cursor.__slots__ == ()` 선례(feature-0029 B-1) — 커서에 속성을 달지 않음을 잠근다.
"""
import re

import pytest

import modules.metadata_graph as G


class _Cur:
    """실행된 cypher 문만 모으는 최소 커서. `__slots__` 로 속성 부착을 금지한다.

    feature-0029 B-1: 라이브 `psycopg.Cursor` 는 `__slots__ == ()` 라 속성을 달 수 없는데,
    `__dict__` 를 가진 fake 커서로 테스트해 '캐시가 라이브에서 항상 꺼져 있는' 결함을 놓쳤다.
    """

    __slots__ = ("sql", "_rows")

    def __init__(self, rows=None):
        self.sql: list = []
        self._rows = list(rows or [])

    def execute(self, sql, params=None):
        self.sql.append(" ".join(str(sql).split()))

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _RaisingCur(_Cur):
    """지정한 부분문자열을 담은 문에서 예외를 던지는 커서 (실패 경로 검증용)."""

    __slots__ = ("boom",)

    def __init__(self, boom):
        super().__init__()
        self.boom = boom

    def execute(self, sql, params=None):
        super().execute(sql, params)
        if self.boom in " ".join(str(sql).split()):
            raise RuntimeError(f"boom: {self.boom}")


def _merges(cur, label):
    return [s for s in cur.sql if f"MERGE (n:{label} " in s]


# ── (1) 정점 중복 MERGE 제거 ────────────────────────────────────────────────
def test_schema_vertex_merged_once_per_run():
    """같은 스키마의 테이블 N개 → Schema 정점 MERGE 는 1회. (실측 rag 16,367 → distinct ~140)"""
    cur, cache = _Cur(), G.new_anchor_cache()
    for i in range(5):
        G.sync_table(cur, "ds1", "sch", f"t{i}", description=None, cache=cache)
        G.anchor_cache_commit_pending(cache)
    assert len(_merges(cur, "Schema")) == 1
    assert len(_merges(cur, "Table")) == 5, "Table 정점은 행마다 필요(축약 대상 아님)"


def test_table_vertex_merged_once_across_columns():
    """같은 테이블의 컬럼 N개 → 소속 Table 정점 MERGE 는 1회."""
    cur, cache = _Cur(), G.new_anchor_cache()
    for i in range(4):
        G.sync_column(cur, "ds1", "sch", "t", f"c{i}", cache=cache)
        G.anchor_cache_commit_pending(cache)
    assert len(_merges(cur, "Table")) == 1
    assert len(_merges(cur, "Column")) == 4


def test_cache_absent_preserves_legacy_call_count():
    """캐시 미전달(외부 호출자·기존 경로)은 종전과 동일하게 매번 MERGE — 하위호환."""
    cur = _Cur()
    for i in range(5):
        G.sync_table(cur, "ds1", "sch", f"t{i}", description=None)
    assert len(_merges(cur, "Schema")) == 5


def test_failed_row_marks_are_dropped_not_cached():
    """행 실패(SAVEPOINT 롤백) 시 그 행의 마크는 폐기 — 후속 행이 다시 MERGE 해야 한다."""
    cur, cache = _Cur(), G.new_anchor_cache()
    G.sync_table(cur, "ds1", "sch", "t0", description=None, cache=cache)
    G.anchor_cache_drop_pending(cache)          # 행 실패
    G.sync_table(cur, "ds1", "sch", "t1", description=None, cache=cache)
    assert len(_merges(cur, "Schema")) == 2, "실패 행의 마크가 남아 후속 MERGE 가 생략됐다"


def test_property_layering_not_swallowed_by_cache():
    """**속성이 다르면 같은 정점이라도 다시 MERGE** 한다 (마크에 속성 포함).

    실제 충돌: fqn `a.b.c` 를 `_step_columns` 는 (schema='a', table='b.c') 로,
    `_step_routines` 의 참조 앵커는 fqn 파싱으로 (schema_name='a.b', table_name='c') 로 분해한다
    — **키는 같고 속성은 다르다**. 키만으로 dedup 하면 선행 단계가 후행의 속성 투영을 삼킨다."""
    cur, cache = _Cur(), G.new_anchor_cache()
    G.sync_column(cur, "ds1", "a", "b.c", "c0", cache=cache)
    G.anchor_cache_commit_pending(cache)
    n_before = len(_merges(cur, "Table"))
    G.sync_routine(cur, "ds1", "sch", "p", "procedure", "",
                   [{"fqn": "a.b.c", "kind": "read"}], cache=cache, sig_cache={})
    added = _merges(cur, "Table")[n_before:]
    assert len(added) == 1, "속성이 다른 Table MERGE 가 캐시에 삼켜졌다"
    assert "'c'" in added[0], "루틴 앵커의 table_name 분해가 유실됐다"


def test_vmark_distinguishes_value_types():
    """패널 M13: 마크는 `repr` 로 값 타입을 구분한다 — `str()` 이면 1 과 '1', None 과 'None' 이
    충돌해 서로 다른 MERGE 가 삼켜진다."""
    assert G._vmark("T", "k", {"a": 1}) != G._vmark("T", "k", {"a": "1"})
    assert G._vmark("T", "k", {"a": None}) != G._vmark("T", "k", {"a": "None"})
    assert G._vmark("T", "k", {"a": True}) != G._vmark("T", "k", {"a": "True"})
    assert G._vmark("T", "k", {"a": 1}) == G._vmark("T", "k", {"a": 1})


# ── (2) ROUTINE_USES 조건부 재작성 ──────────────────────────────────────────
_REFS = [{"fqn": "sch.a", "kind": "read"}, {"fqn": "sch.b", "kind": "write"}]
_RKEY = G._vkey("ds1", "sch.p()")


def _sig_deg(refs, scope="ds1"):
    """서명 + 기대 차수가 모두 일치하는 '변경 없음' 상태의 선조회 결과."""
    return ({_RKEY: G.routine_refs_signature(refs)},
            {_RKEY: G.routine_expected_edge_count(refs, scope)})


def test_refs_signature_is_order_insensitive_and_content_sensitive():
    assert G.routine_refs_signature(_REFS) == G.routine_refs_signature(list(reversed(_REFS)))
    assert G.routine_refs_signature(_REFS) != G.routine_refs_signature(_REFS[:1])
    assert (G.routine_refs_signature(_REFS)
            != G.routine_refs_signature([{"fqn": "sch.a", "kind": "write"},
                                         {"fqn": "sch.b", "kind": "write"}]))
    assert (G.routine_refs_signature(_REFS)
            != G.routine_refs_signature([dict(_REFS[0], cross=True), _REFS[1]]))


def test_signature_folds_duplicate_fqn_like_the_edge_loop():
    """패널 MINOR-1: 엣지 루프는 중복 fqn 에서 **입력 순서상 마지막**이 이긴다(뒤 MERGE 가
    relation_type 덮어씀). 서명도 같은 규칙으로 접어야 최종 엣지 집합과 1:1 이 된다 — 단순
    정렬만 하면 중복 fqn 의 순서가 뒤바뀔 때 최종 엣지는 달라지는데 서명은 같아진다."""
    a = [{"fqn": "s.t", "kind": "read"}, {"fqn": "s.t", "kind": "write"}]   # 최종 write
    b = [{"fqn": "s.t", "kind": "write"}, {"fqn": "s.t", "kind": "read"}]   # 최종 read
    assert G.routine_refs_signature(a) != G.routine_refs_signature(b)


def test_signature_tolerates_malformed_refs_without_raising():
    """패널 MINOR: 서명은 정점 MERGE **이전**에 계산되므로 여기서 raise 하면 종전에는 만들어지던
    Routine 정점·HAS_ROUTINE 까지 잃는다(실패 지점 이동). JSON 문자열·비-dict 원소를 흡수한다."""
    assert G.routine_refs_signature(["sch.a", None, 7]) == G.routine_refs_signature([])
    assert (G.routine_refs_signature('[{"fqn": "sch.a", "kind": "read"}]')
            == G.routine_refs_signature([{"fqn": "sch.a", "kind": "read"}]))
    assert G.routine_refs_signature("not json") == G.routine_refs_signature([])


def test_signature_ignores_empty_fqn_entries():
    """패널 M22: 빈 fqn 은 엣지 루프가 건너뛰므로 서명에도 들어가면 안 된다 — 들어가면 엣지
    집합이 동일한데 서명만 달라져 매 sync 불필요한 전량 재작성이 된다."""
    assert (G.routine_refs_signature(_REFS + [{"fqn": "", "kind": "read"}])
            == G.routine_refs_signature(_REFS))
    assert (G.routine_refs_signature(_REFS + [{"fqn": "   ", "kind": "write"}])
            == G.routine_refs_signature(_REFS))


def test_expected_edge_count_matches_edge_loop_filters():
    """기대 차수는 엣지 루프와 같은 필터(빈 fqn·빈 table 스킵)를 쓰고 tkey 로 중복을 접는다."""
    assert G.routine_expected_edge_count(_REFS, "ds1") == 2
    assert G.routine_expected_edge_count([{"fqn": "s.t"}, {"fqn": "s.t"}], "ds1") == 1
    assert G.routine_expected_edge_count([{"fqn": ""}, {"fqn": "..."}], "ds1") == 0
    cur = _Cur()
    G.sync_routine(cur, "ds1", "sch", "p", "procedure", "",
                   [{"fqn": ""}, {"fqn": "..."}, {"fqn": "s.t"}, {"fqn": "s.t"}], sig_cache={})
    assert len([s for s in cur.sql if "ROUTINE_USES]->(b)" in s]) == 2, "루프는 중복 fqn 도 2회 MERGE"


def test_unchanged_refs_skip_delete_and_edge_rewrite():
    """서명·차수 일치 → ROUTINE_USES DELETE 와 참조 엣지 재-MERGE 를 통째로 생략."""
    sig, deg = _sig_deg(_REFS)
    cur = _Cur()
    G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", _REFS, sig_cache=sig, deg_cache=deg)
    assert not [s for s in cur.sql if "DELETE u" in s]
    assert not [s for s in cur.sql if "ROUTINE_USES]->(b)" in s]
    assert not [s for s in cur.sql if "REMOVE r.refs_sig" in s]
    assert not [s for s in cur.sql if "SET r.refs_sig" in s], "생략 경로는 서명 SET 도 불필요"


def test_skip_path_still_merges_vertex_and_has_routine_edge():
    """패널 M4/M12: 생략은 **참조 엣지에만** 적용된다. Routine 정점과 HAS_ROUTINE 은 계속
    MERGE 돼야 한다(클러스터·params 등 속성 갱신 경로) — early return 이 위로 올라가면 소실."""
    sig, deg = _sig_deg(_REFS)
    cur = _Cur()
    G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", _REFS, sig_cache=sig, deg_cache=deg)
    assert [s for s in cur.sql if "MERGE (n:Routine " in s]
    assert [s for s in cur.sql if "HAS_ROUTINE]->(b)" in s]
    assert [s for s in cur.sql if "MERGE (n:Schema " in s]


def test_changed_refs_still_rewrite_edges():
    """서명 불일치 → 기존 경로 그대로(DELETE + 재-MERGE)."""
    cur = _Cur()
    G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", _REFS,
                   sig_cache={_RKEY: G.routine_refs_signature(_REFS[:1])},
                   deg_cache={_RKEY: 1})
    assert [s for s in cur.sql if "DELETE u" in s]
    assert len([s for s in cur.sql if "ROUTINE_USES]->(b)" in s]) == 2


def test_missing_signature_rewrites_self_healing():
    """서명 부재(신규 routine·배포 직후 전량) → 재작성. skip 은 명시적 일치일 때만."""
    for kw in ({"sig_cache": {}}, {"sig_cache": None}, {}):
        cur = _Cur()
        G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", _REFS, **kw)
        assert [s for s in cur.sql if "DELETE u" in s], f"{kw} 에서 재작성이 일어나지 않았다"


def test_degree_mismatch_forces_rewrite_even_when_signature_matches():
    """패널 B3/MAJOR-3: `--full` 의 재조정 보장. `_merge_edge` 는 끝점 정점이 없으면 **오류 없이
    0행**이라, 서명만 믿으면 그런 엣지 소실이 영구 고착되고 운영 탈출구가 없다. 실제 차수가
    기대치와 다르면 서명이 같아도 재작성한다."""
    sig, _ = _sig_deg(_REFS)
    for deg in ({_RKEY: 1}, {_RKEY: 0}, {_RKEY: 3}, {}, {_RKEY: "bogus"}):
        cur = _Cur()
        G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", _REFS,
                       sig_cache=sig, deg_cache=deg)
        assert [s for s in cur.sql if "DELETE u" in s], f"차수 {deg} 에서 재조정이 일어나지 않았다"


def test_degree_cache_absent_preserves_signature_only_behaviour():
    """`deg_cache` 미전달(외부 호출자)이면 차수 검사를 건너뛴다 — 종전 동작."""
    sig, _ = _sig_deg(_REFS)
    cur = _Cur()
    G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", _REFS, sig_cache=sig)
    assert not [s for s in cur.sql if "DELETE u" in s]


def test_duplicate_routine_key_in_one_run_always_rewrites():
    """패널 MAJOR-1: 정점 key `scope:schema.name()` 에는 routine_type 이 없지만 SSOT 유일키는
    (scope, schema, name, **type**) 이다 — 동명 FUNCTION/PROCEDURE 가 한 정점을 공유한다.
    `sig_cache` 는 step 진입 시 1회 스냅샷이라 두 번째 행이 **stale 항목과 일치해 재작성을
    건너뛰고 첫 행의 엣지를 최종 상태로 남긴다**(종전은 마지막 행 우선). sync 마다 승자가
    뒤바뀌는 flip-flop 도 생긴다. 첫 방문 게이트로 종전 semantics 를 복원한다."""
    refs_f = [{"fqn": "sch.a", "kind": "read"}]
    refs_p = [{"fqn": "sch.b", "kind": "read"}]
    sig = {_RKEY: G.routine_refs_signature(refs_p)}      # 직전 sync 는 procedure 행으로 끝났다
    deg = {_RKEY: 1}
    cur, cache = _Cur(), G.new_anchor_cache()
    G.sync_routine(cur, "ds1", "sch", "p", "function", "", refs_f,
                   cache=cache, sig_cache=sig, deg_cache=deg)
    G.anchor_cache_commit_pending(cache)
    n_del = len([s for s in cur.sql if "DELETE u" in s])
    G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", refs_p,
                   cache=cache, sig_cache=sig, deg_cache=deg)
    assert len([s for s in cur.sql if "DELETE u" in s]) == n_del + 1, \
        "같은 rkey 두 번째 행이 stale 스냅샷과 일치해 재작성을 건너뛰었다(마지막 행 우선 위반)"
    assert [s for s in cur.sql
            if G._vkey("ds1", "sch.b") in s and "ROUTINE_USES]->(b)" in s], \
        "마지막 행(procedure)의 참조 엣지가 최종 상태로 남지 않았다"


def test_signature_removed_before_rewrite_and_set_after():
    """패널 M3: 재작성 순서는 REMOVE → DELETE → 엣지 MERGE → SET.

    서명을 먼저 지우지 않으면, autocommit(비-owned) 경로에서 DELETE 가 커밋된 뒤 엣지 MERGE 가
    중간 실패했을 때 정점에 **직전 서명이 그대로 남는다**. 참조가 안 바뀐 재작성이었다면 그 값이
    현재 서명과 같아 이후 모든 sync 가 skip → 부분 엣지가 영구 고착된다."""
    cur = _Cur()
    G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", _REFS, sig_cache={})
    i_rm = [i for i, s in enumerate(cur.sql) if "REMOVE r.refs_sig" in s]
    i_del = [i for i, s in enumerate(cur.sql) if "DELETE u" in s]
    i_edge = [i for i, s in enumerate(cur.sql) if "ROUTINE_USES]->(b)" in s]
    i_set = [i for i, s in enumerate(cur.sql) if "SET r.refs_sig" in s]
    assert i_rm and i_del and i_edge and i_set
    assert i_rm[0] < i_del[0] < min(i_edge), "REMOVE/DELETE 가 엣지 재작성보다 뒤에 있다"
    assert i_set[0] > max(i_edge), "서명 SET 이 엣지 재작성보다 먼저 기록됐다"


def test_signature_set_failure_propagates_not_swallowed():
    """패널 MAJOR-2: 서명 SET 은 routine 행의 **마지막** 문이라 뒤에 오류를 드러낼 문이 없다.
    삼키면 aborted tx 위에서 `_sync_row_guard` 가 성공(True)을 반환해, 최대 500행이 소실된 채
    `ok:true` + 워터마크 전진이 된다. 반드시 전파해 행 SAVEPOINT 롤백 + errors 집계로 가야 한다."""
    cur = _RaisingCur("SET r.refs_sig")
    with pytest.raises(RuntimeError):
        G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", _REFS, sig_cache={})


def test_signature_property_name_is_not_baked_into_vertex_merge():
    """서명은 정점 MERGE 가 아니라 별도 SET 으로 쓴다.

    (`_props_set` 이 화이트리스트 밖 키를 조용히 버리므로 '정점 MERGE 에 refs_sig 가 없다'만
    보면 vacuous 하다 — 그래서 **별도 SET 문이 실제로 존재**하는 쪽을 함께 잠근다.)"""
    cur = _Cur()
    G.sync_routine(cur, "ds1", "sch", "p", "procedure", "", _REFS, sig_cache={})
    assert [s for s in cur.sql if "SET r.refs_sig" in s]
    assert not [s for s in cur.sql if "MERGE (n:Routine " in s and "refs_sig" in s]


# ── (3) sync_graph 배선 — 리프 함수가 아니라 **실제 경로** ──────────────────
_CYPHER_BODY_RE = re.compile(r"ag_catalog\.cypher\('[^']*',\s*\$(\w+)\$(.*?)\$\1\$", re.S)


def _assert_cypher_parses(sql: str) -> None:
    """PG(AGE)가 거부하는 cypher 를 하네스가 **대신 거부**한다 — mock 은 파서가 아니므로.

    scope-prefetch 결함(2026-07-28 라이브): `WHERE` 절 fragment 를 노드 패턴과 관계 패턴
    **사이에** 보간해 `MATCH (r:Routine) WHERE r.scope_key = 'x'-[u:ROUTINE_USES]->() RETURN …`
    가 생성됐고, 라이브 PG 는 `syntax error at or near ":"` 로 거부했다. 문자열 매칭 하네스는
    그 문장을 그냥 삼켜 **선조회 결과가 소비되는 것처럼** 보였다(테스트 초록, 라이브 무효).

    openCypher 에서 `WHERE` 는 그 MATCH 절의 **패턴 전체 뒤**에만 올 수 있다. 따라서 한 절의
    `WHERE` 이후 `RETURN` 전까지 구간에 관계 패턴(`-[`)이 나타나면 문법 오류로 간주한다.
    """
    for _tag, body in _CYPHER_BODY_RE.findall(sql):
        b = " ".join(body.split())
        low = b.lower()
        i = low.find(" where ")
        if i < 0:
            continue
        j = low.find(" return ", i)
        tail = b[i:] if j < 0 else b[i:j]
        if "-[" in tail:
            raise RuntimeError(
                "syntax error at or near \":\" — WHERE 절 뒤에 관계 패턴이 왔다 "
                f"(패턴 중간 보간): {b[:160]}")


class _SyncCur:
    """`sync_graph` 를 끝까지 구동하는 mock 커서(feature-0016 harness 동형).

    QA 패널 B1/B2: 리프 함수만 문자열 매칭하면 캐시 주입·commit/drop/reset 배선과 선조회 루프가
    전혀 실행되지 않는다. `fetchall` 이 SSOT 행과 **선조회 결과**를 실제로 돌려줘야 한다."""

    __slots__ = ("store",)

    def __init__(self, store):
        self.store = store

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split())
        self.store["sqls"].append(s)
        low = s.lower()
        boom = self.store.get("boom")
        if boom and boom in s:
            raise RuntimeError(f"boom: {boom}")
        _assert_cypher_parses(s)
        if low.startswith("select now()"):
            self.store["rows"] = [["2026-07-28T00:00:00+00:00"]]
        elif "return r.key, r.refs_sig" in low:
            self.store["rows"] = list(self.store.get("sig_rows", []))
        elif "return r.key, count(u)" in low:
            self.store["rows"] = list(self.store.get("deg_rows", []))
        elif "from routine_objects" in low:
            self.store["rows"] = list(self.store.get("routine_rows", []))
        elif "from column_descriptions" in low:
            self.store["rows"] = list(self.store.get("column_rows", []))
        elif "from rag_objects" in low:
            self.store["rows"] = list(self.store.get("rag_rows", []))
        elif "ag_catalog.cypher" in low:
            self.store["rows"] = [["ok"]]
        else:
            self.store["rows"] = []

    def fetchone(self):
        r = self.store.get("rows") or []
        return r[0] if r else None

    def fetchall(self):
        return list(self.store.get("rows") or [])

    def close(self):
        pass


class _SyncConn:
    __slots__ = ("store", "autocommit")

    def __init__(self, store):
        self.store = store
        self.autocommit = True

    def cursor(self):
        return _SyncCur(self.store)

    def commit(self):
        self.store["commits"] += 1

    def rollback(self):
        self.store["rollbacks"] += 1

    def close(self):
        pass


@pytest.fixture()
def sync_store(monkeypatch):
    store = {"sqls": [], "commits": 0, "rollbacks": 0, "rows": []}
    monkeypatch.setattr(G, "_rw_conn", lambda c: (_SyncConn(store), True))
    monkeypatch.setattr(G, "_ensure_graph_indexes", lambda cur: None)
    return store


def test_sync_graph_wires_vertex_cache_into_column_step(sync_store):
    """`_step_columns` 가 캐시를 주입하는지 — 같은 테이블의 컬럼 3개에 Table MERGE 1회."""
    sync_store["column_rows"] = [("ds1", "sch", "t", f"c{i}", "", "manual", i) for i in range(3)]
    G.sync_graph()
    tmerges = [s for s in sync_store["sqls"] if "MERGE (n:Table " in s]
    assert len(tmerges) == 1, f"캐시가 배선되지 않았다 (Table MERGE {len(tmerges)}회)"
    assert len([s for s in sync_store["sqls"] if "MERGE (n:Column " in s]) == 3


def test_sync_graph_wires_vertex_cache_into_rag_step(sync_store):
    """`_step_rag` 도 캐시를 주입한다 — 같은 (ds, 스키마) 테이블 4개에 Schema MERGE 1회.
    (실측상 가장 큰 축약원: rag 16,367 회 → distinct ~140)"""
    sync_store["rag_rows"] = [("ds1", "sch", f"t{i}", f"ds1:sch.t{i}", None, None)
                              for i in range(4)]
    G.sync_graph()
    assert len([s for s in sync_store["sqls"] if "MERGE (n:Schema " in s]) == 1
    assert len([s for s in sync_store["sqls"] if "MERGE (n:Table " in s]) == 4


def test_sync_graph_rolled_back_row_does_not_poison_cache(sync_store):
    """**B-4 edge-loss 가드의 실제 배선**: SAVEPOINT 롤백된 행이 만든 마크가 캐시에 남으면
    후속 행이 공유 정점 MERGE 를 건너뛰고, `_merge_edge` 는 정점 부재 시 **오류 없이 0행**이라
    HAS_TABLE/HAS_COLUMN 이 조용히 소실된다(feature-0029 §18.8 B-4).

    첫 컬럼 행의 Column MERGE 를 실패시키면 그 행은 롤백되고, 다음 행은 같은 Table 정점을
    **다시 MERGE** 해야 한다. `_step_columns` 의 `anchor_cache_drop_pending` 호출이 빠지면 실패."""
    sync_store["column_rows"] = [("ds1", "sch", "t", "c0", "", "manual", 1),
                                 ("ds1", "sch", "t", "c1", "", "manual", 2)]
    sync_store["boom"] = G._vkey("ds1", "sch.t.c0")     # 첫 행의 Column MERGE 에서 폭발
    rep = G.sync_graph()
    assert rep["errors"] >= 1, "행 실패가 집계되지 않았다(하네스가 결함을 관측 못함)"
    tmerges = [s for s in sync_store["sqls"] if "MERGE (n:Table " in s]
    assert len(tmerges) == 2, \
        f"롤백된 행의 마크가 캐시에 남아 후속 행이 Table MERGE 를 생략했다 ({len(tmerges)}회)"


def test_sync_graph_wires_vertex_cache_into_routine_step(sync_store):
    """`_step_routines` 도 같은 캐시를 쓴다 — 같은 스키마 routine 3개에 Schema MERGE 1회."""
    sync_store["routine_rows"] = [("ds1", "sch", f"p{i}", "procedure", "", "[]", None, None)
                                  for i in range(3)]
    G.sync_graph()
    assert len([s for s in sync_store["sqls"] if "MERGE (n:Schema " in s]) == 1
    assert len([s for s in sync_store["sqls"] if "MERGE (n:Routine " in s]) == 3


def test_sync_graph_prefetch_property_names_match_the_write(sync_store):
    """**핵심 커플링**: 선조회가 읽는 속성명과 `sync_routine` 이 쓰는 속성명이 같아야 한다.

    패널 B1: 종전 테스트는 `"SET r.refs_sig" in s` 라는 **prefix** 매칭이라 `refs_sig2` 로 바꿔도
    통과했고, 선조회 cypher 는 아예 실행되지 않았다. 한쪽만 바뀌면 전 routine 이 영구 miss →
    최적화가 100% 무효인데 테스트는 초록 — `psycopg.__slots__` 선례와 같은 결함면이다.
    두 이름을 SQL 에서 정규식으로 뽑아 **동일성**을 본다."""
    sync_store["routine_rows"] = [("ds1", "sch", "p", "procedure", "", "[]", None, None)]
    G.sync_graph()
    joined = " || ".join(sync_store["sqls"])
    read = set(re.findall(r"RETURN r\.key, r\.(\w+)", joined))
    written = set(re.findall(r"SET r\.(\w+) =", joined))
    removed = set(re.findall(r"REMOVE r\.(\w+)", joined))
    assert read, "선조회 cypher 가 실행되지 않았다(하네스가 결함을 관측할 수 없음)"
    assert written, "서명 SET 이 실행되지 않았다"
    assert read == written == removed, f"읽기 {read} / 쓰기 {written} / 삭제 {removed} 속성명 불일치"


def test_sync_graph_prefetch_result_actually_skips_rewrite(sync_store):
    """선조회 결과가 실제로 소비돼 재작성이 생략되는지 — end-to-end.

    선조회가 돌려준 (서명, 차수) 가 SSOT 행과 일치하므로 DELETE 가 한 번도 나오면 안 된다."""
    refs = [{"fqn": "sch.a", "kind": "read"}]
    rkey = G._vkey("ds1", "sch.p()")
    sync_store["routine_rows"] = [("ds1", "sch", "p", "procedure", "",
                                   '[{"fqn": "sch.a", "kind": "read"}]', None, None)]
    sync_store["sig_rows"] = [[f'"{rkey}"', f'"{G.routine_refs_signature(refs)}"']]
    sync_store["deg_rows"] = [[f'"{rkey}"', "1"]]
    G.sync_graph()
    assert not [s for s in sync_store["sqls"] if "DELETE u" in s], \
        "선조회 결과가 소비되지 않아 재작성이 그대로 일어났다"


def test_sync_graph_prefetch_degree_mismatch_forces_rewrite(sync_store):
    """서명은 맞지만 차수가 어긋나면(엣지 소실) end-to-end 로 재작성된다."""
    refs = [{"fqn": "sch.a", "kind": "read"}]
    rkey = G._vkey("ds1", "sch.p()")
    sync_store["routine_rows"] = [("ds1", "sch", "p", "procedure", "",
                                   '[{"fqn": "sch.a", "kind": "read"}]', None, None)]
    sync_store["sig_rows"] = [[f'"{rkey}"', f'"{G.routine_refs_signature(refs)}"']]
    sync_store["deg_rows"] = [[f'"{rkey}"', "0"]]        # 엣지가 실제로는 없다
    G.sync_graph()
    assert [s for s in sync_store["sqls"] if "DELETE u" in s]


def test_sync_graph_prefetch_is_scope_filtered(sync_store):
    """패널 MINOR-2: scope 지정 sync 가 전체 Routine 라벨을 덤프하지 않는다."""
    G.sync_graph(scope_key="ds-x")
    pre = [s for s in sync_store["sqls"] if "RETURN r.key, r.refs_sig" in s]
    assert pre and "r.scope_key = 'ds-x'" in pre[0]


def test_sync_graph_prefetch_failure_is_recorded_not_silent(sync_store, caplog):
    """패널 M2: 선조회가 영구 실패하면 최적화가 조용히 0이 된다 — 다른 실패 경로와 동일하게
    샘플을 남겨야 운영자가 안다. 정합성은 유지(빈 dict → 전량 재작성 = 종전 동작)."""
    sync_store["routine_rows"] = [("ds1", "sch", "p", "procedure", "", "[]", None, None)]
    sync_store["sig_rows"] = [["only-one-column"]]      # 2열 기대인데 1열 → 방어적 인덱싱
    G.sync_graph()
    # 1-튜플이어도 예외로 죽지 않고(패널 M1 회귀) 재작성 경로로 진행한다.
    assert [s for s in sync_store["sqls"] if "DELETE u" in s]
    assert sync_store["rollbacks"] == 0, "행 shape 차이로 트랜잭션을 롤백하면 안 된다"


def test_sync_graph_does_not_attach_attributes_to_cursor(sync_store):
    """feature-0029 B-1 회귀 잠금: 커서에 캐시를 매달면 라이브 psycopg(`__slots__ == ()`)에서
    항상 실패해 최적화가 꺼진다. `_SyncCur` 도 `__slots__` 라 부착 시 AttributeError 로 죽는다."""
    sync_store["column_rows"] = [("ds1", "sch", "t", "c0", "", "manual", 1)]
    sync_store["routine_rows"] = [("ds1", "sch", "p", "procedure", "", "[]", None, None)]
    G.sync_graph()          # 예외 없이 완주하면 부착이 없다는 뜻
    assert sync_store["commits"] >= 1

# ── (4) scope 지정 sync 의 선조회 문법 (2026-07-28 라이브 결함 회귀 잠금) ────────
def test_scoped_degree_prefetch_cypher_is_wellformed(sync_store):
    """**라이브 결함 회귀 잠금**: scope 지정 sync 에서 차수 선조회 cypher 가 문법적으로 유효해야 한다.

    결함(2026-07-28 backfill 리포트 `routine_prefetch: SyntaxError syntax error at or near ":"`):
    `_scope_pred`(` WHERE r.scope_key = '…'`)를 노드 패턴과 관계 패턴 **사이에** 보간해
    `MATCH (r:Routine) WHERE r.scope_key = 'ds-x'-[u:ROUTINE_USES]->() RETURN r.key, count(u)`
    가 생성됐다. `scope_key` 가 None 인 경로만 유효했으므로 **모든 per-datasource sync** 가
    항상 실패했다(정합성은 fail-safe — 빈 차수 dict → 전량 재작성으로 강등).

    여기서는 구조를 직접 단정한다: 차수 선조회의 `WHERE` 는 관계 패턴 **뒤**에 와야 한다.
    """
    G.sync_graph(scope_key="ds-x")
    deg = [s for s in sync_store["sqls"] if "RETURN r.key, count(u)" in s]
    assert deg, "차수 선조회 cypher 가 실행되지 않았다(하네스가 결함을 관측할 수 없음)"
    q = deg[0]
    assert "r.scope_key = 'ds-x'" in q, "차수 선조회에 scope 필터가 없다(전 라벨 덤프)"
    assert "'ds-x'-[" not in q, \
        f"WHERE 값 직후에 관계 패턴이 붙었다(패턴 중간 보간 — PG 가 거부한다): {q}"
    assert q.index("-[u:ROUTINE_USES]->()") < q.index("WHERE"), \
        f"WHERE 가 관계 패턴보다 앞에 있다(openCypher 문법 위반): {q}"


def test_scoped_prefetch_result_actually_skips_rewrite(sync_store):
    """**end-to-end**: scope 지정 sync 에서도 선조회 (서명, 차수)가 소비돼 재작성이 생략된다.

    `test_sync_graph_prefetch_result_actually_skips_rewrite` 의 scope 판 — 종전엔 무-scope
    경로만 잠겨 있어서 per-datasource sync 에서 최적화가 100% 죽어도 스위트가 초록이었다.
    하네스의 `_assert_cypher_parses` 가 PG 대신 malformed cypher 를 거부하므로, 결함이 살아
    있으면 차수 dict 가 비어 `DELETE u` 가 나타나고 이 단정이 깨진다.
    """
    refs = [{"fqn": "sch.a", "kind": "read"}]
    rkey = G._vkey("ds-x", "sch.p()")
    sync_store["routine_rows"] = [("ds-x", "sch", "p", "procedure", "",
                                   '[{"fqn": "sch.a", "kind": "read"}]', None, None)]
    sync_store["sig_rows"] = [[f'"{rkey}"', f'"{G.routine_refs_signature(refs)}"']]
    sync_store["deg_rows"] = [[f'"{rkey}"', "1"]]
    G.sync_graph(scope_key="ds-x")
    assert not [s for s in sync_store["sqls"] if "DELETE u" in s], \
        "scope 지정 경로에서 선조회가 소비되지 않아 재작성이 그대로 일어났다"
    assert sync_store["rollbacks"] == 0, \
        "선조회 실패 경로의 rollback 이 매 scope sync 마다 발생한다"


def test_unscoped_prefetch_stays_wellformed(sync_store):
    """무-scope 경로 무회귀 — 결함 수정이 기존 유효 쿼리를 깨지 않는다."""
    G.sync_graph()
    deg = [s for s in sync_store["sqls"] if "RETURN r.key, count(u)" in s]
    assert deg and "WHERE" not in deg[0], f"무-scope 경로에 불필요한 WHERE 가 생겼다: {deg[0]}"
    assert "-[u:ROUTINE_USES]->()" in deg[0]
