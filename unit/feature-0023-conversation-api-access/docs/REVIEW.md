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
