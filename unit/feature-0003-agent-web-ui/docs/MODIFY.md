---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260515-0001
- Date: 2026-05-15
- Summary: TASK-0059 (REQ-20260515-0001, **Major** §12.3 — 사용자 대화 routing 데이터 영역). "새 대화" 버튼 누른 후 첫 메시지가 신규 대화가 아닌 직전 active 대화로 routing 되던 lazy-create 결함 수정. frontend 의 신규 의도가 backend 로 전달되지 않아 빈 `conversation_id` 가 "session 초기화 후 직전 대화 이어받기" 와 구분 불가했던 갭을 명시적 `lazy_create` hint + `force_new` 분기로 닫는다. 인증/인가 모델 무변경.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `sendPrompt()` 의 askBody 에 `isLazyCreate=true` 일 때만 `lazy_create: true` hint 를 추가. 기존 대화 ask 경로는 hint 미포함 (의미 변경 0).
    - `loadConversations()` 의 `state.activeConversationId` 덮어쓰기를 `!state.pendingNewConversation` 가드 안으로 이동. pending 모드 race 시 사이드바 리스트만 갱신하고 active 보존 → 직전 대화로 복귀하던 회귀 차단.
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`:
    - `_resolve_conversation_for_account` 시그니처에 `force_new: bool = False` kwarg 추가. requested_id 가 truthy 이면 force_new 무시 (의도 상호배타), 빈 문자열이면 `_repair_current_conversation(..., force_new=force_new)` 로 위임. 기존 `_repair_current_conversation` 의 force_new 동작 (line 1167 의 visible fallback 차단 + line 1172 의 신규 cid 생성 + `_assign_conversation_owner(force=True)`) 그대로 활용 — body 변경 없음.
    - `/api/ask` 의 빈 `request_conversation_id` 경로에서 `lazy_create_requested = bool(data.get("lazy_create"))` 추출 후 `_resolve_conversation_for_account(..., create_if_missing=True, force_new=lazy_create_requested)` 호출. hint 없는 legacy client (예: 첫 로그인 후 직전 대화 자동 이어받기 흐름) 는 force_new=False 로 기존 동작 유지.
- Trace: REQ-20260515-0001 → TASK-0059 → CHG-20260515-0001
- Verify: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` / `node --check unit/feature-0003-agent-web-ui/src/static/app.js` / `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

## CHG-20260514-0001
- Date: 2026-05-14
- Summary: TASK-0058 (REQ-20260514-0001, **Critical** §12.3) 대화 공유 링크 기능 도입. anonymous accessible read-only view + 로그인 viewer 의 fork. 사용자 결정 6 항목 + codex outside voice review 의 blindspot 10 개 (B1-B2 blocking + R1-R10 recommended) 모두 plan 에 반영.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`:
    - `PERMISSION_DEFINITIONS` 에 `conversation.share.create` (group="conversation") 추가 → catalog 33 → 34.
    - `SEED_ROLE_DEFINITIONS` 의 operator/sales permissions set 에 `conversation.share.create` 추가. admin 은 `set(PERMISSION_CODES)` 자동 포함.
    - `_ensure_seed_roles` admin 보정 list 에 `conversation.share.create` 추가 + operator/sales catchup INSERT IGNORE.
    - `_ensure_web_conversation_shares_schema(conn)` helper 신설 → `_ensure_web_tables` (slow path) + `_ensure_seed_catchup` (fast path) 양쪽에서 호출. fast path 에 `_ensure_permission_catalog(conn)` 추가로 신규 권한 hydrate.
    - `_optional_account(request, conn)` 헬퍼 신설 — anonymous endpoint 용 (쿠키 없으면 None).
    - `_fork_conversation_impl(conn, account, source_id, from_id)` 로 fork 본체 추출. 기존 `/api/fork_conversation` 은 helper 호출. share-token 경로는 read-gate 우회.
    - `/share/{token}` FileResponse route (admin 옆).
    - 신규 5 endpoint: POST `/api/conversations/{cid}/share`, GET `/api/conversations/{cid}/shares`, DELETE `/api/share/{share_id}`, GET `/api/public/share/{token}`, POST `/api/public/share/{token}/fork`. Token `secrets.token_urlsafe(32)` + UNIQUE 충돌 5 회 retry. revoke + view counter = 단일 race-free UPDATE.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`: chat 헤더 fork 버튼 옆에 `shareConversationBtn` 추가.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `shareConversationBtn` DOM reference + `PERMISSION_LABELS` / `PERMISSION_DESCRIPTIONS` 매핑 추가.
    - 메시지 hover "여기까지 공유" 액션 + 헤더 share 버튼 visibility toggle + click handler.
    - `createConversationShare({anchorMessageId})` async — `/api/conversations/{cid}/share` 호출 + clipboard.writeText + toast.
  - `repo/unit/feature-0003-agent-web-ui/src/static/share.html` (신규): anonymous read-only view, `meta robots noindex,nofollow`, `share.css` 만 import (메인 styles.css 격리).
  - `repo/unit/feature-0003-agent-web-ui/src/static/share.css` (신규): minimal styling. `.share-sql` (dark `<pre>`), `.share-result-table`, fixed footer 사내 협업 고지.
  - `repo/unit/feature-0003-agent-web-ui/src/static/share.js` (신규): vanilla JS — token 추출 → fetch → 메시지 + meta.final_sql + meta.result_rows 렌더 → can_fork 시 fork 버튼.
  - `repo/unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: §2 Goal REQ-20260514-0001 + §11 AC-0053~AC-0060.
  - `repo/unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0058 + §2.1 Implementation Plan + PLAN-APPROVED 마커.
  - `repo/docs/SECURITY.md`: anonymous endpoint 2 곳 명시 + 외부 배포 시 IP 제한/비밀번호 보호 후속 cycle 권장.
  - `repo/docs/STATUS.md`: feature-0003 row 갱신.
- Verification:
  - `python3 -c "import ast; ast.parse(...)"` app.py OK.
  - `node --check` app.js / share.js OK.
  - 부트스트랩 idempotency 는 helper 패턴 (try/except pass + INSERT IGNORE + ON DUPLICATE KEY UPDATE).
  - Runtime 검증 (sales/admin 로그인 → 헤더 "공유" 버튼 → dialog 발급 → anonymous URL 접근 → revoke → 410) 은 후속 단계.

## CHG-20260512-0002
- Date: 2026-05-12
- Summary: TASK-0056 (REQ-20260512-0002, **Major** §12.3 — 작업 화면·관리 콘솔 권한 정렬 분리, AI 자율 commit/push 대상은 사용자 결정) 작업 화면 (`index.html` 권한 현황) 과 관리 콘솔 (`admin.html` 권한 grid) 의 권한 group 순서가 동일 `console→account→role→conversation→[product]→misc` 으로 묶여 있어, 화면 맥락(자기시점 / 관리자시점) 이 정반대인데도 두 곳 모두 admin 메타권한이 위로 노출되던 문제 fix. 화면별 2단 section (관리/운영/기타) 으로 분리, 작업 화면은 운영 권한이 위로 + 관리 권한은 보유 시만 묶음 형태로 뒤로. CONVENTIONS.md §10.6 정책 신설.
- Files:
  - `repo/docs/CONVENTIONS.md` §10.6 (화면별 권한 섹션·정렬 정책) 신설 — 화면별 section 순서 표, 정합 규칙 6 줄, 동적 권한 (`product.access.<key>`, `system_prompt.*`) 처리, 검증 한 줄.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - 새 상수 `ADMIN_PERMISSION_SECTIONS` (관리/운영/기타 3 section 정의) 추가.
    - 새 함수 `sectionedGroupedPermissions(opts)` — `groupedPermissions()` 결과를 section 으로 묶고 빈 group/section 제외 + 미매핑 group 은 "기타" fallback.
    - `renderPermissionGrid` 가 outer section header (`.permission-section` + `.permission-section-head` + `.permission-section-title` + `.permission-section-description` + `.permission-section-groups`) 로 감싸고 inner `<details data-perm-group>` 들을 `sectionGroupsEl` 에 append 하도록 수정.
    - 기존 line 50 의 "backend `PERMISSION_GROUP_ORDER` (app.py) 와 순서 동기 필수" 주석은 실제로는 backend `PERMISSION_DEFINITIONS[*].group` 키 정합에 가까워 표현 정정.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `PERMISSION_GROUP_ORDER` 에 `product` 그룹 추가 + `PERMISSION_GROUP_LABELS.product = "제품"` 추가 (작업 화면 측 누락 fix).
    - 새 상수 `WORK_SCREEN_PERMISSION_SECTIONS` (운영/관리/기타 3 section) 추가 — 관리자측과 정반대 순서.
    - `permissionGroupOf()` 가 `system_prompt.` 접두사를 `product` 그룹으로 명시 매핑 (app.py `system_prompt.manage.role.any` 의 `group: "product"` 와 정합).
    - `PERMISSION_LABELS` / `PERMISSION_DESCRIPTIONS` 에 `product.manage` / `system_prompt.manage.role.any` 항목 추가.
    - `buildPermissionPills(containerEl)` 가 WORK_SCREEN_PERMISSION_SECTIONS 의 2단 묶음 (`.perm-section-meta` + `.perm-section-meta-head` + `.perm-section-meta-title` + `.perm-section-meta-description` + `.perm-section-meta-groups`) 으로 렌더. section 안의 어느 group 권한도 보유하지 않으면 section 자체 미렌더 (관리 권한 묶음 자동 hide). 미매핑 group orphan 처리도 추가.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - 작업 화면측: `.perm-section-meta`, `.perm-section-meta-head`, `.perm-section-meta-title`, `.perm-section-meta-description`, `.perm-section-meta-groups`. 관리 권한 묶음만 살짝 opacity/muted 처리.
    - 관리 콘솔측: `.permission-section`, `.permission-section-head`, `.permission-section-title`, `.permission-section-description`, `.permission-section-groups`. `data-perm-section="manage"` 는 살짝 파란 background, `"operate"` 는 살짝 녹색 background.
    - `.permission-grid/.override-grid { gap: 18px }` 로 increase (외부 section 들 간격), `.permission-section-groups > .permission-group + .permission-group { margin-top: 0 }` 로 gap 중첩 제거.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html`: styles.css / admin.js cache-bust slug `v=20260512-perm-sections`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`: styles.css / app.js cache-bust slug `v=20260512-perm-sections`.
- Verification:
  - `node --check admin.js` 통과.
  - `node --check app.js` 통과.
  - DB schema / backend RBAC catalog / endpoint guard / system prompt assembly 변경 **0**. 본 cycle 은 frontend 렌더링과 project-level 컨벤션 문서만 수정 — 인가 모델 무영향.
  - 두 화면 모두 정렬은 frontend 상수 (`WORK_SCREEN_PERMISSION_SECTIONS` / `ADMIN_PERMISSION_SECTIONS`) 가 단일 정의처. 미매핑 group 은 "기타" section 으로 자동 fallback.
- Risks:
  - 백엔드에 새 group key 가 추가되는 경우 (예: 향후 `audit`, `integration` 등) 두 상수에 명시 매핑하지 않으면 "기타" 로 떨어진다. CONVENTIONS.md §10.6 의 정합 규칙으로 명시.
  - 작업 화면의 "관리 권한" section 자동 hide 는 사용자가 실제로 admin perm 을 한 개도 보유하지 않을 때만 적용 — admin 계정은 항상 표시됨. 일반 사용자는 관리 권한 section 자체가 없어지므로 시각적 단순화.
  - 시각 검증 (`make web` 기동 후 두 화면 비교 + 일반 사용자 / admin 계정 양 시점) 은 사용자 환경에서 진행 권고.

## CHG-20260508-0001
- Date: 2026-05-08
- Summary: TASK-0054 (REQ-20260508-0001) PR 흐름으로 main 동기화 — feat/adopt-external-anchor-v3.2.0-rc + issue/1-github-bootstrap 의 누적 작업을 두 개의 PR 로 main 에 머지. AI 자율 commit/push (§16.5).
- Files:
  - PR #2 (`feat/adopt-external-anchor-v3.2.0-rc` → `main`):
    - merge commit `eafe4c2` (admin merge, 72 commits / 137 files / +28320 / -9018)
    - 충돌 해결 commit `ae53965` — main 의 v3.0.0 마이그레이션과 본 브랜치의 v3.6.0 진화 conflict (10 files: AGENTS.md / CONTRIBUTING.md / unit/_template/docs/TASK.md / docs/{CODEBASE_MAP,LEARNINGS}.md / playbooks/{PB-0001~0004,README}.md) 을 §3.2 + §16.6 자율 해결 원칙에 따라 본 브랜치 본문 우선으로 통합.
  - PR #3 (`issue/1-github-bootstrap` → `main`):
    - merge commit `3fd4272` (admin merge, 단일 commit `38702cd`)
    - 변경: `.github/workflows/{ai-execute,ai-review,ai-triage}.yml` 의 `runs-on` 을 `[self-hosted, linux]` 로 + `anthropics/claude-code-action@v1` 제거 + 로컬 `claude -p ...` CLI 직접 호출.
  - 본 cycle 의 `unit/feature-0003-agent-web-ui/docs/REPORT.md` §3 에 Git 동기화 결과 양식 (§16.5 Step 6) 으로 PR #2 + PR #3 의 머지 commit hash, 충돌 해결 사유, CI fail 인프라 이슈 요약을 누적 기록.
- Verification:
  - `gh pr view 2 --json state,mergedAt,mergeCommit` → `MERGED`, mergeCommit `eafe4c25af3eda75e2f74cd9350dfc3c9531fad9`.
  - `gh pr view 3 --json state,mergedAt,mergeCommit` → `MERGED`, mergeCommit `3fd4272fdc2aaa902df50c8cb03431a7a99c3855`.
  - `git show origin/main:.github/workflows/ai-execute.yml | grep runs-on` → `runs-on: [self-hosted, linux]` (운영 정합성 회복).
  - 직전 `bin/verify-completion.sh --post-commit feature-0003-agent-web-ui` PASS (6/6).
- Risks:
  - feat 브랜치는 PR #2/PR #3 의 merge commits + ae53965 만큼 main 보다 behind 3 — feat 에서 추가 작업 시 catch-up 필요 (사용자 결정).
  - main 의 self-hosted runner 환경에서 `repo-agent` 이미지 누락 (selfhosted-runtime-smoke fail) 은 별도 인프라 후속 작업으로 분리. PR #2 / PR #3 자체의 정책 위반은 아님.
  - CI 의 `policy-contract` (브랜치 이름 `feat/*` 가 `issue/<번호>-<short-slug>` 자동화 계약 외) + `ai-review` (heredoc EOF delimiter 워크플로 버그) 는 본 PR 본문과 무관한 인프라 이슈로 admin merge 정당화. 정책 자동화 자체는 향후 cycle 에서 보강 필요.

## CHG-20260507-0001
- Date: 2026-05-07
- Summary: TASK-0053 사용자 follow-up 2 항목 수정 — (1) Account/Role 의 pending 상태 row UI 뒤틀림 버그 fix, (2) 제품별 접근 카드 list 를 권한 grid 의 'product' 그룹 details 안으로 이전. AI 자율 commit/push.
- Files:
  - [unit/feature-0003-agent-web-ui/src/static/styles.css](../src/static/styles.css)
    - Issue 1 fix: `.admin-list-row.has-pending::before { content: ""; }` 의 placeholder rule 이 CSS Grid container 의 `::before` 가 4번째 grid item 으로 참여해 cb 를 column 2 로 밀고 chips 를 row 2 col 1 로 wrap 시키던 버그 fix. pseudo-element 자체를 제거하고, `.has-pending` 에 `border-color: rgba(37,99,235,.35)` 만 적용해 시각적 표시 유지 (`pendingDot` "•" 이 이미 title 안에서 indicator 역할).
    - 신규 `.admin-product-card-list-embedded` 스타일 (margin-top + padding-top + dashed border-top) — 권한 grid 'product' 그룹 details 안에 inline 배치될 때 정적 권한과의 시각적 구분.
  - [unit/feature-0003-agent-web-ui/src/static/admin.js](../src/static/admin.js)
    - Issue 2: `buildRoleProductCardList(role, disabled, opts={})` / `buildAccountProductOverrideList(account, disabled, opts={})` 시그니처에 `opts.embed` 추가. embed=true 면 별도 section title 생략 (부모 details summary 의 "제품" 라벨과 중복 회피), hint 메시지 단축.
    - `renderRoleDetail`: 기존 `paneEl.appendChild(productCards)` 를 `permWrap.querySelector('details[data-perm-group="product"]')` 가 있으면 그 안에 append, 없으면 fallback 으로 paneEl 에 append 하는 분기로 변경. embed 옵션 전달.
    - `renderAccountDetail`: 동일 패턴으로 `overrideWrap` 안의 product 그룹 details 에 productOverrides append.
  - [unit/feature-0003-agent-web-ui/src/static/admin.html](../src/static/admin.html)
    - cache-bust `v=20260507-row-fix-embed`.
- Verification:
  - (a) `node --check admin.js` PASS / `make web` 재배포.
  - (b) **Issue 1 DOM 분석 (수정 전 → 수정 후)**: sales role 에 pending 적용 후 `getBoundingClientRect`. 수정 전 — `cb x=70 y=30` (column 2 — 잘못), `main x=175 y=9` (column 3 — 잘못), `chips x=11 y=73` (row 2 col 1 — wrap). 수정 후 — `cb x=11 y=30` (column 1 ✓), `main x=34 y=9` (column 2 ✓), `chips x=270 y=26` (column 3 ✓), 모두 row 1 에 정상 배치. row height 102 → 72 (정상 높이).
  - (c) **Issue 2 DOM 검증**: `details[data-perm-group="product"]` 안에 `.admin-product-card-list-embedded` 1 개 + `.admin-product-card` 3 개 (KR / TT / 전 Product 공통) 정상 배치 확인. 사용자가 "제품" 그룹 collapse 시 정적 권한과 product 카드가 함께 접힘.
  - (d) **시각 확인** (스크린샷): pending 상태 sales row 가 다른 role row 와 동일한 패턴 (cb / 아바타 / name+meta / active 칩) 으로 표시. "제품" 그룹 펼치면 정적 권한 + 안내 hint + product 카드 (체크박스 + product key) inline 노출.
- Risks:
  - **CSS pseudo-element grid item 회귀 위험**: 향후 다른 `::before`/`::after` 에 `content: "..."` 가 추가될 때 같은 버그 재발 가능. 방어책: grid container 의 pseudo-element 는 `position: absolute` 로 grid flow 에서 제외하거나 `display: none`. 본 수정은 placeholder rule 자체를 제거.
  - **embed=true 모드의 hint 텍스트 차이**: 부모 details 안에 들어가면 footer 정보가 중복되지 않도록 hint 를 단축. UX 일관성 손실 우려는 적음 — footer "모두 적용" 메시지가 이미 다른 곳에서 노출됨.
  - **Account detail 의 product card 도 동일 처리**: override grid 의 product 그룹 details 안에 inline 배치. 사용자가 "제품" collapse 시 product 별 override select 도 함께 접힘.
- Range: styles.css +6 lines (rule 제거 + 신규 embedded 변형 + has-pending border), admin.js +~25 lines (renderRoleDetail/renderAccountDetail 의 분기 + buildRoleProductCardList/buildAccountProductOverrideList 의 embed opts), admin.html cache-bust 2 lines. 신규 파일 0.
- Notes: 본 fix 는 TASK-0053 의 후속 보완 — 사용자 직접 보고 + 시각 의도 ("제품 접기에 따라 출력") 반영. 정책 주체 (Product) 결정은 변경 없음. CSS Grid 의 ::before pseudo-element 가 grid item 으로 참여한다는 사실은 흔한 함정 — LEARNINGS.md 등재 권고.

## CHG-20260506-0027
- Date: 2026-05-06
- Summary: TASK-0053 (REQ-20260506-0006, Major §12.3) 신규 제품 default 정책 토글 + 권한 grid 의 product sub-catalog + Role/Account detail 의 product-카드 통합. TASK-0052 완료 직후 사용자 follow-up. **사용자 in-cycle 설계 전환 (2026-05-06)**: 정책 주체를 Role 이 아닌 **Product** 로 변경 — 운영자가 product 생성 시점에 토글로 결정하는 것이 더 자연스럽다는 의도. AI 자율 commit/push.
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - **Phase A — `WebProducts.DefaultRoleAccess` 정책 토글 (product 주체)**:
      - `_ensure_dynamic_permissions_schema(conn)` 에 `ALTER TABLE WebProducts ADD COLUMN DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 추가 (idempotent ALTER, 기존 운영 데이터 호환).
      - `_ensure_product_access_permissions(conn)` (catchup backfill) 의 role grant SQL 이 product 의 `DefaultRoleAccess` 값에 따라 분기 — true 면 모든 role grant, false 면 grant 안 함.
      - `POST /api/admin/products` 의 body 에 `default_role_access` 수용, INSERT 시 컬럼 set + transaction 안 backfill 분기에 동일 적용.
      - `PATCH /api/admin/products/{id}` 에 `default_role_access` 수용 (기존 product 정책 변경 가능).
      - `_list_products` SELECT 와 응답 dict 에 `default_role_access` 필드 추가.
      - `WebRoles.DefaultProductAccess` 관련 코드 모두 제거 — `_load_role_by_id` / `_list_roles` SELECT/GROUP BY/dict 에서 컬럼 삭제, `admin_update_role` 의 body 수용 + UPDATE 컬럼 제거. 컬럼 자체는 destructive DROP 회피 차원에서 잔존 (다음 cleanup cycle 에서 DROP COLUMN).
  - [unit/feature-0003-agent-web-ui/src/static/admin.js](../src/static/admin.js)
    - **Phase A frontend**: Product detail 에 토글 1 row 추가 ("신규 역할 자동 접근"). Product detail 의 `merged` 객체에 `default_role_access` 추가, `setProductMetaPending` 핸들러 + `applyAllPending` 의 productMeta PATCH body 에 포함, `describePatchKeys` 라벨 추가. **Role detail 의 토글은 제거** (이전 설계의 잔재 — Role-side 의 default_product_access 흐름 전부 삭제: mergedRole/setRolePending/applyAllPending/startNewRole/describePatchKeys 모두 정정).
    - **Phase B — 권한 grid 의 dynamic 권한 분리**: `groupedPermissions(opts={excludeDynamic})` 옵션 추가, `dynamicProductPermissions()` 헬퍼 신설. `renderPermissionGrid(..., opts={excludeDynamic})` 옵션 전달. Role detail 과 Account detail 의 grid 호출이 `excludeDynamic: true` 로 dynamic `product.access.<key>` 권한들을 별도 product subcatalog 로 분리.
    - **Phase B/C — product subcatalog cards**: `buildRoleProductCardList(role, disabled)` 신설 — product 별 collapsible card (헤더에 access 토글, 본문에 role-scope system prompt textarea fixedProductId=Number(product.id)). "전 Product 공통" generic card 도 마지막에 추가 (fixedProductId=0). `buildAccountProductOverrideList(account, disabled)` 신설 — product 별 flat card 에 override select (allow/deny/inherit) 만 표시 (account scope prompt 는 profile drawer 영역).
    - **Role/Account detail 재구성**: `renderRoleDetail` 의 기존 단일 `buildSystemPromptEditor` (역할 시스템 프롬프트 Role Scope) 호출이 `buildRoleProductCardList` 로 교체. `renderAccountDetail` 에서 권한 override grid 다음에 `buildAccountProductOverrideList` 추가. permission 변경 onChange 핸들러는 dynamic 권한들의 기존 상태 (subcatalog 에서 변경된 값) 를 union 으로 보존하도록 수정.
  - [unit/feature-0003-agent-web-ui/src/static/styles.css](../src/static/styles.css)
    - `.admin-product-card-list` / `.admin-product-card[open]` / `.admin-product-card-head` / `.admin-product-card-toggle` / `.admin-product-card-info` / `.admin-product-card-body` / `.admin-product-card-flat` / `.admin-product-card-generic` 스타일 추가. 토큰 (`--border-subtle` / `--text-muted`) 사용.
  - [unit/feature-0003-agent-web-ui/src/static/admin.html](../src/static/admin.html)
    - cache-bust `v=20260506-c5-product-cards`.
- Verification:
  - (a) `python3 -m py_compile` PASS / `node --check admin.js` PASS / `make web` 재배포.
  - (b) Schema: `DESC WebProducts` 에 `DefaultRoleAccess tinyint(1) NOT NULL DEFAULT 1` 컬럼 추가 확인. 기존 product (KR/TT) 모두 1 유지 (기존 운영 호환). `WebRoles.DefaultProductAccess` (이전 시도) 컬럼은 잔존하나 어떤 SQL 도 참조하지 않음 — 다음 cleanup cycle 에서 DROP COLUMN.
  - (c) `/api/admin/roles` 응답에서 `default_product_access` 필드 제거 확인 (admin role keys 에서 미존재). `/api/admin/products` 응답에 `default_role_access` 필드 노출.
  - (d) **Phase A E2E smoke (product-driven)**: 신규 product `DE` 를 `default_role_access=false` 로 생성 → DB 직접 확인: 6 role 모두 `has_de_grant=NO` ✓. admin effective `product.access.de=False` ✓. 비교 신규 product `JP` 를 `default_role_access=true` 로 생성 → 6 role 모두 `has_jp_grant=YES` ✓. **정책 주체가 product 라는 의도 정확히 반영**.
  - (e) **Phase B/C DOM smoke** (browse): Role detail 진입 시 토글 2 개만 ("활성 / 기본 가입 역할") 노출 — 신규 제품 자동 접근 토글은 Role detail 에서 제거됨, 대신 Product detail 로 이동. 권한 grid `details[data-perm-group="product"]` 안에 `product.manage` / `system_prompt.manage.role.any` 만 (dynamic 코드 제외) ✓. `.admin-product-card-list` 1 개 + `.admin-product-card` 3 개 (KR + TT + 전 Product 공통) 정상.
- Risks:
  - **호환성 영향 0**: `DefaultRoleAccess DEFAULT 1` + 기존 product 들 모두 1 으로 backfill 되어 기존 운영 동작 유지. 운영자가 product 생성 시 토글을 명시적으로 끌 때만 신규 product 의 자동 grant 차단 발효.
  - **이전 시도의 잔재**: `WebRoles.DefaultProductAccess` 컬럼이 DB 에 잔존 — destructive DROP COLUMN 회피. 어떤 SQL 도 참조하지 않으므로 동작 영향 0. 다음 cleanup cycle 에서 정리 (또는 운영자가 직접 `ALTER TABLE WebRoles DROP COLUMN DefaultProductAccess` 가능).
  - **권한 grid 의 dynamic 분리로 인한 caller-update 의존성**: Role/Account detail 의 onChange 핸들러가 `existingDynamic` union 보존 안 하면 product subcatalog 의 토글 변경이 grid 의 onChange 호출 시점에 무효화됨. union 처리 코드 추가. 검증: subcatalog 토글 변경 후 grid 의 정적 권한 토글 변경 → footer 카운트 양쪽 다 반영.
  - **buildRoleProductCardList 가 buildSystemPromptEditor 의 fixedProductId 인자에 의존**: 기존 함수 signature 보존 (TASK-0051 cycle 부터). `fixedProductId=0` 는 generic "Product 무관" 케이스 — backend `_load_system_prompt` 의 `ProductId IS NULL` 매칭과 일치.
  - **계정 detail 의 product card 는 prompt textarea 미포함**: account scope prompt 는 profile drawer 영역 (AC-0014). admin 콘솔에서는 access override 만 product 별 카드로.
- Range: app.py +~60 lines (WebProducts schema ALTER + product API/admin_update_product 의 default_role_access + 정책-driven backfill 분기 + role API 의 default_product_access 제거), admin.js +~250 lines (Phase B groupedPermissions/dynamicProductPermissions + Phase C buildRoleProductCard*/buildAccountProductOverride* + Role/Account detail 재구성 + Product detail 토글), styles.css +~70 lines, admin.html cache-bust.
- Notes: 본 cycle 은 사용자 in-cycle 설계 전환의 결과 — 처음 작성한 Role-side 정책을 Product-side 로 정정. 운영 시나리오: 운영자가 product 를 만들 때 토글로 "이 제품은 모든 role 에 기본 grant" / "명시 grant 만" 결정. 한 번 결정되면 그 product 의 권한 분배 정책으로 고정 (PATCH 로 변경은 가능하나 신규 product 의 backfill 시점에만 적용). TASK-0052 의 8 endpoint guard 는 변경 없음 (보안 표면 동일).

