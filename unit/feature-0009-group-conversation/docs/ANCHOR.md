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

- **[2026-07-04] share-visibility-window (TASK-20260704) — §1·§2-Alt-C 확장, AR-1/AR-2 부분 반전.**
  §1 은 "초대=이 방의 내용을 당신과 공유하는 신뢰 행위 + 권한 없어도 열람 가능"을 정본으로 했고
  Alt-C(완전 RBAC 격리)를 "협업 가치 소멸"로 기각하며 fork 전체 반출까지 수용(AR-2)했다. 본 cycle 은
  그 결정을 **뒤집지 않되**, owner 가 공유 시 열람 범위를 `[from,to]` window 로 **좁힐 수 있는 opt-in**을
  추가한다. 사용자 결정(2026-07-03) = **"라이브룸 + 멤버 필터"**(격리 분기 아님): 참여자는 여전히 라이브
  멤버지만 가려진 구간은 뷰·LLM recall·fork 전부에서 물리 배제(프롬프트 인젝션 방어). full 공유는 종전
  전체 열람 그대로(무회귀). 이로써 SECURITY.md §18 AR-1(join 전체열람)·AR-2/F3(fork 전체반출)는
  **windowed share 에 한해 반전**된다(SECURITY.md §21 정본). owner-answer 누출면은 "표시 태그만"으로 봉인
  (생성시점 클램프는 별 cycle 승격 여지 — §21.4 잔여리스크). 적대 검증: REVIEW.md 참조.
