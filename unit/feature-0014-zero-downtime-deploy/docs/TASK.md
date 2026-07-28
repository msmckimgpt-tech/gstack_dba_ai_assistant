---
doc_type: TASK
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

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
