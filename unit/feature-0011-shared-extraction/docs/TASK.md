---
doc_type: TASK
feature_id: feature-0011-shared-extraction
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: done (Step 1~5 + 동반doc 완료 · Step 6 Dockerfile 분리는 **불채택 종결** — ADR-20260805T153000-p5a-closeout, 2026-08-05)
- Owner: AI / Human
- Priority: high (Critical 등급 — 라이브 제품 구조 리팩터)
- Last Updated: 2026-06-25

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
<!-- 순서 재설계(/plan-eng-review, decision 5cc24689): config 가 db 보다 먼저 — db 의 from .config import * 강결합 때문. config(L0 leaf)→db(L1)→레이어순, 모듈 1개/step. -->
- [x] TASK-0011-6 **P5a Step 2 — config → shared/config 이동 + modules/config alias shim (비파괴)**
- [x] TASK-0011-7 **P5a Step 3 — db.py → shared/db.py 이동 + modules/db.py alias shim (비파괴)**
- [x] TASK-0011-8 **P5a Step 4 — conn_health·datasources → shared/ + alias shim (비파괴) + db lazy back-dep `from modules`→`from shared` 정리**
- [x] TASK-0011-9 P5a Step 5 — import 점진 마이그레이션 + shim 제거 [완료 — per-module sub-step]
  - [x] 5a conn_health·datasources 소비처 shared.* 마이그레이션(60 ref/18 파일) + alias shim 2개 제거
  - [x] 5b config 소비처 shared.config 마이그레이션(~150 ref/53 파일) + modules/config shim 제거 (fan-in 25 foundation)
  - [x] 5c db 소비처 shared.db 마이그레이션(219 ref/52 파일, app.py 112 + .sh-embedded) + modules/db shim 제거 (최다결합)
        → 4개 alias shim(config·db·conn_health·datasources) 전부 제거, shared/ 추출 구조 완성
- [x] TASK-0011-10 P5a Step 6 — **불채택 종결**(단일 이미지 유지): 분리 전제(import 얽힘·경계 불명)는 shared/ 추출+CODEBASE_MAP §7 로 해소, 이후 배포 스파인(0014/0020/0039)이 단일 이미지 전제로 안정화 — ADR-20260805T153000
- [x] TASK-0011-11 동반(저위험) — #4 GDPR gap CODEBASE_MAP 명시 + CODEBASE_MAP stale 정정(feature-0007~0011 추가·shared/ 6모듈·§7 Known Gaps 신설) [완료, CHG-0008]
- [x] TASK-0011-12 P3-제외 100% 검증 — done 항목 유보 3건 전수 실측(wiki 백필 기완료 실증·skeleton 기해소·pb0008 통합 불채택) + wiki/README §5.1 대상 범위 명문화 + ROADMAP 실증 반영 (CHG-20260805T160500)

## 4. In Progress
- 없음 (Step 5b=config 마이그·shim제거 완료; Step 5c=db 마이그·shim제거 부터 별도 cycle/PR)

## 5. Blocked
- 없음
<!-- Phase 3(secret rotation 후 repo 위생)은 사용자 명시 보류 — 본 feature 범위 밖 -->

## 6. Done
- P5a Step 1 (shared/ 플러밍 + model_catalog 첫 추출) — make test 회귀 0, /app smoke PASS, PR #403 머지·배포.
- P5a Step 2 (config → shared/config + alias shim) — config 는 L0 foundation(fan-in 25). enumeration shim 이
  annotated assignment(_ACTIVE_DEFAULT_DB) 누락으로 mssql 10건 회귀 → **모듈 alias(sys.modules 치환)** 로 전환,
  271+ 심볼·monkeypatch 완전 보존. make test 회귀 0, /app alias 완전성 smoke PASS. PR #407 머지·배포.
- P5a Step 3 (db → shared/db + alias shim) — repo 최다결합(fan-in 17). alias 로 underscore·AnnAssign·
  config 재노출 체인 보존. lazy back-dep(datasources/conn_health) `from modules import` 로 임시 재배선. PR #408 머지·배포.
