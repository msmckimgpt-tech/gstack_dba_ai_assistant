---
doc_type: ANCHOR
feature_id: feature-0009-group-conversation
created_at: 2026-06-19T02:31:40Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0009-group-conversation 그룹 대화

## §1. 외부 관점 요약
"왜 멤버는 datasource 권한이 없어도 대화 전체(실제 쿼리 결과·SQL 포함)를 볼 수 있게
했지? RBAC 우회 아닌가?" → 사용자 명시 결정. 그룹대화의 가치는 *함께 보고 논의*하는 것이고,
초대 자체가 "이 방의 내용을 당신과 공유한다"는 신뢰 행위다. 발화(쿼리 실행)는 여전히 본인
권한으로만 게이트해 *새* 데이터를 끌어오지 못하게 막고, 노출 경계는 멤버십 + 감사로 추적한다.
"왜 AI 가 모든 메시지에 응답 안 하지?" → 사람끼리 채팅이 1급 기능이라 `@assistant` 멘션
시에만 호출(Discord/ChatGPT Group Chats 패턴).

## §2. 대안 분기
- **Alt-A: Discord형 sub-channel 스레드(스레드=별도 객체).** 페르소나: 대규모 커뮤니티
  운영팀. 안 고른 이유: conversation 이 이미 "채널" 역할. 별도 thread 테이블·아카이브
  수명주기는 무겁고, run-status KV `(conversation_id,key)` 단일 키와 충돌(ENG #1). v1 은
  Slack형 컬럼 훅만.
- **Alt-B: 모든 메시지가 AI 호출(멘션 게이팅 없음).** 페르소나: 1:1 어시스턴트 사용 습관.
  안 고른 이유: 사람-사람 채팅이 불가능해지고 비용·노이즈 폭증. 사용자가 "사람끼리 일반
  채팅 가능" 을 명시 요구.
- **Alt-C: 결과도 발화처럼 본인 권한으로만 열람(완전 RBAC 격리).** 페르소나: 규제 산업
  보안팀. 안 고른 이유: 그룹대화의 협업 가치를 없앰. 사용자가 "권한 없어도 열람 가능" 선택.
  대신 fork 반출까지 수용 위험으로 명시(docs/SECURITY.md AR-2).

## §3. 가정된 사용 시나리오
DBA 김씨가 운영 이슈 대화에 동료 박씨(해당 datasource 무권한)와 매니저 이씨를 초대한다.
김씨가 `@assistant 주문 테이블 최근 1시간 에러율 보여줘` 로 쿼리(김씨 권한으로 실행),
결과가 방에 표시된다. 박씨는 권한이 없어 직접 쿼리는 못 하지만 결과를 같이 보며 `@김씨
이 스파이크 배포랑 겹치나요?` 로 사람끼리 논의한다. 이씨는 나중에 들어와 unread 표시로
못 본 부분만 따라잡는다. 박씨가 이 대화를 본인 것으로 fork 하면 결과는 사본에 남지만
datasource 무권한이라 이어지는 질문은 맥락이 끊긴다(수용된 한계).

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님. eng-review/cso 검증 기록은 REVIEW.md)

<!-- share-visibility-window(TASK-20260704) 은 §1·§2-Alt-C 를 확장한다(뒤집지 않음): owner 가 공유
     열람 범위를 [from,to] window 로 좁히는 opt-in 추가, AR-1/AR-2 는 windowed 한정 반전. 사용자 결정
     "라이브룸 + 멤버 필터" + owner-answer "표시 태그만". 근거·적대검증 정본 = REVIEW.md 해당 cycle 엔트리
     + SECURITY.md §21. §4 는 human 외부검증 전용이라 본 AI-cycle 근거는 여기 주석으로만 남긴다. -->

