---
doc_type: REVIEW
feature_id: feature-0009-group-conversation
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260619-0001
- Related Change: 계획 검증 (구현 전) — `/plan-eng-review` + `/cso`
- Reason: Critical 기능(인가·cross-account·스키마 마이그레이션) — 코드 진입 전 아키텍처·보안 검증.
- Alternatives Considered:
  - 스레드: Discord형 sub-channel(무거움, run-status 충돌) vs Slack형 컬럼 훅 → Slack형 채택, v1 보류.
  - AI 트리거: 매 메시지 호출 vs @mention 게이팅 → @mention(사람 채팅 1급).
  - 결과 가시성: 완전 RBAC 격리 vs view≠invoke → view≠invoke(사용자 결정).
- Risks (검증 도출):
  - ENG: 스레드 per-thread run 이 KV run-status `(conversation_id,key)` clobber → v1 스레드 보류로 회피.
  - CSO F1(P1): 공유 첨부 → actor 실행 LLM 권한상승 → **첨부 LLM 주입을 발신자-한정**으로 차단(사용자 결정).
  - CSO F2(P1): 초대=exfil 행위 → owner/`conversation.member.manage` 게이트 + audit(S2).
  - CSO F3(P1): fork 반출 → **전체 fork 허용**(수용 위험 AR-2, 사용자 결정, FUNCTION.md §14).
  - CSO F4~F7: audit·cost cap·IDOR 전수·멘션 roster 한정 → 슬라이스 통제로 편입.
- 검증 verdict: ENG = SHIP-WITH-FIXES, CSO = SHIP-WITH-FIXES(P1 차단/수용 처리).
- Open Questions: production write-path(MySQL primary vs PG)의 sender 쓰기 위치(S3 전 확인).
- Human Approval Needed: 완료 — PLAN-APPROVED(실행 진입 S1) + AR-1/AR-2 수용 위험 sign-off + F1 발신자-한정·F3 전체fork 결정.

## REV-20260619-0002
- Related Change: CHG-20260619-0001 (S1 Foundations 구현)
- Reason: 비파괴 스키마·모듈 추가의 안전성 확인.
- Alternatives Considered: 멤버십 모듈 위치 — feature-0009/src vs feature-0002/modules → import 관행(`from modules.x`) 따라 feature-0002/modules, ownership 은 본 unit MODIFY 로 추적.
- Risks: 없음(nullable 컬럼·신규 테이블·미호출 backfill, write 무변경). MySQL parity 는 try/except 멱등.
- Open Questions: backfill 호출 wiring 시점(S2 초입, schema-ensure 직후).
- Human Approval Needed: 아니오 (Minor 비파괴 추가, PLAN-APPROVED 범위 내).

## REV-20260619-0003 [SUBAGENT: S1 diff + design 검증 패널 §18.8]
- [SUBAGENT: design+code grounding] 본 cycle 에 독립 subagent 2회 가동: ① eng-review
  outside-voice(staff-eng) 가 실제 코드(runtime_backend.py·ask_jobs.py·app.py authz·schema)
  를 읽고 RESCOPE→3 P1 적발(run-status clobber·결과누출·read-state) → 계획 반영. ② cso
  grounding subagent 가 audit/share/ask-actor/attach-scope/fork/rate 코드를 file:line 으로
  확인 → F1~F7 도출 → 계획 반영. 두 verdict = SHIP-WITH-FIXES.
- [SUBAGENT: S1 diff] S1 diff 전용 verifier 는 세션 한도로 미완(0 토큰). 대체 self-verify:
  py_compile(group_members.py·test·app.py) OK + 단위테스트 10/10 통과 + 신규 컬럼 nullable
  (`_PG_INSERT_CORE_MESSAGE` 무영향) + backfill 미wired(write·behavior 무변경) + FK
  ON DELETE CASCADE 가 기존 core_messages FK 패턴과 동형 → 기존 1:1 대화 무회귀.
