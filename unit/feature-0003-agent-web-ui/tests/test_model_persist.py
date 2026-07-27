"""feature-0003 model-persist — 대화별 "마지막 요청 모델" 영속·복원 계약 검증.

사용자 요청(2026-07-27): "대화 중 assistant 에게 마지막으로 요청했던 모델을 기준으로,
새로고침이나 다른 대화에서 돌아왔을 때 그 모델 선택이 보존되게 해달라. 다만 '+ 새 대화'로
선택되는 모델은 haiku 그대로."

구현: `/api/ask` 가 **명시 지정된** model 을 대화별 KV(`model`)에 저장하고, `/api/history` 가
그 값을 payload 로 내려 프론트 composer 선택기를 hydration 한다(reasoning_level 과 동형).
신규 대화는 KV 가 비어 있어 프론트가 세션 기본값(API_DEFAULT_MODEL=claude-haiku-4)으로 폴백.

검증(`make test` agent 이미지, DB/LLM 없이 monkeypatch/fake):
  H1  history — 저장된 model 이 allowlist 통과하면 payload.model 로 반환(복원 경로).
  H2  history — 저장값이 allowlist 밖(로컬 LLM alias 등)이면 "" 로 내림(stale alias 복원 차단).
  H3  history — 저장값 없으면 "" (신규 대화 → 프론트 기본값 haiku 유지).
  H4  history — KV 조회 실패해도 payload 는 정상 반환(fail-soft, model="").
  A1  ask — 클라이언트가 model 을 명시하면 그 값이 대화별 KV 에 저장된다.
  A2  ask — model 미지정 내부 재dispatch('AI 로 고치기' 등)는 KV 를 덮어쓰지 않는다(기존 선택 보존).
"""
from __future__ import annotations

import asyncio
import json

import app
from routers import conversations  # feature-0012 P5b


# ── fakes ──────────────────────────────────────────────────────────────────────

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


class _Req:
    """ask() 입력용 최소 request."""

    def __init__(self, payload):
        self._payload = payload
        self.query_params = {}
        self.headers = {}
        self.client = None
        self.scope = {"type": "http", "headers": [], "method": "POST", "path": "/api/ask"}

    async def json(self):
        return self._payload


class _HistoryReq:
    def __init__(self):
        self.query_params = {}
        self.headers = {}
        self.client = None
        self.scope = {"type": "http", "headers": [], "method": "GET", "path": "/api/history"}


_ACCOUNT = {"id": 7, "username": "tester", "permissions": {}}


def _patch_history_guards(monkeypatch, kv, *, can_access=True, window=None):
    """history() 가 KV 조회 지점까지 도달하도록 접근·조회 경로를 통과시킨다."""
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: can_access)
    monkeypatch.setattr(app, "_resolve_display_window", lambda *a, **k: window)
    monkeypatch.setattr(app, "_repair_current_conversation", lambda *a, **k: "")
    monkeypatch.setattr(app, "_get_history", lambda *a, **k: ([], False, None, 0, 0))
    monkeypatch.setattr(app, "_load_user_feedback_by_message", lambda *a, **k: {})
    monkeypatch.setattr(app, "_attach_user_feedback", lambda *a, **k: None)

    def _fake_load_kv(conn, conv_id, key):
        if isinstance(kv, Exception):
            raise kv
        return kv.get(key, "")

    monkeypatch.setattr(app, "load_memory_kv", _fake_load_kv)


def _history_payload(monkeypatch, kv, *, can_access=True, window=None, account=_ACCOUNT):
    _patch_history_guards(monkeypatch, kv, can_access=can_access, window=window)
    resp = conversations.history(
        _HistoryReq(),
        conversation_id="conv-1",
        account=account,
        conn=_BenignConn(),
    )
    return json.loads(resp.body)


# 저장 키는 요청 계정별로 분리된다(그룹 대화에서 타 멤버 선택이 내 composer 를 바꾸지 않게).
_KEY = f"model:{_ACCOUNT['id']}"


# ── H1: 저장값이 allowlist 통과 → payload.model 로 복원 ─────────────────────────

def test_h1_history_returns_saved_model(monkeypatch):
    body = _history_payload(monkeypatch, {_KEY: "claude-sonnet-4"})
    assert body["model"] == "claude-sonnet-4", (
        "대화별로 저장된 마지막 요청 모델이 /api/history 로 내려와야 프론트가 복원할 수 있다"
    )


