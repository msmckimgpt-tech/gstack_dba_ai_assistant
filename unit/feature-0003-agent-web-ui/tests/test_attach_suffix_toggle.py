"""REQ-20260806-attach-suffix-toggle: 다운로드 파일명의 버전 접미사(`_v2`) 토글 회귀 테스트.

사용자 요청: "첨부를 받을 때 `_v2`·`_v3` 가 붙은 채로 받을지 체크박스로 고르게 해달라 —
단일·전체 다운로드 모두". 접미는 두 곳에서 생겼다 — (a) AI 편집본의 **저장명** 자체
(`_next_version_filename` 이 `report_v2.csv` 로 저장), (b) 전 버전 일괄 다운로드가 ZIP
엔트리명에 덧붙이는 `_v<n>`. 두 출처를 한 규칙 함수로 모으고 그 함수를 세 경로(단일
프록시·ZIP·개별 저장)가 공유한다.

검증(`make test` agent 이미지, DB 없이 fake row + monkeypatch):

  규칙 함수 (`_download_filename_with_version`)
    F1  keep — 저장명 그대로(종전 동작 보존).
    F2  strip — stem 끝 `_v<VersionNumber>` 제거.
    F3  strip 은 **번호가 일치할 때만** — 사용자가 `plan_v2.docx` 로 올린 v1 은 안 건드린다.
    F4  force — 이미 접미가 있으면 재부여(이중접미 `report_v2_v2.csv` 방지).
    F5  force — 접미가 없으면 부여. 확장자 없는 이름도 처리.
    F6  빈 이름/미지 모드는 입력을 그대로 돌려준다(조용한 파괴 금지).

  파라미터 정규화 (`_normalize_version_suffix_mode`)
    N1  keep/strip/force + 대소문자·공백 허용.
    N2  미지의 값은 "" → caller 가 400. 기본값으로 조용히 격하하지 않는다(S2 동형).
    N3  미지정은 caller 가 준 default.

  ZIP 엔트리명 (`_zip_entry_name`)
    Z1  force 는 정확히 한 번만 붙인다(AI 편집본 이중접미 회귀).
    Z2  strip + 전 버전 = 이름 충돌 → id 접미 fallback 이 살아 있다(무음 덮어쓰기 금지).

  엔드포인트 계약
    E1  단일 다운로드 `version_suffix=strip` → Content-Disposition + 전용 헤더 모두 정제된 이름.
    E2  단일 다운로드 기본(미지정) = 저장명 그대로 — 기존 호출자의 결과가 안 바뀐다.
    E3  잘못된 값은 400.
    E4  일괄 다운로드 미지정 기본 = scope 별 종전 동작(all→force, latest→keep).
    E5  파라미터 400 은 **인증 뒤** — 미인증이 401 대신 400 을 받지 않는다(security 패널 P3).
    E6  단일 경로도 ZIP 과 같은 경로 성분 정제를 한다(security 패널 P3 방어심층).

  경로 정합 (구조 가드 §16.7 G10)
    G1  프론트가 접미 규칙을 복제하지 않는다 — 서버가 준 이름을 쓴다.
    G2  ZIP 과 개별 저장이 같은 규칙 함수를 거친다.
    G3  패널·모달 토글이 하나의 상태를 공유한다.
    G4  매니페스트가 ZIP 과 같은 이름 함수(중복 회피 포함)를 쓴다.
    G5  일괄 개별 저장은 매니페스트 이름을 우선한다 — 단건 헤더가 묶음 dedup 을 덮지 않는다.
"""
from __future__ import annotations

import inspect
import pathlib

import pytest
from fastapi.responses import JSONResponse

import app
from routers import attachments as att
from routers import conversations as convs


_STATIC = pathlib.Path(__file__).resolve().parents[1] / "src" / "static"


def _row(**kw):
    base = {
        "Id": 1,
        "ConversationId": "conv-1",
        "AccountId": 7,
        "ObjectKey": "conv-1/u1/f.csv",
        "OriginalFilename": "report.csv",
        "SizeBytes": 10,
        "VersionNumber": 1,
        "RootAttachmentId": None,
        "CreatedByRole": "user",
        "UploadStatus": "uploaded",
        "DeletedAt": None,
        "DeletePending": 0,
    }
    base.update(kw)
    return base


# ── F. 규칙 함수 ───────────────────────────────────────────────────────────
def test_f1_keep_returns_stored_name():
    assert app._download_filename_with_version("report_v2.csv", 2, "keep") == "report_v2.csv"
    assert app._download_filename_with_version("report.csv", 1) == "report.csv"


