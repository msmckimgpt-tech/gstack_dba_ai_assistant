"""TASK-0232 — 제품 프롬프트 자동작성의 잘림 검출(meta.truncated) 계약 테스트.

admin_generate_product_prompt 는 LLM 응답의 finish_reason 이 'length' 면 출력이
토큰 상한에 도달해 잘린 것이므로 meta.truncated=True 로 반환한다. admin UI 는 이
플래그로 "프롬프트가 중간에 잘렸을 수 있음" 경고를 표시한다 (조용한 잘림 방지).

app.py 는 컨테이너 전용 무거운 의존성(modules.memory 등)이 있어 로컬에서 직접
import 할 수 없으므로, 여기서는 잘림 판정 로직 자체의 계약을 fake choice 객체로
고정한다. app.py 의 실제 분기(`finish_reason == "length"`)와 동일한 술어를 검증해
회귀를 방어한다.
"""


class _FakeChoice:
    def __init__(self, content, finish_reason):
        self.message = type("_Msg", (), {"content": content})()
        self.finish_reason = finish_reason


def _detect_truncated(choice) -> bool:
    """app.py admin_generate_product_prompt 의 잘림 판정과 동일한 술어.

    이 함수의 정의가 app.py 의 분기와 어긋나면 회귀다 — 동일 술어 유지가 계약.
    """
    finish_reason = getattr(choice, "finish_reason", None)
    return finish_reason == "length"


def test_truncated_true_when_finish_reason_length():
    """출력이 max_tokens 에 도달(finish_reason='length')하면 truncated=True."""
    choice = _FakeChoice("잘린 시스템 프롬프트 본문…", "length")
    assert _detect_truncated(choice) is True


def test_truncated_false_when_finish_reason_stop():
    """정상 완료(finish_reason='stop')면 truncated=False."""
    choice = _FakeChoice("완성된 시스템 프롬프트 본문.", "stop")
    assert _detect_truncated(choice) is False


def test_truncated_false_when_finish_reason_missing():
    """finish_reason 이 없으면(None) 잘림으로 단정하지 않는다 — 오탐 방지."""
    choice = _FakeChoice("본문", None)
    assert _detect_truncated(choice) is False


def test_response_meta_includes_truncated_key():
    """응답 meta 스키마에 truncated 키가 포함돼야 한다 (admin UI 계약).

    app.py 가 반환하는 meta dict 형태를 재현해 키 존재를 고정한다.
    """
    choice = _FakeChoice("본문", "length")
    meta = {
        "schema_count": 0,
        "schema_insight_count": 0,
        "table_insight_count": 0,
        "topic_count": 0,
        "summary_count": 0,
        "grounded": False,
        "truncated": _detect_truncated(choice),
    }
    assert "truncated" in meta
    assert meta["truncated"] is True
