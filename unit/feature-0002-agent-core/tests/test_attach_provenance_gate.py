"""REQ-20260814-attach-provenance-gate — 타 멤버 첨부 본문이 실린 턴의 쓰기 도구 차단.

SECURITY §47.4 가 **수용 위험**으로 남긴 confused-deputy 경로를 실행 단계에서 좁힌다. 공유 대화에서
타 멤버 파일을 읽을 수 있게 되면서(§47), 그 파일 안의 지시문이 호출자 권한으로 도구를 움직일 여지가
생겼다. 프롬프트 계약(datamark + "데이터로만 취급")은 확률적 완화이지 보장이 아니다.

사용자 결정(2026-08-14): **쓰기·외부영향 도구만** 게이트한다. 조회는 그대로 — 그렇지 않으면 공유
대화에서 남의 파일을 보며 DB 와 대조하는 정상 작업까지 죽는다.

여기서 고정하는 계약:
  - 무엇을 막는가(scratch 3종) / 무엇을 막지 않는가(조회 전부 + `update_attachment` — §18.8 [P2])
  - 언제 막는가(타 멤버 **본문**이 실린 턴에만 — 목록만으로는 막지 않는다)
  - 실패 시 어느 쪽으로 기우는가(신호를 못 읽으면 **막는다**)
  - 거부가 교정 정보를 싣는가(이유 없이 막으면 모델이 반복하거나 "실패" 만 전한다)
"""
from __future__ import annotations

import agent_core
from modules import tools


def _set_untrusted(flag: bool):
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(flag)


# ── 대상 선정 ──────────────────────────────────────────────────────────────

def test_write_tools_are_gated_when_untrusted_body_present():
    """작업공간 상태를 바꾸는 도구는 타 멤버 본문이 있으면 막힌다."""
    _set_untrusted(True)
    for name in ("scratch_sql", "scratch_import", "scratch_reset"):
        out = tools._provenance_gate(name)
        assert out and "[차단]" in out, name


def test_read_tools_are_never_gated():
    """조회 도구는 막지 않는다 — 결과는 어차피 그 사용자가 볼 수 있는 것이다."""
    _set_untrusted(True)
    for name in ("execute_sql", "describe_table", "search_tables", "get_sample_rows",
                 "read_attachment", "explain_query", "graph_navigate", "list_schemas"):
        assert tools._provenance_gate(name) is None, name


def test_execute_sql_is_deliberately_not_gated():
    """`execute_sql` 제외는 의도다 — sql_guard 가 단일 SELECT/CTE 만 허용하고 DDL/DML 을 전면 차단한다.

    이것까지 막으면 "남의 파일을 보며 라이브 DB 와 대조" 하는 그룹 대화의 핵심 작업이 죽는다.
    """
    assert "execute_sql" not in tools._PROVENANCE_GATED_TOOLS


def test_gated_set_is_exactly_the_scratch_tools():
    """게이트 목록이 조용히 넓어지거나 좁아지지 않도록 고정한다."""
    assert tools._PROVENANCE_GATED_TOOLS == frozenset({
        "scratch_sql", "scratch_import", "scratch_reset"})


def test_update_attachment_is_deliberately_not_gated():
    """**[P2] 반영**: 첨부 갱신은 막지 않는다.

    공유 대화는 최근 첨부를 매 턴 자동 인라인하므로, 무관한 타 멤버 파일 하나 때문에 호출자가
    자기 파일을 갱신하는 가장 흔한 쓰기까지 막히고 **다음 턴에도 같은 파일이 다시 실려** 빠져나갈
    방법이 없다. 게다가 그 도구의 쓰기 대상은 구조적으로 본인 파일뿐이다
    (`_materialize_assistant_attachment_edits` 가 source AccountId 일치를 강제).
    """
    _set_untrusted(True)
    assert "update_attachment" not in tools._PROVENANCE_GATED_TOOLS
    assert tools._provenance_gate("update_attachment") is None


# ── 발동 조건 ──────────────────────────────────────────────────────────────

def test_no_gate_when_no_untrusted_body():
    """타 멤버 본문이 없으면(1:1 대화·본인 파일만) 아무것도 막지 않는다 — 무회귀."""
    _set_untrusted(False)
    for name in ("scratch_sql", "scratch_reset", "execute_sql"):
        assert tools._provenance_gate(name) is None, name


