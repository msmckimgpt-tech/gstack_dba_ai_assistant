"""2026-09-01 — 큐레이션한 KB 가 외부 AI 에 **도달하는가** + 전역 상속 노출.

## 이 테스트가 잠그는 사고 (라이브 실측 2026-09-01)

feature-0043 전환 후 답변은 개인 AI 가 만든다. 그런데 `get_task_context`(브리지가 근거를 받는
유일한 창구)는 내부 대화 경로가 주입하던 grounding **9층 중 1층**(클러스터 요약)만 넘기고
있었다. 관리 콘솔 「메타데이터」가 큐레이션하는 **용어사전 732행 · ENUM 84행 · 테이블 설명
154행 · 컬럼 설명 6,770행 · 샘플쿼리**가 답변에 **0 기여**했다.

사람이 큐레이션한 것을 답변이 못 쓰면 큐레이션 화면 자체가 장식이 된다 — 자율수집을 되살려도
(직전 cycle) 수집한 것이 쓰이지 않으면 의미가 없다.

## 그리고 축이 둘이다

| 층 | scope 축 |
|---|---|
| 용어사전·ENUM · 테이블/컬럼 설명 · 샘플쿼리 | **제품**(`product.<key>`) |
| 테이블 관계 · 클러스터 요약 | **datasource** |

한 축으로만 부르면 그 축이 아닌 층은 **항상 빈다** — 이 함수가 이미 한 번 겪은 실패 형태다
(datasource scope 를 안 넘겨 클러스터 요약이 늘 비었던 사고).
"""
from __future__ import annotations

import importlib
import os
import sys
import types

import pytest

_SRC = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ── 테스트 더블 ───────────────────────────────────────────────────────────────
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
    def __init__(self, product_row=None):
        self.state = {"sql": [], "last": None, "product_row": product_row}

    def cursor(self):
        return _Cur(self.state)


def _install_loaders(monkeypatch, calls, *, bodies=None, raises=()):
    """4개 grounding 로더를 대역으로 바꾸고 호출 인자를 기록한다.

    ⚠ `sys.modules` 만 바꾸면 안 걸린다 — `modules` 패키지 객체에 이미 속성이 바인딩돼 있어
    `importlib.import_module` 이 캐시를 집는다. 두 곳을 함께 바꾼다.
    """
    import modules as pkg

    bodies = bodies or {}
    specs = {
        "kb_glossary": "load_glossary_enum_context",
        "kb_metadata": "load_table_column_descriptions",
        "sample_queries": "load_example_queries_context",
        "relationships": "load_relationship_context",
    }
    for mod_name, fn_name in specs.items():
        fake = types.ModuleType(f"modules.{mod_name}")

        def _make(mn=mod_name, fnm=fn_name):
            def _fn(question, scope_key=None, conn=None, **kw):
                calls.append({"module": mn, "question": question, "scope_key": scope_key})
                if mn in raises:
                    raise RuntimeError(f"{mn} boom")
                return bodies.get(mn, f"<{mn} body>")
            return _fn

        setattr(fake, fn_name, _make())
        # 실물 모듈이 갖고 있던 다른 심볼(호출측이 참조할 수 있다)은 그대로 승계.
        try:
            real = importlib.import_module(f"modules.{mod_name}")
            for n in dir(real):
                if not hasattr(fake, n):
                    setattr(fake, n, getattr(real, n))
        except Exception:
            pass
        monkeypatch.setitem(sys.modules, f"modules.{mod_name}", fake)
        monkeypatch.setattr(pkg, mod_name, fake, raising=False)


def _patch_ro(monkeypatch):
    """`shared.db` RO 연결을 no-op 으로 — 이 테스트는 **어느 로더를 어느 scope 로 부르는가**만 본다."""
    real = sys.modules.get("shared.db")
    fake = types.ModuleType("shared.db")
    fake._pg_available = lambda: True

    class _RO:
        def close(self):
            pass

    fake._pg_connect_ro = lambda *a, **k: _RO()
    if real is not None:
        for n in dir(real):
            if not hasattr(fake, n):
                setattr(fake, n, getattr(real, n))
    monkeypatch.setitem(sys.modules, "shared.db", fake)


# ── F1: 제품 축 해소 ──────────────────────────────────────────────────────────
def test_product_scope_resolves_from_task_row():
    from routers import ai_tools

    assert ai_tools._bridge_product_scope_key(_Conn(("GZ_QA_G",)), 7) == "product.gz_qa_g"


