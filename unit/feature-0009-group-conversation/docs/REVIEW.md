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

## REV-20260619-0014 [SKIPPED: 릴리즈 노트 개선 정적 데이터]
- Related Change: CHG-20260619-0012 (릴리즈 노트 개선 + 배포)
- Reason: 패널 skip — 정적 큐레이션 데이터(읽기전용), 코드/동작 변경 없음.
- 검증: node --check OK + 캐시버스터 양 페이지 bump. 콘텐츠=shipped 동작에 정확(send-routing 배포 완료라
  "@assistant 안 넣으면 사람끼리 대화" 가 이제 사실). 내부동작 비노출(AC-0579). Bedrock 키 교체 중이라
  @assistant *응답* 테스트는 다음 cycle(사용자 명시)이나 릴리즈 노트는 capability 기술이라 무관.
- Human Approval Needed: 아니오 (정적 데이터 배포, 사용자 명시 요청).

## REV-20260623-0015 [SUBAGENT: 공유 링크 참여(join) 전환 §18.8]
- Related Change: CHG-20260623-0013 (share-link join 일원화 + 멤버 패널/초대 제거)
- Reason: 참여 경로 교체(보안 표면 변화) — join 게이트 정합 + 초대 제거 잔존물 0 확인.
- 검증(self): ① join 게이트 = 로그인(_require_account)+활성(_share_load_active)+미revoke+미expired
  (_share_row_expired)+Joinable+대화 비차단(_conversation_block_info), 이미 멤버는 멱등 성공. actor=조인자
  본인 → 멤버십 백본(group_members.add_member) 재사용, audit conversation.member.join. ② 기본 ON(사용자
  결정): Joinable DEFAULT 1 + create `is False 일 때만 0`. 보안: 조인가능 링크 보유자는 대화 전체 열람
  (AR-1 수용 posture 일관). datasource 발화는 여전히 actor RBAC(S4) — join 이 발화권 안 줌. ③ 초대 제거
  잔존물 0(grep membersBtn/Panel/POST members = 0), s2 계약테스트 8/8, py_compile+node --check OK.
- Risks/Open: 기본 ON = 링크 유출 시 누구나 참여(사용자 명시 수용). roster 가시성/나가기 UI 없음(GET/DELETE
  API 는 유지 — 향후 재노출 가능). PB-0008 실측은 배포 후.
- Human Approval Needed: 아니오 (사용자 명시 결정: 토글 기본 ON + 멤버 패널/초대 제거).

## REV-20260623-0016 [SUBAGENT: 라이브 UX 3종(폴링·멘션자동완성·아바타) §18.8]
- Related Change: CHG-20260623-0014
- Reason: 프론트 UX 추가(핵심 send/render 경로 인접) — 무회귀 + 충돌 없음 확인.
- 검증(self): ① 폴링은 새 id 있을 때만 renderMessages, AI run/검색/숨김 시 skip, dedup(optimistic echo)
  + 스크롤 위치 보존(과거 읽는 중 방해 안 함). _liveSyncInFlight 재진입 가드. ② 멘션 keydown 은 capture+
  stopImmediatePropagation 으로 send(Enter)보다 우선, dropdown 닫힘 시 무간섭(기존 입력 무회귀). lazy 멤버
  fetch(cid 캐시). ③ 아바타는 기존 /api/avatars(404→이니셜) 재사용, meta.prepend(레이아웃 inline). node --check OK.
- Risks/Open: 멤버 캐시는 대화 전환 시 갱신(동일 대화 내 신규 참여자는 전환 전까지 자동완성 미반영 — 경미).
  폴링 4s 주기(실시간성↔부하 균형). 실 브라우저 상호작용 PB-0008 은 배포 후.
- Human Approval Needed: 아니오 (프론트 additive, 기존 엔드포인트 재사용, 사용자 요청).

## REV-20260623-0017 [SUBAGENT: 라이브 UX 2차(gc-live-ux2) 적응형 폴링·멘션 자동완성·피멘션 알림 §18.8]
- Related Change: CHG-20260623-0015
- Risk Grade: **Minor** — 전부 프론트(app.js/styles.css/index.html) additive, 인증·인가·스키마·백엔드 무변경, 기존 엔드포인트(history/members/avatars) 재사용. PLAN-APPROVED feature 의 사용자 지시 연속(가시 동작 개선). §12.3 Minor = AI 자율 진행 + REVIEW.md 기록.
- Reason: 직전 라이브 UX 1차(REV-0016)의 Open Issue 두 건(① 멤버 캐시 대화 전환 전까지 미반영 ② 폴링 4s 고정) 을 사용자 요청대로 해소 + 협업 가시성(피멘션 알림/하이라이트·발신자 식별) 보강. send/render 경로 인접이라 ux1(REV-0016)과 동일하게 적대적 패널 1회 실시.
- 패널 결과(adversarial subagent): **PASS-WITH-NITS, BLOCKING 없음**. 검증 항목: ① 적응형 폴링 — `startLiveSync` 모듈 1회 호출, 재귀 setTimeout self-sustain(중복 루프/타이머 누수 없음), `_liveSyncInFlight` 재진입 가드 유지, hidden 탭은 `state.messages`/DOM 무변경(읽기만, 복귀 시 정상 tick 동기화). ② `_liveNotifiedMaxId` — 메시지 id 가 전역 IDENTITY 단조 시퀀스라 대화 전환에도 정상, 가시·백그라운드 경로 중복/누락 알림 없음. ③ `_notifyMentions` — `sender_account_id==myId` 로 내 메시지 제외, `window.Mentions`/`Notification` 부재 시 graceful. ④ `_msgAvatarEl` 4번째 인자 — 단일 호출부(3461) 4-arg 호출, optional 호환. ⑤ 멘션 TTL — cid 불일치 시 stale 멤버 비노출, in-flight 중복 fetch 차단. ⑥ `item.is_member` — 백엔드가 항상 boolean 으로 채워 1:1/레거시 회귀 없음. ⑦ XSS 없음(textContent/Notification body 문자열, 하이라이트는 class 부여만). 캐시버스터 app.js/styles.css `live-ux2` 일관 bump. `node --check` OK.
- 적발 NIT 3건(전부 cosmetic): (a) assistant 배지가 비-pinned 대화에서 "AI"→"A" → **수정함**(`_assistantLabel` 비-pinned 시 ""→`_msgAvatarEl` 이 "AI" 폴백, 기존 UI 보존). (b) `.is-mention-me` 의 `prefers-color-scheme: dark` 오버라이드는 앱이 고정 light 팔레트라 미세 불일치 — 무해, 유지. (c) `.message.is-mention-me .bubble` dead selector(실 클래스 `.message-bubble` 가 적용) — 무해, 유지.
- Risks/Open: OS Notification 권한 거부/미지원 환경은 토스트로 graceful degrade(설계). 적응형 폴링 하한 1.5s 는 활성 대화 한정(idle 복귀 5s) — 부하 경미. 실 Windows 브라우저 상호작용(PB-0008)·멀티 유저 라이브 검증은 배포 후(ux1 동일 정책).
- Human Approval Needed: 아니오 (Minor·프론트 additive·사용자 명시 요청, 패널 BLOCKING 없음).

## REV-20260623-0018 [SUBAGENT: 그룹 대화 프로필 아바타 Identicon 정합(gc-avatar-identicon) §18.8 + PB-0008]
- Related Change: CHG-20260623-0016
- Risk Grade: **Minor** — 전부 프론트(app.js/styles.css/index.html + 테스트 시나리오) additive, 인증·인가·스키마·백엔드 무변경, 기존 엔드포인트(/api/avatars) 재사용. §12.3 Minor.
- Reason: 사용자 보고 — 그룹 대화 메시지 프로필 아이콘이 실제 이미지가 아닌 "맨 글자". Root cause = 앱 전역 `applyAvatar`/`identiconSvg` 는 미업로드 시 Identicon 폴백인데 그룹챗 `_msgAvatarEl` 만 bare initial 폴백(불일치, 라이브 DB 로 확인: 37계정 중 1개만 아바타). 동일 Identicon 폴백으로 정합.
- 패널 결과(adversarial subagent): **PASS-WITH-NITS, BLOCKING 없음**. 검증: ① XSS 안전 — `identiconSvg(seed)` 는 seed 를 `_identiconHash`(DJB2 숫자)로만 사용, raw username 이 SVG 마크업에 미삽입(제품칩/applyAvatar 와 동일 패턴). ② onerror 루프 없음 — img 1개 제거 후 SVG/텍스트 주입, svg 엔 error listener 없음. ③ 단일 호출부(3470) 5-arg 호환. ④ auto 모드(`_assistantSeed=""`+icon="") → "AI" 배지 유지. ⑤ CSS `.msg-avatar > svg` 가 22px 원형 채움, `.has-img` 가 SVG 가림 없음. ⑥ 실제 아바타 계정(id35) 회귀 없음(error 시에만 identicon). ⑦ `identiconSvg`/`_identiconHash` 무변경 → 헤더/프로필과 동일 시드=동일 아이콘(정합 목적 달성). NIT 2건(cosmetic, 무해 유지): assistant degenerate(product_key 빈 값) 시드 발산 / own-message 폴백 title 로컬라이즈.
- **PB-0008 실측 검증(실제 Windows Chrome, relay@9223)**: scenario `tests/win-browser-avatar-identicon.scenario.json` 실행 PASS. `_msgAvatarEl` 기능 — 무아바타 user=`identicon`, id35=`img:/api/avatars/35`, assistant(auto)=`text:AI`. 실제 대화 메시지 아바타 kinds=`[identicon, AI]`. 증거: `artifacts/pb0008-avatar-identicon/01_avatar_strip.png`(mckim2/mckim3/review_user01/admin/operator 고유 Identicon + id35 실제 이미지 + bootstrap_admin 프로필 Identicon 정합), `02_conversation_avatars.png`. TEST.md §3 Run 2026-06-23-gc-avatar-identicon 기록.
- Risks/Open: 없음. 사용자 보고 결함 해소 + 실측 검증 완료.
- Human Approval Needed: 아니오 (Minor·프론트 additive·사용자 명시 요청·PB-0008 PASS).

