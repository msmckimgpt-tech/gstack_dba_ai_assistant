---
doc_type: TASK
feature_id: feature-0021-redteam-review
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
feature_status_updated: 2026-07-15
feature_status_date: 2026-07-29
feature_status_note: "답변 자가 적대 red-team 리뷰(초안→적대 리뷰→결함 수정→재검증→전달, 결함 해소까지 반복) + 원 요청 정합 교정(answer-origin-realign, 07-28) — 수정 지시가 trailing user turn 이라 답변이 원 요청 대신 직전 문맥(리뷰 결함 목록)에 응답하던 구조적 결함을 재앵커(지시 맨 끝 원 요청 블록 + 출력 계약, 추가 호출 0) + 메타 프레이밍 결정론 탐지 후 내용 보존 재서술 1회(콜백 내부 → verify 통과)로 교정. 폐기 가드(무산출·60% 미만 길이·메타 잔존)·연속 거절 2회 비용 가드·REDTEAM_ANSWER_REALIGN 스위치·bounded 발신자 thread_goal 억제. 신규 23건 PASS·전체 2814(baseline 2791) 회귀 0·마이그레이션 없음. (07-29) 그 재앵커가 다중 턴에서 역효과 — 리뷰어·재앵커가 현재 턴 발화('네 맞습니다')만 보고 실질 답변을 과답변/창작으로 오판, 14 라운드에 3,170자 리뷰가 152자 비-답변으로 붕괴(라이브 run #132). 4축 교정: 리뷰어에 CONVERSATION REQUEST+첨부 근거 제공·과답변 오판 금지, 앵커 2층(대화 요청/직전 발화)·계약을 addressing 전용, 붕괴 가드(초안 30% 미만 미채택, revise_collapsed). 신규 22건·전체 2857(baseline 2835) 회귀 0"
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-24 (redteam-model-align cycle)

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - feature-0002: `src/modules/redteam.py`(신규), `src/modules/agent_notes.py`(신규),
    `src/modules/guidance_registry.py`(신규), `src/agent_core.py`(choke-point 훅·노트 주입),
    `src/modules/ask.py`(노트 TTL reaper), `alembic/versions/20260715_0042_redteam_reviews.py`(신규)
  - shared: `runtime_settings.py`(REDTEAM_* 스펙 + serialize 그룹)
  - feature-0003: `src/web_context.py`(권한 1건 + admin catchup), `src/routers/admin_reasoning.py`(신규),
    `src/static/admin.html`(탭/pane), `src/static/admin.js`(패널 wiring + PERMISSION_DEPENDENCIES)
  - repo: `docs/ROUTEMAP.md`(재생성)
- **접근 방법:** Claude Code 의 fresh-context 적대 리뷰(find→verify)·effort scaling·
  auto-memory·progressive disclosure 패턴을 제품 답변 파이프라인의 단일 choke-point
  (`agent_core.py` `result["answer"]` 확정 지점)에 결정론적 오케스트레이션으로 이식.
  리뷰는 fail-open, 기본 haiku 급 저비용 모델, 추론 강도 게이팅. 노트는 /shared 임시
  파일 + ask-worker reaper TTL 정리. 콘솔은 read-only 신규 라우터 + 신규 권한.
- **위험도:** Major (답변당 LLM 호출 추가 = 외부 비용; 완화 — 저비용 모델·강도 게이팅·
  런타임 on/off·fail-open. 인증/인가·파괴적 변경 없음, 마이그레이션 additive)

<!-- PLAN-APPROVED: entry persona arg-given dispatch (사용자 요청 명시 위임, 2026-07-15).
     plan 표면화 후 진행 — AGENTS.md §7.1 Major 절차. -->

## 3. Task Queue
- [x] TASK-20260715T140100-console-panel: 관리 콘솔 "AI 추론" 탭 (admin_reasoning 라우터 +
      권한 + admin.html/admin.js + 설정 패널 "AI 자가 리뷰")
- [x] TASK-20260715T140101-tests-routemap: 단위 테스트 (redteam fail-open/게이팅,
      agent_notes cap/TTL, 라우터 RBAC) + ROUTEMAP 재생성 + make test
