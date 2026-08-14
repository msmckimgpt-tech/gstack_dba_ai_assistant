---
doc_type: TEST
feature_id: feature-0020-zd-deploy-all
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- deploy 스파인 확장(워커 롤아웃·gateway surge·caddy 이미지 드리프트·scope 플래그)의
  정적 검증(bash -n)·dry-run 전 경로·compose config 정합(±deploy-surge profile)·pin overlay 병합.
- 라이브 재배포 검증(§16.3 deploy-backed 완료 기준): cycle-finalize 후 main 에서
  `sudo -E bin/deploy-web.sh` 실배포 — web soak·워커 healthy·gateway 무접촉/교체.
- 제외: 웹/UI 표면 없음 — **Windows-browser 검증 N/A (UI 표면 없는 배포 인프라 변경,
  §15.4.1 예외 사유 명시)**. MySQL/PG 엔진 재시작·HA (out of scope).

## 2. Test Cases
- TEST-20260714T104500-zd-deploy-all-1: `bash -n` deploy-web.sh·alembic-migrate.sh 구문 PASS.
- TEST-20260714T104500-zd-deploy-all-2: `docker compose -f docker-compose.yml config -q`
  (base) + `--profile deploy-surge` 모두 PASS, surge 서비스가 base 에서 비활성.
- TEST-20260714T104500-zd-deploy-all-3: pin overlay(web+agent 4핀) 병합 시 insight-worker 에
  `image: mysql-ai-agent:*` 적용 확인.
- TEST-20260714T104500-zd-deploy-all-4: dry-run 4 scope(기본/--workers-only/--web-only/
  --rollback) exit 0 + phase 로그(워커 롤아웃·gateway reconcile·state 무기록) 확인.
- TEST-20260714T104500-zd-deploy-all-5 (라이브, POST-DEPLOY): 실배포 1회 — web-a/b 대상 SHA
  soak PASS, insight/ask `mysql-ai-agent:<sha>` healthy, gateway 드리프트 판정 정상,
  edge /healthz 200 유지.

## 3. Test Run History

### Run 2026-07-14 (구현 cycle, worktree)
- Environment: CLI
- Scope: TEST-…-1 ~ TEST-…-4
- Result:
  - bash -n 2종 PASS.
  - compose config base/±surge-profile PASS (`BASE OK`/`SURGE PROFILE OK`).
  - pin overlay 병합 확인 — merged config 의 insight-worker 에 `image: mysql-ai-agent:test`.
  - dry-run: 기본 scope EXIT=0 (web build→agent build→migrate 게이트→롤링→caddy reconcile→
    soak→워커 롤아웃→gateway reconcile 전 phase 발화), --workers-only EXIT=0 (web 단계 skip),
    --web-only EXIT=0, --rollback EXIT=0 (web 핀 last-good + state 기록 dry 로깅).
  - 발견·수정: TLS preflight caddy 대조 무메시지 사망(cold host 잠복, `ps -q` 가드로 수정) /
    STATE_FILE dry-run 실기록(state_set 무기록화) — REVIEW.md 근거 6.
- Verdict: PASS (정적·dry-run 범위)

<!-- 라이브 Run 은 test-runs.d/ fragment 로 기록 (§5.3) -->

## 4. Untested Areas
- 워커 롤아웃 실패 → agent last-good 자동 롤백 경로: 첫 배포는 last-good 부재라 라이브 재현
  불가(의도적 미주입 실패 실험은 라이브 위험) — dry-run·코드 리뷰로 확인, 차후 배포에서 자연 검증.
- gateway surge 실교체: 본 cycle 은 gateway 드리프트가 없어 무접촉 경로만 라이브 검증
  (교체 경로는 --force-gateway 로 유도 가능하나 라이브 LLM 창 리스크로 보류 — 다음 gateway
  설정 변경 배포에서 자연 검증).

