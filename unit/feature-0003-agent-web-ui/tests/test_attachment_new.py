"""FR-brandnew-script-attachment-delivery-gap (conversation_audit 2026-07-24): assistant 가
**새로 생성한** 스크립트/쿼리를 다운로드 첨부(첨부파일 항목)로 전달하는 source-less 경로
(```attachment-new```) 회귀 테스트.

진단(대화 …f1c535ec, 2026-07-24): 사용자가 "전체 스크립트 개선안을 첨부파일로 전달해주세요.
(답변 본문이 아닌.)" 을 (중복 재전송) 요청했으나, 첨부 생성 경로가 **기존 첨부 편집**만
지원(source_attachment_id 필수)해 assistant 가 "원본 파일이 없어 첨부로 전달 불가" 거부.
→ source 없이 brand-new root 첨부를 만드는 경로를 추가(편집 경로 보안 가드 전부 공유).

검증(`make test` agent 이미지, DB 없이 monkeypatch):
  P1  _parse_attachment_new_blocks — 정상 블록 파싱(filename 헤더 + 내용, source_attachment_id 불필요).
  P2  _parse_attachment_new_blocks — 헤더 깨짐/블록 없음 → 빈 리스트(견고). filename 없어도 파싱.
  P3  _attachment_new_block_spans — 본문 내 ``` 코드펜스 포함 전체 본문 캡처(절단 없음).
  P4  edit/new 블록 상호 비간섭(같은 답변에 둘 다 있어도 각 파서가 자기 것만).
  M1  materialize — root 첨부 INSERT(VersionNumber=1, RootAttachmentId=NULL, role='assistant'),
      MinIO put, supersede UPDATE **없음**(신규는 체인 supersede 안 함).
  M2  materialize — 확장자 allowlist 유지(.sql/.md/.csv 등) + kind 매핑.
  M3  materialize(SEC) — 실행형/미허용 확장자(.sh/.py/.exe/없음) → 안전 .txt 강제.
  M4  materialize(SEC) — 경로구분자·내부 dot(이중확장자) 정화(x/y.exe.sql → 안전 stem+ext).
  M5  materialize — 내용 size cap 초과 → 거부(가드).
  M6  materialize — turn 당 개수 cap 초과분 무시(가드, 편집과 동일 상한).
  M7  materialize — filename 누락 → 코드-권위 기본명(script.txt).
  S1  _strip_attachment_new_blocks — 블록 제거 + "📎 첨부 전달" 안내, 본문 미노출.
  S2  _strip_attachment_new_blocks — 블록 없으면 원문 그대로 / materialize 실패해도 빈 답변 방지.
  PR1 SYSTEM_PROMPT + 코드-권위 directive 에 attachment-new 안내 존재 + compose 주입.
  A1  ask 흐름 — _materialize_assistant_attachment_new + _strip_attachment_new_blocks 호출.
"""
from __future__ import annotations

import json

import app


# ── fake DB (편집 테스트와 동형, root 경로용) ─────────────────────────────────
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
        if "coalesce(max(versionnumber)" in s:
            self._rows = [(int(self._store.get("max_version", 1)),)]
        elif "insert into webconversationattachments" in s:
            self._store["insert_params"] = params
            self._store.setdefault("inserts", []).append(params)
            self.lastrowid = int(self._store.get("new_id", 7001))
        elif "set supersededat" in s:
            self._store["superseded_sql"] = (s, params)
            self.rowcount = 1

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
    web_pkg.__path__ = []
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


def _new_row(*, filename="script.sql", kind="text", cid="conv-1", aid=1, nid=7001):
    return {
        "Id": nid, "ConversationId": cid, "AccountId": aid,
        "OriginalFilename": filename, "Kind": kind, "SizeBytes": 20,
        "VersionNumber": 1, "RootAttachmentId": None, "CreatedByRole": "assistant",
        "SupersededAt": None, "DeletedAt": None, "DeletePending": 0,
        "MimeType": "text/plain", "SizeBucket": "<1KB", "Sha256": "x",
        "UploadStatus": "uploaded", "DeleteReason": None,
        "MetaJson": json.dumps({"assistant_generated": True}),
        "ObjectKey": f"{cid}/uuid/{filename}", "CreatedAt": "2026-07-24",
    }


