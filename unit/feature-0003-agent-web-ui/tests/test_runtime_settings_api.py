"""feature-0018 runtime-settings — 관리 콘솔 설정 API RBAC/검증 테스트.

TestClient + as_account(conftest) 로 require_permission 게이트를 실제로 태운다(RP 패턴).
conftest 의 `_no_live_memory_conn` autouse fixture 가 get_conn 을 None 으로 고정하므로, GET 은
기본값 레지스트리를 반환하고 실제 저장이 필요한 PUT 은 **항상 500** 이다(검증→conn 순서 확인).
DB 저장/스냅샷 왕복은 라이브 통합 QA 로 검증한다.

⚠ **PUT 이 200 을 반환하면 그것은 테스트 통과가 아니라 격리 실패다** — 라이브 컨트롤플레인
(agent_memory.WebRuntimeSettings)에 실제 override 가 저장됐다는 뜻이다. 2026-07-13~29 사이
이 파일의 PUT 테스트가 `assert status in (200, 500)` 로 양쪽을 허용한 탓에, 운영 관리 콘솔의
'에이전트/쿼리 실행 타임아웃'(사용자 설정 900초)이 매 `make test` 마다 아래 리터럴 값으로
150회 롤백됐다(audit RemoteAddr=testclient). 그래서 본 파일의 저장 경로 assert 는 500 을
**결정적으로** 요구한다 — 200 은 실패로 잡아 격리 회귀를 즉시 드러낸다.
"""
from __future__ import annotations

WRITE_PERMS = {
    "console.access": True,
    "system.runtime.read": True,
    "system.runtime.write": True,
}
READ_PERMS = {"console.access": True, "system.runtime.read": True}
ENDPOINT = "/api/admin/settings/runtime"

# 저장 경로 assert 실패 시 원인을 즉시 지목하는 메시지(격리 회귀 진단용).
_LIVE_WRITE_MSG = (
    "PUT {key} 가 {code} 를 반환했다. 500(db connection failed) 이 아니면 테스트가 실 DB 커넥션을 "
    "잡았다는 뜻 — 라이브 agent_memory.WebRuntimeSettings 에 override 가 저장돼 운영 설정이 "
    "테스트 값으로 롤백된다. conftest `_no_live_memory_conn` autouse fixture 와 Makefile "
    "`TEST_ISOLATION_ENV` 가 유효한지 확인할 것."
)


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
    # reasoning-budget-per-model: 신규 그룹 agent_max_outputs + per-model reasoning_budgets 노출.
    assert isinstance(body.get("agent_max_outputs"), list) and len(body["agent_max_outputs"]) >= 1
    assert isinstance(body.get("reasoning_budgets"), list)
    amo = {r["key"] for r in body["agent_max_outputs"]}
    assert "agent_max_output:claude-sonnet-4" in amo  # 총 출력(①)은 adaptive 도 live — 유지
    rbk = {r["key"] for r in body["reasoning_budgets"]}
    # sonnet-reasoning-budget-guide(2026-07-24): adaptive(Sonnet 5)는 effort 로 제어 → 죽은 예산 키
    # 미노출. budget 계열(haiku)만 남고, adaptive_models 목록으로 UI 가 guide-note 를 렌더한다.
    assert "reasoning_budget:claude-haiku-4:max" in rbk
    assert "reasoning_budget:claude-sonnet-4:max" not in rbk
    mtb = {r["key"] for r in body["model_thinking_budgets"]}
    assert "model_thinking_budget:claude-sonnet-4" not in mtb
    assert "claude-sonnet-4" in body.get("adaptive_models", [])
    # opus5-model(2026-07-27): Opus 5 도 adaptive — 죽은 예산 키 미노출 + guide-note 대상으로 표면화.
    assert "agent_max_output:claude-opus-5" in amo
    assert "reasoning_budget:claude-opus-5:max" not in rbk
    assert "model_thinking_budget:claude-opus-5" not in mtb
    assert "claude-opus-5" in body.get("adaptive_models", [])
    keys = {t["key"] for t in body["timeouts"]}
    assert "AGENT_TIMEOUT_SEC" in keys and "MCP_TIMEOUT_SEC" in keys
    # 무 DB(get_conn=None) → override 없음 → effective == default.
    row = next(t for t in body["timeouts"] if t["key"] == "AGENT_TIMEOUT_SEC")
    assert row["effective"] == row["default"] and row["has_override"] is False
    # `default` 는 설계상 **배포 env 를 반영한 baseline**(serialize_registry 주석 — 운영 .env 가
    # AGENT_TIMEOUT_SEC=300 이면 300 이다). 스펙 리터럴은 별도 필드 `code_default` 이므로,
    # 상수 60 은 그쪽으로 고정한다. (종전엔 default==60 을 요구해, .env 를 상속하는 컨테이너
    # 테스트 환경에서 상시 FAIL 이었다 — 환경 의존 어서션.)
    assert row["code_default"] == 60
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
    # 검증 통과(범위 내) → conn 사용 단계. conn=None 고정이라 500(db connection failed).
    # 이는 '유효 값은 검증을 통과한다'는 것과 '검증이 conn 사용보다 먼저'임을 함께 확인한다.
    as_account(perms=WRITE_PERMS)
    resp = client.put(ENDPOINT, json={"key": "AGENT_TIMEOUT_SEC", "value": 90})
    assert resp.status_code != 400, "유효 값이 검증에서 거부되면 안 된다"
    assert resp.status_code == 500, _LIVE_WRITE_MSG.format(key="AGENT_TIMEOUT_SEC", code=resp.status_code)


