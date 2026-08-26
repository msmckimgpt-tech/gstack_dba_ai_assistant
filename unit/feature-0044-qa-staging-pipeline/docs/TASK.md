---
doc_type: TASK
feature_id: feature-0044-qa-staging-pipeline
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: planned
feature_status_date: 2026-08-27
feature_status_note: QA·라이브 분리 CI/CD 설계 rev.3 확정 (전제 13축 중 12축 결정 — SVN 안 A(매니페스트만)+파일서버 tar · docker save 릴레이 · 빌드 서버 이관 경로 · **로컬 LLM 전면 폐지로 GPU 불요**, 단 임베딩 사내 MCP 이관이 QA 세팅 선행 조건). 구현 착수는 사용자 승인 대기
---

# Task

## 1. Current Status
- State: proposal rev.2 (설계 확정 — 구현 승인 대기)
- Owner: AI (설계) / Human (인프라 확보·승인)
- Priority: high
- Last Updated: 2026-08-27

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일(구현 시):**
  - `unit/feature-0002-agent-core/src/Dockerfile` · `unit/feature-0003-agent-web-ui/src/Dockerfile`
    (베이스 이미지·pip 소스 `ARG` 파라미터화)
  - `docker-compose.yml` (외부 이미지 이동 태그 제거 — `ollama/ollama:latest` · `caddy:2` 포함)
  - `requirements*.txt` (버전/해시 고정)
  - `bin/deploy-web.sh` (`--from-manifest` 모드 — 기존 로컬 빌드 경로 보존)
  - 신설: `bin/release-build.sh` · `bin/release-agent.sh` · `bin/release-promote.sh` ·
    `bin/qa-smoke.sh`
  - `docs/SECURITY.md` (QA·라이브 = 운영 등급 자산 정합) · `CONTRIBUTING.md` (릴리즈 태그 규약)
- **접근 방법:** 현행 무중단 배포 스파인은 유지하고 **이미지 획득 경로만** 교체한다. 스파인이
  이미 pin overlay 로 이미지를 고정하므로 build → tar load 전환은 침습적이지 않다. 폐쇄망
  빌드 재현성(Phase 1)을 먼저 확보한 뒤 매니페스트 → SVN → 러너 순으로 쌓고, QA 로 절차를
  실증한 뒤 라이브를 옮긴다.
- **위험도:** Major (배포 경로 변경 · 운영 등급 데이터 이동 · 시크릿 관리 방식 변경 ·
  라이브 호스트 이전)

<!-- 승인 대기: 본 cycle 은 설계 제안까지이며, 구현 착수는 사용자 승인 후 -->

## 3. Task Queue

### Phase 0 — 설계 (완료)
- [x] TASK-20260826T140000-qa-cicd-design 설계 제안 rev.1 (GitLab CI + Registry 전제)
- [x] TASK-20260827T090000-qa-cicd-decisions 전제 10축 확정 → rev.2 전면 개정
      (SVN 산출물 저장소 · tar 릴레이 · 빌드 서버 이관 경로 · 라이브 분리 · 권장 스펙 실측 산출)
- [x] TASK-20260827T100000-qa-cicd-rev3 전제 13축 확정 → rev.3
      (SVN 안 A 확정 · **로컬 LLM 실태 코드 실측** · GPU 불요로 스펙 하향 · §9 임베딩 이관 신설)

### Phase 1 — 폐쇄망 빌드 재현성 (선행 필수)
- [ ] TASK-P1-01 Dockerfile `FROM` 을 `${BASE_REGISTRY}` 파라미터화 + 베이스 이미지 tar 확보
- [ ] TASK-P1-02 pip 소스 `ARG` 2안 지원 (미러 index / wheel 번들) + `requirements*.txt` 버전·해시 고정
- [ ] TASK-P1-03 compose 외부 이미지 **이동 태그 제거** — `ollama/ollama:latest` ·
      `caddy:2` · `pgvector` · `mysql` · `minio` · `pgbouncer` · `litellm` · `dbhub` 패치 핀 + tar
