---
doc_type: REPORT
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary

**2026-06-15 TASK-0267 — 권한 grid 트리(tree) UI 재구성: 2열 grid 뒤틀림 해소 + "더 보기 부여됨" 빨강 가시성** (REV-20260615-0267 [SKIPPED:ui-tree-layout-no-logic-change], **Minor §12.3**, frontend-only `src/static/{admin.js,styles.css,admin.html}` + 테스트/문서). 사용자 보고(`관리 권한` 정상 확인 후 `운영 권한` 테스트 중): ① 도달성 보존 "더 보기 · N개 부여됨" 빨강 하이라이트가 운영 권한에서 안 보임 ② 항목 숨김 시 기존 항목이 **뒤틀림** → 상위 권한에 **tree 형태 UI** 요청. **진단**: `.permission-grid-list` 가 `display:grid; grid-template-columns: repeat(2, ...)`(2열) — 행 숨김 시 남은 항목이 2열로 재배치(가로 reflow)돼 뒤틀림. 빨강 badge 는 **로직·CSS 정상**(라이브 실측 checkbox/override 둘 다 `rgb(180,35,31)`)이나 2열 뒤틀림에 "더 보기" 버튼이 묻혀 안 보인 것. **수정**: ① (admin.js) 신규 `_orderItemsAsTree(items)` — 그룹 내 권한을 `PERMISSION_DEPENDENCIES` 트리 DFS 순서(부모 먼저, 자식 들여쓰기)로 정렬, 각 row 에 `data-perm-depth`. 그룹 내 루트=depth 0(부모 없음 / 부모가 다른 그룹, 예: account.read 부모 console.access), 자식=depth+1. 누락 안전망(렌더 누락 0). ② (styles.css) `.permission-grid-list` 를 **2열 grid → 단일 열 flex column** + depth 들여쓰기(`[data-perm-depth="1"] margin-left` + 좌측 가이드 border + 가로 tick 연결선) → 자식 숨김 시 부모는 제자리, **가로 reflow 0**(뒤틀림 해소). `.permission-group-more` 를 flex(grid-column 제거 → align-self) 로, 구 `.permission-row-dependent` accent 제거(depth 기반 대체). **비변경**: disclosure 가시성·게이트·도달성(그룹 유지/배지)·저장 경로·`has-granted` 빨강 CSS·RBAC·엔드포인트 0(순수 렌더 순서+레이아웃). **검증**: `test_permission_dependency_map.py` **15 PASS**(기존 11 + 신규 T1~T4: 트리 정렬 부모-자식 순서·depth 정합·own→any 중첩·account.read 루트·grid-list 단일열 CSS 계약) + make test 컨테이너 **회귀 0**(exit=0) + node --check + CSS brace(1167) + **jsdom 실 DOM 14/14**(트리 순서·depth·누락0·숨김 시 부모 순서 유지). 캐시버스터 `?v=20260615-perm-tree-ui`. worktree `ai/claude/perm-tree-ui`(base f0279c3=main). **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008(단일 열 트리·들여쓰기·운영 권한 "부여됨" 빨강 가시성 시각검증).

### Git 동기화 결과 (TASK-0267)
- 커밋: <cycle commit hash> (ai/claude/perm-tree-ui, base f0279c3)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008 — 트리(단일 열) 레이아웃·자식 들여쓰기·운영 권한 "더 보기 · N개 부여됨" 빨강 가시성·뒤틀림 0 실측.

**2026-06-15 TASK-0268 — 사용자 프로필 / 제품 아이콘 이미지 + Identicon 기본** (동시세션 TASK-0267[perm-tree] 선점으로 0267→0268 재번호; REV-20260615-0268 [SUBAGENT:image-upload-security] **SHIP**, **Major §12.3** — 신규 스키마 컬럼 2 + 이미지 업로드/서빙 엔드포인트 6, `src/app.py` + `src/static/{app.js,admin.js,styles.css,index.html,admin.html}` + 신규 테스트). 사용자 요청: 프로필 이미지·제품 아이콘 설정 가능 + 기본은 Identicon/Gravatar. **사용자 결정(AskUserQuestion)**: Gravatar 미사용(email 컬럼 없음·외부 의존 0) → **Identicon 단독**, **프론트 생성**. **백엔드**: ① WebAccounts.AvatarObjectKey + WebProducts.IconObjectKey 멱등 ALTER — slow path(`_ensure_web_tables`) **및** fast-path(`_ensure_seed_catchup`→신규 `_ensure_avatar_icon_schema`) 양쪽(운영 재기동은 fast-path 만 타므로 한쪽만 두면 'Unknown column' — **라이브 검증서 포착·수정**, [[feedback_sql_builder_live_pg_gate]] 적중). ② `_serialize_account`→`avatar_url`, `_list_products`→`icon_url`(object key sha256 캐시버스터). ③ 엔드포인트: `PUT/DELETE /api/auth/me/avatar`(self-service 로그인만) + `GET /api/avatars/{id}`, `PUT/DELETE /api/admin/products/{id}/icon`(product.manage) + `GET /api/products/{id}/icon`. MinIO prefix `avatars/<id>/`·`product-icons/<id>/`(uuid+ext — 파일명 미사용→traversal 0). ④ `_sniff_image`(매직바이트 png/jpg/webp만, **클라 MIME 불신**, SVG/GIF 거부=XSS 차단) + 크기 cap(아바타 2MB/아이콘 5MB) + `_serve_image_object`(content-type 역추론 + `nosniff` + `inline`). **프론트**: `identiconSvg(seed)`(해시 5x5 대칭 SVG, 외부 의존 0·결정론적) + `applyAvatar`(이미지 or Identicon, onerror 폴백) — 사이드바·드로어·제품 드롭업·admin 제품 상세 적용 + 업로드/제거 UI. **비변경**: 기존 RBAC(product.manage 재사용, 신규 권한 0)·기존 엔드포인트·메시지 경로 0. email/Gravatar 미도입. **검증**: 신규 `test_avatar_icon_upload.py` **8 PASS**(매직바이트·SVG/거짓MIME 거부·크기·object key·URL 헬퍼·서빙 content-type·권한 403) + make test 컨테이너 **전체 회귀 0**(PYTEST_EXIT=0) + ruff + node --check + CSS brace(1175=1175) + **Playwright 격리**(Identicon 결정론·구분·렌더) + **라이브 라운드트립**(PNG 업로드→`/api/avatars/1?v=...`→서빙 200 image/png·nosniff, SVG 거부, 삭제→null; fast-path 스키마 누락 버그 라이브서 포착·수정). **outside-voice 적대적 보안 리뷰 SHIP**(REV-0268, BLOCKER 0 — SVG차단·MIME불신·traversal 0·본인강제·권한게이트·멱등스키마 PASS; MAJOR[nosniff]는 1줄 흡수). [[feedback_outside_voice_for_rbac]] 정합. 캐시버스터 `?v=20260615-task0268-avatar`. worktree `ai/claude/profile-product-avatar`(base f6ccb7b=main). **잔여**: 배포(web) + PB-0008.

### Git 동기화 결과 (TASK-0268)
- 커밋: <cycle commit hash> (ai/claude/profile-product-avatar, base f6ccb7b)
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. app.py(스키마 ALTER + 엔드포인트) + 정적자산 → web 재빌드만.
- 잔여: 정식 배포 후 라이브 재확인(임시 복사본 → 정식 이미지) + PB-0008.

**2026-06-15 TASK-0266 — TASK-0263 핫픽스: usage/conversations 의 interval 파라미터 PG 문법 오류** (동시세션 TASK-0264/0265 선점으로 0265→0266 재번호; **Minor §12.3**, `src/app.py` 1줄 + 회귀 가드 테스트). TASK-0263 배포(머지 후 web 재빌드) 직후 `GET /api/admin/usage/conversations` 가 **HTTP 500** — web 로그 `psycopg.errors.SyntaxError: syntax error at or near "$1" ... interval $1`. **근본 원인**: `_query_usage_conversations` 가 `now() - interval %s`(params=`["{days} days"]`)로 days 를 파라미터화했는데, PG 는 `interval` 키워드 뒤 파라미터 placeholder(`interval $1`)를 **불허**(문자열 리터럴 문법만 허용). admin_llm_usage 는 `interval '{days} days'`(int 보간, days 는 clamp 라 안전)라 무관했으나, 핫스팟에서 파라미터화하려다 문법 위반. **단위 테스트(fake cursor)는 SQL 을 실제 실행하지 않아 통과**시켰고 — **라이브 엔드포인트 검증(실 PG)에서만 포착**. **수정(app.py 1줄)**: `now() - interval %s` → `now() - %s::interval`(캐스트 문법은 파라미터 허용, days 바인드 유지 — 다른 win 패턴 무변경). **회귀 가드**: `test_q2b_interval_cast_not_bare_param`(생성 SQL 에 `%s::interval` 존재 + bare `interval %s` 부재 정적 검증). **검증**: test_usage_conversations.py **12 PASS**(기존 11 + 가드) + py_compile + **라이브 검증**(worktree app.py 임시 web 적용: admin 전체 34건 HTTP 200·좌표/본문 누출 0, 일자 차원 필터 2026-06-15 1건·차트 by_day 정합, profile 200). **교훈**: SQL 빌더 변경은 fake cursor 단위테스트로 불충분 — **라이브 엔드포인트(실 PG) 검증을 게이트화**([[feedback_frontend_real_browser_gate]] 의 백엔드 판). worktree `ai/claude/usage-conv-interval-fix`(base 9ce9ea7=main). **잔여**: 정식 web 재빌드(현재 임시 복사본 실행 중) + PB-0008.

### Git 동기화 결과 (TASK-0266)
- 커밋: <cycle commit hash> (ai/claude/usage-conv-interval-fix, base ac7c1a2)
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor 핫픽스 → PR→머지→cleanup→web 재배포 자동.
- 잔여: 정식 배포 후 라이브 재확인(임시 복사본 → 정식 이미지).

**2026-06-15 TASK-0263 — LLM 사용량 차트 hover 비용 + 클릭→집계 기여 대화목록 모달** (REV-20260615-0263 [SUBAGENT:security-adversarial] **SHIP**, **Major §12.3** — 신규 read 엔드포인트 2개 + admin 타 사용자 대화 메타 인가 표면, `src/app.py` + `src/static/{admin.js,app.js,styles.css,index.html,admin.html}` + 신규 테스트). 사용자 요청: 사용량 차트에 (a) hover 시 모델별 비용 표시, (b) 클릭 시 그 집계 사용량의 대화목록 표시 — 작업 화면 프로필 + 관리 콘솔 양쪽. **사용자 결정(AskUserQuestion)**: 대화목록=**모달/드로어 패널**, admin 범위=**기존 권한 재사용**(신규 RBAC 0). **현황 진단**: admin 도넛은 이미 hover 비용 있음·역할 막대는 계정 drill-down 만(대화목록 아님), 일별 차트·프로필은 비용·클릭 전무, "집계→대화목록"은 양쪽 신규. **백엔드(app.py)**: ① 신규 `GET /api/admin/usage/conversations`(console.usage.read **AND** conversation.list.any — 사용량 권한만으론 타 계정 대화 제목 노출 차단) + `GET /api/profile/usage/conversations`(로그인, owner=self 강제·role/account_id 파라미터 무시로 권한 상승 차단). ② `_query_usage_conversations`: `llm_usage ⋈ core_conversations`(INNER JOIN + `conversation_id IS NOT NULL` — insight/시스템 비대화 usage 제외)로 차원 필터(model=`COALESCE(resolved,model)` / account_ids(역할 역매핑) / day=`to_char(date_trunc(gran))` / owner)된 대화별 호출·토큰·비용·models[] fold. 차원 SQL 은 `admin_llm_usage` 집계와 **동일 규칙**(차트 수치↔대화목록 정합). 좌표/비번/메시지 본문 비노출(메타만), `_USAGE_CONV_LIMIT=200`+truncated. ③ `_usage_account_ids_for_role`(시스템→None·역할없음·역할명), `_enrich_usage_conv_owner_meta`(admin 만 owner 사용자명/역할). ④ by_day_model·by_model 에 `cost_usd` 추가(hover 비용), profile totals.cost_usd. **프론트**: admin.js renderStacked(일별)·renderStackedHBar tooltip 에 모델별 비용 병기 + 차트 요소 `data-usage-model/day` 후크 + `bindUsageDrill`·`openUsageConversations`·`showUsageConvModal`(deep-link `/?conversation=`). 계정 drill 행 클릭→대화 모달. app.js renderProfileUsageStacked/Donut `<title>`에 비용 + 클릭 후크 + 본인 전용 모달 + 추정비용 카드 + `initializeWorkspace` 가 `?conversation=` deep-link 선호 활성화. styles.css usage-conv 모달(admin 넓은 판 + profile 독립 판). **비변경**: RBAC 카탈로그·스키마·기존 엔드포인트 shape(필드 추가만)·메시지 본문 경로 0. **검증**: 신규 `test_usage_conversations.py` **11 PASS**(대화별 fold·INNER JOIN·차원 WHERE/params·좌표 비노출·빈 account 단락·admin AND 게이트 403×2·시스템역할 빈목록·profile 권한상승 차단·역할→계정 역매핑) + make test 컨테이너 **전체 회귀 0**(PYTEST_EXIT=0) + ruff clean + node --check app.js/admin.js + CSS brace(1156=1156) + py_compile + **Playwright 격리**(차트 막대 클릭→model/day 차원 추출→모달 opener). **outside-voice 적대적 보안 리뷰 SHIP**(REV-0263, BLOCKER/MAJOR 0 — SQLi 0[파라미터화+화이트리스트 gran/fmt], AND-게이트, profile self-scope, 메타only+admin-only owner enrich, INNER JOIN+NULL 가드, 차트정합; MINOR 1[대형 역할 wide IN — admin 신뢰경로]). [[feedback_outside_voice_for_rbac]] 정합. 캐시버스터 `?v=20260615-task0263-usage-drill`. worktree `ai/claude/usage-drilldown-conversations`(base 05592b0... TASK-0261 머지 후 fe87981 위). **잔여**: 배포(web) + 라이브 엔드포인트 검증 + PB-0008.

### Git 동기화 결과 (TASK-0263)
- 커밋: <cycle commit hash> (ai/claude/usage-drilldown-conversations, base fe87981)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. app.py(read 엔드포인트) + 정적자산 → web 재빌드만(ask/insight-worker 무변경).
- 잔여: 라이브 엔드포인트 검증(차원 필터 대화목록 반환) + PB-0008(차트 hover 비용·클릭 모달·deep-link).

**2026-06-15 TASK-0264 — 권한 disclosure 추가 단순화: 게이트 미충족 시 부여된 세부 권한도 "더 보기" 뒤로 숨김(forceVisible 제거)** (REV-20260615-0264 [SUBAGENT:rbac-adversarial] SHIP-WITH-FIXES→흡수→SHIP, **Minor §12.3**, frontend-only `src/static/{admin.js,styles.css,admin.html}` + 테스트/문서). 사용자 보고: "`세부 권한 N개 더 보기` 를 클릭하지 않아도 기본적으로 항목이 노출되는 버그 — 최대한 단순화하여 숨겨지도록". **원인**: TASK-0257 의 비파괴 `forceVisible`(부여된 권한+조상을 게이트 OFF 라도 항상 표시)이, 게이트 OFF 인데 일부 세부 권한이 부여된 역할에서 그 부여 항목을 "더 보기" 클릭 없이 노출(사용자가 이전 AskUserQuestion 에서 "비파괴" 를 택했으나 실사용 후 "최대한 숨김" 으로 전환). **수정(admin.js)**: `_applyPermissionDisclosure` 에서 `forceVisible` 제거 → row 는 **게이트 체인이 충족(선행 권한 모두 양성)돼야만** 노출(부여 여부 무관). 게이트 reveal(`계정 조회` 체크 → 나머지 표시)·마스터 게이트(`관리 콘솔 접근`)·own→any 는 불변. **부여 항목 도달성 보존**(적대 리뷰 안전속성): `_refreshGroupDisclosure` 가 부여 항목이 있는 그룹은 게이트 OFF 라도 **vanish 안 함**(`grantedCount>0`) + "더 보기 · N개 부여됨"(`.has-granted` 강조) 표면화 → 부여된 권한이 영구히 가려지지 않고 "더 보기" 로 도달, 그룹 헤더 `N/M 선택` 카운트도 부여 수 노출. 저장 경로(`querySelectorAll(':checked')`/select)는 hidden row 도 그대로 읽어 **저장 누락 0**. orphan 경고칩(`_setPermOrphanWarn`/`_permLabel`)은 부여+게이트OFF 행이 이제 숨겨져 무의미 → 제거. **적대 리뷰 SHIP-WITH-FIXES → 흡수**: 안전 카테고리(부여 도달불가/저장누락/섹션숨김trap/리스너중복/게이트시맨틱) **전부 refute**; MINOR 1건 흡수 — **계정 override 편집기는 컨테이너가 `.override-grid`(≠`.permission-grid`)라 TASK-0258 의 `.permission-grid [data-perm-code][hidden]` 강제 규칙이 override 행에 미적용**(`.field{display:flex}` 가 `[hidden]` override → 안 숨겨짐) → CSS 셀렉터를 컨테이너 무관 `[data-perm-code][hidden]` 로 unscope(test_c1 도 unscoped 검증으로 강화). **검증**: `test_permission_dependency_map.py` **11 PASS**(V1/V4/V5/V6 새 동작: 게이트 OFF 부여 항목 숨김 + 게이트 충족 시 도달; C1 unscoped CSS 계약) + make test 컨테이너 **전체 회귀 0**(exit=0) + node --check + CSS brace(1130=1130) + **jsdom 실 DOM 17/17**(부여 account.delete 게이트OFF 숨김·그룹 유지·"부여됨" 배지·더보기 클릭 도달·저장 누락0·override). 캐시버스터 `?v=20260615-perm-collapse-granted`. worktree `ai/claude/perm-disclosure-collapse-granted`(base 033ec9d=main). **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008(계정 override 모드 행 숨김 computed display 실측 포함).

### Git 동기화 결과 (TASK-0264)
- 커밋: <cycle commit hash> (ai/claude/perm-disclosure-collapse-granted, base 033ec9d)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008 — 게이트 OFF 시 부여 세부 권한도 숨김 + "더 보기 · N개 부여됨" + 계정 override 모드 행 computed display:none 실측.

**2026-06-15 TASK-0261 — 대화 화면 제품 드롭업 datasource 네트워크 상태 배지** (**Minor §12.3**, `src/app.py` + `src/static/{app.js,styles.css,index.html}` + 신규 테스트). 사용자 요청: 대화 화면 제품 선택 드롭업의 제품 dot 이 "현재는 회색, 파란색만 표시 중" → datasource 연결 상태를 반영. **진단**: dot 은 지금까지 **모드 표시**(auto=회색/`--text-muted`, pinned=파랑/`--primary`)일 뿐 네트워크 상태와 무관했다. conn-health-monitor(TASK-0250)가 admin 콘솔엔 `conn_status` 를 주지만 대화 화면 제품 목록(`_list_products`)엔 미첨부였음. **수정(백엔드)**: 신규 `_attach_product_conn_status(conn, products)` — conn_health 모니터의 사전계산 `snapshot()`(추가 probe 없음)을 `datasources.resolve(key)→scope_key` 로 매핑(admin 의 `all_datasources→scope_key` 와 동일 키)해 각 product 의 `datasources[]` 항목에 `conn_status`{status,elapsed_ms,checked_at} 첨부 + product 레벨 `conn_status_overall`(바인딩 **최악 상태**: unstable>unknown>healthy). 좌표/비밀번호 비노출(status/elapsed/checked_at 만). conn_health 미가용·resolve 실패 graceful(unknown), 바인딩 없는 기본 단일 MySQL 제품은 overall=None. `/api/session`·`/api/auth/me` 두 대화 부트스트랩 호출 직후에만 enrich(admin 경로 _list_products 무영향). **수정(프론트)**: `buildProductDropupItem` 이 `connStatusOverall` 을 받아 dot 에 `.product-dropup-item-dot--conn`+`.is-ok/.is-fail/.is-unknown` 클래스 + title/aria-label. `connStatusMeta(status)` 헬퍼(healthy→연결됨/초록, unstable→연결 불안정/빨강, unknown→상태 확인 중/중립). datasource 배지 tooltip 에 각 datasource 상태 라벨 병기. styles.css 에 conn 상태 dot 색(selector specificity 0,3,0 > 모드 규칙 0,2,0 → 모드색 override). **비변경**: RBAC·스키마·엔드포인트 shape(응답 필드 추가만)·conn_health 모니터·share 0. **검증**: 신규 `test_product_conn_status.py` **8 PASS**(단일 healthy / 멀티 최악 unstable / unknown 우선순위 / 바인딩없음 None / 좌표 비노출 / graceful×2 / 빈목록) + make test 컨테이너 **전체 회귀 0**(PYTEST_EXIT=0) + ruff clean + node --check app.js + CSS brace(1128=1128) + py_compile. **Playwright headless chromium 격리**(healthy=초록 rgb(22,163,74)/unstable=빨강 rgb(220,38,38)/unknown=중립/바인딩없음=pinned 파랑 유지 — CSS override 실증) — [[feedback_frontend_real_browser_gate]]. 라이브 conn_health 실측(mysql-kr-an2-*=unstable, mysql-local/mssql-*=healthy)으로 enrich 소스 유효 확인. 캐시버스터 `?v=20260615-task0261-conn-badge`. worktree `ai/claude/product-conn-badge`(base 05592b0=main). **잔여**: 배포(web 재빌드) + PB-0008 Windows 시각검증(드롭업 dot 색이 상태 반영).

### Git 동기화 결과 (TASK-0261)
- 커밋: <cycle commit hash> (ai/claude/product-conn-badge, base 05592b0)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. app.py(read-only enrich) + 정적자산 변경 → web 재빌드만(ask/insight-worker 무변경).
- 잔여: PB-0008 — 드롭업에서 unstable datasource 제품 dot=빨강, healthy=초록 확인(실브라우저).