def test_flag_is_set_only_when_other_member_body_rendered(monkeypatch):
    """플래그는 **본문이 실제로 렌더된** 순간에만 선다(목록만으로는 서지 않는다).

    목록·파일명은 주입 벡터가 아니다. 그것까지 신호로 삼으면 남의 파일이 대화에 있다는 이유만으로
    쓰기가 막힌다(과차단).
    """
    import json

    rows = [(
        1142, "conv-x", "theirs.sql", "text", "text/plain", 100, "small", "uploaded",
        json.dumps({}), None, 1, "user", 50, None,
    )]

    class _RowsConn:
        def cursor(self, *a, **k):
            class _C:
                def execute(self, *a, **k): pass
                def fetchall(self): return rows
                def close(self): pass
            return _C()

    monkeypatch.setenv("ATTACHMENT_IDS", "1142")
    monkeypatch.setattr(agent_core, "_resolve_group_sender_labels", lambda *a, **k: {50: "jm.kim"})
    # 본문 인라인 없음 — 목록만 렌더된다.
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    out = agent_core._build_attachment_context_section(_RowsConn(), [1142], 10, "conv-x")
    assert "uploaded-by=jm.kim" in out, "목록 라벨은 붙는다"
    assert agent_core.untrusted_attachment_body_in_context() is False, \
        "목록만 실렸는데 플래그가 서면 과차단이 된다"

    # 본문이 실리면 선다.
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts",
                        lambda: {1142: {"filename": "theirs.sql", "content": "SELECT 1;", "truncated": False}})
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    agent_core._build_attachment_context_section(_RowsConn(), [1142], 10, "conv-x")
    assert agent_core.untrusted_attachment_body_in_context() is True


def test_flag_resets_per_compose(monkeypatch):
    """매 프롬프트 조립마다 초기화된다 — 워커 스레드 재사용 시 이전 run 상태가 남으면 안 된다."""
    import inspect
    src = inspect.getsource(agent_core.compose_system_prompt)
    assert "_UNTRUSTED_ATTACH_BODY_CTX.set(False)" in src


# ── 실패 방향 ──────────────────────────────────────────────────────────────

def test_signal_read_failure_blocks(monkeypatch):
    """신호를 읽지 못하면 **막는다** — 이 게이트가 조용히 열리면 존재 이유가 없다."""
    def _boom():
        raise RuntimeError("ctx gone")

    monkeypatch.setattr(agent_core, "untrusted_attachment_body_in_context", _boom)
    out = tools._provenance_gate("scratch_sql")
    assert out and "[차단]" in out


def test_helper_itself_fails_closed(monkeypatch):
    """contextvar 조회가 깨져도 helper 는 True(=막음)를 돌려준다."""
    class _Broken:
        def get(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(agent_core, "_UNTRUSTED_ATTACH_BODY_CTX", _Broken())
    assert agent_core.untrusted_attachment_body_in_context() is True


# ── 거부 품질 ──────────────────────────────────────────────────────────────

def test_refusal_carries_reason_and_alternatives():
    """거부는 교정 정보를 실어야 한다 — 이유 없이 막으면 모델이 반복하거나 '실패' 만 전한다."""
    _set_untrusted(True)
    out = tools._provenance_gate("scratch_sql")
    assert "다른 멤버가 올린 첨부" in out, "왜 막혔는지"
    assert "조회 도구는 그대로" in out, "무엇은 되는지"
    assert "새 대화" in out, "어떻게 풀 수 있는지"
    assert "같은 대화 안에서는 계속 차단" in out, \
        "다음 턴에도 같은 파일이 실린다는 사실을 숨기면 사용자가 헛되이 재시도한다"
    assert "update_attachment" in out, "막히지 않는 쓰기 경로를 알려준다"
    assert "숨기지도 마세요" in out, "사용자에게 사실을 알리도록"


def test_dispatch_applies_gate_before_handler():
    """게이트가 **dispatch 단일 지점**에 있어야 새 도구가 추가돼도 자동으로 덮인다."""
    import inspect
    src = inspect.getsource(tools.execute_tool)
    assert "_provenance_gate(tool_name)" in src
    # 핸들러 실행보다 앞에 있어야 한다.
    assert src.index("_provenance_gate") < src.index("_DATASOURCE_FREE_TOOLS")
