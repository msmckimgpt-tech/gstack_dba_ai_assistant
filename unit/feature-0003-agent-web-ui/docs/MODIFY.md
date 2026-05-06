---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260506-0024
- Date: 2026-05-06
- Summary: TASK-0048 후속 fix — backend `_repair_current_conversation` 호출처 5 곳의 `create_if_missing=_account_has_permission(...)` 자동 생성 분기를 모두 비활성화. 사용자 보고 회귀 ("대화 삭제 시 새 대화가 그대로 남는 이슈") 의 근본 원인은 `/api/delete_conversation` 응답 `current` 필드가 backend 의 자동 생성 분기로 또 다른 빈 cid 를 발급해서 frontend 가 그것을 active 로 채택해 사이드바에 다시 등장하던 것. lazy 정책의 일관성을 backend 전 경로에 적용한다.
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - `_build_conversations_payload` (L3412 부근): `create_if_missing=can_create` 분기 제거, `create_if_missing=False` 고정. 후속 재호출 단계도 단일화.
    - `/api/session` 응답 조립 (L3737 부근): `create_if_missing=False`.
    - `/api/history` 의 conv resolver (L4470 부근): `create_if_missing=False`.
    - `/api/delete_conversation` pending 케이스 (L4651 부근): `create_if_missing=False` + 회귀 사유 주석.
    - `/api/delete_conversation` 일반 케이스 (L4662 부근): `create_if_missing=False`.
    - `/api/ask` 의 lazy creation (L3851): `create_if_missing=True` 그대로 보존 — 사용자가 명시적으로 메시지를 보낼 때만 row 가 만들어지는 경로 유지.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과.
  - `make web` EXIT=0 + `repo-web-1 Recreated/Started` 후 새 코드 deploy.
  - 시나리오 검증 (HTTP API):
    1. `/api/conversations` 호출 → row delta=0 (이전엔 빈 대화 자동 생성). items=46 정상 listing.
    2. `/api/session` 호출 → row delta=0.
    3. `/api/new_conversation` 으로 빈 대화 1건 생성 (delta=+1, backward-compat 경로) → 그 cid 를 `/api/delete_conversation` 으로 삭제 → 응답 `{"deleted":"...","current":""}`, row delta=-1. **이전엔 응답의 current 가 새 자동 생성된 cid 였고 frontend 가 그것을 active 로 채택해 사이드바에 또 빈 대화가 등장**. fix 후엔 current="" 라 frontend 가 "대화를 선택하세요" 상태로 떨어진다.
- Risks:
  - 마지막 대화를 삭제한 사용자는 backend 가 자동으로 새 대화를 만들어주지 않는다 — frontend 가 "대화를 선택하세요" 헤더 + 사이드바 empty-state 를 표시하고 사용자가 명시적으로 "새 대화" 버튼을 눌러야 한다. 이는 TASK-0048 lazy 정책의 의도된 결과이며 사용자 보고 회귀의 직접 해결책.
  - 다른 호출처(`/api/use_conversation`, `/api/cancel`, `/api/finalize` 등) 에서 `_resolve_conversation_for_account` 의 default 가 이미 `False` 라 영향 없음.

## CHG-20260506-0023
- Date: 2026-05-06
- Summary: TASK-0051 (REQ-20260506-0004) 관리 콘솔 일괄 저장 정책 회복 + 메타데이터 4 스키마 항상 노출 + DB 목록 라이브 enum — 인라인 save 버튼 3 종(`프롬프트 저장` / `제품 정보 저장` / `DB 목록 저장`) 제거 후 footer `모두 적용` 단일 commit 흐름으로 통합. 메타데이터 4 종(`information_schema`/`mysql`/`sys`/`performance_schema`) 을 회색 disabled chip 으로 강제 노출(REV-20260422-0006 정책 시각화). 자유 텍스트 chip 입력을 `GET /api/admin/databases/available` 라이브 enum 기반 picker 로 교체. C5(계정·역할 → 제품 권한 상속/override) 는 다음 cycle 분리(plan-eng-review 후 진행 권고).
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - L5897~ 신규 `GET /api/admin/databases/available` 엔드포인트 추가. `_account_has_permission(account, "console.access")` 게이트 후 `_open_memory_connection(database=None)` 으로 `SHOW DATABASES` 실행. 결과를 `metadata_schemas`(고정 4 종 + `present` flag) / `user_schemas`(메타·`agent_memory`·`MEMORY_DB`·정규식 위반 제외 + 정렬) 로 분리해 반환. 모듈 상수 `_DATABASES_AVAILABLE_METADATA` / `_DATABASES_AVAILABLE_INTERNAL` / `_DATABASES_AVAILABLE_NAME_RE` 추가.
  - [unit/feature-0003-agent-web-ui/src/static/admin.js](../src/static/admin.js)
    - `adminState` 에 `availableDatabases` 와 `pending.{productMeta, productDatabases, systemPrompts}` 3 buckets 추가. `METADATA_SCHEMAS`/`INTERNAL_SCHEMAS` 상수 + `systemPromptPendingKey()` 헬퍼 추가.
    - `pendingChangeCount()` 에 신규 buckets 합산. `setProductMetaPending` / `setProductDatabasesPending` / `setSystemPromptPending` / `getSystemPromptPending` 헬퍼 신규.
    - `refreshPendingUI()` 의 `commitBarDetail` 에 신규 카테고리 (제품 정보 / 제품 DB / 프롬프트) 표시.
    - `cancelAllPending()` 이 신규 buckets + `productDbDraft` 까지 clear.
    - `loadAdminData()` 가 `Promise.all` 에 `/api/admin/databases/available` 추가 + 제품/역할/계정 삭제 시 stale pending entry GC.
    - `renderProductDetail()`: `saveMetaBtn` / `saveDbBtn` 두 버튼 제거. name/desc/active/default/sort 입력 변경 → `setProductMetaPending`. chip wrap 상단에 메타 4 종 locked chip 강제 prepend(× 없음, `is-locked` 클래스 + `항상 접근` 라벨). 자유 텍스트 input 을 `<select>` picker 로 교체 — 옵션은 user_schemas 에서 메타·내부·이미 등록된 schema 제외. chip × 클릭 / picker 추가 시 `setProductDatabasesPending`. dbHint 끝에 메타 4 종 정책 안내 한 줄 추가.
    - `buildSystemPromptEditor()`: `saveBtn` / `clearBtn` 제거. textarea 위에 안내 메시지 ("변경사항은 하단 '모두 적용' 버튼으로 일괄 저장됩니다") 추가. textarea `input` 이벤트 → `setSystemPromptPending`. `refresh()` 가 pending entry 우선 사용해 사용자 입력 보존.
    - `applyAllPending()` 6 단계로 확장 — 기존 accounts/roles/newRoles 뒤로 productMeta(PATCH `/api/admin/products/{id}`) → productDatabases(PUT `/api/admin/products/{id}/databases`) → systemPrompts(PUT `/api/admin/system-prompts`) 순서. 실패는 기존 `failures` 배열에 합류.
    - `renderDashboard()` `dashboardPendingList` 에 productMeta / productDatabases / systemPrompts 3 카테고리 row 추가. `describePatchKeys` 에 `is_default`/`sort_order` 라벨 추가.
  - [unit/feature-0003-agent-web-ui/src/static/styles.css](../src/static/styles.css)
    - `.admin-chip.is-locked` (회색 + `cursor: not-allowed` + opacity 0.85), `.admin-chip-locked-hint` (소형 라벨), `.admin-db-picker-row`, `.admin-db-picker` (select + disabled 상태) 추가. 기존 `--text-muted` / `--border-subtle` 토큰 사용.
  - [unit/feature-0003-agent-web-ui/src/static/admin.html](../src/static/admin.html)
    - cache-bust query 를 `v=20260506-batch-commit` 로 갱신 (styles.css / admin.js 양쪽).
