"""REQ-20260806-attach-version-diff: 첨부 버전 **임의 쌍** 비교(diff 화면) 회귀 테스트.

사용자 요청: "첨부파일이 여러 버전이 있을 때 각 파일들 간의 diff 를 비교할 수 있는 화면 —
직전/직후뿐 아니라 여러 단계 차이가 나는 버전 간 비교도" (2026-08-06).

기존 자산과의 경계:
  - `MetaJson.version_diff`(TASK-0274/REQ-20260713)는 업로드 시점 **직전↔신규 1쌍**만 담는다
    (LLM 컨텍스트 주입용). 다단계 비교(v1↔v3)에는 답이 없으므로 신규 엔드포인트가 두 원본을
    그때그때 읽어 대칭적으로 계산한다.
  - 권한은 기준 첨부의 `conversation.attachment.read.{own,any}` 재사용 — 신규 권한 코드 0.

검증(`make test` agent 이미지, DB 없이 monkeypatch):
  V1  체인 로더 — MySQL 폴백 SQL 이 soft-delete 제외 + VersionNumber ASC.
  V2  체인 로더 — PG 미러 활성 시 PG 를 읽고 MySQL cursor 를 건드리지 않는다.
  B1  diff 뷰 — 순수 추가/삭제/교체 opcode 가 좌우 정렬 행으로 펼쳐진다.
  B2  diff 뷰 — replace 의 좌우 줄 수가 다르면 짧은 쪽을 None 으로 패딩(정렬 붕괴 방지).
  B3  diff 뷰 — 기본 맥락(3줄) 밖 equal 런이 gap 행으로 접히고 **생략 줄 수를 표면화**.
  B3b diff 뷰 — gap 에 좌·우 줄번호 범위가 실린다(프론트 국소 전개의 전제, 2026-08-07).
  B3c diff 뷰 — 전체 맥락에서는 gap 자체가 없다.
  B4  diff 뷰 — context_lines=None 이면 동일 줄도 전부 방출(gap 없음).
  B5  diff 뷰 — 행 상한 초과 시 잘리고 truncated.rows=True (무음 절단 금지).
  B6  diff 뷰 — 내용 동일이면 identical=True 이고 축약·행 상한과 무관.
  E1  엔드포인트 — 직전↔최신 정상 비교(comparable/rows/stats/unified_diff).
  E2  엔드포인트 — **다단계**(v1↔v3) 비교가 중간 버전을 건너뛰고 성립.
  E3  엔드포인트 — from==to → 400.
  E4  엔드포인트 — 정수 아님 / 파라미터 누락 → 400.
  E5  엔드포인트 — 체인 밖 버전 번호 → 404 (존재 여부 oracle 차단).
  E6  엔드포인트 — 권한 미보유 → 404.
  E7  엔드포인트 — 바이너리 kind → comparable=false + reason=binary + 해시 동일성.
  E8  엔드포인트 — 원본 cap 초과 시 truncated.from_source/to_source 표면화.
  E9  엔드포인트 — 원본 read 실패 → 503 + reason=source_unavailable.
  E10 엔드포인트 — context=full 이 전체 맥락으로 전달된다.
  E11 회귀 — 목록(`/versions`)과 비교(`/diff`)가 **같은 체인 로더**를 쓴다(체인 집합 비대칭 차단).
  E12 엔드포인트 — **D21** 승인 대기 계정은 403 이고 원본을 한 번도 읽지 않는다
      (diff 가 본문 bytes-deny 의 우회 경로가 되지 않게 — `download_attachment` 와 동형).
  E13 체인 로더 — `scope_row` 를 주면 conversation/account 스코프 밖 행을 제외한다(fail-closed).
  E14 회귀 — **두 엔드포인트 모두** `scope_row` 를 넘긴다(한쪽만 걸면 그쪽만 안전하다).
"""
from __future__ import annotations

import json

import app
from routers import attachments as att_router


# ── fakes ──────────────────────────────────────────────────────────────────
class _Cursor:
    def __init__(self, store, rows):
        self._store = store
        self._rows = rows
        self._out: list = []

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        self._store.setdefault("executed", []).append((s, params))
        self._out = list(self._rows)

    def fetchall(self):
        return list(self._out)

    def fetchone(self):
        return self._out[0] if self._out else None

    def close(self):
        return None


