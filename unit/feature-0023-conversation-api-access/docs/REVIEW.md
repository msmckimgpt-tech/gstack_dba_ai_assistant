---
doc_type: REVIEW
feature_id: feature-0023-conversation-api-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260722-0001
- Related Change: CHG-20260722-0001 (Bearer API 토큰 인증 + MCP 서버)
- Reason: 외부 AI 가 대화 API 를 프로그램으로 쓰게 하되, 관리 콘솔은 접근 불가하게 한다.
  세션 쿠키는 사람용(브루트포스 잠금·TOTP·세션 만료)이라 봇에 부적합.
- Alternatives Considered:
  - Alt-A(쿠키 재사용): 코드 0이지만 봇에 취약·revoke 불가 → 기각(ANCHOR §2).
  - Alt-B(관리 콘솔 토큰 UI): 사용자 "콘솔 제외" 요구 → CLI 발급으로 대체.
  - scope 모델: 권한맵 전체 교집합을 `_account_permissions` 단일 choke-point 에 배치.
    `_account_has_product_access` 도 이 경유이므로 데이터 접근까지 일관 적용됨을 확인 →
    scope 기본에 `product.access.` 포함(그래야 chat 이 datasource 접근 가능).
- Risks:
  - 인증 신설(Critical, SECURITY §3) — 인증 우회·과권한 노출 위험. 완화: fail-closed,
    scope 교집합 단일 choke-point, 해시 저장, 파라미터라이즈드 쿼리, 쿠키 우선 무회귀.
  - 서비스 계정이 과권한이면 scope 가 2차 방어. 권장=전용 저권한 계정(문서화).
  - §18.8 적대적 보안 리뷰(security subagent) 수행 — 결과 아래 append.
- Open Questions: 셀프서비스 발급 엔드포인트 도입 여부(후속).
- Human Approval Needed: Plan 승인 완료(2026-07-22, entry arg-given dispatch). 배포는
  deploy_scope: included 로 사전 승인.

## REV-20260722-0002 [SUBAGENT:security] §18.8 적대적 보안 리뷰
- Related Change: CHG-20260722-0001
- 리뷰 결과: 인증 파이프라인(위조/만료/폐기/injection/fail-open-on-exception)은 견고.
  쿠키 우선 무회귀·파라미터라이즈드 쿼리·토큰 원문 미노출 확인. **인가(scope) 층 결함 2건 적발**.
- **HIGH-1 (scope-escape)**: `conversation.` prefix allowlist 가 `conversation.list.any`·
  `conversation.archive.read.any`(group=audit, 관리 콘솔 '감사>보관 대화' 엔드포인트
  `GET /api/admin/conversations/archived`) 등 모든 교차계정 `*.any` 권한을 통과시킴 →
  privileged 계정 바인딩 시 "관리 콘솔 제외" 보증 붕괴.
  - **조치(수정 완료)**: `_account_permissions` 에 scope·계정권한 무관 **절대 denylist**
    (`_api_token_permission_denied`) 추가 — api_token 인증은 `*.any` + 관리 네임스페이스
    (`console./audit./account./role./system./quota./insight./datasource./metadata./kb./graph./
    product.manage|read|create|delete`)를 무조건 effective=False. allowlist 통과해도 봉인.
- **HIGH-2 (fail-open)**: 빈/NULL Scopes = 무제한 → privileged 계정 시 전체 관리 API 개방.
  - **조치(수정 완료)**: scope=None 이면 무제한이 아니라 **안전 기본 allowlist**
    (`conversation.,product.access.`) + denylist 적용(fail-closed). CLI 도 빈 scope 를
    안전 기본값으로 명시 저장하고 admin scope 입력을 거부.
- **MEDIUM-1 (관습 의존)**: CLI 가 admin 계정에도 발급, admin scope 입력 허용.
  - **조치(수정 완료)**: CLI `_validate_scopes`(관리/`.any` scope 거부) + `_warn_if_privileged`
    (admin/operator/dba 역할 계정 경고). 런타임 denylist 가 최종 구조적 보증.
- **LOW**: revoke-by-prefix UNIQUE 부재(과폐기 fail-safe 방향)·LastUsedAt commit 없음
  (LastSeenAt 동일 패턴, 관측 정확도만). 수용(보안 무관).
- 안전 확인: 쿠키 병존 강등 없음·SQL injection 없음·토큰 원문 누출 없음(리뷰어 3중 확인).
- 재검증: HIGH-1/HIGH-2 수정 후 host 15 assertion PASS(`conversation.*.any` 차단·scope=None
  fail-closed) + 단위 테스트 `test_cross_account_any_blocked_despite_conversation_scope` 추가.

