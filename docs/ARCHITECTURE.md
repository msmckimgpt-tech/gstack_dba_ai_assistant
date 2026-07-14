---
doc_type: ARCHITECTURE
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.37.2
domain: [architecture]
ai_read_priority: 4
---

# Architecture

## 1. 전체 구조
저장소는 크게 다음 영역으로 나뉜다.

- 공통 정책: `../AGENTS.md`, `./*`
- 기능 단위 구현: `../unit/<feature-id>/`
- 공통 코드 예약 영역: `../shared/`
- 파생 산출물: `../../artifacts/*`
- 환경값 정본 의미: `../.env` (원본 루트 `.env` 의미 유지)

## 2. 책임 분리
### 공통 정책 영역
프로젝트 전반에 적용되는 규칙, 제약, 용어, 보안 기준을 정의한다.

### 기능 영역
기능별 코드, 테스트, 명세, 변경 이력, 리뷰, 보고를 관리한다.

### 공통 코드 영역 (shared/)
여러 기능에서 공통으로 사용하는 코드가 생길 때만 사용한다.

### 산출물 영역
빌드 결과, 로그, MySQL 데이터, 세션 파일, 인증서 등 런타임 파생 결과를 저장한다.

## 3. 기능 단위 구조 원칙
각 기능은 아래 하위 구조를 가진다.
- `src/` : 기능 구현
- `tests/` : 기능 테스트
- `docs/` : 기능 문서

