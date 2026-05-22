"""ANCHOR §3 invariant 시나리오 카탈로그 — Postgres KB 측에서의 fact-우선 복구 검증.

TASK-0015 §2.1.6 + outside-voice review `REV-20260520-0005` Section C Blocker:
"fact 기반 복구 시나리오 1건 → 6종 카탈로그 (RagDocs 누락 / RagObjs 누락 / Texts
누락 / ScopeKey common 외 / RagObjs category stale / fact_entries 다중 row 우선
순위) 자동화 + LLM 호출 0건 negative assertion".

M2-c cycle (TASK-0021) 실 구현 범위:
- **S1 (RagDocuments 누락)**: 실 구현 — mirror upsert_rag_document 호출 시 Postgres
  INSERT SQL 발행 + LLM 호출 0건 확인 (FakeConn 으로 INSERT 캡쳐).
- **N1 (LLM 호출 0건)**: 실 구현 — `openai.OpenAI().chat.completions.create` 및
  `modules.llm_api` 의 entry point 를 monkeypatch 하여 invocation 발생 시 fail.
- **N2 (TRUNCATE denied)**: env-gated integration test —
  `AGENT_KB_PG_INTEGRATION_TEST=1` 시 실 Postgres 접속 + `agent_kb_rw` 로
  `TRUNCATE TABLE fact_entries` 시도 → `InsufficientPrivilege` raise 확인.

S2~S6 는 M2-d cycle 책임 (실 DB fixture + insight worker 호출 통합 필요).

ANCHOR §3 invariant 본문 (feature-0002 ANCHOR.md):
> insight-worker 의 기존 복구 로직을 건드려야 할 때: 새 AI 세션이 REPORT.md 를
> 읽으면 `fact/RAG/Text/Object 4종 완전성 확인 → 기존 fact 기반 복구 가능 시 즉시
> 복구 → 복구 불가 시에만 LLM 재생성` 순서가 명시되어 있다. 이 순서를 뒤집으면
> LLM 호출 비용이 폭발한다.
"""

from __future__ import annotations

import os
import sys

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 시나리오 카탈로그 (outside-voice REV-20260520-0005 Section C 권고)
# ─────────────────────────────────────────────────────────────────────────────

SCENARIO_CATALOG = [
    {
        "id": "S1_rag_docs_missing",
        "name": "RagDocuments 누락 → repair_from_fact 가 RagDocuments 재생성",
        "setup": "fact_entries 에 row 1개 + texts 에 text_hash 매칭 row 1개 + RagDocuments / RagObjects 미존재",
        "expected": "insight._repair_from_fact() 가 RagDocuments INSERT + LLM 호출 0건",
        "ddl_table_focus": ["fact_entries", "texts", "rag_documents"],
    },
    {
        "id": "S2_rag_objs_missing",
        "name": "RagObjects 누락 → repair_from_fact 가 RagObjects 재생성",
        "setup": "fact_entries + texts + RagDocuments 정합 + RagObjects 만 미존재",
        "expected": "insight._repair_from_fact() 가 RagObjects INSERT + LLM 호출 0건",
        "ddl_table_focus": ["rag_objects"],
    },
    {
        "id": "S3_texts_missing",
        "name": "Texts 누락 → repair_from_fact 가 차단 + 명시 로그",
        "setup": "fact_entries 의 text_hash 가 texts 미참조 (orphan)",
        "expected": "insight._repair_from_fact() 가 `not repair_text: return False` path 진입 + insight_route.log 에 `texts_missing` action 기록",
        "ddl_table_focus": ["texts"],
    },
    {
        "id": "S4_scope_key_non_common",
        "name": "ScopeKey 가 common 외 (사용자 정의 scope) → repair 가 ScopeKey 보존",
        "setup": "fact_entries.scope_key = 'sales_q4' (common 외) + 나머지 정합",
        "expected": "RagDocuments / RagObjects 의 scope_key 가 'sales_q4' 로 보존 (default 'common' 으로 fallback 안 함)",
        "ddl_table_focus": ["fact_entries", "rag_documents", "rag_objects"],
    },
    {
        "id": "S5_rag_objs_category_stale",
        "name": "RagObjects 의 category_* stale → repair 후 카테고리 보존 또는 갱신",
        "setup": "RagObjects 에 row 존재 + category_domain 등 컬럼 NULL 또는 outdated value",
        "expected": "repair 후 category_* 가 보존 (NULL 유지) 또는 명시적 갱신 정책 따라 갱신 — 본 cycle 의 결정: **보존 (NULL stay NULL)**. category 갱신은 별 cycle 의 책임 (RagObjects category re-classification 의 별 ADR 후보).",
        "ddl_table_focus": ["rag_objects"],
    },
    {
        "id": "S6_fact_entries_multi_row_priority",
        "name": "fact_entries 다중 row → weight DESC, updated_at DESC, id DESC 우선순위",
        "setup": "동일 (conv, scope, fact_key) 에 fact_entries row 3개 — (weight=5, updated_at=t1, id=10), (weight=5, updated_at=t2 > t1, id=20), (weight=7, updated_at=t0 < t1, id=5)",
        "expected": "agent_memory_facts VIEW 가 (weight=7, id=5) row 선택. weight 최우선, 동률 시 updated_at 최신, 동률 시 id 최신.",
        "ddl_table_focus": ["fact_entries", "agent_memory_facts"],
    },
]

