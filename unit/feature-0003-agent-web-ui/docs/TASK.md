---
doc_type: TASK
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in_progress
- Owner: AI
- Priority: medium
- Last Updated: 2026-05-15

## 2. Task Queue
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0070, Minor §12.3 — admin list-detail grid row hotfix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0069, Minor §12.3 — admin workspace flex hotfix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0068, Minor §12.3 — admin layout 정합) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0067, Minor §12.3 — 제품 칩 composer 이전) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0066, Minor §12.3 — UI layout 재구조화) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0065, Minor §12.3 — UI 정리 follow-up) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0063, Major §12.3) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-15 -->
- [x] TASK-0070 (REQ-20260518-0008, Minor §12.3 — admin list-detail grid row hotfix of TASK-0069) 사용자 2 차 screenshot 보고: `역할` / `제품` 등 항목이 적은 pane 에서 큰 viewport (height 800+) 의 경우 list-col / detail-col box 가 viewport 의 일부만 차지하고 그 아래 회색 빈 영역. 항목이 많은 `계정` (26 row) 또는 좁은 화면에서는 content 가 row 채워 정상. 원인: `.admin-list-detail` 의 grid-template-rows 미정의 → default auto → row height = content. align-items: stretch 는 row 내부 column 분배만 담당 — row 자체 height 결정 X. Fix: `grid-template-rows: minmax(0, 1fr)` 추가 (1 줄). 검증: 큰 viewport (1320x900) 에서 listDetail h=682, listCol/detailCol h=682 (이전 ~200), cbar viewport bottom sticky. screenshot 첨부. cache-bust `v=20260518-admin-list-rows`.
- [x] TASK-0069 (REQ-20260518-0007, Minor §12.3 — admin workspace flex hotfix of TASK-0068) 사용자 screenshot 보고: admin `역할 관리` (및 다른 list-detail pane) 에서 commit-bar 가 workspace content 바로 아래에 좁게 위치하고 그 아래로 큰 회색 빈 영역. 원인: TASK-0068 에서 commit-bar 를 admin-shell grid → admin-column flex column item 으로 이전한 후 `.admin-workspace` 의 `flex: 1` 명시 누락 → flex column 안에서 workspace 가 자기 content 만큼만 차지. Fix: `.admin-workspace` 에 `flex: 1 1 auto` 추가 (1 줄). 다른 속성 무변경. 검증: DOM `wsBottom=659 / cbarTop=659 / commitBarAtBottom=true / workspaceTouchesCommitBar=true` → list-detail 이 column 의 남은 height 전부 차지 + commit-bar viewport bottom sticky. screenshot 첨부. cache-bust `v=20260518-admin-workspace-flex`.
- [x] TASK-0068 (REQ-20260518-0006, Minor §12.3 — 관리 콘솔 layout 정합 + 미사용 버튼 정리) TASK-0066 / 0067 follow-up. 사용자 명시 — 관리 콘솔의 사이드바 구성을 작업 화면과 동일하게 (ChatGPT 패턴, sidebar 전체 height + admin-column) 정렬. 사용자 직접 테스트에서 거의 사용 안 되는 `새로고침` / `로그아웃` 버튼 제거. `.admin-shell` grid 가 2-row → 2-column (sidebar 220 | admin-column 1fr). `.admin-body` wrapper 폐기. `.sidebar-brand` (작업 화면과 동일 brand "MySQL AI") 가 `.admin-sidebar` 의 첫 영역. `.admin-column` (flex column) 안에 topbar (관리 콘솔 제목 좌측 정렬 + 부제 + "작업 화면" 버튼 우측) + workspace + commit-bar. `#refreshAdminBtn` / `#adminLogoutBtn` element + JS click handler 모두 제거 — 로그아웃은 작업 화면 프로필 drawer 에서 가능 (기능 손실 없음). 검증: DOM `refreshBtnPresent=false / logoutBtnPresent=false / backBtnPresent=true / brandInSidebar=true / adminColumnPresent=true / gridCols="220px 1060px"`. backend / RBAC / endpoint / 데이터 무변경. cache-bust `v=20260518-admin-layout`.
- [x] TASK-0067 (REQ-20260518-0005, Minor §12.3 — 제품 칩 composer 이전 + native select → custom drop-up dropdown) TASK-0066 follow-up. 사용자 명시 — ChatGPT 의 모델 선택 UI 패턴으로 제품 칩을 사이드바 → composer 의 textarea 우측 (sendBtn 직전) 으로 이전. 클릭 시 drop-up dropdown 으로 옵션 표시. 사이드바도 채팅 영역처럼 확장 효과. `.sidebar-head .product-chip-wrap` 제거, `.composer-box` 안에 `.composer-product-chip-wrap` (button#productChip + #productDropupMenu) 신설. 기존 native `<select id="productSelect">` 제거 → custom button + custom menu (drop-up 보장 위해). renderProductChip 재작성 + renderProductDropupMenu / buildProductDropupItem / openProductDropup / closeProductDropup 신설. backend endpoint `PATCH /api/conversations/{cid}/product` 호출 / setActiveProduct 본체 / RBAC / 데이터 영역 무변경. 검증: DOM `chipInComposer=true`, 기존 native select 부재, sidebar-head 가 "새 대화" 만, chip click → menu 4 items (auto + KR + MV + GZ_KR) 표시 + `dropUp=true` (menuY < chipY), KR item click → chip label "KR" + toast "제품을 킹스레이드로 바꿨어요" 정상. cache-bust `v=20260518-product-composer`.
- [x] TASK-0066 (REQ-20260518-0004, Minor §12.3 — ChatGPT 패턴 layout 재구조화) TASK-0065 follow-up. 헤더 4 버튼 제거로 비어 보이던 `.chat-header` 와 `.topbar` (관리 콘솔) 영역을 통합. 사용자 결정 (in-cycle 명시): topbar 에 대화 제목 통합 + 좌측 정렬 (중앙 정렬 금지) + brand `[MA] MySQL AI` 를 sidebar 영역으로 이전 (ChatGPT UI 패턴). `.app-shell` grid 를 row 2개 → column 2개 (sidebar | chat-column) 로 단순화. `.app-body` wrapper 폐기. `.sidebar-brand` 신설 (sidebar 첫 영역, height = topbar-h 로 baseline 정렬). `.chat-column` 신설 (topbar + chat-pane wrapper). `.chat-header` 폐기 — 채팅 영역 확장. `.topbar-info` (제목/부제 좌측 정렬) + `.topbar-tools` (loadMoreBtn) + `.topbar-end` (관리 콘솔 우측). 반응형 mobile (max-width: 680px) 분기도 정렬. JS 변경 0 — 모든 element ID 보존. backend / RBAC / endpoint / 데이터 영역 무변경. 검증: DOM `.app-shell.gridTemplateColumns = "252px 1028px"`, `.sidebar-brand` mount, `.topbar.height = 52px`, 기존 `.chat-header` DOM 부재. browser screenshot 으로 ChatGPT 패턴 정확 구현 확인.
- [x] TASK-0065 (REQ-20260518-0003, Minor §12.3 — UI 정리 follow-up of TASK-0063) 사용자 직접 테스트 피드백 3 항목: (1) 헤더의 "대화 복사 / 공유 / 제목 변경 / 삭제" 4 버튼이 좌측 conv-item "···" menu 와 중복 → 헤더에서 제거 (cancel/finalize 만 유지). (2) "···" trigger 우측 상단 위치가 conv-item 의 "내/sales" badge 와 시각 충돌 → 우측 하단 (`bottom: 6px; right: 6px`) 으로 이전, `.conv-item` 에 `padding-right: 32px` 보정. (3) 캘린더 시간 이동 trigger 가 분기선 click 인데 사용자가 분기선까지 미리 scroll 해야 하는 불편 → Slack 패턴으로 분기선에 `position: sticky; top: 0` 적용 — 현재 시야의 날짜 그룹 헤더가 항상 messageLog 상단에 stick. hover affordance 는 기존 색상 변경 유지 + box-shadow 로 elevation 강화. backend / RBAC / endpoint 변경 0. 검증: node --check + make web 재배포 + browser headless smoke (헤더 4 버튼 부재 / trigger DOM position 확인 / `scrollTop = 600` 시 sticky 분기선 viewport 상단 stay screenshot).
- [x] TASK-0063 (REQ-20260518-0001, **Major** §12.3 — RBAC catalog 확장 2 + 신규 endpoint 1 + 파괴적 액션 menu 통합) 작업 화면 대화 항목별 "···" menu (복사 / 공유 / 제목 변경 / 삭제) + 캘린더 시간 이동을 채팅 로그 날짜 분기선 click trigger 로 이전. ChatGPT / Slack UX 패턴. 사용자 in-cycle 결정 4 항목: (1) 복사 = full self-fork (`_fork_conversation_impl` 재활용), (2) 신규 권한 `conversation.duplicate.own/.any` 분리 추가, (3) 헤더 share 유지 (dual entry), (4) 헤더 calendar 제거 + 분기선 단일 trigger + popover header ‹ › « » nav (« » 는 데이터 1년 이상일 때만). Codex outside voice review 10 risk 보강 (catchup loop 일반화, share-token bypass 차단 = read-gate 명시, 404 metadata leak 차단, .any superset semantics, frontend hide-vs-disable = rename/delete pattern 채택, PERMISSION_LABELS/DESCRIPTIONS/requiredPermissionsFor 3 곳 갱신, grapheme-safe 사본 제목). Catchup 순서 fix — `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출을 `_ensure_seed_roles` 앞으로 이동 (기존 순서는 _permission_id_map 이 신규 권한 id=0 받아 admin/operator/sales catchup skip). 검증: py_compile + node --check + make web 재배포 + DB 직접 grant 확인 (admin .any+.own / operator .own / sales .own) + browser headless smoke (menu 4 항목 + 분기선 click → popover anchored + 월 nav 동작).
- [x] TASK-0062 (REQ-20260515-0011 / REQ-20260515-0012, Minor §12.3) GOAL 2026-05-15 후속: (1) 내 대화 다중선택 UX 개선 — `.conv-item-checkbox` DOM 제거, Ctrl/Shift modifier 만 다중 선택 허용, 2 개 이상 선택 시에만 bulk bar 표시, 일반 click 은 단일 선택 + `state.conversationSelected.clear()`. (2) Point rail dot 위치를 `messageLog.scrollHeight` 기준 비례 분포로 재배치 — `.message-point-rail` 이 `position: relative`, dot 이 `position: absolute; top: <pct>%; transform: translate(-50%, -50%)`. `layoutMessagePointRail()` 헬퍼가 `renderMessagePointRail` + resize 에서 재계산. 검증: node --check 통과, make web 재배포, browser smoke (single click → 다중 선택 해제 / Ctrl click 2개 → bulk bar 표시 / point rail dot 의 top% 가 message scrollHeight 비례). cache-bust `v=20260515-task-0062`.
- [x] TASK-0061 (REQ-20260515-0003 ~ REQ-20260515-0010, **Major** §12.3 — UI 상태 / auth(비밀번호 초기화) / 파괴적 데이터(bulk delete) 일괄 변경) GOAL.md 8 항목 합본 cycle. **/qa round 2 심층 검증 완료 (2026-05-15, CHG-20260515-0004)** — Phase 4 Point rail dot click smooth scroll + active dot id 갱신, Phase 5 캘린더 월 이동 + day click → 시각 list 모두 정상. Phase 3/6/8 destructive endpoints 는 운영 환경 사용자 명시 시점에 실 호출 검증 권고. round 2 신규 이슈 0 건. 답변 버블 내부 실시간 step 진행 (Phase 1) + 신규 대화 첫 요청 polling 즉시 연결 (Phase 2) + processing 만료 감지 + 붉은 badge (Phase 3) + 우측 Point rail (Phase 4) + 캘린더/시각 이동 (Phase 5) + 관리자 비밀번호 초기화 (Phase 6) + admin select-all 현재 페이지 fix (Phase 7) + 내 대화 Ctrl/Shift bulk delete (Phase 8). 상세 plan-review 는 §2.1 Implementation Plan (TASK-0061). **사용자 승인 요청 시점**: §2.1 Plan 확정 후 Phase 6 (Critical 분면 — 비밀번호 초기화, 인증 모델 영향) 진입 전. Phase 1~5, 7, 8 (Major) 는 plan-review 통과 후 Execute.
- [x] TASK-0060 (REQ-20260515-0002, Minor §12.3) Product별 접근 가능 DB의 실제 스키마/데이터를 분석해 Product scope 시스템 프롬프트를 작성하고, Role detail 의 `전 Product 공통` 프롬프트를 역할명에 맞게 채움. 분석 대상: `KR(킹스레이드)` 접근 DB `dbgame,dblog,dbauth`, `MV(마이크로볼츠)` 접근 DB `account_db,dev_1_1_1_20,have_00,log_v2,global_db`. `log_v2`는 DB는 존재하지만 테이블 0개로 확인. 실제 DB에는 product prompt 2건 + role 공통 prompt 5건(`pending/operator/admin/sales/dba`) upsert 완료. runtime 의 누적 적용은 feature-0002 `compose_system_prompt()` 수정으로 보장.
- [x] TASK-0059 (REQ-20260515-0001, **Major** §12.3 — 사용자 대화 routing 데이터 영역, 인증/인가 모델 무변경) "새 대화" 버튼 누른 후 첫 메시지를 보내도 backend 가 직전 active 대화에 메시지를 추가하는 lazy-create routing 결함 수정. 사용자가 신규 대화 의도로 보낸 첫 메시지가 잘못된 대화 컨텍스트로 귀속되어 발견. **근본 원인**: frontend `beginPendingConversation()` 이 `state.activeConversationId=""` 로 두고 backend row 를 lazy 생성 위임하나 (TASK-0048 정책), `/api/ask` 의 빈 `conversation_id` 경로가 `_resolve_conversation_for_account` → `_repair_current_conversation` 으로 폴백해 `account.last_conversation_id` (직전 대화) 를 반환. frontend 의 "pending = 신규 의도" 가 backend 로 전달되지 않아 "session 초기화 후 직전 대화 이어받기" 와 구분 불가. **Fix Phase A**: frontend `sendPrompt()` 가 `isLazyCreate=true` 일 때 `askBody.lazy_create = true` 를 추가. **Phase B**: backend `_resolve_conversation_for_account(..., force_new=False)` kwarg 추가, `_repair_current_conversation` 의 기존 `force_new` 파라미터로 위임. `/api/ask` 의 빈 `request_conversation_id` 경로에서 `data.get("lazy_create")` 가 truthy 이면 `force_new=True` 호출. **Phase C**: frontend `loadConversations()` 의 `state.activeConversationId` 덮어쓰기에 `!state.pendingNewConversation` 가드 추가 — pending 모드 race 시 직전 대화로 복귀 차단. **Phase D**: MODIFY.md CHG-20260515-0001 + REVIEW.md REV-20260515-0001 기록.

### 2.1 Implementation Plan (TASK-0061)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Major 등급 변경 계획이다. **상태**: `approved`. 사용자가 2026-05-15 에 Phase 1~8 일괄 승인 + 비밀번호 초기화 권장안 (MustChangePassword + 임시비번 1회 표시 + 세션 revoke + self-reset 금지) 채택을 명시했다. 사용자의 명료화: "관리자 계정의 비밀번호 초기화가 아닌, 관리자 주관으로 특정 계정의 비밀번호를 초기화 하는 기능" — AC-0093 (self-reset 거부) 의도와 정합.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-15 (TASK-0061 Phase 1~8 일괄, Phase 6 Critical 분면 포함) -->

#### 영향 파일 요약

Backend:
- [src/app.py](../src/app.py) — Phase 3 (`_compute_display_status` + WEB_PROGRESS_STALE_TIMEOUT_SECONDS env + `/api/progress` / `/api/ask_status` / `/api/ask_result` / `_list_conversations` 일관 반영), Phase 5 (`/api/history_dates` 가 `AgentMemoryMessages` 기준으로 SELECT 변경), Phase 6 (`WebAccounts.MustChangePassword` ALTER + `_ensure_web_tables` / `_ensure_seed_catchup` idempotent helper + `POST /api/admin/accounts/{account_id}/password-reset` endpoint + `/api/auth/login` 응답에 `must_change_password` 추가 + `/api/auth/me` PATCH 가 비밀번호 변경 성공 시 `MustChangePassword=0`), Phase 8 (`_delete_conversation_impl` helper 추출 + `POST /api/delete_conversations` endpoint).

Frontend:
- [src/static/app.js](../src/static/app.js) — Phase 1 (`state.pendingBubble` + `renderPendingAssistantBubble()` + `applyProgressPayload()` 가 pending bubble 동시 갱신 + elapsed timer interval + `renderMessages()` 가 pending state 가 있으면 사용자 message + pending bubble 즉시 prepend), Phase 2 (`sendPrompt()` lazy-create 분기에서 pending bubble 진입 + `/api/ask` 응답 직후 polling start), Phase 3 (`renderConversationList()` 가 `display_status === "stale_error"` 시 `.is-stale-error` dot 사용 + tooltip), Phase 4 (`#messagePointRail` 컨테이너 + `renderMessagePointRail()` + scroll/click handler), Phase 5 (`historyCalendarBtn` + popover + `/api/history_dates` 호출 + `/api/history_anchor` jump), Phase 6 (`/api/auth/login` 응답에서 `must_change_password` 처리 — 강제 modal), Phase 8 (`state.conversationSelected: Set<string>` + `state.conversationLastClickIdx` + `conv-item-checkbox` 추가 + Ctrl/Shift click handler + `.conv-bulk-bar`).
- [src/static/admin.js](../src/static/admin.js) — Phase 6 (Account detail 에 `adminPasswordResetBtn` + modal 표시 + 임시 비밀번호 복사 액션), Phase 7 (accountSelectAll change handler 가 `filteredAccounts()` 의 `accountPage` slice 만 대상으로 변경 + `updateAccountSelectAllCheckbox()` 도 동일 helper 사용 + Roles/Products select-all 도 동일 정책 정합화).
- [src/static/index.html](../src/static/index.html) — Phase 4 (`#messagePointRail` 컨테이너), Phase 5 (`historyCalendarBtn` + popover container), 그 외 ID 추가.
- [src/static/admin.html](../src/static/admin.html) — Phase 6 (Account detail 의 `adminPasswordResetBtn` slot — `renderAccountDetail()` 에서 동적 mount 도 가능하지만 cache-bust 위치 정의).
- [src/static/styles.css](../src/static/styles.css) — Phase 1 (`.message.is-pending` + spinner + elapsed + step list 토큰), Phase 3 (`.conv-dot.is-stale-error` red 토큰), Phase 4 (`.message-point-rail` + `.message-point-dot`), Phase 5 (`.history-calendar-popover` + grid), Phase 6 (`.admin-password-reset-modal` + `.temp-password-display`), Phase 8 (`.conv-item-checkbox` + `.conv-bulk-bar`).

문서:
- `docs/FUNCTION.md` — 본 commit 에 REQ-20260515-0003 ~ 0010 + AC-0070 ~ AC-0107 이미 추가됨.
- `docs/TASK.md` — 본 §2.1 + Task Queue entry + Completion Checklist.
- `docs/MODIFY.md` — Phase 별 CHG entry (8 phase).
- `docs/REVIEW.md` — Phase 1 (호환 차원에서 `#progressCard` 유지 결정), Phase 3 (env 기본값 20 분 결정 근거 — 장시간 SQL/LLM 작업 고려), Phase 6 (1 회 표시 / 평문 저장 금지 / MustChangePassword 강제 / 세션 revoke / self-reset 금지 보안 정책 결정), Phase 7 (bulk delete partial success + ≥10 typed-confirm 결정), Phase 8 (bulk delete partial success 채택, rollback 미선택 사유).
- `docs/REPORT.md` — Phase 별 변경 요약 + git 동기화 결과 (§16.5 Step 6).
- `docs/TEST.md` — TEST 케이스 정의 (§2) rewrite + 실행 결과 (§3) append.
- 프로젝트 수준: `repo/.env.example` — `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` 추가, `repo/docs/STATUS.md` feature-0003 row 갱신, `repo/docs/SECURITY.md` 비밀번호 초기화 정책 1 줄 추가.

#### 접근 방법 (Phase 순서)

순서는 의존성 최소화 + 빠른 검증 가능성 기준으로 정렬했다. 각 Phase 끝마다 python compile + node --check 가능하도록 분할.

1. **Phase 3 (backend stale 감지) 먼저** — 가장 자족적인 backend 변경. helper + env 추가 + 3 endpoint 응답 + conversation list status. 검증: `/api/progress` HTTP 응답에 stale 가 정확히 들어가는지.
2. **Phase 1 (답변 버블 live progress)** — frontend 핵심. `state.pendingBubble` 자료구조 + render + applyProgressPayload 갱신 + elapsed timer + `renderMessages()` 분기. Phase 3 의 status 가 stale 일 때 pending bubble 에서도 오류 영역 노출.
3. **Phase 2 (신규 대화 첫 polling)** — Phase 1 의존. lazy-create 분기에서 pending bubble 진입 + `/api/ask` 응답 직후 polling start. 회귀: 기존 대화 ask 흐름은 변경 없음.
4. **Phase 4 (Point rail)** — Phase 1 의 message rendering 위에 build. scroll observer + click handler.
5. **Phase 5 (캘린더)** — Phase 4 와 무관. backend `/api/history_dates` 의 source table 변경 + frontend popover. timezone 은 server 의 DATE() 그대로 (UTC).
6. **Phase 7 (admin select-all fix)** — 자족적인 frontend bug fix. 그 다음 Phase 6 (Critical) 직전에 끊어서 사용자 confirm 요청.
7. **Phase 8 (bulk delete)** — backend helper + endpoint + frontend selection state + UI. 단건 endpoint 와 동일 가드 재사용.
8. **🛑 Phase 6 (비밀번호 초기화 — Critical confirm) 직전 STOP** — DB schema 변경 (`MustChangePassword`) + 인증 응답 contract 변경 + 임시 비밀번호 노출. 사용자 명시 confirm 받은 후 Execute.

#### 위험도 평가 (§12.3)

| Phase | 변경 영역 | 위험도 | 사전 승인 |
|------|-----------|--------|----------|
| Phase 1 | frontend UI 상태 추가 | Minor | plan-review 만 |
| Phase 2 | frontend lazy-create UX | Minor | plan-review 만 |
| Phase 3 | backend status helper + env | Major (운영 환경변수 + 표시 정책) | plan-review |
| Phase 4 | frontend UI 추가 | Minor | plan-review 만 |
| Phase 5 | backend SELECT source 변경 | Minor | plan-review (회귀 가능성) |
| Phase 6 | **인증 모델 + 비밀번호 + 세션 revoke** | **Critical** | **사용자 명시 confirm** |
| Phase 7 | frontend bug fix | Minor | plan-review 만 |
| Phase 8 | **파괴적 데이터 일괄 삭제 + 신규 endpoint** | **Major** | plan-review (cross-account leak 위험 없음 — owner 가드 보존) |

**전체 등급**: Major (Phase 1~5, 7, 8 은 plan-review 마커 부여로 Execute. Phase 6 는 별도 Critical confirm).

#### 검증 계획

각 Phase 종료 후:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
- (c) `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`

전체 완료 후:
- (d) `make web` — 컨테이너 재배포
- (e) browser 검증 (gstack `/browse` 또는 make browser-*) — 8 시나리오 (GOAL.md §5 필수 브라우저 확인 8 항목) 실측 + screenshot 첨부.
- (f) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

#### 미결정 사항의 결정 (GOAL.md §7)

| 항목 | 결정 | 사유 |
|------|------|------|
| 비밀번호 초기화: MustChangePassword vs 임시비번+revoke only | **MustChangePassword 채택** | GOAL.md 권장 + 보안 우위. 1 회 임시 비밀번호 + 세션 revoke + 다음 로그인 시 강제 변경 |
| `#progressCard` 유지 vs 축소 | **유지** | 호환성. 사용자별 collapsed 상태는 localStorage 보존 |
| bulk delete partial vs rollback | **partial success + 결과 요약** | admin bulk UX 일관성 (AC-0035 와 정합) |
| stale 만료시간 기본값 | **1200 sec (20 분)** | 장시간 SQL/LLM 작업 고려한 보수적 기본값. env 로 override 가능 |

#### 사용자 승인 마커

Phase 1~5, 7, 8 (Major) 진행 승인 시 본 plan 의 PLAN-APPROVED 마커는 §2 Task Queue 의 기존 마커를 재사용한다 (사용자가 이미 GOAL.md 의 진행 의도를 명시함). Phase 6 (Critical) 진입 직전 별도 마커:
```md
<!-- PLAN-APPROVED-PHASE-6 by <user> on YYYY-MM-DD -->
```

### 2.1 Implementation Plan (TASK-0060)

영향 파일 / 데이터:
- `agent_memory.WebSystemPrompts` — Product prompt 2건, Role 공통 prompt 5건 upsert
- `../feature-0002-agent-core/src/agent_core.py` — Role 공통 prompt 누적 적용
- `../feature-0002-agent-core/tests/test_compose_system_prompt.py` — 누적 적용 회귀 테스트
- `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md` 및 feature-0002 문서

접근 방법:
1. `WebProducts`와 `WebProductDatabases`에서 Product별 접근 DB 목록을 확인한다.
2. 각 접근 DB에 대해 `information_schema.TABLES/COLUMNS`와 제한적 집계 쿼리로 테이블 수, 주요 테이블, 시간 범위, 민감 컬럼 성격을 확인한다.
3. 확인한 사실만 Product scope 시스템 프롬프트에 반영한다. 비밀번호/토큰/기기 식별자 등 민감 컬럼은 원문 노출 금지 지침으로 명시한다.
4. Role `pending/operator/admin/sales/dba`의 `ProductId IS NULL` prompt 를 역할명에 맞게 작성한다.
5. runtime 조립은 feature-0002에서 `전 Product 공통` Role prompt 누적 방식으로 수정하고 테스트한다.

위험도: Minor — 비파괴 데이터 upsert + LLM 입력 패키징 수정. 인증/인가 catalog, DB schema, 삭제/파괴 작업 없음.

### 2.1 Implementation Plan (TASK-0059)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Major 등급 변경 계획이다. 사용자 승인 (2026-05-15) 으로 진행.

**영향 파일**:
- [src/static/app.js](../src/static/app.js) — `sendPrompt()` askBody 에 `lazy_create` hint (lazy 경로 한정), `loadConversations()` 의 active id 덮어쓰기에 pending 가드
- [src/app.py](../src/app.py) — `_resolve_conversation_for_account` 시그니처에 `force_new=False` kwarg 추가, `/api/ask` 의 빈 `request_conversation_id` 경로가 `lazy_create` body hint 를 `force_new=True` 로 위임

**접근 방법**:
1. Frontend `sendPrompt()` 의 askBody 구성 시 `isLazyCreate` 일 때만 `lazy_create: true` 를 추가 (기존 대화 ask 에는 추가 안 함 — 의미 변경 0).
2. Frontend `loadConversations()` 가 `state.pendingNewConversation` true 일 때는 `state.activeConversationId` 를 덮어쓰지 않음 — 사이드바 리스트와 backend `current` 는 갱신하되 active id 보존.
3. Backend `_resolve_conversation_for_account` 에 `force_new=False` kwarg 추가. requested_id 가 truthy 이면 기존 동작 (force_new 무시), 빈 문자열이면 `_repair_current_conversation(..., force_new=force_new)` 로 위임. `_repair_current_conversation` 은 기존에 `force_new=True` 시 visible fallback 차단 + 새 cid 생성 로직을 이미 가짐 — body 변경 없음.
4. `/api/ask` 의 빈 `request_conversation_id` 경로에서 `lazy_create_requested = bool(data.get("lazy_create"))` 추출 후 `_resolve_conversation_for_account(..., create_if_missing=True, force_new=lazy_create_requested)` 호출. hint 없는 legacy client (예: 첫 로그인 후 직전 대화 자동 이어받기 흐름) 는 force_new=False → 기존 동작 유지.

**위험도**: **Major** §12.3 — 사용자 대화 routing 데이터 영역. 인증/인가 catalog·endpoint guard·owner check 무변경. `_account_can_access_conversation` / `_conversation_owned_by_account` 검사는 기존 그대로 유지되며 force_new 경로는 새 cid 를 생성하므로 owner 가 즉시 본 계정으로 assign 됨 (`_assign_conversation_owner(force=True)`). cross-account leak 가능성 없음.

**검증**:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
- (c) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

- [x] TASK-0058 (REQ-20260514-0001, **Critical** §12.3 — 인증/인가·개인정보·외부 공개 범위 변경) 대화 공유 링크 기능 도입. anonymous 접근 가능한 read-only view + 로그인 viewer 의 fork. 사용자 결정 6 항목 (외부 anonymous 허용 / 무기한 + revoke / read+fork / full+anchored / `conversation.share.create` 신설 / 메시지+SQL+결과셋 노출) 와 codex outside voice review 의 blindspot 보강 (B1 메시지 테이블 이중성 — AnchorMessageId 는 `AgentMemoryMessages.Id` 기준 inclusive `Id <= anchor`, B2 `_optional_account` 헬퍼 신설, R4 `_fork_conversation_impl` 추출로 share-grant 가 read-gate 우회, R6 revoke+view race-free 단일 UPDATE, R7 file attachment 자동 hide, R8 token 충돌 retry, R10 share.html FileResponse mount) 반영. **Phase A**: `PERMISSION_DEFINITIONS` 에 `conversation.share.create` 추가 (catalog 33→34, group=conversation), `SEED_ROLE_DEFINITIONS` operator/sales 에 grant + admin 보정 list 에 추가, `WebConversationShares` 테이블 신설, `_ensure_web_conversation_shares_schema(conn)` helper 가 slow path + fast path 양쪽 idempotent 호출, fast path catchup 에 `_ensure_permission_catalog(conn)` 추가로 신규 권한 hydrate. **Phase B**: `_optional_account` + `_fork_conversation_impl` 헬퍼 + 5 endpoint (POST/GET share[s], DELETE share, GET/POST public/share/{token}[/fork]). Token = `secrets.token_urlsafe(32)`. `/share/{token}` FileResponse route. **Phase C**: 헤더 `shareConversationBtn` (gated by `conversation.share.create`) + 메시지 hover "여기까지 공유" + `createConversationShare` 함수 (clipboard copy + toast). 권한 label/description 매핑 추가 → CONVENTIONS.md §10.6 conversation section 에 자동 합류. **Phase D**: `share.html` / `share.css` / `share.js` 신규 정적 파일 — anonymous accessible read-only view (메시지 + SQL `<pre>` + 결과셋 `<table>`), 로그인 + can_fork 시 "내 계정에서 fork" 버튼. **Phase E**: 본 entry + FUNCTION.md REQ-20260514-0001 (AC-0053~AC-0060), MODIFY.md / REVIEW.md, project-level [`docs/SECURITY.md`](../../../docs/SECURITY.md) 에 anonymous endpoint 2 곳 명시 + 외부 배포 시 IP 제한/비밀번호 보호 후속 cycle 권장, STATUS.md feature-0003 row 갱신.

### 2.1 Implementation Plan (TASK-0058)

영향 파일:
- `unit/feature-0003-agent-web-ui/src/app.py` (RBAC catalog + 부트스트랩 schema helpers + 5 endpoint + helper refactor)
- `unit/feature-0003-agent-web-ui/src/static/app.js` (헤더 share 버튼 + 메시지 hover share + `createConversationShare` + 권한 매핑)
- `unit/feature-0003-agent-web-ui/src/static/index.html` (헤더 share 버튼 1줄)
- `unit/feature-0003-agent-web-ui/src/static/share.html` / `share.css` / `share.js` (신규 anonymous view)
- `unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW}.md` + `docs/{STATUS,SECURITY}.md`

접근 방법: A=infra/RBAC catalog, B=Backend 5 endpoint + helper refactor, C=Frontend logged-in, D=Anonymous view, E=Docs. Phase 별 비파괴 추가이므로 각자 verify 가능. Token = 256-bit URL-safe, UNIQUE 충돌 retry loop. revoke + view 카운터는 동일 UPDATE 로 race-free.

위험도 평가: **Critical** §12.3 — 인증/인가 catalog 확장 + anonymous public endpoint 2 곳 신설 + SQL 결과셋 외부 노출. SECURITY.md §3 의 3 항목 동시 변경. 사용자가 사내 IP 가정으로 anonymous 허용 결정. 외부 배포 전 IP 제한/비밀번호 보호 후속 cycle 필요.

- [x] TASK-0056 (REQ-20260512-0002, **Major** §12.3 — frontend 권한 정렬 + project-level 컨벤션 1 절) 작업 화면·관리 콘솔 권한 정렬을 화면 맥락별로 분리. 두 화면이 같은 `console→account→role→conversation→[product]→misc` 순서를 공유해 admin 메타권한이 두 곳 모두 위에 노출되던 UX 회귀 fix. (1) [docs/CONVENTIONS.md §10.6](../../../docs/CONVENTIONS.md) 화면별 권한 섹션·정렬 정책 신설 — 작업 화면 = "운영→관리→기타", 관리 콘솔 = "관리→운영→기타" 2단 section. (2) **admin.js**: `ADMIN_PERMISSION_SECTIONS` 상수 + `sectionedGroupedPermissions` 함수 + `renderPermissionGrid` 가 outer section header (`.permission-section`) 로 inner group `<details>` 들을 감싸도록 수정. (3) **app.js**: `PERMISSION_GROUP_ORDER` 에 `product` 추가 (누락 fix), `PERMISSION_GROUP_LABELS.product`, `WORK_SCREEN_PERMISSION_SECTIONS` 상수, `permissionGroupOf()` 가 `system_prompt.` 를 product 로 매핑, `PERMISSION_LABELS/_DESCRIPTIONS` 에 `product.manage` / `system_prompt.manage.role.any` 추가, `buildPermissionPills` 가 2단 묶음 (`.perm-section-meta`) 으로 렌더 + 빈 section 자동 hide. (4) **styles.css**: `.perm-section-meta*` 5 클래스 + `.permission-section*` 5 클래스 + section 간 gap 중첩 제거. (5) cache-bust `v=20260512-perm-sections`. DB schema / backend RBAC catalog / endpoint guard / system prompt assembly 변경 0 — 인가 모델 무영향. node --check 양 파일 통과.
- [x] TASK-0055 (REQ-20260512-0001, **Major** §12.3 — admin console UI 정합 컨벤션 정립 + 코드 통일, 사용자 명시 AI 자율 commit/push) 관리 콘솔 카테고리별 다중선택 UX 정합 컨벤션 도입. 사용자 보고: "계정=우상단 / 역할=좌하단 / 제품=다중선택 부재" 의 카테고리 간 일관성 결여. 본 cycle = **정책 + gstack design 외부 시각 + Core+keyboard+advanced 코드 통일 합본**. (1) [docs/CONVENTIONS.md §10](../../../docs/CONVENTIONS.md) 프로젝트 수준 정책 신설 — 다중선택 적용 룰, DOM anchor 표준, 자료구조 invariant, 단위 어휘, 신규 카테고리 체크리스트. (2) [DESIGN.md](./DESIGN.md) 신규 — feature-local 상세 명세 (HTML 구조, CSS 토큰, Set/invariant, runtime assertion, §5 컴포넌트 set, §6 cross-page banner, §7 typed-confirm, §8 RBAC partial-fail UI, §9 keyboard map, §10 a11y, §11 렌더 cycle, §12 Products 마이그레이션). (3) **admin.html / styles.css / admin.js 코드 통일**: Accounts bulk bar 헤더 우상단 → list 직하단 sticky 이전 (DOM anchor 표준), Products multi-select 신설 (`productSelected: Set<number>`, row checkbox, select-all, bulk bar, cross-page banner), keyboard 단축키 (shift-click range + Esc 선택 해제), cross-page banner (Stripe pattern), confirm typed-confirmation (≥10 건 danger), RBAC partial-fail toast (skipped count chip), runtime assertion (`assertBulkBarContract`), a11y 강화 (`role="toolbar"`, `aria-live="polite"`, `role="grid"`, `aria-multiselectable`, checkbox `aria-label`). 외부 design 시각 (general-purpose subagent + worker-design 차용 framework) 으로 v0.1 → v0.2 흡수 (5 gap + a11y + token + keyboard map + 모던 레퍼런스 거부 근거).
- [x] TASK-0054 (REQ-20260508-0001) PR 흐름으로 main 동기화 — feat/adopt-external-anchor-v3.2.0-rc → main (PR #2, merge `eafe4c2`, 72 commits, conflict 10 files §3.2/§16.6 자율 해결) + issue/1-github-bootstrap → main (PR #3, merge `3fd4272`, self-hosted runner + 로컬 claude CLI 전환). 머지 후 main 의 ai-* 워크플로 self-hosted 정렬 확인.
- [x] TASK-0053 (REQ-20260506-0006, **Major** §12.3 — UX + 정책 토글, AI 자율 commit/push) 신규 제품 default 정책 토글 + 권한 grid 의 product sub-catalog + Role/Account detail 의 product-카드 통합 — TASK-0052 완료 직후 사용자 follow-up. **Phase A** (사용자 in-cycle 설계 전환 2026-05-06: 정책 주체 Role → Product): `WebProducts.DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 컬럼 신설 (이전 시도였던 `WebRoles.DefaultProductAccess` 는 deprecated). POST/PATCH `/api/admin/products` 가 `default_role_access` body 수용, true=모든 role 자동 grant, false=명시 grant 만. admin UI 토글은 Product detail 에 위치 — Role detail 에서는 제거. **Phase B**: admin.js 의 권한 grid 가 `groupedPermissions({excludeDynamic: true})` 로 dynamic `product.access.*` 를 grid 에서 분리, 정적 `product.manage` 등만 남기고 동적은 product subcatalog 카드로 이전. **Phase C**: Role detail 의 system prompt editor 가 product 별 collapsible card list 로 재구성 — 각 카드에 access 토글 + role-scope prompt textarea + 마지막에 "전 Product 공통" generic card. Account detail 에는 product 별 override (allow/deny/inherit) flat card list.
- [x] TASK-0052 (REQ-20260506-0005, **Critical** 등급 §12.3 — 인증/인가 구조 변경) 계정·역할 → 제품 권한 상속/override 모델 도입 — TASK-0051 분리분 C5. `/plan-eng-review` + Codex outside voice 통합 plan 은 [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). **Phase 1A** (RBAC engine catalog 인자화 — commit 4dd1d0a) → **Phase 1B** (catalog DB-driven + product 권한 backfill + 명시적 트랜잭션 + caller-update — 본 cycle) → **Phase 1C** (G1-G8 8 endpoint guards + admin_update_account RoleId 보존 pre-existing 버그 fix) → **Phase 1D** (admin UI PERMISSION_GROUP_ORDER 'product' 그룹 추가) → **Phase 2** (HTTP smoke 6/6 P0 직접 검증 + lifecycle T13/T16 + cascade 검증). 사용자 명시 AI 자율 commit/push 권한 (2026-05-06).
- [x] TASK-0051 (REQ-20260506-0004) 관리 콘솔 일괄 저장 정책 회복 + 메타데이터 4 스키마 항상 노출 + DB 목록 라이브 enum — `프롬프트 저장` / `제품 정보 저장` / `DB 목록 저장` 3 버튼 제거 후 footer `모두 적용` 단일 commit 흐름으로 통합, 메타데이터 4 종(`information_schema`/`mysql`/`sys`/`performance_schema`) 을 회색 disabled chip 으로 강제 노출(REV-20260422-0006 정책 시각화), 자유 텍스트 chip 입력을 `GET /api/admin/databases/available` 라이브 enum 기반 picker 로 교체. C5 (제품 권한 상속/override) 는 다음 cycle 로 분리(plan-eng-review 후 진행).
- [x] TASK-0050 (REQ-20260506-0003) `make web` 의 docker compose v5.1.1 + buildx v0.31.1 provenance metadata file race 우회 — Makefile 에 `dc-build SERVICE=...` reusable 가드 타깃 추가, `web` 타깃을 `dc-build SERVICE=web` + `up -d --no-build web` 로 분리. race 한정 무시 (image 빌드 OK + 로그에 `compose-build-metadataFile` 포함 시에만 EXIT=0 정규화).
- [x] TASK-0049 (REQ-20260506-0002) 누적된 빈 대화 일괄 정리 — `bin/cleanup-empty-conversations.sh` (dry-run 기본 + `--execute`, processing 보호 + 최근 N분 보호 + owner-account 옵션) 추가, 운영 데이터에 1회 적용 (88 → 46 conversations, 42개 정리).
- [x] TASK-0048 (REQ-20260506-0001) "새 대화" 생성 시점 lazy 화 — 버튼 클릭 시 client-side pending state 만 표시하고, 첫 메시지 전송 시 `/api/ask` 의 lazy creation path 가 실제 row 를 만들도록 전환. 신규 빈 대화 누적 방지. **CHG-20260506-0024 후속 fix**: backend `_repair_current_conversation` 의 `create_if_missing=_account_has_permission(...)` 자동 생성 분기 5 곳 (`_build_conversations_payload`, `/api/session`, `/api/history`, `/api/delete_conversation` 의 pending/일반 두 케이스) 을 모두 비활성화. 사용자 보고 회귀 "대화 삭제 시 새 대화가 그대로 남는 이슈" 의 근본 원인을 fix — delete 응답 `current` 가 backend 에서 자동 생성된 새 cid 였던 것을 빈 문자열로 정정.
- [x] TASK-0047 Product Selector + Auto 모드 진입 UX (사이드바 chip, `product_mode` 컬럼, `PATCH /api/conversations/{cid}/product`, "상품"→"제품" 일괄 치환) — agent team 4 + Codex CLI 교차검증 합의안
- [x] TASK-0046 API Vault 패널 Linear Wizard 재설계 + 단일 진입점 destructive (REQ-20260425-0001)
- [x] TASK-0045 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입)
- [x] TASK-0044 사업팀(Sales) role + role-scope system prompt + 복제 DB 접속 envelope + Product whitelist 사업팀 접근 runbook — Approach A wedge pilot infrastructure
- [x] TASK-0041 클라이언트 타임아웃 시 대화 지속(Attach/Resume) — `/api/ask_status` + `/api/ask_result` long-poll + 브라우저 UX 다이얼로그 + runner attach 분기
- [x] TASK-0040 schema whitelist 정규식 context-aware 수정 (TASK-0036 회귀 — alias.column 오탐으로 합법 SQL 이 차단되는 블로커 제거)
- [ ] TASK-0034 복잡 QA 성능 테스트 (local LLM 5 직렬 + 상용 API gpt-5.4-mini 5 병렬, 최대 20턴, 실제 DB 결과 대조 검증)
- [x] TASK-0039 메타데이터 스키마(sys/mysql/information_schema/performance_schema) Product whitelist bypass 정책 도입
- [x] TASK-0038 agent_core OpenAI 호출 무제한 대기 방지 + test runner/서버 타임아웃 정렬 (TASK-0034 Q4/Q5 실패 원인 1+2 대응)
- [x] TASK-0037 진행 상황 폴링 루프 중복/축적 방지 리팩터 리뷰 및 문서화 (TASK-0036 부수 변경)
- [x] TASK-0036 시스템 프롬프트 Depth (Product/Role/Account) + Product 단위 DB 접근 관리
- [x] TASK-0035 대화 탭 내 계정 구분 하이라이트/정렬 + 대화/말풍선 fork 기능
- [x] TASK-0033 결과셋 말풍선 단일 스크롤 + RowCount + 첫 행/열 freeze
- [x] TASK-0032 권한 안내 UX (툴팁 서술화 + 차단 시 필요 권한 안내)
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
- [x] TASK-0030 assistant 말풍선 고정 폭 + 결과셋 내부 스크롤 + 펼침 스크롤 앵커
- [x] TASK-0031 관리 콘솔 내부 스크롤 정리 (페이지네이션·액션 버튼 상시 노출)

## 2.1 Implementation Plan (TASK-0052)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Critical 등급 (인증/인가 구조 변경) 변경 계획이다. `/plan-eng-review` (Section 1~4) + Codex outside voice (gpt-5.5, reasoning=high) 통합 후 사용자 승인 (2026-05-06) 으로 진행. 4 phase 분할 → **본 turn 은 Phase 1A 만**.

<!-- PLAN-APPROVED by user on 2026-05-06 -->

전체 plan: [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). 본 §2.1 은 그 briefing 의 Phase 1A 슬라이스만 record.

### Phase 1A — RBAC engine catalog 인자화 (본 turn)

**목표**: Codex Claim 1 이 지적한 정적 PERMISSION_CODES 가정 (5 hot path hardwired) 을 catalog 인자 받는 형태로 refactor. **동작 변경 0**, deploy 안전성 극대화.

**영향 파일**:
- [src/app.py](../src/app.py) — `Iterable` import 추가, `_resolve_permission_catalog(conn=None)` 헬퍼 신설, 5 함수 (`_empty_permission_map`, `_apply_permission_overrides`, `_validate_permission_codes`, `_normalize_override_payload`, `_permission_catalog_payload`) 시그니처 확장 (catalog_codes/catalog_map/catalog kwarg 추가, 기본값 None = 정적 PERMISSION_CODES 사용 → 기존 동작 유지). `/api/admin/permissions` 엔드포인트가 plumbing 검증 경로 (`_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=...)`) 를 거치도록 단일 위치 전환.

**접근 방법**:
1. `_resolve_permission_catalog(conn=None)` 추가 — Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 그대로 반환. Phase 1B 가 conn 으로 WebPermissions union 하도록 body 만 교체.
2. 5 함수의 시그니처에 `*` 강제 keyword + catalog 인자 추가. `None` 이면 기존 정적 사용 (모든 기존 callsite 가 None 인자로 호출되어 회귀 0).
3. `/api/admin/permissions` 1 곳만 새 plumbing 으로 전환 — 정적 결과와 동일함을 HTTP smoke 로 검증.
4. 다른 callsite (account list, role detail 의 `_apply_permission_overrides` 등) 는 Phase 1B 에서 동적 catalog 도입 시 caller-update.

**위험도**: Low — 모든 기본값이 backward-compat. 단일 deploy.

**검증 (완료)**:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과
- (b) `make web` 컨테이너 재배포 성공 (`repo-web-1 Recreated/Started`)
- (c) 컨테이너 in-place 코드 검사: `_resolve_permission_catalog` / `catalog_codes` 키워드 17 hits — 신규 헬퍼 deploy 확인
- (d) bootstrap_admin 로그인 + `/api/admin/permissions` HTTP 200 + 33 codes 정상 (이전 catalog 와 동일)

**Phase 1A 종료 후 후속 phase (별 cycle)**:
- Phase 1B: WebPermissions IsDynamic/ProductId 컬럼 추가 + product 권한 backfill SQL + `_resolve_permission_catalog(conn)` body 를 DB query 로 교체 + 다른 callsite caller-update
- Phase 1C: 8 endpoint guard 도입 (G1-G8 — briefing §3.4)
- Phase 1D: admin UI PERMISSION_GROUP_ORDER 'product' 추가
- Phase 2: 운영 검증

## 2.1.archived Implementation Plan (TASK-0051)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute 프로토콜에 따른 **Major** 등급 변경 계획이다. 사용자가 2026-05-06 직접 진행 지시(§3.1 우선순위 1) + `[A → B → C → D]` 범위 한정으로 인계됐다. C5 (제품 권한 상속/override) 는 분리되어 다음 cycle 의 plan-eng-review 후 진행한다.

<!-- PLAN-APPROVED by user on 2026-05-06 -->

### 영향 파일
- [src/static/admin.js](../src/static/admin.js) — 핵심. 3 개 인라인 save 버튼 제거 + pending 상태 4 종 추가(`productMeta`, `productDatabases`, `systemPrompts`) + `applyAllPending()` 6 단계로 확장 + `pendingChangeCount()` / `refreshPendingUI()` / dashboard pending 카드 갱신. `renderProductDetail()` 의 chip wrap 에 메타데이터 4 종 locked chip 강제 prepend(× 버튼 없음, `is-locked` 클래스). chip 자유 텍스트 입력을 `<select>` picker 로 교체 — `loadAdminData` 에서 `/api/admin/databases/available` 동시 호출, 메타데이터 4 종 / 이미 등록된 chip / 내부 차단 (`agent_memory`) 은 옵션에서 제외. `buildSystemPromptEditor` 의 saveBtn/clearBtn 제거 + textarea 변경 핸들러로 pending 등록 + 안내 메시지 ("변경사항은 하단 '모두 적용' 으로 저장됩니다").
- [src/static/admin.html](../src/static/admin.html) — markup 변경 없음. cache-bust query string `v=20260506-batch-commit` 로 갱신 (admin.js / styles.css 양쪽).
- [src/static/styles.css](../src/static/styles.css) — `.admin-chip.is-locked` (회색 + cursor:not-allowed + opacity 0.55), `.admin-chip-locked-hint` 토큰 사용, `.admin-db-picker-row` (select + 추가 버튼 정렬) 추가. 토큰만 사용하고 hardcoded 색상 금지.
- [src/app.py](../src/app.py) — `GET /api/admin/databases/available` 신규 엔드포인트 추가. `_open_memory_connection(database=None)` 으로 `SHOW DATABASES` 실행, 결과를 `metadata_schemas`(고정 4 종 + 실제 존재 여부 marker) 와 `user_schemas`(메타 4 + `agent_memory` + `MEMORY_DB` 제외) 로 분리. 권한: `console.access`. 검증: schema name regex `^[a-z_][a-z0-9_]{0,63}$` 매칭 만 반환.

### 접근 방법
1. **Backend `/api/admin/databases/available`** 추가 — read-only enumeration. 권한이 약하면 (`console.access` 만) Product 관리자가 아니어도 목록 조회는 가능 (옵션 채우기 용도). 실제 등록은 `product.manage` 권한이 필요한 `PUT /api/admin/products/{id}/databases` 로만.
2. **Frontend pending 흐름 통합**:
   - `adminState.pending` 에 `productMeta: Map<productId, patch>`, `productDatabases: Map<productId, draft[]>`, `systemPrompts: Map<key, {scope, productId, roleId, accountId, content}>` (key = `${scope}:${productId||0}:${roleId||0}:${accountId||0}`) 추가.
   - `setProductMetaPending(id, patch)`, `setProductDatabasesPending(id, draft)`, `setSystemPromptPending(args)` 헬퍼 추가. 모두 immediate API 호출 안 함.
   - `pendingChangeCount()` 에 신규 3 buckets 합산.
   - `applyAllPending()` 에 6 번째~8 번째 단계 추가: 제품 메타 PATCH → 제품 DB PUT → 시스템 프롬프트 PUT (productMeta → productDatabases 순서, 둘 다 같은 product 면 메타 먼저).
   - `cancelAllPending()` 에 신규 buckets clear 추가. `loadAdminData()` 에 stale entry GC 추가 (제품 삭제 시 정리).
   - `refreshPendingUI()` 의 `commitBarDetail` 에 신규 카테고리 항목 추가.
   - Dashboard pending 카드(`renderDashboard` / `dashboardPendingList`) 에도 신규 카테고리 노출.
3. **renderProductDetail (제품 정보 저장 버튼 제거)** — name/desc/active/default/sort 입력 변경 핸들러를 `setProductMetaPending(productId, {field: value})` 로 변경. `saveMetaBtn` 삭제. 입력 disabled 는 `!canManage` 그대로 유지.
4. **renderProductDetail (DB 목록 저장 버튼 제거 + metadata locked chip + picker)**:
   - `redrawChips()` 시작 부분에 메타데이터 4 종을 `<span class="admin-chip is-locked"><span>information_schema</span> <small>항상 접근</small></span>` 형태로 forEach 강제 prepend. × 버튼 없음. `draft` 배열에는 메타 4 종이 들어있더라도 화면 상 user chip 영역에서 제외하여 중복 노출 방지 (단, draft 정합성 유지를 위해 user chip 만 표시).
   - 자유 텍스트 input + 추가 버튼을 `<select>` picker + `+ 추가` 버튼으로 교체. `<select>` 옵션은 `adminState.availableDatabases` (loadAdminData 에서 채움) 에서 메타 4 종 / 이미 draft 에 있는 schema / `agent_memory` / `MEMORY_DB` 제외. 옵션 0개면 "(추가 가능한 DB 없음)" 빈 옵션 표시.
   - `+ 추가` 버튼 클릭 시 draft 에 push + `setProductDatabasesPending(productId, draft)` + `redrawChips()` + picker 옵션 갱신.
   - chip × 버튼 클릭 시도 동일하게 `setProductDatabasesPending` 으로 pending 등록.
   - `saveDbBtn` 삭제. 안내 텍스트(dbHint) 마지막에 "메타데이터 4 종은 정책상 항상 접근 가능하며 변경할 수 없습니다." 한 줄 추가.
5. **buildSystemPromptEditor**:
   - `saveBtn` / `clearBtn` 제거 후, textarea `input` 이벤트로 `setSystemPromptPending({scope, productId: resolveProductId(), roleId, accountId, content: textarea.value})` 호출.
   - 빈 문자열 입력은 그대로 pending 으로 들어가고 apply 시 `PUT /api/admin/system-prompts` body content="" 가 삭제 경로로 처리됨 (기존 backend 동작 활용).
   - textarea 위에 안내 한 줄 ("변경사항은 하단 '모두 적용' 버튼으로 일괄 저장됩니다") 추가.
   - `productSelect` 변경 시 pending 의 key 가 바뀌므로, change 이벤트에서 `refresh()` 만 하고 textarea 값은 비우지 않는다 (사용자 의도 보존). Pending 에 같은 key 가 이미 있으면 textarea 에 그 content 를 채움.
6. **app.py `GET /api/admin/databases/available`** — `_account_has_permission(account, "console.access")` 검사 후 `_open_memory_connection(database=None)` → `SHOW DATABASES` → 결과를 `_METADATA_SCHEMAS = {"information_schema","mysql","sys","performance_schema"}` 와 `_INTERNAL_SCHEMAS = {MEMORY_DB.lower(), "agent_memory"}` 로 분류. user_schemas 에는 메타·내부·정규식 위반 제외 후 정렬해 반환. metadata_schemas 는 항상 고정 4 종 (실제 존재 여부 `present: bool` 표기).
7. **Cache-bust** — admin.html 의 `styles.css?v=…` 와 `admin.js?v=…` 두 줄을 `v=20260506-batch-commit` 으로 갱신.

### 위험도
- **Major** (§12.3) — 다파일 변경(FE 3 + BE 1), 권한 모델 변경 없음, 외부 계약·비용 영향 없음, 기존 정책(REV-20260422-0006 메타 bypass) 의 시각화일 뿐 동작 변경 아님. `agent_memory` 차단 정책 그대로 유지. 회귀 위험 영역: applyAllPending 6 → 8 단계 확장, dashboard pending 카드 새 카테고리.
- **C5 (계정·역할 → 제품 권한 상속/override)** 는 본 cycle 에서 분리. 사유: 신규 테이블(`WebRoleProductAccess`, `WebAccountProductAccessOverrides`) 마이그레이션 + `compose_system_prompt` 의 product 조회 경로 영향 + RBAC override 모델 (TASK-0024) 과의 충돌 검토 필요. 다음 cycle 진입 전 `/plan-eng-review` 권고.

### 검증 계획 (D 단계)
- a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` — syntax
- b) `make web` 재빌드 + `docker logs web` healthy 확인
- c) UX 회귀: `/admin` 진입 → 제품 탭 → 메타 4 chip 회색 표시 / × 없음 확인 / picker 옵션에 메타 4 미포함 확인 / 사용자 schema 추가·제거 시 footer 카운트 증감 / `모두 적용` 클릭 시 PATCH + PUT 순차 호출. 역할 탭 → 권한 grid 변경 + 시스템 프롬프트 textarea 변경 → footer 일괄 적용 동작.
- d) `GET /api/admin/databases/available` 직접 호출로 metadata 4 종 + user_schemas 정렬 + agent_memory 제외 확인.
- e) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS.

