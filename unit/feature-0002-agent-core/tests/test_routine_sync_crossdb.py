"""feature-0016 §56 (routine-sync-crossdb) 단위 테스트 — fhgame1 실측 이슈의 3대 근본원인 잠금.

  RC1: sync_graph batched tx 오염 연쇄 → _sync_row_guard(SAVEPOINT 행 격리)·step_failures 분리.
  RC2: 프로시저 정의의 크로스-DB 참조([db].[dbo].[T]) 폐기·동명 로컬 오귀속 → qualifier 해석 +
       rag_objects 실재 검증(external_tables) + 크로스 refs_fqn(`타스키마.T`) 저장.
  RC3: thin 판정 — LLM 무관계 문구("연결 정보 없음")를 공란과 동치(back-refine 감도).
"""
import json

from modules import routines as rt
from modules import metadata_graph as mg
from modules import node_analysis as na


LOCAL_TABLES = ["Achievement", "T_PurchaseLog", "T_User"]
# external: 같은 ds 의 타 effective 스키마(DB) 실재 테이블 — {(sch_low, tbl_low): (sch, tbl)}
EXT = {
    ("fhauth", "t_user"): ("fhauth", "T_User"),
    ("fhauth", "t_login"): ("fhauth", "T_Login"),
    ("fhlog", "l_gamelog"): ("fhlog", "L_GameLog"),
}


# ── RC2: qualifier 해석 + 실재 검증 ──────────────────────────────────────────
def test_parse_cross_db_three_part_accepted():
    body = "SELECT * FROM [fhauth].[dbo].[T_Login] l JOIN Achievement a ON 1=1"
    refs = rt.parse_referenced_tables(body, LOCAL_TABLES, external_tables=EXT, local_label="fhgame1")
    by = {(r.get("schema"), r["fqn"]): r["kind"] for r in refs}
    assert by[(None, "Achievement")] == "read"
    assert by[("fhauth", "T_Login")] == "read"          # ② 크로스-DB 참조 채택(schema 필드)


def test_parse_cross_db_same_name_not_misattributed():
    """§56 핵심: [fhauth].dbo.T_User 가 로컬 동명 T_User 로 오귀속되지 않는다(기존 leaf-정규화 결함)."""
    body = "INSERT INTO [fhauth].[dbo].[T_User] (Id) VALUES (1)"
    refs = rt.parse_referenced_tables(body, LOCAL_TABLES, external_tables=EXT, local_label="fhgame1")
    assert refs == [{"fqn": "T_User", "kind": "write", "schema": "fhauth"}]


def test_parse_known_other_schema_missing_table_dropped():
    """③ 알려진 타 스키마 지정인데 그 테이블 미실재 → 폐기(로컬 폴백 금지 — 오귀속 차단)."""
    body = "SELECT * FROM fhauth.dbo.Achievement"   # fhauth 에 Achievement 없음(로컬엔 있음)
    refs = rt.parse_referenced_tables(body, LOCAL_TABLES, external_tables=EXT, local_label="fhgame1")
    assert refs == []


def test_parse_dbo_and_local_label_stay_local():
    body = "SELECT * FROM dbo.Achievement; SELECT * FROM [fhgame1].[dbo].[T_PurchaseLog];"
    refs = rt.parse_referenced_tables(body, LOCAL_TABLES, external_tables=EXT, local_label="fhgame1")
    by = {r["fqn"]: r for r in refs}
    assert set(by) == {"Achievement", "T_PurchaseLog"}
    assert all("schema" not in r for r in refs)         # ① 전부 로컬


def test_parse_db_dot_dot_table_and_two_part():
    """MSSQL `db..T`(기본 스키마 생략)·MySQL `db.T` 2-part 모두 qualifier 로 해석."""
    body = "SELECT * FROM fhauth..T_Login; SELECT * FROM fhlog.L_GameLog;"
    refs = rt.parse_referenced_tables(body, LOCAL_TABLES, external_tables=EXT, local_label="fhgame1")
    by = {(r.get("schema"), r["fqn"]) for r in refs}
    assert ("fhauth", "T_Login") in by and ("fhlog", "L_GameLog") in by


def test_parse_unknown_qualifier_legacy_local_fallback():
    """④ 미상 qualifier — 레거시 폴백(leaf 로컬 실재 시 로컬, 기존 recall 보존)."""
    body = "SELECT * FROM [somedb].[dbo].[Achievement]"
    refs = rt.parse_referenced_tables(body, LOCAL_TABLES, external_tables=EXT, local_label="fhgame1")
    assert refs == [{"fqn": "Achievement", "kind": "read"}]


