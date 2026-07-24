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
- Planned: PB-0008 콘솔 시각검증 (배포 후), 라이브 리뷰 판정 1건 실증
- In Progress: cycle-final (verify-completion → PR → 배포)
- Done: 리서치(공식문서+실동작), 코어 3모듈(redteam/agent_notes/guidance_registry),
  choke-point 훅, alembic 0042, REDTEAM_* 런타임 설정, 권한+admin_reasoning 라우터,
  콘솔 탭/설정 패널, 단위 테스트 34건, ROUTEMAP 재생성, route-parity golden 갱신

## 2b. 관리 콘솔 IA (console-ia, 2026-07-16)
- **감사 > AI 추론**: red-team 리뷰 활동·판정 + 메모리 노트 현황 (console.reasoning.read, 감사 카테고리)
- **설정 > 프롬프트**: [전역 시스템 프롬프트(편집) / 작동 지침(조회) / 스킬(조회)] (지침/스킬 = system_prompt.global.read)
- **설정 > 운영 값 > AI 자가 리뷰**: REDTEAM_* 설정 (무변경)
- 전역 프롬프트 비교·검토: 기본 시스템 프롬프트 fallback 은 편집 정본(전역 프롬프트)과 중복이라 작동 지침 목록에서 제외

## 3. Recent Changes
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
- 총 변경 횟수: 6+ (구현 · anchor 정합 · 콘솔 IA 재구성 · 리뷰어 토큰 설정 · 모델 정합 · revise prefill 수정)

## 4. Open Issues
- make test 중 pre-existing 환경 의존 실패 4건 (본 feature 무관 — TEST.md §3 Run 기록 참조):
  runtime_settings 2건은 `.env` 의 AGENT_TIMEOUT_SEC=300 이 기본값 60 단정과 충돌 (main 동일
  실패), routine_dbanalysis·item11_batch8 2건은 main 컨테이너가 라이브 PG 네트워크에 붙어
  통과하던 것이 격리 worktree 네트워크에서 정직하게 실패 (PG 부재). 후속 개선 후보: §8.

## 5. Test Status
- 자동 테스트: 신규 34건 PASS (redteam 18 · agent_notes 8 · admin_reasoning 8) + 기존 스위트
  회귀 0 (환경 의존 4건 제외 — 상세 TEST.md §3). 적대 패널(REV-0002) BLOCK2+MAJOR1+MINOR3 반영·재검증 완료.
- (2026-07-22 CHG-0001) 리뷰어 토큰 설정 추가 후 test_redteam 36건(신규 5) + runtime_settings +
  admin_reasoning 합산 87건 PASS·ruff clean (TEST.md §3 Run 2026-07-22). 프론트 무변경.
- (2026-07-24 CHG-20260724-0001) 모델 정합 후 test_redteam **45건 PASS**(신규 9 — resolve 매핑/폴백/pin 3·
  identity 주입 sonnet/haiku 2·effort 주입 sonnet/haiku 2·orchestrate 스레딩 2)·ruff clean(변경 5파일).
  전체 feature-0002+0003 회귀는 환경 의존 4건만 실패(내 변경 무관 — `.env` AGENT_TIMEOUT_SEC=300 2건은
  `-e AGENT_TIMEOUT_SEC=60` 강제 시 2 passed 로 확증, PG 부재 2건). §18.8 적대 패널(REV-20260724T071500):
  BLOCK 0, MAJOR1(effort=low)+MINOR2(doc·forward-caveat) 반영/수용. 상세 TEST.md §3(20260724T0709 fragment).
- 수동 테스트: 배포 후 PB-0008 Windows-browser 콘솔 검증 + 라이브 리뷰 실증 예정
  (설정 패널 "리뷰어 토큰 할당량" 노출 + 조정 반영 + admin 'AI 추론' 탭 model 컬럼 sonnet 표기 포함)
- 미검증 항목: 리뷰어 실판정 품질 (라이브 축적 관찰), effort=low 로 sonnet 리뷰 타임아웃 소멸(라이브 관찰)

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 없음 (deploy_scope: included — cycle-final 후 자동 배포 진행)

## 8. Suggested Improvements
- make test 의 컨테이너가 라이브 compose 네트워크에 합류해 "DB 필요 테스트가 우연히 통과"
  하는 문제 — `--network none` 격리 또는 env 고정(.env.test)으로 결정론화 후보.
- runtime_settings 기본값 단정 테스트 2건의 env 내성화 (monkeypatch.delenv).
- 리뷰 판정 rubric 의 LLM-as-judge 정확도 평가 (golden 셋) — feature-0002 eval harness 연계.