**2026-06-15 TASK-0260 — 답변 결과셋 ◀▶ 전환 시 확장 높이 보존(스크롤 점프 제거)** (**Minor §12.3**, frontend-only `src/static/{app.js,share.js,index.html,share.html}`). 사용자 보고: assistant 답변 안에서 결과셋을 ◀▶ 버튼으로 전환할 때, 결과셋마다 높이가 달라 스크롤 위치가 jump. **근본 원인**: `buildSqlNavigator` 의 `.sql-nav-panels` 가 min-height 없이 display 토글(`.is-active`)만 해서, 활성 패널 높이로 컨테이너가 매 전환 재조정 → `.result-table-wrap` 의 `max-height: min(60vh,460px)` 때문에 결과셋별 높이 편차가 커 큰 결과셋(예 460px)→작은 결과셋(예 40px) 전환 시 컨테이너가 급격히 줄며 아래 콘텐츠가 위로 점프. **수정(app.js + share.js)**: navigator 인스턴스별 `maxPanelHeight` 추적 + `preserveHeight()`(panels.scrollHeight 가 더 크면 `panels.style.minHeight` floor 갱신). `update()` 가 전환 **전(나가는 패널)·후(들어오는 패널)** 2회 측정 → 지금까지 본 최대 높이를 바닥으로 박아 **축소만 방지·확장은 허용**. 초기 `update()` 는 DOM attach 전이라 scrollHeight=0 → floor 무변(무해). **비변경**: CSS(styles.css/share.css) 0 — min-height 는 JS inline 동적 설정. 백엔드/스키마/RBAC/엔드포인트 0. **검증**: `node --check` app.js/share.js PASS + **Playwright headless chromium 격리 검증**(buildSqlNavigator 핵심 로직 동형 재현: 큰 1000px→작은 2행 전환 시 panels.h 불변[minHeight=1000px floor]·아래콘텐츠 점프 **0px**; **수정 전 대조 = 960px 점프** 재현으로 회귀 가드 유효성 확인) — [[feedback_frontend_real_browser_gate]] 정합. 캐시버스터 `?v=20260615-task0260-sqlnav-height`(index.html app.js·share.html share.js). worktree `ai/claude/sqlnav-height-preserve`(base 038cacb=main). **잔여**: 배포(web 만 — frontend) + PB-0008 Windows 시각검증(CHECK#13 WARN-only).

### Git 동기화 결과 (TASK-0260)
- 커밋: <cycle commit hash> (ai/claude/sqlnav-height-preserve, base 038cacb)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. frontend-only(JS) 라 web 재빌드만.
- 잔여: 최종 PB-0008 — 다중 결과셋 답변에서 ◀▶ 전환 시 스크롤 점프 없음(실브라우저).

**2026-06-15 TASK-0258 — TASK-0257 핫픽스: 권한 disclosure 의 hidden row 가 실브라우저에서 안 숨겨지던 CSS override 버그** (**Minor §12.3**, frontend-only `src/static/{styles.css,admin.html}` + 회귀 테스트). TASK-0257 배포 후 **PB-0008 Windows-browser 시각검증 중 발견**: 마스터 게이트 그룹 vanish(`.permission-group[hidden]`)는 정상이나, **within-group 행 게이팅이 실브라우저에서 무력**(예: `관리 콘솔 접근` 체크 후 `계정 조회`만 보여야 하는데 계정 권한 7개가 다 보임). **근본 원인**: `.permission-toggle-card{display:flex}`(author rule, specificity 0,1,0)가 UA 의 `[hidden]{display:none}`(0,1,0)를 **동일 specificity·후순위로 override** → JS 가 `el.hidden=true` 를 줘도 computed `display:flex` 라 행이 계속 렌더. eval 은 `.hidden===true` 를 읽어 정상으로 보였고, **jsdom 은 CSS 캐스케이드/렌더링이 없어 30/30 통과**시킴 → **실브라우저(PB-0008)만 검출 가능한 클래스**([[feedback_visual_verify_on_design_change]]·TASK-0236 교훈 입증). **수정(styles.css 1규칙)**: `.permission-section[hidden], .permission-group[hidden], .permission-grid [data-perm-code][hidden] { display:none !important; }` — disclosure 의 section/group/row 모든 숨김 대상에 display:none 강제(프로젝트 기존 `.search-modal-overlay[hidden]{display:none}` 선례와 동형). 캐시버스터 `?v=20260615-perm-disclosure-hidefix`. **검증**: 신규 회귀 가드 `test_c1_hidden_rows_force_display_none`(styles.css 에 `[data-perm-code][hidden]` display:none !important + group/section 규칙 존재 정적 검증) 포함 **11 PASS**(기존 10 + C1) + make test 컨테이너 **전체 회귀 0**(make exit=0) + CSS brace(1125=1125) + **실브라우저 수정 CSS 주입 후 computed display 재확인**(account.read=flex, 나머지 6개=none, 표시 1개). **잔여**: 배포(web 만 — `deploy_scope: included`) + 최종 PB-0008 확인. worktree `ai/claude/perm-disclosure-hidden-css`(base 4782fd3=main, TASK-0257 직후).

### Git 동기화 결과 (TASK-0258)
- 커밋: <cycle commit hash> (ai/claude/perm-disclosure-hidden-css, base 4782fd3)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. frontend-only(CSS) 라 web 재빌드만.
- 잔여: 최종 PB-0008 — `관리 콘솔 접근` 체크 후 계정 그룹에서 `계정 조회`만 보이고 나머지 접힘(실브라우저 display:none 확인).

**2026-06-15 TASK-0257 — 관리 콘솔 계정·역할 권한 편집기 점진적 세분화(progressive disclosure)** (REV-20260615-0257 [SUBAGENT:rbac-adversarial] SHIP-WITH-FIXES→흡수→**SHIP**, **Major §12.3** (권한 편집 surface), frontend-only `src/static/{admin.js,styles.css,admin.html}` + `docs/CONVENTIONS.md` §10.6 + 신규 테스트). 사용자 요청: `관리 콘솔 > 계정, 역할 > [각 항목]` 의 카테고리별 권한 UI 를 종속성 기반으로 점진적으로 세분화 — `관리 콘솔 접근(console.access)` 체크 시 관리 권한 내부 항목 표시, `계정 조회(account.read)` 체크 시 나머지 계정 권한 표시, 운영 권한도 동일, **UI 뒤틀림 방지**. **설계**: 선언적 종속성 맵 `PERMISSION_DEPENDENCIES`(child→선행 parent, 31엔트리) — 관리 권한 section 은 `console.access` 가 **마스터 게이트**(account.read/role.read/audit.read.own/system_prompt.global.read 의 부모=console.access → OFF 시 계정·역할·감사·설정 그룹 통째 vanish), 각 그룹 base 가 세부 권한 게이트; 운영 권한은 마스터 게이트 없이 `.any`(전체)→`.own`(내) 종속. **비파괴(사용자 확정)**: 이미 부여된(체크/override 허용·거부) 권한과 그 조상은 게이트 무관 **항상 표시**(forceVisible 조상 마킹), disclosure 는 row 를 *접을* 뿐 *제거*하지 않고 저장 경로(`querySelectorAll('input:checked')`)는 hidden row 도 그대로 읽음 → 권한 조용한 회수 0. 각 그룹 "세부 권한 N개 더 보기" 로 강제 노출 + orphan 경고칩(부여됐으나 게이트 OFF — checkbox 모드). **§10.6 정합**: section/group 정렬·DOM 구조 불변, row 단위 hidden 토글로만 동작(레이아웃 뒤틀림 0, reveal 즉시 토글·애니메이션 없음). **mode 분기(적대 리뷰 MAJOR 흡수)**: 그룹/섹션 통째 vanish 는 checkbox(역할) 모드만 — 마스터 게이트 체크박스가 항상 보이는 복원 레버라 trap 없음; override(계정) 모드는 게이트 select 가 그 자신도 접힐 수 있어 그룹 vanish 시 "더 보기" 탈출구까지 사라져 도달 불가 → **그룹/섹션 비숨김**(§10.6 "전체 표시" 정합) + row 만 접고 "더 보기" 항상 도달 가능. **outside-voice 적대 리뷰(REV-0257)**: SHIP-WITH-FIXES — #1 안전속성(부여 권한 미숨김·저장 누락 0) **400k fuzz refute**, 저장경로/perf/제품그룹/맵정합/§10.6 정렬 전부 refute; MAJOR(override 그룹 도달불가 trap) + MINOR(dead branch) 흡수. **비변경**: 백엔드 RBAC enforce·권한 code·persistence·엔드포인트·스키마 0(순수 편집기 표시 UX). **검증**: 신규 `test_permission_dependency_map.py` **10 PASS**(맵 정합 M1~M4 + 가시성 불변식 V1~V6 — 비파괴/마스터게이트/own→any/orphan/override) + make test 컨테이너 **전체 회귀 0**(진행 100%·skip 2·F/E 0·make exit=0)+ruff clean + node --check + CSS brace(1113=1113) + **jsdom 실 DOM 검증 30/30**(마스터게이트 vanish·그룹 reveal·intra-group 게이팅·orphan 칩·저장경로 안전·override no-vanish·"더 보기" 도달/클릭). 캐시버스터 `?v=20260615-perm-disclosure`. worktree `ai/claude/perm-progressive-disclosure`(base f8845cc=main). 동시세션 번호충돌 대비 머지 직전 origin/main 재확인(origin max=0256(diff 작업 선점)→0257).

### Git 동기화 결과 (TASK-0257)
- 커밋: <cycle commit hash> (ai/claude/perm-progressive-disclosure, base f8845cc)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동 진행. ask/insight-worker 코드 무변경(frontend-only)이라 web 재빌드만으로 충분.
- 잔여: PB-0008 Windows-browser 시각검증(역할: console.access 체크→그룹 등장·account.read 체크→세부 노출; 계정 override: 그룹 비숨김·더 보기 도달) — 배포 후.

**2026-06-15 TASK-0254 — 제품 프롬프트 '자동 작성' 스트리밍 스크롤 stick-to-bottom** (REV-20260615-0254 [SUBAGENT:frontend-adversarial] SHIP-WITH-FIXES→흡수→**SHIP**, **Minor §12.3**, frontend-only `src/static/admin.js`). 사용자 보고: `관리 콘솔 > 제품 > [항목] > 제품 프롬프트` 의 '자동 작성'(TASK-0237 SSE 토큰 스트리밍) 동작 중, 작성되는 본문 상단을 읽으려 위로 스크롤해도 텍스트가 갱신될 때마다 스크롤이 최하단으로 끌려감. 요구: 갱신 중에도 스크롤을 자유롭게 둘 수 있게 + 최하단일 때만 갱신을 따라 내려가게. **진단**: `handleFrame` 의 `token` 분기가 매 토큰마다 무조건 `textarea.scrollTop = textarea.scrollHeight`. **수정(admin.js)**: `token` 분기는 append **직전** `atBottom = scrollHeight - scrollTop - clientHeight <= 8`(8px=분수픽셀/clamp 오차) 판정 → append 후 `atBottom` 일 때만 최하단 추종(위로 스크롤 상태면 위치 유지). 첫 토큰은 `value=""` 직후 빈 상태→atBottom=true→정상 추종, 비-오버플로 상태는 `scrollHeight==clientHeight`→항상 atBottom→수동 관찰 무회귀. `done` 분기는 서버 `done.prompt`(app.py:16519 `.strip()`)가 누적(un-stripped)과 길이 달라질 수 있어 동일하면 재할당 생략 + `maxTop=max(0,scrollHeight-clientHeight)` clamp(`atBottom?maxTop:min(prevTop,maxTop)`)로 재할당發 점프 흡수. 캐시버스터 `?v=20260615-task0254-prompt-stream-scroll`. **outside-voice 적대 리뷰(REV-0254)**: NOT-SHIP 0 — 첫토큰/8px 임계/측정 순서/비-오버플로 무회귀 전부 반박, LOW 1건(done strip 길이차 점프) 흡수. **비변경**: SSE 백엔드 계약·프레임 파싱·abort·pending 저장·meta 표시·styles.css 0(순수 클라이언트 렌더). **검증**: `node --check`(admin.js) PASS + 서버 `.strip()` 사실 확인(app.py:16519) + make test 컨테이너 **회귀 0 PASS**(진행 100%·skip 2·fail/error 0·make exit=0)+ruff clean + verify-completion 9 checks PASS(CHECK#13 WARN=PB-0008 후속). worktree `ai/claude/task0254-prompt-stream-scroll`(base 9c9a5b3=main).

### Git 동기화 결과
- 커밋: <PR push 시 cycle commit hash> (ai/claude/task0254-prompt-stream-scroll, base 9c9a5b3)
- verify-completion: PASS (pre-commit, feature-0003-agent-web-ui — 9 checks, CHECK#13 WARN=PB-0008 후속)
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동 진행. ask/insight-worker 코드 무변경(frontend-only)이라 web 재빌드만으로 충분.
- 잔여: PB-0008 Windows-browser 시각검증(스트리밍 중 위로 스크롤 유지 / 최하단 추종) — 배포 후.

**2026-06-12 TASK-0253 — 관리 콘솔 head-of-line blocking 2건 제거** (REV-20260612-0253 [SUBAGENT:concurrency+SSRF-adversarial] SHIP-WITH-FIXES→흡수→**SHIP**, **Minor §12.3**, frontend+backend). TASK-0250 배포 후 PB-0008 시각검증 중 사용자 발견 2건. **(A) datasource ↻ 새로고침 지연**: 제품 상세 "+ 데이터소스 추가" 드롭다운 ↻ 클릭 시 N개 배지가 "확인 중…"에 9초+ 묶임. 진단(브라우저 실측): 개별 `/test` 45~194ms 인데 동시 11개 시 8~18s. 원인 = `admin_test_datasource`(async def)가 동기 블로킹 `_db.probe_datasource()`(도달불가 시 connection_timeout 8s 점유)를 await/executor 없이 직접 호출 → **이벤트 루프 블로킹** → 동시 /test 직렬화 + 프론트 refresh 가 같은 key 를 force:false(rebuild)+force:true(Promise.all) **2벌** probe(4-cap 세마포어 2배 점유). **(B) 제품 분석 완료율 일괄 대기**: 진입 시 좌측 제품 목록·우측 "insight 분석 완료율"·DB 행 전부 "분석 측정 중…"이 가장 느린 제품 라이브 DB 조회까지 끝나야 한꺼번에 갱신(빠른 제품 개별 즉시표시 안 됨). 원인 = `admin_products_insight_coverage`(동기 def, Starlette 스레드풀 병렬 가능)인데 프론트가 전체 제품을 **1회 fetch + 전역 `productCoverageLoading` 플래그**로 묶음. 둘 다 TASK-0250 이 datasource 연결 도메인에서 제거한 head-of-line 패턴의 잔존. **수정(2 src + 2 test, feature-0003)**: (A) probe 를 `await asyncio.to_thread(_db.probe_datasource, …)` 스레드풀 이관(`/api/ask` `asyncio.to_thread(run_agent)` 기존 패턴) → 이벤트 루프 비블로킹 → N개 /test 가 가장 느린 1건(≤timeout) 안에 완료. 프론트 refresh 는 `_rebuildDsAddList(true)` 단일 경로(중복 Promise.all 제거, `_kickDsConn(force)` 전파). (B) `loadProductInsightCoverage` 를 제품별 `?product_id=N` **단건 병렬 호출**(동시성 cap `_COV_FETCH_MAX=4` via `_runWithConcurrency`) + 전역 플래그 → 제품별 `productCoverageLoadingIds` Set + 끝나는 제품만 즉시 렌더. 백엔드 단건은 대상 제품만 계산 후 break. 캐시버스터 `?v=20260612-task0253-headofline`. **outside-voice 적대 리뷰(REV-0253)**: BLOCKER 0(SSRF pinned-IP/DNS-rebinding 유지·커넥션 누수 없음·break 안전·로딩 stuck 없음 전부 반박). 흡수: MAJOR-2(N-fan-out 공용 anyio 스레드풀[40] 고갈 → 프론트 cap 4 추가), MINOR-2(force 경로 in-flight dedup 부재 → force 무관 합류), MINOR-3(테스트 fake 시그니처 keyword-only 정합); MAJOR-1(테스트 agent 이미지 밖 미실행)은 `make test` green 충족. **검증**: 신규 `test_datasource_test_nonblocking.py`(3: to_thread passthrough/errno 비유출/**동시 probe 비블로킹** 0.3s×5 직렬 1.5s→병렬 ~0.3s) + `test_insight_coverage_endpoint.py`(5: 단건 대상만/**무관 제품 미계산**/전체 무회귀/403/400) **8 PASS** + make test 컨테이너 **전체 회귀 0** + ruff clean + node --check + py_compile. worktree `ai/claude/head-of-line-fix`(base 3a97b86=main 12f5c5e).

**확장 방향 (대규모 — 후속 cycle 후보)**: 제품 수가 수십~수백으로 늘면 매 진입의 N-fan-out(클라이언트 단건 병렬) 자체가 부담이 될 수 있다. 그때 유효한 방향:
1. **백엔드 background 사전계산 worker** — TASK-0250 `conn_health` 모니터 패턴을 완료율에 이식. worker 가 주기적으로 제품별 coverage 를 미리 계산해 두면 화면 진입 시 라이브 DB 조회 없이 즉시 표시(현 on-demand fan-out 제거).
2. **Redis 등 외부 캐시서버에 완료율 스냅샷 저장** — 현재 인메모리 `_insight_cov_cache`(TTL)는 **프로세스 로컬**이라 web/ask-worker/insight-worker 다중 인스턴스 간 공유가 안 된다. Redis 로 옮기면 (a) 인스턴스 공유로 cache hit 율 ↑, (b) 위 background worker 가 계산해 Redis 에 쓰고 web 이 읽는 자연스러운 합류 지점이 된다. 단건 API 도 Redis hit 시 DB 조회 0. (도입 시 datasource 연결 상태[conn_health snapshot]도 같은 Redis 로 공유 가능.)

### Git 동기화 결과
- 커밋: <PR push 시 cycle commit hash> (ai/claude/head-of-line-fix, base 3a97b86)
- verify-completion: <pre-commit 실행 후 갱신>
- Push / PR / main 병합 / 배포: D~E 단계 진행 후 본 항목 갱신(자동 동기화 정책 §16.3 — BLOCKED 없음 + deploy_scope: included → PR→머지→web 재배포). ask/insight-worker 는 코드 무변경이나 동일 agent-common 이미지라 web 재빌드만으로 충분(완료율/probe 변경은 web 프로세스 한정).

**2026-06-12 TASK-0248 — 관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환** (REV-20260612-0248 [SUBAGENT:security+correctness-adversarial, 2-agent] SHIP-WITH-FIXES→흡수→**SHIP**, **Major §12.3** — 파괴적 삭제 + 접근 차단 + cross-store, feature-0002 스키마 교차). 사용자 요청: "관리 콘솔 > 제품에서 각 제품을 삭제할 때, 참조되는 대화가 있더라도 삭제가 가능하도록. 기존의 대화는 막힌 상태(더 이상 대화를 진행할 수 없도록) 전환." + 명확화: "대화 공유는 가능하지만, 대화 자체는 차단으로 진행." → 차단 대화도 **공유(읽기전용)·이력 열람 가능, 새 메시지 진행만 불가**. 설계 승인(AskUserQuestion): **영속 플래그**(`blocked_at`/`blocked_reason`). **구현**: (스키마, feature-0002) alembic `0005_core_conv_blocked`(down_revision=0004, ADD COLUMN IF NOT EXISTS) + 부트스트랩 SQL 멱등 ALTER + app.py MySQL 폴백 parity. (백엔드, app.py) `_conversation_block_info`(fail-open)·`_block_conversations_for_product`(`UPDATE ... WHERE product_id AND blocked_at IS NULL`, backend-aware, 재차단방지) 신설; `admin_delete_product` 가 in_use>0 거부(400) 제거 → cascade 삭제 commit **후** 차단(cross-store "삭제 먼저, 차단 나중") → `{ok, product_id, blocked_conversations}`; `/api/ask` 기존대화 분기가 소유권 직후 blocked→403(slot 前); list PG/MySQL parity 에 blocked 노출. (프런트) canAsk/sendPrompt 가드·composer 입력 disabled+안내·헤더 🚫·목록 "차단" 배지·admin confirm/토스트. 캐시버스터 `?v=20260612-task0248-blocked-conv`. **설계 보존**: fork=차단 전파 안 함(접근불가 제품 auto 강등→원본차단·사본 새 일반대화 정합), share-create=차단 대화 허용(읽기전용). **outside-voice 2-agent 적대 리뷰(REV-0248)**: 백엔드 BLOCKER 0 — probe ①②③④⑤⑦ PASS(특히 ③ cross-store fail-closed 백스톱 **실재 확인**: 제품 cascade 삭제로 WebProducts 행 소멸→`_account_has_product_access` False→ask 403, 차단 UPDATE 실패와 무관하게 진행 차단), probe ⑥(PG 컬럼 부재 시 list SELECT·COUNT 가드 부재로 500)은 **migrate-first 배포 계약으로 흡수**(코드 무변경 — web=DML-only role, alembic 0005 가 정본 적용 경로, 기존 `resolved_model`[TASK-0163] 동일 패턴; 배포 E 단계 `make migrate` 선행 + F 단계 컬럼 psql 실측 게이트); 프런트 **SHIP**(우회 송신 경로 0 — sendPrompt 단일 진입+백엔드 403 이중차단, 공유/이력/fork 요구사항 전부 충족), M-2(admin.js 혼입 의혹)=stale base `git diff` 오탐. **동시세션**: conn-health-monitor(TASK-0250, PR #196 f2a390b)·coverage-multi-ds(0249) active → 머지 직전 origin/main 재확인 후 **f2a390b 위로 rebase**(admin.html 캐시버스터 충돌 1건 해결, app.py/admin.js conn-health+0248 자동 병합 양립). **검증**: 신규 `test_product_delete_block_conv.py` **7 PASS** + make test 컨테이너 **전체 회귀 0**(600 passed/2 skip) + node --check + py_compile + CSS brace 1108=1108 + ruff clean. worktree `ai/claude/task0248-product-delete-blocked-conv`(base ff59f8f→f2a390b 재적용). **잔여**: 배포(make migrate 先 → web 재빌드) + 라이브 검증 + PB-0008 Windows 시각검증.

### Git 동기화 결과
- 커밋: <PR push 시 cycle commit hash> (ai/claude/task0248-product-delete-blocked-conv, base f2a390b 재적용)
- verify-completion: PASS (pre-commit, feature-0003-agent-web-ui)
- Push / PR / main 병합 / 배포: D~E 단계 진행 후 본 항목 갱신(자동 동기화 정책 §16.3 — BLOCKED 없음 + Major → 사람 확인 없이 PR→squash 머지→cleanup, deploy_scope: included).
- 충돌 해결: AI 자율 — rebase 시 admin.html admin.js 캐시버스터 충돌 1건(내 버전 채택), app.py/admin.js conn-health(origin PR#196)+TASK-0248 자동 병합.

**2026-06-12 TASK-0246 — "+ 데이터소스 추가" 드롭다운 항목 열 정렬(고정 열 폭 grid)** (REQ-20260612-0246/AC-0460, REV-20260612-0246 [SKIPPED:trivial-grid-align] + REV-20260612-0247 [SKIPPED:trivial-css-1line] 정련, **Minor §12.3**, CSS-only). TASK-0244 follow-up. 사용자: "`+ 데이터소스 추가` 목록 폭이 문자열 길이에 따라 일정하도록(현재 들쭉날쭉)". **진단(라이브 측정)**: 항목 폭(542px)은 일정하나 `.admin-ds-picker-item` 이 `display:flex` + 이름 `flex:1 1 auto` 라 행마다 엔진 pill(x961/936/967)·좌표(x1011/986/1018)·연결배지(x1105/1080/1080)의 시작 x 가 어긋나 세로 미정렬. **수정(styles.css 단일 블록)**: `.admin-db-picker-item.admin-ds-picker-item` `display:flex`→**`display:grid`** + `grid-template-columns: auto minmax(0,1fr) 56px 124px 104px`(고정 트랙=모든 행 동일 geometry, 이름만 `1fr` 가변 흡수) + 엔진/좌표/연결배지 전부 `justify-self:start`(정련 CHG-0246b — sibling `.cov-db-row`[TASK-0245] 컨벤션·사용자 컬럼 정렬 선호 [[feedback_row_list_column_alignment]] 정합) + 긴 값 ellipsis+title. **비변경**: admin.js·probe·백엔드·RBAC·`.cov-db-row`(동시세션 0245)·DB picker 0(복합 셀렉터 격리). **동시세션 충돌**: db-row-align cycle 이 TASK-0245·CHG/REV/REQ-0245·AC-0385 선점(PR #189/#191) → §13.1 재번호 0245→0246(AC→0460), origin/main(14a296f) 위로 재적용. **배포·검증 완료**: PR #192(grid, main 6756522) + PR #194(정련, main 9c2db34) 머지·push, web 재빌드·재기동(healthz git_commit=9c2db34). **PB-0008 Windows-browser 실측 PASS**: /admin > 제품 "킹스레이드(KR)" > "+ 데이터소스 추가"(datasource 5개) 컬럼 left 좌표 측정 — name/엔진/좌표/연결배지 **전 열 행별 left spread=0px**(각 677/874/938/1070, 수정 전 spread ~31px 들쭉날쭉 해소). 긴 좌표 ellipsis 흡수. 스크린샷 `/tmp/pb0008-ds-picker-colalign-final.png`. worktree `ai/claude/task0246-*`(base f9d8207→14a296f 재적용).

### Git 동기화 결과
- 커밋/PR/배포: main 9c2db34(PR #192 grid + #194 정련) 머지·push·web 재배포·PB-0008 PASS 완료. (TEST.md Run + 본 REPORT docs 후속 #195 예정)


**2026-06-12 TASK-0244 — 관리 콘솔 제품 "+ 데이터소스 추가" 드롭다운 폰트 정합 + 연결 상태 표면화** (REQ-20260612-0244, REV-20260612-0244 [SUBAGENT:design+correctness] **SHIP**, **Major §12.3**, frontend-only). 사용자 요청 2건: 제품 상세(관리 콘솔 > 제품 > [항목]) 데이터소스 탭의 `+ 데이터소스 추가` 목록이 ① 폰트/시각이 다른 UI와 이질, ② 각 데이터소스 연결 상태를 알 수 없음. **진단**: 목록 항목이 `${ds.key} — ${ds.engine} @ ${ds.host}:${ds.port}` 단일 raw `<span>`(무클래스)라 같은 화면 accordion 행(`.ds-acc-name`+`.ds-acc-engine` pill)·`+ 데이터베이스 추가` picker(`.admin-db-picker-name` 구조)와 폰트/정렬이 어긋남. 연결 상태는 `⋯ > 연결 테스트`(일회성 토스트)로만 확인 가능. **수정(frontend-only, admin.js/styles.css/admin.html)**: ① `_rebuildDsAddList` 항목을 `[체크박스 · 이름(.admin-db-picker-name 재사용) · 엔진 pill(.admin-ds-picker-engine = .ds-acc-engine 토큰 1:1) · 좌표(.admin-ds-picker-coord muted) · 연결상태 배지(.admin-ds-conn)]` 구조로 재구성 + 헤더 "데이터소스 · 연결 상태" + ↻ 새로고침. ② `_probeDatasourceConn`/`_paintDsConnBadge` 신설 — 드롭다운 열림 시 `/api/admin/datasources/{key}/test`(기존 엔드포인트) lazy probe → `확인 중… → 연결됨·{ms} / 연결 실패`(원인 tooltip) 배지(`●`점+한글 라벨, 색맹 비의존). `adminState.datasourceConnStatus` Map 세션 캐시(매 토글 재렌더 재probe 방지) + in-flight dedup(`_dsConnInflight`) + **동시 probe 4개 cap 세마포어**(`_dsConnAcquire`/`_dsConnRelease` — 도달불가 다수 + 8s connection_timeout 시 web 스레드 동시 점유 방지, REV nit 선반영). **비변경**: 백엔드 app.py·RBAC(console.access·canDs)·스키마·엔드포인트 shape·datasource 바인딩 스테이징 흐름 0. 캐시버스터 `?v=20260612-ds-picker-status`. **검증**: node --check admin.js PASS + CSS brace 균형 + outside-voice subagent 적대적 디자인/정합 리뷰 **SHIP**(BLOCKER 0). **배포·라이브 검증 완료**: PR #187 main 2b9205a 머지·push, web 재빌드(`sha256:6b05c6…`)·재기동(healthy, healthz git_commit=2b9205a). **PB-0008 Windows-browser 실측 PASS**: /admin > 제품 "킹스레이드(KR)" > "+ 데이터소스 추가" → 3 datasource 가 [이름·엔진 pill·좌표·연결배지] 정합 구조로 렌더(엔진 pill 이 accordion `[mssql]` pill 과 동일 시각), 연결 상태 = `mssql-qa-idc ● 연결 실패`(OperationalError tooltip)·`mssql_local ● 연결됨·8.7ms`·`mysql-local ● 연결됨·8.9ms`(ok/fail/ms 3종 정확). 스크린샷 `/tmp/pb0008-ds-picker-status.png`. worktree `ai/claude/task0244-ds-picker-status`(base f9d8207).

### Git 동기화 결과
- 커밋/PR/배포: main 2b9205a(PR #187) 머지·push·web 재배포·PB-0008 PASS 완료. (TEST.md Run + 본 REPORT 기록 docs 후속 커밋)

**2026-06-12 TASK-0241 — 요청 취소 즉시 처리 + 취소 직후 채팅창 재사용/재요청** (REQ-20260612-0241, REV-20260612-0241 [SUBAGENT:concurrency-adversarial] 2-pass: 1차 BLOCKER 2·HIGH 2·MEDIUM 2 → 흡수 → 2차 **SHIP**, **Major §12.3**, cross-cutting feature-0002+0003). 사용자 보고: "중단을 눌러도 응답이 끝날 때까지 기다린다 — 취소 직후 채팅창 사용·재요청이 가능하게, 부작용도 모두 고려." **진단**: 백엔드 취소 로직(`/api/cancel`+cancel 플래그+agent 루프 폴링)은 정상. 진짜 결함은 **프런트가 `/api/ask` long-poll 을 `await` 하고 busy 해제를 그 `finally` 에서만** 함(app.js sendPrompt) → worker mode 의 동기 응답 계약상 run 종료까지 입력창이 잠김. 추가로 즉시-재요청을 허용하면 같은 conversation 의 old(취소)/new run 동시성 부작용 노출. **수정**: ① **프런트(app.js)** — `cancelCurrentRun` optimistic: busy/입력창 즉시 해제 + pending 말풍선·진행폴링·경과타이머 정리 + in-flight `/api/ask` fetch **abort**(AbortController, `state.askAbortControllers`) + 포커스 + `/api/cancel` 백그라운드 발사. sendPrompt 의 catch 가 `state.userCanceledKeys` 로 사용자 취소를 식별해 에러 토스트/타임아웃 복구 다이얼로그 억제. early-cid(sentinel↔cid) 키 이중성은 `cancelKeys`=양쪽 키 취소 + `askKey` 정렬 + 발사 직전 취소 재확인으로 처리. ② **백엔드(app.py)** — `/api/cancel` 이 pending/running 무관 즉시 KV `canceled`(only_if_current_run) 기록 → orphan `/api/ask` attach 가 슬롯 즉시 반납. attach 루프에 `request.is_disconnected()` + job-aware(`_get_ask_job_status`) 종료로 웹 슬롯 누수 차단. **enqueue 선기록에 sentinel run_id**(`enqpre-<uuid>`) — KV `last_status_run_id` 가 직전(취소) run 으로 남아 orphan terminal write 가 가드를 우회·새 요청 processing 을 클로버하던 BLOCKER 차단. ③ **agent_core.py + memory.py** — `set_run_status(only_if_current_run=True)` supersede 가드: 저장된 last_status_run_id 가 *다른* run 이면 write skip(취소된 orphan 이 새 run 상태 클로버 방지). agent 루프 terminal write(canceled/done/error) 3곳 적용. claim/sentinel takeover 는 default(무조건) 유지. **3중 정합**: sentinel(enqueue) + only_if_current_run(terminal/cancel) + 무조건 takeover(claim, agent_core:2472) → 나열 가능한 모든 인터리빙에서 새 run 보존·취소전용 canceled 오삭제 없음(2차 리뷰 확인). orphan run 은 현재 LLM step(동기, 인터럽트 불가) 종료 후 답변 **기록 없이** 종료. **검증**: 신규 `test_set_run_status_supersede.py` 5건 + 전체 pytest(회귀 0, F/E 0, 2 skip) + ruff All checks passed + node --check + py_compile. **follow-up(별 cycle, LOW)**: never-claimed pending job + sentinel KV 잔존(pending-job TTL reaper 부재 — 본 변경 이전부터의 class, 악화 아님; 20분 후 stale_error·max_wait 슬롯반납으로 완화). **PB-0008 후속 수정(main bb661bf)**: 검증 중 발견 — `cancelCurrentRun` 이 폴링을 멈춰 자동 재렌더 트리거가 사라지자 `clearPendingBubble`(state 만 null)이 DOM `#pendingAssistantBubble` 을 못 지워 "처리 중" 말풍선 잔류 → cancelCurrentRun 에 `renderMessages()` 추가로 즉시 제거(사용자 메시지 유지). 캐시버스터 `?v=20260612-cancel-immediate-2`. **배포·검증 완료**: main bb661bf, web+ask-worker 재빌드·재생성(healthy), 서빙 app.js 신규 마커 + app.py/agent_core/memory.py 가드 baking 확인. **PB-0008 Windows-browser 실측 PASS**: 다단계 run 전송 → busy(중단 모핑·입력잠김·pending 표시) → 중단 클릭 직후 동기 `disabled:true→false`·`mode:stop→send`·`hasPending:true→false`(말풍선 제거)·`focused:promptInput`, 재요청 즉시 수락(429 없음), orphan bail(8s) 후에도 상태 안정·허위 답변 없음. worktree `ai/claude/task0241-cancel-immediate`(base 9fbb185).

### Git 동기화 결과
- 커밋/PR/배포: main bb661bf 머지·push·배포(web+ask-worker)·PB-0008 검증 완료

## 1. Summary

**2026-06-12 TASK-0235 — 새 대화 첫 메시지 작업 단계 진행상황 실시간 표시** (REQ-20260612-0235, REV-20260612-0235 [SUBAGENT:newconv-progress-adversarial-concurrency] CONCERN→흡수, **Major §12.3**, 동시세션 insight-reset·prompt-autogen·ds-a11y·ds-label cycle 이 TASK-0231/0232/0233/0234 선점→§13.1 재번호 0232→0235). 사용자 보고: "새 대화 생성 후 assistant 에게 첫 요청을 보냈을 때 작업 단계 진행상황이 안 나타나고 '시작 중' 출력만 확인됨. 각 단계와 클릭 시 사이드바로 상세 확인 가능하게." **진단**: 진행 단계 한줄 표시(`renderPendingAssistantBubble`)·"N단계 보기"→사이드바(`openStepSidePanel`/`#stepSidePanel`/`_renderStepSidePanelBody`) UI 는 TASK-0061 에서 **이미 구현**됨. 진짜 결함은 **데이터 공급 비대칭** — 기존 대화는 send 직전 `startProgressPolling()` 시작(app.js:5476)하지만, 새 대화(lazy_create)는 `conversation_id` 가 `/api/ask`(블로킹 — worker enqueue 후 long-poll attach 또는 inproc `asyncio.to_thread`) 응답 전까지 없어 폴링을 못 켜고, ask 완료(run 종료 시점) 후에야 폴링 시작 → 처리 내내 step 0 → pending bubble 이 "시작 중…" 고착. **수정(frontend-only, app.js+index.html)**: lazy_create 시 staged 첨부 있을 때만 `/api/new_conversation` 으로 cid 를 선발급하던 분기(TASK-0106)를 **첨부 유무 무관 일반화**. cid 확정 직후 ① `state.activeConversationId` 전환 + optimistic conversation entry 선등재 ② `startProgressPolling({reset:true})` 즉시 시작 → 새 대화 첫 메시지에서도 step 실시간 누적 → pending bubble 단계 표시 + "N단계 보기" 버튼/사이드바 활성화. 후처리 블록(5587-5614)은 `pendingSentinel===busyKey` 가드가 early 전환으로 false 가 되어 중복 폴링 없음(non-lazy lifecycle 로 수렴). **적대적 동시성 리뷰 CONCERN 2 흡수**(REV-20260612-0235): #3 — early-cid 발급 후 ask 실패 시 빈 대화 고아화 회귀 → `earlyCidActivated` 플래그 도입(활성 전환 시 catch 가 lazy 에러 경로 대신 **non-lazy 복구 경로**(fetchAskStatus→is_processing 시 대기/취소/즉시답변)로 분기 → 빈 대화는 실 run 컨테이너가 되고 worker 모드 살아있는 run 도 회수). #2 — 빈 대화에 명시 cid `/api/ask` 가 user message 저장+run 시작? → `run_agent` 내부 `save_memory_message` 책임(agent_core:1379/2273), 기존 staged-attachment 흐름이 동일 패턴 사용 중인 검증된 경로로 확인. race 안전: 첫 poll 이 processing 선기록(worker app.py:8346 / inproc agent_core:2472) 전 도달해 status="" 받아도 폴링 중단 조건(`status && !=="processing"`) 아님 → 다음 tick 포착. **비변경**: 백엔드 app.py·PG/웹 스키마·RBAC·엔드포인트·시크릿 0(병렬 insight-reset worktree 가 app.py 점유 중 — 의도적 회피). 캐시버스터 `app.js?v=20260611-newconv-progress-steps`. **검증**: node --check app.js PASS. **잔여**: verify-completion → 머지 → web 재배포 → PB-0008 Windows-browser 시각검증(새 대화 첫 요청 → 단계 실시간 표시 + 사이드바 열림). worktree `ai/claude/newconv-progress-steps`(base c77111d).

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0231 — insight 분석 초기화 (관리 콘솔 > 제품 > 접근 가능 데이터베이스 단위)** (REQ-20260611-0228, REV-20260611-0231 [SUBAGENT:security] BLOCK(MAJOR 3)→흡수, **Critical §12.3**, 동시세션 SSRF·UI-통합·멀티datasource cycle 이 TASK-0228/0229/0230 선점→§13.1 재번호 0228→0231). 사용자 요청: insight 분석 완료율 화면에서 분석 내용을 초기화하는 수단 — "분석한 내용 자체가 잘못되었을 경우 대응 방법이 없다"는 gap. 사용자 결정(AskUserQuestion): **개별 DB 단위** + **삭제만**(worker 자동 재분석). **구현**: ① 신규 RBAC `insight.reset`(console 그룹, admin 한정 — audit.purge 동급 파괴적; PERMISSION_DEFINITIONS + admin seed catchup, operator/sales/pending 미부여). ② 공용 헬퍼 `_resolve_product_insight_scope` — 완료율 계산 `_compute_product_insight_coverage` 와 reset 이 **동일 scope/allow_null/engine** 식별자 사용 + scope alias 집합(hash/.env label/NULL) 반환. ③ `POST /api/admin/products/{pid}/insight-reset`(body `{db, dry_run}`) — 라이브 카탈로그 조회로 해당 DB 의 `(schema, table)` 쌍 확보 후 **rag_objects 를 완료율 분자와 동일한 (schema_name, table_name) 교집합 + schema 노드로 삭제**(M1: object_key LIKE 가 MSSQL 2-tier 레거시 catalog-less 키를 놓쳐 완료율 divergence 유발하던 것을 해소 — 2-tier/3-tier 무관 완료율 0 보장). fact_entries/rag_documents/kv 는 키 패턴(scope alias 전체 + 라이브 schema 기반, LIKE ESCAPE '\\') 삭제. **fingerprint(schema_fp/table_fp)+refresh_at 동반 삭제가 핵심** — 안 지우면 worker 가 fingerprint_changed 미발생으로 재분석 skip. `dry_run=true`=건수만, `false`=**audit start-event 먼저 commit(실패 시 삭제 중단, M3 fail-safe)** → 단일 PG tx 4종 DELETE + rollback 안전망 → complete-event + 완료율 캐시 clear. 보안 게이트: 권한 403 + 제품 WebProductDatabases 바인딩 DB 만 허용(임의 주입 400) + db 누락 400 + 카탈로그 조회 실패 502. ④ 프런트(admin.js/html/css, TASK-0229 통합 DB 리스트 위로 rebase): per-DB 행 "초기화" 버튼(권한자만) → `resetProductDbInsight`(dry-run 미리보기 → DB명 typed-confirm + "공유 제품 완료율도 함께 0" 경고 → 실삭제 → 완료율 새로고침), 위험색 버튼 CSS + grid 6컬럼, 캐시버스터 `?v=20260611-db-coverage-insight-reset`. **outside-voice 적대적 보안 리뷰 MAJOR 3 흡수**(REV-20260611-0230): M1(MSSQL rag_objects 2-tier 레거시 누락 → 완료율 divergence, 라이브 168행 재현) → (schema,table) 교집합 통일, M2(scope alias 미삭제 → fingerprint 잔존) → alias 집합 전체 삭제, M3(audit 후행 best-effort) → start-event 선행 commit fail-safe. SQL인젝션/권한/IDOR/트랜잭션은 리뷰 PASS. **검증**: 신규 `test_insight_reset.py` 14건 PASS + make test **505 passed/2 skipped(회귀 0)** + ruff All checks passed + py_compile + node --check. 라이브 PG 실측으로 키 패턴 매칭·MSSQL 2-tier/3-tier 분포 검증. worktree `ai/claude/insight-reset`(origin/main 77f2ef6 위로 rebase). **잔여**: verify-completion → 머지 → web 재배포 → 라이브 dry-run/실삭제 검증 + PB-0008 시각검증.

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0229 — 관리 콘솔 제품 상세 "접근 가능 데이터베이스" UI 통합 (gstack 디자인 리뷰)** (REQ-20260611-0229, REV-20260611-0229 [SKIPPED:frontend-ia-merge-no-backend], **Minor §12.3**, 동시세션 SSRF cycle TASK-0228 선점→§13.1 재번호). 사용자 보고 2건: (1) 제품 상세의 `접근 가능 데이터베이스` 섹션에서 위쪽 "insight 분석 완료율" per-DB breakdown 리스트와 아래쪽 사용자 등록 DB chip 목록이 **같은 DB 집합을 두 번 표시**(1:1 매칭)해 분리 의미가 없다 → 하나로 통합. (2) 시스템/메타데이터 DB(MySQL 4종/MSSQL 3종)가 각각 별도 locked chip 으로 나열돼 산만 → 단일 묶음 칩 + hover 상세. **gstack `/design-review` 메서드론**(general-purpose design subagent)으로 통합 IA 도출: "분석 대상(사용자 DB)=한 행에 진척+제거를 담은 단일 리스트, 비-분석 대상(시스템 DB)=접근성 갖춘 단일 묶음 칩". **데이터 정합 검증**: 백엔드 `_compute_product_insight_coverage` 의 `accessible = _list_product_databases(conn, pid)` → `per_db` 의 DB 집합이 사용자 등록 DB(draft chip)와 **정확히 동일**, 시스템 DB 는 `availableDatabases.metadata_schemas` 별도 출처라 per_db 에 미포함 → 조인 키 `per_db.db ↔ draft.schema_name`(소문자) 자연 정합. **수정(admin.js + styles.css + admin.html, 3파일)**: ① `buildProductCoverageDetail` 을 "요약 헤더(제목+전체% 배지+새로고침)+전체 진행 바"로 축소(per-DB breakdown 리스트 제거 — 각 행으로 흡수). ② `buildDbCoverageCells(covRow, measuring)` 신설 — 통합 리스트 한 행의 진척 셀(마이크로바+통계 m/n+상태칩 DB✓/연결불가/측정대기). ③ `buildSystemDbChip(lockedChips)` 신설 — 시스템 DB 단일 묶음 칩(`시스템 DB N개 · 고정`) + `title`/`aria-label`/`tabindex=0` + hover **및** focus/focus-within 커스텀 툴팁(키보드·터치 접근성 병행). ④ `redrawChips` 재작성 — 시스템 묶음 칩(상단) + 사용자 DB 통합 리스트(`cov-db-row` grid 5컬럼: 이름·마이크로바·통계·상태칩·제거 ×). 빈 상태 메시지. ⑤ 컨테이너 `admin-chip-wrap`→`cov-db-wrap`(flex column). **CSS**: `.cov-db-wrap`/`.cov-db-row`(grid)/`.cov-microbar(-fill)`/`.cov-db-status*`/`.cov-db-remove`/`.sysdb-chip(-tip*)` 신설·재구성, 기존 디자인 토큰만 사용(신규 hex 0), 8px 그리드·11~13px 위계 유지. 캐시버스터 `?v=20260611-db-coverage-unified`. **권한/스키마/암호화/엔드포인트/백엔드(app.py)/coverage 데이터 모양 0** — frontend-only IA 재구성. **검증**: node --check admin.js PASS + CSS brace balance(1031/1031) + verify-completion. **잔여**: web 재배포 + PB-0008 Windows-browser 시각검증. worktree `ai/claude/product-db-coverage-merge`(base e93b181).

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0228 — datasource SSRF 사설망 경계 env 토글 + 의도적 비활성화** (REQ-20260611-0228, REV-20260611-0228 [SUBAGENT:security] BLOCK→흡수→PASS, **Major §12.3 — 보안 다운그레이드, 사용자 명시 승인**). 사용자 보고: `관리 콘솔 > 데이터소스` 에서 새 데이터소스(host=`10.200.50.80`) 생성 시 "호스트 차단(SSRF): 사설/링크로컬 IP 차단(allowlist 필요): 10.200.50.80" 에러. **근본 원인**: `_ssrf_check_host`(app.py)가 RFC1918 사설 IP 를 SSRF 방어로 차단하는 설계(TASK-0205/0214). `10.200.50.80`=`10.0.0.0/8` 사설 대역 → 차단. 정당한 사내 host 는 `AGENT_DATASOURCE_HOST_ALLOWLIST` 등재 필요. **코드 버그 아님** — 사내 운영(대부분 사설망 IP)과 SSRF 방어 기본값의 불일치. **사용자 결정**: SSRF 방어 구성을 복원 가능한 형태로 보존(태그)하고 현재는 사설 경계 의도적 비활성화. **구현**: ① `_ssrf_private_guard_enabled()` 신규 — env `AGENT_DATASOURCE_SSRF_GUARD_ENABLED`(기본 `1`=활성 secure-by-default; `0`/`false`/`no`/`off`=비활성). ② `_ssrf_check_host()` 토글 분기 — 비활성 시 **RFC1918(`is_private`)만 완화**. ③ `GET /api/admin/datasources` 에 `ssrf_private_guard_enabled` + admin.js 안내 분기(`?v=20260611-ssrf-private-guard-toggle`). ④ ADR-0030 + SECURITY §11 + .env.secret.example(복원 절차/태그) + 자동 메모리. **불변식(토글 무관 항상 유지)**: 클라우드 메타데이터 IP(IPv4-mapped IPv6 형 `::ffff:...` 포함)·loopback(127.x/::1)·link-local(169.254.x/fe80::)·reserved·multicast 차단 + DNS rebinding pin + fail-closed 에러 경로. **outside-voice 적대적 보안 리뷰 BLOCK→흡수**(REV-20260611-0228): (A/B) 토글 OFF 시 IPv4-mapped 메타데이터 IP 가 `str(ip).endswith` 정규화 빗나감으로 통과 → `ip.ipv4_mapped` 언래핑 비교로 수정. (C) 토글이 loopback/link-local 까지 개방 → `is_private` 한정 + loopback/link-local 상시 차단으로 수정. **검증**: py_compile + node --check PASS, 신규 31 PASS + datasource 회귀 0, 통합 trace 11 케이스 ALL PASS. **잔여**: 운영 `.env.secret` 토글=0 설정 + web 재배포 + PB-0008 Windows-browser(host=10.200.50.80 데이터소스 생성 성공) 시각검증. worktree `ai/claude/ssrf-host-guard-toggle`(base e93b181).

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0227 — 실행 단계 사이드 패널 갱신 시 "결과 보기" 펼침 상태 유지** (REQ-20260611-0227, REV-20260611-0227 [SKIPPED:frontend-ui-state-persist-no-backend], **Minor §12.3**). 사용자 보고: assistant 답변의 `실행 단계`를 사이드바에 펼쳐놓고 한 단계의 `결과 보기`로 결과셋을 확인 중일 때, 실행 단계가 폴링으로 갱신되면 보던 결과셋이 닫혀버린다. **근본 원인**: 폴링으로 새 단계가 도착하면 `applyProgressPayload`(app.js)가 `refreshStepSidePanel`→`_renderStepSidePanelBody`를 호출하고, 이 함수가 `body.innerHTML=""`로 패널 DOM 전체를 비운 뒤 모든 단계를 재생성한다. 그런데 각 단계의 "결과 보기" 펼침 여부는 순전히 DOM 로컬 변수(`resultBody.hidden`, `buildStepDetailEl` 내부)로만 존재 → 재렌더 시 전부 기본값(닫힘)으로 리셋. 스크롤 위치는 이미 `wasAtBottom` 스냅샷/복원하면서 펼침 상태는 미보존하던 비대칭. **수정(app.js + index.html, 2파일)**: ① `state.stepResultExpanded`(Set) 신설 — 펼친 단계의 안정 키 영속화. ② `_stepResultKey(step, idx)` 헬퍼 — `progressSteps` dedup과 동일한 `step_index:created_at` 키(둘 다 없으면 `idx:` fallback)로 같은 단계가 재렌더를 거쳐도 동일 키 유지. ③ `buildStepDetailEl(non-compact)` 결과 토글이 초기 `hidden`/버튼 라벨("결과 보기/닫기")/`aria-expanded`를 Set에서 복원, 토글 클릭 시 add/delete. ④ run 전환 시(`resetProgressTracking` + `applyProgressPayload`의 runId 변경 분기) `state.stepResultExpanded.clear()`로 다른 run의 동일 step 키 혼동 방지. **권한/스키마/암호화/엔드포인트/백엔드(app.py) 0** — frontend-only. `buildSqlStepPanel`(완료 메시지 SQL 결과)은 run 완료 후 폴링 정지로 재렌더되지 않아 본 버그 무관(범위 밖). 캐시버스터 `?v=20260611-step-result-persist`. **검증**: node --check app.js PASS + verify-completion **PASS(9/9 checks)**. **잔여**: web 재배포 + PB-0008 Windows-browser 시각검증. worktree `ai/claude/step-panel-result-persist`(base de52f08).

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0223 — 제품별 insight-worker 분석 완료율 UI (관리 콘솔 > 제품)** (REQ-20260611-0223, REV-20260611-0223 [SUBAGENT:insight-coverage-matching-semantics], **Major §12.3**). 사용자 요청: `관리 콘솔 > 제품` 각 항목에 insight-worker 의 객체 분석 완료율(%)을 표시 — 비율 모수 = 제품 `접근 가능 데이터베이스`(WebProductDatabases) 의 객체, 분자 = PG 내 해당 DB/테이블 통찰값(rag_objects). **구현**: (db.py) `list_information_schema_tables` — datasource information_schema `(schema,table)` flag-무관 직결 열거(`connect()` flag-gated 경로 우회). (app.py) `_compute_product_insight_coverage` + `GET /api/admin/products/insight-coverage`(`console.access`, 90s TTL 캐시). **catalog-driven 매칭** — 라이브 카탈로그 (schema,table) ∩ rag_objects (conv=`__global__`, scope=`common`, object_type∈{schema,table}) **set 교집합 dedup**: MSSQL `schema_name=dbo` 차원·NULL/hash 이중기록을 모두 해소. datasource scope=엔드포인트 해시(`_dsr.scope_key`, .env 라벨 폴백)+기본 엔드포인트면 `datasource_key IS NULL` 폴백. 분모는 resolve된 datasource RO 좌표 직결(SSRF 가드+pinned IP, 5s timeout, per-datasource 실패 격리→measurable:false). MSSQL 비-default_db=미스캔 flag. (admin.js/styles.css) 제품 목록 배지(`분석 N%` 등급색) + 상세 `접근 가능 데이터베이스` 섹션 per-DB breakdown(테이블 analyzed/total·DB✓/✗·미스캔) + 새로고침. 캐시버스터 `?v=20260611-insight-coverage`. **권한/스키마/암호화/insight write 경로 변경 0**(read-only 통계). **검증**: outside-voice 적대적 설계리뷰 [SUBAGENT] NOT-SHIP 5건이 catalog-driven 구현으로 전부 해소 확인. make test pytest **444 passed/2 skipped** + ruff All checks passed(머지 후 `_log` F821·conversation_id 버그 2건 hotfix 포함) + node --check + py_compile. **라이브 실측**: product 1/7/8(MySQL)=100%(dbauth 9/9·dbgame 98/98·dblog 279/279 등), product 91(MSSQL `mssql_local` agent_ro 로그인실패)=graceful 측정불가. **PB-0008 Windows-browser 시각검증 PASS**(목록 3× 녹색 `분석 100%`+1× `분석 측정 불가`, 상세 `insight 분석 완료율 100%` `389/389 객체` per-DB breakdown). worktree `ai/claude/task0223-product-insight-coverage`(base c769612).

### Git 동기화 결과
- 커밋: 15f1fa7 (ai/claude/task0223-product-insight-coverage) → PR #161 머지 (main b46cbd4) + hotfix cde2610(_log→logging) + 0e37b8e(conversation_id `__global__`)
- verify-completion: PASS (9 of 9 checks, CHECK#13 Windows-browser WARN→PB-0008 충족)
- Push: 완료
- main 병합: 완료 (PR #161 merge + hotfix 직접 push)
- 배포: make dc-build SERVICE=web + up -d (healthz git_commit=0e37b8e 베이킹 확인)
- 충돌 해결: 없음

## 1. Summary

**2026-06-11 TASK-0218 — 관리 콘솔 대시보드 CloudWatch 스타일 사람-친화 재구성** (REQ-20260611-0218, REV-20260611-0218 [CODEX+SUBAGENT:cloudwatch-dashboard-design], **Major §12.3**). TASK-0210 위젯 그리드를 AWS CloudWatch 류 운영 대시보드로. gstack `/design-review` 메서드론 + cross-model(Codex+subagent) 디자인 감사 강한 합의 반영: (위계) 9개 동일 비중 → 주 metric 크게(primary)+보조 작게, 카탈로그 활동-우선. (신선도) `days` 윈도우 audits/conversations/accounts 전파(거짓 컨트롤 정직화)+수동 새로고침+auto-refresh(off/30/60s)+마지막 갱신 시각. (추세) 전기간 대비 ▲▼% 델타 배지(의미별 색)+순수 SVG sparkline(lib 0). (fail-loud) overview/위젯 실패 배너+재시도. (drill-down) 위젯→관리 탭. (편집) native HTML5 drag+↑↓ 폴백. (접근성) 포커스 링·aria-live·aria-label·aria-pressed. (polish) Top-N 비율막대·radius --r-md·8px. 백엔드 `_dash_widget_*` window/primary/delta/spark/tab + helper 2. **권한/스키마/시크릿/신규 엔드포인트 0**(응답 shape 확장 + 비파괴 read). make test MAKE_EXIT=0(`test_dashboard_overview.py` 17, 회귀 0)+node/py_compile+내 코드 ruff 클린. 캐시버스터 `?v=20260611-dashboard-cloudwatch`. worktree `ai/claude/dashboard-cloudwatch-ux`(base 1c98a16). flag(내 코드 아님): app.py:14133 `_log` F821(TASK-0216 머지본 잠복).

## 1. Summary

**2026-06-11 TASK-0210 — 관리 콘솔 대시보드 보강(카테고리별 위젯 그리드 + per-account 커스터마이즈/영속)** (REQ-20260611-0210, REV-20260611-0210, **Major §12.3**). 사용자 요청: 관리 콘솔 대시보드("운영 현황")가 빈약(계정 metric 6개 + 권한 drift + pending, 전부 클라 `adminState.accounts` 배열 필터 계산 — 계정 증가 시 비확장)하니 각 카테고리별 풍부 + "사용자별로 확장성 있게" 보충. AskUserQuestion 으로 **종합(RBAC 뷰어 스코프 + 계정별 분해 + 서버 집계) + 각 사용자별 커스텀 구성/수정 가능 + 영속성** 확정. **구현(4파일 + 신규 테스트)**: (백엔드 app.py) ① `_ensure_web_tables()` 에 `WebDashboardPreferences(AccountId PK, Content MEDIUMTEXT JSON-text)` 멱등 추가(MySQL 웹테이블군 정합). ② `GET /api/admin/overview` — 위젯 카탈로그(`_DASHBOARD_WIDGETS`) 각 항목이 표시 권한을 가지며 actor 보유 권한 위젯만 데이터 생성·반환(**권한 경계=데이터 노출 경계**). 위젯 7종(accounts/roles/products/datasources/conversations[PG]/audits[`audit.read.any`]/usage[`console.usage.read`, PG])은 각각 독립 try/except 격리. `days` 는 `max(1,min(365,int()))` clamp 후 PG interval 삽입(인젝션 차단). ③ `GET/PUT /api/admin/dashboard/preferences` — actor.id 한정 self-service(신규 RBAC 권한 0, `console.access` 게이트), PUT 은 `_sanitize_dashboard_prefs`(알려진 키·bool·int 만, 미지/중복/과대 거부). (프런트) admin.js `renderDashboard` 재작성 → 서버 overview+prefs fetch 후 위젯 그리드 + 편집 모드(표시 토글·↑↓ 순서, 외부 라이브러리 없음) + 저장/기본값복원; grant_health·pending 은 client 위젯으로 흡수. admin.html 위젯 그리드·집계기간 select·편집 toolbar; styles.css `.dashboard-widget*`(기존 토큰 재사용). 캐시버스터 `?v=20260611-dashboard-widgets`. **권한 카탈로그/시크릿/웹 외 스키마 변경 0**. **검증**: make test MAKE_EXIT=0 전체 PASS(신규 `test_dashboard_overview.py` 11 PASS — overview RBAC 스코프 operator(usage/audits 부재)·admin(전부 존재)·403·sanitize·기본값·영속 round-trip, 회귀 0) + node --check + py_compile + ruff 통과. outside-voice 적대적 보안리뷰(위젯 권한 경계/IDOR/인젝션). worktree `ai/claude/admin-dashboard-enrich`(base f2054b5).

## 1. Summary

**2026-06-10 TASK-0197 — assistant 말풍선 타임스탬프 옆 소요시간 표시** (REQ-20260610-0197, REV-20260610-0197 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret], **Minor §12.3**). assistant 응답 완료 시 각 대화 bubble 의 타임스탬프 옆에 소요시간 표시. `message.meta.duration_ms`(agent_core mirror_meta 기존 저장 필드) > 0 인 assistant 메시지에 한해 `renderMessages()` 에서 기존 `formatElapsed()` 재사용 + `.message-meta-duration` span 추가. user 메시지·duration 없는 메시지는 기존 textContent 유지. styles.css `.message-meta-duration { font-size:10px; opacity:0.7 }`. 캐시버스터 bump. 백엔드/RBAC/스키마/시크릿 무변경. node --check PASS. worktree `ai/claude/response-duration-display`.

### Git 동기화 결과
- 커밋: 143f039 (ai/claude/response-duration-display)
- verify-completion: PASS (9 of 9 checks)
- Push: 완료 (origin ai/claude/response-duration-display)
- main 병합: 해당없음 (PR 생성 대기 — §16.3 Step 6)
- 충돌 해결: 없음

## 1. Summary

**2026-06-10 TASK-0188 — 공유 대화 페이지 markdown 미적용 수정 + 수신자 가독성 디자인** (REQ-20260610-0188, REV-20260610-0188 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret], **Minor §12.3** — frontend-static-only). 사용자 보고: 공유 링크(`/share/{token}`) 로 전달받은 대화가 markdown 미적용 raw 텍스트(`**`, `|`, `#`, 코드펜스 그대로)로 보임. **근본 원인**: `share.html` 이 메인 UI 의 markdown 파이프라인 라이브러리(`vendor/marked.umd.js` + `vendor/purify.min.js`)를 미로드 + `share.js renderMessage` 가 `content.textContent = msg.content` 로 평문 렌더 — 메인 채팅은 `markdownToHtml()`(marked.parse → DOMPurify.sanitize)로 렌더하는데 공유뷰만 누락. **수정(3파일, 백엔드·API·스키마 무변경)**: ① `share.html` — marked+purify 로드(share.js 앞 순서) + css/js 캐시버스터 `?v=20260610-share-md` + 헤더 브랜드 라벨 + "링크 복사" 버튼. ② `share.js` — `renderMarkdownContent()` 신규(메인과 동일 marked+DOMPurify, 라이브러리 부재 시 평문 폴백) + sql 코드블록 "쿼리 보기" 토글 이식(`collapseSqlCodeBlocks`) + 외부 링크 `target=_blank rel=noopener`(`markExternalLinks`) + 역할 배지(사용자/어시스턴트) + 링크복사 핸들러(clipboard API + execCommand 폴백). ③ `share.css` — 렌더된 markdown 요소 전반 스타일(제목 h1~h4·리스트·인용·인라인/블록 코드·**GFM 표**(DB 질의 응답 핵심)·hr·img·링크) + 역할 배지/메시지 좌측 accent border + 반응형(≤600px) + **인쇄/PDF 스타일시트**(수신자 보고서 보관 — actions/footer 숨김, SQL 토글 펼침, pre 줄바꿈). **보안**: 익명 페이지 XSS 표면은 메인 앱과 동일한 DOMPurify.sanitize 로 차단 — 데이터 노출/redaction(backend) 무변경. node --check share.js PASS. 검증: Windows-browser(PB-0008) 배포 후. 동시세션 다수(0182~0186 선점)→0188 재번호. worktree `ai/claude/share-md-render`.
## 1. Summary

**2026-06-10 TASK-0181 — 역할/계정 차트 모델별 stacked + 상세 표 요청(메시지) 수** (REQ-20260610-0181, REV-20260610-0181 [SKIPPED:read-agg], **Minor §12.3**). 역할별·계정별 [토큰|비용] 막대를 모델별 누적으로 분해(전역 modelColor 색 일관 + renderStackedHBar) + 작업 화면 요청 수(distinct run_id) 컬럼. 백엔드 by_account models[]·requests 집계 확장(RBAC/스키마 무변경). make test 282 passed/5 skipped.
## 1. Summary

**2026-06-10 TASK-0180 — 차트 카테고리별 행 레이아웃 + 일별 폭 채움 + 상세 표 여백** (REQ-20260610-0180, REV-20260610-0180 [SKIPPED:css-layout], **Minor §12.3**). 사용자 피드백(몰아넣기 불쾌·상세 표 여백). 명시적 행 구조(4:1 trend / 역할별 토큰·비용 / 계정별 토큰·비용) + 일별 차트 viewBox=clientWidth 로 넓은 카드 폭 채움 + 상세 표 카드화. 순수 레이아웃, 백엔드 무변경. node --check PASS.
## 1. Summary

**2026-06-10 TASK-0179 — LLM 사용량 차트 넓은 화면 가로 여백 해소 (CSS grid)** (REQ-20260610-0179, REV-20260610-0179 [SKIPPED:css-layout], **Minor §12.3**). 넓은 모니터에서 차트가 좌측만 차지하던 것을 `.admin-usage-charts` grid 다열 배치로 채움(일별 2칸, 나머지 1칸씩, 좁으면 wrap). 순수 레이아웃, 백엔드 무변경. node --check PASS.
## 1. Summary

**2026-06-10 TASK-0178 — LLM 사용량 화면 여백 컴팩트화** (REQ-20260610-0178, REV-20260610-0178 [SKIPPED:css-spacing], **Minor §12.3**). 사용자 보고(여백 과다). TASK-0177 디자인 정렬에서 카드·섹션·차트 패딩이 누적된 것을 축소 — `.admin-usage-card/section/metric` 패딩·margin 하향, 일별 차트 SVG 높이 252→196, HBar 막대 간격 축소. 순수 spacing(CSS/SVG), 백엔드/구조 무변경. node --check PASS.
## 1. Summary

**2026-06-10 TASK-0177 — LLM 사용량 상세 표 추정 비용 컬럼 + gstack 디자인 관점 정렬** (REQ-20260610-0177, REV-20260610-0177 [SKIPPED:frontend-design], **Minor §12.3**). (A) 역할별·계정별 상세 표에 추정 비용 컬럼(차트와 일치) + 숫자 우측정렬·tabular-nums. (B) general-purpose subagent 의 gstack design-review 관점 적대적 리뷰를 받아 usage pane 디자인 정렬: 요약 `.metric-card` 통일, 임의 hex→디자인 토큰, 차트 surface 카드 구획, 8px spacing/타이포 위계 클래스, 표·툴팁 클래스化. styles.css(admin-usage-* 신규)+admin.html+admin.js, 백엔드 무변경. node --check PASS. 캐시버스터 bump. Windows-browser(PB-0008) 검증 배포 후.

**2026-06-09 TASK-0176 — LLM 사용량 역할별·계정별 추정 비용 차트** (REQ-20260609-0176, REV-20260609-0176 [SKIPPED:frontend-viz], **Minor §12.3**). 사용자 요청(역할·계정별 추정 비용도 차트로). 백엔드 `admin_llm_usage` by_account 를 계정×모델 분해로 집계해 계정별 추정 비용(`cost_usd`) 산출 + `_aggregate_usage_by_role` 가 역할별 재합산. 프론트 `renderHBar` 에 valueFmt(usd) 추가 + 역할별/계정별 추정 비용 가로 막대 차트(의존성 0 SVG, hover usd, 비용 0 행 제외). 권한/엔드포인트/스키마 신규 0(기존 컬럼 + TASK-0166 단가 재사용). make test 269 passed/5 skipped. 비용은 claude 등 과금 모델 추정만(로컬=$0). 동시세션 0168~0175 선점→0176 재번호.

**2026-06-09 TASK-0169 — out-of-process ask-worker 실행모델 + 라이브 cutover** (REQ-20260609-0168, REV-20260609-0169, **Critical §12.3**, PLAN-APPROVED). `/api/ask` 의 in-process `asyncio.to_thread(run_agent)` 실행을 전용 `ask-worker`(ask_jobs 큐 claim)로 분리 → web 재배포/SIGTERM 이 in-flight run 을 죽이는 orphan 구조 제거(TASK-0159/0160/0164 이월 B 종결, 두 backstop 격하). flag `AGENT_ASK_EXECUTION_MODE`(기본 inprocess) — 배포 자체는 무변경 shadow, cutover 는 env 전환·즉시 rollback. **web(app.py)**: `_dispatch_ask_run`(inprocess|worker) + readiness gate(503) + 단일문 slot enforce + 내부 attach loop + `result_json` shape 패리티 + backstop ownership-aware(B1) + cancel-pending(2g) + 첨부 temp `/shared`(M6). **agent-core(feature-0002)**: ask_jobs 마이그레이션 0003 + `ask_jobs.py`(atomic claim B2/slot M5/lease fencing B3/sweep) + `ask.py`(worker loop·시간기반 heartbeat·reaper) + `--ask-worker`·healthcheck + `set_run_status` 순서 M4 + `_clear_cancel_request` run_id-scoped MJ-2. docker-compose `ask-worker` 서비스(stop_grace 70s). **거버넌스**: outside-voice 적대적 리뷰 2회(설계 전 "구현 불가" 판정 → BLOCKER 3+MAJOR 4 흡수; 구현 diff → BL-1/MJ-1/MJ-2 추가 수정). make test 회귀 0 + ruff + verify-completion PASS(양 feature). **라이브 cutover 전수 검증**(main 584b8dd): 마이그레이션 0003 적용(live=0003, agent_kb_rw 권한 OK) → web+ask-worker 배포(healthz git_commit 일치) → flag=worker. 실측 — ① ask enqueue→worker claim(atomic,lease=1)→run→동기 응답 shape 패리티, exactly-once(attempts=1); ② **web force-recreate 중 in-flight run 생존**(동일 run_id·done·backstop 미오염, AC-0327); ③ 부하 9동시→6×200+3×429(M5); ④ **PB-0008 Windows-browser** browser→worker→browser 왕복 PASS. **hotfix**: `_ask_worker_ready` naive/aware datetime tz 버그(readiness 영구 503) 라이브 포착·수정. **이월**: worker SIGTERM 장기 run 즉시중단(현 sweeper backstop)·on_event→lifespan. git: main FF 584b8dd(동시세션 0166/0167/0168 선점 → 0169 재번호, base rebase ×2), worktree `ai/claude/ask-worker` 정리.

**2026-06-09 TASK-0167 — 관리 콘솔 작은 화면 세로 잘림 수정 (CSS)** (REQ-20260609-0167, REV-20260609-0167 [SKIPPED:css-only], **Minor §12.3**). 사용자 보고(작은 브라우저 화면에서 화면이 잘림). admin-shell/admin-workspace 가 100vh+overflow:hidden 인데 usage pane 만 자체 overflow-y 누락 → 차트·표로 길어진 usage pane 이 작은 화면에서 세로 스크롤 불가로 하단 잘림. styles.css 의 usage pane 에 overflow-y:auto 추가(dashboard 패턴). CSS 셀렉터 1개 + 캐시버스터. 권한/엔드포인트/스키마/JS/HTML 구조 무변경.

**2026-06-09 TASK-0166 — LLM 사용량 차트 고도화** (REQ-20260609-0166, REV-20260609-0166 [SKIPPED:frontend-viz], **Minor §12.3**). TASK-0165 후속(사용자 지적 누락): 계정별 차트·hover 상세·막대 정확한 값·시간 단위 선택·추가 지표. 백엔드 `admin_llm_usage` 에 granularity(시/일/주/월, date_trunc 화이트리스트) + prompt/completion 분해 + 추정 비용(`_estimate_llm_cost_usd`, claude 근사·로컬 0) 추가. 프론트(의존성 0 SVG): 계정별 가로 막대 차트, 커스텀 hover 툴팁(전 차트, 값/비중/호출/비용), 막대 위 총합 값 라벨, 집계단위 드롭다운, 요약 비용 카드 + 모델별 표 prompt/completion·비용 컬럼. 권한/엔드포인트/스키마/시크릿 신규 0. node --check/py_compile + make test 218 passed/5 skipped(회귀 0). 비용은 추정(로컬=$0). Windows-browser(PB-0008) 검증 배포 후.

**2026-06-09 TASK-0164 — LLM 사용량 화면 차트화 (상용 AI 대시보드 구조 참조)** (REQ-20260609-0164, REV-20260609-0164 [SKIPPED:frontend-viz], **Minor §12.3**). TASK-0163 후속(사용자 요청 "상용 ai 제공 서비스 구조 참조 차트 형식"). 표 위주 화면을 Anthropic Console / OpenAI Usage 류로 시각화 — ① 일별 토큰 모델별 누적(stacked) 세로 막대, ② 모델별 비중 도넛(% 범례), ③ 역할별 가로 막대. 백엔드는 `by_day_model`(일별 × resolved_model 토큰) 집계만 추가(기존 컬럼·비파괴 read, 스키마 0). 프론트는 **순수 SVG·의존성 0**(CDN 회피 — 정적자산 baked·WSL 내부). 기존 표는 `<details>` 접이식 보존. 권한 `console.usage.read`(admin)/엔드포인트/스키마/시크릿 신규 0. node --check/py_compile PASS. Windows-browser(PB-0008) screenshot 검증 배포 후 수행.

**2026-06-09 TASK-0163 (cross-feature, 주관 feature-0002) — LLM 사용량 admin 계정별/역할별 집계 + 모델 해소 표시** (REQ-20260609-0163, REV-20260609-0163, **Major §12.3**). 본 feature 면(엔드포인트+프론트): `admin_llm_usage`(GET /api/admin/usage) 가 by_model `COALESCE(resolved_model, model)` 집계(별칭+실제 모델 노출) + by_account 를 이미 열린 MySQL conn 으로 `WebAccounts⋈WebRoles` username·role enrich(추가 conn 0) + 신규 순수 헬퍼 `_aggregate_usage_by_role` Python 폴딩(account None→`(시스템)`, role None→`(역할 없음)`) + 응답 `by_role`. `admin.html` 역할별 표(#usageByRole) + `admin.js loadUsage` by_role 렌더·계정 username/역할·모델 `별칭 → 해소`·캐시버스터 bump. 권한 `console.usage.read`(admin) **무변경 — RBAC/엔드포인트 신규 0**. 토큰 계측 복구(메인 추론이 회계 chokepoint 우회하던 RC1)·`resolved_model` 마이그레이션·in-process 동시 ask race 수정은 feature-0002 주관. 검증: make test 215 passed/5 skipped + node --check + outside-voice 적대적 diff 리뷰 NEEDS-TWEAK→PASS(BLOCKER 1 흡수).

**2026-06-08 TASK-0157 완료 — 요청 중단(interrupt) 진입점 복구** (REQ-20260608-0157, REV-20260608-0157 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret], **Minor** §12.3 — frontend-only). 사용자 보고: 요청 후 "중단" 기능이 화면에 안 나타나고 진입 경로가 없음. **/investigate 근본 원인**: 취소 기능 자체(`/api/cancel` 엔드포인트 + 에이전트 루프 `_cancel_requested_for_run` 폴링 4지점 + RBAC `conversation.cancel.own/.any`)는 백엔드·루프 전부 정상. 그러나 진입 UI 인 중단(`#cancelBtn`)·즉시 답변(`#finalizeBtn`) 버튼이 커밋 `4ba71f5`(실행 단계 → `#stepSidePanel` 이전) 에서 **영구 숨김(`style="display:none"` 인라인 + "hidden permanently" 주석)된 `#progressCard` 안에 고아로 남음**. `renderProgress()` 의 `progressCardEl.classList.remove("hidden")` 가 인라인 style 우선순위에 가려 무효 → 부모가 영구 `display:none` → 자식 버튼은 `hidden` 토글과 무관하게 영원히 미렌더. 새 거처 `#stepSidePanel` 에는 닫기 버튼만 존재. 정상 동작 중 취소 진입점 0개(네트워크 끊김 복구 다이얼로그만 예외). **수정(사용자 선택: ChatGPT 패턴 — send→stop 모핑)**: (1) `renderComposer()` 가 `isCurrentConvBusy()` 동안 `#sendBtn` 에 `.is-stop`(위험색) + stop square 아이콘 + `aria-label="중단"` 적용, native `disabled` 를 풀어 클릭이 통과하게 함. (2) `#sendBtn` click 핸들러가 busy 면 `cancelCurrentRun()`, 아니면 `sendPrompt()` 분기. (3) hover 의 전송 모드 툴팁은 중단 모드에서 숨김. (4) 중단 권한 없으면 `is-access-blocked`+토스트(기존 `conversation.ask` 패턴 동형). 변경 2파일: `static/app.js`(아이콘 상수 + renderComposer morph + click 분기 + tooltip 가드) + `static/styles.css`(`.send-btn.is-stop`). **index.html 무변경** — 영구 숨김 strip 을 되살리지 않아 기존 TMI 정리 UX 와 충돌 없음. node --check PASS. backend/RBAC/DB schema/endpoint/secret 무변경. **이월(TODOS)**: 즉시 답변(finalize) 진입점은 동일 근본 원인으로 여전히 미노출 — 사용자가 단일-버튼 send-morph 를 선택하여 본 cycle 범위 밖. worktree `ai/claude/send-stop-button`(base d7826f5 — 작업 중 동시 머지된 #123 TASK-0156 inline-table-collapse 위로 rebase, 번호 충돌로 TASK-0156→0157 재부여).

---

**2026-05-28 TASK-0123 완료 — UX 2차 보완 7개 항목 구현** (CHG-20260528-0123, REV-20260528-0123 [SKIPPED:frontend-only], REQ-20260528-0123, **Minor** §12.3 — frontend-only, backend / RBAC / DB schema / endpoint contract 무변경). stop-hook 피드백으로 식별된 UX 미완료 항목 7개를 일괄 구현. **(1) 입력창 높이 일치** — `.composer-box` padding `9px→7px` 축소 (프로필 버튼 48px = padding 8×2 + icon 32px; composer 48px = padding 7×2 + textarea 34px, 정렬 맞춤). **(2) 파일 즉시 업로드 + ingest 병렬** — `_uploadComposerAttachment()` lazy 분기 완전 재작성: 파일 선택 시점에 즉시 `/api/new_conversation` 으로 cid 발급 + 업로드 + `state.composerAttachments.lazyConvCreating` 경쟁 방지 플래그. 대화 목록에 "(파일 첨부 중)" 임시 항목 삽입 + 렌더 갱신. **(3) 말풍선 첨부파일 표시** — 업로드 응답의 `signed_url` 을 bucket item 에 저장 + `_sendAttachmentSnapshot` 에 포함 + `refreshWorkspace()` 후 `lastUserMsg._attachments = snapshot` 재주입 (loadHistory 가 attachments 를 덮어쓰는 문제 해결). **(4) 첨부파일 다운로드** — chip 에 `has-download` class + click 핸들러 (presigned GET). styles.css 에 `.attach-chip-dl` + hover 효과. **(5) 공유뷰 CSV 다운로드** — `share.js` 에 `downloadRowsAsCsv()` helper (BOM UTF-8, RFC4180 escape) + SQL 결과표 하단 "CSV 다운로드" 버튼. `share.css` 에 `.share-csv-download-btn`. (공유뷰 file attachment 는 backend 가 permission-gated 로 숨김 → SQL 결과 CSV 로 대체). **(6) LLM step/thinking 표시** — `renderProgress()` 에 `progressCardEl.open = true` + `renderPendingAssistantBubble()` 의 step details `detailsEl.open = true` (step 도착 시 자동 펼침). **(7) 첫 대화 상태 dot 갱신** — lazy-create 성공 path 에서 `startProgressPolling` 직전 `state.conversations` 에 신규 conv 최소 항목 추가 + `renderConversationList()` 호출 → polling 첫 tick 에서 dot 갱신 가능. node --check PASS. worktree `ux-compact-redesign` (branch `ai/root/ux-compact-redesign`), commit `095f9b1`. docker cp 배포 완료 (repo-web-1:/app/web/static/).

---

**2026-05-26 TASK-0108 완료 — Sprint 3 (B: DDL/KB 보강) admin-only manual KB ingest** (CHG-20260526-0108, REV-20260526-0002, REQ-20260526-0108, **Major** §12.3 — RBAC 신규 코드 + admin endpoint + manual KB fact ingest path). BRIEFING-attachment-multi-cycle.md §6.3 Sprint 3 Cycle 3 implementation. admin 콘솔 "스키마 정의서 KB 등록" pane 에서 text/markdown/.sql 첨부 본문을 `AgentMemoryFactEntries` 의 manual fact (SourceType='manual' 고정, Weight=90 고정, ConversationId='__kb_manual__' reserved sentinel, FactKey=ScopeKey) 로 등록. 동일 ScopeKey 재ingest 시 기존 active row 는 Weight=0 으로 logical supersede (Status 컬럼 추가 회피, `AgentMemoryFacts` VIEW 의 Weight DESC tie-break 가 자연 hide → 회귀 0). **핵심 산출** 7건: (a) `app.py` PERMISSION_DEFINITIONS 에 `attachment.kb.write.any` 1 코드 + SEED admin/dba role catchup + 신규 endpoint `GET /api/admin/attachments` (list) + `POST /api/admin/attachments/kb-ingest` (ingest), (b) `unit/feature-0002-agent-core/src/modules/kb_ingest.py` 신규 (~205 LOC, ingest_manual + 4-step SELECT FOR UPDATE + ON DUPLICATE KEY UPDATE Id=LAST_INSERT_ID(Id)), (c) `admin.html` sidebar 의 "KB 등록" tab + workspace 의 `<section data-admin-pane="kb-ingest">` (list-detail layout), (d) `admin.js` `adminState.kbIngest` + `mountKbIngestPane` + load/render/submit handlers + client regex validation, (e) `tests/test_kb_ingest.py` 10 unit test (FakeConn — happy/supersede/reactivate/mixed/edge case, 10 PASS), (f) `tests/test_kb_ingest_rbac.py` 8 e2e RBAC 시나리오 (사용자 운영 turn 실행), (g) `AGENTS.md` §11.3 신설 — KB Fact 등록 정책 (Source/SourceType/Weight/ConversationId 4열 + supersede 정책). **outside-voice review (Codex `codex-cli 0.130.0`, `REV-20260526-0002`) Verdict BLOCK → PASS 전환 (Critical 5 + Nice-to-have 1 본 cycle 내 흡수)**: (B-1) 동시 ingest race → SELECT FOR UPDATE 명시 lock + reactivated 명시 계산 / (B-2) source_type/weight client spoofable → 서버 상수 고정 (request body 무시) / (B-3) admin endpoint = `console.access` AND `attachment.kb.write.any` / (B-4) audit fail-soft → transactional audit (실패 시 rollback) / (B-5) scope_key regex `^[A-Za-z0-9_.\-]{1,96}$` + audit hash prefix only. py_compile + node --check + 10 unit PASS. base = main HEAD (5448611 — KB Postgres bootstrap fix 흡수 후, dual-write 영역 자연 정합). **Runtime 검증 (사용자 운영 turn)**: docker compose build memory-init web + up -d --force-recreate web → admin 콘솔 → "KB 등록" tab → text/markdown 첨부 1건 ingest → AgentMemoryFactEntries 의 ConversationId='__kb_manual__' Weight=90 row + WebAuditEvents 의 attachment.kb.ingest row + ChangeJson 의 scope_key_hash_prefix 확인.

**2026-05-22 TASK-0107 완료 — 첨부 sandbox 활성화 + LLM context inject + drag&drop UX 확장** (CHG-20260522-0107, REV-20260522-0107, REQ-20260522-0107, **Major** §12.3 — LLM 동작 변경 + sandbox SQL 동선 + UI 진입점 확장). 사용자 직접 보고 2건 일괄 fix. **(1) 파일 첨부 후 LLM 이 "실제 내용을 직접 볼 수 없습니다" 응답** — TASK-0094 sandbox ingest 파이프라인 정의는 있었으나 caller 미ship → MetaJson 에 sandbox_table_name 미기록 → ATTACHED FILES 영역이 schema 명을 모름 → LLM SQL tool 이 SELECT 시도 안 함. **수정 (3-phase)**: Phase A — `app.py` upload endpoint audit dispatch 직후 `threading.Thread(daemon=True)` spawn (kind=csv|xlsx). 신규 helper `_ingest_attachment_background` 가 storage_minio bytes 받기 → `CREATE SCHEMA IF NOT EXISTS agent_attachment_<sha256(cid)[:32]>` (root user 단일-user MVP — 4-user 분리는 후속 cycle, .env 비밀번호 미설정) → `_open_memory_connection(database=schema)` → `sandbox_ingest.ingest_attachment` → MetaJson 에 sandbox_schema_name + sandbox_table_name (csv) 또는 sheets[] (xlsx) 기록 + UploadStatus='ingested'. 실패 → `_mark_ingest_failed` 가 'failed' + degraded_reason. `db.py` connect() 에 `agent_attachment_*` 패턴 → primary 라우팅 강제 (replica latency / 미배포 환경 안전). Phase B — `agent_core.py` `_build_attachment_context_section` 강화: information_schema.columns SELECT (column명 + data_type) + `SELECT * FROM <schema>.<table> LIMIT 5` sample rows (markdown 표, 80자 truncate, pipe escape, table cap 20) + 명시 INSTRUCTION ("first try to answer from the sample rows above. If more data is needed, call execute_sql … Do NOT ask the user to paste the file contents"). UploadStatus='uploaded' / 'failed' 분기 별 안내. **(2) drag&drop 영역 협소 + 새 대화 시 첨부 차단** — composer-wrap 만 drop zone + pendingSentinel 미발급 시점에 `_uploadComposerAttachment` 가 "대화 컨텍스트 미정" toast 로 차단. **수정**: index.html 에 chat-pane 자식 `#chatDropOverlay` (점선 카드 + 아이콘) 추가, styles.css 에 `.chat-drop-overlay` (absolute inset 0 + backdrop-filter blur + fade-in 120ms) + `.chat-pane { position: relative }`. app.js `_bindComposerAttachmentEvents` 에 chat-pane scope 핸들러 + `_isFileDrag()` types Files guard + dragCounter 중첩 추적 + window dragend/drop reset (drop miss 방어) + chat-pane 밖 drop 시 브라우저 기본 동작 preventDefault. `_uploadComposerAttachment` 진입 시 컨텍스트 미정 검출 → `conversation.create` 권한 검증 → `pendingNewConversation=true` + `_newPendingSentinel()` + 모든 render 호출 → 기존 lazy-create path 재사용. py_compile + node --check PASS. backend RBAC / DB schema / endpoint contract / D11 consent / D13 server-side bytes 무변경. worktree `ai/claude/0107-attachment-content`.

---

**2026-05-22 TASK-0106 완료 — 첨부 storage 모듈 import 경로 + lazy-create 첨부 staging** (CHG-20260522-0106, REV-20260522-0106 [SKIPPED:no-rbac-no-schema-no-secret-handling], REQ-20260522-0106, **Major** §12.3 — 외부 storage 통합 + 사용자 노출 첨부 동선 회복). 사용자 직접 보고 2건 일괄 fix. **(1) 첨부 업로드 시 `storage 모듈 import 실패` toast** — `app.py` 의 `from modules import storage_minio` (3 callsite: vision inline `_prepare_vision_inline_images` L6044, upload endpoint L7555, metadata endpoint L7771) + `from modules import sandbox_schema` (grant drift health L11862) 가 잘못된 namespace 검색. **근본 원인**: Dockerfile 이 feature-0002-agent-core 의 unified namespace (14 module cross-injection) 를 `/app/modules` 로 copy + feature-0003-agent-web-ui 의 module 은 `/app/web/modules` 로 별도 copy. `storage_minio.py` 와 `sandbox_schema.py` 는 후자에 위치. `from web.modules import …` 로 4 callsite 교체. `attachment_reconciliation.py` 의 `_delete_minio_object()` 는 docker container (`/app/web/modules`) + host dev (sibling sys.path) 양쪽 호환을 위해 `try: from web.modules import storage_minio / except ImportError: sys.path 삽입 fallback` 의 dual-mode 보강. **(2) "+ 새 대화" 클릭 후 첫 메시지 전 첨부 차단** — `_uploadComposerAttachment()` 의 `if (isLazy) showToast("첨부는 대화가 생성된 후 가능합니다...")` 즉시 차단. lazy-create (TASK-0048) 가 backend cid 발급을 첫 send 까지 지연시키므로 cid 필수의 `/api/conversations/{cid}/attachments` 호출 불가했던 부수 효과. **수정 (Option A — client-side staging)**: lazy 분기에서 즉시 차단 대신 pendingSentinel bucket 에 `{status: "staged", _localFile: File}` 보관 + "첨부가 추가되었습니다 (첫 메시지와 함께 업로드됩니다)" toast. `sendPrompt()` 의 lazy-create attachment_ids 빌드 후 staged ≥1 감지 시 `/api/new_conversation` 으로 cid 즉시 발급 → `_flushStagedAttachmentsToCid(earlyCid, pendingKey)` 신규 helper 가 staged 일괄 업로드 (성공 시 target bucket 으로 이동, 실패는 status="failed" pill) → askBody 를 `lazy_create=true` 에서 `conversation_id=earlyCid` 즉시-cid 모드로 전환 + `attachment_ids` union (기존 ready snapshot + 새 uploadedIds). staged 가 0 인 lazy-create 는 기존 단일 호출 유지 (TASK-0048 정신: "+ 새 대화" 시 빈 row 누적 방지). pill rendering 에 `data-staged="true"` 속성 + "(첫 메시지와 함께 업로드)" tooltip + `_toggleAttachmentPill()` 의 staged 토글 = remove (실수 클릭 자연스러움). py_compile + node --check PASS. backend / RBAC / DB schema / endpoint contract / 암호화 알고리즘 / D11 consent gate / D13 server-side bytes / D7 MIME / D8 size cap / D12 HMAC 모두 무변경. worktree `ai/claude/0106-attachment-fix`.

---

**2026-05-22 TASK-0105 완료 — Profile Drawer '내 감사 로그' 탭 제거 (일반 사용자 비노출)** (CHG-20260522-0008, REV-20260522-0008 [SKIPPED:frontend-only], REQ-20260522-0008, **Minor** §12.3). 사용자 직접 요청 — 일반 사용자에게 Profile Drawer 내 '내 감사 로그' 탭이 노출되어선 안 됨. TASK-0089 가 추가한 `profileAuditTab` 버튼 + `data-profile-pane="audit"` 패널 + 관련 JS 함수 9개 (`_profileAuditEscapeHtml` / `_profileAuditFormatDt` / `_profileAuditHasReadPermission` / `updateProfileAuditTabVisibility` / `_profileAuditReadFilters` / `_profileAuditClearFilters` / `loadProfileAuditList` / `renderProfileAuditList` / `renderProfileAuditDetail` / `attachProfileAuditHandlers`) + `state.profileAudit` 초기값 + `profile-audit-*` CSS 블록 전체를 index.html / app.js / styles.css 에서 제거. backend `/api/profile/audits` 및 `/api/profile/audits/{event_id}` endpoint 무변경 (admin 도구 또는 향후 정책 변경 대응 가능). admin 콘솔 '감사 로그' 탭 무변경. node --check + py_compile PASS. worktree `ai/claude/0105/remove-audit-tab`.

---

**2026-05-22 TASK-0104 완료 — 외부 노출 web 컨테이너 HTTPS 종단 활성화** (CHG-20260522-0007, REV-20260522-0007 [SKIPPED:non-policy-doc], REQ-20260522-0007, **Major** §12.3 — 외부 사용자 전원 영향 + 자격증명 처리 동선의 secure-channel 요건 충족). 외부 사용자가 `https://112.185.196.20:18080/` 로 접속할 수 없던 이슈 보고. **근본 원인**: `repo/.env` 는 `ENABLE_WEB_TLS=1` + `WEB_TLS_CERT_FILE` / `WEB_TLS_KEY_FILE` 가 설정되었고 `docker-compose.yml` 의 web entrypoint 에는 `if [ "$ENABLE_WEB_TLS" = '1' ]; ... --ssl-keyfile ...` 분기가 있으나, dev 편의용으로 작성된 `docker-compose.override.yml` (gitignored, `.example` template 추적) 가 entrypoint 자체를 평문 HTTP uvicorn 으로 강제 override 하고 있었음. compose 자동 merge 로 dev override 가 base 설정을 덮어써서 external-exposed 시나리오에서도 평문 HTTP 만 listening. TASK-0103 (CHG-20260522-0006) 에서 클라이언트 secure-context guard 는 추가했지만 secure channel 자체가 비활성 상태. **수정**: (1) `docker-compose.override.yml` 의 web entrypoint 를 `--ssl-keyfile /certs/mysql-ai.company.local/privkey.pem --ssl-certfile /certs/mysql-ai.company.local/fullchain.pem` 포함한 HTTPS 종단으로 교체 (same-port 18080 HTTPS-only 정책 — 사용자 결정). (2) `docker-compose.override.yml.example` 에는 Variant A (local dev plain HTTP, gstack browse / curl 편의용) / Variant B (외부-노출 HTTPS, 본 cycle default) 두 형태를 주석으로 명시 — 운영자 선택 가능. (3) 기존 인증서 (`../artifacts/certs/mysql-ai.company.local/{fullchain,privkey}.pem`) 는 SAN 에 `IP Address:112.185.196.20` 이미 포함되어 있어 재발급 불필요. 호스트 포트 매핑 (`${WEB_PORT}:8000` = `18080:8000`) 그대로. **외부 영향**: 같은 포트의 HTTP 동시 제공은 안 되며, 기존 HTTP 18080 사용자는 모두 HTTPS 로 전환 필요. self-signed 인증서이므로 첫 접속 시 브라우저가 `NET::ERR_CERT_AUTHORITY_INVALID` 경고를 표시 — `고급 → 진행` 으로 우회. **검증**: `sudo docker compose up -d web` 으로 재기동 후 (1) 컨테이너 로그 `Uvicorn running on https://0.0.0.0:8000` 확인. (2) `curl -sk https://112.185.196.20:18080/` → HTTP 200 + `<title>DQA — Database Query Assistant</title>` 응답. (3) `curl http://112.185.196.20:18080/` → 연결 실패 (예상 — TLS 종단으로 변경됨). backend / RBAC / endpoint contract / DB schema / Python 코드 / Frontend 클라이언트 코드 무변경. TASK-0103 의 "blocked banner" 가드는 후방 안전망으로 유지되며, 본 cycle 로 정상 동선 (HTTPS) 이 회복되면서 모든 외부 사용자에게 WebCrypto SubtleCrypto 가 정상 동작.

---

**2026-05-22 TASK-0103 완료 — API Vault secure context 사전 차단 + UX 안내** (CHG-20260522-0006, REV-20260522-0006 [SKIPPED:non-policy-doc], REQ-20260522-0006, **Major** §12.3 — 외부 사용자 전원 영향 + 자격증명 처리 동선). 외부 사용자가 `http://112.185.196.20:18080/` 로 접속하여 OpenAI API Key 를 입력했을 때 모호한 toast 만 출력되며 저장 안 되는 이슈 보고. **근본 원인**: `encryptPlainApiKey()` 가 `window.crypto.subtle.importKey` 를 호출하는데, WebCrypto SubtleCrypto 는 **secure context (HTTPS / localhost) 에서만 정의**됨 (MDN). 외부 IP 의 HTTP 접속 환경에서는 `window.crypto.subtle = undefined` → `Cannot read properties of undefined (reading 'importKey')` 예외 → catch 블록의 `showToast(error.message ...)` 가 사용자에게 원인을 명확히 전달하지 않음. 서버는 `/api/api-vault/options` 응답에 `requires_secure_context: True` 를 내려주었으나 클라이언트가 이 신호를 활용하지 않아 사전 가드 부재. **수정**: (1) `isVaultCryptoAvailable()` helper 추가 (`window.isSecureContext && window.crypto.subtle`). (2) `updateVaultReadiness()` 에 `blocked` 신규 상태 — banner 빨간 dot + "현재 접속 (...) 은 보안 컨텍스트가 아니어서 API 키를 암호화할 수 없습니다. HTTPS 또는 localhost 로 접속해 주세요." 안내. `state.apiVaultOptions.public_url` 이 https 면 보안 접속 주소도 표기. (3) `syncVaultSteps()` 가 `cryptoOk = false` 시 모든 step 을 `data-state="disabled"` (CSS 의 `pointer-events:none + opacity 0.55` 활용) + `saveVaultBtn.disabled = true`. (4) `encryptPlainApiKey()` 진입 시점에도 `isVaultCryptoAvailable()` 사전 검증 — UI 우회 시도 시 명시적 한국어 안내 throw. (5) `vault-banner[data-state="blocked"]` 에 빨간 색상 토큰 추가 (styles.css). cache-bust `v=20260522-vault-secure-context` (index.html). backend / RBAC / endpoint contract / DB schema / 암호화 알고리즘 (PBKDF2 + AES-GCM) 무변경. `docker compose build web` + `up -d --no-deps web` 으로 배포 — 30 초 다운타임. 외부 IP HTTP 환경에서 사용자가 즉시 사유 진단 가능 + saveVaultBtn 비활성으로 우발적 시도 차단. 근본 해결 (HTTPS 종단점 추가) 는 후속 인프라 작업으로 분리.

---

**2026-05-22 TASK-0102 완료 — topbar `관리 콘솔` 버튼 role fallback gate** (CHG-20260522-0005, REV-20260522-0005 [SKIPPED:non-policy-doc], REQ-20260522-0005, **Minor** §12.3). 테스트에서 `sales` 역할 사용자에게 topbar 관리 콘솔 버튼이 노출되는 현상 확인. **근본 원인**: TASK-0100 에서 추가한 `console_access` 플래그가 서버 미재시작 또는 구버전 서버 실행 시 존재하지 않아 fallback 경로가 없었음. **수정**: `canOpenAdminConsole()` 에 `role.key` 기반 fallback 추가 — `console_access` 가 서버 응답에 포함된 경우 그것을 사용, 없으면 `role.key === "admin"` 으로 fallback. role 필드는 TASK-0098 이전부터 항상 직렬화되므로 서버 버전 무관하게 존재. app.js + index.html(cache-bust `v=20260522-admin-topbar-rbac`) 변경. backend / RBAC / DB / endpoint 무변경.

---

**2026-05-22 TASK-0100 완료 — `관리 콘솔` 버튼 RBAC gate 수정** (CHG-20260522-0004, REV-20260522-0004 [SKIPPED:non-policy-doc], REQ-20260522-0004, **Minor** §12.3). TASK-0098 의 `can()` 단순화(`Boolean(state.user)`) side-effect 로 인해 `canOpenAdminConsole()` 이 로그인한 모든 사용자에게 `true` 반환 → `관리 콘솔` 버튼이 admin 역할 이외의 사용자(operator/sales/pending) 에게도 노출되던 이슈 수정. **수정 방식**: `_serialize_account()` 에 `console_access: _account_has_permission(account, "console.access")` 최소 플래그 추가 + `canOpenAdminConsole()` 이 `Boolean(state.user?.console_access)` 을 검사하도록 변경. TASK-0098 의 "permissions 전체 노출 차단" 설계를 유지하면서 UI gate 에 필요한 최소 정보만 전달. backend RBAC catalog / DB schema / endpoint contract 무변경. py_compile + node --check PASS. cache-bust `v=20260522-console-access-gate`. worktree `ai/claude/issue-admin-console-btn-rbac`.

---

**2026-05-22 TASK-0099 완료 (docs-only tracker hygiene) — audit subsystem followup backlog 8/8 closure marker** (CHG-20260522-0003, REV-20260522-0003 [SKIPPED:doc-only-tracker-hygiene], REQ-20260522-0003, **Minor** §12.3). TASK-0073 audit subsystem followup backlog 의 8 entries (TASK-0086 ~ 0093) 8/8 완료를 tracker 에 정확히 반영. TASK.md 의 stale `[ ]` 체크박스 2건 close: (1) line 152 TASK-0072 (main 통합 `f298f90` + post-deploy hotfix bundle TASK-0074/0075/0076/0077/0078/0079/0080 deployed but 상태 `outside-voice-review` 미갱신), (2) line 2767 TASK-0073 `AGENT_AUDIT_ENABLED=0 + AGENT_MODE=prod` startup fail-closed acceptance (TASK-0092 의 7 vector matrix V1-V3 fail-closed scenario 가 정확히 검증). TASK-0073 의 acceptance criteria 7건 모두 close. docs-only cycle — 코드 / RBAC / 스키마 / endpoint 변경 0. outside voice trigger 미해당 (`feedback_outside_voice_for_rbac` 미발동).

### TASK-0073 audit subsystem followup backlog 8/8 완료 (2026-05-20~22)

| TASK | 등급 | Summary | CHG | REV |
|---|---|---|---|---|
| TASK-0086 | Major §12.3 | `WebAccountActivity` legacy table DROP + dual write 종료 | CHG-20260520-0005 | REV-20260520-0005 [AGENT-TEAM:codex] |
| TASK-0087 | Major §12.3 | 외부 LAN trust 강화 — Caddy XFF 정규화 + `_get_client_ip()` 조건부 trust | CHG-20260520-0010 | REV-20260520-0010 [AGENT-TEAM:codex] |
| TASK-0088 | Minor §12.3 | `slow_query_log` 통합 ADR-0020 Decoupled 채택 (docs only) | CHG-20260520-0007 | REV-20260520-0007 [AGENT-TEAM:codex] |
| TASK-0089 | Minor §12.3 | 작업 화면 audit drawer UX (profile drawer "내 감사 로그" 탭) | CHG-20260520-0009 | REV-20260520-0009 [AGENT-TEAM:codex] |
| TASK-0090 | Minor §12.3 | CSV streaming export (hard cap 50k 제거 + keyset cursor pagination) | CHG-20260520-0008 | REV-20260520-0008 [AGENT-TEAM:codex] |
| TASK-0091 | Major §12.3 | PATCH admin/products audit before-state full snapshot + audit integrity fix | CHG-20260520-0006 | REV-20260520-0006 [AGENT-TEAM:codex] |
| TASK-0092 | Minor §12.3 | `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed 7 vector matrix 검증 | CHG-20260520-0004 | REV-20260520-0004 [AGENT-TEAM:codex] |
| TASK-0093 | Minor §12.3 | `bin/verify-completion.sh check_12` audit endpoint routing 정적 검사 | CHG-20260520-0003 | REV-20260520-0003 [AGENT-TEAM:codex] |
| TASK-0099 | Minor §12.3 | Audit followup backlog tracker hygiene (docs-only closure) | CHG-20260522-0003 | REV-20260522-0003 [SKIPPED] |

**8 audit followup task 의 외부 voice review 결과 요약**: 각 task 모두 Codex outside voice (consult mode, model_reasoning_effort=high) 흡수 후 Plan v2 redesign. 사용자 명시 결정으로 1 finding (TASK-0087 Major #1) 만 거부, 나머지 47 findings 모두 흡수.

---

**2026-05-22 TASK-0098 ship (PR #49) — Profile Drawer 탭 재구성 + 권한 정보 API 단위 차단** (CHG-20260522-0002, REV-20260522-0002 [AGENT-TEAM:codex-outside-voice], REQ-20260522-0002, **Critical** §12.3). 사용자 직접 요청 (2026-05-21). Profile Drawer 탭 5 → 4 = `[프롬프트, 보안 및 계정, API Vault, 내 감사 로그(gated)]` (보안+계정 통합 + "활동 정보" 최상단). "권한 현황" 패널 운영자 전용 분류 — 일반 사용자 UI + `/api/auth/me` 양쪽 차단. `/api/admin/me` 신규 endpoint 분리 (console.access gate, Codex F1 blocker fix). `_serialize_account(account, *, include_permissions: bool = False)` 시그너처 + 7 self callsite 자동 permissions 제거 + admin 3 callsite 명시 보존. frontend `can()` = `Boolean(state.user)` 단순화 ("표시 허용 + 실행은 backend 403 fallback" 패턴, Codex F5). `apiFetch` 403 공통 toast + backend 403 메시지 5 패턴 9 callsite normalize. admin.js `/api/auth/me` → `/api/admin/me` 전환. TASK-0089 "내 감사 로그" 탭 보존. tests 신규 9 시나리오 (4+5). Codex outside voice 6 findings 흡수 + 사용자 메모 `feedback_outside_voice_for_rbac` 정책 적용. **PR #49 multi-race rebase**: 본 cycle 원래 4 commit (base 8888130) → main stale 진행 (#45 v3.10.0 + #47 TASK-0089 + #48/#50 + #52/#61 TASK-0094 첨부 multi-cycle Sprint 1 + DQA 브랜딩 + TASK-0095/0096 v2) 흡수 후 main HEAD `20f0344` 위 단일 squash commit. ID reassign: TASK-0094→TASK-0098 / REQ-20260521-0001→REQ-20260522-0002 / AC-0199~0207→AC-0226~0234 / CHG·REV-20260521-0001~0004→CHG·REV-20260522-0002 / cache-bust `v=20260522-task-0098-perms`. 원래 4 commit backup branch `backup/profile-tabs-restructure-pre-rebase` 보존. py_compile + node --check + verify-completion --pre-commit PASS. 실 컨테이너 9 시나리오 smoke + UI dogfood 2 role 사용자 위임. worktree `ai/claude/profile-tabs-restructure`.

---

**이전 cycle (TASK-0087)**:

**2026-05-21 TASK-0087 완료 (Phase A~E 일괄) — 외부 LAN trust 강화** (CHG-20260520-0010, REV-20260520-0010 [AGENT-TEAM:codex-outside-voice], REQ-20260520-0002, **Major** §12.3). TASK-0073 audit subsystem followup backlog 의 마지막 항목 (TASK-0086~0093 8건의 8번째 = 0087). TASK-0073 Eng review E3 의 deferred 항목 (`_get_client_ip(request)` X-Forwarded-For 무조건 trust = 사내 LAN + Caddy proxy 전제, 외부 LAN/공개 인터넷 노출 시 IP spoof 위험) 을 명시적 정책 + 코드로 lock-in. Plan v1 (RFC1918 trust + silent skip + Caddy reverse_proxy 내부 trusted_proxies) → Codex outside voice review 6 findings (Major 5 + Minor 1) → Plan v2 (Caddy XFF 정규화 + mode-aware fail-loud + XFF IP 검증) 흡수. 사용자 명시 결정: RFC1918 default 유지 (사내 dev/staging 전제) + docker-compose port mapping 변경 별 cycle. 본 변경은 feature-0003 + feature-0006 dual ownership.

**Phase 별 요약**:
- **Phase A** — `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` 의 `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가. Caddy 가 받은 임의 XFF 를 본인이 본 TCP peer IP 로 덮어쓴다. 단일 hop 정규화 → multi-hop / spoof 차단.
- **Phase B** — `unit/feature-0003-agent-web-ui/src/app.py` 의 `_get_client_ip()` 재작성:
  - imports 에 `ipaddress`, `sys` 추가
  - `_parse_trusted_proxies(raw)` helper: 콤마 분리 + `ipaddress.ip_network(token, strict=False)` 파싱. invalid 토큰은 prod/staging `RuntimeError`, dev/test stderr WARNING + skip
  - module-level `WEB_TRUSTED_PROXIES`
  - `ENABLE_WEB_TLS_PROXY=1` + empty env 조합 startup gate (prod/staging RuntimeError, dev/test WARNING)
  - `_is_trusted_proxy(host)` helper
  - `_get_client_ip(request)`: direct_ip 가 trusted proxy 일 때만 XFF 첫 토큰 사용 + `ipaddress.ip_address(first)` 검증 + 실패 시 direct_ip fallback
- **Phase C** — `docs/SECURITY.md §9.7` 갱신 — 기존 3 bullet "deferred to feature-0006" 마커를 8 bullet 정책 (Caddy XFF 정규화 / 조건부 trust / XFF token 검증 / RFC1918 사용자 명시 결정 trade-off / mode-aware fail-loud / proxy mode + empty / schema 호환 / share token 미래 결합) 으로 교체.
- **Phase D** — feature-0003 + feature-0006 양쪽 docs 갱신 (TASK / MODIFY / REVIEW / REPORT / TEST / FUNCTION).
- **Phase E** — verify-completion + commit + cycle-finalize.

**Verification**:
- py_compile PASS (app.py 51 lines 추가)
- Caddyfile validate: `docker compose run --rm caddy caddy validate --config /etc/caddy/Caddyfile` 정상 (live 검증 사용자 위임)
- Codex outside voice review 6 findings (Major 5 + Minor 1) — Verdict NEEDS_REVISION → Plan v2 흡수 (5 흡수 + 1 사용자 명시 거부)
- TEST.md §4 8 시나리오 추가 (trusted+valid XFF / trusted+invalid XFF / trusted+empty 첫항목 / untrusted+XFF spoof 차단 / IPv6 trusted+XFF / invalid env prod fatal / proxy mode + empty prod fatal / caddy validate)

**Backward 호환**: `WEB_TRUSTED_PROXIES` 미설정 = `_get_client_ip()` 가 항상 direct_ip 반환 (caddy 환경에서는 caddy container IP). proxy mode + empty env warning/fatal 로 회귀 가시화. 운영자가 RFC1918 권장값 설정 시 기존 audit IP 품질 유지.

**TASK-0073 audit subsystem followup backlog 완료**: TASK-0086 (DROP) + TASK-0088 (slow_query_log ADR) + TASK-0089 (drawer UX) + TASK-0090 (CSV streaming) + TASK-0091 (product audit snapshot) + TASK-0092 (audit prod fail-closed) + TASK-0093 (verify-completion check_12) + **TASK-0087 (외부 LAN trust) — 본 cycle 완료** → 8건 모두 완료.

---

**2026-05-21 TASK-0095 완료 (Phase A~F 일괄, Phase G verify-completion + commit 진행 예정) — 시스템 프롬프트 누적 구조 최상위 GLOBAL layer 신설** (CHG-20260521-0003, REV-20260521-0003 [SELF-REVIEW], REQ-20260521-0003, **Major** §12.3). 사용자 직접 요청 — "최상위 전역 프롬프트도 구성해주세요. Product / Role / Account 에 기본적으로 처음 누적되어 요청사항에 적용될 부분입니다." 4 layer (BASE → Product → Role → Account) 의 BASE 가 코드 상수 hard-code 라 운영자 수정 불가하던 구조를 5 layer (GLOBAL → Product → Role → Account, BASE = code constant fallback) 로 확장. WebSystemPrompts 테이블의 scope discriminator 가 이미 'global' 을 수용 (VARCHAR(16)) — schema 무변경. RBAC 권한 2 종 신설 (`system_prompt.global.read` / `.write`, group=`settings`, admin only 자동 grant). 관리 콘솔 sidebar 에 신규 `설정` 탭 + 확장 가능한 `admin-settings-section` sub-section 패턴 도입 — 차후 운영 항목 추가 시 동일 패턴으로 sub-section 누적. AC-0011 갱신 + AC-0199 ~ AC-0204 신설.

**Phase 별 요약**:
- **Phase A** — `agent_core.compose_system_prompt(conn, ...)` 함수 진입부에 GLOBAL row fetch + graceful fallback (row 없음 / 빈 본문 / 조회 실패 → 코드 상수 SYSTEM_PROMPT 회귀).
- **Phase B** — `_ensure_seed_global_system_prompt(conn)` helper 신설, 부트스트랩에서 idempotent 호출. agent_core import 실패 / seed 본문 빈 경우 silent skip.
- **Phase C** — `PERMISSION_DEFINITIONS` 에 2 권한 추가. `_ensure_seed_roles` admin catchup list 에 두 권한 코드 추가.
- **Phase D** — GET/PUT `/api/admin/system-prompts` scope allowlist 에 `global` 추가 + `system_prompt.global.read/.write` 권한 가드.
- **Phase E** — `admin.html` `설정` 탭 + `admin-settings-section` sub-section 패턴, `admin.js` switchTab handler + mountSettingsSections() + buildSystemPromptEditor scope='global' 분기, `app.js` PERMISSION_GROUP_ORDER + permissionGroupOf + LABELS/DESCRIPTIONS 동기화, `styles.css` sub-section CSS rules.
- **Phase F** — FUNCTION/MODIFY/REVIEW/REPORT 갱신.
- **Phase G** — verify-completion + commit + main fast-forward (다음).

**Verification**: py_compile PASS (agent_core.py + app.py), node --check PASS (admin.js + app.js). live runtime smoke (관리 콘솔 `설정` 탭 진입 + 본문 수정 + LLM 호출 시 적용 확인) 사용자 검증 위임.

**Follow-up (CHG-20260521-0004 / REV-20260521-0004)**: live deploy 후 사용자 요청 "기능적인 검증 및 스크린샷을 통하여 UI 구성도 검증해주세요." 진행 중 발견된 hot-fix — fast-path catchup `_ensure_seed_catchup(conn)` 에 `_ensure_seed_global_system_prompt(conn)` 호출 누락. CHG-20260521-0003 가 slow path (`_ensure_web_tables`) 에만 helper 를 두었지만 기존 배포는 fast path 만 타기 때문에 GLOBAL row 가 자동 seed 안 되어 textarea 빈 채 노출. `_ensure_seed_role_system_prompts(conn)` 직후 1줄 추가로 보정. idempotent — 양쪽 path 호출 시에도 INSERT 1회만.

**Follow-up (TASK-0096 / CHG-20260521-0005 / REV-20260521-0005, REQ-20260521-0004, Minor §12.3 — `설정` pane sub-sidebar + panel 확장 패턴)**: 사용자 직접 요청 — TASK-0095 검증 완료 후속, "`설정` 탭 내부 화면을 `계정`, `역할`, `제품` 과 같이 패널을 분리해줄 수 있을까요? 차후 `전역 시스템 프롬프트` 항목 외에도 설정 내 많은 항목이 추가될 예정인데 현재는 확장성이 너무 좁게 구현되어 있습니다." 단일 sub-section 누적 구조 → 좌측 sub-sidebar (항목 nav) + 우측 panel 의 2-column grid 확장 패턴으로 전환. 새 항목 추가 절차 = nav button + panel article + `SETTINGS_PANEL_MOUNTERS` 등록 3 단계, panel 마운트는 첫 활성화 시 1회 lazy 실행. UI restructure only — 데이터/API/권한 무영향. AC-0210 신설, AC-0203 갱신 (sub-section → panel 명명).

**Follow-up v2 (TASK-0096 / CHG-20260521-0006 / REV-20260521-0006, REQ-20260521-0004, Minor §12.3 — `설정` pane 을 계정/역할/제품 과 동일한 list-detail 패턴으로 정렬 + 검색창)**: 사용자 직접 follow-up 피드백 — "계정, 역할, 제품 탭과 일관된 디자인이 아닌것으로 확인되었습니다. 검색창을 포함하여, 해당 탭들과 일관된 디자인으로 구성해주세요." v1 의 sub-sidebar (`admin-settings-shell` + `admin-settings-nav`) 변형이 다른 admin pane (계정/역할/제품) 의 5단 master-detail 패턴과 시각 일관성 부족. v2 에서 sub-sidebar 전용 클래스 일괄 제거 후 `admin-list-detail` (좌측 `admin-list-col` (검색창 + section-label + nav rows) + 우측 `admin-detail-col` (panel)) 그대로 차용. nav row 는 `.admin-list-row.admin-list-row--nav` 변형 (체크박스 슬롯 hidden). 검색창 = `admin-search` 재사용 + row 의 `data-settings-tab/-group/-keywords` + textContent 합집합 substring 매칭. AC-0210 갱신 (list-detail + 검색 hook 표기) + AC-0203 갱신 (panel 정렬 후 sentence 보강).

---

**2026-05-21 TASK-0094 PLAN-APPROVED — 첨부 multi-cycle (A CSV + B DDL/KB + C Vision + D PDF RAG) BRIEFING Revision 2 lock-in** (CHG-20260521-0001, REV-20260521-0001 [SUBAGENT:codex], REQ-20260521-0001, **Critical** §12.3). Codex outside-voice review 2 회 흡수 (REV-20260520-0001 1차 17 Valid + REV-20260521-0002 2차 Critical 3 + Major 11 + Minor 2 — F8 만 사용자 명시 거부). D1~D21 21 결정 lock-in. 코드/스키마/RBAC catalog 변경 0 — 계획 문서 only. Sprint 1 (Cycle 0 Foundation + Cycle 1 CSV ingest) implementation 진입 가능. D14 SQL allowlist guard 통과를 Sprint 1 ship 조건.

### Git 동기화 결과 (TASK-0094)
- 커밋: 90df7c4 (ai/claude/0087/attachment-briefing → issue/39-task-0094-attachment-briefing) + follow-up b8dcbfc (issue/43-task-0094-cleanup, REPORT 사후 기록 — 본 entry)
- verify-completion: PASS (10/10 checks, 재시도 1회 — CHECK#3/#8/#9 FAIL 후 MODIFY/REVIEW append + .gitignore 갱신으로 PASS)
- Push: 완료 (issue/39 + issue/43 → origin)
- PR: #40 (closes #39, MERGED 2026-05-21T02:15:30Z) + #44 (closes #43, REPORT 사후 기록 follow-up)
- 병합 상태: PR #40 main 통합 완료. PR #44 conflict resolve 후 main 통합 진행 중.
- 충돌 해결: PR #44 의 REPORT.md / MODIFY.md / REVIEW.md / TASK.md 가 origin/main 의 PR #42 (TASK-0090) merge 후 발생한 conflict — main 의 변경과 본 follow-up 의 변경 모두 보존하여 resolve.
- 다음 단계: Sprint 1 implementation 진입 — 별 worktree `ai/claude/0094/sprint-1-foundation-csv` (또는 호환 `ai/claude/0087/sprint-1-...`). 본 worktree 는 §15 R-F10 cleanup 조건 따라 merge 직후 cleanup 권장.

---

**2026-05-20 TASK-0089 완료 (Phase A~G 일괄) — 작업 화면 profile drawer "내 감사 로그" 탭 신설** (CHG-20260520-0009, REV-20260520-0009, REQ-20260520-0004, **Minor** §12.3 — 신규 backend endpoint 2 + frontend 3 + Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A** — backend 2 endpoint (`/api/profile/audits` + `/api/profile/audits/{event_id}`) 신설. 기존 audit helper 재사용 + `scope="own"` 강제 (Codex C2).
- **Phase B** — index.html drawer-tab + drawer-pane (filter row mini + 1-column list + pagination + inline detail). cache-bust `v=20260520-profile-audit`.
- **Phase C** — app.js: state.profileAudit + helper 6 + loader + renderer 2 + handlers + tab visibility + tab click branch + renderProfile wire.
- **Phase D** — styles.css `.profile-audit-*` ~15 클래스 (drawer 폭 적응 + ChangeJson 수평 스크롤).
- **Phase E** — py_compile + node --check PASS + routing smoke (신규 endpoint 2 등록 확인).
- **Phase F** — docs 6 + FUNCTION AC-0194.
- **Phase G** — verify-completion + commit + cycle-finalize.

**Codex outside voice 5 findings 흡수**:
- C1 URL mismatch → `/api/profile/audits` 신설
- C2 `.any > .own` → backend `scope="own"` 강제
- C3 CSV export drawer 위험 → 미노출
- C4 drawer 폭 → 1-column + inline detail + `<pre>` 수평 스크롤
- C5 권한 race → tab visibility + 403 graceful

### Git 동기화 결과 (§16.3 Step 6)

PR description body 명시 — REPORT.md 갱신 별 commit 회피 (cycle-finalize 패턴).

### 후속 단계 (별 cycle)

- drawer 에서 자기 audit CSV export (`/api/profile/audits/export.csv` + scope="own", Minor)
- TASK-0073 backlog 1 entry 남음 (TASK-0087, 외부 LAN trust feature-0006 위임)
- SECURITY.md §8 strict-string-equality (TASK-0092 followup)
- `_migrate_web_account_activity_to_audit()` 제거 (TASK-0086 followup)
- 동시 export 제한 + EXPLAIN 분석 (TASK-0090 followup)

---

## 1.archived TASK-0090 Summary (2026-05-20)

**2026-05-20 TASK-0090 완료 (Phase A~D 일괄) — `/api/admin/audits/export.csv` CSV streaming export 전환** (CHG-20260520-0008, REV-20260520-0008, REQ-20260520-0005, **Minor** §12.3 — hard cap 50k 제거 + StreamingResponse + keyset cursor + max_id high-water + self-audit, Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A** — `export_audit_events_csv` endpoint 전면 재작성. 2-phase 구조 (auth conn + max_id capture + start audit → sync generator with streaming-only conn + chunked SELECT + byte-threshold flush + try/finally + complete audit). 신규 helper `_audit_export_filter_hash()`, const `_AUDIT_EXPORT_CHUNK_SIZE=500` / `_AUDIT_EXPORT_FLUSH_BYTES=65536`. `StreamingResponse` import.
- **Phase B** — py_compile + lightweight smoke 모두 PASS.
- **Phase C** — docs 6 갱신.
- **Phase D** — verify-completion + commit + cycle-finalize.

**Codex outside voice 5 findings 흡수**:
- C1 async + sync mysql blocking → sync generator + streaming-only conn
- C2 consistent snapshot → max_id high-water mark
- C3 query plan EXPLAIN → future cycle
- C4 cap 제거 = DoS → SECURITY 갱신 + export self-audit
- C5 cleanup → generator 내부 try/finally

**Self-audit ActionCode 신설**: `audit.export.start` / `audit.export.complete` / `audit.export.aborted`.

### Git 동기화 결과 (§16.3 Step 6)

PR description body 명시 — REPORT.md 갱신 별 commit 회피 (cycle-finalize 패턴).

### 후속 단계 (별 cycle)

- 동시 export 제한 (multi-worker semaphore 정합 검토 + advisory lock, Minor)
- representative filters EXPLAIN FORMAT=JSON 분석 (Minor, live mysql)
- TASK-0073 backlog 2 entries 남음 (TASK-0087/0089)
- SECURITY.md §8 strict-string-equality 계약 (TASK-0092 followup)
- `_migrate_web_account_activity_to_audit()` 제거 (TASK-0086 followup)

---

## 1.archived TASK-0088 Summary (2026-05-20)

**2026-05-20 TASK-0088 완료 (Phase A~D 일괄) — `slow_query_log` 통합 ADR-0020 Decoupled 채택 (docs only)** (CHG-20260520-0007, REV-20260520-0007, REQ-20260520-0003, **Minor** §12.3 — ADR-0019 Codex C1 lock-in 의 final 결론, Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A** — `docs/DECISIONS.md` ADR-0020 신설. 4 section + Options 검토 + Recommended performance path + Security policy + Consequences. ADR-0019 의 "별 cycle 분리" 라인 cross-reference 추가.
- **Phase B** — `docs/SECURITY.md §9.9` ADR-0020 cross-reference + raw SQL = 민감 로그 정책 + PS digest-first 권유. + docs 5 갱신 (TASK §2.6 + MODIFY CHG-0007 + REVIEW REV-0007 + TEST §4 + 본 REPORT).
- **Phase C** — verify-completion + commit.
- **Phase D** — cycle-finalize (issue + push + PR + merge + cleanup).

**ADR-0020 핵심 결정**:
- **Option C — Decoupled 채택**: slow_query_log 와 WebAuditEvents 통합 안 함.
- **주 근거**: raw SQL text PII 차단 (PasswordHash/Token/API key/임시 비밀번호/raw LLM prompt literal).
- **Option A reject** (Sidecar ETL): semantic pollution + raw SQL PII + ChangeJson/table bloat + actor/target 의미 부재.
- **Option B reject** (별 endpoint): raw SQL exfiltration + mount/race + DoS + `audit.read.any` 권한 의미 오염 + MySQL `TABLE` log destination 우회.
- **운영 성능 관측 권유**: `performance_schema`/`sys` digest views (1차) + slow_query_log incident enable (2차).
- **외부 SaaS/multi-tenant trigger**: `performance-log.read` permission + redaction/sampling + threat model ADR 선행.

**Codex outside voice 5 findings 흡수**:
- C1 current state framing 정정 (not enabled, forward-looking)
- C2 raw SQL PII 차단 = 주 근거 (1순위)
- C3 Option A reject 재작성 (4 구체 사유)
- C4 Option B reject 재작성 (5 구체 사유)
- C5 performance_schema digest-first 권유 추가

### Git 동기화 결과 (§16.3 Step 6)

PR description body 명시 — REPORT.md 갱신 별 commit 회피 (cycle-finalize 패턴, TASK-0093/0092/0086/0091 답습).

### 후속 단계

- 외부 SaaS/multi-tenant 진입 시 별 cycle (Major §12.3) — 4 선행 조건 충족 후 (`performance-log.read` + redaction/sampling + retention + threat model ADR)
- `performance_schema` digest views 운영자 access policy (별 cycle 또는 SECURITY.md §9 갱신)
- TASK-0073 backlog 3 entries 남음 (TASK-0087/0089/0090) — 각 별 cycle

---

## 1.archived TASK-0091 Summary (2026-05-20)

**2026-05-20 TASK-0091 완료 (Phase A~F 일괄) — PATCH admin/products audit before-state full snapshot + audit integrity fix** (CHG-20260520-0006, REV-20260520-0006, REQ-20260520-0006, ~~Minor~~→**Major** §12.3 — Codex outside voice 5 findings 흡수, audit integrity 결함 fix 포함 scope 확장).

**본 cycle Phase 별 변경 요약**:
- **Phase A** — 신규 helper `_audit_product_snapshot(conn, product_id)` (~line 2127): single-row WebProducts snapshot + `SELECT ... FOR UPDATE` + `system_prompt_summary` (SECURITY §9.2 정합, content 본문 제외).
- **Phase B** — `admin_update_product()` 명시 transaction (autocommit=False + before snapshot + UPDATE + default_cleared_product_ids + after snapshot + audit + commit + finally autocommit=True). Codex C2 audit integrity fix.
- **Phase B-2** — `_AUDIT_BUILDER_PRODUCT_FIELDS` 7→8 field 확장 (+is_default/+sort_order/+system_prompt_summary, -databases/-system_prompt). builder branch `default_cleared_product_ids` 명시 처리.
- **Phase C** — py_compile PASS + sentinel smoke PASS (SENTINEL drop / databases drop / sort_order delta / is_default delta / default_cleared_product_ids / system_prompt_summary).
- **Phase D** — docs 6 갱신: TASK §2.5 / MODIFY CHG-0006 / REVIEW REV-0006 / 본 REPORT / TEST §4 / FUNCTION AC-0192.
- **Phase E** — verify-completion PASS + commit.
- **Phase F** — cycle-finalize (issue + push + PR + merge + main worktree pull + 본 worktree cleanup).

**Codex outside voice 5 findings 흡수**:
- C1 system_prompt full content → summary only (SECURITY §9.2)
- C2 autocommit/transaction → 명시 transaction + SELECT FOR UPDATE
- C3 list scan → single-row helper + databases 제외
- C4 allowlist 누락 → +is_default/+sort_order + default_cleared_product_ids
- C5 rollback → C1 ACCEPT 로 자동 해소

**핵심 발견 (Codex C2)**: 본 cycle 의 Minor 등급 추정이 **audit integrity 결함** 노출 — `admin_update_product()` 가 autocommit=True default 라 UPDATE 가 즉시 commit, audit fail 시 rollback 가능 0 인 상태. scope ~~Minor~~→Major 확장하여 일괄 fix.

**Sentinel smoke 결과** (Phase C):
- `'TASK-0091-SENTINEL' in body: False` ✓ (system_prompt full drop)
- `'should_not_leak' in body: False` ✓ (databases drop)
- sort_order 100→50, is_default False→True, default_cleared_product_ids [5,9] ✓
- system_prompt_summary: {present: True, content_len: 1234/2000, updated_at}

### Git 동기화 결과 (§16.3 Step 6)

PR description body 명시 — REPORT.md 갱신 별 commit 회피 (§16.3 Step 7 권장, TASK-0093/0092/0086 cycle 답습).

### 후속 단계

- admin.product.create / delete 의 audit 도 allowlist 확장 결과 자동 정합 — 별 sentinel test 권유 (Minor)
- admin.product.databases.update audit 의 system_prompt summary 패턴 도입 검토 (별 cycle)
- SECURITY.md §8 strict-string-equality 계약 명시 (TASK-0092 followup)
- rollback window (1~2 cycle) 종료 후 _migrate_web_account_activity_to_audit() 제거 (TASK-0086 followup)
- TASK-0073 backlog 4 entries 남음 (TASK-0087/0088/0089/0090) — 각 별 cycle

---

## 1.archived TASK-0086 Summary (2026-05-20)

**2026-05-20 TASK-0086 완료 (Phase A0~J 일괄) — `WebAccountActivity` legacy table DROP + dual write 종료** (CHG-20260520-0005, REV-20260520-0005, REQ-20260520-0001, **Major** §12.3 — 파괴적 DROP + dual write 단일화 + Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A** (backup + 검증): mysqldump 8 옵션 (Codex C4) + scratch restore rehearsal + 1:1 정합 (74=74). backup file `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes, digest `a09e7898d1ce88711f7a850ab5fbcc91`).
- **Phase B** (사용자 명시 ack): DROP 진행 ack 받음.
- **Phase C** (코드 변경 3): `_log_search_activity()` legacy INSERT 제거 + `_ensure_web_account_activity_schema()` 호출×2+정의 제거 + `_migrate_web_account_activity_to_audit()` rollback window 보존 + docstring 갱신. py_compile PASS.
- **Phase D+E** (lightweight smoke): host-mounted code + docker run import → `IMPORTED OK` + 함수 정의 부재/존재 정합 확인.
- **Phase F** (DROP): `DROP TABLE IF EXISTS WebAccountActivity` 실행 → `DROP completed`.
- **Phase G** (verify): `tables_remaining=0` + mirror 74 row 변동 없음.
- **Phase H** (docs 5 + tests 1 갱신): 본 REPORT.md + TASK §2.4 + MODIFY CHG-20260520-0005 + REVIEW REV-20260520-0005 + TEST §4 prepend + SECURITY §9.8 + test_audit_migration.py M3 제거.
- **Phase I** (verify-completion + commit): 본 단계 진행.
- **Phase J** (cycle-finalize): issue + push + PR + merge + main worktree pull + 본 worktree cleanup.

**Codex outside voice 5 findings 흡수**:
- **C1** Option A 불가능 → helper Option B (호출+정의 명시 제거, migration helper 만 rollback window 보존)
- **C2** dispatcher-only = mirror failure 가 audit 누락 → lightweight smoke + tests M3 제거
- **C3** "single tx DROP" 표현 → "single statement" 정정 (MySQL DDL implicit commit)
- **C4** Backup 검증 강화 → mysqldump 8 옵션 + scratch restore + canonical digest
- **C5** Rollback 2 시나리오 분리 (DB restore only / code revert + DB restore)

**핵심 baseline (Phase A 검증)**:
- WebAccountActivity legacy = **74 rows** (id 1~74, MatchedCount sum=502)
- WebAuditEvents `conversation.search.body` mirror = **74 rows** (1:1 정합)
- 초기 흡수 (RequestId='account-activity:%') = 68 row (TASK-0073 Phase A2 의 1회 호출)
- dual write 추가 (RequestId=NULL + ChangeJson._legacy_source) = 6 row

### Git 동기화 결과 (§16.3 Step 6)

PR description body 에 명시 — REPORT.md 갱신 별 commit 회피 (§16.3 Step 7 권장, TASK-0093/0092 cycle 답습).

### Rollback runbook (2 시나리오, Codex C5)

- **시나리오 1 — DB restore only**: 코드는 그대로, backup SQL 로 table 복구. `_migrate_web_account_activity_to_audit()` 의 SHOW TABLES check 가 다시 true → 재 migration 시 idempotent skip (기존 marker). 단 새 search 는 dispatcher only 라 table 이 다시 비어감.
- **시나리오 2 — code revert + DB restore** (완전 rollback): `git revert <CHG-20260520-0005>` + `docker compose restart web` + DB restore. dual write 부활 + 새 search 가 양쪽에 들어감.

### 후속 단계

- **rollback window 종료 후** (1~2 cycle): `_migrate_web_account_activity_to_audit()` helper 자체 제거 별 cycle (Minor §12.3).
- function rename `_log_search_activity()` → `_audit_conversation_search()` 별 cycle (Minor §12.3, caller 안정성 검토 후).
- SECURITY.md §8 strict-string-equality 계약 명시 (TASK-0092 followup, V6 결과 기반).
- TASK-0073 backlog 5 entries 남음 (TASK-0087, 0088, 0089, 0090, 0091) — 각 별 cycle.

---

## 1.archived TASK-0092 Summary (2026-05-20)

**2026-05-20 TASK-0092 완료 (Phase A0~E 일괄) — `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed 7 vector matrix 검증 (TASK-0073 Phase E 위임 1 건 해소)** (CHG-20260520-0004, REV-20260520-0004, REQ-20260520-0007, **Minor** §12.3 — live container spawn + Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A0** (`.env` + image 가용성 확인): `repo-web:latest` image 가용 (435MB, 이미 build). `.env` 부재 — inline `-e` 만 사용 (compose 우회).
- **Phase A** (7 vector live spawn): `docker run --rm --entrypoint python repo-web:latest -c "import web.app"` 형태 단발 spawn. 7 vector 명세된 환경변수 조합으로 호출.
- **Phase B** (검증, **7 vector PASS (7/7)**):
  - V1 (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod`) → rc=1 + 3 substring + Traceback 부재 ✓
  - V2 (audit=0 + mode=unset) → rc=1 + `AGENT_MODE=(unset → prod)` 정합 ✓
  - V3 (audit=0 + mode=staging) → rc=1 + `AGENT_MODE=staging` 정합 ✓
  - V4 (audit=0 + mode=dev) → rc=0 + `IMPORTED OK` ✓ dev/test bypass
  - V5 (audit=1 + mode=prod) → rc=0 + `IMPORTED OK` ✓ positive control
  - V6 (audit=true + mode=prod) → rc=1 + `[FATAL]` ✓ Codex C3 strict-string-equality 계약
  - V7 (모두 unset) → rc=0 + `IMPORTED OK` ✓ default `1` + default prod
- **Phase C** (docs 5 갱신): 본 REPORT.md + TASK.md §2.3 + MODIFY.md CHG-20260520-0004 + REVIEW.md REV-20260520-0004 + TEST.md **§4** append.
- **Phase D** (verify-completion + commit): `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS 후 사용자 명시 confirm 후 commit.
- **Phase E** (cycle-finalize 패턴): issue + push + PR + merge + main worktree pull + 본 worktree cleanup.

**Outside voice 흡수 5 findings 결정**:
- C1 테스트 명령 오류 → `--entrypoint python` + `import web.app` 정정
- C2 compose 오염 → `docker run` 직접 호출 (compose 우회)
- C3 flag parsing 계약 → V6 추가 (`"true"` fail-closed 검증)
- C4 stderr 검증 → 3 substring + Traceback 부재
- C5 docs §3 → §4 정정 (Test Run History)

**핵심 발견 (V6)**: `AGENT_AUDIT_ENABLED="true"` 는 fail-closed 됨 — strict string equality (`os.getenv(...).strip() == "1"`). 운영자가 truthy 표현 (`"true"`/`"yes"`/`"01"`) 명시 시 prod 시작 차단. SECURITY.md §8 의 strict-string-equality 계약 명시 별 cycle 후속 권고.

### Git 동기화 결과 (§16.3 Step 6)

PR description body 에 명시 — REPORT.md 갱신 별 commit 회피 (§16.3 Step 7 권장 패턴, TASK-0093 cycle 답습).

### 후속 단계

- **SECURITY.md §8 strict-string-equality 계약 명시** 별 cycle (Minor §12.3) — V6 결과 기반.
- TASK-0073 backlog 6 entries 남음 (TASK-0086, 0087, 0088, 0089, 0090, 0091) — 각 별 cycle.
- 본 cycle 종료 후 worktree archive — 다음 task 진입 시 별 worktree (`ai/claude/00XX/<slice>`) 권장.

---

## 1.archived TASK-0093 Summary (2026-05-20)

**2026-05-20 TASK-0093 완료 (Phase A~F 일괄) — verify-completion check_12 audit endpoint routing 정적 검사 신설** (CHG-20260520-0003, REV-20260520-0003, REQ-20260520-0008, **Minor** §12.3 — TASK-0073 Phase E hotfix CHG-20260520-0001 의 routing 회귀 fragility 보강. Codex outside voice 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용).

**본 cycle Phase 별 변경 요약**:
- **Phase A** (`bin/verify-completion.sh` 갱신): `check_12_audit_endpoint_routing()` + `_check_audit_routing_order()` pure helper split (line ~936-1010). `main()` 의 line 1123 에 호출 추가. footer 의 "9 checks" → "10 checks: 7 pilot + worktree binding + repo immutability + audit endpoint routing" (line 1126·1129). META mode footer 는 그대로 (check_12 는 feature-specific). `bash -n` syntax PASS.
- **Phase B** (production positive): production app.py 호출 → `CHECK#12 PASS audit endpoint routing order`. line 9522 max-static < line 9732 detail.
- **Phase C** (5 fixture negative test, production app.py 미수정):
  - `valid.py` (정합 ordering) → PASS
  - `wrong_order.py` (event_id BEFORE static siblings) → FAIL "ordering" + line number hint
  - `no_detail.py` (detail 부재) → FAIL "detail endpoint missing — possible route removal or refactor"
  - `no_siblings.py` (정적 GET sibling 부재) → FAIL "no static GET siblings — audit route layout changed"
  - `refactored.py` (APIRouter prefix) → FAIL "routes not found in expected form — manual review required"
- **Phase D** (5 other-feature SKIP + 1 missing-app structural FAIL): feature-0001/0002/0004/0005/0006 호출 → rc=0, no output. target feature + app.py 부재 → FAIL "expected app.py at <path> but file is missing".
- **Phase E** (docs 5 갱신): 본 REPORT.md + TASK.md §2.2 + MODIFY.md CHG-20260520-0003 + REVIEW.md REV-20260520-0003 + TEST.md.
- **Phase F** (최종 verify-completion + commit): `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` META mode PASS (check_12 자동 skip 정합) + 사용자 명시 commit confirm.

**Outside voice 흡수 5 findings 결정**:
- C1 SKIP→FAIL structural (회귀 방지 게이트 의도 정합)
- C2 grep 패턴 fragility (C1 통합, AST 파서 미도입 — Minor scope)
- C3 `/purge` method-aware mismatch → sibling list 자동 제외
- C4 Inline 4-path → auto-discovery (`@app.get("/api/admin/audits/<non-{>")` 패턴)
- C5 Production app.py 임시 이동 risk → temp fixture + helper split

**in-cycle fix (Phase C debug)**: `set -euo pipefail` + grep no-match (exit 1) 시 `|| true` fallback 처리. log_check 호출 보장.

**Git 동기화 결과** (§16.5 Step 6): `ai/claude/0086/audit-followup` worktree 의 단일 commit. 본 cycle 의 base 는 f41e4f8 (CHG-20260520-0002 backlog staging). 사용자 명시 confirm 후 commit + push 진행. 후속 cycle (TASK-0086~0092 7 entries) 은 별 cycle 별 별 PLAN-APPROVED.

---

## 1.archived TASK-0073 Summary (2026-05-19~20)

**2026-05-19 TASK-0073 진행 중 (Phase A1~D 완료, Phase E 컨테이너 검증 + 최종 commit) — 모든 계정 행위 audit subsystem 도입** (CHG-20260519-0017~0024, REV-20260519-0013~0020, REQ-20260519-0001, **Critical** §12.3 — 인증·인가 + PII 수집 + RBAC 4 신규 + Tx split + dispatcher SPOF + Codex outside voice 14 findings + Eng review E1-E9 lock-in).

**Phase 별 변경 요약**:
- **Phase A1** (CHG-0017): `record_audit_event()` dispatcher + `AGENT_AUDIT_ENABLED` prod startup fail-closed gate (Codex C5) + `bin/verify-completion.sh check_11_audit_dispatcher` SPOF guard (Eng E7).
- **Phase A2** (CHG-0018): WebAccountActivity 흡수 + `_migrate_web_account_activity_to_audit(conn)` helper (idempotent SQL marker `RequestId='account-activity:<id>'`) + `_log_search_activity` signature transparent dual write wrap (Codex C2).
- **Phase A3** (CHG-0019): `PERMISSION_DEFINITIONS` +4 (`audit.read.own/.any/.export/.purge`) + permission group `audit` + admin/operator/sales/dba/pending 5 role catchup loop (Eng E9, Codex C8/C9/C10).
- **Phase A4** (CHG-0020): 5 audit read endpoint (`/api/admin/audits` + detail + export.csv + actors facet + resources facet) + chunked PK purge `POST /api/admin/audits/purge` (Eng E1 Actor OR Target self filter + E8 의사코드 + 30s deadline + idempotency_key).
- **Phase A5** (CHG-0021): admin 11 mutation endpoint Same tx audit hook + 16 ActionCode `build_audit_change_json` builder (Codex C6 allowlist) + `_audit_admin_mutation` helper.
- **Phase A6** (CHG-0022): user 5 endpoint fail-open audit + `_audit_user_action` helper. `/api/ask`, share create / revoke / public view (ActorType='anonymous', Eng E4) / fork.
- **Phase B** (CHG-0023): 3 test 파일. 실 실행은 Phase E 컨테이너 가동 후 사용자 위임.
- **Phase C** (CHG-0024): Frontend admin "감사 로그" 탭 + filter + list-detail + CSV export gated + PERMISSION_GROUP_ORDER 'audit'.
- **Phase D** (이번 commit): `docs/SECURITY.md §9` + `docs/DECISIONS.md ADR-0019` + `docs/ARCHITECTURE.md §4·§6` + `docs/CONVENTIONS.md §10.6` + `docs/STATUS.md` + 본 REPORT.md / TEST.md.

**Git 동기화 결과** (§16.5 Step 6):
- 커밋: 8 phase commits (`bf21886` A1 / `88d6fa4` A2 / `2e45cb4` A3 / `e21ab15` A4 / `4ed5f0d` A5 / `5f42ba6` A6 / `c801104` B / `2ddf9b5` C / Phase D 진행 중).
- worktree: `ai/claude/0073/agent-audit` (`.worktrees/0073-agent-audit/`, §13.2 manual parallel AI worktree).
- verify-completion: 모든 phase PASS (9 checks: 7 pilot + worktree binding + audit dispatcher).
- Push: 보류 (sandbox SSH 인증 차단 — 본 session 종료 후 사용자가 직접 push).
- PR: 미생성 (사용자 결정).
- 충돌 해결: 없음.

**남은 위험 / 후속**:
- Phase E HTTP smoke 실 실행 (admin/operator 자격 + 컨테이너 가동 후 사용자 검증).
- WebAccountActivity 별 cycle DROP (data backup + dual write 검증 후).
- `_get_client_ip` 외부 LAN trust 강화 (feature-0006-lan-proxy-access 후속).
- 작업 화면 audit 자기 view drawer (별 cycle UX).

상세 진행: `docs/MODIFY.md` CHG-20260519-0017~0024 + `docs/REVIEW.md` REV-20260519-0013~0020.

---

(이전 cycle Summary — TASK-0085 lazy-create 사이드바 optimistic pending entry, CHG-0016 / REV-0012)

**2026-05-19 TASK-0085 완료 — lazy-create 사이드바 optimistic pending entry (송신 직후 다른 대화 전환 시 새 대화 entry 잠시 소실 UX 회귀 fix + 클릭 swap 으로 작업 step 현황 출력 지원)** (CHG-20260519-0016, REV-20260519-0012, REQ-20260519-0014, Minor §12.3 — frontend state machine + rendering refactor 5 영역, backend / RBAC / endpoint / audit / DB 무변경).

**배경**: 사용자 직접 요청 — "+ 새 대화 에서 요청을 보내면, 해당 대화가 사용자 입장에서(웹브라우저에서) 즉시 활성화된 대화 객체로 받아들이도록 구성" + "현재는 + 새 대화 에서 요청 후 다른 대화로 전환할 때, 이전에 요청한 신규 대화가 잠시동안 목록에서 사라지는 이슈" + click UX 결정 "대화 내부 진입도 가능하도록 구성해주세요. 작업 step 현황의 출력을 위해서입니다".

**원인**: TASK-0048 의 lazy-create 패턴이 backend conversation row 등재를 `/api/ask` 응답 시점까지 지연. frontend 의 `state.conversations` (사이드바 list) 는 응답 도착 시 `refreshWorkspace` 가 backend `/api/conversations` 결과로 통째 replace — 그 사이 (응답 도착 전) 사용자가 다른 대화로 전환하면 `selectConversation` 이 `state.pendingNewConversation=false` set + `appendPendingItem` 작성 중 placeholder 도 사라짐. 결과: 새 대화 entry 가 사이드바에서 완전 소실 → 응답 도착 후 refreshWorkspace 시점에야 다시 표시.

**Fix design (multi-pending optimistic list entry)**:
- `state.pendingConversationEntries: Map<sentinel, { sentinel, message, started_at, status }>` 신설. multi-pending 지원 — TASK-0082 unique sentinel design 정합.
- `sendPrompt()` lazy-create 진입 시점에 entry add + `renderConversationList()` 호출 — 사이드바 즉시 표시.
- success path: closure 일치 여부와 무관하게 본 send 의 sentinel entry 만 delete (실 cid entry 는 `refreshWorkspace` 가 등재).
- catch path: status="failed" set + 3 s 후 자동 delete. 사용자에게 toast + 사이드바 양방향 안내.
- `renderConversationList()` 의 `hasPending` split: `hasDraftPending` + `hasInFlightPending`. combined prepend 로 둘 다 own 그룹에 표시.
- 신규 `appendInFlightPendingItems()` + `_switchToPendingConversationContext(entry)` helper.

**회귀 시나리오 5 종 검증** (코드 trace 기반):
- ①+ 새 대화 송신 직후 다른 대화 클릭 → state.pendingConversationEntries 에 entry 보존, 사이드바에 in-flight 표시 지속.
- ②응답 도착 → success path 가 본 sentinel entry delete + refreshWorkspace 가 실 cid entry 등재. optimistic → 실 entry 자연 swap.
- ③catch (네트워크 timeout 등) → "전송 실패" 표시 3 s 후 cleanup. 입력란 활성화로 사용자 즉시 재시도 가능.
- ④pending entry 클릭 → `_switchToPendingConversationContext` 가 sentinel 컨텍스트로 swap. pendingBubble 복원으로 elapsed timer 이어짐. 응답 도착 시 closure 일치 → 자동 cid binding + polling 시작.
- ⑤multi-pending 동시 진행 → 각 sentinel 별 분리 보존.

**검증**: `node --check app.js` PASS. backend / RBAC / endpoint / audit / DB 무변경. cache-bust `v=20260519-unique-sentinel` → `v=20260519-pending-entries`.

**Worktree 격리**: 본 작업은 다른 AI 작업자의 main 영역 변경과 격리하기 위해 worktree `ai/claude/0083/pending-list-entry` 에서 진행 후 main 으로 fast-forward merge.

**Trace**: REQ-20260519-0014 → TASK-0085 → CHG-20260519-0016 → REV-20260519-0012. TASK-0048 lazy-create + TASK-0082 unique sentinel design 의 자연 연속.

---

**2026-05-19 TASK-0082 완료 — lazy-create unique sentinel design (첫 in-flight 중 + 새 대화 클릭 시 input 비활성 회귀 근본 fix, TASK-0081 followup)** (CHG-20260519-0012, REV-20260519-0008, REQ-20260519-0010, Minor §12.3 — frontend state machine refactor 5 군데, backend / RBAC / endpoint / audit / DB 무변경).

**배경**: TASK-0081 fix 후 사용자 추가 보고 — "대화 요청을 보낸 후, + 새 대화 버튼을 클릭한 후에도 요청 텍스트 입력칸이 활성화되지 않는 이슈". TASK-0081 의 stale guard + catch cleanup 만으로는 첫 lazy-create in-flight 중 + 새 대화 클릭 시나리오를 cover 못 함.

**원인 (TASK-0081 보다 근본)**: `app.js` 의 글로벌 단일 sentinel (`PENDING_CONV_SENTINEL = "__pending__"`) 가 lazy-create busy tracking 의 토큰. 첫 send 가 in-flight 일 때 busyConversations 에 sentinel 점유 → 사용자가 + 새 대화 클릭해도 두 번째 컨텍스트의 `isCurrentConvBusy()` 가 same sentinel 검사로 true 반환 → `renderComposer()` 가 `promptInputEl.disabled = true` 유지 → input 활성화 안 됨. 추가로 TASK-0081 의 guard 분기는 in-flight 시 early return 으로 renderComposer 호출조차 skip — input.disabled state update 자체 안 됨. 두 결함 합쳐서 사용자 증상.

**Fix**: 각 lazy-create 진입마다 unique sentinel 부여하는 design.

- `state.pendingSentinel` field 추가 — 활성 lazy-create 의 unique sentinel 보관.
- `_newPendingSentinel()` helper — `${prefix}_${Date.now()}_${random 6 char}` 패턴, 16M 분리.
- `isCurrentConvBusy()` 의 sentinel 검사를 글로벌 단일 → `state.pendingSentinel` 점유 여부로 변경.
- `beginPendingConversation()` 의 TASK-0081 guard 제거 + `state.pendingSentinel = _newPendingSentinel()` 명시 부여. 항상 reset 흐름 진입.
- `sendPrompt()` 의 busyKey 를 `state.pendingSentinel` 으로 closure capture. success / catch path 의 cleanup 은 `if (state.pendingSentinel === busyKey)` 일치 검사 후에만 실행.

이 design 의 핵심: 첫 sendPrompt 의 closure 에 capture 된 옛 sentinel ("A") 은 본 함수의 finally 가 책임지고 cleanup. 사용자가 그 사이 + 새 대화 클릭으로 두 번째 컨텍스트 진입하면 `state.pendingSentinel` 은 새 sentinel ("B") 으로 갱신. 첫 send 의 success/catch path 는 closure key ("A") 와 `state.pendingSentinel` ("B") 의 불일치를 보고 두 번째 컨텍스트 state 보존. 두 번째 send 의 busyKey 는 "B" — 본 send 의 finally 가 "B" 만 cleanup.

**회귀 시나리오 4 종 검증** (코드 trace 기반):
- ①첫 송신 in-flight 중 + 새 대화 클릭 → state.pendingSentinel 이 "A" → "B" 로 swap. renderComposer 의 isCurrentConvBusy 가 busyConversations.has("B") = false → busy=false → **input 활성화** ✓. 사용자 두 번째 prompt 작성 + send → busyKey="B" → in-flight. 첫 응답 도착 시 closure mismatch 로 두 번째 컨텍스트 보존. 두 번째 응답 도착 시 closure 일치로 normal cleanup. 사이드바에 양쪽 conv 표시.
- ②catch 분기 종료 후 + 새 대화 → catch 에서 closure 일치 cleanup (state.pendingSentinel = null). 이후 + 새 대화 클릭 시 새 sentinel 부여. 정상 진행.
- ③응답 후 + 새 대화 (정상 흐름) → success path 의 closure 일치 cleanup. 이후 + 새 대화 시 새 sentinel.
- ④pending bubble error 표시 → closure mismatch 시 cleanup skip 하지만 bubble UI 는 별도 (state.pendingBubble). AC-0077 유지.

**TASK-0081 와의 관계**: TASK-0081 의 stale guard (`pendingNewConversation && busyConversations.has(sentinel)`) 와 catch cleanup 정책은 본 design 으로 자연 흡수. 각 진입이 새 sentinel 으로 reset 하므로 stale state 자체가 컨텍스트 분리로 해소. catch cleanup 도 closure-aware 로 유지하되 closure mismatch 시 skip 으로 두 번째 컨텍스트 보호.

**검증**: `node --check app.js` PASS. backend / RBAC / endpoint / audit / DB 무변경 (py_compile 대상 없음). cache-bust `v=20260519-pending-recovery` → `v=20260519-unique-sentinel` (index.html). smoke 시나리오 4 종은 사용자 환경 직접 확인 권장.

**Trace**: REQ-20260519-0010 → TASK-0082 → CHG-20260519-0012 → REV-20260519-0008.

---

**2026-05-19 TASK-0081 완료 — beginPendingConversation stale flag 회복 가드 + sendPrompt catch 분기 pendingNewConversation cleanup (두 번째 새 대화 send 차단 회귀 fix)** (CHG-20260519-0011, REV-20260519-0007, REQ-20260519-0009, Minor §12.3 — frontend state machine 2 군데 변경, backend / RBAC / endpoint / audit / DB 무변경).

**배경**: 사용자 직접 보고 — "새 대화에서 요청을 보낸 후, 다시 새 대화로 별개의 요청을 보내려고 했을 때 진행되지 않는 이슈". 증상 추가 확인: "두 번째 send 를 진행하는 상호작용 (요청 UI 버튼, Ctrl+Enter) 가 막혀있다".

**원인**: `app.js` 의 lazy-create state machine 2 군데 결함. (1) `beginPendingConversation()` (line 2988~3012) 의 early-return guard 가 `state.pendingNewConversation === true` 단독 검사로 stale state 와 정당한 in-flight 점유를 구분 못 함. 첫 lazy-create 가 network/timeout 으로 catch 분기에 진입한 경우 `state.pendingNewConversation` flag 가 cleanup 되지 않은 채 남음 → 사용자가 "+ 새 대화" 다시 클릭 → 가드가 stale flag 만 보고 입력란 포커스만 잡고 return → `state.activeConversationId = ""` reset 도 실행 안 됨. (2) `sendPrompt()` 의 lazy-create catch 분기 (line 3533~3551) 가 `state.pendingBubble` 의 error 영역만 처리하고 `state.pendingNewConversation` 자체는 cleanup 안 함. 결과: 두 번째 새 대화로 send 시도 시 (a) 진입조차 차단되거나 (b) 진입했어도 `sendPrompt()` 의 line 3437 `isCurrentConvBusy()` 가 `pendingNewConversation=true && busyConversations.has(sentinel)` 검사에서 막힘.

**Fix**:
- (a) `beginPendingConversation()` early-return 조건을 `state.pendingNewConversation && state.busyConversations.has(PENDING_CONV_SENTINEL)` 로 좁힘 — 첫 lazy-create 가 실제 in-flight (sentinel 점유) 일 때만 진입 보류. stale state 면 통과해 정상 reset 흐름 진입.
- (b) `sendPrompt()` lazy-create catch 분기 진입 시점에 `state.pendingNewConversation = false` 1 줄 명시 cleanup. pending bubble error 표시 / toast 안내 로직은 무변경. busyConversations sentinel cleanup 은 finally 의 기존 `state.busyConversations.delete(busyKey)` 가 담당.

**회귀 시나리오 5 종 검증** (코드 trace 기반):
- ①정상 첫 송신 후 두 번째 새 대화 진입 + send → 통과. (success path 의 line 3524 `pendingNewConversation = false` + finally sentinel delete 후 sentinel 부재 → guard 가 false → 정상 reset 진입).
- ②첫 송신 timeout 에러 후 두 번째 새 대화 → catch 의 신규 `pendingNewConversation = false` cleanup + sentinel delete (finally) → 두 번째 클릭 시 guard 통과 → 정상 진입.
- ③첫 송신 in-flight 중 사용자가 "+ 새 대화" 클릭 → guard 가 sentinel 점유 검사로 진입 보류 (의도된 동작 — sentinel 중복 race 방지).
- ④AC-0077 pending bubble error 표시: `state.pendingBubble` 별도 state 라 cleanup 과 무관 — 빨간 오류 영역 + toast 안내 그대로 노출.
- ⑤AC-0072~0077 lazy-create 정상 success 흐름 무영향: line 3522~3528 의 success path 변경 없음, polling 시작도 그대로.

**검증**: `node --check app.js` PASS. backend / RBAC / endpoint / audit / DB 무변경 (py_compile 대상 변경 없음). cache-bust `v=20260519-chat-pane-flex` → `v=20260519-pending-recovery` (index.html). smoke 시나리오 5 종은 사용자 환경 직접 확인 권장.

**Trace**: REQ-20260519-0009 → TASK-0081 → CHG-20260519-0011 → REV-20260519-0007.

---

**2026-05-18 TASK-0071 완료 — shell grid row hotfix (cascade root of TASK-0068~0070 layout chain)** (CHG-20260518-0008, REV-20260518-0008, REQ-20260518-0009, Minor §12.3 — CSS 2 줄 hotfix, RBAC / endpoint / 데이터 / JS 무변경).

**배경**: 사용자 3 차 screenshot 보고. TASK-0070 의 list-detail row fix 이후에도 dashboard pane 처럼 list-detail 을 사용하지 않는 화면에서 큰 viewport (height 800+) + 짧은 content 조합 시 sidebar / commit-bar 가 viewport 의 약 70% 위치까지만 차지하고 그 아래 회색 빈 영역이 viewport bottom 까지 노출.

**원인**: `.app-shell` / `.admin-shell` 의 `display: grid; height: 100vh` 만 정의하고 `grid-template-rows` 미정의 → default `auto` → single row track height = 자식 max-content. grid container 100vh 와 track height 의 mismatch 시 track 아래 빈 영역. 이전 cycle 들의 fix 는 column 안의 stretch chain 만 해결 — column 의 height 결정 layer (grid track) 는 미처리. cascade 의 root.

**환경 차이**: 본 환경 (chrome headless) 에서는 grid track 이 100vh 차지 동작이라 TASK-0069 부터 정상 보였음. 사용자 환경에서는 max-content 동작이라 노출. browser engine / DPI / timing 등 환경별 grid algorithm 차이가 회귀 timing 결정.

**Fix**: `.app-shell` 과 `.admin-shell` 양쪽에 `grid-template-rows: minmax(0, 1fr)` 추가 (2 줄, 동일 패턴 일관성). `minmax(0, 1fr)` 은 CSS Grid spec 의 명시적 단일 row stretch 패턴 — 환경 의존성 제거.

**Layout cascade 완성**:
```
.app-shell / .admin-shell { height: 100vh; grid-template-rows: minmax(0, 1fr) }  ← TASK-0071 (cascade root)
  └ chat-column / admin-column  (grid item, row full height)
      └ .chat-pane / .admin-workspace  { flex: 1 1 auto }  ← TASK-0069
          └ .admin-pane.is-active  { flex: 1 1 auto }
              └ .admin-list-detail  { grid-template-rows: minmax(0, 1fr) }  ← TASK-0070
                  └ list-col / detail-col  (row stretch)
      └ commit-bar  (flex-shrink: 0, viewport bottom sticky)
```

**검증**: 1320x900 viewport 에서 admin-shell h=900 (viewport 와 일치), admin-column h=900, commit-bar bottom=900 (viewport bottom 정확히 sticky), gridTemplateRows="900px" (1fr 의 computed 값). Screenshot `/tmp/admin-dashboard-fixed.png` — sidebar (brand → 탭 → pending footer) 가 viewport 전체 height 차지 + admin-column (topbar → dashboard content + 자연 빈 영역 → commit-bar 가 viewport bottom). 회색 빈 영역 사라짐. 작업 화면 (`/`) 도 동일 fix 자연 적용. cache-bust `v=20260518-shell-grid-rows` (admin.html + index.html 양쪽).

본 cycle 이 TASK-0066 (ChatGPT 패턴 layout) 부터 시작된 layout 재구조화의 최종 stretch fix. cascade 완성 후 회귀 없이 안정.

---

**2026-05-18 TASK-0070 완료 — admin list-detail grid row hotfix (TASK-0069 잔여 회귀)** (CHG-20260518-0007, REV-20260518-0007, REQ-20260518-0008, Minor §12.3 — CSS 1 줄 hotfix, RBAC / endpoint / 데이터 / JS 무변경).

**배경**: 사용자 2 차 screenshot 보고. TASK-0069 의 `.admin-workspace { flex: 1 1 auto }` fix 이후에도 `역할` / `제품` 등 항목이 적은 pane 의 큰 viewport (height 800+) 에서 list-col / detail-col box 가 viewport 의 일부만 차지하고 그 아래 회색 빈 영역 잔존. 항목 많은 `계정` (26 row) 이나 좁은 화면에선 row content 가 자연 채워 노출 안 됨 — 1 차 검증 (720 viewport) 에서 놓침.

**원인**: `.admin-list-detail { display: grid; grid-template-columns: ...; align-items: stretch }` 의 `grid-template-rows` 미정의 → default `auto` → row height = content. `align-items: stretch` 는 row 내부 column 분배만 — row 자체 height 결정 X. flex grow chain (admin-column → workspace → pane → list-detail) 의 끝지점이라 fix 가 cascade 의 마지막 단계.

**Fix**: `.admin-list-detail` 에 `grid-template-rows: minmax(0, 1fr)` 1 줄 추가. `minmax(0, ...)` 으로 자식 min-content 무시 — 자식의 `min-height: 0` 와 정합. 다른 속성 무변경.

**검증**: 큰 viewport (1320x900) 에서 `제품` pane (3 items) — `listDetail h=682`, `listCol h=682`, `detailCol h=682` (이전엔 약 200 정도만), `cbar y=839 / bottom=900` (viewport bottom sticky). screenshot `/tmp/admin-products-fixed.png` — box 가 commit-bar 까지 stretch + 회색 빈 영역 사라짐. 다른 pane 도 동일 fix 자연 적용 (`.admin-list-detail` 공통 rule). cache-bust `v=20260518-admin-list-rows`.

검증 viewport 다양성 부족이 회귀 1 cycle 연장한 점 기록 (REV-20260518-0007). 후속 cycle 검증 시 720 / 900 / 1080 / mobile (480) 등 multiple viewport snapshot 으로 stretch chain 종단 확인 권장.

---

**2026-05-18 TASK-0069 완료 — admin workspace flex hotfix (TASK-0068 회귀 차단)** (CHG-20260518-0006, REV-20260518-0006, REQ-20260518-0007, Minor §12.3 — CSS 1 줄 hotfix, RBAC / endpoint / 데이터 / JS 무변경).

**배경**: 사용자 screenshot 보고. admin `역할 관리` (및 다른 list-detail pane) 에서 commit-bar 가 workspace content 바로 아래에 좁게 위치하고 그 아래로 큰 회색 빈 영역이 admin-column 의 bottom 까지 노출. 원인: TASK-0068 에서 commit-bar 를 admin-shell grid (3rd row) → admin-column flex column item 으로 이전한 후 `.admin-workspace` 의 `flex: 1` 명시 누락. flex column 안에서 workspace 가 자기 content 만큼만 차지 → 남은 공간 노출 + commit-bar 가 sticky bottom 효과 상실.

**Fix**: `.admin-workspace` 에 `flex: 1 1 auto` 1 줄 추가. 다른 속성 (overflow / padding / min-* 0 / display flex column) 무변경. `.admin-pane.is-active { flex: 1 1 auto }` 가 의미를 가지려면 부모 workspace 가 stretch 되어야 함 — cascade 출발점에 flex grow.

**검증**: `SKIP_INIT=1 make web` 재배포 OK. DOM (browser headless `/admin` → 역할 tab): `wsHeight=607, wsBottom=659, cbarTop=659, cbarBottom=720, colHeight=720` → `workspaceTouchesCommitBar=true` (둘 사이 빈 공간 없음) + `commitBarAtBottom=true` (commit-bar 가 column bottom 에 정확히 위치). screenshot `/tmp/admin-roles-fixed.png` — list-detail 이 workspace 의 남은 height 전부 차지 + commit-bar viewport bottom sticky + 회색 빈 영역 사라짐. cache-bust `v=20260518-admin-workspace-flex`.

후속 검토 (REV-20260518-0006 Risks): dashboard pane 의 scroll 동작 (overflow-y: auto) 정상 여부는 사용자 직접 확인 권장 — 단일 rule 변경이라 자연 적용되지만 dashboard 전용 시각 검증 별도.

---

**2026-05-18 TASK-0068 완료 — 관리 콘솔 layout 정합 (ChatGPT 패턴 통일) + 새로고침/로그아웃 버튼 제거** (CHG-20260518-0005, REV-20260518-0005, REQ-20260518-0006, Minor §12.3 — admin layout 정합 + 미사용 UI 정리. backend / endpoint / RBAC / 데이터 영역 무변경).

**배경**: TASK-0066 / 0067 follow-up — 사용자 명시. 작업 화면을 ChatGPT 패턴으로 재구조화한 후 관리 콘솔도 같은 layout 으로 통일. 사용자 직접 테스트에서 `새로고침` / `로그아웃` 버튼이 거의 사용 안 되는 것으로 확인 → 제거.

**변경**: (1) `.admin-shell` grid 가 `grid-template-rows: topbar-h | 1fr | auto` → `grid-template-columns: 220px minmax(0, 1fr)` 으로 단순화 (작업 화면 `.app-shell` 과 동일 패턴). `.admin-body` wrapper 폐기. (2) `.admin-sidebar` 의 첫 영역에 `.sidebar-brand` (작업 화면과 동일 brand "MA MySQL AI") 추가. 기존 admin brand "관리 콘솔" 은 페이지 컨텍스트라 topbar 의 `.chat-title` 로 이전 + subtitle "계정 · 역할 · 제품 · 시스템 프롬프트 운영" 동봉. (3) 신규 `.admin-column` (flex column) — sidebar 옆 영역. 안에 topbar (좌측 정렬 제목 + `#backToAppBtn` 우측) → workspace → commit-bar 순서로 flex 배치. (4) `#refreshAdminBtn` / `#adminLogoutBtn` element 제거 + admin.js click handler 제거. `#backToAppBtn` 만 유지. (5) `.admin-sidebar` padding 을 child 들 (sidebar-brand / admin-tabs / sidebar-foot) 로 분배. (6) 반응형 mobile `.admin-shell { grid-template-columns: 1fr }` 정렬.

**검증**: `node --check admin.js` PASS, `SKIP_INIT=1 make web` 재배포 OK. Browser headless `/admin`: `refreshBtnPresent=false`, `logoutBtnPresent=false`, `backBtnPresent=true`, `brandInSidebar=true`, `adminColumnPresent=true`, `oldAdminBodyPresent=false`, `topbarHeight=52`, `topbarInfoText="관리 콘솔 ... 시스템 프롬프트 운영"`, `gridCols="220px 1060px"`. Screenshot `/tmp/admin-merged.png` — 좌측 admin-sidebar (brand + 대시보드 (active) + 계정 카테고리 + 제품 카테고리 + pending 변경 footer) + 우측 admin-column (topbar 좌측 정렬 "관리 콘솔" + 부제 + 우측 끝 "작업 화면" 버튼 / Overview metric cards / commit bar) — 작업 화면과 100% 일관된 ChatGPT 패턴. cache-bust `v=20260518-admin-layout` (admin.html / admin.js).

후속 cycle 권장: 작업 화면 프로필 drawer 의 "로그아웃" 이 admin 페이지에서도 접근 가능한지 확인 (현재 admin 에는 drawer 없음 — 로그아웃 path 가 작업 화면 경유). dead CSS (`.topbar-brand`, `.product-chip-*`, `.admin-body`) 일괄 정리 별 cycle.

---

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
- 2026-05-19 (TASK-0080, REQ-20260519-0008, Minor §12.3 — `_collect_matched_excerpts` AgentMemoryMessages + AgentCoreMessages UNION): TASK-0077 followup. 사용자 직접 확인 — core-only conv 의 snippet 부재 회귀 노출. backend `_collect_matched_excerpts` 의 SELECT 를 두 table UNION ALL + `ROW_NUMBER OVER (PARTITION BY cid ORDER BY msg_id DESC)` 으로 conv 별 더 최근 매칭 1건 선택. `COLLATE utf8mb4_unicode_ci` 통일. RBAC / audit / endpoint contract / line-based clip 로직 무변경. cache-bust `v=20260519-snippet-line` → `v=20260519-chat-pane-flex` (TASK-0079 와 묶음).
- 2026-05-19 (TASK-0079, REQ-20260519-0007, Minor §12.3 — `.chat-pane` flex layout hotfix, TASK-0066 cascade 잔여 결함): 사용자 screenshot 보고 — 짧은 대화 + 큰 viewport 조합에서 composer 아래 viewport bottom 까지 회색 빈 영역 노출. 원인: `.chat-column` flex container 안 `.chat-pane` 의 flex 미정의 → 자식 max-content 만 차지 → `.messages-wrap (flex: 1)` 의 grow chain 끊김. TASK-0066 ChatGPT 패턴 layout 재구조화 시점 누락 + TASK-0068~0071 cascade hotfix chain 이 admin 영역만 다뤘음. Fix: `.chat-pane` 에 `flex: 1 1 auto; min-height: 0` 추가 (CSS 2 line). backend / RBAC / endpoint / JS 무변경. cache-bust `v=20260519-chat-pane-flex` (TASK-0080 과 묶음). make web 재배포 OK (29 초 후 healthy).
- 2026-05-19 (TASK-0078, REQ-20260519-0006, Minor §12.3 — search modal 3 항목 추가 hotfix of TASK-0077): 사용자 직접 테스트 보고 3 항목. (1) **mouseup race 보강** — TASK-0077 의 mousedownOnOverlay-only flag 부족. modal 바깥 mousedown → modal 안 mouseup 시 click target = overlay 가 되어 close 됨. Fix: `state.searchModal.mouseupOnOverlay` 도 추가 추적, click 시 mousedown + mouseup + target 3 개 모두 overlay 일 때만 close (양 끝점 모두 backdrop 인 의도적 click 만). (2) **preset 텍스트 "부터" 제거** — "1시간 전부터" → "1시간 전" 5 버튼 모두. (3) **snippet 본문 발췌 line-based clip** — `_collect_matched_excerpts` 가 매칭 위치의 line 경계 (`\n` 직후 ~ `\n` 직전) 를 찾아 line 전체 반환. line ≤ 220 char 면 그대로, 초과 시 매칭 위치 ±60 char clip + "…". `.search-snippet` CSS line-clamp 2 → 3 + line-height 1.45 + max-height 4.6em. cache-bust `v=20260519-search-presets` → `v=20260519-snippet-line`. py_compile + node --check PASS, make web 24 초 후 healthy.
- 2026-05-19 (TASK-0077, REQ-20260519-0005, Minor §12.3 — search modal 5 항목 hotfix bundle of TASK-0072/0076): 사용자 직접 테스트 보고 5 항목 모두 반영. (1) min char 3→2 (backend `_normalize_search_query` + frontend gate/placeholder/highlight). (2) 소유자 facet DOM + JS 전부 제거 (효용성 낮음 — 사용자 결정). backend `owner_id` 파라미터는 호환 위해 유지. (3) 기간 popover 에 preset 5 종 (1시간/1일/1주/1개월/1년 전부터 지금까지). click 시 from/to 자동 + popover input sync + 즉시 적용. (4) mouseup race fix — `state.searchModal.mousedownOnOverlay` flag 로 click = mousedown + mouseup 둘 다 overlay 일 때만 close. modal 안 text drag 후 backdrop mouseup 시 close 안 됨. (5) snippet 본문 excerpt — backend `_collect_matched_excerpts` 신설 (MySQL 8.0 `ROW_NUMBER() OVER (PARTITION BY ConversationId ORDER BY Id DESC)` 으로 conv 별 최근 매칭 message content 의 매칭 위치 ±40 char clip + "…"). endpoint 가 `matched_excerpts: {conv_id: "..."}` 응답에 첨부. frontend `renderSearchModalResults` 가 snippet 영역에 excerpt + highlight. TASK-0072 의 audit/RBAC 정책 무변경 (snippet opt-in chip + .any 한정 + WebAccountActivity audit). cache-bust `v=20260519-search-facets` → `v=20260519-search-presets`. py_compile + node --check PASS, make web 재배포 OK (8초 후 healthy).
- 2026-05-19 (TASK-0076, REQ-20260519-0004, Minor §12.3 — search modal UX 3 결함 hotfix bundle of TASK-0072): 사용자 직접 테스트 보고 3 항목 — facet click 무동작 / 키보드 ↑↓ scroll 미동작 / 매칭 message bubble jump 미동작. frontend only fix (backend / RBAC / audit / endpoint 무변경). (1) 제품 facet DOM 제거 (사용자 결정: 대화 중 product 변경 가능 → 필터 부적합). 소유자 facet popover (`/api/admin/accounts` 1 회 캐시, .any 한정, "전체" + 각 계정 role label). 기간 facet popover (`<input type="date">` from/to + 적용/지우기). (2) ArrowDown/Up 시 active row 의 `scrollIntoView({block:'nearest'})`. Enter 도 click 과 동일 jump 적용. (3) result click / Enter 시 `state.searchModal.pendingJumpQuery/Conv` 저장 → `selectConversation` 끝 (loadHistory + renderMessages 직후) `_jumpToSearchMatchedMessage()` 호출 → `messageLogEl .message` 의 textContent lowercase compare → 첫 매칭 row `scrollIntoView({behavior:'smooth', block:'center'})` + `.is-search-matched` class 1.8 s pulse animation. cache-bust `v=20260519-modal-contrast` → `v=20260519-search-facets` (styles.css + app.js). make web 재배포 후 healthy. node --check PASS.
- 2026-05-19 (TASK-0074, REQ-20260519-0002, Minor §12.3 — search modal 색상 가독성 hotfix of TASK-0072): site theme = light (`--bg #f4f4f5` / `--surface #ffffff` / `--text #18181b`) 환경에서 TASK-0072 modal 의 미정의 var fallback (dark hardcode `#1f2429`) + site 의 검은 text inherit 충돌 → 어두운 배경 위 검은 텍스트 = 가독성 0 (사용자 screenshot 보고 "사용자가 이용할 수 없을 정도의 색상 구성"). Fix: modal CSS 100여 줄을 site 의 기존 토큰 (`--surface` / `--text` / `--border` / `--text-muted` / `--primary` / `--primary-soft` / `--bg`) 으로 일관 적용. backdrop dark overlay (`rgba(15,23,42,0.48)`) 는 modal pop 강조 유지. highlight bg `#fde68a` + `font-weight: 600` (light theme 위 WCAG AA 충분). owner badge "내" = `--primary-soft` bg + `--primary` border + `--primary-dark` text triple. result row hover/active = `--primary-soft`. cache-bust `v=20260518-conv-search` → `v=20260519-modal-contrast` (styles.css + app.js 양쪽 동일). backend / RBAC / audit / endpoint 무변경. TASK-0073 Phase A0 (WebAuditEvents) 와 file overlap 없음 (styles.css + index.html cache-bust vs app.py DDL + docs). make web 재배포 12 초 후 healthy.
- 2026-05-18 (TASK-0072, REQ-20260518-0010, **Critical** §12.3 — 타 계정 대화 검색·필터 + WebAccountActivity audit log)
  - **Phase A0 (audit infra)**: `WebAccountActivity` (`Id, AccountId, Action, TargetOwnerId, QueryHash CHAR(64), MatchedCount, CreatedAt`) + `_log_search_activity()` helper. SHA-256 hash, 평문 query 저장 금지. slow + fast path 양쪽 보장.
  - **Phase A1 (`_list_conversations` 확장)**: 3 sub-spec — (a) SQL composition order: `.own` owner_id WHERE 가 q 보다 항상 먼저 AND; (b) `hidden_ids` SQL push (`NOT IN`); (c) Python re-sort 삭제 (SQL `ORDER BY` 단일화). 새 파라미터 6: `q`/`owner_id`/`product_id`/`date_from`/`date_to`/`cursor`. `LIKE %s ESCAPE '!'` + `!`/`%`/`_` 3 char escape. min 3 char raw input. `WebAccounts.DeletedAt IS NULL` 필터. collation audit (process 당 1 회).
  - **Phase A2 (`/api/conversations` search mode)**: search params 1 개 이상이면 search mode 분기. body-search 시 `_search_rate_limit_check` 10 req/min (429), `SET SESSION max_execution_time=3000ms`, `_log_search_activity` audit INSERT. cursor pagination 응답 (`next_cursor`). q < 3 char / post-escape 0 → 400. byte-equal owner_id response.
  - **Phase B (test)**: `tests/test_search_rbac.py` 6 시나리오 (cross-account leak / byte-equal owner_id / cursor disjoint / q<3 → 400 / rate limit 11 → 429). 실행은 Phase E 컨테이너 가동 + admin/operator 비밀번호 필요.
  - **Phase C (frontend Spotlight modal)**: 사용자 변형 채택 — 사이드바 "+ 새 대화" 우측 같은 높이에 돋보기 icon (Cmd/Ctrl+K). modal: input(min 3 char + 300ms 디바운스) + 4 facet chip (owner/product/date/snippet, `.any` 만 owner+snippet) + result list (highlight + snippet opt-in) + "더 보기" cursor pagination + a11y (Esc/ArrowUp/Down/Enter, focus 복원). cache-bust `v=20260518-conv-search`.
  - **Phase D**: FUNCTION (REQ-20260518-0010 + AC-0151~AC-0158, 8 개) + MODIFY (CHG-20260518-0010) + REVIEW (REV-20260518-0010, outside voice 3 verdict + D1~D3 + 5 결정 + 6 risk) + TEST (§2 case 추가) + SECURITY §8 + STATUS row.
  - **Phase E**: `make web` + browser smoke + `verify-completion --pre-commit` + commit 사용자 확인 후.
  - **outside voice 3 verdict (REVIEW.md REV-20260518-0010)**: security FIX-FIRST → 4 must-fix 흡수, adversarial Blocker → 3 sub-spec + 6 risk 흡수, ux NEEDS-TWEAK → Spotlight modal 패턴 채택. memory 정책 `feedback_outside_voice_for_rbac` 강제 적용.
  - **D1/D2/D3 결정**: D1 A (LIKE + 안전망; FULLTEXT 별 cycle — 한국어 ngram + Critical migration interleave 회피), D2 A (snippet 항상 OFF + opt-in), D3 B (cursor `updated_at DESC, conversation_id DESC`).
  - **검증 통과**: `python3 -m py_compile app.py` / `python3 -m py_compile test_search_rbac.py` / `node --check app.js` 모두 PASS.
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

## TASK-0256 — assistant 답변 diff 블록 (2026-06-15)

### 변경
- 프롬프트(feature-0002): `agent_core.SYSTEM_PROMPT` OUTPUT 섹션 뒤 "SHOWING CHANGES — USE A MARKDOWN DIFF BLOCK" — 첨부/쿼리 리뷰·편집 시 변경을 ```diff 블록으로 제시.
- 렌더(feature-0003): `enhanceDiffBlocks`(app.js/share.js) — marked.parse→enhance→DOMPurify.sanitize. `language-diff` 블록을 라인별 `<span class="diff-line ...">` 재구성. styles.css/share.css 팔레트. 캐시버스터 bump.

### 라이브 배포 절차 (deploy_scope: included)
1. web + ask-worker 재빌드/재기동:
   `sudo docker compose build web ask-worker && sudo docker compose up -d --no-deps web ask-worker`
2. 라이브 WebSystemPrompts global row 갱신 (멱등·백업). 컨테이너 내 1회 실행:
   ```
   sudo docker compose exec -T web python - <<'PY'
   import app, agent_core
   M = "## SHOWING CHANGES — USE A MARKDOWN DIFF BLOCK"
   sec = agent_core.SYSTEM_PROMPT[agent_core.SYSTEM_PROMPT.find(M):].rstrip()
   c = app._open_memory_connection()
   row = app._load_system_prompt(c, scope="global")
   old = row["content"] if row else ""
   open("/tmp/task0256_global_prompt_backup.txt","w").write(old)
   if row and M in old:
       print("ALREADY-APPLIED")
   elif row:
       app._upsert_system_prompt(c, scope="global", content=old.rstrip()+"\n\n"+sec+"\n"); c.commit(); print("APPENDED")
   else:
       app._upsert_system_prompt(c, scope="global", content=agent_core.SYSTEM_PROMPT); c.commit(); print("SEEDED-FULL")
   PY
   ```
   - 백업: 컨테이너 `/tmp/task0256_global_prompt_backup.txt` (롤백 시 동일 헬퍼로 복원).
   - 멱등: 마커 존재 시 무변경. 기존 admin 커스터마이즈 보존(append-only).
3. PB-0008 Windows-browser 시각검증: 첨부 SQL 리뷰 요청 → 답변의 ```diff 블록이 +초록/-빨강 라인으로 구분되는지 (메인 채팅 + 공유 뷰).