def test_f2_strip_removes_matching_suffix():
    assert app._download_filename_with_version("report_v2.csv", 2, "strip") == "report.csv"
    assert app._download_filename_with_version("분석_v10.xlsx", 10, "strip") == "분석.xlsx"


def test_f3_strip_only_when_version_matches():
    """사용자가 지은 이름을 왜곡하지 않는다 — `_v\\d+$` 를 무조건 지우면 `plan_v2.docx`
    라는 **원본 이름**(v1)이 `plan.docx` 로 바뀐다."""
    assert app._download_filename_with_version("plan_v2.docx", 1, "strip") == "plan_v2.docx"
    assert app._download_filename_with_version("report_v3.csv", 2, "strip") == "report_v3.csv"


def test_f4_force_is_idempotent():
    """AI 편집본은 저장명이 이미 `report_v2.csv` 다 — 덧붙이면 `report_v2_v2.csv`."""
    assert app._download_filename_with_version("report_v2.csv", 2, "force") == "report_v2.csv"


def test_f5_force_adds_when_absent():
    assert app._download_filename_with_version("report.csv", 3, "force") == "report_v3.csv"
    assert app._download_filename_with_version("README", 2, "force") == "README_v2"


def test_f6_empty_and_unknown_mode_pass_through():
    assert app._download_filename_with_version("", 2, "strip") == ""
    assert app._download_filename_with_version("report_v2.csv", 2, "bogus") == "report_v2.csv"
    # stem 이 접미뿐이면 이름이 통째로 사라진다 — 남긴다.
    assert app._download_filename_with_version("_v2.csv", 2, "strip") == "_v2.csv"


def test_f7_dot_edge_names_survive():
    """`rsplit(".", 1)` 은 선행점 파일의 stem 을 없애고(`.env`→`_v1.env`) 끝점 이름의
    점을 삼킨다(`a.`→`a`) — 접미를 **떼지도 붙이지도 않는 구간까지** 이름을 바꾼다
    (§18.8 backend/qa 패널 P3 2건)."""
    assert app._download_filename_with_version("a.", 2, "strip") == "a."
    assert app._download_filename_with_version("a..", 2, "strip") == "a.."
    assert app._download_filename_with_version(".", 1, "strip") == "."
    # 선행점 파일은 stem 이 통째로 이름 — 확장자로 승격되지 않는다.
    assert app._download_filename_with_version(".env", 1, "force") == ".env_v1"


# ── N. 파라미터 정규화 ─────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("keep", "keep"), ("strip", "strip"), ("force", "force"),
    ("  STRIP ", "strip"), ("Force", "force"),
])
def test_n1_normalizes_known_modes(raw, expected):
    assert app._normalize_version_suffix_mode(raw) == expected


def test_n2_unknown_mode_is_rejected_not_downgraded():
    """오타를 기본값으로 흘리면 사용자가 고른 것과 다른 이름을 받고도 알 수 없다."""
    assert app._normalize_version_suffix_mode("strpi") == ""
    assert app._normalize_version_suffix_mode("1") == ""


def test_n3_blank_uses_caller_default():
    assert app._normalize_version_suffix_mode("") == "keep"
    assert app._normalize_version_suffix_mode(None, default="force") == "force"


# ── Z. ZIP 엔트리명 ────────────────────────────────────────────────────────
def test_z1_zip_force_does_not_double_suffix():
    used: set[str] = set()
    name = convs._zip_entry_name(
        _row(Id=3, OriginalFilename="report_v2.csv", VersionNumber=2), mode="force", used=used)
    assert name == "report_v2.csv", "AI 편집본에 접미가 두 번 붙었다"


def test_z2_zip_strip_keeps_collision_fallback():
    """접미를 떼면 전 버전 모드에서 이름이 겹친다 — 조용히 덮이지 않아야 한다."""
    used: set[str] = set()
    first = convs._zip_entry_name(
        _row(Id=3, OriginalFilename="report.csv", VersionNumber=1), mode="strip", used=used)
    second = convs._zip_entry_name(
        _row(Id=4, OriginalFilename="report_v2.csv", VersionNumber=2), mode="strip", used=used)
    assert first == "report.csv"
    assert first.lower() != second.lower(), f"ZIP 안 이름 중복: {first} / {second}"


