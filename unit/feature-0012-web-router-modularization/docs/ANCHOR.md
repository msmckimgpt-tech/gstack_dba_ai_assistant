---
doc_type: ANCHOR
feature_id: feature-0012-web-router-modularization
created_at: 2026-06-25T16:30:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0012-web-router-modularization — app.py 모놀리스 router 분할 (P5b)

## §1. 외부 관점 요약
처음 코드를 여는 사람은 "왜 잘 도는 `app.py` 를 굳이 쪼개지?" 라고 묻는다. 이유: feature-0003 의
`app.py` 가 **29,494줄 / 178 route / 554 함수** 단일 파일로 비대화돼 AI 가 전체를 로드·정확 편집하기
어렵고("요청 미수행" 증상 기여), 사람도 유지보수가 힘들다. 해법은 FastAPI **`APIRouter` 로 도메인별
(auth/conversation/admin/attachment/datasource/share/keywords…) 점진 분할**(router-by-router,
behavior-neutral). 이는 ssot-consolidation ROADMAP **ITEM-P5b**(Critical)이며, **SSOT(중복) 문제가 아니라
모듈화(파일 크기) 문제**다. P5a(shared/ 추출)가 import 표면을 정리해 선행 조건이 됐다.

본 feature 는 P5b 의 **추적 cycle**이다. 코드 변경은 feature-0003(app.py·routers·tests)에 거주(cross-cut,
feature-0009 와 동형). 첫 산출물은 **분할 안전망**(route-parity 스냅샷 테스트)과 **의존성 audit**.

## §2. 대안 분기
- **Alt-A: 한 번에 전부 router 화(big-bang).** 안 고른 이유: 29.5K줄/178 route 라이브 web 을 한 turn 에
  재배선 = 최고위험·검증 불가. ROADMAP·plan-eng-review 모두 점진(router-by-router) 명시.
- **Alt-B: FastAPI `Depends` DI 로 전환하며 분할.** 안 고른 이유: 현재 `Depends()`=0 + 전역 98 + 핵심
  helper `_require_account`(118 호출). DI 도입은 호출 패턴 대변경(structural+behavioral 동시) → blast-radius↑.
  → **web_context 모듈 추출**(app.py·router 양쪽 import)로 최소 diff·behavior-neutral. DI 는 후속 별건.
- **Alt-C: 분할 안 함(현상 유지).** 안 고른 이유: 사용자 원 요청("비대화된 코드"). 비대화는 AI 편집
  정확도·유지보수를 직접 저해.

## §3. 가정된 사용 시나리오
다른 작업자가 첫 router 추출(keywords)을 맡는다. 그는 본 ANCHOR + TASK 의 audit + 안전망만 읽고
재발명 없이 파악할 수 있어야 한다: (1) router 는 `from fastapi import APIRouter; router = APIRouter()` 로
만들고 `app.include_router(router)` 로 등록, (2) handler 가 쓰는 공통 helper(`_require_account`/
`_admin_mutation`/`_require_permission`/`_json_error`/`_audit_row_to_dict`) + 전역 상수는 **`web_context.py`**
로 먼저 추출해 양쪽 import, (3) 추출마다 **route-parity 스냅샷 테스트**(`test_route_parity_p5b.py`)가
경로·메서드·**순서** 불변을 강제하고 의도적 변경 시 골든 갱신, (4) 완료 게이트 = make test + route-parity +
**브라우저 QA(PB-0008)** + 롤백 리허설(§12 Critical).

### 동반 메모 — 실행 환경 제약
추출 단위 완료 게이트인 **브라우저 QA(PB-0008)는 WSL 내부 env 불가**. 따라서 실제 router 추출·배포는
Windows 브라우저 QA env 세션 필요. 본 cycle 은 그 전제인 **안전망 + audit** 만 수행(env 무관).

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — release/milestone 시 사람이 append.)
