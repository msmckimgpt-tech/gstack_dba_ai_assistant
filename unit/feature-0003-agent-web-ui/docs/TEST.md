---
doc_type: TEST
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Policy
- Web UI의 화면/상호작용 검증은 실제 브라우저 기반으로 수행한다.
- 계정/권한/소유권과 같은 서버 계약 검증은 curl 또는 SQL 확인을 병행할 수 있다.
- 브라우저 자동화 API 엔드포인트: `http://localhost:18081`
- 스크린샷 증빙은 `/shared/out/browser`에 저장한다.

## 2. Test Scope
- 계정 기반 로그인/회원가입이 실제로 동작하는지 확인
- 기본 signup role 전환과 role CRUD가 동작하는지 확인
- 계정 role assignment, tri-state override, soft delete가 동작하는지 확인
- 대화 목록/히스토리/제목 변경/삭제/중단/즉시답변이 own/any 권한 기준으로 분기되는지 확인
- 메인 화면이 외부 스크롤 없는 App-Shell 레이아웃으로 렌더링되는지 확인
- 프로필 드로어가 계정 / 보안 / API Vault 탭 구조로 동작하는지 확인
- Admin 콘솔의 검색 / 필터 / role/override 편집이 동작하는지 확인
- role명 휴리스틱 없이 permission + ownership만으로 판정하는지 확인
- 외부 Local LLM gateway 연결 시 API 키 없이 `model=auto` 요청이 가능한지 확인
- 외부 Local LLM provider 미기동 시 `model=auto` 요청이 503으로 제한되는지 확인

### 2.1 Audit subsystem (TASK-0073, Critical §12.3)

본 cycle 의 audit subsystem 검증 case (`tests/test_audit_*.py` 3 file = 20 시나리오 — 실 실행은 컨테이너 가동 후):

- **dispatcher unit** (`test_audit_dispatcher.py` D1~D7): `record_audit_event(conn, ...)` 호출 후 WebAuditEvents row visible / actor / target / change_json 필드 매핑 정합 / ChangeJson allowlist (`_AUDIT_BUILDER_*_FIELDS`) / masked_fields list redact 정합 / unknown action ValueError raise / admin Same tx fail-safe (code review) / `bin/verify-completion.sh check_11` symbol 정적 grep.
- **RBAC enforcement** (`test_audit_rbac.py` S1~S10): admin mutation Same tx → audit row visible / `/api/ask` user fail-open → row visible / `.own` SQL filter Actor OR Target / **S3a (E1 B 핵심)** admin password-reset → user 본인 audit 에 target row 노출 / `.own` actor=other → empty (404 byte-equal metadata leak 차단) / `.any` 전체 row / `audit.export` CSV / `audit.purge` chunked w/ idempotency_key / **S8 prod fail-closed** (manual 컨테이너 재시작) / **S9 anonymous share view** → ActorType='anonymous' + ActorAccountId NULL row / S10 `?actor_type=anonymous` filter.
- **migration smoke** (`test_audit_migration.py` M1~M3): legacy WebAccountActivity row INSERT → 다음 fast-path catchup 시 WebAuditEvents 등재 (`RequestId='account-activity:<id>'` marker) / idempotent (두 번째 호출 0 row) / `_log_search_activity` dual write coverage (legacy + new count).
- **AGENT_AUDIT_ENABLED prod fail-closed** (Phase E manual): `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` → container 시작 시 stderr `[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1` 후 process 종료.
- **admin UI smoke** (Phase E browser headless): admin → 감사 로그 탭 진입 → filter 적용 → list row click → detail pane 의 ChangeJson `<pre>` HTML escape 검증 → CSV button (admin 한정 visible) → 새 admin action 발생 (role 생성 등) 후 audit list 에 1:1 row 등장 검증.

### 2.2 verify-completion check_12 audit endpoint routing (TASK-0093, Minor §12.3)

본 cycle 의 정책 인프라 검증 case (`bin/verify-completion.sh` 의 `check_12_audit_endpoint_routing()` + `_check_audit_routing_order()` helper):

- **TEST-0093-A1 (positive, production)**: production `unit/feature-0003-agent-web-ui/src/app.py` 호출 → `CHECK#12 PASS audit endpoint routing order`. 검증 명령:
  ```bash
  WORKTREE=/root/download/docker/mysql_ai_delegated_dev/.worktrees/0086-audit-followup
  cat > /tmp/run-check12.sh << 'EOF'
  #!/usr/bin/env bash
  sed '/^main "\$@"$/d' "$WORKTREE/bin/verify-completion.sh" > /tmp/_helpers.sh
  source /tmp/_helpers.sh
  _check_audit_routing_order "$1"
  EOF
  chmod +x /tmp/run-check12.sh
  /tmp/run-check12.sh "$WORKTREE/unit/feature-0003-agent-web-ui/src/app.py"
  ```
