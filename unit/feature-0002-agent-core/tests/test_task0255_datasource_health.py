"""TASK-0255 R2 — datasource 연결 health PG 영속 (_record_ds_health / _persist_datasource_health).

검증: ① 자격증명 비영속 불변식(user/password 가 row·upsert params 에 절대 없음), ② scan_outcome 심각도 precedence,
③ _record_ds_health 는 어떤 경우에도 raise 안 함(soft telemetry), ④ PG 미가용 시 graceful no-op,
⑤ upsert + registry 동기 prune 실행, ⑥ PG 실패해도 cycle 안 깨짐. 실 PG 없이 monkeypatch.
"""
from __future__ import annotations

from modules import insight


def test_record_ds_health_no_credentials(monkeypatch):
    import shared.conn_health as ch
    monkeypatch.setattr(ch, "status_for", lambda ds: {
        "status": "unstable", "host": "10.1.1.1", "port": 3306, "engine": "mysql",
        "label": "ds-a", "fails": 3, "last_error": "errno=2003", "checked_at": 1234.5,
    })
    rows: dict = {}
    coords = {"key": "ds-a", "engine": "mysql", "host": "10.1.1.1", "port": 3306,
              "user": "root", "password": "secret"}
    insight._record_ds_health(rows, "mysql-abc", coords, "circuit_open")
    r = rows["mysql-abc"]
    assert r["status"] == "unstable"
    assert r["scan_outcome"] == "circuit_open"
    assert r["fail_count"] == 3
    assert r["host"] == "10.1.1.1"
    # 자격증명 비영속 불변식 — row 에 user/password 키도, secret 값도 없다.
    assert "password" not in r and "user" not in r
    assert "secret" not in str(r)


def test_record_ds_health_skips_when_no_scope():
    rows: dict = {}
    insight._record_ds_health(rows, None, {"engine": "mysql"}, "ok")
    assert rows == {}  # scope_key 없으면(control-plane) 기록 안 함


def test_record_ds_health_precedence(monkeypatch):
    import shared.conn_health as ch
    monkeypatch.setattr(ch, "status_for", lambda ds: {})
    rows: dict = {}
    insight._record_ds_health(rows, "k", {"engine": "mysql"}, "ok")
    insight._record_ds_health(rows, "k", {"engine": "mysql"}, "circuit_open")  # 더 심각 → 덮어씀
    assert rows["k"]["scan_outcome"] == "circuit_open"
    insight._record_ds_health(rows, "k", {"engine": "mysql"}, "ok")            # 덜 심각 → 유지
    assert rows["k"]["scan_outcome"] == "circuit_open"


def test_record_ds_health_never_raises(monkeypatch):
    import shared.conn_health as ch

    def _boom(ds):
        raise RuntimeError("status_for blew up")

    monkeypatch.setattr(ch, "status_for", _boom)
    rows: dict = {}
    insight._record_ds_health(rows, "k", {"engine": "mysql"}, "ok")  # 예외 전파 안 함(soft telemetry)


def test_persist_skips_when_pg_unavailable(monkeypatch):
    monkeypatch.setattr(insight, "_pg_available", lambda: False)

    def _no(*a, **k):
        raise AssertionError("PG 미가용인데 connect 시도함")

    monkeypatch.setattr(insight, "_pg_connect", _no)
    insight._persist_datasource_health({"k": {"scope_key": "k"}}, "run1")  # no-op, no raise


def test_persist_upserts_and_prunes_without_credentials(monkeypatch):
    monkeypatch.setattr(insight, "_pg_available", lambda: True)
    executed: list = []

    class _Cur:
        def execute(self, sql, params=None):
            executed.append((sql, params))

        def close(self):
            pass

    class _Conn:
        def cursor(self):
            return _Cur()

        def close(self):
            pass

    monkeypatch.setattr(insight, "_pg_connect", lambda **k: _Conn())
    rows = {
        "mysql-abc": {"scope_key": "mysql-abc", "label": "ds-a", "engine": "mysql",
                      "host": "10.1.1.1", "port": 3306, "status": "unstable",
                      "scan_outcome": "circuit_open", "fail_count": 2,
                      "last_error_tag": "errno=2003", "last_checked_at": 1234.5},
    }
    insight._persist_datasource_health(rows, "run1")
    sqls = [s for s, _ in executed]
    assert any("INSERT INTO agent_runtime.datasource_health" in s for s in sqls)   # upsert
    assert any("DELETE FROM agent_runtime.datasource_health" in s for s in sqls)   # registry 동기 prune
    # 자격증명 비영속: 어떤 upsert params dict 에도 user/password 키 없음.
    for _s, p in executed:
        if isinstance(p, dict):
            assert "password" not in p and "user" not in p


def test_persist_full_wipe_when_no_rows(monkeypatch):
    monkeypatch.setattr(insight, "_pg_available", lambda: True)
    executed: list = []

    class _Cur:
        def execute(self, sql, params=None):
            executed.append(sql)

        def close(self):
            pass

    class _Conn:
        def cursor(self):
            return _Cur()

        def close(self):
            pass

    monkeypatch.setattr(insight, "_pg_connect", lambda **k: _Conn())
    insight._persist_datasource_health({}, "run1")  # 등록 datasource 0 → 전체 비움
    assert any(s.strip().startswith("DELETE FROM agent_runtime.datasource_health") for s in executed)


def test_persist_soft_fail_no_raise(monkeypatch):
    monkeypatch.setattr(insight, "_pg_available", lambda: True)

    def _boom(**k):
        raise RuntimeError("pg down")

    monkeypatch.setattr(insight, "_pg_connect", _boom)
    insight._persist_datasource_health({"k": {"scope_key": "k", "engine": "mysql"}}, "run1")  # no raise