- [x] TASK-20260715T140102-deploy-verify: PR #819/#821 병합·배포(23b8faba)·alembic 0042·PB-0008 PASS
- [x] TASK-20260716-console-ia: 관리 콘솔 IA 재구성 — 감사>AI추론 + 설정>프롬프트 분리 (배포·PB-0008 PASS)
- [x] TASK-20260716-console-subtabs: 유사 항목 서브탭 통합 (배포·PB-0008 PASS)
- [x] TASK-20260716-subtab-sticky: 서브탭 바 화면 상단 sticky 고정 (CSS, 사용자 요청) —
  커밋 `08704f3d` 로 구현·main 반영 완료. 체크박스만 미갱신이었다(2026-07-28 확인:
  라이브 배포본 `/static/styles.css` 에 `position: sticky; top: 0; z-index: 6` 실재,
  web 컨테이너 내 파일도 동일). 스크롤 컨테이너별 배경 오버라이드(ai-console=--bg)까지 포함.
- [x] TASK-20260722-review-token-setting: "리뷰 실패"=리뷰어 LLM 100% 타임아웃 진단(DB 8/8 @25s) +
  리뷰어 토큰 할당량(REDTEAM_MAX_TOKENS) 콘솔 '설정 > AI 자가 리뷰' 노출 (타임아웃은 기존 노출).
  테스트 87건 PASS·ruff clean·프론트 무변경. 배포 대기.
- [x] TASK-20260724T0709-redteam-model-align: 리뷰어 모델을 답변 모델에 정합(haiku→haiku-chat,
  sonnet→sonnet-chat; AGENT_REDTEAM_MODEL env pin 유지). 이전엔 항상 claude-haiku-4-chat 고정.
  sonnet 리뷰어 OAuth identity 주입(429 게이트 회피) + adaptive effort=low(timeout/truncation 회피,
  적대 패널 MAJOR) + record model/admin 표시 정합. 신규 테스트 9건 PASS·ruff clean·프론트 무변경.
- [x] TASK-20260727T160000-converge-until-resolved: 사용자 리포트("warning·block 이 있어도 항상
  1회 검증") 진단 → 라이브 판정 데이터로 3원인 분해(WARN 무조치=의도 / 일반강도 재검증 부재 /
  재검증 결함잔존에도 상한 1 종료). 재검증 게이트 일반화(REDTEAM_VERIFY_MIN_LEVEL 기본 0) +
  결함 해소까지 반복(REDTEAM_REVISE_UNTIL_RESOLVED 기본 1, 상한 없음) + 사용자 '즉시 답변'/취소
  탈출구(abort_fn) + 무진전·백스톱 가드 + 잔존 결함 3중 표면화(기록/콘솔/답변 고지, alembic 0045).
- [x] TASK-20260727T160100-reviewer-memory: 리뷰어가 대화 내부 격리 환경에서 자기 리뷰 이력과
  assistant 수정본을 기억해 맥락에 맞게 판정 (라운드 이력 + conversation 스코프 직전 판정
  REDTEAM_HISTORY_CONV_LIMIT, 해소된 지적 재보고 금지 프롬프트 — 반복 루프의 수렴 조건).
- [x] TASK-20260727T182000-postverify: PR #957 배포분 POST-DEPLOY 라이브 검증 3건 —
  alembic 0045 실재 · 공유창 window 격리 fail-closed 인과 실증(플래그 토글 대조) ·
  PB-0008 콘솔 표면화(타일·타임라인 ③④⑤·미해소 블록·설정 신규 5항목). 실증용 임시 행은
  삭제·잔존 0 확인. 실판정 수렴 분포는 트래픽 대기(TEST.md §4 미커버 명시).