# ── E. 엔드포인트 계약 ─────────────────────────────────────────────────────
class _FakeStorage:
    class StorageConfigError(Exception):
        pass

    class StorageOperationError(Exception):
        pass

    @staticmethod
    def get_object_bytes(key):
        return b"payload"


def _install_storage(monkeypatch):
    import sys
    import types
    web_pkg = types.ModuleType("web")
    web_pkg.__path__ = []
    modules_pkg = types.ModuleType("web.modules")
    modules_pkg.__path__ = []
    modules_pkg.storage_minio = _FakeStorage
    web_pkg.modules = modules_pkg
    monkeypatch.setitem(sys.modules, "web", web_pkg)
    monkeypatch.setitem(sys.modules, "web.modules", modules_pkg)
    monkeypatch.setitem(sys.modules, "web.modules.storage_minio", _FakeStorage)


class _Conn:
    def close(self):
        pass


def _prepare_download(monkeypatch, row):
    _install_storage(monkeypatch)
    monkeypatch.setattr(app, "_connect_memory", lambda: _Conn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: ({"id": 7}, None))
    monkeypatch.setattr(app, "_load_attachment_row", lambda conn, aid: row)
    monkeypatch.setattr(app, "_account_can_access_attachment", lambda *a, **k: True)
    monkeypatch.setattr(app, "_account_is_pending", lambda account: False)


def test_e1_single_download_strip_applies_to_both_names(monkeypatch):
    _prepare_download(monkeypatch, _row(Id=5, OriginalFilename="report_v2.csv", VersionNumber=2))
    resp = att.download_attachment(5, object(), version_suffix="strip")
    assert resp.status_code == 200
    assert "report.csv" in resp.headers["Content-Disposition"]
    # blob 저장 경로가 쓰는 전용 헤더도 같은 이름이어야 한다(두 이름이 갈리면 어느 쪽이
    # 저장될지 호출부마다 달라진다).
    assert resp.headers["X-Attachment-Download-Name"] == "report.csv"


def test_e2_single_download_default_keeps_stored_name(monkeypatch):
    _prepare_download(monkeypatch, _row(Id=5, OriginalFilename="report_v2.csv", VersionNumber=2))
    resp = att.download_attachment(5, object())
    assert resp.headers["X-Attachment-Download-Name"] == "report_v2.csv"


def test_e3_single_download_rejects_unknown_mode(monkeypatch):
    _prepare_download(monkeypatch, _row(Id=5))
    resp = att.download_attachment(5, object(), version_suffix="nope")
    assert resp.status_code == 400


def test_e5_param_error_comes_after_auth(monkeypatch):
    """미인증 요청이 401 대신 400 을 받으면 입력 검증이 인증 경계보다 먼저 말한다
    (§18.8 security 패널 P3)."""
    _prepare_download(monkeypatch, _row(Id=5))
    sentinel = JSONResponse({"error": "unauthorized"}, status_code=401)
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (None, sentinel))
    resp = att.download_attachment(5, object(), version_suffix="nope")
    assert resp.status_code == 401, "파라미터 400 이 인증보다 앞선다"


def test_e7_single_and_zip_agree_on_dot_names(monkeypatch):
    """두 서버 경로가 같은 첨부에 다른 이름을 주면 어느 버튼을 눌렀는지가 결과를 바꾼다."""
    row = _row(Id=9, OriginalFilename=".env", VersionNumber=1)
    _prepare_download(monkeypatch, row)
    single = att.download_attachment(9, object(), version_suffix="force")
    zip_name = convs._zip_entry_name(row, mode="force", used=set())
    assert single.headers["X-Attachment-Download-Name"] == zip_name == "env_v1"


def test_e6_single_download_strips_path_components(monkeypatch):
    """헤더 소비자가 브라우저가 아니면 UA 의 `download` 정규화 보호가 없다 — ZIP 과 같은
    정제를 단일 경로에서도 한다(§18.8 security 패널 P3)."""
    _prepare_download(monkeypatch, _row(Id=5, OriginalFilename="../../etc/passwd", VersionNumber=1))
    resp = att.download_attachment(5, object())
    name = resp.headers["X-Attachment-Download-Name"]
    assert "%2F" not in name and ".." not in name, name
    assert name == "passwd"


