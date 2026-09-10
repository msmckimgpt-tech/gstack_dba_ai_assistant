"""REQ-20260908-attach-folder-tree — 폴더 첨부의 서버 측 계약(경로 저장·체인 스코프·API 노출).

사용자 요청(2026-09-08): 폴더를 통째로 첨부할 수 있게 하고, 디렉토리 트리를 보존하며,
assistant 도 그 구조를 인지하게 한다.

본 파일이 고정하는 것(web 쪽):
  U1  업로드가 `relative_path` 폼 필드를 받아 **정규화한 값**을 INSERT 한다.
  U2  위험한 경로(traversal·절대경로)는 정규화로 무해해진 뒤 저장된다 — 원문이 그대로 들어가지 않는다.
  C1  버전 체인 스코프가 경로를 포함한다 — 다른 폴더의 동명 파일이 서로를 supersede 하지 않는다.
  C2  경로 없는 첨부끼리는 종전대로 파일명으로 체인을 잇는다(회귀 방지).
  C3  경로 있는 행과 없는 행이 섞이지 않는다(폴더 안 a.txt ≠ 따로 올린 a.txt).
  S1  API 직렬화가 `relative_path` 를 싣는다(없으면 None).
  M1  PG dual-write 미러의 컬럼 계약 3면(SELECT·UPSERT·params)이 경로를 포함한다.
"""
from __future__ import annotations

import pathlib
import sys

from routers import _conv_store

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.attachment_path import normalize_relative_path  # noqa: E402


# ── C1~C3: 버전 체인 스코프 ────────────────────────────────────────────────────
class _ChainCursor:
    """`_find_latest_same_name_attachment` 가 실제로 보낸 SQL·params 를 포획한다."""

    def __init__(self, sink, row):
        self._sink = sink
        self._row = row

    def execute(self, sql, params=None):
        self._sink["sql"] = sql
        self._sink["params"] = params

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _ChainConn:
    def __init__(self, sink, row=None):
        self._sink = sink
        self._row = row

    def cursor(self, *a, **k):
        return _ChainCursor(self._sink, self._row)


def test_c1_chain_scope_uses_path_when_present():
    sink: dict = {}
    _conv_store._find_latest_same_name_attachment(
        _ChainConn(sink), "conv-x", 10, "config.json", relative_path="p/src/config.json")
    # 경로로 매칭해야 한다 — 파일명으로 매칭하면 `p/test/config.json` 이 같은 체인에 들어온다.
    assert "RelativePath = %s" in sink["sql"]
    assert sink["params"] == ("conv-x", 10, "p/src/config.json")


def test_c2_chain_scope_falls_back_to_filename():
    sink: dict = {}
    _conv_store._find_latest_same_name_attachment(
        _ChainConn(sink), "conv-x", 10, "sales.csv")
    assert "OriginalFilename = %s" in sink["sql"]
    assert sink["params"] == ("conv-x", 10, "sales.csv")


def test_c3_pathless_query_excludes_rows_that_have_a_path():
    """폴더 안 `a.txt` 와 따로 올린 `a.txt` 는 다른 파일이다.

    경로 없는 업로드가 경로 있는 행을 체인 head 로 집으면, 폴더 안 파일이 폴더 밖
    재업로드에 의해 supersede 되어 목록에서 사라진다.
    """
    sink: dict = {}
    _conv_store._find_latest_same_name_attachment(_ChainConn(sink), "conv-x", 10, "a.txt")
    assert "RelativePath IS NULL OR RelativePath = ''" in sink["sql"]


# ── S1: API 직렬화 ────────────────────────────────────────────────────────────
def test_s1_serializer_exposes_relative_path():
    row = {
        "Id": 7, "ConversationId": "conv-x", "Kind": "text", "MimeType": "text/plain",
        "OriginalFilename": "helper.py", "RelativePath": "proj/src/helper.py",
        "SizeBytes": 100, "SizeBucket": "small", "Sha256": "d" * 64,
        "UploadStatus": "uploaded", "CreatedAt": None, "DeletePending": 0,
        "DeleteReason": None, "VersionNumber": 1, "RootAttachmentId": None,
        "CreatedByRole": "user", "SupersededAt": None, "MetaJson": None,
    }
    out = _conv_store._serialize_attachment_for_api(row)
    assert out["relative_path"] == "proj/src/helper.py"
    # 파일명은 계속 basename — 경로는 **추가 축**이지 대체가 아니다.
    assert out["original_filename"] == "helper.py"


