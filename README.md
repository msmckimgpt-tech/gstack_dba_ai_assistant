# mysql_ai Delegated Template Repo

`mysql_ai`를 AI 위임 개발 템플릿 구조로 이관한 실행형 사본이다.

## 목적
- 원본 프로젝트를 유지한 채 템플릿 규약 안에서 기능 단위 추적이 가능하도록 재구성한다.
- 실행 진입점은 루트에 두고 실제 구현은 `unit/<feature-id>/src`로 분리한다.
- 로그, 데이터, 세션, 인증서 같은 런타임 산출물은 `../artifacts/`에 격리한다.
- `AGENTS.md`는 원본 루트 지침을 템플릿 실행 루트 기준으로 옮긴 정본이다.
- 템플릿 사본은 원본 프로젝트와 동시 기동하지 않는 단독 실행 전제를 따른다.

## 구조
- `AGENTS.md`: 저장소 운영 정책 정본
- `docs/`: 프로젝트 공통 문서
- `unit/feature-0001-platform-runtime`: MySQL/DAB/SQL 유틸리티
- `unit/feature-0002-agent-core`: CLI, planner, memory, SQL 실행 코어
- `unit/feature-0003-agent-web-ui`: Web UI
- `unit/feature-0004-browser-automation`: Playwright 브라우저 제어
- `unit/feature-0005-qa-mcp`: MCP 테스트와 QA 스크립트
- `unit/feature-0006-lan-proxy-access`: Caddy와 Windows LAN 프록시 자산
- `shared/`: 공용 코드 예약 영역

## 실행
1. 현재 디렉토리에서 작업한다.
2. `.env`가 로컬 전용 파일이며 원본 운영 의미를 유지하는지 점검한다.
3. 외부 Local LLM provider가 필요하면 먼저 `/root/download/docker/local_llm` 에서 별도로 기동한다.
4. 외부 provider가 `llm-shared` 네트워크와 `http://local-llm-gateway:8080/v1` 계약을 제공하는지 확인한다.
5. `ENABLE_MCP=1` 상태라면 호스트 포트 `28000`이 비어 있는지 확인한다.
6. `make start`
7. `make status`
8. `make ask q="질문"`

현재 repo는 Local LLM을 직접 기동하지 않는다. `llm-shared` 외부 네트워크가 없으면 `make` 명령이 안내 메시지와 함께 중단된다.

## GitHub 협업
- 원격 저장소는 `git@github.com:msmckimgpt-tech/ai_desk_mysql.git`를 사용한다.
- 기본 브랜치는 `main`이다.
- 작업은 GitHub Issue를 기준으로 분기한다.
- 공개 PR 브랜치 규칙은 `issue/<번호>-<short-slug>`이다.
- 내부 병렬 브랜치는 `ai/<agent-id>/<issue-number>/<slice>`를 사용하되, 로컬/worktree 전용으로만 운영한다.
- PR 제목 규칙은 `#<번호> <summary>`이다.
- 커밋 제목 규칙은 `type(scope): summary (#issue-number)`이다.
- 단일 AI provider 운영 기준은 `docs/GITHUB_AUTOMATION.md`를 따른다.
- 지원되는 provider 는 `claude` 하나이며, **self-hosted runner 의 로컬 `claude` CLI 를 직접 호출**한다 (API key / OAuth 토큰 시크릿 불필요).
- provider 우선순위는 `agent:claude` 라벨 -> 저장소 변수 `AI_PROVIDER_DEFAULT` -> 기본값 `claude` 순서다.
- 자세한 절차는 `CONTRIBUTING.md`와 `docs/GITHUB_AUTOMATION.md`를 따른다.

## 런타임 산출물
- `../artifacts/shared`: 로그, out, 세션 파일
- `../artifacts/mysql-data`: MySQL 데이터 디렉토리
- `../artifacts/mysql-backup`: 덤프 파일
- `../artifacts/certs`: TLS 인증서
- `../artifacts/caddy-data`, `../artifacts/caddy-config`: Caddy 상태

## 검증 범위
- 현재 단계 검증은 구조/경로/기동 확인까지만 반영했다.
- 엄격한 도메인 검증 시나리오는 각 feature의 `docs/TEST.md`를 정본으로 후속 작성한다.
- `.env.example`는 대체 기본값 파일이 아니라, 원본 `.env` 구조를 민감값 없이 보여주는 샘플이다.
- 2026-04-15 기준으로 현재 repo는 외부 `/root/download/docker/local_llm` provider를 소비만 하며, 내부에서 Ollama/gateway를 생성하거나 관리하지 않는다.
- 2026-04-15 기준으로 Web UI는 `LOCAL_LLM_API_BASE` 연결 가능 여부를 `local_llm_enabled`로 노출하고, 외부 provider 미기동 시 Local LLM 요청을 503으로 제한한다.
- 최근 검증 기준으로 `ENABLE_MCP=1`일 때 호스트 `28000` 포트가 이미 사용 중이면 `make start` 마지막 단계에서 `mcp` 기동이 차단될 수 있다.
