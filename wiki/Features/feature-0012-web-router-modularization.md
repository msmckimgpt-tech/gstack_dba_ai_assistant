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

- **단계**: review(완결) — route-parity 안전망 + 의존성 audit(PR#456) 이후 **P5b 전체추출 완료**(2026-07-01): app.py 모놀리스의 148 route 핸들러 전량을 21개 도메인 `APIRouter` 로 byte-동치 추출(app.py ~29K→18,917줄, 잔여 `@app` 라우트 0). **2026-07-12 feature-0012 완결**(라이브 4c203f9c) — ITEM-10(라우터 추출 + `web_context` 헬퍼 추출, 모듈 분리 -81%) + ITEM-11(잔여 인라인 authn DEFER 핸들러 실leak 13건 DI-rework·keep-inline 정당 37 명시분류) 완료. 브라우저 로그인 QA = 자동 검증 다중 GREEN + 사용자 환경 게이트로 사용자 사인오프 이관. 잔여 initiative ITEM-09(그래프 CSS/JS 세분화·외부 브랜치, blocked).
- **마지막 갱신**: 2026-07-12
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

- ~~web_context 헬퍼 전체 추출~~ — **완료**(ITEM-10, 2026-07-12).
- ~~Final 로그인 QA + batch4(잔여 16 route) 프로덕션 재배포 검증~~ — **완료**(ITEM-10/11 완결, 라이브 4c203f9c; 브라우저 로그인 QA 사용자 사인오프 이관).
- 프론트(admin.js/app.js/styles.css) 분할 — 별건/후속(ITEM-09 그래프 CSS/JS 세분화는 외부 브랜치 blocked, 나머지 분할 후속).
