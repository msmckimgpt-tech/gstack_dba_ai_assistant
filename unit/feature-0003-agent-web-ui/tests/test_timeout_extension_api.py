"""feature-0030 실행시간 연장 — `POST /api/extend` RBAC·게이트·시그널 테스트.

TestClient + as_account(conftest) 로 실제 인가 경로를 태운다. DB 는 --no-deps 라
대화 해석/권한 검사/KV 쓰기를 app 모듈 함수 수준에서 monkeypatch 해 엔드포인트의
계약(권한 → 기능 게이트 → 승인 기록 순서)만 검증한다.
"""
from __future__ import annotations

import pytest

import app as appmod

ENDPOINT = "/api/extend"
CID = "conv-1"


@pytest.fixture
def wired(monkeypatch):
    """대화 해석·인가·KV 를 통제 가능한 스텁으로 교체하고 호출 기록을 돌려준다."""
    calls: dict[str, object] = {"granted": None, "allowed": True, "enabled": 1}

    monkeypatch.setattr(appmod, "_resolve_conversation_for_account", lambda *a, **k: CID)
    monkeypatch.setattr(
        appmod, "_account_can_access_conversation",
        lambda *a, **k: bool(calls["allowed"]),
    )
    monkeypatch.setattr(appmod, "load_memory_kv", lambda *a, **k: "R1")

    def _grant(_conn, conversation_id, run_id=""):
        calls["granted"] = (conversation_id, run_id)
        return True

    monkeypatch.setattr(appmod, "mark_timeout_extension_granted", _grant)

    def _get_int(key):
        if key == "AGENT_TIMEOUT_EXTENSION_ENABLED":
            if calls["enabled"] == "boom":
                raise RuntimeError("settings down")
            return int(calls["enabled"])
        return 60

    monkeypatch.setattr(appmod._runtime_settings, "get_int", _get_int)
    return calls


def test_anonymous_401(client, as_anonymous):
    as_anonymous()
    resp = client.post(ENDPOINT, json={"conversation_id": CID})
    assert resp.status_code == 401


def test_denied_without_permission(client, as_account, wired):
    wired["allowed"] = False
    as_account(perms={"conversation.list.own": True})
    resp = client.post(ENDPOINT, json={"conversation_id": CID})
    assert resp.status_code == 403
    assert wired["granted"] is None, "인가 실패 시 승인이 기록되면 안 된다"


def test_grants_with_permission(client, as_account, wired):
    as_account(perms={"conversation.extend.own": True})
    resp = client.post(ENDPOINT, json={"conversation_id": CID})
    assert resp.status_code == 200
    assert wired["granted"] == (CID, "R1")


def test_feature_off_returns_409_without_recording(client, as_account, wired):
    """OFF 상태의 stale 프론트 호출이 승인을 남기면 다음 ON 전환 때 되살아난다."""
    wired["enabled"] = 0
    as_account(perms={"conversation.extend.own": True})
    resp = client.post(ENDPOINT, json={"conversation_id": CID})
    assert resp.status_code == 409
    assert wired["granted"] is None


def test_empty_conversation_id_400(client, as_account, wired, monkeypatch):
    monkeypatch.setattr(appmod, "_resolve_conversation_for_account", lambda *a, **k: "")
    as_account(perms={"conversation.extend.own": True})
    resp = client.post(ENDPOINT, json={"conversation_id": ""})
    assert resp.status_code == 400


def test_invalid_json_400(client, as_account, wired):
    as_account(perms={"conversation.extend.own": True})
    resp = client.post(ENDPOINT, content=b"not-json", headers={"content-type": "application/json"})
    assert resp.status_code == 400


# ── codex 적대 리뷰 P1-1 / P2-1 회귀 방지 ────────────────────────────────────

