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
- [ ] TASK-20260630T120100-migrate-lint: 마이그레이션 안전 게이트 + CONVENTIONS expand/contract 규칙 (P0a)
- [ ] TASK-20260630T120101-hostport-override: 호스트포트 이전 + stop_grace_period + :18080 폐기 (P0b)
- [ ] TASK-20260630T120102-readyz-livez: /readyz·/livez probe + active-stream 카운터 (P0d)
- [ ] TASK-20260630T120103-deploy-spine: bin/deploy-web.sh (flock/sudo/TLS preflight/migrate/rollback) (P0c)
- [ ] TASK-20260630T120104-two-replica: web→web-a/web-b + Caddy LB (P1)
- [ ] TASK-20260630T120105-sse-asset: SSE pre-drain + 자산 content-hash (P2)
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
