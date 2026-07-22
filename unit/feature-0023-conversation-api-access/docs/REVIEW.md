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
