"""TASK-0277 — 데이터소스 라벨 rename 시 제품 바인딩 안정성 회귀 테스트.

근본 원인: `admin_update_datasource` 의 rename(key_changed) cascade 가 `WebProducts.DatasourceKey`
**한 테이블만** 갱신하고 `WebProductDatasources`(1:N join, TASK-0228/0230)·`WebProductDatabases`
(접근DB 차원, TASK-0206)를 누락 → 멀티 datasource 도입 후 바인딩 본체가 join 테이블로 이동했는데
cascade 미확장 → 라벨 rename 시 제품 바인딩·접근DB 가 고아됨(미바인딩=접근 0, 데이터 접근 상실).

수정(TASK-0277, 라벨/키 분리): 제품 바인딩의 canonical 식별자를 renameable 라벨에서 **stable
surrogate `WebDatasources.Id`** 로 이전. rename cascade 를 3 테이블 전체 완전 갱신 — DatasourceId 가
있으면 Id 구동(WHERE DatasourceId=<id> OR LOWER(DatasourceKey)=old), **컬럼 부재(마이그레이션
지연) 시에도 키 기준으로 완전 cascade**(REV BLOCKER1 — 일부 테이블 누락 금지).

검증(DB 없이 monkeypatch — `make test` agent 이미지, --no-deps):
  R1  explicit rename(컬럼 존재) → 3 바인딩 테이블 모두 DatasourceKey cascade (과거 버그: WebProducts 만).
  R2  cascade 가 Id 구동(WHERE DatasourceId=%s ...) + 해석된 Id 사용 + 구 키 폴백 병행.
  R3  비-rename 편집(insight 토글)은 바인딩 테이블 cascade 미발생.
  R4  **DatasourceId 컬럼 부재**(마이그레이션 지연) → 키 기준으로 3 테이블 모두 cascade(REV BLOCKER1 가드).
"""
from __future__ import annotations

import asyncio
import json

import app

_DS_ID = 42  # rename 후 WebDatasources 에서 해석되는 stable surrogate Id


class _FakeReq:
    def __init__(self, body):
        self._raw = json.dumps(body).encode()

    async def body(self):
        return self._raw

    async def json(self):
        return json.loads(self._raw)


