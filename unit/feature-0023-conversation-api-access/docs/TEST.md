---
doc_type: TEST
feature_id: feature-0023-conversation-api-access
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 검증: Bearer 헤더 파싱·정규화, scope allowlist 파싱/매칭, `_account_permissions`
  scope 교집합(관리 네임스페이스 차단), `_account_has_permission`/`_account_has_product_access`
  가 scope 존중, `_get_account_by_api_token` fail-closed, MCP tool 등록·gated 런처.
- 제외: 라이브 e2e(실토큰→/api/ask 왕복)는 배포 후 §3 Run 으로 기록. **UI 자산 변경 없음**
  → PB-0008 Windows-browser 시각검증 **불필요**(python/bash/docs 만 변경, static/template
  무변경). 검증 환경 = `CLI`(서버 계약).

## 2. Test Cases
### TEST-20260722T024107-conversation-api-access-1 (Bearer 파싱)
- Purpose: `Authorization: Bearer <token>` 정상 추출, 형식 불일치/injection 거부.
- Steps: valid/case-insensitive/missing/Basic/injection-char 헤더로 `_extract_bearer_token`·
  `_sanitize_api_token` 호출.
- Expected Result: 정상 토큰 추출, 형식 불일치=빈문자, injection 문자 제거·128자 상한.

### TEST-20260722T024107-conversation-api-access-2 (scope 강제)
- Purpose: 토큰 인증 시 관리 권한이 effective=False.
- Steps: `permissions` 에 console.manage/audit.read.any=True 인 계정 + `_auth_via=api_token`
  + `_token_scopes=["conversation.","product.access."]` → `_account_permissions`.
- Expected Result: conversation.*/product.access.* True, console.manage/audit.read.any False.
  scope=None·비-토큰 계정은 무변경.

### TEST-20260722T024107-conversation-api-access-3 (인증 fail-closed)
- Purpose: 미존재/미인증 토큰은 None, 유효 토큰은 계정+scope 부착.
- Steps: fake conn 으로 `_get_account_by_api_token` — 헤더 없음/토큰 row 없음/유효 row.
- Expected Result: 헤더·row 없으면 None(계정 조회 skip), 유효 시 `_auth_via`/`_token_id`/
  `_token_scopes` 부착.

### TEST-20260722T024107-conversation-api-access-4 (MCP)
- Purpose: MCP tool 4종 등록 + 런처 gated 동작.
- Steps: dummy env 로 서버 import→`list_tools`; 런처 비활성/활성-누락 실행.
- Expected Result: [ask,get_history,list_conversations,new_conversation]; 비활성 exit0·
  누락 exit2.

### TEST-20260722T024107-conversation-api-access-5 (라이브 e2e — 배포 후)
- Purpose: 실토큰으로 /api/ask 왕복, 스코프-밖 admin 403.
- Steps: bin/api-token-issue.sh 발급 → curl -H "Authorization: Bearer <t>" POST /api/ask;
  같은 토큰으로 admin 엔드포인트 호출.
- Expected Result: /api/ask 200 + output; admin 403.

## 3. Test Run History

### Run 2026-07-22-001
- Date: 2026-07-22
- Environment: CLI
- Runner: AI
- Bridge: n/a (서버 계약·단위 검증, UI 무변경)
- Evidence: host pure-logic 24 assertion PASS(scope/파싱/인증 게이트) + MCP tool 등록·
  런처 gated smoke PASS. py_compile 3파일 OK.
- Result Summary: TEST-1~4 로직 PASS. 정식 pytest(test_api_token_auth.py)는 컨테이너
  make test 에서 수집(conftest app import). TEST-5 라이브는 배포 후.
- Pass/Fail: PASS (단위·smoke). 라이브 e2e 미수행(배포 후).
- Notes: web_context.py 는 fastapi 만 의존해 host bare import 가능.

### TEST-20260728T103500-quality-controls-1~6 (대화 품질 조정 표면)
- Purpose: 외부 AI 가 품질 5축을 **발견·조정**하되, 발견이 새 노출 경로가 되지 않음을 고정.
- Steps/Expected (상세·근거는 §3 fragment `test-runs.d/TASK-20260728T103500-conversation-quality-controls.md`):
  1. `GET /api/ai/capabilities` 익명 → **401**, 응답에 모델·제품 문자열 부재.
  2. 인증 → 5축(model/reasoning_level/product/folder_instructions/attachments) + 각 축 `set_via`,
     모델·제품 목록이 계정 권한 필터를 반영(표시-집행 정합).
  3. 권한 없는 축 → `available:false` + 사유(note). 조용한 빈 배열 금지.
  4. 접근 불가 `conversation_id` → 설정 미노출(타 계정 oracle 차단).
  5. 익명 매니페스트에 `quality_controls` **포인터만**(값 목록 부재), 큐레이션 OpenAPI 에 조정
     6 path + `Capabilities`/`Folder`/`QualityAxis` 스키마, admin 경로 부재.
  6. 토큰 scope `folder.` 확장이 `.own` 2개만 열고 `.any`·관리 네임스페이스는 차단, 기존 발급
     토큰은 무회귀.

## 3.1 Test Run History (fragment, §5.3)
신규 Run 기록은 `docs/test-runs.d/<TASK-또는-REV-id>.md` 항목당 1파일로 작성한다(병렬 세션 무충돌).
- [TASK-20260728T103500-conversation-quality-controls](./test-runs.d/TASK-20260728T103500-conversation-quality-controls.md)
  — CLI, PASS (신규·관련 39 passed / 전체 회귀 2586 passed·0 failed). UI 표면 무변경이라
  Windows-browser 미수행 — 사유는 fragment 에 명시(§15.4.1 예외).
- [TASK-20260728T115500-token-path-e2e](./test-runs.d/TASK-20260728T115500-token-path-e2e.md)
  — **Bearer 토큰 경로 라이브 e2e (배포 fe6d3700), 15/15 PASS**. `bootstrap_admin` 단수명 토큰으로
  수행(사용자 지시) → 관리 엔드포인트 3종 **403** 실증(관리자 계정 토큰이어도 절대 denylist 가
  차단) · 폴더 지침/제품/첨부/ask 전 축 반영 · revoke 후 401 · 토큰 폐기 완료.

## 4. Untested Areas
- **MCP 서버 프로세스 왕복** — `mcp` SDK 가 agent 이미지에 없어 tool 등록·stdio 왕복 미수행.
  서버가 호출하는 HTTP 계약은 토큰 e2e(첨부 multipart 포함)로 전부 실증됐으므로 잔여 위험은
  SDK 배선 레이어에 한정.
- 전용 **저권한 서비스 계정** 기반 운영 검증 — 계정 신설은 운영 결정(현재 e2e 는 `bootstrap_admin`
  단수명 토큰으로 대체, 검증 후 폐기).
- 다수 동시 토큰 요청 부하(quota 상속으로 커버, 별도 부하테스트 없음).
