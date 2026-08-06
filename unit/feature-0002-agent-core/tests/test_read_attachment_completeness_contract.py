"""FR-read-attachment-preview-looks-partial — 첨부 조회의 완전성 계약 회귀 테스트.

관측(conversation_audit 2026-08-05, 라이브 실측 대화 `…843232a3`): 사용자가 단계 보기 패널에서
`read_attachment` 결과를 열어보고 "파일을 일부만 조회하는 것처럼" 보인다고 보고했다.

진단 결과 **세 축이 겹쳐 있었다**:
  1. **표시(무해하나 오인 유발)**: 단계 결과는 `_build_step_result_summary` 가 **500자로 자른 발췌**를
     저장하고 사이드 패널이 그것을 그대로 렌더한다. 절단 표시가 없어 "모델도 일부만 봤다" 로 읽혔다.
     실측: 그 3건은 전부 전문 수신(1~42/42 · 1~32/32 · 1~28/28, tool 메시지 1,485·692·1,213자).
  2. **문구**: 전문을 줬는데도 헤더가 `1~42번째 줄 / 전체 42줄` 이라 부분 조회처럼 읽힌다.
  3. **실재하는 미열람(드묾)**: 라이브 41회 중 절단 2회는 **모두 모델이 스스로 `max_lines` 지정**.
     그중 1건(327줄 중 250줄)은 **이어 읽지 않고** 판단했다. 기본 600줄 캡 발동 0회.

**§18.8 적대 패널(backend+qa)이 초판에서 잡은 것 — 이 파일의 존재 이유**:
초판은 `read_attachment_content` 를 통째로 stub 해 **실제 슬라이싱 로직을 한 번도 태우지 않았다**.
그 사각에 P1 이 숨어 있었다 — 문자 상한(60,000자)이 걸리면 `truncated=True` 지만 `end_line` 은
**자르기 전** 청크 길이라, 헤더가 `남은 0줄 미열람` 같은 **정량화된 허위**를 냈고 MUST 계약이
"읽을 게 없다" 로 귀결됐다. 더 나쁜 변형은 이어읽기 시작점이 실제 전달분보다 앞서, 중간 구간이
**어떤 호출로도 오지 않는 구멍**이 되는 것이었다.
따라서 이 파일은 **실 함수(`read_attachment_content`)를 태운다** — stub 은 스토리지·스코프만.
"""
from __future__ import annotations

import agent_core
import modules.tools as tools

_ROWS = [
    {"id": 31, "filename": "big.sql", "kind": "text", "object_key": "k/31",
     "status": "uploaded", "meta_json": None},
]


def _patch(monkeypatch, body: bytes):
    """스토리지·스코프만 stub — 줄 슬라이싱·문자 상한은 **실 코드**가 돈다."""
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: list(_ROWS))
    monkeypatch.setattr(agent_core, "_load_attachment_bytes", lambda key: body)
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})


def _lines(n, width=10):
    return ("\n".join("L%0*d" % (width - 1, i) for i in range(1, n + 1))).encode()


# ── 문구: 전문 vs 부분 (실 함수 경유) ───────────────────────────────────────


def test_whole_file_header_says_전문_not_a_line_range(monkeypatch):
    """전문일 때 `1~42번째 줄` 은 부분 조회처럼 읽힌다 — 오인 여지를 문구로 없앤다."""
    _patch(monkeypatch, _lines(42))
    out = tools._tool_read_attachment(None, {"filename": "big.sql"})
    assert "전체 42줄 **전문**" in out
    assert "1~42번째 줄" not in out, "전문인데 범위 표기가 남으면 부분 조회로 읽힌다"
    assert "여기까지만 반환" not in out and "미열람" not in out


def test_partial_read_states_both_unread_sides(monkeypatch):
    """부분일 때는 범위 + **앞뒤 미열람 분량**을 함께 — 앞부분 미열람은 절단 플래그가 없다."""
    _patch(monkeypatch, _lines(100))
    out = tools._tool_read_attachment(None, {"filename": "big.sql", "start_line": 21, "max_lines": 30})
    assert "21~50번째 줄 / 전체 100줄" in out
    assert "앞 20줄" in out and "뒤 50줄" in out


def test_mid_file_chunk_to_eof_is_not_labeled_whole(monkeypatch):
    """start_line>1 이면 끝까지 읽었어도 전문이 아니다(앞부분 미열람)."""
    _patch(monkeypatch, _lines(40))
    out = tools._tool_read_attachment(None, {"filename": "big.sql", "start_line": 33})
    assert "33~40번째 줄 / 전체 40줄" in out
    assert "**전문**" not in out
    assert "앞 32줄" in out


