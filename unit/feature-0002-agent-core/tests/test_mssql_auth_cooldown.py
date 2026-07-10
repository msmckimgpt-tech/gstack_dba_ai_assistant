"""TASK-20260710-mssql-auth-cooldown — MSSQL insight 순회 로그인실패 조기 skip + cooldown 회귀 테스트.

codex 디스크 I/O 장애조사 트랙 B. MSSQL datasource 의 **로그인 자체 실패**(MSSQL 18456 "Login failed")가
WebProductDatabases 등록 DB 수만큼 반복 재연결·로그·후속 I/O 를 유발하던 것을,
  (1) cycle 내: 첫 로그인실패 시 같은 datasource 의 나머지 DB 순회 즉시 중단(break),
  (2) cycle 간: cooldown 으로 다음 재시도를 억제(conn_health network breaker 와 분리)
하도록 개선한 것을 검증한다.

합격선(TASK §2.1 acceptance + REV-20260710 흡수):
- AC1: 같은 datasource 10 DB 중 첫 18456 → 실제 connect 1회만(나머지 9 skip).
- AC2: 다음 cycle 에서 cooldown 만료 전까지 그 datasource connect 0회(진입부 통째 skip).
- AC3: cooldown 만료 시 자동 정리(다음 재시도 1회 허용) + clear 로 즉시 해제.
- AC4: AGENT_INSIGHT_AUTH_COOLDOWN_SEC=0 → cooldown 비활성(cycle 내 skip 은 유지, cycle 간 재시도).
- HIGH-1: 같은 host:port(=scope_key) 다른 계정 datasource 는 **연쇄 차단되지 않는다**(cooldown 키=label).
- HIGH-2: 916("Cannot open database" — DB별 권한)은 로그인 성공 상태라 **나머지 DB 를 skip 하지 않는다**
  (916 메시지가 "login failed" 텍스트를 포함해도 로그인실패로 오분류 안 함).

실 DB 없이 monkeypatch 로 순회 의존성을 mock 하고, datasource connect 호출 횟수로 검증한다.
"""
from __future__ import annotations

import sys
import time
import types
from unittest.mock import MagicMock

from modules import insight

# 실제 MSSQL 드라이버 에러 메시지(pymssql `(number, b"...")` 형태) 근사.
_ERR_18456 = "(18456, b\"Login failed for user 'mckim'.\")"
# ⚠ 916 실제 메시지는 "login failed" 텍스트를 포함한다 — 텍스트만으론 로그인실패로 오분류될 소지(HIGH-2).
_ERR_916 = ("(916, b\"Cannot open database \\\"db0\\\" requested by the login. "
            "The login failed for user 'mckim'.\")")
_ERR_TRANSIENT = "(10054, b\"Read from the server failed\")"


def _reset_state():
    insight._DS_AUTH_COOLDOWN.clear()
    insight._LAST_DS_SCAN_STATUS.clear()


# ──────────────────────────────────────────────────────────────────────────
# 1. cooldown 헬퍼 단위 테스트 (AC3/AC4 핵심 로직)
# ──────────────────────────────────────────────────────────────────────────
def test_cooldown_set_then_active(monkeypatch):
    _reset_state()
    monkeypatch.setattr(insight, "AGENT_INSIGHT_AUTH_COOLDOWN_SEC", 600)
    assert insight._ds_auth_cooldown_active("prod-x") is False
    insight._ds_auth_cooldown_set("prod-x")
    assert insight._ds_auth_cooldown_active("prod-x") is True


def test_cooldown_expiry_auto_clears():
    """AC3: 만료된 cooldown 은 active=False + 자동 pop(다음 재시도 1회 허용)."""
    _reset_state()
    insight._DS_AUTH_COOLDOWN["prod-x"] = time.monotonic() - 1.0  # 이미 만료된 시각
    assert insight._ds_auth_cooldown_active("prod-x") is False
    assert "prod-x" not in insight._DS_AUTH_COOLDOWN  # 만료 자동 정리


def test_cooldown_clear(monkeypatch):
    _reset_state()
    monkeypatch.setattr(insight, "AGENT_INSIGHT_AUTH_COOLDOWN_SEC", 600)
    insight._ds_auth_cooldown_set("prod-x")
    assert insight._ds_auth_cooldown_active("prod-x") is True
    insight._ds_auth_cooldown_clear("prod-x")
    assert insight._ds_auth_cooldown_active("prod-x") is False


def test_cooldown_disabled_ttl_zero(monkeypatch):
    """AC4: AGENT_INSIGHT_AUTH_COOLDOWN_SEC=0 이면 set 이 no-op(cooldown 비활성)."""
    _reset_state()
    monkeypatch.setattr(insight, "AGENT_INSIGHT_AUTH_COOLDOWN_SEC", 0)
    insight._ds_auth_cooldown_set("prod-x")
    assert insight._ds_auth_cooldown_active("prod-x") is False


