"""TASK-20260625-role-account-prompt-autogen — 역할 '전체 제품 프롬프트' 자동작성 회귀 테스트.

관리 콘솔 > 역할 > [각 항목] > 제품 사용 > 전체 제품 프롬프트 의 '자동 작성'은 제품 프롬프트
자동작성(TASK-0309/0237)을 role scope(`scope='role'`, ProductId NULL)로 확장한 것이다.
컨텍스트는 **역할 성격**(정의·권한 특성) + **그 역할 소속 사용자들의 실제 대화 패턴**
(집계 topic·summary)이다. 원문 메시지가 아닌 집계 메타만 사용한다(제품 경로와 동일 privacy).

검증:
  T1  _describe_role_character: 질의권한 없는 역할 → '조회 전용' 명시 + description 포함.
  T2  _describe_role_character: admin 역할 → 관리 특성 노출, '조회 전용' 아님.
  T3  _collect_conversation_signals_pg(account_ids=[]) → PG 미접근 + 빈 결과(cross-scope 누출 방지).
  T4  _collect_conversation_signals_pg 필터: account_ids/product_id → SQL owner/product 절 + 파라미터.
  T5  _assemble_role_prompt_llm_request: 역할 없음 → 404 (ctx None).
  T6  _assemble_role_prompt_llm_request: 정상 → ctx.meta_base(member/topic/grounded) + meta-prompt 에
      역할명·성격·실제 주제 포함.
  T7  _collect_role_prompt_context: system_prompt.manage.role.any 미보유 → 403 (코어 미위임).

스트리밍 SSE 경로는 product/role/account 가 공유하는 `_prompt_generate_stream_response`
브릿지를 재사용하며, 그 계약은 test_prompt_generate_stream.py 가 이미 고정한다.

`make test`(agent 이미지, --no-deps)에서 DB 없이 fake/monkeypatch 로 실행된다.
"""
from __future__ import annotations

import asyncio

import app


# ── Fakes ───────────────────────────────────────────────────────────────────────

class _FakeLLMClient:
    """`_get_llm_client` 가 반환하는 객체 자리표시자(어셈블 단계는 호출하지 않음)."""

    def __init__(self):
        self.chat = type("Chat", (), {"completions": None})()


class _FakeCursor:
    """role assembly 의 인라인 SQL(WebAccounts 소속 조회)만 해석하는 fake."""

    def __init__(self, account_ids):
        self._account_ids = account_ids
        self._rows = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "FROM WebAccounts WHERE RoleId" in s:
            self._rows = [(aid,) for aid in self._account_ids]
        else:
            self._rows = []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        return None


class _FakeConn:
    def __init__(self, account_ids):
        self._account_ids = account_ids

    def cursor(self, *a, **k):
        return _FakeCursor(self._account_ids)

    def close(self):
        return None


def _patch_llm(monkeypatch):
    monkeypatch.setattr(app, "_resolve_session_default_model", lambda: "test-model")
    monkeypatch.setattr(app, "max_tokens_for_model", lambda model, kind: 1000)
    monkeypatch.setattr(app, "model_supports_temperature", lambda model: True)
    monkeypatch.setattr("modules.llm._get_llm_client", lambda model=None: _FakeLLMClient())


# ── T1/T2 _describe_role_character ──────────────────────────────────────────────

def test_describe_role_character_readonly():
    role = {
        "description": "조회 전용 파일럿",
        "permission_codes": ["conversation.list.own", "conversation.read.own"],
    }
    out = app._describe_role_character(role)
    assert "조회 전용" in out
    assert "조회 전용 파일럿" in out  # description 포함


def test_describe_role_character_admin():
    role = {
        "description": "관리자",
        "permission_codes": [
            "conversation.ask", "product.manage", "console.access",
            "system_prompt.manage.role.any",
        ],
    }
    out = app._describe_role_character(role)
    assert "제품 구성 관리(관리자)" in out
    assert "조회 전용" not in out  # ask 보유 → 조회 전용 아님


# ── T3/T4 _collect_conversation_signals_pg ──────────────────────────────────────