- **TEST-0093-C1 (negative, valid fixture)**: 정합 ordering fixture → PASS.
- **TEST-0093-C2 (negative, wrong_order fixture)**: event_id BEFORE static siblings → FAIL ordering hint (line number + worst sibling 명시).
- **TEST-0093-C3 (negative, no_detail fixture)**: detail endpoint 부재 → FAIL "static audit GET sibling(s) detected but '/{event_id}' detail endpoint missing".
- **TEST-0093-C4 (negative, no_siblings fixture)**: 정적 GET sibling 부재 → FAIL "'/{event_id}' detail endpoint detected but no static GET siblings".
- **TEST-0093-C5 (negative, refactored fixture)**: APIRouter prefix 패턴 → FAIL "audit routes not found in expected form".
- **TEST-0093-D1~D5 (SKIP, other feature)**: feature-0001 / 0002 / 0004 / 0005 / 0006 호출 → silent return 0, no output.
- **TEST-0093-D6 (structural FAIL, missing app.py)**: target feature 인데 app.py 부재 → FAIL "expected app.py at <path> but file is missing".

검증 시점 (2026-05-20): Phase A~D 모두 PASS — 8 scenario (1 production positive + 5 fixture negative + 5 other-feature SKIP + 1 missing-app structural FAIL) 검증 완료.

## 3. Test Cases

### 구조/문법 검증
- TEST-0001: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- TEST-0002: `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
- TEST-0003: `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`

### 계정/RBAC API 검증
- TEST-0004: `GET /api/session` 비인증 시 `authenticated=false`
- TEST-0005: bootstrap admin 로그인 후 `GET /api/auth/me`, `GET /api/admin/accounts`, `GET /api/admin/roles`, `GET /api/admin/permissions` 정상 응답
- TEST-0006: 임시 기본 signup role 생성 후 신규 회원가입 계정에 해당 role이 자동 부여
- TEST-0007: `console.access` 단독 계정은 `/api/admin/permissions`만 조회 가능하고 `/api/admin/accounts`, `/api/admin/roles`는 403
- TEST-0008: 계정 role assignment + override allow/deny 후 최종 permission map이 기대값과 일치
- TEST-0009: `conversation.list.any`, `conversation.read.any` 허용 계정이 타 계정 대화를 조회 가능
- TEST-0010: 타 계정 대화에 대해 `conversation.ask`는 owner mismatch로 차단
- TEST-0011: `conversation.rename.any` override 후 타 계정 대화 제목 변경 가능
- TEST-0012: `/api/clear_memory`가 410을 반환
- TEST-0013: 마지막 관리 가능 계정/role 보호 규칙이 빈 permission set 변경을 차단
- TEST-0014: soft delete 후 로그인 차단 및 기존 세션 폐기
- TEST-0015: `PATCH /api/auth/me`로 현재 비밀번호 검증 후 새 비밀번호 변경 가능
- TEST-0016: 외부 Local LLM gateway 연결 시 `GET /api/session.local_llm_enabled=true`
- TEST-0017: bootstrap admin 세션에서 외부 provider 연결 상태로 `POST /api/ask` + `model=auto`가 API 키 없이 성공
- TEST-0018: 외부 Local LLM provider 미기동 시 `POST /api/ask` + `model=auto`가 503으로 제한
- TEST-0019: 휴리스틱 금지 grep으로 `ACCOUNT_ROLE_*`, `is_admin`, `is_pending`, `_normalize_role(...)`, legacy `can_*` 권한 판정 경로 부재 확인

### 타 계정 대화 검색·필터 (TASK-0072, REQ-20260518-0010, Critical §12.3)
- TEST-0072-1 (S1 .own no leak): `.own` only operator 토큰 + `q=<상대 키워드>` → 응답 items 의 owner_account_id 가 모두 operator 자신. SQL composition order sub-spec 1 검증.
- TEST-0072-2 (S2 .any includes others): admin 토큰 (.any) + 동일 q → cross-account 매칭 포함. `next_cursor` / `has_any` / `search_mode` 응답 필드 존재.
- TEST-0072-3 (S3 byte-equal owner_id): `.own` operator + `owner_id=<other_real>` 와 `owner_id=99999999` 의 응답이 byte-equal. 404/403 metadata leak 차단.
- TEST-0072-4 (S4 cursor disjoint): limit=5 페이지 1 + cursor 페이지 2 의 id set intersection = ∅. SQL ORDER BY 단일화 정합 검증.
- TEST-0072-5 (S5 invalid q → 400): `q="ab"` / `q="  "` / `q="%%"` 모두 400 응답. raw-len < 3 + post-escape 0 char 차단.
- TEST-0072-6 (S6 rate limit 429): 동일 토큰으로 body-search 11 회 호출 → 11 번째 429. per-account 10 req/min in-process token bucket 검증.
- TEST-0072-7 (DDL idempotent): `_ensure_web_account_activity_schema` 를 두 번 호출해도 에러 없음. `CREATE TABLE IF NOT EXISTS` 패턴.
- TEST-0072-8 (audit log INSERT): admin 토큰 + body-search 1 회 → `SELECT COUNT(*) FROM WebAccountActivity WHERE Action='conversation.search.body' AND AccountId=<admin_id>` ≥ 1. QueryHash 가 SHA-256 hex (64 char) 형식.
- TEST-0072-9 (frontend Cmd+K): browser 환경에서 Cmd/Ctrl+K → `#searchModalOverlay` 가 `hidden=false`. Esc / backdrop click / close 버튼 모두 close. focus 가 input 으로 이동.
- TEST-0072-10 (snippet chip .any only): `.own` operator 로그인 시 `#searchFacetSnippet` / `#searchFacetOwner` 둘 다 `hidden=true`. admin 로그인 시 두 chip 모두 visible + 기본 `aria-pressed="false"`.

