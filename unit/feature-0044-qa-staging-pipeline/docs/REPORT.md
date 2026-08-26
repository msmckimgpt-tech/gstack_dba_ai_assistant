---
doc_type: REPORT
feature_id: feature-0044-qa-staging-pipeline
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary

라이브 배포 전 격리망 QA 머신 도입 + 라이브 호스트 분리를 위한 **CI/CD 전 과정 설계**가
rev.2 로 확정된 상태다. 구현은 아직 착수하지 않았다(사용자 승인 대기).

rev.1 → rev.2 에서 **두 전제가 뒤집혔다**: ① 사내 GitLab·컨테이너 레지스트리가 존재하지
않으며(SVN 을 산출물 저장소로 구축 예정) ② 라이브도 QA 와 함께 전용 호스트로 분리한다.
전자는 전달 수단을 `docker save` tar 릴레이로 재설계하게 했고, 후자는 오히려 설계를
단순하게 만들었다 — QA·라이브가 같은 러너·같은 스크립트를 쓰고 채널만 달라진다.

## 2. Progress
- Planned: Phase 1~7 (폐쇄망 빌드 재현성 → 릴리즈 빌드·매니페스트 → SVN·러너 →
  QA 구축 → 검증 게이트 → 라이브 분리 → 승격 운영)
- In Progress: 없음
- Done: Phase 0 — 설계 rev.1 작성 + 전제 10축 수집 + rev.2 전면 개정 + 권장 스펙 실측 산출

## 3. Recent Changes
- rev.1: unit 개설 + 설계 제안 2문서 (CHG-20260826-0001)
- rev.2: 전제 확정 반영 전면 개정 + ADR 2건 + 권장 스펙 신설 (CHG-20260827-0001)
- 총 변경 횟수: 2

## 4. Open Issues

**미확인 전제 1건** (설계 선택지가 갈림):
- 사내 PyPI/apt 미러 유무 — 있으면 index 치환(안 A), 없으면 오프라인 wheel 번들(안 B).
  Dockerfile 을 `ARG` 로 양쪽 지원하게 두면 확인 전에도 Phase 1 착수가 가능하다.

**사용자 결정 필요 2건** (설계 판단이 아니라 비용·인프라 선택):
- **SVN 용량 정책** — SVN 은 삭제해도 이력 blob 이 남는다. 안 A(매니페스트만 SVN + tar 는
  파일서버, 권장) / 안 B(tar 까지 SVN — 릴리즈 주기 × tar 크기 × 보관 기간만큼 저장소 증가).
- **GPU 선택** — 현행 임베딩(bge-m3)이 GPU 상주다. A(QA·라이브 모두 탑재, 권장) /
  B(라이브만 — QA 의 성능·타임아웃 검증이 무효가 됨) / C(둘 다 CPU — 타임아웃 전면 재조정).

## 5. Test Status
- 자동 테스트: 해당 없음 (본 cycle 은 문서 산출물)
- 수동 테스트: 해당 없음
- 미검증 항목: 설계의 실현 가능성은 Phase 1 의 "네트워크 차단 상태 전체 빌드"
  (TASK-P1-05 / AC-8)에서 처음 실증된다. 그 전까지 폐쇄망 대응은 **설계상 타당하나 미검증**이다.
  tar 릴레이의 신원 등가성(AC-2)은 Phase 2 의 개발 머신 단독 리허설에서 검증 가능하다.

## 6. Blocked Items
- Phase 1~7 전체: 사용자 승인 대기 (본 cycle 은 설계 제안까지)
- TASK-P3-02(SVN 용량 정책) · TASK-P4-02(GPU) · TASK-P4-07(미러 확인): 위 §4 참조

## 7. Human Attention Needed

1. **설계 방향 승인** — registry-free tar 릴레이 + pull 기반 CD + 라이브 분리로 진행할지.
2. **하드웨어 확보 착수** — QA·라이브 2대. 권장 스펙은 CICD_DESIGN §6.2 (16 vCPU / 48GB /
   500GB NVMe / GPU 6~8GB). 리드타임이 있어 승인 즉시 요청을 넣는 편이 유리하다.
3. **GPU 선택** (§4) — 비용 대비 QA 신뢰도의 트레이드오프. 권장은 둘 다 탑재.
4. **SVN 용량 정책 선택** (§4).
5. **사내 PyPI/apt 미러 확인** — Phase 1 의 구현 방식을 확정하므로 가장 먼저 답이 필요하다.

## 8. Suggested Improvements

- **PII 컬럼 한정 마스킹 후처리** — 전면 마스킹은 이번 결정에서 제외됐지만, 복원 후 PII
  컬럼만 치환하는 스크립트는 비용 대비 효과가 크다. QA 머신의 운영 등급 부담을 실질적으로
  낮춘다. (실행하지 않음 — 기록만)
- **컨테이너 레지스트리 도입** — 지금은 tar 릴레이로 시작하되, 매니페스트 `transport`
  추상화 덕에 나중에 러너 무변경으로 전환 가능하다. 릴리즈 빈도가 올라가면 재검토 가치가 있다.
- **이동 태그 감시** — `ollama/ollama:latest` 같은 참조가 재출현하지 않도록, compose 의
  이미지 태그를 정적 검사하는 가드를 CI 에 두는 것이 재발 방지에 효과적이다.
