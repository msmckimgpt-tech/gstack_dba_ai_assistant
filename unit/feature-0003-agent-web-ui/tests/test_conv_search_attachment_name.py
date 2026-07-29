"""대화 검색에 첨부 파일명 축 추가 회귀 테스트 (REQ-20260729-conv-search-attach-name).

요구사항:
  - 대화 검색(`/api/conversations` search mode)이 제목·본문에 더해 **첨부 원본 파일명**도 매칭한다.
  - 검색 대상 첨부는 첨부 목록과 같은 가시성(미삭제 + 버전 체인 최신)으로 한정한다.
  - 첨부 축·매칭 근거는 **첨부 조회 권한 스코프 안에서만** 작동한다(SECURITY §8.2) —
    대화 목록 권한(`conversation.list.*`)과 첨부 조회 권한은 독립 코드라, 목록 권한만으로
    축을 켜면 파일명 존재 여부가 매칭 oracle 로 새어나간다.
  - 파일명으로만 매칭된 대화가 "왜 떴는지" 알 수 있도록 응답이 매칭 파일명을 함께 싣는다.

검증(`make test` agent 이미지, 라이브 DB 무접촉 — fake 커넥션으로 **실제 SQL·params 를 캡처**):
  A1~A4 첨부 축 권한 게이트(PG)  — any / own+self / own-without-self(fail-closed) / 무권한
  A5    첨부 축 권한 게이트(MySQL 폴백) 동형
  A6    `_search_attachment_axis` 판정표(any > own > None, account 없음 포함)
  V1~V2 가시성 한정(삭제·구버전 제외) — PG·MySQL 양쪽 SQL 에 조건 존재
  G1    검색어 없는 목록 조회는 첨부 테이블을 조회하지 않는다(비용 회귀 0)
  E1~E3 LIKE escape — SECURITY §8.3 `ESCAPE '!'` + `%`/`_`/`!` 리터럴화(PG·MySQL·수집 헬퍼 정합)
  C1~C6 매칭 파일명 수집 — PG/MySQL 계약·cap·가시성·빈 입력·fail-soft
  P1~P6 엔드포인트/수집 스코프 — any=전체 / own=본인·멤버만 / 무권한=수집 미호출 /
        own 판정의 SQL 내려보내기(백엔드 무관 정합) / PG statement_timeout(§8.4)
  F1~F5 프론트 — 캐시 병합·리셋 전 지점·응답 경합 세대 가드·칩 렌더·게이트·XSS escape 경유
"""
from __future__ import annotations

import inspect
import pathlib

import app
from routers import _conv_store, _prompt_context


def _norm(text: str) -> str:
    return " ".join(str(text).split()).lower()


# ── fake DB 계층 (실행 기반 검증용) ──────────────────────────────────────────

class _FakeCursor:
    """execute() 된 (sql, params) 를 store 에 기록하고 지정 rows 를 돌려준다."""

    def __init__(self, store, rows_for):
        self._store = store
        self._rows_for = rows_for
        self._rows: list = []

    def execute(self, sql, params=None):
        if self._store.get("raise"):
            raise RuntimeError("db down")
        self._store.setdefault("executed", []).append((str(sql), params))
        self._rows = list(self._rows_for(str(sql)))

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, store, rows_for=None):
        self._store = store
        self._rows_for = rows_for or (lambda sql: [])

    def cursor(self, *a, **k):
        return _FakeCursor(self._store, self._rows_for)

    def commit(self):
        pass

    def close(self):
        self._store["closed"] = True


def _patch_pg(monkeypatch, store, rows_for=None):
    monkeypatch.setattr(app, "_runtime_backend_is_pg", lambda: True, raising=False)
    import shared.db as _sdb
    monkeypatch.setattr(
        _sdb, "_pg_connect", lambda *a, **k: _FakeConn(store, rows_for), raising=False
    )


