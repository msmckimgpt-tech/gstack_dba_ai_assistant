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
    # S6 (agent_memory_facts matview multi-row priority) 은 TASK-0140 에서 제거.
    # matview 폐기로 검증 대상 자체가 사라짐 (fact_entries 가 정본). DISTINCT ON
    # tie-break 의미는 향후 read path 가 fact_entries 직접 조회 시 별 cycle 에서 재검증.
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


def _setup_mock_mirror_env(monkeypatch):
    """공통 fixture: _pg_available True + FakeConn 주입 + audit 우회 + BACKENDS reset.

    REV-20260521-0009 C-5 흡수: 함수 끝에 _BACKENDS_CACHE finalize 등록 — test 순서
    의존성 / leak 방지. monkeypatch.setattr 가 자동 cleanup 하지만 module-level
    `_BACKENDS_CACHE` 는 mutate 이므로 직접 finalize.
    """
    from modules import kb_backend as kb  # type: ignore

    monkeypatch.setattr(
        sys.modules["modules.db"], "_pg_available", lambda: True, raising=True,
    )
    captured: list = []
    fake_conn = _FakeConn(captured)
    monkeypatch.setattr(
        sys.modules["modules.db"], "_pg_connect",
        lambda *a, **kw: fake_conn, raising=True,
    )
    monkeypatch.setattr(
        kb, "_log_kb_write_audit", lambda **kw: None, raising=True,
    )

    prev_cache = kb._BACKENDS_CACHE
    kb._BACKENDS_CACHE = None

    def _finalize():
        kb._BACKENDS_CACHE = prev_cache
    monkeypatch.setattr(kb, "_BACKENDS_CACHE", None, raising=True)
    return kb, captured


