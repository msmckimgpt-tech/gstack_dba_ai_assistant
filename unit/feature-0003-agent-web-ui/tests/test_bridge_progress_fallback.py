"""`/api/progress` steps-fallback 이 브리지 원장을 진행 중 run 으로 오인하지 않는다.

## 이 테스트가 잠그는 사고 (2026-08-27 사용자 제보)

개인 AI 브리지(feature-0043) 대화에는 **서버 run 이 없다**. 그래서 `agent_runtime.kv` 의
`last_status*` 가 아예 비고, `/api/progress` 는 `_load_latest_run_id_from_steps` fallback
("최근 3분 내 step 이 있으면 processing")을 탄다.

그런데 답변이 전달되는 순간 `_materialize_bridge_steps` 가 개인 AI 의 도구 호출 내역을
`run_id = task_id` 로 `agent_runtime.steps` 에 심는다(work_source='bridge-ledger').
이 원장은 **끝난 답변의 기록**인데 fallback 이 "방금 생긴 step = 진행 중" 으로 읽어,
`/api/progress` 는 processing 을, `/api/history` 는 (KV 가 비었으니) 유휴를 보고했다.

프런트는 그 불일치에서 다음을 지연 0ms 로 반복했다:

    loadHistory(유휴) → startRunDetectPolling(baseline=null)
      → detectNewRun 이 processing 을 보고 loadHistory() 재위임
        (preserveScroll 없음 → **화면이 맨 아래로 점프**)
      → 다시 유휴 → baseline=null → …

사용자에게는 "AI 답변을 받은 직후 스크롤이 계속 최하단으로 끌려간다" 로 보였고, 원장 step 이
3분을 넘겨 늙을 때까지 이어졌다.

프런트측 수렴 계약은 `tests/verify_run_detect_poll.mjs` (S9~S11)가 잠그고, 여기서는 **서버가
끝난 원장을 진행 중이라 말하지 않는다**는 정본 계약을 잠근다. 두 층 모두 필요하다 — 서버
불일치가 다른 이유로 다시 생겨도 화면이 스스로 수렴해야 하고(프런트), 애초에 거짓 진행 신호를
내보내지 않아야 한다(서버).
"""
from __future__ import annotations

import datetime
import re

import pytest

import app as appmod


class _FakeCursor:
    def __init__(self, row, sink):
        self._row = row
        self._sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._sink.append((sql, params))

    def fetchone(self):
        return self._row


class _FakePg:
    def __init__(self, row, sink):
        self._row = row
        self._sink = sink
        self.closed = False

    def cursor(self):
        return _FakeCursor(self._row, self._sink)

    def close(self):
        self.closed = True


def _with_pg(monkeypatch, row):
    """PG 백엔드 활성 + `shared.db._pg_connect` 대체. 실행된 (sql, params) 를 돌려준다."""
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    import shared.db as _db

    sink: list[tuple[str, object]] = []
    monkeypatch.setattr(_db, "_pg_connect", lambda: _FakePg(row, sink), raising=False)
    return sink


def _ago(seconds: int) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds)


# ── 쿼리 계약: 브리지 원장은 집계 대상에서 빠진다 ─────────────────────────────

def test_fallback_query_excludes_bridge_ledger(monkeypatch):
    """원장 제외가 **쿼리의 WHERE 절**에, **부정 비교**로 있어야 한다.

    두 가지를 함께 잠근다 —
    ① 위치: 사후 필터는 소용없다. 원장 run 이 최신이면 `ORDER BY … LIMIT 1` 이 그 run 만
       뽑아오므로, 가져온 뒤 걸러도 함께 있던 실 run 을 못 본다.
    ② 방향: `<>` 가 `=` 로 뒤집히면 **원장만** 남는다(정확히 반대 동작). 컬럼명·파라미터
       존재만 보면 이 뒤집기를 통과시킨다(codex 적대 리뷰 [P2]) — 연산자까지 단언한다.
    """
    sink = _with_pg(monkeypatch, None)
    appmod._load_latest_run_id_from_steps("conv-1")

    assert sink, "fallback 쿼리가 실행되지 않았다"
    sql, params = sink[0]

    upper = sql.upper()
    assert "WHERE" in upper and "GROUP BY" in upper, "예상한 쿼리 형태가 아니다"
    where = " ".join(sql[upper.index("WHERE"):upper.index("GROUP BY")].split())
    assert re.search(r"COALESCE\(\s*work_source\s*,\s*''\s*\)\s*(<>|!=)\s*%s", where), (
        f"WHERE 절에 원장 **부정** 비교가 없다 (실제: {where!r}) — "
        "`=` 로 뒤집히면 원장만 남아 동작이 정확히 반대가 된다"
    )
    assert "bridge-ledger" in list(params or []), (
        "원장 표식이 쿼리 파라미터로 전달되지 않는다 — 제외가 실제로 걸리지 않는다"
    )


