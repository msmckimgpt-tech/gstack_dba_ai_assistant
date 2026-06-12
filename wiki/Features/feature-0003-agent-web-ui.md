---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, web, fastapi, rbac, audit]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0003-agent-web-ui
linked_unit: unit/feature-0003-agent-web-ui
created: 2026-05-26
sources:
  - ../../unit/feature-0003-agent-web-ui/docs/FUNCTION.md
  - ../../docs/DECISIONS.md
  - ../../docs/SECURITY.md
---

# Feature — Agent Web UI

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0003-agent-web-ui |
| 상태 | active |
| 정본 | [[../../unit/feature-0003-agent-web-ui/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | FastAPI · 정적 UI · admin console · audit · 첨부 · sandbox · share |

## 1. 개요

사용자가 사용하는 **FastAPI Web UI + 정적 frontend** feature. `/api/ask` 진입점, 관리자 콘솔, audit subsystem (ADR-0019), 첨부 파일 업로드 + MinIO storage + sandbox schema, share link, 비밀번호 reset 등 사용자 facing endpoint 의 정본.

> **2026-06 확장 (§2.5)**: 관리 콘솔이 **데이터소스 CRUD + DB-단위 접근 + 대시보드 위젯/CloudWatch + LLM 사용량 대시보드 + 제품 insight 완료율**까지 포괄하도록 성장. agent 실행은 **ask-worker out-of-process 큐**로 cutover (orphan-on-redeploy 제거). 요청 중단·즉시 재요청, 프롬프트 자동작성 SSE 스트리밍 추가.

## 2. 상세

### 2.1 책임 경계

- **입력**: HTTP request (`/api/*`), `WebAccounts` 인증, RBAC 권한 검사
- **출력**: JSON 응답 / 정적 자산 / audit row / share link / 첨부 signed URL
- **side-effect**: MySQL mutation (admin 11 / user 5 endpoint) + `WebAuditEvents` row + MinIO PUT / signed URL

### 2.2 주요 endpoint 그룹

| 그룹 | 책임 | audit hook |
|---|---|---|
| `/api/ask` (POST) | LLM agent loop entry — `lazy_create` hint 지원, force_new 분기 | `_audit_user_action("conversation.ask")` |
| `/api/admin/accounts/*` | 계정 CRUD · `password-reset` 1 회용 임시비번 + `MustChangePassword` | `_audit_admin_mutation` Same-tx |
| `/api/admin/roles/*` · `/products/*` · `/system_prompt/*` | RBAC 카탈로그 mutation | `_audit_admin_mutation` |
| `/api/conversations/{cid}/attachments` | 첨부 업로드 (UploadFile multipart) → MinIO put | audit row + R-F4 grant drift health |
| `/api/share/*` · `/api/conversations/{cid}/share` | share link 발급 · anonymous view (ActorType="anonymous") | audit row + share_token_prefix 8 char |
| `/api/delete_conversations` (POST, bulk) | 일괄 삭제 (partial success) | conversation.delete.own gate |
| `/api/history_dates`, `/api/history_anchor` | 메시지 캘린더 점프 | conversation.read.own/.any |
| `/api/admin/health/attachment-grants` | sandbox schema grant drift health (R-F4) | admin only |

### 2.3 핵심 RBAC + audit (ADR-0019)

- 4 신규 권한: `audit.read.own` · `audit.read.any` · `audit.export` · `audit.purge`
- `_audit_admin_mutation` = Same-tx fail-safe (INSERT 실패 → rollback + 500)
- `_audit_user_action` = fail-open (long-running 격리, stderr log)
- prod fail-closed: `AGENT_AUDIT_ENABLED=1` 강제 (dev/test 만 toggle)

### 2.4 frontend state (app.js)

- `state.pendingNewConversation` + `state.pendingSentinel` (unique per lazy-create) → "+ 새 대화" race 차단 (TASK-0082)
- `state.composerAttachments.byConv[pendingSentinel]` — lazy-create staged attachment bucket (TASK-0106)
- pending assistant bubble (spinner + elapsed + step list) — TASK-0061 Phase 1
- Point rail + message calendar — TASK-0061 Phase 4/5

### 2.5 관리 콘솔 + 실행 확장 (2026-06)

| 영역 | 내용 | 관련 |
|---|---|---|
| **데이터소스 CRUD** | `/api/admin/datasources` POST/PATCH/DELETE + `/databases` (RO GRANT scope 필터). password envelope 암호화 | [[../concepts/datasource-registry]] · [[../Decisions/ADR-0030-ssrf-guard-toggle]] |
| **DB-단위 접근 UI** | 제품 상세 = 데이터소스 → 접근가능 DB. MSSQL 시스템 DB 고정칩 + 데이터 DB. 참조DB dropdown 폐지 | [[../concepts/db-level-access]] (TASK-0206) |
| **대시보드 위젯화 → CloudWatch** | 카테고리별 위젯 그리드 + per-account 영속(`WebDashboardPreferences`) + 순수 SVG sparkline·auto-refresh·drill-down | TASK-0210/0218 (main 4d688a2) |
| **LLM 사용량 대시보드** | `_record_llm_usage` chokepoint 회계 복구 + 계정/역할별 + SVG 차트(일별 stacked/도넛)·granularity·추정비용·모델 필터칩 | TASK-0163/0165/0166/0198/0202 |
| **제품 insight 완료율** | 제품별 분석완료율% 배지 + per-DB breakdown + DB별 파악내용 한 줄 인라인 | [[../concepts/insight-worker]] (TASK-0223/0242) |
| **ask-worker 큐 cutover** | in-process → `ask_jobs` 큐 + ask-worker 서비스 (web 재배포 중 run 생존) | [[../concepts/ask-worker-queue]] (TASK-0169) |
| **요청 중단 + 즉시 재요청** | 전송버튼 morph(중단), optimistic cancel(fetch abort), run-status 3중 정합 | TASK-0157/0241 (main 6655adc) |
| **프롬프트 자동작성 SSE** | 제품 프롬프트 자동작성 LLM 토큰 스트리밍 (백엔드 SSE + 프런트) | TASK-0233 |
| **fork = hybrid deep-copy** | pure git-lineage 반려(F1~F6) → `core_messages` deep-copy snapshot | ADR-WEB-0005 (TASK-0170) |
| **진입점 없는 기능 복구** | 즉시답변·공유관리·audit.purge·내활동·facet 등 7개 발굴·구성 | TASK-0158 (DESIGN-entry-points) |

## 3. 특징

- **API Vault 폐기** (ADR-0026) — per-user OpenAI key 입력 제거 → Bedrock gateway 단일 진입
- **첨부 sandbox** (ADR-0023) — `attachment_writer/reader/maintainer/cleanup` 4 MySQL user + schema 별 grant
- **TASK-0094 multi-cycle 의 hub** — Sprint 1 (MinIO + sandbox), Sprint 2 (vision), Sprint 4 (D RAG, 예정)
- **admin password reset** (TASK-0061 Phase 6, Critical §12.3) — 16 자 1 회용 임시비번 + `MustChangePassword` 강제
- **stale_error 판정** (TASK-0061 Phase 3) — `processing` 상태가 `WEB_PROGRESS_STALE_TIMEOUT_SECONDS` (기본 1200 초) 초과 시 stale 라벨

## 4. 사용법

```bash
make start            # web + agent + caddy + mysql ...
make web              # web 만
curl http://localhost:18080/admin    # dev — override (TASK-0057)
```

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0002-agent-core]] — `/api/ask` 가 agent loop import
- [[feature-0006-lan-proxy-access]] — `_get_client_ip()` 가 Caddy `trust_forwarded_for` 정합 의존
- [[feature-0007-bedrock-llm-provider]] — LLM env 단일 진입