# ── B. 일괄 다운로드 **배선** (엔드포인트를 실제로 통과시킨다) ─────────────
#
# 규칙 함수를 리터럴 mode 로 직접 호출하는 단위 테스트만으로는 "엔드포인트가 그 값을
# 규칙 함수까지 실어 나르는가" 를 전혀 보지 못한다 — `_zip_entry_name(..., mode="keep")`
# 으로 하드코딩해 **ZIP 이 토글을 완전히 무시하게** 만들어도 전건 통과했다(§18.8
# backend/qa 패널 P2 뮤테이션 실증). 아래는 라우트 함수를 그대로 호출해 산출물을 본다.
class _BulkCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        return None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        return None


class _BulkConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, dictionary=False):
        return _BulkCursor(self._rows)


def _prepare_bulk(monkeypatch, rows):
    _install_storage(monkeypatch)
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(app, "_account_is_pending", lambda account: False)
    monkeypatch.setattr(app, "_resolve_copy_window", lambda conn, cid, aid: ("ok", None, None))
    monkeypatch.setattr(convs, "_audit_bulk_download", lambda *a, **k: None)
    return _BulkConn(rows)


def _zip_names(resp):
    import asyncio
    import io
    import zipfile

    async def _collect():
        chunks = []
        async for c in resp.body_iterator:
            chunks.append(c)
        return b"".join(chunks)

    return zipfile.ZipFile(io.BytesIO(asyncio.run(_collect()))).namelist()


_CHAIN = [
    _row(Id=1, OriginalFilename="report.csv", VersionNumber=1, ObjectKey="k1"),
    _row(Id=2, OriginalFilename="report_v2.csv", VersionNumber=2, ObjectKey="k2"),
]


def test_b1_zip_honors_strip(monkeypatch):
    conn = _prepare_bulk(monkeypatch, _CHAIN)
    resp = convs.bulk_download_conversation_attachments(
        "conv-1", object(), format="zip", scope="all", version_suffix="strip",
        account={"id": 7}, conn=conn)
    names = _zip_names(resp)
    assert all("_v" not in n for n in names), f"strip 인데 버전 접미가 남았다: {names}"
    assert len(set(names)) == len(names), f"이름 충돌이 조용히 덮였다: {names}"


def test_b2_zip_default_keeps_previous_naming(monkeypatch):
    """`version_suffix` 를 모르는 기존 호출자가 다른 이름을 받으면 안 된다."""
    conn = _prepare_bulk(monkeypatch, _CHAIN)
    resp = convs.bulk_download_conversation_attachments(
        "conv-1", object(), format="zip", scope="all", account={"id": 7}, conn=conn)
    assert _zip_names(resp) == ["report_v1.csv", "report_v2.csv"]


def test_b3_zip_force_does_not_double_suffix_end_to_end(monkeypatch):
    conn = _prepare_bulk(monkeypatch, _CHAIN)
    resp = convs.bulk_download_conversation_attachments(
        "conv-1", object(), format="zip", scope="all", version_suffix="force",
        account={"id": 7}, conn=conn)
    assert "report_v2_v2.csv" not in _zip_names(resp)


def test_b4_manifest_carries_mode_into_names_and_urls(monkeypatch):
    conn = _prepare_bulk(monkeypatch, _CHAIN)
    resp = convs.bulk_download_conversation_attachments(
        "conv-1", object(), format="manifest", scope="all", version_suffix="strip",
        account={"id": 7}, conn=conn)
    import json
    files = json.loads(bytes(resp.body).decode("utf-8"))["files"]
    names = [f["download_filename"] for f in files]
    assert all("_v" not in n for n in names), names
    assert len(set(names)) == len(names), f"개별 저장에서 이름이 겹친다: {names}"
    # 개별 URL 도 같은 mode 를 실어야 한다 — 아니면 링크로 받을 때만 이름이 달라진다.
    assert all("version_suffix=strip" in f["url"] for f in files), files