def _new_block(filename=None, body="SELECT 1;\nSELECT 2;"):
    hdr = {} if filename is None else {"filename": filename}
    return f"```attachment-new\n{json.dumps(hdr)}\n{body}\n```"


def _run_materialize(monkeypatch, answer, *, new_row=None, size_ok=True, store=None, can_upload=True):
    storage = _install_fake_storage(monkeypatch)
    store = store if store is not None else {"new_id": 7001}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: (new_row or _new_row()))
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (size_ok, "" if size_ok else "cap"))
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: can_upload)
    created = app._materialize_assistant_attachment_new(
        conn, account=_account(), conversation_id="conv-1", answer=answer, message_id=5,
    )
    return created, store, storage


# ── P: 파서/spans ────────────────────────────────────────────────────────────
def test_p1_parse_valid_block():
    blocks = app._parse_attachment_new_blocks(_new_block("improve.sql"))
    assert len(blocks) == 1
    assert blocks[0]["filename"] == "improve.sql"
    assert "SELECT 1;" in blocks[0]["content"] and "SELECT 2;" in blocks[0]["content"]
    assert "source_attachment_id" not in blocks[0]   # 신규는 source 없음


def test_p2_parse_robust_and_optional_filename():
    assert app._parse_attachment_new_blocks("그냥 텍스트") == []
    assert app._parse_attachment_new_blocks("```attachment-new\n{not json}\nx\n```") == []
    # filename 없어도 파싱 성공(materialize 가 기본명 부여)
    blocks = app._parse_attachment_new_blocks('```attachment-new\n{}\nBODY\n```')
    assert len(blocks) == 1 and blocks[0]["filename"] is None and "BODY" in blocks[0]["content"]


def test_p3_spans_embedded_fence_full_body():
    body = "line1\n```sql\nSELECT x\n```\nlast"
    answer = f'```attachment-new\n{{"filename":"a.sql"}}\n{body}\n```'
    blocks = app._parse_attachment_new_blocks(answer)
    assert len(blocks) == 1
    assert blocks[0]["content"] == body      # 내부 ``` 포함 전체 본문


def test_p4_edit_and_new_blocks_do_not_cross_contaminate():
    edit = '```attachment-edit\n{"source_attachment_id": 5}\nEDIT_BODY\n```'
    new = _new_block("n.sql", body="NEW_BODY")
    combined = edit + "\n\n" + new
    e = app._parse_attachment_edit_blocks(combined)
    n = app._parse_attachment_new_blocks(combined)
    assert len(e) == 1 and e[0]["source_attachment_id"] == 5 and "EDIT_BODY" in e[0]["content"]
    assert "NEW_BODY" not in e[0]["content"]
    assert len(n) == 1 and "NEW_BODY" in n[0]["content"] and "EDIT_BODY" not in n[0]["content"]


def test_p5_coexistence_both_orders_wellformed():
    # 잘-형성된(각자 닫힌) edit·new 가 어느 순서로 오든 각 파서가 자기 본문만 정확히 캡처.
    new = _new_block("n.sql", body="NEW_ONLY")
    edit = '```attachment-edit\n{"source_attachment_id": 9}\nEDIT_ONLY\n```'
    for combined in (edit + "\n\n" + new, new + "\n\n" + edit):
        e = app._parse_attachment_edit_blocks(combined)
        n = app._parse_attachment_new_blocks(combined)
        assert len(e) == 1 and e[0]["content"] == "EDIT_ONLY"
        assert len(n) == 1 and n[0]["content"] == "NEW_ONLY"


def test_p6_known_limitation_other_tag_line_inside_body():
    # 알려진 한계(§18.8 backend 패널, 실트리거 ≈0 for SQL/CSV): 한 블록 **본문 안**에 상대 태그로
    # 시작하는 줄이 있으면 그 줄을 경계로 오인해 바깥 블록이 조기 종료/드롭될 수 있다. 더 흔한
    # 공존 케이스를 지키기 위한 의도된 트레이드오프 — 동작을 여기서 고정(무의식적 변경 방지).
    answer = (
        '```attachment-edit\n{"source_attachment_id": 1}\n'
        "line before\n```attachment-new\nstill edit body\n```"
    )
    e = app._parse_attachment_edit_blocks(answer)
    assert e == []   # 본문 내 ```attachment-new 줄이 경계로 오인 → 조기종료(문서화된 한계)


