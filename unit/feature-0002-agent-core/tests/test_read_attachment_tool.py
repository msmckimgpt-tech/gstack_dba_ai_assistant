"""feature-0003 attach-full-scope — read_attachment 도구 회귀 테스트.

인라인 상한(_TEXT_INLINE_COUNT_CAP=20) 밖이거나 이전 턴에 첨부된 파일은 본문이 프롬프트에
실리지 않는다. 종전에는 그 경우 "사용자에게 재첨부를 요청" 하는 것이 유일한 회복 경로였고,
그래서 사용자에겐 "assistant 가 기존 첨부에 접근하지 못한다" 로 보였다. read_attachment 가
그 자리를 대신해 모델이 자율 판단으로 직접 읽는다.

권한 경계는 ATTACHMENT_IDS(= web ask 가 대화·그룹 스코프로 해소한 집합)이며, 그 밖의 파일은
이름을 알아도 읽히지 않아야 한다 — 본 테스트가 그 불변식을 고정한다.
"""
from __future__ import annotations

import agent_core
import modules.tools as tools


_ROWS = [
    {"id": 31, "filename": "report.sql", "kind": "text", "object_key": "k/31", "status": "uploaded", "meta_json": None},
    {"id": 22, "filename": "sales.csv", "kind": "csv", "object_key": "k/22", "status": "ingested", "meta_json": None},
    {"id": 11, "filename": "chart.png", "kind": "image", "object_key": "k/11", "status": "uploaded", "meta_json": None},
]


def _patch_scope(monkeypatch, rows=None, body: bytes = b"line1\nline2\nline3", inline=None):
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: list(rows if rows is not None else _ROWS))
    monkeypatch.setattr(agent_core, "_load_attachment_bytes", lambda key: body)
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: dict(inline or {}))


# ── 스코프(권한 경계) ────────────────────────────────────────────────────────

def test_scope_ids_parses_context_value(monkeypatch):
    monkeypatch.setenv("ATTACHMENT_IDS", "31, 22 ,-5,abc,22")
    assert agent_core._attachment_scope_ids() == [31, 22], "양수만·중복 제거"
    monkeypatch.setenv("ATTACHMENT_IDS", "")
    assert agent_core._attachment_scope_ids() == []


def test_read_rejects_id_outside_scope(monkeypatch):
    """스코프 밖 attachment_id 는 거부 — 타 대화/타 멤버 첨부 읽기 차단."""
    _patch_scope(monkeypatch)
    res = agent_core.read_attachment_content(attachment_id=999)
    assert res["ok"] is False
    assert "참조할 수 있는 첨부가 아닙니다" in res["error"]


def test_read_rejects_unknown_filename_and_lists_options(monkeypatch):
    _patch_scope(monkeypatch)
    res = agent_core.read_attachment_content(filename="secret-from-another-conv.sql")
    assert res["ok"] is False
    assert "report.sql" in res["error"], "모델이 다시 시도할 수 있게 사용 가능 파일을 알려야 함"


def test_read_requires_a_selector(monkeypatch):
    _patch_scope(monkeypatch)
    assert agent_core.read_attachment_content()["ok"] is False


def test_read_with_no_attachments_is_graceful(monkeypatch):
    _patch_scope(monkeypatch, rows=[])
    res = agent_core.read_attachment_content(filename="x.sql")
    assert res["ok"] is False and "첨부가 없습니다" in res["error"]


# ── 본문 조회 ────────────────────────────────────────────────────────────────

def test_read_by_filename_returns_content(monkeypatch):
    _patch_scope(monkeypatch, body=b"SELECT 1;\nSELECT 2;")
    res = agent_core.read_attachment_content(filename="report.sql")
    assert res["ok"] is True
    assert res["attachment_id"] == 31 and res["kind"] == "text"
    assert "SELECT 1;" in res["text"] and res["total_lines"] == 2


def test_read_matches_filename_case_insensitively_and_partially(monkeypatch):
    _patch_scope(monkeypatch)
    assert agent_core.read_attachment_content(filename="REPORT.SQL")["attachment_id"] == 31
    assert agent_core.read_attachment_content(filename="report")["attachment_id"] == 31


