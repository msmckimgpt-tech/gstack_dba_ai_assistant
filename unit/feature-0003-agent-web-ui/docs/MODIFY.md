---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---


# Modify Log

> 이전 기록(408건): [MODIFY-archive-20260711T115053.md](./_archive/MODIFY-archive-20260711T115053.md)

## CHG-20260715T120000-graph-ctxmenu-band-priority-postverify (TASK-20260715T114608-graph-ctxmenu-band-priority POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-15. 코드/자산 무변경 — test-runs.d fragment POST-DEPLOY 섹션 '이연'→실측 PASS + TASK 체크리스트 완료. 기능 배포 PR #815→main 6a950a20 선행 완료.
- 라이브 실측(win-browser Chrome 150, 6a950a20): 킹스레이드·미분류 CAT 밴드에서 클러스터 박스(dbAuth·dbTest) 우클릭 → **카테고리 메뉴**(band-wins) / 펼친 테이블 노드 → **그 테이블 메뉴**(흡수 안 함) / 좌클릭 → **클러스터 펼치기 정상**. 사용자 결정("밴드 우선") 충족. 증거 scratchpad/evidence-bandwins-box-category.png.
- Cross-ref: CHG-20260715T114608-graph-ctxmenu-band-priority(기능) · REV-20260715T120000-graph-ctxmenu-band-priority-postverify · test-runs.d/20260715T114608-graph-ctxmenu-band-priority.md POST-DEPLOY Run.

## CHG-20260715T114608-graph-ctxmenu-band-priority (TASK-20260715T114608-graph-ctxmenu-band-priority — 제품 카테고리 밴드 우클릭 band-wins, Major §12.3 frontend-only)
- Date: 2026-07-15. 제품 카테고리 밴드 안의 스키마 클러스터 박스가 밴드를 시각적으로 채워, 밴드 우클릭이 스키마 메뉴로 새는 UX 겹침 → 사용자 결정 "밴드 우선"으로 우클릭 시 밴드 귀속.
- `static/graph/graph-renderer-pixi.js`:
  - 신규 `PixiGraphAdapter._pickContext(mx,my)` — `_pick()` 이 combo 또는 schema-card 를 반환하고 그 지점을 덮는 cat-bg 가 있으면 cat-bg(카테고리 밴드)로 승격; 아니면 `_pick()` 그대로.
  - `up()` 우클릭(button===2) 경로만 `_pickContext` 사용(kind=chit.__combo?combo:node 로 emit). 좌클릭/더블클릭/드래그는 `_pick` 불변.
- band-wins 범위: 밴드 멤버 클러스터(combo/schema-card)만 승격. 테이블·컬럼 노드·CATH/CATX/GX/GH/GB·밴드 밖 standalone 클러스터는 불변.
- 비변경: 좌클릭(펼치기/상세)·드래그(노드/combo/밴드헤더)·dispatch·메뉴 함수·시각 z·백엔드/RBAC/스키마 0.
- 검증: `node --check` PASS · `tests/headless/test_pixi_adapter.js` T22 회귀 6종(ALL PASS 68/0) · §18.8 적대 패널. POST-DEPLOY PB-0008 라이브 잔여(visual_verification_scope: always).
- Cross-ref: TASK/REVIEW-20260715T114608-graph-ctxmenu-band-priority · test-runs.d/20260715T114608-graph-ctxmenu-band-priority.md · 선행 CHG-20260715T102901-graph-ctxmenu-hittest(WYSIWYG hit-test 층서).

