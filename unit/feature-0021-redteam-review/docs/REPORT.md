---
doc_type: REPORT
feature_id: feature-0021-redteam-review
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary (2026-07-16 IA 재구성 반영)
assistant 답변 전달 전 자가 적대(red-team) 리뷰 — Claude Code 추론 패턴 (fresh-context
find→verify, effort scaling, auto-memory, progressive disclosure) 이식 완료. 코어 오케스트레이션
(agent_core choke-point) + [세션, 제품] 메모리 노트 (TTL) + 런타임 설정 + 관리 콘솔 "AI 추론"
탭까지 구현. cross-cut 코드 거주: feature-0002/0003/shared.

## 2. Progress
- Planned: 배포 후 라이브 회차 원장 적재 실증 (`redteam_review_rounds` 실제 행 + 콘솔 표시)
- In Progress: cycle-final (verify-completion → PR → 배포) — 회차 원장 cycle(CHG-20260729-0004)
- Done: 리서치(공식문서+실동작), 코어 3모듈(redteam/agent_notes/guidance_registry),
  choke-point 훅, alembic 0042, REDTEAM_* 런타임 설정, 권한+admin_reasoning 라우터,
  콘솔 탭/설정 패널, 단위 테스트 34건, ROUTEMAP 재생성, route-parity golden 갱신

## 2b. 관리 콘솔 IA (console-ia, 2026-07-16)
- **감사 > AI 추론**: red-team 리뷰 활동·판정 + 메모리 노트 현황 (console.reasoning.read, 감사 카테고리)
- **설정 > 프롬프트**: [전역 시스템 프롬프트(편집) / 작동 지침(조회) / 스킬(조회)] (지침/스킬 = system_prompt.global.read)
- **설정 > 운영 값 > AI 자가 리뷰**: REDTEAM_* 설정 (무변경)
- 전역 프롬프트 비교·검토: 기본 시스템 프롬프트 fallback 은 편집 정본(전역 프롬프트)과 중복이라 작동 지침 목록에서 제외

## 3. Recent Changes
- CHG-20260729-0004 — **자가검증·재검증 회차 단계 원장**(`redteam_review_rounds`, alembic 0048)
  신설 + 관리 콘솔 '감사 > AI 운영 현황 > 추론' 을 **대화 단위 격리 + 3계층 접이식**으로 재구성
  (사용자 요청: "각 대화의 마지막 리뷰사항만 기록된다"). 이전에는 한 답변당 요약 1행이라 최초
  리뷰·마지막 재검증만 남았고 중간 회차가 소실됐다. 콘솔 정렬은 대화 최근순(desc) / 대화 내
  진행순(asc). 상세 MODIFY.md.
- CHG-20260715-0001 — 최초 구현 (상세 MODIFY.md)
- CHG-20260722-0001 — "리뷰 실패" 진단(=리뷰어 100% 타임아웃, DB 실측 8/8 @25s) + 리뷰어 토큰
  할당량(REDTEAM_MAX_TOKENS) 콘솔 설정 신설 (타임아웃은 기존 노출). 표시/fail-open 은 의도된
  설계였고, 근본 원인은 리뷰어 alias 고정 thinking(5000) → 상시 25s. 상세 MODIFY.md.
- CHG-20260724-0001 — **리뷰어 모델을 답변 모델에 정합** (사용자 요청). 이전엔 항상
  claude-haiku-4-chat 고정 → 이제 haiku 답변→haiku 리뷰, sonnet 답변→sonnet 리뷰
  (`resolve_review_model`, `AGENT_REDTEAM_MODEL` env pin 유지). 필수 호환: sonnet OAuth
  identity 주입(429 게이트) + adaptive effort=low(적대 패널 MAJOR — timeout→리뷰 skip 회귀 방지,
  CHG-0722 의 25s 타임아웃 근본 원인과 동일 lever). `redteam_reviews.model` 실제 리뷰어 기록.
  상세 MODIFY.md · 적대 패널 REV-20260724T071500.
