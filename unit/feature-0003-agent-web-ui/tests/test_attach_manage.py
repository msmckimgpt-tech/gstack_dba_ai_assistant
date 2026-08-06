"""REQ-20260806-attach-manage: 첨부 삭제(버전 선택)·복구·일괄 다운로드 회귀 테스트.

`ADR-20260729T163000-attach-append-only`(삭제 UI 철회)를 supersede 하며 삭제 경로가
돌아오므로, 그때 "별도 판단 대상" 으로 이월됐던 **인가 경계 결함**을 여기서 잠근다 —
종전엔 열람 헬퍼(`_account_can_access_attachment`)를 삭제에 재사용해 그룹 멤버 전원이
남의 첨부를 지울 수 있었다.

검증(`make test` agent 이미지, DB 없이 fake cursor + monkeypatch):

  인가 경계 (D3, AC-3)
    A1  upload.any 보유 → 통과 (관리·보존정책 경로).
    A2  upload.own + 업로더 본인 → 통과.
    A3  upload.own + 대화 소유자(업로더 아님) → 통과.
    A4  upload.own + 그룹 멤버 단독(업로더도 소유자도 아님) → **거부** — 원 결함.
    A5  권한 없음 → 거부.
    A6  soft-deleted 행도 통과 — 복구 경로가 쓴다(열람 헬퍼는 DeletedAt 이면 거부).
    A7  구조 가드(§16.7 G10): 삭제·복구 핸들러가 열람 헬퍼를 쓰지 않는다.

  scope 계약 (AC-1/AC-2)
    S1  version/chain 정규화 + 대소문자·공백 허용.
    S2  허용 밖 값(오타)은 None → 400. 기본값으로 조용히 격하하지 않는다.
    S3  _root_id_of — RootAttachmentId 우선, 없으면 자기 Id.

  버전 승격 (D5, AC-1)
    P1  미삭제 최신을 SupersededAt=NULL 로 승격하고 나머지는 스탬프를 채운다.
    P2  미삭제 행이 없으면 None (chain 삭제 후).
    P3  승격 대상 판정은 VersionNumber 최대 — Id 순서가 아니다.

  복구 가능 판정 (AC-4)
    R1  DeletePending=0 → 복구 대상 아님(이미 활성).
    R2  UploadStatus='deleted' → 대상 아님(객체가 이미 없다).
    R3  retention 창 안 → 대상.
    R4  retention 만료 → 대상 아님.

  일괄 다운로드 (AC-6~AC-9)
    Z1  ZIP 엔트리명 — 전 버전 모드는 _v<n> 접미.
    Z2  같은 이름 충돌 시 id 를 덧붙여 덮어쓰기를 막는다.
    Z3  경로 구분자·상위 참조 제거(zip-slip).
    Z4  상한 초과는 부분 ZIP 이 아니라 413 (§16.7 G9-b 무음 절단 금지).

  휴지통 (AC-5)
    T1  휴지통 SQL 은 DeletePending=1 AND UploadStatus <> 'deleted'.
"""
from __future__ import annotations

import datetime as dt
import inspect
import re

import app
from routers import attachments as att
from routers import conversations as convs


# ── fake DB ────────────────────────────────────────────────────────────────
class _Cursor:
    def __init__(self, store):
        self._store = store
        self._rows: list = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split())
        self._store.setdefault("executed", []).append((s, params))
        low = s.lower()
        self._rows = []
        if "from webconversationattachments" in low and low.startswith("select"):
            self._rows = list(self._store.get("chain_rows", []))
        elif low.startswith("update"):
            self.rowcount = int(self._store.get("update_rowcount", 1))

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        pass


class _Conn:
    def __init__(self, store):
        self._store = store

    def cursor(self, dictionary=False):
        return _Cursor(self._store)

    def commit(self):
        self._store["committed"] = True

    def close(self):
        pass


def _row(**kw):
    base = {
        "Id": 1,
        "ConversationId": "conv-1",
        "AccountId": 10,
        "ObjectKey": "obj/1",
        "OriginalFilename": "report.csv",
        "SizeBytes": 100,
        "UploadStatus": "ingested",
        "DeletePending": 0,
        "DeleteReason": "user",
        "DeletedAt": None,
        "RootAttachmentId": None,
        "VersionNumber": 1,
        "SupersededAt": None,
    }
    base.update(kw)
    return base