def test_stale_client_run_id_rejected(client, as_account, wired, monkeypatch):
    """배너가 가리키던 run 이 이미 교체됐으면 승인을 기록하지 않는다.

    기록하면 사용자가 보지도 않은 새 run 이 무제한 연장된다.
    """
    monkeypatch.setattr(appmod, "load_memory_kv", lambda *a, **k: "R2")  # 현재 run 은 R2
    as_account(perms={"conversation.extend.own": True})
    resp = client.post(ENDPOINT, json={"conversation_id": CID, "run_id": "R1"})
    assert resp.status_code == 409
    assert wired["granted"] is None


def test_matching_client_run_id_accepted(client, as_account, wired, monkeypatch):
    monkeypatch.setattr(appmod, "load_memory_kv", lambda *a, **k: "R1")
    as_account(perms={"conversation.extend.own": True})
    resp = client.post(ENDPOINT, json={"conversation_id": CID, "run_id": "R1"})
    assert resp.status_code == 200
    assert wired["granted"] == (CID, "R1")


def test_no_active_run_rejected(client, as_account, wired, monkeypatch):
    """진행 중 run 이 없으면 승인 대상이 없다 — 빈 run_id 로 기록하면 wildcard 가 된다."""
    monkeypatch.setattr(appmod, "load_memory_kv", lambda *a, **k: "")
    as_account(perms={"conversation.extend.own": True})
    resp = client.post(ENDPOINT, json={"conversation_id": CID})
    assert resp.status_code == 409
    assert wired["granted"] is None


def test_settings_lookup_failure_is_fail_closed(client, as_account, wired):
    """설정 조회 실패 시 승인을 남기면 기능 재활성 때 의도 없는 연장으로 되살아난다.

    워커의 `_timeout_extension_settings()` 가 fail-closed 이므로 API 도 대칭이어야 한다.
    """
    wired["enabled"] = "boom"
    as_account(perms={"conversation.extend.own": True})
    resp = client.post(ENDPOINT, json={"conversation_id": CID})
    assert resp.status_code == 503
    assert wired["granted"] is None


def test_grant_refusal_surfaces_as_409(client, as_account, wired, monkeypatch):
    """memory 층이 run 불일치로 거절하면 200 으로 위장하지 않는다."""
    monkeypatch.setattr(appmod, "mark_timeout_extension_granted", lambda *a, **k: False)
    as_account(perms={"conversation.extend.own": True})
    resp = client.post(ENDPOINT, json={"conversation_id": CID})
    assert resp.status_code == 409


# ── 권한 카탈로그 ────────────────────────────────────────────────────────────

def test_extend_permissions_registered():
    codes = {d["code"] for d in appmod.PERMISSION_DEFINITIONS}
    assert "conversation.extend.own" in codes
    assert "conversation.extend.any" in codes


def test_extend_permission_metadata_within_column_limits():
    """webperm catalog 계약: description ≤ 255 / label ≤ 128 — 초과 시 시드 catchup 전체가 중단된다."""
    for d in appmod.PERMISSION_DEFINITIONS:
        if not str(d["code"]).startswith("conversation.extend."):
            continue
        assert len(str(d["description"])) <= 255
        assert len(str(d["label"])) <= 128


def test_extend_own_seeded_to_conversation_roles():
    """대화를 보내는 시드 역할은 자기 요청의 연장을 승인할 수 있어야 한다."""
    for role in appmod.SEED_ROLE_DEFINITIONS:
        perms = role.get("permissions") or set()
        if "conversation.finalize.own" in perms:
            assert "conversation.extend.own" in perms, f"{role.get('key')} 역할에 연장 권한 누락"


def test_extend_any_not_auto_seeded_to_non_admin_roles():
    """`any`(타인 run 무제한 연장 + 비용)는 자동 확대하지 않는다 — 관리자 명시 부여.

    '중단'(finalize)과 위험 방향이 반대라 finalize 보유만으로 자동 부여하면 과도한 권한
    확대가 된다(codex 적대 리뷰 P1-4).
    """
    for role in appmod.SEED_ROLE_DEFINITIONS:
        if str(role.get("key") or "").lower() == "admin":
            continue
        perms = role.get("permissions") or set()
        assert "conversation.extend.any" not in perms, f"{role.get('key')} 에 extend.any 자동 부여됨"
