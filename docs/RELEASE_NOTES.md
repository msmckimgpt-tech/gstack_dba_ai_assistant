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

## 2026-07-02 — feature-0016-metadata-graph: 그래프 뷰 상호작용·가시성 진화 (렌더러 G6 전환 · 우클릭 상세 · 초기 진입 · 검색 강조 · 더블클릭 카메라 · 추정관계 자기교정 실동작)

### 변경 (관리자/운영자 영향)
- **그래프 렌더러 Cytoscape(WebGL) → AntV G6 v5(Canvas) 전면 교체 (ADR-004)** — 대규모 스키마 그래프의 확대·이동·펼침 매끄러움/선명도 기반 재정비. 클러스터 다열 masonry + 가변폭 shelf-packing 레이아웃(graph-g6b)으로 카드 배치 밀도 개선.
- **노드 우클릭 상세 상호작용 (graph-ctxmenu)** — 노드 컨텍스트 메뉴 + 관계 상세 패널 + 해당 노드 중심 보기(center-on). 스키마 카드 우클릭 메뉴 + 카드 라벨을 개수 badge 로 압축(schema-card-ctxmenu). 검색 시 스키마 카드 badge 매칭/전체 표기(search-badge).
- **초기 진입 가시성 개선 (graph-initview)** — 진입 시 스키마-우선 배치 + 줌 클램프 + 미니맵. 넓은 그래프에서 현재 위치 파악 용이화.
- **노드 펼침/더블클릭 성능·카메라 정비** — 테이블 노드 펼침 논블로킹화(graph-perf-bg, ADR-005) + 더블클릭 프리즈 잔존 해소 per-node setElementState→setData rebuild(graph-expand-perf, ADR-006) + 더블클릭 카메라 순간이동 재배치 해소를 앵커-중심 애니 팬으로 교체(graph-dblclick-cam, ADR-008).
- **추정/신뢰 관계 자기교정 파이프라인 미가동 근본수정 (rel-selfheal, ADR-007)** — 07-01 발표한 추정(inferred)·신뢰(trusted) 관계 자기교정이, config `__all__` 누락으로 star-import 소비자(insight)에서 발생한 NameError 를 per-schema except 가 삼켜 06-29 부터 3일간 insight 스키마 처리(인사이트 갱신+FK introspect+추론+프로브) 전체가 조용히 정지했던 결함 해소. AST 회귀가드 신설 + 주기 cadence(reinfer) + 게임 DB 관용 PK(uniqueid/unique_id) 인식 + 파서 qualifier/스키마-slot 규약 통일. §18.8 적대 패널 재검증 라운드(instance-scan 커서 DB별 분리·write-back slot 한정·프로브 실행오류·1:N 라우터 컨텍스트 스냅샷) 반영.
- **그래프 관계 분석 전용 모델 분리 (node-analysis-haiku)** — 그래프 관계 능동 분석 경로를 claude-haiku 로 분리(내부 모델 라우팅, 사용자 무체감).

### 잔여
- PB-0008 라이브 브라우저 그래프 UI 실화면 검증(G6 렌더러 교체 후 우클릭/중심보기/초기진입/검색강조/더블클릭 카메라·추정↔신뢰 엣지 시각)은 배포 후. 정본: `unit/feature-0016-metadata-graph/docs/{REPORT,DECISIONS,TEST}.md`(ADR-004~008).

## 2026-07-02 — feature-0003-agent-web-ui: AI 운영 관제 패널 + LLM 계측 확장 + 감사 UX 정비

### 변경 (관리자/운영자 영향)
- **관리 콘솔 > 감사 > 'AI 운영 현황' 탭 신설 (aiops-panel)** — 상태 배너(worst-of 롤업)·KPI·Attention·카테고리 드릴다운·활동 feed·계측 커버리지. `/api/admin/ai-ops` (권한 `console.aiops.read`, admin 전용, 5곳 sync + fail-open 방지). 대시보드에 AI 상태 타일(deep-link) 추가.
- **web 4경로 LLM 계측 확장** — 프롬프트 자동생성(비스트리밍/스트리밍)·자율 sweep·메타 자동완성 경로 계측 + `agent_runtime.llm_usage.latency_ms` 마이그(0030) + shared taxonomy 레지스트리(self-surface). main agent latency 계측 및 최근 활동 cursor 페이징(‘더 보기’, aiops-activity-paging) 추가.
- **최근 활동 클릭 상세 확장 + 감사 UX 정비 (audit-nav-ux)** — 최근 활동 행을 클릭 요약행 + 인라인 아코디언 상세(작업·서빙 모델·토큰·비용·지연·run_id·연결 대화 딥링크)로 재구성. 감사 카테고리 순서 재구성 + 4개 탭 네이티브 툴팁. 시스템 sentinel 활동의 대화 링크 깨짐 수정(aiops-conv-link-fix). AI 운영 현황 pane 세로 스크롤 수정(aiops-scroll).
- **메타데이터 관리 권한 그리드 계층 정합 (metadata-perm-hier)** — 07-01 세분화한 `metadata.*` 5키를 권한 그리드에서 다른 관리 그룹과 동일한 ‘그룹 게이트→세부’ 2단 계층으로 표시 정합화(표시 계층만 — RBAC enforcement/스키마/개별 부여성 B안 무변경).
- **첨부 개수 배지 stale 수정 (attach-count-scope, work)** — 입력창 ‘+’ 메뉴 첨부 개수 배지가 대화 전환 후 이전 대화 개수를 보이던 문제 수정(대화 스코프 정합).

