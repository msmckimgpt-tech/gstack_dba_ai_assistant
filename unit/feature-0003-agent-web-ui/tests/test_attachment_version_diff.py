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
  V3  체인 로더 — **PG 미러 경로도** soft-delete 를 제외한다(MySQL 만 걸면 미러 활성 시 무방비).
  V3b 접합부 — `DeletePending = 1` 로 만드는 모든 write 가 같은 statement 에서 `DeletedAt` 도
      채운다 ⇒ `DeletePending=1 AND DeletedAt IS NULL` 은 도달 불가 ⇒ 체인 로더의 `DeletedAt
      IS NULL` 단일 필터가 삭제 버전 배제에 충분하다. 이 전제가 깨지면(새 삭제 경로가 DeletedAt
      을 안 채우면) 삭제한 버전이 비교 선택기에 되살아나므로, 읽어서 확인한 것을 고정한다
      (REQ-20260806-attach-manage 리베이스로 생긴 접합부, 2026-08-07).
  B1  diff 뷰 — 순수 추가/삭제/교체 opcode 가 좌우 정렬 행으로 펼쳐진다.
  B2  diff 뷰 — replace 의 좌우 줄 수가 다르면 짧은 쪽을 None 으로 패딩(정렬 붕괴 방지).
  B3  diff 뷰 — 기본 맥락(3줄) 밖 equal 런이 gap 행으로 접히고 **생략 줄 수를 표면화**.
  B3b diff 뷰 — gap 에 좌·우 줄번호 범위가 실린다(프론트 국소 전개의 전제, 2026-08-07).
  B3c diff 뷰 — 전체 맥락에서는 gap 자체가 없다.
  B4  diff 뷰 — context_lines=None 이면 동일 줄도 전부 방출(gap 없음).
  B5  diff 뷰 — 행 상한 초과 시 잘리고 truncated.rows=True (무음 절단 금지).
  B6  diff 뷰 — 내용 동일이면 identical=True 이고 축약·행 상한과 무관.
  B7  diff 뷰 — 내용 동일이면 **원문 전량**이 equal 행으로 나온다(gap 으로 접지 않는다).
      맥락 축약은 변경 주변만 남기는 연산이라 변경 0개면 파일 전체가 gap 한 줄이 되어 화면에
      본문이 사라진다 — 사용자 요청 "파일 내용이 동일하다면 문서 원문을 출력" (2026-08-07).
  B7b diff 뷰 — 원문 전량 방출도 행 상한을 넘지 않고, 넘으면 truncated.rows 로 표면화.
  B7c diff 뷰 — 빈 문서끼리는 행 0개(프론트가 '비어 있습니다' 로 답하는 근거).
  B20  intra-line — replace 행에 좌우 세그먼트가 실리고 이어 붙이면 원문과 바이트 동치.
  B21  intra-line — CJK 는 **글자 단위**(어절 통짜 강조는 사용자 요청 미달).
  B22  intra-line — ASCII 단어는 통 토큰(글자 단위로 쪼개면 색종이).
  B23 intra-line — 무관한 쌍은 세그먼트를 주지 않고 줄 단위로 폴백.
  B24 intra-line — insert/delete 행은 대응 줄이 없어 세그먼트 없음.
  B25 intra-line — 상한 초과 긴 줄은 세그먼트 없이도 줄 단위 변경은 유지.
  B26 intra-line — 세그먼트는 행 상한 **통과 행에만** 계산(잘린 행 비용 0).
  B27 intra-line — 자소 묶음(결합 문자·VS·ZWJ·피부톤)이 토큰 경계에 갈리지 않는다.
  B28 intra-line — 작업량 예산 초과 시 `truncated.intraline` 로 표면화 + 줄 단위는 온전.
  B29 intra-line — 정상 diff 는 절단을 주장하지 않는다(배너 늑대소년 방지 — 비율 컷 제외).
  B30 intra-line — 바뀐 조각을 **자소 단위로 정밀화**(식별자·해시 부분 변경이 통째로 안 칠해짐).
  B31 intra-line — 바뀌지 않은 글자를 변경으로 **주장하지 않는다**(흡수 규칙 제거 회귀 잠금).
  B32 intra-line — 악센트 라틴이 단어 런을 끊지 않는다(`café`→`cafe` 마크 0 회귀).
  B33 intra-line — **비용 가드**(길이·문자쌍 컷)만 `truncated.intraline` 로 표면화.
  B34 intra-line — 비용 가드가 **토큰화보다 먼저** 걸린다(대리값 함정 회귀 잠금).
  B35 intra-line — 정밀화도 자소 클러스터를 가르지 않는다(ZWJ·keycap·국기).
  B36 intra-line — 국기·emoji tag sequence 가 한 토큰이다.
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
  E15 엔드포인트 — 텍스트 두 버전의 내용이 같으면 identical=True 와 **원문 행**을 함께 준다
      (B7 의 계약이 응답 payload 까지 도달하는지 — 빌더만 고쳐도 라우터가 삼키면 화면은 그대로).