def test_s1_serializer_none_for_single_file():
    row = {
        "Id": 8, "ConversationId": "conv-x", "Kind": "csv", "MimeType": "text/csv",
        "OriginalFilename": "sales.csv", "RelativePath": None,
        "SizeBytes": 10, "SizeBucket": "small", "Sha256": "e" * 64,
        "UploadStatus": "uploaded", "CreatedAt": None, "DeletePending": 0,
        "DeleteReason": None, "VersionNumber": 1, "RootAttachmentId": None,
        "CreatedByRole": "user", "SupersededAt": None, "MetaJson": None,
    }
    assert _conv_store._serialize_attachment_for_api(row)["relative_path"] is None


# ── U1/U2: 업로드 경로 배선 (소스 계약) ────────────────────────────────────────
def _conversations_src() -> str:
    return (REPO_ROOT / "unit" / "feature-0003-agent-web-ui" / "src"
            / "routers" / "conversations.py").read_text(encoding="utf-8")


def test_u1_upload_accepts_and_normalizes_relative_path():
    src = _conversations_src()
    # 폼 필드 수용 + 정규화 경유 + INSERT 바인딩까지 한 줄기로 이어져야 한다.
    assert "relative_path: str | None = Form(None)" in src
    assert "rel_path = _normalize_relative_path(relative_path, filename)" in src
    assert "object_key, filename, rel_path, filename_hmac" in src


def test_u1_chain_lookup_receives_path():
    src = _conversations_src()
    assert "relative_path=rel_path" in src


def test_u2_raw_client_path_is_never_stored_directly():
    """원문(`relative_path` 인자)이 INSERT 바인딩에 직접 실리면 안 된다 — 정규화가 유일 경로."""
    src = _conversations_src()
    insert_block = src.split("_ATTACH_INSERT_SQL", 1)[1][:2000]
    assert "rel_path" in insert_block
    # 정규화되지 않은 원문 변수명이 바인딩 튜플에 나타나지 않는다.
    assert ", relative_path," not in insert_block


def test_u2_normalizer_defuses_traversal():
    # 정규화 자체의 계약은 shared 테스트가 소유하지만, 업로드가 의존하는 성질을 여기서도 못박는다.
    assert normalize_relative_path("../../etc/passwd", "passwd") == "etc/passwd"
    assert normalize_relative_path("/etc/shadow", "shadow") == "etc/shadow"


# ── M1: PG dual-write 미러 컬럼 계약 ──────────────────────────────────────────
def test_m1_pg_mirror_carries_relative_path_on_all_three_faces():
    """미러의 세 면(MySQL SELECT · PG alias · UPSERT/params)이 함께 움직여야 한다.

    한 면만 빠지면 dual-write 는 조용히 성공하면서 PG 쪽 경로만 NULL 이 된다 —
    read backend 를 PG 로 돌린 순간 폴더 구조가 통째로 사라진다.
    """
    src = (REPO_ROOT / "unit" / "feature-0003-agent-web-ui" / "src"
           / "modules" / "attachment_pg_mirror.py").read_text(encoding="utf-8")
    assert "OriginalFilename, RelativePath" in src          # MySQL SELECT 계약
    assert 'relative_path AS "RelativePath"' in src          # PG → MySQL alias
    assert "original_filename, relative_path, filename_hmac" in src  # UPSERT 컬럼
    assert "%(relative_path)s" in src                        # UPSERT VALUES
    assert "relative_path = EXCLUDED.relative_path" in src   # ON CONFLICT
    assert '"relative_path": (str(row["RelativePath"])' in src  # params 매핑


