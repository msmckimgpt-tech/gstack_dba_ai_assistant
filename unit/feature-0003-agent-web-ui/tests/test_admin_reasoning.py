"""feature-0021 — 관리 콘솔 `AI 추론` 조회 API RBAC/degrade 테스트.

TestClient + as_account(conftest) 로 require_permission 게이트를 실제로 태운다(RP 패턴).
make test 환경(--no-deps): PG 미가용 → redteam 활동은 pg_available=false 부분 degrade,
notes 는 /shared 부재 → 빈 목록. 실데이터 왕복은 라이브 통합 QA(PB-0008) 로 검증한다.
런타임 설정 REDTEAM_* 스펙 노출은 GET /api/admin/settings/runtime 의 redteam 그룹으로 검증.
"""
from __future__ import annotations

READ_PERMS = {"console.access": True, "console.reasoning.read": True}

GUIDANCE = "/api/admin/reasoning/guidance"
REDTEAM = "/api/admin/reasoning/redteam"
NOTES = "/api/admin/reasoning/notes"


# ── RBAC (3 endpoint 공통) ──────────────────────────────────────────────────
def test_endpoints_require_permission(client, as_account):
    as_account(perms={"console.access": True})  # console.reasoning.read 없음
    for ep in (GUIDANCE, REDTEAM, NOTES):
        assert client.get(ep).status_code == 403, ep


def test_endpoints_anonymous_401(client, as_anonymous):
    as_anonymous()
    for ep in (GUIDANCE, REDTEAM, NOTES):
        assert client.get(ep).status_code == 401, ep


# ── guidance (progressive disclosure) ───────────────────────────────────────
def test_guidance_list_meta_only(client, as_account):
    as_account(perms=READ_PERMS)
    resp = client.get(GUIDANCE)
    assert resp.status_code == 200
    body = resp.json()
    items = body.get("items") or []
    assert len(items) >= 5
    keys = {it["key"] for it in items}
    assert "redteam-review" in keys and "active-interpretation" in keys
    # progressive disclosure: 목록엔 본문(text) 없음.
    assert all("text" not in it for it in items)
    kinds = {it["kind"] for it in items}
    assert "guidance" in kinds
    # 스킬(도구) 카탈로그 동반 노출 (execute_sql 등).
    assert any(it["key"].startswith("tool:") for it in items)


def test_guidance_detail_returns_text(client, as_account):
    as_account(perms=READ_PERMS)
    resp = client.get(GUIDANCE + "?key=redteam-review")
    assert resp.status_code == 200
    item = resp.json().get("item") or {}
    assert item.get("key") == "redteam-review"
    assert "adversarial" in (item.get("text") or "")


def test_guidance_unknown_key_404(client, as_account):
    as_account(perms=READ_PERMS)
    assert client.get(GUIDANCE + "?key=no-such-key").status_code == 404


# ── redteam 활동 (PG 미가용 부분 degrade) ───────────────────────────────────
def test_redteam_degrades_without_pg(client, as_account):
    as_account(perms=READ_PERMS)
    resp = client.get(REDTEAM)
    assert resp.status_code == 200  # 503 아님 — ai-ops 부분 degrade 규약
    body = resp.json()
    assert isinstance(body.get("items"), list)
    assert "pg_available" in body
    # table 부재/PG 부재를 "리뷰 없음"과 구분하는 플래그 (마이그 전 stale image 함정 대비).
    assert "table_available" in body


def test_redteam_cursor_param_tolerant(client, as_account):
    as_account(perms=READ_PERMS)
    assert client.get(REDTEAM + "?cursor=abc&limit=9999").status_code == 200


# ── notes 현황 ───────────────────────────────────────────────────────────────
def test_notes_empty_without_volume(client, as_account):
    as_account(perms=READ_PERMS)
    resp = client.get(NOTES)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("items"), list)
    assert set(body.get("ttl_days") or {}) == {"session", "product"}


# ── 런타임 설정 redteam 그룹 노출 ────────────────────────────────────────────
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
