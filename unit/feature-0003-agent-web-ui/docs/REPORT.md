---
doc_type: REPORT
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
**2026-05-18 TASK-0067 완료 — 제품 칩 composer 이전 + custom drop-up dropdown (ChatGPT 모델 선택 패턴)** (CHG-20260518-0004, REV-20260518-0004, REQ-20260518-0005, Minor §12.3 — UI 위치 이전 + native select → custom dropdown, backend / endpoint / RBAC / 데이터 영역 무변경).

**배경**: TASK-0066 의 layout 통합 후 사이드바 영역도 확장하기 위한 사용자 follow-up. ChatGPT 의 모델 선택 UI 패턴 — chip 을 composer 영역 우측 (textarea / sendBtn 사이) 에 두고 click 시 drop-up dropdown 으로 옵션 표시.

**변경**: (1) `.sidebar-head` 의 `.product-chip-wrap` 제거 → sidebar-head 에는 `#newConversationBtn` 만 (sidebar vertical 공간 확장). (2) `.composer-box` 안에 `.composer-product-chip-wrap` 신설 — `button#productChip` (dot + compact label + arrow) + `div#productDropupMenu`. (3) 기존 native `<select id="productSelect">` 폐기 → custom button + custom menu (drop-up 보장). (4) JS: `renderProductChip` 재작성, 신규 `renderProductDropupMenu` / `buildProductDropupItem` / `openProductDropup` / `closeProductDropup`. chip click handler 가 dropdown toggle. `setActiveProduct` 본체 무변경 (backend `PATCH /api/conversations/{cid}/product` 호출 그대로).

**디자인 정책**: chip label = compact (`product_key` 만, chip width 보존) + aria-label = full (`{name} ({product_key})`). menu z=50, drop-up (`bottom: calc(100% + 6px)`), max-height 320px. busy 시 chip.disabled + aria-disabled (race 가드 보존).

**검증**: `node --check` PASS, `SKIP_INIT=1 make web` 재배포 OK. Browser headless: `chipInComposer=true` (chip 이 composer-box 안), 기존 native select 부재, sidebar-head 가 "새 대화" 만, chip click → menu 4 items (auto + KR + MV + GZ_KR) 정상 + `dropUp=true` (menuY=459 < chipY=644), KR item click → chip label "KR" + chip mode=pinned + toast "제품을 킹스레이드로 바꿨어요. 다음 답변부터 적용됩니다." 정상. backend endpoint 호출 정상. cache-bust `v=20260518-product-composer`.

후속 cycle 권장: dead CSS rule (`.product-chip-wrap` / `.product-chip*` / `.topbar-brand`) 정리. arrow key keyboard navigation (REQ-20260518-0005 의 후속 가능).

---

**2026-05-18 TASK-0066 완료 — ChatGPT 패턴 layout 재구조화 (헤더 영역 통합)** (CHG-20260518-0003, REV-20260518-0003, REQ-20260518-0004, Minor §12.3 — UI layout, RBAC / endpoint / 데이터 / JS 시그니처 무변경).

**배경**: TASK-0065 follow-up. 헤더 4 버튼 제거로 `.chat-header` 가 거의 비어 있어 `.topbar` (관리 콘솔) 과 영역 통합이 자연스러움.

**사용자 결정** (in-cycle): topbar 에 대화 제목 통합 + 좌측 정렬 (중앙 정렬 금지) + brand `[MA] MySQL AI` 를 sidebar 영역으로 이전 (ChatGPT UI 명시). chat-pane 상단 chat-header 제거로 채팅 영역 확장.

**변경**: `.app-shell` grid 가 2-row (topbar | app-body) → 2-column (sidebar | chat-column) 로 단순화. `.app-body` wrapper 폐기. `.sidebar-brand` (height = topbar-h = 52px, border-bottom) 신설 — sidebar 의 첫 영역, topbar 와 baseline 정렬. `.chat-column` (flex column) 신설 — sidebar 옆 영역. topbar 가 chat-column 의 첫 child 로 이전 (대화 제목 좌측 정렬 + loadMoreBtn + 관리 콘솔 우측). `.chat-header` 폐기 — `.chat-title` / `.chat-subtitle` typography 만 보존. 반응형 mobile (max-width: 680px) 도 `.app-shell { grid-template-columns: 1fr }` 으로 변환.

**검증**: DOM `.app-shell.gridTemplateColumns = "252px 1028px"` / `.sidebar-brand` 정상 mount + "MA MySQL AI" / `.topbar.height = 52px` / 기존 `.chat-header` DOM 부재 — 모두 확인. browser screenshot (`/tmp/layout-merged.png`): 좌측 sidebar (brand + 제품 칩 + 새 대화 + conv list + 프로필) / 우측 chat-column (topbar 좌측 정렬 제목 "SQL 쿼리 계속 완성 요청" + `최근 갱신 ... 메시지 22 · 소유자 admin` 부제 + 우측 끝 `관리 콘솔` + sticky 분기선 "2026년 4월 16일" + 메시지 영역 확장) — ChatGPT 패턴 정확 구현 + 직전 cycle 변경 (sticky / "···" menu) 무회귀. cache-bust `v=20260518-topbar-merge`. JS 변경 0.

---

**2026-05-18 TASK-0065 완료 — TASK-0063 직접 테스트 follow-up 3 항목 (헤더 4 버튼 제거 + trigger 우측 하단 + 분기선 sticky)** (CHG-20260518-0002, REV-20260518-0002, REQ-20260518-0003, Minor §12.3 — UI 정리, RBAC / endpoint / 데이터 영역 무변경).

**변경**: (1) `chat-header-tools` 의 `forkConversationBtn` / `shareConversationBtn` / `renameConversationBtn` / `deleteConversationBtn` 4 element 제거. conv-item "···" menu 가 단일 진입점. backend helper 는 menu makeItem + message-bubble actions 에서 여전히 호출 — 무변경. (2) `.conv-item-menu-trigger` 위치 `top: 6px` → `bottom: 6px` (owner badge 와 시각 충돌 해결). `.conv-item` 에 `padding-right: 32px` 보정. (3) `.message-date-divider` 에 `position: sticky; top: 0; z-index: 5` + `padding: 4px 0`. label 배경 `var(--surface-2)` (반투명) → `var(--surface-1, #ffffff)` (불투명) + `box-shadow: 0 1px 2px rgba(0,0,0,.04)` elevation. hover 시 `box-shadow: 0 2px 6px rgba(37,99,235,.18)` 강화.

**검증**: `node --check` PASS, `SKIP_INIT=1 make web` 재배포 OK. Browser smoke (`gstack /browse` headless): 헤더 4 버튼 부재 확인 (snapshot 의 `chat-header-tools` 영역에 `loadMoreBtn` 만), active conv-item trigger DOM `getComputedStyle` 가 `bottom: 6px / right: 6px / opacity: 1` (우측 하단 정상), 2 분기선 conversation 에서 `messageLog.scrollTop = 600` 깊이 스크롤 시 첫 분기선 "2026년 4월 15일" 이 messageLog 상단에 sticky stick 됨 (screenshot 첨부) — Slack 패턴 정확 구현. cache-bust `v=20260518-header-cleanup`.

---

**2026-05-18 TASK-0063 완료 — 작업 화면 conv-item "···" menu (복사 / 공유 / 제목 변경 / 삭제) + 캘린더 시간 이동 분기선 trigger** (CHG-20260518-0001, REV-20260518-0001, REQ-20260518-0001, **Major** §12.3 — RBAC catalog 확장 2 + 신규 endpoint 1 + 파괴적 액션 menu 통합). Codex outside voice review 의 10 risk 모두 반영 + 사용자 4 결정 채택 (full self-fork / 신규 권한 분리 / 헤더 share 유지 / 헤더 calendar 제거 + 년 jump 조건부).

**Backend**: `PERMISSION_DEFINITIONS` 에 `conversation.duplicate.own/.any` 2 건 추가 (catalog 34→36). SEED_ROLE_DEFINITIONS operator/sales 에 `.own` grant, admin 은 set(PERMISSION_CODES) 로 둘 다 자동 포함. `_ensure_seed_roles` 의 admin catchup tuple 에 duplicate.own/.any 추가, operator/sales catchup loop 을 (share.create, duplicate.own) 리스트 기반으로 일반화. 신규 endpoint `POST /api/conversations/{cid}/duplicate` — read-gate 먼저 (404 단일 wording → metadata leak 차단), `.any` superset semantics, `_fork_conversation_impl` 재활용, grapheme-safe `사본:` prefix. `_ensure_seed_catchup` 의 catalog hydrate 호출을 seed_roles 앞으로 이동 (회귀 fix — 이전 순서로는 admin/operator/sales catchup 의 _permission_id_map lookup 이 신규 권한 id=0 받아 skip).

**Frontend**: `renderConversationList()` 의 conv-item 마다 `.conv-item-menu-trigger` 추가 (hover/active fade). click → `openConversationItemMenu(cid, triggerEl)` 가 fixed-position dropdown mount (a11y role=menu/menuitem, ESC + outside-click + scroll/resize close, viewport clamping). menu items 는 rename/delete pattern (visible + is-access-blocked + toast). `duplicateConversationFromMenu(cid)` 신설. `createConversationShare({conversationId})` / `renameCurrentConversation(cid)` / `deleteConversation(cid)` 가 cid 인자 수용. `renderMessages()` 에 `.message-date-divider` (Slack pill) 삽입 + click → `openHistoryCalendarAt(dateKey, divider)`. `openHistoryCalendar` 를 `openHistoryCalendarAt(dateKey?, anchorEl?)` 로 리팩토링 — anchorEl 가 주어지면 popover 가 fixed-position 으로 분기선 하단 mount. popover header 의 `#calendarNav` 슬롯에 `‹ › [Y년 M월] (« »)` 동적 nav — 년 jump 는 `(newestYear - oldestYear) >= 1` 일 때만 노출. 헤더 `historyCalendarBtn` 제거. outside-click 으로 popover close 시 `.message-date-divider` 도 trigger pair 로 인정.

**검증**: python compile / node --check 통과. `SKIP_INIT=1 make web` 재배포 PASS. DB 직접 확인 — `WebPermissions` 의 `conversation.duplicate.own/.any` row hydrate 정상, role grant — admin (.any + .own) / operator (.own) / sales (.own). browser headless smoke (`gstack /browse`): 좌측 conv-item "···" trigger 정상 표시, dropdown 4 항목 (복사 / 공유 / 제목 변경 / 삭제 — danger 색) mount, 채팅 로그 "YYYY년 M월 D일" 분기선 표시 + click → popover anchored 오픈, 월 nav (‹ ›) 정상 (테스트 환경 데이터 1년 미만이라 « » 미노출 = 조건 충족 안됨 = 정상). 헤더 historyCalendarBtn 부재 확인. cache-bust `v=20260518-conv-menu`.

후속 cycle 권장 (REV-20260518-0001 Risks):
- 헤더 share 의 hide-vs-disable 패턴을 menu 와 일치 (visible + is-access-blocked) 시키는 정합화 (Codex risk 8 잔여).
- `_ensure_permission_catalog` 가 IsDynamic 컬럼을 명시 INSERT 하도록 강화 (Codex risk 2 — 별 배포 환경 대비).
- 년 jump 버튼의 노출 조건을 `>= 12 months` 또는 `>= 365 days` 로 정밀화 (현재 `>= 1 year diff` 는 같은 해 1월/12월 데이터에서는 숨김).

---

