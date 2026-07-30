---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: draft
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
feature_id: feature-0031-analysis-grounding
linked_unit: unit/feature-0031-analysis-grounding
sources:
  - ../../unit/feature-0031-analysis-grounding/docs/FUNCTION.md
---

# Feature — 노드 분석 접지 (analysis grounding)

> Feature 의 *사람용 입구*. 정본은
> [[../../unit/feature-0031-analysis-grounding/docs/FUNCTION|unit/feature-0031-analysis-grounding/docs/FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> 그래프 뷰 'AI 능동 분석'이 이름 규칙으로 추측하던 것을, 운영 DB 에서 모은 **통계 증거**에
> 근거하도록 바꾼다 — 원시 값은 저장하지도 주입하지도 않는다.

## 2. 상태

- **단계**: draft (T1 구현 완료 · 배포 검증 대기)
- **마지막 갱신**: 2026-07-30
- **AI 작업자**: claude (session e75e6c4c)

## 3. 책임 경계

- **입력**: 분석 대상 Table 노드(`scope:schema.table`) + 해당 datasource 접속 정보
- **출력**: `metadata_table_stats` / `metadata_column_stats` 적재 + 분석 payload 의 `evidence` 블록
- **side-effect**: 운영 DB 에 **읽기 전용** 카탈로그·표본 조회(`ds` 자원 예산 게이트 위,
  첫 접촉은 카탈로그만이라 사용자 테이블 read 0). 쓰기·DDL 없음.
- **하지 않는 것**: 원시 컬럼 값 수집·저장·주입(문자열 min/max 포함) · 클러스터 시그니처 변경 ·
  LLM 호출 수 증가

## 4. 관련 정본

- [[../../unit/feature-0031-analysis-grounding/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0031-analysis-grounding/docs/TASK|TASK.md]] — 작업 컨텍스트
- [[../../unit/feature-0031-analysis-grounding/docs/DECISIONS|DECISIONS.md]] — ADR-0031-01~07
- [[../../unit/feature-0031-analysis-grounding/docs/REPORT|REPORT.md]] — 진단·리서치·구현 보고

## 5. 관련 노트

- [[../../docs/improvements/analysis-orchestration/RESEARCH|RESEARCH.md]] — 진단·웹 리서치·설계 전문
- [[../../docs/improvements/analysis-orchestration/ROADMAP|ROADMAP.md]] — T0~T3 로드맵(11 ITEM)
- [[../../unit/feature-0016-metadata-graph/docs/FUNCTION|feature-0016]] — 그래프·노드 분석 정본
- [[../../unit/feature-0025-worker-parallelism/docs/DECISIONS|feature-0025]] — 자원 예산 계약(T0)

## 6. Open questions / 미해결

- 증거 기반 신호를 `_relevance`(탐색 방향 결정)에도 넣을지 — 1차는 넣지 않았다. 접지가 서술에만
  들어가고 탐색 방향은 여전히 이름이 정한다.
- thin 판정 변경의 실제 back-refine 물량 효과는 라이브 분포에 달렸다(배포 후 실측).
- 아직 분석되지 않은 테이블에는 증거가 없다 — 커버리지는 ITEM-11(결정적 플래너) 소관.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0031-analysis-grounding/docs/MODIFY.md` 에.

- 2026-07-30: 초안 작성 (T1 접지 슬라이스 구현과 함께)
