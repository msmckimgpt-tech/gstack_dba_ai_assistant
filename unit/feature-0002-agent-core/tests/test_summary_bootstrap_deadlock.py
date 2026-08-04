"""FR-summary-bootstrap-deadlock — 요약 미보유 대화가 PG 읽기 실패로 오판되던 교착 회귀 가드.

라이브 실측(2026-08-04, 배포 `c4701a17` 직후): 요약 writer 를 복구했는데도
`refresh_conversation_summary` 가 `saved=False` 로 끝나고 `agent_runtime.summary` 가 계속 0행이었다.
로그: `load_memory_context: PG partial failure (summary=False msgs=True kv=True), falling back to MySQL`.

원인 — `_read_runtime_pg` 의 호출 계약은 "`None` = 읽기 실패"인데 `PgRuntimeBackend.load_summary`
가 **행 없음도 `None`** 으로 돌려줬다. 두 사건이 구분되지 않아 요약이 아직 없는 대화가 전부 PG 실패로
분류 → `conn=None` 인 큐레이션 훅에서 MySQL 폴백 → 예외 → 요약 미저장. **요약이 없으니 읽기가
실패하고, 실패하니 첫 요약을 못 쓰는 부트스트랩 교착**이라 writer 복구가 실효 0 이었다.

검증:
  B1  행 없음 → `''`(빈 문자열). `None` 이면 실패 신호와 충돌한다.
  B2  행 있음 → 본문 그대로.
  B3  NULL 본문 → `''`.
  B4  `load_memory_context` 가 요약 없는 대화에서 **PG 경로를 통과**한다(MySQL 폴백 미진입).
      conn=None 을 넘겨 폴백을 타면 AttributeError 가 나므로, 통과 자체가 증거다.

`make test`(agent 이미지, --no-deps)에서 DB 없이 fake 로 실행된다.
"""
from __future__ import annotations

import pathlib
import sys

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from modules import memory as memory_mod  # noqa: E402
from modules.runtime_backend import PgRuntimeBackend  # noqa: E402


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        return None

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row

    def cursor(self):
        return _FakeCursor(self._row)


# ── B1~B3 load_summary 반환 계약 ────────────────────────────────────────────────

def test_load_summary_missing_row_returns_empty_string():
    """행 없음은 `''` — `None`(=읽기 실패 신호)과 섞이면 안 된다."""
    out = PgRuntimeBackend().load_summary(_FakeConn(None), conversation_id="c1")
    assert out == "", "행 없음을 None 으로 돌려주면 요약 미보유 대화가 읽기 실패로 오판된다"
    assert out is not None


def test_load_summary_existing_row_returns_body():
    out = PgRuntimeBackend().load_summary(_FakeConn(("이전 요약 본문",)), conversation_id="c1")
    assert out == "이전 요약 본문"


def test_load_summary_null_body_returns_empty_string():
    out = PgRuntimeBackend().load_summary(_FakeConn((None,)), conversation_id="c1")
    assert out == ""


# ── B4 load_memory_context 가 PG 경로를 통과 ────────────────────────────────────

def test_load_memory_context_passes_pg_path_without_summary(monkeypatch):
    """요약 없는 대화에서도 PG 경로로 완주한다 — MySQL 폴백에 빠지지 않는다.

    conn=None 을 넘긴다: 폴백을 타면 `conn.cursor()` 에서 AttributeError 가 난다.
    즉 예외 없이 반환되는 것 자체가 "폴백 미진입" 의 증거다(교착 재발 시 즉시 실패).
    """
    from datetime import datetime, timezone

    now = datetime(2026, 8, 4, tzinfo=timezone.utc)
    reads = {
        "load_summary": "",                                  # 행 없음 → 빈 문자열
        "load_messages": [("user", "안녕", None, now)],
        "load_kv_all": [("topic", "테스트 주제")],
    }
    monkeypatch.setattr(
        "modules.runtime_backend.AGENT_RUNTIME_READ_BACKEND", "postgres", raising=False
    )
    monkeypatch.setattr(
        "modules.runtime_backend._read_runtime_pg",
        lambda method, **kw: reads[method],
    )

    summary, rows, kv = memory_mod.load_memory_context(None, "c1", 10)
    assert summary == ""
    assert rows == [("user", "안녕", now)]
    assert kv == {"topic": "테스트 주제"}


def test_load_memory_context_still_falls_back_on_real_failure(monkeypatch):
    """진짜 읽기 실패(`None`)는 여전히 MySQL 폴백으로 간다 — 규약을 무디게 만들지 않았다."""
    monkeypatch.setattr(
        "modules.runtime_backend.AGENT_RUNTIME_READ_BACKEND", "postgres", raising=False
    )
    monkeypatch.setattr("modules.runtime_backend._read_runtime_pg", lambda method, **kw: None)

    called = {"mysql": False}

    class _MyCur:
        def execute(self, *a, **k):
            called["mysql"] = True

        def fetchone(self):
            return None

        def fetchall(self):
            return []

        def close(self):
            return None

    class _MyConn:
        def cursor(self):
            return _MyCur()

    memory_mod.load_memory_context(_MyConn(), "c1", 10)
    assert called["mysql"] is True, "PG 읽기 실패 시에는 MySQL 폴백이 살아 있어야 한다"