def _perm_stub(monkeypatch, granted: set[str]):
    monkeypatch.setattr(
        app, "_account_has_permission",
        lambda account, code: code in granted, raising=False)


def _owner_stub(monkeypatch, is_owner: bool):
    monkeypatch.setattr(
        app, "_conversation_owned_by_account",
        lambda conn, cid, acct: bool(is_owner), raising=False)


# ── A. 인가 경계 ───────────────────────────────────────────────────────────
def test_a1_upload_any_passes(monkeypatch):
    _perm_stub(monkeypatch, {"conversation.attachment.upload.any"})
    _owner_stub(monkeypatch, False)
    conn = _Conn({})
    # 업로더도 소유자도 아니지만 .any 보유 → 통과.
    assert att._account_can_manage_attachment(conn, {"id": 99}, _row(AccountId=10)) is True


def test_a2_uploader_self_passes(monkeypatch):
    _perm_stub(monkeypatch, {"conversation.attachment.upload.own"})
    _owner_stub(monkeypatch, False)
    # 업로더 본인이되 **현재 멤버**여야 한다(t6 이 그 경계를 지킨다).
    monkeypatch.setattr(app, "_account_is_conversation_member", lambda cid, acct: True, raising=False)
    conn = _Conn({})
    assert att._account_can_manage_attachment(conn, {"id": 10}, _row(AccountId=10)) is True


def test_a3_conversation_owner_passes(monkeypatch):
    _perm_stub(monkeypatch, {"conversation.attachment.upload.own"})
    _owner_stub(monkeypatch, True)
    conn = _Conn({})
    # 남이 올린 첨부라도 대화 주인이면 정리할 수 있다(D3).
    assert att._account_can_manage_attachment(conn, {"id": 77}, _row(AccountId=10)) is True


def test_a4_group_member_alone_is_denied(monkeypatch):
    """원 결함의 회귀 잠금 — 그룹 멤버라는 사실만으로는 남의 첨부를 지울 수 없다.

    종전 삭제 경로는 `_account_can_access_attachment` 를 재사용했고, 그 헬퍼는
    `_account_is_conversation_member` 로 그룹 멤버 전원을 통과시켰다.
    """
    _perm_stub(monkeypatch, {"conversation.attachment.upload.own"})
    _owner_stub(monkeypatch, False)
    # 멤버십 헬퍼가 True 를 돌려줘도 결과가 바뀌면 안 된다 — 아예 참조하지 않아야 한다.
    monkeypatch.setattr(app, "_account_is_conversation_member", lambda cid, acct: True, raising=False)
    conn = _Conn({})
    assert att._account_can_manage_attachment(conn, {"id": 77}, _row(AccountId=10)) is False


def test_a5_no_permission_denied(monkeypatch):
    _perm_stub(monkeypatch, set())
    _owner_stub(monkeypatch, True)
    conn = _Conn({})
    assert att._account_can_manage_attachment(conn, {"id": 10}, _row(AccountId=10)) is False


def test_a6_soft_deleted_row_still_manageable(monkeypatch):
    """복구 경로가 성립하려면 삭제된 행에도 인가가 나야 한다."""
    _perm_stub(monkeypatch, {"conversation.attachment.upload.own"})
    _owner_stub(monkeypatch, False)
    monkeypatch.setattr(app, "_account_is_conversation_member", lambda cid, acct: True, raising=False)
    conn = _Conn({})
    row = _row(AccountId=10, DeletePending=1, DeletedAt=dt.datetime.utcnow())
    assert att._account_can_manage_attachment(conn, {"id": 10}, row) is True


def _called_names(fn) -> set[str]:
    """함수 본문에서 실제로 **호출되는** 이름 집합. 주석·docstring 언급은 세지 않는다
    — 문자열 검사로 하면 '왜 이 헬퍼를 쓰지 않는가' 를 적은 주석이 스스로를 red 로 만든다.
    """
    import ast
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                names.add(f.id)
            elif isinstance(f, ast.Attribute):
                names.add(f.attr)
    return names


def test_a7_delete_restore_handlers_do_not_use_read_gate():
    """§16.7 G10 구조 가드 — 삭제·복구 핸들러가 열람 헬퍼로 되돌아가는 것을 막는다.

    이 결함 클래스(열람 경계를 파괴적 동작에 재사용)는 이미 한 번 라이브에 나갔다.
    점수정으로 끝내지 않고 호출 형태 자체를 AST 로 단정한다.
    """
    for fn in (att.delete_attachment, att.restore_attachment):
        called = _called_names(fn)
        assert "_account_can_access_attachment" not in called, (
            f"{fn.__name__} 이 열람 헬퍼를 호출한다 — 삭제/복구는 _account_can_manage_attachment 만 사용")
        assert "_account_can_manage_attachment" in called, (
            f"{fn.__name__} 이 관리 인가 헬퍼를 호출하지 않는다")


