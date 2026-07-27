"""feature-0026 (M2) — 워커/헬퍼 LLM 호출의 latency_ms 백필 검증.

배경: `_record_llm_usage` 호출부 13곳(validate/summary/classify/topic/glossary_suggest/
enum_suggest/sql_fix/schema_insight/table_insight/account_insight/node_analysis/
product_classify/cluster_label)이 latency_ms 를 전달하지 않아 `llm_usage.latency_ms` 가
NULL — 백그라운드 LLM p50/p95 산출 불가(계측 사각)였다. M2 가 전 호출부에 perf_counter_ns
왕복 측정을 추가했다. 본 테스트는 대표 4형(단일라인 2 + 멀티라인 target 2)에서
latency_ms 가 음이 아닌 int 로 전달되는지 계약을 고정한다.

실 LLM/PG 없이 monkeypatch — conftest.py 가 src path 추가.
"""

from __future__ import annotations

import pytest

from modules import llm


class _FakeUsage:
    prompt_tokens = 3
    completion_tokens = 2
    total_tokens = 5


class _FakeMsg:
    content = '{"summary": "ok", "terms": [], "labels": [], "suggestions": []}'


class _FakeChoice:
    message = _FakeMsg()


class _FakeResp:
    usage = _FakeUsage()
    model = "fake-served-model"
    choices = [_FakeChoice()]


class _FakeCompletions:
    def create(self, **kwargs):
        return _FakeResp()


class _FakeChat:
    completions = _FakeCompletions()


class _FakeClient:
    chat = _FakeChat()


@pytest.fixture
def captured(monkeypatch):
    calls: list[dict] = []

    def _capture(model, task, resp, **kwargs):
        calls.append({"model": model, "task": task, **kwargs})

    monkeypatch.setattr(llm, "_get_llm_client", lambda *a, **k: _FakeClient())
    monkeypatch.setattr(llm, "_record_llm_usage", _capture)
    return calls


def _assert_latency(calls, task):
    rows = [c for c in calls if c["task"] == task]
    assert rows, f"task={task} 호출 미기록"
    lat = rows[0].get("latency_ms")
    assert isinstance(lat, int) and lat >= 0, f"task={task} latency_ms={lat!r}"


def test_summary_records_latency(captured):
    llm.llm_update_summary({"k": "v"})
    _assert_latency(captured, "summary")


def test_glossary_suggest_records_latency(captured):
    llm.llm_glossary_suggest({"user_message": "u", "assistant_answer": "a"})
    _assert_latency(captured, "glossary_suggest")


def test_node_analysis_records_latency_and_target(captured):
    llm.llm_node_analysis({"fqn": "s.t", "label": "Table"})
    _assert_latency(captured, "node_analysis")
    assert captured[0].get("target") == "s.t"  # 기존 target 계약 보존


def test_cluster_label_records_latency(captured):
    llm.llm_cluster_label({"datasource": "ds1", "clusters": []})
    _assert_latency(captured, "cluster_label")