"""
from __future__ import annotations

import json

import app
from routers import attachments as att_router
# intra-line 상한은 app.py 가 쓰지 않는 내부 상수라 재-export 하지 않는다 — 사는 곳에서 읽는다.
from routers import _conv_store


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
        # ranged read 는 **별 목록**으로 센다 — "전체를 적재했는가" 와 "앞부분만 읽었는가" 는
        # 다른 사실이고, 원문 보기는 후자여야 한다(§18.8 security: 최대 25× 증폭 회피).
        self.head_reads: list[tuple[str, int]] = []

    def get_object_bytes(self, object_key, **_kw):
        self.reads.append(object_key)
        if object_key in self._fail:
            raise self.StorageOperationError("simulated read failure")
        return self._objects[object_key]

    def get_object_head_bytes(self, object_key, *, max_bytes, **_kw):
        self.head_reads.append((object_key, int(max_bytes)))
        if not object_key:
            raise self.StorageConfigError("object_key required")
        if object_key in self._fail:
            raise self.StorageOperationError("simulated read failure")
        return self._objects[object_key][: int(max_bytes)]

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


def _src(rel: str) -> str:
    """`unit/feature-0003-agent-web-ui/src/<rel>` 원문. 테스트 파일 위치에서 상대 해석."""
    import pathlib
    return (pathlib.Path(__file__).resolve().parent.parent / "src" / rel).read_text(encoding="utf-8")


def test_v3_pg_mirror_version_query_also_excludes_soft_deleted():
    """PG 미러 경로도 soft-delete 를 제외한다.

    체인 로더는 미러가 활성이면 **PG 만** 읽는다(V2). MySQL SQL 에만 `DeletedAt IS NULL` 이
    있으면(V1) 미러 활성 환경에서는 삭제한 버전이 비교 선택기에 그대로 남는다 — 한쪽만 걸린
    필터는 안 걸린 것과 같다.
    """
    src = _src("modules/attachment_pg_mirror.py")
    i = src.index("def pg_get_attachment_versions")
    body = src[i:src.index("\ndef ", i + 1)]
    norm = " ".join(body.lower().split())
    assert "deleted_at is null" in norm, "PG 미러 버전 조회에 soft-delete 필터가 없다"
    assert "root_attachment_id = %s or id = %s" in norm, "PG 미러 체인 스코프가 바뀌었다"


def test_v3b_delete_pending_writes_always_set_deleted_at():
    """`DeletePending = 1` 로 만드는 모든 write 가 같은 statement 에서 `DeletedAt` 도 채운다.

    체인 로더는 `DeletedAt IS NULL` **하나만** 본다(목록 엔드포인트는 `DeletePending = 0` 까지
    본다 — 비대칭이 의도적이다). 그 단일 필터가 충분한 근거는 "두 컬럼이 항상 함께 세팅된다" 는
    이 불변식뿐이다. 새 삭제 경로가 `DeletePending` 만 세우면 삭제한 버전이 비교 선택기에
    되살아나고, 그 실패는 조용하다(에러 없이 목록에만 안 보인다).
    """
    import re
    hits = []
    for rel in ("routers/attachments.py", "modules/attachment_reconciliation.py",
                "routers/conversations.py", "routers/_conv_store.py"):
        src = _src(rel)
        for m in re.finditer(r"SET\s+DeletePending\s*=\s*1(.*?)(?:WHERE|\"\"\")", src, re.S | re.I):
            hits.append((rel, m.group(1)))
    assert hits, "DeletePending=1 write 를 하나도 못 찾았다 — 패턴이 낡았다(허위 통과 방지)"
    for rel, tail in hits:
        assert re.search(r"DeletedAt\s*=", tail, re.I), (
            f"{rel}: DeletePending=1 을 세우면서 DeletedAt 을 채우지 않는다 — "
            "삭제한 버전이 diff 비교 선택기에 남는다"
        )


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


def test_b7_identical_emits_full_source_rows_not_a_gap():
    """내용이 동일하면 **원문 전량**이 행으로 나와야 한다 (사용자 요청 2026-08-07).

    맥락 축약은 '변경 지점 주변만 남기는' 연산이라 변경이 0개면 파일 전체가 gap 한 줄로
    접힌다 — 종전에는 그 화면에 본문이 한 줄도 없었다. 프론트가 원문을 그리려면 서버가
    행을 줘야 하므로, identical 은 `context_lines` 값과 무관하게 축약 대상이 아니다.
    """
    same = "\n".join(f"line{i}" for i in range(40))
    view = app._build_version_diff_view(
        same, same, left_version=1, right_version=3, filename="f", context_lines=3)
    assert view["stats"]["identical"] is True
    assert not [r for r in view["rows"] if r["type"] == "gap"], "identical 은 접히지 않는다"
    assert len(view["rows"]) == 40
    assert all(r["type"] == "equal" for r in view["rows"])
    # 원문 무손실 — 행의 좌/우 텍스트를 이어붙이면 입력과 동일해야 한다(렌더가 원문이라 주장하려면
    # 그 행이 원문이어야 한다). 좌우 어느 쪽으로 이어붙여도 같다.
    assert "\n".join(r["right"] for r in view["rows"]) == same
    assert "\n".join(r["left"] for r in view["rows"]) == same
    assert view["rows"][0]["right_no"] == 1 and view["rows"][-1]["right_no"] == 40


def test_b7b_identical_still_respects_row_cap_and_flags_truncation():
    """원문 전량 방출도 행 상한을 넘지 못한다 — 넘으면 무음이 아니라 플래그로 표면화한다."""
    same = "\n".join(f"line{i}" for i in range(50))
    view = app._build_version_diff_view(
        same, same, left_version=1, right_version=2, filename="f",
        context_lines=3, row_cap=10)
    assert view["stats"]["identical"] is True
    assert len(view["rows"]) == 10
    assert view["truncated"]["rows"] is True


def test_b7c_identical_empty_document_has_no_rows():
    """빈 문서끼리의 비교는 행이 0개다 — 프론트는 이 경우 '비어 있습니다' 로 답한다."""
    view = app._build_version_diff_view(
        "", "", left_version=1, right_version=2, filename="f", context_lines=3)
    assert view["stats"]["identical"] is True
    assert view["rows"] == []
# ── B20~B25: intra-line 세그먼트 (사용자 요청 2026-08-07) ─────────────────────
# "여전히 line 단위 차이만 나타나고 각 글자 단위의 차이점은 출력되지 않는다."
# 세그먼트는 **서버가 단독으로** 정한다(2열·단일열이 같은 구간을 보게 하는 불변식의 연장).
def _seg_text(segs):
    """세그먼트를 이어 붙인 원문 — 프론트가 문자 오프셋으로 덧그리는 근거가 되는 계약."""
    return "".join(s["v"] for s in segs)


def _changed(segs):
    return [s["v"] for s in segs if s["t"] == "ch"]


def test_b20_replace_rows_carry_intraline_segments_roundtrip():
    view = app._build_version_diff_view(
        "SELECT id FROM users WHERE a = 1",
        "SELECT id FROM users WHERE a = 2",
        left_version=1, right_version=2, filename="q.sql", context_lines=None)
    row = [r for r in view["rows"] if r["type"] == "replace"][0]
    # 이어 붙이면 원문과 **바이트 동치** — 이 계약이 깨지면 프론트가 마킹을 통째로 포기한다.
    assert _seg_text(row["left_segs"]) == row["left"]
    assert _seg_text(row["right_segs"]) == row["right"]
    assert _changed(row["left_segs"]) == ["1"]
    assert _changed(row["right_segs"]) == ["2"]


def test_b21_cjk_is_segmented_per_character_not_per_word():
    """한글은 어절 안에서 한두 글자만 바뀌므로 **글자 단위**여야 변경 지점이 드러난다."""
    view = app._build_version_diff_view(
        "이 문서는 수정합니다.", "이 문서는 삭제합니다.",
        left_version=1, right_version=2, filename="note.md", context_lines=None)
    row = [r for r in view["rows"] if r["type"] == "replace"][0]
    assert _changed(row["left_segs"]) == ["수정"]
    assert _changed(row["right_segs"]) == ["삭제"]
    # 어절 전체("수정합니다")가 통으로 잡히면 사용자 요청("각 글자 단위")이 미달이다.
    assert "합니다" not in "".join(_changed(row["left_segs"]))


def test_b22_ascii_word_is_the_alignment_unit_not_the_mark_unit():
    """단어 토큰은 **정렬 앵커**일 뿐 마크 단위가 아니다 — 마크는 글자까지 좁혀진다.

    순수 문자 diff 는 `SELECT`↔`INSERT` 에서 공통 글자를 흩어 잡아 색종이가 되므로 정렬은
    토큰으로 잡는다. 그러나 정렬이 끝난 뒤의 마크는 사용자가 요청한 대로 글자 단위여야 한다
    (§18.8 ux 패널: 한글만 글자별이고 영문은 통짜인 비대칭 지적).
    """
    view = app._build_version_diff_view(
        "alpha beta gamma", "alpha delta gamma",
        left_version=1, right_version=2, filename="a.txt", context_lines=None)
    row = [r for r in view["rows"] if r["type"] == "replace"][0]
    assert "beta" not in _changed(row["left_segs"])      # 어절 통짜가 아니다
    assert "delta" not in _changed(row["right_segs"])
    assert _seg_text(row["left_segs"]) == row["left"]
    assert _seg_text(row["right_segs"]) == row["right"]


def test_b23_unrelated_pair_falls_back_to_line_level():
    """무관한 두 줄이 위치로 짝지어지면 조각 강조가 신호를 가린다 → 세그먼트를 주지 않는다."""
    view = app._build_version_diff_view(
        "완전히 다른 내용입니다", "totally unrelated line",
        left_version=1, right_version=2, filename="a.txt", context_lines=None)
    row = [r for r in view["rows"] if r["type"] == "replace"][0]
    # 키 자체가 없어야 한다 — 빈 배열이면 프론트가 "구간 0개" 로 읽어 분기가 갈린다.
    assert "left_segs" not in row and "right_segs" not in row


def test_b24_insert_delete_rows_have_no_segments():
    """대응할 상대 줄이 없으면 줄 안 비교 자체가 성립하지 않는다(줄 전체가 변경)."""
    view = app._build_version_diff_view(
        "a", "a\nb", left_version=1, right_version=2, filename="a.txt", context_lines=None)
    for r in view["rows"]:
        if r["type"] in ("insert", "delete"):
            assert "left_segs" not in r and "right_segs" not in r


def test_b25_long_lines_skip_segments_but_keep_line_diff():
    """O(n²) 방어 — 상한 초과 줄은 세그먼트 없이도 **줄 단위 변경은 그대로** 보인다."""
    left = "x" * (_conv_store._INTRALINE_MAX_LEN + 10)
    view = app._build_version_diff_view(
        left, left + "y", left_version=1, right_version=2, filename="a.txt",
        context_lines=None)
    row = [r for r in view["rows"] if r["type"] == "replace"][0]
    assert "left_segs" not in row
    assert view["stats"]["added"] == 1 and view["stats"]["removed"] == 1


def test_b27_grapheme_clusters_are_not_split_by_token_boundary():
    """자소 묶음(결합 문자·variation selector·ZWJ)이 토큰 경계에 걸리면 화면에서 합자가 깨진다.

    텍스트는 보존되지만 **원문과 달라 보이는** 렌더가 나오므로, 문자 단위 diff 의 목적을 어긴다.
    """
    tok = _conv_store._intraline_tokens
    # ZWJ 가족 이모지는 통째로 한 토큰이어야 한다(낱개 이모지 여럿으로 쪼개지면 안 됨).
    family = "\U0001F468‍\U0001F469‍\U0001F467"
    assert tok(f"a{family}b") == ["a", family, "b"]
    # 결합 악센트는 앞 문자에 붙는다.
    assert tok("é") == ["é"]
    # variation selector·피부톤 modifier 도 앞 문자에 흡수.
    assert tok("❤️") == ["❤️"]
    assert tok("\U0001F44D\U0001F3FD") == ["\U0001F44D\U0001F3FD"]
    # 실제 diff 에서도 경계가 자소를 가르지 않는다.
    view = app._build_version_diff_view(
        f"상태 {family} 확인", "상태 \U0001F600 확인",
        left_version=1, right_version=2, filename="a.md", context_lines=None)
    row = [r for r in view["rows"] if r["type"] == "replace"][0]
    assert _changed(row["left_segs"]) == [family]
    assert _seg_text(row["left_segs"]) == row["left"]


def test_b28_work_budget_surfaces_intraline_truncation():
    """O(n·m) 예산을 넘어 마크를 생략한 줄이 있으면 **표면화**한다(무음 정밀도 하락 금지).

    예산이 없으면 폭 2000자 × 1500행에서 411초까지 갔다(실측 2026-08-07) — 상한이 행 수가
    아니라 작업량인 이유. 여기서는 그 상한이 실제로 걸리고, **줄 단위 차이는 온전한지**를 본다.
    """
    wide_l = "\n".join(",".join(f"c{i}v{j}" for i in range(300)) for j in range(40))
    wide_r = "\n".join(",".join(f"c{i}w{j}" for i in range(300)) for j in range(40))
    view = app._build_version_diff_view(
        wide_l, wide_r, left_version=1, right_version=2, filename="w.csv",
        context_lines=None)
    reps = [r for r in view["rows"] if r["type"] == "replace"]
    assert len(reps) == 40                       # 줄 단위 diff 는 전부 살아 있다
    assert view["truncated"]["intraline"] is True
    assert any("left_segs" not in r for r in reps)


def test_b29_normal_diff_does_not_claim_intraline_truncation():
    """늑대소년 방지 — 배너는 **비용 가드**(길이·문자쌍 컷)에만 뜬다.

    비율 컷이 걸린 줄(좌우가 사실상 전혀 다름)은 화면에서 이미 "통째로 바뀜" 으로 정확히
    읽히므로 알릴 오해가 없다. 그것까지 세면 재작성이 많은 diff 마다 배너가 상시 표시된다.
    """
    view = app._build_version_diff_view(
        "alpha\nbeta", "alpha\ngamma", left_version=1, right_version=2,
        filename="a.txt", context_lines=None)
    assert view["truncated"]["intraline"] is False
    # 무관한 쌍(비율 컷)·insert/delete 도 절단으로 세지 않는다.
    view2 = app._build_version_diff_view(
        "완전히 다른 내용입니다", "totally unrelated line",
        left_version=1, right_version=2, filename="a.txt", context_lines=None)
    assert view2["truncated"]["intraline"] is False


def test_b26_segments_only_for_rows_that_survive_cap():
    """행 상한으로 잘린 행에는 비용을 치르지 않는다(세그먼트는 표시 확정 뒤에 계산)."""
    left = "\n".join(f"line {i} a" for i in range(20))
    right = "\n".join(f"line {i} b" for i in range(20))
    view = app._build_version_diff_view(
        left, right, left_version=1, right_version=2, filename="a.txt",
        context_lines=None, row_cap=5)
    assert view["truncated"]["rows"] is True
    assert len(view["rows"]) == 5
    assert all("left_segs" in r for r in view["rows"] if r["type"] == "replace")


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
    # 절단 4종(내용 3 + 정밀도 1)을 **전부** 열거해 잠근다 — 키가 늘거나 줄면 여기가 먼저 깨진다.
    assert body["truncated"] == {
        "from_source": False, "to_source": False, "rows": False, "intraline": False}


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


def test_e15_identical_text_returns_source_rows(monkeypatch):
    """텍스트 두 버전의 내용이 같을 때 응답이 원문 행을 싣는다 (사용자 요청 2026-08-07).

    빌더(B7)만 고치고 라우터가 rows 를 안 실으면 화면은 종전과 같다 — 계약이 payload 까지
    도달하는지를 별도로 잠근다. 기본 요청(`context` 미지정 = 축약 3줄)으로 확인해야 의미가 있다.
    """
    body_text = "SELECT 1;\nSELECT 2;\nSELECT 3;\nSELECT 4;\nSELECT 5;\n"
    chain = [_row(vid=10, version=1), _row(vid=11, version=2, superseded=False)]
    objects = {
        "conv-1/u1/f.sql": body_text.encode(),
        "conv-1/u2/f.sql": body_text.encode(),
    }
    _endpoint_setup(monkeypatch, chain, objects)
    resp = att_router.get_attachment_version_diff(11, _Request(from_version=1, to_version=2))
    body = _body(resp)
    assert body["comparable"] is True
    assert body["identical"] is True
    assert not [r for r in body["rows"] if r["type"] == "gap"]
    assert [r["right"] for r in body["rows"]] == body_text.splitlines()
    assert body["truncated"]["rows"] is False


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


# ── B30~B36: §18.8 적대 패널(ux · backend) 흡수 (2026-08-07) ─────────────────
def test_b30_changed_run_is_refined_to_characters():
    """토큰 단위로 잡힌 변경 조각을 자소 단위로 좁힌다.

    패널 실측: `m.last_login_at`→`m.last_logout_at` 이 식별자 **전체**를 칠했고,
    `sha256: …855`→`…856` 은 한 토큰이 줄의 대부분이라 비율 컷에 걸려 **마크가 아예 없었다**.
    사용자가 줄 단위에 대해 제기한 불만이 한 단계 아래에서 반복된 형태다.
    """
    view = app._build_version_diff_view(
        "m.last_login_at = NOW()", "m.last_logout_at = NOW()",
        left_version=1, right_version=2, filename="a.sql", context_lines=None)
    row = [r for r in view["rows"] if r["type"] == "replace"][0]
    assert _changed(row["left_segs"]) == ["in"]
    assert _changed(row["right_segs"]) == ["out"]

    h = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b"
    view2 = app._build_version_diff_view(
        f"-- sha256: {h}855", f"-- sha256: {h}856",
        left_version=1, right_version=2, filename="a.sql", context_lines=None)
    row2 = [r for r in view2["rows"] if r["type"] == "replace"][0]
    assert _changed(row2["left_segs"]) == ["5"]
    assert _changed(row2["right_segs"]) == ["6"]
    assert _seg_text(row2["left_segs"]) == row2["left"]


def test_b31_does_not_claim_unchanged_characters():
    """마크는 **바뀐 글자만** 덮는다 — 짧은 equal 흡수 규칙 제거의 회귀 잠금.

    패널 실측: 흡수가 있으면 CSV `a,b,c,[27,1284000],x` 처럼 필드 구분자까지 삼켜 두 변경이
    한 덩어리로 읽혔고, `2026년 1`/`2027년 3` 은 동일한 `년 ` 을 "바뀌었다" 고 칠했다.
    diff 는 무엇이 바뀌었는지 말하는 화면이므로 과장은 곧 오답이다.
    """
    view = app._build_version_diff_view(
        "a,b,c,27,1284000,x", "a,b,c,31,1341500,x",
        left_version=1, right_version=2, filename="a.csv", context_lines=None)
    row = [r for r in view["rows"] if r["type"] == "replace"][0]
    assert all("," not in v for v in _changed(row["left_segs"])), _changed(row["left_segs"])
    assert _changed(row["left_segs"]) == ["27", "1284000"]
    assert _changed(row["right_segs"]) == ["31", "1341500"]

    view2 = app._build_version_diff_view(
        "본 약관은 2026년 1월 5일부터", "본 약관은 2027년 3월 5일부터",
        left_version=1, right_version=2, filename="a.md", context_lines=None)
    row2 = [r for r in view2["rows"] if r["type"] == "replace"][0]
    assert _changed(row2["left_segs"]) == ["6", "1"]
    assert all("년" not in v and " " not in v for v in _changed(row2["left_segs"]))


def test_b32_accented_latin_stays_one_word_token():
    """`isascii()` 로 좁혔더니 `café` 가 `caf`+`é` 로 갈려 마크가 0개였다(패널 실측)."""
    tok = _conv_store._intraline_tokens
    assert tok("café naïve") == ["café", " ", "naïve"]
    view = app._build_version_diff_view(
        "café naïve 문장", "cafe naive 문장",
        left_version=1, right_version=2, filename="a.txt", context_lines=None)
    row = [r for r in view["rows"] if r["type"] == "replace"][0]
    assert _changed(row["left_segs"]) == ["é", "ï"]
    assert _seg_text(row["left_segs"]) == row["left"]


def test_b33_cost_guards_are_surfaced_not_silent():
    """**비용 가드**로 마크를 못 준 줄은 표면화한다 — 화면만 봐선 알 수 없기 때문이다."""
    long_l = "x" * (_conv_store._INTRALINE_MAX_LEN + 10)
    view = app._build_version_diff_view(
        long_l, long_l + "y", left_version=1, right_version=2, filename="a.txt",
        context_lines=None)
    assert view["truncated"]["intraline"] is True
    assert [r for r in view["rows"] if r["type"] == "replace"]   # 줄 단위는 온전

    w = int(_conv_store._INTRALINE_PAIR_CAP ** 0.5) + 60
    wide_l = "\n".join("a,b;c." * (w // 6) for _ in range(20))
    wide_r = "\n".join("a;b,c." * (w // 6) for _ in range(20))
    view2 = app._build_version_diff_view(
        wide_l, wide_r, left_version=1, right_version=2, filename="w.csv",
        context_lines=None)
    assert view2["truncated"]["intraline"] is True
    assert len([r for r in view2["rows"] if r["type"] == "replace"]) == 20
    assert all("left_segs" not in r for r in view2["rows"] if r["type"] == "replace")

    view3 = app._build_version_diff_view(
        "a", "a\nb", left_version=1, right_version=2, filename="a.txt", context_lines=None)
    assert view3["truncated"]["intraline"] is False


def test_b34_cost_guard_is_checked_before_tokenizing():
    """비용 가드가 **토큰화보다 먼저** 걸리는지 — 대리값 함정의 회귀 잠금.

    초판은 좌·우 '토큰 수의 곱' 을 예산으로 썼는데, 그 값을 알려면 토큰화를 해야 했다.
    §18.8 backend 패널 실측: 예산을 한 푼도 안 쓰고 1,039ms 를 태우는 입력이 존재했고,
    같은 명목 예산에서 실제 시간이 **83배** 벌어졌다. `len(left)*len(right)` 는 O(1) 이다.
    """
    calls = []
    real = _conv_store._intraline_tokens
    try:
        _conv_store._intraline_tokens = lambda s: (calls.append(s), real(s))[1]
        big = "a" * (int(_conv_store._INTRALINE_PAIR_CAP ** 0.5) + 60)
        lsegs, rsegs, degraded = _conv_store._intraline_segments(big, big[:-1] + "b")
        assert lsegs is None and degraded is True
        assert calls == [], "문자쌍 컷은 토큰화 전에 판정해야 한다"
    finally:
        _conv_store._intraline_tokens = real


def test_b35_refine_never_splits_grapheme_clusters():
    """정밀화도 **자소 클러스터** 단위로 자른다.

    §18.8 backend 패널 실측: 초판은 토큰화에만 클러스터 보호를 걸고 정밀화는 raw code point
    `SequenceMatcher` 라, ZWJ 가족 이모지·keycap·국기에서 경계가 클러스터 **내부**에 떨어졌다.
    프론트가 그 경계에서 span 을 쪼개면 합자가 깨져 화면이 원문과 달라 보인다.
    """
    seg = _conv_store._intraline_segments
    cl = _conv_store._grapheme_clusters
    for left, right, label in [
        ("\U0001F468\u200D\U0001F469\u200D\U0001F467 팀 확인",
         "\U0001F468\u200D\U0001F469\u200D\U0001F466 팀 확인", "ZWJ 가족"),
        ("num 1\ufe0f\u20e3 end", "num 2\ufe0f\u20e3 end", "keycap"),
        ("seoul,\U0001F1F0\U0001F1F7,cap", "seoul,\U0001F1F0\U0001F1F5,cap", "국기(RI 쌍)"),
    ]:
        lsegs, rsegs, _ = seg(left, right)
        assert lsegs and rsegs, label
        for segs, orig in ((lsegs, left), (rsegs, right)):
            assert "".join(x["v"] for x in segs) == orig, label
            bounds, acc = set(), 0
            for g in cl(orig):
                acc += len(g)
                bounds.add(acc)
            acc = 0
            for x in segs[:-1]:
                acc += len(x["v"])
                assert acc in bounds, f"{label}: 경계 {acc} 가 자소 클러스터를 가름"


def test_b36_flag_and_tag_sequences_are_single_tokens():
    """국기(지역 지시자 쌍)·emoji tag sequence 도 한 글자로 다룬다(패널 P3)."""
    tok = _conv_store._intraline_tokens
    assert tok("\U0001F1F0\U0001F1F7") == ["\U0001F1F0\U0001F1F7"]
    scot = "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"
    assert tok(scot) == [scot]
