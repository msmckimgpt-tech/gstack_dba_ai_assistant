"""TASK-0274 (Task⑥): assistant 가 전달받은 첨부를 수정해 새 버전으로 materialize +
대화 진행에 따른 버전 관리 회귀 테스트.

사용자 결정: 수정 범위=텍스트 계열 MVP(csv/text), 확정 방식=assistant 자동 materialize.

신뢰 경계 가드(자동 materialize 는 LLM 이 임의 바이트를 저장하는 표면):
  1. 텍스트 계열 kind(csv/text)만 — 바이너리(xlsx/pdf/image) 거부.
  2. source 첨부는 같은 conversation + 같은 account scope (IDOR/cross-conv 차단).
  3. size cap(per_file/conv/account) 재사용.
  4. turn 당 개수 cap + 내용 size cap.
  5. 새 버전 = 같은 RootAttachmentId 체인, VersionNumber+1, CreatedByRole='assistant',
     직전 최신은 SupersededAt 마킹.

검증(`make test` agent 이미지, DB 없이 monkeypatch):
  P1  _parse_attachment_edit_blocks — 정상 블록 파싱(헤더 JSON + 내용 분리).
  P2  _parse_attachment_edit_blocks — 헤더 JSON 깨짐/소스ID 누락/블록 없음 → 빈 리스트(견고).
  M1  materialize — 정상 텍스트 첨부 → 새 버전 INSERT(version+1, role='assistant') + 부모 supersede.
  M2  materialize — 바이너리 kind(pdf) source → 거부(가드 1).
  M3  materialize — 다른 conversation source → 거부(가드 2).
  M4  materialize — 다른 account source → 거부(가드 2).
  M5  materialize — 내용 size cap 초과 → 거부(가드 4).
  M6  materialize — turn 당 개수 cap 초과분 무시(가드 4).
  S1  _serialize_attachment_for_api — 버전 필드(version_number/root_attachment_id/created_by_role/
      is_assistant_generated/superseded) 직렬화.
  N1  _next_version_filename — 확장자 보존 버전 접미.
  R1  list_conversation_attachments SQL 에 SupersededAt IS NULL 필터 존재(최신만 노출).
"""
from __future__ import annotations

import json

import app
from routers import attachments  # feature-0012 P5b
from routers import conversations  # feature-0012 P5b


# ── fake DB ────────────────────────────────────────────────────────────────
class _Cursor:
    def __init__(self, store):
        self._store = store
        self._rows = []
        self.rowcount = 0
        self.lastrowid = 0

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        self._store.setdefault("executed", []).append((s, params))
        self._rows = []
        # 버전 체인 MAX(VersionNumber) 조회
        if "coalesce(max(versionnumber)" in s:
            self._rows = [(int(self._store.get("max_version", 1)),)]
        # INSERT 새 버전 → lastrowid 발급
        elif "insert into webconversationattachments" in s:
            self._store["insert_params"] = params
            self._store.setdefault("inserts", []).append(params)
            self.lastrowid = int(self._store.get("new_id", 9001))
        # 부모 supersede UPDATE
        elif "set supersededat" in s:
            self._store["superseded_sql"] = (s, params)
            self.rowcount = 1
        # DELETE (MinIO put 실패 rollback)
        elif s.startswith("delete from webconversationattachments"):
            self._store.setdefault("deletes", []).append(params)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _Conn:
    def __init__(self, store):
        self._store = store

    def cursor(self, *a, **k):
        return _Cursor(self._store)

    def commit(self):
        self._store["committed"] = True

    def close(self):
        pass


# ── 가짜 storage_minio 주입 (monkeypatch.setitem → 테스트 종료 시 자동 원복) ──
# materialize 헬퍼는 런타임 경로인 `from web.modules import storage_minio` 를 쓴다.
# 테스트 PYTHONPATH 에는 `web` 패키지가 없으므로(app/modules 가 top-level), sys.modules
# 에 가짜 web/web.modules/web.modules.storage_minio 노드를 monkeypatch.setitem 으로
# 주입한다. setitem 은 teardown 시 원래 값(없으면 삭제)으로 자동 복원하므로 다른 테스트
# (예: `import web.app` 하는 share_redaction)와의 상태 오염이 없다.
class _PutRecorder:
    StorageConfigError = type("StorageConfigError", (Exception,), {})
    StorageOperationError = type("StorageOperationError", (Exception,), {})

    def __init__(self):
        self.calls = []
        self.put_calls = self.calls
        self.fail_put = False

    def make_object_key(self, cid, uuid, filename):
        return f"{cid}/{uuid}/{filename}"

    def put_object_bytes(self, object_key, body, content_type=None, metadata=None):
        if self.fail_put:
            raise self.StorageOperationError("simulated put failure")
        self.calls.append((object_key, body, content_type, metadata))
        return {"ok": True}


