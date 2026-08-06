---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, web, fastapi, rbac, audit]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0003-agent-web-ui
linked_unit: unit/feature-0003-agent-web-ui
created: 2026-05-26
sources:
  - ../../unit/feature-0003-agent-web-ui/docs/FUNCTION.md
  - ../../docs/DECISIONS.md
  - ../../docs/SECURITY.md
---

# Feature — Agent Web UI

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0003-agent-web-ui |
| 상태 | active |
| 정본 | [[../../unit/feature-0003-agent-web-ui/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | FastAPI · 정적 UI · admin console · audit · 첨부 · sandbox · share |

## 1. 개요

사용자가 사용하는 **FastAPI Web UI + 정적 frontend** feature. `/api/ask` 진입점, 관리자 콘솔, audit subsystem (ADR-0019), 첨부 파일 업로드 + MinIO storage + sandbox schema, share link, 비밀번호 reset 등 사용자 facing endpoint 의 정본.

> **2026-06 확장 (§2.5)**: 관리 콘솔이 **데이터소스 CRUD + DB-단위 접근 + 대시보드 위젯/CloudWatch + LLM 사용량 대시보드 + 제품 insight 완료율**까지 포괄하도록 성장. agent 실행은 **ask-worker out-of-process 큐**로 cutover (orphan-on-redeploy 제거). 요청 중단·즉시 재요청, 프롬프트 자동작성 SSE 스트리밍 추가.

> **2026-07-02 확장 (§2.6)**: **AI 운영 관제 패널**(`/api/admin/ai-ops` 신규 admin 화면 + LLM 계측 확장·main agent latency·최근 활동 cursor 페이징) 추가. 감사 화면 정리(카테고리 순서·툴팁·최근활동 상세 확장), 메타데이터(지식베이스) 권한 종속관계 그룹 게이트 계층화, 최근활동 sentinel 대화 링크·첨부 개수 배지 stale 수정.

> **2026-07-03~07 확장 (§2.7)**: **대화 화면 사용자 지정 추론 강도**(낮음/일반/높음/매우 높음, composer '+' 메뉴·대화별 영구 저장) · **데이터소스 상세 평균 연결 응답 시간** · **AI 운영 현황 지연 KPI 재정의**(호출 전체 왕복 → 단계 간 간격) · **말풍선 ☰ 메뉴 통합**(액션 3종+'AI 로 고치기', 피드백 👍/👎만 외부) + share-visibility-window 공유 범위 UI(정본 feature-0009) · **(07-07)** 관리 콘솔 시스템>설정 **런타임 설정**(실행 타임아웃·모델별 추론 예산 조정·저장·live/restart 반영, feature-0018 코드 거주).

> **2026-07-08 확장 (§2.8)**: **메타데이터 콘솔 UX·폴리시** — 검토/검수 큐 행 클릭→우측 read-only 상세 패널(선택 불가 해소)·ENUM 그룹 "+코드 추가" pre-fill·샘플 검수 큐 mermaid 렌더·좌측 목록 가독성 + 디자인 폴리시 5건(필 위계·nesting·배지 accent). **제품 분류 AI 제안 승인 UI**(제품 관리 "✨ AI 분류 제안" 블록·승인/거부, 정본 feature-0016 §59).

> **2026-07-13 확장 (§2.9)**: **첨부 사용자 재업로드 버전 관리**(해시 대조→버전 체인 편입·assistant v1→v2 diff 인지·UI v2 배지+diff 색, Major, cross-cut feature-0002) · 작업화면 제품 드롭업 데이터소스 **'연결 테스트' 버튼**+상단 단발성 토스트(ds-conn-test, Major) · **그래프 뷰 권한 분리**(`metadata.graph.read` 를 '메타데이터 관리'(`kb.ingest.manual`) 묶음에서 독립, Critical §12.3·1회 backfill 로 기존 접근 보존, 정본 SECURITY §19) · **그래프 뷰 렌더러 PixiJS v8 전면 교체**(관리콘솔 그래프뷰 UI 가 본 feature static 에 거주 — AntV G6 v5→PixiJS 팬 60fps·미니맵/BitmapText/hover fx, 정본 feature-0016 §78~81).

> **2026-07-14 확장 (§2.10)**: 작업 화면 **애니메이션 효과 복원 + 인앱 on/off 설정**(anim-effect-pref) · 프로필 **'계정' 탭 세분화**(계정/알림/UI/사용 내역 하위 탭, account-subtabs) · 그래프 뷰 **첫 입장 조작 도움말 팝업**(중간버튼 커서 표식 + mis-position CSS 주석 `*/` hazard 근본수정, graph-entry-help) · 그래프 **제품 카테고리 밴드 우클릭 전용 메뉴**(graph-ctxmenu-category) · 실행 단계 폴링 갱신 시 펼친 **'결과 보기' 스크롤 보존**(세로/가로 layout-timing 0-clamp, step-scroll-preserve) · **그래프 뷰 'AI 능동 분석 실행' 권한 분리**(신규 하위 권한 `metadata.graph.analyze` — 실행=LLM 호출/KB 갱신/비용 유발 특권이라 조회 `metadata.graph.read` 에서 분리·무권한 시 실행 트리거 UI 5곳 미표시·결과 열람은 graph.read 유지, Critical §12.3·A안 최소권한 backfill 없음, 정본 SECURITY §19). 전건 POST-DEPLOY PB-0008 라이브 PASS.

## 2. 상세

### 2.1 책임 경계

- **입력**: HTTP request (`/api/*`), `WebAccounts` 인증, RBAC 권한 검사
- **출력**: JSON 응답 / 정적 자산 / audit row / share link / 첨부 signed URL
- **side-effect**: MySQL mutation (admin 11 / user 5 endpoint) + `WebAuditEvents` row + MinIO PUT / signed URL

### 2.2 주요 endpoint 그룹

| 그룹 | 책임 | audit hook |
|---|---|---|
| `/api/ask` (POST) | LLM agent loop entry — `lazy_create` hint 지원, force_new 분기 | `_audit_user_action("conversation.ask")` |
| `/api/admin/accounts/*` | 계정 CRUD · `password-reset` 1 회용 임시비번 + `MustChangePassword` | `_audit_admin_mutation` Same-tx |
| `/api/admin/roles/*` · `/products/*` · `/system_prompt/*` | RBAC 카탈로그 mutation | `_audit_admin_mutation` |
| `/api/conversations/{cid}/attachments` | 첨부 업로드 (UploadFile multipart) → MinIO put | audit row + R-F4 grant drift health |
| `/api/share/*` · `/api/conversations/{cid}/share` | share link 발급 · anonymous view (ActorType="anonymous") | audit row + share_token_prefix 8 char |
| `/api/delete_conversations` (POST, bulk) | 일괄 삭제 (partial success) | conversation.delete.own gate |
| `/api/history_dates`, `/api/history_anchor` | 메시지 캘린더 점프 | conversation.read.own/.any |
| `/api/admin/health/attachment-grants` | sandbox schema grant drift health (R-F4) | admin only |

### 2.3 핵심 RBAC + audit (ADR-0019)

- 4 신규 권한: `audit.read.own` · `audit.read.any` · `audit.export` · `audit.purge`
- `_audit_admin_mutation` = Same-tx fail-safe (INSERT 실패 → rollback + 500)
- `_audit_user_action` = fail-open (long-running 격리, stderr log)
- prod fail-closed: `AGENT_AUDIT_ENABLED=1` 강제 (dev/test 만 toggle)

### 2.4 frontend state (app.js + `app/` 모듈)

- `state.pendingNewConversation` + `state.pendingSentinel` (unique per lazy-create) → "+ 새 대화" race 차단 (TASK-0082)
- `state.composerAttachments.byConv[pendingSentinel]` — lazy-create staged attachment bucket (TASK-0106)
- pending assistant bubble (spinner + elapsed + step list) — TASK-0061 Phase 1
- Point rail + message calendar — TASK-0061 Phase 4/5
- **실행 단계 side panel** (`#stepSidePanel`) — step 별 **근거(reason) 노출** + SQL + "결과 보기" toggle, stick-to-bottom (TASK-0061/0173~0178)
- **답변 diff 블록** (`enhanceDiffBlocks`) — assistant ```diff 블록을 라인별 +/- 색 렌더 (marked→enhance→DOMPurify, textContent XSS 무첨가) (TASK-0256)
- **전체 N행 미리보기 인라인 표** — "📎 전체 N행 미리보기" 링크를 값-기반 매칭으로 인라인 렌더 + "접기" toggle (TASK-0155/0156/0174)
- **데이터소스 연결상태 3색 배지** — composer 제품 chip + sidebar 가 `connStatusMeta()` 로 정상(초록)/불안정(빨강)/끊김(회색) ●점+라벨 (TASK-0244/0261/0282)
- **프롬프트 자동작성 스트리밍 스크롤** — SSE 토큰 append 시 `atBottom` 판정 후에만 추종 (TASK-0254)
- **도메인 모듈 추출** (2026-08-03~05, 정본 feature-0038) — app.js 가 ES module 오케스트레이터가 되고 도메인이 `static/app/` 6모듈(auth·profile·messages·sidebar·composer·progress)로 byte-동치 이동, **13,216 → 8,082줄**. 사이드바·composer/첨부·메시지·진행표시 계열은 각 모듈로 옮겨졌으나 데이터소스 연결상태 3색 배지(`connStatusMeta`)·스트리밍 스크롤(`atBottom`)·실행 단계 side panel 등은 오케스트레이터에 잔류한다 — AC-3(오케스트레이터 ≤~3,000줄)은 **부분 달성**이고 잔여 지도는 REPORT §2.
- **공유 가변 state 편입** (Phase A) — 모듈 경계를 넘어 재할당되던 `_dqaDrag`·`_sidebarCatchupTimer` 가 `state.dqaDrag`·`state.sidebarCatchupTimer` 로 편입되고, 계약 가드 `tests/verify_state_intake.mjs` 가 bare 식별자 잔존 0 을 고정한다.
- **08-06 신규 static 모듈 2종** — 배경 dismiss 판정 정본 `static/modal-dismiss.js`(작업 화면 `app.js` 트리와 관리 콘솔 `admin.js` 트리 **두 ESM 번들이 공유**. `app.js` 는 import 후 **re-export** 해 `app/sidebar.js` 의 기존 import 를 무회귀로 유지한다) · 첨부 버전 diff 모달 `static/app/attach-diff.js`(`openAttachmentDiffModal`). 전자는 같은 배경-닫기 판정이 9곳에 복제돼 6곳 `click` · 3곳 `mousedown` 으로 갈라져 있던 drift 를 단일화한 것이고, 회귀 잠금은 파일 목록 하드코딩이 아니라 `src/static/**/*.js` 재귀 walk + 표기 변형 무관 detector 다.

### 2.5 관리 콘솔 + 실행 확장 (2026-06)

| 영역 | 내용 | 관련 |
|---|---|---|
| **데이터소스 CRUD** | `/api/admin/datasources` POST/PATCH/DELETE + `/databases` (RO GRANT scope 필터). password envelope 암호화 | [[../concepts/datasource-registry]] · [[../Decisions/ADR-0030-ssrf-guard-toggle]] |
| **DB-단위 접근 UI** | 제품 상세 = 데이터소스 → 접근가능 DB. MSSQL 시스템 DB 고정칩 + 데이터 DB. 참조DB dropdown 폐지 | [[../concepts/db-level-access]] (TASK-0206) |
| **대시보드 위젯화 → CloudWatch** | 카테고리별 위젯 그리드 + per-account 영속(`WebDashboardPreferences`) + 순수 SVG sparkline·auto-refresh·drill-down | TASK-0210/0218 (main 4d688a2) |
| **LLM 사용량 대시보드** | `_record_llm_usage` chokepoint 회계 복구 + 계정/역할별 + SVG 차트(일별 stacked/도넛)·granularity·추정비용·모델 필터칩 | TASK-0163/0165/0166/0198/0202 |
| **제품 insight 완료율** | 제품별 분석완료율% 배지 + per-DB breakdown + DB별 파악내용 한 줄 인라인 | [[../concepts/insight-worker]] (TASK-0223/0242) |
| **ask-worker 큐 cutover** | in-process → `ask_jobs` 큐 + ask-worker 서비스 (web 재배포 중 run 생존) | [[../concepts/ask-worker-queue]] (TASK-0169) |
| **요청 중단 + 즉시 재요청** | 전송버튼 morph(중단), optimistic cancel(fetch abort), run-status 3중 정합 | TASK-0157/0241 (main 6655adc) |
| **프롬프트 자동작성 SSE** | 제품 프롬프트 자동작성 LLM 토큰 스트리밍 (백엔드 SSE + 프런트, stick-to-bottom) | TASK-0233/0254 |
| **권한 편집기 tree + 그룹분리** | RBAC grid 를 종속성 기반 점진적 공개 + 단일열 tree(`data-perm-depth`) + 대화 운영권한 own/any 2그룹 + console.access 마스터게이트 | TASK-0257~0270 |
| **보관 대화 탭** | 삭제=hard-delete 아닌 보관(데이터·첨부 보존, 감사·맥락용), 관리콘솔 보관탭에서 조회 | TASK-0277/0277b |
| **데이터소스 연결상태 3색** | composer·sidebar·picker 가 정상/불안정/끊김 lazy probe(세션캐시+세마포어) | TASK-0244/0246/0261/0282 |
| **답변 diff 블록** | assistant ```diff 라인별 +/- 색 렌더 (app.js/share.js `enhanceDiffBlocks`) | TASK-0256 |
| **첨부 메타 PG cutover** | 첨부 4 테이블 MySQL→PG `core_attachments` (id 권위=MySQL, dual-write fail-soft) | TASK-0279 |
| **제품 아이콘 편집 ✎ 오버레이** | 제품 아이콘 hover 시 편집 오버레이 (PB-0008 PASS) | TASK-0283 |
| **fork = hybrid deep-copy** | pure git-lineage 반려(F1~F6) → `core_messages` deep-copy snapshot | ADR-WEB-0005 (TASK-0170) |
| **진입점 없는 기능 복구** | 즉시답변·공유관리·audit.purge·내활동·facet 등 7개 발굴·구성 | TASK-0158 (DESIGN-entry-points) |

### 2.6 AI 운영 관제 + 감사 UX + 권한 계층화 (2026-07-02)

| 영역 | 내용 | 관련 |
|---|---|---|
| **AI 운영 관제 패널 (신규)** | `/api/admin/ai-ops` — LLM 계측 확장 + AI 운영 현황(관제) admin 화면. main agent latency 계측 | TASK §20 (aiops-panel) |
| **최근 활동 cursor 페이징** | AI 운영 현황 '최근 활동' 더 보기(cursor 페이징) + pane 세로 스크롤 | aiops-activity-paging · aiops-scroll |
| **감사 화면 정리** | 감사 카테고리 순서 재구성 + 항목 툴팁 + 최근활동 클릭 상세 확장 | audit-nav-ux |
| **최근활동 conv 링크 fix** | 최근 활동 시스템 sentinel 대화 링크 깨짐 수정 | aiops-conv-link-fix (feature-0003) |
| **메타데이터 권한 종속관계 계층화** | 메타데이터(지식베이스) 권한 묶음을 그룹 게이트로 계층화 — 종속관계 정합화 | metadata-perm-hier · SECURITY §19 |
| **첨부 개수 배지 stale fix** | "+" 메뉴 첨부 개수 배지가 대화 전환 후 stale 하던 것 수정(scope) | attach-count-scope (work/chat) |

### 2.7 추론 강도 · 관측 KPI · 말풍선 메뉴 · 런타임 설정 (2026-07-03~07)

| 영역 | 내용 | 관련 |
|---|---|---|
| **사용자 지정 추론 강도** | 대화 화면 composer '+' 메뉴 "추론 강도" 4단계(낮음/일반/높음/매우 높음, 끄기 없음)·**대화별 영구 저장**(KV)·비-thinking 모델 비활성. `/api/ask` 가 명시 레벨을 요청 단위 `extra_body.thinking.budget_tokens` 로 override(일반=no-override=alias 기본), litellm_config 무변경. cross-unit(feature-0002 `_call_llm`·`shared/model_catalog`) | TASK-20260706T013532-reasoning-effort (Major) |
| **데이터소스 상세 평균 연결 응답 시간** | 관리 콘솔 데이터소스 상세 "연결 상태" 섹션에 연결 응답 시간(평균, 최근 N회)+순간값+마지막 확인. 표본 없으면 "측정 중". cross-unit(`shared/conn_health`) | TASK-20260703T085511-ds-avg-latency (Major, PB-0008 PASS) |
| **AI 운영 지연 KPI 재정의** | AI 운영 현황 "지연 p95" 를 호출 전체 왕복(생성 포함, 답변 길이 비례) → **추론 단계 간 간격** p50/p95 로 재정의(사용자 기준 정합). activity 상세 latency_ms="왕복" 병기. cross-unit(feature-0002 `agent_core._call_llm` 계측) | aiops-stepgap (TASK-20260703-aiops-ttft-latency, Major) |
| **말풍선 ☰ 메뉴 통합** | 말풍선 액션(샘플 등록·여기서 분기·여기까지/여기부터 공유·'AI 로 고치기')을 kebab ☰ 메뉴로 통합, 피드백 👍/👎만 메뉴 밖 유지. share-visibility-window 공유 범위(여기부터) UI 동반 | [[feature-0009-group-conversation]] (정본, TASK-20260704-share-visibility-window) |
| **런타임 설정 콘솔 (2026-07-07)** | 관리 콘솔 시스템>설정 pane 2 에 assistant 운영 값(실행 타임아웃·MCP 타임아웃·모델별 추론 예산) 조정·저장·live/restart 하이브리드 반영. `WebRuntimeSettings` 테이블 + `routers/admin_settings.py`(GET/PUT/DELETE, `system.runtime.read/write` RBAC+audit, autocommit=False 원자화). resolver 는 env-fallback 으로 배포 `.env` 존중(override 없으면 byte-동치). cross-unit(feature-0018 코드 거주 — `shared/runtime_settings.py`·feature-0002 live 배선) | TASK-20260706T094937-runtime-settings (feature-0018, Major, PB-0008 PASS) |
| **지식베이스 채택 인박스 + ENUM 대화 자율수집 (2026-07-07)** | 대화 후보수집(용어사전+ENUM)을 통합 '채택 인박스'로 재구성 — 용어사전(0021/0023) 대칭 ENUM 코드사전 신설(신뢰도/상태별 그룹 카드·개별/일괄 채택·거부·되돌리기·사이드바 pending 배지), 권한 `kb.enum.curate`. cross-unit(feature-0002 `kb_glossary`·`_enum_autopropose`·`llm_enum_suggest`·alembic 0039 비파괴) | TASK-20260707-kb-candidate-adoption |
| **메타데이터 콘솔 IA 통합 (2026-07-07)** | 채택 인박스·샘플 검수 최상위 탭을 각 사전 하위 {목록\|검토/검수 큐} 2차 보기로 통합(2차 보기 파라미터화 `_METADATA_REVIEW`/`viewBySub`/`_metaSyncViews`) + 5서브뷰 디자인 폴리시(`--surface-2` 토큰·rich empty/skeleton·테이블 카드 그룹핑·폼 grid+인라인검증·SQL 프리뷰·배지 semantic 토큰·이모지 제거+KPI). UI 단독·백엔드/RBAC 정의 0 | TASK-20260707-metadata-console-redesign |
| **추론 강도별 예산 + 런타임 pane 재설계 (2026-07-07)** | 런타임 설정에 모델별 예산과 별개로 추론 강도(낮음/높음/매우 높음)별 `reasoning_budget` 축 추가(cross-unit feature-0002 `_call_llm` 명시레벨 override·'일반'=no-override) + pane UI 정렬 grid + commit-bar 배치 저장(기능 불변) | feature-0018 (d9516aee·a2fe4103) |

### 2.8 메타데이터 콘솔 UX·폴리시 + 제품 분류 승인 UI (2026-07-08)

| 영역 | 내용 | 관련 |
|---|---|---|
| **메타데이터 콘솔 UX 4건** | ① list 컬럼 폭 확대+행 가독성(line-height/padding) ② 검토/검수 큐 후보 행(용어·ENUM feedback·샘플)을 `role=button` 클릭→우측 `#metadataReviewDetail` **read-only 상세**(전체 정의/질문·SQL/다이어그램·신뢰도/scope/status + 승급/거부·승인/거부) — '선택 불가' 근본 해소 ③ ENUM 그룹 카드 "+코드 추가" pre-fill 생성 폼 ④ 샘플 검수 큐 `generated_sql` mermaid 를 공용 `mermaid-render.js`(strict) 다이어그램 렌더. UI 단독·백엔드 0 | TASK-20260708-metadata-console-ux2 (Major) |
| **메타데이터 콘솔 디자인 폴리시 5건** | PB-0008 적대 미적 검증에서 도출 — 2차 보기 필 위계 역전(borderless chip)·list-detail 균형(목록 300~400px)·그룹 카드 nesting divider 평탄화·반복 timestamp 경량+그룹 내 숨김·신뢰도 배지 accent 분리. 순수 CSS+배지 클래스 1개(로직/구조 0) | TASK-20260708-metadata-console-polish (Minor) |
| **제품 분류 AI 제안 승인 UI** | 제품 관리 접근DB 규칙 화면 "✨ AI 분류 제안" 블록 — orphan_pending(RuleId NULL·`ai_suggest:<conf>`) 신뢰도 표기 + 승인(Source='ai')/거부 즉시 실행. 승인 경로 `admin_products` ai-suggestions/approve·/reject(감사·이름/제외DB 검증 미러). 정본=feature-0016 §59/ADR-025 (분류 엔진 코드 거주 feature-0002) | TASK §59 (product-classify-suggest) |

## 3. 특징

- **API Vault 폐기** (ADR-0026) — per-user OpenAI key 입력 제거 → Bedrock gateway 단일 진입
- **첨부 sandbox** (ADR-0023) — `attachment_writer/reader/maintainer/cleanup` 4 MySQL user + schema 별 grant
- **TASK-0094 multi-cycle 의 hub** — Sprint 1 (MinIO + sandbox), Sprint 2 (vision), Sprint 4 (D RAG, 예정)
- **admin password reset** (TASK-0061 Phase 6, Critical §12.3) — 16 자 1 회용 임시비번 + `MustChangePassword` 강제
- **stale_error 판정** (TASK-0061 Phase 3) — `processing` 상태가 `WEB_PROGRESS_STALE_TIMEOUT_SECONDS` (기본 1200 초) 초과 시 stale 라벨
- **standalone mjs 하네스 계약** (2026-08-05, harness-repair — tests-only·제품 코드 변경 0) — `tests/verify_*.mjs` red 23건을 전건 수리해 **40/40 green**(단언은 현행 계약으로 갱신하되 검증 취지 보존). 신설 2건: `esm-classic-inject.mjs`(ESM 전환 이후 jsdom classic 주입용 import/export strip — 미커버 형태는 SyntaxError 로 fail-loud) · `verify_notify_gating.mjs`(알림 게이팅 매트릭스 — 구 시나리오 A 블록 이관). `win-browser-settings-notif.scenario.json` 은 죽은 page-전역 의존을 DOM 이벤트 경유로 전환(실 Windows Chrome 20스텝 OK). **mjs 40개가 `make test` 밖이라는 CI 비배선 구조는 잔존.** 정본 FUNCTION `(harness-repair)` · TEST `20260805T1042`.
- **분석문 판정 배지** (2026-08-05, 정본 feature-0036) — 그래프 뷰 노드 상세 'AI 능동 분석' 박스의 판정 배지 + `판정 근거` 한 줄이 본 feature static(`graph/graph-ctxmenu.js` · `admin.html` 범례)에 거주한다. 미판정·판정 실패·해시 불일치는 전부 미표시로 수렴. 정적 자산이 web 이미지에 baked 되므로 시각 검증은 배포 후 수행 — PB-0008 라이브 4항목 PASS(TASK-20260805T192000).
- **첨부 수명주기 개방 — 삭제(버전 선택)·복구(휴지통)·일괄 다운로드** (2026-08-06, attach-manage — **Critical §12.3**: 파괴적 데이터 삭제 + 인가 경계 변경, PLAN-APPROVED) — 목록 행 🗑 가 버전이 여럿이면 "이 버전만 / 전체 버전" 을 고르게 하고(기본은 항상 좁은 쪽 `version`), soft-delete(`DeletePending=1`) 후 retention(`ATTACHMENT_RECON_RETENTION_DAYS`, 기본 30일) 창 안에서 패널 헤더 휴지통 토글로 되살린다. 실 객체 삭제는 기존 reconciliation worker 소관. **삭제 인가를 열람 경계에서 분리**한 것이 핵심 — 종전 `_account_can_access_attachment` 는 그룹 멤버 전원을 통과시켜 제3자가 남의 첨부를 지울 수 있었고(선행 `REQ-20260729-attach-append-only` 가 이월한 미해결 이슈), 이제 삭제·복구는 `conversation.attachment.upload.any` 또는 `upload.own` + (업로더 본인 ∨ 대화 소유자)이며 두 핸들러가 열람 헬퍼를 **호출하지 않음을 AST 로 단정**한다(열람 경계 자체는 종전대로 멤버 전원). 최신 버전 삭제 시 `VersionNumber` 최대값을 승격(`SupersededAt=NULL`)해 체인이 통째로 사라지지 않게 하고, ZIP 일괄 다운로드는 상한 초과 시 **부분 ZIP 없이 413**(무음 절단 금지·상한 검사가 ZIP 생성보다 먼저) · zip-slip 제거 · 이름 충돌 시 id 부여이며, 개별 모드는 presigned MinIO URL 이 내부 endpoint 호스트라 외부 브라우저가 못 여는 문제로 앱-내부 URL manifest 를 준다. `ADR-20260729T163000-attach-append-only` 를 supersede(사용자 승인 2026-08-06). 정본 FUNCTION `REQ-20260806-attach-manage` · TASK `20260806T1541-attach-manage`.
- **첨부 버전 diff 비교 화면 — 임의 쌍·다단계** (2026-08-06~07, attach-version-diff + 후속 5 cycle, Major §12.3 — 신규 권한·스키마·마이그레이션 0) — 버전 체인(`RootAttachmentId`/`VersionNumber`/`SupersededAt`)과 체인 조회는 이미 있었지만 **비교 그 자체**가 없었다: `MetaJson.version_diff` 는 업로드 시점의 직전↔신규 1쌍만 담고(LLM 컨텍스트 주입용) 프론트 diff 렌더 코드가 0 이라 v1↔v3 같은 다단계 비교는 데이터로도 화면으로도 불가능했다. `GET /api/attachments/{attachment_id}/diff` + 전용 모달(`static/app/attach-diff.js`, 좌우 2열/단일열 토글)을 신설하고 후속 cycle 이 열 폭 `<colgroup>` 정본화 · 모달 확대·줄번호 여백·중앙선 드래그·gap 국소 전개 · 높이 고정→**상한** · 상호작용 스크롤 보존·문단 단위 하이라이트를 얹었다. 마지막 `attach-diff-unified-bg` 는 **자기 회귀 수정** — 줄 배경 규칙을 `.has-content` 로 좁힐 때 `_renderSplit` 에만 클래스를 부여해 단일열의 내용 있는 추가/삭제 줄이 전부 중립 filler 를 받았고(색 소실보다 나쁘게 **의미가 반대로 뒤집힘**) 자동 44축 전건 PASS 인 채 배포됐다. 재발 클래스("렌더러가 둘인데 규칙을 한쪽만 따름")를 헤드리스 B9/B9b + mjs A1d 정적 대칭 가드로 잠갔다. 정본 FUNCTION `(attach-version-diff, 2026-08-06)` ~ `(attach-diff-unified-bg, 2026-08-07)` · TASK `20260806T2320` · `20260807T0030/T0200/T0320/T0430/T0620`.
- **폴더 단위 첨부 · 중복 스킵 UX · 편집본 버전 체인 통합** (2026-08-06, attach-multi-upload, Major §12.3) — 사용자 보고("내용이 다른데 '동일한 파일' 로 블로킹")를 실측한 결과 **dedup 판정 자체는 정확**했고(로컬 22개 sha256 전량 일치·mtime 만 갱신) 결함은 그 주변이었다: `#attachFileInput` 에 `multiple` 부재 · change 핸들러가 `files[0]` 만 처리 · `.composer-wrap` drop 이 `#chatPane` **자손**이라 같은 drop 이 버블링돼 첫 파일이 2회 업로드되고 두 번째가 dedup 에 걸리는 **오탐 토스트** · 중복 스킵을 빨간 에러 토스트로 알려 "차단당했다" 로 읽힘 · assistant 편집본이 `<원본>_v<n>` 이라는 다른 파일명으로 저장돼 체인 스코프 `(ConversationId, AccountId, OriginalFilename)` 가 갈리며 한 논리 파일이 **두 체인으로 분열**(라이브 실측 9쌍). 전량 순차 업로드 + 배치 요약 1회(정보 톤 "이미 최신입니다(내용 동일) — 건너뜀") + drop 위임 + 편집본 파일명 **원본 승계**(LLM filename 무시 → 실행파일류 확장자 승격이 정의상 불가능해져 SEC-1 강화)로 해소하고, 버전 구분은 표시 계층(`_v{n}`)에만 둔다. 선행 `REQ-20260713-attach-user-version` 의 해시 대조 판정(AC-AUV-1·2)은 **불변**. 정본 FUNCTION `REQ-20260806-attach-multi-upload` · TASK `20260806T1820-attach-multi-upload`.
- **공유 링크 발화자 배지 = 메시지별 발신자** (2026-08-06, share-sender-nickname, Major §12.3 — 표시 계층 + payload 불리언 1개, RBAC·스키마 무변경) — `share.js renderMessage()` 가 배지를 `roleLabel(msg.role)` 로만 채워 user 가 전원 '사용자' 로 고정돼 그룹 대화를 공유하면 누가 무엇을 말했는지 구분할 수 없었다. 라이브 익명 호출 실측에서 `meta.sender_username`/`sender_account_id` 가 **이미 payload 에 실려 나오고 있음**을 확인해(백엔드 변경 불요) `senderLabel(msg)` 4단 폴백(닉네임 → `사용자 <id>` → 대화 소유자명 → `사용자`)으로 말풍선 배지·point rail 툴팁/aria 를 단일 출처로 통일했다. §18.8 적대 패널(security·ux) CONCERN 5건 전건 흡수 — **사후 추론 각인(`attribution_inferred`)은 확정 라벨로 렌더하지 않고**(fork 본 공유 시 원본 대화 owner 이름이 익명 화면에 등장하던 경로 차단) 소유자명 폴백은 **1:1 확인 시에만** 허용한다(그룹 legacy 행 오귀속 — payload `conversation.is_group` 불리언 1개 + fail-closed 게이트). 노출 집합 서술 정본은 `docs/SECURITY.md §21.7`. 정본 FUNCTION `(share-sender-nickname, 2026-08-06)` · TASK `20260806T0327-share-sender-nickname`.
- **배경 dismiss = 저장소 단일 primitive** (2026-08-06, modal-backdrop-dismiss → modal-dismiss-siblings, Minor §12.3 frontend-only) — DOM `click` 의 target 은 mousedown/mouseup 두 지점의 **공통 조상**이라 패널 안에서 누르고 배경에서 떼거나(지침 textarea 드래그 선택) 그 반대여도 target 이 backdrop 으로 **승격**돼 모달이 닫혔다 — 사용자 관점에선 "down 만 해도 / up 만 해도 종료". 판정을 `pointerdown`+`pointerup` **2단 계약**(두 이벤트 target 이 모두 backdrop 자신)으로 옮기고 실행은 `click` 단계에서 해 backdrop 이 그 click 을 소비하게 하며(ghost click 차단), 터치·펜의 implicit pointer capture 는 배경에서 시작한 제스처에 한해 해제한다. 이어 같은 판정이 9곳에 흩어져 6곳 `click` · 3곳 `mousedown` 으로 굳어 있던 것을 `static/modal-dismiss.js` 정본으로 통일했다 — ESM 번들이 작업 화면/관리 콘솔 **둘**이라 primitive 를 `app.js` 에 두면 admin 쪽 복제가 불가피하고 **그 복제가 애초에 이 결함을 만든 기전**이다. 정본 FUNCTION `(modal-backdrop-dismiss, 2026-08-06)` · `(modal-dismiss-siblings, 2026-08-06)` · TASK `20260806T1144` · `20260806T1830`.

## 4. 사용법

```bash
make start            # web + agent + caddy + mysql ...
make web              # web 만
curl http://localhost:18080/admin    # dev — override (TASK-0057)
```

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0002-agent-core]] — `/api/ask` 가 agent loop import
- [[feature-0006-lan-proxy-access]] — `_get_client_ip()` 가 Caddy `trust_forwarded_for` 정합 의존
- [[feature-0007-bedrock-llm-provider]] — LLM env 단일 진입

