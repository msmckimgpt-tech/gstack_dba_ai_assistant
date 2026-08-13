"""REQ-20260813-attach-name-sort: 첨부 목록을 파일명 순으로 정렬 — 회귀 테스트.

사용자 요청: "프로젝트 내 서비스에서, 첨부파일이 명칭 순으로 정렬되도록 구성해주세요."
종전 동작은 업로드 순(`ORDER BY Id ASC`)이라 같은 작업의 `01_`~`09_` 파일이 올린 차례대로
흩어져 보였다.

검증(`make test` agent 이미지, DB 없이 fake conn):
  N1  _natural_filename_key — 숫자 구간은 수치 비교(`_02_` < `_09_` < `_10_`; 사전순이면 10 < 2).
  N2  _natural_filename_key — 대소문자 무시(casefold), 그래도 순서는 결정적.
  N3  _natural_filename_key — 한글 파일명은 가나다순(완성형 코드포인트 = 사전순).
  N4  _natural_filename_key — None/빈 이름도 예외 없이 정렬(맨 앞).
  S1  _sort_attachment_rows_by_name — 이름순 + 동명 tie-break(VersionNumber → Id).
  S2  _sort_attachment_rows_by_name — PG mirror 판 행(같은 PascalCase 키)도 같은 함수로 정렬.
  B1  _sort_attachment_rows_for_bulk — 그룹 사이는 이름순, 버전 체인은 인접 유지(VersionNumber ASC).
  B2  _sort_attachment_rows_for_bulk — 체인 대표 이름은 **최신 버전 이름**(AI 편집으로 개명된 경우).
  A1  list_conversation_attachments — 응답 순서가 파일명 순(업로드 역순 rows 투입).
  A2  _list_deleted_conversation_attachments — 응답은 이름순이되, 절단 기준 SQL
      (`DeletedAt DESC` + `LIMIT 200`)은 그대로 유지(최근 삭제분이 휴지통에서 밀려나지 않게).
  A3  bulk_download_conversation_attachments — 정렬 헬퍼를 실제로 경유(무정렬 회귀 차단).
  P1  attachment_pg_mirror — PG select 가 `OriginalFilename` alias 를 유지(헬퍼 키 계약).
"""
from __future__ import annotations

import inspect
import json

import app
from routers import conversations


# ── fake DB ─────────────────────────────────────────────────────────────────
class _DictCursor:
    def __init__(self, rows, sink):
        self._rows = rows
        self._sink = sink

    def execute(self, sql, params=None):
        self._sink.append(" ".join(str(sql).split()))

    def fetchall(self):
        return [dict(r) for r in self._rows]

    def close(self):
        pass


class _TupleCursor:
    """version_count 집계용(`conn.cursor()`). 집계는 fail-soft 라 빈 결과로 충분."""

    def __init__(self, sink):
        self._sink = sink

    def execute(self, sql, params=None):
        self._sink.append(" ".join(str(sql).split()))

    def fetchall(self):
        return []

    def close(self):
        pass


class _Conn:
    def __init__(self, rows):
        self._rows = rows
        self.sql_log: list[str] = []

    def cursor(self, dictionary=False):
        return _DictCursor(self._rows, self.sql_log) if dictionary else _TupleCursor(self.sql_log)


def _row(att_id, filename, *, version=1, root=None, deleted_at=None):
    return {
        "Id": att_id,
        "ConversationId": "conv-1",
        "AccountId": 7,
        "ObjectKey": f"k/{att_id}",
        "OriginalFilename": filename,
        "FilenameHmac": None,
        "MimeType": "text/plain",
        "SizeBytes": 100,
        "SizeBucket": "small",
        "Sha256": "0" * 64,
        "Kind": "txt",
        "UploadStatus": "ingested",
        "AttachmentDerivedMessages": None,
        "CreatedAt": None,
        "DeletedAt": deleted_at,
        "DeletePending": 1 if deleted_at else 0,
        "DeleteReason": "user" if deleted_at else None,
        "MetaJson": None,
        "RootAttachmentId": root,
        "VersionNumber": version,
        "CreatedByRole": "user",
        "SupersededAt": None,
    }