### 잔여
- web 재배포(deploy_scope: included) 후 PB-0008 Windows-browser 라이브 실측. 정본: `unit/feature-0003-agent-web-ui/docs/{REPORT,TASK,TEST}.md`.

## 2026-07-03 — feature-0016-metadata-graph: 그래프 뷰 진화 2차 (관계 기반 배치 · 유사 속성 영역화 · 제품 카테고리 · 자유 배치 · 역할 표식)

### 변경 (관리자 영향 — 관리 콘솔 관계도(그래프) 뷰)
- **관계 기반 배치 + 유사 속성 그룹 영역화** — 스키마를 관계 가중(seriation·컴포넌트 군집·barycenter 4-sweep)으로 재배치해 엣지 교차를 줄이고(ADR-012, force 재도입 기각), 이름·관계·역할이 유사한 테이블을 배경 박스+헤더로 영역화(ADR-013, 백엔드 시맨틱 클러스터링은 후속 이연).
- **제품(Products) 단위 카테고리 개요 (ADR-014)** — 진입 시 제품→데이터소스 계층 개요를 먼저 보여주고 항목 클릭으로 상세 관계도 진입. 투영 API 질의 시점에 MySQL SSOT(`WebProducts`/`WebProductDatasources`)로부터 합성(AGE 물리 저장·마이그레이션 0).
- **자유 배치 상호작용 복원 (ADR-015)** — 결정론 배치 위에 사용자 드래그 offset 레이어(클러스터/카드 통째 이동·개별 노드 절대 위치·combo auto-fit 리사이즈)로 접기/펼치기·드래그·반응형 유지.
- **역할 시각 표식 (node-role-viz, ADR-010)** — AI 능동 분석이 끝난 테이블을 8종 역할(기준정보/계정/거래/로그/매핑/설정/통계 등)로 분류해 색(Okabe-Ito)·아이콘·범례로 표시(alembic 0031, `node_analysis_jobs.role` 비파괴 ADD).
- **관계 탐색·상호작용** — 접힌 상태 테이블 간 관계 표시, 상세 패널 관계 컬럼 아코디언(참조함/받음 방향·개수·의미 툴팁), 단일클릭 관계 표시, 클러스터 상세 역할 접두사+행 클릭 노드 선택, 중간버튼 카메라 팬 + 테이블 종속 UI 동반 드래그, 더블클릭 카메라 팬 반응 지연(~350ms) 제거(ADR-011).
- **운영 관측** — 'AI 운영 현황' 최근 활동에 LLM 사용 대상(target) 표시(alembic 0032, `llm_usage.target` 비파괴 ADD). AI 능동 분석 진행 패널이 상세 패널 하단으로 이동 + 그래프 영역 반응형 높이.

### 정본
- `unit/feature-0016-metadata-graph/docs/{REPORT,TASK,DECISIONS}.md` — ADR-010~015 (feature-local). alembic 0031(role)·0032(target).

## 2026-07-03 — feature-0003-agent-web-ui: 데이터소스 평균 연결 응답 시간 + AI 운영 현황 지연 지표 재정의

### 변경 (관리자 영향)
- **데이터소스 상세 패널 평균 연결 응답 시간 표시 (ds-avg-latency)** — 관리 콘솔 > 데이터소스 상세 '연결 상태'에 최근 N회 평균 연결 응답 시간 표시. `shared/conn_health` 성공 probe 이동평균(`AGENT_CONN_AVG_WINDOW`, 기본 20)을 재사용(추가 probe/DB 부하 0·in-memory·마이그레이션 0). 성공 표본이 없으면 '측정 중'. **배포 + PB-0008 PASS(2026-07-03)**.
- **AI 운영 현황 지연(p50/p95) 지표를 '단계 간 간격'으로 재정의 (aiops-ttft)** — KPI가 답변 전체 왕복 시간(`latency_ms`, 답변 길이 비례) 대신 에이전트 라운드 사이 간격(도구 실행·오케스트레이션 = 신규 `step_gap_ms`)을 반영. `routers/ai_ops.py` KPI 질의 전환 + 다단계 요청 분모(M/R) 노출. alembic **0033**(`llm_usage.step_gap_ms` 비파괴 ADD), cross-cut feature-0002 계측. RBAC/엔드포인트/권한키 무변경.

