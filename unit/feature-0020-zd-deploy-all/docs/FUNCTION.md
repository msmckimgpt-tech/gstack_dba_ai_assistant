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
  (in-flight LLM drain — **120s→330s, CHG-20260812T110000**: 120s 는 실측 라운드 지연 분포 안쪽
  이라 배포마다 in-flight 의 7.9%가 SIGKILL 됐다. surge 도 대칭. 덮이지 않는 구간(콘솔 타임아웃
  상향·연장 승인 run)은 앱 층 재시도가 backstop 이며 `deploy-web.sh` 가 드리프트를 경고한다),
  `bedrock-gateway-surge` 서비스(profile `deploy-surge`, DNS alias),
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
3. (신규) insight-worker → ask-worker → ops-scheduler → ext-tool-mcp 순차: recreate(--no-deps·핀
   이미지) → healthy 게이트(start_period 존중) → 이미지 GIT_COMMIT 검증.
   **ask-worker 만 surge 교대 경로**를 탄다(아래 §7-S). 실패는 두 종류로 갈린다:
   신 이미지 결함이면 워커군 last-good 롤백 + exit 1, **본체 무접촉 중단이면 나머지 워커를
   계속 롤아웃**한다(연쇄 차단 금지). 마지막에 컨테이너에서 GIT_COMMIT 을 재판독해 전부
   도달했을 때만 `agent_current` 를 기록한다(부분 완료 ≠ 완료).
4. (신규) gateway reconcile: 드리프트(설정 sha 기록 대비 변경 || 이미지 ID 변경 || --force-gateway)
   시에만 surge up → healthy → **quiesce 게이트** → 본체 recreate → healthy → surge stop·rm.
5. 상태 기록(current sha, gateway_config_sha) + **quiesce_summary** + post_deploy_checklist.

### §7-S. ask-worker surge 교대 — "받는 쪽을 먼저 세운다" (CHG-20260814T120000)
- **왜 §7-Q 를 안 쓰는가**: §7-Q 의 전제("붙어 있는 것은 옮길 수 없다")는 gateway 에는 맞지만
  ask-worker 에는 **성립하지 않는다**. ask-worker 는 HTTP 소켓이 아니라 **PG 큐 소비자**다 —
  신규 job 은 `ask_jobs` 에서 오고, claim 은 `FOR UPDATE SKIP LOCKED` + `lease_epoch` fencing 이라
  다중 인스턴스가 exactly-once 다(`_ask_conc` 스레드 다중화와 같은 계약).
- **왜 바꿨는가(실측)**: 전역 정적을 기다리는 방식은 바쁜 시간대에 **배포를 완결시키지 못했다** —
  유입 7~10분 간격 + run p95 691s 조합에서 상한 900s 안에 정적 창이 생기지 않는다. 사용자가 쓸수록
  배포가 안 되는 구조였고, 순차 롤아웃이라 ask-worker 뒤 워커까지 연쇄로 묶였다(2026-08-14 라이브).
- **절차(MUST 순서)**: surge up(신 이미지 핀) → surge healthy → **본체 drain-stop**(신규 claim 중지
  + 자기 in-flight 완주, 예산 `DEPLOY_ASK_DRAIN_TIMEOUT` 기본 1800s) → 본체 recreate → 본체 healthy
  → surge drain-stop·rm. 순서가 어긋나면 신규 job 을 받을 주체가 없는 창이 생긴다.
- **surge 는 DNS alias 가 필요 없다**(gateway 와의 차이) — 큐에서 스스로 pull 한다. 대신 **핀 이미지**
  는 반드시 받아야 한다(빠지면 compose 가 build 정의로 돌아가 교체 창의 신규 job 이 구 코드로 간다).
- **role 은 본체와 같게 유지한다** — role-scoped 고아 회수가 계속 성립해야 한다. 살아 있는 형제를
  뺏지 않는 근거는 heartbeat 신선도다(`reclaim_role_orphan_jobs` 의 self/heartbeat 술어).
- **liveness 는 인스턴스별로 판정한다(MUST)**: healthcheck 가 role 전역 KV 를 보면 공존 창에서
  ① 죽은 쪽도 healthy(false-pass) ② drain 중 본체는 unhealthy(false-fail)가 된다. 컨테이너-local
  alive 파일 + 메인 루프와 **분리된** liveness 스레드가 그 둘을 가른다(drain 은 죽어가는 중이 아니라
  run 을 마치는 중이다).
