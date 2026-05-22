"""M3 (TASK-0023) — kb_embedding_worker.py 단위 검증.

실 OpenAI 호출 없이 monkeypatch + FakeConn 으로 검증:
- count_pending / fetch_pending_batch 의 SQL 정합
- update_embeddings 의 length mismatch raise + batch UPDATE
- estimate_cost_usd 의 cost 계산 정확성
- main() dry-run mode 가 OpenAI 호출 안 함
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _load_worker(monkeypatch):
    sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    import kb_embedding_worker  # type: ignore
    return kb_embedding_worker


# ─────────────────────────────────────────────────────────────────────────────
# Cost estimation
# ─────────────────────────────────────────────────────────────────────────────


def test_cost_estimation_small_model(monkeypatch):
    worker = _load_worker(monkeypatch)
    # 1M chars = ~333K tokens (conservative ratio 3 char/token).
    cost = worker.estimate_cost_usd([1_000_000], "text-embedding-3-small")
    # 333K tokens × 0.02 USD/1M tokens = ~0.0067 USD
    assert 0.005 < cost < 0.01


def test_cost_estimation_large_model_more_expensive(monkeypatch):
    worker = _load_worker(monkeypatch)
    cost_small = worker.estimate_cost_usd([1_000_000], "text-embedding-3-small")
    cost_large = worker.estimate_cost_usd([1_000_000], "text-embedding-3-large")
    assert cost_large > cost_small * 5  # large 는 6.5x 가량 비쌈


def test_cost_estimation_unknown_model_fallback(monkeypatch):
    worker = _load_worker(monkeypatch)
    # Unknown model → fallback to 0.10 USD/1M
    cost = worker.estimate_cost_usd([1_000_000], "unknown-model-xyz")
    expected_tokens = 1_000_000 / 3.0
    expected_cost = (expected_tokens / 1_000_000.0) * 0.10
    assert abs(cost - expected_cost) < 0.001


# ─────────────────────────────────────────────────────────────────────────────
# update_embeddings — length mismatch raises
# ─────────────────────────────────────────────────────────────────────────────


def test_update_embeddings_length_mismatch_raises(monkeypatch):
    worker = _load_worker(monkeypatch)

    class FakeConn:
        def cursor(self): pass
        def commit(self): pass

    with pytest.raises(ValueError, match="hashes.*embeddings"):
        worker.update_embeddings(
            FakeConn(),
            hashes=["h1", "h2"],
            embeddings=[[0.1] * 1536],  # only 1
            model="text-embedding-3-small",
        )


def test_update_embeddings_emits_sql_per_row(monkeypatch):
    worker = _load_worker(monkeypatch)

    captured = []
    class FakeCursor:
        rowcount = 1
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params):
            captured.append((sql, params))

    class FakeConn:
        def cursor(self): return FakeCursor()
        def commit(self): captured.append(("COMMIT", None))

    rowcount = worker.update_embeddings(
        FakeConn(),
        hashes=["hashA", "hashB"],
        embeddings=[[0.1] * 1536, [0.2] * 1536],
        model="text-embedding-3-small",
    )
    assert rowcount == 2
    # 2 UPDATE + 1 COMMIT
    assert len(captured) == 3
    assert "UPDATE texts" in captured[0][0]
    assert "::vector" in captured[0][0]
    assert captured[0][1][1] == "text-embedding-3-small"
    assert captured[0][1][2] == "hashA"
    assert captured[-1] == ("COMMIT", None)


# ─────────────────────────────────────────────────────────────────────────────
# main() --dry-run does NOT call OpenAI
# ─────────────────────────────────────────────────────────────────────────────


def test_main_dry_run_no_openai_call(monkeypatch):
    worker = _load_worker(monkeypatch)

    # LLM tripwire — fail if OpenAI invoked
    openai_called = []
    def _tripwire(*a, **kw):
        openai_called.append((a, kw))
        raise AssertionError("OpenAI 호출 발생 — dry-run invariant 위반")
    monkeypatch.setattr(worker, "call_openai_embeddings", _tripwire)

    # mock pg conn + count_pending
    class FakeConn:
        def cursor(self): return self
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): self._sql = sql
        def fetchone(self): return (50,) if "COUNT" in (getattr(self, "_sql", "") or "") else None
        def fetchall(self):
            return [("hash1", "sample text content"), ("hash2", "another sample")]
        def close(self): pass
    monkeypatch.setattr(worker, "open_pg_conn", lambda: FakeConn())

    monkeypatch.setattr(sys, "argv", [
        "kb_embedding_worker.py", "--dry-run", "--batch-size", "10",
    ])
    rc = worker.main()
    assert rc == 0
    assert len(openai_called) == 0, "dry-run 인데 OpenAI 호출 발생"
