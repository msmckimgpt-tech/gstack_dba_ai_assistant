"""REQ-20260824-attach-original-baseline — 계보 최초 원본(_v0)의 능동 주입 계약.

사용자 요청(2026-08-24): "assistant 가 첨부된 파일을 비교하는 작업을 수행할 경우, 초창기 원본
데이터를 조회할 수 있었다면 `_v0` 형태로 가장 이전의 버전으로 능동적으로 포함하도록 구성."

종전에는 원본에 도달할 경로가 **한 곳도 없었다** — LLM 첨부 스코프도 `read_attachment` 도
`SupersededAt IS NULL`(최신본)만 보고, `## FILE UPDATES` diff 는 직전 버전 대비이며 재업로드가
일어난 그 턴에만 렌더된다. 그래서 v3 이상 체인에서 "처음 올린 것과 지금의 차이" 는 원리적으로
답할 수 없었고, 모델은 답할 수 없다는 사실조차 몰랐다.

여기서 고정하는 것:
  · 버전>1 인 첨부의 **계보 최초본**이 프롬프트에 `_v0` 로 실린다 (단일 버전이면 안 실린다)
  · 본문이 실리지 않은 원본은 **존재 사실이 명시**된다 (무음 절단 금지 — 반대 방향 단정 차단)
  · 타 계정 원본의 본문이 실리면 provenance 신호가 선다 (쓰기 게이트 우회로가 되지 않는다)
  · `read_attachment(attachment_id=<원본 id>)` 가 열리되 **같은 대화·같은 계보**로만 열린다

MySQL SELECT 컬럼 순서(메인 조회):
  0 Id, 1 ConversationId, 2 OriginalFilename, 3 Kind, 4 MimeType, 5 SizeBytes, 6 SizeBucket,
  7 UploadStatus, 8 MetaJson, 9 RootAttachmentId, 10 VersionNumber, 11 CreatedByRole,
  12 AccountId, 13 CreatedAt
원본 조회(`_load_original_versions`) 컬럼 순서:
  0 Id, 1 OriginalFilename, 2 Kind, 3 ObjectKey, 4 VersionNumber, 5 CreatedByRole,
  6 AccountId, 7 CreatedAt, 8 COALESCE(RootAttachmentId, Id)
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

import agent_core


# ── 하네스 ────────────────────────────────────────────────────────────────

class _SqlRoutingConn:
    """실행된 SQL 로 결과를 고르는 fake connection.

    첨부 주입은 한 conn 으로 **성격이 다른 조회 두 개**(현재본 목록 / 계보 최초본)를 돌린다.
    같은 rows 를 무조건 돌려주는 하네스로는 원본 경로가 검증되지 않는다.
    """

    def __init__(self, main_rows, original_rows=None):
        self.main_rows = main_rows
        self.original_rows = original_rows or []
        self.executed: list[str] = []

    def cursor(self, *a, **k):
        outer = self

        class _Cur:
            def __init__(self):
                self._rows = []

            def execute(self, sql, params=None):
                outer.executed.append(sql)
                if "COALESCE(RootAttachmentId, Id) IN" in sql:
                    self._rows = outer.original_rows
                else:
                    self._rows = outer.main_rows

            def fetchall(self):
                return self._rows

            def fetchone(self):
                return self._rows[0] if self._rows else None

            def close(self):
                pass

        return _Cur()

    def close(self):
        pass


def _main_row(aid, fname, *, uploader=50, version=1, root=None, role="user", kind="text",
              created="2026-08-20 10:00"):
    return (
        aid, "conv-x", fname, kind, "text/plain", 100, "small", "uploaded",
        json.dumps({}), root, version, role, uploader,
        datetime.strptime(created, "%Y-%m-%d %H:%M"),
    )


def _orig_row(aid, fname, *, chain, version=1, uploader=50, role="user", kind="text",
              object_key=None, created="2026-08-01 09:00"):
    return (
        aid, fname, kind, object_key or f"obj/{aid}", version, role, uploader,
        datetime.strptime(created, "%Y-%m-%d %H:%M"), chain,
    )


def _build(conn, ids, monkeypatch, *, account_id=50, bodies=None):
    monkeypatch.setenv("ATTACHMENT_IDS", ",".join(str(i) for i in ids))
    monkeypatch.setattr(agent_core, "_resolve_group_sender_labels", lambda *a, **k: None)
    _bodies = bodies if bodies is not None else {}
    monkeypatch.setattr(
        agent_core, "_load_attachment_bytes",
        lambda key: _bodies.get(key) if key in _bodies else b"-- original body\nSELECT 1;\n",
    )
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._ORIGINAL_VERSIONS_CTX.set(None)
    # run 단위 캐시 — 앞선 테스트가 남긴 값이 "이번 턴 신규" 판정을 오염시키지 않게.
    agent_core._SERVER_NEW_ATTACHMENT_IDS_CTX.set(None)
    return agent_core._build_attachment_context_section(conn, ids, account_id, "conv-x")


def _original_block(out: str) -> str:
    """원본 섹션만 잘라낸다(다른 섹션 문구에 오탐하지 않도록)."""
    head = "## ORIGINAL VERSIONS (_v0)"
    if head not in out:
        return ""
    return out.split(head, 1)[1].split("\n## ", 1)[0]


# ── 파일명 표기 규약 ──────────────────────────────────────────────────────

def test_v0_filename_keeps_extension():
    """`report.sql` → `report_v0.sql` — 확장자 앞에 붙어야 코드 펜스 언어도 유지된다."""
    assert agent_core._original_v0_filename("report.sql") == "report_v0.sql"
    assert agent_core._original_v0_filename("a.b.csv") == "a.b_v0.csv"


def test_v0_filename_without_extension():
    assert agent_core._original_v0_filename("README") == "README_v0"
    assert agent_core._original_v0_filename("") == "attachment_v0"


# ── 렌더 조건: 버전이 오른 파일에만 ────────────────────────────────────────

def test_single_version_renders_no_original_section(monkeypatch):
    """v1 뿐인 첨부는 '이전 버전' 이 없다 — 프롬프트를 늘리지 않는다."""
    conn = _SqlRoutingConn([_main_row(10, "report.sql", version=1)])
    out = _build(conn, [10], monkeypatch)
    assert "ORIGINAL VERSIONS" not in out


def test_versioned_file_inlines_original_body(monkeypatch):
    """v3 첨부면 계보 최초본(v1) 본문이 `_v0` 이름으로 실린다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "init_query.sql", version=3, root=10)],
        [_orig_row(10, "init_query.sql", chain=10, version=1),
         _orig_row(20, "init_query.sql", chain=10, version=2)],
    )
    out = _build(conn, [30], monkeypatch,
                 bodies={"obj/10": b"TRUNCATE TABLE user_log;\n"})
    block = _original_block(out)
    assert block, "버전>1 첨부인데 원본 섹션이 렌더되지 않았다"
    assert "init_query_v0.sql" in block
    assert "attachment_id=10" in block          # v2(20)가 아니라 최초본(10)
    assert "TRUNCATE TABLE user_log;" in block
    # 현재본과의 대응 관계를 같은 자리에서 밝힌다 — 모델이 어느 쌍을 비교할지 알아야 한다.
    assert "attachment_id=30" in block


