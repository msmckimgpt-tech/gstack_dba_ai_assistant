---
doc_type: REVIEW
feature_id: feature-xxxx-template
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260713-0001 [SKIPPED: Phase 1 백엔드 scaffold — dormant·라이브 무영향, 적대 패널은 엔드포인트 라이브 시점 이연]
- Related Change: CHG-20260713-0001 (마이그 0041·recall 로더 active-path·쓰기 체이닝, 백엔드 기반).
- Reason: 본 checkpoint 는 순수 additive scaffold — `has_branches` DEFAULT false 이고 이를 true 로
  만드는 경로(편집 엔드포인트)가 아직 없어 **신규 브랜치 로직은 전부 dormant**(라이브 동작 무변경).
  비분기 대화는 로더·INSERT 모두 byte-identical(INV-1/AC-ME-2, 단위 11 PASS + 회귀 0). 활성 보안
  표면(edit IDOR·@assistant 잠금·공유 window 합성)은 엔드포인트가 배선되는 **Phase 1 완료 시점**에
  비로소 라이브화된다.
- Deferred to Phase 1 완료: §18.8 적대적 보안 패널(security subagent) — edit authz IDOR / 그룹
  @assistant 편집 잠금 / windowed 멤버 recall active-path 합성(가려진 구간 fail-closed) / 브랜치
  전환 권한. ANCHOR §4 외부 검증 로그에 결과 append 예정.
- Risks (현 checkpoint): 코어 로더 blast radius(모든 ask 문맥 진입점) → has_branches 게이트
  fast-path + 단위 회귀 테스트로 가드(비분기 항등성 단언). 잔여 위험 낮음(dormant).
- Human Approval: 설계·착수 승인 완료(2026-07-13, /_template:entry PLAN-APPROVED). 배포는 Phase 1
  완료·PB-0008 이후 별도.

## REV-20260713-0002 [SKIPPED: 표시 store 쓰기 정합 — dormant scaffold, 정상 append byte-identical]
- Related Change: CHG-20260713-0002 (display 브랜치 쓰기 대칭·core_message_id 링크·display 헬퍼).
- Reason: checkpoint 1 과 동일 — dormant(has_branches DEFAULT false). 정상 append 는 core_message_id
  미스레딩으로 byte-identical(hot-path call-site 무변경). 단위 15 PASS + 회귀 0(55). 활성 보안 표면은
  엔드포인트 라이브(Phase 1 완료) 시점에 발생 → §18.8 적대 패널 그때 수행(REV-0001 과 통합).
- Risks: display 쓰기 choke-point(memory.save_memory_message) 변경 → 미분기 항등 단위테스트로 가드.
- Human Approval: PLAN-APPROVED 유효(2026-07-13). 배포 별도.
