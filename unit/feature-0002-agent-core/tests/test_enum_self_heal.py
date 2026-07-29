"""insight-worker ENUM self-heal(`_enum_self_heal`) 단위 테스트.

insight tick 이 스키마를 스캔한 직후, 활성 scope 의 '없는 DB(schema)' enum 을 **완전한 실제 스키마
목록** 기준으로 소급 회수하는 자가수리 헬퍼를 잠근다. 적대 리뷰(BLOCKER/MAJOR) 흡수 게이트를 검증:
grounding 게이트 결합(MAJOR-3)·scanned 게이트(MAJOR-2)·MSSQL 제외·fail-open·dedup·예외 격리·execute.
실 PG/스캔 없이 monkeypatch 로 검증.
"""
import shared.config as _cfg
import shared.db as _db
from modules import insight, kb_glossary as _kg


class _FakePg:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _wire(monkeypatch, *, grounding=True, self_heal=True, scope="mysql-kr-an1-auth",
          sweep_result=None, sweep_raises=False, prev_unknown=None,
          product_scopes=("product.kr_live",)):
    monkeypatch.setattr(_cfg, "AGENT_ENUM_SCHEMA_GROUNDING", grounding, raising=False)
    monkeypatch.setattr(_cfg, "AGENT_ENUM_SELF_HEAL", self_heal, raising=False)
    monkeypatch.setattr(_cfg, "get_active_datasource", lambda: scope)
    # metadata-product-scope: ENUM 저장 축이 제품이라 sweep 대상도 제품 스코프다.
    # 대상 산출(_self_heal_scope_keys)은 별 테스트에서 검증하고, 여기선 고정 주입한다.
    monkeypatch.setattr(insight, "_self_heal_scope_keys",
                        lambda mem_conn, ds_scope: list(product_scopes))
    monkeypatch.setattr(_cfg, "ds_scope_name", lambda name: f"{name}:ds:{scope}")
    monkeypatch.setattr(_db, "_pg_available", lambda: True)
    pg = _FakePg()
    monkeypatch.setattr(_db, "_pg_connect", lambda *a, **k: pg)
    # catalog-shrink 가드 KV: 직전 unknown 로드 + 이번 unknown 저장 캡처
    import json as _json
    monkeypatch.setattr(insight, "load_memory_kv",
                        lambda *a, **k: (_json.dumps(prev_unknown) if prev_unknown is not None else None))
    saved: dict = {}
    monkeypatch.setattr(insight, "save_memory_kv",
                        lambda conn, cid, key, val: saved.__setitem__("val", val))
    calls: dict = {}

    def _fake_sweep(conn, sk, known_schemas, *, dry_run, confirm_lower=None):
        calls["args"] = (sk, list(known_schemas), dry_run)
        calls["confirm_lower"] = confirm_lower
        if sweep_raises:
            raise RuntimeError("boom")
        return sweep_result or {"scope": sk, "scanned": 1, "ungrounded": [],
                                "dict_deleted": 0, "feedback_rejected": 0, "dry_run": dry_run}

    monkeypatch.setattr(_kg, "sweep_unknown_schema_enum", _fake_sweep)
    return calls, pg, saved


def _call(**kw):
    kw.setdefault("engine", "mysql")
    kw.setdefault("known_schemas", ["dbAuth", "dbGame"])
    kw.setdefault("scanned", True)
    kw.setdefault("mem_conn", object())
    return insight._enum_self_heal(kw.pop("swept", set()), **kw)


