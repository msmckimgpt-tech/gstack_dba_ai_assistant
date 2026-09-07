"""KB 근거가 claim/focus로 도달하고 현재 권한·출력 원장을 지키는지 확인한다."""
import asyncio
import json

import pytest

from routers import ai_tools as api


class Request:
    headers = {}
    async def json(self):
        return {"task_id": "t1", "focus": "orders"}


class Conn:
    rowcount = 1
    def cursor(self):
        return self
    def execute(self, *args):
        pass
    def commit(self):
        pass
    def close(self):
        pass
    def fetchone(self):
        return ("고객 주문", "c1", 7, None, None, None, "pinned", "", "", "",
                "chat", None, None)


@pytest.fixture
def wired(monkeypatch):
    state = {"calls": [], "ledger": [], "released": []}
    monkeypatch.setattr(api, "_stale_runner_yield_to", lambda *a: None)
    monkeypatch.setattr(api, "_runner_job_grants", lambda *a: [])
    monkeypatch.setattr(api, "_dispatch_scope_sql", lambda *a: ("AccountId=%s", [1]))
    monkeypatch.setattr(api.app, "_account_can_access_conversation", lambda *a: True)
    monkeypatch.setattr(api._authz, "resolve_product", lambda *a: {"id": 7})
    monkeypatch.setattr(api._authz, "datasource_scope_keys", lambda *a: ["mysql-aaa"])
    monkeypatch.setattr(api, "_load_task", lambda *a, **kw: {
        "task_id": "t1", "product_id": 7, "conversation_id": "c1", "question": "고객 주문"})
    monkeypatch.setattr(api, "_kb_datasource_targets", lambda *a: [
        {"scope_key": "mysql-aaa", "allowed_databases": ["sales"]}])
    monkeypatch.setattr(api, "_bridge_product_scope_key", lambda *a: "product.sales")
    def grounding(question, product_scope, ds_scopes, notes, **kw):
        state["calls"].append((question, product_scope, kw["datasource_targets"]))
        notes.append("샘플쿼리 로드 실패: RuntimeError")
        return ["## KB SCHEMA SEARCH\norders: 승인된 주문 테이블"]
    monkeypatch.setattr(api, "_kb_grounding_sections", grounding)
    monkeypatch.setattr(api, "_recent_conversation_context", lambda *a, **kw: "")
    monkeypatch.setattr(api, "_task_attachment_list", lambda *a: [])
    monkeypatch.setattr(api, "_bridge_system_prompt", lambda *a, **kw: "운영자 지침")
    monkeypatch.setattr(api, "_bridge_product_scope", lambda *a: {"product_id": 7})
    for name in ("_mark_bridge_working", "_record_bridge_activity", "_safe_record",
                 "_renew_claim_lease", "_record_bridge_step"):
        monkeypatch.setattr(api, name, lambda *a, **kw: None)
    monkeypatch.setattr(api._funnel, "record_step", lambda *a, **kw: None)
    monkeypatch.setattr(api._funnel, "account_path_kind", lambda *a: "test")
    monkeypatch.setattr(api, "_pg", lambda: None)
    monkeypatch.setattr(api._ledger, "record", lambda *a, **kw: state["ledger"].append(kw))
    monkeypatch.setattr(api, "_release_claim", lambda *a: state["released"].append(a))
    from modules import cluster_context
    monkeypatch.setattr(cluster_context, "enabled", lambda: False)
    return state


def call(handler):
    return asyncio.run(handler(Request(), ctx={"account": {"id": 1, "username": "alice"}}, conn=Conn()))


def test_claim_and_focus_deliver_evidence_and_partial_failure(wired):
    response = call(api.claim_request)
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert "orders: 승인된 주문 테이블" in payload["kb_context"]
    assert "샘플쿼리 로드 실패" in payload["kb_context"]
    assert "alice" in payload["kb_context"] and "t1" in payload["kb_context"]
    assert wired["ledger"][-1]["bytes_out"] == len(response.body)
    assert wired["calls"][-1][0] == "고객 주문"
    response = call(api.get_task_context)
    assert response.status_code == 200
    context = json.loads(response.body)
    assert "orders: 승인된 주문 테이블" in context["context"]
    assert "샘플쿼리 로드 실패" in context["context"]
    assert wired["calls"][-1][0] == "orders"
    assert wired["ledger"][-1]["bytes_out"] == len(response.body)


@pytest.mark.parametrize("handler", [api.claim_request, api.get_task_context])
@pytest.mark.parametrize("revoked", ["conversation", "product"])
def test_revoked_access_blocks_before_kb_reads(monkeypatch, wired, handler, revoked):
    if revoked == "conversation":
        monkeypatch.setattr(api.app, "_account_can_access_conversation", lambda *a: False)
    else:
        def deny(*a):
            raise api._authz.ScopeDenied("제품 권한 회수", code="product_forbidden")
        monkeypatch.setattr(api._authz, "resolve_product", deny)
    assert call(handler).status_code == 403
    assert not wired["calls"]
    assert bool(wired["released"]) == (handler is api.claim_request)


def test_claim_ledger_failure_releases_claim(monkeypatch, wired):
    def fail(*a, **kw):
        raise api._ledger.LedgerUnavailable("ledger unavailable")
    monkeypatch.setattr(api._ledger, "record", fail)
    assert call(api.claim_request).status_code == 503
    assert len(wired["released"]) == 1


def test_unresolved_search_targets_are_not_replaced_with_global_scope(monkeypatch):
    monkeypatch.setattr(api._authz, "allowed_datasource_labels", lambda *a: ["ds1"])
    from shared import datasources
    monkeypatch.setattr(datasources, "resolve", lambda *a: {"scope_key": "mysql-aaa"})
    def fail(*a, **kw):
        assert kw["strict"] is True
        raise RuntimeError("DB unavailable")
    monkeypatch.setattr(api.app, "_product_allowed_schemas_for_datasource", fail)
    notes = []
    assert api._kb_datasource_targets(Conn(), 7, notes) == []
    assert "범위 해소 실패" in notes[0]


def test_no_product_does_not_resolve_a_default(monkeypatch):
    monkeypatch.setattr(api._authz, "resolve_product", lambda *a: pytest.fail("default product selected"))
    assert api._kb_product_access_denied(None, {}, None) is None


def test_real_loaders_report_sql_failure_while_other_layers_survive(monkeypatch):
    from modules import kb_glossary, kb_metadata, relationships
    from shared import db
    from contextlib import nullcontext
    class Broken:
        def transaction(self): return nullcontext()
        def cursor(self): return self
        def execute(self, *a, **kw): raise RuntimeError("SQL failed")
        def close(self): pass
    monkeypatch.setattr(db, "_pg_available", lambda: True)
    monkeypatch.setattr(db, "_pg_connect_ro", lambda: Broken())
    monkeypatch.setattr(db, "_pg_conn_pair_ro", lambda conn: (conn, False))
    monkeypatch.setattr(kb_glossary, "load_glossary_enum_context", lambda *a, **kw: "customer=고객")
    monkeypatch.setattr(kb_metadata, "load_table_column_descriptions", lambda *a, **kw: "")
    monkeypatch.setattr(relationships, "load_relationship_context", lambda *a, **kw: "")
    notes = []
    out = api._kb_grounding_sections("customer", "product.sales", [], notes, datasource_targets=[
        {"scope_key": "mysql-aaaaaaaaaaaa", "engine": "mysql", "allowed_databases": ["sales"]}])
    assert "customer=고객" in "".join(out)
    assert any("샘플쿼리 로드 실패" in note for note in notes)
    assert any("KB 문서 검색 실패" in note for note in notes)
