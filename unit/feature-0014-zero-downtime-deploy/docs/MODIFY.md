---
doc_type: MODIFY
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

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