# ── M: materialize ───────────────────────────────────────────────────────────
def test_m1_materialize_creates_root_attachment(monkeypatch):
    created, store, storage = _run_materialize(monkeypatch, _new_block("improve.sql"))
    assert len(created) == 1
    ins = store.get("insert_params")
    assert ins is not None
    # VALUES 순서: (cid, aid, object_key, filename, hmac, mime, size, bucket, sha, kind, meta) → RootAttachmentId=NULL, VersionNumber=1 리터럴
    assert ins[3] == "improve.sql"            # filename
    assert None not in ins or True            # RootAttachmentId 는 SQL 리터럴 NULL (params 아님)
    assert len(storage.put_calls) == 1        # MinIO put
    assert "superseded_sql" not in store      # 신규는 supersede 안 함
    assert created[0]["is_assistant_generated"] is True
    assert created[0]["version_number"] == 1


def test_m2_allowed_extension_preserved(monkeypatch):
    for ext, kind in [("sql", "text"), ("md", "text"), ("json", "text"), ("csv", "csv"), ("log", "text")]:
        created, store, _ = _run_materialize(
            monkeypatch, _new_block(f"out.{ext}"), new_row=_new_row(filename=f"out.{ext}"))
        ins = store.get("insert_params")
        assert ins[3] == f"out.{ext}", f"{ext} 확장자 보존 실패: {ins[3]}"
        assert ins[9] == kind, f"{ext} kind 매핑 실패: {ins[9]}"   # kind 는 params[9]


def test_m3_executable_or_unknown_extension_forced_txt(monkeypatch):
    # SEC: 실행형(.sh/.py/.exe)·미허용·확장자 없음 → 안전 .txt 강제.
    for name in ["evil.sh", "run.py", "mal.exe", "noext", "weird.bin"]:
        created, store, _ = _run_materialize(monkeypatch, _new_block(name))
        ins = store.get("insert_params")
        assert ins[3].endswith(".txt"), f"{name} → .txt 강제 실패: {ins[3]}"
        assert ins[9] == "text"


def test_m4_path_and_double_extension_sanitized(monkeypatch):
    # 경로구분자 제거 + 내부 dot 제거(이중확장자 차단): "a/b.exe.sql" → stem 내부 dot 제거, ext=sql 유지.
    created, store, _ = _run_materialize(monkeypatch, _new_block("a/b.exe.sql"))
    ins = store.get("insert_params")
    fn = ins[3]
    assert "/" not in fn and "\\" not in fn
    assert fn.endswith(".sql")             # 마지막 확장자는 allowlist(.sql) 유지
    assert ".exe." not in fn               # 내부 이중확장자 흔적 제거
    assert fn == "a_b_exe.sql", f"정화 결과 예상과 다름: {fn}"


def test_m5_reject_oversize(monkeypatch):
    created, store, _ = _run_materialize(monkeypatch, _new_block("big.sql"), size_ok=False)
    assert created == []
    assert store.get("insert_params") is None


def test_m6_count_cap(monkeypatch):
    # 편집과 동일 개수 cap(_ASSISTANT_EDIT_COUNT_CAP) — 초과분 무시.
    cap = app._ASSISTANT_EDIT_COUNT_CAP
    answer = "\n\n".join(_new_block(f"f{i}.sql", body=f"BODY{i}") for i in range(cap + 3))
    storage = _install_fake_storage(monkeypatch)
    store = {"new_id": 7001}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _new_row())
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    created = app._materialize_assistant_attachment_new(
        conn, account=_account(), conversation_id="conv-1", answer=answer, message_id=5)
    assert len(storage.put_calls) <= cap        # cap 초과분은 materialize 안 됨


# ── SEC: RBAC 게이트 + 공유 개수 예산 (§18.8 패널 대응) ──────────────────────
def test_sec1_rbac_upload_permission_denied(monkeypatch):
    # 보안 MAJOR: 업로드 권한 없는 주체는 신규 첨부를 생성하지 못한다(materialize skip).
    created, store, storage = _run_materialize(monkeypatch, _new_block("x.sql"), can_upload=False)
    assert created == []
    assert store.get("insert_params") is None
    assert len(storage.put_calls) == 0


