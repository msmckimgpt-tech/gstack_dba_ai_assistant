"""TASK-20260624-metadata-ai-autocomplete — 메타데이터 AI 자동완성 회귀/보안 테스트.

ITEM-11 메타데이터 거버넌스 5 서브뷰(glossary/enums/tables/columns/samples)의 단건 자동완성
(POST /api/admin/metadata/{sub}/suggest)과 골격 일괄 자동완성(POST .../bootstrap/describe)의
web 경계를 DB·LLM 없이 monkeypatch/fake 로 검증한다. LLM 은 _metadata_llm_complete 를 mock 해
실제 모델 호출 없이 결정적으로 검증한다(비용/비결정성 차단). tests/test_metadata_phase2.py 의
fake/RBAC 패턴을 복제한다.

검증 대상:
  R403   서브뷰별 RBAC — 권한 없는 account → 403 (LLM 미호출 = 비용/유출 차단).
  SR403  samples 는 kb.sample.curate 게이트 — kb.ingest.manual 만으론 403.
  U404   알 수 없는 서브뷰 → 404 (RBAC·LLM 진입 전 차단).
  IV400  필수 식별 필드 누락 → 400 (LLM 미호출 = 빈 식별자 날조 방지).
  OK     정상 — target/suggestion 반환(영속 안 함): glossary=definition / samples=nl_question.
  CAP    cap 초과 생성물 절단(저장 경로 cap 과 동일 상한).
  LERR   LLM 오류 → 상태코드 전파.
  BOK    bootstrap/describe — JSON 파싱 → results(테이블/컬럼 대소문자·공백 무시 매칭).
  BR403  bootstrap RBAC.
  BIV    bootstrap 입력검증 — mode/빈 tables → 400.
  PJ     _metadata_parse_json_object 단위 — 코드펜스/전후텍스트/깨진 입력.

`make test`(agent 이미지, --no-deps)에서 DB·LLM 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json

import app
from routers import admin_metadata


# ── Fakes (phase2 복제) ──────────────────────────────────────────────────────────

class _FakeRequest:
    def __init__(self, payload=None, query=None):
        self._payload = payload if payload is not None else {}
        self.query_params = query or {}
        self.headers = {}
        self.client = None
        self.cookies = {}

    async def body(self):
        return json.dumps(self._payload).encode("utf-8") if self._payload else b""

    async def json(self):
        return self._payload


class _BenignCursor:
    def execute(self, sql, params=None):
        return None

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        return None


class _BenignConn:
    def cursor(self, *a, **k):
        return _BenignCursor()

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def _body(resp):
    return json.loads(resp.body)


# ── RBAC/LLM 주입 helper ─────────────────────────────────────────────────────────

def _allow(monkeypatch):
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    # 정상 경로는 rate-limit 통과 가정 — 429 검증은 별도 테스트에서 False 주입.
    monkeypatch.setattr(app, "_search_rate_limit_check", lambda *a, **k: True)


def _admin(monkeypatch):
    """메타데이터 세부 권한(graph-panel-perms task4 B안 분리) + kb.sample.curate 모두 보유(happy path).
    as_account/직접 dict 는 _apply_permission_overrides 함의를 안 타므로, 세부 권한을 명시 부여한다."""
    acct = {"id": 1, "username": "admin",
            "permissions": {"metadata.glossary.manage": True, "metadata.enum.manage": True,
                            "metadata.table.manage": True, "metadata.column.manage": True,
                            "metadata.graph.read": True, "kb.sample.curate": True}}
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    return acct


def _ingest_only(monkeypatch):
    """메타데이터 세부 편집 권한만 — samples(kb.sample.curate)에는 부족."""
    acct = {"id": 5, "username": "kb",
            "permissions": {"metadata.glossary.manage": True, "metadata.enum.manage": True,
                            "metadata.table.manage": True, "metadata.column.manage": True}}
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    return acct


def _nobody(monkeypatch):
    acct = {"id": 9, "username": "op", "permissions": {"console.access": True}}
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    return acct


def _fake_llm(monkeypatch, text="AI 가 생성한 한국어 설명입니다.", meta=None, err=None):
    """_metadata_llm_complete mock. err 지정 시 (None, None, err) → 엔드포인트가 그대로 전파.
    called['n'] 으로 LLM 호출 여부를 검증(RBAC/입력검증이 LLM 전에 차단되는지)."""
    called = {"n": 0, "task": None}

    async def _fake(messages, **kw):
        called["n"] += 1
        called["task"] = kw.get("task")
        if err is not None:
            return None, None, err
        return text, (meta or {"model": "fake", "truncated": False}), None

    monkeypatch.setattr(app, "_metadata_llm_complete", _fake)
    return called


# ── R403/SR403: 서브뷰별 RBAC (LLM 미호출) ─────────────────────────────────────────

def test_suggest_requires_permission(monkeypatch):
    _allow(monkeypatch)
    _nobody(monkeypatch)
    called = _fake_llm(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_metadata_suggest("glossary", _FakeRequest({"term": "이탈률"})))
    assert resp.status_code == 403
    assert called["n"] == 0


def test_samples_requires_sample_curate_perm(monkeypatch):
    # kb.ingest.manual 은 있어도 samples 는 kb.sample.curate 게이트 → 403.
    _allow(monkeypatch)
    _ingest_only(monkeypatch)
    called = _fake_llm(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_metadata_suggest("samples", _FakeRequest({"sql": "SELECT 1"})))
    assert resp.status_code == 403
    assert called["n"] == 0


# ── U404: 알 수 없는 서브뷰 ────────────────────────────────────────────────────────

def test_unknown_sub_404_before_llm(monkeypatch):
    _allow(monkeypatch)
    _nobody(monkeypatch)
    called = _fake_llm(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_metadata_suggest("bogus", _FakeRequest({"x": 1})))
    assert resp.status_code == 404
    assert called["n"] == 0


# ── IV400: 필수 식별 필드 누락 (LLM 미호출) ────────────────────────────────────────

def test_missing_required_field_400_no_llm(monkeypatch):
    _allow(monkeypatch)
    _admin(monkeypatch)
    called = _fake_llm(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_metadata_suggest("glossary", _FakeRequest({})))  # term 누락
    assert resp.status_code == 400
    assert called["n"] == 0


# ── OK: 정상 단건 자동완성(영속 안 함) ─────────────────────────────────────────────

def test_glossary_suggest_returns_definition(monkeypatch):
    _allow(monkeypatch)
    _admin(monkeypatch)
    _fake_llm(monkeypatch, text="가입 후 일정 기간 내 활동이 없는 사용자 비율.")
    resp = asyncio.run(admin_metadata.admin_metadata_suggest("glossary", _FakeRequest({"term": "이탈률"})))
    assert resp.status_code == 200
    b = _body(resp)
    assert b["target"] == "definition"
    assert b["suggestion"].startswith("가입 후")
    assert b["meta"]["grounded"] is False  # glossary 는 스키마 grounding 없음


def test_samples_suggest_returns_nl_question(monkeypatch):
    _allow(monkeypatch)
    _admin(monkeypatch)
    _fake_llm(monkeypatch, text="최근 30일 신규 가입자는 몇 명인가요?")
    resp = asyncio.run(admin_metadata.admin_metadata_suggest(
        "samples", _FakeRequest({"sql": "SELECT count(*) FROM users"})))
    assert resp.status_code == 200
    b = _body(resp)
    assert b["target"] == "nl_question"
    assert b["suggestion"].endswith("?")


# ── CAP: cap 초과 절단 ─────────────────────────────────────────────────────────────

def test_suggestion_capped(monkeypatch):
    _allow(monkeypatch)
    _admin(monkeypatch)
    cap = app._METADATA_FIELD_CAPS["definition"]
    _fake_llm(monkeypatch, text="가" * (cap + 200))
    resp = asyncio.run(admin_metadata.admin_metadata_suggest("glossary", _FakeRequest({"term": "x"})))
    assert resp.status_code == 200
    assert len(_body(resp)["suggestion"]) <= cap


# ── LERR: LLM 오류 전파 ────────────────────────────────────────────────────────────

def test_llm_error_propagates_status(monkeypatch):
    _allow(monkeypatch)
    _admin(monkeypatch)
    _fake_llm(monkeypatch, err=app._json_error("LLM 생성 실패", 502))
    resp = asyncio.run(admin_metadata.admin_metadata_suggest("glossary", _FakeRequest({"term": "x"})))
    assert resp.status_code == 502


# ── 비용 차단: sql 입력 cap + rate-limit (§18.8 verification panel 적발 수정의 회귀 가드) ──

def test_samples_sql_input_capped_400(monkeypatch):
    # samples 의 sql 본문은 프롬프트에 raw 삽입되므로 cap 초과는 LLM 도달 전 400(비용 폭주 차단).
    _allow(monkeypatch)
    _admin(monkeypatch)
    called = _fake_llm(monkeypatch)
    cap = app._METADATA_FIELD_CAPS["sql"]
    resp = asyncio.run(admin_metadata.admin_metadata_suggest("samples", _FakeRequest({"sql": "S" * (cap + 1)})))
    assert resp.status_code == 400
    assert called["n"] == 0


def test_suggest_rate_limited_429_before_llm(monkeypatch):
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    _admin(monkeypatch)
    called = _fake_llm(monkeypatch)
    monkeypatch.setattr(app, "_search_rate_limit_check", lambda *a, **k: False)
    resp = asyncio.run(admin_metadata.admin_metadata_suggest("glossary", _FakeRequest({"term": "x"})))
    assert resp.status_code == 429
    assert called["n"] == 0  # rate-limit 이 LLM dispatch 앞에서 차단


def test_bootstrap_rate_limited_429(monkeypatch):
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    acct = _admin(monkeypatch)
    called = _fake_llm(monkeypatch)
    monkeypatch.setattr(app, "_search_rate_limit_check", lambda *a, **k: False)
    resp = asyncio.run(admin_metadata.admin_metadata_bootstrap_describe(
        _FakeRequest({"mode": "tables", "tables": [{"table_name": "users"}]}), account=acct))
    assert resp.status_code == 429
    assert called["n"] == 0


# ── BR403/BIV: bootstrap RBAC + 입력검증 ──────────────────────────────────────────

def test_bootstrap_requires_permission(monkeypatch, client, as_account):
    as_account(perms={"console.access": True})  # kb.ingest.manual 없음 → require_permission 403
    called = _fake_llm(monkeypatch)
    resp = client.post("/api/admin/metadata/bootstrap/describe",
                       json={"mode": "tables", "tables": [{"table_name": "users"}]})
    assert resp.status_code == 403
    assert called["n"] == 0


def test_bootstrap_invalid_mode_400(monkeypatch):
    _allow(monkeypatch)
    acct = _admin(monkeypatch)
    _fake_llm(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_metadata_bootstrap_describe(
        _FakeRequest({"mode": "rows", "tables": [{"table_name": "users"}]}), account=acct))
    assert resp.status_code == 400


def test_bootstrap_empty_tables_400(monkeypatch):
    _allow(monkeypatch)
    acct = _admin(monkeypatch)
    _fake_llm(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_metadata_bootstrap_describe(
        _FakeRequest({"mode": "tables", "tables": []}), account=acct))
    assert resp.status_code == 400


# ── BOK: bootstrap/describe 정형(테이블/컬럼) ─────────────────────────────────────

def test_bootstrap_tables_shapes_results(monkeypatch):
    _allow(monkeypatch)
    acct = _admin(monkeypatch)
    # LLM 이 {table_name: description} JSON(코드펜스 포함)을 반환 → results 로 정형.
    _fake_llm(monkeypatch, text='```json\n{"users": "사용자 계정 정보", "orders": "주문 내역"}\n```')
    resp = asyncio.run(admin_metadata.admin_metadata_bootstrap_describe(_FakeRequest({
        "mode": "tables",
        "tables": [{"schema_name": "public", "table_name": "users"},
                   {"schema_name": "public", "table_name": "orders"}],
    }), account=acct))
    assert resp.status_code == 200
    b = _body(resp)
    assert b["mode"] == "tables"
    by = {r["table_name"]: r["description"] for r in b["results"]}
    assert by["users"] == "사용자 계정 정보"
    assert by["orders"] == "주문 내역"


def test_bootstrap_columns_shapes_results(monkeypatch):
    _allow(monkeypatch)
    acct = _admin(monkeypatch)
    _fake_llm(monkeypatch, text='{"users": {"id": "기본키", "email": "이메일 주소"}}')
    resp = asyncio.run(admin_metadata.admin_metadata_bootstrap_describe(_FakeRequest({
        "mode": "columns",
        "tables": [{"schema_name": "public", "table_name": "users",
                    "columns": [{"column_name": "id", "data_type": "int"},
                                {"column_name": "email", "data_type": "varchar"}]}],
    }), account=acct))
    assert resp.status_code == 200
    got = {(r["table_name"], r["column_name"]): r["description"] for r in _body(resp)["results"]}
    assert got[("users", "id")] == "기본키"
    assert got[("users", "email")] == "이메일 주소"


def test_bootstrap_unparseable_llm_502(monkeypatch):
    _allow(monkeypatch)
    acct = _admin(monkeypatch)
    _fake_llm(monkeypatch, text="죄송하지만 JSON 을 만들 수 없습니다.")  # { } 없음 → parse None
    resp = asyncio.run(admin_metadata.admin_metadata_bootstrap_describe(
        _FakeRequest({"mode": "tables", "tables": [{"table_name": "users"}]}), account=acct))
    assert resp.status_code == 502


# ── PJ: _metadata_parse_json_object 단위 ──────────────────────────────────────────

def test_parse_json_object_variants():
    f = app._metadata_parse_json_object
    assert f('{"a": 1}') == {"a": 1}
    assert f('```json\n{"a": 1}\n```') == {"a": 1}
    assert f('```\n{"a": 1}\n```') == {"a": 1}
    assert f('설명: {"a": 1} 끝입니다') == {"a": 1}   # 전후 텍스트 허용
    assert f("[1, 2, 3]") is None                      # dict 아님
    assert f("not json at all") is None
    assert f("") is None
    assert f(None) is None