def test_original_body_is_line_numbered_and_datamarked(monkeypatch):
    """원본도 현재본과 **같은 규약**으로 실린다 — 줄번호 + 비신뢰 구획."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10)],
        [_orig_row(10, "q.sql", chain=10, version=1)],
    )
    out = _build(conn, [30], monkeypatch, bodies={"obj/10": b"SELECT 1;\nSELECT 2;\n"})
    block = _original_block(out)
    assert "1→" in block and "2→" in block           # _number_file_lines
    assert agent_core._INJ_OPEN in block and agent_core._INJ_CLOSE in block


def test_self_is_original_is_not_rendered(monkeypatch):
    """체인 앞부분이 삭제돼 자기가 최초본이면 보여줄 '이전 버전' 이 없다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=3, root=30)],
        [_orig_row(30, "q.sql", chain=30, version=3)],
    )
    out = _build(conn, [30], monkeypatch)
    assert "ORIGINAL VERSIONS" not in out


def test_original_lookup_failure_does_not_kill_attachment_section(monkeypatch):
    """원본 조회가 실패해도 첨부 주입 전체는 살아 있다(fail-soft)."""
    conn = _SqlRoutingConn([_main_row(30, "q.sql", version=2, root=10)], [])
    out = _build(conn, [30], monkeypatch)
    assert "ATTACHED FILES" in out
    assert "ORIGINAL VERSIONS" not in out


# ── 절단·미인라인은 관측 가능해야 한다 ────────────────────────────────────

