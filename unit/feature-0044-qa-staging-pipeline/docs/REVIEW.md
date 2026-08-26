---
doc_type: REVIEW
feature_id: feature-0044-qa-staging-pipeline
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260826-0001
- Related Change: unit 개설 + QA 스테이징 CI/CD 설계 제안서 (FUNCTION.md · CICD_DESIGN.md · ANCHOR §1~§3)
- Reason: 라이브 배포 전 격리망 QA 머신 도입 결정에 따라, 현행 배포 스파인을 그대로 옮길 수
  없는 지점을 규명하고 대체 파이프라인을 설계했다. 현행 `bin/deploy-web.sh` 는 배포 대상
  호스트에서 `git checkout` + `docker build` 를 수행하는데, QA 머신은 인터넷 차단 격리망이라
  이 전제가 성립하지 않는다. 빌드를 사내 GitLab CI 로 옮기고 QA·라이브는 다이제스트를 pull 하는
  build-once 구조를 채택했다.
- Alternatives Considered: ANCHOR §2 에 4안 기록 (Alt-A 소스만 미러 후 QA 빌드 / Alt-B 개발 머신
  push 기반 CD / Alt-C Kubernetes+ArgoCD 전면 GitOps / Alt-D QA 없이 라이브 겸용).
  Alt-A 는 폐쇄망 빌드 재현성 부재, Alt-B 는 배포 자격증명·인바운드가 개발망에 상주하는 문제,
  Alt-C 는 단일 호스트 규모 대비 과도(단 pull + 선언적 매니페스트라는 핵심 아이디어는 채택),
  Alt-D 는 사용자 결정에 반함.
- Risks:
  - **폐쇄망 빌드 재현성이 아직 미검증** — 설계상 타당하나 실증은 Phase 1 의 네트워크 차단
    빌드(TASK-P1-05)에서 처음 이루어진다. 사내 미러에 없는 베이스 이미지가 발견되면 그 시점에
    범위가 늘어난다.
  - **QA 머신 = 운영 등급 자산** — 마스킹 없는 라이브 복제본 결정의 직접 귀결. 설계로 제거되지
    않으며 접근통제·감사·폐기 절차로만 관리된다. CICD_DESIGN §4 위험 A 에 명시했다.
  - **MCP 도달성이 인프라 의존** — VPN DNS 와 사내 CA 는 본 feature 가 통제할 수 없는 외부
    조건이다. 둘 중 하나만 어긋나도 배포는 성공인데 사용자는 진입 불가다.
  - **이중 원격의 정본 혼선** — GitHub/GitLab 두 원격이 생긴다. QA deploy key read-only 로
    구조적 차단을 두었으나, 운영 규율(GitLab 직접 커밋 금지)에도 의존한다.
- Open Questions: CICD_DESIGN §6 의 미결정 7건 (GitLab 아웃바운드 · 사내 registry · PyPI/apt
  미러 · VPN DNS · 사내 CA · 데이터 반출 승인 · QA 머신 스펙 · 라이브 최종 위치).
- Human Approval Needed: **예.** 본 cycle 은 설계 제안까지이며, Phase 1 이후 구현 착수는 사용자
  승인 후 진행한다. 인프라 협의(VPN DNS·사내 CA·QA 스펙)와 데이터 반출 승인은 사람만 할 수 있다.

## REV-20260826-0002 [SKIPPED:non-policy-doc]
- Related Change: 본 cycle 은 신규 unit 문서 생성만 수행하며 제품 코드·정책 문서(`docs/`·`AGENTS.md`)를
  변경하지 않는다. `docs/STATUS.md` 인덱스 등록은 AGENTS.md §4 가 요구하는 필수 절차다.
- Reason: 코드 변경 0 · 실행 표면 변경 0 이므로 §18.8 verification panel 대상이 아니다.
  설계 자체의 적대적 검토는 구현 착수 시점(Phase 1 PR)에 수행하는 것이 실효적이다 —
  지금 검토해도 미결정 7건이 열려 있어 전제가 확정되지 않는다.
- Human Approval Needed: 아니오 (SKIP 사유 기록으로 갈음)
