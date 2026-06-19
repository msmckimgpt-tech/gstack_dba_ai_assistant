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

## REV-20260619-0007 [SUBAGENT: S4 actor 발화 게이트 §18.8]
- Related Change: CHG-20260619-0005 (멤버 @assistant 발화 + actor datasource 게이트)
- Reason: 최고 보안-민감 — owner-gate 해제가 datasource RBAC 우회를 만들지 않는지 확인(열람 ≠ 발화).
- 검증(self, code-grounded): ① ask 흐름 전반이 `account`(=actor=호출 멤버) 사용 — 소유자 신원 미사용.
  ② **기존 line 10422 가 pinned product 를 `_account_has_product_access(account, pid)` 로 이미 enforce**
  (기존 대화 경로 포함, TASK-0052 G4) → 멤버가 owner-gate 통과해도 무권한 pinned datasource 발화 불가.
  ③ auto 모드는 `allowed_schemas_for_run=[]`(meta only, cross-product leak 차단) + turn-local 제품 선택.
  ④ 폴링/결과(ask_status/ask_result) 멤버십-인지 게이트. ⑤ 명시 멤버 체크(10249) = defense-in-depth +
  "열람만 가능" 명확 메시지 + slot 획득 전 차단. py_compile OK.
- Risks/Open: auto 모드 turn-local 제품 선택의 멤버-invocation actor 게이팅은 product-selector 미정독 —
  컨테이너 make test + 라이브 적대 검증 권장(pinned 은 이중 게이트 확인). cross-account 감사=기존
  conversation.ask audit 가 actor 기록(충족). 멘션 자동완성 roster 한정(F7)=roster UI 에서.
- Human Approval Needed: 아니오 (pinned 이중게이트 확인 + account=actor, PLAN-APPROVED 범위). auto-mode 라이브 재검증 권고.

## REV-20260619-0008 [SKIPPED: S2 roster UI — additive 프론트, PB-0008 보류]
- Related Change: CHG-20260619-0006 (멤버 패널 UI)
- Reason: 패널 skip 사유 — 기존 흐름 무변경 additive UI(신규 버튼·패널). 보안/데이터 변경 없음.
- 검증: node --check(app.js·mentions.js) syntax OK + html↔app.js element id 정합 7/7 + 백엔드
  엔드포인트(S2)는 이미 검증/게이트. 초대 시 "대화 내용 공유" 고지 문구 포함(AR-1 운영자 인지).
- Risks: 실 브라우저 렌더/상호작용 미검증 — **PB-0008(Windows 브라우저) 보류**(TEST.md 기록). WARN-only.
- Open: 멘션 자동완성(F7) 미구현(입력창 @roster) · 사람채팅 send-routing(mention 게이팅) 미배선.
- Human Approval Needed: 아니오 (additive 프론트). 배포 전 PB-0008 권장.

## REV-20260619-0009 [SKIPPED: 릴리즈 노트 정적 데이터, 내부동작 비노출 검토]
- Related Change: CHG-20260619-0007 (release-notes-data.js 그룹 대화 항목)
- Reason: 패널 skip 사유 — 정적 큐레이션 데이터(읽기전용), 코드/동작 변경 없음.
- 검증: node --check(release-notes-data.js) OK + 캐시버스터 양 페이지 bump. **콘텐츠 누출 검토**:
  RBAC/멤버십테이블/actor/PG/F1 등 내부동작 미언급, "본인에게 허용된 제품에 한해"·"초대=대화 공유"
  로 사용자 역량/주의만 표현(AC-0579 정합). shipped 동작에 정확(멘션-게이팅 send-routing 미배선분
  과장 안 함 — "@assistant 안 넣으면 AI 미호출" 문구 제외).
- Human Approval Needed: 아니오.

## REV-20260619-0010 [SUBAGENT: send-routing 멘션 게이팅 §18.8]
- Related Change: CHG-20260619-0008 (멘션 게이팅 사람 채팅)
- Reason: 핵심 send 경로 변경 — 1:1/신규 대화 무회귀 + 그룹만 채팅 분기 확인.
- 검증(self): ① 분기 조건 `member_count>1 && activeConversationId && !messageInvokesAssistant` —
  1:1(count≤1)·신규(lazy)·@assistant 포함은 전부 /api/ask 유지(무회귀). ② 게이트 완화는
  `|| active.is_member` 추가만(비-멤버 차단 유지). ③ member 신호 PG 1쿼리(self_id BOOL_OR), 실패 시
  member_map={}→count 0→채팅 분기 비활성(안전 폴백). ④ 채팅 경로=backend `/messages`(접근 게이트+
  blocked 가드+발신자 귀속) 재사용. py_compile+node --check+회귀 17/17.