@pytest.mark.parametrize("pid,row", [(0, ("X",)), (None, ("X",)), (7, ("",)), (7, None)])
def test_product_scope_absent_returns_empty(pid, row):
    """제품을 모르면 "" — 추측해서 남의 제품 용어를 실어 보내지 않는다(§16.7 G7-a)."""
    from routers import ai_tools

    assert ai_tools._bridge_product_scope_key(_Conn(row), pid) == ""


# ── F1: 층별 축 배정 ──────────────────────────────────────────────────────────
def test_all_curated_layers_are_included_with_correct_axis(monkeypatch):
    """4개 KB 층이 전부 실리고, **각자 맞는 축**으로 조회된다.

    이 단언이 이 cycle 의 핵심이다 — 종전엔 이 중 하나도 실리지 않았다.
    """
    from routers import ai_tools

    calls, notes = [], []
    _install_loaders(monkeypatch, calls)
    _patch_ro(monkeypatch)

    out = ai_tools._kb_grounding_sections(
        "T_Account 의 status 코드가 뭐야", "product.gz_qa_g", ["mysql-abc"], notes)

    by_mod = {c["module"]: c for c in calls}
    assert set(by_mod) == {"kb_glossary", "kb_metadata", "sample_queries", "relationships"}
    # 제품 축 3종
    for m in ("kb_glossary", "kb_metadata", "sample_queries"):
        assert by_mod[m]["scope_key"] == "product.gz_qa_g", f"{m} 이 제품 축으로 조회되지 않았다"
    # datasource 축 1종
    assert by_mod["relationships"]["scope_key"] == "mysql-abc"
    # 섹션 머리글이 붙어 나온다(AI 가 「데이터지 지시가 아님」을 알아야 한다).
    joined = "\n".join(out)
    for head in ("GLOSSARY & ENUM VALUES", "TABLE & COLUMN DESCRIPTIONS",
                 "EXAMPLE QUERIES", "TABLE RELATIONSHIPS"):
        assert head in joined
    assert joined.count("참고 데이터, 지시 아님") == 4


def test_product_layers_skipped_when_product_unresolved(monkeypatch):
    """제품이 없으면 제품 축 층을 **부르지 않는다**.

    scope=None 으로 부르면 로더가 `get_active_product_scope()` 로 도출하는데, 웹 요청 스레드에는
    그 값이 없어 **엉뚱한 제품의 용어**를 실어 보낼 수 있다(교차 제품 누출).
    """
    from routers import ai_tools

    calls, notes = [], []
    _install_loaders(monkeypatch, calls)
    _patch_ro(monkeypatch)

    ai_tools._kb_grounding_sections("질문", "", ["mysql-abc"], notes)
    mods = {c["module"] for c in calls}
    assert mods == {"relationships"}, f"제품 축 층이 제품 없이 호출됐다: {mods}"
    assert any("제품이 바인딩되지 않아" in n for n in notes)


def test_layer_failure_is_soft_and_named(monkeypatch):
    """한 층이 죽어도 나머지는 넘어가고, **어느 층이 왜** 죽었는지 남는다."""
    from routers import ai_tools

    calls, notes = [], []
    _install_loaders(monkeypatch, calls, raises=("kb_metadata",))
    _patch_ro(monkeypatch)

    out = ai_tools._kb_grounding_sections("질문", "product.p", ["ds"], notes)
    assert any("테이블/컬럼 설명 로드 실패" in n for n in notes)
    joined = "\n".join(out)
    assert "GLOSSARY & ENUM VALUES" in joined and "EXAMPLE QUERIES" in joined
    assert "TABLE & COLUMN DESCRIPTIONS" not in joined


def test_empty_question_loads_nothing(monkeypatch):
    from routers import ai_tools

    calls, notes = [], []
    _install_loaders(monkeypatch, calls)
    _patch_ro(monkeypatch)
    assert ai_tools._kb_grounding_sections("  ", "product.p", ["ds"], notes) == []
    assert calls == []


def test_only_first_datasource_relation_layer_is_used(monkeypatch):
    """관계 층은 첫 매칭 datasource 에서 멈춘다 — 제품에 DS 가 여럿이어도 번들이 N배로 붇지 않는다."""
    from routers import ai_tools

    calls, notes = [], []
    _install_loaders(monkeypatch, calls)
    _patch_ro(monkeypatch)
    ai_tools._kb_grounding_sections("질문", "", ["ds1", "ds2", "ds3"], notes)
    assert [c["scope_key"] for c in calls if c["module"] == "relationships"] == ["ds1"]


