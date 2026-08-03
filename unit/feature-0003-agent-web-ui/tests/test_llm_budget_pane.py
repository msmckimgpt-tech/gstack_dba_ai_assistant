"""feature-0032 — AI 운영 현황의 백그라운드 LLM 토큰 예산 노출 단위 테스트.

**왜 렌더까지 단정하는가**: T0b 에서 응답 필드만 추가하고 `admin.js` 렌더를 빠뜨린 채
"콘솔 노출 완료"로 보고한 적이 있다(§16.7 G3 위반). API 필드 존재는 노출이 아니다 —
사용자가 볼 수 있어야 노출이다. 그래서 응답 계약과 렌더 배선을 함께 단정한다.
"""
import pathlib

import pytest

from shared import llm_budget as lb

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "src" / "static"
# feature-0038 Cycle 2: AI 운영 현황 pane 은 admin/aiops.js 로 분리(byte-동치 이동).
#   본 테스트의 단언 대상(예산 막대 렌더)은 그 pane 소속 — admin.js 와 분리 모듈을 합본으로 검사한다.
_ADMIN_JS_PARTS = ("admin.js", "admin/usage.js", "admin/aiops.js")


class _AdminJsView:
    def read_text(self, encoding="utf-8"):
        return "".join((_STATIC / n).read_text(encoding=encoding) for n in _ADMIN_JS_PARTS)


_ADMIN_JS = _AdminJsView()


@pytest.fixture(autouse=True)
def _clear_cache():
    lb.invalidate()
    yield
    lb.invalidate()


def test_admin_js_renders_the_budget_pane():
    """응답 필드를 실제로 읽어 화면에 그리는 코드가 있어야 한다."""
    src = _ADMIN_JS.read_text(encoding="utf-8")
    assert "data.llm_token_budget" in src, "admin.js 가 예산 필드를 읽지 않는다 — 노출이 아니다"
    assert "백그라운드 LLM 토큰 예산" in src, "사용자가 볼 제목이 없다"


def test_admin_js_states_that_user_requests_are_exempt():
    """상한이 대화 답변을 막지 않는다는 사실이 화면에 쓰여 있어야 한다 — 운영자가 '분석이 멈췄으니
    답변도 멈추겠다'고 오해하면 불필요한 상한 상향을 부른다."""
    src = _ADMIN_JS.read_text(encoding="utf-8")
    assert "사용자가 기다리는 호출은 이 예산에서 제외" in src


def test_admin_js_distinguishes_unlimited_from_unmeasurable():
    """'상한 없음'과 '조회 불가'는 다른 상태다 — 같은 문구로 뭉뚱그리면 계량 장애가 숨는다."""
    src = _ADMIN_JS.read_text(encoding="utf-8")
    assert "상한 없음" in src and "조회할 수 없어" in src


def test_snapshot_shape_matches_what_the_pane_reads(monkeypatch):
    """렌더가 읽는 키가 snapshot 계약에 실제로 있는지 — 필드명 드리프트 차단."""
    monkeypatch.setattr(lb, "cap", lambda: 1000)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: 250)
    snap = lb.snapshot()
    for key in ("enabled", "measurable", "spent", "cap", "remaining", "used_ratio", "exhausted"):
        assert key in snap, f"pane 이 읽는 키 {key} 가 snapshot 에 없다"
    assert snap["remaining"] == 750 and snap["used_ratio"] == 0.25


def test_exhausted_budget_surfaces_as_attention(monkeypatch):
    """소진은 조용히 지나가면 안 된다 — '왜 분석이 안 도나'의 1차 답이다."""
    import importlib
    ai_ops = importlib.import_module("routers.ai_ops")
    src = pathlib.Path(ai_ops.__file__).read_text(encoding="utf-8")
    assert "백그라운드 LLM 토큰 상한 도달" in src
    assert "llm_token_budget" in src