## REV-20260623-0019 [SUBAGENT: 멘션 하이라이트 표시 버그 + Windows 알림 형식 재구성(gc-mention-hl-notify) §18.8 + PB-0008]
- Related Change: CHG-20260623-0017
- Risk Grade: **Minor** — 전부 프론트(styles.css/app.js/index.html + 테스트 시나리오) additive, 인증·인가·스키마·백엔드 무변경. §12.3 Minor.
- Reason: 사용자 보고 — ① 멘션 하이라이트 미표시 ② Windows 알림 형식(제목 `DQA : 대화명`, 본문 `[발신자] : 메시지`). ① Root cause = CSS 특이도 충돌(멘션 0,3,0 < 타멤버 0,4,0 → background·border override). ② 알림 제목/본문 문자열 재구성.
- 패널 결과(adversarial subagent): **PASS, BLOCKING 없음**. 검증: ① 타멤버 멘션 메시지는 항상 `message is-user is-other-message is-mention-me` 4클래스(app.js `is-mention-me` 는 `!msgIsOwn` 조건 → `is-other-message` 동반) → 새 선택자(0,5,0)가 충돌 규칙(0,4,0) 정상 override, `border-left:3px` 는 단축 `border:1px` 중 좌측만 덮고 top/right/bottom 유지. `is-pending` 은 assistant 전용이라 클래스 집합 상호배타(충돌 없음). ② `currentConversation()` 는 `_notifyMentions` 호출 시점(라이브 tick·hidden 경로) `state.activeConversationId`(폴링 대상) 기준 → 올바른 대화 반환, null 시 `DQA` 폴백. body XSS 불가(`showToast`=textContent, Notification body=plain text). 다중 멘션 `[who] 외 N건 : preview` 스펙 일치. high-water·내 메시지 제외 로직 무변경. NIT 1건(cosmetic): empty content 시 dangling separator(기존 동일).
- **PB-0008 실측 검증(실제 Windows Chrome, relay@9223)**: scenario `tests/win-browser-mention-hl-notify.scenario.json` PASS. ① 하이라이트 computed style — 멘션 버블 `border-left 3px rgb(245,158,11)` + `background rgba(245,158,11,0.16)` vs 일반 타멤버 `1px 회색`+`흰색`, `highlightDiffers:true`. ② 알림 Notification stub 캡처 — title=`DQA : 운영 이슈 대응방`, body=`[mckim2] : @bootstrap_admin 이거 확인 부탁드려요`. 증거: `artifacts/pb0008-mention-hl-notify/01_highlight.png`(상단 멘션 버블 앰버 틴트+좌측 강조선 육안 확인). TEST.md §3 Run 2026-06-23-gc-mention-hl-notify.
- Risks/Open: 없음. 사용자 보고 2건 모두 해소 + 실측 검증 완료.
- Human Approval Needed: 아니오 (Minor·프론트 additive·사용자 명시 요청·PB-0008 PASS).

