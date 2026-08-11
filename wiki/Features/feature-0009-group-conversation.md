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
  - ../../docs/SECURITY.md
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

- **단계**: substantial — 코어(S1~S4) + 라이브 UX(1·2차) + 아바타·멘션 알림 + 안 읽음/@멘션 배지·메시지 좌우 정렬·owner 멤버 추방/차단·참가자 per-message 제품 선택·composer 비잠금/1:1 인터럽트 재요청 배포 완료. **(2026-07-03)** 공유 링크 참여 시 "참여 알림" pill(멤버 pill + 기존 멤버 unread +1, 가입자 제외; anonymous 공유뷰 username 비노출; LLM 히스토리 sentinel 배제)(gc-join-notice). **(2026-07-04)** **멤버 가시성 window 공유**(share-visibility-window, Critical) — "여기부터/여기까지 공유"로 `[from,to]` window 밖 구간을 참여자의 뷰·LLM recall·fork 전부에서 물리 배제(SECURITY §21/§21.4). S5(run cap·llm_usage actor 귀속)·S6(스레드 UI) deferred.
- **마지막 갱신**: 2026-07-04
- **AI 작업자**: claude (`ai/claude/feature-0009-group-conversation` 외 `gc-*` · `share-visibility-window` worktree 계열)
- 계획은 `/plan-eng-review`(outside-voice) + `/cso` 위협모델 통과 (SHIP-WITH-FIXES).

## 3. 책임 경계

- 입력: 멤버 채팅 메시지(`@assistant`/`@account` 멘션 토큰 가능), 공유 링크 '참여 허용'을 통한 join, roster add/remove 요청.
- 출력: 멤버십 기반으로 열람 가능한 대화 + 발신자 라벨이 붙은 메시지. `@assistant` 발신 시에만 LLM 응답(actor = 발신 멤버 RBAC).
- side-effect: `conversation_members` 멤버십 행, `core_messages.sender_account_id` 귀속, `ask_jobs` enqueue(멘션 시), 멤버/`@assistant` actor 감사(audit), 피멘션 알림(토스트 + OS Notification).

핵심 모델:
- **열람 ≠ 발화**: 멤버는 datasource 권한이 없어도 대화 전체 열람 가능. `@assistant` 로 datasource 쿼리/발화는 발신자 본인 RBAC 로만 게이트. 참가자는 대화 공통 고정 제품 접근권이 없어도 **메시지마다 본인 권한 제품을 선택**해 질의 가능(per-message override, 발신자 RBAC 재확인 — parse + run-product 이중, REQ-GC-R7; 접근 불가 제품은 '열람 전용' 비활성 표시).
- **참여 일원화**: username 직접 초대 폐지(CHG-20260623-0013) → 공유 링크 '참여 허용'(기본 ON)으로 join 일원화.
- **첨부 격리**: 첨부는 멤버 전원 열람/다운로드 공유, 단 LLM 맥락 주입은 `@assistant` 발신자 본인 첨부로 한정(권한상승 방지, CSO F1).
- 라이브 UX: 적응형 폴링(5s↔1.5s)·`@`멘션 자동완성(TTL)·발신자/제품 Identicon 아바타·피멘션 알림+하이라이트·사이드바 안 읽음/@멘션 배지(read cursor, REQ-GC-R8)·메시지 좌우 정렬(내 메시지 우측, 상대/`@assistant` 좌측)·**처리 중 composer 비잠금**(`myAskInFlight` 로 자기 run 만 추적 — 입력 있으면 처리 중에도 전송)·1:1 인터럽트 재요청(진행 중 run abort + 부분 rationale '(중단 보존)' 저장 후 재요청)·그룹 `@assistant` 중복 run 차단.
- owner 멤버 관리: 공유 팝업에서 소유자가 멤버 추방/차단/해제(kick/ban/unban, hover 펼침 액션).
- **참여 알림(gc-join-notice, 2026-07-03)**: 공유 링크로 새 멤버 join 시 대화 내 "X님이 대화에 참여했습니다." pill — core_messages(sentinel `EVENT_MESSAGE_NAME`)+표시 store(`event_type='member_joined'`) 이중 기록으로 기존 멤버 unread +1(가입자 제외), LLM 히스토리에서는 sentinel 배제(발신자라벨 오응답 방지), anonymous 공유뷰는 멤버 username 비노출.
- **멤버 가시성 window(share-visibility-window, 2026-07-04, Critical — 정본 SECURITY §21/§21.4·정본 코드 feature-0002 recall + feature-0003 share/fork/view/FE)**: "여기부터"(floor)+"여기까지"(ceiling)로 공유가 `[from,to]` window 만 노출하고, 가려진 구간을 참여자의 **라이브 뷰·LLM recall·fork** 전부에서 물리 배제(프롬프트 인젝션으로도 추출 불가). 아키텍처 = "라이브룸 + 멤버 필터"(격리 분기 아님) — `conversation_members` window 컬럼 + `has_restricted_members` 게이트(alembic 0037, additive) + recall/display 양 loader 필터(fail-closed DENY, unfiltered 폴백 금지) + fork 3-store 교집합 clip + join stamp never-widen·widen-guard(403) + owner-answer 표시태그(recall_floor). `has_restricted_members=false` 인 대화(거의 전부)는 필터 완전 우회(무회귀). **AR-1/AR-2 수용 위험을 windowed 한정으로 반전**(bounded 멤버 열람·fork 가 `[from,to]` 로 제약; full 공유는 종전 전체 열람/복제 그대로).
- **말풍선 ☰ 메뉴 통합(2026-07-04, FE 거주 feature-0003)**: 말풍선 액션(샘플 등록·여기서 분기·여기까지/여기부터 공유·'AI 로 고치기')을 kebab ☰ 메뉴로 통합, 피드백 👍/👎 만 메뉴 밖 유지.
- **기능 첫 사용 1회 가이드 툴팁(gc-first-use-guide, 2026-08-07, FE 거주 feature-0003 · AC-GC-A13)**: 그룹 대화 기능을 **처음 쓰는 계정**에 컴포저 위 안내 말풍선 5줄(각 30자 이하)을 1회 띄운다 — 모달·백드롭 없음(팝업 금지 = 사용자 결정) · 소진 키는 계정 단위(`mad.gcFirstUseGuide.v1` — "각 그룹대화의 처음" 이 아니라 "기능의 처음") · 닫기 ≠ 소진("다시 안 보기" 만 영구) · 발화 가능(`conversation.ask`) 게이트 · Esc 는 멘션 자동완성·드롭 오버레이에 양보한다(capture 등록 — 버블 단계에서는 먼저 등록된 AC 핸들러가 AC 를 닫은 뒤 실행돼 오판했고 PB-0008 라이브가 이를 적발했다).

