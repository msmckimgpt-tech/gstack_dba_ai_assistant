"""TASK-0226 — MSSQL datasource per-DB 스캔 커버리지 + 권한 실패 가시화.

배경: insight-worker 는 MSSQL datasource 의 제품 접근가능 DB(WebProductDatabases) 마다
재연결해 스캔한다. RO 로그인이 일부 DB 에만 GRANT 돼 있으면 그 DB 연결이 'Login failed'/
'Cannot open database' 로 막혀 순회가 조용히 건너뛰었다(권한 이슈로 탐색 불가). 본 cycle 은:
  1. 발견 함수(_discover_mssql_databases)가 제품 접근가능 DB union 을 그대로 반환함을 확인,
  2. per-DB 연결/스캔 실패가 scan_report(db_targets/db_failed) telemetry 에 집계되어
     status='degraded' 로 가시화됨을 확인.

실 DB 없이 mock cursor + 순수 로직으로 검증.
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────────
# 1. _discover_mssql_databases — 제품 접근가능 DB union (데이터소스 기준)
# ──────────────────────────────────────────────────────────────────────────
class _FakeCursor:
    """execute(sql, params) 호출을 기록하고 미리 정한 rows 를 fetch 하는 mock."""

    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        return None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        return None


class _FakeMemConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)


def test_discover_returns_product_accessible_dbs():
    """제품 접근가능 DB(WebProductDatabases.SchemaName) union 을 정규화·중복제거해 반환."""
    import modules.insight as insight

    mem = _FakeMemConn([("DB_A",), ("DB_B",), ("DB_A",)])  # 중복 DB_A
    out = insight._discover_mssql_databases(mem, "winsql", {"default_db": "DB_A"})
    # 소문자 dedup — DB_A 한 번, DB_B 한 번. default_db(DB_A)는 이미 포함되어 추가 안 됨.
    assert [d.lower() for d in out] == ["db_a", "db_b"]


def test_discover_appends_default_db_when_not_registered():
    """제품 미등록이어도 default_db 가 있으면 최소 1개는 스캔(폴백)."""
    import modules.insight as insight

    mem = _FakeMemConn([])  # 제품 등록 DB 0건
    out = insight._discover_mssql_databases(mem, "winsql", {"default_db": "FallbackDb"})
    assert [d.lower() for d in out] == ["fallbackdb"]


def test_discover_empty_when_no_registry_and_no_default():
    """등록 DB 도 default_db 도 없으면 빈 목록 → 스캔 skip 신호."""
    import modules.insight as insight

    mem = _FakeMemConn([])
    out = insight._discover_mssql_databases(mem, "winsql", {})
    assert out == []


def test_discover_graceful_on_query_error():
    """레지스트리 조회 예외(테이블 부재 등)는 graceful — default_db 폴백."""
    import modules.insight as insight

    class _BoomConn:
        def cursor(self):
            raise RuntimeError("WebProductDatabases 부재")

    out = insight._discover_mssql_databases(_BoomConn(), "winsql", {"default_db": "DB_X"})
    assert [d.lower() for d in out] == ["db_x"]


# ──────────────────────────────────────────────────────────────────────────
# 2. per-DB 실패 telemetry → status='degraded' 결정 로직
# ──────────────────────────────────────────────────────────────────────────
def _decide_status(scan_report, base_status="ok"):
    """run_insight_cycle 의 status degrade 결정 로직 재현(테스트용 순수 함수).

    실제 코드(insight.run_insight_cycle)의 판정과 동일해야 한다:
      - publish 시도됐으나 생성 0 → degraded (TASK-0131)
      - 발견된 DB 중 하나라도 실패(db_failed>0) → degraded (TASK-0226)
    """
    status = base_status
    pub_failed = int(scan_report.get("publish_failed", 0) or 0)
    generated = (
        int(scan_report.get("schemas_generated", 0) or 0)
        + int(scan_report.get("tables_generated", 0) or 0)
        + int(scan_report.get("schemas_repaired", 0) or 0)
        + int(scan_report.get("tables_repaired", 0) or 0)
    )
    if status == "ok" and pub_failed > 0 and generated == 0:
        status = "degraded"
    db_failed = int(scan_report.get("db_failed", 0) or 0)
    if status == "ok" and db_failed > 0:
        status = "degraded"
    return status


def test_status_degraded_when_some_db_failed():
    """발견 3개 중 1개 연결 실패(GRANT 누락 등) → degraded 가시화."""
    report = {"db_targets": 3, "db_failed": 1, "schemas_generated": 2}
    assert _decide_status(report) == "degraded"


def test_status_ok_when_all_dbs_covered():
    """발견된 모든 DB 가 성공적으로 스캔되면 ok 유지."""
    report = {"db_targets": 3, "db_failed": 0, "schemas_generated": 2}
    assert _decide_status(report) == "ok"


def test_status_ok_when_no_mssql_dbs():
    """MSSQL datasource 없음(MySQL 단일) — db_targets/db_failed 0 → ok."""
    report = {"db_targets": 0, "db_failed": 0, "tables_generated": 5}
    assert _decide_status(report) == "ok"


def test_db_failed_does_not_override_error():
    """이미 error 면 db_failed 가 ok→degraded 규칙을 트리거하지 않는다(error 우선)."""
    report = {"db_targets": 2, "db_failed": 2}
    assert _decide_status(report, base_status="error") == "error"


# ──────────────────────────────────────────────────────────────────────────
# 3. perm_suspect 진단 힌트 — 권한거부 감지(단어경계, REV-20260611-0226 CONCERN)
# ──────────────────────────────────────────────────────────────────────────
import re


def _is_perm_error(err_text: str) -> bool:
    """insight.run_insight_cycle 의 per-DB perm_suspect 판정 재현(테스트용).

    텍스트 토큰은 substring, MSSQL 에러번호는 단어경계 정규식(무관 숫자 오탐 방지).
    """
    s = str(err_text).lower()
    return (
        any(t in s for t in ("login failed", "cannot open database", "permission", "denied"))
        or bool(re.search(r"\b(18456|916|229|297)\b", s))
    )


def test_perm_detect_login_failed():
    assert _is_perm_error("Login failed for user 'ro_agent'. (18456)") is True


def test_perm_detect_cannot_open_database():
    assert _is_perm_error("Cannot open database \"DB_B\" requested by the login.") is True


def test_perm_detect_error_number_word_boundary():
    """에러번호가 단어경계로 매칭(고립된 916)."""
    assert _is_perm_error("Server error 916 occurred") is True


def test_perm_no_false_positive_on_rowcount():
    """무관한 행수(2297 rows)에 '297' 이 substring 매칭되지 않는다(단어경계)."""
    assert _is_perm_error("Query affected 2297 rows in 916283 ms") is False


def test_perm_no_false_positive_on_generic_error():
    """권한과 무관한 일반 오류는 perm_suspect 아님(가짜 힌트 방지)."""
    assert _is_perm_error("Connection timeout after 30s") is False
