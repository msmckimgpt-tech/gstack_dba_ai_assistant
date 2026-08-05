---
doc_type: REVIEW
feature_id: feature-0038-frontend-modularization
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260803T174500-css-split
- Related Change: CHG-20260803T174500-css-split (Cycle 1 — ITEM-P5b 잔여, PLAN-APPROVED by mckim 2026-08-03)
- Reason: ssot-consolidation ROADMAP ITEM-P5b 실측 갱신(2026-08-03) — 백엔드는
  feature-0012 완결, 잔여 실체는 프론트 3파일(+23~59% 증가 중). styles.css 가
  가장 저위험(선언적·byte-parity 증명 가능)이라 Cycle 1 로 선행하고, 이 cycle 에서
  롤백 리허설을 실증해 이후 JS cycle 의 절차를 고정한다.
- Alternatives Considered:
  - 사용처 기준 재그룹(페이지별 CSS 분리 — index 전용/admin 전용): 셀렉터 사용처
    전수 분석이 필요해 behavior-neutral 증명이 불가능 → 기각. 순차 분할은 "concat ==
    원본" 이 증명이 된다. 재그룹은 분할 정착 후 후속 개선으로 이연.
  - `@import` 체인: 직렬 로딩 성능 저하 + 프로젝트 선례(link 나열, graph.css) 위배 → 기각.
- Risks:
  - **pre-existing 주석 결함 1건 보존**: 구 styles.css L5577 (`admin.css` L1880)
    `/* … --text*/ …` 가 주석을 조기 종료시키고 잔여 토큰이 무효 CSS 로 error-recovery
    되는 상태 — 원본에 이미 존재하며 분할 후에도 같은 파일 내에 온전히 보존되어 동작
    동일. 본 cycle 은 behavior-neutral 계약이라 **수정하지 않고 기록만** 한다 (후속
    cycle 또는 별도 Minor fix 후보).
  - 분할 파일 수 7 = HTTP 요청 증가: Caddy HTTP/2 + immutable 스탬프 캐시로 무시 가능.
  - stale PoC 참조: `unit/feature-0016-metadata-graph/pixi-migration/poc/integration-harness.html`
    이 구 styles.css 절대경로를 참조 — 개발용 PoC(비서빙)이고 feature-0016 활성 세션
    영역이라 본 cycle 에서 손대지 않음 (REPORT §8 기록).
- Open Questions: 없음
- Human Approval Needed: 완료 — PLAN-APPROVED by mckim on 2026-08-03 (TASK.md §2.1,
  risk_grade Critical 은 ROADMAP ITEM-P5b 지정 등급. 본 cycle 실변경은 byte-parity
  증명이 있는 CSS 물리 분할로 회귀 표면 최소)

## REV-20260803T181500-css-split-panel [SUBAGENT:qa] — SHIP
- Related Change: CHG-20260803T174500-css-split (Cycle 1)
- 패널: fresh-context 적대 1렌즈(qa/frontend — behavior-neutrality 반박 시도, 전 항목 실측 명령 동반). **BLOCKING 0 / MAJOR 0 / MINOR 2.**
- 실측 확인: ① concat byte-identical(322,993B, sha256 일치·link 순서 정합) ② html 배선(7-link 순서·구 링크 잔존 0·graph.css 후순 유지·vendor pin 미접촉·share.html 무변경) ③ per-file 파싱(주석 토크나이저·brace 스캐너 전 파일 균형·고아 `}` 0·`--text*/` quirk 는 파일 중앙 보존) ④ 잔여 참조 0(런타임/테스트 실읽기 기준·JS 동적 stylesheet 조작 0·synthetic fixture 2건은 실파일 미참조) ⑤ 테스트 5파일 순서 정합 + py_compile/ruff PASS ⑥ inject_asset_stamp 재귀 커버·vendor 제외 오폭 없음·decide_cache_control 경로 무관·deploy asset_stamp_verify 커버.
- MINOR 흡수: ② 3연속 빈 줄 코스메틱 → 본 commit 에서 정리. ① CSS 요청 수 1→7(head 내 render-blocking 이라 FOUC 없음·HTTP/2) → 수용(기록만).
- 판정: **SHIP** — behavior-neutral 주장 반박 실패.
- Timestamp: 2026-08-03T18:15:00+09:00

