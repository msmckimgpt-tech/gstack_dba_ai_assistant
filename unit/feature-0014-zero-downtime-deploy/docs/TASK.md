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