### 실행 명령
```bash
# 구조 검증 (Phase A 검증)
python3 -m py_compile repo/unit/feature-0003-agent-web-ui/src/app.py
python3 -m py_compile repo/unit/feature-0003-agent-web-ui/tests/test_search_rbac.py
node --check repo/unit/feature-0003-agent-web-ui/src/static/app.js

# HTTP smoke (Phase E — 컨테이너 가동 + 비밀번호 필요)
python3 repo/unit/feature-0003-agent-web-ui/tests/test_search_rbac.py \
    --base-url http://localhost:18080 \
    --admin-user admin --admin-pass <pw> \
    --operator-user operator --operator-pass <pw>
```

### 브라우저 기반 UI 검증
- TEST-0020: 로그인 화면이 계정/권한 안내 중심 2패널 구조로 렌더링된다
- TEST-0021: 로그인 후 메인 화면이 App-Shell 구조로 렌더링되고 외부 스크롤이 발생하지 않는다
- TEST-0022: 관리자 버튼 클릭 시 `/admin` 화면으로 이동하고 Accounts / Roles 2영역이 렌더링된다
- TEST-0023: 관리자 콘솔에서 role 생성/수정/기본 signup role 전환이 가능하다
- TEST-0024: 브라우저 회원가입 후 기본 signup role이 프로필 role 라벨에 반영된다
- TEST-0025: 관리자 콘솔에서 계정 role을 다른 role로 바꾼 뒤 다시 복원할 수 있다
- TEST-0026: own conversation에서 제목 변경/삭제 버튼이 노출된다
- TEST-0027: 타 계정 대화는 `read/list.any`만 있을 때 버튼이 숨겨지고, `rename/delete.any` 허용 후 버튼이 노출된다
- TEST-0028: soft delete 후 `/admin` deleted 필터에 계정이 보이고, 삭제된 계정 로그인은 차단된다
- TEST-0029: 삭제된 role이 관리자 역할 목록에서 제거된다
- TEST-0030: bootstrap admin 브라우저 세션에서 `model=auto`, 질문 `현재 데이터베이스 목록을 보여줘` 가 실제 화면 기준 `60초 이내` 완료되고 완료 화면이 스크린샷으로 남는다

### TASK-0061 GOAL.md 8 항목 합본 cycle (REQ-20260515-0003 ~ -0010)

