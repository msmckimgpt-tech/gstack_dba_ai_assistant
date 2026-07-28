---
doc_type: TASK
feature_id: feature-0023-conversation-api-access
status: active
edit_policy: append
source_of_truth: true
feature_status: in-progress
feature_status_date: 2026-07-28
feature_status_note: 외부 AI 용 Conversation API (Bearer 토큰·scope 교집합+절대 denylist·CLI 발급·MCP) + 발견 진입점(llms.txt·매니페스트·큐레이션 OpenAPI·가이드) · (07-28) 대화 품질 조정 — 외부 AI 가 모델·추론 강도·제품·폴더 커스텀 지침·첨부를 조정. 인증 필수 `GET /api/ai/capabilities` 가 계정별 라이브 값 제공(작업화면 선택기와 동일 필터 재사용 = 표시-집행 정합·신규 권한 코드 0), 익명 매니페스트는 포인터만(인스턴스 데이터 0 불변식 보존), 큐레이션 OpenAPI +6 path·가이드 §4.7, MCP tool 4→11, 토큰 안전 기본 scope 에 `folder.` 확장(절대 denylist 무변경·기존 발급 토큰 무회귀). 회귀 2586 passed/0 failed
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-22

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - `unit/feature-0003-agent-web-ui/src/routers/_bootstrap_schema.py` — `_ensure_web_api_tokens_schema` 신규
  - `unit/feature-0003-agent-web-ui/src/web_context.py` — `_get_authenticated_account` Bearer fallback + 토큰 helper
  - `unit/feature-0003-agent-web-ui/src/app.py` — `_account_has_permission` 토큰 scope 교집합 게이트
  - `bin/api-token-issue.sh` (+ python helper) — 발급/폐기 CLI
  - `bin/conversation-mcp.sh` + MCP 서버 python 모듈 — 대화 tool 래퍼
  - `unit/feature-0023-conversation-api-access/src/*` — MCP 서버 코드 거주
  - 테스트: `unit/feature-0003-agent-web-ui/tests/` (토큰 인증) + feature-0023 tests
- **접근 방법:** 세션 쿠키 인증 진입점에 Bearer fallback 만 얹어 blast-radius 최소화.
  토큰은 해시 저장·scope 한정(`conversation.*`)·저권한 서비스 계정 귀속으로 심층방어.
  발급은 콘솔 밖 CLI. MCP 서버는 토큰을 env 로 받아 REST 를 tool 로 래핑. additive·fail-closed.
- **위험도:** Critical (인증/인가 신설 — SECURITY §3)

<!-- PLAN-APPROVED by user on 2026-07-22 (entry persona arg-given dispatch, Phase 1+2 전체 승인) -->

## 3. Task Queue
- [x] TASK-0001: 설계 확정 + feature 문서(FUNCTION/ANCHOR/TASK) 기입
- [x] TASK-0002: `WebApiTokens` 스키마 (`_ensure_web_api_tokens_schema` 멱등, fast/slow path)
- [x] TASK-0003: Bearer 토큰 인증 경로 (`_get_account_by_api_token` + 쿠키 fallback + `LastUsedAt`)
- [x] TASK-0004: 스코프 강제 (`_account_permissions` allowlist 교집합 + **절대 denylist**)
- [x] TASK-0005: 발급/폐기 CLI (`bin/api-token-issue.sh`) + audit + scope 검증 + privileged 경고
- [x] TASK-0006: 단위 테스트 (컨테이너 17 passed — 파싱/scope/denylist/fail-closed/인증)
- [x] TASK-0007: §18.8 적대적 보안 리뷰 (HIGH-1/HIGH-2 적발→수정, REV-20260722-0002)
- [x] TASK-0008: MCP 서버 (`conversation_mcp_server.py` + `bin/conversation-mcp.sh` gated, tool 4종)
- [x] TASK-0009: MCP smoke(tool 등록·gated) + `.mcp.json` 등록 + example env + gitignore
- [x] TASK-0010: verify-completion + STATUS.md + commit/push + cycle-final + 배포 + 라이브 e2e
  (배포 66a48870 soak PASS · 라이브 e2e: 토큰→/api/ask 200 · admin 엔드포인트 403 · 무토큰 401)
- [x] TASK-0011: 발급 CLI 서비스명 hotfix (web→web-a/web-b 자동감지, CHG-20260722-0002)
- [x] TASK-0012: 외부 AI API 발견 진입점(llms.txt/manifest/guide)+가이드라인+openapi 익명 차단 (CHG-20260724-0003)
- [x] TASK-0013: 발견 blackbox 검증(URL-only 서브에이전트 성공) + 가이드 정확화(401/403·동기ask·base_url·토큰연락처) + 기계판독 OpenAPI /api/ai/openapi.json (CHG-20260724-0004)

## 20260728T1035-conversation-quality-controls

### 요청
사용자(2026-07-28): "이전에 서비스 내 api 를 구축하여 외부의 AI작업자가 서비스를 이용하는 환경을
조성했습니다. 그 중, **대화의 품질 또한 외부 AI작업자가 조정할 수 있도록** 구성해주세요 —
모델, 추론 강도, 제품, 그 외 추가적인 사항들." 범위는 사용자 선택으로 **최대**(첨부 + 폴더 커스텀
지침까지, 토큰 scope allowlist 확장 포함).

