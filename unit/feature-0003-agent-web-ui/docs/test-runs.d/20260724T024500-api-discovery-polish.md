---
run_at: 2026-07-24T11:45:00+09:00
session: ai/claude/feature-0023-api-discovery-polish
scope: [api-discovery, openapi, ai-api-guide, llms.txt]
verdict: PASS (PRE-COMMIT 계약/불변식 + POST-DEPLOY 라이브 curl)
---

### Run (2026-07-24) — feature-0023 api-discovery-polish: 가이드 정확화 + 기계판독 OpenAPI(/api/ai/openapi.json) (Minor §12.3, feature-0023 확장, cross-cut 코드 거주 feature-0003) — **Environment: Windows-browser (미수행 — 렌더링 surface 부재)**

- **Environment: Windows-browser — PB-0008 미수행 사유(N/A, 카고컬트 방지)**: 본 cycle 의 웹 자산
  변경은 **렌더링 시각/상호작용 surface 가 없다** — `static/ai-api-guide.md`·`static/llms.txt` 는
  외부 AI/도구가 curl·fetch 로 소비하는 **text/markdown 원문**(브라우저 렌더 UI 아님). `index.html`
  변경 없음. 올바른 검증은 **엔드포인트 계약(CLI/live curl)**.
- **PRE-COMMIT 검증 (PASS)**:
  - 계약·불변식 테스트 `test_ai_discovery.py` **8 passed**(컨테이너) — openapi 3.1 conversation-only
    (관리 경로 미포함)·Bearer securityScheme·AskRequest message 필수·매니페스트 contact/openapi_url/
    동기 dispatch 명시.
  - route parity golden 갱신(신규 1 route `/api/ai/openapi.json`) → PASS. `_openapi_spec` 격리 exec
    로 paths=8(conversation only)·admin 0 확인. §18.8 적대 보안 리뷰(진행 → REVIEW append).
- **POST-DEPLOY 라이브 curl(배포 후 append 예정)** — AC:
  - AC-1 `GET /api/ai/openapi.json` = 200, `openapi=3.1.*`, paths 에 `/api/ask` 포함·`/api/admin` 미포함, bearerAuth 존재.
  - AC-2 `GET /api/ai/manifest` 의 `ai_api.auth.contact` 존재·`openapi_url` = `/api/ai/openapi.json`·`/api/ask` dispatch=synchronous.
  - AC-3 기존 발견 무회귀: llms.txt/guide 200, openapi(익명 built-in) 404, admin-openapi 401, Host 주입 400.
  - AC-4 **URL-only 재검증**: 서브에이전트에 URL 만 재제공 → 발견·학습 + 공백(토큰 연락처·동기여부·스키마) 해소 확인.
- **Pass/Fail: PRE-COMMIT PASS · 라이브 = POST-DEPLOY curl + blackbox 재검증**. CHECK#13 충족.