## REV-20260803T193000-usage-aiops-panel [SUBAGENT:qa] — BLOCK → 전건 흡수 후 SHIP-경로
- Related Change: CHG-20260803T190000-usage-aiops-split (Cycle 2)
- 패널: fresh-context 적대 1렌즈(qa/frontend — acorn/acorn-globals 자유 식별자 스캔·역재구성 parity·컨테이너 실 pytest·AST 문자열 리터럴 전수). **판정: 초안 BLOCK — BLOCKING 1 / MAJOR 1 / MINOR 3.**
- **BLOCKING (흡수)**: aiops.js 가 admin.js module-scope `$`(getElementById 헬퍼)를 import 없이 6개소 사용 — loadAiOps 첫 줄(try 밖) ReferenceError 로 '운영 현황' pane 영구 공백(initialized 선세팅 탓 재진입 복구 불가). 작성자 식별자 스캔이 `\b`+`$` regex 함정으로 누락한 것을 acorn-globals 가 적발. → admin.js `export const $` + aiops.js import 로 수정, **재검: acorn-globals free-vars usage/aiops = 0/0**.
- **MAJOR (흡수)**: 이동 경계가 주석-코드 정합 3곳 파괴(TASK-0198 주석 고아 잔류·TASK-0288 주석 usage 꼬리 오이동·feature-0021 주석 aiops 꼬리 오이동) → 경계 재절단(usage=구 L1560–2238·aiops=구 L2352–2626, 선행 주석 포함/후행 이웃 주석 제외) 후 HEAD 에서 재생성. **재검: 역재구성 byte-parity IDENTICAL 유지**.
- **MINOR (흡수 2·기록 1)**: app.js L2732·admin.html L614 stale 포인터 주석 갱신. F1 부재 단언(`"loadQuotas" not in js`)의 분리 모듈 사각은 현재 실해 없음 — 기록만.
- 패널 권고 채택: **acorn-globals 자유 식별자 게이트를 분할 cycle 표준 검증에 추가** (TASK §2.1 게이트 2에 편입 — 합본 문자열 테스트가 원리적으로 못 잡는 부류).
- 패널 clean 실측: 역재구성 parity(sha256 동일)·TDZ top-level 실행문 0·잔여 참조 0·테스트 21+27 passed 컨테이너 실측·문자열 리터럴 39건 전수 오탐 0·스탬프 재귀 커버·admin.html 무변경 정당.
- Timestamp: 2026-08-03T19:30:00+09:00

## REV-20260804T090000-settings-audit-panel [SUBAGENT:qa] — SHIP
- Related Change: CHG-20260803T203000-settings-audit-split (Cycle 3)
- 패널: fresh-context 적대 1렌즈(qa/frontend — 7항목 전부 실측: 역재구성 parity·acorn-globals·TDZ AST·30모듈 링크체크·AST 리터럴 대조·컨테이너 pytest 62건·census e2e). **BLOCKING 0 / MAJOR 0 / MINOR 2.**
- 실측 확인: ① 역재구성 cmp IDENTICAL(본문 862+379줄 치환·export 접두 5 제거) ② 4모듈 자유 식별자 0 ③ TDZ — audit top-level 실행문 0·SETTINGS_PANEL_MOUNTERS 참조 전부 동일 모듈 함수 선언·re-export 는 링크 단계 직결이라 순환 무해(근거 제시) ④ 미-import 잔여 참조 0 + 전 static 30모듈 export↔import 링크 에러 0 ⑤ 대표 4파일 컨테이너 pytest 62 PASS·F1 합본 충분 ⑥ 스탬프 재귀 커버·Dockerfile COPY 재귀·census e2e PASS ⑦ window 대입·인라인 onclick 0.
- MINOR (기록): ① verify_admin_tab_gating.mjs 2건 FAIL 은 **pre-existing**(HEAD·Cycle 2 이전 기준선에서 동일 재현 — 본 변경 무관, make test 미포함이라 CI 사각) → REPORT §8 추적 등록. ② audit.js 의 raw fetch 병용은 byte-이동 산물(기존 동일 동작).
- 판정: **SHIP** — 반박 실패.
- Timestamp: 2026-08-04T09:00:00+09:00