def test_a8_read_paths_keep_using_read_gate():
    """역방향 가드 — 열람 경로가 관리 게이트로 넘어가면(더 좁은 판정) 그룹 멤버가
    남의 첨부를 **읽지도** 못하게 되는 회귀가 된다. 두 경계는 서로 다른 것을 지킨다.
    """
    for fn in (att.get_attachment_metadata, att.download_attachment, att.get_attachment_versions):
        called = _called_names(fn)
        assert "_account_can_access_attachment" in called, f"{fn.__name__} 의 열람 게이트가 사라졌다"


# ── S. scope 계약 ──────────────────────────────────────────────────────────
def test_s1_scope_normalization():
    assert att._normalize_scope(None) == "version"
    assert att._normalize_scope("version") == "version"
    assert att._normalize_scope(" Chain ") == "chain"


def test_s2_invalid_scope_is_rejected_not_defaulted():
    """오타를 기본값으로 삼키면 '전체 삭제' 의도가 조용히 '한 버전' 으로 격하된다."""
    assert att._normalize_scope("chian") is None
    assert att._normalize_scope("all") is None


def test_s3_root_id_of():
    assert att._root_id_of(_row(Id=5, RootAttachmentId=None)) == 5
    assert att._root_id_of(_row(Id=7, RootAttachmentId=5)) == 5
    assert att._root_id_of(None) == 0


# ── P. 버전 승격 ───────────────────────────────────────────────────────────
def test_p1_promote_latest_alive_version():
    store = {"chain_rows": [
        _row(Id=1, VersionNumber=1, SupersededAt=dt.datetime.utcnow()),
        _row(Id=2, VersionNumber=2, SupersededAt=dt.datetime.utcnow()),
        _row(Id=3, VersionNumber=3, DeletePending=1),  # 방금 지운 최신
    ]}
    conn = _Conn(store)
    promoted = att._promote_latest_version(conn, 1)
    assert promoted == 2
    updates = [(s, p) for s, p in store["executed"] if s.lower().startswith("update")]
    # SQL **문자열**만 보면 바인딩이 틀려도(예: 루트를 승격) 통과한다 — params 를 값으로 단정.
    null_upd = [(s, p) for s, p in updates if "SET SupersededAt = NULL" in s]
    assert null_upd, "승격 UPDATE 가 없다"
    assert null_upd[0][1] == (2,), f"엉뚱한 행을 승격한다: params={null_upd[0][1]}"
    # 그리고 그 UPDATE 는 삭제된 행을 되살리지 않도록 DeletedAt 가드를 건다.
    assert "DeletedAt IS NULL" in null_upd[0][0]
    stamp_upd = [(s, p) for s, p in updates if "COALESCE(SupersededAt, UTC_TIMESTAMP(6))" in s]
    assert stamp_upd, "강등 UPDATE 가 없다"
    # 강등에서 제외되는 id 가 승격 대상과 같아야 한다(마지막 바인딩).
    assert stamp_upd[0][1][-1] == 2, f"강등 제외 대상이 승격 대상과 다르다: {stamp_upd[0][1]}"


def test_p4_chain_sql_includes_root_row_itself():
    """`WHERE (RootAttachmentId = %s OR Id = %s)` 의 뒷항을 지우면 **RootAttachmentId 가
    NULL 인 루트 원본**이 체인에서 빠진다 — chain 삭제가 원본을 남기고 승격이 엉뚱한
    행을 고른다. fake cursor 는 WHERE 를 흉내내지 않으므로 SQL 을 직접 단정한다."""
    store = {"chain_rows": []}
    att._load_attachment_chain(_Conn(store), 7)
    sql, params = store["executed"][0]
    assert "(RootAttachmentId = %s OR Id = %s)" in sql, f"루트 원본이 체인에서 빠진다: {sql}"
    assert params == (7, 7)
    assert "DeletedAt IS NULL" in sql, "include_deleted=False 인데 삭제분을 함께 읽는다"


