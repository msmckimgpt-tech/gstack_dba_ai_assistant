---
doc_type: WIKI_ARTICLE
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki]
ai_read_priority: 7
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../../docs/ARCHITECTURE.md
  - ../../docs/PROJECT.md
  - ../../docs/CODEBASE_MAP.md
---

# Architecture — Overview

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/article` |
| 정본 | [[../../docs/ARCHITECTURE\|docs/ARCHITECTURE.md]] |
| Wiki layer | mirror (graph 입구) |
| Feature 수 | 34 카드 (feature-0001 ~ feature-0034; feature-0016 은 metadata-graph + zd-pg-pause-caddy 2 슬라이스, feature-0018 은 카드 없는 슬라이스로 feature-0003 코드 거주) |

## 목차

1. [개요](#1-개요)
2. [상세](#2-상세)
     - [2.1 책임 분리 (정본 §2)](#21-책임-분리-정본-2)
     - [2.2 기능 단위 구조 (정본 §3)](#22-기능-단위-구조-정본-3)
     - [2.3 현재 기능 맵 (정본 §4)](#23-현재-기능-맵-정본-4)
     - [2.4 기능 간 의존성 (정본 §6)](#24-기능-간-의존성-정본-6)
3. [특징](#3-특징)
4. [관련 문서](#4-관련-문서)
5. [둘러보기](#5-둘러보기)
6. [외부 link](#6-외부-link)
- [분류](#분류)

## 1. 개요

저장소는 **공통 정책 영역 / 기능 영역 / 공통 코드 영역 / 산출물 영역** 4 layer 로 분리되어, 기능별 소유권을 명확히 하면서도 단일 docker-compose 로 실행 가능하다. 정본은 [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] §1 — 본 노트는 그 mirror.

## 2. 상세

### 2.1 책임 분리 (정본 §2)

| Layer | 위치 | 책임 |
|---|---|---|
| 공통 정책 | `AGENTS.md`, `docs/*.md` | 프로젝트 전반 규칙·제약·용어·보안 기준 |
| 기능 영역 | `unit/<feature-id>/{src,tests,docs}/` | 기능별 코드·테스트·명세·이력·리뷰·보고 |
| 공통 코드 | `shared/` | 여러 기능에서 공통 사용하는 코드 (필요 시) |
| 산출물 | `../../artifacts/*` (repo 외부) | 빌드 결과, 로그, MySQL 데이터, 세션, 인증서 |

### 2.2 기능 단위 구조 (정본 §3)

각 feature 는 다음 sub-tree 를 갖는다:

```
unit/feature-NNNN-<purpose>/
├── src/      # 기능 구현
├── tests/    # 기능 테스트
└── docs/     # FUNCTION/TASK/REPORT/MODIFY/REVIEW/ANCHOR/...
```

### 2.3 현재 기능 맵 (정본 §4)

| Feature ID | 책임 |
|---|---|
| [[../Features/feature-0001-platform-runtime\|feature-0001-platform-runtime]] | MySQL/DAB 설정 + replica 연결 |
| [[../Features/feature-0002-agent-core\|feature-0002-agent-core]] | agent CLI / core / KB Postgres |
| [[../Features/feature-0003-agent-web-ui\|feature-0003-agent-web-ui]] | FastAPI Web UI + audit subsystem |
| [[../Features/feature-0004-browser-automation\|feature-0004-browser-automation]] | Playwright browser service |
| [[../Features/feature-0005-qa-mcp\|feature-0005-qa-mcp]] | MCP / QA scripts |
| [[../Features/feature-0006-lan-proxy-access\|feature-0006-lan-proxy-access]] | Caddy TLS + Windows LAN proxy |
| [[../Features/feature-0007-bedrock-llm-provider\|feature-0007-bedrock-llm-provider]] | AWS Bedrock (Claude) gateway |
| [[../Features/feature-0008-windows-browser-testing\|feature-0008-windows-browser-testing]] | 실제 Windows 브라우저 AI 자동 검증 (PB-0008) |
| [[../Features/feature-0009-group-conversation\|feature-0009-group-conversation]] | 그룹 대화 — 멤버십 · `@assistant` 멘션 · 열람≠발화 분리 |
| [[../Features/feature-0010-google-drive-integration\|feature-0010-google-drive-integration]] | Google Drive 연동 토대 — 계정별 OAuth 암호화 + MCP seam (비활성) |
| [[../Features/feature-0011-shared-extraction\|feature-0011-shared-extraction]] | 공통 코드 `shared/` 점진 추출 (P5a — model_catalog·config·db alias) |
| [[../Features/feature-0012-web-router-modularization\|feature-0012-web-router-modularization]] | web `app.py` 도메인별 `APIRouter` 분할 (P5b — route 핸들러 전량 추출 완료: 148→21 도메인 라우터, byte-동치 behavior-neutral) |
| [[../Features/feature-0013-relationship-diagrams\|feature-0013-relationship-diagrams]] | flow/관계 질문에 mermaid 다이어그램 답변 + `table_relationships` 관계 저장소 (FK introspection·대화 JOIN 학습) |
| [[../Features/feature-0014-zero-downtime-deploy\|feature-0014-zero-downtime-deploy]] | web 무중단 롤링 배포 — Caddy LB(web-a/web-b) + `bin/deploy-web.sh`(자동 롤백) + `/livez`·`/readyz` + :18080 폐기 |
| [[../Features/feature-0015-zd-hygiene-backup\|feature-0015-zd-hygiene-backup]] | 백엔드/DB 무중단 위생 — insight-worker graceful + MySQL online-DDL 게이트 + 백업·복원 리허설 cron |
| [[../Features/feature-0016-metadata-graph\|feature-0016-metadata-graph]] | 메타데이터 지식그래프 — 관계형 SSOT→AGE `metadata_kb` 투영 + 관리콘솔 그래프 뷰 + `graph_navigate` AI 도구 (cutover 라이브 완료 · 07-01 WebGL·암묵 관계 추론·AI 능동 분석·권한 5분할) |
| [[../Features/feature-0016-zd-pg-pause-caddy\|feature-0016-zd-pg-pause-caddy]] | PG 재시작 무중단화 — pgbouncer PAUSE 래퍼 + deploy-web.sh Caddyfile reconcile |
| [[../Features/feature-0017-deploy-build-gate\|feature-0017-deploy-build-gate]] | 배포 스파인 빌드 게이트 false-failure 수정 (snap-docker metadata-race 이미지 정합 검증) |
| [[../Features/feature-0019-message-editing\|feature-0019-message-editing]] | 메시지 편집 — 1:1 대화 내부 브랜치 트리(단순/요청 분기 재답변 `< n/m >`) + 공유·그룹 단순 수정(@assistant 잠금) |
| [[../Features/feature-0020-zd-deploy-all\|feature-0020-zd-deploy-all]] | 무중단 배포 커버리지 — deploy 스파인 확장(워커 자동 롤아웃·bedrock-gateway surge 무중단 교체·caddy/alembic stale-image 가드) |
| [[../Features/feature-0021-redteam-review\|feature-0021-redteam-review]] | assistant 답변 자가 적대(red-team) 리뷰 — fresh-context 5축 검증 + [세션,제품] 메모리 노트 + 콘솔 'AI 추론' 탭 |
| [[../Features/feature-0022-agent-scratch-workspace\|feature-0022-agent-scratch-workspace]] | assistant PG 자율 작업공간 — 전용 DB `agent_scratch`(대화별 격리 스키마)에서 외부 데이터소스 반입·cross-source JOIN·TTL(기본 24h) 정리 (2026-07-21 라이브 활성·기본값 OFF 게이트 · 코드 거주 0002/shared) |
| [[../Features/feature-0023-conversation-api-access\|feature-0023-conversation-api-access]] | 외부 AI용 Conversation API — Bearer 토큰 인증(scope allowlist ∩ 계정권한·관리 네임스페이스 절대 denylist) + 대화 tool 화 MCP 서버(tool 4종) (2026-07-22 배포·라이브 e2e 통과·코드 거주 0003/0002) |
| [[../Features/feature-0024-conversation-folders\|feature-0024-conversation-folders]] | 대화 폴더(프로젝트 워크스페이스) — 재귀 폴더 조직·이동·삭제 후 대화 보관(승격)·폴더별 지침 ask-time 주입·런타임 max-depth·엄격 per-user 격리(`folder.*.own`, `folder.*.any` 폐지) (2026-07-23 라이브 완결·코드 거주 0002/0003) |
| [[../Features/feature-0025-worker-parallelism\|feature-0025-worker-parallelism]] | 워커 성능·병렬 처리 설정 — 백그라운드 워커(노드 분석·cluster_label)·사용자 답변·KB 임베딩의 병렬도·처리주기·배치크기를 관리 콘솔 '시스템>설정>성능·병렬 처리' 서브탭에서 조절 (feature-0018 runtime-settings 재사용·기본 동시성 1=byte-동치 opt-in·LLM만 병렬/DB직렬·`system.runtime.*` RBAC 재사용·clamp) |
| [[../Features/feature-0026-perf-observability\|feature-0026-perf-observability]] | 성능 관측 인프라 — web HTTP per-route 타이밍·요청당 DB 커넥션 카운터(`GET /api/admin/perf/http`·`console.aiops.read` 재사용)·워커 LLM latency 백필(13 sites)·답변 파이프라인 단계 계측(redteam/post-answer/grounding)·graph sync `duration_ms`·`bin/perf-snapshot.sh`·Caddy access log (측정 전용·사용자 가시 동작 변경 0·additive/fail-open·DB 스키마 0·in-progress 배포 잔여) |
| [[../Features/feature-0027-perf-latency-p0\|feature-0027-perf-latency-p0]] | P0 성능 개선 1차 (feature-0026 병목 지도 기반) — post-answer 큐레이션(topic/용어/ENUM LLM 3건) 답변 KV terminal 후 이동(체감 -25~35s·결과물·scope 귀속 불변)·grounding RO 연결 3→1·MySQL 버퍼풀 128MB→1G·Caddy gzip+immutable static (품질 영향 축=레드팀·thinking 불변·비파괴/가역·2026-07-28·코드 거주 0002/0001/0006) |
| [[../Features/feature-0028-web-perf\|feature-0028-web-perf]] | web 계층 성능 (feature-0026 지목 병목) — `/api/ask_result` long-poll 워커 스레드 이관(이벤트 루프 정지 제거)·스냅샷 PG 연결 4~5→1(단일 왕복 번들)·권한 카탈로그 TTL 캐시+세션 LastSeenAt throttle·web MySQL 풀 opt-in (응답 shape·인가 경계 불변·additive/가역 env 토글·2026-07-28·코드 거주 0003) |
| [[../Features/feature-0029-graph-churn\|feature-0029-graph-churn]] | 그래프 sync churn 근절 — 메타데이터 그래프 incremental sync 무의미 재투영 3종 제거: 값 무변경 시 `updated_at` 미전진(upsert·신호·트리거 alembic 0046·실측 churn 63%)·status 히스테리시스(trusted/broken 왕복 차단)·프로브 broken 부활 금지·공유 정점 중복 MERGE 제거(관계당 cypher 11→1~3) (그래프 신선도·자기교정 보존·가역·2026-07-28·코드 거주 0002) |
| [[../Features/feature-0030-ask-timeout-extension\|feature-0030-ask-timeout-extension]] | 실행 타임아웃 임박 시 사용자 확인 후 연장 — run 실행 예산의 80%(설정 가능) 도달 시 컴포저 비차단 배너(+백그라운드 브라우저 알림)로 확인하고, 승인한 그 run 한정으로 run 예산 컷 해제(개별 LLM 호출 상한 15분은 유지 — 중단·즉시답변·lease fencing 응답성 보존)·미승인 시 종전 타임아웃 동작·KV 시그널 5종은 cancel/finalize 패턴 미러링(run_id 짝 검증)·신규 권한 `conversation.extend.{own,any}`(own 만 finalize 보유 역할 1회 backfill)·콘솔 설정 3종(기본 ON·임계 80%·추가 허용 0=무제한) (위험도 Major·in-progress·2026-07-29 머지·배포 80cc7aeb + PB-0008 라이브 PASS·코드 거주 0002/0003/shared) |
| [[../Features/feature-0031-analysis-grounding\|feature-0031-analysis-grounding]] | 노드 분석 접지 — 운영 DB 에서 **통계만** 단계 수집(Stage 0 카탈로그=사용자 테이블 read 0 → Stage 3 정밀·Stage 0 카탈로그(사용자 테이블 read 0)~Stage 2 표준 표본까지 하루 최대 1단계 승격(주간은 Stage 1 상한)·Stage 3 정밀은 운영자 승인 knob 전용·`ds` 자원 예산 게이트 위 fail-soft·`COUNT(*)` 금지) → `metadata_table_stats`/`metadata_column_stats`(alembic 0050) → 노드 분석 payload `evidence` 블록 주입 + `NODE_ANALYSIS_PROMPT` '증거 우선' 개정(evidence 는 untrusted-data 대상) + `_analysis_is_thin` 길이→항목 충족도. 원시 컬럼값·문자열 min/max 미저장·미주입(`value_pattern` 6종 CHECK 로 DB 강제)·`semantic_cluster` 시그니처 미유입·LLM 호출 수 불변 (위험도 Major·2026-07-30 머지·in-progress 배포 검증 잔여·코드 거주 0002/shared) |
| [[../Features/feature-0032-llm-token-budget\|feature-0032-llm-token-budget]] | 백그라운드 LLM 토큰 예산 — `agent_runtime.llm_usage` 를 원천으로 rolling 24시간 백그라운드 토큰 소비를 집계(`shared/llm_budget.py`·60초 캐시·`ix_llm_usage_created`)하고 백그라운드 진입점 3곳(노드 분석 tick claim 전·클러스터 유지보수 pass·제품 분류 pass)에서 상한 초과 시 다음 주기로 미룸 + 콘솔 'AI 운영 현황' 예산 막대·attention 2단계(80% watch / 도달 degraded). `USER_FACING_TASKS`(agent·redteam·topic·classify·prompt_gen)는 집계·게이트 양쪽에서 제외(블랙리스트 = 새 백그라운드 작업이 자동으로 예산 안)·fail-open 3중(상한 0·조회 실패·모듈 부재)·게이트 커버리지 96%(정직 표기) (위험도 Major·2026-07-30 머지·in-progress·코드 거주 shared/0002/0003) |
| [[../Features/feature-0033-analysis-synthesis\|feature-0033-analysis-synthesis]] | 클러스터 합성 요약(L2) — 클러스터 확정 직후(병합·재정렬·라벨 확정·`_disambiguate_labels` 이후) 멤버셋으로 2~4문장 요약을 합성해 `cluster_summaries`(alembic 0051, PK `(scope_key, schema_name, member_set_hash)`)에 적재. 캐시 키 3중(`member_set_hash`+`l1_version`+`evidence_version`)이 증거·분석 변화의 유일한 전파 경로·정렬 후 해시(캐시 무한 미스 차단)·요약은 `build_table_signature_text` 미유입(재임베딩 순환 차단 불변식)·pass 당 40개·배치 6·배치마다 feature-0032 예산 재확인·20자 미만 미저장·요약 실패는 savepoint 격리로 클러스터링·라벨 역기록을 막지 않음·routine 클러스터 1차 제외 (위험도 Major·2026-07-30 머지·in-progress·코드 거주 0002/shared) |
| [[../Features/feature-0034-analysis-consumption\|feature-0034-analysis-consumption]] | 분석 산출물의 대화 소비 — `agent_core._build_knowledge_context`(답변 grounding 조립 choke-point)에 `TABLE GROUP SUMMARIES` 섹션 신설: `rag_objects` 에서 질문에 등장한 테이블 매칭(`strpos`·4자 미만 제외·행 상한 200) → 그 테이블들의 `(scope, effective_schema, label)` 로 `cluster_summaries` 조회 → 근거 수 병기해 1~2건 주입(매칭 0건이면 섹션·2단계 쿼리 생략). 라벨 조회로 `cluster_id` churn 회피·effective schema 유도로 MSSQL `dbo` 소실 보정·사전 계산분만(런타임 합성·LLM 호출 0)·`_datamark_untrusted`+"지시 아님" 헤더·statement_timeout 1.5s(세션 SET+RESET)·전 구간 fail-soft·`cluster_summary_ms` 계측 (위험도 Major(답변 경로)·2026-07-30 머지·in-progress·코드 거주 0002/shared) |

### 2.4 기능 간 의존성 (정본 §6)

| Feature | 의존 대상 | 유형 | 비고 |
|---|---|---|---|
| feature-0003 | feature-0002 | uses | Web UI → core import |
| feature-0003 | feature-0006 | uses | `_get_client_ip` 가 Caddy `trust_forwarded_for` 의존 |
| feature-0004 | feature-0001 | uses | 운영 런타임 공유 |
| feature-0005 | feature-0001, feature-0002, feature-0004 | uses | Compose + agent + browser smoke |
| feature-0006 | feature-0001 | uses | Web/TLS 운영 자산 공유 |
| feature-0007 | feature-0002, feature-0003 | uses | LLM 호출 단일 진입점 통합 |
| feature-0009 | feature-0003, feature-0002 | uses | Web UI(공유·첨부·avatar) + ask_jobs 큐(`@assistant`) 위 그룹 대화 |
| feature-0010 | feature-0003, feature-0002 | uses | 인증/라우트 app.py 인라인 + `cred_crypto` 토큰 암호화 |
| feature-0011 | feature-0002, feature-0003 | uses | 공통 모듈 `shared/` 추출 + import 재배선 (모듈 alias shim) |
| feature-0012 | feature-0003 | uses | `app.py` 도메인별 `APIRouter` 분할 — route 핸들러 전량 추출 완료(21 도메인 라우터, behavior-neutral) |
| feature-0013 | feature-0002, feature-0003 | uses | 발화 가이던스·관계 저장소·introspection·JOIN 학습은 feature-0002, mermaid 웹 렌더는 feature-0003 (cross-cut) |
| feature-0014 | feature-0003, feature-0006 | uses | 무중단 롤링 = web `/livez`·`/readyz`·SSE 카운터(0003) + Caddy LB·active health·:443 단일(0006) |
| feature-0015 | feature-0002 | uses | insight-worker graceful 핸들러가 feature-0002 `modules/insight.py` 거주 |
| feature-0016-metadata-graph | feature-0002, feature-0003, feature-0013, feature-0014 | uses | 동기화·투영·`graph_navigate`·introspection=0002, 그래프 뷰=0003, 관계 저장소=0013 재사용, AGE 이미지 cutover=0014 무중단 정합 |
| feature-0016-zd-pg-pause-caddy | feature-0002, feature-0006 | uses | pg-restart=0002 PG/pgbouncer, reconcile_caddy=0006 Caddyfile |
| feature-0017 | feature-0014 | extends | feature-0014 배포 스파인 build_image 게이트 보강 |
| feature-0019 | feature-0003, feature-0002 | uses | 메시지 편집 UI·엔드포인트=0003, 대화 내부 브랜치 트리·active-path recall=0002 |
| feature-0020 | feature-0014, feature-0002, feature-0007 | extends | deploy 스파인(0014) 확장 + 워커 이미지 핀(0002) + bedrock-gateway surge 교체(0007) |
| feature-0021 | feature-0002, feature-0003 | uses | red-team choke-point 훅·agent-notes·guidance_registry=0002, 관리 콘솔 'AI 추론' 콘솔=0003 |
| feature-0022 | feature-0002 | uses | scratch 코어·도구 4종·워커 TTL reaper=0002, bootstrap=repo-level `bin/scratch-pg-bootstrap.sh`, `shared/` 설정 공유 · governed 반입=`execute_sql` 신뢰경계 재사용 |
| feature-0023 | feature-0003, feature-0002, feature-0005 | uses | Bearer 토큰 인증 fallback·scope 교집합 게이트·`WebApiTokens` 스키마 = feature-0003(web_context/_bootstrap_schema), 대화 API(`/api/ask`) ask = feature-0002 agent_core, MCP 서버 패턴 = feature-0005 재사용; 발급 CLI(`bin/api-token-issue.sh`)는 repo-level·MCP 서버 코드는 feature-0023 unit |
| feature-0024 | feature-0002, feature-0003, feature-0009 | uses | 폴더 스토어(재귀 CTE)·CRUD/배정/이동/삭제/restore 라우터(`routers/folders.py`)·RBAC(`folder.*.own`)·사이드바 재귀 렌더·DnD/모달 = feature-0003, 폴더 지침 ask-time 주입(`compose_system_prompt`)·신규 테이블 alembic 0044(`agent_runtime`) = feature-0002, 대화 배정 2중 게이트(대화 read + 그룹멤버 + 폴더 소유)가 그룹 멤버십 재사용 = feature-0009; max-depth 런타임 설정 = `shared/runtime_settings`(feature-0018 슬라이스)·`shared/db` 공유 · cross-cut docs-only 코드 거주 0002/0003(feature-0019 선례) |
| feature-0025 | feature-0002, feature-0003 | uses | 워커 루프 동시성 배선·`performance` 그룹 소비(node_analysis/semantic_cluster/insight/ask)·runtime_settings 소비=feature-0002, admin '성능·병렬 처리' 서브탭(admin.html/admin.js)=feature-0003; runtime-settings 레지스트리/스냅샷/`system.runtime.*` RBAC = `shared/runtime_settings`(feature-0018 슬라이스) 재사용·`shared/db` 공유·인프라 여력(pgbouncer 40/200·PG 150)=docker-compose·병렬 대상 워크로드(그래프 노드 분석·cluster_label)=feature-0016 (cross-cut 코드 거주) |
| feature-0026 | feature-0002, feature-0003, feature-0006 | uses | 순수 ASGI 타이밍 미들웨어(`perf_metrics.py`)·`routers/admin_perf.py`(읽기전용·`console.aiops.read` 재사용·신규 권한 0)=feature-0003, 워커 LLM latency 백필(`llm.py` 13 sites)·답변 단계 타이머(`agent_core.py` redteam/post-answer/grounding)·graph sync `duration_ms`(`metadata_graph.py`)·insight cycle 카운터(`insight.py`)=feature-0002, edge access log(`Caddyfile`)=feature-0006; 요청-스코프 커넥션 카운터 `shared/perf_counters.py`+`shared/db` 계측·전 신호 집계 CLI `bin/perf-snapshot.sh`=repo-level (측정 전용·additive/fail-open·cross-cut 코드 거주) |
| feature-0027 | feature-0002, feature-0001, feature-0006, feature-0026 | uses | post-answer 큐레이션 시점 이동(터미널 후·datasource ContextVar 캡처/해제)·grounding 공유 RO 단일연결=feature-0002(`agent_core.py`·`modules/ask.py`), MySQL 버퍼풀 128MB→1G=feature-0001(server `.cnf`), Caddy gzip+immutable static=feature-0006(`Caddyfile`), 병목 지도·before/after 실측 수단(`bin/perf-snapshot.sh`)=feature-0026; 답변 결과물·품질 영향 축(레드팀·thinking) 불변·비파괴/가역 (성능 개선·cross-cut 코드 거주) |
| feature-0028 | feature-0003, feature-0002, feature-0026 | uses | ask_result long-poll 워커 스레드 이관·스냅샷 PG 단일연결 번들·권한 카탈로그 TTL 캐시+세션 touch throttle·web MySQL 풀 opt-in 전부 feature-0003(`routers/conversations.py`·`routers/_conv_store.py`·`web_context.py`·`routers/admin_products.py`·`app.py`), `ask_result` 폴링 대상 ask-worker 잡 결과 계약=feature-0002, `db_per_req` 병목 근거·전후 수단=feature-0026; 응답 shape·인가 경계 불변·additive/가역(env 토글) |
| feature-0029 | feature-0002, feature-0016, feature-0026 | uses | churn 감쇠(upsert `updated_at` 조건화·status 히스테리시스·allow_revive·정점 캐시)+alembic 0046 트리거=feature-0002(`modules/relationships.py`·`modules/metadata_graph.py`), 대상 메타데이터 그래프·자기교정 엔진 정본=feature-0016, sync `duration_ms` 계측=feature-0026 전후 측정; 그래프 신선도·자기교정 semantics 보존·가역 (cross-cut 코드 거주) |
| feature-0030 | feature-0002, feature-0003 | uses | 연장 KV 시그널 5종(`modules/memory.py` — cancel/finalize 패턴 미러링·run_id 엄격 짝 검증)·run 루프 임계 프롬프트 1회 발행 + 예산 초과 시점 grant 게이트·`_call_llm(timeout_override=)` 배선=feature-0002(`agent_core.py`), `POST /api/extend`(클라이언트 run_id 대조·fail-closed 409/403)·`/api/progress`·ask_status 스냅샷 `timeout_extension` 필드·`conversation.extend.{own,any}` 권한(own 한정 1회 backfill)·컴포저 인라인 배너+백그라운드 브라우저 알림=feature-0003(`routers/conversations.py`·`routers/_conv_store.py`·`app.py`·`static/app.js`); 콘솔 설정 3종은 `shared/runtime_settings.py`(feature-0018 런타임설정 슬라이스) 재사용. 연장은 run 시간 예산만 해제 — per-call 상한(15분)·`max_steps`·취소/즉시답변·lease fencing 불변, 외부 Conversation API(feature-0023) 경로는 확인 주체 부재로 종전 정책 (cross-cut 코드 거주) |
| feature-0031 | feature-0002, feature-0016, feature-0025 | uses | 통계 수집·승격 판정·형태 분류·적재·evidence 조립(`modules/metadata_stats.py` 신규)·Table 잡 처리 직전 수집 호출 + payload `evidence` 주입 + `_analysis_is_thin` 재정의(`modules/node_analysis.py`)·`NODE_ANALYSIS_PROMPT` 증거 우선 개정(`modules/llm.py`)·alembic 0050 `metadata_table_stats`/`metadata_column_stats`=feature-0002, 접지 대상인 그래프 메타데이터·노드 분석 정본=feature-0016, 운영 DB read 를 감싸는 `ds` 자원 예산 게이트 계약(ADR-0025-05~08)=feature-0025; 증거 수집 knob 4종(전부 live)·thin 기본값은 `shared/runtime_settings.py`·`shared/config.py` 공유. 원시 컬럼값·문자열 min/max 미저장·미주입·`semantic_cluster` 시그니처 미유입·LLM 호출 수 불변 (cross-cut 코드 거주) |
| feature-0032 | feature-0002, feature-0003 | uses | rolling 24h 집계·게이트·`snapshot()`=`shared/llm_budget.py`(신규)+상한 knob(`shared/config.py`·`runtime_settings.py`), 백그라운드 진입점 3곳 게이트(`node_analysis._process_pending_inner` claim 전 — claim 후 차단은 `attempts` 만 소모·`semantic_cluster.run_cluster_maintenance` 래퍼·`product_classify.run_classify_pass` 래퍼)=feature-0002, 콘솔 노출(`routers/ai_ops.py` 응답 + `static/admin.js` 막대·비율·면제 안내 렌더)=feature-0003; 계량 원천은 기존 `agent_runtime.llm_usage`(신규 계측 0)이고 provider·계정 체인 맥락은 feature-0007 정본 참조. 사용자 요청 경로는 집계·차단 양쪽에서 제외(설계 불변식)·fail-open 3중 (cross-cut 코드 거주) |
| feature-0033 | feature-0002, feature-0016, feature-0031, feature-0032 | uses | `CLUSTER_SUMMARY_PROMPT`+`llm_cluster_summary()`(`modules/llm.py`)·3중 캐시 키/결정적 정렬/savepoint/배치 생성 및 클러스터 확정 시점 배선(`modules/semantic_cluster.py`)·alembic 0051 `cluster_summaries`=feature-0002, 요약 대상인 의미 클러스터·라벨(`_disambiguate_labels`) 파이프라인 정본=feature-0016, `evidence_version` 원천인 L0 통계=feature-0031, 배치마다 재확인하는 백그라운드 토큰 상한=feature-0032; live 정지 스위치는 `shared/config.py`·`runtime_settings.py`. 요약은 클러스터링 시그니처에 유입되지 않으며(순환 차단 불변식) 요약 실패가 클러스터링·라벨 역기록을 막지 않는다 (cross-cut 코드 거주) |
| feature-0034 | feature-0002, feature-0033 | uses | 2단계 매칭·조회·렌더·스위치·fail-soft(`modules/cluster_context.py` 신규)와 `_build_knowledge_context` 의 `TABLE GROUP SUMMARIES` 주입 + `cluster_summary_ms` 계측(`agent_core.py`)=feature-0002, 주입 대상 요약의 생성과 `(scope_key, schema_name, member_set_hash)` 저장 계약=feature-0033; live 정지 스위치는 `shared/config.py`·`runtime_settings.py`. 사전 계산분만 사용(런타임 합성·LLM 호출 0)·라벨 조회로 `cluster_id` churn 회피 + 3중 격리·`_datamark_untrusted` 로 인젝션 차단·statement_timeout 1.5s·전 구간 fail-soft (답변 경로·cross-cut 코드 거주) |

의존 유형 어휘 (`requires` / `uses` / `extends`) 정본은 ARCHITECTURE.md §6.

## 3. 특징

- **source of truth 원칙** (정본 §5): 동일 사실을 여러 문서에 중복 확정하지 않는다. FUNCTION/TASK/REPORT/MODIFY/REVIEW/DECISIONS/STATUS 의 각 책임이 분리됨.
- **runtime artifacts 외부화**: 로그·세션·MySQL data 가 `../../artifacts/` 로 분리되어 git 추적 대상 아님.
- **AI 위임 친화**: AI 가 작업 시 `AGENTS.md` 우선 read + 각 feature 의 `docs/` 자동 참조.
- **멀티 데이터소스 (2026-06)**: data plane 이 단일 MySQL → N 개 데이터소스 (MySQL·MSSQL) 로 일반화. dialect 추상화 + envelope 암호화 registry + DB-단위 접근. 상세 [[Data-Flow]] §2.5 · [[../concepts/multi-datasource]].
- **storage 단일화 (2026-05-27)**: agent runtime + KB 모두 Postgres 단독 (`agent_kb`/`agent_runtime`). MySQL 은 `web*` 18 테이블만 (Phase 3 대상). [[../Decisions/ADR-0027-agent-runtime-pg-schema]] · [[../Decisions/ADR-0028-runtime-mysql-cleanup]].
- **그룹 대화 + 보안 보강 (2026-06-19~23)**: 단일 owner 대화 → 멤버십 기반(feature-0009, **열람 ≠ 발화** RBAC 분리). 사용자 보안 보강 6종(공유 만료·로그인 제한·감사 변조방지·LLM 한도·인젝션 방지·2FA) 완료. [[../Features/feature-0009-group-conversation]] · [[../../docs/SECURITY|SECURITY.md]].
- **NL→SQL 정확도 flywheel (2026-06)**: 평가 harness + 샘플쿼리 few-shot(pgvector) + self-reflection + 용어/ENUM 사전. [[../concepts/nl2sql-flywheel]].
- **메타데이터 거버넌스 + 토대 확장 (2026-06-24)**: ITEM-11 관리 콘솔 메타데이터 거버넌스(용어·ENUM·테이블/컬럼 설명·주입·AI 자동완성)로 NL→SQL 컨텍스트 강화. feature-0010 Google Drive 연동 토대(계정별 OAuth 암호화 + MCP seam, 비활성). feature-0011 공통 코드 `shared/` 점진 추출(P5a). [[../Features/feature-0011-shared-extraction]].
- **피드백 고유화 · 용어사전 자율등록 · router 분할 토대 (2026-06-29)**: 답변 피드백(👍/👎) 답변당 고유화(새로고침·전환 후 중복 차단). 관리 콘솔 용어사전 대화 자율등록(역할 분리·유사어·검토 큐 + 용어 검토 큐 IA 중첩). feature-0012 web `app.py` 도메인별 `APIRouter` 점진 분할 토대(P5b — route-parity 안전망 + 의존성 audit, behavior-neutral). [[../Features/feature-0012-web-router-modularization]].
- **관계 다이어그램 신규 · 메타데이터/공유 화면 정리 (2026-06-29)**: feature-0013 관계 다이어그램 — assistant 가 flow/관계 질문에 mermaid(ER·flowchart)로 답하고 `table_relationships` 관계 저장소(FK introspection·대화 JOIN 학습, alembic 0024)로 지속 학습(PB-0008 라이브 PASS). 메타데이터 스키마 골격 화면 접기·검색·페이지네이션·여백 압축, 공유 대화 뷰 mermaid 렌더·전체폭 반응형·스크롤 가이드, 용어사전 역할 선택 단일화. [[../Features/feature-0013-relationship-diagrams]].
- **무중단 배포·운영 위생 + 메타데이터 지식그래프 (2026-06-30)**: web 무중단 롤링 배포(Caddy LB web-a/web-b 2-replica·자동 롤백·:18080 폐기→:443 단일, feature-0014) + 백엔드/DB 위생(insight graceful·MySQL online-DDL·백업 복원 리허설, feature-0015) + PG 재시작 무중단화(pgbouncer PAUSE 래퍼, feature-0016-zd-pg-pause-caddy) + 배포 빌드게이트 false-failure 수정(feature-0017). 관리콘솔 메타데이터를 Apache AGE 지식그래프(관계형 SSOT→`metadata_kb` 투영)로 승급 + 그래프 뷰·`graph_navigate` AI 도구(feature-0016-metadata-graph, cutover 라이브 완료). [[../Features/feature-0016-metadata-graph]].
- **그래프 뷰 진화 + 라우터 모듈화 완료 (2026-07-01)**: feature-0016 메타데이터 그래프 뷰가 canvas→WebGL 렌더러 전환(프레임레이트 근본 대응)·암묵(FK 미선언) 관계 추론+자기교정 엔진(추정=점선/신뢰=실선, ADR-002)·AI 능동 분석 앵커-상대 관련도 게이팅+실시간 진행 패널·ERD 컬럼 ordinal·메타데이터 탭 권한 5분할(B안)로 대폭 성숙. feature-0012 web `app.py` 148 route 핸들러 전량을 21개 도메인 `APIRouter` 로 byte-동치 추출 완료(behavior-neutral, batch1-3 라이브 배포). [[../Features/feature-0016-metadata-graph]] · [[../Features/feature-0012-web-router-modularization]].

## 4. 관련 문서

- [[Data-Flow]] — 데이터 흐름 다이어그램
- [[Module-Map]] — 디렉토리 ↔ 책임 매핑
- [[../../docs/PROJECT|docs/PROJECT.md]]
- [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] (정본)

## 5. 둘러보기

- 상위: [[../Index|Index]] · [[../overview|overview]]
- sibling: [[Data-Flow]] · [[Module-Map]]
- 관련 ADR: [[../Decisions/ADR-0012-feature-unit-restructure]] · [[../Decisions/ADR-0013-shared-runtime-separation]] · [[../Decisions/ADR-0016-template-v3]]

## 6. 외부 link

- 없음 (모두 repo 안 정본)

## 분류

`#wiki/article` · `#confidence/high` · `#maturity/substantial`
