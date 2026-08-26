---
doc_type: FUNCTION
feature_id: feature-0044-qa-staging-pipeline
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

라이브 배포 전 단계로 **격리망 QA 머신**을 세우고, 개발망(GitHub) → 사내 GitLab →
QA 머신 → 라이브로 이어지는 **단방향 승격형 CI/CD 파이프라인**을 구성한다.

핵심 전환은 두 가지다.

1. **빌드 위치의 이동** — 현행 `bin/deploy-web.sh` 는 배포 대상 호스트에서 `git checkout
   origin/main` + `docker build` 를 수행한다. QA 머신은 사내 저장소만 도달 가능하므로
   대상 호스트 빌드가 성립하지 않는다. 빌드는 사내 GitLab CI 한 곳에서 수행하고, QA·라이브는
   **같은 이미지 다이제스트를 pull 하기만 한다**(build once, deploy many).
2. **배포 방향의 역전** — 개발망이 QA 로 밀어넣는(push) 대신 QA 머신이 사내 GitLab 을
   폴링해 당겨온다(pull). VPN 인바운드 구멍이 필요 없고, 승격은 재빌드가 아니라
   **태그 이동**이 된다.

사용자의 서비스 접근 경로가 MCP 연결/역연결(feature-0041 도구 표면 + feature-0043 pull
브리지)이므로, 본 파이프라인의 **완료 기준은 컨테이너 health 가 아니라 VPN 밖 사용자
머신에서의 MCP 왕복 성공**이다(AGENTS.md §16.3 bring-up/access 완료 기준).

상세 절차·명령·다이어그램의 정본은 [CICD_DESIGN.md](./CICD_DESIGN.md) 이며, 본 문서는
범위·계약·비범위를 정의한다.

## 2. Goal

- REQ-20260826-qa-staging-pipeline: 격리망 QA 머신을 라이브 승격 전 필수 관문으로 세우고,
  dev→QA→live 를 관통하는 단일 이미지 신원(다이제스트) 기반의 재현 가능한 배포 경로를
  구성한다. QA 머신은 아웃바운드로 사내 저장소만 사용하며, 배포·검증·되돌리기가 사람의
  수동 조작 없이 재현된다.

### 2.1 확정 전제 (사용자 결정, 2026-08-26)

| 축 | 결정 | 파생 제약 |
|---|---|---|
| QA망 개방도 | **사내 저장소만 허용** (인터넷 차단) | 베이스 이미지·pip·apt 를 전부 사내 미러로 고정해야 함. QA 에서 `docker build` 금지 |
| 전달 경로 | **사내 GitLab 미러 경유** | GitLab = 배포 정본, GitHub = 개발 정본. 이원 원격의 정본 규칙이 필수 |
| QA 데이터 | **라이브 복제본 그대로**(마스킹 없음) | QA 머신을 **운영 등급 자산**으로 취급 — 접근통제·감사·백업·폐기 절차가 라이브와 동일해야 함 |
| 사용자 접근 | MCP 연결/역연결 | 배포 완료 판정에 OAuth discovery + 도구 왕복 probe 포함 |

## 3. In Scope

### P0-A. 이미지 공급망 (사내 폐쇄망 대응)
- 모든 `Dockerfile` 의 `FROM` 을 `${BASE_REGISTRY}` 파라미터로 치환하고, 사내 registry 미러
  경로를 기본값으로 둔다. 현행처럼 docker hub 를 직접 참조하면 QA 가 이미지를 당길 수 없다.
- pip 설치를 사내 PyPI 미러(`PIP_INDEX_URL`)로 고정하고, `requirements*.txt` 를 **해시 고정**
  (`--require-hashes` 또는 lock)한다. 미러는 시점에 따라 다른 버전을 줄 수 있어, 고정 없이는
  "dev 에서는 되는데 QA 에서 안 됨" 이 재현 불가능한 형태로 발생한다.
- 외부 이미지(caddy·pgvector·litellm·minio·ollama·dbhub)의 사내 registry 미러 등록 목록과
  버전 핀 정본을 만든다.

### P0-B. 릴리즈 컷 + 매니페스트
- 개발망에서 `main` 이 배포 가능 상태가 되면 **annotated 릴리즈 태그**를 자른다.
- GitLab CI 가 태그 이벤트에서 test → build → scan → push → manifest 를 수행한다.
- **릴리즈 매니페스트**(`release/<tag>/manifest.json`) 신설 — 이미지 다이제스트 목록 ·
  alembic head revision · 필요한 `.env` **키 목록(값 아님)** · MCP 서버 API 버전 ·
  개인 머신 러너 호환 버전. 이 파일이 QA·라이브 배포의 계약서이자 preflight 의 검사 기준이다.

### P0-C. QA 머신 부트스트랩 (1회)
- 오프라인 설치 절차(docker/compose, 사내 미러 또는 릴레이) · read-only deploy key ·
  registry read-only 토큰.
