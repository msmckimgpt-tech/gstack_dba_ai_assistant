"""feature-0018 runtime-settings — 관리 콘솔 설정 API RBAC/검증 테스트.

TestClient + as_account(conftest) 로 require_permission 게이트를 실제로 태운다(RP 패턴).
make test 환경(--no-deps, DB 미기동)에서 get_conn 은 None 을 yield → GET 은 기본값 레지스트리를
반환하고, 실제 저장이 필요한 PUT 은 conn=None 이면 500 을 반환한다(검증→conn 순서 확인).
DB 저장/스냅샷 왕복은 라이브 통합 QA 로 검증한다.
"""
from __future__ import annotations

WRITE_PERMS = {
    "console.access": True,
    "system.runtime.read": True,
    "system.runtime.write": True,
}
READ_PERMS = {"console.access": True, "system.runtime.read": True}
ENDPOINT = "/api/admin/settings/runtime"


# ── GET RBAC ────────────────────────────────────────────────────────────────
def test_get_requires_read_permission(client, as_account):
    as_account(perms={"console.access": True})  # system.runtime.read 없음
    resp = client.get(ENDPOINT)
    assert resp.status_code == 403


def test_get_requires_console_access(client, as_account):
    as_account(perms={"system.runtime.read": True})  # console.access 없음
    resp = client.get(ENDPOINT)
    assert resp.status_code == 403


def test_get_anonymous_401(client, as_anonymous):
    as_anonymous()
    resp = client.get(ENDPOINT)
    assert resp.status_code == 401


def test_get_returns_registry(client, as_account):
    as_account(perms=READ_PERMS)
    resp = client.get(ENDPOINT)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("timeouts"), list) and len(body["timeouts"]) >= 20
    assert isinstance(body.get("model_thinking_budgets"), list)
    keys = {t["key"] for t in body["timeouts"]}
    assert "AGENT_TIMEOUT_SEC" in keys and "MCP_TIMEOUT_SEC" in keys
    # 무 DB(get_conn=None) → override 없음 → effective == default.
    row = next(t for t in body["timeouts"] if t["key"] == "AGENT_TIMEOUT_SEC")
    assert row["effective"] == row["default"] == 60 and row["has_override"] is False
    assert row["apply_mode"] == "live"


# ── PUT RBAC + 검증 ──────────────────────────────────────────────────────────
def test_put_requires_write_permission(client, as_account):
    as_account(perms=READ_PERMS)  # write 없음
    resp = client.put(ENDPOINT, json={"key": "AGENT_TIMEOUT_SEC", "value": 90})
    assert resp.status_code == 403


def test_put_rejects_out_of_range(client, as_account):
    as_account(perms=WRITE_PERMS)
    resp = client.put(ENDPOINT, json={"key": "AGENT_TIMEOUT_SEC", "value": 2})  # min 5
    assert resp.status_code == 400
    assert "범위" in resp.json().get("error", "")


def test_put_rejects_unregistered_key(client, as_account):
    as_account(perms=WRITE_PERMS)
    resp = client.put(ENDPOINT, json={"key": "BOGUS_KEY", "value": 5})
    assert resp.status_code == 400


def test_put_rejects_non_integer(client, as_account):
    as_account(perms=WRITE_PERMS)
    resp = client.put(ENDPOINT, json={"key": "AGENT_TIMEOUT_SEC", "value": "abc"})
    assert resp.status_code == 400


def test_put_valid_value_passes_validation_then_needs_db(client, as_account):
    # 검증 통과(범위 내) → conn 사용 단계. make test 는 DB 미기동이라 500(db connection failed).
    # 이는 '유효 값은 검증을 통과한다'는 것과 '검증이 conn 사용보다 먼저'임을 함께 확인한다.
    as_account(perms=WRITE_PERMS)
    resp = client.put(ENDPOINT, json={"key": "AGENT_TIMEOUT_SEC", "value": 90})
    assert resp.status_code in (200, 500)
    if resp.status_code == 400:
        raise AssertionError("유효 값이 검증에서 거부되면 안 된다")


def test_put_model_budget_key_validates(client, as_account):
    as_account(perms=WRITE_PERMS)
    # 범위 밖(16000 초과) → 400.
    resp = client.put(ENDPOINT, json={"key": "model_thinking_budget:claude-sonnet-4", "value": 99999})
    assert resp.status_code == 400


# ── DELETE(초기화) RBAC + 검증 ──────────────────────────────────────────────
def test_delete_requires_write_permission(client, as_account):
    as_account(perms=READ_PERMS)
    resp = client.delete(ENDPOINT, params={"key": "AGENT_TIMEOUT_SEC"})
    assert resp.status_code == 403


def test_delete_unregistered_key_400(client, as_account):
    as_account(perms=WRITE_PERMS)
    resp = client.delete(ENDPOINT, params={"key": "BOGUS_KEY"})
    assert resp.status_code == 400