def test_read_slices_by_line_range(monkeypatch):
    _patch_scope(monkeypatch, body="\n".join(f"L{i}" for i in range(1, 11)).encode())
    res = agent_core.read_attachment_content(filename="report.sql", start_line=4, max_lines=3)
    assert res["text"].splitlines() == ["L4", "L5", "L6"]
    assert res["start_line"] == 4 and res["end_line"] == 6 and res["total_lines"] == 10
    assert res["truncated"] is True, "뒤에 남은 줄이 있으면 이어읽기 신호를 줘야 함"

    tail = agent_core.read_attachment_content(filename="report.sql", start_line=9, max_lines=50)
    assert tail["truncated"] is False and tail["end_line"] == 10


def test_read_prefers_inline_body_without_refetch(monkeypatch):
    """이번 턴에 이미 인라인된 파일은 저장소 재다운로드 없이 그 본문을 쓴다."""
    calls: list[str] = []

    def _boom(key):
        calls.append(key)
        return None

    _patch_scope(monkeypatch, inline={31: {"filename": "report.sql", "content": "INLINED", "truncated": False}})
    monkeypatch.setattr(agent_core, "_load_attachment_bytes", _boom)
    res = agent_core.read_attachment_content(filename="report.sql")
    assert res["ok"] is True and res["text"] == "INLINED"
    assert calls == [], "인라인 본문이 있으면 MinIO 를 다시 치지 않아야 함"


def test_read_rejects_image_kind(monkeypatch):
    _patch_scope(monkeypatch)
    res = agent_core.read_attachment_content(filename="chart.png")
    assert res["ok"] is False and "이미지" in res["error"]


def test_read_reports_storage_failure_without_asserting_cause(monkeypatch):
    """저장소 실패는 원인을 단정하지 않는다 (인프라 장애 환각 방지 — attach-inline-honesty 축)."""
    _patch_scope(monkeypatch, body=None)
    res = agent_core.read_attachment_content(filename="report.sql")
    assert res["ok"] is False
    assert "원인을 단정하지" in res["error"]


def test_read_binary_file_is_explained_not_garbled(monkeypatch):
    _patch_scope(monkeypatch, rows=[
        {"id": 7, "filename": "book.pdf", "kind": "pdf", "object_key": "k/7", "status": "uploaded", "meta_json": None},
    ], body=b"\x89PDF\xff\xfe\x00binary")
    res = agent_core.read_attachment_content(filename="book.pdf")
    assert res["ok"] is False and "이진 파일" in res["error"]


# ── 도구 노출·핸들러 ─────────────────────────────────────────────────────────

def test_tool_exposed_only_when_conversation_has_attachments():
    base = [{"type": "function", "function": {"name": "execute_sql"}}]
    assert tools.with_attachment_tools(base, False) == base, "첨부 없는 대화엔 도구를 띄우지 않음"
    with_tool = tools.with_attachment_tools(base, True)
    names = [d["function"]["name"] for d in with_tool]
    assert "read_attachment" in names and "execute_sql" in names


def test_tool_is_datasource_free():
    """데이터소스 회로차단·연결실패가 첨부 읽기를 막지 않도록 라우팅을 우회한다."""
    assert "read_attachment" in tools._DATASOURCE_FREE_TOOLS
    assert tools._TOOL_HANDLERS.get("read_attachment") is not None


def test_tool_handler_formats_range_and_marks_untrusted(monkeypatch):
    _patch_scope(monkeypatch, body="\n".join(f"L{i}" for i in range(1, 9)).encode())
    out = tools.execute_tool(None, "read_attachment", {"filename": "report.sql", "max_lines": 3})
    assert 'report.sql' in out and "1~3번째 줄" in out and "전체 8줄" in out
    assert "start_line=4" in out, "이어읽기 안내 누락"
    assert "L1" in out


def test_tool_handler_returns_error_text_on_reject(monkeypatch):
    _patch_scope(monkeypatch)
    out = tools.execute_tool(None, "read_attachment", {"attachment_id": 4242})
    assert out.startswith("오류:")


def test_step_labels_describe_attachment_read():
    work = agent_core._derive_step_work("read_attachment", {"filename": "report.sql"})
    assert "report.sql" in work and "읽는다" in work
    assert "첨부" in agent_core._derive_step_reason("read_attachment", {})