- **시크릿 배치 계약** — `.env*` 는 git 에 없다. SOPS+age 로 `.env.*.enc` 를 저장소에 담고
  복호화 키만 QA 머신에 1회 배치하는 방식을 기본안으로 한다. 매니페스트의 env 키 목록과
  실제 파일을 대조하는 preflight 를 둔다.
- **LLM 자격증명 미배치** — feature-0043 서버측 LLM 차단(`AGENT_SERVER_LLM_ENABLED=0`)이
  기본이므로 QA 머신에는 Claude 계정 자격증명을 아예 두지 않는다. 시크릿 표면 축소가 이번
  구조의 부수 이득이다(KB 임베딩 `bge-m3`/ollama 는 계정 무관이라 유지).
- 라이브 데이터 복제 반입 경로 — `bin/backup.sh` 산출물(PG `agent_kb` + MySQL `agent_memory`)
  기준, `bin/restore-rehearsal.sh` 를 QA 적재 검증에 재사용.
- TLS — 사내 CA 서명 인증서를 우선한다. MCP 클라이언트는 브라우저처럼 예외 승인을 누를 수
  없어 self-signed 는 연결 자체를 막는다(대안: 기존 `/trust/` rootCA 배포 경로).

### P0-D. QA 배포 러너 (pull-based CD)
- QA 머신 상주 타이머가 GitLab 의 `qa` 채널 태그를 폴링 → 매니페스트 획득 → 다이제스트로
  `docker pull` → preflight → 배포 → 결과를 GitLab 에 되보고.
- `bin/deploy-web.sh` 에 **registry 모드** 추가 — 빌드 단계를 건너뛰고 매니페스트의
  다이제스트로 pin overlay 를 구성한다. 현행 스크립트가 이미 `docker-compose.deploy-pin.yml`
  로 이미지를 고정하므로 확장 지점이 존재한다. 롤링·soak·last-good 롤백은 그대로 재사용한다.

### P0-E. QA 검증 게이트 (승격 조건)
- **자동 스모크**: 컨테이너 health → Caddy 경유 `/livez`·`/readyz` → OAuth discovery 2종
  (`/.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server`) →
  `/api/ai/mcp` 프로토콜 응답 → 대화 경로 스모크(기존 deploy-conversation-smoke 재사용) →
  feature-0043 브리지 `list_open_requests` 왕복.
- **수동 QA**: VPN 밖 사용자 머신의 Claude Code 에서 MCP 연결 → 브라우저 OAuth 완주 →
  도구 1회 호출 → 웹 화면 렌더 확인. 웹/UI 변경 시 PB-0008 시각검증.
- 통과 시 `promote/<tag>` 태그를 붙이는 것으로 승격한다(재빌드 없음).

### P0-F. 라이브 승격
- 라이브도 같은 매니페스트·같은 다이제스트를 pull 한다. QA 에서 검증한 바이트가 그대로 간다.
- 라이브 배포 경로를 registry 모드로 전환한다(현행 로컬 빌드 경로는 fallback 으로 보존).

## 4. Out of Scope

- **QA 데이터 마스킹 파이프라인** — 사용자 결정으로 라이브 복제본을 그대로 사용한다.
  대신 그 선택의 비용(QA 머신 = 운영 등급)을 §9 와 SECURITY 정합 항목에 명시한다.
- **Kubernetes·ArgoCD 등 오케스트레이터 도입** — 현행 docker compose 스파인(무중단 롤링 ·
  soak · last-good 롤백)이 이미 검증돼 있고, 서비스 23개 단일 호스트 규모에서 오케스트레이터
  전환은 QA 도입과 독립된 별개 결정이다.
- **GitLab 을 개발 정본으로 승격** — GitHub 개발 흐름(PR·리뷰·CI)은 변경하지 않는다.
- **VPN·방화벽 정책 자체의 설계** — 인프라 담당 영역. 본 cycle 은 필요한 도달성 요구사항만
  명세한다.
- **feature-0041/0043 의 기능 변경** — 본 cycle 은 그 표면을 **검증 대상**으로 사용할 뿐
  동작을 바꾸지 않는다.

## 5. Inputs

- 릴리즈 태그(annotated) · 포함 PR 목록
- 릴리즈 매니페스트(이미지 다이제스트 · alembic head · env 키 목록 · API/러너 버전)
- 사내 registry·PyPI 미러 엔드포인트, deploy key, registry read-only 토큰
- 라이브 백업 산출물(PG dump + MySQL dump)
- QA 머신 시크릿 키(1회 배치)

## 6. Outputs

- 사내 registry 의 태그·다이제스트 고정 이미지 세트
- QA 머신의 가동 스택 + 배포 상태 파일(`artifacts/deploy/deploy-web.state` 동형)
- QA 스모크 리포트(자동 게이트 결과) — GitLab 파이프라인 아티팩트
- `promote/<tag>` 승격 태그 = 라이브 배포 입력
- 실패 시: 자동 롤백 + 실패 사유가 GitLab 파이프라인에 기록