- [ ] TASK-P1-04 커스텀 `kb-pg-age:pg16` 을 릴리즈 산출물로 승격 (재현 경로 문서화)
- [ ] TASK-P1-05 **네트워크 차단 상태 전체 빌드 검증** (AC-8 — Phase 1 의 유일한 합격 판정)

### Phase 2 — 릴리즈 빌드 + registry-free 배포 모드
- [ ] TASK-P2-01 `bin/release-build.sh` — test→build→save→sign→push 5단계, `GIT_COMMIT` 주입
- [ ] TASK-P2-02 매니페스트 스키마 확정 (sha256 + image_id + `transport` 추상화)
- [ ] TASK-P2-03 `bin/deploy-web.sh --from-manifest` — build 스킵 + tar load + image_id 대조 +
      last-good 을 릴리즈 단위로
- [ ] TASK-P2-04 preflight 확장 — env 키 대조 · alembic head · TLS · 디스크 (fail-closed)
- [ ] TASK-P2-05 **개발 머신 단독 리허설** (로컬 save→load→배포 전 경로, QA 머신 없이 검증)

### Phase 3 — SVN 산출물 저장소 + 배포 러너
- [ ] TASK-P3-01 SVN 저장소 개설 + 레이아웃 + 권한(빌드 쓰기 / 대상 read-only)
- [ ] TASK-P3-02 **용량 정책 결정** — 안 A(매니페스트만 SVN + tar 는 파일서버) vs 안 B(전부 SVN)
- [ ] TASK-P3-03 `bin/release-agent.sh --channel {qa|promoted}` + systemd timer
- [ ] TASK-P3-04 `bin/release-promote.sh` + `promoted/current.json` 계약

### Phase 4 — QA 머신 구축 (인프라 확보 병렬)
- [ ] TASK-P4-01 **하드웨어 확보** — CICD_DESIGN §6.2 권장 스펙
      (**8~12 vCPU / 32GB / 400GB NVMe / GPU 불요** — 로컬 LLM 폐지 반영)
- [ ] TASK-P4-02 **선행 확인: 임베딩 사내 MCP 이관 완료 여부** (CICD_DESIGN §9.4).
      미완이면 ① QA 에 GPU 투입 또는 ② CPU 기준 타임아웃 재조정 + "성능 QA 무효" 명시 중 택일
- [ ] TASK-P4-03 사내 CA 인증서 발급 + VPN DNS 레코드 등록
- [ ] TASK-P4-04 오프라인 기반 설치 + read-only 자격증명 배치 (SVN + 파일서버 2종)
- [ ] TASK-P4-05 SOPS+age 시크릿 파이프라인 — chat LLM 자격증명 제외(feature-0043 전제),
      **임베딩 전용 계정은 예외로 포함**(최소 권한·범위 명시, CICD_DESIGN §9.5)
- [ ] TASK-P4-06 라이브 백업 → QA 적재 + `bin/restore-rehearsal.sh` 검증 + 경유지 사본 삭제
- [ ] TASK-P4-07 사내 PyPI/apt 미러 유무 확인 → Phase 1 안 A/B 확정
- [ ] TASK-P4-08 사내 파일서버 경로 규약 + 보관 세대(권장 5) 정책 확정 (CICD_DESIGN §3.4)

### Phase 5 — 검증 게이트
- [ ] TASK-P5-01 `bin/qa-smoke.sh` 6종 — health · 엣지 · **OAuth discovery 2종** ·
      MCP 프로토콜 · 대화 경로 · 브리지 왕복
- [ ] TASK-P5-02 수동 QA 체크리스트 → `docs/TEST.md` 편입
- [ ] TASK-P5-03 사용자 머신 온보딩 문서 (MCP 등록 · 러너 설치 · 버전 호환)
- [ ] TASK-P5-04 `bridge_runner` 릴리즈 동봉 + `bridge_runner_min_version` 집행

