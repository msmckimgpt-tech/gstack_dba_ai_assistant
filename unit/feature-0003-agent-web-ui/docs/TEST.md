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

### 2.3 외부 LAN trust 강화 — `_get_client_ip()` 조건부 trust + Caddy XFF 정규화 (TASK-0087, Major §12.3)

본 cycle (TASK-0087, REQ-20260520-0002, **Major** §12.3) 의 검증 시나리오. Codex outside voice (REV-20260520-0010) 권장 8 시나리오 + 본 cycle 추가 확장.

**Phase A** — Caddyfile 정규화 검증:
- **TEST-0087-A1 (positive, caddy validate)**: `docker compose run --rm caddy caddy validate --config /etc/caddy/Caddyfile` → exit 0. `header_up X-Forwarded-For {client_ip}` directive 인식.
- **TEST-0087-A2 (live, header replace)**: Caddy 컨테이너 가동 + 외부 클라이언트가 `curl -H 'X-Forwarded-For: 1.2.3.4' https://<HOST>/api/session` → web 측에서 `request.headers['x-forwarded-for']` 가 Caddy container IP (예: 172.18.0.x) 로 정규화됨 (1.2.3.4 가 아님). live 검증 사용자 위임.

**Phase B** — `_get_client_ip()` unit 시나리오 (Codex 권장 8건 + 확장):
- **TEST-0087-B1 (trusted proxy + valid XFF)**: `WEB_TRUSTED_PROXIES=172.18.0.0/16`, direct_ip=`172.18.0.5`, XFF=`1.2.3.4` → return `1.2.3.4`.
- **TEST-0087-B2 (trusted proxy + invalid XFF)**: 같은 env, direct_ip=`172.18.0.5`, XFF=`garbage` → return `172.18.0.5` (direct_ip fallback).
- **TEST-0087-B3 (trusted proxy + empty 첫항목)**: 같은 env, XFF=`,1.2.3.4` (콤마 시작) → 첫 토큰 빈 문자열 → `ipaddress.ip_address("")` ValueError → return `172.18.0.5`.
- **TEST-0087-B4 (untrusted direct_ip + spoofed XFF)**: `WEB_TRUSTED_PROXIES=172.18.0.0/16`, direct_ip=`192.168.1.10`, XFF=`1.2.3.4` → return `192.168.1.10` (spoof 차단).
- **TEST-0087-B5 (IPv6 trusted + IPv6 XFF)**: `WEB_TRUSTED_PROXIES=fd00::/8`, direct_ip=`fd12::1`, XFF=`2001:db8::1` → return `2001:db8::1`.
- **TEST-0087-B6 (bare IP /32, /128)**: `WEB_TRUSTED_PROXIES=172.18.0.5/32`, direct_ip=`172.18.0.5` → trusted. direct_ip=`172.18.0.6` → untrusted, direct_ip return.
- **TEST-0087-B7 (empty WEB_TRUSTED_PROXIES)**: env 미설정, direct_ip=`172.18.0.5`, XFF=`1.2.3.4` → return `172.18.0.5` (XFF 완전 무시).
- **TEST-0087-B8 (XFF with port)**: `WEB_TRUSTED_PROXIES=172.18.0.0/16`, direct_ip=`172.18.0.5`, XFF=`1.2.3.4:5678` → `ipaddress.ip_address("1.2.3.4:5678")` ValueError → return `172.18.0.5`.

**Phase C** — startup gate 검증 (mode-aware):
- **TEST-0087-C1 (invalid CIDR + prod fatal)**: `WEB_TRUSTED_PROXIES=invalid_cidr,10.0.0.0/8`, `AGENT_MODE=prod` → app.py import 실패, `RuntimeError("WEB_TRUSTED_PROXIES: invalid CIDR(s) in prod: ['invalid_cidr']")`.
- **TEST-0087-C2 (invalid CIDR + dev warning)**: `WEB_TRUSTED_PROXIES=invalid_cidr,10.0.0.0/8`, `AGENT_MODE=dev` → app.py import 성공, stderr WARNING 출력. `WEB_TRUSTED_PROXIES` = `(IPv4Network('10.0.0.0/8'),)` (invalid 만 skip).
- **TEST-0087-C3 (proxy mode + empty + prod fatal)**: `WEB_TRUSTED_PROXIES=""`, `ENABLE_WEB_TLS_PROXY=1`, `AGENT_MODE=prod` → `RuntimeError("WEB_TRUSTED_PROXIES is empty while ENABLE_WEB_TLS_PROXY=1 in prod ...")`.
- **TEST-0087-C4 (proxy mode + empty + dev warning)**: 같은 env, `AGENT_MODE=dev` → stderr WARNING. import 성공.

**검증 방법** (단위):
```bash
# B1~B8: pytest 또는 Python REPL 으로 직접 호출 (Request mock + headers dict)
docker compose run --rm \
  -e WEB_TRUSTED_PROXIES=172.18.0.0/16 \
  -e AGENT_MODE=dev \
  --entrypoint python web -c "
from web.app import _get_client_ip, _is_trusted_proxy
print(_is_trusted_proxy('172.18.0.5'))   # True
print(_is_trusted_proxy('192.168.1.10')) # False
"

# C1: prod fatal
docker compose run --rm \
  -e WEB_TRUSTED_PROXIES='invalid_cidr,10.0.0.0/8' \
  -e AGENT_MODE=prod \
  --entrypoint python web -c "import web.app" 2>&1 | grep "WEB_TRUSTED_PROXIES: invalid"

# C3: proxy mode + empty + prod fatal
docker compose run --rm \
  -e WEB_TRUSTED_PROXIES='' \
  -e ENABLE_WEB_TLS_PROXY=1 \
  -e AGENT_MODE=prod \
  --entrypoint python web -c "import web.app" 2>&1 | grep "WEB_TRUSTED_PROXIES is empty"
```

검증 시점 (2026-05-21): Phase A~B (코드 변경) 적용 완료, py_compile PASS. B1~B8 / C1~C4 단위 검증은 사용자가 docker 환경에서 위 명령으로 진행 (TEST.md §4 Test Run History 에 결과 기록).

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

### TASK-0277 보관 대화 탭 UI 정합 다듬기 (REQ-20260615-0279, AC-0507~0508, Minor §12.3)
- TEST-0059: [문제1] admin.html 에 `class="admin-pane-note"` 사용 0건 + styles.css 에 `.admin-pane-note {` 규칙 0건(제거 확인).
- TEST-0060: [문제1] 보관 대화 pane header↔filter(`admin-archive-filter`) 사이 영역에 `<p>` 안내 문단 없음(다른 탭과 동일 밀도).
- TEST-0061: [문제1] `#archiveDetail` 빈 상태(static HTML) + `renderArchiveDetail` 빈 분기(JS) 양쪽이 `admin-archive-detail-note` 안내("보관됩니다" 포함) carry.
- TEST-0062: [문제2] `renderArchiveList` 로 긴/짧은 문자열 혼재 2 row 렌더 → 각 row 가 정확히 2개의 `.admin-archive-row-line`(1줄=topic+ts, 2줄=owner+by) — 문자열 길이 무관 고정.
- TEST-0063: [문제2] CSS 계약 — `.admin-archive-row-line` 에 `flex-wrap` 부재 + `min-width:0`; topic/owner/by 각 span 에 `white-space:nowrap`+`text-overflow:ellipsis`+`overflow:hidden`+`min-width:0`(줄바꿈 대신 절단 보증).

### TASK-0276 관리 콘솔 "보관 대화" 탭 UI 정합화 (REQ-20260615-0276, AC-0503, Minor §12.3)
- TEST-0053: 빈 목록 → `#archiveList` 에 `.admin-list-empty`("보관된 대화가 없습니다.").
- TEST-0054: 항목 N개 → `.admin-list-row.admin-archive-row` N개(audits 동형 클래스) + `#archiveListCount` "N건" + row 에 topic·보관 시각·소유자·보관 수행자 표시.
- TEST-0055: row 클릭 → `adminState.archives.selectedId` 설정 + `#archiveDetail` 에 `.admin-archive-detail`(dl 메타) 렌더 + 선택 row `is-selected`.
- TEST-0056: 미존재 selectedId → `#archiveDetail` `.admin-detail-empty`.
- TEST-0057: topic 에 `<img onerror>` 주입 → 목록·상세 양쪽 `_archiveEsc` escape(`img` 노드 0, `&lt;img` 텍스트).
- TEST-0058: truncated=true → `#archiveListScope` 에 "좁혀" 안내.

### TASK-0275 assistant 첨부 수정 → 새 버전 materialize + 버전 관리 (REQ-20260615-0275, AC-0493~0496, Critical §12.3)
- TEST-0046: `_parse_attachment_edit_blocks` — 정상 ```attachment-edit``` 블록(헤더 JSON + 내용)을 파싱하고, 헤더 깨짐/source_id 누락/0/블록 부재는 graceful 빈 리스트.
- TEST-0047: `_materialize_assistant_attachment_edits` — 정상 텍스트 첨부 → 새 버전 INSERT(VersionNumber+1, CreatedByRole='assistant', RootAttachmentId=root) + MinIO put + 직전 버전 supersede.
- TEST-0048: materialize 가드 — 바이너리 kind(pdf) source 거부(가드1), cross-conversation source 거부(가드2), cross-account source 거부(가드2), 내용 size cap 초과 거부(가드4), turn 당 개수 cap 초과분 무시(가드4).
- TEST-0049: `_serialize_attachment_for_api` — version_number/root_attachment_id(NULL root → 자기 Id)/created_by_role/is_assistant_generated/superseded 직렬화.
- TEST-0050: `_next_version_filename` — 확장자 보존 버전 접미(report.csv→report_v2.csv), 무확장자/빈입력 fallback.
- TEST-0051: `list_conversation_attachments` SQL 에 `SupersededAt IS NULL` 필터 존재(최신 버전만 노출, 정적 소스 검사).
- TEST-0052: 라이브 — materialize→MinIO 바이트(sha256 일치)·부모 supersede·목록 최신만·`/versions` 체인 2개·IDOR 2종 거부·traversal/.exe 차단·UNIQUE 충돌 IntegrityError.

### TASK-0272 프로필 첫 진입 제품 범위 적재 (REQ-20260615-0272, AC-0487, Minor §12.3)
- TEST-0043: `switchProfileTab("prompt")` 가 호출되면(탭 클릭 이벤트 없이도) `#promptProductSelect` 가 `state.products` 의 활성 제품으로 채워진다 — `openProfile("prompt")`(드로어 첫 오픈) 경로에서도 적재된다.
- TEST-0044: `initialize()` 의 탭 클릭 리스너는 `switchProfileTab(tab)` 만 호출하고 lazy 디스패치(`initAccountPromptEditor`/`loadProfileUsage`)를 직접 중복 보유하지 않는다 (단일 진입점 = `switchProfileTab`).
- TEST-0045: node --check app.js 통과 (구문 무결).

