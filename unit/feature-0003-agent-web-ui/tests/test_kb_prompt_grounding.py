"""2026-09-02 — 큐레이션 KB 근거가 **도구 호출 없이** 프롬프트에 실린다.

## 이 테스트가 잠그는 사고 (부트스트랩 계정 라이브 대화 실측)

2026-09-01 에 `get_task_context` 를 5개 층으로 넓혔고(F1), 서버 쪽은 옳았다 — 실제 GZ_QA_G
task 로 부르면 200 OK 로 정확한 근거가 나온다. 그런데 **라이브 대화에서는 0 기여였다.**

    질문: "steam_billing_log 의 status 코드값이 각각 무슨 뜻이고 …"
    AI  : "steam_billing_log 라는 테이블 자체가 등록 메타데이터 어디에도 없습니다"

번들에는 그 정의가 분명히 들어 있었다. 원인은 러너가 AI 에게 안내하는 도구 목록
(`compose_prompt`)에 **`get_task_context` 가 없다**는 것이다 — list_schemas·describe_table·
search_tables·execute_sql 등 *조사* 도구만 나열한다. 없는 도구는 부를 수 없다.

## 왜 서버에서 고치는가

러너는 **사용자 머신 설치본**이라 프롬프트만 고치면 이미 도는 러너에는 닿지 않는다. 점유 응답
(`claim_request`)은 **매번 서버가 만든다** — 여기 실으면 러너 버전과 무관하게 즉시 도달한다.
전환 전 서버 계정 AI 는 `_build_knowledge_context()` 가 시스템 프롬프트에 **무조건** 주입했고,
외부 AI 전환이 그것을 「AI 가 부르면 받음」으로 바꾼 것이 이 결함이다. 자동 주입으로 되돌린다.
"""
from __future__ import annotations

import os
import sys
import types

_SRC = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ── 러너 쪽 계약: 받은 근거를 프롬프트에 놓는다 ────────────────────────────────
def _compose(**task):
    import importlib.util

    here = os.path.join(_SRC, "static", "agent", "bridge_agent.py")
    spec = importlib.util.spec_from_file_location("_ba_probe", here)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    api = types.SimpleNamespace(base="https://example.invalid")
    base = {"task_id": "t1", "question": "status 코드가 뭐야", "kind": "chat"}
    base.update(task)
    return mod.compose_prompt(api, base)


def test_kb_context_is_placed_in_prompt():
    """서버가 준 근거가 프롬프트 본문에 **그대로** 들어간다."""
    out = _compose(kb_context="용어:\n- steam_billing_log: Steam 결제 로그")
    assert "steam_billing_log: Steam 결제 로그" in out
    assert "이 제품에 등록된 근거" in out


def test_kb_context_absent_omits_block_entirely():
    """근거가 없으면 블록 자체가 없다 — 빈 머리글만 남기면 「등록된 게 없다」로 오독된다.

    옛 서버(이 필드를 안 보내는)와의 호환도 이 계약이 지킨다.
    """
    out = _compose()
    assert "이 제품에 등록된 근거" not in out
    assert "등록 근거 끝" not in out


def test_kb_block_precedes_the_question():
    """근거는 **질문보다 앞**에 둔다 — 뒤에 두면 모델이 질문만 읽고 답을 시작한다."""
    out = _compose(kb_context="용어:\n- MAU: 월간 활성 사용자")
    assert out.index("등록된 근거") < out.index("── 질문 ──")


def test_kb_block_tells_ai_not_to_reinvestigate():
    """이미 조회된 것임을 밝힌다 — 안 그러면 같은 내용을 도구로 다시 캔다(왕복 낭비)."""
    out = _compose(kb_context="용어:\n- MAU: 월간 활성")
    assert "다시 조사하지 마라" in out


def test_job_kind_still_bypasses_framing():
    """콘솔 작업(`kind='job'`)에는 이 블록도 붙이지 않는다 — 기존 계약 불변."""
    out = _compose(kind="job", question="원문 그대로", kb_context="용어:\n- X: Y")
    assert out == "원문 그대로"


# ── 서버 쪽 계약: 점유 응답에 근거를 실어 보낸다 ──────────────────────────────
def test_claim_response_declares_kb_fields():
    """`claim_request` 응답에 `kb_context`·`kb_notes` 가 **선언**돼 있다.

    ⚠ 이 단언이 소스 검사인 이유: `claim_request` 는 원자적 UPDATE·원장·활동기록이 얽혀
      있어 대역으로 완주시키려면 테스트가 그 전부를 재현해야 하고, 그러면 검사하려는 계약보다
      대역이 커진다. 여기서는 **필드가 응답 dict 에 있는가**만 잠그고, 실제 값의 정확성은
      `_kb_grounding_sections` 쪽 테스트(feature-0002/0003)가 이미 검사한다.
    """
    import inspect

    from routers import ai_tools

    src = inspect.getsource(ai_tools.claim_request)
    assert '"kb_context": kb_context' in src, "점유 응답에 kb_context 가 없다"
    assert '"kb_notes": kb_notes' in src
    assert "_kb_grounding_sections(" in src, "근거 조립을 호출하지 않는다"


def test_claim_matches_on_plain_question_not_wrapped():
    """매칭은 가드 래퍼가 붙지 않은 **원문**으로 한다.

    `marked` 로 매칭하면 래퍼 문구(⟦UNTRUSTED-DATA⟧·canary) 안의 낱말이 용어에 걸린다.
    """
    import inspect

    from routers import ai_tools

    src = inspect.getsource(ai_tools.claim_request)
    i = src.index("_kb_grounding_sections(")
    call = src[i:i + 160]
    assert "question," in call and "marked" not in call.split(")")[0], \
        f"원문이 아닌 값으로 매칭한다: {call[:90]!r}"


def test_claim_bundle_has_cap():
    """무제한 주입 금지 — 상한과 **절단 고지**가 함께 있다."""
    import inspect

    from routers import ai_tools

    src = inspect.getsource(ai_tools.claim_request)
    assert "_CTX_BUNDLE_MAX_CHARS" in src
    assert "잘렸습니다" in src, "조용히 자르면 「그 층에 없었다」와 구별되지 않는다"
