---
doc_type: TASK
feature_id: feature-0044-qa-staging-pipeline
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: planned
feature_status_date: 2026-08-26
feature_status_note: 격리망 QA 머신 CI/CD 설계 제안 완료 (build-once + pull 기반 승격 + MCP 도달성 완료판정) — 구현 착수는 사용자 승인 대기
---

# Task

## 1. Current Status
- State: proposal (설계 제안 — 사용자 검토 대기)
- Owner: AI (설계) / Human (인프라 협의·승인)
- Priority: high
- Last Updated: 2026-08-26

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일(구현 시):**
  - `unit/feature-0002-agent-core/src/Dockerfile` · `unit/feature-0003-agent-web-ui/src/Dockerfile`
    (베이스 이미지·pip 인덱스 파라미터화)
  - `docker-compose.yml` (외부 이미지 사내 미러 변수화 + 패치 버전 핀)
  - `requirements*.txt` (버전/해시 고정)
  - `bin/deploy-web.sh` (`--from-manifest` registry 모드 추가 — 기존 로컬 빌드 경로 보존)
  - `.gitlab-ci.yml` (신설), `bin/release-manifest.sh` (신설), `bin/qa-deploy-runner.sh` (신설)
  - `bin/qa-smoke.sh` (신설 — OAuth discovery + MCP 왕복 포함)
  - `docs/SECURITY.md` (QA 머신 = 운영 등급 자산 정합), `CONTRIBUTING.md` (GitLab 미러 규칙)
- **접근 방법:** 현행 무중단 배포 스파인은 유지하고 **이미지 획득 경로만** 교체한다.
  스파인이 이미 pin overlay 로 이미지를 고정하므로 build → pull 전환은 침습적이지 않다.
  폐쇄망 빌드 재현성(단계 1)을 먼저 확보한 뒤 매니페스트 → CI → QA 러너 순으로 쌓는다.
- **위험도:** Major (배포 경로 변경 · 운영 등급 데이터 이동 · 시크릿 관리 방식 변경)

<!-- 승인 대기: 본 cycle 은 설계 제안까지이며, 구현 착수는 사용자 승인 후 -->

## 3. Task Queue

### Phase 0 — 설계 (본 cycle)
- [x] TASK-20260826T140000-qa-cicd-design 전 과정 설계 제안서 작성 (FUNCTION.md + CICD_DESIGN.md)

### Phase 1 — 폐쇄망 빌드 재현성 (선행 필수)
- [ ] TASK-P1-01 Dockerfile `FROM` 을 `${BASE_REGISTRY}` 파라미터화
- [ ] TASK-P1-02 `PIP_INDEX_URL` 사내 미러 파라미터화 + `requirements*.txt` 버전/해시 고정
- [ ] TASK-P1-03 compose 외부 이미지(caddy·pgvector/AGE·mysql·minio·pgbouncer·ollama·litellm·dbhub)
      사내 미러 변수화 + **패치 버전까지 핀** (`caddy:2` 같은 이동 태그 제거)
- [ ] TASK-P1-04 사내 registry 미러 등록 목록 정본 문서화
- [ ] TASK-P1-05 **네트워크 차단 상태 전체 빌드 검증** (이 게이트를 통과해야 QA 에서도 된다)

### Phase 2 — 릴리즈 매니페스트 + registry 배포 모드
- [ ] TASK-P2-01 `bin/release-manifest.sh` — 다이제스트·alembic head·env 키 목록·API/러너 버전 발행
- [ ] TASK-P2-02 `bin/deploy-web.sh --from-manifest` — build 스킵 + digest pin overlay + last-good 다이제스트
- [ ] TASK-P2-03 preflight 확장 — 매니페스트 env 키 목록 vs 실제 `.env*` 대조 (누락 시 fail-closed)
- [ ] TASK-P2-04 로컬 registry 로 리허설 (QA 머신 없이 개발 머신에서 전 경로 검증)