def _run_list_pg(monkeypatch, *, q="매출", attachment_axis=None, self_id=7, has_any=False):
    """_list_conversations_pg 를 fake PG 로 실행하고 첫 execute 의 (sql, params) 반환."""
    store: dict = {}
    _patch_pg(monkeypatch, store)
    _conv_store._list_conversations_pg(
        50,
        has_any=has_any,
        self_id=self_id,
        self_username="tester",
        owner_id=None,
        hidden_ids=[],
        normalized_q=q,
        date_from=None,
        date_to=None,
        parsed_cursor=None,
        mysql_conn=None,
        attachment_axis=attachment_axis,
    )
    assert store.get("executed"), "PG 목록 쿼리가 실행되지 않았다"
    return _main_stmt(store)


def _run_list_mysql(monkeypatch, *, q="매출", account=None, self_id=7):
    """_list_conversations(MySQL 폴백)를 fake conn 으로 실행하고 첫 execute 반환."""
    store: dict = {}
    monkeypatch.delenv("AGENT_RUNTIME_READ_BACKEND", raising=False)
    monkeypatch.setattr(app, "cleanup_pending_delete_conversations", lambda c: None, raising=False)
    monkeypatch.setattr(app, "list_delete_requested_conversation_ids", lambda c: [], raising=False)
    monkeypatch.setattr(app, "_audit_message_table_collations", lambda c: None, raising=False)
    conn = _FakeConn(store)
    _conv_store._list_conversations(
        50, account=account or _account(self_id, "conversation.list.own"), conn=conn, q=q
    )
    assert store.get("executed"), "MySQL 목록 쿼리가 실행되지 않았다"
    return store["executed"][0]


def _account(acct_id: int, *perms: str) -> dict:
    return {"id": acct_id, "username": "tester", "permissions": {p: True for p in perms}}


def _main_stmt(store: dict):
    """실행된 문장 중 `SET statement_timeout` 같은 세션 설정을 빼고 본 쿼리를 고른다."""
    for sql, params in store.get("executed", []):
        if "statement_timeout" not in str(sql):
            return sql, params
    raise AssertionError("본 쿼리가 실행되지 않았다")


# 수집 헬퍼 호출부에서 쓰는 별칭 (같은 필터).
_collect_stmt = _main_stmt


# ── A: 첨부 축 권한 게이트 (SECURITY §8.2) ──────────────────────────────────

def test_a1_pg_axis_any_matches_all_conversations(monkeypatch):
    sql, params = _run_list_pg(monkeypatch, attachment_axis="any")
    n = _norm(sql)
    assert "agent_runtime.core_attachments" in n, "any 스코프면 첨부 축이 켜져야 한다"
    att = n.split("agent_runtime.core_attachments", 1)[1]
    assert "owner_account_id = %s" not in att, "any 스코프에 소유자 제한을 걸면 안 된다"


def test_a2_pg_axis_own_scopes_exists_to_owner_or_member(monkeypatch):
    # has_any=True (list.any 보유) — 기본 owner/멤버십 WHERE 가 빠지므로, 남는 self_id
    # 바인딩은 첨부 축 스코프의 것뿐이다. `list.any` 는 있고 `attachment.read.any` 는
    # 없는 계정이 정확히 이 조합이며, 본 결함(타 계정 파일명 oracle)의 실제 표적이다.
    sql, params = _run_list_pg(monkeypatch, attachment_axis="own", self_id=7, has_any=True)
    n = _norm(sql)
    assert "agent_runtime.core_attachments" in n
    att = n.split("agent_runtime.core_attachments", 1)[1]
    assert "c.owner_account_id = %s" in att, "own 스코프는 본인 소유 대화로 좁혀야 한다"
    assert "agent_runtime.conversation_members" in att, "own 스코프는 멤버 대화도 포함"
    assert params.count(7) == 2, "self_id 가 owner·멤버 조건에 각각 바인딩"


