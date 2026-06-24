---
doc_type: REVIEW
feature_id: feature-0011-shared-extraction
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260624-0001 [SUBAGENT:shared-extraction-p5a-step1]
- Related Change: CHG-20260624-0001 (shared/ 플러밍 + model_catalog 첫 추출, P5a Step 1)
- Reason: model_catalog 을 modules/ → shared/ 로 이동하고 import 4사이트를 재배선. db.py 추출 전
  저결합 모듈로 플러밍을 test-gated 로 증명하는 안전 sequencing (big-bang 금지).
- §18.8 Adversarial Panel: general-purpose 적대적 리뷰어 1인. 7개 결함 가설(놓친 import 사이트·
  컨테이너 경로 깨짐·eager import 체인·Dockerfile COPY·Makefile shadowing·baseline 회귀·wildcard)을
  worktree Read/Grep + **빌드 이미지 실런타임 검증**으로 공격.
  - **결과: BLOCKING 0 / NIT 2.**
  - 실측 핵심: web `uvicorn web.app:app` 실부팅 "Application startup complete"(유일 에러 = DB 호스트
    부재, import 무관) · agent/memory-init/insight-worker/ask-worker 전부 `python /app/agent_core.py`
    import OK · 놓친 import 사이트 0(절대·상대·bare·동적·문자열 전수) · `modules/__init__`→llm→
    shared.model_catalog eager 체인 무결 · `make test` 1077 passed/2 failed(2 실패는 clean main
    에서도 동일 재현 = baseline, 본 변경 무관) · Makefile `/work` top-level shadowing 0.
- Alternatives Considered: db.py 우선 추출(Alt-A, 최고위험 → 반려, ANCHOR §2) · shared 없이 유지
  (Alt-B → 소유권/빌드분리 상충) · 별도 패키지화(Alt-C → 오버헤드 과대).
- Risks: 라이브 web/agent 인접이나 import 경로만 변경(런타임 동작 불변)·단일 commit revert 가능·
  배포 시 healthz/smoke 로 재확인.
- NIT 처리:
  - NIT-1 (호스트 `__pycache__`/README/docs 가 `COPY shared` 로 이미지 유입): **수용**. 기존
    `COPY modules /app/modules` 와 동일 패턴이고 `__pycache__` 는 gitignored 라 클린 체크아웃 빌드는
    무영향. Python 이 `.pyc` 를 mtime 으로 재검증해 기능 무해(패널 실측). repo-wide `.dockerignore`
    도입은 본 Step 1 범위 밖 → 별도 hygiene 후속(TASK-0011-10 인근).
  - NIT-2 (shared/README.md 자기참조 stale): **수정**. README 에 "model_catalog 첫 승격" + import/path
    규칙 반영. shared/docs/{MODIFY,REPORT}.md 의 area-level 추적은 feature MODIFY 가 정본이라 미변경(수용).
- Open Questions: 없음 (Step 2 db.py shim 은 후속 cycle).
- Human Approval Needed: PR 생성·deploy confirm (외부영향). P5a/P5b 진행 자체는 2026-06-24 사용자 승인.
