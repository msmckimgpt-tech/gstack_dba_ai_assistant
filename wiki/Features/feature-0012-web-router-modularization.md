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
maturity: minimal
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

feature-0003 `app.py`(단일 FastAPI app, 최대 29.5K줄/178 route)를 도메인별 `APIRouter` 모듈로 **분할**하는 라이브 web 구조 리팩터 (ssot-consolidation P5b, Critical, behavior-neutral). **route 핸들러 전량 추출 완료** — app.py 는 helpers + DI seam + `include_router` 로 축소.

## 2. 상태

- **단계**: in-progress — route-parity 안전망 + 의존성 audit(PR#456) 이후 **P5b 전체추출 완료**(2026-07-01): app.py 모놀리스의 148 route 핸들러 전량을 21개 도메인 `APIRouter` 로 byte-동치 추출(app.py ~29K→18,917줄, 잔여 `@app` 라우트 0). batch1-3 라이브 배포·검증 완료(main c031b5d — 추출 라우트 프로덕션 응답 byte-동치). 잔여: `web_context` 헬퍼 추출·프론트(admin.js/app.js/styles.css) 분할·Final 로그인 QA·batch4(잔여 16 route) 재배포 검증.
- **마지막 갱신**: 2026-07-01
- **AI 작업자**: claude / Human (§12 승인 2026-06-25)

## 3. 책임 경계

- **입력**: app.py 178 route + 공통 helper(`_require_account` 118 등) + 전역 98.
- **출력**: route-parity 안전망(`test_route_parity_p5b.py` + 골든 route) + 의존성 audit(web_context 경계) + `src/routers/<domain>.py` 21개 도메인 라우터(전량 추출 완료, behavior-neutral).
- **side-effect**: 동작 무변경 — 경로·메서드·순서·응답 byte-동치(route-parity 골든 불변, 프로덕션 응답 실측 동일). 잔여 `web_context` 헬퍼 추출·프론트 분할은 후속 workstream.

## 4. 관련 정본

- [[../../unit/feature-0012-web-router-modularization/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0012-web-router-modularization/docs/TASK|TASK.md]] — 작업 큐
- [[../../unit/feature-0012-web-router-modularization/docs/ANCHOR|ANCHOR.md]] — 방향성
- [[../../docs/improvements/ssot-consolidation/ROADMAP|ROADMAP]] — ITEM-P5b

## 5. 관련 노트

- [[feature-0003-agent-web-ui]] — 분할 대상(코드 거주지, app.py)
- [[feature-0011-shared-extraction]] — 선행(P5a, import 표면 정리)

## 6. Open questions / 미해결

- web_context 헬퍼 전체 추출 — 별도 workstream(원래 블로커), 후속.
- 프론트(admin.js/app.js/styles.css) 분할 — 별건/후속(TASK-0012-10).
- Final 로그인 QA + batch4(잔여 16 route) 프로덕션 재배포 검증 — 후속.
