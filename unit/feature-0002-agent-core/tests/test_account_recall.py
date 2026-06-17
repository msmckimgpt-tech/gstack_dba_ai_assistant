"""단위 테스트 — 계정 스코프 cross-conversation 인사이트 회상 (TASK-20260617T082131, B′).

설계: unit/feature-0002-agent-core/docs/DESIGN-account-insight-recall.md

검증 초점(보안 경계):
- G1: fork 대화 SQL 배제(`forked_from_conversation_id IS NULL`).
- G2: owner_account_id 격리 + 현재 대화/`__global__` sentinel 제외 + owner NULL(SQL).
- G3: 회상은 account_insight source_type 만(user_confirm 등 PII prose 제외) + _mask_prose 2차.
- G4: 회상 row 의 conversation_id 가 계정 소유 집합 밖이면 배제.
- 벡터-only fail-closed: 쿼리 임베딩 None → 회상 0(trigram fallback 안 함, min_sim 척도 혼동 회피).
- opt-out / flag OFF / account 무효 / PG 미가용 → fail-soft [].

`make test`(agent 이미지)에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

from modules import account_recall
from modules.kb_scope import _mask_prose


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

    def fetchone(self):
        return self._rows[0] if self._rows else None

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


# ── _load_account_scoped_conv_ids (G1/G2) ──────────────────────────────────

def test_conv_ids_owner_filter_and_fork_exclusion(monkeypatch):
    conn = _patch_pg(monkeypatch, [("conv-a",), ("conv-b",)])
    out = account_recall._load_account_scoped_conv_ids(42, exclude_conversation_id="cur", limit=10)
    assert out == ["conv-a", "conv-b"]
    sql = conn.cursor_obj.executed[0]
    assert "agent_runtime.core_conversations" in sql
    assert "owner_account_id = %s" in sql
    assert "owner_account_id IS NOT NULL" in sql
    assert "archived_at IS NULL" in sql
    assert "forked_from_conversation_id IS NULL" in sql      # G1
    assert "conversation_id <> %s" in sql
    assert conn.cursor_obj.params[0] == (42, "cur", 10)


def test_conv_ids_excludes_global_sentinel_and_current(monkeypatch):
    _patch_pg(monkeypatch, [("conv-a",), ("__global__",), ("__global__:session:x",), ("cur",), ("conv-b",)])
    out = account_recall._load_account_scoped_conv_ids(7, exclude_conversation_id="cur")
    assert out == ["conv-a", "conv-b"]


def test_conv_ids_invalid_account_and_pg_unavailable(monkeypatch):
    _patch_pg(monkeypatch, [("conv-a",)])
    assert account_recall._load_account_scoped_conv_ids(None) == []
    assert account_recall._load_account_scoped_conv_ids(0) == []
    assert account_recall._load_account_scoped_conv_ids("x") == []
    _patch_pg(monkeypatch, [("conv-a",)], available=False)
    assert account_recall._load_account_scoped_conv_ids(42) == []


# ── recall_account_conv_facts (G3/G4 + 벡터-only + flags) ───────────────────

def _setup_recall(monkeypatch, normalized_rows, *, embed=(0.1, 0.2, 0.3), opted_out=False, conv_ids=("c1", "c2")):
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_RECALL", True)
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_MIN_SIM", 0.5)
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_TOP_K", 2)
    monkeypatch.setattr(account_recall, "_load_account_scoped_conv_ids", lambda *a, **k: list(conv_ids))
    monkeypatch.setattr(account_recall, "_account_recall_opted_out", lambda *a, **k: opted_out)
    monkeypatch.setattr("modules.db._pg_available", lambda: True)
    monkeypatch.setattr("modules.db._pg_connect_ro", lambda *a, **k: _FakeConn([]))
    monkeypatch.setattr("modules.kb_retrieval._embed_query_vector", lambda q: (list(embed) if embed else None))

    class _FakeBackend:
        def search_rag_documents_vector(self, *a, **k):
            return [("raw",)]  # _normalize 가 무시하고 normalized_rows 반환
    monkeypatch.setattr("modules.kb_backend.PgKbBackend", _FakeBackend)
    monkeypatch.setattr("modules.kb_retrieval._normalize_rag_doc_rows", lambda rows: list(normalized_rows))


def test_recall_flag_off_is_noop(monkeypatch):
    monkeypatch.setattr(account_recall, "AGENT_ACCOUNT_INSIGHT_RECALL", False)
    called = {"n": 0}
    monkeypatch.setattr(account_recall, "_load_account_scoped_conv_ids",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1) or ["c1"])
    assert account_recall.recall_account_conv_facts(42, "매출") == []
    assert called["n"] == 0


def test_recall_optout_is_noop(monkeypatch):
    _setup_recall(monkeypatch, [{"conversation_id": "c1", "text": "x", "source_type": "account_insight", "ft_score": 0.9}], opted_out=True)
    assert account_recall.recall_account_conv_facts(42, "매출", exclude_conversation_id="cur") == []


def test_recall_vector_only_failclosed_when_no_embedding(monkeypatch):
    _setup_recall(monkeypatch, [{"conversation_id": "c1", "text": "x", "source_type": "account_insight", "ft_score": 0.9}], embed=None)
    # 임베딩 None → trigram fallback 없이 회상 0.
    assert account_recall.recall_account_conv_facts(42, "매출", exclude_conversation_id="cur") == []


def test_recall_source_allowlist_and_g4_and_minsim_topk(monkeypatch):
    rows = [
        {"conversation_id": "c1", "text": "관심 인사이트", "source_type": "account_insight", "ft_score": 0.9},
        {"conversation_id": "c2", "text": "PII Q/A 유출", "source_type": "user_confirm", "ft_score": 0.95},   # G3: 제외
        {"conversation_id": "c1", "text": "스키마 지식", "source_type": "schema_insight", "ft_score": 0.92},   # 비-account_insight 제외
        {"conversation_id": "OTHER", "text": "타대화", "source_type": "account_insight", "ft_score": 0.99},     # G4: 집합 밖 제외
        {"conversation_id": "c2", "text": "낮은 유사도", "source_type": "account_insight", "ft_score": 0.2},    # min_sim 미달 제외
        {"conversation_id": "c2", "text": "두번째 인사이트", "source_type": "account_insight", "ft_score": 0.6},
        {"conversation_id": "c1", "text": "세번째", "source_type": "account_insight", "ft_score": 0.55},        # top_k=2 초과 제외
    ]
    _setup_recall(monkeypatch, rows)
    out = account_recall.recall_account_conv_facts(42, "매출", exclude_conversation_id="cur")
    assert [r["text"] for r in out] == ["관심 인사이트", "두번째 인사이트"]   # allowlist+G4+min_sim+top_k


def test_recall_applies_prose_mask(monkeypatch):
    rows = [{"conversation_id": "c1", "text": "연락처 a@b.com 010-1234-5678", "source_type": "account_insight", "ft_score": 0.9}]
    _setup_recall(monkeypatch, rows)
    out = account_recall.recall_account_conv_facts(42, "q", exclude_conversation_id="cur")
    assert out and "a@b.com" not in out[0]["text"] and "[email]" in out[0]["text"]
    assert "010-1234-5678" not in out[0]["text"]


# ── _account_recall_opted_out ──────────────────────────────────────────────

def test_optout_reads_kv_true(monkeypatch):
    conn = _patch_pg(monkeypatch, [("1",)])
    assert account_recall._account_recall_opted_out(42) is True
    sql = conn.cursor_obj.executed[0]
    assert "agent_runtime.kv" in sql
    assert conn.cursor_obj.params[0] == ("__account__:42", "account_insight_recall_optout")


def test_optout_default_false(monkeypatch):
    _patch_pg(monkeypatch, [])   # 미설정
    assert account_recall._account_recall_opted_out(42) is False
    _patch_pg(monkeypatch, [("0",)])
    assert account_recall._account_recall_opted_out(42) is False


# ── _mask_prose (G3 2차 방어) ───────────────────────────────────────────────

def test_mask_prose_pii_patterns():
    s = _mask_prose("문의 user.name+x@corp.co.kr 전화 010-9999-8888 주민 901201-1234567 ip 10.0.0.5 계정 1234567890")
    assert "@corp.co.kr" not in s and "[email]" in s
    assert "010-9999-8888" not in s and "[phone]" in s
    assert "901201-1234567" not in s and "[id]" in s
    assert "10.0.0.5" not in s and "[ip]" in s
    assert "1234567890" not in s and "[num]" in s


def test_mask_prose_empty():
    assert _mask_prose("") == ""
    assert _mask_prose(None) == ""


# ── run_account_insight_pass 가드 ──────────────────────────────────────────

def test_extract_pass_flag_off_noop(monkeypatch):
    from modules import insight
    monkeypatch.setattr(insight, "AGENT_ACCOUNT_INSIGHT_EXTRACT", False)
    rep = insight.run_account_insight_pass()
    assert rep["candidates"] == 0 and rep["extracted"] == 0


def test_extract_pass_pg_unavailable_noop(monkeypatch):
    from modules import insight
    monkeypatch.setattr(insight, "AGENT_ACCOUNT_INSIGHT_EXTRACT", True)
    monkeypatch.setattr("modules.db._pg_available", lambda: False)
    rep = insight.run_account_insight_pass()
    assert rep["candidates"] == 0 and rep["extracted"] == 0


def test_extract_pass_kv_source_no_summary(monkeypatch):
    """summary 가 비어도(이 배포처럼) kv 신호만으로 account_insight 를 추출·저장한다."""
    from modules import insight
    monkeypatch.setattr(insight, "AGENT_ACCOUNT_INSIGHT_EXTRACT", True)
    monkeypatch.setattr(insight, "AGENT_ACCOUNT_INSIGHT_MIN_SUMMARY_LEN", 5)
    monkeypatch.setattr("modules.db._pg_available", lambda: True)
    # 후보 쿼리: summary 빈 대화 1건.
    monkeypatch.setattr("modules.db._pg_connect", lambda *a, **k: _FakeConn([("conv-x", "")]))
    monkeypatch.setattr(insight, "connect_with_retry", lambda *a, **k: _FakeConn([]))
    monkeypatch.setattr(insight, "_load_kv_prefix_map", lambda *a, **k: {})
    kv = {"origin_request": "주문 테이블 일별 매출 추이 분석", "thread_goal": "매출 도메인 반복 조회", "topic": "sales"}
    monkeypatch.setattr(insight, "load_memory_kv", lambda conn, cid, key: kv.get(key, ""))
    seen = {}
    monkeypatch.setattr(insight, "llm_account_insight",
                        lambda payload: seen.update(payload=payload) or {"insight": "사용자는 매출 도메인 일별 집계에 반복 관심"})
    published = []
    monkeypatch.setattr("modules.kb_write._publish_fact",
                        lambda conn, cid, key, text, weight, **kw: published.append((cid, key, text, kw.get("source_type"))))
    monkeypatch.setattr(insight, "_save_fingerprint", lambda *a, **k: None)

    rep = insight.run_account_insight_pass()
    assert rep["candidates"] == 1 and rep["extracted"] == 1
    # kv 신호가 payload 로 전달됐고, account_insight 로 대화-로컬 저장됐다.
    assert seen["payload"]["origin_request"].startswith("주문")
    assert published == [("conv-x", "account_insight", "사용자는 매출 도메인 일별 집계에 반복 관심", "account_insight")]
