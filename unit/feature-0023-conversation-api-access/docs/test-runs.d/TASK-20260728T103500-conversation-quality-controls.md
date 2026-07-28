---
run_at: 2026-07-28T11:05:00+09:00
session: ai/claude/conversation-quality-controls
scope: feature-0023-conversation-api-access (대화 품질 조정 표면)
verdict: PASS
---

# Run — conversation-quality-controls 단위·계약 검증

- Date: 2026-07-28
- Environment: `CLI` (서버 계약·단위 검증)
- Runner: AI (claude)
- Bridge: n/a

## Windows-browser 시각검증 미수행 사유 (§15.4.1)
본 cycle 은 **UI 표면을 변경하지 않는다**. `**/static/**` 경로 파일 2개를 건드리지만
(`static/ai-api-guide.md`·`static/llms.txt`) 둘 다 **외부 AI 가 읽는 텍스트/마크다운 계약 자산**
이며 브라우저에 렌더되는 화면(HTML/CSS/JS·템플릿)이 아니다 — `text/markdown`·`text/plain` 으로
서빙된다. 나머지 변경은 python 라우터·MCP 서버·bash CLI·문서다. 사람용 웹 화면(HTML/CSS/JS,
`templates/`)은 **무변경**이라 PB-0008 시각검증으로 확인할 픽셀이 없다. 대신 응답 계약을
`test_ai_capabilities.py` 의 guide/llms.txt 서빙 + 키워드 검증으로 고정했다.

## Evidence
- 신규/관련 테스트: `test_ai_capabilities.py`(10) + `test_ai_discovery.py`(8) +
  `test_api_token_auth.py`(21, folder scope 5 추가) → **39 passed**.
- 전체 회귀(컨테이너 `mysql-ai-agent:current`, `PYTHONPATH=…0002/src:…0003/src:/work`):
  `unit/feature-0002-agent-core/tests` + `unit/feature-0003-agent-web-ui/tests`
  → **2586 passed, 2 skipped, 0 failed** (71.21s).
- §18.8 보안 리뷰 수정 반영 후 재실행(위 2 디렉토리 + 신설 `unit/feature-0023-…/tests` 7):
  **exit 0 = 실패 0** (요약 라인은 컨테이너 파이프라인 캡처 실패로 미기록 — 판정 근거는 exit code).
- 조정된 기대값 2건(둘 다 의도적 변경):
  - `route_snapshot_p5b.json` 골든 — `/api/ai/capabilities` GET 1건 추가로 220→221 재생성.
  - `test_product_list_rbac.py::test_t9_filter_only_on_workspace_paths` — 필터 호출처 2→3
    (`ai_discovery.py` 추가). 카운트만 세던 검증을 **호출 파일 집합**(`{system,auth,ai_discovery}.py`
    + admin 접두 부재) 검증으로 강화 — 원래 의도("workspace paths only")를 더 직접 고정.
- 문법: `py_compile` (ai_discovery/web_context/conversation_mcp_server) OK, `bash -n`
  (api-token-issue.sh) OK.

## Covered cases
- TEST-20260728T103500-quality-controls-1 익명 401 + 응답에 모델/제품 문자열 부재.
- TEST-20260728T103500-quality-controls-2 5축 계약 + 계정 권한 필터 반영 + `set_via` 존재.
- TEST-20260728T103500-quality-controls-3 권한 없는 축 `available:false` + 사유(조용한 빈 배열 금지).
- TEST-20260728T103500-quality-controls-4 접근 불가 `conversation_id` 설정 미노출(oracle 차단).
- TEST-20260728T103500-quality-controls-5 익명 매니페스트에 포인터만(값 목록 부재) + 큐레이션
  OpenAPI 6 path·3 스키마 존재·admin 경로 부재.
- TEST-20260728T103500-quality-controls-6 folder scope 확장이 `.own` 만 열고 `.any`/관리는 차단,
  기존 토큰 무회귀.

## §18.8 보안 리뷰 반영 (REV-20260728T111500)
- 적발 1건(MEDIUM, in-cycle 수정): MCP 클라이언트가 `urllib.parse.quote` 기본 `safe='/'` 로 경로를
  조립해 슬래시가 통과 → tool 인자 `conversation_id` 가 의도한 경로를 벗어날 수 있었다.
  `_path_seg()`(`safe=""`)로 3곳 전환 + 회귀 게이트
  `unit/feature-0023-conversation-api-access/tests/test_mcp_path_segment.py`(ast 추출, **7 passed**).
- 그 테스트가 CI 에서 실제로 돌도록 `make test` 수집 범위에 feature-0023 tests 추가
  (그 전까지 이 feature 자체 테스트는 미수집 — 리뷰 중 발견된 부수 공백).
- scope 우회 없음 확인: capabilities 의 폴더·첨부 게이트가 `_account_has_permission` →
  `_account_permissions`(scope 교집합 + 절대 denylist) 경로를 탄다(코드 경로 추적).

## 라이브 e2e (배포 ebedc256 후, 2026-07-28)
쿠키 인증(bootstrap_admin)으로 수행 — **전용 저권한 서비스 계정이 현재 0건**이라 토큰 발급 경로는
미수행(계정 생성은 운영 결정). 토큰 인증 자체는 이전 cycle 라이브 e2e 로 검증됐고, 이번 변경의
토큰 관련 부분(folder scope)은 단위 테스트로 고정.

| 검증 | 결과 |
|---|---|
| `/livez` | 200 |
| `GET /api/ai/capabilities` **익명** | **401** `로그인이 필요합니다.` (인스턴스 데이터 무노출) |
| 익명 매니페스트 `quality_controls` | `discover` 포인터 + 5축, **모델 카탈로그 미포함** 확인 |
| 인증 capabilities | 200 · 5축 전부 · 모든 축 `set_via` 보유 |
| 모델 목록 | 3건(계정 권한 필터 적용) · `supports_thinking` 동반 · default `claude-haiku-4` |
| 제품 목록 | 16건 · `default_product_id=109` · modes `[auto, pinned]` |
| 폴더 축 | `available=true` · `max_depth=4` |
| 폴더 생성 + 지침 | 200 · capabilities 에 지침 그대로 노출 |
| 대화 폴더 배정 | 200 |
| `PATCH …/product` (pinned 7) | 200 · capabilities `conversation` 에 반영 |
| `POST /api/ask` (model+reasoning_level) | 200 · 17.2s · error 없음 |
| 접근 불가 `conversation_id` | 설정 미노출(동일 메시지, oracle 차단) |

**적발 → 핫픽스(CHG-20260728T115000)**: `conversation.model` 이 항상 `null`. 모델 KV 는 계정별
`model:<account_id>` 인데 대화 단위 `"model"` 로 읽었다. 단위 테스트가 같은 오해로 stub 을 주입해
통과했던 부류(§16.3 proxy≠ground-truth) — 음성 케이스 회귀 테스트로 봉인.

## Untested (배포 후)
- **토큰 경로** e2e — 저권한 서비스 계정 확보 후(운영 결정) 수행.
- MCP tool 실서버 왕복(`list_capabilities`·`upload_attachment` multipart).
