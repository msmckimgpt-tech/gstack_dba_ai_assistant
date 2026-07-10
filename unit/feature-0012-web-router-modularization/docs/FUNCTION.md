---
doc_type: FUNCTION
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
feature-0003 `app.py`(29,494줄/178 route/554 함수, 단일 FastAPI app, `APIRouter` 미사용)를 도메인별
`APIRouter` 모듈로 **점진 분할**(behavior-neutral: 경로·메서드·응답·OpenAPI·등록순서 불변). P5b(ssot-consolidation
ITEM-P5b, Critical). 본 cycle 범위 = **분할 안전망 + 의존성 audit**(첫 산출물). 실제 router 추출은 후속 sub-step
(브라우저 QA env 필요).

## 2. Goal
- REQ-001: router 분할 회귀를 기계적으로 적발하는 **route-parity 안전망**(등록 경로·메서드·순서·OpenAPI 스냅샷 diff).
- REQ-002: handler→전역/helper **의존성 audit** 으로 `web_context` 추출 경계를 확정.
- REQ-003 (후속): 도메인 router 점진 추출(keywords→…→admin), 각 단위 make test + route-parity + 브라우저 QA.

## 3. In Scope (본 cycle)
- `unit/feature-0003-agent-web-ui/tests/test_route_parity_p5b.py` + `route_snapshot_p5b.json`(골든 179 route).
- 의존성 audit 문서화(REPORT §audit): 전역 98·핵심 helper `_require_account`(118)·첫 타깃 keywords 의존.
- feature-0012 추적 docs.

## 4. Out of Scope (후속 sub-step / 별건)
- 실제 router 추출(web_context 추출 + 도메인 router): keywords→profile/attachments/share→auth→conversations→admin(sub-split). 브라우저 QA env 필요.
- 프론트(admin.js/app.js/styles.css) 분할.
- FastAPI `Depends` DI 도입 (별건).
- `@app.on_event`→lifespan 마이그(deprecated 9건, 별건).

## 5. Inputs / 6. Outputs
- 입력: `app.app.routes`(정적 열람, startup·DB 불요).
- 산출: 골든 스냅샷 JSON + parity 테스트(make test 에 편입). 의존성 audit.

## 7. Main Flow (안전망)
1. `import app` → `app.routes` 열거(path·methods·type, 순서 보존).
2. 골든 스냅샷(`route_snapshot_p5b.json`)과 count·set(path+method)·order 비교.
3. drift 시 fail(추가/삭제/재정렬 메시지). 의도적 변경은 골든 갱신.

## 8. Edge Cases
- route 매칭은 등록 **순서** 의존(`{var}` vs 구체경로 충돌 존재) → order diff 필수.
- TestClient 는 startup 훅(9, DB connect) 발화 → `--no-deps` 불가. 그래서 `app.routes` 정적 열람 채택.

## 9. Acceptance Criteria
- AC-001: `test_route_parity_p5b` 가 현재 app 과 골든 일치 시 통과, 경로/메서드/순서 drift 시 실패.
- AC-002: make test 회귀 0(안전망 1건 추가).
- AC-003: audit 가 web_context 가 노출해야 할 helper/전역을 식별.

## 10. 라우터 등록 규약 (parallel-work-structure ITEM-05, 2026-07-10)
- 라우터 등록은 `routers/__init__.py` 의 **`register_all(app)`** 단일 경로 — app.py 꼬리에서 1회 호출.
  신규 라우터는 `routers/` 에 `router` 심볼을 가진 모듈 파일 추가만으로 등록된다(app.py 편집 불필요 —
  병렬 배선 경합 제거, F-008).
- 등록 순서는 각 모듈의 **`INCLUDE_ORDER: int`** 상수가 고정(2026-07-10 현행 23개 순서 스냅샷,
  10~230/10 간격). 순서 변경 금지 — 순서가 의미를 갖는 라우터(`{var}` vs 구체경로 shadow)가 있어
  route-parity 골든이 order diff 로 감시. INCLUDE_ORDER 미지정 신규 모듈은 맨 뒤 파일명 순.

## 13. Pre-approved Changes
- P5b plan-eng-review(Critical) + §12 승인(2026-06-25). 단 router 추출 실행은 브라우저 QA env + 단위별 재확인.
- 라우터 자동 등록(ITEM-05): ROADMAP parallel-work-structure §6.1 사전 승인(2026-07-10) — byte-동치 3중 게이트(스냅샷·F821·A/B pytest) 통과.
