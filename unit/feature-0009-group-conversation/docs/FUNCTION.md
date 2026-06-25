---
doc_type: FUNCTION
feature_id: feature-0009-group-conversation
task_id: TASK-20260619T023140-group-conversation
status: in-progress
edit_policy: rewrite
source_of_truth: true
---

# Function — 그룹 대화 (Group Conversation)

## 1. Summary
하나의 대화(conversation)에 여러 account 가 **멤버**로 참여해, 서로 사람-사람 채팅을
나누고 `@assistant` 멘션으로 AI 를 호출하는 기능. AI 는 멘션 시에만 응답하며, 사람끼리의
대화 맥락까지 읽고 답한다. 대화는 더 이상 단일 소유(owner) 가정에 묶이지 않고, 멤버십
기반으로 열람·발화 권한이 분리된다("열람 ≠ 발화"). 상용 ChatGPT Group Chats /
Microsoft Copilot in Teams 패턴을 사내 RBAC·기존 자산(ask_jobs·fork·share·avatar)
위에 적용한 것이다.

본 계획은 `/plan-eng-review`(outside-voice 포함) 와 `/cso` 위협모델을 통과했다
(verdict: SHIP-WITH-FIXES). 검증에서 도출된 결정과 수용 위험은 §4·§14 에 명시한다.

## 2. Goal
- REQ-GC-R1: 한 대화에 N 명의 account 가 멤버로 참여(owner/member 역할).
- REQ-GC-R2: 멤버끼리 사람-사람 채팅(멘션 없는 메시지는 LLM 미호출, DB 기록만).
- REQ-GC-R3: `@assistant` 멘션 시에만 LLM 응답. 호출 actor = 발신 멤버.
- REQ-GC-R4: `@account` 멘션(주의 환기) — LLM 미호출.
- REQ-GC-R5: LLM 은 멘션 시 사람-사람 채팅 포함 히스토리를 발신자 라벨과 함께 맥락으로 받음.
- REQ-GC-R6: 첨부는 그룹 전원 열람·다운로드 공유. 단 LLM 맥락 주입은 @assistant 발신자 본인 첨부로 한정(권한상승 방지, CSO F1).
- REQ-GC-R7: 접근제어 분리 — 멤버는 datasource 권한 없어도 전체 열람 가능. @assistant 로 datasource 발화/쿼리는 발신자 본인 RBAC 로만 게이트.
  - 구현(gc-participant-product-select): 참가자(비-owner 멤버)는 대화 공통 고정 제품 접근권이 없어도 **본인 권한 제품**을 per-message 로 골라 발화 가능(발신자 본인 RBAC 게이트, 권한 상속 아님). 대화 공통 바인딩은 비파괴(PATCH 는 owner 전용 유지). 접근 불가한 생성자 고정 제품은 작업화면 드롭업에서 '열람 전용' 회색·비활성 그룹으로 분리 표시.
- REQ-GC-R8: read-state(last_read 커서) + @mention 표시 + per-conversation 동시실행/비용 상한.

## 3. In Scope
- `conversation_members` 멤버십 테이블. **참여(join)는 공유 링크('참여 허용' 토글, 기본 ON)로 일원화**
  (`POST /api/share/{token}/join`). username 직접 초대 + 멤버 패널은 **제거됨**(CHG-20260623-0013).
  roster 조회(GET)·제거/나가기(DELETE) 엔드포인트는 API 로 유지.
  - **'참여 허용' 토글은 대화 생성자(owner)만 설정 가능**(CHG-20260624T081516-gc-share-joinable-guard).
    비소유자는 FE 에서 체크박스 비활성 + 발급 시 joinable 강제 false, backend `create_conversation_share`
    가 `joinable=true && !owner` 를 403 으로 차단(이중 방어, owner 판정 fail-closed). admin 예외 없음(D2).