def test_a3_pg_axis_own_without_self_id_is_fail_closed(monkeypatch):
    sql, _ = _run_list_pg(monkeypatch, attachment_axis="own", self_id=None)
    assert "core_attachments" not in _norm(sql), (
        "self_id 없이 own 스코프를 확정할 수 없으면 축을 끈다(fail-closed)"
    )


def test_a4_pg_axis_none_disables_attachment_axis(monkeypatch):
    """첨부 조회 권한이 없으면 매칭 여부 자체가 파일명 oracle 이 되므로 축을 끈다."""
    sql, _ = _run_list_pg(monkeypatch, attachment_axis=None)
    n = _norm(sql)
    assert "core_attachments" not in n
    # 다른 축(제목·본문)은 그대로 살아 있어야 한다.
    assert "agent_runtime.messages" in n and "c.topic ilike" in n


def test_a5_mysql_axis_gate_mirrors_pg(monkeypatch):
    # 첨부 권한 없음 → 축 제외
    sql_none, _ = _run_list_mysql(
        monkeypatch, account=_account(7, "conversation.list.own")
    )
    assert "webconversationattachments" not in _norm(sql_none)
    # own 보유 → 축 + 소유자/멤버 스코프
    sql_own, params_own = _run_list_mysql(
        monkeypatch,
        account=_account(7, "conversation.list.own", "conversation.attachment.read.own"),
    )
    n_own = _norm(sql_own)
    assert "webconversationattachments" in n_own
    att = n_own.split("webconversationattachments", 1)[1]
    assert "c.owner_account_id = %s" in att and "agentcoreconversationmembers" in att
    assert list(params_own).count(7) >= 2
    # any 보유 → 축 + 소유자 제한 없음
    sql_any, _ = _run_list_mysql(
        monkeypatch,
        account=_account(7, "conversation.list.any", "conversation.attachment.read.any"),
    )
    att_any = _norm(sql_any).split("webconversationattachments", 1)[1]
    assert "c.owner_account_id = %s" not in att_any


def test_a6_search_attachment_axis_resolution():
    assert app._search_attachment_axis(None) is None
    assert app._search_attachment_axis(_account(1)) is None
    assert app._search_attachment_axis(_account(1, "conversation.list.any")) is None, (
        "목록 권한은 첨부 축 근거가 아니다 — 두 권한은 독립 코드"
    )
    assert app._search_attachment_axis(_account(1, "conversation.attachment.read.own")) == "own"
    assert app._search_attachment_axis(_account(1, "conversation.attachment.read.any")) == "any"
    assert app._search_attachment_axis(
        _account(1, "conversation.attachment.read.own", "conversation.attachment.read.any")
    ) == "any", "any 가 own 을 포섭"


# ── V: 가시성 한정 (첨부 목록과 동일 조건) ──────────────────────────────────

def test_v1_pg_attachment_axis_excludes_deleted_and_superseded(monkeypatch):
    sql, _ = _run_list_pg(monkeypatch, attachment_axis="any")
    att = _norm(sql).split("agent_runtime.core_attachments", 1)[1]
    assert "att.deleted_at is null" in att, "삭제된 첨부는 검색 대상 제외"
    assert "att.superseded_at is null" in att, "구버전 첨부는 검색 대상 제외(목록 정합)"


def test_v2_mysql_attachment_axis_excludes_deleted_and_superseded(monkeypatch):
    sql, _ = _run_list_mysql(
        monkeypatch,
        account=_account(7, "conversation.list.own", "conversation.attachment.read.own"),
    )
    att = _norm(sql).split("webconversationattachments", 1)[1]
    assert "att.deletedat is null" in att and "att.supersededat is null" in att


# ── G: 비용 회귀 가드 ────────────────────────────────────────────────────────

