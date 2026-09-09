---
doc_type: MODIFY
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260713T073141-deploy-verify-checklist
- Date: 2026-07-13
- Related Requirement: REQ-20260713T073141-deploy-verify-checklist (AC-DVC-1~3)
- 변경:
  - `bin/deploy-web.sh`: `post_deploy_checklist()` 신규(output-only, dry-run skip) + "배포 완료" step 직후 호출. 5항목(배포완료·워커 재빌드·캐시 무효화·실 사용자 표면 검증·완료 보고 시점)을 stderr 로 요약 출력. **배포 판정/제어 흐름 무변경**(`bash -n` PASS).
  - `unit/feature-0014-zero-downtime-deploy/docs/RUNBOOK.md`: §10 배포 검증 체크리스트(판정 기준 표 + 워커 코드 판정 가이드) 추가. §9(worker divergence)와 연동.
  - `docs/LEARNINGS.md`: LRN-20260713-0001 회고(merge≠배포완료·워커 미반영·백엔드만 검증 3중 마찰) 추가.
  - feature-0014 FUNCTION(REQ/AC)·TASK(체크박스)·REPORT·REVIEW 갱신.
- 근거: 2026-07-13 feature-0003 attach-user-version 사용자 테스트가 배포 ~1시간 전(구코드)에 수행돼 실패로 관측됨. 추가로 그 기능의 assistant 인지 로직은 ask-worker 거주라 web 배포만으론 미반영(별도 재빌드 필요), 완료 검증(PB-0008)이 백엔드 fetch 만 타 client-only 경로를 놓침. 세 마찰을 배포 프로세스 체크리스트로 상시화.
- Minor §12.3 (문서 + output-only 스크립트). 스키마/RBAC/배포 로직 무변경. REV-20260713T073141-deploy-verify-checklist.

## CHG-20260630T120000-zero-downtime-deploy
- Date: 2026-06-30
- Related Requirement: REQ-20260630T120000-zero-downtime-web, REQ-...120001-safe-unattended-deploy,
  REQ-...120002-migration-safety
- Summary: web 을 Caddy LB 뒤 2-replica(web-a/web-b) 무중단 롤링으로 전환 + 배포 스파인
  `bin/deploy-web.sh` + 마이그레이션 안전 게이트 `bin/migrate-lint.sh` + /livez·/readyz·SSE 카운터.
  :18080 web 직접 문 폐기(Caddy :443 단일화).
- Files:
  - 신규: `bin/migrate-lint.sh`, `bin/deploy-web.sh`, `unit/feature-0014-zero-downtime-deploy/docs/*`
  - 수정: `docker-compose.yml`(x-web-extra anchor, web→web-a/web-b, 호스트포트 제거, stop_grace 30s,
    caddy depends_on), `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`(2-upstream LB),
    `unit/feature-0003-agent-web-ui/src/app.py`(/livez,/readyz,_counted_stream*),
    `unit/feature-0003-agent-web-ui/tests/route_snapshot_p5b.json`(+/livez,/readyz, 185→187),
    `Makefile`(web-a/web-b, deploy-web, web-rollback, migrate-lint, repo-web→repo-web-a),
    `docs/CONVENTIONS.md`(§12 expand/contract), `AGENTS.md`(§10.5 alembic row),
    `docker-compose.override.yml.example`(web-a/web-b, :18080 폐기 반영)
- Impact:
  - **외부 영향(Major/Critical)**: 서비스 토폴로지 변경(web→web-a/web-b), :18080 접속 경로 폐기,
    배포 명령 변경(`sudo -E bin/deploy-web.sh`). 머지 시 자동배포(deploy_scope) 트리거 — 운영자
    게이트 필요(RUNBOOK).
  - 비파괴: app.py 는 엔드포인트 추가만(기존 동작 무변경), compose 는 merge anchor 로 동등 구성.
- Rollback Notes: PR revert + `docker compose up -d --no-deps web`(단일 web 복귀, base 에 web 서비스
  재존재 필요). 라이브 롤백(이미지)은 `make web-rollback`(last-good). DB 는 expand/contract 라
  down-migration 불필요.

