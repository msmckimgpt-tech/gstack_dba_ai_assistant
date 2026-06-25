"""TASK-20260625-role-account-prompt-autogen — 프로필 '제품별 개인 프롬프트' 자동작성 회귀 테스트.

작업 화면 > 프로필 > 프롬프트 > [각 제품] 의 '자동 작성'. account scope(`scope='account'`)이며
self-service — 본인 계정·본인 대화 패턴만 사용한다. 컨텍스트는 사용자의 역할 성격 + 선택 제품의
용도 + 본인 대화 패턴이다. 개인 프롬프트는 제품/역할 프롬프트 위에 얹히는 개인 선호 레이어이므로
제품 스키마 세부를 중복 서술하지 않는다.

검증:
  T1  _assemble_account_prompt_llm_request(product 지정): ctx.meta_base(product_scoped=True) +
      meta-prompt 에 역할·제품명·'개인 프롬프트' 포함.
  T2  _assemble_account_prompt_llm_request(product 무관): product_scoped=False + '제품 무관' 문구.
  T3  _collect_account_prompt_context: 제품 접근권 없음 → 403 (코어 미위임).
  T4  _collect_account_prompt_context: 접근권 있음 → 코어 위임(account_id/role_id/product_id 정확 전달).

`make test`(agent 이미지, --no-deps)에서 DB 없이 fake/monkeypatch 로 실행된다.
"""
from __future__ import annotations

import asyncio

import app


class _FakeLLMClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": None})()


class _FakeCursor:
    """account assembly 의 인라인 SQL(WebProducts 단건 조회)만 해석하는 fake."""

    def __init__(self, product_row):
        self._product_row = product_row
        self._row = None

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "FROM WebProducts WHERE Id" in s:
            self._row = self._product_row
        else:
            self._row = None

    def fetchone(self):
        return self._row

    def close(self):
        return None


class _FakeConn:
    def __init__(self, product_row):
        self._product_row = product_row

    def cursor(self, *a, **k):
        return _FakeCursor(self._product_row)

    def close(self):
        return None


def _patch_llm(monkeypatch):
    monkeypatch.setattr(app, "_resolve_session_default_model", lambda: "test-model")
    monkeypatch.setattr(app, "max_tokens_for_model", lambda model, kind: 1000)
    monkeypatch.setattr(app, "model_supports_temperature", lambda model: True)
    monkeypatch.setattr("modules.llm._get_llm_client", lambda model=None: _FakeLLMClient())


# ── T1/T2 _assemble_account_prompt_llm_request ──────────────────────────────────

def test_assemble_account_prompt_product_scoped(monkeypatch):
    _patch_llm(monkeypatch)
    monkeypatch.setattr(app, "_connect_memory", lambda: _FakeConn(("KR", "한국 게임", "한국 서비스 DB")))
    monkeypatch.setattr(
        app, "_load_role_by_id",
        lambda conn, rid: {
            "id": rid, "key": "sales", "name": "사업팀", "description": "사업팀",
            "permission_codes": ["conversation.ask"],
        },
    )
    monkeypatch.setattr(app, "_collect_conversation_signals_pg", lambda **kw: (["매출 추이"], []))
    err, ctx = app._assemble_account_prompt_llm_request(7, 3, 5)
    assert err is None and ctx is not None
    mb = ctx["meta_base"]
    assert mb["product_scoped"] is True
    assert mb["topic_count"] == 1
    content = ctx["create_kwargs"]["messages"][0]["content"]
    assert "개인 프롬프트" in content
    assert "사업팀" in content
    assert "한국 게임" in content
    assert "매출 추이" in content


def test_assemble_account_prompt_no_product(monkeypatch):
    _patch_llm(monkeypatch)
    monkeypatch.setattr(app, "_connect_memory", lambda: _FakeConn(None))
    monkeypatch.setattr(
        app, "_load_role_by_id",
        lambda conn, rid: {
            "id": rid, "key": "operator", "name": "운영", "description": "",
            "permission_codes": ["conversation.ask"],
        },
    )
    monkeypatch.setattr(app, "_collect_conversation_signals_pg", lambda **kw: ([], []))
    err, ctx = app._assemble_account_prompt_llm_request(7, 2, None)
    assert err is None and ctx is not None
    assert ctx["meta_base"]["product_scoped"] is False
    assert ctx["meta_base"]["grounded"] is False
    content = ctx["create_kwargs"]["messages"][0]["content"]
    assert "제품 무관" in content


# ── T3/T4 _collect_account_prompt_context auth gate ─────────────────────────────

def test_collect_account_prompt_context_denied(monkeypatch):
    monkeypatch.setattr(app, "_connect_memory", lambda: _FakeConn(None))
    monkeypatch.setattr(app, "_require_account", lambda request, conn: ({"id": 7, "role_id": 3}, None))
    monkeypatch.setattr(app, "_account_has_product_access", lambda acc, pid, conn=None: False)
    called = {"assemble": False}

    def _no_assemble(a, r, p):
        called["assemble"] = True
        return None, {}

    monkeypatch.setattr(app, "_assemble_account_prompt_llm_request", _no_assemble)
    err, ctx = asyncio.run(app._collect_account_prompt_context(5, None))
    assert ctx is None and err is not None
    assert called["assemble"] is False


def test_collect_account_prompt_context_delegates(monkeypatch):
    monkeypatch.setattr(app, "_connect_memory", lambda: _FakeConn(None))
    monkeypatch.setattr(app, "_require_account", lambda request, conn: ({"id": 7, "role_id": 3}, None))
    monkeypatch.setattr(app, "_account_has_product_access", lambda acc, pid, conn=None: True)
    monkeypatch.setattr(app, "_check_account_token_quota", lambda conn, account: (True, ""))
    seen: dict = {}

    def _assemble(a, r, p):
        seen.update({"a": a, "r": r, "p": p})
        return None, {"ok": True}

    monkeypatch.setattr(app, "_assemble_account_prompt_llm_request", _assemble)
    err, ctx = asyncio.run(app._collect_account_prompt_context(5, None))
    assert err is None and ctx == {"ok": True}
    assert seen == {"a": 7, "r": 3, "p": 5}


def test_collect_account_prompt_context_quota_exceeded(monkeypatch):
    """자동작성도 /api/ask 와 동일 LLM 토큰 quota 게이트 — 초과 시 429, 코어 미위임(REV MAJOR)."""
    monkeypatch.setattr(app, "_connect_memory", lambda: _FakeConn(None))
    monkeypatch.setattr(app, "_require_account", lambda request, conn: ({"id": 7, "role_id": 3}, None))
    monkeypatch.setattr(app, "_account_has_product_access", lambda acc, pid, conn=None: True)
    monkeypatch.setattr(app, "_check_account_token_quota", lambda conn, account: (False, "일일 한도 초과"))
    called = {"assemble": False}

    def _no_assemble(a, r, p):
        called["assemble"] = True
        return None, {}

    monkeypatch.setattr(app, "_assemble_account_prompt_llm_request", _no_assemble)
    err, ctx = asyncio.run(app._collect_account_prompt_context(5, None))
    assert ctx is None and err is not None
    assert called["assemble"] is False
