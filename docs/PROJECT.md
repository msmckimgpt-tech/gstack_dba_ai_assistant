---
doc_type: PROJECT
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.47.2
domain: [product, scope]
ai_read_priority: 2
---

# Project

## 1. 프로젝트 개요
이 프로젝트는 기존 `mysql_ai`를 AI 위임 개발 템플릿 구조로 이관한 실행형 사본이다.
루트는 운영 진입점만 담당하고, 실제 구현은 기능 단위 `unit/<feature-id>/src`로 관리한다.

## 2. 목표
- 기능 단위 소유권을 명확히 한다.
- 원본 프로젝트와 분리된 실행 가능한 템플릿 사본을 유지한다.
- 런타임 산출물을 코드 저장소 밖으로 격리한다.
- `AGENTS.md`와 `.env` 의미 체계는 원본 루트 프로젝트 기준을 최대한 보존한다.

## 3. 대상 독자
- 실제 기능을 구현하는 AI 에이전트
- 결과를 검토하고 승인하는 사람
- 이후 작업을 이어받는 다른 AI 또는 개발자

## 4. 범위
### In Scope
- `mysql_ai` 실행 코드와 설정의 템플릿 구조 이관
- 기능 단위 문서화
- 루트 실행 파일 유지
- 구조/기동 검증

### Out of Scope
- 원본 프로젝트 자체의 구조 변경
- 엄격한 도메인 검증 시나리오 작성 완료
- 승인 없는 파괴적 운영 변경
- 비밀정보의 버전관리
- 원본 프로젝트와의 동시 기동 지원

## 5. 성공 기준
- 코드가 `unit/<feature-id>/src` 기준으로 재배치되어 있다.
- `docker-compose.yml`, `Makefile`이 새 구조만 참조한다.
- 런타임 산출물이 `../../artifacts`로 분리된다.
- 다음 작업자가 문서만 읽고 기능 경계와 실행 방법을 파악할 수 있다.

## 6. 제약사항
- 문서 간 중복 진실을 만들지 않는다.
- 보안 관련 변경은 명시적으로 검토한다.
- `.env.example`에는 실제 키를 넣지 않는다.
- `.env`는 로컬 전용으로 관리하되, 값의 운영 의미는 원본 루트 `.env`를 따른다.
- 불명확성은 숨기지 않고 기록한다.

## 7. 우선순위
1. 안전성
2. 명확성
3. 추적성
4. 유지보수성
5. 개발 속도

## 8. 실행 환경 및 빌드

