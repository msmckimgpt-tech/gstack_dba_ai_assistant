---
doc_type: RELEASE_NOTES
scope: project
status: active
edit_policy: append-only
---

# Release Notes

## 2026-06-30 — feature-0014: web 무중단(zero-downtime) 배포 구조

### 변경 (운영자/사용자 영향)
- **web 서비스가 `web-a` / `web-b` 두 replica 로 분할**되어 Caddy 로드밸런서 뒤에서 운영된다.
  재배포 시 한 번에 하나씩 롤링 재시작하여 **비-스트리밍 경로(주 채팅 포함)에 사용자 체감 중단
  (502)이 발생하지 않는다**.
- **`:18080` web 직접 접속 문 폐기** — 모든 외부/LAN 접속은 **`https://mysql-ai.company.local`
  (Caddy :443)** 단일 진입으로 통일. (`:18080` 으로 접속하던 사용자는 전환 필요.)
- **새 배포 명령**: `make deploy-web` (= `sudo -E bin/deploy-web.sh`) — 무중단 롤링 + 자동 롤백.
  수동 롤백: `make web-rollback`.

### 추가
- `bin/deploy-web.sh` — 무중단 배포 스파인(flock 직렬화 + origin/main coalesce, 단일 scoped-sudo,
  TLS preflight, 마이그레이션 게이트, one-at-a-time + SSE pre-drain, post-cutover soak + 자동 롤백).
- `bin/migrate-lint.sh` — alembic 마이그레이션 expand/contract 안전 게이트(`make migrate-lint`).
- `/livez`(DB-무관 liveness, Caddy active health), `/readyz`(DB-backed readiness, 배포 게이트).
- `docs/CONVENTIONS.md §12` — 마이그레이션 expand/contract 규율(무중단 배포 전제).

### 운영자 조치 (컷오버 게이트)
- 본 변경의 라이브 적용은 `unit/feature-0014-zero-downtime-deploy/docs/RUNBOOK.md` 절차를 따른다:
  scoped NOPASSWD sudoers 설정 → 실 non-root 호스트 dry-run → :18080 사용자 통지 → 최초 컷오버
  → zero-502 부하 검증 → 자동 배포 연결. **머지가 자동배포(deploy_scope)를 트리거하므로 운영자
  confirm 전까지 자동 머지/배포는 보류한다.**

### 알려진 한계
- admin 프롬프트 자동작성 SSE / CSV export 는 fetch/getReader 라 자동 재접속이 없다. 배포는
  pre-drain 으로 진행 중 스트림 완료까지 해당 replica recreate 를 미루지만, timeout 시 해당
  스트림은 끊기고 사용자가 수동 재시도해야 한다(주 채팅 경로는 영향 없음).

## 2026-06-30 — feature-0015: 백엔드/DB 무중단 위생 + 백업 정비 (feature-0014 후속)

### 변경 (운영자 영향)
- **insight-worker SIGTERM graceful 종료** — 재배포/recreate 시 진행 중 cycle 을 루프 경계에서 마치고 우아 종료(`stop_grace_period: 30s`). ask-worker 와 동형. 라이브 실증: stop 18s(<30s grace)·ExitCode=0(SIGKILL 아님)·graceful 로그 3종 확인.
- **MySQL online-DDL 강제 게이트** — `bin/mysql-ddl-lint.sh`(diff-mode, 신규 MySQL ALTER 의 `LOCK=NONE` 강제, silent COPY-lock 차단). `make mysql-ddl-lint` / `docs/CONVENTIONS.md §13`.
- **백업 갭 정비** — 백업 범위 명시(sandbox 의도적 제외) + `bin/restore-rehearsal.sh`(throwaway DB 복원·행검증·DROP, 프로덕션 미접촉) + `bin/install-backup-cron.sh`(멱등, 매일 03:00 backup + 주간 일 03:30 restore-rehearsal). 라이브 실증: agent_kb 250M/agent_memory 32M 복원 PASS(PG 34 테이블·MySQL 29 테이블), orphan rehearsal DB 0.

### 운영자 조치
- cron 설치(`bin/install-backup-cron.sh`)는 **main repo 경로에서** 실행해야 cron 항목 경로가 올바름(worktree 경로 아님). 정본: `unit/feature-0015-zd-hygiene-backup/docs/{FUNCTION,TEST}.md`.

### 알려진 한계 / 범위
- HA(멀티 호스트·자동 failover·오케스트레이터)·DB 엔진 메이저 업그레이드·호스트/커널 무중단은 단일 호스트 SPOF 라 범위 밖(feasibility 분석 wf_1d634d33 결론: "HA 아니라 데이터 보존이 진짜 위험").

## 2026-06-30 — feature-0016-metadata-graph: 메타데이터 지식그래프(AGE) + 관리콘솔 그래프 뷰