# ── §18.8 backend 라운드 적발분 회귀 고정 ─────────────────────────────────────
# 리뷰가 **뮤테이션 생존**으로 입증한 구간들이다 — 구현에서 해당 줄을 지워도 스위트가
# 통과했다. 각 테스트는 그 줄이 사라지면 죽도록 겨냥한다(§16.7 G10).

def _pg_mirror_src() -> str:
    return (REPO_ROOT / "unit" / "feature-0003-agent-web-ui" / "src"
            / "modules" / "attachment_pg_mirror.py").read_text(encoding="utf-8")


def _backfill_src() -> str:
    return (REPO_ROOT / "unit" / "feature-0002-agent-core" / "src"
            / "scripts" / "attachment_backfill.py").read_text(encoding="utf-8")


def test_p1_backfill_script_is_the_fourth_face_of_the_pg_contract():
    """[P1] 미러 모듈만 고치면 backfill 이 `relative_path` 를 NULL 로 넣는다.

    `ON CONFLICT DO NOTHING` 이라 **재실행으로도 복구되지 않고**, read backend 를 PG 로
    돌리는 순간 cutover 이전 폴더가 통째로 평면 목록이 된다. 초판 테스트는 미러 모듈만
    grep 해서 이 면을 통과시켰다 — 계약을 주장하는 테스트가 계약이 깨진 걸 못 봤다.
    """
    src = _backfill_src()
    assert "OriginalFilename, RelativePath" in src, "MySQL SELECT 계약에 경로 없음"
    assert "original_filename, relative_path" in src, "PG upsert 컬럼에 경로 없음"
    assert "%(relative_path)s" in src, "PG upsert VALUES 에 경로 없음"
    assert '"relative_path": (str(r["RelativePath"])' in src, "params 매핑 없음"
    # 이미 들어온 행의 NULL 경로를 **치유**해야 한다 — DO NOTHING 이면 영구 NULL.
    assert "relative_path = COALESCE(" in src, "재실행이 기존 NULL 경로를 복구하지 못한다"


def test_p1_read_path_has_degrade_fallback_like_its_sibling():
    """[P1] `_load_scoped_attachment_rows` 에 degrade 가 없으면 롤아웃 창에서
    `read_attachment` 가 **모든 파일에 대해** "참조할 수 없다" 를 낸다.

    ask-worker 는 web 부트스트랩을 타지 않는 별 컨테이너라 컬럼 없이 먼저 뜰 수 있다.
    형제 함수(`_build_attachment_context_section`)는 이미 degrade 를 갖고 있다 — 한쪽만
    고치면 "목록에는 있는데 읽으면 없다" 는 모순이 사용자에게 그대로 간다.
    """
    src = (REPO_ROOT / "unit" / "feature-0002-agent-core" / "src"
           / "agent_core.py").read_text(encoding="utf-8")
    head = src.split("def read_attachment_content", 1)[0]
    assert head.count('_run(_base + ", RelativePath")') >= 1, "read 경로에 2-shot degrade 없음"
    assert "_run(_base)" in head, "폴백 재조회가 없다"


def test_p2_assistant_edit_and_fork_inherit_path():
    """[P2] 승계 두 줄은 뮤테이션 생존 구간이었다 — 지우면 편집본·fork 사본이 폴더 밖으로
    튀어나오는데 어떤 테스트도 죽지 않았다."""
    src = (REPO_ROOT / "unit" / "feature-0003-agent-web-ui" / "src"
           / "routers" / "_conv_store.py").read_text(encoding="utf-8")
    # assistant 편집본: 원본 행(src)의 경로를 INSERT 바인딩에 싣는다.
    assert '(str(src.get("RelativePath")) if src.get("RelativePath") else None)' in src
    # fork 복사: 원본 행(att)의 경로를 싣는다.
    assert '(str(att.get("RelativePath")) if att.get("RelativePath") else None)' in src
    # 두 INSERT 문 모두 컬럼 목록에 경로가 있어야 바인딩이 자리를 찾는다.
    assert src.count("ObjectKey, OriginalFilename, RelativePath,") >= 2