### Phase 6 — 라이브 호스트 분리 (QA 실증 후)
- [ ] TASK-P6-01 라이브 머신 구축 (Phase 4 와 동일 절차)
- [ ] TASK-P6-02 **데이터 이전 리허설** — 90GB 규모 복원 소요 실측 → 전환 창 산정
- [ ] TASK-P6-03 전환 창 공지 + 실제 이전 + DNS 전환
- [ ] TASK-P6-04 현행 호스트 1주 보존 (즉시 되돌림 경로 유지)

### Phase 7 — 승격 운영 정착
- [ ] TASK-P7-01 라이브 러너 `--channel promoted` + QA 스모크 결과 확인 게이트
- [ ] TASK-P7-02 빌드 서버 이관 + **등가성 1회 검증** (AC-9)
- [ ] TASK-P7-03 릴리즈 보관 정책 운영 (tar 세대 관리 · SVN/파일서버 용량 감시)

## 4. In Progress
- 없음 (Phase 0 rev.2 완료, Phase 1 착수는 사용자 승인 후)

## 5. Blocked
- Phase 1~7 전체: BLOCKED: awaiting-human-approval — 본 cycle 은 설계 제안까지
- TASK-P4-01: BLOCKED: awaiting-human-approval — 하드웨어 확보 (QA·라이브 2대, GPU 불요)
- TASK-P4-02: BLOCKED: external-dependency — 임베딩 사내 MCP 이관은 **별도 작업**이며 그
  완료 여부가 QA 스펙·일정에 영향 (CICD_DESIGN §9.4)
- TASK-P4-07: BLOCKED: clarification-needed — 사내 PyPI/apt 미러 유무 (남은 유일한 미확인 전제)

> rev.2 에서 BLOCKED 였던 TASK-P3-02(SVN 용량 정책)는 **안 A 확정**으로 해소됐다.

## 6. Done
- TASK-20260826T140000-qa-cicd-design — 설계 제안 rev.1
- TASK-20260827T090000-qa-cicd-decisions — 전제 10축 확정 + rev.2 전면 개정 + 권장 스펙 실측 산출

## 7. Next Action
사용자가 설계 방향을 승인하면 Phase 1(폐쇄망 빌드 재현성)부터 착수한다. Phase 4-01·4-03
(하드웨어·사내 CA·DNS)은 리드타임이 있으므로 승인 즉시 병렬 요청을 넣는 것이 전체 일정에
유리하며, TASK-P4-07(미러 확인)은 Phase 1 의 구현 방식을 확정하므로 가장 먼저 답이 필요하다.

**순서 권고**: 임베딩 사내 MCP 이관(별도 작업)을 QA 세팅보다 **먼저** 끝내면 GPU 없이
산정·구매할 수 있고 타임아웃 재조정과 그 되돌림이 불필요하다(CICD_DESIGN §9.4).

## 8. Requested Scope (요청 범위 자기-열거)

원 요청: "라이브 배포 전 QA 머신을 세팅해 프로젝트를 올리려 한다. 제한적인 상황(독립 네트워크 +
VPN 전용 접근, MCP 연결/역연결 사용)에서 사내 CI/CD 전 과정을 어떻게 가는 것이 가장 모범적인지
제안해 달라." + 후속 지시: "결정사항 모두 AskUserQuestion 으로 진행해 달라."

- [x] `CI/CD 전체 과정 제안` — 산출물: [CICD_DESIGN.md](./CICD_DESIGN.md) §3 단계 0~7 ·
      배선 확인: 각 단계가 현행 자산(`deploy-web.sh` pin overlay · `ci.yml` 게이트 ·
      `backup.sh`/`restore-rehearsal.sh` · `smoke-conversation.sh`)에 붙는 지점 명시
