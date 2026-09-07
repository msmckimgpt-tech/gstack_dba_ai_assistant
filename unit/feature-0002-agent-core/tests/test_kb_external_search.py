"""임베딩 없는 검색의 실제 PG 결과와 철거된 제공자의 네트워크 차단을 검증한다."""
import os
import sys

import pytest

from modules import sample_queries as sq
from modules import kb_retrieval
from modules.kb_search import search_schema_knowledge
from scripts import kb_embedding_worker as worker
from shared import config


@pytest.mark.parametrize("model", ["titan-embed", " BGE-M3:latest ", "ollama/bge-m3", ""])
def test_retired_models_never_open_clients_or_database(monkeypatch, model):
    def tripwire(*args, **kwargs):
        pytest.fail("retired embedding provider was invoked")

    monkeypatch.setattr(config, "AGENT_KB_EMBEDDING_MODEL", model)
    from modules import llm
    monkeypatch.setattr(llm, "_get_llm_client", tripwire)
    monkeypatch.setattr(worker, "open_pg_conn", tripwire)
    monkeypatch.setattr(worker, "get_settings", lambda: {"model": model, "batch_size": 2})
    assert kb_retrieval._embed_query_vector("활성 고객 수") is None
    assert worker.run_embedding_pass()["skipped"] == "embedding-model-unset"
    monkeypatch.setattr(sys, "argv", ["worker", "--model", model])
    assert worker.main() == 0
    with pytest.raises(RuntimeError, match="임베딩 모델 미설정"):
        worker.call_openai_embeddings(["KB text"], model, 1, 1)


def test_other_explicit_provider_is_not_remapped():
    assert config.normalize_kb_embedding_model(" future-external-provider ") == "future-external-provider"


@pytest.fixture
def pg():
    dsn = os.getenv("KB_SEARCH_TEST_DSN")
    if not dsn:
        pytest.skip("isolated PostgreSQL: set KB_SEARCH_TEST_DSN")
    import psycopg
    with psycopg.connect(dsn) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("CREATE TEMP TABLE sample_queries (id serial, scope_key text, nl_question text, "
                     "sql text, domain text DEFAULT '', weight int DEFAULT 100, approved boolean, "
                     "status text DEFAULT 'active', embedding vector(2), updated_at timestamptz)")
        conn.execute("CREATE TEMP TABLE texts (text_hash text PRIMARY KEY, text_content text)")
        conn.execute("CREATE TEMP TABLE rag_documents (id serial, conversation_id text, scope_key text, "
                     "fact_key text, source_type text, text_hash text)")
        yield conn
        conn.rollback()


def test_sample_search_without_vector_respects_curation_and_product(pg, monkeypatch):
    for scope, approved, status, sql in [
        ("product.sales", True, "active", "SELECT 101 FROM customers"),
        ("common", True, "active", "SELECT 102 FROM customers"),
        ("product.other", True, "active", "SELECT 901 FROM customers"),
        ("product.sales", False, "active", "SELECT 902 FROM customers"),
        ("product.sales", True, "retired", "SELECT 903 FROM customers"),
        ("product.sales", True, "stale", "SELECT 904 FROM customers"),
    ]:
        pg.execute("INSERT INTO sample_queries(scope_key,nl_question,sql,approved,status) "
                   "VALUES(%s,%s,%s,%s,%s)", (scope, "활성 고객 수", sql, approved, status))
    monkeypatch.setattr(sq, "_embed", lambda *a, **kw: pytest.fail("external grounding embedded"))
    out = sq.load_example_queries_context("활성 고객 수", "product.sales", conn=pg, query_vector=None)
    assert "SELECT 101" in out and "SELECT 102" in out
    assert all(f"SELECT {n}" not in out for n in range(901, 905))
    assert sq.search_samples_text(pg, "zzzzzz", "product.sales") == []
    assert sq.search_samples_text(pg, "", "product.sales") == []


def test_sample_focus_matches_sql_identifier(pg):
    pg.execute("INSERT INTO sample_queries(scope_key,nl_question,sql,approved) "
               "VALUES('product.sales','결제 기록','SELECT status FROM steam_billing_log',true)")
    rows = sq.search_samples_text(pg, "steam_billing_log", "product.sales")
    assert len(rows) == 1 and "steam_billing_log" in rows[0][1]


