---
doc_type: TASK
feature_id: feature-0020-zd-deploy-all
feature_status: in-progress
feature_status_date: 2026-07-14
feature_status_note: 무중단 배포 커버리지 완성 — deploy 스파인 확장(워커 insight/ask 자동 롤아웃 build-once `mysql-ai-agent:<sha>` 핀·healthy 게이트·last-good 롤백 + bedrock-gateway 드리프트 시 surge replica 무중단 교체 + caddy 이미지 드리프트 reconcile) · alembic 직접호출 stale-image 가드 · 워커 healthcheck 오탐 견고화(timeout 30s) · 라이브 적용 미커밋 compose 운영 튜닝 정식 커밋(live-truth) · Makefile deploy-all/deploy-workers/ask-worker-* (cross-cut: 0014 스파인/0002 이미지/0007 gateway)
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (ai/claude/feature-0020-zd-deploy-all)
- Priority: high
- Last Updated: 2026-07-14

## 2. Implementation Plan

### 2.1 Plan (REQ-20260714T101500-zd-deploy-all)

- **영향받는 파일 / symbol:**
  - `bin/deploy-web.sh` — `write_pin_overlay`(워커 핀 추가), `build_image`→서비스 일반화
    (`build_service_image`), 신규 `build_agent_image`·`deploy_workers`·`wait_container_healthy`·
    `deploy_gateway_reconcile`, `worker_divergence_warn` 대체, `main()` 배선,
    `--web-only`/`--workers-only`/`--force-gateway` 플래그, `--rollback` 워커 확장,
    stale 주석(528) 정정.
  - `docker-compose.yml` — insight-worker/ask-worker `healthcheck.timeout` 10s→30s,
    `bedrock-gateway.stop_grace_period: 120s`, 신규 `bedrock-gateway-surge`(profile
    `deploy-surge`, networks alias `bedrock-gateway`), 라이브 운영 튜닝 verbatim 채택
    (insight env 7종·on-failure:3·mem_limit·OLLAMA_NUM_PARALLEL — 이미 라이브 적용값과
    전수 일치 확인).
  - `bin/alembic-migrate.sh` — `_alembic_sh` 폴백 가드(미설정 시 WARN + 선행
    `compose build agent`, `MIGRATE_SKIP_REBUILD=1` escape).
  - `Makefile` — `deploy-all`(alias), `ask-worker-up/down/logs`, `up` 빌드 목록에 ask-worker.
  - `unit/feature-0014-zero-downtime-deploy/docs/RUNBOOK.md` §10 — stale 서술(insight-worker
    SIGTERM 핸들러 없음) 정정 + 신규 phase 반영 (cross-cut).
  - `unit/feature-0020-zd-deploy-all/docs/*`, `docs/STATUS.md`(gen-status), `docs/ARCHITECTURE.md`
    §4/§6, wiki `Log.md`/`hot.md`.
- **접근 방법:** 검증된 feature-0014 스파인을 확장한다(별도 스크립트 신설로 flock/coalesce/
  게이트 로직을 중복하지 않음). 워커는 web 과 동형의 build-once+SHA핀+last-good 패턴,
  gateway 는 배포 창 한정 surge replica(DNS alias)로 steady-state 비용 0 의 무중단을 얻는다.
  워커 healthcheck 오탐(10s timeout, 라이브 16h unhealthy)을 먼저 견고화해 헬스 게이트가
  신뢰 가능해진 위에 배포 게이트를 얹는다.
- **완료 판정 기준 (AC):** FUNCTION.md §2 AC-1~5. 검증 = `bash -n`+`--dry-run` 전 경로,
  `docker compose config -q`(±profile), 머지 후 라이브 `sudo -E bin/deploy-web.sh` 실배포
  (deploy-backed 완료 기준 §16.3 — healthz·워커 healthy·gateway 무중단 확인).
- **위험도:** Major (배포 인프라 다파일 — 인증/개인정보/파괴적 데이터 없음, deploy_scope:
  included 사전 승인. 실패 모드는 last-good 롤백/ABORT 로 유계).

