---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0038-frontend-modularization
linked_unit: unit/feature-0038-frontend-modularization
sources:
  - ../../unit/feature-0038-frontend-modularization/docs/FUNCTION.md
  - ../../docs/improvements/ssot-consolidation/ROADMAP.md
---

# Feature — 프론트엔드 모듈화 (ITEM-P5b 완결)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0038-frontend-modularization/docs/FUNCTION|unit/feature-0038-frontend-modularization/docs/FUNCTION.md]].

## 1. 한 줄 요약

프론트 모놀리스 3파일(admin.js 14,007줄 · app.js 13,165줄 · styles.css 9,328줄)을
behavior-neutral 점진 추출로 도메인 모듈화한 initiative (ssot-consolidation
ROADMAP **ITEM-P5b done** — 백엔드 분할은 feature-0012 완결).

## 2. 상태

- **완결** (본편 2026-08-03~04 10 cycle + 후속 Phase A~B3 2026-08-05 — 양 구간 PLAN-APPROVED
  by mckim, 전건 머지·배포·POST-DEPLOY PASS)
- 산출(본편): css/ 7분할 · admin.js 14,007→4,804줄(-66%)+admin/ 9모듈 · app.js ES module 전환+
  app/ 4모듈 · CONVENTIONS §14 code-modularity 재발 방지.
- 산출(후속 Phase A~B3, PR #1147~#1150): 본편이 전제로 남긴 공유 let 결합을 Phase A state 편입
  (`state.dqaDrag`·`state.sidebarCatchupTimer` + 계약 가드 `tests/verify_state_intake.mjs`)으로
  해소한 뒤 sidebar(B1)·composer(B2)·progress(B3) 도메인을 byte-동치 이동 —
  **app.js 11,119 → 8,082줄(-27%)**, `app/` 6모듈(auth·profile·messages·sidebar·composer·progress).
  AC-3(오케스트레이터 ≤~3,000줄)은 여전히 **부분 달성** — 잔여 지도는 REPORT §2.

## 3. 책임 경계

- 코드 거주지는 feature-0003 (`unit/feature-0003-agent-web-ui/src/static/**`) —
  본 unit 은 계획·게이트·검증 기록 홈 (feature-0012 와 동일 패턴).
- `static/graph/**` 는 범위 밖 (이미 모듈화 + 병렬 세션 영역). 번들러 도입 없음.

## 4. 관련 정본

- [[../../unit/feature-0038-frontend-modularization/docs/TASK|TASK.md]] — cycle 시퀀스·게이트 (§2.1 본편 · §2.2 후속 Phase A+B)
- [[../../unit/feature-0038-frontend-modularization/docs/REPORT|REPORT.md]] — 완결 보고 (§2 잔여 지도·AC-3 정직 보고 · §8 잔여 후보)
- [[../../docs/improvements/ssot-consolidation/ROADMAP|ssot ROADMAP]] — ITEM-P5b (실측 갱신 2026-08-03)
- [[../../unit/feature-0012-web-router-modularization/docs/TASK|feature-0012]] — 백엔드 분할 선례

## 5. 관련 노트

- [[feature-0003-agent-web-ui]] · [[feature-0012-web-router-modularization]]

## 6. Open questions / 미해결

- (해소) Cycle 7 `type="module"` 전환 fallback 판정 · 후속 Phase 의 공유 let 결합 전제 — 둘 다 완결.
- admin.js 4,804줄 잔여(공유 코어 = pending/batch-apply·권한 grid)의 추가 감축 여부는 재실측 후 별도 판단 — REPORT §2/§8.
- standalone mjs 하네스 40개가 `make test` 밖(CI 비배선)이라는 구조는 잔존 — 배선 여부 별도 검토. (red 23건 자체는 feature-0003 harness-repair 가 전건 해소.)
- 단일 프론트 파일 N줄 초과 WARN 기계 게이트(verify-completion / pre-commit) 추가 검토 — REPORT §8.

## 7. 변경 이력 (이 카드)

- 2026-08-03 — 카드 생성 (Cycle 1 완료 시점).
- 2026-08-06 (doc_sync) — 08-05 델타 반영: 후속 Phase A~B3 완결(PR #1147~#1150 — Phase A 공유 let 2건 state 편입 + B1~B3 byte-동치 이동, app.js 11,119→8,082줄·-27%)로 제목·§1·§2 의 'ITEM-P5b 잔여'·'공유 let 결합 전제' stale 정정 + §6 재구성(Cycle 7 fallback·후속 전제 해소, 잔여 = admin.js 재실측·mjs CI 비배선·N줄 WARN 게이트). 요지+포인터만(SSOT) — 정본 TASK §2.2/§6 · REPORT §2/§7/§8 · MODIFY CHG-20260805T105500/T114000/T123000/T140000/T145500.
