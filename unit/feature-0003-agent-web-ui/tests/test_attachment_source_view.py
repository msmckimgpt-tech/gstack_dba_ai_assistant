"""REQ-20260807T-attach-source-view: 첨부 **원문 보기**(단일 버전) 회귀 테스트.

사용자 요청: "별도로 추가된 버전이 없는 첨부파일 또한, 클릭했을 때 문서 원문이 출력되도록
구성해주세요." (2026-08-07)

경계:
  - `/diff`(REQ-20260806-attach-version-diff)는 **두 버전**을 요구하고 `from==to` 를 400 으로
    막는다. 버전이 하나뿐인 첨부에는 비교할 짝이 없으므로 원문 전용 엔드포인트가 필요하다.
  - 권한은 `/diff` 와 동형(`conversation.attachment.read.{own,any}` + D21 pending 403) —
    **신규 권한 코드 0**. 본문 bytes 를 노출하므로 metadata 조회가 아니라 다운로드와 같은 등급이다.

검증(`make test` agent 이미지, DB 없이 monkeypatch):
  S1  빌더 — 줄이 1-based 줄번호 행으로 펼쳐지고, 이어붙이면 원문과 byte 동일.
  S2  빌더 — 행 상한 초과 시 잘리고 truncated.rows=True (무음 절단 금지).
  S3  빌더 — 빈 문서는 행 0개(프론트가 '비어 있습니다' 로 답하는 근거).
  S4  빌더 — 행 shape 이 diff `rows` 와 **호환**된다(프론트 `_renderSource` 가 `right ?? left` 를
      읽으므로 우측 키만 채운다 — 좌측까지 채우면 같은 글을 두 벌 실어 보내게 된다).
  E1  엔드포인트 — 텍스트 단일 버전 정상 조회(viewable/rows/stats/version 메타).
  E2  엔드포인트 — 권한 미보유 → 404.
  E3  엔드포인트 — **D21** 승인 대기 계정은 403 이고 원본을 한 번도 읽지 않는다.
  E4  엔드포인트 — 바이너리 kind → viewable=false + reason=binary + rows 미동봉.
  E5  엔드포인트 — 원본 cap 초과 시 truncated.source 표면화.
  E6  엔드포인트 — 원본 read 실패 → 503 + reason=source_unavailable.
  E7  계약 — 버전 선택 파라미터를 두지 않는다(각 버전이 자기 id 를 가지므로 식별 경로가
      둘이 되지 않게). 구버전은 그 버전의 id 로 호출하면 그 버전의 본문이 온다.
  E8  회귀 — 원문 엔드포인트도 diff 와 **같은 텍스트 kind 집합**을 쓴다(한쪽만 넓어지면
      diff 가 거부한 형식을 원문이 뱉는 비대칭이 생긴다).
  E9  인가 — soft-deleted 첨부는 **실제 게이트 함수**로 404 이고 원본을 읽지 않는다
      (다른 테스트는 게이트를 monkeypatch 로 치환하므로, 본문 노출 경로에는 실물 검증이 필요).
  E10 자원 — **ranged read**(cap 만큼만) + 절단 판정을 정본 크기로. 전체 적재는 최대 25× 증폭.
  E11 자원 — per-account rate limit 초과 시 429.
  E12 헤더 — 본문 응답에 `Cache-Control: private, no-store` + `nosniff`(다운로드와 동일 정책).
  E13 결손 — 빈 ObjectKey 는 404(저장소 장애 503 으로 오분류 금지).
  S5  빌더 — `splitlines()` 정규화의 **실제 동작을 고정**한다: CRLF·form feed·U+2028 등은 줄
      경계로 접히므로 재조립이 원본과 byte 동일하지 않을 수 있다(AC-ASV-2 의 정확한 범위).
  S6  빌더 — 입력이 이미 앞부분이면 `stats.lines_partial=True`(앞부분의 줄 수를 전체로 말하지 않게).
"""
from __future__ import annotations

import json

import app
from routers import attachments as att_router

from test_attachment_version_diff import (  # noqa: F401 — fake 재사용(중복 정의 금지)
    _Conn,
    _Request,
    _Storage,
    _install_storage,
    _patch_auth,
    _row,
    _body,
    _src,
)


def _setup(monkeypatch, base, objects, *, allowed=True, fail_keys=(), pending=False):
    conn = _Conn({})
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    _patch_auth(monkeypatch, allowed=allowed, base=base, pending=pending)
    storage = _install_storage(monkeypatch, _Storage(objects, fail_keys=fail_keys))
    return conn, storage