def test_self_heal_happy_path_executes(monkeypatch):
    calls, pg, saved = _wire(monkeypatch, sweep_result={
        "scope": "mysql-kr-an1-auth", "scanned": 2,
        "ungrounded": [{"schema_name": "dbLog", "table_name": None}],
        "dict_deleted": 4, "feedback_rejected": 1, "dry_run": False})
    swept: set = set()
    res = _call(swept=swept, known_schemas=["dbAuth"])
    assert calls["args"][0] == "product.kr_live"   # 제품 스코프로 sweep
    assert calls["args"][1] == ["dbAuth"]              # 실제 스키마 목록 전달
    assert calls["args"][2] is False                   # execute
    assert res["dict_deleted"] == 4
    assert pg.committed is True
    assert "product.kr_live" in swept                  # dedup 마킹(제품 스코프 단위)


def test_self_heal_grounding_off_noop(monkeypatch):
    # MAJOR-3: 예방 게이트(grounding) off 면 self-heal 도 no-op(thrash·명시허용분 삭제 방지)
    calls, _pg, _saved = _wire(monkeypatch, grounding=False)
    assert _call() is None
    assert "args" not in calls


def test_self_heal_switch_off_noop(monkeypatch):
    calls, _pg, _saved = _wire(monkeypatch, self_heal=False)
    assert _call() is None
    assert "args" not in calls


def test_self_heal_not_scanned_noop(monkeypatch):
    # MAJOR-2: 이번 tick 에 실제 스캔이 없으면(scan_started False) skip
    calls, _pg, _saved = _wire(monkeypatch)
    assert _call(scanned=False) is None
    assert "args" not in calls


def test_self_heal_mssql_excluded(monkeypatch):
    # MSSQL 은 schema≠database → 오삭제 위험, self-heal 제외
    calls, _pg, _saved = _wire(monkeypatch)
    assert _call(engine="mssql") is None
    assert "args" not in calls


def test_self_heal_empty_schema_list_failopen(monkeypatch):
    # 실제 스키마 목록 미확보 → fail-open skip
    calls, _pg, _saved = _wire(monkeypatch)
    assert _call(known_schemas=[]) is None
    assert "args" not in calls
    assert _call(known_schemas=None) is None
    assert "args" not in calls


def test_self_heal_dedup_same_scope(monkeypatch):
    calls, _pg, _saved = _wire(monkeypatch)
    assert _call(swept={"product.kr_live"}) is None
    assert "args" not in calls


def test_self_heal_exception_isolated(monkeypatch):
    calls, pg, saved = _wire(monkeypatch, sweep_raises=True)
    assert _call() is None                             # 예외 삼킴(tick 비차단)
    assert pg.rolled_back is True
    assert pg.closed is True


def test_self_heal_no_change_returns_none(monkeypatch):
    calls, pg, saved = _wire(monkeypatch, sweep_result={
        "scope": "s", "scanned": 1, "ungrounded": [],
        "dict_deleted": 0, "feedback_rejected": 0, "dry_run": False})
    assert _call() is None                             # 변경 없으면 None
    assert pg.committed is True                         # no-op 트랜잭션도 커밋
    assert calls["args"][2] is False


def test_self_heal_engine_none_treated_mysql(monkeypatch):
    # engine 미지정(기본 단일 MySQL)은 MySQL 로 간주 — self-heal 동작(sweep 대상은 제품 스코프).
    calls, _pg, _saved = _wire(monkeypatch, scope="common", product_scopes=("product.solo",))
    _call(engine=None)
    assert calls["args"][0] == "product.solo"


def test_self_heal_engine_other_excluded(monkeypatch):
    # allowlist(NIT-D): MySQL 이 아닌 임의 엔진은 제외(향후 3번째 엔진 자동 오삭제 방지)
    calls, _pg, _saved = _wire(monkeypatch)
    assert _call(engine="oracle") is None
    assert "args" not in calls


