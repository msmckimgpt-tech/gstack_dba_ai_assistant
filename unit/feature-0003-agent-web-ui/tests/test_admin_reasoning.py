"""feature-0021 — 관리 콘솔 AI 추론 조회 API RBAC/degrade 테스트.

console-ia(2026-07-16) IA 재구성 반영:
- 리뷰 활동/노트(`/redteam`·`/notes`) = 감사 카테고리 권한 `console.reasoning.read`.
- 작동 지침/스킬(`/guidance`) = 설정>프롬프트, `system_prompt.global.read` 재사용 + ?kind 필터.
- 기본 시스템 프롬프트 fallback(system-prompt-base)은 작동 지침 목록에서 제외(편집 정본 단일화).

TestClient + as_account(conftest) 로 require_permission 게이트를 실제로 태운다(RP 패턴).
make test(--no-deps): PG 미가용 → redteam 부분 degrade, notes 는 /shared 부재 → 빈 목록.
"""
from __future__ import annotations

REVIEW_PERMS = {"console.access": True, "console.reasoning.read": True}
PROMPT_PERMS = {"console.access": True, "system_prompt.global.read": True}

GUIDANCE = "/api/admin/reasoning/guidance"
REDTEAM = "/api/admin/reasoning/redteam"
NOTES = "/api/admin/reasoning/notes"


# ── RBAC 분리 (guidance=프롬프트 권한, redteam/notes=감사 권한) ──────────────
def test_review_notes_require_reasoning_permission(client, as_account):
    as_account(perms={"console.access": True})  # console.reasoning.read 없음
    for ep in (REDTEAM, NOTES):
        assert client.get(ep).status_code == 403, ep


def test_guidance_requires_prompt_permission(client, as_account):
    as_account(perms={"console.access": True})  # system_prompt.global.read 없음
    assert client.get(GUIDANCE).status_code == 403


def test_guidance_denied_with_only_reasoning_perm(client, as_account):
    # 감사 권한만으로는 지침/스킬(프롬프트) 조회 불가 — 권한 분리 확인.
    as_account(perms=REVIEW_PERMS)
    assert client.get(GUIDANCE).status_code == 403


def test_review_denied_with_only_prompt_perm(client, as_account):
    # 프롬프트 권한만으로는 리뷰 활동 조회 불가.
    as_account(perms=PROMPT_PERMS)
    assert client.get(REDTEAM).status_code == 403


def test_endpoints_anonymous_401(client, as_anonymous):
    as_anonymous()
    for ep in (GUIDANCE, REDTEAM, NOTES):
        assert client.get(ep).status_code == 401, ep


# ── guidance (progressive disclosure + kind 필터 + fallback 제외) ───────────
def test_guidance_list_meta_only(client, as_account):
    as_account(perms=PROMPT_PERMS)
    resp = client.get(GUIDANCE)
    assert resp.status_code == 200
    body = resp.json()
    items = body.get("items") or []
    assert len(items) >= 5
    keys = {it["key"] for it in items}
    assert "redteam-review" in keys and "active-interpretation" in keys
    # console-ia: 기본 시스템 프롬프트 fallback 은 작동 지침 목록에서 제외(전역 시스템 프롬프트가 정본).
    assert "system-prompt-base" not in keys
    # progressive disclosure: 목록엔 본문(text) 없음.
    assert all("text" not in it for it in items)
    # 스킬(도구) 카탈로그 동반 노출 (execute_sql 등).
    assert any(it["key"].startswith("tool:") for it in items)


def test_guidance_kind_filter(client, as_account):
    as_account(perms=PROMPT_PERMS)
    g = client.get(GUIDANCE + "?kind=guidance").json().get("items") or []
    s = client.get(GUIDANCE + "?kind=skill").json().get("items") or []
    assert g and all(it["kind"] == "guidance" for it in g)
    assert s and all(it["kind"] == "skill" for it in s)
    assert all(it["key"].startswith("tool:") for it in s)


def test_guidance_detail_returns_text(client, as_account):
    as_account(perms=PROMPT_PERMS)
    resp = client.get(GUIDANCE + "?key=redteam-review")
    assert resp.status_code == 200
    item = resp.json().get("item") or {}
    assert item.get("key") == "redteam-review"
    assert "adversarial" in (item.get("text") or "")


def test_guidance_unknown_key_404(client, as_account):
    as_account(perms=PROMPT_PERMS)
    assert client.get(GUIDANCE + "?key=no-such-key").status_code == 404


# ── redteam 활동 (PG 미가용 부분 degrade) ───────────────────────────────────
def test_redteam_degrades_without_pg(client, as_account):
    as_account(perms=REVIEW_PERMS)
    resp = client.get(REDTEAM)
    assert resp.status_code == 200  # 503 아님 — ai-ops 부분 degrade 규약
    body = resp.json()
    assert isinstance(body.get("items"), list)
    assert "pg_available" in body
    # table 부재/PG 부재를 "리뷰 없음"과 구분하는 플래그 (마이그 전 stale image 함정 대비).
    assert "table_available" in body


def test_redteam_cursor_param_tolerant(client, as_account):
    as_account(perms=REVIEW_PERMS)
    assert client.get(REDTEAM + "?cursor=abc&limit=9999").status_code == 200


# ── notes 현황 ───────────────────────────────────────────────────────────────
def test_notes_empty_without_volume(client, as_account):
    as_account(perms=REVIEW_PERMS)
    resp = client.get(NOTES)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("items"), list)
    assert set(body.get("ttl_days") or {}) == {"session", "product"}


# ── 런타임 설정 redteam 그룹 노출 (설정>운영 값>AI 자가 리뷰 — 무변경) ──────
def test_runtime_settings_expose_redteam_group(client, as_account):
    as_account(perms={"console.access": True, "system.runtime.read": True})
    resp = client.get("/api/admin/settings/runtime")
    assert resp.status_code == 200
    rows = resp.json().get("redteam") or []
    keys = {r["key"] for r in rows}
    assert {"REDTEAM_ENABLED", "REDTEAM_MIN_LEVEL", "REDTEAM_MAX_REVISIONS",
            "REDTEAM_NOTES_SESSION_TTL_DAYS", "REDTEAM_NOTES_INJECT_MAX_CHARS"} <= keys
    enabled = next(r for r in rows if r["key"] == "REDTEAM_ENABLED")
    assert enabled["effective"] == 1 and enabled["apply_mode"] == "live"
