"""ANCHOR §3 invariant 시나리오 카탈로그 — Postgres KB 측에서의 fact-우선 복구 검증.

TASK-0015 §2.1.6 + outside-voice review `REV-20260520-0005` Section C Blocker:
"fact 기반 복구 시나리오 1건 → 6종 카탈로그 (RagDocs 누락 / RagObjs 누락 / Texts
누락 / ScopeKey common 외 / RagObjs category stale / fact_entries 다중 row 우선
순위) 자동화 + LLM 호출 0건 negative assertion".

본 파일은 M2 cycle (TASK-0019) 의 **skeleton 정본** — 시나리오 catalog 정의 +
test stub. 실 구현 (assertion + Postgres fixture + MysqlKbBackend / PgKbBackend
호출) 은 M2-b cycle 책임. 본 cycle 의 검증 항목은 시나리오 명세 + 의도 명확화.

ANCHOR §3 invariant 본문 (feature-0002 ANCHOR.md):
> insight-worker 의 기존 복구 로직을 건드려야 할 때: 새 AI 세션이 REPORT.md 를
> 읽으면 `fact/RAG/Text/Object 4종 완전성 확인 → 기존 fact 기반 복구 가능 시 즉시
> 복구 → 복구 불가 시에만 LLM 재생성` 순서가 명시되어 있다. 이 순서를 뒤집으면
> LLM 호출 비용이 폭발한다.

본 invariant 가 Postgres backend 에서도 동일 의미로 작동하는지 6종 시나리오로 검증.
"""

from __future__ import annotations

import pytest

# M2-b cycle 의 fixture (placeholder).
# 실 구현 시 docker-compose 의 repo-postgres-1 컨테이너에 임시 connection 열고
# fact_entries / texts / rag_documents / rag_objects 에 시나리오 데이터 INSERT.


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

# 추가 negative assertion: M2/M4 검증 게이트의 핵심.
NEGATIVE_ASSERTIONS = [
    {
        "id": "N1_llm_call_zero",
        "name": "repair_from_fact path 진입 시 LLM 호출 0건 (negative assertion)",
        "setup": "S1~S6 의 모든 시나리오 실행 중",
        "expected": "openai.* 또는 llm_gateway.* 의 chat completion 호출 0회. monkeypatch 로 검증.",
    },
    {
        "id": "N2_no_truncate",
        "name": "agent_kb_rw role 이 TRUNCATE 권한 부재 — application 이 KB 통째로 비우지 못함",
        "setup": "agent_kb_rw 로 connect + `TRUNCATE TABLE fact_entries`",
        "expected": "psycopg.errors.InsufficientPrivilege raise",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Test stubs (M2-b cycle 책임 — 실 구현).
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="M2-b cycle 책임 — 실 구현은 dual-write 활성 후")
@pytest.mark.parametrize("scenario", SCENARIO_CATALOG, ids=lambda s: s["id"])
def test_anchor_invariant_scenarios(scenario):
    """ANCHOR §3 의 6종 fact-우선 복구 시나리오 검증.

    M2-b cycle 에서 구현:
    1. Postgres fixture 로 시나리오 setup 데이터 INSERT (`PgKbBackend.upsert_*`)
    2. `insight._repair_from_fact()` 호출
    3. expected 동작 assertion (RagDocuments / RagObjects / Texts row count + content)
    4. `monkeypatch.setattr('openai.chat.completions.create', lambda *a, **k: pytest.fail('LLM called'))` 로 LLM 호출 0건 검증
    """
    assert scenario["id"]  # placeholder — M2-b assertion 채울 위치


@pytest.mark.skip(reason="M2-b cycle 책임")
@pytest.mark.parametrize("assertion", NEGATIVE_ASSERTIONS, ids=lambda a: a["id"])
def test_anchor_invariant_negative(assertion):
    """negative assertion — LLM 호출 0건, TRUNCATE 차단 등."""
    assert assertion["id"]  # placeholder


# ─────────────────────────────────────────────────────────────────────────────
# Helper — M2-b cycle 의 fixture 예시 (참조용).
# ─────────────────────────────────────────────────────────────────────────────


def _example_setup_scenario_s1(pg_conn, mysql_conn):
    """S1 (RagDocuments 누락) fixture 의 reference 예시.

    M2-b 의 실 fixture 가 본 함수 패턴 따라 구현.

    1. fact_entries.upsert (PgKbBackend) + (MysqlKbBackend) 양쪽
    2. texts.upsert (text_hash, text_content) 양쪽
    3. rag_documents 는 INSERT 안 함 (시나리오 setup)
    4. rag_objects 는 INSERT — 본 시나리오는 rag_documents 만 누락
    5. insight._repair_from_fact 호출 → rag_documents INSERT 확인
    """
    pass  # M2-b 책임


if __name__ == "__main__":
    # 본 모듈 직접 실행 시 시나리오 catalog 출력 (M2-a 검증).
    import json
    print("=== ANCHOR §3 invariant 시나리오 catalog ===")
    print(json.dumps(SCENARIO_CATALOG, ensure_ascii=False, indent=2))
    print("\n=== Negative assertions ===")
    print(json.dumps(NEGATIVE_ASSERTIONS, ensure_ascii=False, indent=2))