## CHG-20260711T113717-deploy-flake-hardening (bin/deploy-web.sh — preflight/soak/rollback 판정 하드닝)
- Date: 2026-07-11. 사용자 지시(잔여 작업 재개)로 승인 — parallel-work-structure ITEM-10 배포 게이트가 3회 연속 flake 로 차단된 인시던트의 근본 대응.
- Summary: ① preflight config 재시도(3×2s)+stderr 포획+진단 덤프 ② soak edge 실패 연속-3회 확증(단발 blip 롤백 방지) ③ 롤백 후 edge 판정 60s backoff. 전부 fail-safe 방향 — 진짜 결함(크래시루프·토폴로지 미적용)의 die/rollback 경로는 보존.
- 실측 근거: 07-11 배포 6회 중 preflight flake 3회 — stderr 유실로 **프로덕션 간헐 원인은 미확정**(비원자 env 재작성 창·snap confinement blip 등 후보). 본 변경은 원인 수정이 아니라 **진단 계측(stderr 포획) + transient 재시도** — worktree 검증은 계측 경로가 원인 문자열(env_file 부재)을 정확히 드러냄을 확인한 것(결정적 worktree 아티팩트이며 프로덕션 간헐성의 재현은 아님·env 복사 후 happy-path 도달) + 12:05 soak 단발 edge 실패로 정상 이미지(5a42b6e1, 단독 서빙 검증) 롤백 + 롤백 직후 조기 판정 오보.
- Files: bin/deploy-web.sh (+50/-6).
- Rollback: 단일 커밋 revert.

## CHG-20260711T201156-preflight-sigpipe-rootfix (preflight 검사 파이프 제거 — flake 근본 수정)
- Date: 2026-07-11. 직전 하드닝(CHG-20260711T113717)의 진단 계측이 원인을 특정: pipefail+grep -q 조기종료 SIGPIPE race. 검사 3곳을 bash `[[ == *...* ]]` 매칭으로 교체(의미 동일 — `\n  web-a:` 부분문자열 = `^  web-a:` 앵커 등가, cfg 는 config 출력이라 첫 줄이 서비스일 수 없음).
- Files: bin/deploy-web.sh (검사 3곳).

## CHG-20260728-0001
- Date: 2026-07-28
- Related Requirement: 무중단 배포 계열 4 feature 의 stale 체크박스 정리
  — **docs-only, 코드 무변경** (cross-feature 편집)
- Summary: 3일 이전부터 열려 있던 잔여 작업을 `git blame` 으로 집계하던 중, 무중단 배포
  계열 **23건이 이미 운영 중인데 체크박스만 남은 stale** 임을 실측으로 확인하고 닫았다.
  판정은 문서 대조가 아니라 **라이브 실측**으로 했다:
  - feature-0014 (6건): `bin/migrate-lint.sh` 실재 · `:18080` 무응답(폐기 확인) ·
    `/readyz`·`/livez` 200 · `bin/deploy-web.sh` 실재 · `repo-web-a-1`/`repo-web-b-1`
    2 replica + Caddy LB 가동 · asset stamp 파이프라인 실재
  - feature-0015 (6건): `repo-insight-worker-1` healthy · backup cron 9 entry 설치
  - feature-0016-zd-pg-pause-caddy (6건): `repo-pgbouncer-1` healthy 13일 연속 가동
  - feature-0017 (5건): `asset_stamp_verify` 게이트 실재 · `/readyz` 200
- Files: `unit/feature-0014-zero-downtime-deploy/docs/{TASK,MODIFY,REVIEW}.md`,
  `unit/feature-0015-zd-hygiene-backup/docs/TASK.md`,
  `unit/feature-0016-zd-pg-pause-caddy/docs/TASK.md`,
  `unit/feature-0017-deploy-build-gate/docs/TASK.md`
  (cross-feature 편집 — docs 홈은 가장 큰 덩어리인 feature-0014)
- Impact: 제품 동작 무변경. 4 feature 의 TASK.md 잔여가 각 1건(정형 항목)으로 수렴.
- Rollback Notes: 문서 되돌리기 외 롤백 대상 없음.

