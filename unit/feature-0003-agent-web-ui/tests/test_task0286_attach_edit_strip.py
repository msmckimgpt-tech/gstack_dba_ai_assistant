"""TASK-0286: assistant 가 첨부 수정본을 전달할 때 전체 본문 노출 제거 + 변경점만(diff) +
파일 명시 전달 회귀 테스트.

사용자 요청: assistant 가 파일(첨부)을 전달하지 않고 첨부 본문 전체를 채팅에 텍스트로 출력하던
동작을, ① 변경점만(diff) 채팅에 + ② 전체 수정본은 다운로드 가능한 첨부 새 버전으로 전달하도록.

검증(`make test` agent 이미지, DB 없이):
  S1  _strip_attachment_edit_blocks — 블록 제거 + materialize 성공분 "📎 수정본 전달" 치환, diff 유지.
  S2  _strip_attachment_edit_blocks — materialize 없으면 블록만 제거(placeholder 없음).
  S3  _strip_attachment_edit_blocks — attachment-edit 블록 없으면 원문 그대로.
  S4  _strip_attachment_edit_blocks — 블록만 있고 materialize 실패 시 빈 답변 방지(원문 유지).
  S5  _strip_attachment_edit_blocks — 다중 블록 전부 제거 + 첨부별 placeholder.
  P1  agent_core SYSTEM_PROMPT — attachment-edit 파일화 안내(DELIVERING THE EDITED FILE) 존재.
  P2  agent_core SYSTEM_PROMPT — 전체 본문 코드블록 금지 + diff 변경점 지침 공존.
  A1  ask 흐름 — _strip_attachment_edit_blocks + _update_assistant_message_content 호출 존재.
"""
from __future__ import annotations

import app


_BODY = "SELECT id, amount FROM `db`.`orders` WHERE created_at >= '2026-01-01'"


def _block(src_id: int, body: str = _BODY, filename: str | None = None) -> str:
    hdr = {"source_attachment_id": src_id}
    if filename:
        hdr["filename"] = filename
    import json
    return f"```attachment-edit\n{json.dumps(hdr)}\n{body}\n```"


# ── S: _strip_attachment_edit_blocks ────────────────────────────────────────
def test_s1_strip_block_with_placeholder_keeps_diff():
    answer = (
        "쿼리를 다음과 같이 수정했습니다.\n\n"
        "```diff\n- SELECT *\n+ SELECT id, amount\n```\n\n"
        + _block(1, filename="orders_v2.sql")
    )
    materialized = [{"original_filename": "orders.sql", "version_number": 2}]
    out = app._strip_attachment_edit_blocks(answer, materialized)
    assert "attachment-edit" not in out          # 블록 태그 제거
    assert _BODY not in out                       # 전체 본문 미노출
    assert "```diff" in out                       # 변경점 diff 유지
    assert "📎 수정본" in out                      # 명시 전달 문구
    assert "orders.sql" in out and "v2" in out


def test_s2_strip_block_no_materialize_no_placeholder():
    answer = "여기 있습니다.\n\n" + _block(1)
    out = app._strip_attachment_edit_blocks(answer, [])
    assert _BODY not in out
    assert "attachment-edit" not in out
    assert "📎" not in out                         # materialize 없으면 placeholder 없음
    assert "여기 있습니다." in out


def test_s3_strip_no_block_unchanged():
    answer = "그냥 설명입니다.\n\n```diff\n- a\n+ b\n```"
    out = app._strip_attachment_edit_blocks(answer, [])
    assert out == answer                          # 블록 없으면 원본 그대로


def test_s4_strip_block_only_failed_does_not_resurrect_body():
    """블록만 있고 materialize 실패 → **원문을 되살리지 않는다**(계약 변경 2026-08-28).

    종전 계약은 "빈 답변 방지 = 원문 유지" 였고 의도는 옳았다. 그러나 수단이 파일 전문을
    채팅에 그대로 남겼다(codex 적대 리뷰 P1). 실패·취소 run 은 안내 문구조차 붙지 않아
    그 상태가 굳는다 — 사용자는 답변 대신 파일 덩어리를 본다.

    빈 답변도, 원문 유출도 아닌 **사실 한 줄**이 옳은 답이다.
    """
    answer = _block(1)
    out = app._strip_attachment_edit_blocks(answer, [])
    assert out, "빈 답변이 되면 말풍선이 통째로 비어 '답이 없다' 로 읽힌다"
    assert out != answer, "원문이 그대로 돌아왔다 — 파일 전문이 채팅에 남는다"
    assert "attachment-edit" not in out
    assert "전달되지 않았습니다" in out, "무슨 일이 있었는지 말하지 않는다"


