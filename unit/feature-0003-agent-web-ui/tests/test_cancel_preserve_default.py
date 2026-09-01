"""REQ-20260901T020746-interrupt-context-preserve — 중단은 **기본이 보존** 이다.

## 이 스위트가 잠그는 것

`composer-nonblock-interrupt` R3 는 `preserve_reasoning` 축을 만들었지만 두 진입점 중
**한쪽에만** 배선했다:

| 진입점 | 보내던 값 | 결과 |
|---|---|---|
| 진행 중 새 발화(인터럽트 재요청) | `preserve_reasoning: true` | 진행분 보존 |
| **명시 '중단' 버튼** | (미전송) | `bool(None)` → **전량 폐기** |

즉 결함은 계산이 아니라 **기본값의 방향**이었다. 그래서 여기서 단언하는 것은 "함수가 옳은가"
가 아니라 **"플래그를 안 보내는 호출이 보존으로 떨어지는가"** 다 — 실제 `/api/cancel` 을 쳐서
`mark_cancel_requested` 가 받은 값을 관측한다(헬퍼 단위 검증으로는 이 방향이 안 보인다).

기본값을 서버에 둔 이유도 함께 잠근다: `/api/cancel` 은 외부 AI 도구 표면
(`ai_discovery.py`)에도 공개돼 있어, 프런트만 고치면 그 경로는 계속 폐기한다.
"""
from __future__ import annotations

import json
import pathlib

import pytest

import app as appmod
from routers import conversations  # noqa: F401  (라우터 등록 보장)

_HERE = pathlib.Path(__file__).resolve()
_SRC = _HERE.parents[1] / "src"
APP_JS = _SRC / "static" / "app.js"
DISCOVERY_PY = _SRC / "routers" / "ai_discovery.py"

CID = "20260901T020746-cancel"


@pytest.fixture
def cancel_probe(monkeypatch, as_account):
    """`/api/cancel` 을 DB 없이 태우고, mark_cancel_requested 가 받은 인자를 노출한다."""
    seen: dict[str, object] = {}

    as_account(perms={"conversation.cancel.own": True, "conversation.cancel.any": True})
    appmod.app.dependency_overrides[appmod.get_conn] = lambda: None

    monkeypatch.setattr(appmod, "_resolve_conversation_for_account",
                        lambda *_a, **_k: CID, raising=False)
    monkeypatch.setattr(appmod, "_account_can_access_conversation",
                        lambda *_a, **_k: True, raising=False)
    monkeypatch.setattr(conversations, "_cancel_bridge_tasks_for",
                        lambda *_a, **_k: {"deleted": [], "canceled": []}, raising=False)
    monkeypatch.setattr(appmod, "load_memory_kv",
                        lambda *_a, **_k: "run-1", raising=False)
    monkeypatch.setattr(appmod, "_is_worker_mode", lambda: False, raising=False)
    monkeypatch.setattr(appmod, "set_run_status",
                        lambda *_a, **_k: None, raising=False)

    def _mark(conn, conversation_id, run_id="", preserve_reasoning=False):
        seen["conversation_id"] = conversation_id
        seen["run_id"] = run_id
        seen["preserve_reasoning"] = preserve_reasoning

    monkeypatch.setattr(appmod, "mark_cancel_requested", _mark, raising=False)
    return seen


# ── ① 기본값의 방향 ────────────────────────────────────────────────────────────
def test_cancel_without_flag_preserves(client, cancel_probe):
    """명시 '중단' 버튼(플래그 미전송)이 보존으로 떨어져야 한다 — 이것이 결함의 본체였다."""
    res = client.post("/api/cancel", json={"conversation_id": CID})
    assert res.status_code == 200, res.text
    assert cancel_probe["preserve_reasoning"] is True, (
        "플래그 없는 중단이 폐기로 떨어진다 — 화면·이력·다음 맥락이 동시에 빈다")


def test_cancel_with_explicit_true_preserves(client, cancel_probe):
    res = client.post("/api/cancel",
                      json={"conversation_id": CID, "preserve_reasoning": True})
    assert res.status_code == 200, res.text
    assert cancel_probe["preserve_reasoning"] is True


def test_cancel_with_explicit_false_discards(client, cancel_probe):
    """폐기 경로는 남는다 — 향후 '버리고 중단' UI 의 자리이자, 명시 의사의 존중."""
    res = client.post("/api/cancel",
                      json={"conversation_id": CID, "preserve_reasoning": False})
    assert res.status_code == 200, res.text
    assert cancel_probe["preserve_reasoning"] is False, (
        "명시 false 를 무시하면 사용자가 버리라고 한 것을 남긴다")


@pytest.mark.parametrize("raw", ["", 0, None])
def test_falsy_explicit_values_discard(client, cancel_probe, raw):
    """빈 문자열·0·null 은 '보내긴 했으나 거짓' 이다 — 기본값(보존)으로 승격시키지 않는다."""
    res = client.post("/api/cancel",
                      json={"conversation_id": CID, "preserve_reasoning": raw})
    assert res.status_code == 200, res.text
    assert cancel_probe["preserve_reasoning"] is False


# ── ② 배선 — 프런트와 외부 도구 표면 ─────────────────────────────────────────────
def test_frontend_cancel_states_intent_and_recovers_the_preserved_bubble():
    """프런트가 (a) 보존 의도를 명시하고 (b) 뒤늦게 도착하는 보존분을 화면에 올린다.

    보존분은 agent 루프가 다음 체크포인트에 도달한 뒤에야 쓰인다. 중단과 동시에 진행 폴링을
    멈추므로, 다시 읽어 주지 않으면 사용자는 "대화에 남습니다" 안내를 보고도 직접 새로고침해야
    그것을 본다 — 안내가 거짓말이 된다.
    """
    src = APP_JS.read_text(encoding="utf-8")
    start = src.index("async function cancelCurrentRun")
    body = src[start:src.index("\nasync function ", start + 10)]
    assert "preserve_reasoning: true" in body, "중단 호출이 보존 의도를 남기지 않는다"
    assert "_reloadForPreservedInterrupt(" in body, "뒤늦게 도착하는 보존분을 화면에 올리지 않는다"
    assert "대화에 남습니다" in body, "중단이 '버리는 동작' 으로 읽히는 안내가 그대로다"


def test_preserved_reload_is_bounded_and_yields_to_the_user():
    """유한 재확인이어야 한다 — 무한 재로드는 스크롤을 빼앗고 서버를 두드린다."""
    src = APP_JS.read_text(encoding="utf-8")
    start = src.index("async function _reloadForPreservedInterrupt")
    body = src[start:src.index("\nasync function ", start + 10)]
    assert "DELAYS_MS" in body and "for (const delay of DELAYS_MS)" in body, "재확인 횟수가 유한하지 않다"
    assert "preserveScroll: true" in body, "읽던 위치를 빼앗는다"
    assert "state.busyConversations.size" in body, "새 요청이 시작돼도 끼어든다"
    assert "state.activeConversationId" in body, "다른 대화로 옮겨도 끼어든다"


def test_external_tool_surface_documents_the_default():
    """외부 AI 도구가 이 기본값을 모르면 '취소하면 사라진다' 는 전제로 동작한다."""
    src = DISCOVERY_PY.read_text(encoding="utf-8")
    assert src.count("preserve_reasoning") >= 2, (
        "discovery 목록·OpenAPI 스키마 양쪽에 파라미터가 노출돼야 한다")
    assert '"default": True' in src or "'default': True" in src, "기본값이 스펙에 없다"