class _Conn:
    def __init__(self, store, rows=()):
        self._store = store
        self._rows = rows
        self.cursor_calls = 0

    def cursor(self, *a, **k):
        self.cursor_calls += 1
        return _Cursor(self._store, self._rows)

    def close(self):
        return None


class _Request:
    """엔드포인트는 request 를 query_params 읽기 + _require_account 전달에만 쓴다."""

    def __init__(self, **params):
        self.query_params = {k: str(v) for k, v in params.items()}


class _Storage:
    StorageConfigError = type("StorageConfigError", (Exception,), {})
    StorageOperationError = type("StorageOperationError", (Exception,), {})

    def __init__(self, objects: dict[str, bytes], fail_keys=()):
        self._objects = objects
        self._fail = set(fail_keys)
        self.reads: list[str] = []

    def get_object_bytes(self, object_key, **_kw):
        self.reads.append(object_key)
        if object_key in self._fail:
            raise self.StorageOperationError("simulated read failure")
        return self._objects[object_key]

    def generate_presigned_get(self, object_key, response_filename=None):
        return f"https://signed/{object_key}"


def _install_storage(monkeypatch, storage):
    """런타임 경로 `from web.modules import storage_minio` 를 sys.modules 주입으로 대체."""
    import sys
    import types

    web_pkg = types.ModuleType("web")
    web_pkg.__path__ = []
    modules_pkg = types.ModuleType("web.modules")
    modules_pkg.__path__ = []
    modules_pkg.storage_minio = storage
    web_pkg.modules = modules_pkg
    monkeypatch.setitem(sys.modules, "web", web_pkg)
    monkeypatch.setitem(sys.modules, "web.modules", modules_pkg)
    monkeypatch.setitem(sys.modules, "web.modules.storage_minio", storage)
    return storage


def _row(*, vid, version, kind="text", key=None, sha=None, superseded=False, role="user"):
    return {
        "Id": vid,
        "ConversationId": "conv-1",
        "AccountId": 1,
        "ObjectKey": key or f"conv-1/u{version}/f.sql",
        "OriginalFilename": "f.sql",
        "MimeType": "text/plain",
        "SizeBytes": 100,
        "Sha256": sha or f"sha{version}",
        "Kind": kind,
        "UploadStatus": "uploaded",
        "CreatedAt": None,
        "DeletedAt": None,
        "DeletePending": 0,
        "MetaJson": None,
        "RootAttachmentId": 10 if version > 1 else None,
        "VersionNumber": version,
        "CreatedByRole": role,
        "SupersededAt": "2026-01-01" if superseded else None,
    }


def _patch_auth(monkeypatch, *, allowed=True, base=None, pending=False):
    monkeypatch.setattr(app, "_require_account", lambda request, conn: ({"id": 1}, None))
    monkeypatch.setattr(app, "_account_is_pending", lambda account: bool(pending))
    monkeypatch.setattr(app, "_load_attachment_row", lambda conn, aid: base or _row(vid=10, version=1))
    monkeypatch.setattr(
        app, "_account_can_access_attachment",
        lambda conn, account, row, own, any_: bool(allowed),
    )


def _body(resp):
    return json.loads(resp.body)


# ── V1/V2: 체인 로더 ────────────────────────────────────────────────────────
def test_v1_chain_loader_mysql_fallback_sql_contract(monkeypatch):
    store: dict = {}
    conn = _Conn(store, rows=[_row(vid=10, version=1), _row(vid=11, version=2)])
    # PG 경로 비활성 — read_pg_enabled 를 False 로 두면 MySQL 폴백.
    import sys
    import types
    apm = types.ModuleType("web.modules.attachment_pg_mirror")
    apm.read_pg_enabled = lambda: False
    web_pkg = types.ModuleType("web")
    web_pkg.__path__ = []
    modules_pkg = types.ModuleType("web.modules")
    modules_pkg.__path__ = []
    modules_pkg.attachment_pg_mirror = apm
    web_pkg.modules = modules_pkg
    monkeypatch.setitem(sys.modules, "web", web_pkg)
    monkeypatch.setitem(sys.modules, "web.modules", modules_pkg)
    monkeypatch.setitem(sys.modules, "web.modules.attachment_pg_mirror", apm)

    rows = app._load_attachment_version_chain(conn, 10)
    assert [r["VersionNumber"] for r in rows] == [1, 2]
    sql = store["executed"][0][0]
    # soft-delete 제외 + 체인 스코프 + 정렬 계약.
    assert "deletedat is null" in sql
    assert "rootattachmentid = %s or id = %s" in sql
    assert "order by versionnumber asc" in sql