- P5a Step 4 (conn_health·datasources → shared/ + alias shim) — L1 cross-feature. alias 로 모니터 상태·
  _DEK_CACHE 단일 인스턴스·monkeypatch 보존. db 의 lazy back-dep 을 `from shared import` 로 정리. datasources 의
  cred_crypto 는 `from modules import`(미추출 back-dep, stdlib-only·cycle 없음) 유지. make test **회귀 0**(전체
  green), /app alias 완전성 smoke PASS, §18.8 3렌즈 패널 BLOCKING 0/NIT 0.
- P5a Step 5a (conn_health·datasources 소비처 shared.* 마이그레이션 + shim 2개 제거) — 60 ref/18 파일
  (app.py 26·agent_core 2·ask 3·insight 4·gdrive 1·rekey 1·테스트 12파일 dynamic 포함). config·db 등 타 모듈 미변경.
  make test **회귀 0**(전체 green), residual grep 0, /app smoke(shared.* OK·modules.{conn_health,datasources}
  ModuleNotFoundError·modules.{config,db} shim 유지), §18.8 3렌즈(missed-ref/correctness/deploy) BLOCKING 0/NIT 0.
- P5a Step 5b (config 소비처 shared.config 마이그레이션 + modules/config shim 제거) — L0 foundation(fan-in 25,
  16+ 모듈 wildcard 재노출, __init__ eager). ~150 ref/53 파일(modules/* 17·scripts 6·tests 19·eval 7·agent_core·app.py).
  modules/__init__ eager+wildcard 재노출 체인 보존(config 이름 shared.config 재바인딩). subagent 28파일 + 세션한도
  후 결정적 스크립트 21파일 보완. make test **회귀 0**, residual grep 0, baked-layout smoke(shared.config OK·
  modules.config ModuleNotFoundError·재노출 체인 OK), §18.8 3렌즈 BLOCKING 0/NIT 0.
- P5a Step 5c (db 소비처 shared.db 마이그레이션 + modules/db shim 제거) — repo 최다결합(fan-in 17, underscore
  심볼 9+, __init__ eager). 219 ref/52 파일(app.py 112 포함) + **bin/kb-pg-healthcheck.sh .sh-embedded python**.
  modules/__init__ eager+wildcard 재노출 체인 보존. make test **회귀 0**, residual grep 0(전 파일), baked-layout
  smoke OK. §18.8 3렌즈: **BLOCKING 1 발견·수정**(.sh-embedded `from modules.db import` — .py-only 마이그가 놓침
  → shared.db 로 수정·전파일 재grep 0) / NIT 0 / deploy SAFE. **→ 4개 alias shim 전부 제거, shared/ 추출 완성.**

## 7. Next Action
- (완결) P5a 전 단계 종결 — Step 6 은 ADR-20260805T153000 로 불채택. 재개 조건: 이미지 크기/보안
  요구가 실측으로 등장할 때 별도 initiative.

## 8. Completion Checklist (P5a Step 5c = db 마이그레이션·shim제거 cycle — Step 5 종결)
- [x] AC(db 전 소비처가 shared.db 정본 경로로 마이그레이션됨 — 정적+wildcard+dynamic/string+.sh-embedded 포함)이 구현되었다
- [x] modules/db.py alias shim 이 제거되고 modules.db 가 더는 import 되지 않는다(ModuleNotFoundError); 4개 shim 전부 제거; modules/__init__ 재노출 체인 보존
- [x] 단위 테스트(make test)가 통과한다 — 회귀 0 (전체 green, 2 skip, F/E 0). residual grep 0(전 파일 — .py+.sh+config, 라이브 modules.db 참조 없음)
- [x] FUNCTION.md가 현재 동작과 일치한다 (db shim 제거, 소비처 shared.db 수렴, shared/ 추출 완성 반영)
- [x] MODIFY.md에 변경 이력이 기록되었다 (CHG-20260625-0007)
- [x] REVIEW.md에 판단 근거가 기록되었다 (§18.8 3렌즈 패널 — BLOCKING 1 발견·수정 / NIT 0, REV-20260625-0007)
- [x] REPORT.md에 최종 상태가 반영되었다
- [x] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
