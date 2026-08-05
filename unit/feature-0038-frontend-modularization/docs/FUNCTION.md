---
doc_type: FUNCTION
feature_id: feature-0038-frontend-modularization
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
ssot-consolidation 로드맵 **ITEM-P5b 잔여분** — 프론트 모놀리스 3파일
(`unit/feature-0003-agent-web-ui/src/static/` 의 admin.js 14,007줄 · app.js 13,165줄 ·
styles.css 9,328줄, 2026-08-03 실측)을 behavior-neutral 점진 추출로 모듈화하는
구조 리팩터 initiative. 백엔드(app.py) 분할은 feature-0012 가 완결했으므로 범위 밖.
코드는 feature-0003 src 에 계속 거주하고, 본 unit 은 initiative 의 계획·추적·검증
기록 홈이다 (feature-0012 와 동일한 패턴).

## 2. Goal
- REQ-20260803-item-p5b-frontend-split: admin.js/app.js/styles.css 를 도메인 모듈로
  점진 분할해, AI 작업자의 전체 로드·정확 편집이 가능한 크기(오케스트레이터 ≤ ~3,000줄)로
  낮춘다. 각 추출 단위는 로드맵 게이트(make test + 브라우저 QA + 롤백 리허설 +
  plan-review Critical + check #9)를 통과한다. big-bang 금지.
- REQ-20260803-code-modularity-convention: 재발 방지 — CONVENTIONS.md 에
  code-modularity 컨벤션(파일 크기 임계 → 추출 트리거)을 추가한다.

## 3. In Scope
- `static/styles.css` 순차 물리 분할 (`css/` 7파일, cascade 순서 보존)
- `static/admin.js` ES module 도메인 추출 (`admin/` — graph/ 선례 패턴)
- `static/app.js` type="module" 전환 + 도메인 추출 (`app/`)
- `index.html`/`admin.html` link·script 태그 배선
- 이동 심볼에 결합된 소스-추출형 테스트 경로 갱신
- CONVENTIONS code-modularity 컨벤션 + 로드맵/STATUS 정합

## 4. Out of Scope
- 백엔드 `app.py`/`routers/` — feature-0012 완결, 재착수 금지
- `static/graph/**` 서브트리 (이미 모듈화됨 + 활성 병렬 세션 영역)
- `share.css`/`share.html`/`mentions.js` 등 이미 분리된 소형 자산
- 동작·시각 변경 일체 (behavior-neutral — 리팩터 중 기능 개선 금지)
- 번들러(webpack/vite) 도입 — 현행 무번들 `?v=` 스탬프 체계 유지

## 5. Inputs
- 원본 3파일 (2026-08-03 기준 sha256 을 TEST.md 기준선에 기록)
- 로드맵 `docs/improvements/ssot-consolidation/ROADMAP.md` ITEM-P5b(실측 갱신판)

## 6. Outputs
- `static/css/*.css` 7파일 · `static/admin/*.js` · `static/app/*.js` 도메인 모듈
- 잔존 오케스트레이터 admin.js/app.js (≤ ~3,000줄 목표)
- cycle 별 PR·배포·PB-0008 검증 기록 (TEST.md §3 / test-runs.d)

## 7. Main Flow
1. cycle 착수 — 대상 도메인 심볼 경계 실측, TASK Queue 고정
2. byte-동치 이동 (본문 무수정, import/export/`?v=dev` 배선)
3. 소스-추출형 테스트 경로 갱신
4. 게이트: make test → 헤드리스 → verify-completion → PR → 배포 → PB-0008
5. 롤백 가능성 확인 (단일 PR revert) 후 다음 cycle

## 8. Edge Cases
- ES module 이중 인스턴스화 (`?v=` 불일치 URL) → specifier `?v=dev` 규약 + asset-stamp
- 롤링 배포 창의 신/구 replica 혼재 → asset-stamp cache-integrity (feature-0014) 로 기해소
- app.js module 전환 시 실행 타이밍(defer) 변화 → Cycle 7 단독 격리 + classic 분할 fallback
- 병렬 세션이 같은 파일 수정 → REGISTRY hot_paths + cycle 착수마다 접촉 재실측

## 9. Error Handling
- 게이트 FAIL → 그 cycle 내 수정, 해소 불가 시 PR 미머지 상태로 BLOCKED 보고
- 배포 후 회귀 발견 → `git revert <merge-commit>` + 재배포 (deploy-web.sh last-good 롤백 병용)

## 10. Dependencies
### 내부 기능 의존성
- feature-0003-agent-web-ui (파일 소유 feature — 코드 거주지)
- feature-0012-web-router-modularization (선례 패턴·초기화 initiative 의 프론트 잔여 승계)
- feature-0014-zero-downtime-deploy (배포 스파인·asset-stamp cache-integrity)

### 외부 의존성
- 없음 (신규 라이브러리·번들러 도입 없음)

### shared 모듈 의존성
- 없음

## 11. Acceptance Criteria
- AC-20260803T000000-item-p5b-frontend-split-1: styles.css 분할 7파일의 순차 concat 이
  원본과 byte-identical (기계 검증 스크립트 출력 기록)
- AC-20260803T000000-item-p5b-frontend-split-2: 각 추출 cycle 에서 make test FAILED 0 ·
  헤드리스 스위트 PASS · PB-0008 Windows-browser Run 기록
- AC-20260803T000000-item-p5b-frontend-split-3: admin.js/app.js 잔존 오케스트레이터
  ≤ ~3,000줄 (전 cycle 완료 시점)
- AC-20260803T000000-item-p5b-frontend-split-4: 롤백 리허설 1회 실증 (Cycle 1 —
  revert→재빌드→스모크→재적용 기록)
- AC-20260803T000000-code-modularity-convention-1: CONVENTIONS.md 에 code-modularity
  임계·트리거 등재
- AC-20260805T105500-phaseA-state-intake-1 (후속 Phase A — TASK §2.2): 모듈-스코프 공유 가변
  `let _dqaDrag`·`let _sidebarCatchupTimer` 가 `state.dqaDrag`·`state.sidebarCatchupTimer` 로
  편입되고 bare 식별자 잔존 0 + 계약 가드 `tests/verify_state_intake.mjs` PASS + 전 mjs 하네스
  회귀 0 + POST-DEPLOY PB-0008(사이드바 DnD·catchup 라이브 동작)

## 12. Observability
- cycle 별 라인 수 감소 실측 (TASK.md §6 Done 에 기록)
- 배포 후 PB-0008 스크린샷 + 헤드리스 카운트 (TEST.md §3)
- 배포 스파인 soak/rollback 로그 (deploy-web.sh)

## 13. Pre-approved Changes
- 없음 (전역 `FIRST_REQUEST.md` 의 `deploy_scope: included` · `visual_verification_scope: always` 를 따름)