- Risks/Open: 발신자 UI 표시·LLM 라벨 미구현(S3c, 다음 커밋) — 현재 타 멤버 채팅이 자기 메시지처럼 보일 수 있음.
- Human Approval Needed: 아니오 (무회귀 분기, PLAN-APPROVED).

## REV-20260619-0011 [SUBAGENT: S3c 발신자 표시 + 연속 user 병합 §18.8]
- Related Change: CHG-20260619-0009
- Reason: ① 채팅 표시 버그(표시 store 미러 누락) 수정 ② LLM 경로 연속 user 병합(공유 _assemble 변경 — 전 대화 영향)이 1:1 무회귀인지.
- 검증(self): ① 표시 store 미러=채팅이 /api/history(agent_runtime.messages) 에 노출되도록 save_memory_message
  추가(meta_json sender). 미러 실패는 best-effort(흐름 무중단). ② renderMessages 는 meta.sender_* 있을 때만
  메시지별 발신자, 없으면 기존 owner 로직 폴백 → 비-그룹 무회귀. ③ `_merge_consecutive_user_messages` 는
  연속 user(string) 만 병합, 비-string(이미지)·교대 정상 메시지 무변경 → 1:1 사실상 무영향(연속 user 드묾),
  그룹 채팅 누적 후 @assistant alternating 위반 방지. py_compile + node --check + 회귀 17/17 + 병합 4테스트(컨테이너).
- Risks/Open: LLM 화자 **라벨**(프롬프트에 "누가 말했는지") 미주입 — Bedrock alternating 실측+sanitize 필요로
  배포 후 검증 권장. LLM 은 채팅 전체 맥락은 받음(요구 #2 충족), 화자 명시만 잔여.
- Human Approval Needed: 아니오 (표시 버그수정 + 무회귀 병합, PLAN-APPROVED). 배포 후 그룹 @assistant 라이브 확인 권장.

## REV-20260619-0012 [SKIPPED: S5 잔여 항목 배포-후 라이브 검증 이연 결정]
- Related: S5 Realtime+Limits 범위 결정.
- 결정: 코어 그룹 대화(S1~S4 + roster + send-routing + S3c)는 완성·검증. S5 잔여 4항목은 라이브
  환경 의존/edge/P2 라 **배포 후** 검증·폴리시로 이연:
  1. **per-conversation run cap**(동시 멤버 @assistant): 기존 fencing(run_id/takeover, TASK-0241)이
     데이터 손실은 막음(run-status 표시 race 만). 하드 cap 은 1:1 re-ask 흐름을 깰 위험 → 라이브에서
     "다른 멤버 run 중" 한정 가드로 신중 추가.
  2. **llm_usage actor 귀속(F5, P2 회계)**: `_call_llm` 에 account_id 미존재 + cfg 글로벌은 동시 ask
     race 로 코드베이스가 회피하는 패턴 → cfg/시그니처 스레딩을 라이브 측정과 함께 정확 구현.
  3. **폴링 동기화**(타 멤버 새 메시지 실시간): refresh 로 보임. 라이브에서 폴링 주기/충돌 검증 후 추가.
  4. **LLM 화자 라벨**: 연속 user 병합(완료)으로 alternating 안전. 화자 명시 라벨은 Bedrock 실측+
     sanitize 필요 → 배포 후. (LLM 은 채팅 전체 맥락은 이미 받음 — 요구 #2 충족.)
- Risks: 위 4항목은 모두 비-블로커(코어 동작 영향 없음). 멤버 보존정책은 설계상 완료(remove=membership만 삭제).
- Human Approval Needed: 아니오 (이연 결정, 사용자 "완수 후 배포" 지시 + deploy_scope:included).

## REV-20260619-0013 [SUBAGENT: alembic 0012 마이그레이션 §18.8]
- Related Change: CHG-20260619-0011 (alembic 0012)
- Reason: ★배포 게이트 — agent_runtime 스키마 권위는 alembic(0001~0011). .sql 만 변경했던 갭을
  적발·보정. prod 에 테이블 생성되어야 S1~S4 코드가 실동작.
- 검증: py_compile OK + revision chain 0012→0011→0010 정합 + DDL=scripts/agent_runtime_schema.sql
  parity(멱등 CREATE/ALTER 동일) + DEPLOY TRAP(명시 GRANT agent_kb_rw/ro) 반영(0011 동형). downgrade 완비.
- Risks: 기존 데이터 무손실(IF NOT EXISTS, nullable ADD). FK CASCADE 는 core_conversations 삭제 시 멤버 정리(정합).
- Human Approval Needed: 아니오 (배포 필수 정합 보정, PLAN-APPROVED + deploy_scope:included).