# ── S1~S4: 원문 뷰 빌더 ─────────────────────────────────────────────────────
def test_s1_source_view_expands_lines_with_numbers():
    text = "SELECT 1;\nSELECT 2;\nSELECT 3;"
    view = app._build_source_view(text)
    assert [r["type"] for r in view["rows"]] == ["equal"] * 3
    assert [r["right_no"] for r in view["rows"]] == [1, 2, 3]
    # 원문 무손실 — 행을 이어붙이면 입력과 같다(화면이 "원문" 이라 주장하려면 원문이어야 한다).
    assert "\n".join(r["right"] for r in view["rows"]) == text
    assert view["stats"]["lines"] == 3
    assert view["truncated"]["rows"] is False


def test_s2_source_view_row_cap_truncates_and_flags():
    text = "\n".join(f"line{i}" for i in range(50))
    view = app._build_source_view(text, row_cap=10)
    assert len(view["rows"]) == 10
    assert view["truncated"]["rows"] is True
    # 절단돼도 전체 줄 수는 그대로 보고한다 — 화면이 "N줄 중 앞쪽" 을 말할 수 있어야 한다.
    assert view["stats"]["lines"] == 50


def test_s3_source_view_empty_document_has_no_rows():
    view = app._build_source_view("")
    assert view["rows"] == []
    assert view["stats"]["lines"] == 0


def test_s4_source_rows_are_diff_render_compatible():
    """프론트 `_renderSource` 는 행마다 `right ?? left` / `right_no ?? left_no` 를 읽는다.

    우측 키만 채우면 렌더러 분기 0 으로 재사용되고, 좌측까지 채우면 payload 가 두 배가 된다
    (diff 는 좌우가 다를 수 있어서 두 벌인 것 — 원문은 한 벌이면 족하다).
    """
    view = app._build_source_view("a\nb")
    for r in view["rows"]:
        assert set(r) == {"type", "right_no", "right"}, r


# ── E1~E8: 엔드포인트 ───────────────────────────────────────────────────────
def test_e1_single_version_source(monkeypatch):
    base = _row(vid=10, version=1)
    _, storage = _setup(monkeypatch, base, {"conv-1/u1/f.sql": b"SELECT 1;\nSELECT 2;\n"})
    resp = att_router.get_attachment_source(10, _Request())
    body = _body(resp)
    assert body["viewable"] is True
    assert body["attachment_id"] == 10
    assert body["filename"] == "f.sql"
    assert body["version"]["version_number"] == 1
    assert [r["right"] for r in body["rows"]] == ["SELECT 1;", "SELECT 2;"]
    assert body["stats"]["lines"] == 2
    assert body["truncated"] == {"source": False, "rows": False}
    # 전체 적재가 아니라 **ranged read** 로 cap 만큼만 읽는다.
    assert storage.reads == []
    assert storage.head_reads == [("conv-1/u1/f.sql", int(app._ASSISTANT_EDIT_SIZE_CAP_BYTES))]


def test_e2_forbidden_is_404(monkeypatch):
    base = _row(vid=10, version=1)
    _setup(monkeypatch, base, {}, allowed=False)
    resp = att_router.get_attachment_source(10, _Request())
    assert resp.status_code == 404


def test_e3_pending_account_is_403_and_reads_nothing(monkeypatch):
    """D21 — 원문 보기는 본문 노출이므로 다운로드와 동형으로 막는다.

    이 게이트가 없으면 승인 대기 계정이 다운로드 대신 원문 보기로 bytes 를 얻는다.
    """
    base = _row(vid=10, version=1)
    _, storage = _setup(monkeypatch, base, {"conv-1/u1/f.sql": b"secret"}, pending=True)
    resp = att_router.get_attachment_source(10, _Request())
    assert resp.status_code == 403
    assert storage.reads == []


def test_e4_binary_downgrades_to_meta(monkeypatch):
    base = _row(vid=10, version=1, kind="pdf", sha="deadbeef")
    _, storage = _setup(monkeypatch, base, {})
    resp = att_router.get_attachment_source(10, _Request())
    body = _body(resp)
    assert body["viewable"] is False and body["reason"] == "binary"
    assert "rows" not in body            # 빈 본문을 흉내내지 않는다
    assert body["version"]["sha256"] == "deadbeef"
    assert storage.reads == []           # 바이너리 원본은 읽지 않는다