### 20260812T140000-quiesce-gate 워커·gateway 교체 quiesce 게이트 (Major §12.3 — 배포 스파인, 2026-08-12) — **Environment: unit(shell 함수 격리 실행) + 라이브 SQL 대조 (배포 절차만 변경 — 런타임/웹 자산 무변경 → CHECK#13 미해당)**
- **자동 검증 — PASS**: `unit/feature-0020-zd-deploy-all/tests/test_quiesce_gate.py` **26 passed**(§18.8 흡수 후). 검증 방식은 `bin/deploy-web.sh` 에서 quiesce 함수 블록만 떼어내 stub 로그·stub 신호와 함께 `bash -c` 로 실제 실행하는 것 — 문자열 대조가 아니라 **동작**을 본다(`gateway_grace_drift_warn` 검증과 같은 패턴).
  - 판정 6: 조용→진행 · 바쁨→상한까지 대기 후 **ABORT** · 도중 조용해지면 즉시 진행(폴링 실동작을 파일 카운터로 확인) · web `active_streams` 단독으로도 차단 · **양 신호 관측 불가→ABORT**(vacuous pass 방지) · 한쪽만 관측 가능하면 그쪽으로 판정.
  - `--force-busy` 3: 통과하되 `FORCED` 기록 + **"무중단이 아니었다"** 보고 · 조용 통과 시 "끊지 않았다" · 플래그 없으면 ABORT.
  - 배선 4: ask-worker recreate **앞**(그리고 배경 워커엔 미적용) · gateway 는 surge healthy **뒤** recreate **앞** · 게이트 중단 시 surge 정리 · 성공 경로에 `quiesce_summary` 발화.
  - 계약 5: heartbeat 신선도 필터 존재 · 상한 기본값이 실측 p95(691s) 이상 · `--force-busy` 파싱+usage 등재 · **testpaths 자기등재** · `bash -n`.
- **뮤테이션 16/16 KILLED**(초판 9 + 전용 probe 2 + 패널 흡수 5): 관측불가→0 취급 · 워커 게이트 제거 · FORCED 카운터 무력화 · timeout→진행 · heartbeat 필터 제거 · web 신호 무시 · 중단 시 surge 미정리 · 상한 60s 축소 · testpaths 등재 제거.
- **회귀**: 전 testpaths(feature-0002/0003/0020) 실패 **선재 2건뿐** — ① `test_oauth_exhaustion_gate::test_write_failure_...`(컨테이너에 `chattr` 부재) ② `test_edge_rolling_gate.py` **수집 오류**(`SyntaxError: f-string expression part cannot include a backslash` — 검증 컨테이너가 Python **3.11**.15 인데 그 문법은 3.12+ 전용). **둘 다 pristine main 대조에서 동일** → 회귀 0. ruff clean · `bash -n` OK · `tomllib` parse OK.
- **라이브 대조(읽기 전용)**: 운영 primary 에서 게이트 쿼리를 실제 실행 — `SELECT count(*) … status='running' AND heartbeat_at > now() - interval '90 seconds'` → `0`(현재 진행 중 사용자 run 없음). 좀비 필터 대조(all_running=0 / fresh=0)도 함께 확인.
- **Pass/Fail: PASS**(단위 + 뮤테이션 + 회귀 + 라이브 SQL).
- **라이브 실측 필요분(POST-DEPLOY, append 예정)**: ① 첫 실전 배포 로그에 `quiesce: ask-worker recreate=quiet · gateway recreate=quiet` 가 실제로 찍히는지 ② 진행 중 대화가 있는 상태에서 배포를 걸어 **대기 → 통과** 궤적이 관측되는지(합성 부하로 재현) ③ 배포 전후 `ask_jobs` 에 `attempts>1` 재큐가 늘지 않는지(= 아무것도 죽이지 않았다는 사후 증거).