**Phase 1+2 (답변 버블 실시간 + 신규 대화 첫 polling)**:
- TEST-0080: `state.pendingBubble` 강제 set + `renderMessages()` 호출 시 `#pendingAssistantBubble` element 가 messageLogEl 의 마지막 자식으로 추가된다. spinner / elapsed timer / status badge / latest step / 누적 step `<details>` 5 영역이 정상.
- TEST-0081: `applyProgressPayload({run_id, steps, step_count, display_status, raw_status, is_stale})` 호출 시 `state.pendingBubble.steps` 가 incremental 로 누적되고, 동일 step (step_index+created_at 시그니처) 은 중복 추가되지 않는다.
- TEST-0082: elapsed timer 가 1초 간격 tick 으로 `#pendingBubbleElapsed.textContent` 를 갱신한다 (`Xs / Xm Ys` 형식).
- TEST-0083: `sendPrompt()` lazy-create 분기 시 `state.activeConversationId` 비어 있어도 pending bubble 이 즉시 표시되고, `/api/ask` 응답으로 cid 발급되면 `startProgressPolling({reset:true})` 가 호출되어 polling 이 시작된다.
- TEST-0084: `/api/ask` 실패 (lazy-create) 시 pending bubble 이 `.is-error` 로 전환되고 error 메시지가 노출된다. attach/resume 다이얼로그는 활성화되지 않는다 (cid 발급 여부 불확실).

**Phase 3 (stale processing 만료 감지)**:
- TEST-0085: `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` env 가 컨테이너에 적용된다 (`docker exec web env | grep STALE`).
- TEST-0086: `last_status='processing'` + `last_status_at` 가 만료 시간 초과인 KV 를 조작 후 `/api/progress` 가 `status=stale_error`, `is_stale=true`, `raw_status=processing` 반환한다.
- TEST-0087: `/api/ask_status` / `/api/ask_result` 도 stale 일 때 `is_processing=false` + `is_stale=true` 반환 — attach long-poll 가 즉시 terminal 처리한다.
- TEST-0088: conversation list (`/api/conversations`) 응답에 `display_status` / `raw_status` / `is_stale` 필드가 포함된다.
- TEST-0089: frontend `renderConversationList()` 의 `.conv-dot.is-stale-error` 가 stale 대화에 적용되고 tooltip "작업이 중단된 것으로 보입니다 — 마지막 활동: ..." 이 노출된다.

**Phase 4 (Point rail)**:
- TEST-0090: `#messagePointRail` 컨테이너가 chat pane 우측에 존재하고, 메시지 ≥ 2 일 때 `.hidden` 이 제거된다.
- TEST-0091: `renderMessagePointRail()` 가 메시지 1 개당 1 개의 `.message-point-dot` 를 생성한다 (`is-user` / `is-assistant` 토큰 분기).
- TEST-0092: scroll 이벤트 시 `highlightActivePoint()` 가 viewport 중앙에 가장 가까운 메시지의 dot 에 `.is-active` 를 부여한다.
- TEST-0093: dot 클릭 시 해당 메시지로 smooth scroll 한다 (`scrollIntoView({behavior:'smooth', block:'center'})`).
- TEST-0094: `max-width: 720px` viewport 에서 rail 이 `display: none` 으로 처리된다.

**Phase 5 (캘린더/시각 이동)**:
- TEST-0095: `/api/history_dates?conversation_id=...` 가 `AgentMemoryMessages` 테이블 기준으로 `{dates: {YYYY-MM-DD: [HH:MM, ...]}, first, last}` 응답한다.
- TEST-0096: chat header 의 `#historyCalendarBtn` 클릭 시 `#historyCalendarPopover` 가 노출 (`.hidden` 제거).
- TEST-0097: popover 의 월간 grid 에서 메시지가 있는 날만 `.has-messages` class 가 부여되고, 메시지 없는 날은 `disabled`.
- TEST-0098: 날짜 선택 → 그 날의 첫 시각으로 자동 jump. 시각 선택 → `/api/history_anchor?at=YYYY-MM-DD HH:MM:00` 호출 후 반환된 message_id 의 element 로 smooth scroll + `.is-anchor-highlight` 1.5초 강조.
- TEST-0099: empty state — 메시지 0 개일 때 `#historyCalendarBtn` 이 hidden, 날짜 미선택 시 "메시지가 있는 날짜를 선택하세요" 안내.

**Phase 6 (관리자 비밀번호 초기화, Critical)**:
- TEST-0100: `WebAccounts.MustChangePassword` 컬럼이 존재하고 default 0 (`DESCRIBE WebAccounts` 또는 `SHOW COLUMNS LIKE 'MustChangePassword'`).
- TEST-0101: `POST /api/admin/accounts/{id}/password-reset` 권한: `console.access` + `console.manage` + `account.update` AND `actor.id != account_id`. self-reset (`actor.id == account_id`) 은 400 반환.
- TEST-0102: 권한 없는 계정의 호출은 403 반환.
- TEST-0103: 응답에 `temporary_password` 가 1회 포함되고, `WebAccounts.MustChangePassword=1` + 대상 계정의 `WebAuthSessions IsRevoked=1` 일괄 처리.
- TEST-0104: 대상 계정 로그인 응답에 `must_change_password=true` 가 포함되어 frontend force change modal 이 노출된다. 변경 modal 의 close button 미제공 (강제 변경 전 다른 액션 차단).
- TEST-0105: `PATCH /api/auth/me` 로 비밀번호 변경 성공 시 `MustChangePassword=0` 으로 reset 되고 force modal 이 자동 닫힘.
- TEST-0106: 관리 콘솔 Account detail 의 `adminPasswordResetBtn` "비밀번호 초기화" 버튼이 비-self / 비-deleted / 비-pending new 계정에서만 노출.

