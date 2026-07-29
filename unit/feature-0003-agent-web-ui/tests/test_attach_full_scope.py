"""feature-0003 attach-full-scope — 첨부 참조 스코프를 대화 전체로 전환한 회귀 테스트.

배경(2026-07-29 사용자 보고): 첨부가 걸린 대화를 이어서 진행하면 assistant 가 이전 턴 첨부에
접근하지 못하는 마찰이 관측됐다. 참조 범위가 프론트 selection bucket(`attachment_ids`)에만
의존해(D16 minimum exposure), bucket 이 비는 진입 경로(새로고침·랜딩 복귀·pending 컨텍스트)에서
첨부가 통째로 빠졌기 때문이다. 결정 범위를 **대화 자체**로 옮겨(`_resolve_conversation_attachment_scope`)
어떤 진입 경로로 들어와도 같은 첨부 집합이 보이게 한다.

본 테스트는 fake-cursor 로 스코프 SQL 의 불변식(대화 스코프·그룹 발신자 가드·최신본 한정)과
폴백 계약을 고정한다.
"""
from __future__ import annotations

import app


class _CaptureConn:
    """execute(sql, params) 를 기록하고 지정한 행을 돌려주는 fake conn."""

    def __init__(self, captured: dict, rows=None, raise_on_execute: bool = False):
        self._captured = captured
        self._rows = rows or []
        self._raise = raise_on_execute

    def cursor(self):
        captured = self._captured
        rows = self._rows
        should_raise = self._raise

        class _Cur:
            def execute(self, sql, params=None):
                captured["sql"] = sql
                captured["params"] = params
                if should_raise:
                    raise RuntimeError("db down")

            def fetchall(self):
                return rows

            def close(self):
                pass

        return _Cur()


def _rows(*ids):
    return [(int(i),) for i in ids]


def test_scope_covers_whole_conversation_not_client_selection():
    """클라이언트가 아무 id 도 보내지 않아도 대화의 활성 첨부 전량이 스코프에 들어온다.

    이것이 사용자가 보고한 마찰("이어서 요청하면 기존 첨부 접근 불가")의 직접 해소 경로다.
    """
    captured: dict = {}
    out = app._resolve_conversation_attachment_scope(
        _CaptureConn(captured, rows=_rows(31, 22, 11)),
        "conv-abc",
        7,
        client_ids=[],
    )
    assert out == [31, 22, 11], "대화 전체 첨부가 스코프에 포함되어야 함"
    assert "ConversationId = %s" in captured["sql"], "대화 스코프 누락(타 대화 유입 위험)"
    assert "conv-abc" in tuple(captured["params"])


def test_scope_keeps_latest_version_and_active_rows_only():
    """버전 체인의 최신본·미삭제·업로드 완료 행만 — 구버전 중복/삭제분 주입 금지."""
    captured: dict = {}
    app._resolve_conversation_attachment_scope(
        _CaptureConn(captured, rows=_rows(5)), "conv-x", 7
    )
    sql = captured["sql"]
    assert "SupersededAt IS NULL" in sql, "구버전까지 주입되면 같은 파일이 중복 노출됨"
    assert "DeletedAt IS NULL" in sql and "DeletePending = 0" in sql
    assert "UploadStatus IN ('uploaded','ingested')" in sql


def test_group_conversation_keeps_sender_scope_guard():
    """그룹 대화는 발신자 본인 첨부만 (feature-0009 CSO F1 유지, 2026-07-29 사용자 결정).

    타 멤버 첨부가 발신자 권한의 실행 맥락에 실려 datasource 를 끌어오는 권한상승
    (indirect prompt injection)을 막는 가드다 — 스코프 확대가 이 경계를 넘지 않아야 한다.
    """
    captured: dict = {}
    app._resolve_conversation_attachment_scope(
        _CaptureConn(captured, rows=_rows(9)), "conv-group", 42, sender_scope=True
    )
    assert "AccountId = %s" in captured["sql"], "그룹 대화 발신자 가드 누락(권한상승 경로)"
    assert 42 in tuple(captured["params"])

    # 1:1·이어받기는 발신자 필터 없이 대화 전체 (fork/cross-account 에서도 목록과 주입이 일치)
    captured.clear()
    app._resolve_conversation_attachment_scope(
        _CaptureConn(captured, rows=_rows(9)), "conv-1to1", 42, sender_scope=False
    )
    assert "AccountId = %s" not in captured["sql"]