## CHG-20260728T123000-asset-stamp-cache-integrity — 롤링 배포 창의 브라우저 캐시 오염 근본 해소
- Date: 2026-07-28 · Session: `ai/claude/feature-0014-asset-stamp-cache-integrity` · REQ-20260728-asset-stamp-cache-integrity
- 트리거: 사용자 지시 — 직전 graph-noise-reduction cycle 의 POST-DEPLOY 에서 "서버는 신 코드를 서빙하는데 브라우저만 구버전 렌더" 를 실측하고 후속 근본 해소를 요청받음.
- **근본 원인**: 엣지가 부여하는 `immutable` 의 조건이 "`?v=` 가 있다" 였고, 그 값이 *응답한 replica 의 빌드*인지는 아무도 검사하지 않았다. 정적 파일은 replica 로컬 FS 에서 경로만으로 서빙되므로(쿼리스트링은 파일 조회에 무관) 롤링 창에 **구 replica 가 신 스탬프 URL 에 구 바이트로 200 응답**할 수 있고, 그 응답이 `max-age=31536000, immutable` 로 1년 고착된다.
- `unit/feature-0002-agent-core/src/scripts/inject_asset_stamp.py`
  - 주입 스탬프를 **`<root>/.asset-stamp` 사이드카**로 기록(런타임이 자기 빌드를 알기 위한 유일 출처).
  - `iter_files` 가 사이드카를 해시 입력·재작성 대상 **양쪽에서 제외** — 자기 참조로 멱등성이 깨지면 롤아웃마다 전 캐시가 무효화된다. 경로 비교는 `abspath` 정규화(호출자가 trailing slash 를 붙여도 유효).
- `unit/feature-0003-agent-web-ui/src/static_cache.py` **(신설)**
  - `decide_cache_control()` 정책 판정 — `?v=` 없음=미설정(ETag/304 유지) / 일치=`immutable` / 불일치=`no-store`+`X-Asset-Stamp: mismatch` / vendor=`immutable`(별개 버전 축) / 사이드카 부재=미설정(fail-safe).
  - `StaticCacheHeadersMiddleware` — 순수 ASGI 래퍼(`BaseHTTPMiddleware` 미사용, 스트리밍 무간섭). 200·304 에만 관여, 전 구간 fail-open.
  - `read_build_stamp()` — 시작 시 1회 로드(이미지 내 정적 파일이라 런타임 불변).
- `unit/feature-0003-agent-web-ui/src/app.py` — `/static` mount 를 래퍼로 감싼다(`StaticFiles` 자체는 불변) + `import static_cache`.
- `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` — feature-0027 이 두었던 `@static_versioned` matcher + `header … Cache-Control immutable` **제거**. upstream 헤더가 권위. 엣지가 왜 이 판정을 할 수 없는지(자기 빌드를 모른다)를 주석으로 고정해 규칙 부활을 막는다.
- 테스트 **32 PASS** — `feature-0003/tests/test_static_cache_integrity.py`(정책표 13 파라미터 · ASGI 래퍼 7 · 사이드카 3 · 엣지 짝 계약 1 · 실 injector→실 static 트리→실 StaticFiles **통합** 1 · 기타) + `feature-0002/tests/test_inject_asset_stamp_sidecar.py`(사이드카 5: 값 정합·멱등·내용변경 반영·--check 무기록·placeholder 잔존 0).
- **통합 테스트가 적발한 접합부 결함 1건**: Starlette 최신 `Mount` 는 하위 앱에 `scope["path"]` 를 자르지 않고 넘긴다(`/static/vendor/g6.min.js`). prefix 기반 vendor 판정이 빗나가 라이브러리 pin 이 상시 `no-store` 가 될 뻔했다 → 세그먼트 검사(`"/vendor/" in path`)로 교체하고 두 mount 규약을 모두 단정.
- Verification: 전체 pytest **2719 passed / 2 skipped / 0 failed** · ruff All checks passed · `caddy validate --adapter caddyfile` adapt OK(잔여 에러는 샌드박스의 cert 부재뿐) · 이미지 경로 정합 실측(Dockerfile `--root /app/web/static` == `STATIC_DIR`, `static_cache.py` COPY 포함, `/app/web` 이 런타임 sys.path 에 존재).
- Impact: 롤링 창의 버전 스큐 응답이 **캐시에 들어가지 못한다** → 창이 끝나면 자연 수렴. sticky LB 는 창을 좁히는 최적화로 유지. 정상 상태(스탬프 일치)의 캐시 동작·성능은 종전과 동일.
- Rollback: 4파일 revert(엣지 규칙 복원 포함). 데이터·스키마·API 영향 0.
- Cross-ref: REVIEW REV-20260728T123000-asset-stamp-cache-integrity · 선행 사고 관측 `feature-0003/docs/test-runs.d/20260728T113000-graph-noise-reduction.md` · feature-0027 P0-E(원 immutable 규칙) · AGENTS.md §13.1 v3.35.1(스탬프 자동 주입) · §13.2.9(배포 단계 격리).