def test_non_text_original_is_listed_not_inlined(monkeypatch):
    """xlsx 구버전은 본문이 아니라 **존재 사실**로 실린다 — '원본이 없다' 단정 차단."""
    conn = _SqlRoutingConn(
        [_main_row(30, "sales.xlsx", version=2, root=10, kind="xlsx")],
        [_orig_row(10, "sales.xlsx", chain=10, version=1, kind="xlsx")],
    )
    out = _build(conn, [30], monkeypatch)
    block = _original_block(out)
    assert "sales_v0.xlsx" in block
    assert "attachment_id=10" in block
    assert "kind=xlsx" in block
    assert "read_attachment" in block            # 도달 경로를 함께 준다


def test_unreadable_original_states_uncertain_cause(monkeypatch):
    """본문을 못 읽으면 원인을 단정하지 않는다(형제 경로와 동일 태세)."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10)],
        [_orig_row(10, "q.sql", chain=10, version=1)],
    )
    monkeypatch.setattr(agent_core, "_load_attachment_bytes", lambda key: None)
    monkeypatch.setenv("ATTACHMENT_IDS", "30")
    monkeypatch.setattr(agent_core, "_resolve_group_sender_labels", lambda *a, **k: None)
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    out = agent_core._build_attachment_context_section(conn, [30], 50, "conv-x")
    block = _original_block(out)
    assert "원인 미확인" in block
    assert "MinIO" not in block                  # 인프라 장애 오귀속 금지


def test_count_cap_surfaces_omission(monkeypatch):
    """건수 상한 초과분은 조용히 사라지지 않는다 — 몇 건이 빠졌는지 밝힌다."""
    n = agent_core._ORIGINAL_INLINE_COUNT_CAP + 2
    # 체인 id 는 1부터 — 0 은 "루트 미상" 과 구분되지 않는다(코드가 자기 Id 로 폴백).
    main = [_main_row(100 + i, f"f{i}.sql", version=2, root=i + 1) for i in range(n)]
    orig = [_orig_row(i + 1, f"f{i}.sql", chain=i + 1, version=1) for i in range(n)]
    conn = _SqlRoutingConn(main, orig)
    out = _build(conn, [100 + i for i in range(n)], monkeypatch)
    block = _original_block(out)
    assert "실리지 않은 파일 2건" in block
    assert "상한 초과" in block


def test_char_cap_marks_truncation(monkeypatch):
    """문자 상한을 넘긴 원본은 [truncated] 로 표시된다."""
    big = ("SELECT 1;\n" * 20000).encode()
    assert len(big) > agent_core._ORIGINAL_INLINE_CHAR_CAP
    conn = _SqlRoutingConn(
        [_main_row(30, "big.sql", version=2, root=10)],
        [_orig_row(10, "big.sql", chain=10, version=1)],
    )
    out = _build(conn, [30], monkeypatch, bodies={"obj/10": big})
    block = _original_block(out)
    assert "truncated" in block


# ── provenance: 본문이 실린 순간에만 신호 ─────────────────────────────────

def test_other_member_original_body_sets_untrusted_flag(monkeypatch):
    """타 계정 원본의 **본문이 실제로 실리면** 쓰기 게이트 신호가 선다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10, uploader=50)],
        [_orig_row(10, "q.sql", chain=10, version=1, uploader=77)],
    )
    _build(conn, [30], monkeypatch, account_id=50, bodies={"obj/10": b"SELECT 1;\n"})
    assert agent_core.untrusted_attachment_body_in_context() is True


def test_own_original_body_does_not_set_untrusted_flag(monkeypatch):
    """자기 파일의 원본은 비신뢰 출처가 아니다 — 과차단하지 않는다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10, uploader=50)],
        [_orig_row(10, "q.sql", chain=10, version=1, uploader=50)],
    )
    _build(conn, [30], monkeypatch, account_id=50, bodies={"obj/10": b"SELECT 1;\n"})
    assert agent_core.untrusted_attachment_body_in_context() is False


def test_non_inlined_other_member_original_does_not_set_flag(monkeypatch):
    """목록만 실린 경우는 주입 벡터가 아니다 — 본문 렌더가 발동 조건."""
    conn = _SqlRoutingConn(
        [_main_row(30, "s.xlsx", version=2, root=10, kind="xlsx", uploader=50)],
        [_orig_row(10, "s.xlsx", chain=10, version=1, kind="xlsx", uploader=77)],
    )
    _build(conn, [30], monkeypatch, account_id=50)
    assert agent_core.untrusted_attachment_body_in_context() is False


# ── 조회 술어의 경계 ──────────────────────────────────────────────────────

def test_original_lookup_scopes_by_conversation_and_excludes_deleted(monkeypatch):
    """원본 조회는 현재본과 **같은 술어**로 스코프한다 — 이 경로만 넓어지면 안 된다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10)],
        [_orig_row(10, "q.sql", chain=10, version=1)],
    )
    _build(conn, [30], monkeypatch)
    sql = next(s for s in conn.executed if "COALESCE(RootAttachmentId, Id) IN" in s)
    assert "ConversationId = %s" in sql
    assert "DeletedAt IS NULL" in sql
    assert "DeletePending = 0" in sql


