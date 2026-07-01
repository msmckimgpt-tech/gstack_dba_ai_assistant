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

## 2026-07-01 — feature-0016-metadata-graph: 그래프 뷰 진화 (WebGL · 암묵 관계 추론 · AI 능동 분석 · 권한 세분화)

### 변경 (관리자/운영자 영향)
- **그래프 렌더러 canvas-2D → WebGL 전환** — Cytoscape 3.34.0 `webgl:true`(feature-detect fallback). 노드가 많은 대규모 스키마 그래프에서 확대·이동·펼치기 프레임레이트 근본 개선(실 FPS 는 사용자 하드웨어 의존). 외곽선 선명화(texSize 4096·pixelRatio 2), 이동 중 라벨/엣지 유지.
- **암묵(FK 미선언) 관계 추론 + 자기교정 엔진** — FK 가 선언되지 않아 declared 엣지가 희소한 데이터소스에서 이름·구조 휴리스틱으로 **추정 관계(`source='inferred'`, 점선)**를 채우고, (a) 성공한 대화 JOIN 관찰 + (b) insight 워커 실데이터 겹침 프로브로 **동적 weight**(정적 confidence 와 분리)를 강화/감쇠. weight≤0.15 broken(숨김·주입 제외), ≥0.85+양성누적 trusted(실선), FK 는 권위적 불변. alembic 0026 비파괴 ADD. 노출: AI context digest(broken 제외·weight 정렬·추정/신뢰 태그)·AGE REFERENCES weight/status 투영·admin UI(신뢰=실선/추정=점선/파단=숨김+범례·배지). 정본 ADR-002.
- **AI 능동 분석 — 앵커-상대 관련도 게이팅 + 실시간 진행 패널** — 노드 능동 분석 시 처음 선택한 앵커 기준 관련도로 재귀 확장을 게이팅(무관 분기 번짐 억제, alembic 0029 `node_analysis_jobs.relevance`, ADR-003). 진행 현황(완료/분석중/대기/실패)을 우측 패널에 실시간 표시 + 세션 독립 폴 재개.
- **ERD 카드 컬럼 ordinal 세로배치 + 그래프 UX** — 표(노드)를 펼치면 컬럼이 테이블 compound 박스 안에 실제 순서(ordinal)대로 세로 정렬(겹침 원천 차단, alembic 0027 `column_descriptions.ordinal`). 단일클릭 컬럼 펼침/접힘, 상세 패널 드래그 리사이즈, 접기 버튼, 첫 컬럼명 가림 수정, 노드 드래그 엣지 유지, 클러스터명 WebGL 오버레이 정합 등 다수 개선.
- **메타데이터 관리 권한 5분할 (B안, Critical, PLAN-APPROVED)** — 단일 `kb.ingest.manual` 우산 권한을 `metadata.{glossary,enum,table,column}.manage` + `metadata.graph.read` 5키로 세분(담당자별 개별 위임). **비파괴·가역**: 우산 권한 유지 + 함의(implication)로 기존 grant 무손실·DB 마이그 0. 상세 정본: `docs/SECURITY.md §19` · feature-0003 REVIEW `REV-20260702T120000-graph-panel-perms`.

### 잔여
- PB-0008 라이브 브라우저 그래프 UI 시각검증(T5.4)·eval A/B(T5.1)·추정/신뢰 엣지 시각(점선/실선·배지) 실화면 확인은 배포 후. 정본: `unit/feature-0016-metadata-graph/docs/{REPORT,DECISIONS,TEST}.md`.

## 2026-07-01 — feature-0012-web-router-modularization: P5b 전체추출 완료 (내부 리팩터, behavior-neutral)

### 변경 (개발자 영향 — 사용자 무영향)
- **app.py 모놀리스 라우터 전체추출 완료** — feature-0003 `app.py`(단일 FastAPI app)의 **148 route 핸들러 전량을 21개 도메인 `APIRouter` 모듈로 byte-동치 추출**(app.py ~29K→18,917줄, 잔여 `@app` 라우트 0 — app.py = helpers + DI seam + `include_router`). route-parity 골든(경로·메서드·순서 불변)·프로덕션 응답 byte-동치 검증. **사용자 체감 변화 0**(behavior-neutral 내부 구조 리팩터).
- 배포: batch1-3 라이브 배포·검증 완료(main c031b5d — 추출 라우트 프로덕션 401 응답 verbatim 동일). batch4(잔여 16 route)는 추출 완료·재배포 검증 후속.

### 잔여
- `web_context` 헬퍼 전체 추출(별도 workstream)·프론트(admin.js/app.js/styles.css) 분할·Final 로그인 QA. 정본: `unit/feature-0012-web-router-modularization/docs/{REPORT,TASK}.md`.