## REV-20260804T110000-accounts-roles-panel [SUBAGENT:qa] — BLOCK → 전건 흡수 후 SHIP-경로
- Related Change: CHG-20260804T100000-accounts-roles-split (Cycle 4)
- 패널: fresh-context 적대 1렌즈(qa/frontend — 7항목 실측 + headless chromium 모듈 그래프 실로드·단일 인스턴스 확인·컨테이너 pytest). **판정: 초안 BLOCK — BLOCKING 1 / MAJOR 1 / MINOR 2.**
- **BLOCKING (흡수)**: test_llm_usage_quota f1/f2 가 admin.js 단독 검사인데 quota 편집기 call-site('scope: "account"'·can("quota.read") 등)가 양 pane 으로 이동 — make test **RC=2** 실측. → `_read_admin_bundle()`(admin+accounts+roles 합본) 전환, f1 negative 단언 합본 성립 패널 실측 완료.
- **MAJOR (흡수)**: verify_profile_icon_admin_surfaces.mjs(standalone, CI 비배선) admin.js 단독 read 5단언 회귀 → 합본 전환 후 **17 PASS / 0 FAIL 실측**(jsdom 22.1.0 임시 설치·정리).
- **MINOR (흡수 1·기록 1)**: admin.js dead import(filteredAccounts — roles.js 직접 import 로 대체) 제거 후 parity IDENTICAL 재검. verify_perm_self_scope.mjs 는 ITEM-09 type=module 전환 이래 pre-existing 파손(무귀책) — REPORT §8 추적.
- 패널 clean 실측: 역재구성 cmp IDENTICAL(델타 -1386/+25 전수 일치)·6모듈 free-vars 0·TDZ 0(ACCOUNT_PAGE_SIZE 함수 내부 9개소)·roles→accounts 평가순서 근거·32모듈 링크 정합·권한 grid 호출 2곳 이동-내부 byte-동일·스탬프 모듈 간 import 재작성 커버(files_rewritten=18 실측).
- Timestamp: 2026-08-04T11:00:00+09:00

## REV-20260804T133000-products-datasources-panel [SUBAGENT:qa] — BLOCK → 전건 흡수 후 SHIP-경로
- Related Change: CHG-20260804T120000-products-datasources-split (Cycle 5)
- 패널: fresh-context 적대 1렌즈(qa/frontend — 7항목 실측 + node DOM-stub 전 그래프 link+eval + 스탬프 실주입 + verify_*.mjs 전수 양-트리 스윕 + 컨테이너 pytest 157 passed). **판정: 초안 BLOCK — BLOCKING 1 / MAJOR 0 / MINOR 2.**
- **BLOCKING (흡수)**: verify_profile_icon_consistency.mjs — admin.js 단독 직독 단언("'(약어) 명칭' 3건")이 이동으로 1+2 분산돼 22P/1F→21P/2F 신규 회귀. 같은 cycle 이 chip_list 에 적용한 합본 전환을 자기 변경에 미적용한 누락. → 합본 전환 후 **22/1 기준선 복구 실측**.
- **MINOR (흡수 ①)**: dead import 5건(주석만 참조 — 표면 산출이 주석 텍스트까지 식별자로 집계한 방법 결함) 제거 + dead export 3건(applyAllPending·identiconSvg·_DS_CONN_MAX) 원복 → parity IDENTICAL(export 19 규칙)·free-vars 0/0 재검. **교훈: 이후 cycle 의 표면 산출은 주석-제거 후 스캔으로 보정.**
- **MINOR (② 절차 반영)**: 신규 2파일 untracked — 커밋 시 git add 포함 확인(finalize 체크).
- 패널 clean 실측: 역재구성 sha256 동일·8모듈 free-vars 0(admin.js 3건은 HEAD 동일 pre-existing 브릿지)·TDZ 0(ENGINE_BY_VALUE 모듈-로컬만)·import 바인딩 쓰기 9모듈 0·전 그래프 link+eval OK·pending 엔진(§10.7) admin.js 잔류 + products 35회 import 사용 온전·스탬프 실주입 3 specifier 동일 스탬프.
- Timestamp: 2026-08-04T13:30:00+09:00

