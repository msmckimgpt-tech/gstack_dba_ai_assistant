---
doc_type: REPORT
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 1. 현재 상태

**in-progress — P0 구현 완료 · 라이브 배포 미실시.**

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
- ⚠ **라이브 e2e 미실시** — 본 worktree 에 서비스가 기동돼 있지 않다. "외부 AI 가 등록→인가→
  토큰→도구→제출 을 완주한다" 는 아직 실측되지 않은 주장이다(TASK §9 G3 에 명시).

## 4. 잔여 (BLOCKED 아님 — 다음 cycle)

- **라이브 배포 + e2e 5-probe** (등록 201 / 인가 302+code / 토큰 200 / 도구 200+각인 / 무토큰 401).
  배포는 외부 영향 행동이라 **사람 결정**이다.
- HTTP/SSE MCP 전송(f-ii) — 현재 stdio 만. 발견 자료(`/api/ai/manifest`·`guide`·OpenAPI) 갱신.
- L4 권한 비대칭 flag(원장 컬럼은 준비됨) · 관리 콘솔 '외부 도구 한도' 탭.

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