### 8.1 언어 및 런타임
- Python 3.11
- Docker Compose
- MySQL 8.0 — `web*` control plane (RBAC/audit/auth)
- PostgreSQL 16 + pgvector + Apache AGE — KB(`agent_kb`) · agent runtime(`agent_runtime` schema) · assistant 작업공간(`agent_scratch`) 정본 (ADR-0021 / ADR-0024 / ADR-0027 / ADR-0028). 라이브 KB 이미지는 2026-06-30 AGE cutover(PR #477) 이후 AGE 포함 커스텀 `kb-pg-age:pg16` 이며, compose 는 `${KB_PG_IMAGE:-pgvector/pgvector:pg16}` + `KB_PG_PRELOAD`/`KB_PG_REPLICA_PRELOAD` 토글로 이미지·preload 를 선택한다(compose 기본값 자체는 여전히 `pgvector/pgvector:pg16`)
- pgbouncer (PG 연결 풀) · Caddy 2 (엣지 TLS·LAN 단일 진입) · MinIO (첨부 오브젝트 스토리지) · LiteLLM bedrock-gateway (LLM) · Ollama (KB 임베딩)
- WSL Ubuntu

### 8.2 의존성 설치
```bash
make start
```

### 8.3 테스트 실행
```bash
make status
make web
make browser-up
make mcp-test
```

### 8.4 빌드
```bash
make build
```

### 8.5 배포
- 배포 절차: 라이브 무중단(zero-downtime) 스파인 `make deploy-web` = `sudo -E bin/deploy-web.sh`
  (web 롤링 + 워커 + gateway reconcile, `origin/main` HEAD 기준). 부분 범위 = `make deploy-web-only`
  (web+caddy) · `make deploy-workers` (insight/ask+gateway), 되돌리기 = `make web-rollback`
  (= `bin/deploy-web.sh --rollback`). `make deploy-all` 은 `deploy-web` 의 명시적 alias
  (feature-0020 — 스파인이 전 배포 대상 커버).
- 정본: feature-0014(무중단 스파인) · feature-0015(워커 graceful·백업 위생) · feature-0017(빌드 게이트) ·
  feature-0020(전 대상 확장) · feature-0039(정기 잡 인-컨테이너). 완료 판정 기준은 `../AGENTS.md` §16
  (§16.1 완료 기준 · §16.2 완료 선언 · §16.3 deploy-backed 소비자 완료 기준), 웹 UI 시각검증 기준은
  §16.6 + 실 Windows 브라우저 PB-0008.
- AI 자율 배포: 기본 불가 (사람 승인 필요). 예외 = `FIRST_REQUEST.md` / `unit/<id>/docs/FUNCTION.md`
  `## Pre-approved Changes` 의 `deploy_scope: included` 선언 범위 (`../AGENTS.md` §12.2).

## 9. 빌드 자동화

### 9.1 자동화 도구
- **Makefile**: 프로젝트 루트 `../Makefile`이 주요 빌드/실행 진입점이다.
- 주요 명령: `make start`, `make stop`, `make status`, `make build`, `make web`, `make browser-up`
- 상세 Make 타깃 목록은 `../AGENTS.md` §운영 명령 참조.

### 9.2 서비스 정의
- **Docker Compose**: `../docker-compose.yml`로 서비스 오케스트레이션
- 서비스 23개(2026-08-20 `docker-compose.yml` 실측) — 데이터: `mysql` · `postgres` · `pgbouncer` ·
  `postgres-replica` · `postgres-replica-init` · `minio` · `minio-init` / 에이전트·워커: `agent` ·
  `memory-init` · `insight-worker` · `ask-worker` · `ask-worker-surge` · `ops-scheduler` / 웹·엣지:
  `web-a` · `web-b` · `caddy` / LLM: `bedrock-gateway` · `bedrock-gateway-surge` · `embed-ollama` /
  도구·MCP: `mcp` · `gdrive-mcp` · `ext-tool-mcp` · `browser`
- 상세 볼륨/포트 설정은 `../AGENTS.md` §Docker Compose 기준 참조.

## 10. CI/CD 및 자동화

GitHub Actions 기반 자동화 (`ai-*` 워크플로, `policy-contract`, `selfhosted-runtime-smoke`, `owner-agent-report`, `automation-contract.json`) 와 별도 AI 프롬프트 자산은 2026-05-15 폐기되어 더 이상 사용하지 않는다. GitHub 운영은 일반적인 PR 흐름 (`gh pr create` + 사람 리뷰 + `gh pr merge`) 으로 일원화한다.

- 공개 PR 브랜치: `issue/<번호>-<short-slug>`
- 내부 병렬 브랜치: `ai/<agent-id>/<issue-number>/<slice>` (로컬/worktree 전용)
- 커밋 형식: `type(scope): summary (#issue-number)`
- 자세한 내용은 `../CONTRIBUTING.md`를 따른다.

## 세션 정지 감지 임계 (§13.2.11)

<!-- AGENTS.md §13.2.11 의 stalled 판정 임계를 기록한다. 기록 칸이 없으면 조정은 일어나지 않는다. -->

- 임계: <TBD: 기본 20분 — 「이 프로젝트의 최장 단일 도구 호출 × 2」로 산출>
- 산출 근거 (§16.7 G4 경계 양측):
  - 직하 (정상 장기 도구 호출 최대 지속): <TBD>
  - 직상 (문제로 판정해야 할 무신호): <TBD: 실증 84분 / 11분 27초>
- 관측자 배치: <TBD: 인프라 레벨 단일 관측자 / 프로젝트 전용 — 등록 경로 목록 위치>