## REV-20260804T170000-metadata-panel [SUBAGENT:qa] — BLOCK → 전건 흡수 후 SHIP-경로
- Related Change: CHG-20260804T150000-metadata-split (Cycle 6)
- 패널: fresh-context 적대 1렌즈(7항목 실측 — sha256 양측 동일 기계증명·diff 회계 11/2853 완전 일치·acorn-globals 9모듈·실 ESM 그래프 평가(TDZ 0·56 exports)·스탬프 실주입 멱등·컨테이너 pytest 184 passed·mjs 39종 3-트리 대조). **판정: 이동 자체 전건 PASS — BLOCK 은 동반 수선 완결성 주장에 한정 (B3건/M0/m5).**
- **BLOCKING 흡수**: ① styles.css 직독 3건이 `staticDir` 변수명 차이로 스윕 누락(ENOENT 사망 유지) → 변수명 무관 리터럴 전수 재수선, 잔존 직독 0 실측 ② 구계약 cache-buster 단언 3건(bs_prefill [A8]·inline_desc [A5]·list_detail [C4]) → placeholder 신계약 적용 ③ 문서 오기(TEST Run-024·MODIFY·REPORT §8) → 실측대로 정정(아래).
- **패널 기준선 수치 반증 1건 (본 세션 재측정이 정본)**: inline_desc/list_detail 의 패널 기준선 26P/0F·26P/3F 는 오측 — fd61bb48 기준선 worktree 재생성 실측에서 **양 트리 동일 `ReferenceError: _metaScopeIsProduct`** 크래시 = metadata-product-scope(07-29) 이래 pre-existing (재현 절차 기록). 나머지 수선 후 실측: share_participants **17/0**(기준선 동치)·member_kick_ban 17/2·member_actions_hover 14/1·bs_prefill **44/0** — 전건 기준선 동치 이상.
- **MINOR 흡수**: mermaid dead import/export 제거(델타 축소)·admin.html stale 귀속 주석 2건 갱신·test_metadata_perm_split assert 메시지 정정. usage.js 의 _metaPopulateScopeSelect 런타임 미호출은 기록만(링크 계약상 re-export 필수 — 별도 정리 후보).
- Timestamp: 2026-08-04T17:00:00+09:00

## REV-20260804T193000-appjs-module-panel [SUBAGENT:qa] — SHIP
- Related Change: CHG-20260804T183000-appjs-module (Cycle 7 — B0)
- 패널: fresh-context 적대 1렌즈(7항목 실측 — AST 전수·동반 6스크립트 양방향 교차대조·inject_asset_stamp 계약·index.html 소비 테스트 7종 **HEAD↔변경 A/B 실행 델타 0**·chromium 양팔 비교 headless 스모크 **module 팔 pageerror 0**). **BLOCKING 0 / MAJOR 0 / MINOR 3.**
- 실측 확인: deferred 안전(후행 classic 3종의 app.js 의존 0·역방향 0)·strict 위험 0(암묵 전역 대입·callee·top-level this 등 전수 0)·전역 소멸 무영향(inline 0·동적 onclick= 생성 0·self-window-read 0)·스탬프 재작성 무관·`window.toggleAuthPane` 등 undefined 화 실증에도 파괴 0.
- MINOR (기록): ① 이벤트 콜백 내 `this` 3건(L12266~) — **Cycle 8~10 분할 시 화살표 함수로 바꾸면 깨지는 잠복 지점, 분할 계획에 명기** ② 후행 classic 3종이 향후 app.js 전역을 참조하면 회귀 표면(주석 문서화로 수용) ③ PB-0008 eval 레시피의 top-level 함수 직접 호출 관행 불가 — DOM 이벤트 경유로 전환(도구 관행).
- Timestamp: 2026-08-04T19:30:00+09:00

