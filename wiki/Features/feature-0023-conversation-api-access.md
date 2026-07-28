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
feature_id: feature-0023-conversation-api-access
linked_unit: unit/feature-0023-conversation-api-access
sources:
  - ../../unit/feature-0023-conversation-api-access/docs/FUNCTION.md
---

# Feature — Conversation API 접근 (Bearer 토큰 + MCP)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0023-conversation-api-access/docs/FUNCTION|unit/feature-0023-conversation-api-access/docs/FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

외부 AI 가 세션 쿠키 없이 **Bearer API 토큰**으로 작업 화면 대화(`/api/ask` 등)를 호출하고,
MCP 서버로 그 대화를 tool 화한다. scope 로 관리 콘솔은 원천 차단. **대화 품질**(모델·추론 강도·
제품·폴더 커스텀 지침·첨부)도 외부 AI 가 직접 조정하며, 계정마다 다른 허용 값은 인증 필수
`GET /api/ai/capabilities` 로 조회한다.

## 2. 상태

- **단계**: 라이브 (Bearer 인증·MCP·발견 진입점 배포 완료 / 품질 조정 표면은 배포 대기)
- **마지막 갱신**: 2026-07-28
- **AI 작업자**: claude (feature-0023 cycle · conversation-quality-controls)

## 3. 책임 경계

- 입력: `Authorization: Bearer <token>` 헤더(세션 쿠키 부재 시 fallback), `/api/ask` body,
  품질 조정 요청(제품 PATCH·폴더 지침·첨부 multipart).
- 출력: 기존 대화 API 응답(불변). MCP tool 반환(assistant 답변). `GET /api/ai/capabilities`
  의 계정별 조정 옵션 카탈로그(5축).
- side-effect: `WebApiTokens.LastUsedAt` 갱신, `WebAuditEvents` 발급/폐기 기록.
- 보안 경계: 토큰 인증은 `conversation.*`+`product.access.*`+`folder.*`(own) allowlist ∩
  계정권한, 그리고 `*.any`·관리 네임스페이스 **절대 denylist**(scope 무관) → 관리 콘솔 접근 불가.
  capabilities 는 **인증 필수**(익명 발견 자료의 "인스턴스 데이터 0" 불변식과 계층 분리) 이며
  읽기 전용 — 목록은 작업 화면 선택기와 같은 필터를 거쳐 표시-집행이 어긋나지 않는다.

## 4. 관련 정본

- [[../../unit/feature-0023-conversation-api-access/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0023-conversation-api-access/docs/TASK|TASK.md]] — 작업 컨텍스트
- [[../../unit/feature-0023-conversation-api-access/docs/REVIEW|REVIEW.md]] — 적대적 보안 리뷰(REV-20260722-0002)
- [[../../unit/feature-0023-conversation-api-access/docs/ANCHOR|ANCHOR.md]] — 방향성 앵커

## 5. 관련 노트

- [[../Architecture/Module-Map|Module Map]] — 인증 진입점(web_context)·대화 라우터 위치
- 코드 거주: feature-0003(web 인증·라우터), feature-0002(agent_core ask)

## 6. Open questions / 미해결

- 셀프서비스 토큰 발급 웹 엔드포인트(scope 제한) 도입 여부.
- per-token rate limit(현재는 서비스 계정 quota 상속).
- 기존 발급 토큰은 저장된 scope 라 폴더 축이 닫혀 있다 — 일괄 재발급 안내 방식(운영).
- 폴더 datasource/product 핀(feature-0024 Phase 2b)이 배선되면 품질 축 편입 여부.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0023-conversation-api-access/docs/MODIFY.md` 에.

- 2026-07-22: 초안 작성 (Bearer 토큰 인증 + MCP 서버 cycle).
- 2026-07-28: 대화 품질 조정 표면 반영 (`/api/ai/capabilities` 신설·발견 자료 5축 계약·
  MCP tool 4→11·토큰 안전 기본 scope 에 `folder.` 확장). 관련: [[feature-0024-conversation-folders]]
  (폴더 지침 주입), [[feature-0003-agent-web-ui]](라우터·인증), [[feature-0002-agent-core]](ask).
