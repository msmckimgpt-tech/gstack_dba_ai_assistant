"""TASK-0305 — insight-worker 병목 수정 단위 테스트.

진단(다중 가설 + 적대적 검증)으로 확정한 두 코드 결함을 회귀 가드한다:

- RC2: schema/table fingerprint 가 케이스 미정규화라 MSSQL information_schema 의
  대소문자 진동(TF_ErrorLog <-> tf_errorlog)에 fingerprint 가 흔들려 같은 객체를
  매번 LLM 으로 재생성하던 churn. casefold 를 해시 VALUE 에만 적용해 안정화.
- RC3: pending-repair 무진전 backoff — budget 가 닿지 못하는 미완성 artifact tail 이
  force_scan 을 매 tick 영구 latch 하던 spin 을, 진전 기반 backoff 로 차단.

실 DB 없이 fake cursor / in-memory KV monkeypatch 로만 분기 검증.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


# ── fake DB cursor ───────────────────────────────────────────────────────────
class _FakeCur:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *a, **k):
        return None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        return None


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCur(self._rows)


# ── RC2: fingerprint casefold (VALUE only) ───────────────────────────────────
def test_schema_fingerprint_case_invariant():
    """같은 논리 테이블 목록을 대문자/소문자로 받아도 schema fingerprint 가 동일해야 한다."""
    import modules.insight as insight

    upper = _FakeConn([("TF_ErrorLog",), ("TF_Info_Column",), ("TF_Info_Table",)])
    lower = _FakeConn([("tf_errorlog",), ("tf_info_column",), ("tf_info_table",)])
    assert insight._compute_schema_fingerprint(upper, "log_v2") == \
        insight._compute_schema_fingerprint(lower, "log_v2")


def test_schema_fingerprint_detects_real_change():
    """케이스가 아닌 실제 테이블 구성 변경은 여전히 다른 fingerprint 여야 한다(거짓 안정 방지)."""
    import modules.insight as insight

    a = _FakeConn([("orders",), ("customers",)])
    b = _FakeConn([("orders",), ("invoices",)])
    assert insight._compute_schema_fingerprint(a, "s") != \
        insight._compute_schema_fingerprint(b, "s")


def test_table_fingerprints_batch_value_case_invariant():
    """배치 fingerprint: tname(키)은 보존하되 컬럼명/타입 케이스 진동에는 VALUE 가 불변."""
    import modules.insight as insight

    # rows = (TABLE_NAME, <projection cols...>). 같은 테이블, 컬럼 값 케이스만 다름.
    upper = _FakeConn([("Orders", "Id", "INT"), ("Orders", "CustName", "VARCHAR")])
    lower = _FakeConn([("Orders", "id", "int"), ("Orders", "custname", "varchar")])
    ru = insight._compute_table_fingerprints_batch(upper, "s", ["Orders"])
    rl = insight._compute_table_fingerprints_batch(lower, "s", ["Orders"])
    assert "Orders" in ru and "Orders" in rl  # tname 키 보존(케이스 미변경)
    assert ru["Orders"] == rl["Orders"]       # 해시 VALUE 는 케이스 불변


def test_table_fingerprint_case_invariant():
    """단건 table fingerprint 도 컬럼 케이스 진동에 불변."""
    import modules.insight as insight

    upper = _FakeConn([("Id", "INT"), ("Name", "VARCHAR")])
    lower = _FakeConn([("id", "int"), ("name", "varchar")])
    assert insight._compute_table_fingerprint(upper, "s", "t") == \
        insight._compute_table_fingerprint(lower, "s", "t")


# ── RC3: pending-repair 무진전 backoff ────────────────────────────────────────
def _patch_kv(monkeypatch, insight):
    """insight 의 KV 접근을 in-memory dict 로 대체하고 store 를 반환."""
    store: dict[str, str] = {}

    def _load(conn, conv, key):
        return store.get(key, "")

    def _save(conn, conv, key, val):
        store[key] = val

    monkeypatch.setattr(insight, "load_memory_kv", _load)
    monkeypatch.setattr(insight, "save_memory_kv", _save)
    monkeypatch.setattr(insight, "ds_scope_name", lambda name, **k: name)
    return store


def test_repair_backoff_absent_is_inactive(monkeypatch):
    """KV 부재 = 기존 동작(backoff 없음) — False."""
    import modules.insight as insight

    _patch_kv(monkeypatch, insight)
    assert insight._repair_backoff_active(object()) is False


def test_repair_backoff_set_then_active_then_clear(monkeypatch):
    """set → 미래 시각이라 active, clear → 비활성."""
    import modules.insight as insight

    _patch_kv(monkeypatch, insight)
    conn = object()
    insight._set_repair_backoff(conn, 3600)
    assert insight._repair_backoff_active(conn) is True
    insight._clear_repair_backoff(conn)
    assert insight._repair_backoff_active(conn) is False


def test_repair_backoff_expired_is_inactive(monkeypatch):
    """backoff_until 이 과거면 비활성(만료) — 이후 pending-only 트리거 재허용."""
    import modules.insight as insight

    store = _patch_kv(monkeypatch, insight)
    store["schema_instance_repair_backoff_until"] = (
        datetime.now(timezone.utc) - timedelta(seconds=10)
    ).isoformat()
    assert insight._repair_backoff_active(object()) is False


def test_repair_backoff_minimum_floor(monkeypatch):
    """backoff_sec 가 60 미만이어도 최소 60s 로 바닥 고정(즉시 만료 방지)."""
    import modules.insight as insight

    _patch_kv(monkeypatch, insight)
    conn = object()
    insight._set_repair_backoff(conn, 1)
    assert insight._repair_backoff_active(conn) is True