### Phase 3 — 사내 GitLab CI
- [ ] TASK-P3-01 GitLab 미러 설정 + `main`/태그 보호 + read-only deploy key 발급
- [ ] TASK-P3-02 `.gitlab-ci.yml` test 스테이지 — `ci.yml` 게이트 이식
- [ ] TASK-P3-03 build/publish 스테이지 — `GIT_COMMIT` build-arg 주입 필수
- [ ] TASK-P3-04 scan 스테이지 (초기 비차단 → baseline 후 Critical 차단 승격)
- [ ] TASK-P3-05 manifest 스테이지 + 태그 채널(`qa/*`) 발행

### Phase 4 — QA 머신 부트스트랩 (인프라 협의 병렬 진행)
- [ ] TASK-P4-01 **인프라 요청**: VPN DNS `WEB_PUBLIC_HOST` 해석 · 사내 CA 인증서 · QA 머신 스펙
- [ ] TASK-P4-02 **데이터 반출 승인** 요청 (마스킹 없는 라이브 복제본 이동 경로·주체)
- [ ] TASK-P4-03 오프라인 기반 설치 (docker/compose) + read-only 자격증명 배치
- [ ] TASK-P4-04 SOPS+age 시크릿 파이프라인 구축 (LLM 자격증명 제외 — feature-0043 전제)
- [ ] TASK-P4-05 라이브 백업 → QA 적재 + `bin/restore-rehearsal.sh` 로 검증
- [ ] TASK-P4-06 TLS 인증서 설치 + SAN 검증

### Phase 5 — pull 러너 + 자동 스모크
- [ ] TASK-P5-01 `bin/qa-deploy-runner.sh` + systemd timer (폴링 → pull → preflight → deploy)
- [ ] TASK-P5-02 `bin/qa-smoke.sh` — health · 엣지 · **OAuth discovery 2종** · MCP 프로토콜 ·
      대화 경로 · 브리지 왕복
- [ ] TASK-P5-03 결과를 GitLab 에 되보고 (commit status / 릴리즈 코멘트)

### Phase 6 — 수동 QA 절차 + 온보딩
- [ ] TASK-P6-01 사용자 머신 온보딩 문서 (CA 설치 · VPN · MCP 등록 · 러너 설치)
- [ ] TASK-P6-02 `bridge_runner` 배포·버전 호환 강제 (무음 실패 금지)
- [ ] TASK-P6-03 수동 QA 체크리스트 → `docs/TEST.md` 편입

### Phase 7 — 라이브 승격 경로 전환
- [ ] TASK-P7-01 `promote/*` 채널 러너 + QA 스모크 결과 확인 게이트 (QA 우회 차단)
- [ ] TASK-P7-02 라이브 배포를 registry 모드로 전환 (로컬 빌드 경로는 fallback 보존)

## 4. In Progress
- 없음 (Phase 0 완료, Phase 1 착수는 사용자 승인 후)

## 5. Blocked
- TASK-P4-01: BLOCKED: awaiting-human-approval — VPN DNS·사내 CA·QA 머신 스펙은 인프라 담당 협의 필요
- TASK-P4-02: BLOCKED: awaiting-human-approval — 마스킹 없는 라이브 데이터 반출은 승인 행위일 수 있음
- Phase 1~7 전체: BLOCKED: awaiting-human-approval — 본 cycle 은 설계 제안까지

## 6. Done
- TASK-20260826T140000-qa-cicd-design — 설계 제안서 작성 (FUNCTION.md 범위·계약, CICD_DESIGN.md 전 과정)

## 7. Next Action
사용자가 설계 방향을 승인하면 Phase 1(폐쇄망 빌드 재현성)부터 착수한다. Phase 4-01·4-02 의
인프라 협의는 리드타임이 있으므로 승인 즉시 병렬로 요청을 넣는 것이 전체 일정에 유리하다.

