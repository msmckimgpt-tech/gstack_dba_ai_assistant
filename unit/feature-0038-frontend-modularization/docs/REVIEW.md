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
