---
doc_type: PROJECT_STATUS
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
---

# Project Status

프로젝트 전체 현황을 한눈에 파악하기 위한 문서이다.

> 2026-05-15: TASK-0060 — `KR(킹스레이드)` / `MV(마이크로볼츠)` Product 시스템 프롬프트와 `pending/operator/admin/sales/dba` Role `전 Product 공통` 프롬프트를 실제 접근 DB 분석 결과 기반으로 정비했다. `compose_system_prompt()`는 이제 Role 공통 지침을 Product 선택 시에도 누적 적용한다 (feature-0002 + feature-0003 혼합 변경).

> 2026-05-15: TASK-0059 — `make up` 으로 활성화한 장기 실행 컨테이너의 restart policy 를 정렬했다. `mysql`, `web`, `browser`, `caddy`, `mcp` 는 `restart: unless-stopped` 를 사용하고, 일회성 `agent` / `memory-init` 은 제외한다 (feature-0001).

> 2026-05-15: TASK-0014 — 시스템 프롬프트 조립을 `Product → Role → Account → 현재 요청` 누적 구조로 재확인하고 Account scope 도 `전 Product 공통 + Product 전용` 누적 방식으로 정정했다. 현재 요청은 마지막 `user` 메시지로 보존된다 (feature-0002).

> 2026-05-15: TASK-0058 — `make browser-up` / `make insight-up` 도 `make web` 과 같은 compose/buildx provenance metadata file race 가드(`dc-build` + `up --no-build`)를 사용하도록 정렬했다 (feature-0001).

> 2026-04-23: origin 을 `git@github.com:msmckimgpt-tech/gstack_dba_ai_assistant.git` 으로 전환하고 gstack 스킬 워크플로우와 공존하는 체계로 마이그레이션했다 (`CLAUDE.md §Skill routing`, 신설 `TODOS.md`). feature 단위 작업 기록은 기존 `unit/feature-NNNN/docs/*` 그대로 유지하며, gstack 스킬 호출 시에도 `AGENTS.md` / `CONTRIBUTING.md` 가 우선 적용된다.

## 1. 기능 현황

