---
doc_type: REPORT
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 1. 현재 상태

**in-progress — P0 + 잔여 3건 완료 · 라이브 배포 `e1372f32` · POST-DEPLOY 3회 전건 PASS.**

남은 것은 콘솔 탭(사용자 결정으로 별도 cycle)과 사람 1회 인가가 필요한 전 구간 e2e 뿐이다.

계획 승인(`PLAN-APPROVED` 2026-08-12) 후 P0 를 구현했다. 신규 route 8개는 전부 OAuth 토큰 뒤에
있고, **라이브에 배포되지 않았으므로 현재 도달면은 0** 이다. 기존 경로는 무변경이다 —
`modules/tools.py` 미수정, feature-0023 `ask` 축 무변경, 내부 대화 경로는 새 authz seam 을 거치지
않는다.

## 2. 산출물 (구현)

| 층 | 파일 | 요지 |
|---|---|---|
| 스키마 | `alembic 0055` · `_bootstrap_schema._ensure_oauth_client_schema` | `tool_call_usage`(PG 부하 원장) + `WebOAuthClients/Grants/Tokens` + `WebAiTasks` |
| 보안 코어 | `src/session_guard.py` | L2 각인 · L3 교차오염 탐지(명시 신호 한정) · 인젝션 3단 판정 |
| 보안 코어 | `src/tool_authz.py` | 계정 RBAC → 제품 교차검증 → 라우터 · ContextVar 누수 방지 |
| 보안 코어 | `src/oauth_store.py` | 코드 1회용 · 3요소 결합 · PKCE S256 · rotation/reuse 계열 폐기 · 세션 결합 |
| 보안 코어 | `src/tool_ledger.py` | 기록/조회 실패 = 거절(fail-closed) · 상한 3종 |
| REST | `routers/oauth_as.py` · `routers/ai_tools.py` | DCR·authorize·token·revoke / P0 도구 9종 |
| 어댑터 | `src/external_tool_mcp_server.py` | stdio MCP · 라벨 필수 · https 강제 · 응답 상한 |
| 테스트 | `tests/*` 5파일 | **94건** green |

## 2.1 계획 cycle 산출물

- `docs/ANCHOR.md` — §1 방향(추론 주체 반전의 이유·2축 신원/비용) · §2 대안 4개(0023 확장 /
  BYOK / 구독 토큰 보관 / 역방향 MCP) · §3 시나리오 1개
- `docs/FUNCTION.md` — REQ 1건 · In Scope(P0) · Out of Scope(P1~P3·영구 제외) · AC **11건**
- `docs/TASK.md` §2.1 — 파일·symbol 표 13행 · 접근 7단계 · 완료 판정 11항 · 위험도 Critical
- `docs/REVIEW.md` — REV-20260812-0001 [CODEX:plan-docs]
- `docs/MODIFY.md` — CHG-20260812-0001
- `wiki/Features/feature-0041-external-ai-tool-surface.md` — 사람용 입구 카드
- `unit/feature-0023-conversation-api-access/docs/ANCHOR.md` §1 — 방향 분기 문단
  (0023 은 `ask` 축 유지, 원시 도구 축은 0041 로 분리)
- `docs/STATUS.md` — feature 행 추가

## 3. 검증

- 단위 테스트 **94건 green** (session_guard 25 · tool_authz 15 · oauth_store 37 · tool_ledger 10 ·
  mcp_adapter 12 — 뒤 두 자릿수는 codex 수정 회귀 포함). 기존 스위트(0002/0003/0023) 무회귀.
- `bin/migrate-lint.sh` PASS (0055 expand-safe · head 단일).
- `verify-completion.sh --pre-commit` PASS.
- **§18.8 패널 2회**: REV-0001(계획, P1 3건) · REV-0002(구현 코드, P1 2건+P2 2건) — 전건 in-cycle
  수정. 구현 리뷰의 지적이 **전부 클라이언트 어댑터**에 몰렸다는 점을 REVIEW.md 에 기록했다.
- **라이브 배포 완료** `a68fbbac` — 무중단 실측 0건, 서비스 4종 커밋 일치, POST-DEPLOY 12항
  PASS(TEST.md §3). 무토큰 401 · DCR 201 · 비-HTTPS redirect 400 · 미로그인 authorize 302→/login
  · 기존 경로 200 전부 확인.
- ⚠ **인증된 전 구간 e2e 는 미검증** — 인가 코드 발급에 사람 브라우저 로그인·동의가 필요해
  자동 probe 로 대체할 수 없다(설계상 의도). "외부 AI 가 등록→인가→토큰→도구→제출 을
  완주한다" 는 **사람이 한 번 통과시켜야 확정**된다.
- 배포 1차 실패 1건(모듈이 이미지에 미포함) — 근본 수정 + 회귀 게이트 추가. 사용자 영향 0.

## 3.1 2차 출하 (2026-08-12, `e1372f32`)

발견 자료 · L4 권한 비대칭(원장 전용) · HTTP/SSE 전송. codex 리뷰 P1 3건·P2 2건 전건 수정 —
가장 무거운 것은 **L4 의 교차 테넌트 노출**이었다(OAuth `client_id` 를 "머신 식별자" 로 가정한
내 전제가 틀렸다 — DCR 로 누구나 받는 앱 식별자라 공유 가능하다). 응답에서 제거하고 원장
전용으로 내렸다. 테스트 136건, POST-DEPLOY 8항 PASS.

## 3.3 3차 출하 후속 (2026-08-13, `feadc089`)

