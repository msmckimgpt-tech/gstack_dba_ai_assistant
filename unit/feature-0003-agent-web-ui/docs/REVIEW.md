---
doc_type: REVIEW
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

> 이전 기록(389건): [REVIEW-archive-20260711T115053.md](./_archive/REVIEW-archive-20260711T115053.md)

## REV-20260724T073848-conv-menu-order [SKIPPED:trivial-cosmetic-reorder] — 대화 목록 '···' 확장 메뉴 항목 순서 변경 (TASK-20260724T073848-conv-menu-order, Minor §12.3, frontend-only)
- Panel skip 사유(§18.8): 순수 렌더 순서 재정렬(`공유 → 이동 → 설정`) — 기존 3항목의 append 순서만 교체. 신규 로직·권한 게이트·onSelect 핸들러·action 인자·데이터 흐름·보안 표면 0. `folder.manage.own` 조건부 게이트·`conversation.share`/`conversation.read` action 불변. 적대 리뷰가 표면화할 correctness/security 리스크 없음 → SKIPPED 정당.
- 검증: `node --check` PASS · 항목 3종(공유/이동/설정) 전부 유지 · 순서를 assert 하는 테스트 부재 확인(`verify_settings_archive_leave.mjs` 존재검사만 — 재정렬 무영향; 선존 2 FAIL 은 HEAD 부터의 `makeItem` vs `make` 정규식 drift, 본 변경 무관).

## REV-20260724T053457-metadata-review-ds-scope-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260724T053457-metadata-review-ds-scope, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + REPORT 완결 + TASK 체크박스 + MODIFY CHG 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260724T053457-metadata-review-ds-scope(SHIP-WITH-FIXES, 3건 반영).
- 라이브 실측(실 Windows Chrome via `bin/win-browser.py`, https://localhost/admin, 배포 2b22b5ff): 검토 큐 datasource 필터(공용 96→mysql-kr-an1-auth 16, 전 행 해당 scope) · 배지 정합(96→16, Finding 1 MAJOR) · 자동승급 목록 가시(목록 84 중 82 자동등록) · 등록 시각 전 행 표시 · pageerror 0. 사용자 3결함 전부 해소.

## REV-20260724T053457-metadata-review-ds-scope [SUBAGENT:frontend-correctness-security] — 메타데이터 거버넌스 검토 큐 datasource 필터 + 자동승급 목록 정합 + 등록 시각 (TASK-20260724T053457, Major §12.3) — SHIP-WITH-FIXES (1 MAJOR/2 MINOR in-cycle 반영)
- 범위: `관리 콘솔 > 지식베이스 > 메타데이터 > [용어사전/ENUM/샘플쿼리]` 거버넌스 UI 3결함. 초안=frontend(admin.js): 검토 큐 scope_key 전송(Fix1)·큐↔목록 scope 정합(Fix2)·등록 시각 표시(Fix3).
- **적대 리뷰(general-purpose, frontend/correctness/security 렌즈) verdict = SHIP-WITH-FIXES → 지적 3건 전부 반영 후 SHIP**:
  · **Finding 1 (MAJOR, 반영)**: 검토 큐 리스트는 Fix1 로 scoped 됐으나 pending 배지는 여전히 unscoped(`count_glossary_feedback`/`count_enum_feedback` 가 scope_key 미적용) → 특정 ds 선택 시 리스트 N건 ↔ 배지 전체 건수 지속 불일치(Fix1 의도 정면 위반, 유일한 사용자-가시 오정보). **수정(backend additive)**: 두 count 함수에 `scope_key=None` 파라미터 추가(지정 시 `AND scope_key=%s`·`_normalize_scope_key`) + 엔드포인트(admin_metadata.py glossary-feedback/enum-feedback)가 `scope_filter` 전달 → 배지=scoped pending(리스트와 정합, '공용'=전체). 테스트 monkeypatch 시그니처 2건 동반 갱신(glossary-autoreg/enum-feedback).
  · **Finding 2 (MINOR, 반영)**: datasource 변경 시 배지 미재산정(list 보기·타 서브탭 stale). **수정(frontend)**: `_metaPrimeReviewBadge` 가 `_metaReviewScopeParam` 로 scope 전송 + scope-change 핸들러가 변경 시 배지 재-prime.
  · **Finding 3 (MINOR, 반영)**: sample 큐 날짜(`_sfFmtDt`, 무-prefix)가 glossary/ENUM(`_metaFmtDt`+"등록") 와 포맷·라벨 불일치. **수정(frontend)**: sample 큐 행·상세를 `등록 ${_metaFmtDt}` 로 통일.
- 리뷰 통과(NON-issue, 명시 검증): XSS 없음(전 created_at textContent/mkTag) · 크로스-DS 누출 없음(표시-측 narrowing·백엔드 RBAC=permission-based `kb.*.curate`·'공용'=권한 내 전체) · URL well-formed(`?scope_key`/`&scope_key` 정합·단일 encodeURIComponent) · created_at null-safe(전 가드+`_metaFmtDt` "" 폴백·미존재 시 기존 '수정만' 동작 보존) · 백엔드 3목록/3큐 모두 created_at 반환(no-op 아님) · scope 필터 3큐 균일 · enum bundle 경로 created_at 도달 · auto-promote write↔list read scope 정규화(`_normalize_scope_key`) 동일.
- 검증: `node --check`(ESM) PASS · `verify_metadata_list_detail.mjs` baseline 신규 회귀 0(26 PASS/3 FAIL·[D] crash=pre-existing) · py_compile(kb_glossary/admin_metadata) · pytest(feature-0003 metadata glossary-autoreg/enum-feedback/sample-curation 44 + feature-0002 glossary/enum 72) ALL PASS · 정적 자산 baked → POST-DEPLOY PB-0008 Windows-browser(정본, test-runs.d fragment 20260724T053457).

## REV-20260724T133000-csv-download-wiring-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260724T123600-csv-download-wiring, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + REPORT 완결 + TASK 체크박스 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260724T123600-csv-download-wiring(SHIP-WITH-FIXES).
- 라이브 실측(배포 dc316152, `bin/win-browser.py` relay 실 Windows Chrome 150, bootstrap_admin 세션): 대화 `20260724022429-515c0fd9`('도전 던전 전투 로그…' = 배틀 로그 차원별 집계, 16 메시지) 인라인 ```csv``` 블록 아래 "📥 CSV 다운로드" 버튼 렌더(visible·ready=1·linkAfter=false)·클릭 시 Blob `text/csv;charset=utf-8;` size=2603 다운로드 트리거·콘솔 에러 0. 서빙 app.js/share.js/styles.css 신 심볼 curl 확증. 사용자 요청("CSV 다운로드 가능 답변인데 실제 다운로드 수단 없음") 해소.

## REV-20260724T123600-csv-download-wiring [SUBAGENT:adversarial-review] — assistant "CSV 다운로드 가능" 답변의 실제 다운로드 배선 누락 수정 (TASK-20260724T123600-csv-download-wiring, Major cross-cut) — SHIP-WITH-FIXES (2 MAJOR/MINOR in-cycle 반영)
- 범위: 프론트 `static/{app.js,share.js,styles.css}` + cross-cut feature-0002 `agent_core.py`(`_collapse_large_csv_blocks`/`_collapse_result_blocks`)·`modules/tools.py`(가이던스). §18.8 적대 리뷰(general-purpose subagent, 전 파일 Read·양 렌더 파이프라인·sanitize·재사용 헬퍼·테스트 정독).
- **[MAJOR] 반영**: share.js `enhanceCsvBlockDownloads` 가 app.js 의 "`/api/file` 링크 뒤따름 → 버튼 skip" 가드를 누락 → 백엔드가 절단한 5행 미리보기 블록에 공유 뷰가 "CSV 다운로드" 버튼을 붙여 *일부 행만 받는 오해*(markExternalLinks 가 /api/file 링크를 익명 401 외부링크로 만들어 유일 작동 다운로드가 5행 버튼). **수정**: app.js 동형 skip 가드를 share.js 에 미러(nextElementSibling `a[href*="/api/file?"]` → skip + csvDownloadReady 마킹). .mjs 회귀 잠금 2건 추가(share/2).
- **[MINOR] 반영**: `_collapse_large_tables` 와 `_collapse_large_csv_blocks` 가 각자 `used[]` 를 생성 → 한 답변에 같은 결과가 MD표+```csv 양쪽이면 이중 링크(무해) 또는 token-less 동일-컬럼수 2 CSV 엇갈림 오링크(희소). **수정**: `_collapse_result_blocks(answer, csv_paths)` 통합 wrapper 신설 — 공유 `sigs`/`used` 로 두 패스 순차 적용. 두 collapse 함수에 `_sigs`/`_used` optional 파라미터(기본 자체계산 — 단독 호출 테스트 하위호환) 추가. 3 호출부(초안·redteam 수정·최종) 전부 wrapper 로 통일. pytest 회귀 잠금(`test_collapse_result_blocks_shared_used_no_double_link` — 링크 정확히 1개).
- **[MINOR doc drift] 반영**: `feature-0002/docs/AGENT_CORE_INTERNALS.md:127` 의 폐기된 "CSV 링크를 제공하세요" 서술을 새 가이던스(다운로드 버튼 자동 제공·`_collapse_result_blocks`·프론트 `enhanceCsvBlockDownloads`)로 갱신.
- **결함 없음 확인(리뷰어 근거)**: app.js — sanitize 이후 라이브 DOM 동작·`textContent` 만 사용(XSS 무첨가)·skip 로직 정합·비-csv/멱등/빈블록 무영향·BOM+revokeObjectURL. share 누출 축 — `codeEl.textContent`(이미 가시·sanitize된 본문)만 저장, /api/file·step csv_paths 미접근(redaction 무우회, fail-closed). `_collapse_large_csv_blocks` — 미닫힘 펜스/헤더-only/threshold 경계/no-match 원문보존/미리보기 트림 데이터손실 없음·3 red-team 경로 대칭. tools.py — csv_path=None 게이트로 없는 다운로드 약속 안 함.
- 검증: 전체 pytest **2305 passed / 2 skipped** · jsdom `verify_csv_block_download.mjs` **22 PASS**(app 13 + share 4 + static 5, share skip 가드 회귀 잠금 포함) · `node --check`. CHECK#13 = test-runs.d Windows-browser fragment(PRE-COMMIT 자동검증 + POST-DEPLOY 라이브 PB-0008). Verdict: **SHIP-WITH-FIXES → 반영 완료, SHIP**.

## REV-20260724T033500-graph-emoji-color-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260724T031956-graph-emoji-color, 비-정책 doc-only)
- Panel skip 사유(§18.8): TEST.md POST-DEPLOY 결과 append + TASK 체크박스 완료 + MODIFY 갱신 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260724T031956-graph-emoji-color(SHIP).
- 라이브 실측(배포 c709ad3f, `bin/win-browser.py` relay 실 Windows Chrome): 서빙 graph-renderer-pixi.js 에 fix(hasEmoji 게이트·emoji 폰트) curl 확증. 버그 유발 조건(dark labelFill `#161b22` + emoji 폰트 스택) canvas fillText chroma 프로브 — 6종 컬러(📊217·💳255·📜75·📘177·📦214·🗂255)·3종 그레이스케일(👤·🔗·⚙️=0, Segoe 폰트 디자인, 실 글리프). 9종 전부 flat 틴트 실루엣 아님 → 사용자 리포트("테이블 노드 일부 이모지 검은색 실루엣") 해소 확인.

## REV-20260724T031956-graph-emoji-color [SUBAGENT:adversarial-frontend] — 그래프 뷰 테이블 노드 역할 이모지 검은 실루엣 렌더 수정 (TASK-20260724T031956-graph-emoji-color, Minor §12.3 frontend-only) — SHIP
- 대상 diff: `static/graph/graph-renderer-pixi.js`(+`hasEmoji` 순수 헬퍼 · `_makeText` BitmapText 게이트에 `!hasEmoji` · Text 폴백 fontFamily 색 이모지 폰트) · `tests/headless/test_pixi_adapter.js`(T20b 16-assert). §18.8 적대 패널(general-purpose subagent, 정확성+회귀+성능+fillStyle+혼합라벨 5렌즈) — 결함 적발 목적, 실 소스 882줄+소비처 계약+PixiJS v8.19.0 실측 프로브.
- **VERDICT: SHIP — BLOCKING 결함 0.** 5개 렌즈 전부 REFUTED:
  - **정확성 REFUTED**: 실측 프로브로 역할 아이콘 9종(📘👤💳📜🔗📊📦🗂 전부 1F000-1FAFF, ⚙️=2699+FE0F) 전량 매칭·누락 0. 평문/컨트롤(`−`2212·`+`·`ƒ`0192·`×`·한글·col-lod 배지 `▤`25A4·`…`2026) 비매칭 → 과강등 0(BitmapText 최적 경로 보존). 과매칭 가능 심볼(✓/★/⌘)은 `graph-ctxmenu.js` **DOM 버튼**에만 존재, `_makeText` 를 타는 Pixi labelText 엔 0건 → 실현 안 되는 이론적 여지.
  - **회귀 REFUTED**: PixiJS v8.19.0 `Text`·`BitmapText` 는 공통 `AbstractText`(anchor·text·width)+`ViewContainer`(position) 상속 — 소비처(`_label`·`_ellipsize`·`_drawCombo`·`_paintEdge`)가 쓰는 4 API 양쪽 동일 계약. 강등 시 파손 0. (`_ellipsize` 선두 서로게이트 슬라이싱은 **기존** 동작·실 maxW=140 에서 미발동 → 회귀 아님, nit.)
  - **성능 REFUTED-as-blocking**: 이모지는 분석완료 테이블 칩에만 부착(컬럼·미분석표·접힌 카드 0) → 대량 요소 컬럼 라벨은 전부 BitmapText atlas 배칭 유지. 강등분은 viewport-cull(§67) bounded + render-on-demand(매 프레임 아님) → draw-call 폭증 아님. `hasEmoji` 리터럴 regex(V8 캐시) µs.
  - **fillStyle 무시 REFUTED**: 색 이모지 폰트(Segoe COLR/CPAL·Apple sbix·Noto CBDT)는 canvas fillText 시 색 레이어 자체 렌더·fillStyle 무시(표준). Pixi v8 `Text`=canvas2D 래스터(white-base+tint 아님, tint 미설정) → 이모지 색 채널 보존·fill/tint 로 어두워질 위험 0.
  - **혼합 라벨 REFUTED**: "📊 stats_daily" → 평문 "stats_daily" 는 `fill`(dark=#161b22, 노란 칩 대비 확보) 정상 적용, 📊 만 네이티브 색. 평문 색 손실 0.
- 설계 정합: BitmapText 는 색 이모지 미지원 → PIXI.Text 강등이 Pixi v8 문서화 정석. 기존 "비-hex 색→col.valid=false→Text 강등" seam(L189-190) 과 동형 편입.
- 비-blocking 유의(반영): ① **[필수 게이트]** 실 색 렌더 증적은 PB-0008 win-browser 실측 필수(규약 visual_verification_scope=always) — T20b 는 regex 만 커버, 수정전 실루엣 재현→수정후 색 렌더 라이브 캡처는 배포 후 잔여(deploy_scope: included). ② `_ellipsize` nit·③ regex 과매칭 심볼(Pixi 라벨 미사용)=무해 → 코드 수정 불요.
- 검증: `node --check --input-type=module` PASS · `test_pixi_adapter.js` **112 PASS / 0 FAIL**(기존 96 회귀 0 + T20b 16) · verify-completion #1~#16(§16.3) PASS. 라이브 PB-0008 는 배포 후. Cross-ref: TASK/CHG/TEST-20260724T031956-graph-emoji-color.

## REV-20260724T140000-share-scroll-bottom-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260724T112446-share-scroll-bottom, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료 + MODIFY/REPORT 갱신 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260724T112446-share-scroll-bottom(SHIP-WITH-FIXES).
- 라이브 실측(배포 94b4003a, `bin/win-browser.py` relay 실 Windows Chrome, 실 공유 링크 16-메시지 대화): AC-SSB-1 진입 scrollY 53282==maxY·atBottom=true·pageerror 0 · AC-SSB-3 top 스크롤 후 stayedAtTop(snap-back 없음) · AC-SSB-2 최종 54118px 안착. 서빙 /static/share.js 신 심볼 5종·dead window-load 소멸 curl 확증. 사용자 요청("공유 링크 진입 시 스크롤 맨 아래") 해소.

## REV-20260724T112446-share-scroll-bottom [SUBAGENT:adversarial-frontend] — 공유 대화 링크 진입 시 문서 스크롤 맨 아래 고정 (TASK-20260724T112446-share-scroll-bottom, Minor §12.3 frontend-only) — SHIP-WITH-FIXES
- 대상 diff: `static/share.js` 단일(+70) — 진입 `fetchShare→render` 체인에 `engageInitialBottomPin()` 1회 + `scrollShareToBottom`/`releaseShareBottomPin`/`onShareBottomPinKeydown` 신설 + `pageBranchShare`·`scrollShareMessageIntoCenter` 에서 명시 pin 해제. §18.8 적대 패널(general-purpose subagent, correctness+regression+UX 렌즈 9축) — 결함 적발 목적.
- **헤드라인 회귀 2건 CONFIRMED-OK**: (1) feature-0019 버전 페이징 위치보존(`pageBranchShare` savedY)과 진입 pin 이 싸우지 않음 — 페이저 클릭(마우스 click, wheel/touch/key 아님)이라 명시 `releaseShareBottomPin()`(savedY 캡처 전 선행)이 유일 방어이고 정상 배치·disconnect 후 재-fire 불가. (2) rail dot 점프(`scrollShareMessageIntoCenter`)도 함수 진입 즉시 명시 해제 → eased 스크롤과 무충돌. **BLOCKING/데이터-정확성 defect 0.**
- **누수/멱등 CONFIRMED-OK**: `releaseShareBottomPin` early-return 멱등 · observer disconnect+null · `{passive:true}` add ↔ 옵션 없는 remove 매칭 정상(passive 는 match key 아님) · repin 클로저 `_shareBottomPinActive` 가드. maxY 수식은 파일 내 기존 idiom(L216-217/L388)과 동치 · 빈 공유(messages 0)=maxY 0 no-op CONFIRMED-OK. scroll-behavior:smooth 부재 grep 확인(instant 진입 스크롤 정상, reduced-motion moot). fixed `.share-footer` 는 `.share-container` bottom padding 80px 로 마지막 메시지 안 가림(CONFIRMED-OK).
- **반영한 findings (SHIP-WITH-FIXES → 3건 흡수)**:
  - **[MINOR top-priority, finding#9] 고정 3s 상한이 느린 성장 놓침**: mermaid/외부 이미지가 3s 후 완료되면 pin 해제 후 최신 메시지가 fold 아래로 밀려 무거운 대화에서 "맨 아래" 계약 위배. → **성장 신호(ResizeObserver·img `load` capture)마다 리셋되는 settle 타이머(600ms) + 절대 상한(8s)** 으로 교체(고정 3s 폐기). 이미지 지연 로드 재고정 추가.
  - **[NIT, finding#3] dead `window load` 리스너 제거**: engage 는 resolved fetch promise 안에서 실행돼 window.load 는 이미 발화 → 무효 + 미제거 leak. → 삭제.
  - **[MINOR, finding#5] keydown 과다 트리거 + Tab yank**: any-key 해제가 keyboard/AT 사용자를 조기 해제. → **스크롤 의도 키(PageUp/Down·arrows·Home/End·Space)만** 해제 + **`focusin`** 해제 추가(Tab/클릭 focus 시 헤더로 focus-scroll 을 pin 이 방해하지 않도록).
- 검증: `node --check` PASS(수정 후) · verify-completion #1~#16(§16.3) · CHECK#13 test-runs.d Windows-browser fragment(PRE-COMMIT PASS + POST-DEPLOY 라이브 계획, headless layout 부재 사유). 라이브 PB-0008(AC-SSB-1~3)은 배포 후(deploy_scope: included). Cross-ref: TASK/CHG/TEST-20260724T112446-share-scroll-bottom.

## REV-20260722T105320-share-menu-perm-wiring-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260722T103254-share-menu-perm-wiring, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료 + evidence PNG 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260722T103254-share-menu-perm-wiring(SHIP).
- 라이브 실측(배포 066cec5e, https://localhost/ bootstrap_admin, win-browser Chrome relay): 본인 대화 말풍선 ☰ 3항목(`여기서 분기`·`여기까지 공유`·`여기부터 공유`) 모두 `is-access-blocked` 없음(수정 전 공유 2항목 항상 blocked 회귀 복구)·`여기부터 공유` 클릭 → onSelect(beginShareFloor) 실행·floor arm 배너/마커 표시·pageerror 0. 서빙 app.js `conversation.share.create` action 리터럴 0.

## REV-20260722T103254-share-menu-perm-wiring [SUBAGENT:adversarial-security+ux] — 말풍선 ☰ '여기까지/여기부터 공유' 권한 연결(action 매핑) 회귀 수정 (TASK-20260722T103254-share-menu-perm-wiring, Minor §12.3 frontend-only) — SHIP
- 대상 diff: `static/app.js` 2줄(☰ 공유 항목 action `"conversation.share.create"`→`"conversation.share"`) + `tests/test_menu_action_permission_wiring.py` 신규. §18.8 적대 패널(general-purpose subagent, security/ux 렌즈) — 결함 적발 목적.
- **Q1 정확성 CONFIRMED-OK**: `"conversation.share"` → switch(app.js:606-607) → codes `["conversation.share.create"]` 정확 매핑. share.create 는 own/any 분기 없는 단일 flat 권한이라 ownership 분기 불요(rename/delete 와 다름). 형제 conv-item '공유'(app.js:7763)와 동작 동일 — `markAccessBlocked` 가 `blocked=!can("conversation.share.create")=false` 로 정상 활성.
- **Q2 인가 CONFIRMED-OK(무약화)**: `can()`(app.js:977-984)은 display-permissive(인자 무시·로그인=true) — 순수 표시 게이트 수정. diff 는 app.js(프론트)만. 백엔드 `create_conversation_share`(conversations.py:787-818) enforcement 불변·권위적: share.create 403·read.own/any 404·joinable owner 403·bounded-window widen-guard 403. 비권한 사용자는 pre-fix(즉시 client 토스트)→post-fix(백엔드 403 round-trip 토스트)로 **관측 차이만**, 신규 역량 부여 0(`beginShareFloor` 는 client-only, `onShareCeiling`→createConversationShare 는 guarded 엔드포인트).
- **Q3 형제 회귀 CONFIRMED-OK**: app.js `action:` 전수 6개(:7763 share·:7764 read·:7798 ask·:7805 create·:7816/:7821 share) 모두 처리 case. 권한 코드(`*.create`/`*.own`/`*.any`)를 action 으로 넘기는 다른 항목 0 → default 브랜치 히트 없음.
- **Q4 테스트 CONFIRMED-OK**: fixed 3 PASS·pre-fix HEAD 에서 `unresolved:['conversation.share.create']`로 2개 테스트 FAIL → **원 버그를 실제로 잡음**(no false-negative). CI 도달성 확인(collected dir·PYTHONPATH). 잠재 caveat(현재 미트리거·non-blocking): ① whole-file `action:` 정규식이 향후 비-메뉴 `action:` 리터럴에 false-positive 여지 ② double-quote 한정 ③ function-slice 앵커 의존. 코드베이스가 double-quote 통일이라 현 gap 0.
- **결론: SHIP — blocking defect 0.** 정확·인가 무약화(백엔드 권위적·미변경)·형제 회귀 없음·원 버그 잡는 테스트로 잠금. 라이브 실증 = POST-DEPLOY PB-0008. Cross-ref: CHG/TASK/FUNCTION/TEST-20260722T103254-share-menu-perm-wiring · test-runs.d fragment.

## REV-20260717T010501-doc-sync-rn-0717 [SKIPPED:non-policy-doc] — 릴리즈노트 07-16 블록 ‘연결 테스트’ 버튼 회귀 복구 fixed 항목 추가 (TASK-20260717T010501-doc-sync-rn-0717, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·비중복은 doc_sync 가 정본(feature-0003 REPORT/TASK ds-test-gate-fix + 07-13 블록 소개 대조) 대비 직접 검증.
- 적대 대조(정본): ds-test-gate-fix(REPORT 2026-07-16) = 07-13 출하·PB-0008 PASS 한 ‘연결 테스트’ 버튼이 perm-atomic-split(8e01cc24) 부작용으로 미직렬화 state.user.permissions 의존→항상 false→미렌더 회귀(라이브 b8658bee hasPermissions:false 실측), can() display-permissive 로 07-13 동작 복구·백엔드 enforcement 불변·POST-DEPLOY PB-0008 라이브 복구(87cbe5d8). 07-13 블록이 버튼을 type:new/work 로 소개 → 재소개 아닌 ‘보이지 않던 문제 수정’ fixed 프레이밍(중복 아님). feature-id/§/PR#/구현 누출 0.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(31 releases·07-16 head 5항목[admin 4·work 1]·07-15 보존 7·스키마·누출0) · verify_release_notes.mjs 33/34 PASS·1 FAIL(styles.css 스크롤 정규식 pre-existing false-negative, 본 cycle 미변경·feature-0003 소관).
- **cache-buster**: 소스 `?v=dev` 고정 — ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. index/admin.html 편집 0.
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260717T010501-doc-sync-rn-0717 / META REV-20260717T010501-META-0039-doc-sync-0717(별도 commit) / 원천 PR #855/#856. **무인 스케줄 run — landing/배포는 cron wrapper v3 소유(스킬 로컬 commit 만).**

## REV-20260716T052500-ds-test-gate-fix-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 회귀 복구 라이브 기록 (TASK-20260716T051931-ds-test-gate-fix, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260716T051931-ds-test-gate-fix.
- 라이브 실측(배포 e6ca5e4b, https://localhost/ bootstrap_admin console_access, win-browser Chrome relay): DS 테스트 버튼 **14개 재렌더**(수정 전 0 — 회귀 복구)·클릭→"✓ 'mssql-dk-dev' 연결 성공 (13.6ms)" 상단 토스트·pageerror 0. 서빙 app.js `can("datasource.test")` 반영 확인.

## REV-20260716T051931-ds-test-gate-fix [SKIPPED:trivial-regression-fix-display-only] — 작업화면 데이터소스 '연결 테스트' 버튼 렌더 회귀 수정 (TASK-20260716T051931-ds-test-gate-fix, Minor §12.3)
- Panel skip 사유(§18.8): app.js **1줄** 변경(프론트 표시 게이트) — 백엔드 enforcement·스키마·RBAC·엔드포인트 shape 0. 보안 posture 불변(서버 `admin_test_datasource` 는 console.access+datasource.test 계속 요구). 07-13 출하·PB-0008 PASS 동작의 복구라 신규 설계 표면 없음. 라이브 실증은 POST-DEPLOY PB-0008.
- **회귀 진단**: perm-atomic-split(`8e01cc24`, 07-15 Critical)이 DS 테스트 버튼 프론트 게이트를 `Boolean(state.user?.permissions?.["datasource.test"])` 로 작성. `state.user.permissions` 는 이 코드베이스의 `/api/session` 에 부재(TASK-0098 "표시 허용 + backend 403" 컨벤션·`can()` 이 permissions 맵 미사용) → undefined→false → 버튼 전부 미렌더. 라이브 b8658bee 세션 실측 `user.permissions` 부재 확인.
- **수정**: `Boolean(state.user?.permissions?.["datasource.test"])` → `can("datasource.test")`(display-permissive, 컨벤션 정합). 순 게이트 = `!viewOnly && canOpenAdminConsole()`(07-13 동작 복구). datasource.test 미보유자는 백엔드 403 → apiFetch 공통 토스트.
- **관련 flag(별도 feature 소유)**: 동일 커밋 app.js ≈L2006 권한 표시 UI 도 `state.user?.permissions` 를 읽어 동일 부재 — 본 cycle scope 밖(그 기능 소유자에게 위임).
- **VERDICT: SHIP (회귀 복구·display-only·보안 무영향).**

## REV-20260716T120000-graph-search-groups-postverify [SKIPPED:post-deploy-visual-verification-reconciliation] — PB-0008 라이브 PASS 원장 정합 (docs-only, 코드 변경 0)
- Date: 2026-07-16
- Cycle: CHG-20260716T120000-graph-search-groups-postverify (test-runs.d Run 3 DEFERRED→PASS + TASK 체크박스), **Minor §12.3**.
- SKIPPED 사유: 순수 검증 원장 정합 — 런타임 코드 변경 0(§18.4 META docs-only). 기능 코드 적대검증은 REV-20260716T114705-graph-search-panel-groups(SHIP-WITH-FIXES, C1/C2/P1/P2 봉인)에서 완료. 본 cycle 은 배포·PB-0008 라이브(main 89c1e7b0) 결과 기록.
- 검증 결정적(라이브 실측): 8 스키마→카테고리 2단 접기·모두 접기/펼치기(C2 라벨 정합)·검색 이력 뒤로(입력값·28건 복원)/앞으로·verbose 부제 부재·pageerror 0. 상세 test-runs.d/20260716T1147 Run 3.
- Cross-ref: REV-20260716T114705-graph-search-panel-groups / CHG-20260716T120000-graph-search-groups-postverify.

## REV-20260716T114705-graph-search-panel-groups [SUBAGENT:adversarial-frontend-correctness+ux] — 검색 결과 패널 3개선(2단 접기·검색 이력·간결화) SHIP-WITH-FIXES
- Date: 2026-07-16
- Cycle: TASK-20260716T114705-graph-search-panel-groups (검색 결과 2단 접기·검색 이력·설명문 간결화), **Minor §12.3** — 프론트 단독·additive.
- Trigger: §18.8 — UI/패널/상호작용 변경(ux) + 이력 상태머신·렌더 correctness. 적대 코드리뷰(general-purpose outside voice, 6축 REFUTE: XSS·접기 로직·이력 편입 루프/가드/정합·회귀·UX·JS 참조). 이력 시스템·esc·input 배선·`_metaRenderedIdFor` 싱크 교차검증.
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0) — CONFIRMED 2 + PLAUSIBLE 2 흡수, 1 수용.
- **흡수한 CONFIRMED**:
  - **C1 (이력 forward 미절단)**: `_metaGraphRecordSearch` in-place 갱신이 `cur.v==="search"` 만 보고 forward 를 안 잘라, "뒤로→검색 항목→질의수정" 시 구 문맥 노드가 forward 에 잔존→앞으로가 무관 노드 복원. **수정**: in-place 시 `detailHistIdx < len-1` 이면 `splice(idx+1)` 로 forward 절단(노드/클러스터 새 방문 절단과 동형, top 갱신은 no-op).
  - **C2 (stale collapsed id 누적)**: `_searchGroupCollapsed` 가 검색 해제에서만 clear 돼, 다른 질의의 접힘 id 가 남아 `collapsed.size>0` 기반 "모두 접기/펼치기" 라벨 오표시·유령 부활. **수정**: 렌더마다 `currentIds`(이번 그룹 id 집합)로 collapsed prune → 현재 그룹만 반영.
- **흡수한 PLAUSIBLE**:
  - **P1 (복원 상태 드리프트)**: `_metaGraphRestoreSearch` 가 패널만 재구성하고 `mode`/`searchMatchNodes` 미복원→이후 클리어 판정(그 상태 의존) 드리프트. **수정**: 복원 시 `mode="search"` + `searchMatchNodes`=결과 key 집합 복원(캔버스 글로우 재적용은 back-nav 비용 회피 위해 생략 — 상태 정합만).
  - **P2 (질의문자열→카메라 focus, benign)**: `_metaGraphHistoryGo` 가 search 항목의 `ent.k`(질의)를 `_metaRenderedIdFor`/`AnimateFocus` 에 넘겨 우연 id 일치 시 오팬 가능. **수정**: `ent.v !== "search"` 가드로 search 항목 focus skip.
- **수용(P3, 무시가능)**: 이력 항목당 결과 노드 참조 캐시(≤50) — deep copy 아님·인메모리 전용(직렬화/localStorage 경로 없음)·`h.shift()` 회수, 연속 검색은 in-place 로 1항목. 무시 가능.
- **CONFIRMED-SAFE (리뷰어 실측 인용)**: XSS(전 문자열 esc·상태줄 q 는 textContent·상수 색/배지만 비-esc) · data-toggle/data-box 는 selector 미사용(getAttribute+parentElement)이라 제어문자/따옴표 안전, `\x01`(SOH) cat 구분자가 (scKey,cat) 경계 충돌 확실 차단 · 개별 접기 정합(Set+class+caret+aria 일괄, 헤딩은 body 형제라 이중 토글 없음) · 재검색 루프 없음(value 세팅은 input 미발화) · 항목 폭증 억제(top=search 만 in-place) · finding#5 해소 유효(검색=자기 이력 항목→captureScroll 정합, `_pendingDetailScroll` 은 v==="node" 게이팅) · 회귀 없음(nSchemas 제거 클린·matchBySchema/캔버스 글로우 불변) · 호이스트/import 정합.
- Verification: `node --check`(ESM) PASS · graph.css brace 245:245·comment 76:76 밸런스 · 4개 수정 재검증 PASS. **PB-0008 라이브는 POST-DEPLOY**(test-runs.d/20260716T1147 Run 3, visual_verification_scope: always).
- Cross-ref: CHG-20260716T114705-graph-search-panel-groups / TASK-20260716T114705 / CHG-20260716T013714-graph-search-detail-panel(원 기능·finding#5) / feature-0016(graph-detail-scroll 이력·스크롤).

## REV-20260716T015800-graph-search-detail-postverify [SKIPPED:post-deploy-visual-verification-reconciliation] — PB-0008 라이브 PASS 원장 정합 (docs-only, 코드 변경 0)
- Date: 2026-07-16
- Cycle: CHG-20260716T015800-graph-search-detail-postverify (test-runs.d Run 3 DEFERRED→PASS + TASK 체크박스), **Minor §12.3**.
- SKIPPED 사유: 순수 검증 원장 정합 — 런타임 코드·CSS·백엔드 변경 0(§18.4 META docs-only). 기능 코드 자체의 적대검증은 REV-20260716T013714-graph-search-detail-panel(frontend correctness+ux 7축, SHIP)에서 완료. 본 cycle 은 그 SHIP 후 배포·PB-0008 라이브 시각검증(main 03e8d1b0) 결과를 test-runs fragment 에 기록한 것.
- 검증 결정적(라이브 실측): 검색어 갱신→상세 패널 결과 리스트(코스튬 7건/플루토스 28건), match_via 배지(AI 분석/카테고리)+cluster_label+유사도, 행 클릭→노드 상세, 클리어→뷰 해제, pageerror 0. 상세는 test-runs.d/20260716T0137 Run 3.
- Cross-ref: REV-20260716T013714-graph-search-detail-panel / CHG-20260716T015800-graph-search-detail-postverify.

## REV-20260716T013714-graph-search-detail-panel [SUBAGENT:adversarial-frontend-correctness+ux] — 검색어 갱신 시 상세 패널에 검색 결과 구성 SHIP
- Date: 2026-07-16
- Cycle: TASK-20260716T013714-graph-search-detail-panel (그래프 뷰: 검색어 갱신 시 상세 패널에 검색 결과 리스트 구성), **Minor §12.3** — feature-0003 프론트 단독·additive.
- Trigger: §18.8 — UI/패널/상호작용 변경(ux) + 렌더 correctness(XSS·리스너·stale). 적대 코드리뷰(general-purpose outside voice, 7축 REFUTE: XSS/이스케이프·리스너 누수·stale 레이스·클리어 마커·병렬 hunk·UX/접근성·JS 참조). 백엔드 계약(`search_nodes`/`_node_dict`)·병렬 세션 diff·다크모드 교차검증.
- VERDICT: **SHIP** (BLOCKER 0) — 7축 중 6축 결함 없음, 1축 저-심각도 cross-session 조정 항목.
- **CONFIRMED-SAFE (리뷰어 실측 인용)**: ①XSS — 전 사용자/DB 유래 문자열(name/fqn/cluster_label/key/q) `esc()` 통과, 미이스케이프 보간은 전부 상수맵(`_META_GRAPH_COLOR`)·하드코딩 배지 라벨·숫자(score/length)뿐. data-goto 큰따옴표 delimiter+esc 로 속성 탈출 불가, getAttribute 되읽기 이중인코딩 없음. ②리스너 누수 — innerHTML 교체 시 이전 li detach + 클로저가 지역 r 만 캡처 → GC 회수(파일 표준 패턴). ③stale 레이스 — 렌더 훅이 `seq!==_opSeq`·`q!==lastQuery` 두 가드 뒤, 연타 stale 폐기. ④클리어 마커 — `metaGraphSearchResults` id producer 는 내 코드 2곳뿐(showDetail/클러스터 상세 미생성), 결과클릭→노드상세 진입 시 마커 소멸→보존, 결과뷰 클리어 시 empty 복원(양방향 정확). ⑤UX — 배지 색(카테고리=앰버=글로우 계열·분석=블루·이름=회색) 정확, score 0 analysis-only 는 via 배지만·유사도 배지 억제, 결과 0건 전용 메시지, role/tabindex/Enter·Space(스크롤 차단). ⑥JS 참조 — import 심볼·호이스트·백엔드 필드 계약(match_via list·score·cluster_label) 일치, `Array.isArray` 방어.
- **Flagged cross-session (finding #5, PLAUSIBLE low — 양 브랜치 병합 후에만 발현, 타 브랜치 소유)**: 병렬 세션 `ai/claude/feature-0016-graph-detail-scroll`(session claude-session-4126879)이 추가하는 `_metaGraphHistoryCaptureScroll()`(`_metaGraphHistoryRecord` 내부)은 "상세 패널=항상 history 추적 뷰"를 가정해 현재 scrollTop 을 `detailHist[idx]` 에 스냅샷한다. 내 **검색 결과 뷰는 비-history 뷰**로 같은 aside 를 점유 → 결과행 클릭(`_metaGraphShowDetail`)로 history 기록 시 결과 리스트 스크롤이 직전 항목에 잘못 스냅샷돼 뒤로가기 스크롤 오복원 가능. **텍스트 병합 충돌 없음**(내 hunk L459/L572–579/L1260~ vs 저쪽 L625–659, 48줄 간격, 3-way clean). 그 함수는 저쪽 브랜치에만 존재해 내 트리에서 수정 불가 → **후행 병합 세션이 `_metaGraphHistoryCaptureScroll` 에 마커-스킵 가드**(`if (document.getElementById("metaGraphSearchResults")) return;`) 추가로 해소. SendMessage 로 해당 세션 통지 + 본 항목 REPORT 기록.
- **수용(very-low, 회귀 아님)**: (a) `.amgr-via-*` 텍스트 고정 다크 hex — admin 패널이 다크 root 팔레트 미보유(사실상 라이트 단일)라 현재 무해, graph.css 기존 53 하드코딩 hex 선례 정합. (b) `ul>li[role=button]` 이 implicit listitem role 대체 → SR 목록 시맨틱 very-low nit.
- Verification: `node --check`(ESM) PASS · graph.css brace 233:233 밸런스 · 정적/로직 리뷰 PASS. **PB-0008 라이브 시각검증은 POST-DEPLOY**(test-runs.d/20260716T0137-graph-search-detail-panel.md Run 3, visual_verification_scope: always).
- Cross-ref: CHG-20260716T013714-graph-search-detail-panel / TASK-20260716T013714-graph-search-detail-panel / feature-0002 CHG-20260716-graph-search-content-match(match_via 원천) / feature-0016 병렬 세션 graph-detail-scroll(finding #5).

## REV-20260715T140000-graph-ctxmenu-content-category-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 라이브 검증 기록 (TASK-20260715T135725-graph-ctxmenu-content-category, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 test-runs.d fragment POST-DEPLOY 섹션(DEFERRED→실측 PASS) + TASK 체크리스트 close + MODIFY/REVIEW 기록뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260715T135725-graph-ctxmenu-content-category [SUBAGENT] (SHIP)가 정본.
- 라이브 실측(win-browser Chrome 150, 배포 66722981): ① sim-group "방송 계정·3"(mysql-kr-an2-player dbGame) 우클릭 → **컨텐츠 카테고리** 메뉴(헤더 "방송 계정·테이블 3" + 소속 스키마 상세/접기(묶음)/묶음명 복사) / ② 밴드 위 스키마 클러스터(dbAuth) → **스키마**(band-wins 철회 복원) / ③ 제품 카테고리 밴드 → **카테고리** / 개별 테이블 → **테이블**(흡수 안 됨). 서빙 자산 baked(`_pickContext` 0)+브라우저 fetch 확인. 증거 scratchpad/evidence-content-category-menu.png.
- Cross-ref: REV-20260715T135725-graph-ctxmenu-content-category(기능 정본) · CHG-20260715T140000-graph-ctxmenu-content-category-postverify · test-runs.d POST-DEPLOY Run.

## REV-20260715T135725-graph-ctxmenu-content-category [SUBAGENT:adversarial-content-category-review] — 그래프 우클릭 3대상 정합: 컨텐츠 카테고리(sim-group) 메뉴 신설 + band-wins 철회 (TASK-20260715T135725-graph-ctxmenu-content-category, Major §12.3 frontend-only) — SHIP
- Panel(§18.8): general-purpose 서브에이전트 적대 리뷰 — 8가설 전수 공격(band-wins 철회 dead-ref · GX 라우팅 · groupInfo miss · separator · 접기 토글 · 소속 스키마 앵커 · badge 계약 · 테스트 자명통과) + 66/66 헤드리스 + ESM 문법 + 원본 계약 교차검증. **BLOCKING 0, 8가설 전수 REJECTED → SHIP**.
- 가설별(전부 REJECTED): H1 band-wins 철회 무결(pointerdown `down.hit=_pick`, button===2 가 `hit` emit + `_pickEdge`/canvas 폴백 보존, `_pickContext` 런타임 참조 0) · H2 GX 라우팅=사용자 명시 의도("GB/GH/GX 전용") · H3 `groupInfo.set(gm.key)` 와 GB/GH/GX push 가 **동일 forEach** → 우클릭 가능 그룹은 groupInfo 에 반드시 존재(label 빈문자 불가) · H4 separator `\u0001` 이스케이프·리터럴 0x01 0 · H5 접기 토글=GX 좌클릭 정본과 동일(full-key `groupCollapsed` 토글+`_metaG6Apply(false)`) · H6 소속 스키마 앵커=GB/GH 좌클릭(core:2345)과 **동일 추출** → `_metaGraphShowClusterDetailById` 계약 파리티 · H7 badge 필드 형태 카테고리/스키마 메뉴와 일치 · H8 T22 가 tier 로직 실행(GH z5>GB z1)+band-wins witness(pSC→SC:s1·`_pickContext` undefined), 자명통과 아님.
- NIT 처리(4건): ① [pixi:431] button===2 주석 GX 누락 → **수정**(주석에 GB/GH/GX 명시). ② [test:263-281] T22 가 `up()` dispatch 분기를 직접 미구동 + `_pickContext` 이름 결합(다른 이름 승격 재도입 미포착) → **수용**(우클릭이 이제 `_pick` 이라 T21/T22 의 `_pick` 계약이 곧 우클릭 계약; 이벤트 시뮬레이션은 헤드리스 범위 밖 · POST-DEPLOY PB-0008 라이브가 실 dispatch 커버). ③ [ctxmenu:307] groupInfo miss 폴백 label=원시 fam id → **수용**(H3 근거로 miss 도달 불가, 순수 방어·미관). ④ [core:2144] GX 우클릭이 접기 항목 포함 content-category 메뉴 = GX 기능 중복 → **수용**(사용자 명시 "GB/GH/GX 전용", 3요소 일관성 향상, 무해).
- Cross-ref: TASK/CHG-20260715T135725-graph-ctxmenu-content-category · **철회 대상 REV-20260715T114608-graph-ctxmenu-band-priority** · 유지 선행 REV-20260715T102901-graph-ctxmenu-hittest(WYSIWYG `_pick` 3-tier).

## REV-20260715T120000-graph-ctxmenu-band-priority-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY 라이브 검증 기록 (TASK-20260715T114608-graph-ctxmenu-band-priority, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 test-runs.d fragment POST-DEPLOY 섹션(이연→실측 PASS)+TASK 체크리스트뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260715T114608-graph-ctxmenu-band-priority [SUBAGENT] (SHIP)가 정본.
- 라이브 실측(win-browser Chrome 150, 6a950a20): 밴드 위 클러스터 박스 우클릭→카테고리 메뉴 / 펼친 테이블 노드→그 테이블 / 좌클릭→클러스터 펼치기 정상. 사용자 결정 "밴드 우선" 라이브 충족. 증거 스크린샷 확보.
- Cross-ref: REV-20260715T114608-graph-ctxmenu-band-priority(기능 정본) · CHG-20260715T120000-graph-ctxmenu-band-priority-postverify · test-runs.d POST-DEPLOY Run.

## REV-20260715T114608-graph-ctxmenu-band-priority [SUBAGENT:adversarial-band-wins-review] — 제품 카테고리 밴드 우클릭 band-wins (TASK-20260715T114608-graph-ctxmenu-band-priority, Major §12.3 frontend-only) — SHIP
- Panel(§18.8): general-purpose 서브에이전트 적대 리뷰 — up()→_pickContext→emit→graph-core dispatch 전 경로 추적 + 68/68 테스트 + 좌표 기하 전수 재계산. 8가설 전수 REJECTED(무결).
- 가설별:
  - H1 좌클릭/드래그 보존: `_pickContext` 는 `d.button===2` 분기에서만 호출; onMove(pan/nodedrag)·좌클릭·더블클릭은 `d.hit`(=`_pick`) 사용 → **우클릭 전용 확정**. T21 이 `_pick` 계약 유지 잠금. (NIT: up 버튼 게이팅 자체는 코드리딩+T21 담보, pure 유닛 아님.)
  - H2 콘텐츠 노드 비흡수: 승격 조건 `__combo||kind==="schema-card"` — table/column/term/routine/ctl 전부 제외. T22 rTbl 가드.
  - H3 헤더/컨트롤: CATH(cat-hd)/CATX(cat-ctl)/GB/GH/GX 승격 대상 아님 → 자기 라우팅 그대로. T22 rHd 가드.
  - H4 밴드 밖 standalone: cat-bg=null→승격 skip. T22 rStand(schema-card) 가드. (NIT: standalone combo 미커버지만 로직상 `__combo` 유지→스키마, 회귀 없음.)
  - H5 미분류 밴드: `CAT:미분류` cat-bg 라 균일 적용 → 미분류 클러스터 우클릭=미분류 카테고리 메뉴. 결함 아님, 사용자 결정과 정합(관찰).
  - H6 _payload/kind 정합(핵심): 승격 시 raw cat-bg 노드(`__combo` 미부여) 반환 → `node:contextmenu`, id`"CAT:key"` → graph-core L2141 `/^CAT/`→`_metaGraphCtxForCategory`. combo→cat-bg 승격이 정확히 카테고리로 라우팅. 미승격 combo/SC 는 각자 경로.
  - H7 재-pick 좌표: button===2 는 finished=null(≤MOVE_THRESH 4px)일 때만 도달 → up 좌표 재-pick 이 down 과 동일. payload model 좌표도 up 이라 정합.
  - H8 T22 신뢰성: 좌표 기하(CAT 0..600×100..500·SC 125..275×170..230·combo 359..541×208..276·standalone 825..975×270..330) 코멘트 일치, 6 assertion 실효 가드. 68 PASS/0 FAIL.
- **판정: SHIP · BLOCKING 0**.
- NIT 처리: (1) up 버튼 게이팅 회귀 방지 = PB-0008 POST-DEPLOY 시나리오에 좌/우 분기 명문화(fragment (d) 좌클릭 펼치기 항목) — 수용. (2) T22 커버리지 갭(standalone combo·column·GB·미분류) = accept(로직상 회귀 없음). (3) 문서 = 본 cycle 에서 TASK/MODIFY/REPORT/FUNCTION/fragment 갱신 완료.
- 트레이드오프(사용자 수용): 밴드 내 클러스터 우클릭 스키마 메뉴는 좌클릭 드릴로 대체. 후속 '통합 메뉴' 여지(§8.1).
- Cross-ref: CHG/TASK-20260715T114608-graph-ctxmenu-band-priority · test-runs.d/20260715T114608-graph-ctxmenu-band-priority.md · 선행 REV-20260715T102901-graph-ctxmenu-hittest.

## REV-20260715T110000-graph-ctxmenu-hittest-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY 라이브 검증 기록 (TASK-20260715T102901-graph-ctxmenu-hittest, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 test-runs.d fragment POST-DEPLOY 섹션(이연→실측 PASS)+TASK 체크리스트뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260715T102901-graph-ctxmenu-hittest [SUBAGENT] (SHIP)가 정본.
- 라이브 실측 요지(win-browser Chrome 150, 배포 6ec5da4b→8098aee1): 제품-매핑 데이터소스 스키마그래프 CAT 밴드 2개에서 스키마 클러스터→"스키마" 메뉴 / 밴드 헤더·tint 여백→"카테고리" 메뉴 실증 — 세 사용자 증상(스키마↔카테고리 뒤바뀜) 전부 해소. WYSIWYG. 증거 스크린샷 확보.
- Cross-ref: REV-20260715T102901-graph-ctxmenu-hittest(기능 정본) · CHG-20260715T110000-graph-ctxmenu-hittest-postverify · test-runs.d POST-DEPLOY Run.

## REV-20260715T102901-graph-ctxmenu-hittest [SUBAGENT:adversarial-hittest-review] — 그래프 우클릭 메뉴 오라우팅 hit-test 층서 수정 (TASK-20260715T102901-graph-ctxmenu-hittest, Major §12.3 frontend-only) — SHIP
- Panel(§18.8): general-purpose 서브에이전트 적대 리뷰(코드 교차검증 + 라이브 테스트 62/62). 7가설 전수 판정.
- **핵심 소견**: 이 수정의 본질 = **hit-test 우선순위를 시각 z-페인트 순서와 정확히 정합**(WYSIWYG). `_METZ`(CAT_BG:-1 < COMBO:0 < GROUP_BG:1)에서 combo 는 cat-bg 와 group-bg 사이 유일 요소 → 3-tier(실노드 > combo > cat-bg)가 순수 z-order 를 정확 재현. 수정 전 node-first 는 비-node 인 combo 를 무시해 정합이 깨져 있었음.
- 가설별(전부 REJECTED=문제없음):
  - H1 드래그 회귀: CATH 헤더 리지드 이동·밴드 여백 드래그 tier1/tier3 로 **보존**; 밴드 내부 클러스터 빈배경 드래그는 수정 전 cat-bg 가 가로채 카테고리 통째 이동하던 것을 combo→클러스터 단독 이동으로 **복원**(graph-core L613 설계 주석 정합). 회귀 아님.
  - H2 GB/CAT 공존: GB(group-bg, z=1)는 tier1 유지 — cat-bg 만 tier3. 기존 동작 불변.
  - H3 엣지케이스: 접힌 카테고리(combo 부재→tier3 cat-bg)·terms combo·agg-lod 카드·카드/펼침 모드 전부 정상.
  - H4 `_isCatBg`: `data.kind==="cat-bg"` 방출은 graph-core L490 CAT: 배경 단일 지점; CATH(cat-hd)/CATX(cat-ctl)는 미매칭→tier1 유지(헤더 카테고리 메뉴 보존).
  - H5 성능: pointerdown 만 호출, tier3 단일 bucket 순회 — 무시 가능.
  - H6 증상 해소: "스키마 클러스터 빈배경→카테고리" 확정 해소, "밴드→스키마" 재발 불가(밴드 tint 여백은 tier3 카테고리, 클러스터 페인팅 영역은 tier2 스키마 = WYSIWYG), 헤더→카테고리 보존.
  - H7 테스트: T21 은 실효 가드(witness+실 `_pick` 호출; old 로 되돌리면 "빈배경→combo" FAIL). NIT: 합성 씬 하드코딩이라 data.kind 리네임/z-order drift 는 미포착(단일 방출 지점이라 위험 낮음).
- **판정: SHIP · BLOCKING 0**.
- NIT 처리: (1) diff 주석의 결함 (b)("카드/GB 가 밴드 위 우클릭을 스키마로 샜다→해소") over-claim 지적 → **수정 완료**(주석을 실 기전=combo 가로채기 + WYSIWYG 로 정정, 카드/클러스터가 밴드 위에 보이면 그 요소 메뉴가 정상임을 명시). (2) T21 합성 씬 미-import = accept(단일 방출 지점).
- 권고(비차단): POST-DEPLOY PB-0008 real-mouse 로 3대상(펼친 클러스터 빈배경/밴드 tint/헤더) 우클릭 + 밴드 내부 클러스터 단독 드래그 라이브 실측 → 본 cycle POST-DEPLOY 계획에 반영.
- Cross-ref: CHG/TASK-20260715T102901-graph-ctxmenu-hittest · test-runs.d/20260715T102901-graph-ctxmenu-hittest.md.

## REV-20260714T183808-graph-ctxmenu-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY 라이브 검증 기록 (TASK-20260714T180125-graph-ctxmenu-category, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 TASK 체크리스트 완료 + test-runs.d fragment POST-DEPLOY Run append 뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260714T180125-graph-ctxmenu-category [SKIPPED:frontend-ui-minor-additive-no-backend-no-rbac] 가 정본.
- 라이브 실측 요지(win-browser 실 Windows Chrome/150, 배포 154fb916): 배포 전달 + 라이브 도달성 + **수정 핸들러 우클릭 dispatch 파이프라인 실증** PASS. 리터럴 CAT 밴드 위 '카테고리' 메뉴 육안 = DEFERRED(제품-매핑 scope 필요 — 도달 가능 scope 가 전부 미분류라 밴드 미방출; 코드-로직 airtight + 파이프라인 실증으로 고신뢰, 사용자 1-probe 권장).
- Cross-ref: REV-20260714T180125-graph-ctxmenu-category(기능 정본) · CHG-20260714T183808-graph-ctxmenu-postverify · test-runs.d/20260714T180125-graph-ctxmenu-category.md POST-DEPLOY Run.

## REV-20260714T180125-graph-ctxmenu-category [SKIPPED:frontend-ui-minor-additive-no-backend-no-rbac] — 그래프 카테고리 밴드 우클릭 전용 메뉴 (TASK-20260714T180125-graph-ctxmenu-category)
- Panel skip 사유(§18.8): 프론트 그래프 JS 2파일·additive(신규 메뉴 함수 1 + dispatch 1줄 라우팅 교체)·백엔드/RBAC/스키마/엔드포인트 0·비파괴. 위험 표면 = 우클릭 메뉴 dispatch 한정.
- 적대적 자가검토(4가설 refute): ① "CAT 밴드가 여전히 combo 로 fall-through" → **refute**: Pixi `_pick`(graph-renderer-pixi.js L446-451)은 node hit 을 combo 보다 우선(L448 `if(n) return n`), CAT 배경 노드는 밴드 전체 bbox(size:[bw,bh])이고 hit-grid 는 built.nodes 무필터 포함이라 밴드 영역 우클릭은 반드시 `node:contextmenu`(kindEvt=node) 도달 → L2086 전용 라우팅. combo fall-through 불가. ② "catKey 추출 오류" → **refute**: `id.replace(/^CAT(H|X)?:/, "")` 가 CAT:/CATH:/CATX: 3종 모두 cat.key 로 정규화(좌클릭 핸들러 slice(4/5)와 동치). ③ "의존 심볼 미정의" → **refute**: `_metaGraph.catLabelOf/catCollapsed/catMembers`(graph-state)·`_metaGraphShowCategoryDetail`(동일 파일)·`_metaG6Apply`/`_metaGraphCopyText`(import·기존 combo 메뉴에서 사용) 전부 존재 확인. ④ "접기 토글이 좌클릭 CATX 와 이중 발화" → **refute**: 우클릭 메뉴 onClick 은 catCollapsed 토글+`_metaG6Apply(false)` 1회, 좌클릭 CATX 경로와 독립(동시 발화 없음).
- 근거/대안: 대안A(L2085 hide 유지)=사용자 "밴드 우클릭 무반응/클러스터 오노출" 미해소로 기각. 대안B(combo 핸들러에서 CAT 분기)=hit-test 상 CAT 는 node 이벤트라 부적합. 채택=node 핸들러 전용 라우팅 + 전용 메뉴(combo 메뉴 구조 파리티: 상세·접기/펼치기·복사).
- deploy_scope: included(FIRST_REQUEST) 근거로 cycle-final 후 web 재배포 사전 승인. POST-DEPLOY PB-0008 라이브 잔여.
- Cross-ref: CHG-20260714T180125-graph-ctxmenu-category · test-runs.d/20260714T180125-graph-ctxmenu-category.md.

## REV-20260714T080000-account-subtabs-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260714T074417-account-subtabs, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 TASK 체크리스트 완료 + TEST POST-DEPLOY append + MODIFY -postverify CHG뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260714T074417-account-subtabs [SUBAGENT] (SHIP)가 정본.
- 라이브 실측 요지: win-browser 실 Windows Chrome, 라이브 53e55bfe. 하위탭 4개·기본 account·각 전환 시 정확히 1 subpane 노출 assertion 전항목 PASS·서빙 심볼 확인·세그먼트 하위탭 바 시각 렌더(스크린샷). 1차 배포 soak false-positive 롤백→재배포 PASS(정적자산 /healthz 무관·동시부하 transient).
- Cross-ref: REV-20260714T074417-account-subtabs(기능 정본) · CHG-20260714T080000-account-subtabs-postverify · TEST Run POST-DEPLOY.

## REV-20260714T074417-account-subtabs [SUBAGENT:adversarial-diff-review] — 프로필 '계정' 탭 하위 세분화(계정/알림/UI/사용 내역) (TASK-20260714T074417-account-subtabs, Minor §12.3, frontend-only) — SHIP
- 렌즈: 적대 코드리뷰 서브에이전트(general-purpose) — diff 한정, 5축(섹션 배치 무손실/id 보존·lazy 렌더 정합·first-open 기본 하위탭·이벤트 배선·DOM/CSS 균형).
- **건전 확인(결함 0):** ① 7섹션이 4 subpane 에 정확히 1회씩 배치·손실/중복 0·필수 element id 20종 전부 정확히 1회(grep 확증). ② lazy 렌더 정합 — 활동 dl 은 openProfile→renderProfile 이 계속 채움(기본 노출 account subpane), 모든 change 핸들러는 initialize() 에서 getElementById/querySelectorAll 로 바인딩(=`.hidden` 무관 유효), renderNotifyPrefs/renderMotionPref/loadProfileUsage 는 display-only(SoT=localStorage/API)라 하위탭 활성 시 렌더 지연이 stale 유발 안 함, `dChk.disabled` interlock 은 change 핸들러+subpane open 에서 재적용, renderProfileTotp 는 innerHTML clear-후-rebind 라 반복 토글 리스너 누수 없음, 기존 테스트가 구 평면 구조 참조 0. ③ first-open — `state.accountSubtab` undefined→'account', 정적 HTML 기본값(account is-active/others hidden)이 switchAccountSubtab('account') 결과와 정확히 일치(오패널 flash 없음). ④ 이벤트 배선 — 하위탭 버튼 initialize() 1회 바인딩(중복 없음), openProfile 기본 prompt 탭+state.accountSubtab 세션 유지로 계정 재진입 시 마지막 하위탭 복원(의도 일치). ⑤ 구조 — pane div 균형 32/32, 전역 button reset 로 `.profile-subtab` UA chrome 없음, `state` 모듈 const.
- **Deferred NIT(비차단, 회귀 아님):** 하위탭 버튼에 role="tab"/aria-selected 는 있으나 subpane 에 role="tabpanel"·aria-controls/labelledby·화살표 roving 미비 — 단 부모 drawer-tab 은 role 자체가 없어 본 변경은 additive(퇴행 아님). 부모 탭 ARIA 정비와 함께 추후 일괄 개선 권장.
- **Verdict: SHIP** (blocking/major/minor 0, deferred a11y NIT 1).
- Cross-ref: TASK/CHG/FUNCTION-20260714T074417-account-subtabs · TEST Run(2026-07-14) account-subtabs · 선행 anim-effect-pref · ANCHOR 0003 무충돌.

## REV-20260714T073000-anim-effect-pref-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260714T065503-anim-effect-pref, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 TASK.md 체크리스트 완료 + TEST.md POST-DEPLOY 라이브 PASS append + MODIFY -postverify CHG뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260714T065503-anim-effect-pref [SUBAGENT] (FIX-THEN-SHIP→반영 후 SHIP)가 정본. 본 엔트리는 배포 후 라이브 실측 결과 기록만.
- 라이브 실측 요지: win-browser 실 Windows Chrome, 라이브 f00519dd. 게이트 로직 assertion 전항목 PASS(off→reduced true·on→false OS무관·os→OS일치·data-motion 반영·select 3옵션+hydration·캘린더/검색 scrollMessagePointIntoCenter 라우팅)·서빙 자산 stamp/심볼 확인·프로필 계정 탭 select 시각 렌더(스크린샷). 한계: 검증 머신 reduce-motion off라 육안 모션 시연 불가(로직은 결정적 실증).
- Cross-ref: REV-20260714T065503-anim-effect-pref(기능 정본) · CHG-20260714T073000-anim-effect-pref-postverify · TEST Run POST-DEPLOY.

## REV-20260714T065503-anim-effect-pref [SUBAGENT:adversarial-diff-review] — 작업 화면 애니메이션 복원 + 인앱 "애니메이션 효과" 설정 (TASK-20260714T065503-anim-effect-pref, Major §12.3, frontend-only) — FIX-THEN-SHIP → 반영 후 SHIP
- 렌즈: 적대 코드리뷰 서브에이전트(general-purpose) — diff 한정, 5축(라우팅 등가성·회귀 표면/TDZ·접근성·UI 배선·null/예외 가드). §18.8 dispatch: UI/화면 신호 → ux/design 후보이나, 프론트 단독·비파괴·서버계약/RBAC/스키마 0 라 단일 적대 코드리뷰로 수행.
- **적발(MAJOR 1건, 반영):** 크로스페이드 고스트에 걸린 별도 CSS 미디어쿼리 `@media (prefers-reduced-motion: reduce) { .messages-switch-ghost { display:none } }`(styles.css) 는 인앱 pref 로 덮이지 않아, **OS reduce-motion ON + 인앱 '항상 켬'** 시나리오에서 JS 가드는 통과해 고스트를 생성하지만 CSS 가 `display:none` 으로 가려 "빈 화면 후 fade-in"(크로스페이드 아님)이 되어 **대표 효과(크로스페이드)가 정작 복원 안 되는** 결함. 이 시나리오가 바로 본 기능의 목적이자 POST-DEPLOY PB-0008 검증 항목. → **수정:** `html:not([data-motion="on"]) .messages-switch-ghost { display:none }` 로 이관(이미 init 배선된 `<html data-motion>` 속성 재사용 — 이로써 data-motion 이 "미래용"이 아니라 현재 필수임도 확인). 크래시/누수 없음(fallback 타이머가 숨은 고스트 정리)이라 순수 시각 결함이었음.
- **건전 확인(결함 없음):** ① 캘린더/검색 점프 라우팅(`scrollMessagePointIntoCenter`)은 기존 native `scrollIntoView({behavior:"smooth",block:"center"})`와 실무상 동형 — 타깃은 항상 `messageLogEl` 내부(point-rail dot 클릭과 동일 패턴)·`off`/reduce 시 `setter(to)` 즉시이동(no-op 아님)·`!messageLogEl` no-op 은 `#messageLog` 안정 요소라 불가. ② TDZ 없음 — `MOTION_PREF_KEY` const 접근자 전부 hoisted 함수 선언·런타임 호출(6124 이전 top-level 호출 경로 없음, `initialize()`는 그 뒤 실행). ③ 기본 `os`=기존 로직 byte-동치(회귀 표면 0). ④ localStorage read/write/setAttribute 전부 try/catch. ⑤ null 가드 존재(renderMotionPref·change 리스너·scrollMessagePointIntoCenter). ⑥ UI 배선 정확(`#motionEffectSelect` ∈ `data-profile-pane="security-and-account"`·renderMotionPref 동일 탭 dispatch). ⑦ 접근성 — 기본 `os`가 OS 신호 보존, 인앱 override 는 내부도구 정당 opt-in. `node --check app.js` PASS·잔여 native smooth-into-center 0(10503/10514 는 `block:"nearest"` 의도적 즉시).
- **Verdict: FIX-THEN-SHIP → MAJOR 반영 완료(styles.css data-motion 가드) → SHIP.**
- Cross-ref: TASK/CHG/FUNCTION-20260714T065503-anim-effect-pref · TEST Run(2026-07-14) anim-effect-pref · ANCHOR 0003 무충돌.

## REV-20260713T101500-ds-conn-test-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260713T094624-ds-conn-test, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 test-runs.d fragment POST-DEPLOY append + TASK.md 체크리스트 완료뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260713T094624-ds-conn-test(AGENT-TEAM 3렌즈 SHIP)가 정본. 본 엔트리는 배포 후 라이브 실측 결과 기록만.
- 라이브 실측 요지(배포 02a1e585, https://localhost/ bootstrap_admin console_access, win-browser Chrome relay): AC-1 15 DS 배지 전부 `<button.product-dropup-item-ds--test>`(aria-label·min 24px·테두리)·AC-2 클릭→실 probe "✓ 연결 성공(11.8ms)" 토스트 top=66px(composer 769px 위, 입력창 비가림)·단발성 자동숨김·AC-4 제품 미전환(stopPropagation)·AC-5 프론트 쿨다운 "4초 후 다시" 발화·AC-6 admin `#adminToast` 하단 불변·AC-7 pageerror 0. Evidence scratchpad/ds-conn-test-postdeploy.png.

## REV-20260713T094624-ds-conn-test [AGENT-TEAM:backend+frontend+ux 3lens] — 작업화면 제품 드롭업 데이터소스 '연결 테스트' 버튼 + 상단 단발성 토스트 (TASK-20260713T094624-ds-conn-test, Major §12.3)
- §18.8 dispatch(UI/button/toast → ux·design / API·endpoint·throttle → backend·security / frontend correctness → qa) 3-렌즈 적대 패널. **적발 결함 전건 반영 후 SHIP**.
- **설계 결정(AskUserQuestion 2026-07-13)**: ① 연결 테스트 = **A2**(관리자 엔드포인트 `POST /api/admin/datasources/{key}/test` 재사용 — 별도 RBAC 추가 없음) + 남용 방지 프론트/백 재시도 텀. ② 상단 토스트 = **C2**(작업화면 전체 `#toast` 상단 앵커, admin `#adminToast` 하단 불변).
- **backend+security 렌즈 (BLOCKING/MAJOR 0)**: throttle check-and-set 이 이벤트루프 단일스레드에서 원자적(intra-worker TOCTOU 없음)·prune 반복 iteration-safe·성장 bound(≤3072)·conn 은 DI(yield) teardown 이 early-return 마다 close(누수 0)·429 는 authz(403) 이후라 무권한 존재 노출 없음·자격증명 비유출. 반영: **NIT-1** throttled 반환 `max(1.0, round(...))` 로 0.0 pass-sentinel 충돌 제거 · **NIT-2** `retry_after_ms` int 화 · **NIT-3** throttle 을 resolve/SSRF **이후·probe 직전**으로 이동(무-probe 404/SSRF 경로 미소진·404 마스킹 제거) · **NIT-4** 중복 guard 단순화 · **MINOR-1** env 파싱 try/except(오타로 web 모듈 import 죽음 방지). MINOR-2(게이트 폭=console_access ⊃ datasource.manage) 는 "표시 허용 + backend 403 fallback"(app.js `can()` TASK-0098) 관례 준수로 accept(REPORT §8).
- **frontend+QA 렌즈**: **HIGH** — 무조건 `canOpenAdminConsole()` 호출이 `verify_profile_icon_consistency.mjs` 하네스에서 `ReferenceError`(스텁 부재)로 테스트 전체 붕괴 → **하네스에 `canOpenAdminConsole` 스텁(false) 추가**. **MED-HIGH** — `is-testing`의 `pointer-events:none` 가 더블클릭을 부모(제품 선택)로 라우팅 → **실제 `<button>` + `disabled` 로 교체**(disabled 버튼은 클릭이 부모로 안 샘). **MED** — 쿨다운 `|| 0` sentinel 이 `performance.now()`에서 로드 4초 내 첫 클릭 오차단 → **`.has()` sentinel 로 수정**. LOW(단일/멀티 cdKey 상이·느린 테스트 시 진행토스트 조기소멸)=백엔드 429·is-testing 시각단서로 커버, accept. CORRECT 확인: 정상 클릭 stopPropagation·무권한 byte-동치 span·`_prev` 429 배지 상태 유지.
- **UX+a11y 렌즈**: **MAJOR-1** 중첩 인터랙티브(`span[role=button]` in `<button role=menuitem>` = 비적합 HTML+ARIA) → **행을 `<div role=menuitem tabindex>` (click+keydown 선택 복원) + DS 라벨을 실제 `<button>`** 으로(button-in-button 제거). **MAJOR-2** at-rest 어포던스 없음 → **가시 테두리 + hover 틴트**(display-only 배지와 구분). **MAJOR-3** 접근가능한 이름=DS키뿐 → **`aria-label="<key> 연결 테스트"`**. **MINOR-4** 터치타깃<24px → **min-height 24px**(WCAG 2.5.8). **MINOR-6** narrow 뷰포트 토스트 overflow → **`#toast max-width: min(460px, calc(100vw-32px))`**. **NIT-9** 배경색 snap → `#toast` transition 에 background 추가. MINOR-7(짧은 뷰포트 상단 토스트가 위로 열린 드롭업 상단 일부 가림)·NIT-8(테스트/비테스트 배지 2px 정렬차) = 엣지, accept. 확인: `#toast` id specificity 로 admin 격리·`box-sizing:border-box` 로 hover 무-reflow·단발성.
- **검증**: `node --check`(app.js·admin.js module) · `py_compile` · CSS 1780/1780 · 타깃 6/6 · **전체 1902 passed / 2 skipped / 0 failed**(회귀 0). 라이브=POST-DEPLOY PB-0008(win-browser relay 열림).
- **VERDICT: SHIP-WITH-FIXES → 전건 반영 후 SHIP.**

## REV-20260713T061500-attach-user-version-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260713T053423-attach-user-version, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 TEST.md §4(Windows-browser Run: 배포 후 잔여 → POST-DEPLOY 라이브 PASS)·TASK.md 체크리스트 완료·MODIFY.md postverify CHG 뿐 — 코드/자산/스키마/RBAC 0. 기능 코드 적대 검증은 직전 REV-20260713T053423-attach-user-version(SUBAGENT:security SHIP)이 정본. 본 엔트리는 배포 후 라이브 실측 결과 기록만.
- 라이브 실측 요지(배포 7f1ed748, https://localhost/ bootstrap_admin, win-browser Chrome/150): AC-AUV-1 v2 체인 편입(root 490)·AC-AUV-2 동일 멱등(491 reused)·AC-AUV-3/5 체인 정합(v1 superseded/v2 최신·목록 최신만)·**AC-AUV-4 assistant 가 v1→v2 diff 정확 인지**(SELECT 1→2·주석 추가; new_attachment_ids 미포함 턴엔 정직 "비교 불가"·환각 0)·AC-AUV-6 UI v2 배지+diff 색상 렌더. Evidence artifacts/shared/win-browser-shots-attach-user-version/01_version_badge_and_assistant_diff.png.

## REV-20260713T053423-attach-user-version [SUBAGENT:security 1lens] — 사용자 재업로드 첨부 버전 관리 (TASK-20260713T053423-attach-user-version, Major §12.3, cross-cut feature-0002)
- §18.8 dispatch(첨부 업로드 경로 + LLM 컨텍스트 + IDOR/인젝션 → security 렌즈) 적대적 리뷰 **VERDICT: SHIP (blocking/major 0)**. 7 렌즈(IDOR·체인무결성·인젝션·dedup누출·SELECT index·byte-동치·fail-soft) 전수 SAFE 판정 + MINOR 2 + NIT 1 → **전건 반영 후 재검 PASS**.
- **설계 결정(사용자 승인 3건, AskUserQuestion 2026-07-13)**: ① 재업로드 인식 = 파일명 자동감지(대화 내 동일 파일명·동일 account 최신 head 와 sha256 대조) ② assistant 인지 = 버전 표식 + 변경점 diff 자동 주입 ③ 과거 버전 비교 = 체인 정합 + assistant 비교(신규 UI 최소). 동일 해시 = 기존 재사용(멱등, "완전히 같은 파일이 아니라면 버전업" 요청 정합).
- **보수적 구현 결정**: 기존 assistant materialize 경로(`_materialize_assistant_attachment_edits`)를 **리팩터하지 않고** 사용자 버전 로직을 업로드 핸들러에 별도 구현 — 보안 리뷰 완료된 delicate 경로의 회귀 위험 회피(중복 ~수십 줄 수용, 향후 공통 `_append_attachment_version` 추출은 REPORT §8 개선 제안으로 기록). 체인 스코프를 `(ConversationId, AccountId, filename)` 로 둬 그룹 대화 타 멤버·타 대화 동명 파일과 혼입 차단(materialize 가드 2 대칭).
- **MINOR-1 (PLAUSIBLE, 수정)**: 동시 재업로드가 같은 `(root, version)` 선점 시 `UQ_WCA_VersionChain` 위반이 raw HTTP 500 으로 전파(materialize 는 graceful skip). **수정**: 버전 INSERT 를 `_insert_attachment_row(_ver)` 클로저로 추출, IntegrityError-류 예외 시 **버전 케이스만 체인 MAX+1 재계산 후 1회 재시도**(실패 시 rollback+깨끗한 500). 표준 업로드(prior 없음) 실패는 기존과 동일 500(rollback 보존). UNIQUE 가 데이터 무결성은 이미 보장 — 본 수정은 losing-request UX(500→성공/재시도).
- **MINOR-2 (CONFIRMED mechanic, 수정)**: `_datamark_untrusted` 이 `content` 만 sentinel strip 하고 `label` 은 미strip → 사용자 제어 파일명이 label 로 들어가면 위조 close 마커로 구획 breakout 가능(기존 `:814` 파일 본문 label 도 동일 벡터 — 본 diff 는 확장). **수정**: `_datamark_untrusted` 이 label 도 strip(전 caller 방어). 파일명이 datamark **밖** header(`### {fname}: vN→vM`)로 노출되는 부분은 기존 파일목록 라인(`file "{fname}"`)과 동일 계열(pre-existing) — 파일명 전역 sanitize 는 REPORT §8 후속 제안으로 기록(본 cycle scope 밖, 그룹은 force_sender_scope 로 cross-account 인젝션만 잔여).
- **NIT (수정)**: version_diff 를 매 턴 모든 버전 첨부에서 주입하면 "방금 변경" 문구 stale·토큰 낭비 → **이번 턴 신규 첨부(`attachment_id in new_ids_set`)에 한정** 주입. 재업로드 그 턴에 diff 주입(AC-AUV-4 충족) + 🔄v{n} 표식은 매 턴 유지(이후 턴 버전 인지·명시 비교는 버전 조회 API). 회귀 가드 테스트 `test_diff_not_injected_for_session_attachment` 추가.
- **검증**: py_compile 4 + node --check PASS · 첨부 버전 31→32 PASS(+session-gate) · `test_prompt_injection_defense`(datamark) 포함 재실행 EXIT=0 · 전체 스위트 EXIT=0(회귀 0). SELECT 컬럼 append 는 row[0..8] 보존 + `len(row)>10` 가드로 기존 9-tuple 테스트 무영향(리뷰 렌즈5 확인).
- Cross-ref: FUNCTION/TASK/REPORT/MODIFY-20260713T053423-attach-user-version · 기반 버전 인프라 TASK-0274/0275/0285/0286 · 스키마 alembic 0008 core_attachments. subagent: security 1lens(general-purpose 적대 리뷰).

## REV-20260707T110534-doc-sync-rn-0707 [SKIPPED:non-policy-doc] — 릴리즈노트 07-03/04/06/07 블록 신규(+29) + 캐시버스터 bump (TASK-20260707T110534-doc-sync-rn-0707, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`) + cache-buster(`index/admin.html`) 뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync attended 재구성이 정본(각 feature REPORT/TASK + git log) 대비 직접 검증.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS(jsdom DOM 테스트 `verify_release_notes.mjs` 는 이 실행 env 에 jsdom 미설치 — 컨테이너 전용, 문법+스키마+블록 순서로 갈음). `generated`=2026-07-07·신규 4블록(07-03/04/06/07)·스키마(type/area/title/detail) 정합·07-02 이하 블록 보존. 누출 0(내부용어 feature-id/G6/AGE/alembic/엔드포인트/권한키/모델명/ADR/step_gap_ms/conn_health/xschema/WebRuntimeSettings 0). 07-03 역할 목록 매핑 포함. aiops-ttft 는 관리자 지표라 사용자 블록 제외(기술문서만).
- Cross-ref: CHG/TASK/FUNCTION-20260707T110534-doc-sync-rn-0707 / 원천 머지 feature-0016 그래프 07-03~07(ADR-010~021·alembic 0031~0038)·feature-0003 ds-avg-latency·aiops-ttft·reasoning-effort·runtime-settings(feature-0018)·feature-0009 gc-join-notice·share-visibility-window·feature-0002/0007 insight/fallback/edge-fallback. META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit/META mode(REV-20260707T110534-META-0020-doc-sync-0707).
## REV-20260707T120000-runtime-settings-ux [SUBAGENT:design·ux 1lens] (TASK-20260707T120000-runtime-settings-ux — 런타임 설정 pane UI 재설계, web/UI CSS+JS-only, Major §12.3)
- 요청(사용자): "UI 세련도 부족 — 내부 디자인 리뷰 후 사람이 만족할 UI 로 재구성." 사전에 디자인 시스템 매핑(subagent) + 라이브 참조 pane 캡처로 콘솔 디자인 언어(정렬 grid dl·admin-badge·focus-ring 입력·commit-bar)를 근거화.
- §18.8 dispatch(UI/layout → ux·design) **적대 디자인/UX 렌즈 1차 VERDICT NO-SHIP** — 2 MAJOR + 5 MINOR + 4 NIT 적발. **전 항목 수정 후 SHIP**:
  - **MAJOR-1 (반응형 붕괴, styles.css)**: `@media(max-width:560px)` 가 grid-row 를 재설정하지 않아 컨트롤/상태가 라벨/설명과 겹침 → child 별 grid-row 명시(라벨1·설명2·컨트롤3·상태4) 단일열 스택으로 수정.
  - **MAJOR-2 (재-핀 트랩, admin.js)**: "동일값=예약취소" 가 override 케이스만 가드해, no-override 에서 기본값 그대로 입력 시 redundant PUT(override==default 고정, 모델예산 트랩 재현·pending 배지 잔류) → 조건을 `val === item.effective`(has_override 무관)로 일반화해 서버 현재상태 재현 시 항상 예약 해제.
  - **MINOR**: ① invalid-range 분기의 reset 버튼 라벨/동작 불일치("되돌리기"인데 RS_RESET 스테이지) → 라벨 "기본값" 동기화. ② status 11px 저대비(WCAG AA 미달) → 12px + darker(--text-2·--primary-dark·#b45309). ③ 설정 nav row pending 이 색-only 테두리뿐(콘솔 계정/역할 row 는 `•` dot) → `.admin-pending-dot` 추가. ④ 설명 1줄 ellipsis 로 잘림(구 wrapping 회귀) → 2줄 line-clamp. ⑤ 8px 그리드/`.admin-field` 이탈 값 정규화(gap24·col-gap16·padding12·input 8/10·112px·13px).
  - **NIT**: ① input radius --r-sm→--r-md(admin-field 정합) ② rs-unit min-width 제거 ③ rs-reset 터치타깃 padding 4/8 ④ rerenderRuntimeSettingsPanels 를 runtime pending 있을 때만(불필요 재-fetch 가드).
- 리뷰가 확인한 양호점: buildRuntimeSettingControl 깨끗 제거(dead-ref 0, 잔여 admin-quota-*는 별개 LLM-quota 편집기)·토큰 전부 실재·RS_MODEL_PREFIX 키 분류 정확·mountedPanels 미클리어라 rerender-gate 안전·commit-bar 추가 additive+null-guard(계정/역할/프롬프트 무위험)·상태 text-backed(색-only 아님)·aria-label·focus-ring.
- 검증: node --check PASS · CSS 중괄호 균형 · 기능/백엔드/엔드포인트 불변(표현 계층만). 최종 VISUAL 검증은 PB-0008 POST-DEPLOY before/after.
- Cross-ref: CHG/TASK/TEST 동일 slug · 선행 REV-20260706T094937-runtime-settings.

## REV-20260707T121500-runtime-settings-ux-postverify [SKIPPED:doc-only-postverify] (런타임 설정 UI 재설계 POST-DEPLOY PB-0008 기록, 비-정책 doc-only)
- Panel skip 사유(§18.8/§18.4): 선행 UX 재설계(REV-20260707T120000-runtime-settings-ux [SUBAGENT:design·ux] SHIP)의 배포 후 라이브 시각검증 결과를 TEST.md 에 기록할 뿐 코드/자산 무변경(doc-only). 검증 자체(실 Windows Chrome PB-0008 before/after + commit-bar e2e + DB override roundtrip)가 정본 증적.
- Cross-ref: REV-20260707T120000-runtime-settings-ux · CHG-20260707T121500-runtime-settings-ux-postverify.

## REV-20260707T130000-reasoning-budgets [SUBAGENT:backend·ux 1lens] (TASK-20260707T130000-reasoning-budgets — 추론 강도별 예산 설정 + UI 교훈, Major §12.3 — feature-0003 web/UI + cross-unit feature-0002·shared)
- 요청(사용자): "① 가시성 개선 교훈 기록(LRN-20260707-0001 verified 반영) ② `설정 > 모델별 추론 예산`에 추론 강도별 예산 토큰값 설정 추가."
- §18.8 dispatch(백엔드 precedence·API/RBAC·UI → backend·ux) **적대 렌즈 VERDICT SHIP** — 7개 벡터 정밀 검토, **BLOCKING/MAJOR/MINOR 0**:
  - **B1 무회귀(확인)**: `thinking_budget_for_level('normal')→None` 이라 `_call_llm` 의 reasoning-override 분기(agent_core.py) 미진입 → 모델 override 분기로 낙하. `reasoning_budget:high` 는 'normal'/미지정 요청에 절대 주입 불가(test_reasoning_effort precedence 테스트로 고정).
  - **precedence(확인)**: 명시 레벨이 reasoning 분기 선점 → `_think_budget` 비-None 이라 모델 override 분기 skip → 둘 다 설정 시 레벨이 모델보다 우선. override→12000, 미설정→기본 10000.
  - **clamp 안전(확인)**: override 는 resolver+validate 로 [1024,16000], `_call_llm` 이 `min(budget, max_tokens-1024)` 재-clamp → 16000<agent 20000, 신규 max 노출 없음(기존 effort cap 과 동일).
  - **serialize/endpoint(확인)**: `reasoning_budget:` vs `model_thinking_budget:` 키 startsWith 충돌 없음, 버킷 분리 정확. 기존 PUT/DELETE·validate_value·spec_for·audit 재사용(신규 로직 0). 프론트 `reasoning_budgets` 소비·빈 배열 graceful·pre-fill 정확(기본값이 실제 주입값).
  - **워커 패리티(확인)**: `_payload_to_kwargs → run_agent → 동일 _call_llm` — 별도 extra_body 구성 경로 없음, 우회 없음.
- **NIT 3(인지, 무해 — 미수정)**: ① reasoning row 의 `default_known` 은 프론트 미사용(모델 row 와 row shape 균일 유지 위해 보존) ② 테스트가 `_rs._cache['frozen']` 직접 리셋(기존 snap fixture 와 동일 패턴, 내부 테스트 한정) ③ 일부 테스트 `stmt; assert` one-liner. 모두 기능 무영향 — ship 후 정리 대상.
- 양호점: 기본값을 `thinking_budget_for_level` 로 동적 read(하드코딩 drift 없음), `_reasoning_budget_specs` 가 REASONING_LEVELS 증감에 자동 확장·None 레벨 자동 제외, memoization 유효, 대소문자 정규화 정합.
- 검증: 신규 테스트 +7(레지스트리 4 + _call_llm precedence 3) · **컨테이너 전체 스위트 RC=0** · 로컬 회귀 0. VISUAL 은 PB-0008 POST-DEPLOY(TEST.md §3).
- Cross-ref: CHG/TASK/FUNCTION/TEST 동일 slug · LRN-20260707-0001 · 선행 REV-20260706T094937-runtime-settings·-ux.

## REV-20260707T131500-reasoning-budgets-postverify [SKIPPED:doc-only-postverify] (추론 강도별 예산 POST-DEPLOY PB-0008 기록, 비-정책 doc-only)
- Panel skip 사유(§18.8/§18.4): 선행 REV-20260707T130000-reasoning-budgets [SUBAGENT:backend·ux] SHIP 의 배포 후 라이브 검증 결과를 TEST.md 에 기록할 뿐 코드/자산 무변경(doc-only). 검증 자체(실 Windows Chrome PB-0008 + reasoning-key write-path e2e + 사용자 override 보존)가 정본 증적.
- Cross-ref: REV-20260707T130000-reasoning-budgets · CHG-20260707T131500-reasoning-budgets-postverify.
## REV-20260707T051054-kb-candidate-adoption [AGENT-TEAM:security-authz+backend-correctness+frontend-ux] (TASK-20260707-kb-candidate-adoption — 지식베이스 메타데이터 채택 인박스 + ENUM 대화 자율수집, Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002·shared) — VERDICT: SHIP (BLOCKING 0 · MEDIUM 2 FIXED · LOW 2 FIXED + 1 ACCEPT-RESIDUAL · NIT 2 FIXED)
- §18.8 패널: staged diff(마이그·kb_glossary·llm·config·agent_core·app·admin_metadata·admin.html/js·styles.css) 대상 general-purpose 적대 서브에이전트 3렌즈 병렬 — 보안·인가 / 백엔드·정합성 / 프런트·UX. 각 렌즈는 "승인 아님, 결함 적발" 지시.
- **보안 렌즈**: **[MEDIUM FIXED]** `kb.enum.curate` 가 `_ensure_seed_roles` catchup(app.py) 명시 목록에 부재 → 기존 배포 admin 이 request-time 에 권한 미보유 → enum-feedback 3 엔드포인트 403(fail-closed lockout, 채택 인박스 ENUM 절반 사망). 주석은 "catchup 부여" 라 주장했으나 실제 목록에 없음(kb.glossary.curate·kb.sample.curate 도 동일 잠재 gap — 도입 cycle 누락). **수정**: catchup 목록에 `kb.enum.curate`+`kb.glossary.curate`+`kb.sample.curate` 추가(INSERT IGNORE 멱등, 내 인박스 양쪽 + 기존 glossary/sample lockout 동시 해소). **[LOW ACCEPT-RESIDUAL]** LLM-derived confidence 로 auto-promote(source='auto') 유도 가능(프롬프트 인젝션 "confidence 1.0") — 하이브리드 자동승급 설계 고유 잔여(용어사전 0021 승인 설계와 동일). 완화: auto 행 되돌리기 가능·rejected 재유입 차단(pre-check + ON CONFLICT WHERE pending)·0.9 임계·검토 큐. confidence 는 `llm_enum_suggest` 가 이미 [0,1] clamp → 실 파이프라인 무영향. 결함 아님(설계 인지 잔여). **검증 무결**: 엔드포인트 gating 3/3·least-privilege(operator/sales/pending 미부여·`_METADATA_MANUAL_IMPLIES` 미포함)·마이그 GRANT(0023 parity)·poisoning 순서(REV-20260629 BLOCKER clone)·XSS(textContent-only)·scope 격리(id+FOR UPDATE)·SQL 파라미터화 전부 PASS.
- **백엔드 렌즈**: **정합성 결함 0** — 용어사전 twin(0021/0023) 대비 line-by-line parity 확인(record/auto_promote/promote/reject/list/count SQL·컬럼순서·router r[0..14] 매핑·마이그 체인 0038→0039 단일 head·idempotent·set_updated_at·CHECK 값·`_enum_autopropose` double-wrapped soft-fail·config `__all__`·llm_enum_suggest 필터). **[NIT FIXED]** 마이그 docstring 이 source 도메인을 `manual|auto|auto_promoted` 로 표기(코드는 manual/auto 만·auto_promoted 는 feedback.status) → docstring 정정. **[cosmetic no-action]** `admin_list_enum_feedback` 가 `_metadata_iso` 직접 사용(glossary 는 `_glossary_feedback_iso`) — 후자가 전자의 1-line delegate 라 동작 동일.
- **프런트 렌즈**: **[MEDIUM FIXED]** 탭 pending 배지가 종류 필터로 좁혀진 부분 합계(`pendingTotal`)로 덮어써져, "용어사전" 필터 시 ENUM pending 이 배지에서 사라짐(전역 신호 훼손) → **수정**: `kind==='all'` 일 때만 부분 합계 사용, 좁혀졌으면 `_primeAdoptionBadge`(양쪽 재조회)로 정확도 보존. **[LOW FIXED]** 빈/로딩/오류 placeholder 가 grid 셀(440px)에 갇혀 좁게 렌더 + 로딩 노드가 empty 와 다른 미스타일 → `.admin-adoption-empty` 클래스 통일 + CSS `grid-column:1/-1`. **[NIT FIXED]** `_adoptionBucket(it)` 이중 호출 → 1회 계산. **[NIT no-action]** `.admin-meta-tag-kind` 고정 hex(다크 override 없음) — 기존 형제 태그(-ok/-warn/-role/-stale) 와 동일 규약이라 신규 결함 아님. **검증 무결**: fail-open 방지·first-entry 훅·per-kind 403 경로 없음·XSS·이벤트 배선 멱등(dataset.bound)·재사용 전역(_metaRoleLabel/_metaDatasourceLabelOf/apiFetch/can/showToast) 정의 확인·a11y(aria-label·aria-live) PASS.
- **재검증**: 수정 후 `node --check`·`py_compile` PASS. 관련 43 + 호스트 전체 스위트 **1582 passed**(회귀 0; share_redaction 7 = 컨테이너 `web.app` 경로 host-env 아티팩트, 본 변경 무관). catchup 목록 계약을 검사하는 테스트 없음(추가 3건 무회귀).
- Cross-ref: TASK/MODIFY/FUNCTION/TEST-20260707-kb-candidate-adoption · feature-0002 REPORT(2026-07-07).

## REV-20260707T064745-metadata-console-redesign [AGENT-TEAM:correctness-regression+xss-security+design-consistency] (TASK-20260707-metadata-console-redesign — 메타데이터 콘솔 IA 통합 + 5서브뷰 디자인 폴리시, Major §12.3 — feature-0003 web/UI 단독) — VERDICT: SHIP (BLOCKING 1 FIXED · MAJOR 1 FIXED · HIGH 1 FIXED · MED 3 FIXED · LOW 5 FIXED · ACCEPT 1)
- §18.8 패널: 위임 구현(2차 보기 일반화 + ENUM/샘플 검토 큐 편입 + 디자인 폴리시 10종)의 uncommitted diff 대상 general-purpose 적대 서브에이전트 3렌즈 병렬(정합·회귀 / XSS·보안 / 디자인·일관성). 위임 구현이라 특히 엄격 검증.
- **정합 렌즈**: **[BLOCKING FIXED]** `kb.enum.curate` 가 `ADMIN_TAB_PERMISSIONS.metadata` OR-게이트에서 누락 → ENUM 검토 큐를 metadata 탭 하위로 이관했는데 enum-curate 단독 사용자가 metadata 탭 자체를 못 봐 접근 완전 상실(회귀). 대칭성 확증(kb.glossary.curate·kb.sample.curate 는 존재). **수정**: 게이트에 `kb.enum.curate` 추가. **[MAJOR FIXED]** ENUM 그룹핑이 `schema.table` 키+행 code-only 로 column_name 드롭 → 같은 테이블 두 컬럼의 동일 코드 모호. **수정**: `schema.table.column` 그룹 + 헤더 `table.column`. **[MINOR FIXED/ACCEPT]** feedback.status 서브탭 간 이월(수정) · 샘플 배지 백엔드 limit 캡 과소집계(accept — 백엔드 정본). **검증 무결**: dangling 참조 0·디스패치(kind별 로더)·필드 매핑(enum schema/table/column/code/suggested_label)·동적 버튼 idempotency(replaceChildren)·서브탭 가시성 OR·viewBySub 격리·CRUD 보존 전부 PASS.
- **XSS 렌즈**: **CLEAN** — 신규/변경 렌더(renderFeedbackQueue/renderSampleReview/_metaRenderGroupedList/_metaSyncViews/empty·loading·KPI/폼검증) 전부 createElement+textContent(SQL=pre>code.textContent). 오히려 구 innerHTML+esc 경로를 순수 DOM 으로 대체. 신규 innerHTML-with-data 0건.
- **디자인 렌즈**: **[HIGH FIXED]** light-only 콘솔(다크 팔레트 부재)에 `--surface-2`·`--tag-*` 다크 @media override 를 얹어 OS-dark 시 배지 저대비·카드/pill fill 소멸 회귀 → 다크 override **제거**(light 값이 정답). **[MED FIXED×3]** 스켈레톤 shimmer 무효(--surface-2==--border-subtle → 구분 grays) · `.admin-sf-row` 옛 divider 기하(→카드) · 싱글턴 그룹 카드 스팸(→1건은 flat 행). **[LOW FIXED×5]** KPI 가 #metadataCount 중복(→미기재 M 만·없으면 hide) · 카드행 focus-visible 부재(→ring) · role==provenance 파란색 충돌(→provenance=neutral gray) · vote 이모지(→추천/비추천 텍스트) · 글리프/color-mix nit. **잘 된 점**: light hover≠active 3-상태 분리·rich empty·인라인 검증·폼 grid·색-only 아님(텍스트 동반) 실효 확인.
- **재검증**: 수정 후 `node --check` OK · B1 게이트·H1 다크제거·M1 컬럼·L7 neutral·L5 KPI grep 확인 · 호스트 전체 **1637 passed**(회귀 0) · CSS 균형(1897/1897).
- Cross-ref: TASK/MODIFY/FUNCTION/TEST-20260707-metadata-console-redesign.

## REV-20260707T230501-doc-sync-rn-2305 [SKIPPED:non-policy-doc] — 릴리즈노트 07-07 블록 2항목 append(코드값 후보 채택 + 추론 강도별 예산) + 캐시버스터 bump (TASK-20260707T230501-doc-sync-rn-2305, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`) + cache-buster(`index/admin.html`) 뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync(ULTRACODE 8-agent analyze+adversarial-verify 워크플로 wf_731a14ae)가 정본(feature-0002/0003 REPORT/TASK + git log) 대비 직접 검증.
- **적대 검증 반영(중복 catch)**: 워크플로 verify:release 가 초안의 item①(업무 용어+코드값 통합 채택)을 **과대주장으로 반증** — 업무 용어(glossary) 대화 자율수집·검토 큐는 2026-06-29 블록(라인 408·414)에 이미 landed. → item① 을 **코드값(ENUM) 측만으로 rescope**('용어사전' 표현 전량 제거), summary 도 동일 정정. 최종 append=2항목(코드값 채택 + 추론 강도별 예산).
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS. jsdom DOM 테스트(`verify_release_notes.mjs`)는 이 실행 env 에 jsdom 미설치(컨테이너 전용) — 문법+스키마+블록 순서(07-07>06>04>03>02)+07-06 이하 보존으로 갈음. 누출 0(내부용어 feature-id/enum_feedback/kb_glossary/_enum_autopropose/kb.enum.curate/alembic/reasoning_budget/ADR/모델명 0). skip(비-사용자): 콘솔 IA(47a63b1a UI reorg)·그래프 화살표(b0d9deb6)·pane 재설계(a2fe4103)·OAuth cron(058fec05)·§56 sync(fe05d6f8·94e2e411).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260707T230501-doc-sync-rn-2305 / 원천 머지 0beb02e3(KB 채택 인박스+ENUM 자율수집)·d9516aee(추론 강도별 예산). META(STATUS·wiki·ARCHITECTURE noChange·RELEASE_NOTES·meta/REVIEW)는 별도 commit/META mode(REV-20260707T230501-META-0021-doc-sync-0707-2305).

## REV-20260708T012922-metadata-console-polish [SKIPPED:minor-css-polish-post-visual-review] (TASK-20260708-metadata-console-polish — 메타데이터 콘솔 잔여 디자인 폴리시 5건, Minor §12.3 — feature-0003 web/UI 단독)
- Panel skip 사유(§18.4/§18.8): 본 cycle 은 선행 metadata-console-redesign(REV-20260707T064745, [AGENT-TEAM] SHIP + 배포 35e8cb14)의 **PB-0008 실 Windows 브라우저 적대적 미적 검증**(로그인→전 5서브뷰→2차 보기→그룹 카드→편집 폼 라이브 캡처·판정)에서 도출된 잔여 미세 폴리시 5건을 적용할 뿐이다. 즉 **적대적 디자인 리뷰가 이미 선행**됐고 본 변경은 그 findings 의 이행(순수 시각 CSS + confidence 배지 클래스 1개 교체 — 신규 로직 경로·백엔드/RBAC/스키마/구조 0). 코드 적대검증 대상 아님(§18.8 표 `[SKIPPED:*]`).
- 적용 findings: #1 2차 보기 필 위계 역전(borderless 경량화) · #2 list-detail sprawl(메타 전용 스코프 균형) · #3 그룹 cards-in-card nesting(divider 평탄화) · #4 반복 timestamp 노이즈(경량+그룹 내 숨김) · #5 신뢰도 배지 무리 속 매몰(accent 분리). 검증: node --check OK · CSS 균형(1905/1905) · route 골든 불변 · 호스트 1662 passed(회귀 0). POST-DEPLOY PB-0008 라이브 재확인이 본 폴리시의 정본 증적.
- Cross-ref: TASK/MODIFY/FUNCTION/TEST-20260708-metadata-console-polish · 선행 REV-20260707T064745-metadata-console-redesign.

## REV-20260708T033320-metadata-console-ux2 [SUBAGENT:mainloop-adversarial-correctness+xss+coordination] (TASK-20260708-metadata-console-ux2 — 메타데이터 콘솔 UX 4건, Major §12.3 — feature-0003 web/UI 단독) — VERDICT: SHIP (BLOCKING 0 · MINOR 2 noted)
- 절차 주: 계획한 병렬 서브에이전트 §18.8 패널(정합/XSS/UX 3렌즈)이 **세션 사용량 한도**(reset 12:30 KST)로 스폰 실패. 이에 **메인 루프에서 diff 를 직접 적대 검증**하고, **PB-0008 라이브(배포 후)를 1차 행동 실증**으로 삼는다(한도 리셋 후 서브에이전트 패널 재실행 가능). 자기 재호출 wakeup 은 걸지 않음(CLAUDE.md 정책).
- **정합/coordination**: `_metaRenderReviewDetail`(우측 상세)·`_metaRenderDetail`(3555) 분기 정독 — review view+`reviewSelected.item` 시 상세 렌더(empty/폼/부트스트랩 hide), 아니면 reviewBox hide+clear. `reviewSelected` 초기화 3지점(보기전환 3198·스코프 3254·서브탭 3274) + 큐 (재)렌더 `_metaClearReviewDetail`(2538/8777). 목록 행 클릭(편집 폼)과 검토 행 클릭(read-only 상세)이 #metadataDetail 을 두고 오염 없이 분기. 액션(승급/거부=`_feedbackQueueAction`·승인/거부=`_sampleFeedbackAction`)은 행 핸들러 미러 → 성공 시 큐 리로드가 상세 초기화. **정합 무결**.
- **XSS**: 신규 렌더(review 상세·mermaid) 전부 createElement+textContent. mermaid 는 소스만 `.mermaid-pending` div.textContent 로 넣고 공용 `mermaid-render.js`(securityLevel:strict) 가 SVG sanitize — 원문 innerHTML 경로 0. #3 prefill 은 input.value 만. **clean**.
- **#4 mermaid API 정합**: `mermaid-render.js` 가 소비하는 노드(`.mermaid-pending`, renderMermaidDiagrams:65)와 신규 삽입 노드 일치. lib/헬퍼 부재 시 라벨 코드블록 폴백. `_metaIsMermaid` 정규식은 선두 mermaid 키워드만 — 일반 SQL 오탐면 무시가능(SQL 은 SELECT/WITH 로 시작).
- **MINOR(noted, 무영향)**: ① glossary/enum 상세 액션 버튼은 stopPropagation 미부여(상세 패널은 클릭행 아님 → 무해) ② `_metaIsMermaid` 가 'graph ' 로 시작하는 극단 SQL 을 오탐 가능(실무 무발생).
- Cross-ref: TASK/MODIFY/FUNCTION/TEST-20260708-metadata-console-ux2 · 선행 REV-20260708T012922-metadata-console-polish.

## REV-20260708T230501-doc-sync-rn-0708 [SKIPPED:non-policy-doc] — 릴리즈노트 07-08 블록 3항목 prepend(제품 분류 AI 제안·그래프 접힘 카드 시각화·콘솔 검토 화면 개선) + 캐시버스터 bump (TASK-20260708T230501-doc-sync-rn-0708, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`) + cache-buster(`index/admin.html`) 뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync(ULTRACODE 6-agent write+adversarial-verify 워크플로 wf_3891a205)가 정본(feature-0016 TASK §57/§59·REPORT + feature-0003 TASK/REPORT + git log) 대비 직접 검증.
- **적대 검증(정본 대조)**: 워크플로 verify:release-notes 가 3항목 전부 정본 실재 작업으로 확증(§59 Pending-only·§57 4시각 요소·콘솔 ux2+polish), feature-id/§/테이블/함수/ADR/마이그 누출 0(노출 'ENUM'·'AI 분류 제안'·'+코드 추가'는 실제 온스크린 라벨), 07-07 블록 대비 중복 0, cache-buster 양 파일 동시 bump, node --check PASS. §58(내부/infra)·§56 T56.9(기출시)·META 도구 제외 판정 타당성 확인.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS · jsdom `verify_release_notes.mjs` 33/34 PASS(유일 FAIL=styles.css pre-existing·본 변경 무관·회귀 아님).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260708T230501-doc-sync-rn-0708 / 원천 머지 e035de8b(§59 제품 분류)·bd900515(§57 그래프)·7509fa71(콘솔 ux2)·afd3cfe6(폴리시). META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit/META mode(REV-20260708T230501-META-0022-doc-sync-0708).

## REV-20260709T113000-graph-toolbar-consolidate [SUBAGENT:frontend-correctness+layout+design-ux 3lens] (TASK-20260709-graph-toolbar-consolidate — 그래프 뷰 상단 툴바 통합 + 우측 상태 텍스트 reflow 제거, Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016) — VERDICT: SHIP-WITH-FIXES (BLOCKING 0 · MAJOR 0 · MINOR 2 FIXED + 1 FIXED · NIT 1 FIXED + 3 ACCEPT)
- Panel(§18.8): 웹/UI CSS+HTML+JS 변경(사용자 상호작용 표면) → 적대 리뷰 서브에이전트 1기(correctness/regression · reflow·layout · design/ux 3렌즈). 통과 아닌 결함 적발 목적. diff HEAD + 원본 파일 직접 대조.
- **correctness/regression = clean**: 컨트롤 id 14/14 각 1회 보존(`getElementById` 바인딩 전부 resolve), 툴바 핸들러 전부 `if(!_metaGraph.bound)` 안(중복 리스너 0)·팝오버는 `voBtn._bound` 멱등 가드, 문서-클릭 닫힘 핸들러가 종류토글·select 조작에 조기 닫힘 안 함(whitelist), 버튼 open 은 `stopPropagation`.
- **reflow·layout = clean(주장 확증)**: 상태 pill `position:absolute`(흐름 밖) → '텍스트 길이가 아래 UI 밀기' 근원 제거. 캔버스 높이 체인 건전(wide=grid minmax(0,1fr)→wrapper flex:column→canvas flex:1 / narrow=canvas height clamp(dvh)가 basis, min-height:200px §18.8 M1 floor 유지), grid auto-placement(wrapper→col1·resizer→col2·detail→col3) 보존, 미니맵(canvas 내부 right-bottom) 무영향. a11y 개선(줌·상태가 `role=img` 캔버스 **밖 형제**, aria-live 유지).
- **적발 MINOR 2 + NIT 1 → 전부 FIXED**: ① 팝오버가 자기 라벨/여백 클릭에도 닫히던 오발(admin.js 문서-클릭) → 팝오버 내부 클릭은 '제품 카테고리'(뷰 전환 커밋)만 닫도록 수정 ② `.amg-viewopts-menu{left:0}` 이 좁은 pane(≲590px)에서 우측 clip(admin-workspace overflow:hidden) → `right:0` 앵커(좌측 여유로 펼침, 실브라우저 clip 0 실측 menuRight=438<paneRight=1218) ③ LOD '줌아웃 축약' 마커가 6s auto-fade 로 사라지던 것 → 마커 표시 중 fade 타이머 취소(지속 상태 유지). NIT `aria-haspopup="true"`(메뉴 위젯 의미) → disclosure 패턴이라 제거(aria-expanded+aria-controls 유지).
- **ACCEPT-RESIDUAL(NIT 3)**: 배지 표시/숨김 시 버튼 폭 변화로 초기화·상세 수평 이동(수직 reflow 아님 — 사용자 불만 재유발 안 함) · '스키마 이동' 가용성이 배지에 미반영(의도된 통합 tradeoff — 배지는 숨긴 종류만) · <~340px 초협폭 줌·미니맵 근접(현실 admin 폭 이하). 전부 비-차단.
- 검증: `node --check admin.js` PASS · 실 Windows Chrome 149(win-browser relay) 격리 harness 렌더 실측 — toolbar 자식 4·zoom/status `position:absolute`·status `-webkit-line-clamp:2`·494px 캡·팝오버 4행·종류 3버튼 단일행(h29)·배지·`right:0` clip 0. 스크린샷 harness-closed/open2/fixed.
- POST-DEPLOY PB-0008 라이브 확인 항목(TEST.md §3): 상단 4컨트롤·팝오버 개폐(바깥클릭/Esc·라벨클릭 무닫힘)·줌 오버레이·**상태 pill reflow 0(장문 상태에도 캔버스 높이 불변)**·LOD 마커/auto-fade·pageerror 0.

## REV-20260709T120000-graph-toolbar-consolidate-postverify [SKIPPED:doc-only-postverify] (graph-toolbar 배포 ee54b1ff POST-DEPLOY PB-0008 라이브 PASS 기록, 비-정책 doc-only)
- Panel skip 사유(§18.8): 본 commit 은 TEST.md §3 POST-DEPLOY 실측 결과 append + TASK.md 체크박스 갱신뿐 — 코드·자산·정책 변경 0(doc-only). 코드 적대 검증은 원천 REV-20260709T113000-graph-toolbar-consolidate(SUBAGENT 3lens, SHIP-WITH-FIXES) 가 정본. 라이브 실측 provenance 는 TEST.md §3 POST-DEPLOY 갱신 항목.
- 실측 요지(win-browser Chrome/149, `https://localhost/` bootstrap_admin → /admin → 그래프 뷰): toolbarKids=4·zoom/status `position:absolute`·팝오버 open no-clip(menuRight 629<1249)·**reflow0=true(장문 상태 주입 전후 toolbarH 37→37·canvasTop 179→179·canvasH 572→572 불변)**·kindctl 제품개요 scope 맥락 display:none(기존 동작 보존)·pageerror 0. 사용자 리포트 2건(툴바 지저분·상태 reflow) 라이브 해소.

## REV-20260709T130000-ask-timeout-nonblocking [SUBAGENT:mainloop-adversarial-correctness+regression+ux 2round] (TASK-20260709-ask-timeout-nonblocking — 응답 지연 시 화면 전체를 덮던 타임아웃 복구 모달 제거, Minor §12.3 — feature-0003 web/UI 단독) — VERDICT: SHIP (BLOCKING 0 · MAJOR 1 FIXED · NIT 1 ACCEPT)
- Panel(§18.8): 메시지 전송 핵심 경로(sendPrompt catch)의 UI 동작 변경 → 적대 리뷰 서브에이전트 1기(정합/회귀·엣지·UX 3렌즈, 2라운드: 초기 적발 → 수정 → 재검). 통과 아닌 결함 적발 목적. diff + 원본 파일 직접 대조.
- **R1 적발 MAJOR(H1)**: 신규 대화 첫 메시지 타임아웃(earlyCid 활성) 흐름에서 인라인 "중단"(취소) 버튼이 무동작. 근본원인 = pre-existing `myAskInFlight` 키 불일치 — `busyKey`=pendingSentinel 로 add(`8640`)되나 earlyCid 활성 시(`8818~`) `askAbortControllers` 는 earlyCid 로 이관(`8864`)하면서 `myAskInFlight`/`busyConversations` 는 미이관 → `_myAskInFlightHere()`(`595-600`) false → sendBtn 핸들러가 `cancelCurrentRun` 라우팅 skip → 빈 입력 no-op. 구 타임아웃 모달의 "요청 취소"는 `/api/cancel` 직접 호출이라 이 잠복 버그를 가려왔고, 모달 제거가 노출. (즉시답변은 동작·답변 유실 없음 → non-blocking.)
- **수정(H1)**: early-cid 활성 블록에 `busyConversations.add(earlyCid)`/`myAskInFlight.add(earlyCid)`/`renderComposer()` 추가(askAbortControllers 이관과 대칭) + finally 에 `busyConversations.delete(askKey)`/`myAskInFlight.delete(askKey)` 추가(기존 abort/취소flag dual-delete 패턴 동형, leak 방지).
- **R2 재검(전 항목 REFUTED)**: `_myAskInFlightHere()` earlyCid 후 true → "중단" 라우팅 복원·즉시답변 노출(H1 해소). askKey finally 스코프 접근 가능(`const` 8873, try 8878 이전). non-early-cid 는 `askKey===busyKey` 라 dual-delete 가 no-op(무해). sentinel+earlyCid 공존은 소비자 전수(isCurrentConvBusy·R2/R3·9736/10283/10303)가 activeConversationId/isCurrentConvBusy 기반이라 오작동 없음. `renderComposer`(5204-5304)는 promptInput.value/focus 미변경(read-only hasText만)·`dataset.mode` 가드로 thrash 없음. cancelCurrentRun(early-cid)=`activeConversationId=earlyCid` 로 `/api/cancel` 정상.
- **H2~H7 (R1, 모두 REFUTED)**: 답변 유실 없음(attach terminal→refreshWorkspace, runId timeout payload 포착) · else 블록(진짜 실패=showToast+입력복원) 무결 · finally 미변경 정합 · 빈 askCid 도달 불가(+attach `!conversationId` 가드) · 잔존 실참조 0(주석만) · resume 경로(~9410) 독립 attach.
- **NIT(ACCEPT)**: early-cid 활성 시점 `renderComposer()`는 시각상 `8707` 렌더와 동일(실효 fix 는 state-set) — 방어적 재동기화로 정당, 무해.
- 검증: `node --check app.js` PASS(2회) · 코드 내 `showTimeoutRecoveryDialog` 실참조 0.
- Cross-ref: TASK/MODIFY/REPORT-20260709-ask-timeout-nonblocking · DESIGN-entry-points.md 모달 패턴 참조 갱신. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows-browser 라이브 실측(타임아웃 유발 시 화면 미가림·답변 자동 수신·기존/신규대화 양 흐름 인라인 취소/즉시답변 동작).

## REV-20260709T140000-ask-timeout-nonblocking-postverify [SKIPPED:doc-only-postverify] (ask-timeout-nonblocking 배포 4b6919ec POST-DEPLOY PB-0008 런타임 PASS 기록, 비-정책 doc-only)
- Panel skip 사유(§18.8): 본 commit 은 TEST.md §3 POST-DEPLOY 실측 결과 append + TASK.md 체크박스 flip + MODIFY 기록뿐 — 코드·자산·정책 변경 0(doc-only). 코드 적대 검증은 원천 REV-20260709T130000-ask-timeout-nonblocking(SUBAGENT 2R, SHIP) 가 정본. 라이브 실측 provenance 는 TEST.md §3 POST-DEPLOY 갱신 항목.
- 실측 요지(win-browser Chrome/149, `https://localhost/`): 무중단 배포 4b6919ec(soak PASS)·`/healthz` git_commit 일치. 서빙 app.js `typeof showTimeoutRecoveryDialog==="undefined"`(모달 런타임 완전 제거 — 사용자 신고 화면 전체 경고창 구조적 노출 불가)·attachAndWaitForResult 보존·composerFinalizeBtn/sendBtn DOM 존재·z-9999 backdrop 부재·pageerror 0. 사용자 리포트(응답 지연 시 화면 전체를 덮는 경고창) 라이브 해소.

## REV-20260711T115053-docs-archive [SKIPPED:mechanical-archiving] — MODIFY/REVIEW §5.5 아카이빙
- Related Change: CHG-20260711T115053-docs-archive. cycle: ai/claude-corp/feature-0003-docs-archive. 승인: 사용자 지시(2026-07-11) + §5.5/§5.6 규약 내 작업.
- SKIPPED 사유: 내용 판단이 없는 기계적 이관 — 검증이 그 자체로 결정적: ① head+archived+kept 재구성 md5 == 원본 md5 (양 문서, 스크립트 assert) ② 이관은 엔트리 경계(^## ) 단위 verbatim ③ 현행 파일 상단 아카이브 링크 + REPORT 압축 정보(§5.5 요건). 런타임 코드 0.
- Human Approval Needed: 아니오 — 비파괴(무손실·가역), append-only 규약 준수(기존 엔트리 의미 변경 0).

## REV-20260712T073000-item09-graph-split [SKIPPED:browser-qa-pending] — admin.js 그래프 분리
- Related: CHG-20260712T073000-item09-graph-split. 승인: 사용자 명시(blocked 해제). 자동검증 GREEN(module 문법·import/export 정합·undefined 0). 브라우저 QA(acceptance a) 사용자 게이트 대기 — 머지 전 필수.

## REV-20260712T190500-item09-batch23-stamp [SKIPPED:mechanical-move-machine-verified] — 그래프 세분화+스탬프 자동화
- Related: CHG-20260712T190500-item09-batch23-stamp. 순수 이동은 4중 기계검증(문법·verbatim·미해결참조·byte-eq)으로 대체, 신규 로직(inject_asset_stamp.py·asset_stamp_verify)은 census 실측(vendor 우연매치 12건 제외·pin 보존) 반영 + 멱등성 확인. PB-0008 실 Windows 브라우저 QA 통과(에러 0). 배포 시 asset_stamp_verify 가 주입 누락을 하드 차단.


## REV-20260713T102249-doc-sync-rn-0713 [SKIPPED:non-policy-doc] — 릴리즈노트 07-10 블록 7항목 prepend(관계도 성능·정리·상세 이동·강조 안정화·상단 툴바 / 타임아웃 모달 제거 / AI 능동 분석 '주의' 실질화 §69 / AI 분석 접속거부 조기 skip) (TASK-20260713T102249-doc-sync-rn-0713, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync 가 정본(feature-0016 REPORT/DECISIONS §57.4~76 + feature-0003 REPORT ask-timeout + feature-0002 REPORT mssql-auth-cooldown + feature-0016 §69 T69.5 POST-DEPLOY REPORT + git log) 대비 직접 검증.
- **07-10 run 대비 차이**: (a) §69 AI caveats 편입 — 07-10 run 이 T69.5 미완(라이브 미관측)으로 REJECT 했으나 07-13 PR #744 T69.5 완수(cc_data_main 재생성 715/715·0 failed·옛 자기-불평 사실상 0·사용자 원 리포트 해소)로 라이브 관측 가능 → 7번째 항목으로 편입. (b) cache-buster 수기 bump 제거 — 07-10 run 의 html `?v=` 수기 bump 은 ITEM-09 what#3(inject_asset_stamp.py content-hash 빌드주입) 도입 이전이라 재현 안 함(소스 `?v=dev` 고정). (c) landing/배포 소유=본 attended run(07-10 run 은 cron wrapper 위임).
- 적대 대조(정본): 07-09~10 사용자 화면 신규 = 그래프 §57.4~76(성능·정리·상세 내비·강조 안정화·툴바)·타임아웃 모달 제거·§69 caveats·MSSQL 접속거부 skip. 07-11~13 은 behavior-neutral(feature-0012 완결·ITEM-09 CSS/JS·META)라 사용자향 0. feature-id/§/테이블/함수/ADR/오류코드 누출 0, 07-08/07-09 블록 대비 중복 0.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS · vm 파서 구조검증(블록 순서 07-10>07-09>…·항목 스키마·누출 스캔 0).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260713T102249-doc-sync-rn-0713 / 원천 머지 d87d582e(타임아웃 모달)·§60~76 그래프·10da986e(MSSQL cooldown)·PR #664/#744(§69 T69.5). META(STATUS·wiki·RELEASE_NOTES·meta/REVIEW)는 별도 commit/META mode(REV-20260713T102249-META-doc-sync-0713).

## REV-20260713T181800-graph-perm-split [SUBAGENT:security-lens-adversarial-PASS] — 그래프 뷰 권한을 '메타데이터 관리' 묶음에서 분리 (Critical §12.3 인증/인가, 사용자 승인 B안)
- **결정 근거**: 그래프 뷰 별도 탭 분리(feature-0016 §45)에 맞춘 권한 분리 요청. 위험등급 Critical(인증/인가) → 사람 승인 필수. **AskUserQuestion 로 하위호환 방식 확정 = B안(분리 + 기존 접근 보존, 비파괴)** — A안(완전 분리, 기존 보유자 접근 상실) 대비 현재 접근 회수 없음, 프로젝트의 일관된 "기존 배포 무손실" 패턴(task4·ITEM-11 등)과 정합. graph 는 read-only 권한이라 저위험이나, 인증/인가 구조 변경이므로 §18.8 보안 렌즈 적대 리뷰 수행.
- **§18.8 보안 렌즈 적대 서브에이전트(5축: 권한상승·접근상실·멱등/race·enforcement 일관성·SQL) — 라이브 MySQL 8.0.46 실증 포함**:
  - **FINDING A (MEDIUM, 권한상승) 적발·수정**: role 이 묶음 보유 + account 가 묶음 DENY override 인 계정은 분리 전 effective graph=False(묶음 꺼짐→미함의)였는데, 대상1 role backfill 이 role 에 graph.read 를 주면서 account 가 graph.read 를 새로 획득(과잉부여). → **대상3 추가**: 해당 계정(role 이 묶음 보유 + 묶음 DENY override + graph.read override 부재)에 graph.read DENY override 부여로 분리 전 effective(그래프 없음) 고정(role-scoped JOIN 으로 spurious DENY 회피).
  - **FINDING B (LOW, 멱등 방어) 적발·수정**: `bundle_pid/graph_pid` 부재 시 backfill 본문은 skip 되나 마커가 무조건 기록되어 "done" 오기록→backfill 영구 미실행 위험(정상경로 미도달이나 방어적). → **마커 기록을 `if bundle_pid>0 and graph_pid>0:` 본문 안으로 이동**(다음 startup 재시도 보장).
  - **FINDING C (NIT) 적발·수정**: `admin_metadata.py` 그래프 analyze/analyze-schema docstring 2곳이 "(우산 kb.ingest.manual 함의)" stale → "분리 후 독립 권한" 으로 갱신.
  - **CLEAN(적대 REFUTE 통과)**: (2) 접근상실 — 대상1(role 묶음보유)+대상2(계정 묶음 ALLOW override)로 전 보유자 커버, 명시 graph DENY 존중, OLD-True→NEW-False 경로 없음. **2-path 회귀(운영 재기동 fast path 가 slow path 의 `WebSchemaMigrations` DDL 미경유→backfill 영구 skip→전원 접근상실)를 backfill 함수 자체 `CREATE TABLE IF NOT EXISTS` 로 경로 독립화(리뷰 확인).** (3) 멱등/race — 마커 guard 정확, 자체 테이블 생성, 병렬 web-a/web-b 부트스트랩 PK+INSERT IGNORE+NOT EXISTS 로 benign, 마커 INSERT 실패=안전 재시도. (4) enforcement — 백엔드 `require_permission('metadata.graph.read')` 와 프론트 표시 모두 단일 `_apply_permission_overrides`/`_decorate_account_rows` 파생, 8개 graph 엔드포인트 단일 권한 게이트, 잔여 kb.ingest.manual OR-gate 없음, fail-open 없음. (5) SQL — 대상2 self-ref `INSERT...SELECT...NOT EXISTS` 를 **라이브 repo-mysql-1(8.0.46)에서 실행: error 1093 없음·정확 결과**(bundle-allow→graph-allow, 기존 graph-deny 보존, graph-allow skip, bundle-deny skip). admin catchup 여전히 graph.read 명시 부여(admin 무손실).
  - **VERDICT: PASS/SHIP** (MEDIUM/LOW/NIT 3건 전부 수정 반영 후).
- **검증**: 권한 단위테스트(perm-split R3/R3c/R3d·dependency-map t5/m3) + feature-0003 전체 스위트 PASS(회귀 0, env 중립화). 3 findings 수정 후 재실행 GREEN. `py_compile` 3파일 OK.
- **잔여 커버리지 갭(비-차단, 후속 권장)**: backfill SQL(대상1/2/3·마커 guard)은 `--no-deps` 표준 스위트에 자동 통합테스트 부재 — 본 cycle 은 보안 리뷰의 라이브 MySQL 실증 + `_apply_permission_overrides` 단위테스트로 커버. Critical authz 마이그레이션이므로 MySQL 통합테스트(대상3 과잉부여·graph-DENY skip) 후속 추가 권장(TEST.md 기록).
- Cross-ref: CHG/TASK-20260713T181800-graph-perm-split · REPORT §1. Files: `src/web_context.py`, `src/routers/{_bootstrap_schema,admin_metadata}.py`, `src/static/{admin.js,admin.html,release-notes-data.js}`, `tests/{test_metadata_perm_split,test_permission_dependency_map}.py`.

## REV-20260713T185600-graph-perm-descfix [SKIPPED:bootstrap-robustness-no-authz-surface] — seed catchup 1406 hotfix (권한 설명 255자 초과)
- **적발 경로**: graph-perm-split 배포 후 실증(§16.3 완료 게이트가 아니라 배포 후 검증)이 `WebSchemaMigrations` 미생성·backfill 미실행을 잡아냄 → web 로그 `seed catchup skipped: 1406 Data too long`. 근본원인=내가 `kb.ingest.manual` 설명을 301자로 늘린 것이 `WebPermissions.Description` VARCHAR(255) 초과 → `_ensure_permission_catalog` 던짐 → `_ensure_seed_catchup` 전체 skip.
- **Panel skip 사유(§18.8)**: 본 hotfix 는 신규 authz 로직·enforcement·엔드포인트·스키마 형태 변경 0 — (1) description 문자열 단축(표시 텍스트), (2) `_ensure_permission_catalog` 의 방어적 문자열 클립(부트스트랩 robustness)뿐. 권한 판정(`_apply_permission_overrides`)·게이트·backfill SQL 무변경. 적대 보안 렌즈 대상 아님(표시/부트스트랩 방어). graph-perm-split 본체의 §18.8 PASS(REV-20260713T181800)가 authz 커버리지 정본.
- **자기 검증**: 전 권한 description ≤255·label ≤128 AST 전수 확인(잘림 0) · py_compile OK · feature-0003 전체 스위트 PASS(회귀 0). 근본 fix 실증은 배포 후(catchup 로그 소멸 + WebSchemaMigrations 마커).
- **교훈**: 권한 정의 description/label 은 컬럼 길이 제약이 있고, 초과 시 단일 row 가 전 seed catchup 을 차단한다. CI(`--no-deps`)가 이 DB 제약을 미검출 → 방어적 클립 + (후속) 부트스트랩 통합테스트 필요. graph-perm-split 보안 리뷰가 지적한 "backfill/부트스트랩 DB 통합테스트 부재" 갭이 실제 사고로 실현됨.
- Cross-ref: CHG/TASK-20260713T185600-graph-perm-descfix.


## REV-20260714T024534-doc-sync-rn-0714 [SKIPPED:non-policy-doc] — 릴리즈노트 07-13 블록 +7항목 append(관계도 콘텐츠 밴드 그룹핑·큰 관계도 이동 부드러움·미니맵/상세 hover·첨부 재업로드 버전·데이터소스 연결 테스트·정상 조회 과차단 수정) (TASK-20260714T024534-doc-sync-rn-0714, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync 가 정본(feature-0016 TASK §77~81·content-cluster REPORT + feature-0003 TASK attach-user-version/ds-conn-test + feature-0002 TASK readonly-query-shapes + git log #746~#770) 대비 직접 검증.
- 적대 대조(정본): 07-13 오후 사용자 화면 신규 = 콘텐츠 밴드 그룹핑(content-cluster+p2)·렌더러 교체 체감 부드러움(§78)·미니맵(§77/§79)·상세 hover(§81)·첨부 재업로드 버전(attach-user-version)·ds '연결 테스트'(ds-conn-test)·읽기전용 조회 과차단 수정(readonly-query-shapes). 제외=메시지 편집(backend-only)·describe_routine(LLM 내부 도구·사용자 화면 비노출·체감 간접 — item#7 readonly-query-shapes 는 사용자 조회가 직접 안 막히게 되는 화면 체감이라 포함, 구분 기준=사용자 화면 직접 변화 유무)·내부 최적화(§79 pool/§80 BitmapText). feature-id/§/테이블/함수/ADR/라이브러리명 누출 0(vm leak 스캔), 07-10 블록 대비 중복 회피(부드러움 항목은 컬링→렌더러 근본개선 차원 명시).
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS · vm 파서 구조검증(28 releases·블록 07-13 head·항목 스키마·07-13 8항목·누출 스캔 0).
- **cache-buster**: 소스 `?v=dev` 고정 — 07-12 ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. system-prompt 의 '수동 bump' 지시는 그 정책 이전 모델 기준이라 부적용(수동 변경 시 게이트 무력화·해시 불변). 직전 doc-sync(REV-20260713T102249-doc-sync-rn-0713)도 동일 판단.
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260714T024534-doc-sync-rn-0714 / META REV-20260714T024534-META-0035-doc-sync-0714(별도 commit) / 원천 PR #746~#770. **landing/배포 소유=cron wrapper 위임(로컬 commit 만).**
## REV-20260714T105200-graph-analyze-perm [SUBAGENT:security-lens-adversarial-PASS-after-fix] — AI 능동 분석 실행 권한을 조회에서 하위 분리 (Critical §12.3 인증/인가)
- **결정 근거**: 사용자 요청 "AI 능동 분석 실행 권한을 하위 권한으로 구분 + 무권한 시 버튼 미표시". graph-perm-split 후 graph.read 가 조회+실행을 함께 커버 — 실행(LLM·KB·비용 특권)을 별도 통제. **하위호환 = A안(최소권한, backfill 없음)** — 요청 취지가 "실행 분리 + 무권한 시 버튼 숨김"이라 graph.read 만으론 analyze 딸려오면 안 됨(함의/역함의 없음); admin 은 seed catchup 으로 획득; 현재 graph.read 보유자 admin 뿐이라 실질 영향 0.
- **§18.8 보안 렌즈 적대 서브에이전트(6축: backend 게이트 완결성·frontend 트리거 완결성·FE/BE parity·락아웃·종속/grant 정합·null-safety)**:
  - **FINDING (MEDIUM, 조회 계약 위반) 적발·수정**: 최초 구현이 AI 섹션 **전체**(읽기 전용 결과 box `metaGraphAiBox` 포함)를 `_canAnalyze` 게이트로 감싸 → graph.read-only 뷰어가 **기존 AI 분석 결과를 못 봄**. 그런데 (a) 백엔드 GET `/graph/analyze/node`·`/analyze/status` 는 graph.read 로 결과를 주고, (b) 본 변경이 쓴 graph.read 설명이 "결과·진행 상태 열람 가능"을 명시 → 자기 모순(과잉 제한). → **게이트 분리 수정**: 섹션 컨테이너·결과 box·`_metaGraphLoadNodeAnalysis`(결과 로드)는 항상 렌더(graph.read), 실행 컨트롤(`metaGraphAiBtn`·popover·`_metaGraphBindAiPopover`)만 `_canAnalyze` 게이트. + 회귀 가드 테스트 `test_graph_analyze_fe_gate_split`(결과 로드가 실행 게이트에 안 갇힘·버튼은 게이트) 추가.
  - **CLEAN(적대 REFUTE 통과)**: (1) backend 게이트 완결성 — 실행 POST 2개만 graph.analyze, 읽기 GET 5개 graph.read 유지, `enqueue_analysis`/`enqueue_schema_analysis` 는 그 2개 POST 에만 존재, `relationship/curate`(table.manage)는 LLM/enqueue 없어 무관. (2) frontend 트리거 완결성 — `_metaGraphAnalyze`/`_metaGraphAnalyzeSchema` 호출 UI 5곳 전부 게이트, 그 외 caller 없음. (3) FE/BE parity — 실행 경로 일치(FE 버튼 숨김 ⇔ BE 403). (4) 락아웃 — admin catchup 포함(`_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞이라 pid resolve), 기존 admin 무손실; 비-admin graph.read 보유자 없음. (5) 종속/grant — graph.analyze 는 `_METADATA_MANUAL_IMPLIES` 에 없음(kb.ingest.manual 이 실행 함의 안 함, fail-open 없음), 단일 permission check 는 프로젝트 컨벤션 정합. (6) null-safety — bind 는 `_canAnalyze` + `if(!btn)` 이중 가드, load 는 `if(!box||!key)` 가드, 클러스터 버튼 `if(_schemaAiBtn&&comboId)`.
  - **LOW 흡수**: 읽기 GET 4개 docstring 이 "권한 kb.ingest.manual" stale(실제 graph.read) → 4곳 "권한 metadata.graph.read(결과 조회 — 실행은 graph.analyze)" 로 정정. 테스트 갭 → FE 게이트 분리 테스트 추가.
  - **VERDICT: PASS** (MEDIUM 게이트 분리 수정 + LOW docstring/test 반영 후 재검 — 초기 "not approved" 해소).
- **검증**: 권한 단위테스트(graph.read 만으론 analyze 미부여·독립부여·admin catchup·종속 pin·FE 게이트 분리) + feature-0003 전체 스위트 PASS(회귀 0) · py_compile·node --check OK.
- **잔여**: 배포 후 PB-0008 — graph.read-only 계정: 실행 버튼/메뉴 미노출 + **결과 열람은 가능** + POST analyze 403 / graph.analyze 계정: 버튼 노출·실행 정상.
- Cross-ref: CHG/TASK/FUNCTION-20260714T105200-graph-analyze-perm · REPORT §1. Files: `src/web_context.py`, `src/routers/admin_metadata.py`, `src/static/{admin.js,graph/graph-ctxmenu.js}`, `tests/{test_metadata_perm_split,test_permission_dependency_map}.py`.
## REV-20260714T015432-step-scroll-preserve [SKIPPED:frontend-ui-minor-single-file-no-backend-no-rbac] — 실행 단계 폴링 갱신 시 펼친 "결과 보기" 스크롤 보존 (TASK-20260714T015432-step-scroll-preserve)
- Panel skip 사유(§18.8): 변경은 프론트 단일 파일(`static/app.js`)의 렌더 재작성 사이 스크롤 오프셋 보존 로직뿐 — 백엔드·엔드포인트·RBAC·스키마·마이그·인증/인가·파괴적 데이터 0(§12.3 Minor). §18.8 dispatch 표상 UI/화면 신호는 ux/design 후보이나, (a) 비파괴 UX·표준 DOM scroll semantics, (b) 이미 검증된 동형 패턴(`state.stepResultExpanded` 펼침 영속화)을 스크롤로 확장, (c) 단일 파일이라 적대 코드리뷰의 한계 이득 낮음 → 패널 skip. 대신 소스추출 격리 테스트로 계약을 실증.
- 설계 결정: 근본 재구조화(재렌더를 diff/patch 로 전환) 대신 **스냅샷/복원**을 택함 — (1) 기존 펼침-상태 영속화가 이미 같은 teardown/rebuild 전제 위에서 `_stepResultKey` 로 동작, (2) 스크롤 키를 그와 동일 키에 정합시켜 최소 표면·저위험, (3) diff 렌더 전환은 두 경로(사이드 패널+progress 카드)의 대규모 재작성이라 Minor 범위 초과. 헬퍼는 컨테이너 무관 제네릭으로 두 경로 공용.
- 적대 자가검토(refute 시도): ① "재렌더 후 scrollTop 설정이 layout 전이라 무효?" → `body.scrollHeight` 접근이 동기 reflow 유발, 재-append 후 노드가 DOM 에 있어 설정 유효(기존 `if(wasAtBottom) body.scrollTop=scrollHeight` 가 이미 동일 전제로 동작). ② "접힌 결과 복원이 엉뚱한 값?" → snapshot 이 `wrap.hidden` skip + 비-0 스크롤만 캡처, restore 는 map.has 키만 → 접힘/신규 단계 무영향(테스트 [4][5] 실증). ③ "stepKey 충돌로 A 스크롤이 B 에 복원?" → 키=step_index+created_at(dedup 과 동일), 둘 다 없을 때만 idx fallback — 기존 펼침 영속화가 쓰는 키와 동일해 추가 충돌 표면 없음. ④ "외부 스크롤 prevScrollTop 유지가 새 단계 추가 시 튐?" → 기존 항목은 동일 재렌더라 위쪽 레이아웃 불변, min(prevTop, maxTop) 로 clamp → 안정.
- 검증: `node --check app.js` PASS · `tests/verify_step_result_scroll_preserve.mjs`(jsdom@22, app.js 에서 헬퍼 소스 슬라이스 후 eval) **23/23 PASS** — 정적 배선(양 경로 snapshot 선행·restore 후행·data-step-result-key), 기능(펼친 2개만 캡처·top/left·접힘 제외·240/88 복원·새 단계 D 무영향·null/빈맵 예외 없음). feature-0003 회귀는 verify-completion 게이트.
- 잔여(비-차단): jsdom 은 layout 무계산이라 **외부 목록 스크롤**(scrollHeight 의존)의 픽셀 거동은 미검증 — 내부 결과 스크롤(scrollTop verbatim 저장) 계약만 격리 실증. 외부 목록 + 실제 다단계 폴링 타이밍의 시각 최종확인은 POST-DEPLOY PB-0008(라이브 LLM run 필요·비결정적, visual_verification_scope: always).
- Cross-ref: CHG/TASK/FUNCTION-20260714T015432-step-scroll-preserve · TEST §CHECK#13(2026-07-14) · test-runs.d/20260714T015432-step-scroll-preserve.md · ANCHOR 0003 무충돌.

## REV-20260714T133700-routemap-refresh [SKIPPED:auto-generated-artifact-no-code] — docs/ROUTEMAP.md 재생성(graph-analyze-perm 후속)
- Panel skip 사유(§18.8): 변경은 `bin/gen-routemap.py` 가 라우터 AST 로 자동 생성하는 `docs/ROUTEMAP.md` 2행(analyze POST permission graph.read→graph.analyze 반영)뿐 — 코드·런타임·RBAC enforcement·엔드포인트 shape 무변경. 권한 분리 자체의 authz 검증은 원천 REV-20260714T105200-graph-analyze-perm(§18.8 PASS)가 정본.
- 자기 검증: `gen-routemap.py --check` exit 0 · `codenav-lint.sh` OK · 재생성 diff 가 원천 변경(2 POST 권한)과 정확히 일치.
- 교훈: require_permission 값 변경은 ROUTEMAP drift 이나 verify-completion CHECK#15 는 구조적 route 변경 시에만 gen-routemap --check 를 돌려 로컬 미검출 → CI 에서만 적발. 권한 데코레이터 변경 cycle 은 `gen-routemap.py` 재실행을 명시 수행할 것.
- Cross-ref: CHG-20260714T133700-routemap-refresh · 원천 CHG-20260714T105200-graph-analyze-perm.

## REV-20260714T053522-step-scroll-raf [SKIPPED:frontend-ui-minor-single-file-additive-no-backend] — 펼친 "결과 보기" 가로 스크롤 layout-timing 0-clamp 후속 (TASK-20260714T053522-step-scroll-raf)
- Panel skip 사유(§18.8): 프론트 단일 파일(`static/app.js`), 순수 additive(동기 복원 유지 + rAF 재적용 추가), 백엔드/RBAC/스키마/엔드포인트 0. 표준 DOM scroll 타이밍 처리 → 적대 코드리뷰 한계 이득 낮음.
- **라운드1 실패 정직 기록**: step-scroll-preserve(REV-...T015432) 는 jsdom 23/23 PASS + 배포 자산 서빙 심볼 확인까지 통과했으나 **실브라우저 가로 스크롤은 여전히 초기화**됐다(사용자 재보고). 원인=jsdom 이 `scrollLeft` 를 clamp 없이 verbatim 저장 → 동기 복원의 layout-미확정 0-clamp 결함을 격리 테스트가 놓침. 교훈: scroll 오프셋의 실제 clamp 거동은 jsdom 으로 검증 불가 — layout 의존 동작은 real-browser 또는 배포-후 실측이 정본.
- 적대 자가검토(refute 시도): ① "동기 복원도 남겨두면 0-clamp 값이 최종?" → rAF 콜백이 그 뒤(layout 확정 후) 동일 캡처값을 재적용하므로 최종은 올바른 값(테스트 [7] flush 로 0→88 복구 실증). ② "rAF 가 다음 폴링 재렌더 뒤에 늦게 실행돼 stale DOM 복원?" → rAF≈16ms ≪ 폴링 간격(수 초), 항상 다음 렌더 전 소진(테스트 [7] 큐 소진 확인); 설령 늦어도 캡처값은 콘텐츠 안정 시 동일이라 무해. ③ "additive 가 세로 스크롤/하단추종 회귀?" → `_applyStepPanelScroll` 이 기존 if/else 외부 스크롤 로직을 그대로 이관(atBottom→scrollHeight / else→min(prevTop,maxTop)), 동기 경로 동작 불변. ④ "rAF 미지원 환경?" → `typeof requestAnimationFrame === "function"` 가드, 미지원 시 동기 복원만(라운드1 동작).
- 검증: `node --check app.js` PASS · `verify_step_result_scroll_preserve.mjs` 29/29 PASS. **로컬 real-browser clamp 미재현**(chromium 다운로드 환경 차단) — 근본원인은 well-known layout-timing 클래스이고 수정이 additive(회귀 표면 없음)라 배포 진행, 최종 확인은 사용자/PB-0008 실측(가로 스크롤 유지).
- Cross-ref: CHG/TASK/FUNCTION AC-SSP-4-20260714T053522 · 원천 REQ-20260714T015432 · TEST §CHECK#13(2026-07-14) · test-runs.d/20260714T053522-step-scroll-raf.md · ANCHOR 0003 무충돌.

## REV-20260714T180314-graph-entry-help [SKIPPED:frontend-ui-minor-additive-no-backend-no-rbac] — 그래프 뷰 첫 입장 도움말 팝업 + 중간버튼 커서 (TASK-20260714T1803-graph-entry-help)
- Panel skip 사유(§18.8): 프론트 3파일(admin.html/graph.css/graph-core.js) 순수 additive UI, 백엔드/RBAC/스키마/엔드포인트 0. 정보성 도움말 오버레이 + 커서 표식 → 적대 코드리뷰(권한상승·SQL·enforcement) 한계 이득 낮음.
- 적대 자가검토(refute 시도): ① "팝업이 매 진입 노출돼 성가심?" → `_metaGraphMaybeAutoHelp` 가 `localStorage("metaGraphHelpSeen")` 미확인 시에만 자동노출, 닫으면(4경로 모두 `_metaGraphHideHelp`) seen set → 이후 세션 무자동노출, 재확인은 ❓ 버튼만. ② "localStorage 실패(사생활 모드)로 예외?" → get/set 모두 try/catch, 실패 시 '미확인=노출'로 안전 강등(기능 유지·비차단). ③ "이중 바인딩으로 리스너 누적?" → `_metaGraph._helpBound` 가드 + `_metaShowGraph`(admin.js graphInitialized 가드) 1회 진입. Esc keydown 은 표시 중에만 등록·해제(show 시 기존 핸들 제거 후 재등록). ④ "중간버튼 커서가 팬 도중 깜빡이거나 다른 버튼 뗌에 조기 복원?" → mouseup 에서 `buttons & 4` 여전 눌림이면 복원 skip, 중간버튼 뗌(buttons&4=0)·window blur 시만 복원 + 리스너 self-remove. ⑤ "캔버스에 커서 안 먹힘?" → `#metadataGraphCanvas` 명시 cursor 부재 확인 → 자식 `<canvas>`(cursor 미선언)가 컨테이너 grabbing 상속(렌더러 PixiJS/G6 무관, CSS 상속 프로퍼티). ⑥ "기존 그래프 조작 회귀?" → 기존 `mousedown` 핸들러는 preventDefault 유지·additive, 신규 오버레이는 캔버스 role=img 밖 형제(접근성 보존)·hidden 기본·pointer 이벤트 캔버스 미간섭.
- 검증: `node --check --input-type=module`(graph-core.js) PASS · admin.html 도움말 블록 태그 균형(amg-help 20 매치) · graph.css 중괄호 215/215 · 새 심볼 전수 존재. **라이브 시각검증 = POST-DEPLOY PB-0008**(정적 자산 baked, visual_verification_scope: always) — 자동노출·닫기 4경로·재확인·중간버튼 커서·pageerror 0.
- Cross-ref: CHG/TASK-20260714T1803-graph-entry-help · TEST test-runs.d/20260714T180314-graph-entry-help.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260714T184717-graph-help-overlay-fix [SUBAGENT:css-comment-hazard-adversarial-PASS] — 그래프 도움말 팝업 mis-position 근본원인 수정 (TASK-20260714T184717-graph-help-overlay-fix)
- 변경: `graph.css` 주석 1곳의 토큰 구분자 `/`→`·`(`*/` 조기종료 hazard 제거) + 재발방지 NOTE. CSS 선언/선택자/미디어쿼리 무변경(주석 텍스트 국한, diff +4/-2).
- Panel 실행 사유(§18.8): render-path 인접(도움말 오버레이 레이아웃 회귀·라이브 버그 수정) → 적대적 SUBAGENT 검증 실행.
- SUBAGENT 결과(general-purpose, refute 지향): **PASS — BLOCKING 0**. 근거 — ① edited 주석·추가 NOTE 에 의도치 않은 `*/` 서브스트링 없음(byte 확인: `--text*·--primary`=`2a c2b7`, `(*·/)`·`` `*` + `/` `` 는 `·`/백틱으로 분리). ② `/*`:`*/` 정확히 61:61 균형, 모든 `*/` 가 clean end-of-comment(수정 전 62:61 불균형 → 초과 close 제거 확인). ③ `.amg-help-overlay` 규칙 문법 온전·주변 규칙 무영향. ④ git diff 주석 텍스트 국한(선언/선택자/미디어쿼리 0). ⑤ 회귀 sweep: 파일 내 다른 `*`+`/` hazard 없음(모든 asterisk 는 bold 마커 또는 안전 토큰). NIT(비차단): 설명 off-by-one, NOTE 는 prose-only(기계적 lint 없음 — CI `*/` 균형 grep 가드는 out-of-scope).
- 라이브 재검증(win-browser eval, 배포본): (a) 수정본 파싱 시 `.amg-help-overlay` 복구·`position:absolute`(rule 204→205). (b) 규칙 라이브 주입 후 카드 canvas-wrap 정중앙(dx:0 dy:0)·줌 컨트롤 미겹침(card_overlaps_zoom:false, 카드 하단 694 < 줌 상단 704). (c) `/healthz` git_commit=1f705a9e·pageerror 0. POST-DEPLOY 재배포 자산 최종 확인=deploy-web 직후.
- Cross-ref: CHG/TASK-20260714T184717-graph-help-overlay-fix · 원천 CHG-20260714T180314-graph-entry-help · TEST test-runs.d/20260714T180314-graph-entry-help.md(POST-DEPLOY FIX) · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260714T190916-graph-help-overlay-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 도움말 팝업 mis-position 수정 재배포 자산 실증 기록 (CHG-20260714T190916-graph-help-overlay-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 코드 수정 CHG-20260714T184717-graph-help-overlay-fix 은 이미 REV-20260714T184717 [SUBAGENT:...PASS] 로 적대검증 완료. 본 cycle 은 그 배포 결과를 fragment/TASK 에 기록만.
- 배포본 실증(win-browser eval, 주입 없이, 그래프 뷰 pane 활성): `/healthz` git_commit=8d1285d0 · 서빙 graph.css 스탬프 d5f26a416089(갱신)·소스 byte-identical · `.amg-help-overlay` cssRules 파싱 복구·`position:absolute`·`display:flex`·`align-items:center`·`z-index:40`(수정 전 static/block/normal/auto) · 카드 canvas-wrap 수평 정중앙(dx:0)·줌 컨트롤 미겹침(card_overlaps_zoom:false) · 스크린샷 육안(중앙 모달) · pageerror 0. → PASS.
- Cross-ref: CHG-20260714T190916-graph-help-overlay-postverify · 원천 CHG/REV-20260714T184717-graph-help-overlay-fix · TEST test-runs.d/20260714T180314-graph-entry-help.md · ANCHOR 0003 무충돌.


## REV-20260715T025509-doc-sync-rn-0715 [SKIPPED:non-policy-doc] — 릴리즈노트 07-14 블록 신규 10항목(메시지 편집 Phase 1+2·애니메이션 효과 설정·계정 탭 세분화·첨부 새버전·SQL Server cross-DB·결과보기 스크롤·그래프 첫입장 도움말·카테고리밴드 우클릭·AI분석 권한분리·답변 정확도) (TASK-20260715T025509-doc-sync-rn-0715, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync 가 정본(feature-0019 FUNCTION REQ-ME-R1~R3/AC-ME-3~6 + feature-0003 TASK anim-effect-pref/account-subtabs/graph-entry-help/graph-ctxmenu-category/step-scroll/graph-analyze-perm + feature-0002 TASK grounding/mssql-crossdb/attach-versioned + git log 07-14) 대비 직접 검증(ULTRACODE 4-도메인 병렬 draft→적대 재검증 wf_ebf9d553).
- 적대 대조(정본): 07-14 사용자 화면 신규 = 메시지 편집 Phase 1+2 라이브(git bee8a96d/1cf7784b/08443ae1/3f9c55ba)·애니메이션 효과·계정 탭·첨부 새버전·MSSQL cross-DB·결과보기 스크롤·그래프 첫입장 도움말(mis-position 수정 반영)·카테고리밴드 우클릭·AI분석 권한분리(관리자향)·답변 정확도(grounding). 제외=feature-0020 배포(내부)·feature-0016 flock/cluster-label(내부)·@@ 과차단(07-13 블록 detail 포괄·중복회피). feature-id/§/PR#/테이블/함수/권한키/라이브러리명 누출 0(vm leak 스캔).
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(29 releases·07-14 head 10항목·07-13 보존·스키마·누출0).
- **cache-buster**: 소스 `?v=dev` 고정 — 07-12 ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. system-prompt 의 '수동 bump' 지시는 그 정책 이전 모델 기준이라 부적용(수동 변경 시 게이트 무력화·해시 불변). 직전 doc-sync(REV-20260714T024534-doc-sync-rn-0714)도 동일 판단.
- **정본 lag(보고)**: feature-0019 REPORT.md prose 는 07-14 Phase 1 checkpoint 3 에서 멈춰 Phase 2(1cf7784b) 라이브 미반영 — 릴리즈노트/STATUS/wiki mirror 는 FUNCTION 스펙(REQ-ME-R3/AC-ME-6)+git+PB-0008 실측 기준으로 정확 작성. 정본 REPORT Phase 2 completion 섹션 추가는 feature-0019 후속 cycle 권고(doc_sync 정본 미편집).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260715T025509-doc-sync-rn-0715 / META REV-20260715T025509-META-0036-doc-sync-0715(별도 commit) / 원천 PR 07-14. **landing/배포 소유=cron wrapper 위임(로컬 commit 만).**
## REV-20260714T181936-perm-category-hier [SKIPPED:panel-usage-limit—inline-adversarial-selfreview+live-mysql-dryrun] — 관리 콘솔 권한 체계 카테고리 '접근' 계층 재구성 (20260714T1819-perm-category-hier, Critical §12.3)

- **대상**: 신규 카테고리 접근 권한 5종(`console.{account,product,audit,kb,system}.access`) + GroupName 재배치 + `_backfill_console_category_access_v1`(1회 멱등) + admin.js 종속 트리/탭 카테고리 AND 게이트. 사용자 승인 A안(B안=표시만 은 "카테고리 최상위 접근 권한" 요건 미충족 기각). 병렬 겹침(ITEM-09 admin.js hot_paths)도 사용자 결정 "그대로 진행".
- **§18.8 수행 형태 정직 보고**: 보안 렌즈 subagent 패널이 세션 한도(usage limit)로 조기 종료 → **inline 적대 자가검토 + 라이브 MySQL dry-run 실증으로 대체 수행** (graph-perm-split 의 라이브 실증 선례 답습). 패널 재실행이 필요하면 후속 cycle 에서 가능.
- **적대 가설 → 판정**:
  - 권한상승(역함의): REFUTE — 함의 로직은 `_apply_permission_overrides` 의 `_METADATA_MANUAL_IMPLIES` 뿐(전수 확인), 접근 권한이 세부 권한을 함의하는 경로 0. 접근 권한 단독이 여는 데이터 표면 0(엔드포인트 require_permission 무변경).
  - 동적 `product.access.<key>` prefix 충돌: REFUTE — 동적 판별은 `IsDynamic` 컬럼 기반(`_resolve_permission_catalog`), `product.access.` prefix 문자열 필터 코드 0건(전수 grep). `console.product.access` 는 정적 카탈로그 별개 code.
  - seed catchup 255자 트랩: REFUTE — 전수 72건 label≤128·desc≤255 실측(신규 5종 desc 89~112자). 방어 클립(graph-perm-descfix)도 유지.
  - 부트스트랩 순서: REFUTE — fast(`_ensure_seed_catchup` L2250)·slow(L820) 양 경로 모두 catalog→seed_roles(말미 backfill) 순서 보장, backfill 시점에 접근 pid 존재.
  - GroupName 이동 회귀: REFUTE — 백엔드에 GroupName 문자열 분기 0건(전수 grep), `_prune_orphaned_permission_catalog` 는 명시 폐기 목록만(신규 무관), admin grid 는 백엔드 group 사용·app.js 는 `PERMISSION_GROUP_OVERRIDES` 명시 매핑 추가.
  - 접근 상실(락아웃) 조합 매트릭스: (role console.access × role 세부 × 계정 override allow/deny/부재) 전 조합 사고실험 — backfill 대상 3종이 오늘 탭이 보이던 모든 조합을 커버(동치 보존), 오늘 안 보이던 조합은 그대로(과잉부여 없음: console.access 없는 operator/sales/pending 의 audit.read.own 은 부여 제외 — least-privilege).
  - grid 저장 계약: REFUTE — disclosure 는 collapse only(저장 경로 hidden row 유지, TASK-0264 계약 미변경 코드).
- **라이브 MySQL 8 dry-run 실증(read-only, `repo-mysql-1`/agent_memory, 감사 카테고리 대표)**: backfill 3종 SELECT 문법·의미 정상(1093 없음). **target1 적중 = admin + 커스텀 role `usermanager`** — usermanager 는 seed catchup 목록에 없는 커스텀 role 이라 catchup 만으론 감사 카테고리 탭을 잃었을 대상 → backfill 이 정확히 구제(설계 필요성 실증). target2 = 계정 1건(leaf ALLOW override) · target3 = 0행. 라이브 role 8종 중 console.access 미보유 role(dev_server/dos_web 등)은 오늘도 콘솔 미진입 → 동치 보존.
- **테스트**: 권한 타깃 50 PASS(M5 backfill 맵↔FE 종속 동치 신설) · feature-0003 785/0 · jsdom 탭 게이팅 47/0 · 컨테이너 make test 4 실패 전건 **환경 기인 확정**(3건=복사 .env `AGENT_RUNTIME_READ_BACKEND=postgres`·`AGENT_TIMEOUT_SEC=300` — env 중립화로 소멸·선례 동일 / 1건=`postgres-replica` DNS — main 코드+격리 네트워크 동일 재현, 격리 프로젝트 네트워크에 replica 부재 기인).
- **Human Approval**: 예 — 본 cycle 시작 시 AskUserQuestion 으로 A안 승인 완료(Critical §12.3 사람 승인 충족).

## REV-20260714T203000-perm-category-hier-postverify [SKIPPED:doc-only-postdeploy-verification-record] — perm-category-hier 배포 후 실증 기록 (PR #801 · 7e375ebc)
- 코드 변경 0(문서 전용). 실증 내용: seed catchup 정상 · `console-category-access-v1` 마커 · 접근 5종 부여(admin catchup / **usermanager = backfill 구제 실증** / dba audit) · override target2 1건 · PB-0008 라이브(grid 계층 depth·상위 토글 → 하위 접힘/펼침·admin 13탭·"변경 없음" 상태 무오염). 상세 = test-runs.d/20260714T181936-perm-category-hier.md POST-DEPLOY Run · TASK 20260714T1819 잔여 박스 close.
- [SKIPPED] 사유: 배포 후 실증의 문서화만 — 신규 코드/경계 0, 패널 불요(선례 REV-20260714T190916-graph-help-overlay-postverify).

## REV-20260715T102912-graph-help-text-responsive [SKIPPED:frontend-ui-minor-css-text-layout-no-logic-no-rbac] — 그래프 도움말 팝업 텍스트 줄바꿈 + 반응형 크기 (TASK-20260715T102912-graph-help-text-responsive)
- Panel skip 사유(§18.8): 프론트 1파일 CSS 텍스트-레이아웃 전용(`.amg-help-card` 의 word-break/overflow-wrap/width). 백엔드/RBAC/스키마/엔드포인트/JS/HTML 0. 로직·경계 무변경 → 적대 코드리뷰(권한·주입·enforcement) 이득 없음.
- 적대 자가검토(refute 시도): ① "keep-all 이 긴 무공백 토큰(URL 등)에서 오버플로?" → `overflow-wrap: anywhere` 동반으로 폭 초과 시 강제 분할, 안내 텍스트엔 그런 토큰 없음(어절마다 공백). ② "clamp width 가 좁은 화면에서 컨테이너 넘침?" → 바깥 `min(..., 100%)` 로 항상 컨테이너 바운드(실측 300px→268·오버플로 0). ③ "카드가 너무 커져 모달감 상실?" → 상한 520px(가독 상한), 1100px 캔버스에서도 520 유지. ④ "keep-all 이 중점(·) 목록('설명·컬럼') 을 한 덩어리로 묶어 넘침?" → 285px 설명폭 대비 짧아 무해, 초과 시 overflow-wrap fallback. ⑤ "다른 규칙/미디어쿼리 회귀?" → diff 는 `.amg-help-card` 선언 2 + 주석 국한, `@media(max-width:520px)` 라벨 스택 등 기존 규칙 무변경. ⑥ "주석 hazard 재발?" → 신규 주석 `/*`:`*/` 63:63 균형·`*` 뒤 `/` 없음(20260714T184717-fix 불변식 준수).
- 검증: graph.css `/*`:`*/` 63:63·중괄호 215:215 균형 · 라이브 win-browser eval(keep-all 어절 줄바꿈 스크린샷 + 반응형 다중 폭 실측 300~1100px, 오버플로 0). **라이브 시각검증 = POST-DEPLOY PB-0008**(정적 baked, visual_verification_scope: always).
- Cross-ref: CHG/TASK-20260715T102912-graph-help-text-responsive · 원천 CHG-20260714T180314-graph-entry-help·CHG-20260714T184717-graph-help-overlay-fix · TEST test-runs.d/20260715T102912-graph-help-text-responsive.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260715T103948-graph-help-responsive-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 도움말 팝업 줄바꿈+반응형 재배포 자산 실증 기록 (CHG-20260715T103948-graph-help-responsive-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 CSS 수정 CHG-20260715T102912 은 이미 REV-20260715T102912 [SKIPPED:...] 로 적대 자가검토 완료. 본 cycle 은 배포 결과를 fragment/TASK 에 기록만.
- 배포본 실증(win-browser eval, 주입 없이): `/healthz` git_commit=6af16762 · 서빙 graph.css 스탬프 92be1efb1249(갱신) · `.amg-help-card` word-break=keep-all(설명 상속)·overflow-wrap=anywhere · 반응형 폭 300→268·360→320·617→520·1100→520(오버플로 0) · 스크린샷 육안(어절 줄바꿈·넓어진 카드·중앙 모달) · pageerror 0. → PASS.
- Cross-ref: CHG-20260715T103948-graph-help-responsive-postverify · 원천 CHG/REV-20260715T102912-graph-help-text-responsive · ANCHOR 0003 무충돌.
## REV-20260715T103406-perm-atomic-split [SKIPPED:panel-usage-limit—inline-adversarial-selfreview] — 권한 최소 단위 원자화 + 레거시 묶음 숨김 (20260715T1034, Critical §12.3)

- **대상**: 원자 23종 + 엔드포인트 enforcement 전환(~38 핸들러) + transitive 함의 + backfill v2 + grid 묶음 숨김. 사용자 결정 2건(전체 분리+숨김 / 검수 단일·원본 read 하위) AskUserQuestion 승인.
- **§18.8 수행 형태**: 직전 cycle 과 동일 사유(패널 subagent 세션 한도)로 inline 적대 자가검토. 적대 가설 → 판정:
  - **원자 DENY 무력화(choke-point fallback)**: 설계 단계에서 기각 — `_account_has_permission` 에 묶음 fallback 을 두면 effective map 의 원자 DENY 를 우회(권한상승). 대신 effective map 함의만 사용(DENY 우선, 테스트 R9 pin).
  - **역할 저장 wipe(숨긴 묶음 grant 소실)**: REFUTE — 역할 저장 경로 preservedHidden(TASK-0300)이 grid 미렌더 코드를 union 보존(admin.js 실코드 확인). override 편집기는 row 단위 upsert 라 무관.
  - **suggest(LLM 비용)가 read 로 격하**: 설계에서 차단 — 가시성 맵(read)과 분리된 `_METADATA_SUGGEST_PERM`(update) 신설.
  - **fresh install 순서 결함**: backfill v2 를 category-access-v1 **선행** 호출로 해결(묶음-only role 이 원자 전개 후 카테고리 접근 leaves 판정에 걸림 — 코드 주석 계약).
  - **테스트 fake 계정 우회로 인한 위장 통과**: 원자 키를 perm dict 에 명시 보강(10파일) — enforcement 는 plain lookup 유지.
  - **잔여 묶음 enforcement**: 전수 grep 0(미사용 legacy 헬퍼 `_metadata_resolve_account` 만 잔존 — 호출처 0 확인).
  - **연결 테스트 게이트**: 기존 '버튼 무게이트+서버 manage 403' 괴리 → datasource.test 로 FE/BE 정합(개선).
- **검증**: 785/0(호스트) · jsdom 47/0 · R9(transitive·DENY 우선)/R10(legacy 3자 parity) 신설 · ROUTEMAP 재생성 --check 0. 컨테이너 make test·배포 후 실증은 TASK 잔여.
- **Human Approval**: 예 — cycle 시작 AskUserQuestion 2건 승인(Critical §12.3 충족).
## REV-20260715T113000-perm-atomic-postverify [SKIPPED:doc-only-postdeploy-verification-record] — perm-atomic-split 배포 후 실증 기록 (PR #810 · 8098aee1)
- 코드 변경 0(문서 전용). 실증: seed catchup 정상 · `atomic-perm-split-v1` 마커 · admin 원자 23종 · 묶음 보유 role=admin 뿐(usermanager 비대상 정상·접근 상실 0) · PB-0008 라이브(레거시 묶음 grid 0건·원자 트리 d1/d2·검수=원본 read 하위·토글 접힘/펼침·상태 무오염). 상세 = test-runs.d/20260715T103406-perm-atomic-split.md POST-DEPLOY Run.
- [SKIPPED] 사유: 배포 후 실증 문서화만 — 신규 코드/경계 0(선례 REV-20260714T203000-perm-category-hier-postverify).
## REV-20260715T110000-attach-new-label-symmetry [SUBAGENT:adversarial-scope/IDOR/correctness] — staged-flush 첨부 new_attachment_ids 라벨 대칭
- 대상: `app.js` lazy-create staged-flush 의 `new_attachment_ids` union(±3줄) + 서버측 소비(agent_core `_build_attachment_context_section`). 적대 서브에이전트 1렌즈(scope/IDOR/correctness, 5축), 양 dispatch 경로(in-process router + ask-worker) 추적.
- **CONFIRMED-DEFECT 0 / 5축 전건 REFUTED**:
  - **① Scope/IDOR — REFUTED**: `new_attachment_ids`(→`_NEW_ATTACHMENT_IDS_CTX`→`_load_new_attachment_ids`→`new_ids_set`)는 **라벨(★/◆)+version-diff 게이트 전용**. 주입 대상 선택 SQL 은 `attachment_ids`(`Id IN (...)`)+ConversationId(IDOR 안전망)만 필터 — new_ids_set 은 이미 fetch 된 행을 라벨만 함. attachment_ids 에 없는 id 는 rows 부재 → 라벨 미방출. 접근 확장 불가.
  - **② uploadedIds 신뢰 — REFUTED**: `_flushStagedAttachmentsToCid` 가 성공 업로드 응답 `Number(resp.id)>0` 만 push. resp 는 `POST /api/conversations/{earlyCid}/attachments`(방금 이 계정용 발급된 earlyCid) 결과 → 이-대화·이-계정 서버-확인 id. stale/foreign 누출 불가.
  - **③ version-diff 오트리거 — REFUTED**: `## FILE UPDATES` 게이트는 `new_ids_set 포함 AND MetaJson.version_diff(unified_diff 비어있지 않음)` 동시 요구. 신규 earlyCid 는 동명 prior 부재 → v1/root=NULL, version_diff 부재 → 라벨이 ★신규여도 게이트 닫힘.
  - **④ dedup/type/ordering — REFUTED**: `new Set([...prev,...uploadedIds].map(Number).filter(n>0))` — 빈-버그케이스=deduped uploadedIds(정확), 기존값 있으면 union. NaN/음수 배제, Set dedup, 삽입순 보존. 인접 attachment_ids union 과 정확 대칭.
  - **⑤ 비-lazy 경로 무영향 — REFUTED**: 추가 블록은 `if(isLazyCreate)`+`if(earlyCid)`+`if(stagedCount>0)` 내부만 — 기존 대화·무-staged send 무변경.
- OVERALL: BLOCKING 0 / MAJOR 0 / MINOR 0. No fix required.
- 검증: `node --check` PASS. 라이브 PB-0008(신규 대화 staged 첨부 ★신규 인지)은 정적자산 baked → 배포 후 실측(TEST.md §3 DEFERRED).
- Human Approval: PLAN-APPROVED(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Minor(라벨-only) → PR/deploy(deploy_scope: included).
- Cross-ref: CHG-20260715T110000-attach-new-label-symmetry(MODIFY) · CHG-20260715T060000-attach-inline-honesty(②-backend, feature-0002) · ANCHOR §1~§3 무충돌.

## REV-20260715T105337-enum-review-bundle [SUBAGENT:backend-security-adversarial — VERDICT SHIP after fixes (1 MAJOR + 2 MINOR 전건 수정)] — ENUM 코드사전 검토 큐 구조 묶음 승인 체크리스트 + 일괄 등록 (20260715T1053-enum-review-bundle, Major §12.3)
- 대상: 신규 `POST /api/admin/metadata/enum-feedback/bulk-promote`(admin_metadata.py) + `bulk_promote_enum_feedback`(kb_glossary.py). 프론트(admin.js 묶음 렌더 + CSS)는 로직·경계 무변경(RBAC/스키마/엔드포인트 shape 0) → 백엔드/보안 축만 적대 패널(§18.8 "API/endpoint → backend, security, qa").
- **적대 패널(general-purpose subagent, 결함 적발 목적)** 결과: BLOCKERS 0, MAJOR 1, MINOR 2. **전건 수정 후 SHIP.**
  - **[MAJOR — 수정됨] 이벤트 루프 블로킹**: 핸들러가 `async def`(body await 필수)인데 최대 200×3 블로킹 psycopg 쿼리(+`FOR UPDATE`, `_pg_connect` 는 lock/statement timeout 미설정)를 이벤트 루프에서 직접 실행 → 경합 lock 시 워커 전체 정지(단건 형제는 `def` 라 threadpool 격리). **수정**: 블로킹 배치를 `run_in_executor(None, _run_bulk, pg)` 로 threadpool 오프로드(connect 는 connect_timeout 로 bounded, 루프에 유지해 503 parity) + 배치 트랜잭션에 `SET LOCAL lock_timeout='5s'`(무한 FOR UPDATE 대기 fail-fast → 롤백 → 재시도 가능 500).
  - **[MINOR — 수정됨] deadlock**: `FOR UPDATE` 를 클라이언트 순서로 획득 → 겹치는 id 를 역순으로 동시 bulk-promote 시 deadlock → 500. **수정**: `ids.sort()` 로 결정적 lock 순서(테스트 `test_enum_feedback_bulk_promote_sorts_ids`).
  - **[MINOR — 수정됨] 선-DoS**: cap 을 dedup 후 개수에 적용 → 초대형 배열 full-parse + O(n) 루프가 400 전에 실행. **수정**: 원본 배열 길이(`len(raw_ids)`)부터 cap(테스트 `_cap_400`) + bool/비정수 float 명시 거부.
- **PASS(결함 없음, 패널 확인)**: 트랜잭션 원자성(단일 commit, 예외 시 rollback+close, 부분 실패 전건 롤백)·연결 수명·RBAC(`kb.enum.curate` 단건과 byte-identical, 우회 없음)·SQL injection(파라미터화 재사용, 신규 interpolation 0)·입력검증(missing/non-dict/non-list/non-int/≤0/dedup)·audit(`_metadata_audit` resource_id=None 허용·change_json 직렬화)·부분 skip 시맨틱(없음/이미처리 → enum_id=None skip, 예외 아님).
- 비파괴 재확인: 미선택(해제) 후보는 pending 유지(거부 아님). 개별 promote/reject·glossary/sample 큐·엔드포인트 shape 불변.
- 검증: agent 컨테이너 pytest — core `test_kb_enum_feedback`(bulk_multi·skips_missing) + web `test_metadata_enum_feedback`(bulk_promote·reports_skips·empty_400·bad_type_400·cap_400·sorts_ids·requires_curate) + route_parity(golden 재생성) **31 passed** · `py_compile` OK · `node --check` admin.js PASS · `gen-routemap --check` up-to-date. **라이브 시각검증 = POST-DEPLOY PB-0008**(정적 baked, visual_verification_scope: always).
- Cross-ref: CHG/TASK/REQ-20260715T105337-enum-review-bundle · FUNCTION AC-ERB-1~3 · 원천 enum_feedback(alembic 0039)·admin_metadata enum-feedback 큐 · TEST test-runs.d/20260715T105337-enum-review-bundle.md · ANCHOR 0003 무충돌.


## REV-20260715T113208-enum-bundle-flex-fix [SKIPPED:frontend-css-layout-single-declaration-no-logic-no-rbac] — ENUM 검토 큐 묶음 카드 flex 압축 붕괴 수정 (20260715T1132-enum-bundle-flex-fix, Minor §12.3)
- Panel skip 사유(§18.8): CSS 1선언(`flex-shrink:0`) + 주석. JS/HTML/백엔드/RBAC/엔드포인트 0. 로직·경계 무변경 → 적대 코드리뷰(권한·주입·enforcement) 이득 없음.
- 근본원인 라이브 확정: `#metadataList`(overflow-y:auto·flex-column·height 373px)에서 `.admin-meta-bundle` 기본 flex-shrink:1 → 8카드 압축 + card overflow:hidden 이 내용(164px) 클리핑 → 12px sliver. flex-shrink:0 주입 시 166px 복원(라이브 실측). flat-list `.admin-meta-row`(overflow visible)는 미발현이던 잠복.
- 적대 자가검토(refute): ① "flex-shrink:0 이 목록 스크롤을 깨나?" → `#metadataList overflow-y:auto` 가 컨테이너 스크롤 제공, 카드는 자연 높이(표준 패턴). ② "다건일 때 넘침?" → 컨테이너 스크롤이 흡수(카드 압축 대신). ③ "다른 flex 자식 회귀?" → `.admin-meta-bundle` 한정 선택자, 타 규칙 무변경.
- 검증: POST-DEPLOY PB-0008 라이브(재배포 자산 카드 정상 높이·묶음·체크리스트·등록·pageerror 0).
- Cross-ref: CHG/TASK-20260715T113208-enum-bundle-flex-fix · 원천 REV-20260715T105337-enum-review-bundle · ANCHOR 0003 무충돌.

## REV-20260715T120000-enum-review-bundle-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — ENUM 검토 큐 묶음 승인 체크리스트 + flex-fix POST-DEPLOY 실증 기록 (CHG-20260715T120000-enum-review-bundle-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T105337(백엔드/보안 [SUBAGENT] 적대 패널 완료) + CHG-20260715T113208(CSS [SKIPPED] 적대 자가검토 완료)은 각 REV 로 검증됨. 본 cycle 은 배포 결과를 원장에 기록만.
- 배포본 실증(win-browser eval, bootstrap_admin /api/auth/login 200, 주입 없이): (묶음/체크리스트) 12후보→8묶음·전체 승인 마스터·일부 해제 indeterminate/힌트·등록 count/disabled 라이브 PASS. (flex-fix 재배포 a3c69103) 카드 높이 [166,166,166,205,166,166,298,166]·flex-shrink=0·목록 스크롤(scrollH 1770>clientH 373)·sliver 해소·pageError 0. 스크린샷 육안 정상.
- Cross-ref: CHG-20260715T120000-enum-review-bundle-postverify · 원천 REV-20260715T105337-enum-review-bundle · REV-20260715T113208-enum-bundle-flex-fix · ANCHOR 0003 무충돌.

## REV-20260715T181939-graph-edge-follow-drag [SUBAGENT:pixi-render-lifecycle-adversarial + 적대 자가검토] — 그래프 노드/제품 카테고리 드래그 시 관계선 미추종 수정 (20260715T1819-graph-edge-follow-drag, Minor §12.3)
- 근본원인: PixiJS 엣지는 절대좌표를 Graphics 에 bake 한 world 직속 독립 오브젝트(`_drawEdge`) → 노드 이동으로 미추종. 드래그 경로(`_moveElement`/`translateElementTo`)가 `_render()`(repaint)만 호출, 엣지 재계산은 full `draw()`(줌 rebuild)에서만 발생 → "줌 아웃해야 갱신". 신규 `_refreshIncidentEdges` 로 이동 노드의 incident 엣지만 증분 재그림.
- 적대 자가검토(refute):
  ① "old destroy 후 world 자식 leak/double-destroy?" → 각 엣지 loop 1회 처리(내부 엣지도 edges 배열에서 1회). old 는 `_objs.get(eid)` 로 획득 후 destroy+removeChild, 신규는 addChild+`_objs.set` — draw() 의 recreate lifecycle(550~551)과 동형. leak 없음.
  ② "_objSig 갱신이 이후 full draw() 재사용을 오판?" → draw() 는 committed 위치로 `edgeSig` 재계산: 드래그와 동일 위치면 재사용(시각 동일·정상), 다르면 서명 불일치→recreate(정상). stale 시각 없음. edgeSig/edgeId/pos 계산이 draw() 와 동일 함수라 불일치 0.
  ③ "cross-category 미갱신?" → 판정 `moved.has(source) || moved.has(target)` — 한끝만 이동해도 재그림. 이동 끝점=새 `getElementPosition`, 미이동 끝점=현재 좌표 → 구조 갱신(T23 실증: e2 B이동[500,400]·C미이동[200,200]).
  ④ "카테고리 드래그가 이 chokepoint 를 안 거치면?" → graph-core `_metaNodeDragStart`(CAT/CATH 1768)가 `_metaComboMemberIds` 로 전 구성원 적재→`_metaNodeDrag`(1848) `translateElementTo(to)` → 본 메서드 경유. 커버 확인.
  ⑤ "빈/null/비-node movedIds?" → `new Set(movedIds||[])` + `if(!moved.size) return` 방어. 비-node id 는 어느 엣지 끝점과도 매칭 안 돼 no-op. T23 no-op 케이스 PASS.
  ⑥ 성능(허브 수천 엣지 per-frame): 실 비용 존재하나 full draw() 보다 저렴(콤보/전노드/미니맵 재구성 없음)하고 정확성 필수 최소치 — 수용 가능 트레이드오프로 판정, rAF 스로틀은 deferred(§76).
- [SUBAGENT:pixi-render-lifecycle-adversarial] VERDICT — **correctness 결함 없음**(6축 refute, 73/73 통과). 핵심 불변식 확인: (a) 모든 엣지 끝점은 node id(`graph-core` renderEndpoint 는 node id 또는 `SC:` node 만 반환, combo 는 엣지 끝점 아님), (b) `_refreshIncidentEdges(moved)` 는 방금 `.style` 위치를 바꾼 노드 집합과 **정확히 동일 인자**로 호출 → 위치 바뀐 엣지는 ≥1 끝점이 moved 에 있어 OR 판정으로 100% 포착, stale 잔존 경로 0. 축1(풀 lifecycle/zIndex)·축2(_objSig 재사용: getElementPosition/pos 가 node 끝점에 byte-동일 → 후속 full draw 정확 reuse)·축3(edgeId/edgeSig/좌표 동일 함수)·축4(cross-category OR, T23 실증)·축6(방어) 전부 REFUTED(결함 아님). expanded 스키마 콤보 SCHEMA_REF stale 의심도 refute(양끝 folded=SC: node 일 때만 렌더).
- [SUBAGENT] 잔여 non-blocking: **F1(CONFIRMED, 성능 트레이드오프)** 허브/대형 스키마 드래그 시 프레임당 O(E)×2 스캔 + incident 엣지 destroy/recreate(graph-core `_metaNodeDrag` 종속이동과 이중 호출 — 단 서로 다른 엣지집합). 사용자 드래그로 bound·정확성 무영향 → 수용, deferred 최적화 = 엣지 Graphics 재사용(`.clear()`+재-path, destroy/recreate 회피) 또는 rAF 스로틀. F2(null 끝점 stale, 드래그 중 노드 소멸 거의 도달불가·benign)·F3(비-배열 문자열 movedIds 문자분해, 현 호출자 전부 배열/Set·미도달)·F4(_drawEdge throw 시 다음 draw self-heal, draw() make 경로와 동일 리스크) — 전부 도달난이도 높음/benign, 수정 불요.
- 검증: `node --check` PASS · 헤드리스 T23 7종 ALL PASS 73/0 · [SUBAGENT] 적대 리뷰 결함 없음 · POST-DEPLOY PB-0008 라이브(제품 카테고리 드래그 중 cross-category 관계선 실시간 추종, 잔여).
- Cross-ref: TASK 20260715T1819 · CHG/TEST-20260715T181939-graph-edge-follow-drag · 그래프 도메인 정본 feature-0016 · 선행 graph 렌더러 seam §78(PixiJS) · ANCHOR 0003 무충돌.

## REV-20260715T190000-graph-edge-follow-drag-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 그래프 관계선 추종 수정 POST-DEPLOY 라이브 실증 기록 (CHG-20260715T190000-graph-edge-follow-drag-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T181939 은 REV-20260715T181939([SUBAGENT] 적대 리뷰 correctness 결함 없음)로 검증됨. 본 cycle 은 배포 결과를 원장에 기록만.
- 배포본 실증(win-browser eval, 로그인 세션, 주입 없이): PixiJS 루트 뷰에서 제품 카테고리 드래그 → cross-category 관계선이 pointerup 전·줌 없이 새 위치 실시간 추종(옛 위치 잔상 0)·dragend 정합·pageerror 0. 서빙 자산 baked(`_refreshIncidentEdges` grep=4). 스크린샷 육안 정상(graph_middrag 에서 이동 카테고리→데이터소스 관계선이 새 좌표에서 발원).
- Cross-ref: CHG-20260715T190000-graph-edge-follow-drag-postverify · 원천 REV-20260715T181939-graph-edge-follow-drag · ANCHOR 0003 무충돌.

## REV-20260715T211911-graph-cluster-detail-routines [SUBAGENT:graph-cluster-detail-routine-parity-adversarial + 적대 자가검토] — 스키마 클러스터 상세 패널: 함수·프로시저만 있는 컨텐츠 카테고리 누락 수정 (20260715T2119-graph-cluster-detail-routines, Minor §12.3)
- 근본원인: 캔버스 build(`graph-core.js` L64~L78)는 Table+Routine 을 `g.tables` 에 함께 넣어 `_metaSimGroups` 로 컨텐츠 카테고리화하나, 스키마 클러스터 상세 패널 진입점 2곳·렌더가 `label === "Table"` 만 집계 → Routine-only 컨텐츠 카테고리 누락 + 캔버스 불일치. 수정: 두 진입점이 `label === "Routine"` 도 동일 membership predicate 로 수집, 렌더가 `members=tables.concat(routines)` 로 sim-group 계산·렌더.
- **[SUBAGENT] VERDICT — MAJOR 1건 적발 → 수정 반영**:
  - **MAJOR (hiddenKinds parity 위반, 수정 완료)**: 초판이 routine 을 모델에서 **무조건** 수집 — 그러나 캔버스 build(L74-75)는 `_metaGraph.hiddenKinds`(툴바 'ƒ 함수'/'⚙ 프로시저' 토글, localStorage 영속)로 kind 필터를 적용해 숨긴 kind 를 `g.tables`·sim-group 입력에서 제외한다. 초판은 숨긴 routine 을 패널에 계속 표시·집계·sim-group 투입 → 본 변경이 스스로 주장한 "캔버스와 컨텐츠 카테고리 일치" 불변식을 지원되는(비-기본) 모드에서 위반(개수·그룹핑 math 교란, 숨긴 routine 행 클릭 시 렌더 노드 부재로 focus no-op). **수정**: 두 수집 루프에 build 와 동형 guard `!_metaGraph.hiddenKinds.has((n.routine_type==="function")?"function":"procedure")` 추가(graph-ctxmenu.js:977·2245). 재검증 `node --check` PASS.
  - **NIT (수정 완료)**: 설명 문구 "컬럼·파라미터·관계·용어" 가 routine 없는 Table-only 클러스터에도 "파라미터"(routine 전용 개념) 노출 → `_clickHint` 를 `nRoutines` 조건부로("컬럼·파라미터·관계·용어" / "컬럼·관계·용어").
- **[SUBAGENT] 6축 판정(수정 후 유효)**: ① 회귀(Table-only) — `nTables`/`truncNote`/`totalOverride`/`childCols` 전부 `tblList`(테이블) 기준, `members`=tables 복사, `if(members.length)`≡기존 `if(tables&&tables.length)` → **회귀 0**(문구만 확장). ② 정합성 — canvas `g.tables`=Table+Routine 이 `_metaSimGroups` 입력, 패널 `members`=동일; `panel:`+name schemaId 로 stable-order 분리; `_metaRelAdjacency`+routine key 무해(REFERENCES 끝점이 routine 으로 resolve 안 됨). hiddenKinds guard 추가로 **완전 정합**. ③ 누락/중복 — tables(label Table)·routines(label Routine) label-disjoint 무중복; `_metaCatParent===comboId` 로 타 스키마 routine 미유입; flat-scope routine(`_metaCatParent`→null)은 실 comboId 와 불일치라 제외(캔버스 terms 라우팅과 정합); ById terms combo early-return. ④ null/빈값 — `routines||[]`(호출자 2곳 모두 전달 확인), 빈 members 무섹션, 미상 routine_type→⚙/프로시저. ⑤ 80행 cap — members 기준 iterate, 그룹 절단표식 유지, flat fallback `tblList.concat(rtnList)` 라 테이블 우선(routine 이 테이블 밀어내지 않음). ⑥ XSS — routine name/fqn/description/key·group label·tooltip 전부 `esc()`.
- 적대 자가검토(refute): "guard 추가가 status 라인 개수(ById)와 목록 개수를 어긋나게 하나?" → status 의 `routines.length` 도 guard 후 배열 기준이라 목록·설명·status 3자 동일 집합. "hiddenKinds 미초기화 환경?" → `_metaGraph.hiddenKinds` 는 graph-state 초기화 Set(빈 Set 이면 `.has` 항상 false=전량 표시, 캔버스와 동일).
- 검증: `node --check`(module) PASS · [SUBAGENT] 적대 리뷰 MAJOR 1 수정·잔여 correctness 결함 없음 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T2119 · CHG/TEST-20260715T211911-graph-cluster-detail-routines · test-runs.d/20260715T2119-graph-cluster-detail-routines.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260715T215241-graph-cluster-detail-cap [SKIPPED:frontend-display-cap-constants-and-heading-emission-no-logic-no-boundary-no-rbac] — 스키마 클러스터 상세: 목록 행 캡이 함수·프로시저 컨텐츠 카테고리를 통째 숨기던 문제 수정 (20260715T2152-graph-cluster-detail-cap, Minor §12.3)
- Panel skip 사유(§18.8): 렌더 캡 상수(80→PER_GROUP 25 + ROW_CAP 500) + "그룹 헤딩 항상 방출" 표시 로직 변경. 데이터/집계/membership/권한/엔드포인트/주입 경계 무변경 → 적대 코드리뷰(권한·주입·enforcement) 이득 없음. 대신 적대 자가검토로 대체.
- 근본원인(라이브 확정): `_metaGraphRenderClusterDetail` sim-group 렌더가 `if (emitted >= 80) return` 로 캡 도달 후 그룹 통째 skip. sim-group 순서 be:(테이블) 우선 → gunzgame(409) 앞쪽 테이블 be: 클러스터 10개가 80행 소진 → 함수·프로시저 컨텐츠 카테고리 전체(헤딩 포함) 렌더 누락(POST-DEPLOY PB-0008 라이브 실측: 렌더 그룹 10개 전부 tbl, rtn=0; aside scrollH 2620·마지막 "전체 순위 (2/3)" 절단).
- 적대 자가검토(refute):
  ① "전역 캡 500 도달 후 그룹은?" → `shown = min(sg.n, 25, max(0, 500-emitted))` = 0 → 헤딩은 방출(카테고리 가시), 멤버 0행 + `(0/n)` 표식. 데이터 손실 아님(개수 정직).
  ② "PER_GROUP=25 가 기존 표시를 줄이나?" → 그룹 멤버 >25 인 그룹만(예 gunzgame 32→25) `(25/32)` 표식으로 정직 절단. ≤25 그룹은 전부 표시(대다수 routine 그룹 = affix family 소형이라 전량 노출). 소형 스키마 회귀 0.
  ③ "개수 모순?" → 헤딩 `sg.n`(전체 개수) 불변, 표식 `(shown/n)` 이 표시분 명시 → 섹션 제목(members.length)·설명(함수·프로시저 N개)·헤딩 개수 3자 정합 유지.
  ④ "패널 폭주(수천 행)?" → ROW_CAP=500 전역 상한 + PER_GROUP=25 이중 바운드. 패널 aside=overflow-y:auto 스크롤(라이브 확인). 500 행 DOM/리스너는 현대 브라우저 수용 범위(기존 80 대비 증가하나 gunzgame 409 실렌더 기준 안전).
  ⑤ "flat 폴백(sgs<2) 정합?" → `slice(0,80)`→`slice(0,500)` 동일 상향, 소형은 무영향.
- [SKIPPED] VERDICT — display-cap 규약 개정, correctness/경계 결함 없음. 캡 도달 후에도 **모든 컨텐츠 카테고리가 헤딩으로 반드시 나타나** 사용자 목표(routine 컨텐츠 카테고리 조회 가능) 달성.
- 검증: `node --check`(module) PASS · POST-DEPLOY PB-0008 라이브(gunzgame 상세에서 함수·프로시저 컨텐츠 카테고리 헤딩+ƒ/⚙ 멤버 행 실렌더·클릭 조회 확인, 잔여).
- Cross-ref: TASK 20260715T2152 · CHG/TEST-20260715T215241-graph-cluster-detail-cap · test-runs.d/20260715T2152-graph-cluster-detail-cap.md · 선행 REV-20260715T211911-graph-cluster-detail-routines · ANCHOR 0003 무충돌.

## REV-20260715T220941-graph-cluster-detail-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 그래프 클러스터 상세 함수·프로시저 컨텐츠 카테고리 수정 POST-DEPLOY 실증 기록 (CHG-20260715T220941-graph-cluster-detail-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T211911(routine 집계, [SUBAGENT] hiddenKinds parity MAJOR 수정) + CHG-20260715T215241(cap 개정, [SKIPPED] display-cap 적대 자가검토)은 각 REV 로 검증됨. 본 cycle 은 배포 결과를 원장에 기록만.
- 배포본 실증(win-browser eval, 로그인 세션, 배포 cdee785e, 주입 없이): gunzgame 클러스터 상세에서 함수·프로시저-only 컨텐츠 카테고리 51개 노출(수정 전 0)·⚙/ƒ 칩 멤버 행·⚙ Game_AllItemGet 클릭→routine 노드 상세·캔버스 sim-group 정합·pageerror 0. 스크린샷 육안 정상(gz_routine_groups.png: "계정 조회" 그룹 ⚙ Game_Account*·ƒ Func_IsAccountBoundCustomizeItem 멤버).
- Cross-ref: CHG-20260715T220941-graph-cluster-detail-postverify · 원천 REV-20260715T211911-graph-cluster-detail-routines · REV-20260715T215241-graph-cluster-detail-cap · ANCHOR 0003 무충돌.

## REV-20260715T223744-graph-cluster-detail-fulllist [SUBAGENT:cluster-detail-event-delegation-adversarial + 적대 자가검토] — 스키마 클러스터 상세 컨텐츠 카테고리 목록 전체 출력 + 행 상호작용 이벤트 위임 (20260715T2237-graph-cluster-detail-fulllist, Minor §12.3)
- 근본원인: 직전 cluster-detail-cap 의 전역 상한 500 + 그룹당 25 가 멤버 총합 500 초과 스키마에서 뒤쪽 컨텐츠 카테고리를 `(0/n)`·경계 `(3/5)`로 절단(사용자 스크린샷). 수정: 그룹당 캡 제거 + 전역 상한 500→5000(안전가드)로 전체 멤버 렌더, 행 클릭/hover 를 per-row → 컨테이너 `ul` 이벤트 위임 전환.
- **[SUBAGENT] VERDICT — correctness/회귀 결함 없음(6축 PASS)**:
  - ① 리스너 누적 없음 — 위임을 영속 `el`(#metadataGraphDetailBody) 아닌 **매 렌더 innerHTML 재생성되는 `ul.amgr-cluster-tables`** 에 부착. 직전 ul↔리스너는 외부 참조 없는 자기완결 사이클(블록-local `const _ctUl`)이라 mark-sweep GC 수거. collapse/analyze 버튼은 card head 의 형제(ul 밖)라 위임과 미교차.
  - ② hover 의미 동등 — mouseout `!b.contains(relatedTarget)`(칩↔code 자식 이동 취소 억제, relatedTarget 은 항상 element), 인접행 이동 mouseout(A)→cancel + mouseover(B)→pan 이 원본 mouseleave→enter 순서와 동등(`_metaGraphHoverPan` 이 내부에서 Cancel 선행 — idempotent), `_hoverKey` 로 같은 행 재-pan 억제, window 이탈 relatedTarget=null→cancel. focusout 은 button 만 focusable 이라 안전.
  - ③ 클릭 동등 — `closest(".amgr-ct-row[data-node-key]")` 가 칩/code/desc 클릭 행 승격, 그룹 헤딩(키 없음)→null→no-op. `_metaGraphShowDetail` 은 async(apiFetch await 후 innerHTML 교체)라 클릭 전파 완료 후 ul 교체 — use-after-detach 없음.
  - ④ 전체 출력 — `_metaSimGroups` 반환 `n===tables.length`(동일 배열)라 <5000 스키마는 `shown=len` 전량·trunc 빈값; >5000 은 헤딩 무조건 방출(slice 전) + `(shown/n)` 정직. flat 폴백 `slice(0,ROW_CAP)`.
  - ⑤ 회귀 — 소형 스키마 그룹핑/개수/헤딩 무변경(캡 산술만 변경), `rowHTML`·`esc` byte-동일(XSS·data-node-key round-trip 불변).
  - ⑥ 성능 — 위임 리스너 O(1)(총 5 addEventListener). `_metaSimGroups`/`_metaRelOrderAll` 은 기존에도 전체 멤버 처리(캡은 render-slice 에만 적용)라 신규 알고리즘 비용 0. caveat(결함 아님): ROW_CAP 근처 ~5000 li/button(~20-25k DOM) 1회 innerHTML 동기 렌더는 수백 ms 가능 — "전체 출력" 요청의 수용 트레이드오프, ROW_CAP=5000 가드.
- **NIT 반영**: ROW_CAP 상수를 구획/평면 폴백 공통 스코프로 hoist(리뷰 NIT — 폴백 `5000` 리터럴 하드코딩 drift 위험 제거, 이제 `slice(0, ROW_CAP)`). 잔여 NIT(`_ctUl.contains(b)` 방어적 중복)은 무해로 유지.
- 적대 자가검토: "위임 click 이 재렌더 후에도 stale 참조?" → 클릭은 구 ul 에서 발화·처리 완료 후 재렌더, 신 ul 은 새 위임 획득 — 무해. "5000 초과 실스키마?" → 단일 스키마 테이블+루틴 5000 초과는 비현실(gunzgame 409); 초과 시 헤딩 항상 방출로 discoverability 유지.
- 검증: `node --check`(module) PASS · [SUBAGENT] 적대 리뷰 결함 0 · POST-DEPLOY PB-0008 라이브(500+ 항목 스키마 전 컨텐츠 카테고리 전체 렌더·hover/클릭, 잔여).
- Cross-ref: TASK 20260715T2237 · CHG/TEST-20260715T223744-graph-cluster-detail-fulllist · test-runs.d/20260715T2237-graph-cluster-detail-fulllist.md · 선행 REV-20260715T215241-graph-cluster-detail-cap · ANCHOR 0003 무충돌.
## REV-20260715T231304-graph-cluster-detail-fulllist-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 컨텐츠 카테고리 전체 출력 + 이벤트 위임 POST-DEPLOY 실증 기록 (CHG-20260715T231304-graph-cluster-detail-fulllist-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T223744 은 REV-20260715T223744([SUBAGENT] 6축 결함 0)로 검증됨. 본 cycle 은 배포 결과 기록만.
- 배포본 실증(win-browser, 배포 41cf76c5): DK온라인 dk_data_release_main(423항목=123테이블+300함수·프로시저) 상세에서 컨텐츠 카테고리 66그룹 전량·423행·(0/N) 0·routine-only 43그룹·스크롤 12423px; 행 자식 click 위임 승격 조회; pageerror 0. ROW_CAP=5000 결정론적 전체 렌더로 사용자 >500 스키마도 동일 커버.
- Cross-ref: CHG-20260715T231304-graph-cluster-detail-fulllist-postverify · 원천 REV-20260715T223744-graph-cluster-detail-fulllist · ANCHOR 0003 무충돌.
## REV-20260715T231656-graph-edge-drag-perf [SUBAGENT:pixi-drag-perf-adversarial + 적대 자가검토] — 그래프 드래그 관계선 재그림 per-frame 부하 최적화 (20260715T2316-graph-edge-drag-perf, Minor §12.3)
- 병목: `_refreshIncidentEdges` 프레임당 O(E) 스캔 + incident 엣지 destroy/new Graphics 재생성(GPU 재할당·GC) + 이중 호출. 3 lever(인접 인덱스·in-place 재사용·rAF 코얼레싱)로 공략.
- 적대 자가검토(refute):
  ① "in-place 재사용이 라벨 stale 남기나?" → `_paintEdge` 가 `g.clear()`(geometry) + `g.children.length` 있으면 `removeChildren()`+각 `destroy()`(라벨/bg) 후 재구성. 라벨 없는 대다수 엣지는 children 0 → 오버헤드 0. stale 무.
  ② "재사용 가드가 node/combo 를 오재사용?" → `typeof old.clear==='function'` — Graphics 만 clear 보유(Container 노드/combo 는 없음) + `old.parent===this.world`. edge id↔node id 충돌 시에도 clear 유무로 분기(안전 폴백=destroy+draw). T24 실증.
  ③ "rAF 지연으로 최종 위치 stale?" → dragend `_emitDrag` 가 `_flushEdgeRefresh`(cancel rAF + 즉시 refresh+render)로 최종 위치 동기 반영. destroy 는 `_pendingRaf` cancel. pointerup 후 잔여 rAF 없음.
  ④ "노드 동기·엣지 rAF = 1프레임 괴리?" → 드래그 중 ≤16ms 엣지 지연은 비가시(minimap 뷰포트는 동기). 정확성 무영향. translateElementTo 는 graph-core `_metaNodeDrag`(1849) 단일 호출(드래그 전용)이라 async 안전.
  ⑤ "_edgeIndex stale?" → 토폴로지(source/target) 의존 → 드래그(좌표만 변화) 동안 유효. setData 가 null 무효화 → 다음 draw 재구성. 부재 시 O(E) 폴백(정확성 유지·성능만 degrade). 미해소 끝점 엣지도 인덱스 포함하되 `_refreshIncidentEdges` 의 `if(!a||!b)continue` 가 skip.
  ⑥ "full draw() 회귀?" → `_drawEdge`=`_paintEdge(new Graphics())` — clear/자식정리 no-op(신규) → 종전 byte-동일. draw diff·_objSig·zIndex·sortableChildren 페인트 순서 불변.
- [SUBAGENT:pixi-drag-perf-adversarial] VERDICT — **레버 3종 CONFIRMED correctness 회귀 없음**(8축 refute: node/edge 1프레임 desync·dragend 최종위치·잔여 rAF·_pendingMoved 오염·_edgeIndex stale·guard 오재사용·byte-동일 draw·비-rAF 폴백 전부 clear). `_built.edges` in-place 변이 없음(grep 확증)·setData→draw 항상 후속(graph-core:1108→1116)·translateElementTo 드래그 단일 호출 확인. **반영한 후속 개선(적대 리뷰 지적)**:
  - **P3(perf 실질, 반영)**: `_refreshIncidentEdges` 가 `getElementPosition`(O(N) `nodes.find`)으로 끝점 해소해 실제 O(incident×N)이던 것 → `_nodeById`(draw 구성·setData 무효화) 기반 `_resolvePos` O(1) 로 교체 = O(N+incident). 허브 드래그 이득 실화.
  - **C2(테스트 가능, 반영)**: `draw()` 인라인 인덱스 구성을 순수 `PixiAdapterPure.buildEdgeIndex(edges)` 로 추출 → 자기루프 1회·null/빈·미해소 끝점 포함 계약을 T25 로 잠금.
  - **C1/C3/C4(실-경로 테스트, 반영)**: T24 가 `_paintEdge`/인덱스를 stub 했던 공백을 T25 로 보강 — 실 `_paintEdge`(clear+stale 라벨자식 destroy+재-path·이중렌더 아님)·재사용불가 else 분기(clear 없는 Container→destroy+_drawEdge)·미해소 끝점 skip 실검증.
  - **P1(검증 계약, 조치)**: rAF 지연으로 mid-drag(pointerup 전) 스냅샷이 stale → PB-0008 은 **pointerup 후**(dragend 동기 flush) 또는 프레임 대기 후 캡처. P2(destroy this.world 미null, 도달불가 defense-gap)·N1(edge-id↔node-id 충돌, 기존 동작·본 변경 미도입)은 non-blocking 기록.
- 검증: `node --check`(ESM) PASS · 헤드리스 T24 10종 + T25 13종 + T23 회귀 ALL PASS **96/0** · [SUBAGENT] 적대 리뷰 결함 없음 + 지적 4건 반영 · POST-DEPLOY PB-0008 라이브(대형 스키마 드래그 프레임률·cross-category 추종 정확성 유지, 잔여).
- Cross-ref: TASK 20260715T2316 · CHG/TEST-20260715T231656-graph-edge-drag-perf · 선행 REV-20260715T181939-graph-edge-follow-drag(추종 정확성 정본) · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260716T000000-graph-edge-drag-perf-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 그래프 드래그 관계선 재그림 최적화 POST-DEPLOY 라이브 실증 기록 (CHG-20260716T000000-graph-edge-drag-perf-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T231656 은 REV-20260715T231656([SUBAGENT] 적대 리뷰 결함 없음 + 지적 4건 반영)로 검증됨. 본 cycle 은 배포 결과 원장 기록만.
- 배포본 실증(win-browser eval, pointerup 후 캡처): 추종 정확성 유지(root 카테고리 + gunzgame 409 dense-edge)·정량 부하개선(40move=30.4ms·burst 중 rAF 0=코얼레싱)·dragend 정합·pageerror 0. 서빙 baked.
- Cross-ref: CHG-20260716T000000-graph-edge-drag-perf-postverify · 원천 REV-20260715T231656-graph-edge-drag-perf · ANCHOR 0003 무충돌.

## REV-20260716T003901-graph-cluster-detail-collapse [SUBAGENT:cluster-detail-collapse-disclosure-adversarial + 적대 자가검토] — 스키마 클러스터 상세: 컨텐츠 카테고리별 접기/펼치기 (20260716T0039-graph-cluster-detail-collapse, Minor §12.3)
- 변경: 컨텐츠 카테고리(sim-group) 헤딩을 접기/펼치기 disclosure(role=button·aria-expanded·캐럿)로, 토글 시 헤딩~다음 헤딩 전 멤버 행 display 토글, 접힘 상태 `_metaGraph.panelGroupCollapsed` 유지, 섹션 헤더 '모두 접기/펼치기'. 기존 `ul` 이벤트 위임 확장.
- **[SUBAGENT] VERDICT — BLOCK/MAJOR 결함 0**. 7축(헤딩vs행 분기·토글 순회·초기 접힘 정합·모두 접기/펼치기·리스너 누적·키보드/포커스·회귀/XSS/CSS) 전부 PASS. MINOR 2 + NIT 1 적발:
  - **MINOR #1 (수정 반영)**: '모두 접기/펼치기' 라벨이 개별 토글 후 stale(동작은 self-consistent·데이터손상 없음, 표시만 오해소지). → `_syncCollapseAllLabel()`(전 그룹 상태로 라벨 재계산)을 `_toggleCtGroup` 말미에서 호출; collapse-all 핸들러의 수동 라벨 설정 제거(중복). 개별·일괄 토글 모두 라벨-동작 정합.
  - **MINOR #2 (수정 반영)**: 함수-지역 `esc`(2262)가 `"` 미이스케이프(파일 내 1358/1648/1774 esc 는 이스케이프). `data-group-key`/`aria-label`/`title` 속성이 상태-키 라운드트립을 실어 나르므로 `"` 포함 식별자 시 속성 breakout 가능(선재 패턴이나 data-group-key 는 새 sink). → esc 에 `.replace(/"/g,"&quot;")` 추가(파일 내 강한 esc 와 정합). 텍스트 노드엔 무해.
  - **NIT #3 (선재·미수정)**: 패널 sim-group/접힘 keyspace 가 comboId 아닌 표시명(`"panel:"+_metaComboName`) 기반 → 동명 스키마 동시 표시 시 충돌 가능. 단 기존 `groupOrder`/`groupTableOrder`(graph-simgroups)가 이미 동일 keyspace 공유 — 본 기능이 상속했을 뿐 새로 유발 안 함(표시명 데이터소스 내 유일 시 무해). 별도 개선 대상.
- **[SUBAGENT] 7축 판정**: ① 헤딩(`.amgr-ct-group`)·행(`.amgr-ct-row-li`) ul 형제·무중첩, 자식 클릭 `closest` 귀속, 헤딩 먼저 판정+return → 오분류 0. ② `nextElementSibling` while 이 다음 `.amgr-ct-group` 에서 정확히 멈춤·마지막 그룹 끝까지·헤딩 사이 이물 노드 없음. ③ `collapsed`(panelGroupCollapsed.has)가 is-collapsed/caret/aria-expanded/행 amgr-ct-collapsed 일관, sg.key 동일 클러스터 결정론 안정. ④ `anyExpanded ? !isCol : isCol` 혼합상태 정확·재렌더 리스너 누적 0. ⑤ _toggleCtGroup 렌더별 새 클로저·위임 `ul` 재생성·collapse-all 새 버튼 재바인딩. ⑥ Enter/Space 헤딩 토글·Space preventDefault·행 button 네이티브 클릭 보존(role=button li 미합성). ⑦ 행 클릭/hover/전체출력/개수 불변·`[data-group-key]` presence 선택자만·CSS `*/` hazard 없음.
- 적대 자가검토: "esc 강화가 텍스트(`<code>`,`<strong>`) 렌더 회귀?" → `"`→`&quot;` 는 텍스트 노드에서 `"` 로 렌더(시각 동일)·속성값에서만 실효. "sync 라벨이 flat 폴백(버튼 부재)서 throw?" → getElementById null-guard + groups.length 가드.
- 검증: `node --check`(module) PASS · [SUBAGENT] 6/6→7/7축 PASS·MINOR 2 수정·NIT 1 선재 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260716T0039 · CHG/TEST-20260716T003901-graph-cluster-detail-collapse · test-runs.d/20260716T0039-graph-cluster-detail-collapse.md · 선행 REV-20260715T223744-graph-cluster-detail-fulllist · ANCHOR 0003 무충돌.

## REV-20260716T005817-graph-cluster-detail-collapse-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 컨텐츠 카테고리 접기/펼치기 POST-DEPLOY 실증 기록 (CHG-20260716T005817-graph-cluster-detail-collapse-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260716T003901 은 REV-20260716T003901([SUBAGENT] 7축 BLOCK/MAJOR 0·MINOR 2 수정)로 검증됨. 본 cycle 은 배포 결과 기록만.
- 배포본 실증(win-browser, 배포 00454608): DK dk_data_release_main(66 컨텐츠 카테고리) 상세에서 헤딩 클릭 접기/펼치기·모두 접기/펼치기(라벨 정합)·재렌더 접힘 유지·키보드 토글·행 클릭 조회 불변·pageerror 0. 스크린샷 육안 정상(접힘 ▸/펼침 ▾ 캐럿 공존).
- Cross-ref: CHG-20260716T005817-graph-cluster-detail-collapse-postverify · 원천 REV-20260716T003901-graph-cluster-detail-collapse · ANCHOR 0003 무충돌.

## REV-20260716T012805-graph-cluster-detail-group-hoverpan [SUBAGENT:cluster-detail-group-hoverpan-adversarial + 적대 자가검토] — 스키마 클러스터 상세: 컨텐츠 카테고리 헤딩 hover-pan (20260716T0128-graph-cluster-detail-group-hoverpan, Minor §12.3)
- 변경: 컨텐츠 카테고리 그룹 헤딩에 hover 시 카메라 팬 추가. 헤딩 `data-pan-key` + 기존 `ul` hover 위임 확장(`_panTargetOf`) → `_metaGraphHoverPan` 재사용.
- **[SUBAGENT] VERDICT — diff 도입 BLOCK/MAJOR/MINOR 결함 0**. 6축(GB키 fam정합·미렌더폴백·hover위임·collapse상호작용·회귀·XSS/제어문자) 전부 PASS. #1 에 **runtime-confirm caveat** 지적: 초판 타깃 = 캔버스 그룹 박스 `GB:comboId+·+fam` — 카드클릭 경로(`_metaGraphShowClusterDetailLocal`, 모델 테이블 = 캔버스 `g.tables` 동일 predicate)는 fam **정확 일치**하나, 콤보/히스토리-뒤로 경로(`_metaGraphShowClusterDetailById`, API depth=1 테이블 우선)는 API↔모델 집합 divergence 시 fam 이 갈려 GB 키 불일치 가능(단 graceful no-op·오타깃 아님·API 집합 그룹핑은 선행 상속이라 신규 결함 아님).
- **설계 변경(caveat 근본 제거)**: 타깃을 **GB 박스 → 그룹 첫 멤버 노드 key(`sg.tables[0].key`)** 로 전환. (a) 첫 멤버는 항상 실 노드라 진입경로·fam 정합 **무관**하게 견고, (b) 행 hover-pan 과 **동일하게 노드로 팬** → 사용자 "다른 객체와 동일하게" 에 더 부합, (c) sim-group 이 캔버스에서 조밀 박스로 팩되므로 첫 멤버 팬 = 그 카테고리 영역 진입, (d) 제어문자(0x01)·String.fromCharCode·fam-매핑 전부 제거(소스 단순·리터럴 0x01 부재 재확인).
- **[SUBAGENT] 6축 판정(설계변경 후 유효)**: ① fam정합 우려 자체가 소거(노드 key 직접) — 리뷰의 "테이블-집합 parity 의존" 무의미화. ② 미렌더/폴백 — 첫 멤버 미렌더(접힘/컬링) 시 `_metaRenderedIdFor`||`_metaRenderedAncestorFor` null → no-op(행 동형). ③ hover 위임 — `_panTargetOf` 행 우선·헤딩 나중, 자식 hover closest 승격, `_hoverKey` 행↔헤딩 재-pan/억제 정합, mouseout 다중선택자+`contains(relatedTarget)`. ④ collapse — click(data-group-key 토글)·hover(data-pan-key 팬) 이벤트/속성 분리, `data-pan-key` collapsed 무관 항상 방출 → 접힌 헤딩·모두접기 후에도 팬. ⑤ 회귀 — `_rowKeyOf`(click 행 전용)·click·collapse·전체출력 미접촉, hover 경로에만 추가. ⑥ XSS — `data-pan-key="${esc(_panKey)}"` esc 적용, 첫 멤버 key 는 기존 `data-node-key` 와 동일 sink.
- 적대 자가검토: "첫 멤버가 API 경로서 미렌더면?" → 펼친 스키마는 모델에 전 테이블 로드·API depth=1 = 동일 테이블이라 렌더됨; 드문 divergence 도 no-op(무해). "헤딩 hover 가 행 hover 와 대상 중복?" → 첫 멤버 노드 = 헤딩 아래 첫 행과 동일 노드라 hover 위치만 다르고 팬 대상 일관(혼란 없음).
- 검증: `node --check`(module) PASS · [SUBAGENT] 6축 결함 0 + caveat 설계변경으로 소거 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260716T0128 · CHG/TEST-20260716T012805-graph-cluster-detail-group-hoverpan · test-runs.d/20260716T0128-graph-cluster-detail-group-hoverpan.md · 선행 REV-20260716T003901-graph-cluster-detail-collapse · ANCHOR 0003 무충돌.

## REV-20260716T015146-graph-cluster-detail-group-hoverpan-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 컨텐츠 카테고리 헤딩 hover-pan POST-DEPLOY 실증 기록 (CHG-20260716T015146-graph-cluster-detail-group-hoverpan-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260716T012805 은 REV-20260716T012805([SUBAGENT] 6축 결함 0·GB→첫멤버 전환)로 검증됨. 본 cycle 은 배포 결과 기록만.
- 배포본 실증(win-browser, 배포 d2c72fdc): DK dk_data_release_main 상세에서 66 그룹 전부 data-pan-key=첫 멤버 노드; 헤딩 hover → 카메라 팬("NPC 콘텐츠"↔"게임 콘텐츠 조회" 서로 다른 영역·미니맵 이동); 행 hover/클릭 불변; pageerror 0. 스크린샷 육안 정상(뷰 이동 확인).
- Cross-ref: CHG-20260716T015146-graph-cluster-detail-group-hoverpan-postverify · 원천 REV-20260716T012805-graph-cluster-detail-group-hoverpan · ANCHOR 0003 무충돌.

## REV-20260716T010501-doc-sync-rn-0716 [SKIPPED:non-policy-doc] — 릴리즈노트 07-15 블록 신규 7항목(관계도 우클릭 정합·상세목록 함수/프로시저 포함+접기·드래그 연결선 추종·ENUM 묶음 승인·권한 '접근'+원자화·'AI 추론' 콘솔·답변 정확도) (TASK-20260716T010501-doc-sync-rn-0716, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync 가 정본(feature-0003 TASK graph-cluster-detail/ctxmenu/edge-drag/enum-bundle/perm-*·feature-0002 TASK attach-coverage/schema-case/alias-guard·feature-0021 REVIEW/admin_reasoning + git log 07-15~16) 대비 직접 검증(ULTRACODE 3-타깃 병렬 analyze→적대 verify wf_01d7fc19-550).
- 적대 대조(정본): 07-15~16 사용자 화면 신규/개선 = 관계도 우클릭 3대상 정합(#808/815/820)·상세목록 함수프로시저+접기(#827/828/830/835)·드래그 연결선 추종+성능(#824/832)+도움말(#804)·ENUM 묶음 승인(#811/817)·권한 카테고리+원자화(#801/810)·'AI 추론' 콘솔(feature-0021 affeea67·#821 라이브 검증)·답변 정확도(#823/803/809/813/807/826/833·feature-0021 자체점검). 제외=각 *-postverify(문서)·#805 friction-ledger(내부)·probe/throttle 내부 안정성(⑥ 포괄). feature-id/§/PR#/테이블/함수/권한키/라이브러리/red-team 누출 0(vm leak 스캔).
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(30 releases·07-15 head 7항목[admin 6·common 1]·07-14 보존 10·스키마·누출0). item #6 area='common' = 직전 07-14 블록 ⑩ 답변정확도 area='common' 선례 정합(직접 재확인).
- **pre-existing 무관 실패 정직**: `verify_release_notes.mjs` 33/34 PASS·1 FAIL([스크롤] admin release-notes pane overflow-y:auto 정규식) — `styles.css`(본 cycle 미변경) 대상, 규칙(line 4386 `overflow-y:auto`)은 실재하나 선택자~속성 사이 설명 주석(~200자)이 테스트 160자 정규식 창 초과 → false-negative. pristine HEAD(data 편집 stash)에서 동일 FAIL 재현으로 무관 확인. feature-0003 테스트 정규식 brittleness 는 feature cycle 소관(doc_sync 는 product CSS/feature test 미편집).
- **cache-buster**: 소스 `?v=dev` 고정 — 07-12 ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. system-prompt 의 '수동 bump' 지시는 그 정책 이전 모델 기준이라 부적용(수동 변경 시 injector placeholder 매칭 무력화·해당 2파일 캐시무효화 상실). 직전 doc-sync-rn-0713/0714/0715 동일 판단.
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260716T010501-doc-sync-rn-0716 / META REV-20260716T010501-META-0037-doc-sync-0716(별도 commit 0cc64c2b) / 원천 PR 07-15~16. **landing/배포 소유=cron wrapper 위임(로컬 commit 만).**

## REV-20260716T140735-doc-sync-rn-0716b [SKIPPED:non-policy-doc] — 릴리즈노트 07-16 블록 신규 4항목(관계도 검색 확대/결과 목록·상세 [뒤로/앞으로] 탐색 UX·카테고리 헤딩 hover 이동·콘솔 유사 화면 서브탭 통합) (TASK-20260716T140735-doc-sync-rn-0716b, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피는 doc_sync 가 정본(feature-0003 TASK graph-search-panel-groups/graph-search-detail-panel/graph-cluster-detail-group-hoverpan·feature-0016 TASK graph-detail-scroll/nav-sticky/nav-hover-fade/nav-focus-fade-fix·feature-0021 TASK/FUNCTION console-ia/subtabs + git log 07-16 PR #837~#853) 대비 직접 대조 검증.
- 적대 대조(정본): 07-16 낮 사용자 화면 신규/개선 = 그래프 검색 콘텐츠 카테고리·AI 분석 매칭(#837)+상세 패널 검색 결과 리스트(#839)+2단 접기·이력·간결화(#846)·상세 [뒤로/앞으로] 스크롤 보존(#841)·sticky(#843)·hover-fade(#844)+fix(#845)·카테고리 헤딩 hover-pan(#838)·콘솔 IA 감사/설정 분리(#847)+서브탭 통합(#850)+sticky(#852). 제외=각 *-postverify(문서)·권한 재배치 내부 체계. feature-id/§/PR#/권한키/함수명 누출 0.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(31 releases·07-16 head 4항목[admin 4]·07-15 보존 7·스키마·누출0).
- **cache-buster**: 소스 `?v=dev` 고정 — ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. 직전 doc-sync-rn-0713~0716 동일 판단.
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260716T140735-doc-sync-rn-0716b / META REV-20260716T140735-META-0038-doc-sync-0716b(별도 commit) / 원천 PR #837~#853. **attended run — landing/배포 스킬 소유.**

## REV-20260722T010501-doc-sync-rn-0722 [SKIPPED:non-policy-doc] — 릴리즈노트 07-21 블록 신규 1항목(진행상황 실시간 전파) (TASK-20260722T010501-doc-sync-rn-0722, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·완료형 정당성(a999594e frontend-only 머지→wrapper 배포로 라이브·별도 활성 불요)·area(work — 대화/작업 화면 가시 변화)·누출 회피는 doc_sync 가 정본(feature-0003 TASK/REPORT realtime-progress-propagation + git log 8f3dd00b..HEAD) 대비 직접 검증 + ULTRACODE 타깃별 적대 verify(wf_b9eb441a 초판 — feature-0022 상태 오류 등 8건 적발 → 정정, wf_97d7d599 정정 재검증).

## REV-20260721T175800-realtime-progress-propagation [SUBAGENT:general-purpose] — ACCEPTED-WITH-FIXES (고위험 결함 0, low-med 2건 반영·1건 정밀화·2건 bounded 문서화)
- 대상: `static/app.js` 유휴 run-감지 폴러 diff(+133/추가 함수 `detectNewRun`·`scheduleRunDetectPolling`·`startRunDetectPolling`·`stopRunDetectPolling`·`clearRunDetectTimer` + `loadHistory`/`selectConversation`/`handleLogout`/`visibilitychange` 배선). 적대 리뷰 프롬프트: 폭주/중복 폴링·lifecycle 누수·baseline race·feature-0009 foreign-run 하이재킹·myAskInFlight 오귀속·비용/백오프·일반 correctness.
- 종합 판정: **핵심 메커니즘 건전** — seq-gating(monotonic `runDetectSeq` + stale bailout)과 4-신호 dormant 가드가 (a) 활성 폴러와의 중복 fetch, (b) 로컬 본인 run 하이재킹("처리 중" 고착)의 두 최악 시나리오를 정확히 차단. runaway-timer/stuck 시나리오 구성 실패(=안전).
- **D1 (low-med, 반영)**: 감지기가 트리거한 `loadHistory()` 가 throw(`/api/history` 네트워크 blip)하면 `reschedule=false`(await 전 설정)+outer catch 삼킴 → 감지기 영구 disarm. **Fix**: `_detectHandoffReload(seq)` 헬퍼 도입 — loadHistory 성공 시 loadHistory 가 감지기 상태 관장(idle 재무장/processing 정지), throw 시 seq 유효하면 재무장. 회귀 테스트 S7 추가.
- **D3 (pre-existing, 정밀화 반영)**: `myAskInFlight.add` 가 `!isGroupConversation` 만 게이트해 **모니터링(타 계정 소유) 1:1** 도 포함 → 유휴 감지기가 loadHistory 자동 트리거 시 관찰자에게 동작 안 하는 중단/즉시답변 버튼 오표시(cosmetic·send/cancel 은 백엔드 권한 차단). 리뷰어 확인 "신규 회귀 아님". **Fix**: 문서화된 의도("본인 대화")대로 `isOwnConversation() && !isGroupConversation()` 로 정밀화(그룹은 종전대로 제외).
- **re-entrancy(반영)**: `detectNewRun` 재진입 가드 부재(리뷰어: 최대 1회 transient 중복 fetch) + `runDetectInFlight` write-only dead-state 지적 → dormant 가드에 `state.runDetectInFlight` 추가(dead-state 를 re-entrancy 가드로 활용). 회귀 테스트 S8 추가.
- **방어(반영)**: `beginPendingConversation`·`_switchToPendingConversationContext` 가 `stopProgressPolling` 만 하고 `stopRunDetectPolling` 누락(리뷰어: activeConversationId="" 로 self-terminate 하므로 현재 무해하나 fragile asymmetry) → lifecycle 대칭 위해 `stopRunDetectPolling()` 추가.
- **D2 (bounded, 문서화)**: 무장 후 첫 폴링에서 `loadHistory`↔첫 `/api/progress` 사이(1 라운드트립) run 이 start+complete 하면 그 terminal run 이 baseline 에 흡수돼 미로드. 첫 폴링 한정·다음 run 에서 self-heal — 원 버그의 축소 잔재(신규 회귀 아님). 완전 봉인은 `/api/history` 가 terminal run_id 도 반환하는 백엔드 변경 필요(feature-0012 라우터분할 충돌 회피 위해 이연). 
- **hide/show gap (bounded, 문서화)**: 탭 숨김 중 run 이 전부 완료되면 재가시 시 다음 run/전환 전까지 미반영(재가시는 미래 감지만 arm). pre-feature 거동과 동일(신규 회귀 아님)·숨김 중엔 "실시간" 관측 불가라 실질 영향 경미.
- **비용(정상)**: 숨김 탭 `stopRunDetectPolling` 로 완전 정지·활성 탭 4s clean reschedule — 백오프 정상. "모든 대화 유휴 폴링" 은 사용자 선택 scope 의 product 결정(구현 결함 아님).
- 반영 후 검증: `node --check` PASS · 유닛 `verify_run_detect_poll.mjs` **28/28**(D1 재무장 S7·re-entrancy S8 포함). feature-0009 그룹 경로 안전(리뷰어 확인 — foreign run 을 progressRunId 로 채택, 5870 가드 무충돌).
- Cross-ref: CHG-20260721T1758-realtime-progress-propagation · ANCHOR feature-0003 §1-§3 무충돌 · TEST §16.6 PB-0008 PASS(실 Windows Chrome 150).

## REV-20260722T020408-msg-edit-textarea-contrast [SKIPPED:trivial-display-only] — 메시지 '수정' 편집 UI 글자 비가시 수정 + 편집 폼 재구성 (20260722T020408-msg-edit-textarea-contrast, Minor §12.3)
- Panel skip 사유(§18.8): 순수 표시 변경 — `styles.css` 색/특이도 규칙 + `app.js` 1행 `classList.add`. 백엔드·엔드포인트·RBAC·스키마·편집 로직(`_submitMessageEdit`·브랜치·IDOR 게이트) 0, 보안 posture 불변. 선례 REV-20260716T051931-ds-test-gate-fix([SKIPPED:trivial-regression-fix-display-only]) 와 동류(§18.8 표: display-only 프론트 표시 수정 → full 패널 skip).
- 적대 자문점 자체점검: ① 특이도 — 신규 `.message.is-user .message-bubble.message-bubble-editing`(0,4,0) > 파랑 `.message.is-user .message-bubble`(0,3,0), 실브라우저 렌더로 bubble bg=흰 서피스(255,255,255) 실측 확인. ② 클래스 충돌 — `message-bubble-editing` unique(기존 `is-editing`(admin dashboard)·`.dashboard-widgets.is-editing` 와 선택자 분리). ③ 잔존 위험 — 재렌더로 클래스 소멸(취소=renderMessages/성공=refreshWorkspace) → 편집 취소 후 말풍선 원래 파랑 복귀. ④ 회귀 — 편집 진입(innerHTML 교체) 컨텍스트에만 적용, 일반 말풍선/컨텐츠 렌더 미접촉. ⑤ 라이트 전용 콘솔(styles.css H1)이라 다크 분기 불요.
- 검증: `node --check` PASS · headless Chromium 실측(수정본 textarea 15.38:1·재답변버튼 5.17:1·편집 말풍선 중립전환 / 수정전 1.0:1 버그 재현) + 스크린샷 · POST-DEPLOY PB-0008 Windows-browser(잔여, visual_verification_scope=always).
- Cross-ref: CHG/TASK/TEST-20260722T020408-msg-edit-textarea-contrast · feature-0019 ANCHOR §1-§3 무충돌.

## REV-20260722T024500-msg-edit-textarea-contrast-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 메시지 편집 UI 대비 수정 POST-DEPLOY 라이브 실증 기록 (CHG-20260722T024500-msg-edit-textarea-contrast-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록). 실 구현 코드 리뷰 정본 = REV-20260722T020408-msg-edit-textarea-contrast([SKIPPED:trivial-display-only]). 본 cycle 은 배포(f7a14e9a)+Windows Chrome 150 라이브 실측 결과 append 만.
- 실증: textarea color=rgb(38,37,30) on bg=rgb(255,255,255)(대비 ~15.4:1)·편집 말풍선 `message-bubble-editing`=true·bg=흰 서피스(중립 전환)·재답변버튼 흰글자 on 파랑 + 스크린샷 육안. 사용자 신고(흰 글자 on 흰 배경) 해소 확인.

## REV-20260722T125200-point-rail-range-window [SUBAGENT:general-purpose] — ACCEPTED-WITH-FIXES (Major §12.3 — feature-0003 web/UI, /_template:entry arg-given dispatch)
- 요청 해석: "우측 대화 뱃지" = 메인 뷰 point rail(`app.js`/`styles.css`). 공유 읽기전용 뷰(`share.*`)는 별도 코드라 범위 제외("assistant와 대화를 주고받는 화면"=메인). 3요구 A(범위화)/B(클릭 비례)/C(윈도잉).
- 설계 판단:
  - A: rail 을 대화 세로 미니맵으로. top%/height% 는 messageLog scrollHeight 대비(기존 중심점 top% 와 동일 기준) → rail(뷰포트 높이)에 압축 표시. min-height 로 짧은 메시지 클릭성 보장.
  - B: 신규 `scrollMessagePointToRatio` 로 클릭 y→메시지 [top,bottom] 매핑. 기존 center 함수는 검색/앵커 점프가 재사용하므로 비파괴 유지.
  - C: 신규 DOM 가상화 대신 **기존 `loadHistory` 서버 페이징 재사용**(회귀면 최소화 — 완전 가상화는 첨부/읽음/optimistic/live-poll 상호작용 위험 큼). "화면 4배만 로딩"=초기 로드 목표 높이(하한 채움). 아래로 unload 미수행(요청은 "추가 로딩"만).
- 적대 코드리뷰(REV subagent) 반영: R1(cross-conversation `state.messages` 오염 — `loadHistory` gen-guard)·R2(프로그래매틱 점프 중 자동로드가 목표 어긋냄 — `_pointScrolling`)·B1(전역 `_fillingWindow` 가 빠른 전환 시 새 대화 fill 억제·이전 루프 오염 — 대화별 `_fillToken`). 핵심 우려 preserveScroll flag leak 은 flag 제거 재설계로 원천 소거(리뷰어 moot 확인).
- Known limitation B2 (코너케이스, 미수정): append(과거 자동로드)와 그 대화의 processing 새 run pending-bubble 최초 생성이 동시일 때, `_endAppendScrollPreserve` 의 `delta = scrollHeight - preH` 가 바닥 성장분(pending bubble)을 포함해 소폭 과도 스크롤(뷰가 pending 높이만큼 위로 튐). 발생 조건 희소(유휴 과거 탐색 중 새 run 최초 pending)·자기치유(다음 클린 로드)·영향 경미(pending 높이 소). 별도 cycle 재검토 여지.
- 위험도 Major: 다중 파일·스크롤 로직·회귀 위험(신규 가상화 아님·기존 페이징 재사용으로 완화). 비파괴 additive — 인증/인가/데이터 무영향.

## REV-20260722T135500-point-rail-range-window-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 라이브 시각검증 기록 (CHG-20260722T1355-point-rail-range-window-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록). 실 구현 코드 리뷰 정본 = REV-20260722T125200-point-rail-range-window([SUBAGENT:general-purpose]). 본 cycle 은 배포(22c3b9cb)+Windows Chrome 150 라이브 실측(A·B 라이브 PASS·C 자동 페이징 20개+ 대화 부재로 미트리거) 결과 append 만.

## REV-20260722T142000-point-rail-range-window-dom-windowing [SUBAGENT:general-purpose] — ACCEPTED-WITH-FIXES (윈도잉 강화, Major §12.3 — feature-0003 web/UI, 사용자 후속 요청)
- 사용자 후속 요청: "다른 대화도 확인하여, 이전 대화가 너무 많이 불러와졌을 경우 일부만 로딩되는지 검증". 라이브 실측에서 이 환경 대화 모두 20개 미만(hasMoreHistory=false)이라 서버 페이징 gap 발견 — 20개 미만이나 높이 4배 초과 대화(conv 14개·높이 20배)가 전부 렌더됨. → `state.renderCount` DOM 윈도잉으로 진짜 4배 상한 구현.
- 적대리뷰(general-purpose subagent) 반영: **발견1(필수·회귀)** `_visibleMsgs.forEach` 의 `_msgIdx` 가 절대→창-상대로 바뀌어 `_precedingUserQuestion`(피드백 Q↔A 매칭)·투표 게이트·공유 range idx 비교가 윈도잉된 긴 대화(주 사용 케이스)에서 깨짐 → `_windowBase` 로 절대 인덱스 복원. 발견2(floor 칩 창밖 — loadHistory renderCount 리셋 시 floor 포함). 발견5(검색 첫 매칭이 optimistic id=null 이면 중단 — skip). 발견6(주석).
- Known limitation(미수정, 엣지): 발견3(윈도잉+위 스크롤 중 live-poll 도착 시 tail 창 슬라이딩으로 scrollTop 보존이 어긋나 소폭 튐)·발견4(`_maybeExpandOrLoadOlder` 확장이 짧은 메시지 다수 시 여러 배치 연쇄 — total 상한이라 무한 아님·순간 부하). 별도 cycle 재검토 여지.
- 위험도 Major: `renderMessages` 렌더 경로 변경(창 렌더). 비파괴 additive — 인증/데이터 무영향.

## REV-20260722T144000-point-rail-window-initial-tuning [SKIPPED:param-tuning-no-logic-change] — 윈도잉 초기 렌더 개수 튜닝
- Panel skip 사유(§18.8): 상수(`WINDOW_INITIAL_RENDER` 8→3) 1개 변경, 로직 불변. 윈도잉 구현 리뷰 정본 = REV-20260722T142000-...([SUBAGENT:general-purpose]). 라이브 실측 근거(conv[2] 초기 8개=높이 13배 → "4배만" 미달)로 초기값만 하향.

## REV-20260722T145000-point-rail-windowing-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 윈도잉 라이브 재검증 기록 (CHG-20260722T1450-point-rail-windowing-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록). 윈도잉 구현/튜닝 리뷰 정본 = REV-20260722T142000-...([SUBAGENT])·REV-20260722T144000-...([SKIPPED:param-tuning]). 본 cycle 은 배포(66d1e735) 라이브 실측(conv[2] 초기 3개·확장) append 만.

## REV-20260722T192736-history-top-indicator [SKIPPED:trivial-display-only] — 대화 상단 페이드 신호 (Minor §12.3 — feature-0003 web/UI, /_template:entry 후속)
- Panel skip 사유(§18.8): 순수 표시 변경 — 페이드 div 1개(pointer-events:none) + CSS gradient + `_updateHistoryTopIndicator`(renderCount/hasMoreHistory 판정으로 hidden 토글). 백엔드·엔드포인트·RBAC·스키마·편집 로직 0, 보안 posture 불변. 선례 REV-20260722T020408-msg-edit-textarea-contrast([SKIPPED:trivial-display-only])·ds-test-gate-fix 와 동류.
- 설계: 사용자 검토 후 결정 — 페이드만(칩·스피너·텍스트 제거로 난잡함 회피), 점프=캘린더·로드=스크롤 자동. 위에 더 있음 판정 = `renderCount<total || hasMoreHistory` (윈도잉 창 밖 + 서버 미로드 둘 다 포함).

## REV-20260722T195000-history-top-indicator-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 라이브 검증 기록
- Panel skip 사유(§18.8): 코드 0(문서 전용 POST-DEPLOY 실증). 구현 리뷰 정본 = REV-20260722T192736-history-top-indicator([SKIPPED:trivial-display-only]). 배포(029927dc)+라이브 실측(페이드 표시/숨김/무방해) append 만.

## REV-20260722T122635-shared-branch-readonly-paging [SUBAGENT:general-purpose] — SHIP-WITH-FIXES (1 real-defect 반영, 6축 not-a-defect, 신규 누출 0) — 공유/그룹·익명 공유-링크 뷰 편집 버전 읽기전용 페이징 (20260722T122635, Major §12.3, PLAN-APPROVED design-review C)
- §18.8 적대적 **보안** 리뷰(general-purpose, 7축). **익명 공유 뷰 신규 누출 없음** — 변경 전 `_share_load_messages` 는 [floor,anchor] 내 모든 브랜치를 평면 노출했고, 이 변경은 기본 노출을 active 브랜치로 축소 + branch_view 도 동일 id-범위로만 한정(범위 밖 content·존재 차단). 배포 차단 사유(누출) 없음.
  - **[3] real-defect (반영 완료)**: 브랜치된 그룹의 **평문 멤버 채팅**(`_save_group_chat_message_pg`)이 parent 없이·leaf 전진 없이 고아 삽입 → 새 active-path 필터(그룹 enrich)에서 결정론적 은닉(멤버 채팅 사라짐, availability 회귀). 옛 SEC MINOR-B skip 이 이걸 막던 것. **수정**: `_save_group_chat_message_pg` 의 두 store 쓰기를 has_branches 시 active_leaf 에 체인+전진(memory.py 래퍼 로직 답습). 비분기는 parent None(무회귀). 회귀 테스트 2건(체인/비분기) 추가.
  - **[1] 범위 밖 버전 누출 not-a-defect**: `_branch_version_groups(visible_pred)` count/sibling 배제 + `_branch_resolve_readonly_leaf` fail-closed. leaf-범위안·조상/후손-범위밖 우회도 (messages ∩ active_ids) 교집합 + 형제≠후손으로 차단. 존재 oracle 없음(범위밖/미존재 응답 동일).
  - **[2] active-path 조상 누출 not-a-defect**: 교집합 `messages`(상위 window/id-범위 필터됨)가 방어 — 범위 밖 조상은 애초에 messages 부재.
  - **[4] 읽기전용 불변 not-a-defect**: override 경로 로컬 변수만·DB 미기록. `/branch/switch`·reanswer 그룹 400 유지(INV-4).
  - **[5] 주입/타입 not-a-defect**: branch_view int 강제·공유는 try/except→None. resolver SELECT `conversation_id=%s AND id=%s` 로 타대화/음수/거대 무매칭→None. leaf CTE table allowlist+cid 스코프.
  - **[6] 비분기/1:1 회귀 not-a-defect**: has_branches=false 전체 skip. 1:1 owner(window=None→pred None→전체) 페이징·switch 영속 불변. FE 1:1 은 `_switchBranch` 영속 라우팅 유지.
  - **[7] fail-soft not-a-defect**: enrich 예외 시 원본 반환 — 그러나 messages 는 상위 window/id-범위로 이미 잘려 범위 밖 누출 불가(옛 flat 수준으로만, 경계 내).
  - **[3-2] 권고(bounded 문서화)**: 브랜치된 그룹 **동시 @assistant overlap** 시 cross-run fork 로 한쪽 turn 이 비활성 sibling 으로 갈 수 있음(per-run 커서는 run 내부만 봉인 — branch-chain-race fix 의 알려진 경계, [5] version-active 격하). 드묾·availability(누출 아님)·재답변으로 복구 가능. 후속 하드닝(첫 write active_leaf read 를 SELECT FOR UPDATE 직렬화) 여지 — 본 cycle 범위 밖 문서화.
- 반영 후 검증: `py_compile` 5 + `node --check` 2 · 보안 단위 `tests/test_shared_branch_readonly_paging.py` **12 PASS**(id-범위/window 스코핑·resolver fail-closed·[3] 그룹채팅 체인/비분기 무회귀) · feature-0003 전체 회귀(예정).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260722T122635 · feature-0019 ANCHOR INV-4 개정(mutation 잠금 유지+read 가시성 확장) · POST-DEPLOY 양 surface PB-0008.

## REV-20260722T130000-shared-branch-readonly-paging-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 공유 읽기전용 페이징 배포 + 양 surface 라이브 검증 기록 (CHG-20260722T130000)
- Panel skip 사유(§18.8): 코드 0(POST-DEPLOY 실증·TASK 완료). 코드/보안 리뷰 정본 = REV-20260722T122635([SUBAGENT:general-purpose] SHIP-WITH-FIXES, 누출 0).
- 실증(배포본 622b7434): **공유-링크(익명)** pager 메타 1/2·branch_view=1313 읽기전용 전환·999999999 fail-closed. **인앱 그룹(인증)** pager window-scoped·branch_view 전환·active_leaf 불변(읽기전용 확인). 서빙 자산 반영. Windows-browser 시각 스크린샷은 브리지 다운으로 미수행(§15.4.1 escape) — API end-to-end + 단위 12 PASS 로 보완, 시각 확인은 브리지 복구/사용자 브라우저 잔여.

## REV-20260723T010501-doc-sync-rn-0723 [SKIPPED:non-policy-doc] — 릴리즈노트 07-22 블록 신규 6항목(대화 UI 안정화·탐색) (TASK-20260723T010501-doc-sync-rn-0723, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·완료형 정당성(6항목 전부 owning POST-DEPLOY 커밋으로 라이브 확증; f0a32980 은 브리지 다운 §15.4.1 escape·API e2e+단위 12 보완)·area(work)·누출 회피는 doc_sync 가 정본(각 항목 owning POST-DEPLOY 커밋 + git log cfa647df..HEAD) 대비 직접 검증 + ULTRACODE 타깃별 적대 verify(wf_4ab4d814 — RN 6 INCLUDE holds·feature-0023 등 8 EXCLUDE 사유 정확 confirmed, cross-target cross-fault 회피 스코프).

## REV-20260723T024724-paging-scroll-preserve [SKIPPED:trivial-frontend-ux] — 브랜치 페이징 스크롤 위치 보존 (20260723T024724-paging-scroll-preserve, Minor §12.3)
- Panel skip 사유(§18.8): 순수 프론트 스크롤 UX — `app.js`(loadHistory preserveScroll 옵션·_pageBranch/refreshWorkspace 배선)·`share.js`(window.scrollY 보존). 백엔드·엔드포인트·RBAC·스키마·데이터 0, 보안 표면 없음.
- 자체점검: ① append/일반 로드 경로 무변경(preserveScroll 미지정 시 기존 맨-아래/prepend). ② 1:1 은 refreshWorkspace 유지(사이드바 프리뷰 등 갱신 보존)하고 preserveScroll 만 전달 — behavior 드롭 없음. ③ rAF 복원(layout 확정 후, scroll-restore 규약)·`Math.min(saved,maxTop)` clamp(오버스크롤 방지). ④ 공유 뷰 문서 스크롤도 rAF+clamp. ⑤ 브랜치 대화(has_branches) 페이징에만 preserveScroll — 일반 대화 무영향.
- 검증: `node --check` app.js/share.js PASS · POST-DEPLOY 실브라우저 scrollTop 실측(layout 의존, jsdom 부적합).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260723T024724 · feature-0019 브랜치 페이징(PR#887) 후속 UX.

## REV-20260723T033000-paging-scroll-preserve-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 페이징 스크롤 보존 배포 + 양 surface 라이브 실측 (CHG-20260723T033000)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료). 정본 = REV-20260723T024724-paging-scroll-preserve([SKIPPED:trivial-frontend-ux]).
- 실증(Windows Chrome, 배포본 4ee7ea1d): 인앱 그룹 페이징 scrollTop=0(scrollable maxTop 9538)·스크린샷 육안 상단 pager. 공유-링크 페이징 window.scrollY=0(scrollable maxY 11535). 둘 다 맨-아래 튐 해소(PRESERVED). layout 의존 실브라우저 실측(jsdom 부적합)으로 정본 검증.

## REV-20260723T033143-paging-scroll-longhistory [SKIPPED:trivial-frontend-ux] — 긴 이력 페이징 스크롤 보존 회귀 수정 (20260723T033143-paging-scroll-longhistory, Minor §12.3)
- Panel skip(§18.8): 프론트 렌더창 1줄 로직(preserveScroll 시 renderCount=len). 백엔드·RBAC·스키마 0. 이전 REV(paging-scroll-preserve) 후속 회귀 수정.
- 자체점검: ① 전체 렌더는 preserveScroll(페이징)에만 — append/일반 로드 무변경. ② 형제 버전 분기점-위 이력 동일 → 절대 scrollTop 보존 정확·pager 항상 렌더. ③ 스레드=활성 경로라 크기 bounded(전체 렌더 perf 허용). ④ 공유 뷰(share.js)는 원래 전체 렌더라 무영향(별도 확인).
- 검증: node --check PASS · POST-DEPLOY PB-0008.

## REV-20260723T034500-paging-scroll-longhistory-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 긴 이력 페이징 스크롤 보존 배포+라이브 실측 (CHG-20260723T034500)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료). 정본=REV-20260723T033143-paging-scroll-longhistory.
- 실증(Windows Chrome, 배포본 2cdb7907): '간단한 덧셈 계산' 3→4 페이징 시 전체 렌더(rendered 6)로 pager '4/4' 유지·브랜치 메시지 뷰포트 위치 298px 동일 보존·맨아래 안 튐(maxTop 11286, atBottom=false)·스크린샷 육안. 회귀(pager 소실+스크롤 급변) 해소 확정.

## REV-20260723T034321-conv-date-tree [SUBAGENT:general-purpose] SHIP-WITH-FIXES — 대화목록 날짜 그룹핑 적응형 트리(월/년 집계) (TASK-20260723T034321-conv-date-tree, Major §12.3)
- 적대적 프론트/UX 리뷰(general-purpose, 코드 직접 판독) 6축 점검. 판정: SHIP 아님 → **MAJOR 1건 in-cycle 수정 후 SHIP-WITH-FIXES**.
- **[MAJOR — 수정 완료]** seed × 안정 집계 키의 영속 충돌/파괴: `_seedDateGroupsCollapsedOnce`가 매 로드 최근 그룹 외 전부를 강제 접힘시키는데, 기존 일(日) 키는 매일 바뀌어 무해했으나 `month:`/`year:`는 안정 키라 — ① 사용자가 펼친 6월이 reload 시 재접힘돼 localStorage 와 불일치, ② 이후 무관 그룹 토글 시 `_saveCollapsedGroups`가 in-memory set 전체 저장 → 사용자 영속 펼침 선호를 조용히 collapse 로 덮어씀. **폴더 기능이 이 collapse-영속 모델 위에 세워지므로 근본 수정 필수.** 수정: seed 분리 — 일 단위 키만 로드당 재적용(`_seedDateGroupsCollapsedOnce`가 `_isAggregateGroupKey` 필터), 집계 키는 `_seedAggregateGroupsCollapsedOnce`가 `_seededAggKeys`(신규 localStorage `mad.seededAggGroups.v1`)로 "처음 본 순간 1회만 접힘 seed + 영속" 후 사용자 토글 존중. 결정적 재현 테스트 9/9 PASS(첫 로드 기본 접힘·펼침 영속·reload 강제 재접힘 없음·무관 토글 후 선호 보존).
- **[MINOR — 수정 완료]** 미래 `last_activity_at`(데이터 이상)이 "오늘" 위 정렬/유령 미래 월 노드: `dStart = Math.min(rawStart, today)` clamp 로 미래 날짜를 "오늘" 버킷 합류.
- **[NIT — 수정 완료]** `.conv-date-group-label` inline-flex 하에서 무효였던 `text-overflow: ellipsis`/`overflow`/`white-space`/`min-width` 死코드 제거(라벨 항상 짧음).
- **[NIT — 유지·근거]** 서브 대화 항목(depth1 22px) < 월 서브헤더(24px) 2px: 기존 depth-0 패턴(일 헤더 10px / 항목 8px = 헤더−2px)과 **일관**. 각 depth 에서 항목=헤더−2px 유지가 사이드바 전체 톤과 정합(회귀 아님) + 항목엔 leading dot+gap 이 있어 실제 텍스트는 더 우측. 유지.
- **[NIT — pre-existing·defer]** 날짜 그룹 헤더 키보드 조작 불가(`role=button`+click 만, tabindex/keydown 부재): 기존 owner/date 헤더 전체가 동일 — 이번 diff 신규 결함 아님. 새 집계 노드만 고치면 owner 헤더와 불일치하므로 본 cycle scope 밖. 헤더 전체 a11y 일괄 개선은 후속 항목으로 defer(TODOS 성 기록).
- **[안전 확인]** 키 충돌 없음(top-level 월 노드는 `dY===nowY`·연-자식 월 노드는 else 분기 → `YYYY` 상이로 collapse 상태 공유 불가) · 집계 정확(Map 키 병합 단일 노드·"6월 중복" 소멸) · 리스너 누수 없음(`innerHTML=""` 전체 초기화) · 배지 계산 정확(branch=자식 items 합·leaf=items.length) · 월/연 경계 timestamp 산술로 정확 · 파싱불가→__other__·dangling ref 0 · folder-readiness 재귀 모델 재사용 가능.

## REV-20260723T130200-conv-date-tree-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 대화목록 날짜 그룹핑 적응형 트리 배포 + 라이브 시각검증 (CHG-20260723T130200-conv-date-tree-postverify)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료 기록). 정본 = REV-20260723T034321-conv-date-tree([SUBAGENT:general-purpose] SHIP-WITH-FIXES).
- 실증(Windows Chrome 150, 배포본 0b15a0ea): 배포본 `_buildOwnDateTree` 합성 6/6 + 실계정 사이드바 단일 "6월"[38]·"5월"[15]·중복 라벨 0(이전 ~10개 소멸) + 6월 토글 4→42(배지 정확) + 스크린샷·pageerror 0. 중복 "6월" 혼잡 해소·월/연 집계·연>월 중첩·개수 배지·토글 라이브 확정.
## REV-20260723T071355-universal-ctxmenu [SUBAGENT:general-purpose] SHIP — 서비스 UI 우클릭 = 보편 확장 메뉴 단축 (TASK-20260723T071355-universal-ctxmenu, Major §12.3)
- 적대적 프론트/UX 리뷰(general-purpose, 코드+diff 직접 판독) 8축 점검. 판정: **SHIP** (BLOCKING/MAJOR 0). 검증 통과: 앵커 수명(`_floatingMenuAnchorPoint` 를 synchronous `dispatchEvent` 로 openFloatingMenu 가 소비·finally 방어 해제 → left-click 누출 경로 없음) · anchor=null 3항 ternary 가 원본 표현으로 환원(byte-동치, (0,0) 우클릭도 truthy 유지) · synthetic click 무-사이드이펙트(우클릭=button2 는 native click 미발화 + 트리거 stopPropagation → 대화 선택/폴더 토글 안 됨) · no-trigger/pending·disabled 항목 graceful 폴백(native 우클릭) · 예외 가드(closest/nodeType/querySelector/MouseEvent) · 단일-fire(호스트 disjoint DOM·첫 매치 return·리스너 1회 등록).
- **[MINOR ×3 — in-cycle 수정 완료]** ① 미디어(img/svg/canvas/video)·assistant 답변 mermaid SVG/이미지 우클릭이 ☰ 로 가로채져 "이미지 저장/링크 열기" native 손실 → 양보 selector 에 `img,svg,canvas,video` 추가. ② 키보드 contextmenu(Menu키/Shift+F10, 일부 브라우저 clientX/Y=0)가 좌상단 오배치 → `fromKeyboard`(coords≤0) 시 anchor=null trigger-rect 폴백. ③ `_hasSelectionWithin` 의 commonAncestor-wrap 분기가 stale 교차-메시지 선택 시 무관 호스트 우클릭 과잉차단 → `Range.intersectsNode`(실제 겹침만·구형 브라우저 containment 폴백)로 교체.
- **[NIT ×2 — 무해 유지]** 우클릭 토글 비대칭(호스트 body 우클릭은 mousedown-close→contextmenu-reopen 재배치 / 트리거 정확 우클릭만 toggle-close) · synthetic click 이 focus 미이동(aria-expanded 정합·ESC focus 복원 동작) — 컨텍스트 메뉴 관례상 무해.
- 검증: `node --check app.js` PASS(리뷰 반영 후) · CHECK#13 POST-DEPLOY PB-0008 (TEST fragment 20260723T071355-universal-ctxmenu, AC-1~5).

## REV-20260723T075215-universal-ctxmenu-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 서비스 UI 우클릭 보편 확장 메뉴 배포 + 라이브 실측 (CHG-20260723T075215-universal-ctxmenu-postverify)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료 기록). 정본 = REV-20260723T071355-universal-ctxmenu([SUBAGENT:general-purpose] SHIP).
- 실증(win-browser Chrome 150, 배포본 c6f7f98a, https://localhost/): 서빙 app.js(stamp e6d39fde416f) 신규 심볼 5종 전부 hit + 실 contextmenu(button2) dispatch — AC-1 대화항목→'···' 커서(226,68)·AC-2 폴더헤더→폴더메뉴(168,48)·AC-3 말풍선→'☰' 커서(191,588)·AC-4 텍스트 663자 선택 후 우클릭 defaultPrevented=false native 보존·☰ 미개방·AC-5 버튼 클릭 menuRight==trigRight byte-동치·errCount 0. 우클릭=보편 확장 단축·기본 우클릭 양보·버튼 경로 무회귀 라이브 확정.

## REV-20260723T080415-floating-menu-close-fix [SUBAGENT:general-purpose] SHIP — floating 메뉴 닫힘 결함 수정(folderMenu 1급 승격) (TASK-20260723T080415-floating-menu-close-fix, Minor §12.3)
- 신고: universal-ctxmenu 후속 사용자 — 폴더 '···' 메뉴가 열린 뒤 바깥클릭/ESC 로 안 닫힘. 근본원인 = `closeFloatingMenus` 의 하드코딩 id 목록에 `folderMenu`(feature-0024) 누락(pre-existing drift, 우클릭 기능이 표면화).
- 적대적 프론트 리뷰(general-purpose, 코드+diff 판독) 6축(over/under-removal·dataset copy order·toggle/identity·trigger reset·broader callers). 판정: **SHIP** (BLOCKING/MAJOR 0). 검증 통과: `data-floating-menu` 는 openFloatingMenu 단일 지점에서만 set·closeFloatingMenus 단일 지점에서만 read(3개 메뉴 전부 이 primitive 경유 — over/under-removal 없음) · 마커 write 가 caller dataset copy 보다 선행하고 caller 키(folderId/conversationId/messageId)와 비충돌·역방향 leak 없음 · getElementById(id) 기반 toggle/identity 불변 · `.conv-folder-menu-trigger.is-open` 이 실제 부여 클래스와 정합(오히려 stale is-open/aria 영구잔존을 신규 복구).
- **[NIT ×3 — 리뷰 지적, folderMenu 1급 승격 정합으로 in-cycle fold-in]** ① `_attachShareRangeEsc`(8383) 열린-메뉴 가드에 folderMenu 미포함 → 공유범위 arm 중 폴더 메뉴 열고 ESC 시 공유범위까지 취소 → 가드에 folderMenu 추가. ② `_maybeSyncConversationListUnread`(11662) 7s 재렌더 skip 가드가 convItemMenu 만 → 폴더 메뉴 열림 중 재렌더로 트리거 detach(수정 후엔 body-mount 메뉴라 닫힘엔 무해하나 정합) → folderMenu 포함. ③ `styles.css` `.conv-folder-menu-trigger.is-open` keep-visible 규칙 부재 → 열림 중 포인터 이탈 시 '···' 페이드 → conv-item/말풍선과 동형으로 `opacity:1` 추가.
- 검증: `node --check app.js` PASS · CSS 균형 · POST-DEPLOY PB-0008(AC-1~5 폴더 메뉴 바깥클릭/ESC/scroll/토글 닫힘·무회귀). TEST fragment 20260723T080415-floating-menu-close-fix.

## REV-20260723T081500-floating-menu-close-fix-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — floating 메뉴 닫힘 결함 수정 배포 + 라이브 실측 (CHG-20260723T081500-floating-menu-close-fix-postverify)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료 기록). 정본 = REV-20260723T080415-floating-menu-close-fix([SUBAGENT:general-purpose] SHIP).
- 실증(win-browser Chrome 150, 배포본 57ecc758, https://localhost/): 서빙 app.js(stamp 8373a9f479e2) `data-floating-menu` 2 hit·css `.conv-folder-menu-trigger.is-open` 1 hit + 테스트 폴더(API 생성 id=6, 검증 후 삭제) 실 이벤트 — AC-1 바깥클릭·AC-2 ESC·AC-3 scroll·AC-4 토글 닫힘(+트리거 aria=false·is-open 제거)·AC-5 conv-item 무회귀·errCount 0. 폴더 '···' 메뉴가 정상 닫히고 트리거 상태 복원·타 메뉴 무회귀 라이브 확정 — 사용자 신고 결함 해소.
## REV-20260723T074530-reasoning-timeline [SUBAGENT:general-purpose] SHIP-WITH-FIXES — AI 운영 현황 > 추론 결함수정 전/후·답변개선 과정 가시화 (TASK-20260723T074530-reasoning-timeline, Major §12.3) — panel: frontend-ux-security + backend-qa
- Trigger: UI/화면·레이아웃 keyword matched → ux/design; API/endpoint·response shape keyword matched → backend/qa (§18.8). 적대 general-purpose 2명(프론트/UX/보안, 백엔드/QA) 병렬. 접근 A(기존 `redteam_reviews` 데이터 재구성 — 마이그레이션·계측·답변원문 저장 없음, AskUserQuestion 승인).
- **백엔드/QA panel — 결함 없음(6축 CLEAN)**: 컬럼 인덱스 r[14..16] 정합(0042 base 14 + 0043 3, writer INSERT 순서 일치)·stale-image `information_schema` 폴백·`_pg_connect_ro` autocommit 이라 감지 쿼리 실패가 트랜잭션 abort 안 함(이후 `_query_reviews` 재사용 안전)·회귀0(base 필드 byte-보존, cols 단일 계산으로 cursor/non-cursor 양 경로 정합)·응답계약(rederive 3필드 unconditional 세팅으로 error/폴백 경로도 KeyError 없음)·SQL injection 표면 0(cols=리터럴+bool 게이트, `%s` 바인딩).
  - **[hardening — 반영]** `include_rederive` default `True`→`False`(fail-safe): 유일 caller 가 `_has_rederive` 명시 전달하므로 동작 불변, 미래 caller 가 kwarg 생략해도 stale 이미지에서 UndefinedColumn 안 남.
  - [관찰 defer] 단위테스트 갭(include_rederive 분기·information_schema 감지는 라이브 PG 필요 → POST-DEPLOY 커버) · 기존 rollback 주석 cosmetic(autocommit no-op, 본 cycle 신규 아님·scope 밖).
- **프론트/UX/보안 panel — SHIP 아님 → BLOCK 1 + WARN 2 in-cycle 수정 후 SHIP-WITH-FIXES**. XSS(속성 보간 `esc` 적용·`href` encodeURIComponent·백엔드 axis/severity write sanitize 이중방어)·degrade(findings 비배열·필드 누락·rederive null 전 가드)·접근성(ol/li·aria-hidden·target/rel)·CSS(콘솔 LIGHT-ONLY 확인, 고정 hex 항상 흰 배경 대비 양호·클래스 충돌 0)·회귀(페이징/통계/노트 esc 체인 보존)·딥링크(기존 규약)는 CLEAN.
  - **[BLOCK — 수정 완료] B1** verdict=pass + WARN-only(BLOCK 0)를 단계③에서 "수정 실패·fail-open"으로 오표기 → 상단 "정상 통과"(초록) 배지와 정면 모순(운영자 "하자 초안 그대로 전달" 오독). RC = `hasDefect = verdict==='revise' || nBlock>0 || nWarn>0` 가 WARN 을 결함 취급. 백엔드 verdict 규약(`redteam.py`: BLOCK→revise, WARN-only→pass 자문 신호·수정 대상 아님) 반영: `hasBlock=(verdict==='revise'||nBlock>0)` 로 게이트, `warnOnly` 는 ②"통과 — 경고(자문) N건, 수정 불필요"·③"불필요 (경고성 자문 — 수정 대상 아님)"(na). 미해결 BLOCK(revise·revision_applied=false)만 ③"미적용(수정 실패, fail-open)". harness c7(WARN-only)·c8(미해결 BLOCK) 회귀 케이스 추가 PASS.
  - **[WARN — 수정 완료] W2** 축 집계가 "더 보기" 페이징 후 미갱신 → "현재 목록 N건" 라벨이 거짓(첫 페이지 값 고정). `adminState.reasoning.reviewsAll` 누적 + 페이징마다 `_reasoningAxisSummary` 재계산해 `#reasoningAxisSummaryWrap` 교체.
  - **[WARN — 수정 완료] W4** 단계② "결함 N건" 카운트를 findings severity 에서 일원화(파싱 실패 시만 block_count/warn_count 컬럼 폴백) → 손상 데이터에서 컬럼과의 내부 모순("0건 검출 (BLOCK X)") 방지.
  - **[WARN — 동기화 처리] W3** worktree base stale(cycle-init 시 main=e52e88fc, 이후 universal-ctxmenu PR #897 전진) → `git diff main` 에 무관 app.js 삭제가 stale 아티팩트. 랜딩 전 `git rebase origin/main` + app.js 무변경 확인(아래 Git 동기화 결과).
  - [NIT defer] 모든 링크 동일 문구 "대화 열기 ↗"(WCAG 2.4.4 문맥, 경미) — 후속.
- 재검증: 실제 소스 추출 harness **21/21 PASS**(5단계·rederive·강도 한글화·전후 대비·5축·재검증·pass/error·B1 c7·c8·sentinel·축 집계·XSS·null 안전) · `node --check`(ESM) · `py_compile`.
- 판단: additive read-only API + frontend 표시 재구성. 인증/인가/파괴적/스키마/RBAC/엔드포인트 무변경 → Critical 아님(Major). POST-DEPLOY PB-0008(Environment: Windows-browser, hard gate) 예정.

## REV-20260723T084235-reasoning-timeline-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — AI 운영 현황 > 추론 배포 + 라이브 시각검증 (CHG-20260723T084235-reasoning-timeline-postverify)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료 기록). 정본 = REV-20260723T074530-reasoning-timeline([SUBAGENT:general-purpose] SHIP-WITH-FIXES).
- 실증(Windows Chrome 150, 라이브 e4ef9384): 추론 탭 리뷰 30건 — 진행 타임라인 5단계(stages 150)·전후 대비 47·5축 집계(근거15/SQL6/완전성12/정직성14)·rederive "도구 재추론(SQL)"·대화 딥링크 30·통계 타일 6·pageerror 0. **W2 페이징 축 재계산 47→93** 확증. **B1** verdict pass 카드 "결함 없음—통과" 실렌더(WARN-only 오표기 없음). AC-1~6 라이브 확정.

## REV-20260724T010501-doc-sync-rn-0724 [SKIPPED:non-policy-doc] — 릴리즈노트 07-23 블록 신규 7항목(대화 폴더·탐색·관리 콘솔) (TASK-20260724T010501-doc-sync-rn-0724, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·완료형 정당성(7항목 전부 owning POST-DEPLOY 커밋으로 라이브 확증 — 폴더 9392cf51/e3fec503/0a1378f3/1a2f2595·날짜트리 8b384b8a·우클릭 b51f93e9·페이징 fce9ab2b/5d0f8467·추론타임라인 a17fd1a7·DB분석 6da5e621)·area(work 5·admin 2)·누출 회피는 doc_sync 가 정본(owning POST-DEPLOY 커밋 + git log aac76889..HEAD) 대비 직접 검증 + ULTRACODE 타깃별 적대 verify(wf_ded08a66 — RN major 1[graph-node-reveal 자체 POST-DEPLOY PB-0008 미기록 → 사용자 릴리즈노트 hold, 함정 #15] 반영·나머지 INCLUDE holds, cross-target cross-fault 회피 스코프).

## REV-20260724T012954-usage-model-canonical [SUBAGENT:general-purpose] SHIP (MINOR §12.3) — LLM 사용량 '모델별 비중' canonical 집계
- 위험도(§12.3): **Minor** — 읽기전용 분석/표시 집계 + 추정비용 정확화. 인증·인가·파괴적 데이터·마이그레이션·
  외부 비용 구조 변경 없음. admin.js(프론트)·스키마·엔드포인트 계약 무변경. AI 자율 진행 + 본 기록(§12.3).
- 근거(원인): `by_model` 등 사용량 집계가 `COALESCE(resolved_model, model)` 를 그대로 GROUP BY 해, litellm
  라우팅 변형 alias·실 모델 ID·gemma 폴백 실모델이 별도 세그먼트가 되어 한 논리 모델이 도넛을 분점.
  litellm_config.yaml 상 `claude-haiku-4*` 6개 alias 는 모두 anthropic/claude-haiku-4-5 로 라우팅됨을 확인.
- 결정: canonical family 를 SSOT(`shared/model_catalog.py`)에 두고 SQL/Python 양측이 동일 규칙 사용. 실
  서빙 모델 기준(COALESCE(resolved, model))을 유지(TASK-0163 의도 보존)하되 family 로 접음 = "실제 사용량".
- 대안 검토:
  1. 프론트(admin.js) JS 집계 — 기각: 백엔드 by_model/by_day_model/by_account 4곳 + 드릴다운 필터가 백엔드라
     프론트만으론 불완전, 색맵/칩/필터 전면 재작성 필요. 백엔드 canonical 이 프론트 무변경으로 정합.
  2. Python fold(SQL 은 raw 유지) — 기각: run_id distinct 가 canonical 그룹 횡단 시 과대계상, 드릴다운 필터가
     canonical↔raw 매핑 역질의 필요. SQL CASE(starts_with) 그룹핑이 run_id dedup·필터를 한 번에 정합 해결.
  3. LIKE 'x%' — 기각: 파라미터 쿼리(`_query_usage_conversations`)에서 '%' 이스케이프(%%) 필요, no-param
     쿼리와 이스케이프 불일치 footgun. PG `starts_with()` 로 '%' 자체를 제거해 양쪽 안전.
- 리스크/완화: (a) 실 서빙 모델 기준이라 gemma 폴백(haiku 요청→gemma 서빙)은 edge 로 계상 — TASK-0163 의
  기존 규약(resolved 우선)과 정합, 오히려 haiku 단가 과대계상 정정. (b) 미등록/신규 모델은 원본 유지(self-surface)
  로 조용히 사라지지 않음. (c) 프론트 드릴다운 클릭 키(canonical) ↔ 백엔드 필터(canonical) 정합을 test_c4·
  test_q2 로 회귀 가드. profile 도넛도 동일 canonical 화하여 공유 헬퍼(`_query_usage_conversations`) 필터
  변경으로 인한 profile 드릴다운 미매칭 회귀를 예방.
- 검증: 전체 pytest 2280 passed/2 skipped(baseline), 신규 test_c1~c4 + test_q2_model_filter 갱신. 실 PG(90일)
  실측 — 7 세그먼트 → 3 실제 모델(haiku 64.5M·edge 30.4M·sonnet 0.79M) 병합 확인. POST-DEPLOY PB-0008 예정.
- 완료 정합: 코드 변경은 백엔드 .py 만(html/templates/static 무변경) → §10.5 web/UI 트리거(check #13)
  하드 게이트 대상 아님. 다만 산출물이 렌더 도넛이므로 배포 후 라이브 시각검증(PB-0008)을 완료 근거로 첨부.
- Panel(§18.8): backend/qa/correctness 축 [SUBAGENT:general-purpose] 적대 리뷰 수행(diff + 실 소스 + 프론트
  admin.js 호환 + PG 버전 + canonical Python 런타임 실행 + 생성 SQL 문자열 실측). **Verdict: SHIP** —
  BLOCKING/MAJOR 0. 확인: 리터럴 `%` 0개(starts_with)로 param/no-param 쿼리 이스케이프 안전 · GROUP BY=SELECT
  동일 `_canon` 문자열/ordinal · ORDER BY pos 4→3 정정(model 컬럼 제거 shift) · **단가표 키가 canonical family
  키와 정확 일치**(실ID 형태였다면 전부 $0 되는 BLOCKING 이었을 지점 — 안전 확증) · 컬럼 인덱스 r[0..5] 정합 ·
  `_canon` 스코프 정의-후-사용 보장 · 프론트 라운드트립(도넛 라벨=canonical → 클릭 → 백엔드 canonical 필터 매칭) ·
  run_id canonical 그룹 dedup(과대계상 없음, 오히려 완화) · profile 드릴다운 미스매치 회귀 없음.
- Findings fold-in (전부 의도된 동작/ pre-existing — 코드 수정 불요):
  · [MINOR] 사용량 상세표의 "alias → resolved" 화살표는 model==resolved_model 이라 미렌더 — canonical 통일의
    의도된 결과(패널이 "실제 모델 기준"으로 전환). req→resolved 추적은 AI 운영 관제 activity 피드(ai_ops)가 보존.
  · [MINOR·pre-existing] 'edge' 세그먼트 드릴다운은 `conversation_id IS NOT NULL` 강제라 비대화 insight/worker
    usage 가 빈/부분 결과일 수 있음(도넛=전체 vs 드릴=대화귀속분 의미차, canonical 이 edge 를 단일 큰 세그먼트로
    합쳐 더 두드러짐). 코드 결함 아님 — 정직한 표현.
  · [NIT·범위 밖] `ai_ops.py:319` task×model 은 raw GROUP BY 유지(운영 관제 activity 패널). category 롤업이라
    raw granularity 미노출·per-category 비용은 canonical 단가 계상 → 가시 불일치 없음. follow-up(§8.1) 기록.
  · [NIT] SQL(ELSE NULL/'') vs Python('(미상)') 빈값 divergence — model NOT NULL + COALESCE 로 도달 불가(주석 명시).

## REV-20260724T020632-aiops-model-canonical [SUBAGENT:general-purpose] SHIP-WITH-FIXES (MINOR §12.3) — '운영 현황' 서브탭 모델 canonical 정합 (usage-model-canonical 후속)
- 위험도(§12.3): Minor — 읽기전용 표시/집계 정합. 인증·인가·데이터·마이그레이션·계약 변경 없음.
- 범위: 사용자 요청("나머지 범위 또한 실제값과 정합"). 직전 PR#914 가 남긴 유일 raw 모델 그룹핑 = ai_ops('운영 현황').
- 변경: (1) categories 집계 canonical GROUP BY, (2) 활동 feed 주 배지 canonical(req/resolved raw 보존).
- **적대 리뷰(general-purpose) verdict = SHIP-WITH-FIXES → 지적 3건 전부 반영 후 SHIP**:
  · **M1 (MAJOR, 반영)**: `admin.js:2208` 상세 폴백 `srvM = r.resolved_model || r.model` 이 이번에 canonical 화된
    `r.model` 을 끌어와, `resolved_model=NULL` + 비-canonical `req_model`(예 `auto`·보조 task/pre-migration 행)에서
    상세에 **날조된 라우팅 화살표(`auto → edge`)** 를 생성(cycle 의 "상세=raw audit·손실 없음" 계약 위반 — 손실
    아닌 날조). **수정**: `srvM = r.resolved_model || r.req_model` (canonical `r.model` 미참조 → 상세 100% raw).
    resolved NULL 이면 srvM=reqM → 화살표 소거(변경 전 동작 복원), resolved 존재 시 실 라우팅 유지. **실 Windows
    Chrome(win-browser eval) 4시나리오 확증**: 정상변형·gemma폴백=실화살표 / NULL+auto=`auto`(날조 없음) / NULL+haiku=단일.
  · **m1 (MINOR, 반영)**: categories "출력 불변/byte-동일" 주장 정정 — calls/total_tokens 는 정수 sum 이라 완전
    불변이나, cost 는 `_estimate` 가 호출마다 round(…,4) 하여 raw 다중그룹→canonical 단일그룹 재결합 시 최하위
    4번째 소수(≈$0.0001)에서 미세 변동 가능(단일 round 라 오히려 더 정확). ai_ops.py 주석 + 문서 톤다운.
  · **m2 (MINOR, 반영)**: NULL-resolved+비canonical req 케이스 백엔드 회귀 테스트 추가
    (test_query_activity_null_resolved_badge_canonical_raw_preserved) — 배지=canonical('edge'), req=raw'auto',
    resolved=None 유지. unknown passthrough 는 기존 test_c2(merged)로 커버.
- 리뷰 통과 항목: SQL `GROUP BY task,2` ordinal=CASE 정합·starts_with %-이스케이프 안전 / SSOT(Python↔SQL 규칙
  동일) / 비용 일관(배지 canonical ↔ _estimate 내부 canonical) / 정보 복구(resolved 존재 시 라우팅 완전 표시) /
  두 엔드포인트(/ai-ops·/ai-ops/activity) 배지 일관 · categories try/except degrade 온전.
- 검증: 전체 pytest 2287 passed/2 skipped · admin.js `node --check` · Windows-browser modelDetail eval PASS ·
  POST-DEPLOY PB-0008(운영 현황 배지·활동 상세 라우팅 라이브) = 배포 후 후속(test-runs.d fragment).
## REV-20260724T181106-brandnew-script-attachment [AGENT-TEAM: security+backend] SHIP-WITH-FIXES — §18.8 Verification Panel
- **Trigger**: 새 첨부 쓰기 경로(INSERT WebConversationAttachments) + 프롬프트 변경 → dispatch 키워드 `schema/query`(→backend+qa) + 새 write/RBAC 표면(→security); 프롬프트 변경=full-panel default. 렌즈: security, backend correctness.
- **[AGENT-TEAM: security] MAJOR(반영)**: 신규 source-less 경로가 `conversation.attachment.upload.own/any` 권한 미검사 → `conversation.ask`만 가진 주체(또는 그 scope API 토큰)가 첨부 업로드를 우회 생성(편집 경로는 source 소유권으로 간접 게이팅). **Fix**: `_materialize_assistant_attachment_new` 최상단 `_account_can_access_conversation` 업로드 권한 게이트(권한 없으면 skip, 수동 업로드 엔드포인트와 동일). / **검증-SAFE(REFUTED)**: 확장자 allowlist·이중확장자(x.exe.sql→x_exe.sql)·경로traversal·leading-dot·IDOR(account/conv 서버바인딩)·SQL injection(parametrized)·크기/개수 캡·kind/MIME(비클라이언트)·strip parity 전부 방어 확인.
- **[AGENT-TEAM: backend] MINOR(반영)**: (1) 프론트 배지 v1 신규를 "AI 수정"으로 오표기 → "AI 생성"/"AI 수정" 구분(app.js). (2) turn당 개수 cap 편집+신규 이중카운팅(실질 10) → 공유 예산(remaining_count) 합산 ≤5. (3) span 파서 리팩터: 한 블록 본문에 상대 태그 fence-start 줄 포함 시 조기종료(실트리거 ≈0 for SQL/CSV) → 코멘트 정직화 + 회귀 테스트(test_p6)로 동작 고정(더 흔한 공존 케이스 보존 트레이드오프). / **검증-SAFE(REFUTED)**: root INSERT(RootAttachmentId=NULL·v1·UNIQUE NULL-distinct)·history 칩 렌더(message_id display-space 정합)·fail-open·step_index(편집 뒤 +1 충돌無)·mirror/audit 시그니처 전부 확인.
- **판정**: SHIP-WITH-FIXES → 전 findings in-cycle 반영. 보안 회귀 0(가드 불변 + 업로드 권한 게이트 추가). 잔여 라이브 실측=POST-DEPLOY PB-0008(동일입력 재현으로 거부 소멸 확인).
## REV-20260724T180649-share-point-rail-bars [SKIPPED:trivial-display-only-port-of-reviewed-main] — 공유링크 뷰 rail 막대화 + 클릭 비례 (Minor §12.3 — feature-0003 web/UI, /_template:entry 후속)
- Panel skip 사유(§18.8): 메인 뷰 A(막대화)+B(클릭 위치 비례)를 공유 뷰(share.js/share.css)에 **동형 이식** — 원본은 REV-20260722T125200-point-rail-range-window([SUBAGENT:general-purpose]) 적대리뷰 + 라이브 PB-0008 PASS 완료분. 차이는 좌표계뿐(messageLog 내부 스크롤 → window/문서 스크롤): `layoutSharePointRail` topInDoc=rect.top+scrollY·totalHeight=documentElement.scrollHeight·`scrollShareMessageToRatio` window.scrollTo. 백엔드·엔드포인트·RBAC·스키마 0, 순수 표시+간단 인터랙션. anonymous 노출면이나 dot.title/aria-label 은 기존 DOM API(innerHTML 아님) 유지 — XSS 무첨가.
- `scrollShareMessageIntoCenter`(항상 중앙) 는 제거하지 않고 유지(향후 재사용·메인 대칭). 윈도잉(C)은 공유 뷰 범위 밖(read-only 스냅샷·페이징 없음) — 미적용.
## REV-20260724T085937-sonnet-reasoning-budget-guide [SUBAGENT:adversarial-general-purpose] SHIP-WITH-FIXES — '모델별 추론 예산' adaptive(Sonnet 5) 죽은 budget 슬라이더 제거 + guide-note (CHG-20260724T085937, Minor §12.3, cross-feature 정본 feature-0003+shared)
- Trigger(§18.8): shared/runtime_settings.py(spec 생성 필터) + admin UI(사용자 대면) 변경 → 적대 리뷰 1렌즈(general-purpose, 6 공격각 A~F). 판정 **SHIP-WITH-FIXES** — BLOCKER/MAJOR 0.
- **Finding D (MINOR-latent) 반영·수정**: `_budget_thinking_models()` 필터가 `!= "adaptive"` 였는데, 이는 style=None 미상/미래 claude(예: claude-opus-4-8; model_catalog 가 미상 claude 를 안전하게 None 분류)를 budget 스펙에 **포함** → agent_core `_call_llm` 이 None 스타일엔 budget_tokens 를 주입 안 하므로 **똑같은 죽은 슬라이더가 재발**(게다가 `_adaptive_thinking_models` 는 `== "adaptive"` 라 guide-note 도 없음). **수정**: 필터를 `== "budget"`(agent_core budget 분기와 동형)로 변경 → budget 계열만 ②③ 노출, 미상 claude 는 ①(총 출력 live)만·죽은 컨트롤 0. 현 카탈로그(sonnet=adaptive/haiku=budget)에선 결과 동일(haiku-only)이라 무회귀, 미래 재발만 봉인.
- **Finding A/B (MINOR-inert) 수용**: 변경 전 저장됐을 수 있는 sonnet budget override DB 행은 이제 orphan — but 완전 inert(‌`validate_value`→spec None 로 override 로드에서 제외·`serialize_registry` 는 list_specs 만 순회·override resolver 는 spec None 단락 → 누출/크래시 0, 리뷰 A/B 확증). 잔여 wart: DELETE 가 미등록 키 400 이라 UI 로 리셋 불가(UI 는 guide-note 라 reset 버튼 자체 없음)하나 inert 하므로 수용(정리 마이그레이션 불요 — 필요 시 운영자 직접 DB 삭제). REPORT/MODIFY 기록.
- 공격각 CLEAN: A(PUT/validate — 제거 키 400, 테스트 커버), C(프론트 — `adaptive_models` Array 가드·textContent XSS-safe·① 유지·중복렌더 없음), C2(빈 sliderRows forEach no-op), E(테스트 non-vacuous — len==3·sonnet not in·haiku live 20000·clamp 62976/default 5000 실측 일치), F(agent_max_output:claude-sonnet-4 spec·`_call_llm` max_tokens 계약 보존).
- 검증: 수정 후 feature-0002 test_runtime_settings 39/39 + feature-0003 test_runtime_settings_api RC=0. POST-DEPLOY PB-0008(sonnet 카드 guide-note·haiku 슬라이더) 예정.
- Cross-ref: CHG/TASK/TEST-20260724T085937-sonnet-reasoning-budget-guide · shared/feature-0002 MODIFY 동일 slug · subagent id a77c815ebdf2d791f · ANCHOR 0003 무충돌.

## REV-20260724T183000-share-point-rail-bars-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 공유링크 라이브 검증 기록
- Panel skip 사유(§18.8): 코드 0(문서 전용 POST-DEPLOY 실증). 구현 리뷰 정본 = REV-20260724T180649-share-point-rail-bars([SKIPPED:trivial-display-only-port-of-reviewed-main]). 배포(c1358190)+공유링크 라이브 실측(막대·클릭 비례) append 만.
## REV-20260724T180458-sql-md-highlight [SUBAGENT: SHIP — 6/6축 PASS · BLOCK/MAJOR 0 · 보안·정합성 결함 0] assistant markdown SQL 코드블록 구문 하이라이트 (Minor §12.3, frontend-only)
- **[SUBAGENT] 적대 패널 판정 (§18.8, 보안+프론트 렌즈, 정적분석 + 경험적 테스트 — jsdom 주입 열거 + node ReDoS 1.12M자)**: **VERDICT SHIP**. ① XSS PASS — 토큰 텍스트 `textContent`/`createTextNode` 전용, `tpl.innerHTML` 직렬화가 `<>&` 엔티티 이스케이프 → 주입 payload(`'<img onerror>'`·`</code></pre><script>`·백틱-`</span><script>`·`'"><iframe srcdoc>`) 전부 PRE/CODE/SPAN + `class="sql-tok-*"` 로만 물질화, 금지 태그/속성 0; span class 는 하드코딩 상수(포징 불가); DOMPurify 최종 backstop 유지. ② ReDoS/토크나이저 PASS — unrolled-loop 문자열 패턴(선형)·lazy 블록주석·zero-width 매치 없음(전 분기 ≥1자 소비 + `[\s\S]` fallback)·200k~1.12M자 입력 0.4~64ms 선형·무한루프 없음·미종결 문자열/주석 graceful. ③ 회귀/disjoint PASS — lang 게이트 early-return 로 diff/mermaid/attachment/인라인/plain 무영향, `[class*='language-']` 오탐 없음(`(?:^|\s)language-` 경계), 체인 순서 양파일 정합. ④ 텍스트 무손실 PASS — 전 테스트 100% round-trip(스크립트/`&<>"`/비ASCII/CRLF/탭/이스케이프따옴표/`.5`/`1e`), 트레일링 `\n` strip 은 enhanceDiffBlocks 관례와 동일. ⑤ app.js↔share.js PASS — 마스터 정규식 byte-identical, 함수/Set 동치(차이=app.js 한국어 주석 3줄뿐). ⑥ CSS PASS — 토큰 규칙 `pre.sql-block .sql-tok-*` 이중 조건이라 non-SQL bleed 없음, 사용자 말풍선 override specificity 정합.
- **잔여(수정 안 함 — 코스메틱·text-safe)**: NIT — comment 토큰 `#737aa2`/`#1a1b26` 대비 ≈4.1:1(기존 `.diff-meta` 와 동일 페어 재사용, 의도적 de-emphasis). MINOR(coverage 한계, 결함 아님) — PostgreSQL `$$…$$` dollar-quoted·MySQL `#` 라인주석 미토큰화 시 내부가 일반 SQL 로 색칠될 수 있음(텍스트·안전 무영향, 순수 오색칠). `#` 는 코드 주석에 이미 명시, `$$` 는 향후 확장 여지.
- **결정**: 외부 syntax highlighter 라이브러리(highlight.js/prism) 도입 대신, 기존 `enhanceDiffBlocks`/`enhanceAttachmentEditBlocks` 와 동일한 code-block post-processor 패턴의 경량 토크나이저 `enhanceSqlBlocks` 를 추가한다.
- **대안 검토**:
  - (A) highlight.js/prism vendor 추가 → 번들 크기(+수십~수백KB)·CSP/오프라인 정합·theme CSS 추가 부담·과잉. 서비스가 쓰는 SQL 방언(MySQL/T-SQL/PG) 한정이면 경량 커스텀으로 충분. **불채택**.
  - (B) marked 커스텀 renderer 로 코드 하이라이트 → marked 버전/renderer API 결합 증가, 기존 enhance 체인과 이질. **불채택**.
  - (C) **경량 토크나이저 post-processor(채택)** — 기존 패턴 정합, 의존성 0, 방언 공통 예약어/타입 세트 + `(`휴리스틱 함수 인식. app.js/share.js 로컬 복제는 diff/attachment 선례와 동일.
- **리스크·완화**:
  - XSS: 토큰 텍스트를 `textContent` 로만 span 에 주입(innerHTML 미사용) + 체인 말미 DOMPurify.sanitize 이중 방어. headless 라이브 DOM 실측으로 `<script>/<img>/on*` 0·alert 미발화 확증.
  - ReDoS: 문자열/백틱 토큰을 linear(비-backtrack) 형태(`'[^']*(?:''[^']*)*'`)로, 블록주석은 lazy 로 작성.
  - 방언 충돌: MySQL `#` 라인주석은 T-SQL `#temp` 식별자와 충돌하므로 미지원(`--`,`/* */` 만) — 색만 안 입고 깨지지 않음(무손실).
  - 회귀: lang 필터로 diff/mermaid/attachment/비-SQL/인라인 코드와 disjoint 확인(headless 23/23).
- **테마**: `.message-content pre` 는 라이트/다크 무관 항상 다크(#1a1b26 / share #1e293b)라 diff-block 과 동일 Tokyo Night 팔레트를 재사용, 테마 분기 불필요. 사용자 말풍선(primary 색 위)에 sql 블록이 실릴 경우만 배경을 다크로 고정해 대비 보장.
- **검증**: headless chromium 실 vendor 파이프라인 23/23 PASS · node --check PASS · 시각증거 캡처. POST-DEPLOY PB-0008 라이브(Windows-browser) = 배포 후 정본.

## REV-20260724T184500-sql-md-highlight-postverify [SKIPPED:non-policy-doc] SQL 하이라이트 POST-DEPLOY 라이브 실증 + deploy_scope 근거 기록
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록). 실 구현 리뷰 정본 = REV-20260724T180458-sql-md-highlight([SUBAGENT] 6/6축 SHIP·BLOCK/MAJOR 0). 본 cycle 은 배포(0313b135) 라이브 실측 + §12.2 배포 근거 기록만.
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 cycle-final(PR #946 머지, main 0313b135) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. 첫 배포 직전 "deploy_scope: included 활성" 1줄 표면화 완료. 배포=web-a/web-b one-at-a-time 롤링·90s soak 통과·caddy no-drift·롤백 0.
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: 실 Windows Chrome/150 배포본 `markdownToHtml` eval → sql-tok 26토큰·getComputedStyle Tokyo Night 팔레트 정확(keyword #bb9af7/600·func #7aa2f7·string #9ece6a·number #ff9e64·comment #737aa2·pre #1a1b26)·텍스트 무손실·script 주입 0·콘솔 에러 0. test-runs.d POST-DEPLOY 결과 + evidence/pb0008-sql-highlight-live-20260724.png.

## REV-20260727T010501-doc-sync-rn-0727 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-07-24 블록(대화·공유·관리 UX 8항목) doc_sync 정합
- **changeset (operational, feature-0003)**: `src/static/release-notes-data.js`(2026-07-24 블록 prepend·generated 갱신) + companion `docs/{TASK,MODIFY,FUNCTION,TEST}.md`. 비-정책 doc-only(렌더 로직·제품 코드·스키마·RBAC 0).
- **[SKIPPED:non-policy-doc] 사유**: 사용자향 릴리즈노트 콘텐츠 데이터만(제품 코드·정책 무변경). §18.8 패널 불요(29ef0baf 등 선례 동일 토큰).
- **검증**: `node --check` PASS · vm 구조검증(releases +1·head 8항목·이전 블록 보존·스키마 type/area/title/detail·내부용어 누출 0). 8항목 전부 owning POST-DEPLOY PB-0008 라이브검증(sql 35d6453f·csv 8bf643e0·reanswer 28ec78b3·newfolder f697eddf·share-scroll 5c9d5bf2·share-rail 6290ae1e·metadata-review c7e928c8·graph-emoji 791d5761). ULTRACODE 적대검증 wf_2676a918 — RN confirmed·minor 1(graph-emoji 문구 3종 그레이스케일 정합) fold-in.
- **cache-buster**: `?v=dev` 고정(빌드 자동주입·index/admin 편집 0·수동 bump 폐지 ITEM-09).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).

## REV-20260727T102027-sql-diff-highlight [SUBAGENT: SHIP-WITH-FIXES — MAJOR(FP)+MINOR 3건 in-cycle 수정, 6축 나머지 PASS] ```diff``` 코드블록 내 SQL 구문 하이라이트 (Minor §12.3, frontend-only)
- **[SUBAGENT] 적대 패널 판정 (§18.8, 보안+프론트, 경험적 실행 검증)**: **VERDICT SHIP-WITH-FIXES**. 1 XSS PASS(sqlTokenizeToFragment 는 createElement/textContent/createTextNode 전용·appendChild 는 안전노드 이동·innerHTML sink 무첨가·DOMPurify 최종) · 2 refactor 등가성 PASS(sqlTokenizeToFragment 추출+thin highlightSqlInto, 트레일링개행 strip 정위치, ```sql 무회귀) · 3 **MAJOR(FP)+MINOR(FN)** · 4 diff 구조 PASS(+MINOR hunk 토큰화) · 5 CSS PASS(+MINOR 2: hunk/meta 색·user-bubble parity) · 6 app/share drift PASS(line-for-line).
- **in-cycle 수정 반영**:
  - **[MAJOR Finding 3 — looksLikeSql 오탐] 수정**: verb∧clause(bare FROM 의존) 게이트가 `import…from`+`.delete()/.create()/.update()`·`Object.values()` 등 ORM/코드 관용구를 SQL 오탐. → **실제 SQL statement '모양' 앵커**로 재작성(`SELECT…FROM`(JSX `<select>` negative lookbehind 배제)·`INSERT INTO`·`UPDATE <tbl>…SET`·`DELETE FROM`·`(CREATE|ALTER|DROP) (TABLE|VIEW|…)`·`TRUNCATE`·`MERGE INTO`·`GRANT/REVOKE…ON`·`WITH cte AS (`). 리뷰 지적 FP 6종(TypeORM/JS/Python/Object.values/JSX/Dockerfile) 전부 false, 실제 SQL 13종(whereless UPDATE·CTE 포함) 전부 true 로 실측 확인.
  - **[MINOR Finding 4 — hunk/meta 토큰화] 수정**: 토큰화를 내용 라인(diff-add/del/ctx)으로 한정 — hunk(`@@`)·meta 라인 미토큰화.
  - **[MINOR Finding 5 — CSS] 수정**: `.diff-sql .diff-line` 색 override 에 `:not(.diff-hunk):not(.diff-meta)` 추가(hunk 파랑·meta 회색 고유색 유지) + `.message.is-user .message-content pre.diff-block.diff-sql { background:#1a1b26 }`(사용자 말풍선 SQL diff 다크 배경 parity).
  - **[MINOR Finding 3 — FN]**: `SELECT NOW()`(FROM 없음) 등 일부 미탐은 benign(색 미적용, 텍스트·안전 무손상) — 잔존 허용.
- **잔여(수정 안 함)**: NIT — looksLikeSql/tokenizer 전용 단위테스트 부재(기존 browser-helper 관례, headless 검증으로 대체). 잔여 초희귀 FP(예: `<select>`+import 가 lookbehind 우회하는 변형)도 consequence=benign 오색칠뿐(안전·무손실 불변).
- **결정 근거**: 외부 하이라이터 무추가·기존 enhanceDiffBlocks 패턴 정합·additive(비-SQL diff 무영향). add/del 신호는 배경·border·gutter 로 유지(color-only override 라 border/::before 불변).
- **검증**: headless chromium(chromium-1208, 실 vendor marked+DOMPurify, app.js 추출 실소스) **22/22 PASS**(회귀·SQL diff 토큰·add/del 보존·평문 기본색·배경 tint·gutter·텍스트 무손실·비-SQL diff 무영향·게이트 오탐0·hunk 미토큰화·XSS 무력화) · `node --check` · 시각증거 evidence/sql-diff-highlight-20260727.png. POST-DEPLOY PB-0008(Windows-browser) = 배포 후 정본.

## REV-20260727T110000-sql-diff-highlight-postverify [SKIPPED:non-policy-doc] SQL diff 하이라이트 POST-DEPLOY 라이브 실증 + deploy_scope 근거
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 기록). 실 구현 리뷰 정본 = REV-20260727T102027-sql-diff-highlight([SUBAGENT] SHIP-WITH-FIXES·MAJOR+MINOR3 in-cycle 수정).
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 PR #948 머지(main 8d69490c) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. "deploy_scope: included 활성" 1줄 표면화 완료. 배포=web-a/web-b 8d69490c 롤링 재생성·healthy·RestartCount 0(롤백 0).
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: 실 Windows Chrome/150 배포본 markdownToHtml eval(SQL diff) → diff-sql·sql-tok 9개·getComputedStyle Tokyo Night 색 정확(keyword #bb9af7·string #9ece6a·number #ff9e64)·평문 기본색 #c0caf5·add/del 배경 tint·hunk 미토큰화·gutter 보존·script 0·콘솔 에러 0. test-runs.d POST-DEPLOY 결과 + evidence/pb0008-sql-diff-live-20260727.png.

## REV-20260727T113640-model-persist [SUBAGENT: SHIP-WITH-FIXES — 2라운드 모두 BLOCK, 지적 10건(B1·C1~C4 / B-B·C-A~C-D) 전건 in-cycle 수정] 대화별 "마지막 요청 모델" 보존 + '+ 새 대화'=haiku (Minor §12.3, web/UI + backend additive)
- **[SUBAGENT] 적대 패널 (§18.8, security+backend+qa+ux 4렌즈, 실 소스 추적 검증)** — 2라운드 수행. 두 라운드 모두 **BLOCK** 판정을 받았고 전건 수정 후 재검증했다.
- **1R BLOCK 지적 → 수정**:
  - **B1(high) 랜딩·로그아웃 경로 미커버**: 본 변경이 `state.selectedModel` 을 "명시 클릭으로만 설정" → "대화 로드마다 서버값으로 설정" 으로 바꿔, 대화 삭제/보관/나가기 후 랜딩 및 로그아웃→재로그인(페이지 리로드 없음) 시 직전 대화(직전 **계정**)의 모델이 다음 신규 대화 요청에 실림. → `_resetComposerModelSelection(state)` 신설 + 이탈 경로 4곳 적용.
  - **C1(med) 대화 전환 대기 창**: `activeConversationId` 는 바뀌었으나 hydration 전인 창에서 전송하면 직전 대화 모델이 **대상 대화 KV 에 영구 저장**. → `selectConversation` 에서 전환 즉시 리셋.
  - **C2(med) 기본값 영구 고정**: 웹은 선택기 미상호작용에도 항상 `model` 을 실어 보내므로 모든 대화가 "첫 전송 시점 기본값"에 pin → 이후 기본 모델 상향이 기존 대화에 영원히 미반영. → **기본값 이탈만 저장**(같으면 빈 값으로 해제).
  - **C3(med) 그룹 대화 누출**: 대화 단위 키면 멤버 A 의 선택이 B 의 composer 를 바꾸고 **B 의 토큰 한도로 청구**. → KV 키를 `model:<account_id>` 로 계정별 분리 + `_display_window == "DENY"` 시 미반환.
  - **C4(med) 테스트 위양성**: ask 하네스가 `_is_allowed_api_model`/`_is_safe_model_name` 을 patch 해 무력화(저장이 검증 게이트 위로 올라가는 회귀 미검출), S3 mirror 검출기가 두 조건 모두 false 라 vacuous. → patch 제거 + A1c(거부 alias 400 & KV 미도달)·H2c/H2d 추가, 검출기 재작성 + **S3b 대조군**(추론 강도 미러는 실제 검출되어야 함).
- **2R BLOCK 지적 → 수정** (1R 수정이 만든 회귀 포함):
  - **B-B(med, 자체 회귀) 랜딩 재로드가 미전송 선택 삭제**: `loadHistory` 활성대화없음 분기는 "이탈"이 아니라 랜딩/pending 에 **머무는 동안 반복 호출**되는 재렌더 경로 — 무조건 리셋이 '+ 새 대화'에서 고른 뒤 아직 안 보낸 선택을 사이드바 일괄삭제·제품 롤백 등에서 조용히 삭제. → hydration 경로와 동일 가드 적용(`!_modelHydrationShouldSkip(state, "")`) + R3b/R4/R5 회귀 테스트.
  - **C-A(med) `moveConversationToFolder` hydration 공백**: `loadConversations` 만 호출해 `activeConversationId` 가 hydration 없이 재지정 → 다음 전송이 그 대화의 저장 모델을 기본값으로 clobber. → 폴더 이동 후 `loadHistory()` 추가 + **클래스 차원 가드** `_shouldSendModelField(state, targetConvId, isLazyCreate)`: 신규 대화 / 이 대화에서 명시 선택 / 이 대화 hydration 완료 중 하나일 때만 `askBody.model` 동봉(그 외 생략 → 서버가 기존 저장값 보존).
  - **C-B(med) 최종 fallback 리터럴**: `_composerCurrentModel` 말단 안전망이 `"claude-sonnet-4"` — 카탈로그 로드 실패 시 "새 대화는 haiku" 계약과 반대로 상위 모델 전송. → `"claude-haiku-4"`(서버 `API_DEFAULT_MODEL` 과 동일)로 정정. 나머지 chain 발산은 위 clobber 가드가 흡수.
  - **C-C(low) 열린 메뉴 하위 재렌더**: 매 로드마다 `_renderComposerModelMenu()` innerHTML 재생성 → 열린 상태에서 hover·클릭 대상 노드 교체. → 메뉴가 보일 때만 재렌더(사이드바 unread sync 의 열린-메뉴 skip 과 동일 패턴).
  - **C-D(low) `model:unknown` 공유 슬롯**: 계정 식별 불가 호출자들이 한 키를 공유 → 계정별 분리로 막으려던 것을 재현. → **fail-closed**(빈 키 반환, 저장·복원 모두 skip) + H2e.
  - **B-A(critical, process) 스테이징 누락 지적**: 리뷰어가 index 를 본 시점이 `git add` 전이라 1R 코드가 staged 로 보인 **타이밍 아티팩트**. 현재 10 파일 전부 staged 확증(`git show :…` 마커 grep — `_model_kv_key` 4·`_resetComposerModelSelection` 6·테스트 13(→14)·`index.html` placeholder 1). 지적 자체는 타당한 절차 리스크라 커밋 직전 재확인을 관례로 채택.
- **잔여(수정 안 함 — 문서화)**:
  - **C5 / fix_with_ai 는 기본 모델로 실행**: 'AI 로 고치기'는 model 없이 재dispatch 되므로 정정 run 이 대화의 선택 모델이 아닌 기본값으로 실행된다. 저장값은 덮어쓰지 않으므로(AC-MP-4) 사용자 선택은 보존된다. **본 cycle 에서 바꾸지 않는 근거는 "선존 동작" 만이 아니다 — 계정별 키 도입으로 "그 대화의 모델" 이 더 이상 단일 사실이 아니게 되어, 서버 주도 정정 run 이 어느 멤버의 선호를 택할지가 모호하다. 배포 기본값을 쓰는 편이 오히려 정합적**(리뷰어 §3 수용).
  - **AC-MP-7(b) 기본값 통과 시 명시 선택 해제**: 이탈-인코딩의 알려진 성질. AC 에 명시해 다음 리뷰가 재논쟁하지 않게 고정.
- **결정 근거**: 추론 강도 선택기(대화별 KV + `/api/history` hydration)의 검증된 구조를 재사용하되 **로컬 미러는 의도적으로 두지 않는다** — 미러가 있으면 새 대화가 직전 모델을 상속해 사용자 요구("'+ 새 대화'는 haiku")를 정면으로 깬다. 이 비대칭이 B1 의 근원이기도 했다(미러가 랜딩 상태를 무해하게 만들어 주던 안전망이 모델에는 없었다) → 리셋 헬퍼가 그 자리를 대신한다.
- **대안 검토**: (A) localStorage 미러 — 사용자 요구 위반, 불채택. (B) 대화 단위 단일 키 — 그룹 대화 교차 오염(C3), 불채택. (C) 요청 model 원문 저장 — 기본값 영구 pin(C2), 불채택. (D) **계정별 키 + 기본값-이탈 저장 + 전송 clobber 가드(채택)**.
- **검증**: `test_model_persist.py` 14 PASS · `verify_model_persist.mjs` 32 PASS · `node --check`/`py_compile`/ruff PASS · `make test` 전체 회귀 0(선존 FAIL 4건은 clean main 84f2e5ab 에서 동일 재현 확인 — 본 변경 무관). POST-DEPLOY PB-0008(Windows-browser) = 배포 후 정본.
- Human Approval Needed: no (Minor §12.3 — 스키마/RBAC/엔드포인트 0, additive 응답 필드 1개).

## REV-20260727T124500-model-persist-postverify [SKIPPED:non-policy-doc] model-persist POST-DEPLOY 라이브 실증 + deploy_scope 근거
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록 + 스크린샷 증거). 실 구현 리뷰 정본 = REV-20260727T113640-model-persist([SUBAGENT] 2라운드 BLOCK → 지적 10건 전건 수정).
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 PR #953 머지(main **8cfa00b0**) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. "deploy_scope: included 활성 — 이후 자동 배포" 1줄 표면화 완료. 배포 범위 = web 전용(변경 파일이 web 라우터·정적 자산 한정, 워커/agent 코드 무변경).
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: AC-MP-1(재로드 복원 — `payload.model=claude-sonnet-4` 서버 왕복 + 라벨 `claude-sonnet`)·AC-MP-2(대화 간 격리·복귀)·AC-MP-3('+ 새 대화'=`claude-haiku`) **PASS**, 시각 증거 2건(`docs/evidence/pb0008-model-persist-{restore,newconv}-20260727.png`). **AC-MP-9 는 라이브 미검증** — 유발 트리거(일괄 삭제·실패 롤백)가 라이브 테넌트에서 파괴적/유발 불가라 단위검증(R3b/R4/R5)만으로 커버하고 그 사실을 test-runs.d 에 명시했다(미수행을 검증으로 오인 금지).
- **부수 확인(선존 동작, 본 변경 무관)**: 인자 없는 새로고침은 `initializeWorkspace` 가 직전 대화를 자동 선택하지 않는 기존 설계(`allowCurrentFallback=false`)라 빈 화면으로 시작한다. 사용자 표현 "새로고침" 의 실질 충족 경로는 (a) deep-link 재로드 즉시 복원 (b) 재로드 후 대화 재진입 시 복원이며 양쪽 모두 PASS.
- Human Approval Needed: no.

## REV-20260727T160748-product-picker-scroll [SKIPPED:session-policy-no-subagent] 제품 선택 드롭업 선택 항목 중앙 스크롤 (Minor §12.3, frontend-only)
- **Panel 처리(§18.8) — 정직 표기**: dispatch 표상 UI/화면/레이아웃 키워드 매칭(ux·design) 대상이나, **본 세션은 사용자 환경 정책으로 subagent(Agent tool) 호출이 금지**되어 [SUBAGENT] 패널을 수행하지 못했다. 대체로 (a) 실 chromium 레이아웃 위 헤드리스 검증 11 케이스(경계·무간섭·무예외 포함)와 (b) 아래 자체 적대 검토(H1~H8)를 수행했다. **패널 미수행 사실을 "검증함"으로 오인하지 않는다** — 다음 cycle 에서 패널 재개 시 본 변경을 대상에 포함할 수 있다.
- **변경 요지**: `scrollProductDropupToSelected(menu)` 신설 + `openProductDropup()`·`renderProductChip()`(열린-상태 재렌더) 2곳 호출 + 검색 입력 `focus({preventScroll:true})`. 계산식 `scrollTop = clamp(selected.offsetTop - (menu.clientHeight - selected.offsetHeight)/2, 0, scrollHeight-clientHeight)`.
- **자체 적대 검토(H1~H8)**:
  - **H1 (재렌더 점프)**: `renderProductChip()` 은 컴포저 상태 갱신 경로(L6658 busy 동기화 등)에서 자주 호출된다 — 메뉴가 열린 채 재렌더되면 위치가 이동한다. 단 이는 **pre-existing**: 재렌더가 항목 DOM 을 새로 만들어 `scrollTop` 이 이미 0(최상단)으로 리셋되므로, 본 변경은 "최상단 점프"를 "선택 항목 중앙 복원"으로 바꿀 뿐 새 점프를 만들지 않는다(요청 취지에 부합). 사용자가 스크롤해 다른 제품을 훑던 중의 위치 손실은 재렌더 자체가 원인이며 본 cycle 범위 밖(개선 여지로 기록).
  - **H2 (검색 필터와의 상호작용)**: `filterProductDropupItems` 는 항목을 `hidden` 토글만 하고 스크롤을 만지지 않는다. 필터로 `scrollHeight` 가 줄면 브라우저가 `scrollTop` 을 자동 clamp 하므로 "빈 영역만 보이는" 상태가 생기지 않는다(결과가 뷰포트보다 짧으면 0). 필터 후 재정렬은 하지 않는다 — 검색 중 커서/포커스를 방해하지 않기 위함(의도).
  - **H3 (`preventScroll` 미지원)**: 옵션 객체를 무시하는 구형 엔진에서는 포커스가 스크롤을 유발할 수 있으나, **포커스 → 중앙 정렬 순서**라 마지막 설정이 이긴다. 예외는 `try/catch` 로 이미 감싸져 있다.
  - **H4 (다중 `.is-selected`)**: `buildProductDropupItem` 은 view-only 그룹을 항상 `selected:false` 로 만들고, auto/pinned 중 하나만 selected 다. `querySelector`(첫 매칭)로 충분하며 오탐 없음.
  - **H5 (숨김 상태 호출)**: `.hidden`(display:none) 상태면 `offsetTop`/`clientHeight` 가 0 이라 `scrollTop=0` — 무해한 no-op. 호출 2곳 모두 표시 상태(`hidden` 제거 후 / `aria-expanded="true"`)라 실제로는 발생하지 않는다.
  - **H6 (좌표계 가정)**: `offsetTop` 은 `offsetParent` 기준이므로 메뉴가 `position:absolute` 여야 `scrollTop` 과 같은 기준이 된다 — 가정을 헤드리스 T1 이 **실측 assert**(`sel.offsetParent === menu`)한다. sticky 검색 wrap 은 항목의 조상이 아니라 형제라 무관(T2b 가 검색칸 유무 양 경로 확인).
  - **H7 (성능)**: 레이아웃 읽기 1회 + `querySelector` 1회, 메뉴 open 시점 한정. 강제 reflow 비용은 이미 발생하는 렌더 경로 안이라 체감 영향 없음.
  - **H8 (접근성·모션)**: 즉시 스크롤이라 애니메이션 없음(reduced-motion 무관). 포커스는 검색칸에 유지되고 DOM/ARIA 를 바꾸지 않아 스크린리더 흐름 무변경.
- **결정 근거**: `scrollIntoView({block:"center"})` 는 한 줄로 끝나지만 **조상 스크롤 컨테이너(페이지/messageLog)까지 스크롤**해 컴포저 주변 화면이 튄다 — 메뉴 자신의 `scrollTop` 만 계산·설정하는 편이 부작용 표면이 좁다. 선택 항목이 없을 때(=auto) 스크롤을 건드리지 않는 것도 의도 — auto 는 목록 최상단 근처라 기존 동작이 이미 최적이며, 불필요한 스크롤 변경을 만들지 않는다.
- **검증**: `tests/headless/verify_product_dropup_scroll.py` **11/11 PASS**(chromium 145, 실 app.js 함수 원문 + 실 styles.css) · `node --check app.js` PASS · 시각 증거 `docs/evidence/product-dropup-scroll-{before,after}-20260727.png`(before=최상단·선택 항목 미표시 / after=선택 항목 중앙). POST-DEPLOY PB-0008(Windows-browser) = 배포 후 정본.
- **스키마/RBAC/백엔드**: 0. Human Approval Needed: no (Minor §12.3).

## REV-20260727T163000-product-picker-scroll-ci-fix [SKIPPED:test-harness-rename-no-runtime-change] 헤드리스 검증 스크립트 rename (CI 수집 회피)
- **Panel skip 사유(§18.8)**: 런타임 코드 변경 0 — 검증 하네스 파일명 rename + 문서 경로 참조 갱신뿐(`src/**` 무변경). 실 구현 리뷰 정본 = REV-20260727T160748-product-picker-scroll.
- **문제**: 신규 검증 스크립트가 `test_` prefix 라 CI pytest 가 수집 → 러너 playwright 부재로 collection error(exit 2) → test job FAIL. **본 cycle 이 직접 유발한 red 이므로 무관 flake 로 분류하지 않고 즉시 수정**했다.
- **수정**: `verify_` prefix 로 rename(프로젝트 `tests/verify_*.mjs` 관례와 동일). 헤드리스 검증은 명시 호출 전용이며, CI 는 pytest 단위테스트만 게이트한다는 기존 계약을 존중한다(헤드리스/브라우저 검증은 로컬·PB-0008 축).
- **대안 검토**: (A) CI 에 playwright 설치 — 러너 시간·유지비 증가, 본 cycle 범위 밖. (B) 파일 상단 `pytest.importorskip` — 수집은 계속 일어나 취약. (C) **rename(채택)** — 수집 자체를 회피, 관례 정합.
- **검증**: rename 후 11/11 PASS 재확인 · ruff PASS · pyproject 에 `python_files` 커스텀 없음 확인(기본 패턴만 수집).
- Human Approval Needed: no.

## REV-20260727T165500-product-picker-scroll-postverify [SKIPPED:non-policy-doc] 제품 선택 드롭업 중앙 스크롤 POST-DEPLOY 라이브 실증 + deploy_scope 근거
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 기록 + 스크린샷 증거). 실 구현 리뷰 정본 = REV-20260727T160748-product-picker-scroll([SKIPPED:session-policy-no-subagent] — 세션 정책상 subagent 패널 미수행, 헤드리스 11 케이스 + 자체 적대 검토 H1~H8 로 대체).
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 PR #955 머지(main **b30bb45d**) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. "deploy_scope: included 활성 — 이후 자동 배포" 1줄 표면화 완료. 배포 범위 = web 전용(변경 파일이 정적 자산·문서 한정, 워커/agent 코드 무변경). soak 통과(edge 일시 blip 1회 — 연속 3회 미만 회복, 롤백 0).
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: AC-PPSC-1(중앙 정렬 — centerDelta **0**, scrollTop 254 가 clamp 경계 밖이라 실제 정렬임을 확증)·AC-PPSC-2(양단 clamp — 마지막 항목 선택 시 scrollTop=maxScroll=447, fullyVisible)·AC-PPSC-3(검색 포커스 유지) **PASS**, `offsetParentIsMenu=true` 좌표계 계약 라이브 실측, 페이지 에러 0. 시각 증거 `docs/evidence/pb0008-product-picker-scroll-live-20260727.png`(선택 제품이 목록 한가운데 + 위아래 이웃 제품 동시 노출 — 사용자가 요청한 "상대적인 위치" 파악이 실제로 가능해짐).
- **검증 위생**: 라이브 테넌트 부작용 최소화 — 대화 미선택(랜딩) 상태에서만 제품을 바꿔 owner PATCH 경로를 타지 않게 했고(로컬 pref 만), 검증 후 원래 선택(KR_LIVE)으로 복원 + `win-browser.py down` 으로 드라이버 인스턴스만 종료.
- Human Approval Needed: no.

## REV-20260727T180036-share-bar-layout [SKIPPED:session-policy-no-subagent] 공유 대화 뷰 액션/조회수 재배치 + 바 hover 확장
- Trigger: UI/button/layout/버튼·레이아웃 keyword matched → §18.8 표상 `ux, design` subset 대상.
- **Panel skip 사유(§18.8)**: 본 세션의 사용자 환경 정책이 "Do not call the AgentTool unless the user requested it" 로 subagent 호출을 금지하고 사용자 요청도 없었다. 동일 상황의 선례(REV-20260727T160748-product-picker-scroll)와 같은 처리이며, 대체 검증으로 **헤드리스 chromium 실 레이아웃 8 케이스 + 구조 회귀 5 케이스 + 자체 적대 검토(아래 H1~H7)** 를 수행했다. 미수행을 "검증함"으로 오인하지 않도록 여기에 명시한다.
- **판단 근거**:
  - **액션 그룹 전체 이동(참여/로그인 포함)**: 사용자 원문은 `['링크 복사','내 계정에서 fork']` 2종만 지목했으나, 같은 컨테이너의 나머지 2종(참여·로그인 링크)은 **조건부 노출(hidden)** 이라 사용자 화면에 안 보였을 뿐 성격이 동일한 조작이다. 2종만 옮기면 같은 액션군이 상·하로 쪼개져 일관성이 깨지므로 그룹 전체를 이동했다(요청 확대가 아니라 요청의 자연 경계 적용). 이 판단을 TASK/FUNCTION 에 명시.
  - **바 높이 보존 방식**: 사용자 추가 요청("기존 크기 거의 유지, 필요 시 hover 확장")에 대해 (a) 버튼 규격 축소로 기본 높이를 유지하고 (b) hover/focus 에서만 확장하는 2단 구성을 택했다. `height` 대신 `padding` 을 전이시켜 fixed 바의 리플로우 범위를 줄였다.
  - **접근성 보강(자율 판단)**: `:hover` 만 두면 키보드 사용자는 확장 없이 2px 패딩 버튼을 조작하게 되므로 `:focus-within` 을 함께 걸었고, hover 개념이 없는 터치 환경(`@media (hover:none)`)은 확장 규격을 상시 적용해 타겟 크기를 확보했다. `prefers-reduced-motion` 은 크기 변화는 유지하되 애니메이션만 끈다(기능 손실 없이 모션만 제거).
- **자체 적대 검토(H1~H7, 전건 반영·확인)**:
  - H1 하단 바가 커져 마지막 메시지를 가리는가 → `.share-container` padding-bottom 80px ≥ hover 확장 높이 52.5px, 헤드리스 T7 로 고정.
  - H2 `@media print` 가 헤더 기준으로 `.share-actions` 를 숨겼는데 이동 후 무력화되는가 → 셀렉터가 클래스 기반이라 유효, 이제 `.share-footer` 숨김과 이중 적용(인쇄물에 버튼 미노출 유지).
  - H3 조회수가 `.share-meta-item:empty{display:none}` 규칙에 걸려 안 보이는가 → `share.js` 가 항상 `조회 N회` 를 채우므로 비지 않는다(값 0 도 "조회 0회").
  - H4 우측 스크롤 rail(`.share-point-rail`, z-index 50)이 높아진 바에 가려지는가 → rail z-index 가 footer(10)보다 높아 위에 그려지고 dot 클릭 유지(기존과 동일 관계).
  - H5 좁은 화면에서 버튼이 안내문과 겹치는가 → `flex-wrap:wrap` + 600px 이하에서 안내문 100% 폭 + 액션 우측 정렬로 2줄 분리, 모바일 하단 여백 96px.
  - H6 hover 확장이 커서 아래 콘텐츠를 덮어 클릭을 가로채는가 → 확장분 17px 은 바 자체 영역 내부이고, 확장 트리거가 바 hover 라 커서는 이미 바 위에 있다(콘텐츠 클릭 경로 무간섭).
  - H7 `share.js` 가 DOM 위치에 의존하는가 → `getElementById` 4곳 + 이벤트 바인딩만이며 부모/형제 탐색 없음(`grep` 확인). 구조 이동에 안전.
- **검증**: 구조 회귀 `tests/test_share_bar_layout.py` 5 PASS · 헤드리스 레이아웃 `tests/headless/verify_share_bar_layout.py` **8/8 PASS**(T4 바 높이 35.0→35.2px Δ+0.2 · T5 hover 52.5px · T6 transition 0.18s · T8 버튼 31.5px) · `make test` 전체 실패 15건이 clean main baseline 과 **차집합 0**(회귀 없음) · ruff PASS. 시각 증거 `docs/evidence/share-bar-layout-{before,after,hover}-20260727.png`.
- **검증 환경 정직 기록**: 위는 모두 헤드리스/정적 검증이다. `visual_verification_scope: always`(FIRST_REQUEST.md) 에 따른 **Windows-browser(PB-0008) 라이브 검증은 배포 후 수행**한다 — 정적 자산이 컨테이너 이미지에 포함돼 미배포 코드로는 실 화면 실측이 불가하기 때문(선례와 동일 순서).
- Human Approval Needed: no (Minor §12.3 — 비파괴 frontend 배치 변경).

## REV-20260727T182000-share-bar-layout-postverify [SKIPPED:non-policy-doc] 공유 대화 뷰 하단 바 레이아웃 POST-DEPLOY 라이브 실증 + deploy_scope 근거
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 기록 + 스크린샷 증거 4건). 실 구현 리뷰 정본 = REV-20260727T180036-share-bar-layout([SKIPPED:session-policy-no-subagent] — 헤드리스 8 + 구조 5 + 자체 적대 검토 H1~H7 로 대체).
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 PR #958 머지(main **486a587c**) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. "deploy_scope: included 활성 — 이후 자동 배포" 1줄 표면화 완료(원 cycle 세션). 배포 범위 = web 전용(변경 파일이 정적 자산·문서 한정, 워커/agent 코드 무변경). Caddyfile 무변경으로 caddy blip 0, post-cutover soak 90s 통과, 롤백 0.
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: AC-SBL-1(액션 4종 하단 바 우측 — 바 우측 여백 16px, 안내문보다 오른쪽, 헤더 잔존 액션 0)·AC-SBL-2(`조회 16회` 헤더 `.share-meta` 4번째, y=96 < 바 y=801)·AC-SBL-3(기본 바 높이 **35px** — 변경 전 35.0px 대비 체감 동일)·AC-SBL-4(hover 시 **53px** + 패딩 6→10px + 상단 그림자 + 배경 불투명, `transition … 0.18s`) **전부 PASS**. 추가로 `링크 복사` → `복사됨 ✓`(class `is-copied`) 토글, 최하단 스크롤에서 마지막 메시지 미가림(bottom 732 < 바 top 783), 버튼 `elementFromPoint` hit-test 통과, 페이지 에러 0. 시각 증거 `docs/evidence/pb0008-share-bar-layout-live-{default,hover,header,copied}-20260727.png`.
- **검증 시점 배포본 주의(정직 기록)**: 검증 중 다른 cycle 이 PR #959 를 배포해 서빙 SHA 가 486a587c → **66575331** 로 전진했다. `git merge-base --is-ancestor 486a587c 66575331` 로 본 변경이 서빙본에 포함됨을 확인한 뒤 실측했으므로 검증은 유효하며, 오히려 최신 배포본 기준 실증이다.
- **검증 위생**: fork(신규 대화 생성)·참여(그룹 멤버십 변경) 는 라이브 부작용을 피해 **클릭하지 않고** 노출·좌표·hit-test 로만 확인 — 본 cycle 변경이 HTML 구조 이동 + CSS 뿐이고 `share.js` 무변경이라 클릭 핸들러 자체는 회귀 대상이 아니다(구조 회귀 테스트 L3 가 id·배선 보존을 이미 게이트). 검증 후 `win-browser.py down` 으로 드라이버 인스턴스만 종료.
- Human Approval Needed: no.

## REV-20260727T234439-model-picker-copy [SKIPPED:session-policy-no-subagent] — PASS
- 대상: 모델 선택기 중복 문자열 제거 + 설명 축약 + `word-break: keep-all`. CHG-20260727T234439-model-picker-copy 정합.
- 리뷰 방식([SKIPPED] 사유): §18.8 subagent 패널은 **본 세션의 사용자 환경 정책(Agent tool 미허용)** 으로 미수행. 대체 검증 = 실 Windows 브라우저 **BEFORE/AFTER 정량 실측**(줄 수·문자 수·배지 수·메뉴 높이) + 전체 pytest rc=0 + `node --check` + 아래 자기 적대 검토. 변경면이 표시 문자열 3개·JS 조건 1줄·CSS 1속성이라 정적 패널의 추가 판별력이 낮다.
- 자기 적대 검토:
  - *배지를 무조건 제거하지 않은 이유*: `group` 은 provider 혼재 카탈로그(Local LLM `auto`/`edge`/`core`/`code`)에서 실제 구분 기능을 한다. 지금 무의미한 건 "label 이 이미 group 명으로 시작할 때"뿐이므로 그 조건에서만 생략한다 — 미래에 비-Claude provider 가 카탈로그에 들어오면 배지가 자동으로 다시 살아난다(하드코딩 제거였다면 그때 회귀).
  - *`keep-all` 이 과한가*: 아니다. 문구 단축은 "지금 이 문구·이 폭"에서만 성립하는 완화이고, 근본 원인(한국어 음절 단위 줄바꿈)은 남는다. 두 조치는 중복이 아니라 계층이 다르다.
  - *정보 손실*: "Anthropic"·"Claude"·"frontier" 는 label·배지·형제 행에서 이미 알 수 있는 정보라 제거해도 변별력이 줄지 않는다. 오히려 세 행을 **같은 축**(성능 등급 · 용도)으로 맞춰 비교가 쉬워졌다.
  - *값 오염 없음*: `value`(claude-opus-5 등)는 저장 대화·단가·runtime_settings 키라 손대지 않았다. description 은 표시 전용.
- 위험도: Minor(§12.3) — 표시 문자열·CSS. RBAC·라우팅·스키마 0.
- Verification: PRE-COMMIT Windows-browser 실측 PASS(2줄→1줄, 배지 3→0) · pytest rc=0 · node --check OK. POST-DEPLOY 배포본 육안 재확인 예정.
- Cross-ref: MODIFY CHG-20260727T234439-model-picker-copy / test-runs.d/20260727T234439-model-picker-copy.md.

## REV-20260728T010301-doc-sync-rn-0728 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-07-27 블록에 3항목 append(답변 모델·공유뷰·관계도) doc_sync 정합
- **changeset (operational, feature-0003)**: `src/static/release-notes-data.js`(기존 2026-07-27 블록 3항목 append·summary 증강·generated 불변) + companion `docs/{TASK,MODIFY,FUNCTION,TEST}.md`. 비-정책 doc-only(렌더 로직·제품 코드·스키마·RBAC 0).
- **[SKIPPED:non-policy-doc] 사유**: 사용자향 릴리즈노트 콘텐츠 데이터만(제품 코드·정책 무변경). §18.8 패널 불요(351ed406 등 선례 동일 토큰).
- **검증**: `node --check` PASS · vm 구조검증(releases[0] 2026-07-27 items 4→7·releases[1] 2026-07-24 8항목 보존·스키마·enum·내부용어 누출 0). 3항목 전부 owning POST-DEPLOY PB-0008 라이브검증(opus5 413703b9·share-bar 486a587c/2ec5e0aa·detail-db-groups 66575331/42ee04d0). 릴리즈노트 render 테스트 jsdom 미설치로 미실행(render 로직 미변경). ULTRACODE 적대검증 wf_c9bea2de — RN 3항목 CONTENT confirmed·verifier 가 초안 07-28 date framing REJECT→07-27 append 로 정정(제외 4건: model-picker-copy 미배포·change-reanalysis 백엔드·false-truncation unverified-live·feature-0026 측정전용).
- **cache-buster**: `?v=dev` 고정(빌드 자동주입·index/admin 편집 0·수동 bump 폐지 ITEM-09; wrapper 헤더 수기 bump 지시는 07-12 이전 regime 부적용).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).

## REV-20260728T024258-model-access-rbac [SKIPPED:session-policy-no-subagent] — PASS
- 대상: 계정/역할별 LLM 모델 사용 권한(동적 `model.access.<value>` RBAC). CHG-20260728T024258-model-access-rbac 정합. **Critical §12.3 — 인가 구조 변경, 사용자 승인 후 착수**(설계 3안 제시 → "전부 기본 부여" 채택).
- 리뷰 방식([SKIPPED] 사유): §18.8 subagent 패널은 본 세션의 사용자 환경 정책(Agent tool 미허용)으로 미수행. 대체 = **인가 판정표를 테스트로 전수 고정**(25 케이스, 판정 5분기 + 경계 4종) + 전체 회귀 rc=0 + ruff + 아래 자기 적대 검토. Critical 등급이므로 검토 항목을 공격각 단위로 나열한다.
- **자기 적대 검토 (공격각 8)**:
  1. *게이트 우회 — 다른 진입점으로 model 을 넣을 수 있나?* 클라이언트 지정 model 경로를 전수 grep: `/api/ask` 의 `data.get("model")` 과 재답변(`_reanswer`)의 forward 뿐이며 후자는 `ask()` 재dispatch 로 동일 게이트를 재통과한다. 저장된 대화 모델 hydration(L256)은 **표시 전용**이고 실제 요청은 다시 ask() 를 탄다. → 단일 choke-point 성립.
  2. *conn 없이 호출해 fail-open 분기를 탈 수 있나?* `conn=None` 이면 row 등록 여부를 확인할 수 없으므로 **미보유는 거부**로 닫았다(G4). fail-open 은 conn 이 있고 "row 가 실제로 없다" 를 확인했을 때만.
  3. *fail-open 이 너무 넓은가?* 두 경우(row 미등록 / 조회 예외)로 한정하고 둘 다 WARNING 을 남긴다. 대안(전원 차단)은 신규 배포 첫 요청부터 모든 대화 403 — 통제 목적보다 큰 사고. 관측 가능성으로 보완.
  4. *재배포가 관리자의 해제를 되살리나?* ← **가장 위험한 조용한 실패**. 제품 권한의 무조건 re-grant 패턴을 그대로 베끼면 발생한다. `rowcount>0` one-time 마커로 차단하고 G7 이 회귀를 고정한다.
  5. *API 토큰이 게이트를 우회하나?* scope 면제는 **positive allowlist 축만** 면제이고 `bool(granted)`·절대 denylist·ask() 게이트는 그대로 AND 로 남는다(G6 3케이스). 저권한 서비스 계정에서 해제하면 토큰도 차단.
  6. *표시 필터가 새 실패 모드를 만드나?* 전부 차단 시 원본 유지 + WARNING — 빈 선택기(사용자에겐 "로딩 중")로 원인 불명 상태를 만들지 않는다. 표시를 관대하게 둬도 집행은 ask() 가 담당하므로 인가 누출 아님.
  7. *400/403 축이 섞이나?* 카탈로그 밖 model 은 본 게이트가 True 를 주고 `_is_allowed_api_model` 이 400 을 낸다(G2). 같은 실패가 두 갈래 메시지로 갈리지 않는다.
  8. *프론트 변경이 기존 그룹을 깨나?* `excludeDynamic` 조건을 **좁히기만** 했다(`is_dynamic` → `is_dynamic && group==='product_access'`) — 제품 경로는 동일 분기를 그대로 타고, 전체 회귀 rc=0 이 뒷받침한다.
- **잔여 위험(정직 표기)**:
  - **POST-DEPLOY 미검증** — 권한 grid 의 모델 row 렌더·'모두 적용' 왕복·해제 후 403/선택기 소멸은 배포 후 PB-0008 로 확인해야 한다(부트스트랩 seed 선행 필요라 사전 검증 불가). 배포 직후 수행 + 기록 예정.
  - **모델별 quota 는 범위 밖** — 본 cycle 은 "선택 가능/불가" 이진 통제다. "역할별 opus 월 N 토큰" 같은 상한은 기존 `quota` 그룹(LLM 사용 한도) 축이라 별 cycle.
- 위험도: **Critical(§12.3 인가 구조 변경)**. 완화: 스키마·마이그레이션 0(기존 테이블 재사용) · 기본 전 부여로 배포 무회귀 · 신규 권한은 운영 권한 묶음(관리 콘솔 접근과 무관) · fail-closed 기본.
- Verification: 단위 25 PASS · 전체 pytest rc=0 · ruff All passed · node --check OK.
- Cross-ref: MODIFY CHG-20260728T024258-model-access-rbac / test-runs.d/20260728T024258-model-access-rbac.md / SECURITY §28 / CONVENTIONS §10.6 / feature-0007 REPORT §7 R2.

## REV-20260728T025614-model-access-seed-fix [SKIPPED:live-root-cause-confirmed+session-policy-no-subagent] — PASS
- 대상: 모델 권한 seed SQL arity 수정 + 컬럼 길이 클립 + 호출부 격리. CHG-20260728T025614-model-access-seed-fix 정합.
- 리뷰 방식([SKIPPED] 사유): 근본 원인이 **라이브 로그 + 컨테이너 내 직접 호출 재현**으로 결정적으로 확정됐고(추정 아님), 수정은 파라미터 1개 바인딩 + 클립 2줄 + try/except 2곳이다. §18.8 subagent 패널은 세션 정책(Agent tool 미허용)으로 미수행.
- **배운 것(이번 cycle 의 핵심 교훈)**: 테스트 더블이 **실 드라이버의 계약을 흉내내지 않으면 단위 테스트가 통과 도장을 찍어준다**. 25개 테스트가 전부 green 이었는데 라이브에서 seed 가 한 번도 성공하지 못했다 — 더블이 SQL 문자열만 보고 arity 를 안 봤기 때문이다. 수정은 버그 자체보다 **더블에 그 검사를 심는 것**이 본질이다(그래서 arity 단정을 두 더블 모두에 넣었다).
- 자기 적대 검토:
  - *fail-open 설계가 결함을 가렸나?* 부분적으로 그렇다 — 403 폭주가 없어 즉시 드러나지 않았다. 그러나 대안(fail-closed)이었다면 이 버그가 **전 사용자 대화 403** 으로 터졌다. 설계는 옳았고, 부족한 것은 **seed 성공 여부의 능동 확인**이었다(POST-DEPLOY 체크리스트에 권한 row 카운트를 추가해 보완).
  - *격리가 실패를 숨기나?* try/except 는 예외를 삼키지만 stderr 에 `seed FAILED` 를 loud 하게 남기고, POST-DEPLOY 가 권한 row 수를 직접 센다. "조용한 skip" 은 남지 않는다.
  - *클립이 의미를 잘라 오해를 만드나?* Label 은 `모델 사용 — <label>` 로 짧고, Description 은 문장 끝이 잘릴 수 있으나 권한의 식별·판단은 Code/Label 로 하며 grid 는 Description 을 보조로만 쓴다. 1406 으로 seed 전체가 죽는 것보다 낫다.
- 위험도: Minor(§12.3) — 선행 Critical cycle 의 버그 수정. 인가 판정 로직·경계 무변경(seed 경로만).
- Verification: 단위 26 PASS · 전체 pytest rc=0 · ruff · ast.parse OK.
- Cross-ref: MODIFY CHG-20260728T025614-model-access-seed-fix / test-runs.d/20260728T025614-model-access-seed-fix.md / 선행 REV-20260728T024258-model-access-rbac.

## REV-20260728T031500-model-access-postverify [SKIPPED:post-deploy-live-evidence+docs-only] — PASS
- 대상: 배포 `8db72012` 의 모델 권한 RBAC 라이브 부여·해제 양방향 검증 기록 + `SECURITY §28.6` 신설.
- 리뷰 방식([SKIPPED] 사유): **코드 변경 0**. 산출물은 (a) 라이브 관측 사실, (b) 그 관측에서 드러난 기존 가드의 상호작용을 운영 규칙으로 옮긴 문서. 정본 적대 리뷰는 선행 REV-20260728T024258-model-access-rbac · REV-20260728T025614-model-access-seed-fix.
- **확정된 것**: ① 기본 전부 부여 무회귀 렌더 ② 역할 해제가 대상 모델에만 적용(`7/8`, 타 모델 `8/8` 유지) ③ 표시 필터 + `/api/ask` **403**, 동시점 sonnet **200** 대조로 **모델 단위 스코프** 확정 ④ 재부여 완전 복귀(`8/8` ×3, override 0). → 선행 REVIEW 들이 POST-DEPLOY 로 이관했던 시각·집행 게이트(§16.6) 충족.
- **새로 드러난 것(정직 표기)**: TASK-0300 권한상승 가드 × `model.access.*` = **관리자 자기 잠금 경로**. 결함이 아니라 기존 가드가 새 동적 그룹에 그대로 적용된 결과(=`product.access.*` 와 동일)이므로 **코드 변경 없이** `SECURITY §28.6` 운영 규칙으로 봉인. 완화하려고 가드에 예외를 두면 escalation 방어에 구멍이 생기므로 **의도적으로 하지 않았다**.
- **검증 방법의 한계(정직 표기)**: 집행 검증은 `일반 사용자` 역할에 소속 계정이 0명이라 **자기 계정 override** 로 대리 수행했다. 역할 경유 집행(계정 → 역할 → 권한)의 라이브 관측은 아니지만, 두 경로는 `_account_permissions` 의 동일 병합 맵으로 수렴하고 역할 쓰기 경로는 ②·④ 에서 DB 로 별도 확정했다.
- 위험도: **Minor(§12.3)** — 문서 전용, 동작 영향 0. 라이브 상태는 착수 전과 동일하게 원복됨.
- Cross-ref: MODIFY CHG-20260728T031500-model-access-postverify / test-runs.d/20260728T031500-model-access-pb0008.md / SECURITY §28.6·§28.7 / feature-0007 REPORT §7 (R1·R2 해소).

## REV-20260728T113819-usage-records-system [SKIPPED:session-policy-no-subagent] — PASS

CHG-20260728T113819-usage-records-system. §18.8 dispatch 키워드(UI/화면/API)에 해당하나 본 세션
정책상 subagent panel 미호출 — 대신 라이브 DB 실측 + PB-0008 로 대체 검증했다. Critical 아님
(읽기 전용 집계 확장 · 신규 RBAC 0 · 마이그레이션 0).

### D1. 시스템 기록을 "여집합" 으로 정의한 이유

`conversation_id IS NULL OR LIKE '__%'` 같은 **열거식** 정의도 가능했으나, 대화 목록이 실제로
쓰는 필터는 `INNER JOIN + owner NOT NULL` 이라 열거식과 미묘하게 어긋난다. 실측에서 그 틈이
드러났다 — 예약 sentinel `__ask_worker__` 가 `core_conversations` 에 **실제 행으로 존재**하고
(topic 까지 있음, owner NULL), 반대로 삭제된 대화 id 를 참조하는 usage 도 있다. 따라서
`NOT(joinable AND owner NOT NULL)` 라는 **정확한 여집합**으로 정의해 두 목록의 합이 항상 차트
막대와 일치하도록 했다. 라이브 검증: 897 + 14,476 = 15,373 = 전체(누락·중복 0).

### D2. 계정/일반 역할 클릭에서 시스템 사용분을 **제외**한 이유

시스템 호출은 계정에 귀속되지 않으므로 특정 계정 몫에 섞어 보이면 그 계정이 쓴 것처럼 오도한다.
`(시스템)` 역할과 모델/일자(무-귀속 차원) 클릭에서만 노출한다. 이 규칙은 백엔드에 고정하고
프론트가 재해석하지 않는다.

### D3. target→데이터소스 해소를 "추측하지 않는다"

`llm_usage.target` 에는 데이터소스 차원이 없다(0032 설계). 3 소스 union 으로 역해소하면 실측
8,399 distinct target 중 유일 해소가 대략 60% 대이고 나머지는 dev/qa 동명 스키마로 **모호**하다.
모호할 때 임의로 하나를 고르면 사용자를 **엉뚱한 데이터소스로 착지**시키므로, 후보 2+ 는
`scope_ambiguous` 로 표시하고 화면까지만 이동한다(행에 "(데이터소스 여럿 — 화면까지 이동)" 명시).
근본 해소는 `llm_usage` 에 데이터소스 컬럼을 추가하는 별도 cycle 이 필요 — 본 cycle 범위 밖으로
남기고 REPORT §후속에 기록.

### D4. nav 를 백엔드 SSOT 로 둔 이유

`task → 화면` 매핑을 프론트에 두면 신규 AI 작업이 생길 때 두 곳을 동기화해야 하고, 누락 시
"클릭해도 아무 일이 없는" 조용한 회귀가 된다. `shared/model_catalog.USAGE_TASK_NAV` 한 줄 추가로
목록·내비게이션에 동시 편입되도록 하고, 미등록 task 는 taxonomy self-surface 와 같은 사상으로
AI 운영 현황 폴백을 준다.

### D5. 응답을 `items` + `system_items` 로 **분리**(단일 배열 통합 아님)

기존 `items` 스키마를 그대로 두면 profile 모달·기존 소비자 회귀가 0 이고, 프론트 배포 순서와
무관하게 호환된다(구 프론트는 새 필드 무시, 신 프론트는 필드 부재를 빈 배열로 폴백). 표시 단계의
통합(한 표·토큰 순 병합)은 프론트에서 수행한다.

### 라이브에서 잡은 결함 2건 (in-cycle 수정)

- **모호 신호 유실**: `scope_ambiguous` 를 record 최상위에만 넣고 `nav` 에 싣지 않아, nav 만 읽는
  프론트에서 "데이터소스 여럿" 안내가 조용히 사라졌다(107행이 무표기). → nav 에 동반 + 회귀 가드 테스트.
- **깨진 대화 링크 위험**: 비-sentinel actor 를 무조건 대화로 링크하면 **삭제된 대화**로 404 를
  보낸다. → `bool_or(c.conversation_id IS NOT NULL)` 로 실재 여부를 판정해 3분기.

### 리스크·한계

- `_USAGE_SYS_LIMIT = 200` 상한 — 초과 시 truncated 안내. 대화 목록 상한(200)과 동일 규모.
- 해소 질의는 표시분(≤200행)의 스키마 IN 목록으로 제한 — 유계 비용(실측 14ms).
- 관리자 대비 대비비는 실측 PASS 이나, **다크 테마 대비는 미실측**(본 콘솔은 라이트 기준 운용).
