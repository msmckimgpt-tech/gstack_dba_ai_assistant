---
doc_type: WIKI_LOG
scope: project
status: active
edit_policy: append-only
source_of_truth: true
template_version: v3.12.0
domain: [history, wiki]
ai_read_priority: 9
wiki_role: log
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
---

# Wiki — Log

Append-only 이력. AI 가 wiki 의 페이지를 추가/수정할 때마다 한 줄씩 누적한다. 기존 entry 는 수정·삭제 금지.

## Format

```
[YYYY-MM-DDTHH:MM:SSZ] <operation> | <wiki_role> | <path> | <one-line note>
```

- `<operation>`: `create` | `update` | `link` | `lint-fix` | `graduate`
- `<wiki_role>`: `index` | `article` | `log` | `source_summary` | `feature_card` | `adr_mirror`
- `<path>`: `wiki/` root 로부터의 상대 경로
- `<one-line note>`: 변경 이유 1줄 (≤ 100자)

## Entries

> 첫 entry 는 copy-base 직후 AI 가 vault 를 활성화할 때 작성한다.

<!-- AI: 새 entry 는 위 "## Entries" 헤딩 직후, 다음 줄에 prepend (최신순) -->

[2026-06-12T05:04:26Z] update | hot_cache | hot.md | 2026-06-12 멀티 데이터소스 시대 세션 컨텍스트로 재작성 (drift 해소)
[2026-06-12T05:04:26Z] update | article | overview.md | 멀티 데이터소스 서사 합성 — 8 feature / ADR-0027~0030 / 진행흐름·한계·다음단계 재정렬
[2026-06-12T05:04:26Z] update | index | Index.md | 도메인=멀티 데이터소스 분석 플랫폼 / 8 feature / ADR-0001~0030 + unit ADR
[2026-06-12T05:04:26Z] update | article | Architecture/Overview.md | 8 feature 맵 + 멀티 데이터소스·storage 단일화 특징
[2026-06-12T05:04:26Z] update | article | Architecture/Data-Flow.md | 멀티 데이터소스 data plane + ask-worker 큐 mermaid·trust boundary §2.5
[2026-06-12T05:04:26Z] update | article | Architecture/Module-Map.md | feature-0002 핵심 모듈(dialects/cred_crypto/runtime_backend) + feature 0001~0008
[2026-06-12T05:04:26Z] update | feature_card | Features/feature-0003-agent-web-ui.md | 관리콘솔(데이터소스CRUD·대시보드·LLM사용량·insight완료율)·ask-worker·취소재요청 §2.5
[2026-06-12T05:04:26Z] update | feature_card | Features/feature-0002-agent-core.md | 멀티 데이터소스 §2.5 (dialect·registry·DB접근·insight·EXPLAIN gate)
[2026-06-12T05:04:26Z] update | index | Features/_Index.md | feature-0008 추가 (7→8 active) + 0002/0003 한줄 갱신
[2026-06-12T05:04:26Z] create | article | entities/mssql.md | MSSQL entity — dialect·3-part·DB접근·envelope 자격
[2026-06-12T05:04:26Z] update | index | entities/_Index.md | MSSQL 등록 (9→10) + Tool 분류 갱신
[2026-06-12T05:04:26Z] update | article | entities/mysql.md | 멀티 데이터소스 시대(main_mysql datasource·DB-단위 접근) §2.4
[2026-06-12T05:04:26Z] create | article | concepts/ask-worker-queue.md | out-of-process ask 큐 (ask_jobs·SKIP LOCKED·TASK-0169 cutover)
[2026-06-12T05:04:26Z] create | article | concepts/insight-worker.md | schema 통찰 + 분석 완료율(0223) + DB별 파악내용(0242) + __global__ sentinel
[2026-06-12T05:04:26Z] create | article | concepts/datasource-aware-rag.md | ds-aware rag_objects + endpoint-hash scope(compute_scope_key) (TASK-0219)
[2026-06-12T05:04:26Z] create | article | concepts/db-level-access.md | DB-단위 접근 (catalog allowlist·시스템DB 가시성만) (TASK-0206)
[2026-06-12T05:04:26Z] create | article | concepts/datasource-registry.md | envelope 암호화 KEK/DEK + WebDatasources CRUD (TASK-0205)
[2026-06-12T05:04:26Z] create | article | concepts/multi-datasource.md | MySQL·MSSQL dialect adapter + 3축 보안 게이트 + 1:N 제품
[2026-06-12T05:04:26Z] update | index | concepts/_Index.md | 신규 concept 6종 등록 (6→12)
[2026-06-12T05:04:26Z] create | adr_mirror | Decisions/ADR-0030-ssrf-guard-toggle.md | datasource SSRF 사설망 경계 env 토글
[2026-06-12T05:04:26Z] create | adr_mirror | Decisions/ADR-0029-windows-browser-testing.md | 실제 Windows 브라우저 AI 자동 검증 (PB-0008)
[2026-06-12T05:04:26Z] create | adr_mirror | Decisions/ADR-0028-runtime-mysql-cleanup.md | runtime 6 테이블 MySQL cleanup Stage A/B/C
[2026-06-12T05:04:26Z] create | adr_mirror | Decisions/ADR-0027-agent-runtime-pg-schema.md | agent_runtime PG schema + AR-M4 read cutover
[2026-06-12T05:04:26Z] update | index | Decisions/_Index.md | ADR-0027~0030 mirror 등록 + unit-level ADR-CORE/WEB 표 (§2.1)
[2026-05-28T15:50:00Z] update | hot_cache | hot.md | T1~T5 전체 활성화 완료 — PgBouncer md5/pg_hba 정합 수정 + replica streaming 확인
[2026-05-28T00:00:00Z] update | article | concepts/kb-postgres-pgvector.md | T1~T5 성능 최적화 로드맵 완수 반영 — DISTINCT ON/ANY/MV/JSONB/PgBouncer/replica/advisory-lock/LISTEN-NOTIFY
[2026-05-28T00:00:00Z] update | article | Architecture/Data-Flow.md | pgbouncer sidecar + postgres-replica 다이어그램 추가 (T3-8, T5-14)
[2026-05-28T00:00:00Z] update | hot_cache | hot.md | T1~T5 완수 세션 컨텍스트 압축 저장
[2026-05-26T06:52:40Z] update | index | Index.md | namu-style 인포박스 + 7-feature 매핑 + namu sections 정리 (v3.13.0 follow-up wiki sync)
[2026-05-26T06:52:40Z] update | article | overview.md | living synthesis — 7 feature 표 + 핵심 ADR + KB / 첨부 / Bedrock 흐름 합성
[2026-05-26T06:52:40Z] update | article | Architecture/Overview.md | ARCHITECTURE.md §1~§6 mirror — 4-layer 책임 / 7 feature 표 / 의존 표
[2026-05-26T06:52:40Z] update | article | Architecture/Data-Flow.md | mermaid flowchart — Caddy → web → agent loop / Bedrock / KB / MinIO + trust boundary 표
[2026-05-26T06:52:40Z] update | article | Architecture/Module-Map.md | top-level 디렉토리 매핑 + docs/ 정본 인덱스 + artifacts 조직 표
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0001-platform-runtime.md | namu-style — MySQL/DAB · replica · redo log 1 GiB
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0002-agent-core.md | namu-style — agent loop · KB Postgres M0~M5 · audit
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0003-agent-web-ui.md | namu-style — FastAPI · admin · audit · 첨부 · sandbox · share
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0004-browser-automation.md | namu-style — Playwright HTTP service
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0005-qa-mcp.md | namu-style — MCP test + QA helper
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0006-lan-proxy-access.md | namu-style — Caddy TLS · XFF trust · Windows portproxy
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0007-bedrock-llm-provider.md | namu-style — Bedrock gateway · API Vault 폐기 · env 분리
[2026-05-26T06:52:40Z] update | index | Features/_Index.md | 7 feature entry 표 채움
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0001-state-history-separation.md | 현재 상태 / 이력 분리
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0002-agents-md-canonical.md | AGENTS.md 정본 · CLAUDE.md 참조
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0003-first-request-scope.md | FIRST_REQUEST 부트스트랩 전용
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0004-blocked-preapproved-risk.md | BLOCKED + Pre-approved + 위험도
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0005-task-source-of-truth.md | TASK.md 정본 격상
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0006-test-md-mixed-policy.md | TEST.md 혼합 정책
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0007-conflict-resolution-rule.md | 충돌 해석 규칙
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0008-archiving-policy.md | append-only 20건 초과 아카이빙
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0009-shared-governance.md | shared/ 거버넌스
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0010-status-doc.md | docs/STATUS.md 도입
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0011-gitignore-artifacts.md | .gitignore artifacts 규칙 제거
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0012-feature-unit-restructure.md | feature 단위 재배치
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0013-shared-runtime-separation.md | shared ↔ artifacts 경계
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0014-env-canonical.md | .env / AGENTS.md 원본 의미 보존
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0015-template-v2.md | Template v2.0.0 마이그레이션
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0016-template-v3.md | Template v3.0.0 Plan-Review-Execute
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0017-github-automation-stack.md | superseded by ADR-0018
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0018-github-automation-decommission.md | GitHub 자동화 폐기
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0019-web-audit-events.md | WebAuditEvents dispatcher + 4 권한
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0020-slow-query-log-decoupled.md | slow_query_log 통합 거부
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0021-kb-postgres-rbac.md | KB Postgres 2-layer RBAC
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0022-minio-attachment-storage.md | MinIO 첨부 storage
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0023-sandbox-schema-mysql-users.md | sandbox schema + 4 user
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0024-postgres-database-isolation.md | 단일 cluster + 별 DB
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0025-m5-cleanup.md | M5 cleanup 14-day window (정본 ADR-0025 두 entry 중 하나)
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0025-pgvector-attachment-rag.md | PGVector attachment RAG (정본 ADR-0025 두 entry 중 하나)
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0026-bedrock-llm-provider.md | Bedrock + API Vault 폐기 + Phase E
[2026-05-26T06:52:40Z] update | index | Decisions/_Index.md | 27 entry 표 (ADR-0025 두 mirror)
[2026-05-26T06:52:40Z] create | article | concepts/rag.md | RAG (Retrieval-Augmented Generation)
[2026-05-26T06:52:40Z] create | article | concepts/kb-postgres-pgvector.md | KB Postgres pgvector
[2026-05-26T06:52:40Z] create | article | concepts/audit-subsystem.md | Audit Subsystem
[2026-05-26T06:52:40Z] create | article | concepts/llm-wiki-3-layer.md | LLM Wiki 3-layer (raw/wiki/schema)
[2026-05-26T06:52:40Z] create | article | concepts/namu-style-format.md | namu-style 사람 facing 형식
[2026-05-26T06:52:40Z] create | article | concepts/sandbox-schema-isolation.md | Sandbox Schema Isolation
[2026-05-26T06:52:40Z] update | index | concepts/_Index.md | 6 concept entry 표
[2026-05-26T06:52:40Z] create | article | entities/mysql.md | MySQL 8.0
[2026-05-26T06:52:40Z] create | article | entities/postgres.md | PostgreSQL 16 (pgvector)
[2026-05-26T06:52:40Z] create | article | entities/aws-bedrock.md | AWS Bedrock
[2026-05-26T06:52:40Z] create | article | entities/litellm.md | LiteLLM proxy
[2026-05-26T06:52:40Z] create | article | entities/minio.md | MinIO
[2026-05-26T06:52:40Z] create | article | entities/playwright.md | Playwright
[2026-05-26T06:52:40Z] create | article | entities/caddy.md | Caddy
[2026-05-26T06:52:40Z] create | article | entities/karpathy.md | Andrej Karpathy
[2026-05-26T06:52:40Z] create | article | entities/obsidian.md | Obsidian
[2026-05-26T06:52:40Z] update | index | entities/_Index.md | 9 entity entry 표
[2026-05-26T06:52:40Z] update | index | Glossary/_Index.md | 24 inline term 표 (template + project-specific)
[2026-05-26T06:52:40Z] lint-fix | index | sources/_Index.md | 깨진 wikilink 예시 placeholder text 로 전환 (lint broken PASS)
[2026-05-26T06:52:40Z] lint-fix | index | syntheses/_Index.md | 깨진 wikilink 예시 placeholder text 로 전환 (lint broken PASS)

