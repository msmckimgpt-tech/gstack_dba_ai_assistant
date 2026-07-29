---
doc_type: ARCHITECTURE
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.43.0
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
| feature-0019-message-editing | **메시지 편집 (2026-07-14, Major 신규)** — 사용자가 보낸 메시지 수정을 append-only 대화 모델(feature-0003 DESIGN-fork-reference §7) 위 **대화 내부 브랜치 트리**로 구현: 1:1 = 단순 수정('편집됨' 배지) / 요청사항 수정(편집 지점 새 브랜치 재답변 + `< n/m >` 버전 페이징), 그룹·공유 = 단순 수정만(`@assistant` 호출 메시지 편집 잠금). 본인 발신만 편집(IDOR 게이트)·공유 [from,to] window 합성 fail-closed·edit/branch.switch `WebAuditEvents` 감사, 비분기 대화 recall byte-identical(회귀 0). 마이그 0041 비파괴 additive(브랜치 컬럼). Phase 1+2 라이브·PB-0008. cross-cut 코드 거주 feature-0003(엔드포인트·프론트)·0002(마이그·schema·recall 로더·코어). |
| feature-0020-zd-deploy-all | **무중단 배포 커버리지 완성 (2026-07-14)** — feature-0014 스파인(`bin/deploy-web.sh`)을 전 배포 대상으로 확장: ① 워커(insight/ask) 자동 롤아웃(공용 agent 이미지 `mysql-ai-agent:<sha>` build-once 핀 + 순차 recreate + healthy/GIT_COMMIT 게이트 + agent last-good 자동 롤백 — 구 WARN-only divergence 대체) ② bedrock-gateway 드리프트(설정 sha 기록·bind inode-stale·이미지 ID) 시에만 **surge replica**(profile `deploy-surge`, DNS alias 합류)로 무중단 교체(steady-state 비용 0, stop_grace 120s drain) ③ caddy 이미지 태그 드리프트 recreate ④ `bin/alembic-migrate.sh` 직접 호출 stale-image 가드(upgrade/stamp 시 선행 재빌드) ⑤ 워커 healthcheck timeout 30s 견고화 + 라이브 적용 미커밋 compose 운영 튜닝 정식 커밋(live-truth). `make deploy-all`/`deploy-workers`/`ask-worker-*`. cross-cut 코드 거주 feature-0014(deploy-web.sh)·0002(agent Dockerfile 이미지)·0007(gateway compose). |
| feature-0021-redteam-review | **assistant 자가 적대(red-team) 리뷰 (2026-07-15, Major 신규)** — 답변을 사용자에게 전달하기 **전** choke-point(agent_core `result["answer"]` 확정 직후)에서 초안과 분리된 fresh-context 리뷰어(haiku, task=redteam 계측)가 grounding/SQL 정확성/권한·누출/완전성/정직성 5축으로 적대 리뷰 → BLOCK 결함만 ≤1회 수정 유발·높음+ 재검증·전 경로 fail-open(리뷰 실패가 답변 전달을 막지 않음). 추론 강도(낮음=skip/일반/높음/매우높음) 결정론적 게이팅. 보조: [세션,제품] 2계층 메모리 노트(`/shared/agent-notes`, 캡 8KB·TTL 7d/30d ask-worker reaper)+REDTEAM_* 런타임 설정+alembic 0042 `agent_runtime.redteam_reviews`(additive)+관리 콘솔 '감사>AI 추론' 탭(`console.reasoning.read`). Claude Code find→verify·auto-memory·progressive disclosure 이식. cross-cut 코드 거주 feature-0002(코어·워커·redteam/agent_notes/guidance_registry·choke-point 훅)·0003(관리 콘솔 admin_reasoning)·shared(runtime_settings). |
| feature-0022-agent-scratch-workspace | **assistant PG 자율 작업공간 (2026-07-21, Major 신규·기본 OFF)** — assistant 가 전용 PG DB `agent_scratch`(전용 role `agent_scratch_rw` NOSUPERUSER·CONNECT 격리·대화별 스키마 `s_<hash>`)에서 외부 데이터소스 데이터를 governed 반입(feature-0002 `execute_sql` 신뢰경계 재사용→materialize)해 cross-source JOIN·집계. 도구 4종(`scratch_import`/`scratch_sql`/`scratch_list`/`scratch_reset`, 활성 시에만 노출)·scratch_guard allowlist(root 명시 + CREATE/DROP=TABLE/INDEX kind 한정·함수/프로시저/뷰/DO/CALL/EXTENSION·`pg_` 접두 거부)·시간기반 TTL reaper(기본 24h, ask-worker 훅)·`AGENT_SCRATCH_*` 런타임 설정. 기본값 OFF 게이트이나 **2026-07-21 라이브 활성**(운영자 bootstrap + `AGENT_SCRATCH_ENABLED=1` + 스모크 PASS·run_sql 수정 반영; 잔여=cross-source JOIN e2e 실증·관측 UI·대화별 role 승격 TASK-0011~13). cross-cut 코드 거주 feature-0002(코어 `modules/scratch.py`·도구·워커)·shared(config·db·runtime_settings)·repo-level `bin/scratch-pg-bootstrap.sh`. feature-local ADR-SCRATCH-0001~0004. |
| feature-0023-conversation-api-access | **외부 AI용 Conversation API — Bearer 토큰 인증 경로 (2026-07-22, Critical 신규·사내 LAN 전제)** — 관리 콘솔을 제외한 "작업 화면 대화"(`/api/ask` 등 `conversation.*`)를 외부 AI 가 프로그램 구동하도록 세션 쿠키와 별개인 `Authorization: Bearer <token>` 인증 경로 신설(쿠키 부재 시에만 fallback·쿠키 우선 무회귀·fail-closed). 토큰은 저권한 서비스 계정 귀속·`WebApiTokens` SHA-256 해시 저장(scope·만료·revoke·LastUsedAt)·CLI 발급(`bin/api-token-issue.sh`, 콘솔 밖·audit). scope 강제는 `_account_permissions` 단일 choke-point 의 `scope ∩ 계정권한` 교집합 + **절대 denylist**(`*.any`·관리 네임스페이스 무조건 차단 → 관리 콘솔·교차계정 원천 봉인). MCP 서버(`src/conversation_mcp_server.py` + `bin/conversation-mcp.sh` gated)가 대화 tool 4종(`ask`/`new_conversation`/`list_conversations`/`get_history`) 래핑. 스키마 additive·비파괴. 적대 보안 리뷰(REV-20260722-0002) HIGH-1(scope-escape)·HIGH-2(fail-open) in-cycle 수정, 라이브 e2e PASS(토큰→200·admin 403·무토큰 401). SECURITY.md §25 정합. **(2026-07-24 발견 진입점)** 외부 AI 가 관용 위치에서 API 를 인지하도록 익명 static contract 4종(`llms.txt`·`/.well-known/ai-conversation-api.json`·`/api/ai/manifest`·`/api/ai/guide`) + 코드젠용 수기 OpenAPI(`/api/ai/openapi.json`, conversation-only) 제공, FastAPI 기본 `/openapi.json`·`/docs`·`/redoc` 익명 노출은 비활성(대체: admin-gated `/api/admin/openapi.json`). **(2026-07-28 대화 품질 조정 — conversation-quality-controls)** 외부 AI 가 답변 품질 5축(모델·추론 강도·제품 데이터소스 스코프·폴더 커스텀 지침·첨부)을 직접 조정: 인증 필수 **`GET /api/ai/capabilities`**(`routers/ai_discovery.py`, 신규 권한 코드 0 — 인증만; 모델·제품은 작업 화면 선택기와 **동일 필터 함수** 재사용해 표시-집행 정합, 폴더는 owner-scope 스토어, `conversation_id` 동봉은 대화 접근 게이트, 축별 독립 try 부분 degrade)가 계정별 라이브 값을 반환하고 익명 매니페스트에는 `quality_controls` **포인터만**(인스턴스 데이터 0 불변식 보존). 큐레이션 OpenAPI +6 path(`capabilities`·`PATCH …/product`·`/api/folders` GET/POST·`PATCH /api/folders/{id}`·`PATCH …/folder`·`POST …/attachments`)+3 스키마, 가이드 §4.7, MCP tool 4→11(품질 7 추가·stdlib multipart). 토큰 안전 기본 scope 에 `folder.` 확장(절대 denylist 무변경 — `.any`·관리 차단 유지, 기존 발급 토큰은 저장 scope 그대로라 무회귀). `/api/ask` body 계약 불변(제품 힌트는 신규 대화 한정 — TASK-0047 race 가드 보존, 기존 대화는 PATCH 단독 진실). SECURITY.md §25.1 정합. cross-cut 코드 거주 feature-0003(`web_context.py` 인증·scope·`routers/_bootstrap_schema.py` WebApiTokens·audit·`routers/ai_discovery.py` 발견·capabilities)·0002(`/api/ask`→`run_agent`)·0005(MCP 패턴)·0024(폴더 지침 주입 대상), 발급 CLI·MCP launcher 는 repo-level `bin/`. |
| feature-0024-conversation-folders | **대화 폴더 — 프로젝트 워크스페이스 (2026-07-23, Major 일부 Critical 신규)** — 작업 화면 대화를 사이드바 재귀 폴더(프로젝트 워크스페이스)로 조직·이동, 폴더 삭제 시 하위 대화/서브폴더는 부모(또는 root)로 승격되어 대화 자체는 보관(Trash·undo·하드삭제 경로 없음), 폴더별 커스텀 지침을 발화 시 주입(`compose_system_prompt` 요청자 폴더 기준), 런타임 조절 max-depth(self/subtree 순환·깊이 상한). 신규 테이블 2(`conversation_folders`+`folder_conversation_map`, feature-0002 alembic 0044 expand-safe·GRANT)·RBAC `folder.list.own`/`folder.manage.own`(own only, `folder.*.any` 폐지). **엄격 per-user(owner-scope) 격리** — 크로스-계정 폴더 노출 차단(Critical §12.3), `restore_folders` IDOR(HIGH, 교차계정 un-archive) 봉인. conversation.create 보유 7역할에 `folder.*.own` 동적 backfill(1회 마커·역할명 하드코딩 없이·admin DENY 존중). 4 슬라이스(conversation-folders·folder-privacy·folder-perms-broaden·folder-ux — 무프롬프트 생성·인라인 rename·설정/이동 모달·DnD). Phase 1+2a 라이브 완결(PR #895·POST-DEPLOY PB-0008 PASS)·Phase 2b(폴더 파일·datasource/product 자동스코프) 이연. SECURITY.md §26 정합. cross-cut 코드 거주 feature-0003(사이드바 재귀 렌더·폴더 라우터/스토어·`web_context.py` RBAC·프론트)·0002(`compose_system_prompt` 폴더 지침·alembic 0044)·0009(대화 배정 그룹멤버 게이트)·shared(`runtime_settings` max-depth·feature-0018 런타임설정 슬라이스). feature-local 결정 D1/D2/D4 (TASK.md §2.1)·REVIEW REV-20260723T060000. |
| feature-0025-worker-parallelism | **워커 성능·병렬 처리 런타임 설정 (2026-07-24, Major 신규)** — 백그라운드 워커(insight-worker 그래프 노드 분석·cluster_label, ask-worker 사용자 답변)·KB 임베딩의 병렬도·처리 주기·배치 크기를 관리 콘솔 `시스템 > 설정 > 성능·병렬 처리` 서브탭에서 조절(feature-0018 runtime-settings 인프라 재사용 — 레지스트리 + `/api/admin/settings/runtime` + `/shared` 스냅샷 전파, runtime_settings `performance` 그룹 10 knob). **모든 신규 동시성 기본값 = 1(현행 직렬과 byte-동치·opt-in)** — 운영자가 admin '성능·병렬' 서브탭에서 병렬도 상향 시에만 병렬화(LLM 만 스레드 병렬·DB I/O 단일 스레드, ask 는 전용 conn 스레드풀·`SKIP LOCKED`+lease fencing). 스펙 [min,max] clamp 로 위험값(pgbouncer 풀 소진·LLM 한도 초과) 주입 차단(node 8·cluster 4·ask 8 보수 상한 — 풀 소진→전역 장애 재발 방지 availability). 인프라 여력: pgbouncer DEFAULT_POOL_SIZE 20→40·MAX_CLIENT_CONN 100→200, PG max_connections 100→150(primary/replica 정합). 권한은 feature-0018 `system.runtime.read/write` 재사용(admin 전용·audit, 신규 authz 표면 0). 구현 완료·단위 48+회귀 166 PASS·2렌즈 적대 리뷰 SHIP(feature-local REVIEW REV-20260724T053235·MAJOR 2 in-cycle 수정), **배포 후 PB-0008 라이브 검증 잔여**(TASK-0012 — admin '성능·병렬' 서브탭 UI 육안 미검증). cross-cut 코드 거주 feature-0002(워커 루프 `modules/{node_analysis,semantic_cluster,insight,ask}.py`·runtime_settings 소비)·0003(admin '성능·병렬' 서브탭 `admin.html`/`admin.js`)·shared(`runtime_settings` 레지스트리)·docker-compose(인프라 여력), 병렬 대상 워크로드=feature-0016 그래프 노드 분석·cluster_label. feature-local ADR-0025-01~04. |
| feature-0026-perf-observability | **성능 관측 인프라 (2026-07-27, 측정 전용 신규·사용자 가시 동작 변경 0·in-progress)** — 라이브 전수 성능 조사(답변 1건 평균 141s = agent LLM 87.8s/62% + redteam 파이프라인 46.4s/33%)에서 확인된 계측 사각(HTTP per-route 축 전무·워커 LLM latency NULL·redteam/post-answer/grounding 분해 부재·요청당 DB conn 무관측)을 해소하는 additive·fail-open 계측 인프라. ① web HTTP per-route 지연(순수 ASGI `PerfTimingMiddleware`·버킷 히스토그램 p50/p95·slow ring·주기 로그 flush)+요청당 DB 커넥션 카운터(`shared/perf_counters.py` 요청-스코프 ContextVar, 컨텍스트 밖 no-op) 조회 API `GET /api/admin/perf/http`(`routers/admin_perf.py`, INCLUDE_ORDER=250, 기존 `console.aiops.read` 재사용·RO) ② 워커 LLM latency 백필 13 task(`modules/llm.py` `_record_llm_usage` perf_counter_ns 왕복) ③ 답변 파이프라인 단계 분해(`agent_core` `_build_knowledge_context`·redteam(`_rt_ms`)·post-answer(`_pa_ms`) `_ans_breakdown` additive 키) ④ graph-sync `duration_ms`(`modules/metadata_graph.py`)·insight cycle node_analysis/relationships_probe 카운터 ⑤ 전 신호 집계 CLI `bin/perf-snapshot.sh`→`artifacts/perf/<ts>/` ⑥ Caddy access log(stdout JSON). **전부 additive·fail-open — 동작 변경 0(측정값 기록만)·신규 권한/스키마/UI 표면 0**(§18.8 3렌즈 패널 backend/qa/security 흡수). 개선은 측정치 기반 후속 cycle. cross-cut 코드 거주 feature-0002(`llm`·`agent_core`·`insight`·`metadata_graph` 계측)·0003(`perf_metrics.py`·`routers/admin_perf.py`·app.py 미들웨어 등록)·0006(`Caddyfile` log)·shared(`perf_counters.py`·`db.py` `_pg_connect` incr)·repo-level `bin/perf-snapshot.sh`. |
| feature-0027-perf-latency-p0 | **P0 성능 개선 1차 (2026-07-28, feature-0026 측정 근거·품질 무영향 축만·in-progress)** — 라이브 답변 지연(평균 141s) 분석에서 도출한 비파괴·가역 최적화 4종. ① post-answer 큐레이션(topic/용어/ENUM LLM 3건)을 답변 확정(terminal) 후로 이연(worker 한정 — 실행 내용 불변·시점만 이동, in-process 는 종전 순서 유지, 체감 -25~35s) ② grounding(`_build_knowledge_context`) 공유 RO 단일 연결 ③ MySQL 버퍼풀 128MB→1G(`99-mysql-ai-server.cnf`, 라이브 SET GLOBAL 은 배포 단계) ④ Caddy encode(gzip, SSE 제외 allowlist)+immutable static(스탬프 쿼리 매처). 품질 영향 축은 범위 제외 — red-team 은 DECISIONS.md ADR-20260728T120000, thinking 예산은 feature-0027 스코핑(정본 TASK.md §2.1). 전부 가역(설정·순서 revert). cross-cut 코드 거주 feature-0002(`agent_core` post-answer 이연·grounding RO·`modules/ask.py`)·0001(MySQL cnf 버퍼풀)·0006(`Caddyfile` encode/immutable)·repo-level `bin/perf-snapshot.sh`. |
| feature-0028-web-perf | **web 계층 성능 (2026-07-28, feature-0026 측정 근거·응답 shape·인가 불변·in-progress)** — web 요청 핫패스 관통 최적화. ① `ask_result` long-poll 폴 루프를 `to_thread` 워커 스레드로 이관(이벤트 루프 stall 제거) ② 대화 스냅샷 PG 단일 연결 번들(호출당 4~5→1)+공유 헬퍼 추출 ③ 권한 카탈로그 TTL 캐시+세션 `LastSeenAt` touch throttle(인증 왕복 완화)+`admin_products` 무효화 훅 ④ web memory MySQL 풀 opt-in. 전부 additive·가역(env 토글) — 신규 경로 실패 시 종전 경로 폴백, 응답 shape·인가 경계 무변경. cross-cut 코드 거주 feature-0003(`routers/conversations.py`·`routers/_conv_store.py`·`web_context.py`·`routers/admin_products.py`·`app.py`)·0002(`ask_result` 가 폴링하는 ask-worker 잡 결과 계약)·0026(`db_per_req` 계측 전후 대조). |
| feature-0029-graph-churn | **그래프 sync churn 근절 (2026-07-28, feature-0026 측정 근거·그래프 신선도 손실 0·in-progress)** — 라이브 실측(2h 갱신의 63%가 값 무변경)에 근거한 그래프 동기화 쓰기 증폭 억제. ① 값 무변경 시 `updated_at` 미전진(upsert·신호·alembic 0046 트리거) ② status 히스테리시스(`_TRUST_EXIT`/`_BREAK_EXIT` — trusted/broken 왕복 차단) ③ 프로브 broken 부활 금지(`allow_revive` 게이트) ④ 공유 정점 중복 MERGE 제거(관계당 cypher 11→1~3·정점 캐시). 값이 안 변한 행은 그래프 상태도 불변 → 신선도 손실 없음, 마이그레이션은 downgrade 로 가역. cross-cut 코드 거주 feature-0002(`modules/relationships.py`·`modules/metadata_graph.py`·alembic 0046), 최적화 대상 그래프 sync 는 feature-0016. |
| feature-0030-ask-timeout-extension | **실행 타임아웃 임박 시 사용자 확인 후 그 run 한정 연장 (2026-07-29, Major 신규·in-progress)** — AI 작업자가 관리 콘솔 `시스템 > 설정 > 실행 타임아웃 > 에이전트/쿼리 실행 타임아웃`(`AGENT_TIMEOUT_SEC`)을 낮춰 둔 상태에서 사용자가 답변을 기다리면 run 예산(`AGENT_TIMEOUT_SEC × 3`) 초과로 '타임아웃으로 종료되었습니다.' 가 되어 그때까지의 추론 산출이 소실되던 마찰을 해소. 예산 소진 임계(기본 80%·콘솔 조절)에 도달하면 run 당 1회 확인 신호를 올리되 **루프는 대기 없이 계속 추론**하고(2026-07-09 ask-timeout-nonblocking 비차단 원칙 계승 — 화면 차단 모달 없음), 사용자가 컴포저 인라인 배너의 '계속 추론'을 누르면 **그 run 에 한해** 예산 컷을 넘겨 완주한다(미승인·기능 OFF 경로는 종전 동작 그대로·승인은 다음 요청에 전이 없음). ① 사용자↔워커 신호는 기존 cancel/finalize memory KV 패턴 미러링 5종(`timeout_ext_prompted`·`_run_id`·`_deadline_at`·`_granted`·`_granted_at`) + run_id 엄격 짝 검증(prompt 발행이 이전 run 의 승인 흔적을 리셋 — 교차 run 승인 오염 차단) ② **승인이 푸는 것은 run 전체 예산뿐**이고 per-call LLM 상한은 `_EXTENSION_PER_CALL_TIMEOUT_SEC=900`(15분)으로 유지 — 단일 호출을 무한정 열면 그 사이 '중단'·'즉시 답변'·`max_steps`·lease fencing 이 전부 무응답이 되어 연장의 대가로 탈출구를 잃는다(codex 적대 리뷰 P1-3, 이 값이 곧 '중단' 의 최대 응답 지연) ③ 신규 권한 `conversation.extend.own`/`conversation.extend.any` — `conversation.finalize.*` 보유 역할에 **`own` 만** 1회 backfill(`conversation-extend-perms-v1` 마커), `any` 는 관리자 명시 부여('중단' 과 '비용 유발 계속 실행' 은 위험 방향이 반대·P1-4) ④ 콘솔 설정 3종(`AGENT_TIMEOUT_EXTENSION_ENABLED`·`_PROMPT_PCT`·`_MAX_SEC` 기본 0=무제한, feature-0018 runtime-settings 인프라 재사용) ⑤ `POST /api/extend` 는 클라이언트 run_id 대조 불일치 409·기능 OFF 409·설정 조회 실패 503 fail-closed(워커 게이트와 대칭). 외부 Conversation API(feature-0023) 경로는 대화형 확인 주체가 없어 프롬프트 미발행 — 종전 타임아웃 정책 유지. 배포 `80cc7aeb` + PB-0008 라이브 PASS(설정 3종 노출·KV 프롬프트 발행·배너 노출·승인 시 서버 `granted=1`·backfill `own` 7역할/`any` 미부여·승인된 run 에 '중단' 2초 반영), 라이브 미재현 2항목(승인의 예산-컷-통과 인과·미승인 타임아웃 종료 메시지)은 사유와 단위 테스트 커버 지점을 정직 표기. **잔여 위험**: 프롬프트 발행이 루프 재진입에 의존해 임계 시점 발행이 보장되지 않는다(예산 초과 시점 재발행 + `_EXTENSION_GRACE_SEC=20` 유예가 최후 방어선 — 라이브에서 같은 임계 22s 발행 vs 82s 미발행 관측, codex P2-3 의도적 수용). AGENTS.md §12.3 Major(LLM 외부 비용 축 + 백엔드·웹·프론트 3계층·신규 권한 코드) → AGENTS.md §18.8 backend+security+qa 렌즈 대상이나 세션 Agent-tool 제약과 상충 → 사용자 확인(2026-07-29) 후 AGENTS.md §18.8.2 정합으로 `/codex review` 경로 채택. SECURITY.md §29 정합. cross-cut 코드 거주 feature-0002(`agent_core.run_agent` 예산 게이트·`_call_llm(timeout_override=)`·`modules/memory.py` KV 5종)·0003(`routers/conversations.py` `POST /api/extend`·`routers/_conv_store.py` 스냅샷 `timeout_extension`·`web_context.py` 권한 카탈로그/backfill·`static/app.js` 배너+브라우저 알림)·shared(`runtime_settings.py` `_TIMEOUT_SPECS`). feature-local **결정**(사용자 AskUserQuestion 2026-07-29 — 연장 상한 무제한·확인 UI 인라인 배너+브라우저 알림; 정본 TASK.md §2.1 PLAN-APPROVED·REPORT.md 2026-07-29 착수 항)·REVIEW REV-20260729-0001. |

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
| feature-0019-message-editing | feature-0003-agent-web-ui, feature-0002-agent-core | uses | 편집·브랜치 전환 엔드포인트·프론트 UI 는 feature-0003(`conversations.py`·프론트), 브랜치 마이그(0041)·`agent_runtime` schema·recall 로더(`_load_conversation_messages`) active-path 확장·쓰기 체이닝은 feature-0002(코어·runtime_backend). append-only 대화 모델(feature-0003 DESIGN-fork-reference §7) 위 브랜치 트리 도입 (cross-cut 코드 거주) |
| feature-0020-zd-deploy-all | feature-0014-zero-downtime-deploy, feature-0015-zd-hygiene-backup, feature-0002-agent-core, feature-0007-bedrock-llm-provider | extends | feature-0014 배포 스파인을 워커·gateway·caddy 이미지로 확장. 워커 graceful(0015 `_INSIGHT_SHUTDOWN`/ask `_SHUTDOWN`+lease requeue)을 전제로 배포 자동화만 추가, agent 이미지(0002 Dockerfile)·litellm gateway(0007 compose/config) 재사용 |
| feature-0021-redteam-review | feature-0002-agent-core, feature-0003-agent-web-ui | uses | red-team choke-point 훅(agent_core)·`modules/redteam.py`·`agent_notes.py`·`guidance_registry.py`(progressive disclosure)·REDTEAM_* 런타임 설정은 feature-0002(코어·워커), 관리 콘솔 '감사>AI 추론' 탭(`routers/admin_reasoning.py`)은 feature-0003. `shared/runtime_settings.py` 설정 레지스트리 공유 (cross-cut 코드 거주) |
| feature-0022-agent-scratch-workspace | feature-0002-agent-core | uses | scratch 코어(`modules/scratch.py`)·도구 4종·ask-worker TTL reaper 훅은 feature-0002, bootstrap(`bin/scratch-pg-bootstrap.sh`)은 repo-level, `shared/`(config·db·runtime_settings) 설정·PG 연결 공유. governed 반입은 feature-0002 `execute_sql` 신뢰경계 재사용 (cross-cut 코드 거주) |
| feature-0023-conversation-api-access | feature-0003-agent-web-ui, feature-0002-agent-core, feature-0005-qa-mcp | uses | Bearer 토큰 인증 경로(`_get_account_by_api_token`)·scope 교집합 choke-point(`_account_permissions` + 절대 denylist `_api_token_permission_denied`)·`WebApiTokens` 스키마(`_ensure_web_api_tokens_schema`)·audit 는 feature-0003(`web_context.py`·`routers/_bootstrap_schema.py`), `/api/ask` 가 호출하는 `run_agent` 는 feature-0002, MCP 서버 패턴(`.mcp.json`·`bin/*-mcp.sh`)은 feature-0005 재사용. 발급/폐기 CLI(`bin/api-token-issue.sh`)는 repo-level, MCP 서버(`src/conversation_mcp_server.py`)는 feature-local, `shared/`(config·db) 공유 (cross-cut 코드 거주) |
| feature-0024-conversation-folders | feature-0002-agent-core, feature-0003-agent-web-ui, feature-0009-group-conversation | uses | 폴더 스토어(재귀 CTE·depth cap·순환 방지)·CRUD/배정/이동/삭제/restore 라우터(`routers/folders.py`)·RBAC/audit(`web_context.py`)·사이드바 재귀 렌더·DnD/모달 프론트는 feature-0003, 폴더 지침 ask-time 주입(`compose_system_prompt` 요청자 폴더)·신규 테이블 alembic 0044(`agent_runtime` 스키마)는 feature-0002, 대화 배정 2중 게이트([대화 read own/any + 그룹멤버] + 폴더 소유)가 그룹 멤버십을 재사용하므로 feature-0009 `group_members`. `shared/`(`runtime_settings` max-depth·db) 공유 — max-depth 런타임 설정은 feature-0018 런타임설정 슬라이스(코드 거주 feature-0003/shared) (cross-cut 코드 거주) |
| feature-0025-worker-parallelism | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 워커 동시성·페이싱·배치 배선은 feature-0002(`modules/node_analysis.py` process_pending LLM 병렬·`modules/semantic_cluster.py` cluster_label 배치 병렬·`modules/insight.py` tick/interval·`modules/ask.py` N executor 스레드+전용 conn·runtime_settings 소비), 관리 콘솔 '성능·병렬 처리' 서브탭(`admin.html`/`admin.js`)은 feature-0003. runtime-settings 인프라(레지스트리+`/api/admin/settings/runtime`+`/shared` 스냅샷·`system.runtime.read/write` 게이트)는 feature-0018 재사용(코드 거주 feature-0003/shared), `shared/`(`runtime_settings.py` `performance` 그룹·db) 공유, 인프라 여력(pgbouncer 풀·PG max_connections)은 docker-compose. 병렬 대상 워크로드(그래프 노드 분석·cluster_label)는 feature-0016 (cross-cut 코드 거주) |
| feature-0026-perf-observability | feature-0002-agent-core, feature-0003-agent-web-ui, feature-0006-lan-proxy-access | uses | 워커 LLM latency 백필(`modules/llm.py` 13 task `_record_llm_usage`)·답변 파이프라인 단계 계측(`agent_core` redteam/post-answer/grounding `_ans_breakdown`)·graph-sync `duration_ms`(`modules/metadata_graph.py`)·insight cycle 카운터는 feature-0002, HTTP per-route 타이밍 미들웨어(`perf_metrics.py` 순수 ASGI)·조회 API(`routers/admin_perf.py` INCLUDE_ORDER=250·`console.aiops.read` 재사용)·app.py 미들웨어 등록·`_connect_memory` 카운터는 feature-0003, Caddy access log(stdout JSON)는 feature-0006. 요청-스코프 conn 카운터(`shared/perf_counters.py` ContextVar)·`shared/db.py` `_pg_connect`/`_pg_connect_ro` incr 은 `shared/` 공유, 전 신호 집계 CLI(`bin/perf-snapshot.sh`)는 repo-level. 전부 additive·fail-open 계측(동작 변경 0·신규 권한/스키마/UI 표면 0) (cross-cut 코드 거주) |
| feature-0027-perf-latency-p0 | feature-0002-agent-core, feature-0001-platform-runtime, feature-0006-lan-proxy-access, feature-0026-perf-observability | uses | post-answer 큐레이션 이연(worker=job terminal 후)·grounding 공유 RO conn·`_build_knowledge_context` 는 feature-0002(`agent_core`·`modules/ask.py`), MySQL 버퍼풀 128MB→1G(`99-mysql-ai-server.cnf`)는 feature-0001, Caddy encode(gzip)+immutable static(`Caddyfile`)은 feature-0006, 측정 근거·`bin/perf-snapshot.sh` 캡션은 feature-0026 재사용. 품질 영향 축 범위 제외 — red-team 은 DECISIONS.md ADR-20260728T120000·thinking 은 feature-0027 스코핑. 전부 가역·품질 무영향 (cross-cut 코드 거주) |
| feature-0028-web-perf | feature-0003-agent-web-ui, feature-0002-agent-core, feature-0026-perf-observability | uses | `ask_result` long-poll `to_thread` 이관·대화 스냅샷 PG 단일연결 번들·권한 카탈로그 TTL 캐시+세션 `LastSeenAt` throttle·web MySQL 풀 opt-in 은 feature-0003(`routers/conversations.py`·`routers/_conv_store.py`·`web_context.py`·`routers/admin_products.py`·`app.py`), `ask_result` 가 폴링하는 ask-worker 잡 결과 계약은 feature-0002, `db_per_req` 계측(전후 대조)은 feature-0026 재사용. 응답 shape·인가 경계 무변경·전부 additive·가역(env 토글) (cross-cut 코드 거주) |
| feature-0029-graph-churn | feature-0002-agent-core, feature-0016-metadata-graph, feature-0026-perf-observability | uses | `updated_at` 조건화 upsert·status 히스테리시스(`_TRUST_EXIT`/`_BREAK_EXIT`)·프로브 broken 부활 금지·공유 정점 중복 MERGE 제거·정점 캐시는 feature-0002(`modules/relationships.py`·`modules/metadata_graph.py`·alembic 0046 트리거)에 거주, 최적화 대상 그래프 sync 투영은 feature-0016, churn 전후(cron.log relationships/`duration_ms`)는 feature-0026 재사용. 그래프 신선도 손실 없음(값 무변경 행만 억제)·마이그레이션 가역(downgrade) (cross-cut 코드 거주) |
| feature-0030-ask-timeout-extension | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 임계(기본 80%) 프롬프트 run 당 1회 발행·예산 초과 시점 grant 게이트·per-call 상한 유지(`_EXTENSION_PER_CALL_TIMEOUT_SEC=900`)·`_EXTENSION_GRACE_SEC=20` 유예·연장 KV 시그널 5종(cancel/finalize 패턴 미러링·run_id 엄격 짝 검증)은 feature-0002(`agent_core.run_agent`·`_call_llm(timeout_override=)`·`modules/memory.py`), 승인 엔드포인트 `POST /api/extend`(클라이언트 run_id 대조·409/503 fail-closed)·`ask_status`/`ask_result` 스냅샷 `timeout_extension` 필드·`conversation.extend.own`/`.any` 권한 카탈로그 + `own` 한정 1회 backfill·컴포저 인라인 배너 + 백그라운드 브라우저 알림은 feature-0003(`routers/conversations.py`·`routers/_conv_store.py`·`web_context.py`·`static/app.js`). 콘솔 설정 3종(`AGENT_TIMEOUT_EXTENSION_ENABLED`/`_PROMPT_PCT`/`_MAX_SEC`)은 `shared/runtime_settings.py` `_TIMEOUT_SPECS` 공유 — 레지스트리·`/api/admin/settings/runtime`·`system.runtime.read/write` 게이트는 feature-0018 런타임설정 슬라이스 재사용(코드 거주 feature-0003/shared). 연장이 함께 풀어야 하는 per-attempt body timeout·httpx 총-대기 2층은 feature-0007 timeout-console-sync 계약(정본 로직은 feature-0002 `_call_llm` 거주). 외부 Conversation API(feature-0023) 경로는 확인 주체 부재로 프롬프트 미발행 — 종전 타임아웃 정책 유지 (cross-cut 코드 거주) |

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