- CHG-20260724-0002 — **BLOCK 검출 후 답변 미수정 전달 근본 원인 수정**: revise/rederive
  재프롬프트가 지시를 trailing `role: system` 으로 붙여 초안이 Anthropic prefill 이 됨 →
  재작성 대신 이어쓰기 → 완결 초안은 빈 응답 → fail-open 미수정 전달. 라이브 실측
  redteam_reviews verdict='revise' 42건 중 35건(83%) revision_applied=false ·
  실패 run 전부 revise 호출 completion_tokens=3. 지시 `role: user` 로 교정 +
  `_build_self_review_messages` 불변식 헬퍼 + 다회 draft 앵커링(적대 WARN) + 회귀 테스트. 상세 MODIFY.md.
- CHG-20260727-0001 — **"warning·block 이 있어도 항상 1회 검증 후 답변" 리포트의 근본 수정**.
  라이브 판정 데이터로 3원인 분리 — ① WARN 무조치 = 설계 의도(유지) · ② 일반 강도에 재검증이
  아예 없음(`verify_pass = ordinal >= 2`) · ③ 재검증이 결함 잔존을 판정해도 `MAX_REVISIONS=1`
  상한에서 종료. ②③ 을 결함으로 판정해 재검증 게이트 일반화(`REDTEAM_VERIFY_MIN_LEVEL` 기본 0)
  + 결함 해소까지 반복(`REDTEAM_REVISE_UNTIL_RESOLVED` 기본 1, 상한 없음) + 사용자 '즉시 답변'
  /취소 탈출구 + 무진전·백스톱 가드 + 잔존 결함 3중 표면화(alembic 0045 관측 컬럼 · 콘솔
  타임라인 ⑤ · 답변 말미 고지). 리뷰어가 라운드 이력 + 같은 대화 직전 판정을 이어받아 해소
  여부를 먼저 판정(수렴 조건). 상세 MODIFY.md.
- CHG-20260727-0002 — §18.8 적대 패널(2 렌즈) **BLOCKING 4 · MAJOR 6 · MINOR 6 전건 반영**.
  특히 리뷰 기억이 공유창 window 격리를 우회하는 5번째 LLM 도달 경로를 만들 뻔한 건을
  fail-closed 로 봉인하고, 무효였던 '즉시 답변' 1회차를 run 스코프 플래그로 복구했다
  (상한 제거의 안전성이 이 탈출구에 걸려 있음). 상세 REV-20260727T174500.
- CHG-20260727-0003 — POST-DEPLOY 라이브 검증 기록(docs-only): alembic 0045 실재 · 격리
  fail-closed 인과 실증 · PB-0008 콘솔 표면화. 상세 TEST.md §3 Run 2026-07-27.
- CHG-20260728-0001 — stale 체크박스 정리(docs-only): subtab-sticky(커밋 08704f3d, 라이브
  배포본에 `position: sticky` 실재)와 §9 라이브 재검증(PR #938 머지 + `revision_applied=true`
  15/21 관측)이 이미 완료돼 있었음을 실측 확인하고 닫았다.
- 총 변경 횟수: 9+ (구현 · anchor 정합 · 콘솔 IA 재구성 · 리뷰어 토큰 설정 · 모델 정합 ·
  revise prefill 수정 · 수렴 반복 검증 · 적대 패널 반영 · POST-DEPLOY 검증)