def test_v2_chain_loader_prefers_pg_mirror(monkeypatch):
    import sys
    import types
    pg_rows = [_row(vid=10, version=1), _row(vid=11, version=2), _row(vid=12, version=3)]
    apm = types.ModuleType("web.modules.attachment_pg_mirror")
    apm.read_pg_enabled = lambda: True
    apm.pg_get_attachment_versions = lambda root: list(pg_rows)
    web_pkg = types.ModuleType("web")
    web_pkg.__path__ = []
    modules_pkg = types.ModuleType("web.modules")
    modules_pkg.__path__ = []
    modules_pkg.attachment_pg_mirror = apm
    web_pkg.modules = modules_pkg
    monkeypatch.setitem(sys.modules, "web", web_pkg)
    monkeypatch.setitem(sys.modules, "web.modules", modules_pkg)
    monkeypatch.setitem(sys.modules, "web.modules.attachment_pg_mirror", apm)

    store: dict = {}
    conn = _Conn(store)
    rows = app._load_attachment_version_chain(conn, 10)
    assert [r["VersionNumber"] for r in rows] == [1, 2, 3]
    assert conn.cursor_calls == 0, "PG 미러 활성인데 MySQL cursor 를 열었다"


# ── B1~B6: diff 뷰 빌더 ─────────────────────────────────────────────────────
def test_b1_view_rows_align_insert_delete_replace():
    left = "a\nb\nc"
    right = "a\nB\nc\nd"
    view = app._build_version_diff_view(
        left, right, left_version=1, right_version=2, filename="f.sql", context_lines=None)
    kinds = [r["type"] for r in view["rows"]]
    assert kinds == ["equal", "replace", "equal", "insert"]
    rep = view["rows"][1]
    assert rep["left"] == "b" and rep["right"] == "B"
    assert rep["left_no"] == 2 and rep["right_no"] == 2
    ins = view["rows"][3]
    assert ins["left"] is None and ins["right"] == "d" and ins["left_no"] is None
    assert view["stats"]["added"] == 2 and view["stats"]["removed"] == 1
    assert "--- f.sql (v1)" in view["unified"] and "+++ f.sql (v2)" in view["unified"]


def test_b2_replace_pads_uneven_sides():
    # 좌 3줄이 우 1줄로 교체 — 남는 좌측 2줄이 delete 행으로 떨어져야 정렬이 유지된다.
    view = app._build_version_diff_view(
        "x1\nx2\nx3", "y1", left_version=1, right_version=2, filename="f", context_lines=None)
    kinds = [r["type"] for r in view["rows"]]
    assert kinds == ["replace", "delete", "delete"]
    assert [r["left"] for r in view["rows"]] == ["x1", "x2", "x3"]
    assert view["rows"][1]["right"] is None and view["rows"][1]["right_no"] is None


def test_b3_context_collapses_far_equal_runs_and_surfaces_skipped():
    left = "\n".join(["ctx"] * 20 + ["old"])
    right = "\n".join(["ctx"] * 20 + ["new"])
    view = app._build_version_diff_view(
        left, right, left_version=1, right_version=2, filename="f", context_lines=3)
    gaps = [r for r in view["rows"] if r["type"] == "gap"]
    assert len(gaps) == 1, "먼 equal 런이 gap 하나로 접혀야 한다"
    # 20줄 중 변경 주변 3줄만 남으므로 17줄 생략 — 그 수가 응답에 노출된다.
    assert gaps[0]["skipped"] == 17
    assert sum(1 for r in view["rows"] if r["type"] == "equal") == 3