## REV-20260805T093000-app-auth-profile-panel [SUBAGENT:qa] — SHIP
- Related Change: CHG-20260804T210000-app-auth-profile-split (Cycle 8)
- 패널: fresh-context 적대 1렌즈(7항목 실측 — 역재구성 sha256 동일·acorn-globals 0/0·엄밀 AST import-binding write 0·handleLogout 잔류 정당성 실증(유일 let 재할당)·이동 41심볼 잔여 참조 0·리터럴-대조 34파일 triage·컨테이너 pytest 111 passed·스탬프 실주입 24파일·**headless A/B 로그인 폼 submit→handleLogin 풀 경로 동작**). **BLOCKING 0 / MAJOR 0 / MINOR 5.**
- MINOR 흡수 3건: ① dead import/export(setupProfileDrawerResize — 유일 호출자가 모듈 내) 제거 ② profile-B 꼬리로 딸려간 `conv-date-tree` 주석 → 경계 재절단([2547,2993])으로 _ymdKey 와 재결합 ③ 모듈 헤더 레인지 off-by-one 정정. 재검: parity IDENTICAL·free-vars 0/0.
- MINOR 기록 2건: ④ win-browser 시나리오 json 의 `typeof openProfile` 전역 의존은 C7 ESM 전환 시점부터 pre-existing(도구 시나리오 정비 후보 — REPORT §8) ⑤ 줄수 표기 wc/split 관례 차이(무영향).
- Timestamp: 2026-08-05T09:30:00+09:00

## REV-20260805T133000-app-sidebar-panel [SUBAGENT:qa] — SHIP
- Related Change: CHG-20260805T110000-app-sidebar-split (Cycle 9)
- 패널: fresh-context 적대 1렌즈(7항목 실측 — 역재구성 cmp IDENTICAL(각주: export 앞 공백 1줄은 모듈 스캐폴딩으로 제외 규칙 명기)·acorn-globals 3모듈 앱-자유식별자 0·_dqaDrag 코드 참조 0 독립 실증(잔류 정당)·이동 22심볼 외부 참조 0·컨테이너 pytest 161+33 passed·스탬프 3참조 동일·**headless A/B — 사이드바 DOM 992B 완전 동일 + 새 폴더 생성→인라인 rename→Enter 커밋 클릭 플로우 동등·에러 0/0**). **BLOCKING 0 / MAJOR 0 / MINOR 3.**
- MINOR 흡수: 모듈 헤더 레인지 표기 통일(L2584–2908). 기록: 역재구성 규칙에 "마지막 세그먼트 말미 공백 1줄은 스캐폴딩" 각주(본 세션 재구성 스크립트는 동일 규칙으로 이미 IDENTICAL 판정)·줄수 wc/split 표기 관례 차이.
- 부가 확인: test_menu_action_permission_wiring 의 app.js 단독 스캔 게이트 침식 없음(sidebar.js 에 action: 리터럴 0).
- Timestamp: 2026-08-05T13:30:00+09:00

## REV-20260805T170000-app-messages-panel [SUBAGENT:qa] — SHIP
- Related Change: CHG-20260805T150000-app-messages-split (Cycle 10)
- 패널: fresh-context 적대 1렌즈(7항목 실측 — 역재구성 cmp 완전 일치(산술 정합 포함)·acorn-globals suspect 0·바인딩 양방향 0·잔여 참조 전부 export 집합 내부·테스트 33개 전수 재스캔 회귀 0·컨테이너 pytest 16+전체 스위트 RC=0·csv 하네스 22/0 기준선·mjs 19종 A/B FAIL-set 라인 단위 동일·스탬프 3참조 동일·**headless A/B — 4메시지 스텁 렌더 `#messageLog` innerHTML 8,253자 byte-동일·마커 7종 실증**). **BLOCKING 0 / MAJOR 0 / MINOR 3(표기류).**
- MINOR 기록: 줄수 960(문서 961 표기 정정)·SQL_FORMAT_KEYWORDS 리터럴 const 1건은 원본도 top-level(무해)·mjs jsdom 환경 이슈 pre-existing.
- Timestamp: 2026-08-05T17:00:00+09:00

