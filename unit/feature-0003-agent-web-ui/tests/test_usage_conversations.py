"""TASK-0263 — LLM 사용량 차트 클릭 → 집계 기여 대화목록 엔드포인트.

검증 대상(`make test` agent 이미지, DB 없이 fake cursor/monkeypatch):
  Q1  _query_usage_conversations 대화별 fold — 같은 대화의 여러 모델 행을 calls/tokens/cost 로 합산,
      models[] 분해 보존, conversation_id NOT NULL 강제(INNER JOIN — SQL 에 JOIN core_conversations 포함).
  Q2  차원 필터 → WHERE/params 정합: model / account_ids / day_label / owner_account_id 각각이 올바른
      SQL 조건·바인드 파라미터로 들어간다(차트 수치 ↔ 대화목록 정합 보장의 핵심).
  Q3  좌표/비밀번호 비노출 — 반환 dict 키는 화이트리스트(host/password/user 없음).
  Q4  account_ids=[] (역할에 계정 0) → 빈 결과 + SQL 미실행.
  A1  admin 엔드포인트 권한: console.usage.read 없으면 403, conversation.list.any 없으면 403.
  A2  admin "(시스템)" 역할 클릭 → 빈 목록(owner 없는 비대화 usage).
  P1  profile 엔드포인트: role/account_id 파라미터 무시(권한 상승 차단) — owner_account_id=self 강제.
  R1  _usage_account_ids_for_role: 시스템→None, 역할없음/역할명→계정 집합.
"""
from __future__ import annotations

import json

import app


class _FakeCursor:
    """주어진 rows 를 fetchall 로 돌려주고, 실행된 SQL·params 를 기록하는 커서."""
    def __init__(self, rows, sink):
        self._rows = rows
        self._sink = sink

    def execute(self, sql, params=None):
        self._sink.append((sql, params))

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        return None


class _FakePG:
    def __init__(self, rows, sink):
        self._rows = rows
        self._sink = sink

    def cursor(self, *a, **k):
        return _FakeCursor(self._rows, self._sink)

    def close(self):
        return None


class _FakeDt:
    """isoformat() + 비교 지원(실제 timestamptz 처럼 max()/'>' 동작)."""
    def __init__(self, s):
        self._s = s

    def isoformat(self):
        return self._s

    def __gt__(self, other):
        return self._s > getattr(other, "_s", other)

    def __lt__(self, other):
        return self._s < getattr(other, "_s", other)

    def __eq__(self, other):
        return self._s == getattr(other, "_s", other)

    def __hash__(self):
        return hash(self._s)


def _row(cid, topic, owner, model, calls, tok, pt, ct, last="2026-06-15T10:00:00Z"):
    # 컬럼 순서: conversation_id, topic, owner_account_id, created_at, updated_at, blocked_at, m, calls, tok, pt, ct, last_used
    return (cid, topic, owner, _FakeDt("2026-06-01T00:00:00Z"), _FakeDt("2026-06-15T09:00:00Z"),
            None, model, calls, tok, pt, ct, _FakeDt(last))


# ── Q1: 대화별 fold + INNER JOIN ───────────────────────────────────────────────

def test_q1_fold_and_inner_join():
    sink = []
    rows = [
        _row("conv-A", "토픽 A", 7, "claude-haiku-4", 3, 300, 200, 100),
        _row("conv-A", "토픽 A", 7, "claude-sonnet-4", 2, 200, 150, 50),  # 같은 대화·다른 모델
        _row("conv-B", "토픽 B", 9, "claude-haiku-4", 1, 50, 40, 10),
    ]
    pg = _FakePG(rows, sink)
    items, truncated = app._query_usage_conversations(
        pg, days=30, model=None, account_ids=None, day_label=None, gran="day",
        owner_account_id=None, owner_is_null_ok=False,
    )
    assert truncated is False
    by_cid = {it["conversation_id"]: it for it in items}
    a = by_cid["conv-A"]
    assert a["calls"] == 5 and a["total_tokens"] == 500  # 두 모델 행 합산
    assert len(a["models"]) == 2  # 모델 분해 보존
    # INNER JOIN core_conversations + conversation_id NOT NULL 강제(SQL 검증)
    sql0 = sink[0][0]
    assert "JOIN agent_runtime.core_conversations" in sql0
    assert "u.conversation_id IS NOT NULL" in sql0