**Phase 7 (admin select-all 현재 페이지 fix)**:
- TEST-0107: `currentPageAccounts()` helper 가 `filteredAccounts()` 의 `accountPage` slice 만 반환한다 (≤ ACCOUNT_PAGE_SIZE).
- TEST-0108: `accountSelectAll.checked = true` (또는 change event) 시 현재 페이지 row 의 id 만 `accountSelected` Set 에 추가, 다른 페이지 선택은 보존.
- TEST-0109: `updateAccountSelectAllCheckbox()` 가 현재 페이지의 선택 비율로 checked / indeterminate / unchecked 정확 반영.
- TEST-0110: 검색 / 필터 / 페이지 이동 후에도 동일 정합 유지.

**Phase 8 (내 대화 Ctrl/Shift 다중 선택 + bulk delete)**:
- TEST-0111: own 그룹의 conversation item 에 `.conv-item-checkbox` 가 노출 (delete.own 권한 보유 시). 타 계정 대화에는 미노출.
- TEST-0112: Ctrl/Meta + click → toggle. Shift + click → 마지막 click 이후 range 선택.
- TEST-0113: `.conv-bulk-bar` 가 selection ≥ 1 시 노출 + 라벨 "N개 선택됨" + 삭제 / 선택 해제 버튼.
- TEST-0114: `POST /api/delete_conversations` 가 partial success 응답 (`{deleted, deleted_pending, failed:[{conversation_id, reason}], current}`) 을 반환. 빈 body 는 400. 권한 없는 항목 / processing (force=false) 항목은 failed 에 분리.
- TEST-0115: ≥10 항목 선택 시 typed-confirm 으로 정확한 숫자 입력 요구. processing 대화 포함 시 추가 confirm + "삭제" 입력 요구.
- TEST-0116: 삭제 성공 후 `conversationSelected` clear, active 대화가 삭제된 경우 빈 상태로 reset, `loadConversations()` 로 list 재로드.

### TASK-0047 Product Selector + Auto 모드
- TEST-0031: `/api/session` 응답에 `product_pref{mode,pinned_id,fallback_reason}` + `conversation_product` 키가 항상 포함된다
- TEST-0032: 사이드바 헤더에 `#productChip` + `#productSelect` 마크업이 존재하고 caption "이 대화의 제품" 이 노출된다
- TEST-0033: select 옵션 첫 번째가 `auto` (value="auto", "auto · 자동 (제품 미선택)") 이고 활성 product 들이 그 뒤로 채워진다
- TEST-0034: chip `data-mode` 가 server hydrate 결과(auto / pinned) 와 정확히 일치한다
- TEST-0035: PATCH `/api/conversations/{cid}/product` 가 `pinned`/`auto` 양쪽 mode 에서 200 으로 응답하고 row 가 갱신된다
- TEST-0036: PATCH 가 `mode='pinned'` 인데 product_id 누락이거나 비존재 product_id 일 때 400 으로 거부한다
- TEST-0037: `AgentMemoryKv.last_status='processing'` 동안 PATCH 가 409 로 거부된다 (turn 단위 immutability 가드)
- TEST-0038: `/api/new_conversation` body 가 `mode='auto'|'pinned' + product_id?` 를 수용해 새 대화의 product_mode 가 일치한다
- TEST-0039: UI 에서 select 변경 → setActiveProduct → chip data-mode 즉시 갱신 + localStorage `mad.productPref.v1` 미러
- TEST-0040: 신규 auto 대화로 진입 후 페이지 reload 시 chip 이 auto 로 hydrate 된다
- TEST-0041: 고정 UI 라벨(button/label/option/h1-3 등; conv-list/messages 제외)에 한글 "상품" 잔존 0
- TEST-0042: `_runtime_tables_available` probe 가 신규 컬럼(`product_mode`, `ProductPrefMode`, `ProductPrefPinnedId`) 부재 시 errno 1054 로 False 반환해 마이그레이션을 자동 트리거한다