def test_s5_strip_multiple_blocks_all_removed():
    answer = _block(1, body="AAA_BODY_ONE", filename="a.sql") + "\n\n" + _block(2, body="BBB_BODY_TWO", filename="b.csv")
    materialized = [
        {"original_filename": "a.sql", "version_number": 2},
        {"original_filename": "b.csv", "version_number": 3},
    ]
    out = app._strip_attachment_edit_blocks(answer, materialized)
    assert "AAA_BODY_ONE" not in out and "BBB_BODY_TWO" not in out
    assert "attachment-edit" not in out
    assert out.count("📎 수정본") == 2             # 첨부별 안내
    assert "a.sql" in out and "b.csv" in out


def test_s6_strip_block_with_embedded_fence_no_leak():
    # ★ 보안리뷰 MAJOR: 파일 본문에 ``` 코드펜스가 있어도 블록 전체가 제거되고 잔여 본문이
    # 평문으로 노출되지 않는다(라인 기반 파서 — lazy 정규식 조기 종료 회귀 방지).
    body = "# Report\n\n```sql\nSELECT secret FROM t\n```\n\nSECRET_TAIL_OF_FILE"
    answer = (
        "수정했습니다.\n\n```diff\n- a\n+ b\n```\n\n"
        '```attachment-edit\n{"source_attachment_id": 1}\n' + body + "\n```"
    )
    out = app._strip_attachment_edit_blocks(answer, [{"original_filename": "r.md", "version_number": 2}])
    assert "SECRET_TAIL_OF_FILE" not in out      # 본문 끝 잔여 누출 없음
    assert "SELECT secret" not in out
    assert "attachment-edit" not in out
    assert "```diff" in out                       # diff 보존
    assert "📎 수정본" in out


def test_s7_parse_block_with_embedded_fence_full_body():
    # parse 도 본문 내 ``` 를 포함한 전체 본문을 절단 없이 캡처(첨부 저장이 깨지지 않음).
    body = "line1\n```\nstill body\n```\nlast"
    answer = '```attachment-edit\n{"source_attachment_id": 7}\n' + body + "\n```"
    blocks = app._parse_attachment_edit_blocks(answer)
    assert len(blocks) == 1
    assert blocks[0]["source_attachment_id"] == 7
    assert blocks[0]["content"] == body           # 내부 ``` 포함 전체 본문


# ── P: 시스템 프롬프트 ───────────────────────────────────────────────────────
def test_p1_system_prompt_has_attachment_edit_guidance():
    import agent_core
    src = agent_core.SYSTEM_PROMPT
    assert "attachment-edit" in src
    assert "DELIVERING THE EDITED FILE" in src
    assert "source_attachment_id" in src


def test_p2_system_prompt_forbids_full_body_keeps_diff():
    import agent_core
    src = agent_core.SYSTEM_PROMPT
    # 전체 본문 코드블록 금지 지침 + diff 변경점 지침 공존.
    assert "never paste the whole file body" in src.lower() or "do not paste" in src.lower() or "NEVER PASTE" in src
    assert "SHOWING CHANGES" in src               # diff 변경점 섹션 유지


# ── A: ask 흐름 호출 ─────────────────────────────────────────────────────────
def test_a1_ask_invokes_strip_and_content_update():
    import inspect
    # ITEM-10 p15: strip/update 는 routers/conversations.py 로 이동 — ask 흐름 호출 계약은 위치 무관.
    import routers.conversations as _rc
    src = inspect.getsource(app) + inspect.getsource(_rc)
    assert "_strip_attachment_edit_blocks(" in src
    assert "_update_assistant_message_content(" in src
