---
doc_type: TASK
feature_id: feature-0011-shared-extraction
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in_progress (P5a Step 1 완료, Step 2~5 후속)
- Owner: AI / Human
- Priority: high (Critical 등급 — 라이브 제품 구조 리팩터)
- Last Updated: 2026-06-24

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** shared/__init__.py(신규), shared/model_catalog.py(이동),
  feature-0002 agent_core.py·modules/llm.py·tests/test_prompt_gen_max_tokens.py,
  feature-0003 app.py, feature-0002 src/Dockerfile, Makefile.
- **접근 방법:** db.py(최다결합)를 옮기기 전에 저결합 모듈 model_catalog 으로 shared/ 플러밍을
  test-gated 로 증명. 모든 import 사이트(절대+상대) 재배선 후 `make test` 회귀 0 게이트.
- **위험도:** Critical (라이브 web 컨테이너 인접 — 단계별 commit·다중 PR·롤백 가능)

<!-- PLAN-APPROVED by user on 2026-06-24 (P5a/P5b 진행 승인; Phase 3 secret rotation 은 사용자 보류) -->

## 3. Task Queue
- [x] TASK-0011-1 shared/ 패키지 골격(__init__.py) 확립
- [x] TASK-0011-2 저결합 모듈 model_catalog git mv → shared/ (history 보존)
- [x] TASK-0011-3 import 4사이트 재배선 (agent_core·app.py·modules/llm.py 상대형·테스트)
- [x] TASK-0011-4 Dockerfile COPY shared + Makefile PYTHONPATH(/work) 배선
- [x] TASK-0011-5 make test green(회귀 0) + 프로덕션(/app) import smoke 검증
- [ ] TASK-0011-6 P5a Step 2 — db.py → shared/db.py 이동 + modules/db.py shim(비파괴) [후속 PR]
- [ ] TASK-0011-7 P5a Step 3 — import 점진 마이그레이션 + shim 제거 [후속]
- [ ] TASK-0011-8 P5a Step 4 — config/memory/llm 등 추가 공통 모듈 [후속]
- [ ] TASK-0011-9 P5a Step 5 — feature 단위 Dockerfile 분리 + 브라우저 QA [후속]
- [ ] TASK-0011-10 동반(저위험) — #4 GDPR gap 문서화 + CODEBASE_MAP stale 정정(0007~0010 누락·shared 구식) [후속]

## 4. In Progress
- 없음 (Step 1 완료; Step 2 부터는 별도 cycle/PR)

## 5. Blocked
- 없음
<!-- Phase 3(secret rotation 후 repo 위생)은 사용자 명시 보류 — 본 feature 범위 밖 -->

## 6. Done
- P5a Step 1 (shared/ 플러밍 + model_catalog 첫 추출) — make test 회귀 0, /app smoke PASS.

## 7. Next Action
- P5a Step 2(db.py shim 추출)를 별도 Critical cycle/PR 로 진행. 그 전에 본 Step 1 머지·배포.

## 8. Completion Checklist
- [x] REQ-001~003 의 AC가 구현되었다 (AC-0001~0003)
- [x] 단위 테스트(make test)가 통과한다 — 회귀 0 (기존 baseline 실패 2건만 잔존, 본 변경 무관)
- [x] FUNCTION.md가 현재 동작과 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다
- [x] REVIEW.md에 판단 근거가 기록되었다 (§18.8 패널 SUBAGENT — BLOCKING 0 / NIT 2)
- [x] REPORT.md에 최종 상태가 반영되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다 (해당 시)
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