# ── Q2: 차원 필터 → WHERE/params ───────────────────────────────────────────────

def test_q2_model_filter():
    sink = []
    app._query_usage_conversations(_FakePG([], sink), days=7, model="claude-haiku-4",
                                   account_ids=None, day_label=None, gran="day",
                                   owner_account_id=None, owner_is_null_ok=False)
    sql, params = sink[0]
    assert "COALESCE(u.resolved_model, u.model) = %s" in sql
    assert "claude-haiku-4" in params
    assert "7 days" in params  # days 바인드


def test_q2b_interval_cast_not_bare_param():
    """TASK-0265 회귀 가드: PG 는 `interval $1`(파라미터) 문법 불허 → `%s::interval` 캐스트 사용.
    bare `interval %s` 면 라이브 PG 에서 'syntax error at or near $1' 500 (단위 테스트 fake cursor
    는 SQL 미실행이라 못 잡던 클래스 — SQL 문자열을 정적 검증)."""
    sink = []
    app._query_usage_conversations(_FakePG([], sink), days=30, model=None, account_ids=None,
                                   day_label=None, gran="day", owner_account_id=None, owner_is_null_ok=False)
    sql, _ = sink[0]
    assert "%s::interval" in sql, "days 는 interval 캐스트로 바인드돼야 함(PG 문법)"
    assert "interval %s" not in sql, "bare 'interval %s' 는 PG 문법 위반(라이브 500)"


def test_q2_account_and_day_filter():
    sink = []
    app._query_usage_conversations(_FakePG([], sink), days=30, model=None,
                                   account_ids=[7, 9], day_label="2026-06-15", gran="day",
                                   owner_account_id=None, owner_is_null_ok=False)
    sql, params = sink[0]
    assert "c.owner_account_id IN (%s,%s)" in sql
    assert 7 in params and 9 in params
    assert "2026-06-15" in params
    assert "to_char(date_trunc('day'" in sql


def test_q2_owner_self_filter():
    sink = []
    app._query_usage_conversations(_FakePG([], sink), days=30, model=None, account_ids=None,
                                   day_label=None, gran="day", owner_account_id=42, owner_is_null_ok=False)
    sql, params = sink[0]
    assert "c.owner_account_id = %s" in sql
    assert 42 in params


# ── Q3: 좌표/비밀번호 비노출 ─────────────────────────────────────────────────

def test_q3_no_coordinate_leak():
    sink = []
    rows = [_row("conv-A", "T", 7, "claude-haiku-4", 1, 10, 8, 2)]
    items, _ = app._query_usage_conversations(_FakePG(rows, sink), days=30, model=None,
                                              account_ids=None, day_label=None, gran="day",
                                              owner_account_id=None, owner_is_null_ok=False)
    keys = set(items[0].keys())
    assert "host" not in keys and "password" not in keys and "user" not in keys
    # 화이트리스트 필드만
    assert {"conversation_id", "topic", "owner_account_id", "calls", "total_tokens", "cost_usd", "models"} <= keys


# ── Q4: 빈 account_ids → 즉시 빈 결과(SQL 미실행) ────────────────────────────

def test_q4_empty_account_ids_short_circuit():
    sink = []
    items, truncated = app._query_usage_conversations(_FakePG([], sink), days=30, model=None,
                                                      account_ids=[], day_label=None, gran="day",
                                                      owner_account_id=None, owner_is_null_ok=False)
    assert items == [] and truncated is False
    assert sink == []  # SQL 실행 안 함


# ── A1: admin 권한 게이트 ─────────────────────────────────────────────────────

