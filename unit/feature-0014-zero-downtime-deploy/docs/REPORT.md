---
doc_type: REPORT
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary

**2026-08-11 TASK-20260811T1557-edge-rolling-gate — 롤링이 엣지 관점에서는 무중단이 아니던 근본 결함 수정** (Major §12.3 — 배포 스파인. 데이터/스키마/API/RBAC 무변경). 사용자 보고 "최근 배포 과정 중 서비스가 멈춘다" 로 착수. **근본 원인**: `recreate_replica` 의 게이트가 **컨테이너 내부 `/readyz`**(= 앱이 떴다)까지만 보고 **엣지가 그 replica 를 다시 LB 후보로 쓰는지**는 보지 않았다. Caddy 는 실패한 upstream 을 `fail_duration`(30s) 동안 후보에서 빼는데 실측 롤링 간격은 **10초**(web-a 12:39:54 → web-b 12:40:04)라, web-a 가 아직 격리 중인 상태에서 web-b 를 내려 **available upstream 0** 이 됐다. **라이브 실측**: 엣지 에러 `no upstreams available` **71건/6h**, 전면 503 창 **6회 × 12~17초**, 503 duration 이 전부 `5.01s`(= `lb_try_duration` 소진), 그 창에서 active health 는 양 replica 모두 `host is up`(= passive 격리가 유일 원인), 503 종료 시각이 매 창 "먼저 내린 replica 첫 실패 + 30s" 와 일치. **왜 무증상이었나**: soak 는 web-b recreate 후 시작하고 edge 실패를 blip 으로 관용(`EDGE_FLAP_MAX`)하며 503 은 격리 타이머로 자연 회복하므로 **배포는 매번 성공으로 보고**됐고, `feature-0014/tests/` 는 testpaths 밖이라 이 불변식을 잠그는 테스트가 0건이었다 — 사용자가 유일 backstop. **해소**: `wait_edge_available` 신설(Caddy admin API `/reverse_proxy/upstreams` 의 upstream 별 `fails==0` 확인) + **2층 배선** — recreate 말미 선제 대기(비차단, 롤백 경로 보호) / `predrain` 에서 **상대의 복귀를 fail-closed 로 확인**하고 미복귀면 배포 중단(기존 replica 가 계속 서빙 = 무중단 유지). admin 조회는 `timeout` 2겹(hang 시 flock 을 쥔 채 정지 차단), degrade 대기 기준은 **max(repo Caddyfile, 컨테이너 파일) 에 floor 30s**(파일은 '런타임 적용값' 이 아니므로 관측된 최악값 이상을 기다린다). `predrain` 은 **3조건 fail-closed**(상대 존재·상대 ready·상대 엣지 복귀). **Caddyfile 은 값 원복** — 초안의 `fail_duration 30s→3s` 는 적대 검증이 "`/livez` 는 통과하며 특정 요청만 5xx 인 upstream 이 3초마다 재투입된다"(실장애 격리 10배 약화)를 지적해 철회하고, 결합 사실만 주석으로 고정했다. **검증**: 신규 **39 PASS** · **뮤테이션 17종 전건 KILLED** · codex 적대 리뷰 **5라운드**(1R P1 3·P2 3 / 2R P1 2·P2 2 / 3R P1 1·P2 3 / 4R P1 4·P2 1 전건 반영 · 5R P1 1 은 성립 전제를 실측 반박 후 **근거 기록 + 전제 테스트 잠금**으로 수용) · 라이브 admin 응답 파싱 실측. **게이트 판정 2축**: passive 격리 해제(`fails==0`) **+ Caddy→replica 실도달**(`edge_peer_live` — Caddy 컨테이너에서 그 replica 의 health_uri 를 직접 200 확인, active health probe 와 동일 조건). 전자만 보면 active health 가 제외한 replica 를 복귀로 오판한다. **한계(정직)**: Caddy 내부 healthy 플래그 자체는 admin API 가 노출하지 않아, '방금 실패를 기록해 아직 unhealthy 마킹 중이나 지금은 200' 인 최대 `health_interval`(2s) 창은 폴링(1s)이 흡수한다. **라이브 실효는 다음 배포에서만 측정 가능** — 배포 창 `no upstreams available` = 0 이 유일한 ground truth(수정 전 기준선 = 배포당 8~13건). 전체 회귀의 기존 실패 1건(OAuth 토큰 갱신)은 **main 기준선에서도 동일**함을 확인. 정본: TASK `20260811T1557-edge-rolling-gate` · CHG/REV-20260811T155700-edge-rolling-gate · Run=test-runs.d/20260811T1557-edge-rolling-gate.md.

---

