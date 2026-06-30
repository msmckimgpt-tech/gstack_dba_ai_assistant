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