## CHG-20260811T155700-edge-rolling-gate
- Date: 2026-08-11
- Related: TASK `20260811T1557-edge-rolling-gate` / REVIEW `REV-20260811T155700-edge-rolling-gate`
- Trigger: 사용자 보고 "최근 배포 과정 중 서비스가 멈춘다" → 라이브 엣지 로그 실측으로 근본 원인 확정.
- Root cause: 롤링 게이트가 **앱 레벨**(`/readyz`)까지만 보고 **엣지 레벨 후보 복귀**를 보지 않았다.
  Caddy passive health(`max_fails 1` + `fail_duration 30s`)가 실패한 upstream 을 30초 격리하는데
  실측 롤링 간격은 10초 → 두 replica 동시 격리 → `no upstreams available` → 전 요청 503.
  6시간 창 실측: 배포 6회 × 12~17초 전면 503, 엣지 에러 71건. 그 창의 active health 는 양쪽 `host is up`.
- Files:
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` — **값은 원복(`fail_duration 30s` 유지)**,
    대신 이 값이 롤링과 결합된다는 계약을 주석으로 고정. 초안은 3s 로 낮췄으나 적대 검증이
    "`/livez` 는 통과하면서 특정 요청만 5xx 인 upstream 이 3초마다 재투입된다"(= active health 가
    못 잡는 장애 유형의 격리가 10배 약화)를 지적했고, 그 트레이드오프를 정당화할 SLO 근거가 없다.
    결합은 스파인 게이트가 흡수한다.
  - `bin/deploy-web.sh` — `EDGE_AVAIL_TIMEOUT`/`CADDY_ADMIN_URL` 상수 + `caddy_fail_duration_s()` ·
    `edge_upstream_fails()` · `wait_edge_available()` 신설. **2층 배선**: `recreate_replica()` 말미
    = 선제 대기(비차단 — 롤백 경로도 이 함수를 타므로 여기서 끊으면 롤백이 중단된다),
    `predrain()` = **fail-closed 결정 지점**(상대가 엣지 후보로 복귀하지 않았으면 다음 replica 를
    내리지 않고 중단, 호출부는 `|| die`). admin 조회는 `timeout` 2겹으로 감싼다(hang 시 배포가
    flock 을 쥔 채 정지하는 경로 차단). degrade 대기 기준은 **max(repo Caddyfile, 컨테이너 파일) 에 floor 30s**(파일은 '런타임 적용값' 이 아니므로 관측된 최악값 이상을 기다린다). `predrain` 은 **3조건 fail-closed**(상대 존재·상대 ready·상대 엣지 복귀).
    파싱은 **순수 bash 문자열 연산**
    (호스트 python3 의존 0 + `printf|grep` 의 pipefail SIGPIPE 오판 함정 회피 — preflight_fileset 선례).
    `post_deploy_checklist` 에 [5] 무중단 실측 항목 추가(output-only).
  - `unit/feature-0014-zero-downtime-deploy/tests/test_edge_rolling_gate.py` — 신규 18건.
  - `pyproject.toml` — testpaths 에 `unit/feature-0014-zero-downtime-deploy/tests` 등재(그동안 이
    디렉토리는 수집 대상이 아니어서 배포 스파인 불변식을 잠그는 테스트가 0건이었다).
- Verification: 신규 **39 PASS** · **뮤테이션 17종 전건 KILLED**(각 뮤테이션이 대응 테스트 1건에 정확히 잡힘) · codex 적대 리뷰 P1 3건·P2 3건 전건 반영 · `bash -n` OK · 라이브 Caddy admin
  응답(`[{"address":"web-a:8000","num_requests":0,"fails":0},…]`)으로 파싱 실측 · 전체 회귀는 `make test`.
- Impact: 롤링 중 `available upstream 0` 창이 구조적으로 제거된다(엣지 복귀 확인 후에만 다음 replica
  를 내림). 정상 경로 배포 지연은 `fails==0` 즉시 통과라 **≈0**(격리가 남아 있을 때만 그만큼 대기).
  응답 shape·인가·스키마·마이그레이션 영향 0.
- Rollback: deploy-web.sh 함수·배선 revert + testpaths 되돌림(Caddyfile 은 주석만 변경이라 동작 영향 0). 데이터 영향 0.
- Cross-ref: ANCHOR §1("구조적으로 항상 ≥1 healthy upstream")·§3(사용자는 배포를 알지 못한다) —
  본 변경은 그 앵커가 **미달성** 상태였음을 드러내고 되돌린 것 · AGENTS.md §16.7 G9(검증면의 사각:
  차단·가용성 로직의 실측)·G10(재발 클래스 구조 가드).

## CHG-20260811T173500-edge-rolling-gate-postdeploy
- Date: 2026-08-11
- Related: CHG-20260811T155700-edge-rolling-gate 의 POST-DEPLOY 실증 기록(문서만 — 코드 변경 0).
- 결과: **PASS**. main `8cad9cd7` 배포 창(17:30~17:35)에서 `no upstreams available` **0건**,
  요청 **172건 전부 200**. 수정 전 동일 규모 창(12:40, 111요청)은 503×8·502×1·끊김×1 이었고
  전면 503 이 13초 지속됐다 — 게이트가 그 창을 제거했다.
- 게이트 실동작 확인: `web-b 엣지 passive fails=1 — 격리 해제 대기` → `복귀 확인(fails=0 +
  Caddy→web-b /livez 200)`. 즉 게이트는 "그냥 통과" 한 것이 아니라 **실제로 격리 해제를 기다렸다**.
- 부수 확인: 이번 배포는 Caddyfile 변경으로 `reconcile_caddy` 가 caddy 를 recreate 했는데(단일 edge)
  그 구간에서도 5xx 0. 전 서비스 `GIT_COMMIT=8cad9cd7`.
- Files: TASK.md · REPORT.md · test-runs.d/20260811T1557-edge-rolling-gate.md (기록만).

## CHG-20260826T030000-deploy-conversation-smoke

배포 게이트에 **대화 경로 스모크**를 추가하고, 게이트웨이 상류 ceiling 을 앱 연장 상한과 정합시켰다.

### 왜 (2026-08-26 라이브 장애)

게이트웨이 의존성(litellm)이 갱신되며 요청 조립 계약이 깨져 **모든 대화가 실패**했다. 그런데
배포는 성공했고 `/healthz` 는 ok, post-cutover soak 도 통과했다 — **시스템이 자기 고장을 몰랐고
사용자 신고로만 발견됐다(약 20시간)**. healthz·soak 는 "프로세스가 살아 있는가" 만 본다.

사용자 지적(2026-08-26): 증상 축 조치(문구 교정·재시도 분류·등급 폴백)는 **실제 원인을 가리는
임시조치**다. 특히 등급 교차 폴백은 품질 저하를 은폐해 열화된 답변을 정상으로 믿게 만든다.
그래서 근본 축 — **"깨져도 감지되지 않는다"** 는 관측 공백 — 을 메운다.

### 변경

- `bin/smoke-conversation.sh`(신설): ask-worker 컨테이너에서 **대화 답변 경로의 실제 함수**
  `agent_core._call_llm` 을 `reasoning_level=max` 로 1회 호출해 답변 생성을 확인한다. 요청 조립
  (extra_body·thinking·identity 주입·모델 alias 해소)을 전부 타므로 조립 결함과 게이트웨이 계약
  변화가 여기서 드러난다. 답변이 비면 exit 1.
- `bin/deploy-web.sh` — **2단 배치**(적대 리뷰 [P1] 수용으로 재설계):
  1. **교체 전 후보 검증**(`deploy_gateway_reconcile` 1b): surge 가 healthy 해진 직후, **본체를
     recreate 하기 전에** surge 를 `--gateway-url http://bedrock-gateway-surge:8080/v1` 로 직접
     스모크한다. 실패하면 surge 를 정리하고 **교체를 아예 하지 않는다** → 구 gateway 가 계속
     서빙하므로 **무장애**. 초판은 교체·surge 제거 후에야 검사해 "발견했지만 이미 장애" 였다.
  2. **최종 확인**(`conversation_smoke_or_fail`, 배포 완료 선언 직전): web/워커 이미지에서 비롯된
     잔여 결함을 잡는다. 실패 시 `exit 1`.