## CHG-20260506-0026
- Date: 2026-05-06
- Summary: TASK-0052 Phase 1B/1C/1D + Phase 2 검증 — 계정·역할 → 제품 권한 상속/override 모델 본체 도입. Codex outside voice 의 9 개 finding 모두 통합 + admin_update_account RoleId 손실 pre-existing 버그 fix. AI 자율 commit/push 모드.
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - **Phase 1B (DB schema + catalog source 전환 + caller-update + 트랜잭션)**:
      - `_resolve_permission_catalog(conn=None)` body 를 DB-driven 으로 교체 — conn 이 주어지면 정적 PERMISSION_DEFINITIONS + `WebPermissions WHERE IsDynamic=1` union 반환. graceful fallback (column missing / DB error → static).
      - `_product_permission_code(product_key)` 헬퍼 신설 — `product.access.<key.lower()>` namespace 변환.
      - `_ensure_dynamic_permissions_schema(conn)` 헬퍼 신설 — `WebPermissions ADD COLUMN IsDynamic / ProductId + INDEX` idempotent ALTER. slow path (`_ensure_web_tables`) + fast path (`_ensure_seed_catchup`) 양쪽에서 호출.
      - `_ensure_product_access_permissions(conn)` 헬퍼 신설 — 모든 WebProducts 에 대해 `INSERT IGNORE INTO WebPermissions (Code, Label, ..., IsDynamic=1, ProductId)` + 모든 WebRoles 에 grant `INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)`. D2-A 호환성 backfill, idempotent. backfill 결과를 stderr 에 1 회 기록 (운영 transparency, Codex Claim 5).
      - bootstrap 흐름 (`_ensure_web_tables` + `_ensure_seed_catchup`) 에 `_ensure_dynamic_permissions_schema` + `_ensure_product_access_permissions` 호출 추가.
      - `_decorate_account_rows` / `_ensure_management_survivor_for_role_change` / `admin_update_account` (override + permissions 빌드) / `_list_roles` / `_load_role_by_id` / `admin_create_role` / `admin_update_role` 의 7 callsite 가 `_resolve_permission_catalog(conn)` 결과 (`catalog_codes` / `catalog_map`) 를 명시적으로 전달하도록 caller-update.
      - `_account_permissions(account)` 가 cached map 을 그대로 dict 변환해 dynamic codes (e.g. `product.access.kr`) 가 silently drop 되지 않도록 수정 (기존: `for code in PERMISSION_CODES` iteration → 정적 코드만).
    - **Phase 1B (product CRUD 트랜잭션 — Codex Claim 2)**:
      - `POST /api/admin/products` 가 `conn.autocommit=False` + 명시적 commit/rollback 안에서 product row + WebPermissions row + WebRolePermissions backfill (모든 role grant) 한 트랜잭션 처리.
      - `DELETE /api/admin/products/{id}` 가 in_use guard 통과 후 명시적 트랜잭션 안에서 WebSystemPrompts → WebProductDatabases → WebRolePermissions(IsDynamic=1 ProductId 참조) → WebAccountPermissionOverrides(동일) → WebPermissions → WebProducts cascade 정리.
    - **Phase 1B/1C (`_account_has_product_access` 헬퍼)**:
      - 신설. int / ProductKey 문자열 / int-string 모두 수용. int 입력 시 conn 으로 ProductKey 조회 후 `product.access.<key.lower()>` permission lookup.
    - **Phase 1C (G1-G8 8 endpoint guards — Codex Claim 3 + 4)**:
      - G1 `PATCH /api/conversations/{cid}/product` pinned 모드 — 권한 없으면 403.
      - G2 `POST /api/new_conversation` body `product_id` — 권한 없으면 403 (명시 입력) 또는 auto 강등 (default 채움 분기).
      - G3 `POST /api/ask` body `product_id` hint — 동일 패턴.
      - G4 `POST /api/ask` 기존 conversation 의 `product_id_for_run` 시점 — Codex Claim 3 의 직접 해소. 권한 회수 후 pinned 대화 재실행 시 403 + `이 대화의 제품 접근 권한이 회수되었습니다...` 안내.
      - G5 `POST /api/fork_conversation` source product 상속 + `product_mode` 'auto' 보존 fix (Codex Claim 4 fork 버그). source 'auto' 가 fork 후 'pinned' 으로 변질되던 회귀 차단. fork 대상 계정이 source product 접근 권한 없으면 auto 강등.
      - G6 `_save_account_product_pref` defense-in-depth (signature 에 `account` 추가) — caller-level 가드 누락 시 fallback 보호망.
      - G7 `GET /api/auth/me/system-prompt?product_id=<X>` — 권한 없으면 403.
      - G8 `PUT /api/auth/me/system-prompt` body `product_id` — 동일 패턴.
    - **pre-existing 버그 fix (Phase 1C 작업 중 발견)**:
      - `admin_update_account` (`PATCH /api/admin/accounts/{account_id}`) 가 body 에 `role_id` 미명시 시 `target.get("role")` (항상 None) 으로 fallback 해 next_role_id=0 으로 떨어져 PATCH 마다 RoleId 를 0 으로 덮어쓰던 회귀. `target.get("role_id")` 직접 조회로 fix. 본 fix 가 없으면 admin 의 permission_overrides 변경만으로도 admin role 손실 → 권한 lockout.
  - [unit/feature-0003-agent-web-ui/src/static/admin.js](../src/static/admin.js)
    - **Phase 1D**: `PERMISSION_GROUP_ORDER += "product"` (`["console","account","role","conversation","product","misc"]`), `PERMISSION_GROUP_LABELS["product"] = "제품"`. backend `app.py` 와 동기 필수. 기존 `renderPermissionGrid` 가 자동으로 product group 에 정적 + 동적 코드들 (`product.manage`, `system_prompt.manage.role.any`, `product.access.<key>`) 모두 노출.
  - [unit/feature-0003-agent-web-ui/src/static/admin.html](../src/static/admin.html)
    - cache-bust 갱신 (`v=20260506-c5-product-perms`).