def test_b5_manifest_and_zip_agree_when_a_row_fails(monkeypatch):
    """객체를 못 가져온 행을 ZIP 이 `used` 에서 빼면 뒤 행의 충돌 재배정이 밀려 같은
    첨부가 두 형식에서 다른 이름이 된다(§18.8 backend/qa 패널 P3)."""
    rows = [
        _row(Id=1, OriginalFilename="report.csv", VersionNumber=1, ObjectKey=""),
        _row(Id=2, OriginalFilename="report_v2.csv", VersionNumber=2, ObjectKey="k2"),
        _row(Id=3, OriginalFilename="report_v3.csv", VersionNumber=3, ObjectKey="k3"),
    ]
    conn = _prepare_bulk(monkeypatch, rows)
    zresp = convs.bulk_download_conversation_attachments(
        "conv-1", object(), format="zip", scope="all", version_suffix="strip",
        account={"id": 7}, conn=conn)
    zip_names = _zip_names(zresp)
    conn2 = _prepare_bulk(monkeypatch, rows)
    mresp = convs.bulk_download_conversation_attachments(
        "conv-1", object(), format="manifest", scope="all", version_suffix="strip",
        account={"id": 7}, conn=conn2)
    import json
    manifest = {f["id"]: f["download_filename"]
                for f in json.loads(bytes(mresp.body).decode("utf-8"))["files"]}
    for name in zip_names:
        assert name in manifest.values(), (
            f"ZIP 이름 {name!r} 이 매니페스트에 없다 — 두 형식이 다른 이름을 준다: "
            f"{zip_names} vs {sorted(manifest.values())}")


def test_b6_bulk_rejects_unknown_mode(monkeypatch):
    conn = _prepare_bulk(monkeypatch, _CHAIN)
    resp = convs.bulk_download_conversation_attachments(
        "conv-1", object(), format="zip", scope="all", version_suffix="nope",
        account={"id": 7}, conn=conn)
    assert resp.status_code == 400


# ── G. 경로 정합 구조 가드 ─────────────────────────────────────────────────
def test_g1_frontend_does_not_reimplement_suffix_rule():
    """프론트가 자체로 `_v<n>` 을 만들면 서버 규칙과 두 벌이 되어, 토글을 껐는데 한
    경로에만 접미가 남는다(선행 `_versionedFilename` 이 그 형태였다)."""
    js = (_STATIC / "app" / "composer.js").read_text(encoding="utf-8")
    assert "function _versionedFilename" not in js, "프론트에 접미 생성 규칙이 되살아났다"
    assert "download_filename" in js, "manifest 가 준 서버 결정 이름을 쓰지 않는다"
    assert "X-Attachment-Download-Name" in js, "개별 다운로드가 서버 결정 이름을 쓰지 않는다"


def test_g5_bulk_individual_save_keeps_manifest_names():
    """단건 응답 헤더는 묶음을 모른다 — 개별 저장이 헤더를 우선하면 매니페스트가 푼
    중복이 되살아난다(같은 이름 3개)."""
    js = (_STATIC / "app" / "composer.js").read_text(encoding="utf-8")
    assert "preferGivenName: true" in js, "일괄 개별 저장이 매니페스트 이름을 우선하지 않는다"
    assert "opts.preferGivenName" in js, "우선순위 분기가 사라졌다"


def test_g4_manifest_uses_same_name_function_as_zip():
    """개별 저장(manifest)과 ZIP 이 다른 이름 함수를 쓰면, 접미를 뗀 뒤 개별 저장에서만
    같은 이름이 여럿 나온다 — 모달이 약속한 '구분 번호가 붙습니다' 가 한쪽에서 거짓이 된다."""
    src = " ".join(inspect.getsource(convs.bulk_download_conversation_attachments).split())
    # 표현식을 문자 그대로 요구하면 공백 한 칸·포매터에 red 가 된다 — 배선 사실만 본다.
    # (실제 이름 일치는 B4·B5 가 엔드포인트를 통과시켜 검증한다.)
    assert "_zip_entry_name" in src, "manifest 가 ZIP 과 다른 이름 경로를 쓴다"
    assert "manifest_names" in src, "manifest 에 중복 회피 집합이 없다"


def test_g2_zip_and_single_share_one_rule():
    zip_src = inspect.getsource(convs._zip_entry_name)
    single_src = inspect.getsource(att.download_attachment)
    for name, src in (("_zip_entry_name", zip_src), ("download_attachment", single_src)):
        assert "_download_filename_with_version" in src, f"{name} 이 공용 규칙을 쓰지 않는다"


def test_g3_panel_and_modal_toggles_share_one_state():
    """패널·모달 체크박스가 각자 상태를 들면 한쪽에서 끈 옵션이 다른 쪽에 켜져 보인다."""
    js = (_STATIC / "app" / "composer.js").read_text(encoding="utf-8")
    html = (_STATIC / "index.html").read_text(encoding="utf-8")
    assert "attachSidePanelSuffixToggle" in html, "패널에 토글이 없다(단일 다운로드 대응 누락)"
    assert js.count("js-attach-suffix-toggle") >= 2, "두 표면이 같은 클래스로 동기화되지 않는다"
    assert "_attachVersionSuffixIncluded" in js