**2026-05-15 TASK-0061 round 2 — /qa 심층 검증 완료, 추가 fix 0건** (browser session `483add52718b4a93`). Phase 4 (Point rail) 의 dot click → smooth scroll + active dot id 갱신 (`291`) 정상. Phase 5 (캘린더) 의 월 prev/next 이동 + has-messages day "15" 선택 → 시각 list 1 개 표시 + screenshot `/shared/out/browser/shot_20260515_091222.png` 정상. Phase 3 stale / Phase 6 비번 reset / Phase 8 bulk delete 는 destructive endpoint 라 운영 환경 사용자 명시 시점에 실 호출 검증 권고 (1차 cycle 의 응답 형식 / 권한 / DOM 요소 검증으로 contract 확정 완료). 본 cycle PR (#27) 은 추가 fix 없이 ship 가능.

**2026-05-15 TASK-0061 완료 — GOAL.md 8 항목 Web UI 합본 cycle (실시간 step / lazy polling / stale 감지 / point rail / 캘린더 / 비밀번호 초기화 / select-all fix / bulk delete)** (CHG-20260515-0003, REV-20260515-0003, REQ-20260515-0003~0010, **Major** §12.3 — Phase 6 Critical 분면 포함, 사용자 일괄 승인 + 보안 권장안 채택). 

**Phase 1+2 (답변 버블 실시간 + 신규 대화 첫 polling)**: `state.pendingBubble` + `renderPendingAssistantBubble()` + 1초 elapsed timer + `applyProgressPayload` 동기화. lazy-create 분기에서 cid 발급 즉시 `startProgressPolling({reset:true})` 호출.

**Phase 3 (stale processing 만료 감지)**: backend `_compute_display_status` + `_last_step_at_for_run` + env `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` (20분). `/api/progress` / `/api/ask_status` / `/api/ask_result` / `_list_conversations` 일관 stale 처리 (status=`stale_error`, is_stale=true, is_processing=false). frontend `.conv-dot.is-stale-error` (빨간 토큰) + tooltip + 1회 toast 안내.

**Phase 4 (Point rail)**: `#messagePointRail` + `renderMessagePointRail()` + scroll observer 로 viewport 중앙 dot highlight. 좁은 화면 hidden.

**Phase 5 (캘린더/시각 이동)**: backend `/api/history_dates` 가 `AgentMemoryMessages` 정본 기준 (이전 `AgentCoreMessages`). frontend `historyCalendarBtn` + `#historyCalendarPopover` (월간 grid + 시각 list) + `/api/history_anchor` smooth scroll.

**Phase 6 (관리자 주관 비밀번호 초기화, Critical)**: `WebAccounts.MustChangePassword TINYINT(1) NOT NULL DEFAULT 0` 컬럼 idempotent ALTER. 신규 endpoint `POST /api/admin/accounts/{id}/password-reset` — `secrets.token_urlsafe(12)` 임시 비번 + `MustChangePassword=1` + 대상 계정 `WebAuthSessions IsRevoked=1`. self-reset 거부. `_serialize_account` + `_fetch_account_rows` 에 `must_change_password` 노출. `/api/auth/me` PATCH 가 비번 변경 성공 시 `MustChangePassword=0`. frontend Account detail 의 `adminPasswordResetBtn` + 1회 표시 modal + 강제 변경 modal (login + initializeWorkspace 직후 hook).

**Phase 7 (admin select-all 현재 페이지 fix)**: `currentPageAccounts()` helper 신설. `accountSelectAll` change handler 와 `updateAccountSelectAllCheckbox()` 가 동일 helper 사용 — 현재 페이지 row 만 토글, 다른 페이지 선택 보존.

**Phase 8 (내 대화 Ctrl/Shift 다중 선택 + bulk delete)**: `state.conversationSelected: Set<string>` + Ctrl/Meta toggle + Shift range. own 그룹만 `.conv-item-checkbox` 노출. `.conv-bulk-bar`. backend `_delete_conversation_impl` helper 추출 + `POST /api/delete_conversations` partial success endpoint. ≥10 typed-confirm + processing 강제 삭제 confirm.

검증: python compile / node --check 통과. `make web` 재배포 PASS. browser (http://web:8000) DOM 5개 신규 element + login + bulk bar + 캘린더 popover 2026-04 + `/api/progress` display_status + `/api/history_dates` AgentMemoryMessages 응답 + `/api/delete_conversations` empty=400 validation + pending bubble spinner/elapsed/bubble 정상 + admin currentPageAccounts()=15 / filteredAccounts()=26 (다른 페이지 보존) + `adminPasswordResetBtn` "비밀번호 초기화" 노출 확인. cache-bust `v=20260515-task-0061`.

**2026-05-15 TASK-0060 완료 — 실제 접근 DB 기반 Product / Role 시스템 프롬프트 정비 + Role 공통 누적 적용 fix** (CHG-20260515-0002, REQ-20260515-0002, Minor §12.3). 현재 Product는 `KR(킹스레이드)`와 `MV(마이크로볼츠)` 두 개다. `KR`은 `dbgame,dblog,dbauth`, `MV`는 `account_db,dev_1_1_1_20,have_00,log_v2,global_db`가 접근 DB로 등록되어 있다. `information_schema`와 제한적 집계로 주요 테이블/행 수/시간 범위를 확인한 뒤 `WebSystemPrompts`에 Product prompt 2건과 Role common prompt 5건(`pending/operator/admin/sales/dba`, `ProductId IS NULL`)을 upsert했다. `log_v2`는 DB는 존재하지만 테이블 0개로 확인되어 MV prompt에 명시했다. 기존 runtime은 Role×Product prompt가 있으면 `전 Product 공통` Role prompt를 fallback으로만 사용했으므로, feature-0002 `compose_system_prompt()`를 공통 누적 방식으로 수정했다. 검증: py_compile 통과, 신규 unittest 2건 통과, SQL readback 완료, web 컨테이너 내부 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")` 결과에 `PRODUCT CONTEXT` + `ROLE GUIDANCE` + `### 전 Product 공통` 포함 확인.

**2026-05-12 TASK-0056 완료 — 작업 화면·관리 콘솔 권한 정렬 분리** (CHG-20260512-0002, REQ-20260512-0002, **Major** §12.3). 사용자 보고: "작업 화면에서 접근하는 권한과 관리 콘솔에서 접근하는 권한을 수정할 때 해당 권한들의 순서가 혼용되어 있어 각 화면에 알맞게 순서 및 섹션을 구분 필요". 두 화면이 같은 group 순서 (`console→account→role→conversation→[product]→misc`) 로 묶여 있어 화면 맥락 (자기시점 / 관리자시점) 이 정반대인데도 admin 메타권한이 두 곳 모두 위에 노출되던 문제. **분리 안**: 작업 화면 = "운영 권한 (conversation/product) → 관리 권한 (console/account/role) → 기타" + 관리 권한 묶음은 보유 시만 표시. 관리 콘솔 = "관리 권한 → 운영 권한 → 기타" 2단 section 헤더로 시각 분리. (1) [`docs/CONVENTIONS.md §10.6`](../../../docs/CONVENTIONS.md) 화면별 권한 섹션·정렬 정책 신설 — 화면별 section 순서 표, 정합 규칙 6 줄, 동적 권한 (`product.access.<key>`, `system_prompt.*`) 처리, 새 group key fallback 정책. (2) **admin.js**: 새 상수 `ADMIN_PERMISSION_SECTIONS`, 새 함수 `sectionedGroupedPermissions(opts)`, `renderPermissionGrid` 가 outer `.permission-section` 으로 inner `<details data-perm-group>` 을 감싸도록 수정. (3) **app.js**: `PERMISSION_GROUP_ORDER` 에 `product` 추가 (작업 화면 측 누락 fix), `PERMISSION_GROUP_LABELS.product = "제품"`, 새 상수 `WORK_SCREEN_PERMISSION_SECTIONS`, `permissionGroupOf()` 가 `system_prompt.` 접두사를 product 로 매핑, `PERMISSION_LABELS` / `_DESCRIPTIONS` 에 `product.manage` / `system_prompt.manage.role.any` 추가, `buildPermissionPills` 가 2단 묶음 (`.perm-section-meta`) 으로 렌더 + 빈 section 자동 hide. (4) **styles.css**: 작업 화면 `.perm-section-meta*` 5 클래스, 관리 콘솔 `.permission-section*` 5 클래스 (`data-perm-section="manage"` 살짝 파랑 / `"operate"` 살짝 녹색), section 간 gap 중첩 제거. (5) cache-bust `v=20260512-perm-sections` (admin.html / index.html). **DB schema / backend RBAC catalog / endpoint guard / system prompt assembly 변경 0** — frontend 렌더링 + 정책 문서만 수정, 인가 모델 무영향. node --check 양 파일 통과. **후속**: (a) `make web` 재배포 + 시각 검증 (사용자 환경 — 일반 사용자 / admin 양 시점). (b) 새 group key 가 백엔드에 추가될 때 두 상수 (`WORK_SCREEN_PERMISSION_SECTIONS` / `ADMIN_PERMISSION_SECTIONS`) 에 명시 매핑 — 미매핑 시 "기타" fallback. (c) CONVENTIONS.md §10.6 의 "policy-contract 자동 contract 정의" 후속 cycle 등록.

**2026-05-12 TASK-0055 완료 — 관리 콘솔 카테고리별 다중선택 UX 정합 컨벤션 v0.2 도입 + 코드 통일** (CHG-20260512-0001, REV-20260512-0001, REQ-20260512-0001, Major §12.3, 사용자 명시 AI 자율 commit/push). 사용자 raw feedback "관리 콘솔의 카테고리 별 다중선택 UI 가 계정=우상단 / 역할=좌하단 / 제품=다중선택 부재 로 일관성 없음. 차후 작업에서도 이러한 경향이 나타나지 않도록 방향을 정합적으로 명시" 대응. 본 cycle = **정책 + gstack design 외부 시각 + Core+keyboard+advanced 코드 통일 합본**. (1) **정책 정립**: [project-level `docs/CONVENTIONS.md §10`](../../../docs/CONVENTIONS.md) 신설 (다중선택 적용 룰 / DOM anchor 표준 / 자료구조 invariant / 단위 어휘 / 신규 카테고리 체크리스트) + [feature-local `docs/DESIGN.md`](./DESIGN.md) 신규 (14 섹션, HTML 구조 / CSS 토큰 / Set invariant / runtime assertion / §5 컴포넌트 set / §6 cross-page banner / §7 typed-confirm / §8 RBAC partial-fail UI / §9 keyboard map / §10 a11y / §11 렌더 cycle / §12 Products 마이그레이션 plan / §13 open questions / §14 모던 레퍼런스 거부 근거). (2) **외부 design 시각** (general-purpose subagent + worker-design framework 차용) 으로 v0.1 → v0.2 흡수: dimension rating IA 6 / Visual 5 / Interaction 6 / Consistency 7 / A11y 4 의 5 gap (cross-page selection / empty·loading·error state / optimistic rollback / confirm 컨벤션 / RBAC gating) 전부 반영. 모던 레퍼런스 (Linear floating pill / GitHub select-all menu / Notion morph / Stripe cross-page banner / Vercel inline action) 의 차용·거부 근거 명시. (3) **코드 통일** — admin.html (Accounts bulk anchor 헤더→list 하단, Products multi-select HTML 신설, 모든 카테고리 role/aria-live/cross-page banner), styles.css (`--z-bulk-bar` / `--z-bulk-banner` / `--bulk-bar-bottom` / `--bulk-bar-elev` 토큰, `.admin-bulk-actions` sticky, `.admin-bulk-cross-page`, `.kbd-hint`, `.toast-skipped`), admin.js (`BULK_ENTITY_UNIT` / `BULK_ACTION_LABEL` / `CONFIRM_TYPED_THRESHOLD` 상수, `confirmBulkAction` / `runBulkActionWithPartialFail` / `assertBulkBarContract` / `renderCrossPageBanner` / `applyShiftRangeSelect` 헬퍼, Accounts/Roles/Products 의 `render*List` / `render*BulkBar` / `bulk*SetActive` / `bulk*Delete` 전면 통일, `productSelected: Set<number>` 신설, `accountLastClickIdx` / `roleLastClickIdx` / `productLastClickIdx` 신설, Esc 글로벌 핸들러, `productSelectAll` listener, initialize 끝에 `assertBulkBarContract` 호출). 사이즈: admin.js 2645 → 3080 lines (+435), admin.html 219 → 250 lines (+31), styles.css 2976 → 3052 lines (+76). cache-bust `v=20260512-bulk-contract-v02`. **node --check admin.js 통과**. **후속 검증 항목**: (a) 실제 `make web` 기동 + 브라우저 시각 검증 (사용자 환경) — 본 cycle 은 코드 변경 + 정적 검증까지. (b) `setProductMetaPending(_delete: true)` 의 backend apply path 검증 — backend 가 product `_delete` 키를 수용하는지 확인 필요. (c) e2e/screenshot test 가 `#accountsBulkBar` 의 기존 위치 selector 에 의존하는지 정리. (d) `assertBulkBarContract` 의 CI 화 (jsdom 또는 e2e snapshot). (e) `window.prompt()` 기반 typed-confirmation 의 modern modal upgrade (v0.3 후보).

**2026-05-07 TASK-0053 follow-up 2 — pending row UI 뒤틀림 fix + 제품별 접근 카드 list 를 권한 grid 의 'product' 그룹 details 안으로 이전** (CHG-20260507-0001, REV-20260507-0001). 사용자 직접 보고 두 이슈. (1) `.admin-list-row.has-pending::before { content: "" }` placeholder rule 의 pseudo-element 가 CSS Grid 의 4번째 grid item 으로 참여해 cb/main/chips layout 이 row 2 까지 밀리던 버그 → pseudo-element 제거 + `border-color` 로 대체. (2) `buildRoleProductCardList` / `buildAccountProductOverrideList` 에 `opts.embed` 추가 + `renderRoleDetail` / `renderAccountDetail` 가 권한 grid 안의 `details[data-perm-group="product"]` 를 찾아 그 안에 append. 사용자가 "제품" 그룹 collapse 시 정적 권한 + product 별 카드가 함께 접힘. DOM 좌표 비교 + screenshot 시각 검증 통과.

**2026-05-06 TASK-0053 완료 — 신규 제품 default 정책 토글 (Product 주체) + 권한 grid 의 product sub-catalog + Role/Account detail 의 product 카드** (REQ-20260506-0006, Major §12.3, AI 자율 commit/push). 사용자 follow-up: 신규 product 가 추가될 때마다 각 role 마다 비활성화하는 번거로움 해소 + product 가 많아질 때 Role/Account detail 에서 가시성 향상. 사용자 in-cycle 설계 전환으로 정책 주체를 Role → Product 로 변경 (`WebProducts.DefaultRoleAccess` 컬럼). admin UI 토글은 Product detail 에 위치. 권한 grid 의 dynamic `product.access.*` 가 별도 product subcatalog 카드로 분리되어 Role detail 은 product 별 (access 토글 + role-scope prompt) collapsible card list, Account detail 은 product 별 override (allow/deny/inherit) flat card list. E2E smoke: product 생성 시 `default_role_access=false` → 6 role 모두 grant 0 / `=true` → 6 role 모두 grant. backend `/api/admin/products` 응답에 `default_role_access` 노출, `/api/admin/roles` 에서는 이전 시도 잔재 `default_product_access` 필드 제거 확인.

**2026-05-06 TASK-0052 완료 — 계정·역할 → 제품 권한 상속/override 모델 도입** (REQ-20260506-0005, **Critical** §12.3, AI 자율 commit/push 모드). Codex outside voice 의 9 finding 모두 통합. Phase 1A (catalog 인자화, commit `4dd1d0a`) → Phase 1B (catalog DB-driven + product 권한 backfill + 명시적 트랜잭션 + caller-update) → Phase 1C (G1-G8 8 endpoint guards + admin_update_account RoleId 손실 pre-existing 버그 fix) → Phase 1D (admin UI PERMISSION_GROUP_ORDER 'product') → Phase 2 (HTTP smoke 6/6 P0 직접 + lifecycle T13/T16 cascade + bug fix 검증). bootstrap stderr 메시지 `[TASK-0052 Phase 1B catchup] product access backfill: 7 permission/role-permission rows added` 운영 transparency 확인. catalog 33 → 34 (`product.access.kr` 추가). admin 이 deny override 적용 시 G1/G2/G7/G8 모두 HTTP 403 정상. Phase 2 P2 (sessions/me filter, end-user FE chip filter) 와 F8 (admin lockout 보호) 는 별 cycle 분리.

**2026-05-06 TASK-0052 Phase 1A 진입 — RBAC engine catalog 인자화 refactor** (REQ-20260506-0005, Critical §12.3) — Codex outside voice (Claim 1) 가 발견한 정적 `PERMISSION_CODES` 가정에 5 hot path 가 hardwired 되어 있던 문제의 1 단계 해소. `_resolve_permission_catalog(conn=None)` 헬퍼 신설 + 5 함수 시그니처를 catalog 인자 받는 형태로 확장 (default None = 기존 정적 동작). `/api/admin/permissions` 1 곳만 신규 plumbing 경로로 전환해 Phase 1B 의 DB-driven catalog 도입 surface 를 미리 검증. **동작 변경 0** (33 codes 정확히 동일), `make web` 재배포 + HTTP smoke 통과. Phase 1B (WebPermissions IsDynamic/ProductId 컬럼 + product 권한 backfill SQL + caller-update) / Phase 1C (8 endpoint guard) / Phase 1D (admin UI group label) 는 별 cycle 분리. plan 정본은 [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md).

**2026-05-06 관리 콘솔 일괄 저장 정책 회복 + 메타 4 종 시각화 + DB 라이브 enum** (TASK-0051, REQ-20260506-0004) — 관리 콘솔에 남아 있던 인라인 save 버튼 3 종 (`프롬프트 저장` / `제품 정보 저장` / `DB 목록 저장`) 을 footer `모두 적용` 단일 commit 흐름에 통합하고, 메타데이터 4 스키마(`information_schema`/`mysql`/`sys`/`performance_schema`) 를 회색 disabled chip + `항상 접근` 라벨로 강제 노출(REV-20260422-0006 정책 시각화), 자유 텍스트 chip 입력을 `GET /api/admin/databases/available` 라이브 enum 기반 picker 로 교체했다. C5 (계정·역할 → 제품 권한 상속/override 모델) 는 다음 cycle 의 `/plan-eng-review` 후 진행으로 분리 권고.

**2026-05-06 빈 대화 누적 이슈 일괄 해결** — TASK-0048 (신규 누적 차단, lazy 화), TASK-0049 (누적분 정리, 88→46 conversations), TASK-0050 (`make web` 의 docker compose + buildx race 회피로 운영 검증 가능화) 의 3개 TASK 가 같은 cycle 에서 동시 마감되었다. 운영 데이터에서 빈 대화는 0 건이며 신규 row 측 차단 로직이 컨테이너에 반영되어 활성 상태다 (`docker exec repo-web-1 grep PENDING_CONV_SENTINEL`).

"새 대화" 버튼은 더 이상 `POST /api/new_conversation` 을 즉시 호출하지 않는다 (TASK-0048, REQ-20260506-0001). 클릭 시 client-side `state.pendingNewConversation=true` 로만 진입해 사이드바 "내 대화" 그룹 상단에 `conv-item is-own is-active is-pending` placeholder ("새 대화 (작성 중)" / 부제 "첫 메시지를 입력하세요") 가 표시되고 composer 가 활성 상태로 떨어진다. 사용자가 첫 메시지를 보내면 `sendPrompt()` 가 `/api/ask` 에 `conversation_id: ""` + `product_mode` + `product_id` (사용자 직전 의도) 를 첨부해 호출하고, backend `/api/ask` 의 `request_conversation_id` 가 비어있는 lazy creation 분기에서 `_resolve_conversation_for_account(create_if_missing=True)` 직후 hint 를 `AgentCoreConversations.product_id/product_mode` 에 셋업 + `_save_account_product_pref` 호출로 `WebAccounts.ProductPref*` 미러까지 갱신한다. 응답의 `conversation_id` 를 client 가 채택하고 placeholder 가 사라진다. 빈 대화 누적이 신규 row 측에서 차단된다 — 사용자가 버튼만 누르고 메시지를 보내지 않으면 backend 에는 아무 row 가 생기지 않는다. PATCH race 가드(TASK-0047 AC-0013) 와 attach/resume(TASK-0041 AC-0018) 는 cid 가 있을 때만 의미가 있어 lazy 분기에서 의도적으로 비활성화 — pending 단계 ask 실패는 "다시 시도하거나 사이드바 새로고침" 안내 토스트로 fallback. 기존 누적된 빈 대화의 일괄 정리는 destructive 변경이라 §12 사람 승인이 필요하므로 본 TASK 범위 외 — 후속 작업으로 명시.

사용자가 진입(로그인 직후) 또는 진행 중 대화에서 대상 **제품(Product)** 을 사이드바 헤더 칩에서 선택할 수 있고, `auto` 옵션으로 일반 대화를 이어갈 수 있도록 UX 와 데이터 모델을 확장했다 (TASK-0047). `AgentCoreConversations.product_mode VARCHAR(8) NOT NULL DEFAULT 'pinned'` 컬럼과 `WebAccounts.ProductPrefMode/ProductPrefPinnedId` 두 컬럼이 추가되었고, 신규 `PATCH /api/conversations/{cid}/product` 엔드포인트가 권한·소유자·진행 중 ask race(`AgentMemoryKv.last_status='processing'` ⇒ 409) 가드와 함께 도입되었다. `compose_system_prompt(... ,product_mode='auto')` 분기는 PRODUCT/role/account 의 product 한정 prompt 를 모두 건너뛰고 `[AUTO MODE]` 한 줄만 inject 하며, web 레이어가 `allowed_schemas=[]` (메타 4 스키마 한정) 으로 cross-product leak 을 차단한다. Frontend 는 `state.productMode/pinnedProductId/activeProductId` 3-필드 분리 + `setActiveProduct()` optimistic + PATCH + localStorage 미러(`mad.productPref.v1`) + `<select>` busy disabled tooltip 을 갖췄다. 사용자 가시 한글 라벨 "상품" 은 모두 "제품" 으로 일괄 치환되었고, 코드 식별자(`Product`/`product_id`/`WebProducts`/`ProductKey`) 는 보존했다. **본 turn 은 사용자 검토 없이 4인 agent team(UX/Frontend Architect/Backend Engineer/QA-Flow Validator) 합의 + Codex CLI 교차검증** 으로 진행됐다 — 운영 반영 전에 [`docs/BRIEFING-product-selector-v1.md`](./BRIEFING-product-selector-v1.md) 의 R-01..R-16 검증 + D-01..D-05 사람 결정이 필요하다.

System Prompt 를 Product → Role → Account 3 계층으로 조립하도록 재설계하고, Product 단위의 DB 접근 whitelist 를 agent tools 레벨에서 강제하도록 도입했다. `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` 신규 테이블과 `AgentCoreConversations.product_id` 컬럼을 추가해 모든 대화가 Product 컨텍스트에 귀속되고, `compose_system_prompt` 가 base SYSTEM_PROMPT 뒤로 `## PRODUCT CONTEXT` → `## ROLE GUIDANCE` → `## ACCOUNT PREFERENCES` 블록을 순차 append 한다. 관리 콘솔에는 `상품 카테고리` 그룹 구분선과 함께 `상품 (Products)` 탭(Product CRUD + 접근 DB chip + Product scope prompt 편집기) 이 추가되었고, Roles detail 에 Role scope prompt 편집기가, 프로필 드로우에 `프롬프트` 탭(Account scope) 이 각각 추가되었다. whitelist 정책은 TASK-0039 에서 메타데이터 4 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 를 Product 설정과 무관하게 항상 bypass 하도록 재조정했다 — agent 의 DB 구조 탐색을 보장하면서도 `agent_memory` 차단은 유지해 타 계정 데이터 노출을 막는다. TASK-0046 (REQ-20260425-0001) 에서 프로필 드로어의 API Vault 탭을 Linear Wizard 3-step 구조로 재설계하고 키 갈아끼움 진입점을 "저장된 키 삭제" → confirm → wizard 재진입 → 새 입력 → 저장 1 경로로 단일화했다.

## 2. Progress
- Planned: Phase 2 P2 (sessions/me filter, end-user FE chip filter), F8 (admin lockout 보호) — 별 cycle 분리
- In Progress: TASK-0052 Phase 1B/1C/1D + Phase 2 P0 완료, TASK-0034 복잡 QA 성능 테스트 (Q4/Q5 재수행 — TASK-0040/0041/0046 선행 완료 상태)
- Done: TASK-0052 Phase 1A (4dd1d0a), TASK-0051 관리 콘솔 일괄 저장, TASK-0050 make web buildx race 회피, TASK-0049 누적 빈 대화 일괄 정리, TASK-0048 lazy "새 대화", (이전 항목 below)
- Done: TASK-0050 make web buildx race 회피, TASK-0049 누적 빈 대화 일괄 정리, TASK-0048 "새 대화" lazy 화, TASK-0047 Product Selector + Auto 모드, TASK-0046 API Vault 패널 Linear Wizard 재설계, TASK-0041 클라이언트 타임아웃 시 Attach/Resume, TASK-0040 schema whitelist 정규식 context-aware 수정, TASK-0039 메타데이터 스키마 whitelist bypass 정책, TASK-0036 System Prompt Depth + Product DB whitelist, TASK-0035 대화 사이드바 구분/정렬 + 대화/말풍선 fork, (이전) RBAC table cutover, role CRUD, account role assignment, tri-state override, account soft delete, own/any 대화 권한 분기, 제목 변경 API, `clear_memory` 제거, `console.access` 기반 읽기 전용 관리자 셸, 브라우저/API 검증

## 3. Recent Changes
- 2026-05-15 (TASK-0060): Product prompt 2건 + Role common prompt 5건 DB upsert. DB 분석 결과: `KR` 주요 구조는 `dbgame`(현재 상태) / `dblog`(대용량 로그) / `dbauth`(인증·기기), `MV` 주요 구조는 `account_db`(계정) / `dev_1_1_1_20`(기준정보) / `have_00`(보유·매치 이력) / `global_db`(서버·이벤트) / `log_v2`(테이블 0개). Role common prompt 누적 적용을 위해 feature-0002 `compose_system_prompt()` 수정 및 테스트 추가.
- 2026-05-08 Git 동기화 (PR #2 + PR #3 → main)
  - **PR #2** (`feat/adopt-external-anchor-v3.2.0-rc` → `main`, merge commit `eafe4c2`): 72 commits / 137 files / +28320 / -9018. TASK-0046~0053 + 정책 v3.6.0 진화 + 빈 대화 누적 차단 + 관리 콘솔 일괄 저장 회복. main 의 v3.0.0 마이그레이션 commit (`639130b`) 와 본 브랜치의 v3.6.0 진화 conflict (10 files: AGENTS.md / CONTRIBUTING.md / unit/_template/docs/TASK.md / docs/{CODEBASE_MAP,LEARNINGS}.md / playbooks/{PB-0001~0004,README}.md) 는 §3.2 + §16.6 자율 해결 원칙에 따라 본 브랜치(v3.6.0) 우선으로 합병 commit `ae53965` 생성. CI 의 `policy-contract` fail (브랜치 `feat/*` 가 `issue/<번호>-<short-slug>` 자동화 계약 외) + `selfhosted-runtime-smoke` fail (runner 의 `repo-agent` 이미지 누락) + `ai-review` fail (워크플로우 heredoc EOF delimiter 버그) 은 모두 PR 본문 자체와 무관한 인프라 이슈로 사용자 직접 지시 (§3.1 우선순위 1) 에 따라 admin merge 수행.
  - **PR #3** (`issue/1-github-bootstrap` → `main`, merge commit `3fd4272`): 단일 commit `38702cd` — self-hosted runner + 로컬 claude CLI 전환. 머지 전 main 의 `.github/workflows/{ai-execute,ai-review,ai-triage}.yml` 이 `runs-on: ubuntu-latest` + `anthropics/claude-code-action@v1` 로 남아있어 commit 메시지의 "Pro/Max OAuth 토큰이 2026-02-20 이후 거부" 회귀가 노출된 상태였다. 머지 후 main 의 ai-execute.yml 이 `runs-on: [self-hosted, linux]` + 로컬 `claude -p ...` 호출로 정렬됨을 확인 — 운영 정합성 회복.
  - **누적된 main 상태**: `3fd4272` ← `eafe4c2` ← `ae53965` ← `d9272a8` (TASK-0053 follow-up) ... ← `639130b` (이전 main 끝).
  - **feat 브랜치 후속**: main 대비 behind 3 (PR #2/PR #3 의 merge commits + ae53965 가 feat 에 없음). feat 에서 추가 작업 시 `git pull origin main` 또는 rebase 로 catch-up 권고.

- 2026-05-07 (TASK-0053 follow-up, CHG-20260507-0001, REV-20260507-0001)
  - **Issue 1 (UI 뒤틀림 fix)**: `.admin-list-row.has-pending::before { content: ""; }` placeholder rule 이 CSS Grid 의 4번째 grid item 으로 참여해 cb/main/chips 의 column/row 위치가 어긋나던 버그. DOM 좌표 분석으로 확인 (수정 전 cb x=70 column 2, chips x=11 y=73 row 2 col 1 / 수정 후 cb x=11 column 1, chips x=270 column 3 — row 1 정상). pseudo-element 자체 제거 + `.admin-list-row.has-pending { border-color }` 로 시각 표시 유지.
  - **Issue 2 (제품 카드 위치)**: `buildRoleProductCardList(role, disabled, opts={embed})` / `buildAccountProductOverrideList(account, disabled, opts={embed})` 시그니처에 embed 옵션 추가. `renderRoleDetail` / `renderAccountDetail` 가 `permWrap/overrideWrap.querySelector('details[data-perm-group="product"]')` 로 product 그룹 details 를 찾아 그 안에 product 카드 list 를 append (없으면 fallback). embed=true 모드에서는 별도 section title 생략 (부모 details summary 의 "제품" 라벨과 중복 회피), hint 단축.
  - **CSS**: `.admin-product-card-list-embedded` 신규 변형 (margin-top + padding-top + dashed border-top) — 부모 details 안에서 정적 권한과 시각적 분리.
  - **검증**: node --check + make web 재배포. DOM 좌표 검증 (sales row 정상 + product group 안에 cards 3 개). screenshot 으로 시각 확인.
  - **다음 단계**: 운영 사용 시점에 동일 패턴 (grid 의 ::before pseudo 가 grid item 으로 참여) 의 회귀 방지 — LEARNINGS.md 등재 권고.

- 2026-05-06 (TASK-0053, REQ-20260506-0006, CHG-20260506-0027, REV-20260506-0014)
  - **backend (Phase A — Product 주체)**: `WebProducts.DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 신규 컬럼. POST `/api/admin/products` body 에 `default_role_access` 수용 + INSERT 시 컬럼 set + transaction 내 backfill 분기. PATCH `/api/admin/products/{id}` 에서도 수용. `_list_products` SELECT/응답에 포함. `_ensure_product_access_permissions(conn)` (catchup) 의 backfill SQL 이 product 의 `DefaultRoleAccess` 값 따라 분기.
  - **backend (이전 시도 정리)**: `WebRoles.DefaultProductAccess` 관련 코드 제거 — `_load_role_by_id`/`_list_roles` SELECT/GROUP BY/응답 dict 에서 컬럼 삭제, `admin_update_role` 의 body 수용/UPDATE 컬럼 제거. 컬럼 자체는 destructive DROP 회피로 DB 잔존 (다음 cleanup cycle 에서 DROP COLUMN).
  - **frontend (Phase A)**: Product detail 에 토글 1 row 추가 ("신규 역할 자동 접근"). `merged.default_role_access` + `setProductMetaPending` + `applyAllPending` 의 productMeta PATCH body + `describePatchKeys` 라벨. Role detail 의 토글은 제거 (이전 시도 잔재 — mergedRole/setRolePending/applyAllPending/startNewRole 모두 정정).
  - **frontend (Phase B)**: `groupedPermissions(opts={excludeDynamic})` + `dynamicProductPermissions()` 헬퍼 신설. `renderPermissionGrid` 가 옵션 통과. Role detail 과 Account detail 의 grid 호출이 `excludeDynamic: true` 로 dynamic `product.access.*` 분리. onChange 핸들러는 dynamic 권한들 union 으로 보존.
  - **frontend (Phase C)**: `buildRoleProductCardList(role, disabled)` 신설 — product 별 collapsible card 안에 access 토글 + role-scope system prompt textarea (fixedProductId=Number(id)) 묶음. "전 Product 공통" generic card (fixedProductId=0) 마지막에. `buildAccountProductOverrideList(account, disabled)` 신설 — product 별 flat card 에 override select. Role detail 의 단일 buildSystemPromptEditor 호출은 product 카드의 textarea 로 흡수.
  - **styles.css**: `.admin-product-card-list` / `.admin-product-card` (open 상태 / head / toggle / info / body / flat / generic) 스타일 추가. 토큰 사용.
  - **admin.html**: cache-bust `v=20260506-c5-product-cards`.
  - **검증**: py_compile + node check + make web 재배포. Schema (`DESC WebProducts` 에 DefaultRoleAccess 추가) + role API 에서 default_product_access 제거 + /api/admin/products 에 default_role_access 노출 확인. **Phase A E2E smoke**: 신규 product DE (`default_role_access=false`) → 6 role 모두 grant 0, JP (`=true`) → 6 role 모두 grant. **Phase B/C DOM smoke** (browse): admin-product-card 정상 카운트, 권한 grid 에서 dynamic 코드 제외 확인.
  - **다음 단계**: 운영자 검토 — product 생성 시 토글로 정책 결정. 기존 product 의 정책 변경은 PATCH /api/admin/products 의 default_role_access 변경 (단, 기존 grant 는 보존). `WebRoles.DefaultProductAccess` 컬럼 잔재는 다음 cleanup cycle 에서 DROP COLUMN.

- 2026-05-06 (TASK-0052 Phase 1B/1C/1D + Phase 2, REQ-20260506-0005, CHG-20260506-0026, REV-20260506-0013)
  - **backend (Phase 1B)**: `unit/feature-0003-agent-web-ui/src/app.py` — `_resolve_permission_catalog(conn=None)` body 를 DB-driven 으로 교체 (정적 + WebPermissions IsDynamic=1 union, graceful fallback). `_product_permission_code` / `_ensure_dynamic_permissions_schema` / `_ensure_product_access_permissions` 헬퍼 신설. bootstrap (slow + fast path) 에서 자동 backfill. caller 7 곳 (account list / role survivor / admin update / list_roles / load_role_by_id / role create / role update) update.
  - **backend (Phase 1B 트랜잭션, Codex Claim 2)**: `POST /api/admin/products` 와 `DELETE /api/admin/products/{id}` 가 `conn.autocommit=False` + 명시적 commit/rollback. POST 는 product+permission row+role grant 한 트랜잭션, DELETE 는 cascade (SystemPrompts/ProductDatabases/RolePermissions/AccountPermissionOverrides/Permissions/Products) 한 트랜잭션.
  - **backend (Phase 1C, G1-G8 8 가드)**: `_account_has_product_access(account, product_id_or_key, *, conn=None)` 단일 진입점. G1 PATCH conv product / G2 new_conversation / G3 ask body hint / G4 ask 기존 conv product_id_for_run (Codex Claim 3 핵심) / G5 fork + product_mode 'auto' 보존 fix (Codex Claim 4) / G6 _save_account_product_pref defense-in-depth / G7 GET sysprompt / G8 PUT sysprompt — 권한 없으면 403.
  - **backend pre-existing 버그 fix**: `admin_update_account` 가 `target.get("role")` (항상 None) 으로 fallback 해 PATCH 마다 RoleId=0 으로 덮어쓰던 회귀를 `target.get("role_id")` 직접 조회로 fix. body 에 role_id 미명시인 PATCH 가 더 이상 admin role 손상 안 함.
  - **frontend (Phase 1D)**: `unit/feature-0003-agent-web-ui/src/static/admin.js` — `PERMISSION_GROUP_ORDER += "product"`, `PERMISSION_GROUP_LABELS["product"] = "제품"`. 기존 renderPermissionGrid 가 자동으로 'product' 그룹 (정적 product.manage / system_prompt.manage.role.any + 동적 product.access.<key>) 노출.
  - **markup**: `unit/feature-0003-agent-web-ui/src/static/admin.html` cache-bust `v=20260506-c5-product-perms`.
  - **운영 transparency**: bootstrap stderr `[TASK-0052 Phase 1B catchup] product access backfill: 7 permission/role-permission rows added` 메시지 (1 perm row + 6 role grants — 모든 6 role 에 KR access 자동 grant, D2-A 호환성 우선).
  - **검증 (Phase 2 P0)**: (a) `python3 -m py_compile` PASS / `node --check admin.js` PASS / `make web` 재배포. (b) `/api/admin/permissions` count 33 → 34 (KR 추가) → POST FR 후 35 → DELETE FR 후 34 복귀. (c) admin effective `product.access.kr=True` (D2-A backfill). (d) deny override 후 G1/G2/G7/G8 모두 HTTP 403. (e) cleanup 후 admin 34/34 회복. (f) admin_update_account RoleId 보존 fix 검증: PATCH override 후 role 'admin' 보존, 33/34 true. G3/G4 는 model validation 단계 차단으로 정적 코드 검증으로 대체 (G1/G2 와 동일 패턴).
  - **NOT in scope (별 cycle)**: Phase 2 P2 (`/api/sessions/me` filter, end-user FE chip filter), F8 (admin lockout 보호 survivor 로직 확장).
  - **다음 단계**: 운영자 검토 — D2-A 호환성 backfill 로 모든 role 이 KR 에 default-grant 상태. 권한 회수가 필요한 (role × product) 조합은 admin 콘솔의 deny override 로 적용 (`PATCH /api/admin/accounts/{id}` body `{"permission_overrides":{"product.access.kr":"deny"}}` 또는 admin UI 의 권한 grid).

- 2026-05-06 (TASK-0052 Phase 1A, REQ-20260506-0005, CHG-20260506-0025, REV-20260506-0012)
  - **backend (RBAC engine refactor)**: `unit/feature-0003-agent-web-ui/src/app.py` — `Iterable` import 추가, 신규 `_resolve_permission_catalog(conn=None)` 헬퍼 (Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 반환, Phase 1B 가 conn 으로 WebPermissions union), 5 함수 시그니처 확장 (`_empty_permission_map`/`_apply_permission_overrides`/`_validate_permission_codes`/`_normalize_override_payload`/`_permission_catalog_payload` 모두 catalog kwarg 추가, default None = 기존 정적 사용 → 회귀 0).
  - **plumbing 검증 endpoint**: `/api/admin/permissions` (L5761) 만 신규 경로 (`_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=...)`) 로 전환. Phase 1B 의 DB-driven 전환 surface 를 미리 검증. 다른 callsite (account list / role detail 의 `_apply_permission_overrides` 등) 는 Phase 1B 에서 caller-update.
  - **검증**: (a) `python3 -m py_compile` 통과. (b) `make web` 재배포 (`repo-web-1 Recreated/Started`). (c) `docker exec repo-web-1 grep -c "_resolve_permission_catalog\|catalog_codes" /app/web/app.py` → 17 hits. (d) bootstrap_admin login + `/api/admin/permissions` HTTP 200 + count=33 codes (이전과 정확히 동일, 첫 3 `console.access`/`console.manage`/`account.read`, 마지막 3 `conversation.finalize.any`/`product.manage`/`system_prompt.manage.role.any`).
  - **Plan 정본**: [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). Phase 1A 는 briefing §4 의 1A 항목 ✓.
  - **다음 단계**: Phase 1B (WebPermissions IsDynamic/ProductId 컬럼 + 제품 권한 backfill SQL + `_resolve_permission_catalog(conn)` body 를 DB query 로 교체 + 다른 callsite caller-update). 별 cycle 진입 권장.

- 2026-05-06 Git 동기화 결과 (commit 85f674d)
  - 커밋: `85f674d` (`feat/adopt-external-anchor-v3.2.0-rc`) — TASK-0048/0049/0050/0051 + 정책 변경 흡수 + verify-completion §4 strip fix 32 files / +2493 / -295.
  - verify-completion: PASS (pre + post-commit 모두 6/6)
  - Push: 완료 — `git push origin feat/adopt-external-anchor-v3.2.0-rc` 정상 (`a7122f8..85f674d`)
  - PR: 보류 — 현재 브랜치 `feat/adopt-external-anchor-v3.2.0-rc` 는 internal feat/* 형식이라 `docs/GITHUB_AUTOMATION.md` 의 공개 PR 브랜치 규칙(`issue/<번호>-<short-slug>`) 에 부합하지 않고 GitHub issue 가 본 cycle 에 묶이지 않았다. 사용자가 이미 origin 에 같은 이름으로 작업 중인 internal develop 브랜치라 push 만 진행. PR 전환은 별도 issue 발급 + `issue/*` 통합 시 진행.
  - 병합 상태: 수동 검토 — internal feat/* 브랜치이므로 자동 merge 후보 아님.
  - 충돌 해결: 없음.

- 2026-05-06 (TASK-0048 후속 fix, CHG-20260506-0024)
  - **버그 보고**: 사용자 보고 — "대화 삭제 시 새 대화가 그대로 남는 이슈". 사용자가 active 대화를 삭제했는데 사이드바에 또 빈 대화가 등장.
  - **근본 원인**: backend `_repair_current_conversation` 의 호출처 5 곳이 `create_if_missing=_account_has_permission(account, "conversation.create")` 로 자동 생성하던 분기. 특히 `/api/delete_conversation` 응답의 `current` 필드가 자동 생성된 새 cid 였고 frontend 가 그것을 active 로 채택해 사이드바에 다시 등장. 또 `_build_conversations_payload` (`/api/conversations`), `/api/session`, `/api/history` 의 conv resolver 도 동일하게 자동 생성 중이라 사용자가 어떤 경로로 list 를 fetch 해도 빈 대화가 자동으로 나타날 수 있었다 — TASK-0048 의 lazy 정책을 backend 가 우회하던 회귀.
  - **fix**: 호출처 5 곳을 `create_if_missing=False` 로 일괄 전환 (`/api/ask` 의 lazy creation 단일 경로만 `True` 보존). lazy 정책을 backend 전 경로에 일관 적용.
  - **검증**: HTTP API 시나리오 (a) `/api/conversations` 호출 시 row delta=0, (b) `/api/session` 호출 시 delta=0, (c) `/api/new_conversation` 으로 빈 대화 1건 생성 후 즉시 `/api/delete_conversation` → 응답 `{"deleted":"...","current":""}`, row delta=-1 (이전엔 자동 생성된 새 cid 가 current 에 들어와서 net delta=0 으로 빈 대화가 또 생기던 것). frontend 는 current="" 를 받으면 헤더 "대화를 선택하세요" + 사이드바 empty-state 로 떨어진다.
  - **회귀 표면**: 마지막 대화를 삭제한 사용자에게 backend 가 자동으로 새 대화를 만들어주지 않는다 — 의도된 결과. 사용자가 "새 대화" 버튼을 명시적으로 눌러야 한다 (TASK-0048 lazy 정책의 일관성).

- 2026-05-06 (TASK-0051, REQ-20260506-0004, CHG-20260506-0023, REV-20260506-0011)
  - **frontend (admin)**: `unit/feature-0003-agent-web-ui/src/static/admin.js` — `adminState.pending` 에 `productMeta` / `productDatabases` / `systemPrompts` 3 buckets 추가 + `availableDatabases` 캐시 추가. `setProductMetaPending` / `setProductDatabasesPending` / `setSystemPromptPending` / `getSystemPromptPending` 헬퍼 신설. `pendingChangeCount` / `refreshPendingUI` / `cancelAllPending` / `loadAdminData` 가 신규 buckets 합산·표시·clear·GC 흐름에 합류. `applyAllPending` 6 단계로 확장 (productMeta PATCH → productDatabases PUT → systemPrompts PUT 3 단계 추가).
  - **frontend (admin) — 인라인 save 제거**: `renderProductDetail` 의 `saveMetaBtn` (제품 정보 저장) / `saveDbBtn` (DB 목록 저장) 두 버튼 제거. `buildSystemPromptEditor` 의 `saveBtn` (프롬프트 저장) / `clearBtn` (비우기) 두 버튼 제거. 모두 입력 변경 시 즉시 pending 등록 + footer "모두 적용" 단일 commit 흐름에 통합.
  - **frontend (admin) — 메타데이터 locked chip + DB picker**: 제품 detail 의 chip wrap 에 메타 4 종(`information_schema`/`mysql`/`sys`/`performance_schema`) 을 `is-locked` 클래스 + `항상 접근` 소형 라벨 + tooltip 으로 강제 prepend (× 버튼 없음). 자유 텍스트 chip 입력을 `<select>` picker (loadAdminData 시점의 user_schemas 스냅샷 + 메타·`agent_memory`·이미 등록된 schema 제외) 로 교체.
  - **frontend (admin) — system prompt textarea pending**: 안내 한 줄 ("변경사항은 하단 '모두 적용' 버튼으로 일괄 저장됩니다") 추가. textarea `input` 이벤트 → `setSystemPromptPending`. `refresh()` 가 pending entry 우선으로 textarea 값 복원해 reload race 방지.
  - **frontend (admin) — dashboard pending**: `dashboardPendingList` 에 "제품 정보" / "제품 DB" / "프롬프트 (제품/역할/계정)" 3 카테고리 row 추가. `describePatchKeys` 에 `is_default`/`sort_order` 라벨 추가.
  - **backend**: `unit/feature-0003-agent-web-ui/src/app.py` 신규 `GET /api/admin/databases/available` 엔드포인트. `console.access` 게이트 후 `_open_memory_connection(database=None)` 으로 `SHOW DATABASES` 실행, `metadata_schemas`(고정 4 종 + `present` flag) / `user_schemas`(메타·`agent_memory`·`MEMORY_DB`·정규식 위반 제외 + 정렬) 분리 반환. 모듈 상수 `_DATABASES_AVAILABLE_METADATA` / `_DATABASES_AVAILABLE_INTERNAL` / `_DATABASES_AVAILABLE_NAME_RE` 추가.
  - **markup/style**: `admin.html` cache-bust `v=20260506-batch-commit` (styles.css, admin.js). `styles.css` 에 `.admin-chip.is-locked`, `.admin-chip-locked-hint`, `.admin-db-picker-row`, `.admin-db-picker` (+ disabled 상태) 추가. 토큰(`--text-muted`/`--border-subtle`) 만 사용.
  - **검증**: (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과. (b) `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` 통과. (c) `grep` 으로 3 개 인라인 save 버튼 라벨/핸들러 변수 모두 admin.js 에서 0 hit. (d) `/api/admin/databases/available` 가 FE/BE 양쪽 1 hit. **컨테이너 재빌드(`make web`) + 브라우저 UX smoke 는 사용자 환경에서 진행 예정** (재빌드 후 cache-bust 가 반영되어야 신규 admin.js 가 로드됨).
  - **C5 분리**: 계정·역할 → 제품 권한 상속/override 모델은 다음 cycle 분리. 사유: 신규 테이블 2 개(`WebRoleProductAccess`/`WebAccountProductAccessOverrides`) + 기존 RBAC override 모델(TASK-0024) 우선순위 합성 정의 + `compose_system_prompt` product 조회 경로 영향 분석이 필요. 진입 전 `/plan-eng-review` 권고.


- 2026-05-06 (TASK-0050, REQ-20260506-0003, CHG-20260506-0022)
  - **build infra**: `repo/Makefile` — `dc-build SERVICE=...` reusable 가드 타깃 추가 + `web` 타깃을 `dc-build SERVICE=web` + `up -d --no-build web` 2단계로 분리. docker compose v5.1.1 + buildx v0.31.1 의 provenance metadata file race 를 흡수 (image 빌드는 정상 + 로그에 `compose-build-metadataFile` 포함될 때만 EXIT=0 정규화).
  - **검증**: `make web` EXIT=0, `[make] note: ...provenance metadata file race 우회...` 메시지, `Container repo-web-1 Recreate/Recreated/Started`, `Web UI (HTTPS)` 노출 + 새 코드 deploy 확인.

- 2026-05-06 (TASK-0049, REQ-20260506-0002, CHG-20260506-0021)
  - **cleanup**: `repo/bin/cleanup-empty-conversations.sh` 추가 (executable). dry-run 기본 + `--execute` 명시 시 DELETE, processing 보호 + 최근 N분 보호 + owner-account 옵션. SQL 주입 방지 정수 정규식 검증.
  - **운영 적용**: dry-run 으로 `would_delete=42` 확인 후 `--execute` 로 정리. 결과: 88 conversations / 42 empty / 46 non-empty → 46 conversations / 0 empty / 46 non-empty.
  - **idempotent**: 향후 재실행 시 추가 누적이 없으면 0 건 정리됨 (TASK-0048 이 신규 누적을 차단하므로).

- 2026-05-06 (TASK-0048, REQ-20260506-0001, CHG-20260506-0020, REV-20260506-0010)
  - **frontend**: `unit/feature-0003-agent-web-ui/src/static/app.js` — `state.pendingNewConversation` + `PENDING_CONV_SENTINEL` 도입, `beginPendingConversation()` 신설, `renderConversationList()` 가 pending placeholder 를 "내 대화" 그룹 상단에 prepend, `renderConversationHeader()` 가 pending 시 "새 대화" + 부제 표시, `selectConversation()` 이 pending 자동 종료, `sendPrompt()` 의 lazy create 분기가 `/api/ask` body 에 `product_mode`/`product_id` hint 첨부, 응답 `conversation_id` 채택 후 pending 종료, lazy create 단계 ask 실패는 attach 다이얼로그 대신 재시도 토스트. `newConversationBtn.click` 핸들러를 `createConversation()` → `beginPendingConversation()` 로 교체.
  - **backend**: `unit/feature-0003-agent-web-ui/src/app.py` `/api/ask` 의 lazy creation 분기 (`request_conversation_id` 비어 있을 때) 에 body `product_mode`/`product_id` hint 수용 + `AgentCoreConversations.product_id/product_mode` 셋업 + `_save_account_product_pref` 호출. 기존 대화 경로(`request_conversation_id` 명시) 는 hint 무시 — `PATCH /api/conversations/{cid}/product` race 가드 단독 진실 보존. hint 적용 실패는 ask 자체를 막지 않고 default fallback.
  - **markup/style**: `index.html` cache-bust `v=20260506-pending-conv` (styles.css, app.js). `styles.css` 에 `.conv-item.is-pending` 1 selector 그룹 추가 (border-dashed + faded text + cursor:default, 토큰만 사용).
  - **검증**: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`, `node --check unit/feature-0003-agent-web-ui/src/static/app.js` (재빌드 단계).
  - **후속 처리 완료** (TASK-0049, TASK-0050 으로 분리 마감):
    - 누적된 빈 대화 일괄 정리: TASK-0049 로 진행 (88→46, 42 정리). `bin/cleanup-empty-conversations.sh` 가 영구 도구로 남음 (idempotent — 신규 누적 없으면 0건).
    - `make web` 운영 검증 차단 이슈: TASK-0050 의 Makefile dc-build 가드로 해결. 본 cycle 에서 새 코드를 운영 컨테이너에 deploy 검증.
  - **남은 후속 작업**:
    - lazy create 단계 ask 실패 시 buried orphan (backend cid 발급 후 client 모름) 케이스를 자동 회수하는 경로는 본 turn 에 의도적 미구현 — 사용자에게 사이드바 새로고침으로 위임. 향후 attach API 를 cid 없이 trigger 할 수 있도록 확장 시 검토.
    - frontend 시각 검증 (§8.2 강제 검증): Playwright spec 또는 dogfooding 으로 (1) 새 대화 버튼 클릭 → 사이드바 placeholder 등장 + network round trip 0회 확인, (2) 첫 메시지 전송 → cid 채택 + product hint backend 반영 확인, (3) pending 상태에서 다른 대화 선택 → placeholder 사라짐, (4) pending ask 실패 시 토스트 안내. **API key 환경 + 브라우저 접근이 필요해 본 turn 의 코드 inspection + 컨테이너 deploy 검증 후 사용자 dogfooding 으로 위임.**

- 2026-04-30 (TASK-0047 후속 검증, CHG-20260430-0019, REV-20260430-0009)
  - **버그 수정**: `_runtime_tables_available` 가 테이블만 검사하던 fast-path 에 신규 컬럼(`product_mode`/`ProductPrefMode`/`ProductPrefPinnedId`) probe 와 errno 1054 분기를 추가해, 기존 배포에서 신규 컬럼 마이그레이션이 자동 트리거되도록 했다 (BRIEFING R-09 closed).
  - **Playwright QA 28-check** 작성 및 실행 — `repo/.gstack/qa-reports/qa-product-selector.cjs`. 결과: 28/28 PASS, healthScore=100, console.error=0. PATCH 4 케이스 / new_conversation 2 케이스 / UI select 인터랙션 / hydrate / **PATCH race guard (last_status='processing' → 409)** 모두 자동 검증.
  - 빌드 학습: `docker compose --build` 가 BuildKit layer cache 로 `COPY src/...` 단계를 stale 하게 잡는 케이스를 만나 `docker compose build --no-cache web` 으로 강제 재빌드. LEARNINGS 후보.

- 2026-04-29 (TASK-0047, agent team 4 합의 + Codex CLI 교차검증)
  - `unit/feature-0002-agent-core/src/agent_core.py` — `compose_system_prompt(... ,product_mode='pinned'|'auto')` 분기 추가 (auto 시 `[AUTO MODE]` 한 줄 inject + product 한정 prompt 건너뜀, role/account scope 는 `ProductId IS NULL` fallback 만 사용). `run_agent`/`_run_agent_core` 시그니처에 `product_mode` 전달.
  - `unit/feature-0003-agent-web-ui/src/app.py` — DDL 2 컬럼(AgentCoreConversations.product_mode, WebAccounts.ProductPrefMode/ProductPrefPinnedId), 헬퍼 5종(`_normalize_product_mode`, `_load_account_product_pref`, `_save_account_product_pref`, `_load_conversation_product`, `_conversation_is_processing`), `/api/session` 응답 확장(`product_pref`, `conversation_product`), `/api/new_conversation` body 확장(`mode`, pref upsert), `/api/ask` 분기(mode='auto' → product_id None + allowed_schemas=[]), 신규 `PATCH /api/conversations/{cid}/product` (권한·소유자·race 가드).
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — 사이드바 헤더에 product chip 추가, cache-bust `?v=20260429-product-selector`.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.product-chip*` 스타일 신설(70 줄), mobile ≤720px 분기.
  - `unit/feature-0003-agent-web-ui/src/static/app.js` — state 3-필드 분리, `renderProductOptions`/`renderProductChip`/`applyProductHydration`/`setActiveProduct`/localStorage 헬퍼 6종 신규, `initializeWorkspace`/`refreshWorkspace`/`selectConversation`/`createConversation`/`renderComposer`/`initialize` 흐름에 hydrate + lockout + select change 바인딩 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`, `admin.js`, `unit/feature-0003-agent-web-ui/src/app.py` — "상품" → "제품" 일괄 치환 (코드 식별자 보존).
  - 문서: `docs/TASK.md` §2/§3.1 갱신, `docs/MODIFY.md` CHG-20260429-0018, `docs/REVIEW.md` REV-20260429-0008, `docs/REPORT.md` (this), 신규 `docs/BRIEFING-product-selector-v1.md` (R-01..R-16 + D-01..D-05).
  - 검증: `python3 -m py_compile` (app.py / agent_core.py), `node --check src/static/app.js` 모두 통과. in-process `compose_system_prompt` auto 분기 테스트 통과.

- 2026-04-25 (TASK-0046, REQ-20260425-0001)
  - `src/static/index.html`
    - L246-L334 vault 패널 markup 재구성: `vault-banner` (readiness tri-state) + `ol.vault-stepper > li.vault-step × 3` (Step 1 사용할 API 키 / Step 2 passphrase / Step 3 암호화 후 저장) + `vault-saved` (information only) + `vault-danger-zone` ("저장된 키 삭제" 1 개) + `details.vault-advanced` (cipher 직접 붙여넣기, 기본 접힘). cache-bust `v=20260425-vault-final`.
  - `src/static/styles.css`
    - L1420-L1582 신규 클래스: `.vault-banner` / `.vault-banner-dot[data-state]` / `.vault-stepper` / `.vault-step[data-state="active|done|disabled"]` / `.vault-step-num` / `.vault-step-head/title/body/hint` / `.vault-saved` / `.vault-danger-zone` / `.btn-danger-link` / `.vault-advanced[-body]` (약 170 줄).
  - `src/static/app.js`
    - vault state helper 군 재작성: `updateVaultStatus` → `updateVaultReadiness` rename + `computeVaultReadiness` 의 진실 출처를 input value 에서 storage 로 통일. `syncVaultSteps` 가 `cipherSaved` 만으로 saved-default ↔ wizard 입력 모드 전환. `renderVaultSavedCard` 가 saved card + danger zone 동시 hidden 토글. saveVault 흐름이 평문 → encrypt → cipher 채움 → localStorage 저장 한 줄로 통합. `clearVaultBtn` 핸들러에 `confirm("저장된 암호화 키를 삭제할까요? ...")` 가드 추가.  신규 `vaultImportCipherBtn` 핸들러로 `v1:` prefix 검증 후 ciphertext 직접 import. **단일 진입점 정책**: `vaultReplaceBtn` / `replacingVault` flag / `enterReplaceMode` / `cancelReplaceMode` 모두 제거 — 키 갈아끼움 경로 1 개만 유지.
  - 검증: `repo/.gstack/qa-reports/qa-vault.cjs` (Playwright Node) 28/28 PASS, healthScore 100, console.error 0 건. 사용자 직접 브라우저 검증 4 시나리오(저장 완료 / 새로고침 / 삭제 후 새 키 입력 / confirm 취소) 모두 만족.
  - 문서: `docs/TASK.md` §1/§2 갱신, `docs/MODIFY.md` CHG-20260425-0017, `docs/REPORT.md` (this), `docs/REQUEST.md` (REQ-20260425-0001 Outcome) → `docs/REQUEST_ARCHIVE.md` move.

- 2026-04-22 (TASK-0041)
  - `src/app.py`
    - `_ASK_TERMINAL_STATUSES = frozenset({"done","error","canceled"})` / `_ASK_SUCCESS_STATUSES = frozenset({"done","canceled"})` 상수
    - `_load_run_meta_kv(conn, cid)` — `AgentMemoryKv` 의 5 키(`last_status` · `last_status_at` · `last_status_run_id` · `last_duration_ms` · `last_error`) 를 단일 쿼리로 조회
    - `_build_ask_status_snapshot(conn, cid)` — `{conversation_id, is_processing, status, status_at, run_id, step_count, duration_ms, error, has_answer, answer_preview, _latest_assistant}` 스냅샷 빌더
    - `GET /api/ask_status` — 1-shot. 권한 `conversation.read.own/any`. 응답은 `_latest_assistant` 제외(long-poll 전용)
    - `GET /api/ask_result?conversation_id=&run_id=&wait=<=60` — long-poll. `deadline=loop.time()+wait_s`, `poll_interval=0.5`. terminal 시 assistant dict 반환, 시간 초과 시 `{timeout:true, run_id?}`. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 분리되어 attach 가 새 실행을 시작시키지 않는다.
  - `src/static/app.js`
    - 상수 `ASK_ATTACH_POLL_WAIT_SEC=45` / `ASK_ATTACH_MAX_TOTAL_SEC=1800`
    - `fetchAskStatus(cid)` — 실패 시 null 반환하는 안전 래퍼
    - `showTimeoutRecoveryDialog({statusText})` — 3 버튼 모달(`요청 취소`/`즉시 답변`/`계속 기다리기`) + Escape dismiss. 인라인 스타일로만 구성되어 HTML/CSS 변경 없이 동작
    - `attachAndWaitForResult(cid, {runId})` — `/api/ask_result?wait=45` long-poll 루프, run_id 한 번 고정, terminal 시 `refreshWorkspace(cid)` + 토스트. 최대 1800s
    - `sendPrompt()` — `apiFetch("/api/ask",...)` 를 try/catch 로 감싸 실패 시 `fetchAskStatus` → `is_processing=true` 이면 다이얼로그 → 사용자 선택에 따라 `/api/cancel`·`/api/finalize` 호출 후 `attachAndWaitForResult` 로 이어받음
    - `initializeWorkspace()` 끝에 boot-time auto-attach — 페이지 로드 시 현재 대화가 `is_processing=true` 이면 자동으로 busy 상태 + progress polling + attach 재개, "이전에 남아있던 응답 요청을 이어받습니다." 토스트
  - `tests/task0034_runner.py`
    - 상수 `ATTACH_TIMEOUT_SEC=960.0` / `ATTACH_POLL_WAIT_SEC=45`
    - `_steps_from_attach(meta)` 헬퍼
    - `_attach_run(client, cid, message, t0)` — ask_status 로 run_id/initial_status 확보 → ask_result long-poll 반복 → turn dict 에 `attached_after_timeout=True` + `attach_verdict` + `attach_run_id`/`attach_initial_status` 메타 기록
    - 기존 `httpx.ReadTimeout` 분기: `{"error":"client-read-timeout"}` 반환 대신 `_attach_run(...)` 로 정상 복구
  - 검증: py_compile 3 파일 통과, `node --check app.js` JS OK, `make web` 재빌드 후 새 이미지(sha256:665515...) 반영, `/api/ask_status` / `/api/ask_result` 401 응답으로 라우팅 확인, terminal 상태 스냅샷 38ms, `python3 tests/task0034_runner.py --target api --only Q4,Q5` 재수행 실행
  - 문서: `docs/TASK.md` §1/§2 + TASK-0041 상세 설계 블록(1236 라인대) + Completion Checklist 체크, `docs/MODIFY.md` CHG-20260422-0014, `docs/REVIEW.md` REV-20260422-0007, `docs/FUNCTION.md` 에 신규 2 엔드포인트, `../../docs/LEARNINGS.md` LRN-20260422-0013(작업자 스레드 lifecycle ≠ 클라이언트 연결)

- 2026-04-22 (TASK-0040)
  - `../feature-0002-agent-core/src/modules/tools.py`
    - `_SCHEMA_TABLE_REF_RE` 단일 단계 regex 를 제거하고 `_TABLE_LIST_RE` + `_INNER_REF_RE` 2 단계 스캐너로 교체.
      - 1 단계: `\b(?:FROM|JOIN)\b(.*?)(?=\bON\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b|\bLIMIT\b|\bUNION\b|\bJOIN\b|\bFROM\b|;|\)|$)` (IGNORECASE|DOTALL) — FROM/JOIN 키워드 다음 절 시작 직전까지의 테이블 리스트 구간만 slice
      - 2 단계: slice 내부에서만 `\`?(schema)\`?\s*\.\s*\`?(table)\`?` 패턴으로 schema 토큰 추출
    - SELECT/WHERE/ON 절의 alias.column 토큰은 FROM/JOIN slice 바깥이라 더 이상 매칭되지 않는다.
  - 검증: in-process 15 테스트 케이스 (단일 FROM / FROM+WHERE alias.col / FROM+JOIN+alias.col ON / 혼합 schema / 백틱 / subquery / 비허용 schema 차단 / SELECT 절 alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / 중복 refs dedup) 전부 expected refs 일치. Q4-like SQL 은 `{dblog}` 만 검출, `_whitelist_violation` 이 `{dbauth,dbgame,dblog}` whitelist 에서 None 반환. 비허용 `dbstat.foo` 는 여전히 차단.
  - 문서: `docs/TASK.md` §1/§2 + TASK-0040 상세 설계 블록 + Completion Checklist 체크, `docs/MODIFY.md` CHG-20260422-0013, `docs/REVIEW.md` REV-20260422-0007(TASK-0040/0041 통합), `../../docs/LEARNINGS.md` LRN-20260422-0012(SQL 정규식 문맥 의존성)

- 2026-04-22 (TASK-0039)
  - `../feature-0002-agent-core/src/modules/tools.py`
    - L24~33 `_SYSTEM_SCHEMAS` 단일 frozenset 을 `_METADATA_SCHEMAS = {information_schema, sys, mysql, performance_schema}` (whitelist bypass) + `_INTERNAL_SCHEMAS = {agent_memory}` (whitelist 차단 유지) 두 frozenset 으로 분리. `_SYSTEM_SCHEMAS` 는 union 으로 유지해 `_is_user_schema`/`search_tables` UX 필터 동작 보존.
    - L81~103 `_whitelist_violation` 의 `allowed = set(_ACTIVE_SCHEMA_ALLOWLIST) | {"information_schema"}` 를 `_METADATA_SCHEMAS` 전체로 확장. 차단 에러 메시지에 "메타데이터 스키마(information_schema/sys/mysql/performance_schema) 는 항상 접근 가능" 안내를 추가.
  - 검증: 컨테이너 in-process 8 케이스(whitelist=None / 메타데이터 4 종 bypass / 허용 user schema / 혼합 통과 / agent_memory 차단 / 비허용 user schema 차단 / `_is_user_schema` UX 필터 보존) + `execute_tool` 경로로 information_schema / performance_schema / sys / mysql / agent_memory / 비허용 user schema 각 케이스 기대 동작 확인. `mysql.user` tool-level bypass 후 실제 행 반환(MySQL GRANT 열림) → REV-20260422-0006 에 2 차 방어 필요성 기록.
  - 문서: `docs/TASK.md` §1/§2/§3.1 + TASK-0039 상세 설계, `docs/MODIFY.md` CHG-20260422-0012, `docs/REVIEW.md` REV-20260422-0006 (REV-20260421-0005 일부 supersede), `docs/FUNCTION.md` AC-0010 보강.

- 2026-04-22 (TASK-0038)
  - `../feature-0002-agent-core/src/agent_core.py`
    - L26~32 `from modules.config import` 에 `AGENT_OPENAI_MAX_RETRIES` 추가
    - L1134~1139 `client = OpenAI(**client_kwargs)` → `OpenAI(**client_kwargs, timeout=max(5,int(AGENT_TIMEOUT_SEC)), max_retries=max(0,int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장. OpenAI SDK client-level timeout 이 내부 httpx 에 상속돼 `chat.completions.create` 모든 호출에 wall-clock 상한이 걸린다.
  - `tests/task0034_runner.py`
    - L52~56 `ASK_TIMEOUT_SEC=600.0` → `ASK_TIMEOUT_SEC=960.0` 및 산정 근거 주석(`max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)=900s` + 60s buffer) 추가. 서버가 항상 클라이언트보다 먼저 자기-타임아웃을 친다.
  - 검증: `docker compose up -d --force-recreate web` 후 bootstrap_admin 로그인 + `gpt-5.4-mini` 간단 질의 `/api/ask` HTTP 200, wall=5s, steps=1, list_schemas 정상.

- 2026-04-22 (TASK-0037, 문서화 전용)
  - `/api/progress` 폴링 루프 리팩터(27127b9, TASK-0036 번들) 에 대한 사후 리뷰 및 학습 기록. 코드 변경 없음.
  - 검증: `grep -c "setInterval" src/static/app.js` = 0, 5개 적응형 상수(`PROGRESS_FETCH_TIMEOUT_MS=4000` / `PROGRESS_POLL_ACTIVE_MS=1200` / `PROGRESS_POLL_IDLE_MS=3000` / `PROGRESS_POLL_HIDDEN_MS=10000` / `PROGRESS_POLL_ERROR_MS=8000`) 모두 `scheduleProgressPolling`/`pollProgress` 에서 실제 참조, 서버 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 파라미터를 수용하고 서버 최신 run_id 와 불일치 시 `next_after_step=0` 으로 리셋(app.py:4405-4406).
  - 문서: `docs/TASK.md` §2/§3.1 + TASK-0037 상세 설계 블록, `docs/MODIFY.md` CHG-20260422-0010, `docs/LEARNINGS.md` LRN-20260422-0011(장시간 작업 폴링 5원칙).

- 2026-04-21 (TASK-0036)
  - `../feature-0002-agent-core/src/agent_core.py`
    - `compose_system_prompt(mem_conn, *, product_id, role_id, account_id)` 신규. `WebSystemPrompts` 에서 scope=product → role → account 순으로 조회해 base `SYSTEM_PROMPT` 뒤에 `## PRODUCT CONTEXT ({ProductKey})` / `## ROLE GUIDANCE ({RoleKey})` / `## ACCOUNT PREFERENCES` 블록을 append. role/account 는 `ProductId=X` 우선, 없으면 `ProductId IS NULL` fallback
    - `run_agent(...)` 는 `allowed_schemas` + `product_id`/`role_id`/`account_id` kwargs 를 받는 얇은 래퍼로 재구성, 본문은 `_run_agent_core` 로 rename. try/finally 로 `set_active_schema_allowlist`/`clear_active_schema_allowlist` 세팅/복원
  - `../feature-0002-agent-core/src/modules/tools.py`
    - 모듈-전역 `_ACTIVE_SCHEMA_ALLOWLIST: set[str]|None = None` + `set_active_schema_allowlist()` / `clear_active_schema_allowlist()` / `_whitelist_violation(refs)` / `_extract_sql_schema_refs(sql)` 신규
    - 모든 DB 도구(`execute_sql`, `explain_query`, `describe_schema`, `describe_table`, `search_tables`, `get_sample_rows`, `get_table_indexes`, `get_foreign_keys`, `list_schemas`) 가 호출 직전 스키마 참조를 `_whitelist_violation` 으로 검사. `execute_sql` 은 `schema.table` 정규식 추출
    - `_is_user_schema` 에 whitelist 교집합 조건 추가 → `list_schemas` 출력 post-filter
    - 보안 수정: `_whitelist_violation` 에서 `_SYSTEM_SCHEMAS` bypass 제거. `information_schema` 만 예외(스키마 카탈로그 조회 용도)
  - `src/app.py`
    - 신규 테이블 `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` CREATE (idempotent) + `AgentCoreConversations.product_id` ALTER. `_runtime_tables_available` probe list 에 신규 3 테이블 포함(기존 배포 자동 마이그레이션)
    - `PERMISSION_DEFINITIONS` 에 `product.manage` / `system_prompt.manage.role.any` 추가 및 기존 admin 역할에 보정 부여, `SEED_PRODUCT_DEFINITIONS` 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) seed, `_ensure_seed_products()`
    - 신규 헬퍼: `_get_default_product_id`, `_list_products`, `_product_allowed_schemas`, `_load_system_prompt`, `_upsert_system_prompt`
    - 신규 admin API: `GET/POST/PATCH/DELETE /api/admin/products`, `PUT /api/admin/products/{id}/databases`, `GET/PUT /api/admin/system-prompts`
    - 신규 self API: `GET/PUT /api/auth/me/system-prompt`
    - `/api/new_conversation`, `/api/fork_conversation` 가 `AgentCoreConversations.product_id` 를 (body.product_id → 원본 product_id → default) 순으로 해석/기록
    - `/api/ask` 가 대화 `product_id` 해석 → `_product_allowed_schemas` 로 whitelist 추출 → `run_agent(..., product_id=, role_id=, account_id=, allowed_schemas=)` 호출
    - 세션 응답(`/api/session`, `/api/auth/me`) 에 `products` / `default_product_id` 추가
  - `src/static/admin.html`
    - `계정 카테고리` / `상품 카테고리` 그룹 라벨 + 구분선 추가, 신규 `상품 (Products)` 탭 + `<section data-admin-pane="products">` 추가 (master-detail). cache-bust `v=20260421-sysprompt`
  - `src/static/admin.js`
    - `adminState.products/productSearch/selectedProductId/productDbDraft` 확장
    - `renderProductList()` / `renderProductDetail()` / `startNewProduct()` / `filteredProducts()` 신규
    - 공용 `buildSystemPromptEditor({scope, productId, roleId, accountId, fixedProductId, title, hint})` — Product scope / Role scope / Account scope 편집기 공통 렌더러
    - Role detail 에 Role scope prompt 편집기 통합 (권한 `system_prompt.manage.role.any` 게이트)
    - `loadAdminData()` 가 `/api/admin/products` 도 조회, `refreshPendingUI()` 가 `tabCountProducts` 갱신, `initialize()` 에서 productSearch/newProductBtn 이벤트 바인딩
  - `src/static/index.html`
    - 프로필 드로우 탭에 `프롬프트` 추가 + `<div data-profile-pane="prompt">` (Product 드롭다운 + textarea + 저장/초기화) 신규. cache-bust `v=20260421-sysprompt`
  - `src/static/app.js`
    - `state.products` / `state.default_product_id` 도입 및 세션 bootstrap 에 연동
    - `fetchAccountPromptRow(productId)` / `initAccountPromptEditor()` / `saveAccountPrompt(forceDelete)` 추가, profile 탭 전환 시 `prompt` 탭이 열리면 `initAccountPromptEditor()` 실행
  - `src/static/styles.css`
    - `.admin-tab-group-label`, `.admin-tab-group-divider`, `.admin-chip-wrap`, `.admin-chip`, `.admin-chip-remove`, `.admin-chip-input-row`, `.admin-prompt-textarea`, `.admin-inline-row`, `.admin-detail-hint` 추가

- 2026-04-21 (TASK-0035)
  - `src/app.py`
    - `POST /api/fork_conversation` 추가 (new_conversation 바로 아래, L3192). body: `{source_conversation_id, from_message_id?}` → 응답 `{conversation_id, source, copied, from_message_id, topic}`
    - 권한: `conversation.create` + `_account_can_access_conversation(..., read.own/read.any)`. 위반 시 403, 원본 미존재 404, 빈 body 400
    - 원본 topic (`AgentCoreConversations.topic` 우선, fallback `AgentMemoryKv.topic`) 에 `[Fork] ` 접두사 추가. `AgentMemoryMessages` 는 `(ConversationId, Role, Content, CreatedAt, MetaJson)` 을 **원본 CreatedAt 그대로** 재삽입, `MetaJson.forked_from_conversation_id` / `forked_from_message_id` 추가. `_is_internal_message` 은 skip.
    - 중간 실패 시 `delete_conversation_records(conn, new_cid)` 로 롤백
    - 성공 시 `_set_account_current_conversation` 으로 새 대화를 활성화
  - `src/static/index.html`
    - `chat-header-tools` 에 `#forkConversationBtn` ("대화 복사") 추가
    - `styles.css`, `app.js` 의 cache-bust 쿼리를 `v=20260421-fork` 로 갱신
  - `src/static/app.js`
    - `renderConversationList` 이 `state.conversations` 을 `own` / `others` 로 파티션 → `.conv-group-title` 헤더("내 대화" / "타 계정 대화 (N)") + `.conv-item.is-own` / `.is-other` / `.conv-owner-badge` 노출
    - `renderMessages` 가 대화 소유 계정 기준으로 `is-own-message` / `is-other-message` 클래스 + `나 (<username>)` / `<owner_username>` meta 라벨 적용, 각 메시지에 호버 시 노출되는 `여기서 분기` 버튼 삽입
    - 신규 `forkConversation({fromMessageId})` + `forkConversationBtn` wiring, `renderComposer` 에서 fork 버튼 가시성/disabled 제어
  - `src/static/styles.css`
    - `.conv-group-title`, `.conv-item.is-own` (primary 좌측 바 + 틴트), `.conv-item.is-other`, `.conv-owner-badge.is-own/.is-other` 추가
    - `.message.is-user.is-own-message` / `.is-other-message` 톤 분기, `.message-actions` / `.message-action-btn` (호버 시 opacity 상승 pill 액션) 추가

- (이전) RBAC cutover (CHG-20260416-0007)
  - `src/app.py`
    - `WebPermissions`, `WebRoles`, `WebRolePermissions`, `WebAccountPermissionOverrides`를 기준으로 최종 권한을 계산하도록 재구성
  - legacy `Role`/`Can*` 컬럼은 마이그레이션 원본으로만 사용하고, cutover 후 런타임 read/write 경로에서 분리
  - `GET/PATCH/DELETE /api/admin/accounts`, `GET/POST/PATCH/DELETE /api/admin/roles`, `GET /api/admin/permissions`를 새 RBAC 계약으로 재작성
  - `PATCH /api/conversations/{conversation_id}/title` 추가. 대화 조회/제목 변경/삭제/중단/즉시답변/파일 조회를 `own`/`any` 권한으로 재배선
  - `conversation.ask`는 자신의 대화 또는 새 대화에만 허용하고, 타 계정 대화 이어쓰기는 차단
  - 계정 삭제는 soft delete(`IsActive=0`, `DeletedAt`, `DeletedByAccountId`, 세션 폐기)로 고정
  - `/api/clear_memory`를 410으로 전환하고 legacy `clear conversations` 계약을 런타임에서 제거
- `src/static/index.html`, `src/static/app.js`, `src/static/styles.css`
  - 세션 payload의 role을 문자열이 아닌 `{ id, key, name }` 구조로 소비하고, 버튼 노출은 최종 permission만 기준으로 처리
  - 관리자 콘솔 버튼, rename/delete/cancel/finalize 버튼, 접근 안내 문구를 `console.access`, `conversation.*` 권한에 맞춰 재구성
  - 현재 대화가 own/others 인지에 따라 제목 변경/삭제 버튼이 반영되도록 렌더링 로직 추가
- `src/static/admin.html`, `src/static/admin.js`
  - `Accounts` 섹션에서 role 선택, 활성/비활성, soft delete, tri-state override 매트릭스를 제공
  - `Roles` 섹션에서 role 생성/수정/삭제, 기본 가입 역할 지정, permission checklist를 제공
  - `console.access`만 있는 계정도 `/admin` 셸은 열 수 있고, object read 권한이 없으면 읽기 전용 빈 상태를 표시
- 문서
  - `docs/TASK.md`, `docs/REPORT.md`, `docs/MODIFY.md`, `docs/TEST.md`를 새 RBAC 계약과 검증 결과 기준으로 갱신
  - `docs/STATUS.md`에 feature-0003 최신 갱신일과 개편 요약을 반영

## 4. Open Issues
- 없음

## 5. Notes
- legacy `Role`/`Can*` 컬럼은 DB 스키마에 남아 있지만, 현재 런타임은 새 RBAC table만 읽고 판단한다. 컬럼 drop migration은 별도 DB 정리 과제로 분리한다.

## 6. Test Status
- 코드 문법 검증: `python3 -m py_compile src/app.py`, `node --check src/static/app.js`, `node --check src/static/admin.js`
- 정적/검색 검증:
  - 휴리스틱 금지 grep: `ACCOUNT_ROLE_*`, `is_admin`, `is_pending`, `_normalize_role(...)`, legacy `can_*` 권한 판정 경로가 런타임에 남지 않았는지 확인
- TASK-0035 전용 HTTP 검증 (2026-04-21):
  - bootstrap_admin 로그인 후 `POST /api/fork_conversation {source_conversation_id: "20260421075518-571abdb6"}` → HTTP 200, `copied=6`, 새 대화 `20260421082459-c039abbd`, topic `[Fork] dblog 에서 ... `
  - 같은 계정에서 `{source_conversation_id, from_message_id: 153}` → HTTP 200, `copied=3`, 새 대화 `20260421082523-d9fbb21b`
  - 새 대화의 `/api/history` 응답에서 3개 메시지가 `meta.forked_from_message_id = 146, 152, 153` 으로 추적되는지 확인
  - 인증 없는 호출은 401, 빈 body 는 400, 존재하지 않는 source 는 404 반환 확인
- HTTP 검증:
  - bootstrap admin 로그인 후 role 목록/permission catalog/account 목록 조회
  - 임시 기본 signup role 생성 후 회원가입 계정의 기본 role 자동 부여 확인
  - `console.access` 단독 계정이 `/api/admin/permissions`는 조회 가능하지만 `/api/admin/accounts`, `/api/admin/roles`는 403인지 확인
  - account role assignment + override allow/deny 적용 후 최종 permissions가 기대값과 일치하는지 확인
  - `conversation.list.any`/`read.any` 허용 계정이 타 계정 대화를 조회할 수 있고, `conversation.ask`는 타 계정 대화에 이어쓰기 할 수 없는지 확인
  - `conversation.rename.any` override 후 타 계정 대화 제목 변경 가능 여부 확인
  - `/api/clear_memory`가 410을 반환하는지 확인
  - 마지막 관리 가능 계정/role 보호 규칙이 빈 permission set 갱신을 차단하는지 확인
  - soft delete 후 로그인 차단과 기존 세션 폐기 확인
- 브라우저 검증:
  - 관리자 로그인 후 `/admin` 진입, role 생성/수정/기본 가입 역할 전환 확인
  - 브라우저 회원가입 계정에 기본 signup role이 반영되는지 확인
  - 관리자 콘솔에서 계정 role을 `pending -> custom role -> pending`으로 바꿀 수 있는지 확인
  - own conversation에서 제목 변경/삭제 버튼이 노출되는지 확인
  - 타 계정 대화는 `read/list.any`만 있을 때 버튼이 숨겨지고, `rename/delete.any` 허용 후 버튼이 노출되는지 확인
  - 삭제된 계정이 `deleted` 필터에 표시되고, 삭제된 role이 역할 목록에서 제거되었는지 확인
  - 삭제된 계정 브라우저 로그인 차단 확인
  - 스크린샷:
    - `/shared/out/browser/rbac_admin_home_76309029.png`
    - `/shared/out/browser/rbac_admin_roles_76309029.png`
    - `/shared/out/browser/rbac_user_own_76309029.png`
    - `/shared/out/browser/rbac_user_other_76309029.png`

## 7. Blocked Items
- 없음

## 8. Human Attention Needed
- `.env`에 추가한 `WEB_BOOTSTRAP_ADMIN_USERNAME`, `WEB_BOOTSTRAP_ADMIN_PASSWORD`는 현재 개발 부트스트랩용 값이다. 실제 운영 전에는 반드시 교체해야 한다.
- **TASK-0051 후속: 컨테이너 재빌드 + UX smoke** — `make web` 재빌드 후 `/admin` 진입해 (i) 메타 4 종 chip 회색 + × 없음 / (ii) DB picker 옵션 채워짐(메타·`agent_memory` 제외) / (iii) 제품 detail 의 name·desc·active·default·sort 입력 변경 시 footer 카운트 증가 / (iv) `+ 추가` / chip × / textarea 변경이 footer 단일 commit 으로 수렴 / (v) 시스템 프롬프트 textarea 변경이 productSelect 전환 후에도 보존 / (vi) `취소` 클릭 시 모든 신규 buckets clear 를 확인.
- **C5 (TASK-0052) 본체 cycle 완료 (2026-05-06)** — 운영자 검토 필요: D2-A 호환성 backfill 로 모든 6 role 이 KR 제품에 default-grant. 본 cycle 의 보안 효과 (G1-G8 가드) 가 실효를 발휘하려면 운영자가 권한 회수가 필요한 (role × product) 조합에 admin 콘솔 deny override 를 적용해야 함. 참고: [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). `/plan-eng-review` (Section 1~4) + Codex outside voice (gpt-5.5, reasoning=high) 통합. 핵심 결정: D1-B (권한 코드 + 기존 override 재사용 — 단 RBAC engine DB-driven 마이그레이션을 C5 본체로 흡수) / D2-A (호환성 우선 backfill, **NOT secure-by-default** — 마이그레이션 report 후 운영자 검토) / D3-A (Product CRUD 자동 연동 + 명시적 트랜잭션) / D4 변경 (Codex Claim 6 수용: end-user `/api/session` filter + admin `/api/admin/products` 전체 유지). Codex 가 9 finding 을 catch — 그 중 5 개가 plan 골격을 흔드는 critical (정적 catalog 가정 / autocommit 기본 / 기존 conv `product_id_for_run` 가드 누락 / 추가 endpoint 4 곳 가드 / info 노출). 30 test case (smoke + DOM + negative HTTP) 정의. 다음 cycle 진입 시 TASK-0052 발급 + briefing 의 §3-§5 를 TASK.md §2.1 로 채택. **Phase 1A (RBAC engine 마이그레이션) 은 product 권한 도입 없이 단독 deploy 가능** — 분리 commit 권장.