def test_collect_signals_empty_accounts_short_circuits(monkeypatch):
    """account_ids=[] 면 PG 를 건드리지 않고 빈 결과 — 전체 대화 누출 방지."""

    def _boom():
        raise AssertionError("_pg_connect must not be called for empty account_ids")

    monkeypatch.setattr("shared.db._pg_connect", _boom)
    topics, summaries = app._collect_conversation_signals_pg(account_ids=[])
    assert topics == [] and summaries == []


class _RecPgCursor:
    def __init__(self, rec):
        self._rec = rec
        self._q = 0

    def execute(self, sql, params=None):
        self._rec.append((" ".join(sql.split()), list(params or ())))
        self._q += 1

    def fetchall(self):
        # 1st execute = topics, 2nd = summaries
        return [("주제A",)] if self._q == 1 else [("요약B",)]

    def close(self):
        return None


class _RecPgConn:
    def __init__(self, rec):
        self._rec = rec

    def cursor(self):
        return _RecPgCursor(self._rec)

    def close(self):
        return None


def test_collect_signals_filters(monkeypatch):
    rec: list = []
    monkeypatch.setattr("shared.db._pg_connect", lambda: _RecPgConn(rec))
    topics, summaries = app._collect_conversation_signals_pg(account_ids=[1, 2], product_id=5)
    assert topics == ["주제A"]
    assert summaries == ["요약B"]
    topic_sql, topic_params = rec[0]
    assert "owner_account_id IN" in topic_sql
    assert "product_id = %s" in topic_sql
    assert 5 in topic_params and 1 in topic_params and 2 in topic_params


# ── T5/T6 _assemble_role_prompt_llm_request ─────────────────────────────────────

def test_assemble_role_prompt_not_found(monkeypatch):
    monkeypatch.setattr(app, "_connect_memory", lambda: _FakeConn([]))
    monkeypatch.setattr(app, "_load_role_by_id", lambda conn, rid: None)
    err, ctx = app._assemble_role_prompt_llm_request(99)
    assert ctx is None and err is not None


def test_assemble_role_prompt_ok(monkeypatch):
    _patch_llm(monkeypatch)
    monkeypatch.setattr(app, "_connect_memory", lambda: _FakeConn([10, 11, 12]))
    monkeypatch.setattr(
        app, "_load_role_by_id",
        lambda conn, rid: {
            "id": rid, "key": "sales", "name": "사업팀",
            "description": "게임 사업팀",
            "permission_codes": ["conversation.ask", "conversation.create"],
        },
    )
    monkeypatch.setattr(app, "_list_products", lambda conn: [{"id": 1, "product_key": "KR", "name": "한국"}])
    monkeypatch.setattr(app, "_product_permission_code", lambda k: f"product.access.{k.lower()}")
    monkeypatch.setattr(
        app, "_collect_conversation_signals_pg",
        lambda **kw: (["아이템 매출 조회", "NPC 분포"], ["과거 요약1"]),
    )
    err, ctx = app._assemble_role_prompt_llm_request(3)
    assert err is None and ctx is not None
    mb = ctx["meta_base"]
    assert mb["member_count"] == 3
    assert mb["topic_count"] == 2
    assert mb["grounded"] is True
    content = ctx["create_kwargs"]["messages"][0]["content"]
    assert "사업팀" in content
    assert "아이템 매출 조회" in content
    assert "역할(role) 공통 시스템 프롬프트" in content


# ── T7 _collect_role_prompt_context auth gate ───────────────────────────────────

def test_collect_role_prompt_context_requires_permission(monkeypatch):
    monkeypatch.setattr(app, "_connect_memory", lambda: _FakeConn([]))
    monkeypatch.setattr(app, "_require_account", lambda request, conn: ({"id": 1}, None))
    monkeypatch.setattr(app, "_account_has_permission", lambda acc, perm: False)
    called = {"assemble": False}

    def _no_assemble(rid):
        called["assemble"] = True
        return None, {}

    monkeypatch.setattr(app, "_assemble_role_prompt_llm_request", _no_assemble)
    err, ctx = asyncio.run(app._collect_role_prompt_context(3, None))
    assert ctx is None and err is not None
    assert called["assemble"] is False  # 권한 미보유 → 코어 미위임