### 후속
- C5 분리 권고를 본 plan + `docs/REPORT.md §후속 작업` 에 기록.
- ANCHOR.md §3 의 "Role/Product 권한 부여" 시나리오 묘사가 본 변경으로 시각화되어 강화됨 — §3 본문 보강 여부는 §4 (cycle 종료 시 human 검증) 에서 판단.

## 2.1.archived Implementation Plan (TASK-0048)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute 프로토콜에 따른 Major 등급 변경 계획이다. 사용자가 2026-05-06 직접 진행 지시 (§3.1 우선순위 1) 를 한 상태에서 `<!-- PLAN-APPROVED by user on 2026-05-06 -->` 마커로 인계된다.

### 영향 파일
- [src/app.py](../src/app.py) — `/api/ask` body 에 optional `product_mode` / `product_id` hint 수용. 기존 `request_conversation_id` 이 비어 있어 `_resolve_conversation_for_account(create_if_missing=True)` 로 lazy 생성되는 분기에서, 새 cid 직후 `AgentCoreConversations.product_id/product_mode` 를 hint 값으로 셋업하고 `_save_account_product_pref` 도 호출. `request_conversation_id` 가 명시된 경로(기존 대화에 ask) 에서는 hint 를 무시한다 (대화의 product 변경은 `PATCH /api/conversations/{cid}/product` 가 단독 진실 — TASK-0047 의 race guard 와 충돌 방지).
- [src/static/app.js](../src/static/app.js) — `state.pendingNewConversation: boolean` 도입. `createConversation()` 의 동작은 보존(다른 호출처에서 직접 호출 가능) 하되, `newConversationBtn` 핸들러는 새 함수 `beginPendingConversation()` 으로 교체. `sendPrompt()` 가 pending 상태일 때 `/api/ask` body 에 `product_mode` / `product_id` 를 첨부하고 응답의 `conversation_id` 를 채택. `renderConversationList()` 에 pending placeholder (`is-pending` 클래스, 클릭 비활성, "내 대화" 그룹 상단) 추가. `selectConversation()` 은 pending 모드를 자동 종료. `isCurrentConvBusy()` / progress polling 은 pending 동안 cid sentinel `__pending__` 를 사용해 빈 cid 와 충돌하지 않도록 한다.
- [src/static/index.html](../src/static/index.html) — markup 변경 없음. cache-bust query string `v=20260506-pending-conv` 로 갱신.
- [src/static/styles.css](../src/static/styles.css) — `.conv-item.is-pending` 1 selector 추가 (border-dashed + faded text + cursor:default). 토큰만 사용.

### 접근 방법
1. **Frontend pending state 도입** — `state.pendingNewConversation` 플래그와 sentinel cid `__pending__` 도입. 새 대화 버튼 클릭 시 `beginPendingConversation()` 호출:
   - `state.activeConversationId = ""`, `state.pendingNewConversation = true`, `state.messages = []`
   - `renderConversationList()` (placeholder 표시), `renderConversationHeader()` ("새 대화" 표기), `renderComposer()` (활성), `stopProgressPolling({reset:true})`
   - product chip 은 `state.productMode/pinnedProductId` 를 그대로 유지 (cid 가 없어도 localStorage 미러로 의도 보존, `setActiveProduct` 의 cid-없음 분기 활용)