## 6. 관련 정본

- [[../../unit/feature-0003-agent-web-ui/docs/FUNCTION|FUNCTION.md]] (정본)
- [[../../unit/feature-0003-agent-web-ui/docs/DESIGN|DESIGN.md]] — admin console UI 정본
- [[../../unit/feature-0003-agent-web-ui/docs/DESIGN-ask-worker|DESIGN-ask-worker.md]] — ask-worker 큐 설계
- [[../../unit/feature-0003-agent-web-ui/docs/DESIGN-fork-reference|DESIGN-fork-reference.md]] — fork hybrid (ADR-WEB-0005)
- [[../../unit/feature-0003-agent-web-ui/docs/DESIGN-entry-points|DESIGN-entry-points.md]] — 진입점 복구
- [[../../unit/feature-0003-agent-web-ui/docs/DECISIONS|DECISIONS.md]] (ADR-WEB-*)
- [[../../unit/feature-0003-agent-web-ui/docs/TASK|TASK.md]]
- [[../../docs/SECURITY|docs/SECURITY.md]] — audit / X-Forwarded-For trust 정책 정본

## 7. 관련 노트

- [[../Architecture/Data-Flow]] — 요청 흐름 + audit 흐름
- [[../concepts/ask-worker-queue]] · [[../concepts/datasource-registry]] · [[../concepts/db-level-access]] · [[../concepts/insight-worker]]
- [[../Decisions/ADR-0019-web-audit-events]]
- [[../Decisions/ADR-0022-minio-attachment-storage]]
- [[../Decisions/ADR-0023-sandbox-schema-mysql-users]]
- [[../Decisions/ADR-0026-bedrock-llm-provider]]
- [[../Decisions/ADR-0030-ssrf-guard-toggle]] — datasource 보안 경계 토글

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0002-agent-core]] · [[feature-0006-lan-proxy-access]] · [[feature-0007-bedrock-llm-provider]] · [[feature-0008-windows-browser-testing]]

## 9. 외부 link

- [FastAPI — UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/)
- [python-multipart](https://github.com/Kludex/python-multipart)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/substantial` · `#domain/web` · `#domain/rbac` · `#domain/audit`