기동 실패 3중 원인(이미지 의존 · SDK 2.0 · TLS upstream)과 콘솔 오배치를 잡았다. 두 결함 모두
**"머지·배포 성공" 이후에 라이브를 직접 보고서야** 드러났다 — 하나는 컨테이너가 안 떴고,
하나는 화면에 있긴 한데 엉뚱한 패널에 있었다. 문서는 두 경우 모두 **되기를 바라는 상태**를
적고 있었고, 그게 이번 cycle 의 가장 큰 교훈이다.

라이브 실측(엣지 경유): 익명 401 · initialize 200 · tools/list 9종 · 도구 호출이 검증된 TLS 로
web 에 도달(가짜 토큰 → 401). 콘솔: 전용 패널 4행 렌더, 타임아웃 패널에서 분리 확인(PB-0008).

## 4. 잔여 (BLOCKED 아님 — 다음 cycle)

- **인증된 전 구간 e2e** — 사람이 브라우저로 한 번 인가하면 확정된다(MCP 어댑터 env 3개 설정 후
  `open_task` → `describe_table` → `submit_answer`). 자동화 불가 구간.
- **관리 콘솔 '외부 도구 한도' 탭** — 사용자 결정으로 별도 cycle(admin.js 충돌 + PB-0008 게이트).
  상한은 이미 집행 중이라 기능 공백이 아니다.
- ~~HTTP/SSE 전송 프로세스 기동~~ — **완료**(2026-08-13). `ext-tool-mcp` 서비스 + 엣지
  `/api/ai/mcp`. 사용자는 URL + access token 만 등록하면 된다.

## 5. 알려진 한계 (정직 표기)

- 외부 AI 가 세션 A 의 데이터를 기억한 채 세션 B 에 **서술로** 답하는 경로는 차단·탐지 불가.
  각인·선언·대조는 "몰라서 섞임"을 제거할 뿐이며 "알고도 섞음"은 사후 탐지 대상이다.
- `submit_answer` 미호출은 강제할 수 없다(소프트 강제만 — 미제출률 노출 + 임계 초과 시 신규
  task 제한).
- 인젝션 방어는 SECURITY.md §14 와 동일하게 **확률적 완화**이며 보장이 아니다. 실 경계는
  RBAC·SQL guard·스코프 격리가 진다.
- 교차오염 탐지(AC-5)는 **명시적 유출 신호**에 한정되며 미탐을 허용한다(codex P2 반영).

## 6. Git

- 브랜치: `ai/claude/feature-0041-external-ai-tool-surface` (worktree
  `.worktrees/feature-0041-external-ai-tool-surface`, base `main` @ 6c4973e6)
- commit 완료. **PR 생성·머지는 계획 승인 후** — §16.5 예외("Critical 승인 대기가 REPORT.md 에
  기록됨")에 해당하므로 본 cycle 에서 cycle-finalize 를 진행하지 않는다.

## 7. 개선 제안 (§8.1 — 기록만)

- `tool_call_usage` 가 도입되면 기존 `llm_usage` 기반 계정별 비용 리포트와 **두 원장을 합친
  단가·부하 통합 뷰**가 가능해진다(현재는 토큰 축만 존재).
- ADR-0026(per-user 키 폐기)은 본 feature 로 폐기 사유가 무효화된 것이 아니라 **다른 축으로
  우회**된 것이다 — 향후 BYOK 재검토 시 이 구분을 유지해야 한다.

## 3.2 3차 출하 (2026-08-13) — 잔여 3건 완결

HTTP/SSE 전송을 **라이브에 띄웠다**(`ext-tool-mcp` + Caddy `/api/ai/mcp`). 사용자는 설치물 없이
URL + access token 만 등록하면 되고, 익명 연결은 엣지에서 401 로 끊는다. 상한 4종을 관리
콘솔(`시스템 > 설정 > 외부 AI 도구`)에 올렸고, 전 구간 e2e 는 절차서 + 스크립트로 만들어
**사람이 인가 1회**만 하면 완주하도록 했다.

codex 리뷰 P1 4건·P2 2건 전건 수정. 가장 중요한 것은 **"콘솔이 존재하지 않는 방어를 표시"**
였다 — 동시 실행 상한 knob 은 소비처가 없었고, 미제출 상한은 집행되지 않았으며, RPM 은
`open_task` 에 걸려 있지 않았다. 노출된 knob 은 그 자체로 "이 방어가 있다" 는 주장이므로
미구현 knob 은 삭제하고 나머지는 실제 집행을 붙였다. 테스트 161건.

**여전히 미실측**: 인가 이후 구간(토큰 교환 → 도구 호출 → 제출)의 라이브 완주. 절차서까지
준비했을 뿐 실행은 사람 몫이며, 이 항목은 TASK §9 에서 열린 채로 둔다.

## 3.4 인증 접근성 (2026-08-13, `5f20ee88`)

사용자 지적("스크립트 실행은 접근성이 매우 낮다")에서 시작해 **미로그인 사용자는 인가를
시작할 방법 자체가 없었다**는 것을 발견했다(`/login` 404). 문서는 "브라우저로 인가한다" 고
적혀 있었고 실제로는 404 였다 — 이번 cycle 에서 **문서가 사실을 앞지른 세 번째 사례**다
(앞의 둘: 콘솔 섹션 부재, 컨테이너 미기동).

이제 사용자는 URL 하나만 등록하면 클라이언트가 인증을 스스로 시작하고, 사람은 로그인 후
[허용] 만 누른다. 그 과정에서 **동의 화면 부재로 인한 링크 클릭 탈취 경로**(SameSite=Lax +
GET 발급)도 함께 닫았다.

codex P1×3·P2×3 + 머지 전 PB-0008 이 잡은 2건, 전부 수정. 뮤테이션 8종 KILL.