## REV-20260804T194500-final-panel [SUBAGENT:qa] — BLOCK → 전건 흡수 후 SHIP-경로
- Related Change: Final (CONVENTIONS §14·ROADMAP done·완결 문서화)
- 패널: fresh-context 적대 1렌즈(docs/policy — 수치 전건 wc/git 실측 일치·PR 10건 해시 1:1·방법 서술↔REVIEW 기록 무모순·최소-diff 준수·차단 요인 코드 실증). **판정: 초안 BLOCK — B2/M2/m4.**
- **BLOCKING 흡수**: ① REPORT §3/§5/§7 계획-단계 stale(완결 선언과 모순) → 최신화 ② TASK §3 잔재 TASK-0100 중복 → 제거.
- **MAJOR 흡수**: ③ **날짜 오표기 정정** — 호스트 클록·git 커밋 정본은 2026-08-04 인데 Final diff 문서가 08-05 로 표기(작성자 날짜 진행 오인). 이번 diff 내 전건 08-04 로 정정. **이미 머지된 C8~C10 기록의 `REV-20260805T*` id·Run-035~042 날짜 표기는 append-only 라 존치** — 실제 작업일은 08-04 이며 이 각주가 정정 기록이다. ④ AC-3 이중 체계(§2.1 스모크 vs FUNCTION split-3) → FUNCTION full-id 로 탈모호화.
- **MINOR 흡수**: Run-011→007 인용 정정·feature_status_date/Last Updated 08-04·app.js 기점 13,216 각주·CONVENTIONS §14.1 "ES module" JS 한정.
- Timestamp: 2026-08-04T19:45:00+09:00

## REV-20260805T105500-phaseAB-plan-approval [SKIPPED:plan-approval-record] — 후속 Phase A+B 계획 승인 기록 (판단 근거, 패널 아님)

- 사용자 resume 지시(2026-08-05, "ITEM-P5b 프론트엔드 파일 분할 진행" + REPORT §8 후속 후보)로
  잔여 오케스트레이터 감축 계획 수립 → AskUserQuestion 3택(전체 승인/Phase A만/보류) 제시 →
  **"Phase A+B 전체 승인 (권장)"** 채택. 위험도 Critical 승계(§12.3 — 본편과 동일 축).
- 계획 정본: TASK §2.2. 차단 실측(let 21 × 함수 297 매트릭스)으로 state 편입 대상을 REPORT §8
  추정("_dqaDrag·_sidebarCatchupTimer 류")에서 **정확 2건**으로 확정 — 과편입 회피(§8 의
  _shareRangeEscHandler·mention 계열은 B2 함수 집합 설계로 해소).
- 본 entry 는 승인 이력 기록이며 check #9 의 accepted 근거로 쓰지 않는다 — Phase A 구현 패널은
  별도 REV(SUBAGENT) 로 기록.

## REV-20260805T111500-phaseA-state-intake [SUBAGENT:frontend-state] — Phase A 적대 패널: BLOCK/MAJOR 0 · MINOR 2 · NIT 3 전건 흡수 후 PASS

- Trigger: code change — state-편입 mini-change(비-중립). 렌즈 = 치환 완전성·의미 동일성·
  열거/직렬화 누출·하네스 vacuity·B1~B3 전제 충족 5축.
- 패널 실측 확인(청정 축): 전 트리 bare 잔존 0(코드) · `state` 재할당/spread 복제/for-in
  열거·JSON.stringify(state)·localStorage 통저장 전무 → 의미 동일성·직렬화 누출 없음 ·
  가드 15케이스는 mutation 2종(부분 revert → 2 FAIL·프로퍼티 삭제 → 1 FAIL)으로 비-vacuity
  실증 · **renderConversationList 본문 522줄의 잔여 모듈-let 참조 0** — Phase A 범위 판단
  (양방향 차단재 = 2건뿐) 유효 재확증.