### 진단
`model`·`reasoning_level` 은 이미 `/api/ask` body 계약에 있었고 가이드에도 문서화돼 있었다. 실제
간극은 두 가지였다.
1. **제품 축이 발견 자료에 전혀 없었다** — 조정 자체는 가능(신규 대화 ask 힌트 / 기존 대화 PATCH,
   토큰 scope 에 `product.access.` 포함)했지만 매니페스트·OpenAPI·guide 어디에도 없어 외부 AI 가
   존재를 알 수 없었다.
2. **"내가 쓸 수 있는 값"을 조회할 경로가 없었다** — 모델은 `model.access.<value>` RBAC
   (2026-07-28 신설), 제품은 `product.access.<key>` 로 계정마다 다르게 열리는데, 익명 매니페스트는
   설계상 "인스턴스 데이터 0"(SEC-20260724)이라 목록을 실을 수 없다. 외부 AI 는 값을 추측하다
   400/403 을 맞는 구조였다.

### 결정 (D1~D4)
- **D1 — capabilities 를 인증 계층에 신설**: `GET /api/ai/capabilities`(신규 권한 코드 0, 인증만).
  익명 allowlist 에 넣지 않아 §7 "익명=static contract" 불변식 보존, 익명 매니페스트에는 포인터만.
- **D2 — 표시-집행 정합**: 목록은 작업 화면 선택기와 **같은 필터 함수**를 재사용
  (`_filter_models_for_account_access`·`_filter_products_for_account_access`). 새 판정 로직을 만들면
  capabilities 가 보여준 값을 ask 가 403 하는 불일치가 생긴다.
- **D3 — ask 의 제품 힌트 계약은 불변**: 기존 대화 per-request override 를 추가하지 않는다
  (TASK-0047 race 가드 = 제품 변경은 PATCH 단독 진실). 대신 PATCH 를 발견 자료·MCP tool 로 노출.
- **D4 — 토큰 scope 에 `folder.` 확장**: 폴더 커스텀 지침이 품질 축이므로(사용자 결정).
  `folder.*` 는 `.own` 2개뿐이고 절대 denylist(`.any`·관리)는 무변경. 기존 토큰은 저장된 scope
  그대로라 무회귀 — 열려면 재발급.

### Task Queue
- [x] TASK-0014: capabilities 응답 계약 설계 + scope 확장 안전성 분석
- [x] TASK-0015: 토큰 안전 기본 scope `folder.` 확장 (`web_context` + `bin/api-token-issue.sh`)
- [x] TASK-0016: `GET /api/ai/capabilities` 구현 (5축·부분 degrade·대화 접근 게이트)
- [x] TASK-0017: 발견 자료 4종 확충 (매니페스트 `quality_controls`·큐레이션 OpenAPI 6 path +
      `Capabilities`/`Folder`/`QualityAxis` 스키마·guide §4.7·llms.txt)
- [x] TASK-0018: MCP tool 7종 추가 (`list_capabilities`·`set_conversation_product`·`list_folders`·
      `create_folder`·`set_folder_instructions`·`move_conversation_to_folder`·`upload_attachment`)
      + `ask` 제품 인자 + multipart 헬퍼
- [x] TASK-0019: 단위 테스트 (`test_ai_capabilities.py` 10 + `test_api_token_auth.py` folder scope 5)
      + 골든 route 스냅샷 갱신 + T9 필터 호출처 검증 강화 — 전체 2586 passed / 0 failed
- [x] TASK-0020: 문서 (FUNCTION/TASK/MODIFY/REVIEW/REPORT/TEST/ANCHOR·SECURITY §25.1·ARCHITECTURE·
      ROUTEMAP·STATUS·wiki)
- [x] TASK-0021: §18.8 적대 검증 + verify-completion + commit/PR #981 merge + 배포(ebedc256) + 라이브 e2e
- [x] TASK-0022: 라이브 e2e 적발 핫픽스 — capabilities `conversation.model` 이 항상 null
      (대화 단위 `"model"` 키로 읽음 → 계정별 `model:<account_id>` 정정 + allowlist 검증,
      CHG-20260728T115000)

## 4. In Progress
- TASK-0022 후속 배포·재검증

## 5. Blocked
- 없음

## 6. Done
- TASK-0001~0009 (Phase 1 인증·CLI·테스트·보안리뷰 + Phase 2 MCP).
- TASK-0010~0013 (배포·라이브 e2e·발급 CLI hotfix·발견 진입점·blackbox 검증).
- TASK-0014~0020 (대화 품질 조정 표면).

## 7. Next Action
- 핫픽스 배포 후 `conversation.model` 라이브 재확인. 이후 잔여: 저권한 서비스 계정 확보 시
  **토큰 경로** e2e(현재는 쿠키 인증으로 대체 검증) + MCP tool 실서버 왕복.

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 단위 테스트(unit test)가 통과한다 (AGENTS.md §8.2 단계 1)
- [ ] 전체/통합 테스트(integration test)가 통과하거나, 미작성 사유와 커버 계획이 TEST.md §4에 기록되었다
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다 (§18.8 적대적 보안 리뷰 포함)
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