def test_p5_chain_sql_include_deleted_and_lock():
    store = {"chain_rows": []}
    att._load_attachment_chain(_Conn(store), 7, include_deleted=True, for_update=True)
    sql, _ = store["executed"][0]
    assert "DeletedAt IS NULL" not in sql
    assert sql.rstrip().endswith("FOR UPDATE")


def test_p2_promote_returns_none_when_chain_fully_deleted():
    store = {"chain_rows": [
        _row(Id=1, VersionNumber=1, DeletePending=1),
        _row(Id=2, VersionNumber=2, DeletePending=1),
    ]}
    assert att._promote_latest_version(_Conn(store), 1) is None


def test_p3_promotion_uses_version_number_not_id():
    """Id 가 큰 행이 반드시 최신 버전은 아니다(백필·재삽입)."""
    store = {"chain_rows": [
        _row(Id=91, VersionNumber=1),
        _row(Id=12, VersionNumber=2),
    ]}
    assert att._promote_latest_version(_Conn(store), 91) == 12


# ── R. 복구 가능 판정 ──────────────────────────────────────────────────────
def test_r1_active_row_is_not_restorable():
    assert att._is_restorable(_row(DeletePending=0)) is False


def test_r2_purged_row_is_not_restorable():
    """worker 가 MinIO 객체까지 지운 뒤엔 DB 플래그를 되돌려도 본문이 없다."""
    row = _row(DeletePending=1, UploadStatus="deleted", DeletedAt=dt.datetime.utcnow())
    assert att._is_restorable(row) is False


def test_r3_within_retention_is_restorable(monkeypatch):
    monkeypatch.setenv("ATTACHMENT_RECON_RETENTION_DAYS", "30")
    row = _row(DeletePending=1, DeletedAt=dt.datetime.utcnow() - dt.timedelta(days=3))
    assert att._is_restorable(row) is True


def test_r4_expired_is_not_restorable(monkeypatch):
    monkeypatch.setenv("ATTACHMENT_RECON_RETENTION_DAYS", "30")
    row = _row(DeletePending=1, DeleteReason="user",
               DeletedAt=dt.datetime.utcnow() - dt.timedelta(days=31))
    assert att._is_restorable(row) is False


def test_r5_conv_soft_cascade_is_not_restorable():
    """P1 회귀 — 대화 soft-delete 의 cascade(`conv_soft`)를 첨부 복구 경로가 되살리면
    삭제된 대화의 파일이 되돌아온다. 그 복구는 대화 복구 흐름의 책임이다.
    """
    row = _row(DeletePending=1, DeleteReason="conv_soft", DeletedAt=dt.datetime.utcnow())
    assert att._is_restorable(row) is False


def test_r6_admin_purge_and_legal_are_not_restorable():
    """P1 회귀 — 관리자 purge·법적 삭제(BRIEFING D6 taxonomy)를 사용자 회수 경로가
    되돌릴 수 있으면 그 삭제가 무력화된다.
    """
    for reason in ("admin_purge", "legal"):
        row = _row(DeletePending=1, DeleteReason=reason, DeletedAt=dt.datetime.utcnow())
        assert att._is_restorable(row) is False, f"{reason} 이 복구 가능으로 판정됨"


def test_r7_restore_sql_reasserts_reason_in_where():
    """판정(`_is_restorable`)과 실행(UPDATE) 사이에 worker 가 상태를 바꿀 수 있다 —
    WHERE 절이 같은 경계를 다시 걸어야 TOCTOU 로 새지 않는다.
    """
    src = " ".join(inspect.getsource(att.restore_attachment).split())
    assert "DeleteReason = %s" in src or "DeleteReason = 'user'" in src, (
        "restore UPDATE 의 WHERE 가 DeleteReason 을 재확인하지 않는다")
    assert "UploadStatus <> 'deleted'" in src


def test_r8_trash_list_matches_restorable_boundary():
    """휴지통에 보이는데 복구가 409 나면 사용자는 고장으로 읽는다 — 두 경계가 같아야 한다."""
    src = " ".join(inspect.getsource(convs._list_deleted_conversation_attachments).split())
    assert "DeleteReason = 'user'" in src


