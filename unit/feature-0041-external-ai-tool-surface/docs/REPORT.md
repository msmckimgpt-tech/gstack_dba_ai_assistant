---
doc_type: REPORT
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 1. 현재 상태

**plan-review — 계획 산출물 완료, 구현 미착수.**

본 cycle 의 범위는 방향(ANCHOR)·명세(FUNCTION)·구현 계획(TASK §2.1) 작성까지다. 코드 변경 0,
런타임 영향 0. 위험도 **Critical**(§12.3 — 인증·인가 trust 모델 신설 + 신규 데이터 유출면)이라
§7.1 에 따라 `PLAN-APPROVED` 마커 부여 전까지 구현에 착수하지 않는다.

## 2. 산출물

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

- `bin/verify-completion.sh --pre-commit feature-0041-external-ai-tool-surface` → **PASS**
  (전 CHECK PASS, wiki 카드 WARN 도 해소)
- §18.8 검증 패널: 세션 Agent-tool 제약으로 feature-0030 선례(§18.8.2)대로 `/codex review` 채택.
  GATE **FAIL (P1 3건)** → 전건 in-cycle 수정 후 재확인. 상세는 REVIEW.md.
- 테스트: 코드 변경이 없어 신규 테스트 없음. 구현 cycle 의 완료 판정 기준을 TASK §2.1 에 선고정.

## 4. 승인 대기 (BLOCKED)

- **Critical 승인 대기**: TASK.md §2.1 계획에 대한 사람 승인(`PLAN-APPROVED` 마커).
  승인 전까지 TASK.md §3 Task Queue 의 구현 항목 전건 BLOCKED (§5 등재).
- 승인 시 착수 순서: `schema-ledger` → `authz-seam` → `oauth-as` → `tools-p0` → `isolation`
  → `injection` → `mcp-adapters` → `docs`.
- **구현 cycle 에서 §18.8 보안 렌즈를 다시 받아야 한다** — 본 cycle 의 codex 리뷰는 *계획* 에
  대한 것이고, OAuth AS·도구 표면은 신규 인증·유출 경계라 코드 단계에서 재검증이 필요하다.

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