def _names(payload_body) -> list[str]:
    data = json.loads(payload_body)
    return [a["original_filename"] for a in data["attachments"]]


# ── N: 정렬 키 ──────────────────────────────────────────────────────────────
def test_n1_numeric_segments_compare_as_numbers():
    key = conversations._natural_filename_key
    names = ["job_10_end.sql", "job_2_mid.sql", "job_09_x.sql", "job_1_start.sql"]
    assert sorted(names, key=key) == [
        "job_1_start.sql", "job_2_mid.sql", "job_09_x.sql", "job_10_end.sql",
    ]
    # 사전순이었다면 "job_10_..." 이 "job_2_..." 앞에 온다 — 그 회귀를 명시적으로 잠근다.
    assert sorted(names) != sorted(names, key=key)


def test_n2_case_insensitive_but_deterministic():
    key = conversations._natural_filename_key
    assert key("Alpha.sql") == key("alpha.sql")          # 대소문자만 다르면 같은 키
    assert sorted(["b.sql", "A.sql"], key=key) == ["A.sql", "b.sql"]


def test_n3_korean_names_sort_in_hangul_order():
    key = conversations._natural_filename_key
    names = ["다.txt", "가.txt", "나.txt"]
    assert sorted(names, key=key) == ["가.txt", "나.txt", "다.txt"]


def test_n4_empty_name_is_graceful():
    key = conversations._natural_filename_key
    assert key(None) == ()
    assert sorted(["b.txt", None, ""], key=key) == [None, "", "b.txt"]


def test_n5_absurdly_long_digit_run_does_not_raise():
    # 파이썬은 4,300 자리 초과 int↔str 변환을 거부한다 — legacy/malformed 행 하나가 목록
    # 전체를 500 으로 떨어뜨리면 안 된다(codex 적대 리뷰 P3).
    key = conversations._natural_filename_key
    monster = "a" + "9" * 5000 + ".txt"
    assert key(monster)                       # 예외 없이 키가 나온다
    # 변환 불가분은 "아주 큰 수" 로 취급 — 0 으로 강등하면 `a1.txt` 보다 앞서는 거짓 순서가 된다.
    assert sorted([monster, "a1.txt"], key=key) == ["a1.txt", monster]


# ── S: 목록 정렬 ────────────────────────────────────────────────────────────
def test_s1_sort_rows_by_name_with_version_id_tiebreak():
    rows = [
        _row(5, "b.sql"),
        _row(3, "a.sql", version=2),
        _row(9, "a.sql", version=1),
        _row(1, "C.sql"),
    ]
    out = conversations._sort_attachment_rows_by_name(rows)
    assert [r["OriginalFilename"] for r in out] == ["a.sql", "a.sql", "b.sql", "C.sql"]
    # 동명은 버전 → id 순 — 같은 입력이면 항상 같은 순서(비결정 순서 금지).
    assert [r["Id"] for r in out[:2]] == [9, 3]


def test_s2_pg_shaped_rows_use_the_same_helper():
    # PG mirror 는 `original_filename AS "OriginalFilename"` 으로 alias 하므로 키가 동형이다.
    rows = [{"Id": 2, "OriginalFilename": "z.sql", "VersionNumber": 1},
            {"Id": 1, "OriginalFilename": "a.sql", "VersionNumber": 1}]
    out = conversations._sort_attachment_rows_by_name(rows)
    assert [r["OriginalFilename"] for r in out] == ["a.sql", "z.sql"]


def test_s3_snake_case_keys_still_sort():
    # 어느 read 경로가 snake_case 로 바뀌어도 정렬이 조용히 무의미해지지 않는다(P2 방어).
    rows = [{"id": 2, "original_filename": "z.sql"}, {"id": 1, "original_filename": "a.sql"}]
    out = conversations._sort_attachment_rows_by_name(rows)
    assert [r["original_filename"] for r in out] == ["a.sql", "z.sql"]