# ── X. 원자성 (P1) ─────────────────────────────────────────────────────────
def test_x1_delete_wraps_update_and_promotion_in_one_transaction():
    """P1 회귀 — 삭제 UPDATE 와 승격 UPDATE 가 별개 커밋이면, 승격이 실패했을 때
    '최신본만 지운 체인' 이 목록에서 통째로 사라진 상태가 커밋된다(목록은
    `SupersededAt IS NULL` 을 본다).
    """
    for fn in (att.delete_attachment, att.restore_attachment):
        called = _called_names(fn)
        assert "_begin_tx" in called, f"{fn.__name__} 이 트랜잭션을 열지 않는다"
        assert "rollback" in called, f"{fn.__name__} 에 rollback 경로가 없다"
        assert "commit" in called


def test_x2_promotion_propagates_failure():
    """승격이 예외를 삼키면 호출측이 rollback 할 근거를 잃는다 — fail-soft 금지."""
    src = inspect.getsource(att._promote_latest_version)
    body = src.split('"""', 2)[-1]  # docstring 제외
    assert "except Exception" not in body, (
        "_promote_latest_version 이 예외를 삼킨다 — 트랜잭션 롤백이 불가능해진다")


def test_x3_chain_load_locks_rows_under_transaction():
    """두 요청이 같은 체인을 동시에 처리하면 각자 다른 '최신' 을 계산해 두 행이
    `SupersededAt=NULL` 이 될 수 있다 — 목록에 같은 첨부가 두 번 나온다.
    """
    src = inspect.getsource(att._load_attachment_chain)
    assert "FOR UPDATE" in src
    for fn in (att.delete_attachment, att.restore_attachment):
        fnsrc = " ".join(inspect.getsource(fn).split())
        assert "for_update=in_tx" in fnsrc, f"{fn.__name__} 이 체인을 잠그지 않는다"


# ── Z. 일괄 다운로드 ───────────────────────────────────────────────────────
def test_z1_zip_entry_name_versioned():
    used: set[str] = set()
    name = convs._zip_entry_name(_row(Id=3, OriginalFilename="a.csv", VersionNumber=2),
                                 with_version=True, used=used)
    assert name == "a_v2.csv"


def test_z2_zip_entry_name_collision_gets_id():
    """같은 이름이 두 번 들어가면 압축 해제 시 한쪽이 조용히 사라진다."""
    used: set[str] = set()
    first = convs._zip_entry_name(_row(Id=3, OriginalFilename="a.csv"), with_version=False, used=used)
    second = convs._zip_entry_name(_row(Id=4, OriginalFilename="a.csv"), with_version=False, used=used)
    assert first == "a.csv"
    assert second == "a_4.csv"
    assert first != second


def test_z3_zip_entry_name_strips_path_traversal():
    used: set[str] = set()
    name = convs._zip_entry_name(_row(Id=9, OriginalFilename="../../etc/passwd"),
                                 with_version=False, used=used)
    assert "/" not in name and ".." not in name
    assert name == "passwd"


def test_z5_zip_entry_name_survives_fallback_recollision():
    """id 접미 **한 번**으로는 부족하다 — 다른 첨부가 이미 그 이름을 선점하면 fallback 이
    다시 충돌해 압축 해제 시 한쪽이 조용히 덮인다."""
    used: set[str] = set()
    names = [
        convs._zip_entry_name(_row(Id=7, OriginalFilename="a_4.csv"), with_version=False, used=used),
        convs._zip_entry_name(_row(Id=3, OriginalFilename="a.csv"), with_version=False, used=used),
        convs._zip_entry_name(_row(Id=4, OriginalFilename="a.csv"), with_version=False, used=used),
    ]
    assert len(set(n.lower() for n in names)) == len(names), f"ZIP 안 이름 중복: {names}"


def test_z6_zip_entry_name_is_case_insensitive_unique():
    """대소문자 무시 파일시스템에서 `A.csv` 가 `a.csv` 를 덮는다."""
    used: set[str] = set()
    a = convs._zip_entry_name(_row(Id=1, OriginalFilename="a.csv"), with_version=False, used=used)
    b = convs._zip_entry_name(_row(Id=2, OriginalFilename="A.csv"), with_version=False, used=used)
    assert a.lower() != b.lower(), f"대소문자만 다른 중복: {a} / {b}"


