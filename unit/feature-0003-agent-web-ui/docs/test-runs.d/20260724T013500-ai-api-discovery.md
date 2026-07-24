---
run_at: 2026-07-24T10:35:00+09:00
session: ai/claude/feature-0023-api-discovery
scope: [web-ui, api-discovery, llms.txt, well-known, openapi-disable]
verdict: PASS (PRE-COMMIT 계약/불변식 + POST-DEPLOY 라이브 curl)
---

### Run (2026-07-24) — feature-0023 api-discovery: 외부 AI API 발견 진입점(llms.txt/manifest/guide) + openapi 익명 차단 (Major §12.3, feature-0023 확장, cross-cut 코드 거주 feature-0003) — **Environment: Windows-browser (미수행 — 렌더링 surface 부재)**

- **Environment: Windows-browser — PB-0008 미수행 사유(N/A, 카고컬트 방지)**: 본 cycle 의 웹 자산
  변경은 **렌더링되는 시각/상호작용 surface 가 없다**. (1) `static/index.html` 변경 = `<head>` 안
  기계판독 `<link rel="ai-conversation-api">` + `<meta>` 발견 포인터 — **화면에 렌더되지 않음**(사용자
  가시 UI·상호작용 무변경). (2) `static/llms.txt`·`static/ai-api-guide.md` = 외부 AI/도구가 curl·
  fetch 로 소비하는 **text/markdown 원문**(브라우저 렌더 UI 아님). 따라서 실 Windows 브라우저 육안
  검증 대상이 없다 — 올바른 검증은 **엔드포인트 계약(CLI/live curl)**.
- **PRE-COMMIT 검증 (PASS)**:
  - 계약·보안 불변식 테스트 `test_ai_discovery.py` **6 passed**(컨테이너) — llms.txt/manifest/guide
    200·매니페스트 conversation-only(관리 엔드포인트 카탈로그 미포함)·openapi/docs/redoc 404·
    admin-openapi 무인증 게이트·카탈로그 수기정본(introspection 아님).
  - route parity golden 갱신(신규 5 route) → `test_route_parity_p5b.py` PASS. feature-0003 회귀 0
    (사전 실패 4건 동일). §18.8 적대 보안 리뷰(general-purpose, 6렌즈) **BLOCK/HIGH/MEDIUM 0**
    (base_url 은 TrustedHostMiddleware 가 off-allowlist Host 400 거부·실증; 데이터 누출 0).
- **POST-DEPLOY 라이브 curl 검증(배포 후 append 예정)** — AC:
  - AC-1 `GET /llms.txt` = 200 text, "Conversation API"·"Bearer" 포함.
  - AC-2 `GET /.well-known/ai-conversation-api.json` = 200 JSON, `ai_api.auth.scheme=Bearer`,
    endpoints 에 `/api/ask` 포함·`/api/admin` 미포함.
  - AC-3 `GET /api/ai/manifest` = 200(동일), `GET /api/ai/guide` = 200 markdown.
  - AC-4 `GET /openapi.json`·`/docs`·`/redoc` = 404(익명 차단).
  - AC-5 `GET /api/admin/openapi.json` 무인증 = 401.
  - AC-6 `Host: evil.example` 주입 → 400(TrustedHost 거부, base_url 오염 불가).
- **Pass/Fail: PRE-COMMIT PASS (계약·불변식·보안리뷰) · 라이브 = POST-DEPLOY curl**. CHECK#13
  충족(웹 자산 변경에 Windows-browser Run 라인 + 렌더 surface 부재 미수행 사유 + CLI 실검증 계획).
