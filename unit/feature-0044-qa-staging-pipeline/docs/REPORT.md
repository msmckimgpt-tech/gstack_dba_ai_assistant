---
doc_type: REPORT
feature_id: feature-0044-qa-staging-pipeline
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary

라이브 배포 전 격리망 QA 머신을 세우기 위한 **CI/CD 전 과정 설계 제안**을 작성한 상태다.
구현은 아직 착수하지 않았다(사용자 승인 대기).

핵심 제안: 빌드를 사내 GitLab CI 한 곳으로 모으고(build once), QA·라이브는 같은 이미지
다이제스트를 pull 하며(deploy many), 승격은 재빌드가 아니라 태그 이동으로 처리한다.
배포 완료 판정에 MCP 도달성(OAuth discovery + 도구 왕복)을 포함한다.

## 2. Progress
- Planned: Phase 1~7 (폐쇄망 빌드 재현성 → 매니페스트 → GitLab CI → QA 부트스트랩 →
  pull 러너·스모크 → 수동 QA·온보딩 → 라이브 승격 전환)
- In Progress: 없음
- Done: Phase 0 설계 제안 (FUNCTION.md 범위·계약, CICD_DESIGN.md 전 과정, ANCHOR §1~§3)

## 3. Recent Changes
- unit 신규 개설 + 설계 제안 문서 2건 작성 (FUNCTION.md, CICD_DESIGN.md)
- 총 변경 횟수: 1

## 4. Open Issues

CICD_DESIGN §6 의 미결정 7건이 그대로 열려 있다. 특히 **일정에 영향을 주는 것**:

- 사내 GitLab 의 인터넷 아웃바운드 가능 여부 (미러 자동/수동을 가름)
- 사내 컨테이너 레지스트리 존재 여부 (없으면 registry 구축이 선행)
- 사내 PyPI/apt 미러 존재 여부 (없으면 오프라인 wheel 번들로 대체 — 유지보수 비용 증가)
- VPN DNS 의 `WEB_PUBLIC_HOST` 해석 + 사내 CA 발급 (MCP 접근의 전제 조건)

## 5. Test Status
- 자동 테스트: 해당 없음 (본 cycle 은 문서 산출물)
- 수동 테스트: 해당 없음
- 미검증 항목: 설계의 실현 가능성은 Phase 1 의 "네트워크 차단 상태 전체 빌드 검증"
  (TASK-P1-05) 에서 처음 실증된다. 그 전까지 폐쇄망 대응은 **설계상 타당하나 미검증**이다.

## 6. Blocked Items
- Phase 1~7 전체: 사용자 승인 대기 (본 cycle 은 설계 제안까지)
- TASK-P4-01 / TASK-P4-02: 인프라 협의 및 데이터 반출 승인 필요

## 7. Human Attention Needed

1. **설계 방향 승인** — build-once + pull-based CD + 태그 승격 구조로 진행할지.
2. **인프라 요청 착수** — VPN DNS·사내 CA·QA 머신 스펙은 리드타임이 있어, 승인 즉시
   병렬 요청을 넣는 것이 전체 일정에 유리하다.
3. **데이터 반출 승인 주체 확인** — 마스킹 없는 라이브 복제본 이동은 승인이 필요한 행위일 수 있다.

## 8. Suggested Improvements

- **PII 컬럼 한정 마스킹 후처리** — 전면 마스킹은 이번 결정에서 제외됐지만, 복원 후 PII
  컬럼만 치환하는 스크립트는 비용 대비 효과가 크다. QA 머신의 운영 등급 부담을 실질적으로
  낮춘다. (실행하지 않음 — 기록만)
- **라이브 호스트 분리** — 현재 개발 머신과 라이브가 동일 호스트다. QA 도입으로 pull 기반
  배포 경로가 준비되면 라이브를 별도 호스트로 옮기는 비용이 크게 줄어든다. (별개 결정)