- CHG-20260728-0002 — **원 요청 정합 교정 (answer-origin-realign)** (사용자 요청). 자가 검증
  후 전달되는 답변이 처음 요청사항이 아니라 **직전 문맥(내부 리뷰 결함 목록)에 응답하는
  뉘앙스**를 띠던 결함. 근본 원인은 수정 지시가 초안 컨텍스트의 trailing user turn 이라
  생성 지점 최근접 맥락이 결함 목록이라는 **구조**(2026-07-24 prefill 회귀 방지 불변식의
  부작용)다. 그 배치는 유지한 채 같은 recency 지렛대를 반대로 써서 ① 지시 **맨 끝**에 원 요청
  재앵커 + 출력 계약(추가 호출 0), ② 잔재는 결정론 탐지 + 내용 보존 재서술 1회(콜백 내부 →
  verify 통과). 폐기 가드(무산출·60% 미만 길이·메타 잔존)·연속 거절 2회 비용 가드·
  `REDTEAM_ANSWER_REALIGN` 스위치·bounded 발신자 `thread_goal` 억제. 마이그레이션 없음.
  상세 MODIFY.md · REV-20260728T093528.

- CHG-20260729-0001 — **다중 턴 요청 맥락 회귀 교정** (사용자 리포트). CHG-20260728-0002 의
  재앵커가 다중 턴에서 역효과 — 리뷰어와 재앵커가 **현재 턴 발화만** 보고(리뷰어는 fresh-context,
  첨부는 digest 밖) 실질 답변을 "과답변"·"근거 없는 창작" 으로 오판, 모델이 그에 응해 내용을
  지우자 반박할 claim 이 사라져 리뷰어가 통과 — **축소가 곧 수렴이 되는 퇴행 경로**. 라이브
  실측(run #132): 14 라운드 만에 3,170자 리뷰가 152자 비-답변으로 붕괴, 사용자가 같은 요청을
  세 번째 턴에 다시 눌러야 했다. 4축 교정(리뷰어 CONVERSATION REQUEST+첨부 근거·과답변 오판
  금지 / 앵커 2층·계약 addressing 전용 / 붕괴 가드 `revise_collapsed`). 마이그레이션 없음.
  상세 MODIFY.md · FUNCTION.md §7.4 · REV-20260729T110000.

## 4. Open Issues
- make test 중 pre-existing 환경 의존 실패 4건 (본 feature 무관 — TEST.md §3 Run 기록 참조):
  runtime_settings 2건은 `.env` 의 AGENT_TIMEOUT_SEC=300 이 기본값 60 단정과 충돌 (main 동일
  실패), routine_dbanalysis·item11_batch8 2건은 main 컨테이너가 라이브 PG 네트워크에 붙어
  통과하던 것이 격리 worktree 네트워크에서 정직하게 실패 (PG 부재). 후속 개선 후보: §8.

## 5. Test Status
- (2026-07-29 CHG-20260729-0004) 회차 원장 + 대화 단위 콘솔 — 신규 12건(원장 6 · 콘솔 그룹 6)
  포함 대상 파일 **142건 PASS**·ruff clean. PB-0008 실 Windows 브라우저 시각검증 PASS
  (대화 그룹 12·리뷰 18 렌더, 회차 48단계 렌더, 대화 라벨 중복 결함 1건 발견·교정 —
  TEST.md §3 Run 2026-07-29 (3)). `make test` 실패 15건은 main 에서도 동일한 환경성 baseline.
- 자동 테스트: 신규 34건 PASS (redteam 18 · agent_notes 8 · admin_reasoning 8) + 기존 스위트
  회귀 0 (환경 의존 4건 제외 — 상세 TEST.md §3). 적대 패널(REV-0002) BLOCK2+MAJOR1+MINOR3 반영·재검증 완료.
- (2026-07-22 CHG-0001) 리뷰어 토큰 설정 추가 후 test_redteam 36건(신규 5) + runtime_settings +
  admin_reasoning 합산 87건 PASS·ruff clean (TEST.md §3 Run 2026-07-22). 프론트 무변경.
- (2026-07-24 CHG-20260724-0001) 모델 정합 후 test_redteam **45건 PASS**(신규 9 — resolve 매핑/폴백/pin 3·
  identity 주입 sonnet/haiku 2·effort 주입 sonnet/haiku 2·orchestrate 스레딩 2)·ruff clean(변경 5파일).
  전체 feature-0002+0003 회귀는 환경 의존 4건만 실패(내 변경 무관 — `.env` AGENT_TIMEOUT_SEC=300 2건은
  `-e AGENT_TIMEOUT_SEC=60` 강제 시 2 passed 로 확증, PG 부재 2건). §18.8 적대 패널(REV-20260724T071500):
  BLOCK 0, MAJOR1(effort=low)+MINOR2(doc·forward-caveat) 반영/수용. 상세 TEST.md §3(20260724T0709 fragment).
- (2026-07-27 CHG-20260727-0001/-0002) red-team 단위 **81건 PASS**(기존 46 + 신규 21 + 패널
  회귀 14) + 전체 회귀 PASS · ruff clean · migrate-lint PASS(0045 expand-safe, head 단일).
  상세 TEST.md §3 · test-runs.d/20260727T1600.
- (2026-07-27 CHG-20260727-0003) **POST-DEPLOY 라이브 실증 PASS** — alembic 0045 실재 ·
  공유창 window 격리 fail-closed 인과 확정(동일 대화 플래그 토글 0건↔1건) · PB-0008 실
  Windows 브라우저로 '결함 잔존 전달 (7d)' 타일 · 타임라인 ③④⑤ · 미해소 지적 앰버 블록 ·
  설정 패널 신규 5항목 렌더 확인. 실증용 임시 행 2건은 삭제·잔존 0 확인.
- (2026-07-28 CHG-20260728-0002) answer-origin-realign 후 **전체 2814 passed / 0 failed**
  (동일 컨테이너·동일 명령의 main baseline 2791 대비 순증 23 = 신규 테스트 수, 회귀 0) ·
  ruff clean · 마이그레이션 없음 · 프론트 자산 무변경. 인라인 자기검증에서 MAJOR2(재추론
  재서술의 낡은 근거 되돌림 / 상한 없는 루프의 호출 증폭)+MINOR1(DBA 어휘 오탐) 적발·전건
  커밋 전 반영. 상세 TEST.md §3 · test-runs.d/20260728T0935.
- (2026-07-29 CHG-20260729-0001) 회귀 교정 후 **전체 2857 passed / 0 failed** (main baseline
  2835 대비 순증 22 = 신규 테스트 수, 회귀 0) · ruff clean · 마이그레이션 없음. 붕괴 재현 테스트는
  수정 전 코드에서 실패하도록 작성(가드가 결함 자체를 검증). 상세 TEST.md §3 ·
  test-runs.d/20260729T1100.
- 미검증 항목: 리뷰어 실판정 품질 (라이브 축적 관찰), effort=low 로 sonnet 리뷰 타임아웃
  소멸(라이브 관찰), **실제 답변에서의 수렴 분포**(`revision_rounds>1` · `stop_reason`) —
  배포 이후 새 판정 표본 미발생, 렌더 경로만 합성 행으로 실증 (TEST.md §4),
  **answer-origin-realign 의 라이브 교정 효과·재서술 발동률** (단위 테스트는 계약만 고정 —
  문체 판정 불가, 트래픽 누적 후 stderr/`_rt_meta` 관측, TEST.md §4).

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 없음 (deploy_scope: included — cycle-final 후 자동 배포 진행)

## 8. Suggested Improvements
- make test 의 컨테이너가 라이브 compose 네트워크에 합류해 "DB 필요 테스트가 우연히 통과"
  하는 문제 — `--network none` 격리 또는 env 고정(.env.test)으로 결정론화 후보.
- runtime_settings 기본값 단정 테스트 2건의 env 내성화 (monkeypatch.delenv).
- 리뷰 판정 rubric 의 LLM-as-judge 정확도 평가 (golden 셋) — feature-0002 eval harness 연계.
