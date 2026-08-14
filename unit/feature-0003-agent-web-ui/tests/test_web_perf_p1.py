"""feature-0028 (web-perf P1) — 계약 테스트.

feature-0026 전수 조사가 지목한 web 계층 병목 4건의 개선 계약을 잠근다:
A. ask_result long-poll 스냅샷이 **워커 스레드**에서 실행(이벤트 루프 stall 제거) +
   스냅샷 PG 조회가 **단일 연결 번들**(호출당 4~5 연결 → 1).
B. 권한 카탈로그 TTL 캐시(+ product CRUD 무효화) · 세션 LastSeenAt throttle.
C. web memory 연결 풀 opt-in.

계약 검증은 소스 잠금 + 순수 함수 단위 — 라이브 DB 없이 결정적으로 돈다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import app as webapp
import web_context as wc


# ── A. 스냅샷 단일 연결 번들 + 헬퍼 동치 ──────────────────────────────────────
def test_snapshot_uses_single_pg_connection(monkeypatch):
    """번들 경로: `_pg_connect` 는 스냅샷 1회당 정확히 1번만 열린다."""
    import shared.db as sdb
    from routers import _conv_store as cs

    opened: list = []

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params=None):
            self._sql = sql

        def fetchall(self):
            if "FROM agent_runtime.kv" in self._sql:
                return [("last_status", "done"), ("last_status_run_id", "run-1")]
            if "FROM agent_runtime.messages" in self._sql:
                return []
            return []

        def fetchone(self):
            return (3, None)

    class _Conn:
        def cursor(self):
            return _Cur()

        def close(self):
            pass

    def _mk(*a, **k):
        opened.append(1)
        return _Conn()

    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    monkeypatch.setattr(sdb, "_pg_connect", _mk)
    bundle = cs._ask_snapshot_pg_bundle("cid-x")
    assert bundle is not None
    assert len(opened) == 1, "스냅샷 PG 조회는 단일 연결이어야 한다"
    assert bundle["kv"]["last_status"] == "done"
    assert bundle["step_count"] == 3


def test_snapshot_bundle_returns_none_without_pg(monkeypatch):
    """PG 백엔드가 아니면 None → 호출측이 종전 개별 로더로 폴백(계약 불변)."""
    from routers import _conv_store as cs

    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "mysql")
    assert cs._ask_snapshot_pg_bundle("cid-x") is None


def test_display_status_from_step_at_matches_rules():
    """stale 판정 규칙 동치 + tz-aware 정규화(KST wall-clock 오인 회귀 차단)."""
    fresh = datetime.utcnow() - timedelta(seconds=5)
    old = datetime.utcnow() - timedelta(seconds=webapp.WEB_PROGRESS_STALE_TIMEOUT_SECONDS + 60)
    assert webapp._display_status_from_step_at("done", "", None) == ("done", False)
    assert webapp._display_status_from_step_at("processing", "", fresh) == ("processing", False)
    assert webapp._display_status_from_step_at("processing", "", old) == ("stale_error", True)
    # tz-aware(예: KST) 입력도 UTC 로 정규화돼 fresh 로 판정돼야 한다.
    aware = datetime.now(timezone(timedelta(hours=9))) - timedelta(seconds=5)
    assert webapp._display_status_from_step_at("processing", "", aware) == ("processing", False)


def test_ask_result_polls_in_worker_thread():
    """(소스 잠금) long-poll 스냅샷은 asyncio.to_thread 로 — async 본문 blocking DB 금지."""
    src = (Path(webapp.__file__).parent / "routers" / "conversations.py").read_text(encoding="utf-8")
    i = src.index("async def ask_result(")
    # 함수 **경계**로 자른다. 종전엔 고정 6,000자 창이라 본문이 그보다 길어지면 아래 마커를
    # 못 찾고 ValueError 로 터졌다 — 계약 위반이 아니라 창 부족인데 실패로 보이는 취약점.
    _next = src.find("\n@router.", i)
    body = src[i:_next if _next != -1 else len(src)]
    assert "await asyncio.to_thread(_poll_once)" in body
    # 루프 **본문** 안에서 동기 커넥션을 직접 열지 않는다(헬퍼 안으로 이동).
    loop_start = body.index("while True:")
    loop_end = body.index("last_snapshot.pop(", loop_start)
    assert "app._connect_memory()" not in body[loop_start:loop_end]
    # 커넥션은 워커 스레드에서 도는 헬퍼가 소유하고 finally 로 닫는다.
    helper = body[body.index("def _poll_once("):loop_start]
    assert "app._connect_memory()" in helper and "poll_conn.close()" in helper


# ── B. 권한 카탈로그 캐시 · 세션 touch throttle ────────────────────────────────
@pytest.fixture(autouse=True)
def _isolate_perm_cache():
    """§18.8 qa C6: 카탈로그 캐시는 모듈 전역이고 기본 활성 — 테스트 간 누수를 전후 무효화로
    차단(향후 집행 경로 fake-conn 테스트 추가 시 순서 의존 flake 방지)."""
    wc.invalidate_permission_catalog_cache()
    yield
    wc.invalidate_permission_catalog_cache()

def test_permission_catalog_cache_hits_and_invalidates(monkeypatch):
    calls: list = []

    class _Cur:
        def execute(self, sql, params=None):
            calls.append(1)

        def fetchall(self):
            return []

        def close(self):
            pass

    class _Conn:
        def cursor(self, dictionary=False):
            return _Cur()

    monkeypatch.setattr(wc, "_PERM_CATALOG_TTL_SEC", 30, raising=False)
    wc.invalidate_permission_catalog_cache()
    wc._resolve_permission_catalog(_Conn())
    wc._resolve_permission_catalog(_Conn())
    assert len(calls) == 1, "TTL 이내 2회차는 캐시 히트여야 한다"
    wc.invalidate_permission_catalog_cache()
    wc._resolve_permission_catalog(_Conn())
    assert len(calls) == 2, "무효화 후에는 재조회"


def test_permission_catalog_cache_returns_copies(monkeypatch):
    """캐시 히트 반환값을 호출측이 변형해도 캐시가 오염되지 않는다."""
    class _Cur:
        def execute(self, sql, params=None):
            pass

        def fetchall(self):
            return []

        def close(self):
            pass

    class _Conn:
        def cursor(self, dictionary=False):
            return _Cur()

    monkeypatch.setattr(wc, "_PERM_CATALOG_TTL_SEC", 30, raising=False)
    wc.invalidate_permission_catalog_cache()
    defs, codes, cmap = wc._resolve_permission_catalog(_Conn())
    n = len(codes)
    codes.add("bogus.code")
    defs.append({"code": "bogus.code"})
    _, codes2, _ = wc._resolve_permission_catalog(_Conn())
    assert "bogus.code" not in codes2 and len(codes2) == n
    wc.invalidate_permission_catalog_cache()


def test_session_touch_throttle(monkeypatch):
    # 기록은 성공 후(_session_touch_done)에만 — due 판정은 마지막 성공 기록 기준(§18.8 qa C7).
    monkeypatch.setattr(wc, "_SESSION_TOUCH_MIN_SEC", 60, raising=False)
    wc._SESSION_TOUCH_AT.clear()
    assert wc._session_touch_due("h1") is True   # 최초는 항상 due
    wc._session_touch_done("h1")
    assert wc._session_touch_due("h1") is False  # 간격 내 억제
    assert wc._session_touch_due("h2") is True   # 세션별 독립
    wc._session_touch_done("h2")
    # 상한 초과 시 메모리 무한 증가 방지(전체 비움)
    monkeypatch.setattr(wc, "_SESSION_TOUCH_MAX_KEYS", 2, raising=False)
    for h in ("h3", "h4", "h5"):
        wc._session_touch_due(h)
        wc._session_touch_done(h)
    assert len(wc._SESSION_TOUCH_AT) <= 2


def test_session_touch_disabled_by_zero(monkeypatch):
    monkeypatch.setattr(wc, "_SESSION_TOUCH_MIN_SEC", 0, raising=False)
    wc._SESSION_TOUCH_AT.clear()
    assert wc._session_touch_due("h1") is True
    wc._session_touch_done("h1")
    assert wc._session_touch_due("h1") is True  # 0 = 종전 동작(매 요청)


def test_product_crud_invalidates_catalog_cache():
    """(소스 잠금) 동적 권한을 바꾸는 product CRUD commit 마다 캐시 무효화 호출."""
    src = (Path(webapp.__file__).parent / "routers" / "admin_products.py").read_text(encoding="utf-8")
    assert src.count("app.invalidate_permission_catalog_cache()") >= 4


# ── C. web memory 풀 opt-in ────────────────────────────────────────────────────
def test_web_pool_flag_parsing_and_fallback(monkeypatch):
    """§18.8 qa C3: 배포 설정값(_WEB_DB_POOL_ENABLED)을 단언하지 않는다 — 운영에서 켜는 순간
    CI 가 적색이 되는 자기유발 실패. 기본값 **파싱 규칙**과 폴백 배선만 검증한다."""
    def _parse(v):
        return str(v or "").strip().lower() in ("1", "true", "yes")

    assert _parse(None) is False and _parse("") is False and _parse("0") is False
    assert _parse("1") is True and _parse("true") is True and _parse("YES") is True
    src = (Path(webapp.__file__).parent / "routers" / "_conv_store.py").read_text(encoding="utf-8")
    assert 'os.environ.get("WEB_DB_POOL_ENABLED", "")' in src  # 기본 미설정 = OFF
    i = src.index("def _open_memory_connection(")
    body = src[i:i + 2000]
    assert "_pooled_connect(params)" in body and "app.mysql.connector.connect(**params)" in body


# ── A2 (§18.8 backend B-2): **합성 함수** 동치성 — 컴포넌트 단위로는 못 잡는 계약 ──────
class _FakePgCur:
    """스냅샷 번들/개별 로더가 쓰는 PG 커서 fake (쿼리 종류로 응답 분기)."""

    def __init__(self, state):
        self.state = state
        self._sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._sql = sql

    def close(self):
        pass

    def fetchall(self):
        s = self._sql
        if "FROM agent_runtime.kv" in s:
            return list(self.state["kv"].items())
        if "FROM agent_runtime.messages" in s:
            return list(self.state["messages"])
        if "FROM agent_runtime.steps" in s:
            return []
        return []

    def fetchone(self):
        s = self._sql
        if "COUNT(*), MAX(created_at)" in s:  # 번들 경로(집계 2종 한 문장)
            return (self.state["step_count"], self.state["step_at"])
        if "COUNT(*)" in s:                    # 개별 경로 step count
            return (self.state["step_count"],)
        if "MAX(created_at)" in s:             # 개별 경로 last step at
            return (self.state["step_at"],)
        return None


class _FakePgConn:
    def __init__(self, state):
        self.state = state

    def cursor(self):
        return _FakePgCur(self.state)

    def close(self):
        pass


def _snapshot_both_paths(monkeypatch, state):
    """같은 데이터로 (번들 경로, 개별 로더 경로) 스냅샷을 각각 만들어 돌려준다."""
    import shared.db as sdb
    from routers import _conv_store as cs

    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    monkeypatch.setattr(sdb, "_pg_connect", lambda *a, **k: _FakePgConn(state))
    monkeypatch.setattr(webapp, "_load_step_meta", lambda *a, **k: {})
    monkeypatch.setattr(webapp, "_load_steps_for_message", lambda *a, **k: [])
    monkeypatch.setattr(webapp, "_read_llm_provider_status", lambda: {"state": "ok"})

    bundled = cs._build_ask_status_snapshot(None, "cid-eq")
    monkeypatch.setattr(webapp, "_ask_snapshot_pg_bundle", lambda cid: None)  # 폴백 강제
    legacy = cs._build_ask_status_snapshot(None, "cid-eq")
    return bundled, legacy


def _state(status="done", run_id="run-1", step_at=None, with_answer=True):
    kv = {"last_status": status, "last_status_at": "", "last_status_run_id": run_id,
          "last_duration_ms": "1234", "last_error": ""}
    msgs = []
    if with_answer:
        msgs = [(7, "assistant", "답변 본문", "2026-07-28 04:00:00",
                 {"run_id": run_id})]
    return {"kv": kv, "messages": msgs, "step_count": 3, "step_at": step_at}


def test_snapshot_bundle_equals_legacy_terminal_with_answer(monkeypatch):
    b, l = _snapshot_both_paths(monkeypatch, _state())
    assert b == l and b["has_answer"] is True and b["step_count"] == 3


def test_snapshot_bundle_equals_legacy_processing_fresh(monkeypatch):
    fresh = datetime.utcnow() - timedelta(seconds=3)
    b, l = _snapshot_both_paths(monkeypatch, _state(status="processing", step_at=fresh))
    assert b == l and b["is_stale"] is False and b["is_processing"] is True


def test_snapshot_bundle_equals_legacy_processing_stale(monkeypatch):
    old = datetime.utcnow() - timedelta(seconds=webapp.WEB_PROGRESS_STALE_TIMEOUT_SECONDS + 120)
    b, l = _snapshot_both_paths(monkeypatch, _state(status="processing", step_at=old))
    assert b == l and b["is_stale"] is True and b["status"] == "stale_error"


def test_snapshot_bundle_equals_legacy_without_run_id(monkeypatch):
    b, l = _snapshot_both_paths(monkeypatch, _state(run_id="", with_answer=False))
    assert b == l and b["step_count"] == 0 and b["has_answer"] is False


# ── §18.8 B-3: 인가 집행 경로는 카탈로그 캐시를 쓰지 않는다(비결정적 403 차단) ──────
def test_enforcement_path_bypasses_catalog_cache():
    src = (Path(wc.__file__)).read_text(encoding="utf-8")
    i = src.index("def _decorate_account_rows(")
    j = src.index("\ndef ", i + 10)
    body = src[i:j]
    assert "_resolve_permission_catalog(conn, use_cache=False)" in body, (
        "집행 경로(effective permission map 생성)는 실조회여야 한다"
    )


def test_catalog_cache_can_be_bypassed_per_call(monkeypatch):
    calls: list = []

    class _Cur:
        def execute(self, sql, params=None):
            calls.append(1)

        def fetchall(self):
            return []

        def close(self):
            pass

    class _Conn:
        def cursor(self, dictionary=False):
            return _Cur()

    monkeypatch.setattr(wc, "_PERM_CATALOG_TTL_SEC", 30, raising=False)
    wc._resolve_permission_catalog(_Conn())                     # 캐시 채움
    wc._resolve_permission_catalog(_Conn())                     # 히트
    assert len(calls) == 1
    wc._resolve_permission_catalog(_Conn(), use_cache=False)    # 우회 — 실조회
    assert len(calls) == 2


def test_session_touch_recorded_only_after_success(monkeypatch):
    """§18.8 qa C7: due 판정만으로 타임스탬프를 남기지 않는다(실패한 UPDATE 는 재시도 가능)."""
    monkeypatch.setattr(wc, "_SESSION_TOUCH_MIN_SEC", 60, raising=False)
    wc._SESSION_TOUCH_AT.clear()
    assert wc._session_touch_due("hX") is True
    assert wc._session_touch_due("hX") is True, "성공 기록 전에는 계속 due (UPDATE 실패 재시도)"
    wc._session_touch_done("hX")
    assert wc._session_touch_due("hX") is False