- [x] TASK-20260728T093528-answer-origin-realign: 사용자 리포트("추론·자가적대리뷰 완수 후
  전달되는 답변이 처음 요청사항의 문맥보다 **직전 문맥**에 답변하는 뉘앙스") 진단 → 근본
  원인은 수정 지시가 초안 컨텍스트의 trailing user turn 이라 **생성 지점 최근접 맥락이 리뷰
  결함 목록**이라는 구조. ① 수정·재추론 지시 맨 끝에 원 요청 재앵커 블록 + 출력 계약(메타
  표현·직전 맥락 지시어 금지, 구성은 원 요청이 결정) — 추가 LLM 호출 0. ② 잔재는 결정론
  탐지기 + 내용 보존 재서술 1회(탐지 시에만 호출, 콜백 내부라 verify 통과). 폐기 가드
  (무산출·60% 미만 길이·메타 잔존) + 연속 거절 2회 비용 가드 + `REDTEAM_ANSWER_REALIGN`
  스위치 + bounded 발신자 thread_goal 억제(`_realign_thread_goal`). 신규 23건 PASS ·
  전체 2814 passed/0 failed · ruff clean · 마이그레이션 없음.

## 4. In Progress
- 없음

## 5. Blocked
- 없음

## 6. Done
- TASK-20260715T140099-core: redteam/agent_notes/guidance_registry 모듈 + agent_core 훅 +
  runtime_settings 스펙 + alembic 0042 (구현·단위검증 완료)
- 적대 검증 패널 (REV-20260715-0002) — BLOCK2(MAX_MIGRATION·jsonb cast)+MAJOR1(인젝션 승격)+MINOR3 in-cycle 반영·재검증
- 리서치 (Claude Code 공식문서·엔지니어링 블로그·실동작 introspection + 제품 파이프라인/
  콘솔 구조 탐색) — 산출물: DECISIONS.md ADR-20260715T140000, REVIEW.md 근거 기록

## 7. Next Action
- 코어 모듈 구현 → 콘솔 → 테스트 → cycle-final → 배포

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 단위 테스트(unit test)가 통과한다 (AGENTS.md §8.2 단계 1)
- [ ] 전체/통합 테스트(integration test)가 통과하거나, 미작성 사유와 커버 계획이 TEST.md §4에 기록되었다
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 시)
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다

## 9. 후속 수정 — revise/rederive prefill 결함 (2026-07-24)
BLOCK 검출 후 답변이 미수정 전달되던 근본 원인(수정 지시를 trailing `role: system` 으로 붙여
초안이 Anthropic prefill 이 됨 → 재작성 대신 이어쓰기 → 완결 초안은 빈 응답 → fail-open 미수정
전달) 을 라이브 추적으로 확증하고 `role: user` 로 교정. 상세: MODIFY.md CHG-20260724-0002.
- [x] 근본 원인 라이브 추적·재현 확증 (redteam_reviews 83% revision_applied=false · completion_tokens=3 · gateway 재현)
- [x] `_build_self_review_messages` 헬퍼 신설 + 두 closure 적용 (지시=trailing user turn)
- [x] 적대 리뷰 WARN(다회 수정 stale-draft 앵커링) 반영 — 콜백 (instruction, draft) 계약
- [x] 회귀 테스트 추가 (test_self_review_messages 3 + test_redteam 다회 draft 앵커링) — 통과
- [x] verify-completion --pre-commit PASS + 커밋(79f8bda5) + PR #938
- [x] main 병합(rebase 후) + 배포 (worker/ask-worker/web) + 라이브 재검증 (신규 revise
  revision_applied=true) — PR #938 머지(2026-07-24T07:37Z). 2026-07-28 확인: prefill fix
  배포(16:20) 이후 `redteam_reviews` 표본 21건 중 **revision_applied=true 15건** 관측으로
  라이브 재검증 충족(수정 전에는 42건 중 35건이 false 였다). 체크박스만 미갱신이었다.

