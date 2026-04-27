---
doc_type: REQUEST_ARCHIVE
scope: project
status: active
edit_policy: append-only
source_of_truth: true
---

# Request Archive

## REQ-20260425-0001 api-vault-flow-redesign
- submitted_at: 2026-04-25T00:00:00Z
- target: project
- personas_invoked: [worker-design]
- mode: quick
- source_log: ~/.gstack/projects/mysql_ai_delegated_dev/template-personas/ai-codex-1-issue-1-integration-api-vault-flow-redesign-20260424-185536.md

### Design

**Mode**: quick

**Raw feedback**:
"프로필쪽 키 입력하는곳 왜이래? 알아먹기 힘드네"

**Interpreted mental model**:
- skipped: quick mode

**Dimension ratings** (0-10):

| Dimension | Score | Gap to 10 |
|-----------|-------|-----------|
| Interaction clarity | 3/10 | 시작점이 `<details>` 에 접혀있어 평문 키 입력란이 제1시선 외에 있음. 라벨 renaming + 단계별 활성/비활성 + "저장" 동사 단일화 + top-level readiness 배지까지 가야 10. |
| Information architecture | skipped: quick mode | — |
| Visual hierarchy | skipped: quick mode | — |
| Consistency | skipped: quick mode | — |
| Accessibility | skipped: quick mode | — |

**Diagnosis** (brutal, Top 1):
1. [Interaction clarity 3/10] [index.html:246-280](../unit/feature-0003-agent-web-ui/src/static/index.html#L246-L280) 의 Vault 패널은 **결과물(ciphertext) 을 상단**에, **시작점(평문 키 input) 을 `<details>` 안**에 숨겨 순서가 역순. 사용자가 평문 키를 가지고 들어와도 처음 3 필드를 모두 scan 한 뒤에야 `<details>` 를 연다 — 첫 입력까지 인지 delay 4~5초. Steve Krug "60mph billboard" 기준 광고판이 아니라 숨바꼭질. 라벨 `암호화된 API 키` vs `암호화 키` 는 한 글자("된") 차이로만 구분되며 localStorage 영구 vs sessionStorage 세션 정책 차이도 UI 에 드러나지 않음. `updateVaultStatus` ([app.js:409-428](../unit/feature-0003-agent-web-ui/src/static/app.js#L409-L428)) 는 "모델: X · 암호화된 API 키 저장됨 · 암호화 키 입력됨" dot-separator 병렬 나열이라 "지금 요청 가능한가?" 1 줄 판정 불가.

**Modern reference gap**:
- Count: skipped: quick mode
- Locations:
  - (Stripe Dashboard API Keys, Linear Settings → Integrations, Notion Settings onboarding 의 progressive disclosure 패턴을 Option A 재설계에 반영)

**Redesign proposal**:
- Scope: `src/static/index.html` (프로필 드로어의 `data-profile-pane="vault"` 패널), `src/static/styles.css` (새 `.vault-*` 클래스), `src/static/app.js` (vault state 헬퍼군 재작성)
- **Option A** (채택): Linear Wizard — 세로 3-step stepper + top-level readiness 배지 + 저장된 값 카드 + 고급(접힘) ciphertext 복원.
  - Evidence: 시작점(Step 1 "사용할 API 키") 이 1st 시선 영역으로 이동. `encrypt + save` 두 버튼을 단일 "암호화 후 저장" 으로 통합해 동사 모호성 제거. 라벨 `API 키 (sk-...)` / `passphrase` / `저장된 암호화 키` 로 성격별 명확화. `data-state` 속성으로 step `active|done|disabled` 전환. Stripe / Linear / Notion onboarding 의 표준 progressive disclosure.
  - Tradeoff: 세로 길이 +30~40%. `vaultEncryptBtn` + `saveVaultBtn` 두 핸들러 통합에 따른 에러 경로 단일화 필요. 고급(cipher 직접 붙여넣기) 사용자 +1 클릭.
- **Option B** (기각): Two-Card 분리. 두 카드 경계를 넘는 의존관계(cipher ↔ passphrase) 표현이 어색해짐. 모바일 폭에서 카드 효과 소실.
- **Option C** (선택 안 됨): In-place polish. raw feedback 강도 대비 cosmetic.
- **Recommendation**: Option A — 사용자 선택.

### Iteration log
- **fix1 (saved card 분리)**: cipher 저장 시 `[교체] [삭제]` 두 버튼 → `[다시 입력]` 1개 + 별도 destructive zone 의 "저장된 키 삭제" 분리. confirm 가드 추가. 사용자 검증에서 "두 진입점이 결과적으로 동일" 보고 → 추가 수정.
- **fix2 (replacingVault flag)**: "다시 입력" 의 즉시 cipher 삭제 동작을 비파괴 편집 모드(`state.replacingVault` flag) 로 전환 + 같은 버튼 "다시 입력 ↔ 취소" 토글. computeVaultReadiness 의 진실 출처를 input value → localStorage 로 통일. 사용자 검증에서 "saved-default + 다시 입력 + ready 단계가 정말 필요한가" 의문 + "교체 버튼 자체가 불필요" 재거론.
- **final (단일 진입점)**: 두 방향 가치 비교 후 사용자 신호("교체 버튼 자체가 불필요")에 정렬. `replacingVault` flag · `enterReplaceMode` · `cancelReplaceMode` · saved card 토글 라벨 · banner replacing 분기 · syncVaultSteps replacing 분기 · `vaultReplaceBtn` DOM/이벤트 모두 제거. 키 갈아끼움은 "저장된 키 삭제" → confirm → wizard 재진입 → 새 입력 → 저장 단일 경로. saved card 는 information only.

### Outcome
- status: completed
- completed_at: 2026-04-25T00:00:00Z
- consumed_by:
  - unit/feature-0003-agent-web-ui/src/static/index.html (vault 패널 markup wizard 구조 재작성)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.vault-banner` / `.vault-stepper` / `.vault-step` / `.vault-saved` / `.vault-danger-zone` / `.btn-danger-link` 신규)
  - unit/feature-0003-agent-web-ui/src/static/app.js (vault state helper 재작성, computeVaultReadiness 진실 출처 = storage)
  - unit/feature-0003-agent-web-ui/docs/TASK.md (TASK-0046)
  - unit/feature-0003-agent-web-ui/docs/MODIFY.md (CHG-20260425-0017)
  - unit/feature-0003-agent-web-ui/docs/REPORT.md (Recent Changes)
- verification:
  - 자동 검증: `repo/.gstack/qa-reports/qa-vault.cjs` (Playwright Node) 28/28 PASS, healthScore 100. console.error 0건. 핵심 회귀 — UI-10(`#vaultReplaceBtn` 부재), REG-2(saved card 안 버튼 0개), REG-3(danger zone 안 버튼 1개), REG-5/6/7(confirm 가드 dismiss/accept 양 경로), REG-8(새로고침 후 cipher 보존).
  - 사용자 직접 브라우저 검증: 4가지 시나리오(저장 완료 / 새로고침 / 삭제 후 새 키 입력 / confirm 취소) 모두 정상 동작 확인.
- notes: cache-bust `v=20260425-vault-final`. 변경 atomic commit `feat(agent-web-ui): API Vault 패널 Linear Wizard + 단일 진입점 destructive (TASK-0046, REQ-20260425-0001)` 1건으로 묶음.