## REV-20260722-0003 [SKIPPED:non-code-hotfix] 발급 CLI 서비스명 hotfix
- Related Change: CHG-20260722-0002 (`bin/api-token-issue.sh` 서비스 자동감지)
- [SKIPPED] 사유: 인증/scope 로직 무변경 — 호스트 CLI 가 실행 컨테이너 서비스명을 `web` 로
  하드코딩해 무중단 배포(web-a/web-b)에서 실패하던 **운영 편의 결함**만 수정(패널 대상 아님).
  인증·scope 코어는 라이브 e2e(토큰→/api/ask 200·admin 403·무토큰 401)로 이미 실증됨.
  서비스 감지 로직은 `docker compose ps --status running` 화이트리스트 순회로 injection 무관.

## REV-20260724-0004 [SUBAGENT:data-leak·conversation-only·openapi-disable·admin-gate·path-traversal·base_url §18.8] API 발견 진입점
- Related Change: CHG-20260724-0003
- Reason: 외부 AI 발견성 요구(사용자) — 익명 발견 자료 + openapi 익명 노출 차단. 신규 익명 표면이라
  §18.8 보안 리뷰 필수(SECURITY §7).
- Alternatives Considered: (a) 익명 static contract 발견(채택, 사용자 결정) vs 토큰 게이트.
  (b) openapi 익명 차단(채택, 사용자 결정) vs 유지. 매니페스트 카탈로그는 자동 introspection 대신
  수기 정본(admin 유출 방지).
- Risks: 익명 데이터 누출·매니페스트 admin 노출·base_url(Host) 반영 오염·path traversal·admin_openapi
  게이트 우회. → §18.8 리뷰(아래 결과 append).
- §18.8 적대 보안 리뷰: (general-purpose subagent, 6렌즈 — 결과 append 예정).
- Open Questions: 없음.
- Human Approval Needed: 사용자 결정(익명 static + openapi 차단) 완료. deploy_scope: included → 배포 자동.

### §18.8 적대 보안 리뷰 결과 (general-purpose subagent, 6렌즈) — REV-20260724-0004 append
- **판정: BLOCK/HIGH/MEDIUM 결함 0.** 익명 발견 표면 견고. 6점검 전부 PASS(실증 포함):
  - #1 데이터 누출 0: 매니페스트는 수기 dict, 유일 런타임값 base_url 은 TrustedHostMiddleware 가
    off-allowlist Host 를 400 거부(실증). X-Forwarded-Host 미반영. llms.txt/guide 는 정적·데이터 0.
  - #2 conversation-only: `_CONVERSATION_ENDPOINTS` 수기 리터럴(admin 없음), `openapi()` 호출은
    admin-gated 라우트 1곳뿐(repo-wide grep 확인).
  - #3 openapi 비활성화 완전: /openapi.json·/docs·/redoc·/docs/oauth2-redirect 전부 404(실증),
    app.openapi()는 admin 라우트에서 정상 동작.
  - #4 admin_openapi fail-closed: console.access 필요, 토큰은 denylist(`console.`)로 구조적 차단.
  - #5 static 서빙 traversal 불가(고정 파일명).
  - #6 SECURITY §7 정합(4개 등재 + openapi 비활성 명시).
- **LOW(수정 반영)**: base_url 안전이 non-wildcard WEB_ALLOWED_HOSTS 전제 → `_manifest` 에 주석 1줄 추가.
- **LOW(수용)**: 발견 텍스트가 bin 스크립트·matk_ prefix·스코프 모델 노출 — 비밀 아님·AI 발견 의도·LAN 전제.
  공개 인터넷 노출 시 §7.2 IP allowlist/noindex 가 lever.
- 재검증: 계약·불변식 테스트 6 passed(컨테이너) + 라이브 발견 검증(배포 후).

## REV-20260724-0005 [SUBAGENT:openapi-conversation-only·data-leak·contact-env·doc정확성·엔드포인트정확성 §18.8] 발견 검증 후속(가이드+OpenAPI)
- Related Change: CHG-20260724-0004
- Reason: URL-only blackbox 검증(서브에이전트)에서 발견·학습 성공 확인 + 실통합 공백 5건 지목 →
  가이드 정확화 + 기계판독 OpenAPI 신설(사용자 "문서 + 기계판독 스키마" 결정).
- Alternatives Considered: OpenAPI 를 (a) 수기 conversation-only(채택, admin 유출 방지·§7.1 불변식 정합)
  vs (b) app.openapi() 필터링(admin 유출 위험). 토큰 연락처는 env 반영(운영자 설정, 기본 placeholder).
