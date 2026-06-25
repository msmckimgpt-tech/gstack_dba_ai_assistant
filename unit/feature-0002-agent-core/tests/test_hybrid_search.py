"""ITEM-05 (하이브리드 검색 — 벡터+키워드 score fusion) 단위 테스트.

라이브 DB·임베딩 불요 — `_embed_query_vector` 와 PgKbBackend 검색을 monkeypatch 로
대체하고 FakeConn 으로 PG 연결을 모킹한다. 검증 대상:

- fusion 점수 결합: score = α·vec_sim + β·trigram_sim (AGENT_KB_HYBRID_ALPHA/BETA)
- score 내림차순 정렬
- 한쪽만 매칭(벡터 only / trigram only) → 누락 쪽 sim=0 으로 가중
- qvec None → trigram-only(기존 폴백)
- gate OFF(AGENT_KB_HYBRID_ENABLED=False) → 기존 2-tier 경로(vector-OR-trigram)
- 벡터·trigram 둘 다 결과 0 → trigram-only fall-through (None 반환 후 trigram)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _knowledge():
    from modules import knowledge  # type: ignore
    return knowledge


class _FakeConn:
    closed = False

    def close(self):
        _FakeConn.closed = True


def _row(conv, fact, content, weight, score):
    """search_rag_documents[_vector] 의 8-tuple shape: (…, ft_score)."""
    return (conv, fact, content, weight, "repair", None, "2026-06-23", score)


@pytest.fixture
def pg_mock(monkeypatch):
    """PG available + RO connect 를 FakeConn 으로. backend 검색은 테스트별 주입."""
    _FakeConn.closed = False
    from modules import db as _db  # type: ignore  # ensure modules.db loaded
    monkeypatch.setattr(_db, "_pg_available", lambda: True, raising=True)
    monkeypatch.setattr(_db, "_pg_connect_ro", lambda *a, **k: _FakeConn(), raising=True)
    return monkeypatch


def _install_backend(monkeypatch, *, vec_rows, trg_rows, vec_spy=None, trg_spy=None):
    from modules import kb_backend  # type: ignore

    def _vector(self, conn, *, conversation_ids, query_vector, scope_keys=None, limit=200):
        if vec_spy is not None:
            vec_spy.append({"conv": conversation_ids, "qvec": query_vector, "scope": scope_keys})
        return list(vec_rows)

    def _trigram(self, conn, *, conversation_ids, query_text, scope_keys=None):
        if trg_spy is not None:
            trg_spy.append({"conv": conversation_ids, "qtext": query_text, "scope": scope_keys})
        return list(trg_rows)

    monkeypatch.setattr(kb_backend.PgKbBackend, "search_rag_documents_vector", _vector)
    monkeypatch.setattr(kb_backend.PgKbBackend, "search_rag_documents", _trigram)


# ─────────────────────────────────────────────────────────────────────────────
# fusion 점수 결합 + 정렬
# ─────────────────────────────────────────────────────────────────────────────


def test_fusion_combines_and_ranks(pg_mock):
    """양쪽 매칭 docs 의 score = α·vec + β·trigram, 내림차순 정렬."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", True, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ALPHA", 0.6, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_BETA", 0.4, raising=True)
    # raw 가중합 수식 검증 — 정규화 OFF 로 고정해 결정적으로 본다.
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_NORMALIZE", False, raising=True)

    # docA: vec=0.9, trg=0.1 → 0.6*0.9 + 0.4*0.1 = 0.58
    # docB: vec=0.2, trg=0.9 → 0.6*0.2 + 0.4*0.9 = 0.48
    vec_rows = [_row("c1", "docA", "활성 고객 정의", 5, 0.9), _row("c1", "docB", "주문 상태 코드", 3, 0.2)]
    trg_rows = [_row("c1", "docA", "활성 고객 정의", 5, 0.1), _row("c1", "docB", "주문 상태 코드", 3, 0.9)]
    _install_backend(monkeypatch, vec_rows=vec_rows, trg_rows=trg_rows)

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "활성 고객", ["common", ""])
    assert out is not None
    keys = [d["key"] for d in out]
    assert keys == ["docA", "docB"], f"fusion 정렬 오류: {keys}"
    by_key = {d["key"]: d["ft_score"] for d in out}
    assert by_key["docA"] == pytest.approx(0.58, abs=1e-6)
    assert by_key["docB"] == pytest.approx(0.48, abs=1e-6)