| 기능 ID | 상태 | 담당 | 최종 갱신 | 비고 |
|---------|------|------|----------|------|
| feature-0001-platform-runtime | in-progress | AI | 2026-05-15 | **TASK-0059 (REQ-20260515-0004, Minor §12.3) make up 장기 실행 컨테이너 restart policy 정렬** — `mysql`, `web`, `browser`, `caddy`, `mcp` 에 `restart: unless-stopped` 적용. `agent` / `memory-init` 은 일회성 실행이라 제외. 원인 근거: `make status` 에서 `mcp` 만 실행 중이고 `mysql/web/browser/insight-worker` 는 내려간 상태 + `insight_worker.log` 의 `Unknown MySQL server host 'mysql'` 반복. 검증: `make up`, `make status`, `make browser-health` 통과. **TASK-0058** browser-up / insight-up buildx metadata race 가드 적용. **TASK-0057** dev 환경 single TLS termination 원칙 회복. MySQL runtime 경계 유지, 내장 Local LLM bootstrap 제거, TASK-0045 AI 전용 복제 MySQL 접속 레이어(compose replica-net + REPLICA_DB_* 자리 + `make replica-check`) 추가 |
| feature-0002-agent-core | in-progress | AI | 2026-04-15 | 외부 `local_llm` gateway 소비 계약 정리 |
| feature-0003-agent-web-ui | in-progress | AI | 2026-05-14 | **TASK-0058 (REQ-20260514-0001, Critical §12.3) 대화 공유 링크 기능 도입** — anonymous accessible read-only view + 로그인 viewer 의 fork. 사용자 결정 6 항목 (외부 anonymous 허용 / 무기한 + revoke / read+fork / full+anchored 둘 다 / `conversation.share.create` 신설 / 메시지+SQL+결과셋 노출) + codex outside voice 의 blindspot 10 건 (B1-B2 + R1-R10) 보강 반영. Phase A — `PERMISSION_DEFINITIONS` 에 `conversation.share.create` 추가 (catalog 33→34, group=conversation) + operator/sales/admin 자동 grant + `WebConversationShares` 테이블 신설 + `_ensure_web_conversation_shares_schema(conn)` 부트스트랩 양쪽 helper. Phase B — `_optional_account` + `_fork_conversation_impl` 헬퍼 + 5 endpoint (POST/GET `/api/conversations/{cid}/share[s]`, DELETE `/api/share/{id}`, GET/POST `/api/public/share/{token}[/fork]`) + `/share/{token}` FileResponse. Token = `secrets.token_urlsafe(32)` + UNIQUE 충돌 5 회 retry. revoke + view counter 는 단일 race-free UPDATE. Phase C — 헤더 `shareConversationBtn` (gated by `conversation.share.create`) + 메시지 hover "여기까지 공유" + `createConversationShare` (clipboard copy + toast). Phase D — `share.html` / `share.css` / `share.js` 신규 anonymous view (메시지 + SQL `<pre>` + 결과셋 `<table>` + 로그인 시 fork 버튼). Phase E — FUNCTION/TASK/MODIFY/REVIEW + project-level [`docs/SECURITY.md` §7](./SECURITY.md) anonymous endpoint allowlist + 외부 배포 시 IP allowlist/token 비밀번호/시간 만료 후속 cycle 권장. **위험 등급 Critical** (SECURITY.md §3 의 인증/인가 + 개인정보 + 외부 공개 범위 3 항목 동시 변경, 사내 IP 가정 전제). app.py Python AST parse OK / app.js · share.js node --check OK. **TASK-0056 (REQ-20260512-0002, Major §12.3)** 작업 화면·관리 콘솔 권한 정렬 분리** — 두 화면이 같은 `console→account→role→conversation→[product]→misc` group 순서를 공유해 admin 메타권한이 두 곳 모두 위에 노출되던 UX 회귀 fix. project-level [`docs/CONVENTIONS.md §10.6`](./CONVENTIONS.md) 화면별 권한 섹션·정렬 정책 신설 — 작업 화면 = "운영(conversation/product) → 관리(console/account/role) → 기타", 관리 콘솔 = "관리 → 운영 → 기타" 2단 section. admin.js (`ADMIN_PERMISSION_SECTIONS` + `sectionedGroupedPermissions` + `renderPermissionGrid` outer section wrapper), app.js (`PERMISSION_GROUP_ORDER` 에 `product` 추가, `WORK_SCREEN_PERMISSION_SECTIONS`, `permissionGroupOf()` 가 `system_prompt.` → product 매핑, `buildPermissionPills` 2단 묶음 렌더 + 빈 section 자동 hide), styles.css (`.perm-section-meta*` 5 클래스 + `.permission-section*` 5 클래스). cache-bust `v=20260512-perm-sections`. DB schema / backend RBAC catalog / endpoint guard / system prompt assembly 변경 0 — 인가 모델 무영향. node --check 양 파일 통과. **TASK-0055 (REQ-20260512-0001, Major §12.3) 관리 콘솔 카테고리별 다중선택 UX 정합 컨벤션 v0.2 도입 + 코드 통일** — 사용자 보고 "계정 우상단 / 역할 좌하단 / 제품 다중선택 부재" 의 일관성 결여 root cause (DOM anchor 표준 부재 + `.admin-pane-head-right` semantic 충돌) 해소. project-level [`docs/CONVENTIONS.md §10`](./CONVENTIONS.md) 신설 (다중선택 적용 룰 / DOM anchor 표준 / 자료구조 invariant / 단위 어휘 / 신규 카테고리 체크리스트) + feature-local [`unit/feature-0003-agent-web-ui/docs/DESIGN.md`](../unit/feature-0003-agent-web-ui/docs/DESIGN.md) 신규 (14 섹션, runtime assertion + a11y + keyboard map + cross-page banner + typed-confirm + RBAC partial-fail UI). 외부 design 시각 (general-purpose subagent + worker-design framework) 으로 v0.1 → v0.2 흡수 (5 gap + a11y + token + keyboard map). 코드 통일: admin.html (Accounts bulk anchor 헤더→list 하단 이전, Products multi-select HTML 신설), styles.css (4 토큰 + sticky + cross-page banner CSS), admin.js (Products `productSelected: Set` 신설 + shift-click range + Esc 단축키 + Stripe cross-page banner + typed-confirmation + RBAC partial-fail toast + `assertBulkBarContract`). admin.js 2645 → 3080 (+435), admin.html 219 → 250 (+31), styles.css 2976 → 3052 (+76). cache-bust `v=20260512-bulk-contract-v02`. node --check admin.js 통과. **TASK-0053 (REQ-20260506-0006, Major §12.3) 신규 제품 default 정책 토글 (Product 주체) + 권한 grid sub-catalog + Role/Account detail product 카드** — Product detail 에 "신규 역할 자동 접근" 토글 (`WebProducts.DefaultRoleAccess`), 권한 grid 가 dynamic `product.access.*` 분리, Role detail 은 product 별 (access 토글 + role-scope prompt) collapsible card list, Account detail 은 product 별 override flat card list. 사용자 in-cycle 설계 전환 (Role 주체 → Product 주체) 반영. E2E smoke: product `default_role_access=false` 생성 시 6 role 모두 grant 0 / `=true` 시 모두 grant 1 검증. **TASK-0052 (REQ-20260506-0005, Critical §12.3) C5 본체 완료** — Phase 1B/1C/1D + Phase 2. catalog DB-driven 전환 + WebPermissions IsDynamic/ProductId schema + product 권한 backfill (운영 transparency 메시지) + 명시적 트랜잭션 (Codex Claim 2) + 8 endpoint guards (G1-G8, Codex Claim 3 + 4 통합) + admin UI 'product' 그룹 + admin_update_account RoleId 손실 pre-existing 버그 fix. Phase 2 P0 HTTP smoke 6/6 통과 (catalog 33→34→35→34, admin 자동 grant, G1/G2/G7/G8 직접 403 검증, lifecycle cascade). 운영자 후속: D2-A 호환성 backfill 회수 — admin 콘솔의 deny override. P2 (sessions/me filter, FE chip filter) 와 F8 (admin lockout 보호) 는 별 cycle. TASK-0052 (REQ-20260506-0005, **Critical** §12.3) Phase 1A — RBAC engine catalog 인자화 refactor 완료. `_resolve_permission_catalog(conn=None)` 헬퍼 + 5 함수 시그니처 확장 (catalog kwarg, default None = 기존 정적 동작). `/api/admin/permissions` 만 신규 plumbing 검증 경로로 전환. **동작 변경 0** (33 codes 동일). Phase 1B (WebPermissions IsDynamic/ProductId + 제품 권한 backfill + caller-update) / 1C (8 endpoint guard) / 1D (admin UI) 는 별 cycle. plan 정본은 [BRIEFING-c5-permission-product-access.md](../unit/feature-0003-agent-web-ui/docs/BRIEFING-c5-permission-product-access.md). TASK-0051 (REQ-20260506-0004) 관리 콘솔 일괄 저장 정책 회복 — 인라인 save 버튼 3 종 제거 + footer `모두 적용` 단일 commit 통합, 메타 4 스키마(`information_schema`/`mysql`/`sys`/`performance_schema`) 회색 chip 강제 노출(REV-20260422-0006 시각화), `GET /api/admin/databases/available` 라이브 enum picker. C5(계정·역할 → 제품 권한 상속/override) 는 다음 cycle `/plan-eng-review` 후 진행 분리. TASK-0050 make web buildx race 회피 (Makefile dc-build 가드), TASK-0049 누적 빈 대화 일괄 정리 (88→46), TASK-0048 (REQ-20260506-0001) "새 대화" lazy 화 — client-side pending state + `/api/ask` lazy creation 으로 빈 대화 누적 차단, TASK-0047 Product Selector + Auto 모드, TASK-0044 Approach A wedge 사업팀(Sales) role + role-scope system prompt seed + REPLICA_DB_* envelope + pilot onboarding runbook, TASK-0041 클라이언트 타임아웃 Attach/Resume, TASK-0040 SQL whitelist 정규식 context-aware 2-stage 재작성, TASK-0034 Q4/Q5 재수행 완료 |
| feature-0004-browser-automation | in-progress | AI | 2026-04-06 | 구조 이관 완료, smoke 검증 예정 |
| feature-0005-qa-mcp | in-progress | AI | 2026-04-06 | 포트 28000 점유 해소 확인, MCP 기동 검증 예정 |
| feature-0006-lan-proxy-access | in-progress | AI | 2026-04-06 | 운영 자산 이관 완료 |

