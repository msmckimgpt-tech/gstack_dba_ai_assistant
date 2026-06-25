---
doc_type: REPORT
feature_id: feature-0011-shared-extraction
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
**P5a Step 1~5 전체 완료 — `shared/` 점진 추출 구조 완성.** config-first 위상정렬(/plan-eng-review). Step 1~4 는
4개 공통 모듈(model_catalog·config·db·conn_health·datasources)을 alias shim(`modules.X`=`shared.X` 동일 객체)으로
비파괴 추출했고, Step 5(점진 마이그레이션, sub-step 5a/5b/5c)는 모든 소비처를 정본 `shared.*` 로 수렴시키고
**4개 alias shim(config·db·conn_health·datasources)을 전부 제거**했다. 이제 4개 모듈은 shim 없이 `shared/`
단일 경로로만 존재(model_catalog 는 Step 1 부터 직접). make test **회귀 0**, 전 파일 residual grep 0.
남은 것: Step 6(feature 단위 Dockerfile 분리 — P5b 토대) + 동반 저위험 doc.

## 2. Progress
- Planned: Step 6(feature 단위 Dockerfile 분리 + 브라우저 QA) + 동반 doc(GDPR gap·CODEBASE_MAP 정정)
- In Progress: 없음
- Done: Step 1~4(추출) · **Step 5 전체(5a conn_health/datasources · 5b config · 5c db 마이그레이션 + 4개 shim 제거)**

## 3. Recent Changes
- CHG-20260624-0001: shared/ 패키지 + model_catalog 추출
- CHG-20260624-0002: config → shared/config + 모듈 alias shim
- CHG-20260624-0003: db → shared/db + 모듈 alias shim (lazy datasources/conn_health back-dep, Step 4 정리)
- CHG-20260625-0004: conn_health·datasources → shared/ + 모듈 alias shim + db lazy back-dep `from shared import` 정리
- CHG-20260625-0005: conn_health·datasources 소비처 60 ref/18 파일 shared.* 마이그레이션 + alias shim 2개 제거 (Step 5a)
- CHG-20260625-0006: config 소비처 ~150 ref/53 파일 shared.config 마이그레이션 + modules/config shim 제거 (Step 5b)
- CHG-20260625-0007: db 소비처 219 ref/52 파일(+.sh-embedded) shared.db 마이그레이션 + modules/db shim 제거 (Step 5c — 4개 shim 전부 제거)
- CHG-20260625-0008: docs/CODEBASE_MAP.md stale 정정(feature-0007~0011·shared/ 6모듈) + §7 Known Gaps(GDPR legal-erasure) 신설 (TASK-0011-11)
- 총 변경 횟수: 8

## 4. Open Issues
- **기존 baseline 실패는 해소됨**: Step 3 시점 잔존하던 `test_product_delete_block_conv.py` 2건은 main 의
  CI-fix(PYTHONPATH·/shared mkdir) 이후 본 Step 4 `make test` 에서 전체 green(F/E 0, 2 skip)으로 확인.
- **동반 doc 완료(TASK-0011-11, CHG-0008)**: #4 GDPR legal-erasure gap 을 docs/CODEBASE_MAP.md §7 Known Gaps 에 명시 +
  CODEBASE_MAP stale 정정(feature-0007~0011 추가, shared/ 6모듈 현행화, PB-0008). 해소됨.
- **잔여(범위 밖)**: P5a Step 6(feature 단위 Dockerfile 분리, TASK-0011-10) — Critical, 완료 게이트 Windows 브라우저
  QA(PB-0008)가 WSL env 불가라 별도 환경/세션 필요. Phase 3(secret rotation)은 사용자 보류 유지.

## 5. Test Status
- 자동 테스트: `make test` — **회귀 0**(전체 green, 2 skip, F/E 0). 격리 agent 이미지 `--no-deps` pytest + ruff(All checks passed).
- residual 검증(Step 5c): deterministic grep — **전 파일(.py + .sh + config/yml)** live `modules.{config,db,conn_health,datasources}`
  참조 **0**(잔존은 shared/ 내부 정본 상대 import + .md docs 의 historical 멘션뿐).
- 수동 테스트(Step 5c): baked-layout smoke — `from shared import {config,db,conn_health,datasources}` OK ·
  `import modules.{config,db,conn_health,datasources}`→전부 ModuleNotFoundError(4개 shim 제거 확인) · modules 패키지+
  __init__ eager 체인 OK · agent_core/app(web) import OK · db underscore 심볼(_pg_connect 등) + 재노출 체인
  (`from modules import GLOBAL_CONVERSATION_ID`·`modules.AGENT_KB_PG_PORT`) OK · cross-module lazy(db↔conn_health/datasources) OK.
- 적대 검증: §18.8 3렌즈 패널(missed-ref hunt·migration correctness·deploy/runtime, **실 이미지 baked-layout 빌드·실행**) —
  **BLOCKING 1 발견·수정 / NIT 0**. missed-ref 렌즈가 `bin/kb-pg-healthcheck.sh:121` 의 .sh-embedded
  `from modules.db import`(docker-exec smoke)을 적발 → `from shared.db import` 로 수정·전파일 재grep 0. 결과 REVIEW.md
  REV-20260625-0007. (5b 패널: REV-20260625-0006, 5a: REV-20260625-0005.)
- Windows-browser(PB-0008, verify-completion #13 WARN): **N/A — UI 표면 변경 없음**. feature-0003 app.py 변경은
  전부 import 경로(`from modules import db` → `from shared import db`) 치환으로 렌더/라우트/템플릿 델타 0
  (§18.8 correctness 렌즈 behavior-identical 확인). 실 Windows 브라우저 검증이 보여줄 차이 없음 → 생략.
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