def test_schema_search_filters_before_ranking_with_literal_database_boundaries(pg):
    allowed = "table_insight:ds:mysql-aaaaaaaaaaaa:db_%A.orders"
    specs = [
        (allowed, "__global__", "common", "schema_insight"),
        ("schema_insight:ds:mysql-aaaaaaaaaaaa:db_%A", "__global__", "common", "insight"),
        ("table_insight:ds:mysql-aaaaaaaaaaaa:db_%AB.orders", "__global__", "common", "schema_insight"),
        ("table_insight:ds:mysql-bbbbbbbbbbbb:db_%A.orders", "__global__", "common", "schema_insight"),
        ("table_insight:ds:mysql-aaaaaaaaaaaa:db_XXA.orders", "__global__", "common", "schema_insight"),
        (allowed, "private-conversation", "common", "schema_insight"),
        (allowed, "__global__", "product.other", "schema_insight"),
        (allowed, "__global__", "common", "account_insight"),
        ("insight:ds:mysql-aaaaaaaaaaaa:db_%A.orders", "__global__", "common", "insight"),
    ]
    for i, (key, conv, scope, source) in enumerate(specs):
        pg.execute("INSERT INTO texts VALUES(%s,%s)", (str(i), f"활성 고객 수 evidence-{i}"))
        pg.execute("INSERT INTO rag_documents(fact_key,conversation_id,scope_key,source_type,text_hash) "
                   "VALUES(%s,%s,%s,%s,%s)", (key, conv, scope, source, str(i)))
    targets = [{"scope_key": "mysql-aaaaaaaaaaaa", "engine": "mysql", "allowed_databases": ["db_%A"]}]
    rows = search_schema_knowledge(pg, "활성 고객 수", targets)
    assert {r["key"] for r in rows} == {specs[0][0], specs[1][0]}
    assert {r["text"] for r in rows} == {"활성 고객 수 evidence-0", "활성 고객 수 evidence-1"}
    assert search_schema_knowledge(pg, "zzzzzz", targets) == []
    assert search_schema_knowledge(pg, "활성 고객 수", []) == []
    assert search_schema_knowledge(pg, "활성 고객 수", [{"scope_key": "mysql-aaaaaaaaaaaa"}]) == []
    assert search_schema_knowledge(pg, "활성 고객 수", targets, limit=1)[0]["score"] >= 0.2
    search_schema_knowledge(pg, "' OR 1=1; DROP TABLE texts; --", targets)
    assert pg.execute("SELECT count(*) FROM texts").fetchone()[0] == len(specs)


def test_external_error_mode_distinguishes_failure_from_no_results(monkeypatch):
    monkeypatch.setattr(sq, "_ro_conn", lambda conn: (None, False))
    assert sq.load_example_queries_context("질문", query_vector=None) == ""
    with pytest.raises(RuntimeError, match="connection unavailable"):
        sq.load_example_queries_context("질문", query_vector=None, raise_on_error=True)


def test_dotted_database_requires_every_possible_owner_to_be_allowed(pg):
    scope = "mysql-aaaaaaaaaaaa"
    for i, suffix in enumerate(["sales.orders", "sales.archive.orders", "sales.archived.orders"]):
        pg.execute("INSERT INTO texts VALUES(%s, 'orders details')", (str(i),))
        pg.execute("INSERT INTO rag_documents(fact_key,conversation_id,scope_key,source_type,text_hash) "
                   "VALUES(%s,'__global__','common','schema_insight',%s)",
                   (f"table_insight:ds:{scope}:{suffix}", str(i)))
    def search(databases, engine="mysql"):
        return search_schema_knowledge(pg, "orders", [{"scope_key": scope, "engine": engine,
                                                        "allowed_databases": databases}])
    assert [r["key"].rsplit(":", 1)[-1] for r in search(["sales"])] == ["sales.orders"]
    assert search(["sales.archive"]) == []  # could be sales DB + archive.orders table
    assert len(search(["sales", "sales.archive"])) == 2
    assert search(["sales", "sales.archive"], "mssql") == []


def test_sample_question_edit_keeps_sql_freshness_without_embedding(pg):
    for status in ("active", "stale", "retired"):
        sid = pg.execute("INSERT INTO sample_queries(scope_key,nl_question,sql,approved,status,embedding) "
                         "VALUES('product.sales','old','SELECT 101 FROM customers',true,%s,'[1,0]') "
                         "RETURNING id", (status,)).fetchone()[0]
        sq.update_sample(pg, sid, "product.sales", nl_question="고객 목록", embedding=None)
        row = pg.execute("SELECT status,embedding FROM sample_queries WHERE id=%s", (sid,)).fetchone()
        assert row == (status, None)
    assert len(sq.search_samples_text(pg, "고객 목록", "product.sales")) == 1


def test_long_document_excerpt_contains_late_match_and_discloses_position(pg):
    from modules.kb_search import load_schema_knowledge_context
    content = "prefix unrelated " * 180 + "steam_billing_log 결제 내역 " * 30
    pg.execute("INSERT INTO texts VALUES('long',%s)", (content,))
    pg.execute("INSERT INTO rag_documents(fact_key,conversation_id,scope_key,source_type,text_hash) "
               "VALUES('table_insight:ds:mysql-aaaaaaaaaaaa:sales.orders','__global__','common',"
               "'schema_insight','long')")
    targets = [{"scope_key": "mysql-aaaaaaaaaaaa", "engine": "mysql", "allowed_databases": ["sales"]}]
    out = load_schema_knowledge_context("steam_billing_log", targets, conn=pg)
    assert "steam_billing_log" in out and "발췌" in out and "focus" in out
