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
- [ ] T7 verify-completion → commit → PR → cycle-finalize
- [ ] T8 라이브 배포(deploy_scope: included) + POST-DEPLOY 검증(§16.3 deploy-backed)

## 4. In Progress
- T7 동기화.

## 5. Blocked
- 없음.

## 7. Completion Checklist
- [ ] 모든 REQ 의 AC 가 구현되었다
- [ ] 자동 테스트가 통과한다 (bash -n / dry-run / compose config; make test 회귀 무관 영역)
- [ ] 웹/UI 변경 없음 — Windows-browser 검증 N/A (UI 표면 없음, 사유 TEST.md 명시)
- [ ] FUNCTION.md 가 현재 동작과 일치한다
- [ ] MODIFY.md / REVIEW.md / REPORT.md / TEST.md 기록
- [ ] STATUS.md / ARCHITECTURE.md 반영
- [ ] verify-completion --pre-commit PASS
- [ ] Git 커밋 + 원격 동기화
- [ ] (deploy-backed) 라이브 재배포 검증 — cycle-finalize 후 실배포 + healthz PASS