- Risks: openapi 가 관리 경로 광고·데이터 누출·base_url 오염·contact injection. → §18.8 리뷰(아래 append).
- §18.8 적대 보안 리뷰: (general-purpose subagent, 5렌즈 — 결과 append 예정).
- Human Approval Needed: 사용자 "문서 + 기계판독 스키마" 결정 완료. deploy_scope: included → 배포 자동.

### §18.8 적대 보안 리뷰 결과 (general-purpose subagent, 5렌즈) — REV-20260724-0005 append
- **판정: BLOCK/HIGH/MEDIUM 결함 0.** 5점검 전부 PASS(paths 실열거·소스 추적):
  - openapi 스펙 conversation-only 수기 dict(app.openapi() 미사용; paths 8개 전부 conversation, admin 0).
    app.app.openapi()(admin 포함)는 admin_openapi(console.access) 1곳에만.
  - 데이터 누출 0: 유일 런타임값 base_url(TrustedHost non-wildcard 보호, 이전 cycle 동일). 예제
    (executed_sql 등)는 전부 하드코딩 fake literal.
  - AI_API_TOKEN_CONTACT env 는 JSON 으로만 방출(HTML/JS 렌더 없음) → injection sink 아님. 기본 placeholder 무해.
  - 문서 변경은 기존 노출 사실 재진술(신규 비밀 0). 8 엔드포인트 전부 실재·conversation-scoped·owner-or-member 게이트.
- **LOW(수정 반영)**: auth.contact 가 익명 공개 → 운영자는 팀/역할 채널 사용 권장. `_TOKEN_CONTACT` 주석+placeholder 에 명시.
- 재검증: 계약·불변식 8 passed(컨테이너) + 라이브 curl + URL-only blackbox 재검증(배포 후).

## REV-20260728T103500-ai-claude-conversation-quality-controls (판단 근거)
- Related TASK: feature-0023-conversation-api-access (TASK-0014~0021)
- Timestamp: 2026-07-28T10:35:00+09:00
- Context: 사용자 요청 "대화의 품질도 외부 AI 작업자가 조정 — 모델, 추론 강도, 제품, 그 외".
  범위는 사용자 선택으로 최대(첨부 + 폴더 커스텀 지침, scope 확장 포함).

### 무엇이 실제 간극이었나 (조사 결과)
`model`·`reasoning_level` 은 이미 `/api/ask` body 계약이었고 가이드·OpenAPI 에도 있었다. 없던 것은:
1. **제품 축의 발견 경로** — 조정은 가능했지만(신규 대화 ask 힌트 / 기존 대화 PATCH, scope 에
   `product.access.` 포함) 발견 자료 어디에도 없어 외부 AI 가 존재를 알 수 없었다.
2. **"내 토큰이 쓸 수 있는 값"** — 모델은 `model.access.<value>` RBAC, 제품은 `product.access.<key>`
   로 계정마다 다른데 익명 매니페스트는 "인스턴스 데이터 0"(SEC-20260724)이라 목록을 못 싣는다.
   → 외부 AI 가 값을 추측하다 400/403 을 맞는 구조.

### 결정과 대안
- **D1 capabilities 를 인증 계층에 신설 (채택)**. 대안 (a) 익명 매니페스트에 목록 포함 → §7 불변식
  (1) 위반, 사내 LAN 이어도 계정별 제품/모델 카탈로그를 익명 노출하는 건 정찰 표면. (b) 기존
  `/api/session`·`/api/api-vault/options` 재사용 안내만 → 두 곳에 흩어져 있고 폴더·첨부 축은 어디에도
  없으며, 응답이 웹 UI 부트스트랩 지향(제품 conn 배지 등)이라 AI-facing 계약으로 부적합.
  채택안은 신규 권한 코드 0(인증만) + 익명 매니페스트에 포인터만 두어 두 계층을 분리한다.
- **D2 표시-집행 정합 (채택)**: 목록 산출에 새 판정 로직을 쓰지 않고 선택기와 **같은 함수**
  (`_filter_models_for_account_access`·`_filter_products_for_account_access`)를 재사용. 새 로직을
  두면 capabilities 가 보여준 값을 `/api/ask` 가 403 하는 불일치가 생긴다(model-access-rbac 도입
  때 선택기/게이트를 함께 닫았던 것과 같은 이유).