def test_fusion_union_merge_key_is_conv_fact(pg_mock):
    """병합 키 = (conversation_id, fact_key) — 같은 키는 한 row 로 union."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", True, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_NORMALIZE", False, raising=True)

    vec_rows = [_row("c1", "docX", "동일 문서", 5, 0.8)]
    trg_rows = [_row("c1", "docX", "동일 문서", 5, 0.5)]
    _install_backend(monkeypatch, vec_rows=vec_rows, trg_rows=trg_rows)

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    assert len(out) == 1, "같은 (conv,fact) 가 2 row 로 분리됨 — union 병합 실패"
    # 0.6*0.8 + 0.4*0.5 = 0.68
    assert out[0]["ft_score"] == pytest.approx(0.68, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# 한쪽만 매칭
# ─────────────────────────────────────────────────────────────────────────────


def test_fusion_vector_only_match(pg_mock):
    """trigram 미매칭 doc — trg sim=0, score = α·vec 만."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", True, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_NORMALIZE", False, raising=True)

    vec_rows = [_row("c1", "vonly", "벡터만 매칭", 4, 0.7)]
    trg_rows = []  # trigram 결과 없음
    _install_backend(monkeypatch, vec_rows=vec_rows, trg_rows=trg_rows)

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    assert len(out) == 1
    assert out[0]["key"] == "vonly"
    assert out[0]["ft_score"] == pytest.approx(0.6 * 0.7, abs=1e-6)


def test_fusion_trigram_only_match(pg_mock):
    """벡터 미매칭 doc — vec sim=0, score = β·trigram 만."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", True, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_NORMALIZE", False, raising=True)

    vec_rows = []
    trg_rows = [_row("c1", "tonly", "키워드만 매칭", 2, 0.9)]
    _install_backend(monkeypatch, vec_rows=vec_rows, trg_rows=trg_rows)

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    assert len(out) == 1
    assert out[0]["key"] == "tonly"
    assert out[0]["ft_score"] == pytest.approx(0.4 * 0.9, abs=1e-6)


def test_fusion_normalize_rescales_signals(pg_mock):
    """정규화 ON — 척도가 다른 두 신호(vec 高대역, trg 低대역)를 query-단위 min-max 로
    [0,1] 재척도해 trigram 이 랭킹에 실제 기여하게 한다.

    raw 가중합으로는 vec 항이 지배(아래 docHi 가 항상 위)지만, 정규화하면 trigram 신호의
    상대 차이가 살아나 키워드 강매칭 doc(docLo)이 역전될 수 있음을 검증.
    - docHi: vec=0.80, trg=0.02  / docLo: vec=0.78, trg=0.20  (trg 는 좁은 低대역)
    - raw:       Hi=0.6*0.80+0.4*0.02=0.488,  Lo=0.6*0.78+0.4*0.20=0.548 → Lo 가 이미 높음
      → 이 fixture 만으로는 raw 도 Lo 우위라, 정규화의 '재척도' 자체(스팬 확장)를 직접 검증한다.
    """
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", True, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ALPHA", 0.5, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_BETA", 0.5, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_NORMALIZE", True, raising=True)

    # 두 doc, 두 신호. vec span=[0.78,0.80], trg span=[0.02,0.20].
    vec_rows = [_row("c1", "docHi", "벡터 우위", 5, 0.80), _row("c1", "docLo", "키워드 우위", 5, 0.78)]
    trg_rows = [_row("c1", "docHi", "벡터 우위", 5, 0.02), _row("c1", "docLo", "키워드 우위", 5, 0.20)]
    _install_backend(monkeypatch, vec_rows=vec_rows, trg_rows=trg_rows)

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    by_key = {d["key"]: d["ft_score"] for d in out}
    # 정규화 후: docHi vec_n=1.0 trg_n=0.0 → 0.5*1+0.5*0=0.5; docLo vec_n=0.0 trg_n=1.0 → 0.5.
    # 동점이라 weight·updated_at tiebreak. 핵심: 정규화로 trg 신호가 0~1 로 펼쳐져 vec 와 동급
    # 영향력을 가진다(raw 라면 trg 0.02~0.20 이 거의 무의미). 두 score 가 정규화로 같아짐을 검증.
    assert by_key["docHi"] == pytest.approx(0.5, abs=1e-6)
    assert by_key["docLo"] == pytest.approx(0.5, abs=1e-6)


def test_fusion_normalize_off_vec_dominates(pg_mock):
    """정규화 OFF(raw) — 같은 fixture 로 trg 低대역이 무력화돼 vec 가 지배함을 대조 검증."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", True, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ALPHA", 0.5, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_BETA", 0.5, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_NORMALIZE", False, raising=True)

    vec_rows = [_row("c1", "docHi", "벡터 우위", 5, 0.80), _row("c1", "docLo", "키워드 우위", 5, 0.78)]
    trg_rows = [_row("c1", "docHi", "벡터 우위", 5, 0.02), _row("c1", "docLo", "키워드 우위", 5, 0.20)]
    _install_backend(monkeypatch, vec_rows=vec_rows, trg_rows=trg_rows)

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    by_key = {d["key"]: d["ft_score"] for d in out}
    # raw + trigram floor(0.05, REV MINOR-1): docHi trg 0.02 < floor → 0 → 0.5*0.80+0.5*0=0.40.
    # docLo trg 0.20 ≥ floor → 유지 → 0.5*0.78+0.5*0.20=0.49. (floor 이전 docHi=0.41 이었음)
    assert by_key["docHi"] == pytest.approx(0.40, abs=1e-6)
    assert by_key["docLo"] == pytest.approx(0.49, abs=1e-6)