def test_put_model_budget_key_validates(client, as_account):
    as_account(perms=WRITE_PERMS)
    # 상한이 모델 native−1024(haiku 62976)로 확대. native 초과만 400. (budget 계열 haiku 로 검증.)
    resp = client.put(ENDPOINT, json={"key": "model_thinking_budget:claude-haiku-4", "value": 999999})
    assert resp.status_code == 400


def test_put_model_budget_over_old_cap_now_valid(client, as_account):
    # 회귀 방향 반대 가드: 예전 16000 상한을 넘던 값(30000)이 이제 검증을 통과한다(400 아님, haiku).
    as_account(perms=WRITE_PERMS)
    resp = client.put(ENDPOINT, json={"key": "model_thinking_budget:claude-haiku-4", "value": 30000})
    assert resp.status_code != 400  # 검증 통과 → conn 단계
    assert resp.status_code == 500, _LIVE_WRITE_MSG.format(
        key="model_thinking_budget:claude-haiku-4", code=resp.status_code
    )


def test_put_adaptive_sonnet_budget_keys_rejected(client, as_account):
    # sonnet-reasoning-budget-guide(2026-07-24): adaptive(Sonnet 5) 예산 키는 스펙 제거로 미등록 →
    # 저장 시도는 400(등록되지 않은 설정 키). effort(대화별 추론 강도 선택기)로만 제어된다.
    as_account(perms=WRITE_PERMS)
    r1 = client.put(ENDPOINT, json={"key": "model_thinking_budget:claude-sonnet-4", "value": 20000})
    assert r1.status_code == 400
    r2 = client.put(ENDPOINT, json={"key": "reasoning_budget:claude-sonnet-4:max", "value": 20000})
    assert r2.status_code == 400


def test_put_per_model_reasoning_key_validates(client, as_account):
    as_account(perms=WRITE_PERMS)
    # per-model reasoning 키: haiku native−1024(62976) 초과 → 400.
    resp = client.put(ENDPOINT, json={"key": "reasoning_budget:claude-haiku-4:max", "value": 70000})
    assert resp.status_code == 400
    # 구 스킴(모델 없음) 키는 미등록 → 400(등록되지 않은 설정 키).
    resp2 = client.put(ENDPOINT, json={"key": "reasoning_budget:max", "value": 5000})
    assert resp2.status_code == 400


def test_put_agent_max_output_key_validates(client, as_account):
    as_account(perms=WRITE_PERMS)
    # 총 출력 native(sonnet 128000) 초과 → 400.
    resp = client.put(ENDPOINT, json={"key": "agent_max_output:claude-sonnet-4", "value": 200000})
    assert resp.status_code == 400
    # native 이내(100000) → 검증 통과.
    resp2 = client.put(ENDPOINT, json={"key": "agent_max_output:claude-sonnet-4", "value": 100000})
    assert resp2.status_code != 400
    assert resp2.status_code == 500, _LIVE_WRITE_MSG.format(
        key="agent_max_output:claude-sonnet-4", code=resp2.status_code
    )


# ── DELETE(초기화) RBAC + 검증 ──────────────────────────────────────────────
def test_delete_requires_write_permission(client, as_account):
    as_account(perms=READ_PERMS)
    resp = client.delete(ENDPOINT, params={"key": "AGENT_TIMEOUT_SEC"})
    assert resp.status_code == 403


def test_delete_unregistered_key_400(client, as_account):
    as_account(perms=WRITE_PERMS)
    resp = client.delete(ENDPOINT, params={"key": "BOGUS_KEY"})
    assert resp.status_code == 400


# ── audit action 등록 회귀 가드 (PB-0008 라이브 적발) ────────────────────────
# TestClient PUT/DELETE 는 make test 환경에서 conn=None 로 audit 도달 前 500 → 이 경로가
# 유닛에서 미검증이었다. build_audit_change_json 이 런타임 설정 action 을 모르면 PUT/DELETE 가
# audit 단계에서 fail-closed(rollback→500)로 깨진다(라이브에서 "unknown audit action" 실측).
def test_audit_action_system_runtime_update_registered():
    import app
    change, masked = app.build_audit_change_json(
        action="system.runtime.update", before={"value": 90}, after={"value": 120},
        request_ctx={"key": "AGENT_TIMEOUT_SEC", "value": 120},
    )
    assert change["setting_key"] == "AGENT_TIMEOUT_SEC" and change["value"] == 120 and masked == []
    assert change["previous_value"] == 90  # 감사에 직전 값 보존


def test_audit_action_system_runtime_reset_registered():
    import app
    change, masked = app.build_audit_change_json(
        action="system.runtime.reset", before={"value": 120}, after={"value": None},
        request_ctx={"key": "AGENT_TIMEOUT_SEC"},
    )
    assert change["setting_key"] == "AGENT_TIMEOUT_SEC" and masked == []
    assert change["previous_value"] == 120  # reset 이 되돌린 직전 값 보존
