---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki]
ai_read_priority: 7
wiki_role: index
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../../docs/ARCHITECTURE.md
  - ../../docs/STATUS.md
---

# Features — MOC

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/index` |
| 정본 영역 | `unit/feature-NNNN-<purpose>/docs/FUNCTION.md` |
| Feature 수 | 41 active |
| Wiki layer | mirror (입구점) |

## 목차

1. [개요](#1-개요)
2. [Active features](#2-active-features)
3. [Archived / completed](#3-archived--completed)
4. [Skeleton](#4-skeleton)
5. [관련 문서](#5-관련-문서)
6. [둘러보기](#6-둘러보기)
7. [외부 link](#7-외부-link)
- [분류](#분류)

## 1. 개요

41 개 feature 카드(feature-0016 은 metadata-graph + zd-pg-pause-caddy 2 슬라이스, feature-0018 은 카드 없는 슬라이스로 feature-0003 코드 거주)의 *사람용 카드* 입구. 정본은 `unit/<id>/docs/FUNCTION.md`. AI 가 새 feature 를 생성할 때마다 본 MOC 에 1줄 entry 추가 + `Features/<feature-slug>.md` 동반 (`AGENTS.md §21` 의무).

## 2. Active features

| Feature | 상태 | 책임 한 줄 | 카드 | 정본 |
|---|---|---|---|---|
| feature-0001-platform-runtime | active | MySQL/DAB · replica 연결 · redo log 1 GiB | [[feature-0001-platform-runtime]] | `unit/feature-0001-platform-runtime/docs/FUNCTION.md` |
| feature-0002-agent-core | active | agent core · 멀티 데이터소스(MySQL·MSSQL) · KB Postgres · insight worker | [[feature-0002-agent-core]] | `unit/feature-0002-agent-core/docs/FUNCTION.md` |
| feature-0003-agent-web-ui | active | FastAPI Web UI · 관리콘솔(데이터소스·대시보드·LLM 사용량 차트 지표 선택기) · audit · 첨부(버전 diff·원문 보기·이름순 정렬·공유 대화 스코프) · 그룹 대화 멤버 권한 게이트 · ask-worker | [[feature-0003-agent-web-ui]] | `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` |
| feature-0004-browser-automation | active | Playwright HTTP 제어 service | [[feature-0004-browser-automation]] | `unit/feature-0004-browser-automation/docs/FUNCTION.md` |
| feature-0005-qa-mcp | active | MCP 연결 검증 · QA 보조 | [[feature-0005-qa-mcp]] | `unit/feature-0005-qa-mcp/docs/FUNCTION.md` |
| feature-0006-lan-proxy-access | active | Caddy TLS · Windows LAN proxy · XFF trust | [[feature-0006-lan-proxy-access]] | `unit/feature-0006-lan-proxy-access/docs/FUNCTION.md` |
| feature-0007-bedrock-llm-provider | active | AWS Bedrock (Claude) gateway · API Vault 폐기 | [[feature-0007-bedrock-llm-provider]] | `unit/feature-0007-bedrock-llm-provider/docs/FUNCTION.md` |
| feature-0008-windows-browser-testing | active | 실제 Windows 브라우저 AI 자동 검증 (PB-0008 · ADR-0029) | [[feature-0008-windows-browser-testing]] | `unit/feature-0008-windows-browser-testing/docs/FUNCTION.md` |
| feature-0009-group-conversation | active | 그룹 대화 — 멤버십·@assistant 멘션·열람≠발화 분리·라이브 UX | [[feature-0009-group-conversation]] | `unit/feature-0009-group-conversation/docs/FUNCTION.md` |
| feature-0010-google-drive-integration | active (토대) | Google Drive 연동 토대 — 계정별 OAuth 토큰 암호화 저장 + MCP 구성 seam (연동 미수행/비활성) | [[feature-0010-google-drive-integration]] | `unit/feature-0010-google-drive-integration/docs/FUNCTION.md` |
| feature-0011-shared-extraction | active (리팩터) | 공통 코드 `shared/` 점진 추출 — model_catalog·config·db·conn_health·datasources (P5a, alias shim 4종 전량 제거·회귀 0). **P5a 종결(2026-08-05)** — Step 6(feature 단위 Dockerfile 분리)은 **불채택**: 분리의 전제였던 import 얽힘·경계 불명이 shared/ 추출 + CODEBASE_MAP §7 Known Gaps 로 해소되고 이후 배포 스파인이 단일 이미지를 전제로 안정화됐다(ADR-20260805T153000-p5a-closeout) | [[feature-0011-shared-extraction]] | `unit/feature-0011-shared-extraction/docs/FUNCTION.md` |
| feature-0012-web-router-modularization | active | feature-0003 `app.py` 도메인별 `APIRouter` 분할 — route 핸들러 전량 추출 완료(148→21 도메인 라우터, byte-동치, P5b behavior-neutral) | [[feature-0012-web-router-modularization]] | `unit/feature-0012-web-router-modularization/docs/FUNCTION.md` |
| feature-0013-relationship-diagrams | active | flow/관계 질문에 mermaid 다이어그램 답변 + 관계 저장소(FK introspection·대화 JOIN 학습) | [[feature-0013-relationship-diagrams]] | `unit/feature-0013-relationship-diagrams/docs/FUNCTION.md` |
| feature-0014-zero-downtime-deploy | review | web 무중단 롤링 배포 — Caddy LB(web-a/web-b) + `bin/deploy-web.sh`(flock·coalesce·TLS preflight·migrate-lint·one-at-a-time+SSE pre-drain·soak 자동롤백) + `/livez`·`/readyz` + :18080 폐기 | [[feature-0014-zero-downtime-deploy]] | `unit/feature-0014-zero-downtime-deploy/docs/FUNCTION.md` |
| feature-0015-zd-hygiene-backup | review | 백엔드/DB 무중단 위생(0014 후속) — insight-worker graceful + MySQL online-DDL 게이트(`mysql-ddl-lint`) + 백업 복원 리허설(`restore-rehearsal`)+cron | [[feature-0015-zd-hygiene-backup]] | `unit/feature-0015-zd-hygiene-backup/docs/FUNCTION.md` |
| feature-0016-metadata-graph | in-progress | AGE 메타데이터 지식그래프(관계형 SSOT→`metadata_kb` 투영) + 관리콘솔 그래프 뷰(PixiJS v8 WebGL) + `graph_navigate` AI 도구 — cutover 라이브 완료 + (07-01) WebGL 렌더러·암묵(FK 미선언) 관계 추론·AI 능동 분석·메타데이터 탭 권한 5분할 + (07-13) 렌더러 PixiJS v8 전면 교체·콘텐츠 밴드 그룹핑 + (08-13) 펼침 시 선택 노드 keep-in-view 카메라 추종(안전영역 안이면 카메라 무이동)·재배치 360ms 이동 트윈(모델 무접촉·관계선/hit-test/bounds 가 트윈 좌표 공유·reduced-motion/씬 교체/노드 600/관계선 1500 비용 상한)·스키마 펼침 중앙 focus 복원(라이브가 잡은 자기 회귀) | [[feature-0016-metadata-graph]] | `unit/feature-0016-metadata-graph/docs/FUNCTION.md` |
| feature-0016-zd-pg-pause-caddy | review | PG pgbouncer PAUSE 래퍼(`pg-restart.sh`, near-zero PG 재시작) + deploy-web.sh Caddyfile reconcile(변경 시 caddy recreate) | [[feature-0016-zd-pg-pause-caddy]] | `unit/feature-0016-zd-pg-pause-caddy/docs/FUNCTION.md` |
| feature-0017-deploy-build-gate | review | deploy-web.sh 빌드 게이트 snap-docker metadata-file race false-failure 수정(이미지 정합 검증) | [[feature-0017-deploy-build-gate]] | `unit/feature-0017-deploy-build-gate/docs/FUNCTION.md` |
| feature-0019-message-editing | in-progress | 메시지 편집 — 1:1 대화 내부 브랜치 트리(단순 수정 / 요청 수정=분기 재답변 `< n/m >` 페이징)·공유(그룹)=단순 수정만 · Phase 1+2 라이브(마이그 0041·PB-0008) | [[feature-0019-message-editing]] | `unit/feature-0019-message-editing/docs/FUNCTION.md` |
| feature-0020-zd-deploy-all | in-progress | 무중단 배포 커버리지 완성 — 워커(insight/ask) 자동 롤아웃·bedrock-gateway surge 무중단 교체·caddy 이미지 드리프트·alembic stale-image 가드 (deploy 스파인 확장) | [[feature-0020-zd-deploy-all]] | `unit/feature-0020-zd-deploy-all/docs/FUNCTION.md` |
| feature-0021-redteam-review | in-progress | assistant 답변 자가 적대(red-team) 리뷰 — fresh-context 5축 검증(find→revise→verify·강도 게이팅·fail-open)+[세션,제품] 메모리 노트(TTL)+콘솔 'AI 추론' 탭 (Claude Code 패턴 이식, 코드 거주 0002/0003/shared) | [[feature-0021-redteam-review]] | `unit/feature-0021-redteam-review/docs/FUNCTION.md` |
| feature-0022-agent-scratch-workspace | in-progress | assistant PG 자율 작업공간 — 전용 DB `agent_scratch`(대화별 격리 스키마)에서 외부 데이터소스 반입·cross-source JOIN·TTL(24h 기본) 정리·scratch_guard allowlist (2026-07-21 라이브 활성·기본값 OFF 게이트 · 코드 거주 0002/shared) | [[feature-0022-agent-scratch-workspace]] | `unit/feature-0022-agent-scratch-workspace/docs/FUNCTION.md` |
| feature-0023-conversation-api-access | in-progress | 외부 AI용 Conversation API — 세션 쿠키 없이 **Bearer 토큰**으로 대화 API(`/api/ask` 등) 호출 + 대화를 tool 화하는 MCP 서버(tool 4종) · scope allowlist(`conversation.*`+`product.access.*`) ∩ 계정권한 · `*.any`/관리 네임스페이스 절대 denylist → 관리 콘솔 차단 (2026-07-22 배포·라이브 e2e 통과: 토큰→/api/ask 200·admin 403·무토큰 401 · 코드 거주 0003/0002) | [[feature-0023-conversation-api-access]] | `unit/feature-0023-conversation-api-access/docs/FUNCTION.md` |
| feature-0024-conversation-folders | in-progress | 대화 폴더(프로젝트 워크스페이스) — 사이드바 재귀 폴더로 대화 조직/이동·폴더 삭제해도 대화 보관(Trash·undo·승격)·런타임 max-depth(기본 4·grandfathering)·폴더별 커스텀 지침 ask-time 주입(요청자 폴더 기준)·엄격 per-user 격리(folder.*.own, Critical privacy 수정) (2026-07-23 라이브 완결 Phase1+2a·PR #895/#899/#903/#908·PB-0008 PASS·코드 거주 0002/0003) | [[feature-0024-conversation-folders]] | `unit/feature-0024-conversation-folders/docs/FUNCTION.md` |
| feature-0025-worker-parallelism | in-progress | 워커 성능·병렬 처리 설정 — 백그라운드 워커(그래프 노드 분석·cluster_label)·사용자 답변·KB 임베딩의 병렬도·처리주기·배치크기를 관리 콘솔 '시스템 > 설정 > 성능·병렬 처리' 서브탭에서 조절(feature-0018 runtime-settings 재사용·신규 동시성 기본 1=현행 직렬 byte-동치 opt-in·LLM만 병렬/DB직렬·admin RBAC(system.runtime.*)·clamp 방어) (2026-07-24 머지 PR #933·단위48+회귀166 PASS·§18.8 SHIP 반영·배포후 PB-0008 잔여·코드 거주 0002/0003/shared/compose) | [[feature-0025-worker-parallelism]] | `unit/feature-0025-worker-parallelism/docs/FUNCTION.md` |
| feature-0026-perf-observability | in-progress | 성능 관측 인프라 — HTTP per-route 타이밍·요청당 DB conn 카운터(`/api/admin/perf/http`)·워커 LLM latency 백필·답변 파이프라인 단계 계측(redteam/post-answer/grounding)·graph-sync duration·perf-snapshot CLI·Caddy access log (측정 전용·동작 변경 0, 2026-07-27 전수 성능 조사 기반) | [[feature-0026-perf-observability]] | `unit/feature-0026-perf-observability/docs/FUNCTION.md` |
| feature-0027-perf-latency-p0 | in-progress | P0 성능 개선 1차 — post-answer 큐레이션(topic/용어/ENUM) terminal 후 이동(답변 체감 -25~35s·결과물 불변)·grounding RO 단일연결·MySQL 버퍼풀 128MB→1G·Caddy gzip+immutable static (feature-0026 측정 근거, 품질 영향 축 불변, 2026-07-28) | [[feature-0027-perf-latency-p0]] | `unit/feature-0027-perf-latency-p0/docs/FUNCTION.md` |
| feature-0028-web-perf | in-progress | web 계층 성능 — ask_result long-poll 워커 스레드 이관(이벤트 루프 stall 제거)·스냅샷 PG 연결 4~5→1(단일 왕복 번들)·권한 카탈로그 TTL 캐시+세션 touch throttle·web MySQL 풀 opt-in (feature-0026 측정 근거·응답/인가 불변, 2026-07-28) | [[feature-0028-web-perf]] | `unit/feature-0028-web-perf/docs/FUNCTION.md` |
| feature-0029-graph-churn | in-progress | 그래프 sync churn 근절 — 값 무변경 시 updated_at 미전진(upsert·신호·트리거 alembic 0046)·status 히스테리시스(trusted/broken 왕복 차단)·프로브 broken 부활 금지·공유 정점 중복 MERGE 제거(관계당 cypher 11→1~3). 라이브 실측 근거(2h 갱신의 63%가 값 무변경, sync duration 은 churn 행 수에 선형) (2026-07-28) | [[feature-0029-graph-churn]] | `unit/feature-0029-graph-churn/docs/FUNCTION.md` |
| feature-0030-ask-timeout-extension | in-progress | 실행 타임아웃 임박 시 사용자 확인 후 연장 — 예산 80%(설정 가능) 도달 시 작업 화면에 비차단 배너 + 백그라운드 브라우저 알림, 승인한 그 요청에 한해 run 예산 컷 해제(개별 LLM 호출 상한 15분은 유지 — 중단·즉시답변 응답성 보존). 미승인 시 종전 타임아웃 동작 (2026-07-29) | [[feature-0030-ask-timeout-extension]] | `unit/feature-0030-ask-timeout-extension/docs/FUNCTION.md` |
| feature-0031-analysis-grounding | in-progress | 노드 분석 접지 — 운영 DB 에서 **통계만**(원시 샘플값 배제, 문자열 min/max 도 미저장·`value_pattern` 6종 CHECK) 단계적으로 수집해 `metadata_table_stats`/`metadata_column_stats`(alembic 0050)에 적재하고 노드 분석 payload 의 `evidence` 블록으로 주입(L0+L1). `NODE_ANALYSIS_PROMPT` 를 '이름 규칙 추론'→'증거 우선'으로 개정 + thin 판정을 길이→항목 충족도로 재정의. LLM 호출 수 불변(같은 콜에 더 나은 입력)·Stage 0 카탈로그(사용자 테이블 read 0)~Stage 2 표준 표본까지 하루 최대 1단계 승격(주간은 Stage 1 상한)·Stage 3 정밀은 운영자 승인 knob 전용·`ds` 자원 예산 게이트 위 fail-soft (2026-07-30) | [[feature-0031-analysis-grounding]] | `unit/feature-0031-analysis-grounding/docs/FUNCTION.md` |
| feature-0032-llm-token-budget | in-progress | 백그라운드 LLM 토큰 예산 — 사람이 요청하지 않은 자동 지출(노드 분석·클러스터 유지보수·제품 분류)에 rolling 24시간 토큰 상한(`agent_runtime.llm_usage` 원천·진입점 3곳 게이트·커버리지 96%·60초 캐시). **사용자가 기다리는 호출은 세지도 막지도 않는다**(설계 불변식)·fail-open 3중·기본 2,000만(24h 실측 685만의 약 3배)·콘솔 'AI 운영 현황' 예산 막대+attention 2단계 (2026-07-30) | [[feature-0032-llm-token-budget]] | `unit/feature-0032-llm-token-budget/docs/FUNCTION.md` |
| feature-0033-analysis-synthesis | in-progress | 클러스터 합성 요약(L2) — 의미 클러스터마다 "이 묶음이 함께 무엇을 하는가"를 2~4문장으로 합성해 `cluster_summaries`(alembic 0051)에 적재(라벨 평균 9자가 이름이라면 요약은 설명). PK 는 churn 하는 `cluster_id` 대신 **멤버셋 지문**·캐시 키 3중 일치(멤버셋+L1+L0)·클러스터링 시그니처 **미유입 불변식**(재임베딩 순환 차단)·pass 당 40개 상한·배치 6·feature-0032 예산 하위·live 정지 스위치 (라이브 818 클러스터·15,365 멤버, 2026-07-30) | [[feature-0033-analysis-synthesis]] | `unit/feature-0033-analysis-synthesis/docs/FUNCTION.md` |
| feature-0034-analysis-consumption | in-progress | 분석 산출물의 대화 소비 — 질문이 언급한 테이블이 속한 묶음의 L2 요약 1~2건을 답변 컨텍스트 `TABLE GROUP SUMMARIES` 섹션으로 주입해 RI-5(쌓인 분석이 콘솔 열람에만 갇혀 있던 상태) 해소. 사전 계산분만(런타임 합성·LLM 호출 0)·근거 수 병기로 추정/실측 구분·2단계 매칭(`strpos` + `(scope, effective_schema, label)` 격리)·`_datamark_untrusted`·statement_timeout 1.5s·전 구간 fail-soft (2026-07-30) | [[feature-0034-analysis-consumption]] | `unit/feature-0034-analysis-consumption/docs/FUNCTION.md` |
| feature-0035-analysis-planner | in-progress | 결정적 분석 플래너 — 아직 분석되지 않은 테이블 중 **중요한 것부터** 자동으로 분석 대기열에 시드한다. 중요도 = `대화 조인 이력 × 50 + 관계 차수 × 1`(동점은 이름 오름차순)로 **LLM 없이** 결정적으로 계산하고 AGE 실시간 중심성은 쓰지 않는다(multi-hop 라이브 최악 82초 — 필요한 건 정확한 값이 아니라 순서). 큐잉은 재구현하지 않고 `node_analysis.enqueue_change_analysis` 를 `reason="coverage_priority"` 로만 구분해 재사용(자격·그래프 실재·cap·쿨다운·busy 가드 상속)·2중 상한(스키마당 3 · 사이클 9 = load-bearing)·`object_key` prefix + `strpos(…)=1`+`DISTINCT`·파티션 계열은 대표 1개만(라이브 1,464 테이블 중 1,364=93% 가 날짜 접미) (라이브 커버리지 2,040/17,192=11.9% 가 L1·L2·grounding 품질 상한이던 것을 해소, 2026-07-31) | [[feature-0035-analysis-planner]] | `unit/feature-0035-analysis-planner/docs/FUNCTION.md` |
| feature-0036-analysis-verification | in-progress | 분석문 사실성 판정 — AI 가 쓴 테이블 설명을 **L0 통계 증거와 대조**해 `supported`/`contradicted`/`unverifiable` + 판정을 가른 숫자를 지목하는 근거 한 문장으로 `node_analysis_verdicts`(alembic 0052)에 적재. **판정 실패는 "검증됨"이 아니다** — LLM 오류·타임아웃·계약 위반·근거 없는 응답·증거 부재·저장 실패는 전부 행을 만들지 않는다(= 미검증). fail-soft 가 "통과"가 아니라 **"침묵"**. 예외 하나: 예산 모듈을 읽을 수 없으면 pass 를 중단한다. `analysis_hash` 가 재판정 축(노드당 1행)·pass 당 20건·**배치 없음(1건 1콜** — 배치하면 한 건의 오판이 다른 건으로 번진다)·호출측 `limit` 은 설정 상한을 넘을 수 없다. **2026-08-05 배포 후 라이브에서 판정 무한 순환 발견·차단** — 대상 선정이 행 단위인데 저장이 노드당 1행이라 여러 분석 run 의 done 행이 서로를 미판정으로 되돌렸다(7일 7,896콜에 판정 행은 91개 고정) → 대상도 `DISTINCT ON (scope_key, node_key)` 노드당 최신 1건(\"최신\"=`id`)·순회는 판정 오래된 것부터(ADR-0036-08, 시간당 148콜 → ~14콜). **판정 결과 노출** — 그래프 뷰 노드 상세 'AI 능동 분석' 박스에 배지 + 근거 한 줄, 해시 일치일 때만 표시(ADR-0036-09)·증거 stage 0 은 표본이 0행이라 \"구조와 …\" 라벨(ADR-0036-10)·PB-0008 실측 PASS (2026-07-31 머지 / 2026-08-05 순환 차단·노출) | [[feature-0036-analysis-verification]] | `unit/feature-0036-analysis-verification/docs/FUNCTION.md` |
| feature-0037-domain-synthesis | in-progress | 도메인 합성(L3, lazy) — DB(스키마) 하나의 도메인 개요를 3~5문장으로 접어 `domain_summaries`(alembic 0053)에 둔다. 입력은 개별 테이블이 아니라 그 스키마의 **클러스터 요약들(L2)** — 이미 한 번 접힌 것을 다시 접는다. **요청과 생성을 분리**해 사전 전량 생성 금지(LazyGraphRAG)와 답변 경로 런타임 합성 금지(ADR-0034-07)를 함께 지킨다: grounding 이 조회하고 없으면 `request()` 만 남기고(LLM 0·지연 0·요청 UPSERT 는 별도 RW 연결) insight tick 이 요청된 것만 `request_count` 우선순위로 합성한다(**사용이 곧 우선순위**). 재생성 축 `cluster_set_hash`(라벨·요약·멤버 수·근거 수)는 payload cap 25 로 자르기 **전** 전체 집합(최대 300)으로 해시·pass 당 3·advisory lock 을 얻은 tick 에서만·30자 미만 미저장 (라이브 클러스터 요약 1,006건/120 스키마=평균 8, 2026-07-31) | [[feature-0037-domain-synthesis]] | `unit/feature-0037-domain-synthesis/docs/FUNCTION.md` |
| feature-0038-frontend-modularization | review | 프론트엔드 모듈화(ssot-consolidation ROADMAP **ITEM-P5b 완결** — 본편 10 cycle 2026-08-04 + 후속 Phase A~B3 2026-08-05) — 프론트 모놀리스 3파일(admin.js 14,007줄 · app.js 13,165줄 · styles.css 9,328줄, 2026-08-03 실측)을 behavior-neutral 점진 추출로 도메인 모듈화하는 initiative unit. 백엔드 `app.py` 분할은 feature-0012 가 완결했으므로 범위 밖이고, 코드는 feature-0003 `src/static/**` 에 계속 거주하며 본 unit 은 계획·추적·검증 기록 홈이다(feature-0012 와 동일 패턴). big-bang 금지 — cycle 당 단일 PR + 게이트(make test · PB-0008 브라우저 QA · 롤백 리허설 · plan-review Critical). Cycle 1 배포 완료(styles.css → `css/` 7파일 순차 concat 이 원본과 byte-identical·PB-0008 PASS·롤백 리허설 revert 왕복 diff 0) · Cycle 2~10 + Final 로 본편 완결(2026-08-04): styles.css(9,328) 소멸 + `css/` 7파일 · admin.js 14,007 → **4,804줄(-66%)** + `admin/` 9모듈 · app.js **11,119줄** + ES module 전환 + `app/` 4모듈(PR #1124~#1143 전건 배포·POST-DEPLOY PB-0008 PASS) · **후속 Phase A~B3 완결(2026-08-05, PLAN-APPROVED)**: 공유 가변 `let` 2건 state 편입(Phase A, 비-중립 mini-change) 후 사이드바·composer·progress 도메인 byte-동치 이동으로 app.js **11,119 → 8,082줄(-27%)** + `app/` 6모듈, PR #1147~#1150 전건 배포·POST-DEPLOY PASS. AC-3(오케스트레이터 ≤~3,000줄)은 부분 달성 정직 보고(잔여 admin.js 4,804줄) (위험도 Critical·PLAN-APPROVED 2026-08-03·후속 2026-08-05) | [[feature-0038-frontend-modularization]] | `unit/feature-0038-frontend-modularization/docs/FUNCTION.md` |
| feature-0039-ops-scheduler | review | 운영 정기 잡(백업·복원 리허설·AGE 그래프 sync 증분/전량)을 호스트 root crontab → `ops-scheduler` 컨테이너 서비스로 이관. root 였던 유일한 근거인 `docker exec`(=docker 소켓 root 독점) 의존을 제거하고, 스케줄 정본을 crontab(버전관리 밖)에서 `docker-compose.yml` 의 `OPS_SCHED_*` 로 이동. §82 flock 은 호스트 lock 파일 bind-mount 로 inode 를 공유해 `routine-backfill.sh` 와 상호배제 유지(미마운트 시 fail-loud). pg_dump 는 PGDG `postgresql-client-16` 으로 서버 메이저 고정(trixie 기본 client-17 산출물은 PG16 복원 불가 실측). 부수: AGE cutover 이후 5주간 FAIL 하던 PG 복원 리허설 결함 수정(사용자 승인) — 761MB 실백업 전량 복원 PASS | [[feature-0039-ops-scheduler]] | `unit/feature-0039-ops-scheduler/docs/FUNCTION.md` |
| feature-0040-db-object-explorer | review | 역할 기반 DB 객체 탐색 — 트리거·이벤트·SQL Server Agent 작업·뷰·시노님·시퀀스를 벤더 객체명이 아니라 **역할**(6종 taxonomy SSOT `modules/db_object_roles.py`)로 분류해 `search_db_objects`(역할 생략 시 전 역할 개관)·`describe_db_object` 도구 2종으로 노출하고, `db_objects` SSOT(alembic 0054) + AGE `DbObject`/`HAS_OBJECT`/`OBJECT_USES`(참조·실선)/`OBJECT_ON`(소유·파선) 투영으로 그래프 뷰에 편입(구리 칩·역할 아이콘·표시 토글 5종·범례). 핵심 불변식은 **미지원 ≠ 부재** — 지원상태 4종(SUPPORTED/UNSUPPORTED/PRIVILEGED/DELEGATED)이 0행을 "없다"로 뭉개는 허위 부재를 타입 레벨에서 차단하고, `msdb` 접근은 `_agent_jobs_sql` 한 함수의 고정 질의로만 한다. 신규 77건 PASS·회귀 0·실 Windows Chrome 150 WebGL 실증 (2026-08-12 머지·**라이브 배포 완료**(doc_sync 08-13 실측: alembic `0054` 적용됨(라이브 head `0055`) · `db_objects` 339행 · 그래프 자산 라이브 byte-identical) · 잔여=POST-DEPLOY PB-0008 시각검증 · 코드 거주 0002/0003) | [[feature-0040-db-object-explorer]] | `unit/feature-0040-db-object-explorer/docs/FUNCTION.md` |
| feature-0041-external-ai-tool-surface | in-progress | 외부 AI 도구 표면(추론 주체 반전) — 외부 사용자의 AI 가 **자기 계정 LLM 으로 직접 추론**하면서 이 서비스의 데이터소스·RAG·메타지식에 접근하는 표면(LLM 비용은 호출자 부담·서비스는 자격증명 무보관). feature-0023 의 `ask` 축(우리 LLM 이 추론)과 병존·용도 구분. OAuth AS(`routers/oauth_as.py` — DCR·authorize(세션 쿠키 필수)·token·revoke) + P0 도구 9종 REST(`routers/ai_tools.py` — 관문 순서 **토큰→상한→스코프→실행→각인→원장** 고정·`P0_TOOLS` allowlist 로 도달면 고정·**원장 실패 시 결과 미반환**·거절/게이트도 원장 기록) + `WebAiTasks`(미제출률 = 소프트 강제의 계량 원천) + 전송 어댑터 2종(MCP stdio `external_tool_mcp_server.py` · HTTP/SSE **`ext-tool-mcp` 서비스로 라이브 기동** + 엣지 `/api/ai/mcp` — 판단 로직 0·토큰 무보관·리다이렉트 시 Authorization 전달 금지, 전송 계층에 verifier 가 없으므로 엣지가 `Authorization` 존재 자체를 요구해 익명 스트림 개설 차단) + 발견 자료(매니페스트 `tool_surface`·큐레이션 OpenAPI 7 path — "익명=static contract, 인스턴스 데이터 0" 불변식을 테스트로 고정) + **URL 접속 인증**(RFC 8414/9728 discovery 4경로 + 401 `WWW-Authenticate` · 서명 consent token 동의 화면(세션 결합·nonce 1회) · 발급 페이지 `/ai/connect` · 복귀 대상 `safeNextTarget` = origin 비교로 오픈 리다이렉트 차단) + 상한 4종 콘솔 전용 패널(`runtime_settings` 그룹 `external_tool_surface`) · `docs/SECURITY.md §44`(신뢰경계 반전 위협모델). 1차 `a68fbbac` + 2차 `e1372f32` + 3차 `89b7cd54`→`feadc089` + 인증 접근성 `5f20ee88` 라이브 배포 · POST-DEPLOY 전건 실측 (2026-08-12 신규·Critical · 잔여=사람 1회 브라우저 인가가 필요한 전 구간 e2e(설계상 자동화 불가)·P1 이후 도구는 원장 데이터 보고 판단 · 코드 거주 0003/0002/0006/shared) | [[feature-0041-external-ai-tool-surface]] | `unit/feature-0041-external-ai-tool-surface/docs/FUNCTION.md` |

## 3. Archived / completed

| Feature | 종료 | 카드 |
|---|---|---|
| (없음) | — | — |

## 4. Skeleton

- [[_template-card]] — 새 feature 추가 시 복제할 카드 형식
- [[../_templates/feature-card]] — Obsidian Templater 호환 노트 템플릿

## 5. 관련 문서

- [[../Architecture/Module-Map|Module Map]] — feature 가 어디에 위치하는지
- [[../Decisions/_Index|Decisions MOC]] — feature 관련 ADR
- [[../../docs/STATUS|docs/STATUS.md]] (정본 — 진행률)
- [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] §4 (정본 — 기능 맵)

## 6. 둘러보기

- 상위: [[../Index|Index]]
- sibling: [[../Decisions/_Index]] · [[../Architecture/Overview]]

## 7. 외부 link

- 없음

## 분류

`#wiki/index` · `#confidence/high` · `#maturity/substantial`
