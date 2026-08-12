---
doc_type: REVIEW
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260812-0001 [CODEX:plan-docs] — accepted

- Related Change: CHG-20260812-0001 (feature 신설 + 계획 산출물)
- Reason: AGENTS.md §18.8 검증 패널. 위험도 Critical(인증·인가 + 신규 데이터 유출면)이라
  security 렌즈 필수인데 세션에 Agent-tool 제약이 걸려 있어, feature-0030(2026-07-29 사용자
  확인) 선례대로 §18.8.2 정합 경로인 `/codex review` 를 채택했다.
- 실행: `codex exec -s read-only` + `git diff --cached` (첫 시도는 프롬프트 길이로 5분 게이트
  타임아웃 — 최소 프롬프트로 재시도 성공, 52,962 tokens). GATE: **FAIL (P1 3건)** → 전건
  in-cycle 수정 후 본 엔트리 기록.

### 지적 사항과 처리

1. **[P1] 원장 fail-open ↔ AC-6 모순** (FUNCTION.md §9)
   원장 기록 실패를 best-effort로 두면 호출이 누적 한도에서 누락돼 "모든 호출이 기록되고 상한
   초과 시 429"라는 AC-6과 충돌한다. → **수정**: 원장 기록·예산 차감을 **결과 반환 전 원자적
   커밋**으로 승격하고 실패 시 5xx(결과 미반환). 관측 전용 필드 결손만 best-effort 유지.
   완료 판정에 "기록 실패 주입 시 결과 미반환" 회귀 테스트 추가.

2. **[P1] OAuth 저장 계약 부재** (TASK.md §2.1)
   인가 코드 단회성·TTL, 토큰 해시 저장, refresh rotation/reuse 탐지, PKCE S256, redirect_uri
   결합이 계획·AC에 없었다. → **수정**: FUNCTION.md §3에 저장 계약 명시, `oauth_as.py` symbol에
   `_consume_auth_code`·`_rotate_refresh` 추가, `WebOAuthTokens`(해시 컬럼만) 신설,
   **AC-10** 신규.

3. **[P1] DCR redirect URI 정책 부재** (FUNCTION.md §3)
   "AI가 스스로 등록"이 결정사항이라 DCR이 열려 있는데 URI 제약이 없어 인가 코드 탈취·피싱
   표면이 생긴다. → **수정**: HTTPS 고정(loopback 예외)·정확 일치·등록 rate limit 명시,
   **AC-11** 신규.

4. **[P2] AC-5 과대 약속** (교차오염 탐지)
   외부 AI가 값을 요약·환산·재서술하면 출처를 결정론적으로 판별할 수 없다. → **수정**: AC-5를
   **명시적 유출 신호**(라벨·`task_id`·카나리·원문 그대로의 값)로 한정하고 **미탐 허용**을
   문면에 명시. 테스트는 "명시적 유출 양성 / 정상 답변 음성"만 단정.

- Alternatives Considered: 지적 4건 모두 계획 문서의 실질 결함이라 이월 없이 in-cycle 수정.
  P2는 문면 한정으로 처리(탐지 로직을 더 정교하게 만드는 선택지는 비용 대비 효과가 낮고,
  ANCHOR §1이 이미 "완전 격리 불가"를 방향으로 못박고 있어 정합).
- Risks: 본 cycle 산출물은 계획 문서뿐이라 런타임 위험 0. 구현 위험은 §2.1 위험도 Critical에
  귀속되며, 특히 (a) 도구 스코프 ContextVar → 명시 인자 승격이 내부 대화 경로에 회귀를 낼 수
  있고 (b) OAuth AS는 신규 인증 표면이라 §18.8 보안 렌즈를 구현 cycle에서 다시 받아야 한다.
- Open Questions: 없음 (2026-08-12 대화로 신원/비용 2축·동시 세션 허용·검증 이관 범위·인젝션
  처리·전송 2종·대화 기록 보존·context_depth 전부 확정).
- Human Approval Needed: **예** — §7.1 Critical. TASK.md §2.1에 `PLAN-APPROVED` 마커가
  부여되기 전까지 구현 착수 금지(§5 BLOCKED 등재).


## REV-20260812-0002 [CODEX:implementation] — accepted

- Related Change: CHG-20260812-0002 (P0 구현)
- Reason: §18.8 security 렌즈. 계획 리뷰(REV-0001)는 **문서**에 대한 것이라 코드 리뷰를
  대체하지 않는다 — 배포 전 필수라고 스스로 적어 둔 항목을 같은 cycle 에서 이행했다.
- 실행: `codex exec -s read-only` + `git diff --cached -- '*.py'`. GATE **FAIL (P1 2건)** →
  4건 전부 in-cycle 수정 + 회귀 테스트 5건 추가.