## 4. Test Run History
- 2026-05-19 (TASK-0072 + TASK-0074 HTTP smoke — `bootstrap_admin` 1 토큰만 ad-hoc curl):
  - **S2 .any cross-account** (`GET /api/conversations?q=데이터&limit=10`): ✅ `matched_count=10`, `has_any=true`, `search_mode=true`, `next_cursor` 존재.
  - **S4 cursor disjoint** (limit=5 페이지 1 → 페이지 2):
    - 페이지 1 ids: `20260515074803-d613ab40 20260515092328-a7e5e9e1 20260515092319-96e627b9 20260515092147-e3dc971b 20260515092113-3a7944ff`
    - next_cursor: `2026-05-15 18:21:42|20260515092113-3a7944ff`
    - 페이지 2 ids: `20260515074935-58c48a7e 20260515080029-a5353434 20260429084833-6f07eb25 20260429075057-af0d6352 20260416081007-ec1bfd5d`
    - overlap = ∅ → PASS (sub-spec 3 SQL ORDER BY 단일화 + cursor keyset 정합 확인).
  - **S5 invalid q → 400**: `q="ab"` → 400 / `q="%%"` → 400 / `q="  "` → 400 (raw-len < 3 또는 escape-0 모두 차단).
  - **S6 rate limit 11th → 429**: call#1~10 모두 200, call#11 → 429. per-account 10 req/min token bucket 동작 확인.
  - **S7 DDL idempotent**: `SHOW CREATE TABLE WebAccountActivity` 응답에 PK `(Id)` + `IX_WAA_Account (AccountId, CreatedAt)` + `IX_WAA_Action (Action, CreatedAt)` 모두 존재. AUTO_INCREMENT=24 (이전 호출 누적).
  - **S8 audit INSERT**: `SELECT ... FROM WebAccountActivity ORDER BY Id DESC LIMIT 10` → 23 rows. AccountId=1 (`bootstrap_admin`), Action=`conversation.search.body`, QueryHash 100% 64-char SHA-256 hex (length distribution = `{64: 23}`), MatchedCount 정확. rate-limited (429) 11번째 호출은 audit 안 됨 (endpoint 가 429 early return — 정확한 동작).
  - **Skip**: S1 (.own no leak) / S3 (byte-equal owner_id) — operator (`review_user01`) pw 미보유. SQL composition order sub-spec 1 의 코드 review (`_list_conversations` line 2941-2949 의 has_any 분기 + endpoint line 5566-5571 의 effective_owner_id 강제 overwrite) 로 검증.
  - **TASK-0074 UI 가독성**: 사용자가 브라우저 hard refresh 후 직접 확인 권장.
- 2026-05-15 (TASK-0061 round 2 — /qa 심층 검증, browser session `483add52718b4a93`):
  - **Phase 4 Point rail 동작 검증**: 메시지 2 개 대화 (`20260515080029-a5353434`, topic "[Fork] 안녕하세요...") 선택 → `state.messages.length=2`, `#messagePointRail.hidden=false`, `.message-point-dot` 2 개 노출. 첫 dot click → `messageLog.scrollTop=245 → smooth scroll`, `.message-point-dot.is-active.dataset.messageId=291` 갱신 확인.
  - **Phase 5 캘린더 deep 동작 검증**:
    - `historyCalendarBtn` click → popover hidden 제거, title "2026년 5월" (선택 대화의 메시지 날짜 자동 cursor).
    - `calendarPrevMonth` click → title "2026년 4월" 정상 이동.
    - `calendarNextMonth` click → title "2026년 5월" 복귀.
    - has-messages day "15" click → `.history-calendar-day.is-selected.textContent=15`, `.history-calendar-time` 1 개 (그 날 메시지가 1 건) 표시.
    - 시각 click → `/api/history_anchor` 호출 → `.is-anchor-highlight` 1.5 초 강조 (정상 동작 — 1 차 cycle 의 단위 검증으로 확인).
    - screenshot: `/shared/out/browser/shot_20260515_091222.png`.
  - **Phase 7 admin select-all cross-page 동작**: 1 차 cycle 에서 `currentPageAccounts().length=15` == `accountList .admin-list-row` 개수, `filteredAccounts().length=26` (다른 페이지에 11 개) 확인. round 2 의 admin page reload + cross-page selection 시퀀스는 bash quote escape 이슈로 추가 자동화 어려움 — code review + unit-level helper 동작 검증 (`currentPageAccounts()` 정확한 slice 반환) 으로 정합 보장.
  - **Phase 3 stale 감지 / Phase 6 비번 reset / Phase 8 bulk delete**: 1 차 cycle 의 응답 형식 / endpoint 권한 / DOM 요소 검증 (`/api/progress` 의 display_status·raw_status·is_stale 포함 / `adminPasswordResetBtn` 노출 / `/api/delete_conversations` empty body 400 validation) 으로 contract 확정. **실 데이터 manipulation 또는 destructive 실 호출 검증은 운영 환경에서 사용자 명시 시점에 별도 진행 권고** — stale 은 backend 의 KV 시각 조작 필요, 비번 reset 은 대상 계정의 세션 강제 종료 + 임시 비번 발급 destructive, bulk delete 는 대화 영구 삭제 destructive.
  - 정합 검증 결과: 본 cycle 의 PR 본문 (`#27` 의 차후 PR 으로 main 머지) 에 추가 fix 없이 ship 가능. round 2 검증에서 신규 발견 이슈 0건.