def test_z7_bulk_download_is_conversation_scoped():
    """`WHERE ConversationId = %s` 가 사라지면 **남의 대화 첨부가 원본 바이트로 반출**된다.
    이 경로가 가장 무겁다 — 목록 노출이 아니라 파일 그 자체가 나간다."""
    src = " ".join(inspect.getsource(convs.bulk_download_conversation_attachments).split())
    assert "WHERE ConversationId = %s AND DeletedAt IS NULL" in src
    # 공유창 window clip (SECURITY §21.2 AR-2) — bounded 멤버가 floor 이전 구간을 전량
    # 반출하던 경로. 판정은 fork 와 같은 헬퍼를 쓴다.
    called = _called_names(convs.bulk_download_conversation_attachments)
    assert "_resolve_copy_window" in called, "공유창 window 를 해석하지 않는다"
    assert "_attachment_outside_window" in called, "window 밖 첨부를 clip 하지 않는다"


def test_z8_trash_list_is_conversation_scoped():
    src = " ".join(inspect.getsource(convs._list_deleted_conversation_attachments).split())
    assert "WHERE ConversationId = %s" in src


def test_z9_ids_parse_failure_is_rejected_not_widened():
    """`ids` 파싱 실패를 '필터 없음' 으로 흘리면 3개를 고른 사용자가 대화 전량을 받는다
    — scope 오타를 400 으로 막는 것과 같은 원칙의 반대 방향(무음 확대)."""
    src = " ".join(inspect.getsource(convs.bulk_download_conversation_attachments).split())
    assert "if _ids_raw and not id_filter:" in src
    assert "유효한 첨부 id 가 없습니다" in src


def test_z10_audit_actions_are_registered_in_builder():
    """신규 audit 액션이 builder allowlist 에 없으면 `ValueError` → `_audit_user_action`
    이 삼켜 **감사 행이 0** 이 된다(라우터 except 는 재-raise 가 없어 발화조차 안 함).
    파괴·반출 경로가 조용히 무감사가 되는 구조라 값으로 확인한다."""
    from routers import _audit_infra
    for action in ("attachment.restore", "attachment.bulk_download", "attachment.delete"):
        payload, redacted = _audit_infra.build_audit_change_json(
            action=action, before=None, after=None,
            request_ctx={"conversation_id": "c1", "scope": "chain", "restored_count": 2,
                         "deleted_count": 2, "requested_count": 3, "packed_count": 3},
        )
        assert isinstance(payload, dict), f"{action} 이 builder 에 등록되지 않았다"


def test_z4_zip_cap_is_declared_not_silently_truncated(monkeypatch):
    """상한은 '몇 개만 담기' 가 아니라 '알리고 거부' 여야 한다(§16.7 G9-b)."""
    monkeypatch.setenv("ATTACHMENT_BULK_ZIP_MAX_BYTES", "1024")
    assert convs._bulk_zip_max_bytes() == 1024
    src = inspect.getsource(convs.bulk_download_conversation_attachments)
    # 상한 분기가 413 을 돌려주고, 그 뒤로 ZIP 을 만들지 않는다.
    assert "413" in src
    cap_pos = src.index("_bulk_zip_max_bytes()")
    zip_pos = src.index("zipfile.ZipFile")
    assert cap_pos < zip_pos, "상한 검사가 ZIP 생성보다 뒤에 있으면 부분 ZIP 이 만들어진다"


# ── T. 휴지통 ──────────────────────────────────────────────────────────────
def test_t1_trash_query_excludes_purged():
    src = inspect.getsource(convs._list_deleted_conversation_attachments)
    norm = " ".join(src.split()).lower()
    assert "deletepending = 1" in norm
    assert "uploadstatus <> 'deleted'" in norm


def test_t2_active_list_contract_unchanged():
    """휴지통 추가가 기존 active 목록 계약(최신·미삭제)을 건드리지 않았는지."""
    src = inspect.getsource(convs.list_conversation_attachments)
    norm = " ".join(src.split())
    assert "DeletedAt IS NULL AND SupersededAt IS NULL" in norm


def test_t4_trash_boundaries_match_restorable(monkeypatch):
    """휴지통 SQL 이 `_is_restorable` 의 네 경계를 **모두** 건다 — 하나라도 빠지면
    "보이는데 복구는 409" 가 되어 사용자는 고장으로 읽는다. retention 은 문자열이
    아니라 실제 파라미터로 전달되는지 값으로 확인한다."""
    src = " ".join(inspect.getsource(convs._list_deleted_conversation_attachments).split())
    for frag in ("DeletePending = 1", "DeleteReason = 'user'", "UploadStatus <> 'deleted'",
                 "DeletedAt > UTC_TIMESTAMP(6) - INTERVAL %s DAY", "LIMIT 200"):
        assert frag in src, f"휴지통 SQL 에 {frag} 가 없다"


