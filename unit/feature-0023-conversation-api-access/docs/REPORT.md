---
doc_type: REPORT
feature_id: feature-0023-conversation-api-access
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
외부 AI 프로그래매틱 접근용 **Bearer API 토큰 인증** + **Conversation API MCP 서버** + **외부 AI
발견 진입점**(llms.txt·매니페스트·큐레이션 OpenAPI·가이드)을 제공한다. 세션 쿠키(사람용)와 별개로
저권한 서비스 계정에 귀속된 장수명 토큰으로 `/api/ask` 등 `conversation.*` 를 호출하고, scope
allowlist 위에 절대 denylist 를 얹어 관리/콘솔·교차계정을 원천 차단한다.

**2026-07-28 — 대화 품질 조정(conversation-quality-controls)**: 외부 AI 가 답변 품질 5축을
직접 조정한다 — 모델 · 추론 강도 · 제품(데이터소스 스코프) · 폴더 커스텀 지침 · 첨부. 조정 값이
계정 권한에 따라 다르므로 인증 필수 `GET /api/ai/capabilities` 가 "이 토큰이 실제 쓸 수 있는 값"을
라이브로 알려주고, 익명 발견 자료에는 그 포인터와 축 계약만 실어 "익명=static contract" 불변식을
지킨다. MCP tool 은 11종(대화 4 + 품질 7)으로 확장됐다.

## 2. Progress
- Planned: 배포 후 라이브 e2e(capabilities 조회 → 제품/폴더 지침 조정 → ask 반영).
- In Progress: 적대 검증 → verify-completion → PR → 배포 (TASK-0021).
- Done: Phase 1(인증·scope·CLI) + Phase 2(MCP) + 발견 진입점 + **품질 조정 표면**(TASK-0014~0020).

## 3. Recent Changes
- WebApiTokens 스키마 + fast/slow path 등록 (해시 저장, scope, 만료, revoke, LastUsedAt).
- `_get_authenticated_account` Bearer fallback + `_get_account_by_api_token`(fail-closed).
- `_account_permissions` scope 교집합(단일 choke-point) + 절대 denylist — 관리·교차계정 차단.
- `bin/api-token-issue.sh` 발급/폐기/조회 CLI + WebAuditEvents 기록.
- MCP 서버 `conversation_mcp_server.py` + `bin/conversation-mcp.sh`(gated) + `.mcp.json` 등록.
- 발견 진입점 `llms.txt`·`/.well-known/ai-conversation-api.json`·`/api/ai/{manifest,guide,openapi.json}`.
- **(07-28) `GET /api/ai/capabilities`**(인증 필수·신규 권한 코드 0) + 매니페스트 `quality_controls`
  포인터 + 큐레이션 OpenAPI +6 path/+3 스키마 + 가이드 §4.7 + MCP tool +7 + 토큰 안전 기본 scope
  에 `folder.` 확장(denylist 무변경·기존 토큰 무회귀).
- 총 변경 횟수: 5 (CHG-20260722-0001·0002, CHG-20260724-0003·0004,
  CHG-20260728T103500-ai-claude-conversation-quality-controls)

## 4. Open Issues
- 라이브 e2e(실토큰 ask 왕복 · 품질 조정 반영)는 배포 후 수행.
- 기존 발급 토큰은 폴더 축이 닫혀 있다(저장된 scope). 폴더 지침을 쓰려면 **재발급** 필요 — 운영 안내 사항.

## 5. Test Status
- 신규·관련 39 passed (`test_ai_capabilities.py` 10 · `test_ai_discovery.py` 8 ·
  `test_api_token_auth.py` 21).
- 전체 회귀: **2586 passed / 2 skipped / 0 failed** (컨테이너, 71s). 보안 리뷰 수정 후 재실행
  (+ 신설 feature-0023 tests 7) 도 **exit 0 = 실패 0**.
- §18.8 보안 리뷰(REV-20260728T111500): MEDIUM 1건(MCP 경로 세그먼트 미인코딩) in-cycle 수정 →
  PASS. 회귀 게이트 `test_mcp_path_segment.py` 신설 + `make test` 수집 범위에 feature-0023 tests 추가.
- 의도적 기대값 갱신 2건: route 골든 스냅샷(+1 route), T9 필터 호출처 검증 강화(카운트→파일 집합).
- MCP smoke: tool 등록 + 런처 gated PASS. 신규 tool 은 실서버 왕복 미검증(배포 후).
- 미검증: 라이브 토큰 왕복·품질 조정 반영·MCP multipart 업로드.

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 운영자: 저권한 서비스 계정 + 토큰 발급(`bin/api-token-issue.sh`). **폴더 축을 쓰려면 기존 토큰
  재발급**(신규 기본 scope `conversation.,product.access.,folder.`).
- 인증 신설(Critical, 2026-07-22)·품질 조정 scope 확장(Major, 2026-07-28 사용자 범위 선택) —
  둘 다 승인 완료. §18.8 적대 보안 리뷰 반영.

## 8. Suggested Improvements
- 셀프서비스 토큰 발급 웹 엔드포인트(scope 제한) 후속 검토.
- 토큰 사용량 per-token rate limit(현재는 서비스 계정 quota 상속).
- 폴더 datasource/product 핀(feature-0024 Phase 2b)이 배선되면 품질 축에 편입 검토.