def _install_fake_storage(monkeypatch):
    import sys
    import types

    rec = _PutRecorder()
    web_pkg = types.ModuleType("web")
    web_pkg.__path__ = []  # 패키지로 인식되도록
    modules_pkg = types.ModuleType("web.modules")
    modules_pkg.__path__ = []
    modules_pkg.storage_minio = rec
    web_pkg.modules = modules_pkg

    monkeypatch.setitem(sys.modules, "web", web_pkg)
    monkeypatch.setitem(sys.modules, "web.modules", modules_pkg)
    monkeypatch.setitem(sys.modules, "web.modules.storage_minio", rec)
    return rec


def _account(aid=1):
    return {"id": aid, "role": {"key": "operator"}}


def _src_row(*, kind="text", conv="conv-1", aid=1, deleted=False, pending=False, root=None, ver=1):
    return {
        "Id": 100,
        "ConversationId": conv,
        "AccountId": aid,
        "ObjectKey": f"{conv}/uuid/orig.txt",
        "OriginalFilename": "orig.txt",
        "Kind": kind,
        "SizeBytes": 100,
        "DeletedAt": "2026-01-01" if deleted else None,
        "DeletePending": 1 if pending else 0,
        "RootAttachmentId": root,
        "VersionNumber": ver,
        "CreatedByRole": "user",
        "SupersededAt": None,
    }


# ── P1/P2: 파서 ──────────────────────────────────────────────────────────────
def test_p1_parse_valid_block():
    answer = (
        "수정했습니다.\n\n"
        "```attachment-edit\n"
        '{"source_attachment_id": 100, "filename": "fixed.sql"}\n'
        "SELECT 1;\nSELECT 2;\n"
        "```\n"
    )
    blocks = app._parse_attachment_edit_blocks(answer)
    assert len(blocks) == 1
    assert blocks[0]["source_attachment_id"] == 100
    assert blocks[0]["filename"] == "fixed.sql"
    assert "SELECT 1;" in blocks[0]["content"]
    assert "SELECT 2;" in blocks[0]["content"]


def test_p2_parse_robust_to_garbage():
    # 블록 없음
    assert app._parse_attachment_edit_blocks("그냥 텍스트") == []
    # 헤더 JSON 깨짐
    bad = "```attachment-edit\n{not json}\ncontent\n```"
    assert app._parse_attachment_edit_blocks(bad) == []
    # source_attachment_id 누락
    no_id = '```attachment-edit\n{"filename": "x.txt"}\ncontent\n```'
    assert app._parse_attachment_edit_blocks(no_id) == []
    # source_attachment_id <= 0
    zero_id = '```attachment-edit\n{"source_attachment_id": 0}\ncontent\n```'
    assert app._parse_attachment_edit_blocks(zero_id) == []


# ── M1: 정상 materialize ──────────────────────────────────────────────────────
def test_m1_materialize_creates_new_version(monkeypatch):
    storage = _install_fake_storage(monkeypatch)
    store = {"max_version": 1, "new_id": 9001}
    conn = _Conn(store)

    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: (
        _src_row() if int(i) == 100 else {
            "Id": 9001, "ConversationId": "conv-1", "AccountId": 1,
            "OriginalFilename": "orig_v2.txt", "Kind": "text", "SizeBytes": 20,
            "VersionNumber": 2, "RootAttachmentId": 100, "CreatedByRole": "assistant",
            "SupersededAt": None, "DeletedAt": None, "DeletePending": 0,
            "MimeType": "text/plain", "SizeBucket": "<1KB", "Sha256": "x",
            "UploadStatus": "uploaded", "DeleteReason": None, "MetaJson": None,
        }
    ))
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))

    answer = (
        "```attachment-edit\n"
        '{"source_attachment_id": 100}\n'
        "수정된 내용\n"
        "```"
    )
    created = app._materialize_assistant_attachment_edits(
        conn, account=_account(), conversation_id="conv-1", answer=answer, message_id=5,
    )
    assert len(created) == 1
    # INSERT 가 version=2, role='assistant' 로 실행됐는지
    ins = store.get("insert_params")
    assert ins is not None
    # INSERT params 끝부분: ... root_id, next_version (VALUES 순서상 RootAttachmentId, VersionNumber)
    assert 2 in ins, f"VersionNumber=2 가 INSERT params 에 있어야 함: {ins}"
    assert 100 in ins, f"RootAttachmentId=100 이 INSERT params 에 있어야 함: {ins}"
    # MinIO put 호출됨
    assert len(storage.put_calls) == 1
    # 부모 supersede UPDATE 실행됨
    assert "superseded_sql" in store
    # 새 버전 직렬화 결과
    assert created[0]["is_assistant_generated"] is True
    assert created[0]["version_number"] == 2