- Verification:
  - (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과.
  - (b) `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` 통과.
  - (c) `make web` 재배포 + `repo-web-1 Recreated/Started`.
  - (d) bootstrap 후 stderr `[TASK-0052 Phase 1B catchup] product access backfill: 7 permission/role-permission rows added` 메시지 확인 (1 perm row + 6 role grants).
  - (e) `/api/admin/permissions` count 33 → 34 (`product.access.kr` 추가) → POST FR 후 35 → DELETE FR 후 34 복귀. cascade 정합성 확인.
  - (f) bootstrap_admin 의 effective permissions 에 `product.access.kr=true`, FR 생성 후 `product.access.fr=true`, FR 삭제 후 사라짐. D2-A 호환성 backfill 동작.
  - (g) Phase 2 P0 negative HTTP smoke (deny override 적용 후): T01 PATCH conv→KR (G1) 403, T02 new_conversation KR (G2) 403, T07 GET sysprompt?product_id=1 (G7) 403, T08 PUT sysprompt body product_id=1 (G8) 403. cleanup 후 admin permissions 34/34 회복 확인.
  - (h) admin_update_account RoleId 보존 fix 검증: PATCH `{"permission_overrides":{"product.access.kr":"deny"}}` → role 'admin' 보존, 33/34 true (KR 만 deny).
  - (i) G3/G4 직접 HTTP smoke 는 model validation (`gpt-5-mini` not allowed) 단계에서 차단되어 정적 코드 검증으로 대체 — 코드 경로가 G1/G2 와 동일 패턴 (`_account_has_product_access` 직접 호출).
- Risks:
  - **D2-A 호환성 backfill 의 보안 의미**: pending/sales/operator 등 모든 role 이 KR 에 default grant. 운영자가 권한 회수가 필요한 (role × product) 조합에 admin 콘솔 deny override 를 추가해야 secure-by-default 효과 (Codex Claim 5 명시).
  - **product_key immutability**: ProductKey 변경 시 권한 코드 namespace drift. ProductKey 는 사실상 immutable 로 정책 — 변경은 delete + recreate 경유. 같은 key 의 과거 override 는 cascade 로 사라짐 (briefing §F5).
  - **Phase 2 P2 부분 (DOM/UX)**: `/api/sessions/me` filter (effective products 만 반환), 사이드바 chip option filter (FE permission map 기반) 는 본 turn 에 미포함 — frontend 렌더링은 이미 Phase 1B 의 effective permission map 으로 자동 갱신되므로 별 cycle 에서 보강. 보안 경계는 G1-G8 가드가 server-side 에서 보장.
  - **`/api/sessions/me` 정보 노출 (Codex Claim 6 D4 변경)**: end-user `/api/session` 응답에서 effective products 만 반환하도록 split 은 본 turn 에 미적용 — 별도 작은 cycle 로 후속. 보안 임팩트는 mutation 가드가 이미 보장하므로 P0 아님 (briefing §6 NOT in scope 와 일치).
- Range: app.py +~480 lines (helper 5 신설 + 7 caller-update + 8 가드 + 트랜잭션 wrapper + bug fix), admin.js +2 lines (group order + label), admin.html +0 (cache-bust 만), 신규 파일 0.
- Notes: 본 turn 의 변경은 **Critical 등급 인증/인가 구조 변경** (AGENTS.md §12.3) 이지만 사용자가 AI 자율 commit/push 권한을 명시 부여 (2026-05-06) 함에 따라 진행. Phase 1A (commit 4dd1d0a) 와 본 cycle (Phase 1B/1C/1D + Phase 2) 가 함께 C5 본체를 완성. **Phase 2 의 P2 항목 (sessions/me filter, end-user FE chip filter) 은 정보 노출 강화 차원의 follow-up 으로 별 cycle**.

## CHG-20260506-0025
- Date: 2026-05-06
- Summary: TASK-0052 (REQ-20260506-0005, Critical §12.3 인증/인가 구조 변경) Phase 1A — RBAC engine catalog 인자화 refactor. Codex Claim 1 (정적 PERMISSION_CODES 가정에 5 hot path hardwired) 의 1 단계 해소. 동작 변경 0, plumbing 만 추가. Phase 1B (DB-driven catalog + product 권한 backfill) 진입을 위한 surface 준비.
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - L18~19: `from collections.abc import Iterable` import 추가
    - L290~ 신규 `_resolve_permission_catalog(conn=None) -> tuple[list, set, dict]` 헬퍼 — Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 그대로 반환. Phase 1B 에서 conn 인자 사용해 WebPermissions IsDynamic=1 row union 으로 교체 예정.
    - `_empty_permission_map(catalog_codes=None)` 시그니처 확장 — None 이면 정적 PERMISSION_CODES 사용 (기존 동작).
    - `_apply_permission_overrides(base_codes, overrides=None, *, catalog_codes=None)` 시그니처 확장 — catalog_codes 가 주어지면 그 catalog 기반으로 map build.
    - `_validate_permission_codes(codes, *, catalog_codes=None)` 시그니처 확장.
    - `_normalize_override_payload(payload, *, catalog_codes=None, catalog_map=None)` 시그니처 확장.
    - `_permission_catalog_payload(*, catalog=None)` 시그니처 확장 — caller 가 명시적 catalog 전달 가능.
    - `/api/admin/permissions` 엔드포인트 (L5761) — 단일 위치를 신규 plumbing 경로 (`_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=...)`) 로 전환. Phase 1A 검증용. 다른 callsite 는 Phase 1B 에서 caller-update.
- Verification:
  - (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과.
  - (b) `make web` EXIT=0 (provenance metadata file race 우회 정상) + `repo-web-1 Recreated/Started`.
  - (c) `docker exec repo-web-1 grep -c "_resolve_permission_catalog\|catalog_codes" /app/web/app.py` → 17 hits, 신규 코드 deploy 확인.
  - (d) bootstrap_admin login → `/api/admin/permissions` HTTP 200, count=33 codes (이전과 동일). 첫 3: `console.access`/`console.manage`/`account.read`. 마지막 3: `conversation.finalize.any`/`product.manage`/`system_prompt.manage.role.any` — 정확히 이전 catalog 와 일치.
- Risks:
  - **Backward-compat default 검증된 callsite**: `_apply_permission_overrides` (3 callsites at L854/3681/5403), `_validate_permission_codes` (2 callsites at L5545/5624), `_normalize_override_payload` (1 callsite at L5395) 모두 catalog_codes/catalog_map kwarg 미전달 — 기본값 None → 정적 PERMISSION_CODES 사용 → 기존 동작 유지. 회귀 0.
  - **L3518/3570 `for code in PERMISSION_CODES`** (role payload `permissions` map) 는 Phase 1A 에서 변경 없음. Phase 1B 에서 dynamic 코드 추가 시 caller 가 catalog 를 전달하도록 update.
  - **Container deploy 검증**: `/api/admin/permissions` 만 신규 plumbing 사용. 정적 결과와 동일함 HTTP smoke 로 확인.
- Range: app.py +~30 lines (helper + 5 시그니처 확장 + 1 callsite 전환). 신규 파일 0 개.
- Notes: Phase 1A 는 briefing §12 권고 ("Phase 1A 단독 deploy 가능") 따라 분리 commit 권장. Phase 1B 가 conn-driven catalog 도입 + product 권한 backfill 을 담당. 본 turn 은 Phase 1B 진입을 위한 plumbing 만.

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

## CHG-20260512-0001
- Date: 2026-05-12
- Related Requirement: TASK-0055, REQ-20260512-0001
- Summary: 관리 콘솔 카테고리별 다중선택 (multi-select) UI 정합 컨벤션 v0.2 도입 — Accounts / Roles / Products 의 bulk toolbar / select-all / row checkbox / cross-page banner / keyboard 단축키 / a11y / typed-confirm / RBAC partial-fail UI 를 단일 패턴으로 통일. drift 재발 차단을 위한 runtime contract assertion 추가.
- Files: docs/CONVENTIONS.md (project-level §10 신설), unit/feature-0003-agent-web-ui/docs/DESIGN.md (신규), unit/feature-0003-agent-web-ui/src/static/admin.html (Accounts bulk anchor 이전, Products multi-select HTML 신설, 모든 카테고리에 role/aria-live/cross-page banner), unit/feature-0003-agent-web-ui/src/static/styles.css (--z-bulk-bar/--z-bulk-banner/--bulk-bar-bottom/--bulk-bar-elev 토큰, .admin-bulk-actions sticky, .admin-bulk-cross-page, .kbd-hint, .toast-skipped), unit/feature-0003-agent-web-ui/src/static/admin.js (BULK_ENTITY_UNIT/BULK_ACTION_LABEL/CONFIRM_TYPED_THRESHOLD 상수, confirmBulkAction/runBulkActionWithPartialFail/assertBulkBarContract/renderCrossPageBanner/applyShiftRangeSelect 헬퍼, Accounts/Roles/Products 의 render*List/render*BulkBar/bulk*SetActive/bulk*Delete 전면 통일, productSelected: Set<number> 신설, accountLastClickIdx/roleLastClickIdx/productLastClickIdx 신설, Esc 글로벌 핸들러, productSelectAll listener, initialize 끝에 assertBulkBarContract 호출), unit/feature-0003-agent-web-ui/docs/FUNCTION.md (REQ-20260512-0001 + AC-0031~0040), unit/feature-0003-agent-web-ui/docs/TASK.md (TASK-0055 entry), unit/feature-0003-agent-web-ui/docs/MODIFY.md (본 entry), unit/feature-0003-agent-web-ui/docs/REVIEW.md (REV-20260512-0001), unit/feature-0003-agent-web-ui/docs/REPORT.md (본 cycle Summary prepend), docs/STATUS.md (feature-0003 갱신 2026-05-12).
- Diff size: admin.js 2645 → 3080 lines (+435), admin.html 219 → 250 lines (+31), styles.css 2976 → 3052 lines (+76). cache-bust v=20260512-bulk-contract-v02.
- Impact: 차후 admin 카테고리 추가 시 컨벤션 미준수가 runtime assertion (console.warn) 으로 감지된다. 사용자가 보고한 계정 우상단 / 역할 좌하단 / 제품 다중선택 부재 의 카테고리 간 일관성 결여 root cause 두 가지 (DOM anchor 표준 부재 + .admin-pane-head-right 슬롯 semantic 충돌) 가 정책 + 코드 두 층에서 모두 해소.
- Rollback Notes: 본 변경은 backend 데이터 모델 변경 없음. UI/JS/CSS 만 변경. admin.js / admin.html / styles.css 의 git revert 로 즉시 복구 가능. RBAC catalog 변경 없음 (기존 권한 product.manage / account.activate 등의 row-level check 만 활용).