2. **사이드바 placeholder** — `renderConversationList()` 의 "내 대화" 섹션 렌더 직전에 pending 모드면 가상 항목을 prepend. 클래스: `conv-item is-own is-active is-pending`. 텍스트: "새 대화 (작성 중)" + 부제 "첫 메시지를 입력하세요". 클릭 핸들러 없음.
3. **sendPrompt() 변경** — pending 모드면:
   - body 에 `conversation_id: ""` + `product_mode: state.productMode` + `product_id: state.pinnedProductId || null` 첨부
   - `targetConvId` sentinel 로 `__pending__` 사용하여 `state.busyConversations.add("__pending__")` 처리
   - `progress polling 시작 시 cid 가 비어있으므로 startProgressPolling 호출은 ask 응답으로 cid 를 받은 후로 미룸
   - ask 응답에서 `payload.conversation_id` 받으면 `state.activeConversationId = payload.conversation_id`, `state.pendingNewConversation = false`, busy sentinel 해제, `refreshWorkspace(payload.conversation_id)`
   - ask 가 timeout/네트워크 오류로 실패 — 이 경우 backend 가 이미 cid 를 만들었을 수 있으나 client 가 cid 를 모름 → 사용자에게 "다시 시도하거나 사이드바 새로고침으로 복구" 안내 토스트. attach/resume 다이얼로그는 cid 가 있을 때만 의미가 있어 pending 모드에서는 비활성. 복구 경로: 사용자가 사이드바 새로고침(또는 `loadConversations` 재호출) 으로 새 대화를 보고 그 cid 로 ask 를 다시 보낸다.
4. **Backend `/api/ask` 보강** — `data.get("product_mode")` / `data.get("product_id")` 를 normalize. lazy 생성 분기에서 cid 만든 직후:
   ```python
   if hint_mode in ("auto", "pinned"):
       cur = conn.cursor()
       cur.execute(
           "UPDATE AgentCoreConversations SET product_id = %s, product_mode = %s "
           "WHERE conversation_id = %s",
           (hint_pid, hint_mode, conv_id),
       )
       cur.close()
       _save_account_product_pref(conn, int(account["id"]), mode=hint_mode, pinned_id=hint_pid)
   ```
   기존 대화 경로 (`request_conversation_id` 명시) 는 hint 무시. lazy 분기 이후 line 3886~ 의 `if conv_id:` block 이 새 row 의 `product_mode` 를 다시 읽어 정상 동작한다.

### 위험도 평가 (§12.3)
- **Major** — backend API contract 확장 + frontend state 흐름 변경. 단:
  - Schema/auth/마이그레이션 변경 없음 → Critical 아님
  - 외부 비용 영향 없음
  - 기존 호출자(테스트 러너, 직접 `/api/new_conversation` 사용) 는 backward-compatible 동작 유지
  - 회귀 surface: TASK-0041 attach/resume (cid 가 있을 때만 attach 가능), TASK-0047 product chip race guard (pending 동안 cid 없으니 PATCH 미동작 — `setActiveProduct` 의 cid-없음 분기 활용), 사이드바 그룹 렌더링.

### 사람 승인
<!-- PLAN-APPROVED by user on 2026-05-06 -->

## 3. In Progress
- TASK-0034 복잡 QA 성능 테스트 — 현재 구성된 assistant(agent-core + web UI)의 복잡 질의 대응력을 측정해 이후 개선 포인트를 도출한다. Q1/Q2/Q3 검증 완료, **Q4/Q5 재수행 완료 (2026-04-22: Q4 7 턴 stopped-by-heuristic 1171s / Q5 5 턴 stopped-by-heuristic 251s, 전 턴 HTTP 200)** — TASK-0040/0041 선행 완료 후 블로커 해제. 현재 남은 일은 turn-by-turn 실제 답변과 truth query 대조 검증 + `TASK-0034-REPORT.md` / LEARNINGS 추가 정리.

## 3.1 Recently Done
- TASK-0061 (2026-05-15 마감, REQ-20260515-0003~0010, **Major** §12.3 — Phase 6 Critical 분면 포함, 사용자 일괄 승인): GOAL.md 8 항목 합본 cycle. (Phase 1+2) 답변 버블 내부 실시간 step 진행 + 신규 대화 첫 요청 즉시 polling 연결 — `state.pendingBubble` + `renderPendingAssistantBubble` + elapsed timer + `applyProgressPayload` 동기화 + `sendPrompt` lazy-create 분기에서 cid 발급 즉시 `startProgressPolling`. (Phase 3) `_compute_display_status` + `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` + 일관 stale 반영 (/api/progress, ask_status, ask_result, list_conversations) + frontend `.conv-dot.is-stale-error` + toast. (Phase 4) `#messagePointRail` + scroll observer + click jump. (Phase 5) `/api/history_dates` AgentMemoryMessages 정본 + 캘린더 popover. (Phase 6 Critical) `WebAccounts.MustChangePassword` ALTER + `POST /api/admin/accounts/{id}/password-reset` (self-reset 거부) + 임시 비번 1회 표시 + 세션 revoke + 강제 변경 modal. (Phase 7) `currentPageAccounts()` helper 로 select-all 현재 페이지만 토글. (Phase 8) Ctrl/Shift 다중 선택 + `_delete_conversation_impl` helper 추출 + `POST /api/delete_conversations` partial success + ≥10 typed-confirm. 변경 파일: `app.py`, `app.js`, `admin.js`, `index.html`, `admin.html`, `styles.css`, `.env.example`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`. cache-bust `v=20260515-task-0061`. 검증: python compile / node --check / make web / browser smoke (DOM 5 신규 element + login + bulk bar + 캘린더 popover + display_status + history_dates + delete_conversations + pending bubble + admin currentPageAccounts/select-all + reset btn) 모두 통과.

- TASK-0050 (2026-05-06 마감): `make web` 이 docker compose v5.1.1 + buildx v0.31.1 의 provenance metadata file race 로 EXIT=1 종료되던 문제 우회. 환경 진단으로 `#15 exporting to image` 까지 정상 빌드 후 `#16 resolving provenance for metadata file` 직후 `open /tmp/.tmp-compose-build-metadataFile-<UUID>.json<NNNN>: no such file or directory` 메시지로 종료되는 패턴을 확인 (random suffix mismatch — compose 본체 회귀). `--provenance=false`, `BUILDX_NO_DEFAULT_ATTESTATIONS=1`, `COMPOSE_BAKE=true/false` 모두 효과 없음. Makefile 에 `dc-build SERVICE=...` reusable 가드 타깃을 추가하고 `web` 타깃을 `dc-build SERVICE=web` + `up -d --no-build web` 로 분리. 가드는 build 명령 로그를 임시파일에 캡처해 EXIT≠0 + 로그에 `compose-build-metadataFile` 문자열 포함 시에만 EXIT=0 으로 정규화 (다른 빌드 오류는 그대로 전파). 향후 compose 또는 buildx 가 fix 되면 가드는 자연스럽게 일반 build 경로로 흐름. 검증: `make web` EXIT=0, `[make] note: ...provenance metadata file race 우회...` 로그, `Container repo-web-1 Recreate/Recreated/Started`, `docker exec repo-web-1 grep -n PENDING_CONV_SENTINEL /app/web/static/app.js` 으로 새 코드 반영 확인. 학습 기록: `docs/LEARNINGS.md` LRN-20260506-0001 quirk.

- TASK-0049 (2026-05-06 마감, REQ-20260506-0002): TASK-0048 lazy 화 이전에 누적된 빈 대화 row 들을 일회성으로 정리. `bin/cleanup-empty-conversations.sh` 추가 — dry-run 기본 + `--execute` 명시 시에만 DELETE, `AgentMemoryKv.last_status='processing'` 인 대화 보호 (실행 중 ask race), `c.created_at < NOW() - INTERVAL <keep-recent-min> MINUTE` (default 5분) 으로 방금 만들어진 placeholder 폴백/in-flight 보호, `--owner-account-id <N>` 으로 계정 한정 가능. SQL 주입 방지를 위해 owner_id/keep_recent_min 모두 정수 정규식 검증 후 인터폴레이션, AgentCoreConversations 와 AgentMemoryMessages 의 collation 차이를 `COLLATE utf8mb4_unicode_ci` 명시 변환으로 해결. 운영 데이터에 적용: 88 conversations / 42 empty / 46 non-empty → 46 conversations / 0 empty / 46 non-empty (5분 보호로 방금 만든 backward-compat 검증 row 1개 포함 정리). 정리된 빈 대화 42개의 owner 분포는 admin (id=1) 다수, 그 외 일부 사용자. 본 TASK 는 destructive 변경(§12.1) 이지만 사용자 2026-05-06 명시 진행 지시에 따라 §3.1 우선순위 1 적용. 추후 정리는 동일 스크립트 재실행으로 idempotent 하게 가능.

- TASK-0048 (2026-05-06 마감, REQ-20260506-0001): "새 대화" 버튼이 즉시 `POST /api/new_conversation` 을 호출하지 않도록 client-side pending state 로 전환했다. 사이드바 "내 대화" 그룹 상단에 `conv-item is-own is-active is-pending` placeholder ("새 대화 (작성 중)" / 부제 "첫 메시지를 입력하세요") 가 표시되고 헤더 + composer 가 활성화. 첫 메시지 전송 시 `sendPrompt()` 가 `/api/ask` body 에 `conversation_id: ""` + `product_mode` + `product_id` (사용자 직전 의도) 를 첨부해 호출하면 backend `/api/ask` 의 `_resolve_conversation_for_account(create_if_missing=True)` 직후 hint 를 `AgentCoreConversations.product_id/product_mode` 에 셋업 + `_save_account_product_pref` 호출로 `WebAccounts.ProductPref*` 미러까지 갱신한다. 응답의 `conversation_id` 를 client 가 채택하고 placeholder 가 사라진다. 빈 대화 누적이 신규 row 측에서 차단된다. PATCH race 가드(TASK-0047 AC-0013) 와 attach/resume(TASK-0041 AC-0018) 는 cid 가 있을 때만 의미가 있어 lazy 분기에서 의도적으로 비활성화 — pending 단계 ask 실패는 "다시 시도하거나 사이드바 새로고침" 안내 토스트로 fallback. 변경 파일: `src/app.py` (lazy 분기에 hint 적용 + `_save_account_product_pref`), `src/static/app.js` (`state.pendingNewConversation`, `PENDING_CONV_SENTINEL`, `beginPendingConversation`, `renderConversationList` placeholder + `prependFn`, `renderConversationHeader` pending 표시, `selectConversation` 자동 종료, `sendPrompt` lazy create 분기, `handleLogout` cleanup, 새 대화 버튼 핸들러 교체), `src/static/index.html` (cache-bust `v=20260506-pending-conv`), `src/static/styles.css` (`.conv-item.is-pending` 1 selector 그룹). 검증: `python3 -m py_compile`, `node --check` 모두 통과, `make web` 으로 컨테이너 재기동 후 새 코드 반영 확인 (`docker exec` grep), `/api/new_conversation` backward-compat 정상 (delta=1 정상 row), `/api/ask` invalid (no API key) 시 lazy create 발생 0건 (input validation 후 lazy create 가 일어나므로 안전). 학습 기록: `docs/LEARNINGS.md` LRN-20260506-0014 pattern.

- TASK-0047 (2026-04-29 마감, agent team 4 합의 + Codex CLI 교차검증 — 사람 검토 없이 진행됨):
  사용자가 진입(로그인 직후) 또는 진행 중 대화에서 대상 **제품(Product)** 을 명시 선택할 수 있도록
  사이드바 헤더에 제품 칩(`#productChip` + `<select id="productSelect">`) 을 도입했다. 칩에는
  caption "이 대화의 제품" 을 함께 두어 대화 단위 상태(전역 계정 설정이 아님) 임을 명시한다 (Codex
  R-06 가드). `auto` 옵션은 일반 대화 모드로, 본 MVP 에서는 LLM resolver 가 들어가기 전이므로
  `[AUTO MODE]` 한 줄을 시스템 프롬프트에 inject 하고 product 한정 PRODUCT/role/account prompt 와
  `allowed_schemas` 를 모두 끈다(빈 리스트로 메타 4 스키마만 허용). 데이터 모델은 새 컬럼 2 개로
  분리: `AgentCoreConversations.product_mode VARCHAR(8) NOT NULL DEFAULT 'pinned'` + `WebAccounts.ProductPrefMode`/`WebAccounts.ProductPrefPinnedId`. NULL=auto 의미 변경을
  피하기 위해 명시 컬럼을 신설했다 (Backend Engineer 합의). 신규 API
  `PATCH /api/conversations/{cid}/product { mode, product_id }` 는 (1) 권한
  (`conversation.ask` + 소유자), (2) 진행 중 ask race 가드(`AgentMemoryKv.last_status='processing'`
  이면 409), (3) pinned 모드는 활성 product 검증 후 `WebAccounts` 의 직전 선호도 동시 갱신.
  `/api/session` 응답에 `product_pref` (mode, pinned_id, fallback_reason) +
  `conversation_product` (product_id, product_mode, product_key, product_name) 추가. Frontend 는
  `state.productMode` / `state.pinnedProductId` / `state.activeProductId` 3-필드 분리(의도/핀/서버 결과)
  로 race 회피, optimistic update + PATCH + localStorage 미러 (`mad.productPref.v1`), 진행 중 ask
  동안 `<select>` disabled + tooltip. 코드 중복 방지를 위해 `renderProductOptions(selectEl, {includeAuto, selected})`
  factory 를 추출해 drawer 의 `promptProductSelect` 도 같은 옵션 모델을 공유하게 했다 (FE
  Architect 합의). pinned product 가 비활성/제거된 경우 `_load_account_product_pref` 가 자동으로
  auto 로 강등하고 `pref.fallback_reason='pinned_inactive'` 를 클라이언트에 알려 토스트로 안내한다
  (Codex R-04 가드). 사용자 가시 한글 라벨 "상품" → "제품" 일괄 치환 (`app.py`, `index.html`, `app.js`,
  `admin.html`, `admin.js`); 코드 식별자 `Product`/`product_id`/`WebProducts`/`ProductKey` 는 그대로.
  검증: (1) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과,
  (2) `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py` 통과,
  (3) `node --check src/static/app.js` 통과, (4) in-process `compose_system_prompt(None,...)` /
  fake-conn `compose_system_prompt(...,product_mode='auto')` 검증 — auto 분기는 `[AUTO MODE]` 라인을
  포함하고 pinned 분기는 포함하지 않음. 후속 검증 항목(LLM resolver, PATCH race 강화, Playwright 4 specs,
  BroadcastChannel, mobile bottomsheet, 다국어, 운영 모니터링)은 별도 브리핑 [`docs/BRIEFING-product-selector-v1.md`](./BRIEFING-product-selector-v1.md)
  에 16 개 위험 항목(R-01..R-16) + 5 개 사람 확인 결정 사항(D-01..D-05) 으로 정리. **본 turn 은
  사용자 검토 없이 agent team(UX/FE Architect/BE Engineer/QA-Flow Validator) 4 인 합의 + Codex CLI
  교차검증으로 진행됐다 — 운영 반영 전 D-01..D-05 사람 결정과 R-01..R-16 검증이 필요하다.**