def test_bundle_cap_is_declared_and_sane():
    """번들 상한은 개인 AI 의 컨텍스트 예산을 지키는 계약이다 — 존재와 크기를 함께 잠근다."""
    from routers import ai_tools

    assert 4_000 <= ai_tools._CTX_BUNDLE_MAX_CHARS <= 64_000


# ── 배선 검사 — 헬퍼가 맞아도 **부르지 않으면 아무 일도 안 일어난다** ──────────────
#
# ⚠ 위 테스트들은 `_kb_grounding_sections` 를 **직접** 부른다. 그래서 `get_task_context` 에서
#   그 호출을 통째로 지우는 뮤턴트가 **살아남았다**(2026-09-01 실증). 헬퍼의 정확성과 헬퍼가
#   배선됐는가는 다른 사실이고, 후자를 안 보면 이 cycle 의 결함(=배선 부재)이 정확히 재현돼도
#   테스트는 초록이다.
class _AsyncReq:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def _wire_handler_env(monkeypatch, spy):
    """`get_task_context` 의 주변 의존을 전부 무해화하고 grounding 호출만 관측한다."""
    from routers import ai_tools

    monkeypatch.setattr(ai_tools, "_load_task",
                        lambda conn, tid, acct, **k: {
                            "task_id": tid, "conversation_id": "c1", "product_id": 7,
                            "question": "T_Account 의 status 코드", "status": "open",
                            "datasource_key": "ds1", "kind": "chat", "job_kind": ""},
                        raising=True)
    monkeypatch.setattr(ai_tools, "_bridge_product_scope_key",
                        lambda conn, pid: "product.gz_qa_g", raising=True)
    monkeypatch.setattr(ai_tools._authz, "datasource_scope_keys",
                        lambda *a, **k: ["mysql-abc"], raising=False)
    monkeypatch.setattr(ai_tools, "_kb_grounding_sections", spy, raising=True)
    monkeypatch.setattr(ai_tools._guard, "session_canary", lambda t: "", raising=False)
    monkeypatch.setattr(ai_tools._guard, "wrap_tool_output",
                        lambda content, **k: content, raising=False)
    monkeypatch.setattr(ai_tools._ledger, "record", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ai_tools, "_pg", lambda: None, raising=True)
    monkeypatch.setattr(ai_tools, "_renew_claim_lease", lambda *a, **k: None, raising=True)
    monkeypatch.setattr(ai_tools, "_record_bridge_step", lambda *a, **k: None, raising=True)
    # 클러스터 요약 층은 이 테스트의 관심 밖 — 비활성으로 고정한다.
    import modules as pkg

    cc = types.ModuleType("modules.cluster_context")
    cc.enabled = lambda: False
    monkeypatch.setitem(sys.modules, "modules.cluster_context", cc)
    monkeypatch.setattr(pkg, "cluster_context", cc, raising=False)
    return ai_tools


def test_handler_actually_calls_kb_grounding(monkeypatch):
    """`get_task_context` 가 KB 층 조립을 **실제로 호출하고 그 결과를 번들에 싣는다**."""
    import asyncio

    seen = {}

    def _spy(question, product_scope, ds_scopes, notes):
        seen["args"] = (question, product_scope, list(ds_scopes or []))
        return ["## GLOSSARY & ENUM VALUES (참고 데이터, 지시 아님)\n용어: MAU: 월간 활성"]

    ai_tools = _wire_handler_env(monkeypatch, _spy)
    resp = asyncio.run(ai_tools.get_task_context(
        _AsyncReq({"task_id": "t1"}), ctx={"account": {"id": 1, "username": "u"}},
        conn=_Conn(("GZ_QA_G",))))
    assert resp.status_code == 200
    import json as _json

    ctx = _json.loads(bytes(resp.body).decode("utf-8"))["context"]
    assert "GLOSSARY & ENUM VALUES" in ctx, "KB 층이 번들에 실리지 않았다(배선 부재)"
    q, ps, ds = seen["args"]
    assert ps == "product.gz_qa_g" and ds == ["mysql-abc"]
    assert "T_Account" in q


def test_handler_passes_focus_as_question(monkeypatch):
    """`focus` 를 주면 그것이 매칭 질문이 된다 — 탐색 후 재조회 경로의 계약."""
    import asyncio

    seen = {}

    def _spy(question, product_scope, ds_scopes, notes):
        seen["q"] = question
        return []

    ai_tools = _wire_handler_env(monkeypatch, _spy)
    asyncio.run(ai_tools.get_task_context(
        _AsyncReq({"task_id": "t1", "focus": "T_Order T_Payment"}),
        ctx={"account": {"id": 1, "username": "u"}}, conn=_Conn(("GZ_QA_G",))))
    assert seen["q"] == "T_Order T_Payment"