## 8. Requested Scope (요청 범위 자기-열거)

원 요청: "라이브 배포 전 QA 머신을 세팅해 프로젝트를 올리려 한다. 제한적인 상황에서 사내
CI/CD 과정을 어떻게 가는 것이 가장 모범적인지 전체 과정을 제안해 달라. QA 머신은 독립 네트워크 +
VPN 경유로만 접근 가능하고, 사용자는 MCP 연결/역연결로 서비스를 사용할 예정이다."

- [x] `CI/CD 전체 과정 제안` — 산출물: [CICD_DESIGN.md](./CICD_DESIGN.md) §3 단계 0~7 ·
      배선 확인: 각 단계가 현행 자산(`bin/deploy-web.sh` pin overlay · `ci.yml` 게이트 ·
      `bin/backup.sh`/`restore-rehearsal.sh` · `/trust/` CA 배포)에 어떻게 붙는지 명시
- [x] `독립망 + VPN 제약 반영` — 산출물: CICD_DESIGN §1.2(a) 문제 규명 + §3 단계 1 폐쇄망
      이미지 공급망 · 배선 확인: compose·Dockerfile 실참조를 조사해 미러화 대상 8종을 표로 열거
- [x] `git 기반 개발 흐름과의 정합` — 산출물: CICD_DESIGN §3 단계 0(정본 규칙)·단계 2(릴리즈 컷) ·
      배선 확인: 현행 origin(GitHub)·CONTRIBUTING §5 커밋 규칙 불변임을 명시, 태그 축은 직교
- [x] `MCP 연결/역연결 동작 반영` — 산출물: CICD_DESIGN §3 단계 6-A/6-B + §4 위험 C ·
      배선 확인: feature-0041 OAuth(브라우저 리다이렉트 필요) 와 feature-0043 pull 브리지
      (아웃바운드만 필요) 의 네트워크 방향 차이를 문서에서 확인해 검증 항목으로 분리
- [x] `모범 사례 판단 근거` — 산출물: ANCHOR §2 대안 4안 + CICD_DESIGN §2.2 미채택 사유표 ·
      배선 확인: 각 대안이 이 프로젝트의 어떤 실제 조건에서 실패하는지로 기술(일반론 회피)
- [x] `미결정 사항 표면화` — 산출물: CICD_DESIGN §6 (7건) + TASK §5 Blocked ·
      배선 확인: 인프라 협의 리드타임을 고려해 병렬 착수 권고를 §5 구현 순서에 명시

**주장 affordance 실측 (G3)**: 해당 없음 — 본 cycle 산출물은 설계 문서이며 실행 가능한
기능·UI 를 주장하지 않는다. 설계가 주장하는 것(폐쇄망 빌드 가능성 등)의 실측은
TEST.md §2 의 케이스로 각 구현 Phase 에 배정했다.

**경계변수 양측 검증 (G4)**: 해당 없음 — 본 cycle 은 임계·윈도잉 변수를 도입하지 않는다.
구현 시 도입될 값(폴링 주기·soak 시간·preflight 타임아웃)은 해당 Phase 에서 검증한다.

## 9. Completion Checklist
- [x] 요청된 설계 제안(전 과정)이 문서화되었다
- [x] 확정 전제 4축(QA망 개방도·전달 경로·데이터 등급·접근 경로)이 설계에 반영되었다
- [x] 채택하지 않은 대안과 그 이유가 ANCHOR §2 에 기록되었다
- [x] 미결정 사항이 숨겨지지 않고 명시되었다 (CICD_DESIGN §6)
- [ ] (구현 cycle) 단위/통합 테스트 — 본 cycle 범위 아님
- [ ] (구현 cycle) MODIFY.md 변경 이력 — 본 cycle 은 신규 문서 생성
- [x] REVIEW.md 에 판단 근거가 기록되었다
- [x] REPORT.md 에 최종 상태가 반영되었다