def test_p2_lineage_heads_scope_by_path_not_basename():
    """[P2] `/versions` 의 `lineages[]` 가 파일명으로 스코프되면, 서로 다른 폴더의 동명
    파일이 「한 파일의 경쟁 계보」로 뜬다 — 전부 `created_by_role='user'` 라 화면에 구분
    수단이 없다(폴더 이전에는 불가능했던 상태)."""
    src = (REPO_ROOT / "unit" / "feature-0003-agent-web-ui" / "src"
           / "routers" / "_conv_store.py").read_text(encoding="utf-8")
    fn = src.split("def _load_filename_lineage_heads", 1)[1].split("\ndef ", 1)[0]
    assert 'relative_path: str | None = None' in fn, "경로 인자가 없다"
    assert '_match_sql = "RelativePath = %s"' in fn, "경로 스코프 분기가 없다"
    assert "OriginalFilename, RelativePath, CreatedAt" in fn, "SELECT 에 경로가 없다"


def test_p2_bulk_download_preserves_folders():
    """[P2] 평면 ZIP 은 `src/config.json`·`test/config.json` 을 `config.json`·`config_412.json`
    으로 내보내 왕복이 닫히지 않는다. 디렉토리 부분도 zip-slip 방어를 거쳐야 한다."""
    src = (REPO_ROOT / "unit" / "feature-0003-agent-web-ui" / "src"
           / "routers" / "conversations.py").read_text(encoding="utf-8")
    fn = src.split("def _zip_entry_name", 1)[1].split("\ndef ", 1)[0]
    assert '_rel = str(row.get("RelativePath")' in fn, "ZIP 엔트리명이 경로를 안 본다"
    assert 'name = "/".join(_dir_segs) + "/" + name' in fn, "디렉토리를 엔트리명에 안 붙인다"
    assert '_seg in (".", "..")' in fn, "디렉토리 부분의 zip-slip 방어가 없다"
    # SELECT 가 컬럼을 안 가져오면 위 전부가 무의미하다.
    assert "ObjectKey, OriginalFilename, RelativePath, SizeBytes" in src


def test_p2_count_cap_counts_live_heads_only():
    """[P2] superseded 구버전까지 세면 「폴더를 고쳐 다시 올린다」는 표준 흐름이 스스로
    쿼터를 소진하고, 사용자 화면에 없는 행이 원인이라 안내가 무의미해진다."""
    src = (REPO_ROOT / "unit" / "feature-0003-agent-web-ui" / "src"
           / "routers" / "_conv_store.py").read_text(encoding="utf-8")
    fn = src.split("def _check_attachment_size_caps", 1)[1].split("\ndef ", 1)[0]
    assert "SUM(CASE WHEN SupersededAt IS NULL THEN 1 ELSE 0 END)" in fn
    assert "_attachment_count_cap()" in fn


def test_p2_frontend_treats_server_path_as_authoritative_at_all_merge_sites():
    """[P2] 서버의 **의도적 거절**(null)과 «필드 부재»를 `||` 로 뭉개면, 서버가 버린 폴더를
    화면만 계속 보여 주다가 새로고침 순간 항목이 사라진 것처럼 보인다. 세 병합 지점 모두."""
    js = (REPO_ROOT / "unit" / "feature-0003-agent-web-ui" / "src" / "static"
          / "app" / "composer.js").read_text(encoding="utf-8")
    assert "function _mergeServerRelativePath(" in js
    # 정의부(`function _mergeServerRelativePath(resp, clientValue)`)를 빼고 **호출**만 센다.
    calls = js.count("_mergeServerRelativePath(resp,") - js.count("function _mergeServerRelativePath(resp,")
    assert calls == 3, f"병합 지점 3곳 전부가 아니다 (호출 {calls}곳)"
    # 옛 `||` 폴백이 남아 있으면 그 지점만 조용히 마스킹한다.
    assert "resp.relative_path || _relPath" not in js
    assert "resp.relative_path || staged.relative_path" not in js
