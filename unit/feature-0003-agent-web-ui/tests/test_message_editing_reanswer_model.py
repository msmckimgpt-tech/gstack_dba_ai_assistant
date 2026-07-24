"""feature-0019 reanswer-model-select — 재답변(요청사항 수정)이 사용자가 선택한 model +
추론 강도(reasoning_level)로 재요청하는지 web 경계에서 검증한다 (DB/LLM 없이 monkeypatch/fake).

배경(회귀): `post_edit_message` 의 reanswer 분기가 ask_body 에 model/reasoning 을 싣지 않아
`ask()` 가 `API_DEFAULT_MODEL`(claude-haiku-4) + 모델 config 기본 추론으로 폴백 → 사용자가 고른
sonnet + 매우높음(max) 선택이 haiku + 일반으로 무시됨. 프론트가 정상 /api/ask 와 동일하게
model + reasoning_level 을 전달하고 backend 가 forward 하도록 수정.

검증 대상:
  F1  reanswer + model/reasoning_level 제공 → 재dispatch ask_body 에 그대로 forward.
  F2  reanswer + model/reasoning_level 부재(구 클라이언트) → ask_body 에 미포함(ask() 기본 폴백 보존).
  F3  reanswer + reasoning_level="normal"(일반) 명시 → forward(정규화·override 계약은 ask() 책임).
  S1  simple 수정 → ask 미dispatch(model/reasoning 무관).

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json

import app
import shared.db as shared_db
from routers import conversations  # feature-0012 P5b


# ── Fakes ──────────────────────────────────────────────────────────────────────

class _FakeRequest:
    """post_edit_message 입력용. _make_internal_ask_request 가 scope/_receive 를 읽으므로 제공."""

    def __init__(self, payload=None):
        self._payload = payload if payload is not None else {}
        self.query_params = {}
        self.headers = {}
        self.client = None
        self.scope = {"type": "http", "headers": [], "method": "POST",
                      "path": "/api/conversations/x/messages/1/edit"}

    async def _receive(self):
        return {"type": "http.disconnect"}

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
    def __init__(self):
        self.committed = False

    def cursor(self, *a, **k):
        return _BenignCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        return None

    def close(self):
        return None


def _body(resp):
    return json.loads(resp.body)


def _patch_ask_capture(monkeypatch):
    """conversations.ask 를 캡처용으로 교체 — 실 LLM 미실행. 재dispatch 된 내부 request 의 body 회수."""
    captured: dict = {"called": False, "body": None}

    async def _fake_ask(internal_request):
        captured["called"] = True
        captured["body"] = await internal_request.json()
        return app.JSONResponse({"output": "재답변", "conversation_id": "conv-1", "steps": [], "error": ""})

    monkeypatch.setattr(conversations, "ask", _fake_ask)
    return captured


def _patch_reanswer_guards(monkeypatch, *, disp=None):
    """post_edit_message 의 1:1 reanswer 성공 경로 가드를 전부 통과시키는 공통 patch."""
    acct = {"id": 5, "username": "tester", "permissions": {"conversation.ask": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(app, "_account_has_permission", lambda account, perm: True)
    monkeypatch.setattr(app, "_search_rate_limit_check", lambda *a, **k: True)
    # 편집 대상 메시지(본인 발신 user 메시지) — shared.db._pg_connect 는 함수 내부 import.
    monkeypatch.setattr(shared_db, "_pg_connect", lambda: _BenignConn())
    _disp = disp if disp is not None else {"id": 1, "role": "user", "content": "원래 질문", "meta_json": None}
    monkeypatch.setattr(app, "_branch_get_display_message", lambda _pg, cid, mid: _disp)
    monkeypatch.setattr(app, "_conversation_is_group", lambda cid: False)   # 1:1
    monkeypatch.setattr(app, "_conversation_owned_by_account", lambda conn, cid, aid: True)  # owner=발신자
    monkeypatch.setattr(app, "record_audit_event", lambda conn, **kw: None)
    monkeypatch.setattr(app, "_build_actor_from_request",
                        lambda request, account, actor_type="account": {"actor_type": actor_type})
    monkeypatch.setattr(app, "_branch_reanswer_setup", lambda cid, disp: {"prior": True})
    return acct


# ── F1: model + reasoning_level 제공 → forward ───────────────────────────────────

def test_reanswer_forwards_selected_model_and_reasoning(monkeypatch):
    _patch_reanswer_guards(monkeypatch)
    cap = _patch_ask_capture(monkeypatch)
    resp = asyncio.run(conversations.post_edit_message("conv-1", 1, _FakeRequest({
        "mode": "reanswer", "new_content": "수정한 질문",
        "model": "claude-sonnet-4", "reasoning_level": "max",
    })))
    assert resp.status_code == 200
    assert cap["called"] is True
    body = cap["body"]
    assert body["conversation_id"] == "conv-1"
    assert body["message"] == "수정한 질문"
    assert body["model"] == "claude-sonnet-4", "선택한 model 이 재dispatch ask_body 로 forward"
    assert body["reasoning_level"] == "max", "선택한 추론 강도가 재dispatch ask_body 로 forward"


# ── F2: model/reasoning 부재(구 클라이언트) → ask_body 미포함(기본 폴백 보존) ─────────────

def test_reanswer_omits_model_reasoning_when_absent(monkeypatch):
    _patch_reanswer_guards(monkeypatch)
    cap = _patch_ask_capture(monkeypatch)
    resp = asyncio.run(conversations.post_edit_message("conv-1", 1, _FakeRequest({
        "mode": "reanswer", "new_content": "수정한 질문",  # model/reasoning_level 미포함
    })))
    assert resp.status_code == 200
    body = cap["body"]
    assert "model" not in body, "부재 시 model 미강제 — ask() 가 API_DEFAULT_MODEL 로 폴백"
    assert "reasoning_level" not in body, "부재 시 reasoning 미강제 — ask() override 계약 보존"


# ── F3: reasoning_level='normal'(일반) 명시 → forward ─────────────────────────────

def test_reanswer_forwards_explicit_normal_reasoning(monkeypatch):
    _patch_reanswer_guards(monkeypatch)
    cap = _patch_ask_capture(monkeypatch)
    resp = asyncio.run(conversations.post_edit_message("conv-1", 1, _FakeRequest({
        "mode": "reanswer", "new_content": "질문", "model": "claude-haiku-4",
        "reasoning_level": "normal",
    })))
    assert resp.status_code == 200
    body = cap["body"]
    assert body["model"] == "claude-haiku-4"
    assert body["reasoning_level"] == "normal", "'일반' 명시 선택도 forward(빈 문자열/None 만 미포함)"


# ── F4: reanswer 재dispatch 가 non-2xx(예: forward model allowlist 위반 400) → 브랜치 상태 복원 ──
# (REV-20260724T0641-reanswer-model-select MINOR — model forward 로 신설된 400 도달 경로가
#  active_leaf 를 M.parent 에 고착시키지 않도록 보상 복원. 기존은 예외에만 복원했음.)

def test_reanswer_restores_branch_state_on_ask_non_2xx(monkeypatch):
    _patch_reanswer_guards(monkeypatch)
    restored = {"called": False, "prior": None}

    def _fake_restore(cid, prior):
        restored["called"] = True
        restored["prior"] = prior

    monkeypatch.setattr(app, "_branch_restore_state", _fake_restore)

    async def _fake_ask_400(internal_request):
        # ask() 상단 게이트(허용되지 않은 모델)와 동형 — 예외 아닌 non-2xx JSONResponse 반환.
        return app._json_error("허용되지 않은 모델입니다.", 400)

    monkeypatch.setattr(conversations, "ask", _fake_ask_400)
    resp = asyncio.run(conversations.post_edit_message("conv-1", 1, _FakeRequest({
        "mode": "reanswer", "new_content": "질문", "model": "bad-model",
    })))
    assert resp.status_code == 400, "ask() 의 400 을 그대로 전달(사용자에게 원인 노출)"
    assert restored["called"] is True, "non-2xx → 편집 직전 브랜치 상태 복원(active_leaf 고착 방지)"
    assert restored["prior"] == {"prior": True}, "복원은 _branch_reanswer_setup 이 준 _prior 로 수행"


def test_reanswer_does_not_restore_on_2xx(monkeypatch):
    # 성공(200)·200+error 본문(정정 실패 등)은 새 user 메시지 저장·active_leaf 전진 → 복원 안 함.
    _patch_reanswer_guards(monkeypatch)
    restored = {"called": False}
    monkeypatch.setattr(app, "_branch_restore_state", lambda cid, prior: restored.__setitem__("called", True))
    _patch_ask_capture(monkeypatch)  # 200 반환
    resp = asyncio.run(conversations.post_edit_message("conv-1", 1, _FakeRequest({
        "mode": "reanswer", "new_content": "질문", "model": "claude-sonnet-4", "reasoning_level": "max",
    })))
    assert resp.status_code == 200
    assert restored["called"] is False, "2xx 는 저장 완료 경로 — 브랜치 복원 금지(tail 소실 방지 아님)"


# ── S1: simple 수정 → ask 미dispatch ─────────────────────────────────────────────

def test_simple_edit_does_not_dispatch_ask(monkeypatch):
    _patch_reanswer_guards(monkeypatch)
    monkeypatch.setattr(app, "_branch_simple_edit", lambda cid, disp, nc: None)
    cap = _patch_ask_capture(monkeypatch)
    resp = asyncio.run(conversations.post_edit_message("conv-1", 1, _FakeRequest({
        "mode": "simple", "new_content": "수정만",
        "model": "claude-sonnet-4", "reasoning_level": "max",
    })))
    assert resp.status_code == 200
    assert _body(resp).get("mode") == "simple"
    assert cap["called"] is False, "단순 수정은 재답변 없음 — ask 미dispatch"
