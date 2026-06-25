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
  - unit/feature-0010-google-drive-integration/docs/TASK.md
  - unit/feature-0011-shared-extraction/docs/TASK.md
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
| feature-0002-agent-core | in-progress | 2026-06-25 | [TASK](../unit/feature-0002-agent-core/docs/TASK.md) | init "준비" 임베딩 지연 회귀 해소(전용 embed-ollama·캐싱·fast-timeout)·요청량 한도 메시지 주체 구분·datasource 회로차단 안내 문구 분리(고장 오인 해소) / ITEM-11 메타데이터 컨텍스트·NL→SQL flywheel |
| feature-0003-agent-web-ui | in-progress | 2026-06-25 | [TASK](../unit/feature-0003-agent-web-ui/docs/TASK.md) | 역할/제품 프롬프트 AI 자동작성·제품 분석률 95% 제품프롬프트 자동완성·규칙 자동 추가 DB insight 커버리지 UI·지식베이스 메뉴 재편 / 메타데이터 거버넌스 포탈(ITEM-11) · 좌측 대화 전환 크로스페이드 · 새 요청 진행 중 이전 답변 '단계 보기' 버튼 소실 수정 |
| feature-0004-browser-automation | in-progress | 2026-04-06 | [TASK](../unit/feature-0004-browser-automation/docs/TASK.md) | 구조 이관 완료, smoke 검증 예정 |
| feature-0005-qa-mcp | in-progress | 2026-04-06 | [TASK](../unit/feature-0005-qa-mcp/docs/TASK.md) | 스켈레톤 — MCP 기동 검증 예정 |
| feature-0006-lan-proxy-access | in-progress | 2026-04-06 | [TASK](../unit/feature-0006-lan-proxy-access/docs/TASK.md) | caddy 운영 자산 이관 완료 |
| feature-0007-bedrock-llm-provider | in-progress | 2026-05-21 | [TASK](../unit/feature-0007-bedrock-llm-provider/docs/TASK.md) | AWS Bedrock(Seoul) provider 통합, API Vault 폐기 (ADR-0022) |
| feature-0008-windows-browser-testing | review | 2026-06-04 | [TASK](../unit/feature-0008-windows-browser-testing/docs/TASK.md) | Windows 브라우저 자동 구동 + Playwright MCP (PB-0008) |
| feature-0009-group-conversation | in-progress | 2026-06-25 | [TASK](../unit/feature-0009-group-conversation/docs/TASK.md) | 안 읽은 메세지/@멘션 배지(gc-unread-badge, REQ-GC-R8 read-state, alembic 0019 + 0020 baseline backfill + read-fix 커서 전진 보정 + read-500-fix(읽음 API `POST /read` 서버 import 정정 `modules.db`→`shared.db`) + read-idspace-fix(읽음 커서·unread 집계는 core_messages.id 공간인데 FE 가 표시 store messages.id 를 보내 GREATEST 가 전진 영구 거부하던 최종 근본원인 — 핸들러가 항상 MAX(core_messages.id)로 전진) — 읽지 않은 신규만 집계, 읽으면 0) · 공유 대화 join 불가 수정(PG named-param 타입 모순 AmbiguousParameter 해소) · assistant SQL dialect 교정+발신자 맥락 라벨(MySQL T-SQL thrashing 해소, agent-core) · optimistic 발신자 표시 정정(전송 직후 owner 오표시 깜빡임 제거) · 참가자 per-message 제품 선택·발화(authz, REQ-GC-R7) · 라이브 UX(처리 중 composer 비잠금·1:1 인터럽트 재요청·그룹 @assistant 중복차단)·owner 게이트 (cross-cut: 0002/0003) |
| feature-0010-google-drive-integration | in-progress | 2026-06-23 | [TASK](../unit/feature-0010-google-drive-integration/docs/TASK.md) | Google Drive 연동 토대 — 계정별 OAuth 토큰 암호화 + MCP 구성 seam (연동 미수행/비활성 scaffold) |
| feature-0011-shared-extraction | in-progress | 2026-06-25 | [TASK](../unit/feature-0011-shared-extraction/docs/TASK.md) | `shared/` 공통 코드 추출 P5a Step1~5c 완료 (model_catalog·config·db·conn_health·datasources 소비처 마이그레이션 + alias shim 4종 전량 제거, make test 회귀 0); 잔여 Step6(feature Dockerfile 분리) |

> **미머지 활성 worktree**: 없음 — 현행 worktree(feature-0002·0003·0009)는 모두 `ahead=0`(작업 main 병합 완료). 미머지 in-flight 작업이 생기면 표 아래 note 로만 표기하고, 병합 시 행을 갱신한다(ADR-0031 §1).
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
- feature-0010 → feature-0003(인증/라우트 인라인), feature-0002(`modules/cred_crypto`)
- feature-0011 (refactor) → feature-0002·feature-0003 공통 코드 `shared/` 추출 (양 feature import 재배선)

## 3. 블로킹 항목
- **SSOT 통합(META-0003) Phase 3** — tracked secret 노출 종료(`.env.secret.bak-task0228` 등)는 **rotation(사용자) 선행** 필요. 근거: ADR-0031 §4 / [DOC_REGISTRY.md](./DOC_REGISTRY.md).
- 그 외: 없음.

## 4. 통합 테스트 현황
- 현재 기준: 구조/기동 검증 (`docker compose config`, `make status/web/browser-up/browser-health`, `GET /api/session`).
- 기능별 테스트 정본: `unit/<feature>/docs/TEST.md`.

## 5. 전체 진행률
- 등록 기능(main `unit/`): 11
- review 1 (feature-0008) · in-progress 10 · done 0 · blocked 0
- 상세 진척·이력: 각 unit TASK.md / [STATUS_ARCHIVE.md](./archive/STATUS_ARCHIVE.md)
