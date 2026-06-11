"""TASK-0210 — 관리 콘솔 대시보드 보강 회귀/보안 테스트.

검증 대상:
  S1  GET /api/admin/overview 의 RBAC 스코프 — actor 가 보유한 표시 권한의 위젯만
      catalog/widgets 에 등장(권한 경계 = 데이터 노출 경계). usage(console.usage.read)·
      audits(audit.read.any) 권한 없는 operator 는 응답에 그 위젯이 아예 없어야 한다.
  S2  console.access 미보유는 403.
  P1  _sanitize_dashboard_prefs — 미지 위젯 키·중복·과대 입력 거부, bool/int 정규화.
  P2  _dashboard_default_prefs — actor 권한 기반으로 기본 위젯만 포함(catalog 순서).
  R1  _save/_load_dashboard_pref_row — JSON 본문 영속 round-trip.

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import json

import app


# ── Fakes ────────────────────────────────────────────────────────────────────

class _BenignCursor:
    """모든 SELECT 가 빈 결과(fetchone→None, fetchall→[])인 커서.

    각 위젯 집계 함수는 `cur.fetchone() or (기본 튜플)` / `cur.fetchall() or []` 로
    빈 결과를 흡수하므로, 이 커서로 모든 위젯이 예외 없이 0-metric 구조를 반환한다.
    → 위젯 존재/부재(권한 경계)만 검증하려는 테스트에 적합.
    """

    def __init__(self):
        self.executed: list[str] = []

    def execute(self, sql, params=None):
        self.executed.append(sql)

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        return None


class _BenignConn:
    def cursor(self, *a, **k):
        return _BenignCursor()

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class _FakeRequest:
    def __init__(self, days=None):
        self.query_params = {} if days is None else {"days": str(days)}


def _body(resp):
    return json.loads(resp.body)


def _patch_common(monkeypatch, actor):
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (actor, None))
    monkeypatch.setattr("modules.db._pg_connect", lambda: _BenignConn())


# ── S1: overview RBAC 스코프 ─────────────────────────────────────────────────

def test_overview_operator_excludes_privileged_widgets(monkeypatch):
    """console.access 만 가진 operator: usage/audits 위젯이 catalog/widgets 에 없어야 함."""
    operator = {"id": 5, "permissions": {"console.access": True}}
    _patch_common(monkeypatch, operator)

    resp = app.admin_overview(_FakeRequest())
    body = _body(resp)

    catalog_keys = {c["key"] for c in body["catalog"]}
    # 권한 경계: 미보유 위젯은 카탈로그·데이터 둘 다에서 부재
    assert "usage" not in catalog_keys
    assert "audits" not in catalog_keys
    assert "usage" not in body["widgets"]
    assert "audits" not in body["widgets"]
    # console.access 로 볼 수 있는 위젯은 존재
    assert "accounts" in catalog_keys
    assert "accounts" in body["widgets"]
    assert "conversations" in body["widgets"]  # console.access → PG 대화 위젯 표시


def test_overview_admin_includes_privileged_widgets(monkeypatch):
    """모든 권한 admin: usage/audits 위젯이 catalog/widgets 에 등장."""
    admin = {
        "id": 1,
        "permissions": {
            "console.access": True,
            "console.usage.read": True,
            "audit.read.any": True,
        },
    }
    _patch_common(monkeypatch, admin)

    resp = app.admin_overview(_FakeRequest(days=30))
    body = _body(resp)

    catalog_keys = {c["key"] for c in body["catalog"]}
    assert "usage" in catalog_keys
    assert "audits" in catalog_keys
    assert "usage" in body["widgets"]
    assert "audits" in body["widgets"]
    assert body["window_days"] == 30


def test_overview_catalog_includes_client_widgets(monkeypatch):
    """client-rendered grant_health/pending 도 권한 보유 시 catalog 에 포함(서버 권위 목록)."""
    operator = {"id": 5, "permissions": {"console.access": True}}
    _patch_common(monkeypatch, operator)

    body = _body(app.admin_overview(_FakeRequest()))
    catalog = {c["key"]: c for c in body["catalog"]}
    assert catalog.get("grant_health", {}).get("source") == "client"
    assert catalog.get("pending", {}).get("source") == "client"
    # client 위젯은 server 집계 데이터(widgets)에는 없음
    assert "grant_health" not in body["widgets"]
    assert "pending" not in body["widgets"]


# ── S2: console.access 미보유 403 ────────────────────────────────────────────

def test_overview_requires_console_access(monkeypatch):
    nobody = {"id": 9, "permissions": {"conversation.read": True}}
    _patch_common(monkeypatch, nobody)
    resp = app.admin_overview(_FakeRequest())
    assert resp.status_code == 403


# ── P1: _sanitize_dashboard_prefs ────────────────────────────────────────────

def test_sanitize_drops_unknown_and_dedupes():
    raw = {
        "widgets": [
            {"key": "accounts", "visible": True, "order": 0},
            {"key": "accounts", "visible": False, "order": 9},  # 중복 → 첫 항목만
            {"key": "__evil__", "visible": True, "order": 1},   # 미지 키 → drop
            {"key": "usage", "visible": "yes", "order": "2"},    # bool/int 정규화
            "not-a-dict",                                          # skip
        ]
    }
    out = app._sanitize_dashboard_prefs(raw)
    keys = [w["key"] for w in out["widgets"]]
    assert keys == ["accounts", "usage"]
    assert out["widgets"][0]["visible"] is True
    assert out["widgets"][1]["visible"] is True   # "yes" → truthy → True
    assert out["widgets"][1]["order"] == 2         # "2" → int
    assert out["version"] == app._DASHBOARD_PREF_VERSION


def test_sanitize_caps_oversize_input():
    raw = {"widgets": [{"key": "accounts"}] * 500}  # dedup 후 1개지만 상한 순회도 검증
    out = app._sanitize_dashboard_prefs(raw)
    assert len(out["widgets"]) == 1  # 동일 키 dedup


def test_sanitize_non_dict_returns_empty():
    assert app._sanitize_dashboard_prefs("nope")["widgets"] == []
    assert app._sanitize_dashboard_prefs({})["widgets"] == []


# ── P2: _dashboard_default_prefs ─────────────────────────────────────────────

def test_default_prefs_respects_permissions():
    operator = {"id": 5, "permissions": {"console.access": True}}
    prefs = app._dashboard_default_prefs(operator)
    keys = [w["key"] for w in prefs["widgets"]]
    assert "accounts" in keys
    assert "usage" not in keys      # console.usage.read 없음
    assert "audits" not in keys     # audit.read.any 없음
    # 모두 visible 기본값 + order 는 catalog 순서(연속)
    assert all(w["visible"] for w in prefs["widgets"])
    assert [w["order"] for w in prefs["widgets"]] == list(range(len(keys)))


def test_default_prefs_admin_includes_privileged():
    admin = {"id": 1, "permissions": {"console.access": True, "console.usage.read": True, "audit.read.any": True}}
    keys = [w["key"] for w in app._dashboard_default_prefs(admin)["widgets"]]
    assert "usage" in keys and "audits" in keys


# ── R1: 영속 round-trip ──────────────────────────────────────────────────────

class _KVCursor:
    def __init__(self, store):
        self.store = store

    def execute(self, sql, params=None):
        s = sql.strip().upper()
        if s.startswith("INSERT"):
            self.store["content"] = params[1]

    def fetchone(self):
        c = self.store.get("content")
        return (c,) if c is not None else None

    def close(self):
        return None


class _KVConn:
    def __init__(self):
        self.store = {}

    def cursor(self, *a, **k):
        return _KVCursor(self.store)

    def commit(self):
        return None

    def close(self):
        return None


def test_save_load_pref_roundtrip():
    conn = _KVConn()
    content = {"version": 1, "widgets": [{"key": "accounts", "visible": False, "order": 2}]}
    app._save_dashboard_pref_row(conn, 7, content)
    loaded = app._load_dashboard_pref_row(conn, 7)
    assert loaded == content


def test_load_pref_absent_returns_none():
    assert app._load_dashboard_pref_row(_KVConn(), 7) is None