## 4. 현재 기능 맵
| 기능 ID | 책임 |
|---------|------|
| feature-0001-platform-runtime | MySQL 설정, DAB 설정, SQL 유틸리티 |
| feature-0002-agent-core | agent CLI 및 코어 모듈 + KB Postgres 최적화 (T1~T5, 2026-05-28) |
| feature-0003-agent-web-ui | FastAPI Web UI 및 정적 자산 + **audit subsystem (TASK-0073)** — `WebAuditEvents` + `record_audit_event` dispatcher + admin 11 / user 5 endpoint hook + `audit.*` 4 RBAC + chunked PK purge. SECURITY.md §9 정합. **+ AI 운영 관제 패널(2026-07-02)** — 신규 admin observability 엔드포인트 `GET /api/admin/ai-ops`(`routers/ai_ops.py`, 권한 `console.aiops.read` admin 전용, RO·PG 부분 degrade) + 대시보드 AI 상태 타일 + web 4경로 LLM 계측(alembic 0030 latency_ms · 0032 target · 0033 step_gap_ms). **(07-03)** 지연 KPI(p50/p95)를 호출 왕복→단계 간 간격(step_gap) 재정의(aiops-ttft, cross-cut 0002 계측). SECURITY.md §20 정합. **+ 런타임 설정 콘솔(2026-07-07, feature-0018 코드 거주)** — 관리 콘솔 시스템>설정에서 실행 타임아웃·모델별 추론 예산 조정·저장(`WebRuntimeSettings` + `routers/admin_settings.py` GET/PUT/DELETE·`system.runtime.read/write` RBAC+audit·autocommit=False 원자화) + `shared/runtime_settings.py` 레지스트리/resolver(live TTL / restart frozen, env-fallback 배포 .env 존중), cross-unit feature-0002 live 배선. |
| feature-0004-browser-automation | Playwright 브라우저 제어 |
| feature-0005-qa-mcp | MCP 테스트와 QA 스크립트 |
| feature-0006-lan-proxy-access | Caddy 및 Windows LAN 프록시 자산 + `_get_client_ip` X-Forwarded-For trust 정책 (SECURITY.md §9.7) |
| feature-0007-bedrock-llm-provider | AWS Bedrock (Claude) gateway — per-user OpenAI key 폐기, service-managed LLM provider (ADR-0026) |
| feature-0008-windows-browser-testing | 실제 Windows 브라우저 AI 자동 검증 (PB-0008 · ADR-0029) |
| feature-0009-group-conversation | 그룹 대화 — 멤버십·`@assistant` 멘션·**열람 ≠ 발화** RBAC 분리·라이브 UX + **멤버 가시성 [from,to] window 공유 격리** (SECURITY §21, 2026-07-04) (2026-06-19~07-04) |
| feature-0010-google-drive-integration | **Google Drive 연동 토대 (2026-06-23)** — 계정별 OAuth 토큰 암호화 저장(`WebGoogleDriveTokens`, cred_crypto AAD=`gdrive:{account_id}`) + connect/callback/status/disconnect 라우트 + MCP 구성 seam(`bin/gdrive-mcp.sh`·compose `gdrive-mcp`·`src/gdrive_mcp_seam.py` per-account 토큰 주입 A). **연동 미수행/기본 비활성**. SECURITY.md §17 정합. |
| feature-0011-shared-extraction | **공통 코드 `shared/` 점진 추출 (P5a, 2026-06-24)** — 저결합 공통 모듈(`model_catalog`·`config`·`db`)을 repo 루트 `shared/` 패키지로 **모듈 alias 이동**(Step1~3, 모든 심볼·monkeypatch·wildcard 보존 비파괴 shim) + Dockerfile/Makefile PYTHONPATH 배선, `make test` 회귀 0. feature-0002·0003·격리 컨테이너 공유 토대(`shared/` = DOC_REGISTRY 공통 코드 정본). |
| feature-0012-web-router-modularization | **feature-0003 `app.py` 도메인별 `APIRouter` 분할 (P5b — 2026-07-01 route 전체추출·2026-07-12 완결)** — route-parity 안전망(`test_route_parity_p5b.py` + 골든 route, 경로·메서드·순서 drift 적발) + handler→전역/helper 의존성 audit(`web_context` 경계 확정) → **148 route 핸들러 전량 21개 도메인 APIRouter 로 byte-동치 추출**(app.py ~29K→18,917줄, 잔여 `@app` 라우트 0, helpers+DI seam+`include_router` 잔류). behavior-neutral(경로·메서드·순서·응답 불변, 프로덕션 응답 실측 동일). **2026-07-12 완결** — ITEM-10(라우터 추출 + `web_context` 헬퍼 추출, 모듈 분리 -81%) + ITEM-11(잔여 인라인 authn DEFER 핸들러 실leak 13건 DI-rework·keep-inline 정당 37 명시분류) 완료(라이브 4c203f9c). 브라우저 로그인 QA = 자동 검증 다중 GREEN + 사용자 환경 게이트로 사용자 사인오프 이관. 잔여 initiative ITEM-09(그래프 CSS/JS 세분화·외부 브랜치, blocked)·프론트(admin.js/app.js) 분할 후속. |
| feature-0013-relationship-diagrams | **flow/관계 질문에 mermaid 다이어그램 답변 (2026-06-29)** — 웹 UI mermaid 렌더(vendor v10.9.3, sanitize-후 `securityLevel:'strict'` 렌더 + graceful fallback) + `_MERMAID_DIAGRAM_GUIDANCE` 발화(feature-0002) + `table_relationships` 관계 저장소(alembic 0024 — FK introspection·대화 JOIN 학습) + knowledge context 관계 digest 주입. cross-cut 코드 거주 feature-0002·0003. PB-0008 라이브 검증 PASS. |
| feature-0014-zero-downtime-deploy | **web 무중단 롤링 배포 구조 (2026-06-30)** — Caddy LB(web-a:8000 web-b:8000, sticky cookie + dial-retry-primary + active `/livez`) 뒤 2-replica 를 `bin/deploy-web.sh` 가 한 번에 하나씩 재시작(항상 ≥1 healthy upstream). 배포 스파인: flock 전체 직렬화 + origin/main coalesce, 단일 scoped-sudo 경계, `-f docker-compose.yml` only file-set, TLS preflight, `bin/migrate-lint.sh` expand/contract 게이트(CONVENTIONS §12), one-at-a-time + SSE pre-drain(`/livez` active_streams), post-cutover soak + 자동 롤백(last-good 이미지 pin). app.py `/livez`(DB-무관)·`/readyz`(DB-backed). :18080 web 직접 문 폐기(Caddy :443 단일). cross-cut 코드 거주 feature-0003(app.py)·0006(Caddyfile). |
| feature-0015-zd-hygiene-backup | **백엔드/DB 무중단 위생 + 백업 (2026-06-30, feature-0014 후속)** — feasibility 분석(wf_1d634d33: "HA 아니라 데이터 보존이 진짜 위험, 코드·expand 무중단은 이미 됨") 기반 저비용 위생작업. ① insight-worker SIGTERM graceful(`_INSIGHT_SHUTDOWN`+signal alias+interruptible wait, stop_grace_period 30s) — ask-worker 동형. ② MySQL online-DDL 강제 `bin/mysql-ddl-lint.sh`(diff-mode, LOCK=NONE)+CONVENTIONS §13. ③ 백업 갭: 범위 명시(sandbox 의도 제외)+`bin/restore-rehearsal.sh`(throwaway DB 복원검증)+`bin/install-backup-cron.sh`(멱등). cross-cut 코드 거주 feature-0002(insight). HA·DB엔진·호스트 무중단은 단일 호스트 SPOF 라 범위 밖. |
| feature-0016-metadata-graph | **AGE 메타데이터 지식그래프 + 그래프 뷰 UI + AI 정합 (2026-06-30)** — 관리콘솔 메타데이터를 평면 나열에서 탐색 가능한 지식그래프로 승급. 관계형 테이블을 SSOT 로 두고 Apache AGE `metadata_kb` 그래프(PG16 커스텀 이미지 = pgvector+pg_trgm+AGE 공존, alembic 0025: vlabel 6 Product/Datasource/Schema/Table/Column/GlossaryTerm + elabel 7)를 재생성 가능한 **투영**으로 동기화(`modules/metadata_graph.py` — 멱등 MERGE·Cypher injection 방어·8K 보호 cap·`_ensure_graph_indexes` 멱등 인덱스). 투영 API `GET /api/admin/metadata/graph?q=&node=&depth=&scope=`(RBAC kb.ingest.manual·RO 라우팅·검색/이웃/roots 모드·graceful). 관리콘솔 '🕸 그래프 뷰'(**PixiJS v8(WebGL/WebGPU, G6 v5 폴백 seam)** — 결정론적 배치·Combo 클러스터 다열 masonry·관련도 사이징·우클릭 컨텍스트 메뉴/관계 상세/중심 보기·논블로킹 펼침). per-datasource 투영(rag_objects ~21 ds·8,122 테이블)+scope 격리. `graph_navigate` AI tool(read-only search/neighbor — 대규모 스키마 컨텍스트 초과 해소). 운영 cutover 라이브 완료(primary/replica shared_preload='age' + role search_path, 데이터 무손상, 무중단 롤링). **(2026-07-02 진화)** 렌더러 canvas-2D→WebGL→**AntV G6 v5(Canvas)** 재교체(WebGL 텍스처 왜곡·오버레이 동기화 구조 소멸, feature-local ADR-004~008)·초기 진입 스키마-우선 가시성+미니맵·검색 스키마 카드 badge 매칭·암묵(FK 미선언) 관계 추론+**자기교정 파이프라인 상시화**(주기 cadence — 06-29 config `__all__` 누락 NameError 로 조용히 정지했던 결함 근본수정, alembic 0026, source='inferred', ADR-002)·AI 능동 분석 앵커-상대 관련도 게이팅(alembic 0029, ADR-003, 전용 모델 claude-haiku 분리)·ERD 컬럼 ordinal 세로배치(alembic 0027). cross-cut 코드 거주 feature-0002(코어·tool·insight·추론엔진)·0003(admin.js/admin.html 그래프뷰·메타데이터 탭 권한 5분할 metadata.*.manage+graph.read). **(2026-07-03~06 UX 확장)** 그래프 뷰가 관계 추적·자유배치·유사속성 그룹·제품 카테고리·함수/프로시저 노드·의미 임베딩 클러스터링·크로스-ds 관계·z-order/nav/kind 필터로 확장되고, 전 ds routine backfill + DB(스키마) 단위 AI 능동 분석이 추가됨. **(2026-07-07 §55)** 제품 카테고리 밴드 + 크로스-DB 관계 일반화(xschema) + DB 단위 분석 재귀 전개·refine-not-override(ADR-021, alembic 0038)까지 확장(구조·의존 불변 — 상세·근거 정본 = unit REPORT/DECISIONS feature-local ADR-010~021). **(2026-07-08 §57·§59)** 접힘 카드 집계 연결선(SCHEMA_REF)·상대 하이라이트·크로스 사용선 색 구분·중간 줌 LOD(§57, ADR-024) + 이름 기반이던 제품 카테고리 분류를 분석(테이블 구성·node_analysis) 신호 기반 'AI 제안→사람 승인' 파이프라인으로 승격(§59, ADR-025 — LLM 은 Pending 적재만, 접근 allowlist 무변경·product.manage 승인 시 반영)까지 확장(구조·의존 불변 — 정본 unit REPORT/DECISIONS feature-local ADR-024~025). **(2026-07-13 §78~§81)** 렌더 엔진 G6 v5(Canvas)→**PixiJS v8(WebGL/WebGPU)** 전면 교체 — G6 Canvas 매 프레임 CPU 재래스터 병목 해소(라이브 409객체 팬 60fps vsync-perfect), SceneAdapter seam 으로 UI·상호작용 무변경 어댑터 미러·G6 폴백 seam 유지, 후속 미니맵/드래그(§79)·라벨 BitmapText(§80)·상세패널 hover FX(§81) 라이브 배포 + 카테고리 밴드 '컨텐츠 단위' 그룹핑 실동작화(mig 0040)·p2(가짜 밴드 소멸·연관 밴드 인접)(구조·의존 불변 — 정본 unit TASK §78~81·content-cluster, feature-local ADR-004 supersede 예정). |
| feature-0016-zd-pg-pause-caddy | **무중단 조건부→가능 승격 (2026-06-30)** — ① PG primary 재시작을 near-zero RW 단절로: `bin/pg-restart.sh` 가 pgbouncer(transaction-mode) PAUSE(신규 RW 큐잉)→postgres recreate→healthy→RESUME, RESUME 을 trap 으로 보장(실패 시 RW 차단 방지), PAUSE timeout fail-safe. compose pgbouncer `ADMIN_USERS=${AGENT_KB_PG_USER}`(=agent_kb_rw, userlist 보유). config/minor 한정(major·HA 범위 밖). ② `deploy-web.sh reconcile_caddy()`: 호스트/컨테이너 Caddyfile sha 비교 → 변경 시에만 adapt 검증 후 caddy recreate(WSL2 bind-mount inode-stale 대응 — reload 무효). cross-cut feature-0002(PG)·0006(caddy). |
| feature-0017-deploy-build-gate | **deploy 스파인 빌드 게이트 false-failure 수정 (2026-06-30)** — snap 설치 docker(29.3.1/compose v5.1.1/buildx v0.31.1) strict confinement 에서 compose 가 이미지를 정상 빌드·태깅 후 /tmp metadata 파일을 다른 mount ns 라 못 읽어 EXIT 1 반환 → 기존 게이트(exit-only)가 모든 web 배포를 false-ABORT. `build_image` 게이트를 `docker image inspect mysql-ai-web:<sha>` GIT_COMMIT 라벨==sha 정합 검증으로 보강(EXIT≠0 은 로그 metadata-race 마커 3중 AND 일 때만 양성무시; 진짜 실패는 ABORT, /readyz 2차 방어). dc-build 의 기존 우회 패턴과 정합. cross-cut feature-0014(deploy-web.sh). |
| feature-0020-zd-deploy-all | **무중단 배포 커버리지 완성 (2026-07-14)** — feature-0014 스파인(`bin/deploy-web.sh`)을 전 배포 대상으로 확장: ① 워커(insight/ask) 자동 롤아웃(공용 agent 이미지 `mysql-ai-agent:<sha>` build-once 핀 + 순차 recreate + healthy/GIT_COMMIT 게이트 + agent last-good 자동 롤백 — 구 WARN-only divergence 대체) ② bedrock-gateway 드리프트(설정 sha 기록·bind inode-stale·이미지 ID) 시에만 **surge replica**(profile `deploy-surge`, DNS alias 합류)로 무중단 교체(steady-state 비용 0, stop_grace 120s drain) ③ caddy 이미지 태그 드리프트 recreate ④ `bin/alembic-migrate.sh` 직접 호출 stale-image 가드(upgrade/stamp 시 선행 재빌드) ⑤ 워커 healthcheck timeout 30s 견고화 + 라이브 적용 미커밋 compose 운영 튜닝 정식 커밋(live-truth). `make deploy-all`/`deploy-workers`/`ask-worker-*`. cross-cut 코드 거주 feature-0014(deploy-web.sh)·0002(agent Dockerfile 이미지)·0007(gateway compose). |