def test_self_heal_shrink_guard_passes_prev_and_saves_current(monkeypatch):
    # catalog-shrink 가드(MINOR-A): 직전 unknown 집합을 confirm_lower 로 전달 + 이번 unknown 을 KV 저장
    import json as _json
    calls, _pg, saved = _wire(monkeypatch, prev_unknown=["dbLog"], sweep_result={
        "scope": "mysql-kr-an1-auth", "scanned": 3,
        "ungrounded": [{"schema_name": "dbLog", "table_name": None},
                       {"schema_name": "dbTmp", "table_name": None}],
        "dict_deleted": 2, "feedback_rejected": 0, "dry_run": False})
    _call(known_schemas=["dbAuth"])
    assert calls["confirm_lower"] == {"dblog"}              # 직전 tick unknown 만 삭제 대상
    assert _json.loads(saved["val"]) == ["dblog", "dbtmp"]  # 이번 tick unknown 전체를 다음 confirm 용 저장


def test_self_heal_first_observation_empty_confirm(monkeypatch):
    # 직전 KV 없음 → confirm_lower=빈 set(이번에 처음 본 unknown 은 sweep 이 삭제 보류)
    calls, _pg, _saved = _wire(monkeypatch, prev_unknown=None, sweep_result={
        "scope": "mysql-kr-an1-auth", "scanned": 1,
        "ungrounded": [{"schema_name": "dbLog", "table_name": None}],
        "dict_deleted": 0, "feedback_rejected": 0, "dry_run": False})
    _call(known_schemas=["dbAuth"])
    assert calls["confirm_lower"] == set()


# ── metadata-product-scope: sweep 대상 스코프 산출 ────────────────────────────
class _FakeMem:
    """WebProducts / WebProductDatasources 조회만 흉내내는 최소 커서."""

    def __init__(self, join_rows, legacy_rows, join_raises=False):
        self.join_rows, self.legacy_rows, self.join_raises = join_rows, legacy_rows, join_raises
        self._pending = []

    def cursor(self):
        return self

    def execute(self, sql, params=None):
        if "WebProductDatasources" in sql:
            if self.join_raises:
                raise RuntimeError("no such table")
            self._pending = self.join_rows
        else:
            self._pending = self.legacy_rows

    def fetchall(self):
        return self._pending

    def close(self):
        pass


def _wire_ds(monkeypatch, labels=("ds-a",)):
    import shared.datasources as _dsr
    monkeypatch.setattr(_dsr, "all_datasources",
                        lambda conn: {lbl: {"key": lbl, "scope_key": "scope-a"} for lbl in labels})


def test_self_heal_scope_keys_single_ds_product_only(monkeypatch):
    """단일 DS 제품만 sweep 대상 — 다중 DS 제품은 known_schemas 가 불완전해 오삭제 위험(제외)."""
    _wire_ds(monkeypatch)
    mem = _FakeMem(join_rows=[(1, "SOLO", "ds-a"), (2, "MULTI", "ds-a"), (2, "MULTI", "ds-b")],
                   legacy_rows=[])
    assert insight._self_heal_scope_keys(mem, "scope-a") == ["product.solo"]


def test_self_heal_scope_keys_legacy_single_binding(monkeypatch):
    """join 테이블이 없는 레거시 배치(WebProducts.DatasourceKey 만)에서도 대상이 잡혀야 한다.

    빠뜨리면 그 배치에서 self-heal 이 통째로 죽어 stale/환각 ENUM 이 계속 주입된다."""
    _wire_ds(monkeypatch)
    mem = _FakeMem(join_rows=[], legacy_rows=[(7, "LEGACY", "ds-a")], join_raises=True)
    assert insight._self_heal_scope_keys(mem, "scope-a") == ["product.legacy"]


def test_self_heal_scope_keys_common_and_unknown_scope(monkeypatch):
    """'common' 과 미매칭 scope 는 datasource 귀속이 없어 대상 없음(파괴적 동작이라 보수적)."""
    _wire_ds(monkeypatch)
    mem = _FakeMem(join_rows=[(1, "SOLO", "ds-a")], legacy_rows=[])
    assert insight._self_heal_scope_keys(mem, "common") == []
    assert insight._self_heal_scope_keys(mem, "scope-zzz") == []
