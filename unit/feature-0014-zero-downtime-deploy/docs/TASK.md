---
doc_type: TASK
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## TASK-20260909-auth-transition-deploy-recovery

로그인 화면 수정 PR #1652 배포에서 Caddy PID 예산 소진으로 사전 게이트가 중단됐다. 사용자 수정 요청의 배포 완료에 필요한 연속 복구 범위다. worktree `.worktrees/feature-0003-auth-transition`, 정책 SHA는 feature-0003 TASK와 동일하다.

### 2.1 Implementation Plan

1. `bin/deploy-web.sh:edge_peer_live`의 BusyBox HTTPS 자식 생성 경로를 호스트 curl로 교체한다. Caddy network namespace, 실제 resolver DNS, 공유 network IP, 실제 마운트 CA, 공개 Host/SNI, 정확한 200 및 제한시간을 검증한다.
2. `docker-compose.yml:caddy`에 init 회수 설정과 PID 여유 256을 기록한다. 실행 중 Caddy의 한도만 무중단 상향하며 재생성은 하지 않는다.
3. 종료 자식 증가 0, 잘못된 SNI 거부, DNS/HTTP/메타데이터 오류 실패, 기존 롤링 게이트 회귀와 독립 backend/qa/security 리뷰 후 배포 재개.

- [x] 실측 원인: threads 24 + ssl_client zombie 99, pids.current 123/max 128, 제한 도달 180회
- [x] 현재 PID 3619937 유지, 한도 256으로 내부 실행 복구
- [x] 근본 경로 수정, 관련 49 PASS, 실제 probe 5회 후 zombie 99 유지·잘못된 SNI 차단
- [x] PR #1656 병합, cf55c659 web-only 배포 exit 0·90초 soak PASS 및 설치 DQA 3회 왕복 성공


## TASK-20260909T140000-deploy-refresh — 완료 신호 게시
- 정본: feature-0003 TASK의 동명 항목. 사용자 요청으로 배포 완료→열린 DQA 자동 적용 승인.
- Plan: `bin/deploy-web.sh:publish_ui_release` / `bin/lib/ui-release.sh`로 실제 두 replica ready·revision·stamp 일치 및 배포 검증 성공 뒤 공유 manifest 원자 게시. 실패·혼합 버전·모의 실행에는 미게시, rollback 및 재시도 검증.
- AC: 미완료 배포는 새 release를 알리지 않는다. 완료 시 두 replica가 같은 완료 release를 반환한다. 기존 드레인·롤링·검증 게이트 유지.
- [ ] 완료 신호 구현·검증·출하 결과 기록

- [x] PR #1653/7fa75a51 배포 완료, 두 replica/edge 완료 메타데이터와 제품7파일 지문 확인. 설치 DQA 검증 진행 중.

