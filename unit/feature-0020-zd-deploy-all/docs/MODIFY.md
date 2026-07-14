---
doc_type: MODIFY
feature_id: feature-0020-zd-deploy-all
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260714T104500-ai-claude-feature-0020-zd-deploy-all
- Date: 2026-07-14
- Related Requirement: REQ-20260714T101500-zd-deploy-all (AC-1~5)
- Summary: 무중단 배포 커버리지 완성 — deploy 스파인(deploy-web.sh)에 워커(insight/ask)
  자동 롤아웃·bedrock-gateway surge 무중단 교체·caddy 이미지 드리프트 reconcile 를 추가하고,
  alembic 직접 호출 stale-image 가드·워커 healthcheck 견고화·라이브 적용 미커밋 compose
  운영 튜닝 정식 커밋·Makefile 타깃(deploy-all/deploy-workers/ask-worker-*)을 반영.
- Files:
  - `bin/deploy-web.sh` — 워커 phase(`build_agent_image`/`deploy_workers`/`rollback_workers`/
    `wait_worker_healthy`), gateway surge(`deploy_gateway_reconcile`), pin overlay 확장
    (web+agent 2이미지), `build_service_image` 일반화(feature-0017 게이트 로직 공용화),
    state 파일 key=value 다중화(`state_get`/`state_set` — dry-run 실기록 결함 동반 수정),
    scope 플래그(`--web-only`/`--workers-only`/`--force-gateway`), `--rollback` 워커 확장,
    caddy 이미지 드리프트 recreate, TLS preflight caddy 대조 블록의 무메시지 사망 결함 수정
    (`ps caddy`→`ps -q` 실존 가드 — cold host 잠복 버그), wait_ready/predrain/soak dry-run 가드,
    구 `worker_divergence_warn`(WARN-only) 제거.
  - `docker-compose.yml` — insight/ask healthcheck timeout 10s→30s(부하 오탐), bedrock-gateway
    `stop_grace_period: 120s`, 신규 `bedrock-gateway-surge`(profile deploy-surge, DNS alias),
    라이브 적용분 운영 튜닝 verbatim 커밋(insight env 7종·restart on-failure:3·mysql/browser/
    ollama mem_limit·OLLAMA_NUM_PARALLEL=1 — 라이브 컨테이너 실값 전수 대조 후 채택).
  - `bin/alembic-migrate.sh` — `MIGRATE_ALEMBIC_IMAGE` 미설정 + upgrade|stamp 직접 호출 시
    선행 `compose build agent`(stale-image head 오판 봉인, `MIGRATE_SKIP_REBUILD=1` escape).
  - `Makefile` — `deploy-all`/`deploy-web-only`/`deploy-workers` 타깃, `ask-worker-up/down/
    status/logs`, `up` 빌드 목록에 ask-worker 추가(cold up 공백).
  - `unit/feature-0014-zero-downtime-deploy/docs/RUNBOOK.md` — §9 수동 워커 재빌드 절차 폐기
    (스파인 자동화로 대체) + "insight-worker SIGTERM 핸들러 없음" stale 서술 정정(feature-0015
    기구현), §10 체크리스트 #2 갱신 (cross-cut).
- Impact: 배포 경로 통합 — `make deploy-web`(=deploy-all) 1회로 web·워커·gateway·caddy 가
  무중단/near-zero 롤아웃. 워커 이미지가 `repo-*` 무핀에서 `mysql-ai-agent:<sha>` 핀으로 전환
  (last-good 롤백 확보). 앱 런타임 코드 변경 0 (배포 인프라·compose·문서만).
- Rollback Notes: PR revert 후 기존 수동 절차로 복귀 가능. 워커 컨테이너는 revert 후 첫
  `docker compose up` 에서 `repo-*` 이미지로 자연 복귀. surge 서비스는 profile 뒤라 revert 전
  실행 중이면 `docker compose --profile deploy-surge rm -sf bedrock-gateway-surge` 로 정리.