def test_original_lookup_picks_lowest_version_in_chain():
    """체인에 여러 구버전이 있으면 **가장 낮은 버전**이 최초본이다."""
    conn = _SqlRoutingConn([], [
        _orig_row(22, "q.sql", chain=10, version=2),
        _orig_row(10, "q.sql", chain=10, version=1),
        _orig_row(33, "q.sql", chain=10, version=3),
    ])
    got = agent_core._load_original_versions(
        conn, [{"id": 33, "root": 10, "version": 3, "filename": "q.sql"}],
        "conv-x", 50, True,
    )
    assert got[33]["id"] == 10
    assert got[33]["version"] == 1


def test_original_lookup_requires_a_scope():
    """대화도 계정도 없으면 조회하지 않는다(fail-closed)."""
    conn = _SqlRoutingConn([], [_orig_row(10, "q.sql", chain=10, version=1)])
    got = agent_core._load_original_versions(
        conn, [{"id": 33, "root": 10, "version": 3, "filename": "q.sql"}],
        None, None, False,
    )
    assert got == {}


# ── read_attachment 의 계보 조상 폴백 ─────────────────────────────────────

def test_ancestor_row_requires_conversation_chain_and_alive(monkeypatch):
    """조상 허용 술어 4겹 — 같은 대화 · 같은 체인 · **더 낮은 버전** · 미삭제.

    앵커 조회는 `(chain, VersionNumber)` 를 돌려주고, 그 버전이 조상 판정의 상한이 된다
    (§18.8 codex [P2] — 종전엔 버전 비교가 없어 같은 체인의 더 최신 행도 통과했다).
    """
    calls: list[str] = []

    class _Conn:
        def cursor(self, *a, **k):
            class _Cur:
                def __init__(self):
                    self._rows = []

                def execute(self, sql, params=None):
                    calls.append(sql)
                    if "COALESCE(RootAttachmentId, Id), VersionNumber" in sql:
                        self._rows = [(10, 3)]          # 체인 10 의 스코프 버전 = v3
                    else:
                        self._rows = [(
                            10, "q.sql", "text", "obj/10", "uploaded", None, "user", 1, 50, 10,
                        )]

                def fetchall(self):
                    return self._rows

                def fetchone(self):
                    return self._rows[0] if self._rows else None

                def close(self):
                    pass

            return _Cur()

        def close(self):
            pass

    monkeypatch.setenv("ATTACHMENT_IDS", "30")
    monkeypatch.setattr(agent_core, "_connect_memory", lambda *a, **k: _Conn())
    import shared.config as _cfg
    monkeypatch.setattr(_cfg, "get_active_conversation_id", lambda: "conv-x")

    row = agent_core._load_ancestor_attachment_row(10)
    assert row is not None and row["id"] == 10
    target_sql = calls[-1]
    assert "ConversationId = %s" in target_sql
    assert "COALESCE(RootAttachmentId, Id) IN" in target_sql
    assert "DeletedAt IS NULL" in target_sql
    assert "DeletePending = 0" in target_sql


def test_ancestor_row_fails_closed_without_conversation(monkeypatch):
    """대화 컨텍스트가 없으면 읽지 않는다 — 형제 경로와 동일 태세."""
    monkeypatch.setenv("ATTACHMENT_IDS", "30")
    import shared.config as _cfg
    monkeypatch.setattr(_cfg, "get_active_conversation_id", lambda: "")
    assert agent_core._load_ancestor_attachment_row(10) is None


def test_ancestor_row_needs_scope_ids(monkeypatch):
    """참조 가능한 첨부 자체가 없으면 체인 집합이 없다 — 조상도 없다."""
    monkeypatch.delenv("ATTACHMENT_IDS", raising=False)
    agent_core._ATTACHMENT_IDS_CTX.set(None)
    assert agent_core._load_ancestor_attachment_row(10) is None


