"""단위 테스트 — 계정 스코프 cross-conversation 인사이트 회상 (TASK-20260617T082131, Phase 1).

설계: unit/feature-0002-agent-core/docs/DESIGN-account-insight-recall.md

검증 초점(보안 경계):
- G2 격리: owner_account_id 필터 + 현재 대화 제외 + __global__ sentinel 제외 + owner NULL 제외(SQL).
- account_id 무효/PG 미가용 → fail-soft [].
- RECALL flag OFF → no-op(회상 0). flag ON → conv_ids 도출 + 벡터 회상 + top-K/min_sim.

`make test`(agent 이미지)에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

from modules import account_recall


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed: list[str] = []
        self.params: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append(sql)
        self.params.append(params)

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, rows):
        self.cursor_obj = _FakeCursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def _patch_pg(monkeypatch, rows, available=True):
    conn = _FakeConn(rows)
    monkeypatch.setattr("modules.db._pg_available", lambda: available)
    monkeypatch.setattr("modules.db._pg_connect_ro", lambda *a, **k: conn)
    return conn


# ── _load_account_scoped_conv_ids ──────────────────────────────────────────

def test_conv_ids_owner_filter_and_params(monkeypatch):
    conn = _patch_pg(monkeypatch, [("conv-a",), ("conv-b",)])
    out = account_recall._load_account_scoped_conv_ids(
        42, exclude_conversation_id="current-cid", limit=10,
    )
    assert out == ["conv-a", "conv-b"]
    sql = conn.cursor_obj.executed[0]
    # 보안 경계: owner_account_id 일치 + NOT NULL + archived 제외 + 현재 대화 제외 + schema-qualified.
    assert "agent_runtime.core_conversations" in sql
    assert "owner_account_id = %s" in sql
    assert "owner_account_id IS NOT NULL" in sql
    assert "archived_at IS NULL" in sql
    assert "conversation_id <> %s" in sql
    # params: (account_id, exclude, cap)
    assert conn.cursor_obj.params[0] == (42, "current-cid", 10)


def test_conv_ids_excludes_global_sentinel(monkeypatch):
    # SQL 이 sentinel 을 흘려보내도 Python 방어심층이 __global__ 접두를 배제한다.
    _patch_pg(monkeypatch, [("conv-a",), ("__global__",), ("__global__:session:x",), ("conv-b",)])
    out = account_recall._load_account_scoped_conv_ids(7, exclude_conversation_id="cur")
    assert out == ["conv-a", "conv-b"]


def test_conv_ids_excludes_current(monkeypatch):
    _patch_pg(monkeypatch, [("cur",), ("conv-a",)])
    out = account_recall._load_account_scoped_conv_ids(7, exclude_conversation_id="cur")
    assert out == ["conv-a"]


def test_conv_ids_invalid_account(monkeypatch):
    _patch_pg(monkeypatch, [("conv-a",)])
    assert account_recall._load_account_scoped_conv_ids(None) == []
    assert account_recall._load_account_scoped_conv_ids(0) == []
    assert account_recall._load_account_scoped_conv_ids(-5) == []
    assert account_recall._load_account_scoped_conv_ids("abc") == []


def test_conv_ids_pg_unavailable(monkeypatch):
    _patch_pg(monkeypatch, [("conv-a",)], available=False)
    assert account_recall._load_account_scoped_conv_ids(42) == []


def test_conv_ids_limit_cap_zero(monkeypatch):
    _patch_pg(monkeypatch, [("conv-a",)])
    assert account_recall._load_account_scoped_conv_ids(42, limit=0) == []


# ── recall_account_conv_facts ──────────────────────────────────────────────

def test_recall_noop_when_flag_off(monkeypatch):
    # 기본 RECALL OFF — conv_ids 로더가 호출되지 않아야(no-op).
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_RECALL", False)
    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        return ["conv-a"]

    monkeypatch.setattr(account_recall, "_load_account_scoped_conv_ids", _boom)
    assert account_recall.recall_account_conv_facts(42, "매출 추이") == []
    assert called["n"] == 0


def test_recall_empty_query(monkeypatch):
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_RECALL", True)
    assert account_recall.recall_account_conv_facts(42, "   ") == []


def test_recall_applies_min_sim_and_top_k(monkeypatch):
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_RECALL", True)
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_MIN_SIM", 0.5)
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_TOP_K", 2)
    monkeypatch.setattr(account_recall, "_load_account_scoped_conv_ids", lambda *a, **k: ["c1", "c2"])

    fake_rows = [
        {"conversation_id": "c1", "content": "high", "ft_score": 0.9},
        {"conversation_id": "c2", "content": "mid", "ft_score": 0.6},
        {"conversation_id": "c1", "content": "low", "ft_score": 0.2},   # min_sim 미달 → 제외
        {"conversation_id": "c2", "content": "third", "ft_score": 0.55},  # top_k 초과 → 제외
    ]
    monkeypatch.setattr(
        "modules.kb_retrieval._load_rag_documents_for_request_pg",
        lambda conv_ids, q, scopes: list(fake_rows),
    )
    out = account_recall.recall_account_conv_facts(42, "매출 추이", exclude_conversation_id="cur")
    assert [r["content"] for r in out] == ["high", "mid"]  # min_sim 통과 상위 2


def test_recall_passes_exclude_to_loader(monkeypatch):
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_RECALL", True)
    seen = {}

    def _capture(account_id, exclude_conversation_id=None, **k):
        seen["account_id"] = account_id
        seen["exclude"] = exclude_conversation_id
        return []  # 빈 conv_ids → 회상 0(벡터 검색 미호출)

    monkeypatch.setattr(account_recall, "_load_account_scoped_conv_ids", _capture)
    assert account_recall.recall_account_conv_facts(99, "q", exclude_conversation_id="cur-x") == []
    assert seen == {"account_id": 99, "exclude": "cur-x"}
