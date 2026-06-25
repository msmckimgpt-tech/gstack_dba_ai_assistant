---
doc_type: REPORT
feature_id: feature-0011-shared-extraction
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
P5a Step 1(model_catalog) + Step 2(config) + Step 3(db) + Step 4(conn_health·datasources) 완료.
config-first 위상정렬(/plan-eng-review). config·db·conn_health·datasources 모두 `modules.X`→`shared.X`
**모듈 alias** 로 추출돼 모든 심볼(annotated 포함)·monkeypatch·wildcard·모듈객체접근·재노출 체인·모듈상태
(모니터/_DEK_CACHE)를 동일 객체로 완전 보존. Step 4 에서 db 의 lazy datasources/conn_health 참조를
`from shared import` 로 정리(두 모듈 이동 완료). datasources 의 cred_crypto 는 `from modules import`
(미추출 back-dep, stdlib-only·cycle 없음) 유지. make test **회귀 0**(전체 green). 다음은 Step 5(import 점진 마이그).

## 2. Progress
- Planned: P5a Step 5(소비처 `from shared import` 점진 마이그 + alias shim 제거) → Step 6(feature 단위 Dockerfile 분리), 동반 doc
- In Progress: 없음
- Done: Step 1 (model_catalog) · Step 2 (config alias) · Step 3 (db alias) · Step 4 (conn_health·datasources alias + db back-dep 정리)

## 3. Recent Changes
- CHG-20260624-0001: shared/ 패키지 + model_catalog 추출
- CHG-20260624-0002: config → shared/config + 모듈 alias shim
- CHG-20260624-0003: db → shared/db + 모듈 alias shim (lazy datasources/conn_health back-dep, Step 4 정리)
- CHG-20260625-0004: conn_health·datasources → shared/ + 모듈 alias shim + db lazy back-dep `from shared import` 정리
- 총 변경 횟수: 4

## 4. Open Issues
- **기존 baseline 실패는 해소됨**: Step 3 시점 잔존하던 `test_product_delete_block_conv.py` 2건은 main 의
  CI-fix(PYTHONPATH·/shared mkdir) 이후 본 Step 4 `make test` 에서 전체 green(F/E 0, 2 skip)으로 확인.
- **후속 동반 doc(저위험, 미반영)**: #4 GDPR legal-erasure gap 의 CODEBASE_MAP 명시 + CODEBASE_MAP
  자체 stale 정정(0007~0010 feature 누락, shared 구식 기술)은 본 PR 에 미포함 — TASK-0011-11 로 추적.

## 5. Test Status
- 자동 테스트: `make test` — **회귀 0**(전체 green, 2 skip, F/E 0). 격리 agent 이미지 `--no-deps` pytest + ruff(All checks passed).
- 수동 테스트: /app alias 완전성 smoke — `modules.conn_health is shared.conn_health`·`modules.datasources is
  shared.datasources`, db lazy back-dep→shared(`_breaker_key` scope_key 도달), cred_crypto back-dep→modules,
  모듈상태 단일(`_STATE`/`_DEK_CACHE`), config 재노출 체인(`db.AGENT_KB_PG_PORT`) 전부 PASS.
- 적대 검증: §18.8 3렌즈 패널(import-cycle/runtime·alias-completeness·deploy/build) — BLOCKING 0 / NIT 0.
  결과는 REVIEW.md REV-20260625-0004. `conn_health._scope_key_of(ds)==db._breaker_key(ds)` 키 계약 실측 보존.
- 미검증 항목: 라이브 배포 후 web-1/agent/insight-worker/ask-worker 헬스(배포 시 healthz/smoke 로 확인 예정).

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- Phase 3(secret rotation)은 사용자 보류 상태 유지.
- deploy_scope:included → 머지 후 자동 배포(첫 배포 직전 1줄 표면화). PR 생성은 외부 노출 행동.

## 8. Suggested Improvements
- 추출 헬퍼/체크리스트: 새 모듈 이동 시 절대+상대 import 전수 grep + AST 심볼 추출(`ast.Assign`+`ast.AnnAssign`
  +Func/Class 모두) 을 lint 로 자동화하면 누락 위험을 줄인다.
- **shim 전략 가이드**: 단순 모듈(model_catalog)은 full 이동+rewire, foundation/모듈객체접근/monkeypatch 대상
  (config)은 **모듈 alias(sys.modules)** 가 정답 — enumeration shim 은 annotated/동적 심볼을 놓쳐 fragile.
  Step 3(db) 도 모듈객체 접근(`from . import db as _db`)·shim 대상이라 alias 패턴 우선 검토.