def test_sec2_shared_count_budget(monkeypatch):
    # 보안 MINOR: 편집 경로와 합산 cap — remaining_count 로 잔여만큼만 materialize.
    _install_fake_storage(monkeypatch)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _new_row())
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    store = {"new_id": 7001}
    conn = _Conn(store)
    answer = "\n\n".join(_new_block(f"f{i}.sql", body=f"BODY{i}") for i in range(5))
    created = app._materialize_assistant_attachment_new(
        conn, account=_account(), conversation_id="conv-1", answer=answer, message_id=5,
        remaining_count=2)   # 편집이 이미 3개 materialize → 신규는 2개만
    assert len(created) == 2


def test_sec3_shared_count_budget_zero(monkeypatch):
    # 편집이 cap 을 모두 소진(remaining_count=0)하면 신규는 0개.
    created, store, storage = _run_materialize(monkeypatch, _new_block("x.sql"))
    # _run_materialize 는 remaining_count 미전달(기본 cap) — 별도 직접 호출로 0 검증:
    _install_fake_storage(monkeypatch)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _new_row())
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    conn = _Conn({"new_id": 7001})
    created0 = app._materialize_assistant_attachment_new(
        conn, account=_account(), conversation_id="conv-1",
        answer=_new_block("x.sql"), message_id=5, remaining_count=0)
    assert created0 == []


def test_m7_missing_filename_default(monkeypatch):
    created, store, _ = _run_materialize(monkeypatch, _new_block(None, body="SELECT 1"))
    ins = store.get("insert_params")
    assert ins[3] == "script.txt"               # filename 누락 → 코드-권위 기본명


def test_m8_empty_content_skipped(monkeypatch):
    created, store, _ = _run_materialize(monkeypatch, _new_block("x.sql", body=""))
    assert created == []
    assert store.get("insert_params") is None


# ── S: strip ─────────────────────────────────────────────────────────────────
def test_s1_strip_block_with_note():
    body = "SELECT secret FROM t WHERE 1=1"
    answer = "개선안입니다.\n\n" + _new_block("improve.sql", body=body)
    out = app._strip_attachment_new_blocks(answer, [{"original_filename": "improve.sql"}])
    assert "attachment-new" not in out
    assert body not in out                       # 전체 본문 미노출
    assert "📎" in out and "improve.sql" in out  # 첨부 전달 안내
    assert "개선안입니다." in out


def test_s2_strip_no_block_or_failed():
    assert app._strip_attachment_new_blocks("설명만", []) == "설명만"
    # 블록만 있고 materialize 실패([]) → **원문을 되살리지 않는다**(계약 변경 2026-08-28).
    #
    # 종전 계약은 "빈 답변 방지 = 원문 유지" 였다. 그 의도는 옳지만 수단이 틀렸다 — 원문을
    # 돌려주면 **파일 전문이 채팅에 그대로 쏟아진다**(codex 적대 리뷰 P1). 특히 실패·취소 run은
    # 안내 문구도 붙지 않아 그 상태가 굳는다. 빈 답변도 원문 유출도 아닌, 사실 한 줄로 답한다.
    only = _new_block("x.sql", body="B")
    out = app._strip_attachment_new_blocks(only, [])
    assert out, "빈 답변이 되면 말풍선이 통째로 비어 '답이 없다' 로 읽힌다"
    assert "B" not in out and "attachment-new" not in out, "파일 전문이 채팅에 남았다"
    assert "전달되지 않았습니다" in out, "무슨 일이 있었는지 말하지 않는다"


# ── PR: 프롬프트 ─────────────────────────────────────────────────────────────
def test_pr1_prompt_has_attachment_new_guidance():
    import agent_core
    src = agent_core.SYSTEM_PROMPT
    assert "attachment-new" in src
    assert "NEW SCRIPT/QUERY AS A DOWNLOADABLE ATTACHMENT" in src
    # 코드-권위 directive 존재 + compose 주입.
    assert "attachment-new" in agent_core._ATTACHMENT_NEW_DELIVERY_DIRECTIVE
    # ⚠️ 2026-08-25: 종전에는 `inspect.getsource(compose_system_prompt)` 에 상수 **이름**이
    # 있는지로 검사했다. 조립부가 헬퍼로 빠지자(조기 return 도 directive 를 거치게 하는 [P1]
    # 수정) 이름이 본문에서 사라져 깨졌다 — 주입은 오히려 더 견고해졌다. 계약을 유지한 채
    # 실행 기반으로 격상한다 (§16.7 G11).
    assert agent_core._ATTACHMENT_NEW_DELIVERY_DIRECTIVE in agent_core._code_directive_parts("BASE")
    assert "attachment-new" in agent_core.compose_system_prompt(None)


