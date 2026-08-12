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