- `core_messages.sender_account_id`(발신자 귀속) + `thread_root_message_id`(스레드 컬럼 훅, 동작 미연동).
- 멘션 파싱(FE/BE canonical 공유) + @assistant 만 ask_jobs enqueue(actor=발신자).
- 멤버십 기반 열람 접근제어(전 conversation-scope 엔드포인트 IDOR 방지).
- 발신자-한정 첨부 LLM 주입, 구조적 sender 라벨 + sanitize + 연속 user 턴 병합.
- read-state 커서·@mention 표시·폴링 동기화. **(구현 gc-unread-badge, 2026-06-25)**: 멤버별
  `conversation_members.last_read_message_id` 커서 + 사이드바 **안 읽은(새) 메세지/@멘션 배지**
  (형식 `<안읽음>[ / @<멘션>]`, 그룹 대화 한정, 본인 발신 제외) + 읽음 API(`POST /api/conversations/{cid}/read`).
  **(보정 gc-unread-baseline, 2026-06-25)**: last_read baseline 은 가입/배포 *이전* 메세지를
  읽음으로 간주한다 — 멤버 가입 시 `add_member` 가 가입 시점 `MAX(core_messages.id)` 로 커서를
  초기화하고, 기존 데이터는 alembic 0020 이 대화별 `MAX(id)` 로 backfill. 따라서 배지는 "읽지
  않은 *신규* 메세지"만 센다(과거 전체 메세지가 unread 로 잡히지 않음). 메세지 0건 대화는 NULL→첫 메세지부터 unread.
  **(보정 gc-unread-read-fix, 2026-06-25)**: 대화를 보면 읽음 커서를 최신으로 전진시켜 배지가 0
  이 된다 — 첫 전환(`selectConversation`)·**재선택**·**페이지 복원/갱신**(`refreshWorkspace`)·활성
  대화 새 메세지 도착(`_liveSyncTick`) 전 경로에서 `_markActiveConversationRead` 호출(복원/재선택
  경로 누락을 보정 — 그 전엔 새로고침으로 복원된 대화가 아무리 봐도 배지가 안 줄었다).
- per-conversation run cap + llm_usage actor 귀속.
- 멤버 add/remove + @assistant actor 감사(audit) 액션.