- 2026-05-15 (TASK-0061 GOAL.md 8 항목 합본 cycle):
  - 정적 검증:
    - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` → PASS
    - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` → PASS
    - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` → PASS
  - 컨테이너 재배포: `make web` → `repo-web-1 Recreated/Started`. mysql healthy.
  - browser 검증 (`http://web:8000` via `make browser-*`, session `e438b0811dc1477d`):
    - 메인 페이지: title `MySQL AI Assistant`, cache-bust `?v=20260515-task-0061` 적용. 신규 DOM 5개 (`.messages-wrap` / `#messagePointRail` / `#historyCalendarBtn` / `#historyCalendarPopover` / `#conversationBulkBar`) 모두 존재.
    - bootstrap_admin 로그인 → auth overlay hidden + profile name "bootstrap_admin" 정상.
    - conversation list 45개 표시, 내 대화 checkbox 34개 노출 (own 그룹 한정), 타 계정 대화 (11개) 에는 미노출.
    - 첫 own conversation 의 checkbox click → `conv-bulk-bar` 노출, label "1개 선택됨" 표시 확인.
    - `#historyCalendarBtn` click → `#historyCalendarPopover` 노출, title "2026년 4월", has-messages day 1개 (4/22) 정상.
    - `/api/progress` 응답: `{status:"done", display_status:"done", raw_status:"done", is_stale:false}` — 신규 필드 모두 포함.
    - `/api/history_dates` 응답: `{first:"2026-04-22", last:"2026-04-22", dateCount:1}` — `AgentMemoryMessages` 정본 기준 동작 확인.
    - `/api/delete_conversations` 빈 body POST → HTTP 400 validation 정상.
    - pending bubble 강제 렌더 (`state.pendingBubble = {...}; renderMessages();`) → `#pendingAssistantBubble` + `.pending-bubble-spinner` + `#pendingBubbleElapsed` 모두 존재. `clearPendingBubble()` 호출 시 정상 정리.
    - admin 페이지: title `MySQL AI Assistant Admin`. accountList 15 rows (현재 페이지). `currentPageAccounts().length == 15`, `filteredAccounts().length == 26` — helper 가 정확히 현재 페이지 sub-set 반환. 비-bootstrap_admin 계정 (sales) detail panel 진입 시 `adminPasswordResetBtn` "비밀번호 초기화" 노출 확인.
    - screenshot: `/shared/out/browser/shot_20260515_085713.png` (admin sales detail with reset btn).
  - 미수행: 실제 stale 시각 manipulation (KV 직접 UPDATE 로 last_status_at 을 만료 시간 이전으로 후퇴) → 후속 cycle 의 운영 데이터 관찰 시 함께 확인 권고. 실제 비밀번호 reset → 로그인 force modal end-to-end → 변경 완료 흐름은 별도 사용자 환경 검증 (현재 cycle 은 backend endpoint 권한 / button 노출 / 응답 구조 / modal DOM 정상 확인까지).
- 2026-05-15 (TASK-0060 Product / Role 시스템 프롬프트 정비):
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`
    - 결과: 통과
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
    - 결과: 2건 통과
  - DB 분석 / readback:
    - `KR`: `dbgame` 98 tables, `dblog` 279 tables, `dbauth` 9 tables 확인
    - `MV`: `account_db` 6 tables, `dev_1_1_1_20` 62 tables, `have_00` 50 tables, `global_db` 28 tables, `log_v2` 0 tables 확인
    - `WebSystemPrompts`: Product prompt 2건 + Role common prompt 5건 content length 확인
  - runtime 직접 확인:
    - web 컨테이너 내부 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")`
    - 결과: `HAS_PRODUCT_CONTEXT=True`, `HAS_ROLE_COMMON=True`, `HAS_SALES=True`
