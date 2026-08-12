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
