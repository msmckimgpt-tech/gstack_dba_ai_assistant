"""rel-selfheal: insight 관계 유지보수 cadence 순수 로직 단위 테스트 (QA-F2c/B-F1).

DB 연결 없이 검증한다 — instance-scan 커서 키의 DB(catalog) 분리(B-F1)와
_is_refresh_due 게이트 의미론(D1a 본체). PG I/O 경로는 라이브 스택 검증 대상.
"""
from datetime import datetime, timedelta, timezone

from shared import config as cfg
from modules import insight as I
from modules.kb_scope import _is_refresh_due


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def test_instance_scan_cursor_key_per_db():
    """B-F1: MSSQL multi-DB 는 커서를 DB별 분리 — 첫 DB 스탬프의 나머지 DB 독점 차단.

    active database 미설정(MySQL/단일 DB)이면 기존 키 그대로(하위호환 — 기존 스탬프 유효).
    """
    prev_ds = cfg.get_active_datasource()
    try:
        cfg.set_active_datasource("dsx", engine="mssql")
        cfg.set_active_database("DBX")
        k_db = I._instance_scan_cursor_key()
        assert k_db.endswith(":db:dbx") and ":ds:dsx" in k_db

        cfg.set_active_database("dby")
        assert I._instance_scan_cursor_key().endswith(":db:dby")  # DB 마다 상이

        cfg.set_active_database(None)
        k_plain = I._instance_scan_cursor_key()
        assert ":db:" not in k_plain and ":ds:dsx" in k_plain
    finally:
        cfg.set_active_database(None)
        cfg.set_active_datasource(prev_ds)


def test_rel_cadence_refresh_due_semantics():
    """D1a 게이트: kv 부재=due(첫 사이클 백필) / 최근 스탬프=미due / 경과=due."""
    now = datetime.now(timezone.utc)
    m = {}
    assert _is_refresh_due(m, "relationship_infer_at:x", 21600) is True  # 부재 → due
    m["relationship_infer_at:x"] = _iso(now - timedelta(seconds=60))
    assert _is_refresh_due(m, "relationship_infer_at:x", 21600) is False  # 최근 → 미due
    m["relationship_infer_at:x"] = _iso(now - timedelta(seconds=21601))
    assert _is_refresh_due(m, "relationship_infer_at:x", 21600) is True  # 경과 → due


def test_rel_cadence_disabled_by_nonpositive_interval():
    """AGENT_RELATIONSHIP_REINFER_SEC<=0 = off — insight 게이트는 `sec > 0` 가드가 필수
    (_is_refresh_due 단독은 span<=0 에서 due 를 반환하는 의미론)."""
    rel_reinfer_sec = 0
    due = bool(rel_reinfer_sec > 0 and _is_refresh_due({}, "k", rel_reinfer_sec))
    assert due is False