### 지적 사항과 처리 — 전부 MCP 어댑터(클라이언트 측)에 집중

1. **[P1] Bearer token 이 평문/MITM 에 노출** — `BASE_URL` 의 https 미검증 + TLS 검증 끄기 허용.
   → `_require_https()` 신설(https 강제, loopback 만 예외, 위반 시 fail-loud SystemExit).
   검증 끄기는 사내 self-signed 현실 때문에 남기되 **`EXT_TOOL_CA_BUNDLE`(사설 CA)** 을 권장
   경로로 추가하고, 끄면 stderr 경고를 낸다. 회귀 테스트 2건.
2. **[P1] `LABEL` 이 선택이라 L1 격리가 무력화** — 라벨 없는 두 계정 인스턴스가 **같은 tool
   이름**을 갖는다. 세션 격리의 유일한 물리적 gate 가 선택 사항이었다.
   → `_require_label()` 로 **필수화** + charset/길이 검증(`[A-Za-z0-9_-]{1,32}`).
   `_name()` 의 `if LABEL else` 분기 제거. 회귀 테스트가 그 분기의 부활을 막는다.
3. **[P2] 오류 본문이 각인 없이 tool 결과로 유입** — 성공 경로의 인젝션 gate 를 오류 경로로
   우회할 수 있다. → `_defang()` 으로 sentinel·`[SCOPE]` 제거 후 반환(HTTPError·일반 예외 양쪽).
4. **[P2] 응답 크기 무제한 `read()`** — 오동작·탈취된 endpoint 가 MCP 프로세스 메모리를 고갈.
   → `_MAX_BYTES`(기본 8MiB) 상한 + 초과 시 `response_too_large`.

- Alternatives Considered: (1)에서 "검증 끄기 옵션 자체를 제거" 도 검토했으나 사내 self-signed
  환경(CONTRIBUTING §10)에서 현실적으로 막힌다 — 대신 **올바른 경로(CA 지정)를 1급으로 만들고
  끄기는 경고와 함께 남기는** 절충. (2)는 절충 없이 필수화 — 선택으로 두면 격리가 사실상 없다.
- Risks: 지적 4건이 전부 **클라이언트 측 어댑터**였다는 점이 시사적이다 — 서버측 관문은
  단위 테스트로 두껍게 덮었는데 어댑터는 "얇은 래퍼" 라는 이유로 덜 봤다. 얇아도 토큰을 들고
  네트워크에 나가는 컴포넌트다.
- Open Questions: 없음.
- Human Approval Needed: **배포**는 사람 결정(외부 영향 + Critical). 라이브 e2e 미실시 상태.


## REV-20260812-0003 [SKIPPED:pre-deploy-hardening] — 배포 전 자체 점검 (패널 재호출 불요)

- Related Change: CHG-20260812-0003 (catchup 체인 보호)
- Reason: 라이브 배포 직전 `LEARNINGS.md` 의 반복 결함 목록을 이 변경에 대조하다 발견한
  **순수 방어 수정**이다. 새 기능·새 경로·새 노출면이 0 이고, 기존 함수의 try 경계만 넓혀
  예외가 `_ensure_seed_catchup` 로 새지 않게 한다.
- 발견 내용: `conn.cursor()` 가 try 밖 → 커서 획득 실패가 catchup 으로 전파 → 뒤따르는 6건
  (gdrive·아바타·첨부 버전·DB allowlist·**audit events**·**audit chain**)이 조용히 skip.
  `resource-acquire-outside-try` 는 LEARNINGS 에 **4 cycle 반복**으로 기록된 패턴이고,
  seed-catchup abort 는 별도 사례로 기록돼 있다 — 둘이 겹치는 자리였다.
- 판단: §18.8 패널 재호출을 하지 않는 근거 — (a) 변경이 `try:` 한 줄 이동 + except 추가이고
  (b) 방향이 항상 안전한 쪽(예외 봉인)이며 (c) AST 단정 7건으로 회귀를 고정했고 (d) 직전
  REV-0002 codex 리뷰의 대상 코드와 같은 파일이 아니다. 새 판단이 필요한 설계 변경이 아니다.
- Risks: 예외를 삼키므로 **테이블 생성 실패가 조용해진다.** 그 대가는 의도적이다 — 실패 시
  이 feature 의 엔드포인트가 fail-closed 로 막히고(도달면 0), 무관한 서브시스템은 살아남는다.
  배포 후 검증에서 4개 테이블 실재를 직접 확인해 이 침묵을 보완한다(POST-DEPLOY).
- Human Approval Needed: 아니오 (배포 자체는 `deploy_scope: included` 사전 승인 + 사용자
  2026-08-12 명시 지시).
