---
doc_type: REVIEW
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260625-0001 [SKIPPED:test-only-route-parity-safety-net]
- Related Change: CHG-20260625-0001 (route-parity 안전망 + 의존성 audit, P5b 선행물)
- §18.8 Adversarial Panel: **SKIPPED — test-only/비핵심경로.** 본 cycle 의 코드 변경은 **추가 테스트 1건**
  (`test_route_parity_p5b.py`, `app.routes` 정적 열람)과 골든 JSON·doc 뿐. 프로덕션 src·런타임·이미지 무변경
  → 적대 패널 표적(import 깨짐·런타임·배포 회귀) 부재. (실제 router 추출 시점에는 추출 단위마다 §18.8 패널 +
  브라우저 QA 적용 — 후속.)
- 검증(결정적): 안전망 테스트가 현재 app(179 route)과 골든 일치 시 통과(make test 회귀 0), 인위적 경로/메서드/
  순서 drift 시 fail 하도록 set·order 비교 구현. TestClient 미사용(startup 훅·DB 발화 회피, `--no-deps` 동작) 확인.

## REV-20260625-0002 [SUBAGENT:p5b-plan-eng-review-critical]
- Related Change: P5b 실행 계획(plan-review gate, ROADMAP ITEM-P5b "plan-review(Critical)" 충족)
- 검토: plan-eng-review(eng-manager mode). 대상 = app.py(29.5K/178 route/0 APIRouter) 도메인 router 점진 분할 계획.
- **VERDICT: APPROVE-WITH-CONDITIONS.** 접근(점진 strangler·FastAPI APIRouter built-in[Layer1]·router당 commit
  reversible·behavior-neutral)은 견고.
  - **must-fix 2 (실행 전)**: (T1) route-level 테스트 격차 — 60 테스트 중 HTTP-route 레벨 ~0 → route-parity 안전망
    선구축(본 cycle 완료). (A1) 의존성 audit — `Depends()`=0+전역 98 → web_context 경계 확정(본 cycle 완료).
  - **A2**: route 등록 순서 민감(`{var}` vs 구체경로 충돌) → 안전망이 order diff 포함.
  - **A3**: startup 훅 9(deprecated) + lifespan 은 app 잔류, on_event→lifespan 은 scope 밖.
  - 결정: web_context 모듈(DI 보류)·첫 타깃 keywords·admin 최후 sub-split·프론트 별건·route-parity HARD 게이트.
- 전문: 계획+리뷰리포트 = 본 cycle 작업 산출(scratchpad P5b-PLAN.md 의 GSTACK REVIEW REPORT). 
- Human Approval: §12 승인 획득(2026-06-25). router 추출 실행은 브라우저 QA env + 단위별 재확인.
