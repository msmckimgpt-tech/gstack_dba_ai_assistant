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
maturity: draft
ai_generated: true
feature_id: feature-0038-frontend-modularization
linked_unit: unit/feature-0038-frontend-modularization
sources:
  - ../../unit/feature-0038-frontend-modularization/docs/FUNCTION.md
  - ../../docs/improvements/ssot-consolidation/ROADMAP.md
---

# Feature — 프론트엔드 모듈화 (ITEM-P5b 잔여)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0038-frontend-modularization/docs/FUNCTION|unit/feature-0038-frontend-modularization/docs/FUNCTION.md]].

## 1. 한 줄 요약

프론트 모놀리스 3파일(admin.js 14,007줄 · app.js 13,165줄 · styles.css 9,328줄)을
behavior-neutral 점진 추출로 도메인 모듈화하는 initiative (ssot-consolidation
ROADMAP **ITEM-P5b 잔여** — 백엔드 분할은 feature-0012 완결).

## 2. 상태

- **완결** (2026-08-03~04, PLAN-APPROVED by mckim — 10 cycle 전건 머지·배포·POST-DEPLOY PASS)
- 산출: css/ 7분할 · admin.js 14,007→4,804줄(-66%)+admin/ 9모듈 · app.js ES module 전환+
  app/ 4모듈 · CONVENTIONS §14 code-modularity 재발 방지. 잔여 오케스트레이터 감축은
  공유 let 결합(state 편입 mini-change 승인 필요)이 전제 — REPORT §2/§8.

## 3. 책임 경계

- 코드 거주지는 feature-0003 (`unit/feature-0003-agent-web-ui/src/static/**`) —
  본 unit 은 계획·게이트·검증 기록 홈 (feature-0012 와 동일 패턴).
- `static/graph/**` 는 범위 밖 (이미 모듈화 + 병렬 세션 영역). 번들러 도입 없음.

## 4. 관련 정본

- [[../../unit/feature-0038-frontend-modularization/docs/TASK|TASK.md]] — cycle 시퀀스·게이트 (§2.1)
- [[../../docs/improvements/ssot-consolidation/ROADMAP|ssot ROADMAP]] — ITEM-P5b (실측 갱신 2026-08-03)
- [[../../unit/feature-0012-web-router-modularization/docs/TASK|feature-0012]] — 백엔드 분할 선례

## 5. 관련 노트

- [[feature-0003-agent-web-ui]] · [[feature-0012-web-router-modularization]]

## 6. Open questions / 미해결

- Cycle 7 (app.js `type="module"` 전환) 실패 시 classic 순차 분할 fallback 채택 여부는 그 cycle 에서 판정.

## 7. 변경 이력 (이 카드)

- 2026-08-03 — 카드 생성 (Cycle 1 완료 시점).