def test_g1_no_query_means_no_attachment_join(monkeypatch):
    """검색어 없는 일반 목록 조회는 첨부 테이블을 건드리지 않는다."""
    sql_pg, _ = _run_list_pg(monkeypatch, q=None, attachment_axis="any")
    assert "core_attachments" not in _norm(sql_pg)
    sql_my, _ = _run_list_mysql(
        monkeypatch,
        q=None,
        account=_account(7, "conversation.list.any", "conversation.attachment.read.any"),
    )
    assert "webconversationattachments" not in _norm(sql_my)


# ── E: LIKE escape (SECURITY §8.3) ──────────────────────────────────────────

def test_e1_pg_search_escapes_like_wildcards(monkeypatch):
    """PG 경로도 `ESCAPE '!'` + `%`/`_` 리터럴화 — AR-M4 포팅 때 유실됐던 §8.3 계약."""
    sql, params = _run_list_pg(monkeypatch, q="a%b_c", attachment_axis="any")
    n = _norm(sql)
    assert "escape '!'" in n, "PG ILIKE 도 ESCAPE '!' 를 써야 한다"
    assert "%a!%b!_c%" in [p for p in params if isinstance(p, str)], (
        "검색어의 %/_ 가 리터럴로 escape 되어야 한다"
    )


def test_e2_mysql_search_escapes_like_wildcards(monkeypatch):
    sql, params = _run_list_mysql(
        monkeypatch,
        q="a%b_c",
        account=_account(7, "conversation.list.own", "conversation.attachment.read.own"),
    )
    assert "escape '!'" in _norm(sql)
    assert "%a!%b!_c%" in [p for p in params if isinstance(p, str)]


def test_e3_collect_helper_uses_same_escape(monkeypatch):
    """수집 헬퍼와 검색 절의 escape semantics 가 어긋나면 근거 칩만 조용히 빈다."""
    store: dict = {}
    _patch_pg(monkeypatch, store)
    _prompt_context._collect_matched_attachment_names(None, ["c1"], "a%b_c")
    sql, params = _collect_stmt(store)
    assert "escape '!'" in _norm(sql)
    assert "%a!%b!_c%" in [p for p in params if isinstance(p, str)]


# ── C: 매칭 파일명 수집 헬퍼 ────────────────────────────────────────────────

def test_c1_collect_pg_groups_names_by_conversation(monkeypatch):
    store: dict = {}
    _patch_pg(monkeypatch, store, rows_for=lambda sql: [
        ("conv-a", "매출_2026.xlsx"),
        ("conv-a", "매출_요약.csv"),
        ("conv-b", "매출계획.pdf"),
    ])
    out = _prompt_context._collect_matched_attachment_names(None, ["conv-a", "conv-b"], "매출")
    assert out == {
        "conv-a": ["매출_2026.xlsx", "매출_요약.csv"],
        "conv-b": ["매출계획.pdf"],
    }
    assert store.get("closed") is True, "PG 연결은 항상 닫힌다"