- 흡수: [MINOR] tombstone 주석 오치환(`let state.dqaDrag` 자기모순) → 원 식별자 복원 ·
  [MINOR] 가드 [A3] 스캔이 2파일 하드코딩 → app/*.js 디렉토리 전수(readdirSync — B1~B3 의
  코드 목적지 자동 커버) · [NIT 3] 죽은 주입 파라미터 → 실 자유식별자(loadConversations·
  renderConversationHeader) · codeOnly `//` 스트리퍼의 문자열 내 URL false-negative 방지 ·
  sidebar.js stale 차단 서술 현행화. 흡수 후 가드 18/18 PASS + ESM 문법 PASS.
- 관찰(기록만): verify_*.mjs 전체가 CI(pytest 전용) 밖 — 본 가드도 동일(기존 조건과 같음,
  feature-0003 REVIEW 의 "mjs CI 배선 검토" 후속 후보에 합류).

## REV-20260805T115500-phaseB1-sidebar [SUBAGENT:frontend-split] — B1 적대 패널: MAJOR 1·MINOR 1 흡수 후 PASS

- Trigger: code change (byte-동치 추출) — 렌즈 5축(순환 import TDZ·이동 누락/중복·export 계약·
  하네스 정합·실 로드).
- 패널 실측 확인(청정 축): sidebar.js top-level 문의 app.js import 바인딩 참조 **0**(AST 전수)
  + **실 ESM 로드 검증**(실 index.html DOM + jsdom 글로벌에서 모듈 그래프 evaluate — LOAD OK,
  순환 초기화 무사, renderConversationList() 실호출 empty-state 렌더) · byte-parity 독립 재검증
  IDENTICAL · 합본 중복 선언명 0(extractFn 오포착 불가) · 신규 export 11건 전부 실사용.
- 흡수: **[MAJOR]** headless verify_share_bar_layout.py 가 dated evidence
  (share-bar-layout-before-20260727.png)를 in-place 재촬영 → 워킹트리 오염 적발 — git restore
  로 복원·커밋 제외(근본 처방 = 하네스 출력 경로 분리, 후속 후보로 기록) · **[MINOR]** app.js
  의 dead 역-import `_saveCollapsedGroups` 제거(사용처 0 — "필요한 전부만" 계약).
- 흡수 후: 문법 PASS · make test RC=0(FAILED/ERROR 0).

## REV-20260805T125500-phaseB2-composer [SUBAGENT:frontend-split] — B2 적대 패널: BLOCK 1·MINOR 1 흡수 후 PASS

- Trigger: code change (byte-동치 추출, sendPrompt 포함 — 핵심 경로 send). 렌즈 5축(import
  바인딩 재할당·순환 TDZ 실로드·이동 완전성·export 부작용·하네스 정합).
- 패널 실측 확인(청정 축): 이동 let 6종 재할당 전부 composer 내부(양방향 read-only 위반 0,
  acorn AST 전수) · **실 ESM 그래프 evaluate OK**(app export 101·composer 23·단일 인스턴스·
  renderComposer 실호출·_mentionAC live-binding) · parity 50/50 verbatim · 중복 export 0 ·
  inject_asset_stamp 가 JS 내부 specifier 까지 재작성(이중 인스턴스화 없음).
- 흡수: **[BLOCK]** pytest `test_msg_speaker_attribution_web.py` 의 개행-앵커 마커
  `\nfunction renderMessages(` 가 잔류-export 화로 미매칭 → ValueError 2건(CI 적색 예정) —
  export-prefix 내성 마커로 2곳 수정 + 합본에 composer.js 추가, make test 재실행 완주(FAILED 0).
- 기록(선재 결함, B2 비회귀): `win-browser-share-group-sync.scenario.json` 이 Cycle 7 ESM 화
  이후 죽은 전역(state·sendPrompt 등) 참조 — settings-notif 와 같은 뿌리, 후속 정비 후보
  (feature-0003 REVIEW 의 시나리오 정비 후보에 합류).

## REV-20260805T143000-phaseB3-progress [SUBAGENT:frontend-split] — B3 적대 패널: BLOCK/MAJOR/MINOR 0 · NIT 2 (1 흡수·1 기록) PASS

- Trigger: code change (byte-동치 추출 — run 추적 최다 회귀 영역). 렌즈 5축(run 추적 정확성·
  순환 TDZ 실로드·바인딩 재할당·re-export 계약·이동 완전성).
- 패널 실측(청정 축): **mutation probe 2건**(foreign-run 가드 훼손 → 하네스 3 FAIL · 백오프
  제거 → 3 FAIL)으로 합본 하네스의 비-공허 실증 · 실 ESM 그래프 evaluate OK(app export 124 ·
  progress top-level 실행문 0 = TDZ 면제 · sentinel 미채택/seq/타이머 경계 넘어 정상) ·
  재할당 양방향 0(7모듈 AST) · re-export 6심볼 런타임 동일성(===) 확인 · parity 18/18.
- 흡수: [NIT] 합본 extractFn 의 첫-매치가 죽은 사본을 검증할 수 있는 미래-가드 — 다중 출현
  fail-loud 를 합본 하네스 3건에 추가.
- 기록: [NIT] run-감지 서브도메인이 경계 상호재귀(detectNewRun[app]↔scheduleRunDetectPolling
  [progress]) — live-binding 으로 정확, 후속 phase 에서 detectNewRun 동반 이동 시 해소 후보.