# ── B: 일괄 다운로드 정렬 ───────────────────────────────────────────────────
def test_b1_bulk_keeps_version_chain_contiguous():
    rows = [
        _row(1, "z.sql", version=1),
        _row(2, "z.sql", version=2, root=1),
        _row(3, "a.sql", version=1),
    ]
    out = conversations._sort_attachment_rows_for_bulk(rows)
    assert [r["Id"] for r in out] == [3, 1, 2]          # a.sql → z.sql 체인(v1, v2)
    assert [r["VersionNumber"] for r in out[1:]] == [1, 2]


def test_b2_bulk_group_ordered_by_latest_chain_name():
    # AI 편집이 v2 에서 이름을 바꾼 체인. 그룹 자리는 **목록 패널에 보이는 최신 이름** 기준.
    rows = [
        _row(1, "zz_old.sql", version=1),
        _row(2, "aa_new.sql", version=2, root=1),
        _row(3, "mm.sql", version=1),
    ]
    out = conversations._sort_attachment_rows_for_bulk(rows)
    assert [r["Id"] for r in out] == [1, 2, 3]          # 체인(대표=aa_new) → mm.sql
    assert [r["OriginalFilename"] for r in out] == ["zz_old.sql", "aa_new.sql", "mm.sql"]


# ── A: API 응답 ─────────────────────────────────────────────────────────────
def test_a1_active_list_response_is_name_sorted(monkeypatch):
    rows = [_row(1, "20260709_08_fix_log_tables.sql"),
            _row(2, "20260709_01_rename_table.sql"),
            _row(3, "20260709_10_extra.sql"),
            _row(4, "20260709_02_refill_trigger.sql")]
    conn = _Conn(rows)
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(app, "_manage_gate_for_conversation", lambda *a, **k: (lambda r: True))

    resp = conversations.list_conversation_attachments(
        "conv-1", request=None, state="active", account={"id": 7}, conn=conn)
    assert _names(resp.body) == [
        "20260709_01_rename_table.sql",
        "20260709_02_refill_trigger.sql",
        "20260709_08_fix_log_tables.sql",
        "20260709_10_extra.sql",
    ]


def test_a2_trash_list_sorted_but_truncation_stays_recency(monkeypatch):
    rows = [_row(1, "b.sql", deleted_at="2026-08-13T00:00:00"),
            _row(2, "a.sql", deleted_at="2026-08-12T00:00:00")]
    conn = _Conn(rows)
    monkeypatch.setattr(app, "_manage_gate_for_conversation", lambda *a, **k: (lambda r: True))

    resp = conversations._list_deleted_conversation_attachments(conn, "conv-1", {"id": 7})
    assert _names(resp.body) == ["a.sql", "b.sql"]
    # 무엇을 가져올지는 여전히 최근 삭제 순 — 이름순 LIMIT 이면 방금 지운 파일이 밀려난다.
    sql = " ".join(conn.sql_log).lower()
    assert "order by deletedat desc" in sql and "limit 200" in sql


def test_a3_bulk_download_calls_the_sort_helper():
    src = inspect.getsource(conversations.bulk_download_conversation_attachments)
    assert "_sort_attachment_rows_for_bulk(rows)" in src


# ── P: PG 경로 키 계약 ──────────────────────────────────────────────────────
def test_p1_pg_mirror_aliases_original_filename():
    # 테스트 env 엔 배포 레이아웃의 `web` 패키지가 없다 — 파일 경로로 직접 로드한다
    # (test_attachment_pg_cutover 와 같은 방식).
    import importlib.util
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src" / "modules" / "attachment_pg_mirror.py"
    spec = importlib.util.spec_from_file_location("_name_sort_apm", src)
    apm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(apm)

    assert 'original_filename AS "OriginalFilename"' in apm._PG_ATTACH_SELECT
    # 정렬은 두 read 경로가 합류한 뒤 파이썬에서 한 번만 — PG SQL 에 이름 ORDER BY 가 새로
    # 생기면 collation 차이가 경로별 순서 차이로 돌아온다.
    assert "ORDER BY original_filename" not in inspect.getsource(apm.pg_list_conversation_attachments)