## [2026-06-15] feature | TASK-0256 assistant 답변 markdown diff 블록(리뷰 시 변경 제시) + 웹 UI diff 색 렌더 (PR#209, main 2befd37)
## [2026-06-16] docs | 서비스 소개 프레젠테이션(docs/presentation: 자기완결 HTML 덱 + SCENARIO.md 발표 스크립트·공격 질문 대응) 신설 + wiki 정합 갱신(연결상태 3색·datasource Id surrogate·첨부 PG cutover·답변 diff)
## [2026-06-16] docs | 프레젠테이션 개정 — 공격질문을 발표자 전용 OBJECTION-HANDLING.md 로 분리(덱에서 제거)·워커(질문 일꾼/정리 일꾼) 작동 슬라이드 추가·전문용어 비전문가용 평이화·한국어 word-break(keep-all) 줄바꿈 수정·세로 스크롤 제거(크기 축소). browse 1366×768 검증 scroll=0
## [2026-06-16] docs | 프레젠테이션 정합/표현 보완 — mock UI 를 실제 서비스 라벨로 정합(새 대화·관리 콘솔·데이터소스·감사 로그·LLM 사용량·설정·brand "Database Query Assistant")+"예시 화면" 표기(거짓 인지 방지)·과장 표현 절제(근거 같은 페이지면 무심한 어투)·창 높이 맞춤 scale-to-fit(overflow:hidden, 짧은 창 1174×588 scroll=0)·**모든 항목 클릭 시 상세 설명 팝업**(data-explain 46키, 전문용어 허용; 클릭=팝업/빈영역=이동)
## [2026-06-16] docs | 프레젠테이션 슬라이드[8] 권한 격자 실제 UI 정합 — 2단 섹션(관리 권한/운영 권한)+그룹 활성화 개수 배지+토글 카드(라벨+설명, PERMISSION_DEFINITIONS 실값)+종속성 트리 depth+`관리 콘솔 접근` 마스터 게이트+"세부 권한 N개 더 보기"(점진적 공개)+내 대화/전체 대화 분리. browse page8 렌더 검증
## [2026-06-16] docs | 프레젠테이션 단계 표시 + 우측 말풍선 팝업 — 페이지 내 reveal 진행("단계 N/M"+점, 완료 시 "다음=페이지")을 우하단에 표시(실수 페이지 넘김 방지); 상세 설명 팝업을 중앙 딤 모달 → **우측 말풍선**(슬라이드인 애니메이션·좌측 꼬리)로 전환, 배경 딤/흐림 제거(뒤 슬라이드 선명)·부드러운 그림자만. 외부 클릭 닫힘. browse 검증(단계 0→3·다음=페이지, 팝업 bg transparent)
## [2026-06-16] docs | 프레젠테이션 고아 줄바꿈 제거 — 단어 하나만 다음 줄로 떨어지는 현상 방지(`text-wrap:pretty` 본문/`balance` 제목) + `.lead` max-width 46em→64em. 작업화면 lead 1줄 정합(browse 1289×587·1366×768 lead lines=1 검증)
## [2026-06-16] docs | 프레젠테이션 마무리 슬라이드의 동작하지 않는 CTA 버튼("시범 도입 문의"·"자세한 자료 보기") 제거 + 미사용 .cta CSS 정리. outro=타임라인+도입 권장 순서로 종료. browse 검증(cta/btn 0, 15슬라이드 유지)
## [2026-06-16] docs | 프레젠테이션 상호작용 발견성 개선 — Ctrl 키를 누르고 있는 동안 클릭 가능한(상세 설명) 항목을 옅게 강조(`body.find-explain [data-explain]` outline+soft glow, keydown/keyup·blur 토글, 발표 중 상호작용 지점 찾기 용이) + 상세 팝업이 열린 상태에서도 다른 항목 클릭 시 교체(`.pop{pointer-events:none}`/`.pop-card{pointer-events:auto}` 로 오버레이 통과 → deck 핸들러가 openPop 재호출; 빈 곳 클릭=팝업만 닫힘, 페이지 유지). browse 1366×768 검증(outline rgb(37,99,235)+glow·keyup 해제·elementFromPoint 통과·교체·Esc/네비 회귀·팝업 bg transparent)
## [2026-06-17] docs | 프레젠테이션 Ctrl 강조를 outline → 은은한 glow fade-in/out 로 변경 — outline 이 발표 중 거슬려 제거하고, Ctrl 누른 동안 클릭 가능 항목 주위로 glow 가 천천히 fade-in/out(`@keyframes findglow` alpha 0↔.55, blur 1px↔7px, 2.1s ease-in-out infinite). `filter:drop-shadow` 사용(항목 고유 box-shadow/레이아웃 무간섭) + `prefers-reduced-motion` 정적 glow 폴백 + keyup/blur 시 transition .35s 로 부드럽게 해제. browse 검증(outline none, filter alpha 시간별 0→.52→0 호흡, keyup→filter none, 팝업 열기/교체/닫기 회귀)
## [2026-06-17] docs | 프레젠테이션 Ctrl glow keyup 해제를 snap → 은은한 fade-out 으로 — 키를 떼면 glow 가 갑자기 사라져 청중에게 거슬리던 것을 부드러운 fade-out 으로. 핵심: CSS 애니메이션만 제거하면 transition 이 발화하지 않고 snap 됨 → setFind(off) 에서 현재 glow 값을 `getComputedStyle().filter` 로 읽어 inline 고정 → find-explain 제거(애니메이션 중단) → reflow → `filter:'none'` 설정해 base `transition:filter .5s`(.35→.5s)로 0 까지 점진 감소 → 560ms 후 inline 정리. 재누름 시 타이머 clear+inline reset 으로 즉시 재강조. browse 검증(peak 0.55→0 점진, 중간 0.075 지점도 점프 없이 fade, 재누름 clean, 팝업 회귀)
## [2026-06-17] docs | 실무자(현업 사용자) 전용 프레젠테이션 신설 — docs/presentation/practitioner.html (기존 index.html 과 별도). 관리 콘솔·내부 아키텍처/워커 토폴로지 제외하고 '실제 사용 흐름'만 9슬라이드로: 표지 → 무엇을 할 수 있나(할 수 있는/없는 일) → 첫 화면(작업화면 mock, 관리 콘솔 링크 제거) → 질문하는 법(기간·대상·정렬, 데이터소스 선택, 이어서 다듬기) → 진행 과정(단계+근거, 멈춤/즉시답변) → 결과 보기(표·CSV·diff) → 편의 기능(첨부·검색·공유·연결상태) → 안심하고 쓰기(조회전용 3단계·범위·기록) → 잘 쓰는 법(흐름 요약). 상세 설명은 동일 팝업(data-explain 23키) 방식, 프레임워크(scale-to-fit·우측 말풍선·Ctrl glow fade·인덱스·터치)는 index.html 검증본 재사용. browse 1366×768 검증(9슬라이드·관리콘솔/아키텍처 0건·전 슬라이드 fitsV·bodyScroll=false·팝업 열기/교체·Ctrl glow outline없음·콘솔 0). 배포 불필요(정적 산출물). [[project_task_conv_entry_defaults]]
## [2026-06-23] fix | insight-worker "제품 DB 파악 진전 없음" 병목 진단·수정 (TASK-0305) — 다중가설+적대검증으로 2축 분리: 축A 커버리지=39 catalog DB 중 28개 RO 로그인 per-DB GRANT 누락(권한 18456/916)으로 영구 스캔실패(서킷이 엔드포인트 단위라 per-DB 권한실패 미격리)→status=degraded 고정, **1차 해결은 운영 GRANT**; 축B 처리량=살아있는 11개 DB 도 신규통찰 0. 코드 3건(insight.py): RC2 fingerprint casefold(VALUE 한정 — MSSQL information_schema 케이스 진동 TF_ErrorLog↔tf_errorlog 의 11초 LLM 재생성 churn 제거), RC3 진전기반 backoff(무경계 detector 의 force_scan 영구 latch spin 차단, 건강한 처리량 보존, ANCHOR §3 순서 무손상), RC5 cycle summary 에 db_failed_{perm,circuit,other} 노출+비-MSSQL ds 집계(perm vs network 분리 특정). 테스트 8 + 회귀 0, 적대 backend+qa 리뷰 ACCEPT. [[insight-worker]]
## [2026-06-23] wiki-ingest | 문서 정합 갱신(06-19~23 작업 rollup) — `Features/feature-0009-group-conversation.md` 카드 신설 + `Features/_Index`(8→9) · `overview.md`/`Index.md`/`Architecture/Overview.md` 에 그룹 대화(feature-0009)·사용자 보안 보강 6종 완료·NL→SQL flywheel 반영(06-16→06-23 drift 해소) · `concepts/nl2sql-flywheel.md` 신설 + `concepts/_Index`(12→13) · stale 했던 "보안 hardening 미구현" 한계 정정. (동반: 릴리즈노트 06-23 블록 + STATUS.md 06-20~23 rollup) [[nl2sql-flywheel]]
## [2026-06-23] feature | feature-0010-google-drive-integration 토대 신설 — 각 계정이 본인 Google Drive 에 연결하는 멀티테넌트 연동의 인증 구조 + MCP 구성 scaffolding(연동 미수행/기본 비활성). `WebGoogleDriveTokens`(계정별 암호화 OAuth 토큰, cred_crypto AAD=gdrive:{account_id}) + connect/callback/status/disconnect 라우트(flag OFF→404) + bin/gdrive-mcp.sh·docker-compose gdrive-mcp(profile gdrive)·src/gdrive_mcp_seam.py(per-account 토큰 주입 seam A) + .env.oauth/.env config + SECURITY §16 + ARCHITECTURE 기능맵. app.py 인라인(로그인 OAuth·TOTP 선례). Features 카드 신설 + _Index(9→10). [[feature-0010-google-drive-integration]]
## [2026-06-24] update | README §5.1 신설 — SSOT 계약(ADR-0031) 내 wiki 위치 명시: 참조 레이어(전역 sot:false, 예외 Log.md), 동기화=/_dqa:doc_sync(결정론 렌더러 없음 — LLM-persona 유지), 구조 drift=wiki-lint, stale 카드 maturity 라벨 정책. 정본 지도 DOC_REGISTRY 연결. (META-0003 Phase 4) [[../docs/DOC_REGISTRY]]
## [2026-06-24] wiki-ingest | 문서 정합(doc_sync, 06-24 머지 rollup) — `Features/feature-0011-shared-extraction.md` 카드 신설 + `Features/_Index`(10→11) · `overview.md`/`Index.md` 11-feature 정합 + 06-24 서사(메타데이터 거버넌스 ITEM-11 · feature-0010 gdrive 토대 · feature-0011 shared 추출) · `hot.md` refresh(feature-0011·메타데이터 거버넌스 반영, feature-0010 활성화·insight-worker thread 보존) · STATUS 인덱스 feature-0010/0011 행 승격 + 0002/0003/0009 06-24 정합 · ARCHITECTURE 기능맵/의존맵 feature-0011 추가. (META-0009-doc-sync-0624) [[feature-0011-shared-extraction]]
## [2026-06-25] fix | 요청량 한도 도달 메시지 주체 구분 — 서비스 자체 한도(`llm_provider_health` KIND_THROTTLED)에서 provider명(AWS Bedrock) 제거 + "서비스 자체의 요청량 한도" 명시, 계정 당 한도(`app.py _check_account_token_quota`)는 "계정의 … LLM 토큰 사용 한도" 로 명시. 메시지 문구만(분류 kind·HTTP 429·응답 계약 무변경) + 회귀 테스트 1건. (limit-subject-msg, cross-feature: feature-0002 주관 / feature-0003 cross-ref) [[feature-0002-agent-core]]
## [2026-06-25] wiki-ingest | 문서 정합(doc_sync, 06-25 머지 rollup, PR#420~#436) — `Features/feature-0009-group-conversation.md` 카드 06-25 정합(안 읽음/@멘션 배지·메시지 좌우 정렬·owner 멤버 추방/차단 — 마지막 갱신 06-23→06-25) · `overview.md` §2.1 표 11-feature 정합(feature-0010/0011 행 누락 보강) + 06-25 서사(⑦그룹대화 라이브UX 확장·⑧관리콘솔 프롬프트 자동화·⑨shared P5a Step5 완료·⑩안정성) · `hot.md` refresh · STATUS 인덱스 0002/0003/0011 행 06-25 정합(0009 는 cycle 자체 갱신분 유지). 동반: 릴리즈노트 06-25 블록(9항목) + cache-buster bump. (doc-sync-20260625-163929) [[feature-0009-group-conversation]]
## [2026-06-25] wiki-ingest | 문서 정합(doc_sync, 06-25 잔여 머지분 — 직전 sync 163929 의 브랜치 stale 로 누락된 PR#437~#440·#444) — `Features/feature-0009-group-conversation.md` 카드 §2 상태·§3 핵심모델/라이브UX·§7 변경이력 정합(참가자 per-message 제품 선택 REQ-GC-R7·처리 중 composer 비잠금/1:1 인터럽트 재요청/그룹 @assistant 중복차단·발신자 표시 정정) · `overview.md` 06-25 서사 ⑦(per-message 제품·composer 비잠금/인터럽트)·⑩(동시 처리 고착/입력 블로킹 해소·datasource 회로차단 안내 명확화) 보강 · `hot.md` refresh(actionable thread 보존). 동반: STATUS 인덱스 0002(회로차단 안내 분리)·0009(composer 비잠금/인터럽트) 행 정합 + 릴리즈노트 06-25 블록 5항목 추가(9→14) + cache-buster b→c bump. (doc-sync-20260625-192007) [[feature-0009-group-conversation]]
## [2026-06-25] fix | 그룹대화 optimistic 발신자 표시 정정(gc-optimistic-sender-attrib) — 비-owner 참가자가 `@assistant`/채팅 전송 시 처리 중 동안 말풍선이 대화 owner 가 보낸 것처럼(좌측·owner 이름) 표시되다 답변 완료 후 본인으로 복구되던 깜빡임 제거. 근본=optimistic user 메시지 `meta:{}` → `renderMessages` 가 발신자 부재 시 `isOwn`(owner 여부) 폴백. 수정=신규 `_selfSenderMeta()`(현재 사용자 sender_account_id/username)를 optimistic 2지점(_sendGroupChatMessage·sendPrompt)에 부여. frontend display-only(서버 권위 발신자·client meta 미전송 무변경, spoofing 불가). §18.8 적대 패널 SHIP·BLOCKING 0. (gc-optimistic-sender-attrib, 코드 정본 feature-0003) [[feature-0009-group-conversation]]
## [2026-06-26] wiki-ingest | 문서 정합(doc_sync, 06-25 후속 버그픽스 — 릴리즈노트 sync a29a2f0 이후 머지분) — `Features/feature-0009-group-conversation.md` 카드 §7 1줄 append(안 읽음 배지 미감소 최종 근본원인 read-idspace-fix·선행 read 500·읽음 커서 전진 누락·입력창 즉시 클리어 / optimistic 발신자 깜빡임 정정 / 공유 대화 join 불가 AmbiguousParameter / assistant SQL dialect 교정+그룹 발신자 맥락 라벨 feature-0002) · `hot.md` refresh(Recent Changes gc-optimistic "미머지"→"머지" 정정 + 06-25 잔여 delta 1줄 보강 + last_updated 06-26, Active Threads 보존). 동반: STATUS 인덱스 feature-0003/0009 행 정합 + 릴리즈노트 06-25 블록 6항목 추가(14→20) + cache-buster index/admin bump(20260626-rn-0626). overview/_Index/ARCHITECTURE/SECURITY/DECISIONS noChange. (doc-sync-20260626-080501) [[feature-0009-group-conversation]]
## [2026-06-29] wiki-ingest | 문서 정합(doc_sync, 06-26 머지 backfill — 직전 wiki sync c11cc27 @ 08:36 이후 머지된 product-chip(f049fee 12:05)·ask-dedup(0818b0a 13:51·3595ea3 14:00)) — `hot.md` Key Recent Facts/Recent Changes 에 제품 chip 처리 중 항상 활성화(ADR-WEB-0006)·assistant 요청 2번 중복 처리 차단(ask-dedup-idempotency, enqueue 멱등화 + AmbiguousParameter 회귀 격리) 2건 추가 + last_updated 06-29(Active Threads 보존) · `overview.md` 06-26 서사 ⑪제품chip·⑫ask 중복 차단 추가. 동반: STATUS 인덱스 feature-0003 행 ask-dedup 1줄(product-chip 은 f049fee 가 이미 반영) + 릴리즈노트 06-26 블록 ask-dedup 1항목 추가(fixed/work) + cache-buster index/admin bump(20260629-rn-0629). ARCHITECTURE/SECURITY/DECISIONS/feature카드/Index/_Index noChange. ADR-WEB-0006 색인 보류(선별 MOC §2.1, ADR-WEB-0001/0003 도 미색인). (doc-sync-20260629-080501) [[feature-0003-agent-web-ui]]
## [2026-06-29] fix | 관리 콘솔 메타데이터 부트스트랩 MSSQL database 차원 수정 + 패널 잘림 해소(metadata-bootstrap-mssql-db) — "테이블 설명 > 스키마 골격 가져오기"가 MSSQL 데이터소스에서 중립 `tempdb`(shared/db.py `_connect_mssql` 의 보안 기본값) 임시테이블(`#…`)을 노출하던 "테이블 명칭 모두 오류" 근본 수정. 부트스트랩 unit 을 엔진별 분기(MySQL=schema / MSSQL=database via `list_server_databases`, 시스템 DB·스키마·`__invalid_default_db__` 센티넬 필터) + MSSQL 은 선택 DB 로 연결해 비시스템 SQL 스키마 평탄수집(저장 schema_name=database — server>db>schema>table 4계층을 3-키 모델에 매핑, 사용자 결정) + 단건 suggest grounding(`_metadata_introspect_table`) 동일 분기로 정상화 + 프론트 라벨 '데이터베이스/스키마' 분기 + `.admin-meta-bootstrap-result` max-height:460px 제거(pane overflow 와 이중 스크롤이 잘림 원인, 테이블·컬럼 서브뷰 공통). AI 자동완성은 기구현(REQ-20260624-metadata-ai-autocomplete)이었고 깨진 골격에 grounding 해 무력화됐던 것. 라이브 검증(API curl + Playwright eval): MSSQL 129 실 DB·GunzGame 88 실테이블(temp 0)·라벨 '데이터베이스 *'·maxHeight none·suggest grounded. RBAC/스키마/마이그 0. (metadata-bootstrap-mssql-db, REQ-20260629T114221) [[feature-0003-agent-web-ui]]
## [2026-06-29] wiki-ingest | 문서 정합(doc_sync, 06-29 머지 backfill — 직전 wiki sync 6dee739 @ 08:34 이후 feature-0012 머지 PR#456·피드백 고유화·용어사전 자율등록·검토큐 IA 중첩·첨부 id-space) — `Index.md`/`Features/_Index.md`/`overview.md` feature 카운트 11→12(feature-0001~0012) + `_Index`·`overview` §2.1 표에 feature-0012-web-router-modularization 행 + `overview` 2026-06-29 서사(⑬피드백 고유화·⑭용어사전 자율등록+역할분리+유사어·⑮검토큐 IA 중첩·⑯첨부 wrong-bubble id-space 하드닝·⑰feature-0012 토대) + `hot.md` 06-29 갱신(Active Threads 보존) + `Architecture/Overview.md` Feature 수 11→12·기능맵/의존맵 feature-0012 행·06-29 서사 1줄 + `Features/feature-0012-web-router-modularization.md` 카드 머지 reality 정합(status stub→active·maturity stub→minimal·마지막 갱신 06-25→06-29). 동반: STATUS/ARCHITECTURE 인덱스 feature-0012 행 + 0002/0003 피드백·첨부 정합 + 릴리즈노트 06-29 블록 3항목 + cache-buster index/admin bump(20260629b-rn-0629). DECISIONS/SECURITY/PROJECT noChange. (doc-sync-20260629-130501) [[feature-0012-web-router-modularization]]
## [2026-06-29] feature | feature-0013-relationship-diagrams 신규 — assistant 가 flow/관계/구조 질문에 mermaid 다이어그램(ER·flowchart)으로 사용자 DB 구조를 답하도록 3-phase 구현. (L1) 웹 UI mermaid 렌더(vendor v10.9.3 UMD + sanitize-후 라이브DOM `mermaid.render(securityLevel:'strict')` + graceful fallback, DOMPurify 전역완화 불채택) · (L2) `_MERMAID_DIAGRAM_GUIDANCE` 발화 가이던스(get_foreign_keys/describe_table 선조회) · (L3) `table_relationships` 정규화 관계 저장소(alembic 0024 + GRANT) + insight worker FK introspection(구조변경 gate) + knowledge context 관계 digest 주입 · (L4) 대화 중 성공한 execute_sql 의 JOIN 학습(`parse_join_relationships`, source='conversation', conf 0.4). 단위 테스트 17건 PASS·변경 py compile·ruff clean·alembic single-head. 라이브/Windows-browser 검증 미수행. (feature 신규 생성 동반 — 카드+_Index 동반 작성) [[feature-0013-relationship-diagrams]]
