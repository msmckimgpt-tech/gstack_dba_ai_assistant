---
doc_type: REPORT
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary

**2026-07-13 TASK-20260713T073141-deploy-verify-checklist — 배포 검증 체크리스트 상시화** (Minor §12.3, 문서 + output-only 스크립트). feature-0003 attach-user-version 배포 후 사용자 버그 리포트 조사에서 3중 마찰(① 사용자 테스트가 배포 ~1h 전 구코드에 수행 — merge≠배포완료 ② assistant 인지 로직이 ask-worker 거주라 web 배포만으론 미반영 ③ 완료 검증이 백엔드 fetch 만 타 client-only 경로 누락)을 확인, 배포 프로세스 체크리스트로 상시화했다. `bin/deploy-web.sh` 에 `post_deploy_checklist()`(output-only, dry-run skip)를 추가해 "배포 완료" 직후 5항목(배포완료·워커 재빌드 판정·캐시 무효화·실 사용자 표면 PB-0008·완료 보고 시점)을 stderr 로 요약 출력하고, 정본을 RUNBOOK.md §10(판정 기준 표 + 워커 코드 판정 가이드)에 문서화, LEARNINGS LRN-20260713-0001 회고를 남겼다. **배포 판정/제어 흐름 무변경**(`bash -n` PASS). §18.8 [SKIPPED:output-only-script+doc] REV-20260713T073141. worktree `ai/claude/feature-0014-deploy-verify-checklist`(base main).

---

## 1. Summary
web 서비스를 Caddy LB 뒤 **2-replica(web-a/web-b) 무중단 롤링** 으로 전환하는 구조와 그
롤아웃을 안전하게 수행하는 배포 스파인(`bin/deploy-web.sh`)을 구현했다. 설계는 독립 아키텍트
패널 → 심사 → 합성 → 9개 적대적 검증 워크플로(wf_f176026a)로 도출했고, 검증이 적발한 8개 gap
(마이그레이션 규율 부재·:18080 외부계약·배포 race·Caddy retry 메커니즘 오인·unattended sudo
경계·SSE 재접속 오해·자산 스큐·롤백 사각)을 모두 코드/문서에 반영했다.

**코드/문서는 worktree 에서 정적 검증 완료. 라이브 토폴로지 컷오버 + 무인 sudo 검증 + zero-502
부하 테스트는 운영자가 실 호스트에서 수행한다 (docs/RUNBOOK.md).** 본 개발 환경은 root+NOPASSWD:ALL
이라 sudo 경계 문제를 은폐하므로 그 검증을 대신할 수 없다.

## 2. Progress
- Planned: (없음)
- Done: P0~P3 코드 구현 + **라이브 컷오버 완료(2026-06-30, 사용자 승인 — 라이브 사용자 1명)**.
  PR #475 머지(main d980e24) → web-a/web-b 기동 → caddy 전환 → 구 web 제거 → edge 200(d980e24).
  단일 replica 롤링 부하 104/104 200·0실패·max 0.27s. 라이브 적발 버그 2건(health Host, proxy Host) 즉시 수정.
- In Progress: (없음 — 잔여는 운영자 후속: 자동롤백/SSE pre-drain 실측, scoped sudoers 무인경로)

## 3. Recent Changes
- `bin/migrate-lint.sh`(신규, AST 기반 expand/contract 게이트), `bin/deploy-web.sh`(신규, 배포 스파인)
- `docker-compose.yml`(web→web-a/web-b, 호스트포트 제거, stop_grace_period 30s, x-web-extra anchor)
- `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`(2-upstream LB + retry-primary + sticky cookie + active /livez)
- `unit/feature-0003-agent-web-ui/src/app.py`(/livez, /readyz, SSE active-stream 카운터)
- `Makefile`(up/web/web-tls web-a/web-b, deploy-web/web-rollback 타깃, migrate-lint, repo-web→repo-web-a)
- `docs/CONVENTIONS.md §12`, `AGENTS.md §10.5` row, route_snapshot_p5b.json(+2 routes), override.yml.example
- 총 변경 횟수: 1 (CHG-20260630T120000)

## 4. Open Issues
- ~~운영자 게이트~~ **해소**: 사용자가 전체 배포 승인 + 라이브 사용자 1명(외부 :18080 영향 없음) →
  머지·컷오버 완료. caddy hotfix(health_headers + header_up Host)는 main 에 후속 커밋(CHG-20260630T123000).
- **후속(운영자/별 cycle)**: ① 무인 자동배포 경로(`deploy-web.sh` + scoped NOPASSWD sudoers) 미검증 —
  현재 컷오버는 수동 오케스트레이션. ② 자동 롤백(TEST-...-6)·SSE pre-drain(TEST-...-7) 실측 미수행.
  ③ Caddyfile 변경 시 caddy recreate 필요(inode staleness) — deploy-web.sh 에 "Caddyfile 변경 감지 시
  caddy recreate" 추가 검토. ④ feature-0006 AC-0553/0556(:18080) deprecated 표기(TODOS P2).
- feature-0006 AC-0553/0556(:18080 직접 접속) deprecated 표기는 후속 doc-sync.
- (선택) 자산 스큐: sticky cookie LB 로 차단. 더 강한 보장이 필요하면 후속에서 content-hash 파일명.

## 5. Test Status
- 자동(정적): migrate-lint self-test PASS / `docker compose -f docker-compose.yml config` exit=0 /
  `caddy adapt` exit=0 / `python -m py_compile app.py` OK / `bash -n` (migrate-lint, deploy-web) OK /
  route_snapshot_p5b.json 정합(187/186) / `make -n up` OK.
- 수동(운영자): zero-502 롤링 부하, non-root dry-run, 롤백, SSE pre-drain — RUNBOOK §4~§7 (미수행).
- 미검증: 라이브 무중단 동작(실 호스트 한정).

## 6. Git 동기화 결과
- (commit/PR 시 갱신)

## 7. 후속(별 cycle)
- worker(insight/ask) divergence quiet-time 재빌드 절차 자동화, content-hash 자산 fingerprint(선택).

## 8. 개선 제안 (기록만)
- insight-worker SIGTERM graceful 핸들러(web 배포와 무관하나 quiet-time 재빌드 안전성 향상).