- [x] `독립망 + VPN 제약 반영` — 산출물: §1.2(a)(b) 문제 규명 + §3 단계 1 폐쇄망 공급망 ·
      배선 확인: compose·Dockerfile 실참조 조사로 이동 태그 2건(`ollama:latest`·`caddy:2`) 적발
- [x] `git 개발 흐름과의 정합` — 산출물: §3 단계 0(정본 규칙)·단계 2(릴리즈 컷) ·
      배선 확인: GitHub 정본·CONTRIBUTING §5 커밋 규칙 불변, SVN 은 산출물만
- [x] `MCP 연결/역연결 동작 반영` — 산출물: §3 단계 6-A/6-B + §4 위험 D ·
      배선 확인: feature-0041 OAuth(브라우저 리다이렉트)와 feature-0043 브리지(아웃바운드)의
      네트워크 방향 차이를 검증 항목으로 분리
- [x] `모든 결정사항을 AskUserQuestion 으로 수집` — 산출물: §0.2 확정 전제 10축 표 ·
      배선 확인: 3라운드 11문항으로 수집, 답변이 전제를 뒤집은 2건(사내 저장소 부재 ·
      라이브 분리)은 설계를 rev.2 로 전면 개정
- [x] `권장 스펙 산출` — 산출물: §6 (현행 실측 + QA/라이브/빌드 머신 권장) ·
      배선 확인: `nproc`/`free`/`du`/compose `mem_limit` 실측 + GPU 상주 사실 확인
- [x] `미결정 표면화` — 산출물: §8 (미러 1건) + TASK §5 Blocked ·
      배선 확인: rev.2 의 결정 요청 2건(SVN 정책·GPU)이 rev.3 에서 해소됨을 §8 에 명시
- [x] `로컬 LLM 잔존 실태 직접 확인` (사용자 명시 요청) — 산출물: CICD_DESIGN §9.1~§9.3 ·
      배선 확인: compose `embed-ollama` 정의 · `litellm_config.yaml` `titan-embed` alias ·
      소비처 3경로(`kb_embedding_worker`·`kb_retrieval`·`sample_queries`) · 차원 고정 지점
      (`AGENT_KB_EMBEDDING_DIM=1024`, `texts.embedding vector(1024)`) 를 코드로 실측

**주장 affordance 실측 (G3)**: 해당 없음 — 본 cycle 산출물은 설계 문서이며 실행 가능한
기능·UI 를 주장하지 않는다. 설계가 주장하는 것(폐쇄망 빌드 가능성·tar 신원 등가성)의 실측은
TEST.md §2 케이스로 각 구현 Phase 에 배정했다.

**경계변수 양측 검증 (G4)**: 해당 없음 — 본 cycle 은 임계·윈도잉 변수를 도입하지 않는다.
구현 시 도입될 값(폴링 주기·soak 시간·preflight 타임아웃·**임베딩 타임아웃**)은 해당 Phase
에서 검증한다. 특히 GPU 미탑재 시 임베딩 타임아웃은 경계 양측 실측이 필수다(CICD_DESIGN §6.3).

## 9. Completion Checklist
- [x] 요청된 설계 제안(전 과정)이 문서화되었다
- [x] 확정 전제 10축이 설계에 반영되었다 (9축 결정 + 1축 미확인 명시)
- [x] 전제를 뒤집은 답변(사내 저장소 부재 · 라이브 분리)이 설계에 소급 반영되었다
- [x] 채택하지 않은 대안과 그 이유가 ANCHOR §2 / CICD_DESIGN §2.2 에 기록되었다
- [x] 권장 스펙이 실측 근거와 함께 산출되었다
- [x] 미결정 사항이 숨겨지지 않고 명시되었다 (CICD_DESIGN §8)
- [ ] (구현 cycle) 단위/통합 테스트 — 본 cycle 범위 아님
- [x] MODIFY.md 에 변경 이력이 기록되었다
- [x] REVIEW.md 에 판단 근거가 기록되었다
- [x] REPORT.md 에 최종 상태가 반영되었다
