---
doc_type: REPORT
feature_id: feature-0009-group-conversation
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
그룹 대화(여러 멤버 + @assistant) 기능. 계획·검증 완료 후 S1 Foundations 구현 중.
스키마(PG 정본 + MySQL parity) + 멤버십 데이터접근 모듈 + 멱등 backfill 함수 완료.

## 2. Progress
- **코어 완성(배포 대기)**: S1 Foundations · S2 Membership(백엔드+roster UI) · S3(멘션 파서·발신자 귀속·사람채팅·F1·send-routing·발신자 표시·연속 user 병합) · S4 Security(멤버 @assistant actor RBAC) · 릴리즈 노트.
- **라이브 UX 1차(PR#370 배포완료)**: 실시간 폴링(4s)·@멘션 자동완성·발신자 아바타.
- **라이브 UX 2차(gc-live-ux2, 배포완료 PR#371)**: 적응형 폴링(5s↔1.5s)·멘션 자동완성 TTL(신규 참여자 반영)·피멘션 알림(토스트+OS Notification·백그라운드)/하이라이트·assistant 제품 아이콘·사이드바 카테고리화. 전부 프론트, 캐시버스터 live-ux2. (CHG-0015/REV-0017)
- **메시지 아바타 Identicon 정합(gc-avatar-identicon, 배포완료 PR#377)**: 사용자 보고("프로필 아이콘이 글자") 해소 — `_msgAvatarEl` 을 앱 전역 `applyAvatar`/`identiconSvg` 와 정합. 캐시버스터 avatar-identicon. **PB-0008 PASS**. (CHG-0016/REV-0018)
- **멘션 하이라이트 + Windows 알림(gc-mention-hl-notify)**: 사용자 보고 2건 — ① 하이라이트 미표시(CSS 특이도 0,3,0<0,4,0) → 멘션 선택자 (0,5,0) override. ② OS 알림 제목 `DQA : {대화명}` + 본문 `[발신자] : 메시지`. 캐시버스터 mention-hl-notify. **PB-0008 실측 PASS**. (CHG-0017/REV-0019)
- In Progress: gc-mention-hl-notify docs 반영 완료 → verify-completion → PR → 배포 → smoke.
- Deferred(배포 후 라이브): S5 run cap·llm_usage actor 귀속·LLM 화자 라벨 (REV-0012) / S6 스레드(별도 계획). [폴링 동기화는 ux2 적응형으로 해소]
- 커밋: 489deb5·8ef6598·eb707e2·76da62d·2542359·fa23367·f503630·1b7ba47·5c75c84 (코어, 머지됨) + ux2(워크트리 ai/claude/gc-live-ux2, 커밋 전).

## 3. Recent Changes
- PG `agent_runtime_schema.sql`: `conversation_members` 테이블 + `core_messages.sender_account_id`/`thread_root_message_id` + 인덱스 2.
- MySQL parity: `AgentCoreConversationMembers` + `AgentCoreMessages` 컬럼(READ_BACKEND!=postgres 가드).
- 신규 `modules/group_members.py`: backfill + 멤버 read/add/remove 헬퍼.
- 신규 `tests/test_group_members.py`: 10 테스트(SQL 계약·멱등·검증·파싱).
- 총 변경 횟수: 1 (CHG-20260619-0001)

## 4. Open Issues
- backfill 호출 wiring(스키마 ensure 직후 1회 호출)은 S2 초입에서 연결 — 현재는 멱등 함수만 제공.
- production write-path(MySQL primary vs PG) 가 sender_account_id 쓰기 전(S3) 확인 필요.

## 5. Test Status
- 자동 테스트: `test_group_members.py` 10/10 통과 (FakeConn, DB 불요). py_compile(모듈·테스트·app.py) OK.
- 수동 테스트: 미수행(스키마 멱등성 실 DB 검증은 배포 환경에서).
- 미검증 항목: 실 PG 에 대한 DDL 멱등 적용·backfill 행 수(라이브 검증은 S1 배포 시).

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- push/PR 여부(현재 worktree 브랜치 로컬 커밋만). 배포는 S1 만으로는 비대상(기능 미완).

## 8. Suggested Improvements
- S3 에서 LLM 히스토리 발신자 라벨은 구조적 메타로(주입 방지), 첨부 주입은 발신자-한정 적용(CSO F1).