def test_cooldown_none_key_safe():
    """label None(기본 단일 MySQL)은 모든 헬퍼가 no-op — raise 없음."""
    _reset_state()
    assert insight._ds_auth_cooldown_active(None) is False
    insight._ds_auth_cooldown_set(None)
    insight._ds_auth_cooldown_clear(None)
    assert insight._DS_AUTH_COOLDOWN == {}


def test_prune_auth_cooldown_removes_stale(monkeypatch):
    """LOW-5: 등록 해제/rename 된 datasource 항목을 현재 label 집합으로 prune."""
    _reset_state()
    monkeypatch.setattr(insight, "AGENT_INSIGHT_AUTH_COOLDOWN_SEC", 600)
    insight._ds_auth_cooldown_set("prod-a")
    insight._ds_auth_cooldown_set("prod-gone")
    insight._prune_auth_cooldown({"prod-a"})  # prod-gone 은 더 이상 등록 안 됨
    assert insight._ds_auth_cooldown_active("prod-a") is True
    assert "prod-gone" not in insight._DS_AUTH_COOLDOWN


# ──────────────────────────────────────────────────────────────────────────
# 2. run_insight_cycle 순회 통합 테스트 (AC1/AC2/AC4 + HIGH-1/HIGH-2)
# ──────────────────────────────────────────────────────────────────────────
def _base_mocks(monkeypatch):
    """공통 순회 의존성 mock (mem/db conn·lock·readback·telemetry·node_analysis)."""
    fake_conn = MagicMock(name="mem_or_db_conn")
    monkeypatch.setattr(insight, "connect_with_retry", lambda *a, **k: fake_conn)
    monkeypatch.setattr(insight, "_acquire_advisory_lock", lambda *a, **k: True)
    monkeypatch.setattr(insight, "_release_advisory_lock", lambda *a, **k: None)
    monkeypatch.setattr(insight, "_insight_readback_degraded", lambda: False)
    monkeypatch.setattr(insight, "_persist_datasource_health", lambda *a, **k: None)
    monkeypatch.setattr(insight, "save_memory_kv", lambda *a, **k: None)
    monkeypatch.setattr(insight, "AGENT_MULTI_DATASOURCE_ENABLED", True)
    monkeypatch.setattr("shared.conn_health.should_fast_fail", lambda k: False)
    fake_na = types.ModuleType("modules.node_analysis")
    fake_na.process_pending = lambda *a, **k: {}
    fake_na.backfill_roles = lambda *a, **k: 0
    monkeypatch.setitem(sys.modules, "modules.node_analysis", fake_na)


def _install_single_ds(monkeypatch, n_dbs=10, err=_ERR_18456):
    """단일 MSSQL datasource(label 'mssql-qa-idc') + n_dbs 개 등록 DB. 모든 DB 연결이 err 로 실패.
    datasource connect 대상 DB 리스트(호출 카운터)를 반환."""
    _base_mocks(monkeypatch)
    calls: list = []
    ds = {
        "key": "mssql-qa-idc", "engine": "mssql", "scope_key": "mssql-06656002eda6",
        "host": "10.0.0.1", "port": 1433, "default_db": None, "insight_enabled": True, "user": "mckim",
    }
    monkeypatch.setattr("shared.datasources.all_datasources", lambda mem: {"mssql-qa-idc": ds})
    monkeypatch.setattr(insight, "_discover_mssql_databases",
                        lambda mem, k, c: [f"db{i}_20260625" for i in range(n_dbs)])

    def _fake_ds_connect(*a, **k):
        calls.append(k.get("database"))
        raise Exception(err)

    monkeypatch.setattr(insight._db, "connect_with_retry", _fake_ds_connect)
    return calls


def test_first_cycle_connects_once_and_sets_cooldown(monkeypatch):
    """AC1: 같은 datasource 10 DB 인데 첫 DB 18456 → 실제 connect 1회만(나머지 9 skip) + cooldown 설정."""
    _reset_state()
    monkeypatch.setattr(insight, "AGENT_INSIGHT_AUTH_COOLDOWN_SEC", 600)
    calls = _install_single_ds(monkeypatch, n_dbs=10, err=_ERR_18456)

    insight.run_insight_cycle("test-auth-cooldown-1")

    assert len(calls) == 1, f"18456 후 나머지 DB 를 계속 시도함(실제 connect {len(calls)}회, 기대 1회)"
    assert insight._ds_auth_cooldown_active("mssql-qa-idc") is True  # cooldown 키 = datasource label