- **D3 ask 의 제품 힌트 계약 불변 (채택)**: 기존 대화 per-request override 를 넣지 않는다 —
  대화 제품 변경은 `PATCH …/product` 단독 진실(TASK-0047 race 가드 / ADR-WEB-0006, in-flight run 은
  enqueue 시점 캡처로 보호). MCP `ask` 에 기존 대화 + 제품 인자가 오면 조용한 무시 대신 명시 오류로
  안내해, 계약을 문서가 아니라 **동작으로** 알린다.
- **D4 토큰 안전 기본 scope 에 `folder.` 확장 (채택, 보안 경계 변화)**: 폴더 커스텀 지침이 품질
  축이라 사용자가 최대 범위를 선택. 안전 근거 — `folder.*` 는 `folder.list.own`/`folder.manage.own`
  둘뿐이고 모두 `.own`(feature-0024 privacy 슬라이스가 `folder.*.any` 를 폐지·restore IDOR 봉인),
  스토어가 owner-scope 강제. **절대 denylist 는 손대지 않아** `.any`·관리 네임스페이스는 그대로
  차단되고, `folder.*.any` 가 되살아나도 토큰 경로는 막힌다(단위 테스트로 고정). 대안 (a) 확장 없이
  폴더 축 제외 → 사용자 결정과 어긋남. (b) 신규 전용 scope 문자열 도입 → 권한 코드와 scope 의
  1:1 대응이 깨져 추론이 어려워짐.
- **무회귀 설계**: 확장은 **Scopes 가 비어 있는 토큰**의 기본값에만 적용된다. 이미 발급된 토큰은
  `conversation.,product.access.` 가 저장돼 있어 폴더 축이 닫힌 채 유지되고, 열려면 재발급이
  필요하다 — 기존 토큰의 권한이 소급 확대되지 않는다(테스트
  `test_legacy_token_without_folder_scope_is_unchanged`).

### Risks
- capabilities 가 계정별 인스턴스 데이터를 반환 → **익명 노출이면 정찰 표면**. 완화: 인증 필수 +
  익명 401 회귀 테스트, 매니페스트에 값 미포함 테스트(`"claude-" not in blob`).
- `conversation_id` 파라미터가 타 계정 대화 설정 oracle 이 될 수 있음. 완화: 접근 게이트 통과 시에만
  설정 반환, 실패 시 필드 자체를 싣지 않음(회귀 테스트).
- scope 확장이 의도보다 넓은 표면을 열 위험. 완화: `.own` 2개 한정 + denylist 무변경 + 관리
  네임스페이스 비노출 테스트.
- 발견 자료(수기 정본)와 실제 계약의 drift. 완화: 큐레이션 OpenAPI 의 `$ref` 정의 존재·admin 경로
  부재·guide 키워드를 테스트로 고정.
- **미해소(수용)**: capabilities 는 읽기 전용이라 자체 위험은 낮으나, 제품·폴더 목록이 서비스 계정
  권한 구성을 드러낸다(사내 LAN + 인증 전제에서 수용). per-token rate limit 부재는 기존 이월 항목.

## REV-20260728T111500-ai-claude-conversation-quality-controls [SUBAGENT:security] — CONCERN(수정 완료 → PASS)
- Related TASK: feature-0023-conversation-api-access
- Trigger: auth/token/scope·API/endpoint keyword matched (인증·인가 경계 변경 + 신규 엔드포인트)
- Timestamp: 2026-07-28T11:15:00+09:00
- Verdict: CONCERN → 적발 1건 in-cycle 수정 후 **PASS**
- Artifact: 본 entry 에 인라인(아래) — 채널 제약으로 별도 artifact 파일 없음(사유 하단)
- Human Approval Needed: no (scope 확장 범위는 사용자가 사전 결정)

### 검증 채널 (AGENTS.md §18.8.2 — 상위 우선순위 지시 carve-out 적용)
본 세션에는 **"사용자 요청 없이 Agent tool 을 호출하지 말라"** 는 상위(하네스/개발자 수준) 도구
제약이 있다. §18.8.2 는 이 경우 그 지시가 우선하며 본 §를 우회 근거로 쓰지 말라고 규정하므로,
subagent panel 대신 **제약 없는 채널**로 검증했다:
- built-in `/security-review` 스킬(가이드라인 로드) — 단, 스킬의 기본 실행 방식인 sub-task fan-out 은
  위 제약 때문에 쓰지 않고 **본 세션이 인라인으로** 5 카테고리(입력검증·인증인가·crypto/secret·
  injection/RCE·데이터노출) 를 diff 전수 대조.
