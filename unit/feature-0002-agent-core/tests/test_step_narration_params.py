"""TASK-0178 — 단계 narration 을 tool 호출 인자(reason/work)로 전달하는 회귀 테스트.

배경: content 동시 방출(TASK-0177)은 Bedrock gateway 가 tool_use 턴의 text content 를
strip 해 라이브에서 reason_source 가 전부 derived 였음(REV-20260610-0177 M2 확정).
인자(arguments)는 안정 전달되므로 모든 도구 스키마에 optional reason/work 를 주입한다.
"""
from __future__ import annotations

from modules.tools import (
    TOOL_DEFINITIONS,
    TOOL_DEFINITIONS_FULL,
    execute_tool,
)


def test_all_tools_have_reason_and_work_props():
    for t in TOOL_DEFINITIONS_FULL:
        name = t["function"]["name"]
        params = t["function"]["parameters"]
        props = params["properties"]
        assert "reason" in props, f"{name} 에 reason 파라미터 없음"
        assert "work" in props, f"{name} 에 work 파라미터 없음"
        # narration 은 optional — required 에 넣지 않는다(미제공 시 derived fallback)
        req = params.get("required", [])
        assert "reason" not in req and "work" not in req, f"{name} 가 narration 을 required 로"


def test_core_tools_share_injection():
    # TOOL_DEFINITIONS_FULL = TOOL_DEFINITIONS + 확장. 핵심 4개도 동일 주입돼야 함.
    for t in TOOL_DEFINITIONS:
        props = t["function"]["parameters"]["properties"]
        assert "reason" in props and "work" in props


def test_reason_is_first_property_think_first():
    # think-first: reason 이 properties 맨 앞에 와야 모델이 먼저 근거를 떠올린다.
    keys = list(TOOL_DEFINITIONS[0]["function"]["parameters"]["properties"].keys())
    assert keys[0] == "reason"
    assert keys[1] == "work"


def test_execute_tool_ignores_extra_narration_args():
    # 핸들러는 named-get 이라 reason/work 가 인자에 남아도 무해해야 한다(루프가 pop 하지만 이중 안전).
    # list_schemas 는 conn 을 거의 안 쓰므로 None 으로도 동작(인자 무시 경로만 확인).
    out = execute_tool(
        None,
        "list_schemas",
        {"reason": "접근 가능한 스키마 파악", "work": "스키마 목록 확인"},
    )
    # 예외 없이 문자열 반환(권한/conn 에 따라 내용은 달라도 형식만 확인)
    assert isinstance(out, str)