### 상태 값 정의
- `planned`: 요구사항 정리 단계
- `in-progress`: 구현 진행 중
- `blocked`: 승인 대기 또는 불명확성으로 차단
- `done`: 완료
- `deprecated`: 폐기

## 2. 기능 간 의존성 요약
ARCHITECTURE.md §6 참조. 현재 등록된 의존 관계:
- `feature-0003-agent-web-ui` uses `feature-0002-agent-core`
- `feature-0004-browser-automation` uses `feature-0001-platform-runtime`
- `feature-0005-qa-mcp` uses `feature-0001-platform-runtime`, `feature-0002-agent-core`, `feature-0004-browser-automation`
- `feature-0006-lan-proxy-access` uses `feature-0001-platform-runtime`

## 3. 블로킹 항목
현재 사람 승인 또는 확인이 필요한 항목:
- 없음
- ~~호스트 포트 `28000`을 외부 컨테이너 `mysql-ai-mcp`가 사용 중이라 `feature-0005-qa-mcp`의 `make start`/`mcp` 단독 기동 검증이 차단됨~~ → 2026-04-06 포트 미사용 확인, 차단 해소

## 4. 통합 테스트 현황
- 통합 테스트 대상 기능 쌍: 향후 엄격 시나리오 정의 후 확정
- 최근 통합 테스트 실행: 2026-03-26 구조/기동 검증
- 현재 기준: 구조/기동 검증만 적용
- 확인 완료: `docker compose config`, `make status`, `make web`, `make browser-up`, `make browser-health`, `GET /api/session`
- 차단됨: `make mcp-test`(MCP 기동 검증 예정)
- 2026-04-15 갱신: 현재 repo 내부 Local LLM runtime 제거 작업을 반영했고, 외부 provider 계약 기준으로 문서와 실행 경로를 정리

## 5. 전체 진행률
- 총 기능 수: 6
- 완료: 0
- 진행 중: 6
- 차단: 0