## 3. Task Queue
- [x] T1 gap 분석(전 서비스 × 무중단 현황) + 계획 수립
- [x] T2 docker-compose.yml (healthcheck·surge·stop_grace·live-truth 채택)
- [x] T3 deploy-web.sh 워커 phase + gateway surge reconcile + caddy 이미지 드리프트
- [x] T4 alembic-migrate.sh 폴백 가드
- [x] T5 Makefile (deploy-all·ask-worker 타깃·up 빌드 목록)
- [x] T6 검증(bash -n·dry-run 4 scope·compose config ±profile·pin overlay 병합) + 문서(RUNBOOK §9 정정·unit docs·STATUS·ARCHITECTURE·wiki 카드/_Index/Log/hot)
- [x] T7 verify-completion → commit → PR #780 → cycle-finalize(머지 eaba795a)
- [x] T8 라이브 배포(deploy_scope: included) + POST-DEPLOY 검증(§16.3 deploy-backed) — exit 0·워커 healthy·edge 200 (test-runs.d fragment)

## 4. In Progress
- 없음 (cycle 완료).

## 5. Blocked
- 없음.

## 7. Completion Checklist
- [x] 모든 REQ 의 AC 가 구현되었다 (AC-1~5)
- [x] 자동 테스트가 통과한다 (bash -n / dry-run 4 scope / compose config ±profile)
- [x] 웹/UI 변경 없음 — Windows-browser 검증 N/A (UI 표면 없음, 사유 TEST.md 명시)
- [x] FUNCTION.md 가 현재 동작과 일치한다
- [x] MODIFY.md / REVIEW.md / REPORT.md / TEST.md 기록
- [x] STATUS.md / ARCHITECTURE.md 반영
- [x] verify-completion --pre-commit PASS (본 cycle 1차 commit)
- [x] Git 커밋 + 원격 동기화 (PR #780 머지 eaba795a)
- [x] (deploy-backed) 라이브 재배포 검증 — 실배포 exit 0 + edge /healthz 200 + 워커 healthy

## TASK-20260812T140000 워커·gateway 교체 quiesce 게이트 (무중단 배포 근본 해소)
사용자 지시(2026-08-12) — conv-audit `FR-llm-transient-failure-kills-run` 대응 중 "배포 이슈가
나타나는 원인을 근본적으로 해소할 수 있도록 완벽한 무중단 배포 환경을 먼저 구성" 요청.

- [x] 현행 spine 실측 — web 은 `predrain`(실제 신호 + fail-closed)으로 이미 정본, **워커·gateway
      만 눈감고 재는 타이머**. ask_jobs 363건: p50 81s · p95 691s · max 2,024s, **60초 초과 66%**
      vs ask-worker drain 60s. 반대편: 시스템은 30일 중 **2.1% 만 busy**(대기가 현실적)
- [x] `quiesce_user_runs` — 진행 중 사용자 run 2신호 합산(ask_jobs running[heartbeat 신선분만]
      + web active_streams) 폴링, 상한까지 조용해지지 않으면 **중단**(fail-closed)
- [x] 두 신호 모두 관측 불가 = "조용한지 알 수 없다" → 0 으로 읽지 않고 중단(vacuous pass 방지)
- [x] 배선 — ask-worker recreate **직전**, gateway 본체 recreate **직전**(surge healthy 이후).
      배경 워커(insight/ops)는 대상 아님(실패=degraded 후 재시도)
- [x] `--force-busy` 탈출구 + usage 등재. 강행 시 **무중단이 아니었음을 배포 말미에 보고**
      (`quiesce_summary` — LRN-20260811T1557 "성공 보고 ≠ 무중단" 직접 적용)
- [x] 게이트 중단 경로가 surge 를 정리(leaked surge 재발 방지)
- [x] 테스트 18건 신규 + **`pyproject.toml testpaths` 등재**(feature-0014 가 남긴 교훈의 자기적용)
- [x] 뮤테이션 9/9 KILLED · 전 testpaths 회귀 실패 0(선재 2건 제외) · ruff/bash -n/TOML OK
- [x] 라이브 SQL 검증 — 운영 primary 에서 게이트 쿼리 실행(현재 running=0)
- [x] §18.8 적대 검증(codex, full-panel 대체 채널) — **P1 5건 흡수**(실행모드 게이트 · unknown
      차단 · settle 재확인 · stale 분리차단 · 롤백 보고[차단은 의도적 미수용]) + **자체 적발
      1건**(공용 헬퍼의 실패→0 관용을 전용 probe 로 교체). 뮤테이션 16/16 KILLED
- [x] 배포 + **첫 실전 게이트 동작 실측** — 2단계 배포에서 게이트가 **두 번 발화, 두 번 다 통과**
      (`ask-worker recreate=quiet` · `gateway recreate=quiet`, settle 재확인 로그 포함).
      5서비스 `7c2918a8` healthy · `/healthz` ok · gateway `StopTimeout` 120 → **330** 전환 실측 ·
      surge 잔재 0 · 강행 카운터 0(= 이 배포는 실제로 무중단).

## TASK-20260812T200000 배포 스파인 밖 재생성 봉인 (quiesce 게이트 공용화 + 사후 감사)
사용자 지시(2026-08-12): 2차 사고의 recreate 가 `deploy-web.sh` **밖**이었음을 확인하고
"직접 막는 장치도 이번에" 요청.

- [x] 근거 확정 — 17:33 시점 배포 lock mtime 이 13:00(직전 배포) 그대로였고 배포는 **17:49·18:07**
      에 따로 돌았다 → 17:30:05 게이트웨이 recreate 는 배포 경로가 아니다(`restarts=0` = 재생성).
- [x] `bin/lib/quiesce.sh` 신설 — 게이트 구현을 **단일 정본**으로 분리(deploy-web.sh 는 source 만).
      호출측이 안 준 것만 기본값 주입해 **단독 source 가능**하게 설계.
- [x] `bin/safe-recreate.sh` — 배포 밖 재생성의 **인가된 진입점**. 배포와 같은 라이브러리로 판정,
      fail-closed + `--force-busy`, web replica 동시 지정 거부, compose 미존재 서비스 거부.
- [x] `Makefile` — `quiesce-guard` 타깃 신설 후 `up`·`down` 에 전치(=`restart` 도 커버).
      `make safe-recreate SVC=…` · `make recreate-audit` 진입점 추가.
- [x] `bin/recreate-audit.sh` — raw `docker compose` 는 막을 수 없으므로 **보이게** 만든다:
      인가 경로 2종이 같은 스탬프 파일에 남기고, 컨테이너 `StartedAt` 과 대조해 우회 재생성을
      사후 적발(`unknown`/`UNSANCTIONED` 구분, 위반 시 exit 1).
- [x] 배포 스탬프 3지점 배선(web replica·워커·gateway) — 한 곳이라도 빠지면 감사가 오탐한다.
- [x] **라이브 검증에서 결함 3건 적발·수정**: ① `err "…\`/livez\`…"` 백틱이 **명령 치환**으로
      해석돼 `/livez` 실행 시도 + 메시지 파손(**이미 머지된 코드의 버그**) ② 컨테이너 재생성 중
      `exec` 실패를 'env 미설정=inprocess' 로 오독해 엉뚱한 사유로 게이트 차단 ③ 단독 source 시
      `QUIESCE_FORCED` 미초기화로 `quiesce_summary` 가 산술 비교 오류.
- [x] 라이브 재검증 — web probe 가 `unknown` 인 동안 **차단**하고, 조용해진 뒤 settle 재확인을
      거쳐 통과(`mode=worker`, `sample=0|0|unknown` → `quiet`). 감사 도구도 라이브 판독 확인.
- [x] 테스트 34 PASS(신규 8) · **뮤테이션 7/7 KILLED** · ruff/bash -n OK
- [ ] 배포 + POST-DEPLOY(스탬프 생성 확인 → 감사 `ok` 전이)

## TASK-20260814T120000 ask-worker surge 교대 (바쁜 시간대 배포 완결 + 연쇄 차단 해소)

### 9. Requested Scope (요청 범위)
사용자 요청(2026-08-14): "서비스 내 배포를 모두 무중단으로 진행" 요청이 **부분 완료**로 끝났고
(web=신 커밋 / ask-worker·ops-scheduler·ext-tool-mcp=구버전), "배포 및 서비스가 중단되는 이슈가
없도록 환경을 개선" 하라는 후속 요청.

- [x] R1 바쁜 시간대에도 ask-worker 배포가 **완결**된다(전역 정적 창 비의존) — 산출물:
      `rollout_ask_worker_via_surge` + `ask-worker-surge` 서비스, `test_ask_surge_rollout.py` 순서 계약
- [x] R2 진행 중 사용자 run 이 배포로 끊기지 않는다(기존 무중단 유지) — 산출물: drain-to-completion
      (예산 60s→1800s, stop_grace 1830s) + `drain_stop_ask` 완주 관측·초과 보고
- [x] R3 한 워커의 미교체가 무관한 워커 배포를 **연쇄 차단하지 않는다** — 산출물: rc 1/2 분리 +
      `deferred` 누적 후 계속 롤아웃, `test_ask_worker_deferral_does_not_block_unrelated_workers`
- [x] R4 부분 완료를 "배포 완료" 로 보고하지 않는다 — 산출물: `verify_workers_at_sha`(컨테이너
      GIT_COMMIT 실측) 통과 후에만 `agent_current` 기록, post-deploy 체크리스트 [2]·[2b]

### Task Queue
- [x] T1 근본원인 확정 — 라이브 실측으로 quiesce 게이트의 전제 붕괴 입증: 유입 7~10분 간격
      (11:08·11:18·11:25·11:27·11:30·11:41) + run p95 691s → 상한 900s 안에 전역 정적 창 없음.
      `deploy_workers` 의 `return 1` 이 ask-worker 뒤 워커까지 연쇄 차단(실측: insight 만 신 sha).
      state 오염도 확인 — `agent_current=95f5ea0f` 인데 insight-worker 는 `e545796f` 로 가동 중.
- [x] T2 설계 판정 — ask-worker 는 gateway 와 **다르다**: HTTP 소켓이 아니라 PG 큐 소비자이고
      claim 이 `FOR UPDATE SKIP LOCKED`+lease fencing 이라 다중 인스턴스 exactly-once 다.
      따라서 "조용해지기를 기다린다" 가 아니라 **"받는 쪽을 먼저 세운다"** 가 성립한다.
- [x] T3 `docker-compose.yml` — `ask-worker-surge`(profile deploy-surge·restart no·본체 대칭
      stop_grace) 신설 + 본체 drain 예산 60s→1800s / stop_grace 70s→1830s.
- [x] T4 `bin/deploy-web.sh` — `rollout_ask_worker_via_surge`(surge healthy → 본체 drain →
      본체 교체 → surge 정리) · `drain_stop_ask` · `sweep_leaked_ask_surge` · `DC_SURGE_PROD` ·
      pin overlay 에 surge 포함 · 롤백 경로의 surge 선제거.
- [x] T5 실패 격리 + 완결 판정 — rc 2(본체 무접촉)는 나머지 워커를 계속 롤아웃하고,
      `verify_workers_at_sha` 가 **컨테이너에서 GIT_COMMIT 을 재판독**해 전부 도달했을 때만
      `agent_current` 를 기록한다(부분 완료 ≠ 완료).
- [x] T6 liveness 계층 분리 — `ask.py` 전용 데몬 스레드 + 인스턴스-local alive 파일,
      `healthcheck_ask_worker.py` 가 그 파일을 우선 판독(KV 는 구 이미지 폴백).
      **surge 공존 창에서 공유 KV 가 false-pass/false-fail 을 만드는** 결함 선제 차단.
- [x] T7 테스트 — `test_ask_surge_rollout.py` 신설(26건) + `test_quiesce_gate.py` 범위 정정.
      feature-0014 allowlist 확장의 전제(web replica 미접촉)를 별도 테스트로 잠금.
- [x] T8 **CI 갭 수정(부수 발견)** — `.github/workflows/ci.yml` · `Makefile test` 가 경로를
      명시해 `testpaths` 의 feature-0014/0020 이 **한 번도 실행되지 않았다**. 경로 추가 +
      `test_edge_rolling_gate.py` 의 f-string 백슬래시(py3.11 SyntaxError) 수정 —
      그 파일은 CI 파이썬에서 **collection 자체가 불가**했다. `PyYAML` 개발 의존 명시.
- [x] T9 전체 스위트 실행 — 귀책 실패 0. pre-existing 1건(`chattr` 미설치 환경 의존,
      main 기준선에서 동일 재현).
- [x] T10 verify-completion → commit → PR #1295 → 머지(73c02c71)
- [x] T11 라이브 배포 + POST-DEPLOY 검증 — exit 0 · 6서비스 전부 73c02c71 · surge 잔존 0 · 엣지 503 0건 · alive 파일/healthcheck/drain 예산 실증 (TEST.md POST-DEPLOY 기록)

### Completion Checklist
- [x] R1~R4 가 구현되었다
- [x] 자동 테스트가 통과한다 (feature-0014+0020 98건, 전체 스위트 귀책 실패 0)
- [x] 웹/UI 변경 없음 — Windows-browser 검증 N/A (배포 스파인·워커 런타임만)
- [x] FUNCTION.md 가 현재 동작과 일치한다
- [x] MODIFY.md / REVIEW.md / TEST.md 기록
- [x] verify-completion --pre-commit PASS
- [x] Git 커밋 + 원격 동기화 (PR #1295 머지 73c02c71)
- [x] (deploy-backed) 라이브 재배포 검증 — exit 0 + 전 서비스 SHA 일치 + 엣지 무중단 실측
