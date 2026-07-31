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
feature_id: feature-0037-domain-synthesis
linked_unit: unit/feature-0037-domain-synthesis
sources:
  - ../../unit/feature-0037-domain-synthesis/docs/FUNCTION.md
---

# Feature — 도메인 합성 (L3, lazy)

> 정본은 [[../../unit/feature-0037-domain-synthesis/docs/FUNCTION|FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> DB 하나의 도메인 개요를 3~5문장으로 접어 둔다 — **실제로 조회된 DB만** 만든다.

## 2. 상태

- **단계**: draft (구현·리뷰 완료 · 배포 검증 대기)
- **마지막 갱신**: 2026-07-31
- **AI 작업자**: claude (session e75e6c4c)

## 3. 책임 경계

- **입력**: 그 스키마의 클러스터 요약들(L2)
- **출력**: `domain_summaries` 행 + grounding 주입 한 줄
- **side-effect**: 요청된 스키마당 LLM 1콜(pass 상한 3, advisory lock 아래)
- **하지 않는 것**: 사전 전량 생성 · 답변 경로 런타임 합성 · 그룹 나열

## 4. 관련 정본

- [[../../unit/feature-0037-domain-synthesis/docs/FUNCTION|FUNCTION.md]]
- [[../../unit/feature-0037-domain-synthesis/docs/DECISIONS|DECISIONS.md]] — ADR-0037-01~07
- [[../../unit/feature-0037-domain-synthesis/docs/REVIEW|REVIEW.md]] — codex P1 1건

## 5. 관련 노트

- [[feature-0033-analysis-synthesis|feature-0033]] — L2, 이 층의 입력
- [[feature-0034-analysis-consumption|feature-0034]] — 요청을 남기고 주입하는 경로
- [[../../docs/improvements/analysis-orchestration/ROADMAP|ROADMAP.md]] — ITEM-08(마지막 항목)

## 6. Open questions / 미해결

- 행 단위 claim 이 없어 lock 밖 호출 경로가 생기면 중복 합성 가능(현재 호출자는 insight tick 뿐).
- 요청은 있는데 L2 가 아직 없는 스키마는 계속 대기(L2 가 채워지면 해소).

## 7. 변경 이력 (이 카드)

- 2026-07-31: 초안 작성