def test_next_cycle_skips_entirely_during_cooldown(monkeypatch):
    """AC2: cooldown 중 다음 cycle 은 그 datasource 를 진입부에서 통째 skip → connect 0회."""
    _reset_state()
    monkeypatch.setattr(insight, "AGENT_INSIGHT_AUTH_COOLDOWN_SEC", 600)
    calls = _install_single_ds(monkeypatch, n_dbs=10, err=_ERR_18456)

    insight.run_insight_cycle("test-auth-cooldown-c1")
    assert len(calls) == 1
    calls.clear()

    insight.run_insight_cycle("test-auth-cooldown-c2")
    assert len(calls) == 0, f"cooldown 중인데 재시도함(connect {len(calls)}회, 기대 0회)"


def test_ttl_zero_retries_next_cycle_but_still_breaks_in_cycle(monkeypatch):
    """AC4: cooldown=0 이면 cycle 내 skip(break→connect 1회)은 유지, cycle 간 재시도(다음 cycle 다시 1회)."""
    _reset_state()
    monkeypatch.setattr(insight, "AGENT_INSIGHT_AUTH_COOLDOWN_SEC", 0)
    calls = _install_single_ds(monkeypatch, n_dbs=10, err=_ERR_18456)

    insight.run_insight_cycle("test-ttl0-c1")
    assert len(calls) == 1  # cycle 내 나머지 skip(break)은 cooldown 과 무관하게 유지
    calls.clear()

    insight.run_insight_cycle("test-ttl0-c2")
    assert len(calls) == 1  # cooldown 미설정 → 다음 cycle 재시도(단, 여전히 첫 실패 후 break)


def test_per_db_916_does_not_skip_other_dbs(monkeypatch):
    """HIGH-2: 916("Cannot open database" — DB별 권한)은 로그인 성공 상태라 나머지 DB 를 통째 skip 하지 않는다.
    916 메시지가 'login failed' 텍스트를 포함해도 로그인실패로 오분류하지 않아, 10 DB 전부 시도된다."""
    _reset_state()
    monkeypatch.setattr(insight, "AGENT_INSIGHT_AUTH_COOLDOWN_SEC", 600)
    calls = _install_single_ds(monkeypatch, n_dbs=10, err=_ERR_916)

    insight.run_insight_cycle("test-916")

    assert len(calls) == 10, f"916(DB별)인데 나머지 DB 를 skip 함(connect {len(calls)}회, 기대 10회)"
    assert insight._ds_auth_cooldown_active("mssql-qa-idc") is False  # 916 은 cooldown 안 함(로그인 성공)


def test_different_login_same_endpoint_not_chained(monkeypatch):
    """HIGH-1: 같은 host:port(=scope_key) 에 다른 계정으로 등록된 두 datasource — 잘못된 계정 A 의 18456 이
    정상 계정 B 를 연쇄 차단하지 않는다(cooldown 키 = datasource label, scope_key 아님)."""
    _reset_state()
    monkeypatch.setattr(insight, "AGENT_INSIGHT_AUTH_COOLDOWN_SEC", 600)
    _base_mocks(monkeypatch)

    # 같은 host:port → 동일 scope_key, 다른 label/user.
    ds_a = {"key": "prod-a", "engine": "mssql", "scope_key": "mssql-shared", "host": "10.0.0.9",
            "port": 1433, "default_db": None, "insight_enabled": True, "user": "wrong"}
    ds_b = {"key": "prod-b", "engine": "mssql", "scope_key": "mssql-shared", "host": "10.0.0.9",
            "port": 1433, "default_db": None, "insight_enabled": True, "user": "valid"}
    monkeypatch.setattr("shared.datasources.all_datasources",
                        lambda mem: {"prod-a": ds_a, "prod-b": ds_b})
    monkeypatch.setattr(insight, "_discover_mssql_databases", lambda mem, k, c: ["db0"])

    attempted: list = []

    def _connect(*a, **k):
        ds = k.get("datasource") or {}
        attempted.append(ds.get("key"))
        # A(잘못된 계정)만 18456, B 는 로그인실패가 아닌 다른 오류(연결이 시도됐음만 검증).
        raise Exception(_ERR_18456 if ds.get("user") == "wrong" else _ERR_TRANSIENT)

    monkeypatch.setattr(insight._db, "connect_with_retry", _connect)

    insight.run_insight_cycle("test-high1")

    assert "prod-b" in attempted, f"정상 계정 B 가 A 의 cooldown 에 연쇄 차단됨(attempted={attempted})"
    assert insight._ds_auth_cooldown_active("prod-a") is True   # A: 18456 → cooldown
    assert insight._ds_auth_cooldown_active("prod-b") is False  # B: 로그인실패 아님 → cooldown 없음