## 5. source of truth 원칙
동일한 사실을 여러 문서에 중복 확정하지 않는다.
- 기능의 현재 동작: `FUNCTION.md`
- 작업 진행 상태: `TASK.md`
- 최근 진행 요약: `REPORT.md`
- 변경 기록: `MODIFY.md`
- 판단 근거: `REVIEW.md`
- 의사결정: `DECISIONS.md`
- 프로젝트 전체 현황: `STATUS.md`

## 6. 기능 간 의존성 맵
| 기능 ID | 의존 대상 | 의존 유형 | 비고 |
|---------|----------|----------|------|
| feature-0003-agent-web-ui | feature-0002-agent-core | uses | Web UI가 코어 모듈을 import |
| feature-0003-agent-web-ui | feature-0006-lan-proxy-access | uses | TASK-0073: `_get_client_ip` X-Forwarded-For trust 가 Caddy `trust_forwarded_for` / `trusted_proxies` 설정에 의존 (SECURITY.md §9.7) |
| feature-0004-browser-automation | feature-0001-platform-runtime | uses | 운영 런타임과 함께 구동 |
| feature-0005-qa-mcp | feature-0001-platform-runtime | uses | Compose와 환경값 공유 |
| feature-0005-qa-mcp | feature-0002-agent-core | uses | 에이전트/MCP 모드 검증 |
| feature-0005-qa-mcp | feature-0004-browser-automation | uses | 브라우저 제어 smoke 검증 |
| feature-0006-lan-proxy-access | feature-0001-platform-runtime | uses | Web/TLS 운영 자산 공유 |
| feature-0007-bedrock-llm-provider | feature-0002-agent-core, feature-0003-agent-web-ui | uses | LLM 호출 단일 진입점 통합 |
| feature-0009-group-conversation | feature-0003-agent-web-ui, feature-0002-agent-core | uses | Web UI(공유·첨부·avatar) + ask_jobs 큐(`@assistant`) 위에 그룹 대화 |
| feature-0010-google-drive-integration | feature-0003-agent-web-ui, feature-0002-agent-core | uses | 인증/라우트/DDL 은 web app.py 인라인(물리 위치), 토큰 암호화는 `modules/cred_crypto`+`datasources`(DEK). 활성화 cycle 에서 `modules/mcp_client` seam(A) 배선 예정 |
| feature-0011-shared-extraction | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 두 feature 가 공유하는 저결합 공통 모듈을 repo 루트 `shared/` 로 추출하고 import 사이트 재배선 (모듈 alias shim 으로 비파괴). 추출 후 양 feature 가 `shared.*` 를 import |
| feature-0012-web-router-modularization | feature-0003-agent-web-ui | uses | app.py 도메인별 APIRouter 분할 — route 핸들러 전량 추출 완료(21 도메인 라우터, behavior-neutral) |
| feature-0013-relationship-diagrams | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 발화 가이던스·관계 저장소·insight introspection·대화 JOIN 학습은 feature-0002, mermaid 웹 렌더는 feature-0003 (cross-cut) |
| feature-0014-zero-downtime-deploy | feature-0003-agent-web-ui, feature-0006-lan-proxy-access | uses | 무중단 롤링은 web app.py `/livez`·`/readyz`·SSE 카운터(0003)와 Caddy 2-upstream LB·active health·:443 단일화(0006) 위에 동작 (cross-cut 코드 거주) |
| feature-0015-zd-hygiene-backup | feature-0002-agent-core | uses | insight-worker SIGTERM graceful 핸들러가 feature-0002 `modules/insight.py` 에 거주 (MySQL DDL 린트·백업 스크립트는 repo-level `bin/`) |
| feature-0016-metadata-graph | feature-0002-agent-core, feature-0003-agent-web-ui, feature-0013-relationship-diagrams, feature-0014-zero-downtime-deploy | uses | 동기화·투영 모듈/`graph_navigate` tool/insight FK introspection 은 feature-0002, 관리콘솔 그래프 뷰는 feature-0003 (cross-cut). `table_relationships` 저장소·FK introspection·대화 JOIN 학습은 feature-0013 재사용(엣지 투영 입력). 커스텀 AGE PG 이미지 cutover 는 feature-0014 무중단 배포 파이프라인과 정합(replica shared_preload·롤백 경로) |
| feature-0016-zd-pg-pause-caddy | feature-0002-agent-core, feature-0006-lan-proxy-access | uses | pg-restart 가 feature-0002 KB Postgres/pgbouncer(transaction-mode·ADMIN_USERS) 경로에, reconcile_caddy 가 feature-0006 Caddyfile 에 의존 (cross-cut) |
| feature-0017-deploy-build-gate | feature-0014-zero-downtime-deploy | extends | feature-0014 배포 스파인 `bin/deploy-web.sh` 의 build_image 게이트를 이미지 정합 검증으로 보강 (snap-docker metadata-race false-failure 수정) |
| feature-0020-zd-deploy-all | feature-0014-zero-downtime-deploy, feature-0015-zd-hygiene-backup, feature-0002-agent-core, feature-0007-bedrock-llm-provider | extends | feature-0014 배포 스파인을 워커·gateway·caddy 이미지로 확장. 워커 graceful(0015 `_INSIGHT_SHUTDOWN`/ask `_SHUTDOWN`+lease requeue)을 전제로 배포 자동화만 추가, agent 이미지(0002 Dockerfile)·litellm gateway(0007 compose/config) 재사용 |

