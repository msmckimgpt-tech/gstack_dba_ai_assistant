---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, nl2sql, rag, evaluation]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
concept_category: framework
aliases: [nl2sql-flywheel, NL2SQL flywheel, NL→SQL 정확도, dba-ai-nl2sql]
tags: [nl2sql, rag, evaluation, few-shot, self-reflection, glossary]
last_updated: 2026-06-23
---

# NL→SQL 정확도 Flywheel (dba-ai-nl2sql)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | framework |
| 정본 로드맵 | `docs/improvements/dba-ai-nl2sql/ROADMAP.md` (`/_dqa` 파이프라인 산출) |
| 정본 리서치 | `docs/improvements/dba-ai-nl2sql/RESEARCH.md` |
| 구현 정본 | `unit/feature-0002-agent-core/docs/FUNCTION.md` |
| 최종 갱신 | 2026-06-23 |

## 1. 개요

자연어 질문 → SQL 생성의 **정확도를 측정 기반으로 끌어올리는 일련의 개선 묶음**. `/_dqa`
지속 개선 파이프라인(improve_research → improve_listup → improve_cycle)이 발굴·로드맵화한
`dba-ai-nl2sql` initiative 의 항목들이다. 핵심 통찰: **"샘플쿼리 유무 = 정확도 ±90%"**
(BroQuery 자체측정) — 사용이 정확도를 키우는 순환(flywheel)을 만드는 것이 최대 레버.

> **불변 규칙**: ITEM-01(평가 harness)이 **모든 성능 항목의 선행 측정 수단**. 측정 없이
> 성능 항목을 done 으로 닫지 않는다.

## 2. 구현 현황 (2026-06-23 드레인)

| ITEM | 내용 | 상태 |
|---|---|---|
| **ITEM-01** | NL→SQL 평가 harness (RAGAS + LLM-as-Judge) | 코어 완료 |
| **ITEM-02+03** | 샘플쿼리(NL↔SQL) few-shot 저장소 (PR-A) | 코어 완료 |
| **ITEM-04** | 데이터소스 비즈니스 컨텍스트 필드 | read-side+schema 완료 (write UI 는 ITEM-11) |
| **ITEM-07** | Self-Reflection 명시 자가수정 루프 | 완료 |
| **ITEM-10** | 용어사전 + ENUM 코드사전 구조부 | 구조부 완료 |
| **ITEM-09** | heavy-query plan+approve | reject(subsumed) — 기존 EXPLAIN gate 가 포섭 |

> **측정 보류**: ITEM-02/04 의 효과 A/B(샘플 off/on)는 임베딩(titan-embed) 다운으로 보류 —
> 복구 후 ITEM-01 harness 로 generation/retrieval metric 유의 상승 검증 예정.

## 3. 핵심 메커니즘

| 축 | 설계 |
|---|---|
| **평가 harness (ITEM-01)** | RAGAS + LLM-as-Judge 로 generation/retrieval metric 산출 — 개선 효과의 측정 게이트. |
| **샘플쿼리 few-shot (ITEM-02)** | `sample_queries` 테이블(마이그 0014) + 임베딩 `vector(1536)`, `approved ∧ active ∧ weight` cosine 검색, `## EXAMPLE QUERIES` **예시-only 주입**(직접 실행 아님), datasource-scoped(교차오염 차단). |
| **feedback 환류 (ITEM-03)** | 답변 👍/👎 + "샘플로 등록" → 검수 큐 → 승인 시 `sample_queries`(approved) 승급, 👎=negative example. (PR-B/ITEM-11) |
| **DS 비즈니스 컨텍스트 (ITEM-04)** | `WebDatasources.Description`/`DomainTags` → `describe()` → 멀티DS 그라운딩 주입(질문 의도 해석 보강). |
| **self-reflection (ITEM-07)** | 답변 전 명시적 자가수정 루프 — 생성 SQL/결과를 스스로 한 번 더 점검. |
| **용어/ENUM 사전 (ITEM-10)** | 도메인 용어사전 + ENUM 코드사전 구조부 — 코드값↔의미 매핑 그라운딩. |

## 4. guard (fit-review)

- 샘플은 **datasource-scoped** (insight `ds_fact_like` 패턴 재사용 — 교차오염 차단).
- 샘플은 프롬프트 **예시로만** 주입(직접 실행 금지).
- 등록 경로는 **큐레이션 게이트** 통과분만(ITEM-03 검수).
- 적대 backend+security 리뷰: 임베딩 `::vector` BLOCKER 흡수 후 SHIP.

## 5. 인용 source

- `docs/improvements/dba-ai-nl2sql/ROADMAP.md` (정본 — 12 ITEM 종속 그래프 + Phase 시퀀스)
- `docs/improvements/dba-ai-nl2sql/RESEARCH.md` (개선 후보 리서치)
- [[../../unit/feature-0002-agent-core/docs/FUNCTION|feature-0002 FUNCTION.md]]

## 6. 관련 concept

- [[rag]] — Retrieval-Augmented Generation
- [[kb-postgres-pgvector]] — 임베딩 저장·검색 인프라
- [[datasource-aware-rag]] — datasource 별 격리(샘플 scoping 동형)
- [[insight-worker]] — 스키마 통찰(그라운딩 보조)

## 7. 관련 entity

- [[../entities/postgres]] (pgvector) · [[../entities/aws-bedrock]] (임베딩·LLM-judge)

## 8. 외부 link

- [RAGAS — RAG evaluation](https://github.com/explodinggradients/ragas)

## 분류

`#wiki/concept` · `#concept_category/framework` · `#domain/nl2sql` · `#confidence/high`