def test_c2_collect_mysql_path(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(app, "_runtime_backend_is_pg", lambda: False, raising=False)
    conn = _FakeConn(store, rows_for=lambda sql: [("conv-a", "설계서.docx")])
    out = _prompt_context._collect_matched_attachment_names(conn, ["conv-a"], "설계")
    assert out == {"conv-a": ["설계서.docx"]}
    assert "webconversationattachments" in _norm(_collect_stmt(store)[0])


def test_c3_collect_sql_limits_visibility_and_caps(monkeypatch):
    store: dict = {}
    _patch_pg(monkeypatch, store)
    _prompt_context._collect_matched_attachment_names(None, ["conv-a"], "매출", per_conv_cap=2)
    sql, params = _collect_stmt(store)
    n = _norm(sql)
    assert "att.deleted_at is null" in n and "att.superseded_at is null" in n
    assert "row_number() over" in n and "t.rn <= %s" in n, "conv 당 상한 필요"
    assert params[-1] == 2, "per_conv_cap 이 파라미터로 전달"
    assert "order by att.created_at desc" in n, "최신 첨부 우선"


def test_c4_collect_empty_inputs_short_circuit(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(app, "_runtime_backend_is_pg", lambda: False, raising=False)
    conn = _FakeConn(store, rows_for=lambda sql: [("conv-a", "x.txt")])
    assert _prompt_context._collect_matched_attachment_names(conn, [], "매출") == {}
    assert _prompt_context._collect_matched_attachment_names(conn, ["conv-a"], "") == {}
    assert "executed" not in store, "빈 입력은 쿼리를 실행하지 않는다"


def test_c5_collect_fail_soft_on_db_error(monkeypatch):
    store: dict = {"raise": True}
    monkeypatch.setattr(app, "_runtime_backend_is_pg", lambda: False, raising=False)
    assert _prompt_context._collect_matched_attachment_names(
        _FakeConn(store), ["conv-a"], "매출"
    ) == {}


def test_c6_collect_fail_soft_on_cursor_creation_error(monkeypatch):
    """헬퍼 경계 전체가 fail-soft — 커서 생성 실패도 빈 dict."""
    monkeypatch.setattr(app, "_runtime_backend_is_pg", lambda: False, raising=False)

    class _BadConn:
        def cursor(self, *a, **k):
            raise RuntimeError("no cursor")

    assert _prompt_context._collect_matched_attachment_names(_BadConn(), ["c1"], "q") == {}


# ── P: 엔드포인트 스코프 (권한별 matched_attachments) ────────────────────────

def _call_search_endpoint(monkeypatch, account, items):
    """conversations 엔드포인트를 호출하고 (payload, 수집에 넘어간 conv_ids) 반환."""
    from routers import conversations as conv_router
    import json

    seen: dict = {}
    monkeypatch.setattr(app, "_list_conversations", lambda **kw: items, raising=False)
    monkeypatch.setattr(app, "_collect_matched_excerpts", lambda *a, **k: {}, raising=False)
    monkeypatch.setattr(app, "_search_rate_limit_check", lambda *a, **k: True, raising=False)
    monkeypatch.setattr(app, "_log_search_activity", lambda *a, **k: None, raising=False)

    def _spy(conn, conv_ids, q, **kw):
        seen["conv_ids"] = list(conv_ids)
        seen["scope_account_id"] = kw.get("scope_account_id")
        # SQL 스코프를 시뮬레이트 — own 스코프면 본인 소유·멤버 대화만 근거를 돌려준다.
        scope = kw.get("scope_account_id")
        out = {}
        for it in items:
            cid = str(it.get("id"))
            if cid not in conv_ids:
                continue
            if scope is not None and not (
                it.get("owner_account_id") == scope or it.get("is_member")
            ):
                continue
            out[cid] = ["f.xlsx"]
        return out

    monkeypatch.setattr(app, "_collect_matched_attachment_names", _spy, raising=False)

    resp = conv_router.conversations(
        request=None, q="매출", account=account, conn=_FakeConn({})
    )
    return json.loads(bytes(resp.body).decode("utf-8")), seen


def _endpoint_scope_arg(monkeypatch, account):
    _, seen = _call_search_endpoint(monkeypatch, account, _ITEMS)
    return seen


_ITEMS = [
    {"id": "own-1", "owner_account_id": 7, "is_member": False},
    {"id": "member-1", "owner_account_id": 99, "is_member": True},
    {"id": "other-1", "owner_account_id": 99, "is_member": False},
]


def test_p1_endpoint_any_scope_collects_all(monkeypatch):
    payload, seen = _call_search_endpoint(
        monkeypatch,
        _account(7, "conversation.list.any", "conversation.attachment.read.any"),
        _ITEMS,
    )
    assert seen["conv_ids"] == ["own-1", "member-1", "other-1"]
    assert set(payload["matched_attachments"]) == {"own-1", "member-1", "other-1"}


def test_p2_endpoint_own_scope_excludes_foreign_conversations(monkeypatch):
    """`list.any` 는 있으나 `attachment.read.any` 가 없는 계정 — 타 계정 파일명 미노출."""
    payload, seen = _call_search_endpoint(
        monkeypatch,
        _account(7, "conversation.list.any", "conversation.attachment.read.own"),
        _ITEMS,
    )
    assert set(payload["matched_attachments"]) == {"own-1", "member-1"}, "본인 소유·멤버 대화만"
    assert "other-1" not in payload["matched_attachments"], "타 계정 대화 파일명 미노출"


def test_p3_endpoint_without_attachment_permission_collects_nothing(monkeypatch):
    payload, seen = _call_search_endpoint(
        monkeypatch, _account(7, "conversation.list.any"), _ITEMS
    )
    assert seen.get("conv_ids") is None, "수집 자체를 호출하지 않는다"
    assert payload["matched_attachments"] == {}


def test_p4_own_scope_is_pushed_into_sql_not_item_fields(monkeypatch):
    """`own` 스코프 판정은 SQL(scope_account_id)로 내려간다.

    items 의 `owner_account_id`/`is_member` 로 거르면, 그 필드를 채우지 않는 백엔드
    (MySQL 폴백 경로 — PG 경로만 is_member 를 싣는다)에서 멤버 대화의 근거가 조용히 빈다.
    """
    seen = _endpoint_scope_arg(
        monkeypatch, _account(7, "conversation.list.any", "conversation.attachment.read.own")
    )
    assert seen["scope_account_id"] == 7, "own 스코프는 SQL 파라미터로 전달"
    assert seen["conv_ids"] == ["own-1", "member-1", "other-1"], (
        "conv_ids 를 미리 거르지 않고 SQL 이 좁힌다(백엔드 무관 정합)"
    )
    seen_any = _endpoint_scope_arg(
        monkeypatch, _account(7, "conversation.list.any", "conversation.attachment.read.any")
    )
    assert seen_any["scope_account_id"] is None, "any 스코프는 SQL 제한 없음"


def test_p5_collect_helper_applies_scope_in_sql(monkeypatch):
    """수집 SQL 이 scope_account_id 를 owner/멤버 조건으로 실제 조립하는지."""
    store: dict = {}
    _patch_pg(monkeypatch, store)
    _prompt_context._collect_matched_attachment_names(
        None, ["c1"], "매출", scope_account_id=7
    )
    sql, params = _collect_stmt(store)
    n = _norm(sql)
    assert "join agent_runtime.core_conversations c" in n, "소유자 판정을 위해 대화 조인"
    assert "c.owner_account_id = %s" in n and "agent_runtime.conversation_members" in n
    assert list(params).count(7) == 2

    store2: dict = {}
    _patch_pg(monkeypatch, store2)
    _prompt_context._collect_matched_attachment_names(None, ["c1"], "매출")
    n2 = _norm(_collect_stmt(store2)[0])
    assert "c.owner_account_id = %s" not in n2, "scope 미지정(any)은 소유자 제한 없음"


def test_p6_pg_search_paths_set_statement_timeout(monkeypatch):
    """§8.4 runaway 방어 — MySQL 전용 `max_execution_time` 과 별개로 PG 도 상한을 건다."""
    store: dict = {}
    _patch_pg(monkeypatch, store)
    _conv_store._list_conversations_pg(
        50, has_any=True, self_id=7, self_username="t", owner_id=None, hidden_ids=[],
        normalized_q="매출", date_from=None, date_to=None, parsed_cursor=None,
        mysql_conn=None, attachment_axis="any",
    )
    assert any("statement_timeout" in s for s, _ in store["executed"]), (
        "PG 목록 검색에 statement_timeout 미설정"
    )

    store2: dict = {}
    _patch_pg(monkeypatch, store2)
    _prompt_context._collect_matched_attachment_names(None, ["c1"], "매출")
    assert any("statement_timeout" in s for s, _ in store2["executed"]), (
        "PG 수집 쿼리에 statement_timeout 미설정"
    )

    # 검색어 없는 목록 조회에는 굳이 걸지 않는다(검색 경로 한정).
    store3: dict = {}
    _patch_pg(monkeypatch, store3)
    _conv_store._list_conversations_pg(
        50, has_any=True, self_id=7, self_username="t", owner_id=None, hidden_ids=[],
        normalized_q=None, date_from=None, date_to=None, parsed_cursor=None,
        mysql_conn=None, attachment_axis="any",
    )
    assert not any("statement_timeout" in s for s, _ in store3["executed"])


# ── F: 프론트 계약 ──────────────────────────────────────────────────────────

def _app_js() -> str:
    return (
        pathlib.Path(__file__).resolve().parents[1] / "src" / "static" / "app.js"
    ).read_text(encoding="utf-8")


def test_f1_frontend_caches_and_merges_attachment_matches():
    js = _app_js()
    assert "sm.matched_attachments = append" in js, "더 보기(append) 시 병합"
    # excerpt 캐시가 리셋되는 모든 지점에서 첨부 캐시도 함께 리셋되어야 stale 근거가 안 남는다.
    assert js.count("matched_excerpts = {}") == js.count("matched_attachments = {}"), (
        "캐시 리셋 지점이 excerpt 와 1:1 대응해야 한다(누락 시 이전 검색의 파일명 칩이 잔존)"
    )


def test_f2_attachment_chip_render_and_visibility_gate():
    js = _app_js()
    assert "search-attach-chip" in js, "결과 행에 첨부 파일명 칩 렌더"
    assert "(mine || sm.snippet_opt_in)" in js, (
        "본인 대화는 항상, 타 계정 대화는 opt-in 게이트 (SECURITY §8.6)"
    )


def test_f3_attachment_chip_escapes_filename():
    """파일명은 사용자 입력 — 반드시 escapeHtml 을 거치는 _searchHighlight 로만 주입."""
    js = _app_js()
    chunk = js.split("search-attach-matches", 1)[1].split("row.appendChild(wrap)", 1)[0]
    assert "_searchHighlight(String(fname)" in chunk, "파일명은 escape 경유로만 innerHTML 주입"
    assert "innerHTML = fname" not in chunk and "innerHTML = String(fname)" not in chunk
    # _searchHighlight 자체가 escapeHtml 을 먼저 적용하는지 고정.
    hl = js.split("function _searchHighlight", 1)[1][:400]
    assert "escapeHtml(String(text" in hl


def test_f5_search_response_race_guard():
    """늦게 도착한 이전 응답이 새 검색 결과·근거 칩을 덮어쓰지 않는다(세대 토큰)."""
    js = _app_js()
    body = js.split("async function runSearchQuery", 1)[1].split("\nfunction ", 1)[0]
    assert "sm.requestGen" in body, "요청 세대 토큰 부재"
    assert body.count("gen !== sm.requestGen") >= 2, (
        "성공·실패 양 경로 모두에서 세대를 확인해야 한다"
    )


def test_f4_search_copy_mentions_attachment_axis():
    js = _app_js()
    html = (
        pathlib.Path(__file__).resolve().parents[1] / "src" / "static" / "index.html"
    ).read_text(encoding="utf-8")
    assert "첨부 파일명" in html, "검색 입력 placeholder 가 새 축을 알린다"
    assert "첨부 파일명" in js, "빈 상태 안내도 정합"


# ── 구조 가드 (실행 검증이 못 잡는 배치 계약) ────────────────────────────────

def test_axis_computed_once_as_single_source():
    """축 판정이 목록 SQL·수집 양쪽에서 같은 헬퍼를 쓰는지(판정 분기 중복 방지)."""
    assert "_search_attachment_axis" in inspect.getsource(_conv_store._list_conversations)
    from routers import conversations as conv_router
    assert "_search_attachment_axis" in inspect.getsource(conv_router.conversations)