### 의존 유형 정의
- `requires`: 대상 기능이 완성되어야 구현 가능
- `uses`: 대상 기능의 API/인터페이스를 사용하지만 독립 개발 가능
- `extends`: 대상 기능을 확장하는 관계

## 7. KB Postgres 성능 최적화 레이어 (2026-05-28)

T1~T5 로드맵 완수 후의 Postgres 데이터 경로 구성.

### 7.1 쿼리 최적화 (T1)
- `_load_top_facts_pg()`: NOT EXISTS O(N²) → `DISTINCT ON` + covering index (`ix_fact_entries_conv_scope_key_rank`)
- `_build_knowledge_payload()`: N+1 루프 → `ANY(array)` 단일 쿼리 (local+global 통합)

### 7.2 스키마 최적화 (T2)
- `agent_memory_facts`: regular VIEW → **MATERIALIZED VIEW** (CONCURRENTLY refresh 지원)
- `category_join_hints_json`: TEXT → **JSONB** + GIN index
- `texts.embedding`: partial ivfflat index (WHERE embedding IS NOT NULL)

### 7.3 인프라 최적화 (T3)
- PgBouncer transaction-mode sidecar (`edoburu/pgbouncer`, `pgbouncer:5432`)
- PostgreSQL 서버 파라미터 전면 조정 (shared_buffers, WAL, checkpoint 등)
- `pg_stat_statements` + `kb_slow_queries` view + autovacuum scale_factor=0