def test_b3b_gap_carries_line_ranges_for_local_expand():
    """gap 에 줄번호 범위가 실려야 프론트가 "N줄 생략" 클릭 시 **그 구간만** 되살릴 수 있다.
    개수(`skipped`)만으로는 위치를 알 수 없다(사용자 요청 2026-08-07 국소 전개의 전제)."""
    left = "\n".join(["ctx"] * 20 + ["old"] + ["tail"] * 20)
    right = "\n".join(["ctx"] * 20 + ["new"] + ["tail"] * 20)
    view = app._build_version_diff_view(
        left, right, left_version=1, right_version=2, filename="f", context_lines=3)
    gaps = [r for r in view["rows"] if r["type"] == "gap"]
    assert len(gaps) == 2, "앞·뒤 두 구간이 각각 접혀야 한다"
    head, tail = gaps
    assert (head["left_from"], head["left_to"]) == (1, 17), head
    assert (head["right_from"], head["right_to"]) == (1, 17), head
    assert head["skipped"] == 17
    assert tail["left_from"] == 25 and tail["left_to"] == 41, tail
    assert tail["skipped"] == 17
    # 범위 길이와 skipped 가 일치해야 전개 결과가 정확히 그 구간이다.
    for g in gaps:
        assert g["left_to"] - g["left_from"] + 1 == g["skipped"], g


def test_b3c_gap_ranges_absent_when_no_collapse():
    """전체 맥락에서는 gap 이 없으므로 범위 필드도 없다(전개 버튼 미부착의 근거)."""
    left = "\n".join(["ctx"] * 10 + ["old"])
    right = "\n".join(["ctx"] * 10 + ["new"])
    view = app._build_version_diff_view(
        left, right, left_version=1, right_version=2, filename="f", context_lines=None)
    assert not [r for r in view["rows"] if r["type"] == "gap"]


def test_b4_full_context_emits_every_line():
    left = "\n".join(["ctx"] * 10 + ["old"])
    right = "\n".join(["ctx"] * 10 + ["new"])
    view = app._build_version_diff_view(
        left, right, left_version=1, right_version=2, filename="f", context_lines=None)
    assert not any(r["type"] == "gap" for r in view["rows"])
    assert sum(1 for r in view["rows"] if r["type"] == "equal") == 10


def test_b5_row_cap_truncates_and_flags():
    left = "\n".join(f"a{i}" for i in range(50))
    right = "\n".join(f"b{i}" for i in range(50))
    view = app._build_version_diff_view(
        left, right, left_version=1, right_version=2, filename="f",
        context_lines=None, row_cap=10)
    assert len(view["rows"]) == 10
    assert view["truncated"]["rows"] is True


def test_b6_identical_is_independent_of_collapse_and_cap():
    same = "\n".join(["line"] * 40)
    view = app._build_version_diff_view(
        same, same, left_version=1, right_version=3, filename="f",
        context_lines=3, row_cap=5)
    assert view["stats"]["identical"] is True
    assert view["stats"]["added"] == 0 and view["stats"]["removed"] == 0


# ── E1~E11: 엔드포인트 ──────────────────────────────────────────────────────
def _endpoint_setup(monkeypatch, chain, objects, *, allowed=True, fail_keys=(), pending=False):
    store: dict = {}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    _patch_auth(monkeypatch, allowed=allowed, base=chain[0], pending=pending)
    monkeypatch.setattr(
        app, "_load_attachment_version_chain",
        lambda c, root, scope_row=None: list(chain))
    storage = _install_storage(monkeypatch, _Storage(objects, fail_keys=fail_keys))
    return conn, storage


def test_e1_adjacent_pair_diff(monkeypatch):
    chain = [_row(vid=10, version=1), _row(vid=11, version=2, superseded=False)]
    objects = {
        "conv-1/u1/f.sql": b"SELECT 1;\nSELECT 2;\n",
        "conv-1/u2/f.sql": b"SELECT 1;\nSELECT 3;\n",
    }
    _endpoint_setup(monkeypatch, chain, objects)
    resp = att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=2))
    body = _body(resp)
    assert body["comparable"] is True
    assert body["from"]["version_number"] == 1 and body["to"]["version_number"] == 2
    assert body["identical"] is False
    assert body["stats"]["added"] == 1 and body["stats"]["removed"] == 1
    assert any(r["type"] == "replace" for r in body["rows"])
    assert "SELECT 3;" in body["unified_diff"]
    assert body["truncated"] == {"from_source": False, "to_source": False, "rows": False}