**2026-07-28 TASK-20260728T123000-asset-stamp-cache-integrity — 롤링 배포 창의 브라우저 캐시 오염 근본 해소** (Major §12.3 — 엣지 설정 + 전역 캐싱 semantics; cross-cut: feature-0002 injector · feature-0003 web · feature-0006 Caddyfile. 데이터/스키마/API/RBAC 무변경). 사용자 지시 — 직전 graph-noise-reduction 배포의 POST-DEPLOY 에서 **"서버는 신 코드를 서빙하는데 브라우저만 구버전 렌더"** 를 실측하고 후속 근본 해소를 요청받음. **근본 원인**: 정적 파일은 각 replica 로컬 FS 에서 **경로만으로** 서빙되는데(쿼리 무시), 엣지가 `?v=` 의 **존재**만 보고 `immutable` 을 부여했다. 롤링 창에 sticky pinned replica 가 recreate 되면 LB 가 재배정하고, 그 순간 **구 replica 가 `?v=<신 스탬프>` 요청에 구 바이트로 200 응답** → `max-age=31536000, immutable` 로 **1년 고착**(ES module 진입점이 굳으면 import 체인 전체가 구버전). sticky 는 창을 *좁힐* 뿐 *닫지* 못한다. **해소 불변식**: "immutable 로 표시되려면 응답한 replica 의 빌드 스탬프 == 요청 `?v=`" — 불일치는 `no-store`(+`X-Asset-Stamp: mismatch`) → 버전이 어긋난 응답이 **캐시에 들어가지 못한다**. **변경 4파일**: ① `inject_asset_stamp.py` 가 주입 스탬프를 `<static>/.asset-stamp` 사이드카로 기록(해시 입력서 자기 제외 = 멱등 보존, abspath 정규화) ② `web/static_cache.py` **신설** — 순수 ASGI 래퍼 + 정책 판정(전 구간 fail-open) ③ `app.py` 가 `/static` mount 를 래퍼로 감쌈(StaticFiles 불변) ④ `Caddyfile` 의 `@static_versioned` + `header … immutable` **제거**(upstream 이 권위 — 엣지는 자기 빌드를 모른다). **의도적 예외**: vendor pin(`?v=5.1.1`)은 별개 버전 축이라 종전 immutable 유지(비교하면 상시 불일치 → vendor 캐시 전면 상실). **검증**: 신규 **32 PASS**(정책표 13 파라미터 · ASGI 래퍼 7 · 사이드카 5 · 엣지 짝 계약 1 · **실 injector→실 static 트리→실 StaticFiles 통합 1**) · 전체 회귀 **2719 passed / 2 skipped / 0 failed** · ruff All checks passed · `caddy validate` adapt OK · 이미지 경로 정합 컨테이너 실측(injector root == `STATIC_DIR`, `static_cache.py` COPY 포함, `/app/web` 이 런타임 sys.path 에 존재). **통합 테스트가 접합부 결함 1건 적발**: Starlette 최신 `Mount` 는 하위 앱에 `scope["path"]` 를 자르지 않고 넘겨(`/static/vendor/...`) prefix 기반 vendor 판정이 빗나갔다 → 라이브러리 pin 이 상시 `no-store` 가 될 뻔했고 세그먼트 검사로 교체(격리 단위테스트만 있었으면 통과했을 결함). §18.8 패널은 세션 정책(Agent tool 미허용)으로 [SKIPPED] + **자체 적대 검토 H1~H10** 실측 기록. **한계(정직 표기)**: 롤링 창 자체는 남는다 — 창 안에서 버전이 섞인 페이지를 한 번 볼 수 있고 달라진 것은 **캐시에 굳지 않는다**는 점(다음 로드에서 수렴). 창 제거는 content-addressed 경로(`/static/<hash>/…` + retention)가 후속 과제. 이미 오염된 브라우저는 해당 URL 재요청 전까지 자동 복구되지 않는다(스탬프가 바뀌면 새 URL 이라 실질 영향 소멸). **상태**: 구현·검증 완료 → cycle-final 진행. deploy_scope: included — 배포 후 결정론 헤더 프로브(구 스탬프→`no-store` / 현 스탬프→`immutable` / vendor→`immutable` / 무-v→미설정) + 캐시 미삭제 브라우저에서 그래프 뷰 정상 렌더 PB-0008 확인 예정. worktree `ai/claude/feature-0014-asset-stamp-cache-integrity`(base main f4c50289). 정본: TASK/CHG/REV-20260728T123000-asset-stamp-cache-integrity · FUNCTION AC-ASCI-1~5 · Run=test-runs.d/20260728T123000-asset-stamp-cache-integrity.md.

---

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