# ── M2: 바이너리 kind 거부 ────────────────────────────────────────────────────
def test_m2_reject_binary_kind(monkeypatch):
    _install_fake_storage(monkeypatch)
    store = {}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _src_row(kind="pdf"))
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))

    answer = '```attachment-edit\n{"source_attachment_id": 100}\nx\n```'
    created = app._materialize_assistant_attachment_edits(
        conn, account=_account(), conversation_id="conv-1", answer=answer,
    )
    assert created == []
    assert "insert_params" not in store


# ── M3: 다른 conversation source 거부 ────────────────────────────────────────
def test_m3_reject_cross_conversation(monkeypatch):
    _install_fake_storage(monkeypatch)
    store = {}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _src_row(conv="other-conv"))
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))

    answer = '```attachment-edit\n{"source_attachment_id": 100}\nx\n```'
    created = app._materialize_assistant_attachment_edits(
        conn, account=_account(), conversation_id="conv-1", answer=answer,
    )
    assert created == []
    assert "insert_params" not in store


# ── M4: 다른 account source 거부 ─────────────────────────────────────────────
def test_m4_reject_cross_account(monkeypatch):
    _install_fake_storage(monkeypatch)
    store = {}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _src_row(aid=999))
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))

    answer = '```attachment-edit\n{"source_attachment_id": 100}\nx\n```'
    created = app._materialize_assistant_attachment_edits(
        conn, account=_account(aid=1), conversation_id="conv-1", answer=answer,
    )
    assert created == []
    assert "insert_params" not in store


# ── M5: 내용 size cap 초과 거부 ──────────────────────────────────────────────
def test_m5_reject_oversize_content(monkeypatch):
    _install_fake_storage(monkeypatch)
    store = {}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _src_row())
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))

    big = "A" * (app._ASSISTANT_EDIT_SIZE_CAP_BYTES + 1)
    answer = '```attachment-edit\n{"source_attachment_id": 100}\n' + big + "\n```"
    created = app._materialize_assistant_attachment_edits(
        conn, account=_account(), conversation_id="conv-1", answer=answer,
    )
    assert created == []
    assert "insert_params" not in store


# ── M6: turn 당 개수 cap ─────────────────────────────────────────────────────
def test_m6_count_cap(monkeypatch):
    storage = _install_fake_storage(monkeypatch)
    store = {"max_version": 1, "new_id": 9001}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: (
        _src_row() if int(i) == 100 else {
            "Id": 9001, "ConversationId": "conv-1", "AccountId": 1,
            "OriginalFilename": "v2.txt", "Kind": "text", "SizeBytes": 5,
            "VersionNumber": 2, "RootAttachmentId": 100, "CreatedByRole": "assistant",
            "SupersededAt": None, "DeletedAt": None, "DeletePending": 0,
            "MimeType": "text/plain", "SizeBucket": "<1KB", "Sha256": "x",
            "UploadStatus": "uploaded", "DeleteReason": None, "MetaJson": None,
        }
    ))
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))

    # cap+3 개의 블록 — cap 개수만 처리
    one = '```attachment-edit\n{"source_attachment_id": 100}\nx\n```'
    answer = "\n\n".join([one] * (app._ASSISTANT_EDIT_COUNT_CAP + 3))
    created = app._materialize_assistant_attachment_edits(
        conn, account=_account(), conversation_id="conv-1", answer=answer,
    )
    # 최대 cap 개수만 생성 (각 블록이 동일 source 라도 cap 만큼만 시도)
    assert len(created) <= app._ASSISTANT_EDIT_COUNT_CAP
    assert len(storage.put_calls) <= app._ASSISTANT_EDIT_COUNT_CAP