def test_h1b_history_is_scoped_per_account(monkeypatch):
    """그룹 대화: 타 계정(model:99)의 선택은 내 composer 로 복원되지 않는다."""
    body = _history_payload(monkeypatch, {"model:99": "claude-sonnet-4"})
    assert body["model"] == "", "다른 멤버의 모델 선택이 내 화면·내 토큰 한도로 새지 않는다"


# ── H2: allowlist 밖 저장값 → "" (stale alias 복원 차단) ─────────────────────────

def test_h2_history_blanks_disallowed_model(monkeypatch):
    # 로컬 LLM alias 는 웹 /api/ask 에서 거부되는 값(_is_allowed_api_model=False).
    # 그대로 복원하면 다음 전송이 400 으로 막히므로 서버가 "" 로 내려 기본값 폴백시킨다.
    assert app._is_allowed_api_model("auto") is False
    body = _history_payload(monkeypatch, {_KEY: "auto"})
    assert body["model"] == ""


def test_h2b_history_blanks_unsafe_model_name(monkeypatch):
    body = _history_payload(monkeypatch, {_KEY: "../../etc/passwd"})
    assert body["model"] == "", "형식 위반 alias 도 복원 대상이 아니다"


# ── H2c/H2d: 접근 게이트 — 열람 불가·DENY window 면 모델도 내려주지 않는다 ──────────

def test_h2c_history_no_model_when_access_denied(monkeypatch):
    """접근 권한이 없어 conv_id 가 ""로 해소되면 모델도 노출되지 않는다."""
    body = _history_payload(monkeypatch, {_KEY: "claude-sonnet-4"}, can_access=False)
    assert body["conversation_id"] == ""
    assert body["model"] == "", "열람 불가 대화의 저장 모델을 응답에 싣지 않는다"


def test_h2d_history_no_model_when_display_window_denied(monkeypatch):
    """가시 window DENY(제약 대화) — messages 를 비우는 것과 동일하게 모델도 비운다."""
    body = _history_payload(monkeypatch, {_KEY: "claude-sonnet-4"}, window="DENY")
    assert body["messages"] == []
    assert body["model"] == "", "DENY 뷰어의 composer 를 그 대화 상태로 재조준하지 않는다"


# ── H2e: 계정 식별 불가 → 키 fail-closed(공유 sentinel 슬롯 금지) ─────────────────

def test_h2e_unresolvable_account_yields_empty_key_and_no_restore(monkeypatch):
    """계정 id 해석 실패 시 공유 sentinel 키로 뭉치지 않고 복원 자체를 건너뛴다."""
    assert conversations._model_kv_key(None) == ""
    assert conversations._model_kv_key({}) == ""
    assert conversations._model_kv_key({"id": "not-an-int"}) == ""
    assert conversations._model_kv_key({"id": 7}) == _KEY
    # 식별 불가 계정으로 조회하면 어떤 저장값도 복원되지 않는다(타 익명 호출자 값 공유 차단).
    body = _history_payload(
        monkeypatch, {_KEY: "claude-sonnet-4", "": "claude-sonnet-4"}, account={"id": None},
    )
    assert body["model"] == ""


# ── H3: 저장값 없음(신규 대화) → "" → 프론트 기본값(haiku) 유지 ──────────────────

def test_h3_history_empty_when_never_saved(monkeypatch):
    body = _history_payload(monkeypatch, {})
    assert body["model"] == "", "'+ 새 대화'는 저장값이 없어 프론트 기본값(haiku)에서 시작한다"


# ── H4: KV 조회 실패 → fail-soft ────────────────────────────────────────────────

def test_h4_history_kv_failure_is_fail_soft(monkeypatch):
    body = _history_payload(monkeypatch, RuntimeError("kv down"))
    assert body["model"] == ""
    assert body["conversation_id"] == "conv-1", "KV 조회 실패가 history 응답 자체를 막지 않는다"


# ── ask() 하네스 ───────────────────────────────────────────────────────────────

class _DispatchReached(Exception):
    """KV 저장 직후 지점 도달 신호 — 실 LLM/worker dispatch 는 실행하지 않는다."""


