---
doc_type: REPORT
feature_id: feature-0011-shared-extraction
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
P5a Step 1(model_catalog)·2(config)·3(db)·4(conn_health·datasources) 추출 완료 + **Step 5a**(conn_health·
datasources 소비처 마이그레이션 + shim 제거) 완료. config-first 위상정렬(/plan-eng-review). Step 2~4 는 alias shim
(`modules.X`=`shared.X` 동일 객체)으로 비파괴 추출했고, Step 5(점진 마이그레이션)는 소비처를 정본 `shared.*` 로
수렴시키며 shim 을 제거한다(per-module sub-step: 5a=conn_health/datasources 완료, 5b=config·5c=db 후속).
Step 5a 후 conn_health/datasources 는 shim 없이 shared.* 단일 경로; config/db 는 아직 alias shim 유지.
make test **회귀 0**, residual grep 0. 다음은 Step 5b(config 마이그·shim 제거).

## 2. Progress
- Planned: Step 5b(config 마이그·shim 제거) → 5c(db) → Step 6(feature 단위 Dockerfile 분리), 동반 doc
- In Progress: 없음
- Done: Step 1(model_catalog) · 2(config alias) · 3(db alias) · 4(conn_health·datasources alias + db back-dep 정리)
  · **5a(conn_health·datasources 소비처 shared.* 마이그 + shim 2개 제거)**

## 3. Recent Changes
- CHG-20260624-0001: shared/ 패키지 + model_catalog 추출
- CHG-20260624-0002: config → shared/config + 모듈 alias shim
- CHG-20260624-0003: db → shared/db + 모듈 alias shim (lazy datasources/conn_health back-dep, Step 4 정리)
- CHG-20260625-0004: conn_health·datasources → shared/ + 모듈 alias shim + db lazy back-dep `from shared import` 정리
- CHG-20260625-0005: conn_health·datasources 소비처 60 ref/18 파일 shared.* 마이그레이션 + alias shim 2개 제거 (Step 5a)
- 총 변경 횟수: 5

## 4. Open Issues
- **기존 baseline 실패는 해소됨**: Step 3 시점 잔존하던 `test_product_delete_block_conv.py` 2건은 main 의
  CI-fix(PYTHONPATH·/shared mkdir) 이후 본 Step 4 `make test` 에서 전체 green(F/E 0, 2 skip)으로 확인.
- **후속 동반 doc(저위험, 미반영)**: #4 GDPR legal-erasure gap 의 CODEBASE_MAP 명시 + CODEBASE_MAP
  자체 stale 정정(0007~0010 feature 누락, shared 구식 기술)은 본 PR 에 미포함 — TASK-0011-11 로 추적.

## 5. Test Status
- 자동 테스트: `make test` — **회귀 0**(전체 green, 2 skip, F/E 0). 격리 agent 이미지 `--no-deps` pytest + ruff(All checks passed).
- residual 검증(Step 5a): deterministic grep — 라이브 `modules.conn_health`/`modules.datasources` 참조 **0**
  (잔존은 shared/ 내부 정본 상대 import + modules/db.py shim 의 stale 주석 1줄 = 5c 에서 제거).
- 수동 테스트(Step 5a): /app smoke — `from shared import conn_health/datasources` OK · `modules.{conn_health,
  datasources}`→ModuleNotFoundError(shim 제거 확인) · `modules.{config,db}` shim 유지 · db back-dep · cred_crypto OK.
- 적대 검증: §18.8 3렌즈 패널(missed-ref hunt·migration correctness·deploy/runtime, 실 이미지 배포 레이아웃 실행) —
  BLOCKING 0 / NIT 0. 결과는 REVIEW.md REV-20260625-0005. (Step 4 패널: REV-20260625-0004.)
- Windows-browser(PB-0008, verify-completion #13 WARN): **N/A — UI 표면 변경 없음**. feature-0003 app.py·테스트
  변경은 전부 함수-local import 경로(`from modules import` → `from shared import`) 치환으로 렌더/라우트/템플릿
  델타 0(§18.8 correctness 렌즈 behavior-identical 확인). 실 Windows 브라우저 검증이 보여줄 차이 없음 → 생략.
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