## 11. 회귀 교정 — 다중 턴 요청 맥락 (review-request-context, 2026-07-29)
§10 재앵커가 **다중 턴에서 역효과**를 냈다는 사용자 리포트("처음 요청했던 '쿼리 리뷰'는 수행하지
않고 두 번째 대화의 '네 맞습니다.' 에만 정합하게 답변")를 라이브 판정 데이터로 진단·교정.
상세: FUNCTION.md §7.4 · MODIFY.md CHG-20260729-0001 · REVIEW.md REV-20260729T110000.
- [x] 라이브 기전 확정 — 대화 `20260729013313-2211841a` run #132: **14 라운드** 수정 후
      `stop=resolved`, 최종 152자. 리뷰어 BLOCK 2건이 원인이며 **둘 다 구조적 false positive**
      (리뷰어가 현재 턴 발화만 봄 / 첨부 본문이 evidence digest 에 없음).
- [x] D1 — `run_review` 에 `CONVERSATION REQUEST` 주입 + 프롬프트에 "짧은 후속 발화 대비 과답변
      보고 금지" · "삭제로 결함 해소 = REGRESSION, BLOCK" 규칙 추가.
- [x] D3 — evidence digest 에 `USER-ATTACHED FILES` 매니페스트+발췌(자기 예산 선점).
- [x] D2 — 재앵커 2층([대화 요청]/[직전 발화]) + 계약을 addressing 전용으로 한정(범위 축소 금지
      문구 명시, 초판의 축소 유발 문구 제거).
- [x] D4 — 붕괴 가드(초안 30% 미만 미채택, `stop_reason=revise_collapsed`) + 콘솔 라벨.
- [x] 누출 게이트 — `_review_conversation_request`/`_review_attachments` 가 bounded 발신자에
      대해 fail-closed(테스트 고정).
- [x] 테스트 22건 신규(라이브 붕괴 재현 케이스 포함)·전체 2857(baseline 2835) 회귀 0·ruff clean.
- [x] TASK-20260729T120000-review-continuation: **라이브 유도 측정 후속** — 배포 후 동일 구조
      대화를 실제로 태워(2턴: 상세 리뷰 요청 → "네 맞습니다.") 회귀 소멸 확인(rounds=0·BLOCK 0·
      797자 실질 continuation). 같은 초안 A/B 에서 grounding 오판 2→0 확인, 대신 반대 방향
      과교정(이미 전달한 리뷰 재요구) 2/3 관측 → continuation 규칙 추가로 1/4 로 감소.
      잔여는 답변을 늘리는 방향이라 붕괴 가드와 무충돌(REVIEW 비대칭 논거).
- [x] TASK-20260729T125000-continuation-postverify: continuation 가드 **배포본**(`44d70215`)에서
      재확인 — Run 3 의 2/3→1/4 는 배포 *전* 프롬프트 주입 측정이라 배포 검증으로 등치하지 않는다.
      같은 대화에 짧은 후속 발화를 **연속 2회째** 태워 `id=140` **pass·rounds=0·BLOCK 0·WARN 0**
      · 566자 실행 체크리스트 확인(수정 전 붕괴 지점).

## 10. 후속 개선 — 원 요청 정합 (answer-origin-realign, 2026-07-28)
자가 검증을 거쳐 전달된 답변이 **처음 요청사항이 아니라 직전 문맥(내부 리뷰)에 답하는
뉘앙스**를 띤다는 사용자 리포트를 구조적 원인으로 환원하고 교정. 상세: MODIFY.md
CHG-20260728-0002 · REVIEW.md REV-20260728T093528-answer-origin-realign.
- [x] 근본 원인 특정 — 수정 지시가 초안 컨텍스트의 **trailing user turn**(prefill 회귀 방지
      불변식, 2026-07-24 §9)이라 생성 지점 최근접 맥락이 리뷰 결함 목록. 그 위치는 유지하고
      **같은 recency 지렛대를 반대로** 쓰는 방향 채택.
- [x] 1차 방어 — `build_request_anchor` + `_ANSWER_CONTRACT` 를 revise/rederive 지시 **맨 끝**에.
      추가 LLM 호출 0.
- [x] 2차 방어 — `detect_meta_framing`(결정론·도입부 한정) + `realign_answer`(내용 보존 재서술
      1회, 콜백 내부 실행이라 verify 통과) + 폐기 가드(무산출·60% 미만 길이·메타 잔존).
- [x] 비용 가드 — 탐지 없으면 호출 0 · 반복 루프에서 연속 거절 2회면 잔여 라운드 시도 중단.
- [x] 누출 게이트 — `_realign_thread_goal` 로 bounded 발신자 `thread_goal` 억제(system 프롬프트
      CONVERSATION CONTEXT 와 동일 축) + `<<USER_REQUEST>>` datamark.
- [x] 오탐 가드 — DBA 답변의 정당 어휘("내용을 수정합니다" DML 설명)를 메타로 오인하지 않도록
      탐지 목적어를 `답변|초안` 으로 한정.
- [x] 테스트 23건 신규(전체 2814 passed / baseline 2791) · ruff clean · 마이그레이션 없음.
- [x] TASK-20260728T185500-realign-postverify: PR #1026 머지 → `make deploy-all` 배포(web 롤링
      + 90s soak + 워커 롤아웃, `deploy_scope: included`) → POST-DEPLOY 실증 — 4 컨테이너
      `GIT_COMMIT=f0b3d3a5` · 이미지 baked 심볼 확인 · `/healthz` 200 · **PB-0008 실 Windows
      브라우저**로 신규 설정 행(원 요청 기준 답변 정합 교정 / 즉시 반영 / effective 1) 표출·정렬
      확인. 답변 뉘앙스의 라이브 교정 효과는 표본 대기(TEST.md §4 미커버).