## 2026-07-03 — feature-0009-group-conversation: 공유 링크 참여 알림

### 변경 (사용자 영향 — 작업 화면 그룹/공유 대화)
- **공유 링크 참여 시 대화 내 '참여 알림' pill + 기존 멤버 unread +1** — 공유 링크로 새 멤버가 처음 참여하면 대화 흐름 가운데에 시스템 알림이 표시되고, 기존 참여자에게는 안 읽은 메시지(unread) 배지로도 잡힙니다(가입자 본인 제외). `core_messages` 이벤트 행 + 표시 store system pill 이중 기록, `__event__` sentinel 로 LLM 히스토리에서 배제, 익명 공유뷰에서는 참여 이벤트/username 비노출. 마이그레이션 0·인가 경계 불변.

## 2026-07-03 — feature-0002 / feature-0007: insight 워커 부하 분산 · 상태표시 정정 · LLM 요청-레벨 fallback (안정성)

### 변경 (운영자 영향 — 대화 답변 품질·화면 동작 변화 없음)
- **insight-worker 동일구조 샤드 그룹화 (feature-0002)** — 날짜/번호 suffix 만 다른 동일구조 테이블(샤드)을 `(base_stem, 컬럼 지문)` 그룹으로 묶어 대표 1건만 LLM 분석하고 형제는 LLM 없이 전파(`table_group_insight` KV 상속). per-table 인사이트·NL→SQL grounding 무회귀, flag(`AGENT_INSIGHT_TABLE_GROUPING_ENABLED`) rollback 가능.
- **긴 분석 주기 중 healthcheck false-negative 해소 (feature-0002)** — 스키마·테이블 순회 중 진행-중 heartbeat(30s throttle)로 liveness 전진 → 'AI 운영 현황'에서 insight-worker 가 잘못 '중단'으로 표시되던 문제 해소(hang 탐지 의도 보존).
- **insight/graph 부하 분산 (feature-0002, TASK-0308)** — probe 격리(없는 DB→파단·transient backoff), circuit-open(DOWN) 데이터소스 scan skip(복구 시 자동 재개), batched graph sync(WAL fsync 대폭 감소) + incremental watermark + cron 이중 스케줄. 마이그레이션 0.
- **insight LLM 요청-레벨 fallback (feature-0007)** — `litellm_config.yaml` 3-deployment(claude-corp → root Max → 로컬 edge gemma) + `fallbacks`/`num_retries`. insight 생성 burst 로 계정 RPM/TPM 초과(429) 시 다음 계정/로컬로 즉시 우회해 생성 무중단. config-only·인가 경계 불변.

### 운영자 조치
- 배포 시 메타데이터 그래프 sync cron 재설치: `sudo bin/install-metadata-graph-sync-cron.sh`. 정본: `unit/feature-0002-agent-core/docs/{REPORT,TASK}.md` · `unit/feature-0007-bedrock-llm-provider/docs/{REPORT,TASK}.md`.

## 2026-07-04 — feature-0016 / feature-0009 / feature-0007: 그래프 뷰 대폭 확장 · 멤버 가시성 window 공유 · 용도별 LLM 라우팅

### 변경 (관리자 영향 — 관리 콘솔 관계도(그래프) 뷰)
- **의미 임베딩 클러스터링 (Phase C, ADR-018)** — 메타데이터 객체 시그니처를 bge-m3 로 임베딩해 kNN+union-find 로 의미 유사 클러스터를 구성(alembic 0035). 이름 휴리스틱만으로 잡히지 않던 유사군을 값 기반으로 보강.
- **크로스-데이터소스 관계 (Phase B, ADR-019)** — 시그니처 임베딩 구동 후보 + 신뢰 게이팅으로 서로 다른 데이터소스 간 관계를 추론·표시(alembic 0036, UI 마젠타 점선).
- **카테고리 그룹(sim-group) 상호작용 (ADR-020)** — 배경 영역(묶음)을 드래그·접기·반응형 리사이즈. 그룹 드래그 헤더 hit-test hotfix.
- **그래프 UX 7건 + z-order 정합 (graphux7, graph-zorder)** — 상세 패널 뒤로/앞으로·관계 단/더블 클릭 구분·범례 3탭 정리·중복 분석 방어·데이터소스 라벨 정합 + 겹침 순서(`_METZ` 단일 스케일 bake+드래그 부스트/복원, FUNCTION §13)·관계도 최상위 탭 분리+검색 부드러운 하이라이트·더블클릭 재배치 순서 안정화·AI 능동 분석 팝오버 Esc 닫힘 hotfix.

