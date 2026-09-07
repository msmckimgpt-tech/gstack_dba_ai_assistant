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
3. `ENABLE_MCP=1` 상태라면 호스트 포트 `28000`이 비어 있는지 확인한다.
4. `make start`
5. `make status`
6. `make ask q="질문"`

로컬 LLM은 사용하지 않는다 (2026-09-07 사용자 결정). 별도 `local_llm` provider 기동이나
`llm-shared` 외부 네트워크는 더 이상 전제조건이 아니며, 이를 요구하던 `check-llm-network`
게이트도 제거됐다. 대화 추론은 각 사용자의 개인 머신 AI 런타임이 수행하고
(feature-0043 external-llm-bridge), KB 검색의 쿼리 임베딩은 미설정 상태이므로
`kb_retrieval` 이 `pg_trgm` 유사도로 fallback 한다.

## GitHub 협업
- 원격 저장소는 `git@github.com:msmckimgpt-tech/ai_desk_mysql.git`를 사용한다.
- 기본 브랜치는 `main`이다.
- 작업은 GitHub Issue를 기준으로 분기한다.
- 공개 PR 브랜치 규칙은 `issue/<번호>-<short-slug>`이다.
- 내부 병렬 브랜치는 `ai/<agent-id>/<issue-number>/<slice>`를 사용하되, 로컬/worktree 전용으로만 운영한다.
- PR 제목 규칙은 `#<번호> <summary>`이다.
- 커밋 제목 규칙은 `type(scope): summary (#issue-number)`이다.
- 자세한 절차는 `CONTRIBUTING.md`를 따른다.

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
- ~~2026-04-15 기준으로 현재 repo는 외부 `/root/download/docker/local_llm` provider를 소비만 하며…~~
  **(2026-09-07 폐기)** 사용자 결정 "로컬 LLM 미사용" 으로 그 provider 자체가 폐기됐고, 본 repo 의
  로컬 LLM 소비면(`llm-shared` attach · `check-llm-network` 게이트 · `titan-embed` alias ·
  `embed-ollama` 서비스 · 모델 카탈로그의 로컬 tier)이 전부 제거됐다.
- ~~Web UI는 `LOCAL_LLM_API_BASE` 연결 가능 여부를 `local_llm_enabled`로 노출하고…~~
  **(2026-09-07 폐기)** `shared/model_catalog.py` 의 `_LOCAL_LLM_ENABLED` 가 env 를 읽지 않고
  상수 `False` 이므로, `.env` 에 `LOCAL_LLM_API_BASE` 가 남아 있어도 로컬 alias(auto/edge/core/code)는
  카탈로그 밖이며 `/api/ask` 가 400 으로 거부한다.
- 최근 검증 기준으로 `ENABLE_MCP=1`일 때 호스트 `28000` 포트가 이미 사용 중이면 `make start` 마지막 단계에서 `mcp` 기동이 차단될 수 있다.

## Codex Commands

Codex 호환 command 원본은 repo-local `.codex/` 아래에 둔다. `~/.codex` 와
plugin cache 는 설치 대상일 뿐 source of truth 가 아니다.

```bash
bash repo/bin/codex-template-install.sh --check
bash repo/bin/codex-template-install.sh --link
bash repo/bin/codex-template-install.sh --check
```

copy-base 전달 과정에서 symlink 가 빠지면 Codex 의 `$<skill>` 자동완성이
`_template-*` skill 을 찾지 못한다. 첫 AI 작업자는 skill 이 없다고 판단하기 전에
wrapper 위치에서 위 명령으로 `<wrapper>/.codex -> repo/.codex` 링크를 복구한다.

필요 시 local marketplace 또는 prompt 호환 링크를 설치한다:

```bash
bash repo/bin/codex-template-install.sh --install-marketplace
bash repo/bin/codex-template-install.sh --install-prompts
```