def test_e5_source_cap_truncation_is_surfaced(monkeypatch):
    cap = int(app._ASSISTANT_EDIT_SIZE_CAP_BYTES)
    # 절단 판정의 정본은 **DB 의 SizeBytes** 다(ranged read 는 항상 cap 만큼 오므로 읽은 길이로는
    # 판정할 수 없다) — 행의 크기를 cap 초과로 둔다.
    base = dict(_row(vid=10, version=1))
    base["SizeBytes"] = cap + 10
    _setup(monkeypatch, base, {"conv-1/u1/f.sql": b"x" * (cap + 10)})
    resp = att_router.get_attachment_source(10, _Request())
    body = _body(resp)
    assert body["truncated"]["source"] is True
    assert body["caps"]["source_bytes"] == cap


def test_e6_object_read_failure_is_503(monkeypatch):
    base = _row(vid=10, version=1)
    _setup(monkeypatch, base, {}, fail_keys=("conv-1/u1/f.sql",))
    resp = att_router.get_attachment_source(10, _Request())
    assert resp.status_code == 503
    body = _body(resp)
    assert body["viewable"] is False and body["reason"] == "source_unavailable"


def test_e7_no_version_query_param__id_identifies_the_version(monkeypatch):
    """버전 선택 파라미터를 두지 않는 계약.

    각 버전이 자기 행·자기 Id 를 가지므로 경로 id 하나로 대상이 특정된다. `?version=` 을 얹으면
    같은 대상을 가리키는 식별 경로가 둘이 되고, 그 중 하나만 스코프 검사를 통과하는 비대칭이
    생길 수 있다. 구버전 id 로 호출하면 그 버전의 본문이 온다 — 그리고 무시돼야 할 쿼리를
    붙여도 대상이 바뀌지 않는다.
    """
    import inspect

    # 단언 대상은 **쿼리 파싱**이지 "version" 이라는 문자열이 아니다 — 응답 payload 에는
    # `version` 메타 블록이 정당하게 있다(초판 단언이 그걸 잡아 자기 자신을 red 로 만들었다).
    src = inspect.getsource(att_router.get_attachment_source)
    assert 'query_params.get("version")' not in src, "본문에 version 쿼리 파싱이 남아 있다"

    v1 = _row(vid=10, version=1, key="conv-1/u1/f.sql")
    _setup(monkeypatch, v1, {"conv-1/u1/f.sql": b"OLD\n", "conv-1/u2/f.sql": b"NEW\n"})
    body = _body(att_router.get_attachment_source(10, _Request(version=2)))
    assert [r["right"] for r in body["rows"]] == ["OLD"], "쿼리가 대상을 바꾸면 안 된다"
    assert body["version"]["version_number"] == 1


def test_e8_source_and_diff_share_text_kind_set():
    """원문·비교가 같은 kind 집합을 본다 — 한쪽만 넓어지면 diff 가 거부한 형식을 원문이 뱉는다."""
    import inspect

    src = inspect.getsource(att_router.get_attachment_source)
    dsrc = inspect.getsource(att_router.get_attachment_version_diff)
    assert "_VERSION_DIFF_TEXT_KINDS" in src and "_VERSION_DIFF_TEXT_KINDS" in dsrc


# ── S5~S6: splitlines 정규화 · 부분 줄 수 ───────────────────────────────────
def test_s5_splitlines_normalization_is_pinned():
    """`splitlines()` 는 CRLF·CR·form feed·U+2028/U+0085 를 모두 줄 경계로 접는다.

    그래서 "행을 이어붙이면 원본과 byte 동일" 은 **LF 개행 문서에 한해** 참이다. 이 테스트는
    현행 동작을 고정하고 AC-ASV-2 의 범위를 명시한다(§18.8 security 지적 — 그 주장이 일반적으로는
    거짓이며, form feed 는 없던 줄바꿈을 만들어 이후 줄번호를 밀어낸다).
    """
    lf = "a\nb\nc"
    assert "\n".join(r["right"] for r in app._build_source_view(lf)["rows"]) == lf

    crlf = app._build_source_view("a\r\nb")
    assert [r["right"] for r in crlf["rows"]] == ["a", "b"]      # \r 은 보존되지 않는다
    ff = app._build_source_view("a\x0cb")
    assert [r["right"] for r in ff["rows"]] == ["a", "b"]        # form feed 가 줄을 만든다
    ls = app._build_source_view("a\u2028b")
    assert [r["right"] for r in ls["rows"]] == ["a", "b"]


def test_s6_partial_input_marks_lines_as_partial():
    view = app._build_source_view("a\nb", source_truncated=True)
    assert view["stats"]["lines_partial"] is True
    assert app._build_source_view("a\nb")["stats"]["lines_partial"] is False