def _run_ask_capture(monkeypatch, body):
    """ask() 를 KV 저장 지점까지 실행하고 save_memory_kv 호출을 캡처한다."""
    saved: list[tuple[str, str, str]] = []

    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda req, c: (_ACCOUNT, None))
    # NOTE(적대 리뷰 C4): `_is_safe_model_name` / `_is_allowed_api_model` 은 **의도적으로 patch 하지
    # 않는다** — 실 allowlist 를 통과한 model 만 저장 지점에 도달함을 이 하네스가 실제로 보장해야
    # 한다(저장이 검증 게이트 위로 올라가는 회귀를 잡기 위함).
    monkeypatch.setattr(app, "_check_account_token_quota", lambda c, a: (True, ""))
    monkeypatch.setattr(app, "_conversation_exists", lambda cid, conn=None: True)
    monkeypatch.setattr(app, "_account_has_permission", lambda a, p: True)
    monkeypatch.setattr(app, "_conversation_owned_by_account", lambda c, cid, aid: True)
    monkeypatch.setattr(app, "_conversation_block_info", lambda cid, conn=None: (False, ""))
    monkeypatch.setattr(app, "_conversation_is_group", lambda cid: False)
    monkeypatch.setattr(app, "_audit_user_action", lambda *a, **k: None)
    monkeypatch.setattr(app, "_acquire_request_slot", lambda k: True)
    monkeypatch.setattr(app, "_release_request_slot", lambda k: None)
    monkeypatch.setattr(app, "_model_supports_temperature", lambda m: False)
    monkeypatch.setattr(app, "_get_default_product_id", lambda c: None)
    monkeypatch.setattr(app, "_role_payload", lambda a: {})
    monkeypatch.setattr(app, "_prepare_vision_inline_images", lambda *a, **k: (None, 0, []))
    monkeypatch.setattr(app, "_prepare_text_inline_attachments", lambda *a, **k: None)
    monkeypatch.setattr(app, "save_memory_kv",
                        lambda conn, cid, key, value: saved.append((cid, key, value)))

    async def _boom(**kwargs):
        raise _DispatchReached()

    monkeypatch.setattr(app, "_dispatch_ask_run", _boom)
    resp = None
    try:
        resp = asyncio.run(conversations.ask(_Req(body)))
    except _DispatchReached:
        pass
    return saved, resp


# ── A1: 명시 model → (대화, 계정)별 KV 저장 ─────────────────────────────────────

def test_a1_ask_persists_explicit_model(monkeypatch):
    saved, _ = _run_ask_capture(monkeypatch, {
        "message": "안녕", "conversation_id": "conv-1", "model": "claude-sonnet-4",
    })
    assert ("conv-1", _KEY, "claude-sonnet-4") in saved, (
        "사용자가 고른 모델이 (대화, 계정)별 KV 에 저장돼야 새로고침·대화 복귀 시 복원된다"
    )


def test_a1b_ask_clears_kv_when_model_equals_session_default(monkeypatch):
    """기본값과 같은 모델은 '이탈 없음' 으로 지운다(운영이 기본 모델을 올리면 자연 반영)."""
    default_model = app._resolve_session_default_model()
    saved, _ = _run_ask_capture(monkeypatch, {
        "message": "안녕", "conversation_id": "conv-1", "model": default_model,
    })
    assert ("conv-1", _KEY, "") in saved, (
        "기본값 선택은 빈 값 저장(해제) — 복원 결과는 동일하고 기본값 변경이 따라온다"
    )


def test_a1c_ask_rejects_disallowed_model_before_persisting(monkeypatch):
    """allowlist 밖 alias 는 400 으로 막히고 KV 에 도달하지 않는다(저장이 검증 위로 올라가는 회귀 차단)."""
    saved, resp = _run_ask_capture(monkeypatch, {
        "message": "안녕", "conversation_id": "conv-1", "model": "auto",  # 로컬 LLM alias
    })
    assert resp is not None and resp.status_code == 400
    assert not [s for s in saved if s[1] == _KEY], "거부된 모델은 저장되지 않는다"


# ── A2: model 미지정 내부 재dispatch → KV 미변경(기존 선택 보존) ─────────────────

def test_a2_ask_without_model_does_not_overwrite(monkeypatch):
    # 'AI 로 고치기'(fix_with_ai)는 model 없이 ask 를 재dispatch 한다 — 이 경로가 대화의
    # 선택 모델을 기본값(haiku)으로 조용히 되돌리면 사용자 선택이 사라진다.
    saved, _ = _run_ask_capture(monkeypatch, {
        "message": "정정해줘", "conversation_id": "conv-1",
    })
    assert not [s for s in saved if s[1] == _KEY], (
        "model 미지정 요청은 저장된 대화 모델을 덮어쓰지 않는다"
    )


def test_a2b_ask_blank_model_does_not_overwrite(monkeypatch):
    saved, _ = _run_ask_capture(monkeypatch, {
        "message": "정정해줘", "conversation_id": "conv-1", "model": "   ",
    })
    assert not [s for s in saved if s[1] == _KEY], "공백 model 도 명시 선택이 아니다"
