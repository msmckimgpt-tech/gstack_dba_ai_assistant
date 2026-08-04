"""FR-summary-writer-disconnected — 대화 요약(`agent_runtime.summary`) writer 배선 회귀 가드.

배경(라이브 실측 2026-08-04): `modules/llm.py` 의 `_refresh_summary_after_step` /
`_refresh_summary_after_ask` 는 삭제된 `agent_cli.py`(커밋 68ed7a76, 2026-06-02)에서만
호출됐고, 그 뒤로 web/worker 어느 경로에서도 호출자가 없었다. 결과:

  - `save_memory_summary()` 미실행 → `agent_runtime.summary` 0행(대화 296건 기준)
  - 그 테이블을 접지원으로 읽는 **제품·역할·개인 시스템 프롬프트 자동작성**의
    "실제 분석 사례 요약" 블록이 한 번도 생성되지 않음(`meta.summary_count` 항상 0)
  - 호출자가 0 이라 `_refresh_summary_after_*` 안의 미해소 전역(NameError)도 드러나지 않음

본 테스트는 그 두 결함을 각각 고정한다:
  T1  `refresh_conversation_summary` 가 요약을 실제로 저장한다(happy path).
  T2  AGENT_SUMMARY_REFRESH=0 이면 LLM·저장 모두 미수행(운영자 스위치 존중).
  T3  LLM 이 빈 결과를 주면 저장하지 않는다(빈 요약 덮어쓰기 금지).
  T4  내부 예외는 호출측으로 전파되지 않는다(fail-open — 답변 경로 차단 금지).
  T5  `agent_core.run_post_answer_curation` 이 요약 갱신을 **호출한다** — 배선 자체의 가드.
      (이 단언이 없으면 함수만 남고 호출자가 사라지는 원래 결함이 그대로 재발한다.)
  T6  `_refresh_summary_after_step` 의 타 모듈 심볼이 해소된다(NameError 재발 방지).

`make test`(agent 이미지, --no-deps)에서 DB·LLM 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from modules import llm as llm_mod  # noqa: E402
import agent_core  # noqa: E402


@pytest.fixture
def stub_deps(monkeypatch):
    """`_summary_deps` 가 돌려주는 타 모듈 심볼을 전부 가짜로 대체한다."""
    saved: list = []
    timings: list = []

    def _load_memory_context(conn, cid, max_turns):
        return ("이전 요약", [("user", "안녕", "2026-08-04T00:00:00")], {"topic": "T"})

    def _save_memory_summary(conn, cid, summary):
        saved.append((cid, summary))

    deps = {
        "load_memory_context": _load_memory_context,
        "save_memory_summary": _save_memory_summary,
        "_record_step_summary": lambda conn, cid, text: None,
        "sanitize_user_text": lambda t: t,
        "log_timing": lambda ev, data: timings.append((ev, data)),
        "_near_run_deadline": lambda *a, **k: False,
    }
    monkeypatch.setattr(llm_mod, "_summary_deps", lambda: deps)
    return {"saved": saved, "timings": timings}


# ── T1 happy path ───────────────────────────────────────────────────────────────

def test_refresh_conversation_summary_saves(monkeypatch, stub_deps):
    monkeypatch.setattr(llm_mod, "AGENT_SUMMARY_REFRESH", True, raising=False)
    monkeypatch.setattr(llm_mod, "llm_update_summary", lambda payload: "새 요약")

    assert llm_mod.refresh_conversation_summary("conv-1", last_step_summary="ask=hi") is True
    assert stub_deps["saved"] == [("conv-1", "새 요약")]
    assert stub_deps["timings"] and stub_deps["timings"][0][0] == "summary_refresh"


# ── T2 운영자 스위치 ─────────────────────────────────────────────────────────────

def test_refresh_conversation_summary_respects_gate(monkeypatch, stub_deps):
    monkeypatch.setattr(llm_mod, "AGENT_SUMMARY_REFRESH", False, raising=False)

    def _boom(payload):
        raise AssertionError("gate=0 이면 LLM 을 호출하면 안 된다")

    monkeypatch.setattr(llm_mod, "llm_update_summary", _boom)
    assert llm_mod.refresh_conversation_summary("conv-1") is False
    assert stub_deps["saved"] == []


# ── T3 빈 결과는 저장 안 함 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("empty", ["", None])
def test_refresh_conversation_summary_skips_empty(monkeypatch, stub_deps, empty):
    monkeypatch.setattr(llm_mod, "AGENT_SUMMARY_REFRESH", True, raising=False)
    monkeypatch.setattr(llm_mod, "llm_update_summary", lambda payload: empty)
    assert llm_mod.refresh_conversation_summary("conv-1") is False
    assert stub_deps["saved"] == []


def test_refresh_conversation_summary_requires_cid(monkeypatch, stub_deps):
    monkeypatch.setattr(llm_mod, "AGENT_SUMMARY_REFRESH", True, raising=False)
    monkeypatch.setattr(llm_mod, "llm_update_summary", lambda payload: "x")
    assert llm_mod.refresh_conversation_summary("   ") is False
    assert stub_deps["saved"] == []


# ── T4 fail-open ────────────────────────────────────────────────────────────────

def test_refresh_conversation_summary_fail_open(monkeypatch, stub_deps):
    monkeypatch.setattr(llm_mod, "AGENT_SUMMARY_REFRESH", True, raising=False)

    def _raise(payload):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(llm_mod, "llm_update_summary", _raise)
    assert llm_mod.refresh_conversation_summary("conv-1") is False  # 예외 전파 없음


# ── T5 배선 가드 (핵심) ─────────────────────────────────────────────────────────

def test_post_answer_curation_invokes_summary_refresh(monkeypatch):
    """`run_post_answer_curation` 이 요약 갱신을 호출하는지 — 호출자 소멸 재발 방지.

    다른 큐레이션(topic/glossary/enum)은 no-op 으로 눌러 두고, 요약 호출만 관측한다.
    """
    calls: list = []
    monkeypatch.setattr(agent_core, "_writes_allowed", lambda conn, cid: True)
    monkeypatch.setattr(agent_core, "_try_update_topic", lambda *a, **k: None)
    monkeypatch.setattr(agent_core, "_glossary_autopropose", lambda *a, **k: None)
    monkeypatch.setattr(agent_core, "_enum_autopropose", lambda *a, **k: None)
    monkeypatch.setattr(agent_core, "save_memory_kv", lambda *a, **k: None)
    monkeypatch.setattr(
        agent_core, "_refresh_conversation_summary",
        lambda cid, **kw: calls.append((cid, kw)) or True,
    )

    agent_core.run_post_answer_curation({
        "conversation_id": "conv-42",
        "user_message": "접속 로그 집계해줘",
        "answer": "결과입니다",
        "history_len": 2,
        "run_id": "run-1",
    })

    assert len(calls) == 1, "run_post_answer_curation 이 요약 갱신을 호출해야 한다"
    cid, kw = calls[0]
    assert cid == "conv-42"
    assert "접속 로그 집계해줘" in str(kw.get("last_step_summary") or "")


def test_post_answer_curation_survives_summary_failure(monkeypatch):
    """요약 갱신이 던져도 큐레이션 전체가 fail-open 이어야 한다(답변 경로 무영향)."""
    monkeypatch.setattr(agent_core, "_writes_allowed", lambda conn, cid: True)
    monkeypatch.setattr(agent_core, "_try_update_topic", lambda *a, **k: None)
    monkeypatch.setattr(agent_core, "_glossary_autopropose", lambda *a, **k: None)
    monkeypatch.setattr(agent_core, "_enum_autopropose", lambda *a, **k: None)
    monkeypatch.setattr(agent_core, "save_memory_kv", lambda *a, **k: None)

    def _raise(cid, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent_core, "_refresh_conversation_summary", _raise)
    agent_core.run_post_answer_curation({
        "conversation_id": "conv-43", "user_message": "q", "answer": "a",
        "history_len": 0, "run_id": "r",
    })  # 예외 전파 없으면 통과


# ── T6 심볼 해소 (NameError 재발 방지) ──────────────────────────────────────────

def test_summary_deps_resolve():
    """`_summary_deps()` 가 요구 심볼을 전부 실제로 import 해 온다.

    이 함수 도입 전에는 `_refresh_summary_after_step` 이 `log_timing` /
    `load_memory_context` / `save_memory_summary` 등을 module 전역에서 찾았는데
    llm.py 는 그 어느 것도 import 하지 않아 **호출 즉시 NameError** 였다. 호출자가
    0 이라 테스트에도 안 잡혔다(§gate-hidden-call-test-blindspot).
    """
    d = llm_mod._summary_deps()
    for key in (
        "load_memory_context", "save_memory_summary", "_record_step_summary",
        "sanitize_user_text", "log_timing", "_near_run_deadline",
    ):
        assert callable(d[key]), f"{key} 가 해소되지 않았다"


def test_production_answer_paths_invoke_curation_hook():
    """실제 완료 경로 2곳이 `run_post_answer_curation` 을 호출하는지 소스로 고정 (codex P2).

    T5 는 "훅 안에서 요약을 부르는가" 를 잡지만, **그 훅을 부르는 생산 경로가 사라지는** 상위
    실패 모드는 못 잡는다 — 본 cycle 이 고치는 결함이 정확히 그 종류(호출자 소멸)였다.
    두 경로:
      - in-process: `agent_core._run_agent_core` 말미 (`defer_terminal_status=False` 분기)
      - worker:     `modules/ask.py` 의 job terminal 전이 직후
    AST 로 호출식을 세어 "함수는 남고 호출만 사라진" 상태를 실패시킨다.
    """
    import ast

    def _call_count(path: pathlib.Path, name: str) -> int:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        n = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id == name:
                    n += 1
                elif isinstance(fn, ast.Attribute) and fn.attr == name:
                    n += 1
        return n

    core = SRC_ROOT / "agent_core.py"
    worker = SRC_ROOT / "modules" / "ask.py"
    assert _call_count(core, "run_post_answer_curation") >= 1, (
        "in-process 답변 경로가 run_post_answer_curation 을 호출해야 한다"
    )
    assert _call_count(worker, "run_post_answer_curation") >= 1, (
        "ask-worker terminal 후 경로가 run_post_answer_curation 을 호출해야 한다"
    )
    # 훅 안에서 요약 갱신을 부르는지도 같은 방식으로 — 주석/문자열이 아닌 실제 호출식으로 확인.
    assert _call_count(core, "_refresh_conversation_summary") >= 1, (
        "run_post_answer_curation 이 요약 갱신을 호출해야 한다 (writer 재단절 방지)"
    )


def test_refresh_summary_after_step_does_not_raise_nameerror(monkeypatch, stub_deps):
    """레거시 진입점도 호출 가능해야 한다 — 죽은 채 남겨 두지 않는다."""
    monkeypatch.setattr(llm_mod, "AGENT_SUMMARY_REFRESH", True, raising=False)
    monkeypatch.setattr(llm_mod, "llm_update_summary", lambda payload: "레거시 요약")
    llm_mod._refresh_summary_after_step(None, "conv-9", "step summary", None)
    assert stub_deps["saved"] == [("conv-9", "레거시 요약")]
