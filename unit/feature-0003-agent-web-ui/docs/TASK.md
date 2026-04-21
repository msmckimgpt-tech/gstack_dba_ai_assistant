---
doc_type: TASK
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: completed
- Owner: AI
- Priority: high
- Last Updated: 2026-04-21

## 2. Task Queue
- [x] TASK-0001 Web UI 코드 이관
- [x] TASK-0002 정적 자산 이관
- [x] TASK-0003 agent 이미지 복사 경로 반영
- [x] TASK-0004 엄격한 Web UI 검증 시나리오 정의
- [x] TASK-0005 모던 UI/UX 전면 리디자인
- [x] TASK-0006 기존 사용자 식별 UI 추가
- [x] TASK-0007 키워드 학습 구조 추가
- [x] TASK-0008 로그인 버튼 브라우저 호환성 버그 수정
- [x] TASK-0009 작업 중심 콘솔 UI 재개편
- [x] TASK-0010 계정/비밀번호 기반 인증 모델 도입
- [x] TASK-0011 pending/operator/admin 권한 체계와 관리자 화면 도입
- [x] TASK-0012 대화 소유권을 계정 기준으로 전환
- [x] TASK-0013 상단 상태/키워드 관리/시간 이동 등 불필요한 UI 제거
- [x] TASK-0014 로컬 LLM false-ready 방지
- [x] TASK-0015 성공 사례 기반 UI/UX 전면 개편 (App-Shell 레이아웃)
- [x] TASK-0016 AI 작업자용 UI/UX 정책 지침 문서화
- [x] TASK-0017 프로필 드로어, 병렬 대화 지원, Admin 콘솔 개편
- [x] TASK-0018 프로필 드로어 탭 구조화, API Vault 통합, 버그 수정, 탑바 정리
- [x] TASK-0019 로컬 LLM 런타임 복구 및 alias 모델 준비
- [x] TASK-0020 내장 Local LLM 제거 및 외부 provider 참조 전환
- [x] TASK-0021 쿼리 결과셋 인라인 표시 복원
- [x] TASK-0022 Progress Strip 드롭다운 구조화 (단계 누적에 따른 채팅 영역 축소 해소)
- [x] TASK-0023 Planner 자율성 개선 (휴리스틱 없이 불필요 탐색 축소)
- [x] TASK-0024 Role/권한 구조를 RBAC + account override 모델로 재설계
- [x] TASK-0025 SQL 결과셋 Navigator(말풍선 내 스텝 탐색) 도입
- [x] TASK-0026 긴 SQL 쿼리 수평 확장 방지 (SQL 포매팅 + wrap)
- [x] TASK-0027 RBAC 세분화 반영 — Profile 권한 그룹화 + 관리 콘솔 UX 재설계
- [x] TASK-0028 Insight 시스템 및 agent-core 내부 설계 문서화
- [x] TASK-0029 관리 콘솔 재구조화 (탭 + 마스터-디테일 + 일괄 commit)

## 3. In Progress
- 없음

