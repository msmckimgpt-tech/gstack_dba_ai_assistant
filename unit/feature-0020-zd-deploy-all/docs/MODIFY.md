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

## CHG-20260714T130500-ai-claude-feature-0020-zd-deploy-all
- Date: 2026-07-14
- Related Requirement: REQ-20260714T101500-zd-deploy-all (POST-DEPLOY 기록)
- Summary: 라이브 배포 검증 기록(docs-only) — test-runs.d fragment(TEST-…-5 PASS)·REPORT §2/§7
  동기화 결과·TASK 체크리스트 완결. 직전 docs 커밋(e4a02ec7)이 TASK 체크박스/MODIFY entry 누락
  상태로 파이프 exit-code 가림 탓에 verify FAIL 을 지나쳐 커밋된 것을 본 커밋이 정합(§16.3
  Step 3 — amend 금지, 새 commit 으로 수정).
- Files: unit/feature-0020-zd-deploy-all/docs/{TASK,MODIFY,REPORT,REVIEW}.md, docs/test-runs.d/
- Impact: 문서만 — 런타임 0.
- Rollback Notes: 해당 없음(기록).

## CHG-20260812T110000-gateway-drain-grace (cross-unit: 정본 feature-0002 CHG-20260812T110000-llm-transient-retry-resume)
- Date: 2026-08-12
- Related: conv-audit 원장 `FR-llm-transient-failure-kills-run` (사용자 명시 호출
  `/_dqa:conversation_audit`, 2026-08-12).
- Summary: `bedrock-gateway` / `bedrock-gateway-surge` 의 `stop_grace_period` **120s → 330s** +
  `bin/deploy-web.sh` 에 grace↔`AGENT_TIMEOUT_SEC` 드리프트 경고(`gateway_grace_drift_warn`)를
  gateway reconcile 진입부에 추가.
- 근거(측정): 120s 는 실측 분포 **안쪽**이었다 — 30일 대화 LLM 라운드 1,210건 중 **120초 초과
  96건(7.9%)**, p50 11.3s · p95 181.8s. 즉 gateway recreate 마다 진행 중이던 라운드의 약 8%가
  grace 만료 SIGKILL 로 죽었고, 앱은 그 예외로 run 을 통째로 폐기했다(2026-08-12 사고: 구
  컨테이너 SIGTERM 11:00:05 → SIGKILL 11:02:05 = 정확히 120s, 사용자 7분 40초 대기 후 유실).
  330s = 현행 `AGENT_TIMEOUT_SEC`(300s) + 여유 30s. surge 도 **대칭**으로 올렸다 — 교체 창에
  들어온 요청이 surge 로 가므로 그쪽에 같은 구멍을 남기면 안 된다.
- 비용은 조건부: uvicorn 은 in-flight 가 끝나는 즉시 종료하므로 한산할 때는 종전과 같고, 긴
  호출이 있을 때만 그만큼 기다린다. 그 대기 동안 신규 요청은 surge 가 DNS alias 로 흡수한다.
- **정직한 한계(§18.8 패널 P1-3)**: `AGENT_TIMEOUT_SEC` 은 콘솔에서 최대 3600s, 연장 승인 run 은
  per-call 900s 라 그 구간은 이 grace 로 덮이지 않는다. grace 를 3600s 로 키우면 배포가 한 시간
  멎을 수 있어 오답 — 덮이지 않는 구간은 **앱 층 일시 실패 재시도가 backstop** 이고, 운영값이
  grace 를 넘기면 배포마다 경고가 뜬다.
- Files: `docker-compose.yml`, `bin/deploy-web.sh`, 본 문서, `docs/FUNCTION.md`.
- Impact: 배포 시 gateway 정지 대기 상한만 변경. 런타임 서빙 동작·자원 사용 무변.
- Rollback Notes: compose 두 값을 120s 로 되돌리면 즉시 원복(다음 배포부터 적용). 단 앱 층
  재시도만으로는 8% 구간의 사용자 대기가 backoff 만큼 늘어난다.
