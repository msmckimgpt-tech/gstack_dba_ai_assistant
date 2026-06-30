---
doc_type: TEST
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 포함: 마이그레이션 안전 게이트 로직, compose/Caddy 구조 유효성, app.py 엔드포인트 구문,
  route-parity 정합, 무중단 롤링 동작(zero-502), 자동 롤백, SSE pre-drain.
- 제외: 앱 기능 회귀(feature-0002/0003 기존 스위트가 담당), DB 자체 HA.

> 본 feature 는 인프라/배포 구조라 화면(UI) 검증 대상이 아니다. 서버 계약(`CLI`) + 라이브
> 무중단 동작(운영자 실 호스트)으로 검증한다.

## 2. Test Cases
### TEST-20260630T120000-migrate-lint-1
- Purpose: expand-only revision PASS, contract(drop/rename/type/NOT NULL/raw DDL in op.execute 상수) FAIL.
- Steps: `bash bin/migrate-lint.sh --self-test`
- Expected: 4 케이스(expand-safe / drop_column / downgrade-only 무시 / raw ALTER..DROP) 전부 통과.

### TEST-20260630T120000-compose-config-2
- Purpose: web-a/web-b 가 호스트포트 없이, KEK/HOST_ALLOWLIST(.env.secret) 포함해 resolve.
- Steps: `docker compose -f docker-compose.yml config`
- Expected: exit 0, web-a/web-b 존재, published 포트 없음, certs 볼륨·stop_grace_period 30s.

### TEST-20260630T120000-caddy-adapt-3
- Purpose: Caddyfile LB(2-upstream/cookie/retry/active /livez) 구조 유효.
- Steps: `caddy adapt --config Caddyfile`
- Expected: exit 0, JSON 에 load_balancing/selection_policy(cookie)/try_duration/health_checks/web-a:8000/web-b:8000.

### TEST-20260630T120000-route-parity-4
- Purpose: /livez·/readyz 추가 후 route-parity 골든 정합.
- Steps: `make test`(agent 컨테이너 pytest) — `test_route_parity_p5b.py`.
- Expected: PASS (golden 187/186, /livez·/readyz 가 /healthz 직후).

### TEST-20260630T120000-zero-502-rolling-5
- Purpose: 롤링 재배포 중 비-SSE 502 = 0 (true-zero).
- Preconditions: 운영자 실 호스트, 컷오버 완료(RUNBOOK §5).
- Steps: RUNBOOK §6 의 부하 루프 + `sudo -E bin/deploy-web.sh` 동시 실행.
- Expected: 200 only (502/000 = 0), round_robin 양 replica 신규 git_commit.

### TEST-20260630T120000-auto-rollback-6
- Purpose: 결함 이미지 배포 시 soak 가 감지 → last-good 자동 롤백, edge 유지.
- Steps: 잘못된 이미지로 배포 유도 → soak 동작 관찰.
- Expected: RestartCount/edge 이상 감지 → 자동 롤백 → edge 200.

### TEST-20260630T120000-sse-predrain-7
- Purpose: 진행 중 SSE 가 있는 replica 는 active_streams==0 까지 recreate 보류.
- Steps: admin 프롬프트 자동작성 SSE 진행 중 배포 → 해당 replica pre-drain 관찰.
- Expected: 스트림 완료까지 대기 후 recreate(또는 timeout 시 경고).

## 3. Test Runs (append-only)
### Run 2026-06-30 — Environment: CLI (정적 검증, worktree)
- migrate-lint --self-test: PASS (4/4)
- migrate-lint --all: 기존 destructive revision(0009/0015/0023) 적발, baseline/expand 통과 (게이트 동작 확인)
- `docker compose -f docker-compose.yml config`: exit=0 (web-a/web-b 호스트포트 없음, KEK/allowlist resolve)
- `caddy adapt`: exit=0 (LB/cookie/health/retry/web-a:8000/web-b:8000 확인)
- `python -m py_compile app.py`: OK
- `bash -n` migrate-lint.sh / deploy-web.sh: OK
- route_snapshot_p5b.json: JSON valid, 187/186 정합, /livez(idx9)/readyz(idx10) /healthz(idx8) 직후
- `make -n up`: exit=0
- deploy-web.sh --dry-run(stub env): preflight 순서·flock·origin/main coalesce(8baa707) 동작, file-set
  preflight 가 env 부재 시 fail-loud (정상). **완전 dry-run 은 운영자 실 호스트(.env 보유) 단계.**

### Run (예정) — Environment: CLI (운영자 실 호스트)
- TEST-...-5/6/7 (zero-502, 자동 롤백, SSE pre-drain) — RUNBOOK §4~§7 수행 후 기록.

## 4. 미작성/미수행 사유 및 커버 계획
- 라이브 무중단 동작(zero-502/롤백/pre-drain)은 실 docker 호스트 + sudo + 라이브 트래픽이 필요해
  worktree 정적 검증으로 대체 불가. 본 dev 환경은 root+NOPASSWD:ALL 이라 sudo 경계 검증도 은폐된다.
  → 운영자가 RUNBOOK 절차로 수행하고 §3 Run + ANCHOR §4 에 기록(human).