### TASK-0029 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  1. OVERVIEW / ACCOUNTS / ROLES 3개 섹션이 한 화면에 스택되어 있어 ([admin.html:22-111](../src/static/admin.html#L22-L111)) 현황을 한눈에 파악하기 어렵다.
  2. 페이지 좌우 여백 때문에 정보 표현 공간이 낭비된다. (채팅 "작업 화면"은 `100vw` app-shell 레이아웃을 쓰는 반면, admin은 좁은 surface-card 3개를 세로로 쌓은 구조)
  3. ACCOUNTS 섹션의 `#adminSearch`("사용자 ID 검색…") 플레이스홀더를 보고 ROLES 요소를 찾으려다 실패하는 사용자 동선이 확인됨. 한 화면에 두 섹션이 동시에 보여 검색 범위에 대한 혼동을 유발.
  4. 각 계정/역할이 모든 필드를 펼친 채로 나열되어 있어 목록 탐색이 어렵다. 요약 라인 + 클릭 시 상세 펼침이 필요.
  5. 계정 "관리"는 **일괄 작업**이 전제되어야 한다. (여러 계정에 권한 추가/수정/제거, 일괄 삭제 등)
  6. **크리티컬 버그**: 여러 계정을 동시에 수정한 뒤 특정 계정 하나에서 "저장" 누르면 나머지 계정의 pending 변경사항이 모두 소실됨. 원인: [admin.js:463-483](../src/static/admin.js#L463-L483)에서 저장 성공 후 `loadAdminData()`가 전체 DOM을 re-render하면서 다른 form의 pending edit가 지워진다. 역할 편집도 동일 패턴([admin.js:641-662](../src/static/admin.js#L641-L662)). AWS IAM 콘솔처럼 **pending changes 누적 + 일괄 commit** 구조로 전환 필요.
  7. Admin 화면이 "작업 화면"과 구성/레이아웃이 달라 위화감이 있다.
- 목표:
  - 관리 콘솔을 **탭 기반 네비게이션** + **마스터-디테일 리스트** + **AWS 스타일 일괄 commit 바** 구조로 전환.
  - 여러 계정/역할을 동시에 수정해도 각각의 pending 상태가 유지되며, 화면 하단의 "변경사항 N건 · 적용 / 취소" 바에서 일괄 커밋.
  - 채팅 작업 화면의 `app-shell` 스타일(전폭 + 좌측 사이드 + 상단 topbar)과 톤을 맞춘다.
- 접근:
  1. **레이아웃 재구성 (admin.html)**:
     - 현재 `<main class="admin-main admin-section-stack">` 3 section 스택 구조를 제거하고, 채팅 `app-shell`과 유사한 3영역 레이아웃으로 전환:
       ```
       <body class="admin-shell">
         <header class="topbar"> (브랜드 / 탭 네비 / 로그아웃)
         <aside class="admin-sidebar"> (대시보드 / 계정 / 역할 탭 버튼, 각 탭에 배지: 계정 N, 역할 M, pending 변경 K)
         <main class="admin-workspace"> (선택된 탭의 패널만 표시)
         <footer class="admin-commit-bar"> (pending 변경 N건 · 취소 · 모두 적용)
       ```
     - 각 탭 패널은 `<section data-admin-pane="dashboard|accounts|roles">`로 구성하고 비활성 탭은 `display:none`.
  2. **대시보드 탭 (신규)**:
     - 현재 4개 metric card(Active/Inactive/Deleted/Roles)를 유지하되 카드를 더 크게 배치하고 보조 정보 추가:
       - 최근 7일 로그인한 계정 수
       - 권한이 할당된 역할 수 / 전체 역할 수
       - pending 변경사항 미리보기 리스트 (있을 때만)
     - 전폭을 활용해 grid-template-columns를 반응형으로 (`repeat(auto-fit, minmax(220px, 1fr))`).
  3. **계정 탭 — 마스터/디테일 구조**:
     - 레이아웃: 좌측 account list (username, role, 상태 뱃지, pending 마크) + 우측 detail pane (선택된 계정의 편집 폼).
     - 리스트 각 row: checkbox + username + role 이름 + 상태 chip + pending 표시(`•`). 클릭 시 detail pane에 해당 계정 로드.
     - 리스트 상단 툴바: **scoped search** ("계정/사용자 검색…"으로 플레이스홀더 변경), 상태 필터(전체/활성/비활성/삭제), 선택된 row 수 + 일괄 액션 드롭다운(활성화/비활성화/삭제/역할 변경/권한 추가/권한 제거).
     - detail pane: 기존 per-form submit 제거. form의 value change event → `adminState.pending.accounts.set(id, patch)` 에 기록만 하고 서버 호출 없음. 저장 버튼은 detail pane 내부에 "이 변경을 pending에 추가" 같은 로컬 확정 버튼으로 둔다(혹은 inputs 가 변하면 자동으로 pending 에 들어가는 방식, 이쪽이 더 AWS 스타일).
     - pending patch가 있는 계정은 리스트/detail 모두에서 `•` 마커로 표시.
  4. **역할 탭 — 마스터/디테일 구조**:
     - 동일 패턴. 리스트(role name + key + 멤버 수 + 활성 뱃지 + pending 마크) + detail pane(name/description/permission grid/활성/기본 가입).
     - 역할 생성 폼은 리스트 상단 "+ 새 역할" 버튼 → detail pane에 빈 폼 로드 (별도 페이지/모달 없이 동일 pane 재사용).
     - 역할 일괄 작업: 선택된 역할들을 활성/비활성 토글, 삭제.
  5. **Pending / Commit 상태 모델 (admin.js)**:
     ```js
     adminState.pending = {
       accounts: new Map(),  // id -> { role_id?, is_active?, permission_overrides?, _delete?: true }
       roles: new Map(),     // id -> { name?, description?, is_active?, is_default_signup?, permission_codes?, _delete?: true, _create?: { role_key, ... } }
       createRoles: [],      // 임시 생성한 역할들 (tempId 관리)
     };
     ```
     - `adminState.pending`의 변경마다 commit bar 카운트/내용 업데이트.
     - commit bar `모두 적용`: pending의 각 entry에 대해 PATCH/DELETE/POST 순차 호출(또는 `Promise.all`, 에러 시 실패한 항목만 pending에 남김). 전체 완료 후 `loadAdminData()` 1회.
     - commit bar `취소`: `pending`을 비우고 detail pane 을 현재 서버 값으로 다시 렌더.
     - **핵심**: `loadAdminData()` 는 "모두 적용" 이후에만 호출. 단일 저장으로 전체 DOM 초기화 경로를 제거한다.
  6. **Per-tab scoped search**:
     - `#adminSearch`를 제거하고, 각 탭 리스트 상단에 전용 search input을 배치. 계정 탭: "username 검색", 역할 탭: "역할 이름/키 검색". 대시보드 탭: 검색 없음.
  7. **bulk 작업**:
     - 리스트 row 체크박스 + 헤더 "전체 선택" 체크박스. 선택된 row 수가 1 이상이면 일괄 액션 바 노출.
     - 일괄 액션은 즉시 API 호출하지 않고 pending에 반영(동일 모델).
     - 일괄 권한 추가/제거: 모달 대신 선택 후 드롭다운 → 권한 코드 선택 → 선택된 모든 계정의 `permission_overrides[code]` 를 allow/deny/inherit 로 일괄 세팅.
  8. **CSS (styles.css 추가/수정)**:
     - `.admin-shell` grid: `grid-template-columns: 240px 1fr; grid-template-rows: 60px 1fr 56px;` (topbar + sidebar + main + commit-bar).
     - `.admin-sidebar`: 탭 버튼, 각 버튼에 pending 배지 (`.tab-badge`).
     - `.admin-workspace`: 패널 컨테이너, 전폭 활용.
     - `.admin-list-detail`: `grid-template-columns: minmax(260px, 360px) 1fr; gap: 16px;` — 좌측 리스트 + 우측 디테일.
     - `.admin-list-row`: 선택 상태(`.is-active`), pending 상태(`.has-pending`) 표시.
     - `.admin-commit-bar`: `position: sticky; bottom: 0; background: ...; box-shadow: top;` — 변경사항 N건 · 취소 / 모두 적용.
     - 반응형: viewport width 1024px 미만이면 `.admin-list-detail` 가 1열로 스택, 리스트 클릭 시 detail pane 이 리스트 위로 올라오는 모바일 친화 모드.
- 범위 제한:
  - 백엔드 API 변경 없음. 기존 PATCH/DELETE/POST 엔드포인트 그대로 사용.
  - 실제 서버 호출 시점만 변경(개별 → 일괄).
  - 권한 정의(33개 permission, 그룹 라벨)와 `renderPermissionGrid()` 자체는 기존 그대로 재사용 (detail pane 안에서만 호출).
  - 로컬 LLM, chat UI 쪽은 수정하지 않는다.
- 검증 기준:
  1. 관리자 계정 로그인 → `/admin` → 좌측 사이드바에 "대시보드 / 계정 / 역할" 탭 버튼이 보이고, 초기 표시는 대시보드.
  2. 계정 탭 클릭 → 리스트/디테일 2분할 레이아웃. 리스트 검색 플레이스홀더가 "사용자 검색…" 등 계정 전용 문구.
  3. **다중 편집 보존 시나리오**: 계정 A 선택 → role 변경 → 계정 B 선택 → permission override 변경 → 계정 C 선택 → is_active 토글. 하단 commit bar가 "변경사항 3건"을 표시. 계정 A 다시 선택 시 role 변경이 그대로 유지. "모두 적용" 클릭 후 서버 반영 확인.
  4. "취소" 클릭 시 pending 이 비워지고 detail pane 이 서버 값으로 복원된다.
  5. 일괄 선택 시나리오: 계정 3개 체크 → 일괄 비활성화 → commit bar 변경사항 3건 → 적용.
  6. 역할 탭에서도 동일한 pending/commit 모델 동작.
  7. 페이지 좌우 여백이 chat 작업 화면 수준으로 확장되어 있고 (full viewport width), topbar/sidebar 톤이 chat `app-shell` 과 맞춰져 있다.
  8. 브라우저 자동화 스크립트로 위 6번까지 시나리오를 재현해 증빙한다.

### TASK-0027 상세 설계
- 문제:
  - 다른 AI 작업자가 RBAC 권한을 33개(5그룹: console/account/role/conversation + misc)로 세분화했으나, Profile 드로어의 권한 현황 영역은 `buildPermissionPills()`([app.js:326-345](../src/static/app.js#L326-L345))이 활성 권한을 **알파벳순 플랫 리스트**로 렌더링하기만 해서 한눈에 파악 불가.
  - 관리 콘솔의 계정 편집은 `renderPermissionGrid(..., mode="override")`([admin.js:84-146](../src/static/admin.js#L84-L146))에서 33개 permission 각각이 inherit/allow/deny select dropdown으로 렌더링되어 계정 1건당 33개 select가 쌓이고, 페이지당 10개 계정이 나오면 330개 select가 한 화면에 쌓여 실사용 불가 수준이 됨.
  - 역할 편집 권한 그리드([admin.js:384-559](../src/static/admin.js#L384-L559))는 그룹화는 되어 있으나 접기/펼치기가 없어 역할 1건당 5개 그룹 33개 체크박스가 전부 펼쳐져 스크롤 지옥.
- 목표:
  - Profile 드로어: 활성 권한을 그룹(console/account/role/conversation)별로 묶어 섹션 헤더 + pill chip으로 렌더. 그룹 내 권한이 없으면 그룹 자체 숨김.
  - 관리 콘솔 계정 override: `<details>`/`<summary>` 기반 collapsible 그룹으로 전환. summary에 `그룹명 · (N allowed / M denied / 나머지 inherit)` 상태 배지를 표시해 접힌 상태에서도 override 현황이 보이게 함. 기본 접힘.
  - 역할 편집 권한 그리드: 동일한 collapsible 그룹 구조. summary에 `그룹명 · (N/M 선택됨)` 카운트. 기본 접힘(단 선택된 항목이 있는 그룹은 열림).
  - 각 그룹에 "모두 허용 / 모두 거부 / 모두 상속" 배치 액션 버튼(권한 있을 때만). 일괄 조작 가능.
- 접근:
  - `PERMISSION_LABELS`에 그룹 라벨 맵 추가 (`console` → "관리 콘솔", `account` → "계정", `role` → "역할", `conversation` → "대화", `misc` → "기타").
  - app.js `buildPermissionPills()`를 `buildPermissionSections()`로 재작성. 입력: `state.user.permissions` + 서버가 반환한 permission 정의(그룹 정보 포함). 없으면 코드의 앞쪽 토큰(`console.*`, `account.*` 등)으로 폴백 그룹화.
  - admin.js의 `renderPermissionGrid()`에 `collapsible: true` 옵션 추가. 각 그룹을 `<details>`로 감싸고 summary에 실시간 카운트 배지. 배치 액션 버튼 포함.
  - CSS: `.permission-section`, `.permission-section-head`, `.permission-section-counts`, `.permission-bulk-actions` 스타일 추가. 기존 `.permission-group*`/`.permission-grid*` 스타일은 유지하고 `<details>` 내부에서 재사용.
- 검증 기준:
  - Profile 드로어에서 활성 권한이 그룹별 헤더 아래로 묶여 표시된다.
  - 관리 콘솔 계정 1건을 펼쳤을 때 override 섹션이 기본 접힘 상태로 보이고, summary에 그룹별 allow/deny 카운트가 표시된다.
  - 역할 편집 그리드도 동일한 collapsible 그룹 구조로 동작한다.
  - 배치 액션 버튼(모두 허용/거부/상속)이 동일 그룹 내 모든 select/checkbox에 반영된다.
  - 권한이 없는 사용자는 액션 버튼/체크박스가 disabled로 표시된다.
  - 브라우저 자동화로 admin.html을 열어 section 개수, collapsed 상태, 카운트 정확성을 확인한다.

### TASK-0028 상세 설계
- 문제:
  - Insights(스키마/테이블 메타데이터 자동 분석) 기능이 `insight.py`에 660줄로 구현되어 있으나 **어느 문서에도 명시되어 있지 않음**. 사용자 입장에서는 백그라운드 worker가 돌고 있는 것을 "서비스 오류"로 오해함.
  - Insights 외에도 코드에만 있고 문서에 없는 주요 기능들: SYSTEM_PROMPT 설계 의도, TOOL_DEFINITIONS 우선순위 근거, Step Loop/Timeout/Cancel 메커니즘, Knowledge Injection(KNOWN SCHEMAS 자동 주입), CSV 저장(preview_table + csv_paths 2단계 반환), Fingerprint 변경 감지, Advisory Lock 등.
- 목표:
  - feature-0002-agent-core 문서를 "코드만 보면 알 수 없는 기능/설계 의도"가 모두 드러나도록 보강.
  - 신규 문서 2종 추가 + 기존 FUNCTION.md 확장.
  - 각 기능이 "어디서 왜 이렇게 동작하는지"를 실제 코드 경로/줄 번호와 함께 설명.
  - 검증: 문서를 작성하면서 실제 insight worker가 현재 런타임에서 정상 동작하는지(heartbeat, last_cycle_at, last_status) MEMORY DB로 직접 확인.
- 접근:
  1. **`docs/INSIGHTS.md` 신규 작성**: Insight 시스템 아키텍처 전용 문서.
     - 목적과 사용자 영향 (질의 응답 품질 향상 / 탐색 단계 감소)
     - 3단계 데이터 생성: bootstrap → instance scan → on-demand refresh
     - Worker 구조: `run_insight_worker_loop()` → `run_insight_cycle()` → `_bootstrap_schema_insights()` + `_scan_instance_schema_insights()`
     - Fingerprint 변경 감지 (`_compute_schema_fingerprint`, `_compute_table_fingerprint`, batch 최적화)
     - Advisory Lock (MySQL GET_LOCK 기반, `AGENT_INSIGHT_WORKER_LOCK_NAME`)
     - Heartbeat & Stale 감지 (`_is_insight_worker_heartbeat_fresh` + `AGENT_INSIGHT_WORKER_STALE_SEC`)
     - Inline fallback (`_should_run_inline_insight_scan`, worker 부재 시 ask 시점에 인라인 실행)
     - 메모리 DB 저장 키(`schema_insight:*`, `table_insight:*`, `insight_worker_last_*`)
     - 환경변수 표 (`AGENT_SCHEMA_INSIGHT`, `AGENT_INSIGHT_WORKER_*`, `AGENT_INLINE_INSIGHT_ON_ASK` 등)
     - "오류 아님 신호" 표 — 사용자/운영자가 "이건 오류 같다"고 오해하기 쉬운 로그 라인과 실제 의미.
     - 헬스 체크 SQL snippet (worker heartbeat, last_status, last_error 조회용)
  2. **`docs/AGENT_CORE_INTERNALS.md` 신규 작성**: agent_core + 주변 모듈의 숨은 계약 문서.
     - SYSTEM_PROMPT 구조 설명: CRITICAL DIRECTIVE → CORE RULES → STRATEGY → IDEAL FLOW → ANTI-PATTERNS → SQL PATTERNS → OUTPUT (코드 파일/줄 참조)
     - TOOL_DEFINITIONS 우선순위: execute_sql 최우선 배치 근거 (LRN-20260416-0001와 연결)
     - Knowledge Injection 흐름: `_build_knowledge_context()` → KNOWN SCHEMAS + RELEVANT TABLES 자동 주입
     - Step Loop & Budget: max_steps, timeout, finalize_now 신호, cancel 요청
     - CSV 저장 2단계: preview_table(LLM에 전달, 기본 5행) + csv_paths(전체 결과, 별도 파일)
     - Planner fast path (`_build_insight_object_fast_plan`): 인사이트 기반 빠른 실행 계획 (있을 때)
  3. **`docs/FUNCTION.md` 보강**:
     - "Main Flow" 섹션을 실제 호출 경로로 확장 (knowledge injection → step loop → tool call → memory write).
     - "Dependencies" 섹션에 MEMORY_DB 스키마 의존성 명시 (`AgentMemoryFactEntries`, `AgentMemoryTexts`, insight KV 키 패턴).
     - "Observability" 섹션에 insight_worker 로그 파일과 healthcheck 방법 추가.
  4. **검증**: 실제 MEMORY DB에 접속해 `insight_worker_last_cycle_at`, `insight_worker_last_status`, `schema_insight:*` 몇 개를 조회하고, 문서에 예시 출력으로 넣어 "현재 실제로 이렇게 돌고 있다"는 증빙을 남긴다.
- 범위 제한:
  - 코드 변경 없음. 문서만 추가/갱신.
  - 기존 인사이트 로직/설정값은 그대로 유지.
  - 신규 문서는 `unit/feature-0002-agent-core/docs/` 하위에 배치.
- 검증 기준:
  - 신규 문서 2종이 존재하고, 각 문서에서 언급된 함수/상수/환경변수가 실제 코드에 존재한다.
  - Insight worker 헬스 체크 SQL snippet이 실제 MEMORY DB에 대해 실행 가능하다(검증 과정에서 직접 실행 결과를 문서에 남김).
  - FUNCTION.md Main Flow 내 각 단계가 실제 코드 경로와 일치한다.

### TASK-0026 상세 설계
- 문제: assistant 말풍선에 한 줄로 길게 들어온 SQL(예: `SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ...`)이 `<pre class="sql-block">`의 `white-space: pre` + `overflow-x: auto` 특성상 줄바꿈 없이 길게 그려지며, flex/grid 자식의 `min-width` 계산으로 인해 말풍선 전체가 수평으로 확장되는 UX 이슈가 있다.
- 목표:
  - SQL 쿼리가 한 줄로 길게 들어와도 말풍선 폭이 부모(채팅 영역) 폭 이상으로 확장되지 않는다.
  - 쿼리 가독성을 유지하기 위해 주요 키워드 경계에서 줄바꿈을 적용한다. 이미 여러 줄인 쿼리는 원형을 유지한다.
  - 기존 Navigator 헤더/버튼/컨텍스트 레이아웃은 그대로 유지한다.
- 접근:
  - 표시 전용 포매터 `formatSqlForDisplay(sql)` 추가 (저장/실행 SQL에는 영향 없음, `<pre>.textContent`에만 적용):
    - 입력에 이미 `\n`이 있으면 그대로 반환 (LLM이 포맷팅한 경우 존중).
    - 단일 라인일 경우 주요 키워드 경계에서 줄바꿈을 삽입한다. 대상 키워드:
      `SELECT`, `FROM`, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`,
      `LEFT JOIN`, `RIGHT JOIN`, `INNER JOIN`, `OUTER JOIN`, `FULL JOIN`, `CROSS JOIN`, `JOIN`,
      `ON`, `AND`(AND만 분리 시 너무 잦아지므로 `WHERE/ON` 뒤의 AND만), `UNION`, `UNION ALL`, `INSERT INTO`, `UPDATE`, `SET`, `VALUES`, `DELETE FROM`.
    - 정규식 기반으로 구현하되 **따옴표 안의 키워드는 분리하지 않는다**(단순 토크나이저로 문자열 리터럴 내부 스킵).
    - 중첩 괄호(서브쿼리) 깊이는 유지하고 별도 들여쓰기는 하지 않는다(단순화·안정성 우선).
  - CSS 수정:
    - `.sql-block`을 `white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere;` 로 변경(포매터가 못 잡는 초장문 토큰·식별자도 wrap되도록 안전망).
    - `.sql-navigator`, `.sql-nav-panel`, `.sql-result-group` 등 컨테이너에 `min-width: 0`을 보장해 flex/grid 자식 shrink를 허용한다.
  - 기존 단일 step 블록과 Navigator 패널 양쪽 모두 `buildSqlStepPanel()`을 경유하므로 한 곳만 수정하면 된다.
- 범위 제한:
  - 포매터는 표시용(`pre.textContent`) 전용. 서버로 전송되는 SQL, 복사(copy) 시나리오에는 영향을 주지 않는다(복사 시 줄바꿈 포함 허용 — 사용자가 다시 한 줄로 정리하면 되므로).
  - 새 백엔드 API 없음. agent_core / tools 변경 없음.
  - 기존 Navigator/키보드/CSV 전체 보기 로직은 변경하지 않는다.
- 검증 기준:
  - 긴 한 줄 SQL을 주입했을 때 말풍선 폭이 chat pane 폭 이상으로 확장되지 않는다.
  - `SELECT`/`FROM`/`WHERE`/`JOIN`/`GROUP BY`/`ORDER BY` 경계에서 줄바꿈이 삽입된다.
  - 이미 여러 줄로 포맷된 쿼리는 원형이 유지된다.
  - 따옴표 내부 문자열의 키워드(예: `'SELECT one, ...'`)는 분리되지 않는다.
  - 기존 Navigator 키보드 조작(`←/→/Home/End`)과 "전체 데이터 보기"가 그대로 동작한다.

### TASK-0025 상세 설계
- 문제: assistant 말풍선 내 `<details>`(실행 단계 및 쿼리 결과 보기)를 펼치면, execute_sql step이 여러 개인 경우 각 SQL + 결과 테이블이 수직으로 누적되어 말풍선 길이가 과도하게 증가한다. UI 개편 이전에 있었던 별도 팝업(`CSV 미리보기`) 방식은 창 크기가 레코드 수에 따라 흔들리는 UX 이슈가 있었다.
- 목표:
  - 말풍선 내 `<details>` 안에서 다수 SQL step을 수직 누적 없이 탐색 가능한 Navigator로 압축한다.
  - 각 말풍선의 탐색 범위는 해당 말풍선으로만 한정된다(격리된 스코프). 현재 선택된 결과셋이 어떤 SQL에 대응하는지 화면에서 상시 확인 가능해야 한다.
  - preview 레코드 제한을 넘어 전체 데이터도 조회 가능해야 한다(CSV 기반).
  - 키보드 조작 가능, 단 조작법은 화면에 상시 노출하지 않고 버튼의 `title` 툴팁(마우스 hover)으로만 힌트 제공.
- 접근:
  - `buildStepBlocks()`를 분해. execute_sql step이 2개 이상이면 Navigator 형태로 렌더링, 1개면 기존 단일 블록 유지.
  - Navigator 구조:
    - 헤더(1행): `◀` 이전 버튼 + `쿼리 n/N` 인디케이터 + `▶` 다음 버튼 + 현재 쿼리의 첫 테이블 참조(작업 대상) 라벨.
    - 본문: 현재 인덱스의 SQL `<pre>` + 결과 테이블 + 액션 영역(전체 데이터 보기, CSV 다운로드).
  - 키보드 조작:
    - Navigator 컨테이너에 `tabindex="0"` 부여 → 포커스 시 `←`/`→`로 prev/next, `Home`/`End`로 처음/끝 이동.
    - 각 버튼의 `title`에 단축키 힌트 포함(예: `이전 쿼리 (←)`).
  - 전체 데이터 조회:
    - preview_table이 truncated이고 csv_paths가 있을 때 "전체 N행 보기" 버튼 노출.
    - 클릭 시 `/api/file?path=...` 로 CSV fetch → 클라이언트 측 CSV 파서로 파싱 → 기존 테이블의 tbody를 전체 행으로 교체.
    - 대량 행(>500) 렌더 시 테이블 컨테이너 `max-height` + `overflow:auto`로 말풍선 영역 보호.
  - 스코프 격리:
    - Navigator 인스턴스마다 내부 상태(현재 인덱스)를 가지며, 말풍선 별로 완전 격리.
    - 헤더 상단에 "쿼리 1/3 · `schema.table`" 형태로 현재 선택 컨텍스트 상시 노출.
  - 접근성:
    - 버튼에 `aria-label`, 인디케이터에 `aria-live="polite"` 부여.
    - 키보드 포커스 시 outline 스타일 유지(제거하지 않음).
- 범위 제한:
  - 새로운 백엔드 API 추가 없음. 기존 `/api/file`만 재사용.
  - 기존 `<details>` 드롭다운 구조는 유지(그 안의 렌더링만 교체).
  - 단일 SQL step 케이스는 Navigator를 쓰지 않고 기존 블록 유지(불필요한 chrome 방지).
- 검증 기준:
  - operator 계정으로 2개 이상 execute_sql step을 발생시키는 질의 전송 후, Navigator로 단계 탐색이 정상 동작한다.
  - 키보드 `←/→/Home/End`로 step 이동 가능.
  - "전체 데이터 보기" 클릭 시 preview 이상의 행이 테이블에 렌더링된다.
  - 말풍선 총 높이가 step 수와 무관하게 한 화면 내로 유지된다.

## 4. Blocked
- 없음

## 5. Done
- TASK-0010 (2026-04-15): `WebAccounts`, `WebAuthSessions`, 회원가입/로그인/로그아웃 API, 부트스트랩 관리자 계정 추가
- TASK-0011 (2026-04-15): `/admin` 화면과 계정 승인/비활성/세부 권한 제어 API/UI 추가
- TASK-0012 (2026-04-15): `AgentCoreConversations.owner_account_id` 기반 계정 소유권 도입, 기존 대화 관리자 귀속 처리
- TASK-0013 (2026-04-15): 표시 이름/역할/사용 목적 입력 제거, Keyword Management 제거, Domain/Strategy/Session/Calendar 등 불필요한 UI 제거
- TASK-0014 (2026-04-15): 세션 응답의 `local_llm_enabled`를 실제 연결 가능 여부 기준으로 보정
- TASK-0015 (2026-04-15): 외부 스크롤 제거 · 마케팅 패널 제거 · App-Shell 레이아웃 적용. 로그인: 단일 카드, 메인: Topbar+Sidebar+ChatPane 3단 고정 구조
- TASK-0016 (2026-04-15): feature AGENTS.md §8에 UI/UX 설계 원칙, 버튼 클래스 규칙, 브라우저 검증 정책, 금지사항 문서화. LEARNINGS.md에 3개 항목 추가
- TASK-0017 (2026-04-15): 사이드바 하단 프로필 트리거(ChatGPT 패턴) + 프로필 드로어(권한/활동정보/비밀번호 변경/로그아웃). state.busyConversations Set으로 병렬 대화 지원. Admin 콘솔에 검색/필터/페이지네이션 추가
- TASK-0018 (2026-04-15): 프로필 드로어를 계정/보안/API Vault 3탭으로 재구성. 기존 설정 드로어 제거 및 API Vault 흡수. 탑바 API Vault 버튼 제거. 로그아웃 시 드로어 미닫힘 버그·회원가입 폼 잔류 버그 수정.
- TASK-0019 (2026-04-15): `llm-shared` 외부 네트워크에 Ollama 기반 `local-llm-gateway`를 복구하고 `auto/edge/core/code` alias 모델을 준비해 API 키 없는 `model=auto` 실행 경로를 복원
- TASK-0020 (2026-04-15): 현재 repo 내부 Local LLM runtime을 제거하고, 외부 `/root/download/docker/local_llm` provider를 `LOCAL_LLM_API_BASE=http://local-llm-gateway:8080/v1` 계약으로 소비하도록 전환
- TASK-0021 (2026-04-15): UI 개편 과정에서 누락된 `execute_sql` step 결과셋 인라인 표시 복원. `result_summary.preview_table`을 HTML 테이블로 렌더링, SQL 쿼리+결과+CSV를 step 단위로 묶어 표시. 구형 메시지는 `meta.sql`/`meta.csv_paths` 폴백.
- TASK-0022 (2026-04-16): Progress Strip을 `<details>`/`<summary>` 드롭다운으로 전환. step 수가 늘어도 기본 1행 고정, 펼침 시 `max-height:40vh` 내부 스크롤. summary에 `n단계 · 최근 작업` 표시.
- TASK-0023 (2026-04-16): Planner 자율성 개선 — TOOL_DEFINITIONS 순서를 execute_sql 최우선으로 재배치, 각 도구 description에 사용 조건 명시, SYSTEM_PROMPT에 CRITICAL DIRECTIVE·IDEAL FLOW EXAMPLE·강화 ANTI-PATTERNS 추가. 휴리스틱 없이 프롬프트/도구 제시 순서만으로 불필요 탐색을 억제.
- TASK-0024 (2026-04-16): `WebRoles`/`WebPermissions`/`WebRolePermissions`/`WebAccountPermissionOverrides` 기반 RBAC로 cutover. role명 특수 처리 없이 permission + ownership 로만 권한 판정. 계정 soft delete, role CRUD, tri-state override, own/any 대화 권한, 제목 변경 API, Accounts/Roles 2영역 관리자 콘솔, `/api/clear_memory` 제거 완료.
- TASK-0025 (2026-04-16): assistant 말풍선 내 다중 execute_sql step을 수직 누적 없이 SQL Navigator(단일 패널 + `←/→/Home/End` 키보드 조작 + `쿼리 n/N · 대상 테이블` 상시 컨텍스트 + "전체 데이터 보기" CSV 로드)로 압축. 단일 step은 기존 블록 유지. 새 백엔드 API 없이 `/api/file`만 재사용. 브라우저 자동화로 탐색/키보드/단일 step 분기/CSV 파서 모두 검증 완료.
- TASK-0026 (2026-04-21): 한 줄 긴 SQL이 말풍선을 수평 확장하는 이슈 해소. 표시 전용 `formatSqlForDisplay()` 추가(주요 키워드 경계 줄바꿈, 복합 JOIN 보존, 문자열 리터럴 보호, 기존 여러 줄 쿼리 원형 유지). `.sql-block` CSS를 `pre-wrap` + `word-break` + `overflow-wrap`으로 변경, 컨테이너 `min-width:0` 안전망 추가.
- TASK-0027 (2026-04-21): 33개 RBAC 권한의 UX 정리. Profile 드로어의 `buildPermissionPills()`를 그룹별 `<section class="perm-section">` + 카운트 배지 구조로 재작성. Admin 콘솔 권한 그리드 `renderPermissionGrid()`를 `<details>` 기반 collapsible + summary 카운트 배지(허용/거부/상속 또는 N/M 선택) + 그룹별 배치 액션 버튼(모두 허용/거부/상속 또는 모두 선택/해제)으로 개편. `PERMISSION_GROUP_ORDER/LABELS` 상수와 `permissionGroupOf()` 헬퍼 추가. CSS: `.perm-sections`, `.perm-section*`, `.permission-group-head`, `.permission-group-counts`, `.permission-bulk-actions` 스타일 추가.
- TASK-0029 (2026-04-21): 관리 콘솔 재구조화. `admin.html` 을 `topbar + sidebar(tabs) + workspace + commit-bar` 4영역 grid 로 재작성(탭: 대시보드/계정/역할). `admin.js` 전면 재작성 — `adminState.pending = { accounts, roles, newRoles }` Map 기반 pending changes 모델 + 서버 값과 일치하면 auto-drop 로직(`setAccountPending`/`setRolePending`). 계정/역할 편집은 form submit 없이 input/select change 이벤트에서 pending 에 적재만 하고, 하단 commit bar 의 "모두 적용" 클릭 시 전체 pending entry 를 순차 PATCH/DELETE/POST 후 1회만 `loadAdminData()`. 리스트-디테일 레이아웃 + 탭별 scoped search + 리스트 row 체크박스 기반 일괄 작업(활성/비활성/삭제 pending 반영). 신규 역할은 tempId(`new:N`)로 pending.newRoles 에 넣고 POST 로 일괄 커밋. `styles.css` 에 `.admin-shell` grid/`.admin-sidebar`/`.admin-tab`/`.admin-list-detail`/`.admin-list-row`/`.admin-detail-*`/`.admin-commit-bar`(.has-pending 노란 강조) 스타일 추가. 사용자 테스트에서 확인된 "여러 계정 동시 수정 시 특정 계정 저장하면 타 계정 변경 소실" 버그는 pending 모델 + 단일 commit 경로로 근본 해소.
- TASK-0028 (2026-04-21): agent-core 문서 보강. `docs/INSIGHTS.md` 신규 작성(워커 루프/사이클/fingerprint/인라인 fallback/KV 스키마/환경변수 14종/해석 가이드/헬스 체크 SQL + 2026-04-21 실제 런타임 출력). `docs/AGENT_CORE_INTERNALS.md` 신규 작성(run_agent 흐름도, SYSTEM_PROMPT 7블록 구조, TOOL_DEFINITIONS 우선순위 근거, Knowledge Injection, Step 예산/타임아웃/cancel/finalize 신호, CSV 2단계(preview 50행 + 전체 파일), Planner insight fast path, 3-state 대화 맥락). `FUNCTION.md` Main Flow/Dependencies/Observability 확장(MEMORY_DB 스키마 표, insight_worker 로그 관측성). 코드 변경 없음.

## 6. Next Action
- 신규 권한/계정 정책 변경이 필요하면 별도 TASK로 분리한다

## 7. Completion Checklist
- [x] Web UI 코드 이관이 완료되었다
- [x] 루트 실행 경로가 새 구조를 참조한다
- [x] 문서가 현재 구조를 반영한다
- [x] 계정/비밀번호 기반 인증이 동작한다
- [x] pending/read-only 흐름이 동작한다
- [x] 관리자 승인 및 세부 권한 조정이 가능하다
- [x] 대화 소유권이 계정 기준으로 분리되었다
- [x] 불필요한 상단 상태 정보와 Keyword Management가 제거되었다
- [x] 브라우저 기반 렌더링 증빙이 남아 있다
- [x] 상용 AI 앱 수준의 App-Shell 레이아웃이 적용되었다 (외부 스크롤 없음)
- [x] UI/UX 정책 지침이 feature AGENTS.md §8에 문서화되었다
- [x] 사이드바 하단 프로필 버튼이 ChatGPT/Claude 패턴으로 배치되었다
- [x] 프로필 드로어가 계정/보안/API Vault 탭으로 구조화되어 있다
- [x] 병렬 대화가 다른 대화의 요청 처리 중에도 차단되지 않는다
- [x] Admin 콘솔에 검색·역할 필터·페이지네이션이 동작한다
- [x] 계정별 설정(API Vault)이 탑바가 아닌 프로필 드로어 안에 배치되어 있다
- [x] 로그아웃 시 열린 드로어가 닫히고 인증 폼이 초기화된다
- [x] 현재 repo가 Local LLM runtime을 직접 소유하지 않는다
- [x] execute_sql 단계의 쿼리 결과가 인라인 HTML 테이블로 표시된다
- [x] SQL 쿼리 블록과 결과 테이블, CSV 링크가 step 단위로 묶여 표시된다
- [x] Progress Strip이 `<details>` 드롭다운으로 동작하며 step 증가 시 채팅 영역이 축소되지 않는다
- [x] Planner가 execute_sql을 우선 시도하도록 도구 순서와 프롬프트가 구성되어 있다
- [x] 계정이 `Role 기본 권한 + account override` 구조로 계산된다
- [x] `pending/operator/admin` 문자열 비교 없이 permission + ownership 만으로 권한이 판정된다
- [x] 관리 콘솔에서 role 생성/수정/삭제와 기본 가입 역할 변경이 가능하다
- [x] 관리 콘솔에서 계정 role 부여와 tri-state override 편집이 가능하다
- [x] 계정 soft delete 후 로그인 차단과 세션 폐기가 동작한다
- [x] 대화 조회/제목 변경/삭제/중단/즉시답변이 own/any 권한으로 분기된다
- [x] `/api/clear_memory` 및 legacy `Can*` 계약이 런타임에서 제거되었다
- [x] 다중 execute_sql step 말풍선이 Navigator로 압축되어 수직 누적되지 않는다
- [x] Navigator에서 `←/→/Home/End` 키보드로 step 탐색이 가능하다
- [x] 현재 선택된 쿼리의 인덱스와 대상 테이블이 Navigator 헤더에 상시 노출된다
- [x] "전체 데이터 보기" 로 preview 이상의 행을 CSV 기반으로 로드할 수 있다
- [x] 한 줄 긴 SQL 쿼리가 키워드 경계에서 줄바꿈되어 말풍선이 수평 확장되지 않는다
- [x] 이미 여러 줄로 포맷된 쿼리와 따옴표 내 키워드가 원형 유지된다
- [x] Profile 드로어의 권한 현황이 console/account/role/conversation/misc 그룹 단위 섹션으로 묶여 표시된다
- [x] Admin 콘솔의 계정/역할 권한 편집이 `<details>` collapsible 그룹 구조로 동작하고 summary에 카운트 배지가 표시된다
- [x] 각 권한 그룹에 배치 액션(모두 허용/거부/상속 또는 모두 선택/해제) 버튼이 동작한다
- [x] Insight 시스템(백그라운드 스키마/테이블 분석 워커)의 구조와 헬스 체크 방법이 `docs/INSIGHTS.md`에 명시되어 있다
- [x] agent-core 내부 동작(SYSTEM_PROMPT 구조, TOOL_DEFINITIONS 우선순위, Knowledge Injection, Step 예산, CSV 2단계, Planner fast path)이 `docs/AGENT_CORE_INTERNALS.md`에 명시되어 있다
- [x] 관리 콘솔이 대시보드/계정/역할 탭 기반 네비게이션으로 분리되어 있다
- [x] 계정/역할 편집이 pending changes 모델로 관리되며, 하단 commit bar 의 "모두 적용" 시에만 서버에 반영된다
- [x] 여러 계정을 동시에 편집해도 각 편집 내용이 유지되며 단일 계정 저장으로 소실되지 않는다
- [x] 리스트 row 체크박스 + 일괄 작업(활성/비활성/삭제 pending)이 동작한다
- [x] 계정 탭/역할 탭 각각이 독립된 scoped search 를 가진다