- **정직 표기**: drain 예산은 실측 max(2,024s)를 다 덮지 않는다. 초과분은 재큐되고 배포 말미 요약에
  `DRAIN-TIMEOUT` 으로 남는다 — 조용히 넘기면 "무중단이었다" 로 읽힌다(LRN-20260811T1557).
- **drain 관측은 hostname 기준이다(MUST, CHG-20260814T133000)**: 완주 여부는 "그 **인스턴스가**
  자기 이름으로 claim 한 running job" 으로 센다(`claimed_by LIKE '%-<hostname>-%'`). hostname 은
  **stop 전에** 확보해야 한다 — `docker compose ps -q` 는 running 만 반환하므로(라이브 실측),
  stop 후 컨테이너로 다시 조회하면 빈 값이 나와 **결과가 항상 0 인 상수**가 된다(vacuous pass).
  같은 이유로 surge 존재 확인은 `ps -aq` 다: leaked surge 는 대개 "stop 됐는데 rm 실패" 형태로
  남고, `ps -q` 는 정확히 그 형태를 놓친다.
- **잔존 run 은 성공이 아니다(MUST)**: 정상 종료했는데 그 인스턴스 소유 running 이 남았다면 완주도
  반납도 못 한 run 이다 → `=CUT` 기록 + 강행 카운터. 관측 실패는 `drained-unverified` 로 남기고
  조용함으로 읽지 않는다.
- **적용 범위**: 배포 스파인 한정. `bin/safe-recreate.sh` 의 ask-worker 경로는 여전히 §7-Q 를 쓴다
  (surge 인프라가 없다). 코드 반영이 목적이면 `make deploy-workers` 를 쓴다.

### §7-Q. quiesce 게이트 — "지금 이걸 내려도 되는가" (CHG-20260812T140000)
> **적용 대상 축소(CHG-20260814T120000)**: 배포 스파인에서 이 게이트는 이제 **gateway 전용**이다.
> ask-worker 는 §7-S 의 surge 교대를 쓴다. 배포 밖 경로(`safe-recreate.sh`·`make up/down`)는
> 종전대로 이 게이트를 그대로 쓴다.
- **왜 surge 만으로는 부족한가**: surge replica 는 DNS alias 로 **신규** 요청만 흡수한다.
  이미 본체 소켓에 붙은 in-flight 호출은 **프로세스 간 이전이 불가능**하다 — HTTP 요청도,
  실행 중 agent run 도. 종전엔 그 사실을 `stop_grace_period` 타이머로 덮었고(만료 시 SIGKILL),
  그것이 2026-08-12 사고의 기전이다. 그래서 "옮긴다" 가 아니라 **"붙어 있는 게 없을 때
  바꾼다"** 로 푼다.
- **관측 신호 2종을 합산한다(MUST)**: `ask_jobs.status='running'`(heartbeat 신선분만) +
  web replica `active_streams` 합. 실행 dispatch 가 worker/inprocess 두 모드라(TASK-0169)
  한쪽만 보면 다른 모드에서 게이트가 **공허하게 통과**한다.
- **fail-closed(MUST)**: 상한 초과도, 양 신호 관측 불가도 **중단**이다. 중단하면 구버전이 계속
  서빙해 무중단이 유지되지만, 강행하면 정확히 고치려는 사고가 재현된다(`predrain` 과 동일 자세).
  **관측 불가를 0 으로 읽지 않는다** — 그것이 게이트를 있으나 마나로 만드는 vacuous pass 다.
- **대상은 사용자 run 을 든 컴포넌트만**: ask-worker·gateway. insight-worker/ops-scheduler 는
  배경 작업(실패=degraded 기록 후 다음 cadence 재시도)이라 제외 — 걸면 유휴 대기만 늘고 얻는 게 없다.
- **강행은 보고된다**: `--force-busy` 통과 시 배포 말미에 "이 배포는 무중단이 아니었다" 를 남긴다.
  조용히 통과한 배포와 끊고 지나간 배포가 같은 "배포 완료" 로 보이면 안 된다(LRN-20260811T1557).