## 1. Current Status
- State: in-progress
- Owner: AI (claude) / Human approved
- Priority: high
- Last Updated: 2026-06-30

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - `bin/migrate-lint.sh` (신규), `docs/CONVENTIONS.md`, `bin/verify-completion.sh`
  - `docker-compose.yml`, `docker-compose.override.yml`, `docker-compose.override.yml.example`
  - `unit/feature-0003-agent-web-ui/src/app.py` (`/readyz`·`/livez`·active-stream 카운터)
  - `bin/deploy-web.sh` (신규), `Makefile`, `bin/cycle-finalize.sh`
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`
  - 정적 자산 fingerprint: `unit/feature-0003-agent-web-ui/src/static/index.html` 등 + 빌드 단계
  - 본 feature `docs/*`, `docs/STATUS.md`, `docs/RELEASE_NOTES.md`
- **접근 방법:** Caddy 뒤 web-a/web-b 2-replica + one-at-a-time 롤링으로 항상 ≥1 healthy
  upstream 유지(true-zero, 비-SSE). 배포 스파인 `deploy-web.sh` 가 flock(전체 배포, origin/main
  coalesce)·단일 scoped-sudo·프로덕션 file-set 격리·TLS preflight·migrate 순서·post-cutover
  soak+자동 롤백을 소유. 마이그레이션 안전은 `migrate-lint.sh` 게이트로 강제. SSE 는 pre-drain,
  자산 스큐는 content-hash fingerprint 로 차단. `:18080` 직접 문 폐기, Caddy 단일화.
- **위험도:** Critical (라이브 DB 마이그레이션 안전 + 프로덕션 배포 자동화).

<!-- PLAN-APPROVED by ms.mckim.gpt (user) on 2026-06-30 -->
<!-- 승인 결정: 실행범위=Foundations+Tier2 끝까지 / :18080=Caddy :443 단일화 / SSE=pre-drain 게이트 -->

## 3. Task Queue
- [x] TASK-20260630T120100-migrate-lint: 마이그레이션 안전 게이트 + CONVENTIONS expand/contract 규칙 (P0a)
  ↳ 2026-07-28 실측: `bin/migrate-lint.sh` 실재 (feature-0021 cycle 의 test-runs 에서 실제 호출·PASS 기록).
- [x] TASK-20260630T120101-hostport-override: 호스트포트 이전 + stop_grace_period + :18080 폐기 (P0b)
  ↳ 2026-07-28 실측: `https://localhost:18080` 무응답(폐기 확인) · 443 이전 완료.
- [x] TASK-20260630T120102-readyz-livez: /readyz·/livez probe + active-stream 카운터 (P0d)
  ↳ 2026-07-28 실측: `/readyz` 200 · `/livez` 200 라이브 응답.
- [x] TASK-20260630T120103-deploy-spine: bin/deploy-web.sh (flock/sudo/TLS preflight/migrate/rollback) (P0c)
  ↳ 2026-07-28 실측: `bin/deploy-web.sh` 실재 (배포 canonical 경로로 상시 사용 중).
- [x] TASK-20260630T120104-two-replica: web→web-a/web-b + Caddy LB (P1)
  ↳ 2026-07-28 실측: `repo-web-a-1`·`repo-web-b-1` 2 replica 가동 + Caddy LB.
- [x] TASK-20260630T120105-sse-asset: SSE pre-drain + 자산 content-hash (P2)
  ↳ 2026-07-28 실측: asset stamp 파이프라인(`inject_asset_stamp`/`asset_stamp_verify`) 실재.
- [ ] TASK-20260630T120106-wire-tests-docs: cycle-finalize wire + 수용 테스트 + 정적 검증 + 문서 (P3)
- [x] TASK-20260713T073141-deploy-verify-checklist: 배포 후 사용자 인수 전 검증 체크리스트 상시화 (RUNBOOK §10 + deploy-web.sh `post_deploy_checklist` output-only + LEARNINGS). Minor §12.3, `bash -n` PASS. feature-0003 attach-user-version 회고 반영.

## 4. In Progress
- P0a~P3 순차 구현 중.

## 5. Blocked
- 없음 (PLAN-APPROVED 완료).

## 6. Done
- 설계 + 적대적 검증 (워크플로 wf_f176026a) 완료 — 8 failure mode gap + 완화책 도출.

## 7. Next Action
- P0a migrate-lint.sh 구현부터 순차 진행.

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 단위 테스트(unit test)가 통과한다 (정적 검증: compose config / caddy validate / bash -n / migrate-lint self-test)
- [ ] 전체/통합 테스트(integration test) — 라이브 롤링 zero-502 부하 + non-root dry-run 은 운영자 수행 (TEST.md §4 기록)
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 시)
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다

## 9. Requested Scope (요청 범위)

원 요청(2026-08-11): "최근 배포 과정 중 사용자들로부터 서비스가 멈춘다는 이슈가 자주 확인되었습니다.
이전에 무중단 배포를 구성한 것으로 알고 있는데 이와 같은 이슈가 나타나는 근본적인 원인을 분석 후
대응해주세요."

- [x] **(1) 근본 원인 분석** — 추정이 아니라 라이브 증거로 확정할 것.
      → 엣지 로그 실측: `no upstreams available` 71건/6h · 503 창 6회 × 12~17초 · duration 전부
        `lb_try_duration`(5.01s) 소진 · 창 중 active health 는 양쪽 `host is up` · 503 종료가 매 창
        "먼저 내린 replica 첫 실패 + fail_duration" 과 일치 · 롤링 간격 10초(StartedAt 실측).
- [x] **(2) 대응 — 원인 제거** — 롤링이 엣지 후보 복귀를 확인하고 미복귀면 중단(fail-closed).
- [x] **(3) 대응 — 재발 방지** — 그 불변식을 구조 테스트로 잠금(39건) + 그동안 수집조차 되지 않던
      `feature-0014/tests` 를 testpaths 에 등재.
- [x] **(4) 적대 검증** — codex P1 3건·P2 3건 전건 반영(hang·게이트 무의미화·소스파일 신뢰·주장범위·
      설정 인하 대가·테스트 vacuous 구멍).
- [x] **(5) 라이브 실증 완료 (2026-08-11 17:30~17:35, main 8cad9cd7)** — 배포 창
      `no upstreams available` = **0**, 요청 **172건 전부 200**(5xx·연결끊김 0). 수정 전 동일
      규모 창(12:40 배포: 111요청 중 503×8·502×1·끊김×1)과 대조된다. 게이트가 실제로 발동한
      로그도 확인: `web-b 엣지 passive fails=1 — 격리 해제 대기` → `복귀 확인(fails=0 +
      Caddy→web-b /livez 200)`. 이번 배포는 Caddyfile 변경으로 caddy recreate 까지 동반했는데
      그 blip 도 0 이었다.


## 20260711T1137-deploy-flake-hardening — 배포 스파인 flake 하드닝 (사용자 지시 2026-07-11 "나머지 작업 재개")

- [x] preflight_fileset: `docker compose config` stderr 포획 + rc≠0/web-a·b 미검출 시 2s backoff 3회 재시도 + 최종 실패 시 stderr·출력헤더 진단 덤프 (배경: 07-11 배포 6회 중 3회 간헐 실패 — 구코드는 stderr 유실로 진단 불가. 프로덕션 원인은 미확정 — 본 변경은 계측+재시도)
- [x] soak: 단발 edge 실패 → 2s 간격 **연속 3회 확증** 후에만 롤백 + **blip 회복 시 continue 전 RestartCount 재검**(패널: crash-loop 감시 공백) + **누적 4회(비연속) flapping 기준 병행**(패널: 교대 200/503 무감 해소); dependency_down 분기는 확증 이후(예산 보존)
- [x] auto_rollback + 수동 --rollback 경로 양쪽: 롤백 직후 단발 edge 판정 → **60s(3s 간격) 회복 대기** 후 판정 (워밍업 창 오판 해소, 경로 일관성 — 패널 지적)
- [x] 검증: bash -n · worktree dry-run 재현 — 실패 경로(env_file 부재가 stderr 에 원인 파일명까지 표시, 3회 재시도 후 정직 die) + happy path("OK — 두 replica 정의 확인" 도달) 양쪽 실증
- [x] §18.8 적대 패널: 아래 REVIEW 참조

## 20260711T2011-preflight-sigpipe-rootfix — preflight flake 근본 원인 수정 (SIGPIPE race)

- [x] **근본 원인 확정**(하드닝 진단 덤프가 특정): `printf 145KB | grep -q` — grep -q 조기 종료가 printf 에 SIGPIPE → `set -o pipefail` 하에서 파이프라인 rc=141 → **출력이 완전(rc=0·bytes=145,878·서비스 29)해도 "미검출" 오판**. 타이밍 race 라 부하 의존 = 간헐성(6회 중 3회)의 정체.
- [x] 수정: 검사 3곳(재시도 루프·최종 검사·published)을 파이프 없는 **bash 부분문자열 매칭**으로 교체 — SIGPIPE 표면 원천 제거.
- [x] 검증: worktree dry-run — 실패 경로(env 부재 시 3회 재시도+정직 die) + **happy path "OK — 두 replica 정의 확인" 도달**(대형 cfg 에서 재현). bash -n. 라이브 실증 = 머지 직후 배포.

## 20260728T1230-asset-stamp-cache-integrity — 롤링 배포 창의 브라우저 캐시 오염 근본 해소
- [x] **근본 원인 확정(라이브 실측)** — 엣지(`Caddyfile`)의 `@static_versioned` 가 `?v=` 의 **존재**만 보고 `immutable` 부여. 정적 파일은 각 replica 로컬 FS 에서 **경로만으로** 서빙(쿼리 무시)되므로, 롤링 창에 구 replica 가 `?v=<신 스탬프>` 요청에 **구 바이트**로 200 응답 → 그 응답이 그 URL 에 **1년 고착**. ES module 진입점이 굳으면 import 체인 전체가 구버전으로 끌려간다(2026-07-28 graph-noise-reduction 배포 후 실측: 서버는 신 코드 서빙, 브라우저만 구 렌더)
- [x] sticky(`lb_policy cookie weblb`)로 안 닫히는 이유 규명 — pinned replica 가 recreate 되는 순간 LB 가 재배정 → 한 페이지 로드가 두 버전에 걸친다(창을 *좁힐* 뿐 *닫지* 못함)
- [x] **불변식 채택** — "응답이 immutable 로 표시되려면 응답한 replica 의 빌드 스탬프 == 요청 `?v=`". 불일치 = `no-store` → 오염이 구조적으로 불가능
- [x] `inject_asset_stamp.py` — 주입 스탬프를 `<static>/.asset-stamp` 사이드카로 기록(해시 입력에서 자기 제외 = 멱등성 보존, 경로 비교는 abspath 정규화)
- [x] `web/static_cache.py` 신설 — 순수 ASGI 래퍼(`StaticCacheHeadersMiddleware`) + 정책 판정(`decide_cache_control`). 전 구간 fail-open
- [x] `app.py` — `/static` mount 를 래퍼로 감쌈(StaticFiles 자체는 불변)
- [x] `Caddyfile` — 무조건 `header @static_versioned Cache-Control immutable` **제거**(upstream 헤더가 권위). 제거 사유를 주석으로 고정
- [x] vendor pin(`?v=5.1.1`) 예외 — 빌드 해시와 다른 버전 축이라 비교하면 상시 불일치 → 캐시 전면 상실. 종전 immutable 유지
- [x] 단위·통합 **32 PASS** (정책표 13 · 사이드카 5 · ASGI 래퍼 7 · 엣지 짝 계약 1 · **실 injector→실 static 트리→실 StaticFiles 통합 1** 외)
- [x] **통합 테스트가 접합부 결함 1건 적발** — Starlette 최신 `Mount` 는 하위 앱에 `scope["path"]` 를 자르지 않고 넘겨(`/static/vendor/...`) prefix 기반 vendor 판정이 빗나갔다 → 라이브러리 pin 이 상시 `no-store` 가 될 뻔. 세그먼트 검사로 교체 + 양 규약 단정 추가
- [x] 전체 회귀 **2719 passed / 2 skipped / 0 failed** · ruff All checks passed · `caddy validate` adapt OK
- [x] 이미지 경로 정합 사전 확인 — Dockerfile `--root /app/web/static` == app `STATIC_DIR`, `COPY unit/feature-0003-agent-web-ui/src /app/web` 로 `static_cache.py` 동봉, `/app/web` 이 런타임 sys.path 에 존재(`perf_metrics` 와 동일 기전, 컨테이너 실측)
- [ ] POST-DEPLOY 라이브 결정론 검증 — 구 스탬프 → `no-store` / 현 스탬프 → `immutable` / vendor pin → `immutable`

## 20260811T1557-edge-rolling-gate — 롤링이 **엣지 관점에서는** 무중단이 아니던 근본 결함 수정

사용자 보고: "최근 배포 과정 중 사용자들로부터 서비스가 멈춘다는 이슈가 자주 확인된다."

- [x] **근본 원인 확정(라이브 로그 실측, 2026-08-11)** — 엣지가 `no upstreams available` 로 503 을
      반환한 창이 6시간 안에 **6회**, 각 **12~17초**(에러 로그 71건). 503 응답의 duration 이 전부
      `5.01s` = `lb_try_duration` 을 다 쓰고 포기. **그 창에서 active health 는 양 replica 모두
      `host is up`** 이었다 → 원인은 active 가 아니라 **passive 격리**.
- [x] **기전** — `recreate_replica` 의 게이트가 **컨테이너 내부 `/readyz`**(= 앱이 떴다)까지만 보고
      **엣지가 그 replica 를 다시 LB 후보로 쓰는지**는 보지 않았다. Caddy 는 실패한 upstream 을
      `fail_duration`(당시 30s) 동안 후보에서 뺀다. 실측 롤링 간격은 **10초**(web-a 12:39:54 →
      web-b 12:40:04)이므로, web-a 가 아직 격리 중인 상태에서 web-b 를 내려 **available upstream 0**
      이 됐다. 503 종료 시각이 매 창마다 "먼저 내린 replica 의 첫 실패 + 30s" 와 일치(12:16:26,
      12:11:56, 12:40:23)해 기전이 확정됐다.
- [x] **왜 자동 게이트가 못 잡았나** — soak 는 web-b recreate 가 끝난 **뒤** 시작하고 edge 실패를
      "일시 blip"(`EDGE_FLAP_MAX`)으로 관용한다. 503 은 격리 타이머로 자연 회복하므로 배포는 매번
      **성공으로 보고**됐다. `unit/feature-0014-*/tests/` 는 testpaths 밖이라 테스트도 0건이었다 —
      사용자가 유일한 backstop 이었던 무증상 장애(§16.7 G9).
- [x] **수정 1 (스파인 게이트, 근본)** — `wait_edge_available` 신설: Caddy admin API
      `/reverse_proxy/upstreams` 로 upstream 별 `fails==0` 복귀를 확인. 2층 배선 —
      ① `recreate_replica` 말미 **선제 대기(비차단)**, ② `predrain <target> <other>` 에서
      **상대의 복귀를 fail-closed 로 확인**하고 미복귀면 배포 중단(기존 replica 가 계속 서빙 =
      무중단 유지). 중단이 강행보다 항상 낫다 — 강행하면 정확히 그 전면 503 이 재현된다.
- [x] **수정 2 (Caddyfile 은 값 변경 대신 계약 문서화)** — 초안은 `fail_duration 30s→3s` 였으나
      적대 검증에서 **실장애 격리를 10배 약화**시킨다는 지적(P2)을 받고 **원복**했다: `/livez` 는
      통과하면서 특정 요청만 5xx 를 내는 upstream(active health 가 못 잡는 유형)이 3초마다 다시
      투입된다. 그 트레이드오프를 정당화할 SLO 근거가 없다. 대신 **결합을 스파인이 흡수**하도록
      두고, 이 값이 롤링과 결합된다는 사실·바꿀 때의 제약(`< EDGE_AVAIL_TIMEOUT`)을 주석으로 고정.
- [x] **적대 검증 반영 (codex, §18.8.1 경량 경로)** — P1 3건 전건 수정:
      ① admin 조회가 멈추면 while 이 deadline 을 재검사 못 해 **배포가 flock 을 쥔 채 무기한 정지**
         → `timeout` 2겹(wget `-T 5` + exec 전체 15s).
      ② 격리를 관측한 채 timeout 인데 성공 반환 → 다음 replica 를 그대로 내려 원 결함 재현
         → **관측-timeout 은 실패 반환**, predrain 이 fail-closed 중단.
      ③ degrade 대기가 repo Caddyfile 만 신뢰 → 이 변경을 처음 배포하는 창에는 **라이브 Caddy 가
         아직 옛 값**이라 덜 기다림 → **max(repo, 라이브 컨테이너 설정)**, 둘 다 미상이면 30s.
      P2 3건도 반영(주장 범위 정직 표기 · fail_duration 원복 · 실효하지 않던 fallback 테스트 수정).
- [x] **수정 3 (회귀 잠금)** — `unit/feature-0014-*/tests/test_edge_rolling_gate.py` **건**(테스트 함수 32 + 파라미터 확장) 신설 +
      `pyproject.toml` testpaths 등재. G1 배선(recreate·predrain·호출부 `|| die`)·G2 파싱(8케이스)·
      G3 대기·G4 degrade/hang/라이브값·G5 비차단·G6 예산정합·G7 passive 존치.
      **뮤테이션 17종 전건 KILLED** — 3라운드 적대 검증마다 추가된 계약까지 포함.
- [x] 배포 체크리스트 [5] 신설 — 매 배포 후 `caddy logs | grep -c 'no upstreams available'` = 0 확인.
      "스파인이 성공 보고 = 무중단" 이 아니라는 사실을 상시 표면화.
- [x] 검증: `bash -n` · 신규 **39 PASS** · **뮤테이션 17종 전건 KILLED** · 라이브 Caddy admin 응답 파싱 실측 · 라이브 Caddy→web-a `/livez` 200 실측(peer probe 경로 확인)
- [x] POST-DEPLOY 라이브 실측 **완료** — 배포 창 `no upstreams available` = **0**(수정 전 12~17초 전면 503 → 0),
      요청 172건 전부 200. 4서비스 GIT_COMMIT=8cad9cd7 확인(web-a/web-b/ask-worker/insight-worker/ops-scheduler).

## TASK-20260826T030000-deploy-conversation-smoke — 배포 게이트 대화 스모크

2026-08-26 라이브 장애에서 드러난 **관측 공백**(대화가 죽어도 healthz·soak 는 green)을 메운다.
사용자 결정: 증상 축(문구·재시도·폴백)이 아니라 근본 축으로 진행. 원장:
`FR-conversation-failure-undetected-by-deploy-gate`.

- [x] `bin/smoke-conversation.sh` 신설 — 대화 답변 경로 실제 함수 1회 호출·답변 생성 확인.
- [x] `bin/deploy-web.sh` **2단 배치** — ① 교체 전 후보(surge) 검증(실패 시 교체 안 함 = 무장애)
      ② 배포 완료 직전 최종 확인. 실패 시 exit 1(조용한 성공 금지).
- [x] 멱등성 봉인 — `conv_smoke_sha` 기록 + no-op 판정 포함(스모크 실패 SHA 재실행이 green 이 되던 결함).
- [x] fail-closed — 스크립트 부재는 skip 아닌 배포 실패.
- [x] 게이트웨이 `request_timeout` 300 → 960 **+ stop_grace 330s → 990s**(층 간 정합, 사용자 결정).
- [x] 라이브 배포본에서 스모크 PASS 확인 + fail-closed 동작 확인.
- [ ] **배포로 게이트 실동작 확인** — 다음 배포에서 `대화 경로 스모크 … PASS` 로그가 찍히는지.
