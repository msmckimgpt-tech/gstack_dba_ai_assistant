---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki, conversation, rbac]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0009-group-conversation
linked_unit: unit/feature-0009-group-conversation
created: 2026-06-23
sources:
  - ../../unit/feature-0009-group-conversation/docs/FUNCTION.md
---

# Feature — 그룹 대화 (Group Conversation)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0009-group-conversation/docs/FUNCTION|unit/feature-0009-group-conversation/docs/FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> 하나의 대화에 여러 account 가 **멤버**로 참여해 사람-사람 채팅을 나누고, `@assistant` 멘션 시에만 AI 를 호출한다. 대화는 단일 소유(owner) 가정에서 멤버십 기반으로 전환되어 **열람 ≠ 발화** 권한이 분리된다.

## 2. 상태

- **단계**: substantial — 코어(S1~S4) + 라이브 UX(1·2차) + 아바타·멘션 알림 배포 완료. S5(run cap·llm_usage actor 귀속)·S6(스레드 UI) deferred.
- **마지막 갱신**: 2026-06-23
- **AI 작업자**: claude (`ai/claude/feature-0009-group-conversation` 외 `gc-*` worktree 계열)
- 계획은 `/plan-eng-review`(outside-voice) + `/cso` 위협모델 통과 (SHIP-WITH-FIXES).

## 3. 책임 경계

- 입력: 멤버 채팅 메시지(`@assistant`/`@account` 멘션 토큰 가능), 공유 링크 '참여 허용'을 통한 join, roster add/remove 요청.
- 출력: 멤버십 기반으로 열람 가능한 대화 + 발신자 라벨이 붙은 메시지. `@assistant` 발신 시에만 LLM 응답(actor = 발신 멤버 RBAC).
- side-effect: `conversation_members` 멤버십 행, `core_messages.sender_account_id` 귀속, `ask_jobs` enqueue(멘션 시), 멤버/`@assistant` actor 감사(audit), 피멘션 알림(토스트 + OS Notification).

핵심 모델:
- **열람 ≠ 발화**: 멤버는 datasource 권한이 없어도 대화 전체 열람 가능. `@assistant` 로 datasource 쿼리/발화는 발신자 본인 RBAC 로만 게이트.
- **참여 일원화**: username 직접 초대 폐지(CHG-20260623-0013) → 공유 링크 '참여 허용'(기본 ON)으로 join 일원화.
- **첨부 격리**: 첨부는 멤버 전원 열람/다운로드 공유, 단 LLM 맥락 주입은 `@assistant` 발신자 본인 첨부로 한정(권한상승 방지, CSO F1).
- 라이브 UX: 적응형 폴링(5s↔1.5s)·`@`멘션 자동완성(TTL)·발신자/제품 Identicon 아바타·피멘션 알림+하이라이트.

## 4. 관련 정본

- [[../../unit/feature-0009-group-conversation/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0009-group-conversation/docs/TASK|TASK.md]] — 작업 컨텍스트(TASK-20260619T023140)
- [[../../unit/feature-0009-group-conversation/docs/REPORT|REPORT.md]] — 진행 현황(S1~S6)
- [[../../unit/feature-0009-group-conversation/docs/DECISIONS|DECISIONS.md]] — feature-level 결정
- [[../../docs/SECURITY|docs/SECURITY.md]] — 수용 위험(view≠invoke 노출·fork 반출)

## 5. 관련 노트

- [[feature-0003-agent-web-ui]] — Web UI·공유 링크·첨부·avatar 자산 재사용
- [[feature-0002-agent-core]] — ask_jobs 큐·LLM actor 귀속
- [[../concepts/ask-worker-queue|ask-worker 큐]] — `@assistant` enqueue 경로
- [[../Architecture/Overview|Architecture Overview]]

## 6. Open questions / 미해결

- S5: per-conversation run cap·`llm_usage` actor 귀속·LLM 화자 라벨(REV-0012, 배포 후 라이브).
- S6: 풀 스레드 UI + 스레드별 AI run 병렬화 — run-status KV 재키잉 필요(별도 계획).
- 실시간성: 현재 적응형 폴링. WebSocket/pubsub 는 v1 범위 외.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0009-group-conversation/docs/MODIFY.md` 에.

- 2026-06-23: 초안 작성 (코어 + 라이브 UX 1·2차 + 아바타·멘션 알림 배포 후 wiki 정합).
