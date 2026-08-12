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