def test_parse_cross_write_wins_over_read():
    body = "SELECT * FROM fhauth.dbo.T_Login; DELETE FROM fhauth.dbo.T_Login WHERE 1=0;"
    refs = rt.parse_referenced_tables(body, [], external_tables=EXT, local_label="fhgame1")
    assert refs == [{"fqn": "T_Login", "kind": "write", "schema": "fhauth"}]


# ── RC2: introspect_and_store 배선(ext 로드·크로스 refs_fqn·캐시) ─────────────
class _DbCursor:
    def __init__(self, routines):
        self._routines = routines
        self._last = []

    def execute(self, sql, params=None):
        if "information_schema.ROUTINES" in sql:
            self._last = [(r["name"], r["rtype"].upper(), r["definition"]) for r in self._routines]
        else:
            self._last = []

    def fetchall(self):
        return self._last

    def close(self):
        pass


class _DbConn:
    def __init__(self, routines):
        self._cur = _DbCursor(routines)

    def cursor(self):
        return self._cur


class _KbCursor:
    def __init__(self, rag_rows):
        self.rag_rows = rag_rows
        self.rag_queries = 0
        self.inserted = []
        self._last = []

    def execute(self, sql, params=None):
        if "FROM rag_objects" in sql:
            self.rag_queries += 1
            self._last = self.rag_rows
        elif "INSERT INTO routine_objects" in sql:
            self.inserted.append(params)
            self._last = []
        else:
            self._last = []

    def fetchall(self):
        return self._last

    @property
    def rowcount(self):
        return 1

    def close(self):
        pass


class _KbConn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self):
        return self._cur

    def close(self):
        pass


def _mk_env(monkeypatch, rag_rows):
    import modules.semantic_cluster as sc
    monkeypatch.setattr(sc, "_effective_schema", lambda dsk, okey, sch: sch)
    rt._EXT_CACHE.clear()
    kb = _KbCursor(rag_rows)
    return kb, _KbConn(kb)


def test_introspect_stores_cross_refs_fqn(monkeypatch):
    kb, kbc = _mk_env(monkeypatch, [("fhauth", "T_Login", "ds:fhauth.dbo.T_Login"),
                                    ("fhgame1", "Achievement", "ds:fhgame1.dbo.Achievement")])
    db = _DbConn([{"name": "usp_X", "rtype": "procedure",
                   "definition": "SELECT * FROM Achievement; INSERT INTO fhauth.dbo.T_Login (a) VALUES (1)"}])
    n = rt.introspect_and_store(db, "dbo", ["Achievement"], kb_conn=kbc,
                                scope_key="ds", datasource_key="ds",
                                store_schema="fhgame1", prune=False)
    assert n == 1 and len(kb.inserted) == 1
    refs = json.loads(kb.inserted[0][8])
    by = {r["fqn"]: r for r in refs}
    assert by["fhgame1.Achievement"]["kind"] == "read" and "cross" not in by["fhgame1.Achievement"]
    assert by["fhauth.T_Login"]["kind"] == "write" and by["fhauth.T_Login"].get("cross") == 1


def test_external_tables_ttl_cache(monkeypatch):
    kb, kbc = _mk_env(monkeypatch, [("fhauth", "T_Login", "k")])
    a = rt._external_tables_for(kbc, "ds")
    b = rt._external_tables_for(kbc, "ds")
    assert a == b == {("fhauth", "t_login"): ("fhauth", "T_Login")}
    assert kb.rag_queries == 1          # TTL 캐시 — 같은 ds 연쇄 introspect 에서 rag 1회


def test_external_tables_load_failure_is_soft(monkeypatch):
    class _Boom:
        def cursor(self):
            raise RuntimeError("pg down")
    rt._EXT_CACHE.clear()
    assert rt._external_tables_for(_Boom(), "ds2") == {}   # 실패 = {} (로컬 파싱 불변·비차단)


# ── RC1: _sync_row_guard — SAVEPOINT 행 격리 ─────────────────────────────────
class _GuardCursor:
    def __init__(self):
        self.sql = []

    def execute(self, q, params=None):
        self.sql.append(q)


def test_row_guard_success_release():
    cur = _GuardCursor()
    samples = []
    ok = mg._sync_row_guard(cur, True, samples, "t", lambda: None)
    assert ok and cur.sql == ["SAVEPOINT sg_row", "RELEASE SAVEPOINT sg_row"] and not samples


