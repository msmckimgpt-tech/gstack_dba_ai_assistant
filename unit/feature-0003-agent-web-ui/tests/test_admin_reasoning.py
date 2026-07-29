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


# ── 대화 단위 그룹 페이징 + 회차 원장 (feature-0021, 2026-07-29) ─────────────
# 콘솔이 "각 대화의 마지막 리뷰만" 보이던 원인은 두 겹이었다: (a) 회차 원장 부재(요약 1행),
# (b) 리뷰를 flat id DESC 로만 내려 같은 대화가 목록 곳곳에 흩어짐. 아래는 (b) 의 정렬·
# 그룹 계약과 (a) 의 동봉을 DB 없이 fake cursor 로 고정한다.

def test_redteam_response_exposes_conversation_grouping_fields(client, as_account):
    as_account(perms=REVIEW_PERMS)
    body = client.get(REDTEAM).json()
    assert isinstance(body.get("conversations"), list)
    # 회차 원장 가용 여부는 목록 가용성과 별개 플래그(0048 미적용 이미지 폴백 신호).
    assert "rounds_available" in body
    assert body.get("per_conversation_cap")


class _FakeCursor:
    """execute 순서대로 준비된 결과를 돌려주는 최소 스텁 (psycopg cursor 대역)."""

    def __init__(self, results):
        self._results = list(results)
        self.sqls = []
        self._rows = []

    def execute(self, sql, params=None):
        self.sqls.append(" ".join(sql.split()))
        self._rows = self._results.pop(0) if self._results else []

    def fetchall(self):
        return self._rows


def _review_row(rid, cid, created="2026-07-29T00:00:00"):
    import datetime as _dt
    return (rid, cid, f"run-{rid}", "pass", None, 0, 0, None, False, "m", 10,
            "normal", False, _dt.datetime.fromisoformat(created))


def test_conversation_page_orders_conversations_desc_and_reviews_asc():
    from routers import admin_reasoning as ar
    import datetime as _dt

    groups = [
        ("conv-new", 9, _dt.datetime(2026, 7, 29, 12, 0, 0), 2),
        ("conv-old", 4, _dt.datetime(2026, 7, 28, 9, 0, 0), 1),
    ]
    reviews = [_review_row(3, "conv-new"), _review_row(4, "conv-old"), _review_row(9, "conv-new")]
    cur = _FakeCursor([groups, reviews])
    items, conversations, next_cursor = ar._query_conversation_page(
        cur, cursor=None, conv_limit=10, per_conv_cap=20)

    # 대화 = 최근 리뷰 순 desc, 대화 내 리뷰 = 진행 순서 asc.
    assert [c["conversation_id"] for c in conversations] == ["conv-new", "conv-old"]
    assert [it["id"] for it in items] == [3, 9, 4]
    assert next_cursor is None  # 그룹 수가 limit 이하 → 다음 페이지 없음
    assert conversations[0]["review_count"] == 2 and conversations[0]["capped"] is False


def test_conversation_page_cursor_and_has_more():
    from routers import admin_reasoning as ar
    import datetime as _dt

    # conv_limit=1 인데 그룹이 2개 → has_more, next_cursor = 반환된 마지막 그룹의 last_id.
    groups = [("conv-a", 9, _dt.datetime(2026, 7, 29), 1), ("conv-b", 4, _dt.datetime(2026, 7, 28), 1)]
    cur = _FakeCursor([groups, [_review_row(9, "conv-a")]])
    items, conversations, next_cursor = ar._query_conversation_page(
        cur, cursor=None, conv_limit=1, per_conv_cap=20)
    assert len(conversations) == 1 and next_cursor == 9
    assert [it["id"] for it in items] == [9]
    # cursor 를 준 호출은 그룹 keyset(HAVING MAX(id) < cursor)을 태운다.
    cur2 = _FakeCursor([[], []])
    ar._query_conversation_page(cur2, cursor=9, conv_limit=1, per_conv_cap=20)
    assert "HAVING MAX(id) < %s" in cur2.sqls[0]


