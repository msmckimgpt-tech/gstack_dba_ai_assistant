---
doc_type: FUNCTION
feature_id: feature-0020-zd-deploy-all
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
feature-0014(web)·0015(위생)·0016-zd(PG/Caddy)·0017(빌드게이트)로 구축된 무중단 배포를
**배포가 필요한 나머지 모든 부분**으로 완성한다: ① 워커(insight-worker·ask-worker) 코드
배포를 deploy 스파인에 통합(자동 재빌드·SHA 핀·순차 recreate·헬스 게이트·last-good 롤백),
② bedrock-gateway(LLM 단일 관문)를 surge(임시 2번째 replica) 방식으로 무중단 재배포,
③ `alembic-migrate.sh` 직접 호출의 stale-image 폴백 가드, ④ caddy 이미지 드리프트 reconcile,
⑤ 워커 healthcheck 견고화(10s timeout 오탐 해소) + 라이브 적용 상태였던 미커밋 compose 운영
튜닝의 정식 커밋(live-truth 정합). 코드 거주: `bin/deploy-web.sh`(feature-0014 스파인 확장,
cross-cut)·`docker-compose.yml`·`Makefile`·`bin/alembic-migrate.sh`.

## 2. Goal
- REQ-20260714T101500-zd-deploy-all: 프로젝트 내 배포가 필요한 모든 부분(사용자 대면 경로의
  전 서비스)에 대해, 한 번의 배포 명령으로 사용자 체감 중단 없이(zero/near-zero) 최신
  origin/main 코드·설정이 롤아웃되도록 구성한다.
  - AC-20260714T101500-zd-deploy-all-1: `sudo -E bin/deploy-web.sh` 1회 실행이 web 롤링에
    이어 insight-worker·ask-worker 를 fresh 이미지(`mysql-ai-agent:<sha>`, GIT_COMMIT 라벨
    검증)로 순차 recreate 하고, 각 워커가 healthy 게이트를 통과한다. 실패 시 워커만
    last-good 이미지로 자동 롤백한다. (기존 WARN-only divergence 해소)
  - AC-20260714T101500-zd-deploy-all-2: bedrock-gateway 는 이미지/설정 드리프트가 있을 때만
    surge replica(동일 DNS alias) 기동→healthy→본체 recreate→surge graceful 종료 순서로
    재배포되어, 재배포 창에도 신규 LLM 요청이 실패하지 않는다(steady-state 리소스 증가 0).
  - AC-20260714T101500-zd-deploy-all-3: `bin/alembic-migrate.sh` 를 `MIGRATE_ALEMBIC_IMAGE`
    없이 직접 호출해도 stale agent 이미지로 head 를 오판하지 않는다(선행 재빌드 기본 +
    명시 escape).
  - AC-20260714T101500-zd-deploy-all-4: 워커 healthcheck 가 부하 시 timeout 오탐(라이브
    16h unhealthy 실측)을 내지 않도록 견고화되고, 라이브에 이미 적용돼 있던 미커밋 compose
    운영 튜닝(insight-worker env·mem_limit·OLLAMA_NUM_PARALLEL)이 정식 커밋되어 이후 배포가
    라이브 설정을 되돌리지 않는다.
  - AC-20260714T101500-zd-deploy-all-5: `make up` cold start 가 ask-worker 이미지를 포함해
    빌드하며, ask-worker 운영 타깃(up/down/logs)과 `make deploy-all` 진입점이 존재한다.

## 3. In Scope
- `bin/deploy-web.sh` 확장: 워커 배포 phase(빌드-once·핀·순차 recreate·헬스 게이트·롤백),
  gateway surge reconcile phase, caddy 이미지 드리프트 reconcile, `--web-only`/`--workers-only`/
  `--force-gateway` 플래그, `--rollback` 의 워커 포함 확장.
- `docker-compose.yml`: 워커 healthcheck timeout 상향, bedrock-gateway `stop_grace_period` 상향
  (in-flight LLM drain), `bedrock-gateway-surge` 서비스(profile `deploy-surge`, DNS alias),
  라이브 적용분 운영 튜닝 커밋(verbatim).
- `bin/alembic-migrate.sh`: 직접 호출 폴백 가드(선행 `compose build agent`).
- `Makefile`: `deploy-all`, `ask-worker-*` 타깃, `up` 빌드 목록 정정.
- feature-0014 RUNBOOK/스크립트 주석의 stale 서술 정정(insight-worker graceful 기구현).