def test_row_guard_failure_rolls_back_and_releases():
    """§18.8 패널(§56): 실패 행도 ROLLBACK TO 후 RELEASE — 열린 서브트랜잭션 누적(>64 suboverflow
    성능 절벽) 방지."""
    cur = _GuardCursor()
    samples = []

    def boom():
        raise RuntimeError("bad row")
    ok = mg._sync_row_guard(cur, True, samples, "routine", boom)
    assert not ok
    assert cur.sql == ["SAVEPOINT sg_row", "ROLLBACK TO SAVEPOINT sg_row", "RELEASE SAVEPOINT sg_row"]
    assert samples and samples[0].startswith("routine: RuntimeError")


def test_row_guard_not_owned_no_savepoints():
    cur = _GuardCursor()
    ok = mg._sync_row_guard(cur, False, [], "t", lambda: None)
    assert ok and cur.sql == []


def test_row_guard_isolates_failure_from_followers():
    """연쇄 차단 계약: 실패 행 뒤의 행이 정상 처리된다(오염 연쇄의 회귀 잠금 — 가드 조합 시뮬레이션)."""
    cur = _GuardCursor()
    samples = []
    results = [mg._sync_row_guard(cur, True, samples, "r", fn)
               for fn in (lambda: None, (lambda: (_ for _ in ()).throw(RuntimeError("x"))), lambda: None)]
    assert results == [True, False, True]
    assert cur.sql.count("ROLLBACK TO SAVEPOINT sg_row") == 1
    assert cur.sql.count("RELEASE SAVEPOINT sg_row") == 3   # 성공 2 + 실패 후 해제 1


def test_row_guard_savepoint_failure_counts_step_not_row(monkeypatch):
    """§18.8 패널(§56): SAVEPOINT 확립 실패 = 트랜잭션 무결성 실패 — per-row errors(워터마크 비차단)가
    아닌 rep.step_failures 로 계상 + fn 미실행(오염 연쇄가 카운터 이름만 바꿔 재현되는 것 차단)."""
    class _SpFail:
        def __init__(self):
            self.sql = []

        def execute(self, q, params=None):
            self.sql.append(q)
            if q.startswith("SAVEPOINT"):
                raise RuntimeError("current transaction is aborted")
    cur = _SpFail()
    rep = {"step_failures": 0}
    ran = []
    ok = mg._sync_row_guard(cur, True, [], "rag_table", lambda: ran.append(1), rep)
    assert not ok and not ran
    assert rep["step_failures"] == 1