def test_client_ids_never_widen_scope_of_a_known_conversation():
    """대화가 확정된 경로에서는 클라이언트가 보낸 id 가 스코프를 넓히지 못한다.

    무검증 합집합은 그룹 대화의 발신자 가드를 통째로 우회시킨다(적대 리뷰 security/qa BLOCK):
    스톡 UI 조차 대화 첨부 전량을 selected 로 보내므로, 합치는 순간 타 멤버 첨부가 발신자의
    실행 맥락에 그대로 들어온다. DB 조회 결과만이 진실이다.
    """
    out = app._resolve_conversation_attachment_scope(
        _CaptureConn({}, rows=_rows(20, 10)),
        "conv-abc",
        7,
        client_ids=[10, 99],  # 99 = DB 스코프에 없는 id (타 멤버 첨부이거나 위조)
    )
    assert out == [20, 10]
    assert 99 not in out, "클라이언트가 보낸 스코프 밖 id 가 실행 맥락에 유입되면 안 됨"


def test_group_scope_fails_closed_on_db_failure():
    """그룹 대화에서 해소가 실패하면 첨부 없이 간다 — client 폴백은 발신자 가드를 우회시킨다."""
    out = app._resolve_conversation_attachment_scope(
        _CaptureConn({}, raise_on_execute=True), "conv-group", 7,
        client_ids=[3, 4], sender_scope=True,
    )
    assert out == []


def test_direct_scope_falls_back_to_client_ids_on_db_failure():
    """1:1·이어받기는 해소 실패 시 client 선택분 폴백(fail-safe) — 하위 소비자가 대화 스코프 재적용."""
    out = app._resolve_conversation_attachment_scope(
        _CaptureConn({}, raise_on_execute=True), "conv-abc", 7, client_ids=[3, 4]
    )
    assert out == [3, 4]


def test_scope_without_conversation_uses_client_ids_only():
    """conversation_id 미확정(lazy-create) 경로는 client 선택분만 — 대화 없는 전량 조회 금지."""
    out = app._resolve_conversation_attachment_scope(None, None, 7, client_ids=[1, 2])
    assert out == [1, 2]


# ── PG read 경로 (라이브 기본 백엔드) ────────────────────────────────────────
# 운영은 AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND=postgres 로 도는 구간이 있어, MySQL 폴백
# 분기만 검증하면 실제로 실행되는 경로의 가드가 무검증으로 남는다(적대 리뷰 qa).

class _FakePgMirror:
    def __init__(self, rows):
        self._rows = rows

    def read_pg_enabled(self):
        return True

    def pg_list_conversation_attachments(self, cid):
        return list(self._rows)


def _with_pg(monkeypatch, rows):
    import sys
    import types
    mod = _FakePgMirror(rows)
    pkg = types.ModuleType("web.modules")
    pkg.attachment_pg_mirror = mod
    monkeypatch.setitem(sys.modules, "web.modules", pkg)
    monkeypatch.setitem(sys.modules, "web.modules.attachment_pg_mirror", mod)


def _pg_row(aid, account_id=7, status="ingested"):
    return {"id": aid, "account_id": account_id, "upload_status": status}


def test_pg_path_filters_status_and_orders_latest_first(monkeypatch):
    _with_pg(monkeypatch, [
        _pg_row(10), _pg_row(31), _pg_row(22),
        _pg_row(40, status="failed"),   # 업로드 미완/실패는 제외
        _pg_row(41, status="deleted"),
    ])
    out = app._resolve_conversation_attachment_scope(None, "conv-abc", 7)
    assert out == [31, 22, 10], "최신 우선 정렬 + 상태 필터가 PG 경로에서도 성립해야 함"


def test_pg_path_applies_group_sender_guard(monkeypatch):
    """PG 경로에서도 그룹 발신자 가드가 성립 — 라이브에서 실제로 실행되는 분기."""
    _with_pg(monkeypatch, [_pg_row(10, account_id=7), _pg_row(22, account_id=99)])
    out = app._resolve_conversation_attachment_scope(None, "conv-group", 7, sender_scope=True)
    assert out == [10], "타 멤버(account 99) 첨부가 발신자 스코프에 들어오면 안 됨"

    # 1:1 은 같은 대화의 타 계정 첨부도 정상 포함(fork·이어받기)
    _with_pg(monkeypatch, [_pg_row(10, account_id=7), _pg_row(22, account_id=99)])
    out = app._resolve_conversation_attachment_scope(None, "conv-1to1", 7, sender_scope=False)
    assert out == [22, 10]


def test_pg_path_is_capped(monkeypatch):
    cap = app._ATTACHMENT_SCOPE_COUNT_CAP
    _with_pg(monkeypatch, [_pg_row(i) for i in range(1, cap + 50)])
    out = app._resolve_conversation_attachment_scope(None, "conv-big", 7)
    assert len(out) == cap
    assert out[0] == cap + 49, "상한 초과 시 최신 첨부가 보존되어야 함"


def test_scope_is_capped():
    """첨부가 매우 많은 대화에서도 상한을 넘겨 프롬프트를 밀어내지 않는다."""
    cap = app._ATTACHMENT_SCOPE_COUNT_CAP
    many = _rows(*range(1, cap + 50))
    out = app._resolve_conversation_attachment_scope(
        _CaptureConn({}, rows=many), "conv-big", 7
    )
    assert len(out) == cap