# ── E9~E13: 인가 실물 · 자원 · 헤더 ─────────────────────────────────────────
def test_e9_soft_deleted_attachment_is_404_with_real_gate(monkeypatch):
    """게이트를 **치환하지 않고** soft-delete 거부를 실증한다.

    다른 테스트의 `_patch_auth` 는 `_account_can_access_attachment` 를 통째로 lambda 로 바꾼다 —
    그러면 이 경로에서 `DeletedAt` 검사가 한 번도 실행되지 않는다. 본문 노출 경로에는 실물이 필요하다.
    """
    conn = _Conn({})
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    monkeypatch.setattr(app, "_require_account", lambda request, c: ({"id": 1}, None))
    monkeypatch.setattr(app, "_account_is_pending", lambda account: False)
    deleted = dict(_row(vid=10, version=1))
    deleted["DeletedAt"] = "2026-01-01"
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, aid: deleted)
    monkeypatch.setattr(app, "_account_has_permission", lambda account, perm: True)
    storage = _install_storage(monkeypatch, _Storage({"conv-1/u1/f.sql": b"secret"}))
    resp = att_router.get_attachment_source(10, _Request())
    assert resp.status_code == 404
    assert storage.reads == []


def test_e10_ranged_read_and_truncation_from_authoritative_size(monkeypatch):
    """cap 만큼만 읽고, 절단 판정은 **DB 의 정본 크기**로 한다.

    ranged read 는 항상 정확히 cap 만큼 오므로 `len(raw) > cap` 은 영원히 거짓 —
    그 판정을 그대로 두면 대용량 파일의 절단이 **무음**이 된다.
    """
    cap = int(app._ASSISTANT_EDIT_SIZE_CAP_BYTES)
    base = dict(_row(vid=10, version=1))
    base["SizeBytes"] = cap * 3
    _, storage = _setup(monkeypatch, base, {"conv-1/u1/f.sql": b"x" * cap})
    resp = att_router.get_attachment_source(10, _Request())
    body = _body(resp)
    assert body["truncated"]["source"] is True
    assert body["stats"]["lines_partial"] is True
    assert storage.head_reads == [("conv-1/u1/f.sql", cap)], storage.head_reads
    assert storage.reads == []          # 전체 적재 경로를 타지 않는다


def test_e11_rate_limited_returns_429(monkeypatch):
    base = _row(vid=10, version=1)
    _, storage = _setup(monkeypatch, base, {"conv-1/u1/f.sql": b"a\n"})
    monkeypatch.setattr(app, "_search_rate_limit_check", lambda *a, **k: False)
    monkeypatch.setattr(app, "_rate_limit_retry_after", lambda *a, **k: 5)
    resp = att_router.get_attachment_source(10, _Request())
    assert resp.status_code == 429
    assert storage.head_reads == [] and storage.reads == []


def test_e12_body_response_carries_no_store_headers(monkeypatch):
    """본문을 싣는 응답은 다운로드와 같은 저장 정책을 갖는다(JSON 이라고 사라지면 안 된다)."""
    base = _row(vid=10, version=1)
    _setup(monkeypatch, base, {"conv-1/u1/f.sql": b"a\n"})
    resp = att_router.get_attachment_source(10, _Request())
    assert resp.headers["cache-control"] == "private, no-store"
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_e13_missing_object_key_is_404_not_503(monkeypatch):
    base = dict(_row(vid=10, version=1))
    base["ObjectKey"] = ""
    _, storage = _setup(monkeypatch, base, {})
    resp = att_router.get_attachment_source(10, _Request())
    assert resp.status_code == 404
    assert storage.head_reads == [] and storage.reads == []


# ── C1~C5: 체인 요약(비교 기준 선택기용) — REQ-20260813-attach-source-compare ──
# 사용자 요청(2026-08-13): "첨부파일의 '문서 원문' 화면에서도 버전 간 비교를 수행할 수 있도록."
# 선택기를 채우려면 체인이 필요한데, `/versions` 를 따로 부르면 왕복이 늘고(원문 모달의 요청이
# `/source` 한 번이라는 계약이 깨진다) 버전마다 MinIO presign 이 생긴다. `/source` 가 같은
# 게이트 안에서 체인 **요약**을 함께 싣는다.
def _patch_chain(monkeypatch, chain):
    monkeypatch.setattr(
        app, "_load_attachment_version_chain",
        lambda conn, root, scope_row=None: list(chain),
    )


