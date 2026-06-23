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