def test_external_tables_failure_not_cached(monkeypatch):
    """§18.8 패널(§56): ext 로드 실패는 미캐시 — 다음 호출이 재시도(600s 침묵 비활성 창 제거)."""
    import modules.semantic_cluster as sc
    monkeypatch.setattr(sc, "_effective_schema", lambda dsk, okey, sch: sch)
    rt._EXT_CACHE.clear()

    class _Flaky:
        def __init__(self):
            self.calls = 0

        def cursor(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("pg down")
            return _KbCursor([("fhauth", "T_Login", "k")])
    fl = _Flaky()
    assert rt._external_tables_for(fl, "ds9") == {}
    assert "ds9" not in rt._EXT_CACHE                       # 실패 미캐시
    ok = rt._external_tables_for(fl, "ds9")
    assert ok == {("fhauth", "t_login"): ("fhauth", "T_Login")}


# ── RC3: thin 판정 — 무관계 문구 동치 ────────────────────────────────────────
def test_thin_treats_no_relation_phrase_as_empty():
    a = json.dumps({"summary": "s" * 200, "relationships": "연결 정보 없음", "usage": "", "caveats": ""},
                   ensure_ascii=False)
    assert na._analysis_is_thin(a, 120) is True
    b = json.dumps({"summary": "s" * 200, "relationships": "연결 정보 없음", "usage": "운영 조회", "caveats": ""},
                   ensure_ascii=False)
    assert na._analysis_is_thin(b, 120) is False   # usage 있으면 비-thin(과잉 재분석 방지)


# ── RC4: routine_backfill read-axis scope 정규화 ─────────────────────────────
def test_backfill_uses_read_axis_scope_not_label(monkeypatch):
    """DB-등록 datasource(scope_key=해시 보유)는 라벨이 아닌 **read-axis scope** 로 SSOT/그래프 키를
    쓴다 — 라벨 키 이중 적재(라이브 실측 dk-dev 1,449×2)·label 고아 그래프·RC2 rag 불일치의 근본 수정."""
    from test_routine_dbanalysis import _patch_backfill, _BFConn, _BFCursor
    from modules import routine_backfill as rb
    from modules import metadata_graph as mgm
    ds = {"mssql-dk-dev": {"key": "mssql-dk-dev", "engine": "mssql",
                           "scope_key": "mssql-ba175631e9fc"}}
    conns = {("mssql-dk-dev", "gamedb"): _BFConn(_BFCursor(["dbo"], ["t1"]))}
    synced = []
    calls = _patch_backfill(monkeypatch, ds, conns, dbs=["gamedb"])
    monkeypatch.setattr(mgm, "sync_graph", lambda scope_key=None, **kw: synced.append(scope_key) or {"ok": True})
    rep = rb.run()
    assert calls and calls[0][1]["scope_key"] == "mssql-ba175631e9fc"
    assert calls[0][1]["datasource_key"] == "mssql-ba175631e9fc"
    assert synced == ["mssql-ba175631e9fc"]                     # label 스코프 고아 투영 금지
    assert rep["datasources"]["mssql-dk-dev"]["scope"] == "mssql-ba175631e9fc"


def test_backfill_env_legacy_falls_back_to_label(monkeypatch):
    """.env 레거시(scope_key 부재)는 종전대로 라벨(lower) — read-axis 규약의 다른 반쪽."""
    from test_routine_dbanalysis import _patch_backfill, _BFConn, _BFCursor
    from modules import routine_backfill as rb
    ds = {"M1": {"key": "M1", "engine": "mysql"}}
    conns = {("M1", None): _BFConn(_BFCursor(["appdb"], ["t1"]))}
    calls = _patch_backfill(monkeypatch, ds, conns)
    rb.run()
    assert calls and calls[0][1]["scope_key"] == "m1"           # 라벨 lower


def test_backfill_scope_filter_matches_label_or_scope(monkeypatch):
    from test_routine_dbanalysis import _patch_backfill, _BFConn, _BFCursor
    from modules import routine_backfill as rb
    ds = {"mssql-dk-dev": {"key": "mssql-dk-dev", "engine": "mssql",
                           "scope_key": "mssql-ba175631e9fc"}}
    conns = {("mssql-dk-dev", "gamedb"): _BFConn(_BFCursor(["dbo"], ["t1"]))}
    calls = _patch_backfill(monkeypatch, ds, conns, dbs=["gamedb"])
    rb.run(scope_filter="mssql-ba175631e9fc")                   # scope 해시로도 필터 가능
    assert calls


# ── RC5: MSSQL store label 케이스 정규화 (§56, 2026-07-07) ────────────────────
def test_backfill_mssql_store_label_lowercased(monkeypatch):
    """MSSQL store label(DB명)은 set_active_database(TASK-0220)가 lower 로 고정한 시스템 계약 —
    sys.databases 원본 케이스(FHGame1)를 무가공 store 하면 cadence(lower)와 같은 scope 에
    케이스-변형 이중 적재(라이브 실측 qa-idc 1,912쌍)·그래프 중복 클러스터가 생긴다(§56 RC5).
    질의 연결은 원본 dbname 유지(store/query 분리)."""
    from test_routine_dbanalysis import _patch_backfill, _BFConn, _BFCursor
    from modules import routine_backfill as rb
    import shared.config as scfg
    ds = {"mssql-qa": {"key": "mssql-qa", "engine": "mssql", "scope_key": "mssql-abc123"}}
    conns = {("mssql-qa", "FHGame1"): _BFConn(_BFCursor(["dbo"], ["t1"]))}
    connect_calls, purge_calls = [], []
    calls = _patch_backfill(monkeypatch, ds, conns, dbs=["FHGame1"],
                            connect_calls=connect_calls, purge_calls=purge_calls)
    rep = rb.run()
    assert calls and calls[0][1]["store_schema"] == "fhgame1"   # store 는 lower
    assert any(c["database"] == "FHGame1" for c in connect_calls)  # 질의 연결은 원본 케이스
    # parity 잠금(패널 NIT): backfill 라벨 == 단일 계약 normalize_db_label == set_active_database 결과
    assert calls[0][1]["store_schema"] == scfg.normalize_db_label("FHGame1")
    scfg.set_active_database("FHGame1")
    assert scfg.get_active_database() == calls[0][1]["store_schema"]
    scfg.set_active_database(None)
    # 패널 MAJOR 보완: introspect 성공 직후 케이스-변형 label 행 멱등 회수 호출
    assert purge_calls == [("mssql-abc123", "fhgame1")]
    assert rep["datasources"]["mssql-qa"]["store_labels"] == {"FHGame1": "fhgame1"}


def test_backfill_mssql_case_twin_dbs_demote_prune(monkeypatch):
    """CS-collation 서버에서 케이스만 다른 DB('Sales'/'SALES')가 한 lower label 로 병합되면
    뒤 DB 의 prune 이 앞 DB 전용 행을 교차-삭제(진동)한다 — label 충돌 시 prune 강등(§56 RC5 보완)."""
    from test_routine_dbanalysis import _patch_backfill, _BFConn, _BFCursor
    from modules import routine_backfill as rb
    ds = {"mssql-qa": {"key": "mssql-qa", "engine": "mssql", "scope_key": "mssql-abc123"}}
    conns = {("mssql-qa", "Sales"): _BFConn(_BFCursor(["dbo"], ["t1"])),
             ("mssql-qa", "SALES"): _BFConn(_BFCursor(["dbo"], ["t2"]))}
    calls = _patch_backfill(monkeypatch, ds, conns, dbs=["Sales", "SALES"])
    rb.run()
    assert len(calls) == 2 and all(c[1]["prune"] is False for c in calls)


def test_backfill_mssql_dry_run_slot_keeps_original_case(monkeypatch):
    """ADR-023 이 CS-collation 병합 진단 수단으로 의존하는 리포트 slot 은 **원본 케이스**를
    유지하고(store_labels 매핑으로 lower 라벨 대응 표기), dry-run 은 store·purge 를 안 한다."""
    from test_routine_dbanalysis import _patch_backfill, _BFConn, _BFCursor
    from modules import routine_backfill as rb
    ds = {"mssql-qa": {"key": "mssql-qa", "engine": "mssql", "scope_key": "mssql-abc123"}}
    conns = {("mssql-qa", "FHGame1"): _BFConn(_BFCursor(["dbo"], ["t1"]))}
    purge_calls = []
    calls = _patch_backfill(monkeypatch, ds, conns, dbs=["FHGame1"], purge_calls=purge_calls)
    rep = rb.run(dry_run=True)
    entry = rep["datasources"]["mssql-qa"]
    assert entry["schemas"] == {"FHGame1//dbo": "(dry-run)"}
    assert entry["store_labels"] == {"FHGame1": "fhgame1"}
    assert not calls and not purge_calls


def test_purge_case_variant_labels_sql_contract():
    """purge 는 (scope, lower(label)) 에서 케이스만 다른 행을 삭제 — fresh lower 재적재가 선행하므로
    행 단위 twin-검증 불요. 예외는 삼켜 0(루프 비차단)."""
    from modules import routines as rt

    class _Cur:
        rowcount = 7
        def __init__(self): self.executed = []
        def execute(self, sql, params): self.executed.append((sql, params))

    class _Conn:
        def __init__(self): self.cur = _Cur()
        def cursor(self): return self.cur

    conn = _Conn()
    n = rt.purge_case_variant_labels("mssql-abc123", "fhgame1", kb_conn=conn)
    assert n == 7
    sql, params = conn.cur.executed[0]
    assert "DELETE FROM routine_objects" in sql
    assert "schema_name <> %s" in sql and "lower(schema_name) = %s" in sql
    assert params == ("mssql-abc123", "fhgame1", "fhgame1")
    assert rt.purge_case_variant_labels("mssql-abc123", "", kb_conn=conn) == 0  # 빈 label no-op

    class _Boom:
        def cursor(self): raise RuntimeError("kb down")
    assert rt.purge_case_variant_labels("s", "l", kb_conn=_Boom()) == 0  # 예외 삼킴


def test_backfill_mysql_schema_case_preserved(monkeypatch):
    """MySQL 스키마는 파일시스템 기반 케이스 구분(lower_case_table_names=0)이 유효 — RC5 lower
    정규화는 MSSQL 전용이고 MySQL store_schema 는 원본 케이스를 보존한다."""
    from test_routine_dbanalysis import _patch_backfill, _BFConn, _BFCursor
    from modules import routine_backfill as rb
    ds = {"M1": {"key": "M1", "engine": "mysql"}}
    conns = {("M1", None): _BFConn(_BFCursor(["AppDB"], ["t1"]))}
    calls = _patch_backfill(monkeypatch, ds, conns)
    rb.run()
    assert calls and calls[0][1]["store_schema"] == "AppDB"