def test_read_attachment_falls_back_to_ancestor(monkeypatch):
    """스코프 밖이어도 같은 계보의 조상이면 읽힌다 — 안내가 막다른 길이 되지 않게."""
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [
        {"id": 30, "filename": "q.sql", "kind": "text", "object_key": "obj/30",
         "status": "uploaded", "meta_json": None, "created_by_role": "user",
         "version_number": 2, "account_id": 50},
    ])
    monkeypatch.setattr(agent_core, "_load_ancestor_attachment_row", lambda aid: (
        {"id": 10, "filename": "q.sql", "kind": "text", "object_key": "obj/10",
         "status": "uploaded", "meta_json": None, "created_by_role": "user",
         "version_number": 1, "account_id": 50} if int(aid) == 10 else None
    ))
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})
    monkeypatch.setattr(agent_core, "_load_attachment_bytes", lambda key: b"ORIGINAL BODY\n")

    res = agent_core.read_attachment_content(attachment_id=10)
    assert res["ok"] is True
    assert res["attachment_id"] == 10
    assert "ORIGINAL BODY" in res["text"]


def test_read_attachment_still_rejects_foreign_id(monkeypatch):
    """계보 밖 id 는 계속 거부된다 — 조상 폴백이 경계를 지우지 않는다."""
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [
        {"id": 30, "filename": "q.sql", "kind": "text", "object_key": "obj/30",
         "status": "uploaded", "meta_json": None, "created_by_role": "user",
         "version_number": 2, "account_id": 50},
    ])
    monkeypatch.setattr(agent_core, "_load_ancestor_attachment_row", lambda aid: None)
    res = agent_core.read_attachment_content(attachment_id=999)
    assert res["ok"] is False
    assert "참조할 수 있는 첨부가 아닙니다" in res["error"]


def test_filename_lookup_is_not_widened_to_ancestors(monkeypatch):
    """filename 경로는 최신본만 본다 — 구버전이 동명 후보로 끼면 매번 되묻게 된다."""
    called = {"n": 0}

    def _anc(aid):
        called["n"] += 1
        return None

    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [
        {"id": 30, "filename": "q.sql", "kind": "text", "object_key": "obj/30",
         "status": "uploaded", "meta_json": None, "created_by_role": "user",
         "version_number": 2, "account_id": 50},
    ])
    monkeypatch.setattr(agent_core, "_load_ancestor_attachment_row", _anc)
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})
    monkeypatch.setattr(agent_core, "_load_attachment_bytes", lambda key: b"CURRENT\n")

    res = agent_core.read_attachment_content(filename="q.sql")
    assert res["ok"] is True and res["attachment_id"] == 30
    assert called["n"] == 0, "filename 경로가 조상 조회를 불렀다"


# ── 프롬프트 지시 계약 ────────────────────────────────────────────────────

def test_system_prompt_separates_history_spans():
    """`_v0`(전 이력)와 FILE UPDATES(마지막 한 걸음)의 **범위 차이**를 명시한다."""
    sp = agent_core.SYSTEM_PROMPT
    assert "ORIGINAL VERSIONS" in sp
    assert "FILE UPDATES" in sp
    # 마지막 한 걸음짜리 diff 로 "처음부터" 질문에 답하지 말라는 규칙이 있어야 한다.
    assert "only the LAST step" in sp


def test_original_section_instructs_dual_source_comparison(monkeypatch):
    """섹션이 렌더되면 '원본과 현재본을 모두 근거로' 라는 지시가 함께 실린다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10)],
        [_orig_row(10, "q.sql", chain=10, version=1)],
    )
    out = _build(conn, [30], monkeypatch, bodies={"obj/10": b"SELECT 1;\n"})
    assert "INSTRUCTION (ORIGINAL VERSIONS)" in out
    assert "BOTH" in _original_block(out)


def test_read_attachment_tool_advertises_previous_versions():
    """도구 설명이 '이전 버전도 읽을 수 있다' 를 밝힌다 — 안내와 실제 동작의 정합."""
    from modules import tools as _tools
    spec = next(
        d for d in _tools._ATTACHMENT_TOOL_DEFS
        if d["function"]["name"] == "read_attachment"
    )
    desc = spec["function"]["description"]
    assert "이전 버전" in desc
    assert "attachment_id" in spec["function"]["parameters"]["properties"]


@pytest.mark.parametrize("version", [2, 3, 11])
def test_any_updated_version_triggers_lookup(monkeypatch, version):
    """버전이 오른 사실 자체가 트리거다 — 질문이 비교인지 판정하지 않는다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=version, root=10)],
        [_orig_row(10, "q.sql", chain=10, version=1)],
    )
    out = _build(conn, [30], monkeypatch, bodies={"obj/10": b"SELECT 1;\n"})
    assert "ORIGINAL VERSIONS" in out