### 변경 (운영자 영향)
- **KB Postgres 가 Apache AGE(openCypher 확장) 포함 커스텀 PG16 이미지로 cutover** — 관리콘솔 메타데이터(테이블·컬럼 설명)를 관계형 SSOT 의 재생성 가능한 그래프 투영(`metadata_kb`)으로 동기화. primary/replica `shared_preload_libraries='age'` + role search_path, alembic 0025(그래프 스키마 + RBAC). **라이브 cutover 완료(PR #477) — 데이터 무손상, 무중단 롤링**. 그래프는 관계형의 사본(진실 아님) — 손상/초기화 시 `bin/metadata-graph-sync.sh --rebuild` 로 재생성.
- **관리콘솔 '🕸 그래프 뷰'** — 데이터소스별 메타데이터 그래프 탐색(검색·이웃 확장·카테고리 클러스터링) + AI `graph_navigate` 도구(대규모 스키마 컨텍스트 초과 해소).

### 운영자 조치 / 롤백
- 이미지 토글 env-var(`KB_PG_IMAGE`/`KB_PG_PRELOAD`/`KB_PG_REPLICA_PRELOAD`, 기본=cutover 이미지). 롤백 = 이전 이미지 revert + `drop_graph`. 정본: `unit/feature-0016-metadata-graph/docs/RUNBOOK-cutover.md`.

### 알려진 한계
- 게임 DB 는 FK 미선언이 많아 테이블 간 관계 엣지가 현재 희소(노드 그래프·스키마 그룹핑은 즉시 가치). 대화 JOIN 학습·후속 관계 추론으로 점증. PB-0008 라이브 브라우저 그래프 UI 검증·eval A/B 잔여.

## 2026-06-30 — feature-0016-zd-pg-pause-caddy: PG 재시작 무중단화 + Caddyfile reconcile

### 변경 (운영자 영향)
- **PG primary 재시작 near-zero RW 단절** — `bin/pg-restart.sh` 가 pgbouncer(transaction-mode) PAUSE(신규 RW 큐잉)→postgres recreate→healthy 대기→RESUME. RESUME 을 `trap` 으로 보장(실패 시 RW 영구차단 방지) + PAUSE timeout fail-safe(긴 트랜잭션 시 abort+RESUME). config/minor 한정(major·HA 범위 밖). `make pg-restart`.
- **compose pgbouncer `ADMIN_USERS=${AGENT_KB_PG_USER}`(=agent_kb_rw)** — admin 콘솔 PAUSE/RESUME 인증 가능(기본 admin_users=postgres 는 userlist 부재로 불가였음). **적용엔 pgbouncer 1회 recreate(짧은 RW blip) 필요**, 이후 pg-restart 는 near-zero.
- **`deploy-web.sh reconcile_caddy()`** — 호스트/컨테이너 Caddyfile sha 비교 → 변경 시에만 `caddy adapt` 검증 후 recreate(WSL2 bind-mount inode-stale 대응 — reload 로는 옛 내용 재독). 무변경 시 무접촉(blip 0).

### 라이브 실증
- pgbouncer `ADMIN_USERS=agent_kb_rw` recreate 적용 → `pg-restart --check` admin 콘솔 OK(PgBouncer 1.25.1). pgbouncer 경유 RW 부하 루프 돌리며 `make pg-restart` → **RW 무에러**(에러 0, MAX_QUERY_WAIT 14s 는 큐 지연), RESUME 후 paused DB=0. reconcile_caddy 는 현재 무변경이라 no-op 경로 확인. 정본: `unit/feature-0016-zd-pg-pause-caddy/docs/TEST.md`.

### 보안 메모
- agent_kb_rw 를 pgbouncer admin_users 로 재사용 — 내부 신뢰 role + dbnet 전용이라 수용. 전용 admin user 분리는 하드닝 후속.

## 2026-06-30 — feature-0017: 배포 스파인 빌드 게이트 false-failure 수정

### 변경 (운영자 영향)
- **snap-docker metadata-file race false-ABORT 해소** — snap 설치 docker(29.3.1/compose v5.1.1/buildx v0.31.1) strict confinement 에서 compose 가 이미지를 정상 빌드·태깅 후 `/tmp` metadata 파일을 다른 mount ns 라 못 읽어 EXIT 1 반환 → 기존 게이트(exit-only)가 **이 호스트의 모든 web 배포를 false-ABORT**(feature-0003 PR #481 포함).
- `bin/deploy-web.sh` `build_image` 게이트를 `docker image inspect mysql-ai-web:<sha>` 의 GIT_COMMIT 라벨==sha 정합 검증으로 보강: EXIT≠0 은 로그 metadata-race 마커(3중 AND)일 때만 양성무시, 진짜 빌드 실패는 ABORT(음성 보존), `/readyz` git_commit 게이트가 2차 방어.

### 검증
- 격리(main repo .env 재현): positive(EXIT=1+이미지 GIT_COMMIT 라벨 일치+마커 → PASS 양성무시) / negative(존재 안 하는 sha → GIT_COMMIT 빈값 → ABORT). end-to-end 롤링 배포 완주 검증은 머지 후 라이브 단계. 정본: `unit/feature-0017-deploy-build-gate/docs/{FUNCTION,TEST}.md`.