- 2026-03-26: 구조 검증 기준만 정의
- 2026-04-06: 이전 로그인 버그 수정 기준의 브라우저 검증 수행
- 2026-04-14: 이전 콘솔형 UI 렌더링 검증 수행
- 2026-04-15:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`
  - curl 기반으로 `session/auth/signup/admin/accounts/new_conversation/conversations/history/ask` 검증
  - MySQL로 `AgentCoreConversations.owner_account_id` 직접 확인
  - 브라우저 자동화로 스크린샷 생성:
    - `/shared/out/browser/ui-account-login.png`
    - `/shared/out/browser/ui-account-workspace.png`
    - `/shared/out/browser/ui-account-admin.png`
  - 이후 구현 변경으로 프로필 드로어 탭, 로그아웃 초기화, Admin 검색/페이지네이션, 병렬 대화 UX, 외부 Local LLM provider 기준 ask 흐름에 대한 재검증 필요
- 2026-04-15:
  - bootstrap admin 브라우저 로그인 후 `model=auto` 실사용 검증
  - 완료 화면 conversation `20260415092741-f2384e59`, subtitle `최근 갱신 2026. 04. 15. 오후 06:28 · 메시지 2 · 상태 done`
  - 회귀 측정 결과:
    - `20260415091922-1a529620`: `duration_ms=33038.4`
    - `20260415092741-f2384e59`: `duration_ms=35555.35`
  - 스크린샷 증빙:
    - `/shared/out/browser/perf_login.png`
    - `/shared/out/browser/perf_before_send.png`
    - `/shared/out/browser/perf_just_after_send.png`
    - `/shared/out/browser/perf_done.png`
  - 테스트 중 생성된 stuck conversation `20260415093013-f34140ec` 는 `POST /api/cancel` 후 `status=done` 으로 정리했고, 이후 `GET /api/conversations` 기준 `processing` 0건 확인
- 2026-04-16:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`
  - API 회귀 스크립트로 기본 signup role 전환, role CRUD, account override, `console.access` 읽기 전용 셸, own/any 대화 권한, `clear_memory=410`, 마지막 관리 가능 계정 보호, soft delete/session revoke 검증
  - 브라우저 자동화로 관리자/사용자 세션 검증:
    - `/shared/out/browser/rbac_admin_home_76309029.png`
    - `/shared/out/browser/rbac_admin_roles_76309029.png`
    - `/shared/out/browser/rbac_user_own_76309029.png`
    - `/shared/out/browser/rbac_user_other_76309029.png`
  - 후속 브라우저 검증으로 deleted 필터의 soft-deleted 계정 표시, 삭제 role 미노출, 삭제 계정 로그인 차단을 재확인

- 2026-04-30 (TASK-0047 Product Selector + Auto 모드 자동 검증):
  - 빌드: `docker compose build --no-cache web` (BuildKit layer cache 가 stale 잡는 edge case 회피) → image sha 갱신.
  - 컬럼 검증: `SHOW COLUMNS FROM AgentCoreConversations LIKE 'product_mode'` → `varchar(8) NO '' pinned`. `SHOW COLUMNS FROM WebAccounts LIKE 'ProductPref%'` → `ProductPrefMode varchar(8) YES NULL`, `ProductPrefPinnedId bigint YES NULL`.
  - Playwright 28-check spec 실행 결과: **28/28 PASS, healthScore=100, console.error=0**. 결과 JSON: `repo/.gstack/qa-reports/qa-product-selector-result.json`.
  - 검증된 항목: AUTH(1) / SESSION(4) / BUST(2) / MARKUP(2) / CHIP(5) / LABEL(1) / PATCH(4) / NEWCONV(2) / UI(3) / HYDRATE(1) / RACE(2) / CONSOLE(1).
  - 스크린샷 증빙: `repo/.gstack/qa-reports/screenshots/product-01-app-loaded.png`, `product-02-pinned-selected.png`, `product-03-auto-selected.png`, `product-04-auto-hydrated.png`.
  - 발견된 회귀: 기존 배포의 fast-path 가 신규 컬럼 마이그레이션을 우회하던 문제. `_runtime_tables_available` probe 에 신규 컬럼 검사 + errno 1054 분기를 추가해 자동 트리거되도록 수정 (CHG-20260430-0019, REV-20260430-0009).
  - 검증 미흡 영역(후속): LLM resolver 도입(R-02) 후 autoFocusChip / 운영 회귀(다중 탭 BroadcastChannel, mobile bottomsheet), R-03 row-level lock — 모두 BRIEFING-product-selector-v1.md §1 추적.