## 7. Main Flow

1. 개발망에서 `main` 머지 완료 → 릴리즈 태그 `v<날짜>-<seq>` 생성 → GitHub + 사내 GitLab 양쪽 push
2. GitLab CI(사내 러너): test → build(사내 미러 기반) → scan → registry push → 매니페스트 발행
3. QA 머신 타이머가 새 `qa` 채널 태그 감지 → 매니페스트 fetch → 다이제스트로 pull
4. preflight: env 키 대조 · alembic head 정합 · TLS 만료 · 디스크
5. `deploy-web.sh --from-manifest` → migrate(expand) → 무중단 롤링 → soak
6. 자동 스모크(§3 P0-E) 실행 → 결과를 GitLab 에 되보고
7. 수동 QA(사용자 머신 MCP 왕복 + 화면) 통과 → `promote/<tag>` push
8. 라이브가 `promote` 채널을 폴링 → 동일 다이제스트로 3~6 반복

## 8. Edge Cases

- 사내 미러에 베이스 이미지가 없음 → CI build 단계에서 **즉시 실패**(대체 소스 자동 탐색 금지 —
  조용한 소스 대체는 QA 와 라이브의 바이트를 다르게 만든다)
- QA 머신이 GitLab 에 도달 불가 → 배포 스킵 + 알림. 마지막 성공 상태 유지(현행 fail-closed 자세와 동일)
- 매니페스트의 env 키가 QA 에 없음 → preflight 차단(배포 시작 안 함). 부분 기동으로 넘어가지 않는다
- alembic head 불일치(QA 데이터가 더 오래된 라이브 복제본) → expand 마이그레이션 적용 후 진행,
  contract 는 라이브 정책과 동일하게 별도 cycle
- 승격 태그가 QA 미검증 릴리즈를 가리킴 → 라이브 러너가 매니페스트의 QA 스모크 결과 유무를 확인해 거부
- 개인 머신 러너 버전이 서버 API 와 불일치 → MCP 연결 시 명시적 버전 오류(무음 실패 금지)

## 9. Error Handling

- 모든 게이트는 **fail-closed**. "일단 올리고 본다" 경로를 두지 않는다 — QA 가 라이브 복제본
  데이터를 담고 있어 부분 기동 상태가 곧 노출면이다.
- 배포 실패 시 `deploy-web.sh --rollback` 이 last-good 다이제스트로 복귀한다. registry 모드에서는
  이전 이미지가 로컬에 남아 있어 재빌드 없이 복귀 가능하다(현행 로컬 빌드 모드보다 빠르고 안전).
- 스모크 실패는 배포를 롤백하되 **승격 태그를 붙이지 않는 것**으로 라이브를 보호한다.
- **알려진 한계**: QA 데이터가 마스킹되지 않았으므로, QA 머신에서의 데이터 열람·반출은 라이브와
  동일한 감사 대상이다. 이 파이프라인은 그 사실을 제거하지 않고 명시할 뿐이다.

## 10. Acceptance Criteria

- AC-1: QA 머신에서 `docker build` 없이 배포가 완료된다(빌드 산출물은 사내 registry 에서만 온다).
- AC-2: dev·QA·live 가 참조하는 이미지 다이제스트가 동일함을 매니페스트로 대조 확인할 수 있다.
- AC-3: QA 배포는 인바운드 접속 없이 QA 머신의 pull 만으로 완결된다.
- AC-4: 배포 완료 판정에 OAuth discovery 2종 + MCP 도구 왕복 probe 가 포함되며, 실패 시 승격이 차단된다.
- AC-5: 시크릿은 저장소에 평문으로 존재하지 않고, 매니페스트 env 키 목록과 실제 배치가 preflight 로 대조된다.
- AC-6: 임의 릴리즈에 대해 QA→라이브 승격이 **재빌드 없이** 태그 조작만으로 수행된다.
- AC-7: QA 머신에 LLM 계정 자격증명이 배치되지 않은 상태로 전 기능 QA 가 가능하다(feature-0043 전제).

## 11. 관련 문서

- 상세 설계·절차: [CICD_DESIGN.md](./CICD_DESIGN.md)
- 배포 스파인 정본: `unit/feature-0014-zero-downtime-deploy/docs/FUNCTION.md` ·
  `unit/feature-0020-zd-deploy-all/docs/FUNCTION.md`
- MCP 도구 표면: `unit/feature-0041-external-ai-tool-surface/docs/FUNCTION.md`
- 서버 LLM 차단 + pull 브리지: `unit/feature-0043-external-llm-bridge/docs/FUNCTION.md`
- 완료 기준: `AGENTS.md` §16.1~§16.3 · 보안 정합: `docs/SECURITY.md`