# ── 리뷰어 ground truth 정합 (FR-redteam-digest-lacks-prior-attachment-version 축) ──
# 답변이 "처음과 비교하면 …" 을 말할 때 그 근거는 `_v0` 본문이다. 리뷰어가 그것을 못 보면
# 정확한 답변이 창작으로 오판돼 grounding BLOCK 이 난다 — 같은 실패 모드가 `## FILE UPDATES`
# 축에서 2026-08-11 라이브로 실증됐다.

def test_rendered_original_is_exposed_to_reviewer(monkeypatch):
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10)],
        [_orig_row(10, "q.sql", chain=10, version=1)],
    )
    _build(conn, [30], monkeypatch, bodies={"obj/10": b"ORIGINAL LINE\n"})
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [])
    items = agent_core._review_attachments(False)
    names = [i["filename"] for i in items]
    assert "q_v0.sql" in names
    got = next(i for i in items if i["filename"] == "q_v0.sql")
    assert "ORIGINAL LINE" in got["content"]
    assert got["content_available"] is True


def test_unrendered_original_is_not_claimed_to_reviewer(monkeypatch):
    """본문이 실리지 않은 원본을 리뷰어에게 주면 'assistant 가 봤다' 는 거짓 전제가 된다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "s.xlsx", version=2, root=10, kind="xlsx")],
        [_orig_row(10, "s.xlsx", chain=10, version=1, kind="xlsx")],
    )
    _build(conn, [30], monkeypatch)
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [])
    items = agent_core._review_attachments(False)
    assert not [i for i in items if i["filename"].endswith("_v0.xlsx")]


def test_original_ctx_is_reset_per_compose(monkeypatch):
    """run 경계에서 지우지 않으면 다른 대화의 원본이 리뷰어 ground truth 로 샌다."""
    agent_core._ORIGINAL_VERSIONS_CTX.set((("stale_v0.sql", "STALE", False),))
    agent_core.compose_system_prompt(None)          # mem_conn 없음 → 조기 return 경로
    assert agent_core._ORIGINAL_VERSIONS_CTX.get() is None


def test_bounded_sender_gets_no_original(monkeypatch):
    """공유창 window 로 가려진 발신자에겐 첨부 ground truth 자체가 비워진다(누출 게이트)."""
    agent_core._ORIGINAL_VERSIONS_CTX.set((("q_v0.sql", "ORIGINAL", False),))
    assert agent_core._review_attachments(True) == []


# ── 현재본이 실리지 않은 경우의 안내 (없는 증거를 가리키지 않는다) ────────────────

def test_points_to_tool_when_current_body_not_inlined(monkeypatch):
    """현재본이 인라인되지 않았는데 '위 본문 참조' 라고 하면 없는 증거를 찾게 만든다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10)],
        [_orig_row(10, "q.sql", chain=10, version=1)],
    )
    # 인라인 맵이 비어 있으므로 현재본 본문은 이번 턴에 실리지 않는다.
    out = _build(conn, [30], monkeypatch, bodies={"obj/10": b"SELECT 1;\n"})
    block = _original_block(out)
    assert "인라인되지 않음" in block
    assert "attachment_id=30" in block
    assert "위 ATTACHED FILE CONTENTS 참조" not in block