- Verification:
  - (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과.
  - (b) `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` 통과.
  - (c) `grep -n "프롬프트 저장\|제품 정보 저장\|DB 목록 저장\|saveMetaBtn\|saveDbBtn\|clearBtn"` admin.js 에서 0 hit (3 개 인라인 save 버튼 + 그 핸들러 변수 모두 제거 확인).
  - (d) `grep -c "/api/admin/databases/available" admin.js app.py` → 양쪽 1 hit (FE / BE 한 쌍).
  - (e) 컨테이너 재빌드(`make web`) + UX smoke 는 사용자 환경에서 진행 예정 (재빌드 후 cache-bust 가 반영돼야 신규 admin.js 가 브라우저에 로드됨).
- Range: backend 1 파일 +60 lines, FE admin.js ~+200 lines (인라인 save 핸들러 제거 + pending 통합 + locked chip + picker), styles.css +44 lines, admin.html cache-bust 2 lines.
- Notes: REV-20260422-0006 의 메타 4 종 bypass 정책은 시각화만 변경했고 backend tool-level (`tools.py` `_METADATA_SCHEMAS`) 은 손대지 않았다 — agent 실행 동작에는 영향 없음. C5(계정·역할 → 제품 권한 상속/override) 는 신규 테이블(`WebRoleProductAccess`/`WebAccountProductAccessOverrides`) 마이그레이션 + RBAC override 모델(TASK-0024) 충돌 검토 + `compose_system_prompt` product 조회 경로 영향 분석이 필요해 별 cycle 로 분리. 진입 전 `/plan-eng-review` 권고. 권한 게이트 약함(`console.access` 만으로 DB 목록 enum 가능)에 대한 위협 모델: enum 결과는 schema 이름 / 존재 여부에 한정되며 row 데이터 노출은 없고, 실제 등록은 `product.manage` 권한 게이트의 PUT `/api/admin/products/{id}/databases` 가 그대로 유지된다 (`agent_memory` / `mysql.user` 등 민감 schema 자체는 user_schemas 에서 제외).

## CHG-20260506-0022
- Date: 2026-05-06
- Summary: TASK-0050 (REQ-20260506-0003) `make web` 의 docker compose v5.1.1 + buildx v0.31.1 provenance metadata file race 회피 — Makefile 에 `dc-build SERVICE=...` reusable 가드 타깃 추가, `web` 타깃을 build/up 분리.
- Files:
  - `Makefile`
    - `.PHONY` 목록에 `dc-build` 추가
    - `dc-build` 타깃 신설 — `$(DC_QUIET) build $(SERVICE)` 호출 + 임시 로그 캡처. EXIT≠0 + 로그에 `compose-build-metadataFile` 문자열 포함 시에만 EXIT=0 으로 정규화 (다른 빌드 오류는 그대로 전파). `SERVICE` 인자 검증 포함.
    - `web` 타깃을 `up -d --build web` 단일 호출에서 `$(MAKE) -s dc-build SERVICE=web` + `$(DC_QUIET) up -d --no-build web` 의 2 단계로 분리. image 를 미리 만들어 두고 컨테이너 교체만 별도 단계로 수행.
- Verification:
  - `make web` EXIT=0, 로그에 `[make] note: docker compose v5.1.1+buildx v0.31.1 의 provenance metadata file race 우회 — web image 빌드 OK, compose EXIT=1 무시` 출력. `Container repo-web-1 Recreate/Recreated/Started` 후 `Web UI (HTTPS): https://localhost:18080` 노출.
  - `docker exec repo-web-1 grep -n PENDING_CONV_SENTINEL /app/web/static/app.js` 으로 TASK-0048 의 새 코드가 컨테이너에 반영됨을 확인.

## CHG-20260506-0021
- Date: 2026-05-06
- Summary: TASK-0049 (REQ-20260506-0002) 누적된 빈 대화 일괄 정리 — `bin/cleanup-empty-conversations.sh` 추가 + 운영 데이터 1회 적용.
- Files:
  - `bin/cleanup-empty-conversations.sh` (신규, executable)
    - dry-run 기본 + `--execute` 명시 시 DELETE
    - `--owner-account-id <N>` 으로 계정 한정 가능 (정수 정규식 검증)
    - `--keep-recent-min <분>` 으로 최근 N분 이내 대화 보호 (default 5)
    - `AgentMemoryKv.last_status='processing'` 인 대화 보호 (실행 중 ask race)
    - SQL 주입 방지: 모든 인터폴레이션 변수 정수 정규식 검증, AgentCoreConversations / AgentMemoryMessages collation 차이는 `COLLATE utf8mb4_unicode_ci` 명시 변환
    - DB password 는 `.env` 의 `DB_PASSWORD` 에서 읽어 git 추적 대상이 아닌 값으로 처리
- Verification:
  - dry-run: `would_delete=42, oldest=2026-04-15, newest=2026-04-30 10:41:10` (5분 이내 row 1건 보호 확인).
  - execute: `88 conversations / 42 empty / 46 non-empty → 46 conversations / 0 empty / 46 non-empty` (방금 만든 backward-compat 검증 row 도 5분 보호 cutoff 통과해 정리됨).
  - 보호 검증: `processing` last_status 를 갖는 대화는 dry-run sample 에 포함되지 않음 (별도 query 로 0 건 확인).

## CHG-20260506-0020
- Date: 2026-05-06
- Summary: TASK-0048 (REQ-20260506-0001) "새 대화" 생성 시점을 lazy 화 — 버튼 클릭 시 client-side pending state 만 표시하고, 첫 메시지 전송 시 `/api/ask` 의 lazy creation path 가 실제 row 를 만들도록 전환. 기존에 사용자가 새 대화 버튼만 누르고 메시지를 보내지 않으면 `AgentCoreConversations` 에 빈 row 가 누적되던 문제를 신규 row 측에서 차단.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state` 에 `pendingNewConversation: false` + 모듈 상수 `PENDING_CONV_SENTINEL = "__pending__"` 추가
    - `isCurrentConvBusy()` 가 pending 모드에서 sentinel 도 검사
    - `renderConversationList()` 가 pending 모드면 빈 `state.conversations` 에서도 그룹을 그리고 "내 대화" 그룹 상단에 placeholder (`conv-item is-own is-active is-pending`) prepend. 기존 `renderGroup` 시그니처에 `prependFn` optional 인자 추가
    - `renderConversationHeader()` 가 pending 일 때 "새 대화" + "첫 메시지를 입력하면 대화가 만들어집니다." 표시
    - `beginPendingConversation()` 신설 — backend 호출 없이 `state.pendingNewConversation=true`, `activeConversationId=""`, `messages=[]` + 사이드바/헤더/composer 리렌더 + 입력란 포커스
    - `selectConversation()` 시작에 pending 자동 종료 분기
    - `sendPrompt()` 에 lazy create 분기:
      - `isLazyCreate = isPending || !state.activeConversationId` 판정
      - busy sentinel `PENDING_CONV_SENTINEL` 사용 + lazy create 시 progress polling 시작 보류
      - `/api/ask` body 에 `product_mode` / `product_id` hint 첨부 (사용자 직전 의도 보존)
      - 응답에 `conversation_id` 가 있으면 `state.pendingNewConversation=false` + `state.activeConversationId=newCid` 채택
      - lazy create 단계의 ask 실패는 attach/resume 다이얼로그 대신 재시도 안내 토스트 (cid 발급 여부가 client 에 불확실)
    - `newConversationBtn.click` 핸들러를 `createConversation()` → `beginPendingConversation()` 로 교체. 기존 `createConversation()` 함수는 다른 호출처 호환을 위해 보존
  - `unit/feature-0003-agent-web-ui/src/app.py`
    - `/api/ask` — `request_conversation_id` 가 비어 lazy 생성된 경로에서 body 의 `product_mode` / `product_id` hint 를 normalize 후 `AgentCoreConversations.product_id/product_mode` 셋업 + `_save_account_product_pref` 호출. `request_conversation_id` 명시 경로에는 무시 (TASK-0047 의 PATCH race 가드 단독 진실 보존). hint 적용 실패는 ask 자체를 막지 않고 default fallback.
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust `v=20260429-product-selector` → `v=20260506-pending-conv` (styles.css, app.js 양쪽).
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.conv-item.is-pending` 1 selector 그룹 추가 (border-dashed + faded text + cursor:default). 토큰만 사용(`--text-2`, `--text-muted`, `--border`).
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과 예정 (재빌드 단계).
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` 통과 예정.
  - frontend 흐름 inspection: 새 대화 버튼 → backend round trip 0회, placeholder 표시. 첫 메시지 → `/api/ask` 1회 (lazy create + product hint 적용). 응답 `conversation_id` 채택 후 `refreshWorkspace`.

## CHG-20260430-0019
- Date: 2026-04-30
- Summary: TASK-0047 후속 — Playwright QA 실행 중 발견된 마이그레이션 누락 회귀(R-09 closed) + race-guard 검증 자동화.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py` `_runtime_tables_available` — 신규 컬럼(`product_mode`, `ProductPrefMode`, `ProductPrefPinnedId`) 존재 여부도 probe 에 포함. errno 1054 (Unknown column) 도 1146 과 함께 False 반환 분기로 처리해 `_ensure_web_tables` idempotent ALTER 들이 자동 트리거되도록 함. **버그**: 기존 배포에서 새 컬럼 마이그레이션이 fast-path 로 우회되던 회귀를 제거.
  - `repo/.gstack/qa-reports/qa-product-selector.cjs` (신규) — Playwright 28-check QA spec. 검증 항목: AUTH/SESSION/BUST/MARKUP/CHIP/LABEL/PATCH/NEWCONV/UI/HYDRATE/RACE/CONSOLE. SQL 주입은 stdin 파이프로 nested-quote 회피.
  - `repo/.gstack/qa-reports/qa-product-selector-result.json` (생성) — 28/28 PASS, healthScore=100, console.error=0.
  - `repo/.gstack/qa-reports/screenshots/product-01..04.png` (생성) — 진단 스크린샷.
- Verification:
  - `docker compose build --no-cache web` (이전 `--build` 가 stale layer cache 로 신규 코드를 누락했음 — `--no-cache` 가 필수임을 학습).
  - 컬럼 검증: `SHOW COLUMNS FROM AgentCoreConversations LIKE 'product_mode'` → `product_mode varchar(8) NO '' pinned ''`. `SHOW COLUMNS FROM WebAccounts LIKE 'ProductPref%'` → 2 row.
  - QA spec 28/28 PASS:
    - 마크업/cache-bust/select 옵션/data-mode 동기화/localStorage 미러
    - PATCH 4 케이스(pinned 정상 / auto 정상 / pinned w/o product_id → 400 / 비존재 product_id → 400)
    - new_conversation 2 케이스(auto / pinned)
    - UI 인터랙션 2 케이스(select pinned ↔ auto)
    - 신규 auto 대화 hydrate
    - **PATCH race guard**: `AgentMemoryKv.last_status='processing'` 상태에서 PATCH → 409, 정리 후 → 200.
    - console.error 0.

## CHG-20260429-0018
- Date: 2026-04-29
- Summary: TASK-0047 — Product Selector 칩(사이드바) + Auto 모드 진입 UX. `product_mode` 컬럼/`WebAccounts.ProductPref*`/PATCH endpoint/agent_core auto 분기 추가, 한글 "상품" → "제품" 일괄 치환.
- Files:
  - `unit/feature-0002-agent-core/src/agent_core.py` — `compose_system_prompt(... , product_mode='pinned'|'auto')` 분기 추가, `run_agent`/`_run_agent_core` 시그니처에 `product_mode` 전달.
  - `unit/feature-0003-agent-web-ui/src/app.py` — DDL 2 컬럼 추가(AgentCoreConversations.product_mode, WebAccounts.ProductPrefMode/PinnedId), 헬퍼 4종(`_normalize_product_mode`, `_load_account_product_pref`, `_save_account_product_pref`, `_load_conversation_product`, `_conversation_is_processing`), `/api/session` 응답 확장(`product_pref`, `conversation_product`), `/api/new_conversation` body 확장(`mode`, pref upsert), `/api/ask` 분기(mode='auto' → product_id None + allowed_schemas=[]), 신규 `PATCH /api/conversations/{cid}/product` (race 가드 포함).
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — 사이드바 헤더에 `<div class="product-chip-wrap">` + caption + `<select id="productSelect">` 신설. cache-bust `?v=20260429-product-selector`.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.product-chip-wrap`/`.product-chip-caption`/`.product-chip[data-mode]`/`.product-chip-dot`/`.product-chip-select` 신설, mobile ≤720px 분기.
  - `unit/feature-0003-agent-web-ui/src/static/app.js` — state 3-필드 분리 (productMode/pinnedProductId/activeProductId), `renderProductOptions`/`renderProductChip`/`readProductPrefFromLocal`/`writeProductPrefToLocal`/`applyProductHydration`/`setActiveProduct` 신규, `initializeWorkspace`/`refreshWorkspace`/`selectConversation`/`createConversation`/`renderComposer`/`initialize` 흐름에 hydrate + lockout + select change 바인딩 추가, `PRODUCT_PREF_LS_KEY` 상수.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`, `unit/feature-0003-agent-web-ui/src/static/admin.js` — "상품" → "제품" 일괄 치환.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0047 entry.
  - `unit/feature-0003-agent-web-ui/docs/BRIEFING-product-selector-v1.md` (신규) — 차후 검증 항목(R-01..R-16) + 사람 확인 결정사항(D-01..D-05).
- Notes:
  - **사용자 검토 없이 agent team 4 인(UX/Frontend Architect/Backend Engineer/QA-Flow Validator) 합의 + Codex CLI 교차검증** 으로 진행됨. 운영 반영 전 D-01..D-05 결정과 R-01..R-16 검증 필요.
  - 마이그레이션은 idempotent(`try/except`) — 기존 행은 default `'pinned'` 로 backfill, NULL product_id 는 ask 진입 시 기존 default 채움 경로 보존.
  - "상품" → "제품" 치환은 사용자 가시 텍스트만. 코드 식별자(`Product`/`product_id`/`WebProducts`/`ProductKey`) 보존.

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: Web UI 앱과 정적 자산을 기능 단위 구조로 이관
- Files: src/app.py, src/static/*
- Notes: 코어 로직은 별도 feature에 유지

## CHG-20260414-0002
- Date: 2026-04-14
- Summary: 메인 워크스페이스를 작업 중심 콘솔 레이아웃으로 재개편하고 로그인/드로어/빠른 액션 UX를 재정의
- Files: src/static/index.html, src/static/styles.css, docs/TASK.md, docs/REPORT.md, docs/TEST.md
- Notes: 기존 기능 ID와 JS 결합은 유지하고, 시각 체계와 정보 배치를 전면 수정

## CHG-20260415-0003
- Date: 2026-04-15
- Summary: 계정/권한 체계를 실제 인증 모델로 교체하고, 대화 소유권과 관리자 화면 기준으로 Web UI를 전면 재구성
- Files: src/app.py, src/static/index.html, src/static/styles.css, src/static/app.js, src/static/admin.html, src/static/admin.js, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../.env
- Notes: `WebUsers`/`WebKeywords` 런타임 경로를 제거하고 `WebAccounts`/`WebAuthSessions`/`AgentCoreConversations.owner_account_id`를 기준으로 동작하도록 변경. 로컬 LLM 게이트웨이 미가용 시 false positive를 막기 위해 연결 가능 여부를 세션 응답에 반영

## CHG-20260415-0004
- Date: 2026-04-15
- Summary: App-Shell 기준 메인 레이아웃, 프로필 드로어, 병렬 대화 UX, 관리자 콘솔 사용성을 강화
- Files: src/app.py, src/static/index.html, src/static/styles.css, src/static/app.js, src/static/admin.html, src/static/admin.js, docs/TASK.md
- Notes: 사이드바 하단 프로필 트리거와 드로어 구조를 추가했고, `state.busyConversations`로 대화별 요청 상태를 분리했다. `/api/auth/me` 비밀번호 변경 엔드포인트, Admin 검색/필터/페이지네이션이 함께 추가되었다.

## CHG-20260415-0005
- Date: 2026-04-15
- Summary: 프로필 드로어를 3탭 구조로 재편하고 API Vault를 통합했으며, UI 정책/학습 문서를 최신화
- Files: src/static/index.html, src/static/styles.css, src/static/app.js, docs/AGENTS.md, docs/TASK.md, ../../../docs/LEARNINGS.md
- Notes: 계정별 설정을 탑바에서 제거하고 프로필 드로어의 `계정 / 보안 / API Vault` 탭으로 이동했다. 로그아웃 시 드로어 및 인증 폼 상태 초기화 규칙을 코드와 문서에 동시에 반영했다.

## CHG-20260415-0006
- Date: 2026-04-15
- Summary: 내장 Local LLM 소유 구성을 제거하고 외부 provider 소비 계약으로 전환
- Files: src/app.py, src/static/index.html, src/static/app.js, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../.env, ../../../../docker-compose.yml, ../../../../Makefile
- Notes: 현재 repo는 더 이상 Ollama/local-llm-gateway를 직접 기동하지 않는다. `LOCAL_LLM_API_BASE` 연결 가능 여부만 세션과 오류 메시지에 반영한다.

## CHG-20260416-0007
- Date: 2026-04-16
- Summary: Web UI 권한 모델을 RBAC + account override로 cutover하고 관리자 콘솔을 Accounts/Roles 2영역으로 재구성
- Files: src/app.py, src/static/index.html, src/static/app.js, src/static/admin.html, src/static/admin.js, src/static/styles.css, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../../../docs/STATUS.md
- Notes: role명 휴리스틱을 제거하고 `permission code + ownership`만으로 권한을 판정한다. `WebPermissions`/`WebRoles`/`WebRolePermissions`/`WebAccountPermissionOverrides`가 단일 정본이며, legacy `Role`/`Can*` 컬럼은 마이그레이션 원본으로만 남긴다. `/api/clear_memory`는 410으로 유지하고, 계정 삭제는 soft delete + 세션 폐기로 고정했다.

## CHG-20260421-0008
- Date: 2026-04-21
- Summary: 대화 사이드바의 내 계정/타 계정 대화 구분 하이라이트·정렬과 대화/말풍선 단위 fork(복제) 기능 도입
- Files: src/app.py, src/static/index.html, src/static/app.js, src/static/styles.css, docs/TASK.md, docs/FUNCTION.md, docs/REPORT.md, docs/REVIEW.md
- Notes: 사이드바는 `내 대화` / `타 계정 대화` 2 그룹으로 분할 렌더되고 내 대화는 primary 좌측 바 + 틴트, 타 계정 대화는 owner 뱃지를 강조한다. 말풍선 user 메시지에 `is-own-message` / `is-other-message` 톤 분리와 `나 (<username>)` / `<owner_username>` 라벨을 적용했다. 신규 `POST /api/fork_conversation` 은 `conversation.create` 권한과 원본 대화의 read 권한을 동시에 요구하며, 원본 `topic`(앞에 `[Fork] ` 접두사)과 메시지(internal 제외)를 `AgentMemoryMessages` 에 `CreatedAt` 보존 + `MetaJson.forked_from_*` 추가로 복제한다. 프론트엔드는 헤더 `대화 복사`(전체 복제), 말풍선 hover 액션 `여기서 분기`(부분 복제) 버튼을 제공한다.

## CHG-20260421-0009
- Date: 2026-04-21
- Summary: System Prompt Depth 3 계층(Product→Role→Account) + Product 단위 DB 접근 화이트리스트 도입
- Files: ../feature-0002-agent-core/src/agent_core.py, ../feature-0002-agent-core/src/modules/tools.py, src/app.py, src/static/admin.html, src/static/admin.js, src/static/index.html, src/static/app.js, src/static/styles.css, docs/TASK.md, docs/FUNCTION.md, docs/REPORT.md, docs/REVIEW.md
- Notes: 신규 테이블 `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` + `AgentCoreConversations.product_id` 컬럼 추가. `_runtime_tables_available` probe list 에 신규 3 테이블 포함해 기존 배포 재진입 시 자동 마이그레이션. 신규 permission `product.manage` / `system_prompt.manage.role.any` 를 `admin` 역할에 기본 부여, seed 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) 생성. `agent_core.compose_system_prompt` 가 base prompt 뒤로 `## PRODUCT CONTEXT` → `## ROLE GUIDANCE` → `## ACCOUNT PREFERENCES` 블록을 순차 append. `modules/tools.py` 에 모듈 전역 `_ACTIVE_SCHEMA_ALLOWLIST` + `set_/clear_active_schema_allowlist()` + `_whitelist_violation()` 을 두고, 모든 DB 도구 핸들러가 호출 직전 스키마 참조를 검사(`execute_sql` 은 `schema.table` 정규식 추출). `run_agent` 는 `allowed_schemas` kwarg 을 받아 try/finally 로 whitelist 를 세팅/복원하는 얇은 래퍼 + 본문 `_run_agent_core` 로 분리. 보안 수정: `_whitelist_violation` 에서 `_SYSTEM_SCHEMAS` 우회를 제거해 `mysql`/`performance_schema`/`sys`/`agent_memory` 직접 참조가 whitelist 로 차단되도록 했다. 관리 콘솔은 `계정 카테고리` / `상품 카테고리` 그룹 구분선 + `상품 (Products)` 탭(Product CRUD + 접근 DB chip 편집 + Product scope prompt 편집기) 을 추가, Roles detail 에 Role scope prompt 편집기(Product 드롭다운 포함), 프로필 드로우에 `프롬프트` 탭(Account scope) 을 추가. 신규 API: `GET/POST/PATCH/DELETE /api/admin/products`, `PUT /api/admin/products/{id}/databases`, `GET/PUT /api/admin/system-prompts`, `GET/PUT /api/auth/me/system-prompt`. 세션 응답에 `products` / `default_product_id` 포함. `/api/new_conversation` / `/api/fork_conversation` / `/api/ask` 가 대화 `product_id` 를 해석해 `run_agent` 에 `product_id`/`role_id`/`account_id`/`allowed_schemas` 를 전달.

## CHG-20260422-0011
- Date: 2026-04-22
- Summary: agent_core `OpenAI()` 초기화에 per-call `timeout` + `max_retries` 를 적용하고 TASK-0034 러너 `ASK_TIMEOUT_SEC` 을 서버 `run_timeout_sec` 이상으로 정렬
- Files: ../feature-0002-agent-core/src/agent_core.py, tests/task0034_runner.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md
- Notes: TASK-0034 Q4/Q5 실패 원인 분석에서 확인된 근본 원인 1(agent_core 의 `OpenAI(**client_kwargs)` 가 timeout 파라미터 없이 초기화돼 LLM 호출이 무한 대기) 과 근본 원인 2(러너 600s < 서버 900s 로 클라이언트가 먼저 포기해 좀비 스레드 발생) 를 동시 대응. 1) `agent_core.py:26~32` import 에 `AGENT_OPENAI_MAX_RETRIES` 추가, `agent_core.py:1134~1139` `client = OpenAI(**client_kwargs)` 를 `OpenAI(**client_kwargs, timeout=max(5,int(AGENT_TIMEOUT_SEC)), max_retries=max(0,int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장. 현재 `.env` 값 기준 `timeout=300s`, `max_retries=0`. 2) `tests/task0034_runner.py:52~56` `ASK_TIMEOUT_SEC=600.0` 을 `ASK_TIMEOUT_SEC=960.0` 으로 인상하고 산정 근거 주석(`max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)=900`) 추가. 검증: (a) `python3 -m py_compile` 통과, (b) `docker compose up -d --force-recreate web` 후 신규 컨테이너(StartedAt=2026-04-22T01:02:40Z) 기동, `docker exec grep` 으로 `timeout=max(5` 와 `AGENT_OPENAI_MAX_RETRIES` 반영 확인, `modules.config` import 시 `AGENT_TIMEOUT_SEC=300`/`AGENT_OPENAI_MAX_RETRIES=0` 확정, (c) bootstrap_admin 로그인 후 신규 대화로 `gpt-5.4-mini` 모델 `/api/ask` 한 턴 실행 — HTTP 200, wall=5s, steps_count=1, `list_schemas` + `SELECT FROM information_schema.schemata` 정상 실행.

## CHG-20260422-0010
- Date: 2026-04-22
- Summary: (문서화 전용) `/api/progress` 폴링 루프의 `setInterval` → 순번 기반 `setTimeout` + AbortController + 적응형 주기 리팩터 사후 리뷰 · 학습 기록
- Files: docs/TASK.md, ../../docs/LEARNINGS.md, docs/MODIFY.md
- Notes: 코드 변경 없음. TASK-0036 커밋(27127b9) 에 번들됐지만 commit message 에 언급되지 않은 폴링 리팩터를 TASK-0037 로 분리해 설계·검증·학습 내용을 사후 문서화한다. 검증: (a) `grep -c "setInterval" src/static/app.js` = 0, (b) 5 개 적응형 상수(`PROGRESS_FETCH_TIMEOUT_MS=4000`, `PROGRESS_POLL_ACTIVE_MS=1200`, `PROGRESS_POLL_IDLE_MS=3000`, `PROGRESS_POLL_HIDDEN_MS=10000`, `PROGRESS_POLL_ERROR_MS=8000`) 모두 `scheduleProgressPolling`/`pollProgress` 본문에서 실제 참조, (c) 서버 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 파라미터를 수용하고 서버 run_id 와 불일치 시 `next_after_step=0` 으로 리셋 (line 4405-4406), (d) `curl -sk -b cookie https://127.0.0.1:18080/api/progress?conversation_id=&client_run_id=STALE` 가 HTTP 200 + `{steps, status, status_at, step_count, run_id, conversation_id}` 스키마를 반환. `docs/LEARNINGS.md` 에 `LRN-20260422-0011 장시간 작업 폴링 5원칙(순번 기반 setTimeout 체인 + AbortController + 요청당 timeout + document.hidden 감지 + 서버측 delta with client_run_id)` 을 추가.

## CHG-20260422-0014
- Date: 2026-04-22
- Summary: 클라이언트 타임아웃 시 대화 지속 복구 경로 도입 — 서버 read-only 상태/결과 엔드포인트 2종 + 브라우저 복구 다이얼로그 + test runner attach 분기 (TASK-0041)
- Files: src/app.py, src/static/app.js, tests/task0034_runner.py, docs/TASK.md, docs/MODIFY.md, docs/REPORT.md, docs/FUNCTION.md, docs/REVIEW.md, ../../docs/LEARNINGS.md
- Notes: 사용자 요청(2026-04-22) — "클라이언트 타임아웃이 나타날 경우 해당 대화를 사용자 판단하에 지속적으로 처리할 수 있는 방법" 에 대응. 에이전트 작업자 스레드는 `asyncio.to_thread` 로 HTTP 연결과 독립적으로 실행되므로, 클라이언트(httpx/브라우저/proxy)가 ReadTimeout 으로 끊겨도 백엔드에서 계속 완료까지 진행한다. 이 자원을 회수할 read-only 경로가 없어 기존엔 결과가 유실됐다. `src/app.py` 에 `_ASK_TERMINAL_STATUSES={done,error,canceled}` / `_ASK_SUCCESS_STATUSES={done,canceled}` 상수와 `_load_run_meta_kv(conn, conversation_id)` 단일 쿼리 KV loader, `_build_ask_status_snapshot(conn, conversation_id)` 스냅샷 빌더, `GET /api/ask_status` (1-shot, `conversation.read.own/any` 권한) 과 `GET /api/ask_result` (long-poll `wait<=60s`, deadline/0.5s interval, terminal 시 assistant/steps 전문, 타임아웃 시 `{timeout:true}`) 2 엔드포인트를 추가. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 분리되어 attach 가 새로운 실행을 시작시키지 않는다. `src/static/app.js` 에 `ASK_ATTACH_POLL_WAIT_SEC=45` / `ASK_ATTACH_MAX_TOTAL_SEC=1800` 상수, `fetchAskStatus`/`showTimeoutRecoveryDialog`(3 버튼 모달: 요청 취소/즉시 답변/계속 기다리기, Escape 로 dismiss) / `attachAndWaitForResult` (long-poll 루프, run_id 고정, terminal 시 `refreshWorkspace`) 를 추가했고, `sendPrompt()` 의 `apiFetch("/api/ask",...)` 를 try/catch 로 감싸 실패 + `is_processing=true` 이면 다이얼로그 → 사용자 선택에 따라 `/api/cancel`/`/api/finalize`/attach 로 분기한다. `initializeWorkspace()` 끝에 boot-time auto-attach: 페이지 로드 시 현재 대화가 서버에서 처리 중이면 자동으로 busy 상태 + progress polling + attach 를 재개한다. `tests/task0034_runner.py` 에 `ATTACH_TIMEOUT_SEC=960.0` / `ATTACH_POLL_WAIT_SEC=45` 상수, `_steps_from_attach(meta)` 헬퍼, `_attach_run(client, cid, msg, t0)` 함수(ask_status → ask_result long-poll 반복)를 추가했고, 기존 `httpx.ReadTimeout` 분기가 `{"error": "client-read-timeout"}` 을 반환하는 대신 `_attach_run` 으로 이어받아 `attached_after_timeout=True, attach_verdict="succeeded-via-attach"|"attach-status-<status>"` 메타와 함께 turn 기록을 정상 작성한다. 검증: (a) `python3 -m py_compile` 3 파일 통과, (b) `node --check static/app.js` JS 문법 OK, (c) `make web` 재빌드/재기동 → 새 sha256 이미지 반영 + `/api/ask_status` / `/api/ask_result` 401 응답으로 라우팅 확인, (d) terminal 상태 대화에 대한 `/api/ask_status` + `/api/ask_result` 가 38ms 이내 snapshot/assistant 반환 확인, (e) `python3 tests/task0034_runner.py --target api --only Q4,Q5` 재수행. 보안: `/api/ask_status`/`/api/ask_result` 는 read-only 이며 기존 `conversation.read.own/any` 권한 모델 재사용 — 새로운 공격 표면 추가 없음. 범위: 서버 1 파일 약 190 줄, 프론트 1 파일 약 230 줄, 테스트 1 파일 약 95 줄.

## CHG-20260422-0013
- Date: 2026-04-22
- Summary: SQL schema whitelist 정규식을 context-aware 2 단계 스캐너로 재작성 — `alias.column` 오탐으로 합법 SQL 이 차단되던 TASK-0036 회귀 제거 (TASK-0040)
- Files: ../feature-0002-agent-core/src/modules/tools.py, docs/TASK.md, docs/MODIFY.md, docs/REPORT.md, docs/REVIEW.md, ../../docs/LEARNINGS.md
- Notes: 기존 `_SCHEMA_TABLE_REF_RE = r"\`?([A-Za-z_]\w*)\`?\s*\.\s*\`?([A-Za-z_]\w*)\`?"` 는 SQL 문맥 구분 없이 모든 `x.y` 패턴을 `schema.table` 로 간주했다. `SELECT bb.BattleType, be.Star FROM dblog.t bb JOIN dblog.u be ON be.a = bb.a` 같은 alias.column 토큰이 전부 schema 후보로 수집되어 `_whitelist_violation` 이 Product whitelist=`{dbauth,dbgame,dblog}` 에서 `be`/`bb` 불허로 판정 → TASK-0034 Q4 재수행의 모든 턴이 `BLOCKED_SCHEMAS=bb,be` 로 실패했다. 수정: `_SCHEMA_TABLE_REF_RE` 를 제거하고 `_TABLE_LIST_RE`(`FROM`/`JOIN` 키워드 뒤 ~ 다음 절 키워드 `ON|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|UNION|JOIN|FROM|;|)|$` 전까지 lookahead) + `_INNER_REF_RE`(그 구간 내부에서 `schema.table` 만 추출) 2 단계 스캐너로 재작성. SELECT 절/WHERE 절/ON 절의 alias.column 은 FROM/JOIN 슬라이스 바깥이어서 더 이상 매칭되지 않는다. 검증: in-process 15 테스트 케이스 (단일 FROM / FROM+WHERE alias / FROM+JOIN+alias.col ON / 혼합 스키마 / 백틱 / subquery / 비허용 schema 차단 / SELECT 절 alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / 중복 refs dedup) 전부 expected refs 일치, `_whitelist_violation` 이 Q4-like SQL 에서 `{dblog}` 만 검출하고 `dbstat.foo` 는 여전히 차단. 범위: `modules/tools.py` 약 25 줄 (`_SCHEMA_TABLE_REF_RE` 제거 + 2 단계 스캐너 추가). TASK-0034 Q4/Q5 재수행을 가능하게 하는 선행 블로커 해제.

## CHG-20260422-0012
- Date: 2026-04-22
- Summary: 메타데이터 4 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 를 Product whitelist 와 무관하게 항상 agent tool 에서 접근 가능하도록 bypass 정책 확장 (REV-20260421-0005 일부 완화)
- Files: ../feature-0002-agent-core/src/modules/tools.py, docs/TASK.md, docs/MODIFY.md, docs/REVIEW.md, docs/FUNCTION.md, docs/REPORT.md
- Notes: 사용자 지시(2026-04-22, "assistant 가 스키마 구조를 찾지 못하는 이슈를 방지") 에 따라 Product 단위 DB whitelist 의 bypass 집합을 확장. `tools.py` 의 `_SYSTEM_SCHEMAS` 단일 frozenset 을 `_METADATA_SCHEMAS`(information_schema/sys/mysql/performance_schema, whitelist bypass) + `_INTERNAL_SCHEMAS`(agent_memory, whitelist 차단 유지) 두 frozenset 으로 분리했고, `_SYSTEM_SCHEMAS` 는 이들의 union 으로 남겨 기존 `_is_user_schema` / `search_tables` UX 필터 동작을 보존했다. `_whitelist_violation` 의 `allowed` 집합을 `{information_schema}` 에서 `_METADATA_SCHEMAS` 전체로 교체. 차단 시 에러 메시지 끝에 "메타데이터 스키마(information_schema/sys/mysql/performance_schema) 는 항상 접근 가능" 한 줄을 덧붙여 LLM 이 잘못 참조한 user schema 를 information_schema 경로로 리디렉션할 수 있도록 힌트를 남긴다. `agent_memory` 는 계속 차단(타 계정 대화/세션/권한 override 보호). 검증: (a) `python3 -m py_compile modules/tools.py` 통과, (b) `docker compose up -d --build web` + `--force-recreate` 후 컨테이너 in-process 호출 8 케이스(whitelist=None/메타데이터 4종 bypass/허용 user schema/혼합 통과/agent_memory 차단/비허용 user schema 차단/`_is_user_schema` UX 필터 보존) 모두 통과, (c) `execute_tool` 경로로 `execute_sql("SELECT ... FROM information_schema.TABLES")` / `describe_schema("sys")` / `execute_sql("... performance_schema.tables")` 정상 응답, `execute_sql("... mysql.user")` 는 tool-level whitelist 통과 후 DB 에서 실제 행 반환(MySQL GRANT 가 열려있음 — REV-20260422-0006 에 2 차 방어 필요성 기록), `execute_sql("... agent_memory.AgentMemoryMessages")` 와 임의 비허용 `dbstat.*` 은 여전히 차단. 범위: 코드 변경 `tools.py` 1 파일 약 14 줄. `list_schemas` 결과에 메타데이터를 노출할지는 UX 결정 영역으로 현 상태(숨김) 유지.

## CHG-20260423-0015
- Date: 2026-04-23
- Summary: Approach A wedge (사업팀 자가서비스) pilot infra — sales role seed + role-scope system prompt seed + 복제 DB 접속 envelope + pilot onboarding runbook (TASK-0044)
- Files: src/app.py, ../feature-0002-agent-core/src/modules/config.py, ../feature-0002-agent-core/src/modules/db.py, ../../.env.example, docs/TASK.md, docs/MODIFY.md, docs/FUNCTION.md, ../../docs/STATUS.md
- Notes: office-hours 2026-04-23 세션에서 승인된 Approach A (사업팀 통계/단순 데이터 자가서비스 wedge) 의 infra 구현. (1) `SEED_ROLE_DEFINITIONS` 에 RoleKey=`sales` / Name=`사업팀` entry 를 추가 — operator 권한에서 `conversation.delete.own` 만 제거한 9 개 권한(conversation.create/ask/suggestions.read/list.own/read.own/file.read.own/rename.own/cancel.own/finalize.own) 으로 사업팀 pilot 이 자기 대화 흐름은 조작하되 과거 요청 기록 삭제는 막는 subset. (2) 신규 `SEED_ROLE_SYSTEM_PROMPTS` + `_ensure_seed_role_system_prompts(conn)` 부트스트랩 단계 — `_load_system_prompt` 로 존재 여부 먼저 확인해 idempotent(관리 콘솔 수정 존중), 없을 때만 `_upsert_system_prompt(scope='role', role_id=<sales>, product_id=None)` 로 4 지침(단순 조회 → 문장 / 집계 → 결과셋 표 / ad-hoc 분석 → DBA 팀 이관 안내 후 종료 / DB 쓰기 쿼리 거부) prompt 를 insert. `_ensure_seed_products` 바로 뒤에 호출해 sales role + WebSystemPrompts 스키마 준비 모두 보장된 상태에서 실행. `agent_core.compose_system_prompt` 가 기존 로직(TASK-0036) 그대로 `## ROLE GUIDANCE (sales)` 블록으로 주입한다. (3) `modules/config.py` 에 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` env 4 개 + 파생 `REPLICA_DB_ENABLED=bool(REPLICA_DB_HOST)` 추가, `__all__` 에 5 개 export. `modules/db.py::connect()` 에 라우팅 로직 — `REPLICA_DB_ENABLED` 가 True 이고 요청된 `database` 가 `MEMORY_DB`(=agent_memory) 가 아니면 복제 인스턴스(host/port/user/password) 로 접속, 그 외(미설정/메모리 연결/database=None) 는 기존 primary 파라미터. memory DB 는 항상 primary 이므로 대화·세션·권한 정본이 보존된다. (4) `.env.example` 에 `REPLICA_DB_HOST=` / `REPLICA_DB_PORT=` / `REPLICA_DB_USER=` / `REPLICA_DB_PASSWORD=` 4 placeholder + 사업팀 pilot 이름 치환용 `WEB_PILOT_SALES_USERNAMES=` 주석 추가. 실제 접속 정보/계정 이름은 `.env` 또는 docker-compose secret 으로만 주입(commit 금지). (5) pilot 계정 자동 생성은 하지 않음 — admin 이 관리 콘솔에서 수동 발급하도록 docs/TASK.md §TASK-0044 pilot onboarding runbook 에 3 단계 절차(계정 발급 / Product whitelist 2 가지 옵션 / 복제 DB 접속 등록) 기록. (6) Product 단위 접근 DB 화이트리스트 조정은 런타임 코드 변경 없이 runbook 으로 해결 — 옵션 A(KR Product 에서 dbauth 제거) 또는 옵션 B(KR-Sales Product 신규 생성) 중 조직 정책에 맞게 선택. 현재 seed 는 호환성을 위해 변경하지 않음. 검증: (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py unit/feature-0002-agent-core/src/modules/config.py unit/feature-0002-agent-core/src/modules/db.py` 통과, (b) `docker compose up -d --build web` 후 `/api/session` HTTP 200 OK + bootstrap_admin 로그인 성공, (c) MySQL 에 `SELECT r.RoleKey,r.Name,COUNT(rp.PermissionId) FROM WebRoles r LEFT JOIN WebRolePermissions rp ON r.Id=rp.RoleId WHERE r.RoleKey='sales' GROUP BY r.Id` 결과 1 row `sales / 사업팀 / 9`, (d) `SELECT LEFT(Content,60) FROM WebSystemPrompts WHERE Scope='role' AND RoleId=(SELECT Id FROM WebRoles WHERE RoleKey='sales') AND ProductId IS NULL` 1 row 에 "당신은 게임 사업팀을 지원하는 DBA 어시스턴트다" 로 시작. 범위: 코드 3 파일 약 70 줄(app.py +54, config.py +12, db.py +11), `.env.example` +6 줄, 문서 4 파일. 사업팀 pilot 의 단순/집계/ad-hoc 실제 응답 acceptance 3 개는 pilot 계정 발급 이후 admin 이 수동 확인(TASK.md AC 체크리스트의 미체크 3 항목) 하도록 남겨둔다 — 현재 환경에 사업팀 pilot 계정 발급이 선행되지 않아 코드 단독으로는 검증 불가.


## CHG-20260424-0016
- Date: 2026-04-24
- Related Requirement: TASK-0045 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — Web UI feature가 "UI + 서버 측 로직 전체" 범위임을 명시, System Prompt 3계층 조립의 Web feature 귀속 근거, layering 위반 방지, whitelist 관리 onboarding 시나리오.
- Files: unit/feature-0003-agent-web-ui/docs/ANCHOR.md, unit/feature-0003-agent-web-ui/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. System Prompt 조립을 core로 옮기려는 향후 요청은 §1 / §2 Alt-A와 충돌 감지 (Conflict Protocol 발화). whitelist 정책 변경 시 §3 시나리오가 onboarding 진입점 역할.
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.

## CHG-20260425-0017
- Date: 2026-04-25
- Related Requirement: TASK-0046, REQ-20260425-0001
- Summary: 프로필 드로어의 API Vault 탭을 Linear Wizard 3-step 구조로 재설계 + 단일 진입점 destructive 정책. 사용자 raw feedback "프로필쪽 키 입력하는곳 왜이래? 알아먹기 힘드네" 대응.
- Files: unit/feature-0003-agent-web-ui/src/static/index.html, unit/feature-0003-agent-web-ui/src/static/styles.css, unit/feature-0003-agent-web-ui/src/static/app.js, unit/feature-0003-agent-web-ui/docs/TASK.md, unit/feature-0003-agent-web-ui/docs/MODIFY.md, unit/feature-0003-agent-web-ui/docs/REPORT.md, docs/REQUEST.md, docs/REQUEST_ARCHIVE.md
- Notes: 4 단계 반복(initial Linear Wizard → fix1 saved card 분리 → fix2 replacingVault flag → final 단일 진입점) 으로 사용자 검증을 거쳐 완성. 핵심 변경 (1) `index.html` L246-L334 의 vault 패널 markup 을 `vault-banner` (readiness tri-state) + `ol.vault-stepper > li.vault-step × 3` (Step 1 사용할 API 키 / Step 2 passphrase / Step 3 암호화 후 저장) + `vault-saved` (information only — 저장 시 노출, 버튼 0 개) + `vault-danger-zone` (저장된 키 삭제 1 개) + `details.vault-advanced` (cipher 직접 붙여넣기, 기본 접힘) 로 재구성. (2) `styles.css` L1420-L1582 에 `.vault-banner` / `.vault-banner-dot[data-state]` / `.vault-stepper` / `.vault-step[data-state="active|done|disabled"]` / `.vault-step-num` / `.vault-step-head/title/body/hint` / `.vault-saved` / `.vault-danger-zone` / `.btn-danger-link` / `.vault-advanced[-body]` 신규(약 170 줄). (3) `app.js` 의 vault state helper 군 재작성 — `updateVaultStatus` → `updateVaultReadiness` rename + `computeVaultReadiness` 의 진실 출처를 input value 에서 storage(localStorage cipher + sessionStorage|input passphrase) 로 통일, `syncVaultSteps` 가 `cipherSaved` 만으로 saved-default ↔ wizard 입력 모드 전환, `renderVaultSavedCard` 가 saved card + danger zone 동시 hidden 토글, `encryptPlainApiKey` + `writeVaultState` 를 단일 saveVault 흐름으로 합쳐 "암호화 후 저장" 한 버튼이 평문→cipher 변환→영속 모두 처리, `clearVaultBtn` 핸들러 앞에 `confirm("저장된 암호화 키를 삭제할까요? ...")` 가드 추가, 신규 `vaultImportCipherBtn` 핸들러로 `v1:` prefix 검증 후 ciphertext 직접 import. 키 갈아끼움 진입점은 "저장된 키 삭제" → confirm → wizard 재진입 → 새 평문 입력 → 저장 1 경로로 단일화 — `vaultReplaceBtn` / `replacingVault` flag / `enterReplaceMode` / `cancelReplaceMode` 모두 제거. cache-bust `v=20260425-vault-final`. (4) 검증: `repo/.gstack/qa-reports/qa-vault.cjs` (Playwright Node script, browse 데몬 우회) 28/28 PASS, healthScore 100, console.error 0 건. AUTH/SESSION/BUST/DRAWER/TAB/UI(10)/FLOW(3)/REG(8)/CONSOLE 전 카테고리 통과. 사용자 직접 브라우저 검증 4 시나리오(저장 완료 / 새로고침 / 삭제 후 새 키 입력 / confirm 취소) 모두 만족. (5) 사용자 raw feedback ("프로필쪽 키 입력하는곳 왜이래? 알아먹기 힘드네") 의 구조적 원인(시작점이 `<details>` 에 숨음 / 라벨 한 글자 차이 / 종속관계 표현 실패 / "저장" 동사 모호성 / 결과 동일 진입점 중복) 모두 해소됨.
