"""공유 대화 첨부 스코프 게이트(`shared.share_window`) 계약 고정.

FR-group-attach-sender-scope-blocks-members (2026-08-13 사용자 결정): 그룹 대화의 첨부 LLM
스코프를 "발신자 본인" → "대화 전체" 로 넓히되, 공유창 window(docs/SECURITY.md §21·§47)로
**가려진 표시 메시지가 실재하는 발신자**에게는 확대를 적용하지 않는다(fail-closed).

이 게이트는 web 의 스코프 해소(`_resolve_conversation_attachment_scope`)와 agent_core 의 주입
게이트가 **함께** 쓰는 단일 정본이라, 규칙이 흔들리면 두 경계가 조용히 갈린다. 그룹 여부까지
게이트가 판정한다 — 호출측이 `_is_group_conversation()` 으로 선-게이팅하면 그 함수가 PG 오류 시
False 를 돌려 게이트를 통째로 건너뛰는 fail-open 이 된다(§18.8 적대 리뷰 [P1]).
"""
from __future__ import annotations

import pytest

import shared.share_window as sw


class _FakeCursor:
    def __init__(self, row, exc=None):
        self._row = row
        self._exc = exc

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        if self._exc is not None:
            raise self._exc

    def fetchone(self):
        return self._row


class _FakePg:
    def __init__(self, row, exc=None):
        self._row = row
        self._exc = exc
        self.closed = False

    def cursor(self):
        return _FakeCursor(self._row, self._exc)

    def close(self):
        self.closed = True


def _with_pg(monkeypatch, row, exc=None, connect_exc=None):
    """PG 백엔드 활성 + `shared.db._pg_connect` 대체."""
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    import shared.db as _db

    def _connect():
        if connect_exc is not None:
            raise connect_exc
        return _FakePg(row, exc)

    monkeypatch.setattr(_db, "_pg_connect", _connect, raising=False)


def _row(*, is_owner=False, members=2, role="member", floor=None, ceiling=None, hidden=0):
    """게이트 쿼리 반환 형태: (is_owner, member_count, role, floor_id, ceiling_id, hidden_after_ceiling)."""
    return (is_owner, members, role, floor, ceiling, hidden)


# ── 게이트를 아예 태우지 않는 경로 ──────────────────────────────────────────

def test_non_pg_backend_does_not_restrict(monkeypatch):
    """멤버십·window 는 PG 런타임에서만 생성된다 — 비-PG 는 1:1 과 동치."""
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "mysql")
    assert sw.group_attachment_scope("conv-1", 7) == sw.SCOPE_CONVERSATION


def test_missing_identifiers_fail_closed(monkeypatch):
    """대화/발신자를 모르면 확대하지 않는다(시스템·CLI 호출 포함)."""
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    assert sw.group_attachment_scope(None, 7) == sw.SCOPE_SENDER_ONLY
    assert sw.group_attachment_scope("conv-1", None) == sw.SCOPE_SENDER_ONLY


# ── 그룹 판정(게이트가 직접 한다 — fail-open 차단) ──────────────────────────

def test_non_group_conversation_is_full_scope(monkeypatch):
    """멤버 ≤ 1 이면 그룹이 아니다 — 1:1·fork·이어받기는 종전 대화 스코프 그대로(무회귀)."""
    _with_pg(monkeypatch, _row(members=1, role=None))
    assert sw.group_attachment_scope("conv-1to1", 7) == sw.SCOPE_CONVERSATION

    _with_pg(monkeypatch, _row(members=0, role=None))
    assert sw.group_attachment_scope("conv-fork", 7) == sw.SCOPE_CONVERSATION


def test_group_membership_gap_is_sender_only(monkeypatch):
    """그룹인데 발신자의 멤버 행이 없으면 좁힌다.

    멤버십 게이트는 호출자 책임이지만, 여기서 넓히면 그 게이트의 구멍이 곧 첨부 노출이 된다
    (§18.8 적대 리뷰 [P2] — LEFT JOIN NULL 경로).
    """
    _with_pg(monkeypatch, _row(is_owner=False, members=3, role=None))
    assert sw.group_attachment_scope("conv-group", 99) == sw.SCOPE_SENDER_ONLY


def test_owner_gets_full_scope(monkeypatch):
    """소유자는 본인 대화에 정당한 전체 접근 — 멤버 행 유무와 무관."""
    _with_pg(monkeypatch, _row(is_owner=True, members=3, role=None))
    assert sw.group_attachment_scope("conv-group", 7) == sw.SCOPE_CONVERSATION

    _with_pg(monkeypatch, _row(is_owner=False, members=3, role="owner"))
    assert sw.group_attachment_scope("conv-group", 7) == sw.SCOPE_CONVERSATION


# ── window 판정 ────────────────────────────────────────────────────────────

def test_full_member_gets_full_scope(monkeypatch):
    """경계 미설정(full) 멤버는 가릴 것이 없다."""
    _with_pg(monkeypatch, _row(members=3, role="member", floor=None, ceiling=None))
    assert sw.group_attachment_scope("conv-group", 7) == sw.SCOPE_CONVERSATION


def test_ceiling_member_with_no_hidden_message_gets_full_scope(monkeypatch):
    """**마찰 대화의 실제 형태**: ceiling 이 설정돼 있어도 실제로 가리는 메시지가 0이면 확대한다.

    라이브 관측(2026-08-13, 대화 …46763d6e): 합류한 멤버는 `visible_ceiling_message_id` 가
    설정돼 있었지만 ceiling 다음 메시지가 곧 자신의 합류 이벤트라 은닉 구간이 비어 있었다.
    그 멤버가 첨부를 못 봐서 "첨부파일이 보이지 않습니다" 를 두 번 받고 대화를 떠났다.
    """
    _with_pg(monkeypatch, _row(members=3, role="member", ceiling=2170, hidden=0))
    assert sw.group_attachment_scope("conv-group", 10) == sw.SCOPE_CONVERSATION