# ── 이어읽기 계약 ───────────────────────────────────────────────────────────


def test_truncated_result_has_must_continue_contract(monkeypatch):
    """실측 미열람 사례(327줄 중 250줄만 읽고 판단)의 봉인 — 방법만이 아니라 **의무**를 준다."""
    _patch(monkeypatch, _lines(327))
    out = tools._tool_read_attachment(None, {"filename": "big.sql", "max_lines": 250})
    assert "1~250번째 줄 / 전체 327줄" in out
    assert "뒤 77줄" in out
    assert "start_line=251" in out
    assert "**MUST**" in out and "반드시 이어 읽" in out
    # 탈출구는 **조건부**여야 한다 — 무조건 허용이면 더 싼 경로가 되어 실측 행동을 그대로 승인한다.
    assert "그 파일 전체에 관한 판단이 아니어서" in out
    # 본문이 머리말을 반박하지 못하게 하는 권위 조항.
    assert "이 머리말만이 권위" in out


def test_whole_file_has_no_continue_contract(monkeypatch):
    """전문일 때 이어읽기 계약을 붙이면 존재하지 않는 잔여분을 찾게 만든다."""
    _patch(monkeypatch, _lines(28))
    out = tools._tool_read_attachment(None, {"filename": "big.sql"})
    assert "MUST" not in out and "미열람" not in out


# ── 문자 상한(60,000자) — §18.8 [P1] 이 숨어 있던 경로 ──────────────────────


def test_char_cap_end_line_reflects_delivered_lines_only(monkeypatch):
    """문자 상한이 줄 중간을 자르면 `end_line` 은 **온전히 전달된** 마지막 줄이어야 한다.

    종전: 자르기 전 청크 길이를 돌려줘 "1~600줄 전달" 로 보였고, 실제 전달은 400줄이라
    이어읽기를 601 부터 시작하면 401~600 이 **어떤 호출로도 오지 않는 구멍**이 됐다.
    """
    body = ("\n".join("Z" * 150 for _ in range(1000))).encode()  # 1,000줄 × 150자
    _patch(monkeypatch, body)
    res = agent_core.read_attachment_content(filename="big.sql")  # 기본 600줄
    assert res["truncated"] is True and res["char_capped"] is True
    delivered = res["text"].count("\n") + 1 if res["text"] else 0
    assert res["delivered_lines"] == delivered, "전달분과 보고분 불일치"
    assert res["end_line"] == res["delivered_lines"], "start=1 이므로 end_line == 전달 줄 수"
    assert res["end_line"] < 600, "문자 상한이 걸렸는데 슬라이스 길이를 그대로 보고하면 안 된다"
    # 이어읽기 시작점이 전달분 바로 다음이어야 구멍이 생기지 않는다.
    out = tools._tool_read_attachment(None, {"filename": "big.sql"})
    assert f"start_line={res['end_line'] + 1}" in out
    assert "줄 중간에서 잘렸고" in out


def test_char_cap_never_reports_zero_remaining_while_truncated(monkeypatch):
    """`남은 0줄` + `반드시 이어 읽으십시오` 는 자기모순 — 종전 초안이 내던 정량화된 허위."""
    body = ("\n".join("Z" * 700 for _ in range(100))).encode()  # 100줄 × 700자 → 슬라이스는 전체
    _patch(monkeypatch, body)
    res = agent_core.read_attachment_content(filename="big.sql")
    assert res["truncated"] is True and res["char_capped"] is True
    assert res["end_line"] < res["total_lines"], "전달분이 전체보다 적어야 한다"
    out = tools._tool_read_attachment(None, {"filename": "big.sql"})
    assert "뒤 0줄" not in out and "미열람: " in out
    assert "**전문**" not in out, "문자 상한이 걸렸는데 전문이라 하면 최악의 오도"


def test_char_cap_dropping_every_line_reports_no_delivery(monkeypatch):
    """첫 줄 하나가 상한을 넘으면 온전한 줄이 0 — 빈 본문을 '내용 없음' 으로 오독하면 부재 단정."""
    body = ("Z" * 70000).encode()
    _patch(monkeypatch, body)
    out = tools._tool_read_attachment(None, {"filename": "big.sql"})
    assert "전달된 줄 없음" in out
    assert "파일에 내용이 없다는 뜻이 **아닙니다**" in out


# ── start_line 이 파일 끝을 넘은 경우 ───────────────────────────────────────