## 4. 관련 정본

- [[../../unit/feature-0009-group-conversation/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0009-group-conversation/docs/TASK|TASK.md]] — 작업 컨텍스트(TASK-20260619T023140)
- [[../../unit/feature-0009-group-conversation/docs/REPORT|REPORT.md]] — 진행 현황(S1~S6)
- [[../../unit/feature-0009-group-conversation/docs/DECISIONS|DECISIONS.md]] — feature-level 결정
- [[../../docs/SECURITY|docs/SECURITY.md]] — 수용 위험(view≠invoke 노출·fork 반출, §18) + 멤버 가시성 window 격리(§21·§21.4 recall 봉인 잔여리스크) 정본
- [[../../unit/feature-0009-group-conversation/docs/ANCHOR|ANCHOR.md]] §4 — 멤버 window 필터 위치 매핑(cross-feature 코드 거주)

## 5. 관련 노트

- [[feature-0003-agent-web-ui]] — Web UI·공유 링크·첨부·avatar 자산 재사용
- [[feature-0002-agent-core]] — ask_jobs 큐·LLM actor 귀속
- [[../concepts/ask-worker-queue|ask-worker 큐]] — `@assistant` enqueue 경로
- [[../Architecture/Overview|Architecture Overview]]

## 6. Open questions / 미해결

- S5: per-conversation run cap·`llm_usage` actor 귀속·LLM 화자 라벨(REV-0012, 배포 후 라이브).
- S6: 풀 스레드 UI + 스레드별 AI run 병렬화 — run-status KV 재키잉 필요(별도 계획).
- 실시간성: 현재 적응형 폴링. WebSocket/pubsub 는 v1 범위 외.
- **owner-answer 누출면(§21.4)**: bounded 멤버 뷰에서 owner/full 멤버의 무제한-recall 답변 은닉은 "표시 태그만"(display-단) 결정 — 생성시점 클램프가 아니라 잔여 리스크(사용자 sign-off). share-visibility-window PB-0008 라이브 시각검증(☰ 메뉴·여기부터 범위 배너·windowed 공유 뷰)은 배포 후 잔여.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0009-group-conversation/docs/MODIFY.md` 에.

- 2026-06-23: 초안 작성 (코어 + 라이브 UX 1·2차 + 아바타·멘션 알림 배포 후 wiki 정합).
- 2026-06-25: 06-25 머지 정합 — 사이드바 안 읽음/@멘션 배지(REQ-GC-R8 read cursor, alembic 0019)·메시지 좌우 정렬·owner 멤버 추방/차단/해제(kick/ban/unban, hover 액션) 반영 (doc_sync).
- 2026-06-25: 06-25 잔여 머지 정합 — 참가자 per-message 제품 선택·발화(REQ-GC-R7, PR#440)·처리 중 composer 비잠금/1:1 인터럽트 재요청/그룹 @assistant 중복차단(PR#438·#444)·@assistant 발신자 표시 정정(PR#437) 반영 (doc_sync).
- 2026-06-26: 06-25 후속 버그픽스 정합(릴리즈노트 sync a29a2f0 이후) — 안 읽음 배지 미감소 최종 근본원인(읽음 커서 id-space 불일치: 항상 `MAX(core_messages.id)` 로 전진)·선행 read 500(`modules.db`→`shared.db`)·읽음 커서 전진 누락·입력창 즉시 클리어 / optimistic 발신자 표시 깜빡임 정정 / 공유 대화 join 불가(PG AmbiguousParameter) / assistant SQL dialect 교정 + 그룹 발신자 맥락 라벨(feature-0002) 반영 (doc_sync).
- 2026-07-06: 07-03/07-04 델타(마지막 릴리즈노트 5b1481bb 이후) 반영 — gc-join-notice(공유 참여 시 참여 알림 pill + 기존 멤버 unread, LLM sentinel 배제·anonymous username 비노출, CHG-20260703T182740) + share-visibility-window(멤버 가시성 window [from,to] 공유 격리 — 뷰·recall·fork 물리 배제, alembic 0037, AR-1/AR-2 windowed 반전, AC-GC-A20~A27, Critical, CHG-20260704T130000) + 말풍선 ☰ 통합('AI 로 고치기' 포함·👍/👎 외부, FE 거주 feature-0003) 반영. 정본 REPORT/FUNCTION §11(share-visibility-window AC)·SECURITY §21/§21.4·ANCHOR §4 / 코드 정본 cross-feature(feature-0002 recall + feature-0003 share·fork·view·FE) / 머지 #593 전후 share-visibility-window 커밋열. 요지+포인터만(SSOT). (doc_sync)