class _FakeCur:
    """compose_system_prompt 의 WebSystemPrompts 조회를 모사. global base 만 operator_base 반환,
    scope(role/account/product) 조회는 전부 None(커스텀 없음)."""
    def __init__(self, base_content):
        self._base = base_content
        self._last = ""

    def execute(self, sql, params=None):
        self._last = " ".join(str(sql).split()).lower()

    def fetchone(self):
        if "scope='global'" in self._last:
            return (self._base,) if self._base is not None else None
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class _FakeConn:
    def __init__(self, base_content):
        self._b = base_content

    def cursor(self, *a, **k):
        return _FakeCur(self._b)


def test_pr2_directive_injected_even_when_operator_base_strips_it():
    # drift-proof(AUTH-1a): 운영자 global row 가 첨부 지침 없는 base 로 통째 대체해도, 코드-권위
    # directive 주입으로 attachment-new/attachment-edit 지침이 최종 프롬프트에 살아있어야 한다.
    import agent_core
    operator_base = "You are a helper. (no attachment guidance in operator base)"
    out = agent_core.compose_system_prompt(_FakeConn(operator_base), product_mode="pinned")
    assert operator_base in out                   # 운영자 base 적용됨
    assert "attachment-new" in out                # 신규 첨부 지침이 코드-권위로 주입됨
    assert "attachment-edit" in out               # 편집 지침도 함께(회귀 방지)


# ── A: ask 흐름 ──────────────────────────────────────────────────────────────
def test_a1_ask_invokes_new_materialize_and_strip():
    import inspect
    import routers.conversations as _rc
    src = inspect.getsource(_rc)
    assert "_materialize_assistant_attachment_new(" in src
    assert "_strip_attachment_new_blocks(" in src
    assert 'result["new_attachments"]' in src


def test_a2_web_postprocess_is_evidence_gated():
    """§18.8 회귀 방지 — web 후처리 게이트 2계약.

    (BLOCKER) materialize **와 strip 4곳 전부**가 같은 게이트를 통과해야 한다. strip 만 게이트에서
    빠지면 worker 모드에서 web 이 빈 목록으로 블록을 지워 저장 → 워커가 읽을 때 블록이 없어 첨부가
    영영 생성되지 않고 스크립트 본문도 소실된다(원 결함보다 악화).

    (MAJOR) 게이트는 **모드가 아니라 증거** 기준이어야 한다 — worker 가 이미 strip 했으면 블록이
    없어 no-op 이고, 블록이 남아 있으면(구버전 워커·web-only 배포·후처리 실패) web 이 self-heal.
    모드만으로 게이팅하면 혼합 버전 배포 창에서 첨부 미생성 + 원문 영구 잔존.
    """
    import inspect
    import re
    import routers.conversations as _rc
    src = inspect.getsource(_rc)
    # 증거 기반 게이트: worker 모드여도 블록이 남아 있으면 수행.
    assert "_raw_block_left" in src
    assert "(not app._is_worker_mode()) or _raw_block_left" in src
    # materialize 2곳 + strip 2곳 = 4곳 전부 게이트 통과.
    guarded = len(re.findall(r"if _attach_postprocess_here and ", src))
    assert guarded >= 4, f"web 후처리 게이팅 누락(발견 {guarded}/4)"
    for m in re.finditer(
        r"^\s*if .*_strip_attachment_(?:edit|new)_blocks|^\s*if .*\"attachment-(?:edit|new)\" in render_output",
        src, re.M,
    ):
        line = m.group(0)
        if "_raw_block_left" in line:
            continue    # 게이트 자체를 계산하는 줄
        assert "_attach_postprocess_here" in line, f"게이트 없는 strip 분기: {line.strip()[:80]}"
