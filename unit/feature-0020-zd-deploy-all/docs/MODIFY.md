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

## CHG-20260812T140000-quiesce-gate (워커·gateway 교체 quiesce 게이트 — 무중단의 마지막 구멍)
- Date: 2026-08-12
- Related: 사용자 지시(2026-08-12) — conv-audit `FR-llm-transient-failure-kills-run` 대응 중
  "배포 이슈가 나타나는 원인을 근본적으로 해소할 수 있도록 완벽한 무중단 배포 환경을 먼저
  구성" 요청. 선행 `CHG-20260812T110000-gateway-drain-grace`(grace 상향)의 후속·상위 봉인.
- **문제**: 무중단은 web 에만 완성돼 있었다. `predrain()` 은 상대 replica 의 엣지 후보 복귀와
  대상의 `active_streams==0` 을 **실제로 확인하고 아니면 배포를 중단**하는데, 워커·gateway 는
  **아무 상태도 보지 않고** `stop_grace_period` 타이머가 만료되면 SIGKILL 했다.
  실측이 그 타이머가 분포 안쪽임을 보여준다:
  - `ask_jobs` 30일 363건 — p50 **81s** · p95 **691s** · max **2,024s** · **60초 초과 66%**
    vs ask-worker drain **60s**(`stop_grace_period: 70s`).
  - LLM 라운드 30일 1,210건 — p95 **182s** vs gateway grace **120s**(당시).
  즉 배포마다 진행 중 사용자 run 의 상당수가 죽었고, `FR-ask-orphan-redeploy-dead-air` 의 회수
  로직은 **죽은 뒤의 복구**(재큐 → 전량 재실행 = 수 분 dead air)였을 뿐 안 죽이는 장치가 아니었다.
- **왜 surge 로는 안 되나(구조)**: surge replica 는 DNS alias 로 **신규** 요청만 흡수한다.
  이미 본체 소켓에 붙은 in-flight 호출은 **프로세스 간 이전이 불가능**하다 — HTTP 요청도,
  실행 중 agent run 도. 그래서 "옮긴다" 가 아니라 **"붙어 있는 게 없을 때 바꾼다"** 로 푼다.
- **가능성의 근거(측정)**: 시스템은 30일 중 **2.1% 만 busy**(363런 × 평균 152초). 조용한 순간을
  기다리는 것이 현실적이며, 실제로 대부분의 배포는 즉시 통과한다.
- **봉인**:
  1. `quiesce_user_runs` — 진행 중 사용자 run 을 **2신호 합산**으로 관측하고 0 이 될 때까지
     폴링(상한 `DEPLOY_QUIESCE_TIMEOUT`, 기본 900s = 실측 p95 691s 상회).
     · `ask_jobs.status='running'`(**heartbeat 신선분만** — 죽은 워커 한 줄이 배포를 영구
       차단하지 않게) · web replica `active_streams` 합.
     **두 신호를 다 보는 이유**: 실행 dispatch 가 worker/inprocess 두 모드라(TASK-0169)
     한쪽만 보면 다른 모드에서 게이트가 **공허하게 통과**한다.
  2. **fail-closed** — 상한 초과·양 신호 관측 불가 모두 **중단**. 중단하면 구버전이 계속 서빙해
     무중단이 유지되고, 강행하면 정확히 고치려는 사고가 재현된다(`predrain` 과 같은 자세).
     특히 "관측 불가를 0 으로 읽는" 것은 게이트를 있으나 마나로 만드는 vacuous pass 다.
  3. **배선** — ask-worker recreate 직전 / gateway 본체 recreate 직전(surge healthy **이후**).
     배경 워커(insight/ops)는 대상 아님 — 실패가 degraded 기록 후 다음 cadence 재시도라
     게이트를 걸면 유휴 대기만 늘고 얻는 게 없다.
  4. `--force-busy` 탈출구 + usage 등재. 강행하면 `quiesce_summary` 가 **"이 배포는 무중단이
     아니었다"** 를 배포 말미에 남긴다 — LRN-20260811T1557("성공 보고 ≠ 무중단")의 직접 적용.
     조용히 통과한 배포와 끊고 지나간 배포가 똑같이 "배포 완료" 로 보이면 안 된다.
  5. 게이트 중단 경로가 surge 를 정리한다(리뷰 M-1 이 잡았던 leaked surge 재발 방지).
- **ANCHOR 정정(§2 Alt-C · §3)**: 두 절이 "워커의 짧은 단일 재시작은 이미 사용자 무영향" ·
  "ask-worker in-flight run 은 lease requeue 로 새 컨테이너가 이어받는다" 고 적고 있었다.
  실측이 둘 다 반증한다 — 재시작은 run 의 66%를 죽였고, requeue 는 **이어받는 게 아니라
  전량 재실행**이다(부분 산출 이월은 원장에 이월 항목으로 남아 있다). 방향(스파인 확장·
  2-replica 미채택)은 그대로이므로 충돌이 아니라 **사실 정정**으로 §1~§3 을 갱신했다.