### 변경 (사용자 영향 — 작업 화면)
- **멤버 가시성 window 공유 (share-visibility-window, Critical — SECURITY §21/§21.4)** — '여기부터/여기까지'로 공유가 `[from,to]` window 만 노출하고, 가려진 구간을 참여자의 라이브 뷰·LLM recall·fork 전부에서 물리 배제(프롬프트 인젝션으로도 추출 불가). `conversation_members` window 컬럼 + `has_restricted_members` 게이트(alembic 0037, additive) + recall/display 양 loader 필터(fail-closed) + fork clip + join stamp never-widen. `has_restricted_members=false` 대화는 필터 완전 우회(무회귀).
- **말풍선 ☰ 메뉴 통합** — 말풍선 액션(샘플 등록·여기서 분기·여기까지/여기부터 공유·'AI 로 고치기')을 kebab ☰ 메뉴로 통합, 피드백 👍/👎만 메뉴 밖 유지.

### 변경 (운영자 영향 — 화면 변화 없음)
- **용도별 LLM 라우팅 분리 (llm-routing-interactive-split, feature-0007, ADR-002 feature-local)** — insight-worker 가 주말/야간 gemma 로 고착(refresh-oauth cron 평일한정 → 토큰 만료 → edge 강등)하던 현상 해소. 사람 실시간(대화·AI 능동 분석)=항상 claude / 백그라운드 insight 배치=시각 기반 분리 + fallback 체인 결함 수정 + refresh/keepalive cron 24/7 확장.

### 정본
- `unit/feature-0016-metadata-graph/docs/{REPORT,TASK,DECISIONS}.md`(ADR-016~020, alembic 0034~0036) · `unit/feature-0009-group-conversation/docs/*` + `docs/SECURITY.md` §21/§21.4 · `unit/feature-0007-bedrock-llm-provider/docs/*`.

## 2026-07-06 — feature-0003 / feature-0016: 대화 화면 추론 강도 선택 · 함수/프로시저 노드 + DB 단위 AI 능동 분석

### 변경 (사용자 영향 — 대화 화면)
- **사용자 지정 추론 강도 (reasoning-effort, Major)** — 대화 composer '+' 메뉴에 "추론 강도" 4단계(낮음/일반/높음/매우 높음)를 추가, 대화별 영구 저장(KV). `/api/ask` 가 명시 레벨을 요청 단위 `extra_body.thinking.budget_tokens` 로 override('일반'=no-override=alias 기본), `litellm_config` 무변경. 비-thinking 모델에선 비활성. cross-unit feature-0002 `_call_llm`·`shared/model_catalog`. **PB-0008 PASS**.

### 변경 (관리자 영향 — 관계도 뷰)
- **전 datasource 함수·프로시저 가시화 (routine backfill)** — `routine_objects` SSOT + AGE `Routine` 노드 + 정의 파싱으로 참조 테이블 엣지(alembic 0034). `bin/routine-backfill.sh`·`routine_backfill.py` 로 insight cadence 대기 없이 결정론 적재(도달 4 ds·2,201 routines 라이브 backfill).
- **DB(스키마) 단위 'AI 능동 분석'** — `analyze-schema` 엔드포인트로 데이터베이스 단위 일괄 분석(재귀 0 보장·비용 가드 only_missing+cap 200/hard 500+confirm, FUNCTION §15).
- **그래프 뷰 개선 5건 (graph-navfilter-routine)** — 상세 패널 뒤로/앞으로(view-typed 이력)·노드 종류 필터(관계/함수/프로시저 토글, localStorage)·검색 구성 보존(additive overlay)·DB 단위 분석의 Routine 포함(테이블 우선 cap)·프로시저 파라미터 수직 배치(FUNCTION §16). **PB-0008 PASS**.

### 정본
- `unit/feature-0003-agent-web-ui/docs/*`(reasoning-effort, TASK-20260706T013532) · `unit/feature-0016-metadata-graph/docs/*`(§53~54, alembic 0034).

## 2026-07-07 — feature-0018 / feature-0016 / feature-0002: 런타임 설정 콘솔 · 제품 카테고리 밴드 + 크로스-DB 관계 일반화 · 대화 답변 안정성

### 변경 (관리자 영향)
- **런타임 설정 콘솔 (runtime-settings, feature-0018, Major)** — 관리 콘솔 '시스템 > 설정'에 assistant 운영 값(실행 타임아웃·MCP 타임아웃·모델별 추론 예산)을 조정·저장·런타임 반영. `WebRuntimeSettings` 테이블 + `routers/admin_settings.py`(GET/PUT/DELETE, `system.runtime.read/write` RBAC+audit, autocommit=False 원자화) + `shared/runtime_settings.py` 레지스트리/resolver(live TTL / restart frozen). env-fallback 으로 배포 `.env` 존중(override 없으면 byte-동치). live(즉시)·restart(재배포) 하이브리드 반영. **PB-0008 PASS**.
- **제품 카테고리 밴드 + 크로스-DB 관계 일반화 + DB 분석 재귀·refine (§55, ADR-021, alembic 0038)** — 관계도에 제품 카테고리 '띠(밴드)'(CAT/CATH/CATX, `WebProductDatabases` 질의시점 합성·밴드별 shelf-pack·헤더 드래그·접기·미분류 후미) + 크로스-DB 관계 일반화(xschema — 같은 DS 다른 DB, MSSQL 3-part 프로브 dbo 가드) + 관계 수동 큐레이션 API/UI(trust/break) + DB 단위 분석 재귀 전개(per-seed anchor·예산 cap)·refine-not-override·back-refine. **PB-0008 PASS**.