- **[POST-DEPLOY 2026-08-12] quiesce 게이트 라이브 실증 (PASS)** — PR #1219 merge main `7c2918a8` →
  **2단계 배포**(사용자 선택). 게이트가 **실전에서 두 번 발화했고 두 번 다 통과**했다.
  - **1단계**(`sudo -E bin/deploy-web.sh`) — web 롤링 + soak 통과 → 워커 롤아웃 직전 게이트 발화:
    `=== quiesce 게이트: 진행 중 사용자 run 이 끝나기를 대기 (ask-worker recreate, 상한 900s) ===`
    → 최종 요약 `quiesce: ask-worker recreate=quiet — 진행 중 사용자 run 을 끊지 않았다.`
    gateway 는 `드리프트 없음 — 무접촉(blip 0)`(compose `stop_grace_period` 는 드리프트 판정
    대상이 아님 — 2단계 분리의 근거를 실측으로 확인).
  - **2단계**(`--force-gateway`) — 멱등 skip(web/워커 이미 대상 SHA) → surge up→healthy →
    게이트 `gateway recreate: 진행 중 run 0 (settle 3s 재확인, 대기 0s) — 교체 진행.` →
    본체 recreate → healthy → `gateway 무중단 교체 완료.` → surge Removed →
    `quiesce: gateway recreate=quiet — 진행 중 사용자 run 을 끊지 않았다.`
  - **settle 재확인이 로그에 실제로 찍혔다** — 스냅샷 1장이 아니라 두 표본으로 판정했다는 증거.
  - **배포 결과**: 5서비스 `GIT_COMMIT=7c2918a8` **전부 healthy**(web-a·web-b·ask-worker·
    insight-worker·ops-scheduler). edge `/healthz` = `status=ok · git_commit=7c2918a8 ·
    mysql_ok=true · pg_ok=true`. surge 잔재 0.
  - **grace 적용 실증**: 교체 **전** `docker inspect` = `StopTimeout=120`, 교체 **후** = **`330`**.
    즉 compose 값 변경이 recreate 없이는 발효되지 않는다는 사실도 함께 실측됐다(2단계가 필요했던
    이유 — 1단계만 돌렸다면 앱 재시도만 발효되고 배포 층은 구 예산 그대로였을 것).
  - **끊긴 요청 0**: 두 게이트 모두 `=quiet` 이고 강행 카운터 0 → 이 배포는 **실제로 무중단**이었다.
