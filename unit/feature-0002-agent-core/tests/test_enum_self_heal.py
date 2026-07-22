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
          sweep_result=None, sweep_raises=False, prev_unknown=None):
    monkeypatch.setattr(_cfg, "AGENT_ENUM_SCHEMA_GROUNDING", grounding, raising=False)
    monkeypatch.setattr(_cfg, "AGENT_ENUM_SELF_HEAL", self_heal, raising=False)
    monkeypatch.setattr(_cfg, "get_active_datasource", lambda: scope)
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
    assert calls["args"][0] == "mysql-kr-an1-auth"
    assert calls["args"][1] == ["dbAuth"]              # 실제 스키마 목록 전달
    assert calls["args"][2] is False                   # execute
    assert res["dict_deleted"] == 4
    assert pg.committed is True
    assert "mysql-kr-an1-auth" in swept                # dedup 마킹


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
    assert _call(swept={"mysql-kr-an1-auth"}) is None
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
    # engine 미지정(기본 단일 MySQL, ds=None)은 MySQL 로 간주 — self-heal 동작(scope='common')
    calls, _pg, _saved = _wire(monkeypatch, scope="common")
    _call(engine=None)
    assert calls["args"][0] == "common"


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