### 변경 (운영자 영향 — 대화 답변 품질·화면 변화 없음)
- **대화 답변 경로 edge(gemma) 폴백 완전 차단 (feature-0002)** — 특정 상황에서 대화 답변이 성능이 낮은 로컬 임시 모델(edge/gemma)로 처리되며 이전 맥락을 놓치던 문제를 근본 차단(conversation_audit FR-edge-fallback-conversation-context-loss, CHG-20260707T100640). 대화 답변은 항상 정규 모델 경로로 처리.

### 정본
- `unit/feature-0003-agent-web-ui/docs/*`(runtime-settings, TASK-20260706T094937 — feature-0018 코드 거주) · `unit/feature-0016-metadata-graph/docs/*`(§55, ADR-021, alembic 0038) · `unit/feature-0002-agent-core/docs/*`(edge-fallback) · `docs/improvements/conversation-audit/FRICTION_LEDGER.md`.

## 2026-07-07 — feature-0002 / feature-0003 / feature-0016: 지식베이스 채택 인박스 + ENUM 대화 자율수집 · 메타데이터 콘솔 IA 통합 · 그래프 sync 견고화(§56) (07-07 후속 — 11:34 이후 머지분)

### 변경 (관리자 영향 — 지식베이스)
- **지식베이스 채택 인박스 + ENUM 코드사전 대화 자율수집 (0beb02e3)** — 대화 후보수집(용어사전+ENUM)을 통합 "채택 인박스"로 재구성. ENUM 코드사전을 용어사전(0021/0023)과 대칭으로 신설: 대화 답변 직후 `(table.column)` 코드↔라벨 후보를 LLM 으로 추론(threshold ≥0.9 자동승급, 미만 검토 큐) — `enum_dictionary.source`(manual|auto) 컬럼 + `enum_feedback` 검토 큐(alembic **0039**, 비파괴·멱등), 신규 권한 **`kb.enum.curate`**(admin seed·검토큐 promote/reject 게이트·catchup fail-closed lockout), enum-feedback API. UI: 신뢰도/상태별 그룹 카드 + 개별/일괄 채택·거부·되돌리기 + 사이드바 pending 배지. env: `AGENT_ENUM_AUTOPROPOSE`(기본 on)·`AGENT_ENUM_SUGGEST_MODEL`·`AGENT_ENUM_AUTOPROMOTE_THRESHOLD`(0.9)·`AGENT_ENUM_SUGGEST_MAX`(5).
- **메타데이터 콘솔 IA 통합 + 5서브뷰 디자인 폴리시 (47a63b1a, UI 단독)** — 채택 인박스·샘플 검수 최상위 탭을 각 사전 하위 `{목록 | 검토/검수 큐}` 2차 보기로 통합(2차 보기 파라미터화). ENUM 후보=ENUM 코드사전 하위, 샘플 검수=샘플쿼리 하위. 5서브뷰 폴리시(`--surface-2` 토큰·rich empty+skeleton·테이블 카드 그룹핑·폼 grid+인라인검증·SQL 프리뷰·배지 semantic 토큰·이모지 제거+KPI). 백엔드/스키마/RBAC 정의 0.
- **추론 강도별 예산 설정 (d9516aee)** — 런타임 설정(feature-0018)에 모델별 예산과 별개로 추론 강도(낮음/높음/매우 높음)별 `reasoning_budget` 축 추가(`shared/runtime_settings.py`·`_call_llm` 명시레벨 override·'일반'=no-override 무회귀). pane UI 정렬 grid + commit-bar 재설계(a2fe4103, 기능 불변).

