"""feature-0043 — 위임 결과가 **각인 래퍼 없이** 화면에 도달한다 (2026-08-31 라이브 제보).

## 무슨 일이 있었나

사용자가 최신 러너를 붙이고 용어사전 자동완성을 실행하자, 폼 입력란에 이것이 들어갔다:

    ⟦UNTRUSTED-DATA⟧ (account=admin task=j_… source=external_ai_answer)
    [UNTRUSTED] Authored by an external AI runtime outside our control. …
    <실제 정의 본문>
    ⟦/UNTRUSTED-DATA⟧

`WebAiTasks.Answer` 는 **각인본**이다 — 감사 보존 + 지연 인젝션 방어용. 대화 경로는 그것을
화면에 쓰지 않고 원문을 대화에 따로 저장한다("두 소비처의 요구가 달라 저장본을 나눈다").
콘솔 경로가 그 규율을 따라가지 못해 각인본을 그대로 폼에 흘렸다.

## 여기서 잠그는 것

구조가 아니라 **행위**다: 화면으로 나가는 본문에 sentinel 이 없다. 저장을 어떻게 나누든,
파싱을 하든 안 하든, 그 불변식만 지켜지면 이 결함은 재발하지 않는다.
"""
from __future__ import annotations

# ⚠ 이 테스트는 **feature-0003 쪽**에 산다. `routers.admin_console` 이 `app` 을 import 하고,
#   그 모듈 그래프(`modules.memory` 등)는 feature-0003 conftest 가 세우는 경로에서만 선다.
#   feature-0043 tests 에 두면 수집 단계에서 ModuleNotFoundError 로 죽는다.
from session_guard import INJ_CLOSE, INJ_OPEN, unwrap_external_answer, wrap_external_answer
from routers.admin_console import _console_job_body

_BODY = "수집 경로를 표시하는 출처 구분 값으로,\n리포트에서 필터링 기준이 된다."


def _marked() -> str:
    return wrap_external_answer(_BODY, account="admin", task_id="j_test")


# ── 불변식: 화면으로 나가는 본문에 sentinel 이 없다 ──────────────────────────────────

def test_polling_body_never_contains_the_datamark_sentinel():
    """정본(`JobResult`)이 있든 없든 **화면 본문에 래퍼가 없다**.

    이것이 이 결함의 유일한 불변식이다 — 저장을 어떻게 나누든 여기만 지켜지면 재발하지 않는다.
    """
    for job in ({"result": _BODY, "answer": _marked()},          # 정본 있음(신규 행)
                {"result": None, "answer": _marked()},           # 정본 없음(과거 행) → 폴백
                {"result": "", "answer": _marked()}):            # 빈 문자열도 폴백
        out = _console_job_body(job)
        assert INJ_OPEN not in out, f"각인 여는 마커가 화면으로 나간다: {out[:80]!r}"
        assert INJ_CLOSE not in out, "각인 닫는 마커가 화면으로 나간다"
        assert "[UNTRUSTED]" not in out, "경계 고지가 폼 입력란에 들어간다"
        assert "출처 구분 값" in out, "본문이 유실됐다"


def test_stored_result_is_preferred_over_parsing():
    """정본이 있으면 **파싱하지 않는다** — 폴백에 의존하기 시작하면 규율이 파싱으로 대체된다."""
    job = {"result": "정본본문", "answer": _marked()}
    assert _console_job_body(job) == "정본본문"


# ── 역함수: 정확하고, 모르면 손대지 않는다 ─────────────────────────────────────────

def test_unwrap_is_the_exact_inverse_of_wrap():
    assert unwrap_external_answer(_marked()) == _BODY


def test_unwrap_preserves_multiline_bodies():
    """본문의 줄바꿈을 삼키지 않는다 — 삼키면 설명이 한 줄로 뭉개져 폼에 들어간다."""
    assert "\n" in unwrap_external_answer(_marked())


def test_unwrap_leaves_unmarked_text_untouched():
    """각인이 없으면 **원본 그대로** — 추측해서 자르면 본문 일부가 사라진다."""
    plain = "래퍼 없는 평범한 본문"
    assert unwrap_external_answer(plain) == plain


def test_unwrap_leaves_malformed_markers_untouched():
    """여는 마커만 있는 등 형식이 깨졌으면 손대지 않는다(손실보다 원본 노출이 낫다)."""
    broken = f"{INJ_OPEN} (label)\n본문만 있고 닫는 마커가 없다"
    assert unwrap_external_answer(broken) == broken


def test_unwrap_handles_a_body_that_mentions_the_marker():
    """본문이 마커 문자열을 언급해도 **바깥 블록**을 기준으로 벗긴다."""
    tricky = wrap_external_answer(f"이 값은 {INJ_CLOSE} 를 설명한다", account="a", task_id="t")
    out = unwrap_external_answer(tricky)
    assert out.startswith("이 값은"), out