### 7.4 Lock / 캐시 최적화 (T4)
- Advisory lock: MySQL GET_LOCK → `pg_try_advisory_lock(hashtext(name))`
- 캐시 무효화: TTL 폴링 → `kb_invalidations` 테이블 + `pg_notify` groundwork
- `_is_refresh_due()` PG 무효화 플래그 연동

### 7.5 Replica 분리 (T5)
- `postgres-replica` streaming replica 서비스 (profile: replica)
- `AGENT_KB_PG_HOST_RO` / `AGENT_KB_PG_PORT_RO` 환경변수로 read-only 라우팅

### 7.6 KB 모듈 레이어 구조 (TASK-0142, 2026-06-02)
이전 단일 `modules/knowledge.py` (약 3376줄 god-module) 를 책임별 3개 모듈로 분할했다.
순수 구조 리팩터 — 함수 본문 로직 무변경.

| 모듈 | 책임 |
|---|---|
| `modules/kb_scope.py` | scope SQL clause (`_scope_filter_sql`, STRICT/INCL_NULL), PII 마스킹, 에러 분류, 요청 유사도, advisory lock(MySQL/PG), schema/search cache key, refresh 무효화 |
| `modules/kb_retrieval.py` | RAG document/object 검색(`_load_rag_documents_for_request*`/`_load_rag_objects_for_request*`), 쿼리 임베딩(벡터)·trigram 읽기, fact 텍스트 로딩(`_load_fact_text`/`_trim_fact_text`), insight 존재 로더(`_load_existing_schema_insights`/`_load_existing_table_insight_map`) (TASK-0150: planner 경로 전용이던 `_build_knowledge_payload`·`_load_top_facts*`·prompt 선택/retrieval-depth/schema-meta cache helper 죽은 subtree 제거) |
| `modules/kb_write.py` | fact/rag upsert(`_upsert_fact`), dual-write 미러, global publish, KB entry 영속화, step-trace (TASK-0150: 죽은 `_plan_zero_result_diagnostic` 제거) |