- 기계적 점검: `py_compile` 3파일 · `bash -n` · cross-ref(§25.1 앵커 실재·ARCHITECTURE 역참조) ·
  전체 회귀 스위트.
- `[SKIPPED:tool-restricted:ux,design]` — UI 표면 변경이 없어 해당 도메인은 애초에 N/A.
  backend/qa 렌즈는 본 인라인 검증 + 회귀 스위트가 커버.

### 적발 (1건, in-cycle 수정)
- **[MEDIUM→수정] MCP 클라이언트 경로 세그먼트 미인코딩** —
  `conversation_mcp_server.py` 의 3개 tool 이 `urllib.parse.quote(conversation_id)` 로 URL 경로를
  조립했는데, `quote` 의 **기본 `safe='/'` 는 슬래시를 통과**시킨다. 실증:
  `quote("x/../../api/admin/openapi.json")` → 변형 없음. tool 인자는 이 MCP 서버를 구동하는 LLM 이
  채우고 그 입력에 신뢰할 수 없는 대화 내용이 섞일 수 있어(prompt injection), 클라이언트가 의도하지
  않은 엔드포인트를 때릴 수 있다.
  **영향 한정**: 서버측 인증·scope 교집합·절대 denylist 가 최종 방어선이라 **권한 상승은 불가**하고
  (관리 네임스페이스는 어떤 경로로 접근해도 차단), 호출자는 이미 토큰 보유자다 — 그래서 HIGH 가
  아니라 MEDIUM(클라이언트 측 경로 무결성).
  **수정**: `_path_seg()`(= `quote(..., safe="")`) 헬퍼 도입·3곳 전환. 회귀 게이트로
  `unit/feature-0023-conversation-api-access/tests/test_mcp_path_segment.py` 신설(ast 추출 —
  MCP 모듈은 `mcp` SDK+필수 env 때문에 bare import 불가, feature-0003 `test_perm_self_scope.py`
  동일 관용구). 이 테스트가 CI 에서 **실제로 돌도록** `make test` 수집 범위에 feature-0023 tests 를
  추가했다(그 전까지 이 feature 의 자체 테스트는 수집 대상이 아니었다 — 발견된 부수 공백).

### PASS 항목 (근거)
- **인증**: capabilities 는 `_get_authenticated_account` 후 계정 부재 시 **401**. 익명이 계정별
  인스턴스 데이터(모델·제품·폴더)를 얻는 경로 없음 — 회귀 테스트가 응답 본문에 모델/제품 문자열
  부재까지 검사.
- **scope 우회 없음(핵심 확인)**: capabilities 의 폴더·첨부 축 게이트는 `_account_has_permission`
  → **`_account_permissions`**(scope 교집합 + 절대 denylist) 를 탄다. 따라서 `folder.` scope 없는
  토큰은 서비스 계정이 `folder.list.own` 을 보유해도 `available:false` 이고 목록이 은닉된다.
  (raw `account["permissions"]` 직접 읽기였다면 read-path 우회였을 지점 — 코드 경로 확인 완료.)
- **교차계정 oracle 없음**: `conversation_id` 는 `_account_can_access_conversation` 통과 시에만
  설정을 싣고, 실패 시 존재/부재 구분 없는 동일 메시지(`접근할 수 없는 대화입니다.`)만 반환.
- **scope 확장의 표면**: `folder.*` 는 `.own` 2개뿐(`folder.*.any` 는 feature-0024 에서 폐지),
  denylist 무변경이라 `.any`·관리 네임스페이스는 그대로 차단. 확장은 **빈 scope 토큰의 기본값**에만
  적용되어 기존 발급 토큰은 권한이 소급 확대되지 않는다(테스트로 고정).
- **익명 static contract 불변식**: 매니페스트에 값 목록이 실리지 않음을 테스트로 강제
  (`"claude-" not in blob`), 큐레이션 OpenAPI 에 `/api/admin` 부재 재확인.
- **injection/secret**: 신규 SQL 0(기존 helper 재사용), `eval`/역직렬화 0, 첨부 multipart 는
  `secrets` boundary + filename 의 CR/LF/따옴표 제거(헤더 injection 차단), 토큰은 로그·에러 메시지에
  미노출(기존 계약 유지). `folder_id` 등 수치 path 파라미터는 `int()` 강제.

### 잔여 리스크 (수용)
- capabilities 는 인증된 토큰에게 그 계정의 제품·폴더 구성을 드러낸다 — 사내 LAN + 인증 전제에서 수용.
- 신규 MCP tool 의 실서버 왕복(특히 multipart 업로드)은 배포 후 라이브 검증 대상.