## 4. Out of Scope (deferred / accepted-risk)
- **풀 스레드 UI + 스레드별 AI run 병렬화** — 별도 계획(S6). run-status KV 가
  `(conversation_id, key)` 단일 키라 스레드별 run 은 `(conversation, thread)` 재키잉이
  필요(ENG #1). v1 은 thread_root 컬럼만 추가하고 run 직렬화는 **대화당** 유지.
- WebSocket/pubsub 실시간 — v1 은 폴링으로 충분.
- ~~공개 링크 참여 — account 직접 초대로 대체~~ → **반전(CHG-20260623-0013)**: 참여는 공유 링크
  '참여 허용'(기본 ON)으로 일원화, username 직접 초대 폐지. [수용 위험] 조인가능 링크 보유자는 누구나
  참여→대화 전체 열람(AR-1 연장, 사용자 결정).
- **[수용 위험] view ≠ invoke 데이터 노출**: 무권한 멤버가 방 안에서 권한 멤버가 생성한
  실제 datasource 쿼리 결과·SQL 을 열람(의도된 RBAC 우회, 사용자 sign-off). docs/SECURITY.md 참조.
- **[수용 위험] fork 반출**: 무권한 멤버가 그룹대화를 fork 하면 그 결과를 본인 소유 사본에
  영구 반출 + 추방 후에도 보유(CSO F3, 사용자 "전체 fork 허용" 선택). docs/SECURITY.md 참조.

## 5. Inputs
- 멤버 초대/제거 요청(owner 또는 `conversation.member.manage` 권한 보유 actor).
- 채팅 메시지(멘션 토큰 `@assistant`/`@account` 포함 가능).
- `@assistant` 발화 + 선택적 첨부(발신자 본인 것만 LLM 주입).
- read cursor 갱신(last_read_message_id).

## 6. Outputs
- 멤버십 변경 + audit 이벤트(member.add/remove).
- 사람 채팅 메시지(role=user, sender_account_id, ask_jobs 미경유).
- @assistant 응답(role=assistant) + conversation.ask audit(actor=발신자).
- 멤버별 unread/멘션 표시 상태.

## 7. Main Flow
```
멤버 메시지 전송
   │
   ├─ @assistant 미포함 ─► core_messages INSERT(role=user, sender_account_id) ─► 폴링으로 타 멤버에 표시 (AI 미호출)
   │
   └─ @assistant 포함 ───► core_messages INSERT(sender) ─► actor RBAC 게이트(datasource)
                              │                                  │ 통과
                              │                                  ▼
                              │                          ask_jobs enqueue(account_id=발신자)
                              │                          per-conversation run cap 검사
                              │                                  ▼
                              │                          ask-worker: 히스토리(발신자 라벨) +
                              │                          발신자 본인 첨부만 주입 ─► LLM ─► assistant 메시지
                              ▼
                          무권한 datasource ─► 발화 거부(열람은 유지)
```

## 8. Edge Cases
- 멤버 제거 중 in-flight ask_job(완료까지 honor) / 제거 후 메시지·첨부 잔존(tombstone author).
- 연속된 사람 메시지 다수 후 @assistant → Anthropic role 교대 제약 → 단일 user 턴 병합.
- 동일 대화 동시 @assistant 다수 → per-conversation cap + 대화당 run 직렬화.
- 빈 멤버십 / owner 탈퇴(소유권 이전 또는 마지막 멤버 처리).
- backfill: 기존 단일소유 대화 → owner member 1건, 기존 메시지 sender=owner(멱등).

## 9. Error Handling
- 무권한 datasource 발화: 사용자에게 "권한 없음" 표시(열람은 유지), 재시도 불가.
- cap 초과: "AI 응답 중/대기" 표시, 큐잉 또는 부드러운 거부.
- 멘션 파싱 실패: 일반 메시지로 처리(LLM 미호출), silent fail 금지.
- backfill 부분 실패: 멱등 재실행 가능, MySQL 권위 우선.

## 10. Dependencies
### 내부 기능 의존성
- feature-0002-agent-core (core_conversations / core_messages 스키마, ask-worker, 히스토리 로드, 첨부 주입)
- feature-0003-agent-web-ui (app.py 엔드포인트, RBAC, 멤버 관리·멘션·UI, audit)

### 외부 의존성
- MySQL 8.0 + PostgreSQL (dual-write, AR-M4 cutover 진행 중)
- Bedrock Anthropic (LLM)

### shared 모듈 의존성
- 없음 (cross-feature 편집은 MODIFY.md 로 추적)

## 11. Acceptance Criteria
- AC-GC-A1: 한 대화에 2명 이상 멤버가 참여하고 서로의 메시지를 본다.
- AC-GC-A2: 멘션 없는 메시지는 ask_jobs 에 들어가지 않는다(LLM 미호출).
- AC-GC-A3: `@assistant` 메시지만 LLM 응답을 트리거하고 actor=발신자다.
- AC-GC-A4: LLM 응답이 사람-사람 채팅 맥락을 반영한다(발신자 라벨 포함 eval).
- AC-GC-A5: 무권한 멤버가 대화 전체를 열람하나 `@assistant` datasource 발화는 거부된다.
- AC-GC-A6: 멤버 A 의 첨부가 멤버 B 의 @assistant 실행 맥락에 주입되지 않는다(F1).
- AC-GC-A7: 멤버십 게이트가 history/attachments/download/steps/search/ask-status 전 엔드포인트에 적용된다(IDOR 부재).
- AC-GC-A8: 멤버 초대/제거가 owner 또는 `conversation.member.manage` 권한으로만 되고 audit 에 남는다.
- AC-GC-A9: per-conversation run cap 이 동작하고 llm_usage 가 actor 에 귀속된다.
- AC-GC-A10: read-state 커서 + @mention 표시가 멤버별로 동작한다.
- AC-GC-A11: backfill 후 기존 1:1 대화·fork·share-link 가 무회귀로 동작한다.
- AC-GC-A12: 멘션 자동완성이 방 멤버 roster 로 한정된다(전역 계정 검색 금지, F7).

## 12. Observability
- audit: `conversation.member.add` / `conversation.member.remove` / 기존 `conversation.ask`(actor 기록).
- llm_usage actor 귀속(방 단위 비용 오귀속 방지).
- per-conversation run cap 도달 로그.

## 13. Pre-approved Changes
- feature-0002 / feature-0003 src 의 cross-feature 편집(스키마·app.py)은 본 feature 의 MODIFY.md 로 추적하며 사전 승인 범위에 포함.

## 14. 수용 위험 (Accepted Risks — 사용자 명시 sign-off)
- **AR-1 (view ≠ invoke 노출)**: 대화 멤버는 datasource 권한이 없어도 권한 멤버가 생성한
  실제 쿼리 결과·SQL 을 방 안에서 열람한다. 의도된 RBAC 우회. 통제: 멤버 add/remove 감사로
  "누가 누구를 노출시켰는가" 추적.
- **AR-2 (fork 반출)**: 무권한 멤버가 그룹대화를 fork 하면 그 결과를 본인 소유 사본으로
  영구 반출하고 추방 후에도 보유한다. 사용자 "전체 fork 허용" 결정. fork 시 결과 스크럽은
  하지 않음(view≠invoke 의 자연스러운 연장으로 수용).
- 두 위험은 docs/SECURITY.md 에 등재하고, 운영자에게 "그룹대화 초대 = 데이터 노출 행위"임을
  UI 에서 1줄 고지한다.