### 변경 (내부 — 관계도 데이터 정합, 화면 변화 없음)
- **그래프 sync 견고화 §56 (fe05d6f8·94e2e411, feature-local ADR-022~023, 마이그 0)** — 루틴(함수/프로시저) sync 정합 RC1~5: `_sync_row_guard` SAVEPOINT 행 격리(실패 행만 롤백·연쇄/배치 소실 차단)·워터마크 전진 게이트(errors→step_failures)·크로스-DB ROUTINE_USES 참조 채택(parser qualifier 4규칙 + external_tables 실재검증 TTL 600s)·thin "연결 정보 없음" 공란 동치·backfill read-axis scope 정규화·MSSQL store label lower 정규화(`normalize_db_label`)+케이스-변형 행 멱등 자동 회수. POST-DEPLOY e2e 완수: errors 0·step_failures 0·크로스 ROUTINE_USES 1,041·case_purged 6,320(잔여 0)·워터마크 전진. + §55 그래프 화살표 데이터흐름 정합(쓰기=루틴→테이블 / 읽기·미상=테이블→루틴)+AI 능동 분석 지침 플로팅 툴팁(b0d9deb6).
- **OAuth 토큰 갱신 cron 정적 검사 전환 (feature-0007, 058fec05)** — 라이브 probe 제거 → 정적 검사(CHG-20260707-oauth-cron-static-refresh).

### 정본
- `unit/feature-0002-agent-core/docs/*`(ENUM 자율수집·추론 강도별 예산) · `unit/feature-0003-agent-web-ui/docs/*`(채택 인박스 UI·콘솔 IA 통합) · `unit/feature-0016-metadata-graph/docs/*`(§56, feature-local ADR-022~023) · `unit/feature-0007-bedrock-llm-provider/docs/*`(oauth-cron-static).

## 2026-07-08 — feature-0016 / feature-0003: 관계도 접힘 카드 연결선·상대 하이라이트·중간 줌 LOD · 분석 기반 제품 분류 'AI 제안→사람 승인' · 메타데이터 콘솔 검토 화면 UX