NEGATIVE_ASSERTIONS = [
    {
        "id": "N1_llm_call_zero",
        "name": "repair_from_fact path 진입 시 LLM 호출 0건 (negative assertion)",
        "setup": "S1 시나리오 실행 중 LLM API entry point monkeypatch",
        "expected": "openai.OpenAI().chat.completions.create / modules.llm_api 의 호출 0회",
    },
    {
        "id": "N2_no_truncate",
        "name": "agent_kb_rw role 이 TRUNCATE 권한 부재 — application 이 KB 통째로 비우지 못함",
        "setup": "agent_kb_rw 로 connect + `TRUNCATE TABLE fact_entries`",
        "expected": "psycopg.errors.InsufficientPrivilege raise",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — FakeConn / Cursor + LLM monkeypatch
# ─────────────────────────────────────────────────────────────────────────────


class _FakeCursor:
    """SQL 실행 캡쳐 + RETURNING id 모의."""

    def __init__(self, captured: list, returning_id: int = 1001):
        self._captured = captured
        self._returning_id = returning_id
        self._last_was_returning = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._captured.append((sql, params))
        self._last_was_returning = "RETURNING id" in sql

    def fetchone(self):
        if self._last_was_returning:
            return (self._returning_id,)
        return None


class _FakeConn:
    def __init__(self, captured: list):
        self._captured = captured

    def cursor(self):
        return _FakeCursor(self._captured)

    def close(self):
        pass


def _install_llm_tripwires(monkeypatch) -> list:
    """LLM entry point 들을 monkeypatch 하여 호출 시 record + AssertionError raise.

    outside-voice REV-20260521-0009 B-2 흡수: 실제 LLM 모듈은 `modules.llm` 이며
    (`modules.llm_api` 는 존재하지 않음), 또한 `modules.llm` 이 `from openai import
    OpenAI` 로 이미 module-local 에 binding 된 후이므로 `openai.OpenAI` 만 patch 해도
    이미 import 된 caller 는 영향 받지 않는다. `modules.llm.OpenAI` 자체 + 호출 entry
    point 들 (`_get_openai_client`, `_openai_chat_completion_with_deadline`,
    `llm_*` prefix) 을 직접 patch 한다.

    Returns: 호출 기록 list (정상 path 는 비어있어야 함).
    """
    llm_calls: list = []
    installed: list = []

    def _trip(name):
        def _called(*args, **kwargs):
            llm_calls.append((name, args, kwargs))
            raise AssertionError(f"LLM 호출 발생: {name} — ANCHOR §3 invariant 위반")
        return _called

    # modules.llm 의 직접 entry point.
    try:
        from modules import llm as _llm  # type: ignore
    except ImportError:
        _llm = None

    if _llm is not None:
        # Low-level entry — 모든 chat completion 이 통과하는 함수.
        for fn_name in ("_get_openai_client", "_openai_chat_completion_with_deadline"):
            if hasattr(_llm, fn_name):
                monkeypatch.setattr(_llm, fn_name, _trip(f"modules.llm.{fn_name}"))
                installed.append(f"modules.llm.{fn_name}")

        # High-level llm_* entry — caller 가 직접 호출.
        for fn_name in dir(_llm):
            if fn_name.startswith("llm_") and callable(getattr(_llm, fn_name)):
                monkeypatch.setattr(_llm, fn_name, _trip(f"modules.llm.{fn_name}"))
                installed.append(f"modules.llm.{fn_name}")

        # OpenAI class — modules.llm.OpenAI 가 module-local binding 이므로 직접 교체.
        if hasattr(_llm, "OpenAI") and getattr(_llm, "OpenAI") is not None:
            class _TripOpenAI:
                def __init__(self, *a, **kw):
                    llm_calls.append(("modules.llm.OpenAI.__init__", a, kw))
                    raise AssertionError(
                        "LLM 호출 발생: modules.llm.OpenAI() — invariant 위반"
                    )
            monkeypatch.setattr(_llm, "OpenAI", _TripOpenAI)
            installed.append("modules.llm.OpenAI")

    # Smoke check — 적어도 하나의 entry point 가 patch 됐는지.
    # 0 개라면 modules.llm import 자체가 실패했거나 expected entry point 가 모두
    # 사라진 것 — 본 test 의 invariant 가 의미를 잃었음을 즉시 알린다.
    assert installed, (
        "LLM tripwire 가 하나도 설치되지 않음 — modules.llm 의 entry point 가 변경된 "
        "것으로 추정. _install_llm_tripwires() 갱신 필요."
    )

    return llm_calls


# ─────────────────────────────────────────────────────────────────────────────
# S1 + S2~S6 (parametrized)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("scenario", SCENARIO_CATALOG, ids=lambda s: s["id"])
def test_anchor_invariant_scenarios(scenario, monkeypatch):
    """ANCHOR §3 fact-우선 복구 시나리오.

    M2-c (TASK-0021) 범위: S1 만 실 구현. S2~S6 는 M2-d cycle 책임.
    """
    if scenario["id"] != "S1_rag_docs_missing":
        pytest.skip(f"{scenario['id']}: M2-d cycle 책임 (실 DB fixture 통합 필요)")

    # S1: RagDocuments 누락 → mirror 가 upsert_rag_document 호출 시 INSERT SQL 발행
    #     + 동시에 LLM 호출 0건 negative assertion (N1 의 한 axis).
    from modules import kb_backend as kb  # type: ignore

    monkeypatch.setattr(
        sys.modules["modules.db"],
        "_pg_available",
        lambda: True,
        raising=True,
    )

    captured: list = []
    fake_conn = _FakeConn(captured)
    monkeypatch.setattr(
        sys.modules["modules.db"],
        "_pg_connect",
        lambda *a, **kw: fake_conn,
        raising=True,
    )

    # Cross-DB audit 은 MySQL 접속을 시도 — 본 unit test 에서 우회.
    monkeypatch.setattr(
        kb,
        "_log_kb_write_audit",
        lambda **kw: None,
        raising=True,
    )

    kb._BACKENDS_CACHE = None

    # LLM tripwire 설치 — 호출 발생 시 AssertionError raise.
    llm_calls = _install_llm_tripwires(monkeypatch)

    # repair_from_fact path 의 핵심 동작: fact + text 만 있는 상태에서 caller
    # 가 RagDocuments 를 INSERT 시도 → mirror 가 Postgres upsert_rag_document 발행.
    # caller (insight worker) 의 실 호출 패턴: scope_key='common', doc_type='fact-derived'.
    result = kb._dual_write_kb.upsert_rag_document(
        conversation_id=None,
        scope_key="common",
        doc_type="fact-derived",
        fact_key="user-count-7d",
        text_hash="abc123def456" * 5 + "0000",  # 64 hex
        content_hash="aa" * 32,
        weight=1,
        source_type="repair_from_fact",
        source_run_id=None,
        source_sql=None,
    )

    # RETURNING id 의 모의 응답 확인
    assert result == 1001, f"mirror 가 RETURNING id 반환 실패: {result}"

    # rag_documents INSERT SQL 캡쳐 확인
    assert len(captured) >= 1, "Postgres mirror INSERT 가 발행되지 않음"
    sql_text = "\n".join(s[0] for s in captured)
    assert "rag_documents" in sql_text.lower(), (
        f"rag_documents INSERT SQL 미발견: captured={captured}"
    )

    # N1 의 핵심 — repair path 진입 중 LLM 호출 0건.
    assert len(llm_calls) == 0, (
        f"ANCHOR §3 invariant 위반 — LLM 호출 발생: {llm_calls}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# N1 + N2 (parametrized)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("assertion", NEGATIVE_ASSERTIONS, ids=lambda a: a["id"])
def test_anchor_invariant_negative(assertion, monkeypatch):
    """Negative assertion — LLM 호출 0건, TRUNCATE 차단."""
    if assertion["id"] == "N1_llm_call_zero":
        # S1 변형: mirror invocation 6종 (upsert_text + upsert_fact_entry +
        # upsert_rag_document + upsert_rag_object + delete + prune) 전부 실행 중
        # LLM 호출이 한 번도 발생하지 않음을 확인.
        from modules import kb_backend as kb  # type: ignore

        monkeypatch.setattr(
            sys.modules["modules.db"],
            "_pg_available",
            lambda: True,
            raising=True,
        )
        captured: list = []
        fake_conn = _FakeConn(captured)
        monkeypatch.setattr(
            sys.modules["modules.db"],
            "_pg_connect",
            lambda *a, **kw: fake_conn,
            raising=True,
        )
        monkeypatch.setattr(
            kb,
            "_log_kb_write_audit",
            lambda **kw: None,
            raising=True,
        )
        kb._BACKENDS_CACHE = None

        llm_calls = _install_llm_tripwires(monkeypatch)

        # 6 mirror method 모두 invoke — repair-style payload.
        kb._dual_write_kb.upsert_text(text_hash="h" * 64, text_content="t")
        kb._dual_write_kb.upsert_fact_entry(
            conversation_id=None, scope_key="common", fact_key="k",
            text_hash="h" * 64, weight=1, source_type="repair",
        )
        kb._dual_write_kb.upsert_rag_document(
            conversation_id=None, scope_key="common", doc_type="fact-derived",
            fact_key="k", text_hash="h" * 64, content_hash="c" * 64,
            weight=1, source_type="repair", source_run_id=None, source_sql=None,
        )
        kb._dual_write_kb.upsert_rag_object(
            conversation_id=None, scope_key="common",
            object_type="metric", object_key="users.signup_7d",
        )
        kb._dual_write_kb.delete_fact_entries_by_conv_scope_key(
            conversation_id=None, scope_key="common", fact_key="k",
        )
        # outside-voice REV-20260521-0009 B-3 흡수: prune 의 실제 PgKbBackend signature
        # 는 `conversation_id=, scope_key=, fact_key=, keep_limit=` — 이전 cycle 의
        # `keep_top=` kwarg 명 오타로 _mirror() 내부 silent swallow 가 발생, prune
        # path 가 실제로 invoke 되지 않았다.
        kb._dual_write_kb.prune_fact_entries_keep_top(
            conversation_id=None, scope_key="common", fact_key="k", keep_limit=10,
        )

        assert len(llm_calls) == 0, (
            f"N1 위반 — repair-style mirror 호출 중 LLM 발생: {llm_calls}"
        )

        # 6 mirror method 의 SQL 이 captured 에 실제 발행되었는지 — silent swallow
        # 회귀 방지 (REV-20260521-0009 B-3).
        sql_blob = "\n".join(s[0].lower() for s in captured)
        assert "insert" in sql_blob and ("texts" in sql_blob or "text" in sql_blob), (
            f"upsert_text SQL 미발견: captured count={len(captured)}"
        )
        assert "fact_entries" in sql_blob, "fact_entries 관련 SQL 미발견"
        assert "rag_documents" in sql_blob, "rag_documents SQL 미발견"
        assert "rag_objects" in sql_blob, "rag_objects SQL 미발견"
        assert "delete from fact_entries" in sql_blob, (
            "delete SQL 미발견 — delete_fact_entries_by_conv_scope_key path 미실행"
        )

    elif assertion["id"] == "N2_no_truncate":
        # 실 Postgres 접속이 필요한 integration test. AGENT_KB_PG_INTEGRATION_TEST=1
        # 환경에서만 실행 — 그 외엔 skip (unit test runner 의 default 환경 보호).
        if os.environ.get("AGENT_KB_PG_INTEGRATION_TEST") != "1":
            pytest.skip(
                "N2 는 실 Postgres 접속 필요 — AGENT_KB_PG_INTEGRATION_TEST=1 로 활성화"
            )

        try:
            import psycopg  # type: ignore
            from psycopg import errors as pg_errors  # type: ignore
        except ImportError:
            pytest.skip("psycopg 미설치 — N2 통합 테스트 skip")

        # agent_kb_rw 의 connection — bootstrap script 가 셋업한 role.
        conninfo = os.environ.get(
            "AGENT_KB_PG_RW_DSN",
            "host=postgres dbname=agent_memory user=agent_kb_rw password=change_me_rw",
        )
        with psycopg.connect(conninfo, autocommit=True) as conn:
            with conn.cursor() as cur:
                with pytest.raises(pg_errors.InsufficientPrivilege):
                    cur.execute("TRUNCATE TABLE fact_entries")
    else:
        pytest.fail(f"unknown negative assertion id: {assertion['id']}")


if __name__ == "__main__":
    import json
    print("=== ANCHOR §3 invariant 시나리오 catalog ===")
    print(json.dumps(SCENARIO_CATALOG, ensure_ascii=False, indent=2))
    print("\n=== Negative assertions ===")
    print(json.dumps(NEGATIVE_ASSERTIONS, ensure_ascii=False, indent=2))