def test_ceiling_member_with_hidden_messages_is_sender_only(monkeypatch):
    """ceiling 과 합류 사이에 가려진 표시 메시지가 실재하면 확대하지 않는다 — §21 AR-1 무회귀."""
    _with_pg(monkeypatch, _row(members=3, role="member", ceiling=2170, hidden=3))
    assert sw.group_attachment_scope("conv-group", 7) == sw.SCOPE_SENDER_ONLY


def test_floor_member_is_always_sender_only(monkeypatch):
    """floor("여기부터 공유") 가 설정된 멤버는 은닉 수와 무관하게 좁힌다.

    (a) floor 이전 구간의 첨부 귀속을 시간축으로 판정할 수 없고, (b) `_msg_outside_window` 는
    floor 가 있을 때 assistant 답변의 recall 태그로도 메시지를 숨기는데 그 축까지 SQL 로
    재현하면 두 구현이 갈릴 위험이 실익보다 크다(§18.8 적대 리뷰 [P2]).
    """
    _with_pg(monkeypatch, _row(members=3, role="member", floor=500, hidden=0))
    assert sw.group_attachment_scope("conv-group", 7) == sw.SCOPE_SENDER_ONLY


# ── 실패 경로(전부 fail-closed) ─────────────────────────────────────────────

def test_unknown_conversation_fails_closed(monkeypatch):
    _with_pg(monkeypatch, None)
    assert sw.group_attachment_scope("conv-none", 7) == sw.SCOPE_SENDER_ONLY


def test_pre_migration_schema_is_not_restricted(monkeypatch):
    """visible_* 컬럼 부재(42703)면 windowed 멤버가 존재할 수 없다 — 안전하게 전체 스코프."""
    exc = RuntimeError("undefined column")
    exc.sqlstate = "42703"
    _with_pg(monkeypatch, None, exc=exc)
    assert sw.group_attachment_scope("conv-1", 7) == sw.SCOPE_CONVERSATION


def test_query_failure_fails_closed(monkeypatch):
    _with_pg(monkeypatch, None, exc=RuntimeError("boom"))
    assert sw.group_attachment_scope("conv-1", 7) == sw.SCOPE_SENDER_ONLY


def test_connect_failure_fails_closed(monkeypatch):
    """PG 무연결도 마찬가지 — 가용성 저하가 경계 완화로 번지지 않게 한다."""
    _with_pg(monkeypatch, None, connect_exc=RuntimeError("no route"))
    assert sw.group_attachment_scope("conv-1", 7) == sw.SCOPE_SENDER_ONLY


def test_unparseable_counts_fail_closed(monkeypatch):
    """카운트를 숫자로 읽을 수 없으면 좁힌다(드라이버 이상·스키마 drift)."""
    _with_pg(monkeypatch, (False, "not-a-number", "member", None, 2170, 0))
    assert sw.group_attachment_scope("conv-1", 7) == sw.SCOPE_SENDER_ONLY

    _with_pg(monkeypatch, (False, 3, "member", None, 2170, "nan"))
    assert sw.group_attachment_scope("conv-1", 7) == sw.SCOPE_SENDER_ONLY


# ── 구조 잠금 ──────────────────────────────────────────────────────────────

def test_gate_query_uses_message_ids_not_attachment_timestamps():
    """은닉 판정은 **메시지 id/joined_at** 축이어야 한다(첨부 시각축 왜곡 회피).

    첨부 `created_at` 은 표시/코어 메시지의 `created_at` 과 같은 시간축이 아니다(라이브 실측
    기준 로컬시각이 UTC 로 라벨링돼 미래로 찍힘). 그 축으로 window 를 자르면 하한에서는 열고
    상한에서는 가리는 양방향 오판이 난다 — 규칙이 id 축을 떠나지 않도록 고정한다.
    """
    sql = sw._PG_ATTACH_WINDOW_GATE
    assert "d.id > m.visible_ceiling_message_id" in sql
    assert "d.created_at < m.joined_at" in sql, "ceiling 초과분은 joined 이후면 가시(라이브룸 규칙)"
    assert "core_attachments" not in sql, "첨부 시각을 window 판정에 끌어들이면 안 됨"


def test_gate_resolves_group_membership_itself():
    """그룹 여부를 게이트가 직접 판정해야 한다 — 호출측 선-게이팅은 fail-open 이었다([P1])."""
    sql = sw._PG_ATTACH_WINDOW_GATE
    assert "member_count" in sql
    assert "conversation_members cm" in sql
    assert "owner_account_id" in sql, "소유자 판정도 같은 쿼리에서(멤버 행 부재 대비)"


def test_bool_wrapper_matches_scope():
    assert sw.group_attachment_is_sender_only(None, None) is True


@pytest.mark.parametrize("hidden", [0, 1, 5])
def test_hidden_count_is_the_only_switch_for_ceiling_member(monkeypatch, hidden):
    """ceiling-only 멤버의 분기는 오직 '은닉이 실재하는가' 하나다(경계값 포함)."""
    _with_pg(monkeypatch, _row(members=3, role="member", ceiling=2170, hidden=hidden))
    expected = sw.SCOPE_CONVERSATION if hidden == 0 else sw.SCOPE_SENDER_ONLY
    assert sw.group_attachment_scope("conv-1", 7) == expected