# ── S1: 직렬화 버전 필드 ──────────────────────────────────────────────────────
def test_s1_serialize_version_fields():
    # assistant 생성 v3 (root=100)
    row = {
        "Id": 9003, "ConversationId": "conv-1", "Kind": "text",
        "MimeType": "text/plain", "OriginalFilename": "v3.txt", "SizeBytes": 10,
        "SizeBucket": "<1KB", "Sha256": "x", "UploadStatus": "uploaded",
        "CreatedAt": None, "DeletePending": 0, "DeleteReason": None, "MetaJson": None,
        "DeletedAt": None, "RootAttachmentId": 100, "VersionNumber": 3,
        "CreatedByRole": "assistant", "SupersededAt": None,
    }
    out = app._serialize_attachment_for_api(row)
    assert out["version_number"] == 3
    assert out["root_attachment_id"] == 100
    assert out["created_by_role"] == "assistant"
    assert out["is_assistant_generated"] is True
    assert out["superseded"] is False

    # 루트(원본) — RootAttachmentId NULL → 자기 Id 가 root
    root_row = dict(row)
    root_row.update({"Id": 100, "RootAttachmentId": None, "VersionNumber": 1, "CreatedByRole": "user"})
    out2 = app._serialize_attachment_for_api(root_row)
    assert out2["root_attachment_id"] == 100
    assert out2["is_assistant_generated"] is False
    assert out2["version_number"] == 1


# ── N1: 버전 파일명 ──────────────────────────────────────────────────────────
def test_n1_next_version_filename():
    assert app._next_version_filename("report.csv", 2) == "report_v2.csv"
    assert app._next_version_filename("query.sql", 5) == "query_v5.sql"
    # 확장자 없음
    assert app._next_version_filename("README", 2) == "README_v2"
    # 빈 입력 fallback
    assert app._next_version_filename("", 2) == "edited_v2.txt"


# ── N2: 버전 파일명 idempotent (FR-attachment-update — 이중접미 방지) ──────────
def test_n2_next_version_filename_idempotent():
    # 이미 _v<n> 접미가 있는 이름을 재편집해도 이중접미가 생기지 않는다(원본과 정합).
    assert app._next_version_filename("report_v2.csv", 3) == "report_v3.csv"
    assert app._next_version_filename("data_v10.txt", 11) == "data_v11.txt"
    assert app._next_version_filename("q_v5", 6) == "q_v6"
    # 내부의 _v 는 접미가 아니면 보존(끝의 _v<digits> 만 제거).
    assert app._next_version_filename("v2_report.csv", 2) == "v2_report_v2.csv"


# ── N3: materialize 가 원본 파일명을 승계하고 LLM filename 을 무시 (attach-multi-upload) ──
def test_n3_materialize_inherits_source_filename(monkeypatch):
    storage = _install_fake_storage(monkeypatch)
    store = {"max_version": 1, "new_id": 9010}
    conn = _Conn(store)
    # source = orig.txt (kind text, v1). 버전 체인 스코프가 (conv, account, OriginalFilename)
    # 이므로 편집본 파일명이 원본과 다르면 체인이 갈라진다(사용자 재업로드가 새 root 를 만듦).
    # → 편집본은 **원본 파일명을 그대로 승계**하고, LLM 이 준 이름은 무시한다.
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _src_row())
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))

    answer = (
        "```attachment-edit\n"
        '{"source_attachment_id": 100, "filename": "hacked.exe"}\n'
        "수정된 내용\n"
        "```"
    )
    created = app._materialize_assistant_attachment_edits(
        conn, account=_account(), conversation_id="conv-1", answer=answer, message_id=5,
    )
    assert len(created) == 1
    ins = store.get("insert_params")
    assert ins is not None
    # INSERT params[3] = OriginalFilename(코드가 실제 저장하는 값). LLM 의 hacked.exe 는 통째로
    # 버려지고 source 파일명이 그대로 쓰인다 — 실행파일류 확장자 승격도 정의상 불가능해진다.
    # (created[0] 직렬화는 monkeypatch 된 _load_attachment_row 재조회 결과라 harness 아티팩트
    #  — INSERT param 이 authoritative.)
    assert ins[3] == "orig.txt", f"원본 파일명 승계 실패: {ins[3]!r}"
    assert "_v2" not in ins[3], "저장 파일명에 버전 접미가 붙으면 체인이 이름 기준으로 갈라진다"