def test_fusion_same_factkey_different_content_not_merged(pg_mock):
    """REV MAJOR: 같은 (conv,fact_key) 라도 content 다르면 별 엔트리(스키마 unique 는
    content_hash 포함). 병합키에 content 미포함 시 두 문서 신호가 한 엔트리로 섞임."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", True, raising=True)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_NORMALIZE", False, raising=True)
    # 같은 (c1, dup) 인데 content 가 다른 두 행(스키마상 정상 공존).
    vec_rows = [_row("c1", "dup", "내용 A", 5, 0.80), _row("c1", "dup", "내용 B", 5, 0.60)]
    _install_backend(monkeypatch, vec_rows=vec_rows, trg_rows=[])
    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    # content 가 키에 포함 → 2 엔트리 보존(병합 안 됨). (conv,fact)만 키였다면 1개로 뭉개짐.
    assert len(out) == 2
    # 두 행이 별 엔트리이므로 vec sim(0.80/0.60) 차이가 ft_score 에 각각 보존(뭉개지면 1개·max만).
    scores = sorted(d["ft_score"] for d in out)
    assert len(scores) == 2 and scores[0] != scores[1]


def test_fusion_both_empty_falls_through_to_trigram(pg_mock):
    """벡터·trigram 둘 다 결과 0 → fusion None → trigram-only fall-through.

    fusion 안의 두 검색이 [] 라도, fall-through 의 마지막 trigram 호출은 같은 mock
    이라 여전히 []. 핵심은 예외 없이 [] 반환(폴백 보존)."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", True, raising=True)
    _install_backend(monkeypatch, vec_rows=[], trg_rows=[])

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    assert out == []


# ─────────────────────────────────────────────────────────────────────────────
# 폴백: qvec None → trigram-only (기존 경로)
# ─────────────────────────────────────────────────────────────────────────────


def test_qvec_none_uses_trigram_only(pg_mock):
    """임베딩 실패/미설정(qvec None) → 벡터 검색 호출 없이 trigram-only."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: None)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", True, raising=True)

    vec_spy: list = []
    trg_spy: list = []
    trg_rows = [_row("c1", "doc", "트라이그램 결과", 1, 0.3)]
    _install_backend(monkeypatch, vec_rows=[], trg_rows=trg_rows, vec_spy=vec_spy, trg_spy=trg_spy)

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    assert vec_spy == [], "qvec None 인데 벡터 검색이 호출됨"
    assert len(trg_spy) == 1, "trigram 검색이 호출되지 않음"
    assert len(out) == 1 and out[0]["key"] == "doc"
    # trigram-only 경로의 ft_score 는 raw trigram similarity (가중 미적용).
    assert out[0]["ft_score"] == pytest.approx(0.3, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# gate OFF → 기존 2-tier(vector-OR-trigram fallback)
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_off_uses_legacy_2tier_vector_first(pg_mock):
    """AGENT_KB_HYBRID_ENABLED=False + 벡터 결과 있음 → 벡터 결과 그대로(2-tier),
    trigram 미호출 + fusion 미수행."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", False, raising=True)

    vec_spy: list = []
    trg_spy: list = []
    vec_rows = [_row("c1", "vdoc", "벡터 결과", 5, 0.95)]
    trg_rows = [_row("c1", "tdoc", "트라이그램 결과", 3, 0.5)]
    _install_backend(monkeypatch, vec_rows=vec_rows, trg_rows=trg_rows, vec_spy=vec_spy, trg_spy=trg_spy)

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    assert len(vec_spy) == 1, "2-tier 인데 벡터 검색 미호출"
    assert trg_spy == [], "2-tier vector-first 인데 trigram 이 호출됨 (gate OFF 회귀)"
    assert len(out) == 1 and out[0]["key"] == "vdoc"
    # 2-tier 벡터 경로는 raw cosine 유사도 보존(가중 미적용).
    assert out[0]["ft_score"] == pytest.approx(0.95, abs=1e-6)


def test_gate_off_vector_empty_falls_back_to_trigram(pg_mock):
    """gate OFF + 벡터 결과 0 → 기존대로 trigram fallback."""
    knowledge = _knowledge()
    monkeypatch = pg_mock
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: [0.1] * 1024)
    monkeypatch.setattr(sys.modules["shared.config"], "AGENT_KB_HYBRID_ENABLED", False, raising=True)

    trg_rows = [_row("c1", "tdoc", "트라이그램 결과", 3, 0.5)]
    _install_backend(monkeypatch, vec_rows=[], trg_rows=trg_rows)

    out = knowledge._load_rag_documents_for_request_pg(["c1"], "쿼리", ["common", ""])
    assert len(out) == 1 and out[0]["key"] == "tdoc"