### 변경 (관리자 영향 — 관계도 뷰)
- **접힘 카드 연결선·상대 하이라이트·크로스 색 구분·중간 줌 LOD (§57, feature-local ADR-024, 마이그 0)** — 관계도에서 데이터베이스(스키마) 카드를 펼치지 않아도 카드 간 연결선과 연결 개수를 표시(`SCHEMA_REF` 질의시점 1-hop 스키마-쌍 무향 집계·cap 400·렌더 3단 승격 컬럼→테이블→스키마 카드, 양쪽 접힘일 때만) + 선택 노드 1-hop 상대 하이라이트(비인접 dim, rebuild-bake) + 크로스-DB `ROUTINE_USES` 마젠타 색 구분(직교 인코딩) + 중간 줌 LOD(줌<0.35 ∧ 모델 엣지>120 무상태 FK·비크로스 단건 축약). POST-DEPLOY PB-0008 라이브 PASS(상대 dim 358/361·마젠타 51·LOD dropped 520, PR #623).

### 변경 (관리자 영향 — 제품 분류)
- **분석 기반 제품 분류 'AI 제안→사람 승인' 파이프라인 (§59, feature-local ADR-025, 마이그 0)** — 데이터베이스→제품(카테고리) 매핑을 이름 규칙에서 분석 신호(테이블 구성·`node_analysis` 요약)로 개선. 매핑 테이블(`WebProductDatabases`)이 에이전트 접근 allowlist 를 겸하므로 LLM 산출은 **Pending(`RuleId` NULL·`Reason='ai_suggest:<conf>'`) 적재까지만** — 사람이 제품 관리의 "✨ AI 분류 제안"에서 승인(`Source='ai'`)/거부. 환각 차단 3중 게이트(스키마 실재·datasource 연결 제품 화이트리스트·`MIN_CONF` 0.6)·데몬 기본 OFF(`AGENT_PRODUCT_CLASSIFY_AUTO`). 접근 allowlist 무변경(보안 경계 신설 아님·기존 `product.manage` 승인). POST-DEPLOY 라이브 실증(dry-run 11→10건 Pending 적재, PR #626).

### 변경 (관리자 영향 — 메타데이터 콘솔)
- **메타데이터 콘솔 검토 화면 UX 4건 + 디자인 폴리시 5건 (metadata-console-ux2 / -polish, UI 단독)** — 검토·검수 큐 후보 행 클릭 시 우측 read-only 상세 패널(전체 정의·질문/SQL/다이어그램·신뢰도, '선택 불가' 해소) + ENUM 코드사전 그룹 "+ 코드 추가" pre-fill + 샘플 검수 큐 mermaid 다이어그램 렌더(공용 `mermaid-render.js` strict) + 목록 가독성. 디자인 폴리시 5건(2차 보기 필 위계·list-detail 균형·그룹 nesting·timestamp 경량·신뢰도 배지 accent). 백엔드/RBAC/스키마 0.

### 변경 (내부 — 화면 변화 없음)
- **스키마 골격 가져오기 MSSQL 라벨 케이스 정합 + gateway 안정화 (§58, feature-0003 + infra)** — '스키마 골격 가져오기' MSSQL 분기 라벨 케이스 정규화(`normalize_db_label`, §56 RC5 계약의 테이블 축 확장)로 특정 MSSQL 데이터소스 중복 카드 해소 + AccountDB 33행 rekey(AGE 34정점 회수). bedrock-gateway OOM 재시작 루프 → `mem_limit` 2g 영속화(compose 중복 키 배포 차단 정정, #625→#627).

### 정본
- `unit/feature-0016-metadata-graph/docs/*`(§57~59, feature-local ADR-024~025) · `unit/feature-0003-agent-web-ui/docs/*`(metadata-console-ux2/-polish·product-classify-suggest UI) · `unit/feature-0002-agent-core/docs/*`(§59 분류 엔진 코드 거주 product_classify/llm/insight).

## 2026-07-09 — feature-0018 / feature-0003: 모델별 추론 예산 상한 확대 + 추론↔본문 비율 배분

### 변경 (관리자 영향 — 런타임 설정)
- **‘모델별 추론 예산’ 재구성 + 상한 native 확대 (feature-0018, 코드 거주 feature-0003/0002)** — 관리 콘솔 시스템 > 설정의 ‘모델별 추론 예산’을 모델별 카드(접기/펼치기)로 재구성하고, 총 출력 한도(`max_tokens`)를 모델 실성능(Sonnet 128,000 · Haiku 64,000 토큰)까지 상향 허용(이전 ‘매우 높음’ 최대값=기본값이라 위로 조정 불가하던 제약 해소). 추론 강도(낮음·높음·매우 높음)별 예산을 모델마다 분리하고, 추론↔본문 출력 비율 슬라이더로 배분(남는 본문 여유 표시·총 출력을 크게 잡으면 실행 제한 시간도 함께 올려야 할 수 있다는 안내).

### 정본
- `unit/feature-0003-agent-web-ui/docs/*`(WebRuntimeSettings·admin_settings) · `unit/feature-0002-agent-core/docs/*`(`reasoning_budget`·`shared/runtime_settings`).

## 2026-07-10 — feature-0016 / feature-0003 / feature-0002: 관계도 대규모 성능·정리 + 상세 내비·강조 안정화 · 응답 지연 타임아웃 모달 제거 · AI 능동 분석 ‘주의’ 실질화 · 인증실패 회복력 (07-09~10 머지분)

### 변경 (관리자 영향 — 관계도 뷰, §60~76)
- **대규모 관계도 성능·정리 (§60~67·§73~76, feature-local ADR-028~033/035~037, 마이그 0)** — 스키마 펼침 시 세로 폭주 해소(적응형 폭 + 실높이 열 balance, ADR-028)·노드-레벨 컬럼 LOD(ADR-029)·뷰포트 컬링(화면 밖 미그리기, ADR-032) + 컬링 노드의 참조/상호작용 보존(ADR-037)·배치정렬 위상서명 메모이즈(줌인 근본해소, POST-DEPLOY 882노드 7.4×, ADR-035)·미니맵 전체이미지 재사용(ADR-036). 극단 줌아웃 클러스터 집계 카드(ADR-030/031)는 규모·구조 파악 저해로 §67 폐기(ADR-033 — 뷰포트 컬링 + 컬럼 LOD 만 잔존). 사용자 체감: 수백 테이블·수천 항목 규모에서 확대·축소·이동이 매끄럽고 화면 밖 요소 자동 생략(연결선·상세 이동은 보존).
- **상세 패널 내비·사용 관계 read/write 분리 (§68~72·§75)** — 상세 패널의 사용(참조) 관계를 읽기/쓰기 그룹으로 분리(§68), 선택 노드/관계행/미렌더 컬럼으로 카메라 이동(§70~72), 상세 컬럼 목록에서 직접 컬럼 선택(§75), 중복 관계행 병합(§69).
- **관계 강조·엣지 팬 안정화 (§57.4~9·§62·§64·§66, feature-local ADR-026~028/031)** — 선택 노드 상대 하이라이트 즉시·정확 점등(빌드시점 인접 재산출·직렬화 bake 단일 진실)·선택 노드 오-침강 및 dim 영구고착 해소·유령 관계선 잔상 제거(§66)·줌아웃 하이라이트 LOD 정규화(§64)·관계선(엣지) 위 중간(휠)버튼 카메라 팬(§62, 엣지 자체는 비이동 보존).
- **상단 툴바 통합 (graph-toolbar)** — 흩어진 13 컨트롤을 3존(검색·보기 옵션 팝오버·초기화·상세)으로 압축, 줌·상태는 캔버스 플로팅 오버레이로 이동(상태 텍스트 reflow 제거).

### 변경 (작업 화면)
- **응답 지연 타임아웃 복구 모달 제거 (feature-0003, ask-timeout-nonblocking)** — 답변 생성이 오래 걸릴 때 화면 전체를 덮으며 선택을 요구하던 복구 모달(z-9999) 제거 → 모달·토스트 없는 조용한 자동 재연결. 취소/즉시답변은 컴포저 인라인 버튼 상시. 배포 4b6919ec·POST-DEPLOY PB-0008 라이브 PASS.

### 변경 (관리자 영향 — AI 능동 분석 품질, §69)
- **능동 노드분석 caveats 계약 재설계 (§69, feature-local ADR-034)** — AI 노드 능동 분석의 ‘주의’ 항목이 ‘불완전 메타/직접 확인 필요’ 형식적 자기-불평 대신 실질 운영·보안 포인트(비가역 삭제·cascade, 민감·현금성 데이터, 대량데이터 성능/잠금, 미검증 FK 데이터품질)만 짚도록 프롬프트 재설계 + Routine(함수/프로시저) touches 읽기/쓰기 구분·returns payload 투영·시드 커버리지 확대. **T69.5 POST-DEPLOY 완수(07-10 배포 a24415a5 + `cc_data_main` 재생성 run 7c75ddcb: 715/715 done·0 failed, PR #744)** — 표본 재확인 시 옛 자기-불평 사실상 0(사용자 원 리포트 ‘대부분 노드 주의가 불명확’ 해소) → 사용자 릴리즈노트 편입.

### 변경 (내부 — 화면 변화 없음)
- **MSSQL 인증 실패 순회 조기 skip + datasource cooldown (feature-0002, §12.3, 마이그 0)** — insight-worker 순회에서 MSSQL 로그인 실패(18456)를 감지하면 같은 datasource 의 나머지 등록 DB 를 cycle 내 조기 skip + datasource label 키 cooldown(기본 600s, `AGENT_INSIGHT_AUTH_COOLDOWN_SEC`)으로 운영자 GRANT 복구 전 반복 재연결·로그·I/O 억제(복구권위 = TTL 만료). DB/객체별 권한거부(916/229/297)는 로그인 성공 상태라 해당 DB 만 실패·순회 계속(로그인 실패 전용).

### 정본
- `unit/feature-0016-metadata-graph/docs/*`(§57.4~9·§60~76, feature-local ADR-026~037) · `unit/feature-0003-agent-web-ui/docs/*`(ask-timeout-nonblocking·graph-toolbar) · `unit/feature-0002-agent-core/docs/*`(mssql-auth-cooldown §12.3·§69 node-analysis 코드 거주).

## 2026-09-08 — 러너 동시 갱신 복구 / DQA Connect 1.1.1

- 같은 머신의 러너들이 공유 파일을 동시에 갱신해도 완성된 파일로 교체하고 각각 새 빌드로 돌아오도록 수정했다.
- 앱이 띄운 러너가 비정상 종료되면 최대 5회 백오프로 재기동한다. 자동 복구 실패와 정상 종료는 연결 단절을 알리고, 사용자가 연결을 끊으면 재시도를 취소한다.
- 갱신 실패 안내가 없어진 터미널 명령 대신 앱 업데이트와 재연결을 안내한다.
- 기존 앱 사용자는 앱에서 업데이트 확인 후 **1.1.1 설치·재연결**이 필요하다. 서버 배포만으로 이미 죽은 구 러너가 다시 뜨지는 않는다.

## 2026-09-08 — DQA Connect 1.1.2: 서비스 아이콘

- 마상소프트·마상게임즈 공식 심볼의 사선과 시안·보라·마젠타 흐름을 참고한 DQA Q·데이터 아이콘을 적용했다. 앱 창·트레이·실행 파일·설치기에 같은 아이콘을 쓴다.
- 1.1.1의 러너 복구 개선을 포함한다. 기존 앱의 **업데이트 확인** 또는 연결 화면의 **연결 프로그램 받기**로 적용한다. 웹 화면 색상 테마는 이번 변경에 포함하지 않는다.
- PR #1608 및 기존 릴리스 채널 배포 완료. Windows 5개 아이콘 표면 대조, 전체 클라이언트 테스트 524건, 실제 엣지 설치기 다운로드 크기·SHA-256 검증 PASS. 상세: [검증 기록](../unit/feature-0046-native-client/docs/test-runs.d/20260908T020049-brand-icon.md).


## 2026-09-08 — DQA 1.2.0: 내 AI 자동 연결

- DQA에 로그인하면 설치된 AI를 플랫폼별로 자동 연결합니다. 같은 AI가 여러 Windows/WSL 위치·계정에 있을 때만 고릅니다.
- 성공한 위치 선택을 클라이언트가 기억하고 다음 실행에서 확인해 재사용합니다.
- 연결 카드에서 상태·위치·재시도를 확인하고, 모델 등록까지 끝난 AI는 완료 알림으로 알려줍니다.
- 탐색·모델 확인을 병렬 처리하고, AI를 추가할 때 기존 연결을 유지합니다. 최신 아이콘과 자동 연결 복구 기능도 포함합니다.
- 기존 DQA 앱의 업데이트 확인을 통해 1.2.0을 설치합니다. 별도 러너 또는 Windows 브라우저 실행은 필요하지 않습니다.
