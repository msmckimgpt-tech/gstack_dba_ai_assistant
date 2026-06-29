---
doc_type: TASK
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in_progress (P5b 안전망 + audit 완료; router 추출은 브라우저 QA env 후속)
- Owner: AI / Human
- Priority: high (Critical 등급 — 라이브 web app 모놀리스 분할)
- Last Updated: 2026-06-25

## 2. Implementation Plan

### 2.1 Plan
- **목표**: app.py(29.5K/178 route) → 도메인 `APIRouter` 점진 분할(behavior-neutral).
- **접근**: web_context.py 공통 helper/전역 선추출 → 도메인 router 1개/커밋 → route-parity + make test + 브라우저 QA.
- **순서**: keywords(첫, 저결합) → profile/attachments/share → auth(18) → conversations → admin(92 sub-split).
- **위험도**: Critical (라이브 web, 178 route). 안전망(route-parity)·롤백(1 router/commit)·canary 로 관리.

<!-- §12 APPROVED: P5b plan-eng-review(Critical, APPROVE-WITH-CONDITIONS) + 사용자 §12 승인 2026-06-25. 조건: (1)route-level 안전망 先, (2)의존성 audit. -->

## 3. Task Queue
- [x] TASK-0012-1 P5b plan-eng-review(Critical) + §12 승인
- [x] TASK-0012-2 **안전망**: route-parity 스냅샷 테스트(`test_route_parity_p5b.py` + 골든 179 route) + make test green
- [x] TASK-0012-3 **의존성 audit**: 전역 98·핵심 helper `_require_account`(118 호출)·첫 타깃 keywords 의존 → web_context 경계(REPORT §audit)
- [ ] TASK-0012-4 web_context.py 추출(공통 helper/전역) [후속, 브라우저 QA env]
- [ ] TASK-0012-5 keywords router 추출(첫 도메인, 패턴 증명) [후속, 브라우저 QA env]
- [ ] TASK-0012-6 profile/attachments/share → auth → conversations router 추출 [후속]
- [ ] TASK-0012-7 admin(92) sub-domain 분할 [후속]
- [ ] TASK-0012-8 프론트(admin.js/app.js/styles.css) 분할 + CONVENTIONS code-modularity 규약 [후속/별건]

## 4. In Progress
- 없음 (안전망+audit 완료; TASK-0012-4~ 는 브라우저 QA 가능 env 세션에서)

## 5. Blocked
- TASK-0012-4~7 (router 추출): 완료 게이트 브라우저 QA(PB-0008)가 현 WSL env 불가 → Windows 브라우저 QA env 필요.

## 6. Done
- P5b plan-eng-review: APPROVE-WITH-CONDITIONS (REVIEW REV-0012-0001). §12 승인.
- 안전망: `test_route_parity_p5b.py` — `app.routes` 정적 열람으로 경로·메서드·**순서**·count 를 골든(179 route)과
  비교, drift 시 fail. TestClient(startup·DB 발화) 대신 정적 열람이라 `--no-deps` 동작. make test 회귀 0.
- 의존성 audit: web_context 가 노출해야 할 핵심 = `_require_account`(118)·`_admin_mutation`(18)·`_require_permission`(7)·
  `_json_error`·`_audit_row_to_dict` + 전역 98(대부분 `_`-prefix 상수). 첫 타깃 keywords(L29476-29492, 연속 CRUD).

## 7. Next Action
- (브라우저 QA env 에서) TASK-0012-4 web_context.py 추출 → TASK-0012-5 keywords router 추출, route-parity+make test+브라우저 QA.

## 8. Completion Checklist (본 cycle = 안전망 + audit)
- [x] AC(route-parity 안전망이 경로·메서드·순서 drift 를 적발)가 구현되었다
- [x] 의존성 audit 가 web_context 경계(핵심 helper/전역)를 식별했다
- [x] 단위 테스트(make test)가 통과한다 — 회귀 0(안전망 1건 추가, 전체 green)
- [x] FUNCTION.md가 현재 동작과 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다 (CHG-20260625-0001)
- [x] REVIEW.md에 판단 근거가 기록되었다 (plan-eng-review + 안전망, REV-0012-0001/0002)
- [x] REPORT.md에 최종 상태가 반영되었다
- [x] BLOCKED 항목이 사람에게 전달되었다 (router 추출 = 브라우저 QA env)
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