def test_bridge_only_conversation_reports_no_run(monkeypatch):
    """원장만 있는 대화(= 브리지 전용) 는 '진행 중 run 없음' 이다.

    fallback 쿼리가 원장을 제외하면 남는 행이 없어 fetchone() 이 None 이 된다.
    이 반환이 `/api/progress` 의 run_id="" / status="" 로 이어져, 프런트 감지기가
    재로드를 위임하지 않는다(= 스크롤이 유지된다).
    """
    _with_pg(monkeypatch, None)
    assert appmod._load_latest_run_id_from_steps("conv-bridge") == ("", False)


# ── 기존 계약(실 run) 은 그대로다 ────────────────────────────────────────────

def test_recent_real_run_still_reports_processing(monkeypatch):
    """실 서버 run 의 최근 step 은 여전히 processing 으로 읽힌다(회귀 방지)."""
    _with_pg(monkeypatch, ("run-real", _ago(10)))
    assert appmod._load_latest_run_id_from_steps("conv-1") == ("run-real", True)


def test_old_real_run_is_not_recent(monkeypatch):
    """3분을 넘긴 step 은 진행 중이 아니다(기존 임계 유지)."""
    _with_pg(monkeypatch, ("run-real", _ago(600)))
    assert appmod._load_latest_run_id_from_steps("conv-1") == ("run-real", False)


def test_naive_timestamp_is_treated_as_utc(monkeypatch):
    """tz 없는 timestamp 도 UTC 로 해석한다(기존 동작 유지 — 로컬시각 오판 차단)."""
    naive = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    _with_pg(monkeypatch, ("run-real", naive))
    assert appmod._load_latest_run_id_from_steps("conv-1") == ("run-real", True)


def test_non_pg_backend_skips_fallback(monkeypatch):
    """비-PG 런타임은 fallback 자체가 없다(기존 계약)."""
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "mysql")
    assert appmod._load_latest_run_id_from_steps("conv-1") == ("", False)


# ── 생산자·소비자가 같은 표식을 쓴다 ─────────────────────────────────────────

def test_ledger_marker_matches_producer():
    """제외 표식이 `_materialize_bridge_steps` 의 INSERT 값과 **글자 그대로** 같아야 한다.

    두 곳이 갈리면 제외는 조용히 무효가 된다(테스트는 통과하는데 라이브만 다시 튄다).
    """
    from pathlib import Path

    from routers import _conv_store

    marker = _conv_store._BRIDGE_LEDGER_WORK_SOURCE
    producer = Path(_conv_store.__file__).resolve().parent / "ai_tools.py"
    src = producer.read_text(encoding="utf-8")
    assert f"'{marker}'" in src, (
        f"원장 생산자(ai_tools._materialize_bridge_steps)가 '{marker}' 를 쓰지 않는다 — "
        "표식이 갈렸다"
    )


@pytest.mark.parametrize("conversation_id", ["", None])
def test_blank_conversation_id_is_safe(monkeypatch, conversation_id):
    """대화 식별 불가 시에도 예외 없이 '없음' 으로 수렴한다(fail-safe)."""
    _with_pg(monkeypatch, None)
    assert appmod._load_latest_run_id_from_steps(conversation_id) == ("", False)