- 의존 방향은 단방향: `kb_scope`(leaf) ← `kb_retrieval` ← `kb_write`. 순환 없음.
- `modules/knowledge.py` 는 **얇은 facade** 로 남아 세 모듈의 모든 top-level 심볼(public
  `__all__` + private `_helper`) 을 re-export 한다. 기존 `from modules.knowledge import X`
  / `knowledge.X` 소비처(agent_core·insight·schema·render·sql_ops·domain·utils·db·llm·
  kb_backend·tests) blast-radius 0. public `__all__` 73개 심볼 그대로 보존.
- cross-module 이름은 `modules/__init__.py` 의 주입 메커니즘으로 런타임 해석된다(기존과 동일).
  facade 는 추가로 세 모듈 함수의 `__globals__` 를 단일 facade 네임스페이스로 재바인딩해,
  분할 전처럼 `monkeypatch.setattr(knowledge, "_helper", ...)` 가 호출 함수 내부 조회까지
  전파되는 test seam 을 보존한다(코드 객체 자체는 불변).

### 7.7 KB 검색 파이프라인 (벡터 + trigram, 활성)
`AGENT_KB_READ_BACKEND=postgres` 시 read 경로는 다음 순서로 동작한다. (read-only 는
`agent_kb_ro` least-privilege role `_pg_connect_ro()` 사용 — RW role bypass 금지.)