- 결론: S1 (비파괴 additive) SHIP. 잔여 P1 통제(F2 audit·IDOR 전수·actor 발화 게이트)는
  S2~S4 슬라이스에서 검증.
- Human Approval Needed: 아니오 (S1 비파괴, PLAN-APPROVED 범위).

## REV-20260619-0004 [SUBAGENT: S2 membership 검증 패널 §18.8]
- Related Change: CHG-20260619-0002 (S2 Membership 백엔드)
- Reason: 접근제어 변경(보안 민감) — 멤버십 OR 이 IDOR 우회/과다노출을 만들지 않는지 확인.
- 검증: ① 본 cycle 의 cso 패널이 이미 "view ≠ invoke"·F6(멤버십 OR 전 엔드포인트 적용) 을
  코드 grounding 으로 리뷰. ② 본 cycle F6 IDOR sweep 직접 수행 — VIEW 게이트 19곳이 중앙
  `_account_can_access_conversation`(멤버십 반영) 경유 확인, owner-직접 잔존 4곳 분류(ask·
  update_product·fork 는 발화/mutation→S3/S4 의도적 owner-only; 멤버 엔드포인트는 manage
  게이트). **첨부 헬퍼(`_account_can_access_attachment`) 갭 적발→멤버십 OR 추가**(첨부 전원공유
  REQ-GC-R6). ③ py_compile OK + 소스-계약 7/7 + group_members 10/10. (diff 전용 독립 subagent 는
  세션 한도로 미완 — self+패널 대체.)
- Risks: 발화 경로(ask/fork/update_product)는 아직 멤버 미허용(owner-only) — 의도된 S3/S4 경계.
- Open Questions: roster UI(프론트) 미구현 — S2 잔여(다음 turn).
- Human Approval Needed: 아니오 (additive view-access, PLAN-APPROVED 범위).

## REV-20260619-0005 [SKIPPED: S3 멘션 파서 — pure additive primitive, 미배선]
- Related Change: CHG-20260619-0003 (canonical 멘션 파서)
- Reason: 패널 skip 사유 — 어떤 흐름에도 미배선된 순수 함수(behavior 무변경). 소비처 0.
- 검증: BE 단위 3/3 + FE↔BE parity 14/14(node, 동일 _CANONICAL_CASES 표) + py_compile.
  divergence 위험(eng/cso 지적)을 ASCII-explicit lookbehind + 공유 케이스표로 구조적 차단.
- Risks: 없음(미배선). 배선(enqueue 게이팅·발신자 라벨·F1 첨부주입)은 behavior-changing →
  그 chunk 에서 정식 패널.
- Human Approval Needed: 아니오.

## REV-20260619-0006 [SUBAGENT: S3 backend core (sender·chat·F1) §18.8]
- Related Change: CHG-20260619-0004
- Reason: F1(첨부 주입 발신자-한정)은 보안 변경(권한상승 차단) — 1:1/fork 무회귀 + 그룹 격리 확인.
- 검증: ① 본 cycle cso 패널이 F1 "발신자-한정 주입" 을 정확히 처방(사용자 결정 채택). ② self-verify:
  `_scope_by_conv = bool(conversation_id) and not (force_sender_scope and account_id)` — force_sender_scope 는
  `_is_group_conversation`(멤버 count>1) 일 때만 True → 1:1(count≤1)·미백필(count0)·fork 는 conversation
  스코프(TASK-0284) 보존, 그룹만 account_id(발신자) 스코프. guard(`not account_id and not _scope_by_conv`) 무손상.
  ③ py_compile + 회귀 20/20. sender_account_id·채팅 엔드포인트는 nullable/additive(무회귀).
- Risks: 멤버 @assistant 호출은 아직 owner-gate(의도) — S4 에서 actor RBAC 로 확장 시 재검증.
- Open Questions: S3c(히스토리 발신자 라벨) 미구현 — 그룹 @assistant 가 S4 에서 켜질 때 함께 필요.
- Human Approval Needed: 아니오 (F1=보안 강화·그룹한정, 나머지 additive, PLAN-APPROVED 범위).
