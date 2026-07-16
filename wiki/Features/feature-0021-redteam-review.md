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

## 상태

- 단계: 구현 완료 (cycle-final·배포 진행)
- 마지막 갱신: 2026-07-16 (콘솔 IA 재구성 — 감사/설정 분리·유사 탭 서브탭 통합·서브탭 바 sticky)

## 책임 경계

- 입력: 답변 초안 + 도구 실행 digest + 추론 강도 + REDTEAM_* 런타임 설정
- 출력: (수정되었을 수 있는) 최종 답변 · `agent_runtime.redteam_reviews` 판정 ·
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

- 리뷰 판정 품질(검출률/오탐률) 라이브 관찰 후 rubric 튜닝 여부
- 다중 호스트 스케일아웃 시 노트 저장소 DB 승급 (ANCHOR §2 Alt-C)