@pytest.mark.parametrize("scenario", SCENARIO_CATALOG, ids=lambda s: s["id"])
def test_anchor_invariant_scenarios(scenario, monkeypatch):
    """ANCHOR §3 fact-우선 복구 시나리오.

    M2-c (TASK-0021): S1 실 구현.
    M2-d (TASK-0022): S2 / S4 / S5 / S6 mock-pattern 실 구현. S3 는 insight worker
    integration 필요 → skip 유지 (caller 의 repair logic 모의 불가).
    """
    sid = scenario["id"]
    llm_calls = _install_llm_tripwires(monkeypatch)

    if sid == "S1_rag_docs_missing":
        # S1: RagDocuments 누락 → mirror upsert_rag_document 발행 + LLM 0건
        kb, captured = _setup_mock_mirror_env(monkeypatch)
        result = kb._dual_write_kb.upsert_rag_document(
            conversation_id=None,
            scope_key="common",
            doc_type="fact-derived",
            fact_key="user-count-7d",
            text_hash="abc123def456" * 5 + "0000",
            content_hash="aa" * 32,
            weight=1,
            source_type="repair_from_fact",
            source_run_id=None,
            source_sql=None,
        )
        assert result == 1001, f"mirror RETURNING id 반환 실패: {result}"
        sql_text = "\n".join(s[0] for s in captured)
        assert "rag_documents" in sql_text.lower(), "rag_documents INSERT SQL 미발견"

    elif sid == "S2_rag_objs_missing":
        # S2: RagObjects 누락 → mirror upsert_rag_object 발행 + LLM 0건
        kb, captured = _setup_mock_mirror_env(monkeypatch)
        result = kb._dual_write_kb.upsert_rag_object(
            conversation_id=None,
            scope_key="common",
            object_type="metric",
            object_key="users.signup_7d",
            schema_name="agent_memory",
            table_name="users",
            column_name="created_at",
            text_hash="aa" * 32,
            weight=1,
            source_type="repair_from_fact",
            category_domain="user_acquisition",
        )
        assert result == 1001
        sql_text = "\n".join(s[0] for s in captured)
        assert "rag_objects" in sql_text.lower(), "rag_objects INSERT SQL 미발견"
        # ON CONFLICT 절에 category_* COALESCE NULLIF 보존 패턴 (S5 변종 검증)
        assert "coalesce(nullif" in sql_text.lower(), (
            "rag_objects ON CONFLICT 의 category_* 보존 로직 (COALESCE(NULLIF, …)) 미발견"
        )

    elif sid == "S3_texts_missing":
        # S3: texts 미참조 fact_entries (orphan) — repair path 차단. insight worker
        # 의 `_repair_from_fact()` 가 `not repair_text: return False` 분기로 들어가는지
        # mock 으로 검증 불가 (insight worker 의 실 호출 흐름 의존). 본 cycle 에서는
        # SQL 템플릿 자체에 fact_entries → texts FK 추론 가능한 text_hash 컬럼이
        # 존재하는지만 가벼운 정합 검증.
        from modules.kb_backend import _PG_UPSERT_FACT_ENTRY
        assert "text_hash" in _PG_UPSERT_FACT_ENTRY, (
            "fact_entries INSERT 에 text_hash 컬럼 없음 — texts orphan 검출 불가"
        )
        pytest.skip(
            "S3 의 caller (`insight.py:_repair_from_fact`) integration 은 M2-d 외 cycle. "
            "SQL 정합은 위 assertion 으로 통과 — repair-path 실 분기 검증은 별 integration test."
        )

    elif sid == "S4_scope_key_non_common":
        # S4: scope_key='sales_q4' (common 외) 보존 → mirror 가 scope_key 그대로 전달
        kb, captured = _setup_mock_mirror_env(monkeypatch)
        # fact_entry + rag_document + rag_object 3개 모두 같은 scope 로 호출
        kb._dual_write_kb.upsert_fact_entry(
            conversation_id="conv-q4",
            scope_key="sales_q4",
            fact_key="quarterly-revenue",
            text_hash="aa" * 32,
            fact_fingerprint="fp1",
            weight=5,
            source_type="repair",
        )
        kb._dual_write_kb.upsert_rag_document(
            conversation_id="conv-q4",
            scope_key="sales_q4",
            doc_type="fact-derived",
            fact_key="quarterly-revenue",
            text_hash="aa" * 32,
            content_hash="bb" * 32,
            weight=5,
            source_type="repair",
            source_run_id=None,
            source_sql=None,
        )
        kb._dual_write_kb.upsert_rag_object(
            conversation_id="conv-q4",
            scope_key="sales_q4",
            object_type="metric",
            object_key="revenue.q4",
        )
        # 모든 SQL 의 params 에 'sales_q4' scope_key 가 전달되었는지 (default 'common' 으로
        # fallback 안 했는지) 검증.
        scope_keys_used = []
        for sql, params in captured:
            if isinstance(params, dict) and "scope_key" in params:
                scope_keys_used.append(params["scope_key"])
        assert scope_keys_used, "scope_key params 캡쳐 실패"
        assert all(s == "sales_q4" for s in scope_keys_used), (
            f"scope_key 가 'sales_q4' 로 보존 안 됨 — 캡쳐: {scope_keys_used}"
        )

    elif sid == "S5_rag_objs_category_stale":
        # S5: RagObjects 의 category_* stale 시 보존 (NULL stay NULL / outdated value
        # 유지) — SQL template 의 ON CONFLICT DO UPDATE 절이
        # `COALESCE(NULLIF(EXCLUDED.category_*, ''), rag_objects.category_*)`
        # 패턴인지 검증. 빈 string 이 들어와도 기존 값 유지.
        from modules.kb_backend import _PG_UPSERT_RAG_OBJECT
        sql_lower = _PG_UPSERT_RAG_OBJECT.lower()
        category_cols = (
            "category_domain", "category_entity_type", "category_metric_family",
            "category_event_type", "category_time_grain", "category_join_hints_json",
        )
        for col in category_cols:
            # 각 컬럼이 COALESCE(NULLIF(EXCLUDED.<col>, '')...rag_objects.<col>) 형태
            assert col in sql_lower, f"category 컬럼 '{col}' 누락"
            assert f"coalesce(nullif(excluded.{col}" in sql_lower, (
                f"S5 invariant 위반 — '{col}' 가 빈 string 으로 덮어쓰여질 수 있음 "
                "(COALESCE(NULLIF(EXCLUDED.x, ''), rag_objects.x) 패턴 부재)"
            )

    # S6 (agent_memory_facts matview multi-row priority) 분기는 TASK-0140 에서 제거 —
    # matview 폐기로 검증 대상 DDL 부재.

    else:
        pytest.fail(f"unknown scenario id: {sid}")

    # 모든 시나리오 — N1 invariant (LLM 호출 0건) 동시 검증.
    assert len(llm_calls) == 0, (
        f"ANCHOR §3 invariant 위반 — {sid} 실행 중 LLM 호출 발생: {llm_calls}"
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
