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

## REV-20260827-0001
- Related Change: 사용자 결정 수집(AskUserQuestion 3라운드 11문항) 반영 — 설계 rev.2 전면 개정
  (CICD_DESIGN·FUNCTION·TASK 재작성 + DECISIONS ADR 2건 + 권장 스펙 신설)
- Reason: 사용자가 "결정사항 모두 AskUserQuestion 으로 진행" 을 지시해 미결정 전건을 문항으로
  수집했다. 그 과정에서 **rev.1 의 전제 2개가 사실과 다름이 드러났다** — ① 1라운드에서 "사내
  GitLab 미러 경유" 로 답했던 것이 2라운드 확인 결과 "사내 저장소는 아직 없고, 만든다면 SVN"
  이었고 컨테이너 레지스트리도 없다 ② 라이브 위치는 rev.1 에서 "별개 결정" 으로 남겼는데
  "QA 와 함께 분리" 로 확정됐다. 전자는 전달 수단 자체가 없다는 뜻이라 설계의 3·4단계를
  재작성해야 했고, 후자는 반대로 설계를 단순화했다(QA·라이브가 같은 절차를 공유).
- Alternatives Considered:
  - 전달 수단: tar 릴레이 vs 레지스트리 선구축 vs 각자 빌드. **tar 릴레이 채택** — 레지스트리
    구축을 QA 일정의 선행 조건에서 빼면서도 `sha256`+`image_id` 2중 대조로 신원 보증은 유지된다.
    각자 빌드는 폐쇄망 재현성 문제로 되돌아가므로 기각.
  - 승격 표현: git 태그 vs SVN 파일. SVN 이 산출물 저장소이므로 `promoted/current.json` 채택
    (git 은 개발 정본이라 배포 상태를 git 에 기록하면 두 축이 섞인다).
  - 미래 레지스트리 전환: 지금 추상화 vs 나중에 리팩터. **지금 `transport` 필드로 추상화** —
    획득 단계를 함수 하나로 격리하는 비용이 거의 0 인 반면, 나중에 러너 전체를 고치는 비용은 크다.
  - 라이브 이전 순서: 동시 vs QA 먼저. **QA 먼저** — 같은 절차를 라이브에 적용하기 전에
    한 번 실증하는 것이 사고 비용을 낮춘다.
- Risks:
  - **SVN 용량 단조 증가** — 새로 식별한 위험이다. SVN 은 삭제해도 이력 blob 이 남아 이미지
    tar 를 매 릴리즈 커밋하면 저장소가 계속 커지고 checkout 이 무거워진다. 사용자가 "릴리즈
    산출물 저장소" 로 SVN 을 지정했으므로 그 안에서 안 A(매니페스트만) / 안 B(전부)를
    선택지로 제시했다. **설계가 임의로 정할 사안이 아니다.**
  - **GPU 의존을 rev.1 이 놓쳤다** — 실측에서 임베딩(bge-m3)이 GPU 상주(`OLLAMA_KEEP_ALIVE: -1`)
    임을 확인했다. GPU 없는 QA 는 임베딩이 CPU 로 떨어져 타임아웃 cliff 위험이 있고, 그러면
    성능 관련 QA 결과를 신뢰할 수 없다. 스펙 권장의 **결정 변수**로 승격했다.
  - **이동 태그 2건 실재** — `ollama/ollama:latest` 와 `caddy:2` 를 compose 실측으로 확인했다.
    폐쇄망 이전에 이미 "QA 와 라이브가 서로 다른 이미지를 쓸 수 있는" 상태였다.
  - **빌드 머신 이관 시 등가성** — 개발 머신 → 빌드 서버 전환 시 같은 커밋이 같은 산출물을
    내는지 1회 검증하지 않으면, 이후 "어느 머신에서 빌드한 릴리즈인가" 가 디버깅 변수로 남는다.
    매니페스트 `built_by` 필드로 추적 가능하게 했다.
  - **라이브 이전은 무중단이 아니다** — 데이터 90GB 이전이 포함되므로 전환 창이 발생한다.
    리허설로 소요를 실측해 공지 시간을 정하고, 현행 호스트를 1주 보존해 되돌림 경로를 남긴다.
- Open Questions: 사내 PyPI/apt 미러 유무(미확인 1건) + 사용자 결정 2건(SVN 용량 정책 · GPU 선택).
- Human Approval Needed: **예.** Phase 1 이후 구현 착수, 하드웨어 2대 확보, GPU·SVN 정책 선택.

## REV-20260827-0002 [SKIPPED:non-policy-doc]
- Related Change: 본 cycle 도 rev.1 과 마찬가지로 unit 문서만 변경하며 제품 코드·정책 문서를
  건드리지 않는다(`docs/STATUS.md` 인덱스와 wiki 미러는 AGENTS.md §4·§21 이 요구하는 동반 갱신).
- Reason: 코드 변경 0 · 실행 표면 변경 0. 설계의 적대적 검토는 구현 착수 시점(Phase 1 PR)에
  하는 것이 실효적이다 — 지금은 미확인 전제 1건과 사용자 결정 2건이 열려 있어 검토 대상이
  확정되지 않는다.
- Human Approval Needed: 아니오 (SKIP 사유 기록으로 갈음)