- [ ] (후속) realign 관측치의 관리 콘솔 노출 — 현재는 `_rt_meta` + stderr 만. DB 컬럼 신설이
      필요해 별도 cycle 로 분리(본 cycle 은 마이그레이션 없음 원칙 유지).

## 20260729T1230-review-rounds-ledger — 회차 단계 원장 + 대화 단위 콘솔 (2026-07-29)
사용자 리포트: "'감사 > AI 운영 현황 > 추론' 에서 자가 적대 리뷰 활동은 **각 대화의 마지막
리뷰사항만** 기록되는 것으로 확인된다. 자가검증·재검증 **회차 단계를 모두** 기록하고, 스크롤
폭증을 막게 요소를 **대화 단위로 격리**하고 각 단계를 **접기/펼치기** 가능하게, 대화는 최근
순(desc)·대화 내 리뷰는 회차 순(asc)으로 정렬하라."

원인 두 겹: (a) `orchestrate_review` 가 루프 종료 시 **요약 1행만** INSERT — `findings` 는
최초 리뷰, `verify_findings` 는 마지막 재검증이라 중간 회차가 어디에도 남지 않았다.
(b) 콘솔이 리뷰를 id DESC **flat 목록**으로만 내려 같은 대화의 리뷰가 흩어지고 페이징 경계에서
쪼개졌다. 상세: FUNCTION.md §7.5 · MODIFY.md CHG-20260729-0004 · REVIEW.md REV-20260729T123000.
- [x] 회차 원장 테이블 신설 — alembic `0048_redteam_review_rounds`(신규 테이블 + GRANT,
      expand-safe) + `agent_runtime_schema.sql` 부트스트랩 미러(0045 컬럼 누락도 함께 정합)
- [x] `redteam.py` — `rounds_ledger` 누적(0회차 자가검증 → N회차 수정 → N회차 재검증) +
      폐기 라운드(`revise_failed`/`no_progress`/`revise_collapsed`/`verify_error`/`unverified`)
      도 note 로 보존 + `record_review(..., rounds=)` 요약 커밋 **후** 별도 트랜잭션 배치 INSERT
- [x] 답변 본문 비저장 — 회차별 길이(`answer_chars`)만 기록 (`/notes` 의 "본문 비반환" 규약 정합)
- [x] `admin_reasoning.py` — 페이징 단위를 **대화**로 전환(`_query_conversation_page`):
      대화 keyset = MAX(id) DESC, 대화 내부 id ASC, 대화당 상한 20건(`capped` 표시) +
      `_attach_rounds` 로 회차 원장 동봉(0048 미적용 이미지는 `rounds_available:false` 폴백)
- [x] `admin.js` — 대화 격리 컨테이너 → 리뷰(run) → 회차 단계의 **3계층 접이식**(`<details>`),
      기본 접힘(최근 대화 1개만 펼침) + "대화 더 보기" 는 그룹 append(펼침 상태 보존)