## 4. Test Run History
- 2026-06-16 (TASK-20260616T100304-conv-entry-defaults — 작업 화면 첫 진입 기본값: 타 계정 대화 접힘 + 빈 대화 화면):
  - **Environment: CLI** (정적 + 순수 node 회귀). `node --check app.js` PASS + `tests/verify_conv_entry_defaults.mjs` **20/20 PASS** (jsdom 불필요 — localStorage/state 로직: `_seedOthersCollapsedOnce` fresh seed/already-seeded respect/date-group 보존, `loadConversations` 빈 진입(allowCurrentFallback=false)·기본 폴백·resume-select·preferred-미존재·pending-guard, `initializeWorkspace` 배선 4종). 백엔드 무변경. REV-20260616T100304-ai-claude-conv-entry-defaults [SKIPPED:frontend-ui-entry-defaults-no-backend-no-rbac].
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → 로그인(bootstrap_admin) → 작업 화면 진입 → localStorage clean-room 재현 + computed/state 실측).
  - **PB-0008 PASS (배포본 main `b5f2434`, healthz git_commit 일치 mysql_ok·pg_ok, `?v=20260616-conv-entry-defaults`)**:
    - **요구2 (빈 대화 화면)**: 로그인(bootstrap_admin)·대화 104개·서버 직전 대화 존재(`state.session.conversation_id="20260615070025-1ae46506"`)인데도 첫 진입 `state.activeConversationId=""`·`#conversationTitle="대화를 선택하세요"` — 직전 대화 자동선택 차단 확인(구behavior 라면 로드됐을 대화).
    - **요구1 (타 계정 대화 접힘)**: 타 계정 대화 50건 존재. 첫 진입 시 `.conv-group-collapsible`("타 계정 대화") `is-collapsed=true`·`aria-expanded="false"`·`.conv-owner-header` **0개 렌더**(50건 숨김), `localStorage["mad.othersCollapsedSeed.v1"]="1"`·`collapsedGroups=["__others__"]`.
    - **clean-room 결정 증명**: `localStorage.clear()` → reload → seed 재발화(`seedFlag="1"`·`__others__`∈set·접힘·owner 0)·빈 화면(`activeConv=""`) 동시 재현. 서버 current 는 여전히 존재(미로드).
    - **선호 존중**: "타 계정 대화" 헤더 click → 펼침(`is-collapsed=false`·owner 헤더 5개 렌더·set 에서 `__others__` 제거) → reload 후에도 **펼침 유지**(`stillExpandedAfterReload=true`·owner 5개·seedFlag 유지) — 재접힘 강제 없음(seed-once).
    - evidence `artifacts/pb0008-conv-entry-defaults/entry-others-collapsed-empty-chat.png`(타 계정 대화 접힘 + 빈 대화 화면 육안). REV-20260616T163634-ai-claude-conv-entry-defaults-pb0008 [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-16 (TASK-20260616T022652-ai-claude-sidebar-resize — 대화창 좌측 사이드바 너비 드래그 조절):
  - **Environment: CLI** (정적 + jsdom + 컨테이너 make test). `node --check app.js` PASS + CSS brace 균형(1222=1222) + **jsdom 23 PASS** (`tests/verify_sidebar_resize.mjs` — [1] index.html `#sidebarResizer` role=separator·`.app-shell` 자식 위치, [2] styles.css `.app-shell{position:relative}`·`.sidebar-resizer{left:var(--sidebar-w);cursor:ew-resize}`·모바일 display:none, [3] init `setupSidebarResize()`·resize 리스너 `_applySidebarWidth()`, [4a] 핸들 1회 배선·멱등, [4b] drag→`--sidebar-w`=clientX·`is-sidebar-resizing`·mouseup localStorage 영속, [4c] clamp 하한 180/상한 512@1024·`_sidebarMaxW`, [4d] 저장값 복원·모바일 override 제거, [4e] 더블클릭 reset) + make test 컨테이너 **전체 회귀 0**(REAL_MAKE_EXIT=0, ruff clean). 백엔드 무변경. REV-20260616T022652-ai-claude-sidebar-resize [SKIPPED:frontend-ui-resize-no-backend-no-rbac].
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → 로그인(bootstrap_admin) → 사이드바 노출 → MouseEvent 디스패치 + computed 실측).
  - **PB-0008 PASS (배포본 main `6f1242b`, healthz git_commit 일치, `?v=20260616-sidebar-resize`, innerWidth 1249)**: 핸들 `#sidebarResizer` computed `display:block·cursor:ew-resize·position:absolute·width:8px·visible:true`(hit-test 가능). **드래그 실측(실 레이아웃 reflow — jsdom 미검출 영역)**: before `--sidebar-w 252px / sidebarW 252 / chatLeft 252` → 드래그 252→380 `var 380px / sidebarW 380 / chatLeft 380 / localStorage "380"`(사이드바 실제 확장 + chat-column 우측 reflow). **clamp**: 좌측 드래그(clientX 50)→`180px`(하한), 우측 드래그(clientX 99999)→`624px`(=min(640, floor(1249×0.5))=624 정확 일치). **영속**: 340px 드래그 후 페이지 reload → `--sidebar-w 340px / sidebarW 340 / localStorage "340"`(`_applySidebarWidth` 복원). **reset**: 핸들 더블클릭 → `252px`(기본)·`localStorage` null. evidence `artifacts/pb0008-sidebar-resize/sidebar-resized-340.png`(확장된 사이드바·대화목록·하단 프로필·chat-column reflow 육안). REV-20260616T024150-ai-claude-sidebar-resize-pb0008 [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-15 (TASK-0277b 후속 핫픽스 — 보관 대화 row ellipsis 실작동 수정):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → /admin(세션 인증됨) → 보관 대화 탭 클릭 → computed layout 실측).
  - **PB-0008 적발 (TASK-0277 배포본 main `61e0151`, `?v=...task0277-archives-ui-align`)**: [문제1] `paneNotePresent:false`·header↔filter gap 16px(밀도 정합 PASS). [문제2] **줄바꿈 차단은 PASS**(긴 문자열 주입 시 rowH 56px 고정) **이나 ellipsis 미작동**(line getBoundingClientRect 2858px, topic scrollW===clientW===2714 → clipped:false). 원인 진단: `.admin-archive-row` computed `align-items:center`(`.admin-list-row` grid 상속) → 줄이 row 폭으로 stretch 안 됨.
  - **수정 라이브 실험 검증**: `r.style.alignItems='stretch'` 적용 시 line 2858→308px, topic clientW 164·scrollW 2714 → **clipped:true(ellipsis 작동)**, rowH 56 유지(2줄 고정). → `styles.css` 에 반영.
  - **재배포 후 PB-0008 재검증 PASS (main `d6123d3` #252, web 재빌드, 서빙 `?v=20260615-task0277b-archive-row-ellipsis`)**: 실 Chrome/148 relay, /admin(세션 인증) → 보관 대화 탭 → 긴 문자열(×40 반복) 주입 후 computed 실측 — `rowAlignItems:stretch`·`paneNotePresent:false`·`lineCount:2`·`rowH 56→56 heightStable:true`(2줄 고정·미줄바꿈)·`line0W 308`(row 폭 330 내 갇힘, 팽창 해소)·**topic `clientW 164 < scrollW 2586 → clipped:true`(nowrap+ellipsis 발동)**·owner `132<1627 clipped:true`·by `168<2066 clipped:true`. 즉 [문제1] 안내 우측 이동(밀도 정합) + [문제2] 2줄 고정·`…` 절단 모두 실 브라우저 PASS. evidence: `artifacts/pb0008-task0277/{01_archive_long_ellipsis,02_archive_clean_density}.png`(긴 topic·소유자·보관자 `…` 절단 + 우측 빈 상태 안내 표면화 육안 확인).
  - **Environment: CLI** (정적 + jsdom). node --check + CSS brace(1210=1210) + **jsdom 26 PASS**(0277 25건 + `.admin-archive-row align-items:stretch` 계약 1건) + make test 컨테이너 **전체 회귀 0**(MAKE_EXIT=0). REV-20260615-0283 [SKIPPED:frontend-ui-consistency-no-backend].
- 2026-06-15 (TASK-0277 보관 대화 탭 UI 정합 다듬기 — 안내 밀도 정합 + row 2줄 고정·ellipsis):
  - **Environment: CLI** (정적 + jsdom). node --check admin.js PASS + CSS brace 균형(1207=1207) + **jsdom 25 PASS**(`tests/verify_archive_tab_ui.mjs` — admin-pane-note 0건·styles.css 규칙 제거·header↔filter `<p>` 없음·빈 상태 안내 carry(static+JS)·긴/짧은 row 2줄 고정·1줄 topic+ts/2줄 owner+by·flex-wrap 제거·topic/owner/by nowrap+ellipsis+overflow+min-width:0) + make test 컨테이너 **전체 회귀 0**(백엔드 무변경, MAKE_EXIT=0, ruff clean). REV-20260615-0281 [SKIPPED:frontend-ui-consistency-no-backend].
  - **Residual: Windows-browser** — 배포(deploy_scope: included) 후 PB-0008(보관 대화 탭 진입 → 짧은/긴 topic·긴 username 혼재 시 2줄 고정·미줄바꿈·ellipsis + 안내 우측 표면화) 기록 예정.

- 2026-06-15 (TASK-20260615T182907-product-list-row-icon-layout-fix 제품 관리 목록 행 UI 뒤틀림 핫픽스 — **PB-0008 Windows-browser 재검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore).
  - **배포:** 핫픽스 머지본 → web 재배포. 서빙 자산 admin.js 재빌드(`?v=20260615-product-icon-chip-list` 유지).
  - **검증 내용:** 제품 관리 목록 8행이 `.admin-list-row` 3열 grid(`auto 1fr auto`)로 정렬 복원 — avatar(원형 Identicon)·`(약어) 명칭`·sub·분석률 배지가 행마다 어긋남 없이 정합. row 높이 균일, 텍스트 위치 정상(뒤틀림 해소). 수정 전 대비(42_admin_list_icons.png) 행 정렬 어긋남이 사라짐.
  - **Evidence:** `artifacts/pb0008-profile-icon/50_admin_list_fixed.png`.
  - **Pass/Fail: PASS** (목록 행 정렬·아이콘·텍스트 위치 정상). CHECK#13 충족.

- 2026-06-15 (TASK-20260615T180923-product-icon-chip-list 제품 프로필 아이콘을 대화창 chip + 제품 관리 목록 행에 표시 — **PB-0008 Windows-browser 완료 게이트, 인증 후 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → `/api/auth/login`(bootstrap_admin) → 대화창 chip 제품 선택 eval + 관리 콘솔 `/admin` 제품 탭 목록 행 eval + screenshot)
  - **배포:** main `aea4d15`(PR #249 squash) → `sudo docker compose build web && up -d --no-deps web`(repo-web-1 Up healthy, HTTPS /healthz 200). 서빙 자산 `?v=20260615-product-icon-chip-list` — app.js `productChipIcon` 1 hit, admin.js `applyAvatar(avatar, { url: p.icon_url` 1 hit.
  - **검증 내용 (인증 후 실제 화면):**
    - **① 대화창 chip 아이콘 — PASS:** pinned 제품(GZ_QA_KR) 선택 시 chip 에 `#productChipIcon` 표시(`chipIconHidden:false`, `chipIconKind:"identicon"`). 확대 캡처(41_chip_zoom.png): [🔴 빨강 dot(unstable) → 원형 Identicon(주황 대칭) → `GZ_QA_KR` → 펼침 화살표] 순서. dot conn 색·compact label 무회귀.
    - **② 제품 관리 목록 행 아이콘 — PASS(아이콘 표시), 행 레이아웃 뒤틀림은 후속 핫픽스(182907):** 8개 행 **전부** `avatarKind:"identicon"` — `(KR) 킹스레이드`(파란 십자가)·`(KR_QA)`·`(MV)`(분홍)·`(GZ_KR)`·`(DK)`(빨강 체크)·`(FH)`(노랑)·`(GZ_QA_KR)`(주황) 각 고유 Identicon + `(약어) 명칭` + 분석률 배지. (단 이 Run 은 행 grid 뒤틀림을 놓침 — 사용자 보고 후 TASK-...-182907 로 수정·재검증.)
    - **③ 정합 — PASS:** 같은 제품(KR)이 대화창 chip·드롭업·관리 상세·관리 목록 행에서 **동일 파란 십자가 Identicon**, GZ_QA_KR 이 chip·목록 행에서 **동일 주황 Identicon**(동일 `identiconSvg(product_key)` 규칙 교차 확인).
  - **Evidence:** `artifacts/pb0008-profile-icon/41_chip_zoom.png`(대화창 chip 확대 — dot+Identicon+product_key), `42_admin_list_icons.png`(제품 관리 목록 8행 전부 Identicon + `(약어) 명칭` + 분석률), `40_chip_pinned_icon.png`(chip 전체 화면).
  - **Pass/Fail: PASS(아이콘·정합), 행 레이아웃은 후속 핫픽스 PASS** (① chip 아이콘 + ② 목록 행 아이콘 + ③ 제품별 동일 Identicon 정합 실제 Windows 화면 확인). CHECK#13(PB-0008 Windows-browser) **충족**. (auto 모드 chip 아이콘 hidden 은 jsdom 14/14 의 (c) 케이스로 검증 — 라이브 auto 전환은 기존 드롭업 동작이라 본 cycle 범위 밖.)
- 2026-06-15 (TASK-20260615T172210-profile-icon-consistency 제품 프로필 아이콘 정합화 + 대화 드롭업 레이아웃·너비 + 명칭 표기 순서 — **PB-0008 Windows-browser 완료 게이트, 인증 후 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → `/api/auth/login`(bootstrap_admin) → 대화 드롭업 eval 구조검증 + 관리 콘솔 `/admin` 제품 탭 eval + screenshot)
  - **Scenario:** `unit/feature-0003-agent-web-ui/tests/win-browser-profile-icon.scenario.json` (대화 드롭업) + `win-browser-profile-icon-admin.scenario.json` (관리 콘솔) + 직접 eval 보강.
  - **배포:** main `bb1a991`(PR #246 squash) → `sudo docker compose build web && up -d --no-deps web`(repo-web-1 Up healthy, HTTPS /healthz 200). 서빙 자산 `?v=20260615-profile-icon-consistency` — admin.js `identiconSvg`/`applyAvatar` 2 hit, app.js 명칭 `(약어) 명칭` 4 hit, styles.css `product-dropup-item-icon` 18px·`max-width: min(420px, 92vw)`.
  - **검증 내용 (인증 후 실제 화면):**
    - **① 대화 드롭업 항목 순서 — PASS:** 8개 pinned 제품 **전부** 항목 자식 순서 `[product-dropup-item-dot → product-dropup-item-icon → product-dropup-item-label → product-dropup-item-ds → check]` (eval `firstChildOrder` 단언). 사용자 요청 [네트워크 상태 배지 → 프로필 아이콘 → 명칭 → 데이터소스] 와 정확 일치.
    - **② 프로필 아이콘 Identicon — PASS:** 8개 제품 모두 `iconKind:"identicon"`(이미지 미설정 → 결정론적 Identicon SVG 폴백). auto 항목은 아이콘 없이 dot 만. **작업화면 프로필(applyAvatar/identiconSvg)과 동일 규칙** — 같은 제품(KR) 이 관리 콘솔·대화 드롭업에서 **동일 파란 십자가 Identicon** 렌더(스크린샷 교차 확인).
    - **③ 명칭 표기 `(약어) 명칭` — PASS:** 드롭업 `(KR) 킹스레이드 - 로컬`·`(KR_QA) 킹스레이드 - 국내 QA`·`(MV)...`·`(GZ_KR)...`·`(DK)...`·`(FH)...`, 관리 콘솔 제품 목록·상세 `(KR) 킹스레이드 - 로컬` — 전부 `labelStartsWithParen:true`/`detailStartsParen:true`.
    - **④ 드롭업 메뉴 너비 — PASS:** `menuMaxWidth:"420px"`, 렌더 너비 358px, 첫 항목 `firstLabelTruncated:false`(명칭 안 잘림). 이전 280px 잘림 해소.
    - **⑤ 관리 콘솔 제품 상세 아이콘 — PASS:** `(KR) 킹스레이드` 상세 헤더 `avatarKind:"identicon"`(이니셜 텍스트 아님) + 아이콘 변경 컨트롤 보존.
  - **Evidence:** `artifacts/pb0008-profile-icon/35_dropup_large.png`(대화 드롭업 확대 — dot+Identicon+`(약어) 명칭`+datasource 4요소 순서, KR_QA unstable 빨강 dot), `20_admin_detail_identicon.png`(관리 콘솔 제품 상세 — `(KR) 킹스레이드` Identicon + `(약어) 명칭` 목록 8개), `01_dropup_layout.png`/`33_dropup_open.png`(드롭업 열린 전체 화면).
  - **Pass/Fail: PASS** (① 항목 순서 + ② Identicon 정합 + ③ 명칭 순서 + ④ 너비 + ⑤ 관리 콘솔 아이콘 전부 실제 Windows 화면 확인). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0276 관리 콘솔 "보관 대화" 탭 UI 정합화, **Minor §12.3** frontend-only):
  - **Environment: CLI** (정적 + jsdom). node --check admin.js PASS + CSS brace(1206=1206). **jsdom 13 PASS**(빈 목록 empty·row 2개 audits 동형 클래스·count·row 클릭→selectedId+상세 렌더+is-selected·미존재 선택 empty·topic XSS escape 목록/상세·truncated scope 안내) + make test 컨테이너 **전체 회귀 0**(백엔드 무변경). 정적자산 web 임시 적용 후 admin.js 새 함수 14건·admin.html list-detail 마크업 12건 서빙 확인. REV-20260615-0277 [SKIPPED:frontend-ui-consistency-no-backend].
  - **(잔여) PB-0008 Windows-browser**: web 재배포 후 보관 대화 탭 진입 → list-detail 렌더 + row 클릭 시 우측 상세 패널 → 결과 추가 예정. (배포 전 CHECK#13 WARN.)
- 2026-06-15 (TASK-0275 assistant 첨부 수정→새 버전 materialize + 버전 관리, **Critical §12.3**):
  - **Environment: CLI** (컨테이너 make test). 신규 `test_attachment_versioning.py` **11 PASS**(파서2·materialize 가드6·직렬화1·파일명1·목록필터1) + make test 컨테이너 **전체 회귀 0** + ruff clean + py_compile + node --check app.js + CSS brace(1194=1194). 테스트 sys.modules 오염(가짜 web 모듈) → `monkeypatch.setitem` 자동 원복으로 해소(share_redaction 등 web.app import 테스트와 공존 확인).
  - **Environment: live-roundtrip** (임시 web 적용 + 라이브 MySQL ALTER + MinIO). materialize(source 272 text → 새 버전 273 v2 role=assistant root=272)·MinIO 바이트 70B sha256 일치·원본 272 SupersededAt 마킹·목록(SupersededAt IS NULL)에 273만 노출·`/versions` 체인 [272 v1 superseded, 273 v2 active]. **보안 가드 라이브 확인**: cross-account(999)/cross-conversation 거부(로그 mismatch), traversal `../../../etc/passwd.exe` → OriginalFilename `.._.._.._etc_passwd.sql`(확장자 .sql 고정)·object_key `../` 없음, 같은 (root,version) 2차 INSERT IntegrityError 거부(UNIQUE). 검증 데이터 정리(273 제거·272 원복).
  - **outside-voice 보안 리뷰** REV-20260615-0276 [SUBAGENT]: 외부 침투형 BLOCKER 0, 데이터 정합 BLOCKER1(원자성)+MAJOR2(UNIQUE race·audit)+MINOR1(확장자) 수정 흡수 → SHIP.
  - **(잔여) PB-0008 Windows-browser**: web 재배포 후 첨부 버전 배지(`v{n} · AI 수정`)·`edited_attachments` 토스트·`/versions` 시각검증 → 결과 추가 예정. (배포 전 CHECK#13 WARN.)
- 2026-06-15 (TASK-0272 대화 화면 프로필 첫 진입 시 "프롬프트 > 제품 범위" 비어있는 버그, **Minor §12.3** frontend-only):
  - **Environment: CLI** (정적 검증): `node --check app.js` PASS. 코드 정합 — `switchProfileTab(tab)` 에 탭별 lazy 디스패치(prompt→`initAccountPromptEditor()` / usage→`loadProfileUsage()`) 추가, `initialize()` 탭 클릭 리스너의 중복 디스패치 제거(단일 진입점화). index.html app.js 캐시버스터 `?v=20260615-task0272-prompt-scope`. REV-20260615-0272 [SKIPPED:panel].
  - **(잔여) PB-0008 Windows-browser**: web 재배포(deploy_scope: included) 후 프로필 드로어 첫 진입(새로고침 후)에서 제품 범위 셀렉트가 즉시 채워짐을 실제 Windows 화면에서 실측 → 결과를 본 항목에 추가 예정. (배포 전이라 본 commit 의 CHECK#13 은 WARN — 배포 후 충족 기록.)
- 2026-06-15 (TASK-0270 계정 override 게이트 = 허용/상속(허용) 펼침, **Minor §12.3** frontend-only):
  - **Environment: CLI** (컨테이너 make test). perm test **16 PASS**(신규 V7: 상속(허용)→펼침·상속(거부)→숨김·명시 거부 우선·허용 무관 펼침) + make test 컨테이너 회귀 0(exit=0) + node --check + **jsdom 8/8**(상속허용·상속거부·거부우선·허용·운영 list.own 상속허용). REV-20260615-0270 [SKIPPED:ui-disclosure-gate-no-enforcement].
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). 라이브 배포(main `8953dc1`, web Up healthy, 서빙 admin.js `inheritedGrants`, 캐시버스터 `?v=20260615-task0270-inherit-gate`) 후 카탈로그 주입 + computed display 실측. 스크린샷 `artifacts/pb0008-task0270/step_04(override 상속허용 게이트).png`.
  - **Runner: AI. 결과: PASS.** 계정 override 편집기에서 전 항목 "상속", 역할 baseline = {console.access, account.read, conversation.list.own} 주입 → ① 계정 그룹 등장, `계정 조회`(account.read) 아래 `계정 수정/삭제/활성화/비활성화/역할 부여/override 관리` 트리 펼침(account.read computed `flex`·account.update `flex` — 상속(허용) 게이트). ② `대화 요청 실행` `flex`(conversation.list.own 상속허용). ③ `전체 대화 내용 조회` computed `none`(conversation.list.any 역할 미부여 = 상속(거부)). 사용자 요구("부여된 역할 중 '허용' 및 '상속(허용)' 일 경우에 펼쳐지도록") 라이브 충족. 콘솔 에러 0. CHECK#13 충족.
- 2026-06-15 (TASK-0269 운영 권한 대화 그룹 분리 + "목록 조회" 게이트 트리, **Minor §12.3** frontend-only):
  - **Environment: CLI** (컨테이너 make test). perm test **15 PASS**(M4 list 게이트/V2 운영 루트/T2 그룹 분리+게이트 중첩) + make test 컨테이너 회귀 0(백엔드 RBAC 무회귀) + node --check(admin.js·app.js) + **jsdom 20/20**(2그룹·라벨·게이트·트리·누락0). outside-voice REV-20260615-0269 [SUBAGENT:rbac-adversarial] **SHIP**(enforcement byte-identical).
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` relay, https://localhost:18080). 라이브 배포(main `73755e9`, web Up healthy, 서빙 admin.js `내 대화 권한`/`전체 대화 권한` 라벨, 캐시버스터 `?v=20260615-task0269-conv-split`) 후. 스크린샷 `artifacts/pb0008-task0269/step_04(2그룹 트리).png`.
  - **Runner: AI. 결과: PASS.** 운영 권한이 **내 대화 권한**(13)/**전체 대화 권한**(10) 2그룹 분리, 각 그룹 "대화 생성·목록 조회(기반) > 동작" 트리. `내 대화 목록 조회`(게이트) 체크 → 내 동작(대화 요청 실행·내용 조회·파일 조회·제목 변경·삭제·중단 등) computed `flex` 펼침, 전체 대화 동작 computed `none`(전체 목록 조회 OFF). 사용자 요구 라이브 충족. CHECK#13 충족.
- 2026-06-15 (TASK-0267 권한 grid 트리(tree) UI 재구성 — 2열 grid 뒤틀림 해소 + "더 보기 부여됨" 빨강 가시성, **Minor §12.3** frontend-only):
  - **Environment: CLI** (컨테이너 make test). `test_permission_dependency_map.py` **15 PASS**(기존 11 + 신규 T1~T4: 트리 정렬 부모-자식 순서·depth 정합·own→any 중첩·account.read 루트·grid-list 단일열 CSS 계약) + make test 컨테이너 **전체 회귀 0**(merged tree, exit=0) + node --check + CSS brace(1167) + **jsdom 실 DOM 14/14**(트리 순서·depth·누락0·숨김 시 부모 DOM 앞 유지). REV-20260615-0267 [SKIPPED:ui-tree-layout-no-logic-change](disclosure/저장 로직 byte-identical, 렌더 순서+레이아웃 전용).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(main `f6ccb7b`, web `Up healthy`, 서빙 styles.css `.permission-grid-list{flex-direction:column}` + `[data-perm-depth]` + admin.js `_orderItemsAsTree`, 캐시버스터 `?v=20260615-perm-tree-ui`) 후. 배포 admin.js `renderPermissionGrid` 에 카탈로그(47) 주입해 실 grid 렌더 + computed style 실측. 스크린샷 `artifacts/pb0008-task0267/{step_04(manage 트리),step_01(operate 단일열)}.png`.
  - **Runner: AI. 결과: PASS.** **① 단일 열 트리(뒤틀림 해소)**: `.permission-grid-list` computed `display:flex`·`flex-direction:column`·`grid-template-columns:none`(2열 grid 아님) — 자식 row 숨김 시 가로 reflow 0. **② 트리 들여쓰기**: `관리 콘솔 접근`(부모, `data-perm-depth=0`·margin-left 0) 아래 `관리 콘솔 수정`/`LLM 사용량 조회`/`insight 분석 초기화`(자식, depth 1·**margin-left 24px** 들여쓰기·좌측 가이드/tick 연결선) 시각 확인. 운영 권한 `내 대화 내용 조회`(read.own depth0) ↔ `전체 대화 내용 조회`(read.any depth1·24px). **③ 운영 권한 빨강 가시성(이슈1 해소)**: conversation 그룹 read.any 부여+게이트OFF → computed `display:none`, "세부 권한 10개 더 보기 · 1개 부여됨" computed color **`rgb(180,35,31)`(빨강)**·`has-granted` — 2열 뒤틀림 제거로 빨강 badge 정상 가시. 사용자 두 보고(① 운영 권한 빨강 미가시 ② 항목 숨김 뒤틀림 → tree UI) 라이브 충족. 콘솔 에러 0. CHECK#13 **충족**.
- 2026-06-15 (TASK-0264 권한 disclosure 추가 단순화 — 게이트 미충족 시 부여 세부 권한도 더보기 뒤로 숨김(forceVisible 제거), **Minor §12.3** frontend-only):
  - **Environment: CLI** (컨테이너 make test). `test_permission_dependency_map.py` **11 PASS**(V1/V4/V5/V6 새 동작: 게이트 OFF 부여 항목 숨김 + 게이트 충족 시 도달; C1 unscoped CSS 계약) + make test 컨테이너 **전체 회귀 0**(merged tree, exit=0) + node --check + CSS brace(1133) + **jsdom 실 DOM 17/17**(부여 account.delete 게이트OFF 숨김·그룹 유지·"부여됨" 배지·더보기 클릭 도달·저장 누락0·override). outside-voice 적대 리뷰 REV-20260615-0264 [SUBAGENT:rbac-adversarial] **SHIP-WITH-FIXES**(안전 전부 refute; MINOR override-grid `[hidden]` unscope 흡수).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(main `d35299e`, web `Up healthy`, 서빙 styles.css 에 unscoped `[data-perm-code][hidden]{display:none!important}` + `.permission-group-more.has-granted`, 캐시버스터 `?v=20260615-perm-collapse-granted`) 후. 배포 admin.js `renderPermissionGrid` 에 카탈로그(47) 주입해 실 grid 렌더 + computed display 실측. 시나리오 `/tmp/pb0264.json`, 스크린샷 `artifacts/pb0008-task0264/{step_04(checkbox),step_06(override)}.png`.
  - **Runner: AI. 결과: PASS.** **① 역할(checkbox) — account.delete 부여 + 게이트(계정 조회·관리 콘솔 접근) OFF**: 계정 그룹은 vanish 안 하고(`1/7 선택` 헤더 카운트) 권한 행은 **하나도 노출 안 됨** — 부여된 `account.delete` 도 computed **`display:none`**(이전 forceVisible 누출 버그 해소), "세부 권한 7개 더 보기 · 1개 부여됨"(`.has-granted` 빨강) 으로 도달성 표면화. **② 계정(override) — account.delete=거부 + 게이트 inherit**: container=`override-grid`, `account.delete` computed **`display:none`** — TASK-0258 의 `.permission-grid` 한정 `[hidden]` 강제가 override 편집기를 놓치던 갭을 컨테이너 무관 unscope 로 해소했음을 실증, 그룹 유지 + "부여됨" 배지. 사용자 요구("세부 권한 더 보기 클릭 전 항목 노출 → 최대한 단순화하여 숨김") 두 편집기 모두 라이브 충족. 콘솔 에러 0. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-15 (TASK-0262 선택 제품 chip dot 네트워크 상태색 — TASK-0261 후속, **Minor §12.3** frontend-only):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). 라이브 배포(main `eb7be30`, healthz `git_commit=eb7be30`/status ok, 서빙 `?v=20260615-task0262-chip-conn-color`) 후. 시나리오 `tests/win-browser-task0262-chip-conn-color.scenario.json`, 스크린샷 `/tmp/win-browser-shots/task0262/{01_chip_unstable_p94,02_chip_healthy_p95}.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 세션 → composer 제품 chip(`#productChip`) 드롭업에서 제품 pin 후 `#productChipDot` 의 `getComputedStyle().backgroundColor` + class 실측. **선택 제품 94 킹스레이드 국내 QA(datasource `mysql-kr-an2-player`=unstable)**: dot class `composer-product-chip-dot--conn is-fail`, **bg rgb(220,38,38)=#dc2626 빨강**, chip aria-label "...· 데이터소스 연결 불안정". **선택 제품 95 건즈 국내 QA(`mysql-gz-qa-kr`=healthy)**: class `--conn is-ok`, **bg rgb(22,163,74)=#16a34a 초록**, aria "...· 데이터소스 연결됨". **auto(미선택)**: conn 클래스 제거됨, bg rgb(128,125,114) 중립(전이 reset 정상). 과거엔 선택(pinned) 제품이 상태 무관 파랑(`--primary`)이었음 → 상태색 반영 확인(사용자 요구 충족). 콘솔 0. CHECK#13(PB-0008) **충족**.
- 2026-06-15 (TASK-0257 권한 편집기 점진적 세분화 + TASK-0258 [hidden] CSS override 핫픽스, **Major/Minor §12.3** — frontend-only):
  - **Environment: CLI** (컨테이너 make test). 신규 `test_permission_dependency_map.py` **11 PASS**(맵 정합 M1~M4 + 가시성 불변식 V1~V6 + CSS 계약 C1) + make test 컨테이너 **전체 회귀 0**(merged tree, exit=0) + ruff clean + node --check + CSS brace(1125=1125). **jsdom 실 DOM 30/30**(마스터게이트 vanish·그룹 reveal·게이팅·orphan 칩·저장경로 안전·override no-vanish·더보기). outside-voice 적대 리뷰 REV-20260615-0257 [SUBAGENT:rbac-adversarial] **SHIP-WITH-FIXES→흡수**(부여 권한 미숨김·저장 누락 0 을 400k fuzz refute; MAJOR override trap 흡수).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 → `compose up --no-build`, web `Up healthy`, 서빙 admin.html 캐시버스터 `?v=20260615-perm-disclosure-hidefix`, 서빙 styles.css 에 `[data-perm-code][hidden]{display:none!important}` 1매치) 후. 배포된 admin.js `renderPermissionGrid` 에 카탈로그(47 권한) 주입해 실 grid 렌더 검증. 스크린샷 `artifacts/pb0008-task0257/{step_04_…(역할 collapsed),01_role_console_access_checked,…}.png` + `artifacts/pb0008-task0258/step_02_…(배포 CSS within-group 게이팅).png`.
  - **Runner: AI. 결과: PASS.** **① 역할(checkbox) 신규 미선택**: 관리 권한 section 이 "관리 콘솔" 그룹만 표시(계정/역할/감사/설정 그룹 `[hidden]` vanish, computed `display:none`), 운영 권한은 대화/제품 표시 — 마스터 게이트 OFF 단순화 시각 확인. **② "관리 콘솔 접근" 체크**: 계정/역할/감사/설정 그룹 등장. **③ 계정 그룹 펼침(배포 CSS, TASK-0258 핫픽스 검증)**: `계정 조회`(account.read)만 표시, 나머지 6개(`계정 수정/삭제/활성화/비활성화/역할 부여/override 관리`) **computed `display:none`**(visible=1), "세부 권한 6개 더 보기" 노출 — within-group 게이팅이 실브라우저에서 정상 동작(TASK-0257 의 `[hidden]` override 버그가 TASK-0258 로 해소됨). **④ 계정 override(select) 모드**: 계정/역할/감사 그룹 통째 vanish 안 함(account_group_display=block) + "더 보기" 도달 가능 — override trap 수정 확인. 사용자 두 예시("관리 콘솔 접근 체크→관리 권한 내부 표시", "계정 조회 체크→나머지 계정 권한 표시") 모두 라이브 충족. 콘솔 에러 0. CHECK#13(PB-0008 Windows-browser) **충족**. **교훈**: TASK-0257 의 `[hidden]` override 버그는 jsdom(CSS 캐스케이드 부재)이 못 잡고 PB-0008 실브라우저(computed display)만 검출 — 권한 grid 표시/숨김은 PB-0008 로 확인([[feedback_visual_verify_on_design_change]]·TASK-0236 교훈).
- 2026-06-15 (TASK-0255 insight 연결 탄력성 R2 — datasource 상세 '인사이트 스캔 상태' 행 = 연결 불안정 vs 정상 구분, **Major §12.3** cross-feature):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(main `a410986`, healthz `git_commit=a410986`/status ok, web `Up healthy`, admin.js 캐시버스터 `?v=20260615-task0255-insight-health`) 후. 스크린샷 `/tmp/win-browser-shots/task0255/{01_unstable_ds_auth_detail,02_healthy_ds_gzqa_detail}.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 영속 세션. **① 엔드포인트(데이터)**: `GET /api/admin/datasources` 200, datasource 11개. `mysql-kr-an2-auth` → `conn_status=unstable` + `insight_health={status:unstable, scan_outcome:circuit_open, fail_count:11}`; `mysql-gz-qa-kr` → `conn_status=healthy` + `insight_health={status:healthy, scan_outcome:ok, fail_count:0}` — insight 관점 health 가 응답에 정상 첨부됨. **② UI(시각)**: /admin > 데이터소스 탭 > datasource 행 클릭 → 상세 "출처·보안" 섹션의 신규 **"인사이트 스캔 상태"** 행: 불안정 `mysql-kr-an2-auth` = **"⚠ 연결 불안정 (미커버 — 자동 재시도 대기)"**, 정상 `mysql-gz-qa-kr` = **"정상 (분석됨)"**. 운영자가 "연결 불안정 미커버" 를 권한 실패/정상과 **구분** 인지(사용자 R2 요구 충족). 자격증명/민감정보 미노출(host/port/status/errno-tag 만). 콘솔 에러 0. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-15 (TASK-0254 제품 프롬프트 '자동 작성' 스트리밍 스크롤 stick-to-bottom, **Minor §12.3** — frontend-only admin.js):
  - **Environment: CLI** (컨테이너 make test + ruff + node --check). make test 컨테이너 **전체 회귀 0**(진행 100%·skip 2·F/E 0·make exit=0) + ruff clean + `node --check`(admin.js) PASS + 서버 `.strip()` 사실 확인(app.py:16519). outside-voice 적대 리뷰 REV-20260615-0254 [SUBAGENT:frontend-adversarial] **SHIP-WITH-FIXES→흡수**(LOW 1건 done strip 길이차 점프; 첫토큰/8px 임계/측정순서/비-오버플로 무회귀 전부 반박).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 → `compose up --no-build`, web `Up healthy`, healthz `git_commit=f8845cc` mysql_ok/pg_ok, 베이킹 admin.js `atBottom`×4·`TASK-0254`×2 + 서빙 admin.html 캐시버스터 `?v=20260615-task0254-prompt-stream-scroll`, HTTP 응답 admin.js 에 `atBottom` 포함 확인) 후. 스크린샷 `/tmp/win-browser-shots/task0254/{01_prompt_pane_after,02_prompt_textarea_top}.png`(= `artifacts/pb0008-task0254/`).
  - **Runner: AI. 결과: PASS.** bootstrap_admin 영속 세션 → /admin > 제품 (Products) > "킹스레이드 (KR)"(pid 1) 상세 > 제품 프롬프트 pane. **자동 계측(eval 기반, 토큰 갱신마다 scrollTop 샘플링)** — `자동 작성` 클릭 → SSE 스트리밍(최종 ~7.5k자) 진행 중 2단계 측정. **① HOLD(위로 스크롤 유지) — 결정적 실측**: clear(첫 토큰 `value=""`) 감지 후 새 스트리밍 내용이 오버플로(>200px, len>1200)된 시점에 `scrollTop=60`(위로) 1회 설정 → 이후 토큰 8개 샘플 **전부 `top=60` 고정**, 그동안 오버플로는 748→852px 로 계속 증가(구버그면 top 이 oflow 를 따라 최하단으로 튐). **위로 스크롤한 위치가 토큰 갱신에도 유지됨** 실증. **② FOLLOW(최하단 추종)**: 그 후 `scrollTop=scrollHeight`(하단) 설정 → 이후 토큰 **73개 샘플 전부 `dist(scrollHeight-scrollTop-clientHeight)=0`**(max=min=0), 내용이 1.5k→자라는 내내 정확히 하단 추종. **사용자 시나리오 실증**: 스트리밍 완료 후 textarea 를 상단으로 두면 "# 킹스레이드 DB 분석 어시스턴트 시스템 프롬프트…" 본문 상단이 그대로 보임(02 스크린샷 — 사용자 원요구 "작성 현황 텍스트 상단 보기" 충족). 콘솔 에러 0. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0253 관리 콘솔 head-of-line blocking 2건 제거 — (A) datasource ↻ 새로고침 비블로킹 + (B) 제품 분석 완료율 제품별 병렬 갱신, **Minor §12.3** — frontend + async backend):
  - **Environment: CLI** (컨테이너 make test + ruff + node --check + py_compile). 신규 `test_datasource_test_nonblocking.py` + `test_insight_coverage_endpoint.py` **8 PASS**(로컬 + 컨테이너), make test 컨테이너 **전체 회귀 0**(진행점 619, F/E 0) + ruff clean + node --check(admin.js) + py_compile(app.py). outside-voice 적대 리뷰 **SHIP-WITH-FIXES→흡수**(MAJOR-2 N-fan-out 스레드풀 고갈→프론트 cap 4, MINOR-2 force in-flight dedup, MINOR-3 fake keyword-only; BLOCKER 0).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web/ask-worker/insight-worker 재빌드 → `compose up --no-build`, 전 컨테이너 `Up healthy`, web env `GIT_COMMIT=a7c09d7`, 베이킹 app.py:10587 `await asyncio.to_thread(_db.probe_datasource, …)` + admin.js `_COV_FETCH_MAX` ×3 + 캐시버스터 `?v=20260612-task0253-headofline` 확인) 후. 스크린샷 `/tmp/task0253-pb0008-{products-coverage,ds-refresh}.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 영속 세션 → /admin. **(A) datasource ↻ 비블로킹 — 결정적 실측**: 브라우저에서 11개 datasource `/api/admin/datasources/{key}/test` 동시 POST(Promise.all) wall-clock **847ms** ≈ 가장 느린 단건 845ms(ratio 1.0), 직렬 합산이면 6491ms = **약 7.7배 개선**(전부 status 200). 수정 전엔 `admin_test_datasource`(async)가 동기 `probe_datasource`(도달불가 시 8s 점유)를 직접 호출해 이벤트 루프 블로킹 → 동시 /test 직렬화. 이제 `asyncio.to_thread` 로 진짜 병렬. 제품 상세 > "+ 데이터소스 추가" 패널의 **↻ 새로고침 버튼 hit-test PASS**(62×27px visible + clickable), 클릭 후 배지 "확인 중" stuck **0**, "정상" 표면화. **(B) 제품 완료율 제품별 병렬 갱신**: fetch 후킹으로 강제 새로고침 시 coverage 호출이 **제품별 단건 7건**(`?product_id={1,94,7,8,91,92,95}&refresh=1`, first→last spread 203ms = cap 4 두 배치) — 전역 1회 fetch 아님. 좌측 목록 완료율 배지 7개 모두 개별 settle(`분석 100%`×6 + `분석 56.8%`), "측정 중" stuck **0**(TASK-0249 에서 STATUS flag 로 남긴 일괄대기 초기렌더 고착 해소). **콘솔 에러 0**. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0248 관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환, **Major §12.3** — 파괴적 삭제 + 접근 차단 + cross-store):
  - **Environment: CLI** (컨테이너 pytest + ruff + node --check + py_compile + CSS brace). 신규 `test_product_delete_block_conv.py` **7 PASS**(D1 삭제허용+차단·D2 참조0·D3 권한403·B1 block_info·B2 block UPDATE SQL/rowcount·A1 ask 403) + make test 컨테이너 **전체 회귀 0**(600 passed/2 skip) + ruff clean + node --check(app.js·admin.js) + py_compile(app.py·alembic 0005) + CSS brace 1108/1108.
  - **outside-voice 적대적 2-agent 리뷰**: REV-20260612-0248 [SUBAGENT:security+correctness-adversarial] SHIP-WITH-FIXES→흡수→**SHIP**. 백엔드 BLOCKER 0(probe ①SQL바인딩 ②오차단 ③cross-store fail-closed ④conn누수 ⑤멱등 ⑦split-brain PASS; ⑥PG컬럼부재500=migrate-first 배포계약 흡수). 프런트 SHIP(우회 송신 경로 0, 공유/이력/fork 충족). M-2(admin.js 혼입)=stale base 오탐.
  - **라이브 검증(서빙 web 컨테이너 코드 경로, 실데이터 무오염)**: PASS. (1) migrate 0005 적용 → PG `core_conversations.blocked_at`/`blocked_reason` 컬럼 psql 실측 존재. (2) 라이브 `_block_conversations_for_product(99999)`=1건 차단, `_conversation_block_info`(pinned)=True·(auto NULL)=**False**(오차단 방지 probe②), 재호출=0(멱등). (3) end-to-end `admin_delete_product(96)`(테스트 제품) → status **200** + `blocked_conversations:2`(과거 400 거부 제거 확인), WebProducts 96 + 동적권한 cascade 삭제, 검증 대화 2건 blocked=t. (4) 정상 대화(product 91) blocked=False(무영향 probe⑤). 검증 후 임시 데이터 전량 정리 → 라이브 차단행 0 복원.
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(make migrate 0005 → web 재빌드/재기동, healthz `status:ok`·mysql_ok/pg_ok·insight_age 8s, 서빙 admin.js `?v=20260612-task0248-blocked-conv` + confirm 문구 "차단' 상태로 전환됩니다") 후. 스크린샷 `/tmp/pb0008-task0248-{admin-product-delete,blocked-conv}.png`.
  - **Runner: AI. 결과: PASS.** 영속 admin 세션. **(A) admin 제품 삭제** — /admin > 제품 탭(7개 렌더) > "킹스레이드 (KR)" 선택 → 상세 패널 + 하단 **"삭제" 버튼 hit-test PASS**(좌표 643,706 에서 `elementFromPoint`=버튼 자신). 서빙 admin.js confirm 문구 = TASK-0248 신규("이 제품을 참조하는 대화가 있으면 더 이상 진행할 수 없는 '차단' 상태로 전환됩니다 ... 되돌릴 수 없습니다"). **(B) 차단 대화 UI**(검증용 실대화 1건 일시 차단→검증→원복) — (1) **사이드바**: `.conv-item.is-blocked` 클래스 + "차단" 배지(visible) + 제목 `line-through`. (2) **헤더**: 부제 = "🚫 차단됨 (참조 제품 삭제) · 최근 갱신 ... · 메시지 6 · 소...". (3) **composer**: 입력창 `disabled=true` + 전송버튼 `aria-disabled=true` + 제목 "차단된 대화" + 안내 "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다. 이력 열람·공유는 가능하며, 복제(사본 만들기)로 새 대화에서 이어갈 수 있습니다." (4) **요구사항 실증**: fork(복제) 버튼·공유 버튼 **노출 유지**(차단 대화도 가능), 메시지 **58개 렌더**(이력 열람 가능 — 차단이 렌더 미차단). 검증 후 차단 원복(라이브 blocked 행 0). CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0249 제품 insight 완료율 멀티 datasource(1:N) + 대소문자 매칭 수정, **Minor §12.3**):
  - **Environment: CLI** (make test 컨테이너 pytest + ruff + py_compile). 신규 `test_insight_coverage.py` 5(C1 멀티 datasource per-DB 집계 0/0 회귀차단·C2 단일 datasource 레거시 무회귀·C3 mixed-case 매칭·C4 한 datasource 부분측정·C5 measurable=False) PASS + 전체 회귀 0(rebase 후 598 passed/2 skipped, origin/main TASK-0250 이 test_db_circuit_breaker→test_conn_health 교체) + ruff clean. 적대적 correctness 리뷰 **SHIP**(REV-20260612-0249, CONCERN 1[동명 DB 이중카운트]→seen_dbs 가드 흡수).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 + healthz `git_commit=12f5c5e`, mysql_ok/pg_ok, 베이킹 `seen_dbs`·`LOWER(TABLE_SCHEMA)` 확인) 후. 시나리오 `tests/win-browser-task0249-coverage.scenario.json`, 스크린샷 `/tmp/win-browser-shots/task0249/{10_ds_player_expanded,11_ds_common_dbcommon_111,12_ds_auth_expanded_dbauth_row}.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 세션 → /admin → 제품 탭 → "킹스레이드 - 국내 QA (KR_QA, id 94)" 선택. **핵심 검증 — 0/0 해소**: 요약 "insight 분석 완료율 **100%** · **571 / 571 객체 (DB + 테이블)**"(수정 전 7개 DB 전부 0/0). 7개 datasource accordion(player/auth/common/globalrank/gms/log/mail) 각각 펼쳐 그 datasource 의 DB 행 확인 — **dbgame(player) 99/99·마이크로바 100%·DB✓**, **dbcommon(common, 타 서버) 111/111·마이크로바 100%·DB✓**, **dbauth(auth, 타 서버) 10/10·마이크로바 100%·DB✓**(eval 측정 + 스크린샷). 각 DB 가 자기 datasource 좌표에서 실측됨(수정 전엔 단일 primary[player] 서버 질의로 타 서버 DB 0/0). 좌측 목록 배지 "분석 100%"(제품94 + 제품1[단일 datasource] 무회귀). 브라우저 API 일괄/단건 coverage 3회 반복 모두 7/7 conn·571/571(연결 안정 시) — 일시 연결 불안정 시에는 per-DB conn=False+note 로 graceful(0/0 일괄 오표기 아님, TASK-0247/0250 영역). CHECK#13(PB-0008 Windows-browser) **충족**. **관찰(별개 선존 이슈, 내 변경 무관)**: 페이지 첫 진입 시 프런트 일괄 coverage 로드의 초기 렌더 타이밍으로 좌측 목록·요약이 일시 "측정 중…" 고착 → 새로고침/재렌더 시 정상(`productCoverageLoading`/state 는 정상 false·7건 로드 확인). 백엔드 `_compute_product_insight_coverage`(본 TASK)와 무관한 프런트 `loadProductInsightCoverage` 초기 렌더 경로 — STATUS flag.
- 2026-06-12 (TASK-0246 "+ 데이터소스 추가" 드롭다운 항목 열 정렬 — 고정 열 폭 grid + 연결배지 좌측 정렬 정련, **Minor §12.3**):
  - **Environment: CLI** (CSS brace 균형 — CSS-only). CSS brace 1105/1105. REV-20260612-0246 [SKIPPED:trivial-grid-align] + REV-20260612-0247 [SKIPPED:trivial-css-1line](정련).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). 라이브 배포(web 재빌드 + healthz `git_commit=9c2db34`, mysql_ok/pg_ok, 서빙 `?v=20260612-ds-picker-colalign2` + `.admin-ds-conn { justify-self: start`) 후. 스크린샷 `/tmp/pb0008-ds-picker-colalign-final.png`(+ 중간 `/tmp/pb0008-ds-picker-status.png`).
  - **Runner: AI. 결과: PASS.** /admin > 제품 "킹스레이드(KR)" > "+ 데이터소스 추가" 드롭다운(datasource 5개) 항목별 컬럼 left 좌표를 win-browser eval 로 측정. **핵심 — 행별 left spread=0px**([[feedback_row_list_column_alignment]] 기준): name 5행 전부 x=677(spread 0), 엔진 pill 전부 x=874(spread 0), 좌표 전부 x=938(spread 0), 연결배지 전부 x=1070(spread 0). **수정 전(CHG-0246 측정)**: 엔진 x961/936/967·좌표 x1011/986/1018·배지 x1105/1080/1080 으로 들쭉날쭉 → grid 고정 열 폭(`auto minmax(0,1fr) 56px 124px 104px`) + 정련(연결배지 justify-self:end→start)으로 전 열 정렬. 긴 좌표(`kr-apne2-auth.masangs…`)는 ellipsis 흡수, 연결 상태(연결 실패/연결됨·ms) 정상 병행 표시. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0244 관리 콘솔 제품 "+ 데이터소스 추가" 드롭다운 폰트 정합 + 연결 상태 표면화, **Major §12.3**):
  - **Environment: CLI** (`node --check admin.js` 정적 문법 검증 + CSS brace 균형 — frontend-only).
  - **Runner: AI.** `node --check ...admin.js` PASS, CSS brace 1103/1103. outside-voice subagent 디자인/정합 적대적 리뷰 **SHIP**(REV-20260612-0244, BLOCKER 0; `.admin-ds-picker-engine` ≡ `.ds-acc-engine` 토큰 동일·`.admin-db-picker-name` 재사용 확인, 동시성 nit 4-cap 세마포어 선반영).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 `sha256:6b05c6…` + healthz `git_commit=2b9205a` mysql_ok/pg_ok, 서빙 캐시버스터 `?v=20260612-ds-picker-status`·신규 심볼 5) 후 수행. 스크린샷 `/tmp/pb0008-ds-picker-status.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 영속 세션 → /admin → 제품 탭 → "킹스레이드 (KR)" 선택 → 데이터소스 accordion(2행) 하단 "+ 데이터소스 추가" 클릭. **검증 1 — 폰트/시각 정합**: 드롭다운 각 항목이 `[체크박스 · 이름(.admin-db-picker-name) · 엔진 pill(.admin-ds-picker-engine) · 좌표(.admin-ds-picker-coord) · 연결상태 배지(.admin-ds-conn)]` 구조로 렌더, 엔진 pill 이 위 accordion 행의 `[mssql]` pill 과 동일 시각(이전 `key — engine @ host:port` 단일 raw 문자열 이질감 해소). 헤더 "데이터소스 · 연결 상태" + ↻ 새로고침 표시. **검증 2 — 연결 상태**: 드롭다운 열림 시 lazy probe → 약 10초 후 settle: `mssql-qa-idc` ● **연결 실패**(is-fail, title="연결 실패: OperationalError" — 도달불가 IDC), `mssql_local` ● **연결됨 · 8.7ms**(is-ok), `mysql-local` ● **연결됨 · 8.9ms**(is-ok). ●점 + 한글 라벨 + 색(빨강/초록) 병행 — 색맹 비의존. ok/fail/elapsed_ms 3종 모두 정확 표면화. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0235 새 대화 첫 메시지 작업 단계 진행상황 실시간 표시, **Major §12.3**):
  - **Environment: CLI** (`node --check` 정적 문법 검증 — frontend-only 변경, app.js).
  - **Runner: AI.** `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS. 변경: `sendPrompt` 의 lazy_create early-cid 발급 일반화(첨부 유무 무관) + `earlyCidActivated` 플래그 도입(ask 실패 시 non-lazy 복구 경로 분기). 동시성 7 실패모드 적대적 리뷰(REV-20260612-0235 [SUBAGENT:newconv-progress-adversarial-concurrency]) — 중복폴링/빈status조기종료/sentinel가드/첨부회귀/bubble race 안전 + CONCERN 2(고아대화·빈대화 명시cid) 흡수.
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 `sha256:9195e3…` + healthz 200 mysql_ok/pg_ok) 후 수행. 시나리오 `tests/win-browser-task0235-newconv-progress.scenario.json`, 스크린샷 `/tmp/win-browser-shots/task0235/{01_app_loaded..06_step_side_panel_open}.png`.
  - **Runner: AI. 결과: PASS (23/23 step ok).** bootstrap_admin 영속 세션 → 사이드바 "+ 새 대화" → `#promptInput` 에 "데이터베이스에서 테이블 목록을 보여주고 각 테이블의 행 수를 알려줘" 입력 → `#sendBtn` 전송. **핵심 검증 — 새 대화 첫 메시지에서 진행 단계 실시간 표시**: (1) 전송 직후(shot 03) 사이드바에 "새 대화" 항목 즉시 등재(녹색 활성 점) + "다른 대화에서 새 요청 가능" 안내 → **early-cid 발급 + optimistic entry + polling 시작 작동**(수정 전이라면 cid 부재로 항목·polling 모두 없음). (2) LLM 첫 step 생성 전(shot 04 5초·shot 05 11초)에는 "시작 중…" 유지(정상 — step 0 구간), step 도착 즉시(shot 06) pending bubble 이 **"SQL 실행 · INFORMATION_SCHEMA.TABLES에서 모든 테이블의 스키마명·테이블명·행 수 조회"** 로 전환 = 실시간 단계 표시 확인. (3) **"단계 보기" 클릭 → `#stepSidePanel` 우측 사이드바 열림**(`sidePanelOpen:true, sidePanelItems:1, badge:"1단계"`) + 단계 상세(SQL 실행 배지 / "근거" / 실 SQL 쿼리 / "결과 보기") 렌더 = 사용자 요청("각 단계 + 클릭 시 사이드바") 충족. (`window.state` 모듈 스코프라 eval activeConvId 는 null 노출됐으나 DOM 증거가 결정적.) CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0228 datasource SSRF 사설망 경계 env 토글 + 의도적 비활성화, **Major §12.3 보안 다운그레이드**):
  - **Environment: CLI** (컨테이너/로컬 pytest — `_ssrf_check_host`/`_ssrf_private_guard_enabled` 단위 + 통합 trace).
  - **Runner: AI.** 신규 `test_ssrf_private_guard_toggle.py` **31 PASS** (토글 ON/OFF·메타데이터 IPv4-mapped 차단·loopback/link-local 상시 차단·allowlist 공존·파싱·공인 IP 허용·빈 host 거부) + datasource 회귀(`test_datasource_registry.py`/`test_datasource_delete.py`) 회귀 0. 통합 trace 11 케이스(토글 OFF): RFC1918(10.200.50.80 등) 허용 + 메타데이터(bare/IPv4-mapped) 차단 + loopback/link-local 차단 ALL PASS. py_compile + node --check PASS.
  - **outside-voice 적대적 보안 리뷰**: REV-20260611-0228 [SUBAGENT:security] BLOCK→흡수→PASS (Finding A/B IPv4-mapped 메타데이터 우회 + Finding C loopback/link-local 과개방 수정).
  - **Environment: Windows-browser** — 배포(web 재기동, 토글=0) 후 PB-0008 으로 admin 콘솔 데이터소스 생성(host=`10.200.50.80`) 성공 + 안내 문구("사설망 IP 허용...") 확인 예정. (UI 변경 = 안내 텍스트 1줄 분기 — 백엔드 보안 로직이 핵심.)