- **멱등성 봉인**(적대 리뷰 [P1]): 스모크 결과를 `conv_smoke_sha` 로 state 에 기록하고 **no-op 판정에
  포함**한다. 종전엔 `current`/`agent_current` 만 봐서 스모크 실패 SHA 를 재실행하면 no-op 분기에서
  `exit 0` — 결함이 그대로인데 "재시도하니 green" 이 되는 거짓 신호였다.
- **fail-closed**(적대 리뷰 [P2]): 스크립트 부재는 skip 이 아니라 배포 실패로 처리한다(실행 비트는
  보지 않는다 — `bash` 로 호출하므로 WSL filemode 차이에 게이트가 조용히 빠지지 않게).
- `scope=web` 은 ask-worker 미롤아웃이라 skip하되 `conv_smoke_sha=skipped-scope-web` 을 남기고
  **"대화 동작 미검증"** 을 경고로 표면화한다(완료 문구가 통과를 함의하지 않도록).
- `DEPLOY_WEB_SKIP_CONV_SMOKE=1` break-glass 유지(해제 시 경고).
- 배포 검증 체크리스트에 `[1b] 대화 스모크` 항목 추가.
- `litellm_config.yaml`: `request_timeout` **300 → 960** + `docker-compose.yml` 의 bedrock-gateway ·
  bedrock-gateway-surge `stop_grace_period` **330s → 990s**(사용자 결정 2026-08-26 AskUserQuestion:
  "960 + gateway stop_grace 상향"). 본문 timeout 제거로 정적 ceiling 이 상류 상한의 유일한 근거가
  됐으므로 앱 연장 per-call(900s)보다 크게 두고, **drain 이 ceiling 을 덮도록** stop_grace 를 그보다
  또 크게 둔다. 적대 리뷰가 "960 은 330s drain 계약을 깬다"([P1])를 잡아 두 층을 함께 올렸다.
  **대가**: gateway 교체가 최대 ~16분 대기할 수 있다. cross-ref: feature-0007.