- **게이트는 배포 전용이 아니다(MUST, CHG-20260812T200000)**: 구현은 `bin/lib/quiesce.sh` 가 소유하고
  `deploy-web.sh` 는 source 만 한다. 게이트가 배포 스크립트 **안에만** 있으면
  `docker compose up -d` · `make up` · 단일 서비스 재기동이 전부 사각지대이고, 2026-08-12 17:30
  사고가 정확히 그 경로였다(배포 lock mtime 이 그 시각 이전 값 그대로, 배포는 17:49·18:07 에 따로 돌았다).
  - **인가된 out-of-band 경로** = `bin/safe-recreate.sh <svc>…`(= `make safe-recreate SVC=…`).
    배포와 같은 판정 · fail-closed · `--force-busy` · **web replica 동시 지정 거부**(전면 다운) ·
    compose 미존재 서비스 거부.
  - **평범한 운영 경로도 통과** — `make up`/`down`(→`restart`)은 `quiesce-guard` 를 전치로 갖는다.
  - **raw `docker compose` 는 막을 수 없다 → 보이게 만든다**: 인가 경로 2종이
    `artifacts/deploy/recreate-sanctioned.log` 에 스탬프를 남기고 `bin/recreate-audit.sh` 가
    컨테이너 `StartedAt` 과 대조해 우회를 사후 적발한다(`unknown` 은 스탬프 도입 이전 —
    위반과 구분해야 경보 피로를 피한다). 배포는 **web replica·워커·gateway 3지점** 모두 스탬프한다 —
    한 곳이라도 빠지면 감사가 정상 배포를 위반으로 오탐한다.
- **메시지에 백틱을 쓰지 않는다(MUST)**: 큰따옴표 안의 `` `...` `` 는 명령 치환이다. 초판이
  `err "… \`/livez\` …"` 로 적어 라이브에서 `/livez` 를 실행하려 했고 메시지도 파손됐다.
- **관측 실패와 '설정되지 않음' 을 구분한다(MUST)**: 컨테이너 재생성 중 `exec` 는 실패해 빈 값을
  준다. 그것을 "env 미설정 = 코드 기본값" 으로 읽으면 **게이트는 막되 사유가 틀린다**(운영자가
  엉뚱한 것을 의심한다). 종료코드를 보고 unknown 으로 분리한다.

## 8. Edge Cases
- 워커가 배포 전부터 unhealthy: healthcheck 견고화(AC-4)로 오탐 해소를 선행하되, 게이트는
  recreate 후 신규 컨테이너의 health 만 판정(과거 상태 비참조).
- 워커 신규 이미지 결함: 워커만 last-good 롤백(web 은 이미 swap — expand/contract 가 혼합
  버전 안전을 보장). WARN 으로 혼합 상태 명시.
- surge 기동 실패: 본체 무접촉 ABORT(기존 gateway 유지 — 무중단 보존).
- **quiesce 상한 초과**(바쁜 시간대 배포, **gateway 한정** — CHG-20260814T120000): 해당 phase 중단
  → 구 gateway 계속 서빙. 배포는 멱등이므로 조용한 시간에 재실행하면 이어서 완료된다. 즉시
  필요하면 `--force-busy`(끊기는 요청 수를 로그로 인지한 상태에서만).
  > ⚠ ask-worker 에 대해 이 항목이 말하던 "조용한 시간에 재실행" 은 **틀린 처방이었다**.
  > 실측에서 그 창은 낮 시간대에 열리지 않았고(유입 7~10분 간격 + p95 691s), 사람이 창을 노려야
  > 한다는 요구 자체가 시급한 변경(보안 게이트)의 라이브 도달을 막았다. §7-S 로 대체.
- **ask-worker surge 기동 실패**: 본체 무접촉 ABORT(구 워커가 계속 처리) + surge 정리. 나머지
  워커는 계속 롤아웃되고, 배포는 **부분 완료로 정직 보고**된다(`agent_current` 미기록 → 다음
  실행이 멱등하게 이어서 완료).
- **ask-worker 본체가 신 이미지로 못 뜸**: surge 가 임시 처리 주체로 **의도적 유지**(제거하면
  처리 주체 0). 워커군 롤백 대상 — 롤백은 surge 를 먼저 제거한다(신 코드 격리 우선).
- **leaked ask surge**(직전 배포가 정리 전 종료): 다음 배포 시작 시 sweep. 본체가 healthy 일 때만
  정리한다(비정상이면 surge 가 유일 처리 주체일 수 있다). 그 사이에는 두 인스턴스가 함께 돈다 —
  post-deploy 체크리스트 [2b] 가 노출한다.
- **quiesce 관측 불가**(PG·web 양쪽 조회 실패): 중단. "조용한지 알 수 없다" 를 "조용하다" 로
  읽지 않는다.
- **죽은 워커의 stale `running` 행**: heartbeat 신선도 필터(`DEPLOY_QUIESCE_HEARTBEAT_FRESH`,
  기본 90s)로 제외 — 안 그러면 좀비 한 줄이 배포를 영구 차단한다.
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
