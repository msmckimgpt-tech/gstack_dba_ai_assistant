---
doc_type: CODEBASE_MAP
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
---

# Codebase Map

저장소의 파일 구조와 주요 진입점을 AI가 빠르게 참조할 수 있도록 요약한다.
기능 추가/삭제, 파일 구조 변경 시 갱신한다.

## 1. Directory Tree

```
repo/
├── AGENTS.md              # AI 운영 정책 정본
├── CONTRIBUTING.md         # 기여 및 커밋 규칙
├── CLAUDE.md               # AGENTS.md 참조 shim
├── MCP_DESIGN.md           # MCP 서비스 설계 참고 문서
├── README.md
├── Makefile                # 주요 빌드/실행 진입점
├── docker-compose.yml      # 서비스 오케스트레이션
├── .env / .env.example     # 런타임 환경변수
├── .aiignore               # AI 컨텍스트 제외 패턴
├── docs/                   # 프로젝트 수준 문서
│   ├── AGENTS.md(상위)·CONVENTIONS·DECISIONS·PROJECT·SECURITY·STATUS
│   ├── ARCHITECTURE.md
│   ├── LEARNINGS.md
│   └── CODEBASE_MAP.md     # 이 문서
├── playbooks/              # PB-0001 ~ PB-0006
├── shared/                 # 공통 모듈 (현재 예약 영역)
├── tests/integration/      # 통합 테스트
└── unit/                   # 기능 단위
    ├── _template/
    ├── feature-0001-platform-runtime/
    ├── feature-0002-agent-core/
    ├── feature-0003-agent-web-ui/
    ├── feature-0004-browser-automation/
    ├── feature-0005-qa-mcp/
    └── feature-0006-lan-proxy-access/
```

## 2. Key Entry Points

| File | Role | Notes |
|------|------|-------|
| `Makefile` | 실행/운영 진입점 | `make start`, `make stop`, `make status`, `make build`, `make web`, `make browser-up`, `make mcp-test` |
| `docker-compose.yml` | 서비스 오케스트레이션 | `mysql`, `agent`, `memory-init`, `insight-worker`, `mcp`(선택) |
| `.env` | 런타임 환경변수 (정본) | 포트, 모델, DB 자격증명 — 원본 `mysql_ai`의 운영 의미를 보존 |
| `.env.example` | 예시 템플릿 | 민감값 제거된 샘플. 런타임은 읽지 않음 |
| `AGENTS.md` | AI 운영 정책 정본 | 섹션 §1~§17 + Part A~G 구조 |
| `MCP_DESIGN.md` | MCP 서비스 설계 | `feature-0005-qa-mcp`와 연동되는 설계 참고 |
| `README.md` | 사람용 개요 | 구조와 시작 절차 |

## 3. Shared Module Index

| Module | Purpose | Used By |
|--------|---------|---------|
| `shared/` | 공용 코드 예약 영역 | 현재 사용 중인 모듈 없음 (feature 간 직접 공유 자산 없음). 추후 공용 유틸 등장 시 ADR 경유로 승격 |

## 4. Feature File Index

| Feature | 역할 | 주요 소스 |
|---------|------|-----------|
| `feature-0001-platform-runtime` | 플랫폼 런타임/공통 자산 | (scaffold — `src/README.md`, `tests/README.md`) |
| `feature-0002-agent-core` | Agent 핵심 로직 | `src/agent_core.py` (라이브 진입점 = in-process tool-calling 루프), `src/modules/*` (config/llm/knowledge/sql_ops 등), `tests/test_llm_api.py` |
| `feature-0003-agent-web-ui` | Agent Web UI | `src/app.py` |
| `feature-0004-browser-automation` | 브라우저 자동화 | `src/app.py`, `src/ctl.py` |
| `feature-0005-qa-mcp` | QA 및 MCP 테스트 | `src/mcp_tests.py` |
| `feature-0006-lan-proxy-access` | LAN/프록시 접근 | (scaffold — `src/README.md`, `tests/README.md`) |
| `_template` | 신규 feature 템플릿 | `docs/AGENTS.md`, `docs/TASK.md`, `docs/FUNCTION.md`, `docs/REPORT.md`, 등 |

각 feature는 `docs/`(AGENTS, FUNCTION, TASK, TEST, REPORT, MODIFY, REVIEW), `src/`, `tests/` 구조를 따른다.

## 5. External Interfaces

| Interface | Type | Used By |
|-----------|------|---------|
| MySQL 8.0 (container `mysql`) | 런타임 DB | agent, memory-init, insight-worker |
| LLM API (외부) | HTTPS | `feature-0002-agent-core` (`test_llm_api.py` 포함) |
| MCP 프로토콜 | IPC/stdio | `feature-0005-qa-mcp` |
| 브라우저 (로컬/헤드리스) | Automation | `feature-0004-browser-automation` |
| GitHub (원격) | git/HTTPS | `CONTRIBUTING.md` 의 PR 흐름 사용 |
| `../../artifacts/` | 런타임 산출물 | 모든 feature 실행 결과 — Git 외부 |

## 6. Automation Assets

자동화 워크플로 (`ai-*`, `policy-contract`, `selfhosted-runtime-smoke`, `owner-agent-report`) 와 `automation-contract.json` 은 2026-05-15 폐기되어 더 이상 사용하지 않는다. GitHub 흐름은 일반적인 PR 머지 (`gh pr create` + 사람 리뷰 + `gh pr merge`) 로 일원화한다.