## REV-20260623-0020 [SUBAGENT: 그룹대화 4종(보유자 authz·공유후 오호출·사이드바 가시성·공유시 그룹전환) §18.8 + PB-0008]
- Related Change: CHG-20260623-0018
- Risk Grade: **Major** — 백엔드 인가(#1 owner-only) + 메시지 라우팅(#2) + 스키마 마이그레이션(#4 is_group) + 프론트(#3). 보안 인접. 사용자 명시 4건 + #4 메커니즘(영구 플래그) 사전 확인. §7.1 Plan-Review-Execute → §12.3 Major.
- 사전 조사(4영역 병렬): #2 진짜 원인 = owner 가 conversation_members 미삽입(member_count under-count), #1 = `_account_can_access_conversation` 열람게이트가 멤버 통과(IDOR류), #4 = 그룹 신호가 member_count>1 뿐.
- 패널 결과(adversarial 3렌즈 subagent): **PASS-WITH-NITS, BLOCKING 없음**. authz(admin .any 우회 보존·owner 통과·0/NULL 오매칭 불가·일괄 delete 커버·1:1 무회귀) / 라우팅·스키마(0016 체인 정합·무손실·헬퍼 분기·add_member owner 강등없음·422 신규대화·멘션 오발동 없음·mentions parity·defensive 쿼리 폴백) / 프론트(isGroupConversation 폴백·배지 XSS무관·422 토스트). **반영 nit**: ① NULL-owner lockout → 게이트 `owner_id is not None and owner_id!=actor` fail-open. ② 배지 1명표기 → 칩 `_gn>1`, 1명은 아이콘만.
- **PB-0008 실측(실제 Windows Chrome, relay@9223)**: scenario `tests/win-browser-group-authz.scenario.json` PASS. 공유 → `is_group:false→true`·`isGroupConversation()=true`(#4); 그룹+비멘션 `/api/ask`→`422 group_requires_mention`(#2 미실행); owner 리네임→`200`(#1 무회귀); 사이드바 `group_badge_count:1`(#3). 증거 `artifacts/pb0008-group-authz/01_sidebar_group_badge.png`.
- 단위 테스트 무회귀: group_members 10/10·mentions 3/3·s2 8/8·history_merge 4/4.
- Risks/Open: 기존 joinable 공유 대화는 다음 join/share 시점 전환(retroactive backfill 없음, member_count>1 OR-branch 보강). 배포 시 alembic 0016 필수.
- Human Approval Needed: #4 메커니즘 사용자 확인 완료. 그 외 사용자 명시 요청 범위.

## REV-20260624-0021 [SUBAGENT: 공유 직후 메시지 사람채팅 전환(gc-share-group-sync) §18.8 + PB-0008]
- Related Change: CHG-20260624-0019
- Risk Grade: **Minor** — 전부 프론트(app.js/index.html) additive, 백엔드·스키마 무변경. CHG-0018 클라이언트 stale 잔여 윈도 보강. §12.3 Minor.
- Reason: 사용자 보고 — 공유 직후 메시지가 assistant 로 오라우팅돼 422 block. Root cause = 공유 후 클라 active.is_group stale(false) → /api/ask → 서버 422. 수정 = ① 공유 시 로컬 is_group 즉시 전환(primary) ② 422 graceful store-only 재라우팅(safety net, 메시지 유실 없음).
- 패널 결과(adversarial subagent): **PASS-WITH-NITS, BLOCKING 없음**. catch reroute↔finally(busy/abort) 충돌 없음(_sendGroupChatMessage busy 미터치, return→finally 단일 정리); 무한루프 없음(store-only 엔드포인트 422 미발생); `_reCid=targetConvId`(422 는 기존 대화만, isLazyCreate=false); apiFetch 토스트 제거 안전(/api/ask 유일 호출자=sendPrompt); createConversationShare optimistic try/catch·joinable!==false 정확. **반영 nit**: 재라우팅 중복 user 버블 flicker → optimistic user 메시지 splice.
- **PB-0008 실측(실제 Windows Chrome, relay@9223)**: scenario `tests/win-browser-share-group-sync.scenario.json` PASS. 공유 후 is_group=false 강제(stale 재현) → 비멘션 sendPrompt → `reroute_no_error_toast:true`·`conv_is_group_after:true`·`composer_cleared:true`·`pendingBubble_null:true`·사람채팅 저장. 증거 `artifacts/pb0008-share-group-sync/01_share_then_send_chat.png`(파란 사용자 채팅 버블, assistant 응답·오류 없음).
- Risks/Open: 없음. block/오류 제거 + 메시지 유실 없음.
- Human Approval Needed: 아니오 (Minor·프론트 additive·사용자 명시 요청·PB-0008 PASS).

## REV-20260624-0022 [SKIPPED: 알림 본문 발신자 대괄호 제거 — trivial cosmetic 문자열, 로직 무변경]
- Related Change: CHG-20260624-0020
- Risk Grade: **Minor (trivial)** — `_notifyMentions` body 템플릿에서 `[` `]` 2글자 제거(`[${who}]` → `${who}`). 신규 로직·분기·상태 변경 0. §18.8 단순 변경 → 적대 패널 SKIP(사유 기록).
- 자가 검증: `node --check` OK. 제목/다중표기/high-water/dedup/라우팅 무변경. XSS 무관(textContent/Notification body=plain text).
- **PB-0008 실측(실제 Windows Chrome, relay@9223)**: scenario `tests/win-browser-notify-nobracket.scenario.json` PASS. Notification stub body=`mckim2 : @bootstrap_admin 이거 확인 부탁드려요`(starts_with_sender=true, has_no_leading_bracket=true), title=`DQA : 운영 이슈 대응방` 유지.
- Human Approval Needed: 아니오 (trivial cosmetic·사용자 명시 요청·PB-0008 PASS).

## REV-20260624-0023 [SUBAGENT: 설정/알림 UI 정리(gc-settings-notif) — kebab 통합·프로필 계정 병합·알림 환경설정/음소거 §18.8 + PB-0008]
- Related Change: CHG-20260624-0021
- Risk Grade: **Minor** — 전부 프론트(app.js/index.html/styles.css + 테스트 시나리오), 백엔드·스키마·인가 무변경. 제목 변경은 동일 owner 게이트(canRenameConversation+서버 PATCH owner-gate)·공유 발급은 동일 _issueConversationShare 로직 유지. 알림 제어는 클라이언트 localStorage. §12.3 Minor. §7.1(다파일) → 적대 패널 수행.
- Reason: 사용자 요청 — 알림 동작 사용자 제어 + UI 정리(대화 ··· 메뉴 4건·프로필 탭 3건). 알림 제어 위치: 프로필>계정>알림(전역) + 대화 ···>설정(대화별 음소거).
- 사전 조사(4영역 병렬 recon): kebab 메뉴 구조(makeItem 명령형 5항목)·공유 모달 2종(promptShareExpiry/openShareManager 동일 share-mgr CSS 재사용)·프로필 탭(index.html DOM 순서가 곧 표시순서, switchProfileTab 키 매칭)·알림 저장(localStorage 환경설정 패턴=sendMode/productPref) 파악 → 클라이언트 localStorage + 공통 헬퍼 추출 설계 확정.
- 패널 결과(adversarial 3렌즈 subagent: regression-routing/profile-drawer/edge-consistency): **PASS, BLOCKING 없음**. regression 패널이 올린 blocking 1건(read-only 사용자 공유 view-only 진입 차단 회귀)은 **적대 검증에서 기각** — `can()`(app.js, TASK-0098)이 인자를 무시하고 로그인 사용자면 항상 true 반환하는 stub("표시 허용 + backend 403 fallback")이라 markAccessBlocked 가 메뉴를 막지 않고 openShareDialog 가 항상 열림(view-only !canCreate 분기는 기존 패턴대로 dead, 실제 인가는 backend). profile-drawer 패널 PASS(탭 재정렬·usage 병합 id 보존·알림 배선·id 무중복·dead usage 경로 부재). **반영 nit 3건**: ① `.share-mgr-body{flex:1;min-height:0}`(통합 팝업 4단 확장 후 스크롤 경계 확정) ② openShareDialog 의 shareJoinableChk→shareDialogJoinableChk(promptShareExpiry 와 id 격리) ③ saveTitle: PATCH 실패와 refreshWorkspace 실패 분리(성공 후 close + best-effort refresh — detached 버튼 재활성/중복 토스트 방지). + createConversationShare scopeMode:"full" 명시 + stale 주석 갱신.
- **PB-0008 실측(실제 Windows Chrome/149, relay@9223)**: scenario `tests/win-browser-settings-notif.scenario.json` 17/17 step PASS. ① 알림 게이팅 logic — {default_on:1, master_off:0, desktop_off:0, muted:0, unmuted:1, pass:true}(마스터/데스크톱/음소거 게이트 정확·기본 ON 보존). ② kebab items=["공유","설정","보관"](복사/공유 관리/제목 변경 제거). ③ 공유 팝업=생성영역(참여허용+만료+생성버튼)+소제목+목록 통합. ④ 대화 설정=제목 입력+음소거 토글, 섹션 ["제목","알림"]. ⑤ 프로필 탭=["릴리즈 노트","프롬프트","계정"]·release_first·알림/사용내역 계정 병합·usage 탭 제거. 증거: artifacts/pb0008-settings-notif/03_profile_account.png(계정 탭 활동→알림→사용 내역 육안 확인), 02_conv_settings.png(대화 설정 팝업), 01_share_dialog.png. TEST.md §3 Run 2026-06-24-settings-notif.
- Risks/Open: 없음. 알림 기본값 ON 으로 무회귀. 비-active 대화 음소거는 해당 대화 전환 시 적용(데이터는 per-cid 즉시 저장 — 의도된 동작).
- Human Approval Needed: 아니오 (Minor·프론트·사용자 명시 요청·PB-0008 PASS).

## REV-20260624T031337-gc-settings-archive-leave [SUBAGENT:cross-ref-feature-0003]
- Date: 2026-06-24
- Cycle: gc-settings-archive-leave (CHG-0022/REV-0024) — 보관 ··· 메뉴 → 설정 팝업 이동 + 보관 권한 없는 그룹 참여자 '나가기'. **Minor §12.3**, frontend only.
- 정본: 코드/리뷰 정본 = feature-0003 `docs/REVIEW.md` REV-20260624T031337(적대적 3-렌즈 서브에이전트 — security/authz·correctness·UX, **실질 결함 0건 SHIP**). 본 entry 는 cross-feature 추적.
- 핵심 판정: client gate cosmetic(backend `_delete_conversation_impl`·`remove_conversation_member` authoritative 재검증), IDOR 없음(self-leave `state.user.id` only), 버튼-권한 매핑 정합(owner→보관/admin→보관/비보유 그룹멤버→나가기/타인 1:1→미렌더). LOW 1건은 기존 `is_group` PG-only 환경의존(본 변경 비도입).
- Verification: `node --check` + `verify_settings_archive_leave.mjs` 22/22. PB-0008 미실측(worktree WSL — 배포 후 권장).
- Human Approval Needed: 아니오 (Minor·프론트·사용자 명시 요청·backend 무변경).

## REV-20260624T081516-gc-share-joinable-guard [SUBAGENT:security]
- Date: 2026-06-24
- Cycle: gc-share-joinable-guard (CHG-20260624T081516) — 공유 '참여 허용' 토글 owner-only 게이트. **Critical §12.3 (인가)**, 별도 worktree `ai/claude/feature-0009-share-joinable-guard`.
- Related Change: feature-0003 `src/app.py`(`create_conversation_share` owner 게이트 403) + `static/`(FE disabled + joinable 강제 false) + 신규 `tests/test_share_joinable_owner_guard.py` (6).
- Reason: Critical 인가 변경 — 비소유자의 joinable 링크 발급 차단이 실제 우회 불가능한지 적대적 검증 필요(§18.8 security dispatch).
- 결정(AskUserQuestion): D1=403 거부, D2=소유자만 엄격(admin/`conversation.read.any` 예외 없음).
- 적대적 검증(security 서브에이전트, 우회 2시도):
  - 게이트 우회 불가 — `joinable` truthiness 코어션 fail-secure(`{joinable:false}` 만 0, 그 외 8 페이로드 전부 1 수렴), 게이트가 INSERT·`_ensure_owner_membership`·`_mark_conversation_group` 보다 선행, `account["id"]` 는 세션 유도(body 위조 불가).
  - owner 판정 fail-closed — `owner_account_id` NULL/0 → `None` → 거부(비소유자 오판 없음).
  - 단일 mutation 경로 — `Joinable=1` 쓰기는 `create_conversation_share` 1곳(join/revoke/view/fork 미해당, grep 전수).
  - FE/BE 기준 동일(`isOwnConversation` ↔ `_conversation_owned_by_account`), 403 메시지 정보누설 없음, 회귀 없음.
- 핵심 판정: **SHIP**. 블로커 결함 0. P3 2건 = (a) 레거시 backfill 소급 미폐쇄(의도된 scope-out, D 결정과 정합) + (b) PG/MySQL owner 폴백 분기(기존 코드, 본 변경 무관) — 둘 다 비블로커, MODIFY.md 에 기록.
- Verification: pytest 신규 6/6 + 관련 share 20/20 + `node --check` + `py_compile`. PB-0008 미실측(worktree WSL — 배포 후 권장).
- Human Approval Needed: 아니오 (사용자 명시 요청 + AskUserQuestion D1/D2 반영, backend authz 강화·무회귀).

## REV-20260625T163424-gc-participant-product-select [SUBAGENT:cross-ref-feature-0003]
- Date: 2026-06-25 (중단 세션 resume).
- Cycle: gc-participant-product-select (CHG-20260625T163424) — 공유 대화 참가자(비-owner)의 per-message 제품 선택·발화. **Major §12.3** authz 경계, 코드 거주=feature-0003.
- 정본: 코드/리뷰 정본 = feature-0003 `docs/REVIEW.md` REV-20260625T163424-gc-participant-product-select(적대적 authz 서브에이전트 — 6개 공격가설[권한우회·바인딩오염·owner회귀·view-only과다·FE정합·auto] 전부 REFUTED, **VERDICT SHIP, BLOCKING 0**). 본 entry 는 cross-feature 추적.
- 핵심: ANCHOR §1 / REQ-GC-R7 보존 — 발화는 발신자 본인 RBAC 로만 게이트(권한 상속 없음), 대화 공통 바인딩 비파괴. authz 이중 게이트(parse + run-product 재확인).
## REV-20260625T163744-gc-run-status-stuck [SUBAGENT:concurrency-run-status]
- Date: 2026-06-25
- Cycle: gc-run-status-stuck (CHG-20260625T163744) — 그룹대화 동시 run 충돌로 인한 '처리 중' 고착/채팅 블로킹 fix. **Major §12.3 (동시성·run-status 핵심 경로, 인가/파괴적 변경 없음)**, worktree `ai/claude/gc-run-status-stuck`.
- Related Change: feature-0002 `modules/memory.py`(set_run_status per-run marker) + feature-0003 `app.py`(`_load_run_terminal_marker`+`/api/progress` 해소) + `static/app.js`(client_run_id 항상 전송+foreign-run hijack 가드).
- Reason: 동시성·핵심 send/run-status 경로 인접 → §18.8 적대적 패널 필수. 라이브 자동 배포(deploy_scope: included)라 회귀 차단 검증 필요.
- 적대적 검증(Explore 서브에이전트 3, lens 분리 — 동시성/FE회귀/BE데이터; "통과 아닌 결함 적발"):
  - **동시성/race**: per-run marker 가 *살아있는* run 을 오해소하나 → 반증(run_id=`timestamp+uuid8` 고유, 클라이언트는 자기 run_id 로만 marker 조회 → 타 run 못 읽음). supersede 가드 회귀 없음(취소된 superseded run 은 새 run 추적 클라이언트가 조회 안 함).
  - **FE 회귀**: early-return 이 자기 버블 step 갱신 누락 지적 → 동시 처리중 창에서 자기 *라이브 step* 미표시는 **의도된 동작**(이전엔 foreign step 오표시=버그; '처리중+elapsed' 표시 유지, 완료 즉시 해소). 1:1·관찰자·대화전환·취소-재요청 정상 흐름은 가드 미발동 확인.
  - **BE 데이터**: 신규 KV 키 누수 0(대화목록 dump·`list_processing_conversation_ids`·orphan recovery 전부 명시 `IN(...)` allowlist, LIKE/prefix 없음). 키폭 OK(`varchar(128)`, ~57자). `/api/progress` after_step 재설정 로직 marker 해소 후 정합. `_compute_display_status` 가 non-processing 조기 return → terminal marker 가 stale 오판 안 됨.
- 패널 반영(유효 NIT 2): ① 주석 "단일 run 키 누적 0" 부정확 + 1:1 취소-재요청 supersede 도 skip 분기 진입 → marker 를 **done/error 만** 기록하도록 tighten(canceled 미기록 → 1:1 누적 차단, 주석 정확화). ② marker TTL 정리 부재 → 충돌 시·tiny row 만 잔존, S6 per-thread 재키잉 이연 명시(MODIFY 기록).
- 핵심 판정: **SHIP**. 진짜 BLOCKING 0(패널 "BLOCKING" 라벨은 false-positive[run_id 고유]·intended-behavior[foreign step 미표시]·본질적[첫 폴 run_id 미정] 으로 트리아지). 잔여는 수용 NIT.
- Verification: `py_compile`(memory.py/app.py) + `node --check`(app.js) PASS. **PB-0008 미실측**(worktree=WSL; 다중 사용자 동시 race — 배포 후 라이브 그룹대화 검증 권장).
- Human Approval Needed: 아니오 (사용자 명시 버그 보고 재개, 동시성 fix·무회귀, deploy_scope: included standing 승인).

## REV-20260625T065840-gc-unread-badge [SUBAGENT:authz·correctness·perf 3렌즈 §18.8]
- Date: 2026-06-25 (패널 2026-06-25, resume 세션에서 완료)
- Cycle: gc-unread-badge (CHG-20260625T065840) — 사이드바 "안 읽은(새) 메세지 + 안 읽은 @멘션" 배지. **Major §12.3** (스키마 추가+백엔드 쿼리+프론트 다중 파일, deploy-backed). 사용자 `/_template:entry` 요청 + Major plan 사전 승인("바로 구현").
- Related Change: alembic 0019(PG 컬럼) + schema.sql/app.py parity + group_members read-state + mentions.sql_mention_regex + app.py 읽음 API/집계 + FE 배지/읽음처리/주기갱신 + test_mentions 파리티.
- 요구 해석: "진행된 메세지 개수" 1차 해석은 누적 총계였으나 사용자 명확화("실제 메신저처럼 새 메세지 기준")로 **unread(안 읽은) 집계**로 확정 → read cursor 인프라 신설(기존 미구현 REQ-GC-R8 완성).
- 설계 근거(대안 비교):
  - read cursor 저장: (택) `conversation_members.last_read_message_id` 컬럼 — 멤버별 1행, 자연스러운 위치(REQ-R8 설계와 정합). vs KV(`(conversation,key)` 단일키라 account 별 분리 불가) 기각.
  - cursor 단위: (택) message_id(단조 증가, 시계 skew 무관) vs last_read_at(timestamp, 동시각 경합) 기각.
  - unread 정의: 본인 미발신(`sender IS DISTINCT FROM me`) + last_read 이후 user/assistant + content 비어있지 않음. assistant 응답도 "새 메세지"로 포함(메신저 관례, 헤더 message_count 와 동일 role 집합).
  - 멘션 카운트: canonical `parse_mentions` 단어경계를 `sql_mention_regex` 로 미러(lookbehind 미지원 POSIX/ICU → `(^|[^A-Za-z0-9_@])`/`([^A-Za-z0-9._-]|$)` 변환). FE↔BE↔SQL 단일 문법 — test_mentions 파리티로 고정.
  - 커서 전진만(GREATEST): 폴링/재진입이 더 작은 id 로 되돌리지 않음(이미 읽은 메세지 부활 방지).
- 보안/인가: 읽음 API 는 기존 `_account_can_access_conversation`(read.own/.any) 멤버십 게이트 재사용 — IDOR 부재(AC-GC-A7 정합). 비멤버 admin(.any) 열람은 멤버 행 없어 set_last_read no-op(타인 커서 오염 불가). 멘션 regex 는 파라미터 바인딩 + username escape(SQL/regex 인젝션 차단). unread 집계는 `conversation_members(본인) JOIN` 이라 멤버인 대화만 노출(타 대화 카운트 누설 0).
- 수용/한계: ① 멘션 카운트는 username 기준(예약어 'assistant' 미해당 — 실사용자 대상). ② MySQL 경로는 레거시 parity(production=PG). ③ 배지 라이브 동작은 alembic 0019 적용 후에만 데이터 발생 → **PB-0008 실측은 배포 후**(worktree WSL 한계 + 데이터 의존, 본 feature 의 기존 PB-0008-after-deploy 패턴과 정합).
- 적대 패널(§18.8, SUBAGENT 3렌즈 병렬 — 통과가 아닌 결함 적발 목적): **종합 SHIP, BLOCKING 0**.
  - **보안/authz 렌즈 → SHIP**: 우회 4경로 전부 차단 — ① body-forged account_id IDOR(신원은 세션 `account["id"]` 유도, body 는 `last_read_message_id` 만) ② 비멤버 타인 커서 오염(게이트가 set 선행 + WHERE `account_id=세션` → rowcount 0 no-op) ③ admin(.any) 비멤버 열람 시 멤버 행 부재로 set_last_read no-op ④ regex/SQL 인젝션(username `USERNAME_RE` + `_sanitize_username` charset 제한 + `sql_mention_regex` 메타문자 escape + `%s` 파라미터 바인딩, ReDoS 200k~5ms). cross-conv 누설 0(이중 멤버십 JOIN). 0012 GRANT 가 0019 ADD COLUMN 에 자동 상속 — "추가 GRANT 불요" 주장 정확.
  - **정확성 렌즈 → SHIP**: 커서 경계 strict `>`(방금 읽은 메세지 재집계 없음, 읽음 후 0) · 멘션 파리티 `sql_mention_regex`↔`parse_mentions` 14 canonical + 20+ edge(이메일·연속 @@·코드블록·멀티라인·대소문자) 전부 P==SQL · 불변식 `unread_mention ≤ unread`(엄격 부분집합) · NULL last_read=전부 unread(COALESCE 0) · PG `IS DISTINCT FROM`↔MySQL `<=>` 동치 · FE 0-숨김(`if(_unread>0)`/멘션 0 시 ` / @0` 미부착) · 캐시버스터 app.js+styles.css 둘 다 bump 확인.
  - **성능/회귀 렌즈 → SHIP-WITH-NITS**: N+1 없음(단일 GROUP BY, limit 200, regex 는 CASE 3번째 AND 단축평가로 unread+미발신 행만) · 인덱스 정합(`ix_core_messages_conv_id(conversation_id,id)` + members PK 커버, 신규 컬럼 인덱스 불요) · 마이그레이션 멱등·체인 0018→0019 정합·nullable ADD COLUMN 락 짧음 · 커넥션 누수 없음(finally close) · payload 신규 키 2개 충돌 0, 1:1/비그룹 미영향.
- 수용된 NIT (가시 회귀 0 — 본 cycle 미적용, 후속 개선 후보):
  - **N1 (성능, 실질)**: `_maybeSyncConversationListUnread` 가 탭 가시 상태 7s(`SIDEBAR_UNREAD_SYNC_MS`)마다 `/api/conversations`(200건 unread 집계) 신규 상시 폴링 — 활성 1인당 ~8.6 req/min. throttle·`document.hidden` 가드는 있음. → **별도 최적화 cycle 권고**(그룹대화 0건 skip / 7s→15s 상향 / 경량 `/api/conversations/unread` 분리). 본 cycle(배지 표시) scope 외 — resume 의도 완결 우선.
  - **N2 (정확성, 회귀가드)**: off-by-one·NULL 초기동작·PG/MySQL 집계 동치·멀티라인 멘션 파리티의 in-container 단위 테스트 부재(DB 의존 → `make test`/PB-0008 배포 후 커버). 파리티 regression 케이스(멀티라인·trailing-newline) 명시 추가 권고. 패널이 수동 실측으로 통과 확인.
  - **N3 (보안, 무해)**: MySQL parity `_mention_re.lower()` 가 charset `[A-Za-z0-9_@]`→소문자 변형(범위 보존 + content `LOWER()` 로 경계 유지, prod=PG 영향 0).
- Verification: py_compile(app.py·group_members·mentions·alembic) + node --check(app.js·mentions.js) + CSS brace 1576=1576 + test_mentions 6/6 PASS. group_members/s2 DB 의존 테스트는 컨테이너 make test(배포 경로).
- Human Approval Needed: 아니오 (Major plan 사전 승인 "바로 구현" + additive·무회귀). **배포(alembic 0019 + web 재빌드)는 외부영향 — 별도 confirm**(§16.3 deploy-backed).

## REV-20260625T162000-gc-ask-sender-attrib [SUBAGENT:correctness+security]
- Date: 2026-06-25
- Cycle: gc-ask-sender-attrib (CHG-20260625T162000) — 그룹 대화 `@assistant` 호출 시 user 메시지가 표시 store 미러에서 대화 owner(생성자) 프로필로 오귀속되던 것을 실제 발신 멤버(actor)로 귀속. **Major §12.3** (ask dispatch 경로·2+ 파일, 신규 authz 미도입 — account_id 는 기존 actor).
- Related Change: feature-0002 `src/agent_core.py`(`run_agent`/`_run_agent_core` 에 `sender_username` + user 미러 meta) + `src/modules/ask.py`(`_payload_to_kwargs` worker 복원) + feature-0003 `src/app.py`(ask dispatch 그룹 한정 `sender_username` 계산 + inproc run_kwargs + worker enqueue payload) + `tests/test_ask_worker.py`(+3 보강/신규).
- Reason: 코어 user 메시지 저장/미러 경로 인접 + 발신자 귀속(spoofing 표면) → §18.8 적대적 검증 dispatch.
- 적대적 검증(general-purpose 서브에이전트, correctness+security 렌즈, 6항목 의심):
  - end-to-end 무결성 — inproc(app.py run_kwargs→_run_agent_core)·worker(payload→ask_jobs jsonb→_payload_to_kwargs→run_agent→_run_agent_core) **양 경로 모두 sender_username 끝까지 도달**, run_agent 래퍼 forward 확인. 두 모드 동작 일치.
  - spoofing 불가 — sender_username 출처가 클라 입력이 아닌 서버측 인증 actor `account.get("username")`, account_id/username 동일 row(WebAccounts) → 위장 경로 없음.
  - 1:1 회귀 0 — 비그룹/신규는 `_conversation_is_group("")`=False → sender_username=None → meta 미부착 → 기존 동작 100% 동일. `int(account_id)` 캐스팅은 `sender_username and account_id` 가드 내부에서만 평가 → None/0 안전.
  - jsonb 직렬화·이중미러 — None↔null round-trip 안전, ask 경로와 사람-채팅 경로(`_save_group_chat_message_pg`) 상호배타(그룹 비멘션 422) → 이중 미러 없음.
- 핵심 판정: **SHIP. BLOCKER 0 / MAJOR 0**.
  - MINOR(빈 username 비대칭, 패널 적발) **REJECTED-as-fix / ACCEPTED-as-is**: 패널 제안(`if account_id` 로 대칭화)은 역회귀 유발 — agent 경로는 1:1+그룹 양용이라 `sender_username` truthiness 가 그룹 게이트 proxy. `if account_id` 로 바꾸면 모든 1:1 에 `group_chat:True` meta 가 붙어 회귀. 비대칭은 의도적·필수. 추가로 `WebAccounts.Username` 은 `NOT NULL UNIQUE` 라 `""` actor 경로 자체가 비현실적. 현 `sender_username AND account_id` 가드가 정답.
  - NIT(주석 "동일 shape") **수정 반영**: agent_core 주석을 "동일 키 집합 + 1:1/그룹 양용이라 sender_username 으로 게이트, account_id-only 게이트는 회귀" 로 정확화.
- Verification: `test_ask_worker.py` 7/7 (보강 round_trip/defaults + 신규 sender_username 시그니처) + 인접 회귀 `test_ask_jobs`/`test_group_history_merge` 20/20 + 3파일 `py_compile`. PB-0008 미실측(백엔드 배선 — 표시 동작은 배포 후 라이브 그룹 대화에서 권장).
- Human Approval Needed: 아니오 (Major·backend 배선·신규 authz 미도입·무회귀, deploy_scope: included 사전승인).

## REV-20260625T165320-gc-unread-baseline [SUBAGENT:데이터정확성·보안/회귀 2렌즈 §18.8]
- Date: 2026-06-25
- Cycle: gc-unread-baseline (CHG-20260625T165320) — unread 배지 baseline 누락 버그(읽은 대화에 전체 개수 표시) 수정. **Major §12.3** (데이터 마이그레이션 + 멤버 INSERT, deploy-backed). 사용자 명시 버그 보고 → 즉시 수정.
- 원인/해결: 0019 가 baseline backfill 누락(137행 NULL→전체 unread). 0020 backfill(NULL→대화별 MAX id) + add_member INSERT baseline(가입 시점 MAX).
- 적대 패널(§18.8, SUBAGENT 2렌즈 병렬 — 결함 적발 목적): **종합 SHIP, BLOCKING 0**.
  - 데이터 정확성/안전 → SHIP-WITH-NITS: per-conversation MAX 스코핑(core_messages.id 전역 단조·유일) · `IS NULL` 멱등 가드(전진 커서 미복귀) · strict `>` 경계(off-by-one 0) · 메세지 0건=NULL 유지 · `ON CONFLICT` role-only(재참여 커서 보존) · 단일 add_member funnel.
  - 보안/회귀 → SHIP: 파라미터 바인딩(서브쿼리 `%(conversation_id)s`) · cross-conv 누설 0 · add_member 호출처(`_ensure_owner_membership`·share join) 시그니처 무변경(서브쿼리가 기존 param 재사용) · 권한(agent_kb_rw SELECT/UPDATE 커버) · owner 자기발신 `sender IS DISTINCT FROM self` 제외 · MySQL read-only 무영향 · 체인 0018→0019→0020 선형.
- 수용 NIT (가시 회귀 0 — 미적용):
  - backfill `MAX(id)` 가 role 필터 없이 전체 max(집계는 user/assistant+content 필터) — id 단조라 **결과 동치**(baseline 이하 전부 읽음, 이후 신규 정상) — 무해.
  - MySQL backfill parity 부재 — production=PG 정본, MySQL 폴백 미운용. 운용 시 동일 UPDATE 필요(기록).
  - add_member `MAX`↔`ON CONFLICT` TOCTOU 좁은 창 — 단일 statement, 자기 가입 기준이라 무시 가능.
- Verification: py_compile(group_members·0020) + §18.8 패널 2렌즈 SHIP. backfill 라이브 적용 + unread smoke + PB-0008 배포 후.
- Human Approval Needed: 아니오 (Major·사용자 명시 버그 보고·데이터 보정 멱등·무회귀, deploy_scope: included 사전승인).

## REV-20260625T191040-composer-nonblock-interrupt [SUBAGENT:R1R2회귀·R3race·BE / 교차회귀 3렌즈 §18.8]
- Date: 2026-06-25
- Cycle: composer-nonblock-interrupt (CHG-20260625T191040) — 입력창 비잠금(R1) + 그룹 @assistant 중복 차단(R2) + 1:1 인터럽트 재요청·추론 보존(R3). **Major §12.3** (composer/send 핵심 경로 동작 변경, 인가/스키마 변경 없음). 사용자 지시 + AskUserQuestion(R2=중복차단+안내 / R3=가시+다음 run 맥락).
- Related Change: feature-0003 `static/app.js`(myAskInFlight·renderComposer·sendPrompt R2/R3·_interruptCurrentRunForResend·resume/loadHistory 복원) + `app.py`(/api/cancel preserve_reasoning) + `static/index.html`(캐시버스터) + feature-0002 `modules/memory.py`(mark_cancel_requested+_clear_cancel_request) + `agent_core.py`(canceled 분기 부분추론 보존).
- Reason: 핵심 send/cancel 경로 + 동시성(같은-계정 slot=6 동시 run) + 라이브 자동 배포(deploy_scope: included) → §18.8 적대 패널 필수.
- 적대적 검증(Explore 서브에이전트 3, lens 분리 — R1/R2 회귀·R3/race/BE·교차회귀; "결함 적발"):
  - **R1/R2 회귀**: myAskInFlight 생애주기·R2 오차단·버튼 thrash·dead code 점검. 버튼 thrash 반증(dataset.mode 가드로 모드 변동 시에만 innerHTML 교체). `busy` 변수는 dead 아님(composer 타이틀 'else if(busy)' 사용 — 유지).
  - **R3/race/BE**: same-key 정리 race 반증(await /api/cancel macrotask 가 aborted send finally microtask 를 먼저 드레인 → 새 add 가 나중; 권한 게이트로 await-skip 차단). preserve 콘텐츠 주입 안전(서버측 rationale/answer 만). mark_cancel_requested 회귀 0(기본 False). supersede 가드로 canceled→new processing 클로버 없음.
  - **교차회귀**: 1:1 정상·그룹 비멘션 채팅 자유·명시 중단·취소-재요청·전송후 입력clear 점검.
- 패널 반영(유효 4 — 모두 적용): ① **새로고침/resume 후 myAskInFlight 미복원** → 1:1 processing 복원 시 myAskInFlight 복원(그룹은 오귀속 방지 제외) — 새로고침 후 중단 버튼·R3 동작 회복. ② mouseenter 툴팁이 isCurrentConvBusy(타 멤버 run 시 숨김) → `_myAskInFlightHere()&&빈입력` 으로 일관화. ③ `_interruptCurrentRunForResend` 후 renderComposer 추가(버튼 즉시 갱신). ④ `_clear_cancel_request` 가 cancel_preserve 도 정리(위생; stale read 는 mark_cancel_requested 원자적 재세팅으로 원래 없음).
- 핵심 판정: **SHIP**. 진짜 BLOCKING 0(패널 "BLOCKING" 라벨 3건은 ①refresh 복원[수정]·②툴팁[NIT 수정]·③interrupt 렌더[NIT 수정] 로 트리아지·해소). 잔여 수용: 그룹 새로고침 직후 1회 한해 내 중복차단 완화(허용, slot=6 + gc-run-status 가 상태 정합).
- Verification: `node --check`(app.js) + `py_compile`(app.py·agent_core·memory) PASS. **PB-0008 미실측**(worktree=WSL; 입력창 비잠금·인터럽트·중복차단은 배포 후 라이브 다중 사용자 검증 권장).
- Human Approval Needed: 아니오 (사용자 명시 지시 + AskUserQuestion 반영, composer 동작 개선·1:1 무회귀, deploy_scope: included 사전승인).

## REV-20260625T195400-composer-clear-input-on-send [SUBAGENT:입력창 클리어 회귀 1렌즈 §18.8]
- Date: 2026-06-25
- Cycle: composer-clear-input-on-send (CHG-20260625T195400) — @assistant 전송 시 입력창 미클리어 회귀(R1 누락분) 수정 — 낙관적 클리어 일원화 + 응답-시점 클리어 제거 + 실패 복원. **Minor §12.3** (composer 전송 표현계층, 로직/스키마/authz 무변경). 사용자 보고.
- Related Change: feature-0003 `static/app.js`(sendPrompt 낙관 클리어/응답 클리어 3 제거/실패 복원) + `static/index.html`(캐시버스터).
- Reason: 핵심 send 경로(sendPrompt) 인접 → §18.8 적대 검증(scoped 1렌즈 — 입력창 클리어 회귀).
- 적대적 검증(Explore 서브에이전트, 라인별 추적 9항목): **회귀 0**.
  - message 캡처 안전(const, 클리어 이후 askBody/optimistic 가 사용) · 버튼 모드 순서 정확(myAskInFlight.add → 클리어 → renderComposer 빈입력+myRun=중단) · 실패 복원 분기 분리(user-cancel[userCanceledKeys]·422 reroute 는 조기 분기로 미도달 → 의도적 비복원) · 새 입력 보호(`if(!입력.trim())` 빈 경우만 복원) · 제거 3곳 안전(전부 낙관 클리어 선행 → 재클리어 불필요) · 그룹채팅 독립(별도 함수, 무영향) · 첨부/lazy-create/height-autogrow 무충돌.
  - lazy-create 초기 실패 미복원 = 의도된 설계(실패 pending 버블에 메시지 표시) — 수용.
- 핵심 판정: **SHIP**. BLOCKING 0.
- Verification: `node --check`(app.js) PASS. **PB-0008 미실측**(배포 후 라이브 실측 권장 — 전송 즉시 비움·실패 복원).
- Human Approval Needed: 아니오 (사용자 명시 버그 보고·표현계층·무회귀, deploy_scope: included 사전승인).

## REV-20260625T194159-gc-unread-read-fix [SKIPPED:frontend 읽음처리 누락 보정·비핵심경로·신규표면 0]
- Date: 2026-06-25
- Cycle: gc-unread-read-fix (CHG-20260625T194159) — 읽은 대화의 unread 배지가 안 줄던 버그. **Minor §12.3** frontend-only.
- 원인/해결: 읽음 커서 전진이 `selectConversation`(첫 전환)·`_liveSyncTick`(새 메세지)에서만 호출 → `refreshWorkspace`(복원/갱신) 진입 + 이미-active 재클릭 경로 누락. → refreshWorkspace `loadHistory` 후 + selectConversation 가드 시 `_markActiveConversationRead` 보강.
- 패널 SKIP 근거: 순수 frontend 읽음 처리 호출 위치 보강(로직 신설 0, 기존 `_markActiveConversationRead`/`POST /read` 재사용), 신규 인가/스키마/엔드포인트 표면 0, 핵심 send/render 경로 무변경.
- 자체 검토: ① 커서 GREATEST 전진만(되돌림 0, 이미 읽은 메세지 부활 없음) ② `isGroupConversation` 게이트로 1:1 무영향 ③ refreshWorkspace 호출 빈도 낮음 + 커서 max 면 no-op(부하 무시) ④ best-effort try/catch(UI 흐름 비차단).
- Verification: `node --check`(app.js) PASS. PB-0008 배포 후(새로고침→복원 대화→배지 0).
- Human Approval Needed: 아니오 (Minor·frontend·사용자 명시 버그·무회귀).

## REV-20260625T104906-gc-optimistic-sender-attrib [SUBAGENT:spoofing·hydrate·회귀·422 1렌즈 §18.8]
- Date: 2026-06-25
- Cycle: gc-optimistic-sender-attrib (CHG-20260625T104906) — optimistic user 메시지 발신자 귀속 정정(비-owner 참가자 메시지가 처리 중 owner 로 잘못 표시되던 깜빡임 제거). **Minor §12.3** (frontend display-only, 인가/스키마/신규권한 0, 서버 권위 발신자 무변경).
- Related Change: feature-0003 `static/app.js`(`_selfSenderMeta()` 헬퍼 + optimistic 2지점 meta 부여) + `static/index.html`(캐시버스터).
- Reason: 발신자 귀속 영역(ANCHOR §1 의 actor RBAC 와 표면 인접) → §18.8 적대 패널 1렌즈로 spoofing·정합·회귀 적발 시도.
- 적대적 검증(general-purpose 서브에이전트 1, "결함 적발" 목적, 코드 직접 read):
  - **Spoofing**: optimistic `meta` 는 client 메모리(`state.messages`)에만 존재. 실제 전송 본문(`_sendGroupChatMessage` body=`{content}`, `sendPrompt` askBody)에 `sender_*`/`meta` 키 없음. 서버는 `account["id"]`/`username`(인증 세션)에서만 발신자 결정 — app.py 에 `data.get("sender_account_id")`/`data.get("sender_username")`/`data.get("meta")` **0건**. 타인 위장 불가. **OK**.
  - **Hydrate 정합**: `loadHistory(append=false)` 가 `state.messages` 전량 교체(id-merge 아님) → optimistic(`id:null`)·서버행 충돌/중복 없음. `_liveSyncTick` 에코 dedup 은 role+content 키(meta 무관)라 독립. 재-깜빡임 없음. **OK**.
  - **회귀**: 1:1/owner 본인 = senderId=own id → `msgIsOwn=true`(기존 isOwn 폴백과 동일 결과). `state.user` 결측/id=0 → `_selfSenderMeta()={}` → 정확히 수정 전 `isOwn` 폴백(안전 degrade). 멘션 하이라이트(`!msgIsOwn`)·아바타 무회귀. **OK**.
  - **422 재라우팅**: sendPrompt optimistic → 422 시 참조 동등성으로 제거 후 `_sendGroupChatMessage` 가 동일 `_selfSenderMeta()` 재생성 — 발신자 meta 일관. **OK**.
- 핵심 판정: **SHIP**. BLOCKING 0. 순수 client-render-only, 새 신뢰경계 미도입.
- Verification: `node --check`(app.js) PASS + 발신자 귀속 결정부 4케이스 node 하니스(BEFORE 버그재현 / AFTER·hydrate 동일 / owner·1:1 무회귀). **PB-0008 미실측**(배포 후 라이브 그룹 대화 권장 — 비-owner 참가자 계정으로 @assistant 전송 직후 우측·본인 이름 확인).
- Human Approval Needed: 아니오 (사용자 보고 직접 수정, Minor display-only, 무회귀, deploy_scope 판정은 commit 후 안내).

## REV-20260625T202817-gc-unread-read-500-fix [SUBAGENT:근본원인·트랜잭션·leak·잔존근본원인 1렌즈 §18.8]
- Date: 2026-06-25
- Cycle: gc-unread-read-500-fix (CHG-20260625T202817) — 읽음 API `POST /api/conversations/{cid}/read` 가 web 컨테이너에 없는 `modules.db` 를 import → 매 호출 silent 500 → 읽음 커서 미전진 → 새로고침 시 unread 배지 복원. **Minor §12.3** (서버 import 경로 1줄 정정, 인가/스키마/계약/frontend 무변경).
- Related Change: feature-0003 `src/app.py`(`modules.db`→`shared.db`) + 신규 회귀 테스트 `tests/test_read_endpoint_pg_import.py`.
- Reason: 핵심 경로(읽음 처리 read endpoint) 인접 + 사용자 2회 재보고(앞선 frontend/DB 수정 3건이 실패) → §18.8 적대 패널 1렌즈로 "근본원인 정타 여부 + 잔존 근본원인" 적발 시도.
- 적대적 검증(general-purpose 서브에이전트 1, "결함 적발" 목적, 컨테이너 Dockerfile 레이아웃·코드 직접 read):
  - **Q1 근본원인 제거**: web 이미지(feature-0002 Dockerfile)가 `modules/`(feature-0002, `db.py` 부재)·`shared/` baked. app.py 가 import 하는 `modules.*` 13개 중 `db` 만 부재 → 깨진 게 정확히 그것. `shared/db.py:831 _pg_connect` 실재·resolvable. **정타**.
  - **Q2 트랜잭션 정합**: `_pg_connect` default autocommit=True + `set_last_read` 명시 commit = psycopg3 무해(no-op). 누수/중복/누락 0. **OK**.
  - **Q3 connection close**: `_connect_memory()`=외곽 finally, `_pg_connect()`=내부 finally. 1줄 수정이 close 경로 무변경 → 신규 leak 0. **OK**.
  - **Q4 다른 숨은 modules.db**: web app.py 내 `modules.db` import 0(수정 후). 나머지 `modules.*` 전부 feature-0002 실재. **0건**.
  - **Q5 잔존 근본원인(3차 재보고 방지 핵심)**: 커서는 **읽는 시점**(selectConversation `loadHistory` 후 5650 / refreshWorkspace 5543 / liveSyncTick 9647)에 전진·영속. import 복구로 이 경로 전부 작동 → 사용자가 실제로 읽은 모든 대화 커서 전진, 새로고침 후 unread 재계산(`m.id>COALESCE(last_read,0)`)이 영속 커서 기준이라 복원 안 됨. 새로고침 후 active 없음 경로는 mark 안 하지만 **그게 정상**(읽을 때 이미 전진). **추가 서버측 근본원인 없음**.
- 핵심 판정: **SHIP**. BLOCKING 0. 1줄 import 정정이 진짜 근본 원인 정타, 부작용 0.
- NIT(수용/처리): ① 핸들러 테스트 공백(2회 재보고 산 원인) → **회귀 테스트 신규 추가로 해소**. ② 읽음 호출 fire-and-forget(await 안 함) — 대화 열자마자 RTT 내 새로고침 시 드문 미전진 엣지(회귀 아님, refresh-restore 재마킹으로 대부분 완화) → REVIEW 수용 기록(현 수정 범위 외). ③ 이미지 baked → web **재빌드+재배포** 후에야 적용 → 배포 게이트에서 강제.
- Verification: `python -m py_compile`(app.py·test) PASS + 컨테이너 재현 `set_last_read` rowcount=1. **배포 후 web 로그 read 500→200 + 고착 커서(3466→conv_max) 전진 실증 필수**(deploy-backed 완료 기준).
- Human Approval Needed: 아니오 (사용자 보고 직접 수정, Minor 서버 버그 정정, 무회귀). deploy_scope: included(FIRST_REQUEST.md 전역) → 배포 자동.

## REV-20260625T202843-gc-assistant-dialect-context [AGENT-TEAM:회귀·정확성 / 보안·prompt-injection 2렌즈 §18.8]
- Date: 2026-06-25
- Cycle: gc-assistant-dialect-context (CHG-20260625T202843) — 라이브 그룹대화 `20260625063340-4220125d` 마찰 근본원인 2건 수정. **Major §12.3**(코어 LLM 컨텍스트 조립 경로 + backend SELECT 변경).
- Related Change: feature-0002 `src/agent_core.py`·`src/modules/tools.py`·`src/modules/runtime_backend.py` (cross-feature, FUNCTION.md §13 사전 승인).
- Reason: 코어 ask 경로(히스토리 조립·system prompt·sql_guard 피드백) 변경 + 사용자 입력(Username)을 LLM 컨텍스트에 prepend → 회귀·정합·prompt-injection 표면. §18.8 적대 패널 2렌즈로 결함 적발 시도.
- 진단 근거(라이브 PG `agent_runtime` read-only 조사): product 110=`mysql-mv-dev`(MySQL 단일 DS)인데 assistant 가 T-SQL 반복 생성→거부(msg 3440·3505·3571·3602·3625·3641·3643·3585); 히스토리 로드 SELECT 가 sender_account_id 누락(REQ-GC-R5 위반) 확인. product 전용 prompt(websystemprompts Id 32)가 "TOP N/UNION ALL/DESCRIBE [..]" 로 T-SQL 유도.
- 적대적 검증(general-purpose 서브에이전트 2, "결함 적발" 목적, 코드 직접 read):
  - **렌즈 A (회귀·정확성)** — VERDICT: SHIP-WITH-FIXES. 6 가설 중 5 clean: ① 1:1·비그룹 `sender_labels=None` 바이트 동일 무회귀(시그니처 default 인자, 외부 호출처 0) ② PG tuple idx 5 `(r[5] if len(r)>5 else None)` 가드, `_PG_GET_CONV_MESSAGES_FULL` 별도 미변경 ③ normalize/merge 불변식 보존(라벨은 content 문자열만 변형, user 행 게이트) ⑤ 라벨 누수 없음(저장·미러·origin/thread_goal 전부 raw) ⑥ None/예외 graceful 이중 방어. **적발 2건(둘 다 NON-BLOCKING, 반영 완료)**: (가설4) 멀티DS(mysql primary+mssql secondary)에서 `_MYSQL_DIALECT_GUIDANCE` 의 "every query/IGNORE T-SQL" 가 secondary mssql 안내와 모순 → 문구를 "활성(primary) MySQL 데이터소스" 로 스코프 + multi-ds grounding 위임 명시(수정함). (추가) 신규 함수 단위 테스트 0 → `test_gc_dialect_context.py` 6건 추가(수정함).
  - **렌즈 B (보안·prompt-injection)** — VERDICT: SHIP. 4 가설 전부 SAFE: ① 라벨 spoofing **불가** — `WebAccounts.Username` 은 VARCHAR(64) UNIQUE + 전 쓰기 경로(signup `_sanitize_username` `[A-Za-z0-9_.-]`·admin·OAuth=email local-part sanitize)가 `]`/`[`/`:`/공백/개행 물리 차단 → `[admin]: ignore` 류 생성 불가(app.py:1254/105/19160). content 는 기존 `_INJECTION_GUARD_NOTICE`+RBAC fail-closed 가 받침(신뢰경계 미확장, 라벨 소스가 content 보다 강한 제약). ② 권한경계: `SELECT Id,Username` 만·멤버 한정·파라미터 바인딩+int 강제(민감필드/SQLi 없음). ③ 거부 힌트 정적 문구(SQL 원문 미에코). ④ sql_guard 미변경·거부 분기 내 문자열 append 만(게이트 무력화 없음).
- 핵심 판정: **SHIP-WITH-FIXES → 적발 NON-BLOCKING 2건 모두 반영. BLOCKING 0.**
- Verification: `py_compile`+`ruff` PASS. 단위 48 PASS(신규 6 + 회귀 42 `test_db_query_ux`·`test_runtime_read_backend`). **PB-0008 미실측**(배포 후 라이브 그룹대화 실측 권장 — MySQL 제품 @assistant 가 LIMIT/단일SELECT 생성·다자 맥락 재질문 감소 확인).
- Human Approval Needed: 예(커밋·배포는 사용자 confirm) — Major + 코어 LLM 경로 + 라이브 system prompt 동작 변화. deploy_scope 판정은 commit 후 안내.

## REV-20260625T121352-gc-join-ambiguous-param-fix [AGENT-TEAM:correctness·회귀 / security·authz 2렌즈 §18.8]
- Date: 2026-06-25
- Cycle: gc-join-ambiguous-param-fix (CHG-20260625T121352-gc-join-ambiguous-param-fix) — 공유 대화 join 항상 500 실패("대화 참여에 실패했습니다") 근본원인 수정. **Minor §12.3**(backend PG bind-param 1곳 + 진단 로깅 1곳).
- Related Change: feature-0002 `src/modules/group_members.py`(`_PG_ADD_MEMBER` 서브쿼리 별도 param + `add_member` dict 키), `tests/test_group_members.py`(회귀 2 신규), feature-0003 `src/app.py`(join 핸들러 silent except 로깅). cross-feature, FUNCTION.md §13 사전 승인.
- Reason: 멤버십(authz-adjacent) + PG 쿼리 수정 → §18.8 dispatch(backend·qa·security). 적대 패널 2렌즈로 결함 적발.
- 진단 근거(라이브 컨테이너 `repo-web-1` 재현, 데이터 무오염): 수정 전 `add_member` → `AmbiguousParameter: inconsistent types deduced for parameter $1 — text versus character varying`. web 로그에 `_ensure_owner_membership failed` + 동일 AmbiguousParameter 6건. 수정 SQL → INSERT 성공(last_read baseline 정상 set) + cleanup.
- 적대적 검증(general-purpose 서브에이전트 2, "결함 적발" 목적, 컨테이너 직접 재현):
  - **렌즈 A (correctness·회귀)** — VERDICT: **SHIP**, BLOCKING 0. Q1 별도 param 으로 두 placeholder 독립 타입추론 → AmbiguousParameter 제거 충분(명시 캐스트 불요, 컨테이너 OLD=오류/NEW=통과 실증). Q2 baseline=`MAX(core_messages.id)` 정확(RETURNING 확인), `conversation_id_lookup==conversation_id` 코드상 보장(동일 변수). Q3 ON CONFLICT DO UPDATE role 갱신·last_read 보존 무회귀(재참여 시뮬). Q4 호출처(_ensure_owner_membership·join) 영향 0(키는 add_member 내부 항상 주입 → KeyError 불가). Q5 회귀 테스트 실효(OLD SQL/dict 에 실제 FAIL 확인, 허울 아님). Q6 동일 named-param 재사용 패턴 worktree 전체 1곳뿐(이제 수정) — backfill·ban·set_last_read·alembic 0020 모두 무관. MINOR M1(테스트가 SQL 문자열 형태만 검사 — `--no-deps` 제약상 합리적, 컨테이너 재현이 런타임 커버). NIT(코멘트 메커니즘 설명 미세 — 결론·수정 정확).
  - **렌즈 B (security·authz·injection)** — VERDICT: **SHIP**, BLOCKING 0. S1 join 게이트 체인(login→링크활성→미취소→미만료→Joinable→대화존재→비차단→ban fail-closed→멱등 short-circuit→`add_member(role="member")`) 전부 무변경(diff 가 게이트 로직 미수정). S2 SQL injection 표면 0(`conversation_id_lookup` 도 parameterized binding, f-string/format/concat 0). S3 로깅이 토큰·자격증명 미노출(conversation_id·actor_id 만, 인접 ban 체크 로그와 동일 정책). S4 신규 권한상승 0(role='member' 하드코딩, actor 영향 불가; `_ensure_owner_membership` 는 core_conversations 의 실제 owner 만 해석 → 가입자에 무권한 부여 0; AR-1 수용위험 무변경). S5 owner self-heal/member join 이 동일 SQL 공유라 대칭 복구(비대칭 우회 상태 없음), role 화이트리스트 검증 유지.
- 핵심 판정: **SHIP. BLOCKING 0.** MINOR 1(M1, 수용)·NIT 2(수용). 비파괴 bind-param 수정, 재현·수정 모두 라이브 오염 없이 실증.
- Verification: `python -m py_compile`(group_members·app) PASS + `test_group_members` 12/12(회귀 2 신규: distinct-param·lookup-equals-cid) + 컨테이너 재현 OLD/NEW 대조. **배포(web+ask-worker 이미지 재빌드) 후 라이브 공유 링크 join 200 + web 로그 `_ensure_owner_membership failed`/AmbiguousParameter 소거 실증 필수**(deploy-backed 완료 기준).
- Human Approval Needed: 아니오 (사용자 보고 직접 수정, Minor 서버 버그 정정, 무회귀, 게이트 무변경). deploy_scope: included(FIRST_REQUEST.md 전역) → 배포 자동.

## REV-20260625T225851-gc-unread-read-idspace-fix [SUBAGENT:증상제거·1:1회귀·시맨틱·경합·MySQL·backfill·MAX필터비대칭 1렌즈 §18.8 + 4-dim 조사 워크플로]
- Date: 2026-06-25
- Cycle: gc-unread-read-idspace-fix (CHG-20260625T225851) — 읽음 커서와 unread 집계(core_messages.id 공간)와 FE 가 보내는 last_read_message_id(표시 store messages.id 공간)의 **id-space 분리(disjoint)** 로 GREATEST 가 전진을 영구 거부 → 읽어도 배지 미감소·전환 시 회귀. **Major §12.3**(서버 read 핸들러 커서 산출 로직 변경).
- Related Change: feature-0003 `src/app.py`(mark_conversation_read: requested 신뢰 분기 제거, 항상 MAX(core_messages.id) 전진 + docstring), `tests/test_read_endpoint_pg_import.py`(id-space 계약 회귀 테스트 신규).
- Reason: 핵심 경로(읽음 처리) + 사용자 4차 재보고(앞선 5건 수정 실패) → 근본원인 다각 조사(4-dim 병렬 워크플로: frontend 전송값/handler updated/unread SQL/전환·폴링) 후 §18.8 적대 패널.
- 근본원인 확정(다각 조사 워크플로 + 라이브 DB, 2개 독립 차원이 동일 결론): messages 750~845 vs core_messages 3369~3655 **비겹침** 라이브 SELECT 확인. `_get_history`(AGENT_RUNTIME_READ_BACKEND=postgres)가 messages 테이블에서 읽어 FE state.messages 천장=845. set_last_read GREATEST(3466,845)=3466 영구 no-op, 멤버 행 존재로 updated=1·200 OK 이나 값 불변. 폴백(MAX core_messages)은 requested<=0 에서만 발동 → FE 양수라 미발동.
- 적대적 검증(general-purpose 서브에이전트 1, "결함 적발" 목적, worktree diff·코드·라이브 DB 직접):
  - **Q1 증상제거**: 진입 → 핸들러 MAX=3655 전진 → 라이브 cursor=3655 시 unread **0** 확인. 7s 폴링 재조회해도 서버 0 → 회귀 없음(+ active 클램프 이중안전). **PASS**.
  - **Q2 1:1/비그룹 회귀**: FE 전 호출처가 `isGroupConversation` 게이트 통과해야 endpoint 도달 → 1:1 호출 안 됨. 직접 호출돼도 set_last_read UPDATE 가 멤버 행 있을 때만 매치 → 1:1 updated=0 no-op. **안전**.
  - **Q3 "열면 전부 읽음" 시맨틱**: 표시/카운트 store 분리로 FE 가 정확한 core id 를 알 방법이 없어 **부분읽음은 원래 구현 불가** → 새 데이터손실 아닌 구조적 제약의 정직한 반영(카카오/슬랙도 진입=전체읽음). 멘션 카운트 동일 커서라 영구소실 아님. **수용**.
  - **Q4 새 메시지 경합**: 진입 후 도착분은 `_liveSyncTick` 이 append 직후 `_markActiveConversationRead` 재호출로 재전진. 비활성 전환 후 도착분은 마땅히 unread(정상). **PASS**.
  - **Q5 MySQL 경로**: 현 배포 postgres 확인. MySQL `AgentCoreConversationMembers.last_read_message_id` 는 **DDL 만 있고 write 경로 0건**(이 수정 이전부터 미배선 — 선행 결함, 회귀 아님). **무영향(NIT)**.
  - **Q6 backfill 미실행**: 일괄 MAX backfill 은 안 읽은 대화까지 0 처리(데이터손실) → 핸들러 수정만으로 각 대화 lazy 전진이 옳음. **타당**.
  - **Q7 커서 MAX(id) vs unread 필터 비대칭(핵심)**: MAX 보다 큰 counted 메시지는 정의상 불가 → 커서가 tool id 에 앉아도 unread `m.id>cursor` 가 항상 0 이하, **over-count 불가**. 라이브 전수: max_all>max_counted 인 대화 1건도 둘 다 counted 전부 덮어 unread=0 동일(커서가 약간 앞설 뿐 절대 뒤처지지 않음). **안전**.
- 핵심 판정: **SHIP. BLOCKING 0.** NIT 3(MySQL write 경로 선행부재 / 고착대화 lazy-correction 의도 / 테스트 import-path는 baked 이미지 harness 전제·정적 assertion diff 확인). 전부 수용/추적.
- Verification: `py_compile`(app.py·test) PASS + 핸들러 소스 계약 4/4(target_id=requested 부재·body 파싱 부재·MAX core_messages·set_last_read) + 라이브 재현(cursor 3655 → unread 0). **배포 후 web 로그 read 200 + 멤버 커서 conv_max 전진 + 전환·폴링 후 미회귀 실증 필수**(deploy-backed 완료 기준).
- Human Approval Needed: 아니오 (사용자 보고 직접 수정, 서버 버그 정정, 게이트·스키마·인가 무변경). deploy_scope: included(FIRST_REQUEST.md 전역) → 배포 자동.

## REV-20260703T182740-gc-join-notice [SUBAGENT:LLM히스토리·unread·anon-leak·meta정합·best-effort·XSS·멱등 1렌즈 §18.8]
- Date: 2026-07-03
- Cycle: gc-join-notice (CHG-20260703T182740-gc-join-notice) — 공유 링크 참여 시 대화 내 '참여 알림' 이벤트(pill + 기존 멤버 unread). **Major §12.3**(share/join 멤버십 경로 + 메시지 렌더 + LLM 히스토리 인접, cross-feature 0003+0002). 중단 세션 7d92a878 resume(session limit).
- Related Change: feature-0003 `src/app.py`(`_save_group_join_event_pg` + `_share_load_messages` guard)·`src/routers/share.py`(join 핸들러 호출)·`src/static/{app.js,index.html,styles.css}`, feature-0002 `src/modules/runtime_backend.py`(`EVENT_MESSAGE_NAME`)·`src/agent_core.py`(`_normalize_history_rows` 배제), `tests/test_gc_join_event_history.py`(신규 5). cross-feature, FUNCTION.md §13 사전 승인.
- Reason: 핵심 경로(공유 join 멤버십 + 메시지 렌더 + LLM 히스토리 소스인 core_messages 기록) → §18.8 dispatch. 적대 패널 1렌즈(general-purpose, 코드 직접 read + 주변 함수 추적)로 7개 실패 모드 결함 적발 시도.
- 적대적 검증(general-purpose 서브에이전트 1, "결함 적발" 목적):
  - **#1 LLM 히스토리 오염 — CONFIRMED-DEFECT (BLOCKING)**: join 이벤트가 core_messages(role=user)로 기록되고 그 store 가 `_PG_LOAD_CORE_MESSAGES`(role/event 필터 없음)→`_normalize_history_rows`(user 행 유지)→`_format_core_messages`(발신자 라벨 부착)로 LLM 히스토리에 그대로 흘러 `[Alice]: Alice님이 대화에 참여했습니다.` user 턴 주입 + `_merge_consecutive_user_messages` 로 실제 질문에 융합 → assistant 오응답/컨텍스트 낭비. 저자 docstring 이 "LLM 히스토리 포함"을 의도로 기술했으나 완화책 부재. **→ 수정: `EVENT_MESSAGE_NAME='__event__'` sentinel(name 컬럼)로 표식하고 `_normalize_history_rows` 최상단에서 배제. unread SQL 은 name 미참조라 role='user' 집계 유지. 재검증: 컨테이너 pytest 36 PASS(신규 5 — 배제·미주입·name매칭·슬롯 미잠식).**
  - **#2 unread 집계 정확 — NO-DEFECT**: PG 쿼리 `role IN ('user','assistant')`+`tool_calls NULL`+`content<>''` 통과, `sender IS DISTINCT FROM self` 로 가입자 제외·기존 멤버 +1. add_member 가 이벤트 INSERT **전** last_read=MAX 설정 → off-by-one 없음.
  - **#3 anonymous 공유 leak — NO-DEFECT(이벤트 한정)**: 공유뷰 `_share_load_messages` 가 event_type 파싱 가드로 join 이벤트(및 username) 억제(PG dict·MySQL str 양형 robust). ADJACENT NIT(이번 diff 무관, 선행): 일반 그룹채팅 메시지의 `meta.sender_username` 은 여전히 anonymous 공유에 노출 — 후속 티켓 권고.
  - **#4 meta 읽기/쓰기 정합 — NO-DEFECT**: 표시 store 기록→`/api/history`(system 행이 `_is_internal_message` 통과)→`message.meta.event_type` 프론트 노출→pill 발화 end-to-end 확인. NIT: `_get_agent_core_history` 폴백(희귀)은 event_type 부재라 일반 버블로 degrade(leak 아님, 표현만).
  - **#5 best-effort — NO-DEFECT**: add_member 선행 commit(autocommit) 후 이벤트 호출 try/except, 성공 응답은 try 밖 무조건. 이벤트 예외가 join 롤백 없음.
  - **#6 XSS — NO-DEFECT**: `pill.textContent`/`evTime.textContent` 사용, innerHTML sink 0. className/dataset 은 DOM property 대입(마크업 파싱 아님).
  - **#7 멱등 — NO-DEFECT(순차)**: 이벤트 호출이 `if not already:` 내부 → 재참여/기존 멤버 재호출 시 스킵(중복 알림 없음). NIT(UNCERTAIN): 락·유니크 제약 부재로 진짜 동시(더블클릭) 2요청이 둘 다 `already=False` 읽으면 이벤트 2건 가능 — 관측 시 dedupe 가드 권고.
- 핵심 판정: **BLOCKING #1 적발 → 수정 후 재검증 통과. 최종 BLOCKING 0.** NIT 3(#3 선행 anon-leak / #4 폴백 표현 / #7 동시 double-submit) 수용·추적.
- Verification: `py_compile`(agent_core·runtime_backend·app.py·share.py) + `node --check`(app.js) + agent 컨테이너 pytest **36 PASS**(신규 `test_gc_join_event_history` 5 + 회귀 dialect/tooluse-sanitize/group-history-merge/group-members). **배포 후 라이브 그룹 공유 join → pill 렌더 + 기존 멤버 unread +1 + @assistant 가 "참여했습니다"에 오응답 안 함 실측 필수**(PB-0008, deploy-backed 완료 기준).
- Human Approval Needed: 아니오 (기존 의도 완수 resume, additive 기능, 인가·스키마 무변경). deploy_scope: included(FIRST_REQUEST.md 전역) → 배포 자동.

## REV-20260704T130000-share-visibility-window [SUBAGENT:recall완전성·id-space·fork-exfil·필터우회·owner-answer·view·lifecycle 7렌즈 §18.8]
- Cycle: share-visibility-window (TASK-20260704). [from,to] 공유창 격리 + 말풍선 ☰ 통합. 위험 = Critical(접근제어·프롬프트 인젝션 방어). 사용자 결정 "라이브룸 + 멤버 필터" + owner-answer "표시 태그만".
- 검증 방식: §18.8 적대 보안 패널 1렌즈(general-purpose, 실 diff `git diff main...HEAD` 전수 read) — 7 공격 렌즈로 "가려진 구간이 bounded 참여자/프롬프트 인젝션에 도달하는가" 를 적대적으로 탐색.
- **적발 → 봉인 (commit a1ab4b0e)**:
  - **B1 (BLOCKER)**: `origin_request`/`thread_goal`(CONVERSATION CONTEXT)이 bounded 발신자의 system prompt 에 무필터 주입 — origin 은 대화 첫 요청(가려졌을 수 있음)에서 파생된 자유 텍스트라 window 로 못 자름 → self-service 인젝션("원래 요청이 뭐였어?")으로 유출. 봉인: `_suppress_conversation_context = (_recall_visibility is not None)` → bounded/DENY 발신자에게 CONVERSATION CONTEXT 블록 전체 스킵.
  - **M1 (MAJOR)**: owner/wider 멤버의 full-context 답변이 bounded 멤버의 post-join tail 에 남아 recall 로 유입("표시 태그만" 이 recall 은 미커버). 봉인: display-tag 를 recall 로 확장 — `core_messages.recall_floor_created_at`(alembic 0037) 에 답변의 recall 하한 기록(`_answer_recall_floor_ca`, recall_full=epoch sentinel) + windowed recall 쿼리에 `NOT (recall_floor_created_at < 뷰어 floor_ca)` 배제. **owner 생성은 무손상**(클램프 아님 — 사용자 "표시 태그만" 결정 정합, tag 기반으로 display+recall 양쪽 은닉).
  - **M2 (MAJOR)**: ceiling-only 멤버(floor_ca None) 답변 under-tag(`{}`) → floor-bounded 뷰어에게 노출. 봉인: ceiling-only=`recall_full`(하한 무제한).
  - **M3 (MAJOR)**: join 이 add_member(커밋) 후 stamp 를 별 트랜잭션으로 → stamp 실패 시 멤버가 무제한 접근으로 커밋·sticky(fail-open). 봉인: `commit=False` + 단일 `pg.commit()` + rollback 으로 원자화.
  - **m1 (MINOR)**: fork window 활성 + 표시행 0 시 core created_at 경계가 None 으로 떨어져 무필터 전량 복사 → `_win_bounded_empty` 가드(core 복사 0).
  - **m2 (MINOR)**: windowed 익명 공유 뷰의 topic(origin 파생) 요약 누출 → "공유된 대화" genericize.
- **SEALED (렌즈별)**: id-space bridge(created_at 항상 in-window 유도, 발명 없음, `>=` floor hide 방향), fork exfil(교집합 max/min, /fork·/duplicate 자동 clip, empty→400·PG오류→500 fail-closed, fork 는 tail 미포함이라 M1 면역), account cross-conv recall(owner-keyed + exclude-current, 구조적 격리), recall fail-closed(PG오류=DENY, windowed 는 MySQL unfiltered fall-through 금지), 8-older-user-turn trim(window-필터 후 동작이라 pre-floor 생존 불가), display 필터(PG+MySQL 양분기 + core-fallback skip + 카운트 필터 후 산출).
- **수용 잔여(MINOR, 문서화 §21.5)**: m3(sample-feedback 상단 gap 존재 probe — 하단 floor 만 게이트, 존재 oracle·비콘텐츠), m4(`has_more` 존재 oracle — 가려진 하위 이력 존재만 노출), bounded 멤버 대화목록의 topic(익명뷰는 봉인, 로그인 멤버 목록은 잔여). m5(경계 tie): 트랜잭션-시각 distinct 로 비실현.
- 핵심 판정: **BLOCKER 1 + MAJOR 3 적발 → 전부 봉인, 재검증 후 잔여 BLOCKER/MAJOR 0.** MINOR 존재-oracle 3 수용(콘텐츠 미노출).
- Verification: `make test`(agent 이미지 --no-deps) **전체 PASS**(신규/수정 포함) + ruff PASS + `node --check`(app.js) + `py_compile` 전 파일. **PB-0008 미실측**(worktree WSL 무인 브리지 3중벽 — 배포 후 라이브 시각검증: ☰ 메뉴·여기부터 범위 배너·windowed 공유 뷰·bounded 멤버 recall 격리 실측 권장).
- Human Approval Needed: 아니오 (사용자 PLAN-APPROVED Critical, 아키텍처·owner-answer 결정 사전 승인). deploy_scope: included → 배포 자동(첫 배포 1줄 표면화).