class _RenameCursor:
    def __init__(self, existing, *, has_dsid_col=True):
        self._existing = existing  # (Engine, Host, Port, PasswordEnc, EncryptionVersion)
        self._has_dsid_col = has_dsid_col
        self.executed = []
        self._last = ("", ())

    def execute(self, sql, params=None):
        self.executed.append((sql, params or ()))
        self._last = (sql, params or ())

    def fetchone(self):
        sql, _ = self._last
        if "SELECT Engine, Host, Port, PasswordEnc, EncryptionVersion" in sql:
            return self._existing
        if sql.startswith("SELECT 1 FROM WebDatasources WHERE DatasourceKey="):
            return None  # rename 대상 키 미존재(중복 아님 → 409 통과)
        if sql.startswith("SELECT Id FROM WebDatasources WHERE DatasourceKey="):
            return (_DS_ID,)  # Id 구동 cascade 의 anchor 해석
        if "information_schema.COLUMNS" in sql and "DatasourceId" in sql:
            return (1 if self._has_dsid_col else 0,)  # 컬럼 존재 여부 probe
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class _RenameConn:
    def __init__(self, cur):
        self._cur = cur
        self.committed = False
        self.rolled_back = False
        self.autocommit = True  # 핸들러가 트랜잭션 위해 False 로 설정함

    def cursor(self, *a, **k):
        return self._cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def _patch(monkeypatch, conn):
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    monkeypatch.setattr(app, "_require_account", lambda req, c: ({"id": 10}, None))
    monkeypatch.setattr(app, "_account_has_permission", lambda a, p: True)
    monkeypatch.setattr(app, "record_audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(app, "_build_actor_from_request", lambda *a, **kw: {"id": 10})


def _cascade_updates(cur, table):
    """`UPDATE <table> SET DatasourceKey=...` 로 시작하는 실행 SQL 목록."""
    return [(s, p) for (s, p) in cur.executed if s.startswith(f"UPDATE {table} SET DatasourceKey=")]


def _preclean_deletes(cur, table):
    """`DELETE FROM <table> WHERE LOWER(DatasourceKey)=new_k` (PK 충돌 고아 사전제거) 목록."""
    return [(s, p) for (s, p) in cur.executed
            if s.startswith(f"DELETE FROM {table} WHERE LOWER(DatasourceKey)=")]


def _run_rename(monkeypatch, body, *, has_dsid_col=True):
    cur = _RenameCursor(("mssql", "172.28.64.1", 14330, None, 1), has_dsid_col=has_dsid_col)
    conn = _RenameConn(cur)
    _patch(monkeypatch, conn)
    resp = asyncio.run(app.admin_update_datasource("mssql_local", _FakeReq(body)))
    return cur, conn, json.loads(resp.body)


def test_r1_rename_cascades_all_three_binding_tables(monkeypatch):
    """R1(핵심): explicit rename 시 WebProducts·WebProductDatasources·WebProductDatabases 가 모두 cascade.

    과거 버그는 WebProducts 만 갱신 → 멀티 datasource join 바인딩·접근DB 가 고아.
    """
    cur, conn, body = _run_rename(monkeypatch, {"key": "mssql_prod"})
    assert body.get("key_changed") is True, f"explicit rename 미반영: {body}"
    assert conn.committed and conn.autocommit is False, "명시 트랜잭션 commit 안 됨(REV BLOCKER2)"
    for tbl in ("WebProducts", "WebProductDatasources", "WebProductDatabases"):
        ups = _cascade_updates(cur, tbl)
        assert ups, f"{tbl} cascade 누락 — 라벨 rename 시 이 테이블 바인딩이 고아됨(회귀): {cur.executed}"
        assert ups[0][1] and ups[0][1][0] == "mssql_prod", f"{tbl} cascade 가 새 키로 안 됨: {ups}"
    # REV BLOCKER3: cascade 전 new_k 고아 행 사전제거(PK 충돌 방지) — 2 PK 테이블에서 발생.
    for tbl in ("WebProductDatasources", "WebProductDatabases"):
        dels = _preclean_deletes(cur, tbl)
        assert dels and dels[0][1] and dels[0][1][0] == "mssql_prod", \
            f"{tbl} new_k 고아 사전제거 누락(PK 충돌 위험): {cur.executed}"


def test_r2_cascade_is_id_driven(monkeypatch):
    """R2: cascade WHERE 가 Id 구동(DatasourceId=<id>) + 해석된 Id 사용 + 구 키 폴백 병행."""
    cur, _conn, _body = _run_rename(monkeypatch, {"key": "mssql_prod"})
    assert any(s.startswith("SELECT Id FROM WebDatasources WHERE DatasourceKey=") for (s, p) in cur.executed), \
        f"Id 해석 쿼리 누락(cascade anchor): {cur.executed}"
    for tbl in ("WebProducts", "WebProductDatasources", "WebProductDatabases"):
        sql, params = _cascade_updates(cur, tbl)[0]
        assert "WHERE DatasourceId=%s" in sql, f"{tbl} cascade 가 Id 구동 아님: {sql}"
        assert _DS_ID in params, f"{tbl} cascade 가 해석된 Id 미사용: {params}"
        assert "LOWER(DatasourceKey)=%s" in sql, f"{tbl} cascade 구 키 폴백 누락: {sql}"


def test_r3_non_rename_edit_no_binding_cascade(monkeypatch):
    """R3: 비-rename 편집(insight 토글)은 바인딩 테이블 cascade 미발생(불필요 write 없음)."""
    cur, _conn, body = _run_rename(monkeypatch, {"insight_enabled": True})
    assert body.get("key_changed") is False, f"비-rename 편집이 rename 으로 처리됨: {body}"
    for tbl in ("WebProducts", "WebProductDatasources", "WebProductDatabases"):
        assert not _cascade_updates(cur, tbl), f"{tbl} 불필요 cascade 발생: {cur.executed}"


def test_r4_cascade_complete_when_dsid_column_absent(monkeypatch):
    """R4(REV BLOCKER1 가드): DatasourceId 컬럼 부재(마이그레이션 지연) 시에도 3 테이블 모두 키 기준 cascade.

    과거 결함 분석: 컬럼이 없으면 Id 구동 UPDATE 가 errno 1054 로 죽고 (당시 swallow 로) WebProducts
    포함 전 테이블 cascade 가 누락돼 기존보다 악화. 수정 후엔 컬럼 부재 시 key-only cascade 로 완전 동작.
    """
    cur, _conn, body = _run_rename(monkeypatch, {"key": "mssql_prod"}, has_dsid_col=False)
    assert body.get("key_changed") is True, f"explicit rename 미반영: {body}"
    for tbl in ("WebProducts", "WebProductDatasources", "WebProductDatabases"):
        ups = _cascade_updates(cur, tbl)
        assert ups, f"{tbl} cascade 누락(컬럼 부재 시) — REV BLOCKER1 회귀: {cur.executed}"
        sql = ups[0][0]
        assert "DatasourceId" not in sql, f"{tbl} 컬럼 부재인데 DatasourceId 참조(1054 위험): {sql}"
        assert "LOWER(DatasourceKey)=%s" in sql, f"{tbl} key 기준 cascade 아님: {sql}"
        assert ups[0][1][0] == "mssql_prod", f"{tbl} 새 키로 cascade 안 됨: {ups}"
