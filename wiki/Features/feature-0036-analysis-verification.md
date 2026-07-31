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
feature_id: feature-0036-analysis-verification
linked_unit: unit/feature-0036-analysis-verification
sources:
  - ../../unit/feature-0036-analysis-verification/docs/FUNCTION.md
---

# Feature — 분석문 사실성 판정

> 정본은 [[../../unit/feature-0036-analysis-verification/docs/FUNCTION|FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> AI가 쓴 테이블 설명을 **실제 측정값과 대조**해 뒷받침됨/어긋남/판단불가로 표시한다 —
> 확인에 실패하면 아무 표시도 남기지 않는다.

## 2. 상태

- **단계**: draft (구현·리뷰 완료 · 배포 검증 대기)
- **마지막 갱신**: 2026-07-31
- **AI 작업자**: claude (session e75e6c4c)

## 3. 책임 경계

- **입력**: 분석문(`node_analysis_jobs`) + 통계 증거(`metadata_table_stats/column_stats`)
- **출력**: `node_analysis_verdicts` 행(verdict + 근거 문장 + 증거 깊이)
- **side-effect**: 판정 1건당 LLM 1콜(pass 상한 20)
- **하지 않는 것**: 분석문 수정 · 표시(후속) · 확인 실패 시 기록

## 4. 관련 정본

- [[../../unit/feature-0036-analysis-verification/docs/FUNCTION|FUNCTION.md]]
- [[../../unit/feature-0036-analysis-verification/docs/DECISIONS|DECISIONS.md]] — ADR-0036-01~07
- [[../../unit/feature-0036-analysis-verification/docs/REVIEW|REVIEW.md]] — codex P1 4건

## 5. 관련 노트

- [[feature-0031-analysis-grounding|feature-0031]] — 판정의 근거가 되는 증거
- [[feature-0035-analysis-planner|feature-0035]] — 커버리지가 차야 판정 대상이 는다
- [[../../docs/improvements/analysis-orchestration/ROADMAP|ROADMAP.md]] — ITEM-10

## 6. Open questions / 미해결

- 판정 대상이 현재 7건 수준(증거 커버리지 제약).
- 판정 결과의 콘솔 표시·grounding 반영은 후속 범위.
- 규칙으로 잡을 수 있는 모순(언급된 컬럼이 증거에 없음)은 전처리로 덜어낼 여지가 있다.

## 7. 변경 이력 (이 카드)

- 2026-07-31: 초안 작성