- **[POST-DEPLOY 2026-08-12] 배포본 런타임 실증 (ask-worker `7c2918a8`)** — 앱 층 봉인(PR #1217)이
  같은 이미지에 함께 실려 있음을 확인:
  상수 `RETRY_MAX=2 · BASE=1.5s · CAP=8.0s · SLOW_RATIO=0.5 · CANCEL_POLL=1.0s` ·
  `Connection error.` → `transient / timeout_class=False / 한국어 안내 / confirmed=False`(글로벌
  배너 비오염) · `Request timed out.` → `transient / timeout_class=True` ·
  401 auth → `permanent`(재시도 안 함) · 504 `Gateway timeout` → `timeout_class=True`(패널 P1-1) ·
  느린 실패 예산 게이트 `_llm_retry_allowed(...attempt_elapsed=280s, remaining=10s) = False`.
  히스토리 창 교정도 배포본에서 확인 — linear·windowed·branch **3경로 모두** `LIMIT-order=DESC` +
  `returns-ASC=True`.

### 20260812T200000-quiesce-out-of-band 배포 밖 재생성 봉인 (Major §12.3, 2026-08-12) — **Environment: unit + 라이브 실측(읽기 전용) (운영/배포 절차만 — 런타임 서빙 코드 변경 0 → CHECK#13 미해당)**
- **자동 검증 — PASS**: `test_quiesce_gate.py` **34 passed**(신규 8). 신규 축: 게이트가 공용 라이브러리에 있고 배포 스크립트에 중복 구현이 없음 · `safe-recreate.sh` 가 같은 라이브러리 + recreate **앞** 게이트 + web replica 동시 거부 · 인가 2경로가 **같은 스탬프 파일** + 배포 3지점 스탬프 · 감사가 `unknown`/`UNSANCTIONED` 구분 + 위반 시 exit 1 · `make up`/`down` 에 `quiesce-guard` 전치 · **라이브 적발 3건**(코드 줄 백틱 금지 · exec rc 분리 · 보고 변수 자체 초기화).
- **뮤테이션 7/7 KILLED**: `make up` 게이트 제거 · `make down` 게이트 제거 · safe-recreate 게이트 무력화 · 백틱 재도입 · exec rc 무시 · `QUIESCE_FORCED` 초기화 제거 · 배포 web replica 스탬프 제거.
- **하네스 정정(중요)**: 라이브러리가 knob 을 `DEPLOY_QUIESCE_*` env 로 **무조건 재설정**하므로, 테스트가 셸 변수로만 짧은 상한을 주면 출하 기본값 900s 가 이겨 **스위트가 멈춘다**(초판에서 실제로 10분 타임아웃). env 매핑으로 교정 + `subprocess` timeout 부여.
- **라이브 검증(읽기 전용, 결함 3건 적발)**: 실제 스택에 라이브러리를 source 해 실행 — 1차 시도에서 ① `/livez` 실행 시도(백틱) ② `mode=inprocess` 오판(exec 실패 오독) ③ `[: : integer expression expected`(보고 변수) 를 **동시에** 잡았다. 수정 후 재검증: `mode=worker` · 첫 표본 `0|0|unknown`(그 순간 web replica 재생성 중) → **차단·대기** → 15초 뒤 settle 재확인 통과 `quiet`. `bin/recreate-audit.sh` 도 실 `StartedAt` 4건 판독 + 스탬프 미배포를 `unknown` 으로 구분(위반 오탐 0, exit 0).
- **Pass/Fail: PASS**. 단위·뮤테이션·라이브 3층 모두 통과.
- **라이브 실측 필요분(POST-DEPLOY)**: ① 배포가 스탬프를 실제로 남기는지(3지점) ② 이후 `make recreate-audit` 가 `ok` 로 전이하는지 ③ `make safe-recreate SVC=…` 실전 1회.

### 20260814T120000-ask-surge-rollout ask-worker surge 교대 (Major §12.3, 2026-08-14) — **Environment: unit (배포 스파인 + 워커 종료 시맨틱 — 웹/UI 자산 변경 0 → CHECK#13 미해당)**
- **자동 검증 — PASS**: `test_ask_surge_rollout.py` **26 passed**(신규) + `test_quiesce_gate.py` 30 passed(범위 정정 1건) + `test_edge_rolling_gate.py` 42 passed = **feature-0014+0020 98 passed**. py3.11(agent 이미지) · py3.12(로컬) 양쪽 실행.
- **신규 축**: surge 서비스가 profile 게이트 + `restart: "no"` · 본체와 drain 예산 **대칭** · stop_grace 가 실측 p95(691s)를 덮음 · 순서 계약(surge healthy → 본체 drain → 본체 교체 → surge 정리) · surge 정리가 본체 healthy **뒤** · surge 기동 실패 시 본체 무접촉(rc 2 분리) · surge 가 **같은 이미지 핀** 수령 · 미교체가 무관 워커를 막지 않음 · `agent_current` 는 완결 판정 **뒤에만** 기록 · 완결 판정이 컨테이너 실측 기반 · 롤백이 surge 선제거 · leaked surge sweep 이 본체 상태 확인 · drain 예산 초과가 요약에 보고됨 · 컨테이너-스코프 job 카운트가 조회 실패를 0 으로 읽지 않음 · liveness 이벤트가 `_SHUTDOWN` 과 분리 · liveness 스레드가 메인 루프 **전에** 시작 · healthcheck 가 로컬 파일 우선 · alive 파일 원자 교체 · 종료 시 alive 파일 제거 · 신규 knob 이 config 공개 목록에 등재.
- **기존 계약 충돌 검사**: feature-0014 `test_g1b2_no_replica_recreate_outside_the_gated_helper` 가 신규 3함수를 offender 로 적발 → allowlist 확장 + **그 확장의 전제(web replica 미접촉)를 별도 테스트 3건으로 잠금**(allowlist 확장이 테스트를 약화시키지 않도록).
- **하네스 결함 적발(가장 큰 발견)**: CI(`ci.yml`)와 `Makefile test` 가 pytest 경로를 명시해 `pytest.ini` 의 `testpaths`(feature-0014/0020)가 **무시되고 있었다** — 배포 무중단 불변식 테스트가 CI 에서 한 번도 실행된 적 없음. 더해 `test_edge_rolling_gate.py` 는 f-string 안 백슬래시(PEP 701, 3.12+)로 **CI 파이썬 3.11 에서 collection 자체가 불가**했다(로컬 3.12 에서만 통과했으므로 아무도 몰랐다). 경로 추가 + 3.11 호환 수정 + `PyYAML` 개발 의존 명시로 해소. 이후 3.11 컨테이너에서 98건 통과 확인.
- **전체 스위트**: feature-0002/0003/0023/0014/0020 통합 실행 — **귀책 실패 0**. pre-existing 1건(`test_oauth_exhaustion_gate.py::test_write_failure_after_successful_post_cannot_kill_slot_selection`, `chattr` 미설치 환경 의존 — **main 기준선(25637d1c)에서 동일 재현** 확인).
- **정적 검증**: `bash -n` (deploy-web.sh · safe-recreate.sh) · `py_compile` (ask.py · healthcheck · config.py) · compose YAML 구조 단정 · `--help` 출력 정합(usage sed 범위 갱신 반영).
- **Pass/Fail: PASS** (단위 + 정적).
- **라이브 실측 필요분(POST-DEPLOY)**: ① surge 컨테이너 생성 → 본체 drain(완주 로그) → 본체 신 sha healthy → surge 소멸 궤적 ② 그 창에 사용자 run 이 끊기지 않음 ③ 전 워커 GIT_COMMIT 일치(완결 판정 `ok`) ④ `?v=` 자산/엣지 무관(웹 미접촉 배포 시).

#### [POST-DEPLOY 2026-08-14] surge 교대 라이브 실증 (main `73c02c71`, exit 0)
- **교대 궤적(로그 실측)**: `ask-worker-surge-1 Created → Started` → `surge healthy — 이 시점부터
  신규 job 은 surge(신 코드)가 가져간다` → `drain-stop: 본체(예산 1800s, 보유 0)` → `3s 만에 완주
  종료(보유 0→0) — 끊긴 run 없음` → `recreate ask-worker → 73c02c71` → `healthy(GIT_COMMIT=73c02c71)`
  → `drain-stop: surge` → `Removed`. **설계한 순서 그대로 작동**.
- **완결 판정 발효**: `워커 완결 판정 (서비스별 GIT_COMMIT 실측)` 통과 후 `워커 롤아웃 완료`.
  실물 대조 — web-a/web-b/insight-worker/ask-worker/ops-scheduler/ext-tool-mcp **6서비스 전부
  `73c02c71`**. 종전 배포에서 발생하던 "web 만 신 코드" 혼합이 재현되지 않았다.
- **surge 잔존 0**: `--profile deploy-surge ps -q ask-worker-surge` 빈 출력(체크리스트 [2b]).
- **엣지 무중단**: `no upstreams available` **0건**(15분 창).
- **quiesce 요약**: `ask-worker 본체=drained(3s) · ask-worker surge=drained(3s) — 진행 중 사용자
  run 을 끊지 않았다.` 강행 카운터 0.
- **신 liveness 계층 실증(배포본 런타임)**: `/tmp/ask-worker.alive` 존재(내용 `2026-08-14T03:47:48+00:00`,
  age 6s — 갱신 주기 10s 정상) · `healthcheck_ask_worker.py` **exit 0**(파일 기반 판정 경로) ·
  `AGENT_ASK_WORKER_DRAIN_SEC=1800` 발효(compose 값이 recreate 로 반영됨을 확인).
- **정직 — 이번에 실증되지 **않은** 축**:
  ① 배포 시점 `ask_jobs` running = **0**(유휴)이었다. 따라서 "바쁠 때 **기다리지 않고** 완결한다"
     는 핵심 주장은 **아직 궤적으로 관측되지 않았다** — 이번 실증은 "경로가 설계대로 돈다" 까지다.
     그 축은 다음 바쁜 시간대 배포에서 `보유 N→0` 과 3s 를 넘는 완주 시간으로 확인된다.
  ② 이번 교체에서 내려간 본체는 **구 이미지(`4491ad80`)** 라 구 drain 시맨틱(60s)으로 동작했다.
     신 예산(1800s)은 이번 recreate 로 발효됐으므로 **다음 배포부터** 완전한 완주 보장이 적용된다.
  ③ `DRAIN-TIMEOUT` 보고 경로(예산 초과)는 유휴 배포라 미발화 — 단위 테스트로만 잠겨 있다.