- **§18.8 적대 패널 흡수(P1 5건)**: 초판은 세 곳에서 **조용히 통과**했을 것이다 —
  ① **실행 모드**: `ask_jobs` 는 worker 모드에서만 정본이다. 코드 기본값 `inprocess` 에서
  `/api/ask` 는 web 안에서 직접 돌아 ask_jobs 행을 만들지 않고, `/livez` 의 `active_streams` 는
  **CSV export 와 SSE 프롬프트 자동작성만** 세고 `/api/ask` 를 세지 않는다(라이브 코드 확인:
  `_ACTIVE_STREAMS` 증가 지점 2곳). 즉 그 모드에서 게이트는 아무것도 못 보면서 '조용함' 을
  보고한다 — 있으나 마나가 아니라 **무중단이라고 믿게 만들어 더 나쁘다**. 현행 운영은
  `worker`(`.env` + 라이브 web-a `printenv` 확인)라 오늘은 유효하지만, 모드를 실측해 worker 가
  아니면 **거부**하도록 바꿨다.
  ② **unknown→0**: 초판은 한쪽 신호가 관측되면 다른 쪽 unknown 을 0 으로 읽었다. 두 신호는
  서로 다른 차원(worker 큐 vs web 스트림)이라 한쪽으로 다른 쪽을 증명할 수 없다 → 어떤 조합의
  unknown 도 차단.
  ③ **stale heartbeat**: 초판은 오래된 heartbeat 행을 조용히 제외했는데, 살아 있는 워커도 PG 가
  흔들리면 heartbeat 를 놓치고 그 사이 LLM 호출은 계속된다 → 분리 계상 + **차단**(로그로 구분).
  ④ **admission 경합**: 스냅샷 1장 뒤 recreate 사이에 들어온 run 이 죽는다 → settle 재확인
  (기본 3s)으로 창을 좁혔다. **완전한 barrier 는 아니다**(앱측 fence 필요 — 아래 이월).
  ⑤ **롤백**: 패널은 롤백에도 게이트를 요구했으나 **부분 수용**했다 — 롤백을 막으면 결함 있는
  배포가 그대로 남는다(feature-0014 가 엣지 게이트를 롤백에서 비차단으로 둔 것과 같은 근거).
  차단 대신 **끊고 가는 양을 관측·보고**하고 최종 요약의 강행 카운터에 반영한다.
- **자체 적발(패널 이전)**: `web_active_streams_total` 초판이 공용 `replica_active_streams` 를
  썼는데 그 헬퍼는 **조회 실패도 0 으로** 돌려준다(`|| echo 0` + 내부 fallback). 조회가 깨진
  배포는 항상 '조용함' 으로 통과했을 것 — 실패를 비-0 종료로 구분하는 전용 probe 로 교체.
- **정직 — 남은 창(이월)**: settle 재확인은 경합을 **좁힐 뿐 없애지 못한다**. 진짜 admission
  barrier 는 배포 창 동안 신규 `/api/ask` 를 fence 하는 **앱측 변경**(claim 루프가 읽는 pause
  플래그 등)이 필요하고, 그건 사용자 표면 동작 변경이라 별 cycle + 사람 판단 대상이다.
  현재 잔여 창 ≈ settle 재확인 후 recreate 명령까지의 1초 미만 × busy 2.1%.
- **의도적 미변경**: `AGENT_ASK_WORKER_DRAIN_SEC`(60) · ask-worker `stop_grace_period`(70s) 는
  손대지 않았다. 게이트가 통과한 뒤 recreate 까지의 창은 1초 미만이고 그 사이 새 run 이
  시작될 확률은 유휴 98% 환경에서 무시할 수준이며, 그 경우에도 기존 재큐 경로가 복구한다.
  반대로 이 값들을 p95(691s)까지 올리면 **배포와 무관한** 운영자 `down` 까지 그만큼 멎는다.
  (남은 꼬리는 원장 이월 — 아래 REPORT 참조.)
- Files: `bin/deploy-web.sh`, `pyproject.toml`(testpaths 등재),
  `unit/feature-0020-zd-deploy-all/tests/test_quiesce_gate.py`(신규),
  `unit/feature-0020-zd-deploy-all/docs/{TASK,MODIFY,FUNCTION,TEST,REVIEW,ANCHOR}.md`.
- Impact: 배포 절차만 변경. 런타임 서빙 코드·자원·보안 경계 무변경. 배포 소요는 **조건부**로
  늘어난다(진행 중 run 이 있을 때만 그만큼 대기 — 유휴 시 종전과 동일).
- Rollback Notes: `quiesce_gate` 호출 2곳을 제거하면 즉시 종전 동작. 다만 그 순간부터 배포는
  다시 진행 중 사용자 run 을 죽인다.

## CHG-20260812T160000-quiesce-postdeploy (POST-DEPLOY 기록 — 문서만)
- Date: 2026-08-12. `CHG-20260812T140000-quiesce-gate` 의 배포·실측 기록.
- **배포**: PR #1219 merge main `7c2918a8` → **2단계 배포**(사용자 선택: ① web·워커 → ② `--force-gateway`).
  게이트가 **실전에서 두 번 발화, 두 번 다 `=quiet`**. 5서비스 healthy · `/healthz` ok · surge 잔재 0.
- **가장 중요한 실측 2가지**:
  ① gateway `StopTimeout` 이 교체 **전 120 / 후 330** — compose 값 변경은 **recreate 없이는
     발효되지 않는다**. 1단계만 돌렸다면 앱 재시도만 살고 배포 층은 구 예산 그대로였을 것이다
     (드리프트 판정이 litellm config sha·이미지만 보기 때문 — 2단계 분리가 필요했던 이유).
  ② 게이트 로그에 **settle 재확인이 실제로 찍혔다** — 스냅샷 1장이 아니라 두 표본으로 판정했다.
- **정직**: 이번 배포는 시스템이 유휴(진행 중 run 0)라 게이트가 즉시 통과했다. **"바쁠 때 실제로
  기다렸다가 통과하는" 궤적은 아직 관측되지 않았다** — 합성 부하 또는 실사용 중 배포에서 확인 필요.
- Files: 본 문서 · `docs/TASK.md` · `docs/TEST.md` · `docs/LEARNINGS.md`(LRN 신설) ·
  conv-audit 원장(status 전이) · feature-0002 `docs/{TASK,TEST}.md`(cross-ref, 문서만).
- Impact: 문서만 — 런타임 0.
