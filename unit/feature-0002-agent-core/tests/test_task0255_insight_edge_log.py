"""TASK-0255 R1 — insight scan_failed 로그 edge-trigger.

매 8s cycle 마다 불안정 datasource 전부를 WARNING 으로 재기록하던 도배(2일 ~20만 줄)를, (scope_key, db_name)
의 직전 분류 상태 대비 **변경 시에만** WARNING(→True) / 지속은 DEBUG(→False)로 전환한 핵심 판정 함수를 검증.
"""
from __future__ import annotations

from modules import insight


def _reset():
    insight._LAST_DS_SCAN_STATUS.clear()


def test_first_observation_is_change():
    _reset()
    assert insight._ds_scan_status_changed("mysql-abc", None, "circuit_open") is True


def test_repeated_same_status_not_change():
    _reset()
    assert insight._ds_scan_status_changed("mysql-abc", None, "circuit_open") is True
    assert insight._ds_scan_status_changed("mysql-abc", None, "circuit_open") is False
    assert insight._ds_scan_status_changed("mysql-abc", None, "circuit_open") is False


def test_transition_between_statuses_is_change():
    _reset()
    assert insight._ds_scan_status_changed("mysql-abc", None, "circuit_open") is True
    assert insight._ds_scan_status_changed("mysql-abc", None, "perm_failed") is True   # 전이 → WARNING
    assert insight._ds_scan_status_changed("mysql-abc", None, "perm_failed") is False  # 지속 → DEBUG
    assert insight._ds_scan_status_changed("mysql-abc", None, "circuit_open") is True  # 재전이 → WARNING


def test_recover_to_healthy_is_change():
    _reset()
    insight._ds_scan_status_changed("mysql-abc", None, "circuit_open")
    assert insight._ds_scan_status_changed("mysql-abc", None, "healthy") is True       # 회복 전이


def test_per_db_keys_independent():
    _reset()
    # MSSQL: 같은 datasource(scope)의 서로 다른 DB 는 독립 키로 추적.
    assert insight._ds_scan_status_changed("mssql-x", "db1", "circuit_open") is True
    assert insight._ds_scan_status_changed("mssql-x", "db2", "circuit_open") is True   # 다른 db → 별도 키
    assert insight._ds_scan_status_changed("mssql-x", "db1", "circuit_open") is False  # db1 지속