def test_c1_source_payload_carries_version_chain(monkeypatch):
    chain = [_row(vid=10, version=1), _row(vid=11, version=2), _row(vid=12, version=3)]
    base = _row(vid=12, version=3)
    _setup(monkeypatch, base, {"conv-1/u3/f.sql": b"SELECT 1;\n"})
    _patch_chain(monkeypatch, chain)
    body = _body(att_router.get_attachment_source(12, _Request()))
    assert [v["version_number"] for v in body["versions"]] == [1, 2, 3]
    # 각 항목은 선택기가 라벨을 만들 수 있어야 한다(번호·주체·최신 여부·id).
    v3 = body["versions"][2]
    assert v3["id"] == 12 and v3["created_by_role"] == "user"
    assert set(v3) >= {"id", "version_number", "created_by_role", "created_at",
                       "size", "sha256", "kind", "original_filename", "is_latest"}


def test_c2_chain_summary_excludes_object_key_and_signed_url(monkeypatch):
    """선택기는 **무엇을 고를지**만 알면 된다 — 저장소 경로·서명 URL 은 싣지 않는다.

    `/versions`(다운로드 경로)는 버전마다 presign 을 만들지만 이 payload 는 그 비용도 그 노출도
    갖지 않는다. 노출 범위가 `/versions` 응답의 부분집합이라는 사실을 데이터로 고정한다.
    """
    chain = [_row(vid=10, version=1), _row(vid=11, version=2)]
    _setup(monkeypatch, _row(vid=11, version=2), {"conv-1/u2/f.sql": b"a\n"})
    _patch_chain(monkeypatch, chain)
    body = _body(att_router.get_attachment_source(11, _Request()))
    assert body["versions"]
    for v in body["versions"]:
        assert "signed_url" not in v and "object_key" not in v and "ObjectKey" not in v


def test_c3_chain_load_failure_is_fail_soft(monkeypatch):
    """체인 조회 실패는 **비교 기능만** 없애고 원문은 그대로 준다.

    원문 보기가 이 조회에 종속되면 체인 쿼리 한 번의 실패가 "내용을 볼 수 없음" 으로 번진다.
    프론트는 `versions` 가 2개 미만이면 선택기를 숨기므로 빈 배열이 곧 종전 동작이다.
    """
    def _boom(conn, root, scope_row=None):
        raise RuntimeError("chain query failed")
    _setup(monkeypatch, _row(vid=10, version=1), {"conv-1/u1/f.sql": b"SELECT 1;\n"})
    monkeypatch.setattr(app, "_load_attachment_version_chain", _boom)
    body = _body(att_router.get_attachment_source(10, _Request()))
    assert body["versions"] == []
    assert body["viewable"] is True
    assert [r["right"] for r in body["rows"]] == ["SELECT 1;"]


def test_c4_binary_degraded_payload_also_carries_chain(monkeypatch):
    """바이너리 강등 화면에서도 체인을 싣는다 — 그 화면의 비교는 메타 비교(`comparable=false`)로
    답할 수 있고, 조용히 선택기를 없애면 사용자는 비교 자체가 불가하다고 읽는다."""
    chain = [_row(vid=10, version=1, kind="pdf"), _row(vid=11, version=2, kind="pdf")]
    _setup(monkeypatch, _row(vid=11, version=2, kind="pdf"), {})
    _patch_chain(monkeypatch, chain)
    body = _body(att_router.get_attachment_source(11, _Request()))
    assert body["viewable"] is False and body["reason"] == "binary"
    assert [v["version_number"] for v in body["versions"]] == [1, 2]


def test_c5_version_side_is_single_source_of_format():
    """`/source` 의 `version`·`versions` 와 `/diff` 의 `from`·`to` 는 **같은 함수**로 만든다.

    형식이 두 벌이면 필드 하나가 조용히 빠지는 방식으로 어긋나고(프론트는 두 dict 를 같은
    라벨러·같은 select 에 넣는다), 그 결과 어느 화면에서는 "AI 수정" 이 뜨고 다른 화면에서는
    안 뜨는 비대칭이 된다.
    """
    src = _src("routers/attachments.py")
    assert src.count("def _version_side(") == 1
    assert src.count("_version_side(") >= 4          # 정의 1 + version + versions + from/to
    assert "def _side(" not in src, "nested 사본이 남아 있다"
    row = _row(vid=11, version=2, role="assistant", superseded=True)
    side = att_router._version_side(row)
    assert side["created_by_role"] == "assistant" and side["is_latest"] is False