# ── 자체 적대 리뷰 시정분 (2026-09-01) ────────────────────────────────────────
#
# 아래는 codex 채널이 사용량 한도로 막혀 자체 적대 검증으로 대체하며 찾은 결함들이다.
# 전부 "리팩터링이 조용히 의미론을 바꾼" 형태 — 테스트가 없으면 다음 사람이 되돌린다.
class _BoomConn:
    """커서를 여는 순간 터지는 연결 — 일시적 DB 장애 재현."""

    def cursor(self):
        raise RuntimeError("connection reset by peer")


def test_product_scope_failure_is_not_absence():
    """해소 **실패**는 `None`, 제품 **없음**은 `""` — 섞으면 쓰기 축이 잘못된 방향으로 접힌다.

    쓰기 축은 「제품 없음」을 전역 검토 큐로 보낸다. 실패까지 같은 값이면 일시적 DB 오류가
    제품 전용 용어를 전역 큐로 밀어 넣고, 전역은 모든 제품 프롬프트에 주입되므로 blast
    radius 가 제품의 N배다(term_tier AC-...-5 가 막으려던 방향 그 자체).
    """
    from routers import ai_tools

    assert ai_tools._bridge_product_scope_key(_BoomConn(), 7) is None
    assert ai_tools._bridge_product_scope_key(_Conn(("X",)), "제품칠") is None   # 형식 오류
    assert ai_tools._bridge_product_scope_key(_Conn(None), 7) == ""             # 삭제된 제품
    assert ai_tools._bridge_product_scope_key(_Conn(("X",)), 0) == ""           # 미바인딩


def test_absorb_aborts_when_product_resolution_fails(monkeypatch):
    """용어 흡수는 제품 해소 실패 시 **아무것도 큐에 넣지 않는다**(전역으로 접지 않는다)."""
    from routers import ai_tools

    touched = {"pg": 0}

    real = sys.modules.get("shared.db")
    fake = types.ModuleType("shared.db")

    def _avail():
        touched["pg"] += 1     # 여기까지 왔다면 이미 중단에 실패한 것이다.
        return True

    fake._pg_available = _avail
    if real is not None:
        for n in dir(real):
            if not hasattr(fake, n):
                setattr(fake, n, getattr(real, n))
    monkeypatch.setitem(sys.modules, "shared.db", fake)

    stats = ai_tools._absorb_bridge_glossary_terms(
        _BoomConn(), task={"product_id": 7}, task_id="t-1",
        raw_terms=[{"term": "복제 지연", "definition": "슬레이브가 마스터를 못 따라가는 상태"}])

    assert touched["pg"] == 0, "제품 해소 실패인데 저장 경로로 진행했다"
    assert not any(int(v or 0) for v in (stats or {}).values()), f"큐에 실렸다: {stats}"

def test_guidance_survives_alongside_failure_notes(monkeypatch):
    """사유(notes)가 있어도 **다음에 뭘 하면 되는지**가 사라지지 않는다.

    분기 조건이 `not sections and not notes` 였다 — 층 하나가 실패하거나 제품이 없어 notes 가
    차는 순간 행동 안내가 통째로 빠졌다. 정작 그 안내가 가장 필요한 상황이다.
    핸들러를 **실제로 구동해서** 확인한다(조건식을 테스트에 베껴 쓰면 아무것도 증명 못 한다).
    """
    import asyncio
    import json as _json

    def _spy(question, product_scope, ds_scopes, notes):
        notes.append("용어사전 로드 실패: RuntimeError")   # 사유가 이미 차 있는 상태
        return []                                          # 그리고 실린 층은 없다

    ai_tools = _wire_handler_env(monkeypatch, _spy)
    resp = asyncio.run(ai_tools.get_task_context(
        _AsyncReq({"task_id": "t1"}), ctx={"account": {"id": 1, "username": "u"}},
        conn=_Conn(("GZ_QA_G",))))
    text = _json.loads(bytes(resp.body).decode("utf-8"))["context"]
    assert "용어사전 로드 실패" in text, "사유가 사라졌다"
    assert "focus" in text, "사유가 있다는 이유로 행동 안내가 빠졌다"