# ── N4: 확장자 없는 source → kind 기반 안전 확장자 부여 (§18.8 SEC-1 불변) ──
def test_n4_extensionless_source_forces_safe_ext(monkeypatch):
    _install_fake_storage(monkeypatch)
    store = {"max_version": 1, "new_id": 9011}
    conn = _Conn(store)
    # source 는 확장자 없는 text 첨부(예: 'statement'). LLM 이 x.exe.txt 류 이중확장자를 줘도
    # 유효(trailing) 확장자는 kind 기반 안전값(txt)이어야 하고 .exe 가 유효 확장자로 승격되면 안 된다.
    def _noext_src(c, i):
        r = _src_row()
        r["OriginalFilename"] = "statement"  # 확장자 없음
        r["ObjectKey"] = "conv-1/uuid/statement"
        return r
    monkeypatch.setattr(app, "_load_attachment_row", _noext_src)
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))

    answer = (
        "```attachment-edit\n"
        '{"source_attachment_id": 100, "filename": "statement.exe.txt"}\n'
        "x\n```"
    )
    created = app._materialize_assistant_attachment_edits(
        conn, account=_account(), conversation_id="conv-1", answer=answer, message_id=5,
    )
    assert len(created) == 1
    saved = store["insert_params"][3]
    # 유효(마지막) 확장자는 반드시 안전값 txt (실행파일류 확장자 승격 차단).
    assert saved.rsplit(".", 1)[-1] == "txt", f"유효 확장자가 안전하지 않음: {saved!r}"
    # 확장자 없는 원본은 stem 을 승계하고 안전 확장자만 덧붙인다 — 버전 접미는 붙지 않는다.
    assert saved == "statement.txt", f"확장자 없는 원본의 이름 승계 실패: {saved!r}"


# ── N5: 편집본이 원본 체인의 head 로 이어진다 (이름 분열 회귀 차단) ──────────────
def test_n5_edit_keeps_single_chain_for_reupload(monkeypatch):
    """편집본 파일명 == 원본 파일명 이어야 `_find_latest_same_name_attachment` 가
    사용자 재업로드를 같은 체인의 다음 버전으로 편입한다.

    회귀 배경(2026-08-06 라이브 실측): 편집본이 `x_v2.sql` 로 저장되던 동안 원본 `x.sql` 은
    supersede 되어 head 에서 빠졌고, 사용자가 `x.sql` 을 다시 올리면 같은 이름의 head 가 없어
    **새 root(v1)** 가 생겼다 — 한 논리 파일이 두 체인으로 갈라져 목록에 나란히 남았다(9쌍).
    """
    _install_fake_storage(monkeypatch)
    store = {"max_version": 1, "new_id": 9012}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _src_row())
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))

    answer = '```attachment-edit\n{"source_attachment_id": 100}\n수정\n```'
    app._materialize_assistant_attachment_edits(
        conn, account=_account(), conversation_id="conv-1", answer=answer, message_id=5,
    )
    saved_name = store["insert_params"][3]
    src_name = _src_row()["OriginalFilename"]
    assert saved_name == src_name, (
        f"편집본 파일명이 원본과 다르면 재업로드가 새 체인을 만든다: {saved_name!r} != {src_name!r}")


# ── N6: 다운로드는 v2+ 에서만 응답 파일명에 버전 접미 (저장값 불변) ────────────
def test_n6_download_response_filename_versioned():
    import inspect

    src = inspect.getsource(attachments.download_attachment)
    norm = " ".join(src.split())
    assert "_next_version_filename" in norm, (
        "체인 통합으로 모든 버전이 같은 저장명을 쓰므로, 구버전 다운로드는 응답 파일명에 "
        "버전 접미를 붙여 로컬 최신본 덮어쓰기를 막아야 한다")
    assert "_dl_version > 1" in norm, "v1 은 원본명 그대로여야 한다(불필요한 _v1 접미 금지)"


# ── R1: 목록 SQL 최신버전 필터 (정적 소스 검사) ──────────────────────────────
def test_r1_list_filters_superseded():
    import inspect

    src = inspect.getsource(conversations.list_conversation_attachments)
    norm = " ".join(src.split()).lower()
    assert "supersededat is null" in norm, "목록은 최신 버전만 노출(SupersededAt IS NULL) 해야 함"


# ════════════════════════════════════════════════════════════════════════════
# REQ-20260713-attach-user-version: 사용자 재업로드 → 버전 체인 편입 (해시 대조)
# ════════════════════════════════════════════════════════════════════════════

