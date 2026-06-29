---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: stub
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
feature_id: feature-0012-web-router-modularization
linked_unit: unit/feature-0012-web-router-modularization
created: 2026-06-25
sources:
  - ../../unit/feature-0012-web-router-modularization/docs/FUNCTION.md
---

# Feature — web app `app.py` 모놀리스 router 분할 (P5b)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0012-web-router-modularization/docs/FUNCTION|unit/feature-0012-web-router-modularization/docs/FUNCTION.md]].

## 1. 한 줄 요약

feature-0003 `app.py`(29.5K줄/178 route, 단일 FastAPI app)를 도메인별 `APIRouter` 모듈로 **점진 분할**하는 라이브 web 구조 리팩터 (ssot-consolidation P5b, Critical). 본 cycle 은 분할 **안전망 + 의존성 audit** 까지.

## 2. 상태

- **단계**: in-progress — plan-eng-review(조건부 승인)+§12 승인 후, route-parity 안전망·audit 완료. router 추출은 후속(브라우저 QA env).
- **마지막 갱신**: 2026-06-25
- **AI 작업자**: claude / Human (§12 승인 2026-06-25)

## 3. 책임 경계

- **입력**: app.py 178 route + 공통 helper(`_require_account` 118 등) + 전역 98.
- **출력(본 cycle)**: route-parity 안전망(`test_route_parity_p5b.py` + 골든 179 route) + 의존성 audit(web_context 경계).
- **출력(후속)**: `src/web_context.py` + `src/routers/<domain>.py` (behavior-neutral router 추출).
- **side-effect**: 본 cycle 없음(테스트/doc). 추출은 동작 무변경(경로·메서드·순서·응답 불변) 목표.

## 4. 관련 정본

- [[../../unit/feature-0012-web-router-modularization/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0012-web-router-modularization/docs/TASK|TASK.md]] — 작업 큐
- [[../../unit/feature-0012-web-router-modularization/docs/ANCHOR|ANCHOR.md]] — 방향성
- [[../../docs/improvements/ssot-consolidation/ROADMAP|ROADMAP]] — ITEM-P5b

## 5. 관련 노트

- [[feature-0003-agent-web-ui]] — 분할 대상(코드 거주지, app.py)
- [[feature-0011-shared-extraction]] — 선행(P5a, import 표면 정리)

## 6. Open questions / 미해결

- web_context 추출 방식(모듈 vs DI) — 모듈 채택, DI 보류.
- 실제 router 추출(keywords→…→admin) — 브라우저 QA(PB-0008) env 필요.
- 프론트(admin.js/app.js/styles.css) 분할 — 별건/후속.