def test_start_line_beyond_eof_is_explicit(monkeypatch):
    """`100~99번째 줄` 같은 역전 범위 + 빈 본문은 '그 자리에 내용 없음' 으로 오독된다."""
    _patch(monkeypatch, _lines(3))
    out = tools._tool_read_attachment(None, {"filename": "big.sql", "start_line": 100})
    assert "전달된 줄 없음" in out
    assert "파일 끝(전체 3줄)을 넘었습니다" in out
    assert "유효 범위는 1~3줄" in out
    assert "100~99번째 줄" not in out, "역전 범위를 그대로 노출하면 안 된다"


# ── 인자 전달(§18.8 qa [P2]: 초판 stub 이 인자를 버려 이 seam 이 무방비였다) ──


def test_args_are_forwarded_to_reader(monkeypatch):
    captured: dict = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "filename": "f", "attachment_id": 1, "kind": "text", "text": "x",
                "start_line": 5, "end_line": 9, "delivered_lines": 5, "total_lines": 20,
                "truncated": True, "char_capped": False, "start_beyond_eof": False}

    monkeypatch.setattr(agent_core, "read_attachment_content", _fake)
    tools._tool_read_attachment(None, {"filename": "f.sql", "start_line": 5, "max_lines": 5})
    assert captured["filename"] == "f.sql"
    assert captured["start_line"] == 5
    assert captured["max_lines"] == 5


# ── 도구 정의 ───────────────────────────────────────────────────────────────


def test_tool_def_is_read_attachment_and_discourages_small_max_lines():
    """정의 순서가 바뀌어도 엉뚱한 항목을 검사하지 않도록 이름부터 고정한다."""
    defs = [d for d in tools._ATTACHMENT_TOOL_DEFS if d["function"]["name"] == "read_attachment"]
    assert len(defs) == 1
    desc = defs[0]["function"]["description"]
    assert "max_lines 를 임의로 작게 지정하지 말 것" in desc
    assert "반드시 이어 읽는다" in desc


def test_tool_def_reaches_model_only_with_attachments():
    """`with_attachment_tools` 게이트 — 첨부가 없으면 도구가 붙지 않는다(기존 계약)."""
    base = [{"type": "function", "function": {"name": "execute_sql"}}]
    assert all(d["function"]["name"] != "read_attachment"
               for d in tools.with_attachment_tools(base, False))
    assert any(d["function"]["name"] == "read_attachment"
               for d in tools.with_attachment_tools(base, True))


# ── 표시용 발췌 플래그 ──────────────────────────────────────────────────────


def test_step_summary_flags_truncated_preview():
    """단계 보기 패널이 '발췌' 를 명시할 수 있어야 한다 — 무음 절단이 오인의 직접 원인이었다."""
    s = agent_core._build_step_result_summary("read_attachment", "X" * 1500)
    assert len(s["preview"]) == agent_core._STEP_PREVIEW_CAP_CHARS
    assert s["preview_truncated"] is True
    assert s["result_chars"] == 1500
    assert "result_capped_for_model" not in s


def test_step_summary_no_flag_when_not_truncated():
    s = agent_core._build_step_result_summary("read_attachment", "짧은 결과")
    assert s["preview"] == "짧은 결과"
    assert "preview_truncated" not in s and "result_chars" not in s


def test_step_summary_marks_model_side_cap():
    """`_cap_tool_result` 가 먼저 자른 결과에 '전문 전달' 이라 표시하면 거짓이 된다(§18.8 [P1-2])."""
    capped = "Y" * 2000 + "\n... (truncated)"
    s = agent_core._build_step_result_summary("describe_routine", capped)
    assert s["result_capped_for_model"] is True


def test_flags_survive_normalize(monkeypatch):
    """저장→API seam — 이 경로에 allowlist 가 하나 끼면 주석이 조용히 사라진다."""
    from modules.render import normalize_step_result_summary
    src = {"preview": "p", "preview_truncated": True, "result_chars": 900,
           "result_capped_for_model": True}
    for tool in ("read_attachment", "execute_sql"):
        out = normalize_step_result_summary(tool, dict(src))
        assert out["preview_truncated"] is True, tool
        assert out["result_chars"] == 900, tool
        assert out["result_capped_for_model"] is True, tool


def test_step_preview_cap_unchanged():
    """표시 상한은 이번 범위에서 올리지 않는다.

    사유는 "공유 저장 경로" 가 아니라(도구별 분기는 tool_name 이 있어 기술적으로 가능 —
    §18.8 backend [P2] 정정) **steps 가 run 진행 중 폴링으로 반복 전송**되기 때문이다.
    """
    assert agent_core._STEP_PREVIEW_CAP_CHARS == 500