def test_points_to_contents_when_current_body_inlined(monkeypatch):
    """현재본이 실제로 실렸으면 그쪽을 가리킨다 — 불필요한 도구 호출을 유도하지 않는다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10)],
        [_orig_row(10, "q.sql", chain=10, version=1)],
    )
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {
        30: {"filename": "q.sql", "content": "SELECT 2;\n", "truncated": False},
    })
    out = _build(conn, [30], monkeypatch, bodies={"obj/10": b"SELECT 1;\n"})
    block = _original_block(out)
    assert "위 ATTACHED FILE CONTENTS 참조" in block


# ── 상한이 무엇을 밀어내는가 (선례 있는 함정) ────────────────────────────────

def test_count_cap_keeps_this_turn_uploads_first(monkeypatch):
    """상한 초과 시 **방금 재업로드한 파일**의 원본이 살아남아야 한다.

    목록 순서(Id ASC)대로 자르면 가장 오래된 것이 남고 질문 대상이 밀린다 — text 인라인에서
    실측된 함정("cap 초과 시 방금 올린 파일이 조용히 누락")과 같은 축이다.
    """
    n = agent_core._ORIGINAL_INLINE_COUNT_CAP + 2
    main = [_main_row(100 + i, f"f{i}.sql", version=2, root=i + 1) for i in range(n)]
    orig = [_orig_row(i + 1, f"f{i}.sql", chain=i + 1, version=1) for i in range(n)]
    conn = _SqlRoutingConn(main, orig)
    ids = [100 + i for i in range(n)]
    # 이번 턴 신규 = 가장 오래된 id 하나(정렬이 순진하면 정확히 이게 밀려난다).
    monkeypatch.setenv("NEW_ATTACHMENT_IDS", "100")
    out = _build(conn, ids, monkeypatch)
    block = _original_block(out)
    assert "f0_v0.sql" in block, "이번 턴 신규 첨부의 원본이 상한에 밀렸다"


def test_char_cap_cuts_on_line_boundary(monkeypatch):
    """문자 상한은 **온전한 줄까지만** — 조각난 줄에 줄번호가 붙으면 없는 차이가 생긴다."""
    line = "SELECT 'x';\n"
    body = (line * 8000).encode()
    assert len(body) > agent_core._ORIGINAL_INLINE_CHAR_CAP
    conn = _SqlRoutingConn(
        [_main_row(30, "big.sql", version=2, root=10)],
        [_orig_row(10, "big.sql", chain=10, version=1)],
    )
    out = _build(conn, [30], monkeypatch, bodies={"obj/10": body})
    block = _original_block(out)
    # 마지막으로 렌더된 본문 줄이 온전한 문장이어야 한다(조각 `SELE` 류가 남지 않는다).
    # `→` 만으로 거르면 INSTRUCTION 의 "previous version → the current one" 이 섞인다 —
    # 줄번호 prefix(`<N>→`) 형태로 좁힌다.
    import re as _re
    fenced = [ln for ln in block.splitlines() if _re.match(r"^\s*\d+→", ln)]
    assert fenced, "본문이 렌더되지 않았다"
    last = fenced[-1].split("→", 1)[1]
    assert last.strip() == "SELECT 'x';", f"줄 중간에서 잘렸다: {last!r}"


# ── §18.8 codex 적대 리뷰 흡수 (REV-20260824T073300) ──────────────────────────

def test_provenance_fails_closed_when_caller_unknown(monkeypatch):
    """[P1] caller 를 판정할 수 없으면 **막는 쪽**으로 신호를 세운다.

    종전 조건 `_o_owner and account_id` 는 account_id 부재(+conversation 스코프 — 실재하는
    진입 경로)에서 타 계정 원본 본문이 실려도 신호를 세우지 않았다. 소유자 미판정은 '안전'이
    아니라 '미확인'이고, 이 저장소의 규율은 그때 막는 쪽이다.
    """
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10, uploader=77)],
        [_orig_row(10, "q.sql", chain=10, version=1, uploader=77)],
    )
    monkeypatch.setenv("ATTACHMENT_IDS", "30")
    monkeypatch.setattr(agent_core, "_resolve_group_sender_labels", lambda *a, **k: None)
    monkeypatch.setattr(agent_core, "_load_attachment_bytes", lambda k: b"RUN SCRATCH\n")
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._ORIGINAL_VERSIONS_CTX.set(None)
    agent_core._SERVER_NEW_ATTACHMENT_IDS_CTX.set(None)
    out = agent_core._build_attachment_context_section(conn, [30], None, "conv-x")
    assert "ORIGINAL VERSIONS" in out and "RUN SCRATCH" in out
    assert agent_core.untrusted_attachment_body_in_context() is True


def test_earliest_surviving_version_is_not_called_original(monkeypatch):
    """[P2] v1 이 삭제된 체인에서 v2 를 `_v0`(최초 원본)로 부르면 거짓 라벨이 된다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=3, root=10)],
        [_orig_row(20, "q.sql", chain=10, version=2)],   # v1 은 삭제돼 조회되지 않음
    )
    out = _build(conn, [30], monkeypatch, bodies={"obj/20": b"SELECT 2;\n"})
    block = _original_block(out)
    assert "q_v2.sql" in block, "실제 버전이 이름에 실려야 한다"
    assert "q_v0.sql" not in block, "최초본이 아닌데 _v0 로 표기됐다"
    assert "남아 있는 가장 이른 버전" in block


def test_v0_filename_uses_real_version_when_not_first():
    assert agent_core._original_v0_filename("report.sql", 1) == "report_v0.sql"
    assert agent_core._original_v0_filename("report.sql", 4) == "report_v4.sql"