def test_e2_multi_step_pair_skips_intermediate(monkeypatch):
    chain = [
        _row(vid=10, version=1),
        _row(vid=11, version=2),
        _row(vid=12, version=3),
    ]
    objects = {
        "conv-1/u1/f.sql": b"A\n",
        "conv-1/u2/f.sql": b"B\n",
        "conv-1/u3/f.sql": b"C\n",
    }
    _, storage = _endpoint_setup(monkeypatch, chain, objects)
    resp = att_router.get_attachment_version_diff(12, _Request(from_version=1, to_version=3))
    body = _body(resp)
    assert body["comparable"] is True
    # v2 원본은 읽지 않는다 — 요청한 두 버전만 대상.
    assert storage.reads == ["conv-1/u1/f.sql", "conv-1/u3/f.sql"]
    assert body["from"]["version_number"] == 1 and body["to"]["version_number"] == 3
    assert body["stats"]["added"] == 1 and body["stats"]["removed"] == 1


def test_e3_same_version_rejected(monkeypatch):
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    _endpoint_setup(monkeypatch, chain, {})
    resp = att_router.get_attachment_version_diff(11, _Request(from_version=2, to_version=2))
    assert resp.status_code == 400


def test_e4_bad_params_rejected(monkeypatch):
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    _endpoint_setup(monkeypatch, chain, {})
    assert att_router.get_attachment_version_diff(11, _Request()).status_code == 400
    assert att_router.get_attachment_version_diff(
        11, _Request(from_version="x", to_version=2)).status_code == 400
    assert att_router.get_attachment_version_diff(
        11, _Request(from_version=1, to_version=2, context="huh")).status_code == 400


def test_e5_version_outside_chain_is_404_not_400(monkeypatch):
    """존재 여부 oracle 차단 — 체인 밖 번호에 400('있지만 잘못됨')을 주지 않는다."""
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    _endpoint_setup(monkeypatch, chain, {})
    resp = att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=9))
    assert resp.status_code == 404


def test_e6_permission_denied_is_404(monkeypatch):
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    _endpoint_setup(monkeypatch, chain, {}, allowed=False)
    resp = att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=2))
    assert resp.status_code == 404


def test_e7_binary_downgrades_to_meta_compare(monkeypatch):
    chain = [
        _row(vid=10, version=1, kind="pdf", sha="deadbeef"),
        _row(vid=11, version=2, kind="pdf", sha="deadbeef"),
    ]
    _, storage = _endpoint_setup(monkeypatch, chain, {})
    resp = att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=2))
    body = _body(resp)
    assert body["comparable"] is False and body["reason"] == "binary"
    assert body["identical"] is True          # 해시 동일
    assert "rows" not in body                 # 빈 diff 를 흉내내지 않는다
    assert storage.reads == []                # 바이너리 원본은 읽지 않는다


def test_e8_source_cap_truncation_is_surfaced(monkeypatch):
    cap = int(app._ASSISTANT_EDIT_SIZE_CAP_BYTES)
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    objects = {
        "conv-1/u1/f.sql": b"x\n" * (cap // 2 + 10),   # cap 초과
        "conv-1/u2/f.sql": b"y\n",
    }
    _endpoint_setup(monkeypatch, chain, objects)
    resp = att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=2))
    body = _body(resp)
    assert body["truncated"]["from_source"] is True
    assert body["truncated"]["to_source"] is False
    assert body["caps"]["source_bytes"] == cap


def test_e9_source_read_failure_is_503(monkeypatch):
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    objects = {"conv-1/u2/f.sql": b"y\n"}
    _endpoint_setup(monkeypatch, chain, objects, fail_keys=("conv-1/u1/f.sql",))
    resp = att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=2))
    assert resp.status_code == 503
    assert _body(resp)["reason"] == "source_unavailable"


def test_e10_context_full_passes_through(monkeypatch):
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    body_left = "\n".join(["ctx"] * 12 + ["old"]).encode()
    body_right = "\n".join(["ctx"] * 12 + ["new"]).encode()
    objects = {"conv-1/u1/f.sql": body_left, "conv-1/u2/f.sql": body_right}
    _endpoint_setup(monkeypatch, chain, objects)

    default = _body(att_router.get_attachment_version_diff(
        11, _Request(from_version=1, to_version=2)))
    assert any(r["type"] == "gap" for r in default["rows"])
    assert default["context_lines"] == app._VERSION_DIFF_CONTEXT_DEFAULT

    full = _body(att_router.get_attachment_version_diff(
        11, _Request(from_version=1, to_version=2, context="full")))
    assert full["context_lines"] is None
    assert not any(r["type"] == "gap" for r in full["rows"])


