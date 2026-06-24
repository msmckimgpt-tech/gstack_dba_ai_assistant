---
doc_type: PROJECT_STATUS
scope: project
status: active
edit_policy: rewrite
lifecycle: active
source_of_truth: true
template_version: v3.34.1
domain: [status, index]
ai_read_priority: 6
sources:
  - unit/feature-0001-platform-runtime/docs/TASK.md
  - unit/feature-0002-agent-core/docs/TASK.md
  - unit/feature-0003-agent-web-ui/docs/TASK.md
  - unit/feature-0004-browser-automation/docs/TASK.md
  - unit/feature-0005-qa-mcp/docs/TASK.md
  - unit/feature-0006-lan-proxy-access/docs/TASK.md
  - unit/feature-0007-bedrock-llm-provider/docs/TASK.md
  - unit/feature-0008-windows-browser-testing/docs/TASK.md
  - unit/feature-0009-group-conversation/docs/TASK.md
---

# Project Status (인덱스)

프로젝트를 cross-feature 관점에서 한눈에 보는 **인덱스**다 (ADR-0031 SSOT 계약 §1 — 셀에 TASK 상세를 누적하지 않는다).

- **기능별 상세 현황 정본**: `unit/<feature>/docs/{TASK,REPORT}.md` — 본 문서는 그 요약·링크만.
- **인덱스화 이전 누적 rollup·상세 이력**: [docs/archive/STATUS_ARCHIVE.md](./archive/STATUS_ARCHIVE.md) (verbatim 보존).
- 정본 지도: [docs/DOC_REGISTRY.md](./DOC_REGISTRY.md) · SSOT 계약: [docs/DECISIONS.md](./DECISIONS.md) ADR-0031.

## 1. 기능 현황 (요약 인덱스)

| 기능 ID | 상태 | 최종 갱신 | 정본(상세) | 최근 작업 요지 |
|---|---|---|---|---|
| feature-0001-platform-runtime | in-progress | 2026-05-18 | [TASK](../unit/feature-0001-platform-runtime/docs/TASK.md) | MySQL redo log 1GiB 상향·restart policy 정렬 (TASK-0064/0059) |
| feature-0002-agent-core | in-progress | 2026-06-23 | [TASK](../unit/feature-0002-agent-core/docs/TASK.md) | NL→SQL 정확도 flywheel (`dba-ai-nl2sql` ROADMAP 드레인) |
| feature-0003-agent-web-ui | in-progress | 2026-06-23 | [TASK](../unit/feature-0003-agent-web-ui/docs/TASK.md) | LLM 사용량 한도 RBAC·UI, 첨부 lifecycle·diff (TASK-0284~0286) |
| feature-0004-browser-automation | in-progress | 2026-04-06 | [TASK](../unit/feature-0004-browser-automation/docs/TASK.md) | 구조 이관 완료, smoke 검증 예정 |
| feature-0005-qa-mcp | in-progress | 2026-04-06 | [TASK](../unit/feature-0005-qa-mcp/docs/TASK.md) | 스켈레톤 — MCP 기동 검증 예정 |
| feature-0006-lan-proxy-access | in-progress | 2026-04-06 | [TASK](../unit/feature-0006-lan-proxy-access/docs/TASK.md) | caddy 운영 자산 이관 완료 |
| feature-0007-bedrock-llm-provider | in-progress | 2026-05-21 | [TASK](../unit/feature-0007-bedrock-llm-provider/docs/TASK.md) | AWS Bedrock(Seoul) provider 통합, API Vault 폐기 (ADR-0022) |
| feature-0008-windows-browser-testing | review | 2026-06-04 | [TASK](../unit/feature-0008-windows-browser-testing/docs/TASK.md) | Windows 브라우저 자동 구동 + Playwright MCP (PB-0008) |
| feature-0009-group-conversation | in-progress | 2026-06-23 | [TASK](../unit/feature-0009-group-conversation/docs/TASK.md) | 그룹 대화 라이브 UX (cross-cut — 코드 거주: 0002/0003, ANCHOR 매핑) |

> **feature-0010-google-drive-integration**: 활성 worktree(`ai/claude/feature-0010-google-drive-integration`) 진행 중 — main `unit/` 미병합. 병합 시 본 표에 행 추가.
> 상세 TASK 이력을 셀에 누적하지 않는다(ADR-0031 §1) — 상세는 정본 링크의 unit TASK.md / 인덱스화 이전 분은 STATUS_ARCHIVE.md.

### 상태 값 정의
`planned`(요구 정리) · `in-progress`(구현 중) · `blocked`(승인/불명확 차단) · `review`(검토) · `done`(완료) · `deprecated`(폐기)

## 2. 기능 간 의존성 요약
[ARCHITECTURE.md](./ARCHITECTURE.md) §6 정본 참조. 요약:
- feature-0003 → feature-0002
- feature-0004 → feature-0001
- feature-0005 → feature-0001, feature-0002, feature-0004
- feature-0006 → feature-0001
- feature-0008 → feature-0003(검증대상), feature-0004(headless 보조)
- feature-0009 (cross-cut) → 코드 거주 feature-0002(mentions/group_members)·feature-0003(app.py)

## 3. 블로킹 항목
- **SSOT 통합(META-0003) Phase 3** — tracked secret 노출 종료(`.env.secret.bak-task0228` 등)는 **rotation(사용자) 선행** 필요. 근거: ADR-0031 §4 / [DOC_REGISTRY.md](./DOC_REGISTRY.md).
- 그 외: 없음.

## 4. 통합 테스트 현황
- 현재 기준: 구조/기동 검증 (`docker compose config`, `make status/web/browser-up/browser-health`, `GET /api/session`).
- 기능별 테스트 정본: `unit/<feature>/docs/TEST.md`.

## 5. 전체 진행률
- 등록 기능(main `unit/`): 9 (+ feature-0010 worktree 진행 중)
- review 1 (feature-0008) · in-progress 8 · done 0 · blocked 0
- 상세 진척·이력: 각 unit TASK.md / [STATUS_ARCHIVE.md](./archive/STATUS_ARCHIVE.md)