def test_conversation_page_marks_capped_group():
    from routers import admin_reasoning as ar
    import datetime as _dt

    groups = [("conv-a", 9, _dt.datetime(2026, 7, 29), 30)]  # 총 30건인데 1건만 반환
    cur = _FakeCursor([groups, [_review_row(9, "conv-a")]])
    _items, conversations, _nc = ar._query_conversation_page(
        cur, cursor=None, conv_limit=10, per_conv_cap=1)
    assert conversations[0]["capped"] is True
    assert conversations[0]["review_count"] == 30 and conversations[0]["returned_count"] == 1


def test_attach_rounds_orders_by_round_index_asc():
    from routers import admin_reasoning as ar
    import datetime as _dt

    items = [{"id": 5, "rounds": []}]
    rows = [
        (5, 0, "review", "revise", [{"axis": "sql", "severity": "BLOCK"}], 1, 0,
         None, None, 0, 100, None, _dt.datetime(2026, 7, 29)),
        (5, 1, "revise", None, None, 0, 0, "rederive", "sql", 2, 120, None,
         _dt.datetime(2026, 7, 29)),
        (5, 1, "verify", "pass", [], 0, 0, None, None, 0, 120, None, _dt.datetime(2026, 7, 29)),
    ]
    cur = _FakeCursor([rows])
    assert ar._attach_rounds(cur, items) is True
    rounds = items[0]["rounds"]
    assert [(r["round_index"], r["phase"]) for r in rounds] == [
        (0, "review"), (1, "revise"), (1, "verify")]
    assert rounds[1]["revise_method"] == "rederive" and rounds[1]["tool_rounds"] == 2
    assert "ORDER BY review_id, round_index, id" in cur.sqls[0]


def test_conversation_page_covers_blank_conversation_ids():
    """NULL 과 빈 문자열은 Q1 이 같은 그룹으로 묶으므로 Q2 도 둘 다 조회해야 한다.

    (codex 리뷰 P2) 빈 문자열을 `IS NULL` 로만 조회하면 그 행이 items 에서 빠져
    conversations[].returned_count/capped 가 사실과 어긋난다."""
    from routers import admin_reasoning as ar
    import datetime as _dt

    groups = [("", 8, _dt.datetime(2026, 7, 29), 2)]
    rows = [_review_row(7, ""), _review_row(8, None)]
    cur = _FakeCursor([groups, rows])
    items, conversations, _nc = ar._query_conversation_page(
        cur, cursor=None, conv_limit=10, per_conv_cap=20)
    assert "conversation_id = ''" in cur.sqls[1]
    assert [it["id"] for it in items] == [7, 8]
    assert conversations[0]["returned_count"] == 2 and conversations[0]["capped"] is False


def test_attach_rounds_caps_per_review_and_flags_truncation():
    """회차 폭증(하드 백스톱 50 라운드) 시 응답이 부풀지 않도록 상한 + 절단 표시."""
    from routers import admin_reasoning as ar
    import datetime as _dt

    cap = ar._PER_REVIEW_ROUND_CAP
    rows = [(5, i, "verify", "pass", [], 0, 0, None, None, 0, 100, None,
             _dt.datetime(2026, 7, 29)) for i in range(cap + 5)]
    items = [{"id": 5, "rounds": []}]
    cur = _FakeCursor([rows])
    ar._attach_rounds(cur, items)
    assert len(items[0]["rounds"]) == cap
    assert items[0]["rounds_truncated"] is True
    # 상한 이하이면 절단 표시가 붙지 않는다.
    items2 = [{"id": 6, "rounds": []}]
    cur2 = _FakeCursor([[(6, 0, "review", "pass", [], 0, 0, None, None, 0, 10, None,
                          _dt.datetime(2026, 7, 29))]])
    ar._attach_rounds(cur2, items2)
    assert items2[0]["rounds_truncated"] is False