def test_e12_pending_account_blocked_like_download(monkeypatch):
    """D21 — diff 행은 파일 **본문**이다. 승인 대기 계정 판정은 metadata 조회(signed URL 보류)가
    아니라 본문 다운로드(403)와 동형이어야 한다. 아니면 diff 가 bytes-deny 우회 경로가 된다."""
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    objects = {"conv-1/u1/f.sql": b"secret A\n", "conv-1/u2/f.sql": b"secret B\n"}
    _, storage = _endpoint_setup(monkeypatch, chain, objects, pending=True)
    resp = att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=2))
    assert resp.status_code == 403
    # 본문을 한 번도 읽지 않았다 — 게이트가 원본 조회 **앞**에 있다.
    assert storage.reads == []
    assert b"secret" not in resp.body


def test_e13_chain_scope_guard_drops_foreign_rows(monkeypatch):
    """체인 스코프(conversation·account) 밖 행은 기준 첨부 게이트가 덮지 못한다 — 가정이 아니라
    필터로 막는다(fail-closed). 정상 데이터에서는 아무것도 걸러지지 않는다."""
    import sys
    import types
    base = _row(vid=10, version=1)
    foreign = _row(vid=99, version=2)
    foreign["ConversationId"] = "conv-OTHER"
    pg_rows = [base, foreign, _row(vid=11, version=3)]
    apm = types.ModuleType("web.modules.attachment_pg_mirror")
    apm.read_pg_enabled = lambda: True
    apm.pg_get_attachment_versions = lambda root: list(pg_rows)
    web_pkg = types.ModuleType("web")
    web_pkg.__path__ = []
    modules_pkg = types.ModuleType("web.modules")
    modules_pkg.__path__ = []
    modules_pkg.attachment_pg_mirror = apm
    web_pkg.modules = modules_pkg
    monkeypatch.setitem(sys.modules, "web", web_pkg)
    monkeypatch.setitem(sys.modules, "web.modules", modules_pkg)
    monkeypatch.setitem(sys.modules, "web.modules.attachment_pg_mirror", apm)

    conn = _Conn({})
    # scope_row 없이 부르면 전부 반환(기존 계약 — 호출자가 게이트를 책임진다).
    assert len(app._load_attachment_version_chain(conn, 10)) == 3
    # scope_row 를 주면 타 대화 행이 제외된다.
    scoped = app._load_attachment_version_chain(conn, 10, scope_row=base)
    assert [r["Id"] for r in scoped] == [10, 11]
    # 계정 축도 동일.
    other_acct = dict(base)
    other_acct["AccountId"] = 2
    assert app._load_attachment_version_chain(conn, 10, scope_row=other_acct) == []


def test_e14_both_endpoints_pass_scope_row(monkeypatch):
    """스코프 재확인이 **두 엔드포인트 모두** 걸려야 한다 — 한쪽만 걸면 그쪽만 안전하다."""
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    objects = {"conv-1/u1/f.sql": b"a\n", "conv-1/u2/f.sql": b"b\n"}
    _endpoint_setup(monkeypatch, chain, objects)
    seen: list[object] = []

    def _spy(conn, root, scope_row=None):
        seen.append(scope_row)
        return list(chain)

    monkeypatch.setattr(app, "_load_attachment_version_chain", _spy)
    att_router.get_attachment_versions(11, _Request())
    att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=2))
    assert len(seen) == 2
    assert all(s is not None and s.get("Id") == 10 for s in seen), \
        "한 엔드포인트가 scope_row 없이 체인을 로드했다"


def test_e11_versions_and_diff_share_one_chain_loader(monkeypatch):
    """목록과 비교가 서로 다른 체인 집합을 보면, 목록에 있는 버전을 비교하지 못한다.
    두 엔드포인트가 같은 로더를 통과함을 호출 계수로 고정한다."""
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    objects = {"conv-1/u1/f.sql": b"a\n", "conv-1/u2/f.sql": b"b\n"}
    _endpoint_setup(monkeypatch, chain, objects)
    calls: list[int] = []
    real = app._load_attachment_version_chain

    def _counting(conn, root, scope_row=None):
        calls.append(int(root))
        return list(chain)

    monkeypatch.setattr(app, "_load_attachment_version_chain", _counting)
    assert real is not _counting  # sanity: 우리가 실제로 그 심볼을 갈아끼웠다

    att_router.get_attachment_versions(11, _Request())
    att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=2))
    assert len(calls) == 2, "두 엔드포인트 중 하나가 자체 체인 SQL 로 우회했다"
