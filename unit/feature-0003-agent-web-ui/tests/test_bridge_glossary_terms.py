"""0057 — 브리지 용어 자율수집 복원(답변 동봉 규약 + 서버 수신) 계약 테스트.

## 이 테스트가 잠그는 사고 (2026-09-01 실측)

feature-0043 이 서버 계정 LLM 을 fail-closed 로 닫으면서 `run_agent` 가 돌지 않게 됐다.
그런데 답변 직후 큐레이션(`run_post_answer_curation` → `_glossary_autopropose`)은 **그 안에서만**
호출되고, 브리지 `submit_answer` 는 그것을 부르지 않는다. 결과: **용어 자율수집이 통째로 정지**.

라이브 증거 — `kb_glossary` 의 마지막 `source='auto'` 등록이 전환 당일(2026-08-26)이고 그 뒤
0건. 화면에는 「검토 큐 0건」만 보여서 「요즘 등록될 용어가 없다」로 읽혔다(§16.7 G8-a — 결정의
적용면 누락).

두 층을 잠근다:
1. **러너 규약** — 답변 끝의 `#GLOSSARY:` 한 줄을 떼어 목록으로 만들되, 규약을 모르거나 JSON 이
   깨진 런타임이 **답변을 상하게 하지 않는다**.
2. **서버 수신** — 통제 밖 LLM 의 산출물이므로 서버 LLM 경로와 **같은 필터**를 타고, 제품 귀속을
   주변 상태가 아니라 task 행에서 해소한다.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

_SRC = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _load_bridge_agent():
    """러너 스크립트를 모듈로 로드한다(패키지가 아니라 배포용 단일 파일이라 경로 로드)."""
    path = os.path.join(_SRC, "static", "agent", "bridge_agent.py")
    spec = importlib.util.spec_from_file_location("bridge_agent_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BA = _load_bridge_agent()


def _peel(raw):
    """러너 `handle_one` 과 **같은 순서**로 벗긴다 — 순서가 계약의 일부다."""
    body, title = BA.split_title(raw)
    body, terms = BA.split_glossary(body)
    if not title:
        body, title = BA.split_title(body)
    return body, title, terms


# ── 1층: 러너 규약 ────────────────────────────────────────────────────────────
def test_glossary_line_is_peeled_and_body_is_clean():
    raw = ('답변 본문입니다.\n둘째 줄.\n'
           '#GLOSSARY: [{"term":"SponsorCode","definition":"후원 코드","tier":"product",'
           '"confidence":0.9}]\n'
           '#TITLE: 후원 코드 문의')
    body, title, terms = _peel(raw)
    assert body == "답변 본문입니다.\n둘째 줄."
    assert title == "후원 코드 문의"
    assert terms == [{"term": "SponsorCode", "definition": "후원 코드",
                      "tier": "product", "confidence": 0.9}]
    # 규약 문자열이 사용자 화면에 남지 않는다 — 남으면 그 자체가 회귀다.
    assert "#GLOSSARY" not in body and "#TITLE" not in body


def test_reversed_marker_order_is_absorbed():
    """지시는 「용어 줄 → 제목 줄」 하나로 주지만, 뒤바꿔 내는 런타임이 있어도 둘 다 살린다."""
    raw = '본문.\n#TITLE: 제목\n#GLOSSARY: [{"term":"A","definition":"B"}]'
    body, title, terms = _peel(raw)
    assert body == "본문." and title == "제목" and len(terms) == 1


@pytest.mark.parametrize("tail", [
    "#GLOSSARY: []",                 # 담을 것이 없는 정상 턴
    "#GLOSSARY: [{broken json",      # 형식 위반
    "#GLOSSARY:",                    # 빈 값
    '#GLOSSARY: {"not":"a list"}',   # 배열 아님
])
def test_malformed_glossary_line_never_damages_the_answer(tail):
    """형식을 못 지킨 것은 그 AI 의 사정이고, 그 대가를 사용자 답변이 치르게 하지 않는다."""
    body, title, terms = _peel(f"소중한 답변 본문.\n{tail}\n#TITLE: 제목")
    assert body == "소중한 답변 본문."
    assert title == "제목"
    assert terms == []


def test_runner_without_the_convention_is_unaffected():
    """구 러너(마커를 모르는 실행 파일)는 종전과 완전히 같게 동작한다 — additive 계약."""
    raw = "본문만 있습니다.\n#TITLE: 제목"
    body, title, terms = _peel(raw)
    assert body == "본문만 있습니다." and title == "제목" and terms == []


def test_glossary_line_is_capped():
    many = json.dumps([{"term": f"t{i}", "definition": "d"} for i in range(20)],
                      ensure_ascii=False)
    _, _, terms = _peel(f"본문.\n#GLOSSARY: {many}\n#TITLE: T")
    assert len(terms) == BA._GLOSSARY_MAX


class _StubApi:
    """`compose_prompt` 가 URL·토큰 문자열만 읽는다 — 네트워크를 타지 않는다."""

    base = "http://stub"
    token = "stub-token"


def test_composed_prompt_states_the_convention_and_separates_the_two_axes():
    """프롬프트가 두 축(tier / confidence)을 **갈라서** 지시하는지.

    이 지시가 합쳐지면(종전 서버 프롬프트가 그랬듯 confidence 에 재사용성을 섞으면) 범용
    용어가 다시 고신뢰로 올라온다 — 그것이 이 cycle 이 고치는 근본 원인이다.

    ⚠ **소스 텍스트가 아니라 조립된 프롬프트 문자열을 본다** (§16.7 G11-a): 소스에는 이
    조항을 설명하는 주석이 있어서, 파일 전체를 검사하면 **자기 주석이 자기 단언을 통과**시킨다.
    실제로 `compose_prompt` 를 돌려 산출물을 검사해야 지시가 사라진 것을 잡는다.
    """
    prompt = BA.compose_prompt(_StubApi(), {"kind": "chat", "question": "질문",
                                            "task_id": "t1"})
    assert BA._GLOSSARY_MARK in prompt, "용어 동봉 규약이 프롬프트에 없다"
    assert '"tier"' in prompt and '"confidence"' in prompt
    # 두 축이 서로 다른 질문임을 명시하는 문장이 있어야 한다.
    assert "어디까지 통용되는가" in prompt
    assert "얼마나 명확히 정의했는가" in prompt
    # 예시가 있어야 모델이 general 을 알아본다(사용자 지적 3종 중 최소 하나).
    assert "Online DDL" in prompt or "시점 복구" in prompt


def test_console_job_prompt_has_no_glossary_convention():
    """콘솔 작업에는 대화용 프레이밍을 씌우지 않는다 — 용어 규약도 마찬가지다.

    씌우면 JSON 산출물 끝에 규약 줄이 붙어 파서가 깨진다(러너가 이미 겪은 형태).
    """
    prompt = BA.compose_prompt(_StubApi(), {"kind": "job", "question": "지시문"})
    assert BA._GLOSSARY_MARK not in prompt and prompt == "지시문"


# ── 2층: 서버 수신 ────────────────────────────────────────────────────────────
class _Cur:
    def __init__(self, state):
        self._state = state

    def execute(self, sql, params=None):
        self._state["sql"].append((sql, params))
        self._state["last"] = self._state["product_row"] if "WebProducts" in sql else None

    def fetchone(self):
        return self._state["last"]

    def close(self):
        pass


class _Conn:
    def __init__(self, product_row):
        self.state = {"sql": [], "last": None, "product_row": product_row}

    def cursor(self):
        return _Cur(self.state)


def test_absorb_resolves_product_from_the_task_row(monkeypatch):
    """제품 귀속은 **task 행**에서 온다 — 주변 상태(`get_active_product_scope`)를 읽지 않는다.

    이 요청은 웹 요청 스레드라 그 값이 이 대화의 제품이라는 보장이 없다(§16.7 G7-a).
    """
    from routers import ai_tools

    calls = []
    _install_fake_kg(monkeypatch, calls)
    _patch_pg(monkeypatch)

    conn = _Conn(("GZ_QA_G",))
    stats = ai_tools._absorb_bridge_glossary_terms(
        conn, task={"product_id": 7, "conversation_id": "c1"}, task_id="t1",
        raw_terms=[{"term": "SponsorCode", "definition": "후원 코드", "tier": "product"}])
    assert calls and calls[0]["scope_key"] == "product.gz_qa_g"
    assert stats == {"auto_promoted": 1}


def test_absorb_falls_back_to_global_when_product_is_absent(monkeypatch):
    """제품 없는 대화의 후보는 전역 scope 로 넘긴다 — 라우터가 그것을 **검토 큐**로 받는다.

    (자동등록이 아니다: 귀속처를 모르는 용어를 전역 사전에 앉히지 않는다.)
    """
    from routers import ai_tools

    calls = []
    _install_fake_kg(monkeypatch, calls)
    _patch_pg(monkeypatch)

    conn = _Conn(("",))
    ai_tools._absorb_bridge_glossary_terms(
        conn, task={"product_id": 0, "conversation_id": "c1"}, task_id="t1",
        raw_terms=[{"term": "무언가", "definition": "정의"}])
    assert calls[0]["scope_key"] == "common"


def test_absorb_ignores_non_list_and_empty(monkeypatch):
    from routers import ai_tools

    calls = []
    _install_fake_kg(monkeypatch, calls)
    _patch_pg(monkeypatch)
    conn = _Conn(("GZ",))
    for raw in ("문자열", {}, [], None, 3):
        assert ai_tools._absorb_bridge_glossary_terms(
            conn, task={"product_id": 1}, task_id="t", raw_terms=raw) == {}
    assert calls == []


def test_absorb_caps_item_count(monkeypatch):
    """러너는 통제 밖 LLM 이다 — 러너가 상한을 지켰다고 **믿지 않는다**(서버가 다시 건다)."""
    from routers import ai_tools

    calls = []
    _install_fake_kg(monkeypatch, calls)
    _patch_pg(monkeypatch)
    conn = _Conn(("GZ",))
    ai_tools._absorb_bridge_glossary_terms(
        conn, task={"product_id": 1}, task_id="t",
        raw_terms=[{"term": f"t{i}", "definition": "d"} for i in range(50)])
    assert len(calls) == ai_tools._BRIDGE_GLOSSARY_MAX


# ── 테스트 더블 ───────────────────────────────────────────────────────────────
def _fake_kb_glossary(calls):
    """`modules.kb_glossary` 대역. **정규화는 진짜 것을 쓴다** — 그래야 「서버 LLM 경로와 같은
    필터를 탄다」는 계약이 실제로 검사된다(대역이 필터까지 흉내 내면 vacuous pass 다)."""
    import types

    from modules import kb_glossary as real

    m = types.ModuleType("modules.kb_glossary")
    m.GLOBAL_SCOPE = real.GLOBAL_SCOPE
    m.COMMON_ROLE = real.COMMON_ROLE
    m.normalize_suggestion_items = real.normalize_suggestion_items

    def _route(conn, scope_key, term, definition, **kw):
        calls.append({"scope_key": scope_key, "term": term, "kw": kw})
        return "auto_promoted"

    m.auto_promote_or_queue = _route
    return m


def _install_fake_kg(monkeypatch, calls):
    """`from modules import kb_glossary` 를 대역으로 바꾼다.

    ⚠ `sys.modules` 만 바꾸면 **안 걸린다** — `modules` 패키지 객체에 이미 `kb_glossary`
    속성이 바인딩돼 있어 `from X import Y` 가 그쪽을 집는다. 두 곳을 함께 바꾼다.
    (이 함정을 처음에 밟았고, 그때 테스트는 대역이 아니라 실제 코드를 돌려 엉뚱한 이유로
    실패했다 — 실패가 성공이었다면 그대로 vacuous pass 가 됐을 자리다.)
    """
    import modules as modules_pkg

    fake = _fake_kb_glossary(calls)
    monkeypatch.setitem(sys.modules, "modules.kb_glossary", fake)
    monkeypatch.setattr(modules_pkg, "kb_glossary", fake, raising=False)
    return fake


def _patch_pg(monkeypatch):
    """`shared.db` 의 PG 연결을 no-op 으로 — 이 테스트는 라우팅 결정만 본다(라이브 무접촉)."""
    import types

    fake = types.ModuleType("shared.db")
    fake._pg_available = lambda: True

    class _PG:
        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    fake._pg_connect = lambda **kw: _PG()
    real = sys.modules.get("shared.db")
    if real is not None:
        for name in dir(real):
            if not hasattr(fake, name):
                setattr(fake, name, getattr(real, name))
    monkeypatch.setitem(sys.modules, "shared.db", fake)