## CHG-20260715T110000-graph-ctxmenu-hittest-postverify (TASK-20260715T102901-graph-ctxmenu-hittest POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-15. 코드/자산 무변경 — test-runs.d fragment 의 POST-DEPLOY 섹션을 '이연' 계획→실측 PASS 로 갱신 + TASK 체크리스트 완료. 기능 배포는 PR #808→main 6ec5da4b(이후 병렬 8098aee1 재배포, fix 포함)로 선행 완료.
- 라이브 실측 요지(win-browser 실 Windows Chrome/150, https://localhost/admin): 제품-매핑 데이터소스(mysql-kr-an2-auth, "킹스레이드 - 국내 QA") 스키마그래프에 CAT 밴드 2개 렌더 → **스키마 클러스터(dbAuth·dbTest) 우클릭 = "스키마" 메뉴**(이전 결함 해소) · **밴드 헤더·tint 여백 우클릭 = "카테고리" 메뉴** · 세 증상 전부 해소(WYSIWYG). 증거 scratchpad/evidence-cluster-schema-menu.png.
- Cross-ref: CHG-20260715T102901-graph-ctxmenu-hittest(기능) · REV-20260715T110000-graph-ctxmenu-hittest-postverify · test-runs.d/20260715T102901-graph-ctxmenu-hittest.md POST-DEPLOY Run.

## CHG-20260715T102901-graph-ctxmenu-hittest (TASK-20260715T102901-graph-ctxmenu-hittest — 그래프 우클릭 메뉴 오라우팅 hit-test 층서 수정, Major §12.3 frontend-only)
- Date: 2026-07-15. 그래프 뷰 우클릭 메뉴가 대상과 뒤바뀌는 결함(스키마 클러스터→카테고리 메뉴 / 제품 카테고리 밴드→스키마 메뉴) 수정. 근본: `_pick` 이 node 우선 반환→CAT 밴드 배경(node, `data.kind:"cat-bg"`, z=-1, 멤버 클러스터 전체 덮음)이 스키마 클러스터 빈배경(combo, 폴백 대상) 우클릭을 가로챔.
- `static/graph/graph-renderer-pixi.js`:
  - `PixiAdapterPure.hitTest(mx,my,hg,nodes,filter)` — optional `filter(n)` 인자 추가(tier 분리, `filter(n)→false` 노드 skip).
  - `PixiGraphAdapter._pick()` 3-tier 재작성: ① `hitTest`(cat-bg 제외) → ② `hitTestCombo`(스키마 클러스터) → ③ `hitTest`(cat-bg 만). `_isCatBg(n)` 헬퍼 신설.
- 층서 결과: 구체 요소 > 스키마 클러스터 배경 > 카테고리 밴드 배경. 시각 z(-1) 불변 — hit-test 우선순위만 교정.
- 비변경: dispatch(graph-core node:contextmenu)·메뉴 함수·노드 방출·좌클릭·드래그 경로·백엔드/RBAC/스키마 0.
- 검증: `node --check` PASS · `tests/headless/test_pixi_adapter.js` T21 회귀 6종 추가(ALL PASS 62/0) · §18.8 적대 패널. POST-DEPLOY PB-0008 라이브 잔여(visual_verification_scope: always).
- Cross-ref: TASK/REVIEW-20260715T102901-graph-ctxmenu-hittest · test-runs.d/20260715T102901-graph-ctxmenu-hittest.md · 선행 CHG-20260714T180125-graph-ctxmenu-category(dispatch 라우팅).

## CHG-20260714T183808-graph-ctxmenu-postverify (TASK-20260714T180125-graph-ctxmenu-category POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-14. 코드/자산 무변경 — TASK.md 체크리스트 완료(verify/PR#794/POST-DEPLOY) + test-runs.d fragment 에 POST-DEPLOY 라이브 검증 Run append. 기능 배포는 PR #794→main 154fb916, `deploy-web`(deploy_scope: included, web-a/b soak PASS) 로 선행 완료(본 커밋은 그 사후 기록).
- 라이브 실측 요지(win-browser 실 Windows Chrome/150, https://localhost/admin): 배포 전달(서빙 baked 자산에 `_metaGraphCtxForCategory` 반영)·라이브 도달성(그래프 렌더·범례 '제품 카테고리 밴드')·**수정 핸들러(node:contextmenu CAT 분기 graph-core L2086) 우클릭 dispatch 파이프라인 라이브 실증** PASS. 리터럴 CAT 밴드 위 '카테고리' 메뉴 육안 = DEFERRED(도달 scope 전부 미분류→밴드 미방출, 제품-매핑 scope 필요) — 사용자 1-probe 권장.
- postverify 재확인(main 1f705a9e): web-a·web-b `GIT_COMMIT=1f705a9e`(154fb916 포함) + baked `_metaGraphCtxForCategory` 반영 실측 — 수정 정상 서빙 중.
- Cross-ref: CHG-20260714T180125-graph-ctxmenu-category(기능) · REV-20260714T183808-graph-ctxmenu-postverify · test-runs.d/20260714T180125-graph-ctxmenu-category.md POST-DEPLOY Run.

## CHG-20260714T180125-graph-ctxmenu-category (TASK-20260714T180125-graph-ctxmenu-category — 그래프 카테고리 밴드 우클릭 전용 메뉴, Minor §12.3 frontend-only additive)
- Date: 2026-07-14. 그래프 뷰 '제품 카테고리 밴드'(CAT:/CATH:/CATX:) 우클릭을 전용 카테고리 메뉴로 라우팅 — 이전 `_metaGraphCtxHide()` stopgap(및 그 이전 배포본의 combo fall-through "스키마 클러스터 메뉴" 오노출) 대체.
- `static/graph/graph-ctxmenu.js`: +`_metaGraphCtxForCategory(catKey, x, y)`(헤더 배지 + 카테고리 상세 + 밴드 접기/펼치기 + 카테고리명 복사) + export.
- `static/graph/graph-core.js`: `node:contextmenu` CAT 분기 `_metaGraphCtxHide()` → `_metaGraphCtxForCategory(String(id).replace(/^CAT(H|X)?:/, ""), p.x, p.y)` + import.
- 검증: `node --check`(module) 양 파일 PASS · dispatch/의존심볼 grep 정합. POST-DEPLOY PB-0008 라이브 잔여(visual_verification_scope: always).

## CHG-20260714T080000-account-subtabs-postverify (TASK-20260714T074417-account-subtabs POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-14. 코드/자산 무변경 — TASK.md 체크리스트 완료 + TEST.md POST-DEPLOY 라이브 PASS append + REVIEW postverify. 배포 PR #788→main 53e55bfe, `deploy-web --web-only`(1차 soak false-positive 롤백→재배포 PASS).
- 라이브 실측 요지(win-browser 실 Windows Chrome, 라이브 53e55bfe): 하위탭 4개·기본 account·각 클릭 시 정확히 1 subpane(알림 체크박스/UI select/사용량 차트/2FA·로그아웃) 노출 assertion 전항목 PASS + 서빙 자산 심볼 확인 + 세그먼트 하위탭 바 시각 렌더(스크린샷).
- 운영 노트: 1차 배포가 post-cutover soak 에서 edge /healthz 순간 비정상(mysql/pg 정상)으로 last-good 자동 롤백 — 정적 자산 변경이라 /healthz 무관, cold-start+insight-worker 동시부하 transient(LRN deploy-web-healthz-concurrent-resync 패턴). 동일 이미지 재배포 시 soak PASS 로 false-positive 확증.
- Cross-ref: CHG-20260714T074417-account-subtabs(기능) · REV-20260714T080000-account-subtabs-postverify · TEST Run POST-DEPLOY.

## CHG-20260714T074417-account-subtabs (TASK-20260714T074417-account-subtabs — 프로필 '계정' 탭 하위 세분화, Minor §12.3, frontend-only)
- Date: 2026-07-14. `/_template:entry` arg-given. 스키마/마이그/RBAC/엔드포인트/서버 계약 0 — DOM 재배치 + 표현계층 sub-nav.
- 배경: anim-effect-pref 로 '화면 효과'가 추가되며 '계정' 탭 7섹션(활동·알림·화면효과·사용내역·비번·2FA·로그아웃)이 한 화면에 누적 → 난잡. 사용자 요청으로 하위 탭 세분화(알림·UI 독립 확정 → 4탭 승인).
- 변경:
  - `static/index.html`: `data-profile-pane="security-and-account"` 를 `.profile-subtabs`(계정/알림/UI/사용 내역 4버튼) + 4× `.profile-subpane`(data-account-subpane) 으로 재구성. 7섹션을 account(활동+비번+2FA+로그아웃)/notifications(알림)/ui(화면효과)/usage(사용내역) 로 이동 — 모든 element id 보존(회귀 0).
  - `static/app.js`: 신규 `switchAccountSubtab(sub)` — `[data-account-subtab]` is-active·aria-selected + `[data-account-subpane]` hidden 토글 + 하위 탭별 lazy 렌더(account→renderProfileTotp / notifications→renderNotifyPrefs / ui→renderMotionPref / usage→loadProfileUsage). `switchProfileTab('security-and-account')` 를 4콘텐츠 일괄 렌더에서 `switchAccountSubtab(state.accountSubtab||'account')` 로 변경(사용량 API 는 usage 탭 진입 시에만 호출 — 효율 개선). `initialize()` 에 `[data-account-subtab]` 클릭 리스너 배선.
  - `static/styles.css`: `.profile-subtabs`(세그먼트 컨테이너)·`.profile-subtab`(pill, is-active 강조)·`.profile-subpane`(세로 스택) — 상단 drawer-tab 언더라인과 시각 구분.
- 검증: `node --check app.js` PASS · 하위탭/subpane 각 4·섹션 id 전부 보존·pane div 균형 32/32. §18.8 적대 서브에이전트 리뷰(REVIEW). POST-DEPLOY PB-0008 라이브 시각검증(TEST §Run 2026-07-14 account-subtabs).
- Cross-ref: TASK-20260714T074417-account-subtabs · REV-20260714T074417-account-subtabs · 선행 anim-effect-pref(CHG-20260714T065503) · ANCHOR 0003 무충돌.

## CHG-20260714T073000-anim-effect-pref-postverify (TASK-20260714T065503-anim-effect-pref POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-14. 코드/자산 무변경 — TASK.md 체크리스트 완료 + TEST.md POST-DEPLOY 라이브 PASS append + REVIEW postverify 엔트리. 배포 PR #786→main f00519dd, `deploy-web --web-only` 무중단 롤링(soak PASS).
- 라이브 실측 요지(https://localhost/ bootstrap_admin, win-browser Chrome): 게이트 로직 런타임 assertion 전항목 PASS(`off→reduced=true`·`on→reduced=false` OS무관·`os→OS일치`·data-motion 반영·`#motionEffectSelect` 옵션3종+hydration·캘린더/검색 `scrollMessagePointIntoCenter` 라우팅) + 서빙 자산 stamp 갱신(b162038f7a10)·심볼 확인 + 프로필 계정 탭 select 시각 렌더(스크린샷). 한계: 검증 머신 reduce-motion off라 육안 모션 시연 불가·로직은 결정적 실증.
- Cross-ref: CHG-20260714T065503-anim-effect-pref(기능) · REV-20260714T073000-anim-effect-pref-postverify · TEST Run(2026-07-14) POST-DEPLOY.

## CHG-20260714T065503-anim-effect-pref (TASK-20260714T065503-anim-effect-pref — 작업 화면 애니메이션 복원 + 인앱 "애니메이션 효과" 설정, Major §12.3, frontend-only)
- Date: 2026-07-14. `/_template:entry` arg-given. 스키마/마이그/RBAC/엔드포인트/서버 계약 0 — 프론트 단독·비파괴.
- 근본원인: 사용자 보고 3종 애니(대화 전환 크로스페이드·point-rail 뱃지 스크롤·캘린더 버튼 스크롤)가 `prefers-reduced-motion: reduce` 매칭 시 통째로 즉시(instant)로 degrade. 코드/배포는 정상(소스 애니 증가·배포 byte-동일). Windows 에서 이 미디어쿼리는 "동작 줄이기"가 아니라 설정>접근성>시각 효과>애니메이션 효과·배터리 절약 모드에 매핑 → 사용자 미인지 상태로 "최근 갑자기" 발동 가능.
- 변경:
  - `static/app.js`: `_prefersReducedMotion()` 을 pref-aware 로 개편 — 신규 `MOTION_PREF_KEY="mad.motionEffect.v1"`(localStorage `os`/`on`/`off`)·`getMotionPref`/`setMotionPref`/`applyMotionPref`(`<html data-motion>` 반영)/`_osPrefersReducedMotion`. `on`=항상 애니(줄임 안 함)·`off`=항상 줄임·`os`=OS 신호(기본, 하위호환). 캘린더 `jumpToHistoryAnchor`·검색 `_jumpToSearchMatchedMessage` 의 네이티브 `scrollIntoView({behavior:"smooth",block:"center"})` → pref-aware `scrollMessagePointIntoCenter`(point-rail 과 동일 EaseOutExpo 경로)로 라우팅 → `on` 이면 OS reduce-motion 에서도 부드럽게 이동. `renderMotionPref()` 신규 + 계정 탭 렌더/change 리스너/`initialize()` 의 `applyMotionPref()` 배선.
  - `static/index.html`: 프로필 드로어 '계정' 탭에 '화면 효과 > 애니메이션 효과' select(`#motionEffectSelect`, 시스템 설정 따름/항상 켬/항상 끔) `profile-section#profileMotionSection` 추가.
  - `static/styles.css`: `.profile-select-row`/`.profile-motion-select` 정합 스타일(toggle-row 시각 정합).
- 검증: `node --check app.js` PASS · 심볼/배선 확인 · 잔여 네이티브 smooth-into-center `scrollIntoView({behavior:"smooth"})` 0건 · `os` 기본값 하위호환(회귀 표면 0). §18.8 적대 서브에이전트 리뷰(REVIEW). POST-DEPLOY PB-0008 라이브 시각검증(TEST §Run 2026-07-14 anim-effect-pref).
- Cross-ref: TASK-20260714T065503-anim-effect-pref · REV-20260714T065503-anim-effect-pref · TEST Run(2026-07-14) anim-effect-pref · ANCHOR 0003 무충돌.

## CHG-20260713T101500-ds-conn-test-postverify (TASK-20260713T094624-ds-conn-test POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-13. 코드/자산 무변경 — test-runs.d/20260713T094624-ds-conn-test.md 에 POST-DEPLOY 라이브 PASS append + TASK.md 체크리스트 완료 + REVIEW postverify 엔트리. 배포 PR #767→main 02a1e585, `make deploy-web` 무중단 롤링(soak PASS).
- 라이브 실측 요지(https://localhost/ bootstrap_admin, win-browser relay Chrome): AC-1 15 DS 배지 전부 `<button.product-dropup-item-ds--test>`·AC-2 클릭→"✓ 연결 성공(11.8ms)" 상단 토스트(top 66px·입력창 비가림)·AC-4 제품 미전환·AC-5 프론트 쿨다운 발화·AC-6 admin 토스트 하단 불변·AC-7 pageerror 0.
- Cross-ref: CHG-20260713T094624-ds-conn-test(기능) · REV-20260713T101500-ds-conn-test-postverify · test-runs.d fragment.

## CHG-20260713T094624-ds-conn-test (TASK-20260713T094624-ds-conn-test — 작업화면 제품 드롭업 데이터소스 '연결 테스트' 버튼 + 상단 단발성 토스트, Major §12.3)
- Date: 2026-07-13. `/_template:entry` arg-given. 스키마/마이그/신규 RBAC/신규 엔드포인트 0.
- 변경:
  - `static/app.js`: `buildProductDropupItem` — 데이터소스 배지를 `_dsTestable = !viewOnly && canOpenAdminConsole()` 게이트로 실제 `<button>`('연결 테스트') 렌더(`_makeDsBadge`, 무권한/열람전용은 기존 display-only span). **행 요소 `<button>`→`<div role=menuitem>` + `tabIndex=0` + click/keydown(Enter/Space) 선택 복원**(중첩 `<button>` 회피). 신규 `runDatasourceConnTest(keys, badgeEl)` — 프론트 쿨다운(`PRODUCT_DS_TEST_COOLDOWN_MS=4000`·`_dsTestLastAt` `.has()` sentinel)·진행 중 `disabled`·단일/멀티(순차+요약)·403(apiFetch 위임)/429(중립)/실패(에러) 상단 토스트.
  - `static/styles.css`: `#toast` 상단 앵커(`top: calc(var(--topbar-h,52px)+14px)`·`bottom:auto`·`max-width: min(460px, calc(100vw-32px))`·`transition` 에 background 추가·`#toast.is-visible`) — 작업화면 전 토스트 상단화(admin `#adminToast` 하단 불변, id 스코프). `button.product-dropup-item-ds--test`(font reset·min-height 24px·at-rest 테두리·hover 틴트·:focus-visible·:disabled).
  - `routers/admin_datasources.py`: import `os`/`time`. 모듈 상태 `_DS_TEST_COOLDOWN_SEC`(env `AGENT_DS_TEST_COOLDOWN_SEC` 기본 3, try/except 폴백)·`_ds_test_last_at`·`_DS_TEST_LRU_CAP=4096`. 신규 `_ds_test_throttle_check(account_id, key)`(per-(account,key) 쿨다운·LRU prune·throttled 반환 `max(1.0, round(ms))`). `admin_test_datasource`: resolve/SSRF 이후·probe 직전에 throttle 게이트 — 미경과 시 probe 없이 **429**(body: key/ok/elapsed_ms/error/status/throttled/retry_after_ms(int)).
  - `static/admin.js`: `_probeDatasourceConn` — `const _prev` 함수 스코프 캡처 + 429 catch 시 'down' 대신 직전 확정 상태 유지. 상세 `_dsRenderDetail` '연결 테스트' + 제품바인딩 ⋯ '연결 테스트' catch 에 429=중립 토스트 분기.
  - `tests/verify_profile_icon_consistency.mjs`: 하네스에 `canOpenAdminConsole(){return false;}` 스텁(display-only 경로 유지). `tests/test_datasource_test_nonblocking.py`: autouse `_reset_ds_test_throttle` fixture + throttle 계약 테스트 2건(T4 반복→429·독립 account/key, T5 404 무-throttle).
- 검증: `node --check`(app.js·admin.js module)·`py_compile`·CSS 1780/1780·타깃 6/6·**전체 pytest 1902 passed / 2 skipped / 0 failed**. §18.8 3렌즈 패널 SHIP-WITH-FIXES→반영 후 SHIP.
- Cross-ref: REV-20260713T094624-ds-conn-test · REPORT §1 · TASK-20260713T094624-ds-conn-test · TEST test-runs.d/20260713T094624-ds-conn-test.md · FUNCTION §13.

## CHG-20260713T061500-attach-user-version-postverify (TASK-20260713T053423-attach-user-version POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-13. 코드/자산 무변경 — TEST.md §4 Windows-browser Run 을 "배포 후 잔여" → **POST-DEPLOY 라이브 PASS** 로 갱신 + TASK.md 체크리스트 완료. 배포: PR #751→main 7f1ed748, web-a/web-b 무중단 롤링 + ask-worker 재빌드(agent_core 변경 baked).
- 검증 요지(https://localhost/, bootstrap_admin, win-browser relay Chrome/150): 라이브 e2e — v1(490)→v2(491, root=490 편입)→동일 재업로드(491 reused)→버전 체인 2개(v1 superseded/v2 최신)→목록 최신만(version_count=2); **assistant 가 v1→v2 diff(SELECT 1→2·-- changed 추가) 정확 인지**(new_attachment_ids 포함 시), 미포함 턴엔 정직 "비교 불가"(환각 0). Evidence artifacts/shared/win-browser-shots-attach-user-version/01_version_badge_and_assistant_diff.png.
- Cross-ref: CHG-20260713T053423-attach-user-version(기능) · TEST.md §4 2026-07-13 Run · REV-20260713T053423-attach-user-version.

## CHG-20260713T053423-attach-user-version (TASK-20260713T053423-attach-user-version — 사용자 재업로드 첨부 버전 관리, Major §12.3, cross-cut feature-0002)
- 변경:
  - `routers/_conv_store.py`: 신규 `_find_latest_same_name_attachment(conn, conversation_id, account_id, filename)`(대화 내 `(ConversationId,AccountId,OriginalFilename)` 최신 비-superseded·비-deleted head 1건 — 버전 체인 편입 판정, MySQL write-consistent)·`_compute_version_diff(prev, new, *, prev_version, new_version, filename, cap_bytes)`(difflib unified diff, size-cap `_ASSISTANT_EDIT_SIZE_CAP_BYTES`, truncated 플래그).
  - `app.py`: p15 rebind 블록에 `_find_latest_same_name_attachment`·`_compute_version_diff` import 추가(app.X 노출).
  - `routers/conversations.py` `upload_conversation_attachment`: sha256 계산 직후 prior head 조회 → **해시 일치=기존 최신 버전 재사용**(INSERT/MinIO put skip, 기존 payload + `reused_existing_version:true` 반환) / **불일치=새 버전**(root=prior.root||prior.Id·`VersionNumber=MAX+1`·텍스트계열 diff 를 `MetaJson.version_diff` 저장). INSERT 를 버전 컬럼(`MetaJson,RootAttachmentId,VersionNumber,CreatedByRole='user'`) 명시로 확장(prior 없음 시 NULL/1/NULL='user' → 기존 default byte-동치). commit 후 직전 버전 `SET SupersededAt=UTC_TIMESTAMP(6) WHERE VersionNumber<new` + PG dual-write 를 체인 전체 id 로 확장.
  - `unit/feature-0002-agent-core/src/agent_core.py` `_build_attachment_context_section`: PG/MySQL SELECT 에 `root_attachment_id/version_number/created_by_role`(row[9..11]) append(기존 index 0~8 보존)·`version_number>1` 파일 라인에 🔄v{n} 표식(사용자/AI 구분)·`MetaJson.version_diff` 수집 → `## FILE UPDATES` 섹션에 `_datamark_untrusted` 후 ```diff``` 주입 + 지침.
  - `static/app.js`: 신규 `_sha256HexOfFile`(crypto.subtle)·`_attachUploadDoneMessage`(버전 상태별 toast). `_uploadComposerAttachment` 클라이언트 dedup 을 이름+크기 → **해시 대조**로 정밀화(동일 내용만 차단). 업로드 성공 3지점(earlyCid·activeConv·staged flush) pill 에 `sha256`/`version_number` 적재 + 버전 인지 toast. 목록 로더 pill 에 `sha256` 적재.
  - tests: `unit/feature-0003-agent-web-ui/tests/test_attachment_versioning.py` +6(U1 diff·U2 truncate·U3/U4 find·U5 upload 정적)·신규 `unit/feature-0002-agent-core/tests/test_attachment_user_version_context.py` +5(표식·FILE UPDATES·datamark·truncate·v1 무회귀).
  - docs: FUNCTION.md REQ-20260713-attach-user-version(AC-AUV-1~6)·TASK.md(PLAN-APPROVED)·REPORT.md·TEST.md §4·REVIEW.md.
- 스키마/마이그레이션/RBAC/엔드포인트 shape: **무변경**(버전 컬럼 전부 기존재 — TASK-0274/0008). 응답 필드 additive(`reused_existing_version`)·MetaJson additive(`version_diff`).
- 검증: py_compile 4 + node --check PASS · 첨부 버전 31 PASS · 전체 스위트 EXIT=0(회귀 0). §18.8 REV-20260713T053423-attach-user-version. Cross-ref: TASK/FUNCTION-20260713T053423-attach-user-version · 기반 TASK-0274/0275/0285/0286(버전 인프라)·0008 core_attachments 스키마.

## CHG-20260707T111500-runtime-settings-postverify (feature-0018 + audit hotfix POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-07. 코드/자산 무변경 — TEST.md §3 에 POST-DEPLOY PB-0008 PASS Run append + TASK 완료 체크. 배포: PR #602→a7dcc436(feature) + PR #604→8d0a4723(audit hotfix), web 무중단 롤링 ×2.
- 검증 요지: 설정 pane 3항목 렌더, 실행 타임아웃 22입력/6카테고리/즉시·재배포 배지, **env-fallback 실증**(300/600/180=.env 값), 모델 예산 2행 no-override input 비움, write-path e2e(저장→DB override→audit→초기화→DB 정리), pageerror 0. 증적 artifacts/feature-0018-runtime-settings/pb0008-runtime-settings-timeouts.png.
- Cross-ref: CHG-20260706T094937-runtime-settings(feature) · CHG-20260707T110000-runtime-settings-auditfix(hotfix) · TEST.md §3 Run.

## CHG-20260707T110534-doc-sync-rn-0707 (TASK-20260707T110534-doc-sync-rn-0707 — 07-02→07-07 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 신규 '2026-07-03'(8항목)·'2026-07-04'(12항목)·'2026-07-06'(4항목)·'2026-07-07'(5항목) 블록 prepend(07-02 이하 블록 보존, 총 4블록 29+ 신규 항목). `generated` 2026-07-02→2026-07-07. 블록 요지: 07-03 제품 카테고리 개요·유사 테이블 영역화·역할 색/아이콘·관계 탐색·화면 조작·데이터소스 평균 연결시간·공유 참여 알림·대량분석 안정성 / 07-04 유사 항목 자동묶음·크로스-DB 연결·묶음 드래그/접기·상세 뒤로앞으로·범례 탭·ds 이름표시·분석중 안내·겹침순서·상단탭+검색·Esc fix·여기부터~여기까지 공유·☰ 메뉴·응답 안정성 / 07-06 추론 강도 선택·함수/프로시저 노드·DB 단위 분석·상세 nav·필터·검색 / 07-07 런타임 설정·카테고리 밴드+크로스-DB·관계 큐레이션·DB 분석 심화·응답 안정성.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260702-rn-0702`→`?v=20260707-rn-0707`.
- Verification: `node --check release-notes-data.js` PASS. 블록 순서 07-07>06>04>03>02·스키마 정합·07-02 이하 보존 확인. 사용자향 평이화(내부용어 누출 0). jsdom 테스트는 이 env 미설치(컨테이너 전용).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- 사용자향 평이화: 내부 구현·feature-id·렌더러/마이그/엔드포인트/cache-buster 내부 슬러그 비노출. 렌더 로직(`release-notes.js`) 무변경 — 데이터만. META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260707T110534-META-0020-doc-sync-0707).
## CHG-20260707T120000-runtime-settings-ux (TASK-20260707T120000-runtime-settings-ux — 런타임 설정 pane UI 재설계, web/UI CSS+JS-only, Major §12.3, feature-0003)
- Date: 2026-07-07 (worktree ai/claude-corp/feature-0018-runtime-settings-ux). 사용자 피드백("UI 세련도 부족") 대응. feature-0018 기능/동작 불변 — **표현(presentation) 계층만** 재구성.
- `static/styles.css`: `.rs-*` 컴포넌트 세트 신규(정렬 grid 행·카테고리 섹션·focus-ring 입력·배지·dirty/override/invalid 상태·반응형). 콘솔 디자인 토큰/패턴 정합.
- `static/admin.js`: 런타임 설정 렌더러 재작성 — `.admin-quota-editor`(미정렬·행별 버튼) 폐기 → `buildRuntimeSettingRow`(2×2 grid, 저장/초기화 버튼 제거). 편집·기본값복원을 `adminState.pending.runtimeSettings` 로 예약, 하단 commit-bar("모두 적용")로 배치 적용(`setRuntimeSettingPending`·applyAllPending 루프·cancelAllPending·refreshPendingUI 연동, nav row `.has-pending` dirty 표시). 설명 잘림 해소(ellipsis+title), 범위 인라인 경고. rsSaveValue/rsResetValue(엔드포인트) 재사용.
- `static/admin.html`: cache-buster `?v=20260707-runtime-settings-ux`(admin.js·styles.css).
- 영향: 백엔드/엔드포인트/RBAC/스키마 무변경. 저장 UX 가 즉시 PUT → pending+배치적용(콘솔 네이티브)로 변경. 회귀 표면=공유 commit-bar 로직(계정/역할/프롬프트) — additive 배선, 적대 리뷰로 검증.
- Cross-ref: CHG-20260706T094937-runtime-settings(기능) · TEST/REVIEW 동일 slug.

## CHG-20260707T121500-runtime-settings-ux-postverify (런타임 설정 UI 재설계 POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-07. 코드/자산 무변경 — TEST.md §3 에 POST-DEPLOY PB-0008 PASS(before/after) append + TASK 완료 체크. 배포 PR #607→da3f57db.
- 검증 요지: 두 패널 정렬 grid·설명 완전노출·commit-bar 편집/적용/복원 e2e(DB override roundtrip)·pageerror 0. 사용자 "세련도 부족" 피드백 해소 확인. 증적 artifacts/feature-0018-runtime-settings/{current,after}-{timeout,model}-panel.png.
- Cross-ref: CHG-20260707T120000-runtime-settings-ux(재설계) · TEST/REVIEW 동일 slug.

## CHG-20260707T130000-reasoning-budgets (TASK-20260707T130000-reasoning-budgets — 추론 강도별 예산 설정 + UI 교훈, Major §12.3 — feature-0003 web/UI + cross-unit feature-0002·shared)
- Date: 2026-07-07. feature-0018 후속: 모델별 예산에 이어 추론 강도(낮음/높음/매우 높음)별 요청 단위 thinking budget 을 관리 콘솔에서 조정 가능하게. '일반'은 no-override(B1)라 설정 대상 제외.
- `shared/runtime_settings.py`: reasoning_budget 레지스트리/resolver/serialize(상세 shared/docs/MODIFY 동일 slug). `unit/feature-0002-agent-core/src/agent_core.py`: `_call_llm` precedence 확장(레벨 override→기본→모델 override; 상세 feature-0002/docs/MODIFY 동일 slug).
- `static/admin.js`: `모델별 추론 예산` 패널을 2 섹션(모델별 + 추론 강도별)으로 확장, 추론 행은 pre-fill(기본값=적용값). nav-dirty 분류 RS_REASONING_PREFIX 추가. `static/admin.html` cache-buster admin.js bump(styles.css 무변경).
- `docs/LEARNINGS.md`: LRN-20260707-0001(UI 가시성 개선 교훈, verified).
- 영향: 백엔드 엔드포인트/RBAC/스키마/audit 무변경(기존 PUT/DELETE·validate·audit 재사용, 신규 키만 등록). override 미설정 시 전 경로 기존 동작 동치(B1 유지).
- Cross-ref: CHG-20260706T094937-runtime-settings·-ux / feature-0002·shared MODIFY 동일 slug.

## CHG-20260707T131500-reasoning-budgets-postverify (추론 강도별 예산 POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-07. 코드/자산 무변경 — TEST.md §3 POST-DEPLOY PB-0008 PASS append. 배포 PR #609→767ca387(web + 워커 재빌드). 검증: 추론 강도별 예산 섹션 렌더·reasoning-key write-path e2e·사용자 MCP_TIMEOUT_SEC=60 override 보존·pageerror 0. 증적 after-model-panel-reasoning.png.
- Cross-ref: CHG-20260707T130000-reasoning-budgets · TEST/REVIEW 동일 slug.
## CHG-20260707-kb-candidate-adoption (TASK-20260707-kb-candidate-adoption — 지식베이스 메타데이터 채택 인박스 + ENUM 대화 자율수집, Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002 agent-core·shared/config)
- 변경 요지: 대화에서 용어사전·ENUM 코드사전 후보를 수집하고 관리 콘솔에서 채택(승급/거부)하도록 재구성. 용어사전은 이미 구현(0021/0023)돼 있어 **ENUM 을 그 대칭으로 신설** + 두 사전 후보를 **통합 채택 인박스**(지식베이스 하위 신규 탭)로 한눈에.
- **ENUM 백엔드(parity)**: 마이그 `0039_enum_feedback`(`enum_feedback` 검토큐 + `enum_dictionary.source` + GRANT, 비파괴·멱등, down_revision 0038_node_analysis_refine). `kb_glossary.py`: enum feedback 함수군(record/auto_promote_or_queue/list/count/promote/reject/_status/_insert_auto/infer) + enum CRUD source. `llm.py`: ENUM_SUGGEST_PROMPT+llm_enum_suggest. `config.py`: AGENT_ENUM_*(threshold 0.9). `agent_core.py`: _enum_autopropose(best-effort). `app.py`: 권한 kb.enum.curate(카탈로그, 마이그 불필요). `admin_metadata.py`: enum-feedback list/promote/reject + admin_list_enums source.
- **UI**: `admin.html`(adoption 탭/pane + 필터 툴바 + 카드 그리드), `admin.js`(ADMIN_TAB_PERMISSIONS.adoption·switchTab 훅·loadAdoptionInbox/render/그룹 카드/개별·일괄 채택·배지·컨트롤 배선), `styles.css`(.admin-meta-tag-kind + .admin-adoption-* — 기존 .admin-meta-row/.dashboard-widget 재사용).
- **범위 봉인**: 용어사전 후보수집·검토 큐 로직 불변(인박스가 기존 glossary-feedback 엔드포인트 재사용). 샘플 검수 큐·그래프 뷰 무변경. 편집-후-채택 미포함(as-is 채택).
- 검증: 신규 코어 14 + web 경계 9 테스트 PASS · 기존 enum-list 계약(source)·route 골든(197→200) 갱신 · 호스트 전체 1581 passed · 컨테이너 make test 유일 실패(routine_dbanalysis, postgres-replica 미해석)는 main 격리에서도 동일 = 사전존재 env(본 변경 무관) · ruff PASS. PB-0008 Windows-browser= POST-DEPLOY(정적 baked).
- Files: `alembic/versions/20260707_0039_enum_feedback.py`(feature-0002), `modules/kb_glossary.py`·`modules/llm.py`·`agent_core.py`(feature-0002), `shared/config.py`, `app.py`·`routers/admin_metadata.py`·`static/{admin.html,admin.js,styles.css}`(feature-0003), 테스트 `test_kb_enum_feedback.py`·`test_metadata_enum_feedback.py`·`test_metadata_glossary_enum.py`·`route_snapshot_p5b.json`, docs `{TASK,TEST,REPORT,FUNCTION,MODIFY,REVIEW}.md`
- Cross-ref: REVIEW.md REV-20260707T051054-kb-candidate-adoption · TASK-20260707-kb-candidate-adoption · feature-0002 REPORT(2026-07-07)

## CHG-20260707-metadata-console-redesign (TASK-20260707-metadata-console-redesign — 메타데이터 콘솔 IA 통합 + 5서브뷰 디자인 폴리시, Major §12.3 — feature-0003 web/UI 단독)
- 변경 요지: 직전 채택 인박스 배포 후 실사용 피드백 반영 — 최상위 `채택 인박스`·`샘플 검수` 탭이 메타데이터 서브뷰와 겹쳐, **2차 보기를 서브탭 파라미터화**해 각 사전 하위로 통합하고 5서브뷰 디자인을 이전 교훈 기반으로 폴리시. **UI 단독**(admin.html/admin.js/styles.css) — 백엔드/라우터/스키마/RBAC 정의 무변경(enum-feedback·sample-feedback API·`kb.enum.curate`/`kb.sample.curate` 권한 유지).
- **구조**: `_METADATA_REVIEW` config + `viewBySub` 상태 + `_metaSyncViews`(#metadataViews 동적 버튼) + `_metaIsReview` 로 glossary 하드코딩 2차 보기를 일반화. 채택 인박스 제거(탭/pane/JS블록/CSS/init/perm), ENUM 후보 → `ENUM 코드사전 > {목록|검토 큐}`, 샘플 검수 → `샘플쿼리 > {목록|검수 큐}`(`loadSampleReview`/`renderSampleReview` #metadataList 재타깃), 최상위 샘플검수 탭 제거. glossary+enum 큐 통합(`loadFeedbackQueue`/`renderFeedbackQueue(kind)`).
- **디자인(감사 Top 10)**: `--surface-2` 토큰·rich empty+skeleton·enums/columns 카드 그룹핑·행 카드 기하·title↔body 위계·폼 grid+인라인검증·SQL 프리뷰·필터바·배지 semantic 토큰(자동등록=neutral)·이모지 제거+KPI. cache-buster `?v=20260707-metadata-console-redesign`.
- **범위 봉인**: 5서브뷰 CRUD/AI 자동완성/부트스트랩 로직 보존. 그래프 뷰·대시보드 등 타 pane 무변경. 백엔드 0.
- 검증: §18.8 3렌즈 패널(BLOCKING 1·MAJOR 1·HIGH 1·MED 3·LOW 5 FIXED, XSS clean, ACCEPT 1) · node --check OK · 제거 심볼 grep-0 · route 골든 불변 · 호스트 1637 passed(회귀 0) · CSS 균형. PB-0008 = POST-DEPLOY.
- Files: `static/{admin.html,admin.js,styles.css}` + docs `{TASK,TEST,REPORT,FUNCTION,MODIFY,REVIEW}.md`
- Cross-ref: REVIEW.md REV-20260707T064745-metadata-console-redesign · TASK-20260707-metadata-console-redesign

## CHG-20260707T230501-doc-sync-rn-2305 (TASK-20260707T230501-doc-sync-rn-2305 — 07-07 후속 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 기존 '2026-07-07' 블록 `items` 에 2항목 append(같은 날 → 새 일자 블록 미생성, `generated` 2026-07-07 유지) — ① new/admin "대화에서 모은 코드값(상태 코드 등) 뜻풀이 후보를 검토해 채택"(0beb02e3) ② improved/admin "AI 추론 예산을 강도(낮음·높음·매우 높음)별로도 설정"(d9516aee). 블록 `summary` 에 '코드값 후보 검토·채택 · 추론 강도별 예산 설정' 구 추가.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260707-rn-0707`→`?v=20260707b-rn-0707`.
- 중복 회피: 업무 용어(glossary) 대화 자율수집은 2026-06-29 블록에 이미 있어(라인 408·414) 재announce 금지 — 신규 코드값(ENUM) 측만 반영(적대 검증 rescope). 콘솔 IA 통합(47a63b1a)·그래프 화살표·pane 재설계·OAuth cron·§56 sync 는 비-사용자/이미-커버 → 릴리즈노트 미포함.
- Verification: `node --check release-notes-data.js` PASS · 블록 순서 07-07>06>04>03>02 · 07-06 이하 보존 · 스키마 정합. 사용자향 평이화(내부용어 누출 0). jsdom 테스트는 이 env 미설치(컨테이너 전용).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- 사용자향 평이화: 내부 구현·feature-id·렌더러/마이그/엔드포인트/권한키/cache-buster 내부 슬러그 비노출. 렌더 로직(`release-notes.js`) 무변경 — 데이터만. landing/배포는 cron wrapper 소관. META(STATUS·wiki·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260707T230501-META-0021-doc-sync-0707-2305).

## CHG-20260708-metadata-console-polish (TASK-20260708-metadata-console-polish — 메타데이터 콘솔 잔여 디자인 폴리시 5건, Minor §12.3 — feature-0003 web/UI 단독)
- 변경 요지: metadata-console-redesign 배포 후 PB-0008 실 Windows 브라우저 적대적 미적 검증에서 잡은 잔여 미세 폴리시 5건 적용. **UI 단독**(styles.css + admin.js confidence 배지 클래스 1개), 백엔드/구조/로직 무변경.
- #1 2차 보기 필 경량화(border 제거·borderless active chip — 1차 밑줄 탭에 종속) · #2 메타 전용 list-detail 균형(목록 300~400px + empty 중앙·max-width) · #3 그룹 카드 내부 행 divider 평탄화(nesting 경감) · #4 timestamp 경량+그룹 내 숨김 · #5 신뢰도 배지 accent(`-conf`).
- 검증: node --check OK · CSS 균형(1905/1905) · route 골든 불변 · 호스트 1662 passed(회귀 0). cache-buster `?v=20260707-metadata-console-polish`.
- Files: `static/{admin.js,styles.css,admin.html}` + docs `{TASK,TEST,REPORT,FUNCTION,MODIFY,REVIEW}.md`
- Cross-ref: REVIEW.md REV-20260708T012922-metadata-console-polish · TASK-20260708-metadata-console-polish · 선행 REV-20260707T064745-metadata-console-redesign

## CHG-20260708-metadata-console-ux2 (TASK-20260708-metadata-console-ux2 — 메타데이터 콘솔 UX 4건, Major §12.3 — feature-0003 web/UI 단독)
- 변경: #1 list 컬럼 폭 확대+행 가독성 · #2 검토/검수 큐 행 클릭→우측 read-only 상세(`_metaRenderReviewDetail`/`reviewSelected`) · #3 ENUM 그룹 "+코드 추가"(`_metaStartCreatePrefilled` pre-fill) · #4 샘플 mermaid 다이어그램 렌더(공용 `mermaid-render.js` 재사용, admin.html vendor 로드). **UI 단독**(백엔드/RBAC/스키마 0).
- 검증: node --check OK · CSS 균형 · route 불변 · 호스트 1662 passed(회귀 0). cache-buster `?v=20260708-metadata-console-ux2`.
- Files: `static/{admin.html,admin.js,styles.css}` + docs `{TASK,TEST,REPORT,FUNCTION,MODIFY,REVIEW}.md`
- Cross-ref: REVIEW.md REV-20260708T033320-metadata-console-ux2 · TASK-20260708-metadata-console-ux2 · 선행 REV-20260708T012922-metadata-console-polish

## CHG-20260708T230501-doc-sync-rn-0708 (TASK-20260708T230501-doc-sync-rn-0708 — 07-08 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases[0] 에 `date:"2026-07-08"` 새 블록 prepend(`generated` 2026-07-08) — 3항목(전부 admin): new §59 제품 분류 AI 제안 / improved §57 그래프 접힘 카드 시각화 / improved 콘솔 검토 화면 개선(ux2 4건+폴리시 5건 통합). 07-07 이하 블록 보존.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260707b-rn-0707`→`?v=20260708-rn-0708`.
- 제외: §58(라벨 케이스/rekey·infra)·§56 T56.9(기출시)·내부 기록·META 도구 → 릴리즈노트 미포함. 07-07 블록과 중복 0.
- Verification: `node --check release-notes-data.js` PASS · 블록 순서 07-08>07>06>04>03>02 · 스키마 정합 · jsdom verify_release_notes.mjs 33/34 PASS(1 FAIL=styles.css pre-existing·본 변경 무관). 사용자향 평이화(내부용어 누출 0).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포는 cron wrapper 소관. META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260708T230501-META-0022-doc-sync-0708).

## CHG-20260709-graph-toolbar-consolidate (TASK-20260709-graph-toolbar-consolidate — 그래프 뷰 상단 툴바 통합 + 우측 상태 텍스트 reflow 제거, Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016)
- 문제: 그래프 뷰 툴바에 성격이 다른 컨트롤 13개(검색·깊이·스키마이동·종류필터3·초기화·제품·줌4·상세·상태)가 한 줄 flat 나열 → '지저분'. 상태 텍스트가 flex-wrap 툴바에 인라인(`margin-left:auto`)이라 내용 길이↑ → 툴바 wrap → 높이↑ → body(`flex:1`) 가 남은 높이 채워 캔버스가 위아래로 밀림(사용자 '아래 UI 지속 변형' 불만의 정확한 메커니즘).
- 변경: ① 툴바 4존 압축 + 보기옵션 팝오버(`.amg-viewopts*`) ② 줌 → 캔버스 좌하단 오버레이(`.admin-meta-graph-zoomctl` absolute) ③ 상태 → 캔버스 좌상단 오버레이 pill(`.admin-meta-graph-status` absolute·2줄 클램프·auto-fade) — 레이아웃 흐름 밖이라 reflow 0 ④ 캔버스 `.admin-meta-graph-canvas-wrap` 위치 컨텍스트(role=img 밖 형제 오버레이) ⑤ admin.js: `_metaGraphStatus` auto-fade·`_metaGraphSyncViewOptsBadge`·팝오버 토글·LOD `is-idle` 해제.
- behavior-neutral: 컨트롤 id 전량 보존(`getElementById` 바인딩 불변). 캐시버스터 styles.css/admin.js `20260709-graph-toolbar`.
- Files: `static/{admin.html,admin.js,styles.css}`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- Verification: `node --check` OK · 실 Windows Chrome 149 harness 렌더 실측 PASS · 디자인·correctness 적대 패널(REVIEW). POST-DEPLOY PB-0008 라이브(deploy_scope:included).

## CHG-20260709T120000-graph-toolbar-postverify (graph-toolbar POST-DEPLOY PB-0008 라이브 PASS 기록 — 비-정책 doc-only)
- 배포 ee54b1ff(soak PASS) 후 라이브 콘솔(`https://localhost/` → /admin → 그래프 뷰) PB-0008 실측 결과를 TEST.md §3 Run 에 POST-DEPLOY 갱신으로 append + TASK.md POST-DEPLOY 체크박스 [x]. 실측: toolbarKids=4·**reflow0=true**·팝오버 no-clip·pageerror 0(상세 TEST.md §3). 코드·자산 변경 0.
- Files: `docs/{TEST,TASK,MODIFY,REVIEW}.md` (doc-only). 원천 cycle: CHG-20260709-graph-toolbar-consolidate(코드) / 배포 ee54b1ff.

## CHG-20260710T230000-minimap-reuse (그래프 미니맵 전체-이미지 재사용 — web 자산, 정본 feature-0016 §70/ADR-034)
- 대상: `src/static/admin.js`(신규 `_metaMinimapGeomSig`·`_metaPatchMinimapReuse` + `_metaG6ApplyOnce` 서명 배선 + minimap 플러그인 `key:"minimap"` + init 직후 patch) + `src/static/admin.html`(버스터 `admin.js?v=20260710-minimap-reuse`) + 신규 `tests/headless/test_g6build_minimap_reuse.js`.
- 변경(frontend-only, cross-cut 코드 거주 — 기능 정본 feature-0016): G6 v5 minimap 플러그인의 전량 재복제 `renderMinimap()` 을 기하 서명 게이트로 감싸, 상태-only rebuild(선택/역할도착/busy)에서 미니맵 재복제를 skip(이미 그려둔 전체 이미지 재사용). 구성 변경 시엔 정상 재복제. 팬/줌은 원래도 G6 가 마스크만 갱신(무영향).
- 적대 리뷰 2건 BLOCK 적발→수정: H1(패치 init 시점 호출→plugin lazy-init 전 no-op) → draw 직후 이동, H2(네이티브 드래그 stale 서명→미니맵 얼어붙음) → afterdraw stage="translate" 서명 무효화.
- Verification: `node --check` OK · headless 신규 **35** + 회귀 150 PASS · 적대 패널(REVIEW). POST-DEPLOY PB-0008 라이브(deploy_scope:included, TEST §70).

## CHG-20260711T115053-docs-archive (MODIFY/REVIEW §5.5 아카이빙 — priming read-set 경량화)
- Date: 2026-07-11. AGENTS.md §5.5(20건 초과)·§5.6(50KB/400줄 임계 — MODIFY 5,589줄·REVIEW 4,650줄로 최대 위반) 적용, 사용자 지시("정책문서 분리/세분화")로 착수.
- Summary: 엔트리 verbatim 이관(원본 순서·내용 무변경) — MODIFY 408건·REVIEW 389건 → `_archive/<DOC>-archive-20260711T115053.md`(timestamp 규약 ADR-20260710T231146 첫 적용). 현행 파일 각 114줄로 경량화. 무손실 재구성 md5 증명.
- Files: docs/MODIFY.md · docs/REVIEW.md · docs/_archive/ 신설 2파일 · docs/REPORT.md(압축 정보) · docs/TASK.md.
- Rollback: 아카이브 내용을 링크 지점에 재삽입(verbatim 이라 무손실 복원 가능).

## CHG-20260712T073000-item09-graph-split (admin.js 그래프 분리)
- Date: 2026-07-12. admin.js 3618~9024→static/graph/graph.js(pure move, -5,407). type=module+bridge. 자동검증 GREEN. 브라우저 QA 대기.

## CHG-20260712T190500-item09-batch23-stamp (그래프 CSS/JS 세분화 + 캐시버스터 자동화)
- Date: 2026-07-12. 변경: ① batch2 — styles.css 그래프 밴드(8246~8682, 437줄)→graph/graph.css(공유 2예외 잔류), admin.html link 추가 ② batch3 — graph.js→7모듈+barrel(섹션-연속 pure move, import/export 표면은 census 마스킹 참조로 기계 산출, 죽은 _metaSubmitForm import 제거) ③ what#3 — ?v= 소스 placeholder(?v=dev) 고정 + inject_asset_stamp.py 빌드 주입(content-hash, vendor pin 보존) + deploy-web asset_stamp_verify 하드게이트(구 asset_stamp_warn 대체) + ES import specifier 스탬프(이중 인스턴스화 해소).
- Files: static/{styles.css,admin.html,index.html,share.html,admin.js}, static/graph/{graph.js,graph-*.js,graph.css,MAPPING.md}, feature-0002 src/{Dockerfile,scripts/inject_asset_stamp.py}, bin/deploy-web.sh, .gitattributes, AGENTS.md §13.1, ROADMAP.
- Verification: node --check 8/8 · 이동구간 verbatim 7/7 · 미해결참조/ghost-export 0 · CSS byte-eq+brace 0 · inject 멱등(--check=a888c8833eb6) · PB-0008 실브라우저(렌더 픽셀동일·스코프·검색·줌·클릭·우클릭, 콘솔 에러 0).
- Rollback: 커밋 revert(atomic PR). 배포 실패 시 deploy-web last-good 자동 롤백.


## CHG-20260713T102249-doc-sync-rn-0713 (TASK-20260713T102249-doc-sync-rn-0713 — 07-09~10 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases[0] 에 `date:"2026-07-10"` 새 블록 prepend(`generated` 2026-07-10) — 7항목(fixed/work 1·improved admin 5·improved/common 1). 07-09 이하 블록 보존.
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(ITEM-09 what#3 이후 수기 bump 폐지) — Dockerfile `inject_asset_stamp.py` 가 배포 시 content-hash 주입, deploy-web `asset_stamp_verify` 가 baked placeholder 잔존 하드 차단. index/admin.html 편집 0.
- 제외: POST-DEPLOY/docs-only 커밋·추론예산(07-09 기출시·docs/RELEASE_NOTES 미러에만 추가)·07-11~13 behavior-neutral(feature-0012 라우터 모듈화 완결·ITEM-09 그래프 CSS/JS·META 툴링). 07-08/07-09 블록과 중복 0.
- **§69 편입**: 07-10 run REJECT(T69.5 미완) → 07-13 PR #744 T69.5 완수(cc_data_main 715/715)로 라이브 관측 가능 → 편입.
- Verification: `node --check release-notes-data.js` PASS · vm 구조검증(블록순서·스키마·누출0). 사용자향 평이화(내부용어 누출 0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포는 본 attended run 소유(PR→merge→make deploy-web). META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260713T102249-META-doc-sync-0713).


## CHG-20260713T181800-graph-perm-split (그래프 뷰 권한을 '메타데이터 관리' 묶음에서 분리 — Critical §12.3 인증/인가, 사용자 승인 B안)
- Date: 2026-07-13. 요청(/_template:entry): "그래프 뷰가 별도의 탭으로 분리됨에 따라, 권한 또한 '메타데이터 관리'로부터 별도로 분리." 결정: **B안(분리 + 기존 접근 보존, 비파괴)**.
- 변경(behavior — RBAC):
  - `src/web_context.py`: `_METADATA_MANUAL_IMPLIES` 에서 `metadata.graph.read` 제거(편집 4종만 함의) · 묶음 `kb.ingest.manual` 설명·`metadata.graph.read` 라벨("그래프 뷰 조회")/설명 갱신 · 신규 `_backfill_graph_perm_split_v1(conn)`(1회 접근보존 backfill, `_ensure_seed_roles` 말미 호출) + `_GRAPH_PERM_SPLIT_MIGRATION_KEY` 상수.
  - `src/routers/_bootstrap_schema.py`: `WebSchemaMigrations(MigrationKey PK, AppliedAt)` DDL — 1회 웹 DB 마이그레이션 guard 저장소.
  - `src/static/admin.js`: `ADMIN_TAB_PERMISSIONS.graph` = `["metadata.graph.read"]`(묶음 인정 제거) · `PERMISSION_DEPENDENCIES["metadata.graph.read"]` = `"console.access"`(묶음 하위→직속 승격).
  - `src/static/admin.html`: 그래프 탭 게이트 주석 갱신.
  - `tests/test_metadata_perm_split.py`, `tests/test_permission_dependency_map.py`: 분리 계약 반영(R3 편집4종·R3c 묶음 graph 미함의·R3d 독립부여·t5 graph.read=console.access·m3 포함).
- 하위호환(비파괴·가역): backfill 이 분리 전환 1회에 (a) 묶음 보유 role→graph.read role권한, (b) 묶음 ALLOW override 계정→graph.read ALLOW override(graph.read DENY 는 존중). `WebSchemaMigrations` 마커로 재실행 차단. admin 은 기존 explicit catchup 으로 graph.read 유지.
- Files: `src/web_context.py`, `src/routers/_bootstrap_schema.py`, `src/routers/admin_metadata.py`(docstring), `src/static/admin.js`, `src/static/admin.html`, `tests/test_metadata_perm_split.py`, `tests/test_permission_dependency_map.py`, `docs/{TASK,MODIFY,REPORT,REVIEW,TEST}.md`, `static/release-notes-data.js`.
- Verification: 권한 단위테스트(perm-split/dependency-map/glossary-enum) + feature-0003 전체 스위트 PASS(회귀 0) · §18.8 보안 렌즈 적대 리뷰(권한상승·접근상실·멱등·enforcement·SQL, 라이브 MySQL 8.0.46 실증) — 3 findings(A MEDIUM 권한상승·B LOW 멱등·C NIT docstring) 적발·수정 후 VERDICT PASS.
- Rollback: 커밋 revert. backfill 은 grant 추가만(파괴 없음) — revert 후에도 부여된 graph.read 는 잔존(관리 콘솔에서 명시 회수 가능). `WebSchemaMigrations` 마커 row 는 잔존(무해).
- 잔여: verify-completion → commit(사용자 confirm) → 머지·push → web 재배포 → 배포 후 DB 마커·라이브 권한 그리드 + PB-0008 실렌더.

## CHG-20260713T185600-graph-perm-descfix (graph-perm-split 배포 후 seed catchup 1406 hotfix — 권한 설명 255자 초과)
- Date: 2026-07-13. 배포 후 실증에서 `WebSchemaMigrations` 미생성·backfill 미실행 적발. web 로그 `seed catchup skipped: 1406 Data too long for column 'Description'`. 근본원인: `kb.ingest.manual` 설명 301자 > `WebPermissions.Description` VARCHAR(255) → `_ensure_permission_catalog` 1406 → `_ensure_seed_catchup`(fast path) 전체 skip → seed_roles/backfill 미실행. CI(`--no-deps`)가 컬럼 제약 미검출.
- 변경(behavior — 부트스트랩 robustness):
  - `src/web_context.py` `_ensure_permission_catalog`: `label[:128]`·`description[:255]` 방어적 클립(단일 긴 문자열이 전 catchup 을 차단하던 fragility 제거).
  - `src/web_context.py` `kb.ingest.manual` description 301→205자 단축(온전 저장, 잘림 0).
- 영향: 그래프 접근 상실 사용자 0명(유일 묶음 보유=admin, 이미 graph.read 보유). 부트스트랩 catchup 재개가 핵심.
- Files: `src/web_context.py`, `docs/{TASK,MODIFY,REPORT,REVIEW,FUNCTION}.md`, `docs/test-runs.d/*`.
- Verification: py_compile OK · feature-0003 전체 스위트 PASS(회귀 0) · 전 권한 desc≤255·label≤128 전수 확인.
- Rollback: 커밋 revert(설명 길이만 원복 시 1406 재발하므로 truncation 클립은 유지 권장).
- 잔여: 배포 후 web 로그 `seed catchup skipped` 소멸 + `WebSchemaMigrations` graph-perm-split-v1 row 실증.


## CHG-20260714T024534-doc-sync-rn-0714 (TASK-20260714T024534-doc-sync-rn-0714 — 07-13 오후 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases[0](date "2026-07-13") items 에 **+7항목** append(improved/admin 4·new/work 2·fixed/work 1)·summary 재작성. generated 2026-07-13 유지(새 date 블록 생성 안 함). 07-10 이하 블록 보존.
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0. release-notes-data.js 내용 변경만으로 전역 content-hash 변화 → wrapper 재빌드 시 서빙 토큰 자동 갱신(수동 bump 부적용·해시 불변).
- 제외: feature-0019 메시지 편집(backend-only)·describe_routine(unverified-live)·내부 렌더 최적화(§79/§80)·deploy checklist.
- Verification: `node --check` PASS · vm 구조검증(블록순서·스키마·07-13 8항목·누출0). 사용자향 평이화(내부용어 누출 0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **landing/배포 소유=cron wrapper 위임**(로컬 commit 만·push/merge/deploy 미수행). META(STATUS·wiki·ARCHITECTURE·SECURITY·meta/REVIEW)는 별도 commit(REV-20260714T024534-META-0035-doc-sync-0714).

## CHG-20260713T185846-attach-filename-consistency (첨부 새 버전 파일명 코드-권위 정합, secondary cross-ref, conversation_audit FR-attachment-update-pasted-not-versioned)
- Date: 2026-07-13. `/_dqa:conversation_audit "첨부파일 갱신"` 의 **secondary(cross-ref)** — primary=feature-0002 프롬프트(CHG-20260713T185846-attach-update-versioned). 사용자 요구 2항: "갱신된 파일의 명칭도 기존과 정합(버전 접미)".
- Reason(RC): 명명 정합이 코드로 보장되지 않음 — `_next_version_filename` 은 LLM 이 filename 을 **생략할 때만** 적용됐고, 프롬프트는 오히려 LLM 에게 `report_v2.csv` 수동 지정을 유도 → 버전 불일치·재편집 이중접미(`report_v2.csv`→`report_v2_v3.csv`) 가능.
- Changes (`src/routers/_conv_store.py`):
  - `_next_version_filename` idempotent 강화: stem 의 기존 `_v<n>$` 접미를 `app.re.sub` 로 제거 후 재부여 → 재편집 이중접미 방지(`report_v2.csv`+v3→`report_v3.csv`). 확장자 없는 이름도 처리.
  - `_materialize_assistant_attachment_edits` 명명 블록을 **코드-권위**로 교체: LLM `filename` 유무와 무관하게 항상 `<stem>_v<next_version>.<src_ext>` 생성. LLM 이 이름을 줘도 stem 만 취하고 버전 접미를 강제, 확장자는 source 를 강제 보존(보안리뷰 V3 `.exe` 차단 불변; 확장자 부재 source 는 kind 기반 안전값 §18.8 SEC-1).
- Recurrence sealing: LLM-dependent 명명 → 코드 권위 명명(AUTH-1a). materialize 가드(conv/account scope·size cap·text-only·MinIO 원자성·UNIQUE version race) 전부 불변. **보안 회귀 0**.
- 검증: `tests/test_attachment_versioning.py` 명명 정합 케이스(idempotent·이중접미 방지·확장자 강제·SEC-1) + feature-0003 회귀. §18.8 패널 REV-20260713T185846.
- Cross-ref(정본): feature-0002 CHG-20260713T185846-attach-update-versioned · FRICTION_LEDGER FR-attachment-update-pasted-not-versioned · ANCHOR 0003 무충돌.
## CHG-20260714T105200-graph-analyze-perm (그래프 AI 능동 분석 실행 권한을 하위 권한으로 분리 — Critical §12.3 인증/인가)
- Date: 2026-07-14. 요청: AI 능동 분석 '실행' 권한을 조회(metadata.graph.read)에서 하위 권한으로 구분 + 무권한 시 버튼 UI 미표시. 하위호환=A안(최소권한, backfill 없음).
- 변경(behavior — RBAC):
  - `src/web_context.py`: 신규 `metadata.graph.analyze`("그래프 AI 능동 분석 실행", group=kb) + `metadata.graph.read` 설명 갱신(조회+결과열람 / 실행은 하위 권한으로 분리) + `_ensure_seed_roles` admin catchup 에 `metadata.graph.analyze` 추가(기존 admin 락아웃 방지).
  - `src/routers/admin_metadata.py`: 실행 POST 2개 `require_permission` `metadata.graph.read`→`metadata.graph.analyze` (`/graph/analyze` 노드, `/graph/analyze-schema` 스키마) + docstring 갱신. GET status/node/columns 는 graph.read 유지(읽기).
  - `src/static/admin.js`: `PERMISSION_DEPENDENCIES` 에 `metadata.graph.analyze → metadata.graph.read`(하위, progressive disclosure).
  - `src/static/graph/graph-ctxmenu.js`: 능동 분석 트리거 UI 5곳 `can("metadata.graph.analyze")` 게이팅 — 노드 상세 AI 섹션(#metaGraphAiSec, 미렌더+바인딩 skip)·노드 우클릭·스키마 우클릭·combo 우클릭·클러스터 카드 버튼.
  - tests: `test_metadata_perm_split.py`(graph.read 만으론 analyze 미부여·독립부여·admin catchup·catalog/seed) + `test_permission_dependency_map.py`(t5 graph.analyze→graph.read 종속·depth).
- 하위호환: A안 — graph.read 보유자에게 analyze backfill 없음(명시 부여). admin 은 catchup 으로 획득. 현재 graph.read 보유자 admin 뿐 → 실질 영향 0. 데이터 마이그레이션 없음(WebSchemaMigrations 마커 불요).
- Files: `src/web_context.py`, `src/routers/admin_metadata.py`, `src/static/admin.js`, `src/static/graph/graph-ctxmenu.js`, `tests/{test_metadata_perm_split,test_permission_dependency_map}.py`, `docs/{FUNCTION,TASK,MODIFY,REPORT,REVIEW}.md`, `docs/test-runs.d/*`.
- Verification: py_compile + node --check(module) OK · 권한 타깃 + feature-0003 전체 스위트 PASS(회귀 0) · §18.8 보안 렌즈 적대 리뷰.
- Rollback: 커밋 revert. grant 추가만(파괴 없음) — revert 후 admin 의 graph.analyze row 는 잔존(관리 콘솔 회수 가능).
- 잔여: 배포 후 graph.read-only 계정 버튼 미노출·POST 403 / graph.analyze 계정 버튼·실행 정상 실증.
## CHG-20260714T015432-step-scroll-preserve (TASK-20260714T015432-step-scroll-preserve — 실행 단계 폴링 갱신 시 펼친 "결과 보기" 스크롤 보존, Minor §12.3 frontend-only)
- Date: 2026-07-14. 사용자 보고: 내부 실행 단계 갱신 때마다 펼쳐 둔 "결과 보기" 스크롤이 초기값으로 리셋. RC: 두 라이브 폴링 재렌더 경로가 컨테이너를 `innerHTML=""` 로 통째 재작성 → 결과 표/미리보기·외부 목록 스크롤 0 초기화(펼침 상태는 `state.stepResultExpanded`+`_stepResultKey` 로 이미 복원되나 스크롤은 미복원).
- Changes (`src/static/app.js`):
  - `buildStepDetailEl`: 결과 wrap(`.step-result-wrap`)에 `dataset.stepResultKey = stepKey`(`_stepResultKey`=step_index+created_at) 부여 — 재렌더 간 스크롤 매칭 안정 키(펼침 영속화와 동일 키 재사용).
  - 신규 제네릭 헬퍼 `_snapshotStepResultScroll(body)` / `_restoreStepResultScroll(body, map)`: 컨테이너 내 펼쳐진(`[data-step-result-key]` 비-hidden) 결과의 `.result-table-wrap`/`.step-result-preview` 스크롤(top/left)을 stepKey 로 Map 캡처·복원. 접힘·미매칭·null/빈맵 방어.
  - `_renderStepSidePanelBody`(사이드 패널): 재렌더 전 `prevScrollTop`+`_snapshotStepResultScroll(body)` → `body.innerHTML=""` 재작성 → `_restoreStepResultScroll` + 외부 스크롤(하단추종=최하단 / 미추종=`Math.min(prevScrollTop, maxTop)` 유지, 기존 미추종 0 리셋 제거).
  - `renderProgress`(인라인 progress 카드): 동일 규약을 `progressStepsEl` 에 적용(progAtBottom/progPrevTop + snapshot/restore).
- 무회귀: 펼침/토글 동작·하단추종 자동스크롤·step dedup 키 불변. 백엔드/엔드포인트/RBAC/스키마 0. 표준 DOM scroll semantics.
- 검증: `node --check app.js` PASS · 신규 `tests/verify_step_result_scroll_preserve.mjs`(jsdom, 소스추출 격리) **23/23 PASS**. 정적 자산 baked → 시각 최종확인 PB-0008 배포 후 잔여(§CHECK#13, visual_verification_scope: always).
- Files: `src/static/app.js`, `tests/verify_step_result_scroll_preserve.mjs`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,TEST,REPORT}.md`, `docs/test-runs.d/20260714T015432-step-scroll-preserve.md`.
- Cross-ref: REV-20260714T015432-step-scroll-preserve · REQ/AC-SSP-1~3.

## CHG-20260714T133700-routemap-refresh (graph-analyze-perm 후속 — docs/ROUTEMAP.md 재생성, 자동생성 artifact)
- Date: 2026-07-14. graph-analyze-perm(PR #783, e7c31e3e) 이 analyze POST 2개의 `require_permission` 를 graph.read→graph.analyze 로 바꿨는데 `docs/ROUTEMAP.md`(route→permission 자동 맵) 재생성을 누락 → main CI "Code-Navigation Map gate"(`gen-routemap.py --check` exit 3, ROUTEMAP STALE) 적색. **원인**: verify-completion CHECK#15 는 diff 에 구조적 route 추가/삭제가 있을 때만 gen-routemap --check 를 돌려 permission-only drift 를 로컬 미검출(CI 는 무조건 검사).
- 변경: `python3 bin/gen-routemap.py` 재실행 → `docs/ROUTEMAP.md` 의 `/graph/analyze`·`/graph/analyze-schema` 두 POST 행 permission 을 `metadata.graph.analyze` 로 갱신(2행, 202 routes 중). **코드/런타임 무변경**(auto-generated 내비 doc only).
- Files: `docs/ROUTEMAP.md`, `docs/{TASK,MODIFY,REVIEW}.md`.
- Verification: `gen-routemap.py --check` exit 0(up-to-date) · `codenav-lint.sh` OK.
- Cross-ref: CHG-20260714T105200-graph-analyze-perm(원천) · REV-20260714T133700-routemap-refresh.

## CHG-20260714T053522-step-scroll-raf (TASK-20260714T053522-step-scroll-raf — 펼친 "결과 보기" 가로 스크롤 layout-timing 0-clamp 후속, Minor §12.3 frontend-only)
- Date: 2026-07-14. step-scroll-preserve(CHG-...T015432) 배포 후 사용자 재보고("가로 스크롤이 지속적으로 초기화 여전히 남아있음"). RC: 동기 `_restoreStepResultScroll` 이 재렌더 직후 결과 표 layout 확정 전에 `scrollLeft` 를 써서 브라우저가 `scrollWidth`(overflow 미확정)로 0-clamp. 라운드1 jsdom 테스트는 scrollLeft verbatim 저장이라 미검출.
- Changes (`src/static/app.js`):
  - 신규 `_applyStepPanelScroll(container, resultScroll, atBottom, prevTop)`: 내부 결과셋(`_restoreStepResultScroll`) + 외부 목록 스크롤(하단추종=최하단 / 미추종=`Math.min(prevTop, maxTop)`)을 함께 복원.
  - 신규 `_scheduleStepPanelScroll(...)`: `_applyStepPanelScroll` 을 **동기 1회 + `requestAnimationFrame` 1회** 적용(rAF 로 layout 확정 후 재적용 → 0-clamp 복구). rAF 는 다음 폴링보다 훨씬 앞서(≈16ms) 실행 → 재진입 경합 없음.
  - `_renderStepSidePanelBody`·`renderProgress` 의 인라인 복원 블록(동기 restore + if/else 외부 스크롤)을 `_scheduleStepPanelScroll(...)` 호출로 대체.
- 무회귀: 순수 additive(동기 복원 유지 + rAF 추가, 동일 캡처값 재적용). 펼침/토글·하단추종·dedup 키·백엔드/RBAC/스키마 0.
- 검증: `node --check` PASS · `tests/verify_step_result_scroll_preserve.mjs` **29/29 PASS**(+5: [3b] rAF 배선·[7] 동기+rAF 이중 복원·0-clamp 복구·큐 소진). 로컬 chromium 다운로드 차단으로 real-browser clamp 는 미재현 — 배포 후 사용자/PB-0008 확인.
- Files: `src/static/app.js`, `tests/verify_step_result_scroll_preserve.mjs`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,TEST,REPORT}.md`, `docs/test-runs.d/20260714T053522-step-scroll-raf.md`.
- Cross-ref: REV/TASK/AC-SSP-4-20260714T053522 · 원천 REQ-20260714T015432-step-scroll-preserve.

## CHG-20260714T180314-graph-entry-help (TASK-20260714T1803-graph-entry-help — 그래프 뷰 첫 입장 도움말 팝업 + 중간버튼 커서, Minor §12.3 frontend-only additive)
- Date: 2026-07-14. 사용자 요청: 그래프 뷰 첫 입장 조작 도움말 팝업(닫기·재확인 가능) + 마우스 중간 버튼 클릭 시 커서 적절 변경. `/_template:entry` arg-given. 그래프 도메인 정본 feature-0016.
- Changes:
  - `src/static/admin.html`: 툴바 `❓ 도움말` 버튼(`#metadataGraphHelpBtn`, 초기화·상세 옆) + 캔버스 wrap(role=img 밖 형제 — 접근성) 내 `#metadataGraphHelp` 오버레이(role=dialog·aria-modal, 8개 조작 항목·읽기전용 고지·✕/알겠습니다).
  - `src/static/graph/graph.css`: `.amg-help-*` 스타일 — `.admin-meta-graph-canvas-wrap`(position:relative) 기준 절대배치 inset:0·z-index 40(줌6/상태6/미니맵5/보기옵션30 위)·중앙 카드+반투명 backdrop·amgHelpIn 애니·좁은 폭 라벨 세로 스택. 토큰(--surface/--border/--text*/--primary)만 써 라이트/다크 자동.
  - `src/static/graph/graph-core.js`: `_metaGraphShowHelp`/`_metaGraphHideHelp`/`_metaGraphMaybeAutoHelp`/`_metaGraphBindHelp` 신설(+`_META_HELP_SEEN_KEY`/`_metaHelpKeydown`). `_metaShowGraph` 에 `_metaGraphBindHelp()`(멱등 `_helpBound`) + 검색 포커스 뒤 `_metaGraphMaybeAutoHelp()` 훅. 첫 진입 1회 자동노출=`localStorage("metaGraphHelpSeen")` 미확인 시만, 닫으면 seen set. 닫기 4경로(✕·알겠습니다·배경 target 판정·Esc capture)·a11y 포커스 이동/복귀·localStorage try/catch 안전 강등. 중간버튼: 기존 container `mousedown` button===1 핸들러에 `cursor="grabbing"` + mouseup(buttons&4 유지 가드)·blur 복원.
- 무회귀: 순수 additive. 백엔드/엔드포인트/RBAC/스키마 0 · 기존 그래프 상호작용(팬·노드드래그·우클릭·줌·미니맵)·이벤트 바인딩 0 · cache-buster `?v=dev` placeholder(빌드 content-hash 자동주입) 수기편집 없음.
- 검증: `node --check --input-type=module`(graph-core.js) PASS · admin.html 도움말 블록 태그 균형 · graph.css 중괄호 215/215 · 심볼 전수 존재. PB-0008 라이브=POST-DEPLOY 이연(정적 baked).
- Files: `src/static/admin.html`, `src/static/graph/graph.css`, `src/static/graph/graph-core.js`, `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260714T180314-graph-entry-help.md`.
- Cross-ref: REV/TASK-20260714T1803-graph-entry-help · TEST test-runs.d/20260714T180314-graph-entry-help.md · ANCHOR 0003 무충돌.

## CHG-20260714T184717-graph-help-overlay-fix (TASK-20260714T184717-graph-help-overlay-fix — 그래프 도움말 팝업 mis-position 근본원인 수정, Minor §12.3 frontend-only)
- Date: 2026-07-14. POST-DEPLOY 후속(graph-entry-help 배포 1f705a9e 직후 사용자 지적: "도움말 팝업을 그래프 뷰 중앙에 위치·좌하단 줌 컨트롤 겹침 해결"). `/_template:resume` 재개.
- 근본원인: `graph.css` 도움말 스타일 주석(CHG-20260714T180314-graph-entry-help 에서 작성)의 토큰 목록 `토큰(--surface/--border/--text*/--primary)만` 에서 `--text*` 뒤 `/` 와 결합해 **`*/` 서브스트링**이 생겨 CSS 주석이 조기 종료 → 이후 텍스트가 깨진 CSS 로 유입 → 바로 아래 `.amg-help-overlay { position:absolute … }` 규칙이 파서에서 통째 드롭 → position `static` 폴백 → flex column 흐름상 캔버스 아래 렌더 → 팝업이 줌 컨트롤과 겹침. (라이브 CDP: `getComputedStyle` 전 속성 기본값 + `sheet.cssRules` 에 bare `.amg-help-overlay` 부재 + 격리 파싱은 정상 → 직전 주석 문맥 문제로 특정. `/*`:`*/` 개수 61:62 → 61:61.)
- Changes:
  - `src/static/graph/graph.css`: 주석 line ~447 토큰 구분자 `/` → `·`(`--surface·--border·--text*·--primary`)로 `*/` 서브스트링 제거 + 재발 방지 NOTE 2줄 삽입. **CSS 선언·선택자·미디어쿼리 무변경**(주석 텍스트 국한).
- 무회귀: CSS 규칙/선택자/미디어쿼리 0 변경(git diff +4/-2, 주석만). 백엔드/RBAC/스키마/JS/HTML 0. cache-buster `?v=dev` placeholder(빌드 content-hash 자동주입) 수기편집 없음.
- 검증: (a) 수정본 파싱 시 `.amg-help-overlay` 규칙 복구·`position:absolute`(rule 204→205). (b) 라이브 규칙 주입 후 geometry: 카드 canvas-wrap 정중앙(dx:0 dy:0)·줌 컨트롤 미겹침(card_overlaps_zoom:false). (c) §18.8 SUBAGENT 적대검증 PASS(주석 델리미터 61/61·잔여 `*/` hazard 없음·diff 주석 국한). POST-DEPLOY 재배포 자산 최종 확인=deploy-web 직후.
- Files: `src/static/graph/graph.css`, `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260714T180314-graph-entry-help.md`.
- Cross-ref: REV/TASK-20260714T184717-graph-help-overlay-fix · 원천 CHG-20260714T180314-graph-entry-help · TEST test-runs.d/20260714T180314-graph-entry-help.md(POST-DEPLOY FIX 섹션) · ANCHOR 0003 무충돌.

## CHG-20260714T190916-graph-help-overlay-postverify (그래프 도움말 팝업 mis-position 수정 POST-DEPLOY 재배포 자산 실증 기록, doc-only)
- Date: 2026-07-14. CHG-20260714T184717-graph-help-overlay-fix(PR #798, main 8d1285d0) 배포 후 **재배포된 자산** 상 최종 확인. 코드 변경 0(문서 전용).
- Changes: `docs/test-runs.d/20260714T180314-graph-entry-help.md` POST-DEPLOY FIX 섹션에 "재배포 자산 최종 확인" append + `docs/TASK.md` fix post-deploy 박스 close.
- 실증: `/healthz` git_commit=8d1285d0. 서빙 graph.css 스탬프 `4335ea1dac52`→`d5f26a416089`(content-hash 갱신)·소스 byte-identical·주석 델리미터 61:61. 배포본 런타임(win-browser eval, 주입 없이): `.amg-help-overlay` cssRules 파싱 복구·`position:absolute`·`display:flex`·`align-items:center`·`z-index:40` · 카드 canvas-wrap 수평 정중앙(dx:0)·줌 컨트롤 미겹침(card_overlaps_zoom:false) · ❓ 버튼 팝업 스크린샷 육안(중앙 모달) · pageerror 0. → 배포본 실증 PASS.
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/test-runs.d/20260714T180314-graph-entry-help.md`.
- Cross-ref: REV-20260714T190916-graph-help-overlay-postverify · 원천 CHG/REV-20260714T184717-graph-help-overlay-fix · ANCHOR 0003 무충돌.


## CHG-20260715T025509-doc-sync-rn-0715 (TASK-20260715T025509-doc-sync-rn-0715 — 07-14 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases 배열 head 에 **date "2026-07-14" 새 블록 prepend**(10항목: work 6·admin 3·common 1)·summary 작성. generated 07-13→07-14. 기존 28 블록 보존(총 29).
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0. release-notes-data.js 내용 변경만으로 전역 content-hash 변화 → wrapper 재빌드 시 서빙 토큰 자동 갱신(수동 bump 부적용·해시 불변).
- 제외: feature-0020 무중단 배포(내부)·feature-0016 flock/cluster-label(내부 운영)·@@ 시스템변수 과차단(07-13 블록 detail 포괄·중복 회피)·POST-DEPLOY/ROUTEMAP/ANCHOR 기록.
- Verification: `node --check` PASS · vm 구조검증(29 releases·07-14 head 10항목·07-13 보존·스키마·누출0). 사용자향 평이화(내부용어 누출 0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **landing/배포 소유=cron wrapper 위임**(로컬 commit 만·push/merge/deploy 미수행). META(STATUS·wiki·ARCHITECTURE·SECURITY·meta/REVIEW)는 별도 commit(REV-20260715T025509-META-0036-doc-sync-0715).
## CHG-20260714T181936-perm-category-hier (TASK 20260714T1819-perm-category-hier — 관리 콘솔 권한 체계 카테고리 '접근' 계층 재구성, Critical §12.3 인증/인가)
- Date: 2026-07-14. 사용자 요청("권한 체계 구조적 난잡 — 카테고리별 '접근'(=조회) 최상위 + 하위 종속 + 상위 활성화 시 UI 펼침") — 사용자 승인 A안.
- backend `src/web_context.py`: 신규 카테고리 접근 권한 5종 `console.{account,product,audit,kb,system}.access`(각 카테고리 그룹 배치, desc≤255) · GroupName 재배치(`console.usage.read`/`console.aiops.read`/`conversation.archive.read.any`→audit, `insight.reset`→product — code·enforcement 불변) · admin catchup 5종 + dba `console.audit.access` · `_CONSOLE_CATEGORY_ACCESS_LEAVES` 카테고리→하위 맵 · `_backfill_console_category_access_v1`(1회 멱등, `WebSchemaMigrations` `console-category-access-v1`, 대상 3종 — 접근 무손실) `_ensure_seed_roles` 말미 배선.
- frontend `src/static/admin.js`: `PERMISSION_DEPENDENCIES` 카테고리 계층 전면 재구성(+`system.runtime.*` 종속 신설, `conversation.create`→list.own, `insight.reset`→product.read, 감사 4탭 조회→`console.audit.access`) · `ADMIN_TAB_CATEGORY_ACCESS` 신설 + `canSeeTab`=카테고리 접근(AND)&&탭 권한(OR) · settings 탭 게이트 `system.runtime.read/write` 보강 · 그룹 순서 nav 정합 + kb 라벨 "지식베이스".
- frontend `src/static/app.js`: 그룹 라벨(quota/datasource/kb)·순서 + `PERMISSION_GROUP_OVERRIDES`(재배치 코드 명시 매핑) + 접근 5종 라벨 + manage section groups 정합.
- tests: `test_permission_dependency_map.py`(M3/M4 갱신·M5 신설·V2/V3/V4·v6/v7·t3/t5/t6) · `test_llm_usage_quota.py` f2 · `test_insight_reset.py` group · `verify_admin_tab_gating.mjs`(카테고리 AND 케이스 2b/4b 신설 + release-notes 상시 노출로 stale 하던 시스템 라벨 기대 2건 정정 — main baseline 부터 FAIL 이던 건).
- docs: `docs/SECURITY.md` §22 신설 · `docs/CONVENTIONS.md` §10.6 정합 · unit TASK/REPORT/REVIEW/DECISIONS.
- 비변경: 엔드포인트 `require_permission` 0건(ROUTEMAP 무영향) · 권한 code/스키마/마이그 0 · `_METADATA_MANUAL_IMPLIES` 불변 · 작업 화면 동작.
- Verification: 권한 타깃 50 PASS · feature-0003 스위트 785/0(호스트, baseline 제외) · jsdom 탭 게이팅 47/0 · 컨테이너 make test + 배포 후 backfill 마커·무손실 실증은 TASK 잔여 항목.
- Cross-ref: REV-20260714T181936-perm-category-hier · ADR-20260714T181936-perm-category-hier · SECURITY §22.

## CHG-20260715T102912-graph-help-text-responsive (그래프 도움말 팝업 텍스트 줄바꿈 + 반응형 크기, Minor §12.3 frontend-only CSS)
- Date: 2026-07-15. 사용자 피드백 2건(graph-entry-help 배포본): ① 설명 텍스트가 어절 중간에서 줄바꿈("…탐색하세"/"요.") ② 팝업이 고정 크기가 아닌 브라우저 크기 반응형이 되도록. `/_template:entry`(resume 후속 세션).
- Changes:
  - `src/static/graph/graph.css` `.amg-help-card`: (텍스트) `word-break: keep-all; overflow-wrap: anywhere;` — CJK 기본(normal)이 글자 사이 아무 데서나 끊어 음절 orphan 발생 → keep-all 로 어절(공백) 단위 줄바꿈, overflow-wrap:anywhere 는 폭 초과 토큰 예외 처리. (반응형) `width: min(460px, 100%)` → `width: min(clamp(320px, 90%, 520px), 100%)` — 고정 상한 460px 제거, 캔버스(=브라우저) 폭 90% 를 320~520px 사이 유동, 좁은 화면 100% 바운드. 세로 max-height:100%+overflow-y:auto 유지.
- 무회귀: CSS 선언 2 + 주석만(선택자/미디어쿼리/다른 규칙 0). 백엔드/RBAC/스키마/JS/HTML 0. `/*`:`*/` 63:63·중괄호 215:215 균형(주석 hazard 없음 — 20260714T184717-fix 정신 준수). cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: 라이브 win-browser eval — keep-all 어절 줄바꿈(스크린샷) · 반응형 다중 폭 실측(300→268·360→320·617→520·1100→520, 오버플로 0). POST-DEPLOY 재배포 자산 확인=deploy-web 직후.
- Files: `src/static/graph/graph.css`, `docs/{TASK,MODIFY,REVIEW,FUNCTION,REPORT}.md`, `docs/test-runs.d/20260715T102912-graph-help-text-responsive.md`.
- Cross-ref: REV/TASK-20260715T102912-graph-help-text-responsive · 원천 CHG-20260714T180314-graph-entry-help(팝업 신설)·CHG-20260714T184717-graph-help-overlay-fix(위치 수정) · ANCHOR 0003 무충돌.

## CHG-20260715T103948-graph-help-responsive-postverify (도움말 팝업 줄바꿈+반응형 POST-DEPLOY 재배포 자산 실증 기록, doc-only)
- Date: 2026-07-15. CHG-20260715T102912-graph-help-text-responsive(PR #804, main 6af16762) 배포 후 재배포 자산 상 최종 확인. 코드 변경 0(문서 전용).
- Changes: `docs/test-runs.d/20260715T102912-graph-help-text-responsive.md` 재배포 자산 확인 append + `docs/TASK.md` post-deploy 박스 close.
- 실증: `/healthz` git_commit=6af16762. 서빙 graph.css 스탬프 `d5f26a416089`→`92be1efb1249`(갱신)·`word-break: keep-all`+`clamp(320px, 90%, 520px)` 반영·주석 63:63. 배포본 런타임(win-browser eval, 주입 없이): `.amg-help-card` word-break=keep-all(설명 상속)·overflow-wrap=anywhere · 반응형 다중 폭 300→268·360→320·617→520·1100→520(오버플로 0) · 스크린샷 육안 · pageerror 0. → PASS.
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/test-runs.d/20260715T102912-graph-help-text-responsive.md`.
- Cross-ref: REV-20260715T103948-graph-help-responsive-postverify · 원천 CHG/REV-20260715T102912-graph-help-text-responsive · ANCHOR 0003 무충돌.
## CHG-20260715T103406-perm-atomic-split (TASK 20260715T1034-perm-atomic-split — 권한 최소 단위 원자화 + 레거시 묶음 숨김, Critical §12.3 인증/인가)
- Date: 2026-07-15. perm-category-hier 후속(사용자: "[등록/수정/삭제]·[등록/거부] 통합 잔존") — 사용자 결정: 전체 분리+묶음 숨김 / 검수 단일 유지·원본 사전 하위 종속.
- backend `src/web_context.py`: 원자 23종 신설(사전 4종×read/create/update/delete + product.{create,update,delete} + datasource.{create,update,delete,test}) · `_PERMISSION_BUNDLE_IMPLIES` transitive 함의(개별 DENY 우선) · `LEGACY_BUNDLE_PERMISSIONS` 7종 · admin catchup 23종 · `_backfill_atomic_perm_split_v1`(1회 멱등 `atomic-perm-split-v1`, category-access-v1 선행 호출) · leaves 맵 원자화.
- backend 라우터: `admin_metadata.py` 22 핸들러 액션별 전환+`_METADATA_SUBTAB_PERM_SERVER`=read+`_METADATA_SUGGEST_PERM`(update) 분리 · `admin_products.py` create/update/delete(+구성/규칙/AI제안/프롬프트=update) · `admin_datasources.py` `_ds_write_common(action_perm)`+test=`datasource.test` · `_prompt_context.py` update.
- frontend `admin.js`: DEPS 원자 트리(검수→원본 read 하위)·legacy grid 필터·서브탭 C/U/D 맵+버튼 게이팅·ds/제품 bulk·상세 액션 분리·metadata 탭 게이트 read+curate. `app.js`: legacy 숨김·ds-conn-test `datasource.test` 게이트·라벨 23종.
- tests: perm dict 원자 보강 10파일 · dependency-map 재계약(M3/V2/t5/t6·legacy 제외) · perm_split R7/R8=read + R9(transitive·DENY)·R10(3자 parity) 신설.
- docs: SECURITY §22.4 · CONVENTIONS §10.6 · ROUTEMAP 재생성(202 routes, 권한 열 30행 갱신, --check 0).
- 비변경: 권한 code 삭제 0(묶음은 숨김만·함의 유지) · 스키마/마이그 0 · route 경로/메서드 0 · `_METADATA_MANUAL_IMPLIES` 상수 보존.
- Verification: 785/0(호스트) · jsdom 47/0 · 컨테이너 make test·배포 후 실증은 TASK 잔여.
- Cross-ref: REV-20260715T103406-perm-atomic-split · ADR-20260715T103406-perm-atomic-split · SECURITY §22.4 · 원천 CHG-20260714T181936.

## CHG-20260715T110000-attach-new-label-symmetry (staged-flush 첨부 new_attachment_ids 라벨 대칭 — deferred ②-frontend, Minor §12.3)
- Date: 2026-07-15. 계기: 첨부-답정합 실데이터 감사 deferred ②-frontend(②-backend=CHG-20260715T060000 별도 완료). ② 서브에이전트가 share-window 는 라이브-ask 첨부 경로 밖(비보안)임을 확인 — friction(1) stale-window 의 프론트 축.
- Reason(RC): 신규 대화 send 시 staged 첨부(status="staged")를 `_flushStagedAttachmentsToCid` 가 업로드해 `uploadedIds` 반환 → `attachment_ids` 에만 union(app.js:9307), `new_attachment_ids`(9264 스냅샷은 flush 전이라 `status==="ready"` 필터로 staged 제외)엔 누락. 비대칭 → 방금 올린 파일이 프롬프트에서 ◆세션(이전 세션)으로 오라벨 → assistant 가 "새 파일이 업로드되지 않았거나 반영 안 됨"이라 오판(관측 대화 20260615061233).
- 사용자 승인: **PLAN-APPROVED**(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Minor(라벨-only 프론트 union; 접근/인가 불변 → Critical 아님).
- Changes(feature-0003):
  - `src/static/app.js` — lazy-create + staged 블록에서 `uploadedIds` 를 `askBody.new_attachment_ids` 에도 union(`new Set(...).filter(n>0)`, attachment_ids union 대칭). 블록 밖(기존 대화·무-staged)은 무영향.
- Recurrence sealing: attachment_ids/new_attachment_ids union 대칭으로 staged-flush 신규 첨부의 ★신규 라벨 보장 → "새 파일 반영 안 됨" 오판 경로 봉인. **보안 회귀 0**: new_attachment_ids 는 서버측 라벨+version-diff 게이트 전용(접근 스코프 아님), uploadedIds 는 서버-확인 id, v1 staged 라 version-diff 미트리거.
- 검증: `node --check` PASS. de-risk(로직 대칭 분석 + 적대 패널 + 서버측 new_attachment_ids 소비 추적). 라이브 PB-0008(신규 대화 staged 첨부 ★신규 인지)은 정적자산 baked → 배포 후 실측(TEST.md §3 DEFERRED). §18.8 → REV-20260715T110000-attach-new-label-symmetry.
- Cross-ref: CHG-20260715T060000-attach-inline-honesty(②-backend, feature-0002) · ② 서브에이전트 진단(share-window 비관여) · ANCHOR §1~§3 무충돌.
## CHG-20260715T105337-enum-review-bundle (ENUM 코드사전 검토 큐: 구조 묶음 단위 승인 체크리스트 + 일괄 등록, Major §12.3 additive·비파괴)
- Date: 2026-07-15. 사용자 요청: `관리 콘솔 > 지식베이스 > 메타데이터 > ENUM 코드사전` 검토 큐에서 ENUM값을 구조 묶음 단위로 구성 + 승인 체크리스트(전체 승인/일부 해제) 후 등록. `/_template:entry` arg-given dispatch. 설계 근거: `enum_feedback` UNIQUE `(scope,schema,table,column,code)` → 한 컬럼 = 한 구조 묶음.
- Changes:
  - `unit/feature-0002-agent-core/src/modules/kb_glossary.py`: 신규 `bulk_promote_enum_feedback(conn, feedback_ids, *, approved_by=None)` — 기존 `promote_enum_feedback` 를 단일 트랜잭션 loop, `[{"feedback_id","enum_id"}]` 반환(없음/이미 처리 → enum_id=None skip).
  - `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py`: 신규 `POST /api/admin/metadata/enum-feedback/bulk-promote`(RBAC `kb.enum.curate`) — body `{"feedback_ids":[int,...]}` 정규화(int·양수·dedup·≤`_ENUM_BULK_PROMOTE_MAX`=200) → `bulk_promote_enum_feedback` → commit/rollback + audit `enum.feedback.bulk_promote`(requested/promoted_count/skipped_ids). 모듈 상수 `_ENUM_BULK_PROMOTE_MAX` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `renderFeedbackQueue` enum 경로 → `_metaRenderEnumBundles`(묶음 그룹핑) + `_metaBuildEnumBundle`(전체 승인 마스터+개별 체크박스+힌트+등록 버튼) + `_enumBundleKey`/`_enumBundleRegister`(bulk-promote). enum note 텍스트 갱신. glossary/sample 경로 불변.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-meta-bundle*` 카드 스타일(헤더/체크리스트/푸터).
  - `docs/ROUTEMAP.md`: 재생성(203 routes, 신규 route 반영).
- 무회귀: 개별 promote/reject·glossary/sample 큐·RBAC 정의·스키마/마이그레이션·인증 0. 미선택(해제)은 pending 유지(비파괴 — 거부 아님). cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: `node --check`(module) admin.js PASS · agent 컨테이너 targeted pytest 28/0(core 2 + web 6 신규 포함) · `gen-routemap --check` up-to-date. POST-DEPLOY PB-0008 라이브(묶음 카드·토글·등록) 예정.
- Files: `unit/feature-0002-agent-core/src/modules/kb_glossary.py`, `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py`, `unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css}`, `unit/feature-0002-agent-core/tests/test_kb_enum_feedback.py`, `unit/feature-0003-agent-web-ui/tests/test_metadata_enum_feedback.py`, `docs/ROUTEMAP.md`, `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260715T105337-enum-review-bundle.md`.
- Cross-ref: REV/TASK-20260715T105337-enum-review-bundle · REQ-20260715T105337-enum-review-bundle · 원천 enum_feedback(alembic 0039)·admin_metadata enum-feedback 큐 · ANCHOR 0003 무충돌.


## CHG-20260715T113208-enum-bundle-flex-fix (ENUM 검토 큐 묶음 카드 flex 압축 붕괴 수정, Minor §12.3 CSS 전용)
- Date: 2026-07-15. enum-review-bundle 배포 후 PB-0008 적발 — 묶음 카드 12px sliver 로 붕괴.
- Changes: `unit/feature-0003-agent-web-ui/src/static/styles.css` `.admin-meta-bundle` 에 `flex-shrink: 0` 추가. `#metadataList`(overflow-y:auto flex-column, 높이 제약)에서 카드가 flex 압축 + card `overflow:hidden` 클리핑되던 것을 자연 높이 유지로 해소.
- 무회귀: JS/HTML/백엔드/RBAC/엔드포인트/스키마 0. CSS 선언 1 + 주석. cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: 라이브 win-browser 주입 검증(카드 12px→166px). POST-DEPLOY PB-0008 재검증 예정.
- Files: `unit/feature-0003-agent-web-ui/src/static/styles.css`, `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260715T113208-enum-bundle-flex-fix.md`.
- Cross-ref: 원천 CHG-20260715T105337-enum-review-bundle · ANCHOR 0003 무충돌.

## CHG-20260715T120000-enum-review-bundle-postverify (ENUM 검토 큐 묶음 승인 체크리스트 + flex-fix POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. CHG-20260715T105337-enum-review-bundle(PR #811, f6cb0b14) + CHG-20260715T113208-enum-bundle-flex-fix(PR #817, a3c69103) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- Changes: `docs/test-runs.d/20260715T105337-enum-review-bundle.md` + `docs/test-runs.d/20260715T113208-enum-bundle-flex-fix.md` POST-DEPLOY append + `docs/TASK.md` 두 cycle post-deploy 박스 close.
- 실증(win-browser eval, bootstrap_admin, 주입 없이): (bundle) `/admin` ENUM 검토 큐 12후보 → 8묶음 그룹핑·전체 승인 마스터·일부 해제 indeterminate/힌트·등록 count/disabled 로직 PASS. (flex-fix) 재배포 자산(a3c69103·styles.css 62c4b695387d) 카드 높이 [166…298] 자연 높이·flex-shrink=0·목록 스크롤·sliver 해소·pageError 0.
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/test-runs.d/{20260715T105337-enum-review-bundle,20260715T113208-enum-bundle-flex-fix}.md`.
- Cross-ref: 원천 CHG-20260715T105337-enum-review-bundle · CHG-20260715T113208-enum-bundle-flex-fix · ANCHOR 0003 무충돌.

## CHG-20260715T135725-graph-ctxmenu-content-category (TASK-20260715T135725-graph-ctxmenu-content-category — 그래프 우클릭 3대상 정합: 컨텐츠 카테고리 전용 메뉴 신설 + band-wins 철회, Major §12.3 frontend-only)
- Date: 2026-07-15. 사용자 정정("'제품 카테고리 밴드'를 '내부 노드를 컨텐츠 단위로 묶은 클러스터=컨텐츠 카테고리'로 착각") → band-priority(CHG-20260715T114608) 전제 무효. 그래프 우클릭 3층 정합: 제품 카테고리 밴드=카테고리 / 스키마 클러스터=스키마 / 컨텐츠 카테고리(sim-group)=신설 전용 메뉴.
- `static/graph/graph-renderer-pixi.js` (band-wins 철회):
  - `PixiGraphAdapter._pickContext(mx,my)` 제거. `up()` 우클릭(button===2)은 다시 `d.hit`(=`_pick`, WYSIWYG)로 emit — 좌클릭·드래그와 동일 hit. 밴드 위 스키마 클러스터 우클릭 → 스키마 메뉴(카테고리 승격 제거).
- `static/graph/graph-ctxmenu.js`:
  - 신규 `_metaGraphCtxForContentCategory(gk,x,y)` + export. gk 형식 "<schemaKey>\u0001<token>". 헤더 배지 '컨텐츠 카테고리'(#8a3f7a)+label·테이블수 / 📋 소속 스키마 상세(`_metaGraphShowClusterDetailById`) / 접기·펼치기 (묶음)(`groupCollapsed` 토글+`_metaG6Apply(false)`) / 묶음명 복사. groupInfo miss 시 token 폴백(안전).
- `static/graph/graph-core.js`:
  - `node:contextmenu` GB/GH/GX 분기: `_metaGraphCtxForSchema(gk.slice(0,sep))` → `_metaGraphCtxForContentCategory(gk)`. import 추가.
  - `_metaGraph.groupInfo` 신설 · `_metaG6Build` reset + sim-group emission 전량 적재({label,n,schema}, 접힘/펼침 무관).
- `static/graph/graph-state.js`: `groupInfo: new Map()` 초기화(groupMembers 패턴 정합).
- `tests/headless/test_pixi_adapter.js`: T22 를 band-wins → 컨텐츠 카테고리 회귀로 교체(GB/GH 자기노드·밴드 흡수 안 함 · 밴드 위 스키마카드→SC · `_pickContext` undefined). ALL PASS 66/0.
- 비변경: 좌클릭(GB/GH 상세, GX 접기)·드래그(sim-group 리지드 이동)·제품 카테고리 밴드/스키마 클러스터 메뉴·dispatch 타 분기·시각 z·백엔드/RBAC/스키마 0.
- 검증: `node --check`(4 파일) PASS · 헤드리스 66/0 · §18.8 적대 패널. POST-DEPLOY PB-0008 라이브 잔여(visual_verification_scope: always).
- Cross-ref: TASK/REVIEW-20260715T135725-graph-ctxmenu-content-category · test-runs.d/20260715T135725-graph-ctxmenu-content-category.md · **철회 대상 CHG-20260715T114608-graph-ctxmenu-band-priority** · 유지 선행 CHG-20260715T102901-graph-ctxmenu-hittest(WYSIWYG _pick 3-tier) · ANCHOR 0003 무충돌.

## CHG-20260715T140000-graph-ctxmenu-content-category-postverify (그래프 우클릭 3대상 정합 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. CHG-20260715T135725-graph-ctxmenu-content-category(PR #820, main 66722981) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- 실증(win-browser Chrome 150, 배포 66722981): ① sim-group "방송 계정·3"(mysql-kr-an2-player dbGame) 우클릭 → **컨텐츠 카테고리** 메뉴 / ② 밴드 위 스키마 클러스터(dbAuth) → **스키마**(band-wins 철회 복원) / ③ 제품 카테고리 밴드 → **카테고리** / 개별 테이블 → **테이블**(흡수 안 됨). 서빙 자산 baked(`_pickContext` 메서드 0·우클릭=`_pick`·ContentCategory 라우팅·groupInfo)+브라우저 in-page fetch(stale 아님) 확인.
- Changes: `docs/test-runs.d/20260715T135725-graph-ctxmenu-content-category.md` POST-DEPLOY 섹션 DEFERRED→PASS · `docs/TASK.md` 체크리스트 close · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T135725-graph-ctxmenu-content-category · ANCHOR 0003 무충돌.

## CHG-20260715T082345-picker-case-preserve (제품 접근DB write-path 서버-실제-case 정규화 — B ingestion, cross-ref feature-0002 FR-schema-name-case-drift)
- Date: 2026-07-15. 계기: `/_dqa:conversation_audit` "테이블 구조 정합성 검토" 마찰의 ingestion 근본 — 스키마 whitelist 가 소문자로 저장돼 case-sensitive MySQL 에서 assistant 조회 0행(정본 근본·봉인 = feature-0002 CHG-20260715T082345-schema-name-case-drift).
- Reason(RC, §18.8 적대 패널 재진단): 초기 후보(admin_console picker `.lower()` 제거)는 **실효 없음**으로 기각 — (a) 그 picker(`/api/admin/databases/available`)는 미바인딩 default 폴백 전용이고 실 바인딩 picker 는 `list_server_databases_classified`(이미 실제 case), (b) **admin.js(11277/11366)가 MySQL 스키마명을 저장 직전 `.toLowerCase()`** 해 서버-측 picker case 보존을 무효화. 실 소문자화는 프론트 + write path 무정규화의 합작.
- Changes(feature-0003): `src/routers/admin_products.py` `admin_update_product_databases` — 저장 직전 `cleaned` 스키마명을 datasource 서버 **실제 case**(`shared.db.list_server_databases`, SSRF-pin 선행)로 정규화. **엔드포인트/프론트 case 무관 backend chokepoint** — admin.js 소문자화·수기 소문자 입력 모두 write 시점에 서버 실제값으로 고정. degrade-safe(datasource 미해소·SSRF 차단·연결 실패·모호[대소문자만 다른 동명 복수] → 입력 case 유지·저장 차단 안 함). MySQL only(MSSQL catalog case-insensitive). admin_console picker 변경은 **원복**(wrong-endpoint·무효).
- 검증: 신규 `tests/test_product_databases_case_normalize.py` 2 PASS(소문자 입력→서버 실제 case 저장·degrade-safe). feature-0003 전체 회귀 무영향(2113 passed 통합).
- 한계(§정직, deferred): admin.js 소문자화 자체는 미수정(프론트·visual verification 필요·write-path 정규화가 상쇄) · datasource-scoped picker 실제 case 표시(후속) · 기존 저장 소문자 행 백필은 admin 별도(A 런타임 canonicalize + 재저장 시 write-path 정규화가 점진 seal).
- Cross-ref: **primary = feature-0002 CHG-20260715T082345-schema-name-case-drift**(런타임 resolution seal·verify 정본) · REV-20260715T082345-schema-name-case-drift(패널) · FRICTION_LEDGER FR-schema-name-case-drift.

## CHG-20260715T181939-graph-edge-follow-drag (그래프 뷰 노드/제품 카테고리 드래그 시 관계선 미추종 수정 — PixiJS incident 엣지 증분 재그림)
- Date: 2026-07-15. 계기: 사용자 보고 "그래프 뷰에서 좌클릭 드래그로 제품 카테고리를 옮길 때 관계선이 옮기기 전 위치에 그대로 출력(줌 아웃으로만 갱신)". 작업 중 사용자 정정: "cross-category 엣지(다른 제품 카테고리로 가는 연결선)의 구조 갱신이 핵심".
- 근본원인: PixiJS 렌더러에서 엣지는 절대 model 좌표(a,b)를 Graphics path 에 bake 한 **world 직속 독립 오브젝트**(`_drawEdge`)라 노드 Container 이동으로 따라오지 않는다. 드래그 경로 `_moveElement`/`translateElementTo` 는 노드 style/position 만 갱신 + `_render()`(단순 repaint)만 호출 → incident 엣지 옛 좌표 유지. full `draw()`(줌 밴드 LOD rebuild)만 `edgeSig(e,a,b)` 끝점 변경을 감지해 recreate → "줌 아웃해야 갱신".
- Changes(feature-0003, frontend-only 1 파일 + 테스트):
  - `src/static/graph/graph-renderer-pixi.js`: 신규 `_refreshIncidentEdges(movedIds)` — `this._built.edges` 중 `source||target ∈ movedIds` 인 엣지만 old destroy→removeChild→`_drawEdge(e,a,b)`→addChild→`_objs.set`, `_objSig.set(eid, edgeSig(e,a,b))`(다음 full draw 재사용). 좌표는 `getElementPosition`(draw() 의 pos 계산과 동형). `_moveElement` 노드분기(`[id]`)·combo분기(이동 자식 id 수집)·`translateElementTo`(이동 노드 id 수집) 에서 `_render()` 직전 호출.
  - `tests/headless/test_pixi_adapter.js`: T23 신규 7종(prototype call + stub world/_drawEdge — incident 선택 e1(내부)·e2(cross-category) 재그림·e3 skip / cross-category 이동끝점 새좌표·미이동끝점 옛좌표 / _objs·world 교체 / _objSig 갱신 / 빈·null no-op). ALL PASS 73/0.
- cross-category 보장: OR 판정 — 한끝(이동 카테고리 구성원)만 movedIds 에 있어도 재그림, 이동 끝점 새 좌표 + 미이동 끝점 현재 좌표로 연결선 구조 갱신(사용자 정정 케이스). 카테고리 드래그는 `graph-core._metaNodeDrag` 가 전 구성원을 `translateElementTo` 로 이동시키므로 본 chokepoint 가 커버.
- 비변경: 팬/줌·상태·미니맵·hover-fx·우클릭 메뉴·클릭·백엔드/RBAC/스키마/마이그레이션 0. full `draw()` diff 경로 불변.
- 한계(정직, deferred): 허브 노드(수천 incident 엣지) per-frame 재그림 비용 — full draw() 보다 저렴하고 정확성 필수 최소치, rAF 스로틀은 후속(§76 계열).
- 검증: `node --check` PASS · 헤드리스 73/0 · §18.8 적대 리뷰 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T1819 · REV/TEST-20260715T181939-graph-edge-follow-drag · test-runs.d/20260715T1819-graph-edge-follow-drag.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## CHG-20260715T190000-graph-edge-follow-drag-postverify (그래프 관계선 추종 수정 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. CHG-20260715T181939-graph-edge-follow-drag(PR #824, main 0f26cec1) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- 실증(win-browser 실 Windows Chrome 150, relay, 배포 0f26cec1): PixiJS 그래프 루트 뷰(제품 카테고리 14 + 데이터소스 18 + cross-category 관계선)에서 제품 카테고리 "건즈-개발·1"을 합성 PointerEvent(button0)로 드래그 → **pointerup 전·줌 없이** mid-drag 스크린샷에서 관계선이 이동한 새 위치를 그대로 추종(옛 위치 잔상 0). dragend 후에도 정합(ADR-004 자유배치 영속). pageerror 0. 서빙 자산 `_refreshIncidentEdges` grep=4(baked). evidence: graph_root·graph_middrag·graph_after_reset.
- Changes: `docs/test-runs.d/20260715T1819-graph-edge-follow-drag.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T181939-graph-edge-follow-drag · ANCHOR 0003 무충돌.

## CHG-20260715T211911-graph-cluster-detail-routines (스키마 클러스터 상세 패널: 함수·프로시저만 있는 컨텐츠 카테고리 누락 수정, Minor §12.3)
- Date: 2026-07-15. feature-0003 web/UI 프론트 단독(1파일). 그래프 도메인 정본 feature-0016. `/_template:entry` arg-given dispatch.
- 사용자 보고: 상세 패널의 컨텐츠 카테고리가 테이블만 집계 → 함수·프로시저만 있는 컨텐츠 카테고리(예: "상점 아이템 명칭")가 목록 누락. 해당 항목도 조회되게 구성.
- 근본원인: 캔버스 build(`graph-core.js` L64~L78)는 Table+Routine 을 모두 `g.tables` 에 넣어 `_metaSimGroups` 로 함께 sim-group(컨텐츠 카테고리)화하나, 스키마 클러스터 상세 패널 진입점(`_metaGraphShowClusterDetailById`·`_metaGraphShowClusterDetailLocal`)과 렌더(`_metaGraphRenderClusterDetail`)는 `label === "Table"` 만 집계 → Routine-only 컨텐츠 카테고리 누락 + 캔버스와 불일치.
- Changes:
  - `src/static/graph/graph-ctxmenu.js`:
    - `_metaGraphShowClusterDetailLocal`: `label === "Routine" && _metaCatParent(n.key,n.fqn)===comboId` 수집·정렬 → `routines` 인자로 렌더 전달.
    - `_metaGraphShowClusterDetailById`: 모델에서 routines 수집(API 응답 형태 무관 — 패널은 화면 내 스키마라 모델 보장) → 렌더 전달 + status 라인 함수·프로시저 개수 노출.
    - `_metaGraphRenderClusterDetail(name,fqn,tables,childTables,childCols,totalOverride,truncated,comboId,routines)`: `members=tables.concat(routines)` 로 `_metaSimGroups`/렌더. Routine 행 = ƒ/⚙ 보라 칩(`_META_GRAPH_COLOR.Routine`) 접두사, 클릭 → `_metaGraphShowDetail`(API 조회, routine 키 동작). 설명/섹션 제목/그룹 aria-label 병합집합 반영. 테이블 개수·cap 절단(nTables/truncNote)은 테이블 기준 유지.
- 정합성: 패널 sim-group 입력을 캔버스와 동일 Table+Routine 병합집합으로 맞춤 → 상세 패널 컨텐츠 카테고리가 캔버스와 일치. `_metaSchemaComboOf(Routine)`==`_metaCatParent(...)` 동일 predicate 로 membership 정합.
- 비변경: 제품 카테고리 패널(스키마 목록)·캔버스 build·우클릭 메뉴·드래그·상태·백엔드/RBAC/스키마/엔드포인트 0. Table-only 스키마 회귀 0(문구만 확장). cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: `node --check`(module) PASS · §18.8 적대 리뷰 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T2119 · REV/TEST-20260715T211911-graph-cluster-detail-routines · test-runs.d/20260715T2119-graph-cluster-detail-routines.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## CHG-20260715T215241-graph-cluster-detail-cap (스키마 클러스터 상세: 목록 행 캡이 함수·프로시저 컨텐츠 카테고리를 통째 숨기던 문제 수정, Minor §12.3)
- Date: 2026-07-15. feature-0003 web/UI 프론트 단독(1파일). cluster-detail-routines(CHG-20260715T211911) POST-DEPLOY PB-0008 후속. 그래프 도메인 정본 feature-0016.
- 트리거: cluster-detail-routines 배포 후 라이브 검증에서, gunzgame 클러스터 상세(409항목=테이블 115+함수·프로시저 294)의 집계·개수는 정확하나 목록에 렌더된 컨텐츠 카테고리가 앞쪽 테이블 be: 클러스터 10개(80행)뿐 — 함수·프로시저 컨텐츠 카테고리가 한 개도 안 보임을 적발.
- 근본원인: `_metaGraphRenderClusterDetail` sim-group 렌더가 전역 80행 캡 도달 시 이후 그룹 통째 skip(`if (emitted >= 80) return`). sim-group 순서가 be: 의미 클러스터(테이블) 우선이라 대형 스키마에서 앞쪽 테이블 그룹이 80행 소진 → 뒤쪽 routine 컨텐츠 카테고리(헤딩 포함) 전체 렌더 누락. 집계 포함(cluster-detail-routines)만으로는 시각적 조회 불가.
- Changes:
  - `src/static/graph/graph-ctxmenu.js` `_metaGraphRenderClusterDetail` 캡 규약 개정: (1) `if (emitted >= 80) return` 제거 → **모든 컨텐츠 카테고리 헤딩 항상 방출**(카테고리 가시·조회 가능). (2) 멤버 행 캡을 그룹당 PER_GROUP=25 + 전역 ROW_CAP=500 로 재구성(`shown = min(sg.n, 25, max(0, 500-emitted))`) — 한 그룹 예산 독식 방지 + 패널 길이 바운드(aside overflow-y:auto). 절단은 그룹별 `(shown/n)`. (3) flat 폴백 `slice(0,80)`→`slice(0,500)`.
- 회귀: 소형 스키마(≤80·그룹 ≤25) 동일. 그룹 멤버 >25 인 그룹만 25 표시 + `(25/n)`(예 gunzgame "캐릭터 정보 및 랭킹" 32→25) — routine 카테고리 전면 가시화 위한 수용 트레이드오프.
- 비변경: cluster-detail-routines 집계/membership/hiddenKinds/렌더 분기·백엔드/RBAC/스키마 0. cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: `node --check` PASS · §18.8 [SKIPPED] 적대 자가검토(display-cap 상수·헤딩 방출, 경계·주입·RBAC 무관) · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T2152 · REV/TEST-20260715T215241-graph-cluster-detail-cap · test-runs.d/20260715T2152-graph-cluster-detail-cap.md · 선행 CHG-20260715T211911-graph-cluster-detail-routines · ANCHOR 0003 무충돌.

## CHG-20260715T220941-graph-cluster-detail-postverify (그래프 클러스터 상세 함수·프로시저 컨텐츠 카테고리 수정 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. cluster-detail-routines(CHG-20260715T211911, PR #827 main 1b370dfd) + cluster-detail-cap(CHG-20260715T215241, PR #828 main cdee785e) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- 실증(win-browser 실 Windows Chrome 150 relay, 배포 cdee785e, 로그인 세션): 그래프 뷰 > mysql-gz-dev > gunzgame 스키마 카드 클릭 → 상세 패널에서 (1) 컨텐츠 카테고리 그룹 **72개** 렌더(cap 수정 전 10개), 함수·프로시저-only 그룹 **51개**(수정 전 0개 — "계정 조회" 24 routine·"캐릭터 인벤토리" 25·"아이템 구매" 15·"아이템 정보" 13·"재화 변환" 5·"스팀 캐시 관리" 3·"로그인 보상" 2 등), (2) `⚙ Game_AllItemGet`(gunzgame.Game_AllItemGet()) 클릭 → "ROUTINE / ⚙ 프로시저 / 이웃 2개" 노드 상세 조회, (3) 섹션 "테이블·함수·프로시저 (409)"·설명 "테이블 115개 · 함수·프로시저 294개", (4) 캔버스 sim-group 과 패널 컨텐츠 카테고리 일치, (5) pageerror 0. 서빙 자산 baked(`ROW_CAP = 500` grep=1 web-a/web-b). evidence: gz_routine_groups.png.
- Changes: `docs/test-runs.d/20260715T2119-graph-cluster-detail-routines.md` Run 3 DEFERRED→PASS(집계) · `docs/test-runs.d/20260715T2152-graph-cluster-detail-cap.md` Run 4 DEFERRED→PASS(라이브) · `docs/TASK.md` 두 cycle POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T211911-graph-cluster-detail-routines · CHG-20260715T215241-graph-cluster-detail-cap · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## CHG-20260715T223744-graph-cluster-detail-fulllist (스키마 클러스터 상세: 컨텐츠 카테고리 목록 전체 출력 + 행 상호작용 이벤트 위임, Minor §12.3)
- Date: 2026-07-15. feature-0003 web/UI 프론트 단독(1파일). cluster-detail-cap(CHG-20260715T215241) 후속. 그래프 도메인 정본 feature-0016.
- 사용자 보고: 컨텐츠 카테고리 일부만 집계 — `(3/5)`·`(0/N)`. 원인·전체 출력 가능 여부 문의.
- 근본원인: 직전 cluster-detail-cap 의 전역 상한 ROW_CAP=500 + 그룹당 25. 멤버 총합 500 초과 스키마에서 500행 소진 후 그룹 헤딩+0행/경계 그룹 부분 표시.
- Changes:
  - `src/static/graph/graph-ctxmenu.js` `_metaGraphRenderClusterDetail`:
    - 캡 사실상 해제: 그룹당 캡 제거, 전역 안전가드 ROW_CAP 500→5000. `shown = min(sg.tables.length, max(0, 5000-emitted))` → 전체 멤버 렌더. flat 폴백 500→5000. 헤딩 항상 방출·`(shown/n)` 유지.
    - 행 클릭/hover 바인딩을 per-row(`_metaBindHoverPan` 4리스너 + 클릭 1) → 컨테이너 `ul.amgr-cluster-tables` 이벤트 위임(리스너 O(1)). ul 매 렌더 재생성이라 누적 없음. mouseover/out·focusin/out(버블)+`_hoverKey`+`relatedTarget` 검사로 원본 hover 의미 보존. 클릭 `closest(".amgr-ct-row[data-node-key]")`.
- 비변경: 집계/membership/hiddenKinds/sim-group/헤딩/XSS·백엔드/RBAC/스키마 0. cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: `node --check` PASS · §18.8 적대 리뷰(위임 누적·hover 의미·클릭 동등성) · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T2237 · REV/TEST-20260715T223744-graph-cluster-detail-fulllist · test-runs.d/20260715T2237-graph-cluster-detail-fulllist.md · 선행 CHG-20260715T215241-graph-cluster-detail-cap · ANCHOR 0003 무충돌.

## CHG-20260715T231304-graph-cluster-detail-fulllist-postverify (컨텐츠 카테고리 전체 출력 + 이벤트 위임 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. cluster-detail-fulllist(CHG-20260715T223744, PR #830 main 41cf76c5) 배포 후 win-browser PB-0008 라이브 실증. 코드 변경 0(문서 전용).
- 실증(실 Windows Chrome 150 relay, 배포 41cf76c5, 로그인 세션): 그래프 뷰 > mssql-dk-dev(DK온라인) > `dk_data_release_main`(123 테이블 + 300 함수·프로시저 = 423항목) 상세 → (1) 컨텐츠 카테고리 그룹 **66개 전량 렌더 · 423행 · (0/N) 0 · 절단 0 · routine-only 43그룹**("NPC 콘텐츠 41" 등), aside scrollH 12423, (2) 행 자식(`<code>`) 합성 click → 이벤트 위임 승격 → `singleinfo` 노드 상세 조회, (3) pageerror 0. 서빙 자산 baked(`ROW_CAP = 5000`·`_ctUl` grep=9). evidence: relmain_full.png.
- 주(정직): 사용자 스크린샷의 정확한 >500 스키마(gemstone/binto32/merchant — DK QA/production 추정)는 좌표 특정 못 함. 단 검증한 423/66그룹 스키마 전량 렌더 + ROW_CAP=5000 결정론(적대 리뷰 확인)으로 해당 >500 스키마도 (0/N) 없이 전체 표시됨.
- Changes: `docs/test-runs.d/20260715T2237-graph-cluster-detail-fulllist.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T223744-graph-cluster-detail-fulllist · ANCHOR 0003 무충돌.