### 검증

- 라이브 배포본에서 스모크 실행 → **PASS**(`model=claude-haiku-4-chat len=58`).
- fail-closed 확인: 모델 해소가 빈 값이던 초판에서 스크립트가 정확히 FAIL 을 냈다(조용한 통과 없음).
- `bash -n` 문법 검사 통과 · `litellm_config.yaml` YAML 파싱 검증(모델 16개 유지).

### 한계 (정직 표기 — 적대 리뷰 지적으로 정정)

- **기본 모델 1개만** 검증한다. 기본이 budget 계열(Haiku)이면 adaptive 계열(Sonnet 5·Opus 5) 전용
  경로 — OAuth frontier identity 주입, `output_config.effort`, 그 alias 해소 — 는 **검증되지 않는다**.
  초판 주석의 "identity 주입까지 전부 탄다" 는 틀린 주장이라 철회했다.
- HTTP 대화 진입점(`/api/ask` 인증·라우팅), 워커 큐 claim/lease, system/tool payload, 프런트는
  범위 밖이다. 초판은 "edge soak 가 담당" 이라 썼으나 **edge soak 는 `/healthz` 200 만 본다** —
  대화 API 인증·라우팅을 대신 검증하지 않는다. 이 주장도 철회했다.
- 보조 chokepoint(`_openai_chat_completion_with_deadline`)를 부르는 방식으로는 부족하다 —
  2026-08-25 에 그 방식으로 200 을 받고 "해소" 로 오판했다. **대화 경로 함수를 직접 불러야 한다.**


## CHG-20260909T140000-deploy-refresh
- Related TASK: TASK-20260909T140000-deploy-refresh
- 완료 신호를 전용 읽기 전용 mount로 전달. 혼합 배포/실패/재시도/rollback 분기 보완. 독립 회귀85 PASS. 상세 [TASK-20260909T140000-deploy-refresh](test-runs.d/TASK-20260909T140000-deploy-refresh.md).


## CHG-20260909T141300-deploy-refresh-evidence
- Related TASK: TASK-20260909T140000-deploy-refresh
- 초기 서버 배포/완료 신호/제품 지문과 환경 실패45PASS 재검증 기록. web-only smoke 미수행 경계를 명확히 함. 설치 DQA 검증은 진행 중으로 유지.


## CHG-20260909T143400-caddy-probe
- Related TASK: TASK-20260909T143400-caddy-probe-reaping / TASK-20260909T140000-deploy-refresh
- 배포 완료를 막은 Caddy ssl_client 좀비99/PID123/128 및 exec 실패를 진단. 점검을 같은 network namespace의 별도 init 컨테이너로 분리하고 Docker archive 파일 읽기·자기CID cleanup·조회 실패 fail-closed를 적용했다.
- Caddy 다음생성 init:true/pids_limit256. 현재프로세스는재생성하지않는다. 현재한도256은동시작업중외부변경을관측하여중복변경하지않았다.
- 실제검증·단위회귀·최종배포결과는 TASK-20260909T140000-deploy-refresh Run에분리기록한다.
