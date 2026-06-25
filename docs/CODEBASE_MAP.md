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
├── playbooks/              # PB-0001 ~ PB-0006, PB-0008
├── shared/                 # 공통 모듈 패키지 (feature-0002·0003 공유): __init__·model_catalog·config·db·conn_health·datasources (feature-0011 추출)
├── tests/integration/      # 통합 테스트
└── unit/                   # 기능 단위
    ├── _template/
    ├── feature-0001-platform-runtime/
    ├── feature-0002-agent-core/
    ├── feature-0003-agent-web-ui/
    ├── feature-0004-browser-automation/
    ├── feature-0005-qa-mcp/
    ├── feature-0006-lan-proxy-access/
    ├── feature-0007-bedrock-llm-provider/
    ├── feature-0008-windows-browser-testing/
    ├── feature-0009-group-conversation/
    ├── feature-0010-google-drive-integration/
    └── feature-0011-shared-extraction/
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

`shared/` 는 feature-0002(agent-core)·feature-0003(web-ui)·격리 컨테이너가 공유하는 Python 패키지다
(feature-0011 P5a 점진 추출, Step 1~5 완료). 컨테이너는 Dockerfile `COPY shared /app/shared`, 테스트는
Makefile PYTHONPATH 의 `/work` 로 import. `from shared.<mod> import ...` 형식. **alias shim 없이 정본 단일 경로**
(추출 초기엔 `modules/X`=`shared.X` alias shim 으로 비파괴 추출했으나 Step 5 에서 소비처를 `shared.*` 로 마이그레이션 후 shim 전부 제거).

| Module | Purpose | Used By |
|--------|---------|---------|
| `shared/__init__.py` | 패키지 골격 | (패키지 마커) |
| `shared/model_catalog.py` | LLM 모델 카탈로그 (순수 stdlib) | feature-0002·0003 |
| `shared/config.py` | 설정·환경변수·플래그 (L0 foundation, fan-in 25; 16+ 모듈이 wildcard 재노출) | feature-0002·0003·컨테이너 |
| `shared/db.py` | DB 연결/풀/PG 라우팅 (repo 최다결합, fan-in 17; `_pg_connect`·`_POOL_REGISTRY` 등 underscore 심볼) | feature-0002·0003·컨테이너·healthcheck |
| `shared/conn_health.py` | per-datasource 연결 health 모니터 (TCP liveness, circuit) | feature-0002·0003 (db·datasources 와 lazy 상호참조) |
| `shared/datasources.py` | datasource 레지스트리 (DB+`.env` 병합, 자격증명 복호) | feature-0002·0003 (cred_crypto back-dep — 아직 modules/) |

> 아직 추출되지 않은 cross-feature 공통 후보(cred_crypto·memory·llm 등)는 feature-0002 `modules/` 에 잔존(후속 step). 신규 공용 모듈 추가는 PB-0002 참조.

## 4. Feature File Index

| Feature | 역할 | 주요 소스 |
|---------|------|-----------|
| `feature-0001-platform-runtime` | 플랫폼 런타임/공통 자산 | (scaffold — `src/README.md`, `tests/README.md`) |
| `feature-0002-agent-core` | Agent 핵심 로직 | `src/agent_core.py` (라이브 진입점 = in-process tool-calling 루프), `src/modules/*` (config/llm/knowledge/sql_ops 등), `tests/test_llm_api.py` |
| `feature-0003-agent-web-ui` | Agent Web UI | `src/app.py` |
| `feature-0004-browser-automation` | 브라우저 자동화 | `src/app.py`, `src/ctl.py` |
| `feature-0005-qa-mcp` | QA 및 MCP 테스트 | `src/mcp_tests.py` |
| `feature-0006-lan-proxy-access` | LAN/프록시 접근 | (scaffold — `src/README.md`, `tests/README.md`) |
| `feature-0007-bedrock-llm-provider` | AWS Bedrock(Seoul `ap-northeast-2`) LLM provider 통합 — 사용자별 API Vault 폐기(ADR-0022) | litellm gateway 구성(`src/config/litellm_config.yaml`), `.env.bedrock` |
| `feature-0008-windows-browser-testing` | 실제 Windows 브라우저(CDP) 자동 구동 검증 워크플로 + Playwright MCP (PB-0008, 웹/UI 완료 게이트) | `bin/win-browser.py`, `bin/playwright-mcp.sh`, `.mcp.json` |
| `feature-0009-group-conversation` | 그룹 대화(멤버 roster·보관 이동·나가기·공유 참여 owner 게이트·kick/ban) — **cross-cut** | 코드 거주: feature-0002(`modules/group_members`)·feature-0003(`src/app.py`) |
| `feature-0010-google-drive-integration` | 계정별 Google Drive 연동 토대(OAuth 토큰 암호화 + MCP seam) — 연동 미수행/비활성 scaffold | `src/gdrive_mcp_seam.py` (feature-0002 `modules/cred_crypto` 의존) |
| `feature-0011-shared-extraction` | 공통 모듈 `shared/` 점진 추출 리팩터(P5a Step 1~5 완료 — model_catalog·config·db·conn_health·datasources, 4 alias shim 제거) | `shared/*` + feature-0002·0003 import 재배선 (§3 참조) |
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

## 7. Known Gaps (미배선 설계 / 의도적 보류)

코드에 존재하나 라이브에 **가동되지 않는** 설계 — 후속 결정/배선 대상. 추출·리팩터 시 dedup-merge 하지 말고 보존한다.

| Gap | 위치 | 상태 | 비고 |
|-----|------|------|------|
| **GDPR legal-erasure (#4)** | feature-0002 `src/modules/attachment_reconciliation.py` (TASK-0094 D6 4-state + legal pseudonym, Phase 10 의존) | **미배선(unwired)** | 라이브 web(feature-0003)판 reconciliation 에는 legal-erasure 경로가 가동되지 않는다. 코드 보존(삭제·병합 금지). wiring 은 **별도 compliance 결정** 사항. (feature-0011 ANCHOR §3 동반 메모 출처) |