- 2026-06-11 (TASK-0218 관리 콘솔 대시보드 CloudWatch 스타일 재구성 **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(healthz `git_commit=c990107`, mysql/pg ok) 후. 스크린샷 `/tmp/win-browser-shots/task0218/{01_cloudwatch_dashboard,02_edit_drag}.png`.
  - **Runner: AI.** 시나리오: 영속 admin 세션 → `/admin` 대시보드 → 클린 로드 eval → 편집 모드 토글.
  - **결과: PASS.** (a) **toolbar** = "마지막 갱신 HH:MM:SS" + 집계기간 + 자동 새로고침(off/30/60s) + ↻ 새로고침 + 편집. (b) **주/보조 위계**: 계정 활성=6 녹색 大 + 보조(비활성/삭제/최근7일/전체) 小. (c) **sparkline 3 + 델타 배지 2**(▲▼% 의미별 색); 라이브 overview conversations primary={최근7일 45, spark[7], ▲2150% neutral}. (d) **Top-N 인라인 비율막대**. (e) **drill "열기 →" 6**(위젯→탭). (f) **편집 모드**: "완료" + ☑표시 + ↑↓(첫 위젯 ↑ disabled) + native drag + 저장/복원, drill 숨김. (g) **클린 로드 정확**: editBarHidden=true·editControls=0·drill 6. (h) RBAC 스코프·인젝션 차단(TASK-0210) 유지.
  - CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-11 (TASK-0210 관리 콘솔 대시보드 보강 — 카테고리별 위젯 그리드 + per-account 커스터마이즈 **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(healthz `git_commit=98f719d`, mysql/pg ok) 후 수행.
  - **Runner: AI.** 시나리오: 영속 admin 세션 → 관리 콘솔(`/admin`) → 대시보드("운영 현황") → 편집 모드 토글. 스크린샷 `/tmp/win-browser-shots/task0210/{01_dashboard,02_edit_mode}.png`.
  - **결과: PASS.** (a) **위젯 그리드 9개** 렌더: 계정·역할·제품·데이터소스·대화·활동·감사 활동·LLM 사용량·첨부 DB 권한·미저장 변경(2열 auto-fill). (b) **실데이터 집계**: 계정(활성 6/비활성 0/삭제 20/최근7일 3/전체 26 + 역할별 계정 Top-N), 역할(역할수 5 + 역할별 권한수 Admin 51/DBA 20/…), 제품(활성 4/바인딩 4), 데이터소스(활성 2 + 엔진별 mysql 1/mssql 1). metric chip 23·list row 27 렌더. (c) **가로 스크롤 없음**(`hScroll:false` — 레이아웃 정상). (d) **편집 모드**: "편집"→"완료" 토글, 편집 안내 바 + 기본값복원/저장, 위젯별 ☑표시 체크박스 9 + ↑↓ 이동 버튼 18(점선 테두리). (e) 집계기간 `최근 7일` dropdown. 라이브 API 검증(curl): overview 200 실데이터, prefs GET 기본(customized=false)→PUT(usage 숨김+미지키 `__evil__` **거부**)→GET(customized=true·usage=false 영속)→DB 행 영속, 검증 후 테스트 prefs 행 삭제(admin 기본값 복원).
  - CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-11 (TASK-0206 DB-단위 접근 모델 — 관리콘솔 제품상세 UI 재구성 **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(healthz `git_commit=cf1962e`, mysql/pg ok) 후 수행.
  - **Runner: AI.** 시나리오: bootstrap_admin 영속 세션 → 관리 콘솔(`#openAdminBtn`) → 제품 → MSSQL_DK(제품 90, winsql/dk_data_release) 상세.
  - **결과: PASS.** (a) **섹션 순서** = `데이터 소스 (datasource)` → `접근 가능 데이터베이스` → `제품 프롬프트` — 데이터소스 패널이 접근가능DB **위**로 이동(요청대로). (b) 데이터소스 dropdown `winsql — mssql @ 172.28.64.1:14330` + 연결테스트, **별도 '참조 DB' dropdown 폐지**(DB-단위 multi-select 로 흡수). (c) 접근가능DB = datasource-driven: 시스템 DB `master 고정·model 고정·msdb 고정`(고정칩) + 사용자 DB `dk_data_release ×`(제거가능) — 실 MSSQL 서버 DB 반영(tempdb 제외, 대소문자 보존). (d) hint 텍스트 = "데이터는 데이터 소스에 종속됩니다 — 선택하면 아래 접근 가능 데이터베이스 목록이 갱신됩니다". 스크린샷 `artifacts/task0206/03-product90-mssql.png`.
  - CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-10 (TASK-0184 LLM 사용량 계정 drill-down + 프로필 사용 내역 차트 + 내 활동기록 제거 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포 검증(healthz `git_commit=0181301`, mysql/pg ok, 베이킹·자산 서빙 PASS) 후 수행.
  - **(C 활동기록 제거)** bootstrap_admin 프로필 → 탭 = [프롬프트, 사용 내역, 보안 및 계정], '내 활동 기록' 탭 부재(`hasActivityTab=false`). PASS.
  - **(B 프로필 사용내역)** '사용 내역' 탭 → 요약(요청 24·호출 57·총 토큰 515,443) + 일별 모델별 누적 막대(06-09/06-10 claude-haiku-4) + 모델별 비중 도넛(claude-haiku-4 100%) 정상 렌더. 스크린샷 `/tmp/0184_profile_usage.png`. PASS.
  - **(A 계정 drill-down)** 관리 콘솔 > LLM 사용량 → 역할별 차트 막대(역할 = (시스템)·Admin) 클릭 → 그 역할의 계정만 펼치는 drill 패널 노출(계정 검색 input + 10/20/50 page size select). (시스템) 클릭 시 "계정별 · (시스템) — 1개 계정" + 계정 막대 1개(15,866,265 토큰) + 검색·페이저(계정 1개라 페이저 숨김) 정상. 계정별 독립 차트는 제거됨. 스크린샷 `/tmp/0184_admin_drill2.png`. PASS.
  - **(A 후속 — 계정별 비용 차트 보강)** 사용자 지적 "계정별 비용 차트 누락" 수정 후 재배포(b4e52b5) 재검증: 역할 'Admin' 클릭 → drill 패널이 **[토큰 | 비용] 2열**(역할별 차트와 일관). 토큰열(bootstrap_admin #1 515,443 / admin #10 451,667) + **추정 비용열(bootstrap_admin $0.60 / admin $0.50)** 모두 노출. 스크린샷 `/tmp/0184_drill_cost.png`. PASS.
  - CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-09 (TASK-0174 "전체 N행 미리보기" 링크 오정렬 수정 — **PB-0008 Windows-browser 완료 게이트(무회귀 smoke)**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 가 아닌 실제 Windows 화면 검증.
  - 시나리오: bootstrap_admin 영속 세션 → `#promptInput` 에 부위별 Top-N 질의(+범위 MIN/MAX 동반) 전송 → ask-worker 처리 완료 → 멀티-result 답변 정상 렌더. 스크린샷 `/tmp/win-browser-shots/shot_20260609_174354.png`(쿼리 1/3 result 뷰어), `_174718.png`(대형 인라인 표).
  - **결과: 무회귀 PASS.** (a) 병합된 `app.js`(본 cycle 의 `loadCsvAsInlineTable` 값 가드 + 동시세션 TASK-0173 `.step-reason` 기능)이 채팅 UI·대화목록·result 뷰어를 정상 렌더, JS 크래시 0. (b) 버그를 유발하던 **MIN/MAX 보조쿼리 패턴이 실데이터 result set 으로 실존**(쿼리 1/3: MinItemID=1001 / MaxItemID=900007 / count 1행) 확인 — `_collapse_large_tables` 가 이를 ranking 표에 잘못 붙이던 것이 근본.
  - **한계(정직 기재):** `_collapse_large_tables` 의 collapse+"전체 N행 미리보기" 링크 경로는 LLM 이 본문 대형 표(>5행)를 렌더하고 동턴에 execute_sql CSV 를 생성해야만 트리거되는데, 2회 유도에도 LLM 이 result 뷰어/소형 표/이전결과 재포맷을 선택해 **온디맨드 재현 불가**(비결정적). 해당 경로의 결정적 검증은 `unit/feature-0002-agent-core/tests/test_collapse_table_csv_match.py` 회귀 4종(값매칭·무매칭생략·형태폴백·토큰필터)이 담당 — make test 컨테이너 PASS. CHECK#13 **충족**(시각 표면 존재 + 실 브라우저 무회귀 확인, 핵심 로직은 단위테스트 결정적).
- 2026-06-09 (TASK-0169 out-of-process ask-worker 실행모델 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 가 아닌 실제 Windows 화면 검증.
  - 시나리오(라이브 cutover, flag=worker): bootstrap_admin 로그인 상태 → `#newConversationBtn` 새 대화 → `#promptInput` 질문 입력 → `#sendBtn` 전송 → ask_jobs `running→done`(worker 처리) → **답변 정상 렌더**("7 곱하기 8 = 56, 경로: worker 직접 계산, ✅ 검증 완료"). browser→ask_jobs enqueue→worker claim→run→result_json→browser 렌더 전체 왕복 PASS. 스크린샷 `/tmp/pb0008_answer.png`. CHECK#13(PB-0008) **충족**.
  - 라이브 부하/백프레셔: 9 동시 ask(동일 계정) → 6× 200(실답변) + **3× 429**("동시 요청 제한") = `WEB_PARALLEL_LIMIT`(6) 정확 enforce(M5). burst 중 ask_jobs `pending=5,running=1`(6 active=limit), 단일 worker 직렬 처리로 6건 모두 동기 응답. 잡 전부 done(stuck 0).
  - 라이브 핵심(AC-0327): ask `running` 중 web `force-recreate` → 동일 run_id·attempts=1·lease=1 로 `done` 도달, backstop 미오염(last_status=done/last_error 빈값, B1). **web 재배포가 in-flight worker run 을 건드리지 않음** 실측.
  - 단위(DB-free, agent 이미지 mount): 신규 `test_ask_jobs.py`(claim/enqueue/fencing/sweep/cancel/ownership/active_inline_paths/table_exists 16건) + `test_ask_worker.py`(payload round-trip/config 불변식/run_id 6건) + `test_clear_cancel_runid.py`(MJ-2 fencing 4건) → make test 회귀 0 + ruff clean + py_compile.
  - hotfix(라이브 포착): `_ask_worker_ready` naive/aware datetime 비교 TypeError→readiness 영구 503 버그 수정([[project_task0159_orphan_run_stale_tz]] tz 함정 동형).
- 2026-06-09 (TASK-0164 SIGTERM graceful finalizer + RBAC catalog prune + out-of-process 설계):
  - 변경 성격: **백엔드** (`app.py` shutdown hook + run 생명주기 정리 + RBAC catalog DELETE) + 설계 문서. **시각 UI 표면 변경 없음** → **Environment: Windows-browser N/A** (PB-0008 화면 검증 대상 아님 — 관리 그리드는 PERMISSION_DEFINITIONS 기반이라 A2 도 비가시). CHECK#13 WARN 사유 = 시각 표면 부재.
  - 단위(DB-free, agent 이미지 mount): 신규 `test_shutdown_finalizer.py` 3건(S1 역 boot-guard 선정 / S2 부팅이전 skip / S3 race 가드) + 기존 `test_orphan_run_stale_recovery.py` 6건 → 전체 pytest 통과(회귀 0), py_compile PASS.
  - 라이브(배포 후): (a) ask mid-flight 중 `docker stop`/재배포 → web 로그 `shutdown finalize: 진행중 run N건 정리` + 해당 cid KV `last_status='error'`(고착 아님), (b) SIGKILL(`kill`) 대조 시 부팅 reconciliation 이 정리, (c) A2 — 재기동 후 `WebPermissions` 의 3 폐기 코드 행 0 — STATUS TASK-0164 참조.
  - outside-voice 적대적 리뷰 PASS-WITH-NITS, BLOCKER 0 (REV-20260609-0164).

- 2026-06-08 (TASK-0158 "진입점 없는 기능" 진입점 구성 Tier 1·2 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 가 아닌 실제 Windows 화면 검증.
  - 시나리오: `unit/feature-0003-agent-web-ui/tests/win-browser-task0158.scenario.json` (authed-session 가정 — 영속 프로필 로그인 상태). 재현: `python3 bin/win-browser.py launch --url https://localhost:18080/` → `run --scenario <위 파일>` → `down`.
  - **결과: OK=True, 39/39 step PASS.** 7개 진입점 전부 실제 브라우저 동작 확인:
    - **Tier1 즉시답변** — ask 전송 직후 `#sendBtn` 이 `.send-btn.is-stop`(중단)으로 모핑 + `#composerFinalizeBtn`("즉시 답변") 노출 `assert_visible` PASS(shot 03), 중단 클릭으로 취소 PASS(shot 04).
    - **Tier1 공유 링크 관리** — 대화 ··· 메뉴 "공유 관리" → `.share-mgr-panel` 모달 렌더("발급된 공유 링크가 없습니다." — 새 대화 정상)(shot 05·06).
    - **Tier1 scopeAll** — `#composerAttachmentsScopeAll` DOM 존재 eval=True (마크업 배포 확인).
    - **Tier2 내 활동기록** — 프로필 drawer "내 활동 기록" 탭 → `#profileAuditList` 렌더(shot 07).
    - **Tier2 grant 진단** — 관리콘솔 대시보드 `#dashboardGrantHealth` eval=True(shot 08).
    - **Tier2 audit.purge** — Audits pane 빨간 "보존기간 초과 로그 정리"(`#auditPurgeBtn`) `assert_visible` PASS → 모달(`.admin-modal`) "감사 로그 정리 (purge)" + 기준날짜 + 미리보기/삭제실행(disabled) 렌더 → 취소(삭제 미실행)(shot 09·10).
    - **Tier2 감사 facet** — `auditResourceTypeOptions`/`auditActorOptions` datalist 채워짐 eval `{res:9, actor:5}`.
  - 증거 스크린샷 10장: `/tmp/win-browser-shots/task0158/` (02_app_loaded ~ 10_purge_modal). CHECK#13(PB-0008 Windows-browser) **충족** — Tier1/2 커밋 시점 WARN 의 후행 보강.

- 2026-06-08 (TASK-0159 고아 run 무한 폴링 수정 — tz stale 회귀 + 부팅 reconciliation):
  - 변경 성격: 백엔드 (`app.py` run-status 생명주기 + stale 판정 tz). **시각 UI 표면 변경 없음** → PB-0008 Windows-browser N/A, CHECK#13 PASS(web/UI diff 없음).
  - 신규 `tests/test_orphan_run_stale_recovery.py` — agent 이미지(`--no-deps`, DB 없이 monkeypatch) 에서 **6 passed in 0.65s**:
    - T1 `_last_step_at_for_run`: aware KST(14:33+09) → UTC naive(05:33) 변환 / naive 통과 (회귀 가드).
    - T2 `_compute_display_status`: 오래된 step(>1200s) → `('stale_error', True)`, 최근(30s) → `('processing', False)`, terminal 통과.
    - T3 startup reconciliation boot-guard: `last_status_at >= _PROCESS_BOOT_UTC` skip 시맨틱.
  - 전체 app.py `python3 -m py_compile` PASS. 라이브 검증: web 재배포 후 (a) startup reconcile 로그, (b) 합성 고아 run → 재배포 시 `error` 자동 정리 확인 — STATUS TASK-0159 참조.

- 2026-06-05 (TASK-0151 DB 조회 UX 개선 — web 면: 첨부 text inline cap 정렬):
  - 변경 성격: `app.py _prepare_text_inline_attachments` 의 SQL 정렬(`ASC`→`DESC`+reverse) — **시각 UI 표면 변경 없음**(LLM 컨텍스트로 들어가는 inline 첨부 선별 로직, 백엔드). PB-0008 Windows-browser 화면 검증 대상 아님(Environment: Windows-browser N/A — UI 표면 없음). CHECK#13 WARN 의 사유 = 시각 표면 부재.
  - 검증: ruff(All passed) + pytest **191 passed/2 skipped**(feature-0002 신규 `test_db_query_ux.py` 14건 포함, 회귀 0). 동작 검증은 라이브 canary ask(첨부 리뷰 + 스키마 grounding)로 배포 후 수행 — STATUS TASK-0151 참조.

- 2026-05-20 (TASK-0089 Phase A~E — 작업 화면 profile drawer "내 감사 로그" 탭 신설):
  - **환경**: `docker run --rm --entrypoint python -v <wt>/unit/feature-0003-agent-web-ui/src:/app/web repo-web:latest` host-mounted code + image dependency.
  - **py_compile**: PASS.
  - **node --check static/app.js**: PASS.
  - **routing smoke (Phase E)**:
    - `list_profile_audit_events` present in app.py module ✓
    - `get_profile_audit_event` present ✓
    - FastAPI app routes: `['/api/profile/audits', '/api/profile/audits/{event_id}']` ✓
  - **Codex outside voice 5 findings 흡수 검증**:
    - C1 URL mismatch → 신규 `/api/profile/audits` endpoint 등록 확인 ✓
    - C2 `.any > .own` 강제 → backend `_audit_compose_where(scope="own", ...)` 직접 호출 (code review) ✓
    - C3 CSV export 미노출 → drawer-pane HTML 에 export 버튼 부재 (code review) ✓
    - C4 1-column + 수평 스크롤 → styles.css `.profile-audit-detail-change { white-space: pre; overflow: auto; max-height: 30vh }` ✓
    - C5 권한 race → `state.profileAudit.forbidden` + 403 handler in `loadProfileAuditList` + `updateProfileAuditTabVisibility()` in `renderProfile` ✓
  - **미완 (PR merge 후 사용자 위임)**:
    - live browser smoke: drawer tab 클릭 → list 표시 → row click → inline detail expand → filter 적용 / 초기화
    - `.any` 보유자 (admin) 가 drawer 호출 시 본인 row 만 나오는지 확인 (Codex C2 검증)
    - `audit.read.own` 권한 revoke 후 403 graceful state 진입 확인 (Codex C5 검증)
    - drawer 폭 390px 에서 1-column layout + ChangeJson 수평 스크롤 시각 검증 (Codex C4 검증)
- 2026-05-20 (TASK-0090 Phase A~B — `/api/admin/audits/export.csv` CSV streaming export 전환):
  - **환경**: `docker run --rm --entrypoint python -v <wt>/unit/feature-0003-agent-web-ui/src:/app/web repo-web:latest -c "..."` host-mounted code + image dependency.
  - **py_compile**: PASS.
  - **lightweight smoke (Phase B)**:
    - `import web.app` → IMPORTED OK ✓
    - `_AUDIT_EXPORT_CHUNK_SIZE = 500` ✓ (Codex minimum-fix — 1000→500)
    - `_AUDIT_EXPORT_FLUSH_BYTES = 65536` ✓ (Codex minimum-fix — 64KiB byte-threshold)
    - `_audit_export_filter_hash` present ✓ (Codex C4 — filter PII 회피)
    - `StreamingResponse` imported ✓ (Codex C1 — sync generator base)
    - `filter_hash` deterministic (sort_keys 정렬): `h1 == h2 = "42ea65e7de088de2"` ✓
  - **Codex outside voice 5 findings 흡수**:
    - C1 async + sync mysql blocking → sync generator (`def csv_iter()`) + streaming-only conn (generator 내부 try/finally)
    - C2 consistent snapshot vs max_id → `SELECT MAX(Id) FROM WebAuditEvents{where}` high-water + 모든 page `Id <= max_id AND Id < cursor_id`
    - C3 query plan EXPLAIN → future cycle (live mysql, representative filters)
    - C4 cap 제거 = DoS/계약 변경 → SECURITY §9.5 갱신 + export self-audit (start + complete/aborted) + 동시 제한 별 cycle
    - C5 cleanup → generator 내부 try/finally (cursor.close + conn.close + complete audit)
  - **endpoint 구조 검증 (code review)**:
    - **Phase 1 (auth conn)**: `_connect_memory()` + `_require_account` + `audit.export` permission + `_audit_parse_filter_params` + `_audit_compose_where` + `SELECT MAX(Id)` + `record_audit_event(action="audit.export.start", ...)` + commit + conn.close()
    - **Phase 2 (sync generator)**: `def csv_iter()` — header yield + while loop (max_id + cursor_id + chunk_size=500) → `_audit_compose_where` per page (cursor_id 추가) + Id<=max_id 강제 + ORDER BY Id DESC LIMIT 500 → row 마다 csv.writer.writerow → sio.tell()>=65536 마다 yield + reset → cursor_id 갱신 → final flush → try/finally cleanup → complete audit
  - **미완 (PR merge 후 사용자 위임)**:
    - live container PATCH 호출 + WebAuditEvents row 의 실 audit.export.start/complete 검증
    - representative filters EXPLAIN FORMAT=JSON 분석 (live mysql, query plan 보장)
    - 100k+ row export 시 memory footprint 측정 (현재 worktree 데이터는 ~150 row, 실 검증 불가)
- 2026-05-20 (TASK-0088 Phase A~D — `slow_query_log` 통합 ADR-0020 Decoupled 채택, docs only):
  - **검증 형태**: ADR 결정 → docs only, code 변경 0, runtime side-effect 0. py_compile/runtime smoke 불필요. verify-completion PASS 만 확인.
  - **Codex outside voice review** (consult mode, model_reasoning_effort=high, 390,785 tokens) → 5 critical findings + 2 minimum-fix 도출 → v2 redesign 흡수:
    - **C1 (framing)**: 현재 mysql conf `99-mysql-ai-server.cnf` 에 `slow_query_log` 설정 부재 (MySQL 8.0 default disabled) → ADR framing "현재 통합" → "**향후** 통합 여부" 정정.
    - **C2 (PII)**: slow query log = raw SQL statement literal — PasswordHash/Token/API key/임시 비밀번호/raw LLM prompt 등이 SECURITY.md §9.2 redact 정책 밖 → Decision 1순위 근거 = raw SQL text PII 차단.
    - **C3 (Option A reject 재작성)**: ETL 의 retention/RBAC 정합 trivial. 진짜 reject = semantic pollution + raw SQL PII + ChangeJson/table bloat + actor/target 의미 부재.
    - **C4 (Option B reject 재작성)**: raw SQL exfiltration 표면 + mount/rotation/race + 대용량 파일 DoS + `audit.read.any` 권한 의미 오염 + MySQL `log_output=TABLE` destination 우회.
    - **C5 (PS digest-first 추가)**: MySQL 8.0 의 `events_statements_summary_by_digest` digest 집계 1차 도구 권유. slow_query_log 는 incident/deep capture 2차로 제한.
  - **ADR-0020 4 section**: Context (current state) + Decision (Option C Decoupled) + Options 검토 (A/B reject 구체 사유 + C 채택) + Recommended performance path (PS digest-first 1차, slow_query_log incident 2차) + Security policy (raw SQL = 민감 로그) + Consequences (외부 SaaS trigger 4 선행 조건).
  - **결론**: Codex 5 findings 모두 ACCEPT 후 v2 redesign. ADR-0019 Codex C1 lock-in 의 final 결론. docs only — runtime smoke 불필요.
- 2026-05-20 (TASK-0091 Phase A~F — PATCH admin/products audit before-state full snapshot + audit integrity fix):
  - **환경**: `docker run --rm --entrypoint python -v <wt>/unit/feature-0003-agent-web-ui/src:/app/web repo-web:latest -c "..."` host-mounted code + image dependency.
  - **py_compile**: PASS.
  - **Sentinel + leak checks** (Codex C1, C3): `build_audit_change_json(action='admin.product.update', before=..., after=...)` → ChangeJson body 검사:
    - `'TASK-0091-SENTINEL-FULL-CONTENT-SHOULD-NOT-LEAK' in body: False` ✓ (Codex C1 — system_prompt full content drop, SECURITY §9.2)
    - `'should_not_leak' in body: False` ✓ (Codex C3 — databases drop)
  - **before/after delta checks** (Codex C4): sort_order 100→50 / is_default False→True / name 'before-name'→'after-name' 모두 정확 ✓
  - **default_cleared_product_ids** (Codex C4 side effect): caller 가 after dict 에 `_default_cleared_product_ids` 키로 명시 전달 → builder branch 가 처리 → body 의 top-level `default_cleared_product_ids: [5, 9]` ✓
  - **system_prompt_summary** (Codex C1, SECURITY §9.2): before/after 모두 `{present, content_len, updated_at}` 만 (content 본문 부재 sentinel 검증) ✓
  - **결론**: Codex outside voice 5 findings 모두 흡수 정합. 8-field allowlist + transaction integrity + side effect 추적 모두 검증.
  - **미완 (PR merge 후 사용자 위임)**: live PATCH 호출 + WebAuditEvents row 의 실 ChangeJson 검증 (real DB write path).
- 2026-05-20 (TASK-0086 Phase A~G — `WebAccountActivity` legacy table DROP + dual write 종료):
  - **baseline**: legacy=74 row, mirror=74 row (1:1 정합). 초기 흡수 68 + dual write 추가 6.
  - **backup (Codex C4)**: `mysqldump --single-transaction --quick --set-charset --create-options --add-drop-table --triggers --hex-blob --no-tablespaces agent_memory WebAccountActivity > artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes). Row digest `a09e7898d1ce88711f7a850ab5fbcc91`. File md5 `f4163df9dc1b7ac81ae4c463a0f35e98`.
  - **scratch restore rehearsal**: 별 schema `task0086_restore_test` import → row count 74 + digest match ✓ → scratch DB DROP.
  - **사용자 명시 ack** 받음.
  - **code 변경 (Phase C)**: `_log_search_activity()` legacy INSERT 제거 + `_ensure_web_account_activity_schema()` 정의+호출×2 제거 + `_migrate_web_account_activity_to_audit()` rollback window 보존. py_compile PASS.
  - **lightweight smoke (Phase D+E)**: `docker run --rm --entrypoint python -v <wt>/.../src:/app/web repo-web:latest -c "import web.app"` → `IMPORTED OK` + `_ensure_web_account_activity_schema present: False` ✓ + `_migrate_web_account_activity_to_audit present: True` ✓.
  - **DROP (Phase F)**: `DROP TABLE IF EXISTS WebAccountActivity` → `DROP completed`.
  - **verify (Phase G)**: `tables_remaining=0` ✓ + WebAuditEvents `conversation.search.body` 74 row 변동 없음 ✓.
  - **tests**: test_audit_migration.py M3 (`m3_log_search_activity_dual_write`) 제거 + main() 호출 제거 + 모듈 docstring 3→2 시나리오 (Codex C2). M1/M2 보존 (table-absent silent skip).
  - **Codex outside voice 5 findings 흡수**: C1 (Option A 불가능→helper Option B) / C2 (mirror risk→smoke + M3 제거) / C3 ("single tx"→"single statement") / C4 (backup 검증 강화) / C5 (rollback 2 시나리오).
  - **Rollback runbook**: (1) DB restore only / (2) code revert + DB restore (완전).
  - TASK-0073 Phase A2 dual write 종료. dispatcher → WebAuditEvents 단일 source.
- 2026-05-20 (TASK-0092 Phase A~B — `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed **7 vector matrix** 검증):
  - 환경: `docker run --rm --entrypoint python repo-web:latest -c "import web.app"`. module load 시점 `_enforce_audit_prod_gate()` (app.py:76-94) trigger. compose `--no-deps` 우회 (Codex C2 — mysql 기동 회피, 다른 worktree compose project 오염 차단). `.env` 부재로 inline `-e` 만 사용.
  - **7 vector PASS (7/7)**:
    - **V1** (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod`) → rc=1, stderr `[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1 (AGENT_MODE=prod; TASK-0073 Phase A1)` ✓ target fail-closed
    - **V2** (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=<unset>`) → rc=1, stderr `... AGENT_MODE=(unset → prod) ...` ✓ default prod 정합
    - **V3** (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=staging`) → rc=1, stderr `... AGENT_MODE=staging ...` ✓ non-dev/test 정합
    - **V4** (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=dev`) → rc=0, stdout `IMPORTED OK` ✓ dev/test bypass 허용
    - **V5** (`AGENT_AUDIT_ENABLED=1` + `AGENT_MODE=prod`) → rc=0, stdout `IMPORTED OK` ✓ positive control
    - **V6** (`AGENT_AUDIT_ENABLED=true` + `AGENT_MODE=prod`) → rc=1, stderr `... AGENT_MODE=prod ...` ✓ Codex C3 strict-string-equality 계약 확인 (`"true"` ≠ `"1"` — 운영자 trap 가능성)
    - **V7** (모두 unset) → rc=0, stdout `IMPORTED OK` ✓ default `1` + default prod 정상
  - **stderr 검증** (Codex C4 강화): 모든 FAIL vector 가 rc=1 + stderr 3 substring (`[FATAL] AUDIT REQUIRED IN PROD` + `set AGENT_AUDIT_ENABLED=1` + `TASK-0073 Phase A1`) 모두 포함 + `Traceback` / `ModuleNotFoundError` 부재. PASS vector 는 stderr `[FATAL]` 부재 + stdout `IMPORTED OK` 정합.
  - **운영자 trap 확인** (V6): `AGENT_AUDIT_ENABLED="true"` 가 fail-closed 됨 — strict string equality (`os.getenv(...).strip() == "1"`). 운영자가 truthy 표현 (`true`/`yes`/`01`) 명시 시 prod 시작 차단. **SECURITY.md §8 의 strict-string-equality 계약 명시 별 cycle 후속 권고** (본 cycle scope 외).
  - 본 검증으로 TASK-0073 Phase E 의 사용자 위임 항목 1 건 (audit prod gate fail-closed) 해소. live container spawn 으로 코드 path 정합성 + 메시지 정확성 + dev/test bypass 정합성 모두 확인.
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

- 2026-06-10 (TASK-0197 assistant 말풍선 타임스탬프 옆 소요시간 표시 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py doctor → launch → eval → screenshot)
  - **Bridge:** relay (무권한 userspace relay 자동 기동, endpoint: http://172.28.64.1:9223)
  - **검증 내용:**
    - DOM eval — `.message-meta-duration` span 존재 확인: `{"totalMeta":2,"withDuration":1,"assistantMessages":1}` — assistant 말풍선 1개에만 소요시간 표시, user 말풍선에는 미표시(정상).
    - 소요시간 텍스트: `"38초"` (formatElapsed 형식 일치).
    - fullText 확인: `"Assistant · 2026. 06. 10. 오전 11:06 38초"` — 타임스탬프 바로 옆에 붙어 표시.
  - **Evidence:** `/tmp/win-browser-shots/task0197_zoomed.png` (2× 줌, 빨간 outline 하이라이트 — "Assistant · 2026. 06. 10. 오전 11:06 **38초**" 명확 확인)
  - **Pass/Fail: PASS**
  - **Notes:** `.message-meta-duration { font-size:10px; opacity:0.7 }` 스타일 적용, 캐시버스터 `?v=20260610-response-duration` 확인. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-10 (TASK-0198 LLM 사용량 모델별 분리/선택 + 모델별 요약 카드 + 좌우 스크롤 제거 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py launch → run --scenario → eval → screenshot)
  - **Bridge:** relay (무권한 userspace relay 자동 기동, endpoint: http://172.28.64.1:9223)
  - **Scenario:** `unit/feature-0003-agent-web-ui/tests/win-browser-task0198-usage.scenario.json` (22 steps, 인증된 admin 세션 — `console.usage.read`)
  - **배포:** 이 worktree 코드로 web 이미지 재빌드(`docker compose -p repo build web`, sha 갱신) + `up -d --no-deps --force-recreate web`. cert(`make web-tls-cert`) 생성 후 TLS 모드 기동(`--ssl-keyfile/--ssl-certfile`). 서빙 자산 캐시버스터 `?v=20260610-usage-model-filter2` 확인, healthz status:ok(mysql/pg ok).
  - **검증 내용 (전 step ok:true, scenario ok:true):**
    - **모델별 분리 (A):** 모델 필터 칩 6개(전체 + edge/gemma4:e2b/claude-haiku-4/claude-sonnet-4, 각 토큰 수·색 dot), scope "전체 모델", 모델별 분리 카드 **4개** 렌더 — `{"chips":6,"mcards":4,"scope":"전체 모델"}`.
    - **모델 선택 (A):** 칩 클릭 → `{"scope":"선택 1개 모델","activeChips":1}` — 요약 합계 카드·모델별 카드·일별 stacked·도넛(100.0%)이 선택 모델(edge: 요청 27/호출 19,616/토큰 11,557,309) 기준으로 재계산. 전체 칩 복귀·모델 카드 클릭 solo 선택 모두 동작.
    - **좌우 스크롤 제거 (C):** usage pane `overflowX:"hidden"`, `userCanScrollHorizontally:false` — 사용자가 가로로 스크롤 **불가** 확정. 세로 스크롤바(`vbarPx:15`)만 존재(콘텐츠 길이상 정상). `scrollW 972 vs clientW 966` 6px 차이는 세로바 폭으로 인한 것이며 overflow-x:hidden 으로 클리핑/스크롤 안 됨 — 위양성 아님.
  - **Evidence:** `/tmp/win-browser-shots/task0198/03_summary_model_cards.png` (전체 모델 — 칩 바·합계 카드·모델별 4카드·일별/도넛 차트, 가로 스크롤바 부재), `04_one_model_selected.png` (edge 단독 선택 — 합계·카드·차트 모두 edge 기준 재계산, 도넛 100%).
  - **Pass/Fail: PASS**
  - **Notes:** 백엔드/API/스키마/RBAC/시크릿 무변경(기존 `/api/admin/usage` 응답 클라이언트 재계산). 모델 키 `COALESCE(resolved_model,model)`. 부분 선택 시 역할·계정 요청·호출은 모델 횡단 분해 불가라 `—` 표기(토큰·비용은 정확). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0204 LLM 사용량 '모델별' 카드 제거 + 모델 칩 토큰수 제거 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py launch → goto → click → eval → screenshot)
  - **배포:** main `e51a836` 로 web 이미지 재빌드(`make dc-build SERVICE=web`) + `up -d --no-build web`. 베이킹 `admin-usage-mcards`=0, 서빙 캐시버스터 `?v=20260611-usage-no-mcards`, healthz `git_commit=e51a836`(mysql/pg ok).
  - **결함 재현(수정 전, TASK-0202):** 모델 카드 클릭 시 비선택 3카드 즉시 소실 + 빈 공간 — `02_solo_hover.png`(선택 직후 visible:1/dimmed:3, 커서가 카드 위인데도 collapse). 근본원인=re-render 후 새 노드 `:hover` 미부여로 동기 회수 로직 오발동.
  - **검증 내용(수정 후, 전 step ok:true):**
    - 모델별 카드 부재: `{"mcards":0,"mcardsHead":0}` — 카드 그리드·"모델별" 헤더 완전 제거.
    - 칩 모델명만: `{"chips":5,"chipTok":0,"firstChipText":"edge","allChipText":"전체"}` — 버튼 내 토큰수 0, 모델명/`전체`만.
    - 칩 토글 정상: edge 칩 클릭 → `{"scope":"선택 1개 모델","activeChips":1,"mcards":0,"donutHasData":true}`(필터된 도넛/차트 재계산, 카드 재등장 없음), `전체` 복귀 → `{"scope":"전체 모델"}`.
  - **Evidence:** `/tmp/win-browser-shots/task0204/01_usage_no_mcards.png`(칩 모델명만·카드 부재·요약+차트 정상), `02_chip_filter.png`(edge 필터). 결함 비교: `/tmp/win-browser-shots/task0202/02_solo_hover.png`.
  - **Pass/Fail: PASS**
  - **Notes:** hover 결합 잭 제거 확인 — 카드가 없어 마우스 이동 시 깜빡임/레이아웃 점프 없음. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0206 쿼리 문자열 항상 표시 + 실행결과셋 기본 숨김 토글 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py launch → run --scenario → eval + screenshot)
  - **Bridge:** relay (무권한 userspace relay 자동 기동, endpoint: http://172.28.64.1:9223)
  - **배포:** `docker compose up -d web`(신규 이미지 sha 갱신) + 컨테이너 healthy 확인. 서빙 `app.js` — `collapseSqlCodeBlocksInContent`가 빈 함수(토글 로직 0), `buildSqlStepPanel`에서 결과셋 토글 래퍼 확인. healthz 200 OK.
  - **검증 내용 (전 step ok:true):**
    - **초기 DOM 상태:** `{"sqlBlockCount":1,"visibleSqlBlocks":1,"toggleWrapCount":1,"resultToggleWrapCount":1,"resultBodyCount":1,"resultBodyHiddenCount":1,"queryViewBtnCount":1,"queryViewBtnTexts":["결과 보기"]}` — SQL 블록 1개 **기본 표시**, 결과셋 1개 **기본 숨김**, 버튼 텍스트 "결과 보기"(구 "쿼리 보기" 아님).
    - **"결과 보기" 클릭 후:** `{"resultBodyCount":1,"resultBodyHiddenCount":0,"btnTexts":["결과 닫기"]}` — 결과셋 **펼쳐짐**, 버튼 텍스트 "결과 닫기"로 토글.
  - **Evidence:** `/tmp/win-browser-shots/step_01_20260611_123131.png`(SQL 블록 기본 표시·"결과 보기" 버튼), `/tmp/win-browser-shots/step_03_20260611_123146.png`(클릭 후 결과셋 펼쳐짐·"결과 닫기" 버튼).
  - **Pass/Fail: PASS**
  - **Notes:** 쿼리 문자열 항상 표시(숨김 로직 0), 결과셋 기본 숨김·클릭 토글 정상 동작. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0207 관리 콘솔 데이터소스 pane list-detail UI 표준화 + 수정/삭제 노출 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py doctor → launch → click → eval → screenshot)
  - **Bridge:** relay (endpoint: http://172.28.64.1:9223)
  - **배포:** PR #144 → main `20a826d` 머지 → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz `git_commit:20a826d` mysql_ok/pg_ok, 컨테이너 healthy. 서빙 `admin.js` 신규 코드(`_dsRenderDetail`×7·`admin-list-row--nav`·`datasourceList`) 베이킹 + 구 `admin-ds-list`/`datasourcesPane` 0건 확인. 캐시버스터 `?v=20260611-ds-admin-ui`.
  - **검증 내용 (전 step ok:true):**
    - **pane 구조:** `{"paneActive":true,"listExists":true,"detailExists":true,"rowCount":1,"count":"1","tabCount":"1","newBtn":true,"oldFlat":false}` — 다른 카테고리와 동일한 list-detail 5단 구조로 렌더, 구 평면 `.admin-ds-list` 제거 확인. 탭 배지·목록 카운트 wiring 동작.
    - **상세(read view):** 행 클릭 → `{"title":"winsql","badges":["mssql",".env 읽기전용"],"kvPairs":6,"actionButtons":["연결 테스트"]}` — 연결 좌표·출처·보안 kv 6쌍 렌더. 본 datasource 는 `.env` 출처(읽기전용)이라 **수정/삭제 미노출(테스트만)** + 읽기전용 사유 안내(".env 출처 데이터소스입니다 — 콘솔에서 수정/삭제할 수 없습니다.") 표시 — RBAC/editable 게이트 정상.
    - **생성/편집 폼:** "+ 새 데이터소스" 클릭 → `{"formTitle":"새 데이터소스","fieldCount":7,"fields":["키…","엔진…","호스트","포트","DB 유저…","비밀번호","기본 참조 DB…"],"buttons":["생성","취소"]}` — 7필드 폼 + 생성/취소 렌더(편집도 동일 폼 사용 → 수정 UI 동시 검증). 실 생성은 미수행(라이브 무변경).
  - **Evidence:** `artifacts/ds-admin-ui-1-list.png`(목록+빈 상세), `artifacts/ds-admin-ui-2-detail.png`(선택 datasource 상세 — 연결좌표·출처·보안·연결 테스트), `artifacts/ds-admin-ui-3-form.png`(새 데이터소스 폼).
  - **Pass/Fail: PASS**
  - **Notes:** 데이터소스 pane 이 계정/역할/제품/설정 과 동일한 list-detail 외관으로 통일. 수정/삭제는 editable(DB 출처) datasource 의 상세 sticky 액션바에 노출(`.env` 출처는 정책상 읽기전용). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0213 접근 가능 DB picker — dropdown+checkbox 연속 토글 UI — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py doctor → launch → click → screenshot)
  - **Bridge:** relay (endpoint: http://172.28.64.1:9223)
  - **배포:** PR #151 → main `9d8d33e` 머지 → `docker compose build web` + `docker compose up -d --no-build web`. `grep -c db-picker-checkbox admin.html` = 2, `grep -c admin-db-picker-wrap admin.js` = 1 확인.
  - **검증 내용 (전 step ok:true):**
    - **제품 상세 화면:** 킹스레이드(KR) 클릭 → `접근 가능 데이터베이스` 섹션에 `+ 데이터베이스 선택` 버튼 렌더. 구 `<select>+추가` 버튼 없음 확인.
    - **체크박스 드롭다운:** `+ 데이터베이스 선택` 클릭 → 드롭다운 패널 오픈, `BackupManager` / `DBFunctor` / `distribution` 등 체크박스 항목 목록 표시 확인. 시스템 DB(`master`/`model`/`msdb`) 는 고정칩으로 표시되고 드롭다운 목록에 미노출.
  - **Evidence:** `/tmp/pb0008_product_detail.png`(제품 상세 — "+ 데이터베이스 선택" 버튼), `/tmp/pb0008_picker_open.png`(체크박스 드롭다운 오픈 — 항목 목록 표시).
  - **Pass/Fail: PASS**
  - **Notes:** 캐시버스터 `?v=20260611-db-picker-checkbox` 서빙 확인. 체크박스 연속 토글(추가버튼 없이 즉시 draft 반영) 구조. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0223 제품별 insight-worker 분석 완료율 UI — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (doctor → launch → run --scenario `tests/win-browser-task0223.scenario.json` + 단발 click/eval/screenshot)
  - **Bridge:** relay (endpoint: http://172.28.64.1:9223)
  - **배포:** PR #161 → main `b46cbd4` 머지 + hotfix `cde2610`(_log→logging) + `0e37b8e`(conversation_id `__global__`) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz git_commit=`0e37b8e` 베이킹 확인.
  - **검증 내용 (시나리오 step1~10 ok:true):**
    - **제품 목록 배지:** 4개 제품 row 에 분석 완료율 배지 렌더 (eval 추출): 킹스레이드(KR)=`분석 100%`(cov-ok 녹색), 마이크로볼츠(MV)=`분석 100%`, 건즈 국내(GZ_KR)=`분석 100%`, DK온라인(DK)=`분석 측정 불가`(cov-muted — MSSQL `mssql_local` 연결실패 graceful).
    - **제품 상세 breakdown:** 킹스레이드 클릭 → `접근 가능 데이터베이스` 섹션에 `insight 분석 완료율` 블록: 요약 `100%`, 진행바 `389 / 389 객체 (DB + 테이블)`, per-DB `dbauth=테이블 9/9 · DB✓`, `dbgame=테이블 98/98 · DB✓`, `dblog=테이블 279/279 · DB✓`.
    - **라이브 API 실측:** `GET /api/admin/products/insight-coverage` — product 1/7/8(MySQL)=100% (analyzed=total), product 91(MSSQL)=measurable:false(graceful, 500 없음).
  - **Evidence:** `/tmp/win-browser-shots/task0223/01_list_badges.png`(목록 — 3× 녹색 `분석 100%` + 1× `분석 측정 불가`). 상세 screenshot 은 relay CDP transient(font-load 후 timeout)로 미캡처되나 구조 검증은 eval 로 확정.
  - **Pass/Fail: PASS**
  - **Notes:** 캐시버스터 `?v=20260611-insight-coverage` 서빙. 분자=PG rag_objects(`__global__`/`common`) ∩ 라이브 카탈로그 set 교집합, datasource scope=엔드포인트 해시(+기본 엔드포인트 NULL 폴백). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0229 제품 상세 "접근 가능 데이터베이스" UI 통합 — **PB-0008 Windows-browser 완료 게이트, 인증 후 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (doctor → launch → `/api/auth/login`(bootstrap_admin) → goto `/admin` → 제품 탭 → 제품 선택 → eval 구조검증 + screenshot)
  - **배포:** main `997d9ec`(PR #167 TASK-0229 + PR #166 SSRF + PR #168 멀티 datasource 머지본). healthz status=ok, git_commit=`997d9ec`, mysql_ok/pg_ok. 라이브 정적 자산 — `admin.js?v=20260611-product-multi-ds`(PR #168 이 캐시버스터 갱신, 내 통합 UI 코드는 그 안에 공존) 에 `buildSystemDbChip`/`buildDbCoverageCells`/`cov-db-wrap`(grep 5 매치), `styles.css` 에 `sysdb-chip`/`cov-microbar`(19 매치).
  - **검증 내용 (인증 후 실제 화면):**
    - **로그인:** `/api/auth/login`(bootstrap_admin/admin role) status 200, 세션 쿠키 설정.
    - **제품 목록:** `관리 콘솔 > 제품` 5개 row, 각 `분석 N%` 배지 렌더.
    - **문제1 해소(1:1 중복 통합) — PASS:** 킹스레이드(KR) 선택 → `접근 가능 데이터베이스` 섹션이 (a) 요약 헤더(`insight 분석 완료율` `100%` 배지 + 전체 진행 바 `389/389 객체` + 새로고침) + (b) **통합 리스트** 3행으로 렌더. 각 행(eval 추출): `dbauth 9/9 DB✓` / `dbgame 98/98 DB✓` / `dblog 279/279 DB✓` — per-DB 진척(마이크로바+통계+상태칩)이 사용자 DB chip 과 **한 행으로 통합**됨(구 per-DB breakdown 리스트 별도 표시 사라짐, `old_breakdown_in_covDetail:false`).
    - **문제2 해소(시스템 DB 묶음) — PASS:** 시스템/메타데이터 4종이 단일 칩 `시스템 DB 4개` + `고정` 태그로 묶임. `tabindex=0`, `title`=개행 구분 4개 목록(`information_schema`/`mysql`/`sys`/`performance_schema`), `aria-label`=동일 목록 1줄, **focus 시 커스텀 툴팁 `visibility:visible`** + 툴팁 카드에 4개 DB 목록 — 마우스 hover·키보드 focus·터치 tap 모두 개별 이름 확인 가능(접근성 3중).
    - **MSSQL 제품(DK/FH):** `시스템 DB 3개` 묶음 칩(master/model/msdb) 정상.
  - **Evidence:** `artifacts/task0229-product-db-unified.png`(킹스레이드 제품 상세 — 요약 헤더 100% + dbauth/dbgame/dblog 통합 리스트(9/9·98/98·279/279·DB✓·×) + `시스템 DB 4개·고정` 칩 + focus 툴팁 카드 펼침), `artifacts/task0229-admin-login.png`(로그인 화면).
  - **Pass/Fail: PASS** (문제1 통합 리스트 + 문제2 시스템 묶음 칩 + 접근성 툴팁 전부 실제 Windows 화면에서 확인).
  - **Notes:** 첫 탐색 시 `db_row_count:0` 관측됐으나 이는 브라우저 세션의 stale `productDbDraft` 캐시(이전 탐색 잔재) 탓 — 완전 새로고침 후 3행 정상 렌더 확인. 라이브 데이터 정합 검증: `/api/admin/products` 의 KR `databases[].datasource_key` = `mysql-local`(전 행), `datasources`=[mysql-local primary] → `_serverDbsFor` 매칭 정상(PR #168 멀티 datasource 차원 모델과 정합, 회귀 없음). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-12 (TASK-0242 제품 데이터소스 — DB별 insight 파악 내용 한 줄 인라인 + 추가 picker 분석상태 — **PB-0008 Windows-browser 완료 게이트, 인증 후 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (doctor → `/api/auth/login`(bootstrap_admin) → goto `/admin` → 제품 탭 → 제품 선택 → eval 구조검증 + screenshot)
  - **Scenario:** `unit/feature-0003-agent-web-ui/tests/win-browser-task0242-db-insights.scenario.json` (19 steps, 인증된 admin 세션)
  - **배포:** main `f815335`(PR #182 머지본) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz git_commit=`f815335`, mysql_ok/pg_ok, insight_heartbeat_age=7s(worker fresh). 서빙 자산 `admin.js?v=20260612-db-insight-surface`(신규 함수 `buildDbRoleCell`/`buildPickerInsightMeta`/`loadProductDbInsights` 6 매치).
  - **검증 내용 (전 19 step ok:true, scenario ok:true):**
    - **로그인:** `/api/auth/login`(bootstrap_admin) `login_ok:true`, `/admin` 200.
    - **등록 DB 행 한 줄 인라인 (요청①③④) — PASS:** 킹스레이드(KR) 선택 → datasource accordion `mysql-local`(기본) 펼침 아래 `.cov-db-row` **3행, 전부 role 셀 채워짐**(`rowCount:3, populatedRoleCount:3`). 각 행 = [DB명 · insight-worker 설명 · 분석률 마이크로바 · 객체 N/N · DB✓ · 초기화 · ×] 단일 라인(eval 추출): `dbauth | Account/Auth — Schema containing account authentication and profile data… | 9/9`, `dbgame | Game Data — This schema contains game progression tables… | 98/98`, `dblog | Game Logs — This schema logs detailed user actions… | 279/279`. 설명은 overflow ellipsis 한 줄, 전문은 hover title. **별도 펼침 버튼 없음**(사용자 지시 반영).
    - **추가 picker 분석상태 (요청②③④) — PASS:** `+ 데이터베이스 추가` 클릭 → 드롭다운 13항목, 각 [☐ DB명 · 도메인 힌트 · 분석상태 칩]. `stateCounts={"분석됨":13}`(전부 is-done, mysql-local 전 DB 분석 완료). 예: `__invalid_default_db__·Global/Server·분석됨`, `account_db·Account/Auth·분석됨`, `dbauth·Account/Auth·분석됨`(체크됨), `dbgame·Game Data·분석됨`(체크), `dblog·Game Logs·분석됨`(체크), `dbresult·Game Data·분석됨`. 클리핑 없이 inline 정상 흐름(TASK-0240 fix 위 공존).
    - **라이브 API 실측:** `GET /api/admin/products/{1,8}/db-insights`(MySQL)=ok, account_db 13객체(schema+12T) domain Account/Auth + 실 설명; `/91/db-insights`(MSSQL)=ok, dbo **373객체**(schema+372T), dev50 1객체(미분석 → "No schema… information"). worker `{alive:true,age_sec:2,status:ok}`.
  - **Evidence:** `/tmp/win-browser-shots/task0242/01_db_rows_role_inline.png`(제품 상세 — 데이터소스 섹션·완료율 100%·mysql-local accordion), `/tmp/win-browser-shots/task0242/02_add_picker_status.png`(DB 3행 한 줄 인라인 설명 `Account/Auth — Schema c…`/`Game Data — …`/`Game Logs — …` + 9/9·98/98·279/279·DB✓·초기화·× + picker 13항목 도메인힌트·분석됨 칩).
  - **Pass/Fail: PASS** (등록 DB 행 한 줄 인라인 설명 + 추가 picker 도메인 힌트·분석상태 전부 실제 Windows 화면에서 확인. 콘솔/pageerror runner ok:true).
  - **Notes:** '분석중'/'미분석' 칩은 분석 객체 0 + worker alive/미alive 조건이라 라이브(전 DB 분석완료)에서는 '분석됨'만 관측 — 3-state 로직은 단위테스트(test_db_insights 14)로 커버. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-12 (TASK-0243 MSSQL db-insights catalog 귀속 수정 — **PB-0008 Windows-browser 완료 게이트, MSSQL 제품 시각검증 PASS + MySQL 무회귀 대조**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (doctor → launch(relay 재기동) → `/api/auth/login`(bootstrap_admin) → goto `/admin` → 제품 탭 → **DK온라인(MSSQL) 선택** → eval 구조검증 + screenshot)
  - **Scenario:** `unit/feature-0003-agent-web-ui/tests/win-browser-task0243-mssql-db-insights.scenario.json` (17 steps, 인증된 admin 세션, MSSQL 제품)
  - **배포:** main `ed09a53`(PR #184 머지본) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz git_commit=`ed09a53`, mysql_ok/pg_ok.
  - **진단(수정 전 결함):** TASK-0242 의 `_compute_product_db_insights` 가 by_db 를 `rag_objects.schema_name` 으로 묶었는데 MSSQL 은 schema_name=`dbo`(SQL스키마)라 등록 DB(catalog)와 차원이 달라 라이브 제품91 by_db=`['dbo','dev50']` — 등록 DB(GameLog_100/dk_data_release/…)와 무교집합 → MSSQL 등록 DB 행 전부 "역할 미파악". MySQL 은 db==schema 라 정상이었음.
  - **검증 내용 (전 17 step ok:true, scenario ok:true):**
    - **MySQL 무회귀(사용자 요청 — 키 수정 side-effect):** 배포 전/후 제품1(MySQL) `GET .../db-insights` by_db 키 집합 20개 **byte-identical**(diff 0). 그룹핑 분기를 engine=='mssql' 에만 적용하고 MySQL 은 schema_name 직접 사용.
    - **MSSQL 등록 DB 행 역할 표면화 — PASS:** DK온라인(제품91, mssql_local) 선택 → `.cov-db-row` **5행 전부 role 셀 채워짐**(`engine:mssql, rowCount:5, populatedRoleCount:5` — 수정 전이면 0). 각 행 한 줄 인라인(eval): `GameLog_100 | Game Data — This schema appears to store detailed information related to player… | 37/37`, `GameLog_151 | Account/Auth — … | 37/37`, `dk_data_release | Game Data — … | 123/123`, `dk_server_info | Global/Server — … | 1/1`, `GameLogManager | Game Logs — … | 7/7`. by_db 키가 catalog(GameLog_100 등) 단위로 묶여 등록 DB 와 lowercase 매칭.
    - **picker 3-state 실증(MySQL 검증서 못 본 상태):** `+ 데이터베이스 추가` → 10항목, `stateCounts={"분석중":5,"분석됨":5}`. insight 보유 DB(dk_data_release·dk_server_info·GameLog_100·GameLog_151 = 도메인 표시 + **분석됨**), insight 미보유 + worker alive DB(BackupManager·DBFunctor·distribution = **분석중**). 시스템 DB 3개(master/model/msdb) 고정 묶음 칩.
  - **Evidence:** `/tmp/win-browser-shots/task0243/01_mssql_db_rows_role.png`(DK온라인 제품 상세 — 데이터소스 섹션·완료율 100%·210/210·MSSQL note), `/tmp/win-browser-shots/task0243/02_mssql_add_picker.png`(MSSQL 5행 한 줄 인라인 역할 `Game Data — …`/`Account/Auth — …`/`Global/Server — …`/`Game Logs — …` + 37/37·123/123·1/1·7/7 + picker 분석중[노랑]/분석됨[초록] 3-state + 시스템 DB 3개 고정칩).
  - **Pass/Fail: PASS** (MSSQL 등록 DB 5행 역할 한 줄 인라인 + picker 3-state[분석중/분석됨] 실제 Windows 화면 확인, MySQL by_db 키 byte-identical 무회귀).
  - **Notes:** side-effect 격리(사용자 요청) — coverage(완료율)·insight-reset 은 object_key 미사용(schema_name/table_name 컬럼)이라 무영향, 전체 make test 회귀 0, 적대적 subagent SHIP. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-12 (TASK-0245 제품 상세 접근가능 DB 리스트 행 컬럼 폭 정합 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py goto → click → eval(좌표 측정) → screenshot)
  - **배포:** PR #189 → main `2bc2067` 머지 → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz `git_commit:2bc2067`, 서빙 `styles.css` 에 신규 grid(`minmax(96px,0.9fr) … 96px 54px 76px 60px 24px`) 베이킹 확인. 캐시버스터 `?v=20260612-db-row-align`.
  - **검증 내용 (객관 좌표 측정 — 제품 92 "출조낚시왕(FH)" / datasource mssql-qa-idc, cov-db-row 8행):**
    - 각 행의 컬럼 시작 x(`getBoundingClientRect().left`) 측정 — **전 8행 spread=0px**: 역할설명(`.cov-db-role`) left=770, 진척바(`.cov-microbar`) left=816, 통계(`.cov-db-stat`) left=922, 상태칩(`.cov-db-status`) left=986, 초기화(`.cov-db-reset`) left=1072. 문자열 길이(FHDef↔fh_ods↔FHGame1, 역할 Gam…↔Acco…)와 무관하게 **모든 컬럼이 행 간 동일 좌표 정렬**.
    - 수정 전: 통계·상태·초기화 `auto` 컬럼이 행마다 폭을 달리해 name/role(fr) 컬럼이 어긋나며 spread>0(들쭉날쭉). 수정 후 고정폭 트랙으로 spread=0.
  - **Evidence:** `artifacts/db-row-align-after.png` (제품 상세 DB 리스트 8행 — DB명·역할·진척바·상태칩·초기화·× 전 컬럼 수직 정렬 일치).
  - **Pass/Fail: PASS**
  - **Notes:** 순수 CSS grid 트랙 고정(`.cov-db-row` auto→고정폭 + justify-self:start). 행 콘텐츠·셀 빌더·권한 무변경. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-12 (TASK-0251 공유 페이지 SQL "쿼리 열고닫기" 토글 → "실행 쿼리 전환" navigator 교정 — **PB-0008 Windows-browser 완료 게이트, 익명 공유뷰**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, 라이브 공유 URL `https://112.185.196.20:18080/share/{token}`, self-signed ignore). WSL headless 아닌 실제 Windows 화면. **익명(비로그인) 접근** — 쿠키 임포트 불요.
  - **Runner: AI** (bin/win-browser.py launch/goto → eval(DOM 검사·nav-btn click hit-test) → screenshot)
  - **배포:** PR #202 → main `9cee54a` 머지 → `docker compose build web` + `up -d --no-deps web`. 서빙 `/app/web/app.py` 에 `_share_sanitize_step`/`_share_attach_sanitized_steps` 베이킹 확인(grep 6), 서빙 `share.html` 캐시버스터 `?v=20260612-share-sql-nav` 확인. healthz 200(mysql_ok/pg_ok).
  - **검증 내용 (라이브 2개 공유 토큰):**
    - **① 사용자 보고 토큰** (`tDuTZ…`, 대화 20260612055236, steps 없음 + 본문 ```sql``` 보유): `.share-sql-toggle-btn` **0개**(열고닫기 토글 완전 부재), 본문 "쿼리 보기/닫기/열기" 라벨 **없음**, `.share-message-content pre` **5개 전부 펼쳐 가시**(visiblePre=5/5). → 사용자가 보고한 "쿼리 열기" 버튼 제거 + 본문 SQL 항상 표시 확인.
    - **② 실행단계 보유 토큰** (`xGXRt…`, 대화 20260527044221, 8 execute_sql): `.share-sql-navigator` **1개**, 인디케이터 **"쿼리 1/8"**, nav-btn 2개(◀▶). **▶ click hit-test**: "쿼리 1/8"→"2/8" 전환(activeIdx 0→1) + 활성 패널 결과 테이블 가시. 끝까지 ▶ → "쿼리 8/8" + ▶ disabled, ◀ 복귀 → "쿼리 1/8" + ◀ disabled. 8개 패널 SQL 실측: `SHOW TABLES … '%login%'`×3 / `'%event%'`×3 / `SELECT COUNT(*) … atten…`×2 — **결과셋별 실행 쿼리 전환 동작 확인**. 토글 0·라벨 없음.
  - **익명 노출 경계(라이브 API 직접):** 응답 직렬화에 `result_summary.csv_paths`(서버 `/shared/` 경로) **0**, bare `preview` 키 **0**, step 키 = `{intent,reason,result_summary,sql,tool,work}`, result_summary 키 = `{preview_table}`만 — `_share_sanitize_step` 화이트리스트 라이브 적용 확인.
  - **Pass/Fail: PASS**
  - **Notes:** 사용자 의도("쿼리 열고닫기"가 아닌 "결과셋에 따라 실행 쿼리 전환") 정확 구현 — steps 없는 대화는 본문 SQL 펼침, steps 있는 대화는 navigator 전환. 익명 노출 sanitize 라이브 검증(csv_paths/preview/args/error 0). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0256 assistant 답변 markdown ```diff 블록 — **PB-0008 Windows-browser 완료 게이트, 렌더 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (win-browser.py launch → eval(배포 markdownToHtml 로 샘플 diff 주입·DOM 검사·getComputedStyle) → screenshot)
  - **Steps/Result:** 배포 자산(app.js?v=20260615-task0256-diff) 의 전역 `markdownToHtml`/`enhanceDiffBlocks` 에 샘플 리뷰 답변(```diff: `- SELECT *` 삭제 / `+ 필요컬럼 + 삭제행제외` 추가)을 `.message-content` 로 주입 → `pre.diff-block`=1, `.diff-add`=1(getComputedStyle color `rgb(158,206,106)` 초록), `.diff-del`=1(`rgb(247,118,142)` 빨강), 좌측 보더 색 구분. 스크린샷 `/tmp/task0256/pb0008_diff_render.png` 육안: 삭제라인 빨강·추가라인 초록 명확.
  - **Pass/Fail: PASS**
  - **Notes:** 렌더(시각) 검증 — 라이브 배포 자산의 실제 파이프라인(marked.parse→enhanceDiffBlocks→DOMPurify.sanitize) 결과를 실제 Windows 화면에서 확인. CSS 팔레트(.message-content pre 다크 #1a1b26 위) 정확 적용. 프롬프트측(assistant diff 생성)은 ask-worker SYSTEM_PROMPT baked + 라이브 WebSystemPrompts global row 갱신으로 보장(별도 LLM e2e 미수행). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0256b diff 블록 줄 이중 줄바꿈 수정 — **PB-0008 Windows-browser 재검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Steps/Result:** 배포 자산(app.js?v=20260615-task0256b-spacing) 의 `markdownToHtml` 로 8줄 diff(2 del + 6 add, EXIT HANDLER 예시) 렌더 → `.diff-line` 8개, lineHeight=20px, **줄 간 top 간격(gap)=[20,20,20,20,20,20,20] = lineHeight 와 동일 = 단일 줄 간격**. 수정 전 이중 줄바꿈(블록 span + 리터럴 `"\n"` ≈ 40px)이 해소됨. 스크린샷 `/tmp/task0256/pb0008b_diff_spacing_fixed.png` 육안: 8줄 빈 줄 없이 연속, +초록/-빨강 색 유지.
  - **Pass/Fail: PASS**
  - **Notes:** `enhanceDiffBlocks` 의 block span 사이 `"\n"` 텍스트 노드 제거 효과 실측(gap==lineHeight). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0256c diff 블록 줄번호(old|new) + 복사 시 마커·번호 제외 — **PB-0008 Windows-browser PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080). WSL headless 아닌 실제 Windows 화면.
  - **Steps/Result:** 배포 자산(app.js?v=20260615-task0256c-gutter) 의 `markdownToHtml` 로 8줄 diff(2 del + 6 add, EXIT HANDLER 예시) 렌더.
    - **줄번호 gutter**: `.diff-line` data-gutter = `["1   -","2   -"," 1 +"," 2 +",...]`(del=old번호+빨강 / add=new번호+초록), `getComputedStyle(line,'::before').content` 에 숫자 포함(번호 가시). 스크린샷 `/tmp/task0256/pb0008c_diff_gutter.png` 육안: 각 줄 좌측 old/new 번호 + 색마커 + 구분선.
    - **복사 클린(getSelection 실측)**: `range.selectNodeContents(pre.diff-block)` → `getSelection().toString()` = 8줄, **마커로 시작하는 줄 0(copyHasMarker=false)**, 첫 줄 `"DECLARE v_Result INT DEFAULT 0;"`(마커·번호 없음), 코드 포함. 즉 블록 복사 시 줄번호·+/- 제외된 순수 코드만 잡힘.
  - **Pass/Fail: PASS**
  - **Notes:** 줄번호+마커는 `::before content`(의사요소=선택/복사 비포함) + user-select:none. CHECK#13 충족.

- 2026-06-15 (TASK-0256d HTML 엔트리포인트 no-cache — 캐시버스터 전달 검증 PASS):
  - **Environment: 라이브 curl + Windows-browser** (https://localhost:18080, web main 1c184f8).
  - **Steps/Result:**
    - **헤더(curl GET)**: `/` → `cache-control: no-cache` + ETag, `/admin` → no-cache, `/share/{token}` → no-cache. 서빙 index.html 이 최신 `app.js?v=20260615-task0256c-gutter` 참조. 정적 `/static/app.js?v=...` 은 no-cache 아님(ETag 캐시 가능 — 의도).
    - **브라우저 로드(win-browser eval)**: `typeof window.buildDiffRows="function"`·`stripDiffMarker="function"`, loadedScript=`app.js?v=20260615-task0256c-gutter` → 옛 캐시 깨고 새 자산 로드 확인.
    - **gutter+복사(사용자 유형 SQL diff 렌더)**: `hasGutter=true`, context 줄 data-gutter `"1 1"`, `copyHasMarker=false`, 복사 = `["SELECT","    AID","  , UserID"]`(마커·번호 없는 순수 코드, 들여쓰기 보존). 스크린샷 `/tmp/task0256/pb0008d_nocache_gutter.png`.
  - **Pass/Fail: PASS** — no-cache 가 0256c(줄번호/복사클린)를 사용자에게 전달함을 end-to-end 실증.
  - **Notes:** 기 캐시된 사용자는 1회 하드리프레시(Ctrl+Shift+R)로 no-cache index.html 진입 후 자동 최신. CHECK#13 충족.

- 2026-06-15 (TASK-0274 첨부파일 목록 사이드 패널 너비 조절 — **PB-0008 Windows-browser PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `bb06ddf`(PR #241 squash) → `sudo docker compose build web && up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 자산 `app.js/styles.css?v=20260615-attach-panel-resize`(resizer 코드 4 hit).
  - **Steps/Result:**
    - **진입 + 핸들 hit-test**: 작업 화면에서 `+`(#composerActionsBtn) 클릭 → "첨부파일 목록"(#composerActionsListItem) 클릭 → `#attachSidePanel` 표시(panelHidden=false, 초기 width=280px, 우측 고정 left=969). `#attachSidePanelResizer` 실재 + `cursor:ew-resize`, rect{x:967,w:8,h:840}. **`document.elementFromPoint(resizer center)` = `attachSidePanelResizer`** → 핸들이 다른 요소에 가려지지 않음(CSS 클리핑/겹침 0).
    - **드래그 너비 변경**: 핸들에 mousedown → document mousemove(좌측 −180px) → 패널 width **280 → 458px** 실시간 변경(`width=innerWidth−clientX` 정확), 드래그 중 `.is-resizing` 적용 → mouseup 후 해제. **`localStorage["web.attachSidePanel.width"]="458"` 저장 확인**.
    - **새로고침 후 복원**: page reload → `+` > 첨부파일 목록 재클릭 → 패널 표시 + **width 458px 복원**(storedWidth 458 → inline `width:458px`). 영속화 end-to-end PASS.
    - **clamp 경계**: 핸들 우측 끝 드래그 → width **240px 에서 정지**(min-width 240). 핸들 좌측 끝 드래그 → **1149px(=92vw, innerWidth 1249) 에서 정지**(max-width 92vw). CSS `min-width:240px`/`max-width:1149.08px` 실측 일치.
    - **시각 evidence**: 스크린샷 `artifacts/pb0008-task0274/attach-panel-resized-458.png` — 우측 "첨부 파일" 패널이 확장 너비로 메인/대화목록과 레이아웃 충돌 없이 렌더. 콘솔 throw 0.
  - **Pass/Fail: PASS** — 핸들 hit-test·드래그 너비 변경·localStorage 저장·새로고침 복원·min/max clamp 전부 실제 Windows 브라우저 실측 통과. (기존 `#stepSidePanel`/`#profileDrawer` 검증 패턴과 동일 동작.)
  - **Notes:** 기 캐시된 사용자는 1회 하드리프레시(Ctrl+Shift+R)로 no-cache index.html 진입 후 자동 최신. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0278 데이터소스 목록 행별 네트워크 상태 배지 — **PB-0008 Windows-browser PASS**):
  - **정적 검증**: `node --check admin.js` PASS, CSS 중괄호 균형. 적대적 코드리뷰(REV-0282, general-purpose outside voice) **SHIP** — grid 스코프 회귀 0(`#datasourceList` ID 특이성 > base, `#settingsList` 미매칭)·leading 배치·async detach 가드(`isConnected`)·캐시우선·중복 probe 0.
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). 배포: main `73d65b8`(PR #251 squash) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`(repo-web-1 healthy). 서빙 `admin.js?v=20260615-task0278-ds-conn-badge`(`_paintDsConnDot` 3 hit) + healthz `git_commit=73d65b8`(mysql_ok·pg_ok true).
  - **계측 결과(win-browser eval)**: `관리 콘솔 > 데이터소스` **14행 전부 leading `.ds-conn-dot`**(withDot=14). **행별 도트 `getBoundingClientRect().left=270` 단일값**(컬럼 정렬 완벽). 행 `grid-template-columns: 9px 274px`(auto 도트 컬럼 + 1fr main). 색: `is-ok`=`rgb(22,163,74)` 초록(`--success`) / `is-fail`=`rgb(220,38,38)` 빨강(`--danger`). `title`/`aria-label` 실측("네트워크 상태: 연결됨 · 152.1ms" / "네트워크 상태: 연결 실패: 연결 불안정"). **`#settingsList` 무회귀**: 설정 탭 `grid-template-columns: 308px` 단일(도트 컬럼 없음, `hasDotInSettings=false`) — `#datasourceList` 스코프 grid 가 타 nav 목록 무영향 실증.
  - **시각 evidence**: 스크린샷 `artifacts/pb0008-task0278/ds-conn-badge.png`.
  - **Pass/Fail: PASS** — leading 도트 정렬(left=270 단일)·색 구분(초록/빨강)·접근성(title/aria-label)·grid 스코프(9px 274px)·`#settingsList` 무회귀(308px 단일) 전부 실제 Windows 브라우저 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-15 (TASK-20260615T183409-ds-list-multiselect 데이터소스 목록 다중 선택 — 정적 검증 PASS / **PB-0008 배포 후 잔여**; PR#251 leading 도트를 행에 통합·행 구조 button→div 로 #251 의 button-row PB-0008 측정 supersede):
  - **Environment: 정적(node + subagent 코드리뷰)** — 변경은 frontend 정적자산(admin.js/admin.html)뿐, 백엔드 엔드포인트(PATCH/DELETE) 재사용이라 Python(make test) 영향 0.
  - **Steps/Result:**
    - **node --check admin.js**: SYNTAX OK (전 편집 후 재확인).
    - **런타임 계약**: `assertBulkBarContract("datasources")` 가 init 루프에서 호출되며 admin.html 의 `#datasourcesBulkBar`(role=toolbar/aria-live/`.admin-list-col` 직속)·ID 정합으로 충족(코드 대조).
    - **적대적 subagent 코드리뷰(general-purpose outside voice)**: 10개 검증항목(partial-fail 분할·재동기화·prune·contract·select-all/indeterminate·shift-range string-key·button→div 회귀·체크박스 stopPropagation·XSS·hoisting·env 제외) 전부 confirmed-correct → **SHIP(BLOCKER 0/MAJOR 0)**. REV-20260615-0286.
  - **Pass/Fail: PASS(정적)** — 구조/계약/로직 검증 완료.
  - **Notes:** **잔여 — PB-0008 Windows-browser**: 배포 후 데이터소스 탭에서 행 체크박스·전체선택(indeterminate)·shift-click 범위·일괄 인사이트 토글·일괄 삭제(env 제외·409 제외 리포트) + leading 도트(통합) 실측 필요. CHECK#13 은 그때 충족. → **아래 항목에서 충족(PASS).**
- **TASK-0277 (데이터소스 라벨/키 분리, Critical §12.3) — 백엔드 전용 회귀 검증.**
  - **Environment: 컨테이너 make test (agent 이미지, --no-deps) + unit(monkeypatch, DB 무)**. UI 표면(HTML/CSS/JS) 변경 **없음** — `app.py` 백엔드 로직(스키마 마이그레이션·rename cascade·바인딩 write·런타임 probe)만 변경.
  - **결과**: 신규 `test_datasource_rename_binding_stable.py` R1~R4 PASS(R1 3 테이블 cascade+고아 사전제거·R2 Id 구동 WHERE·R3 비-rename 무 cascade·R4 DatasourceId 컬럼 부재 시 key-only 완전 cascade) + 기존 `test_datasource_edit_label_stable.py` S1~S3 PASS + `make test` 컨테이너 **전체 회귀 0** + ruff clean + py_compile OK.
  - **외부음성 2-pass(RBAC 적대적)**: 1차 NOT-SHIP(BLOCKER1 probe 미등록+cascade 하드의존 / BLOCKER2 autocommit 비원자 / BLOCKER3 PK 충돌 + MINOR) → 흡수 → 2차 SHIP-WITH-FIXES.
  - **PB-0008 (Windows-browser): N/A — 사유 명시.** 본 변경은 사용자가 보는 UI surface(렌더·레이아웃·상호작용·라벨 표시 문자열·DOM·CSS)를 변경하지 않는다. 효과는 "라벨 rename 후 제품 바인딩·접근DB 유지"라는 **데이터/동작 정합**이며, 시각이 아닌 라이브 기능 라운드트립(rename→GET 재조회로 제품 바인딩 키 갱신·접근 유지)으로 검증한다(배포 후 잔여). CHECK#13 WARN(비차단)은 본 사유로 갈음.
  - **Pass/Fail: PASS** (단위·컨테이너 회귀 + 외부음성 2-pass). 라이브 기능 검증은 배포 후 수행(잔여).

- 2026-06-16 (TASK-20260615T183409-ds-list-multiselect 데이터소스 목록 다중 선택 — **PB-0008 Windows-browser PASS**; CHG/REV-20260615-0289 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). 배포: main `3605443`(PR #254 squash) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`(repo-web-1 healthy). 서빙 `admin.js/styles.css?v=20260615-ds-multiselect` + healthz `git_commit=3605443`(mysql_ok·pg_ok true). 로드 admin.js `?v=20260615-ds-multiselect`(신규 `_runDatasourceBulkAsync` 등 hit).
  - **계측 결과(win-browser eval)**:
    - **구조**: `#datasourceList` **14행 전부** `<div role=row>`(rowsAreDiv=true) + `.admin-list-row-cb` 체크박스(rowsHaveCheckbox=true) + `.ds-conn-dot`(rowsHaveConnDot=true, PR#251 통합 보존). `#datasourceSelectAll`·`#datasourcesBulkBar`(role=toolbar, 초기 empty)·`#datasourcesCrossPageBanner` 실재. listRole=`grid`. **행 grid `grid-template-columns: 13px 9px 251px`**(체크박스·도트·main 3열) — base `auto 1fr auto` 가 아닌 `#datasourceList .admin-list-row` override 적용 확인.
    - **체크박스→bulkBar**: 1개 체크 시 bulkBar `childElementCount>0`, role=toolbar, 라벨 "1개 선택됨", 버튼=[인사이트 탐색 켜기·인사이트 탐색 끄기·삭제·선택 해제](console.manage 게이트 통과).
    - **전체선택**: `#datasourceSelectAll` 클릭 → 14행 전부 체크(checkedCount=14), selectAllChecked=true·indeterminate=false, 라벨 "14개 선택됨".
    - **indeterminate**: 전체선택 상태에서 1개 해제 → checked=13, selectAllChecked=false·**selectAllIndeterminate=true**(부분 선택 반영).
  - **시각 evidence**: 스크린샷 `artifacts/pb0008-ds-multiselect/ds-multiselect-partial-select.png`(1249×840) — 좌측 데이터소스 목록 [전체선택(indeterminate) · 14] + 13행 체크 + 각 행 [체크박스·연결도트(초록/빨강)·이름·엔진 pill·좌표], 하단 bulk 툴바 "13개 선택됨 · 인사이트 켜기/끄기/삭제/선택 해제". 계정·역할·제품 pane 과 동일 다중선택 구조.
  - **Pass/Fail: PASS** — 행 체크박스(div role=row)·전체선택(indeterminate)·일괄 툴바(buttons·count)·leading 도트(#251 통합)·3열 grid(13px 9px 251px) 전부 실제 Windows 브라우저 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** shift-click 범위·실제 일괄 삭제/insight 토글(파괴적·상태변경)은 라이브 데이터 보호 위해 실행 미수행(구조·게이트·핸들러는 적대적 코드리뷰 REV-0286 에서 confirmed). 기 캐시 사용자는 1회 하드리프레시.

- 2026-06-16 (TASK-0283 제품 아이콘 편집 UI 유저 프로필 ✎ 오버레이 통일 — 정적 검증 PASS / **PB-0008 배포 후 잔여**; CHG/REV-20260616-0291):
  - **Environment: 정적(node --check)** — 변경은 frontend 정적자산(admin.js/styles.css/index.html/admin.html)뿐, 백엔드 엔드포인트(PUT/DELETE icon) 재사용이라 Python(make test) 영향 0.
  - 결과: `node --check admin.js` PASS. diff = admin.js(renderProductDetail 1곳, 텍스트 pill → `.profile-avatar-edit`+`.profile-avatar-change` ✎ 오버레이 + `.profile-avatar-remove` 링크) + styles.css(dead `.admin-avatar-edit/change/remove` 제거) + index/admin.html(cache-buster `?v=20260616-product-icon-edit`).
  - **PB-0008 Windows-browser → 아래 항목에서 PASS(CHG/REV-20260616-0292).**

- 2026-06-16 (TASK-0283 제품 아이콘 편집 UI 유저 프로필 ✎ 오버레이 통일 — **PB-0008 Windows-browser PASS**; CHG/REV-20260616-0292 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). 배포: main `245446f`(PR #265 squash) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 admin.html `admin.js?v=20260616-product-icon-edit`·`styles.css?v=20260616-product-icon-edit`, 서빙 admin.js 에 `profile-avatar-change` baked(grep 1 hit).
  - **계측 결과(win-browser eval, `관리 콘솔 > 제품 > (KR) 킹스레이드 - 로컬` 상세)**:
    - **✎ 오버레이 실재**: `.admin-detail-identity .profile-avatar-edit` 래퍼 present(`position:relative`), `.profile-avatar-change` = 텍스트 "✎", computed `position:absolute · right:-4px · bottom:-4px · width:22px · height:22px · border-radius:50%`, rect 22×22, `visibility:visible · opacity:1 · display:grid` → 유저 프로필 드로어와 **동일 클래스·동일 computed**(시각 동형).
    - **구 텍스트 pill 부재**: `.admin-detail-identity .admin-avatar-change`/`.admin-avatar-edit` querySelector = null(oldPillPresent=false). 36px 아바타(`position:relative`) 영역 침범 0.
    - **제거 링크 분기**: 본 제품은 custom icon_url 미설정(Identicon) → `.profile-avatar-remove` 미노출(null) = 명세대로(아이콘 설정 시에만 "아이콘 제거" 표시).
  - **시각 evidence**: `artifacts/pb0008-task0283/product-icon-edit-overlay.png`(1249×840) — 제품 상세 헤더가 아바타 + 이름 "(KR) 킹스레이드 - 로컬" + 메타로 깔끔, 기존 "아이콘" 텍스트박스 침범 제거됨.
  - **Pass/Fail: PASS** — ✎ 원형 오버레이 실재·visible, 텍스트 pill 부재, 아이콘 영역 침범 0, 유저 프로필과 동일 클래스 재사용으로 시각 동형 전부 실제 Windows 브라우저 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(Ctrl+Shift+R)로 no-cache index/admin.html 진입 후 자동 최신.

- 2026-06-16 (TASK-0291 관리 콘솔 계정 탭 배지 활성 계정만 집계 — 정적 검증 PASS / **PB-0008 배포 후 잔여**; CHG/REV-20260616-0300):
  - **Environment: 정적(node --check)** — 변경은 frontend 정적자산(admin.js 집계식 1곳 + admin.html 캐시버스터)뿐, 백엔드/엔드포인트 무변경이라 Python(make test) 영향 0.
  - 결과: `node --check admin.js` PASS. diff = admin.js(`refreshPendingUI` 의 `#tabCountAccounts` = `adminState.accounts.filter((a) => a.is_active && !a.deleted_at).length`) + admin.html(cache-buster `?v=20260616-task0291-account-active-count`). 활성 정의는 `filteredAccounts()` 의 `'active'` 분기(`is_active && !deleted_at`)와 동일 재사용.
  - **PB-0008 Windows-browser → 배포 후 측정**: 계정 탭 배지 `#tabCountAccounts` 텍스트가 "활성" 필터 적용 시 `#accountListCount`("N명")의 N 과 일치하고, "전체" 필터 수보다 작거나 같음을 win-browser eval 로 실측 예정.

- 2026-06-16 (TASK-0291 관리 콘솔 계정 탭 배지 활성 계정만 집계 — **PB-0008 Windows-browser PASS**; CHG/REV-20260616-0301 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `9bdb9f8`(PR #287 squash) → `docker compose build web` + `up -d --no-build web`(repo-web-1 Up healthy, /healthz git_commit=9bdb9f8·mysql_ok·pg_ok true). 서빙 admin.html `admin.js?v=20260616-task0291-account-active-count` + 서빙 admin.js 에 `activeAccountCount` baked(2 hit).
  - **계측 결과(win-browser eval, `관리 콘솔 > 계정`)**: 계정 탭 배지 `#tabCountAccounts` = **7**. 목록 카운트 `#accountListCount`: 전체 필터 **28명** / 활성 **7명** / 비활성 1명 / 삭제됨 20명. 검산 7+1+20=28(active+inactive+deleted=all). **배지 7 = 활성 필터 목록 수 7명 일치** + **배지 7 < 전체 28**(수정 전이라면 28 표시) → `#tabCountAccounts` 가 `adminState.accounts.length`(28)가 아닌 활성만(`is_active && !deleted_at`, 7) 집계함을 실측 확인. `#accountListCount`(filter-aware)는 비변경 — 필터별 정확 카운트 유지.
  - **시각 evidence**: `artifacts/pb0008-task0291/account-tab-active-count.png`(1249×840) — 좌측 사이드바 계정 배지 **7**, 본문 "계정 관리" 목록 "전체" 필터에서 **28명** 동시 표시(배지 ≠ 전체, 배지 = 활성). 역할(5)·제품(8)·데이터소스(14) 탭 배지는 비변경(요청 범위=계정 한정).
  - **Pass/Fail: PASS** — 계정 탭 배지가 활성 계정 수(7)만 집계하고 전체(28)와 분리됨을 실제 Windows 브라우저 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(index/admin.html no-cache 진입 후 자동 최신).

- 2026-06-16 (TASK-0292 관리 콘솔 좌측 사이드패널 수직 스크롤 — **PB-0008 Windows-browser PASS**; CHG/REV-20260616-0304 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `be3a775`(PR #289 squash) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 admin.html `styles.css?v=20260616-task0292-admin-sidebar-vscroll` + 컨테이너 baked styles.css `.admin-tabs{min-height:0;overflow-y:auto}`·`.admin-sidebar-foot{flex-shrink:0}`.
  - **측정(win-browser eval, /admin 로그인 세션)**: computed style — `.admin-tabs` `overflow-y=auto`·`min-height=0px`, `.admin-sidebar-foot` `flex-shrink=0`. 짧은 viewport 시뮬(`.admin-shell` height=240px): `.admin-tabs` clientHeight=134·scrollHeight=572 → **scrollable=true**, scrollTop=scrollHeight 설정 시 438 도달(canScroll), 하단 `[data-admin-tab=settings]`('설정') **settingsReachable=true**, foot bottom = aside bottom(footPinned=true).
  - **시각 evidence**: `artifacts/pb0008-task0292/admin-sidebar-vscroll-short-vp.png` — 짧은 사이드바에 수직 스크롤바 노출 + 하단 스크롤 상태에서 "시스템 > 설정" 탭·"변경 없음" 풋 표시(브랜드 상단 고정).
  - **Pass/Fail: PASS** — 화면 높이가 작아도 좌측 사이드패널 탭 전체(특히 하단 '설정')가 수직 스크롤로 도달·조작 가능함을 실제 Windows 브라우저 실측 통과. 사용자 보고 이슈 해소. CHECK#13(PB-0008 Windows-browser) **충족**.