- TASK-0044 (2026-04-23 마감): Approach A wedge (office-hours 2026-04-23 세션에서 승인 — 사업팀 통계/단순 데이터 자가서비스) pilot 인프라 추가. (1) `SEED_ROLE_DEFINITIONS` 에 RoleKey=`sales` / Name=`사업팀` entry 를 추가해 부트스트랩 시 자동 생성되고, 권한은 대화 생성/질의/조회/파일조회/이름변경/취소/즉시답변(own 범위) 9 개로 operator 에서 `conversation.delete.own` 을 제거한 subset — 사업팀 pilot 은 자기 대화 흐름은 조작할 수 있지만 과거 요청 기록의 삭제는 불가. (2) 신규 `SEED_ROLE_SYSTEM_PROMPTS` + `_ensure_seed_role_system_prompts(conn)` 부트스트랩 단계를 추가해 sales role 에 역할 범위(`WebSystemPrompts.Scope='role', RoleKey=sales, ProductId=NULL`) system prompt 를 1 회 upsert 한다 — 관리 콘솔에서 덮어쓴 값은 존중(존재 시 skip). prompt 본문은 "단순 조회 → 문장 / 집계 → 결과셋 표 / ad-hoc 분석 → DBA 팀 이관 안내 후 대화 종료 / DB 쓰기 쿼리는 항상 거부" 4 지침. `compose_system_prompt` (agent_core) 가 기존 로직대로 `## ROLE GUIDANCE (sales)` 블록으로 주입한다. (3) `modules/config.py` 에 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` / `REPLICA_DB_ENABLED` env 5 개 추가 + `modules/db.py::connect()` 에 라우팅 — `REPLICA_DB_HOST` 가 세팅되어 있고 요청된 `database` 가 `MEMORY_DB`(=agent_memory) 가 아니면 복제 인스턴스로 접속, 아니면 기존 primary. memory DB 연결은 항상 primary 로 남아 대화/세션/권한 정본이 보존된다. `.env.example` 에 4 개 placeholder 추가, 실제 값은 `.env` 또는 docker-compose secret 으로만 주입한다(commit 금지). (4) Product 단위 접근 DB 화이트리스트 조정은 **런타임 체크가 아닌 관리 콘솔 runbook** 으로 정리 — 사업팀 pilot 에게 서빙할 Product 는 KR 의 기본값(`dbgame`/`dblog`/`dbauth`) 을 admin 이 관리 콘솔 `상품 (Products)` 탭에서 `dbauth` 를 제거하거나, 별도 Product(예: `KR-Sales`={dbgame,dblog}) 를 신규 생성해 사업팀 대화를 routing 하는 방식 중 조직 정책에 맞게 선택한다. 현재 seed 는 호환성을 위해 변경하지 않음(기존 KR 을 그대로 쓰는 DBA 워크플로우 영향 없음). (5) 사업팀 pilot 계정 자체는 코드가 자동 생성하지 않고 admin 이 관리 콘솔에서 수동 발급 — `.env.example` 에 `WEB_PILOT_SALES_USERNAMES=` placeholder 주석으로 치환 예시(`sales_lee,sales_kim,sales_park`) 기록. 검증: (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py unit/feature-0002-agent-core/src/modules/config.py unit/feature-0002-agent-core/src/modules/db.py` 통과, (b) `docker compose up -d --build web` 후 `/api/session` HTTP 200 OK, (c) `/api/admin/roles` 응답에 `{"role_key":"sales","name":"사업팀", permissions:[9 codes] }` 포함, (d) `WebSystemPrompts.Scope='role' AND RoleId=<sales_role_id> AND ProductId IS NULL` 1 row 존재하고 content 가 4 지침 문자열로 저장됨. 범위: 애플리케이션 코드 3 파일 약 70 줄, `.env.example` 6 줄, 문서 4 파일. `agent_core` 경로 재빌드(`depends_on` 체인) 는 모두 `modules/db.py` 변경 때문에 필요하다.
- TASK-0041 (2026-04-22 마감): 클라이언트 타임아웃 시 대화 지속(Attach/Resume) 경로를 구축. 에이전트 작업자 스레드는 `asyncio.to_thread` 로 HTTP 연결과 독립 실행되므로 클라이언트(httpx/브라우저/프록시) 가 ReadTimeout 으로 끊겨도 서버는 완료까지 계속 진행한다. 이 결과를 회수할 read-only 경로가 없어 결과가 유실되던 문제를 해결. 서버에는 `_ASK_TERMINAL_STATUSES={done,error,canceled}` 상수와 `_load_run_meta_kv` + `_build_ask_status_snapshot` 헬퍼, 그리고 `GET /api/ask_status` (1-shot 스냅샷, `conversation.read.own/any` gated) 와 `GET /api/ask_result?wait<=60` (long-poll, `deadline/0.5s` interval, terminal 시 assistant 전문 반환) 2 엔드포인트를 추가. 브라우저에는 `ASK_ATTACH_POLL_WAIT_SEC=45`/`ASK_ATTACH_MAX_TOTAL_SEC=1800` 상수와 `fetchAskStatus` / `showTimeoutRecoveryDialog`(3 버튼 모달 + Escape dismiss, 인라인 스타일) / `attachAndWaitForResult` long-poll 루프를 추가하고, `sendPrompt()` 의 `/api/ask` 호출 실패 시 is_processing=true 이면 다이얼로그 → 선택에 따라 `/api/cancel`·`/api/finalize` + attach, `initializeWorkspace()` 말미에는 페이지 로드 시 auto-attach. 테스트 러너에는 `ATTACH_TIMEOUT_SEC=960.0`/`ATTACH_POLL_WAIT_SEC=45` 상수와 `_attach_run(client,cid,message,t0)` 함수를 추가해 기존 `httpx.ReadTimeout` 분기를 `{"error":"client-read-timeout"}` 반환 대신 ask_status → ask_result long-poll 로 정상 복구하고 turn dict 에 `attached_after_timeout=True` + `attach_verdict` 기록. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 분리되어 attach 가 새 실행을 시작시키지 않는 안전 속성을 보장한다. 검증: py_compile 3 파일 + `node --check app.js` 통과, `make web` 재빌드 후 새 이미지 반영, 엔드포인트 401 라우팅 확인, terminal 상태 스냅샷 38ms, Q4 7 턴 + Q5 5 턴 전부 HTTP 200 으로 완료 (단일 턴이 960s 를 넘지 않아 attach 는 실제 발동되지 않았지만 safety net 인프라는 검증됨).
- TASK-0040 (2026-04-22 마감): SQL schema whitelist 정규식을 context-aware 2 단계 스캐너로 재작성해 `alias.column` 오탐 회귀를 제거했다. 기존 `_SCHEMA_TABLE_REF_RE = r"\`?([A-Za-z_]\w*)\`?\s*\.\s*\`?([A-Za-z_]\w*)\`?"` 는 SQL 문맥 구분 없이 전체에서 `x.y` 를 찾았고, SELECT/WHERE/ON 절의 alias.column 토큰이 schema 후보로 수집되어 Q4 재수행이 모든 턴 `BLOCKED_SCHEMAS=bb,be` 로 실패했다. `_TABLE_LIST_RE` (FROM/JOIN 뒤 다음 절 키워드 직전까지의 테이블 리스트 구간을 slice, IGNORECASE|DOTALL) + `_INNER_REF_RE` (그 slice 내부에서만 `schema.table` 추출) 2 단계로 재작성. SELECT 절의 alias.column 은 FROM/JOIN slice 바깥이라 더 이상 매칭되지 않는다. 검증: in-process 15 테스트 케이스(단일 FROM / FROM+WHERE alias.col / FROM+JOIN+alias.col ON / 혼합 / 백틱 / subquery / 비허용 schema 차단 / SELECT alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / dedup) 전부 expected 일치, Q4-like SQL 이 `{dblog}` 만 추출되고 `_whitelist_violation` 이 `{dbauth,dbgame,dblog}` whitelist 에서 None 반환, 비허용 `dbstat.foo` 는 계속 차단. 후속 TASK-0034 Q4/Q5 재수행이 전 턴 HTTP 200 으로 완료됨.
- TASK-0039 (2026-04-22 마감): Product 단위 DB whitelist 를 적용하면서 **메타데이터 4 스키마**(`information_schema`, `sys`, `mysql`, `performance_schema`) 만은 Product 접근 DB 목록에 등록 여부와 무관하게 agent tools 가 **항상 조회 가능** 하도록 정책을 재정의했다. 사용자 지시 2026-04-22: "assistant 가 스키마 구조를 찾지 못하는 이슈를 방지". 이는 TASK-0036 의 REV-20260421-0005 결정(메타데이터도 기본 차단) 을 일부 완화하는 방향이며, **`agent_memory` 는 여전히 whitelist 로 차단 유지**(에이전트 자신의 메모리/세션/계정 데이터 노출 방지). 변경: [tools.py:24-28](../../feature-0002-agent-core/src/modules/tools.py#L24-L28) 의 `_SYSTEM_SCHEMAS` frozenset 을 `_METADATA_SCHEMAS`(4 종) 와 `_INTERNAL_SCHEMAS`(1 종, `agent_memory`) 두 frozenset 으로 분리하고 `_SYSTEM_SCHEMAS` 는 union 으로 유지(기존 `_is_user_schema`/`search_tables` 의 UX-레벨 필터 동작 보존). [tools.py:78-94](../../feature-0002-agent-core/src/modules/tools.py#L78-L94) 의 `_whitelist_violation` 은 기존 `{information_schema}` bypass 대신 `_METADATA_SCHEMAS` 전체(4 종) 를 bypass 하고, `agent_memory` 는 여전히 `blocked` 로 떨어지도록 했다. 에러 메시지에 "메타데이터 스키마는 항상 접근 가능" 안내 한 줄을 추가해 agent 가 잘못된 참조를 메타데이터로 리디렉션하지 않도록 유도. 검증: (a) `python3 -m py_compile unit/feature-0002-agent-core/src/modules/tools.py` 통과, (b) 컨테이너 재빌드 후 `docker compose exec web python -c "..."` in-process 호출로 `set_active_schema_allowlist(['dbgame'])` 설정 상태에서 `_whitelist_violation({'mysql'})` / `{'sys'}` / `{'performance_schema'}` / `{'information_schema'}` 가 모두 `None` 반환, `{'agent_memory'}` 는 `오류:` 문자열 반환, `{'dbstat'}` (임의의 비허용 user schema) 은 차단. (c) 실사용 스모크: Product=KR 로그인 + 새 대화 + `/api/ask` 로 "dbgame 스키마에 있는 테이블 수를 information_schema 로 세어봐" → whitelist bypass 로 information_schema 접근 허용, tool step 정상 완료. 범위: 본 TASK 는 whitelist 정책 bypass 목록 조정에 국한. `list_schemas` 결과에 메타데이터 스키마를 노출할지는 UX 결정이라 현 상태(숨김) 유지.

- TASK-0038 (2026-04-22 마감): TASK-0034 Q4/Q5 실패 원인 분석([TASK-0038 상세 설계](#task-0038-상세-설계-2026-04-22) 참조)에서 확인된 근본 원인 1(agent_core 의 `OpenAI(**client_kwargs)` 가 `timeout`/`max_retries` 파라미터 없이 초기화돼 LLM 호출이 무한 대기할 수 있음) 과 근본 원인 2(러너 `ASK_TIMEOUT_SEC=600s` < 서버 `run_timeout_sec=900s` 로 클라이언트가 서버보다 먼저 포기해 좀비 에이전트 스레드가 발생) 를 대응했다. (1) [agent_core.py:1134](../../feature-0002-agent-core/src/agent_core.py#L1134) 의 `client = OpenAI(**client_kwargs)` 를 `OpenAI(**client_kwargs, timeout=max(5,int(AGENT_TIMEOUT_SEC)), max_retries=max(0,int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장하고 import 에 `AGENT_OPENAI_MAX_RETRIES` 를 추가. OpenAI Python SDK v1.x 의 client-level `timeout` 은 내부 httpx 에 그대로 적용되므로 `chat.completions.create` 개별 호출마다 wall-clock 상한이 보장된다. `max_retries` 는 이미 `AGENT_OPENAI_MAX_RETRIES=0` (config 기본값) 이므로 SDK 내부 재시도로 budget 이 배수로 늘어나지 않는다. (2) `task0034_runner.py:52` `ASK_TIMEOUT_SEC=600.0` 을 `960.0` 으로 인상(서버 `run_timeout_sec=max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)=max(900,180)=900` 보다 60s 여유). 이제 서버가 먼저 자기-타임아웃으로 실패 응답을 돌려주고, 클라이언트는 그 응답을 받은 뒤 다음 턴으로 넘어간다 — 좀비 스레드 창이 사라진다. 검증: (a) `python3 -m py_compile src/agent_core.py tests/task0034_runner.py` 통과, (b) `docker compose up -d --build web` 후 bootstrap_admin 로그인 + `/api/session` 200 OK + `/api/new_conversation` 후 간단 질의가 정상 응답, (c) agent_core 내부 LLM 호출이 AGENT_TIMEOUT_SEC(=.env 값 300s) 초과 시 `openai.APITimeoutError` 를 던지고 `_call_llm` caller 에서 step error 로 흡수되는 경로를 `grep` 으로 재확인. 범위: 본 TASK 는 근본 원인 1+2 만 다루고, 3(질문 follow_up 강화) 과 4(러너 격리/쿨다운) 는 TASK-0034 재실행 단계에서 별도 처리한다.
- TASK-0037 (2026-04-22 마감): `/api/progress` 폴링 루프를 `setInterval` 고정 주기에서 **순번(progressPollSeq) 기반 `setTimeout` 체인 + AbortController + 적응형 주기** 로 전환한 TASK-0036 부수 변경을 사후 리뷰/검증/문서화한다. 문제: `/api/ask` 한 턴이 수분까지 걸리는 실사용 워크로드(TASK-0034 에서 평균 ~3분/턴 관측) 에서 1500ms 고정 `setInterval` 폴링은 (1) 이전 요청이 끝나기 전에 다음 요청이 발행돼 **in-flight 요청 쌓임**, (2) 탭 전환/대화 변경/로그아웃 시 발행된 요청을 취소할 경로가 없어 서버에 **스텁 요청이 계속 도착**, (3) 서버는 `_load_steps_for_run` 이 전체 step 을 파이썬으로 로드해 `after_step` 필터를 코드로 걸던 경로였고, (4) 탭이 배경화되어도 그대로 1500ms 주기로 폴링을 지속해 배터리/네트워크를 불필요하게 소모했다. 조치 (이미 27127b9 커밋에 반영됨): 서버는 `_load_progress_status(conn, cid)` 단일 커서로 `(status, status_at, run_id)` 를 반환하도록 분리하고, `_load_steps_for_run(after_step=0)` 으로 SQL 레이어 필터를 밀어넣었으며, `/api/progress` 에 `client_run_id` 쿼리 파라미터를 추가해 클라이언트가 들고 있는 run_id 가 서버 최신 run_id 와 불일치하면 `after_step` 을 0 으로 리셋해 새 run 전체를 다시 흘려보내도록 했다. 클라이언트는 상수 `PROGRESS_FETCH_TIMEOUT_MS=4000`, `PROGRESS_POLL_ACTIVE_MS=1200`, `PROGRESS_POLL_IDLE_MS=3000`, `PROGRESS_POLL_HIDDEN_MS=10000`, `PROGRESS_POLL_ERROR_MS=8000` 5개를 도입하고, state 에 `progressPollInFlight`/`progressPollSeq`/`progressAbortController`/`progressErrorCount` 을 추가했다. `setInterval` → `setTimeout` 단일 체인(`scheduleProgressPolling(delayMs, seq)`) 으로 전환해 각 poll 이 응답하고 나서 다음 poll 을 예약하는 구조가 되었고, `pollProgress(seq)` 은 `seq !== state.progressPollSeq || progressPollInFlight` 이면 즉시 return 해 중복 실행을 차단한다. 매 요청마다 `AbortController` 를 생성해 `state.progressAbortController` 에 보관하고 `stopProgressPolling({abort:true})` 이나 `controller.abort()` 타임아웃(4초) 에서 in-flight 요청을 즉시 취소한다. 적응형 주기: 응답에 step 이 있으면 1.2s(ACTIVE), 없으면 3s(IDLE), `document.hidden` 이면 최소 10s(HIDDEN), 연속 오류 3회 미만까지는 8s(ERROR) 간격으로 재시도하되 3회 이상은 아예 재스케줄링하지 않는다. 검증: (1) `grep -c "setInterval" src/static/app.js` = 0 으로 기존 폴링 루프가 모두 제거됨, (2) 적응형 상수 5개 모두 `scheduleProgressPolling`/`pollProgress` 에서 실제 참조됨, (3) 서버 `/api/progress` 는 `client_run_id` 가 없거나 불일치 시 `after_step` 을 0 으로 리셋하는 조건을 실제로 가진다(`app.py:4405`), (4) 브라우저에서 `/api/progress` 응답 status 가 `processing` 이외 값이 되면 `stopProgressPolling({abort:false})` + `refreshWorkspace(cid)` 호출로 폴링이 즉시 멈추고 최종 workspace 가 재로드된다. 영향: TASK-0034 복잡 QA 테스트 중 상용 API 응답이 5분 이상 걸리는 상황에서도 브라우저 열린 탭에서 요청이 쌓이지 않고, 탭 전환 시 자동으로 저속 모드로 내려간다.
- TASK-0036 (2026-04-21 마감): System Prompt Depth 가 Product → Role → Account 3 계층 체인으로 동작하고, Product 단위 접근 DB 화이트리스트가 agent tools 레벨에서 강제된다. `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` 3 신규 테이블 + `AgentCoreConversations.product_id` 컬럼을 추가했고, `product.manage` / `system_prompt.manage.role.any` 2 개 permission 을 `admin` 역할에 기본 부여했다. seed 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) 가 자동 생성된다. `agent_core.compose_system_prompt(mem_conn, product_id, role_id, account_id)` 가 base prompt 뒤로 `## PRODUCT CONTEXT` / `## ROLE GUIDANCE` / `## ACCOUNT PREFERENCES` 블록을 순차 append 하고, `tools.set_active_schema_allowlist()` 가 execute_sql/describe_schema 등 모든 도구의 스키마 참조를 검사한다. 관리 콘솔은 `상품 카테고리` 구분 그룹 아래 `상품 (Products)` 탭이 추가되어 Product CRUD + 접근 DB chip 편집 + Product scope prompt 편집을, Roles detail 은 Role scope prompt 편집기(Product 드롭다운 포함) 를, 프로필 드로우의 새 `프롬프트` 탭은 Account scope prompt 편집기를 각각 제공한다. 검증: (1) `docker compose up -d --build web` → bootstrap_admin 로그인 → `/api/admin/products` → KR seed 확인, (2) `PUT /api/admin/products/1/databases` 로 dblog 제거/복원 왕복 OK, (3) `PUT /api/admin/system-prompts` (product scope) → `compose_system_prompt(conn, product_id=1, role_id=3, account_id=1)` 출력에 `## PRODUCT CONTEXT (KR)` 블록이 추가됨을 in-container 직접 확인, (4) whitelist=`{dbgame,dblog,dbauth}` 설정 후 `execute_sql("SELECT 1 FROM mysql.user")` 및 `describe_schema("mysql")` 이 `오류: 접근이 허용되지 않은 스키마 참조: mysql` 반환, `describe_schema("dbgame")` 은 정상 동작. 부수 수정: `_runtime_tables_available` 의 probe list 에 신규 3 테이블을 포함해 기존 배포에서 schema 마이그레이션이 자동 트리거되게 했고, `_whitelist_violation` 이 `_SYSTEM_SCHEMAS` 를 예외 처리하던 우회 경로를 제거해 `mysql`/`performance_schema`/`sys`/`agent_memory` 가 더 이상 whitelist 를 건너뛰지 않게 했다 (security hardening).

### TASK-0040 상세 설계 (2026-04-22)
- 문제/목적 (TASK-0034 Q4 재수행 중 2026-04-22 관찰): Q4 재수행 3 턴이 모두 `오류: 접근이 허용되지 않은 스키마 참조: bb, be. 현재 Product 에 허용된 스키마: dbauth, dbgame, dblog` 에러로 종료됐다. 실제 SQL 은 `SELECT ... FROM dblog.battlebegin bb JOIN dblog.battleend be ON be.AcntNo = bb.AcntNo ... WHERE bb.BattleType = 'CROSSROUTE' AND be.Star >= 3 ...` 형태로 `dblog` 만 참조하고 `bb`/`be` 는 테이블 별칭(alias) 이었다. 원인은 TASK-0036 에서 도입한 [tools.py:65-80](../../feature-0002-agent-core/src/modules/tools.py#L65-L80) 의 `_extract_sql_schema_refs` 정규식 `r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\.\s*`?([A-Za-z_][A-Za-z0-9_]*)`?"` 이 WHERE/SELECT 절의 `alias.column` 토큰까지 `schema.table` 로 수집한 뒤 [tools.py:83-105](../../feature-0002-agent-core/src/modules/tools.py#L83-L105) `_whitelist_violation` 이 allowlist(`{dbauth,dbgame,dblog}` + 메타데이터 4 종) 에 없다는 이유로 `bb`/`be` 를 차단하는 회귀다.
- 현황/환경 분석 (코드 기준):
  1. [tools.py:65-80](../../feature-0002-agent-core/src/modules/tools.py#L65-L80) `_extract_sql_schema_refs` — module-level lazy compile, finditer 로 전체 SQL 을 훑는다. 컨텍스트 구분이 없어 `WHERE bb.BattleType = 'X'` / `SELECT be.Star, be.Time` / `ORDER BY bb.StartTime` 등 alias.column 이 모두 매칭된다.
  2. 이 함수의 소비자는 [tools.py `_tool_execute_sql` / `_tool_explain_query`](../../feature-0002-agent-core/src/modules/tools.py#L83-L105) 의 `_whitelist_violation(refs)` 단일 경로. `describe_schema` / `describe_table` / `search_tables` / `get_sample_rows` / `get_table_indexes` / `get_foreign_keys` / `list_schemas` 는 이미 `{ schema_arg }` 1 건만 전달하므로 영향이 없다.
  3. MySQL 문법상 `schema.table` 을 쓸 수 있는 위치는 **FROM 절 / JOIN 절 / DELETE FROM / INSERT INTO / UPDATE / CREATE TABLE `s`.`t` / ALTER TABLE / TRUNCATE / INDEX reference** 등 DDL/DML 대상 지정 구간이다. agent 는 `execute_sql` 이 read-only SELECT 전용이므로 실사용 범위는 **FROM {schema}.{table} [alias]**, **JOIN {schema}.{table} [alias]**, **FROM/JOIN 연속 comma list `{s1}.{t1}, {s2}.{t2}`** 3 가지로 좁혀진다.
  4. WHERE/SELECT/GROUP BY/ORDER BY/ON 조건에 나오는 `x.y` 는 반드시 alias 또는 unqualified table → column 참조로, schema 의미가 없다. 따라서 "`FROM`/`JOIN`/`,` 직후에 위치한 `x.y`" 만 `schema.table` 로 간주하면 오탐이 제거된다.
  5. Edge case:
     - 중첩 서브쿼리 `FROM (SELECT ... ) t1 JOIN dblog.battlebegin bb ...` — `JOIN dblog.battlebegin` 은 여전히 매칭. 서브쿼리 내부의 `FROM dbgame.items` 도 독립적으로 매칭. 이상 없음.
     - `INSERT INTO` / `UPDATE` / `DELETE FROM` — read-only 전제라 발생하지 않지만, 보수적으로 `FROM|JOIN|,` 만 보되 향후 필요 시 확장 가능하게 둔다.
     - 백틱 `` FROM `dblog`.`battlebegin` `` — 공백/백틱 허용.
     - 대소문자 `from`/`From`/`FROM` — `IGNORECASE` 필요.
     - 주석 `/* ... */`, 문자열 리터럴 `'dblog.table'` 내부 — 현재 구현도 별도 처리 없음(기존 과탐/과누락 동등). 범위 외.
  6. test runner 의 기존 실패 아티팩트는 `tests/task0034_runs/api-Q4.failed.whitelist_regex.20260422.json` 으로 보관 중 (2026-04-22 세션 내 이동).
- 설계 (실구현 기준):
  1. **1 차안의 한계** — `FROM|JOIN|,` 세 가지 prefix 만 정규식으로 요구하는 방안은 `SELECT bb.BattleType, be.Star FROM dblog.t bb JOIN dblog.u be ON ...` 같은 SQL 에서 SELECT 절의 `, be.Star` 를 comma-join 으로 오탐해 `be` 가 schema 로 추출되는 새 회귀를 만든다(실제 테스트 2026-04-22 에서 확인). SELECT 절 쉼표와 FROM 절 쉼표를 단일 정규식만으로는 구분할 수 없다.
  2. **2 단계 스캐너로 확정** — [tools.py:65-99](../../feature-0002-agent-core/src/modules/tools.py#L65-L99) 를 table-list 구간 슬라이스 + 내부 schema.table 추출 2 단계로 재구현.
     ```python
     _TABLE_LIST_RE = _re.compile(
         r"\b(?:FROM|JOIN)\b(.*?)"
         r"(?=\bON\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b"
         r"|\bLIMIT\b|\bUNION\b|\bJOIN\b|\bFROM\b|;|\)|$)",
         _re.IGNORECASE | _re.DOTALL,
     )
     _INNER_REF_RE = _re.compile(
         r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\.\s*`?([A-Za-z_][A-Za-z0-9_]*)`?",
     )
     # 1) FROM|JOIN 키워드 뒤 table-list 구간을 모두 잘라낸 뒤
     # 2) 그 내부에서만 schema.table 을 반복 추출
     ```
     - 바깥 정규식이 `FROM`/`JOIN` 뒤 table-list 구간을 lookahead terminator 로 경계 설정: `ON` / `WHERE` / `GROUP BY` / `ORDER BY` / `HAVING` / `LIMIT` / `UNION` / 다음 `FROM`·`JOIN` / `;` / `)` / EOS.
     - 안쪽 정규식은 그 구간 안에서만 동작하므로 SELECT/WHERE/ON/ORDER/GROUP 절의 `alias.column` 은 애초에 스캔 영역 밖.
     - FROM 뒤 comma join(`FROM a.x, b.y`) 은 자연스럽게 수용됨 — 콤마가 같은 FROM 슬라이스 내부이므로 두 스키마 모두 `_INNER_REF_RE` 에 매칭.
     - 대소문자 무시(`IGNORECASE`), 다중 라인 쿼리(`DOTALL`) 수용.
  3. **테스트 매트릭스 (15 케이스)** — in-process 호출로 다음 기대치를 모두 확인한다. (TASK-0040 구현 직후 실제 실행 결과 포함)
     - `SELECT bb.BattleType FROM dblog.battlebegin bb JOIN dblog.battleend be ON be.AcntNo = bb.AcntNo` → `{dblog}` ✓ (기존 오탐: `{dblog, bb, be}`)
     - `SELECT * FROM dbgame.items i WHERE i.type='x'` → `{dbgame}` ✓
     - `SELECT * FROM dblog.battlebegin bb, dblog.battleend be WHERE bb.Id = be.Id` (comma join) → `{dblog}` ✓
     - `` SELECT * FROM `dblog`.`battlebegin` bb `` (백틱) → `{dblog}` ✓
     - `SELECT * FROM (SELECT 1 AS x) t JOIN dbgame.items i ON i.id=t.x` (서브쿼리) → `{dbgame}` ✓
     - `select * from dblog.t` (lower) → `{dblog}` ✓
     - `SELECT 1` (no FROM) → `∅` ✓
     - `SELECT bb.x FROM bb` (alias only) → `∅` ✓
     - `SELECT * FROM dbstat.foo` (비허용 스키마) → `{dbstat}` → 차단 ✓
     - `SELECT bb.BattleType, be.Star FROM dblog.battlebegin bb JOIN dblog.battleend be ON be.AcntNo = bb.AcntNo WHERE bb.BattleType = 'CROSSROUTE' AND be.Star >= 3` (Q4-like) → `{dblog}` ✓
     - `SELECT * FROM dbgame.t INNER JOIN dblog.u ON t.a=u.a LEFT JOIN dbauth.v ON v.a=t.a` (3-way JOIN) → `{dbgame, dblog, dbauth}` ✓
     - `SELECT * FROM a.x, b.y WHERE 1=1` (2-way comma join) → `{a, b}` ✓
     - `SELECT * FROM dblog.orders o GROUP BY o.user ORDER BY o.date` (GROUP/ORDER terminators) → `{dblog}` ✓
     - `SELECT col1, col2, tbl.col3 FROM sch.tbl tbl WHERE tbl.x > 5 ORDER BY tbl.y` (SELECT 절 쉼표 + alias 함정) → `{sch}` ✓
     - `WITH x AS (SELECT * FROM a.b) SELECT * FROM x` (CTE) → `{a}` ✓
     - 보안 비회귀: `SELECT * FROM dblog.t LEFT JOIN dbstat.u ON t.a=u.a` → `{dblog, dbstat}` → whitelist 차단 ✓
  3. **범위 제한** — 코드 변경은 `unit/feature-0002-agent-core/src/modules/tools.py` 1 파일 약 5 줄. tool 시그니처·호출처·기타 모듈 수정 없음. `execute_sql` 외 tool 은 호출 인자 레벨에서 schema 가 이미 들어오므로 정규식과 독립이다.
  4. **회귀 방어** — 기존 TASK-0036 원안(REV-20260421-0004) 의 "모듈 전역 + finally" 패턴은 변경하지 않는다. Product whitelist 로 차단해야 하는 비허용 user schema (예: `SELECT * FROM dbstat.foo`) 는 새 정규식에서도 `FROM dbstat.foo` 매칭으로 포착되어 여전히 차단된다.
- 검증:
  1. `python3 -m py_compile unit/feature-0002-agent-core/src/modules/tools.py` 문법.
  2. `docker compose up -d --build --force-recreate web` 후 위 테스트 매트릭스 8 케이스 in-process 호출 통과.
  3. `_whitelist_violation({'dblog', 'bb'})` → 기존 블로킹 메시지 반환, `_whitelist_violation({'dblog'})` + `set_active_schema_allowlist(['dbauth','dbgame','dblog'])` → `None`. 즉 정규식 출력이 올바르면 `_whitelist_violation` 은 변경 없이 통과/차단 판정이 정상.
  4. `python3 tests/task0034_runner.py --target api --only Q4,Q5` — TASK-0041 완료 후 최종 재수행. 이 시점에서는 whitelist regression 가 제거된 상태에서 Q4/Q5 가 전 턴 정상 응답/도구 호출을 수행하는지를 1 차 smoke 로 본다 (정답 내용 검증은 TASK-0034 보고서 업데이트 단계에서).
- 완료 조건:
  - TASK.md §2 / §3 업데이트 + TASK-0040 상세 설계 블록
  - tools.py 정규식 교체 + in-process 8 케이스 테스트 통과
  - Q4 재수행에서 whitelist 위반이 더 이상 발생하지 않음 확인 (최소 1 턴 정상 tool 호출 성공)
  - MODIFY.md 에 CHG-20260422-0013 append
  - REVIEW.md 는 추가 불필요(REV-20260421-0004 의 결정 틀 유지, 정규식 세부는 코드 주석 + 본 설계 블록으로 충분)
  - LEARNINGS.md 에 `LRN-20260422-0012 SQL 텍스트 스캔은 컨텍스트 조건(FROM|JOIN|,) 없이는 alias.column 과 schema.table 을 구분할 수 없다` append
  - REPORT.md §3 에 TASK-0040 한 줄 추가

### TASK-0041 상세 설계 (2026-04-22)
- 문제/목적 (사용자 지시 2026-04-22): 상용 API `gpt-5.4-mini` 가 복잡 질의에 응답하는 데 최대 15 분 이상 소요되는 실사용 워크로드에서, 서버 `run_timeout_sec=900s` 이전이라도 **(a) 브라우저 탭 닫힘/새로고침**, **(b) 테스트 러너 httpx `ReadTimeout` (960s)**, **(c) 네트워크 일시 단절** 같은 사유로 클라이언트 연결이 끊겨도 agent 스레드는 `asyncio.to_thread(_run_agent_core, ...)` 의 worker 에서 계속 실행된다. 그러나 현재 웹 UI 와 test runner 는 끊어진 요청에 대해 "실패" 상태만 보이고 `AgentMemoryKv.last_status` / `AgentMemoryMessages.assistant` 에 뒤늦게 기록되는 결과를 회수할 공식 경로가 없다. 사용자 입장에서는 "이미 시작된 턴을 계속 기다릴지 / 즉시 포기할지" 를 다시 선택할 수 있어야 하고, 테스트 러너 입장에서는 timeout 직후 동일 대화의 결과를 폴링해 최종 응답이 도착하면 이후 턴을 정상 진행해야 한다.
- 현황/환경 분석 (코드 기준):
  1. [app.py `/api/ask`](../src/app.py#L3520) 는 `asyncio.to_thread(_run_agent_core, ...)` 로 agent 를 돌리고, 완료되면 `AgentMemoryKv.set_run_status('done'|'error'|'canceled', run_id=...)` + `AgentMemorySteps` + `AgentMemoryMessages` 에 persistence 가 이뤄진다(실제 상태값 참조: [agent_core.py:1542](../../feature-0002-agent-core/src/agent_core.py#L1542) `done` / L1537 `error` / L1524 `canceled`, `processing` 이 running). HTTP 응답이 나가기 전에 client 가 끊겨도 to_thread 는 cancel 되지 않으므로 최종 결과는 DB 에 저장된다(검증: `finally` 블록 + `set_run_status('done', ...)` 순서).
  2. [app.py `/api/progress`](../src/app.py#L4381) 는 이미 `(status, status_at, run_id, steps, step_count)` 를 반환한다. 그러나 `steps` 만 내려가고, 최종 `assistant` 메시지(`_load_latest_assistant_message`) 나 `last_error` / `last_duration_ms` 는 별도 응답에 없어 브라우저는 `/api/history` 를 재-GET 해 메시지 목록을 다시 당겨야 한다. Test runner 에는 이 경로가 구성돼 있지 않다.
  3. [app.py `/api/cancel`](../src/app.py#L4296), [app.py `/api/finalize`](../src/app.py#L4338) 는 `AgentMemoryKv.mark_cancel_requested` / `mark_finalize_requested` 로 **KV 플래그만 세팅** 하고 agent loop 가 step 경계마다 플래그를 체크해 self-terminate 하는 패턴이다. 본 TASK 는 이 기존 신호 경로를 유지·활용한다(새 플래그 없음).
  4. [memory.py `set_run_status`](../../feature-0002-agent-core/src/modules/memory.py#L920~L1030) 에 `last_status` / `last_status_run_id` / `last_status_at` / `last_duration_ms` / `last_error` 5 키가 이미 persist 된다. `is_processing_conversation(cid)` 헬퍼도 존재. 새 테이블/컬럼 추가 없이 status 를 읽을 재료가 전부 있다.
  5. [task0034_runner.py:186-204](../tests/task0034_runner.py#L186-L204) 의 httpx.ReadTimeout 브랜치는 현재 `{"error": "client-read-timeout"}` 턴을 추가하고 즉시 다음 턴으로 넘어간다 — 실행 중이던 agent 는 서버에서 계속 돌고, 완료 후에도 runner 는 조회하지 않는다.
  6. [app.py WEB_PARALLEL_LIMIT=6](../src/app.py) — 계정당 동시 `/api/ask` 슬롯은 6. attach/resume 엔드포인트는 read-only 이므로 이 슬롯을 점유하지 않아야 한다(중요 설계 제약).
- 설계:
  1. **신규 엔드포인트 `GET /api/ask_status`** — read-only 스냅샷. Query: `conversation_id`. 응답:
     ```json
     {
       "conversation_id": "20260422-...",
       "is_processing": true|false,
       "status": "processing|done|error|canceled|(empty)",
       "status_at": "2026-04-22T01:23:45Z",
       "run_id": "...",
       "step_count": 7,
       "duration_ms": 123456,
       "error": null | "...",
       "has_answer": true|false,    // latest assistant message at or after run_id 존재 여부
       "answer_preview": null | "첫 160자 미리보기 ..."
     }
     ```
     내부 구현은 기존 `_load_progress_status(conn, cid)` + `_load_step_count_for_run` + `_load_latest_assistant_message(conn, cid, role='assistant')` 헬퍼를 재사용하며, 슬롯 카운터는 건드리지 않는다. 권한: 해당 대화에 대한 `conversation.read.own/any`.
  2. **신규 엔드포인트 `GET /api/ask_result`** — long-poll. Query: `conversation_id`, `run_id`(optional — 특정 run 지정), `wait`(초, 기본 30, 최대 60). 로직:
     - `t0 = time.monotonic()` 시점의 status 를 `_load_progress_status` 로 읽는다.
     - `run_id` 가 명시된 경우: 서버의 `last_status_run_id` 가 그 run_id 이고 status ∈ {done, error, canceled} 이면 즉시 200 반환.
     - `run_id` 미지정: 현재 status 가 terminal 이면 즉시 반환.
     - 그 외에는 `await asyncio.sleep(0.5)` 루프를 돌며 최대 `wait` 초 동안 polling. 매 반복마다 status 재조회. Terminal 상태 진입 시 즉시 반환.
     - 타임아웃까지 terminal 도달 안 하면 `{"timeout": true, "status": "processing", "run_id": "...", "step_count": N}` 반환.
     - Terminal 도달 시 응답에 `{"status": "...", "run_id": "...", "duration_ms": ..., "error": ..., "assistant": {"message_id": 123, "content": "...", "meta": {...}, "steps_count": N}}` 포함. `assistant.content` 는 full. 권한은 위와 동일.
     - 슬롯 카운터 미점유 확인: `/api/ask` 의 `async with _acquire_account_slot(...)` 블록 외부에서 실행.
     - 내부 구현은 `asyncio.sleep` 기반 polling 이라 background task 추가 없음 → 복잡도 최소.
  3. **브라우저 UX (`src/static/app.js`)** —
     - `sendPrompt()` 내부에서 `fetch('/api/ask', ...)` 의 AbortController `timeoutMs = PROGRESS_MAX_SESSION_MS (예: 900_000ms)` 로 기본값 조정. 기존보다 길게.
     - `fetch` 가 `AbortError` / `TypeError: Failed to fetch` / HTTP 504/502 로 떨어지면 `/api/ask_status?conversation_id=CID` 를 호출해 `is_processing=true` 가 돌아올 때 **다이얼로그 `showTimeoutRecoveryDialog(conversation_id, run_id)`** 를 띄운다. 버튼: `[ 계속 기다리기 ]` / `[ 즉시 답변 ]` / `[ 요청 취소 ]`.
       - **계속 기다리기**: `/api/ask_result?conversation_id=...&run_id=...&wait=60` 을 background 에서 polling. terminal 반환 시 `refreshWorkspace(cid)` + 토스트. UI 에는 기존 progress polling 루프가 계속 동작(TASK-0037 의 `scheduleProgressPolling`).
       - **즉시 답변**: `POST /api/finalize` (기존 기능) → 이후 terminal 도달까지 `/api/ask_result` long-poll.
       - **요청 취소**: `POST /api/cancel` (기존) → 이후 terminal 도달까지 `/api/ask_result` long-poll 후 cancelled 결과 반영.
     - 페이지 로드(bootstrap) 또는 대화 전환 시, 선택된 대화의 `/api/ask_status` 를 1 회 호출해 `is_processing=true` 면 자동으로 attach mode 에 들어간다(브라우저를 껐다 켜도 이전 턴을 이어서 관찰).
     - 기존 `PROGRESS_POLL_*` 상수와 충돌하지 않도록 `/api/ask_result` 호출은 **별도 single-flight in-flight 플래그** (`state.resultWaitInFlight` Set by conversation_id) 로 관리.
  4. **Test runner (`tests/task0034_runner.py`) attach/resume** —
     - 현재 `httpx.ReadTimeout` 브랜치를 `{"error": "client-read-timeout", "attached": true}` 기록으로 남기되, 즉시 다음 턴으로 넘어가지 않고 아래 루프로 전환:
       - `attach_deadline = time.monotonic() + ATTACH_TIMEOUT_SEC` (기본 900.0, .env override `TASK0034_ATTACH_TIMEOUT_SEC`).
       - 루프: `resp = await client.get('/api/ask_result', params={'conversation_id': cid, 'run_id': rid, 'wait': 45})`. terminal 응답이면 기록 후 루프 종료. `{timeout: true}` 면 계속. `attach_deadline` 초과 또는 HTTP 오류 2 회 연속 시 fallback 으로 `{"error": "attach-timeout"}` 기록 후 다음 턴 진행.
       - `run_id` 는 timeout 직후 `/api/ask_status` 1 회 호출로 획득해 고정. 그래야 같은 대화의 "다음 run" 이 아니라 현재 돌던 run 의 결과만 기다린다.
     - 성공적으로 attach 된 경우 turn 객체에 `status="succeeded-via-attach"` + `attached_after_timeout=true` + 원본 steps/assistant 를 삽입해 이후 truth 대조 단계가 일반 턴과 동일하게 동작하도록 한다.
  5. **에러/보안 고려**:
     - `/api/ask_status`, `/api/ask_result` 모두 **read-only**. write 경로 없음. `mark_cancel_requested` / `mark_finalize_requested` 는 기존 `/api/cancel` / `/api/finalize` 를 그대로 사용 — 본 TASK 에서 새 side-effect 경로 도입 금지.
     - 슬롯 카운터 비점유: attach/resume 은 별도 계정에서도 호출 가능하지만 `conversation.read.*` 권한 만으로 충분. `/api/ask` 는 여전히 `conversation.ask` 소유자 제한 유지.
     - long-poll `wait` 상한 60 초로 한정해 느린 로드밸런서/ingress 타임아웃과 충돌 방지.
  6. **범위 제한**:
     - 서버 변경은 `src/app.py` 에 2 개 엔드포인트 + 기존 헬퍼 재사용(새 SQL/테이블/마이그레이션 없음).
     - 브라우저 변경은 `src/static/app.js` + `src/static/index.html` 의 다이얼로그 마크업 + `src/static/styles.css` 의 다이얼로그 스타일.
     - Test runner 변경은 `tests/task0034_runner.py` 의 ReadTimeout 브랜치 확장 + `ATTACH_TIMEOUT_SEC` 상수 추가.
     - 기존 `/api/cancel` / `/api/finalize` / `/api/progress` / `/api/ask` 시그니처는 변경하지 않는다.
- 검증:
  1. **문법**: `python3 -m py_compile src/app.py tests/task0034_runner.py`, `node --check src/static/app.js`.
  2. **컨테이너 재빌드**: `docker compose up -d --build --force-recreate web`.
  3. **단순 동작**: bootstrap_admin 로그인 → 새 대화 → 빠른 질의(`/api/ask`, 5초 완료) 실행 중에 `curl .../api/ask_status?conversation_id=...` 가 `is_processing=true|false` 및 terminal `status` 를 반환.
  4. **long-poll**: `curl .../api/ask_result?conversation_id=...&wait=5` 가 이미 terminal 이면 즉시 200, processing 이면 5 초 `{timeout:true}` 반환.
  5. **브라우저**: 일부러 `/api/ask` 를 AbortController 로 2 초 뒤 중단 → 다이얼로그 출현 → `계속 기다리기` 클릭 → agent 완료 후 메시지가 UI 에 주입.
  6. **Runner attach**: `ASK_TIMEOUT_SEC=10.0` 로 일시 축소한 후 `--only Q4` 로 돌려 runner 가 timeout → attach → 최종 turn 기록까지 이동하는지 확인. 정상 확인 후 960s 로 원복.
  7. **TASK-0034 재수행**: TASK-0040 선 완료 + 본 TASK 완료 상태에서 `python3 tests/task0034_runner.py --target api --only Q4,Q5` 를 돌려 whitelist regression + timeout attach 두 경로 모두 정상 동작함을 입증.
- 완료 조건:
  - TASK.md §2 / §3 / TASK-0041 상세 설계
  - app.py `/api/ask_status` + `/api/ask_result` 추가, 문법·컨테이너 재빌드 통과
  - app.js 다이얼로그 + attach polling + bootstrap attach 연결
  - index.html / styles.css 다이얼로그 마크업·스타일
  - task0034_runner.py attach 분기
  - 검증 항목 1-7 모두 통과
  - MODIFY.md 에 CHG-20260422-0014 append
  - REVIEW.md 에 REV-20260422-0007 append (장기 실행 에이전트에 대한 read-only attach/resume 패턴 채택 이유)
  - FUNCTION.md 의 API 목록에 `/api/ask_status`, `/api/ask_result` 추가
  - REPORT.md §3 에 TASK-0041 한 줄 추가
  - LEARNINGS.md 에 `LRN-20260422-0013 장기 실행 worker 는 client disconnect 과 agent finalize 경로가 독립적이어야 한다` append

### TASK-0039 상세 설계 (2026-04-22)
- 문제/목적 (사용자 지시 2026-04-22): TASK-0036 이 `_whitelist_violation` 에서 `_SYSTEM_SCHEMAS` 통째 bypass 를 제거하면서 `mysql` / `performance_schema` / `sys` 를 기본 차단했지만, 실사용 중 "assistant 가 Product DB 의 테이블 구조를 찾지 못하는" 문제가 발견됐다. 원인: agent 가 본능적으로 `information_schema.TABLES` 외에 `sys.schema_table_statistics`, `performance_schema.tables`, 드물게 `mysql.*` 을 함께 조회해 교차 검증하려 하는데 이들이 전부 차단되면 재시도 루프에 빠지거나 `describe_schema` 만 반복하게 된다. 사용자는 메타데이터 4 종을 **Product 설정에 명시하지 않아도 항상 접근 가능** 하게 해달라고 요청했다. **`agent_memory` 는 예외** — 여기엔 다른 계정의 대화 내용, 세션, 권한 override 가 담겨 있어 여전히 차단 유지.
- 현황/환경 분석 (코드 기준):
  1. [tools.py:25-28](../../feature-0002-agent-core/src/modules/tools.py#L25-L28) `_SYSTEM_SCHEMAS` 는 `{information_schema, mysql, performance_schema, sys, agent_memory}` 5 종 frozenset. 이 집합은 두 용도로 쓰인다:
     - [tools.py:51-57](../../feature-0002-agent-core/src/modules/tools.py#L51-L57) `_is_user_schema(name)` — `list_schemas` 결과 post-filter 와 `search_tables` 의 `sys_exclude` 조건에서 "사용자 스키마가 아님" 판정. UX 용도.
     - [tools.py:78-94](../../feature-0002-agent-core/src/modules/tools.py#L78-L94) `_whitelist_violation(refs)` — agent tool 레벨 접근 차단 결정. Security 용도.
  2. 현재 `_whitelist_violation` 은 `allowed = _ACTIVE_SCHEMA_ALLOWLIST | {information_schema}` 로 **information_schema 1 종만** bypass. 나머지 `sys`/`mysql`/`performance_schema`/`agent_memory` 는 whitelist 에 명시적으로 등록하지 않으면 차단.
  3. `_is_user_schema` 는 `_SYSTEM_SCHEMAS` 에 포함된 스키마를 전부 "사용자 스키마 아님" 으로 판정해 `list_schemas` 결과에서 숨기는 UX 동작을 한다. 이건 사용자의 요청 의도("목록 내 유무와 관계없이 **접근** 가능") 와 무관하게 유지해도 된다 — agent 는 `describe_schema('information_schema')` / `execute_sql("SELECT ... FROM information_schema...")` 로 명시 호출이 가능하고, `list_schemas` 결과에 카탈로그 스키마를 섞어 보여주는 건 오히려 탐색 노이즈.
  4. [tools.py:451](../../feature-0002-agent-core/src/modules/tools.py#L451) `search_tables` 의 `sys_exclude` 도 `_SYSTEM_SCHEMAS` 전체를 WHERE NOT IN 으로 제외 — 키워드 검색이 메타데이터 테이블을 섞어 반환하면 결과가 지저분해지므로 이 동작도 유지.
- 설계:
  1. **스키마 상수를 두 카테고리로 분리** — [tools.py:24-28](../../feature-0002-agent-core/src/modules/tools.py#L24-L28):
     ```python
     # 메타데이터 스키마 — Product whitelist 와 무관하게 agent tools 가 항상 접근 가능.
     # DB 구조 탐색(정의·통계·런타임 메트릭) 에 필요해 기본 허용한다.
     _METADATA_SCHEMAS = frozenset({"information_schema", "mysql", "performance_schema", "sys"})
     # 에이전트 내부 스키마 — whitelist 로 차단 유지. 타 계정 대화/세션/권한 데이터 보호.
     _INTERNAL_SCHEMAS = frozenset({"agent_memory"})
     # 기존 호환: list_schemas/search_tables 의 "사용자 스키마 아님" 판정에 사용.
     _SYSTEM_SCHEMAS = _METADATA_SCHEMAS | _INTERNAL_SCHEMAS
     ```
  2. **`_whitelist_violation` bypass 집합 교체** — [tools.py:78-94](../../feature-0002-agent-core/src/modules/tools.py#L78-L94):
     - `allowed = set(_ACTIVE_SCHEMA_ALLOWLIST) | {"information_schema"}` → `allowed = set(_ACTIVE_SCHEMA_ALLOWLIST) | _METADATA_SCHEMAS`
     - 결과: agent 가 `execute_sql("SELECT ... FROM mysql.user")`, `describe_schema("sys")`, `describe_table("performance_schema", "tables")` 류 호출을 시도하면 Product 설정과 무관하게 통과.
     - `agent_memory` 는 `_METADATA_SCHEMAS` 에 없으므로 기존처럼 차단.
     - 비허용 user schema (예: 임의의 `dbstat`) 도 기존처럼 차단.
     - 에러 메시지에 "메타데이터 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 는 항상 접근 가능" 한 줄을 덧붙여, LLM 이 차단된 user schema 를 메타데이터 쿼리로 리디렉션할 수 있는 힌트 제공.
  3. **`_is_user_schema` / `search_tables` 는 그대로 유지** — `list_schemas` 결과에 메타데이터 4 종 노출 여부는 UX 결정 영역이고 현재는 숨김이 더 자연스럽다. agent 는 시스템 프롬프트의 KNOWN SCHEMAS 힌트 없이도 `execute_sql` 로 `information_schema.TABLES` 를 직접 조회할 수 있어 구조 탐색에 문제가 없다.
- 보안 고려 (REV-20260422-0006 으로 문서화):
  1. `mysql.user` 등이 bypass 경로를 타게 되지만, **DB 커넥터가 사용하는 MySQL 계정에 `mysql.*` SELECT 권한이 없으면 실행 단계에서 차단** 된다. whitelist 는 tool-레벨 1 차 방어이고 MySQL GRANT 가 2 차 방어로 남는다.
  2. `performance_schema` / `sys` 는 민감도 낮음(런타임 stat + 뷰).
  3. `information_schema` 는 원래부터 허용돼 있었다.
  4. 이 완화는 **현 리포의 agent read-only SQL 특성** 을 전제로 한다. write 가능 계정을 agent 가 쓰게 된다면 이 결정을 재검토해야 한다.
- 검증:
  1. `python3 -m py_compile unit/feature-0002-agent-core/src/modules/tools.py` → 문법.
  2. `docker compose up -d --build web` 후 컨테이너 내부에서 직접 호출:
     ```python
     from modules.tools import set_active_schema_allowlist, _whitelist_violation
     set_active_schema_allowlist(["dbgame"])
     assert _whitelist_violation({"mysql"}) is None
     assert _whitelist_violation({"sys"}) is None
     assert _whitelist_violation({"performance_schema"}) is None
     assert _whitelist_violation({"information_schema"}) is None
     assert _whitelist_violation({"dbgame"}) is None
     assert "agent_memory" in (_whitelist_violation({"agent_memory"}) or "")
     assert "dbstat" in (_whitelist_violation({"dbstat"}) or "")
     ```
  3. 실사용 스모크: bootstrap_admin 로그인 → 새 대화(Product=KR) → `/api/ask` 로 "information_schema 에서 dbgame 의 테이블 개수" → 성공 응답.
  4. 회귀 방어: whitelist 미설정 상태(`_ACTIVE_SCHEMA_ALLOWLIST is None`) 에서는 `_whitelist_violation` 이 즉시 `None` 반환하는 경로가 유지됨(코드 L80-L81).
- 범위 제한:
  - 코드 변경은 `unit/feature-0002-agent-core/src/modules/tools.py` 한 파일(약 10 줄).
  - `_is_user_schema` / `search_tables` / `list_schemas` UX 동작은 손대지 않는다.
  - 시스템 프롬프트의 "KNOWN SCHEMAS" 블록 포맷도 손대지 않는다 — agent 가 이미 information_schema 경로를 잘 찾는다.
- 완료 조건:
  - TASK.md §2 / §3.1 / 상세 설계 블록 추가
  - tools.py 반영 + in-process 테스트 통과
  - MODIFY.md 에 `CHG-20260422-0012` append
  - REVIEW.md 에 `REV-20260422-0006` append (REV-20260421-0005 supersede 관계 명시)
  - FUNCTION.md AC-0010 보강
  - REPORT.md §3 에 TASK-0039 한 줄 추가
  - git commit + push

### TASK-0038 상세 설계 (2026-04-22)
- 문제/목적 (사용자 지시 2026-04-22, TASK-0034 Q4/Q5 원인 분석 후): Q4 conversation `20260421084441-6b71b1b1` 은 대화 생성(17:44:41) → step 1 `execute_sql` 실패(17:44:46) → step 2/3 `describe_table` 완료(17:44:48) 후 10분 공백 후 클라이언트 600s read-timeout 으로 종료됐다. DB 에는 `assistant` 메시지가 0 건, run_id 가 1 개만 존재해 **turn 1 의 agent 가 LLM 호출 단계에서 무한 대기** 한 것으로 판정됐다. 그 사이 클라이언트는 먼저 포기했지만 서버 thread pool 은 해당 스레드를 계속 물고 있어 Q4 turn 2 는 persist 이전에 풀 경쟁에 막혔고, Q5 는 60s 안에 `/api/auth/login` ConnectTimeout 으로 실패했다.
- 현황/환경 분석 (코드 기준):
  1. `agent_core.py:1134` `client = OpenAI(**client_kwargs)` — OpenAI Python SDK v1 은 `timeout` 인자가 없으면 내부 httpx 기본(연결당 10 분 수준) 을 쓰되, 실제로는 서버가 SSE 스트림을 끊지 않는 한 무한 대기한다. `chat.completions.create(...)` 호출([L999](../../feature-0002-agent-core/src/agent_core.py#L999)) 도 per-request timeout 을 지정하지 않는다.
  2. `modules/llm.py` 는 이미 `_get_openai_client(timeout_sec=...)` 헬퍼에서 `timeout + max_retries + ThreadPoolExecutor wall-clock deadline` 패턴을 구현해 뒀다([llm.py:482~529](../../feature-0002-agent-core/src/modules/llm.py#L482)) — 동일한 상한 개념을 `agent_core.py` 의 메인 루프 클라이언트에도 적용하기만 하면 된다. 최소 변경 원칙으로 `modules/llm.py` 를 통째 재사용하는 대신 `OpenAI(...)` 초기화에 `timeout`/`max_retries` 만 얹는 것으로 제한한다.
  3. `modules/config.py:283` `AGENT_OPENAI_MAX_RETRIES=int(os.getenv("AGENT_OPENAI_MAX_RETRIES","0"))` 는 이미 존재하므로 환경변수 계약을 깨지 않는다. `.env` 에는 기본값 미설정 → 0 (재시도 비활성).
  4. `agent_core.py:1255~1258` `run_timeout_sec = max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)`. `.env` 에는 `AGENT_TIMEOUT_SEC=300, AGENT_EARLY_FINALIZE_MS=180000` 이므로 `run_timeout_sec = max(900, 180) = 900s` 고정.
  5. 러너 `task0034_runner.py:52` `ASK_TIMEOUT_SEC=600.0` → httpx client 의 per-request timeout. 600 < 900 이므로 클라이언트가 항상 서버보다 먼저 포기한다.
- 설계:
  1. **agent_core `OpenAI` 초기화에 timeout/max_retries 반영** — [`agent_core.py:26~32`](../../feature-0002-agent-core/src/agent_core.py#L26) 의 `from modules.config import` 에 `AGENT_OPENAI_MAX_RETRIES` 를 추가. [L1134](../../feature-0002-agent-core/src/agent_core.py#L1134) `client = OpenAI(**client_kwargs)` 를 `OpenAI(**client_kwargs, timeout=max(5, int(AGENT_TIMEOUT_SEC)), max_retries=max(0, int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장. 개별 `chat.completions.create` 호출은 그대로 두되, client-level timeout 이 httpx transport 에 상속되므로 모든 호출에 wall-clock 상한이 걸린다.
  2. **test runner ASK_TIMEOUT_SEC 인상** — `tests/task0034_runner.py:52` `ASK_TIMEOUT_SEC = 600.0` 을 `ASK_TIMEOUT_SEC = 960.0` 으로 변경. 주석으로 "`> run_timeout_sec=900`" 근거를 명시. 다른 타임아웃(`httpx.AsyncClient(timeout=60.0)` 기본값) 은 fast endpoint 전용이므로 손대지 않는다.
  3. **환경변수 override 경로는 유지** — `AGENT_TIMEOUT_SEC` / `AGENT_OPENAI_MAX_RETRIES` 모두 `os.getenv` 로 오버라이드 가능. 운영에서 더 짧게(예: 90s) 조이고 싶으면 .env 만 바꾸면 된다.
- 검증:
  1. `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/tests/task0034_runner.py` → 문법 체크.
  2. `grep -nE "OpenAI\(.*timeout" unit/feature-0002-agent-core/src/agent_core.py` 가 L1134 를 반환하는지 확인.
  3. `grep -n "ASK_TIMEOUT_SEC" unit/feature-0003-agent-web-ui/tests/task0034_runner.py` 에서 960.0 확인.
  4. `docker compose up -d --build web` → 신규 이미지 기동, `/api/session` 200 OK, bootstrap_admin 로그인 성공, `/api/new_conversation` + `/api/ask` 로 짧은 질의("SHOW DATABASES;" 수준) 가 정상 응답하는지 in-host curl 로 확인.
  5. 의도적 timeout 유발: 로컬 환경에서 AGENT_TIMEOUT_SEC=3 + 긴 질의로 `openai.APITimeoutError` 가 step error 로 흡수되는지 (기존 `try/except Exception` 경로가 삼키는지) 확인 — 단, prod .env 에 영향이 없도록 임시 override 만 사용.
- 범위 제한:
  - 코드 변경은 `agent_core.py`(2줄: import + OpenAI() 확장) 와 `task0034_runner.py`(1줄) 로 제한.
  - 원인 분석 3(질문 follow_up trigger 확장) / 4(러너 격리/쿨다운) 는 본 TASK 범위 외. TASK-0034 재실행 단계에서 별도 처리.
  - `modules/llm.py` 의 `_openai_chat_completion_with_deadline` 패턴 통합 리팩터는 위험도/변경폭이 커 별도 TASK 로 분리.
- 완료 조건:
  - TASK.md §2 / §3.1 / 상세 설계 블록 추가
  - agent_core.py + task0034_runner.py 반영
  - `docker compose up -d --build web` 후 `/api/session` probe 통과
  - MODIFY.md 에 `CHG-20260422-0011` append
  - REPORT.md §3 에 TASK-0038 한 줄 추가
  - git commit + push

### TASK-0037 상세 설계 (2026-04-22)
- 문제/목적 (사용자 보고 2026-04-22 01:07 KST): TASK-0034 복잡 QA 성능 테스트(상용 API gpt-5.4-mini, 대화당 ~3분/턴) 를 돌리면서 브라우저 탭을 열어두면 `/api/progress` 요청이 지속적으로 쌓이는 현상이 관찰됐다. 이 "폴링이 끝없이 요구되는" 증상은 다른 작업자 AI 가 TASK-0036 PR 에 같이 묶어 해결(27127b9)한 상태라, 본 세션에서는 **수정 내용을 리뷰하고 설계·학습 문서에 반영**하는 것이 목표다.
- 현황/환경 분석 (수정 전 코드 기준):
  1. `src/static/app.js` 의 폴링 루프는 `setInterval(pollProgress, 1500)` 단일 `state.progressPoller` 핸들로 동작했다. `pollProgress()` 는 fetch 후 await 하는데, `/api/progress` 응답이 느리면 다음 `setInterval` tick 이 먼저 발화해 **동시 in-flight 요청이 1 을 넘길 수 있는 구조**.
  2. 대화 전환/로그아웃 시 `stopProgressPolling()` 이 `clearInterval` 만 호출하고 이미 발행된 fetch 를 취소하지 않아, 서버 측에는 **스텁 요청이 뒤늦게 계속 도착**.
  3. `/api/progress` 핸들러는 `_load_steps_for_run(conn, cid, run_id)` 로 **해당 run 의 전체 step 을 매번 파이썬 메모리로 로드**하고 `[s for s in all_steps if step_index > after_step]` 로 필터링했다. 서버 `AgentMemorySteps` 가 쌓이는 장기 대화일수록 폴링 비용이 O(N) 으로 증가.
  4. 서버는 `after_step` 만 받고 `client_run_id` 는 없어서, **클라이언트가 들고 있는 run_id 가 서버 최신 run_id 와 달라도** 서버가 그것을 감지할 수 없었다. 결과: 새 run 이 시작됐는데 클라이언트는 과거 run 의 `after_step` 을 계속 들고 와 **신규 step 0..K 를 놓침**.
  5. `document.hidden` 상태(탭 전환) 에서도 1500ms 주기가 그대로 유지 — 탭이 백그라운드여도 매초 한 번 네트워크/CPU 를 쓴다.
- 설계 (TASK-0036 시점에 실제 적용된 구조, 본 TASK-0037 은 이를 검토·문서화):
  1. **클라이언트 상태 모델 확장** — `state` 에 `progressPollInFlight:boolean`, `progressPollSeq:number`, `progressAbortController:AbortController`, `progressErrorCount:number` 추가. 기존 `progressPoller`(timer handle), `progressSteps`(누적 step 캐시), `progressRunId`(현재 추적 중인 run), `progressAfterStep`(다음 폴링의 after_step 값) 와 결합해 **폴링 생명주기** 를 정확히 모델링.
  2. **`setInterval` → 순번 기반 `setTimeout` 체인** — `scheduleProgressPolling(delayMs, seq)` 는 `clearProgressPollTimer()` 후 `setTimeout(() => pollProgress(seq).catch(()=>{}), nextDelay)` 단 하나만 예약. `pollProgress(seq)` 는 실행 시작 때 `seq !== state.progressPollSeq || progressPollInFlight` 이면 즉시 return, 끝날 때 다시 `scheduleProgressPolling(nextDelay, seq)` 로 다음 한 번을 예약한다. 즉 타임라인 상 항상 `[fetch] → [응답] → [다음 fetch 예약]` 순차 체인 구조가 보장되어 **in-flight 요청 수 ≤ 1** 가 코드로 강제됨.
  3. **AbortController 기반 취소 경로** — 매 poll 마다 `new AbortController()` 를 `state.progressAbortController` 에 저장하고 fetch 에 signal 로 전달. `stopProgressPolling({abort:true})` 는 이를 `.abort()` 호출해 in-flight fetch 를 즉시 끊는다. 추가로 `setTimeout(() => controller.abort(), PROGRESS_FETCH_TIMEOUT_MS=4000)` 로 서버 응답 지연 상한도 보장.
  4. **적응형 폴링 주기** — `PROGRESS_POLL_ACTIVE_MS=1200ms`(신규 step 스트리밍 중), `PROGRESS_POLL_IDLE_MS=3000ms`(기본), `PROGRESS_POLL_HIDDEN_MS=10000ms`(탭 배경화), `PROGRESS_POLL_ERROR_MS=8000ms`(에러 후). `scheduleProgressPolling(delayMs)` 진입부에서 `document.hidden` 이면 `Math.max(delayMs, PROGRESS_POLL_HIDDEN_MS)` 로 하한을 올려, 어떤 경로로 빠른 delay 가 들어와도 탭이 숨겨져 있으면 자동 감속.
  5. **에러 백오프 + 포기 조건** — `progressErrorCount` 를 각 예외 경로(fetch 에러/timeout) 마다 증가시키고, 3회 미만이면 `PROGRESS_POLL_ERROR_MS=8000` 으로 재시도하되 3회 이상이면 아예 재스케줄링하지 않는다(`shouldSchedule = errorCount < 3`).
  6. **서버 `/api/progress` 최적화** — `_load_progress_status(conn, cid)` 로 `(status, status_at, run_id)` 를 단일 커서에서 반환. `_load_steps_for_run(..., after_step=0)` 은 `after_step > 0` 이면 SQL `WHERE step_index > %s` 조건을 직접 걸어 **DB 에서 바로 필터링** (python 측 list comprehension 제거). 핸들러는 async → sync 로 바뀌고(블로킹 mysql 호출과 단순 수식 뿐이라 이벤트 루프 점유 이득 없음), `client_run_id` 가 없거나 서버 최신 run_id 와 다르면 `next_after_step = 0` 으로 리셋해 응답에 해당 run 의 모든 step 을 담아 되돌려준다 — 클라이언트가 `applyProgressPayload` 에서 `runId !== state.progressRunId` 를 감지해 캐시를 새 run 으로 교체.
  7. **라이프사이클 API 일관화** — `startProgressPolling({reset=false, runId=""})` 은 이전 체인을 `stopProgressPolling({reset:false, abort:true})` 로 끊고 `progressPollSeq` 를 한 칸 올린 뒤 `scheduleProgressPolling(0, seq)` 로 즉시 첫 poll 을 예약한다. `stopProgressPolling({reset, abort})` 은 `reset=true` 일 때 `resetProgressTracking()` 을 호출해 캐시/run_id/after_step 을 0으로 복원 — 대화 전환/로그아웃/새 대화 생성 등 "새로 시작해야 하는" 경로에서 명시적으로 reset 을 지정.
- 검증 (코드 리뷰 + 정적 확인 — 이미 커밋된 변경이므로 신규 runtime 배포 불필요):
  1. `grep -c "setInterval" src/static/app.js` = 0. 기존 고정 주기 루프가 폴링 경로에 남아있지 않음.
  2. `grep -nE "PROGRESS_POLL_(ACTIVE|IDLE|HIDDEN|ERROR)_MS|PROGRESS_FETCH_TIMEOUT_MS" src/static/app.js` 로 5 개 상수(lines 67-71) 모두 선언 확인, `scheduleProgressPolling`/`pollProgress` 본문에서 실제 참조.
  3. `progressPollSeq` 증가 지점(3곳): `stopProgressPolling()`, `startProgressPolling()`, `applyProgressPayload()` 계열 콜러에서 새 run 감지 시. 각 poll 은 `seq !== state.progressPollSeq` 로 자신이 구버전인지 체크.
  4. `AbortController` 배치: `pollProgress` 는 `controller = new AbortController()`, `timeoutId = setTimeout(controller.abort, 4000)`, `fetch(url, {signal: controller.signal})`, `finally` 에서 `clearTimeout(timeoutId)` + `state.progressAbortController = null if matches controller`.
  5. 서버 측 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 파라미터를 선언하고 `if not run_id or str(client_run_id or "").strip() != run_id: next_after_step = 0` 조건을 가진다 (line 4405-4406).
  6. 사용자 수신 상태 플로우: `status != 'processing'` 이면 `stopProgressPolling({abort:false})` + `refreshWorkspace(cid)` 호출 — 즉 서버가 done/failed 를 돌려주는 순간 클라이언트 폴링이 종료되고 workspace 가 최종 상태로 refresh 된다.
- 영향/후속:
  1. TASK-0034 같이 턴당 수분 걸리는 워크로드에서도 브라우저에서 `/api/progress` 요청이 쌓이지 않는다. 서버 측 로그/DB/네트워크 부하가 선형에서 상수 시간대로 감소.
  2. 현재는 LEARNINGS.md 에 폴링 패턴 학습 기록이 없다. 본 TASK 로 `LRN-20260422-0011 장시간 작업 폴링은 setInterval 이 아니라 순번 기반 setTimeout 체인 + AbortController + document.hidden 감지가 기본` 을 추가.
  3. TASK-0036 MODIFY 항목(CHG-20260421-0009) 에는 폴링 리팩터가 언급되지 않았다. 본 TASK 에서 별도 CHG 로 분리하지 않고 CHG-20260421-0009 Notes 에 한 줄을 보강하는 대신, 문서화 목적이므로 `CHG-20260422-0010` 으로 따로 기록하는 것이 다른 feature/에이전트 가 "폴링 개선" 키워드로 검색할 때 발견 가능성이 높다 — 따라서 별도 CHG 로 분리.
- 범위 제한:
  - 신규 코드 변경 없음(이미 27127b9 에 반영됨).
  - 문서 갱신만 수행: `docs/TASK.md`(본 항목 + 체크리스트), `docs/MODIFY.md`(CHG-20260422-0010), `docs/LEARNINGS.md`(LRN 추가), `docs/REPORT.md`(검증 결과 한 줄).
- 완료 조건:
  - TASK.md §2 Task Queue 에 TASK-0037 `[x]` 가 올라가고 §3.1 Recently Done 에 본 요약이 들어간다.
  - LEARNINGS.md 에 폴링 패턴 LRN 항목이 추가된다.
  - MODIFY.md 에 CHG-20260422-0010 문서화 전용 엔트리가 append 된다.
  - git commit + push 가 완료된다.

### TASK-0036 상세 설계 (2026-04-21)
- 문제/목적 (사용자 요청 2026-04-21):
  1. 현재 `SYSTEM_PROMPT` 는 `agent_core.py:70` 에 하드코딩되어 있고, 조직/도메인/사용자별 맞춤 지침을 주입할 방법이 없다. 운영 중 "이 Role 은 이렇게 답하게 해달라", "특정 계정은 본인 전용 스타일 지침을 추가하고 싶다" 같은 요구가 반복된다.
  2. 현재 agent 는 `DB_CONNECT_DB` 로 default schema 만 고정되어 있고 `_SYSTEM_SCHEMAS` 외의 모든 user schema 에 무차별로 접근한다. 실제로는 서비스 경계(국가/팀/도메인) 단위로 "이 Product 는 이 DB 세트만 본다" 로 묶어야 한다.
  3. 현재는 Product 가 하나지만(초기 값으로 `KR` 부여, 접근 DB: `dbgame`/`dblog`/`dbauth`), 이후 다른 Product 가 추가될 것이므로 **Role/Account 와 대등한 위상의 정본 테이블** 로 관리해야 한다.
- 현황/환경 분석 (출발점 근거):
  1. `SYSTEM_PROMPT` ([agent_core.py:70](../../feature-0002-agent-core/src/agent_core.py#L70)) 는 `run_agent` ([agent_core.py:935](../../feature-0002-agent-core/src/agent_core.py#L935)) 안 `system_content = SYSTEM_PROMPT` ([L1090](../../feature-0002-agent-core/src/agent_core.py#L1090)) 에서 origin_request/thread_goal/knowledge_ctx 와 합쳐진다. `run_agent` 호출은 web 측 `app.py` 가 in-process 로 수행 ([app.py:3260](../src/app.py#L3260)) 하므로 kwarg 추가가 쉽다.
  2. RBAC 정본은 `WebPermissions` / `WebRoles` / `WebRolePermissions` / `WebAccountPermissionOverrides` 이고 account ↔ role 은 `WebAccounts.RoleId` 이다 ([app.py:1477~1570](../src/app.py#L1477)). Product 는 이 구조와 대등하게 `WebProducts` / `WebProductDatabases` (+ 계정/대화별 Product 참조) 를 추가하면 자연스럽다.
  3. 도구 구현 `tools.py` ([feature-0002-agent-core/src/modules/tools.py:23](../../feature-0002-agent-core/src/modules/tools.py#L23)) 의 `_SYSTEM_SCHEMAS` + `_is_user_schema` 만으로 스키마 필터가 결정된다. 여기에 **실행 시점 whitelist** 를 추가하고 execute_sql 에서 `schema`.`table` 참조를 검사하면 접근 제한이 가능하다.
  4. admin console 은 "대시보드/계정/역할" 3 탭 ([admin.html:24~36](../src/static/admin.html#L24)) 이고, 4 번째 탭 "상품" 추가가 자연스럽다. 프로필 드로우는 "계정/보안/API Vault" 3 탭 ([index.html:187~189](../src/static/index.html#L187)) 이고 여기에 "프롬프트" 탭 추가.
  5. 대화의 Product 결정: `AgentCoreConversations` 에 `product_id` 컬럼 추가. 새 대화는 계정의 default product (추후 account-level 선택 가능) 로 고정. fork 시 원본 product_id 를 그대로 상속.

- 설계 (Plan-Review-Execute, 위험도: Moderate — 신규 테이블 3개 + permission 2개 + admin/prompt API + UI 2곳 + agent_core signature 확장):

  A. DB 스키마 (`_ensure_web_tables` 확장)
     ```
     WebProducts (
       Id BIGINT AUTO_INCREMENT PK,
       ProductKey VARCHAR(32) UNIQUE NOT NULL,   -- 'KR', 'JP', ...
       Name VARCHAR(128) NOT NULL,
       Description VARCHAR(255) DEFAULT '',
       IsActive TINYINT(1) DEFAULT 1,
       IsDefault TINYINT(1) DEFAULT 0,           -- 대화 생성 시 기본 product
       SortOrder INT DEFAULT 100,
       CreatedAt/UpdatedAt
     )
     WebProductDatabases (
       ProductId BIGINT NOT NULL,
       SchemaName VARCHAR(64) NOT NULL,
       Description VARCHAR(255) DEFAULT '',
       SortOrder INT DEFAULT 100,
       CreatedAt,
       PRIMARY KEY (ProductId, SchemaName)
     )
     WebSystemPrompts (
       Id BIGINT AUTO_INCREMENT PK,
       Scope ENUM('product','role','account') NOT NULL,
       ProductId BIGINT NULL,                    -- scope=product: 필수, role/account: nullable(=범용)
       RoleId BIGINT NULL,                       -- scope=role 만 사용
       AccountId BIGINT NULL,                    -- scope=account 만 사용
       Content MEDIUMTEXT NOT NULL,
       UpdatedAt, UpdatedByAccountId,
       UNIQUE KEY UX_Scope (Scope, ProductId, RoleId, AccountId)
     )
     AgentCoreConversations.product_id BIGINT NULL   -- 대화가 속한 Product
     ```
     - seed (`_ensure_seed_products`): ProductKey=`KR`, Name=`Korea`, IsDefault=1, IsActive=1. 연결 DB: `dbgame`, `dblog`, `dbauth`.

  B. Permission 추가 (PERMISSION_DEFINITIONS)
     - `product.manage` (그룹: `관리`) — Product/ProductDatabases CRUD + Product scope prompt 쓰기. 기본으로 admin role 에 부여.
     - `system_prompt.manage.role.any` (그룹: `관리`) — Role scope prompt 쓰기. admin role 에 부여.
     - Account scope prompt 는 본인 자신은 언제나 읽기/쓰기 가능 (별도 permission 불요). 다른 계정의 account scope prompt 는 `system_prompt.manage.role.any` 가 있어야 관리 가능 (감사성 측면).
     - Product 자체 조회(`products.read`)는 "로그인한 모든 계정"에 기본 허용 — 대화 생성 시 product 선택/표시를 위해 필요. 따라서 세션 payload 에 products 목록만 내려주고 별도 permission 체크는 생략한다. CUD 는 `product.manage` 로만 가드.

  C. 시스템 프롬프트 조립 함수 (`agent_core.py`)
     - 신규 함수 `compose_system_prompt(mem_conn, *, product_id, role_id, account_id) -> str`:
       ```
       [BASE SYSTEM_PROMPT]
       (product prompt 있으면) "\n\n## PRODUCT CONTEXT ({product_key})\n{content}"
       (role prompt 있으면)    "\n\n## ROLE GUIDANCE ({role_key})\n{content}"
       (account prompt 있으면) "\n\n## ACCOUNT PREFERENCES\n{content}"
       ```
     - role/account scope prompt 는 `ProductId=NULL`(전 Product 공통) 과 `ProductId=X`(해당 product 전용) 둘 다 가능. product-specific 이 있으면 그걸 쓰고 없으면 generic fallback.
     - Product 가 없거나 prompt 가 비어 있으면 기존 동작(base prompt 만) 과 동일.
     - `run_agent` 는 신규 kwargs `product_id: int | None = None`, `role_id: int | None = None`, `account_id: int | None = None` 을 받아 `system_content = compose_system_prompt(...)` 을 사용. 이어서 기존 `CONVERSATION CONTEXT` + `knowledge_ctx` 를 현재 순서 그대로 뒤에 붙인다.

  D. DB 접근 whitelist (tools.py)
     - 모듈 전역 `_ACTIVE_SCHEMA_ALLOWLIST: set[str] | None = None` 추가. `None` 이면 기존 동작(모든 user schema), set 이면 whitelist 필터 적용.
     - `_is_user_schema` 는 유지하고, whitelist 가 set 이면 그 추가 조건으로 AND 필터. `_tool_list_schemas` / `_tool_describe_schema` / `_tool_describe_table` / `_tool_search_tables` / `_tool_execute_sql` 모두 반영.
     - execute_sql 은 SQL 에서 ``\`schema\`.\`table\``` 또는 `schema.table` 패턴을 정규식으로 추출해 whitelist 밖 스키마가 있으면 즉시 에러(`"접근이 허용되지 않은 스키마: X"`).
     - `run_agent` 는 `allowed_schemas: list[str] | None` kwarg 를 추가로 받아, 실행 시작 시 `tools.set_active_schema_allowlist(...)` 로 세팅하고 종료 시 `None` 으로 복원(try/finally).

  E. app.py 계약
     - 신규 헬퍼: `_get_product_for_conversation(conn, conversation_id)` — `AgentCoreConversations.product_id` 를 읽어 없으면 default product 로 fallback.
     - 새 대화 생성 (`/api/new_conversation`, `/api/fork_conversation`, 자동 생성): `product_id` = request body 의 `product_id` (optional) → fallback 으로 `account` 의 해당 Product (향후) → fallback 으로 default product.
     - `/api/ask` 는 대화의 product_id 를 조회 → 해당 product 의 DB schema 리스트 조회 → `run_agent(..., product_id=pid, role_id=rid, account_id=aid, allowed_schemas=schemas)` 로 전달.
     - 신규 admin API:
       - `GET /api/admin/products` — 목록 (`product.manage` 없이도 읽기 허용 = 공용 카탈로그)
       - `POST /api/admin/products` body: `{product_key, name, description?, is_active?, is_default?, sort_order?}` (`product.manage`)
       - `PATCH /api/admin/products/{id}` — 같은 필드 (`product.manage`)
       - `DELETE /api/admin/products/{id}` — 해당 product 를 쓰는 대화가 있으면 거부 (`product.manage`)
       - `GET /api/admin/products/{id}/databases` — 스키마 목록
       - `PUT /api/admin/products/{id}/databases` body: `{databases: [{schema_name, description?, sort_order?}, ...]}` — 전체 교체 (`product.manage`)
       - `GET /api/admin/system-prompts?scope=product|role|account&product_id=&role_id=&account_id=` — 해당 스코프 리스트
       - `PUT /api/admin/system-prompts` body: `{scope, product_id?, role_id?, account_id?, content}` — upsert. scope=role 은 `system_prompt.manage.role.any`, scope=account 는 본인이 아니면 `system_prompt.manage.role.any` 필요.
       - `DELETE /api/admin/system-prompts/{id}` — 같은 권한 규칙.
     - 신규 self API:
       - `GET /api/auth/me/system-prompts` — 본인의 account scope prompt 목록 (product_id 별)
       - `PUT /api/auth/me/system-prompt` body: `{product_id?, content}` — 본인 upsert (본인 계정 대상은 권한 불요).
     - 세션 응답 (`/api/auth/me`) 에 `products: [{id, product_key, name, is_default}]` 를 추가해 프론트가 드롭다운/라벨에 사용.

  F. UI — admin console
     - 탭 추가 `상품` (admin.html): 대시보드/계정/역할 다음에 배치. 좌측 list + 우측 detail 패턴으로 구성 (기존 Role 관리와 같은 layout 재사용).
     - Detail 구성:
       1. 기본 정보 섹션 (ProductKey/Name/Description/IsActive/IsDefault/SortOrder)
       2. **접근 DB** 섹션 — "계정 카테고리와 별개" 라는 사용자 요구에 따라 구분선 + 명시적 헤더 (`접근 가능 DB 스키마`) 로 그룹화. 해당 product 에 등록된 schema 를 chip 으로 보여주고, 텍스트 입력 + `추가` 버튼 + 각 chip 옆 `×` 삭제.
       3. **시스템 프롬프트** 섹션 (Product scope) — textarea + 저장. scope=product, ProductId=현재 product 로 upsert.
     - Role detail 에도 **시스템 프롬프트** 섹션 추가:
       - Product 드롭다운 (첫 항목 `(전 Product 공통)`, 그 아래 구분선 후 Product 목록) + textarea + 저장. 저장 시 scope=role, RoleId=현재 role, ProductId=(선택값 or NULL).
     - Products 탭은 `product.manage` 가 없으면 read-only 상태(수정/삭제 버튼 disable + 저장시 에러 토스트)로 보인다. 어떤 계정도 product 목록 자체는 볼 수 있어야 profile 화면에서 product 별 prompt 를 지정할 수 있다.

  G. UI — 프로필 드로우
     - 드로우 탭에 `프롬프트` 추가 (계정/보안/API Vault/프롬프트).
     - 내부: Product 드롭다운 (`(전 Product 공통)` 기본값 + 각 Product) + textarea + 저장 + 초기화. 저장 시 `PUT /api/auth/me/system-prompt`.
     - 프로필 탭에서 product 선택을 바꾸면 해당 product scope 의 현재 prompt 를 다시 불러온다.

  H. 대화/Agent 연결
     - `/api/new_conversation` 과 `/api/fork_conversation` 은 생성/복제 시 `AgentCoreConversations.product_id` 에 값을 기록. 기본값은 (body.product_id || account.default_product_id || global default product).
     - `/api/ask` 는 conversation.product_id 를 조회해 `product_id` + `allowed_schemas` + `role_id` + `account_id` 를 `run_agent` 에 넘긴다.
     - `run_agent` 는 `allowed_schemas` 를 tools 전역에 set/clear 하고, `compose_system_prompt` 결과로 system message 를 만든 뒤 기존 흐름대로 진행.

- 검증 계획:
  1. `python3 -m py_compile` 로 agent_core.py / app.py / tools.py 문법 확인.
  2. 컨테이너 재빌드 (`make web`, `make agent`) 후 bootstrap_admin 로그인 → `/api/admin/products` GET → KR seed 확인 → `/api/admin/products/{kr_id}/databases` GET → `dbgame,dblog,dbauth` 3건 확인.
  3. `PUT /api/admin/system-prompts` 로 Product scope prompt 생성 → Role scope prompt 생성 → 본인 account scope prompt 생성.
  4. `/api/ask` 로 질의 → agent 가 받은 system message 에 `## PRODUCT CONTEXT (KR)` / `## ROLE GUIDANCE (admin)` / `## ACCOUNT PREFERENCES` 가 순서대로 주입되었는지 agent 응답의 steps 로그에서 확인.
  5. whitelist 밖 schema (e.g. `mysql.user`) 를 execute_sql 로 호출했을 때 거부되는지 확인.
  6. 브라우저 수동: admin 의 Products 탭 + Roles detail 의 prompt 영역 + 프로필의 프롬프트 탭이 모두 렌더되는지 확인.

- 비-목적 (Out of Scope):
  - Product 별 계정 멤버십 ACL (`WebAccountProducts`). 이번은 모든 계정이 모든 active product 접근 가능한 MVP.
  - Product 별 RBAC override 매트릭스. 현재 permission 체계는 RBAC 만 쓰고, "이 Role 이 이 Product 에서만 유효" 같은 scoping 은 별 과제로 둠.
  - `_tool_execute_sql` SQL parsing 정확도: quoted identifier 가 아닌 서브쿼리 내부 복잡 참조는 표면적 regex 로만 검사. full sqlparse 도입은 후속 과제.

- TASK-0035 (2026-04-21 마감): 사이드바가 `내 대화` / `타 계정 대화 (N)` 섹션으로 분할 노출되고 내 대화는 좌측 primary 컬러 바 + 틴트, 타 계정 대화는 owner 뱃지 강조로 구분된다. 말풍선의 user 메시지도 `is-own-message` / `is-other-message` 로 톤이 분리되며, meta 라벨은 `나 (<username>)` 또는 `<owner_username>` 을 표시한다. `POST /api/fork_conversation` 이 `conversation.create` + `read.own/any` 권한에 맞춰 원본 topic 과 메시지(internal 제외)를 새 대화로 복제하며, 복제본 topic 에는 `[Fork]` 접두사를 붙인다. 헤더 `대화 복사` 버튼은 전체 복제, 말풍선 hover 액션 `여기서 분기` 는 부분 복제(`from_message_id` 지정) 를 수행한다. 검증: `docker compose run --rm -T web python -m py_compile src/app.py` OK, 브라우저 스크립트 `curl -sk ... /api/fork_conversation` 로 전체 복제 6건/부분 복제 3건(source 20260421075518-571abdb6) 모두 HTTP 200 반환, 새 conversation_id 20260421082459-c039abbd / 20260421082523-d9fbb21b 에 topic `[Fork] ...` 접두어와 MetaJson 내 `forked_from_message_id` 저장 확인.

### TASK-0035 상세 설계 (2026-04-21)
- 문제/목적 (사용자 요청 2026-04-21):
  1. 사이드바 대화 목록에서 자신의 대화인지, 타 계정 대화인지 **한눈에 구분이 안 된다**. 현재는 `conv-item-meta` 마지막에 작은 회색 글자로 `owner_username` 만 표시되어, admin 으로 로그인해 전체 대화를 볼 때 본인 대화가 파묻힌다.
  2. 타 계정 대화는 조회만 가능하고 composer 가 잠겨 있어(`renderComposer` 의 `!isOwnConversation(...)` 분기), **타 계정 대화를 그대로 이어서 질의할 수 없다**. 따라서 "이 대화의 지금까지 맥락을 가져와서 내 대화로 이어서 질문" 하는 경로가 필요하다.
  3. 동일한 요구가 자기 대화 내에서도 발생 — 특정 중간 응답(가설/분기점)에서부터 다른 방향으로 실험해 보고 싶을 때 **현재 대화를 오염시키지 않고** 그 지점까지 복제한 새 대화가 있으면 안전하다.
- 현황/환경 분석 (출발점 근거):
  1. `_list_conversations` ([app.py:1629](../src/app.py#L1629)) 는 `owner_account_id`, `owner_username`, `last_activity_at` 을 모두 반환하지만, 프론트엔드 `renderConversationList` ([static/app.js:588](../src/static/app.js#L588)) 는 단일 리스트로 `owner_username` 만 소극적으로 덧붙인다.
  2. `isOwnConversation` ([static/app.js:319](../src/static/app.js#L319)) 이 `Number(conversation.owner_account_id) === Number(state.user.id)` 기준으로 소유 판정 로직을 이미 갖고 있어, 하이라이트/정렬 로직에서 재사용 가능하다.
  3. `renderMessages` ([static/app.js:1153](../src/static/app.js#L1153)) 는 role 만으로 "사용자 / Assistant" 를 표시한다. `user` 메시지는 현재 대화 소유자가 보낸 것이므로, 대화 소유자가 현재 계정이면 "나 (<username>)", 아니면 `owner_username` 으로 라벨링하면 정보량이 크게 올라간다.
  4. `/api/new_conversation` ([app.py:3171](../src/app.py#L3171)) 는 빈 대화만 만든다. 메시지 복사는 별도 API 가 필요하다.
  5. `AgentMemoryMessages` 는 `(ConversationId, Role, Content, CreatedAt, MetaJson)` 스키마이고, `memory.py` 의 insert 문 ([memory.py:867](../../feature-0002-agent-core/src/modules/memory.py#L867)) 은 CreatedAt 을 DEFAULT CURRENT_TIMESTAMP 에 의존한다. fork 시에는 **원본 CreatedAt 을 보존** 해야 원본과 동일한 시계열로 재생된다 → 별도 insert 쿼리(CreatedAt 포함) 를 API 레벨에서 직접 발행.
  6. `_get_history` ([app.py:2343](../src/app.py#L2343)) 와 `_is_internal_message` 는 internal 플래그가 붙은 시스템 메시지를 표시에서 제거한다. fork 에서는 **표시되는 메시지만** 복사해 새 대화를 "깨끗하게" 시작할 수 있도록 한다.
- 설계 (Plan-Review-Execute, 위험도: Minor — UI 레이어 추가 + 신규 API 1개, 기존 스키마/권한 체계 변경 없음):
  A. 사이드바 구분/정렬 (프론트엔드)
     - `renderConversationList` 를 **own-first 그룹핑** 으로 재구성: `state.conversations` 을 `isOwnConversation(item)` 으로 파티션 → `own` 블록 + `others` 블록. 각 블록은 기존 ORDER(`updated_at DESC`) 를 그대로 따른다.
     - 각 블록 앞에 `.conv-group-title` (섹션 헤더) 을 삽입: "내 대화" / "타 계정 대화 (<count>)". 타 계정 블록은 item 이 1건 이상일 때만 노출.
     - `conv-item` 에 `is-own` / `is-other` 클래스 추가. 활성 하이라이트(`is-active`) 와 독립적.
     - CSS (`styles.css`):
       * `.conv-item.is-own` → `border-left: 3px solid var(--primary)`(내 대화 좌측 컬러 바) + 약한 `background` 틴트.
       * `.conv-item.is-other` → `border-left: 3px solid transparent` + `.conv-item-meta` 의 owner_username 을 bold/색 강조(`var(--text-2)`) 처리.
       * `.conv-item.is-own .conv-owner` 는 "나" 로 라벨, `.conv-item.is-other .conv-owner` 는 `owner_username` 을 그대로 노출.
       * `.conv-group-title` → 11px, uppercase, letter-spacing 0.06em, muted 톤.
  B. 말풍선 소유자 라벨/하이라이트 (프론트엔드)
     - `renderMessages` 에서 현재 대화를 `currentConversation()` 로 잡아 `isOwn = isOwnConversation(conversation)`, `ownerLabel = conversation.owner_username || "사용자"` 를 계산.
     - user 메시지 meta 라인: `isOwn ? "나 (" + state.user.username + ")" : ownerLabel` → 기존 "사용자" 라벨 교체.
     - user 메시지 row 에 `is-own-message` 또는 `is-other-message` 클래스 부여.
     - CSS: `is-own-message .message-bubble` → 기존 primary 톤 유지(현 상태), `is-other-message .message-bubble` → 중성 grey 톤(`--bg`, border `var(--border)`) 으로 색상 분리해 "내가 보낸 글" 과 혼동 방지. assistant 말풍선은 계정과 무관하므로 변경 없음.
  C. 대화 fork API (백엔드)
     - 신규 엔드포인트 `POST /api/fork_conversation` ([app.py:3171](../src/app.py#L3171) 근처, `new_conversation` 바로 아래 배치):
       ```
       request body: {
         source_conversation_id: str (required),
         from_message_id: int | null   // 이 ID 까지(포함) 복사. null/누락 시 전체 복사.
       }
       response: { conversation_id: str, copied: int, source: str }
       ```
     - 권한:
       * 현재 계정이 `conversation.create` 를 가져야 한다 (not owned).
       * 원본 대화에 대해 `_account_can_access_conversation(conn, account, source, "conversation.read.own", "conversation.read.any")` 가 True 이어야 한다.
     - 절차:
       1. 원본 존재/권한 검증. 실패 시 404/403.
       2. `agent_core.create_new_conversation(conv_file=_account_conv_file(id))` 로 새 cid 발급 + `_assign_conversation_owner(conn, cid, account_id, force=True)`.
       3. topic 복사: 원본 topic 조회 후 `_set_conversation_topic(conn, cid, "[Fork] " + original_topic)`. (기존 `rename_conversation_title` 의 topic 쓰기 경로를 재사용한다.)
       4. `AgentMemoryMessages` 에서 `ConversationId = source` AND (`from_message_id` 있으면 `Id <= from_message_id`) 조건으로 Role/Content/CreatedAt/MetaJson 을 ORDER BY Id ASC 로 가져와, 새 cid 로 **원본 CreatedAt 을 그대로 유지한 채** 재삽입. `_is_internal_message` 가 True 인 row 는 skip (internal=True 인 시스템 메모는 fork 대상 아님).
       5. MetaJson 에 `forked_from_conversation_id`, `forked_from_message_id`(또는 null) 를 추가해 추적성 보존.
       6. `_set_account_current_conversation(conn, account_id, cid)` 로 새 대화를 활성화 후 JSON 응답.
     - 실패/롤백: 중간 예외 시 이미 생성된 새 대화는 `delete_conversation_records(conn, cid)` 로 정리 후 500.
  D. 대화 fork UI (프론트엔드)
     - 헤더 버튼: `index.html` `chat-header-tools` 에 `<button id="forkConversationBtn">대화 복사</button>` 추가. 활성 대화가 있고 `conversation.create` 권한이 있으면 visible, 없으면 `is-access-blocked`.
     - 말풍선 단위 fork: `renderMessages` 에서 각 message row 에 `message-actions` 액션 바를 생성하고 `여기서 새 대화로 분기` 버튼을 둔다. 호버 시 opacity 가 올라오는 pattern (기존 hover 스타일 참고). click → `forkConversation(from_message_id=message.id)`.
     - 공통 함수:
       ```js
       async function forkConversation({ fromMessageId = null } = {}) {
         const src = state.activeConversationId;
         if (!src) return;
         if (!can("conversation.create")) { showPermissionDeniedToast("conversation.create"); return; }
         const payload = await apiFetch("/api/fork_conversation", {
           method: "POST",
           body: JSON.stringify({ source_conversation_id: src, from_message_id: fromMessageId }),
         });
         showToast(fromMessageId ? "선택한 지점까지 새 대화로 복제했습니다." : "대화를 새 대화로 복제했습니다.");
         await refreshWorkspace(payload.conversation_id || "");
       }
       ```
     - 비-own 대화에서도 `conversation.create` 만 있으면 fork 가 허용되므로, 기존 "읽기 전용 대화" 문구 아래에 "대화 복사" 버튼을 강조 노출한다 (read-only UX 의 탈출구 제공).
- 테스트/검증:
  1. `python3 -m py_compile repo/unit/feature-0003-agent-web-ui/src/app.py` 로 문법/import 점검.
  2. 브라우저 수동 검증: 로그인 → 내 대화/타 계정 대화가 섹션 분리 + 하이라이트로 구분되는지 확인. admin 계정에서 본인 대화가 상단으로 정렬되는지 확인.
  3. fork 수동 검증:
     - 자기 대화에서 "대화 복사" → 새 대화 cid 반환 + 사이드바 "내 대화" 블록에 추가됨.
     - 타 계정 대화에서 특정 assistant 말풍선의 "여기서 분기" → 해당 말풍선 id 까지 복사된 새 대화가 나에게 생성됨.
     - 새 대화의 topic 이 `[Fork] ...` 로 표시되는지 확인.
     - 새 대화에서 composer 가 열려 추가 ask 가 가능한지 확인.
  4. 권한 분기 검증: `conversation.create` 가 없는 viewer 계정에서 fork 버튼이 `is-access-blocked` 로 표시되고 클릭 시 토스트만 뜨는지.
- 비-목적(Out of Scope):
  - 메시지 meta 의 steps/csv/sql 아티팩트 복제. (MetaJson 은 그대로 복제되지만, `/shared/...` 에 있는 CSV 파일은 그대로 원본 경로를 참조한다. 파일 접근은 `conversation.file.read.*` 권한과 `_account_can_access_conversation` 으로 여전히 통제되므로 fork 소유자가 원본 파일에 대한 접근 권한을 갖고 있지 않으면 링크 클릭 시 403 을 받는다. 이 범위는 현 작업에서 변경하지 않는다.)
  - 실시간 동기화(원본 대화가 뒤에 더 쌓여도 fork 된 대화에는 반영되지 않음 — snapshot 시맨틱 유지).
  - agent-core 내부 `ConversationState` 마이그레이션(대화별 run state 는 새 대화에서 깨끗하게 시작).

### TASK-0034 상세 설계
- 문제/목적 (사용자 요청 2026-04-21):
  - 현재 구성된 assistant (RBAC/SQL agent/Insight/Local+API LLM) 가 실제로 **복잡한 도메인 질의** 에서 얼마나 정확한 답을 내놓는지 체계적으로 확인하고, 이후 개선 이슈의 근거로 쓰고자 함.
  - 정확한 답변을 위해 **한 대화 안에서 최대 20회 까지 질의를 이어간다** (= 사용자 역할을 하는 테스트 러너가 추가 질문/구체화 요청으로 agent 를 보조) 는 가정으로 진행.
  - 구성: **local LLM 5 대화 (성능 한계 → 직렬)** + **상용 API 5 대화 (모델 = gpt-5 mini → 이 저장소의 `gpt-5.4-mini`, 병렬 가능)**.
  - API 키는 `.env` 의 `OPENAI_API_KEY` 재사용 승인됨.
  - **실제 DB 데이터와 정확히 일치하는지 별도 검증**: 같은 질문을 사람이 직접 MySQL 쿼리로 풀어서 그 결과를 assistant 의 최종 답변과 1:1 대조한다.
  - 기본 예시 3 개는 주어졌고, 더 복잡한 변주도 가능하면 포함한다.
- 기준 예시 질문 (사용자 제공):
  1. dblog 에서 **영웅스킬 업그레이드의 가장 대중적인 테크트리** 를 영웅별 및 테크트리별로 집계.
  2. dblog 에서 **전투시작 관련 테이블 통계** — 전투시작 구성 영웅 중 가장 많이 사용된 50종의 참여 횟수/채택률.
  3. 한정가챠 — **유저가 특정 상품일 때만 시도하고 나머지는 만료** 시키는 패턴을 근거로, "가치가 높은 상품" 이 무엇인지 집계 (이진 플래그 기반).
- 원인/환경 분석 (본 작업의 출발점):
  1. `/api/ask` 가 commercial 모델 사용 시 클라이언트 측에서 **PBKDF2-HMAC-SHA256(100000 iter, 32byte) + AES-GCM, `v1:<salt_b64>:<iv_b64>:<ct_b64>`** 포맷으로 암호화된 API key 를 요구 ([app.py:1003](../src/app.py#L1003) `_decrypt_api_key`). 즉 브라우저 없이 curl 로만 commercial 테스트를 하려면 동일 포맷의 암호 헬퍼가 별도로 필요하다.
  2. Local LLM 경로는 `model ∈ {"auto","edge","core","code"}` 이고 API key 를 요구하지 않는다 ([model_catalog.py](../../feature-0002-agent-core/src/modules/model_catalog.py)). Local LLM 은 `local-llm-gateway:8080/v1` 단일 프로세스라 병렬 대화가 큐 경합으로 느려지므로 **직렬** 지시가 적절하다.
  3. 기본 인증은 HttpOnly 세션 쿠키이므로 `/api/auth/login` → 쿠키 jar 저장 → `/api/ask` 재사용 흐름을 그대로 쓸 수 있다. `bootstrap_admin` 은 RoleId=3 (admin) 으로 `conversation.ask`/`conversation.create`/`conversation.read.any`/`conversation.file.read.any` 등 필요한 권한을 모두 보유(확인됨 `SELECT ... webrolepermissions WHERE RoleId=3 AND Code LIKE 'conversation%'`).
  4. DB 스키마 사전 조사:
     - `dblog.battlebegin` (533k rows). `MyHeroInfo` 컬럼이 JSON 배열 `[{Index, Level, Star, Skill:[5 levels], Equip..., Transcend...}, ...]` — **질문 1 (영웅스킬 테크트리) + 질문 2 (영웅 사용 빈도) 의 공통 자원**.
     - `dblog.battleend` (555k rows). `Win/Star/PlayTime` 포함 — BattleType 별 성과 지표 확장 가능.
     - `dblog.equipoptionupgrade` (8.7k rows). `OptionIndex, OptionStep` — "장비 옵션 업그레이드 테크트리" 로 해석할 여지 있으나 질문 1 의 본질은 MyHeroInfo.Skill[] 분포.
     - `dblog.equipgacharecord` (165 rows). `HighGachaCategory` 는 comma-separated 카테고리(`"25,71,13,2"`) 와 클래스명(`"NewHero"`, `"Wizard"` 등) 이 섞여 저장되어 있음. 행 수가 매우 적지만 질문 3 이 요구하는 "이진 플래그 기반 한정가챠 가치 판별" 의 뚜렷한 resource — assistant 의 희소 데이터 해석력 테스트에 오히려 적합.
     - 추가 대형 테이블: `dblog.currency` (2.84M), `dblog.equipget` (1.8M), `dblog.equipremove` (1.6M), `dblog.gold` (899k), `dblog.battlebeginaffixv2` (562k), `dblog.battleendaffixv2` (511k), `dblog.gemv2` (308k). 이들은 추가 복잡 질의(재화 유출입/장비 수명주기/전투 affix 영향) 에 쓸 수 있음.
- 5 개 복잡 질문 설계 (local LLM 5 대화 × 상용 API 5 대화 공통, 동일 질문 쌍으로 두 경로를 비교):
  1. **Q1 영웅스킬 업그레이드 테크트리 랭킹** — dblog 기준, 영웅(Index)별로 [Skill1, Skill2, Skill3, Skill4, Skill5] 레벨 조합(= "테크트리") 의 등장 빈도를 집계해 영웅별 상위 5 테크트리(+테크트리별 전체 상위 20) 를 리스트업. 데이터 소스: `battlebegin.MyHeroInfo` 배열을 JSON 풀어서 집계. (battlebegin 한 row 당 여러 hero 가 들어 있음에 주의 — assistant 가 스스로 풀어내는지 관찰 포인트.)
  2. **Q2 전투시작 영웅 사용 Top 50** — `battlebegin.MyHeroInfo` 를 펼쳐 hero Index 별 등장 수(= 참여 횟수) 와 채택률(= 등장 수 / 전체 battlebegin 행 수) 을 계산. 전체 영웅 종 수와 rank, 채택률 소수점 2자리 보고.
  3. **Q3 한정가챠 가치 품목 판별** — `equipgacharecord` 에서 (a) 유저가 실제로 **가챠를 진행한 행위** 와 (b) 만료/미진행 으로 보이는 **카테고리 노출 기록** 을 구분하고, 진행 행위가 많았던 카테고리(또는 코드) ↔ 일반 노출뿐이었던 카테고리 간 차이를 도출. 카테고리가 comma-separated 이므로 "이진 플래그" 해석을 assistant 가 잡아내는지가 관건.
  4. **Q4 BattleType 별 승률 × 평균 플레이타임** — `battlebegin` ↔ `battleend` 를 (AccountId, Time window) 로 매칭하여 BattleType 별 전투 수 / 승률 (`SUM(Win) / COUNT(*)`) / 평균 PlayTime / 평균 Star 를 도출, 상위 10 BattleType 랭킹. JOIN 정의가 애매하므로 assistant 의 스키마 탐색/LIMIT 프로빙 능력 관찰.
  5. **Q5 영웅 레벨/스타 분포로 본 "육성 된 메타 영웅" Top 20** — 각 영웅 Index 에 대해, 전투에 투입된 **최고 Level**, **평균 Level**, **Star ≥ 2 비율**, **총 등장 수** 를 계산해 "많이 나오면서 평균 레벨/스타도 높은" 영웅 Top 20. rank 산식은 assistant 가 합리적으로 제시하게 두고 검증 시 동일 산식을 사람 쿼리로 재현해 비교.
  - 모든 5 질문은 두 모델 경로에서 동일하게 사용 → 같은 질문에 대한 local vs API 응답 품질 비교 가능.
- 대화 프로토콜 (1 질문 → 1 "대화" 단위, 최대 20 turn):
  - **turn 1**: 주 질문을 그대로 던진다.
  - **turn 2~N**: assistant 가 부분 답/진행 중/스키마 탐색 중이면 러너가 보조 프롬프트 ("스키마를 먼저 확인해주세요", "JSON 안의 Skill 배열을 풀어서 집계해주세요", "가능하면 영웅별 Top 5 로 잘라주세요", "각 수치에 대해 어떤 쿼리를 썼는지 같이 보여주세요") 를 순차 제공.
  - 종료 조건 (다음 중 하나):
    a. assistant 가 명확한 최종 답 (표/CSV + 요약) 을 내고 러너가 "이제 충분합니다" 판단.
    b. 20 turn 도달.
    c. `/api/ask` 가 인증 만료/서버 500 반환 → turn 간격 유지를 위해 재로그인 1 회 시도 후 실패하면 종료.
  - 대화 1 건당 메타: `{model, conversation_id, turns: [{user, assistant_answer, sql_list, csv_preview, elapsed_s}], final_verdict}`.
- 테스트 하니스 설계:
  - 위치: `/root/download/docker/mysql_ai_delegated_dev/repo/unit/feature-0003-agent-web-ui/tests/task0034_runner.py` (신규, 테스트 전용). 실제 배포 코드가 아님.
  - 의존: `httpx`, `cryptography` (PBKDF2 + AESGCM). 두 라이브러리는 repo web 이미지에 이미 포함됨 — host 의 `python3 -m pip` 대신 `docker compose run --rm -T web python` 으로 실행해도 되고, host 에 이미 설치되어 있으면 host 에서 바로 실행 가능 (둘 다 시도 가능하도록 설계).
  - 주요 함수:
    ```python
    def encrypt_api_key(plain: str, passphrase: str) -> str:
        # salt(16B rand) + iv(12B rand) + PBKDF2HMAC-SHA256(iter=100_000, len=32)
        # → AESGCM encrypt → "v1:<b64 salt>:<b64 iv>:<b64 ct>"
    def login(client, username, password) -> None                 # POST /api/auth/login
    def new_conversation(client, model) -> dict                   # POST /api/new_conversation
    def ask(client, message, model, conversation_id,
            api_key_cipher=None, api_key_passphrase=None,
            timeout=600) -> dict                                   # POST /api/ask
    def run_conversation(question, model, api_key, max_turns=20) -> dict
    ```
  - 상용 API 경로: `ask()` 호출 시 매 턴마다 암호화된 cipher + 새 passphrase 같이 전송 (서버 측 복호화 → upstream OpenAI 호출).
  - Local LLM 경로: `api_key_cipher=None`, `model ∈ {"core","edge","auto"}`. 본 테스트는 `core` 고정 (agent 기본 권장).
  - 실행 전략:
    - 상용 5 대화: `asyncio.gather` 5 병렬 (`gpt-5.4-mini`).
    - Local 5 대화: `for` 루프 직렬 (`core`).
  - 결과 저장: `/root/download/docker/mysql_ai_delegated_dev/repo/unit/feature-0003-agent-web-ui/tests/task0034_runs/{local|api}-{qid}.json` — 각 대화의 전체 turn 로그 + 최종 답변 + 모든 SQL + CSV preview path 포함.
- DB 대조 검증 설계:
  - 질문별 **사람 정답 쿼리** 를 별도 파일 `tests/task0034_truth.sql` 에 기록 (Q1~Q5). 예:
    ```sql
    -- Q2 (참고): hero 사용 Top 50
    SELECT h.hero_index, COUNT(*) AS appearances,
           ROUND(COUNT(*) / (SELECT COUNT(*) FROM dblog.battlebegin WHERE MyHeroInfo IS NOT NULL) * 100, 2) AS adoption_pct
    FROM dblog.battlebegin b,
         JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero_index INT PATH '$.Index')) h
    WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
    GROUP BY h.hero_index
    ORDER BY appearances DESC
    LIMIT 50;
    ```
  - 검증 스크립트 `tests/task0034_verify.py`: assistant 가 낸 최종 Top-N 리스트 vs truth 쿼리 결과를 **(key, count) tuple set 비교 + rank 순서 비교** 로 확인. 일치율 % 와 불일치 항목 diff 출력.
  - 모호한 질문(Q3, Q5) 은 "논리적으로 맞는 범위" 를 기준으로 판정 기록 (완전 일치 가능 여부를 리포트에 명시).
- 결과 리포트:
  - `tests/TASK-0034-REPORT.md` — 질문별로 (a) assistant 최종 답변 요약, (b) 사람 truth 결과, (c) 일치/불일치, (d) 몇 턴 만에 수렴, (e) 관찰된 개선 포인트.
  - LEARNINGS 는 (**LRN-20260421-0010**) "복잡 QA 에서 agent 가 어디에서 막히거나 무한 재시도하는지, 어떤 휴리스틱을 추가하면 턴 수를 줄일 수 있는지" 한 줄 패턴으로 정리.
- 범위 제한:
  - 프로덕션 UI/백엔드 코드 변경 **금지**. 오직 테스트 하니스 신규 파일 추가 + 결과 문서만.
  - 결과 저장 CSV 원본 (agent 가 `/data/artifacts` 에 남기는 실제 파일) 은 repo 에 체크인하지 않음 — 로그 JSON 의 `preview` 10 행만 커밋.
  - `.env` 의 실제 API key 는 **절대 로그에 남기지 않는다**. 러너가 키를 메모리에 로드해서 암호화·전송 후 즉시 해제.
  - 본 테스트 실행 중 agent 가 만든 대화/메타데이터(webaccounts/conversations) 는 정리하지 않고 남겨 둠 — 사용자가 이후 UI 로 참고 가능.
- 검증 기준 (본 TASK 자체의 완료 조건):
  1. local 5 + API 5 총 10 대화가 실제로 실행되어 JSON 로그로 남았다.
  2. 각 대화의 turn 수 / 최종 답변 / SQL 목록 / 경과 시간이 로그에서 읽힌다.
  3. 5 질문 각각에 대해 DB truth 쿼리를 사람이 돌려본 결과와 assistant 답변을 비교한 diff 가 REPORT.md 에 기록되었다.
  4. LEARNINGS.md 에 이번 실험에서 발견된 구조적 개선점(LRN 항목 신규) 이 추가되었다.
  5. 커밋/푸시까지 완료.

### TASK-0033 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 말풍선 안의 `실행 단계 및 쿼리 결과 보기` 를 펼치면 **바깥 채팅 로그(`.messages`) 스크롤 + 말풍선 상세 본문(`.message-details-body`) 스크롤** 두 개가 중첩되어, 사용자가 대화 전체를 마우스 휠로 훑을 때 경계에서 "턱턱" 끊기는 느낌이 난다.
  - 사용자 요청: **바깥 스크롤(= 말풍선 body cap)은 최대한 나타나지 않도록** 본문을 확장해달라.
  - 결과셋의 행/열이 많을 때 (특히 열이 10개 이상) 어느 행/열을 보고 있는지 **위치 파악이 어렵다**. 기본적으로 RowCount(행 번호) 컬럼이 있어야 하고, 1행(헤더)/1열(번호)은 스크롤해도 **틀 고정(freeze)** 되어야 한다.
- 원인:
  1. [styles.css:849-859](../src/static/styles.css#L849-L859) `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; padding-right: 4px; }` — TASK-0030 에서 말풍선 폭/스크롤 격리 목적으로 넣었지만, 내부의 `.sql-block`/`.result-table-wrap` 가 이미 각자 cap 을 가지므로 바깥 body cap 은 **중복 방어**. 중복된 cap 때문에 같은 콘텐츠에 대해 스크롤 컨테이너가 2개 생기고, 마우스 휠이 경계를 넘을 때마다 어느 컨테이너가 휠을 소비할지 바뀌어 "턱턱" 멈춤이 발생.
  2. [styles.css:913-920](../src/static/styles.css#L913-L920) `.result-table-wrap { ...; overscroll-behavior: contain; max-height: 320px; }` + [styles.css:907-909](../src/static/styles.css#L907-L909) `.sql-block { ...; overscroll-behavior: contain; max-height: 240px; }` — `overscroll-behavior: contain` 은 자식이 경계에 도달해도 휠을 부모로 **전파하지 않는다**. 그래서 테이블/SQL 내부 스크롤이 바닥/천장에 닿으면 `.messages` 로 올라가지 못하고 그대로 멈춤 — 이것도 "턱턱" 느낌의 큰 원인.
  3. [app.js:734-781](../src/static/app.js#L734-L781) `buildResultTable()` — 데이터 컬럼만 그대로 th/td 로 렌더. RowCount 컬럼 없음. thead th / 첫 컬럼 td 모두 `position: static` 이라 내부 스크롤 시 헤더/첫 열이 함께 밀려 보이지 않게 됨.
  4. [app.js:801-825](../src/static/app.js#L801-L825) `loadFullCsvIntoTable()` — 전체 데이터 로드 시에도 `header.forEach` / `body.forEach` 만 사용, RowCount 를 따로 추가하지 않음.
- 목표:
  1. 말풍선 상세 본문(`.message-details-body`) 의 수직 스크롤 컨테이너를 **제거** — 본문이 콘텐츠 높이만큼 자연스럽게 자라고, 전역 세로 스크롤은 채팅 로그(`.messages`) 하나로 통일. 같은 말풍선 안에 스크롤바 2개가 동시에 뜨는 상황을 근본 제거.
  2. 결과 테이블/SQL 블록은 여전히 **자체 내부 스크롤**을 가지지만, 내부가 경계에 닿으면 `.messages` 로 휠이 **전파**되어 끊김 없이 상하 흐름이 이어져야 한다.
  3. 모든 결과 테이블에 **RowCount 컬럼**(첫 컬럼 `#`) 이 항상 포함되어, 스크롤 중에도 몇 번째 행인지 바로 알 수 있다.
  4. 결과 테이블의 **첫 행(헤더) + 첫 열(#)** 은 내부 스크롤 동안 고정되어 보인다(Excel 의 `Freeze first row + first column` 과 동일한 개념).
  5. "전체 데이터 보기" 로 CSV 전체를 로드해도 동일하게 RowCount + freeze 가 유지된다.
- 접근:
  1. **`.message-details-body` 단일화** — `max-height`, `overflow`, `overscroll-behavior`, `padding-right` 제거. 말풍선 본문은 자연스럽게 자라고, 채팅 로그(`.messages`) 가 유일한 세로 스크롤 컨테이너가 된다. TASK-0030 의 scroll anchor(summary 클릭 시 `messageLogEl.scrollTop` 보정) 은 그대로 동작 — 애초에 `messageLogEl` 기준으로 측정하므로 inner cap 유무와 무관.
  2. **내부 컨테이너 휠 전파 허용** — `.result-table-wrap`, `.sql-block` 의 `overscroll-behavior: contain` 제거. 스크롤 자체는 남기되 경계에서 부모(.messages)로 휠이 넘어가게 한다. 내부 max-height 은 조금 넉넉히 — `.result-table-wrap { max-height: min(60vh, 460px) }`, `.sql-block { max-height: min(40vh, 320px) }` 로 상향(사용자의 "최대한 바깥 스크롤이 나타나지 않도록 확장" 요청 반영).
  3. **`buildResultTable()` 에 RowCount 삽입** — thead 에 `<th class="col-rownum">#</th>` prepend, tbody 의 각 tr 에 `<td class="col-rownum">{i+1}</td>` prepend. 데이터 컬럼 카운트는 그대로 `columns.length` 로 유지(meta 의 `N열` 문구 영향 없음).
  4. **sticky freeze CSS**:
     ```css
     .result-table { border-collapse: separate; border-spacing: 0; }
     .result-table thead th {
       position: sticky; top: 0; z-index: 2;
       background: var(--bg);
       box-shadow: inset 0 -1px 0 var(--border);
     }
     .result-table th.col-rownum,
     .result-table td.col-rownum {
       position: sticky; left: 0; z-index: 1;
       background: var(--bg);
       color: var(--text-muted);
       font-variant-numeric: tabular-nums;
       text-align: right;
       min-width: 40px;
       width: 40px;
       box-shadow: inset -1px 0 0 var(--border);
     }
     .result-table thead th.col-rownum { z-index: 3; }  /* corner: 두 축 모두 최상위 */
     ```
     `border-collapse: separate` 는 sticky 셀에 border 가 제대로 그려지도록 필요 — box-shadow 로 border 대체.
  5. **`loadFullCsvIntoTable()` 동일 패턴 적용** — thead 재구성 시 `#` 먼저, tbody 재구성 시 각 tr 에 `i+1` 먼저.
  6. 기존 `result-table th:last-child, td:last-child { border-right: none }` 는 유지(마지막 데이터 컬럼의 우측 border 제거). sticky 코너가 배경색과 일치해 content 가 뒤쪽으로 비치지 않도록 `background: var(--bg)` 확인.
- 범위 제한:
  - backend API / `preview_table` 응답 스키마 변경 없음. RowCount 는 순수 클라이언트 가상 컬럼.
  - Navigator(`sql-navigator`) 구조/키보드 로직 변경 없음.
  - 말풍선 폭 정책(TASK-0030) 변경 없음.
  - SQL 블록 구조(pre tag) 변경 없음 — 기존 `formatSqlForDisplay()` / pre-wrap 유지.
- 검증 기준:
  1. 쿼리 결과 ≥ 20행을 포함한 말풍선을 펼쳤을 때 `.message-details-body` 에 scrollbar 가 나타나지 않는다(`overflow` 제거 확인).
  2. 결과 테이블 영역에서 세로 스크롤 시 헤더 row 가 상단에 고정되어 보인다 (`getComputedStyle(thead th).position === 'sticky'`).
  3. 가로 스크롤 시 `#` 컬럼이 좌측에 고정되어 보인다 (`getComputedStyle(td.col-rownum).position === 'sticky'`).
  4. 결과 테이블 내부에서 세로로 스크롤하다 바닥/천장에 닿으면 `.messages` 로 휠이 전파되어 채팅 전체 스크롤이 이어진다(overscroll-behavior 제거 효과).
  5. "전체 데이터 보기" 클릭 후에도 #/sticky 동작 유지.
  6. 단일 말풍선 내부에 세로 스크롤바는 최대 1개(= 결과 테이블)만 동시 존재. `.message-details-body` / `.sql-block` (SQL 이 짧을 때) 에는 스크롤바 없음.
  7. 브라우저 자동화로 위 2/3/6 을 `eval` 로 확인 + 스크린샷 캡처.

### TASK-0032 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 작업 화면에서 사용자가 특정 동작(대화 생성/제목 변경/삭제/중단/즉시답변/요청 전송)을 시도했을 때 권한이 없으면 버튼이 **아예 숨겨지거나 조용히 무시되어** 사용자는 "어떤 권한"이 필요한지 알 수 없다. 결과적으로 관리자에게 "그냥 권한 다 줘 주세요" 같은 불필요·과도한 요청이 반복된다.
  - Profile > 계정 탭의 권한 pill 에 마우스를 올리면 툴팁에 **영문 권한 id 만 노출**([app.js:387](../src/static/app.js#L387) `item.title = code`)되어, `conversation.rename.own` 같은 코드를 일반 사용자가 해석할 수 없다.
  - 원인:
    1. [app.js:340-393](../src/static/app.js#L340-L393) `buildPermissionPills()` — `item.title = code` 한 줄. 서술 맵 부재.
    2. [app.js:1102-1105](../src/static/app.js#L1102-L1105) `renderComposer()` 에서 cancel/finalize/rename/delete 버튼을 `classList.toggle("hidden", !canX)` 로 처리 — 권한이 없으면 버튼 자체가 사라져 "이 동작이 있다"는 정보조차 사라짐.
    3. [app.js:1250](../src/static/app.js#L1250), [app.js:1258](../src/static/app.js#L1258), [app.js:1272](../src/static/app.js#L1272), [app.js:1304](../src/static/app.js#L1304), [app.js:1313](../src/static/app.js#L1313), [app.js:1323](../src/static/app.js#L1323) — 각 action 함수가 `if (!canX(...)) return;` 로 **조용히** 리턴. 사용자 피드백 없음.
    4. [app.js:548](../src/static/app.js#L548), [app.js:1088](../src/static/app.js#L1088) `renderAccessNotice()` / `renderComposer()` 안내 문구가 "대화 요청 실행 권한이 없습니다" 까지만 말하고 **어떤 permission code 를 요청해야 하는지 명시하지 않는다**.
- 목표:
  1. Profile > 계정 권한 pill hover 툴팁이 "이 권한이 실제로 어떤 동작을 허용하는지" 한국어 서술 문장 + 권한 코드를 모두 보여준다.
  2. 사용자가 차단된 동작을 시도했을 때(버튼 클릭 / 전송 / 단축키), **필요 권한 이름 + 관리자 요청 문구** 가 포함된 토스트가 즉시 노출된다.
  3. 버튼 가림 정책 변경: context 상 의미있는 상태(대화 선택됨 / 처리 중)에서는 **권한이 없어도 버튼을 유지**하되 `aria-disabled="true"` + 희미한 스타일로 "존재는 하지만 현재 계정으로는 실행 불가"임을 암시. 툴팁에도 필요 권한을 명시.
  4. 조회 전용 / 복구 가능 상태 안내 문구(`accessNoticeEl`, `composerHintEl`)에도 필요한 권한 코드를 명시.
  5. 기존에 자연스레 숨겨야 할 경우(대화 미선택 상태의 제목 변경 버튼 등)는 그대로 숨김 유지 — context 상 의미가 없기 때문.
- 접근:
  1. **권한 서술 맵 추가 ([app.js:97](../src/static/app.js#L97) 부근)**:
     ```js
     const PERMISSION_DESCRIPTIONS = {
       "console.access": "관리 콘솔에 접속할 수 있는 권한입니다.",
       "console.manage": "관리 콘솔에서 계정/역할/권한을 저장 커밋할 수 있는 권한입니다.",
       "account.read": "계정 목록과 상세 정보를 조회할 수 있는 권한입니다.",
       // ... 33개 모두 서술 ...
       "conversation.rename.own": "내가 소유한 대화의 제목을 변경할 수 있는 권한입니다.",
       "conversation.rename.any": "모든 사용자의 대화 제목을 변경할 수 있는 권한입니다.",
       // ...
     };
     function describePermission(code = "") {
       return PERMISSION_DESCRIPTIONS[code] || "권한 설명이 등록되어 있지 않습니다.";
     }
     ```
  2. **필요 권한 반환 헬퍼**:
     ```js
     // 현재 대화에서 action 을 실행하기 위해 필요한 "대안 권한 코드들"을 반환.
     // 예: conversation.rename → ["conversation.rename.any"] 또는 own 대화면 ["conversation.rename.any", "conversation.rename.own"].
     // 이 중 하나라도 granted 면 허용.
     function requiredPermissionsFor(action, conversation = currentConversation()) {
       const own = conversation ? isOwnConversation(conversation) : false;
       switch (action) {
         case "conversation.ask":     return { label: "대화 요청 실행", codes: ["conversation.ask"] };
         case "conversation.create":  return { label: "새 대화 생성", codes: ["conversation.create"] };
         case "conversation.rename":  return { label: "대화 제목 변경", codes: own ? ["conversation.rename.any", "conversation.rename.own"] : ["conversation.rename.any"] };
         case "conversation.delete":  return { label: "대화 삭제",     codes: own ? ["conversation.delete.any", "conversation.delete.own"] : ["conversation.delete.any"] };
         case "conversation.cancel":  return { label: "대화 중단",     codes: own ? ["conversation.cancel.any", "conversation.cancel.own"] : ["conversation.cancel.any"] };
         case "conversation.finalize":return { label: "즉시 답변",     codes: own ? ["conversation.finalize.any","conversation.finalize.own"] : ["conversation.finalize.any"] };
         default:                     return { label: action, codes: [] };
       }
     }
     function hasAnyPermission(codes = []) { return codes.some((c) => can(c)); }
     ```
  3. **차단 토스트 헬퍼**:
     ```js
     function showPermissionDeniedToast(action, conversation = currentConversation()) {
       const req = requiredPermissionsFor(action, conversation);
       if (!req.codes.length) { showToast(`'${req.label}' 을(를) 실행할 수 없습니다.`, true); return; }
       const missing = req.codes.filter((c) => !can(c));
       const primary = missing[0] || req.codes[0];
       const desc = describePermission(primary);
       const alt = req.codes.length > 1 ? `(또는 ${req.codes.slice(1).join(", ")})` : "";
       showToast(`'${req.label}' 권한이 필요합니다. 관리자에게 \`${primary}\`${alt ? " " + alt : ""} 권한 부여를 요청하세요.\n${desc}`, true);
     }
     ```
  4. **buildPermissionPills 툴팁 서술화**:
     ```js
     item.title = `${describePermission(code)}\n(${code})`;
     ```
     (short label 은 pill 의 `textContent`로 유지, 서술 문장은 hover 툴팁에만 노출 — 레이아웃 변경 없음)
  5. **버튼 visibility 정책 전환** ([app.js:1102-1105](../src/static/app.js#L1102-L1105)):
     - `cancelBtn` / `finalizeBtn`: "처리 중" 컨텍스트에서만 의미가 있으므로 `hidden` 토글은 `processing` 여부에만 매핑. 권한 부재는 `aria-disabled + .is-access-blocked` 로 표현.
     - `renameConversationBtn` / `deleteConversationBtn`: 대화가 선택되었을 때만 의미가 있으므로 `hidden` 토글은 `state.activeConversationId` 에만 매핑. 권한 부재는 `aria-disabled + .is-access-blocked`.
     - 헬퍼:
       ```js
       function markAccessBlocked(btn, action, conversation) {
         const req = requiredPermissionsFor(action, conversation);
         const blocked = !hasAnyPermission(req.codes);
         btn.classList.toggle("is-access-blocked", blocked);
         if (blocked) {
           btn.setAttribute("aria-disabled", "true");
           btn.dataset.blockedAction = action;
           const missing = req.codes.filter((c) => !can(c))[0] || req.codes[0];
           btn.title = `'${req.label}' 권한이 없습니다. 필요 권한: \`${missing}\``;
         } else {
           btn.removeAttribute("aria-disabled");
           delete btn.dataset.blockedAction;
           btn.title = "";
         }
       }
       ```
  6. **클릭 핸들러 보강** ([app.js:1534-1580](../src/static/app.js#L1534-L1580)):
     - 각 핸들러 본문 맨 앞에 `if (btn.getAttribute("aria-disabled") === "true") { showPermissionDeniedToast(action, currentConversation()); return; }` 추가.
     - `createConversation()`, `renameCurrentConversation()`, `deleteConversation()`, `cancelCurrentRun()`, `finalizeCurrentRun()`, `sendPrompt()` 내부의 조용한 `if (!canX) return` 도 `if (!hasAnyPermission(req.codes)) { showPermissionDeniedToast(action); return; }` 패턴으로 교체 — 단축키(Ctrl+Enter) 경로에서도 토스트가 나오도록.
  7. **안내 문구 보강** (`renderAccessNotice()`, `renderComposer()`):
     - `accessNoticeEl.textContent = "현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다. 관리자에게 권한을 요청하세요.";`
     - `composerHintEl.textContent = "현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다. 관리자에게 요청하세요.";`
     - Profile 의 "사용 가능한 권한이 없습니다" 문구는 그대로 (별도 추가 작업 불필요).
  8. **CSS** (`styles.css`):
     - `.tool-btn.is-access-blocked` + `.tool-btn[aria-disabled="true"]` 에 `opacity: .38; cursor: help; color: var(--text-muted);` 지정 — 기존 `:disabled` 스타일 재사용하되 click 은 계속 통과.
     - `button.is-access-blocked` hover 시 네이티브 `title` 툴팁이 뜨도록 `pointer-events: auto` 유지 (기본값이라 별도 선언 불필요).
- 범위 제한:
  - 백엔드 API 변경 없음. 권한 정의 테이블(WebPermissions) 그대로 사용.
  - admin 콘솔 쪽 UX 는 TASK-0031 이 마무리되었으므로 이번 범위에서 제외.
  - Profile 드로어의 "활성 권한" 섹션 외관은 유지 (그룹핑/카운트 배지 TASK-0027 그대로).
  - "부족한 권한 전체 목록" 같은 별도 UI 섹션은 추가하지 않는다 — 동작 시도 시점에 안내되므로 과설계.
- 검증 기준:
  1. Profile > 계정 탭에서 임의의 권한 pill 에 hover → 툴팁에 한국어 서술 문장 + `(code)` 가 표시된다(단순 `code` 가 아님).
  2. operator 계정(= `conversation.delete.own` 미보유) 로그인 → 본인 대화 선택 시 "삭제" 버튼이 보이고 `aria-disabled="true"` + 희미한 색. 클릭하면 토스트 `'대화 삭제' 권한이 필요합니다. 관리자에게 \`conversation.delete.any\` 권한 부여를 요청하세요.` 노출.
  3. 동일 계정에서 대화 미선택 상태에서는 "삭제" 버튼이 (권한과 무관하게) 숨김 — context 상 의미 없음.
  4. pending 계정(= `conversation.ask` 미보유) 로그인 → access notice / composer hint 에 `conversation.ask` 권한 코드 명시. 전송 시도 시 토스트 출현.
  5. admin 계정(모든 권한) 로그인 → 버튼 모두 정상 클릭 가능. `aria-disabled` 없음. 툴팁에도 빈 문자열.
  6. Ctrl+Enter 로 빈 권한 상태 전송 시도해도 동일 토스트 확인 (단축키 경로).
  7. 브라우저 자동화로 위 2번/4번을 재현해 스크린샷 or DOM 상태 증빙.

### TASK-0031 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 관리 콘솔에서 계정/권한 목록이나 디테일 편집 항목이 많아지면 화면 아래 있어야 할 버튼(예: 페이지 버튼, 저장/취소/삭제 액션)이 외부 스크롤에 의해 뷰포트 밖으로 밀려 **이용자가 존재 자체를 인지하지 못한다**.
  - 원인:
    1. [styles.css:1378-1383](../src/static/styles.css#L1378-L1383) `.admin-workspace { overflow-y: auto }` — workspace 전체가 단일 스크롤 컨테이너. 디테일 pane 이 커지면 그 높이가 workspace 스크롤을 지배하여 리스트 하단 페이지네이션이 **외부 스크롤 아래로 숨음**.
    2. [styles.css:1509-1516](../src/static/styles.css#L1509-L1516) `.admin-list { max-height: calc(100vh - 320px) }` 는 고정 pixel 계산인데다 외부 workspace 스크롤에 의해 의도치 않게 무력화됨.
    3. [admin.html:113-114](../src/static/admin.html#L113-L114) 페이지네이션(`#accountPagination`)이 `.admin-list` 바깥(동일 `.admin-list-col` 자식)으로 위치해, 리스트 내부 스크롤이 아니라 바깥 workspace 스크롤에 종속됨.
    4. [admin.js:854-855](../src/static/admin.js#L854-L855) `.admin-detail-actions`(저장/취소/삭제 버튼 영역)도 detail pane 내용 맨 아래에 append 될 뿐 위치 고정 처리가 없어 detail 이 길어지면 외부 스크롤로만 접근 가능.
- 목표:
  - 관리 콘솔 2열 레이아웃(리스트 / 디테일) 각 컬럼이 **자체 내부 스크롤**을 가지며, 컬럼 하단의 페이지네이션·일괄 액션·detail 저장 버튼은 **항상 뷰포트 내에 노출**된다.
  - 외부(페이지 전체) 스크롤은 발생하지 않는다. 모든 스크롤은 각 pane / 컬럼 내부로 한정.
  - 하단 commit bar, topbar, sidebar 는 기존대로 고정(이미 grid 로 고정되어 있음 — 그대로 유지).
- 접근:
  1. **`.admin-workspace` 를 스크롤 컨테이너에서 flex 컨테이너로 전환**:
     ```css
     .admin-workspace { overflow: hidden; display: flex; flex-direction: column; padding: 20px 24px 24px; min-height: 0; }
     ```
     (`min-height: 0` 은 부모 grid row 에서 flex children 이 overflow 하지 않게 하는 안전장치)
  2. **`.admin-pane.is-active` 가 workspace 를 수직으로 채우도록**:
     ```css
     .admin-pane { display: none; flex-direction: column; gap: 16px; min-height: 0; flex: 1 1 auto; }
     .admin-pane.is-active { display: flex; }
     ```
  3. **`.admin-pane-head` 는 고정**(shrink 없음):
     ```css
     .admin-pane-head { flex-shrink: 0; }
     ```
  4. **리스트-디테일 컨테이너가 남은 공간을 채우고, 자식 컬럼이 동일 높이를 가지도록**:
     ```css
     .admin-list-detail { flex: 1 1 auto; min-height: 0; align-items: stretch; }
     ```
     (기존 `align-items: start` 는 제거 — start 로는 두 컬럼이 콘텐츠 길이에 따라 다르게 자라므로)
  5. **리스트 컬럼 = 고정 헤더(툴바/리스트-헤드) + 내부 스크롤 본문 + 고정 푸터(페이지네이션/일괄 액션)**:
     ```css
     .admin-list-col { min-height: 0; max-height: 100%; }
     .admin-list-toolbar, .admin-list-head { flex-shrink: 0; }
     .admin-list { flex: 1 1 auto; min-height: 0; max-height: none; overflow-y: auto; }
     .admin-list-pagination, .admin-bulk-actions { flex-shrink: 0; border-top: 1px solid var(--border-subtle); margin-top: 4px; padding-top: 8px; }
     ```
     기존 하드코딩 `max-height: calc(100vh - 320px)` 제거.
  6. **디테일 컬럼 = 내부 스크롤 본문 + 하단 sticky 액션 바**:
     - CSS 만으로 마지막 자식 `.admin-detail-actions` 를 sticky 하게 만들면, 내부 구조 변경 없이 저장/취소/삭제 버튼이 detail pane 하단에 항상 노출된다:
     ```css
     .admin-detail-col { min-height: 0; max-height: 100%; overflow-y: auto; padding-bottom: 0; }
     .admin-detail-actions {
       position: sticky;
       bottom: 0;
       background: var(--surface);
       margin: 0 -22px -18px;   /* detail-col padding(18 22)을 상쇄해 전폭 바 */
       padding: 10px 22px;
       border-top: 1px solid var(--border);
       z-index: 1;
     }
     ```
  7. **대시보드 pane** 은 카드 + pending 미리보기만 있으므로 내부 스크롤이 필요한 경우에만 대비:
     ```css
     .admin-pane[data-admin-pane="dashboard"] { overflow-y: auto; }
     ```
  8. **뷰포트가 좁을 때 보호**: 기존 반응형 쿼리가 있다면 그대로 유지. 모바일(viewport < 960px) 대응은 이번 범위 아님(이용자는 데스크탑에서 사용).
- 범위 제한:
  - JS(admin.js) 변경 불필요. CSS 만으로 해결.
  - admin.html DOM 구조 변경 불필요(페이지네이션·액션 바가 각각 올바른 컬럼의 마지막 자식에 이미 위치).
  - 채팅 쪽, backend 변경 없음.
- 검증 기준:
  1. 브라우저로 `/admin` 열어 계정 탭 진입 → 페이지를 스크롤하지 않고도 페이지네이션 버튼이 리스트 하단에 보인다.
  2. 계정을 선택해 디테일에 많은 권한 그룹을 펼친 상태에서도 리스트 컬럼의 페이지네이션은 그대로 보이며, 디테일 하단 저장/취소 버튼도 sticky 로 노출된다.
  3. 리스트 컬럼에서 스크롤해도 페이지네이션은 리스트 아래에 고정 위치. 디테일 컬럼에서 스크롤해도 액션 바는 하단에 고정.
  4. `document.documentElement.scrollHeight === document.documentElement.clientHeight` 인지 확인(외부 스크롤 없음).
  5. 역할 탭에서도 동일 동작(역할 일괄 액션 바/detail 저장 버튼).
  6. 브라우저 자동화로 위 동작을 재현·수치 검증.

### TASK-0030 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - assistant 답변의 "실행 단계 및 쿼리 결과 보기" `<details>` 블록을 펼칠 경우, 결과셋 구성(쿼리 수/행 수/컬럼 수/SQL 길이)에 따라 말풍선의 높이와 폭이 비결정적으로 커져 **채팅 스크롤 위치가 움직이고**, 사용자가 방금 보던 문장을 놓친다.
  - 원인 1: [styles.css:721-725](../src/static/styles.css#L721-L725) `.message { max-width: 82% }`가 user/assistant 양쪽에 동일 적용되어, assistant 말풍선이 기본적으로 좁고, 내용이 커지면 높이로 비대해진다.
  - 원인 2: [styles.css:838-843](../src/static/styles.css#L838-L843) `.message-details-body`에 max-height/overflow 제약이 없어서 내부 SQL · 테이블 · 긴 `<pre>` 가 수직으로 끝없이 누적된다.
  - 원인 3: [styles.css:894-898](../src/static/styles.css#L894-L898) `.result-table-wrap` 기본형은 `overflow-x: auto`만 있고 수직 cap이 없다 ("is-full-data" 변형만 360px 로 제한). 결과 preview가 많이 잘리지 않은 상태면 높이가 무제한.
  - 원인 4: [styles.css:877-891](../src/static/styles.css#L877-L891) `.sql-block`은 `pre-wrap`이지만 초장문 SQL 은 여전히 화면 높이를 밀어낸다.
  - 원인 5: [app.js:980-1023](../src/static/app.js#L980-L1023) `renderMessageDetails()`는 `<details>` 펼침/접힘 시 스크롤 앵커 로직이 없어, `<summary>` 위치가 뷰포트 내에서 통째로 이동한다.
- 목표:
  1. assistant 말풍선은 기본적으로 **넓은 폭으로 고정**(우측 사용자 질문 영역과 구분할 수 있는 소량 여백만 유지). 펼친 내용의 크기에 따라 말풍선 폭이 흔들리지 않는다.
  2. 말풍선 내부가 너무 길어지면 **말풍선 내부에서 수직/수평 스크롤**로 처리한다. 말풍선 바깥 레이아웃(채팅 스크롤, 사이드바, 메시지 간격)은 변형되지 않는다.
  3. `<details>` 펼침/접힘 시 **`<summary>`가 뷰포트 내 동일 위치에 유지**되도록 스크롤을 보정한다(scroll anchor).
  4. user 말풍선은 우측 정렬 좁은 형태를 유지해 assistant와 시각적으로 확실히 구분된다.
- 검토한 대안:
  - Option A (사용자 제안 원형): 말풍선 전폭 + 내부 수평 스크롤. 단순하고 직접적.
  - Option B (Claude artifact 사이드 패널): 결과셋을 별도 right-panel에 띄워 채팅 흐름과 분리. 현재 이슈 해결에는 과설계이며 Navigator/CSV 링크/progress strip 과의 통합 비용이 큼.
  - Option C (채택): **말풍선 고정 폭 + `<details>` 본문 max-height 캡 + 중첩 스크롤 + summary 클릭 스크롤 앵커**. Option A의 직접성에 scroll anchor를 더해 "펼칠 때 위치가 튀는" 부작용까지 해소. 기존 Navigator/CSV 흐름 그대로 재사용.
- 접근:
  1. **말풍선 폭 분기 (styles.css)**:
     - 기존 `.message { max-width: 82% }` 를 제거하고 역할별로 분리:
       ```css
       .message.is-user      { max-width: 72%; }
       .message.is-assistant { max-width: calc(100% - 48px); }
       ```
       (assistant 는 우측으로만 약 48px 여백, 나머지는 전부 사용 — 사용자 질문 영역과 구분은 이 여백으로 확보)
     - `.message-bubble` 에 `width: 100%; min-width: 0;` 추가해 말풍선 자체가 자식 내용에 의해 팽창하지 않도록 고정한다.
  2. **펼침 본문 내부 스크롤 (styles.css)**:
     - `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; }` — 펼침 시 본문 전체가 내부 세로 스크롤. `overscroll-behavior: contain`으로 내부 끝에 도달해도 상위 채팅 스크롤이 이어서 움직이지 않게 격리.
     - `.message-details[open] .message-details-body { padding-right: 4px; }` 로 스크롤바가 생길 때 콘텐츠가 숨지 않게 여유.
  3. **결과 테이블 기본 스크롤 (styles.css)**:
     - `.result-table-wrap { max-height: 320px; overflow: auto; }` 기본 캡 (기존에는 수평 스크롤만). "전체 데이터 보기"로 CSV 를 로드한 경우(`is-full-data`)는 기존 360px 를 유지.
  4. **초장문 SQL 캡 (styles.css)**:
     - `.sql-block { max-height: 240px; overflow: auto; }` — 수백 줄 SQL이 말풍선을 뚫고 들어오는 걸 방지. 기존 pre-wrap/word-break 은 유지.
  5. **Navigator 패널 min-width (styles.css)**:
     - `.sql-navigator`, `.sql-nav-panel`, `.sql-result-group` 에 `min-width: 0` 재확인(이미 있는 곳도 있으나 누락된 곳 보강)해 flex/grid shrink 허용.
  6. **스크롤 앵커 (app.js)**:
     - [app.js:980-1023](../src/static/app.js#L980-L1023) `renderMessageDetails()` 에서 `<summary>` 에 `click` 리스너를 추가:
       - 클릭 직전에 `summary.getBoundingClientRect().top - messageLogEl.getBoundingClientRect().top` 을 기록(=`prevOffset`).
       - `requestAnimationFrame` 2회 후(`<details>` open 상태 토글 + 레이아웃 반영 이후) 같은 값을 다시 계산해 `delta = newOffset - prevOffset` 만큼 `messageLogEl.scrollTop` 을 더한다.
     - 결과: `<summary>` 라인은 사용자 뷰포트에서 동일한 y좌표에 고정되고, 펼침으로 생긴 공간은 `<summary>` 아래로만 밀려난다.
     - 접힘 시에도 같은 로직이 대칭으로 작동 (summary 위치 유지).
- 범위 제한:
  - 백엔드/agent-core 변경 없음.
  - 기존 SQL Navigator, CSV 다운로드, "전체 데이터 보기", Progress Strip `<details>` 는 그대로 유지. Progress Strip 은 이번 이슈의 범주가 아님 (이미 TASK-0022 에서 max-height 처리됨).
  - admin 콘솔 쪽 CSS 변경 없음.
- 검증 기준:
  1. assistant 말풍선이 기본적으로 채팅 pane 의 오른쪽 약간(≈48px)만 남기고 좌측부터 넓게 차지한다. user 말풍선은 우측 정렬 좁은 형태로 구분된다.
  2. `<details>` 접힌 상태의 말풍선 크기가, `<details>` 를 펼쳐도 **폭이 변하지 않는다**. 내부에 긴 SQL · 큰 결과 테이블 · 여러 쿼리 Navigator 가 있어도 말풍선의 폭/높이 outline 은 결과셋 구성에 무관하게 일정(max-height 내부 스크롤로 흡수).
  3. `<summary>` 클릭으로 펼칠 때 해당 `<summary>` 라인이 뷰포트 내 동일 좌표에 유지된다. 접을 때도 동일. 채팅 로그 다른 메시지들의 뷰포트 위치가 튀지 않는다.
  4. 결과 테이블 내부에서 세로/가로 스크롤이 작동하고, 채팅 로그 스크롤과 독립적(`overscroll-behavior: contain`)이다.
  5. 단일 SQL step / 다중 SQL Navigator / CSV 전체 데이터 로드 / `meta.sql` 폴백 네 경로 모두에서 위 동작이 일관된다.
  6. 브라우저 자동화(또는 수동) 스크린샷으로 "펼침 전/후 말풍선 bounding box 동일" 과 "summary 좌표 불변"을 확인.

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
- TASK-0031 (2026-04-21): 관리 콘솔 내부 스크롤 정리. `.admin-workspace` 의 외부 스크롤(`overflow-y: auto`) 제거 → `overflow: hidden` + flex column 으로 전환하고, `.admin-pane.is-active` / `.admin-list-detail` 가 남은 공간을 `flex: 1 1 auto + min-height: 0` 으로 채우도록 변경. `.admin-list-col` / `.admin-detail-col` 각각 자체 내부 스크롤 소유 — list 컬럼은 toolbar/list-head(shrink 고정) + `.admin-list`(`flex: 1; overflow-y: auto`, 기존 `max-height: calc(100vh-320px)` 제거) + 페이지네이션/일괄 액션(`flex-shrink: 0; border-top`) 구조. detail 컬럼은 `overflow-y: auto` + `.admin-detail-actions { position: sticky; bottom: -18px; margin: 4px -22px -18px; padding: 12px 22px; background: var(--surface); border-top }` 로 저장/취소/삭제 버튼을 detail 높이와 무관하게 상시 하단 노출. 대시보드 pane 은 `overflow-y: auto` 단일 스크롤로 별도 처리. 검증: detailColScroll=1866, listScroll=807 각각 내부 스크롤 활성, docScrollDelta=0(외부 스크롤 0), paginationVisible/actionsVisible=true, 양 컬럼 끝까지 스크롤해도 두 하단 요소 모두 뷰포트 내 유지. JS/HTML 변경 없이 CSS 만으로 해결.
- TASK-0030 (2026-04-21): assistant 말풍선 고정 폭 + `<details>` 펼침 시 내부 스크롤/스크롤 앵커. `.message`의 role별 max-width 분기(user 72% / assistant `max-width:none` + `margin-right:48px` + `align-self:stretch`)로 assistant 는 채팅 pane 전폭에 가깝게, user 는 좁은 우측 정렬로 분리. `.message-details-body`에 `max-height:min(60vh,520px); overflow:auto; overscroll-behavior:contain` 캡으로 펼친 본문을 말풍선 내부에서 수직 스크롤 처리. `.result-table-wrap` 기본 `max-height:320px`, `.sql-block` `max-height:240px` 로 결과 테이블/초장문 SQL 도 내부 스크롤로 격리. `app.js` `renderMessageDetails()`의 `<summary>` 클릭 핸들러에 `messageLogEl` 기준 `summary.getBoundingClientRect().top` 측정 → 2-frame `requestAnimationFrame` 후 delta 만큼 `messageLogEl.scrollTop` 보정하는 scroll anchor 추가. 브라우저 검증: summaryDelta=0/scrollDelta=0, Navigator 이동 시 bubble width 705→705 불변, bodyMaxH=432px(60vh), details body overflow-y=auto 확인.
- TASK-0029 (2026-04-21): 관리 콘솔 재구조화. `admin.html` 을 `topbar + sidebar(tabs) + workspace + commit-bar` 4영역 grid 로 재작성(탭: 대시보드/계정/역할). `admin.js` 전면 재작성 — `adminState.pending = { accounts, roles, newRoles }` Map 기반 pending changes 모델 + 서버 값과 일치하면 auto-drop 로직(`setAccountPending`/`setRolePending`). 계정/역할 편집은 form submit 없이 input/select change 이벤트에서 pending 에 적재만 하고, 하단 commit bar 의 "모두 적용" 클릭 시 전체 pending entry 를 순차 PATCH/DELETE/POST 후 1회만 `loadAdminData()`. 리스트-디테일 레이아웃 + 탭별 scoped search + 리스트 row 체크박스 기반 일괄 작업(활성/비활성/삭제 pending 반영). 신규 역할은 tempId(`new:N`)로 pending.newRoles 에 넣고 POST 로 일괄 커밋. `styles.css` 에 `.admin-shell` grid/`.admin-sidebar`/`.admin-tab`/`.admin-list-detail`/`.admin-list-row`/`.admin-detail-*`/`.admin-commit-bar`(.has-pending 노란 강조) 스타일 추가. 사용자 테스트에서 확인된 "여러 계정 동시 수정 시 특정 계정 저장하면 타 계정 변경 소실" 버그는 pending 모델 + 단일 commit 경로로 근본 해소.
- TASK-0033 (2026-04-21): 결과셋 말풍선의 이중 스크롤 제거 + RowCount + Excel-like freeze. `styles.css` 의 `.message-details-body` 에서 `max-height: min(60vh,520px); overflow: auto; overscroll-behavior: contain; padding-right: 4px` 일괄 제거 → 말풍선 body 는 자연스럽게 자라고 세로 스크롤은 `.messages` 하나로 통일. `.result-table-wrap` 은 `max-height: 320px → min(60vh, 460px)` + `overscroll-behavior: contain` 제거(= auto 로 복원 → 경계에서 `.messages` 로 휠 전파). `.sql-block` 도 `max-height: 240px → min(40vh, 320px)` + overscroll 제거. `.result-table` 을 `border-collapse: separate; border-spacing: 0` 으로 전환하고 border 는 `box-shadow: inset` 으로 대체(sticky 셀에서 border 누락 방지). `.result-table thead th { position: sticky; top: 0; z-index: 2 }` 로 헤더 freeze, `.result-table th.col-rownum, td.col-rownum { position: sticky; left: 0; z-index: 1 }` 로 첫 열(#) freeze, 코너 `thead th.col-rownum { z-index: 3 }` 로 교차점 최상위. `app.js` 에 `appendRowNumCell(tr, tag, value)` 헬퍼 추가, `buildResultTable()` thead/tbody 렌더 시 `<th class="col-rownum">#</th>` + `<td class="col-rownum">{i+1}</td>` 항상 prepend. `loadFullCsvIntoTable()` 도 동일 패턴으로 재구성 → "전체 데이터 보기" 이후에도 #/freeze 유지. 검증: 기존 대화의 33행 결과 테이블에서 `theadThPosition='sticky'`, `col-rownum td position='sticky'`, corner `zIndex=3`, wrap `max-height=432px`, `overscroll-behavior='auto'`, `.message-details-body { max-height: none; overflow: visible }`, `hasInnerDetailScroll=false`, 수직 스크롤 200px 시 각 th 개별 top 변동 없음(`firstTh_delta=0`), 가로 스크롤 60px 시 `col-rownum` 좌측 고정(`rnStayed=true`, `dataMoved=true`). 스크린샷 `artifacts/shared/out/browser/task0033_01_result_tables.png` · `task0033_02_sticky_header_mid_scroll.png`.
- TASK-0032 (2026-04-21): 권한 안내 UX 개편. `app.js` 에 `PERMISSION_DESCRIPTIONS`(33개 권한 서술 문장 맵), `describePermission()`, `requiredPermissionsFor(action, conversation)`(any/own 이원화된 권한 자동 확장), `hasAnyPermission()`, `showPermissionDeniedToast()`(필요 권한 코드 + 서술 + 관리자 요청 문구), `markAccessBlocked(btn, action, conversation)`(aria-disabled + is-access-blocked + 서술 title) 추가. `buildPermissionPills()` 의 `item.title = code` 를 `서술 문장\n(code)` 로 교체. `renderComposer()` 에서 `cancel/finalize/rename/delete` 버튼을 context 신호(processing / activeConversationId) 로만 hidden 토글하고, 권한 부재는 `markAccessBlocked()` 로 별도 표현. `sendBtn`/`newConversationBtn` 도 native disabled 대신 aria-disabled 사용해 클릭이 통과하도록 전환. 각 action 함수 (`createConversation`, `renameCurrentConversation`, `deleteConversation`, `cancelCurrentRun`, `finalizeCurrentRun`, `sendPrompt`) 의 silent `return` 을 `showPermissionDeniedToast()` 호출로 교체. `renderAccessNotice()` / `renderComposer()` 안내 문구에 `conversation.ask` 코드 명시. `styles.css` 에 `.is-access-blocked { opacity: .42; cursor: help; color: var(--text-muted) }` 추가. 검증 (admin / pending 계정): pill tooltip=한국어 서술 문장+`(code)`, pending 계정 composerHint=`현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다...`, sendBtn/newConvBtn/renameBtn/deleteBtn 모두 `is-access-blocked` + aria-disabled + 서술 title, 클릭 시 `'대화 삭제' 권한이 필요합니다. 관리자에게 \`conversation.delete.any\` 권한 부여를 요청하세요. — 타 사용자가 소유한 대화까지 삭제할 수 있는 권한입니다.` 형식 토스트 노출. 스크린샷 `artifacts/shared/out/browser/task0032_{01,02,03}_*.png` 증빙.
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
- [x] assistant 말풍선이 기본적으로 채팅 pane 의 우측 약간(48px)만 남기고 넓게 고정되며, `<details>` 펼침/접힘이나 결과셋 구성 변화에 말풍선 폭이 흔들리지 않는다
- [x] `<details>` 펼침 시 내부 SQL/테이블/Navigator 가 말풍선 내부 수직 스크롤로 격리되어 채팅 로그 스크롤 위치와 전체 레이아웃이 변형되지 않는다
- [x] `<summary>` 클릭 시 해당 라인이 뷰포트 내 동일 y좌표를 유지(scroll anchor)
- [x] 관리 콘솔이 외부 페이지 스크롤 없이 viewport 에 고정되며, 리스트 컬럼과 디테일 컬럼이 각각 내부 스크롤을 가진다
- [x] 리스트 하단 페이지네이션/일괄 액션 바와 디테일 하단 저장/삭제 액션 바가 컬럼 스크롤과 무관하게 항상 뷰포트 내에 노출된다
- [x] 리스트 row 체크박스 + 일괄 작업(활성/비활성/삭제 pending)이 동작한다
- [x] 계정 탭/역할 탭 각각이 독립된 scoped search 를 가진다
- [x] Profile > 계정 탭 권한 pill 에 마우스를 올리면 한국어 서술 문장과 권한 코드가 툴팁으로 표시된다
- [x] 권한이 부족한 계정에서 차단된 동작을 시도(클릭/단축키)하면 필요 권한 코드 + 서술 문장 + 관리자 요청 문구가 토스트로 노출된다
- [x] cancel/finalize/rename/delete 버튼은 context 상 의미있을 때는 항상 보이고, 권한이 없을 때는 `is-access-blocked` 로 표시되며 클릭은 토스트로 안내된다
- [x] assistant 말풍선의 `실행 단계 및 쿼리 결과 보기` 내부에 세로 스크롤바가 중첩되지 않는다 (본문은 콘텐츠 크기만큼 확장되고 세로 스크롤은 `.messages` 하나)
- [x] 쿼리 결과 테이블에 첫 컬럼 `#` (RowCount) 이 자동 삽입되어 행 번호가 1부터 표시된다
- [x] 결과 테이블 내부 세로 스크롤 시 헤더 행이 상단 고정, 가로 스크롤 시 `#` 컬럼이 좌측 고정된다
- [x] 결과 테이블 내부 스크롤이 경계에 닿으면 채팅 로그(`.messages`) 로 휠이 전파된다 (`overscroll-behavior` 제거)
- [x] "전체 데이터 보기" 로 CSV 로드 후에도 RowCount 와 sticky freeze 가 유지된다
- [ ] TASK-0034: 복잡 QA 성능 테스트가 local LLM 5 (직렬) + 상용 API gpt-5.4-mini 5 (병렬) 총 10 대화로 실행되어 turn-by-turn 로그가 JSON 으로 저장된다
- [ ] TASK-0034: 5 개 복잡 질문에 대해 사람 truth 쿼리와 assistant 최종 답변이 비교 가능한 diff 형태로 `TASK-0034-REPORT.md` 에 기록된다
- [ ] TASK-0034: 관찰된 개선 포인트가 `docs/LEARNINGS.md` 에 신규 LRN 항목으로 추가된다
- [x] TASK-0040: `_extract_sql_schema_refs` 가 `WHERE bb.BattleType = 'X'` 등 alias.column 토큰에서 schema 를 추출하지 않는다 (FROM/JOIN 구간의 테이블 리스트로 범위 제한)
- [x] TASK-0040: `FROM dblog.t bb JOIN dblog.u be ON be.a = bb.a` 형식 SQL 이 Product whitelist=`{dbauth,dbgame,dblog}` 상태에서 정상 통과한다
- [x] TASK-0040: 비허용 스키마(`FROM dbstat.foo`) 는 여전히 차단된다 (15 테스트 케이스 통과)
- [x] TASK-0041: `GET /api/ask_status?conversation_id=...` 이 `{is_processing, status, run_id, step_count, duration_ms, has_answer, answer_preview}` 스냅샷을 반환한다
- [x] TASK-0041: `GET /api/ask_result?conversation_id=...&run_id=...&wait=N(<=60)` 이 terminal 도달 시 `{status, run_id, assistant.{message_id,content,meta,steps_count}}` 를 반환하고, 시간 초과 시 `{timeout:true}` 를 반환한다
- [x] TASK-0041: 브라우저에서 `/api/ask` 요청이 끊겨도 `is_processing=true` 인 경우 `[계속 기다리기/즉시 답변/요청 취소]` 다이얼로그가 노출되고 선택한 동작 이후 최종 메시지가 UI 에 주입된다
- [x] TASK-0041: `task0034_runner.py` 의 `httpx.ReadTimeout` 분기가 `/api/ask_status` + `/api/ask_result` long-poll 로 attach 해 최종 응답을 해당 턴에 기록한다
- [x] TASK-0037: `/api/progress` 폴링이 `setInterval` 고정 주기가 아니라 순번 기반 `setTimeout` 체인으로 동작하고 in-flight 요청이 1 을 넘지 않는다
- [x] TASK-0037: 대화 전환/로그아웃/새 대화 생성 시 AbortController 로 진행 중인 `/api/progress` 요청이 즉시 취소된다
- [x] TASK-0037: 탭 전환(`document.hidden`) 시 폴링 주기가 최소 10초로 감속되고, 연속 오류 3회 이상이면 재스케줄링되지 않는다
- [x] TASK-0037: 서버 `/api/progress` 가 `client_run_id` 불일치 시 `after_step` 을 0 으로 리셋해 새 run 의 모든 step 을 되돌려준다
- [x] TASK-0037: 폴링 패턴 학습 내용이 `docs/LEARNINGS.md` 의 LRN 항목(LRN-20260422-0011) 로 기록된다
- [x] TASK-0044: `SEED_ROLE_DEFINITIONS` 에 RoleKey=`sales` / Name=`사업팀` entry 가 있고, 부트스트랩 후 `WebRoles` 에 해당 row + `conversation.create` / `conversation.ask` 등 9 개 권한이 `WebRolePermissions` 로 연결된다 (admin 콘솔 `/api/admin/roles` 조회로 확인)
- [x] TASK-0044: `SEED_ROLE_SYSTEM_PROMPTS` + `_ensure_seed_role_system_prompts(conn)` 이 sales role 에 대해 `WebSystemPrompts(Scope='role', RoleId=<sales>, ProductId=NULL)` prompt 1 row 를 1 회만 upsert 하고, 이미 존재하면 덮어쓰지 않는다 (관리 콘솔 수정 존중)
- [x] TASK-0044: sales role prompt 본문이 "단순 조회 → 문장 응답 / 집계 → 결과셋 표 응답 / ad-hoc 심층 분석 요청 → DBA 팀 이관 안내 후 대화 종료 / DB 쓰기 쿼리(INSERT/UPDATE/DELETE/DDL) 거부" 4 지침을 포함한다
- [x] TASK-0044: `modules/config.py` 가 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` / `REPLICA_DB_ENABLED` 5 개 심볼을 export 하고, `.env.example` 에 4 개 placeholder 가 등록되어 있다 (실제 접속 정보는 commit 금지)
- [x] TASK-0044: `modules/db.py::connect()` 이 `REPLICA_DB_HOST` 가 설정되어 있고 요청 `database` 가 `MEMORY_DB` 가 아닐 때 복제 인스턴스의 host/port/user/password 로 라우팅하고, 그 외에는 primary (DB_HOST/...) 로 라우팅한다
- [x] TASK-0044: `REPLICA_DB_HOST` 가 비어있는 기존 배포에서 동작이 변하지 않는다 (`connect(database=None)` / `connect(database=MEMORY_DB)` / `connect(database="dbgame")` 모두 primary 접속)
- [ ] TASK-0044: 사업팀 pilot 계정(placeholder `<< pilot_username_1..N >>`) 이 admin 콘솔에서 발급된다 — 코드 auto-create 없음, 발급 절차는 본 TASK 기술부 마지막 runbook 문단 참조
- [ ] TASK-0044: 사업팀 pilot 계정으로 로그인해 단순 조회 prompt(예: "대표 아이템 X 가 몬스터 Y 에 연결돼 있나요?") 에 문장형 응답을 받는다
- [ ] TASK-0044: 사업팀 pilot 계정으로 집계 prompt(예: "최근 7 일 레벨별 유저 수") 에 결과셋 표 응답을 받는다
- [ ] TASK-0044: 사업팀 pilot 계정으로 ad-hoc 분석 prompt(예: "유저가 왜 이탈하는지 분석해줘") 에 "DBA 팀으로 요청 이관이 필요합니다" 안내가 응답되고 대화가 그 턴에서 종료된다

### TASK-0044 pilot onboarding runbook (2026-04-23)
사업팀 pilot 발급·서빙을 위한 관리자 운용 절차. 본 TASK 의 코드 변경은 infra 만 제공하며, 실제 account/Product 매핑은 admin 이 수동 수행한다.

1. **사업팀 pilot 계정 발급** (`.env.example` 의 `WEB_PILOT_SALES_USERNAMES` placeholder 참조)
   1. admin 계정으로 로그인 → 관리 콘솔 `계정 (Accounts)` 탭 → `신규 계정` 으로 3~5 명 발급.
   2. 각 계정의 Role 드롭다운에서 `사업팀 (sales)` 을 선택하고 commit bar 의 `모두 적용` 을 누른다.
   3. 초기 비밀번호는 pilot 에게 안전한 채널(사내 1:1 메신저 등) 로 공유하고 본인이 첫 로그인 시 교체하도록 안내한다.

2. **사업팀 전용 Product whitelist 구성 (권장안 2 가지 중 조직 정책에 맞춰 선택)**
   - **옵션 A — KR Product 에서 `dbauth` 를 제외**: 관리 콘솔 `상품 (Products)` 탭 → KR 선택 → 접근 DB chip 에서 `dbauth` 제거 → 저장. 주의: DBA 운영 계정도 KR 을 쓰면 영향. DBA 가 `dbauth` 직접 조회 필요 시 별도 Product 로 분리해야 한다.
   - **옵션 B — 사업팀 전용 Product `KR-Sales` 신규 생성** (권장): 관리 콘솔 `상품 (Products)` 탭 → `신규 상품` 으로 ProductKey=`KR-Sales` / Name=`Korea Sales` 를 생성 → 접근 DB chip 을 `dbgame,dblog` 로 지정. 사업팀 pilot 은 새 대화 시 이 Product 를 명시적으로 선택하거나, `/api/new_conversation` body 의 `product_id` 로 기본값을 지정한다.

3. **복제 DB 접속 정보 등록**
   1. 복제 인스턴스가 이미 가동 중이면 `.env` 에 `REPLICA_DB_HOST=<host>` / `REPLICA_DB_PORT=<port>` / `REPLICA_DB_USER=<user>` / `REPLICA_DB_PASSWORD=<password>` 를 기입 (quote 는 mysql.connector 인자이므로 bash-safe 처리 필요).
   2. `docker compose up -d --force-recreate agent web insight-worker` 로 재기동하면 data-plane 쿼리가 복제로 라우팅된다. memory DB 는 계속 primary.
   3. 수동 sanity check: `docker compose exec agent python -c "from modules.db import connect; c=connect(database='dbgame'); cur=c.cursor(); cur.execute('SELECT 1'); print(cur.fetchall())"` → `[(1,)]` 출력 + 필요시 `mysql -h $REPLICA_DB_HOST -P $REPLICA_DB_PORT -u $REPLICA_DB_USER -p -e 'SELECT 1'` 으로 직접 접속.
   4. 복제 인스턴스가 아직 없으면 3.1~3.3 은 후속 작업이며, `.env` 의 REPLICA_DB_* 를 비워 두면 기존 primary 경로가 그대로 동작한다 (사업팀 pilot 테스트 자체는 복제 없이 가능).

4. **사업팀 prompt 튜닝 (선택)**: 관리 콘솔 `역할 (Roles)` 탭 → `사업팀` 선택 → Role scope prompt 편집기 → Product 드롭다운(`(전 Product 공통)` 또는 특정 Product) 선택 후 초안을 수정. 저장 시 `WebSystemPrompts` 의 해당 scope row 가 업데이트되고 다음 `/api/ask` 부터 새 가이던스가 즉시 적용된다.
