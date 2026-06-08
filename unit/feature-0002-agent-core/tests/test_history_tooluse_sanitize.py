"""TASK-0160 회귀 — `_normalize_history_rows` 가 중단 run 의 고아 tool_use 턴을 drop.

배경:
  `/api/ask` 는 agent 를 web 프로세스 안에서 in-process(`asyncio.to_thread`) 실행한다
  ([[TASK-0159]]). web 재배포/재시작이 ask 를 `execute_sql` 도중 죽이면 assistant 의
  `tool_use` 블록만 저장되고 대응 `tool_result` 전에 종료된다. 재질의 시 그 히스토리를
  그대로 LLM 에 보내면 Anthropic/Bedrock 이 거부한다:
    "messages.N: tool_use ids were found without tool_result blocks immediately after"
  → 해당 대화가 영구히 400 으로 막힌다.

  `_normalize_history_rows` 는 assistant(tool_calls) 턴을 버퍼링해 **모든** tool_use id
  가 뒤따르는 tool 행으로 해소된 경우에만 commit 하고, 하나라도 미해소면 그 턴
  (assistant + 부분 tool 결과)을 통째로 drop 한다.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 순수 함수로 실행된다.
"""
from __future__ import annotations

import json

import agent_core


def _asst(tool_ids):
    return {
        "role": "assistant",
        "tool_calls": json.dumps([
            {"id": t, "type": "function",
             "function": {"name": "execute_sql", "arguments": "{}"}}
            for t in tool_ids
        ]),
    }


def _tool(tcid, content="result"):
    return {"role": "tool", "tool_call_id": tcid, "content": content}


def _user(text="q"):
    return {"role": "user", "content": text}


def _asst_text(text="answer"):
    return {"role": "assistant", "content": text}


def _roles(rows):
    return [r.get("role") for r in rows]


def _assert_all_paired(out):
    """out 의 모든 assistant tool_use id 가 직후 tool 행으로 해소됐는지 검증 (Anthropic 제약)."""
    i = 0
    while i < len(out):
        r = out[i]
        tc = r.get("tool_calls")
        if r.get("role") == "assistant" and tc:
            ids = {c["id"] for c in json.loads(tc)}
            j = i + 1
            while j < len(out) and out[j].get("role") == "tool":
                ids.discard(out[j].get("tool_call_id"))
                j += 1
            assert not ids, f"unpaired tool_use ids 남음: {ids}"
            i = j
        else:
            i += 1


def test_drops_orphaned_tool_use_turn():
    """중단 run: assistant(tool_use) 직후 tool_result 없이 user 재질의 → 고아 턴 drop."""
    rows = [
        _user(), _asst(["t1"]), _tool("t1"), _asst_text(),  # 유효 턴
        _user(), _asst(["orphan"]),                          # execute_sql 도중 종료
        _user("retry"),                                      # 재질의(tool_result 없음)
    ]
    out = agent_core._normalize_history_rows(rows)
    assert _roles(out) == ["user", "assistant", "tool", "assistant", "user", "user"]
    assert all(
        "orphan" not in (r.get("tool_calls") or "")
        for r in out
    ), "고아 tool_use 가 payload 에 남으면 안 됨"
    _assert_all_paired(out)


def test_keeps_valid_multi_tool_turn():
    """모든 tool_use 가 해소된 유효 턴(병렬 2개 포함)은 그대로 보존."""
    rows = [_user(), _asst(["t1", "t2"]), _tool("t1"), _tool("t2"), _asst_text()]
    out = agent_core._normalize_history_rows(rows)
    assert _roles(out) == ["user", "assistant", "tool", "tool", "assistant"]
    _assert_all_paired(out)


def test_drops_partial_tool_turn():
    """2개 tool_use 중 1개만 결과 도착 → 턴 전체 drop(부분 결과도 제거)."""
    rows = [_user(), _asst(["t1", "t2"]), _tool("t1"), _user("next")]
    out = agent_core._normalize_history_rows(rows)
    assert _roles(out) == ["user", "user"]
    _assert_all_paired(out)


def test_drops_orphan_tool_use_at_eof():
    """윈도우 경계/EOF: 마지막이 결과 없는 assistant(tool_use) → drop."""
    rows = [_user(), _asst(["t1"]), _tool("t1"), _asst(["tail"])]
    out = agent_core._normalize_history_rows(rows)
    assert _roles(out) == ["user", "assistant", "tool"]
    _assert_all_paired(out)


def test_drops_orphan_tool_row():
    """매칭 assistant 없는 고아 tool 행 → drop (기존 동작 유지)."""
    rows = [_user(), _tool("nomatch"), _asst_text()]
    out = agent_core._normalize_history_rows(rows)
    assert _roles(out) == ["user", "assistant"]


def test_drops_idless_tool_calls_turn():
    """tool_calls 가 있으나 usable id 가 0개(id 누락/공백) → 페어링 검증 불가 → 턴 drop.

    (REV-20260608-0160 nit 하드닝: 라이브 트리거는 아니나, id 없는 tool_use 가
    payload 에 실리면 동일 400 을 재현하므로 보수적으로 drop.)
    """
    idless = {
        "role": "assistant",
        "tool_calls": json.dumps([
            {"id": "", "type": "function", "function": {"name": "x", "arguments": "{}"}},
            {"type": "function", "function": {"name": "y", "arguments": "{}"}},  # id 키 자체 없음
        ]),
    }
    rows = [_user(), idless, _tool(""), _user("next")]
    out = agent_core._normalize_history_rows(rows)
    # id 없는 assistant 턴은 commit 되면 안 됨
    assert all(not (r.get("role") == "assistant" and r.get("tool_calls")) for r in out)
    assert _roles(out) == ["user", "user"]


def test_preserves_parsed_tool_calls_marker():
    """commit 된 유효 assistant 턴은 `_parsed_tool_calls` 마커를 보존(_format 단계가 소비)."""
    rows = [_asst(["t1"]), _tool("t1"), _asst_text()]
    out = agent_core._normalize_history_rows(rows)
    asst = next(r for r in out if r.get("role") == "assistant" and r.get("tool_calls"))
    assert asst.get("_parsed_tool_calls"), "commit 된 tool_use 턴은 파싱된 tool_calls 마커 보유"