class _Req:
    def __init__(self, qp=None):
        self.query_params = qp or {}


class _Conn:
    def cursor(self, *a, **k):
        return _FakeCursor([], [])

    def close(self):
        return None


def _body(resp):
    return json.loads(resp.body)


def test_a1_admin_requires_usage_read(monkeypatch):
    actor = {"id": 1, "permissions": {"conversation.list.any": True}}  # usage.read 없음
    monkeypatch.setattr(app, "_connect_memory", lambda: _Conn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (actor, None))
    # P5b DI seam Phase 3: admin_usage_conversations 가 account=Depends(get_current_account) 로 마이그됨
    # → 직접호출 시 account/conn 명시 주입. AO 라 본문 perm 검사(usage.read+list.any)가 account 로 실행.
    resp = app.admin_usage_conversations(_Req(), account=actor, conn=_Conn())
    assert resp.status_code == 403


def test_a1_admin_requires_list_any(monkeypatch):
    actor = {"id": 1, "permissions": {"console.usage.read": True}}  # list.any 없음
    monkeypatch.setattr(app, "_connect_memory", lambda: _Conn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (actor, None))
    resp = app.admin_usage_conversations(_Req(), account=actor, conn=_Conn())
    assert resp.status_code == 403


# ── A2: "(시스템)" 역할 클릭 → 빈 목록 ──────────────────────────────────────

def test_a2_system_role_empty(monkeypatch):
    actor = {"id": 1, "permissions": {"console.usage.read": True, "conversation.list.any": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _Conn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (actor, None))
    monkeypatch.setattr(app, "_usage_account_ids_for_role", lambda conn, rk: None)  # 시스템
    resp = app.admin_usage_conversations(_Req({"role": "(시스템)"}), account=actor, conn=_Conn())
    body = _body(resp)
    assert body["items"] == [] and body["truncated"] is False


# ── P1: profile 권한 상승 차단 ───────────────────────────────────────────────

def test_p1_profile_ignores_role_account(monkeypatch, client, as_account):
    # P5b DI seam Phase 2: profile_usage_conversations 가 account=Depends(get_current_account) 로
    # 마이그됨 → 직접 함수호출 대신 TestClient + as_account override(get_current_account).
    as_account(id=42, perms={})  # 일반 사용자
    captured = {}
    monkeypatch.setattr(app, "_connect_memory", lambda: _Conn())  # get_conn → fake conn(body 미사용)
    monkeypatch.setattr("shared.db._pg_connect", lambda: _FakePG([], []))

    def _fake_query(pg, **kw):
        captured.update(kw)
        return ([], False)
    monkeypatch.setattr(app, "_query_usage_conversations", _fake_query)
    # role/account_id 를 주입해도 무시되고 owner_account_id=self(42) 강제여야 함
    resp = client.get(
        "/api/profile/usage/conversations",
        params={"role": "admin", "account_id": "999", "model": "claude-haiku-4"},
    )
    assert resp.status_code == 200
    assert captured.get("owner_account_id") == 42
    assert captured.get("account_ids") is None
    assert captured.get("model") == "claude-haiku-4"  # 모델 필터는 적용


# ── R1: 역할 → 계정 집합 역매핑 ─────────────────────────────────────────────

def test_r1_role_to_accounts(monkeypatch):
    # "(시스템)" → None
    assert app._usage_account_ids_for_role(_Conn(), "(시스템)") is None

    class _RoleCursor:
        def __init__(self, rows):
            self._rows = rows

        def execute(self, sql, params=None):
            self._sql = sql

        def fetchall(self):
            return self._rows

        def close(self):
            return None

    class _RoleConn:
        def __init__(self, rows):
            self._rows = rows

        def cursor(self, *a, **k):
            return _RoleCursor(self._rows)

    # 역할명 → 계정 IN 쿼리 결과
    out = app._usage_account_ids_for_role(_RoleConn([(7,), (9,)]), "sales")
    assert out == [7, 9]
