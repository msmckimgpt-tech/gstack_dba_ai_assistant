---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
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
feature_id: feature-0041-external-ai-tool-surface
linked_unit: unit/feature-0041-external-ai-tool-surface
sources:
  - ../../unit/feature-0041-external-ai-tool-surface/docs/FUNCTION.md
---

# Feature — 외부 AI 도구 표면 (추론 주체 반전)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0041-external-ai-tool-surface/docs/FUNCTION|unit/feature-0041-external-ai-tool-surface/docs/FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> 외부 사용자의 AI 가 **자기 계정 LLM 으로 직접 추론**하면서 이 서비스의 데이터소스·RAG·
> 메타지식에 접근하도록, 내부 에이전트 도구를 인증·스코프·원장이 붙은 외부 표면으로 노출한다
> (LLM 비용은 호출자 부담, 서비스는 자격증명 무보관).

## 2. 상태

- **단계**: in-progress (P0 도구 9종 + OAuth AS + MCP stdio / HTTP·SSE 어댑터 구현 완료 · 1차 `a68fbbac` / 2차 `e1372f32` 라이브 배포 + POST-DEPLOY 12항·8항 실측 완료)
- **마지막 갱신**: 2026-08-12
- **AI 작업자**: claude / feature-0041 cycle
- **잔여**: 관리 콘솔 '외부 도구 한도' 탭(사용자 결정으로 별도 cycle — admin.js 동시 편집 충돌 + PB-0008 하드 게이트, 상한 자체는 runtime 기본값으로 이미 집행 중) · 사람 1회 인가가 필요한 전 구간 e2e(설계상 자동화 불가) · P1 이후 도구(`execute_sql` 등) 별도 단계

## 3. 책임 경계

- **입력**: OAuth 인가(사람 브라우저 로그인·동의) · 도구 인자(`task_id`·식별자·`source_tasks`)
- **출력**: datamark 각인된 데이터 블록 · `tool_call_usage` 원장 · 대화 적재(원 질문·최종 답변)
- **side-effect**: 없음(읽기 전용 도구만 — 쓰기·첨부·scratch 계열은 영구 제외)

## 4. 관련 정본

- [[../../unit/feature-0041-external-ai-tool-surface/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0041-external-ai-tool-surface/docs/ANCHOR|ANCHOR.md]] — 방향성 정본 (왜 추론 주체를 반전하는가)
- [[../../unit/feature-0041-external-ai-tool-surface/docs/TASK|TASK.md]] — 구현 계획 (§2.1)
- [[../../unit/feature-0041-external-ai-tool-surface/docs/REVIEW|REVIEW.md]] — codex 적대 리뷰 결과

## 5. 관련 노트

- [[feature-0023-conversation-api-access|feature-0023]] — `ask` 축(우리 LLM 이 추론). 본 feature 와 병존·용도 구분
- [[../Architecture/Module-Map|Module Map]]
- [[../Decisions/_Index|Decisions MOC]] — ADR-0026(per-user 키 폐기)이 Alt-B 폐기 근거

## 6. Open questions / 미해결

- 외부 AI 가 세션 A 데이터를 기억한 채 세션 B 에 **서술로** 답하는 경로는 차단·탐지 불가
  (구조적 한계 — 각인·선언·대조는 "몰라서 섞임"만 제거)
- `submit_answer` 미호출은 강제 불가 (소프트 강제: 미제출률 노출 + 임계 초과 시 신규 task 제한)

## 7. 접속 방법 (사용자 관점)

설치물이 없다. MCP 클라이언트에 **URL + access token** 만 등록한다:

- 엔드포인트: `https://<host>/api/ai/mcp` (streamable-http)
- 헤더: `Authorization: Bearer <access_token>` — 없으면 **엣지에서 401**(익명 연결 차단)
- 토큰 발급: `/api/ai/guide` 부록 B (등록 → 브라우저 인가 1회 → 토큰 교환)

여러 계정을 **동시에** 다룰 때는 stdio 런처(`external_tool_mcp_server.py`)를 권한다 — 도구
이름에 라벨이 접미돼 호출자 AI 가 세션을 구분할 수 있다(L1). HTTP 전송에는 그 층이 없다.

## 8. 변경 이력 (이 카드)

- 2026-08-12: 초안 작성 (계획 cycle)
- 2026-08-13: 3차 출하 반영 — HTTP/SSE 전송 라이브 기동(`ext-tool-mcp` + 엣지 `/api/ai/mcp`) ·
  상한 4종 콘솔 노출 · e2e 절차서. §7 접속 방법 추가