- [x] `styles.css` — 대화 그룹/회차 단계 스타일(단계별 좌측 색 밴드: 통과/결함/폐기)
- [x] 단위 테스트 15건 추가(회차 원장 8 · 콘솔 그룹 페이징 7) — 대상 파일 145건 PASS·ruff clean
- [x] PB-0008 실 Windows 브라우저 시각검증 (visual_verification_scope: always) — 격리 검증
      컨테이너 + 실 Chrome. 검증 중 대화 라벨 중복(같은 分 대화 구분 불가) 발견·교정
- [x] codex 적대 리뷰(REV-20260729T134100) — P1 1건(원장 INSERT 원자성: autocommit 커넥션에서
      executemany 는 행별 커밋 → 단일 multi-VALUES statement) + P2 3건 수정, 1건 근거 기록 후 수용
- [x] verify-completion PASS → 커밋(ba365d5e) → PR #1044 머지(f87bf1da) → 배포(scope=all)
- [x] POST-DEPLOY 라이브 실증 — alembic 0048 적용·GRANT 확인, 검증 질문 1건으로 회차 원장
      2단계 적재(0 review BLOCK1 → 1 revise note=revise_failed) 및 콘솔 표시 확인 (TEST.md Run (4))

## 20260729T1420-rounds-visual-fixes — 다회차 육안 검증 후 표시 교정 (2026-07-29)
사용자 요청("다회차 표본이 확보되었습니다. 정상 작동 육안 검증")으로 라이브 10단계 표본
(review `id=145`: 수정 4회 · 도구 재추론 3회 · BLOCK 3건 미해소)을 PB-0008 로 확인한 결과,
회차 목록 자체는 원장과 정확히 일치했으나 **다회차에서만 드러나는 표시 결함 2건**을 발견했다.
상세: MODIFY.md CHG-20260729-0006 · REVIEW.md REV-20260729T142000.
- [x] 라이브 다회차 표본 원장 대조 — 10단계(0 review → 4×(revise/verify) → 5 revise 폐기)가
      화면 라벨·수정 방식·도구 라운드·길이까지 DB 와 1:1 일치 확인
- [x] 결함 ①: 폐기 회차(`revise_failed`)의 사유가 **접힌 요약에 없어** 그 회차를 펼쳐야만
      "왜 여기서 멈췄나" 를 알 수 있었다 → 요약 라인에 사유 표기
- [x] 결함 ②: 회차 시각이 10개 전부 동일(원장은 루프 종료 후 배치 기록 → 컬럼 DEFAULT now())
      → (a) 회차마다 실제 종료 시각 기록(`_now_utc()` + `COALESCE(%s, now())`),
      (b) 기존 배치 기록은 시각을 숨기되 **숨긴 사실을 1줄 안내**(조용한 제거 금지)
- [x] 단위 테스트 2건 추가(147 passed·ruff clean) + codex 리뷰(P1 0건, P2 2건 중 1건 반영)
- [x] PB-0008 재검증 — 10단계 표본에서 사유 표기·시각 숨김·안내 문구 확인

## 20260729T1730-reasoning-hint-trim — 추론 탭 안내 문구 축약 (2026-07-29)
사용자 지적: "사용자에게 의미없는 정보가 나열되었습니다" (자가 적대 리뷰 활동 섹션 안내 문단).
회차 원장 cycle 에서 안내에 **조작법**(대화를 펼치면 …, 접기/펼치기 됩니다)과 **다른 화면
경로**(설정 > AI 자가 리뷰 / 설정 > 프롬프트)를 덧붙여 3줄 벽이 됐다 — 화면을 보면 아는 것을
매번 읽히게 만든 것. 상세: MODIFY.md CHG-20260729-0007.
- [x] 안내를 "이 화면이 무엇인가" 한 문장(57자)으로 축약 — 조작법·타 화면 경로 제거
- [x] PB-0008 시각검증 — 목록이 3줄 위로 올라와 첫 화면 정보 밀도 개선 확인
- [x] **이전 cycle 미커버 항목 확정** — 배포 후 다회차 표본(review `id=159`, 5단계)에서
      회차마다 **서로 다른 실제 시각**(17:25:01 → 17:25:44 → 17:26:11 → 17:27:03 → 17:27:33,
      `distinct_ts=5/5`)이 기록되고 화면에도 그대로 표시됨을 확인