- **rag_documents** (`_load_rag_documents_for_request` → `_load_rag_documents_for_request_pg`):
  1. `_embed_query_vector()` 로 쿼리 임베딩(`AGENT_KB_EMBEDDING_MODEL=titan-embed`, Bedrock
     gateway). 성공 시 `PgKbBackend.search_rag_documents_vector()` (pgvector, 한국어 의미검색).
  2. 임베딩 미설정/실패 또는 벡터 결과 없음(미임베딩 row) → `search_rag_documents()`
     **pg_trgm trigram similarity** fallback.
- **rag_objects** (`_load_rag_objects_for_request` → `_load_rag_objects_for_request_pg`):
  `PgKbBackend.search_rag_objects()` 로 D0–D3 스키마/객체 routing 근거 제공.
- **fail-soft fallback (라이브 경로)**: 위 PG 경로가 예외/PG 미가용 시, 동일 함수가
  `conn` 기반 MySQL-dialect SQL 로 fallthrough 한다. cutover 미완 구간의 안전망으로
  **여전히 도달 가능** — 따라서 dead code 가 아니다 (TASK-0142 에서 보존). 이미 사장된
  MySQL 전용 분기는 선행 TASK-0127/0135 에서 제거 완료.

## 8. 통합 테스트 정책
- 현재 단계에서는 구조/기동 검증 위주로 운영한다.
- 엄격한 도메인 시나리오는 기능별 `docs/TEST.md`를 정본으로 후속 작성한다.
- 통합 테스트 자동화가 생기면 `../tests/integration/`로 승격한다.

## 8. 확장 원칙
- 기능 간 공통성이 반복되면 공통 모듈로 승격을 검토한다.
- 구조 변경이 필요한 경우 프로젝트 수준 `DECISIONS.md`에 남긴다.

## 9. artifacts 조직 규칙
`/artifacts/`는 재생성 가능한 파생 결과물을 저장한다.

### 9.1 디렉토리 구조
```
artifacts/
├── build/              # 빌드 산출물
├── reports/            # 생성된 보고서
├── exports/            # 내보내기 파일
├── tmp/                # 임시 파일
└── <feature-id>/       # 기능별 산출물 (검증 결과, 로그 등)
    └── <timestamp>/    # 실행 시점별 격리
```

### 9.2 규칙
- artifacts는 git 추적 대상이 아니다 (repo 외부에 위치).
- 기능별 산출물은 `<feature-id>/` 하위에 타임스탬프 디렉토리로 격리한다.
- 빌드/테스트 산출물은 재생성 가능해야 하며, source of truth가 아니다.
- 공유 런타임 데이터(로그, 세션 등)는 `artifacts/shared/`에 둔다.
- `.gitkeep` 파일로 디렉토리 구조를 유지한다.