## 6. 관련 정본

- [[../../unit/feature-0003-agent-web-ui/docs/FUNCTION|FUNCTION.md]] (정본)
- [[../../unit/feature-0003-agent-web-ui/docs/DESIGN|DESIGN.md]] — admin console UI 정본
- [[../../unit/feature-0003-agent-web-ui/docs/DESIGN-ask-worker|DESIGN-ask-worker.md]] — ask-worker 큐 설계
- [[../../unit/feature-0003-agent-web-ui/docs/DESIGN-fork-reference|DESIGN-fork-reference.md]] — fork hybrid (ADR-WEB-0005)
- [[../../unit/feature-0003-agent-web-ui/docs/DESIGN-entry-points|DESIGN-entry-points.md]] — 진입점 복구
- [[../../unit/feature-0003-agent-web-ui/docs/DECISIONS|DECISIONS.md]] (ADR-WEB-*)
- [[../../unit/feature-0003-agent-web-ui/docs/TASK|TASK.md]]
- [[../../docs/SECURITY|docs/SECURITY.md]] — audit / X-Forwarded-For trust 정책 정본

## 7. 관련 노트

- [[../Architecture/Data-Flow]] — 요청 흐름 + audit 흐름
- [[../concepts/ask-worker-queue]] · [[../concepts/datasource-registry]] · [[../concepts/db-level-access]] · [[../concepts/insight-worker]]
- [[../Decisions/ADR-0019-web-audit-events]]
- [[../Decisions/ADR-0022-minio-attachment-storage]]
- [[../Decisions/ADR-0023-sandbox-schema-mysql-users]]
- [[../Decisions/ADR-0026-bedrock-llm-provider]]
- [[../Decisions/ADR-0030-ssrf-guard-toggle]] — datasource 보안 경계 토글

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0002-agent-core]] · [[feature-0006-lan-proxy-access]] · [[feature-0007-bedrock-llm-provider]] · [[feature-0008-windows-browser-testing]]

## 9. 외부 link

- [FastAPI — UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/)
- [python-multipart](https://github.com/Kludex/python-multipart)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/substantial` · `#domain/web` · `#domain/rbac` · `#domain/audit`
