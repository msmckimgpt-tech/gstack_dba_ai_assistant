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
3. `ENABLE_LOCAL_LLM=1` 상태라면 `make start` 전에 `llm-shared` 외부 네트워크가 생성 가능한지 확인한다.
4. `make start`는 `local-llm-gateway`를 함께 기동하고, `auto/edge/core/code` alias 모델을 Ollama에 준비한다.
4. `ENABLE_MCP=1` 상태라면 호스트 포트 `28000`이 비어 있는지 확인한다.
5. `make start`
6. `make status`
7. `make ask q="질문"`

## GitHub 협업
- 원격 저장소는 `git@github.com:msmckimgpt-tech/ai_desk_mysql.git`를 사용한다.
- 기본 브랜치는 `main`이다.
- 작업은 GitHub Issue를 기준으로 분기한다.
- 공개 PR 브랜치 규칙은 `issue/<번호>-<short-slug>`이다.
- 내부 병렬 브랜치는 `ai/<agent-id>/<issue-number>/<slice>`를 사용하되, 로컬/worktree 전용으로만 운영한다.
- PR 제목 규칙은 `#<번호> <summary>`이다.
- 커밋 제목 규칙은 `type(scope): summary (#issue-number)`이다.
- 단일 AI provider 운영 기준은 `docs/GITHUB_AUTOMATION.md`를 따른다.
- Codex와 Claude는 둘 다 사용할 수 있지만, 한 이슈/한 PR/한 워크플로 런에서는 하나의 provider만 활성화한다.
- provider 우선순위는 `agent:codex` / `agent:claude` 라벨 -> 저장소 변수 `AI_PROVIDER_DEFAULT` -> 기본값 `codex` 순서다.
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
- 2026-04-15 검증 기준으로 `make start` 또는 `make local-llm-up`은 `local-llm-gateway`를 `llm-shared`에 연결하고 Ollama alias 모델(`auto`, `edge`, `core`, `code`)을 준비한다.
- 2026-04-15 검증 기준으로 Web UI `GET /api/session`은 `local_llm_enabled=true`를 반환했고, `POST /api/ask`가 API 키 없이 `model=auto`로 성공했다.
- 최근 검증 기준으로 `ENABLE_MCP=1`일 때 호스트 `28000` 포트가 이미 사용 중이면 `make start` 마지막 단계에서 `mcp` 기동이 차단될 수 있다.
