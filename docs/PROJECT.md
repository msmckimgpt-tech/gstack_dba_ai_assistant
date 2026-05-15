---
doc_type: PROJECT
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.6.1
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
- MySQL 8.0
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
- AI 자율 배포: 불가 (사람 승인 필요)
- 배포 절차: 별도 정의 필요

## 9. 빌드 자동화

### 9.1 자동화 도구
- **Makefile**: 프로젝트 루트 `../Makefile`이 주요 빌드/실행 진입점이다.
- 주요 명령: `make start`, `make stop`, `make status`, `make build`, `make web`, `make browser-up`
- 상세 Make 타깃 목록은 `../AGENTS.md` §운영 명령 참조.

### 9.2 서비스 정의
- **Docker Compose**: `../docker-compose.yml`로 서비스 오케스트레이션
- 서비스: `mysql`, `agent`, `memory-init`, `insight-worker`, `mcp`(선택)
- 상세 볼륨/포트 설정은 `../AGENTS.md` §Docker Compose 기준 참조.

## 10. CI/CD 및 자동화

### 10.1 CI/CD 파이프라인
- GitHub Actions 기반 자동화가 구성되어 있다.
- 주요 워크플로:
  - `ai-triage.yml`: 저장소 신호 기반 autonomous issue 생성
  - `ai-execute.yml`: 실행 가능 이슈를 공개 `issue/*` 브랜치/PR로 전개
  - ~~`ai-review.yml`: 활성 provider 기반 PR 리뷰~~ — 비활성화 (issue #24, self-hosted runner OAuth 만료)
  - `policy-contract.yml`: 브랜치/PR/커밋/문서-자동화 계약 검증
  - `owner-agent-report.yml`: provider 및 위험 요약 게시
  - `selfhosted-runtime-smoke.yml`: self-hosted 런타임 smoke 검증

### 10.2 AI 워크플로 프롬프트
- `.github/ai/prompts/triage.md`: triage 워크플로 공용 프롬프트
- `.github/ai/prompts/implement.md`: 이슈 구현 워크플로 공용 프롬프트
- `.github/ai/prompts/review.md`: PR 리뷰 워크플로 공용 프롬프트

### 10.3 자동화 규칙
- 자동화 계약 정본: `.github/automation-contract.json`
- 공개 PR 브랜치: `issue/<번호>-<short-slug>`
- 내부 병렬 브랜치: `ai/<agent-id>/<issue-number>/<slice>` (로컬/worktree 전용)
- 커밋 형식: `type(scope): summary (#issue-number)`
- 자세한 내용은 `../docs/GITHUB_AUTOMATION.md`와 `../CONTRIBUTING.md`를 따른다.