## 4. Out of Scope (선행 feature 의 선언 유지)
- DB 엔진(MySQL/PG) HA·failover·호스트/커널 무중단 — 단일 호스트 SPOF (feature-0015 ANCHOR).
- PG major 업그레이드 (feature-0016-zd), MySQL 엔진 재시작 near-zero 래퍼(앞단 pooler 부재 —
  구조적 제약; MySQL DDL 은 online-DDL 게이트로 기커버).
- bedrock-gateway **상시** 2-replica (steady-state 메모리 예산 — 사람 결정 필요. 본 cycle 은
  배포 창 한정 surge 로 무중단만 달성).
- mcp(bytebase 외부 이미지·opt-in)·browser·embed-ollama·minio·pgbouncer 재시작 blip — 내부
  보조 도구/드문 이벤트로 수용(문서화). agent 서비스는 ephemeral `compose run` 이라 배포 개념 없음.
- cycle-finalize 자동 배포 배선(배포 트리거는 entry persona Phase 6.8 + deploy_scope 선언이 담당).

## 5. Inputs
- `origin/main` HEAD (coalesce 대상 SHA), `docker-compose.yml` base file-set only.
- 상태 파일: `artifacts/deploy/deploy-web.state`(current=/gateway_config_sha= 등),
  `deploy-web.last-good`(web), `deploy-agent.last-good`(워커, 신규).
- env 오버라이드: `DEPLOY_WORKER_READY_TIMEOUT`, `DEPLOY_GATEWAY_READY_TIMEOUT` 등.

## 6. Outputs
- 롤아웃된 컨테이너: web-a/web-b(`mysql-ai-web:<sha>`), insight-worker/ask-worker
  (`mysql-ai-agent:<sha>`), (드리프트 시) bedrock-gateway, (변경 시) caddy.
- 태그 회전: `mysql-ai-agent:{<sha>,current,last-good}` (web 과 동형, keep-N prune).
- 로그/체크리스트: 단계별 step 로그 + post_deploy_checklist.

## 7. Main Flow
1. (기존) flock → preflight → SHA coalesce → web 이미지 build-once → migrate 게이트+적용
   → web-a/web-b 순차 롤링(pre-drain·/readyz) → reconcile_caddy(설정+이미지) → soak/자동롤백.
2. (신규) agent 이미지 build-once(`mysql-ai-agent:<sha>`, GIT_COMMIT 검증, last-good 회전).
3. (신규) insight-worker → ask-worker 순차: recreate(--no-deps·핀 이미지) → healthy 게이트
   (start_period 존중) → 이미지 GIT_COMMIT 검증. 실패 시 워커군 last-good 롤백 + exit 1.
4. (신규) gateway reconcile: 드리프트(설정 sha 기록 대비 변경 || 이미지 ID 변경 || --force-gateway)
   시에만 surge up → healthy → 본체 recreate → healthy → surge stop(graceful)·rm.
5. 상태 기록(current sha, gateway_config_sha) + post_deploy_checklist.

## 8. Edge Cases
- 워커가 배포 전부터 unhealthy: healthcheck 견고화(AC-4)로 오탐 해소를 선행하되, 게이트는
  recreate 후 신규 컨테이너의 health 만 판정(과거 상태 비참조).
- 워커 신규 이미지 결함: 워커만 last-good 롤백(web 은 이미 swap — expand/contract 가 혼합
  버전 안전을 보장). WARN 으로 혼합 상태 명시.
- surge 기동 실패: 본체 무접촉 ABORT(기존 gateway 유지 — 무중단 보존).
- gateway 설정 sha 최초 기록 부재: 기록만 하고 recreate 안 함(안전 기본).
- snap-docker metadata race: 기존 feature-0017 게이트 로직을 agent 이미지 빌드에 동일 적용.
- dry-run: 전 신규 phase 가 명령 출력만.

## 9. Dependencies
- feature-0014 `bin/deploy-web.sh` 스파인(확장 대상), feature-0017 빌드 게이트 패턴,
  feature-0015 워커 graceful(`_INSIGHT_SHUTDOWN`/`_SHUTDOWN`+lease requeue) — 본 cycle 은
  이를 전제로 배포 자동화만 얹는다.
- feature-0007 litellm gateway 구성(`litellm_config.yaml` bind), feature-0002 agent Dockerfile.

## Pre-approved Changes
- (전역 FIRST_REQUEST.md) `deploy_scope: included` — cycle-final 후 배포까지 사전 승인.
