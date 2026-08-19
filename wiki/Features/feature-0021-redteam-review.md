---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0021-redteam-review
linked_unit: unit/feature-0021-redteam-review
created: 2026-07-15
sources:
  - ../../unit/feature-0021-redteam-review/docs/FUNCTION.md
---

# Feature — assistant 자가 적대(red-team) 리뷰

> 사람용 입구. 정본: [[../../unit/feature-0021-redteam-review/docs/FUNCTION|FUNCTION.md]].

## 목차

- [한 줄 요약](#한-줄-요약)
- [상태](#상태)
- [책임 경계](#책임-경계)
- [관련 정본](#관련-정본)
- [관련 노트](#관련-노트)
- [Open questions](#open-questions)

## 한 줄 요약

assistant 답변을 전달 전에 fresh-context 저비용 리뷰어가 5축(grounding/SQL/권한/완전성/정직성)
으로 적대 검증(find→revise→verify, 추론 강도 게이팅·fail-open)하고, [세션, 제품] 메모리 노트
(TTL 임시 파일)와 지침/스킬 레지스트리 콘솔 조회를 함께 제공 — Claude Code 추론 패턴 이식.
콘솔 표면은 07-16 IA 재구성으로 감사 > 'AI 운영 현황' 탭 [추론] 서브탭(리뷰 활동·노트 현황) +
설정 > 프롬프트 서브탭(작동 지침·스킬, `system_prompt.global.read` 재사용)으로 분리.
검증은 07-27 이후 **1회 상한이 아니라 결함 해소까지 반복**하며(사용자 '즉시 답변'/취소 탈출구 ·
무진전·붕괴 가드 · 잔존 시 기록/콘솔/답변 3중 고지), 회차 단계는 07-29 부터 원장
(`agent_runtime.redteam_review_rounds`)에 남아 콘솔에서 대화 단위로 접어 볼 수 있다.

## 상태

- 단계: in-progress (정본 `feature_status` 기준 — 구현·배포 완료, 라이브 실측 기반 교정 사이클 진행)
- 마지막 갱신: 2026-08-19 (unresolved-convergence — '재검증에서 해소되지 않은 지적' 잔존 전달의
  비수렴 경로 3종 봉인. 경유 사이클: 07-16 콘솔 IA 재구성(감사/설정 분리·서브탭 통합·sticky) ·
  07-22 리뷰어 토큰 할당량 콘솔 노출 · 07-24 리뷰어 모델을 답변 모델에 정합 + revise/rederive
  prefill 결함 교정 · 07-27 재검증 게이트 일반화·결함 해소까지 반복·리뷰어 라운드 기억 ·
  07-28 원 요청 정합 재앵커 · 07-29 다중 턴 요청 맥락 회귀 교정 + 회차 단계 원장·대화 단위
  콘솔 + 추론 탭 안내 축약 + UI 카피 예산 게이트 채택)

## 책임 경계

- 입력: 답변 초안 + 도구 실행 digest + 추론 강도 + REDTEAM_* 런타임 설정
- 출력: (수정되었을 수 있는) 최종 답변 · `agent_runtime.redteam_reviews` 판정 +
  `agent_runtime.redteam_review_rounds` 회차 단계 원장(alembic 0048, 07-29) ·
  `/shared/agent-notes/{session,product}` 노트 · `GET /api/admin/reasoning/*`
- side-effect: 답변당 리뷰 LLM 호출(haiku 급, task=redteam 계측) · 노트 파일 쓰기 ·
  ask-worker reaper 의 TTL 삭제

## 관련 정본

- [[../../unit/feature-0021-redteam-review/docs/FUNCTION|FUNCTION]]
- [[../../unit/feature-0021-redteam-review/docs/TASK|TASK]] (active)
- [[../../unit/feature-0021-redteam-review/docs/DECISIONS|DECISIONS]] (ADR-20260715T140000~2)
- [[../../unit/feature-0021-redteam-review/docs/REPORT|REPORT]]

## 관련 노트

- [[feature-0002-agent-core]] · [[feature-0003-agent-web-ui]] (코드 거주)
- [[../Architecture/Data-Flow]] — 답변 choke-point 위치
- [[../concepts/_Index]] — ask-worker · runtime settings

## Open questions

- 리뷰 판정 품질(검출률/오탐률) 라이브 관찰 후 rubric 튜닝 여부 — 08-19 에 라이브 30일 실측
  (잔존 전달 33건 · 미해소 축 grounding 47/71)으로 오탐 원천 1건을 봉인했고, 봉인 후 수렴 분포
  재측정은 트래픽 대기 (정본 TEST.md §4 미커버)
- 콘솔 회차 라벨 backfill — 08-19 신규 원장 note 2종(`revise_failed_retry`/`revise_aborted`)이
  한글 라벨 없이 raw 코드로 표시된다(fail-soft 폴백·기능 정상). 웹 자산 변경이라 다음 콘솔
  cycle 동반 (정본 REPORT.md §8)
- 이전 턴 도구 실행 근거의 리뷰어 비가시 — 08-19 프롬프트 규칙 + grounding 재도출로 완화,
  근본 해소(이전 run 근거의 bounded 동봉)는 비용·누출 경계 검토 후 후속 (정본 REPORT.md §8)
- 다중 호스트 스케일아웃 시 노트 저장소 DB 승급 (ANCHOR §2 Alt-C)
