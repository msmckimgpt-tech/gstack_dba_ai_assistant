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
maturity: substantial
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

- **단계**: substantial — cycle 1 출하(배포 8b46bdec) + cycle 2 판정 순환 수정 + cycle 3 판정 노출,
  전건 배포·라이브 실측 완료(PB-0008 PASS).
- **마지막 갱신**: 2026-08-05
- **AI 작업자**: claude (session e75e6c4c · 08-05 cycle 2·3)

## 3. 책임 경계

- **입력**: 분석문(`node_analysis_jobs`) + 통계 증거(`metadata_table_stats/column_stats`)
- **출력**: `node_analysis_verdicts` 행(verdict + 근거 문장 + 증거 깊이) + `get_node_analysis` 응답의
  `verdict` — 그래프 뷰 노드 상세 'AI 능동 분석' 박스의 판정 배지 + 근거 한 줄(cycle 3, 표시 코드는
  feature-0003 static 거주)
- **side-effect**: 판정 1건당 LLM 1콜(pass 상한 20). 대상은 **노드당 최신 분석문 1건**(`DISTINCT ON`,
  최신 기준 = `id`) — 행 단위로 두면 저장(노드당 1행)과 단위가 어긋나 판정이 무한 순환한다(ADR-0036-08)
- **하지 않는 것**: 분석문 수정 · 확인 실패 시 기록 · 해시 불일치 판정 표시(ADR-0036-09) · grounding 반영(후속)

## 4. 관련 정본

- [[../../unit/feature-0036-analysis-verification/docs/FUNCTION|FUNCTION.md]]
- [[../../unit/feature-0036-analysis-verification/docs/DECISIONS|DECISIONS.md]] — ADR-0036-01~10
- [[../../unit/feature-0036-analysis-verification/docs/REPORT|REPORT.md]] — cycle 2 판정 순환 서사(실측·원인·대조군·잔여)
- [[../../unit/feature-0036-analysis-verification/docs/REVIEW|REVIEW.md]] — codex P1 4건 + 08-05 적대 패널 4종(backend·qa·ux·backend-security)

## 5. 관련 노트

- [[feature-0031-analysis-grounding|feature-0031]] — 판정의 근거가 되는 증거
- [[feature-0035-analysis-planner|feature-0035]] — 커버리지가 차야 판정 대상이 는다
- [[feature-0003-agent-web-ui|feature-0003]] — 판정 배지가 거주하는 그래프 뷰 노드 상세(static)
- [[../../docs/improvements/analysis-orchestration/ROADMAP|ROADMAP.md]] — ITEM-10

## 6. Open questions / 미해결

- **검증 범위 4.5%** — 증거(`metadata_table_stats`)가 95개 테이블에만 있어 분석문 2,052 노드 중 판정 가능한 것이 92~95개(2026-08-05 실측). feature-0035 플래너가 커버리지를 올려야 이 층이 실질 값을 한다.
- 라이브 판정의 대다수가 증거 stage 0(표본 0행 — 구조만 대조)이다(적대 패널 실측 95건 중 82건). 라벨·tooltip 이 그 차이를 말하지만 표본 수집 자체는 후속.
- (해소) 판정 결과의 표시 — cycle 3 에서 노드 상세 배지 + 근거 한 줄로 연결(PB-0008 라이브 PASS). **grounding 반영은 여전히 후속 범위.**
- 규칙으로 잡을 수 있는 모순(언급된 컬럼이 증거에 없음)은 전처리로 덜어낼 여지가 있다.

## 7. 변경 이력 (이 카드)

- 2026-07-31: 초안 작성
- 2026-08-06 (doc_sync): 08-05 델타 반영 — cycle 2 판정 순환 차단(대상을 `DISTINCT ON` 노드당 최신 1건으로, ADR-0036-08 · 7일 7,896콜/정보 증가 0 → 시간당 148콜 → ~14콜) + cycle 3 판정 노출(노드 상세 배지·근거 한 줄, 해시 일치 시에만·stage 0 라벨 분리, ADR-0036-09/10 · PB-0008 라이브 PASS)로 §2/§3/§6 의 '배포 검증 대기'·'표시(후속)'·'대상 7건' stale 정정. 요지+포인터만(SSOT) — 정본 FUNCTION §3/§7 · DECISIONS ADR-0036-08~10 · REPORT cycle 2 · TASK cycle 2/3 · MODIFY CHG-20260805T143000/T190000.