def test_t5_trash_filters_rows_server_side(monkeypatch):
    """`can_manage=false` 행을 **반환하지 않는다**. 표시만 숨기면 원본 파일명·크기·
    sha256 이 응답에 그대로 실려, 삭제 전 전원이 보던 것이 삭제 후에도 계속 보인다."""
    rows = [_row(Id=1, AccountId=10, DeletePending=1, DeleteReason="user"),
            _row(Id=2, AccountId=99, DeletePending=1, DeleteReason="user")]
    conn = _Conn({"chain_rows": rows})
    monkeypatch.setattr(app, "_manage_gate_for_conversation",
                        lambda c, a, cid: (lambda r: int(r.get("AccountId") or 0) == 10), raising=False)
    monkeypatch.setattr(app, "_serialize_attachment_for_api",
                        lambda r, **kw: {"id": int(r.get("Id") or 0)}, raising=False)
    resp = convs._list_deleted_conversation_attachments(conn, "conv-1", {"id": 10})
    import json as _json
    payload = _json.loads(bytes(resp.body).decode("utf-8"))
    got = [a["id"] for a in payload["attachments"]]
    assert got == [1], f"남의 삭제 첨부가 응답에 실렸다: {got}"


def test_t6_manage_gate_requires_current_conversation_access(monkeypatch):
    """그룹에서 kick 당한 이탈자가 자기 파일을 되살리거나 지울 수 있으면, 그 방을 볼 수
    없는 사람이 그 방의 내용을 바꾸는 셈이다(열람 게이트와 비대칭)."""
    _perm_stub(monkeypatch, {"conversation.attachment.upload.own"})
    _owner_stub(monkeypatch, False)
    monkeypatch.setattr(app, "_account_is_conversation_member", lambda cid, acct: False, raising=False)
    conn = _Conn({})
    # 업로더 본인이지만 더 이상 멤버가 아니다 → 거부.
    assert att._account_can_manage_attachment(conn, {"id": 10}, _row(AccountId=10)) is False
    # 멤버로 복귀하면 통과 — 게이트가 멤버십만으로 열리지 않는지도 위 a4 가 지킨다.
    monkeypatch.setattr(app, "_account_is_conversation_member", lambda cid, acct: True, raising=False)
    assert att._account_can_manage_attachment(conn, {"id": 10}, _row(AccountId=10)) is True


# ── M. PG 미러 (라이브 read 경로) ──────────────────────────────────────────
def test_m1_mirror_covers_whole_chain(monkeypatch):
    """`_promote_latest_version` 은 승격 행뿐 아니라 **강등 행들**도 바꾼다. 변경분만
    미러하면 PG 에 `superseded_at IS NULL` 이 둘 남아, PG read(라이브 기본)가 같은
    첨부를 두 줄로 반환한다 — 다음 write 까지 영구히 어긋난다."""
    chain = [_row(Id=100, VersionNumber=1), _row(Id=101, VersionNumber=2)]
    conn = _Conn({"chain_rows": chain})
    seen: list[list[int]] = []
    monkeypatch.setattr(att, "_mirror_attachment_ids", lambda c, ids: seen.append(sorted(set(ids))), raising=False)
    att._mirror_chain(conn, 100, [101])
    assert seen and set(seen[0]) >= {100, 101}, f"강등 형제가 미러에서 빠졌다: {seen}"


def test_m2_handlers_mirror_chain_not_just_targets():
    for fn in (att.delete_attachment, att.restore_attachment):
        called = _called_names(fn)
        assert "_mirror_chain" in called, f"{fn.__name__} 이 체인 전량을 미러하지 않는다"


def test_t3_list_exposes_can_manage_from_same_gate():
    """표시(can_manage)와 집행이 같은 술어를 쓰는지 — §16.7 G6.

    프론트가 소유권을 따로 추정하면 '보이는데 404' 또는 '숨겨졌는데 권한 있음' 이 된다.
    """
    for fn in (convs.list_conversation_attachments,
               convs._list_deleted_conversation_attachments,
               att.get_attachment_versions):
        src = inspect.getsource(fn)
        assert "_manage_gate_for_conversation" in src, f"{fn.__name__} 이 can_manage 를 별도 계산한다"
        assert re.search(r'\[["\']can_manage["\']\]\s*=', src), f"{fn.__name__} 이 can_manage 를 내리지 않는다"
