---
doc_type: TASK
feature_id: feature-0009-group-conversation
task_id: TASK-20260619T023140-group-conversation
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task — 그룹 대화

## 1. Current Status
- State: in-progress (S2 Membership — 백엔드 완료, roster UI 잔여)
- Owner: AI (claude) / Human (sign-off 완료)
- Priority: high
- Risk: Critical (인가·cross-account·스키마 마이그레이션)
- Last Updated: 2026-06-19

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - feature-0002-agent-core: `src/scripts/agent_runtime_schema.sql`(PG DDL), `src/agent_core.py`(첨부 주입·히스토리 라벨), ask-worker
  - feature-0003-agent-web-ui: `src/app.py`(MySQL DDL/_ensure_*·멤버 엔드포인트·접근제어·멘션·audit·cost cap), 프론트(roster·멘션·read-state UI)
  - 신규 모듈: membership / mention 파서(app.py 밖 분리)
- **접근 방법:** Slack형(단일 메시지 스트림 + nullable 컬럼). 멤버십 테이블 추가, owner_account_id
  유지(backward-compat). actor-권한 발화 게이트 + 멤버십 열람 게이트("열람 ≠ 발화"). @assistant
  멘션만 enqueue. 첨부 LLM 주입은 발신자-한정. dual-write(MySQL 권위→PG).
- **위험도:** Critical
- **검증:** `/plan-eng-review`(outside-voice) + `/cso` 통과(SHIP-WITH-FIXES). REVIEW.md 참조.

<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-19 (실행 진입 S1 선택) -->

## 3. Task Queue (슬라이스)
- [x] **S1 Foundations** — DDL(conversation_members + sender_account_id + thread_root_message_id) + 멱등 backfill + members(account_id) 인덱스 + membership helper 모듈 (commit 489deb5)
- [x] **S2 Membership** — ✅백엔드: 멤버십 열람 접근제어(중앙 게이트 + 첨부 게이트 OR, F6 sweep) + 멤버 엔드포인트 + audit + backfill wiring + 신규 권한. ✅roster UI(멤버 버튼·패널·초대·제거/나가기, CHG-0006, PB-0008 보류)
- [ ] **S3 Chat+Mention** — ⏳ sender_account_id write 배선 · 사람 채팅(enqueue 미경유) · @assistant enqueue(actor) · LLM 히스토리(구조 sender 라벨·sanitize·연속 user 병합) · **발신자-한정 첨부 주입(F1)** · read-state 커서 · @mention 표시
  - [x] canonical 멘션 파서 (BE modules/mentions.py + FE static/mentions.js + node parity 14/14)
  - [x] sender_account_id write 배선 (save_core_message + _save_message + _run_agent_core)
  - [x] 사람 채팅 store-only 엔드포인트 (POST /api/conversations/{cid}/messages)
  - [x] F1 발신자-한정 첨부 주입 (force_sender_scope + _is_group_conversation)
- [~] **S4 Security** — cross-account 감사(기존 ask audit actor). ⏳잔여: auto-mode 라이브 적대검증 · 멘션 자동완성 roster 한정(roster UI)
  - [x] actor datasource 발화 게이트 (멤버 @assistant 허용, pinned 이중게이트, 열람≠발화 완성)
- [ ] **S5 Realtime+Limits** — 폴링 동기화 + per-conversation run cap + llm_usage actor 귀속 + 멤버 제거/보존 정책
- [ ] **S6 (deferred, 별도 계획)** — 풀 스레드 UI + run-status `(conversation,thread)` 재키잉

## 4. In Progress
- S3 멘션 배선(enqueue 게이팅·발신자 라벨·F1 첨부주입·read-state) + S2 roster UI (둘 다 잔여)

## 5. Blocked
- 없음

## 6. Done
- 계획 수립 + eng-review + cso 검증 (REVIEW.md)
- feature unit + FUNCTION.md(수용위험 포함) 작성
- S1 Foundations (commit 489deb5)
- S2 백엔드 (접근제어·멤버 엔드포인트·audit·backfill wiring·신규 권한·F6 sweep)

## 7. Next Action
- S2 roster UI: 대화 헤더에 멤버 목록·초대(username)·제거 + GET/POST/DELETE members 연동.
- 이후 S3 Chat+Mention(사람 채팅·@assistant enqueue actor·발신자 라벨·발신자-한정 첨부주입·read-state).

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다 (S1~S5 누적)
- [ ] 단위 테스트(unit test)가 통과한다
- [ ] 전체/통합 테스트가 통과하거나 사유·계획이 TEST.md §4에 기록되었다
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다 (cross-feature 편집 포함)
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] docs/SECURITY.md 에 AR-1/AR-2 수용 위험이 등재되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] Git 커밋·원격 동기화가 완료되었거나 보류 사유가 기록되었다