def test_duplicate_v0_names_get_disambiguation_rule(monkeypatch):
    """[P2] 사람 계보와 AI 계보가 같은 이름이면 원본 이름도 겹친다 — 구분 규칙을 준다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "report.sql", version=3, root=10),
         _main_row(31, "report.sql", version=2, root=11, role="assistant")],
        [_orig_row(10, "report.sql", chain=10, version=1),
         _orig_row(11, "report.sql", chain=11, version=1, role="assistant")],
    )
    out = _build(conn, [30, 31], monkeypatch,
                 bodies={"obj/10": b"USER ORIGINAL\n", "obj/11": b"AI ORIGINAL\n"})
    block = _original_block(out)
    assert "두 계보의 원본이 같은 이름" in block
    assert "`report_v0.sql`" in block
    # 각 원본은 자기 짝(현재본)을 밝힌다.
    assert "attachment_id=30" in block and "attachment_id=31" in block


def test_single_lineage_gets_no_duplicate_warning(monkeypatch):
    """이름이 겹치지 않으면 경고를 붙이지 않는다 — 프롬프트를 낭비하지 않는다."""
    conn = _SqlRoutingConn(
        [_main_row(30, "q.sql", version=2, root=10)],
        [_orig_row(10, "q.sql", chain=10, version=1)],
    )
    out = _build(conn, [30], monkeypatch, bodies={"obj/10": b"SELECT 1;\n"})
    assert "두 계보의 원본이 같은 이름" not in out


def _ancestor_conn(rows_anchor, row_target):
    class _Conn:
        def cursor(self, *a, **k):
            class _Cur:
                def __init__(self):
                    self._rows = []
                    self._one = None

                def execute(self, sql, params=None):
                    if "VersionNumber \nFROM" in sql or "COALESCE(RootAttachmentId, Id), VersionNumber" in sql:
                        self._rows, self._one = rows_anchor, None
                    else:
                        self._rows, self._one = [], row_target

                def fetchall(self):
                    return self._rows

                def fetchone(self):
                    return self._one

                def close(self):
                    pass

            return _Cur()

        def close(self):
            pass

    return _Conn()


def test_ancestor_rejects_newer_version_in_same_chain(monkeypatch):
    """[P2] 같은 체인이어도 **더 최신** 버전은 조상이 아니다 — 이 함수는 과거만 연다."""
    monkeypatch.setenv("ATTACHMENT_IDS", "30")
    import shared.config as _cfg
    monkeypatch.setattr(_cfg, "get_active_conversation_id", lambda: "conv-x")
    # 스코프는 체인 10 의 v3, 대상은 같은 체인의 v4(미삭제).
    conn = _ancestor_conn([(10, 3)], (40, "q.sql", "text", "obj/40", "uploaded", None, "user", 4, 50, 10))
    monkeypatch.setattr(agent_core, "_connect_memory", lambda *a, **k: conn)
    assert agent_core._load_ancestor_attachment_row(40) is None


def test_ancestor_accepts_older_version_in_same_chain(monkeypatch):
    monkeypatch.setenv("ATTACHMENT_IDS", "30")
    import shared.config as _cfg
    monkeypatch.setattr(_cfg, "get_active_conversation_id", lambda: "conv-x")
    conn = _ancestor_conn([(10, 3)], (10, "q.sql", "text", "obj/10", "uploaded", None, "user", 1, 50, 10))
    monkeypatch.setattr(agent_core, "_connect_memory", lambda *a, **k: conn)
    got = agent_core._load_ancestor_attachment_row(10)
    assert got is not None and got["id"] == 10 and got["version_number"] == 1


def test_ancestor_chain_anchor_excludes_deleted_scope_rows(monkeypatch):
    """[P2] 삭제된 stale 스코프 id 로 체인을 열면 지운 파일의 계보가 되살아난다."""
    monkeypatch.setenv("ATTACHMENT_IDS", "30")
    import shared.config as _cfg
    monkeypatch.setattr(_cfg, "get_active_conversation_id", lambda: "conv-x")
    # 앵커 조회가 (삭제 술어 때문에) 0행 → 체인 집합 없음 → 거부.
    conn = _ancestor_conn([], (10, "q.sql", "text", "obj/10", "uploaded", None, "user", 1, 50, 10))
    monkeypatch.setattr(agent_core, "_connect_memory", lambda *a, **k: conn)
    assert agent_core._load_ancestor_attachment_row(10) is None