# ── find 헬퍼 전용 fake conn (dict-cursor fetchone) ──────────────────────────
class _FindCur:
    def __init__(self, row, captured):
        self._row = row
        self._captured = captured

    def execute(self, sql, params=None):
        self._captured["sql"] = sql
        self._captured["params"] = params

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _FindConn:
    def __init__(self, row, captured):
        self._row = row
        self._captured = captured

    def cursor(self, *a, **k):
        return _FindCur(self._row, self._captured)


# ── U1: diff 계산 (pure) ─────────────────────────────────────────────────────
def test_u1_compute_version_diff_basic():
    vd = app._compute_version_diff("a\nb\nc", "a\nB\nc", prev_version=1, new_version=2, filename="q.sql")
    assert vd["from_version"] == 1 and vd["to_version"] == 2
    assert vd["truncated"] is False
    assert "-b" in vd["unified_diff"] and "+B" in vd["unified_diff"]
    # 파일명·버전 헤더가 diff 에 포함(fromfile/tofile).
    assert "q.sql (v1)" in vd["unified_diff"] and "q.sql (v2)" in vd["unified_diff"]


def test_u2_compute_version_diff_truncation():
    big_prev = "x\n" * 5000
    big_new = "y\n" * 5000
    vd = app._compute_version_diff(
        big_prev, big_new, prev_version=1, new_version=2, filename="big.txt", cap_bytes=100)
    assert vd["truncated"] is True
    assert len(vd["unified_diff"].encode("utf-8")) <= 100


# ── U3/U4: 동명파일 최신버전 조회 (체인 편입 판정) ────────────────────────────
def test_u3_find_latest_same_name_match():
    row = {
        "Id": 100, "Sha256": "abc", "OriginalFilename": "report.sql",
        "RootAttachmentId": None, "VersionNumber": 1, "Kind": "text",
        "ObjectKey": "conv-1/uuid/report.sql", "ConversationId": "conv-1", "AccountId": 7,
    }
    cap: dict = {}
    out = app._find_latest_same_name_attachment(_FindConn(row, cap), "conv-1", 7, "report.sql")
    assert out and out["Id"] == 100 and out["Sha256"] == "abc"
    s = " ".join(str(cap["sql"]).split()).lower()
    # 체인 스코프: conversation + account + filename + 최신(head) 만.
    assert "conversationid = %s" in s and "accountid = %s" in s and "originalfilename = %s" in s
    assert "supersededat is null" in s, "체인 head(비-superseded)만 매칭해야 함"
    assert "deletedat is null" in s and "deletepending = 0" in s
    assert tuple(cap["params"]) == ("conv-1", 7, "report.sql")


def test_u4_find_latest_same_name_none_and_guards():
    # 매칭 없음 → None
    assert app._find_latest_same_name_attachment(_FindConn(None, {}), "conv-1", 7, "x.sql") is None
    # 인자 결손(빈 conv / account 0 / 빈 filename) → None (쿼리 미실행 — fail-safe)
    assert app._find_latest_same_name_attachment(_FindConn({"Id": 1}, {}), "", 7, "x") is None
    assert app._find_latest_same_name_attachment(_FindConn({"Id": 1}, {}), "c", 0, "x") is None
    assert app._find_latest_same_name_attachment(_FindConn({"Id": 1}, {}), "c", 7, "") is None


# ── U5: 업로드 핸들러 버전 로직 (정적 소스 검사) ──────────────────────────────
def test_u5_upload_handler_user_version_logic():
    import inspect

    src = inspect.getsource(conversations.upload_conversation_attachment)
    norm = " ".join(src.split())
    # 재업로드 감지: 동명파일 최신버전 조회.
    assert "_find_latest_same_name_attachment" in norm, "재업로드 감지 헬퍼 호출 누락"
    # 해시 일치 → 기존 재사용(멱등) 플래그.
    assert "reused_existing_version" in norm, "동일 해시 재사용 플래그 누락"
    # 새 버전은 사용자 생성.
    assert "'user'" in norm, "새 버전 CreatedByRole='user' 누락"
    # 직전 버전 supersede.
    assert "SET SupersededAt" in norm, "직전 버전 supersede UPDATE 누락"
    # 해시 대조로 버전업 판정(요청: 완전히 같은 파일이 아니라면 버전업).
    assert "sha256_hex" in norm and "Sha256" in norm, "sha256 대조 누락"
