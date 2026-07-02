---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---


# Modify Log

## CHG-20260702T193000-aiops-conv-link-fix (TASK-20260702-aiops-conv-link-fix — AI 운영 현황 '최근 활동' 상세 시스템 sentinel 대화 링크 깨짐 수정, Minor §12.3 — feature-0003 프론트 단독)
- Date: 2026-07-02 (worktree ai/claude/feature-0003-aiops-conv-link-fix, base 4ec15191). TASK-20260702-audit-nav-ux 후속.
- 트리거: audit-nav-ux(bc2a0fa6) 배포 후 PB-0008 라이브 검증 적발 — '최근 활동' 상세 '연결 대화' 가 insight/ask 워커·자율 호출(활동 대부분)에도 `/?conversation=__insight_worker__` 등 열 수 없는 링크 렌더.
- 근본원인: `__insight_worker__`·`__ask_worker__`·`__global__`·`__kb_manual__`(shared/config.py·kb_ingest.py) 등 예약 sentinel(전부 `__` 접두)은 실제 대화 아님인데 `conversation_id != NULL` 이라 `aiOpsActivityRowsHtml` 이 링크로 처리.
- 변경(`src/static/admin.js`): `isSysConv = cid && cid.slice(0,2)==="__"` 가드 추가 — sentinel=안내(sentinel id 표기)·링크 없음, 실 사용자 대화(비-`__`)=`/?conversation=<id>` 링크 유지, NULL=기존 일반 안내. `src/static/admin.html` cache-buster `admin.js?v=20260702-aiops-conv-link-fix`.
- 비변경: 백엔드(`_query_activity`·엔드포인트)·스키마·RBAC·마이그 0. conversation_id 페이로드는 audit-nav-ux 그대로.
- 검증: node --check PASS · make test(백엔드 무변경 회귀) · PB-0008 재검증(배포 후).


## CHG-20260702T190000-audit-nav-ux (TASK-20260702-audit-nav-ux — 감사 카테고리 순서 재구성 + 항목 툴팁 + AI 운영 현황 '최근 활동' 클릭 상세 확장, Minor §12.3 — feature-0003 프론트 UI + 읽기전용 additive 백엔드, 비파괴)
- Date: 2026-07-02 (worktree ai/claude/feature-0003-admin-audit-ux, base 44d958cd).
- 요청(/_template:entry arg-given): "`관리 콘솔 > AI 운영 현황`에서 (1) `감사` 카테고리 순서 재구성: 감사 로그·보관 대화·LLM 사용량·AI 운영 현황 (2) 각 항목 hover 시 상세설명 툴팁 (3) '최근 활동' 클릭 시 상세 확장 — 구조는 `프로필 > 사용 내역 > 차트`·`LLM 사용량 > 차트` 그래프 클릭→대화 목록 드릴다운 참조."
- 변경(`src/static/admin.html`): 감사 그룹에서 `보관 대화`(archives) 버튼을 `LLM 사용량`(usage) 앞으로 이동(요청 순서). 4개 감사 탭(audits/archives/usage/ai-ops)에 네이티브 `title` 상세설명. cache-buster `admin.js?v=20260702-audit-nav-ux`. 순서·title 은 표시 계층만 — 게이팅(`ADMIN_TAB_PERMISSIONS`)·서브탭·`applyAdminTabVisibility` 그룹경계 동적계산이 `data-admin-tab` 키 기반이라 불변.
- 변경(`src/routers/ai_ops.py` `_query_activity`): SELECT 11열 확장(model, resolved_model, run_id, conversation_id 추가) + dict additive(`req_model`·`resolved_model`·`prompt_tokens`·`completion_tokens`·`run_id`·`conversation_id`). 기존 필드 byte-동치 보존(서빙=`r[3] or r[2]`; writer 가 빈 resolved_model→None → `or`==`COALESCE`). overview feed + `/api/admin/ai-ops/activity` 페이징 공용 헬퍼라 양쪽 자동 상속(신규 엔드포인트 무).
- 변경(`src/static/admin.js`): `aiOpsActivityRowsHtml` 를 클릭 요약 행(`role=button`/`tabindex`/`aria-expanded`/caret) + 숨김 상세 패널(인라인 아코디언)로 재구성. 상세: 작업·요청→서빙 모델·토큰(프롬프트/완료/합계)·비용·지연·run_id·연결 대화(conversation_id→`/?conversation=<id>` 새 탭, 없으면 미귀속 안내). `_toggleAiOpsActRow`(링크 클릭 제외)·`bindAiOpsActivityToggle`(컨테이너 위임, 페이징 append 상속) 신설, `renderAiOps` 배선.
- 변경(`tests/test_ai_ops.py`): `_act_rows` 11-tuple + 신규 필드/서빙 우선순위/conv 유·무 경로 assert.
- 비변경: RBAC enforcement·인가·스키마·마이그레이션·파괴적 데이터·신규 엔드포인트 0. conversation_id/run_id 는 기존 `console.aiops.read` 게이트 + 기존 usage 모달 동일 노출 등급.
- 검증: `py_compile`·`node --check` PASS · `make test` exit 0(feature-0002+0003, test_ai_ops.py 15/15) · ruff PASS · §18.8 3-렌즈 VERDICT SHIP → REV-20260702T190000-audit-nav-ux.

## CHG-20260630T174000-metadata-bs-prefill (TASK-20260630T174000-metadata-bs-prefill — 스키마 골격 가져오기 시 기존 저장된 테이블/컬럼 설명 prefill, Minor §12.3 — feature-0003 프론트 단독, 비파괴)
- Date: 2026-06-30 (worktree ai/claude/feature-0003-metadata-bs-prefill, base dcb3e02).
- 요청: 관리콘솔 > 메타데이터 > 테이블 설명/컬럼 설명 — "스키마 골격을 가져왔을 때 기존에 입력된 정보가 확인되지 않음".
- 근본원인: 백엔드 `/api/admin/metadata/bootstrap`(`admin_bootstrap`)은 설계상 골격(이름·타입)만 반환·설명 미영속(주석 "UI 가 빈칸 prefill")인데, 프론트 `_metaBootstrapRenderResult` 가 `adminState.metadata.items`(저장된 설명) 매칭 prefill 을 구현하지 않아 골격 import 시 항상 빈칸.
- 변경(`src/static/admin.js`):
  - 색인/조회 헬퍼 신설 — `_metaBootstrapBuildDescIndex(mode)`(items 를 `(schema,table[,column])` 키로 색인; schema 소문자화 + 정확-schema 우선) + `_metaBootstrapDescLookup(idx, schemaName, tableName[, colName])`(정확-schema 시도 후 빈-schema 폴백). read 경로 `kb_metadata.load_column_descriptions_for_table`(`LOWER(schema_name)=LOWER() OR schema_name=''`)와 동일 정규화 → 수동 폼 입력(임의 케이스)·MSSQL 저장 schema_name=DB명(원본 케이스)·레거시 빈-schema 저장분도 매칭.
  - `_metaBootstrapRenderResult`: 입력란 생성 시 헬퍼로 prefill(`inp.value`) + `inp.dataset.original` 원본 기록(테이블·컬럼 양 분기).
  - `_metaBootstrapRefreshPrefill` 신설(in-place): 골격 DOM 재생성 없이 입력란 `value`·`dataset.original`·hint 만 최신 items 로 갱신 → 검색어·페이지·펼침 등 작업 위치 보존.
  - `loadMetadata`: items 적재 후 부트스트랩 모드(골격 존재)면 `_metaBootstrapRefreshPrefill` 호출(전체 재렌더 아님).
  - `_metaBootstrapSave`: `desc && desc !== inp.dataset.original` 인 행만 POST(미변경 prefill 재저장 안 함 → `source` provenance 보존). post-save 는 `await loadMetadata()` 로 재prefill(저장분 반영·original 최신화 → 중복 저장 차단). 기존 "빈칸 비우기 루프" 폐기. save-info 안내문 갱신.
- 변경(`src/static/admin.html`): cache-buster lockstep bump `admin.js`·`styles.css` `?v=20260630-metadata-list-detail → 20260630-metadata-bs-prefill`.
- 불변식: `.admin-meta-bs-desc[data-kind=...]` 셀렉터·골격 수집 구조·AI 일괄생성(빈 칸만 채움)·백엔드 계약(`/api/admin/metadata/bootstrap*`·tables/columns POST) 전부 불변. prefill 은 `inp.value`(DOM 프로퍼티) 주입 — XSS 무첨가.
- Impact: 비파괴, 순수 프론트. 데이터/스키마/RBAC/백엔드/엔드포인트/마이그 0 변경. 저장 측은 변경분만 → 기존 manual source 보존(prefill 추가가 유발할 manual→bootstrap 덮어쓰기 회귀 동반 차단).
- Verification: `node --check` PASS · admin.js NUL 0 · 신규 `verify_metadata_bs_prefill.mjs` 44/44(케이스 무관·빈-schema 폴백·정확 우선·변경감지·in-place 검색보존) + 인접 inline-desc 30·list-detail 33·paging 32·scope-single-ds 15 회귀 0. §18.8 적대 패널 8-가설 FIX-THEN-SHIP → H2(상태 리셋)·H3(키 케이스) 수정 → 재검 SHIP. REV-20260630T174000-metadata-bs-prefill.
- Rollback: 색인/조회/refresh 헬퍼 제거 + `_metaBootstrapRenderResult` prefill·dataset.original 제거 + `_metaBootstrapSave` 변경감지 환원(전 행 저장) + loadMetadata 재prefill 제거 + cache-buster 환원.
- Deploy: web 재빌드(정적 자산 — deploy_scope: included). 백엔드/마이그 무관.
- Files: `src/static/admin.js`, `src/static/admin.html`, `tests/verify_metadata_bs_prefill.mjs`(신규), `docs/{TASK,FUNCTION,REPORT,MODIFY,REVIEW}.md`.

## CHG-20260630T100000-doc-sync-rn-0630 (TASK-20260630T100000-doc-sync-rn-0630 — 06-29 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 기존 '2026-06-29' 블록에 doc_sync 6항목 추가(최종 11항목 — landing 중 origin/main 공유 2항목 합류분 보존) — [new work] 관계를 그림(다이어그램)으로 답변(feature-0013) · [improved admin] 스키마 골격 화면 접기·검색·페이지 정리 · [improved admin] 용어사전 역할 선택 단일화 · [improved work] 공유 대화 화면 보기 개선 · [fixed work] 새 대화 중복 표시 수정 · [fixed work] diff 답변 줄번호 수정 (기존: 용어 자율등록·검토 큐·답변 평가·공유 링크 참여 허용/유지 보존). `generated` 2026-06-29→2026-06-30.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260629b-rn-0629`→`?v=20260630-rn-0630`.
- Verification: `node --check release-notes-data.js` PASS + vm 로드 generated=2026-06-30·06-29 블록 11항목 확인 + 스키마(type/area/title/detail) 정합 + 신규 user-facing 머지 consolidate 대조.
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`.
- 사용자향 평이화: 내부 구현·feature-id·테이블/함수명·마이그 번호·엔드포인트·cache-buster 내부 슬러그 비노출. 렌더/접기/탐색 로직(`release-notes.js`) 무변경 — 데이터만. META(STATUS·wiki)는 별도 commit.

## CHG-20260629T181648-point-scroll-easeoutexpo (TASK-20260629T181648-point-scroll-easeoutexpo — 공유 대화 뷰 우측 스크롤바 가이드 뱃지(point rail) 추가 + 가이드 뱃지 클릭 스크롤 단축·EaseOutExpo, Minor §12.3 — frontend 표현계층)
- Date: 2026-06-29 (worktree ai/claude/share-scroll-guide-badge, base 60c0d45).
- 요청: 공유 기능으로 전달한 대화에도 우측 스크롤바 대화 가이드 뱃지 UI 구성 + 가이드 뱃지 클릭 시 소요시간 단축 + Easing 을 EaseOutExpo 로.
- 변경(`src/static/app.js`, 메인 뷰): rail dot 클릭 핸들러가 native `scrollIntoView({behavior:'smooth',block:'center'})` 대신 `scrollMessagePointIntoCenter(target)` 호출. 신규 헬퍼 `POINT_SCROLL_DURATION_MS=280`·`_easeOutExpo(t)=t>=1?1:1-2^(-10t)`·`_animatePointScroll(setter,from,to)`(rAF 보간, reduced-motion·performance.now 부재 폴백)·`scrollMessagePointIntoCenter`(messageLogEl 중앙 정렬 목표 scrollTop 계산+clamp). 기존 `renderMessagePointRail`/`layoutMessagePointRail`/`highlightActivePoint` 보존. rail dot 외 scrollIntoView(검색결과 5037·캘린더 9439·드롭다운 9629/9639) 무변경.
- 변경(`src/static/share.js`, 공유 뷰): `render()` 가 `renderMessage(msg, idx)` 로 idx 전달 + `setupSharePointRail(messages)` 호출. `renderMessage` 가 `row.id=share-msg-${idx}`·`dataset.idx` 부여. 신규 rail 로직 `setupSharePointRail`(렌더+scroll/resize/ResizeObserver/load 리스너 1회 부착, rAF 스로틀)·`renderSharePointRail`(dot=`<button.share-point-dot.is-{role}>`, ≤1개 hidden)·`layoutSharePointRail`(문서좌표 비율 top%)·`highlightSharePoint`(뷰포트 중앙 최근접 `is-active`)·`scrollShareMessageIntoCenter`(`shareEaseOutExpo`+`SHARE_POINT_SCROLL_DURATION_MS=280`, `window.scrollTo` 보간, reduced-motion 폴백).
- 변경(`src/static/share.html`): `<main id="shareMessages">` 직후 `<nav id="sharePointRail" class="share-point-rail hidden">` 추가. cache-buster `share.css`/`share.js` `?v=20260629-share-mermaid → 20260629-share-scroll-guide`.
- 변경(`src/static/share.css`): `.share-point-rail`(position:fixed 우측 미니맵, `pointer-events:none`)·`.share-point-dot`(`pointer-events:auto`, is-user/is-assistant/is-active/hover)·`@media(max-width:720px)` 숨김·`@media(prefers-reduced-motion)` transition 제거 추가.
- 변경(`src/static/index.html`): app.js cache-buster `?v=20260629d-new-conv-dedup → 20260629-point-scroll-easeoutexpo`.
- Impact: 비파괴, 순수 표현계층. 데이터/스키마/RBAC/백엔드/엔드포인트 0 변경. 공유 뷰는 anonymous 노출면이나 dot.title/aria-label 은 `.title`/`setAttribute`(DOM API)로 XSS 무첨가. reduced-motion·모바일 가드.
- Rollback: app.js 클릭 핸들러를 `scrollIntoView` 로 환원 + 신규 헬퍼 제거 / share.* 의 rail 추가분 제거 + cache-buster 환원.
- Deploy: web 재빌드(정적 자산 — deploy_scope: included). ask-worker 무관(프런트 전용).
- Deploy & live-verify (2026-06-29): commit f9954cf → origin/main drift(251df5f, diff-lineno-leak PR#467) rebase 3931fa3(cache-buster 충돌 2건 → 결합 신규 토큰 `20260629f-…` 해소) → ff-merge + push origin main(`251df5f..3931fa3`). 직후 feature-0013-mermaid PR#468 머지로 origin/main `8f0a025`(내 3931fa3 조상 포함 확인). web 이미지 재빌드(GIT_COMMIT 주입)·repo-web-1 recreate → **서빙본 검증 PASS**: healthz `git_commit=8f0a025`·mysql/pg ok / 서빙 index.html `app.js?v=20260629f-point-scroll-easeoutexpo`·share.html `share.js?v=20260629f-share-scroll-guide`·`share.css?v=20260629-share-scroll-guide` / 서빙 app.js EaseOutExpo 심볼 6·share.js rail 심볼 6·share.css rail 스타일 10 존재. worktree/branch cleanup 완료. **PB-0008 Windows 브라우저 시각검증은 잔여**(메인/공유 양 뷰 rail 표시·클릭 단축·EaseOutExpo). F0 repo-immutability escape(worktree finalize 완료, post-deploy doc-only).
- Files: feature-0003 `src/static/{app.js,index.html,share.html,share.js,share.css}` · `docs/{FUNCTION,TASK,MODIFY,REVIEW,TEST,REPORT}.md` · `docs/STATUS.md`.
- Cross-ref: 기존 메인 rail REQ-20260515-0006(TASK-0061 Phase 4) · 공유 뷰 mermaid 반응형 REQ-20260629T143914-share-mermaid-responsive.

## CHG-20260629T170913-glossary-role-fieldname-fix (TASK-20260629T170913-glossary-role-fieldname-fix — 용어사전 역할 드롭다운/라벨이 실제 역할 미표시하던 필드명 버그 수정, Minor §12.3 — 프런트 전용)
- Date: 2026-06-29 (worktree ai/claude/glossary-role-fieldname-fix, base 54dbfe3).
- 근본원인: `/api/admin/roles` 정본 직렬화 role 객체는 `{id,key,name,permission_codes,...}`. glossary 의 `_metaPopulateRoleFilter`/`_metaRoleLabel` 이 `adminState.roles` 를 `.role_key`/`.role_name`(미존재)로 읽어 → 필터는 전 역할 스킵(`if(!rk) continue`), 라벨은 미매칭 raw key. 역할 관리·계정 화면은 `.key`/`.name`(정본)이라 정상이었고 glossary 만 회귀. role.read 권한 게이트와 무관(현 admin 계정 보유, API 200·8역할 반환 확인).
- 변경(`src/static/admin.js`): `_metaRoleLabel` find 키 `x.role_key→x.key`·반환 `r.role_name→r.name`; `_metaPopulateRoleFilter` `r.role_key→r.key`·`r.role_name→r.name`(총 4 참조, 주석으로 근본원인 명기).
- 변경(`src/static/admin.html`): admin.js cache-buster `?v=20260629-glossary-role-single-ui → ?v=20260629-glossary-role-fieldname-fix`.
- Impact: 비파괴. 단일 진실원 헬퍼 수정으로 역할 필터 드롭다운(실제 8역할 노출)·등록 대상 역할 배지·용어 태그·유사어/관계 라벨이 친화 역할명 표기. 데이터/스키마/RBAC/백엔드 0.
- Rollback: admin.js 4 참조를 role_key/role_name 으로 환원 + cache-buster 복원.
- Deploy: web 재빌드(정적 자산 — deploy_scope: included). ask-worker 무관(프런트 전용).
- Deploy & live-verify (2026-06-29): commit 90ab783 → base drift(main 8383652) 흡수 병합 a5fea6f(REPORT.md union — fieldname-fix 엔트리 + main flexclip 완료본) → PR #466(CI test pass) 머지(main f021f3d) → worktree/branch cleanup → web 이미지 재빌드·repo-web-1 recreate. **PB-0008 재검증 PASS**(실 Windows Chrome): healthz git_commit=f021f3d·mysql/pg ok / 새 admin.js `?v=…-fieldname-fix` 로드 / 메타데이터>용어사전 역할 드롭다운 옵션 **2→10**(실제 8역할 Pending·일반 사용자·Admin·DBA·관리자·서버·웹플랫폼·사업팀 노출, 증적 artifacts/pb0008-glossary-role-dropdown-after.png). F0 repo-immutability escape(worktree finalize 완료, post-deploy doc-only).
- Files: feature-0003 `src/static/{admin.js,admin.html}` · `docs/{TASK,REPORT,REVIEW,MODIFY}.md` · `docs/STATUS.md`.
- Cross-ref: TASK-20260629T141637-glossary-role-single-ui(역할 단일 컨텍스트 도입 — 본 fix 가 그 드롭다운을 실제 동작시킴) · 정본 role 직렬화 `.key/.name`(admin.js 역할 관리·계정 화면).

## CHG-20260629-metadata-bs-flexclip (TASK-20260629-metadata-bs-flexclip — 메타데이터 부트스트랩 결과 패널 flex-shrink 클리핑 수정 + cache-buster bump, Minor §12.3, feature-0003)
- Date: 2026-06-29 (worktree ai/claude/metadata-bootstrap-flex-clip-fix, base origin/main dad75c3).
- 트리거: resume — `테이블 설명 AI 자동완성 및 UI 버그 수정`(원본 metadata-table-desc-fix/metadata-bs-collapse) PB-0008 실 Windows 브라우저 시각검증 중 적발한 추가 UI 버그. 메타데이터 > 테이블 설명 부트스트랩 골격이 다수 테이블일 때 결과 패널이 ~1행만 보이고 **pane 스크롤도 안 되어** 나머지 테이블 확인 불가.
- 근본원인: `.admin-pane[data-admin-pane="metadata"]` 는 `display:flex; flex-direction:column; flex:1 1 auto; min-height:0; overflow-y:auto`(고정 height 컨테이너). 그 flex 자식 `.admin-meta-bootstrap` 은 `overflow:hidden`(둥근모서리 클립)이라 flex 의 `min-height:auto` 가 0 으로 계산 → 결과가 많을 때 `flex-shrink:1`(기본)로 90px 까지 압축되고 자기 `overflow:hidden` 으로 내부 클립. 동시에 형제들이 압축되어 pane scrollHeight==clientHeight → pane 스크롤바 미발생. 직전 metadata-table-desc-fix 의 `.admin-meta-bootstrap-result { max-height: 460px }` 제거는 옳았으나 flex-shrink 경로가 별도 클리핑을 유발(headless Playwright 는 max-height:none 만 확인해 놓침 → PB-0008 실브라우저가 적발).
- 수정: `static/styles.css` `.admin-meta-bootstrap` 에 `flex-shrink: 0;` 추가(주석으로 근본원인 명기) → 부트스트랩 섹션이 자연높이 보존, pane 의 `overflow-y:auto` 가 스크롤 담당. `static/admin.html`·`static/index.html` 의 `styles.css?v=` cache-buster `20260629-metadata-bs-collapse → 20260629-metadata-bs-flexclip`(CSS 전용 변경 전파 — admin.js 미변경이라 `admin.js?v=` 유지).
- 영향 파일: `static/styles.css`(+6/−0, flex-shrink:0 + 주석), `static/admin.html`(cache-buster 1), `static/index.html`(cache-buster 1). 백엔드/route/RBAC/스키마/마이그/JS 로직 0.
- 라이브 검증(PB-0008): fix 주입 시 paneScrollHeight 684→2364(스크롤 발생), 17개 테이블(MSSQL `mssql-qa-idc`/`Account` 실테이블 `tblAccount` 등) 전부 표시. 배포 후 cache-buster·healthz 확인은 REPORT/TEST §3.
- REV-20260629T165743-metadata-bs-flexclip.

## CHG-20260629-metadata-bs-collapse (TASK-20260629-metadata-bs-collapse — 메타데이터 부트스트랩 결과 패널 접기+검색 재설계 + cache-buster bump, Major §12.3, feature-0003)
- Date: 2026-06-29 (worktree ai/claude/metadata-bootstrap-collapse-search, base origin/main 3dfe81c).
- 사용자 보고(metadata-bootstrap-mssql-db 배포 후속): 스키마 골격 가져온 뒤 (1) 테이블 펼침 시 패널 내부 UI 가 여전히 잘려 각 테이블 확인 불가, (2) 테이블 다수일 때 여백 과다.
- 진단: (1) 잘림은 직전 metadata-bootstrap-mssql-db 가 `styles.css` 의 `.admin-meta-bootstrap-result` 460px 캡을 제거·서버 배포까지 했으나 `admin.html` 의 `styles.css?v=`/`admin.js?v=` cache-buster 미bump → 브라우저가 stale CSS(캡 생존) 를 계속 로드(서버 반영, 미전파). (2) 부트스트랩 결과가 수백 테이블을 전부 펼쳐 평면 렌더.
- 변경(파일):
  - `static/admin.html`: `styles.css?v=`·`admin.js?v=` → `?v=20260629-metadata-bs-collapse`; status~result 사이 검색 필터바(`#metadataBootstrapFilterBar`: 검색 input `#metadataBootstrapSearch` + 카운트 `#metadataBootstrapFilterCount` + 모두펼치기/접기 `#metadataBootstrapExpandAll`).
  - `static/index.html`: `styles.css?v=` → `?v=20260629-metadata-bs-collapse`(공유 CSS 전파).
  - `static/admin.js`: `_metaBootstrapRenderResult` 재작성 — 테이블별 기본 접힘 한 줄 헤더(button: caret+이름+입력상태 힌트), 본문을 `.admin-meta-bs-body` 로 감쌈. 신규 `_metaBootstrapToggleTable`·`_metaBootstrapUpdateHint`·`_metaBootstrapRefreshAllHints`·`_metaBootstrapApplyFilter`·`_metaBootstrapToggleAll`·`_metaBootstrapSyncExpandAllLabel`. `_metaBindBootstrap` 에 검색·모두펼치기 idempotent 바인딩. `_metaBootstrapAiFill` finally 에 hint 일괄 갱신.
  - `static/styles.css`: `.admin-meta-bs-filterbar`/`-search`/`-filter-count`/`-expandall`, 접기 헤더(button, hover/focus-visible)·`.admin-meta-bs-caret`·`.admin-meta-bs-hint`(`.is-filled`)·`.admin-meta-bs-body`(`.is-collapsed` 시 display:none), 결과 gap 10→4px 조밀화. max-height 캡 미재도입(metadata-table-desc-fix 보존).
- 안전 불변: 접기·필터는 시각 토글(class/`display`)만 → 입력값 DOM 보존. 저장(`_metaBootstrapSave`)·AI 일괄생성(`_metaBootstrapApplyDescriptions`)이 descendant 셀렉터라 접힌/필터된 입력까지 전체 수집(회귀 0).
- 비변경: 백엔드/route/엔드포인트/스키마/RBAC/마이그 0. feature-0003 단독(cross-feature 없음).
- 검증: node --check PASS. §18.8 적대 frontend 패널(value-loss·state-machine·XSS·AI-fill·binding·edge·max-height) BLOCKER 0·diff CLEAN, MINOR(모두펼치기 라벨 desync) 수정 흡수. REV-20260629T142631-metadata-bs-collapse.

## CHG-20260629T041724-doc-sync-rn-0629 (TASK-20260629T041724-doc-sync-rn-0629 — 06-29 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- Date: 2026-06-29 (`/_dqa:doc_sync` 무인 스케줄, worktree ai/claude/doc-sync-20260629-130501).
- 배경: 직전 릴리즈노트 sync(63874f2 @ 06-29 08:35) 이후 main 병합된 06-29 user-facing 변경(40c0de0 용어사전 대화 자율등록 · 284e75a 용어 검토 큐 중첩 · 31aa67a+8c605b8 답변 평가 고유성)이 릴리즈노트 미반영(drift).
- 내용:
  - `static/release-notes-data.js`: releases head 에 신규 '2026-06-29' 블록 prepend(3항목) — [new admin] 대화 내용 바탕 업무 용어 자동 제안·검토 후 등록(역할별 구분·비슷한 용어 연결) · [improved admin] 용어 검토 큐를 용어사전 화면 안의 보기 탭으로 이동 · [fixed work] 답변 평가가 새로고침·대화 전환 후에도 답변마다 한 번만 남도록 정리(평가 변경 가능). generated 2026-06-29 유지.
  - `static/index.html`·`static/admin.html`: 릴리즈노트 cache-buster `?v=20260629-rn-0629`→`?v=20260629b-rn-0629`. app.js/styles.css 토큰 무변경.
- 제외 결정(적대): 첨부 wrong-bubble(ec39a60)은 "정상 display 경로 동작 동일"(스키마/마이그·프론트 무변경, 드문 cross-space 엣지) → 사용자 체감 변화 0 이라 릴리즈노트 항목 미추가.
- Why: 현실↔릴리즈노트 정합(사용자 노출 표면 최신화). 평이한 한국어·내부 비노출. 원천 코드(40c0de0/284e75a/31aa67a)는 별도 cycle 에서 이미 배포·검증됨 — 릴리즈노트 announcement 만 누락분.
- Verification: `node --check release-notes-data.js` PASS + 항목 스키마(type/area/title/detail) 정합 + releases head '2026-06-29' 블록 3항목 + 머지 3건 1:1 대조.
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`.
- Rollback: '2026-06-29' 블록 + cache-buster 2줄 revert. 비파괴 — 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked, deploy_scope: included) — 릴리즈노트 콘텐츠+cache-buster 전파. landing/deploy 는 cron wrapper 소관.

## CHG-20260629T120711-attach-id-space (TASK-20260629T120711-attach-id-space — 첨부 영속 레이어에 message_id_space 추가, H5(b) follow-up 완결, Major §12.3 — feature-0003 단독, 스키마 마이그 없음)
- Date: 2026-06-29. 선행 CHG-20260629T022055-feedback-id-space(피드백 레이어 H5(b) 해소)가 "잔여 — 별도 feature"로 명시한 **첨부 영속 레이어**(`_load_assistant_attachments_by_message`, message.id 키)를 동일 패턴으로 마저 완수. 사용자 요청("동일한 message.id 키를 쓰는 첨부 영속 레이어의 같은 이슈를 마저 처리"). 코드 계층만 변경 — DB 스키마/마이그 없음(MetaJson JSON 키로 id_space 보존).
- 변경 파일:
  - `src/app.py` `_materialize_assistant_attachment_edits`: 새 첨부 버전 row 의 MetaJson 에 `"message_id_space": "display"` 추가. message_id 은 `_load_latest_assistant_message`(표시 store 전용)에서만 와 항상 display 공간이라는 불변식을 영속화.
  - `src/app.py` `_load_assistant_attachments_by_message`: 반환 키를 `message_id` → `(message_id, message_id_space)` 복합 키로. MetaJson 의 `message_id_space`(없으면 'display' — legacy 행 하위호환) 읽어 그룹핑. 반환 타입 `dict[int, …]` → `dict[tuple, …]`.
  - `src/app.py` `_attach_assistant_attachments`: history 메시지의 `(id, id_space)`(미설정 시 'display') 복합 키로 매칭 — `_attach_user_feedback` 와 대칭. core 공간 메시지가 같은 숫자 id 의 display 첨부를 잘못 집어가는 wrong-bubble 차단.
  - `tests/test_task0285_attach_surfacing.py`: A1/A2/L1/L2 를 복합 키 shape 로 갱신 + A3(cross-space wrong-bubble 차단)·L4(core/display 분리 + legacy 'display' 간주) 회귀 테스트 신규. 헬퍼 `_att_row(space=…)` 추가.
- 비변경: 프론트(renderMessages 는 서버가 채운 `_attachments` 만 렌더)·share 경로·cache-buster·DB 스키마 0. 정상 display 경로 동작 동일(하위호환).
- 검증: 대상 테스트 11/11(A1~A3·L1~L4·V1·V2·S1·S2), `make test` 전체 스위트 exit=0(두 feature 회귀 0)·ruff 통과·py_compile.
- Cross-ref: 선행 CHG/REV-20260629T022055-feedback-id-space(피드백 레이어, H5(b) 출처) / REV-20260629T120711-attach-id-space.
## CHG-20260629-glossary-review-nest (TASK-20260629-glossary-review-nest — 용어 검토 큐 IA 중첩, Minor §12.3, 프런트 전용)
- Date: 2026-06-29. 검토 큐를 메타데이터 최상위 서브탭 → 용어사전 하위 2차 보기 탭으로 이동(IA). 백엔드/route/엔드포인트 무변경.
- admin.html: `data-meta-subtab="glossary-review"` 버튼 제거 + 용어사전 하위 `#metadataGlossaryViews` strip(`.admin-meta-gview`: data-glossary-view="list"|"review") + 배지 이전.
- admin.js: 상태 `glossaryView`; 헬퍼 `_metaIsGlossaryReview`/`_metaSubtabVisible`(용어사전 OR(ingest.manual, glossary.curate))/`_GLOSSARY_VIEW_PERM`/`_metaSyncGlossaryViews`(보기 권한 게이트+보정+aria-selected); `_metaBindControls` gview 바인딩; `_metaRenderForm`/`loadMetadata`/`_metaSyncToolbarVisibility` 를 새 보기 모델로; **`ADMIN_TAB_PERMISSIONS.metadata` 에 `kb.glossary.curate` 추가**(적대 리뷰 MAJOR — curate-only 부모 탭 진입 보존); 메타 탭 재진입 분기에 `_metaSyncGlossaryViews`+`_metaPrimeReviewBadge`.
- styles.css: `.admin-meta-glossary-views`/`.admin-meta-gview` 필 스타일. FUNCTION.md IA 기술 갱신.
- 검증: node --check PASS, 잔여 functional glossary-review 참조 0, 적대 검증 3 lens(BLOCKER 0, MAJOR 1 수정). Cross-ref: REV-20260629T120000-glossary-review-nest / TASK-20260629-glossary-conv-autoreg(선행).
- **배포 정합(cache-buster)**: admin.html 의 `admin.js`/`styles.css` 참조 `?v=20260625-role-account-prompt-autogen` → `?v=20260629-glossary-review-nest` bump. 정적 자산 전파의 유일 메커니즘(웹 재빌드만으론 브라우저 캐시 미갱신). **부수 효과**: 직전 glossary-conv-autoreg cycle 이 admin.js/styles.css 를 변경하고도 `?v=` 를 bump 하지 않아 캐시 보유 관리자에게 미전파였던 갭도 본 bump 로 함께 해소(직전 + 본 cycle UI 동시 propagate).

## CHG-20260629T022055-feedback-id-space (TASK-20260629T022055-feedback-id-space — 피드백 고유성 키에 id_space 추가, H5(b) follow-up, Major §12.3 — cross-feature 0002+0003)
- Date: 2026-06-29. 선행 CHG-20260629T014345-feedback-unique-vote 의 적대 리뷰가 수용·문서화한 H5(b)(message_id 두 id 공간 모호성) 잔여 한계 완수. 데이터 계층(컬럼·인덱스·코어 UPSERT)은 feature-0002(마이그 0022 + sample_feedback.py) — 본 항목은 feature-0003 web 층.
- 변경(feature-0003):
  - `src/app.py` `/api/history` 4개 메시지 빌더에 `m["id_space"]` 노출 — `_get_agent_core_history`(PG·MySQL)="core", `_get_history`(PG·MySQL display)="display".
  - `src/app.py` `_load_user_feedback_by_message`/`_attach_user_feedback`: 반환·매칭 키를 int(message_id) → **(message_id, id_space) 복합 키**로 확장(cross-space wrong-bubble 복원 차단).
  - `src/app.py` `post_sample_feedback`: body `message_id_space`("display"|"core") 파싱·정규화 후 `record_feedback(message_id_space=…)` 전달.
  - `src/static/app.js` `_buildSampleFeedbackControls`: `message.id_space` 읽어 POST body 에 `message_id_space` 포함(기본 "display").
  - `src/static/index.html`: app.js cache-buster `?v=20260629-feedback-unique-vote` → `?v=20260629b-feedback-id-space`.
  - `tests/test_sample_feedback_curation.py`: 요청에 message_id_space="core" 추가 + 코어 전달 단언.
- 비변경: 재투표 변경 허용·"샘플 등록" 분리·rate-limit·RBAC·audit·CSS 0.
- 검증: curation 15/15 · node --check · py_compile · 두 feature 전체 회귀 0.
- Cross-ref: feature-0002 CHG-20260629T022055-feedback-id-space / 마이그 0022 / REV-20260629T022055-feedback-id-space.

## CHG-20260629T014345-feedback-unique-vote (TASK-20260629T014345-feedback-unique-vote — 답변당 사용자별 고유 피드백(👍/👎) 강제, Major §12.3 — cross-feature 0002+0003)
- Date: 2026-06-29. 사용자 보고(새로고침·대화 전환 후 같은 답변에 피드백 재부여 가능)의 수정. 정본 데이터 계층 변경(테이블 컬럼·UNIQUE 인덱스·코어 UPSERT)은 feature-0002(마이그 0021 + sample_feedback.py) — 본 항목은 feature-0003 web 층 변경(endpoint·history·UI·CSS) 기록.
- 변경(feature-0003):
  - `src/app.py` `post_sample_feedback`: 요청 body `message_id` 파싱(int|None) → `record_feedback(message_id=…)` 전달. id 회수는 `lastval()`(UPSERT DO UPDATE 경로 부정확) 제거 후 record_feedback 의 `RETURNING id` 반환값 직접 사용.
  - `src/app.py` 신규 `_load_user_feedback_by_message(conversation_id, created_by)`(PG `sample_feedback` 에서 현재 사용자 vote 행 message_id→{vote} 그룹핑, suggested=false 한정, fail-soft) + `_attach_user_feedback(messages, by_message)`(assistant 메시지에 `m["feedback"]` 주입). `@app.get("/api/history")` 가 messages 로드 직후 호출 — 새로고침·전환 시 기존 투표 복원 원천(첨부 영속 attach 패턴 대칭).
  - `src/static/app.js` `_buildSampleFeedbackControls`: POST body 에 `message_id: message.id` 포함. `message.feedback` 있으면 해당 투표 버튼 활성표시(`is-active`)+상태문구 복원. in-session 영구 잠금(`data-done`) 제거 → 변경 허용(버튼 enable 유지), 전송 중 `data-busy` 가드로만 더블클릭 차단. "샘플 등록"(suggested) 은 투표 활성표시와 분리.
  - `src/static/styles.css`: 기존 `[data-done]` 비활성 규칙을 `.message-feedback-btn.is-active`(현재 투표 강조)+`[data-busy]`(전송 중) 규칙으로 교체.
  - `src/static/index.html`: cache-buster `styles.css ?v=20260629-feedback-unique-vote` · `app.js ?v=20260629-feedback-unique-vote`(변경 전파).
  - `tests/test_sample_feedback_curation.py`: record_feedback 반환 id(=42) 기반 + `message_id=77` 전달 단언으로 갱신(lastval 제거 정합).
- 비변경: RBAC(대화 접근 게이트)·rate-limit(10/min)·audit(sample.feedback.submit)·scope 도출·승급/거부 endpoint 무변경. 엔드포인트 shape 는 body 에 optional `message_id` 추가뿐(하위호환 — 부재 시 기존 동작).
- 검증: curation 15/15 PASS · `node --check app.js` · `py_compile app.py` PASS · 두 feature 전체 스위트 회귀 0.
- Cross-ref: feature-0002 CHG-20260629T014345-feedback-unique-vote / REV-20260629T014345-feedback-unique-vote / MIGRATIONS 0021.
## CHG-20260629-glossary-conv-autoreg (TASK-20260629-glossary-conv-autoreg — 용어사전 대화 자율등록 web/UI, Major §12.3, cross-cut 0002+0003)
- Date: 2026-06-29. 「관리 콘솔 > 메타데이터 > 용어사전」의 대화 자율등록·역할 분리·유사어 참조 web 경계 + 관리 UI. 코어/마이그/hook = feature-0002 동반 CHG.
- app.py: ① glossary CRUD 에 role_key(공용 '*' 기본) 검증·필터 추가 + UNIQUE(scope,role,term) 409. ② 신규 권한 `kb.glossary.curate`(group=kb, admin seed). ③ 검토 큐 3 엔드포인트(`GET …/glossary-feedback`·`POST …/{id}/promote`·`POST …/{id}/reject`). ④ 유사어 3 엔드포인트(`GET/POST …/glossary/{id}/relations`·`DELETE …/glossary/relations/{id}`). audit: glossary.feedback.promote/reject·glossary.relation.create/delete.
- admin.html/admin.js/styles.css: glossary 폼 역할 select·목록 역할/출처 배지·툴바 역할 필터·검토 큐 서브탭(pending 배지·승급/되돌리기)·용어별 유사어 패널. XSS=textContent/value.
- route_snapshot_p5b.json: 신규 6 라우트 반영(golden 갱신). 테스트: 신규 `test_metadata_glossary_autoreg.py` 13 + 기존 metadata 회귀 갱신.
- Cross-ref: feature-0002 CHG-20260629-glossary-conv-autoreg / REV-20260629T103000-glossary-conv-autoreg / ADR-20260629T101500.

## CHG-20260626T135945-ask-dedup-hotfix (TASK-20260626-ask-dedup-idempotency — 동일 cycle 라이브 PG 회귀 hotfix, Major §12.3, 정본 코드=feature-0002 ask_jobs.py)
- Date: 2026-06-26. CHG-20260626-ask-dedup-idempotency 배포 검증 중 적발된 라이브 회귀의 즉시 수정. 정본 코드 변경은 feature-0002 ask_jobs.py(전용 파라미터 분리) — 본 항목은 feature-0003 동반 기록(REPORT/TASK/REVIEW 갱신).
- 회귀/수정 요지: dedup NOT EXISTS 의 `%(cid)s`/`%(account_id)s` 재사용 → PG `AmbiguousParameter(text vs character varying)` → 워커 모드 신규 /api/ask 전부 500. 전용 파라미터 `%(dcid)s`/`%(daccount)s` + 테이블 alias `d` 로 분리. 라이브 PG 수정 SQL 직접 실행 재검증 + 회귀 테스트 단언 추가(21/21). web/app.py·app.js 코드 변경 0(본 commit 은 feature-0002 코드 + 양 feature 문서).
- 검증/배포: verify-completion --pre-commit → ff-merge → web+ask-worker 재빌드·재기동(deploy_scope: included).
- Cross-ref: feature-0002 CHG-20260626-ask-dedup-idempotency(HOTFIX) / REV-20260626T135945-ask-dedup-idempotency / REV-20260626T134920-ask-dedup-idempotency.

## CHG-20260626-ask-dedup-idempotency (TASK-20260626-ask-dedup-idempotency — assistant 요청 2번 중복 전송/처리 결함 수정, Major §12.3 — /api/ask send/concurrency, cross-feature 0002 주 변경 + 0003 dispatch/UI)
- Date: 2026-06-26. 사용자 보고(/_template:entry): assistant 요청이 2번 중복 전송/처리(요청·답변 모두 2회, 항상). 근본원인: 워커 모드 `/api/ask` long-poll 연결이 web 재생성(배포)으로 끊기면(502 EOF) 사용자 재전송 → 워커 enqueue 멱등성 부재로 두 번째 job 생성 → 첫 job 은 out-of-process 생존·완료 → 답변 2개.
- Scope: feature-0003 web (app.py dispatch · app.js 복구 경로). ask_jobs.py 정본 변경은 feature-0002 CHG-20260626-ask-dedup-idempotency(교차). 스키마/RBAC/마이그/엔드포인트 shape 0(런타임 멱등 — payload->>'user_message' 비교, 신규 컬럼·인덱스 없음).
- 내용(`src/app.py` `_dispatch_ask_run_worker`):
  - `_enqueue` 멱등화: payload.user_message 를 `_user_message` 로 캡처 → ① 사전 `ask_jobs.find_active_dup_ask_job(conv, account, user_message)` — 활성 중복 있으면 **새 job·sentinel 미생성, 기존 job_id 반환**(기존 run KV/run_id 보존; 아래 attach 루프가 그 run 결과를 동기 응답) ② 없으면 enqpre sentinel 선기록 후 `enqueue_ask_job(..., dedup_message=_user_message)`(INSERT NOT EXISTS atomic backstop) ③ INSERT 억제(None) 시 `find_active_dup_ask_job` 재조회로 슬롯가득(None→429) vs 중복(기존 job_id→attach) 구분 + `logging...info("ask-dedup: …")`.
  - 기존 attach 루프(KV terminal / job terminal long-poll)·슬롯 429·sentinel 가드(TASK-0241)·shape 무변경 — dedup 분기만 추가.
- 내용(`src/static/app.js` sendPrompt 실패 catch, 기존 대화 분기): `/api/ask` 실패 시 복구 status 조회 `fetchAskStatus(askCid)` 가 첫 호출 null(web 일시 불안정으로 /api/ask_status 도 502) 이면 **0.7s 간격 ×3 재시도**해 in-flight run 을 안정 포착 → `is_processing` 시 기존 attach 경로로 흡수(불필요 재전송 억제). is_processing 분기 이후 로직(timeout recovery dialog·attach·cancel/finalize)·shape 무변경. cache-buster 는 배포 시 bump(아래).
- 비변경: 프론트 이벤트 바인딩·apiFetch·resume·group/1:1 send 라우팅·R2/R3 인터럽트 0. 백엔드 inproc 경로·claim/sweep/heartbeat 0.
- 적대 리뷰 흡수(REV-20260626T134920-ask-dedup-idempotency, SHIP-WITH-FIXES → SHIP, BLOCKER/MAJOR 0): ① dedup/find 활성 판정을 `_ACTIVE_SLOT_PREDICATE` 재사용으로 교체(stale-running 제외 — 죽은 run 에 attach 방지, `find_active_dup_ask_job(stale_seconds=...)`); ② `index.html` app.js cache-buster `?v=20260626-ask-dedup-idempotency` bump(part B 전파); ③ dedup 키 attachment 누락은 accepted trade-off(동시 same-text/different-attachment 극희소). 동시 race 표현은 "commit 된 중복에 atomic" 으로 정정(sub-ms 동시충돌 완전차단은 partial unique index 후속).
- 검증: `test_ask_jobs.py` 21/21(신규 dedup 5, stale MAKE_INTERVAL 단언 포함) + `py_compile app.py` + `node --check app.js` PASS.
- Deploy: **web + ask-worker 재빌드 필수**(A 가 ask_jobs.py = 양 이미지 baked). deploy_scope: included.
- Cross-ref: feature-0002 CHG-20260626-ask-dedup-idempotency / REV-20260626T134920-ask-dedup-idempotency / TASK-20260626-ask-dedup-idempotency / REPORT 2026-06-26.

## CHG-20260625-role-account-prompt-autogen (TASK-20260625-role-account-prompt-autogen — 역할 '전체 제품 프롬프트' + 프로필 '제품별 개인 프롬프트' 자동 작성, Major §12.3 — 외부 LLM dispatch 2개 scope 확장)
- Date: 2026-06-25. 사용자 요청(/_template:entry): "`관리 콘솔 > 역할 > 제품 사용 > 전체 제품 프롬프트` 와 `작업 화면 > 프로필 > 프롬프트 > [각 제품]` 의 자동 완성 기능 구성 — 역할 성격·소속 사용자 대화 내역, 프로필은 역할·제품·대화 패턴 반영." 결정: on-demand 버튼만 + 기능만 구성(seed 라이브 생성은 운영자).
- Scope: feature-0003 web only. **스키마 변경 0**(기존 `WebSystemPrompts` scope='role'/'account' 행 재사용 — 합성은 agent-core `compose_system_prompt` 가 이미 처리). PG·gateway·credential·RBAC 카탈로그 무변경. 기존 제품 자동작성 엔드포인트·UI 동작 보존.
- 내용(`src/app.py`):
  - 신규 컨텍스트 헬퍼: `_collect_conversation_signals_pg(*, product_id=None, account_ids=None, topic_limit, summary_limit)` — 제품 경로가 인라인 수집하던 topic·summary 를 필터 일반화. **빈 account_ids → PG 미접근 + 빈 결과**(cross-scope 누출 가드), account_ids=None → 전체. 원문 메시지 아닌 집계 메타만.
  - 신규: `_describe_role_character`(권한코드→성격 서술, `_ROLE_CAPABILITY_HINTS` — ask 없으면 '조회 전용' 명시) · `_assemble_role_prompt_llm_request(role_id)`(역할 정의/권한 + 소속 계정 대화 패턴 + 접근 가능 제품 → role-scope meta-prompt) · `_assemble_account_prompt_llm_request(account_id, role_id, product_id)`(역할 성격 + 제품 용도 + 본인 대화 패턴 → 개인 선호 레이어 meta-prompt; 스키마 세부 미중복).
  - 공유 응답 헬퍼 추출(중복 제거): `_prompt_generate_json_response(ctx, *, log_label, log_ctx)`(비스트리밍) · `_prompt_generate_stream_response(ctx, *, log_label, log_ctx)`(SSE 별스레드+Queue 브릿지). **제품 비스트리밍/스트리밍 엔드포인트도 동일 헬퍼로 리팩터** — 동작·SSE 이벤트·JSON shape 불변(계약 테스트가 self-contained 라 회귀 0).
  - 신규 엔드포인트 4종 + 인증 게이트: `_collect_role_prompt_context`(`system_prompt.manage.role.any`) → `POST|GET /api/admin/roles/{id}/prompt/generate[/stream]` · `_collect_account_prompt_context`(본인 + 제품 지정 시 `_account_has_product_access`) → `POST|GET /api/auth/me/system-prompt/generate[/stream]`.
- 내용(정적 자산): admin.js `buildSystemPromptEditor` 에 `autoGenerateRoleId` 추가(스트림 URL = role 이면 roles/{id}) + `applyAutoGenMeta` scope-aware(role=소속 사용자·대화주제) + 역할 '전체 제품 프롬프트' 카드가 `autoGenerateRoleId` 전달. index.html 프로필 프롬프트 탭 `#generatePromptBtn` 추가. app.js `generateAccountPrompt()` SSE 핸들러(admin 핸들러와 동형, 선택 제품 query, 생성 후 검토→'저장').
- privacy/비용: 역할 scope 는 교차사용자 집계지만 **원문 미사용·집계 메타만**(제품 경로와 동일 house style) + admin 게이트. account 는 본인 데이터만 + **LLM 토큰 quota 게이트**(아래 적대리뷰 MAJOR-1). on-demand 전용 — 자율 백그라운드 생성·자동 저장 없음(사용자 결정).
- **적대 리뷰(REV-20260625T173000-role-account-prompt-autogen, §18.8 2렌즈) MAJOR 2 + MINOR 2 흡수**: **MAJOR-1**(self-service account 자동작성 quota 우회 → `_collect_account_prompt_context` 에 `_check_account_token_quota` 게이트=429) · **MAJOR-2**(프로필 에디터 dirty 미추적 → 자동작성 본문이 제품 전환 시 silent 소실 → `initAccountPromptEditor` `_lastLoaded`/`_prevValue` + `window.confirm` dirty 가드) · MINOR(재진입 가드 `_streamAbort===controller`로 app.js·admin.js 동시 수정 · 프로필 메타 `.helper-text-warn` 강조) · NIT(done 스크롤 보존). 반증 실패=안전 확인: IDOR 없음(account 는 authed id 만)·privacy 빈 account_ids PG 미접근 가드·SQLi 없음·리팩터 byte-equivalent.
- 정적 자산 캐시버스터: index.html `styles.css`/`app.js` + admin.html `styles.css`/`admin.js` → `?v=20260625-role-account-prompt-autogen`.
- 검증: `tests/test_auto_role_prompt.py`(7) + `tests/test_auto_account_prompt.py`(5) 신규 + 회귀(`test_auto_product_prompt` 12·`test_prompt_generate_stream` 3·`test_prompt_generate_truncation` 4) = **33/33 PASS**(agent 이미지) + `py_compile` + ruff(app.py) PASS + `node --check` admin.js/app.js + CSS brace balance(1572/1572) PASS.
- worktree `ai/claude/role-account-prompt-autogen`(base 7e6aab8). REVIEW REV-20260625T173000-role-account-prompt-autogen.

## CHG-20260625-auto-product-prompt (TASK-0309 — 제품 insight 분석률 95% 도달 시 제품 프롬프트 무인 자동완성(1회성), Major §12.3 — 자율 LLM dispatch + 자율 DB write)
- Date: 2026-06-25. 사용자 요청(/_template:entry): "`관리 콘솔 > 제품`의 각 제품에서 '제품 프롬프트'가 미입력인 항목을 대상으로, 분석률이 95% 넘는 순간 자체적으로 자동완성·저장. 단 임의적 insight 초기화로 재상승해도 별도 분석 안 함(1회성)."
- Scope: feature-0003 web only. **마이그레이션 = MySQL 멱등 ALTER 1컬럼**(`WebProducts.AutoPromptGeneratedAt`), PG·agent-core·gateway·credential·RBAC·정적자산 무변경. 수동 '자동작성' 엔드포인트(POST/GET `.../prompt/generate[/stream]`) 무변경 보존.
- 내용(`src/app.py`):
  - `_ensure_web_tables`: `ALTER TABLE WebProducts ADD COLUMN AutoPromptGeneratedAt DATETIME NULL`(try/except 멱등, 1회성 마커). insight reset 은 PG insight 만 지우고 본 컬럼 보존 → reset→재상승 무재실행.
  - 리팩터: `_collect_product_prompt_context`(인증 게이트)에서 request-less 조립 코어 `_assemble_product_prompt_llm_request(product_id)` 분리. 인증·무인 경로 공유(중복 0). 시그니처/반환계약/await 무변경 → 비스트리밍·스트리밍 엔드포인트 blast-radius 0.
  - 신규: `_product_prompt_present`(Scope='product' 비어있지 않음) · `_auto_prompt_eligible_product_ids`(마커 NULL 후보, 컬럼 부재 시 빈목록) · `_autonomous_generate_product_prompt`(조립→동기 LLM→마커 행 FOR UPDATE 잠금+재검사→upsert(system, updated_by NULL)+마커 UPDATE+audit `admin.product.prompt.autogenerate` 를 **autocommit=False 명시 tx** 로 commit, finally 복원) · `_auto_prompt_sweep_once`(미입력 검사 우선→backoff 체크→coverage 캐시→`pct>=임계`→cycle 상한 → 생성) · `@app.on_event("startup") _start_auto_prompt_sweep_loop`(daemon thread, `AGENT_AUTO_PROMPT_SWEEP_SEC` 기본 180·0=비활성, jitter min(45,interval), `_start_db_rule_reconcile_loop` 패턴).
  - 설정: `_AUTO_PROMPT_COVERAGE_THRESHOLD`(기본 95.0) · `_AUTO_PROMPT_MAX_PER_CYCLE`(`AGENT_AUTO_PROMPT_MAX_PER_CYCLE` 기본 3, 0=무제한) · `_AUTO_PROMPT_FAIL_BACKOFF_SEC`(기본 3600) + in-process `_AUTO_PROMPT_FAIL_UNTIL`(실패 제품 backoff).
- **적대 리뷰(REV-20260625T161500-auto-product-prompt) BLOCKER 1 + MAJOR 2 흡수**: **B1**(원자성) `_connect_memory` autocommit=True 라 "단일 tx" 거짓 → `conn.autocommit=False` + FOR UPDATE + finally 복원으로 진짜 단일 tx(부분실패 rollback → 마커/프롬프트 정합 = 1회성 불변식 보호). **M1**(비용 누수) 실패 경로 마커 미설정 매-cycle 재호출 → 실패 backoff. **M2**(버스트) cycle 생성 상한. MINOR(m1 `_record_llm_usage` 우회=수동경로 동일 기존갭/m2 lost-update 잔여창/m3 float 경계) 수용.
- 비용/안전: 성공 시 1회성 마커로 제품당 LLM 1회 영구 제외 · 실패 시 backoff 로 재호출 제한(영구 손실 없음) · cycle 상한으로 버스트 분산 · 저장직전 FOR UPDATE+재검사로 수동입력/경합 보호 · audit(system actor) 추적 · env 로 전면 비활성 가능.
- 검증: `tests/test_auto_product_prompt.py` 12/12 PASS(T1~T12 — T3 reset 생존·T10 마커 UPDATE 실패 rollback·T11 backoff·T12 cycle 상한 회귀 가드 포함) + `test_insight_coverage.py` 5/5 무회귀 + `py_compile app.py` + ruff PASS.
- worktree `ai/claude/auto-product-prompt`(base 262a065). REVIEW REV-20260625T161500-auto-product-prompt.

## CHG-20260624T170757-metadata-ai-autocomplete (TASK-20260624-metadata-ai-autocomplete — 관리 콘솔 메타데이터 5 서브뷰 AI 자동완성(단건+골격 일괄) + pane 스크롤 수정, Major §12.3 — 외부 LLM dispatch + 서브뷰별 RBAC 표면)
- Date: 2026-06-24. 사용자 요청(entry persona): "관리 콘솔 > 메타데이터를 실제 관리자가 처음 쓰기 까다롭다 — 모든 탭에 AI 자동완성" + "창이 길어지면 스크롤이 없어 하단 항목을 못 본다". **중단 세션 resume** — 원본 세션이 session limit 으로 프론트 일괄 함수 삽입 직후 중단 → 본 cycle 이 잔여(CSS·테스트·docs·panel·게이트) 완수.
- Scope: feature-0003 web only. 마이그레이션 없음, gateway·credential·ROADMAP·embedding provider·agent-core 무변경. 기존 metadata 거버넌스(ITEM-11) 폼/부트스트랩 UI 에 AI 채움 버튼만 추가.
- 내용(`src/app.py`): 신규 엔드포인트 2개 —
  - `POST /api/admin/metadata/{sub}/suggest`(단건): 5 서브뷰(glossary→definition·enums→label·tables/columns→description·samples→nl_question)의 식별 필드 → 설명 1건 생성. RBAC 서브뷰별(glossary/enums/tables/columns=kb.ingest.manual, samples=kb.sample.curate). tables/columns 는 datasource 지정 시 실제 스키마(컬럼) best-effort grounding(부트스트랩 introspection 재사용 — `_safe_ident`+`load_known_schemas` allowlist). **생성물 영속 안 함**(기존 등록/수정 저장 흐름).
  - `POST /api/admin/metadata/bootstrap/describe`(일괄): 골격(테이블/컬럼)을 1 LLM 호출로 설명 생성, 프론트가 청크 단위 호출. RBAC kb.ingest.manual. 식별자는 프롬프트 텍스트로만(SQL 미사용). 결과 {schema,table[,column],description} 리스트, 빈 입력란만 채움.
  - 헬퍼: `_metadata_resolve_account_perm`(perm 가변 RBAC)·`_metadata_introspect_table`(grounding)·`_metadata_suggest_messages`/`_metadata_bulk_describe_messages`(프롬프트)·`_metadata_parse_json_object`(코드펜스/전후텍스트 허용 JSON 추출)·`_metadata_bulk_shape_results`(대소문자·공백무시 매칭)·`_metadata_llm_complete`(비스트리밍 공용 호출).
  - **비용/DoS 방어(§18.8 panel BLOCKING 적발 수정)**: `_METADATA_FIELD_CAPS` 에 `"sql": 8000` 추가(samples sql 이 프롬프트에 raw 삽입 → 입력 cap 으로 거대 프롬프트 차단, `_metadata_str_field` 강제) + 두 엔드포인트에 `_search_rate_limit_check(max_per_min=_METADATA_AI_RATE_PER_MIN=20)`(per-account 비용 DoS, RBAC 통과 후·LLM 전, 429 — fix-with-ai 동형).
- 내용(`src/static/admin.html`): 단건 버튼 `#metadataSuggestBtn`(폼 액션) + 일괄 버튼 `#metadataBootstrapAiBtn`(부트스트랩 저장 액션). cache-buster `?v=20260624-metadata-ai-autocomplete`(styles+admin.js).
- 내용(`src/static/admin.js`): `_metaSuggestFill`(단건 — 서브뷰별 REQUIRES 검증·scope datasource grounding·target 필드 채움·진행 disable/복구)·`_metaScopeDatasourceKey`·`_metaBootstrapAiFill`(일괄 — 청크 순차·진행률·부분실패 카운트)·`_metaBootstrapApplyDescriptions`(빈 입력란만, 수동입력 보존). 이벤트 바인딩 `dataset.bound` 가드. **XSS: 생성물은 input.value 로만(innerHTML 무사용)**.
- 내용(`src/static/styles.css`): (1) **스크롤 수정** — `.admin-pane[data-admin-pane="metadata"].is-active` 를 dashboard/usage/release-notes 와 동일한 `overflow-y:auto; overflow-x:hidden` 목록(TASK-0167)에 추가. metadata pane 은 scope+서브탭+부트스트랩+폼+리스트의 단순 세로 흐름인데 `.admin-workspace`(overflow:hidden+100vh) 하위에서 pane 자체 스크롤이 없어 창이 길면 하단이 잘렸음 → 해소. 셀렉터 속성 한정이라 타 pane 무영향. (2) `.admin-meta-ai-btn` — btn-secondary 위 옅은 primary 강조(color-mix, 선례 다수) + disabled progress 커서.
- 내용(`tests/test_metadata_ai_autocomplete.py`, 신규): 18 케이스 — RBAC(서브뷰별·samples=sample.curate)·U404·필수필드 400·정상(definition/nl_question)·cap·LLM오류 전파·bootstrap RBAC/mode/빈tables/정형(tables·columns)·미파싱 502·parse_json 단위 + **sql cap 400·rate-limit 429(LLM 미호출 단언)**.
- 보안: RBAC 서브뷰별 게이트(LLM/introspection 전 검사) · 입력 cap 전 필드(+sql) · per-account rate-limit · 생성물 영속 안 함(검토 후 별도 저장) · XSS input.value · introspection allowlist(부트스트랩 SQLi 방어 재사용) · LLM 응답 신뢰경계(parse/shape isinstance 가드·cap). §18.8 2-lens 적대(backend-security+frontend/css): 백엔드 BLOCKING 2건(sql cap·rate-limit) 적발→수정, 프론트 SHIP.
- Verification: `tests/test_metadata_ai_autocomplete.py` **18/18**(PYTHONPATH=feature-0002:feature-0003 실측). py_compile(app.py) OK. UI 실렌더 = PB-0008(배포 후).
- Deploy: deploy_scope: included(프로젝트 전역) — web 재빌드(정적+엔드포인트). cache-buster bump 로 신규 admin.js/styles.css 강제 로드. 마이그 없음.
- Rollback: app.py(엔드포인트 2+헬퍼+cap+rate) / admin.{html,js} 버튼·핸들러 / styles.css metadata overflow+버튼 / 테스트 제거 → AI 자동완성·스크롤 수정 제거(기존 metadata CRUD 무영향).
- Files: src/app.py, src/static/admin.html, src/static/admin.js, src/static/styles.css, tests/test_metadata_ai_autocomplete.py, docs/{TASK,MODIFY,REVIEW,REPORT}.md.

## CHG-20260624T160000-scope-key-unify (TASK-20260624-scope-key-unify — 메타데이터/샘플 admin scope_key 축을 read 축으로 통일: ds-scoped 死data 수정, Major §12.3 — scope 경계)
- Date: 2026-06-24. `/_template:resume` 의 ITEM-11 Phase 2 작동검증 중 구조 감사(4 dim)가 적발한 scope-key 축 불일치 死data 수정. ITEM-10(용어/ENUM)·ITEM-11(테이블/컬럼 설명)·ITEM-03(샘플 검수) admin **공유 경로**.
- 死data: admin write=datasource **라벨**(all_datasources dict 키), 질의 read=`agent_core.set_active_datasource(_ds.get('scope_key') or _ds.get('key'))`=DB-등록 ds 의 compute_scope_key **해시** → 라벨≠해시 로 DB ds 의 ds-scoped 설명/샘플이 'common' 외 영영 안 읽힘(라이브 재현: 라벨 'mysql-local' 저장 → 질의시점 해시 'mysql-ddae8975d793' 읽기 MISS). 배포 DS 20+ 전부 WebDatasources(.env 0), KB 테이블 전부 0행이라 손실 데이터 없는 잠복.
- 변경(feature-0003):
  - `src/app.py` `_metadata_valid_scope_keys`: 허용 scope 를 dict 키(라벨)가 아닌 **read 동일식** `ds.get('scope_key') or ds.get('key')`(DB=해시·.env=라벨)로. (⚠️ `_dsr.scope_key` 미사용 — 그 헬퍼는 .env(host 보유) 시 해시를 *계산*해 read 라벨과 어긋나 死data 가 역재발한다. 적대 패널이 이 함정을 BLOCKER 로 적발 → 교정.)
  - `src/app.py` `/api/admin/datasources` 응답: 메타데이터 드롭다운용 `scope_key`(=read 해소값 `scope_key or key`) 노출. health 용 `_sk`(=`_dsr.scope_key` 항상-해시)와 분리.
  - `src/static/admin.js`: scope 드롭다운 value=노출 scope_key(read축)·표시=라벨. 메타데이터 탭 게이트 `kb.ingest.manual`→`+kb.sample.curate` OR(RISK 해소 — 샘플 큐레이터 도달). bootstrap 저장 `source:'bootstrap'`(NIT 해소 — provenance). cache-buster `?v=20260624-scope-key-unify`(admin.html/index.html).
  - `tests/test_metadata_phase2.py`·`test_metadata_glossary_enum.py`: `_allow_scopes` fake 가 scope_key 필드 제공(write==read 축 모사). scope **양방향** 회귀 2 신규(DB=해시 허용·라벨 거부 / .env=라벨 허용·해시 거부 — v1 _dsr.scope_key 로직선 FAIL 하는 유효 가드).
- 비변경: read 측(feature-0002 agent_core/kb_metadata/sample_queries/insight) 0 — write 를 기존 read 축에 맞춤. write/read/insight 3자 동일 축(`scope_key 필드 or 라벨`).
- 보안: 적대 패널 2-lens 가 첫 fix 의 .env 축 반전 BLOCKER 적발 → 교정 → 재확인 agent RESOLVED(7항목, BLOCKER/MAJOR 0). 라벨 직접 POST 우회는 `_metadata_check_scope` 400 차단.
- Rollback: 3 지점(valid_scope_keys·datasources 응답·드롭다운) revert. 신규 테이블 0행이라 데이터 영향 없음(라벨 行 orphan 없음 — 백필 불요).
- Deploy: web 재빌드(app.py·admin.js·html). 마이그 없음. 死data 수정은 배포 후 라벨/해시 정합 라이브 재검증.
- Cross-ref: REV-20260624T160000-scope-key-unify / FUNCTION REQ-20260624-scope-key-unify / TASK-20260624-scope-key-unify / CHG-20260624T133000-item11-phase2(死data 잠복 도입) / ROADMAP ITEM-11·ITEM-10·ITEM-03.

## CHG-20260624T133000-item11-phase2 (TASK-20260624-item11-phase2 — ITEM-11 Phase 2: 테이블/컬럼 설명+주입+부트스트랩 / 샘플 admin, Major §12.3 — 보안 경계)
- Date: 2026-06-24 (ROADMAP dba-ai-nl2sql ITEM-11 Phase 2, **Major §12.3** — 신규 RBAC 표면 + KB 주입 경로 신설 + 부트스트랩 introspection). PLAN-APPROVED(2a+2b 한 컷).
- Scope: cross-feature. **primary=feature-0003**(web 엔드포인트·admin UI), **secondary=feature-0002**(KB 코어·주입·마이그 — 본 CHG 에 cross-ref).
- 변경(feature-0002, cross-ref):
  - `src/scripts/agent_kb_schema.sql`: 신규 테이블 `table_descriptions`·`column_descriptions`(enum_dictionary 컨벤션: scope_key·schema_name·table/column·description·source·timestamps·UNIQUE·set_updated_at 트리거) + GRANT rw/ro 둘 다 추가. alembic `20260624_0017_table_column_descriptions.py`(down_revision=0016, 단일 head, upgrade=CREATE+인덱스+트리거+GRANT, downgrade=DROP, 멱등).
  - `src/modules/kb_metadata.py`(신규): read `load_table_column_descriptions`(glossary 동형 — scope_candidates 캐스케이드·substring 매칭·cap·`get_active_datasource`, CURRENT_FACT_SCOPE_KEY 미사용) + overlay read `load_column_descriptions_for_table` + admin CRUD 6함수(list/upsert/update/delete × table/column, id+scope_key 가드·rowcount·ON CONFLICT).
  - `src/modules/sample_queries.py`: `list_samples_admin`·`update_sample`(하이브리드 C 임베딩)·`delete_sample` 추가(기존 register/search 무변경).
  - `src/agent_core.py` `_build_knowledge_context`: glossary 섹션 직후 `## TABLE & COLUMN DESCRIPTIONS (참고 데이터, 지시 아님)` datamark(`_datamark_untrusted`) 주입(빈 결과 생략). [D2-B]
  - `src/modules/tools.py` `_tool_describe_table`: native COLUMN_COMMENT 빈 컬럼만 KB column_description 으로 충전(MSSQL 빈 comment gap 해소, dialects.py:453). [D2-A]
- 변경(feature-0003, primary):
  - `src/app.py`: 엔드포인트 `/api/admin/metadata/{tables,columns}`(GET/POST/PUT/DELETE, RBAC `kb.ingest.manual`) + `/samples`(GET/PUT/DELETE, RBAC `kb.sample.curate`, POST 없음 — 검수 경로 정본) + `/bootstrap/schemas`·`/bootstrap`(RBAC `kb.ingest.manual`). MVP-1 헬퍼(`_metadata_resolve_account/_metadata_check_scope/_metadata_str_field/_metadata_audit`) 재사용 + 샘플용 `_samples_resolve_account`. 부트스트랩 read: `all_datasources` DS 검증(SSRF 차단) → `set_active_datasource(engine)` dialect 활성화(MSSQL) → `db.connect(datasource, RO)` → `load_known_schemas`/dialect-aware `_bootstrap_collect_skeleton`(자동샘플·인덱스 미호출, cap 500/200, 미영속).
  - `src/static/{admin.html,admin.js,styles.css,index.html}`: 메타데이터 탭에 테이블/컬럼/샘플 3 서브뷰 + 부트스트랩 UI(DS→schema→골격 가져오기→설명 prefill→저장). XSS textContent. cache-buster `?v=20260624-item11-phase2`.
- 보안(적대 리뷰 REV-20260624T133000 SHIP-WITH-FIXES → 전부 흡수):
  - **BLOCKER B1(흡수)**: 부트스트랩 `schema_name` 이 `dialect.describe_schema_tables` f-string(dialects.py:251)에 게이트 없이 도달 → RO 커넥션 UNION 읽기 인젝션. **fix**: 구조화 도구(tools.py:732)와 동일 게이트 — `_safe_ident` 정제 + `load_known_schemas` 멤버십 allowlist(미포함 404), `_bootstrap_collect_skeleton` 의 introspection 산출 tname 도 `_safe_ident`(방어심층). SQLi 거부 회귀 테스트 +1.
  - **MAJOR M2(흡수)**: alembic 0017 이 잘못된 위치(`src/alembic/`)에 생성 → 올바른 체인(`alembic/versions/`, down_revision=0016)으로 이동, stray dir 제거, 단일 head 검증.
  - **MINOR(수용)**: m1 샘플 PUT 임베딩 동기 호출(app층 timeout 가드 없음, 예외→stale 폴백이라 무한블록 아님) · m2 부트스트랩 컬럼 실패 silent · m3 data_type 엔진별 표기차(표시용). REFUTE 실패(안전): RBAC·scope/IDOR·SSRF(차단)·프롬프트 인젝션(datamark)·임베딩 하이브리드 C·SQLi 파라미터화(B1 외)·GRANT.
- Verification: `tests/test_metadata_phase2.py` **27/27**(RBAC 403·scope 400/격리·affected 404·멱등·audit·입력 cap·샘플 weight clamp·nl 중복 409·임베딩 분기·부트스트랩 RBAC/DS/**SQLi 거부**·주입 datamark) + MVP-1 `test_metadata_glossary_enum.py` 13/13 + 코어/보안 91/91 회귀 0. py_compile + node --check. PYTHONPATH=feature-0002/src:feature-0003/src.
- Rollback: alembic 0017 downgrade(DROP 2테이블) · 엔드포인트/코어/주입/오버레이/frontend revert. 신규 테이블 비어있어 무손실.
- Deploy: 마이그 0017 적용(superuser) + GRANT + ask-worker/web 재빌드. UI 라이브 검증 PB-0008(배포 후).
- **ITEM-11 부분 진행**: Phase 2 로 ITEM-11 의 잔여(테이블/컬럼 설명·describe 부트스트랩·샘플 admin) 구현 — ITEM-11 done.
- Cross-ref: REV-20260624T133000-item11-phase2 / FUNCTION REQ-20260624-item11-phase2 / ROADMAP ITEM-11(→done) / CHG-20260624T130000(MVP-1).

## CHG-20260623T031910-ai-claude-ds-conn-bg-decouple (TASK-20260623T031910, REQ-20260623-ds-conn-bg-decouple, Major §12.3)
- Date: 2026-06-23
- 요청(사용자, /_template:entry): `관리 콘솔 > 제품 > [각 항목]` 진입 시 연결 불안정 데이터소스 접근 시 timeout 까지 나머지 UI 갱신이 멈춤 → 모든 연결 확인을 백그라운드로 처리하고 내부 UI 갱신과 분리.
- 범위 결정(AskUserQuestion): 전체 분리(Layer 1+2) — 이벤트 루프 차단 해소 + conn_health 캐시 게이트 + 프론트 비차단 렌더/배지.
- 진단: `admin_datasource_databases`(GET `/api/admin/datasources/{key}/databases`, 제품 항목 진입 시 `_refreshAccessibleDbs` 호출)가 `async def` 안에서 동기 `_db.list_server_databases_classified()`(live connect, db.py 기본 8s)를 `asyncio.to_thread` 없이 호출 → FastAPI 이벤트 루프 전체 8s 블록 = 모든 요청 정지. preview + rule create/update 의 `_reconcile_one_db_rule`(async 핸들러서 동기 호출)도 동일. 백그라운드 `conn_health`(TASK-0250 캐시 3-state) 미사용 + `should_fast_fail` 은 `down` 만 즉시실패.
- 변경:
  - `src/app.py` — `admin_datasource_databases`: `from modules import conn_health as _ch` 추가. SSRF 후 `_ch.status_for(ds)` 캐시 먼저 읽어 `unstable`/`down` 이면 live connect 생략·`{databases:[], databases_classified:[], conn_status, degraded:true}` 즉시 반환(`?force=1` 시에만 실제 열거). 실제 열거 `await asyncio.to_thread(_db.list_server_databases_classified, …)` 오프로드 + 예외 시 `_ch.record_foreground_result(ds, False, None, "list_databases_failed")` 피드백 후 502. 성공 응답에 `conn_status`/`degraded:false` 추가(기존 `databases`/`databases_classified` 보존). `admin_create_product_db_rule`·`admin_update_product_db_rule`: `_reconcile_one_db_rule(conn, …)` 호출을 `await asyncio.to_thread(…)` 로 오프로드. `admin_preview_product_db_rule`: `list_server_databases_classified` 호출을 `await asyncio.to_thread(…)` 로 오프로드.
  - `src/static/admin.js` — `renderProductDetail` 내 신규 `_setAccessDbDegraded(info)`(picker 위 `.admin-db-degraded-note` 배너 "연결 불안정/끊김 — DB 목록 보류 + [새로고침]", `role="status"`, 클릭 시 `?force=1` 재시도). `_refreshAccessibleDbs(key, opts={})` — `opts.force` 시 `?force=1` 부착, `r.degraded` 응답 시 빈 목록 + 배너, catch 시 `degraded=true` 로 재시도 배너 유지. 정상 경로 classified/lockedChips 로직은 else 블록으로 재배치(byte-equivalent).
  - `src/static/styles.css` — `.admin-db-degraded-note` + `.admin-db-degraded-refresh`(danger 토큰 기반 배너/버튼).
  - `src/static/admin.html` — 캐시버스터 `styles.css?v=20260623-ds-conn-bg-decouple` + `admin.js?v=20260623-ds-conn-bg-decouple`.
- 비변경: `_reconcile_one_db_rule` 내부 로직(M3/M4/M5)·`conn_health` 모듈·RBAC·스키마·엔드포인트 contract·`/db-insights`(sync def → 이미 threadpool, PG insight 읽기라 live datasource connect 아님) 0.


## CHG-20260619T120000-ai-claude-db-rule-pending-batch (TASK-20260619T120000, REQ-20260619-0331, Major §12.3 — 보안 경계)
- Date: 2026-06-19
- 요청(사용자, /_template:entry): 관리 콘솔 모든 변경을 pending → 일괄적용으로 구성·정책에 검증과정 명시·프로젝트 메모리 기억. 보고된 위배 = 정규식 자동 규칙 수정 시 즉시 반영.
- 범위 결정(AskUserQuestion): 범위 A — 규칙 편집 동작만 pending, 확정 규칙의 백그라운드 자동 동기화는 보존.
- 변경:
  - `src/static/admin.js` — `adminState.pending.productDbRules` 스토어 + 헬퍼(`_dbRuleStageKey`/`_ensureDbRulePending`/`_getDbRulePending`/`_dbRulePendingEntryEmpty`/`_settleDbRulePending`/`productDbRuleDirtyCount`) 신설. `pendingChangeCount`·`refreshPendingUI`(detail "제품 규칙 N")·`buildPendingWidgetBody`·`cancelAllPending`·loadAdminData stale GC 에 통합. 규칙 에디터(`renderProductDetail` 내 `cov-db-rule`)의 add/edit/delete/approve 핸들러를 즉시 `apiFetch` → pending 스테이징으로 재배선. `_buildRuleCard` optimistic 오버레이(수정 대기=새 패턴+배지+수정취소 / 삭제 대기=dim+삭제취소 / 승인 대기 토글) + `_buildStagedCreateCard`(추가 대기). `applyAllPending` 에 dbRuleEntries replay(creates POST → updates PUT → approves approve-pending → deletes DELETE, entryFailed 아니면 정리) + early-return guard 포함. `reloadProductAfterRuleChange`(즉시 reload 헬퍼) 제거.
  - `src/static/styles.css` — `.cov-db-rule-card.is-staged-{create,update,delete}` + `.cov-db-rule-card-badge.is-{create,update,delete}` + `.cov-db-rule-approve.is-staged` + `.cov-db-rule-pending-tag`.
  - `src/static/admin.html` — admin.js 캐시버스터 `?v=20260619-llm-quota` → `?v=20260619-db-rule-pending`.
  - `src/app.py` — `admin_list_product_db_rules`(GET `/db-rules`)에서 `_reconcile_product_db_rules(trigger="view")` 블록 제거(조회는 allowlist 무변경). docstring 갱신. (`_reconcile_product_db_rules` 헬퍼 자체는 백그라운드 경로용으로 보존 — 현재 호출자 0, REVIEW 기록.)
  - `tests/verify_db_rule_pending.mjs` — jsdom 단위 테스트 신설(18).
  - `docs/CONVENTIONS.md §10.7` 신설(정책 본체는 repo docs).
- 비변경: rule reconcile/preview 로직·on-write reconcile·백그라운드 reconcile 루프(`_start_db_rule_reconcile_loop`)·RBAC 카탈로그·DB 스키마·엔드포인트 shape.

## CHG-20260618T062406-ai-claude-release-notes-scope-scroll-evidence (TASK-20260618T061520 후속 docs-only — PB-0008 evidence)
- Date: 2026-06-18
- Scope: docs 전용(TEST §4 Run PASS + TASK 마감). 코드·자산·RBAC 0.
- 변경: TEST.md §4 에 양 화면 PB-0008 PASS 기록 — 작업 화면 칩=[전체/작업/공통]·admin 항목 0(AC-0582), 관리 콘솔 pane overflow-y:auto·scrollH 1418>clientH 801·하단 도달·admin 23 무회귀(AC-0583). TASK 마감.
- Why: 화면 정본(PB-0008 computed 값) 영속화 + CHECK#13 충족.
- Verification: computed 값 authoritative. 스크린샷은 relay 폰트로드 transient timeout(직전 사이클 시각 베이스라인 보유).
- Rollback: 불요(docs-only). 코드 `e812c9d` 배포됨.
- Deploy: 불요.

## CHG-20260618T061520-ai-claude-release-notes-scope-scroll (TASK-20260618T061520 — 릴리즈 노트 표면별 영역 + 관리 콘솔 스크롤)
- Date: 2026-06-18
- Scope: frontend-only. `release-notes.js`·`app.js`·`styles.css` + index/admin 캐시버스터 + 테스트. 백엔드·RBAC·스키마·데이터 0.
- 변경:
  - `release-notes.js` — `render(container, opts)` `opts.areas` 화이트리스트: items 선필터+빈 그룹 제거, 필터 칩 allowed 영역만(전체+해당). 기본=전체(무회귀).
  - `app.js` — 작업 화면 release-notes 렌더에 `{areas:["work","common"]}` → area=admin 노트·'관리 콘솔' 칩 숨김.
  - `styles.css` — `.admin-pane[data-admin-pane="release-notes"].is-active{overflow-y:auto;overflow-x:hidden}`(TASK-0167 동형) → 관리 콘솔 pane 세로 스크롤.
  - index.html/admin.html — styles.css·app.js·release-notes.js `?v=20260618-rn-scope-scroll` bump.
  - `tests/verify_release_notes.mjs` — 작업화면 영역 제한 + 스크롤 규칙 단언 추가(34/34).
- Why: 사용자 요청 — ①작업 화면서 관리 콘솔 릴리즈 노트 숨김 ②관리 콘솔 하단 항목 스크롤 불가 해소.
- Verification: `verify_release_notes.mjs` 34/34 + `node --check`. 화면 정본 PB-0008(재배포 후).
- Rollback: 옵션/규칙/버전 revert(무손실).
- Deploy: web 재배포(deploy_scope: included).

## CHG-20260618T051005-ai-claude-release-notes-evidence (TASK-20260618T044611 후속 docs-only — PB-0008 Windows-browser evidence)
- Date: 2026-06-18
- Scope: docs 전용(TEST §4 Windows-browser Run PASS + TASK 마감). 코드·정적자산·스키마·RBAC 0.
- 변경: TEST.md §4 에 양 화면(작업 화면 프로필 탭 + 관리 콘솔 카테고리) PB-0008 Windows-browser 재실측 PASS 기록 — 접힘 트랩 1차 적발→hotfix→재실측 `display:none`/height 0 확정, 토글·영역 필터(작업 40/관리 23)·모두 펼치기·누출어 0 서빙. TASK 마지막 체크박스 마감. evidence `artifacts/pb0008-release-notes/{work-screen,admin}-release-notes.png`(git 비추적).
- Why: 화면 정본(PB-0008) 결과 영속화 + CHECK#13(Windows-browser) 충족.
- Verification: 본 기록 자체가 검증 산출물. 코드 무변경(회귀 0).
- Rollback: 불요(docs-only).
- Deploy: 불요(코드 무변경, 이미 `091280e` 배포됨).

## CHG-20260618T050409-ai-claude-release-notes (TASK-20260618T044611 후속 — PB-0008 적발 접힘 버그 + CSS 캐시버스터)
- Date: 2026-06-18
- Scope: frontend CSS hotfix. `styles.css` 1규칙 + `index.html`/`admin.html` 캐시버스터 + 테스트 가드 1건. 로직·백엔드·RBAC 0.
- 변경:
  - `src/static/styles.css` — `.rn-group-body[hidden] { display: none; }` 추가. **PB-0008 적발**: `.rn-group-body{display:flex}` 가 UA `[hidden]{display:none}` 를 specificity 동률(둘 다 0,1,0)+소스순서로 덮어써, 접힌 그룹(hidden 속성·aria-expanded=false)이 실제 화면에선 여전히 `display:flex`(펼침)로 보였다. class+attr (0,2,0) 명시 규칙으로 우선권 확보 → 접힘 정상. (메모리의 권한 grid `[hidden]` override 트랩과 동류 — jsdom 은 cascade 미계산이라 못 잡고 PB-0008 만 적발.)
  - `src/static/index.html` · `admin.html` — `styles.css?v=` 를 `20260618-release-notes` 로 bump. 신규 `.rn-*` 스타일을 기존 사용자(캐시된 styles.css) 에게도 강제 재요청(미bump 시 기존 cache-buster URL 동일 → stale CSS → RN 무스타일).
  - `tests/verify_release_notes.mjs` — `.rn-group-body[hidden]{display:none}` 가드 소스 단언 추가(jsdom cascade 비검출 보완, 27/27).
- Why: PB-0008 Windows-browser 실측에서 접힌 그룹 computed `display:flex` 확인(접힘 무력화). 화면 정본 게이트가 jsdom 통과 버그를 적발.
- Verification: `verify_release_notes.mjs` 27/27 + `node --check`. 재배포 후 PB-0008 재실측(접힌 그룹 computed display:none).
- Rollback: 규칙/버전 revert(무손실).
- Deploy: web 재배포(deploy_scope: included).

## CHG-20260618T044611-ai-claude-release-notes (TASK-20260618T044611 — 릴리즈 노트: 작업 화면 프로필 탭 + 관리 콘솔 카테고리)
- Date: 2026-06-18
- Scope: frontend additive. 신규 정적 2파일 + index.html/admin.html/app.js/admin.js/styles.css + 신규 jsdom 테스트. 백엔드·RBAC·스키마·엔드포인트·DB·신규 권한 **0**.
- 변경:
  - 신규 `src/static/release-notes-data.js` — 릴리즈 노트 콘텐츠(정적 큐레이션). `window.RELEASE_NOTES`, 일자별 11블록(2026-06-04~06-18 상세 + "그 이전" 마일스톤), 항목 = type(new/improved/fixed)+area(work/admin/common)+title+detail. git 출시 이력을 사용자 친화 문장으로 풀고 내부 정보(cutover/PG/RBAC 내부/SSRF/KEK/livelock 등) 비노출·"안정성/보안 개선"으로 간략화.
  - 신규 `src/static/release-notes.js` — 공유 렌더러 `window.ReleaseNotes.render(container)`. 일자별 그룹 접기(기본 최신 1개 펼침)·영역 필터 칩(전체/작업/관리/공통)·모두 펼치기/접기. 전 텍스트 `textContent`(XSS-safe).
  - `src/static/index.html` — 프로필 드로어 `drawer-tab[data-profile-tab="release-notes"]` + pane `#releaseNotesBody` + 스크립트 2종(`?v=20260618-release-notes`).
  - `src/static/app.js` — `switchProfileTab` 에 `release-notes` lazy 렌더 디스패치.
  - `src/static/admin.html` — 시스템 그룹에 `admin-tab[data-admin-tab="release-notes"]` + pane `#adminReleaseNotesBody` + 스크립트 2종.
  - `src/static/admin.js` — `switchTab` 에 `release-notes` 렌더 디스패치(`ADMIN_TAB_PERMISSIONS` 미등록 → 콘솔 진입자 모두 노출).
  - `src/static/styles.css` — `.release-notes`/`.rn-*` 스타일(디자인 토큰 재사용, 종류·영역 배지).
  - 신규 `tests/verify_release_notes.mjs` — jsdom 검증.
- Why: 사용자 요청(2026-06-18) — 각 작업 내역·개선을 일반 사용자가 파악하도록 릴리즈 노트 제공, 역할/권한별 진입점 2개, 일자별 접기/탐색.
- Verification: `node --check` 4파일 PASS + `tests/verify_release_notes.mjs` 26/26 PASS. 화면 정본 = PB-0008 Windows-browser(배포 후 양 화면 실측, 별 evidence cycle).
- Rollback: 신규 파일 제거 + index/admin/app/admin.js/styles.css 추가분 revert(무손실, 비파괴).
- Deploy: web 재배포(deploy_scope: included) — 정적 자산 baked.

## CHG-20260618T031450-ai-claude-product-picker-search-evidence (TASK-20260618T024517 후속 docs-only — PB-0008 Windows-browser evidence)
- Date: 2026-06-18
- Scope: docs 전용(TEST/TASK/MODIFY/REVIEW). 코드·정적자산·스키마·RBAC 0.
- 변경: TASK-20260618T024517(제품 선택 드롭업 명칭 검색 필터)의 "머지 → 배포 → PB-0008" 잔여를 **완료**로 갱신(PR #327 squash main `ebd2849` → `make dc-build SERVICE=web`+`up -d --no-deps --force-recreate web` healthy, /healthz git_commit=ebd2849 → PB-0008 Windows-browser PASS). TEST.md §4 에 Windows-browser Run 실측 기록: pinned 10개(≥임계 6)→검색 입력 노출·placeholder·sticky top:0·자동 focus·`dk_`→2건(DK_DEV·DK_QA)·`zzzznotexist`→0건+"검색 결과가 없습니다"·비움→11건 복원(VERDICT PASS). evidence `artifacts/pb0008-product-picker-search/search-filter-dk.png`(1249×836, git 비추적).
- Why: 화면 정본(PB-0008) 검증 결과를 문서에 영속화 + CHECK#13(Windows-browser) 충족.
- Verification: 본 기록 자체가 검증 산출물. 코드 무변경(회귀 0).
- Rollback: 불요(docs-only). 코드는 이미 `ebd2849` 배포됨.
- Deploy: 불요(코드 무변경).
## CHG-20260618T031747-ai-claude-ds-list-engine-icon-evidence (TASK-20260618T030534 후속 docs-only — PB-0008 Windows-browser evidence)
- Date: 2026-06-18.
- 변경: 코드 0. TEST.md §3 Windows-browser Run + TASK.md 마감 체크박스 + REVIEW evidence 항목. main `8a2c886`(PR #332) 배포 후 실 Windows Chrome PB-0008 PASS 기록.
- 내용: 데이터소스 목록 18행 각각 children `[cb, dot, engIcon, main]`(엔진 아이콘 도트 우측)·grid `13px 9px 16px 225px`(4열)·MySQL #00758F / Microsoft SQL Server #EE352C 브랜드색·아이콘 컬럼 leftAlignSpread=0px(정렬 무붕괴) 실측. evidence `artifacts/pb0008-ds-list-engine-icon/ds-list-engine-icons.png`.
- 판단: docs-only evidence 기록이라 코드 리뷰/외부 패널 불요. 회귀 위험 0.

## CHG-20260618T024517-ai-claude-product-picker-search (TASK-20260618T024517 — 제품 선택 드롭업 명칭 검색 필터)
- Date: 2026-06-18
- Scope: frontend-only — feature-0003-agent-web-ui `src/static/app.js`(검색 입력 빌더+필터+포커스+data-search) + `src/static/styles.css`(검색 입력/sticky/결과없음) + `src/static/index.html`(캐시버스터 2곳). 백엔드·스키마·RBAC·엔드포인트·데이터 0.
- 내용: 작업 화면 요청문 텍스트박스의 제품 선택 드롭업(`#productDropupMenu`)에 제품 명칭 검색 필터를 추가. ① app.js — `PRODUCT_DROPUP_SEARCH_MIN`(=6) 상수 + `renderProductDropupMenu` 리팩토링(pinned 제품 ≥ 임계 시 `buildProductDropupSearch()` 삽입, `.product-dropup-no-result` 동적 안내 추가, `products.filter(id)` 로 pinned 분리) + 신규 `buildProductDropupSearch()`(input[type=text].product-dropup-search, input 이벤트→`filterProductDropupItems`) + 신규 `filterProductDropupItems(query)`(항목 `.hidden` 토글 + no-result 토글, 재렌더 없이 포커스/한글 IME 유지) + `buildProductDropupItem` 에 `data-search`(소문자 라벨=product_key+제품명) 부여 + `openProductDropup` 에 검색 입력 자동 `focus()`. ② styles.css — `.product-dropup-search-wrap`(position:sticky top:0), `.product-dropup-search`(+:focus 보더/그림자, ::placeholder), `.product-dropup-no-result`. ③ index.html — styles.css/app.js 캐시버스터 `?v=20260618-product-picker-search`.
- Why: 사용자 요청 — 제품이 많아질수록 드롭업에서 원하는 제품 탐색이 번거로움. 명칭(product_key/한글명) 검색으로 즉시 좁히기. 제품이 적을 때는 입력칸을 숨겨 단순성 유지(무회귀). `.hidden`(글로벌 `display:none !important`) 토글이라 별도 숨김 CSS 불필요.
- Verification: `tests/verify_product_picker_search.mjs` 27/27 PASS(jsdom 격리) + `node --check app.js`. 화면 정본 = PB-0008 Windows-browser(배포 후, 라이브 제품 13개라 검색박스 자연 노출).
- Rollback: 3개 정적 파일 revert(비파괴 추가라 단순).
- Deploy: web 재빌드(deploy_scope: included — FIRST_REQUEST.md 전역 선언).
- 식별자 메모: 고병렬 동시세션 origin/main rebase(2회) 시 최초 REQ-0288/AC-0572·0573 이 타 세션 선점과 충돌 → grep max 재번호 REQ-20260618-0317/AC-0574·0575([[feedback_feature_doc_id_grep_max]]). docs 충돌은 --ours(타 세션 항목 보존)+내 항목 재삽입으로 keep-both.
## CHG-20260618T030534-ai-claude-ds-list-engine-icon (TASK-20260618T030534 — 데이터소스 목록 행 엔진 서비스 아이콘)
- Date: 2026-06-18.
- Scope: frontend admin.js(`_dsRenderList`) + styles.css + admin.html(cache-buster ×2). 백엔드·RBAC·스키마·데이터 0.
- 내용: TASK-20260618T022006(엔진 드롭다운) 후속. `관리 콘솔 > 데이터소스` 목록 각 행의 네트워크 연결 도트 **우측에** 엔진 서비스 브랜드 아이콘 추가. ① `_dsRenderList` 가 `engineMeta(ds.engine)`(드롭다운과 동일 출처)의 아이콘을 `span.ds-list-engine-icon`(브랜드색·role=img·aria-label "엔진: <label>")으로 만들어 `row.append(cb, dot, engIcon, main)`. ② styles.css `#datasourceList .admin-list-row` grid `auto auto 1fr`→`auto auto auto 1fr`(4열 cb·dot·engIcon·main 1:1, 행 정렬 보존) + `.ds-list-engine-icon`(16px). 기존 엔진 텍스트 배지는 유지(additive). ③ admin.html admin.js+styles.css 캐시버스터 `?v=20260618-ds-list-engine-icon`(공유 styles.css 변경 — 직전 task cache-buster 교훈 적용).
- Why: 사용자 요청 "데이터소스 목록에서도 식별하기 쉽도록 네트워크 연결 뱃지 우측에 [엔진 아이콘] 구성".
- Verification: jsdom `verify_ds_list_engine_icon.mjs` 17 PASS + node --check. 화면 정본 = PB-0008(배포 후).
- Rollback: admin.js engIcon 블록·`row.append` 4-인자, styles.css 4열 grid·`.ds-list-engine-icon`, admin.html cache-buster revert.
- Deploy: web 재빌드 + 컨테이너 재생성(deploy_scope: included).

## CHG-20260618T030014-ai-claude-engine-dropdown-evidence (TASK-20260618T022006 후속 docs-only — PB-0008 Windows-browser evidence)
- Date: 2026-06-18
- 변경: 코드 0. TEST.md §3 Windows-browser Run 추가 + TASK.md 마지막 체크박스 완료(마감) + REVIEW evidence 항목. feature(PR #325 main `da227eb`) + cache-buster fix(PR #326 main `071020c`) 배포 후 실 Windows Chrome PB-0008 PASS 사실 기록.
- 내용: 데이터소스 탭 → '+ 새 데이터소스' → 엔진 드롭다운 열림·옵션 2개(MySQL #00758F·Microsoft SQL Server #EE352C 브랜드 아이콘+색)·선택 시 트리거/포트 placeholder(1433) 갱신 실측. 1차에서 styles.css cache-buster 누락(아이콘 52px·CSS 미적용) 적발→CHG-20260618-0316 으로 수정→재배포 후 18px·border 1px 해소까지 기록. evidence `artifacts/pb0008-engine-dropdown/{engine-dropdown-open,engine-mssql-selected}.png`.
- 판단: docs-only evidence 기록이라 코드 리뷰/외부 패널 불요. 회귀 위험 0.

## CHG-20260618-0316
- Date: 2026-06-18 (TASK-20260618T022006 후속 fix — 엔진 드롭다운 styles.css cache-buster 누락 보정).
- Scope: frontend admin.html + index.html(styles.css cache-buster 2곳). 코드 로직·CSS 본문·백엔드·데이터 0.
- 내용: TASK-20260618T022006 이 `styles.css` 에 `.engine-picker*`/`.engine-option*`/`.engine-icon` 규칙을 추가했으나, 이를 링크하는 페이지의 `styles.css?v=` cache-buster 를 안 올려, 캐시된 브라우저가 옛 styles.css(엔진 규칙 0)를 계속 수신 → 드롭다운이 미스타일(아이콘 ~52px·버튼 border/padding 0)로 렌더되던 것. admin.html(`?v=20260616-task0292-admin-sidebar-vscroll`)·index.html(`?v=20260616-task0289-runtime-transparency`) 의 styles.css cache-buster 를 둘 다 `?v=20260618-engine-dropdown` 으로 bump(공유 styles.css 변경 → 전 consumer 페이지 bust).
- Why: PB-0008 실 Windows Chrome 1차 검증에서 `engineIconCssRuleLoaded=false`·아이콘 52px·버튼 border 0px 로 미스타일 적발(jsdom 은 캐시·실 stylesheet 미재현이라 못 잡음 — PB-0008 canonical 게이트의 본령).
- Verification: 재배포 후 PB-0008 재검증(`.engine-icon` width 18px·버튼 border/padding·브랜드색). 코드 로직 무변경이라 jsdom/단위 영향 0.
- Rollback: 2 파일 cache-buster 문자열 revert.
- Deploy: web 재빌드 + 컨테이너 재생성(deploy_scope: included).

## CHG-20260618T022846-ai-claude-admin-status-filter-evidence (TASK-20260618T021526 후속 docs-only — PB-0008 Windows-browser evidence)
- Date: 2026-06-18
- Scope: docs 전용(TEST/TASK/MODIFY/REVIEW). 코드·정적자산·스키마·RBAC 0.
- 변경: TASK-20260618T021526(역할·제품 탭 활성/비활성 필터)의 "verify-completion → 머지 → 배포 → PB-0008" 잔여를 **완료**로 갱신(PR #321 squash 머지 main `6da40dc` → `make dc-build SERVICE=web`+`up -d --no-deps web` healthy → PB-0008 Windows-browser PASS). TEST.md §4 에 Windows-browser Run 실측 기록: 제품 탭 전체 13행 = 비활성 6(전부 `is-disabled`·inactive 배지) + 활성 7(전부 활성) 정확 분할, 역할 탭 6행(active=6/inactive=0), 버튼 `is-active` 단독 토글, 계정 탭 패턴 1:1 정합(VERDICT PASS). evidence `artifacts/pb0008-admin-status-filter/{products-inactive-filter,roles-active-filter}.png`(git 비추적 artifacts).
- Why: 직전 cycle 의 화면 정본(PB-0008) 검증 결과를 문서에 영속화 + CHECK#13(Windows-browser) 충족.
- Verification: 본 기록 자체가 검증 산출물. 코드 무변경(회귀 0).
- Rollback: 불요(docs-only). 코드는 이미 `6da40dc` 배포됨.
- Deploy: 불요(코드 무변경).

## CHG-20260618T021526-ai-claude-admin-status-filter (TASK-20260618T021526 — 관리 콘솔 역할·제품 탭 활성/비활성 필터 추가)
- Date: 2026-06-18
- Scope: frontend-only — feature-0003-agent-web-ui `src/static/admin.html`(역할·제품 toolbar 2곳) + `src/static/admin.js`(상태 2 + 술어 2 + 배선 2). 백엔드·스키마·RBAC·엔드포인트·CSS 0.
- 내용: 관리 콘솔 `역할`·`제품` 탭에 계정 탭과 동형의 활성/비활성 필터를 추가. ① admin.html — 두 toolbar 의 검색창 뒤에 `admin-filter-group`(전체/활성/비활성, `data-role-filter`/`data-product-filter`) 추가(계정 탭 `data-account-filter` 마크업 1:1, 단 역할·제품엔 soft-delete 가 없어 "삭제됨" 버튼 제외 → 3버튼). ② admin.js — `adminState.roleFilter`/`productFilter`(기본 "all") 신설; `filteredRoles()`/`filteredProducts()` 가 검색어 매칭 앞에서 상태로 게이트(active=`is_active` true 만, inactive=false 만); `filteredProducts()` 의 `if(!q) return slice()` 단축 제거(빈 검색에도 필터 적용); `[data-role-filter]`·`[data-product-filter]` 버튼 핸들러를 계정 필터와 동형으로 배선.
- Why: 사용자 요청 — 계정 탭에만 있던 활성/비활성 필터를 역할·제품 탭에도. 기본 "전체"라 기존 동작 무회귀.
- Verification: node --check admin.js PASS + `scripts/verify_admin_status_filter.mjs` 11/11 PASS(실 `filteredRoles`/`filteredProducts` 본문 추출 실행 — all/active/inactive × 검색 교집합 × 빈검색 회귀). 화면 정본 = PB-0008 Windows-browser(배포 후).
- Rollback: admin.html 2 filter-group 제거 + admin.js 상태 2·술어 분기·배선 2 revert(`filteredProducts` 단축 복원). 시각/필터만 원복, 데이터·권한 무영향.
- Deploy: web 재빌드 1 이미지(프론트 baked). deploy_scope: included.
## CHG-20260618-0315
- Date: 2026-06-18 (TASK-20260618T022006 — 관리 콘솔 데이터소스 '새 항목' 엔진 선택 = 아이콘 드롭다운).
- Scope: frontend admin.js + styles.css + admin.html(cache-buster). 백엔드·스키마·RBAC·엔드포인트·데이터 0.
- 내용: `관리 콘솔 > 데이터소스 > 새 데이터소스` 폼의 엔진 입력을 자유 텍스트 input → **아이콘 드롭다운**으로 전환. ① admin.js `ENGINE_CATALOG`(mysql|mssql — 라벨·기본포트·브랜드색·아이콘) + `engineMeta()`(미지원/공백/null→mysql 폴백, 백엔드 기본값 정합) + `_dsBuildEngineField`(아이콘+라벨 트리거, role=listbox/option·aria-selected·↓↑/Enter/Esc·hidden valueHolder) 신설. ② `_dsRenderForm` 의 엔진 필드를 드롭다운으로 교체 — save 핸들러는 `inputs.engine.value`(hidden) 를 그대로 읽어 POST/PATCH `body.engine` **무변경**(텍스트 input 의 `.value` 계약 보존). 엔진 변경 시 포트 placeholder=기본포트(값 강제변경 안 함). ③ 아이콘 = 공식 브랜드 마크 **inline SVG baking**(외부 CDN 핫링크 0 — sparkline/identicon 정합): MySQL=simple-icons 돌고래(#00758F)·MSSQL=devicon SQL Server(#EE352C), `fill=currentColor`+`.engine-icon` color. ④ styles.css `.engine-picker*`/`.engine-option*`/`.engine-icon` — 목록은 admin-db-picker 처럼 inline-flow(absolute 금지, `.admin-detail-col` overflow 클리핑 회피 TASK-0240).
- Why: 사용자 요청(/_template:entry) — 엔진을 드롭다운으로 선택 + 각 엔진 서비스 아이콘으로 식별 용이. 기존 자유 텍스트는 오타 가능 + 식별 보조 없음.
- Verification: jsdom `verify_engine_dropdown.mjs` 36 PASS(드롭다운 구조·옵션별 svg·hidden 값 계약·선택→repaint/aria/onChange·engineMeta 폴백·CSS inline-flow) + node --check. outside-voice 적대 리뷰 SHIP(REV-20260618-0315, 8가설 전부 REFUTED).
- Rollback: 3 파일 revert(admin.js ENGINE_*/`_dsBuildEngineField`/`_dsRenderForm` 필드, styles.css `.engine-*`, admin.html cache-buster) — 백엔드 영향 0.
- Deploy: web 재빌드(deploy_scope: included). 라이브 검증 = PB-0008 Windows-browser(드롭다운 열림·브랜드 아이콘 렌더·선택 반영).

## CHG-20260618T011645-ai-claude-date-group-collapse-evidence (TASK-20260618T010417 후속 docs-only — PB-0008 Windows-browser evidence)
- Date: 2026-06-18
- Scope: docs 전용(TEST/TASK/REPORT/MODIFY/REVIEW). 코드·정적자산·스키마·RBAC 0.
- 변경: TASK-20260618T010417 의 "verify-completion → 머지 → 배포 → PB-0008" 잔여를 **완료**로 갱신(PR #319 squash 머지 main `32b5e8f` → web 재배포 healthy → PB-0008 Windows-browser PASS). TEST.md §4 에 Windows-browser Run 실측 기록: 첫 진입 6개 날짜 그룹 중 가장 최근 "6월 10일 (수)"만 펼침·나머지 5개 접힘(VERDICT PASS), clean-room `localStorage.clear()`→reload seed 매-진입 재발화 + 날짜키 비영속(reload 후 `mad.collapsedGroups.v1`=`["__others__"]`만) 실증, 세션 내 토글 1회-게이트 존중 PASS. evidence `artifacts/pb0008-date-group-collapse/entry-recent-only-expanded.png`(git 비추적 artifacts).

## CHG-20260618T010417-ai-claude-date-group-collapse (TASK-20260618T010417, 작업 화면 좌측 대화목록 첫 진입 시 최근 일자 그룹만 펼침)
- Date: 2026-06-18
- Scope: frontend-only. 백엔드·RBAC·스키마·엔드포인트·데이터 0.
- `src/static/app.js` — ① 모듈 스코프 `let _dateGroupsSeededThisLoad = false` + `_seedDateGroupsCollapsedOnce(sortedDateKeys)` 신설(`_seedOthersCollapsedOnce` 직후). `sortedDateKeys[0]`(최근)은 `state.collapsedDateGroups.delete`(펼침 보장), 나머지는 `add`(접힘). 빈 키면 플래그 미설정(다음 렌더 재시도). `_saveCollapsedGroups` 미호출(비영속, 세션 단위). ② `renderConversationList` 의 `sortedDateKeys` 정렬 직후·`forEach` 렌더 전에 `_seedDateGroupsCollapsedOnce(sortedDateKeys)` 1회 호출.
- `src/static/index.html` — app.js 캐시버스터 `?v=20260616-conv-entry-defaults` → `?v=20260618-date-group-collapse`.
- `tests/verify_date_group_collapse.mjs` — 신규 순수 node 회귀(22 케이스). set 조작 로직이라 jsdom 불필요.
- 근거: 사용자 요청(2026-06-18) "처음 진입 시 최근 일자 제외 나머지 접힘". 사용자 결정으로 매 reload 재적용(날짜 키 상대성 → 영구 seed 부적합). 타 계정 그룹 `_seedOthersCollapsedOnce` 와 직교. 판단 상세 REV-20260618T010417-ai-claude-date-group-collapse.

## CHG-20260617T095122-ai-claude-account-insight-complete (cross-feature, feature-0002 TASK-20260617T095122 주관 — fork 마커)
- `src/app.py` — `_mark_conversation_forked(conversation_id, source_id)` 신설 + `_fork_conversation_impl` owner 부여 직후 호출. fork 본의 `agent_runtime.core_conversations.forked_from_conversation_id` 를 소스 대화 id 로 set(best-effort, PG 전용). 근거: account insight 회상/추출이 fork 본을 배제(fork 는 타 계정 메시지를 복사+owner 재귀속하므로 owner 격리만으론 cross-account 누출). 정본 feature-0002 [DESIGN-account-insight-recall.md](../../feature-0002-agent-core/docs/DESIGN-account-insight-recall.md) §10 G1. 컬럼은 feature-0002 alembic 0010.

## CHG-20260617T060740-ai-claude-task0295-pb0008-evidence (TASK-0295 후속 docs-only — PB-0008 evidence)
- Date: 2026-06-17
- Scope: docs 전용(TEST/MODIFY/REVIEW/TASK). 코드/정적자산/스키마/RBAC 0.
- 변경: TASK-0295 의 "verify-completion → 머지 → 배포 → PB-0008" 잔여를 **완료**(PR #303 머지 main `3fa87e8` → web 재배포 healthy → PB-0008 Windows-browser PASS)로 갱신. TEST.md §4 에 Windows-browser Run 실측 기록: 부분 회수(admin role `product.access.mv` 회수 시 `/api/session` products 8→7·MV 제거·MV_QA 유지 + 드롭업 DOM 7개·MV 부재), 빈목록(전체 회수 시 0개 + "접근 가능한 제품이 없습니다" 안내 렌더), 권한 복원. evidence `artifacts/pb0008-task0295/{mv-revoked-picker,all-revoked-empty}.png`.
- 검증: PB-0008 실측(win-browser eval — `/api/session` products + 드롭업 메뉴 DOM 집계, DB 권한 회수/복원 대비). 코드 무변경.
- Files: unit/feature-0003-agent-web-ui/docs/{TEST,MODIFY,REVIEW,TASK}.md

## CHG-20260617T052414-ai-claude-task0295-product-list-rbac (TASK-0295 — 작업 화면 제품 목록 product.access RBAC 게이트)
- Date: 2026-06-17
- Scope: feature-0003-agent-web-ui — backend(`src/app.py`) + frontend(`src/static/app.js`·`styles.css`) + 테스트. **신규 RBAC 권한 0**(기존 동적 `product.access.<key>` 재사용). 스키마/엔드포인트 무변경.
- 변경:
  - backend `src/app.py`: 신규 `_filter_products_for_account_access(account, products)`(product_key 기반 `_account_has_product_access` lookup, conn 불필요 — account.permissions 캐시만) + `_coerce_default_product_id(default_pid, products)`(default 가 접근 목록 밖이면 첫 접근 가능 제품으로 보정, 빈 목록=0). 작업 화면 2곳(`/api/session`·`/api/auth/me`)에서 `_list_products(include_inactive=False)` 직후 필터+보정 적용(`_attach_product_conn_status` 전 → 권한 없는 제품 연결 probe 회피). admin 4곳(`include_inactive=True`) 무변경.
  - frontend `src/static/app.js`: `renderProductDropupMenu` 에 접근 가능 제품 0건 시 "접근 가능한 제품이 없습니다" 안내(`.product-dropup-empty`). 제품 목록 렌더는 `state.products` 순회라 백엔드 필터로 자동 정합(추가 변경 0).
  - frontend `src/static/styles.css`: `.product-dropup-empty`(muted italic) 추가.
  - test `tests/test_product_list_rbac.py`: 순수 9건(필터·default 보정·정적 호출처 2곳).
- 검증: 단위 9/9 PASS(agent 이미지 `import app`, DB 없이) + py_compile PASS + 작업화면 필터 호출 정확히 2곳 정적 검증. outside-voice·PB-0008 후속.
- Files: unit/feature-0003-agent-web-ui/src/app.py, src/static/app.js, src/static/styles.css, tests/test_product_list_rbac.py, docs/{FUNCTION,TASK,MODIFY,REVIEW,TEST}.md

## CHG-20260617T040000-ai-claude-task0293-profile-icons-pb0008 (TASK-0293 후속 docs-only — PB-0008 evidence)
- Date: 2026-06-17
- Scope: docs 전용(TEST/TASK/MODIFY/REVIEW). 코드/정적자산/스키마/RBAC 0.
- 변경: TASK-0293 의 "잔여: verify-completion·머지·배포·PB-0008" 을 **완료**(PR #300 머지 main `7a52a66` → web 재배포 → PB-0008 Windows-browser PASS)로 갱신. TEST.md §3 에 Windows-browser Run 기록(AC-0542 계정 조회버그 해소[작업화면 아바타 img 1 + Identicon 14·이니셜 0]·AC-0544 역할 Identicon 5·AC-0543 타계정 아바타 업로드 200·AC-0545 역할 아이콘 업로드 200, 검증 후 테스트 업로드 DELETE 복원). evidence `artifacts/pb0008-task0293/admin-account-role-icons.png`.
- 검증: PB-0008 실측(win-browser eval — DOM 아바타 img/svg/textOnly 집계 + 실 업로드/서빙 round-trip). 코드 무변경.
- Files: unit/feature-0003-agent-web-ui/docs/{TEST,TASK,MODIFY,REVIEW}.md

## CHG-20260617T034455-ai-claude-task0293-profile-icons (TASK-0293 — 프로필 아이콘 전 구간 조회·수정: 관리 콘솔 계정·역할)
- Date: 2026-06-17
- Scope: feature-0003-agent-web-ui — backend(`src/app.py`) + frontend(`src/static/admin.js` + `admin.html` 캐시버스터) + 테스트. 신규 admin 엔드포인트 4 + 서빙 1 + 비파괴 스키마 1컬럼. **신규 RBAC 권한 0**(기존 재사용).
- 스키마 변경(비파괴): `WebRoles.IconObjectKey VARCHAR(512) NULL` 추가.
  - fast-path: `_ensure_avatar_icon_schema(conn)` 에 `ALTER TABLE WebRoles ADD COLUMN IconObjectKey ...`(idempotent, 기존 배포 backfill — `_ensure_seed_catchup` 경유).
  - slow-path/fresh: `_ensure_web_tables` 의 `CREATE TABLE WebRoles` 에 `IconObjectKey VARCHAR(512) NULL` 컬럼.
  - NULL=미설정 → 프론트 role_key 시드 Identicon. MinIO object key 저장(`role-icons/<role_id>/<uuid>.<ext>`).
- 백엔드 변경(`src/app.py`):
  - `_role_icon_url_for(role_id, object_key)` 신설 — `/api/roles/<id>/icon?v=<sha256[:12]>` 캐시버스터(`_product_icon_url_for`/`_avatar_url_for` 동형).
  - `_list_roles` SELECT 에 `r.IconObjectKey AS icon_object_key` + GROUP BY 추가, 직렬화에 `icon_url` 추가. `_load_role_by_id` 동일.
  - 신규 `PUT/DELETE /api/admin/accounts/{account_id}/avatar` — 관리자(`console.access`+`console.manage`+`account.update`)가 대상 계정 아바타 교체/제거. self-service `/api/auth/me/avatar`(로그인만, 본인 한정)와 별개 경로. `_store_image_upload(prefix="avatars", owner_id=account_id, max=2MB)` 재사용, 삭제 예정 계정 차단, 이전 key best-effort 삭제.
  - 신규 `PUT/DELETE /api/admin/roles/{role_id}/icon` — 관리자(`console.access`+`console.manage`+`role.update`). `_store_image_upload(prefix="role-icons", owner_id=role_id, max=5MB)`.
  - 신규 `GET /api/roles/{role_id}/icon` — 로그인 서빙(`_serve_image_object`, nosniff·inline·1일 캐시). 제품 아이콘 서빙(`serve_product_icon`) 패턴 정합.
  - audit: 아바타/아이콘 mutation 은 audit 미기록 — 제품 아이콘(TASK-0268 `upload_product_icon`/`delete_product_icon`)과 동일 정합(일관 결정, SECURITY §9.2 builder 에 아바타/아이콘 필드 미포함과도 정합).
- 프론트 변경(`src/static/admin.js`):
  - 계정 목록(`renderAccountList`)·상세(`renderAccountDetail`): `avatar.textContent=username.slice(0,2)` → `applyAvatar({url: avatar_url, seed: username})`. **작업화면 프로필과 동일 username 시드** → 동일 계정 동일 아이콘(조회 버그 해소). 상세에 ✎ 오버레이(`.profile-avatar-edit`) + "아바타 제거"(console.manage+account.update, 삭제 계정 제외).
  - 역할 목록(`renderRoleList`)·상세(`renderRoleDetail`): 이니셜 텍스트 → `applyAvatar({url: icon_url, seed: role_key})`. 상세에 ✎ 오버레이 + "아이콘 제거"(console.manage+role.update, **미저장 신규 역할 차단**).
  - CSS 무변경(제품 아이콘이 쓰는 `.admin-avatar`/`.profile-avatar-edit` 클래스 재사용). `admin.html` 캐시버스터 `?v=20260617-task0293-profile-icons`.
- 테스트: `tests/verify_profile_icon_admin_surfaces.mjs` 신설(jsdom 17건 — applyAvatar 분기·시드 정합·이니셜 폐기·편집 엔드포인트·게이트). `tests/test_avatar_icon_upload.py` 에 4건 추가(`_role_icon_url_for`·역할/계정 mutation RBAC 403). 기존 `verify_profile_icon_consistency.mjs` 회귀 0.
- 검증: `make test`(컨테이너 pytest exit 0 + ruff all-clear), node --check admin.js + py_compile app.py PASS, 라우트 충돌 0. 잔여: §18.8 외부 패널·verify-completion·배포·PB-0008.
- Files: unit/feature-0003-agent-web-ui/src/app.py, src/static/admin.js, src/static/admin.html, docs/{FUNCTION,TASK,MODIFY,REVIEW}.md, tests/{test_avatar_icon_upload.py, verify_profile_icon_admin_surfaces.mjs}

## CHG-20260616T163634-ai-claude-conv-entry-defaults-pb0008 (TASK-20260616T100304-conv-entry-defaults 후속 docs-only — PB-0008 evidence)
- Date: 2026-06-16
- Scope: docs 전용(TEST/REPORT/TASK/MODIFY/REVIEW + STATUS) + evidence 이미지. 코드/정적자산 0.
- 변경: TASK-20260616T100304-conv-entry-defaults 의 "잔여: 머지→배포→PB-0008" 을 **완료(PR #293 머지 main b5f2434·web 재배포·PB-0008 PASS)** 로 갱신. TEST.md §4 에 Windows-browser Run 기록(요구1 타 계정 대화 접힘·요구2 빈 대화 화면·clean-room 재현·선호 존중). evidence `artifacts/pb0008-conv-entry-defaults/entry-others-collapsed-empty-chat.png` 추가.
- 검증: PB-0008 실측(win-browser eval — computed/state/localStorage). 코드 무변경.
- Files: unit/feature-0003-agent-web-ui/docs/{TEST,REPORT,TASK,MODIFY,REVIEW}.md, docs/STATUS.md

## CHG-20260616T100304-conv-entry-defaults (TASK-20260616T100304-conv-entry-defaults — 작업 화면 첫 진입 기본값: 타 계정 대화 접힘 + 빈 대화 화면)
- Date: 2026-06-16
- Scope: feature-0003-agent-web-ui frontend-only(`src/static/app.js` + `index.html` 캐시버스터) + 신규 `tests/verify_conv_entry_defaults.mjs`. 백엔드/RBAC/스키마/엔드포인트 무변경.
- 변경:
  - (요구1) `src/static/app.js`: 상수 `OTHERS_GROUP_KEY="__others__"` + `OTHERS_COLLAPSED_SEED_LS_KEY="mad.othersCollapsedSeed.v1"` 신설. `_seedOthersCollapsedOnce()` — seed 플래그가 없을 때만 1회 `__others__` 를 `collapsedDateGroups` 에 추가하고 `collapsedDateGroups`(localStorage `mad.collapsedGroups.v1`) + seed 플래그를 영속(모듈 로드 시 1회 호출). `renderConversationList` 의 `othersKey` 를 상수로 통일.
  - (요구2) `loadConversations(preferredConversationId, { allowCurrentFallback = true })` — preferred 미존재 시 `allowCurrentFallback` 가 false 면 `payload.current` 폴백 없이 active="" (빈 화면). `refreshWorkspace(_, opts)` 가 옵션 전달. `initializeWorkspace`: `_preferCid` 기본 ""/`_allowCurrentFallback=false`(빈 진입), deep-link 시 `allowCurrentFallback=true`(TASK-0263 보존), 직전 대화가 처리 중이면 그 대화를 선택해 resume(TASK-0041, `_resumeStatus` 재사용으로 중복 fetch 회피).
  - `index.html`: app.js 캐시버스터 → `?v=20260616-conv-entry-defaults`.
- 근본원인: ① 첫 진입 시 `collapsedDateGroups` 가 비어 "타 계정 대화" 가 펼침 기본. ② bootstrap 이 서버 직전 대화를 무조건 자동선택(`_preferCid=session.conversation_id` + `payload.current` 폴백).
- 검증: node --check PASS + `verify_conv_entry_defaults.mjs` 20/20 PASS. 백엔드 무변경(make test 회귀 자명 0). 실 화면은 PB-0008.
- Files: src/static/app.js, src/static/index.html, tests/verify_conv_entry_defaults.mjs, docs/{TASK,FUNCTION,REPORT,REVIEW,MODIFY}.md, ../../docs/STATUS.md

## CHG-20260616-0301 (TASK-0291 후속 docs-only — PB-0008 evidence)
- Date: 2026-06-16
- Scope: docs 전용(TEST/STATUS/REPORT/MODIFY/REVIEW). 코드 0.
- 변경: TASK-0291 "잔여: 머지→배포→PB-0008" 을 **완료(PR #287 머지 main 9bdb9f8·web 재배포·PB-0008 PASS)** 로 갱신. win-browser 실측 기록(계정 탭 배지 #tabCountAccounts=7 = 활성 필터 목록 7명 일치, 전체 28명과 분리).
- 검증: PB-0008 실측(win-browser eval + 스크린샷 `artifacts/pb0008-task0291/account-tab-active-count.png`). 코드 무변경.

## CHG-20260616-0300 (TASK-0291 — 계정 탭 배지 활성 계정만 집계)
- Date: 2026-06-16
- Scope: frontend-only. `src/static/admin.js` 1곳 + `src/static/admin.html` 캐시버스터.
- 변경: `refreshPendingUI()` 의 `#tabCountAccounts` 집계를 `adminState.accounts.length`(전체) → `adminState.accounts.filter((a) => a.is_active && !a.deleted_at).length`(활성만). 활성 정의는 `filteredAccounts()` 의 `'active'` 분기(`is_active && !deleted_at`)와 동일. 비활성·삭제는 목록 필터에서 확인 가능하므로 배지에서 제외.
- 비변경: 백엔드/RBAC/스키마/엔드포인트 0. `#accountListCount`(이미 filter-aware) 비변경. 역할/제품/데이터소스 탭 배지 비변경(요청 범위 = 계정 한정).
- 검증: node --check PASS. 백엔드 무변경(make test 회귀 자명 0). PB-0008 Windows-browser 실측은 web 재배포 후.

## CHG-20260616-0298 (TASK-0287 후속 docs-only — PB-0008 evidence)
- Date: 2026-06-16
- Scope: docs 전용(STATUS/REPORT/TASK/MODIFY/REVIEW). 코드 0.
- 변경: TASK-0287 "잔여: 머지→배포→PB-0008" 을 **완료(PR #281 머지 main c5b4823·web 재배포·PB-0008 PASS)** 로 갱신. PB-0008 win-browser 실측(chipUsesFetch=true·credentials=same-origin) 기록.
- 검증: PB-0008 실측(win-browser eval fetch monkeypatch). 코드 무변경.
- Files: docs/STATUS.md, unit/feature-0003-agent-web-ui/docs/{TASK,REPORT,MODIFY,REVIEW}.md

## CHG-20260616-0297 (TASK-0287 — 말풍선 첨부 칩 다운로드 실패 수정)
- Date: 2026-06-16
- Scope: feature-0003-agent-web-ui frontend-only(app.js 1곳 + index.html 캐시버스터). 백엔드/RBAC 무변경.
- 변경: `src/static/app.js` `_buildMessageAttachChip` 의 다운로드 핸들러를 `<a href download>` navigation → `_downloadAttachmentById(att.id, attName)`(목록과 동일 raw fetch + blob, 프록시 `/api/attachments/{id}/download`)로 통일. signed_url 만 있는 폴백은 navigation 유지. 캐시버스터 `?v=20260616-task0287-bubble-chip-dl`.
- 근본원인: TASK-0284 가 octet-stream 프록시 다운로드를 navigation→fetch+blob 으로 전환했으나 말풍선 칩(TASK-0285 `_buildMessageAttachChip`)은 navigation 으로 남아 있어 다운로드 실패.
- 검증: node --check PASS. 백엔드 무변경(make test 회귀 자명 0). 실 다운로드는 PB-0008.
- Files: src/static/app.js, src/static/index.html, docs/{TASK,FUNCTION,REPORT,REVIEW,MODIFY}.md

## CHG-20260616-0296 (TASK-0286 후속 docs-only — PB-0008 + 라이브 프롬프트 evidence)
- Date: 2026-06-16
- Scope: docs 전용(STATUS/REPORT/TASK/MODIFY/REVIEW) + evidence 이미지. 코드/정적자산 0.
- 변경: TASK-0286 "잔여: 머지→배포→라이브 프롬프트→PB-0008" 을 **완료(PR #278 머지 main b884b67·web+ask-worker 재배포·라이브 WebSystemPrompts global row append·PB-0008 PASS)** 로 갱신. PB-0008 render-injection 실측(fullBodyHidden·diff 유지·📎 note) + 라이브 row 6837→8536 기록. evidence `artifacts/pb0008-task0286/attach-edit-diff-only.png` 추가.
- 검증: PB-0008 실측(win-browser eval render-injection + screenshot). 코드 무변경(회귀 0).
- Files: docs/STATUS.md, unit/feature-0003-agent-web-ui/docs/{TASK,REPORT,MODIFY,REVIEW}.md, artifacts/pb0008-task0286/attach-edit-diff-only.png

## CHG-20260616-0295 (TASK-0286 — 첨부 수정본 전달: 전체 본문 노출 제거 + 변경점만 + 파일 명시 전달)
- Date: 2026-06-16
- Scope: feature-0003-agent-web-ui(app.py + app.js/share.js/styles.css/share.css/index.html/share.html) + feature-0002-agent-core(agent_core.py SYSTEM_PROMPT). RBAC 카탈로그/스키마/엔드포인트 shape 무변경.
- 변경:
  - `feature-0002 agent_core.py`: SYSTEM_PROMPT 에 "DELIVERING THE EDITED FILE — attachment-edit" 섹션 추가(diff=변경점 + attachment-edit=전체 본문 숨김·첨부화, 전체 본문 코드블록 금지).
  - `feature-0003 app.py`: 라인 기반 `_attachment_edit_block_spans`(본문 내 ``` 허용) 도입 → `_parse_attachment_edit_blocks` 재구현(절단 제거) + 신규 `_strip_attachment_edit_blocks`(블록 제거→"📎 수정본 전달" 치환) + `_update_assistant_message_content`(PG·MySQL content UPDATE). ask 후처리에서 render_output/DB content strip.
  - `feature-0003 app.js/share.js`: `enhanceAttachmentEditBlocks`(attachment-edit 코드블록→`.attachment-edit-note` 안내) + markdown 파이프라인 체인.
  - `feature-0003 styles.css/share.css`: `.attachment-edit-note`(메인 라이트·share 다크). 캐시버스터 `?v=20260616-task0286-attach-edit-diff`(index.html·share.html).
  - `tests/test_task0286_attach_edit_strip.py`: 신규 10 PASS(S1~S7 strip/parse + embedded-fence 회귀 + P1/P2 프롬프트 + A1 배선).
- 검증: make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0, ruff clean), py_compile(app.py·agent_core.py), node --check(app.js·share.js), CSS brace(styles 1243·share 107). 보안 SHIP-WITH-FIXES(REV-20260616-0295, MAJOR 흡수).
- 배포: web 재빌드(app.py·정적자산) + agent/ask-worker 재빌드(agent_core SYSTEM_PROMPT) + **라이브 WebSystemPrompts global row 멱등 갱신**(상수는 seed/fallback). ask/insight-worker 는 agent_core baked.
- Files: unit/feature-0002-agent-core/src/agent_core.py, unit/feature-0003-agent-web-ui/src/app.py, src/static/{app.js,share.js,styles.css,share.css,index.html,share.html}, tests/test_task0286_attach_edit_strip.py, docs/{TASK,FUNCTION,REPORT,REVIEW,MODIFY}.md

## CHG-20260616-0294 (TASK-0285 후속 docs-only — PB-0008 evidence 기록)
- Date: 2026-06-16
- Scope: docs 전용(STATUS/REPORT/TASK/MODIFY/REVIEW) + evidence 이미지. 코드/정적자산 0.
- 변경: TASK-0285 의 "잔여: 머지→배포→PB-0008" 을 **완료(PR #275 머지 main 1c4737d·web 재배포·PB-0008 PASS)** 로 갱신. PB-0008 render-injection computed 실측 결과 기록(ai-edited 배지 색·assistant 칩 배경·버전 박스). evidence `artifacts/pb0008-task0285/attach-version-surfacing.png` 추가.
- 검증: PB-0008 실측(win-browser eval render-injection + computed + screenshot). 코드 무변경(회귀 0).
- Files: docs/STATUS.md, unit/feature-0003-agent-web-ui/docs/{TASK,REPORT,MODIFY,REVIEW}.md, artifacts/pb0008-task0285/attach-version-surfacing.png

## CHG-20260616-0293 (TASK-0285 — 첨부 버전 현황 표면화 ②③④)
- Date: 2026-06-16
- Scope: feature-0003-agent-web-ui. frontend(app.js/styles.css/index.html) + 백엔드 노출(app.py). RBAC 카탈로그/스키마/엔드포인트 shape 무변경(응답 필드 추가 + 신규 헬퍼만).
- 변경:
  - `src/app.py`: ② `list_conversation_attachments` version_count/ai_version_count GROUP BY 집계. ③ `_load_assistant_attachments_by_message` + `_attach_assistant_attachments` 신규 + `_get_history`(PG·MySQL 양 경로) assistant 첨부 직렬화 주입. ④ ask materialize 후처리에 `save_memory_step`(attachment_edit/materialize_attachment) + 응답 render_steps 즉시 반영.
  - `src/static/app.js`: 첨부 목록 버전 배지/펼침(`_downloadAttachmentById`·`_renderAttachmentVersionsBox` 헬퍼), 메시지 칩 공통 헬퍼 `_buildMessageAttachChip`(user/assistant), renderMessages 칩 조건 assistant 포함.
  - `src/static/styles.css`: `.attach-list-entry`/`.attach-list-item-ver`/`.attach-list-versions*` + `.message.is-assistant` 칩 배경 보정 + `.attach-chip-ver`.
  - `src/static/index.html`: 캐시버스터 `?v=20260616-task0285-attach-surfacing`(styles.css·app.js).
  - `tests/test_task0285_attach_surfacing.py`: 신규 9 PASS(A1/A2/L1~L3/V1/V2/S1/S2).
- 검증: make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0), ruff clean, py_compile, node --check, CSS brace(1242=1242). 보안 SHIP(REV-20260616-0293).
- Files: src/app.py, src/static/{app.js,styles.css,index.html}, tests/test_task0285_attach_surfacing.py, docs/{TASK,FUNCTION,REPORT,REVIEW,MODIFY}.md

## CHG-20260616T024150-ai-claude-sidebar-resize-pb0008
- Date: 2026-06-16 (TASK-20260616T022652-ai-claude-sidebar-resize 후속, **docs-only** — 사이드바 너비 드래그 조절 PB-0008 Windows-browser 시각검증 evidence 기록)
- Scope: docs 전용(TASK.md 잔여 체크박스 [x] + TEST.md §4 Windows-browser Run 실측 + REPORT.md git-sync/PB-0008 결과). 코드/정적자산 0.
- 변경: PB-0008 **PASS** 기록 — 배포본 main `6f1242b`(healthz git_commit 일치)에서 실 Chrome/148 드래그 시 사이드바 폭 실제 변화(252→380, chat-column reflow), clamp 180/624, 새로고침 복원(340), 더블클릭 reset 실측. evidence `artifacts/pb0008-sidebar-resize/sidebar-resized-340.png`.
- 검증: PB-0008 실측(win-browser MouseEvent 디스패치 + computed + screenshot). 코드 무변경(회귀 0).
- Files: docs/{TASK,TEST,REPORT,MODIFY,REVIEW}.md

## CHG-20260616T022652-ai-claude-sidebar-resize
- Date: 2026-06-16 (TASK-20260616T022652-ai-claude-sidebar-resize — 대화창 좌측 사이드바 너비 드래그 조절. timestamp+branch id, ADR-0025/v3.32.0)
- Scope: frontend-only `src/static/{index.html,styles.css,app.js}` + 신규 테스트 `tests/verify_sidebar_resize.mjs`. RBAC/스키마/엔드포인트/백엔드 0.
- 변경:
  - index.html: `.app-shell` 자식으로 `#sidebarResizer`(role=separator, aria-label "사이드바 너비 조절") 핸들 추가. styles.css/app.js 캐시버스터 `?v=20260616-sidebar-resize`.
  - styles.css: `.app-shell{position:relative}`; `.sidebar-resizer`(absolute, `left:var(--sidebar-w)`, 8px hit-area, `cursor:ew-resize`, hover/`is-sidebar-resizing` 시 `--primary` 2px 라인); `.app-shell.is-sidebar-resizing{user-select:none}`; 모바일(≤680) `.sidebar-resizer{display:none}`.
  - app.js: `SIDEBAR_WIDTH_KEY="web.sidebar.width"` + `_sidebarMaxW`(min(640, 50%vw)) + `_applySidebarWidth`(저장값 복원·clamp·모바일 override 제거) + `setupSidebarResize`(mouse/touch drag → `--sidebar-w`=clamp([180,max], clientX), mouseup 영속, 더블클릭 reset). 우측 패널 resizer 3종과 동형 패턴. `initialize()` 1회 배선 + `window resize` 리스너에 `_applySidebarWidth()`.
- 검증: node --check PASS + CSS brace(1222=1222) + jsdom 23/23(`verify_sidebar_resize.mjs`) + make test 회귀 0(REAL_MAKE_EXIT=0).
- Files: src/static/{index.html,styles.css,app.js}, tests/verify_sidebar_resize.mjs, docs/{TASK,FUNCTION,REVIEW,TEST,REPORT,MODIFY}.md

## CHG-20260616-0292
- Date: 2026-06-16 (TASK-0283 후속, **docs-only** — 제품 아이콘 편집 UI ✎ 오버레이 통일 PB-0008 Windows-browser 시각검증 evidence 기록; §13.1 origin max CHG-20260616-0291 → 0292)
- Scope: docs 전용(TASK.md 잔여 체크박스 + TEST.md §4 PB-0008 Run + REPORT.md 잔여). 코드/정적자산 0.
- 변경: PB-0008 Windows-browser **PASS** 기록 — `관리 콘솔 > 제품 > [항목]` 상세 아이콘 편집이 `.profile-avatar-change` ✎ 원형 오버레이(computed absolute·right:-4px·bottom:-4px·22×22·border-radius:50%·visible)·구 텍스트 pill 부재(oldPillPresent=false)·침범 0·유저 프로필 동일 클래스 시각 동형. 배포 main `245446f`(#265). evidence `artifacts/pb0008-task0283/product-icon-edit-overlay.png`.
- 검증: PB-0008 실측(win-browser eval + screenshot). 코드 무변경(회귀 0).
- Files: docs/{TASK,TEST,MODIFY,REVIEW,REPORT}.md
- Cross-ref: REV-20260616-0292 / CHG-20260616-0291(원 변경) / TASK-0283.

## CHG-20260616-0291
- Date: 2026-06-16 (TASK-0283, **Minor §12.3** — 관리 콘솔 제품 아이콘 편집 UI 를 유저 프로필과 동일한 ✎ 오버레이로 통일, frontend-only. §13.1 origin max CHG-20260616-0290 → 0291)
- Scope: agent-web-ui(프론트 전용) — `src/static/admin.js` `renderProductDetail` 1곳 + `src/static/styles.css`(dead-rule 제거) + `src/static/{index,admin}.html`(cache-buster) + `docs/{TASK,TEST,MODIFY,REVIEW}.md`. RBAC/스키마/엔드포인트/백엔드 0.
- 원인(사용자 보고): 제품 상세 아이콘 편집이 `.admin-avatar-edit`(absolute `bottom:-22px`) 안에 "아이콘"·"제거" 텍스트 pill 2개를 배치 → 텍스트 버튼 폭이 36px 아바타보다 넓어 좌우 spill·아이콘 영역 침범. 유저 프로필(`.profile-avatar-edit`)의 ✎ 원형 오버레이 패턴과 불일치.
- 수정: admin.js — 텍스트 pill 폐기, 유저 프로필과 동일하게 아바타를 `.profile-avatar-edit` 래퍼로 감싸 `.profile-avatar-change`(✎, `right:-4px bottom:-4px` 22px 원형 오버레이) 버튼 + 숨김 file input 부착, "아이콘 제거"는 `.profile-avatar-remove` 텍스트 링크로 idText 하단 분리. styles.css — 사용처 0건이 된 `.admin-avatar-edit`/`.admin-avatar-change`/`.admin-avatar-remove` 규칙 제거(프로필 클래스 재사용 → 신규 CSS 0).
- 비변경: 아이콘 PUT/DELETE 엔드포인트·5MB 가드·image accept·toast·renderProductDetail 재렌더·applyAvatar/Identicon 폴백·`canManage` 게이트 무변경. 제품 목록 행·chip·드롭업·계정 아바타 무관(`.admin-avatar` 베이스 클래스 유지).
- 검증: node --check admin.js PASS. (잔여) web 재배포 후 PB-0008 Windows-browser 시각검증.
- Cross-ref: REV-20260616-0291 / TASK-0283.

## CHG-20260615-0286
- Date: 2026-06-15 (TASK-20260615T182907-product-list-row-icon-layout-fix, **Minor §12.3** — 제품 관리 목록 행 UI 뒤틀림 핫픽스, frontend-only. 동시세션 TASK-0277/0277b/0278 이 CHG-0281~0285 선점 → §13.1 재번호 0280→0286)
- Scope: agent-web-ui (프론트 전용) — `src/static/admin.js` `renderProductList` 1곳 + `tests/verify_product_icon_chip_list.mjs`([3] 회귀 검증 추가) + `docs/{TASK,TEST}.md`. RBAC/스키마/엔드포인트/백엔드 0.
- 원인: 직전 CHG-20260615-0279(PR #249)가 제품 목록 행에 아이콘을 추가하면서 `row.append(cb, avatar, meta)` 로 avatar 를 row 최상위 2번째 칸에 배치 → `.admin-list-row` 3열 grid(`auto 1fr auto`)에서 avatar 가 `1fr` 칸 점유·meta 가 `auto` 칸으로 밀려 행 정렬·텍스트 위치 뒤틀림.
- 수정: avatar 를 row 최상위가 아니라 `meta`(`admin-list-main`) 첫 줄 `titleRow`(신규 `admin-list-row-title` flex 컨테이너) 안에 name 과 함께 묶음 — 계정 목록 행(`title.append(avatar, name, ...)` + `row.append(cb, main, chips)`)과 동형. `row.append(cb, meta)` 2자식 복원 → grid `auto 1fr auto` 정상. sub·cov 줄은 meta 세로 stack 유지.
- 비변경: 아이콘 렌더 로직(applyAvatar)·CSS·chip·드롭업·상세·명칭 0. row click·shift-range·cov 배지·checkbox 무변경.
- 검증: node --check admin.js + jsdom 19/19 PASS([3] avatar∈titleRow·row 2자식·grid 정합 회귀 5건) + make test 컨테이너 회귀 0.
- Cross-ref: REV-20260615-0286 / TASK-20260615T182907-product-list-row-icon-layout-fix / CHG-20260615-0279(원인 cycle).

## CHG-20260615-0285
- Date: 2026-06-15 (TASK-0278, **docs-only** — 데이터소스 목록 네트워크 상태 배지 PB-0008 Windows-browser 시각검증 evidence 기록; §13.1 origin max CHG-0284 → 0285)
- Scope: docs 전용(TASK.md 잔여 체크박스 + TEST.md §4 PB-0008 Run). 코드/정적자산 0.
- 변경: PB-0008 Windows-browser **PASS** 기록 — `관리 콘솔 > 데이터소스` 14행 전부 leading `.ds-conn-dot`·left=270 단일정렬·is-ok 초록(22,163,74)/is-fail 빨강(220,38,38)·title/aria-label·grid `9px 274px`·`#settingsList` 무회귀(308px). 배포 main `73d65b8`(#251). evidence `artifacts/pb0008-task0278/ds-conn-badge.png`.
- 검증: PB-0008 실측(win-browser eval + screenshot). 코드 무변경(회귀 0).
- Files: docs/{TASK,TEST,MODIFY,REVIEW}.md
- Cross-ref: REV-20260615-0285 / TASK-0278 / CHG-20260615-0282(코드 cycle).

## CHG-20260615-0284
- Date: 2026-06-15 (TASK-0277b 후속, **docs-only** — PB-0008 재검증 PASS evidence 기록)
- Scope: agent-web-ui 문서만(TEST.md §4 + TASK.md 완료 표기). src 코드 0.
- 변경: TEST.md §4 의 "재검증 결과 기록 예정" placeholder → 실 결과로 교체. 배포본 main `d6123d3`(#252) 서빙 `?v=...task0277b-archive-row-ellipsis` 에서 실 Chrome/148 relay 로 보관 대화 탭 computed 실측: `rowAlignItems:stretch`·`paneNotePresent:false`·2줄 고정(rowH 56→56)·line0W 308(row 폭 갇힘)·topic clientW 164<scrollW 2586 clipped:true·owner/by clipped:true(ellipsis 발동). [문제1·2] 실 브라우저 PASS. TASK.md 0277b 잔여 체크박스 완료 표기. evidence `artifacts/pb0008-task0277/{01_archive_long_ellipsis,02_archive_clean_density}.png`.
- 비변경: 코드·CSS 0(순수 evidence). 핵심 변경은 CHG-0281(TASK-0277)·CHG-0283(TASK-0277b)에서 이미 반영·머지.
- 검증: PB-0008 Windows-browser PASS(위 실측). CHECK#13 충족(직전 cycle 에서 기록됨).
- Files: docs/{TEST,TASK,MODIFY,REVIEW}.md
- Cross-ref: REV-20260615-0284 / TASK-0277b / CHG-20260615-0283.

## CHG-20260615-0283
- Date: 2026-06-15 (TASK-0277b, **Minor §12.3** — TASK-0277 후속 핫픽스: 보관 대화 row ellipsis 실작동 수정; PR #250 후 PB-0008 실 브라우저 실측에서 발견)
- Scope: agent-web-ui frontend 전용(styles.css 1 규칙 + admin.html 캐시버스터 + jsdom 테스트 계약 1건). 백엔드·RBAC·엔드포인트 0.
- 근본 원인: `.admin-archive-row` 는 `.admin-list-row`(grid) + `.admin-archive-row`(flex column) 두 클래스를 함께 가지는데, `.admin-list-row` 의 `align-items: center` 가 flex 컬럼에 상속돼 각 줄(`.admin-archive-row-line`)이 row 폭(330px)으로 **stretch 되지 않고 콘텐츠 폭(2858px)으로 팽창** → 자식 span 이 shrink 안 돼 `text-overflow: ellipsis` 가 발동하지 못함(줄바꿈은 막혔으나 절단 미작동, 하드 클립). TASK-0277 jsdom 은 CSS 규칙 존재만 검사해 미검출.
- 변경:
  - (styles.css) `.admin-archive-row` 에 `align-items: stretch` 추가 — 줄을 row 폭에 맞춰 span 이 shrink→ellipsis 절단. PB-0008 실측: line 2858→308px, topic clientW 164·scrollW 2714 → clipped:true, rowH 56 유지(2줄 고정).
  - (admin.html) 캐시버스터 `?v=20260615-task0277-archives-ui-align` → `?v=20260615-task0277b-archive-row-ellipsis`.
  - (tests) `verify_archive_tab_ui.mjs` 에 `.admin-archive-row { align-items: stretch }` CSS 계약 단언 추가(26 PASS).
- 검증: node --check + CSS brace(1210=1210) + jsdom 26 PASS + make test 회귀 0 + **PB-0008 실 브라우저 재검증**(clipped:true·2줄 고정·밀도 정합).
- Files: src/static/{styles.css,admin.html}, tests/verify_archive_tab_ui.mjs, docs/{TASK,MODIFY,REVIEW,REPORT,TEST}.md
- Cross-ref: REV-20260615-0283 / TASK-0277b / CHG-20260615-0281(TASK-0277 본 변경) / FUNCTION AC-0508.

## CHG-20260615-0282
- Date: 2026-06-15 (TASK-0278, **Minor** — 관리 콘솔 데이터소스 목록 행별 네트워크 상태 배지, frontend-only; §13.1 #249·#250 동시세션이 CHG-0279~0281·TASK-0277 선점 → CHG-0282/TASK-0278 재번호)
- Scope: 정적자산만(admin.js + styles.css + admin.html). 백엔드/스키마/RBAC/엔드포인트 0.
- 변경:
  - (admin.js `_dsRenderList`) 각 행 leading 에 `.ds-conn-dot` 추가 — 캐시(`datasourceConnStatus`) hit 동기 즉시, miss(unknown)만 `_probeDatasourceConn`(force=false·4-cap 세마포어·in-flight dedup) lazy probe + `dot.isConnected` 가드(검색 재렌더 detach 보호).
  - (admin.js 신규) `_paintDsConnDot(el, entry)` — ok/fail/checking→클래스 + `title`/`role=img`/`aria-label`(색맹 대응). picker `_paintDsConnBadge`(텍스트 배지)와 독립.
  - (styles.css) `.ds-conn-dot`(currentColor 점+halo·상태 색·covPickerPulse·prefers-reduced-motion 정지) + `#datasourceList .admin-list-row--nav { grid-template-columns: auto 1fr }`(컨테이너 스코프, `#settingsList` 등 1fr 유지).
  - (admin.html) 캐시버스터 `?v=20260615-task0278-ds-conn-badge`(styles.css + admin.js — #249/#250 변경과 합본 서빙).
- 검증: node --check admin.js + CSS brace 균형 + 적대적 코드리뷰(REV-0282) SHIP. (잔여 PB-0008 배포후)
- Files: unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css,admin.html}, docs/{TASK,MODIFY,REVIEW,TEST,FUNCTION}.md
- Rollback: `.ds-conn-dot` 블록 + grid 스코프 규칙 + `_paintDsConnDot` + `_dsRenderList` 도트 삽입 + 캐시버스터 환원(전부 additive, 백엔드 무영향).
- Deploy: web 재빌드(정적자산)만. migrate 불필. ask/insight-worker 무변경.

## CHG-20260615-0281
- Date: 2026-06-15 (TASK-0277, **Minor §12.3** — 관리 콘솔 "보관 대화" 탭 UI 정합 다듬기; TASK-0276 list-detail 위 후속. 동시세션이 CHG-0279/0280 선점 → §13.1 재번호 0281)
- Scope: agent-web-ui frontend 전용(admin.html + admin.js + styles.css) + 신규 jsdom 테스트. 백엔드·RBAC·엔드포인트·스키마·데이터 0.
- 변경:
  - (admin.html) [문제1] archives pane header↔filter 사이의 `<p class="admin-pane-note">`(3문장 안내) 제거 → 다른 운영 탭과 동일 밀도. 안내는 우측 `#archiveDetail` 빈 상태(`admin-detail-empty`)에 `admin-archive-detail-note` 로 이동(정보 보존). 캐시버스터 admin.js·styles.css `?v=20260615-task0276-archives-ui` → `?v=20260615-task0277-archives-ui-align`.
  - (admin.js) `renderArchiveDetail` 의 빈 분기 innerHTML 을 동일하게 `admin-detail-empty` + `admin-archive-detail-note` 안내 carry 하도록 갱신(미선택 시에도 안내 노출, static HTML 과 정합).
  - (styles.css) [문제2] `.admin-archive-row-line` 의 `flex-wrap: wrap` 제거 + `align-items:baseline`/`min-width:0` 추가. `.admin-archive-row-topic` 에 `min-width:0` 보강. `.admin-archive-row-owner`/`.admin-archive-row-by` 에 `white-space:nowrap`+`text-overflow:ellipsis`+`overflow:hidden`+`min-width:0`+`flex:0 1 auto` 추가(긴 문자열 줄바꿈 대신 절단). `.admin-archive-row-ts` 에 `flex:0 0 auto`+`white-space:nowrap`(시각 비절단·우측 정렬 유지). [문제1] 사용처 0건이 된 `.admin-pane-note` 규칙 제거.
  - (tests) 신규 `tests/verify_archive_tab_ui.mjs` — jsdom 으로 안내 이동(밀도 정합)·row 2줄 고정 구조·CSS anti-wrap 계약 검증(25 PASS).
- 검증: node --check admin.js + CSS brace 균형 + jsdom 25 PASS + make test 컨테이너 전체 회귀 0(백엔드 무변경). 시각 = PB-0008(배포 후).
- Files: src/static/{admin.html,admin.js,styles.css}, tests/verify_archive_tab_ui.mjs, docs/{TASK,MODIFY,FUNCTION,REVIEW,REPORT,TEST}.md
- Cross-ref: REV-20260615-0281 / TASK-0277 / FUNCTION REQ-20260615-0279(AC-0507~0508) / CHG-20260615-0277(TASK-0276 list-detail 선행).

## CHG-20260615-0279
- Date: 2026-06-15 (TASK-20260615T180923-product-icon-chip-list, **Minor §12.3** — 제품 프로필 아이콘을 대화창 chip + 제품 관리 목록 행에도 표시, frontend-only)
- Scope: agent-web-ui (프론트 전용) — `src/static/{index.html, app.js, admin.js, styles.css}` + 신규 `tests/verify_product_icon_chip_list.mjs`. RBAC/스키마/엔드포인트/백엔드(app.py) 0.
- 변경:
  - index.html: chip 에 `#productChipIcon`(`.composer-product-chip-icon hidden`) span 추가(dot↔label 사이).
  - app.js `renderProductChip`: pinned 제품이면 chip 아이콘 표시(설정 이미지 or Identicon[product_key 시드] 폴백, onerror Identicon), auto 모드면 `.hidden` + innerHTML 비움. 기존 dot conn 색·label compact·busy 로직 무변경.
  - admin.js `renderProductList`: 각 행에 `applyAvatar(avatar,{url:p.icon_url, seed:product_key})` 아이콘(`admin-avatar admin-avatar-sm`, checkbox 다음·meta 앞) — 계정 목록 행과 동형, 직전 cycle 이식 헬퍼 재사용.
  - styles.css: `.composer-product-chip-icon`(16px·`border-radius:50%`·overflow hidden + `.hidden{display:none}` + img/`>svg` 100% 규칙) 신설. `.composer-product-chip` max-width 180→200. 행 아이콘은 직전 cycle `.admin-avatar .avatar-img,.admin-avatar > svg`(원형 클립) 규칙 그대로 적용.
  - 캐시버스터 통일 `?v=20260615-product-icon-chip-list`(index/admin html 의 app.js·admin.js·styles.css).
- 비변경: 백엔드/RBAC/스키마/엔드포인트 0(icon_url 은 기존 `_list_products`·session 직렬화 필드 그대로 소비).
- 검증: node --check + CSS brace(1211) + jsdom 14/14 PASS + make test 컨테이너 회귀 0.
- Cross-ref: REV-20260615-0280 / TASK-20260615T180923-product-icon-chip-list / TASK profile-icon-consistency(직전 정합화).

## CHG-20260615-0278
- Date: 2026-06-15 (TASK-20260615T172210-profile-icon-consistency 후속, **docs-only** — PB-0008 Windows-browser 시각검증 evidence 기록)
- Scope: agent-web-ui 문서/테스트만 — `docs/TEST.md` §4 Run 1건 추가 + `docs/TASK.md` 잔여 PB-0008 항목 "완료" 표기 + `tests/win-browser-profile-icon{,-admin}.scenario.json` 보존. src 코드 0.
- 변경: TEST.md §4 — 배포(main `bb1a991` PR #246 squash, web 재배포) 후 실 Chrome/148 relay 로 ① 대화 드롭업 8제품 항목 순서 [dot→icon→label→ds] ② 전 제품 Identicon(작업화면 프로필 정합) ③ 명칭 `(약어) 명칭`(드롭업·관리목록·상세) ④ 메뉴 너비 max 420px 미잘림 ⑤ 관리 콘솔 제품 상세 Identicon 시각검증 PASS. 스크린샷 `artifacts/pb0008-profile-icon/35_dropup_large.png`·`20_admin_detail_identicon.png`.
- 비변경: 코드·CSS 0(순수 evidence). 핵심 변경은 CHG-20260615-0276(PR #246 머지)에서 이미 반영.
- 검증: PB-0008 Windows-browser PASS(위 5항목 실측). CHECK#13 충족.
- Cross-ref: REV-20260615-0279 / TASK-20260615T172210-profile-icon-consistency / CHG-20260615-0276.

## CHG-20260615-0277
- Date: 2026-06-15 (TASK-0276, **Minor §12.3** — 관리 콘솔 "보관 대화" 탭 UI 정합화; 동시세션 profile-icon 이 CHG-0276 선점 → §13.1 재번호 0276→0277)
- Scope: agent-web-ui frontend 전용(admin.html + admin.js + styles.css). 백엔드·RBAC·엔드포인트·스키마·데이터 0.
- 변경:
  - (admin.html) archives pane 을 단일 `#archivesContent` table 에서 다른 탭 동형 **list-detail 2단**으로 교체: `admin-archive-filter`(검색 input + 적용/초기화) + `admin-list-detail`(좌 `#archiveList`+`#archiveListCount`/`#archiveListScope`, 우 `#archiveDetail`). 헤더 인라인 검색 제거(필터 행 이동), 새로고침 유지.
  - (admin.js) `adminState.archives` 상태 + `renderArchiveList`/`renderArchiveDetail`(audits 동형) + `loadArchivedConversations` 목록·상세 분리 렌더·선택 유지 + 검색 적용/초기화 바인딩. 기존 `renderArchivedConversations`(table) 대체. `_archiveEsc/_archiveFmtDt/_archiveOwnerLabel/_archiveByLabel` 헬퍼.
  - (styles.css) `.admin-archives-table` 류 제거 → `.admin-archive-filter/.admin-archive-row(-*)/.admin-archive-detail(-fields)` 추가(`.admin-audit-*` 동형).
  - 캐시버스터 admin.html admin.js·styles.css `?v=20260615-task0276-archives-ui`.
- 검증: node --check admin.js + CSS brace(1206=1206) + jsdom 13 PASS(list-detail 정합·row 클릭 상세·is-selected·XSS escape·truncated) + make test 회귀 0(백엔드 무변경).
- Files: src/static/{admin.html,admin.js,styles.css}, docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md, docs/STATUS.md(repo)
- Rollback: archives pane 을 table 렌더로 환원 + `.admin-archive-*` CSS 제거 + 캐시버스터 환원. 백엔드 무영향.
- Deploy: web 재빌드(정적자산). migrate 불필. ask/worker 무변경.

## CHG-20260615-0276
- Date: 2026-06-15 (TASK-20260615T172210-profile-icon-consistency, **Major §12.3** — 제품 프로필 아이콘 정합화 + 대화 드롭업 레이아웃·너비 + 명칭 표기 순서, frontend-only)
- Scope: agent-web-ui (프론트 전용) — `src/static/{admin.js, app.js, styles.css, index.html, admin.html}` + 신규 `tests/verify_profile_icon_consistency.mjs`(jsdom 격리 검증). RBAC/인증/스키마/엔드포인트 계약/데이터/시크릿/백엔드(app.py) 0.
- 변경:
  - admin.js: app.js 의 `_identiconHash`/`identiconSvg`/`applyAvatar` byte-identical 이식(작업화면 프로필과 동일 폴백). `renderProductDetail` 헤더 아이콘을 `applyAvatar(avatar,{url:product.icon_url, seed:product_key})` 로 교체 — icon_url 미설정 시 이니셜 텍스트 대신 결정론적 Identicon SVG. 아이콘 변경/제거 편집 컨트롤 보존.
  - app.js `buildProductDropupItem`: 항목 자식 순서를 [① dot(네트워크 상태 배지) → ② 프로필 아이콘 → ③ 명칭 → ④ datasource] 로 재배열. pinned 제품은 아이콘 항상 표시(설정 이미지 또는 Identicon 폴백; 과거엔 icon_url 설정 시에만 + dot 앞). auto 항목은 dot 만.
  - styles.css: `.product-dropup-menu` min 220→300 / max 280→`min(420px,92vw)`(명칭 잘림 해소). `.product-dropup-item-icon` 16→18px·`border-radius:50%` + `> svg` 규칙. `.admin-avatar.has-avatar-img`(padding 0·transparent) + `.admin-avatar .avatar-img,.admin-avatar > svg`(100%·object-fit cover·`border-radius:50%`·overflow hidden) — edit 컨트롤은 avatar 밖(bottom:-22px)이라 컨테이너 overflow visible 유지, 이미지·SVG 만 원형 클립.
  - 명칭 조합 `${name} (${product_key})` → `(${product_key}) ${name}` 7곳: app.js(promptSelect / chip fullLabel / dropup label / promptProductSelect), admin.js(제품 목록행 / 상세 헤더 / role-product select).
  - 캐시버스터 통일 `?v=20260615-profile-icon-consistency`(index/admin html 의 app.js·admin.js·styles.css).
- 비변경: 백엔드 직렬화(app.py `_list_products` 는 name·product_key 분리 반환 — 조합은 프론트 전담, 변경 없음), RBAC/스키마/엔드포인트/conn_status/icon 업로드 경로 0.
- 검증: node --check app.js·admin.js PASS + CSS brace 균형(1198) + jsdom 23/23 PASS + make test 컨테이너 전체 회귀 0(ruff clean, 2 skip).
- Cross-ref: REV-20260615-0277 / TASK-20260615T172210-profile-icon-consistency / TASK-0268(아이콘 인프라 base). (REV 0276→0277: 동시세션 TASK-0275 보안리뷰가 REV-0276 선점 → §13.1 재번호.)

## CHG-20260615-0275
- Date: 2026-06-15 (TASK-0275, **Critical §12.3** — assistant 첨부 수정→새 버전 materialize + 버전 관리; 동시세션 첨부패널 resize 선점 0274 → §13.1 재번호 0274→0275)
- Scope: app.py(materialize 파서/헬퍼 + ask 훅 + /versions 엔드포인트 + 버전 직렬화 + 멱등 스키마) + 정적자산(app.js/styles.css/index.html). MySQL 스키마 컬럼 ADD(첨부 테이블 — PG/alembic 무관, migrate 불필).
- 변경:
  - (스키마 MySQL 전용) `WebConversationAttachments` 에 `RootAttachmentId`/`VersionNumber`/`CreatedByRole`/`SupersededAt` + UNIQUE `UQ_WCA_VersionChain`. `_ensure_attachment_version_schema` 멱등 ALTER — fast-path(`_ensure_seed_catchup`)+slow-path(`_ensure_web_tables`) 양쪽. CREATE TABLE 정의에도 반영.
  - (materialize) `_parse_attachment_edit_blocks`(```attachment-edit``` fenced block 파싱, graceful) + `_materialize_assistant_attachment_edits`(5가드: 텍스트kind·conv/account scope·size cap·count/size cap·확장자고정+safe_filename). MinIO put 선행→INSERT→supersede(VersionNumber< self-heal)→`attachment.version.create` audit. ask 흐름 render_output 확정 후 호출 → 응답 `edited_attachments`.
  - (조회/목록) `GET /api/attachments/{id}/versions`(체인 전체, read.{own,any}, pending signed_url 미발급). `list_conversation_attachments` WHERE `SupersededAt IS NULL`(최신만). `_serialize_attachment_for_api` 버전 필드 5개.
  - (프론트) app.js `_buildPill` 버전 배지(`v{n} · AI 수정`) + `_syncConversationAttachmentsToBucket` version 메타 보존 + `edited_attachments` 토스트. styles.css `.pill-version`(.ai-edited 강조). index.html 캐시버스터 `?v=20260615-task0275-attachment-version`.
- 검증: 신규 test_attachment_versioning.py 11 PASS(파서2·가드6·직렬화1·파일명1·목록필터1) + make test 컨테이너 전체 회귀 0 + ruff + py_compile + node --check + CSS brace(1194=1194) + 라이브 라운드트립(materialize→v2·MinIO sha256·supersede·목록필터·/versions·IDOR 2종·traversal/.exe 차단·UNIQUE 충돌 거부) + outside-voice 보안 리뷰 SHIP(REV-0275, 데이터정합 BLOCKER1+MAJOR2+MINOR1 수정).
- Files: src/app.py, src/static/{app.js,styles.css,index.html}, tests/test_attachment_versioning.py, docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md, docs/STATUS.md(repo)
- Rollback: materialize 파서/헬퍼·ask 훅·/versions 엔드포인트·버전 직렬화·목록 SupersededAt 필터·프론트 배지/토스트 제거 + 캐시버스터 환원. 버전 컬럼·UNIQUE 잔존(무해, 기존 첨부 동작 동일). MinIO 고아 객체는 reconciliation worker 정리.
- Deploy: web 재빌드(app.py+정적자산). **migrate 불필**(첨부 MySQL DML-only — 멱등 ALTER 재기동 자동 적용). ask/insight-worker 무변경.

## CHG-20260615-0274b
- Date: 2026-06-15 (TASK-0274 후속, **docs-only** — 첨부 패널 resize PB-0008 Windows-browser 시각검증 evidence 기록)
- Scope: agent-web-ui 문서만 — `docs/TEST.md` §4 Run 1건(TASK-0274) 추가 + `docs/TASK.md` 잔여 PB-0008 항목 "완료(PASS)" 표기. src 코드 0.
- 변경: TEST.md §4 — 배포(main `bb06ddf` web 재배포) 후 실 Chrome/148 relay 로 ① `+` > 첨부파일 목록 → 패널 표시 + resizer hit-test(elementFromPoint=attachSidePanelResizer, 가림 0) ② 핸들 드래그 280→458px + `.is-resizing` ③ localStorage `web.attachSidePanel.width`=458 저장 ④ 새로고침 후 458px 복원 ⑤ min240/max92vw(1149) clamp 실측. 스크린샷 `artifacts/pb0008-task0274/attach-panel-resized-458.png`.
- 비변경: 코드·테스트·CSS 0(순수 evidence). 핵심 변경은 CHG-20260615-0274(PR #241 머지)에서 이미 반영.
- 검증: PB-0008 Windows-browser PASS(위 5항목 실측). CHECK#13 충족.

## CHG-20260615-0274
- Date: 2026-06-15 (TASK-0274, **Minor §12.3** — 첨부파일 목록 사이드 패널 너비 조절(리사이즈) 가능화)
- Scope: agent-web-ui (프론트 전용) — 사용자 요청(`작업 화면 > '+' > 첨부파일 목록` 사이드바 resize). `#attachSidePanel` 만 고정 280px 였고, 동일 우측 고정 패널인 `#stepSidePanel`·`#profileDrawer` 는 이미 좌측 드래그 핸들 + localStorage 너비 영속화 resize 를 운영 중 → 검증된 패턴 verbatim 이식.
- 변경:
  - `src/static/index.html`: `#attachSidePanel` 첫 자식으로 `<div class="attach-side-panel-resizer" id="attachSidePanelResizer" role="separator" aria-orientation="vertical" aria-label="패널 너비 조절" title="드래그하여 너비 조절">` 추가(step-side-panel 마크업 동형). 캐시버스터 styles.css·app.js `?v=20260615-attach-panel-resize`.
  - `src/static/styles.css`: `.attach-side-panel` 에 `min-width:240px`·`max-width:92vw` 추가(기존 `width:280px` 는 초기값으로 유지). `.attach-side-panel.is-resizing`(transition:none + user-select:none) + `.attach-side-panel-resizer`(position:absolute·left:-3px·width:8px·cursor:ew-resize·touch-action:none) + `::before` 가이드라인(hover/dragging 시 `var(--primary,#2563eb)`) — step-side-panel-resizer 와 동형.
  - `src/static/app.js`: `ATTACH_PANEL_WIDTH_KEY="web.attachSidePanel.width"`·`ATTACH_PANEL_MIN_W=240`·`_attachPanelMaxW()`(92vw)·`_applyAttachSidePanelWidth(panel)`(저장 너비 clamp 복원)·`setupAttachSidePanelResize()`(mousedown/touchstart 드래그, `width=innerWidth−clientX` clamp, dragstop 시 localStorage 저장, `dataset.wired` idempotent) 추가. 패널 open 경로(`composerActionsListItem` 클릭 핸들러)에서 표시 전 `setupAttachSidePanelResize()` + `_applyAttachSidePanelWidth(panel)` 호출.
- 비변경: 백엔드·RBAC·엔드포인트·스키마·첨부 업로드/목록 로직·다른 패널 0. 첨부 패널 초기 너비(280px)·열림/닫힘 애니메이션·목록 렌더 무변경.
- 검증: node --check app.js PASS. 잔여 = verify-completion --pre-commit → 배포(deploy_scope: included) → PB-0008 Windows-browser 시각검증(핸들 드래그 너비 변경 + 새로고침 후 복원).

## CHG-20260615-0271
- Date: 2026-06-15 (TASK-0271, **docs-only** — TASK-0269/0270 PB-0008 Windows-browser 시각검증 evidence 기록)
- Scope: agent-web-ui 문서만 — `docs/TEST.md` §4 Run 2건(TASK-0269·0270) 추가 + `docs/TASK.md` 두 항목 "잔여 PB-0008" → "완료(PASS)". src 코드 0.
- 변경: TEST.md §4 — ① TASK-0270 계정 override 상속(허용) 게이트(실 Chrome computed display: account.read/update/conv.ask=flex 상속허용, read.any=none 상속거부) ② TASK-0269 운영 권한 2그룹 분리·목록 조회 게이트 트리(내 대화 목록 조회 체크→내 동작 flex, 전체 동작 none). 둘 다 PASS.
- 비변경: 코드·테스트·CSS 0(순수 evidence).
- 검증: 라이브 배포(0270 main `8953dc1`, 0269 main `73755e9`, web Up healthy) 후 win-browser.py 실 Chrome computed display 실측. 스크린샷 `artifacts/pb0008-task0269/`·`artifacts/pb0008-task0270/`.

## CHG-20260615-0270
- Date: 2026-06-15 (TASK-0270, **Minor §12.3** — 계정 override 편집기 게이트 = 허용/상속(허용) 펼침)
- Scope: agent-web-ui (프론트 전용) — 사용자 요청(역할 트리 후속). 계정 override 편집기 disclosure 게이트가 '허용' 외에 '상속(허용)'(상속 + 역할 부여)에도 자식을 펼치도록. 트리/2그룹은 renderPermissionGrid 공유로 이미 적용됨.
- 변경:
  - `src/static/admin.js`:
    - `_applyPermissionDisclosure(containerEl, mode, showAll, inheritedGrants)` — override `gateSatisfied = value==="allow" || (value==="inherit" && inheritedGrants.has(code))`. checkbox 모드 gateSatisfied(체크) 무변경. recompute 클로저에 inheritedGrants 전파.
    - `renderPermissionGrid` opts 에 `inheritedGrants`(기본 빈 Set) 수용 + recompute 에 전파.
    - 계정 override 호출부: `adminState.roles` 에서 계정 역할 조회 → `role.permission_codes`(상속 baseline)로 `inheritedGrants` Set 구성해 opts 전달.
  - `src/static/admin.html`: 캐시버스터 `admin.js?v=20260615-task0270-inherit-gate`.
  - `tests/test_permission_dependency_map.py`: `compute_visibility_override` 에 `inherited` 파라미터 추가(상속(허용) 게이트) + 신규 `test_v7_override_inherit_allow_gate_reveals_children`.
- 비변경: 역할(checkbox) 모드·enforcement(권한 체크 code 기반)·override 저장 경로(select 값 그대로)·disclosure 가시성/도달성/트리·RBAC·엔드포인트·스키마. 상속 baseline = role.permission_codes 는 백엔드 계정 effective 와 동일 출처(정확).
- 검증: perm test **16 PASS**(신규 V7) + make test 컨테이너 회귀 0(exit=0) + node --check + jsdom 8/8. **잔여**: 배포 + PB-0008.

## CHG-20260615-0269
- Date: 2026-06-15 (TASK-0269, **Minor §12.3** — 운영 권한 대화 그룹 own/any 분리 + "목록 조회" 게이트 카테고리 트리)
- Scope: agent-web-ui — 사용자 요청(역할 트리 후속). 대화를 `내 대화 권한`/`전체 대화 권한` 2그룹으로 분리, `.any→.own` 1:1 종속을 "생성·조회 기반 > 동작" 카테고리로 교체. 권한 code·enforce 불변(group=UI 분류 메타).
- 변경:
  - `src/app.py`: `PERMISSION_DEFINITIONS` conversation 권한 `group` 코드 기반 분리 — `.any` → `"conversation_any"`(10), 나머지(create/ask/list.own/*.own/share.create) → `"conversation_own"`(13). code/label/description 불변.
  - `src/static/admin.js`: `PERMISSION_GROUP_ORDER`(conversation→conversation_own,conversation_any), `PERMISSION_GROUP_LABELS`(내 대화 권한/전체 대화 권한), `ADMIN_PERMISSION_SECTIONS` operate=[conversation_own,conversation_any,product,attachment], `PERMISSION_DEPENDENCIES` 재정의(create/list.own/list.any 루트; 내 동작→list.own·전체 동작→list.any).
  - `src/static/app.js`: 동일 group order/labels/`WORK_SCREEN_PERMISSION_SECTIONS` + `permissionGroupOf`(conversation.* → .any?conversation_any:conversation_own).
  - `src/static/admin.html`·`index.html`: 캐시버스터 `admin.js`·`app.js`?v=20260615-task0269-conv-split.
  - `tests/test_permission_dependency_map.py`: M4(own→any → list 게이트), V2(운영 루트 create/list.own/list.any), T2(그룹 분리+게이트 중첩) 갱신.
- 비변경: 권한 code·enforce(`_account_has_permission` 등 code 기반)·저장 경로·disclosure 가시성/도달성 로직·트리 렌더·RBAC·엔드포인트·스키마(GroupName VARCHAR(32) 무절단, ON DUPLICATE KEY UPDATE 멱등→마이그 불요).
- 검증: perm test **15 PASS** + make test 컨테이너 회귀 0(백엔드 RBAC 무회귀) + node --check(admin.js·app.js) + jsdom 20/20. outside-voice [SUBAGENT:rbac-adversarial] **SHIP**(REV-20260615-0269). **잔여**: 배포 + PB-0008.

## CHG-20260615-0268
- Date: 2026-06-15 (TASK-0268, **docs-only** — TASK-0267 트리 UI PB-0008 Windows-browser 시각검증 evidence 기록)
- Scope: agent-web-ui 문서만 — `docs/TEST.md` §4 Run 추가 + `docs/TASK.md` TASK-0267 "잔여 PB-0008" → "완료(PASS)". src 코드 0.
- 변경: TEST.md §4 에 2026-06-15 (TASK-0267 트리 UI) Run — CLI(15 PASS·jsdom 14/14) + Windows-browser. 결과 PASS: ① `.permission-grid-list` computed flex column(2열 grid 아님, 뒤틀림 해소) ② 자식 row depth 1·margin-left 24px 들여쓰기(트리) ③ 운영 권한 "더 보기 · 1개 부여됨" computed color rgb(180,35,31) 빨강 가시. 사용자 두 보고 충족.
- 비변경: 코드·테스트·CSS 0(순수 evidence).
- 검증: 라이브 배포(main `f6ccb7b`, web Up healthy, 서빙 단일열 CSS + `_orderItemsAsTree`) 후 win-browser.py 실 Chrome computed style 실측. 스크린샷 `artifacts/pb0008-task0267/`.

## CHG-20260615-0267
- Date: 2026-06-15 (TASK-0267, **Minor §12.3** — 권한 grid 트리 UI 재구성: 2열 grid 뒤틀림 해소 + "더 보기 부여됨" 빨강 가시성)
- Scope: agent-web-ui (프론트 전용) — 사용자 보고(운영 권한 테스트 중 ① 빨강 미가시 ② 항목 숨김 뒤틀림 → tree UI 요청). 2열 grid 가 행 숨김 시 가로 reflow 로 뒤틀리고 "더 보기" 빨강 badge 가 묻히던 것을, 단일 열 트리로 전환. 백엔드/RBAC/저장 0.
- 변경:
  - `src/static/admin.js`: 신규 `_orderItemsAsTree(items)` — 그룹 내 권한을 `PERMISSION_DEPENDENCIES` 트리 DFS(부모 먼저, 자식 들여쓰기)로 정렬, `[{permission, depth}]` 반환(루트=부모 없음/타 그룹 → depth 0, 자식 depth+1, 누락 안전망). 렌더 루프가 이를 순회 + row wrapper(label/field)에 `data-perm-depth`. 구 `permission-row-dependent` 토글 제거.
  - `src/static/styles.css`: `.permission-grid-list` **2열 grid → 단일 열 flex column**. `[data-perm-depth="1"|"2"]` 들여쓰기 + 좌측 가이드 border + 가로 tick 연결선(트리 위계). `.permission-group-more` grid-column→`align-self:flex-start`. `.permission-toggle-card.permission-row-dependent` accent 규칙 제거(depth 기반 대체).
  - `src/static/admin.html`: 캐시버스터 `?v=20260615-perm-tree-ui`(styles.css + admin.js).
  - `tests/test_permission_dependency_map.py`: 신규 `_order_items_as_tree` 포팅 + T1~T4(트리 정렬 부모-자식 순서·depth 정합, own→any 중첩, account.read 루트 depth0, grid-list 단일열 CSS 계약).
- 비변경: disclosure 가시성(`_applyPermissionDisclosure`)·게이트·도달성(그룹 유지/"부여됨" 배지)·저장 경로(순서 무관)·`has-granted` 빨강 CSS·제품 카드 임베드·RBAC·엔드포인트·스키마.
- 검증: perm test **15 PASS** + make test 컨테이너 회귀 0(exit=0) + node --check + CSS brace(1167=1167) + jsdom 실 DOM 14/14. **잔여**: 배포(web 만) + PB-0008.

## CHG-20260615-0265
- Date: 2026-06-15 (TASK-0265, **docs-only** — TASK-0264 PB-0008 Windows-browser 시각검증 evidence 기록)
- Scope: agent-web-ui 문서만 — `docs/TEST.md` §4 Run 추가 + `docs/TASK.md` TASK-0264 "잔여 PB-0008" → "완료(PASS)". src 코드 0.
- 변경: TEST.md §4 에 2026-06-15 (TASK-0264 disclosure 추가 단순화) Run — Environment Windows-browser(실 Chrome/148) + CLI(make test 11 PASS·jsdom 17/17). 결과 PASS: ① 역할(checkbox) account.delete 부여+게이트OFF → computed display:none(권한 행 0 노출)+"더 보기 7개·1개 부여됨" ② 계정(override) account.delete=거부+게이트inherit → override-grid 행 computed display:none(unscope 수정 실증). 사용자 요구 두 편집기 충족.
- 비변경: 코드·테스트·CSS 0(순수 evidence).
- 검증: 라이브 배포(main `d35299e`, web Up healthy, 서빙 unscoped `[data-perm-code][hidden]` + `.has-granted`) 후 win-browser.py 실 Chrome computed display 실측. 스크린샷 `artifacts/pb0008-task0264/`.

## CHG-20260615-0264
- Date: 2026-06-15 (TASK-0264, **Minor §12.3** — 권한 disclosure 추가 단순화: 게이트 미충족 시 부여 세부 권한도 숨김, forceVisible 제거)
- Scope: agent-web-ui (프론트 전용) — 사용자 보고("더 보기 클릭 전 항목 노출, 최대한 숨김"). TASK-0257 의 비파괴 forceVisible 이 게이트 OFF·부분부여 역할서 부여 항목을 노출하던 것을 제거. 백엔드/RBAC/스키마 0.
- 변경:
  - `src/static/admin.js`:
    - `_applyPermissionDisclosure`: `forceVisible`(부여 권한+조상 강제표시) **제거** → `isVisible` 은 게이트 체인 충족 시에만 true(부여 무관). orphan 칩 호출 제거.
    - `_refreshGroupDisclosure(.., isExplicit)`: 부여 항목 있는 그룹은 checkbox 모드서도 vanish 안 함(`hiddenCount===rows.length && grantedCount===0` 만 vanish) + "더 보기 ${n}개 더 보기 · ${hiddenGranted}개 부여됨"(`has-granted` 클래스) → 부여 권한 도달성·표면화 보존.
    - `_setPermOrphanWarn`/`_permLabel` 함수 제거(부여+게이트OFF 행이 이제 숨겨져 무의미).
  - `src/static/styles.css`: `.permission-group-more.has-granted`(부여됨 강조) 추가. `[hidden]` 강제 규칙 셀렉터를 `.permission-grid [data-perm-code][hidden]` → **컨테이너 무관 `[data-perm-code][hidden]`** 로 unscope(계정 override 편집기 `.override-grid` 행 커버 — TASK-0258 갭 수정, 적대 리뷰 MINOR 흡수).
  - `src/static/admin.html`: 캐시버스터 `?v=20260615-perm-collapse-granted`(styles.css + admin.js).
  - `tests/test_permission_dependency_map.py`: 가시성 포팅서 force 제거, V1/V4/V5/V6 를 새 동작(게이트 OFF 부여 항목 숨김 + 게이트 충족 시 도달)으로 재작성, C1 을 unscoped 셀렉터 검증으로 강화.
- 비변경: PERMISSION_DEPENDENCIES·게이트 reveal·마스터 게이트·own→any·저장 경로(hidden row 도 `:checked`/select 그대로 읽어 누락 0)·RBAC·엔드포인트·스키마.
- 검증: perm test **11 PASS** + make test 컨테이너 회귀 0(exit=0) + node --check + CSS brace(1130=1130) + jsdom 17/17. **잔여**: 배포(web 만) + PB-0008.

## CHG-20260615-0262b
- Date: 2026-06-15 (TASK-0262b PB-0008 Windows-browser 시각검증 evidence 후속 — 코드 변경 0, docs+scenario. CHG-20260615-0262 main `eb7be30` 머지·web 재배포 이후).
- 변경: `docs/TEST.md` §4 `Environment: Windows-browser` Run 기록(chip dot 색 실측) + `docs/TASK.md` PB-0008 체크박스 [x] + `docs/REVIEW.md` REV-20260615-0262b [SKIPPED] + `tests/win-browser-task0262-chip-conn-color.scenario.json`(재현 시나리오).
- 검증 결과(PB-0008 실제 Windows Chrome/148, main `eb7be30`): 선택 제품 94(unstable)=빨강 rgb(220,38,38)/`is-fail`, 95(healthy)=초록 rgb(22,163,74)/`is-ok`, auto=중립 회색(conn 클래스 reset). aria-label 상태 병기. 콘솔 0.
- 비변경: src 코드 0(evidence·docs·scenario only). REV-20260615-0263 [SKIPPED:pb0008-evidence-docs-only].

## CHG-20260615-0262
- Date: 2026-06-15 (TASK-0262, **Minor §12.3** — TASK-0261 후속 frontend-only: 선택 제품 chip dot 도 네트워크 상태색)
- Scope: agent-web-ui (프론트 전용) — `static/app.js`(`renderProductChip`), `static/styles.css`(chip dot conn 색 규칙 3개), `static/index.html`(캐시버스터). 백엔드 무변경(`conn_status_overall` 은 TASK-0261 이 이미 `/api/session`·`/api/auth/me` product 에 첨부).
- 변경:
  - `renderProductChip`: pinned 제품의 `conn_status_overall` → `#productChipDot` 에 `.composer-product-chip-dot--conn` + `connStatusMeta(status)` 클래스(is-ok/is-fail/is-unknown). dot 은 `aria-hidden` 이므로 상태 라벨을 chip `aria-label` 에 ` · 데이터소스 {라벨}` 로 병기 + dot `title`. 매 렌더 conn 클래스 reset(auto/미바인딩 전이 시 모드색 복귀, stale 클래스 누적 방지).
  - `styles.css`: `.composer-product-chip .composer-product-chip-dot--conn.{is-ok=success 초록,is-fail=danger 빨강,is-unknown=text-muted}`. 드롭업 conn 규칙과 동형 — specificity (0,3,0) 동일이라 모드색 규칙(`[data-mode=pinned] .dot`)보다 **소스 뒤**에 두어 override.
- 비변경: 백엔드/RBAC/엔드포인트/스키마/conn_health 0. 드롭업 목록 항목(`buildProductDropupItem`) 동작 0(TASK-0261 그대로). 순수 트리거 chip 색만 보완.
- 검증: `node --check`(app.js) PASS + CSS brace 1131=1131 + `make test` 회귀 0 + ruff clean. REV-20260615-0262 [SKIPPED:frontend-color-readonly-no-rbac]. **잔여**: 배포(web) + PB-0008.

## CHG-20260615-0259
- Date: 2026-06-15 (TASK-0259, **docs-only** — TASK-0257/0258 PB-0008 Windows-browser 시각검증 evidence 기록)
- Scope: agent-web-ui 문서만 — `docs/TEST.md` §4 Run 추가 + `docs/TASK.md` 0257/0258 항목의 "잔여 PB-0008" → "완료(PASS)" 갱신. src 코드 0.
- 변경: TEST.md §4 에 2026-06-15 (TASK-0257 점진적 세분화 + TASK-0258 [hidden] CSS 핫픽스) Run — Environment: Windows-browser(실 Chrome/148 relay) + CLI(make test 11 PASS·jsdom 30/30). 결과 PASS: ① 역할 신규=관리 콘솔 그룹만(계정/역할/감사/설정 vanish, computed display:none) ② 관리 콘솔 접근 체크→그룹 등장 ③ 계정 그룹 펼침=계정 조회만+나머지 6개 computed display:none(배포 CSS, TASK-0258 핫픽스 실측)+더 보기 ④ override 모드 그룹 비vanish+더 보기 도달. 사용자 두 예시 라이브 충족.
- 비변경: 코드·테스트·CSS 0(순수 evidence 기록).
- 검증: 라이브 배포(web `Up healthy`, 서빙 styles.css `[data-perm-code][hidden]{display:none!important}`, 캐시버스터 `?v=20260615-perm-disclosure-hidefix`) 후 win-browser.py 실 Chrome 으로 computed display 실측. 스크린샷 `artifacts/pb0008-task0257/`·`artifacts/pb0008-task0258/`.

## CHG-20260615-0258
- Date: 2026-06-15 (TASK-0258, **Minor §12.3** — TASK-0257 핫픽스: disclosure hidden row 가 실브라우저에서 안 숨겨지던 `[hidden]` CSS override 버그)
- Scope: agent-web-ui (프론트 전용) — within-group 행 게이팅이 실브라우저에서 무력(PB-0008 검출). `.permission-toggle-card{display:flex}` 가 UA `[hidden]{display:none}` 를 동일 specificity·후순위로 override → `el.hidden=true` 가 무력화(computed display:flex). jsdom 은 CSS 캐스케이드 없어 미검출.
- 변경:
  - `src/static/styles.css`: 신규 규칙 — `.permission-section[hidden], .permission-group[hidden], .permission-grid [data-perm-code][hidden] { display: none !important; }`. disclosure 의 section/group/row 모든 숨김 대상에 display:none 강제(기존 `.search-modal-overlay[hidden]{display:none}` 선례와 동형).
  - `src/static/admin.html`: 캐시버스터 `styles.css?v=20260615-perm-disclosure-hidefix` + `admin.js?v=...-hidefix`.
  - `tests/test_permission_dependency_map.py`: 신규 `test_c1_hidden_rows_force_display_none` — styles.css 에 `[data-perm-code][hidden]` display:none !important + group/section 규칙 존재 정적 검증(회귀 가드).
- 비변경: JS 로직·PERMISSION_DEPENDENCIES·저장 경로·RBAC·엔드포인트·스키마 0. 동작 방향 strictly safer(hidden 인 행을 *실제로* 숨김 — 권한을 드러내지 않음).
- 검증: `test_c1` 포함 **11 PASS** + make test 컨테이너 회귀 0(exit=0) + CSS brace(1125=1125) + 실브라우저 수정 CSS 주입 후 computed display 재확인(account.read=flex, 나머지 6개=none). **잔여**: 배포(web 만) + 최종 PB-0008.

## CHG-20260615-0257
- Date: 2026-06-15 (TASK-0257, **Major §12.3** 권한 편집 surface — 관리 콘솔 계정·역할 권한 편집기 점진적 세분화(progressive disclosure))
- Scope: agent-web-ui (프론트 전용) — `관리 콘솔 > 계정, 역할 > [각 항목]` 권한 grid 가 카테고리별 전 권한을 평면 노출해 핵심 게이트가 묻히던 것을, 종속성 기반 row 단위 disclosure 로 점진 세분화. 백엔드 RBAC enforce·권한 code·persistence·엔드포인트·스키마 **무변경**(편집기 표시 UX 전용).
- 변경:
  - `src/static/admin.js`:
    - 신규 `PERMISSION_DEPENDENCIES`(child→선행 parent, 31엔트리) — 관리 권한 마스터 게이트 `console.access`(account.read/role.read/audit.read.own/system_prompt.global.read 부모=console.access); 그룹 base 가 세부 게이트; 운영 권한 `.any`→`.own`.
    - 신규 `_applyPermissionDisclosure`/`_refreshGroupDisclosure`/`_setPermOrphanWarn`/`_permLabel` — 매 변경/초기에 row 가시성 재계산. `forceVisible`(명시 설정 권한+조상)로 비파괴(부여 권한 미숨김), `gateSatisfied`(checkbox=체크 / override=허용)로 자식 노출, "세부 권한 N개 더 보기" 강제 노출 토글 + orphan 경고칩(checkbox 모드).
    - `renderPermissionGrid`: 각 row wrapper 에 `data-perm-code` 부여 + change/bulk 핸들러에 `recompute()` 배선 + 말미 초기 `recompute()`. mode 분기(적대 리뷰 흡수): 그룹/섹션 통째 vanish 는 checkbox(역할) 모드만, override(계정) 모드는 그룹 비숨김+row 만 접음(§10.6 "전체 표시" 정합, "더 보기" 항상 도달).
  - `src/static/styles.css`: `.permission-group-more`(더 보기 토글) / `.permission-orphan-warn`(경고칩) / `.permission-toggle-card.permission-row-dependent`(종속 row 미세 좌측 accent). reveal 즉시 토글(애니메이션 없음 — 레이아웃 뒤틀림 방지).
  - `src/static/admin.html`: 캐시버스터 `styles.css?v=20260615-perm-disclosure` + `admin.js?v=20260615-perm-disclosure`.
  - `docs/CONVENTIONS.md` §10.6: progressive disclosure 표시 단계 계층 명문화(마스터 게이트·비파괴 BLOCKING·그룹 vanish=checkbox 한정).
- 비변경: 저장 경로(`querySelectorAll("input:checked")` / `select[data-override-code]`)는 hidden row 도 그대로 읽어 권한 누락 0; product 그룹 임베드 카드·dynamic product.access.* 처리·§10.6 section/group 정렬 무변경.
- 검증: 신규 `tests/test_permission_dependency_map.py` **10 PASS**(맵 정합 M1~M4 + 가시성 불변식 V1~V6) + make test 컨테이너 **전체 회귀 0**(make exit=0) + ruff clean + `node --check`(admin.js) + CSS brace(1113=1113) + **jsdom 실 DOM 30/30**. **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008 Windows-browser 시각검증.

## CHG-20260615-0255b
- Date: 2026-06-15 (TASK-0255b PB-0008 Windows-browser 시각검증 evidence 후속 — 코드 변경 0, docs+scenario. CHG-20260615-0255 main `a410986` 머지·재배포 이후).
- 변경: `docs/TEST.md` §4 에 `Environment: Windows-browser` Run 기록(엔드포인트 insight_health + UI "인사이트 스캔 상태" 행 구분 실증) + `docs/TASK.md`(양 feature) PB-0008 체크박스 [x] + `docs/REVIEW.md` REV-20260615-0255c [SKIPPED] + `tests/win-browser-task0255-insight-health.scenario.json`(재현 시나리오).
- 검증 결과(PB-0008 실제 Windows Chrome/148, 배포 main `a410986`): `mysql-kr-an2-auth` insight_health=unstable/circuit_open(fail 11) → UI "⚠ 연결 불안정 (미커버)"; `mysql-gz-qa-kr` healthy/ok → "정상 (분석됨)". 운영자 구분 인지 충족. 콘솔 0. 자격증명 미노출.
- 비변경: src 코드 0(evidence·docs·scenario only). REV-20260615-0255c [SKIPPED:pb0008-evidence-docs-only].

## CHG-20260615-0255
- Date: 2026-06-15 (TASK-0255 cross-feature — 주 변경은 agent-core CHG-20260615-0255. 본 항목은 **web 표면화만**)
- Scope: agent-web-ui — `app.py`(신규 `_read_insight_datasource_health` + `admin_list_datasources` 에 `insight_health` 첨부, RO·graceful), `static/admin.js`(`datasourceInsightHealth` 맵 + 배지 enrich + `_dsInsightHealthLabel` + 상세 "인사이트 스캔 상태" 행), `static/admin.html`(admin.js ?v= 캐시버스터).
- 목적: insight-worker 가 PG 에 영속한 datasource 연결 health(agent-core R2)를 관리콘솔에 표면화 — 운영자가 **"연결 불안정 미커버"(circuit_open/unstable) vs "권한 실패"(perm_failed)** 를 구분. 권한 게이트 `console.access` 유지, 자격증명/민감정보 비노출.
- 검증: `make test` GREEN. PB-0008 Windows-browser 시각검증(배포 후) — CHECK#13.

## CHG-20260615-0254b
- Date: 2026-06-15 (TASK-0254 PB-0008 Windows-browser 시각검증 evidence 후속 — 코드 변경 0, docs-only. CHG-20260615-0254 main `f8845cc` 머지·web 재배포 이후).
- 변경: `docs/TEST.md` §4 에 `Environment: Windows-browser` Run 기록(자동 eval 계측 HOLD/FOLLOW 결과) + `docs/TASK.md` TASK-0254 에 PB-0008 PASS 체크박스 + `docs/REVIEW.md` REV-20260615-0254b [SKIPPED] + 스크린샷 `artifacts/pb0008-task0254/{01_prompt_pane_after,02_prompt_textarea_top}.png`.
- 검증 결과(PB-0008 실제 Windows Chrome/148, 배포 main `f8845cc`): 제품1(KR) 제품 프롬프트 '자동 작성' SSE 스트리밍 중 ① **HOLD**(위로 scrollTop=60) 후 토큰 8샘플 **전부 top=60 고정**(오버플로 748→852 증가) = 위로 스크롤 위치 유지, ② **FOLLOW**(하단 이동) 후 토큰 73샘플 **전부 dist=0** = 최하단 추종. 사용자 원요구("작성 현황 텍스트 상단 보기") 충족. 콘솔 에러 0.
- 비변경: src 코드 0(evidence·docs only). REV-20260615-0255 [SKIPPED:pb0008-evidence-docs-only].
- Files: unit/feature-0003-agent-web-ui/docs/{TEST,TASK,REVIEW,MODIFY}.md, artifacts/pb0008-task0254/*.png

## CHG-20260615-0254
- Date: 2026-06-15 (TASK-0254, **Minor §12.3** — 관리 콘솔 제품 프롬프트 '자동 작성' SSE 스트리밍 중 스크롤 stick-to-bottom 도입)
- Scope: agent-web-ui (프론트 전용) — `관리 콘솔 > 제품 > [항목] > 제품 프롬프트` 의 '자동 작성'(TASK-0237 SSE 토큰 스트리밍)이 매 토큰 갱신마다 무조건 textarea 를 최하단으로 강제 이동시켜, 사용자가 작성 중 상단 텍스트를 읽으려 위로 스크롤해도 다음 토큰에서 즉시 최하단으로 끌려가던 이슈.
- 변경:
  - `src/static/admin.js` (autoBtn 클릭 핸들러 `handleFrame`):
    - `ev === "token"` 분기: append **직전** `atBottom = scrollHeight - scrollTop - clientHeight <= 8` 판정 → 텍스트 append 후 `atBottom` 일 때만 `scrollTop = scrollHeight`. 무조건 `textarea.scrollTop = textarea.scrollHeight` 제거. 위로 스크롤한 상태면 위치 유지, 최하단에 있으면 갱신을 따라 내려감. (임계 8px = 분수 픽셀/브라우저 clamp 오차 흡수). 첫 토큰은 `textarea.value=""` 직후라 빈 상태 → atBottom=true → 정상적으로 따라감.
    - `ev === "done"` 분기: 최종 `textarea.value` 재할당이 스크롤을 상단으로 되돌리는 부수효과 보정 — 재할당 전 `atBottom`/`prevTop` 포착 후 재할당 직후 `scrollTop = atBottom ? scrollHeight : prevTop` 로 사용자 위치 보존.
  - `src/static/admin.html`: 캐시버스터 `admin.js?v=20260615-task0254-prompt-stream-scroll`.
- 비변경: SSE 백엔드 계약(`/api/admin/products/{id}/prompt/generate/stream`)·토큰 프레임 파싱·재진입 abort·RBAC·`done` 의 pending 저장(`setSystemPromptPending`)·meta 표시(`applyAutoGenMeta`)·styles.css 무변경. 순수 클라이언트 렌더 동작만 조정.
- 검증: `node --check admin.js` PASS + 서버 `.strip()` 사실 확인(app.py:16519) + make test 컨테이너 **회귀 0 PASS**(전 진행 100%·skip 2·fail/error 0, make exit=0) + ruff clean. **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008 Windows-browser 시각검증(스트리밍 중 위로 스크롤 유지 / 최하단일 때만 따라감).

## CHG-20260612-0253
- Date: 2026-06-12 (TASK-0253, **Minor §12.3** — 관리 콘솔 head-of-line blocking 2건 제거: A datasource ↻ 새로고침 / B 제품 분석 완료율)
- Scope: agent-web-ui — TASK-0250 배포 후 PB-0008 중 사용자 발견. "느린 대상이 정상 대상을 뒤에서 대기시키는" head-of-line 2곳 제거(이벤트 루프 비블로킹 + 제품별 병렬·개별 즉시표시).
- 변경:
  - `src/app.py`:
    - (A) `admin_test_datasource`: `_db.probe_datasource({**ds, "host": _pin})` 직접 호출 → **`await asyncio.to_thread(_db.probe_datasource, {**ds, "host": _pin})`**. async 핸들러가 동기 블로킹 probe(도달불가 시 connection_timeout 8s 점유)로 이벤트 루프를 막아 동시 /test 가 직렬화되던 것을 스레드풀 이관으로 해소(`/api/ask` `asyncio.to_thread(run_agent)` 기존 패턴). SSRF pinned IP(`_pin`)·DNS rebinding 차단 경로 무변경(인자 그대로 전달).
    - (B) `admin_products_insight_coverage`: 단건(`?product_id=`) 요청 시 대상 제품 계산·캐시 put **이후 break** 추가 — 무관 제품 순회/계산 생략(프론트 제품별 병렬 단건 호출 패턴 정합). 응답 형태(`{coverage:{...}}`) 불변.
  - `src/static/admin.js`:
    - (A) datasource 추가 드롭다운 refresh 핸들러: 캐시 비운 뒤 `_rebuildDsAddList()` + 별도 `Promise.all(force:true)` **2벌 probe** → `_rebuildDsAddList(true)` 단일 경로(중복 제거, `_kickDsConn(dsk, status, forceProbe)` 로 force 전파). `_probeDatasourceConn` 의 in-flight dedup 을 force 무관 적용(↻ 연타 중복 방지, REV MINOR-2).
    - (B) `productCoverageLoading`(전역 bool) → `productCoverageLoadingIds`(제품별 Set) + `_isProductCoverageLoading(pid)` 헬퍼. `loadProductInsightCoverage` 를 전체 1회 fetch → **제품별 `?product_id=N` 단건 병렬**(동시성 cap `_COV_FETCH_MAX=4` via 신규 `_runWithConcurrency`) + 각 제품 settle 즉시 그 배지만 렌더. 4개 표시 함수(`buildCoverageBadge`/`buildProductCoverageDetail` summaryChip·refreshBtn.disabled·hint·`redrawChips` measuring)가 제품별 로딩 참조.
  - `src/static/admin.html`: 캐시버스터 `admin.js?v=20260612-task0253-headofline`.
- 비변경: RBAC(console.access)·datasource CRUD·`/test` 응답 계약(errno 만, 자격증명 비유출)·완료율 계산 함수(`_compute_product_insight_coverage`)·conn_health 모니터·styles.css 무변경.
- 검증: node --check(admin.js) + py_compile(app.py) + 신규 `test_datasource_test_nonblocking.py`(3)·`test_insight_coverage_endpoint.py`(5) **8 PASS** + make test 컨테이너 **전체 회귀 0** + ruff clean. outside-voice REV-20260612-0253 SHIP-WITH-FIXES→흡수. 잔여: 배포(web 만) + PB-0008.

## CHG-20260612-0249b
- Date: 2026-06-12
- Task: TASK-0249 PB-0008 Windows-browser 시각검증 evidence 후속 (코드 변경 0 — REV-20260612-0249 적대 리뷰 SHIP·main `12f5c5e` 머지 완료 이후).
- 변경: `docs/TEST.md` §4 Windows-browser Run 기록 + `tests/win-browser-task0249-coverage.scenario.json`(시각검증 시나리오) 추가 + `docs/FUNCTION.md` AC-0462 PB-0008 완료 표기 + `docs/TASK.md`/`docs/REVIEW.md` 검증 결과 기록.
- 검증 결과(PB-0008 Windows Chrome/148, 배포 main `12f5c5e`): 제품94 요약 100%(571/571), datasource accordion 별 dbgame(player) 99/99·dbcommon(common, 타 서버) 111/111·dbauth(auth, 타 서버) 10/10 각 마이크로바 100%·DB✓ 시각 실증 — 0/0 해소. 스크린샷 `/tmp/win-browser-shots/task0249/{10,11,12}*.png`.
- 비변경: src 코드 0(evidence·docs only). REV-20260612-0251 [SKIPPED:visual-verify-followup] PASS.
- Files: unit/feature-0003-agent-web-ui/docs/{TEST,FUNCTION,TASK,REVIEW}.md, unit/feature-0003-agent-web-ui/tests/win-browser-task0249-coverage.scenario.json

## CHG-20260612-0248
- Date: 2026-06-12 (TASK-0248, **Major §12.3** — 관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환; 스키마는 feature-0002 CHG-20260612-0248)
- Scope: agent-web-ui — 제품 삭제가 참조 대화를 거부(400)하던 가드 제거 → 삭제 허용 + 그 제품 pinned 대화를 **차단(blocked)** 으로 전환(이력 열람·공유는 가능, 새 메시지 진행 불가).
- 변경:
  - `src/app.py`:
    - 신규 상수 `_BLOCKED_PRODUCT_DELETED_REASON` + `_conversation_block_info(cid, *, conn=None)`(backend-aware 차단 상태 조회, 조회실패 fail-open — PG 모드는 `_pg_connect` 별도 open/close, 전달 conn 미close) + `_block_conversations_for_product(pid, reason, *, conn=None)`(`UPDATE agent_runtime.core_conversations SET blocked_at=now(), blocked_reason=%s WHERE product_id=%s AND blocked_at IS NULL` PG 정본 / MySQL 폴백, 재차단 방지, rowcount 반환).
    - `admin_delete_product`: `in_use>0` 거부(400) **제거** → 미차단 참조 COUNT(`... AND blocked_at IS NULL`) 산출 → 기존 WebProducts cascade 삭제 commit → **commit 후** `_block_conversations_for_product` 호출(cross-store) → 응답 `{ok, product_id, blocked_conversations}` + audit change_json `referencing_conversations`.
    - `ask`(기존대화 분기): 소유권 체크 직후 `_conversation_block_info` → blocked 면 403(slot 획득 前, conn.close 후 return).
    - `_list_conversations_pg`(SELECT + item) 및 MySQL `_list_conversations` parity 에 `blocked`/`blocked_at`/`blocked_reason` 필드 추가(동일 계약).
    - MySQL `_ensure_web_tables` 폴백: `AgentCoreConversations` 에 `blocked_at DATETIME`/`blocked_reason VARCHAR(256)` 멱등 ALTER(try/except).
  - `src/static/app.js`: `canAskInConversation`(blocked→false) + `sendPrompt` 차단 가드(토스트) + `renderComposer`(isBlocked → 입력창 disabled·전송버튼 aria-disabled·"차단된 대화" 안내, busy/권한 분기 우선순위 정렬) + `renderConversationHeader`(부제 맨앞 "🚫 차단됨") + `renderConversationList`(`.is-blocked` 행 + "차단" 배지).
  - `src/static/styles.css`: `.conv-item.is-blocked`(opacity .72 + 제목 line-through) + `.conv-item-blocked-badge`(danger 토큰 `--danger`/`--danger-soft`).
  - `src/static/admin.js`: 삭제 confirm 문구("참조 대화는 '차단' 상태로 전환·되돌릴 수 없음") + 결과 토스트(`삭제됨 (대화 N개 차단)`).
  - `src/static/index.html`·`admin.html`: 캐시버스터 `?v=20260612-task0248-blocked-conv`(styles.css·app.js·admin.js).
- 비변경: RBAC 권한 카탈로그(product.manage·conversation.ask 재사용)·신규 엔드포인트 0·share-create 제한 0·fork 동작 0(접근불가 제품 auto 강등 정합 보존).
- 검증: node --check(app.js·admin.js) + py_compile(app.py) + CSS brace 1108=1108 + make test 컨테이너 회귀 0(600 passed/2 skip) + 신규 7 PASS. outside-voice REV-20260612-0248 SHIP. 잔여: 배포(make migrate 先) + 라이브 + PB-0008.

## CHG-20260612-0250
- Date: 2026-06-12 (TASK-0250, **Major §12.3** — 연결 health 모니터; web/admin 측. 코어는 feature-0002 CHG-20260612-0250)
- Scope: agent-web-ui — 관리 콘솔 datasource 연결상태를 **백그라운드 모니터가 사전계산한 값으로 즉시 표시**(per-item lazy `/test` probe + 4-cap 세마포어 자동경로 폐기) + web 프로세스에 conn_health 모니터 기동.
- 변경:
  - `src/app.py`: `@app.on_event("startup")` `_start_conn_health_monitor`(`conn_health.start_monitor(datasources.health_probe_provider())`) + `@app.on_event("shutdown")` `_stop_conn_health_monitor`. `admin_list_datasources` 가 각 datasource 에 `conn_status`(=`conn_health.snapshot()` 조회, **좌표 비노출** status/elapsed_ms/checked_at 만) 첨부.
  - `src/static/admin.js`: datasources 목록 로드 시 `conn_status`→`datasourceConnStatus` 캐시 반영. `_kickDsConn` 가 캐시 hit(=모니터 populated) 즉시 표시, miss(unknown 콜드 edge)/force(↻)만 lazy `/test` 폴백 → 자동 토글 경로 세마포어 대기 폭주 제거. ↻ 새로고침은 명시 force probe.
  - `src/static/admin.html`: 캐시버스터 `?v=20260612-conn-health-status`.
- 비변경: RBAC(console.access)·datasource CRUD·스키마·`/test` 엔드포인트·기존 배지 painter 무변경(데이터 출처만 사전계산으로).
- 검증: node --check + make test 컨테이너 회귀 0. outside-voice REV-20260612-0250(코어 feature-0002). 잔여: 배포 후 PB-0008 admin 연결상태 시각검증.

## CHG-20260612-0249
- Date: 2026-06-12
- Task: TASK-0249 (제품 insight 완료율 멀티 datasource(1:N) + 대소문자 매칭 수정), **Minor §12.3** (web-ui app.py + agent-core db.py 교차 — db.py 변경은 CHG-20260612-0249 로 feature-0002 MODIFY.md 교차 기록). 동시세션 `task0248-product-delete-blocked-conv` 가 TASK-0248 선점 → §13.1 재번호 후 0249.
- 진단: 사용자 보고 — `관리 콘솔 > 제품 > 킹스레이드(KR_QA, id 94) > 데이터 소스 & 접근 가능 데이터베이스` 에서 DB객체 분석은 진행되는데 **테이블 분석 현황 0/0**. KR_QA 는 7개 접근 DB 가 각각 다른 datasource(다른 서버)에 바인딩된 진성 1:N 제품. **Bug A**: `_compute_product_insight_coverage` 가 제품 primary datasource 하나(auth)만 해석해 7 DB 전부를 단일 auth 서버에 질의 → 타 서버 DB 0 테이블. **Bug B**: Linux MySQL `lower_case_table_names=0` 라 등록명 `dbcommon`(소문자)↔실제 `dbCommon` 어긋나 `TABLE_SCHEMA IN (...)` 0행(db.py LOWER() 로 별도 해소). 두 결함 모두 있어야 정확히 0/0.
- 변경 (`unit/feature-0003-agent-web-ui/src/app.py`, `_compute_product_insight_coverage` 전면 리팩터):
  - 접근 DB rows 를 effective datasource_key(`row.datasource_key or product["datasource_key"]`) 별 **그룹핑**. 그룹마다 `_resolve_product_insight_scope(conn, {"id":pid, "datasource_key":dskey})` 로 scope/coords/engine/allow_null 해석 → SSRF 체크 → 그룹 좌표로 라이브 카탈로그 질의(MySQL=그룹 schemas 일괄, MSSQL=DB별 연결) → 그룹 scope 로 rag_objects 분자 조회.
  - PG 통찰 연결은 그룹 간 **1회 재사용**(내부 헬퍼 `_analyzed_sets_for_scope(scope, allow_null)` 가 scope 만 바꿔 조회), `finally` 에서 close.
  - 원래 노출 순서(`order`) 보존해 합산 → 프런트 per_db 1:1 매칭 유지. 응답 키 계약(per_db: db/connected/schema_analyzed/tables_total/tables_analyzed/note + top: pct/analyzed_objects/total_objects/measurable/reason/engine/default_db) **불변**.
  - `measurable = connected_count > 0`. 한 datasource 만 해석/연결 실패 → 그 DB 만 `connected:False`+note(부분 측정), 전부 실패 → `measurable:False`(reason: 미해석이면 "데이터소스를 해석할 수 없습니다", 도달실패면 "연결할 수 없습니다").
- 비변경: `_resolve_product_insight_scope`(reset/db-insights 공유 헬퍼) — 의도적 무변경. RBAC·스키마·암호화·엔드포인트 shape·insight-worker 런타임 0. db-insights/insight-reset 계산 경로 무영향.
- 검증: 신규 `tests/test_insight_coverage.py` 5 테스트(C1~C5) + make test 컨테이너 **전체 599 passed/2 skipped 회귀 0** + ruff clean + py_compile. 라이브 시뮬레이션 기대: 제품94 ≈ 42.6%(243/571), 제품1 = 100%(무회귀).
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/tests/test_insight_coverage.py, unit/feature-0002-agent-core/src/modules/db.py, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md, docs/STATUS.md
- Rollback: `_compute_product_insight_coverage` 를 단일 datasource(primary 해석) 버전으로 환원 + db.py `LOWER(TABLE_SCHEMA)` → `TABLE_SCHEMA` 환원(단 0/0 버그 재발).

## CHG-20260612-0246b
- Date: 2026-06-12
- Task: TASK-0246 정련 (연결상태 배지 정렬 컨벤션 통일), **Minor §12.3** (CSS 1줄 + 캐시버스터)
- 진단: CHG-20260612-0246 배포 후 PB-0008 측정 — name/engine/coord 행별 left spread=0(정렬 완료), 단 연결배지가 `justify-self:end`(우측 정렬)라 배지 left spread=25px(폭 차이). 사용자 컬럼 정렬 선호([[feedback_row_list_column_alignment]] — "행별 left spread=0px") + sibling `.cov-db-row`(TASK-0245)가 status/reset 를 `justify-self:start` 로 통일한 것과 정합 위해 배지도 좌측 정렬로 맞춤.
- 변경 (`styles.css` 1줄): `.admin-ds-picker-item .admin-ds-conn` `justify-self: end` → **`justify-self: start`**(고정폭 104px 열에서 배지 자연폭 좌측 정렬 → 배지 left 도 행별 동일). `admin.html` 캐시버스터 `?v=20260612-ds-picker-colalign2`.
- 비변경: 그 외 grid 트랙·열 폭·probe·백엔드·RBAC 전부 CHG-0246 그대로.
- 검증: CSS brace 균형(1105/1105) + 배포 후 PB-0008 재측정(전 열 left spread=0). REV-20260612-0246 [SKIPPED:trivial-grid-align] 연장.
- Files: unit/feature-0003-agent-web-ui/src/static/{styles.css,admin.html}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: `justify-self: start` → `end` 환원.

## CHG-20260612-0246
- Date: 2026-06-12
- Task: TASK-0246 ("+ 데이터소스 추가" 드롭다운 항목 열 정렬 — 고정 열 폭 grid), **Minor §12.3** (CSS-only 단일 블록; admin.js·백엔드·RBAC·스키마 0). 동시세션 db-row-align cycle 이 TASK-0245·CHG/REV/REQ-0245·AC-0385 선점(PR #189/#191 main 14a296f) → §13.1 재번호 0245→0246, AC→0460.
- 진단: 사용자 — "목록 폭이 문자열 길이에 따라 일정하도록(현재 들쭉날쭉)". 라이브 DOM 측정(win-browser): 항목 폭(542px)·우측 끝(1174px)은 일정하나, `.admin-ds-picker-item` 이 `display:flex` + 이름 `flex:1 1 auto` 라 행마다 이름·좌표·배지 텍스트 길이에 따라 엔진 pill(x961/936/967)·좌표(x1011/986/1018)·연결배지(x1105/1080/1080) 의 시작 x 가 어긋나 열이 세로로 정렬되지 않음. (동일 종류의 정렬 결함을 별 요소 `.cov-db-row` 에서 고친 동시세션 TASK-0245 와 무겹침 — 셀렉터 격리.)
- 변경 (`unit/feature-0003-agent-web-ui/src/static/styles.css`, 단일 블록):
  - `.admin-db-picker-item.admin-ds-picker-item`(복합 셀렉터 — DB picker `.admin-db-picker-item` 단독 행은 미영향): `display:flex` → **`display:grid`** + `grid-template-columns: auto minmax(0,1fr) 56px 124px 104px` + `align-items:center; gap:8px`. 고정 트랙이라 모든 행이 동일 열 geometry 를 공유 → 이름(`1fr`)만 가변 흡수하고 엔진/좌표/상태 열은 정렬.
  - `.admin-ds-picker-engine`: flex 잔여 제거 → `justify-self:start` + `max-width:100%`+ellipsis. `.admin-ds-picker-coord`: `justify-self:start` + ellipsis(기존 `max-width:38%`·flex 제거). `.admin-ds-picker-item .admin-ds-conn`: `justify-self:end`(배지 우측 정렬 일치).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260612-ds-picker-col-align`(styles.css·admin.js).
- 열 폭 근거(라이브 측정): 엔진 42~43px(→56), 좌표 최장 `10.31.21.71:11433` 87px(→124, FQDN 초과 시 ellipsis+title), 상태 최장 `연결됨 · 8.9ms` 94px(→104, justify-self:end). 이름 잔여 ≈186px(콘텐츠영역 518 − 고정 332). datasource 키 초과 시 ellipsis.
- 비변경: admin.js(probe/캐시/세마포어/구조 0), 백엔드 app.py, RBAC, 스키마, 엔드포인트, DB picker(`.admin-db-picker-item` 단독)·`.cov-db-row`(동시세션 0245)·accordion. CSS 한 블록.
- 검증: CSS brace 균형(1105/1105) + REV-20260612-0246 [SKIPPED:trivial-grid-align](단일 규칙 cosmetic, PB-0008 가 실질 게이트). 배포 후 PB-0008 Windows-browser 열 정렬 시각검증.
- Files: unit/feature-0003-agent-web-ui/src/static/{styles.css,admin.html}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: `.admin-ds-picker-item` 를 `display:flex` 로 환원 + engine/coord/conn 의 justify-self 제거(flex 속성 복원), 캐시버스터 환원.

## CHG-20260612-0244
- Date: 2026-06-12
- Task: TASK-0244 (관리 콘솔 제품 "+ 데이터소스 추가" 드롭다운 폰트 정합 + 연결 상태 표면화), **Major §12.3** (frontend-only 다중 파일 + 네트워크 probe 추가; RBAC·스키마·백엔드 엔드포인트 0)
- 진단 (사용자 요청 2건): 관리 콘솔 > 제품 > [항목] > 데이터소스 탭의 `+ 데이터소스 추가` 목록이 ① 각 항목 `${ds.key} — ${ds.engine} @ ${ds.host}:${ds.port}` 단일 raw `<span>`(무클래스)라 같은 화면 accordion 행(`.ds-acc-name` 굵은 이름 + `.ds-acc-engine` pill)·`+ 데이터베이스 추가` picker(`.admin-db-picker-name` 구조)와 폰트/정렬이 이질적, ② 연결 상태를 `⋯ > 연결 테스트`(일회성 토스트)로만 확인 가능하고 목록엔 표시가 없음.
- 변경 (frontend-only):
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `adminState.datasourceConnStatus`(Map, key(lower)→{state,elapsed_ms,error}) 신설.
    - `_paintDsConnBadge(el, entry)` — 주어진 `<span>` 에 연결 상태(확인 중/연결됨·ms/연결 실패) in-place 렌더(비동기 probe 완료 시 동일 노드 갱신).
    - `_probeDatasourceConn(key, {force})` — `/api/admin/datasources/{key}/test` POST. 캐시 우선 + in-flight dedup(`_dsConnInflight`). **동시 probe 4개 cap 세마포어**(`_dsConnAcquire`/`_dsConnRelease`) — 도달불가 datasource 다수 시 8s(db.py connection_timeout)×N web 스레드 동시 점유 방지(REV nit 선반영).
    - `_rebuildDsAddList` 재구성: 항목 = `[체크박스 · 이름(.admin-db-picker-name 재사용) · 엔진 pill(.admin-ds-picker-engine) · 좌표(.admin-ds-picker-coord) · 연결상태 배지(.admin-ds-conn)]`. 헤더(`.admin-ds-picker-head`)에 "데이터소스 · 연결 상태" 라벨 + `↻ 새로고침`(캐시 무효화 후 재probe, stopPropagation+preventDefault). 드롭다운 열림/재렌더 시 `_kickDsConn` 으로 캐시 hit→즉시 / miss→'확인 중' 후 probe. 토글 재렌더는 캐시 hit 라 재probe 폭주 없음.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-ds-picker-head`/`-head-label`/`-refresh`(sticky 헤더), `.admin-ds-picker-engine`(= `.ds-acc-engine` 토큰 1:1 복제로 accordion 과 정합), `.admin-ds-picker-coord`(muted ellipsis), `.admin-ds-conn`(.is-ok/.is-fail/.is-checking — `●` 점 + 한글 라벨 병행해 색-단독 비의존, is-checking 펄스 + prefers-reduced-motion 존중).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260612-ds-picker-status`(styles.css·admin.js).
- 비변경: 백엔드(app.py 무수정 — 기존 `/datasources/{key}/test` 재사용), RBAC(console.access·canDs 게이트 보존), 스키마, 암호화, 엔드포인트 shape, datasource 바인딩 스테이징 흐름(stageAdd/Remove/SetPrimary·applyAllPending 무관), accordion ⋯ 메뉴.
- 검증: node --check admin.js PASS + CSS brace 균형(1103/1103) + outside-voice subagent 디자인/정합 적대적 리뷰 **SHIP**(BLOCKER 0; 시각정합 = `.admin-ds-picker-engine` ≡ `.ds-acc-engine` 토큰 동일·`.admin-db-picker-name` 재사용 확인, 동시성 nit 세마포어로 선반영, 색맹 대응 ●+라벨 확인) REV-20260612-0244. 배포 후 라이브 + PB-0008 Windows-browser 시각검증.
- Files: unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css,admin.html}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: admin.js 의 datasourceConnStatus/_paintDsConnBadge/_probeDatasourceConn/세마포어 + `_rebuildDsAddList` 구조 재구성 되돌림(단일 span 복원), styles.css 의 `.admin-ds-picker-*`/`.admin-ds-conn` 블록 제거, 캐시버스터 환원.

## CHG-20260612-0243
- Date: 2026-06-12
- Task: TASK-0243 (TASK-0242 후속 — MSSQL db-insights catalog 귀속 수정), **Minor §12.3** (단일 read 함수 격리 수정; RBAC·스키마·암호화·엔드포인트 shape 0)
- 진단: TASK-0242 의 `_compute_product_db_insights` 가 by_db 를 `rag_objects.schema_name` 으로 묶었는데, **MSSQL 은 schema_name 이 SQL 스키마(`dbo`)** 라 등록 DB(catalog, 예: `GameLog_100`)와 차원이 다르다. 결과로 MSSQL 의 모든 통찰이 `dbo`/`dev50` 한두 바구니로 뭉쳐, 프런트가 `insByDb[등록DB명]` 로 조회할 때 전부 빗나가 **MSSQL 등록 DB 행이 모두 "역할 미파악"** 으로 떴다(라이브 제품91 by_db=['dbo','dev50'] vs 등록 DB=GameLog_100/dk_data_release/… 무교집합). MySQL 은 db==schema 라 우연히 정상 동작했음.
- 변경 (`unit/feature-0003-agent-web-ui/src/app.py`, 단일 함수):
  - 신규 `_db_catalog_from_object_key(object_key, engine, object_type)` — `rag_objects.object_key`(`{scope}:{path}`)에서 catalog 파싱. MySQL: path 첫 segment(=db). MSSQL: schema=`{catalog}.{sqlschema}`(2)·table=`{catalog}.{sqlschema}.{table}`(3) → 첫 segment, bare(default_db, segment 부족)→None.
  - `_compute_product_db_insights`: ① SELECT 에 `o.object_key` 추가, ② 로컬 `engine` 변수화, ③ 그룹핑 키를 schema_name → 파싱한 catalog 로 변경. MSSQL 의 catalog 미귀속(bare default_db) 행은 skip, MySQL 은 catalog==schema_name 이라 **결과 byte-identical**(폴백도 schema_name).
  - SELECT 외 다른 코드 무수정. `_compute_product_insight_coverage`(완료율)·`admin_product_insight_reset`(초기화)는 object_key 미사용(schema_name/table_name 컬럼만) — **무영향**(코드 주석 + 전체 회귀로 확인).
  - `unit/feature-0003-agent-web-ui/tests/test_db_insights.py`: 기존 행 6-tuple(object_key) 보강 + `_db_catalog_from_object_key` 파서 2 + MSSQL catalog 귀속 1 테스트 추가(14→17).
- 비변경: RBAC·스키마·암호화·엔드포인트 shape·coverage/insight-reset 계산·insight-worker write 경로(feature-0002) 0. MySQL by_db 키 집합 불변(라이브 대조).
- 검증: db_insights 17 PASS + make test 컨테이너 **전체 회귀 0**(coverage·reset 등 전 스위트 통과) + ruff clean + py_compile. **side-effect 격리 분석**: `_db_catalog_from_object_key`/`_compute_product_db_insights` 각 호출처 1곳, 다른 object_key 사용처는 MinIO 첨부·coverage(schema_name 전용)로 무관. 적대적 subagent 리뷰(REV-20260612-0243). 배포 후 라이브 MSSQL by_db=catalog 매칭 + PB-0008.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/tests/test_db_insights.py, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION,TEST}.md
- Rollback: `_db_catalog_from_object_key` 제거 + 그룹핑 키 schema_name 환원 + SELECT object_key 제거.

## CHG-20260612-0242
- Date: 2026-06-12
- Task: TASK-0242 (관리 콘솔 > 제품 > 데이터소스 & 접근 가능 데이터베이스 — DB별 insight-worker 파악 내용 표면화 + 추가 picker 분석상태), **Major §12.3** (신규 read 엔드포인트 + 다중 파일; RBAC·스키마·암호화 0)
- 배경: 각 DB 행은 완료율 마이크로바(TASK-0223/0229)만 보이고 insight-worker 가 파악한 *역할/도메인*(texts.text_content 의 "domain / summary / usage / key columns")은 UI 에 없었음. `+ 데이터베이스 추가` 드롭다운도 DB 이름만 나열. 사용자 요청: 각 DB 에서 파악된 내용을 같이 출력(역할 명시) + 완료율/분석상태를 목록에도 표시. 사용자 확정: 등록 DB 행은 **펼침 없이 한 줄 인라인**(DB명·설명·분석률·객체 N/N·동일), picker 는 **도메인 힌트 + 분석상태(미분석/분석중/분석됨)**.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - 신규 `_clean_insight_segment(text)` — insight text_content 에서 "X domain:" 선두 라벨 + "key columns:" 꼬리 제거하고 summary/usage 만 ' · ' 결합(한 줄 설명용).
    - 신규 `_compose_db_insight_text(ent)` → (한 줄 description = 도메인 — 요약, 멀티라인 detail_text = schema 전문 + 테이블별 정제 본문[hover title용]). schema insight 없으면 table 도메인들로 합성.
    - 신규 `_insight_worker_liveness(conn)` — heartbeat KV(`insight_worker_last_cycle_at`/`_last_status`)로 {alive,age_sec,status}. alive=status∈{ok,skip_locked} AND age≤max(30,STALE_SEC)(insight._is_*_heartbeat_fresh 정합). picker '분석중' 판정.
    - 신규 `_compute_product_db_insights(conn, product, datasource_key=None)` — 편집 대상 datasource scope(coverage 와 동일 `_resolve_product_insight_scope`)로 `public.rag_objects ⋈ texts`(conversation_id='__global__', scope_key='common', object_type∈schema/table, datasource_key=scope[OR NULL if allow_null]) 조회 → DB(schema_name lower) 별 {db,domain,description,detail_text,analyzed_schema,analyzed_tables,analyzed_objects}.
    - 신규 엔드포인트 `GET /api/admin/products/{product_id}/db-insights` — console.access 게이트, `?datasource=<key>` 멀티 datasource scope 선택(요청 datasource 가 제품 바인딩이 아니면 400 — `_list_product_datasources` 검증), 미존재 product 404. read-only.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - state `productDbInsights`(Map `${pid}::${dsKey}`→payload) + `productDbInsightsLoading`(Set). 로더 `loadProductDbInsights({productId,datasourceKey,refresh,onDone})`(캐시+중복요청 차단) + `_dbInsightsKey`.
    - `buildDbRoleCell(insRow,{loading})` — 등록 DB 행의 한 줄 설명(역할 미파악/파악 중 fallback, 전문 hover title). `redrawChips` 가 이름 다음·진척 셀 앞에 삽입 + reset-spacer(그리드 7컬럼 일관).
    - `buildPickerInsightMeta(insRow,worker)` — picker 항목 도메인 힌트 + 분석상태 칩(분석됨=analyzed_objects>0 / 분석중=0+worker.alive / 미분석). `buildPicker` 가 각 항목에 부착.
    - `_ensureDbInsights` 지연로드 hook — `_refreshAccessibleDbs`(양 분기)·`_switchEditDs`(via refresh) 에서 호출, 완료 시 redraw. `loadProductInsightCoverage(refresh)` 시 insight 캐시 무효화.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.cov-db-row` 그리드 6→7컬럼(설명 추가) + `.cov-db-role`/`-muted`/`.cov-db-reset-spacer` + `.admin-db-picker-name`/`-domain`/`-status`(is-done/is-running[pulse, prefers-reduced-motion 존중]/is-none). 기존 디자인 토큰만.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260612-db-insight-surface`(admin.js + styles.css).
  - `unit/feature-0003-agent-web-ui/tests/test_db_insights.py`: 신규 14 테스트(세그먼트 정제 2 / 한 줄 합성 3 / worker liveness 3 / 집계 2 / 엔드포인트 4).
- 비변경: RBAC 권한 카탈로그(console.access 재사용), 스키마(웹·agent_runtime·PG), 암호화, 기존 엔드포인트 shape, insight-worker/agent-core 런타임. 완료율(coverage) 응답·계산 무변경(별도 read 경로).
- 검증: db_insights 14 PASS(올바른 PYTHONPATH) + make test 컨테이너 회귀 0(점매트릭스 100%) + ruff clean + node --check admin.js + CSS brace balance(1090/1090) + py_compile. REV-20260612-0242. 배포 후 PB-0008 Windows-browser 시각검증 예정.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css,admin.html}, unit/feature-0003-agent-web-ui/tests/test_db_insights.py, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: app.py 의 4 신규 함수 + 엔드포인트 제거, admin.js 의 state/로더/3 빌더/_ensureDbInsights/redrawChips·buildPicker 삽입 되돌림, styles.css 신규 클래스 + 그리드 복원, admin.html 캐시버스터 복원, test_db_insights.py 삭제.

## CHG-20260612-0240
- Date: 2026-06-12 (TASK-0240, **Minor §12.3** — datasource picker 클리핑 수정 + 데이터소스 추가 체크박스 토글 통일. frontend only)
- 사용자 보고(연속 2건): ① "`+ 데이터베이스 추가` 버튼으로 나타나는 리스트가 패널 내부로 잘리는 이슈", ② "`+ 데이터소스 추가` 버튼 또한 `+ 데이터베이스 추가` 리스트와 같이 체크박스 토글 형식으로 구성".
- 진단(① — Playwright clip 조상 재현):
  - `.admin-db-picker-list` 는 `position:absolute; top:calc(100%+4px); max-height:220px`. 펼치면 드롭다운(top=492, bottom=712)이 **3중 overflow 조상**에 잘림 — (a) `.ds-acc-body{overflow:hidden}`(내가 TASK-0239 펼침 애니메이션 때 도입, 가장 가까운 조상, bottom=504 → 220px 중 12px만 노출), (b) `.admin-detail-col{overflow-y:auto}`(제품 상세 패널 스크롤 컨테이너 — 긴 폼 스크롤에 필요해 제거 불가, bottom=820), (c) `.admin-workspace{overflow:hidden}`. `position:absolute` 인 한 (b) 스크롤 컨테이너가 패널 하단을 넘는 드롭다운을 계속 자름.
- 변경 (`src/static/styles.css`, `src/static/admin.js`, `src/static/admin.html` — frontend only):
  - **① 클리핑 원천 제거(css)**: `.admin-db-picker-list` 를 `position:absolute` 플로팅 → **inline 정상 흐름**(`margin-top:4px; width:100%; max-height:220px; overflow-y:auto`)으로 전환. 목록 자신만 스크롤하고 어떤 overflow 조상도 자르지 못함(클리핑 박스가 아니게 됨). `.ds-acc-body` 의 `overflow:hidden` 제거(재발 금지 주석 — 펼침 페이드는 opacity 위주라 overflow 불필요).
  - **② 데이터소스 추가 체크박스 토글(admin.js+css)**: accordion 하단 `<select class="ds-acc-add-select">`(단일 선택) → DB picker 와 동일한 inline 체크박스 토글 드롭다운(`.ds-acc-add-btn`(=`.admin-db-picker-btn` 재사용) + `.admin-db-picker-list`). `_rebuildDsAddList()` 가 등록 datasource 전체를 항목으로, **effective(desired) 바인딩이면 체크 상태**로 렌더. 체크 → `stageAddDatasource`+`_afterBindChange(key)`(새 datasource 펼침), 해제 → `stageRemoveDatasource`+`_afterBindChange`. 매 토글 후 `_rebuildDsAddList` 로 체크 상태 재동기화. 버튼 aria-haspopup/aria-expanded + 바깥 클릭 닫기. 즉시 API 아니라 desired 스테이징 유지(TASK-0239) → "모두 적용" 일괄. `.ds-acc-add-select` CSS → `.ds-acc-add-btn`(점선 버튼) + add-row `position:relative`.
  - 캐시버스터 `?v=20260612-ds-bulk-apply`→`?v=20260612-ds-picker-inline`.
- 비변경: RBAC·DB 스키마·암호화·**백엔드 0**(엔드포인트 그대로). 스테이징·diff-apply 로직(TASK-0239)도 그대로 — 데이터소스 추가의 진입 UI(select→체크박스)만 교체.
- 검증: **Playwright 실 헤드리스 브라우저**(라이브 admin, pid=92) — clip 조상 재현(ds-acc-body·admin-detail-col·admin-workspace 3중 확인) → 수정 후 4-test(DB picker 무클리핑·hitInside / ds picker 체크박스 3항목·바인딩된 것 체크·무클리핑 / 체크 토글 시 pending+1·행 2개·서버 1개 불변 / ⋯ 메뉴 hit-test 정상) + 토글 양방향(체크 +1 → 같은 항목 해제 시 desired==baseline 복귀 pending 0·행 1개) PASS, 콘솔/pageerror 0. make test 회귀 0. node --check PASS. CSS 1076/1076 balanced.
- Files: src/static/{admin.js,styles.css,admin.html}, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: frontend only — revert 시 TASK-0239 absolute picker + select UI 복귀(단 클리핑 재발). 데이터/스키마 영향 없음.

## CHG-20260612-0241
- Date: 2026-06-12 (TASK-0241, **Major §12.3** — 요청 취소 즉시 처리 + 취소 직후 재요청. cross-cutting feature-0002+0003)
- 사용자 보고: "assistant 요청 후 취소했을 때, 취소 메시지 후 곧바로 취소처리 + 채팅창 즉시 사용·재요청 가능하게(현재는 취소 후 응답 대기). 구조 변경 부작용도 모두 고려."
- 진단: 백엔드 취소(`/api/cancel` cancel 플래그 + agent 루프 폴링)는 정상. 진짜 결함 = 프런트 `sendPrompt` 가 `/api/ask`(worker mode 동기응답 long-poll attach)를 `await` 하고 `state.busyConversations.delete` 를 그 `finally` 에서만 → run 종료 시점까지 입력창 잠김. 또 즉시-재요청 허용 시 같은 conversation 의 old(취소)/new run 동시성 부작용 노출.
- 변경:
  - **app.js**: `cancelCurrentRun` optimistic — busy/입력창 즉시 해제 + pending 말풍선·진행폴링·경과타이머 정리 + in-flight `/api/ask` fetch abort(`state.askAbortControllers` Map) + 포커스 + `/api/cancel` 백그라운드 발사. `state.userCanceledKeys` Set 으로 sendPrompt catch 가 사용자취소를 식별해 에러 토스트/타임아웃 복구 다이얼로그 억제. lazy-create sentinel↔earlyCid 키 이중성은 `cancelKeys`(양쪽 키 취소) + `askKey`(effective 키 정렬) + 발사 직전 취소 재확인(`throw AbortError`)으로 처리.
  - **app.py**: `/api/cancel` 이 pending/running 무관 즉시 `set_run_status("canceled", only_if_current_run=True)` → orphan `/api/ask` attach 가 슬롯 즉시 반납. `_dispatch_ask_run_worker` attach 루프에 `request.is_disconnected()` + job-aware(`_get_ask_job_status(job_id)`) 종료 → 웹 슬롯 누수 차단(`request` 를 `_dispatch_ask_run`→worker 배선). **enqueue 선기록을 `set_run_status("processing", run_id="enqpre-<uuid>")`(sentinel)로** — KV `last_status_run_id` 가 직전(취소) run 으로 남아 orphan terminal write 가 가드를 우회·새 요청 processing 을 클로버하던 BLOCKER 차단.
  - **agent_core.py + memory.py**: `set_run_status(only_if_current_run=True)` supersede 가드(저장된 last_status_run_id 가 다른 run 이면 write skip). agent 루프 terminal write(canceled/done/error) 3곳 적용. claim/sentinel takeover 는 default(무조건) 유지.
- 정합: sentinel(enqueue) + only_if_current_run(terminal/cancel) + 무조건 takeover(claim, agent_core:2472) 3중. 나열 가능한 모든 인터리빙에서 새 run processing 보존·취소전용 canceled 오삭제 없음(2차 적대 리뷰 확인). orphan 은 현 LLM step(동기, 인터럽트 불가) 종료 후 답변 기록 없이 종료.
- 검증: 신규 `unit/feature-0002-agent-core/tests/test_set_run_status_supersede.py` 5건 PASS + 전체 pytest 회귀0(F/E 0, 2 skip) + ruff All checks passed + node --check + py_compile.
- follow-up(별 cycle, LOW): never-claimed pending job + sentinel KV 잔존(pending-job TTL reaper 부재 — 본 변경 이전 class, 악화 아님; 20분 후 stale_error·max_wait 슬롯반납 완화).

## CHG-20260612-0239
- Date: 2026-06-12 (TASK-0239, **Minor §12.3** — datasource accordion 후속 버그/UX 3건. frontend only)
- 사용자 보고(TASK-0238 재설계 직후 실사용): ① "⋯ 버튼이 작동하지 않아 검증 필요", ② "데이터소스 추가 후 일괄 적용 형식에 포함 안 됨(추가 시 즉시 반영되는 이슈)", ③ "각 데이터소스 클릭 시 깜빡임 → 부드러운 애니메이션 적용".
- 진단:
  - **①(기능 버그, Playwright hit-test 재현)**: `.ds-acc-menu-btn` 클릭 시 JS 는 `.ds-acc-menu` 의 `hidden` 을 정상 토글(`display:flex`)하나, TASK-0238 에서 행에 준 `.ds-acc-row{overflow:hidden}` 이 행 경계 밖(`top:100%`)으로 드롭되는 `position:absolute` 메뉴를 **클리핑** → 메뉴가 화면에 안 그려지고 `document.elementFromPoint(메뉴중앙)` 이 메뉴 항목이 아닌 뒤의 `.cov-db-editor` 를 맞힘(클릭 불가).
  - **②(일관성)**: 콘솔의 다른 모든 편집(productMeta/productDatabases/systemPrompts)은 `adminState.pending` 에 스테이징 후 footer "모두 적용" 으로 일괄 저장. datasource 바인딩만 즉시 API(`POST/PATCH/DELETE /datasources`) → 일괄 흐름 밖 anomaly.
  - **③(UX)**: 행 전환(`_switchEditDs`)·바인딩 변경이 전체 `renderProductDetail()` 재렌더 + 비동기 `_refreshAccessibleDbs`(칩 비웠다 다시 채움)를 유발 → 깜빡임.
- 변경 (`src/static/admin.js`, `src/static/styles.css`, `src/static/admin.html` — frontend only):
  - **① CSS**: `.ds-acc-row` 의 `overflow:hidden` 제거(재발 금지 주석) + `transition`(active 강조 부드럽게). 둥근 모서리는 `.ds-acc-head` 가 직접 — 좌측만, `:only-child`(메뉴 없는 행)는 양쪽, `.is-active`(펼친 행)는 하단 직각 분기.
  - **② 일괄 적용 스테이징(admin.js)**: 신규 `pending.productDatasources` Map(productId → {baseline:[{datasource_key,is_primary}], desired:[…]}). 헬퍼 `_ensureDatasourcePending`/`_settleDatasourcePending`/`effectiveProductDatasources`/`stageAddDatasource`/`stageRemoveDatasource`/`stageSetPrimaryDatasource` + 비교 `_dsBindNorm`/`_dsBindEqual`/`datasourceDirtyProductCount`. ⋯ 메뉴(기본지정/제거)·추가 select 가 즉시 API 대신 stage* 호출 + 로컬 `_afterBindChange`(accordion 만 재렌더). `pendingChangeCount`·`refreshPendingUI`(detail "데이터소스 바인딩 N")·`cancelAllPending`·삭제제품 GC 에 편입. `applyAllPending` 에 diff-apply 루프 추가 — baseline↔desired diff 로 제거(DELETE)→추가(0개면 PATCH, 이후 POST)→primary 재지정(POST is_primary) 순, **제품 DB PUT 보다 먼저** 수행(추가 바인딩에 DB PUT 가능) + 제거된 datasource 의 접근DB draft 는 PUT skip(서버가 바인딩과 함께 삭제 — 고아 방지).
  - **③ 깜빡임(admin.js+css)**: `_switchEditDs`·`_afterBindChange` 가 전체 렌더 대신 accordion 로컬 재렌더 + `redrawChips()` 동기 선호출(구 datasource DB 잔상 제거 후 비동기 정교화). `.ds-acc-body` 에 `@keyframes ds-acc-body-in`(opacity+translateY) 펼침 애니메이션, `@media (prefers-reduced-motion:reduce)` 로 비활성화.
  - 캐시버스터 `?v=20260612-ds-accordion`→`?v=20260612-ds-bulk-apply`.
- 비변경: RBAC·DB 스키마·암호화·**백엔드 0**(엔드포인트 add/remove/set/test/databases 그대로 재사용). desired-state 는 클라이언트 조립 후 기존 엔드포인트로 diff 호출.
- 검증: **Playwright 실 헤드리스 브라우저**(라이브 admin, pid=92) 4-test + 제거 일괄적용 — ⋯ 클릭 시 "연결 테스트" hit-test PASS, 추가 시 pending+1·행2개·**서버 1개 불변**, 전환 직후 동기 DB리스트 렌더(무 flash), "모두 적용" 후 서버 2개·pending 0, 제거 스테이징 시 서버 불변→적용 후 제거. 콘솔/pageerror 0. make test(컨테이너 pytest+ruff) 회귀 0. node --check PASS. CSS 1075/1075 balanced.
- Files: src/static/{admin.js,styles.css,admin.html}, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: frontend only — 직전 커밋으로 revert 시 TASK-0238 즉시-API accordion 복귀(단 ⋯ 메뉴 클릭불가 재발). 데이터/스키마 영향 없음.

## CHG-20260612-0238
- Date: 2026-06-12 (TASK-0238, **Minor §12.3** — datasource 패널 통합 accordion 재설계; 동시세션 cycle 이 TASK-0237 선점(자동작성 SSE)→본 cycle 은 0238)
- 사용자 요청: "기능은 모두 정상 동작 확인. 단 디자인적으로 중복되는 분류가 많고 통일감이 없다 → gstack 스킬을 적극 사용해 보충." 멀티 datasource(TASK-0228~0236)를 여러 동시세션이 증분 수정하며 누적된 시각 부채.
- 진단 (gstack `/design-review` + codex outside-voice 소스 감사):
  - **중복 분류**: datasource 정보가 3곳 — ① "데이터 소스" 섹션 칩, ② "편집 대상 데이터소스" `<select>`, ③ "접근 가능 데이터베이스" 헤더 배지(dbTitleDs). 같은 데이터를 3 표현으로 반복.
  - **통일감 부재**: 시각 패턴 3종 혼재 — 파란 pill(datasource 칩) / 점선 pill(시스템 DB 칩) / 둥근 사각 행(DB 항목). 칩 액션 아이콘 불일치(★기본/⟳테스트/×제거 가 칩마다). DB행은 텍스트버튼(초기화)+아이콘(×) 혼재. 헤더 배지는 제목에 공백 없이 붙고 대소문자 불일치. rgba 하드코딩(토큰 미사용).
- 변경 (표현 계층 교체, 편집 로직 보존):
  - `src/static/admin.js` (`renderProductDetail` datasource 영역 ~242줄 재작성):
    - **제거**: 별도 "데이터 소스" 섹션, 편집대상 `<select>`(_editDsSelect), 헤더 배지(dbTitleDs/`_updateDbSectionLabel`/`_renderDsChips`/dsChips), 독립 "연결 테스트" 버튼.
    - **신설**: 단일 섹션 "데이터 소스 & 접근 가능 데이터베이스" → `buildProductCoverageDetail` → datasource accordion(`.ds-acc`) → "＋ 데이터소스 추가" select. 각 datasource = `.ds-acc-row`(`▸/▾` caret + 이름 + 엔진 + "기본" 배지 + `⋯` 메뉴). 펼친(active) 행 아래로 `dbEditorWrap`(시스템칩 + DB리스트 + 추가 picker) 인라인 이동.
    - `_buildDsMenu(b)`: 행별 `⋯` 메뉴 — 연결 테스트 / 기본으로 지정(primary 아닐 때) / 바인딩 제거. 흩어진 ★/⟳/× + 공용 연결테스트 버튼을 한 곳으로 통일.
    - `_renderDsAccordion()`: 바인딩 배열로 행 재구축 + active 행 아래 dbEditorWrap 이동. `_switchEditDs(key)`: draft 보존 후 `_editDsKey` 전환 + `_renderDsAccordion` + `_refreshAccessibleDbs`. `_reloadProductDatasources()`: 바인딩 변경 후 adminState 정본 동기화 + `renderProductDetail()` 전체 재렌더(TASK-0236 교훈 유지).
    - **보존 클로저**(회귀 최소화): draft/`_swapDraftContents`/`_loadDraft`/`_draftKeyFor`/redrawChips/buildPicker/`_refreshAccessibleDbs`/`_serverDbsFor`. `let _editDsKey` 는 accordion 사용 전 선언(TASK-0236 TDZ 수정 유지).
  - `src/static/styles.css`: `.admin-db-ds-badge` 제거. `.ds-acc*`(`.ds-acc-row`/`.is-active`/`.ds-acc-head`/`.ds-acc-caret`/`.ds-acc-name`/`.ds-acc-engine`/`.ds-acc-primary`/`.ds-acc-body`/`.ds-acc-menu-wrap`/`.ds-acc-menu-btn`/`.ds-acc-menu`/`.ds-acc-menu-item`/`.ds-acc-add-row`/`.ds-acc-add-select`/`.cov-db-editor`) 신설 — 디자인 토큰(`--primary`/`--primary-soft`/`--border`/`--r-md`/`color-mix`)만 사용, 단일 시각 패턴(둥근 행).
  - `src/static/admin.html`: 캐시버스터 `?v=20260612-prompt-stream`→`?v=20260612-ds-accordion`(styles.css·admin.js).
- 비변경: RBAC 카탈로그·DB 스키마·암호화·엔드포인트 shape·백엔드 0(엔드포인트는 기존 datasources/datasource/test 재사용). 표현 계층만 교체.
- 검증: **Playwright 실 헤드리스 브라우저**(라이브 admin) — 단일(pid=92)·멀티(추가 후 2행)·MSSQL 캡처 + 펼침/접힘/전환(active 이동 + DB목록 datasource 반영)/추가 동작 PASS, 콘솔/pageerror 0. make test(컨테이너 pytest) 회귀 0. node --check admin.js PASS.
- Files: src/static/{admin.js,styles.css,admin.html}, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: 표현 계층만 교체이므로 직전 커밋(8be6487) 으로 revert 시 기존 칩+select+배지 UI 복귀(편집 로직 동일). 데이터/스키마 영향 없음.

## CHG-20260612-0237
- Date: 2026-06-12 (TASK-0237, **Major §12.3** — 자동작성 LLM 토큰 스트리밍 + OpenAI legacy 명명 정리; 동시세션 cycle 이 TASK-0231~0236 선점→§13.1 재번호 0233→0237)
- 사용자 요청: 제품 프롬프트 "자동 작성"이 최대 90초 LLM 호출 동안 "생성 중…" spinner 뿐이라 진행을 알 수 없음 → 토큰 스트리밍으로 실시간 표시.
- 변경 (feature-0003 측):
  - `src/app.py`: ① `_collect_product_prompt_context` 헬퍼 추출 — 기존 `admin_generate_product_prompt`(POST)의 MySQL 제품/스키마 조회 + PG 인사이트 수집 + knowledge_block + create_kwargs 조립을 비스트리밍/스트리밍 공유(중복 제거). 인증·권한·제품부재 실패 시 `(JSONResponse, None)` 반환. ② 신규 `GET /api/admin/products/{id}/prompt/generate/stream` — 인증·수집을 generator 진입 전 완료(export_audit_events_csv 패턴), 별 스레드 `produce()`가 `chat.completions.create(stream=True)` 동기 iterate → `loop.call_soon_threadsafe` 로 `asyncio.Queue` 브릿지(단일 uvicorn 이벤트 루프 블로킹 차단). SSE event `progress`→`token`(증분)→`done`(prompt+meta)|`error`. `truncated` = 마지막 chunk finish_reason=='length'. `StreamingResponse(media_type="text/event-stream", X-Accel-Buffering:no, Cache-Control:no-cache)`. ③ 기존 POST 핸들러는 헬퍼 사용으로 재작성(동작 동일, 비스트리밍 안전망). ④ `_sse_pack`(ensure_ascii=False). ⑤ `_get_openai_client`→`_get_llm_client` import(CHG agent-core 0237 정합). ⑥ `_resolve_session_default_model` env 소스 `LLM_MODEL or OPENAI_MODEL`.
  - `src/static/admin.js`: autoBtn 핸들러를 `apiFetch`(즉시 json) 우회 → `fetch + response.body.getReader() + TextDecoder + "\n\n" 프레임 파싱`. `token`→textarea append+글자수 카운터+자동 스크롤, `progress`→단계 라벨, `done`→최종 prompt 정합+`setSystemPromptPending`+`applyAutoGenMeta`(grounded/truncated 경고 — 기존 로직 헬퍼 추출), `error`→실패 메시지. `AbortController` 재진입 방어, `!resp.ok`(403/404/503 JSON) 분기.
  - `src/static/admin.html`: 캐시버스터 `?v=20260612-ds-detail-rerender`→`?v=20260612-prompt-stream`(styles.css·admin.js).
- 동반 변경 (feature-0002): `_get_openai_client`→`_get_llm_client` rename + alias, `OPENAI_API_BASE` 제거, env backward-compat. agent-core MODIFY.md CHG-20260612-0237 참조.
- 비변경: RBAC 카탈로그·DB 스키마·암호화·기존 엔드포인트 shape(신규 stream GET 추가 외). 비스트리밍 POST 응답 동일.
- 검증: 신규 `tests/test_prompt_generate_stream.py` 6(SSE 직렬화/파싱 라운드트립 + Queue 브릿지 누적/truncated/error) + 기존 truncation 3 PASS. node --check admin.js PASS. app.py AST 구문 OK. 시각 동작은 PB-0008(배포 후) 확인.
- Files: src/app.py, src/static/{admin.js,admin.html}, tests/test_prompt_generate_stream.py(신규), docs/{FUNCTION,TASK,REVIEW,MODIFY}.md
- Rollback: 신규 stream GET·헬퍼·프론트 SSE 제거 시 기존 POST 비스트리밍 경로로 복귀(안전). rename 은 alias 로 무중단.

## CHG-20260612-0236
- Date: 2026-06-12 (TASK-0236, **Minor §12.3** — datasource UI 바인딩 변경 후 미갱신 근본수정, frontend-only)
- Scope: TASK-0234 후속 사용자 보고 3건(연결테스트 무의미·DB 목록 datasource 단서 없음/미갱신·primary 미갱신). Playwright 실 헤드리스 브라우저로 재현 후 근본수정. 권한/스키마/엔드포인트/백엔드 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (① `_reloadProductDatasources`/첫-바인딩 PATCH 경로 → `renderProductDetail()` 전체 재렌더, ② `_editDsKey` 선언을 "편집 대상 select" 블록 앞으로 이동[TDZ 해소])
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 `?v=20260612-ds-detail-rerender`)
- 근본 원인: (a) 제품 상세 datasource UI 가 단일 `renderProductDetail()` 시점 클로저 기반인데 바인딩 변경 후 칩만 부분 갱신 → 편집대상 select·배지·DB목록 stale. 바인딩 0↔1↔N 전환 시 select 생성/제거 불가. (b) `length>=2` 편집대상 select 블록이 `_editDsKey` 를 let 선언 전에 참조 → ≥2 바인딩 제품 렌더 시 ReferenceError(TDZ)로 패널 blank(잠복).
- 검증: Playwright 실브라우저 재현→수정→재검증(add/switch 모두 PASS, 콘솔에러 0) + make test 회귀 0.
- Rollback: 위 2파일 revert(frontend-only).
## CHG-20260612-0235v
- Date: 2026-06-12 (TASK-0235 후속 — PB-0008 Windows-browser 시각검증 PASS 기록 + 시나리오 자산 추가)
- Scope: TASK-0235(새 대화 첫 메시지 진행 단계 실시간 표시) 라이브 배포 후 실제 Windows 브라우저 검증 완료 기록. docs + test scenario only — 코드 0.
- 변경:
  - `docs/TEST.md`: §4 2026-06-12 TASK-0235 Run 의 Windows-browser Environment 를 "예정"→**PASS(23/23)** 로 갱신(증거 6 스크린샷 + 단계 실시간 전환·사이드바 동작 실측).
  - `tests/win-browser-task0235-newconv-progress.scenario.json`: 신규 — 새 대화 첫 요청 → pending bubble step 실시간 표시 → "단계 보기" → `#stepSidePanel` 사이드바 검증 시나리오(재현 가능).
- 비변경: app.js / index.html / 백엔드 / 스키마 0. TASK-0235 코드는 이미 PR #172 로 머지·배포됨.
- 검증: PB-0008 시나리오 PASS, healthz 200. CHECK#13 충족.
- Cross-ref: TASK-0235 / CHG-20260612-0234 / REV-20260612-0235v.

## CHG-20260612-0234
- Date: 2026-06-12 (TASK-0235, **Major §12.3** — 새 대화 첫 메시지 작업 단계 진행상황 실시간 표시; 동시세션 insight-reset·prompt-autogen·ds-a11y·ds-label cycle 이 TASK-0231/0232/0233/0234 선점→§13.1 재번호 0232→0235)
- Scope: 채팅 화면 새 대화(lazy_create) 첫 메시지의 진행 단계 폴링 시작 시점 수정. feature-0003(web-ui) **frontend-only** 단독.
- 배경: 사용자 보고 — 새 대화 첫 요청 시 작업 단계가 안 보이고 "시작 중" 만 표시. 진단 결과 step/사이드바 UI(TASK-0061)는 이미 존재하고, **데이터 공급 비대칭**이 근본원인. 기존 대화는 send 직전 `startProgressPolling()` 시작하지만(app.js:5476) 새 대화는 cid 가 `/api/ask` 응답 전까지 없어 폴링을 못 켜고, ask 블로킹 완료 후(run 종료 시점)에야 폴링 시작 → 처리 내내 "시작 중…".
- 변경:
  - `src/static/app.js`: lazy_create 의 early-cid 발급 분기를 **첨부 유무 무관 일반화**(기존 staged 첨부 있을 때만 `/api/new_conversation` 선호출하던 TASK-0106 분기). cid 확정 직후 `state.activeConversationId` 전환 + optimistic conversation entry 선등재 + `startProgressPolling({reset:true})` 즉시 시작. `earlyCidActivated` 플래그로 ask 실패 시 non-lazy 복구 경로(진행 중 run 추적) 분기. early-cid 발급 실패 시 기존 `lazy_create=true` 단일 호출 경로로 graceful fallback. 후처리 블록은 `pendingSentinel===busyKey` 가드로 중복 폴링 자연 차단.
  - `src/static/index.html`: 캐시버스터 `app.js?v=20260611-newconv-progress-steps`.
- 비변경: 백엔드 app.py·PG/웹 스키마·RBAC·엔드포인트·시크릿 0. step/progress 표시·"N단계 보기"→사이드바 UI(`renderPendingAssistantBubble`/`openStepSidePanel`/`#stepSidePanel`) 코드 무변경 — 데이터만 흐르면 자동 동작. `/api/new_conversation`·`/api/progress`·`/api/ask` API 계약 무변경. 병렬 worktree 가 app.py 점유 중이라 의도적으로 app.py 미수정.
- 검증: node --check app.js PASS + verify-completion PASS(9/9). 적대적 동시성 리뷰 REV-20260612-0235 CONCERN 2 흡수. **잔여**: web 재배포 + PB-0008 Windows-browser 시각검증.
- Files: src/static/app.js, src/static/index.html, docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md, docs/reviews/20260612T000000Z-newconv-progress-concurrency.md, ../../docs/STATUS.md
- Rollback: 단일 함수(`sendPrompt`) 내 분기 일반화 + 캐시버스터. 되돌리면 staged 첨부 전용 early-cid 로 복귀(기존 동작). additive 한 state 전환만 추가됨.
- Cross-ref: TASK-0235 / REQ-20260611-0232 / REV-20260612-0235. (TASK-0061 실시간 step UI 후속 — 새 대화 경로 데이터 공급 보완.)
- Date: 2026-06-12 (TASK-0234, **Minor §12.3** — datasource UI 사용성 버그 2건, frontend-only)
- Scope: 멀티 datasource 1:N(TASK-0230) 배포 후 사용자 보고 2건. ① 연결 테스트 버튼이 바인딩 존재 시 무동작(드롭다운 add 모드 value=''), ② 선택 DB 가 어느 datasource 소속인지 불명. 권한/스키마/엔드포인트/백엔드 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (각 datasource 칩 per-chip ⟳ 연결테스트 + "접근 가능 데이터베이스" 헤더 datasource 배지 + 공용 버튼 안내 명확화 + reload 시 편집대상/배지 동기화)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-chip-action--ok/--fail`, `.admin-db-ds-badge`)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 `?v=20260612-ds-test-label`)
- 배경: ① 공용 "연결 테스트" 가 `dsSelect.value` 를 읽는데 TASK-0230 에서 바인딩 ≥1 이면 드롭다운이 "추가" 모드(value='')라 항상 빈 값 → 바인딩 datasource 테스트 불가. 백엔드 `/test` 엔드포인트는 정상(라이브 3/3 ok). ② 멀티 바인딩 시 DB 목록이 어느 datasource 것인지 라벨 없음.
- Rollback: 위 3파일 revert(frontend-only, 백엔드 영향 0).

## CHG-20260611-0233
- Date: 2026-06-11 (TASK-0233, **Minor §12.3** — datasource multi-bind UI 접근성 보강, frontend-only)
- Scope: TASK-0230 의 제품 상세 datasource multi-bind UI 를 gstack `/design-review` 소스 접근성 감사로 검토 후 HIGH 3 + MEDIUM 4 흡수. 권한/스키마/엔드포인트/백엔드 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (★/× 칩버튼 aria-label + disabled 중복요청 가드 + 두 select aria-label + 빈상태 CTA)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (.admin-chip-action/.admin-chip-remove 24px 타깃 + :focus-visible + opacity)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 `?v=20260611-ds-multibind-a11y`)
- Rollback: 위 3파일 revert(frontend-only, 동작 영향 0 — 접근성 속성·CSS 만).
- Date: 2026-06-11 (TASK-0233, **Major §12.3** — 외부 LLM 비용 영향: 제품 프롬프트 "자동 작성" 결과 중간 잘림 해소; 동시세션 insight-reset cycle 이 TASK-0231/CHG-0231 선점→§13.1 재번호 0231→0232)
- 사용자 보고: `관리 콘솔 > 제품 > [각 제품] > 제품 프롬프트 > 자동작성` 텍스트가 글자 수 제한으로 중간 잘림.
- 근본 원인: `admin_generate_product_prompt` 가 출력 토큰 상한을 `max_tokens_for_model(llm_model, "summary")` 로 잡음 — `"summary"` 는 짧은 요약/토픽용 cap(Claude 7000 / 로컬 512). 웹 기본 모델 `claude-haiku-4` 기준 thinking budget(≤5000) 차감 후 실본문 ~2000 토큰 → 본문 잘림. `finish_reason` 미검사로 잘린 채 조용히 반환. 저장 컬럼(MEDIUMTEXT)·프론트 textarea(maxlength 없음)는 제약 아님.
- 변경 (feature-0003 측):
  - `src/app.py`: ① `admin_generate_product_prompt` 의 `max_tokens_for_model(..., "summary")` → `"prompt_gen"`, `timeout` 55→90s. ② LLM 응답 `choices[0].finish_reason == "length"` 검출 → `meta.truncated` 플래그 + `logging.warning`(model·max_tokens·product_id).
  - `src/static/admin.js`: 자동작성 핸들러가 `payload.meta.truncated` 시 metaEl 에 "출력 길이 제한 도달 — 잘렸을 수 있음, 재생성 권장" 경고 append + `.admin-meta-warn` 클래스.
  - `src/static/styles.css`: `.admin-meta.admin-meta-warn { color: var(--warning, #d97706); }` 신설(기존 디자인 토큰).
- 동반 변경 (feature-0002): `src/modules/model_catalog.py` 에 `"prompt_gen"` task cap 신설(Claude 20000 / 로컬 3072). agent-core MODIFY.md CHG-20260611-0233 참조.
- 비변경: RBAC 카탈로그·DB 스키마(`WebSystemPrompts.Content` MEDIUMTEXT 유지)·암호화·신규 엔드포인트·응답 shape(meta 에 `truncated` 키 추가 외) 무변경.
- 검증: agent-core 신규 5(prompt_gen cap 존재·summary 대비 단조성·thinking 차감 여유·로컬 4K 한도·tier 라우팅) + web-ui 신규 4(finish_reason 잘림 검출·meta.truncated 계약) = 9 PASS, model_catalog 기존 회귀 0, node --check admin.js PASS. 시각 동작은 PB-0008(배포 후) 확인.
- Files: src/app.py, src/static/admin.js, src/static/styles.css, tests/test_prompt_generate_truncation.py(신규), docs/{FUNCTION,REVIEW,TASK,MODIFY}.md
- Rollback: 위 3 src 파일 + model_catalog.py revert. cap 조정이라 데이터 마이그레이션 없음.

## CHG-20260611-0231
- Date: 2026-06-11 (TASK-0231, **Critical §12.3** — insight 분석 초기화 (접근 가능 DB 단위 삭제); 동시세션 SSRF·UI-통합·멀티datasource cycle 이 TASK-0228/0229/0230 선점→§13.1 재번호)
- Scope: 관리 콘솔 제품 상세 `접근 가능 데이터베이스 > insight 분석 완료율` per-DB 초기화 기능. 신규 RBAC 권한 + 엔드포인트 + 프런트. feature-0003(web-ui) 단독.
- 배경: 사용자 요청 — insight 분석이 잘못됐을 때 되돌릴 수단이 없었다. DB 단위로 PG insight(fact/rag/fingerprint)를 삭제하면 insight-worker 가 다음 cycle 에 자동 재분석한다.
- 변경:
  - `src/app.py`: ① RBAC `insight.reset`(group console, admin 한정 — `PERMISSION_DEFINITIONS` + `_ensure_seed_roles` admin catchup). ② `_resolve_product_insight_scope`(완료율 계산과 공유하는 datasource scope 해석 헬퍼 추출 + scope alias 집합 반환 — `_compute_product_insight_coverage` 도 이를 호출하도록 리팩터). ③ `_like_escape`/`_insight_reset_ds_heads`/`_insight_reset_fact_key_patterns`/`_insight_reset_kv_key_patterns`(저장 키 체계 정합 LIKE 패턴 — scope alias + live_schemas 기반, ESCAPE '\\'). ④ `POST /api/admin/products/{pid}/insight-reset`(라이브 카탈로그 (schema,table) 교집합으로 rag_objects 삭제 + audit start-event fail-safe + 단일 PG tx 4종 DELETE + complete-event + 완료율 캐시 무효화).
  - `src/static/admin.js`: `resetProductDbInsight`(dry-run 미리보기 → DB명 typed-confirm + 공유 제품 영향 경고 → 실삭제 → 완료율 새로고침) + TASK-0229 통합 DB 리스트(`redrawChips` 의 `cov-db-row`)에 per-DB "초기화" 버튼(`insight.reset` 권한자만).
  - `src/static/styles.css`: `.cov-db-reset` 위험색 버튼 + `cov-db-row` grid 6컬럼.
  - `src/static/admin.html`: 캐시버스터 `?v=20260611-db-coverage-insight-reset`.
- 비변경: PG/웹 스키마·시크릿·암호화·insight write 경로 무변경(read + targeted delete only). 기존 완료율 엔드포인트 동작 보존(_resolve 헬퍼 추출은 동치 리팩터).
- 검증: 신규 `tests/test_insight_reset.py` 14건 PASS + make test 505 passed/2 skipped(회귀 0) + ruff clean + py_compile + node --check + 라이브 PG 키패턴 매칭 실측. outside-voice 적대적 보안 리뷰 MAJOR 3(M1 MSSQL rag_objects 2-tier/M2 scope alias/M3 audit fail-safe) 흡수.
- Files: src/app.py, src/static/{admin.js,admin.html,styles.css}, tests/test_insight_reset.py, docs/{FUNCTION,TASK,REPORT,MODIFY,REVIEW}.md, ../../docs/STATUS.md
- Rollback: 신규 권한/엔드포인트/헬퍼는 additive. 프런트 버튼은 권한 게이트(미보유 시 미노출). 엔드포인트 미호출 시 기존 동작 무영향.
- Cross-ref: TASK-0231 / REQ-20260611-0228 / REV-20260611-0231. (TASK-0223 insight-coverage 후속, TASK-0229 UI-통합·TASK-0230 멀티datasource 위로 rebase.)

## CHG-20260611-0230
- Date: 2026-06-11 (TASK-0230, **Critical §12.3** — 멀티 datasource 1:N: 제품 ↔ 여러 datasource 참조)
- Scope: feature-0003 측 — 관리 평면(join 테이블·admin 엔드포인트·접근DB 차원화·제품 프롬프트 다중 datasource 인지) + UI(제품 상세 datasource 칩 multi-bind·편집 대상 선택기, 대화화면 다중 배지). 단일 바인딩·flag OFF 동작 0 변경.
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (`_ensure_web_product_datasources_schema` join 테이블+차원 마이그레이션 + `_list_product_datasources`/`_product_allowed_schemas_for_datasource` helper + admin GET/POST/DELETE `/products/{id}/datasources` + `_list_products`·`GET /api/admin/datasources`·`PUT databases` datasource 차원 + DELETE datasource 고아 정리 + `admin_generate_product_prompt` 다중 datasource ds-키·접근DB 그룹)
  - unit/feature-0003-agent-web-ui/src/static/admin.js (제품 상세 datasource 칩 multi-bind + 편집 대상 datasource 선택기 + 차원별 productDatabases pending 키)
  - unit/feature-0003-agent-web-ui/src/static/app.js (대화화면 다중 datasource 배지)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-chip--primary`/`.admin-chip-action`)
  - unit/feature-0003-agent-web-ui/src/static/{admin,index}.html (캐시버스터 `?v=20260611-product-multi-ds`)
  - unit/feature-0003-agent-web-ui/tests/test_product_multi_datasource_api.py (신규 7)
- 보안: admin 엔드포인트 console.access(+manage), 미등록 키 거부(400), audit. PUT databases 가 요청 datasource_key 바인딩 검증(임의 키 접근DB 주입 차단). 마이그레이션 loud(REV-0230 MAJOR-1). 런타임 격리는 agent-core `_DatasourceRouter`(CHG-20260611-0230 agent-core) 가 담당.
- Rollback: flag `AGENT_MULTI_DATASOURCE_ENABLED=0` 또는 제품 바인딩 1개 축소 시 기존 단일 경로 복귀. 코드 환원 시 위 파일 revert(join 테이블·차원 컬럼은 멱등 — 잔존해도 무해).
## CHG-20260611-0229
- Date: 2026-06-11 (TASK-0229, **Minor §12.3** — 관리 콘솔 제품 상세 "접근 가능 데이터베이스" UI 통합; 동시세션 SSRF cycle TASK-0228 선점→§13.1 재번호)
- Scope: frontend-only IA 재구성. 제품 상세의 (a) insight 분석 완료율 per-DB breakdown 리스트와 (b) 사용자 등록 DB chip 목록의 1:1 중복을 단일 통합 리스트로 융합 + (c) 시스템/메타데이터 고정 DB 다수 chip을 단일 묶음 칩(hover/focus 툴팁)으로 강등.
- 배경: 사용자 보고 — per-DB 완료율 행과 DB chip이 같은 DB를 두 번 표시(분리 의미 없음) + 시스템 DB 4종(MySQL)/3종(MSSQL)이 각각 chip이라 산만. gstack `/design-review` 메서드론(design subagent)으로 통합 스펙 도출. 데이터 정합 확인: 백엔드 `per_db` 집합 = 사용자 등록 DB(`_list_product_databases`)와 동일, 시스템 DB는 별도 출처(`metadata_schemas`)라 per_db 미포함 → 융합/분리가 데이터 모델과 정합.
- 변경:
  - `src/static/admin.js`: ① `buildProductCoverageDetail` → 요약 헤더+전체 진행 바로 축소(per-DB breakdown 제거). ② `buildDbCoverageCells(covRow, measuring)` 신설(통합 리스트 행의 마이크로바+통계+상태칩). ③ `buildSystemDbChip(lockedChips)` 신설(단일 묶음 칩 + title/aria-label/tabindex + hover·focus·focus-within 툴팁). ④ `redrawChips` 재작성(시스템 칩 + `per_db ↔ schema_name` 소문자 조인한 `cov-db-row` grid 리스트 + 빈 상태). ⑤ chipWrap 클래스 `admin-chip-wrap`→`cov-db-wrap`.
  - `src/static/styles.css`: `.cov-db-wrap`(flex column)/`.cov-db-list`/`.cov-db-row`(grid 5컬럼)/`.cov-microbar`+fill/`.cov-db-stat`/`.cov-db-status*`/`.cov-db-remove`(+spacer)/`.cov-db-list-empty`/`.sysdb-chip`+`-label`/`-tag`/`-tip`+`-title`/`-list` 신설·재구성. 기존 `.cov-db-list/.cov-db-row/.cov-db-name/.cov-db-stat` 정의 교체(단일 사용처). 디자인 토큰만 사용(신규 hex 0).
  - `src/static/admin.html`: 캐시버스터 styles.css·admin.js `?v=20260611-mssql-coverage-perdb`→`?v=20260611-db-coverage-unified`.
- 비변경: RBAC 카탈로그·DB 스키마·암호화·신규 엔드포인트·백엔드(app.py)·`/api/admin/products/insight-coverage` 응답 shape 무변경. 기존 per_db 데이터/draft chip 배열 그대로 사용.
- 검증: node --check admin.js PASS + CSS brace balance(1031/1031) + verify-completion PASS. 시각 동작은 PB-0008(배포 후) 확인.
- Files: src/static/admin.js, src/static/styles.css, src/static/admin.html, docs/{REPORT,REVIEW,TASK,MODIFY}.md
- Rollback: frontend 3파일 revert + 캐시버스터 환원. 백엔드 무관.

## CHG-20260611-0228
- Date: 2026-06-11 (TASK-0228, **Major §12.3** — datasource SSRF 사설망 경계 env 토글 + 의도적 비활성화)
- 사용자 보고: `관리 콘솔 > 데이터소스` 에서 새 데이터소스(host=`10.200.50.80`) 생성 시 "호스트 차단(SSRF): 사설/링크로컬 IP 차단(allowlist 필요): 10.200.50.80" 에러. **근본 원인**: `app._ssrf_check_host` 가 RFC1918 사설 IP 를 SSRF 방어로 차단(설계 의도, TASK-0205/0214). `10.200.50.80` 은 `10.0.0.0/8` 사설 대역이라 차단되며, 정당한 사내 host 는 `AGENT_DATASOURCE_HOST_ALLOWLIST` 에 등재해야 통과하는 구조. 코드 버그 아님 — 사내 운영 환경(대부분 사설망 IP)과 SSRF 방어 기본값의 불일치.
- 사용자 결정: SSRF 방어 구성을 **복원 가능한 형태로 보존(태그)** 하고 **현재는 사설 경계를 의도적으로 비활성화**. (사내 사설망 전면 운영 맥락 — 매 host allowlist 등재 부담 회피.)
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_ssrf_private_guard_enabled()` 신규 — `AGENT_DATASOURCE_SSRF_GUARD_ENABLED` env 파싱(기본 `1`=활성, secure-by-default; `0`/`false`/`no`/`off`=비활성).
    - `_ssrf_check_host()` — 사설/링크로컬/reserved/multicast 차단을 `private_guard` 분기 뒤로 이동. **메타데이터 IP 하드차단·DNS rebinding pin·빈 host 거부는 토글 무관 항상 유지**.
    - `GET /api/admin/datasources` 응답에 `ssrf_private_guard_enabled` 필드 추가(UI 안내 정합).
  - `static/admin.js`: `adminState.datasourcesSsrfPrivateGuard` + 안내 문구 분기(토글 OFF 시 "사설망 IP 허용, 메타데이터는 여전히 차단").
  - `static/admin.html`: admin.js 캐시버스터 `?v=20260611-ssrf-private-guard-toggle`.
  - `docs/DECISIONS.md` ADR-0030 (정본 + 복원 절차) / `docs/SECURITY.md` §11 (토글 정책 + 불변식) / `.env.secret.example` (토글 안내).
  - 신규 테스트 `unit/feature-0003-agent-web-ui/tests/test_ssrf_private_guard_toggle.py` (22 case: 토글 ON/OFF, 메타데이터 항상 차단, allowlist 공존, 파싱).
- 검증: py_compile + node --check PASS. 신규 22 PASS + datasource 회귀 29 PASS(회귀 0). 운영 `.env.secret` 에 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` 설정 + web 재배포는 배포 단계.
- Cross-ref: TASK-0228 / REQ-20260611-0228 / ADR-0030 / SECURITY §11. (TASK-0205/0214 SSRF 가드 후속.)

## CHG-20260611-0223
- Date: 2026-06-11 (TASK-0223, **Major §12.3** — 제품 프롬프트 자동작성 실데이터 정합 + MSSQL database-aware 3계층 인사이트 + ask-worker grounding 검증)
- Scope: 자동 생성 프롬프트가 실제 DB 인사이트에 근거하도록 매칭 로직 재작성(MySQL) + MSSQL database.schema.table 3계층 인사이트 파이프라인 신설(insight-worker 스캔 → fact_key → 엔드포인트/grounding 매칭). feature-0002(agent-core) + feature-0003(web-ui) 교차 변경.
- 배경: ① 자동작성 프롬프트가 없는 테이블(`play_log` 등)을 날조 — `source_type` 컬럼이 전부 `schema_insight`(신뢰불가, 실 종류는 fact_key 접두) + `scope_key`가 전부 `common`(ILIKE 매칭 0건)이라 인사이트 통째 누락. ② MSSQL 3계층 미지원 — insight-worker가 `dbo` 단일 DB만 스캔 + fact_key에 database 누락 → 제품 등록 DB와 매칭 불가.
- 변경:
  - `src/app.py` `admin_generate_product_prompt`: fact_key 접두로 종류 판별 + `regexp_replace`로 ds 접두 정규화 후 제품 접근 스키마/DB명 정확 매칭(boundary, substring 아님). MSSQL 3계층 segment 분기 렌더. datasource 교차노출 차단(제품 `DatasourceKey`→`_generate_datasource_key` scope_key 필터 + 무접두 레거시 허용). LLM 지시문 강화(실 인사이트만·날조 금지). 응답 `meta`(schema_insight_count/table_insight_count/topic_count/grounded). **+ `_log` F821 hotfix**(`_log.getLogger`→`logging.getLogger(__name__)` — TASK-0216 머지본 잠복 NameError).
  - `src/static/admin.js`: "자동 작성" 응답 meta 충실도 표시(grounded 시 스키마/테이블/주제 건수, 미수집 시 안내).
- 비변경: RBAC 카탈로그·시크릿·웹 스키마 무변경. 기존 `product.manage` 권한 재사용. PG 읽기 전용.
- 검증: pytest 444 passed/2 skipped(회귀 0) + py_compile + 라이브 end-to-end(MySQL 킹스레이드 138테이블·MSSQL 제품 60테이블 grounded·교차노출 0·ask-worker grounding 정상).
- Files: src/app.py, src/static/admin.js, (agent-core) modules/{config,insight,utils,schema}.py, agent_core.py, tests/test_mssql_three_tier_insight.py, 양 feature docs
- Rollback: 엔드포인트/헬퍼는 additive. ds_object_suffix가 active_database 미설정 시 2계층(MySQL 동치)이라 MSSQL 미사용 환경 무영향.

## CHG-20260611-0218
- Date: 2026-06-11 (TASK-0218, **Major §12.3** — 관리 콘솔 대시보드 CloudWatch 스타일 재구성)
- Scope: TASK-0210 위젯 그리드를 AWS CloudWatch 류 사람-친화 운영 대시보드로 재구성. gstack `/design-review` + cross-model(Codex+subagent) 디자인 감사(REV-20260611-0218) 반영.
- 변경:
  - `src/app.py` `_dash_widget_*`: ① 시간 위젯에 `days` 윈도우 전파(accounts/audits/conversations — 거짓 컨트롤 정직화). ② 주 metric `primary` 플래그. ③ 시계열 위젯(audits/conversations/usage)에 전기간 대비 `delta_pct`+`delta_sentiment`(neutral/bad) + 일별 `spark` 배열. ④ 위젯에 `tab`(drill-down 대상). 신규 helper `_dash_pct_delta`/`_dash_fill_daily`(UTC gap-fill, ≤60점). `_DASHBOARD_WIDGETS` 카탈로그 활동-우선 재편(conversations/usage/audits 상단). usage 주 metric=추정비용.
  - `src/static/admin.js`: toolbar(`dashboardRefreshBtn` 수동 새로고침 + `dashboardAutoRefresh` off/30/60s + `dashboardUpdated` 마지막 갱신) + `_setDashboardAutoRefresh`/`_updateDashboardMeta`. `buildDataWidgetBody` 주(크게+델타배지+sparkline)/보조(작게) 위계 + Top-N 비율막대(`--bar`). `_dashSparkline`(순수 SVG)·`_dashDeltaBadge`(의미별 색). fail-loud(`_buildDashboardErrorBanner` 전체 + 위젯 단위 재시도, `dashboardError` 상태). drill-down(`dashboard-widget-open`→`switchTab`). native HTML5 drag reorder(`reorderWidgetBefore`)+↑↓ 키보드 폴백. 접근성(card role/aria-label, move/vis/open aria-label, aria-pressed). adminState 필드 추가.
  - `src/static/admin.html`: toolbar 재구성(마지막갱신·기간·auto-refresh·새로고침·편집), `#dashboardWidgets` aria-live, 캐시버스터 `?v=20260611-dashboard-cloudwatch`.
  - `src/static/styles.css`: `.dashboard-primary*`/`.dashboard-secondary`/`.dashboard-delta`/`.dashboard-spark`/`.dashboard-list-row::after`(비율막대)/`.dashboard-error-banner`/`.dashboard-widget-error`/`.dashboard-widget-open`/drag 상태/`:focus-visible` 포커스 링. widget radius `--r-lg`→`--r-md`, 8px 그리드 정돈, 소형 라벨 `--text-muted`→`--text-2`(대비).
  - `tests/test_dashboard_overview.py`: +6(델타·gap-fill·카탈로그 활동-우선·window 전파) = 17.
- 비변경: RBAC 권한 카탈로그·시크릿·DB 스키마(웹·agent_runtime)·신규 엔드포인트 0. overview/preferences 응답 shape 확장(추가 필드)만. 추세/sparkline·window 는 비파괴 read(기존 컬럼/시계열).
- 검증: make test MAKE_EXIT=0(신규 6 포함 전체 PASS, 회귀 0) + node --check + py_compile + (내 코드) ruff 클린. **잔존(내 코드 아님)**: app.py:14133 `_log` F821(동시세션 TASK-0216 머지본 잠복 버그) — flag only.
- Files: unit/feature-0003-agent-web-ui/src/app.py, .../static/{admin.js,admin.html,styles.css}, .../tests/test_dashboard_overview.py, docs/{TASK,MODIFY,REVIEW,REPORT,FUNCTION,TEST}.md, ../../docs/STATUS.md
- Rollback: 추가 필드/helper/toolbar 는 additive. admin.js 대시보드 함수군·styles `.dashboard-*` 를 TASK-0210 버전으로 환원하면 위젯 그리드 v1 로 복귀(백엔드 추가 필드는 무시되어도 무해).

## CHG-20260611-0216
- Date: 2026-06-11 (TASK-0216, **Minor §12.3** — 제품 프롬프트 자동 작성 품질 강화)
- Scope: `POST /api/admin/products/{product_id}/prompt/generate` 엔드포인트 신규 추가 — DB 구조 인사이트(fact_entries 4종) + 사용자 대화 주제 패턴(topic 최신 50개) + 실제 사용 사례 요약(summary 최신 5개)를 LLM 컨텍스트로 구성해 시스템 프롬프트 자동 생성. 관리 콘솔 제품 상세 화면에 "자동 작성" 버튼 추가.
- 배경: 기존 자동 작성 엔드포인트 미존재 — 운영자가 제품 프롬프트를 수동 작성하던 구조. insight-worker가 축적한 팩트(schema_insight/table_insight/search_pref/insight)와 실제 사용자 대화 주제·요약을 활용하면 LLM이 더 정확하고 실무 적합한 프롬프트를 생성 가능.
- 변경:
  - `src/app.py`: `POST /api/admin/products/{product_id}/prompt/generate` 엔드포인트 추가. MySQL에서 제품/DB 스키마 조회, PG에서 fact_entries(4종) + core_conversations.topic(최신 50) + summary(최신 5) 조회 후 knowledge_block 구성 → LLM 호출(model/max_tokens/temperature 동적). 권한: `product.manage`.
  - `src/static/admin.js`: `buildSystemPromptEditor`에 `autoGenerateProductId` 파라미터 + "자동 작성" 버튼 추가(생성 중 disabled). `renderProductDetail`에서 `autoGenerateProductId: Number(product.id)` 전달. 불필요 hint 문자열("이 제품에만 적용됩니다.") 제거.
- 비변경: RBAC 카탈로그·스키마·시크릿 무변경. 기존 `product.manage` 권한 재사용. fact_entries/core_conversations/summary 읽기 전용(쓰기 없음).
- 검증: py_compile PASS + curl 실제 LLM 호출 성공(킹스레이드 product_id=1, 한국어 시스템 프롬프트 정상 생성).
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/admin.js, docs/{TASK,MODIFY,REVIEW}.md
- Rollback: 신규 엔드포인트는 additive — 미사용 시 무영향. admin.js의 버튼 제거 및 엔드포인트 삭제로 원복.

## CHG-20260611-0210
- Date: 2026-06-11 (TASK-0210, **Major §12.3** — 관리 콘솔 대시보드 보강)
- Scope: 빈약한 관리 콘솔 대시보드("운영 현황")를 카테고리별 위젯 그리드 + per-account 커스터마이즈(표시/순서) + 서버 영속으로 재구성. RBAC-스코프 집계 엔드포인트 + 본인 한정 prefs self-service.
- 배경: 기존 대시보드는 계정 metric 6개 + 권한 drift + pending 만 표시했고 전부 클라이언트 `adminState.accounts` 배열을 필터링해 계산(서버 집계 없음 → 계정/데이터 증가 시 비확장). 관리 콘솔 8개 카테고리 중 계정·역할만 일부 노출하고 제품/데이터소스/감사/사용량/대화는 통째 미노출.
- 변경:
  - `src/app.py` `_ensure_web_tables()`: `WebDashboardPreferences(AccountId BIGINT PK, Content MEDIUMTEXT, UpdatedAt, CreatedAt)` 멱등 CREATE 추가(MySQL, 웹테이블군 정합, alembic 무).
  - `src/app.py` `_runtime_tables_available()`: 두 probe 블록(postgres-backend + 기본) table 목록에 `WebDashboardPreferences` 추가 — TASK-0047 패턴. 기존 DB 배포 시 fast-path(`_schedule_memory_runtime_bootstrap`)가 신규 테이블 부재(errno 1146)를 감지해 우회하고 `_ensure_web_tables()` 의 멱등 CREATE 를 1회 실행하게 한다(누락 시 신규 테이블이 영원히 안 생기는 함정 — 라이브 배포 중 포착·수정).
  - `src/app.py` 신규 블록(`# TASK-0210` 배너): 위젯 카탈로그 `_DASHBOARD_WIDGETS`(key/title/permission/source) + `_dashboard_default_prefs`/`_sanitize_dashboard_prefs`/`_load_dashboard_pref_row`/`_save_dashboard_pref_row` + `_dash_widget_{accounts,roles,products,datasources,audits,conversations,usage}` 7종 + `GET /api/admin/overview`(RBAC-스코프, 위젯별 try/except 격리, PG 연결 permitted 시만 open, `days` clamp 후 interval) + `GET/PUT /api/admin/dashboard/preferences`(actor.id self-service, console.access 게이트).
  - `src/static/admin.js`: `renderDashboard` 재작성(overview+prefs fetch → 위젯 그리드) + `loadDashboardOverview`/`_dashboardRenderOrder`/`renderDashboardWidgets`/`buildWidgetCard`/`buildDataWidgetBody`/`buildPendingWidgetBody` + 편집(`setWidgetVisible`/`moveWidget`)·영속(`saveDashboardPrefs`/`resetDashboardPrefs`)·`wireDashboardControls`. adminState 에 overview/dashboardPrefs/dashboardEditMode/dashboardWindow 등 추가.
  - `src/static/admin.html`: 대시보드 pane 을 위젯 그리드(`#dashboardWidgets`) + 집계기간 select(`#dashboardWindow`) + 편집 toolbar/edit-bar 로 교체. 캐시버스터 `?v=20260611-dashboard-widgets`(styles.css·admin.js).
  - `src/static/styles.css`: `.dashboard-toolbar/.dashboard-edit-bar/.dashboard-widgets/.dashboard-widget*/.dashboard-metric*/.dashboard-list-*` 추가(기존 디자인 토큰 재사용).
  - `tests/test_dashboard_overview.py`: 신규 11 테스트(overview RBAC 스코프 operator/admin·403·client 위젯 catalog·sanitize·기본값·영속 round-trip).
- 비변경: 권한(RBAC) 카탈로그·시크릿·웹 외 스키마(agent_runtime 등)·기존 엔드포인트 무변경. 기존 권한(console.access/console.usage.read/audit.read.any) 재사용 + prefs 는 self-service.
- 검증: make test MAKE_EXIT=0 전체 PASS(신규 11, 회귀 0) + node --check admin.js + py_compile + ruff. outside-voice 적대적 보안리뷰 SHIP-ABLE BLOCKER/MAJOR 0(REV-20260611-0210), MINOR 1(PUT 예외 텍스트 노출) 흡수.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}, unit/feature-0003-agent-web-ui/tests/test_dashboard_overview.py, docs/{TASK,MODIFY,REVIEW,REPORT}.md, ../../docs/STATUS.md
- Rollback: 신규 엔드포인트/테이블/위젯은 additive — 미사용 시 무영향. admin.js `renderDashboard` 및 admin.html 대시보드 pane 을 이전 metric-card 버전으로 환원하면 UI 원복(WebDashboardPreferences 테이블은 잔존해도 무해).

## CHG-20260610-0200
- Date: 2026-06-10 (TASK-0200, **Minor §12.3** — 읽기경로 정렬 교정)
- Scope: REV-20260610-0196 이 지적한 MINOR 잔존(수용 항목) 실행 — `_collect_matched_excerpts` 발췌 선택 정렬. (#1 convo_search LIKE escaping 은 feature-0002 CHG-20260610-0200.)
- 배경: conv 별 "가장 최근 매칭 1건" 을 `ROW_NUMBER() OVER (PARTITION BY cid ORDER BY msg_id DESC)` 로 골랐는데, UNION 양변 `agent_runtime.messages.id` / `core_messages.id` 가 독립 IDENTITY 시퀀스라 cross-table id 비교가 chronological 과 어긋날 수 있었다(어느 대화가 매칭되는지엔 무관, 어느 메시지 본문을 스니펫으로 보일지에만 영향).
- 변경 ([src/app.py](../src/app.py) `_collect_matched_excerpts`): UNION 내부 subquery 가 `msg_id` 대신 두 table 공통 `created_at`(PG timestamptz / MySQL CreatedAt·created_at) 을 선택하고 `ROW_NUMBER() OVER (… ORDER BY created_at DESC)` 로 정렬. PG 분기 + MySQL legacy 분기 + docstring 모두 갱신.
- 비변경: 매칭 집합·후처리(line-based 발췌 클리핑)·RBAC·스키마·응답 계약 무변경. ESCAPE/ILIKE 등 기존 로직 유지.
- 검증: `tests/test_cutover_routing_gaps.py` T1 에 `ORDER BY created_at DESC` 존재 + `msg_id` 정렬 부재 단언. make test exit=0. outside-voice [SKIPPED:minor-ordering-implements-REV-0196] (REV-20260610-0200).
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/tests/test_cutover_routing_gaps.py, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: 정렬 키를 `msg_id DESC` 로 환원(기능 무관, 스니펫 선택만 이전 동작).

## CHG-20260610-0197
- Date: 2026-06-10 (TASK-0197, **Minor §12.3** — 프런트 UI 소요시간 표시)
- Scope: assistant 말풍선 타임스탬프 옆 소요시간 표시. `message.meta.duration_ms`(agent_core `mirror_meta` 저장값)가 있는 assistant 메시지에 한해 기존 `formatElapsed()` 재사용, `.message-meta-duration` span 추가.
- 변경:
  - `src/static/app.js` (`renderMessages`): durationMs > 0 일 때 speaker·datetime 텍스트노드 + `<span class="message-meta-duration">N분 M초</span>` 구성. 0이거나 user 메시지면 기존 `textContent` 방식 유지.
  - `src/static/styles.css`: `.message-meta-duration { font-size: 10px; opacity: 0.7; }` 추가.
  - `src/static/index.html`: 캐시버스터 `?v=20260610-response-duration` 갱신(styles.css·app.js).
- 비변경: 백엔드(app.py)·API·DB 스키마·RBAC·시크릿 무변경.
- 검증: node --check app.js PASS. 시각 검증 = Windows-browser(PB-0008) 배포 후.
- Files: unit/feature-0003-agent-web-ui/src/static/{app.js,styles.css,index.html}, docs/{TASK,MODIFY,REVIEW}.md
- Rollback: 본 cycle 커밋 revert — assistant 말풍선에서 소요시간 표시 사라짐.

## CHG-20260610-0196
- Date: 2026-06-10 (TASK-0196, **Minor §12.3** — 백엔드 읽기/쓰기경로 라우팅)
- Scope: AR-M5 cutover 잔존 라우팅 누락 web 3건 복구(대화 제목 변경·관리자 제품 삭제·검색 발췌). TASK-0189 와 동일 결함 class(삭제된 MySQL 테이블을 PG 게이트 없이 조회) 전 서비스 스윕의 web 산물.
- 배경: cutover 로 `AgentCoreConversations`/`AgentMemoryMessages`/`AgentCoreMessages` 등 MySQL 테이블 DROP. 전 코드 스윕(SQL 컨텍스트에서 삭제 테이블을 조회하면서 `AGENT_RUNTIME_READ_BACKEND`/`_pg_connect`/`agent_runtime.` 지표가 함수 내 전무한 함수 추출) + 정적·라이브 검증으로 결함 4건 확정(false positive 제거: KB 게이트 dual-path·caller 라우팅·docstring·information_schema).
- 변경 ([src/app.py](../src/app.py)):
  - `rename_conversation_title`(`PATCH /api/conversations/{id}/title`): raw `UPDATE AgentCoreConversations`(삭제 테이블→**라이브 500**, 재현 확인) → 이미 PG 라우팅된 게이트 헬퍼 `_conv_update_topic(conn, cid, title)`(PG `agent_runtime.core_conversations`) 호출로 교체 + try/except→500.
  - `admin_delete_product`(`DELETE /api/admin/products/{id}`): 참조 가드 `SELECT COUNT(*) FROM AgentCoreConversations WHERE product_id`(→**라이브 500**, 재현 확인) 를 `_runtime_backend_is_pg()` 분기로 PG `agent_runtime.core_conversations` COUNT 라우팅(legacy MySQL else). cursor 는 분기별 자체 정리, 후속 Web* 삭제 autocommit 트랜잭션은 conn 그대로 사용(영향 0).
  - `_collect_matched_excerpts`(검색 발췌): `AgentMemoryMessages UNION AgentCoreMessages`(except→{} 로 스니펫 **항상 빈칸**) → `_runtime_backend_is_pg()` 분기로 PG `agent_runtime.messages` UNION ALL `core_messages`(`ROW_NUMBER() OVER (PARTITION BY cid ORDER BY msg_id DESC)`, `ILIKE … ESCAPE '!'` — MySQL utf8mb4_unicode_ci case-insensitive 패리티) 라우팅. 후처리(line-based 발췌 클리핑)는 DB 무관(rows(cid, content) 동일). legacy MySQL else 보존. params 튜플 양 분기 공유.
- 비변경: RBAC(엔드포인트 기존 게이트 `_account_can_access_conversation`/`_account_has_permission` 유지)·스키마·시크릿·프런트 무변경.
- 검증: 신규 `tests/test_cutover_routing_gaps.py`(T1 excerpts·T2 _conv_update_topic PG 라우팅 + 삭제 테이블 미접촉 가드). make test exit=0. outside-voice REV-20260610-0196.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/tests/test_cutover_routing_gaps.py, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: 본 cycle 커밋 revert — 3 면이 다시 삭제된 MySQL 테이블 조회(rename·제품삭제 500, 발췌 빈칸).
- Cross-ref: convo_search(agent-core) 동일 cutover 복구는 feature-0002 CHG-20260610-0196.

## CHG-20260610-0189
- Date: 2026-06-10 (TASK-0189, **Minor §12.3** — 백엔드 읽기경로 라우팅)
- Scope: 날짜기준표 캘린더의 "대화 구간 이동"(날짜/시각 점프) 기능 복구. AR-M5 cutover 라우팅 누락 수정.
- 배경: 메시지 정본이 MySQL `AgentMemoryMessages` → PG `agent_runtime.messages` 로 cutover 되며 MySQL 테이블이 DROP(AR-M5). 메시지 목록(`_get_history`)·`_load_latest_assistant_message` 는 `AGENT_RUNTIME_READ_BACKEND` 게이트로 PG 라우팅 이전됐으나, 캘린더 backing 2개 엔드포인트(`/api/history_dates`·`/api/history_anchor`)는 이전에서 **누락**돼 삭제된 MySQL 테이블을 직접 조회 → `history_dates` 는 except 폴백으로 항상 `{"dates": {}}`(캘린더에 선택 가능한 날짜 없음 = 기능 누락), `history_anchor` 는 500. 프런트(app.js) 캘린더 로직(`openHistoryCalendarAt`/`renderHistoryCalendar`/`jumpToHistoryAnchor`)은 정상.
- 변경 ([src/app.py](../src/app.py)):
  - `history_anchor`: `AGENT_RUNTIME_READ_BACKEND == "postgres"` 일 때 PG `agent_runtime.messages` 에서 `id, created_at` 을 `to_char(created_at,'YYYY-MM-DD HH24:MI') <= left(%s,16)`(세션 tz wall-clock **분 단위** 문자열 비교) 기준 최신 1건 조회, 없으면 최초 1건 폴백. 반환 `message_id` 는 `_get_history` PG 분기가 DOM 에 부여한 PG id(`message-<id>`)와 동일 id-space → 점프 타겟 매칭. **분 단위 비교 이유**: 프런트 at 은 분 라벨에 `:00` 을 붙인 값(`YYYY-MM-DD HH:MM:00`)이고 실제 created_at 초는 0 이 아니라, 초 단위(`HH24:MI:SS <= ...:00`)면 클릭한 분의 메시지가 제외돼 직전 메시지로 점프하는 결함(원본 MySQL `CreatedAt <= when` 의 잠재 결함)이 생긴다 → 분 단위로 클릭한 분의 (마지막) 메시지에 정확 착지(라이브 검증). legacy MySQL 경로는 else 유지.
  - `history_dates`: 동일 게이트로 `to_char(created_at,'YYYY-MM-DD')` 그룹 + `string_agg(to_char(created_at,'HH24:MI') ORDER BY created_at)` 로 날짜별 시각 라벨 조립(원본 `DATE(CreatedAt)` + `GROUP_CONCAT(DATE_FORMAT(...,'%H:%i'))` 등가). legacy MySQL 경로 else 유지. history_anchor 와 동일 `to_char` 기준이라 라벨·점프 매칭 상호 일관.
  - 두 분기 모두 미사용 `_connect_memory()` conn 을 모든 return 경로(성공·무행·예외)에서 정확히 1회 close.
- 비변경: RBAC(엔드포인트는 기존 `_require_account` + `_resolve_conversation_for_account` 유지)·스키마·시크릿·프런트 무변경. 파괴적 연산 0(읽기 전용).
- 검증: 신규 `tests/test_history_calendar_pg_routing.py`(T1 PG 라우팅+삭제 테이블 미접촉 가드, T2 PG id 반환, T3 legacy back-compat). make test(컨테이너 pytest+ruff) exit=0. outside-voice 적대적 백엔드/QA 검토 REV-20260610-0189 — MAJOR 2건 제기됐으나 라이브 실측으로 무력화(① PG 세션 tz=Asia/Seoul=브라우저 KST → 날짜키 skew 없음, ② core-only 대화 0건 → core-fallback id-space gap 미발생).
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (`history_anchor`·`history_dates` PG 라우팅 분기)
  - unit/feature-0003-agent-web-ui/tests/test_history_calendar_pg_routing.py (신규 회귀 테스트)
  - unit/feature-0003-agent-web-ui/docs/TASK.md, MODIFY.md, REVIEW.md
- Rollback: 본 cycle 커밋 revert — 두 엔드포인트가 다시 MySQL `AgentMemoryMessages` 만 조회(= 캘린더 점프 재차 무력화).

## CHG-20260610-0189-SUGGESTIONS
- Date: 2026-06-10 (TASK-0189 근본원인 형제 인스턴스, **Minor §12.3** — 백엔드 읽기경로 라우팅)
- Scope: `/api/suggestions`(입력 추천: 최근 사용자 프롬프트 목록) — CHG-0189 와 동일 AR-M5 cutover 라우팅 누락으로 라이브 **HTTP 500**.
- 배경: TASK-0189 root-cause("cutover 시 미이전 엔드포인트") 자동 스윕(게이트 없이 `AgentMemoryMessages`/`AgentCoreMessages` 직접 조회 + PG 헬퍼 미사용 라우트 함수 탐지)에서 발견. `suggestions` 는 `SELECT Content FROM AgentMemoryMessages WHERE Role='user' …` 을 try/except 없이 실행 → 삭제된 테이블 조회로 예외 전파 → 500(입력 추천 기능 전면 사망). 라이브 재현 확인(MySQL `AgentMemoryMessages` 부재 + `/api/suggestions` 500).
- 변경 ([src/app.py](../src/app.py) `suggestions`): `AGENT_RUNTIME_READ_BACKEND == "postgres"` 일 때 PG `agent_runtime.messages` 에서 `SELECT content … WHERE role='user' AND conversation_id IN (…) ORDER BY created_at DESC LIMIT %s` 조회. legacy MySQL 경로는 else 보존. 추가로 조회 전체를 try/except 로 감싸 예외 시 빈 `rows`(=빈 items) fail-soft — 함수 기존 계약(`{"items": []}` 으로 degrade)과 정합.
- 비변경: RBAC(`conversation.ask` 게이트 유지)·응답 계약·스키마 무변경.
- 검증: 회귀 테스트 T4(`tests/test_history_calendar_pg_routing.py` — PG 라우팅 + 삭제 테이블 미접촉 가드). make test exit=0. 재배포 후 `/api/suggestions` 라이브 200.
- Files: unit/feature-0003-agent-web-ui/src/app.py (`suggestions` PG 라우팅 + fail-soft), tests/test_history_calendar_pg_routing.py (T4)
- Rollback: 본 변경 revert — `/api/suggestions` 가 다시 삭제된 MySQL 테이블 조회(500).

## CHG-20260610-0188
- Date: 2026-06-10 (TASK-0188, **Minor §12.3** — frontend-static-only)
- Scope: 공유 대화 페이지(`/share/{token}`)의 메시지 본문 markdown 미적용 수정 + 수신자 입장 가독성 디자인 보강.
- 배경: 사용자 보고 — 공유 링크로 전달받은 대화가 markdown 미적용 raw 텍스트(`**`, `|`, `#`, 코드펜스 그대로)로 보임. 근본 원인: 메인 채팅 UI(`app.js markdownToHtml`)는 `vendor/marked.umd.js` + `vendor/purify.min.js`(marked.parse → DOMPurify.sanitize)로 렌더하는데, 공유뷰는 ① `share.html` 이 두 라이브러리를 미로드하고 ② `share.js renderMessage` 가 `content.textContent = msg.content` 로 평문 렌더 → markdown 구문이 문자 그대로 노출.
- 변경:
  - [src/static/share.html](../src/static/share.html): `share.js` 앞에 `vendor/marked.umd.js` + `vendor/purify.min.js` 로드. css/js 링크 캐시버스터 `?v=20260610-share-md`. 헤더에 브랜드 라벨(`.share-brand`) + "링크 복사" 버튼(`#shareCopyLinkBtn`).
  - [src/static/share.js](../src/static/share.js): `renderMessage` 가 `renderMarkdownContent()` 호출 — 메인과 동일 marked+DOMPurify 파이프라인(라이브러리 부재 시 `.share-content-plain` 평문 폴백). ` ```sql ` 코드블록 "쿼리 보기" 토글 이식(`collapseSqlCodeBlocks`), 본문 외부 링크 `target=_blank rel="noopener noreferrer nofollow"`(`markExternalLinks`), 역할 배지(사용자/어시스턴트), `setupCopyLink`(clipboard API + textarea execCommand 폴백).
  - [src/static/share.css](../src/static/share.css): `.share-message-content` 에서 `white-space:pre-wrap` 제거(렌더 HTML) → 폴백 클래스에만 보존. 렌더 markdown 요소 스타일(제목 h1~h4, ul/ol/li, blockquote, 인라인/블록 code, **GFM 표**, hr, img, a, strong/em) + 역할 배지 + 메시지 좌측 accent border + 반응형(≤600px) + 인쇄/PDF 스타일시트(actions/footer 숨김, SQL 토글 펼침, pre 줄바꿈) + `.share-brand`/`.share-copy-link-btn`/`.share-sql-toggle-*`.
- 비변경: 백엔드(app.py)·공유 API(`/api/public/share/*`)·redaction·RBAC·DB 스키마·시크릿 무변경. 익명 페이지 XSS 표면은 메인 앱과 동일한 DOMPurify.sanitize 로 차단(데이터 노출 정책 무변경). node --check share.js PASS. 시각 검증 = Windows-browser(PB-0008) 배포 후.

## CHG-20260610-0186-MDTABLE
- Date: 2026-06-10 (TASK-0186 후속, **Minor §12.3** — frontend-only)
- Scope: CHG-20260610-0186 보강 — 표로 렌더되는 단계 결과 범위를 `execute_sql` 외 **전 도구**로 확장.
- 배경: 0186 은 `result_summary.preview_table`(구조화)이 있는 `execute_sql` 만 표로 렌더했는데, 라이브 `/api/progress` 확인 결과 `get_sample_rows`/`describe_table` 등은 `preview_table` 없이 markdown 표 **문자열**(`preview`)만 가짐 → 여전히 raw `<pre>` 노출(사용자 스크린샷이 바로 `get_sample_rows` raw md).
- 변경 ([src/static/app.js](../src/static/app.js)):
  - `parseMarkdownTablePreview(text)` 신규 — markdown 표 문자열(`| a | b |\n|---|---|\n| 1 | 2 |`)을 `{columns, rows}` 로 파싱(연속 `|` 라인 블록만, 2번째 줄 구분선 검증, 이후 "(N 행)"/"CSV 저장" 등 trailing 무시). 표 아니면 null.
  - `buildStepDetailEl` 결과 우선순위: ① `preview_table` → `buildResultTable` ② `preview` markdown 파싱 → `buildResultTable` ③ raw `<pre>` 폴백(비표형 list_schemas 등). 캐시버스터 `?v=20260610-step-md-table`.
- 비변경: 백엔드/RBAC/스키마/엔드포인트 무변경. XSS: 파싱값은 `buildResultTable` 의 `textContent`. node --check PASS. outside-voice [SKIPPED:frontend-only] (REV-20260610-0187).

## CHG-20260610-0186
- Date: 2026-06-10 (TASK-0186, **Minor §12.3** — frontend-only, web-ui 정적자산만)
- Scope: 실행 단계 사이드 패널(`단계 보기(N)`) ① 결과를 raw 마크다운 텍스트 → HTML 표 렌더링 ② 패널 너비 드래그 리사이즈.
- 배경: TASK-0173 이후 사이드 패널 결과가 `step.result_summary.preview`(markdown 문자열)를 `<pre>` 로 raw 출력 → 가독성 낮음. 단계 데이터엔 이미 구조화된 `preview_table`(columns/rows, `buildSqlStepPanel` 이 쓰는 것과 동일)이 포함돼 있어 백엔드 변경 없이 표로 렌더 가능.
- 변경:
  - [src/static/app.js](../src/static/app.js):
    - `buildStepDetailEl` 결과 블록: `result_summary.preview_table.columns` 가 있으면 기존 `buildResultTable(pt)`(행번호·헤더·hover, `.result-table-wrap` overflow:auto·max-height) 로 표 렌더, 없으면 `preview` 문자열 `<pre>` 폴백(describe 등 비표형 결과 호환).
    - 패널 리사이즈: `setupStepSidePanelResize()`(좌측 핸들 드래그 → 너비 = `innerWidth − clientX`, clamp [300, 92vw], localStorage `web.stepSidePanel.width` 영속, mouse+touch) + `_applyStepSidePanelWidth()` 를 `openStepSidePanel` 에서 호출(저장 너비 복원, 핸들 1회 배선 가드).
  - [src/static/index.html](../src/static/index.html): 패널 첫 자식에 `#stepSidePanelResizer`(role=separator) 추가. 캐시버스터 `?v=20260610-step-panel-table`.
  - [src/static/styles.css](../src/static/styles.css): `.step-side-panel` 에 min/max-width + `.is-resizing`(transition 제거·user-select 차단) + `.step-side-panel-resizer`(ew-resize 핸들, hover/드래그 시 primary 색 표시).
- 비변경: 백엔드(app.py/agent_core)·RBAC·스키마·엔드포인트·시크릿 무변경. `preview_table` 은 이미 `/api/progress` step 데이터에 포함. XSS: `buildResultTable` 은 `textContent` 사용.
- 게이트: node --check app.js PASS. outside-voice [SKIPPED:frontend-only] (REV-20260610-0186). 시각 검증=Windows-browser(PB-0008).

## CHG-20260610-0181
- Date: 2026-06-10
- TASK-Cycle: TASK-0181, **Minor §12.3** — 역할/계정 차트 모델별 stacked + 상세 표 요청(메시지) 수
- Summary: (A) 역할별·계정별 [토큰|비용] 막대를 모델별 누적(stacked)으로 분해(모델 색 일관). (B) 작업 화면 요청 수(distinct run_id) 컬럼 추가. 기존 컬럼 read 집계 확장, RBAC/스키마 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `admin_llm_usage` — totals/by_model 에 `count(distinct run_id)`=requests; by_account fold 에 `models:[{model,total_tokens,cost_usd}]` 보존 + 계정별 requests 별도 쿼리(`count(distinct run_id) WHERE run_id NOT NULL`); `_aggregate_usage_by_role` 가 역할별 `models[]`·`requests` 합산.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: 전역 `modelColor`(등장 모델 전체로 1회 — 일별/도넛/stacked 색 일관) + `mcol()`; renderStacked/renderDonut 가 modelColor 사용; `renderStackedHBar`(역할/계정 토큰·비용 모델별 누적 막대) 신규 + 역할/계정 4 차트 교체; 요약 '요청' 카드; 상세 표(모델/역할/계정) '요청' 컬럼.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260610-usage-stacked`.
- Note: 권한/엔드포인트/스키마/시크릿 신규 0 — read 집계 확장(distinct run_id, 모델 fold). 요청=사용자 메시지(run) 수, 호출=LLM 호출 수로 구분.
- Review: REV-20260610-0181 [SKIPPED:read-agg-no-rbac-no-schema]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260610-0180
- Date: 2026-06-10
- TASK-Cycle: TASK-0180, **Minor §12.3** — 차트 카테고리별 행 레이아웃 + 일별 폭 채움 + 상세 표 여백
- Summary: TASK-0179 의 auto-fill grid(카테고리 무시 몰아넣기)를 명시적 행 구조(4:1 trend / 역할별 토큰|비용 / 계정별 토큰|비용)로 교체 + 일별 차트가 넓은 카드를 폭 채우게(viewBox=clientWidth) + 상세 표 카드화로 여백 해소. 순수 레이아웃.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-usage-charts`/`.admin-usage-span2`(grid) 제거 → `.admin-usage-trend-row`(flex)+`.admin-usage-trend-main`(flex 4, min 420)+`.admin-usage-trend-side`(flex 1, min 240); `.admin-usage-row > card` min 300; `.admin-usage-table-card .admin-usage-table { max-width:none; width:100% }`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 차트를 3행(trend 4:1 / 역할별 토큰·비용 / 계정별 토큰·비용)으로 재배치; details 상세 표를 카드(모델별 full + 역할별|계정별 2열)로. 캐시버스터 `?v=20260610-usage-rows`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: renderStacked 의 viewBox W 를 `el.clientWidth`(폴백 760)로, H 200 고정, 막대 cap 46→64, SVG max-width 제거(카드 폭 채움).
- Note: 권한/엔드포인트/스키마/백엔드 무변경 — 레이아웃/SVG 치수만. 데이터/툴팁/팔레트 동일. clientWidth 측정은 탭 활성 후 렌더 시점(폴백 760).
- Review: REV-20260610-0180 [SKIPPED:css-layout-no-logic]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260610-0179
- Date: 2026-06-10
- TASK-Cycle: TASK-0179, **Minor §12.3** — LLM 사용량 차트 넓은 화면 가로 여백 해소 (CSS grid)
- Summary: 넓은 모니터에서 차트가 좌측만 차지하고 우측 가로 여백이 크던 것을, 차트 6개를 CSS grid 다열 배치로 채움. 순수 레이아웃(CSS/HTML), 동작/데이터 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-usage-charts`(grid auto-fill minmax(400px,1fr)) + `.admin-usage-span2`(grid-column span 2) + 860px↓ 1열 미디어쿼리.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 차트 6개(일별/모델별/역할별/계정별/역할별비용/계정별비용)를 `.admin-usage-charts` grid 의 카드로 재배치, h3/h4 헤더를 각 카드 안으로. 일별 카드 `.admin-usage-span2`. 캐시버스터 `?v=20260610-usage-grid`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: 일별 차트 SVG max-width 780→1000(grid cell span2 폭 채움).
- Note: 권한/엔드포인트/스키마/백엔드 무변경 — 레이아웃만. 차트 데이터/툴팁/팔레트 동일.
- Review: REV-20260610-0179 [SKIPPED:css-layout-no-logic]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260610-0178
- Date: 2026-06-10
- TASK-Cycle: TASK-0178, **Minor §12.3** — LLM 사용량 화면 여백 컴팩트화
- Summary: 사용자 보고(여백 과다). TASK-0177 디자인 카드·섹션·차트 패딩 누적분 축소. 순수 spacing(CSS/SVG), 동작/구조 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-usage-card` padding 16/18→12/14; `.admin-usage-section` margin-top 20→12(first 14→8); `.admin-usage-h3/h4` margin 하향; `.admin-usage-metric` padding 11/14·strong 22→19·span margin-bottom 4; `.admin-usage-row` gap 16→12·min-width 280; usage `.summary-metrics` gap 10·margin-top 0.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: renderStacked SVG H 252→196·pL 64→60·pT 16→10·pB 34→26; renderHBar 막대 div margin 8px→6px.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 styles.css·admin.js `?v=20260610-usage-design`→`?v=20260610-usage-compact`.
- Note: 권한/엔드포인트/스키마/시크릿/백엔드 무변경 — 시각 spacing 만. 차트 데이터/구조 동일.
- Review: REV-20260610-0178 [SKIPPED:css-spacing-no-logic]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260610-0177
- Date: 2026-06-10
- TASK-Cycle: TASK-0177, **Minor §12.3** — LLM 사용량 상세 표 추정 비용 컬럼 + gstack 디자인 관점 정렬
- Summary: (A) 역할별·계정별 상세 표에 추정 비용 컬럼 + 숫자 우측정렬. (B) gstack design-review 관점 subagent 리뷰 후 usage pane 디자인 토큰 정렬(요약 metric-card, 임의 hex→토큰, 차트 surface 카드, spacing/타이포 위계, 표/툴팁 클래스化). 백엔드 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-usage-*` 클래스군 신규(.metric-card 정의 다음) — card/row/section/h3/h4/caption/metric/legend/table(+td.num)/details/empty/tooltip. 기존 :root 토큰(`--surface`/`--border`/`--border-subtle`/`--text*`/`--r-lg`/`--r-sm`/`--shadow-md`) 재사용.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: usage pane 인라인 style 제거 + `.admin-usage-section/card/row/h3/h4/caption/details` 클래스 적용. 차트 각 블록을 surface 카드로 래핑(모델별|역할별, 역할별비용|계정별비용 2-col). 캐시버스터 styles.css·admin.js `?v=20260610-usage-design`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `loadUsage` — 요약을 `.metric-card`/`.summary-metrics`(card 헬퍼)로, tbl 을 `.admin-usage-table` + `align:'right'`(td/th.num), 역할별·계정별 표 cost_usd 컬럼(costFmt) 추가, 툴팁 cssText→`className='admin-usage-tooltip'`, SVG fill 임의 hex→`var(--text*)`/`var(--border*)`(sed 치환), 빈 상태 `.admin-usage-empty`.
- Note: 권한/엔드포인트/스키마/시크릿/백엔드(app.py) 신규 0 — 순수 프론트(표 컬럼 + 디자인). cost_usd 데이터는 TASK-0176 백엔드 산물. 차트 막대 색 팔레트는 카테고리 구분용 의도라 유지.
- Review: REV-20260610-0177 [SKIPPED:frontend-design-no-rbac-no-schema] + general-purpose subagent 의 gstack design-review 관점 리뷰 반영(High 3·Med 4·Low). Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260609-0176
- Date: 2026-06-09
- TASK-Cycle: TASK-0176, **Minor §12.3** — LLM 사용량 역할별·계정별 추정 비용 차트
- Summary: 사용자 요청. 역할별/계정별 토큰 막대 외에 추정 비용 막대 차트 추가. 비용은 모델별 단가라 계정×모델 분해로 집계.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `admin_llm_usage` by_account 쿼리를 `c.owner_account_id` 단일 GROUP BY → `owner_account_id, COALESCE(resolved_model,model)` 분해 + prompt/completion 추가, Python 계정별 fold(`_estimate_llm_cost_usd` 모델별 합 = `cost_usd`). `_aggregate_usage_by_role` 가 by_account 의 `cost_usd` 를 역할 버킷별 재합산(`by_role[].cost_usd`).
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `renderHBar(el, rows, valueFmt)` 에 valueFmt 인자(기본 num, 비용은 usd) — strong·tip 포맷 적용. 역할별/계정별 추정 비용 차트 렌더 호출(`#usageRoleCostChart`/`#usageAccountCostChart`, cost_usd, 0 행 제외). element 선언 2개 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 계정별 차트 다음에 "추정 비용" 섹션(역할별·계정별 2열 #usageRoleCostChart/#usageAccountCostChart) 추가. 캐시버스터 admin.js `?v=20260609-usage-charts2` → `?v=20260609-usage-cost`.
- Note: 권한/엔드포인트/스키마/시크릿 신규 0. 단가는 TASK-0166 의 `_LLM_PRICE_USD_PER_1M` 재사용(claude 근사 추정, 로컬=$0). by_account 가 모델 분해 fold 로 바뀌어도 응답 shape(account_id/calls/total_tokens + enrich username/role)는 동일 + cost_usd 추가.
- Review: REV-20260609-0176 [SKIPPED:frontend-viz-no-rbac-no-schema]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260609-0173
- Date: 2026-06-09 (TASK-0173)
- Scope: 실행 단계(step) "근거(reason)" 사용자 노출 — frontend-only(web-ui 정적자산만).
- 문제: assistant 답변 시 실행 단계의 수행 근거가 화면에 나오지 않아, 사용자가 각 단계가 합리적으로 진행됐는지 확인 불가. 근본은 `reason` 데이터는 end-to-end 정상(LLM tool_notes → `agent_runtime.steps.reason_text` → `/api/progress` 응답)인데 프런트가 과거 "TMI 개선" 결정으로 step 사이드 패널에서 reason 을 `item.title`(hover 툴팁)에만 넣고 `.step-reason { display:none }` 으로 숨김.
- 변경:
  - [src/static/app.js](../src/static/app.js):
    - `buildStepDetailEl`: 숨김 주석 자리를 실제 `.step-reason`(라벨 "근거" pill + 텍스트) DOM 렌더링으로 교체 → step 사이드 패널의 모든 단계가 근거를 표시. compact/non-compact 공통.
    - `_renderStepSidePanelBody`: 인라인 렌더링으로 대체되었으므로 중복 `item.title = step.reason` 제거.
    - `buildSqlStepPanel`: 완료 메시지 상세의 execute_sql 단계 패널 상단에도 동일 `.step-reason` 추가(side panel 과 일관 — non-SQL 단계는 `buildStepBlocks` 가 이미 `work — reason` 표시 중이었음).
  - [src/static/styles.css](../src/static/styles.css): `.step-reason { display:none }` → 가시 secondary 라인(제목 아래 muted, "근거" pill) 스타일로 복원 + `.step-reason-label` / `.step-reason-text`.
  - [src/static/index.html](../src/static/index.html): styles.css·app.js 캐시버스터 `?v=20260609-query-toggle` → `?v=20260609-step-reason`.
- 비변경: 백엔드(app.py/agent_core)·RBAC·스키마·엔드포인트·시크릿 무변경. `reason` 텍스트는 LLM tool_notes 의 명시 user-facing 근거(provider chain-of-thought=`reasoning_content` 와 분리·폐기됨, agent_core.py:2054-2056) 이므로 노출 안전. XSS: `textContent` 사용.
- 게이트: node --check app.js PASS. outside-voice [SKIPPED:frontend-only] (REV-20260609-0173). 시각 검증=Windows-browser(PB-0008) 권장.

## CHG-20260609-0169
- Date: 2026-06-09 (TASK-0169)
- Scope: out-of-process ask-worker 실행모델 — web 측(feature-0003). 짝: feature-0002 CHG-20260609-0169.
- 변경 ([src/app.py](../src/app.py)):
  - `/api/ask`: `asyncio.to_thread(run_agent,…)` 를 `_dispatch_ask_run()` 으로 추상화. `AGENT_ASK_EXECUTION_MODE=inprocess`(기본) 는 현행 to_thread 그대로, `worker` 는 `ask_jobs` enqueue + 내부 `/api/ask_result` long-poll attach(동기 응답 계약 유지). 두 경로 동일 shape 의 agent_result 반환.
  - `_dispatch_ask_run_worker` / `_build_worker_agent_result`: readiness gate(worker heartbeat 신선도 → 부재 시 503), 단일문 slot enforce(`enqueue_ask_job`), run_timeout 까지 attach loop, `ask_jobs.result_json` 으로 응답 shape 패리티(answer/executed_sql/steps/result_csv_paths/rationale/error).
  - backstop ownership-aware(B1): `_reconcile_orphaned_runs_on_startup`(0159)·`_finalize_inflight_runs_on_shutdown`(0164)이 worker mode 에서 활성 `ask_jobs`(pending/running) conversation 을 skip — web 재배포가 worker run 을 오염하지 않음. `_active_ask_job_conversation_ids()` 신설.
  - `/api/cancel`: worker mode 에서 pending `ask_jobs` 도 canceled 로(2g — pending cancel 유실 방지). running 은 기존 KV 플래그 폴링 무변경.
  - 첨부 inline temp(M6): worker mode 는 `_inline_tmp_dir()` 가 `/shared/ask-inline`(web·worker 공통 볼륨) 반환, web 은 cleanup 안 함(worker terminal-only + reaper 소유).
  - BL-1(outside-voice): 403 product-access early-return 의 slot 이중 release 제거(finally 단일 release) — 기존 동시성 카운터 손상 수정.
- 게이트: make test 회귀 0(244 pass), py_compile OK, ruff clean. outside-voice 적대적 리뷰 2회(설계 전 + diff) — BLOCKER 3 + MAJOR 4 흡수.
- flag 기본 inprocess 라 본 배포 자체로는 동작 무변경(shadow). cutover 는 env 전환.
- **라이브 cutover 검증(2026-06-09, main 1320bca→후속 hotfix)**: 마이그레이션 0003 적용(live=0003, agent_kb_rw 권한 OK) → web+ask-worker 배포(healthz git_commit 일치) → `AGENT_ASK_EXECUTION_MODE=worker` 전환. 실측: ① ask enqueue→worker claim(atomic, lease=1)→run→result_json→/api/ask 동기 응답 shape 패리티 PASS, exactly-once(attempts=1). ② **web force-recreate 중 in-flight run 생존**(AC-0327): 동일 run_id·attempts=1·lease=1 로 done 도달, backstop 미오염(last_status=done/last_error 빈값, B1). ③ **hotfix**: `_ask_worker_ready` 가 `_parse_kv_timestamp`(naive UTC) 와 `datetime.now(timezone.utc)`(aware) 를 빼 TypeError→항상 False→readiness 영구 503 이던 tz 버그 라이브 포착·수정(naive 비교). project_task0159 KV tz stale 와 동형 함정.

## CHG-20260609-0167
- Date: 2026-06-09
- TASK-Cycle: TASK-0167, **Minor §12.3** — 관리 콘솔 작은 화면 세로 잘림 수정 (CSS)
- Summary: 사용자 보고(작은 브라우저 화면에서 화면 전체가 안 나오고 잘림). admin-shell/admin-workspace 가 height:100vh+overflow:hidden 인데 usage pane 만 자체 overflow-y 누락 → 차트·표로 길어진 usage pane 하단 잘림. usage pane 에 overflow-y:auto 추가(dashboard 와 동일 패턴).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: dashboard overflow 규칙(`[data-admin-pane="dashboard"].is-active`)에 `,[data-admin-pane="usage"].is-active` 셀렉터 추가 + 사유 주석.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: styles.css 캐시버스터 `?v=20260605-ui-ux-polish` → `?v=20260609-usage-overflow`.
- Note: 권한/엔드포인트/스키마/시크릿/JS/HTML 구조 무변경 — CSS 셀렉터 1개 추가. 다른 pane(accounts/roles/products/audits)은 내부 admin-list 스크롤이라 제외(이중 스크롤 방지).
- Review: REV-20260609-0167 [SKIPPED:css-only-no-rbac-no-schema]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260609-0166
- Date: 2026-06-09
- TASK-Cycle: TASK-0166, **Minor §12.3** — LLM 사용량 차트 고도화 (계정별 차트·hover 툴팁·막대 값·시간단위·추가지표)
- Summary: TASK-0165 후속(사용자 지적: 계정별 차트 부재·추가 지표·hover 상세·막대 정확한 값·시간 기준 선택). 상용 대시보드 수준으로 보강. 의존성 0 순수 SVG 유지.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_LLM_PRICE_USD_PER_1M`(claude 근사 단가)+`_estimate_llm_cost_usd`+`_USAGE_GRAN`(date_trunc 화이트리스트+포맷+상한) 모듈 상수/헬퍼 추가. `admin_llm_usage` — `gran` 파라미터(화이트리스트 검증) + bucket_expr(`to_char(date_trunc('{gran}',...))`); by_model 에 prompt/completion + cost_usd; by_day/by_day_model 을 bucket 집계(by_day_model 은 서브쿼리로 by_day 와 동일 버킷); totals.cost_usd; 응답 `granularity` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `loadUsage` 재작성 — 커스텀 hover 툴팁(`tip`/`bindTip`, data-tip), renderStacked(막대 값 라벨 + data-tip + gran 라벨축약), renderDonut(data-tip 토큰/비중/호출/비용), renderHBar((el,rows[{label,value,tip}]) 일반화), 계정별 차트 렌더, 요약 추정비용 카드, 모델별 표 prompt/completion·비용 컬럼, gran/days URL 파라미터. usageGranSel change 바인딩 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: usage pane 에 `#usageGranSel`(시/일/주/월) + 기간 옵션(1일/1년) + `#usageAccountChart`(계정별 차트) + `#usageTrendTitle`(동적 단위 라벨). 캐시버스터 `?v=20260609-usage-charts` → `?v=20260609-usage-charts2`.
- Note: 권한 `console.usage.read`(admin)/엔드포인트/스키마/시크릿 신규 0. granularity 는 date_trunc 단위 화이트리스트로만 SQL 삽입(인젝션 차단). 비용은 공시가 근사 "추정"(로컬 LLM=$0).
- Review: REV-20260609-0166 [SKIPPED:frontend-viz-no-rbac-no-schema]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260609-0165
- Date: 2026-06-09
- TASK-Cycle: TASK-0165, **Minor §12.3** — LLM 사용량 화면 차트화 (상용 AI 사용량 대시보드 구조 참조)
- Summary: TASK-0163 후속(사용자 요청). 관리 콘솔 > 감사 > LLM 사용량을 표 위주에서 Anthropic Console / OpenAI Usage 류 차트로 시각화. 일별 토큰 모델별 누적 막대 + 모델별 도넛 + 역할별 가로 막대. 의존성 0 순수 SVG(CDN 회피 — 정적자산 baked·WSL 내부). 동시 세션 TASK-0164(SIGTERM) 머지 충돌로 0164→0165 재부여.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `admin_llm_usage` 에 `by_day_model` 집계 추가 — `SELECT date(created_at)::text, COALESCE(resolved_model, model), sum(total_tokens) ... GROUP BY 1,2 ORDER BY 1` (기존 컬럼만, 비파괴 read). 응답에 `by_day_model` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `loadUsage` 에 SVG 차트 헬퍼 3종 추가 — `renderStacked`(일별 stacked 세로 막대 + 날짜축 + 범례), `renderDonut`(모델별 비중 도넛, 실제 서빙 모델 라벨 + % 범례), `renderHBar`(역할별 가로 막대). `colorMapFor`(모델/카테고리 안정 색상, 로컬/시스템=회색). data 수신 후 3 차트 렌더 호출.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: usage pane 에 차트 컨테이너(#usageDayChart, #usageModelChart, #usageRoleChart) 추가 + 기존 모델별/역할별/계정별 표를 `<details>` "상세 표" 로 접이식 보존. 캐시버스터 `?v=20260609-usage-roles` → `?v=20260609-usage-charts`.
- Note: 권한 `console.usage.read`(admin)/엔드포인트/스키마/시크릿 신규 0. by_day_model 은 기존 llm_usage 컬럼만 사용(마이그레이션 불요).
- Review: REV-20260609-0165 [SKIPPED:frontend-viz-no-rbac-no-schema]. Windows-browser(PB-0008) 라이브 screenshot 검증 완료(배포 후).

## CHG-20260609-0164
- Date: 2026-06-09
- TASK-Cycle: TASK-0164, **Major §12.3** — 이월 처리: SIGTERM graceful finalizer(A1) + RBAC 고아 catalog prune(A2) + out-of-process 설계(B, 이월)
- Summary: in-process ask 실행의 orphan-on-redeploy 근본을 종료 시점 finalizer 로 저위험 차단 + RBAC catalog 정합 정리 + 구조적 재설계는 설계 문서로 이월. outside-voice PASS-WITH-NITS(BLOCKER 0).
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_SHUTDOWN_FINALIZE_MESSAGE` 상수 + `@app.on_event("shutdown") _finalize_inflight_runs_on_shutdown`(부팅 reconciliation 대칭 역, race 가드, 8s 소프트캡, 단일 connect) + `_prune_orphaned_permission_catalog(conn)`(고아 WebPermissions 행 가드 DELETE) + `_ensure_seed_roles` 에서 호출 연결.
  - `unit/feature-0003-agent-web-ui/tests/test_shutdown_finalizer.py`: 신규 단위테스트 3(역 boot-guard 선정 / 부팅이전 skip / race 가드).
  - `unit/feature-0003-agent-web-ui/docs/DESIGN-ask-worker.md`: 신규 — out-of-process ask-worker 아키텍처 설계(구현 안 함, B 이월).
  - (무변경 — A3) 빈 attachment 그룹 키는 forward-compatible 유지.

## CHG-20260609-0163
- Date: 2026-06-09
- TASK-Cycle: TASK-0163, **Major §12.3** — LLM 사용량 admin 계정별/역할별 집계 + 모델 해소 표시 (cross-feature, 주관 feature-0002)
- Summary: 관리 콘솔 > 감사 > LLM 사용량에 모델별(claude 포함 실제 모델)·계정별(이름/역할)·역할별 집계를 노출. 토큰 계측 복구·`resolved_model` 마이그레이션·in-process race 수정은 feature-0002 주관. 본 feature 는 엔드포인트 집계/표시 면.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `admin_llm_usage`(GET /api/admin/usage) — by_model `SELECT COALESCE(resolved_model, model) AS m, model, count(*), sum(total_tokens) ... GROUP BY COALESCE(resolved_model,model), model`(별칭+실제 모델 노출); by_account 를 이미 열린 MySQL `conn`(추가 개방 0)으로 `WebAccounts a LEFT JOIN WebRoles r ON r.Id=a.RoleId WHERE a.Id IN (%s,...)`(파라미터화) username·role enrich(실패 시 graceful null); 신규 모듈 헬퍼 `_aggregate_usage_by_role`(account None→`(시스템)`, role None→`(역할 없음)`, total_tokens desc) Python 폴딩; 응답에 `by_role` 추가. 권한 `console.usage.read`(admin) 게이트 무변경.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: usage pane 에 역할별 표(`<h3>역할별</h3><div id="usageByRole">`) 추가; 정적자산 캐시버스터 `?v=20260605-tmi-cleanup` → `?v=20260609-usage-roles`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `loadUsage` — `tbl(rows,cols)` 의 fmt 에 행 전체(r) 전달; 모델별에 `별칭 → 해소모델` 표시; 역할별 표(`#usageByRole`) 렌더; 계정별에 사용자명(`username (#id)`)·역할 컬럼 추가. `esc()` XSS 이스케이프 유지.
- Note: RBAC 카탈로그/엔드포인트/시크릿 신규 0. cross-DB(PG usage + MySQL 역할)는 SQL join 불가라 Python 으로 enrich/fold.
- Review: REV-20260609-0163 (정본 feature-0002) NEEDS-TWEAK→PASS, BLOCKER 1 흡수. **Windows-browser(PB-0008) 라이브 검증은 배포 후 수행.**

## CHG-20260608-0162
- Date: 2026-06-08
- TASK-Cycle: TASK-0162, **Minor §12.3** — 진행중("작업 중") 말풍선 생명주기 수정 (대화 전환 누출 + 새로고침 경과시간 초기화)
- Summary: 사용자 보고 2건 복구. (A) 요청 처리 중 다른 대화로 전환 시 직전 작업의 "작업 중" 말풍선이 전환한 대화에 누출 렌더되던 문제 — `selectConversation` 이 pendingBubble 스냅샷만 저장하고 `state.pendingBubble` 을 비우지 않아 잔존 말풍선이 새 대화에 렌더됨. (B) 새로고침 시 말풍선 경과시간이 0 으로 초기화되던 문제 — 말풍선이 `startedAt: Date.now()` 로 재생성되어 실제 run 시작 시각을 잃음. 서버가 보유한 run 시작 시각(KV `last_status_at`)을 `/api/history` 가 반환하고 프론트가 elapsed 기준점으로 쓰도록 수정.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `history()` 엔드포인트가 `last_status=='processing'` 일 때 `last_run_started_at`(=`load_memory_kv(conn, conv_id, "last_status_at")`)를 응답에 포함. 기존 `_account_can_access_conversation` 권한 게이트 안(`if conv_id:`)에서만 계산 — 신규 노출/IDOR 없음.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: (1) `selectConversation` — 스냅샷 저장 직후 `stopProgressPolling({reset:true})` 로 진행 상태(pendingBubble+polling+elapsed timer) 분리(`beginPendingConversation` 과 동일 패턴; 스냅샷은 reassign-null 이라 보존). (2) `loadHistory` processing 분기 — `startedAt` 을 `payload.last_run_started_at`(서버 run 시작) 파싱값으로, `Number.isFinite` 폴백 `Date.now()`. (3) `initializeWorkspace` resume 분기 — `startedAt` 을 `status.status_at`(ask_status snapshot) 파싱값으로 대칭 수정. (4) `loadHistory` 비-processing(else) 분기 — `_savedPendingBubbles[activeConversationId]` 폐기(stale 말풍선 부활 차단).
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: 정적자산 캐시버스터 `?v=20260608-task-0156` → `?v=20260608-task-0162` (styles.css·app.js 양쪽).
- Note(tz): 클라 elapsed = `new Date(서버ISO).getTime()`(절대 epoch) − `Date.now()`(절대 epoch) → 브라우저 타임존 무관. `last_status_at` 은 `set_run_status` 가 'processing' 전이 시 1회만 기록(agent_core.py:1903)하고 terminal 시점까지 미갱신 → processing 상태에서 run 시작 시각으로 안정적. TASK-0159 의 PG timestamptz naive 변환 회귀와 무관(이 경로는 `_parse_kv_timestamp`/timestamptz 컬럼 미사용).
- Review: REV-20260608-0162 [SUBAGENT 적대적 diff 리뷰] APPROVE-WITH-NITS, BLOCKER 0.

## CHG-20260608-0161
- Date: 2026-06-08
- TASK-Cycle: TASK-0161, **Major §12.3** — RBAC 카탈로그 정리(거짓 컨트롤 권한 제거) + 죽은 코드 제거 (TASK-0158 Tier 3 종결)
- Summary: ① `attachment.execute_sql_on.own/.any` 제거(enforce 미배선 거짓 컨트롤 — 실제 게이트 allowlist+attachment_reader+sql_guard 무변경). ② 죽은 중복 제거(list_conversations HTTP 핸들러·#composerAttachments DOM·#tabCountAudits). ③ `upload.any` 유지+문서화. outside-voice 적대적 RBAC 리뷰 PASS-WITH-NITS(BLOCKER 0).
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `PERMISSION_DEFINITIONS` 에서 `attachment.execute_sql_on.own/.any` 제거(실제 게이트 문서화 주석으로 대체) + operator/sales/admin 시드·catchup 제거 + `_cleanup_deprecated_role_permissions.removals` 2 코드 추가(전 롤 멱등 DELETE) + `upload.any` 의도적 UI 미노출 주석 + `POST /api/list_conversations` 핸들러 제거(내부 `_read_runtime_pg` 무관) + attachment 그룹 주석 갱신.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: execute_sql_on 라벨/설명 map 제거; 죽은 `#composerAttachments`/`Pills` 참조(렌더 hide·catch·pillsContainer 핸들러)·고아 `_toggleAttachmentPill` 제거(`state.composerAttachments`·`_removeAttachmentPill` 은 live 유지).
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: 죽은 `#composerAttachments`/`#composerAttachmentsPills` DOM 제거.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: `#tabCountAudits` stale 뱃지 제거.

## CHG-20260608-0158-V (PB-0008 Windows-browser 검증 기록)
- Date: 2026-06-08
- TASK-Cycle: TASK-0158 — 진입점 구성 Tier1·2 의 실제 Windows 브라우저 완료 게이트 검증 (코드 변경 없음, 테스트 증거만)
- Summary: `bin/win-browser.py`(무권한 relay)로 실제 Windows Chrome 에서 7개 진입점을 시나리오 검증(39/39 PASS). 결과·증거를 TEST.md §4 에 기록하고 재현용 시나리오를 tests 에 추가.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 Test Run History 에 "Environment: Windows-browser" Run 추가(PASS 상세 + 스크린샷 10장 참조).
  - `unit/feature-0003-agent-web-ui/tests/win-browser-task0158.scenario.json`: 재현 가능 win-browser 시나리오 신규(비밀번호 없음 — authed-session 가정).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0158 완료 표시 + PB-0008 게이트 [x].

## CHG-20260608-0159
- Date: 2026-06-08
- TASK-Cycle: TASK-0159, **Major §12.3** — 고아 run 무한 폴링 수정 (런타임 run 생명주기/데이터 경로)
- Summary: 웹 DBA 챗 요청이 무한 "처리중"으로 멈추던 결함 복구. `/api/ask` 는 agent 를 `asyncio.to_thread` 로 web 프로세스 안에서 in-process 실행하므로, web 재배포/재시작이 in-flight run 을 죽이면 `set_run_status("done")` 미도달 → KV `last_status='processing'` 영구 고착 → 프런트엔드 무한 폴링 + 신규 질의 409 차단. 더해 20분 stale 자동복구가 `_last_step_at_for_run` 의 timestamptz(KST aware)→UTC 미변환 회귀(CHG-20260527-0001)로 elapsed 음수가 되어 영구히 안 터졌다. tz 변환 수정 + 부팅 시 고아 reconciliation 으로 재배포 즉시 자동복구를 보장.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: (1) `_last_step_at_for_run` PG 분기 — aware timestamptz 를 `astimezone(timezone.utc).replace(tzinfo=None)` 으로 UTC naive 변환(이미 naive 면 통과). (2) 모듈 레벨 `_PROCESS_BOOT_UTC = datetime.utcnow().replace(microsecond=0)` (부팅 시각, 초 절삭 race 가드). (3) 신규 `@app.on_event("startup")` `_reconcile_orphaned_runs_on_startup` — daemon thread 에서 `last_status='processing'` 중 `last_status_at < _PROCESS_BOOT_UTC` 고아만 `set_run_status(..., "error", ...)` 정리. (4) `set_run_status` import.
  - `unit/feature-0003-agent-web-ui/tests/test_orphan_run_stale_recovery.py`: 신규 6 case (tz 변환·stale 판정·boot-guard).
- Note(즉시 해소, 코드 외): 라이브 PG `agent_runtime.kv` 의 고아 run `20260608053241-f47482aa` 를 `last_status=error` 로 수동 표시. 답변 미합성이라 재질의 필요.
- Note(병행 충돌): 본 cycle 중 다른 세션이 TASK-0158(진입점 Tier1·2, frontend)을 main 에 연속 병합 → 본 작업을 0159 로 재배정. app.py 무충돌(disjoint), docs 만 rebase 재삽입.

## CHG-20260608-0158-T2
- Date: 2026-06-08
- TASK-Cycle: TASK-0158, **Minor §12.3** — 진입점 구성 Tier 2 (관리자/자기서비스, frontend-only)
- Summary: Tier 2 진입점 4종 — audit.purge(파괴적, dry-run+typed-confirm)·내 활동기록 profile 탭·감사 필터 facet 드롭다운·첨부 권한 drift 진단 카드. 신규 RBAC 코드/스키마/시크릿/엔드포인트 무변경(기존 `audit.purge`·`audit.read.*`·`console.access` 권한과 엔드포인트에 UI 진입점만 추가).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: Audits pane 에 `#auditPurgeBtn`(.btn-danger) + resource/actor `<datalist>` + 대시보드 `#dashboardGrantHealth` 카드 컨테이너 신설.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `openAuditPurgeModal`(dry-run 미리보기 + typed-confirm)·`loadAuditFacets`(actors/resources)·`loadGrantHealth`(attachment-grants) 신규 + `renderAuditList` purge 가시성 게이트 + `attachAuditFilterHandlers` purge 바인딩 + `switchTab` audit init facet 로드 + setup grant 로드.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: 프로필 drawer 에 `data-profile-tab="audits"`("내 활동 기록") 탭 + pane(`#profileAuditList`/`#profileAuditMoreBtn`) 신설.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `loadProfileAudits`(cursor 페이지네이션) 신규 + 프로필 탭 hook + `renderProfile` audit 권한 게이트 + more 버튼 바인딩.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.btn-danger`·`.admin-modal-field/-preview/-actions`·`.admin-grant-health`/`.grant-health-*`·`.profile-audit-*` 신설 (기존 토큰만).

## CHG-20260608-0158
- Date: 2026-06-08
- TASK-Cycle: TASK-0158, **Minor §12.3** — "진입점 없는 기능" 전수조사 후 진입점 구성 (Tier 1, frontend-only)
- Summary: 백엔드·로직·RBAC 는 완성됐으나 사용자 진입점이 없던 기능에 UI 길을 추가 (Tier 1: 즉시답변·공유링크관리·scopeAll). 신규 RBAC 코드/스키마/시크릿/엔드포인트 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: composer 에 `#composerFinalizeBtn`("즉시 답변") 신설 + 영구숨김 `#progressCard` 의 고아 `#cancelBtn`/`#finalizeBtn` 제거; attach 사이드패널에 `#composerAttachmentsScopeAll` 체크박스 행 신설.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: 구 cancelBtn/finalizeBtn const·toggle·listener 제거 + `composerFinalizeBtn` 신규 배선(renderComposer busy 분기 노출/권한 + click→finalizeCurrentRun); `openShareManager(cid)` 신규(공유 링크 목록/취소 모달, `GET /api/conversations/{cid}/shares`·`DELETE /api/share/{id}`) + ··· 메뉴 "공유 관리" 항목 + `requiredPermissionsFor` 에 `conversation.read` case 추가; `_loadConversationAttachmentList` 에 scopeAll 체크박스 상태 동기화/표시.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.composer-finalize-btn`, `.share-mgr-*`(모달), `.attach-scope-all*` 스타일 신설 (기존 토큰만 사용).
  - `unit/feature-0003-agent-web-ui/docs/DESIGN-entry-points.md`: design.md 9섹션 형식 신규 작성.

## CHG-20260608-0157
- Date: 2026-06-08
- TASK-Cycle: TASK-0157, **Minor §12.3** — 요청 중단(interrupt) 진입점 복구 (frontend-only)
- Summary: 요청 처리 중 사용자가 실행을 멈출 수 있는 "중단" 버튼이 화면에 노출되지 않던 결함 복구. 근본 원인은 중단(`#cancelBtn`)·즉시 답변(`#finalizeBtn`) 버튼이 커밋 `4ba71f5` 에서 영구 숨김(`style="display:none"`)된 `#progressCard` 안에 고아로 남아 `renderProgress()` 의 `classList.remove("hidden")` 가 인라인 style 우선순위에 가려 무효였기 때문. 백엔드 `/api/cancel` + 에이전트 루프 폴링 + RBAC 는 정상. 사용자 선택(ChatGPT 패턴)에 따라 처리 중 전송 버튼을 "중단" 버튼으로 모핑.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `SEND_BTN_SEND_ICON`/`SEND_BTN_STOP_ICON` 상수 추가; `renderComposer()` 가 `isCurrentConvBusy()` 동안 `#sendBtn` 을 `.is-stop`(stop 아이콘 + `aria-label="중단"`, native disabled 해제) 로 모핑하고 종료 시 전송 버튼 환원 + 중단 권한 access-blocked 반영; `#sendBtn` click 핸들러 busy→`cancelCurrentRun()` / else `sendPrompt()` 분기; hover 전송모드 툴팁을 중단 모드에서 숨김.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.send-btn.is-stop { background: var(--danger) }` + hover `#b91c1c` + `.is-stop.is-access-blocked` muted 규칙.
  - `index.html` 무변경 (영구 숨김 strip 미복원 — 기존 TMI 정리 UX 보존).

## CHG-20260605-0151
- Date: 2026-06-05
- TASK-Cycle: TASK-0151, **Major §12.3** — 첨부 text inline cap 정렬 버그 수정 (DB 조회 UX 개선의 web 면)
- Summary: text 첨부가 count cap(20)을 초과하는 대화에서 가장 오래된 20개만 inline 주입되고 방금 첨부한 최신 파일이 조용히 누락되던 정렬 버그를 수정. 최신 cap개를 보존하도록 DESC 선별 후 표시 순서는 시간순으로 복원.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_prepare_text_inline_attachments` 의 `ORDER BY Id ASC LIMIT %s` → `ORDER BY Id DESC LIMIT %s`, 선별 후 `inline_entries.reverse()` 추가. AccountId IDOR 스코프(`AND AccountId = %s` + per-row 검증) 및 64KB size cap 무변경.

## CHG-20260528-0124
- Date: 2026-05-28
- Related Requirement: TASK-0124 (REQ-20260528-0124, **Minor** §12.3 — 관리 콘솔 RBAC 권한 정합 및 폐기 권한 정리)
- Summary: (1) `sales` 롤에 `conversation.delete.own` 추가 — 대화 생성·실행 권한과 삭제 권한 정합. (2) `conversation.suggestions.read` 폐기 — 항상 `conversation.ask` 종속, 단독 실효성 없는 zombie 권한; suggestions 엔드포인트 게이트를 `conversation.ask` 로 교체. (3) `pending` 롤에서 `conversation.file.read.own` 제거 — 승인 전 조회 전용 롤 의미와 파일 다운로드 혼재 제거. (4) `_cleanup_deprecated_role_permissions(conn)` 신설 — 기존 DB `WebRolePermissions` rows 에서 폐기 권한을 `DELETE` 로 멱등 제거.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `PERMISSION_DEFINITIONS` 에서 `conversation.suggestions.read` 제거; `SEED_ROLE_DEFINITIONS` sales 에 `conversation.delete.own` 추가, operator/sales 에서 `suggestions.read` 제거, pending 에서 `file.read.own` 제거; suggestions 엔드포인트 RBAC 게이트 `conversation.ask` 로 변경; `_legacy_permission_codes_from_row` 에서 `suggestions.read` 제거; `_ensure_seed_roles` catchup_codes 에 `conversation.delete.own` 추가; `_cleanup_deprecated_role_permissions` 신설 및 호출.
  - `docs/STATUS.md`: RBAC 권한 정합 변경 이력 2건 추가 (sales delete.own 추가 + suggestions.read 폐기 + file.read.own from pending 제거).

## CHG-20260528-0125
- Date: 2026-05-28
- Related Requirement: TASK-0125 (REQ-20260528-0125, **Minor** §12.3 — UX 2차 보완 7개 항목 구현; ux-compact-redesign 병합 시 재부여 — 브랜치 원번호 TASK-0123, main TASK-0123/0124 와 ID 충돌하여 다음 feature-0003 시퀀스로 정합)
- Summary: frontend-only UX 보완 7개 항목 일괄 구현. (1) `.composer-box` padding `9px→7px` (입력창 높이 프로필 버튼 48px 일치). (2) `_uploadComposerAttachment()` lazy 분기 재작성: 파일 선택 즉시 `/api/new_conversation` cid 발급 + 업로드 + `lazyConvCreating` 경쟁 방지 플래그. (3) 업로드 응답 `signed_url` bucket 보존 + `_sendAttachmentSnapshot` 포함 + `refreshWorkspace()` 후 lastUserMsg._attachments 재주입. (4) 첨부 chip `has-download` class + click 핸들러 (presigned GET). (5) `share.js` `downloadRowsAsCsv()` helper + SQL 결과표 하단 CSV 버튼. `share.css` `.share-csv-download-btn`. (6) `renderProgress()` `progressCardEl.open=true` + step details `detailsEl.open=true`. (7) lazy-create 성공 path `state.conversations` 최소 항목 추가 + `renderConversationList()`. node --check PASS. backend / RBAC / DB schema / endpoint contract 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: lazy upload 재작성 + signed_url 보존 + lastUserMsg._attachments 재주입 + progressCardEl.open + detailsEl.open + state.conversations 최소 항목
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.composer-box` padding 축소 + `.attach-chip-dl` + `.message-bubble-attach-chip.has-download` hover 효과
  - `unit/feature-0003-agent-web-ui/src/static/share.js`: `downloadRowsAsCsv()` helper + CSV 버튼 삽입
  - `unit/feature-0003-agent-web-ui/src/static/share.css`: `.share-csv-download-btn` 스타일

## CHG-20260528-0123
- Date: 2026-05-28
- Related Requirement: REQ-20260527-0001 (**Major** §12.3 — KB 등록 UI/endpoint 제거)
- Summary: 관리 콘솔 "KB 등록" pane + backend endpoint 2개 + RBAC 권한 1코드 완전 제거. 제거 사유: (1) 대화 첨부(`WebConversationAttachments`) 의존 — 관리 영역이 사용자 대화에 기생하는 설계 결함, (2) Weight=90 manual fact 가 DB 스키마 변경 시 오래된 정보를 자동 수집(Weight=1)보다 우선 참조 → 스키마 오염 위험. `kb_ingest.py` 모듈 + 테스트는 재설계 시 재활용 가능하므로 보존.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: "KB 등록" tab 버튼 + `<section data-admin-pane="kb-ingest">` 전체 제거
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `adminState.kbIngest` state + `mountKbIngestPane` + `loadKbIngestList` + `renderKbIngestList` + `renderKbIngestDetail` + `submitKbIngest` + `KB_INGEST_SCOPE_KEY_RE` + tab 분기 핸들러 (~221 LOC) 제거
  - `unit/feature-0003-agent-web-ui/src/app.py`: `attachment.kb.write.any` PERMISSION_DEFINITIONS 엔트리 + admin seed grant 항목 + `GET /api/admin/attachments` endpoint + `POST /api/admin/attachments/kb-ingest` endpoint + `_KB_INGEST_SCOPE_KEY_RE` (~264 LOC) 제거
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0108 항목에 제거 사유 및 범위 기록

## CHG-20260528-0122
- Date: 2026-05-28
- Related Requirement: TASK-0122 (REQ-20260528-0122, **Minor** §12.3 — 외부 LLM 수신 동의 UI·권한·로직 전면 제거)
- Summary: 사용자 프로필 > 보안 및 계정 탭의 "외부 LLM 송신 동의" 섹션 제거. 서비스 사용 자체를 묵시 동의로 간주. `index.html` DOM 제거 / `app.js` consent 함수·변수·이벤트 바인딩 일체 제거 / `styles.css` consent CSS 블록 제거 / `app.py` `_ensure_web_account_consents_schema` + `_has_active_consent` 함수 제거, `_prepare_vision_inline_images` D11 consent gate + 409 응답 제거 (vision pre-fetch D13 보존, 4-tuple→3-tuple), `/api/account/consents` 3 엔드포인트 제거, `attachment.consent.grant|revoke` audit 핸들러 제거, `_model_to_consent_provider`→`_model_to_llm_provider` rename. py_compile + node --check PASS.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: `profileConsentSection` div 제거
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: consent 함수·변수 9개 제거 + RBAC description 갱신 + 이벤트 바인딩 제거
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: consent CSS 블록 (~43 LOC) 제거
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_ensure_web_account_consents_schema` 제거 + `_has_active_consent` 제거 + consent gate 제거 + 3 엔드포인트 제거 + audit 핸들러 제거 + rename

## CHG-20260526-0108
- Date: 2026-05-26
- Related Requirement: TASK-0108 (REQ-20260526-0108, **Major** §12.3 — Sprint 3 (B: DDL/KB 보강) admin-only manual KB ingest)
- Summary: BRIEFING-attachment-multi-cycle.md §6.3 Sprint 3 Cycle 3 implementation. admin 콘솔 "스키마 정의서 KB 등록" pane 에서 text/markdown/.sql 첨부를 `AgentMemoryFactEntries` 의 manual fact 로 등록. SourceType='manual' 고정, Weight=90 고정 (BRIEFING D 의 0.9 scale ×100, 자동 수집 Weight=1 대비 90× 우선), ConversationId='__kb_manual__' reserved sentinel, FactKey=ScopeKey 자체. 동일 ScopeKey 재ingest 시 기존 active row 는 Weight=0 으로 logical supersede (Status 컬럼 추가 회피, `AgentMemoryFacts` VIEW 의 Weight DESC tie-break 가 자연 hide → 회귀 0). RBAC 1 코드 신설: `attachment.kb.write.any` (admin/dba role catchup). audit `attachment.kb.ingest` dispatch. AGENTS.md §11.3 신설 — manual ingest fact 정책 명문화. **outside-voice review (Codex `codex-cli 0.130.0`, `REV-20260526-0002`) Verdict BLOCK → PASS 전환 (Critical 5 + Nice-to-have 1 본 cycle 내 흡수)**: (B-1) 동시 ingest race → SELECT FOR UPDATE 명시 lock + reactivated 명시 계산 / (B-2) source_type/weight client spoofable → endpoint 가 서버 상수 고정 (request body 입력 무시) / (B-3) admin endpoint 가 `console.access` + `attachment.kb.write.any` 둘 다 require / (B-4) ingest 먼저 commit + audit fail-soft = canonical KB 변경만 + audit 누락 가능 → single transaction + audit 실패 시 rollback / (B-5) scope_key arbitrary string + audit 평문 → regex `^[A-Za-z0-9_.-]{1,96}$` validation + audit ChangeJson 에는 `scope_key_hash_prefix` (SHA256 prefix) 만 + masked_fields=["scope_key", ...]. Nice-to-have: `ON DUPLICATE KEY UPDATE Id = LAST_INSERT_ID(Id)` 로 fact_entry_id 명시 확보.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py` (+~330 LOC): PERMISSION_DEFINITIONS 의 `attachment.kb.write.any` 1 코드 신설 (group="attachment") + SEED admin role grant + dba catchup. 신규 endpoint `GET /api/admin/attachments` (list, RBAC `console.access` AND `attachment.kb.write.any`). 신규 endpoint `POST /api/admin/attachments/kb-ingest` (RBAC + scope_key regex + 1 MB size cap + storage_minio body fetch + UTF-8 decode + kb_ingest.ingest_manual() + audit dispatch, single transaction). `_KB_INGEST_SCOPE_KEY_RE` module-level.
  - `unit/feature-0002-agent-core/src/modules/kb_ingest.py` (신규 ~205 LOC): `KB_MANUAL_CONVERSATION_ID="__kb_manual__"` + `DEFAULT_MANUAL_WEIGHT=90` + `DEFAULT_SOURCE_TYPE="manual"`. `ingest_manual(conn, *, scope_key, body, source_filename, source_sha256, source_type, weight) -> dict` — 4-step: INSERT IGNORE Texts → SELECT FOR UPDATE → UPDATE Id IN (active) → INSERT FactEntries ON DUPLICATE KEY UPDATE Id=LAST_INSERT_ID(Id). 응답 `{fact_entry_id, text_hash, fact_fingerprint, superseded_count, reactivated}`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (+~50 LOC): sidebar "시스템" 그룹에 신규 tab `kb-ingest` + workspace 의 신규 `<section data-admin-pane="kb-ingest">` (pane-head + list-detail layout — 좌 첨부 list, 우 form panel with ScopeKey input + 안내 + submit/cancel). cache-bust `v=20260526-task-0108-kb-ingest`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (+~230 LOC): `adminState.kbIngest` state + `switchTab("kb-ingest")` 분기 + `mountKbIngestPane()` + `loadKbIngestList()` (kind=text,markdown + .sql 별 호출 merge + CreatedAt DESC) + `renderKbIngestList()` + `renderKbIngestDetail()` + `submitKbIngest()` (client regex + source_type/weight 안 보냄). `KB_INGEST_SCOPE_KEY_RE` constant.
  - `unit/feature-0002-agent-core/tests/test_kb_ingest.py` (신규 ~190 LOC): 10 unit test (FakeConn 패턴 — happy path / supersede 3건 / reactivate 동일 본문 / mixed active+inactive 시나리오 / scope_key empty,long / body empty / fingerprint normalization / text_hash determinism / 상수). 10 PASS.
  - `unit/feature-0003-agent-web-ui/tests/test_kb_ingest_rbac.py` (신규 ~165 LOC): 8 e2e RBAC 시나리오 (admin ingest / 동일 ScopeKey reactivate / operator 403 / anonymous 401 / 비-허용 kind 400 / scope_key 누락 400 / 비존재 attachment 404). 운영 turn 에 `make web` 후 실행.
  - `AGENTS.md` (+31 LOC): §11.3 신설 — KB Fact 등록 정책 (Source/SourceType/Weight/ConversationId 4열 테이블 + manual fact supersede 정책 + 책임 분담).
  - `unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`: docs append.
- 검증 (본 cycle):
  - `python3 -m pytest unit/feature-0002-agent-core/tests/test_kb_ingest.py -v` — 10 PASS.
  - `python3 -m py_compile` (변경 4 .py 파일) PASS.
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS.
- Runtime 검증 deferral (사용자 운영 turn 책임):
  - PR 머지 + `docker compose -p repo build memory-init web` + `up -d --force-recreate web` 후 admin 콘솔 → "KB 등록" tab → text/markdown 첨부 1건 ingest → AgentMemoryFactEntries 에 ConversationId='__kb_manual__' Weight=90 row + WebAuditEvents 에 attachment.kb.ingest row 1개 (ChangeJson 의 scope_key_hash_prefix 확인, raw scope_key 미기록).
  - `test_kb_ingest_rbac.py` 8 시나리오 e2e PASS.
- Outside-voice rationale: 호출 ✓ — `REV-20260526-0002` (Codex). RBAC 신규 코드 + admin endpoint + DB mutation = 사용자 메모 `feedback_outside_voice_for_rbac.md` 정합. BLOCK → PASS 전환.

## CHG-20260522-0107
- Date: 2026-05-22
- Related Requirement: TASK-0107 (REQ-20260522-0107, **Major** §12.3 — 첨부 sandbox 활성화 + LLM context inject + drag&drop UX 확장)
- Summary: 사용자 직접 보고 2건 일괄 fix. (1) 파일 첨부 후 LLM 이 "실제 내용을 직접 볼 수 없습니다" 응답 — TASK-0094 sandbox ingest 파이프라인은 정의되어 있었으나 `app.py` upload endpoint 가 `sandbox_ingest.ingest_attachment` 를 호출하지 않아 MetaJson 에 sandbox_table_name 미기록 → ATTACHED FILES section 이 schema 명을 noindict → LLM 의 SQL tool 이 SELECT 시도 안 함. **수정 (3-phase)**: Phase A 활성화 — `app.py` upload endpoint audit dispatch 직후 `threading.Thread(target=_ingest_attachment_background, daemon=True)` spawn (kind=csv|xlsx). 신규 helper 가 storage_minio 로 bytes 받기 → `CREATE SCHEMA IF NOT EXISTS agent_attachment_<sha256(cid)[:32]>` (root user 단일-user MVP — 4-user 분리 grant 는 후속 cycle, .env 비밀번호 미설정) → `_open_memory_connection(database=schema)` → `sandbox_ingest.ingest_attachment` → MetaJson 에 sandbox_schema_name + sandbox_table_name (csv) 또는 sheets[] (xlsx) 기록 + UploadStatus='ingested'. 실패 → `_mark_ingest_failed` 가 'failed' + degraded_reason. `db.py` connect() 에 `agent_attachment_*` schema 패턴 → primary 라우팅 강제 (replica latency / 미배포 환경 안전). Phase B LLM 인지 — `agent_core.py` `_build_attachment_context_section` 강화: information_schema.columns SELECT (column명 + data_type) + `SELECT * FROM <schema>.<table> LIMIT 5` sample rows (markdown 표, 80자 truncate, pipe escape, table cap 20) + 명시 INSTRUCTION ("first try to answer from the sample rows above. If more data is needed, call execute_sql … Do NOT ask the user to paste the file contents"). UploadStatus='uploaded'/'failed' 분기 별 안내. (2) drag&drop 영역 협소 + 새 대화 시 첨부 차단 — composer-wrap 만 drop zone + pendingSentinel 미발급 시 `_uploadComposerAttachment` 가 "대화 컨텍스트 미정" toast 차단. **수정**: index.html 에 chat-pane 자식 `#chatDropOverlay` (점선 카드 + 아이콘) 추가, styles.css 에 `.chat-drop-overlay` (absolute inset 0 + backdrop-filter blur + fade-in 120ms) + `.chat-pane { position: relative }`. app.js `_bindComposerAttachmentEvents` 에 chat-pane scope 핸들러 + `_isFileDrag()` types Files guard + dragCounter 중첩 추적 + window dragend/drop reset (drop miss 방어) + chat-pane 밖 drop 시 브라우저 기본 동작 preventDefault. `_uploadComposerAttachment` 진입 시 컨텍스트 미정 검출 → `conversation.create` 권한 검증 → `pendingNewConversation=true` + `_newPendingSentinel()` + 모든 render 호출 → 기존 lazy-create path 재사용. py_compile + node --check PASS. backend RBAC / DB schema / endpoint contract / D11 consent / D13 server-side bytes 무변경.
- Files:
  - `unit/feature-0002-agent-core/src/modules/db.py`: `connect()` 에 `agent_attachment_*` schema 패턴 매칭 + sandbox 시 replica 라우팅 우회 (primary 강제) — replica latency / 미배포 환경에서도 즉시 SELECT 가능.
  - `unit/feature-0003-agent-web-ui/src/app.py`: upload endpoint (`POST /api/conversations/{cid}/attachments`) 의 audit dispatch 직후 `threading.Thread` 로 `_ingest_attachment_background` spawn (csv|xlsx 한정, fail-open). 신규 helper `_ingest_attachment_background(attachment_id, conversation_id, object_key, kind)`: storage_minio bytes → CREATE SCHEMA + sandbox conn → `sandbox_ingest.ingest_attachment` → MetaJson `sandbox_schema_name` + `sandbox_table_name` 또는 `sheets[]` + UploadStatus='ingested'. 신규 helper `_mark_ingest_failed(attachment_id, reason)`: UploadStatus='failed' + MetaJson `degraded_reason`.
  - `unit/feature-0002-agent-core/src/agent_core.py`: `_build_attachment_context_section` 전면 강화 — metadata + sandbox_table_specs 수집 + `information_schema.columns` SELECT + `SELECT * FROM <schema>.<table> LIMIT 5` sample rows (markdown 표 형식, 80자 cell truncate, pipe escape, table cap 20) + 명시 SQL INSTRUCTION 추가. UploadStatus='uploaded'/'failed' 분기별 안내. ingest 미완 시 fallback 메시지.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: chat-pane 자식으로 `#chatDropOverlay` div (점선 카드 + 아이콘 + "여기에 파일을 놓으세요" 텍스트). cache-bust query `v=20260522-task-0107-attachment` (styles.css + app.js 양쪽).
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.chat-drop-overlay` (absolute inset 0 + flex center + backdrop-filter blur 2px + fade-in animation 120ms) + `.chat-drop-overlay-card` (점선 border + box-shadow + 점선 색 primary) + `.chat-pane { position: relative }` + `@keyframes chat-drop-overlay-fade`.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `_bindComposerAttachmentEvents()` 에 chat-pane scope drag/drop 핸들러 추가 — `_isFileDrag()` (types Files guard), dragCounter (자식 → 부모 bubble 중첩 추적), window dragend/drop reset (drop miss 방어), chat-pane 밖 drop 시 브라우저 기본 동작 preventDefault, multi-file 직렬 업로드. `_uploadComposerAttachment()` 진입 시 컨텍스트 미정 (activeConversationId 없음 + pendingSentinel 없음) 검출 → `conversation.create` 권한 검증 → 자동으로 pendingNewConversation=true + `_newPendingSentinel()` + 모든 render 호출 → 기존 lazy-create path 재사용.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0107 entry 추가 + Current Status 갱신.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: TASK-0107 Summary 추가.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0107 entry 추가.
  - `docs/STATUS.md`: TASK-0107 narrative entry + 표 row 갱신.

## CHG-20260522-0106
- Date: 2026-05-22
- Related Requirement: TASK-0106 (REQ-20260522-0106, **Major** §12.3 — 첨부 storage 모듈 import 경로 + lazy-create 첨부 staging)
- Summary: 사용자 직접 보고 2건 일괄 fix. (1) 웹 첨부 업로드 시 `Error: storage 모듈 import 실패: cannot import name 'storage_minio' from 'modules' (/app/modules/__init__.py)` toast — Dockerfile 이 feature-0002-agent-core 의 unified namespace 만 `/app/modules` 로 copy + feature-0003 의 `storage_minio.py`/`sandbox_schema.py` 는 `/app/web/modules/` 로 copy 하지만 `app.py` 의 `from modules import …` (4 callsite) 가 잘못된 경로. `from web.modules import …` 로 교체. attachment_reconciliation worker 는 docker (`/app/web/modules`) + host dev (sibling sys.path) 양쪽 dual-mode fallback. (2) "+ 새 대화" 클릭 후 첫 메시지 전 첨부 차단 (`isLazy` 조기 toast). lazy-create (TASK-0048) 는 backend cid 발급을 첫 send 까지 지연시키므로 cid 필수의 `/api/conversations/{cid}/attachments` 호출 불가. **Option A — client-side staging**: lazy 분기에서 즉시 차단 대신 pendingSentinel bucket 에 status=`staged` + `_localFile=File` 보관, `sendPrompt()` 의 lazy-create path 가 staged ≥1 감지 시 `/api/new_conversation` 으로 cid 즉시 발급 → `_flushStagedAttachmentsToCid()` 신규 helper 가 staged 일괄 업로드 → askBody 를 `lazy_create=true` → `conversation_id=earlyCid` 로 전환 + `attachment_ids` union. staged 0 인 lazy-create 는 기존 단일 호출 보존 (TASK-0048 정신). pill rendering 에 `data-staged` 속성 + "(첫 메시지와 함께 업로드)" tooltip + staged 토글 = remove. py_compile + node --check PASS. backend / RBAC / DB schema / endpoint contract 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `from modules import storage_minio` 3 callsite (L6044 vision inline, L7555 upload endpoint, L7771 metadata endpoint) → `from web.modules import storage_minio`. `from modules import sandbox_schema` (L11862 grant drift health) → `from web.modules import sandbox_schema`.
  - `unit/feature-0002-agent-core/src/modules/attachment_reconciliation.py`: `_delete_minio_object()` 의 storage_minio import 를 `try: from web.modules import storage_minio` 우선 시도 + ImportError 시 sys.path 삽입 fallback 의 dual-mode 보강 (docker container + host dev 양쪽 환경 호환).
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `_uploadComposerAttachment()` 의 `if (isLazy)` 차단 toast 제거 + pendingSentinel bucket 에 staged item 추가. `_renderAttachmentPills()` 에 `data-staged` 속성 + 조건부 tooltip. `_toggleAttachmentPill()` 에 staged 토글 = remove. `_flushStagedAttachmentsToCid()` 신규 helper. `sendPrompt()` 의 lazy-create attachment_ids 빌드 후 staged ≥1 감지 시 `/api/new_conversation` 발급 + flush + askBody 즉시-cid 모드 전환 + attachment_ids union.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0106 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0106 [SKIPPED:no-rbac-no-schema-no-secret-handling] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0106 entry 추가
  - `docs/STATUS.md`: project-level entry 추가

## CHG-20260522-0008
- Date: 2026-05-22
- Related Requirement: TASK-0105 (REQ-20260522-0008, **Minor** §12.3 — Profile Drawer '내 감사 로그' 탭 일반 사용자 비노출)
- Summary: 사용자 직접 요청 — 일반 사용자에게 Profile Drawer 내 '내 감사 로그' 탭이 노출되어선 안 됨. TASK-0089 에서 추가한 `profileAuditTab` 버튼 + `data-profile-pane="audit"` 패널 + JS 함수 9개 (`_profileAuditEscapeHtml` / `_profileAuditFormatDt` / `_profileAuditHasReadPermission` / `updateProfileAuditTabVisibility` / `_profileAuditReadFilters` / `_profileAuditClearFilters` / `loadProfileAuditList` / `renderProfileAuditList` / `renderProfileAuditDetail` / `attachProfileAuditHandlers`) + `state.profileAudit` 초기값 + `profile-audit-*` CSS 블록 전체를 제거. backend `/api/profile/audits` 및 `/api/profile/audits/{event_id}` endpoint 무변경. admin 콘솔 '감사 로그' 탭 무변경. node --check + py_compile PASS. frontend-only.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: `profileAuditTab` 버튼 제거, `data-profile-pane="audit"` 패널 전체 제거, 주석 갱신 (탭 수 4 → 3)
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `state.profileAudit` 초기값 제거, TASK-0089 `_profileAudit*` 함수 블록 전체 제거, `renderProfile()` 내 `updateProfileAuditTabVisibility()` 호출 제거, 탭 이벤트 핸들러의 audit 분기 제거, `attachProfileAuditHandlers()` 호출 제거
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.profile-audit-*` CSS 블록 전체 제거
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0105 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0008 [SKIPPED:frontend-only] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0105 entry 추가
  - `docs/STATUS.md`: project-level entry 추가

## CHG-20260522-0007
- Date: 2026-05-22
- Related Requirement: TASK-0104 (REQ-20260522-0007, **Major** §12.3 — 외부 노출 web 컨테이너 HTTPS 종단 활성화)
- Summary: 외부 사용자가 `https://112.185.196.20:18080/` 로 접속할 수 없던 이슈 수정. **근본 원인**: `repo/.env` 의 `ENABLE_WEB_TLS=1` + `WEB_TLS_CERT_FILE` / `WEB_TLS_KEY_FILE` 설정과 `docker-compose.yml` 의 TLS 분기 entrypoint 가 있었으나, dev 편의용 `docker-compose.override.yml` (gitignored) 가 entrypoint 자체를 평문 HTTP uvicorn 으로 강제 override. compose 자동 merge 로 base TLS 분기를 덮어써 외부 노출 시나리오에서도 평문만 listening. **수정**: `docker-compose.override.yml` 의 entrypoint 를 `--ssl-keyfile /certs/mysql-ai.company.local/privkey.pem --ssl-certfile /certs/mysql-ai.company.local/fullchain.pem` 포함한 HTTPS 종단으로 교체 (same-port 18080 HTTPS-only — 사용자 결정). `docker-compose.override.yml.example` 에 Variant A (local dev plain HTTP) / Variant B (외부-노출 HTTPS, default) 두 형태 주석 명시. 기존 인증서는 SAN 에 `IP Address:112.185.196.20` 이미 포함되어 재발급 불필요. 호스트 포트 매핑 `${WEB_PORT}:8000` (`18080:8000`) 그대로. backend / RBAC / endpoint contract / DB / Frontend 코드 무변경.
- Files:
  - `docker-compose.override.yml` (gitignored — 운영 인스턴스 직접 적용):
    - `services.web.entrypoint` 를 plain HTTP → HTTPS 종단 (`--ssl-keyfile` + `--ssl-certfile`) 으로 교체
    - 헤더 주석 갱신 — DEV ONLY 표기 → DEV / EXTERNAL-EXPOSED, TASK-0103 / TASK-0104 컨텍스트 명시
  - `docker-compose.override.yml.example` (committed template):
    - 헤더 주석에 사용 시나리오 (A) Local dev / (B) 외부 노출 single-instance / (C) Production with Caddy 3가지 명시
    - `services.web.entrypoint` 에 Variant A (commented out) / Variant B (default) 두 형태 제공
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0104 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0007 [SKIPPED:non-policy-doc] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0104 entry 추가
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0271 (HTTPS 종단 활성화 acceptance) 추가
  - `docs/STATUS.md`: project-level entry 추가

## CHG-20260522-0006
- Date: 2026-05-22
- Related Requirement: TASK-0103 (REQ-20260522-0006, **Major** §12.3 — API Vault secure context 사전 차단 + UX 안내)
- Summary: 외부 사용자가 `http://112.185.196.20:18080/` 로 접속하여 OpenAI API Key 입력 시 모호한 toast 만 출력되며 저장 안 되던 이슈 수정. **근본 원인**: `encryptPlainApiKey()` 가 호출하는 `window.crypto.subtle` 은 secure context (HTTPS / localhost) 에서만 정의됨. 외부 IP 의 HTTP 접속에서는 `undefined` → `Cannot read properties of undefined (reading 'importKey')` 예외 → catch 블록 toast 가 사용자에게 원인을 명확히 전달 안 함. 서버는 `requires_secure_context: True` 를 내려줬으나 클라이언트가 활용 안 함. **수정**: `isVaultCryptoAvailable()` helper + `updateVaultReadiness()` `blocked` 신규 상태 (빨간 banner + 한국어 사유) + `syncVaultSteps()` 가 `cryptoOk = false` 시 모든 step disable + `encryptPlainApiKey()` 진입 시 사전 throw + styles.css `vault-banner[data-state="blocked"]` 빨간 톤. cache-bust `v=20260522-admin-topbar-rbac` → `v=20260522-vault-secure-context`. backend / RBAC / endpoint contract / DB / 암호화 알고리즘 (PBKDF2 + AES-GCM) 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `isVaultCryptoAvailable()` — `window.isSecureContext && window.crypto?.subtle` 체크 helper 추가
    - `updateVaultReadiness()` — `cryptoOk = false` 시 readiness `blocked` 반환 + 한국어 사유 메시지 (`public_url` 이 https 면 보안 주소 표기)
    - `syncVaultSteps()` — `cryptoOk = false` 분기 추가, 모든 step `data-state="disabled"` + saveVaultBtn 차단
    - `encryptPlainApiKey()` — 진입 시점에 `isVaultCryptoAvailable()` 사전 검증, 명시적 한국어 안내 throw
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - `.vault-banner[data-state="blocked"]` + `.vault-banner-dot` 빨간 색상 토큰 추가 (`#ef4444`)
  - `unit/feature-0003-agent-web-ui/src/static/index.html`:
    - cache-bust `v=20260522-admin-topbar-rbac` → `v=20260522-vault-secure-context`
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0103 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0006 [SKIPPED:non-policy-doc] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0103 entry 추가
  - `docs/STATUS.md`: project-level entry 추가

## CHG-20260522-0005
- Date: 2026-05-22
- Related Requirement: TASK-0102 (REQ-20260522-0005, Minor §12.3 — topbar 관리 콘솔 버튼 role fallback gate)
- Summary: 테스트에서 `sales` 역할 사용자에게 topbar 관리 콘솔 버튼이 노출되는 현상 확인. `canOpenAdminConsole()` 에 `role.key` 기반 fallback 추가 — `console_access` 플래그가 서버 응답에 포함된 경우 그것을 사용, 없으면 `role.key === "admin"` 으로 fallback. role 필드는 TASK-0098 이전부터 항상 직렬화되므로 서버 버전 무관하게 존재. backend / RBAC / DB / endpoint 무변경. cache-bust `v=20260522-admin-topbar-rbac`.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `canOpenAdminConsole()` — `console_access !== undefined` 분기 추가, 없으면 `role.key === "admin"` fallback
  - `unit/feature-0003-agent-web-ui/src/static/index.html`:
    - cache-bust `v=20260522-console-access-gate` → `v=20260522-admin-topbar-rbac`
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0102 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0005 [SKIPPED:non-policy-doc] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0102 entry 추가
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0269 추가
  - `docs/STATUS.md`: feature-0003 row 갱신

## CHG-20260522-0004
- Date: 2026-05-22
- Related Requirement: TASK-0100 (REQ-20260522-0004, Minor §12.3 — 관리 콘솔 버튼 RBAC gate 수정)
- Summary: TASK-0098 의 `can()` 단순화(`Boolean(state.user)`)로 인해 `canOpenAdminConsole()` 이 로그인한 모든 사용자에게 `true` 반환 → `관리 콘솔` 버튼이 admin 역할 이외의 사용자에게도 노출되던 이슈 수정. `_serialize_account()` 에 `console_access: bool` 최소 플래그 추가 + `canOpenAdminConsole()` 이 `state.user.console_access` 검사하도록 변경. TASK-0098 의 "permissions 전체 노출 차단" 설계 유지. backend RBAC catalog / DB schema / endpoint contract 무변경. cache-bust `v=20260522-console-access-gate`.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_serialize_account()` — `console_access: _account_has_permission(account, "console.access")` 플래그 추가 (payload 에 항상 포함)
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `canOpenAdminConsole()` — `can("console.access")` → `Boolean(state.user?.console_access)` 로 변경
  - `unit/feature-0003-agent-web-ui/src/static/index.html`:
    - cache-bust `v=20260522-task-0098-perms` → `v=20260522-console-access-gate`
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0100 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0004 [SKIPPED:non-policy-doc] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0100 entry 추가
  - `docs/STATUS.md`: feature-0003 row tail 에 TASK-0100 완료 marker append
- Diff size: app.py +5 lines / app.js +5 lines / index.html 2 replace / docs 5 files
- Impact:
  - admin 역할(`console.access` 보유) 사용자만 `관리 콘솔` 버튼 표시 — 정상 동작 복원
  - 일반 사용자(operator/sales/pending) 는 버튼 미노출
  - `console.access` override grant 된 사용자는 버튼 노출 (RBAC 정합)
  - `_serialize_account()` 호출 모든 경로(로그인 / me / patch / bootstrap) 동일 적용
  - backend API 응답에 `console_access: true/false` 필드 추가 — 클라이언트 호환 변경 (기존 필드 제거 없음)
- Rollback Notes: `_serialize_account()` 의 `console_access` 필드 제거 + `canOpenAdminConsole()` 복원 (`return can("console.access")` 또는 `return Boolean(state.user)`) + index.html cache-bust 원복.

## CHG-20260522-0003
- Date: 2026-05-22
- Related Requirement: TASK-0099 (REQ-20260522-0003, Minor §12.3 — docs-only tracker hygiene)
- Summary: TASK-0073 audit subsystem followup backlog 8 entries (TASK-0086~0093) 8/8 완료 후 정리 cycle. TASK.md 의 stale `[ ]` 체크박스 2건 close: (1) line 152 TASK-0072 (main 통합 `f298f90` + post-deploy hotfix bundle TASK-0074/0075/0076/0077/0078/0079/0080 모두 deployed but 상태 `outside-voice-review` 미갱신), (2) line 2767 TASK-0073 `AGENT_AUDIT_ENABLED=0 + AGENT_MODE=prod` startup fail-closed acceptance (TASK-0092 V1-V3 fail-closed scenario 가 정확히 검증 → close). TASK.md 상단 Task Queue 에 TASK-0099 entry 추가. STATUS.md feature-0003 row tail 에 audit followup backlog 8/8 완료 marker append. docs-only — 코드 / RBAC / 스키마 / endpoint 변경 0.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`:
    - line 152 TASK-0072 `[ ]` → `[x]` + 상태 텍스트 갱신 (deployed commits + hotfix bundle 명시)
    - line 2767 TASK-0073 startup fail-closed acceptance `[ ]` → `[x]` + TASK-0092 7 vector matrix V1-V3 cross-ref
    - 상단 Task Queue 에 TASK-0099 entry 추가 (본 closure cycle)
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0003 [SKIPPED:doc-only-tracker-hygiene]
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0099 cycle entry 추가 + audit followup backlog 8/8 closure marker table
  - `docs/STATUS.md`: feature-0003 row tail 에 audit followup backlog 8/8 완료 marker append
- Diff size: docs-only. TASK.md 3 entry change (2 close + 1 new) + MODIFY/REVIEW/REPORT/STATUS 5 file 갱신. 코드 line change 0.
- Impact:
  - tracker hygiene — TASK.md 의 deployed task 가 정확히 `[x]` 로 close 되어 future cycle 의 audit followup backlog 검색 정확도 향상
  - TASK-0073 audit subsystem 의 7개 acceptance criteria 모두 close — Phase D 의 "deferred to followup cycle" 마지막 항목 (line 2767) 까지 정리 완료
  - 코드 / RBAC / 스키마 / endpoint 변경 없음 → 운영 영향 0
- Rollback Notes: docs-only. 5 file (TASK.md / MODIFY.md / REVIEW.md / REPORT.md / STATUS.md) 의 본 commit revert 로 즉시 복구 가능. 단 `[ ]` 로 돌릴 명분 없음 — 실제 deploy 상태 반영.

## CHG-20260522-0002
- Date: 2026-05-22
- Summary: TASK-0098 (REQ-20260522-0002, **Critical** §12.3 — Profile Drawer 탭 재구성 + 권한 정보 API 단위 차단) cycle ship. PR #49 multi-race rebase + ID reassign + squash commit. Codex outside voice 6 findings (1 blocker + 4 high + 1 medium) 흡수.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: Profile Drawer 탭 5 → 4 (`[프롬프트, 보안 및 계정, API Vault, 내 감사 로그(gated)]`). 보안+계정 통합 pane (활동 정보 최상단 → 비밀번호 변경 → 세션/로그아웃). "권한 현황" DOM 제거. 첫 탭 `is-active` = "프롬프트". cache-bust `v=20260520-profile-audit` → `v=20260522-task-0098-perms`.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `profilePermPillsEl` + `profileStateNoteEl` 변수 제거 + `renderProfile()` 의 호출 + `profileStateNote` 분기 제거. `openProfile(tab = "prompt")` 기본값 + `openProfileBtn` click handler 변경. `can(permission)` 함수를 `Boolean(state.user)` 분기로 단순화 (Codex F5). `apiFetch` 의 403 공통 처리 — toast `"요청을 수행할 수 없습니다."` + Promise reject. `_profileAuditHasReadPermission()` 도 `Boolean(state.user)` 분기. `buildPermissionPills()` 함수 자체는 dead code (호출 없음) 로 남김 — 별 cycle 의 cleanup 위임.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: initialize() 가 `/api/auth/me` → `/api/admin/me` 전환 + `.catch(() => null)` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: cache-bust `v=20260521-settings-listdetail` → `v=20260522-task-0098-perms`.
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_serialize_account(account, *, include_permissions: bool = False)` 시그너처 + default `False`. 7 self callsite 자동 permissions 제거. admin callsite 3 곳 (`_list_accounts_for_admin`, admin account update, 신규 `/api/admin/me`) `include_permissions=True` 명시. 신규 `@app.get("/api/admin/me")` endpoint (console.access 보유자 200, 미보유 403, 비로그인 401). 일반 사용자 경로 403 메시지 5 패턴 9 callsite normalize — 모두 `"요청을 수행할 수 없습니다."` 통일. admin endpoint 의 403 메시지 보존.
  - `unit/feature-0003-agent-web-ui/tests/test_admin_me_rbac.py`: 신규 4 시나리오.
  - `unit/feature-0003-agent-web-ui/tests/test_auth_me_rbac.py`: 신규 5 시나리오.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: REQ-20260522-0002 + AC-0226~0234 9 항목 신규.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0098 queue entry + PLAN-APPROVED marker.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0002 [AGENT-TEAM:codex-outside-voice].
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 갱신.
  - `docs/STATUS.md`: feature-0003 row prepend.
- 검증: py_compile + node --check + verify-completion --pre-commit PASS. 실 컨테이너 9 시나리오 smoke + UI dogfood 2 role 사용자 위임.
- Codex 6 findings 흡수 매핑: F1 (admin.js console.access blocker) → `/api/admin/me` 분리 / F2 (Option Y raw permission 비노출) → can() 단순화 + apiFetch 403 fallback + 메시지 normalize / F3 (403 메시지 권한명 노출) → 5 패턴 9 callsite normalize / F4 (누출 경로 다수) → default False 일괄 적용 / F5 (false 단순 전환 금지) → can() true 반환 + UI 표시 유지 / F6 (CSRF/race) → 현 backend SameSite + fresh permission 검사 안전.
- Multi-race rebase 영역: backup branch `backup/profile-tabs-restructure-pre-rebase` (677d48a tip) 에 원래 4 commit 보존. main HEAD `20f0344` 위에 squash commit. main 흡수 = PR #45 v3.10.0 + #47 TASK-0089 audit drawer + #48/#50 docs + #52 TASK-0094 첨부 multi-cycle Sprint 1 Phase 1 + #61 Phase 4 storage + DQA 브랜딩 (TASK-0097) + TASK-0095 GLOBAL prompt + TASK-0096 v2 (설정 list-detail). 의도 통합 = Profile Drawer 5 탭 → 4 탭 (audit 보존 + 3 탭 통합). ID reassign = TASK-0094→TASK-0098 / REQ-20260521-0001→REQ-20260522-0002 / AC-0199~0207→AC-0226~0234 / CHG·REV-20260521-0001~0004→CHG·REV-20260522-0002 / cache-bust `v=20260522-task-0098-perms`.

## CHG-20260521-0006
- Date: 2026-05-21
- Summary: TASK-0096 v2 (REQ-20260521-0004 follow-up). 사용자 직접 피드백 — "계정, 역할, 제품 탭과 일관된 디자인이 아닌것으로 확인되었습니다. 검색창을 포함하여, 해당 탭들과 일관된 디자인으로 구성해주세요." CHG-20260521-0005 의 sub-sidebar (`admin-settings-shell` + `admin-settings-nav`) 형태가 다른 탭의 5단 master-detail 패턴 (header → `admin-list-detail` (좌측 list-col + 우측 detail-col)) 과 시각 일관성 부족. v2 에서 sub-sidebar 전용 클래스 일괄 제거 + 계정/역할/제품 의 `admin-list-detail` / `admin-list-col` / `admin-detail-col` 그대로 차용 + `admin-list-row` 의 nav 변형 (`.admin-list-row--nav`, 체크박스 슬롯 hidden, full-width content) 추가. 검색창 = `admin-search` 재사용 (placeholder = "설정 항목 검색…"), 항목 카운트 = `admin-list-count` 재사용. 검색 필터는 row 의 `data-settings-tab` + `data-settings-group` + `data-settings-keywords` + textContent 를 합쳐 substring 매칭. UI restructure only — 데이터/API/권한 무영향.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`:
    - `admin-settings-shell` + `admin-settings-nav` + `admin-settings-content` 구조 → 표준 `admin-list-detail` (`admin-list-col` (toolbar+search+`admin-list-head`+`admin-list`) + `admin-detail-col` (panel)) 로 교체. `admin-pane-hint` 단락 제거 (다른 탭과 일관 — pane-head 직접에 hint 없음).
    - 신규 hook id = `settingsSearch` (`admin-search`), `settingsListCount` (`admin-list-count`), `settingsList` (`admin-list`), `settingsDetail` (`admin-detail-col`). 기존 `globalPromptEditorMount` 보존.
    - 첫 항목은 `<button class="admin-list-row admin-list-row--nav is-active" role="option" aria-selected="true" data-settings-tab="global-prompt" data-settings-group="시스템 프롬프트" data-settings-keywords="...">`. row 본문은 `admin-list-row-cb` (visual hidden) + `admin-list-row-main` (`admin-list-row-title` + `admin-list-row-meta` 2줄).
    - section label = `admin-list-section-label` (UPPERCASE, head row 안). 차후 항목 추가 시 새 section label + row 묶음을 등재.
    - cache-buster `v=20260521-settings-subnav` → `v=20260521-settings-listdetail`.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - sub-sidebar 전용 셀렉터 (`.admin-settings-shell`, `.admin-settings-nav`, `.admin-settings-nav-group-label`, `.admin-settings-nav-item[.is-active]`, `.admin-settings-nav-label`, `.admin-settings-nav-hint`, `.admin-settings-content`) + 760px responsive 블록 일괄 제거. 함께 `.admin-pane-hint` 도 제거 (markup 에서도 미사용).
    - 신규: `.admin-list-section-label` (UPPERCASE 11px, head row 안). `.admin-list-row.admin-list-row--nav` 변형 (grid 1fr, button 전용 reset, cb 슬롯 hidden, meta 본문 영구 노출). `.admin-settings-panel`/-`head h3`/-`hint`/-`body` 본문 스타일은 유지하되 자체 border 제거 (`admin-detail-col` 의 surface 가 이미 border 책임).
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `mountSettingsSections()` 가 `bindSettingsList()` + `bindSettingsSearch()` + `updateSettingsListCount()` + `activateSettingsPanel(activeTab)` 호출. `bindSettingsNav()` 는 v1 의 `adminSettingsNav` 셀렉터 의존이라 제거.
    - `bindSettingsList()` — `#settingsList` 에 위임 click. row `[data-settings-tab]` 매칭.
    - `bindSettingsSearch()` — `#settingsSearch` 에 `input` 이벤트 → `applySettingsSearchFilter(value)`.
    - `applySettingsSearchFilter(query)` — 모든 row 에 대해 합친 haystack (`data-settings-tab` + `data-settings-group` + `data-settings-keywords` + textContent) lower-case substring 매칭, 비매칭 row 는 `display:none`.
    - `updateSettingsListCount()` — 가시 row 수 / 전체 row 수 형식 ("1건" 또는 "1 / 2건").
    - `activateSettingsPanel(tab)` — `#settingsList` + `#settingsDetail` 셀렉터로 갱신, `aria-selected` 동기화 추가. mount lazy 로직은 동일.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0210 갱신 — list-detail 패턴 + 검색 hook 표기.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0096 entry + Last Updated 갱신 (v2 흡수).
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260521-0006.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary follow-up note.
- Verification:
  - 정적 검사 N/A (frontend only).
  - 사후 검증: web 컨테이너 재배포 → `/browse` 로 설정 탭 진입 → header (Settings 라벨 + 제목) + 좌측 list-col (검색창 + section-label `시스템 프롬프트` + nav row `전역 시스템 프롬프트`) + 우측 detail-col (panel head + textarea body) 노출 확인 + 검색창에 "전역" 입력 시 row 1건 표시 / "missing" 입력 시 0 / 1 표시 + 콘솔 errors 없음.
- Risks:
  - row 의 hidden 처리는 `style.display = "none"` 인라인. screen reader 가 카운트 mismatch 가능 — 향후 `aria-hidden` 동기화 보강 후보 (현 build 는 카운트 라이브 영역으로 충분).
  - `admin-list-row--nav` 가 다른 탭의 row hover/active 스타일 (`admin-list-row.is-active` 의 primary-soft) 을 그대로 상속 — 시각 정합 OK 이며 권한 grid 처럼 추가 컬러 token 불필요.
- Trace: REQ-20260521-0004 → TASK-0096 → CHG-20260521-0006 → REV-20260521-0006 (CHG-20260521-0005 follow-up redesign).

## CHG-20260521-0005
- Date: 2026-05-21
- Summary: TASK-0096 (REQ-20260521-0004, **Minor** §12.3 — `설정` pane sub-sidebar + panel 확장 패턴). 사용자 직접 요청 — TASK-0095 검증 완료 후속, "`설정` 탭 내부 화면을 `계정`, `역할`, `제품` 과 같이 패널을 분리해줄 수 있을까요? 차후 `전역 시스템 프롬프트` 항목 외에도 설정 내 많은 항목이 추가될 예정인데 현재는 확장성이 너무 좁게 구현되어 있습니다." 단일 sub-section 누적 구조 → 좌측 sub-sidebar (항목 nav) + 우측 panel 의 2-column grid 확장 패턴으로 전환. 새 항목 추가 절차 = `<button data-settings-tab="X">` + `<article data-settings-panel="X">` + `SETTINGS_PANEL_MOUNTERS["X"] = mountFn` 3 단계. mount 함수는 panel 첫 활성화 시 1회 실행 (lazy mount, `adminState.settings.mountedPanels` Set). UI restructure only — 데이터/API/권한 무영향.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`:
    - `admin-settings-list` / `admin-settings-section` (TASK-0095 단일 누적 구조) → `admin-settings-shell` (grid 240px + 1fr) + `admin-settings-nav` (sub-sidebar) + `admin-settings-content` (panel 컨테이너) 로 교체.
    - 첫 nav item = `data-settings-tab="global-prompt"` (is-active), 첫 panel = `data-settings-panel="global-prompt"` (is-active). nav 안에 그룹 라벨 (`시스템 프롬프트`) + label/hint 2-line 구조.
    - 신규 hook id = `adminSettingsNav`, `adminSettingsContent`. 기존 `globalPromptEditorMount` 는 panel body 안으로 이동 (변경 없음, 셀렉터 호환).
    - cache-buster `v=20260521-settings-tab` → `v=20260521-settings-subnav`.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - `.admin-settings-list` / `.admin-settings-section` (TASK-0095) 셀렉터 제거 (markup 에서 사용 안 됨).
    - `.admin-settings-shell` (grid 240px / 1fr), `.admin-settings-nav` (sticky, border-right), `.admin-settings-nav-group-label` (uppercase 11px), `.admin-settings-nav-item` (vertical flex + label/hint), `.admin-settings-nav-item.is-active` (소프트 surface 강조), `.admin-settings-content` (left padding 20), `.admin-settings-panel` (default `display:none`) + `.is-active` (`display:flex`), `.admin-settings-panel-head/-hint/-body` 스타일 추가.
    - `@media (max-width: 760px)` — sub-sidebar 가 가로 wrap 으로 collapse, content 가 그 아래로 stack.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `adminState.settings` 에 `activeTab` (default `"global-prompt"`) + `mountedPanels` (Set) 추가.
    - `SETTINGS_PANEL_MOUNTERS` 객체 신설 — key=tab id, value=mount 함수. 차후 항목 추가 시 본 객체 한 줄 등록만으로 확장.
    - `mountSettingsSections()` 가 `bindSettingsNav()` + `activateSettingsPanel(activeTab)` 호출하는 형태로 재정의.
    - `bindSettingsNav()` — 1회 위임 click 핸들러 (`data-settings-tab` 매칭).
    - `activateSettingsPanel(tab)` — nav/panel `.is-active` toggle + 첫 활성화 시 mount 함수 1회 실행 + `mountedPanels` 기록.
    - `mountGlobalPromptPanel()` — TASK-0095 의 인라인 글로벌 프롬프트 마운트 로직을 단독 함수로 추출. 권한 게이트 + read-only disabled 처리 동일.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0210 신설 (sub-sidebar + panel 패턴 정의).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0096 entry + Last Updated 갱신.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260521-0005.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary follow-up note.
- Verification:
  - py_compile / 정적 검사 N/A — 본 cycle 은 frontend 만 변경 (HTML/CSS/JS).
  - 사후 검증: web 컨테이너 재배포 → `/static/admin.html` 응답에 `admin-settings-shell` / `admin-settings-nav-item[data-settings-tab="global-prompt"]` markup 노출 확인 + `/browse` 로 좌측 sub-sidebar 노출 + 활성 panel 의 textarea 본문 노출 확인 + 권한 grid 회귀 없음 확인.
- Risks:
  - 차후 항목 추가 시 mount 함수가 panel 첫 활성화 후에만 작동하므로, 첫 진입 항목에서 다른 탭 데이터 의존 시 명시적 prefetch 필요. 본 cycle 의 `global-prompt` 단일 항목은 자기 충족.
  - `bindSettingsNav` 의 `dataset.bound = "1"` 가드로 중복 핸들러 부착 방지. 다른 admin tab 패턴과 동형.
- Trace: REQ-20260521-0004 → TASK-0096 → CHG-20260521-0005 → REV-20260521-0005.

## CHG-20260521-0004
- Date: 2026-05-21
- Summary: TASK-0095 follow-up hot-fix — fast-path catchup (`_ensure_seed_catchup`) 에 `_ensure_seed_global_system_prompt(conn)` 호출 누락을 보정. CHG-20260521-0003 이 slow path (`_ensure_web_tables`) 에만 helper 를 배치했지만, 기존 배포는 fast path 만 타기 때문에 GLOBAL scope row 가 자동 seed 되지 않았다. live deploy 후 DB 검증으로 발견 — `WebSystemPrompts WHERE Scope='global'` 0 row, 모든 응답이 코드 상수 fallback 만 작동. 관리 콘솔 `설정` 탭의 textarea 가 빈 채로 노출되어 운영자가 매번 직접 base prompt 를 입력해야 하는 UX 회귀 발생.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_ensure_seed_catchup(conn)` 안 `_ensure_seed_role_system_prompts(conn)` 직후에 `_ensure_seed_global_system_prompt(conn)` 추가. idempotent — 기존 row 가 있으면 no-op, agent_core import 실패 시 silent skip.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260521-0004.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary follow-up note.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0095 entry sub-bullet.
- Verification:
  - py_compile PASS (app.py).
  - 사후 검증 절차: web 컨테이너 재배포 → `SELECT * FROM WebSystemPrompts WHERE Scope='global'` 1 row + Content 본문 = `agent_core.SYSTEM_PROMPT` (3179 chars) 일치 → `GET /api/admin/system-prompts?scope=global` 응답 `prompt.content` 비어있지 않음 확인.
- Risks:
  - 기존 row 가 빈 본문으로 이미 누군가 저장한 환경에서는 본 helper 가 no-op (existing row truthy → return). 의도한 동작이며, 운영자가 직접 갱신해야 한다.
- Trace: REQ-20260521-0003 → TASK-0095 → CHG-20260521-0004 → REV-20260521-0004 (CHG-20260521-0003 follow-up fix).

## CHG-20260520-0010
- Date: 2026-05-21
- Related Requirement: TASK-0087, REQ-20260520-0002
- Summary: 외부 LAN trust 강화 — TASK-0073 Eng review E3 의 deferred 항목 (`_get_client_ip(request)` X-Forwarded-For 무조건 trust = 사내 LAN + Caddy proxy 전제, 외부 LAN/공개 인터넷 노출 시 IP spoof 위험) 을 명시적 정책 + 코드로 lock-in. Plan v1 (RFC1918 trust + silent skip) → Codex outside voice review 6 findings (Major 5 + Minor 1) → Plan v2 (Caddy XFF 정규화 + mode-aware fail-loud + XFF IP 검증) 흡수. 사용자 명시 결정: RFC1918 default 유지 (사내 dev/staging 전제) + docker-compose port mapping 변경은 별 cycle. 본 변경은 feature-0003 + feature-0006 dual ownership — feature-0006 의 `CHG-20260520-0010` 와 동일 의의.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - imports 에 `ipaddress`, `sys` 추가 (알파벳 순 삽입)
    - `_parse_trusted_proxies(raw) -> tuple[_TrustedNetwork, ...]` helper 신설 — 콤마 분리 + `ipaddress.ip_network(token, strict=False)` 파싱. invalid 토큰은 `AGENT_MODE in {prod, staging}` 에서 `RuntimeError` startup, dev/test/"" 에서 stderr WARNING + 해당 토큰만 skip
    - module-level `WEB_TRUSTED_PROXIES = _parse_trusted_proxies(os.getenv("WEB_TRUSTED_PROXIES", ""))`
    - `ENABLE_WEB_TLS_PROXY=1` + `WEB_TRUSTED_PROXIES` empty 조합 startup gate — prod/staging `RuntimeError`, dev/test stderr WARNING (PIPA §29 audit `IpAddr` 품질 회귀 경고)
    - `_is_trusted_proxy(host) -> bool` helper — host 가 `WEB_TRUSTED_PROXIES` CIDR 화이트리스트 안인지 검증
    - `_get_client_ip(request) -> str` 재작성 — `direct_ip = request.client.host`, direct_ip 가 trusted proxy 이면 `X-Forwarded-For` 첫 토큰 사용 + `ipaddress.ip_address(first)` 파싱 검증 + 실패 시 direct_ip fallback. 그 외 모두 direct_ip 반환
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0087 checkbox close + §2.9 Implementation Plan 신설 (사용자 in-cycle 결정 3 항목 + Phase A~E + 8 test 시나리오 + REV-20260520-0010 정본 + PLAN-APPROVED 마커)
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0010 [AGENT-TEAM:codex-outside-voice] (Verdict: NEEDS_REVISION, 6 findings Major 5 + Minor 1, 사용자 명시 결정으로 Major 1 거부 + 나머지 5 흡수)
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단 TASK-0087 cycle entry 추가
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 Audit subsystem followup 에 TASK-0087 시나리오 8 건 추가
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0205 / AC-0206 / AC-0207 신설
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`: `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가 (Caddy 가 받은 임의 XFF 를 본인이 본 TCP peer IP 로 덮어씀 → multi-hop / spoof 차단)
  - `unit/feature-0006-lan-proxy-access/docs/TASK.md`: TASK-0006 신규 entry + Task Queue
  - `unit/feature-0006-lan-proxy-access/docs/MODIFY.md`: CHG-20260520-0010 (dual ownership)
  - `unit/feature-0006-lan-proxy-access/docs/REVIEW.md`: REV-20260520-0010 (dual ownership)
  - `unit/feature-0006-lan-proxy-access/docs/REPORT.md`: §1 Summary cycle entry 추가
  - `unit/feature-0006-lan-proxy-access/docs/TEST.md`: TEST-0004 (caddy validate) 추가
  - `unit/feature-0006-lan-proxy-access/docs/FUNCTION.md`: AC-0004 (XFF 정규화) 신설
  - `docs/SECURITY.md` §9.7: 기존 "deferred to feature-0006" 마커를 8 bullet 정책 (Caddy XFF 정규화 / 조건부 trust / XFF token 검증 / RFC1918 사용자 명시 결정 trade-off / mode-aware fail-loud / proxy mode + empty / schema 호환 / share token 미래 결합) 으로 교체
- Diff size: app.py +51 lines (`_parse_trusted_proxies` + `WEB_TRUSTED_PROXIES` + proxy-mode gate + `_is_trusted_proxy` + `_get_client_ip` 재작성 — 기존 9 lines → 60 lines), Caddyfile +1 line, SECURITY.md §9.7 +9 lines (3 lines → 12 lines).
- Impact:
  - **audit `IpAddr` 품질**: 사내 LAN dev/staging 환경에서 audit IP 가 정확히 클라이언트 IP 로 기록 — 기존 동작 유지 (`WEB_TRUSTED_PROXIES` RFC1918 권장값 설정 시).
  - **외부 LAN spoof 차단**: Caddy 가 받는 임의 `X-Forwarded-For` 가 무시되고 Caddy 가 본 TCP peer IP 로 정규화. web 의 `_get_client_ip()` 가 direct connection IP 검증 후 XFF 사용 — 외부에서 임의 XFF 주입 attack 차단.
  - **malformed env 운영자 인지**: prod/staging 에서 invalid CIDR 또는 proxy mode + empty env 조합이 startup 실패 → 운영자가 즉시 인지.
  - **backward 호환 (default)**: `WEB_TRUSTED_PROXIES` 미설정 = `_get_client_ip()` 가 항상 direct_ip 반환. caddy compose 환경에서는 audit IP 가 caddy container IP 가 됨 — proxy mode + empty env warning/fatal 로 회귀 가시화.
  - **RBAC catalog 변경 없음**.
- Rollback Notes:
  - 코드 revert: `_get_client_ip()` 9 lines 원본 복원 + `_parse_trusted_proxies` / `WEB_TRUSTED_PROXIES` / proxy-mode gate / `_is_trusted_proxy` 삭제 + import `ipaddress` / `sys` 제거.
  - Caddyfile revert: `header_up X-Forwarded-For {client_ip}` 한 줄 제거.
  - SECURITY.md §9.7 revert: 8 bullet 정책 → 기존 3 bullet ("deferred to feature-0006") 복원.
  - schema 변경 없음 → DB rollback 불필요.

## CHG-20260521-0003
- Date: 2026-05-21
- Summary: TASK-0095 (REQ-20260521-0003, **Major** §12.3 — GLOBAL system prompt layer 신설). 시스템 프롬프트 누적 구조의 최상위 base 를 코드 상수 hard-code 에서 `WebSystemPrompts WHERE Scope='global'` row 로 이전. 모든 LLM 응답의 base prompt 가 운영자 관리 콘솔에서 관리 가능. RBAC 권한 2 종 신설 (`system_prompt.global.read` / `.write`, group=`settings`). 관리 콘솔 sidebar 에 `설정` 탭 + 확장 가능한 `admin-settings-section` sub-section 패턴 도입.
- Files:
  - `unit/feature-0002-agent-core/src/agent_core.py`:
    - `compose_system_prompt(conn, ...)` 함수 진입부 — `WebSystemPrompts WHERE Scope='global' AND ProductId IS NULL AND RoleId IS NULL AND AccountId IS NULL LIMIT 1` 조회 + 성공 시 base 로 사용, 실패 / row 없음 / 빈 본문 시 코드 상수 `SYSTEM_PROMPT` fallback. `parts: list[str] = [base_prompt]` 로 누적 시작.
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_ensure_seed_global_system_prompt(conn)` helper 신설 (after `_ensure_seed_role_system_prompts`): idempotent — 기존 row 있으면 no-op, 없으면 `agent_core.SYSTEM_PROMPT` 본문을 seed 로 INSERT. import / seed 본문 빈 경우 silent skip.
    - 부트스트랩 (`_ensure_seed_catchup` / `_ensure_web_tables` 후속) 에서 helper 호출.
    - `PERMISSION_DEFINITIONS` 에 `system_prompt.global.read` / `system_prompt.global.write` 2 권한 추가 (group=`settings`).
    - `_ensure_seed_roles` 의 admin 자동 grant catchup list 에 두 권한 코드 추가.
    - `GET /api/admin/system-prompts` scope allowlist 에 `global` 추가 + `system_prompt.global.read` 권한 가드 + `product_id` / `role_id` / `account_id` 인자 NULL 강제.
    - `PUT /api/admin/system-prompts` 동일 패턴 (`system_prompt.global.write` 권한 가드).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`:
    - sidebar 에 `시스템` 그룹 라벨 + `설정` 탭 (`data-admin-tab="settings"`) 추가.
    - `<section data-admin-pane="settings">` pane 신설 — `<article data-settings-section="global-prompt">` sub-section 컨테이너 + `<div id="globalPromptEditorMount">` mount point.
    - cache-bust 토큰 `v=20260519-audit-tab` → `v=20260521-settings-tab`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `PERMISSION_GROUP_ORDER` 에 `settings` 추가 (`product` 와 `misc` 사이).
    - `PERMISSION_GROUP_LABELS.settings = "시스템 설정"`.
    - `ADMIN_PERMISSION_SECTIONS.manage` 에 `settings` 그룹 포함.
    - `buildSystemPromptEditor({scope})` — `isGlobal` boolean + product select 조건 (`!isGlobal && scope !== "product" && !fixedProductId`) 으로 global scope 일 때 product 드롭다운 미렌더.
    - `switchTab("settings")` handler — `adminState.settings.initialized` 가드 + `mountSettingsSections()` 호출.
    - `mountSettingsSections()` — `system_prompt.global.read` 권한 검사 + `buildSystemPromptEditor({scope:'global', mountId:'globalPromptEditorMount'})` 마운트 + `system_prompt.global.write` 미보유 시 textarea read-only.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `PERMISSION_GROUP_ORDER` 에 `settings` 추가.
    - `PERMISSION_GROUP_LABELS.settings = "시스템 설정"`.
    - `WORK_SCREEN_PERMISSION_SECTIONS.manage` 에 `settings` 그룹 포함.
    - `permissionGroupOf(code)` — `system_prompt.global.` 접두사 우선 `settings` 그룹으로 매핑, 그 외 `system_prompt.` 는 기존대로 `product` fallback.
    - `PERMISSION_LABELS` / `PERMISSION_DESCRIPTIONS` 에 `system_prompt.global.read` / `.write` 2 entry 추가.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - `.admin-pane-hint` / `.admin-settings-list` / `.admin-settings-section` / `.admin-settings-section-head h3` / `.admin-settings-section-hint` / `.admin-settings-section-body` rules 추가 — sub-section 카드 패턴 (border + padding + flex-column gap), 차후 운영 항목 추가 시 동일 패턴 재사용.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0095 entry + Plan §2.7 PLAN-APPROVED marker (ms.mckim.gpt@gmail.com, 2026-05-21).
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: REQ-20260521-0003 추가 + AC-0011 갱신 (5 layer 명시) + AC-0199 ~ AC-0204 신설.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260521-0003.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary sticky note.
- Schema: 변경 없음 — `WebSystemPrompts.Scope VARCHAR(16)` 가 이미 'global' 을 수용. UNIQUE INDEX `UX_WebSystemPrompts_Scope` 가 `(Scope, ProductId, RoleId, AccountId)` 정합으로 working — global row 는 `(scope='global', product_id=NULL, role_id=NULL, account_id=NULL)` 단 1건.
- Audit: 기존 `admin.system_prompt.update` ActionCode + `_audit_admin_mutation` Same tx hook 재사용. ChangeJson 의 `scope` 필드가 `'global'` 인 row 가 새로 등장 — `_audit_admin_mutation` 의 redaction allowlist 에 system_prompt.content 본문이 이미 미포함 (SECURITY §9.2 정합). content_full 마스킹 정책은 GLOBAL scope 에도 그대로 적용.
- RBAC default grant 정책: admin role 만 자동 grant. operator/sales/dba/pending 은 명시 grant 가 없는 한 미보유 — 모든 LLM 응답에 영향가는 권한이라 운영자 한정 패턴 의도적으로 채택.
- Verification:
  - py_compile PASS (agent_core.py, app.py — 단 agent_core.py 76 line `'\``' SyntaxWarning 은 pre-existing, 본 cycle 무관).
  - node --check PASS (admin.js, app.js).
- Risks:
  - GLOBAL row 본문이 잘못 입력되면 모든 LLM 응답에 영향 — 운영자 한정 권한 + 빈 본문 시 코드 상수 fallback 으로 위험 완화.
  - 부트스트랩 시점 `from agent_core import SYSTEM_PROMPT` 가 실패할 수 있는 환경 (web 컨테이너 정상 환경에선 무관) — 본 helper 는 lazy try/except 으로 처리, seed 자체 skip 시에도 compose_system_prompt 는 자기 fallback 으로 정상 작동.
  - live runtime smoke (관리 콘솔 `설정` 탭 진입 + 본문 수정 + LLM 호출 시 적용 확인) 는 사용자 검증으로 위임.
- Trace: REQ-20260521-0003 → TASK-0095 → CHG-20260521-0003 → REV-20260521-0003.

## CHG-20260520-0009
- Date: 2026-05-20
- Summary: TASK-0089 (REQ-20260520-0004, **Minor** §12.3 — 작업 화면 audit drawer UX). profile drawer "내 감사 로그" 탭 신설 + 신규 backend endpoint 2 (`/api/profile/audits` + detail) + frontend (HTML + JS + CSS). Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 v2 redesign.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: 신규 endpoint 2 (`list_profile_audit_events` line ~9981, `get_profile_audit_event` line ~10043). 기존 helper 재사용 (`_audit_parse_filter_params`, `_audit_compose_where(scope="own")`, `_audit_row_to_dict`, `_audit_build_self_filter_sql`). `scope="own"` **강제** — `.any` 보유자도 본인만 (Codex C2).
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: drawer-tab "내 감사 로그" (line 228, `data-profile-tab="audit"` + id `profileAuditTab` + hidden default) + drawer-pane (filter row mini 3 필드 + 1-column list + pagination + inline detail). cache-bust `v=20260520-profile-audit`.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `state.profileAudit = {items, selectedId, filters, nextCursor, loading, forbidden}` + helper 6 (`_profileAuditEscapeHtml`, `_profileAuditFormatDt`, `_profileAuditHasReadPermission`, `updateProfileAuditTabVisibility`, `_profileAuditReadFilters`, `_profileAuditClearFilters`) + loader (`loadProfileAuditList`) + renderer (`renderProfileAuditList`, `renderProfileAuditDetail`) + handlers (`attachProfileAuditHandlers`). tab click handler audit branch + `renderProfile()` tab visibility wire.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.profile-audit-*` ~15 클래스 — filter row + 1-column list + row hover/selected + pagination + inline detail dl + `<pre>` overflow:auto 수평 스크롤 (Codex C4).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: §2.8 + TASK-0089 [x].
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0009.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 본 cycle 결과.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0194.
- Codex outside voice 5 findings 흡수:
  - C1 URL 의미 mismatch → `/api/profile/audits` 신설
  - C2 `.any > .own` 우선 → backend `scope="own"` 강제
  - C3 CSV export drawer 위험 → 미노출 (admin 한정)
  - C4 drawer 폭 1-column + ChangeJson 수평 스크롤
  - C5 권한 race → tab visibility + 403 graceful
- Verification:
  - py_compile PASS
  - node --check app.js PASS
  - routing smoke: `/api/profile/audits` + `/api/profile/audits/{event_id}` 등록 확인
  - `list_profile_audit_events` + `get_profile_audit_event` 함수 존재 확인
- Risks: live browser smoke (drawer tab 클릭 → list 표시 → click → inline detail expand → filter 적용 / 403 시 "권한 없음") PR merge 후 사용자 위임. `audit.read.own` 권한 없는 사용자에게 tab 자체가 hidden — `updateProfileAuditTabVisibility()` 가 `renderProfile()` 마다 호출.
- Trace: REQ-20260520-0004 → TASK-0089 → CHG-20260520-0009 → REV-20260520-0009.

## CHG-20260520-0008
- Date: 2026-05-20
- Summary: TASK-0090 (REQ-20260520-0005, **Minor** §12.3 — CSV streaming export). `/api/admin/audits/export.csv` hard cap 50k row 제거 + StreamingResponse + keyset cursor pagination 전환. Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `StreamingResponse` import 추가 (line 28).
    - 신규 helper `_audit_export_filter_hash(params)` (~line 9466): filter PII 회피용 sha256[:16] hash.
    - 신규 const `_AUDIT_EXPORT_CHUNK_SIZE = 500` + `_AUDIT_EXPORT_FLUSH_BYTES = 65536`.
    - `export_audit_events_csv` endpoint 전면 재작성: 2-phase (짧은 auth conn + max_id capture + start audit → sync generator with streaming-only conn + chunked SELECT + byte-threshold flush + try/finally + complete audit).
  - `docs/SECURITY.md §9.5`: `audit.export` 설명 갱신 (hard cap 50k 제거 + StreamingResponse + max_id high-water + self-audit + 동시 제한 별 cycle).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: §2.7 + TASK-0090 [x].
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0008.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 본 cycle 결과.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0193.
- Codex outside voice 5 findings 흡수:
  - C1 async generator + sync mysql → sync generator (def csv_iter) + streaming-only conn (generator 내부 finally)
  - C2 consistent snapshot → max_id high-water mark (long transaction 회피)
  - C3 query plan 미보장 → TEST.md EXPLAIN 기록 (future cycle, live mysql)
  - C4 cap 제거 = DoS/계약 변경 → SECURITY 갱신 + export self-audit + 동시 제한 별 cycle followup
  - C5 cleanup → generator 내부 try/finally (cursor + conn + complete audit)
- 추가: chunk_size 1000→500, 64KiB byte-threshold flush, CRLF 유지 (BOM 추가 안 함).
- Self-audit ActionCode 신설: `audit.export.start`, `audit.export.complete`, `audit.export.aborted` (purge 패턴 답습).
- Verification:
  - py_compile PASS
  - lightweight smoke: _AUDIT_EXPORT_CHUNK_SIZE=500 ✓, _AUDIT_EXPORT_FLUSH_BYTES=65536 ✓, helper 존재 ✓, StreamingResponse import ✓, filter_hash deterministic ✓
- Risks: live runtime smoke (PATCH 호출 + WebAuditEvents row 검증) PR merge 후 사용자 위임. 동시 export 제한 별 cycle (multi-worker semaphore 정합 검토). representative filters EXPLAIN 분석 별 cycle.
- Trace: REQ-20260520-0005 → TASK-0090 → CHG-20260520-0008 → REV-20260520-0008.

## CHG-20260520-0007
- Date: 2026-05-20
- Summary: TASK-0088 (REQ-20260520-0003, **Minor** §12.3 — `slow_query_log` 통합 ADR-0020 결정, docs only). ADR-0019 의 Codex C1 lock-in 의 최종 결론 — **Option C Decoupled 채택** (slow_query_log 와 WebAuditEvents 통합 안 함). Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign 적용.
- Files:
  - `docs/DECISIONS.md`: ADR-0020 신설 (line 207~ ADR-0019 Consequences 다음). 4 section — Context (current state: not enabled, forward-looking) + Decision (Option C Decoupled, raw SQL PII 차단 1순위) + Options 검토 (A/B reject 구체 사유 + C 채택) + Recommended performance path (PS digest-first 1차, slow_query_log incident enable 2차) + Security policy + Consequences (외부 SaaS trigger 4 선행 조건). ADR-0019 Consequences 의 "별 cycle 분리" 라인에 ADR-0020 cross-reference 추가.
  - `docs/SECURITY.md §9.9`: ADR-0020 cross-reference + raw SQL = 민감 로그 + admin UI/ChangeJson 복제 금지 + PS digest-first 정책.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0088 [ ]→[x] + §2.6 본 plan PLAN-APPROVED.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0007 entry.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 갱신.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 본 cycle 결과 (docs only, ADR review trace).
- Decision 요지: slow_query_log 와 WebAuditEvents 의 통합 reject. 운영 성능 관측 = performance_schema/sys digest views (1차) + slow_query_log incident enable (2차). 외부 SaaS/multi-tenant trigger 시 `performance-log.read` permission + redaction/sampling + threat model ADR 선행 필수.
- Codex outside voice 5 findings 흡수:
  - **C1** current state framing 정정 (not enabled, forward-looking)
  - **C2** raw SQL PII 차단을 주 근거로 (1순위)
  - **C3** Option A reject 재작성 (semantic pollution + raw SQL PII + ChangeJson bloat + actor/target 의미 부재)
  - **C4** Option B reject 재작성 (raw SQL exfiltration + mount/race + DoS + 권한 의미 오염 + TABLE log destination 우회)
  - **C5** performance_schema digest-first 권유 추가
- Verification: docs only, code 변경 0. py_compile/runtime smoke 불필요. verify-completion PASS 만 확인.
- Risks: ADR 자체는 future trigger 조건만 명시 — 현재 운영 영향 0. 외부 SaaS/multi-tenant 진입 시점에 별 cycle (Major §12.3) 재진입 명시 (트리거 조건 4 선행).
- Trace: REQ-20260520-0003 → TASK-0088 → CHG-20260520-0007 → REV-20260520-0007.

## CHG-20260520-0006
- Date: 2026-05-20
- Summary: TASK-0091 (REQ-20260520-0006, ~~Minor~~→**Major** §12.3 — PATCH admin/products audit before-state full snapshot + audit integrity fix). Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 — Minor 등급 추정이 audit integrity 결함 (autocommit=True default) 노출 → scope 확장.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - 신규 helper `_audit_product_snapshot(conn, product_id)` (~line 2127): single-row WebProducts snapshot + `SELECT ... FOR UPDATE` + `system_prompt_summary = {present, content_len, updated_at}` (SECURITY §9.2 정합 — content 본문 제외). `databases` 제외 (Codex C3 — 별 endpoint audit).
    - `admin_update_product()` 갱신 (line 8328~): `conn.autocommit=False` + before snapshot + UPDATE + `default_cleared_product_ids` 캡처 + after snapshot + audit + commit + `finally autocommit=True` (Codex C2 audit integrity fix).
    - `_AUDIT_BUILDER_PRODUCT_FIELDS` 확장 (line 8862): 7→8 field. `+is_default`, `+sort_order`, `+system_prompt_summary` / `-databases`, `-system_prompt` (Codex C1+C4).
    - builder branch `admin.product.update` (line 8966~): `default_cleared_product_ids` 키 명시 처리 (Codex C4 side effect).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` §2.5 본 plan + TASK-0091 [x]
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` REV-20260520-0006
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` §1 Summary
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` §4 sentinel + delta smoke 결과
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` AC-0192
- Codex outside voice 5 findings 흡수:
  - **C1**: `system_prompt.content` full drop → `system_prompt_summary` only (SECURITY §9.2)
  - **C2**: autocommit/transaction integrity fix (audit 실패 시 UPDATE rollback 가능)
  - **C3**: single-row `SELECT FOR UPDATE` + databases 제외
  - **C4**: allowlist 확장 (`is_default`, `sort_order`) + `default_cleared_product_ids` side effect
  - **C5**: C1 ACCEPT 로 자동 해소 (full content drop)
- Verification (Phase C sentinel smoke):
  - py_compile PASS
  - `'TASK-0091-SENTINEL' in body: False` ✓ (system_prompt full drop)
  - `'should_not_leak' in body: False` ✓ (databases drop)
  - sort_order 100→50 / is_default False→True / `default_cleared_product_ids: [5,9]` / `system_prompt_summary` 정합 ✓
- Risks: scope ~~Minor~~→Major (audit integrity fix 포함). 사용자 영향 0 (audit row 정확성). DB schema 변경 0. PATCH admin/products endpoint behavior: 외부 contract 동일, internal transaction semantics 만 변경.
- Trace: REQ-20260520-0006 → TASK-0091 → CHG-20260520-0006 → REV-20260520-0006.

## CHG-20260520-0005
- Date: 2026-05-20
- Summary: TASK-0086 (REQ-20260520-0001, **Major** §12.3 — `WebAccountActivity` legacy table DROP + dual write 종료). TASK-0073 Phase A2 의 dual source 일시 공존을 단일 source-of-truth (WebAuditEvents) 로 전환. Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용. backup + scratch restore rehearsal + 1:1 정합 (74=74) + 사용자 명시 ack 후 진행.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_log_search_activity()`: legacy `INSERT INTO WebAccountActivity` 블록 제거. dispatcher (`record_audit_event` → WebAuditEvents) 만 primary path. signature transparent 보존. docstring 갱신.
    - `_ensure_web_account_activity_schema()`: 함수 정의 + 호출 2 사이트 명시 제거 (Codex C1 — helper Option B 채택).
    - `_migrate_web_account_activity_to_audit()`: 함수 본체 + `SHOW TABLES LIKE` table-absent skip 보존. docstring 갱신 (TASK-0086 rollback 1~2 cycle window 명시).
  - `unit/feature-0003-agent-web-ui/tests/test_audit_migration.py`: 모듈 docstring 갱신 (3→2 시나리오) + `m3_log_search_activity_dual_write()` 제거 + main() M3 호출 제거 (Codex C2 minimum-fix).
  - `docs/SECURITY.md` §9.8: "별 cycle DROP" → "DROP 완료 (2026-05-20)" + 8 step 절차 + backup file + rollback 2 시나리오 cross-reference.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` §2.4 Implementation Plan (TASK-0086) 신설 + TASK-0086 [x] 마킹.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` REV-20260520-0005 entry 추가.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` §1 Summary 갱신.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` §4 본 cycle 결과 prepend.
- DB: `DROP TABLE IF EXISTS WebAccountActivity` 실행. `SHOW TABLES` = 0 ✓. WebAuditEvents `conversation.search.body` row 74 변동 없음 ✓.
- Backup: `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes, 74 row, digest `a09e7898d1ce88711f7a850ab5fbcc91`, file md5 `f4163df9dc1b7ac81ae4c463a0f35e98`). mysqldump 8 옵션 + scratch restore rehearsal PASS.
- v2 redesign (Codex 5 findings 흡수): C1 Option A 불가능 → helper Option B / C2 dispatcher-only 검증 → lightweight smoke + M3 제거 / C3 "single tx" → "single statement" / C4 backup 검증 강화 / C5 rollback 2 시나리오.
- Verification: Phase A~G 모두 PASS (backup integrity / 1:1 정합 / py_compile / import smoke / DROP 정합 / SHOW TABLES = 0 / mirror 보존).
- Risks: rollback window 1~2 cycle 동안 migration helper 보존. dispatcher-only 후 mirror failure = audit 누락 risk → lightweight smoke mitigated. function rename 별 cycle.
- Trace: REQ-20260520-0001 → TASK-0086 → CHG-20260520-0005 → REV-20260520-0005. TASK-0073 Phase A2 dual write 종료.

## CHG-20260520-0004
- Date: 2026-05-20
- Summary: TASK-0092 (REQ-20260520-0007, **Minor** §12.3 — `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed 7 vector matrix 검증). TASK-0073 Phase E 의 사용자 위임 항목 1 건 해소 (sandbox SSH 인증 차단 환경 해소 + docker/compose 가용 확인). Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용. Code 변경 0, docs append only.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` — **§4** Test Run History 에 본 cycle 7 vector 결과 prepend (Codex C5 흡수 — §3 = Test Cases, §4 = Test Run History).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — §2.3 Implementation Plan (TASK-0092) 신설 (PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20). TASK-0092 [ ]→[x] 마킹.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0004 entry 추가 (head prepend, outside voice 5 findings + 2 minimum-fix 흡수 이력).
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary 갱신 + 1.archived TASK-0093 Summary 보존.
- v2 redesign (Codex 5 findings 흡수):
  - **C1** 테스트 명령 오류: Dockerfile 이 web UI 를 `/app/web/` 에 복사 → `--entrypoint python` + `import web.app` 으로 정정. uvicorn entrypoint 우회 명확화.
  - **C2** compose 오염 위험: `docker run` 직접 호출 (compose 우회). `--no-deps` 동등 효과 — mysql 기동 + .env + shared volume + 다른 worktree compose project 모두 회피.
  - **C3** flag parsing 계약: V6 추가 (`AGENT_AUDIT_ENABLED=true` + prod → exit 1). strict-string-equality (`os.getenv(...).strip() == "1"`) 계약 명시화. 운영자가 `"true"` / `"yes"` / `"01"` 명시 시 fail-closed — SECURITY.md §8 계약 명시 별 cycle 후속 권고.
  - **C4** stderr 검증 강화: prefix-only 약함, full byte-equal strict 회피. 3 substring (`[FATAL] AUDIT REQUIRED IN PROD` + `set AGENT_AUDIT_ENABLED=1` + `TASK-0073 Phase A1`) 모두 포함 + `Traceback` / `ModuleNotFoundError` 부재 검증.
  - **C5** docs append 위치: TEST.md §3 → §4 (Test Run History) 정정.
- Verification (Phase A~B):
  - (Phase A0) `repo-web:latest` image 가용 확인 (435MB). `.env` 부재 — inline `-e` 만 사용.
  - (Phase A) 7 vector live spawn 실행 (`docker run --rm --entrypoint python repo-web:latest -c "import web.app"`).
  - (Phase B) **7 vector PASS (7/7)**:
    - V1 (audit=0 + mode=prod) → rc=1 + `[FATAL] ... AGENT_MODE=prod ...`
    - V2 (audit=0 + mode=unset) → rc=1 + `[FATAL] ... AGENT_MODE=(unset → prod) ...`
    - V3 (audit=0 + mode=staging) → rc=1 + `[FATAL] ... AGENT_MODE=staging ...`
    - V4 (audit=0 + mode=dev) → rc=0 + `IMPORTED OK`
    - V5 (audit=1 + mode=prod) → rc=0 + `IMPORTED OK`
    - V6 (audit=true + mode=prod) → rc=1 + `[FATAL] ... AGENT_MODE=prod ...` (Codex C3 strict-string-equality 계약)
    - V7 (모두 unset) → rc=0 + `IMPORTED OK`
- Risks: V6 가 운영자 trap (`AGENT_AUDIT_ENABLED="true"` 가 fail-closed) 노출 — SECURITY.md §8 의 strict-string-equality 계약 명시 필요 (별 cycle 후속). audit prod gate 자체는 정합 — 본 cycle scope 외.
- Trace: REQ-20260520-0007 → TASK-0092 → CHG-20260520-0004 → REV-20260520-0004.

## CHG-20260520-0003
- Date: 2026-05-20
- Summary: TASK-0093 (REQ-20260520-0008, **Minor** §12.3 — `bin/verify-completion.sh check_12` audit endpoint routing 정적 검사 신설). TASK-0073 Phase E hotfix (CHG-20260520-0001) 의 routing 회귀 fragility 보강. Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용.
- Files:
  - `bin/verify-completion.sh` — `check_12_audit_endpoint_routing()` 함수 신설 (line ~936-955) + `_check_audit_routing_order()` pure helper split (line ~957-1010). `main()` 의 line 1123 에 호출 추가. footer line 1126·1129 의 "9 checks" → "10 checks: 7 pilot + worktree binding + repo immutability + audit endpoint routing". META mode footer (line 1084·1091·1094) 는 그대로 — check_12 는 feature-specific 라 META mode 에서 의도적으로 skip.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — §2.2 Implementation Plan (TASK-0093) 신설 (PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20). TASK-0093 [ ]→[x] 마킹.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0003 entry 추가 (head prepend, outside voice 흡수 이력 + 5 findings 표).
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` — Phase A~F 변경 요약 + git 동기화 결과.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` — TEST 케이스 정의 (positive 1 + negative 5 fixture + SKIP 5 other-feature + 1 missing-app structural FAIL).
- check_12 spec (v2, Codex outside voice 5 findings 흡수):
  - feature_id != "feature-0003-agent-web-ui" 만 SKIP (silent return 0). 그 외 분기는 모두 FAIL — APIRouter 분리·prefix 변경·route 삭제가 silent pass 되는 v1 의 회귀 방지 게이트 의도 모순 (Codex C1) 차단.
  - 정적 GET sibling list 는 inline 4-path hardcoded 가 아니라 auto-discovery (`@app.get("/api/admin/audits/<non-{>")` 패턴 grep). new static GET 추가 시 자동 catch (Codex C4).
  - `/purge` (POST) 는 method-aware 라 GET `/{event_id}` 와 collision 위험 0. auto-discovery 패턴이 `@app.get(...)` 만 매치하여 자연 제외. hint 정확화 (Codex C3).
  - helper split (`_check_audit_routing_order(app_path)`) — Phase C fixture 테스트 진입점. production app.py 외에도 임의 fixture 파일로 호출 가능 (Codex C5).
  - `set -euo pipefail` 환경의 grep no-match (exit 1) 시 `|| true` fallback 처리 — log_check 호출 보장 (in-cycle fix during Phase C debug).
  - FAIL hint 4 종: (1) "audit routes not found in expected '@app.get("/api/admin/audits/...")' form" — structural refactor, (2) "static audit GET sibling(s) detected but '/{event_id}' detail endpoint missing" — route removal, (3) "'/{event_id}' detail endpoint detected but no static GET siblings" — layout 변화, (4) "'/api/admin/audits/{event_id}' (line N) precedes static GET sibling 'X' (line M). FastAPI/starlette linear match would route 'X' to '{event_id}' (422 int_parsing). Move '{event_id}' definition after all static GET siblings" — ordering 위반.
- Verification:
  - (Phase A) `bash -n bin/verify-completion.sh` PASS — syntax 정합.
  - (Phase B) production positive: `_check_audit_routing_order` wrapper 호출 → `CHECK#12 PASS audit endpoint routing order` (production app.py line 9522 max-static < line 9732 detail).
  - (Phase C) 5 fixture negative: valid.py PASS / wrong_order.py FAIL ordering / no_detail.py FAIL "detail endpoint missing" / no_siblings.py FAIL "no static GET siblings" / refactored.py FAIL "routes not found in expected form".
  - (Phase D) 5 other-feature SKIP: feature-0001 / 0002 / 0004 / 0005 / 0006 호출 → rc=0, no output.
  - (Phase D 추가) target feature + app.py 부재 → FAIL "expected app.py at <path> but file is missing".
- Risks: feature-0003 hardcode 는 의도적 — 일반화는 별 cycle. auto-discovery 패턴이 `@app.get(...)` 만 매치 — `@router.get(...)` / `app.include_router(prefix=...)` 등 APIRouter 패턴 채택 시 structural FAIL "routes not found in expected form" 으로 manual review 강제 (LOUD fail 의도). multi-line decorator / single quote / trailing slash 변형도 동일 — structural FAIL 로 잡힘. 본 cycle scope (Minor) 에서 AST 파서까지 도입 안 함.
- Trace: REQ-20260520-0008 → TASK-0093 → CHG-20260520-0003 → REV-20260520-0003.

## CHG-20260520-0002
- Date: 2026-05-20
- Summary: TASK-0073 후속 cycle backlog (TASK-0086~TASK-0093) list-up. `ai/claude/0086/audit-followup` worktree 의 단일 commit 으로 다음 세션 진입점 (`/_template:entry`) lock-in. 본 backlog 의 각 entry 는 별 cycle (별 PLAN-APPROVED + 별 CHG/REV) 로 분리.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — §2. Task Queue 의 머리에 "TASK-0073 Audit subsystem followup backlog (2026-05-20)" subsection 신설. 8 entries:
    - TASK-0086 Major §12.3 — WebAccountActivity legacy table DROP + dual write 종료 (data backup + 5 sub-step)
    - TASK-0087 Major §12.3 — 외부 LAN trust 강화 (Caddy trust_forwarded_for + `_get_client_ip` whitelist, feature-0006 위임)
    - TASK-0088 Minor §12.3 — slow_query_log 통합 ADR-0020 결정
    - TASK-0089 Minor §12.3 — 작업 화면 audit drawer UX (`audit.read.own` 본인 view)
    - TASK-0090 Minor §12.3 — CSV streaming export (`StreamingResponse` + generator)
    - TASK-0091 Minor §12.3 — PATCH admin/products audit before-state full snapshot
    - TASK-0092 Minor §12.3 — AGENT_AUDIT_ENABLED=0+prod startup fail-closed 검증 (Phase E 사용자 위임 항목)
    - TASK-0093 Minor §12.3 — verify-completion check_12 audit endpoint routing 정적 검사 (Phase E hotfix fragility 보강)
- Verification: 본 commit 은 docs only — code 변경 없음. 신규 worktree 의 base 는 a060c64 (TASK-0073 Phase E hotfix 머지 후 main HEAD). 다음 세션 진입 시 `cd /root/download/docker/mysql_ai_delegated_dev/.worktrees/0086-audit-followup && /_template:entry <선택한 task> 진행해주세요` 형태로 사용.
- Risks: backlog 8 entries 가 단일 worktree 에 묶임 — 다음 세션이 1 cycle 한정 1 task 만 진행. 다른 task 는 별 worktree (`ai/claude/0087/...` 등) 분기 필요. 또는 본 worktree 안에서 별 branch checkout (§13.2.2 F1 binding 위반 — 허용 안 됨). 다음 세션 작업자가 본 worktree 의 첫 task 선택 후 별 worktree 권장.
- Trace: TASK-0073 후속 → CHG-20260520-0002 → REV-20260520-0002. 본 backlog 는 신규 cycle 들의 staging area.

## CHG-20260520-0001
- Date: 2026-05-20
- Summary: TASK-0073 Phase E hotfix (REQ-20260519-0001, **Critical** §12.3) — `/api/admin/audits/{event_id}` routing 순서 회귀 fix + browser smoke 검증 PASS. main worktree 의 `make web` 재배포 후 audit subsystem 8 endpoint 실 검증 중 발견.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py` — `get_audit_event(event_id: int, ...)` endpoint 의 정의 위치를 `export_audit_events_csv` / `list_audit_actors` / `list_audit_resources` / `purge_audit_events` 4 정적 sibling endpoint 뒤로 이동. NOTE comment 추가 — FastAPI/starlette 의 linear match order 가 `/{event_id}` path parameter 로 `export.csv` / `actors` / `resources` 를 잡아 422 int_parsing error. 본 fix 로 detail endpoint 가 정적 path 다음에 매칭.
- Verification: `python3 -m py_compile` PASS. `make web` 재배포 후 browser smoke 검증 PASS:
  - GET /api/admin/audits/{int} → 200 + detail (item.id=128, action=admin.role.create)
  - GET /api/admin/audits/export.csv → 200 + Content-Type=text/csv + Content-Disposition=attachment
  - GET /api/admin/audits/actors → items=[{actor_account_id: 1, username: 'bootstrap_admin'}]
  - GET /api/admin/audits/resources → items=[{resource_type: 'conversation'}, {resource_type: 'role'}]
  - POST /api/admin/audits/purge dry_run → {purged: 0, to_purge: 0, cutoff: '2026-05-01T...', chunk_size: 1000}
  - admin.role.create 호출 → audit row 68→69 (delta=1) + ChangeJson 화이트리스트 정합
  - anonymous share view (cookie 없음) → ActorType='anonymous' + ActorAccountId NULL + token_prefix 8 char (`Wp45TbFK`) + view_count_after=2 + masked_fields=['share.token_full']
  - WebAccountActivity → WebAuditEvents migration 68 row 모두 RequestId=`account-activity:%` marker 정합
- Risks: routing 순서 정합성은 endpoint 추가/삭제 시 fragile — 향후 audit endpoint 확장 시 정적 path 가 `/{event_id}` 보다 위에 위치 보장 필요. NOTE comment 가 가이드.
- Trace: REQ-20260519-0001 → TASK-0073 Phase E hotfix → CHG-20260520-0001 → REV-20260520-0001.

## CHG-20260519-0026
- Date: 2026-05-19
- Summary: TASK-0073 Phase E (REQ-20260519-0001, **Critical** §12.3) — Completion Checklist 마킹 + TASK-0073 [~] → [x] + Phase E checkbox [x] + 외부 영향 (make web + browser smoke + AGENT_AUDIT_ENABLED prod fail-closed manual + WebAccountActivity migration SQL count) 사용자 위임 명시. sandbox SSH 인증 차단으로 본 session 내 컨테이너 재배포 불가.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0073 Task Queue entry `[~]` → `[x]` + Phase E sub-checkbox `[x]` + Completion Checklist §7 의 TASK-0073 sub-entries 추가 (20+ AC, 16 [x] + 3 [ ] 사용자 위임 외부 영향). 8 commit hash 목록 본문 포함.
- Verification: 본 phase 는 docs only — code 변경 없음. `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS. TASK-0073 의 모든 Phase 가 [x] 마킹 완료, 외부 영향 (사용자 위임) 3 항목은 [ ] 로 명시.
- Risks: 본 cycle 종료 후 사용자가 외부 영향 검증 안 하면 컨테이너 가동 + audit row 실 검증 미수행 — 별 cycle Phase E 의 결과 보고 (`docs/TEST.md §3 Test Run History` append) 권유.
- Trace: REQ-20260519-0001 → TASK-0073 Phase E → CHG-20260519-0026 → REV-20260519-0022.

## CHG-20260519-0025
- Date: 2026-05-19
- Summary: TASK-0073 Phase D (REQ-20260519-0001, **Critical** §12.3) — 프로젝트 수준 docs 일괄 갱신. SECURITY §9 (Audit subsystem 정책 + Sensitive field catalog source-of-truth) + DECISIONS.md ADR-0019 + ARCHITECTURE.md §4·§6 + CONVENTIONS.md §10.6 audit group + STATUS.md feature-0003 row + feature 의 REPORT.md §1 (Phase 별 변경 요약 + git 동기화 결과) + TEST.md §2.1 audit subsystem scope.
- Files:
  - `repo/docs/SECURITY.md` — §9 (Audit subsystem 정책) 신설. §8 가 TASK-0072 cross-account search 점유라 §9 로 분리. 정합성 보존. 하위 §9.1~9.9: 권한 모델 (`audit.*` 4건 + group=audit), Sensitive field catalog (`_AUDIT_BUILDER_*_FIELDS` + `_AUDIT_MASKED_FIELDS_*` source-of-truth), Tx 정책 split (admin Same tx fail-safe / user fail-open), Anonymous ActorType (E4), purge self-audit + idempotency (E8), `AGENT_AUDIT_ENABLED` prod fail-closed (Codex C5), RemoteAddr spoof risk (E3), WebAccountActivity 흡수 (Codex C2), 보관 정책 + 외부 배포 TODO.
  - `repo/docs/DECISIONS.md` — ADR-0019 신설. Context (TASK-0072 의 WebAccountActivity 한정 + CEO review 9 + Codex 14 + Eng review 9 합의) + Decision (Approach B + WebAuditEvents 단일 + dispatcher + builder allowlist + 2 helper + RBAC 4 + AGENT_AUDIT_ENABLED prod gate + chunked purge + 흡수 migration) + Consequences 11 항목.
  - `repo/docs/ARCHITECTURE.md` — §4 (현재 기능 맵) 의 feature-0003 row 에 audit subsystem 명시 + feature-0006 의 `_get_client_ip` X-Forwarded-For trust 정책 참조. §6 (의존성 맵) 에 feature-0003 → feature-0006 의존 (TASK-0073) 추가.
  - `repo/docs/CONVENTIONS.md` — §10.6 화면별 권한 섹션 정렬 정책에 audit group 추가. group 키 list 갱신 (console/account/role/conversation/product/`audit`/misc). 화면별 2단 section 표의 manage 묶음에 audit 합류. label map 의 `audit`="감사" 추가. 두 화면 모두 "관리 권한" 묶음에 audit 등재.
  - `repo/docs/STATUS.md` — feature-0003-agent-web-ui row 갱신 (TASK-0073 신규 entry prepend). 2026-05-19 audit subsystem 도입 일지 entry prepend.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary rewrite. Phase 별 변경 요약 + git 동기화 결과 (§16.5 Step 6) + 남은 위험 / 후속.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` — §2.1 신설 (Audit subsystem 검증 case 5 분야 — dispatcher unit / RBAC enforcement / migration smoke / AGENT_AUDIT_ENABLED prod fail-closed / admin UI smoke).
- Verification: 본 phase 는 docs only — py_compile / node --check 대상 변경 없음. `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS. SECURITY.md / DECISIONS.md / CONVENTIONS.md / ARCHITECTURE.md 의 정합성 확인.
- Risks: SECURITY.md §8 (TASK-0072) 와 §9 (TASK-0073) 의 1년/365일 retention 정책이 유사 — 별 cycle 통합 검토. CONVENTIONS.md §10.6 갱신 후 작업 화면의 audit placeholder UX 가 실제 entry point 부재 (admin 콘솔 redirect) — UX 보강 별 cycle.
- Trace: REQ-20260519-0001 → TASK-0073 Phase D → CHG-20260519-0025 → REV-20260519-0021.

## CHG-20260519-0024
- Date: 2026-05-19
- Summary: TASK-0073 Phase C (REQ-20260519-0001, **Critical** §12.3) — Frontend admin 콘솔 "감사 로그" tab 신설 + filter / list / detail / CSV export gated + `PERMISSION_GROUP_ORDER` 'audit' group 추가. CONVENTIONS.md §10.6 정합 — admin section 의 관리 권한 묶음에 audit 그룹 합류. 작업 화면 placeholder.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — 새 sidebar tab `data-admin-tab="audits"` (#adminTabAudits) + filter row (action / resource_type / actor_account_id / actor_type select / from_at + to_at datetime-local / q + 적용 / 초기화) + list-detail pane (admin-audit-row + admin-audit-detail + admin-audit-detail-fields dl + admin-audit-detail-change pre) + CSV export `<a id="auditExportCsvBtn">` (hide 기본). cache-bust `v=20260518-shell-grid-rows` → `v=20260519-audit-tab` (styles + admin.js).
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.js` — `PERMISSION_GROUP_ORDER` 에 audit 추가, `PERMISSION_GROUP_LABELS.audit="감사"`. `ADMIN_PERMISSION_SECTIONS.manage.groups` 에 audit 추가. switchTab("audits") 첫 진입 시 loadAuditList() 트리거. adminState.audit state (items / selectedId / nextCursor / scope / loading / initialized / filters). `_auditEscapeHtml` / `_auditFormatDt` / `_readAuditFilters` / `_clearAuditFilters` / `loadAuditList(append)` / `renderAuditList()` / `renderAuditDetail(id)` / `attachAuditFilterHandlers()` 함수 신설. CSV button gate = `audit.export` permission. tab 자체 hide gate = `audit.read.own || audit.read.any`. cursor pagination via "더 불러오기" button + Enter 키 apply.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — audit pane styles 10+ class 추가 (`.admin-audit-filter`, `.admin-audit-row` + 변형, `.admin-audit-detail-*`, `.admin-list-scope`, `.admin-audit-pagination`).
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js` — `PERMISSION_GROUP_ORDER` 에 audit 추가, `PERMISSION_GROUP_LABELS.audit="감사"`. `WORK_SCREEN_PERMISSION_SECTIONS.manage.groups` 에 audit 추가 (작업 화면 placeholder).
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust `styles.css?v=20260519-chat-pane-flex` → `v=20260519-audit-tab` + `app.js?v=20260519-pending-entries` → `v=20260519-audit-tab`.
- Verification: `node --check admin.js && node --check app.js` PASS. backend 의 `/api/admin/audits*` 5 endpoint (Phase A4) 호출. ChangeJson 의 `<pre>` 영역은 `_auditEscapeHtml` 로 XSS 차단 (TASK-0058 share.html `<pre>` 패턴 답습). CSV gate / tab visibility gate 가 `adminState.me.permissions[<code>]` truthy 검사.
- Risks: 작업 화면의 audit 그룹 placeholder 가 본인 `audit.read.own` 권한이라도 작업 화면에서 실 audit 진입점 부재 (admin 콘솔로 안내) — Phase E 별도 UX cycle 에서 작업 화면 audit drawer 검토 가능. 시간 정렬 `_auditFormatDt` 가 toLocaleString (browser timezone) — server OccurredAt UTC 와 mismatch 가능, 의도된 UX (사용자 local TZ).
- Trace: REQ-20260519-0001 → TASK-0073 Phase C → CHG-20260519-0024 → REV-20260519-0020. CONVENTIONS.md §10.6 audit group section 배치 lock-in.

## CHG-20260519-0023
- Date: 2026-05-19
- Summary: TASK-0073 Phase B (REQ-20260519-0001, **Critical** §12.3) — 3 test 파일 신설. dispatcher / RBAC / migration 의 핵심 행위 HTTP smoke 검증. 실 실행은 컨테이너 가동 + admin/operator/sales 자격 필요 — Phase E 사용자 위임 (본 cycle 의 plan 본문 명시: "환경 미비 시 test 작성만 + 실행은 Phase E 에 위임").
- Files:
  - `repo/unit/feature-0003-agent-web-ui/tests/test_audit_dispatcher.py` — 신설. 7 시나리오 (D1~D7). HTTP smoke 4 (D1~D4) + static / code review 3 (D5~D7). D7 은 `bin/verify-completion.sh check_11` 의 정적 symbol check 와 동일 grep — 컨테이너 무관 실행 가능.
  - `repo/unit/feature-0003-agent-web-ui/tests/test_audit_rbac.py` — 신설. 10 시나리오 (S1~S10). E1 B 의 핵심 (S3a admin password-reset target user 본인 audit 가시성) + E4 (S9 anonymous share view + S10 actor_type=anonymous filter) + 404 byte-equal metadata leak 차단 (S4) + CSV export (S6) + purge dry_run (S7) + prod fail-closed (S8, manual).
  - `repo/unit/feature-0003-agent-web-ui/tests/test_audit_migration.py` — 신설. 3 시나리오 (M1 legacy → new migration visible / M2 idempotent / M3 dual write coverage). mysql client 직접 사용 — DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / MEMORY_DB env 필수.
- Verification: 3 file 모두 `python3 -m py_compile` PASS. test_search_rbac.py (TASK-0072 Phase B) 와 동일 urllib + login + Set-Cookie 패턴 답습. 컨테이너 가동 후 사용자가 `python3 tests/test_audit_*.py --base-url http://localhost:18080 --admin-user admin --admin-pass <pw>` 로 실행 가능.
- Risks: HTTP smoke 가 컨테이너 환경 의존 — admin/operator/sales 비밀번호 미보유 시 partial PASS. dispatcher 단위 검증이 실제 dispatcher import 직접 호출 X (PYTHONPATH 의존 회피) — `record_audit_event` symbol 부재 시 D7 static check 가 cover. M1 의 legacy INSERT 가 직접 SQL — `make ask` 우회 시 docker exec mysql 또는 host mysql client 필요.
- Trace: REQ-20260519-0001 → TASK-0073 Phase B → CHG-20260519-0023 → REV-20260519-0019.

## CHG-20260519-0022
- Date: 2026-05-19
- Summary: TASK-0073 Phase A6 (REQ-20260519-0001, **Critical** §12.3) — user 5 endpoint fail-open best-effort audit hook + anonymous share view (ActorType='anonymous'). `_audit_user_action` helper 신설 (TASK-0072 `_log_search_activity` 패턴 답습). Eng review E4 — ActorType column 활용 anonymous filter.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - 신규 helper `_audit_user_action(conn, request, account, *, action, resource_type, resource_id, request_ctx, target_account_id, actor_type='account')` — user endpoint fail-open audit. try/except wrap → 실패 시 conn.rollback() + stderr log + main flow 계속. `/api/ask` long-running LLM + share view anonymous flow 전용.
    - POST /api/ask — `conversation.ask` hook (conv_id 결정 직후, LLM 호출 전, ChangeJson `{conversation_id, model, lazy_create, prompt_length}`).
    - POST /api/conversations/{cid}/share — `conversation.share.create` hook (token 발급 직후, token full X — `token_prefix[:8]` 만, scope_mode + anchor_message_id + share_id).
    - DELETE /api/share/{share_id} — `conversation.share.revoke` hook (UPDATE rowcount 직후, already_revoked flag + conversation_id + share_id).
    - GET /api/public/share/{token} — `share.public.view` hook (anonymous! viewer None 이면 ActorType='anonymous' + ActorAccountId NULL, viewer 있으면 'account'). ChangeJson `{share_id, token_prefix[:8], view_count_after, remote_addr}`. Eng review E4 정합.
    - POST /api/public/share/{token}/fork — `share.fork` hook (fork 결과 직후, source_share_id + source_token_prefix + new_conversation_id).
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. _audit_user_action helper 가 5 endpoint 모두에서 호출. _log_search_activity (Phase A2 mirror) 까지 합쳐 user audit path 전부 wire-up 완료. dispatcher 의 best-effort 실패 시 stderr `[TASK-0073 Phase A6] <action> audit failed: <exc>` log. plan 의 "user 4 endpoint" 는 실제로는 5 endpoint — `/api/conversations` search snippet 가 TASK-0072 `_log_search_activity` 의 자연 wrap (Phase A2 dual write), 본 phase 의 명시 5 endpoint = ask + share create + share revoke + share view (anonymous) + share fork.
- Risks: `share.public.view` 의 `viewer = _optional_account(request, conn)` 는 cookie 없으면 None 반환. ActorType='anonymous' 분기 정합. dispatcher 의 actor_type 화이트리스트 (`account` / `anonymous` / `system`) 검증 — 잘못된 값 → `account` 로 normalize. token_prefix 가 8 char 만 — full token 64 char 의 1/8 노출, PII 침해 면적 최소.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A6 → CHG-20260519-0022 → REV-20260519-0018. Eng review E4 (anonymous ActorType) lock-in + Codex C11 (TASK-0058 share anonymous path 누락) lock-in.

## CHG-20260519-0021
- Date: 2026-05-19
- Summary: TASK-0073 Phase A5 (REQ-20260519-0001, **Critical** §12.3) — admin 11 mutation endpoint Same tx audit hook + ActionCode-specific `build_audit_change_json()` builder dispatch + `_audit_admin_mutation()` helper. Codex outside voice C6 minimum-fix (raw 검증 X, builder allowlist). Eng review E5 (product delete cascade lock 순서) + E6 (explicit dispatcher, decorator 거부).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - 신규 helper `_audit_pick_fields(source, fields)` — 화이트리스트 field 만 extract.
    - 신규 helper `_audit_redact_sensitive(d)` — password_hash / token / api_key 등 sensitive field 값을 `<redacted>` 로 shallow 치환.
    - 신규 `build_audit_change_json(*, action, before, after, request_ctx)` dispatcher — 16 ActionCode (admin 11 + user 5) 의 ChangeJson 화이트리스트 빌더. unknown action 은 ValueError raise (Codex C6 explicit allowlist).
    - 신규 `_audit_admin_mutation(conn, request, actor, *, action, resource_type, resource_id, before, after, request_ctx, target_account_id)` helper — builder dispatch + record_audit_event 호출. caller 가 commit 직전 1 line 으로 호출.
    - 11 admin mutation endpoint 의 Same tx audit hook 적용:
      1. PATCH /api/admin/accounts/{id} — admin.account.update (before=target, after=updated, target_account_id=account_id)
      2. POST /api/admin/accounts/{id}/password-reset — admin.account.password-reset (PasswordHash 명시 redact)
      3. DELETE /api/admin/accounts/{id} — admin.account.delete
      4. POST /api/admin/roles — admin.role.create
      5. PATCH /api/admin/roles/{id} — admin.role.update
      6. DELETE /api/admin/roles/{id} — admin.role.delete
      7. POST /api/admin/products — admin.product.create (autocommit tx 뒤에 별 tx hook)
      8. PATCH /api/admin/products/{id} — admin.product.update
      9. DELETE /api/admin/products/{id} — admin.product.delete (E5 cascade lock 순서 — system_prompts → product_databases → role_permissions → account_permission_overrides → permissions → products → audit)
      10. PUT /api/admin/products/{id}/databases — admin.product.databases.update (before-state schemas 캡처 후 hook)
      11. PUT /api/admin/system-prompts — admin.system_prompt.update (before/after content_len + content_preview_after 120 char, full content 미포함)
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. record_audit_event 호출 19 회 (= 11 admin endpoint hook + 2 purge self-audit + 1 _log_search_activity mirror + helper 정의 5 etc.). 각 hook 의 try/except 가 audit 실패 시 conn.rollback() 후 500 응답 (Same tx fail-safe). plan 의 "13" 은 elastic 표현 — 11 endpoint 가 admin mutation 전부 (TASK-0073 plan E5 의 cascade lock 순서가 admin.product.delete 1 개 endpoint).
- Risks: PATCH /api/admin/accounts/{id} 의 conn close() 위치가 audit hook 뒤로 이동 — 기존 flow 가 _set_account_overrides + revoke 세션 후 close. audit hook 도 같은 conn 사용. POST /api/admin/products 의 autocommit=False/True toggle 가 audit hook 안 영향 — finally 의 `conn.autocommit = True` 다음에 audit hook 이 추가 INSERT (auto-commit 모드 안전). PUT /api/admin/products/{id}/databases 의 before-state 캡처가 DELETE 직전에 — 추가 SELECT row.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A5 → CHG-20260519-0021 → REV-20260519-0017. Codex C6 (builder allowlist) + Eng review E5 (cascade lock 순서) + E6 (explicit dispatcher) lock-in.

## CHG-20260519-0020
- Date: 2026-05-19
- Summary: TASK-0073 Phase A4 (REQ-20260519-0001, **Critical** §12.3) — 5 audit read endpoint + 1 chunked PK purge endpoint. `.own` SQL filter = `ActorAccountId OR TargetAccountId` (Eng review E1) + 404 byte-equal metadata leak 차단 + CSV 50k hard cap + chunked purge w/ idempotency_key + start/complete self-audit + 30s deadline.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - helper functions 신설 — `_audit_row_to_dict(row)`, `_audit_build_self_filter_sql(account_id)`, `_audit_resolve_read_scope(actor)`, `_audit_parse_filter_params(request)`, `_audit_compose_where(*, scope, account_id, params, cursor_id)`, `_audit_parse_cursor(cursor)`, `_audit_clamped_limit(raw)`. defaults: `_AUDIT_LIST_DEFAULT_LIMIT=100`, `_AUDIT_LIST_MAX_LIMIT=500`, `_AUDIT_PURGE_CHUNK_SIZE=1000`, `_AUDIT_PURGE_MAX_RUNTIME_SEC=30`.
    - `GET /api/admin/audits` — list w/ filter (action_code / resource_type / actor_account_id / actor_type / from_at / to_at / q / cursor / limit). `.own` filter E1 (Actor OR Target). LIMIT N+1 → next_cursor 판정. Response `{items, next_cursor, scope}`.
    - `GET /api/admin/audits/{event_id}` — detail. `.own` 보유자는 본인 actor/target 일 때만, 권한 부족 무조건 404 (byte-equal).
    - `GET /api/admin/audits/export.csv` — `audit.export` gate. hard cap 50k row. `csv` 모듈 + `io.StringIO` + `PlainTextResponse` w/ Content-Disposition.
    - `GET /api/admin/audits/actors` — distinct actor facet. `.own` = 본인 1건만 (enumeration 차단). `.any` = WebAccounts JOIN.
    - `GET /api/admin/audits/resources` — distinct resource_type facet. `.own` 분기 SQL.
    - `POST /api/admin/audits/purge` — chunked PK purge. `audit.purge` gate. dry_run=true → COUNT(*) 만 반환. 실 삭제 — chunk 1000 row 별 tx (LRT 회피). start/complete self-audit 2건. idempotency_key = sha256(cutoff + started_at_minute)[:32]. max runtime 30s (deadline 초과 시 partial — 다음 호출 cursor 재시작).
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. endpoint 6개 신설 (5 GET + 1 POST). 사용한 helper 모두 file 내 정의. `_build_actor_from_request` (Phase A1) 재사용. `record_audit_event` (Phase A1) purge start/complete 호출.
- Risks: `.own` SQL filter 가 `ActorAccountId IS NULL` row 도 OR 분기로 `TargetAccountId=:self` 매칭 가능 — anonymous share view 시 본인 share 의 viewer 가 본인 audit 에 보이는 경우 (E4 정합, 의도). CSV 50k cap 가 large fleet 에서 모자랄 수 있음 — 본 cycle 의 hard cap, 별 cycle 에서 streaming export 검토. purge max runtime 30s 가 LLM 으로 인한 connection stall 회피 — partial purge 시 다음 호출 cursor 자연 재시작 (cutoff 이전 row 가 남아 있음).
- Trace: REQ-20260519-0001 → TASK-0073 Phase A4 → CHG-20260519-0020 → REV-20260519-0016. Eng review E1 (Actor OR Target self filter) + E8 (chunked purge Python 의사코드).

## CHG-20260519-0019
- Date: 2026-05-19
- Summary: TASK-0073 Phase A3 (REQ-20260519-0001, **Critical** §12.3) — RBAC catalog audit 4건 + permission group `audit` 신규 + admin/operator/sales/dba/pending 5 role 자동 grant catchup. Codex outside voice C8/C9/C10 lock-in (`.own/.any` 정합 + dba seed/catchup 보강 + permission group misc fallback 차단). Eng review E9 — dba 누락 보강.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - `PERMISSION_DEFINITIONS` 끝부분 (system_prompt.manage.role.any 다음) 에 4 entry 추가 — `audit.read.own` (모든 role), `audit.read.any` (admin/dba), `audit.export` (admin/dba), `audit.purge` (admin only). 모두 `group="audit"` (신규 permission group). 기존 ~40 → 44 codes.
    - `SEED_ROLE_DEFINITIONS` pending/operator/sales role `permissions` set 에 `audit.read.own` 명시 추가. admin 은 `set(PERMISSION_CODES)` 라 자동 모두 포함.
    - `_ensure_seed_roles` admin catchup (line ~1486) 의 명시 code list 에 `audit.read.own/.any/.export/.purge` 4 code 추가.
    - operator/sales catchup (line ~1511) 의 `catchup_codes` tuple 에 `audit.read.own` 추가.
    - 신규 dba role catchup loop — `SELECT Id FROM WebRoles WHERE RoleKey='dba' LIMIT 1` 검색 + 존재 시 `audit.read.own/.any/.export` 3 code INSERT IGNORE (.purge 는 admin only). Eng review E9 lock-in.
    - 신규 pending role catchup loop — `audit.read.own` INSERT IGNORE (SEED_ROLE_DEFINITIONS 와 dual safety).
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. `_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞에서 hydrate 되므로 (TASK-0063 회귀 fix 답습) 신규 4 permission id 가 catchup INSERT 시 valid 보장. frontend admin.js / app.js 의 `PERMISSION_GROUP_ORDER` 갱신은 Phase C scope (본 commit 의 backend 만 RBAC enforce 가능).
- Risks: dba role 이 DB 에 없는 환경은 catchup loop graceful skip. 이미 audit 권한 보유한 admin (e.g. 수동 grant) 은 INSERT IGNORE 라 duplicate 회피. `set(PERMISSION_CODES)` 가 SEED admin 권한을 매 catchup 마다 재계산 → 정적 (module load 시 fixed) 이라 안전.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A3 → CHG-20260519-0019 → REV-20260519-0015. Codex C8/C9/C10 + Eng review E9 lock-in.

## CHG-20260519-0018
- Date: 2026-05-19
- Summary: TASK-0073 Phase A2 (REQ-20260519-0001, **Critical** §12.3) — `WebAccountActivity` (TASK-0072) 기존 row 흡수 + migration helper + `_log_search_activity` dual write wrap. Codex outside voice C2 minimum-fix (legacy table 발견 + transparent wrap). 기존 table 자체는 본 cycle DROP 안 함 (별 cycle backup 후 DROP).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - `_log_search_activity()` 본문 변경 — signature 무변경 (6 keyword args 보존, caller 변경 0). 본문은 dual write: (1) 기존 `WebAccountActivity` INSERT + commit, (2) 새 `record_audit_event(conn, actor={account_id, actor_type:'account'}, action, resource_type='conversation', resource_id=target_owner_id, change_json={query_hash, matched_count, _legacy_source:'WebAccountActivity'}, target_account_id=target_owner_id)` mirror best-effort. 두 source 모두 실패해도 main flow 차단 X.
    - 신규 `_migrate_web_account_activity_to_audit(conn)` helper — 기존 row → WebAuditEvents transform. SQL: `INSERT INTO WebAuditEvents (...) SELECT waa.AccountId, NULL, 'account', waa.TargetOwnerId, NULL, waa.Action, 'conversation', CAST(waa.TargetOwnerId AS CHAR), JSON_OBJECT(...), NULL, NULL, NULL, CONCAT('account-activity:', waa.Id), waa.CreatedAt FROM WebAccountActivity waa WHERE NOT EXISTS (SELECT 1 FROM WebAuditEvents wae WHERE wae.RequestId = CONCAT('account-activity:', waa.Id))`. RequestId marker 로 idempotent. legacy table 부재 시 SHOW TABLES check 후 graceful skip. 성공 시 stderr `migrated N WebAccountActivity row(s) → WebAuditEvents` log.
    - `_ensure_seed_catchup()` 에 `_migrate_web_account_activity_to_audit(conn)` 호출 추가 (Phase A0 `_ensure_web_audit_events_schema` 직후). fast path.
    - `_ensure_web_tables()` slow path 에도 동일 migration 호출 추가 — `WebRoles CREATE TABLE` 직전.
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. dispatcher (Phase A1) 의 `record_audit_event` 호출이 `_log_search_activity` mirror 에서 첫 실 사용 — INSERT path 의 정상 동작 확인 본 cycle 의 `make web` 재배포 + browser smoke (Phase E) 에서 검증.
- Risks: dual write 시 동일 audit event 가 두 row (legacy + new) — search 통계 / billing 의 double count 위험. 본 cycle 에서 admin UI 는 WebAuditEvents 만 조회 (Phase C) 라 frontend 영향 0. 별 cycle DROP table 시 분리. migration helper 의 `JSON_OBJECT` 가 MySQL 8.0 한정 — repo 의 docker-compose.yml MySQL 8.0 가정 (§15.4) 정합.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A2 → CHG-20260519-0018 → REV-20260519-0014. Codex C2 (WebAccountActivity 발견) 최소 fix.

## CHG-20260519-0017
- Date: 2026-05-19
- Summary: TASK-0073 Phase A1 (REQ-20260519-0001, **Critical** §12.3) — audit dispatcher `record_audit_event()` + `AGENT_AUDIT_ENABLED` prod startup fail-closed gate + verify-completion check_11_audit_dispatcher SPOF guard. CEO review · Codex outside voice C5 minimum-fix · Eng review E6 (explicit dispatcher) / E7 (SPOF mitigation) 흡수.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - 신규 env constants (line 67 직후) — `AGENT_AUDIT_ENABLED` (bool, default 1), `AGENT_MODE` (str, lower-cased), `_AUDIT_IS_PROD_MODE` (bool — AGENT_MODE not in dev/test).
    - 신규 `_enforce_audit_prod_gate()` 함수 + module-load 시점 즉시 호출 — prod (AGENT_MODE != dev/test) 에서 AGENT_AUDIT_ENABLED=1 가 아니면 `sys.exit(1)` + stderr `[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1 (AGENT_MODE=...; TASK-0073 Phase A1)`. Codex C5 — flag bypass surface 차단.
    - 신규 `record_audit_event(conn, *, actor, action, resource_type, resource_id, change_json, masked_fields=None, target_account_id=None)` dispatcher (Phase A0 `_ensure_web_audit_events_schema` 뒤). AGENT_AUDIT_ENABLED=0 (dev/test only) 일 때 silent no-op. actor=None / actor_type='system' 시 ActorAccountId/ActorRoleId NULL 보정 (E4). admin caller = same conn / tx 호출 → 실패 bubble up (caller rollback). user caller = best-effort try/except wrapper → 실패 stderr only. dispatcher 자체는 commit/rollback 안 함 (E6 explicit).
    - 신규 helper `_build_actor_from_request(request, account, *, actor_type='account')` — caller 가 actor dict 조립 시 사용 (remote_addr / user_agent / session_id 자동 캡처).
  - `repo/bin/verify-completion.sh`
    - 신규 `check_11_audit_dispatcher(fdir)` 함수 — feature-0003-agent-web-ui scope 일 때 src/app.py 안 `record_audit_event(`, `AGENT_AUDIT_ENABLED`, `_enforce_audit_prod_gate` 3 symbol 존재 강제. 다른 feature scope 는 silent PASS. Eng review E7 SPOF mitigation.
    - main() 호출 추가 — check_2~9 다음 line 에 `check_11_audit_dispatcher "$fdir"` 호출 + failed counter 반영. PASS / FAIL 메시지 "8 checks" → "9 checks (7 pilot + worktree binding + audit dispatcher)" 로 갱신.
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. `bash -n bin/verify-completion.sh` PASS. Phase A0 schema 변경 0 — dispatcher 가 기존 `WebAuditEvents` INSERT 패턴 사용. RBAC / endpoint / 데이터 변경 0 (dispatcher 는 caller wire-up 전이라 INSERT row 실측 0). 본 commit 은 인프라 layer 만.
- Risks: module-load time `sys.exit` 가 tests 의 import 차단 가능 → Phase B tests 에서 `AGENT_MODE=test` 환경변수 강제 (test runner 가 환경 set). dispatcher 가 commit/rollback 안 한다는 caller contract 가 강함 — admin endpoint 의 same-tx fail-safe 정합성에 의존, 추후 Phase A5 wire-up 시 transaction boundary 명확 표기.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A1 → CHG-20260519-0017 → REV-20260519-0013. CEO review 9 decision + Codex 14 findings + Eng review E6/E7 lock-in.

## CHG-20260519-0016
- Date: 2026-05-19
- Summary: TASK-0085 (REQ-20260519-0014, Minor §12.3) — lazy-create 사이드바 optimistic pending entry 도입. "+ 새 대화 송신 직후 다른 대화 전환 시 새 대화 entry 가 사이드바에서 잠시 사라지는" UX 회귀 fix + 사용자 의도 "작업 step 현황의 출력 위해" pending entry 클릭으로 컨텍스트 swap 지원.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - state 정의 (line 120~127) — `pendingConversationEntries: new Map()` field 추가. Map<sentinel, { sentinel, message, started_at, status }>. status: "in_flight" | "failed". multi-pending 지원 (TASK-0082 unique sentinel 정합).
    - `sendPrompt()` lazy-create 진입 (line 3596~3605) — `state.pendingConversationEntries.set(busyKey, {...})` + `renderConversationList()` 호출 → 사이드바 즉시 표시.
    - `sendPrompt()` success path (line 3685~3687) — closure 일치 여부와 무관하게 본 send 의 sentinel entry 만 `pendingConversationEntries.delete(busyKey)` (실 cid entry 는 `refreshWorkspace` 가 backend list refresh 로 등재 — optimistic 자연 swap).
    - `sendPrompt()` catch path (line 3705~3715) — 본 send 의 entry status="failed" set + `renderConversationList()` + 3 s 후 자동 delete. toast 안내와 함께 양방향 신호.
    - `renderConversationList()` 변경 (line 1209~1450) — `hasPending` 을 `hasDraftPending` (작성 중 placeholder) + `hasInFlightPending` (응답 대기 entries) 둘로 split. empty-state guard 도 둘 다 검사. 신규 `appendInFlightPendingItems()` 가 entries 를 started_at desc 정렬 후 each 표시 (라벨 = prompt 첫 60 자, meta = "응답 대기 중…" / "전송 실패", `is-pending-inflight` / `is-pending-failed` class, 활성 sentinel = `is-active`). failed entry 는 click 비활성, in_flight 는 `_switchToPendingConversationContext(entry)` 클릭 handler. `combinedPrepend` 가 own 그룹의 prepend 로 (1) in-flight entries (상단) + (2) 작성 중 placeholder (하단) 같이 표시.
    - `_switchToPendingConversationContext(entry)` helper 신설 (line 3100~3137) — pending entry 클릭 시 sentinel 컨텍스트로 swap. `stopProgressPolling({reset:false, abort:true})` + `state.activeConversationId=""` + `state.pendingNewConversation=true` + `state.pendingSentinel=entry.sentinel` + `messages=[]` + `pendingBubble` 도 entry metadata 기반 복원 (startedAt 이어짐 → elapsed timer 자연 진행). renderComposer / renderMessages / renderProgress / startElapsedTimer 호출. 응답 도착 시 sendPrompt 의 success path closure 일치 (`state.pendingSentinel === busyKey`) → 자동 `activeConversationId=newCid` + `startProgressPolling`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `app.js?v=20260519-unique-sentinel` → `app.js?v=20260519-pending-entries` cache-bust 토큰 갱신.
- Verification: `node --check app.js` PASS. backend / RBAC / endpoint / audit / DB 무변경. smoke 5 종 (송신 후 전환 / 응답 도착 / catch / click swap / multi-pending).
- Risks: pendingBubble swap 시 step 정보 손실 (cid 전 polling 불가) / closure mismatch 시 cid binding skip / 3 s failed timer / grapheme-safe slice 미적용 / legacy appendPendingItem 보존.
- Trace: REQ-20260519-0014 → TASK-0085 → CHG-20260519-0016 → REV-20260519-0012. TASK-0048 lazy-create + TASK-0082 unique sentinel 의 자연 연속.

## CHG-20260519-0015
- Date: 2026-05-19
- Summary: TASK-0084 (REQ-20260519-0013, Minor §12.3) — D2Coding 우선 monospace stack 으로 전역 통일 재시도. 사용자 후속 요청 "D2Coding 폰트를 우선해줄 수 있을까요?" + AskUserQuestion 으로 적용 범위 확인 (본문 + 코드 모두). CHG-0014 의 한글 친화 sans-serif stack 을 폐기하고, CHG-0013 의 monospace 통일 의도를 D2Coding (한글 monospace 가독성 검증된 NAVER 폰트) 우선으로 부활. `--font` 와 `--mono` 두 토큰을 다시 동일 D2Coding 우선 monospace stack 으로 통합. 사용자가 D2Coding 미설치 환경에서 fallback chain 의 Cascadia Code / SFMono-Regular / Consolas / Noto Sans Mono CJK KR / system monospace 로 자동 fallback.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - line 33~35 (`:root` Typography 토큰) — CHG-0014 의 sans-serif stack 폐기. 새 stack: `--mono: "D2Coding", "D2Coding ligature", "Cascadia Code", "SFMono-Regular", Consolas, "Noto Sans Mono CJK KR", ui-monospace, Menlo, monospace` + `--font: var(--mono)` 로 통합. body cascade (`font-family: var(--font)` line 65 + `font: inherit` line 72~73) 가 그대로 작동해 작업·관리 화면 전역에 D2Coding 우선 monospace 적용. var(--mono) 명시 사용처 (코드/로그 영역) 도 동일하므로 영향 없음.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — line 7 `styles.css?v=20260519-cjk-readable` → `styles.css?v=20260519-d2coding-mono` cache-bust 토큰 갱신.
- Verification:
  - CSS syntax 단순 토큰 교체. JS / Python 변경 없음.
  - cascade 검증: body / button / input / textarea / select 의 기존 font cascade 그대로 작동.
  - smoke (사용자 직접 확인 권장): ①작업 화면 (`/`) 진입 → D2Coding 설치 시 한글·영문 모두 D2Coding 등폭으로 렌더, 미설치 시 Cascadia Code (영문 등폭) + system monospace (한글 fallback). ②관리 화면 (`/admin`) 동일. ③한글 메시지·이름·테이블명에서 글자 폭 정합. ④`var(--mono)` 명시 영역도 동일 stack — 변경 영향 없음.
  - index.html cache-bust 미갱신 (CHG-0014 와 동일 — 사용자 main wt revert 의도 존중). 사용자가 작업 화면 진입 시 Ctrl+Shift+R 권장.
- Risks:
  - **D2Coding 미설치 환경**: 사용자가 D2Coding 폰트를 시스템에 설치하지 않은 경우 첫 fallback `Cascadia Code` (영문) + system monospace (한글) 로 렌더. 영문은 등폭 OK 이나 한글은 system monospace 가 깔려 있어야 등폭. 사용자가 D2Coding 설치 (NAVER 공식 https://github.com/naver/d2codingfont) 후 재확인 권장.
  - **D2Coding 가독성 보고 가능성**: CHG-0014 에서 사용자가 monospace 가독성 호소했었음. D2Coding 은 한글 monospace 중 가독성 가장 좋은 평가지만 일반 본문 sans-serif 보다는 가독성 trade-off 있음. 사용자가 본 stack 검증 후 추가 조정 요청 시 별 cycle (예: 본문은 sans-serif + var(--mono) 사용처만 D2Coding 으로 분리).
  - **D2Coding ligature 변형**: stack 두 번째 entry `D2Coding ligature` 는 D2Coding 의 ligature 지원 변형 — `==`, `=>`, `->` 같은 합자 표시. 시스템에 설치 시 자동 적용. 미설치 시 무영향.
  - **CHG-0013 + CHG-0014 + CHG-0015 trace**: append-only 정책 (§5.2). 3 차례의 monospace ↔ sans-serif ↔ monospace 진동이 정직하게 기록. CHG-0013 (monospace 시도) → CHG-0014 (sans-serif 환원, 가독성) → CHG-0015 (D2Coding 우선 monospace 부활, 가독성 + 정렬 양립).
  - **share.css 무변경**: 공유 페이지 별도 stylesheet — 영향 없음.
- Trace: REQ-20260519-0013 → TASK-0084 → CHG-0015 → REV-0011. AC-0184 (전역 monospace) + AC-0185 (--mono 사용처 monospace) 모두 본 cycle 에서 단일 stack 통합으로 의미 합쳐짐. AC-0186 (admin.html cache-bust) 갱신. 새 AC-0187 등록 (D2Coding 우선).

## CHG-20260519-0014
- Date: 2026-05-19
- Summary: TASK-0083 followup (REQ-20260519-0012, Minor §12.3) — CHG-0013 의 monospace 통합 방향 폐기 + 한글 가독성 우선 system-ui sans-serif stack 으로 재설정. 사용자 추가 보고: "한글 기준으로 눈이 아픕니다… 한글 기준으로 가장 범용성있는 폰트로 다시 설정해주세요". CHG-0013 의 `--font: var(--mono)` 통합을 해제하고 `--font` 를 OS native 한글 폰트 자동 fallback stack 으로 갱신. `--mono` 는 원래 stack 복원 (코드/로그 영역만 적용). worktree `ai/claude/task-0083` 에서 진행 — 다른 AI 작업자의 a7b7ded commit 의 docs 변경 (CHG-0013/REV-0009 흡수) 과 격리된 src commit.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - line 33~35 (`:root` Typography 토큰) — CHG-0013 의 `--mono` stack (한글 monospace fallback 포함) + `--font: var(--mono)` 통합 해제. 새 stack: `--font: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "맑은 고딕", "Helvetica Neue", Arial, sans-serif`. macOS 는 `-apple-system → Apple SD Gothic Neo`, Windows 는 `Segoe UI → 맑은 고딕`, Linux/ChromeOS 는 `system-ui` 또는 Noto Sans CJK 자동 fallback. `--mono` 는 CHG-0013 이전 stack 복원: `"Cascadia Code", "SFMono-Regular", Consolas, monospace`.
    - 다른 `font-family` 출현 위치 무변경 — `var(--mono)` 명시 사용처 (line 1069, 1082, 1186, 1379, 2542) 는 monospace 유지, hardcoded `ui-monospace, ...` (line 2216) 와 `monospace` (line 3846) 도 그대로. `var(--font)` 사용처 (body line 65 등) 만 sans-serif 로 환원.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — line 7 `styles.css?v=20260518-shell-grid-rows` → `styles.css?v=20260519-cjk-readable` cache-bust 토큰 갱신.
- Verification:
  - CSS syntax 단순 토큰 교체. JS / Python 변경 없음.
  - cascade 검증: `body { font-family: var(--font); }` (line 65) + `button/input/textarea/select { font: inherit; }` (line 72~73) 가 sans-serif 적용. `var(--mono)` 사용처 (코드/로그 영역) 는 monospace 유지.
  - smoke (사용자 직접 확인 권장): ①작업 화면 (`/`) 메시지 본문 / sidebar / topbar / composer / popover 텍스트가 sans-serif 로 자연스러운 한글 표시. ②관리 화면 (`/admin`) list / detail / form 텍스트가 sans-serif. ③`var(--mono)` 명시 영역 (예: result table, log view, code snippet) 은 여전히 monospace.
  - index.html cache-bust 미갱신 (사용자가 main wt 에서 직접 revert 한 의도 존중) — 사용자가 작업 화면 진입 시 styles.css 가 캐시되어 새 stack 이 즉시 안 보일 수 있음. Ctrl+Shift+R (hard refresh) 권장.
- Risks:
  - **index.html cache-bust 미갱신**: 사용자의 main wt revert 흔적 (system reminder 명시) 을 존중하기 위해 본 cycle 에서 skip. 사용자가 hard refresh 또는 캐시 무시 모드로 접근해야 새 stack 적용 인지. 사용자가 index.html cache-bust 도 갱신 요청 시 별 cycle 1 line.
  - **system-ui 의미 ambiguity**: 일부 구형 브라우저 (특히 모바일 Safari 12 이하) 가 `system-ui` 를 인식 못 함. fallback `-apple-system` / `BlinkMacSystemFont` 로 안전. 본 stack 의 광범위 fallback 으로 실용적 risk 0.
  - **Pretendard 등 별도 한글 모던 폰트 미포함**: 시스템 native 폰트 우선 — Pretendard 같은 비표준 폰트는 stack 에 포함 안 함. 사용자가 Pretendard 우선 요청 시 첫 위치에 추가 또는 WebFont 도입 (별 cycle).
  - **CHG-0013 design intent 회수**: CHG-0013 의 "전역 등폭" intent 가 본 cycle 로 사실상 폐기 — 사용자 feedback 의 가독성 우선. CHG-0013 entry 는 append-only 이므로 그대로 유지하되, 본 entry 가 후속 정정임을 명시.
  - **share.css 무변경**: share.html (공유 페이지) 은 별도 stylesheet 사용 — typography 변경 영향 없음. 별도 cycle 필요 시 추가 작업.
- Trace: REQ-20260519-0012 → TASK-0083 followup → CHG-0013 (monospace, a7b7ded 의 docs / 본 cycle 의 worktree src) → CHG-0014 (sans-serif 환원). AC-0184 (전역 monospace 통일) 의 design intent 는 CHG-0014 로 부분 해제 — "var(--font) 영역은 sans-serif, var(--mono) 영역은 monospace 유지" 로 재정의. 새 AC-0185 등록.

## CHG-20260519-0013
- Date: 2026-05-19
- Summary: TASK-0083 (REQ-20260519-0011, Minor §12.3) — web UI 전역 폰트를 monospace 로 통일. `:root` 의 `--font` 토큰을 `--mono` 와 같은 stack 으로 묶어 작업 화면 / 관리 화면의 모든 text 를 등폭 글꼴로 렌더. 영문은 Cascadia Code / SFMono-Regular / Consolas, 한글은 D2Coding / Noto Sans Mono CJK KR fallback. 사용자 요청 — "문자열 길이와 실제 표현되는 위치가 정합" 을 위한 등폭 정렬 보장.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - line 33~36 (`:root` Typography 토큰 정의) — `--font: "Segoe UI", "Noto Sans KR", -apple-system, BlinkMacSystemFont, sans-serif` 제거 → `--mono` stack 을 한글 monospace fallback 포함으로 확장 (`"Cascadia Code", "SFMono-Regular", Consolas, "D2Coding", "Noto Sans Mono CJK KR", ui-monospace, Menlo, monospace`) + `--font: var(--mono)` 로 참조 통합. 기존 `body { font-family: var(--font); }` (line 65) + `button/input/textarea/select { font: inherit; }` (line 72~73) cascade 가 그대로 작동해 전역 적용.
    - 다른 `font-family` 출현 위치 (line 1069 `var(--mono)`, line 1082 `var(--mono)`, line 1186 `var(--mono)`, line 1379 `var(--mono)`, line 1904 `var(--font-mono, ui-monospace, monospace)` 별도 변수, line 2216 hardcoded `ui-monospace, SFMono-Regular, Menlo, monospace`, line 2542 `var(--mono)`, line 3846 `monospace`, line 4026/4170/4190/4217/4233 `inherit`) 무변경 — 기존이 이미 monospace 또는 inherit 이라 영향 없음.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — line 7 `styles.css?v=20260519-chat-pane-flex` → `styles.css?v=20260519-mono-font-stack` cache-bust 토큰 갱신.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — line 7 `styles.css?v=20260518-shell-grid-rows` → `styles.css?v=20260519-mono-font-stack` cache-bust 토큰 갱신.
- Verification:
  - CSS syntax 단순 토큰 교체. JS / Python AST 변경 없음.
  - `var(--font)` / `var(--mono)` 참조 자리 의미 무손상 — 두 토큰이 동일한 값으로 통합되어 cascade 결과 동일 (등폭) 보장.
  - smoke (사용자 직접 확인 권장): ①작업 화면 (`/`) 진입 → sidebar / topbar / composer / message bubble / popover 의 모든 텍스트가 monospace 로 표시. ②관리 화면 (`/admin`) 진입 → list / detail / bulk toolbar / form 의 모든 텍스트가 monospace 로 표시. ③한글 메시지·이름·테이블명에서 글자 폭 정합 (system 에 D2Coding / Noto Sans Mono CJK KR 가 깔려 있을 때). ④`share.html` (별도 `share.css`) 은 본 변경 영향 없음 — 의도.
- Risks:
  - **한글 monospace 시스템 의존**: 시스템에 D2Coding / Noto Sans Mono CJK KR 가 설치되지 않은 환경 (예: 기본 Windows / macOS 사용자) 은 fallback chain 의 `ui-monospace` 또는 `monospace` 가 system default monospace 를 사용하는데, 일반적으로 한글은 system default proportional font (예: 맑은 고딕 / Apple SD Gothic Neo) 로 표시되어 한글만 등폭이 깨질 수 있음. CSS 단독으로 강제 불가 — system 폰트 설치 안내 또는 WebFont 도입은 별 cycle.
  - **읽기 가독성 trade-off**: monospace 는 한글·영문 혼합 본문에서 가독성이 일반 sans-serif 보다 낮을 수 있음. 사용자가 명시 요청한 "문자열 길이 / 위치 정합" 우선이라 trade-off 수용. 사용자가 추후 일부 영역 (예: navigation, button label) 만 sans-serif 로 환원 요청 시 별 cycle.
  - **`--font` 토큰의 의미 분리 소실**: 기존에 proportional / monospace 두 토큰이 분리되어 있던 design intent 가 사라짐. `var(--font)` 참조 자리에서 향후 다시 proportional 로 돌리려면 단일 line 변경 (line 35 `--font: var(--mono)` → 별도 stack) 으로 회복 가능 — 미래 cycle 옵션 보존.
  - **share.css (share.html 전용) 미변경**: 공유 페이지의 폰트는 본 cycle 범위 외. 사용자가 명시한 "프로젝트로 실행되는 웹브라우저" 가 작업·관리 화면을 가리킨다고 해석. share.html 도 monospace 통일 요청 시 별 cycle 1 line 추가.
- Trace: REQ-20260519-0011 → TASK-0083 → CHG-20260519-0013 → REV-20260519-0009. AC-0184 (전역 monospace 통일) 신규 등록. 기존 AC 회귀 없음 (cascade 동일).

## CHG-20260519-0012
- Date: 2026-05-19
- Summary: TASK-0082 (REQ-20260519-0010, Minor §12.3) — lazy-create unique sentinel design 도입. TASK-0081 followup. 글로벌 단일 sentinel 의 컨텍스트 충돌로 첫 in-flight 중 + 새 대화 클릭 시 input 활성화 안 되던 회귀 근본 fix.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - state 정의 (line 115 부근) — `pendingSentinel: null` field 추가. 각 lazy-create 진입의 unique sentinel 보관.
    - 상수 정의 (line 156 부근) — `PENDING_CONV_SENTINEL` 글로벌 별칭 유지 (legacy 호환) + `PENDING_CONV_SENTINEL_PREFIX` 신설 + `_newPendingSentinel()` helper 추가. helper 는 `${prefix}_${Date.now()}_${random 6 char}` 패턴으로 unique id 발급.
    - `isCurrentConvBusy()` (line 333~339) — sentinel 점유 검사를 글로벌 단일 토큰 → `state.pendingSentinel` 점유 여부로 변경. `state.pendingNewConversation && state.pendingSentinel && busyConversations.has(state.pendingSentinel)` AND 조건.
    - `beginPendingConversation()` (line 2993~3015) — TASK-0081 의 stale guard 분기 제거 + 항상 reset 흐름 진입 + `state.pendingSentinel = _newPendingSentinel()` 명시 부여. 첫 in-flight 여부와 무관하게 새 컨텍스트는 별개 sentinel 으로 분리. 기존 stopProgressPolling / activeConversationId reset / renderComposer 호출 chain 무변경.
    - `sendPrompt()` busyKey 결정 (line 3458~3475) — lazy-create 시 `state.pendingSentinel` 을 busyKey 로 capture. pendingSentinel 미할당 (직접 send 진입) fallback 으로 새 sentinel 생성 후 state 에 기록. 직접 send 는 `busyKey = targetConvId` 그대로.
    - `sendPrompt()` success path (line 3522~3539) — `if (state.pendingSentinel === busyKey)` closure check 후에만 `pendingNewConversation = false; activeConversationId = newCid; pendingSentinel = null` cleanup + polling 시작. closure mismatch (사용자가 send 도중 + 새 대화 이동) 시 두 번째 컨텍스트 state 보존 + refreshWorkspace 만 호출 (사이드바 list refresh).
    - `sendPrompt()` catch path (line 3537~3551) — TASK-0081 의 cleanup 도 closure check 추가. `if (state.pendingSentinel === busyKey)` 일 때만 cleanup. pending bubble error 표시 / toast 안내는 closure 무관하게 본 send 발생 사실을 알림.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `app.js?v=20260519-pending-recovery` → `app.js?v=20260519-unique-sentinel` cache-bust 토큰 갱신.
- Verification:
  - `node --check repo/unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - backend / RBAC / endpoint / audit / DB 무변경 (Python AST 검증 대상 없음).
  - smoke (사용자 직접 확인 권장): 회귀 시나리오 4 종 — ①첫 송신 in-flight 중 "+ 새 대화" 클릭 → 입력칸 활성화 + 두 번째 prompt 작성 + send → 두 응답 모두 정상 (각자 sentinel 분리, sidebar 양 conv 표시). ②catch 분기 종료 후 "+ 새 대화" → 정상 진입 (closure check 로 cleanup OK). ③응답 후 "+ 새 대화" → 정상. ④pending bubble error 표시 → closure check 와 무관하게 표시 (cleanup 은 closure 일치 시에만, bubble UI 는 별도).
- Risks:
  - **closure mismatch 시 첫 대화의 activeConversationId 갱신 skip**: 첫 send 의 success path 가 newCid 를 받아도 closure mismatch (두 번째 컨텍스트 이동) 면 `state.activeConversationId` 를 newCid 로 set 하지 않음. 사용자가 사이드바 conversation list 에서 첫 대화 (이미 발급된 newCid) 를 직접 클릭해서 진입해야 함. `refreshWorkspace(newCid)` 가 list 를 refresh 하므로 첫 대화는 list 에 표시. 의도된 동작이지만 사용자 인지 필요.
  - **closure mismatch 시 polling 시작 skip**: 첫 send 의 응답 도착 시 closure mismatch 면 `startProgressPolling` 호출 안 함. 첫 대화의 backend status="processing" 인 비동기 흐름은 사용자가 첫 대화로 진입 후 `loadHistory` → `startProgressPolling` (line 2895~2899 의 last_status=processing 경로) 가 다시 시작. 일관성 OK.
  - **pendingSentinel race**: 동일 ms 안에 두 진입 시 random suffix (`Math.random().toString(36).slice(2, 8)`) 로 16^6 = ~16M 가지 분리. 실용적 충돌 위험 0.
  - **legacy PENDING_CONV_SENTINEL reference**: 본 fix 후 글로벌 단일 토큰 검사는 모두 `state.pendingSentinel` 검사로 변경됨. `PENDING_CONV_SENTINEL` 상수는 외부 reference 없으나 호환 차원에서 유지 (별 cycle 에서 cleanup 가능).
- Trace: REQ-20260519-0010 → TASK-0082 → CHG-20260519-0012 → REV-20260519-0008. TASK-0081 의 stale 가드 + catch cleanup 정책 본 design 으로 자연 흡수. AC-0072 / AC-0075~0077 / AC-0176~0178 (TASK-0081) 회귀 보호.

## CHG-20260519-0011
- Date: 2026-05-19
- Summary: TASK-0081 (REQ-20260519-0009, Minor §12.3) — `beginPendingConversation()` stale flag 회복 가드 + `sendPrompt()` catch 분기 `pendingNewConversation` cleanup. 두 번째 새 대화 send (요청 버튼 / Ctrl+Enter) 가 무동작이던 회귀 fix.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - line 2993~2997 (`beginPendingConversation()` 의 early-return guard) — `state.pendingNewConversation` 단독 검사 → `state.pendingNewConversation && state.busyConversations.has(PENDING_CONV_SENTINEL)` 로 좁힘. 첫 lazy-create send 가 실제 in-flight (sentinel 점유) 일 때만 진입 보류. stale state (catch 분기 후 cleanup 누락 등) 는 통과해 정상 reset 흐름으로 진입.
    - line 3536~3537 (`sendPrompt()` 의 lazy-create catch 분기 진입 직후) — `state.pendingNewConversation = false` 명시 cleanup 1 줄 추가. pending bubble 의 error 표시 / toast 안내 로직은 무변경. busyConversations sentinel cleanup 은 기존 finally 블록의 `state.busyConversations.delete(busyKey)` 가 담당 (변경 없음).
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `app.js?v=20260519-chat-pane-flex` → `app.js?v=20260519-pending-recovery` cache-bust 토큰 갱신.
- Verification:
  - `node --check repo/unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - backend / RBAC / endpoint / audit / DB 무변경 (Python AST 검증 대상 변경 없음).
  - smoke (사용자 직접 확인 권장): ①새 대화 만들기 + 메시지 송신 + 정상 응답 후 다시 "+ 새 대화" 클릭 + 두 번째 메시지 send → 정상 진행. ②새 대화 만들기 + 메시지 송신 + (네트워크 차단 시뮬레이션 또는 backend timeout) catch 진입 후 "+ 새 대화" 클릭 + 두 번째 메시지 send → 정상 진행. ③첫 송신 in-flight 상태 (응답 도착 전) 에서 "+ 새 대화" 클릭 → 입력란 포커스만 유지 (의도적 — sentinel race 방지).
- Risks:
  - **lazy-create in-flight 중 "+ 새 대화" 클릭 보류 유지**: 사용자가 첫 송신 응답을 기다리는 중에 두 번째 대화로 전환을 시도하면 여전히 포커스만 잡고 진입 보류. 이는 sentinel 중복 race 방지를 위한 의도된 동작. UX 측면에서 사용자 안내 toast 추가 여부는 별 cycle 검토 가능.
  - **catch 분기 cleanup 이 pending bubble error 표시와 독립**: `state.pendingNewConversation = false` 직후에도 `state.pendingBubble` 의 error 영역은 그대로 표시되어 사용자가 직전 실패 컨텍스트를 확인 가능. 다만 사용자가 즉시 "+ 새 대화" 로 이동하면 pending bubble 도 새 흐름에 의해 정리될 수 있음 — AC-0077 의 빨간 오류 표시 안내 의도와 약간 trade-off.
  - **다른 entry point**: `beginPendingConversation()` 외에 `state.pendingNewConversation` 을 set 하는 코드 경로 미발견. line 3001 (본 함수 내부) + line 3524 의 success cleanup + line 3537 신규 catch cleanup 3 군데로 명확.
- Trace: REQ-20260519-0009 → TASK-0081 → CHG-20260519-0011 → REV-20260519-0007 (lazy-create state machine, AC-0072/0075/0076/0077 의 회귀 차단)

## CHG-20260519-0010
- Date: 2026-05-19
- Summary: TASK-0080 (REQ-20260519-0008, Minor §12.3) — `_collect_matched_excerpts` 의 SELECT 를 `AgentMemoryMessages` + `AgentCoreMessages` UNION ALL 로 확장. TASK-0077 followup. core-only conv 의 snippet 부재 회귀 차단.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py` — `_collect_matched_excerpts` 의 inner SELECT 가 두 table UNION ALL. 두 sub-SELECT 모두 동일 `conv_ids` IN + LIKE pattern + `COLLATE utf8mb4_unicode_ci` 통일. outer `ROW_NUMBER OVER (PARTITION BY cid ORDER BY msg_id DESC)` 으로 conv 별 더 최근 매칭 1건 선택. 파라미터 binding 은 `(conv_ids, pattern, conv_ids, pattern)` 4 그룹. line-based clip 로직 (LINE_MAX 220 + HALF_WINDOW 60) 무변경.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS.
  - make web 재배포 OK — repo-web-1 29 초 후 healthy.
  - smoke (사용자 브라우저 직접 확인 권장): core-only conv 에 매칭되는 검색어로 검색 → snippet 영역에 본문 excerpt 노출 확인.
- Risks:
  - **msg_id 의 두 table namespace 차이**: AgentMemoryMessages.Id 와 AgentCoreMessages.id 가 다른 schema. 본 fix 는 더 큰 id = 더 최근 가정 (monotonic 시간 증가) — 본 프로젝트 schema 정합. 동일 시점에 양 table 모두 INSERT 가 일어나는 race 에서는 어느 row 가 "더 최근" 인지 모호하나 sub-second race 라 사용자 시각 영향 0.
  - **collation 통일 cost**: `COLLATE utf8mb4_unicode_ci` 명시로 index 우회 가능 — query 비용 ↑ 가능. 단 본 query 는 `WHERE conv_ids IN (...)` 으로 row scope 가 conv 단위 (검색 결과 LIMIT 50) 라 cost overhead 미미.
  - **AgentCoreMessages content 컬럼이 NULL 인 row**: LIKE 의 NULL 매칭은 false 라 자동 제외 — 안전. 단 NULL content 의 conv 가 list 에 포함되면 excerpt 부재 (frontend snippet skip) — 그대로.
  - **search EXISTS 와 excerpt 의 동기화**: TASK-0072 의 `_list_conversations` search EXISTS subquery 가 두 table 모두 검사하므로 본 fix 와 일치. 향후 EXISTS / excerpt 중 하나만 변경 시 동기화 깨질 위험.
- Trace: REQ-20260519-0008 → TASK-0080 → CHG-20260519-0010 → REV-20260519-0006 (followup of TASK-0077)

## CHG-20260519-0009
- Date: 2026-05-19
- Summary: TASK-0079 (REQ-20260519-0007, Minor §12.3) — `.chat-pane` 의 flex 누락으로 짧은 대화 + 큰 viewport 조합 시 composer 아래 회색 빈 영역 노출되던 layout 결함 차단. TASK-0066 ChatGPT 패턴 layout 재구조화 시점 cascade 잔여 결함 — TASK-0068~0071 chain 이 admin 영역만 다뤘고 작업 화면 chat-pane 은 미적용.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.chat-pane` 에 `flex: 1 1 auto` + `min-height: 0` 추가 (2 line). 다른 속성 (display: flex, flex-direction: column, overflow: hidden, background: var(--bg)) 무변경.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust styles.css + app.js `v=20260519-snippet-line` → `v=20260519-chat-pane-flex` (양쪽 동일).
- Verification:
  - browser smoke 는 사용자 hard refresh 후 직접 확인 권장 (cache-bust `v=20260519-chat-pane-flex`).
  - make web 재배포 OK — repo-web-1 29 초 후 healthy.
  - DOM cascade 정합: `.app-shell { grid-template-rows: minmax(0, 1fr) }` (TASK-0071) → `.chat-column { flex column }` → `.chat-pane { flex: 1 1 auto; min-height: 0 }` (본 cycle) → `.messages-wrap { flex: 1; min-height: 0 }` → `.messages { flex: 1; min-height: 0 }`.
- Risks:
  - **다른 viewport 조합 검증**: 본 환경 (사용자 브라우저) 에서 정상 확인 필요. 작은 viewport (height < 600) 에서는 `.messages` 의 `overflow-y: auto` 가 scroll 흡수.
  - **mobile 반응형**: `.app-shell` 의 mobile 분기 (`max-width: 680px`) 는 grid → single column. `.chat-pane` 의 flex chain 은 mobile 에서도 정상 (single column 안에서 grow).
  - **TASK-0073 (다른 session) 과 file overlap 없음**: 본 cycle 의 styles.css `.chat-pane` 변경은 TASK-0073 의 admin / audit / endpoint 영역과 영역 분리.
- Trace: REQ-20260519-0007 → TASK-0079 → CHG-20260519-0009 → REV-20260519-0005 (TASK-0066 cascade 잔여 결함 hotfix)

## CHG-20260519-0008
- Date: 2026-05-19
- Summary: TASK-0078 (REQ-20260519-0006, Minor §12.3) — search modal 3 항목 추가 hotfix of TASK-0077. (1) mouseup race 보강 (mouseup target 추적 추가), (2) preset 텍스트 "부터" 제거, (3) snippet 본문 발췌 line-based clip.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py` — `_collect_matched_excerpts` 의 excerpt 추출 로직을 line-based 로 재작성. 매칭 위치의 line 경계 (`text.rfind("\n", 0, idx)` + `text.find("\n", idx)`) 를 찾아 line 전체를 반환. line 이 LINE_MAX (220 char) 초과 시 매칭 위치 ±HALF_WINDOW (60 char) clip + "…" prefix/suffix. 매칭 위치 검색 실패 (escape edge) 시 first line 사용.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `#searchDatePresets` 의 5 preset button 텍스트 "...부터" → "..." (5 개 모두). data-preset-hours 데이터 속성 무변경 (1/24/168/720/8760). cache-bust `v=20260519-search-presets` → `v=20260519-snippet-line` (styles.css + app.js 양쪽).
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.search-snippet` 의 `-webkit-line-clamp: 2` → `3` + `line-height: 1.45` + `max-height: 4.6em` 추가. line-based excerpt 의 시각 잘림 완화.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state.searchModal` 에 `mouseupOnOverlay: false` 추가.
    - `openSearchModal` reset 에 `mouseupOnOverlay = false` 추가.
    - `_bindSearchModalListeners` 의 overlay handler 패턴 갱신 — `overlay.mousedown` (mousedownOnOverlay 기록) + `overlay.mouseup` (mouseupOnOverlay 기록, **신규**) + `overlay.click` 시 둘 다 true + target === overlay 일 때만 close.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS.
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - `make web` 재배포 OK — `repo-web-1` 24 초 후 healthy.
- Risks:
  - **line-based excerpt 가 가독 line 보다 짧을 가능성**: 매칭 line 이 1 char 일 수도 있음 (예: 빈 line 직후 매칭 char 만 있는 line). 본 cycle 은 그대로 노출 — 사용자가 더 긴 context 가 필요하면 별 cycle 에서 neighboring line 추가 옵션 도입 권고.
  - **mouseup race 보강**: 양 끝점 모두 overlay 인 의도적 backdrop click 만 close. 사용자 의도 모호 케이스 (예: backdrop 위 mousedown → 곧바로 backdrop 위 mouseup) 는 정상 close — 의도적 backdrop click 으로 인식.
  - **preset 텍스트 변경**: 단순 텍스트 변경. 다른 영향 0.
  - **line-clamp 3 의 시각 영역 ↑**: 결과 row 의 height 가 1 줄 분량 (~21 px) 증가 가능. result list 의 max-height (TASK-0072 의 modal 본체 max-height 72vh) 내에서 노출 — viewport 안 result row 수가 ~1 개 감소할 수 있음. 보통 결과 list 가 길지 않아 영향 미미.
- Trace: REQ-20260519-0006 → TASK-0078 → CHG-20260519-0008 → REV-20260519-0004 (hotfix of TASK-0077)

## CHG-20260519-0007
- Date: 2026-05-19
- Summary: TASK-0077 (REQ-20260519-0005, Minor §12.3) — search modal 5 항목 hotfix bundle of TASK-0072/0076. 사용자 직접 테스트 보고 5 항목 모두 반영 — min char 3→2, 소유자 facet 제거, 기간 preset 5종, mouseup race fix, snippet 본문 excerpt.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py` — `_normalize_search_query` raw-len gate 3→2. `_collect_matched_excerpts(conn, conv_ids, q)` helper 신설 (MySQL 8.0 `ROW_NUMBER() OVER (PARTITION BY ConversationId ORDER BY Id DESC)` window function, content 매칭 위치 ±40 char clip + "…" prefix/suffix, AgentMemoryMessages 한정). `/api/conversations` endpoint 응답에 `matched_excerpts: {conv_id: "..."}` 첨부 (body-search 활성 시만, 실패 안전 — snippet 은 best-effort UX).
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — 소유자 facet button + `#searchOwnerPopover` + `#searchOwnerList` DOM 제거. 기간 popover 에 `#searchDatePresets` row 신설 (5 preset button). input placeholder "제목 · 계정명 · 본문 (3자 이상)" → "제목 · 본문 (2자 이상)". cache-bust `v=20260519-search-facets` → `v=20260519-search-presets`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.search-modal-popover-presets` + `.search-modal-popover-preset` 토큰 신설 (flex-wrap row, chip 모양).
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state.searchModal`: `owner_id` / `owner_username` / `product_id` / `ownerAccountsCache` 제거, `matched_excerpts: {}` + `mousedownOnOverlay: false` 추가.
    - 제거: `_loadOwnerAccountsForSearch`, `_openOwnerPopover`. `_closeSearchPopovers` / `_updateSearchFacetChipLabels` 의 owner 분기 제거.
    - `openSearchModal` reset 갱신 (owner 흔적 제거, matched_excerpts + mousedownOnOverlay 초기화).
    - `runSearchQuery`: min 2 char gate, owner_id 쿼리 파라미터 보내지 않음, matched_excerpts state 캐시 (append 모드 merge), 실패 시 reset.
    - `renderSearchModalResults`: empty state 문구 2자 기준, snippet 영역이 topic 대신 `sm.matched_excerpts[item.id]` excerpt + highlight. excerpt 부재 시 snippet skip (제목 매칭만).
    - `_searchHighlight`: min length 3 → 2.
    - `_bindSearchModalListeners`:
      - overlay click + mousedown race fix — `mousedownOnOverlay` flag 추적, click 시 둘 다 overlay 일 때만 close.
      - owner chip handler 제거.
      - facetClear: owner 흔적 reset 제거 + matched_excerpts reset 추가.
      - 기간 preset row click handler 신설 (5 preset 공통 — `data-preset-hours` 읽어 now - hours ~ now 자동 채움 + popover input sync + 적용 + runSearchQuery).
      - popover close mousedown 의 owner 분기 제거 (date 만 검사).
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS.
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - `make web` 재배포 OK — `repo-web-1` 8 초 후 healthy.
  - browser smoke 는 사용자 hard refresh 후 직접 확인 권장 (cache-bust `v=20260519-search-presets`).
- Risks:
  - **min 2 char gate 약화**: 검색 결과 수 증가 가능 + rate limit 빈번 진입 가능 — per-account 10 req/min 정책은 그대로라 DoS 표면 추가 0. raw 2 char 가 한글 grapheme 1 자도 통과 (예: "데") 는 일반적 검색어 패턴.
  - **`_collect_matched_excerpts` MySQL 8.0 dependency**: window function 의존. MySQL 5.7 환경에서는 query 실패 — try/except 로 silent skip + snippet 부재 fallback. STATUS.md 의 MySQL 8.0 명시와 정합.
  - **snippet excerpt PII 표면**: TASK-0072 의 audit/RBAC 정책 그대로. `.any` 한정 + opt-in chip + `WebAccountActivity` audit (현재 `conversation.search.body` action 만 기록 — excerpt 자체는 별 audit action 안 만듦, snippet chip 활성 시점에 이미 query 단위 audit 기록). 새 PII 표면 아님.
  - **소유자 facet 폐기 회귀**: backend `owner_id` 파라미터 호환 유지 — 향후 frontend 재도입 또는 다른 caller 영향 0.
  - **mouseup race fix**: mouseup 이 overlay 안에서 일어나지 않는 경우 click 이벤트도 발생 안 함 (브라우저 표준). 본 fix 는 click 발생 시 mousedown 도 overlay 였는지 검사 — drag-out 후 다시 modal 안으로 돌아와 mouseup 발생하는 edge case 도 안전 (target 이 modal element 라 close 안 됨).
- Trace: REQ-20260519-0005 → TASK-0077 → CHG-20260519-0007 → REV-20260519-0003 (hotfix bundle of TASK-0072/0076)

## CHG-20260519-0006
- Date: 2026-05-19
- Summary: TASK-0076 (REQ-20260519-0004, Minor §12.3) — search modal UX 3 결함 hotfix bundle of TASK-0072. 사용자 직접 테스트 보고: (1) facet click 무동작, (2) 키보드 ↑↓ scroll 미동작, (3) 매칭 message bubble jump 미동작. frontend only — backend / RBAC / audit / endpoint 무변경.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — 제품 facet button DOM 제거 (사용자 결정: 대화 중 product 변경 가능 → 필터 부적합). `#searchOwnerPopover` + `#searchDatePopover` 2 popover element 신설 (overlay 안 fixed 위치). cache-bust styles.css + app.js `v=20260519-modal-contrast` → `v=20260519-search-facets`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.search-modal-popover*` 토큰 ~110 줄 신설 (popover 자체 + header + body + popover-item + popover-field date input + footer + apply/clear buttons). `.message.is-search-matched` + `@keyframes search-matched-pulse` (1.6 s box-shadow pulse for matched message bubble jump highlight).
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state.searchModal` 에 `owner_username`, `ownerAccountsCache`, `pendingJumpQuery`, `pendingJumpConvId` 4 필드 추가.
    - `openSearchModal` 의 reset 보강 (owner_id / date_from / date_to / chip label / popover close).
    - 신규 helpers: `_positionPopoverBelow` / `_closeSearchPopovers` / `_updateSearchFacetChipLabels` / `_loadOwnerAccountsForSearch` (1 회 캐시) / `_openOwnerPopover` (admin accounts list + "전체" + role label) / `_openDatePopover` (`<input type="date">` from/to 동기화) / `_jumpToSearchMatchedMessage` (messageLogEl `.message` textContent lowercase compare → 첫 매칭 row scrollIntoView + `is-search-matched` class 1.8 s).
    - input keydown handler 갱신: ArrowDown / ArrowUp 시 active row 의 `scrollIntoView({block:'nearest'})` 추가. Enter 도 click 과 동일 pending jump 저장.
    - result item click 시 `state.searchModal.pendingJumpQuery = q` + `pendingJumpConvId` 저장 → closeSearchModal → selectConversation.
    - `_bindSearchModalListeners` 끝부분에 owner / date facet click handler + date apply / clear button handler 추가. overlay mousedown 시 popover 외 click 이면 popover 자동 close.
    - `selectConversation` 끝 (loadHistory + renderMessages + product hydration 직후) 에 `_jumpToSearchMatchedMessage()` 호출 추가.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - `make web` 재배포 OK — `repo-web-1` recreated 26 초 후 healthy.
  - browser smoke 는 사용자 hard refresh 후 직접 확인 권장 (cache-bust `v=20260519-search-facets`).
- Risks:
  - facet popover positioning 은 `position: fixed` + chip getBoundingClientRect 기반 — modal scroll / viewport resize 시 popover anchor drift 가능 (단발 click 후 즉시 적용이므로 보통 무문제. 단 popover 가 viewport 밖이면 right-edge clamp 만 적용 — bottom clamp 추가는 follow-up).
  - matched message jump 의 client-side textContent compare 는 user / assistant 메시지 모두 검사 — content snippet 매칭이 너무 광범위 (예: q="대화" 가 "대화 시작" 안내문에도 매칭) 시 정확도 낮음. backend matched_message_id 응답 도입은 별 cycle 권고.
  - owner_id facet 의 admin accounts cache 가 modal close 후 유지 — admin/operator 의 계정 추가/삭제 가 한 session 안에서 발생하면 stale 가능. 후속 cycle 에서 SSE / invalidate hook 권고.
- Trace: REQ-20260519-0004 → TASK-0076 → CHG-20260519-0006 → REV-20260519-0002 (hotfix bundle of TASK-0072)

## CHG-20260519-0005
- Date: 2026-05-19
- Summary: TASK-0072 + TASK-0074 HTTP smoke test 실행 결과를 `unit/feature-0003-agent-web-ui/docs/TEST.md §4 Test Run History` 에 append. bootstrap_admin 1 토큰만 ad-hoc curl (operator pw 미보유). 6/8 PASS — S2 (any cross-account), S4 (cursor disjoint), S5 (q invalid 400), S6 (rate limit 429), S7 (DDL idempotent), S8 (audit SHA-256). S1/S3 (operator 의존) skip — `_list_conversations` 의 has_any 분기 + endpoint 의 effective_owner_id 강제 overwrite 코드 review 로 검증.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/docs/TEST.md` — §4 Test Run History 에 2026-05-19 entry 추가 (8 sub-result + skip 사유 + UI 가독성 사용자 직접 확인 권장 note).
- Verification: 6/8 시나리오 PASS (S1/S3 operator 의존 skip). 코드 변경 0 — 단순 test 결과 기록.
- Risks: 0 (append-only 문서 갱신).
- Trace: TASK-0072 + TASK-0074 → CHG-20260519-0005 (test execution record only, no spec change)

## CHG-20260519-0004
- Date: 2026-05-19
- Summary: TASK-0074 (REQ-20260519-0002, Minor §12.3) — search modal 색상 가독성 hotfix of TASK-0072. site theme = light (`--bg #f4f4f5` / `--surface #ffffff` / `--text #18181b`) 환경에서 modal 의 미정의 var fallback (dark hardcode `#1f2429`) + site 의 text inherit 검은색 = 어두운 배경 위 검은 텍스트 = 가독성 0 (사용자 screenshot 보고). modal CSS 전체를 site 의 기존 토큰으로 일관 적용.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `--search-modal-bg: var(--surface)`, `--search-modal-border: var(--border)`, `--search-highlight-bg: #fde68a`. modal block 의 모든 `var(--text-primary)` → `var(--text)`, `rgba(255,255,255,.04|.03|.05)` → `var(--primary-soft)` / `var(--bg)`, chip aria-pressed bg → `--primary-soft`, owner badge "내" = triple (bg + border + color), snippet bg = `--bg`, snippet-hl color = `--text` + `font-weight: 600`, result-item button reset (background transparent + border 0 + width 100% + text-align left + font-family inherit), backdrop `rgba(15,23,42,0.48)` (modal pop 강조 유지).
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust styles.css + app.js `v=20260518-conv-search` → `v=20260519-modal-contrast`.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260519-0002 / TASK-0074 / CHG-20260519-0004 / REV-20260519-0001 entries.
- Verification:
  - `make web` 재배포 OK — repo-web-1 recreated 12 초만에 healthy.
  - backend / RBAC / endpoint / audit / TASK-0073 의 WebAuditEvents 영역 무변경.
  - python3 / node --check 대상 변경 없음 (CSS + cache-bust only).
- Risks: 매우 낮음 — CSS 토큰 변경만. modal 외 영역 영향 0. TASK-0073 Phase A0 (WebAuditEvents) 와 file overlap 없음 (styles.css + index.html cache-bust vs app.py DDL + docs).
- Trace: REQ-20260519-0002 → TASK-0074 → CHG-20260519-0004 → REV-20260519-0001 (hotfix of TASK-0072)

## CHG-20260519-0003
- Date: 2026-05-19
- Summary: TASK-0073 (REQ-20260519-0001, **Critical** §12.3) — Phase A0: WebAuditEvents DDL + bootstrap helper. plan §2.1 (TASK-0073) 의 Eng review lock-in (E2 schema hybrid + E4 ActorType + E1 TargetAccountId) 의 schema 정의를 코드로 정착. 본 CHG 는 schema 만 — dispatcher (Phase A1), migration (A2), RBAC (A3), endpoints (A4), admin hook (A5), user hook (A6), tests (B), frontend (C), project docs (D) 는 별 phase.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - **신설** `_ensure_web_audit_events_schema(conn)` (line ~2501 직전, `_log_search_activity` 직후, `_ensure_must_change_password_schema` 직전). DDL: `WebAuditEvents` 14 columns (Id BIGINT PK, ActorAccountId/ActorRoleId/TargetAccountId BIGINT NULL, ActorType VARCHAR(16) DEFAULT 'account', SessionId VARCHAR(64), ActionCode VARCHAR(64), ResourceType VARCHAR(32), ResourceId VARCHAR(64), ChangeJson/MaskedFields JSON, RemoteAddr VARCHAR(64), UserAgent VARCHAR(255), RequestId VARCHAR(64), OccurredAt TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3)) + 5 secondary indexes (IX_WAE_Actor / Target / Action / Resource / ActorType). Docstring 에 Eng review E1-E5 결정 근거 명시 (Approach B + Same tx admin / fail-open user + ActorType enum + TargetAccountId self filter).
    - **fast-path hydrate** (`_ensure_seed_catchup` line ~2541): `_ensure_web_audit_events_schema(conn)` 호출 추가 (`_ensure_web_account_activity_schema` 직후). 기존 배포 재기동 시 audit table backfill.
    - **slow-path bootstrap** (`_ensure_web_tables` line ~2748): 동일 helper 호출 추가 (`_ensure_web_account_activity_schema` 직후, `WebRoles` CREATE 직전). 신규 배포 첫 기동 시 audit table 생성.
    - 3 위치 모두 TASK-0072 의 `_ensure_web_account_activity_schema` 패턴 답습.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` → **PASS** (helper 신설 + 2 hook 추가 syntax 검증).
  - `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` (commit 직전 gate).
  - 컨테이너 재기동 시 fast-path / slow-path 모두 `WebAuditEvents` DDL 적용 확인은 Phase E (make web 재배포) 에서.
- Risks:
  - **DDL idempotent**: `CREATE TABLE IF NOT EXISTS` — 기존 배포 재기동 시 noop. TASK-0072 패턴 검증됨.
  - **Schema migration 정합**: ActorType `DEFAULT 'account'` 기본값으로 기존 row 가 있어도 NOT NULL 충족 (단 본 phase 는 신규 table, 기존 row 0). Phase A2 의 WebAccountActivity migration 시 ActorType="account" 명시 INSERT.
  - **Index cardinality**: 5 secondary indexes — write 부하 5x. 단 admin 빈도 낮음 + user (대화·SQL·share·anonymous) 도 본질 write 빈도. 365일 retention 후 partitioning 검토 (Phase 2).
  - **schema drift**: 본 cycle 의 다른 Phase 가 schema 변경 시 본 helper 의 DDL 도 update 필요. 단 schema 는 Eng review 에서 fix 됨 — drift 없음.
- Trace: REQ-20260519-0001 → TASK-0073 → §2.1 (TASK-0073) 의 Eng review lock-in E2 + E1 + E4 → Phase A0 → CHG-20260519-0003 → REV-20260519-0001 (CEO + Eng + Phase A0 통합, Phase D)

## CHG-20260519-0002
- Date: 2026-05-19
- Summary: TASK-0073 (REQ-20260519-0001, **Critical** §12.3) — `/plan-eng-review` Eng review lock-in (E1-E9 + 30 test paths + 5 deadlock scenarios). Codex outside voice 의 Additional risk 9 (C7-C14) + 5 deadlock scenarios + 추가 eng items 를 architecture-level 로 lock-in. 사용자 결정 2 항목 (E1 self 정의 = Actor OR Target / E4 anonymous share audit 포함 + ActorType column) + 나머지 7 항목 prose lock-in. 본 CHG 는 plan 본문 update 만, 코드 변경 0. Phase A0 진입 ready 상태.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/docs/TASK.md`
    - §2.1 (TASK-0073) 의 마지막 subsection 으로 "Eng review lock-in (E1-E9)" 추가 — 9 finding 의 architecture-level decision + Phase B 시나리오 확장 8 → 10 + Test infra 보강 + Acceptance criteria + Eng review 결과 요약 명시.
    - 본 추가로 `WebAuditEvents` DDL 14 columns (ActorType + TargetAccountId 추가) + 5 secondary indexes 확정. E8 chunked PK purge Python 의사코드 정착. E1 self filter SQL (`WHERE ActorAccountId = :self OR TargetAccountId = :self`) 확정.
- Verification:
  - 본 CHG 는 plan 본문 update 만이라 py_compile / node --check 적용 대상 없음.
  - `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` (Phase A0 진입 전 lock-in commit).
- Risks:
  - **E1 B 결정의 부수효과**: admin actor 의 mutation 이 target user audit 에 보임 → admin "감시당함" 인지 가능. 단 정당한 보안 추적, SECURITY.md §8 에 명시.
  - **E4 B 결정의 부수효과**: anonymous share view 도 audit row → write 부하 추가 (대화 share 빈도에 비례). 단 ActorType="anonymous" filter 로 분리 조회 가능.
  - **E8 chunked purge idempotency**: 1 분 내 중복 purge 차단 (`idempotency_key = hash(cutoff, started_at_minute)`). 단 1 분 이후 동일 cutoff 재호출은 허용 — 이미 deleted 된 데이터라 noop 이지만 audit.purge.start row 만 추가 생성. 운영 정책상 acceptable.
  - **E2 Schema 변경 가능성**: ActorType column 추가는 본 CHG 가 plan 본문만 update — 실제 DDL 은 Phase A0. DDL 변경 시 본 lock-in 의 schema 명세 update 필요.
  - **테스트 부하**: 30 test paths 중 Phase B 10 HTTP smoke 가 가장 무거움 (admin/operator/sales/dba 다중 role + cross-account). 실행 시간 ~3분 추정.
- Trace: REQ-20260519-0001 → TASK-0073 → §2.1 Implementation Plan (TASK-0073) + Codex outside voice 14 findings + Eng review 9 lock-in → CHG-20260519-0001 (CEO) → CHG-20260519-0002 (Eng) → REV-20260519-0001 (CEO + Eng 통합, Phase D)

## CHG-20260519-0001
- Date: 2026-05-19
- Summary: TASK-0073 (REQ-20260519-0001, **Critical** §12.3) — 모든 계정 행위 audit 기능 + 관리 콘솔 조회 plan 본문 작성 (plan-approved 단계, 코드 변경 0). CEO review 9 decision (Mode=HOLD SCOPE, Scope=Approach B Balanced, Storage=DB-only, Hook=Web-ui 단일, MySQL log=통합, RBAC=4건 .self/.any, Tx=Same tx, Masking=Hybrid, Flag=AGENT_AUDIT_ENABLED=1) → Codex outside voice 14 findings + 6 minimum-fix dispatch (read-only sandbox, model_reasoning_effort=high) → 9 decision 중 5 reset (Storage·MySQL log·Hook·Tx·Masking 의 5 domain) → Major redesign 사용자 확정. WebAccountActivity (TASK-0072) 흡수 결정 (직전 검토 보고가 놓친 결손, codex finding C2). 본 CHG 는 plan 본문 작성만, Phase A0 부터 별 cycle 시작.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/docs/TASK.md`
    - Task Queue 에 TASK-0073 entry 추가 (in-cycle 결정 9 항목 + 상태 `approved-after-outside-voice` + 사용자 메모리 `feedback_outside_voice_for_rbac` 적용).
    - `<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0073 Phase A0~F 일괄, Critical 등급 audit 표면 신설 + WebAccountActivity 흡수 + RBAC 4건 .own/.any + Tx split + Allowlist builder + AGENT_AUDIT_ENABLED prod fail-closed) -->` marker.
    - §2.1 Implementation Plan (TASK-0073) section 신설 (§2.1 (TASK-0072) 위에 시간 역순 배치). 본 plan 의 구성: CEO 9 decision 표 + outside voice 종합 결정 표 (Codex 14 findings) + Must-fix 5 + Additional risk 9 (eng review lock-in) + 영향 파일 13 + Phase A0~F 순서 + 위험도 평가 표 10 + 검증 계획 + outside voice 결과 요약.
- Verification:
  - `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` (Phase A0 진입 전, plan-approved commit).
  - 본 CHG 는 plan 본문 작성만이라 py_compile / node --check / HTTP smoke 적용 대상 없음.
  - 외부 검증: Codex outside voice (`codex exec -s read-only -c 'model_reasoning_effort="high"'`) 14 findings + 6 minimum-fix 도출 → 본 plan 의 redesign 에 모두 흡수.
- Risks:
  - **PII leak (ChangeJson masking)**: Action-specific allowlist builder + SECURITY.md §8 sensitive field catalog (Phase D 작성) + admin UI HTML escape.
  - **RBAC bypass (.own ↔ .any)**: TASK-0058 share read-gate 패턴 + Phase B smoke 8 시나리오 + 404/403 byte-equal.
  - **Tx atomicity (admin Same tx)**: dispatcher SPOF = verify-completion.sh check + 100% test coverage + builder explicit raise on unknown action.
  - **`/api/ask` deadlock**: user endpoint fail-open + TASK-0072 `_log_search_activity` 패턴 답습 + Same tx 제외.
  - **Feature flag bypass**: `AGENT_AUDIT_ENABLED` prod (`AGENT_MODE!=dev/test`) startup fail-closed + dev/test only toggle.
  - **WebAccountActivity 흡수**: migration data 보존 (기존 table drop 별 cycle backup 후) + dual source 일시 공존 → 단일 source 전환.
  - **RBAC hydrate 순서**: TASK-0063 회귀 fix 패턴 답습 (`_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞).
  - **365일 chunked purge**: `ORDER BY Id LIMIT N` cursor 재시작 가능 + idempotency key + `audit.purge` self-audit row.
- Trace: REQ-20260519-0001 → TASK-0073 → §2.1 Implementation Plan (TASK-0073) + Codex outside voice 14 findings + 6 minimum-fix → CHG-20260519-0001 → REV-20260519-0001 (Phase D)

## CHG-20260518-0010
- Date: 2026-05-18
- Summary: TASK-0072 (REQ-20260518-0010, **Critical** §12.3) — 타 계정 대화 검색·필터 + WebAccountActivity audit log 신설. Phase A0~E. outside voice 3 review (security FIX-FIRST, adversarial Blocker + 3 sub-spec, ux NEEDS-TWEAK) 의 4 must-fix + 3 sub-spec + 6 risk 모두 흡수. UI 위치 = Spotlight modal (Cmd/Ctrl+K) + 사용자 변형 ("+ 새 대화" 우측 같은 높이 돋보기 icon). 사용자 in-cycle 결정 5 항목 채택.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - Phase A0: `_ensure_web_account_activity_schema(conn)` + `_log_search_activity(conn, account_id, action, target_owner_id, query, matched_count)` 신설. `WebAccountActivity` 테이블 (`Id, AccountId, Action, TargetOwnerId, QueryHash CHAR(64), MatchedCount, CreatedAt`, 2 index). slow path (`_ensure_web_tables`) + fast path (`_ensure_seed_catchup`) 양쪽에서 idempotent 보장.
    - Phase A1 helpers: `_RATE_LIMIT_BUCKETS` / `_RATE_LIMIT_LOCK` / `_COLLATION_AUDIT_DONE` module global + `_escape_like_for_search(s)` (`!`/`%`/`_` 3 char escape) + `_normalize_search_query(q)` (strip + len 3-200 gate, post-escape 0 literal char 차단) + `_search_rate_limit_check(account_id, max_per_min=10)` (in-process token bucket, 60 s window) + `_audit_message_table_collations(conn)` (process 당 1 회 information_schema 점검) + `_parse_search_cursor(cursor)` (`updated_at|conversation_id` 파싱).
    - Phase A1: `_list_conversations()` 시그니처 확장 (`q`, `owner_id`, `product_id`, `date_from`, `date_to`, `cursor`). 3 sub-spec 적용 — (a) SQL composition order: owner_id WHERE 가 q/owner_id/product_id 보다 항상 먼저 AND, `.own` 사용자 owner_id 는 self 로 SQL 단계에서 강제 overwrite; (b) `hidden_ids` SQL push: Python post-filter 폐기 후 `c.conversation_id NOT IN (...)` 로 이전; (c) Python re-sort 삭제: SQL `ORDER BY c.updated_at DESC, c.conversation_id DESC LIMIT N` 단일화. 본문 search 는 `c.topic` / `topic_kv.Value` / `owner.Username` (.any 한정) / `AgentMemoryMessages.Content` EXISTS subquery / `AgentCoreMessages.content` EXISTS subquery + `LIKE %s ESCAPE '!'`. `WebAccounts.DeletedAt IS NULL` 필터 추가 (cross-account leak 추가 차단 layer). cursor pagination keyset on `(updated_at, conversation_id)` DESC.
    - Phase A2: `/api/conversations` 가 `q`/`owner_id`/`product_id`/`date_from`/`date_to`/`cursor`/`limit` query param 수신. search mode 분기 (search params 가 하나라도 있을 때 활성). body-search 시 `_search_rate_limit_check` 10 req/min 진입 (429), `SET SESSION max_execution_time = 3000` 적용, `_log_search_activity` audit INSERT. 응답: `{items, current=null, next_cursor, matched_count, search_mode=true, has_any}`. q < 3 char 또는 escape-0 → 400. `.own` 사용자 owner_id 는 endpoint 에서도 effective overwrite 로 byte-equal response 보장.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`
    - `.sidebar-head` 의 "+ 새 대화" 버튼 우측에 같은 높이 `#openSearchBtn` (돋보기 SVG icon + aria-label="대화 검색 (Ctrl+K)") 추가. `+ 새 대화` 는 `flex: 1`, 검색 버튼은 `flex: 0 0 auto` (30×30).
    - body 끝 직전에 `#searchModalOverlay` (role="dialog" aria-modal="true") + `#searchModal` (header + input row + facets row + result list + footer). facets: `#searchFacetOwner` (.any 한정 hidden 토글) / `#searchFacetProduct` / `#searchFacetDate` / `#searchFacetSnippet` (.any 한정 hidden, aria-pressed) / `#searchFacetClear`.
    - cache-bust `v=20260518-shell-grid-rows` → `v=20260518-conv-search`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.sidebar-head` flex-direction column → row (gap 6 px, align-items: center). `.btn-new-conv { flex: 1 1 auto }` + `.btn-search-conv { flex: 0 0 auto; width/height: 30px }` + hover/focus-visible 상태.
    - 신규 search modal 토큰 ~200 줄: `--search-highlight-bg` / `--search-modal-bg` / `--search-modal-border` root var, `.search-modal-overlay` (fixed, backdrop blur, z-index 1200), `.search-modal` (max-width 640px, max-height 72vh), header / input row / facets / result list / footer / snippet (`-webkit-line-clamp: 2`) / `.search-snippet-hl` (highlight bg). a11y: `focus-visible` outline ring, mobile (`max-width: 600px`) 분기.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state.searchModal: { open, q, owner_id, product_id, date_from, date_to, snippet_opt_in, cursor, results, has_any, debounceTimer, activeResultIdx, lastFocusedBeforeOpen }` 신설.
    - `openSearchModal()` / `closeSearchModal()` / `runSearchQuery({append})` / `renderSearchModalResults()` / `_searchHighlight(text, q)` (case-insensitive 매칭 highlight) / `_bindSearchModalListeners()` 추가.
    - Cmd/Ctrl+K (toggle) + Esc (close 시 only) 글로벌 keydown. ArrowDown/ArrowUp 으로 결과 이동, Enter 로 선택. backdrop click 도 close. 300 ms 디바운스. snippet opt-in chip 토글. cursor pagination 더 보기 버튼.
    - file 끝의 `initialize()` 호출 직전에 `_bindSearchModalListeners()` 호출.
  - `repo/unit/feature-0003-agent-web-ui/tests/test_search_rbac.py` 신설 — 6 시나리오 standalone Python smoke (urllib).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md` + `repo/docs/SECURITY.md §8` + `repo/docs/STATUS.md` — REQ-20260518-0010 / TASK-0072 / CHG-20260518-0010 / REV-20260518-0010 entries.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS (Phase A0/A1/A2 + helper 5 + endpoint 모두).
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/tests/test_search_rbac.py` PASS.
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS (Phase C 의 modal handler 포함).
  - HTTP smoke 6 시나리오 (`tests/test_search_rbac.py`) 는 Phase E 에서 컨테이너 가동 후 실행 (admin/operator 비밀번호 필요).
  - `make web` 재배포 + browser smoke (Cmd+K open / q="test" 입력 / Esc close / snippet chip toggle / cursor 더 보기) 도 Phase E 에서.
- Risks:
  - **WebAccountActivity DDL idempotent**: `CREATE TABLE IF NOT EXISTS`. slow + fast path 양쪽 보장.
  - **3 sub-spec 회귀**: `.own` 사용자 owner_id 가 endpoint 와 _list_conversations 양쪽에서 self 로 강제. byte-equal response 보장. Phase B 6 시나리오 smoke 에서 검증.
  - **PII leak**: snippet opt-in 기본 OFF + `.any` 한정 + audit log + SHA-256 hash. cross-account body 검색 전 사용자가 명시적으로 chip 켜야 본문 미리보기 노출.
  - **성능 회귀**: min 3 char + LIMIT 50 + per-account rate 10/min + `max_execution_time=3000ms` + collation audit. 한계 도달 시 후속 cycle 에서 ngram FULLTEXT 도입 (REVIEW.md REV-20260518-0010 의 미해결 followup).
  - **share-link 회귀**: `share.js` 신규 import 없음. modal element 는 `index.html` 에만 mount.
- Trace: REQ-20260518-0010 → TASK-0072 → §2.1 Implementation Plan (TASK-0072) + outside voice 3 verdict → CHG-20260518-0010 → REV-20260518-0010

## CHG-20260518-0008
- Date: 2026-05-18
- Summary: TASK-0071 (REQ-20260518-0009, Minor §12.3 — shell grid row hotfix, RBAC / endpoint / 데이터 / JS 무변경) TASK-0070 의 list-detail row fix 이후에도 사용자 3 차 screenshot 보고 — dashboard pane 처럼 list-detail 을 사용하지 않는 화면에서 큰 viewport (height 800+) + 짧은 content 조합 시 sidebar / commit-bar 가 viewport 의 약 70% 위치까지만 차지하고 그 아래 회색 빈 영역이 viewport bottom 까지 노출.
- 원인: `.app-shell` / `.admin-shell` 둘 다 `display: grid; height: 100vh` 만 정의하고 `grid-template-rows` 미정의 → default `grid-auto-rows: auto` → single row track 의 height 가 자식 max-content 결정. 자식 (sidebar / column) 의 max-content 가 짧으면 grid track 도 짧음. grid container 자체는 100vh 차지하지만 track 이 100vh 보다 작으면 track 아래 빈 영역. 이전 cycle 의 fix (list-detail / workspace 의 flex grow) 는 column 안의 stretch chain 만 해결 — column 의 height 자체가 grid track 에 의해 결정되는 layer 는 미처리. cascade 의 root.
- 관찰: 동일 viewport (900) 에서 본 환경 (chrome headless) 은 grid track 이 100vh 차지 (다른 grid track sizing 동작), 사용자 환경에서는 max-content 차지 — 환경별 grid algorithm 동작 차이가 회귀 노출 timing 결정.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.app-shell` 에 `grid-template-rows: minmax(0, 1fr)` 추가. single row 가 grid container 의 전체 height 차지하도록 명시.
    - `.admin-shell` 에 동일 rule 추가. 두 shell 동일 패턴 유지.
    - 다른 속성 (grid-template-columns / height: 100vh / overflow: hidden) 무변경.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — cache-bust `v=20260518-admin-list-rows` → `v=20260518-shell-grid-rows`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust `v=20260518-product-composer` → `v=20260518-shell-grid-rows` (양쪽 페이지 동일 cache-bust 로 정렬).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0009 / TASK-0071 / CHG-20260518-0008 / REV-20260518-0008 entries.
- Verification:
  - `SKIP_INIT=1 make web` 재배포 OK.
  - DOM (browser headless `/admin` dashboard pane, viewport `1320x900`):
    `admin-shell h = 900` (viewport 와 일치), `admin-column h = 900`, `commit-bar bottom = 900` (viewport bottom 정확히 sticky), `gridTemplateRows = "900px"` (minmax(0, 1fr) 의 computed 값).
  - Screenshot `/tmp/admin-dashboard-fixed.png` — sidebar (brand → 탭 → ... → pending footer) 가 viewport 전체 height 차지 + admin-column (topbar → dashboard content + 자연 빈 영역 → commit-bar 가 viewport bottom). sidebar / commit-bar 아래 회색 빈 영역 사라짐.
  - 작업 화면 (`/`) 도 동일 fix 자연 적용 — `.app-shell` 의 동일 rule.
  - 양쪽 shell 의 일관성 보장 (`.app-shell` 과 `.admin-shell` 둘 다 `grid-template-rows: minmax(0, 1fr)`).
- Trace: REQ-20260518-0009 → TASK-0071 → CHG-20260518-0008 → REV-20260518-0008 (hotfix of TASK-0068 / 0069 / 0070 layout chain — cascade root fix)

## CHG-20260518-0007
- Date: 2026-05-18
- Summary: TASK-0070 (REQ-20260518-0008, Minor §12.3 — admin list-detail grid row hotfix, RBAC / endpoint / 데이터 / JS 무변경) TASK-0069 follow-up. 사용자 screenshot 2 차 보고 — `역할` / `제품` 등 항목이 적은 pane 에서 화면 height 가 큰 viewport 의 경우 list-col / detail-col box 가 viewport 의 일부만 차지하고 그 아래로 admin-workspace 의 padding 영역이 회색으로 노출. 항목이 많은 pane (`계정` 26 row) 이나 화면이 좁을 때는 content 가 row 를 자연 채워 노출 없었기에 1 차 검증 (720 viewport) 에서는 놓침.
- 원인: `.admin-list-detail { display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr) }` 의 `grid-template-rows` 미정의 → default `grid-auto-rows: auto` → row 의 height 가 content 결정. `align-items: stretch` 는 row 안에서 column 분배만 담당 (row 자체의 height 결정 X). 결과: list-col / detail-col content 가 짧으면 row 도 짧고 list-detail 의 flex grow 가 의미를 잃음.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.admin-list-detail` 에 `grid-template-rows: minmax(0, 1fr)` 추가. 단일 row 의 height 를 명시. minmax(0, ...) 으로 자식의 min-content 무시 — 큰 viewport 에서도 row 가 list-detail 의 flex grow 받은 height 전부 차지.
    - 다른 속성 (grid-template-columns / gap / align-items / min-* 0 / flex 1 1 auto) 무변경.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — cache-bust `v=20260518-admin-workspace-flex` → `v=20260518-admin-list-rows`.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0008 / TASK-0070 / CHG-20260518-0007 / REV-20260518-0007 entries.
- Verification:
  - `SKIP_INIT=1 make web` 재배포 OK.
  - DOM (browser headless `/admin` → 제품 tab, viewport `1320x900`):
    `viewport = 900`, `listDetail h = 682` (이전엔 자기 content 약 200 만큼만), `listCol h = 682`, `detailCol h = 682`, `cbar y = 839 / bottom = 900` (viewport bottom 에 정확히 sticky).
  - Screenshot `/tmp/admin-products-fixed.png` — list-col / detail-col box 가 viewport 의 거의 전체 height 까지 stretch + 3 items 만 있어도 box 자체는 commit-bar 까지 stretch + 회색 빈 영역 사라짐. 사용자 screenshot 회귀 완전 해결.
  - 다른 pane (계정 / 역할) 도 동일 fix 자연 적용 — `.admin-list-detail` 단일 rule 변경.
- Trace: REQ-20260518-0008 → TASK-0070 → CHG-20260518-0007 → REV-20260518-0007 (hotfix of TASK-0068 / 0069 layout chain)

## CHG-20260518-0006
- Date: 2026-05-18
- Summary: TASK-0069 (REQ-20260518-0007, Minor §12.3 — admin layout hotfix, RBAC / endpoint / 데이터 / JS 무변경) TASK-0068 follow-up. 사용자 screenshot 으로 보고된 layout 회귀 — admin `역할 관리` (및 다른 list-detail pane) 에서 commit-bar 가 workspace content 바로 아래에 좁게 위치하고 그 아래로 큰 회색 빈 영역이 admin-column 의 bottom 까지 노출. 원인: TASK-0068 에서 commit-bar 를 admin-shell grid (3rd row) → admin-column 의 flex column item 으로 이전한 후 `.admin-workspace` 에 `flex: 1` 명시 누락. flex column 안에서 workspace 가 자기 content 만큼만 차지 → flex column 의 남은 공간이 빈 채로 보이고 commit-bar 가 workspace 끝 바로 아래에 위치 (sticky bottom 효과 상실). 각 `.admin-pane.is-active` 의 `flex: 1 1 auto` 가 의미를 가지려면 부모 `.admin-workspace` 자체가 stretch 되어야 함.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.admin-workspace` 에 `flex: 1 1 auto` 추가. 다른 속성 (overflow / padding / display flex column / min-* 0) 무변경.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html`
    - cache-bust `v=20260518-admin-layout` → `v=20260518-admin-workspace-flex` (admin.html / admin.js 양쪽 stylesheet ref).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0007 / TASK-0069 / CHG-20260518-0006 / REV-20260518-0006 entries.
- Verification:
  - `SKIP_INIT=1 make web` 재배포 OK.
  - DOM (browser headless `/admin` → 역할 tab):
    `wsHeight = 607, wsBottom = 659, cbarTop = 659, cbarBottom = 720, colHeight = 720, colBottom = 720`
    → `workspaceTouchesCommitBar = true` (둘 사이 빈 공간 없음), `commitBarAtBottom = true` (commit-bar 가 column 의 bottom 에 정확히 위치).
  - Screenshot `/tmp/admin-roles-fixed.png` — 역할 list-detail 이 admin-workspace 의 남은 height 전부 차지 + commit-bar 가 viewport bottom 에 sticky. 회색 빈 영역 사라짐. screenshot 으로 보고된 회귀 fix 확인.
  - 다른 pane (계정 / 제품 / 대시보드) 도 동일 fix 자연 적용 — `.admin-workspace` 의 단일 rule 변경이 전체 admin pane 에 일관 적용.
- Trace: REQ-20260518-0007 → TASK-0069 → CHG-20260518-0006 → REV-20260518-0006 (hotfix of TASK-0068)

## CHG-20260518-0005
- Date: 2026-05-18
- Summary: TASK-0068 (REQ-20260518-0006, Minor §12.3 — admin layout 정합 + 미사용 버튼 정리. backend / endpoint / RBAC / 데이터 영역 무변경.) 사용자 follow-up — 관리 콘솔의 사이드바 구성을 작업 화면 (TASK-0066 의 ChatGPT 패턴) 과 동일하게 정렬 + 헤더의 `새로고침` / `로그아웃` 버튼 제거 (사용자 직접 테스트에서 거의 사용 안 되는 것 확인).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html`
    - `<header class="topbar">` 의 `.topbar-brand` 를 `.admin-sidebar` 의 첫 child `.sidebar-brand` (brand-icon + "MySQL AI" — 작업 화면과 동일 brand) 로 이전. 기존 admin brand 가 "관리 콘솔" 이었지만 ChatGPT 패턴은 brand 가 product 정체성 (MySQL AI), 페이지 컨텍스트 (관리 콘솔) 는 topbar 안에 표시.
    - 기존 topbar 의 `#refreshAdminBtn` (새로고침) 과 `#adminLogoutBtn` (로그아웃) 2 element 제거. `#backToAppBtn` (작업 화면 전환) 만 `.topbar-end` 에 유지.
    - `.admin-body` wrapper 제거.
    - 신규 `.admin-column` (sidebar 옆 영역 wrapper, flex column) 안에 `<header class="topbar">` (`.topbar-info` 안에 `<h2 class="chat-title">관리 콘솔</h2>` + `<span class="chat-subtitle">계정 · 역할 · 제품 · 시스템 프롬프트 운영</span>`) → `<main class="admin-workspace">` → `<footer class="admin-commit-bar">` 순서로 배치. commit bar 가 sidebar 와 분리되어 admin-column 의 하단에만 표시.
    - cache-bust `v=20260515-task-0062` → `v=20260518-admin-layout` (admin.html 은 이전 cycle 들의 cache-bust 흐름에서 누락되어 별 cycle 마다 갱신 안 됐던 점도 정렬).
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.js`
    - `#refreshAdminBtn` click handler 제거 (적용된 pending clear + loadAdminData 호출 로직 제거 — element 부재로 dead reference).
    - `#adminLogoutBtn` click handler 제거 — `POST /api/auth/logout` 호출 흐름 제거. 로그아웃은 작업 화면 (`/`) 의 프로필 drawer 에서 가능하므로 기능 손실 없음.
    - `#backToAppBtn` click handler 유지 (pending change 보호 confirm + `window.location.href = "/"`).
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.admin-shell` 의 `grid-template-rows: var(--topbar-h) minmax(0, 1fr) auto` → `grid-template-columns: 220px minmax(0, 1fr)` (작업 화면의 `.app-shell` 과 동일 패턴 — 단일 row 2-column).
    - `.admin-body` rule 폐기 (HTML wrapper 도 제거됨).
    - 신규 `.admin-column` — `display: flex; flex-direction: column; min-width: 0; overflow: hidden`.
    - `.admin-sidebar` 의 `padding: 10px 8px` 제거 — brand 가 sidebar 의 첫 영역으로 들어가면서 padding 을 각 child (`.sidebar-brand`, `.admin-tabs`, `.admin-sidebar-foot`) 가 갖도록 함. 신규 `.admin-sidebar .admin-tabs { padding: 10px 8px 0 }` + `.admin-sidebar .admin-sidebar-foot { padding-left: 8px; padding-right: 8px }`.
    - 반응형 `@media (max-width: 680px)` 에서 `.admin-body { grid-template-columns: 1fr }` → `.admin-shell { grid-template-columns: 1fr }` 로 정렬.
    - `.sidebar-brand` rule (TASK-0066 신설, index.html 의 `.sidebar` 에서만 사용) 은 그대로 재사용 — admin.html 의 sidebar 안에서도 동일 스타일 (52px height, border-bottom).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0006 / TASK-0068 / CHG-20260518-0005 / REV-20260518-0005 entries.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS
  - `SKIP_INIT=1 make web` 재배포 OK
  - DOM 검증 (browser headless `/admin`): `refreshBtnPresent = false`, `logoutBtnPresent = false`, `backBtnPresent = true`, `brandInSidebar = true` (sidebar-brand 가 admin-sidebar 안에 mount), `adminColumnPresent = true`, `oldAdminBodyPresent = false`, `topbarHeight = 52` (var(--topbar-h)), `topbarInfoText = "관리 콘솔 ... 시스템 프롬프트 운영"`, `gridCols = "220px 1060px"` (sidebar 220 + 나머지).
  - Screenshot `/tmp/admin-merged.png`: 좌측 admin-sidebar (brand "MA MySQL AI" + 대시보드 (active) + 계정 카테고리 (계정 26 / 역할 5) + 제품 카테고리 (제품 3) + pending 변경 0건 footer) / 우측 admin-column (topbar "관리 콘솔" 좌측 정렬 제목 + 부제 + 우측 끝 "작업 화면" 버튼만 / Overview 운영 현황 metric cards / 변경사항 0건 commit bar) — 작업 화면과 100% 일관된 ChatGPT 패턴.
- Trace: REQ-20260518-0006 → TASK-0068 → CHG-20260518-0005 → REV-20260518-0005 (follow-up of TASK-0066 / 0067)

## CHG-20260518-0004
- Date: 2026-05-18
- Summary: TASK-0067 (REQ-20260518-0005, Minor §12.3 — UI 위치 이전 + native select → custom dropdown 전환. backend / endpoint / RBAC / 데이터 영역 무변경.) 사용자 직접 테스트 follow-up — TASK-0066 의 layout 통합 후 사이드바도 채팅 영역처럼 확장하기 위해 `제품 칩` 을 사이드바에서 composer 의 우측 (textarea 와 send 버튼 사이) 으로 이전. ChatGPT 의 모델 선택 UI 패턴 — chip 클릭 시 drop-up dropdown 으로 옵션 표시 + 선택 시 즉시 적용 + chip label/dot 갱신.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`
    - `.sidebar-head` 의 `.product-chip-wrap` (caption + label.product-chip + select 형태) 제거. `.sidebar-head` 에는 `#newConversationBtn` 만 남음 → 사이드바 vertical 공간 확장.
    - `.composer-box` 안 textarea 와 `#sendBtn` 사이에 `.composer-product-chip-wrap` 신설 — `button#productChip` (dot + label + arrow) + `div#productDropupMenu.product-dropup-menu`.
    - chip 의 기존 ID 보존 (`productChip`, `productChipDot`) + 신규 ID (`productChipLabel`, `productDropupMenu`).
    - cache-bust `v=20260518-topbar-merge` → `v=20260518-product-composer`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `renderProductChip()` 재작성 — 기존 native `<select id="productSelect">` 의존 (renderProductOptions 호출) 제거. 새 chip 의 dataset.mode / label / aria-label / busy 시 disabled 갱신. menu 가 열려 있으면 `renderProductDropupMenu()` 도 즉시 갱신해 옵션 list 동기화.
    - chip label 정책: pinned 시 `compactLabel = product_key` (chip width 보존), aria-label 은 `fullLabel = "{name} ({key})"` (a11y 보존).
    - 신규 `renderProductDropupMenu()` — section head ("이 대화의 제품") + auto item + products 의 pinned items 렌더. `state.products` 변경 시 menu open 중에도 즉시 반영.
    - 신규 `buildProductDropupItem({mode, pid, label, selected})` — `role="menuitem"`, dot + label + check svg, click handler 가 closeProductDropup + setActiveProduct 호출.
    - 신규 `openProductDropup()` / `closeProductDropup()` — menu visibility + chip `aria-expanded` 동기화 + outside-click (mousedown capture, setTimeout 0 으로 trigger click 충돌 방지) + ESC 닫기.
    - DOM ready 의 기존 `productSelect` change handler 제거. 신규 `#productChip` click handler 가 dropdown toggle.
    - `setActiveProduct` 본체 무변경 — backend `PATCH /api/conversations/{cid}/product` 호출, optimistic state 갱신, toast 메시지 모두 그대로.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - 신규 `.composer-product-chip-wrap` (relative + flex 끝 정렬), `.composer-product-chip` (pill: 30px height, padding 0 9px, border 1px, hover/expanded 시 primary 색 강조, busy 시 opacity .5), `.composer-product-chip-dot` (7px 원, mode=auto 회색 / mode=pinned 파랑), `.composer-product-chip-label` (max-width 130px ellipsis).
    - 신규 `.product-dropup-menu` (`position: absolute; right: 0; bottom: calc(100% + 6px); z-index: 50; min-width: 220px; max-width: 280px; max-height: 320px; overflow-y: auto`) — chip 위로 펼침 (drop-up).
    - 신규 `.product-dropup-item` + `.is-selected` + `.product-dropup-item-dot` + `.product-dropup-item-label` + `.product-dropup-item-check` (svg checkmark, selected 시만 opacity 1) + `.product-dropup-section-head` (소형 caps).
    - `.composer-box` 의 `gap: 8px` → `gap: 6px` 로 조정 (chip + send 간 간격 자연스럽게).
    - 기존 `.product-chip-wrap` / `.product-chip` / `.product-chip-caption` / `.product-chip-select` rule 은 stylesheet 에 남아 있으나 사용처가 사라져 dead code (제거는 별 cycle).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0005 / TASK-0067 / CHG-20260518-0004 / REV-20260518-0004 entries.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `SKIP_INIT=1 make web` 재배포 OK
  - DOM 검증 (browser console): `chipInComposer = true` (chip 이 composer-box 안), `oldSelectPresent = false` (기존 native select 부재), `oldWrapPresent = false` (sidebar product-chip-wrap 부재), `sidebarHeadChildren = ["BUTTON.btn-new-conv"]` (sidebar-head 가 새 대화 버튼만), `chipLabel = "auto"`, `chipMode = "auto"` (hydrate 정상).
  - 동작 검증: chip click → menu 표시 (4 items: auto + KR + MV + GZ_KR, auto selected), `dropUp = true` (menuY=459 < chipY=644 — drop-up 보장), KR item click → menu close + chip 갱신 (`chipMode=pinned, chipLabel="KR", chipAriaLabel="이 대화의 제품 선택, 현재 킹스레이드 (KR)"`) + toast "제품을 킹스레이드로 바꿨어요. 다음 답변부터 적용됩니다.". backend endpoint `PATCH /api/conversations/{cid}/product` 정상 호출.
- Trace: REQ-20260518-0005 → TASK-0067 → CHG-20260518-0004 → REV-20260518-0004 (follow-up of TASK-0066)

## CHG-20260518-0003
- Date: 2026-05-18
- Summary: TASK-0066 (REQ-20260518-0004, Minor §12.3 — UI layout 재구조화, RBAC / endpoint / 데이터 영역 무변경) TASK-0065 follow-up. 사용자 직접 테스트 피드백: 헤더 4 버튼 제거 후 `.chat-header` 가 거의 비어 있어 `.topbar` (관리 콘솔) 와 영역 통합 필요. ChatGPT 패턴으로 layout 재구조화 — sidebar 가 전체 height, brand (`[MA] MySQL AI`) 를 sidebar 의 첫 영역으로 이전, topbar (대화 제목 + 관리 콘솔) 을 chat-column 의 첫 영역으로 이전, chat-header 폐기로 채팅 영역 확장. 대화 제목은 좌측 정렬 (사용자 명시 — 중앙 정렬 금지).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`
    - `.app-shell` 내 grid 구조 재정의:
      - 기존: `.topbar` (전체 너비) + `.app-body` (sidebar + chat-pane)
      - 신규: `.sidebar` (column 1, 전체 height) + `.chat-column` (column 2, 전체 height) — `.app-body` wrapper 폐기.
    - `.topbar-brand` 를 `.sidebar` 의 첫 child `.sidebar-brand` 로 이전 (brand icon + name).
    - 신규 `.chat-column` 안에 `.topbar` (대화 제목 + tools + 관리 콘솔) → `.chat-pane` 순서.
    - `.chat-pane > .chat-header` 폐기 — `.chat-title` / `.chat-subtitle` / `#loadMoreBtn` 은 `.topbar > .topbar-info` / `.topbar-tools` 로 이전. `#openAdminBtn` 은 `.topbar-end` 위치 유지.
    - cache-bust `v=20260518-header-cleanup` → `v=20260518-topbar-merge`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.app-shell` 의 `grid-template-rows: var(--topbar-h) minmax(0, 1fr)` → `grid-template-columns: var(--sidebar-w) minmax(0, 1fr)` (단일 row, 2 column).
    - `.app-body` rule 폐기 (HTML 에서 wrapper 제거됨).
    - `.chat-column` 신설 — `display: flex; flex-direction: column; min-width: 0; overflow: hidden`.
    - `.sidebar-brand` 신설 — `padding: 0 14px; height: var(--topbar-h); border-bottom: 1px solid var(--border-subtle)`. topbar 와 baseline (y=52px) 정렬.
    - `.topbar` rule 갱신 — `padding: 0 20px; height: var(--topbar-h); flex-shrink: 0`. 기존 topbar-brand min-width 제거 (brand 가 sidebar 로 이전됨).
    - `.topbar-info` 신설 — `display: flex; flex-direction: column; min-width: 0; flex: 1 1 auto` (좌측 정렬, justify-content 미설정).
    - `.topbar-tools` 신설 — `display: flex; align-items: center; gap: 6px; flex-shrink: 0` (loadMoreBtn 등).
    - `.topbar-end` 기존 유지 (관리 콘솔, `margin-left: auto`).
    - `.chat-header` / `.chat-header-info` / `.chat-header-tools` rule 폐기. `.chat-title` / `.chat-subtitle` typography rule 만 유지 (topbar-info 안에서 사용).
    - 반응형 `@media (max-width: 680px) { .app-body { ... } }` → `.app-shell { grid-template-columns: 1fr }` 로 변경.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0004 / TASK-0066 / CHG-20260518-0003 / REV-20260518-0003 entries.
- Verification:
  - DOM 검증: `.app-shell` gridTemplateColumns = `"252px 1028px"` (sidebar-w + 나머지), `.sidebar-brand` 정상 mount + 텍스트 "MA MySQL AI", `.topbar` mount + height 52px, `.topbar-info` mount, 기존 `.chat-header` DOM 부재.
  - Browser smoke (`gstack /browse` headless + screenshot `/tmp/layout-merged.png`): sidebar 좌측 (brand + 제품 칩 + 새 대화 + conv list + 프로필) / chat-column 우측 (topbar 제목 좌측 정렬 + `최근 갱신 ... 메시지 22 · 소유자 admin` 부제 + 우측 끝 `관리 콘솔` 버튼) — ChatGPT 패턴 정확 구현. brand 와 topbar 의 baseline (y=52px) 정렬. sticky 날짜 분기선 ("2026년 4월 16일") + per-conversation "···" trigger 등 직전 cycle 변경사항 무회귀.
  - JS 변경 없음 — 모든 element ID 보존 (conversationTitle / conversationSubtitle / loadMoreBtn / openAdminBtn 모두 getElementById 동작).
- Trace: REQ-20260518-0004 → TASK-0066 → CHG-20260518-0003 → REV-20260518-0003 (follow-up of TASK-0065)

## CHG-20260518-0002
- Date: 2026-05-18
- Summary: TASK-0065 (REQ-20260518-0003, Minor §12.3 — UI 정리 + sticky 분기선) TASK-0063 직접 테스트 follow-up. (1) 헤더의 대화 복사 / 공유 / 제목 변경 / 삭제 4 버튼 제거 (per-item "···" menu 로 일원화). (2) menu trigger 우측 상단 → 우측 하단 이동 (badge "내/sales" 우측 상단 영역과 시각 충돌 해결). (3) 채팅 로그 날짜 분기선에 `position: sticky; top: 0` 적용 — Slack 패턴. 사용자가 분기선까지 scroll 할 필요 없이 현재 시야의 날짜 그룹 헤더가 messageLog 상단에 stick 되고 click 시 캘린더 popover anchored 진입.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`
    - `chat-header-tools` 의 `forkConversationBtn` / `shareConversationBtn` / `renameConversationBtn` / `deleteConversationBtn` 4 element 제거. `loadMoreBtn` 만 유지 (이전 기록 — 별 기능).
    - cache-bust `v=20260518-conv-menu` → `v=20260518-header-cleanup`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - 4 element 의 `getElementById` 변수 선언 (line 56/59/60/61) 제거.
    - `toggleConversationActionButtons` 류 가시성 로직 (line 2492 ~ 2530) 의 4 element 관련 분기 (35 lines) 삭제. cancel/finalize 만 남음.
    - DOM ready 의 4 element click handler (line 3837 ~ 3860) 삭제. backend helper (`deleteConversation` / `renameCurrentConversation` / `forkConversation` / `createConversationShare`) 는 conv-item "···" menu 의 makeItem handler 가 cid 인자로 직접 호출하므로 유지.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.conv-item` 에 `padding-right: 32px` 추가 (trigger 22px + margin 10px 확보).
    - `.conv-item-menu-trigger` 의 `top: 6px` → `bottom: 6px` (위치 우측 하단으로 이동).
    - `.message-date-divider` 에 `position: sticky; top: 0; z-index: 5` + `padding: 4px 0` (sticky 안정성). label 의 배경 `var(--surface-2)` → `var(--surface-1, #ffffff)` 로 조정 (sticky 시 message bubble 위에 자연스럽게 떠 보이도록 불투명도 강화) + `box-shadow: 0 1px 2px rgba(0,0,0,.04)` 추가. hover 시 `box-shadow: 0 2px 6px rgba(37,99,235,.18)` 로 elevation 강화.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0003 / TASK-0065 / CHG-20260518-0002 / REV-20260518-0002 entries.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `SKIP_INIT=1 make web` 재배포 OK
  - Browser smoke (`gstack /browse` headless): (1) 헤더 4 버튼 부재 확인 (snapshot 의 `chat-header-tools` 영역에 `loadMoreBtn` + product selector 외 추가 버튼 없음), (2) active conv-item 의 "···" trigger 가 bottom=6px / right=6px / opacity=1 로 우측 하단 정상 위치 (DOM `getComputedStyle` 확인), (3) 2 분기선 conversation 에서 `messageLog.scrollTop = 600` 깊이 스크롤 시 첫 분기선 "2026년 4월 15일" 이 messageLog 상단에 stick (screenshot `/tmp/sticky-scrolled.png` 첨부) — Slack 패턴 정확 구현.
- Trace: REQ-20260518-0003 → TASK-0065 → CHG-20260518-0002 (follow-up of TASK-0063 / CHG-20260518-0001)

## CHG-20260518-0001
- Date: 2026-05-18
- Summary: TASK-0063 (REQ-20260518-0001, **Major** §12.3 — RBAC catalog 확장 2건 + 신규 endpoint 1건 + 파괴적 액션 menu 통합) 작업 화면 대화 항목별 "···" menu (복사 / 공유 / 제목 변경 / 삭제) + 캘린더 시간 이동을 채팅 로그 날짜 분기선 click trigger 로 이전. ChatGPT / Slack UX 패턴 정렬.
- Decisions (사용자):
  - 복사 = full self-fork (`_fork_conversation_impl` 재활용, 메시지+첨부+SQL 결과 + 활성 대화 자동 전환).
  - 신규 권한 `conversation.duplicate.own` / `conversation.duplicate.any` 분리 추가 (rename/delete 일관성).
  - 헤더 `shareConversationBtn` 유지 (active 대화의 quick share path) — per-item menu 와 dual entry.
  - 헤더 `historyCalendarBtn` 제거 — 캘린더 trigger 는 채팅 로그의 날짜 분기선이 단일 진입점. 먼 과거 jump 는 popover header 의 ‹ › (월) + « » (년, 데이터가 1년 이상일 때만) 로 해결.
- Outside voice review: Codex (general-purpose subagent, 10 blindspot 보강 — risk 1 admin/operator/sales catchup loop 일반화, risk 2 IsDynamic NULL legacy schema 는 별도 cycle followup, risk 3 fast-path hydration call site 정합, risk 5 share-token bypass 차단 (read-gate 명시 호출), risk 6 403 vs 404 metadata leak 차단 (rename/delete 와 동일 wording), risk 7 `.any` superset semantics backend mirror, risk 8 frontend hide-vs-disable — rename/delete pattern (visible + is-access-blocked + toast) 채택, risk 9 PERMISSION_LABELS / PERMISSION_DESCRIPTIONS / requiredPermissionsFor 3 곳 갱신, risk 10 사본 제목 grapheme-safe truncation).
- Catchup 순서 fix: `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출을 `_ensure_seed_roles` 앞으로 옮김. 기존 호출 순서로는 `_ensure_seed_roles` 의 admin/operator/sales catchup loop 이 `_permission_id_map(conn)` 으로 신규 권한 id 를 lookup 할 때 catalog 에 아직 INSERT 안 되어 0 을 받아 skip 하던 회귀 (Codex risk 3 변형).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - `PERMISSION_DEFINITIONS` 에 `conversation.duplicate.own` / `conversation.duplicate.any` 2건 추가 (catalog 34 → 36, group=conversation).
    - `SEED_ROLE_DEFINITIONS` operator/sales 에 `conversation.duplicate.own` grant. admin 은 `set(PERMISSION_CODES)` 으로 자동 포함.
    - `_ensure_seed_roles` 의 admin catchup tuple 에 `conversation.duplicate.own/.any` 추가. operator/sales catchup loop 을 `(share.create, duplicate.own)` 리스트 기반으로 일반화 (Codex risk 1).
    - `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출을 `_ensure_seed_roles` 앞으로 이동 (Codex risk 3 변형 fix).
    - 신규 endpoint `POST /api/conversations/{cid}/duplicate` — read-gate 먼저 (404 단일 wording, Codex risk 5/6), `.any` superset semantics (Codex risk 7), `_fork_conversation_impl` 재활용, 제목은 grapheme-safe `사본: <base[:256-len('사본: ')]>` (Codex risk 10).
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `PERMISSION_LABELS` / `PERMISSION_DESCRIPTIONS` 양쪽에 duplicate 2건 추가 (Codex risk 9).
    - `requiredPermissionsFor` switch 에 `conversation.duplicate` / `conversation.share` case 추가.
    - `renameCurrentConversation(cid)` / `deleteConversation(cid)` / `createConversationShare({conversationId})` 시그니처를 cid 인자 수용 가능하도록 확장 (backward compat).
    - 신규: `duplicateConversationFromMenu(cid)` (RBAC + create 권한 사전 gate + apiFetch POST).
    - 신규: `openConversationItemMenu(cid, triggerEl)` / `closeConversationItemMenu()` — fixed-position dropdown (z=200) + a11y (role=menu/menuitem, aria-haspopup, aria-expanded) + outside-click (setTimeout 0 으로 trigger click 충돌 방지) + ESC + scroll/resize close + viewport edge clamping.
    - `renderConversationList()` 의 conv-item 마다 `.conv-item-menu-trigger` 추가 (hover 시 fade-in, active 시 상시 표시) + click handler toggle + keyboard (Enter/Space).
    - `renderMessages()` 에 `.message-date-divider` 삽입 (createdAt 비교, 첫 등장만) + click → `openHistoryCalendarAt(dateKey, divider)`.
    - `openHistoryCalendar` → `openHistoryCalendarAt(dateKey?, anchorEl?)` 로 리팩토링. anchorEl 가 주어지면 popover 를 fixed-position 으로 분기선 하단에 mount + viewport clamping.
    - `calendarDateBounds()` 신설 — `(oldest, newest)` 키 추출. 년 jump 버튼 (« ») 노출 조건 = `(newestYear - oldestYear) >= 1`.
    - `renderHistoryCalendar()` 의 popover header 에 동적 nav 슬롯 (`#calendarNav`) 렌더 — `‹ › [Y년 M월] (« »)` + cursor 가 oldest/newest 범위를 넘으면 disabled.
    - 헤더 historyCalendarBtn 의 가시성 토글 + click handler + outside-click pair 제거. outside-click 은 popover 외부 + `.message-date-divider` 외부 click 일 때만 닫음.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `historyCalendarBtn` 삭제, popover header 를 `#calendarNav` slot + hidden `#calendarTitle` (backward compat) 로 교체. cache-bust `v=20260518-conv-menu`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.conv-item-menu-trigger` (absolute 위치, hover/active fade), `.conv-item-menu` (fixed, z=200, shadow), `.conv-menu-item` + `.is-danger` + `.is-access-blocked`, `.message-date-divider` + label (Slack pill 패턴, before/after horizontal line), `.history-calendar-nav` + `.calendar-nav-btn` + `.calendar-nav-title` (월/년 nav).
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS
  - `SKIP_INIT=1 make web` 재배포 OK (buildx provenance race 우회는 기존 dc-build 가드 동작).
  - DB 직접 확인: `agent_memory.WebPermissions` 의 `conversation.duplicate.own/.any` row hydrate 확인. 신규 role grant — admin (duplicate.any + duplicate.own), operator (duplicate.own), sales (duplicate.own).
  - Browser smoke (gstack `/browse` headless): 좌측 conv-item 마다 "···" trigger 표시, click → 4 menu 항목 (복사 / 공유 / 제목 변경 / 삭제 — danger 색) 정상 mount + outside-click + ESC close 동작. 채팅 로그에 "YYYY년 M월 D일" 분기선 표시 (메시지 2 일 이상), click → popover anchored 오픈, 월 nav (‹ ›) 정상 (현재 데이터 1년 미만이라 « » 조건 충족 안 됨 = 정상). 헤더 historyCalendarBtn 부재 확인.
- Trace: REQ-20260518-0001 → TASK-0063 → CHG-20260518-0001

## CHG-20260515-0005
- Date: 2026-05-15
- Summary: TASK-0062 (REQ-20260515-0011 / REQ-20260515-0012, Minor §12.3) — 사용자 GOAL 2026-05-15 후속 2 항목.
  - **다중선택 UX 개선**: `.conv-item-checkbox` 제거 → Ctrl/Meta toggle + Shift range 만으로 다중 선택. 일반 click 은 단일 선택 + `state.conversationSelected.clear()` + `state.conversationLastClickIdx = -1`. `renderConversationBulkBar()` 의 노출 임계값 `count >= 1` → `count >= 2`. 즉 2 개 이상 선택 시에만 bar 가시.
  - **Point rail 위치 비례 분포**: `.message-point-rail` 을 `flex column` → `position: relative` 로 변경. 각 `.message-point-dot` 가 `position: absolute; left: 50%; top: <pct>%; transform: translate(-50%, -50%)`. `pct = (msg.offsetTopInLog + msg.height/2) / messageLog.scrollHeight * 100`. 신규 helper `layoutMessagePointRail()` 가 `renderMessagePointRail` 끝 + resize listener 에서 재계산. `.is-active` 의 transform 도 `translate(-50%, -50%) scale(1.8)` 로 보정 (좌측 튐 방지).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js` — `renderConversationList` 의 checkbox block 제거 + 일반 click 의 `conversationSelected.clear()` 추가 + `renderConversationBulkBar` 임계값. `renderMessagePointRail` 끝에 `layoutMessagePointRail()` 호출 + helper 신설 + resize handler 가 layout + highlight 둘 다 호출.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.message-point-rail` (flex/gap/padding/overflow 제거 + relative 추가), `.message-point-dot` (position absolute + transform translate), `.message-point-dot.is-active` (translate + scale 합성), `.conv-item-checkbox` rule 제거, `.conv-item.is-multi-selected` outline-offset -1px 보강.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` + `admin.html` — cache-bust `v=20260515-task-0062`.
  - `repo/unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — REQ-20260515-0011 / REQ-20260515-0012 + AC-0108 ~ AC-0113 추가.
  - `repo/unit/feature-0003-agent-web-ui/docs/TASK.md` — Task Queue entry 추가.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS
  - (browser smoke 는 후속 단계에서 make web 재배포 후 진행)
- Trace: REQ-20260515-0011 / REQ-20260515-0012 → TASK-0062 → CHG-20260515-0005

## CHG-20260515-0004
- Date: 2026-05-15
- Summary: TASK-0061 round 2 — /qa 심층 검증 결과 docs 보강. Phase 4/5 의 사용자 상호작용 흐름 (dot click smooth scroll, 캘린더 월 이동 + day click) 을 browser 자동화 (`make browser-*`, session `483add52718b4a93`) 로 실측 확인. Phase 3/6/8 의 destructive endpoint 는 1차 cycle 의 contract 확정 (응답 형식 / 권한 / DOM 노출) 으로 충분, 운영 환경 실 호출은 사용자 명시 시점에 별도 진행 권고. round 2 신규 발견 이슈 0 건.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/docs/REPORT.md` — round 2 검증 결과 summary 라인 prepend.
  - `repo/unit/feature-0003-agent-web-ui/docs/TEST.md` — round 2 test run history entry prepend (Phase 4/5 deep + Phase 3/6/8 contract 정합 메모).
- Verification:
  - browser session `483add52718b4a93`, screenshot `/shared/out/browser/shot_20260515_091222.png`.
  - 대화 `20260515080029-a5353434` (2 메시지), Point rail dot click → `messageLog.scrollTop=245 → smooth scroll`, active dot id `291` 갱신.
  - 캘린더 popover title 2026년 5월 ↔ 4월 prev/next 이동, day "15" click → 시각 list 1개 표시.
- Trace: TASK-0061 → CHG-20260515-0003 → CHG-20260515-0004 (post-ship QA round 2).

## CHG-20260515-0003
- Date: 2026-05-15
- Summary: TASK-0061 (REQ-20260515-0003 ~ REQ-20260515-0010, **Major** §12.3 — UI 상태 / 인증(비밀번호 초기화) / 파괴적 데이터(bulk delete) 일괄 변경) GOAL.md 8 항목 합본 cycle.
- Phases:
  - Phase 1+2: 답변 버블 내부 실시간 step 진행상황 + 신규 대화 첫 요청 즉시 polling 연결 (state.pendingBubble + renderPendingAssistantBubble + 1초 elapsed timer + applyProgressPayload 동기화 + sendPrompt lazy-create 분기에서 cid 발급 즉시 polling start).
  - Phase 3: 끊긴 processing 대화 만료 감지 + 붉은 badge — backend `_compute_display_status(conn, conversation_id, last_status, last_status_at, last_status_run_id)` + `_last_step_at_for_run` + `_parse_kv_timestamp` helper. env `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` (20분). `_list_conversations` payload 에 `display_status` / `raw_status` / `is_stale` 추가. `/api/progress` / `_build_ask_status_snapshot` / `/api/ask_status` / `/api/ask_result` long-poll 일관 stale 처리. frontend `.conv-dot.is-stale-error` + tooltip + bubble error 영역 + 1회 toast 안내.
  - Phase 4: 우측 Point rail (`#messagePointRail` + `renderMessagePointRail()` + scroll observer → `highlightActivePoint()` + click → `scrollIntoView smooth`). 좁은 화면(`max-width:720px`) hidden.
  - Phase 5: 캘린더/시각 이동 — backend `/api/history_dates` 가 `AgentMemoryMessages` 정본 기준 (이전 `AgentCoreMessages` 에서 변경). frontend `historyCalendarBtn` + `#historyCalendarPopover` (월간 grid + 시각 목록) + `/api/history_anchor?at=...` jump + `.is-anchor-highlight` 1.5s 강조.
  - Phase 6 (Critical 분면): 관리자 주관 비밀번호 초기화. `WebAccounts.MustChangePassword TINYINT(1) NOT NULL DEFAULT 0` 컬럼 idempotent ALTER (`_ensure_web_tables` slow path + `_ensure_must_change_password_schema` + `_ensure_seed_catchup` fast path). 신규 endpoint `POST /api/admin/accounts/{id}/password-reset` — `secrets.token_urlsafe(12)` 임시비번 + `_hash_password` 저장 + `MustChangePassword=1` + 대상 계정 `WebAuthSessions IsRevoked=1`. self-reset 거부. `_serialize_account` 에 `must_change_password` 필드 + `_fetch_account_rows` 가 `COALESCE(a.MustChangePassword, 0)` SELECT. `/api/auth/me` PATCH 가 비밀번호 변경 성공 시 `MustChangePassword = 0`. frontend `adminPasswordResetBtn` (Account detail) + 1회 표시 modal + 강제 변경 modal (login + initializeWorkspace 직후 must_change_password=true 시 노출).
  - Phase 7: 관리자 select-all 현재 페이지 fix — `currentPageAccounts()` helper 신설. `accountSelectAll` change handler 와 `updateAccountSelectAllCheckbox()` 가 동일 helper 사용해 현재 페이지 row 만 토글. 다른 페이지 선택은 보존.
  - Phase 8: 내 대화 Ctrl/Shift 다중 선택 + bulk delete — `state.conversationSelected: Set<string>` + `state.conversationLastClickIdx`. `renderConversationList()` 의 own 그룹에만 `.conv-item-checkbox` 추가 + Ctrl/Meta toggle + Shift range. `.conv-bulk-bar` (label / 삭제 / 선택 해제). backend `_delete_conversation_impl(conn, account, conversation_id, force, confirm_text)` helper 추출 (단건/일괄 공용) + 신규 `POST /api/delete_conversations` partial success endpoint (`{deleted, deleted_pending, failed:[{conversation_id, reason}], current}`). ≥10 typed-confirm + processing 대화 강제 삭제 confirm.
- Files:
  - backend: `repo/unit/feature-0003-agent-web-ui/src/app.py` — env + helper 추가, `_list_conversations` / `/api/progress` / `_build_ask_status_snapshot` / `/api/ask_result` / `/api/history_dates` / `_delete_conversation_impl` / `/api/delete_conversations` / `/api/admin/accounts/{id}/password-reset` / `_serialize_account` / `_fetch_account_rows` 수정.
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/app.js` — state 확장 + renderMessages + renderPendingAssistantBubble + elapsed timer + applyProgressPayload 동기화 + renderConversationList Ctrl/Shift + renderConversationBulkBar + bulkDeleteConversations + renderMessagePointRail + highlightActivePoint + calendarState + openHistoryCalendar / renderHistoryCalendar / jumpToHistoryAnchor + showForceChangePasswordModal + must_change_password hook in handleLogin/initializeWorkspace + listener wiring.
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/admin.js` — currentPageAccounts + select-all change handler + updateAccountSelectAllCheckbox + renderAccountDetail 의 adminPasswordResetBtn + triggerPasswordResetFlow + showTemporaryPasswordModal.
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `.messages-wrap` / `#messagePointRail` / `#historyCalendarBtn` / `#historyCalendarPopover` / `#conversationBulkBar` 추가 + cache-bust `v=20260515-task-0061`.
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — cache-bust 만 갱신 (button 은 renderAccountDetail 에서 동적 mount).
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — Phase 1~8 신규 클래스 토큰 (pending bubble + stale dot + point rail + history calendar + conv-item-checkbox + conv-bulk-bar + admin-modal + temp-password-display + field-input).
  - env: `repo/.env.example` — `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=` placeholder + 설명.
  - docs: `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS
  - `make web` 재배포 PASS — `repo-web-1 Recreated/Started`
  - browser 검증 (http://web:8000): cache-bust `v=20260515-task-0061` 적용 확인 / `.messages-wrap` / `#messagePointRail` / `#historyCalendarBtn` / `#historyCalendarPopover` / `#conversationBulkBar` 모두 존재 / login 후 conv list 45개 + own checkbox 34개 / bulk bar 1개 선택 시 "1개 선택됨" 라벨 / 캘린더 popover 2026년 4월 + has-messages 1일 (4/22) / `/api/progress` 응답에 display_status·raw_status·is_stale 포함 / `/api/history_dates` 응답 first/last 2026-04-22 / `/api/delete_conversations` 빈 body → 400 validation / pending bubble 강제 렌더 시 spinner + elapsed + bubble DOM 정상 / admin page accountList 15 + currentPageAccounts() 15 + filteredAccounts() 26 (다른 페이지 보존 가능) / 비-bootstrap_admin 계정 detail panel 에 `adminPasswordResetBtn` "비밀번호 초기화" 노출.
- Trace: REQ-20260515-0003 ~ REQ-20260515-0010 → TASK-0061 → CHG-20260515-0003

## CHG-20260515-0002
- Date: 2026-05-15
- Summary: TASK-0060 (REQ-20260515-0002) 실제 접근 가능 DB 분석 기반 Product 시스템 프롬프트 작성 + Role `전 Product 공통` 프롬프트 작성 + runtime 누적 적용 fix.
- Files / Data:
  - `agent_memory.WebSystemPrompts`:
    - Product prompt upsert: `KR / 킹스레이드` (`dbgame,dblog,dbauth`), `MV / 마이크로볼츠` (`account_db,dev_1_1_1_20,have_00,log_v2,global_db`).
    - Role common prompt upsert: `pending`, `operator`, `admin`, `sales`, `dba` 각각 `Scope='role' AND ProductId IS NULL`.
  - `repo/unit/feature-0002-agent-core/src/agent_core.py`: Role `ProductId IS NULL` prompt 를 fallback 이 아니라 공통 누적 지침으로 조립하도록 변경.
  - `repo/unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`: pinned/auto 모드 누적 적용 테스트 추가.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,REVIEW,REPORT,TEST}.md` 및 feature-0002 문서 갱신.
- DB Analysis:
  - `KR`: `dbgame` 98 tables / 약 147만 rows, `dblog` 279 tables / 약 3929만 rows, `dbauth` 9 tables / 약 7977 rows. 주요 확인 범위: `dbgame.player` 2187 rows (`CreatedTime` 2026-04-07~2026-04-23), `dblog.battleend` 813,280 rows, `dblog.item` 12,656,848 rows, `dbauth.accountbasicinfo` 2187 rows.
  - `MV`: `account_db` 6 tables / 약 21.8만 rows, `dev_1_1_1_20` 62 tables / 약 12.6만 rows, `have_00` 50 tables / 약 2520만 rows, `global_db` 28 tables / 약 599 rows, `log_v2` DB 존재 + tables 0. 주요 확인 범위: `account_db.account` 242,973 rows, `have_00.player` 232,922 rows, `have_00.matchhistory` 8,006,486 rows (`rv_created_at` 2023-09-09~2026-05-11).
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
  - SQL readback: Product prompt 2건, Role common prompt 5건 content length 확인.
  - web 컨테이너 내부 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")` 직접 조회로 Product context + Role common guidance 포함 확인.

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

## CHG-20260521-0001
- Date: 2026-05-21
- Related Requirement: TASK-0094, REQ-20260521-0001
- Summary: 첨부 기능 multi-cycle (A CSV ingest + B DDL/KB + C Vision + D PDF RAG) 의 BRIEFING 정본 (Revision 2) 작성 + TASK.md 신규 entry 등재 + PLAN-APPROVED 마커 부여. Codex outside-voice review 2 회 (REV-20260520-0001 1차 + REV-20260521-0002 2차 follow-up) 흡수. 코드 변경 0, 계획 문서만 갱신.
- Files: unit/feature-0003-agent-web-ui/docs/BRIEFING-attachment-multi-cycle.md (신규, 923 lines), unit/feature-0003-agent-web-ui/docs/TASK.md (TASK-0094 entry + Current Status + PLAN-APPROVED 마커), .gitignore (`.context/` 추가).
- Notes: 본 cycle 은 코드/스키마/RBAC catalog 변경 없이 multi-cycle plan 의 정본을 lock-in 한다. 핵심 결정 21 건 (D1~D21):
  - D1 S3-compat MinIO (compose +1 service `minio`). 사내망 다운로드용 signed URL 만 발급, 외부 LLM provider 에는 절대 송신 금지 (D13).
  - D2 sandbox DB = 동일 cluster + 별 schema `agent_attachment_<sha256(conv_id)[:32]>`. `WebConversationAttachmentsSandboxSchemas` mapping table 유지.
  - D3 vector store = PGVector (Postgres 도입 — compose +1 service `postgres`). 단계적 (D10): dev 1차는 agent_memory 와 동일 컨테이너 + DB 분리, prod 는 별 instance 옵션 PLAN gate 재검토.
  - D4 4 시나리오 (A CSV + B DDL/KB + C Vision + D PDF RAG) 전부 진행. 4 sprint 분리. D18 단일 통합 PLAN gate.
  - D5 Codex outside-voice review 2 회 완료 — 1차 17 Valid finding 흡수, 2차 Critical 3 + Major 11 + Minor 2 흡수 (F8 만 사용자 명시 거부).
  - D6 lifecycle 4 종 (user delete / conv soft / admin purge / legal erasure) + tombstone + nullable FK (R-Claim6) + UX 4 state 표면화 (R-F1) + pseudonymous irreversible event id (R-F12).
  - D7 MIME allowlist + archive 거부. D8 size cap (per-file 25MB / per-conv 100MB / per-account 1GB).
  - D9 share derived redact + 기존 token 자동 redact (R-F7 Critical) + `WebShareLinks.PolicyVersion` column.
  - D10 PGVector dev/prod 단계적.
  - D11 consent provider×data_class×purpose + revoke + 재동의 + grouped batch modal (R-F2) + provider Files API lifecycle (R-F13).
  - D12 audit HMAC + extension/size bucket + AST normalized SQL + denied reason + pseudonym cross-ref.
  - D13 외부 LLM bytes = server-side read + base64 inline 또는 Files API. `WebConversationAttachmentProviderFiles` 신규 + post-inference delete (R-F13).
  - **D14 sandbox SQL guard = AST shape allowlist (R-F3 Critical)** — single SELECT/CTE only, FOR UPDATE / LOCK / EXPLAIN ANALYZE / optimizer hint / SLEEP / BENCHMARK / user variable / INTO OUTFILE / LOAD_FILE / information_schema / mysql.* / performance_schema / sys.* 전부 거부. denylist 는 보조 secondary check.
  - D15 wildcard grant 금지 + writer 최소권한 (CREATE/ALTER/INSERT/SELECT) (R-Claim4) + grant drift health endpoint `/api/admin/health/attachment-grants` + 주기 reconciliation (R-F4).
  - D16 attachment_ids selected-only + lazy-create attachment snapshot (R-F5) — busyKey/pending sentinel 에 snapshot 저장.
  - D17 UploadStatus 7 값 + retrieval-time policy (R-F6) — partial_indexed 문서 answer meta degraded_sources / UI banner / LLM system note / OCR follow-up.
  - **D18 단일 통합 PLAN gate** — Codex F8 의 1A/1B/1C 분할 권고 사용자 명시 거부. 위험 격리는 D14 + R-Claim4 + R-F4 + D20 조합으로 충족.
  - **D19 `WebAttachmentDerivedMessages(AttachmentId, MessageId, DerivationType, CreatedAt)` join table** (R-F11) — many-to-many 정규화, share redact/audit/fork 의 source-of-truth.
  - **D20 MinIO dual-key rotation runbook** (R-F9) — old/new 24h dual window + canary write/read/delete + 컨테이너 순차 재기동 + rollback + audit `attachment.storage.key_rotation`.
  - **D21 pending role attachment metadata-only** (R-F14) — bytes download 는 승인 후, audit `attachment.bytes_download.denied_pending` 기록.
- Impact: Sprint 1 (Cycle 0 Foundation + Cycle 1 CSV ingest) implementation 진입 가능. D14 SQL allowlist guard 통과가 Sprint 1 ship 조건. 코드 변경은 별 worktree `ai/claude/0087/sprint-1-foundation-csv` (또는 `0094/sprint-1-...`) 에서 진행. 본 cycle 자체의 코드/스키마/RBAC catalog 영향 0.
- Rollback Notes: 본 변경은 문서 only. revert 시 BRIEFING 신규 파일 삭제 + TASK.md 의 TASK-0094 entry + PLAN-APPROVED 마커 + Current Status 갱신 revert + .gitignore 의 `.context/` 한 줄 revert. revert 후 Sprint 1 진입은 BRIEFING/계획 재작성 필요.

## CHG-20260521-0002
- Date: 2026-05-21
- Related Requirement: TASK-0094 cleanup follow-up (AGENTS.md §16.5 Step 6 사후 동기화 결과 기록)
- Summary: TASK-0094 PLAN-APPROVED cycle (CHG-20260521-0001, PR #40 merged 2026-05-21T02:15:30Z) 의 §16.5 Step 6 결과 기록 보강. CHG-20260521-0001 본 PR 에서 누락된 REPORT.md §1 Summary 의 cycle entry + Git 동기화 결과 표 append. 추가 코드 변경 0.
- Files: unit/feature-0003-agent-web-ui/docs/REPORT.md (§1 Summary 상단에 TASK-0094 entry + Git 동기화 결과 표), unit/feature-0003-agent-web-ui/docs/MODIFY.md (본 entry), unit/feature-0003-agent-web-ui/docs/REVIEW.md (REV-20260521-0002 [SKIPPED:report-sync-only]).
- Notes: 단순 운영 기록 follow-up. AGENTS.md §16.5 Step 6 의 결과 기록을 본 cycle 의 첫 PR 에 포함하지 못한 누락 보강. outside-voice review 추가 호출 없음 (REPORT.md 의 단순 사실 append 는 SUBAGENT review 대상 아님 — SKIPPED).
- Impact: docs only. backend / RBAC / 스키마 영향 0.
- Rollback Notes: REPORT.md TASK-0094 entry 한 블록 revert 로 즉시 복구 가능. MODIFY/REVIEW 의 본 entry 도 함께 revert.

## CHG-20260521-0003
- Date: 2026-05-21
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 1 — Pre-flight (ADR + compose + env + bootstrap script + platform-runtime ANCHOR)
- Summary: 첨부 기능 multi-cycle Sprint 1 Cycle 0 진입 인프라 사전 작업. ADR-0022 (MinIO 도입) + ADR-0023 (sandbox schema + D15 maintenance path 분리) + ADR-0025 (PGVector for attachment Sprint 4 prerequisite) 등재. docker-compose.yml 에 `minio` + `minio-init` service 추가. `.env.example` 16 변수 추가 (MinIO 7 + 호스트 port 2 + browser redirect 1 + ATTACHMENT_MAX_BYTES_* 3 + ATTACHMENT_AUDIT_HMAC_KEY 1 + SANDBOX_SQL_* 2). `unit/feature-0003-agent-web-ui/src/scripts/minio-init.sh` 신설 (idempotent bucket + bucket-scoped policy + app key bootstrap). feature-0001-platform-runtime ANCHOR §1 갱신.
- Files:
  - `docs/DECISIONS.md` — ADR-0022/0023/0025 신설 (3 ADR, 약 56 lines)
  - `docker-compose.yml` — `minio` + `minio-init` 2 service 추가 (약 50 lines)
  - `.env.example` — MinIO + attachment + sandbox 섹션 추가 (41 lines, 16 vars)
  - `unit/feature-0003-agent-web-ui/src/scripts/minio-init.sh` — 부트스트랩 신규 (130 lines, mc-based)
  - `unit/feature-0001-platform-runtime/docs/ANCHOR.md` — §1 비-MySQL service platform 책임 명시 항목 추가
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Sprint 1 Phase 1~12 breakdown + Phase 1 [x] 표시 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0003 entry
- Notes: Phase 1 은 코드 직접 변경 (Python / JS) 없이 인프라 / 정책 / 부트스트랩만. Phase 2~12 가 schema / RBAC / storage wrapper / API / UI / share / lifecycle / sandbox / ingest / SQL guard 본격 작업. **D14 SQL allowlist guard 통과** 가 Sprint 1 ship 조건 (Phase 12).
- Impact:
  - 본 Phase 1 ship 후 dev 환경에서 `make up` 또는 `docker compose up -d` 시 minio + minio-init 함께 가동. minio-init 부트스트랩 1 회 완료 후 minio API endpoint (`minio:9000`) 에서 app key 인증 가능. `agent-attachments` bucket 생성 확인 가능.
  - 본 Phase 1 자체는 backend / RBAC catalog / 스키마 영향 0. Phase 2 진입 시 `_ensure_web_conversation_attachments_schema(conn)` 등 helper 와 schema column 신설.
  - 실제 attachment upload / ingest / SQL 실행 path 는 Phase 5/11/12 ship 까지 unavailable (사용자에게는 영향 없음).
- Rollback Notes:
  - ADR-0022/0023/0025 의 status 를 `superseded` 또는 `rejected` 로 갱신.
  - docker-compose.yml 의 `minio` + `minio-init` service block 제거.
  - `.env.example` 의 MinIO/attachment/sandbox 섹션 제거.
  - `unit/feature-0003-agent-web-ui/src/scripts/minio-init.sh` 파일 삭제.
  - `unit/feature-0001-platform-runtime/docs/ANCHOR.md` 의 비-MySQL service 항목 revert.
  - 실제 데이터 영향 0 (Phase 1 은 인프라 / 정책만). minio container volume `../artifacts/minio-data` 도 비어 있어 별도 cleanup 불필요.

## CHG-20260521-0004
- Date: 2026-05-21
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 2 — Cycle 0 schema (5 신규 table + 1 column ALTER)
- Summary: BRIEFING §5.1 정본의 첨부 metadata + sandbox mapping + consent + derived join + provider files lifecycle 5 신규 테이블 + 기존 `WebConversationShares` 에 `PolicyVersion` column (R-F7) idempotent ALTER. 6 helper 신설 + fast/slow path 양쪽 호출 등록. py_compile PASS.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py` — 6 helper 신설 (line 2638~2853, 약 215 lines) + 호출 등록 2 곳 (`_ensure_seed_catchup` line 3037~3047, `_ensure_web_tables` line 3414~3424)
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0210~0215 추가 (6 AC)
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 2 [x] 표시 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0004 [SKIPPED:schema-only] append
- Notes: Phase 2 는 schema only — backend endpoint / RBAC catalog / UI 변경 0. 실제 INSERT / SELECT path 는 Phase 5 (upload API), Phase 8 (share redact), Phase 11 (ingest), Phase 12 (SQL guard) 에서 ship. 5 신규 table 은 모두 빈 상태로 시작 — 본 schema add 자체가 사용자에게는 영향 없음.
- Impact: 부트스트랩 (`_ensure_seed_catchup` fast path + `_ensure_web_tables` slow path) 양쪽에서 신규 helper 가 idempotent 실행. 기존 배포에도 자동 적용. `WebConversationShares.PolicyVersion` column 은 기존 row 에 DEFAULT 1 backfill. backend / RBAC catalog 영향 0.
- Rollback Notes:
  - `unit/feature-0003-agent-web-ui/src/app.py` 의 6 helper 정의 + 호출 등록 revert.
  - 5 신규 table 은 `DROP TABLE IF EXISTS WebConversationAttachments, WebConversationAttachmentsSandboxSchemas, WebAccountConsents, WebAttachmentDerivedMessages, WebConversationAttachmentProviderFiles;` 로 제거 (rollback DDL 단순).
  - `WebConversationShares.PolicyVersion` column 은 `ALTER TABLE WebConversationShares DROP COLUMN PolicyVersion;` 으로 제거 (column 자체는 NOT NULL DEFAULT 1 이라 기존 row 영향 0).
  - 본 Phase 2 가 ship 된 commit 후에 사용자 데이터가 누적되지 않은 시점이라 rollback risk 최소.

## CHG-20260521-0005
- Date: 2026-05-21
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 3 — Cycle 0 RBAC (4 권한 + 6 checklist + D21 pending)
- Summary: BRIEFING §5.2 1~4 row 정합. 첨부 기능 4 권한 코드 (`conversation.attachment.{upload,read}.{own,any}`) catalog 추가 + admin/operator/sales/dba/pending 5 role 모두 catchup + D21 (R-F14) pending metadata-only + app.js label/description map. attachment group 신설은 Phase 12 (Cycle 1 attachment.execute_sql_on.*) 까지 보류.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py` — PERMISSION_DEFINITIONS 4 코드 추가 (line 314~341, 약 28 lines), SEED_ROLE_DEFINITIONS pending/operator/sales 의 permissions set 에 attachment 권한 추가, _ensure_seed_roles 의 admin/operator-sales/dba/pending 4 곳 catchup tuple 갱신.
  - `unit/feature-0003-agent-web-ui/src/static/app.js` — PERMISSION_LABELS (line ~267) + PERMISSION_DESCRIPTIONS (line ~310) 에 4 코드 추가 (각 8 lines).
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0216~0218 (3 AC).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 3 [x] 표시 + Current Status 갱신.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0005 [SKIPPED:rbac-catalog-only] append.
- Notes: 사용자 메모리 정책 "RBAC plan 은 outside voice 필수" 대응 — 본 Phase 3 의 RBAC 변경은 TASK-0094 BRIEFING Revision 2 (Codex outside-voice review 2 회 흡수 lock-in) 의 D6/D11/D12/D14/D15/D16/D21 결정 정합. catalog blindspot 대응은 BRIEFING REV-20260520-0001 Claim #1 (6 checklist) + Claim #3 (정적 catalog source) + REV-20260521-0002 R-F14 (pending metadata-only) 흡수로 이미 정본 review 완료. 사용자 명시 진입 결정에 따라 본 Phase 진행. 후속 plan-eng-review / codex review 는 Phase 12 (D14 SQL guard, Ship 조건) 진입 시점에 권장.
- Impact: 새 catalog 4 코드 + 5 role catchup. 기존 배포에 `_ensure_seed_catchup` fast path 진입 시 자동 INSERT IGNORE. application-level endpoint 는 Phase 5 (upload API) 에서 ship — 본 Phase 3 ship 직후 시점은 권한만 부여, 실제 upload/download 경로 unavailable.
- Rollback Notes: PERMISSION_DEFINITIONS 의 4 코드 entry / SEED_ROLE_DEFINITIONS pending/operator/sales 추가 권한 / _ensure_seed_roles 의 5 catchup 추가 / app.js label/description map 의 4 entry revert. 기존 배포의 WebRolePermissions 에 INSERT 된 row 는 `DELETE FROM WebRolePermissions WHERE PermissionId IN (SELECT Id FROM WebPermissions WHERE Code LIKE 'conversation.attachment.%')` 또는 보존 (catalog 무관 row 는 영향 0).

## CHG-20260522-0001
- Date: 2026-05-22
- Related Requirement: TASK-0097 (REQ-20260522-0001, Minor §12.3) DQA 브랜딩 적용
- Summary: 웹 UI 전체 브랜딩을 'MySQL AI' → DQA (Database Query Assistant) 로 변경. SVG 로고 신설.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — title / auth-title / auth-logo / sidebar brand-icon·name 변경.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` — title / sidebar brand-icon·name 변경.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — 상단 주석 갱신, .auth-logo / .brand-icon background → transparent.
  - `unit/feature-0003-agent-web-ui/src/static/logo-dqa.svg` — 신규 SVG 로고 (48×48, primary #2563eb, DB 실린더+돋보기).
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — REQ-20260522-0001 + AC-0219~0222 등재.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0097 [x] + Current Status 갱신.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260522-0001 [SKIPPED:static-asset-only] append.
- Notes: 정적 자산 변경만. backend / RBAC / endpoint / DB / audit 무변경. docker cp 로 런닝 컨테이너에 즉시 반영 확인 (browse 스크린샷 3장).
- Impact: 브라우저 출력 브랜딩만 변경. 기능 영향 0.
- Rollback Notes: `index.html` / `admin.html` / `styles.css` 의 DQA → MySQL AI 텍스트 revert + `logo-dqa.svg` 제거.

## CHG-20260521-0006
- Date: 2026-05-22
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 4 — Cycle 0 storage wrapper + D20 rotation runbook
- Summary: BRIEFING D1/D13/D20 + R-F9 정합. MinIO S3-compat 첨부 storage wrapper `storage_minio.py` (boto3 기반, idempotent client cache, safe filename + object key, put/get/delete/signed URL/bucket_exists/smoke_test/reset_cache/CLI entry) 신설. D20 dual-key rotation runbook 별 doc. boto3>=1.34.0 / botocore>=1.34.0 requirements 추가.
- Files:
  - `unit/feature-0002-agent-core/src/requirements.txt` — boto3 + botocore 4 줄 추가 (agent 이미지 + web 이미지 공통 dep).
  - `unit/feature-0003-agent-web-ui/src/modules/__init__.py` — modules 패키지 신설 (마커 파일, 약 5 lines).
  - `unit/feature-0003-agent-web-ui/src/modules/storage_minio.py` — 약 350 lines (config + client cache + safe_filename + make_object_key + put/get/delete/signed URL + bucket_exists + run_smoke_test + reset_client_cache + CLI smoke).
  - `unit/feature-0003-agent-web-ui/docs/RUNBOOK-minio-key-rotation.md` — 약 150 lines (6 섹션: 전제/정상 path/rollback/체크리스트/자동화/cross-ref).
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0223~0225 (3 AC, TASK-0097 의 AC-0219~0222 와 충돌하여 본 cycle AC 0223 부터 재번호).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 4 [x] + Current Status 갱신.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0006 [SKIPPED:storage-wrapper-only] append.
- Notes: storage_minio.py 는 thin wrapper — RBAC / consent / audit / size cap / MIME 검증 모두 caller (Phase 5 upload endpoint) 책임. 본 Phase 의 module 은 SDK abstraction 만 제공. 외부 boto3 호출 실패는 모두 StorageOperationError 로 wrap 되어 caller fail-fast. boto3 미설치 환경 (dev/test) 에서는 BOTO3_AVAILABLE=False 로 import 성공 후 `get_s3_client()` 호출 시점에 StorageConfigError 발생 — graceful degradation 정합.
- Impact: 본 Phase 의 module 만 ship — 실제 upload/download endpoint 는 Phase 5 ship 후 가용. requirements.txt 변경으로 docker 이미지 rebuild 필요 (다음 compose up 시 자동). D20 runbook 은 운영자 reference — 실제 rotation 진행은 별 사용자 trigger.
- Rollback Notes: requirements.txt 의 boto3 + botocore 2 entry revert. modules/storage_minio.py + modules/__init__.py + RUNBOOK 파일 삭제 + FUNCTION/TASK/MODIFY/REVIEW 의 본 cycle entry revert. import 한 caller 가 없으므로 (Phase 5 미시작) 즉시 revert 가능.

## CHG-20260521-0007
- Date: 2026-05-22
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 5 — Cycle 0 upload API + audit + HMAC + size cap + D21 deny
- Summary: BRIEFING §5.4 6 endpoint + D7/D8/D11/D12/D13/D21 정합. FastAPI multipart upload (UploadFile/File/Form) + RBAC 검증 + size cap + HMAC categorical 메타 + MinIO put/get + audit dispatch + D21 pending bytes deny. 약 900 lines.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - FastAPI import 에 UploadFile/File/Form 추가
    - `build_audit_change_json` 에 4 신규 ActionCode case (attachment.upload / .delete / .consent.grant / .consent.revoke) — D12 raw filename / bytes 절대 미노출
    - attachment helper 묶음 신설 (`_attachment_size_caps`, `_hmac_filename`, `_extension_bucket`, `_size_bucket`, `_kind_from_mime`, `_account_role_key`, `_account_is_pending`, `_account_can_access_attachment`, `_check_attachment_size_caps`, `_load_attachment_row`, `_serialize_attachment_for_audit`, `_serialize_attachment_for_api`, `_ATTACHMENT_ALLOWED_MIME_TO_KIND` 상수)
    - 6 endpoint 신설:
      * `POST /api/conversations/{cid}/attachments` (multipart upload + MinIO put + INSERT + audit)
      * `GET /api/conversations/{cid}/attachments` (list active)
      * `GET /api/attachments/{id}` (metadata + signed URL re-issue, D21 pending deny)
      * `DELETE /api/attachments/{id}` (soft-delete user reason, audit)
      * `POST /api/account/consents` (D11 grant, UNIQUE upsert, audit)
      * `DELETE /api/account/consents/{id}` (D11 revoke, RevokedAt UPDATE, audit)
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0226~0233 (8 AC)
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 5 [x] + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0007 [SUBAGENT:codex-deferred] (codex review 권장 시점인데 Phase 통합 ship 후 별 cycle 로 분리)
- Notes: 본 Phase 의 endpoint 가 BRIEFING D7/D8/D11/D12/D13/D21 결정의 application-level enforcement — Phase 4 의 storage 모듈 (SDK abstraction) 위에서 보안 결정 적용. 사용자 메모리 정책 "RBAC plan 은 outside voice 필수" 정합 — RBAC 변경은 Phase 3 에서 catalog 작업 완료, 본 Phase 는 catalog enforcement 이라 별 review 우선순위 낮음. 다만 D21 pending bytes deny 의 application-level 분기 (`_account_is_pending`) 는 향후 codex review 권장 항목으로 명시.
- Impact: 본 Phase ship 직후 dev 환경에서 첨부 upload/list/get/delete + consent grant/revoke 가능. MinIO + WebConversationAttachments + WebAccountConsents 모두 활성 — Phase 6 (composer UI) 진입 시 frontend 가 본 endpoint 호출. raw bytes 는 사내망 다운로드만 (signed URL) + 외부 LLM 송신은 Phase 5 unblock 안 됨 (Cycle 2 vision / Cycle 3 KB / Cycle 4 RAG 시점 ship).
- Rollback Notes: 6 endpoint definition + helper 묶음 + audit case 4 모두 revert. 기존 row 는 DB 에 보존 — `DELETE FROM WebConversationAttachments`/`WebAccountConsents` 또는 보존. MinIO bucket 의 객체는 운영자가 별도 `mc rm` 또는 보존.

## CHG-20260521-0008
- Date: 2026-05-22
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 6 — Cycle 0 composer UI (paperclip + drag-drop + pills + D16 snapshot + R-F5 lazy-create)
- Summary: BRIEFING §5.6 + D16 + R-F5 정합. composer 영역에 첨부 UI (paperclip 버튼 + hidden file input + drag-drop overlay + attachment pills + scope-all checkbox) 추가. state.composerAttachments 신규 + helper 7개 + event binding + selectConversation 진입 시 list load.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — composer-wrap 안에 composer-attachments + composer-drop-overlay + attach-btn + file input 추가 (약 25 lines).
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.composer-wrap` position relative + `.composer-attachments` + `.composer-attachment-pill` (selected/uploading/error data-attr 별 스타일) + `.composer-drop-overlay` + `.attach-btn` (약 130 lines).
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - state.composerAttachments 추가 (byConv / uploadingCount / nextLocalId)
    - sendPrompt 의 askBody 에 attachment_ids + attachment_scope_all 명시 (snapshot 호출)
    - helper 7 신설: `_composerAttachmentKey`, `_ensureComposerBucket`, `_composerAttachmentSnapshot`, `_renderAttachmentPills`, `_uploadComposerAttachment`, `_guessKindFromFile`, `_toggleAttachmentPill`, `_loadConversationAttachments`, `_bindComposerAttachmentEvents` (실제 9 helper)
    - initialize 끝에 `_bindComposerAttachmentEvents()` 호출 (paperclip click / file input change / scope-all change / pills toggle / drag-drop)
    - selectConversation 끝에 `_loadConversationAttachments(cid)` 호출 (대화 진입 시 backend ground truth 동기화)
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0234~0240 (7 AC)
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 6 [x] + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0008 [SKIPPED:frontend-only] append
- Notes: lazy-create 상태에서는 paperclip 클릭 시 사용자에게 "첨부는 대화 생성 후 가능" 안내 후 거부 — backend endpoint 가 cid 를 요구하기 때문. 첫 메시지 send 후 (대화 생성 후) 다시 paperclip 클릭 가능. Phase 11 (ingest pipeline) 진입 후 사용자가 실제 LLM 응답에서 CSV/XLSX 의 content 가 활용되는 것을 확인 가능 — 본 Phase 만으로는 attachment_ids 전송만 가능하고 backend `/api/ask` 가 아직 attachment 를 prompt context 에 주입하지 않음 (Phase 11 ship 후 활성).
- Impact: 사용자 view 의 첫 표면화 — 본 Phase ship 후 사용자가 composer 의 paperclip + drag-drop 으로 파일 업로드 가능, pill 로 선택 토글 가능. 실제 LLM context 주입은 Phase 11 ship 후.
- Rollback Notes: index.html 의 신규 마크업 4개 (composer-attachments / composer-drop-overlay / attach-btn / file input) 제거. styles.css 의 신규 130 lines block 제거. app.js 의 state.composerAttachments + 9 helper + binding + load call + sendPrompt askBody 갱신 모두 revert. backend / DB / 권한 영향 0 (Phase 5 endpoint 는 그대로 유지 — Phase 6 revert 만으로 backend 호출 안 됨).

## CHG-20260521-0009
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 7 — D11 consent grouped batch modal (R-F2)
- Summary: Profile Drawer 의 "보안 및 계정" 탭에 consent UI 추가. provider × 3 group grouped batch toggle. GET /api/account/consents endpoint 신규 (POST/DELETE 는 Phase 5 ship).
- Files: app.py (GET /api/account/consents 추가), index.html (#profileConsentSection), app.js (_renderConsentSection + _handleConsentToggle + binding), styles.css (consent UI), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: DB 는 세분 row, UX 는 3 group. R-F2 modal 폭격 위험 해소 정합.
- Rollback: 본 cycle entry revert + #profileConsentSection 마크업/CSS/JS 제거.

## CHG-20260521-0010
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 8 — D9 share redact + R-F7 PolicyVersion 활성
- Summary: WebConversationShares.PolicyVersion column 활성 (INSERT 명시 + SELECT 추출 + redact 로직 분기). attachment_derived 메시지 본문 자동 redact + share.policy.redact_applied audit. 기존 token (Phase 2 ship 시 DEFAULT 1 backfill) 도 배포 즉시 새 정책 적용.
- Files: app.py (_share_redact_message_content / _share_load_messages 갱신 / public_share_view redact dispatch / INSERT PolicyVersion / build_audit_change_json case), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: attachment_derived flag 의 실제 설정은 Phase 11 (ingest) / Cycle 2/3/4 ship 시점. 본 phase 는 mechanism 만 ship.
- Rollback: SHARE_POLICY_VERSION_CURRENT=1 로 reset 또는 redact_active 분기 비활성.

## CHG-20260521-0011
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 9 — F1 delete UX + D6 reconciliation + R-Claim6 tombstone + F12 pseudonym
- Summary: attachment lifecycle reconciliation worker (feature-0002-agent-core) + 4 state 표면화 (_serialize_attachment_for_api) + R-Claim6 tombstone 정합.
- Files: feature-0002-agent-core/src/modules/attachment_reconciliation.py (신규), app.py (_serialize_attachment_for_api 갱신), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: worker scheduling (cron / thread) 은 Phase 10 후속 cycle. 본 phase 는 mechanism + run_once 만.
- Rollback: 모듈 + serialize 변경 revert.

## CHG-20260521-0012
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 10 — 4 MySQL user + R-Claim4 minimal grants + R-F4 drift health
- Summary: .env.example 4 user credentials + modules/sandbox_schema.py (4 helper) + admin health endpoint.
- Files: .env.example, modules/sandbox_schema.py (신규), app.py (GET /api/admin/health/attachment-grants), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: 실제 4 MySQL user 생성 + maintainer 의 wildcard grant 는 운영자가 root 로 사전 진행 (Sprint 1 ship 시 runbook 별도). 본 phase 는 application helper + drift endpoint.
- Rollback: 4 helper module / endpoint / env entry revert.

## CHG-20260521-0013
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 11 — CSV/XLSX ingest pipeline + LLM prompt integration
- Summary: sandbox_ingest.py (ingest_csv + ingest_xlsx + ingest_attachment) + agent_core._build_attachment_context_section + /api/ask attachment_ids env passing.
- Files: feature-0002-agent-core/src/modules/sandbox_ingest.py (신규), agent_core.py (compose_system_prompt 갱신), app.py (/api/ask attachment_ids env), requirements.txt (chardet/openpyxl), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: 실제 ingest 호출은 별 background worker 가 필요 (Phase 5 upload endpoint 가 RowInsert 만 ship, ingest 는 별도 trigger). 본 phase 는 helper + LLM prompt mechanism. Phase 12 의 SQL guard 와 결합 시 사용자 view 의 첨부 기반 SQL 응답 가능.
- Rollback: 모듈/helper/env passing revert.

## CHG-20260521-0014
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 12 — D14 + R-F3 Critical SQL allowlist guard + Sprint 1 Ship
- Summary: sql_guard.py (sqlglot AST allowlist) + attachment.execute_sql_on.{own,any} RBAC + attachment group 신설 + audit ActionCode 3 + FE 상수 갱신. Sprint 1 Critical Ship 조건 충족.
- Files: feature-0002-agent-core/src/modules/sql_guard.py (신규), requirements.txt (sqlglot), app.py (PERMISSION_DEFINITIONS 2 + SEED operator/sales + 3 catchup + build_audit_change_json case 3), app.js + admin.js (PERMISSION_GROUP_ORDER 9 group + label + sections), docs/CONVENTIONS.md §10.6, FUNCTION/TASK/MODIFY/REVIEW.
- Notes: 본 Phase 가 Sprint 1 Critical Ship 조건 충족. validate_sql_for_sandbox 의 실제 호출 (LLM tool 실행 시점) 은 별 cycle 또는 후속 patch — 본 phase 는 guard module + RBAC + audit dispatch 메커니즘 + group 정합.
- Rollback: sql_guard.py + 2 RBAC + group + 3 audit case + FE 상수 + CONVENTIONS revert.

## CHG-20260522-0007 (feature-0008: composer model selector)
- Date: 2026-05-22
- Related Requirement: 사용자 요청 (2026-05-22) — profile drawer 의 API Vault
  잔존 영역 + 모델 선택 UI 를 composer textarea 좌측 `+` dropdown 으로 이전
  (ChatGPT 패턴).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: composer-box 의
    `#attachBtn` (paperclip) 제거 → `#composerActionsBtn` (`+` icon) 신규 +
    `#composerActionsMenu` (primary drop-up popup) + `#composerModelMenu`
    (secondary popup) 추가.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `state.modelCatalog` + `state.selectedModel` 신규 (선택 모델 보존).
    - dead vault code (주석화된 readVaultState 등 함수 정의 161 줄) 일괄 삭제.
    - `_bindComposerAttachmentEvents()` 의 attachBtn 직접 binding → fileInput
      change 핸들러만 유지. `+` 버튼 → primary popup 의 "파일 첨부" 항목으로
      통합.
    - 신규 helpers: `_composerCurrentModel()`, `_updateComposerModelLabel()`,
      `_closeComposerActionsMenus()`, `_openComposerActionsMenu()`,
      `_renderComposerModelMenu()`, `_openComposerModelMenu()`,
      `_bindComposerActionsEvents()`.
    - `sendPrompt()` 의 askBody.model fallback chain: `state.selectedModel` →
      `state.session.default_model` → `state.modelCatalog.default_model` →
      `state.apiVaultOptions.default_model` → literal "claude-sonnet-4".
    - `loadVaultOptions()` 가 `state.modelCatalog` 도 채우고 composer model
      label 즉시 갱신.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.attach-btn`
    rename → `.composer-actions-btn` + 신규 `.composer-actions-menu` +
    `.composer-actions-item` + `.composer-model-menu` + `.composer-model-item*`.
    `.composer-box` 에 `position: relative` (popup anchor).
    반응형 fallback (max-width 720px) — secondary popup 위치 조정.
  - `unit/feature-0003-agent-web-ui/src/static/index.html` + `admin.html`:
    cache-bust `v=20260522-bedrock-cutover` → `v=20260522-composer-model-selector`.
- Impact:
  - UX: ChatGPT-스타일 multi-action `+` dropdown — 첨부 + 모델 선택을 한 곳에
    통합. textarea 좌측 영역 정리.
  - 사용자가 turn 별 모델 (Sonnet 4.6 / Haiku 4.5) 명시 선택 가능 — backend
    default 보다 우선 적용.
  - product chip (composer 우측) 은 별 영역 유지 — product 선택 의도와 모델
    선택 의도가 분리되어 명확.
- Rollback: 본 cycle 의 변경은 frontend-only — revert 시 attach-btn paperclip
  복원 + 모델 selector 제거 + cache-bust 회귀. backend 영향 0.
- Verification:
  - `node --check app.js` PASS.
  - DOM 구조: 12 service docker-compose 무영향. backend `/api/api-vault/options`
    응답 contract 무변경.

## CHG-20260522-0007
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 2 — Cycle 2 Vision Ship (Major §12.3, BRIEFING §6.2)
- Summary: 첨부 image (kind=image) 의 vision 가능 모델 (Claude Sonnet 4 / Haiku 4) inline 송신 + D11 consent gate + D13 base64 inline + D9 share redact + D19 derived join. feature-0007 (bedrock) 머지 위에서 LiteLLM proxy auto-normalize 활용.
- Files:
  - feature-0002-agent-core/src/modules/model_catalog.py (S2.1 — supports_vision flag + model_supports_vision helper + __all__)
  - feature-0002-agent-core/src/modules/llm.py (S2.2 — messages_for_provider helper + __all__ + import)
  - feature-0002-agent-core/src/agent_core.py (S2.3 + S2.6 — _load_attachment_inline_images + _call_llm self-contained injection + mirror_meta attachment_derived flag + imports)
  - feature-0003-agent-web-ui/src/app.py (S2.4 + S2.5 + S2.6 — _prepare_vision_inline_images + _model_to_consent_provider + _has_active_consent + _cleanup_vision_inline + build_audit_change_json case attachment.vision.invoke + ask 안 vision pre-fetch/cleanup/audit dispatch + WebAttachmentDerivedMessages INSERT + model_supports_vision import)
  - feature-0003-agent-web-ui/docs/FUNCTION.md (AC-0280~0285)
  - feature-0003-agent-web-ui/docs/TASK.md (Sprint 2 [x] mark)
  - feature-0003-agent-web-ui/docs/MODIFY.md (본 entry)
  - feature-0003-agent-web-ui/docs/REVIEW.md (REV-20260522-0014/0015)
  - feature-0003-agent-web-ui/docs/TODO-SPRINT-2-PLUS.md (Sprint 2 step 들 [x] mark + Sprint 3/4 인계 정본 보존)
- Notes:
  - **Cross-feature import 회피 (option A)**: storage_minio (feature-0003) 를 agent_core (feature-0002) 가 직접 import 안 함. caller (app.py /api/ask) 가 image bytes pre-fetch + base64 + 임시 file 작성, env `ATTACHMENT_IMAGE_INLINE_PATH` 로 path 만 전달. agent_core 는 path read only.
  - **DB string contract 불변**: messages_for_provider 는 provider 직전 transient 변환 — `AgentMemoryMessages.Content` 는 string 유지. share builder / fork / audit 영향 0.
  - **D11 consent gate**: image 첨부 + vision 가능 모델 시 `(account_id, provider=anthropic, data_class=file_image, purpose=inference)` 의 active row 확인. 미동의 시 409 + `{error_code: "consent_required", consent_required: [...]}` body 응답 (frontend modal trigger).
  - **D12 audit masking**: vision audit ChangeJson 는 `{attachment_id, mime_type, size_bucket}` 만. raw filename / bytes / object_key 절대 미노출.
  - **D13 정합**: server-side bytes read + base64 inline only. signed URL 외부 송신 0.
  - **D9 share redact**: agent_core 가 vision invoke 결과 메시지 mirror 시 MetaJson 에 `attachment_derived=true` + `derivation_type="vision_analysis"` 추가 → Sprint 1 Phase 8 의 `_meta_has_attachment_derived` 가 자동 redact 적용.
  - **D19 join**: app.py 가 audit dispatch 직후 (vision 성공 시) `_load_latest_assistant_message` 로 message_id 확보 + `WebAttachmentDerivedMessages` INSERT (각 inline attachment 별 1 row).
  - **size/count cap**: 단일 image ≤ 5MB (pre-base64), turn 당 ≤ 5. 비용 폭주 + context overflow 방지.
  - **R-F13 provider Files API lifecycle SKIPPED**: 본 cycle 은 base64 inline only → provider 측 잔존 0 → Files API 미사용 → R-F13 진입 불요. WebConversationAttachmentProviderFiles schema 는 Sprint 1 Phase 2 에서 already ship (D13 schema), 본 cycle 의 lifecycle row INSERT/DELETE 가 없음.
  - **bedrock 정합**: catalog 변경 0 (option A 사용자 결정), flag 만 추가. LiteLLM proxy (feature-0007) 가 OpenAI Chat Completions `image_url` content-array → Anthropic Vision spec (`{type:image, source:{type:base64, ...}}`) auto-normalize. `drop_params: true` 로 미지원 OpenAI param silent drop.
  - **테스트**: 14 unit test pass — messages_for_provider 8 (empty / vision_off / conversion / empty base64 skip / multi-turn idempotency / 다중 image inline / DB string 불변 / integration with claude-sonnet-4) + _load_attachment_inline_images 6 (env 부재 / file 부재 / 정상 JSON / 빈 base64 skip / 잘못된 schema / invalid JSON). _prepare_vision_inline_images 통합 test 는 container smoke 시점.
  - **codex outside-voice review SKIPPED** (사용자 결정 2026-05-22) — REV-20260522-0014 에 사유 명시.
  - Sprint 2 의 commit 분리 (rebase 후 hash): S2.1+S2.2+S2.3 backend / S2.4+S2.5+S2.6 source / S2.8 docs ship.
- Rollback: 본 4 source 파일 + 5 docs revert. Sprint 1 산출물 (storage_minio, sandbox_*, sql_guard, attachment_reconciliation, RBAC 6, audit 10, endpoint 7) 은 보존.

## CHG-20260527-0001
- Date: 2026-05-27
- Related Requirement: AR-M5-impl web hotfix — PG cutover MySQL 잔존 쿼리 차단 (TASK-AR-M5)
- Summary: `_last_step_at_for_run()` 에 `AGENT_RUNTIME_READ_BACKEND=postgres` 가드 추가. PG 모드에서 MySQL `AgentMemorySteps` 직접 조회 제거 → `agent_runtime.steps` 쿼리로 대체. web 컨테이너 재빌드 시 `ensure_memory_schema()` 가 `pass` 로만 동작하여 MySQL `agent*` 테이블 재생성 차단.
- Files:
  - feature-0003-agent-web-ui/src/app.py (_last_step_at_for_run PG 가드 추가)
- Notes:
  - PG 경로: `_pg_connect()` 로 연결 → `SELECT MAX(created_at) FROM agent_runtime.steps WHERE conversation_id=%s AND run_id=%s`. tzinfo=None 정규화 (datetime.utcnow() 비교 기준 일치).
  - MySQL fallback 유지: `AGENT_RUNTIME_READ_BACKEND != postgres` 시 기존 `AgentMemorySteps` 쿼리 동작.
  - web 이미지 재빌드 필요: `docker compose build web && docker compose up -d web` (feature-0002 의 pass-only `ensure_memory_schema()` 가 빌드에 포함).
- Rollback: app.py 의 본 PG 가드 블록 제거 + web 컨테이너 재빌드.

## CHG-20260527-ASK-STATUS-FIX
- Date: 2026-05-27
- Related Requirement: TASK-0121 (**Critical §12.3** — AR-M5 PG cutover 후 `ask_status` 500 fix)
- Summary: `_load_latest_assistant_message` 가 MySQL `AgentMemoryMessages`(AR-M5 에서 DROP됨)를 직접 쿼리하던 경로를 PG routing으로 전환. `agent_runtime.messages WHERE role='assistant' ORDER BY id DESC LIMIT 50` 쿼리 추가. psycopg2 JSONB는 dict이므로 json.dumps로 직렬화 후 기존 루프에 투입. MySQL 쿼리는 PG 예외 발생 시 fallback으로 유지.
- Files: unit/feature-0003-agent-web-ui/src/app.py
- Rollback: PG routing 블록 제거 + MySQL 직접 쿼리 복원.

## CHG-20260527-ASK-STATUS-PG
- Date: 2026-05-27
- Related Requirement: TASK-0121 (ask_status 500 오류 수정)
- Summary: `_load_latest_assistant_message` 에 PG routing 추가. AR-M5에서 MySQL `AgentMemoryMessages` 테이블 DROP 후 `ask_status` 500 오류. PG `agent_runtime.messages` WHERE role='assistant' ORDER BY id DESC LIMIT 50 쿼리로 대체. JSONB meta_json은 `json.dumps()` 직렬화 후 기존 `json.loads()` 루프에 전달 (호환 유지). PG 실패 시 MySQL fallback (try/except).
- Files:
  - feature-0003-agent-web-ui/src/app.py (_load_latest_assistant_message PG 경로 추가)
- Notes:
  - psycopg2 JSONB → dict 반환 → `json.dumps()` → 기존 `json.loads()` 흐름 유지.
  - MySQL fallback 경로 유지 (PG 연결 실패 시).
  - `from modules.db import _pg_connect` 기존 app.py PG 패턴 일치.
- Rollback: PG routing 블록 제거, MySQL 직접 쿼리 복원.

## CHG-20260527-PERM-TOGGLE-VALUE
- Date: 2026-05-27
- Related Requirement: TASK-0121 (**Critical §12.3** — 역할 권한 저장 시 "unknown permissions: on" 오류)
- Summary: `buildRoleProductCard()` 의 product access 토글 checkbox 에 `value` 속성 미설정으로 인해 브라우저 기본값 `"on"` 이 `permission_codes` 배열에 포함되어 서버 검증 실패. `toggleInput.value = perm.code` 추가. admin.js 캐시 버스팅 `v=20260527-task-0121-perm-toggle-value`.
- Files: unit/feature-0003-agent-web-ui/src/static/admin.js, unit/feature-0003-agent-web-ui/src/static/admin.html
- Rollback: admin.js 의 `toggleInput.value = perm.code` 라인 제거 + admin.html 캐시 버스트 이전 버전으로 복원.

## CHG-20260609-FORK-SHARE-PG-CUTOVER
- Date: 2026-06-09
- Related Requirement: TASK-0167 (**Major §12.3** — 대화 분기/공유 cutover 회귀 HTTP 500 수정)
- Summary: 2026-05-27 MySQL→PG cutover 로 `AgentCoreConversations`/`AgentMemoryMessages`/`AgentMemoryKv` 가 DROP 됐는데 fork/share/duplicate/public-share-view 가 raw MySQL 경로를 유지해 `Table 'agent_memory.agentmemorymessages' doesn't exist` / `agentcoreconversations` 500 을 던졌다 (CHG-20260527-ASK-STATUS-PG 의 형제 회귀 — 당시 `_load_latest_assistant_message` 만 고치고 fork/share 면은 누락). `AGENT_RUNTIME_READ_BACKEND=postgres` 분기 + `_pg_connect()` 로 PG `agent_runtime.{core_conversations,messages,kv}` 라우팅하는 backend-aware helper 10종 신설(`_runtime_backend_is_pg`/`_meta_json_to_dict`/`_conv_load_topic`/`_conv_load_product`/`_conv_load_messages_raw`/`_conv_message_exists`/`_conv_update_topic_product`/`_conv_update_topic`/`_conv_copy_messages`/`_conv_load_share_meta`). `public_share_view` 는 core_conversations(PG) + WebProducts/WebAccounts(MySQL) cross-DB 이므로 단일 JOIN 을 PG read + MySQL enrichment + Python merge(`_conv_load_share_meta`)로 분리. jsonb meta_json 은 read 시 dict 정규화 / insert 시 `%s::jsonb` 캐스트. MySQL else 분기는 비-postgres 배포용 legacy fallback 보존(`_ensure_conversation_row`/`_assign_conversation_owner` 관례 답습).
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (backend-aware helper 블록 + 5개 함수 라우팅)
  - unit/feature-0003-agent-web-ui/tests/test_fork_share_cutover.py (회귀 e2e T1~T5)
- Notes:
  - jsonb meta_json: PG psycopg 는 jsonb→dict 반환 → `_meta_json_to_dict` 로 정규화 후 `_is_internal_message`(str|None 시그니처)에는 `json.dumps` 직렬화 전달. insert 는 `%(...)s::jsonb` 와 동등한 `%s::jsonb` 캐스트(runtime_backend._PG_INSERT_MEMORY_MESSAGE 패턴 일치).
  - `_pg_connect()` 는 autocommit=True (mysql.connector 기본 동작 일치) → 명시 commit 불요.
  - fork 메시지 복제 시 FK(fk_messages_conv) 충족: create_new_conversation + _assign_conversation_owner 가 새 conv row 를 선커밋 → 이후 messages INSERT.
- Rollback: backend-aware helper 블록 제거 + 각 함수의 raw MySQL 쿼리 복원. 단 MySQL 런타임 테이블은 DROP 상태이므로 rollback 시 500 재발 — PG 경로가 정본.

## CHG-20260609-SHARE-ERRCONTRACT
- Date: 2026-06-09
- Related Requirement: TASK-0168 (**Minor §12.3** — TASK-0167 outside-voice REV-20260609-0001 권고 F1·F2 처리)
- Summary: **F1** `public_share_view` 의 대화 메타/메시지 로드(`_conv_load_share_meta`/`_share_load_messages`, PG read)를 `try/except` 로 감싸 PG 일시 장애 시 bare 500(FastAPI 기본) 대신 graceful JSON 500(`"공유 대화를 불러오지 못했습니다."`)을 반환 — fork(`_fork_conversation_impl`)의 명시 500 래핑과 에러 계약 대칭. 상단 `ViewCount++`(revoke race 가드 겸용 UPDATE)는 그대로 두며, 로드 실패 시 1 과대카운트는 허용 가능한 soft-metric 오차(race 정합 우선)로 주석화. **F2** 신규 `tests/test_share_redaction_invariant.py` — `modules.db._pg_connect` 를 mock + `AGENT_RUNTIME_READ_BACKEND=postgres` set 으로 cutover 후 PG dict-meta(jsonb→dict) 경로를 결정적 재현하고, 익명 공유뷰 보안 불변식(attachment_derived redact / internal 메시지 필터 / 정상 본문 보존 / 정책 version gate)을 단언. 성공경로 동작·RBAC·스키마·엔드포인트 계약 무변경.
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (public_share_view F1 try/except)
  - unit/feature-0003-agent-web-ui/tests/test_share_redaction_invariant.py (F2 신규)
- Notes:
  - F2 는 web 컨테이너 in-process 실행(`docker exec -w /app repo-web-1 python <test>`) 또는 make test(pytest 수집)로 검증. 라이브 DB 불요(mock).
  - 컨테이너 in-process 3/3 PASS 확인(2e89ac3 위, TASK-0167 _share_load_messages PG 경로 대상).
  - redaction/internal-filter 코드(`_share_redact_message_content`/`_is_internal_message`)는 TASK-0167·0168 모두 무변경 — F2 는 cutover refactor 후에도 불변식이 살아있음을 가드.
- Rollback: F1 try/except 제거(원래 bare 호출 복원) + 테스트 파일 삭제. 동작 회귀 없음(F1 은 실패경로만, F2 는 테스트).

## CHG-20260609-FORK-CORE-CONTEXT
- Date: 2026-06-09
- Related Requirement: TASK-0170 (**Major §12.3** — fork 문맥 상실 수정, 하이브리드 Phase 1, ADR-WEB-0005)
- Summary: fork/duplicate/공유-fork 본에서 어시스턴트가 이전 대화 문맥을 인지 못 하던 버그 수정. 원인: LLM 문맥은 `agent_runtime.core_messages`(agent_core `_load_conversation_messages` → `_PG_LOAD_CORE_MESSAGES`)에서 읽는데, fork(`_fork_conversation_impl`)는 표시 메시지(`agent_runtime.messages`)만 복사하고 core_messages 를 복사 안 해 복사본 core_messages 가 비어 문맥 0. 신규 헬퍼 `_conv_load_core_messages_raw`/`_conv_copy_core_messages`(PG 전용)로 fork 시 core_messages 를 deep-copy(role/content/tool_calls/tool_call_id/name/created_at, tool_calls jsonb 직렬화 후 `::jsonb` 재삽입). anchored fork 는 앵커 메시지 created_at 까지(`src_rows[-1][3]`), full fork/duplicate 는 전체. 교차계정 공유 fork 도 이 복사로 snapshot(상시 cross-tenant 흐름 없음). core 복사 실패 시 fork 통째 cleanup(`delete_conversation_records`, PG CASCADE)+500(반쪽 fork 금지). 응답 dict 에 `core_copied` 추가.
- 설계 경위: 사용자가 git식 reference 아키텍처 희망 → `DESIGN-fork-reference.md` 설계 → outside-voice 적대적 검토(REV-20260609-0003)가 순수 reference 의 BLOCKER 2(cross-table 시각 cut 불가, 로더 오기술)+보안 안티패턴 3(`.any` 영구 tap, 교차계정 live read, sandbox 공유) 발견 → **하이브리드 확정(ADR-WEB-0005)**: Phase 1=core_messages 복사(본 변경), Phase 2=첨부(후속 cycle).
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (_conv_load_core_messages_raw/_conv_copy_core_messages + _fork_conversation_impl 배선 + core_copied)
  - unit/feature-0003-agent-web-ui/tests/test_fork_share_cutover.py (T1b 문맥 복사 단언)
  - unit/feature-0003-agent-web-ui/docs/DESIGN-fork-reference.md (설계 정본)
  - unit/feature-0003-agent-web-ui/docs/DECISIONS.md (ADR-WEB-0005)
- Notes:
  - cross-table 시각 cut 의 한계(DESIGN §14 F1): anchored fork 경계 ±1턴. copy 라 straddling turn 은 로드 시 `_normalize_history_rows` 가 자가 치유(reference 와 달리 corruption 아님).
  - 스키마 변경·코어 로더 변경 0 — 순수 복사라 마이그레이션 0, 회귀 표면 최소(무-fork·기존 대화 무영향).
  - PG 전용: 비-postgres 배포는 core 복사 skip([]), fork 는 표시 메시지로 진행.
- Rollback: 두 헬퍼 + _fork_conversation_impl 의 core 복사 블록 + core_copied 제거. fork 는 TASK-0167 동작(표시만 복사)으로 회귀(문맥 상실 재발).

## CHG-20260609-FORK-ATTACHMENTS
- Date: 2026-06-09
- Related Requirement: TASK-0171 (**Major §12.3** — fork 첨부 복사, 하이브리드 Phase 2, ADR-WEB-0005)
- Summary: fork/duplicate/공유-fork 본에서 사용자가 원본 첨부 파일을 열람·다운로드하고 어시스턴트가 첨부 맥락을 이어가도록, fork 시 첨부를 복사한다. 신규 `_copy_conversation_attachments(conn, source_cid, new_cid, fork_account_id)` 가 `WebConversationAttachments` 활성 행(`DeletedAt IS NULL`)을 새 ConversationId + fork 소유 AccountId 로 복사하고, blob 은 **독립 복사**(`storage_minio.get_object_bytes`→`put_object_bytes`, 새 ObjectKey)한다. ObjectKey 공유는 reconciliation 이 공유 blob 을 hard-delete 해 fork 가 404 되는 refcount 위험이 있고 server-side copy 가 없어 get+put 으로 독립 복사한다(ADR 의 "blob 재업로드 0" 에서 안전상 이탈). CSV/XLSX 는 `_ingest_attachment_background` background 재적재로 **fork 전용 sandbox 스키마**(`sha256(new_cid)`)를 만든다(조상 스키마 공유 금지 — DESIGN §14 F5). `_fork_conversation_impl` 에 배선(core_messages 복사 직후), 응답에 `attachments_copied` 추가. 첨부는 보조물이라 per-attachment fail-open(단일 실패가 fork 를 막지 않음). IDOR 게이트(`_account_can_access_attachment`, conversation 소유 기반) 무변경 — fork 가 자기 행 소유라 그대로 통과.
- outside-voice(REV-20260609-0004, FIX-FIRST) 반영:
  - #2 (MAJOR) orphan blob: put→INSERT + fail-open 이 행 없는 blob 을 남겨 reconciliation 이 GC 못 함 → **INSERT 먼저 → put → put 실패 시 행 보상삭제**(업로드 endpoint 검증 순서). 양방향 고아(행 없는 blob / blob 없는 행) 차단.
  - #6 (MAJOR) quota 우회: 복사가 cap 검사 미수행 → 반복 fork 로 storage 무한 증식 → 복사 전 `_check_attachment_size_caps`(per-file/conv/account 누적) 검사, 초과분 skip(log).
  - #5 (MINOR) audit: 교차계정 fork 가 타 계정 첨부를 forker 로 이동하는 보안민감 이벤트 → `public_share_fork` 의 `share.fork` audit ctx 에 `attachments_copied`/`core_messages_copied` 건수 기록(파일명·바이트 비노출, D12).
  - #7 (MINOR) test flap: ingest 타이밍/cap-skip 대비 테스트를 ⊆+count 일관성으로 완화.
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (_copy_conversation_attachments + fork 배선 + share.fork audit ctx)
  - unit/feature-0003-agent-web-ui/tests/test_fork_attachments.py (A1~A4 신규)
- Notes:
  - 현 배포엔 활성 sandbox 0개(첨부는 text kind) — CSV 재적재 경로는 미사용/미라이브검증, 코드는 방어적 포함.
  - WebConversationAttachments 는 MySQL web 테이블(conn autocommit=True → 즉시 커밋). soft-deleted(DeletedAt) 첨부는 SELECT 에서 제외(tombstone 미복사).
- Rollback: `_copy_conversation_attachments` + fork 배선 + audit ctx 2키 + 테스트 제거. fork 는 TASK-0170 동작(첨부 미복사)으로 회귀.

## CHG-20260609-PREVIEW-CSV-GUARD
- Date: 2026-06-09
- Related Requirement: TASK-0174 ("전체 N행 미리보기" 인라인 로더 방어막 — #118 인라인 경로)
- Summary: 본문 "📎 전체 N행 미리보기" 링크가 타는 `loadCsvAsInlineTable` 에 값 기반 방어 가드 추가. 기존엔 #118 가드가 SQL-nav 경로(`loadFullCsvIntoTable`)에만 있고 본문 인라인 경로엔 없어, 잘못된 CSV 링크를 그대로 인라인 렌더했다. 로드한 CSV 의 식별 값 토큰이 인접 미리보기 표(td)와 전혀 겹치지 않으면 렌더 거부(헤더명이 아닌 값 비교 — LLM 헤더 리네이밍 오탐 방지). previewTokens≥2 일 때만 거부해 단일 토큰 우연 불일치 오탐 차단.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/app.js (distinctiveValueTokens 헬퍼 신규 + loadCsvAsInlineTable 가드)
- Notes:
  - 1차 방어는 backend(agent_core _collapse_large_tables 값매칭, CHG-20260609-PREVIEW-CSV-MATCH). 본 가드는 방어심층(defense-in-depth) 최종선.
  - §18.8 패널(REV-20260609-0173) JS 오탐 지적 반영(≥2 임계).
- Rollback: distinctiveValueTokens + loadCsvAsInlineTable 가드 블록 제거.

## CHG-20260609-TASK0174-CLOSE
- Date: 2026-06-09
- Related Requirement: TASK-0174 (cycle closure — 라이브 검증 기록)
- Summary: TASK-0174 인라인 가드(CHG-20260609-PREVIEW-CSV-GUARD) cycle 마감 — TASK.md 체크박스 [x] 갱신 + TEST.md §4 에 PB-0008 Windows-browser 무회귀 검증 Run 기록(2026-06-09 TASK-0174 항목, CHECK#13 충족). 코드 변경 없음(문서 한정).
- Files:
  - unit/feature-0003-agent-web-ui/docs/TASK.md (TASK-0174 체크박스 완료)
  - unit/feature-0003-agent-web-ui/docs/TEST.md (§4 Test Run History PB-0008 Run 추가)
- Rollback: 체크박스 환원 + TEST.md §4 항목 제거.

## CHG-20260610-0184
- Date: 2026-06-10
- Related Requirement: TASK-0184 (REQ-20260610-0184)
- Summary: 관리 콘솔 LLM 사용량 3건. (A) 계정별 독립 차트를 **역할 drill-down**(역할 막대 클릭→그 역할 계정만 검색·Top-N 페이징, 기본 접힘)으로 대체 — 계정 수 증가 시 차트 과다 길이/탐색난 해소. (B) 프로필 **'사용 내역' 탭** 신설 — 신규 `GET /api/profile/usage`(본인 owner_account_id 한정, `_require_account` 로그인만, 추정 비용·역할 enrich 제외) + 미니 SVG 차트(모델별 stacked·donut). (C) 의도치 않게 노출된 프로필 **'내 활동 기록' 탭/패널/JS 제거**(`/api/profile/audits` 는 호출처 없이 잔존). RBAC 카탈로그·스키마·시크릿 무변경.
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (`profile_llm_usage` 신규 엔드포인트)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (계정별 독립 차트 → drill 패널 + 캐시버스터)
  - unit/feature-0003-agent-web-ui/src/static/admin.js (`renderStackedHBar` onRowClick + `toggleAccountDrill`/`renderAccountDrill` + drill 컨트롤 바인딩 + 계정 독립 차트/`acctLabel` 제거)
  - unit/feature-0003-agent-web-ui/src/static/index.html (audits 탭/패널 제거 + usage 탭/패널 + 캐시버스터)
  - unit/feature-0003-agent-web-ui/src/static/app.js (`loadProfileAudits`/audit 게이트/핸들러 제거 + `loadProfileUsage`/미니차트 + usage 탭 핸들러)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`admin-usage-drill`·`admin-usage-hbar-row` + `profile-usage` 클래스)
  - unit/feature-0003-agent-web-ui/docs/TASK.md, FUNCTION.md, REVIEW.md, STATUS.md
- Rollback: 본 cycle 커밋 revert — drill 패널→계정별 독립 차트 복원, 프로필 usage 탭/엔드포인트 제거, audits 탭/JS 복원.

## CHG-20260610-0184-COSTCHART
- Date: 2026-06-10
- Related Requirement: TASK-0184 (A drill-down 누락 보강 — 사용자 지적 "계정별 비용 차트 누락")
- Summary: A drill-down 전환 시 계정별 독립 차트(토큰+비용) 2종을 모두 제거하고 drill 패널에 **토큰만** 넣어 계정별 비용이 사라졌다(역할별은 토큰|비용 둘 다 유지). drill 패널 body 를 **[토큰 | 비용] 2열**(`usageDrillChart`/`usageDrillCostChart`, `.admin-usage-drill-charts` flex, 좁으면 wrap)로 재구성하고 `renderAccountDrill` 이 토큰(`total_tokens`/num)·비용(`cost_usd`/usd) 막대를 함께 렌더(빈 검색·접힘 시 둘 다 클리어). by_account 응답엔 이미 `cost_usd` 포함 — 백엔드 무변경. 캐시버스터 `?v=20260610-usage-drill2`(admin).
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.html (drill body → 토큰|비용 2열 + 캐시버스터)
  - unit/feature-0003-agent-web-ui/src/static/admin.js (`renderAccountDrill` 비용 차트 렌더 + 접힘/빈검색 클리어)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-usage-drill-charts`/`-col`)
- Rollback: drill body 를 단일 `usageDrillChart`(토큰만)로 환원.

## CHG-20260610-0198
- Date: 2026-06-10
- Related Requirement: TASK-0198 (사용자 요청 — LLM 사용량 모델별 분리/선택 차트 + 좌우 스크롤 제거)
- Summary: `관리 콘솔 > 감사 > LLM 사용량` 상단 대시보드가 종합만 보이고 모델별 분리/선택 불가 + 좌우 스크롤 불편 해소. **(A) 모델 필터·분리**: 상단 모델 칩 바(`#usageModelFilter`)로 전체/모델 다중 토글, 선택 모델 기준으로 요약·일별·도넛·역할·계정 차트/표를 클라이언트 재계산(`buildView`)으로 좁힘. `loadUsage` 가 응답을 days|gran 키로 캐시(`_lastRaw`)하고 칩 토글은 재조회 없이 재렌더(`refetch:false`). 모델 키=`COALESCE(resolved_model,model)`. 부분 선택 시 역할·계정 표의 요청·호출은 모델 횡단이라 `—`(토큰·비용은 기여분 재합산으로 정확). **(B) 모델별 요약 카드**: 합계 카드(스코프 라벨) + 모델별 분리 카드(토큰/요청/호출/비용, 클릭 시 단독 선택). **(C) 좌우 스크롤 제거**: usage pane `overflow-x:hidden`, flex `min-width:min(Npx,100%)`, 넓은 표는 카드 내부 `overflow-x:auto`. `color-mix`/`--accent` 미사용 → `--primary`/`--primary-soft` 토큰. 백엔드/API/스키마/RBAC/시크릿 무변경(읽기 전용 집계 표시만). 캐시버스터 `?v=20260610-usage-model-filter2`. PB-0008 Windows-browser 검증 시 전체 모델 상태에서 세로 스크롤바(15px) 등장으로 인한 잔여 6px 측정값을 추가 차단 — usage pane summary-metrics `minmax(min(160px,100%),1fr)` + pane 직접 자식 `min-width:0;max-width:100%`. `userCanScrollHorizontally:false` 확정(TEST.md §3).
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (`loadUsage` 모델 필터 상태·`buildView`·`renderModelFilter`·모델별 요약 카드·view 기준 렌더·부분선택 `—` 처리)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (`#usageModelFilter` 컨테이너 + admin.js/styles.css 캐시버스터 `usage-model-filter2`)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (가로 스크롤 차단[overflow-x:hidden + min-width:min(Npx,100%) + pane 자식 min-width:0/max-width:100% + summary minmax min()] + `.admin-usage-filter`/`-chip`/`-mcard*` 스타일)
  - unit/feature-0003-agent-web-ui/tests/win-browser-task0198-usage.scenario.json (PB-0008 검증 시나리오 신규)
  - unit/feature-0003-agent-web-ui/docs/{TASK,FUNCTION,REVIEW,TEST}.md (명세·이력·검증 기록)
- Rollback: 캐시버스터 환원 + `loadUsage` 를 직접 `data` 렌더로 되돌리고(`buildView`/필터 칩 제거), `#usageModelFilter` div 와 `.admin-usage-filter`/`-chip`/`-mcard*` CSS·`overflow-x`·`min-width` 변경 제거.

## CHG-20260610-0202
- Date: 2026-06-10
- Related Requirement: TASK-0202 (사용자 요청 — LLM 사용량 "모델별" 모델 전환 애니메이션 + 비선택 dim/이탈 시 사라짐)
- Summary: `관리 콘솔 > 감사 > LLM 사용량` "모델별" 카드(`.admin-usage-mcards`)에서 모델 카드 클릭(solo 선택) 시 비선택 카드가 즉시 사라져 불편하던 것을 개선. (1) 카드를 필터된 `view.by_model` 대신 **전체 `data.by_model`** 로 항상 렌더(카드 수치는 각 모델 고유값이라 선택 무관) — 비선택 카드가 DOM 에서 제거되지 않음. 선택=`is-active`·비선택=`is-dimmed`, 컨테이너에 `is-filtering`(부분 선택 시만). (2) CSS: `.admin-usage-mcard` 에 opacity/transform 트랜지션, `.is-filtering .is-dimmed`=흐림(opacity .4, hover 시), `.is-filtering:not(:hover) .is-dimmed`=fade-out(opacity 0+scale .92+pointer-events none), `prefers-reduced-motion` 가드. (3) JS hover 생명주기: 영역 이탈 fade-out 종료(`transitionend opacity`)시 `display:none` 회수(active 카드 제외), 재진입 시 reflow 기반 0→.4 fade-in 복구, 칩 바 필터링 등 마우스 영역 밖 재렌더는 초기 transition 미발동이라 동기 `display:none` 회수(유령 카드 방지). 백엔드/API/스키마/RBAC/시크릿/`buildView`/차트·표(전부 `view.*` 유지) 무변경 — 카드 렌더 소스와 표현만 변경. 캐시버스터 `?v=20260610-usage-model-anim`.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (`loadUsage` 모델별 카드 렌더를 `data.by_model` 전체+active/dimmed, `is-filtering` 컨테이너, transitionend/mouseenter 생명주기 + 동기 회수)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-usage-mcard` 트랜지션 + `.is-filtering`/`.is-dimmed` dim/접힘 규칙 + reduced-motion)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 `usage-model-filter2` → `usage-model-anim`)
  - unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md (명세·이력·검증 기록)
- Rollback: 캐시버스터 환원 + 카드 렌더를 `view.by_model` 직접 렌더(soloActive 단일 강조)로 되돌리고 `is-filtering`/`is-dimmed`/transitionend·mouseenter 핸들러 제거, styles.css 의 `.is-filtering`/`.is-dimmed` 규칙·opacity/transform 트랜지션·reduced-motion 블록 제거.

## CHG-20260611-0204
- Date: 2026-06-11
- Related Requirement: TASK-0204 (사용자 피드백 — TASK-0202 모델 카드 hover 동작 불편/의도치 않음 → '모델별' 카드 제거 + 칩 토큰수 제거)
- Summary: `관리 콘솔 > 감사 > LLM 사용량` 요약 영역의 '모델별' 분리 카드 그리드(`.admin-usage-mcards`, TASK-0198 도입·TASK-0202 애니메이션)를 **제거**한다. 사용자 라이브 사용에서 모델 카드 클릭 시 비선택 카드가 즉시 사라지고(빈 공간) hover 결합 dim/접힘이 re-render·마우스 이동과 충돌해 잭을 유발 → 상단 '모델' 칩 바 + '전체' 가 모델별 분리/선택을 이미 담당하므로 중복 섹션을 폐기. (1) admin.js `loadUsage`: mcards 빌드 + 카드 클릭/transitionend/mouseenter/동기회수 핸들러 제거 → `summaryEl.innerHTML = totalsHtml`(합계 카드만). (2) admin.js `renderModelFilter`: 칩 버튼 내 토큰수(`admin-usage-chip-tok`) 및 '전체' 토큰수 제거(모델명만), 미사용 `tokByKey`/`t` 파라미터 정리. (3) styles.css: `.admin-usage-mcards*` + `.admin-usage-chip-tok` 규칙 제거(dead). 모델 토큰량은 '모델별 비중' 도넛·일별 차트·상세 표에 유지. `buildView`/차트/표 무변경(회귀 0), 백엔드/API/스키마/RBAC 무변경. 캐시버스터 `?v=20260611-usage-no-mcards`.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (mcards 섹션·핸들러 제거, 칩 토큰수 제거, 미사용 정리)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-usage-mcards*`·`.admin-usage-chip-tok` 제거)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 → usage-no-mcards)
  - unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: TASK-0202 시점 admin.js/styles.css 환원(mcards 그리드+카드 클릭/hover 핸들러+`.admin-usage-mcard*`/`.admin-usage-chip-tok` CSS 복원) + 캐시버스터 환원.

## CHG-20260611-0205
- Date: 2026-06-11
- Related Requirement: TASK-0205 (사용자 요청 — 텍스트박스 Shift+Enter 줄바꿈 지원)
- Summary: composer 입력 텍스트박스(`promptInputEl`)의 `keydown` 핸들러에서 `event.shiftKey` 가 true 이면 즉시 `return` 하여 브라우저 기본 줄바꿈 동작을 허용한다. `sendMode` 설정("Enter 전송"/"Ctrl+Enter 전송")과 무관하게 Shift+Enter 는 항상 줄바꿈. 기존 Enter/Ctrl+Enter 전송 경로 무변경. 백엔드·API·스키마·RBAC 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/app.js (promptInputEl keydown — Shift+Enter early return 1줄)
  - unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: `if (event.shiftKey) return;` 1줄 제거.

## CHG-20260611-0206
- Date: 2026-06-11
- Related Requirement: TASK-0206 (사용자 피드백 — 쿼리 문자열 항상 표시, 실행결과셋 기본 숨김 토글)
- Summary: 답변 내 SQL 쿼리 문자열은 항상 표시하고, 실행결과셋(테이블/미리보기 데이터)을 `결과 보기` 버튼으로 기본 숨김·클릭 시 토글한다. ① `collapseSqlCodeBlocksInContent()` — ` ```sql ``` ` 코드블록 숨김 로직 제거(항상 표시). ② `buildSqlStepPanel()` — SQL `<pre>` 항상 표시, 결과 테이블+CSV 액션을 `sql-result-toggle-wrap`+`resultBody(hidden=true)`로 감싸고 `결과 보기/닫기` 토글. ③ `renderMessageDetails()` 구형 fallback — SQL 토글 제거(항상 표시). ④ `buildStepDetailEl()` 사이드 패널 — 결과셋(표/preview)을 `sql-result-toggle-wrap`+`resultBody(hidden=true)`로 감싸고 `결과 보기/닫기` 토글. ⑤ styles.css — `.sql-result-toggle-wrap`, `.sql-result-body` 규칙 추가. 백엔드·API·스키마·RBAC 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/app.js (4개 함수 수정)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (토글 래퍼 CSS 추가)
  - unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: `collapseSqlCodeBlocksInContent` 원상복구 + `buildSqlStepPanel`·`buildStepDetailEl` 결과셋 토글 래퍼 제거 + styles.css `.sql-result-toggle-wrap`·`.sql-result-body` 제거.

## CHG-20260611-0207
- Date: 2026-06-11 (TASK-0207, **Minor §12.3** — 관리 콘솔 데이터소스 pane UI 표준화 + 수정/삭제 노출)
- Scope: `관리 콘솔 > 데이터소스` pane 을 계정/역할/제품/설정 과 동일한 list-detail 5단 구조(DESIGN.md §2)로 재구성하고 수정/삭제 액션을 상세 패널에 명시 노출. 프런트 전용 — 백엔드/API/스키마/RBAC/시크릿 무변경.
- 배경: 데이터소스 pane 만 표준 구조 미적용(`h3` + 평면 `admin-ds-list` + 미스타일 클래스 `admin-badge`/`admin-field`/`admin-row-actions`)이라 시각적으로 이질적. 수정(PATCH)/삭제(DELETE+force) 핸들러는 TASK-0205 에서 이미 구현됐으나 평면 행 우측 버튼에 묻혀 잘 안 보였음.
- 변경:
  - `src/static/admin.html`: 데이터소스 `<section data-admin-pane="datasources">` 를 `drawer-label`+`h2`+`admin-pane-head-right`(`#newDatasourceBtn`) 헤더 + `admin-list-detail`(좌 `admin-list-col`: `#datasourceSearch`/`#datasourceListCount`/`#datasourceList`, 우 `admin-detail-col` `#datasourceDetail`) 로 교체. 정적자산 캐시버스터 `?v=20260611-usage-no-mcards` → `?v=20260611-ds-admin-ui`.
  - `src/static/admin.js`: `renderDatasourcesPane` 전면 재작성(`#datasourcesPane`/`admin-ds-list`/`dsFormHost`/`_dsShowForm` 폐기 → `_dsRenderList`/`_dsSyncListActive`/`_dsRenderDetail`/`_dsRenderDetailEmpty`/`_dsRenderForm`/`_dsKvRow`). 목록 클릭→상세, 검색 필터(`adminState._dsSearch`, dataset.bound idempotent), 선택 상태(`adminState._dsSelectedKey`), 생성 후 canonical(소문자) key 자동 선택. `refreshPendingUI` 에 `#tabCountDatasources` 카운트 배지 추가. RBAC 게이트(console.manage·ds.editable·encryption-ready) 전부 보존.
  - `src/static/styles.css`: 미스타일 클래스 `admin-badge`(+`--muted`/`--warn`)·`admin-kv`(dl/dt/dd)·`admin-detail-title`·`admin-field`(+label·readonly)·`admin-row-actions` 표준 토큰 스타일 추가. (`admin-detail-head` 중복정의 제거 — 패널 리뷰 BLOCKER 수정, 기존 canonical 재사용.)
- 비변경: `/api/admin/datasources` CRUD/test/databases 엔드포인트·envelope 암호화·SSRF allowlist·RBAC·제품별 datasource 바인딩 UI(buildProductDetail) 무변경.
- 검증: node --check admin.js PASS. 패널([SUBAGENT:design-correctness]) SHIP-WITH-FIXES 5건 전부 수용. 빌드/배포 + Windows-browser(PB-0008) 시각검증은 배포 단계.
- Files: unit/feature-0003-agent-web-ui/src/static/{admin.html,admin.js,styles.css}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: admin.html 데이터소스 section + admin.js `renderDatasourcesPane` 군 + styles.css 추가 블록을 TASK-0205 상태로 환원(기능 무관, 레이아웃만 평면 복귀).

## CHG-20260611-0208
- Date: 2026-06-11 (TASK-0208, **Minor §12.3** — 프로필 drawer 너비 조절 + 사용 내역 집계 단위)
- Scope: 사용자 요청 2건 — ① 프로필 사이드바(`#profileDrawer`)를 `단계 보기` 패널처럼 너비 드래그 조절 + 영속. ② `사용 내역` 탭 집계 단위(시간별/일별/월별) 셀렉터. 프런트 전용 — 백엔드/API/스키마/RBAC/시크릿 무변경.
- 배경: drawer 는 고정 폭 390px(모바일 380px) 이었고, 사용 내역 탭은 `gran=day` 하드코딩이라 시간/월 단위 조회 불가(백엔드 `/api/profile/usage` 는 TASK-0166 이후 `gran` hour/day/week/month 를 이미 지원했으나 프런트 컨트롤 부재).
- 변경:
  - `src/static/app.js`: (Task1) `PROFILE_DRAWER_WIDTH_KEY`/`PROFILE_DRAWER_MIN_W`/`_profileDrawerMaxW`/`_applyProfileDrawerWidth`/`setupProfileDrawerResize` 추가(단계 패널 `setupStepSidePanelResize` 미러). `openProfile` 가 setup+apply 호출. `_applyProfileDrawerWidth` 는 ≤680px 에서 inline 너비 미적용(미디어쿼리 소유). (Task2) `loadProfileUsage` 가 `#profileUsageGran` 값을 `GRAN_LABEL`(hour/day/month) 검증 후 `&gran=` 전달 + `#profileUsageTrendTitle` 동기화, `#profileUsageGran` change 리스너 추가.
  - `src/static/index.html`: `#profileDrawer` 첫 자식으로 `#profileDrawerResizer` + 내부 스크롤 래퍼 `.drawer-scroll`(헤더/탭/패널 래핑). 사용 내역 헤더에 `.profile-usage-controls` + `#profileUsageGran` 셀렉터(시간별/일별/월별). 캐시버스터 `?v=20260610-response-duration` → `?v=20260611-profile-resize-gran`.
  - `src/static/styles.css`: `.drawer` 에서 padding/gap/overflow-y 제거 + `overflow:hidden`(비스크롤 shell), 신규 `.drawer-scroll`(flex:1·min-height:0·overflow-y:auto·padding·gap) 으로 스크롤 이동. `.drawer.is-resizing`·`.drawer-resizer`(+`::before`·hover) 추가(단계 패널 리사이저 패턴). `.profile-usage-controls`(flex row).
- 비변경: `/api/profile/usage` 엔드포인트·RBAC·집계 SQL·단계 보기 패널 코드·기타 drawer 탭 로직 무변경.
- 검증: node --check app.js PASS, styles.css 중괄호 911/911, drawer aside div 30/30. 패널([SUBAGENT:design-correctness], REV-20260611-0208) SHIP-WITH-FIXES — MAJOR(스크롤 분리)+MINOR(모바일 가드) 수정 후. 빌드/배포 + Windows-browser(PB-0008) 시각검증은 배포 단계.
- Files: unit/feature-0003-agent-web-ui/src/static/{app.js,index.html,styles.css}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: app.js 추가 함수군 + index.html 리사이저/`.drawer-scroll`/gran 셀렉터 + styles.css 추가/변경 블록 환원(기능 무관, drawer 고정폭·사용내역 일별 고정 복귀).

## CHG-20260611-0209
- Date: 2026-06-11 (TASK-0209, **Minor §12.3** — 관리 콘솔 LLM 사용량 드롭다운 순서 정렬)
- Scope: `관리 콘솔 > LLM 사용량` 헤더의 집계범위/집계기준 드롭다운 순서를 프로필 `사용 내역`(TASK-0208)과 동일하게(집계기준 먼저) 정렬. 프런트 전용 — 백엔드/API/스키마/RBAC/시크릿/JS/CSS 무변경.
- 배경: 프로필 사용 내역 탭은 집계기준(gran)→집계범위(days) 순인데, 관리 콘솔은 반대(days→gran)라 두 화면 일관성 결여. 사용자가 관리 콘솔을 프로필 순서에 맞춰달라 요청.
- 변경 (`src/static/admin.html`): `.admin-pane-actions` 내 `#usageGranSel`(시/일/주/월) 을 `#usageDaysSel`(최근 N일) 앞으로 이동(형제 순서 교체). 캐시버스터 `?v=20260611-ds-admin-ui` → `?v=20260611-usage-dropdown-order`.
- 비변경: `admin.js` 의 두 select id 참조·change 핸들러·`/api/admin/usage` 호출·집계 로직 무변경(순서 무관). RBAC/엔드포인트/스키마 무변경.
- 검증: admin.html select 태그 균형(4/4). 빌드/배포 + Windows-browser(PB-0008) 시각검증은 배포 단계. outside-voice [SKIPPED:frontend-trivial-reorder] (REV-20260611-0209).
- Files: unit/feature-0003-agent-web-ui/src/static/admin.html, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: 두 select 의 순서를 원위치(days→gran)로 환원.

## CHG-20260611-0213
- Date: 2026-06-11 (TASK-0213, **Minor §12.3** — 접근 가능 DB 선택 드롭다운+체크박스)
- Scope: `관리 콘솔 > 제품 > 접근 가능 데이터베이스` picker UI 를 드롭다운+체크박스 연속 토글 방식으로 교체. RBAC·API 계약·스키마 신규 0.
- 배경: 기존 `<select>` + `+ 추가` 버튼 패턴은 DB 여러 개를 등록할 때 드롭다운 선택 → 버튼 클릭을 반복해야 해 불편. 체크박스 드롭다운으로 연속 토글 가능하게 개선.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `buildPicker()` 체크박스 드롭다운 패널 방식으로 재작성, `pickerSelect`/`pickerAddBtn`/`pickerRow` → `pickerDropBtn`/`pickerDropList`/`pickerWrap`. 항목 체크 시 즉시 draft push+setProductDatabasesPending+redrawChips, 언체크 시 즉시 draft splice. 패널 외부 클릭 닫기. `_refreshAccessibleDbs` 내 `buildPicker()` 호출 유지.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-db-picker-wrap/.admin-db-picker-btn/.admin-db-picker-list/.admin-db-picker-item/.admin-db-picker-empty` 신규.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260611-db-picker-checkbox`.
  - `unit/feature-0002-agent-core/src/modules/db.py`: `_connect_mssql` 의 `db_name` 폴백 `""` → `"tempdb"` (중립 DB, 무자격 참조 누출 차단).
  - `unit/feature-0002-agent-core/src/app.py`: `admin_create_datasource`/`admin_update_datasource` 에서 `default_db` 필드 갱신 제거(NULL 고정).
  - `unit/feature-0002-agent-core/tests/test_multi_datasource.py`: `test_connect_engine_dispatch_mssql_uses_pymssql` 기대값 `"" → "tempdb"` 수정.
- 비변경: RBAC·API 계약·WebDatasources 스키마·`_refreshAccessibleDbs`·고정칩 렌더링 무변경.
- 검증: node --check admin.js PASS. verify-completion PASS. 빌드/배포 + PB-0008 시각검증은 배포 단계.
- Files: unit/feature-0003-agent-web-ui/src/static/{admin.html,admin.js,styles.css}, unit/feature-0002-agent-core/src/modules/db.py, unit/feature-0002-agent-core/src/app.py, unit/feature-0002-agent-core/tests/test_multi_datasource.py, docs/{TASK,MODIFY,REVIEW}.md
- Rollback: admin.js picker 교체 전 상태(select+추가버튼) + styles.css picker-wrap 블록 제거 + db.py `""` 복원 + app.py default_db 복원.

## CHG-20260611-0213-docs
- Date: 2026-06-11 (TASK-0213 docs cycle — verify-completion PASS 확인 후 docs 보완)
- Scope: TASK-0213 문서 보완 (REVIEW.md REV 엔트리 추가, MODIFY.md 검증 상태 갱신).
- Files: unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md

## CHG-20260611-0216
- Date: 2026-06-11 (TASK-0216, **Minor §12.3** — 데이터소스 키 자동 생성: 엔진+호스트+포트 해시)
- Scope: `관리 콘솔 > 데이터소스` 항목의 키를 식별자 문자열에서 `엔진+호스트+포트` SHA-256 해시(앞 12자 + 엔진 태그)로 변경. 기존 `main_mysql` 레거시 키 자동 마이그레이션 포함.
- 배경: 식별자 문자열 키(`main_mysql` 등)는 엔드포인트 용도가 바뀔 때 기존 키가 그대로 남아 대응이 어려웠음. 해시 키는 동일 엔드포인트=항상 동일 키(멱등), 엔드포인트 변경 시 자동으로 다른 키가 발급되어 명확히 구분된다.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_generate_datasource_key(engine, host, port)` 신규 함수: `{engine}:{host}:{port}` SHA-256 해시 앞 12자 + 엔진 태그 → `{engine}-{hash12}` 형식. `_ds_valid_key` 제약(소문자 영숫자·_·-, `ds` 시작 금지) 통과.
    - `admin_create_datasource`: body `key` 수신 제거 → `_generate_datasource_key` 자동 생성. 409 에러 메시지 상세화("동일 엔드포인트가 이미 등록되어 있습니다"). 응답 `default_db` 미정의 버그 → `None` 명시.
    - `_seed_main_mysql_datasource`: `key = "main_mysql"` → `key = _generate_datasource_key("mysql", DB_HOST, int(DB_PORT))`. 레거시 `main_mysql` 키 존재 시 해시 키로 rename + `WebProducts.DatasourceKey` 참조 일괄 UPDATE(운영 연속성 보장, 멱등).
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `_dsRenderForm`: 신규 생성 시 key 입력 필드 제거, 자동 생성 안내 힌트 추가. 수정 시는 key readonly 표시 유지. body 전송 시 `key` 필드 제외(`k !== "key"` 가드). 생성 완료 토스트 "(키 자동 생성)" 메시지 추가.
- 비변경: `_migrate_env_datasources_to_db`(`.env` 레거시 경로 — 의도적 유지), RBAC(console.manage), API 계약(수신 필드에서 `key` 제거만), WebDatasources 스키마, DEK/KEK 암호화 경로.
- 검증: py_compile app.py PASS, node --check admin.js PASS.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/admin.js, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: `_generate_datasource_key` 제거 + `admin_create_datasource` body key 수신 복원 + `_seed_main_mysql_datasource` `"main_mysql"` 복원 + `_dsRenderForm` key 입력 필드 복원.

## CHG-20260611-0217
- Date: 2026-06-11 (TASK-0217, **Minor §12.3** — 데이터소스 해시 키 버그 수정 2건)
- Scope: TASK-0216 후속 버그 2건 — ① `main_mysql` 마이그레이션 시 패스워드 AAD 재암호화 누락, ② PATCH 수정 시 키 재생성 미처리.
- 배경: AESGCM 암호화에서 AAD=DatasourceKey를 사용하기 때문에, 키 이름이 바뀌면 동일 DEK로도 복호가 실패(InvalidTag)한다. TASK-0216에서 `main_mysql` → 해시 키로 rename할 때 PasswordEnc를 재암호화하지 않아 부팅 시마다 `datasource_decrypt_failed` 오류로 데이터소스가 전부 skip됐다.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_seed_main_mysql_datasource`: rename 전 `PasswordEnc, EncryptionVersion` 조회 → DEK 로드 → 복호 → 새 키 AAD로 재암호화 → `UPDATE ... DatasourceKey=%s, PasswordEnc=%s, EncryptionVersion=%s` 원자적 처리. 복호 실패 시 기존 암호문 유지(silent pass).
    - `admin_update_datasource`: 기존 `SELECT Id` → `SELECT Engine, Host, Port, PasswordEnc, EncryptionVersion`. 변경 후 새 해시 키 계산(`_generate_datasource_key`), 키 변경 시: ① 패스워드 입력 있으면 새 키 AAD로 암호화, ② 패스워드 입력 없으면 기존 패스워드를 복호 후 새 키 AAD로 재암호화(실패 시 500 + 직접 입력 안내). `DatasourceKey` 업데이트 + `WebProducts.DatasourceKey` 참조 업데이트. 응답에 `key_changed: bool` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `_dsRenderForm` save 핸들러: `await apiFetch(PATCH)` 응답의 `key`(`updated.key || ds.key`)로 `_dsSelectedKey` 동기화 → 키 변경 후에도 목록 선택 유지.
- 비변경: RBAC(console.manage), 신규 엔드포인트, WebDatasources 스키마, DEK/KEK 키 구조. 암호화 알고리즘(AESGCM) 동일.
- 검증: py_compile app.py PASS, node --check admin.js PASS.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/admin.js, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: app.py 두 함수 변경 전 상태 복원 + admin.js save 핸들러 `ds.key` 직접 참조 복원.

## CHG-20260611-0218
- Date: 2026-06-11
- Task: TASK-0218 (데이터소스 키 명시적 rename 지원 + AAD 자가수복), **Minor §12.3**
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_seed_main_mysql_datasource`: `main_mysql` 행이 DB에 없을 때(이미 rename됨)의 `else` 브랜치 추가. 해시 키 행의 `PasswordEnc` 를 현재 키 AAD로 복호 시도 → 실패 시 구 AAD(`main_mysql`)로 복호 → 성공 시 현재 키 AAD로 재암호화하는 자가수복 로직. 복호 완전 실패 시 silent pass(수동 재입력 필요).
    - `admin_update_datasource`: PATCH body `key` 필드 수신 추가 — `_ds_valid_key`로 검증 후 `explicit_new_key` 로 처리. `new_k` 결정 순서: ① 명시 키(`body.key`, 현재 키와 다를 때) ② 엔진+호스트+포트 해시 재계산. 기존 패스워드 재암호화·`DatasourceKey` 업데이트·`WebProducts.DatasourceKey` 참조 업데이트 경로 동일. 409 에러 메시지 간결화.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `_dsRenderForm`: 수정(`isEdit`) 시 key 필드 `readonly` → `false`(편집 가능), `is-readonly` CSS 클래스 제거. 라벨 "키" → "키 (변경 시 수정)".
    - `_dsRenderForm` save 핸들러: `k === "key"` 분기 추가 — 수정 시 값이 원래 키와 다를 때만 `body.key = v` 로 전송, 신규 생성 시 미전송 유지.
- 비변경: RBAC(console.manage), 신규 엔드포인트, WebDatasources 스키마, DEK/KEK 키 구조, 암호화 알고리즘(AESGCM).
- 검증: py_compile app.py PASS, node --check admin.js PASS.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/admin.js, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: app.py `else` 브랜치 제거 + `admin_update_datasource` `explicit_new_key` 로직 제거. admin.js key 필드 `readonly=true` 복원.

## CHG-20260611-0223
- Date: 2026-06-11
- Task: TASK-0223 (제품별 insight-worker 분석 완료율 UI), **Major §12.3** (read-only 통계, RBAC·스키마·암호화·외부계약 변경 0)
- 변경:
  - `unit/feature-0002-agent-core/src/modules/db.py`:
    - 신규 `list_information_schema_tables(datasource, *, schemas, database, timeout, cap)`: datasource 의 `information_schema.TABLES` 에서 `(schema, table)` 객체 목록을 **flag-무관 직결**로 열거(`list_server_databases_classified` 패턴 — `connect()` 의 flag-gated datasource 경로 우회). MySQL=`TABLE_SCHEMA IN (schemas)`(VIEW 포함, insight 정합), MSSQL=`database` 1개 컨텍스트 + `_MSSQL_SYSTEM_SCHEMAS` 제외. 신규 상수 `_MSSQL_SYSTEM_SCHEMAS`.
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - 신규 헬퍼 `_compute_product_insight_coverage(conn, product)`: 제품 accessible DB 기준 분석 완료율 산출. 분자=PG `rag_objects`(conv=`__insight_worker__`, scope=`common`, object_type∈{schema,table}) 의 통찰 보유 객체, **catalog-driven 매칭**(라이브 (schema,table) ∩ rag (schema,table), set dedup). datasource 스코핑=`_dsr.scope_key`(엔드포인트 해시); 기본 엔드포인트면 `datasource_key IS NULL`(ds=None 스캔)도 허용. 분모 연결은 resolve 된 datasource RO 좌표(SSRF 가드+pinned IP, timeout 5s, per-datasource 실패 격리). MSSQL 비-default_db 접근DB=미스캔(analyzed 0+flag).
    - 신규 엔드포인트 `GET /api/admin/products/insight-coverage` (`admin_products_insight_coverage`): `console.access`. `?product_id=` 단건, `?refresh=1` 캐시 무시. 인메모리 TTL 캐시(90s) `_INSIGHT_COVERAGE_CACHE` + 헬퍼.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `adminState.productCoverage`(Map)+`productCoverageLoading`. `loadProductInsightCoverage()` (loadAdminData 후 fire-and-forget). `buildCoverageBadge`(목록 row 배지)+`buildProductCoverageDetail`(상세 전체%+per-DB breakdown+새로고침)+`_coverageTone`. `renderProductList` row 에 배지, `renderProductDetail` 접근 가능 DB 섹션에 breakdown 삽입.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.cov-badge`/`.cov-bar`/`.cov-db-row` 등 완료율 시각 스타일(등급별 색: ok≥80/warn≥40/low/muted).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260611-insight-coverage`.
- 비변경: RBAC 카탈로그, WebProducts/WebProductDatabases/rag_objects 스키마, 암호화 경로, insight-worker write 경로. 기존 엔드포인트 계약.
- 검증: py_compile app.py+db.py PASS, node --check admin.js PASS, verify-completion(코드 게이트) + 라이브 실측 + PB-0008 Windows-browser.
- Files: unit/feature-0002-agent-core/src/modules/db.py, unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: app.py 신규 헬퍼·엔드포인트·캐시 제거 + db.py `list_information_schema_tables`/`_MSSQL_SYSTEM_SCHEMAS` 제거 + admin.js/styles.css/admin.html coverage 추가분 복원.

## CHG-20260611-0225
- Date: 2026-06-11
- Task: TASK-0225 (textarea 우측 하단 핸들 더블클릭 시 내용 높이로 자동 확장), **Minor §12.3** (비파괴 프런트 추가, 백엔드·RBAC·스키마·암호화·외부계약 변경 0)
- 변경:
  - 신규 `unit/feature-0003-agent-web-ui/src/static/textarea-autogrow.js`: document 레벨 `dblclick` capture 위임 핸들러. `resize: vertical|both` 인 textarea 에 한정, 더블클릭 좌표가 우측 하단 native resize 핸들 영역(`GRAB_PX=18`) 안일 때만 발동(본문 더블클릭=단어선택은 통과). `fitToContent`: `style.height="auto"` → `scrollHeight` 측정 → border-box 보정 후 적용, 상한 `MAX_PX=600`. capture phase 로 본문 선택 동작보다 먼저 핸들 영역 가로챔.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: `textarea-autogrow.js?v=20260611-dblclick-autogrow` script 태그 추가(app.js 다음).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 동 script 태그 추가(admin.js 다음). 동적 생성 `.admin-prompt-textarea` 도 capture 위임으로 자동 커버.
  - `unit/feature-0003-agent-web-ui/src/static/share.html`: 동 script 태그 추가(share.js 다음).
- 비변경: 백엔드(app.py 무수정), RBAC, 스키마, 암호화, 신규 엔드포인트, 기존 JS 의 promptInput auto-grow(input 이벤트) 로직. share.js 의 클립보드용 숨김 textarea 는 대상 아님(resize 핸들 없음).
- 검증: node --check textarea-autogrow.js PASS, verify-completion(코드 게이트), 배포 후 PB-0008 Windows-browser 시각검증 예정.
- Files: unit/feature-0003-agent-web-ui/src/static/textarea-autogrow.js, unit/feature-0003-agent-web-ui/src/static/{index,admin,share}.html, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: textarea-autogrow.js 삭제 + 3개 html 의 script 태그 1줄씩 제거.

## CHG-20260611-0226
- Date: 2026-06-11
- Task: TASK-0226 (MSSQL 제품 분석 완료율 미표시(연결) 수정 — per-DB 연결 격리; 동시세션 TASK-0225 충돌로 재번호 §13.1), **Minor §12.3** (TASK-0223 후속 버그수정, RBAC·스키마·엔드포인트 0)
- 진단: MSSQL 제품(`mssql_local`)이 "측정 불가" — RO 로그인 `agent_ro` 가 `dk_data_release` 만 GRANT(123 테이블, rag 123/123=100%), 나머지 4 DB 권한없음(18456). bug1=accessible DB 전체 단일 try/except → 한 DB 실패가 전체 오염. bug2=`scannable=default_db` 게이트(None)가 분석된 DB 마저 미스캔 처리.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py` `_compute_product_insight_coverage`: MSSQL 분기 **per-DB try/except 격리** — DB별 연결 실패는 `connected=False`+note, 나머지 정상 집계. `scannable`(default_db) → `connected` 대체. 비연결 DB 는 분모 제외. 전부 실패 시 reason. MySQL 경로는 단일 try 유지(회귀 0). `base["default_db"]` 추가(unused 제거).
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: per-DB 렌더 `d.scannable`→`d.connected`, 비연결="연결 불가"(cov-low). 배지/요약 "연결 불가" vs "대상 없음" 구분(per_db.connected===false 검사). total=0 도 per-DB 목록 노출. MSSQL 안내 "RO GRANT 없는 DB=연결 불가, 집계 제외".
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260611-mssql-coverage-perdb`.
- 비변경: RBAC, 스키마, 엔드포인트(`/api/admin/products/insight-coverage` 응답 shape 만 `scannable`→`connected`+`note` 확장), insight write, 매칭 의미론(catalog-driven 동일).
- 검증: py_compile app.py PASS, node --check admin.js PASS, make test + 라이브 실측 + PB-0008.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION,TEST}.md
- Rollback: app.py MSSQL 분기를 단일 try + scannable 게이트로 복원, admin.js connected→scannable 복원.

## CHG-20260611-0227
- Date: 2026-06-11
- Task: TASK-0227 (실행 단계 사이드 패널 갱신 시 "결과 보기" 펼침 상태 유지), **Minor §12.3** (frontend-only, RBAC·스키마·엔드포인트·백엔드 0)
- 진단: 실행 단계 사이드 패널(`#stepSidePanel`)에서 한 단계의 "결과 보기"를 펼쳐 결과셋을 보던 중, 폴링으로 새 단계가 추가되면 패널이 통째로 재렌더되며 펼쳐둔 결과셋이 닫힘. 근본 원인 = `_renderStepSidePanelBody`가 `body.innerHTML=""`로 전체를 비우고 재생성하는데, 펼침 여부가 DOM 로컬 변수(`resultBody.hidden`)로만 존재해 재렌더 시 기본값(닫힘)으로 리셋. (스크롤 위치는 이미 스냅샷/복원하던 비대칭.)
- 변경:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `state.stepResultExpanded`(Set) 신설 — 펼친 단계의 안정 키 영속화.
    - `_stepResultKey(step, idx)` 헬퍼 — `progressSteps` dedup과 동일한 `step_index:created_at` 키(둘 다 없으면 `idx:` fallback).
    - `buildStepDetailEl` 결과 토글: 초기 `hidden`/버튼 라벨/`aria-expanded`를 Set에서 복원, 토글 클릭 시 add/delete.
    - `resetProgressTracking` + `applyProgressPayload`의 runId 변경 분기에서 `state.stepResultExpanded.clear()` — run 전환 시 다른 run의 동일 step 키 혼동 방지.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: 캐시버스터 `?v=20260611-step-result-persist`.
- 비변경: 백엔드(app.py 무수정), RBAC, 스키마, 암호화, 엔드포인트, `buildSqlStepPanel`(완료된 채팅 메시지용 — run 완료 후 폴링 정지로 재렌더 안 됨, 본 버그 무관), progress strip 레거시 카드(`renderProgress`는 `buildStepDetailEl` 공용 → 동일 혜택).
- 검증: node --check app.js PASS, verify-completion(코드 게이트), 배포 후 PB-0008 Windows-browser 시각검증 예정.
- Files: unit/feature-0003-agent-web-ui/src/static/app.js, unit/feature-0003-agent-web-ui/src/static/index.html, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: app.js의 `state.stepResultExpanded`·`_stepResultKey`·토글 복원/저장·clear 4개 변경 되돌림, index.html 캐시버스터 복원.

## CHG-20260612-0245
- Date: 2026-06-12 (TASK-0245, **Minor §12.3** — 제품 상세 접근가능 DB 리스트 행 컬럼 정합)
- Scope: 관리 콘솔 제품 상세 `접근 가능 데이터베이스` 통합 리스트(`.cov-db-row`)의 컬럼 폭이 문자열 길이에 따라 들쭉날쭉하던 것을 고정폭 트랙으로 정렬. CSS 전용 — 백엔드/API/스키마/RBAC/시크릿 무변경.
- 배경: `.cov-db-row` 가 행 단위 `display:grid` 인데 `grid-template-columns` 의 통계·상태칩·초기화 컬럼이 `auto` 라 행마다 콘텐츠 폭(`37/37`↔`123/123`, `DB✓`↔`연결 불가`)이 달라짐 → 남는 폭을 분배받는 name/role `fr` 컬럼이 행마다 어긋나 역할설명·진척바 시작 x 불일치(green-line 보고).
- 변경 ([src/static/styles.css](../src/static/styles.css)):
  - `.cov-db-row` `grid-template-columns`: `minmax(56px,0.8fr) minmax(0,1.6fr) 96px auto auto auto 24px` → `minmax(96px,0.9fr) minmax(0,1.7fr) 96px 54px 76px 60px 24px` (통계 54·상태 76·초기화 60 고정).
  - `.cov-db-status` + `.cov-db-reset`: `justify-self: start` 추가 — 고정폭 컬럼에서 grid item stretch 로 pill/button 이 늘어나지 않고 자연폭 유지(좌측 정렬).
  - admin.html 캐시버스터 `?v=20260612-ds-picker-status` → `?v=20260612-db-row-align`.
- 비변경: `.cov-db-stat` 우측 정렬·마이크로바·셀 빌더(buildDbCoverageCells/buildDbRoleCell) JS·권한 게이트·데이터 무변경. 행 콘텐츠/구조 동일, 트랙 폭만 고정.
- 검증: CSS brace 균형 OK. 배포 후 PB-0008 Windows-browser 시각검증(행 간 정렬 일치).
- Files: unit/feature-0003-agent-web-ui/src/static/styles.css, unit/feature-0003-agent-web-ui/src/static/admin.html, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: `grid-template-columns` 를 이전 값으로 환원 + `justify-self` 2줄 제거(정렬만 이전 들쭉날쭉으로 복귀, 기능 무관).

## CHG-20260612-0251
- Date: 2026-06-12 (TASK-0251, **Major §12.3 — 익명 공유뷰 데이터 노출 경계**) — 공유 페이지 SQL "쿼리 열고닫기" 토글을 의도된 "실행 쿼리 전환" navigator 로 교정 + 누락된 백엔드 steps 공급 + 익명 sanitize.
- Scope: `/share/{token}` 익명 공유 페이지의 SQL/결과 표시. ① share.js 가 본문 ```sql``` 블록을 "쿼리 보기/닫기" 열고닫기 토글로 감싸던 것(사용자가 본 그 버튼) 제거 → 본문 SQL 항상 펼침. ② 답변의 execute_sql 단계를 메인 UI 와 동일한 ◀▶ navigator(결과셋별 쿼리 전환)로 렌더. ③ 그 navigator 데이터(meta.steps)를 share API 가 공급하지 않던 것을 동적 조립로 보강. ④ 익명 노출이므로 step sanitize.
- 배경/진단(라이브):
  - share.js 의 `collapseSqlCodeBlocks` 가 markdown ```sql``` 블록을 토글로 감쌌다. 사용자 토큰(conv 20260612055236, msg id=554)은 meta=`{run_id,duration_ms}`뿐 + 본문에 ```sql``` 블록 → 정확히 이 토글이 노출됨.
  - 메인 UI(app.js)는 `meta.steps`(execute_sql 단계)를 `buildSqlNavigator` 로 전환하나, **share API(`_share_load_messages`→`_conv_load_messages_raw`)는 저장 `meta_json` 만 읽어 steps 가 없다**(라이브 PG: 저장 message meta 에 steps/result_summary 0건 — steps 는 일반 로드 경로가 `agent_runtime.steps` 에서 동적 조립). 즉 navigator 데이터 공급원이 share 경로에 부재.
- 변경:
  - [src/static/share.js](../src/static/share.js): `collapseSqlCodeBlocks` 제거(본문 SQL 항상 펼침). `renderAssistantDetails` 가 meta.steps 의 execute_sql 단계 렌더(1개=`buildSqlStepPanel`, 2+=`buildSqlNavigator` ◀▶ 전환 + "쿼리 N/M" + "대상: schema.table" + ←→Home End 키보드). 메인 UI helper 이식: `buildSqlStepPanel`/`buildSqlNavigator`/`buildPreviewTable`/`formatSqlForDisplay`(`` sentinel 포함)/`extractFirstTableRef` + `SQL_FORMAT_KEYWORDS` 상수. steps 없는 구형 메시지는 기존 `final_sql`/`result_rows` 폴백 유지.
  - [src/static/share.css](../src/static/share.css): `.share-sql-toggle-*` 제거, `.share-sql-navigator`/`.share-sql-group`/`.share-step-reason`/`.share-result-table-wrap` 신규(@media print 는 비활성 패널 모두 펼침).
  - [src/static/share.html](../src/static/share.html): 캐시버스터 `?v=20260610-share-md` → `?v=20260612-share-sql-nav`(share.js·share.css).
  - [src/app.py](../src/app.py): **(핵심)** `_share_attach_sanitized_steps` 신설 — `_share_load_messages` 가 assistant 메시지(redact 안 된)에 `_load_steps_for_message`(agent_runtime.steps)로 steps 동적 조립 → navigator 라이브 동작. **(보안)** `_share_sanitize_step` — 익명 노출용 화이트리스트 `{tool,sql,reason,intent,work,result_summary.preview_table}` 로 재구성(csv_paths[서버 `/shared/` 경로]·preview[결과 전문]·args·error 제거). `_SHARE_REDACTED_META_KEYS` 에 `steps` 추가(attachment_derived 메시지 redact + steps 재조립 skip 이중 차단).
- 보안(REV-20260612-0251, outside-voice 적대): BLOCKER(steps 경유 csv_paths/preview/args/error 익명 누출)→`_share_sanitize_step` 흡수(라이브 검증: step 직렬화에 csv_paths 0·preview 0·`/shared/out` 0). MINOR(sentinel 누락 주장)→오탐 기각(`cat -A` + 라이브 `LIMIT 10` 정상). XSS=textContent 일관 PASS. version gate=steps 재조립이 redact 안 된 assistant 메시지만 + attachment 항상 steps 제거로 정합.
- 비변경: RBAC 권한·DB 스키마·암호화·신규 엔드포인트 0(읽기 경로 steps 조립+sanitize). 메인 UI(app.js) 무변경.
- 검증: 신규/보강 4 테스트(steps redact·정상 steps 보존·sanitize 가 csv_paths/preview/args/error 제거·malformed 안전) + make test 컨테이너 **599 PASS(회귀 0, skip 2)** + ruff clean + node --check share.js + CSS brace 균형 + py_compile. Playwright 실 헤드리스 chromium 2종(mock + 라이브 sanitized 대화 20260527044221 id=128 8 execute_sql) ALL PASS.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{share.js,share.css,share.html}, unit/feature-0003-agent-web-ui/tests/test_share_redaction_invariant.py, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md, unit/feature-0003-agent-web-ui/docs/reviews/20260612T010000Z-share-anonymous-exposure.md, docs/STATUS.md
- Rollback: share.js 의 `renderAssistantDetails` 를 final_sql/result_rows 단일 표시 + `collapseSqlCodeBlocks` 토글로 환원, app.py 의 `_share_attach_sanitized_steps` 호출/`_share_sanitize_step`/`steps` redact 키 제거(공유 페이지가 다시 본문 토글 + 단일 SQL 로 복귀).

## CHG-20260612-0252
- Date: 2026-06-12 (TASK-0252, **doc-only** — TASK-0251 PB-0008 Windows-browser 완료 게이트 기록)
- Scope: 문서 전용 — 코드/정적자산/스키마/RBAC 0. TASK-0251(공유 페이지 SQL navigator) 의 라이브 배포 후 PB-0008 Windows-browser 시각검증 PASS 결과를 TEST.md §4 에 기록하고 STATUS.md/TASK.md 의 잔여 항목을 완료로 갱신.
- 변경: TEST.md §4(TASK-0251 Windows-browser Run — 사용자 토큰 토글 0·본문 SQL 펼침 / steps 토큰 navigator "쿼리 1/8"↔"8/8" ▶◀ click hit-test 전환 / 익명 API csv_paths·preview 누출 0), STATUS.md(TASK-0251 잔여→완료), TASK.md(AC5 체크).
- 검증: doc-only — 코드 변경 없음(make test 무관). PB-0008 실측은 TASK-0251 배포본(main 9cee54a) 대상.
- Files: docs/STATUS.md, unit/feature-0003-agent-web-ui/docs/{TASK,TEST,MODIFY,REVIEW}.md
- Rollback: 문서 기록 제거(실제 시스템 영향 0).

## CHG-20260615-0256
- Date: 2026-06-15 (TASK-0256)
- Scope: 웹 UI 정적자산 — markdown ```diff 블록 렌더 + CSS. 백엔드/API/스키마/RBAC 0.
- 변경: app.js enhanceDiffBlocks(marked.parse→enhance→DOMPurify.sanitize) 신설 — <pre><code class="language-diff"> 를 라인별 <span class="diff-line ..."> 로 재구성(textContent 양방향, 새 HTML 주입 없음). share.js 동일 parity. styles.css/share.css diff 팔레트(다크 코드배경 #1a1b26/#1e293b 정합). index.html/share.html 캐시버스터 bump.
- 검증: node --check app.js/share.js PASS. 렌더 동작은 PB-0008(배포 후).
- Files: src/static/{app.js,share.js,styles.css,share.css,index.html,share.html}, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: enhanceDiffBlocks 호출 제거(원래 marked.parse 직접 sanitize) + CSS/캐시버스터 환원.
- Deploy: web 재빌드(정적자산 베이킹).

## CHG-20260615-0260
- Date: 2026-06-15 (TASK-0260)
- Scope: 웹 UI 정적자산 — 답변 SQL navigator(◀▶ 결과셋 전환) 확장 높이 보존. 백엔드/API/스키마/RBAC/CSS 0.
- 변경: `buildSqlNavigator`(app.js + share.js parity)에 navigator 인스턴스별 `maxPanelHeight` 추적 + `preserveHeight()`(panels.scrollHeight 가 더 크면 `panels.style.minHeight` floor 갱신) 추가. `update()` 가 전환 전(나가는 패널)·후(들어오는 패널) 2회 측정 → 본 적 있는 최대 높이를 바닥으로 박아 작은 결과셋으로 전환해도 panels 컨테이너 축소 안 됨(아래 콘텐츠/스크롤 점프 제거). 축소만 방지·확장 허용. min-height 는 JS inline 동적 설정(CSS 파일 무변경). index.html/share.html 캐시버스터 bump.
- 검증: node --check app.js/share.js PASS + Playwright headless chromium 격리 검증(큰 1000px→작은 2행 전환 panels.h 불변·점프 0px; 수정 전 대조 960px 점프 재현). 실 동작은 PB-0008(배포 후).
- Files: src/static/{app.js,share.js,index.html,share.html}, docs/{TASK,MODIFY,REPORT}.md, docs/STATUS.md(repo)
- Rollback: `preserveHeight()`/`maxPanelHeight` 제거 + `update()` 의 preserveHeight 2호출 제거 + 캐시버스터 환원(navigator 가 다시 활성 패널 높이로 컨테이너 재조정 = 점프 복귀).
- Deploy: web 재빌드(정적자산 베이킹).

## CHG-20260615-0261
- Date: 2026-06-15 (TASK-0261)
- Scope: 대화 화면 제품 드롭업 datasource 네트워크 상태 배지. app.py(read-only enrich) + 정적자산. RBAC/스키마/엔드포인트 shape 0.
- 변경: 신규 `_attach_product_conn_status(conn, products)`(app.py) — conn_health `snapshot()`(TASK-0250 모니터, 추가 probe 없음)을 `datasources.resolve(key)→scope_key` 로 매핑(admin all_datasources→scope_key 와 동일 키)해 각 product 의 datasources[] 에 `conn_status`{status,elapsed_ms,checked_at} + product 레벨 `conn_status_overall`(최악: unstable>unknown>healthy) 첨부. 좌표/비번 비노출, graceful(unknown), 바인딩없음 None. `get_session`(/api/session)·`auth_me`(/api/auth/me) 두 호출 직후 enrich(admin 경로 _list_products 무영향). frontend `buildProductDropupItem`(app.js) 가 `connStatusOverall`→dot `.product-dropup-item-dot--conn`+`.is-ok/.is-fail/.is-unknown`+title/aria-label, `connStatusMeta` 헬퍼, datasource 배지 tooltip 에 상태 라벨 병기. styles.css conn dot 색(specificity 0,3,0 override). index.html 캐시버스터 bump(styles.css·app.js).
- 검증: 신규 test_product_conn_status.py 8 PASS + make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0) + ruff clean + node --check app.js + CSS brace(1128=1128) + py_compile + Playwright 격리(healthy=초록/unstable=빨강/unknown=중립/바인딩없음=파랑) + 라이브 conn_health 실측. 실 동작은 PB-0008(배포 후).
- Files: src/app.py, src/static/{app.js,styles.css,index.html}, tests/test_product_conn_status.py, docs/{TASK,MODIFY,REPORT,REVIEW,FUNCTION}.md, docs/STATUS.md(repo)
- Rollback: `_attach_product_conn_status` 호출 2곳 + 함수 제거(products 응답에서 conn_status/conn_status_overall 사라짐) + app.js connStatusMeta/dot conn 클래스 + styles.css conn dot 규칙 + 캐시버스터 환원(dot 가 모드색으로 복귀).
- Deploy: web 재빌드(app.py + 정적자산 베이킹). ask/insight-worker 무변경.

## CHG-20260615-0256b
- Date: 2026-06-15 (TASK-0256b, frontend-only 버그수정)
- Scope: 웹 UI 정적자산 — diff 렌더 줄 간격 수정. 백엔드/API/스키마/RBAC/CSS 0.
- 변경: `enhanceDiffBlocks`(app.js/share.js)가 display:block 인 `.diff-line` span 사이에 `"\n"` 텍스트 노드를 넣어 `<pre>` 에서 이중 줄바꿈(줄마다 빈 줄) 발생 → `"\n"` 삽입 제거(block span 이 줄 구분). 변경 자산 캐시버스터만 bump.
- 검증: node --check app.js/share.js PASS. 렌더(단일 줄 간격)는 PB-0008(배포 후).
- Files: src/static/{app.js,share.js,index.html,share.html}, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: `"\n"` 삽입 복원(이중 줄바꿈 회귀).
- Deploy: web 재빌드(정적자산). ask-worker 무관(프롬프트 무변경).

## CHG-20260615-0263
- Date: 2026-06-15 (TASK-0263 — 동시세션 TASK-0262[chip-conn-color] 선점으로 재번호)
- Scope: LLM 사용량 차트 hover 비용 + 클릭→집계 기여 대화목록 모달. app.py(신규 read 엔드포인트 2 + 헬퍼) + 정적자산. RBAC 카탈로그/스키마/기존 엔드포인트 shape 0.
- 변경:
  - (백엔드 app.py) 신규 `GET /api/admin/usage/conversations`(console.usage.read AND conversation.list.any) + `GET /api/profile/usage/conversations`(로그인·owner=self 강제). `_query_usage_conversations`(llm_usage ⋈ core_conversations INNER + conversation_id NOT NULL, 차원 필터 model/account_ids/day/owner 파라미터 바운드, gran 화이트리스트 to_char, 대화별 fold + models[] + cost, LIMIT 200+truncated, 좌표/비번/본문 비노출). `_usage_account_ids_for_role`(시스템→None·역할없음·역할명 역매핑), `_parse_usage_conv_params`, `_enrich_usage_conv_owner_meta`(admin 만). admin_llm_usage by_day_model 에 cost_usd(prompt/completion 합 추가). profile_llm_usage by_model/by_day_model/totals 에 cost_usd 추가.
  - (admin.js) renderStacked(일별)·renderStackedHBar(역할/계정) tooltip 모델별 비용 병기 + 차트 요소 data-usage-model/day 후크 + bindUsageDrill(위임 클릭)·openUsageConversations(fetch)·showUsageConvModal(모달, deep-link /?conversation=). 계정 drill 행 클릭→대화 모달.
  - (app.js) renderProfileUsageStacked/Donut <title> 비용 병기 + 클릭 후크 + bindProfileUsageDrill·openProfileUsageConversations·showProfileUsageConvModal(본인 전용) + 추정비용 카드 + initializeWorkspace 가 ?conversation= deep-link 선호 활성화(URL replaceState 정리).
  - (styles.css) usage-conv 모달(admin 넓은 .usage-conv-modal/head/close + profile 독립 .usage-conv-overlay/dialog) + .admin-usage-clickable/.profile-usage-clickable 커서. index.html/admin.html 캐시버스터 ?v=20260615-task0263-usage-drill.
- 검증: 신규 test_usage_conversations.py 11 PASS + make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0) + ruff clean + node --check app.js/admin.js + CSS brace + py_compile + Playwright 격리(막대 클릭→차원 추출). outside-voice 적대적 보안 리뷰 SHIP(REV-20260615-0263, BLOCKER/MAJOR 0).
- Files: src/app.py, src/static/{admin.js,app.js,styles.css,index.html,admin.html}, tests/test_usage_conversations.py, docs/{TASK,MODIFY,REPORT,REVIEW,FUNCTION}.md, docs/STATUS.md(repo)
- Rollback: 두 엔드포인트 + 헬퍼 제거(app.py), admin.js/app.js 의 bindUsageDrill/openUsageConversations/show*Modal + 차트 data-usage 후크 + hover 비용 추가분 + initializeWorkspace deep-link 분기 제거, styles.css usage-conv 규칙 제거, 캐시버스터 환원. by_day_model/by_model cost_usd 추가는 무해(프론트 미사용 시 무시).
- Deploy: web 재빌드(app.py + 정적자산). ask/insight-worker 무변경.

## CHG-20260615-0266
- Date: 2026-06-15 (TASK-0266 — TASK-0263 핫픽스; 동시세션 TASK-0264/0265 선점으로 0265→0266 재번호)
- Scope: app.py 1줄 SQL 문법 수정 + 회귀 가드 테스트. 백엔드/스키마/RBAC/정적자산 0(엔드포인트 동작만 정상화).
- 변경: `_query_usage_conversations` 의 `win = "now() - interval %s"` → `"now() - %s::interval"`. PG 는 `interval $1`(파라미터) 문법 불허(리터럴만) → 라이브 500(`syntax error at or near "$1"`). 캐스트(`%s::interval`)는 파라미터 허용 → days 바인드 유지하며 정상. 회귀 가드 `test_q2b_interval_cast_not_bare_param`(SQL 정적 검증) 추가.
- 검증: test_usage_conversations.py 12 PASS(기존 11 + 가드) + py_compile + **라이브 검증**(worktree app.py 임시 web 적용: admin 34건 HTTP 200·좌표/본문 누출 0, 일자 차원 필터 1건·차트 by_day 정합, profile 200).
- Files: src/app.py, tests/test_usage_conversations.py, docs/{TASK,MODIFY,REPORT,REVIEW}.md, docs/STATUS.md(repo)
- Rollback: `%s::interval` → `interval %s` 환원(= 버그 복귀). 권장 안 함.
- Deploy: web 재빌드(app.py). ask/insight-worker 무변경.

## CHG-20260615-0256c
- Date: 2026-06-15 (TASK-0256c)
- Scope: 웹 UI 정적자산 — diff 줄번호 gutter + 복사 클린. 백엔드/API/스키마/RBAC 0.
- 변경: `enhanceDiffBlocks`(app.js/share.js) — 각 줄을 buildDiffRows 로 분해, 맨 앞 `+`/`-` 마커를 코드에서 분리(stripDiffMarker)하고 old/new 줄번호 계산(parseDiffHunkHeader `@@` seed, 없으면 1부터). 줄번호+마커는 `data-gutter` 속성 → CSS `::before content` 로만 렌더(의사요소=선택/복사 비포함 + user-select:none). 코드는 마커 제거 후 textContent. styles.css/share.css `.diff-line::before` gutter + `--diff-gutter-ch`(2w+3, DOMPurify 가 inline style 제거해도 var fallback 7 로 graceful). 캐시버스터 bump.
- 검증: node 로직(줄번호/마커제거/hunk seed) + node --check PASS. 렌더·복사는 PB-0008(배포 후).
- Files: src/static/{app.js,share.js,styles.css,share.css,index.html,share.html}, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: enhanceDiffBlocks/CSS 를 TASK-0256b 시점으로 환원(줄번호·gutter 제거, 마커 포함 코드 표시).
- Deploy: web 재빌드(정적자산). ask-worker 무관(프롬프트 무변경).

## CHG-20260615-0256d
- Date: 2026-06-15 (TASK-0256d)
- Scope: web app.py — HTML 엔트리포인트 캐시 헤더. RBAC/스키마/엔드포인트 계약/데이터 0.
- 변경: index()/admin_index()/share_page() 의 FileResponse 에 `headers={"Cache-Control":"no-cache"}`(_HTML_NO_CACHE) 추가. 정적 자산 `?v=` 캐시버스터가 항상 적용되도록 HTML 을 매 로드 조건부 재검증.
- 검증: test_html_no_cache(3-route, FileResponse 가로채) + make test PASS.
- Files: src/app.py, tests/test_html_no_cache.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: headers 인자 제거(휴리스틱 캐싱 복귀).
- Deploy: web 재빌드.

## CHG-20260615-0268
- Date: 2026-06-15 (TASK-0268 — 동시세션 TASK-0267[perm-tree] 선점으로 0267→0268 재번호)
- Scope: 프로필 아바타 / 제품 아이콘 이미지 업로드·서빙·삭제 + Identicon 기본. app.py(스키마 ALTER + 엔드포인트 6 + 헬퍼) + 정적자산. RBAC 카탈로그/시크릿 0(product.manage 재사용).
- 변경:
  - (스키마) WebAccounts.AvatarObjectKey + WebProducts.IconObjectKey 멱등 ALTER — `_ensure_web_tables`(slow) + `_ensure_avatar_icon_schema`(fast-path `_ensure_seed_catchup`) 양쪽. 계정 SELECT chokepoint + `_list_products` SELECT 에 컬럼 추가.
  - (직렬화) `_serialize_account`→`avatar_url`, `_list_products`→`icon_url`. `_avatar_url_for`/`_product_icon_url_for`(object key sha256[:12] 캐시버스터, 미설정 None).
  - (엔드포인트) `PUT/DELETE /api/auth/me/avatar`(self-service 로그인만, owner=self 강제) + `GET /api/avatars/{id}`(로그인). `PUT/DELETE /api/admin/products/{id}/icon`(product.manage) + `GET /api/products/{id}/icon`. 이전 object best-effort 삭제(DB commit 후).
  - (검증) `_sniff_image`(매직바이트 png/jpg/webp만, 클라 MIME 불신, SVG/GIF 거부) + `_store_image_upload`(크기 cap 2MB/5MB, MinIO prefix `avatars/<id>/`·`product-icons/<id>/`, uuid+ext 파일명 미사용) + `_serve_image_object`(content-type 역추론 + `X-Content-Type-Options: nosniff` + `Content-Disposition: inline`).
  - (프론트) app.js `identiconSvg(seed)`(해시 5x5 대칭 SVG·외부의존0·결정론적) + `applyAvatar(el,{url,seed,initials})`(이미지 or Identicon, onerror 폴백). renderAccountState/renderProfile 아바타 + 드로어 업로드/제거 UI(index.html). buildProductDropupItem 아이콘 이미지(설정 시). admin.js renderProductDetail 제품 아이콘 이미지·업로드/제거(product.manage). styles.css 아바타/아이콘/Identicon. index.html·admin.html 캐시버스터 `?v=20260615-task0268-avatar`.
- 검증: 신규 test_avatar_icon_upload.py 8 PASS + make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0) + ruff + node --check app.js/admin.js + CSS brace(1175=1175) + py_compile + Playwright(Identicon 결정론·구분) + 라이브 라운드트립(PNG 업로드→서빙 200 image/png·nosniff, SVG 거부, 삭제→null) + outside-voice 보안 리뷰 SHIP(REV-0268).
- Files: src/app.py, src/static/{app.js,admin.js,styles.css,index.html,admin.html}, tests/test_avatar_icon_upload.py, docs/{TASK,MODIFY,REPORT,REVIEW,FUNCTION}.md, docs/STATUS.md(repo)
- Rollback: 6 엔드포인트 + 헬퍼(_sniff_image/_store_image_upload/_serve_image_object/_avatar_url_for/_product_icon_url_for/_ensure_avatar_icon_schema) 제거, SELECT/직렬화 avatar_url/icon_url 제거, ALTER 는 컬럼 잔존(무해). 프론트 identicon/applyAvatar/업로드 UI 제거 + 캐시버스터 환원. 컬럼 DROP 은 별도 cleanup.
- Deploy: web 재빌드(app.py + 정적자산). ask/insight-worker 무변경.

## CHG-20260615-0272
- Date: 2026-06-15 (TASK-0272; 동시세션이 TASK-0271/CHG-20260615-0271 선점→§13.1 재번호 0271→0272)
- Scope: 대화 화면 프로필 드로어 첫 진입 시 `프롬프트 > 제품 범위`(`#promptProductSelect`) 비어있는 버그 수정. 프론트엔드 단일 파일(app.js) + 캐시버스터. RBAC/스키마/엔드포인트/데이터 0.
- 변경:
  - (app.js) `switchProfileTab(tab)` 내부에 탭별 lazy 콘텐츠 디스패치 추가 — prompt→`initAccountPromptEditor()`, usage→`loadProfileUsage()`. `openProfile()`(기본 활성 탭) 와 탭 클릭 양쪽 경로가 `switchProfileTab` 을 거치므로 단일 진입점으로 일원화.
  - (app.js) `initialize()` 의 탭 클릭 리스너에서 중복 lazy 디스패치 제거 — `switchProfileTab` 호출만 유지.
  - (index.html) app.js 캐시버스터 `?v=20260615-task0269-conv-split` → `?v=20260615-task0272-prompt-scope`.
- 근본원인: lazy 디스패치가 탭 '클릭' 이벤트에만 배선돼 있어, 첫 진입(prompt 가 기본 활성 탭, 클릭 없음) 시 셀렉트가 미적재. `state.products` 는 부트스트랩에서 적재 완료라 데이터 문제 아님.
- 검증: node --check app.js + verify-completion --pre-commit + PB-0008 Windows-browser(프로필 첫 진입 제품 범위 채워짐).
- Files: src/static/app.js, src/static/index.html, docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md
- Rollback: lazy 디스패치를 탭 클릭 리스너로 되돌리고 `switchProfileTab` 내부 디스패치 제거(= 회귀), 캐시버스터 환원.
- Deploy: web 재빌드(정적자산). app.py/worker 무변경.

## CHG-20260615-0273
- Date: 2026-06-15 (TASK-0273, **Critical §12.3** — 대화 삭제→soft-archive; 동시세션 prompt-scope 선점 0272 → §13.1 재번호 0272→0273)
- Scope: app.py(삭제 동작 변경 + 신규 엔드포인트 + 권한 + 진행차단) + alembic 0007 + agent_runtime_schema.sql + 정적자산. 스키마 마이그레이션(컬럼 ADD, 데이터 무손실).
- 변경:
  - (스키마 3중 멱등) `core_conversations.archived_at`/`archived_by_account_id` — alembic `0007_core_conv_archived`(down=0006_datasource_health) + agent_runtime_schema.sql(CREATE+ALTER+index) + app.py MySQL 폴백 ALTER. blocked(0005) 3중 패턴 동형.
  - (삭제→archive) `_archive_conversation`(UPDATE archived_at=NOW(), archived_by, WHERE archived_at IS NULL 가드, PG+MySQL). `_delete_conversation_impl` 가 hard-delete(`delete_conversation_records`) 대신 호출 → status `archived`/`archived_pending`(첨부 cascade soft-delete 제거 — 데이터 보존). 응답 키 deleted/deleted_pending 유지(프론트 호환).
  - (목록 숨김) `_list_conversations_pg`·`_list_conversations` 둘 다 WHERE `archived_at IS NULL`.
  - (진행 차단) `_conversation_block_info` SELECT 에 archived_at 추가 → blocked_at OR archived_at 이면 차단(보관 사유). /api/ask 게이트 재사용.
  - (권한+admin) PERMISSION_DEFINITIONS 에 `conversation.archive.read.any` + admin seed 자동 + `_ensure_seed_roles` admin catchup 목록 추가. `GET /api/admin/conversations/archived`(권한 게이트, 메타만, q bound param, PG/MySQL + 계정 enrich). admin.html "보관 대화" 탭 + admin.js loadArchivedConversations/렌더 + 게이트/검색/새로고침. styles.css .admin-archives-*.
  - (fork+UI) 접근/fork 경로 archived 필터 없음(보관 참조·복제 가능). app.js 삭제 UI 라벨 "보관". 캐시버스터 ?v=20260615-task0273-archive.
- 검증: 신규 test_conversation_archive.py 7 PASS + 기존 test_product_delete_block_conv block_info SQL 3-tuple 갱신 + make test 컨테이너 전체 회귀 0(ALL=0) + ruff + py_compile + node --check + CSS brace + 라이브 라운드트립(archive→목록숨김·PG 기록·ask 403·admin 조회 count=2) + outside-voice 보안 리뷰 SHIP(REV-0273). 라이브가 2버그(PG 컬럼·admin catchup) 포착 수정.
- Files: src/app.py, unit/feature-0002-agent-core/{alembic/versions/20260615_0007_core_conv_archived.py, src/scripts/agent_runtime_schema.sql}, src/static/{app.js,admin.js,admin.html,styles.css,index.html}, tests/test_conversation_archive.py, tests/test_product_delete_block_conv.py, docs/{TASK,MODIFY,REPORT,REVIEW,FUNCTION}.md, docs/STATUS.md(repo)
- Rollback: `_delete_conversation_impl` 를 delete_conversation_records 환원(=hard-delete 복귀), archive 헬퍼/admin 엔드포인트/권한/탭/목록필터/block_info archived 분기 제거 + 캐시버스터 환원. archived 컬럼·권한 잔존(무해) / alembic 0007 downgrade 로 DROP.
- Deploy: **migrate-first 필수** — web=DML-only role. PR 머지 후 make migrate(alembic 0007) 선행 → web 재빌드. ask/insight-worker 무변경.

## CHG-20260615-0286
- Date: 2026-06-15 (TASK-20260615T183409-ds-list-multiselect, **Major §12.3** — 관리 콘솔 데이터소스 목록 다중 선택 구조; 동시세션 PR#251[ds-list-conn-badge] 이 TASK-0278·REQ-0280·AC-0509·CHG/REV-0282 선점 → §13.1 rebase 후 재번호 REQ-0281·AC-0512~0514·CHG/REV-0286. TASK id 는 timestamp 형식이라 무충돌)
- Scope: frontend 정적자산 3파일(admin.js + admin.html + styles.css). 백엔드/RBAC/스키마/엔드포인트/데이터 0.
- 변경:
  - (admin.js adminState) `datasourceSelected: new Set()`(문자열 key)·`datasourceLastClickIdx: -1` 추가 — 제품 `productSelected`/`productLastClickIdx` 동형. 단일 상세 선택 `_dsSelectedKey` 와 동거.
  - (admin.js bulk 어휘) `BULK_ENTITY_UNIT.datasources="개"` + `BULK_ACTION_LABEL.insight_on/insight_off` 추가.
  - (admin.js `_dsRenderList` 재작성) 행을 `<button.admin-list-row--nav role=option>`(단일선택 listbox)에서 `<div.admin-list-row role=row>` + `.admin-list-row-cb` 체크박스로 전환(제품 행 동형). 체크박스 click(`stopPropagation`+shift-range)·change(Set 토글) 배선, 행 click=상세. 행 children=`체크박스 + 네트워크 도트(PR#251 _paintDsConnDot, leading 통합) + main`. 신규 `_dsFiltered`(select-all/bulk/shift-range 공용 필터)·stale key prune(reload·삭제 후 선택 정리)·말미에서 update/bulk/cross-page 렌더 호출.
  - (admin.js 신규 함수) `updateDatasourceSelectAllCheckbox`·`renderDatasourceBulkBar`(console.manage 게이트, [인사이트 켜기·끄기·삭제danger]+[선택해제])·`renderDatasourceCrossPageBanner`(공용 `renderCrossPageBanner` entity="datasources")·`_dsBulkTargetable`(editable=비-env)·`_runDatasourceBulkAsync`(async partial-fail: applied/excluded/failed → 토스트 + loadAdminData·재렌더)·`bulkDatasourceSetInsight`(PATCH insight_enabled)·`bulkDatasourceDelete`(DELETE, 409=제외).
  - (admin.js initialize) `#datasourceSelectAll` change 리스너(현재 필터 add/delete)·Esc 핸들러 datasources 분기·`assertBulkBarContract` 루프에 "datasources" 추가.
  - (admin.html datasources pane) `.admin-list-head` 의 section-label 를 `#datasourceSelectAll` 전체선택 label 로 교체 + `#datasourcesCrossPageBanner`(role=status) + 목록 `role=grid aria-multiselectable` + `#datasourcesBulkBar`(role=toolbar aria-live, `.admin-list-col` 직속) 추가. 캐시버스터 styles.css/admin.js `?v=20260615-ds-multiselect`.
  - (styles.css) `#datasourceList .admin-list-row { grid-template-columns: auto auto 1fr }`(체크박스·도트·main) 추가 — PR#251 의 `#datasourceList .admin-list-row.admin-list-row--nav { auto 1fr }` override 는 `--nav` 제거로 미매칭되므로 그 자리를 대체(`--nav` 제거 + 체크박스 컬럼 추가). `.ds-conn-dot`(PR#251)·`.admin-list-row-cb`·`.admin-bulk-*`·`.admin-list-select-all` 은 재사용.
- 근본원인: 데이터소스 pane 만 계정·역할·제품의 표준 bulk 계약(체크박스+전체선택+툴바)에서 누락 — 단일선택 nav 로 잔존. CSS 는 grid override 1줄만 신규(체크박스 컬럼 추가), 나머지(`.admin-list-row-cb`·`.admin-bulk-actions`·`.admin-list-select-all`·`.admin-bulk-cross-page`·`.ds-conn-dot`)는 재사용. 제품(pending-commit) vs 데이터소스(즉시 CRUD) 모델 차이는 async runner 로 흡수.
- 검증: node --check admin.js PASS + 런타임 `assertBulkBarContract("datasources")` + 적대적 subagent 코드리뷰 SHIP(BLOCKER 0/MAJOR 0; 10개 검증항목 전부 confirmed-correct, MINOR·NIT 는 제품 패턴 기인 비회귀). PB-0008 Windows-browser 는 배포 후(잔여).
- Files: src/static/admin.js, src/static/admin.html, src/static/styles.css, docs/{FUNCTION,MODIFY,REVIEW,TASK,TEST}.md
- Rollback: `_dsRenderList` 를 `<button role=option>` 단일선택 + section-label HTML 로 환원, 신규 함수/상태/리스너/contract 항목 + styles.css grid override 제거(PR#251 --nav override 복원), 캐시버스터 환원. (전면 frontend-only 라 backend 무영향.)
- Deploy: web 재빌드(정적자산 baked). app.py/ask-worker/insight-worker 무변경 → web 단일 서비스 재배포.
## CHG-20260615-0287
- Date: 2026-06-15 (TASK-0279, **Critical §12.3** — 첨부 메타 MySQL→PG agent_runtime 통합 cutover; 동시세션 0277·0278 선점 → 0279 재번호, origin/main 6커밋 rebase)
- Scope: alembic 0008 + agent_runtime_schema.sql(§6d) + 신규 modules/attachment_pg_mirror.py + scripts/attachment_backfill.py + app.py(dual-write 미러 9 + read 게이트 7) + agent_core.py(context read 게이트) + attachment_reconciliation.py(미러 2) + 신규 test. cross-store 데이터 마이그레이션(신규 PG 테이블, 데이터 무손실 추가).
- 변경:
  - (스키마) alembic `0008_core_attachments`(down=0007_core_conv_archived): PG `agent_runtime.core_attachments`(+sandbox_schemas/derived_messages/provider_files). **id=plain bigint PK**(GENERATED ALWAYS 금지 — MySQL Id 권위 보존). `UNIQUE(root_attachment_id, version_number)` NULLS DISTINCT 동형. derived.message_id=비-FK(PG messages IDENTITY 재발급으로 id-space 불일치). 4테이블 **명시 GRANT**(superuser 적용 trap). bootstrap §6d 정합(GRANT §7 ALL TABLES 위임).
  - (모듈) `attachment_pg_mirror`: 플래그 `AGENT_RUNTIME_ATTACHMENTS_DUAL_WRITE`/`_READ_BACKEND`(전역 READ_BACKEND 재사용 금지 — 이미 postgres). 타입 정합: read 가 jsonb→`::text`(mysql.connector JSON=str 정합), timestamptz→`AT TIME ZONE 'UTC'`(naive UTC); write 는 역방향 `::timestamptz`/`::jsonb`. read 헬퍼는 MySQL-shape(PascalCase alias) dict 반환.
  - (dual-write) MySQL write commit 직후 동기·fail-soft 미러 9 지점. mirror_attachments(id 재조회 upsert ON CONFLICT id DO UPDATE, created_at 보존) / mirror_derived_messages(부모 첨부 선미러 후 derived) / mirror_conversation_attachments.
  - (read cutover) 사용자·LLM 대면 read PG 게이트(권한체크는 PG 분기 前 선행, account_id/conversation_id WHERE 동형). write-트랜잭션 내부 read(버전 MAX·sandbox enum·fork source)는 MySQL 유지(decommission 전환). PG 실패 시 MySQL 폴백.
  - (size-cap) REV MAJOR-1 흡수: `_check_attachment_size_caps` = MySQL(권위) 후 read_pg 면 `max(MySQL, PG)`(미러 누락분 과소계상→cap 우회 방지).
  - (backfill) `attachment_backfill.py` 4테이블 멱등 + `--verify`(count·SUM·missing-id) → read flip 게이트.
- Verification: 신규 test 14 PASS + make test 회귀 0 + ruff + py_compile. outside-voice 2인(REV-0286). 라이브 라운드트립은 배포 단계.
- Deploy: **migrate-first 필수**(web=DML-only role) — make migrate(alembic 0008 superuser) 선행 → web+ask-worker 재빌드(agent_core 변경). insight-worker 무변경. 플래그 단계 전환(dual-write ON → backfill → verify diff=0 → read flip).

## CHG-20260615-0288
- Date: 2026-06-15 (TASK-0279 라이브 rollout 후속, **Critical §12.3** — 데이터 이전 무결성 핫픽스)
- Scope: alembic `0009_core_attachments_drop_conv_fk`(down=0008) + agent_runtime_schema.sql §6d + test E3/E4. DDL 제약 제거(데이터·컬럼·인덱스 불변).
- 발견: 라이브 backfill 에서 272 첨부 중 **126행 FK 위반**(`fk_core_attachments_conv`) — 그 대화가 PG core_conversations 에 없음(05-27 cutover 시기, MySQL AgentCoreConversations 드롭으로 복구 불가 orphan). MySQL WebConversationAttachments 는 원래 conversation FK 가 없어 orphan 정상 존재.
- 변경: 0008 의 conversation FK(core_attachments·sandbox_schemas → core_conversations)를 제거 → faithful 이전(272 전량) + `--verify` diff=0 게이트 통과 가능. conversation_id 컬럼·`ix_core_attachments_conv` 인덱스 유지(JOIN 불변). 서브테이블 attachment_id FK(derived/provider, id 보존으로 안정)는 유지. downgrade 는 NOT VALID 재추가(orphan 허용).
- Verification: test E3(0009 DROP) + E4(bootstrap no conv FK, 서브 FK 유지) 추가 + make test 회귀 0. 라이브: 0009 적용 후 re-backfill 272 전량 + verify diff=0(예정).
- Deploy: migrate-first(alembic 0009 superuser) → re-backfill → verify → read flip.
## CHG-20260615-0277
- Date: 2026-06-15 (TASK-0277, **Critical §12.3** — 데이터소스 라벨/키 분리: 제품 바인딩을 stable surrogate Id 로 이전. 사용자 보고: 라벨 rename 시 연결 제품 미갱신)
- Scope: app.py(스키마 마이그레이션 + rename cascade + 바인딩 write dual-write + 런타임 probe). 추가형 스키마(컬럼 ADD, PK 무변경, 데이터 무손실).
- 변경:
  - (근본원인) rename(`admin_update_datasource` key_changed) cascade 가 `WebProducts.DatasourceKey` 만 갱신 → `WebProductDatasources`(1:N join)·`WebProductDatabases`(접근DB 차원) 누락 → 라벨 rename 시 제품 바인딩·접근DB 고아(미바인딩=접근 0). 삭제 경로는 3 테이블 정리(대조 증거).
  - (스키마) `_ensure_web_product_datasources_schema` step 6 — 3 테이블에 `DatasourceId BIGINT NULL` 멱등 ADD + 현재 라벨로 backfill(JOIN WebDatasources) + 단일컬럼 인덱스. 기존 PK(DatasourceKey 포함) 유지.
  - (probe) `_runtime_tables_available` 양 branch 에 3 테이블 `DatasourceId` 컬럼 검증 추가 — 미등록 시 기존 배포가 fast-path 로 마이그레이션 영구 skip(TASK-0047 함정) 방지(1054→full 마이그레이션).
  - (rename) Id 구동 완전 cascade(3 테이블, `WHERE DatasourceId=%s OR LOWER(DatasourceKey)=%s`; 컬럼 부재 시 key-only) + new_k 고아 사전제거(PK 충돌 방지) + 명시 트랜잭션(autocommit off + rollback, 부분적용 방지).
  - (바인딩 write) `admin_add/remove/set_product_datasource`·`admin_update_product_databases` dual-write `DatasourceId`(key→Id resolve, guarded). DELETE-force 경로 dangling Id 해제 + 승격 primary Id 동기화.
  - (seed) `_seed_main_mysql_datasource` legacy main_mysql→해시 rename cascade 를 3 테이블로 보강.
  - read 무변경(cascade 가 denormalized 키 신선도 보장). 컬럼 drop·read Id-JOIN 전면화·PK 이전은 차기 cycle 이월.
- 검증: 신규 test_datasource_rename_binding_stable.py 4(R1~R4) + 기존 test_datasource_edit_label_stable 3 PASS + make test 컨테이너 전체 회귀 0 + ruff clean + py_compile + 외부음성 2-pass(RBAC 적대적) NOT-SHIP→SHIP-WITH-FIXES(BLOCKER 4건 흡수).
- Files: src/app.py, tests/test_datasource_rename_binding_stable.py, docs/{TASK,MODIFY,REVIEW}.md
- Rollback: 코드 롤백만으로 회귀(추가 컬럼·인덱스는 무해 잔존, backfill 멱등). cascade/probe/dual-write 제거 시 기존 동작.
- Deploy: web 재빌드(스키마 마이그레이션은 web 부팅 `_ensure_web_tables`→probe False→실행). ask-worker/insight-worker 코드 무변경(필요 시 무해).

## CHG-20260615-0289
- Date: 2026-06-16 (TASK-20260615T183409-ds-list-multiselect PB-0008 evidence, **docs-only**) — 코드 변경 0.
- Scope: 데이터소스 목록 다중 선택(CHG-0286, main 3605443) 의 라이브 배포 + PB-0008 Windows-browser 시각검증 PASS 기록.
- 변경: docs/TEST.md(§3 PB-0008 PASS Run 추가 — 14행 div+체크박스+연결도트·grid 13px 9px 251px·전체선택 indeterminate 13/14·bulkBar buttons), docs/TASK.md(잔여 [x] 마감), docs/REVIEW.md(REV-0289 [SKIPPED:pb0008-evidence-docs-only]).
- 검증: 라이브 main 3605443 배포(healthz git_commit 일치) + win-browser eval 계측 + screenshot `artifacts/pb0008-ds-multiselect/`.
- Files: docs/{TEST,TASK,REVIEW,MODIFY}.md
- Rollback: 해당 evidence 문단 제거(무해, 코드 무관).
- Deploy: 없음(docs-only — 재배포 불필요).

## CHG-20260616-0290
- Date: 2026-06-16 (TASK-0282, **Major §12.3** — datasource 연결 상태 3단계 분류 + 느린 타-리전 연결 완화). (동시세션 CHG-20260615-0289 선점 → 0290 재번호)
- Scope: feature-0002-agent-core(config.py env 3종, conn_health.py 분류/게이트, db.py foreground elapsed) + feature-0003-agent-web-ui(app.py _RANK/​test status, admin.js·app.js·styles.css 3색 배지 + 캐시버스터). RBAC·스키마·엔드포인트 shape(필드 추가만)·SSRF 가드 무변경.
- 사용자 보고/결정: mysql-mv-qa-* 가 다른 리전이라 느림(1745ms) — 연결은 되는데 네트워크 배지·작업화면 제품목록이 "연결 불안정". (Q1) 느린-연결=빨강(불안정). (Q2) 작업화면은 연결되면 허용(fast-fail 은 down 만).
- 근본원인: conn_health TCP 선검사 timeout 100ms(`AGENT_CONN_PROBE_TIMEOUT_MS_BASE`) 고정이 다른 리전 RTT(>100ms)를 못 견뎌 연결 가능한 느린 서버를 1단 TCP 에서 unstable 로 오판(2단 DB probe 미도달). 상태도 2단계(healthy/unstable+unknown)뿐 — 끊김/불안정 미분리.
- 변경: 상태 `DOWN` 추가 → 3+1단계(healthy 초록/unstable 빨강/down 회색/unknown 확인중). `classify()` 단일 분류(성공+빠름=healthy, 성공+≥SLOW=unstable, 1회실패=blip unstable, 연속 DOWN_AFTER_FAILS=down). TCP timeout=`AGENT_CONN_TCP_TIMEOUT_MS`(2000) / 느림=`AGENT_CONN_SLOW_MS`(1000) / 끊김=`AGENT_CONN_DOWN_AFTER_FAILS`(2). `_driver_timeout_sec` base=SLOW×3(느린성공 첫 probe 보장). `should_fast_fail`=down 한정(unstable 시도 허용). db.py foreground connect 소요 측정 피드백(flapping 방지). `/test` 응답에 status. `_attach_product_conn_status` _RANK down 최악집계. 프론트 3색(is-ok/is-unstable/is-down, 레거시 is-fail 빨강 별칭 유지).
- Verification: test_conn_health 재작성 27(classify·느린성공→unstable·연속→down·gate down한정·monitor slow) + test_product_conn_status(down 최악) + test_datasource_test_nonblocking(/test status) + make test 컨테이너 전체 회귀 0 + ruff + node --check + CSS brace(1221). 적대 리뷰 REV-20260616-0290 SHIP-WITH-FIXES(흡수: foreground elapsed·rebase).
- Deploy: web + ask-worker + insight-worker 3 이미지 재빌드(conn_health 공유) → PB-0008. 캐시버스터 `?v=20260616-conn-tristate`.

## CHG-20260616-0291
- Date: 2026-06-16 (TASK-0284, **Critical §12.3** — 첨부 3개 이슈: cross-account LLM 주입 / 외부 머신 다운로드 / 파일명 지칭).
- Scope: feature-0003(app.py 주입 3경로+pending+sandbox conversation 스코프, 신규 다운로드 라우트, app.js 다운로드 2지점, index.html 캐시버스터, attachment_pg_mirror scope) + feature-0002(agent_core 주입 conversation 스코프 + 파일명 포맷). RBAC 카탈로그·스키마·기존 엔드포인트 shape 무변경.
- 사용자 보고/결정: ①다른 계정이 그 대화 조회/이어받아 질문 시 첨부가 LLM 텍스트 미포함(목록 조회는 됨) ②외부 머신 다운로드 불가 ③assistant 가 일련번호로 답변. 결정(AskUserQuestion): 이슈1=대화 접근 권한 기준, 이슈2=앱 프록시 스트리밍.
- 근본원인(이슈1): 첨부 목록(`list_conversation_attachments`)·다운로드(`get_attachment_metadata`)는 ConversationId + `_account_can_access_conversation`(own/any) 게이트인데 LLM 주입 3경로(+pending ingest+sandbox allowlist)는 `AND AccountId = %s`(본인) → fork/이어받기 cross-account 시 목록엔 보이나 주입 0행.
- 변경: ① 주입/ingest/allowlist 를 conversation_id 우선 스코프(account 폴백)로 — `_attach_scope_clause` 헬퍼 + `pg_select_text_inline/vision_images/ingested_meta` 시그니처 `(conversation_id, account_id, ...)`. 대화 접근권은 ask 핸들러(owner 게이트 9338)가 이미 보장 → IDOR 안전망(타 대화 첨부 주입 차단) ConversationId 로 유지. ② 신규 `GET /api/attachments/{id}/download` web 프록시(권한 동형·pending 차단·octet-stream+`Content-Disposition: attachment`+nosniff·ascii_fallback 제어문자 strip) — MinIO presigned 내부호스트(`minio:9000`) 회피. app.js 다운로드 2지점 프록시 경로(same-origin 쿠키). ③ 첨부 포맷 파일명 우선 + 지칭 지침.
- Verification: test_task0284_attachment_access.py 9 + test_attachment_idor.py +4 + make test 컨테이너 전체 회귀 0 + py_compile + node --check. 적대 보안 리뷰 REV-20260616-0291 SHIP-WITH-FIXES(BLOCKER/MAJOR 0, MINOR CRLF strip 흡수, H1 cross-account refuted).
- Files: feature-0003 src/app.py, src/static/app.js, src/static/index.html, src/modules/attachment_pg_mirror.py, tests/test_task0284_attachment_access.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md; feature-0002 src/agent_core.py, tests/test_attachment_idor.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 스코프를 AccountId 로 되돌림(주입 불일치 재발) / 다운로드 라우트 제거(외부 다운로드 불가) / 포맷 복원.
- Deploy: web 재빌드 + ask-worker 재빌드(agent_core baked). 캐시버스터 `?v=20260616-task0284-attachment-access`.

## CHG-20260616-0299
- Date: 2026-06-16 (TASK-0288, **Critical §12.3** — 권한 회수 미반영 RBAC 결함 4종 + '제품' 권한 2축 분리).
- Scope: feature-0003-agent-web-ui(app.py 권한 카탈로그·엔드포인트 게이트·seed catchup·동적권한 그룹 마이그레이션, admin.js 탭 게이팅·권한 편집기 그룹/종속성·datasource 버튼, admin.html 캐시버스터). 데이터 스키마(WebPermissions row 추가만)·기존 엔드포인트 응답 shape·SSRF 가드·audit 백엔드 무변경.
- 사용자 보고/결정: 권한 회수해도 UI/데이터 접근 가능(관리콘솔 탭 전노출 / 제품 조회 / 데이터소스 항상 노출 / 감사로그). 결정: datasource read/manage 2단, 제품 작업화면사용↔관리콘솔구성 2축 + read/manage 쪼개기.
- 근본원인: ① admin.js 가 audits/usage/archives 3개 탭만 게이팅(나머지 console.access 만으로 항상 노출). ③ `GET /api/admin/products` 가 console.access 만 검사. ④ datasource 전용 권한이 카탈로그에 부재(console.access/console.manage 만으로 게이팅). (② audit 백엔드 `.own` 스코프는 정상 — 회수 미반영 아님.)
- 변경: (카탈로그) datasource.read/manage(group=datasource)·product.read(group=product) 신설, product.access.* group→product_access(신규+마이그). (게이트) datasource GET=read|manage·databases=read|manage·test=manage·CRUD=manage, product GET 4종=read|manage. (catchup) admin 역할 datasource.read/manage·product.read backfill. (프론트) applyAdminTabVisibility 전탭 게이팅+그룹라벨/구분선 숨김+활성탭 fallback, 권한편집기 그룹 재배선(datasource·product 관리권 section / product_access 운영권 section)+종속성+동적카드 재타겟, datasource 탭 버튼 datasource.manage. superset 의미=`_account_has_any_permission(read,manage)`.
- Verification: jsdom verify_admin_tab_gating.mjs 34 PASS + make test 컨테이너 전체 회귀 0(영향 테스트 4개 신규 계약 갱신) + node --check + py ast.parse. 적대 보안 리뷰 REV-20260616-0299 SHIP(7항목 코드대조; MINOR 2+NIT 1, 흡수 가능분 흡수).
- Files: feature-0003 src/app.py, src/static/admin.js, src/static/admin.html, tests/{test_datasource_delete,test_db_insights,test_insight_coverage_endpoint,test_permission_dependency_map}.py, tests/verify_admin_tab_gating.mjs, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 신규 권한 게이트 제거 시 결함 재발(권한 없이 노출). 동적권한 group 마이그레이션은 enforce 무관(UI 메타) — 롤백 불필요. catchup 제거 시 기존 admin lockout 위험(제거 금지).
- Deploy: web 재빌드 1 이미지(app.js/admin.html baked + app.py). 캐시버스터 `?v=20260616-task0288-rbac-gating`. deploy_scope: included.

## CHG-20260616-0302
- TASK-0289 — 대화 수행시간 정직 표시 + 내부 동작 투명화 + 즉각 반응 + 큐 병목 완화 (Major §12.3).
- 보고: assistant 대화 요청 시 ①내부 동작(단계별 DB동작 외) 미표현 ②실측 45초인데 화면 25초(내부 동작 집계 숨김) → 낮은 신뢰감·"느리다" 체감. 투명 공개 + 즉각 반응(스트리밍 검토) + 병목 확인 요청.
- 근본원인: 표시 `duration_ms` 가 `agent_core run_start`(초기화 이후) 기준이라 LLM 루프(≈25s)만 집계 — 큐 대기·웹 처리·DB 연결·grounding/prompt(≈20s) 제외. step 은 tool(DB 동작)만 기록.
- 변경(frontend, feature-0003): app.js `formatDurationBreakdown`(대기/준비/추론, 250ms 미만 생략) + 완료 메시지에 헤드라인 total + 인라인 보조 + `title` tooltip(`.message-meta-duration.has-breakdown`); `buildStepDetailEl` 가 `action==='activity'` step 을 `.step-detail-activity` muted + "내부 동작" 배지로 구분; `pollProgress` 처리 중 항상 `PROGRESS_POLL_ACTIVE_MS`(첫 동작 빠른 표면화). styles.css `.message-meta-breakdown`/`.step-detail-activity`/`.step-activity-badge`/`.has-breakdown`. (백엔드 P1/P2/P4 는 feature-0002 CHG-20260616-0302.)
- Verification: verify_runtime_transparency.mjs 16(jsdom) + node --check app.js + CSS brace. 적대 코드리뷰 REV-20260616-0302 SHIP(BLOCKER 0).
- Files: feature-0003 src/static/app.js, src/static/styles.css, tests/verify_runtime_transparency.mjs, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md; (백엔드: feature-0002 src/agent_core.py·modules/{ask,ask_jobs,config}.py).
- Rollback: 표시값을 inference-only 로 되돌림(숫자 축소 재발) / activity step 미emit / 폴링 cadence 복원.
- Deploy: web 재빌드(정적자산) + ask-worker 재빌드(agent_core baked). 캐시버스터 `?v=20260616-task0289-runtime-transparency`.

## CHG-20260616-0303
- Date: 2026-06-16 (TASK-0292, **Minor §12.3** — 관리 콘솔 좌측 사이드패널 수직 스크롤).
- Scope: feature-0003-agent-web-ui(styles.css `.admin-tabs`/`.admin-sidebar-foot`, admin.html 캐시버스터). HTML 구조·JS·백엔드·RBAC·스키마·엔드포인트 무변경.
- 사용자 보고: 화면 높이가 매우 작을 때 `관리 콘솔` 좌측 사이드패널을 조작할 수 없음(하단 탭 클릭 불가). 수직 스크롤 구성 요청.
- 근본원인: `aside.admin-sidebar`(flex column, `overflow:hidden`) 안에서 `.admin-tabs`(`flex:1`)에 `min-height:0`·`overflow-y` 부재. flex 항목 기본 `min-height:auto` 가 콘텐츠 높이 미만 축소를 막아, viewport 높이가 brand+탭+foot 합보다 작으면 `.admin-sidebar` 의 `overflow:hidden` 이 넘친 탭을 스크롤 없이 잘라냈다. 작업 화면 `.conv-list`(styles.css:500-503)는 이미 동일 idiom 보유 — admin 사이드바만 누락.
- 변경: `.admin-tabs` 에 `min-height:0; overflow-y:auto;`(작업 화면 `.conv-list` 정합) + `.admin-sidebar-foot` 에 `flex-shrink:0`(탭 스크롤 시 pending 요약 풋 하단 고정). 브랜드는 공유 `.sidebar-brand`(flex-shrink:0)로 상단 고정. 모바일(≤680, `.admin-sidebar{display:none}`)은 무영향.
- Verification: CSS brace 균형 + 정적 검증(JS 무변경 → node 무관) → 머지 → web 재배포 → PB-0008 Windows-browser(짧은 viewport: `.admin-tabs` overflow-y computed=auto·scrollHeight>clientHeight·하단 '설정' 탭 스크롤 도달).
- Files: feature-0003 src/static/styles.css, src/static/admin.html, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: `.admin-tabs` 의 `min-height:0; overflow-y:auto;` + `.admin-sidebar-foot` 의 `flex-shrink:0` 제거(짧은 화면 클리핑 재발). 캐시버스터 복원.
- Deploy: web 재빌드 1 이미지(styles.css/admin.html baked). 캐시버스터 `?v=20260616-task0292-admin-sidebar-vscroll`. deploy_scope: included.

## CHG-20260616-0304
- Date: 2026-06-16 (TASK-0292 후속 docs-only — PB-0008 evidence + 배포 기록).
- Scope: docs only (TASK/STATUS/MODIFY/REVIEW/TEST). 코드·자산 무변경 (TASK-0292 CHG-0303 에서 이미 머지·배포됨).
- 내용: TASK-0292(관리 콘솔 사이드바 수직 스크롤) PR #289(main be3a775) 머지 + web 재배포 + PB-0008 Windows-browser PASS 결과를 정본화. TEST.md §3 에 Windows-browser Run 추가(CHECK#13 충족).
- Verification: PB-0008 실측 — computed `.admin-tabs{overflow-y:auto; min-height:0px}`·`.admin-sidebar-foot{flex-shrink:0}`; 짧은 viewport(240px) tabsScrollH=572 > clientH=134(scrollable), scrollTop=438 도달, 하단 '설정' 탭 settingsReachable=true, foot 하단 고정. evidence `artifacts/pb0008-task0292/admin-sidebar-vscroll-short-vp.png`.
- Files: unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,TEST}.md, docs/STATUS.md.
- Rollback: 해당없음(docs only).
- Deploy: 해당없음(코드 무변경).

## CHG-20260616-0305
- Date: 2026-06-16 (TASK-0293, **Critical §12.3** — 감사 로그 `.own` Actor-only + 대시보드 위젯 데이터 권한 게이팅).
- Scope: feature-0003-agent-web-ui(app.py audit self filter·dashboard 위젯 카탈로그/헬퍼, docs/SECURITY.md §9.1). 스키마·엔드포인트 응답 shape·`.any` 경로·UI 레이아웃 무변경. 순수 권한 경계 강화(데이터 노출 축소).
- 사용자 보고/결정: ① 감사 `.own` 이 target=self(타인의 admin 조치)까지 노출 → Actor-only 반전. ② 대시보드 위젯 데이터가 console.access 만으로 노출 → 리소스별 권한 게이팅.
- 근본원인: ① `_audit_build_self_filter_sql` 가 `(ActorAccountId OR TargetAccountId)=self`(TASK-0073 E1 결정 B). ② `_DASHBOARD_WIDGETS` 의 accounts/products/datasources/roles/conversations 가 전부 `console.access` 로만 게이팅 — 탭(TASK-0288)은 막혀도 대시보드 집계 데이터는 누출.
- 변경: (A) self filter `ActorAccountId = :self` 단일(헬퍼 정본 — list/single/profile×2/resources facet inline 전파). (B) 위젯 권한 리소스별 교체 + `_actor_can_see_widget`(단일/리스트 OR, manage⊇read). overview catalog·`_isolate` 데이터 양쪽 동일 경계. conversations=conversation.list.any(cross-account COUNT(*) 집계).
- Verification: test_dashboard_overview.py(5케이스 갱신/신규) + test_audit_rbac.py smoke(s3/s3a 반전) + make test 컨테이너 회귀 0. 적대 리뷰 REV-20260616-0305 SHIP(8항목 코드대조; OR-Target 잔존 0, prefs 우회 불가). MINOR profile docstring 흡수.
- Files: feature-0003 src/app.py, tests/{test_dashboard_overview,test_audit_rbac}.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md; repo docs/SECURITY.md.
- Rollback: audit self filter 에 `OR TargetAccountId=:self` 복원(target 노출 재발) / 위젯 권한 console.access 복원(데이터 노출 재발).
- Deploy: web 재빌드 1 이미지(app.py baked, 프론트 무변경 — 캐시버스터 불요). deploy_scope: included.

## CHG-20260617-0306
- Date: 2026-06-17 (TASK-0294, **Critical §12.3** — 대시보드 위젯 데이터 `.own`/`.any` 세분화 스코핑).
- Scope: feature-0003-agent-web-ui(app.py 대시보드 위젯 함수 2종 + 카탈로그 + overview). 스키마·엔드포인트 응답 shape·`.any` 경로·UI 레이아웃·프론트 무변경. 위젯 데이터 출력 경계 세분화(축소).
- 사용자 보고/결정: 제한 권한(.own만) 보유자도 대시보드에서 cross-account 정보 노출 → 위젯 데이터를 보유 권한의 `.own`/`.any` 로 세분화.
- 근본원인: `_dash_widget_*` 함수가 actor/scope 인자 없이 무조건 전체 집계. audits 의 by_actor 가 타 계정 username 노출 + `audit.read.any` 게이팅으로 `.own` 보유자 self-scoped 버전 부재(all-or-nothing). conversations 도 cross-account 전체 집계.
- 변경: `_widget_data_scope` 신설 + `_dash_widget_audits`/`_dash_widget_conversations` 에 `scope`/`account_id` 인자. `.own`(=`.any` 미보유): audits=`ActorAccountId=self`(전 쿼리)+by_actor 생략, conversations=`owner_account_id=self`(전 쿼리, parameterized)+활성소유자 생략. `.any`: 기존 cross-account(byte-identical). 카탈로그 audits/conversations permission→[own, any] 리스트(가시성 own|any). fail-closed(account_id None→-1).
- Verification: test_dashboard_overview.py(scope kwargs + `.own` self-scope) + make test 컨테이너 회귀 0. 적대 리뷰 REV-20260617-0306 SHIP(SQLi 0·self-scope 완전·`.any` 무회귀 7항목). D1 fail-open 흡수.
- Files: feature-0003 src/app.py, tests/test_dashboard_overview.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 위젯 함수 scope 인자 제거(cross-account 무조건 집계 재발) / 카탈로그 permission 단일(.any) 복원.
- Deploy: web 재빌드 1 이미지(app.py baked, 프론트 무변경 — 캐시버스터 불요). deploy_scope: included.

## CHG-20260617-0307
- Date: 2026-06-17 (TASK-0300, **Critical §12.3 — 인가/RBAC privilege escalation 방지**).
- Scope: feature-0003-agent-web-ui(app.py 권한 가드 helper 3 + admin_update_account/role wiring + admin.js 권한 grid·제품카드 self-scope 필터 + admin.html 캐시버스터). 스키마·엔드포인트 응답 shape·`account.permission.override.manage`/`role.permission.manage` 게이트·RBAC 카탈로그 무변경. 권한 부여 가능 범위만 축소(actor 보유 권한 상한).
- 사용자 보고/결정: `관리 콘솔 > 계정` 에서 자기 보유 권한 초과 권한 숨김+설정 불가. 결정 ① 미보유=allow·deny 모두 불가(완전 숨김) ② 범위=계정+역할.
- 근본원인: 관리자가 본인 미보유 권한을 계정 override/역할 permission_codes 로 부여 가능(self-scope 가드 부재 = privilege escalation). 부수: override/permission_codes 전체 교체+delete-all-then-insert 라 행을 숨기면 숨긴 권한 기존값 누락→삭제(데이터 손실).
- 변경: 신규 `_actor_editable_permission_codes`/`_enforce_override_self_scope`/`_enforce_role_permission_self_scope`/`_role_grant_excess_for_actor`. 미보유 권한 설정 시 403 + 범위 밖 기존값 merge 보존. wiring 4경로: `admin_update_account`(override normalize 직후 + **역할 배정 변경 시 배정역할 권한 ⊄ actor → 403**)·`admin_update_role`(validate 직후·survivor 직전)·`admin_create_role`(role.permission.manage 게이트 직후, 신규 역할이라 current=∅). admin.js `renderPermissionGrid(opts.allowedCodes)` 미보유 행 숨김(빈 그룹/section 제거·product_access 컨테이너 보존) + 계정/역할 상세 wiring + 제품카드 필터 + **역할 드롭다운 배정불가 역할 숨김** + onChange 숨긴값 보존 + 안내문구. (역할 생성/배정 가드는 외부리뷰 MAJOR-1 흡수 — 사용자 결정 '배정도 차단'.)
- Verification: `test_perm_self_scope.py`(ast 실 helper 12 PASS) + jsdom `verify_perm_self_scope.mjs`(실 renderPermissionGrid 13 PASS) + node --check + py ast.parse. 적대 리뷰 REV-20260617-0307. 화면 정본 = PB-0008.
- Files: feature-0003 src/app.py, src/static/admin.js, src/static/admin.html, tests/test_perm_self_scope.py, tests/verify_perm_self_scope.mjs, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 두 enforce helper 호출 제거(escalation 재개방) + admin.js allowedCodes 전달 제거(전체 표시 복원). 캐시버스터 되돌림.
- Deploy: web 재빌드 1 이미지(app.py + 프론트 baked, 캐시버스터 bump). deploy_scope: included.

## CHG-20260617-0308
- Date: 2026-06-17 (TASK-0300 evidence — 라이브 403 + PB-0008 Windows-browser 검증 기록).
- Scope: docs-only(TEST.md run 기록 + REPORT.md 잔존→완료 + TASK.md 최종 체크). 코드·스키마·엔드포인트·프론트 0.
- 내용: TASK-0300(계정/역할 권한 편집 self-scope) 배포(main a9effd6, PR #313) 후 검증 증거 기록. ① 라이브 백엔드 403(실 제한계정 pgpark/usermanager): 미보유 audit.purge override allow·deny 403, 보유 account.read allow 200, admin 역할배정 403(pgpark 자격 백업→검증→복원 비파괴). ② PB-0008 실 Chrome render-injection: 미보유 권한 행 숨김·빈 그룹 제거·product_access 컨테이너 보존·account 행 computed flex·offsetParent≠null. evidence `artifacts/pb0008-task0300/perm-self-scope-hidden.png`.
- Verification: 본 기록 자체가 검증 산출물. 코드 무변경(회귀 0).
- Files: unit/feature-0003-agent-web-ui/docs/{TEST,REPORT,TASK,MODIFY,REVIEW}.md.
- Rollback: 불요(docs-only).
- Deploy: 불요(코드 무변경 — TASK-0300 코드는 이미 a9effd6 배포됨).

## CHG-20260617-0311
- Date: 2026-06-17 (TASK-0301, **Minor §12.3 — 관리 콘솔 제품 목록 항목 글꼴 크기 정합**).
- Scope: feature-0003-agent-web-ui(admin.js 2줄). 백엔드·스키마·CSS·엔드포인트·RBAC 무변경.
- 근본원인: `renderProductList()` 의 제품명 요소가 `admin-account-name`(15px, 700) 을 사용 — 계정·역할·데이터소스 목록은 `admin-list-row-name`(13px, 600). 컨테이너 클래스도 `admin-list-main`(CSS 미정의) vs `admin-list-row-main` 불일치.
- 변경: admin.js `renderProductList()` — ① 이름 요소 `div.admin-account-name` → `span.admin-list-row-name` ② 컨테이너 `admin-list-main` → `admin-list-row-main`. 2줄, frontend-only.
- Verification: node --check + 라이브 화면 비교(제품 탭 항목 글꼴 ≡ 계정·역할). 화면 정본 = PB-0008.
- Files: feature-0003 src/static/admin.js, docs/{TASK,MODIFY,REVIEW}.md.
- Rollback: 두 클래스명을 원복(`admin-account-name`, `admin-list-main`). 시각만 원복, 기능 무영향.
- Deploy: web 재빌드 1 이미지(프론트 baked). deploy_scope: included.

## CHG-20260617-0312
- Date: 2026-06-17 (TASK-0302 — 관리 콘솔 제품 일괄 삭제 미적용 + bulk staging 목록 즉시 반영).
- Scope: frontend admin.js + admin.html(cache-buster) + backend app.py(admin_delete_product 가드). 스키마 0, 신규 권한 0.
- 내용: ① **근본 수정** — `applyAllPending` 의 productMeta 루프가 `_delete` 플래그를 미처리(account/role 루프와 비대칭)해 bulk "삭제 pending"→"모두 적용" 이 빈 body·요청 0건으로 조용히 무효였음. `if (patch._delete) → DELETE /api/admin/products/{id}` 추가(단일 삭제·account/role 정합). 혼합 편집(제품 메타 수정 + 다중 삭제) 시 "마지막 수정 제품만 적용"으로 보이던 증상의 근본. ② bulkProductDelete/bulkProductSetActive/bulkAccount*/bulkRole* staging 후 `renderXList()` + 제품 행 pending 마커(`has-pending`/`is-to-delete`/dot) 신설(계정·역할 동형 — 이전엔 제품 행 마커 부재). ③ 백엔드 `admin_delete_product`: 기본 제품(IsDefault) **409** + 미존재 **404** 가드(defense-in-depth — bulk DELETE 가 서버 도달, 프론트 canTargetRow client-trust 보강; 단일 삭제도 보호).
- Why: 사용자 보고 "다중선택 변경점 pending 돼도 마지막만 적용". 전수 조사 결과 깨진 것은 제품 일괄 삭제뿐(나머지 bulk·grid·prompt·단일 삭제 정상).
- Verification: 라이브(실 running stack + 브라우저) 수정 전 제품 3개 일괄 삭제 → 0건, 수정 후 → 3건 전부 삭제. is-to-delete rows=2·pendingDots=2. 회귀(역할 일괄 비활성 2/2) 정상. node --check + py ast.parse. 외부리뷰 SHIP-WITH-FIXES(REV-20260617-0312 — MAJOR 기본제품 가드·MINOR 제품행 마커 흡수).
- Rollback: 3 파일 revert(admin.js _delete 분기·renderXList·제품 마커, admin.html cache-buster, app.py IsDefault/404 가드).
- Deploy: web 재빌드(deploy_scope: included). 라이브 재검증 = 기본 제품 삭제 409 + 일괄 삭제 N건 전부 + pending 마커 + PB-0008.

## CHG-20260618T022150-ai-claude-ds-acc-collapsible
- Date: 2026-06-18 (TASK-20260618T022150-ai-claude-ds-acc-collapsible — 관리 콘솔 > 제품: 펼쳐진 데이터소스의 접근 가능 DB 목록 접기 가능하게).
- Scope: frontend-only — feature-0003 `src/static/admin.js`(제품 상세 datasource accordion) + `src/static/admin.html`(cache-buster). 백엔드·스키마·CSS·엔드포인트·RBAC·신규 권한 0.
- 근본원인: "데이터 소스 & 접근 가능 데이터베이스" accordion(TASK-0238, `_renderDsAccordion`)의 행 머리(`.ds-acc-head`) 클릭이 `_switchEditDs(key)` 만 호출하는데, `_switchEditDs` 는 `nk === _editDsKey` 이면 early-return(admin.js:6526~) → 이미 편집 대상인 행을 다시 눌러도 무반응 = 접기 불가. 데이터소스가 하나면 그 하나가 항상 편집 대상이라 접근 DB 편집기(`.ds-acc-body`)가 영구 펼침 → 하단 UI(데이터소스 추가·제품 프롬프트·삭제)가 멀어짐.
- 변경(admin.js): ① 렌더 함수 클로저에 `let _dsBodyCollapsed = false`(편집 대상 body 접힘 여부, 기본 펼침=기존 동작 보존) 신설. ② `_renderDsAccordion` 행 렌더에서 `isActive` → `isEditTarget`(키 일치) + `isExpanded`(= isEditTarget && !_dsBodyCollapsed) 분리 — is-active 클래스·`aria-expanded`·caret(▾/▸)·`.ds-acc-body` 생성·head `title` 모두 `isExpanded` 기준. ③ head 클릭 핸들러: 이미 편집 대상이면 `_dsBodyCollapsed` 토글 + `_renderDsAccordion()`, 아니면 `_switchEditDs(key)` 전환. ④ `_switchEditDs`·`_afterBindChange`(편집 대상 제거 분기)에서 `_dsBodyCollapsed=false` 리셋(다른 datasource 전환/이동 시 자동 펼침). admin.html cache-buster `?v=20260618-ds-acc-collapsible`.
- Why: 사용자 보고 — 데이터소스가 하나일 때 DB 목록이 접히지 않아 하단 UI 접근이 번거로움. 접기 토글 신설로 해소. 기본 펼침 유지로 멀티 datasource 기존 흐름 무회귀.
- Verification: `node -c admin.js` PASS + `tests/verify_ds_accordion_collapse.mjs` **19/19 PASS**(jsdom — 초기 펼침 회귀 없음·토글1 접힘[body 제거·is-active 해제·aria-expanded false·caret ▸·행 유지·하단 '+ 데이터소스 추가' 도달]·토글2 재펼침). 화면 정본 = PB-0008 Windows-browser(배포 후).
- Rollback: 2 파일 revert(admin.js `_dsBodyCollapsed`/`isExpanded`/토글 핸들러/리셋, admin.html cache-buster). 동작만 원복(접기 불가 상태로), 데이터·기능 무영향.
- Deploy: web 재빌드 1 이미지(프론트 baked). deploy_scope: included.

## CHG-20260618T024209-ai-claude-ds-acc-collapsible-evidence
- Date: 2026-06-18 (TASK-20260618T022150-ai-claude-ds-acc-collapsible — PB-0008 Windows-browser evidence 기록, docs-only).
- Scope: docs-only — feature-0003 `docs/{TASK,REPORT,MODIFY,REVIEW,TEST}.md`. 코드·스키마·배포 0(증거 기록).
- 내용: TASK-20260618T022150(데이터소스 DB 목록 접기 토글)의 배포 후 PB-0008 Windows-browser 실측 결과를 TEST.md §4 에 'Environment: Windows-browser' Run 으로 기록(CHECK#13 충족), TASK/REPORT 의 잔여 → 완료 전환. 실측: 배포본 main `9069518`(PR #323 merge), 실 Chrome/149 via win-browser relay, 단일 datasource 제품 KR(`mysql-local`) 에서 초기 펼침→머리 클릭 접힘(body 제거·행 유지·caret ▸·aria false)→'+ 데이터소스 추가' 912→685px viewport 내 진입→재펼침 토글 복원 PASS. evidence `artifacts/pb0008-ds-acc-collapsible/ds-acc-collapsed.png`.
- Why: AGENTS.md §15.4.1 PB-0008 — 웹/UI 변경 완료 검증은 실 Windows 브라우저 정본. 코드 PR(#323) 머지·배포 후 별도 evidence cycle 로 기록(two-PR 패턴).
- Verification: 본 변경은 docs-only(코드 0). 검증 정본은 본 cycle 이 기록하는 PB-0008 결과 자체.
- Rollback: docs revert(증거 기록 제거). 코드·배포 무영향.
- Deploy: 없음(docs-only).

## CHG-20260618T025220-ai-claude-ds-acc-collapsed-default
- Date: 2026-06-18 (TASK-20260618T025220-ai-claude-ds-acc-collapsed-default — 제품 선택 시 접근 가능 DB 목록 기본 접힘).
- Scope: frontend-only — feature-0003 `src/static/admin.js`(1줄 + 주석) + `src/static/admin.html`(cache-buster) + `tests/verify_ds_accordion_collapse.mjs`(단언 반전). 백엔드·스키마·CSS·엔드포인트·RBAC 0.
- 내용: TASK-20260618T022150 이 도입한 datasource accordion 접힘 상태 `_dsBodyCollapsed` 의 초기값을 `false`(펼침) → `true`(접힘)로 변경. 제품을 선택해 `renderProductDetail` 이 상세를 열면 편집 대상 datasource 의 DB 편집기(`.ds-acc-body`)가 접힌 채 시작 → 하단 UI(데이터소스 추가·제품 프롬프트·삭제) 바로 접근. 토글 메커니즘(머리 클릭 펼침/접힘)·전환 시 자동 펼침(`_switchEditDs`/`_afterBindChange` 의 `false` 리셋)은 불변. 주석 갱신, admin.html cache-buster `?v=20260618-ds-acc-collapsed-default`.
- Why: 사용자 요청 — 기본적으로 제품 선택 시 데이터베이스 목록이 접혀 있도록. REQ-20260618-0314(접기 토글)의 기본값 후속.
- Verification: `node -c admin.js` PASS + `tests/verify_ds_accordion_collapse.mjs` **19/19 PASS**(초기 접힘[body 미생성·is-active 아님·aria false·caret ▸·행 유지·하단 `.ds-acc-add-btn` 도달]·토글1 펼침·토글2 접힘). 화면 정본 = PB-0008 Windows-browser(배포 후).
- Rollback: 초기값 `true`→`false` 복원(1줄) + cache-buster·test 단언 원복. 동작만 기본 펼침으로, 데이터·기능 무영향.
- Deploy: web 재빌드 1 이미지(프론트 baked). deploy_scope: included.

## CHG-20260618T025848-ai-claude-ds-acc-collapsed-default-evidence
- Date: 2026-06-18 (TASK-20260618T025220-ai-claude-ds-acc-collapsed-default — PB-0008 Windows-browser evidence 기록, docs-only).
- Scope: docs-only — feature-0003 `docs/{TASK,REPORT,MODIFY,REVIEW,TEST}.md`. 코드·스키마·배포 0.
- 내용: 제품 선택 시 DB 목록 기본 접힘(TASK-...T025220)의 배포 후 PB-0008 Windows-browser 실측 결과를 TEST.md §4 'Environment: Windows-browser' Run 으로 기록(CHECK#13 충족), TASK/REPORT 잔여→완료. 실측: 배포본 main `1ad1519`(PR #328), 실 Chrome/149, 단일 datasource 제품 KR(`mysql-local`) 선택 직후 클릭 없이 DB 목록 접힘(body 미생성·caret ▸·aria false·하단 버튼 도달) + 머리 클릭 토글 펼침/접힘 무회귀. evidence `artifacts/pb0008-ds-acc-collapsed-default/default-collapsed-on-select.png`.
- Why: AGENTS.md §15.4.1 PB-0008 — 웹/UI 완료 검증 정본. 코드 PR(#328) 머지·배포 후 별도 evidence cycle(two-PR 패턴).
- Verification: docs-only. 검증 정본 = 본 cycle 이 기록하는 PB-0008.
- Rollback: docs revert. 코드·배포 무영향.
- Deploy: 없음(docs-only).
## CHG-20260618T025755-ai-claude-dbpicker-search-regex
- Date: 2026-06-18 (TASK-20260618T025755-ai-claude-dbpicker-search-regex — '+ 데이터베이스 추가' picker 검색 필터 + 정규식 일괄 선택).
- Scope: frontend-only — feature-0003 `src/static/admin.js`(모듈 helper 4종 + buildPicker toolbar + 클로저 보존 변수) + `src/static/styles.css`(toolbar/검색/정규식/하이라이트/결과없음) + `src/static/admin.html`·`index.html`(cache-buster) + `tests/verify_dbpicker_search_regex.mjs`(신규). 백엔드·스키마·엔드포인트·RBAC·데이터 0.
- 내용: 관리 콘솔 제품 상세의 '+ 데이터베이스 추가' 드롭다운(`buildPicker`)에 후보 DB ≥ 6 일 때 sticky toolbar 추가 — ① 이름 검색 필터(부분일치·대소문자 무시, `.hidden` 토글, 결과없음 안내) ② 정규식 일괄 선택(라이브 `N개 일치` 카운트 + `.is-regex-match` 하이라이트 미리보기, "일치 선택" 버튼/Enter 로 additive push, 검증 통과분만) ③ "선택됨 N개" 요약. 입력값은 렌더 클로저(`_dbPickerQuery`/`_dbPickerRegex`)에 보존. 순수/DOM helper 4종 분리(`dbPickerFilterNames`/`dbPickerRegexMatches`/`applyDbPickerSearch`/`applyDbPickerRegexHighlight`)로 jsdom 검증.
- Why: 사용자 요청 — 사내 데이터소스 DB 추가/삭제가 잦아 제품 DB 구성 변경이 번거로움. 검색+정규식 선택으로 다수 DB 를 빠르게 allowlist 에 반영.
- Verification: `node --check admin.js` PASS + `tests/verify_dbpicker_search_regex.mjs` **33/33 PASS**. 선택 쓰기는 기존 pending→모두 적용 경로 + 기존 schema_name 검증 그대로(보안 경계·쓰기 계약 불변). 화면 정본 = PB-0008 Windows-browser(배포 후).
- Rollback: helper 4종 + buildPicker toolbar 블록 + 클로저 변수 2개 + CSS 블록 제거, cache-buster·test revert. 후보 목록 체크박스만 남는 기존 동작으로 복원(데이터·기능 무영향).
- Deploy: web 재빌드 1 이미지(프론트 baked). deploy_scope: included.

## CHG-20260618T025755-ai-claude-dbpicker-search-regex-evidence
- Date: 2026-06-18 (TASK-20260618T025755 PB-0008 Windows-browser evidence — '+ 데이터베이스 추가' 검색 필터 + 정규식 일괄 선택).
- Scope: docs-only — feature-0003 `docs/TEST.md`(PB-0008 Run 기록) + `docs/TASK.md`(마감 체크) + `docs/MODIFY.md`·`docs/REVIEW.md`(본 evidence). 코드·배포·스키마·RBAC 0.
- 내용: 배포(main 14c3280, web 재빌드)된 '+ 데이터베이스 추가' 검색 필터 + 정규식 일괄 선택을 실제 Windows Chrome(win-browser relay)으로 PB-0008 검증한 결과를 TEST.md §3 에 'Environment: Windows-browser' Run 으로 기록. render-injection 기법(실 배포 helper 4종 + styles.css computed) — sticky toolbar·검색 3/8·결과없음·정규식 count 3·하이라이트 primary@12%·hidden display:none(글로벌 .hidden !important)·additive 전부 PASS. 시각 evidence `artifacts/pb0008-dbpicker-search-regex/picker-search-regex.png`.
- Why: AGENTS.md §15.4.1 CHECK#13 — 웹/UI 변경은 실제 Windows 브라우저 검증 기록 필요.
- Verification: 본 변경은 docs-only(코드 0). 검증 정본은 본 cycle 이 기록하는 PB-0008 결과 자체.
- Rollback: docs revert(증거 기록 제거). 코드·배포 무영향.
- Deploy: 없음(docs-only).

## CHG-20260618-0317
- Date: 2026-06-18 (TASK-0303 — 역할/계정 '제품 사용(product_access)' 다중선택 무효 + 그룹 카운트 "0/0").
- Scope: frontend admin.js + admin.html(cache-buster) + tests/verify_product_access_multiselect.mjs. 백엔드·스키마·RBAC·신규권한 0.
- 내용: ① 제품 카드 토글이 렌더 시점 스냅샷(role.permission_codes/account.permission_overrides)을 읽어 매 토글이 전체 교체→마지막 1개만 남던 다중선택 무효 수정 — `onToggle`/`onChange` 가 라이브 `mergedRole`/`mergedAccount`(pending 오버레이) 읽기로 전환(단건만 가감, 누적). ② 역할 메인 grid `onChange` 의 `existingDynamic`/`preservedHidden` 도 라이브 `mergedRole` 읽기(정적↔제품 상호 클로버 방지, TASK-0300 self-scope hidden 보존 정합). ③ product_access 그룹 배지 "0/0" — 카드는 grid 렌더(`_updateCheckboxGroupSummary` 1차) *이후* 임베드돼 0/0 고정이던 것을, 임베드 직후 재집계(역할 N/M·계정 허용/거부/상속) + 부여 시 그룹 펼침 + 토글 시 배지 라이브 갱신.
- Why: 사용자 보고 — 역할 제품별 접근 다중선택 미작동 + "제품 사용" 권한 항상 "0/0".
- Verification: `verify_product_access_multiselect.mjs` 6 PASS(실 추출 함수 — 역할·계정 다중선택 누적·OLD 버그 대조군·정적↔제품 클로버 방지·카운트 0/0→3/16) + node --check. 외부리뷰 **SHIP**(REV-20260618-0317 — 6항목 전부 refuted, 권한손실·self-scope회귀·escalation 0).
- Rollback: admin.js 5개 편집 + admin.html cache-buster revert.
- Deploy: web 재빌드(deploy_scope: included). 라이브 재검증 = 역할 제품 3개 토글→3개 staged·배지 N/M·적용 후 영속 + PB-0008.

## CHG-20260618T044318-ai-claude-db-rule-autosync
- Date: 2026-06-18 (TASK-20260618T044318 — 제품 DB allowlist 정규식 규칙 자동 동기화, **Critical §12.3**).
- Scope: feature-0003 `src/app.py`(스키마 helper + reconcile/검증/매칭 helper + 5 엔드포인트 + 수동 PUT B4 수정 + 백그라운드 task + probe 등록 + `_list_product_databases` source) + `src/static/admin.js`(규칙 에디터·pending·배지·picker 비활성·PUT body 필터) + `src/static/styles.css`(.cov-db-rule*) + `admin.html`/`index.html`(cache-buster) + `tests/verify_db_rule_logic.py`·`verify_db_rule_ui.mjs`(신규) + `docs/PLAN-db-rule-autosync.md`.
- 내용: (제품×데이터소스) 정규식 규칙을 저장하면 데이터소스 DB 변화 시 일치 DB 를 allowlist 에 안전 하이브리드로 반영 — cap 이하+권한 충족=자동(Source='rule'), 초과·권한보류=pending(1클릭 승인). 트리거=규칙 저장·관리자 규칙 섹션 열람(lazy)·백그라운드 주기(300s). allowlist=에이전트 접근 경계라 outside-voice 2-pass + BLOCKER 전부 반영(B1 hybrid/cap-withhold·B2 ReDoS 강화·B3 생성자 귀속 감사·B4 수동 PUT rule 보존·B5 엔진별 case-fold·M2 제외 union·M3 creator 활성+권한 재검증·M4 add-only no-op·M5 SortOrder 말미·M6 product.manage 쓰기 게이트).
- Why: 사용자 요청 — 정규식 선택을 1회 구성으로 데이터소스 변화 자동 추종(잦은 DB 구성 변경 무인 대응).
- Verification: `ast.parse(app.py)` + `node --check admin.js` + `verify_db_rule_logic.py` 25/25 + `verify_db_rule_ui.mjs` 17/17 + ReDoS catastrophic 0.000s 차단 실측. outside-voice 구현 재리뷰 SHIP-WITH-FIXES(BLOCKER ReDoS 흡수). 화면 정본 = PB-0008(배포 후).
- Rollback: 신규 helper/엔드포인트/백그라운드/스키마 helper + admin.js 규칙블록 + CSS 제거, 수동 PUT B4 분기 원복(Source 무시 전체교체), cache-buster·test revert. 스키마 테이블/컬럼은 비파괴(잔존 무해). reconcile 미동작 시 기존 수동 allowlist 그대로.
- Deploy: web 재빌드 1 이미지(백엔드+프론트 baked). deploy_scope: included.


## CHG-20260618T052403-ai-claude-db-rule-autosync-audit-fix
- Date: 2026-06-18 (TASK-20260618T044318 후속 — PB-0008 적발 audit action 미등록 버그 수정).
- Scope: feature-0003 `src/app.py`(build_audit_change_json 에 db_rule 5 action 등록) + `tests/verify_db_rule_logic.py`(회귀 가드).
- 내용: 규칙 PUT/DELETE 가 `_audit_admin_mutation` → `build_audit_change_json` 경로인데, 신규 action(`admin.product.db_rule.set/delete`, `db.autoadd/staged`, `db_rule.approve`)이 빌더에 미등록 → `unknown audit action` ValueError → 500/rollback 으로 규칙 저장 자체가 실패(PB-0008 라이브 적발). 빌더에 5 action handler 추가(target_product_id/datasource_key/before/after 통과).
- Why: PB-0008 Windows-browser 실 저장 시 500 발견 — 단위/jsdom 은 audit 레이어 미경유라 못 잡음(라이브 게이트의 가치).
- Verification: ast.parse + verify_db_rule_logic.py 30/30(audit 등록 가드 5건 포함) + 재배포 후 라이브 PUT/GET/DELETE round-trip.
- Rollback: 빌더 5 action 블록 제거.
- Deploy: web 재빌드. deploy_scope: included.
## CHG-20260619T014034-ai-claude-llm-restriction-notice
- TASK-20260619T014034 — LLM provider 외부요인 제한 명시 표면화 (web 면, Major §12.3). agent-core 분류·영속·probe 는 feature-0002 CHG-20260619-0319.
- 변경:
  - `src/app.py`: `_read_llm_provider_status`(modules.llm_provider_health.read_provider_health graceful) + `GET /api/llm/health`(인증 게이트 — 미인증은 probe 없이 read만; force=1=TTL 무시) + `/api/session` payload·`_build_ask_status_snapshot` 에 `llm_provider_status` 필드.
  - `src/static/index.html`: 컴포저 배너+'다시 확인' / footer 상태점(툴팁) / 실행단계 패널 노트 마크업 + 캐시버스터 bump(`?v=20260619-llm-restriction`).
  - `src/static/styles.css`: `.llm-restriction-banner`·`.llm-status-dot(.is-restricted)`·`.llm-restriction-notice`·`.llm-restriction-panel-note` + footer 상태점 노출 시 유지하는 `:has(.llm-status-dot.hidden)` 조정.
  - `src/static/app.js`: `applyLlmProviderStatus`/`renderLlmRestrictionInlineNotice`/`pollLlmHealth`/`startLlmHealthPolling` + `/api/session`·`/api/ask_result` 소비 wiring(restricted+error→인라인 notice). textContent(XSS-safe)·DOM 누락 graceful·인라인 dedup·타이머 단일 가드.
- Verification: `tests/verify_llm_restriction_surface.mjs` 35(정적+jsdom 4-surface) + node --check + py_compile. 적대 코드리뷰 REV-20260619T014034-ai-claude-llm-restriction-notice.
- Files: src/app.py, src/static/{index.html,styles.css,app.js}, tests/verify_llm_restriction_surface.mjs(new), docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 엔드포인트/필드 제거 + UI surface 제거 + 캐시버스터 revert. backend 미가용 시 read→unknown(배너 미표시) graceful.
- Deploy: web 재빌드(app.py·static baked) + ask-worker(feature-0002) + 마이그 0011. deploy_scope: included.

## CHG-20260618T061703-ai-claude-db-rule-multi
- Date: 2026-06-18 (TASK-20260618T061703 — DB allowlist 정규식 규칙 다중 + 종속 UI). TASK-20260618T044318 확장.
- Scope: feature-0003 `src/app.py`(UNIQUE 제거+SortOrder 마이그레이션·probe·fast-path catchup·다중규칙 함수/엔드포인트·INSERT IGNORE·rule_id 직렬화) + `src/static/admin.js`(규칙 카드/폼/추가·DB 중첩·redrawChips manual 분리) + `styles.css`(.cov-db-rule-card*/-dblist*) + admin.html·index.html(cache-buster) + tests(logic 30/ui 18) + docs.
- 내용: (product,ds)당 규칙 1→N. 각 규칙 카드에 그 규칙이 추가한 DB 를 중첩 표시(종속 시각화). reconcile 은 규칙별 순차(cross-rule dedup, 먼저 매칭한 규칙이 RuleId 소유), 삭제는 RuleId 행만 strip. 안전 모델(cap/pending/ReDoS/manual 우선/감사/creator 재검증) 규칙별 유지. outside-voice 재리뷰 MAJOR#1(INSERT IGNORE)·#2(fast-path catchup) 반영.
- Why: 사용자 요청 — 여러 규칙 + DB 종속 UI.
- Verification: ast+node + verify_db_rule_logic.py 30/30 + verify_db_rule_ui.mjs 18/18. 화면 정본=PB-0008.
- Rollback: 다중규칙 함수/엔드포인트/UI 복원 + UNIQUE 재추가(단, 기존 다중 규칙 행 있으면 충돌 — 운영 주의). 비파괴 스키마(SortOrder 잔존 무해).
- Deploy: web 재빌드. deploy_scope: included.

## CHG-20260619T012028-ai-claude-share-link-expiry
- Date: 2026-06-19 (TASK-20260619T012028-share-link-expiry — 대화 공유 링크 시간 기반 만료, 설정 가능. SECURITY.md §7.2 TODO 구현). 사용자 보안 보강 6종 중 ①.
- Scope: feature-0003 `src/app.py`(스키마 헬퍼 `_ensure_web_share_links_expiry_column`+양 경로 호출·`_share_load_active` SELECT·`_share_row_expired` 헬퍼·`_SHARE_EXPIRY_MAX_SECONDS`·create 검증/INSERT/응답/audit·list IsExpired·public view/fork 410 집행·view 응답 expires_at·audit builder share.create) + `src/static/app.js`(promptShareExpiry 모달·createConversationShare·공유관리 만료 배지) + `share.js`(만료 렌더+410 body.error 구분) + `share.html`(#shareExpiry) + `styles.css`(.is-expired/.share-expiry-*) + index.html/share.html(cache-buster) + `tests/test_task20260619_share_expiry.py`(신규 12) + docs.
- 내용: `ExpiresAt DATETIME NULL`(기본 NULL=무기한, 기존 동작 무회귀·명시 revoke 유지). 생성 시 `expires_in_seconds`(무기한/1일/7일/30일, 상한 365일) → `DATE_ADD(NOW(), INTERVAL %s SECOND)`. anonymous view/fork 시 `ExpiresAt <= NOW()` → 410(취소 410 과 구분된 "만료되었습니다" 메시지). 만료 판정은 **전부 DB 시계(NOW()/DATE_ADD)** — web↔DB clock skew 차단. view 의 ViewCount UPDATE 도 만료 predicate 포함(만료뷰 카운트 인플레 차단). 410 이 대화 본문 로드보다 선행(누출 0).
- Why: 사용자 요청 + SECURITY.md §7.2 외부 배포 전 보완 TODO(시간 기반 만료) 충족. 공유 링크의 무기한 노출 위험 완화.
- Verification: test_task20260619_share_expiry.py 12/12 + make test 전체 회귀 0(사전존재 product-delete 2건 제외) + py_compile + node --check(app.js/share.js) + CSS brace 1372=1372. outside-voice 적대 보안 리뷰 SHIP(9 probe refute, BLOCKER/MAJOR 0). 화면 정본=PB-0008(배포 후).
- Rollback: 스키마 헬퍼/엔드포인트/UI 변경 복원. ExpiresAt 컬럼은 비파괴(잔존 무해, NULL=무기한이라 enforcement 영향 0). cache-buster 되돌림.
- Deploy: web 재빌드. (ask/insight-worker 무관 — 공유는 web 전용.)

## CHG-20260619T021356-ai-claude-login-attempt-limit
- Date: 2026-06-19 (TASK-20260619T021356-login-attempt-limit — 잘못된 로그인 시도 제한). 사용자 보안 보강 6종 중 ②.
- Scope: feature-0003 `src/app.py`(config 4 env·`_ensure_login_lockout_schema`+양 경로·`_fetch_account_rows` is_locked DB컬럼·`_serialize_account` lock 노출·IP throttle 3헬퍼+메모리 sweep·계정잠금 2헬퍼·auth_login 재작성·`admin_account_unlock` 엔드포인트·password-reset 잠금해제·build_audit_change_json auth.lockout/auth.unlock) + `src/static/admin.js`(잠금 배지+해제 버튼+triggerAccountUnlockFlow) + `styles.css`(.status-chip.is-locked) + admin.html/index.html(cache-buster) + `tests/test_login_attempt_limit.py`(신규 11) + docs.
- 내용: 계정 잠금(DB 영속, cross-worker) + IP throttle(in-process, per-worker) 심층방어. 보수적 프로파일(계정 5회→15분 자동해제, IP 20회/600초). 모든 임계 env. 잠금 판정 전부 DB 시계(NOW()/DATE_ADD)로 clock skew 차단. 로그인: IP throttle→미존재(일반 401)→is_locked(429)→실패누적/잠금시 audit→성공시 초기화. 관리자 잠금 해제(비번 변경 없이) + password-reset 동반 해제.
- Why: 사용자 요청 — 무차별 대입(brute-force) 방어. 기존 로그인엔 실패 제한 전무.
- Verification: test_login_attempt_limit.py 11/11(IP throttle 실 동작 포함) + make test 회귀 0(사전존재 product-delete 2건 제외) + py_compile + node --check + CSS brace 1373. outside-voice 적대 보안 리뷰 SHIP-WITH-FIXES(BLOCKER 0, MINOR/NIT 흡수, MAJOR soft-threshold accept+문서화).
- Rollback: 엔드포인트/헬퍼/login 변경 복원. lockout 컬럼 비파괴(잔존 무해, DEFAULT 0/NULL=enforcement 영향 0). cache-buster 되돌림.
- Deploy: web 재빌드. (ask/insight-worker 무관 — 인증은 web 전용.)

## CHG-20260619T022449-ai-claude-release-note-llm-restriction
- TASK-20260619T022449 — 릴리즈 노트에 LLM 사용 제한 안내 항목 추가 (content-only, Minor §12.3). 사용자 정책(2026-06-19): /_template:entry 완료 시 릴리즈 노트 명시.
- 변경: `src/static/release-notes-data.js` `releases[]` 맨 앞 2026-06-19 블록 + `generated` 갱신(1 item: type=new/area=work). index.html/admin.html `release-notes-data.js?v=20260619-llm-restriction`. 렌더러(release-notes.js)·로직 불변 — 순수 데이터/콘텐츠.
- 문체 정합: 기존 노트(2026-06-12~18) 양식·문체 파악 후 동일하게(사용자 결과 중심 title·존댓말 detail·내부동작 비노출 AC-0579 — "외부 요인" 추상화).
- Verification: `verify_release_notes.mjs` 34/34 + node --check.
- Files: src/static/release-notes-data.js, src/static/{index,admin}.html, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 2026-06-19 블록 제거 + 캐시버스터 되돌림.
- Deploy: web 재빌드(static baked). ask/insight-worker 무관.

## CHG-20260619T023922-ai-claude-audit-tamper-evidence
- Date: 2026-06-19 (TASK-20260619T023922-audit-tamper-evidence — 감사 기록 변조방지 해시 체인). 사용자 보안 보강 6종 중 ③.
- Scope: feature-0003 `src/app.py`(`_ensure_web_audit_chain_schema`+양 경로·`_audit_canonical_string`/`_audit_compute_hash`/`_AUDIT_CHAIN_SELECT`·`_seal_audit_chain`(GET_LOCK·Id ASC·`EventHash IS NULL` 가드)·`_seal_audit_chain_drain`·record_audit_event fresh-conn 봉인 훅·`_start_audit_seal_loop` 로그 앵커·`verify_audit_chain` 엔드포인트·purge checkpoint·build 무관) + `src/static/admin.js`(무결성 검증 버튼+triggerAuditChainVerify)+`admin.html`(버튼)+`styles.css`(.admin-audit-verify-result)+admin/index.html(cache-buster) + `tests/test_audit_tamper_evidence.py`(신규 11) + docs(SECURITY.md §13).
- 내용: 감사행마다 EventHash=SHA256(PrevHash|정규화행) 해시 체인 → 변조 탐지. 봉인은 GET_LOCK 직렬 fresh-conn(RR fork 방지)+Id ASC 일괄+가드. verify 엔드포인트가 walk·재계산. purge 는 경계 checkpoint 재앵커. **위협모델 정직화**: in-DB 체인은 비-체인-인지 변조/손상/부분권한 공격 탐지용; full DB-write 공격자는 재계산/truncation 가능 → 백그라운드 sealer 가 head 해시를 off-DB 로그 앵커(외부 WORM/SIEM 대조).
- Why: 사용자 요청 — 감사 무결성. 기존 audit 는 변조 탐지 수단 0.
- Verification: test 11/11(해시 tamper-detection 실 동작) + make test 회귀 0 + py_compile + node --check. outside-voice SHIP-WITH-FIXES(MAJOR 3 흡수).
- Rollback: 엔드포인트/헬퍼/훅/UI 복원. EventHash/PrevHash 컬럼·Checkpoint 테이블 비파괴(잔존 무해). cache-buster 되돌림.
- Deploy: web 재빌드.

## CHG-20260619T030500-ai-claude-llm-usage-quota
- Date: 2026-06-19 (TASK-20260619T030500-llm-usage-quota — LLM 사용량 한도). 사용자 보안 보강 6종 중 ④.
- Scope: feature-0003 `src/app.py`(config LLM_QUOTA_ENFORCE·`_ensure_llm_quota_schema`+양 경로·`_account_effective_quota`/`_account_period_usage_tokens`/`_check_account_token_quota`/`_quota_upsert`/`_quota_parse_limit`·/api/ask 게이트·admin 3 엔드포인트·audit quota.role/account.update) + `src/static/admin.js`(loadQuotas)+`admin.html`(한도 패널)+`styles.css`(.admin-quota-row)+admin/index.html(cache-buster) + `tests/test_llm_usage_quota.py`(신규 10) + docs.
- 내용: 역할별 기본 + 계정별 특수(override) LLM 토큰 한도(daily/monthly). 토큰 계량/대시보드는 기존(TASK-0136) 재사용, 한도 설정+사전 게이트만 추가. 미설정=무제한(안전 기본), 초과 시 /api/ask 429. fail-open(PG 장애/킬스위치). admin UI 로 역할/계정 한도 편집.
- Why: 사용자 요청 — LLM 비용 통제(역할 기본·계정 특수).
- Verification: test 10/10 + make test 회귀 0 + py_compile + node --check. outside-voice SHIP-WITH-FIXES(MINOR clamp+footgun 캡션 흡수).
- Rollback: 게이트/헬퍼/엔드포인트/UI 복원. 한도 테이블 비파괴(잔존 무해, 행 없으면 무제한). cache-buster 되돌림.
- Deploy: web 재빌드.
## CHG-20260619T034522-ai-claude-oauth-google-foundation
- Date: 2026-06-19 (TASK-20260619T034522-oauth-google-foundation — Google 계정 OAuth 로그인 토대). 사내 웹서비스 편입 기반작업. **Critical §12.3 — 인증 경로.**
- Scope: feature-0003 `src/app.py`(config 블록 `OAUTH_GOOGLE_*`/`OAUTH_NO_PASSWORD_SENTINEL` · `_ensure_oauth_identity_schema`+fast/slow 양 경로 · `_fetch_account_rows` SELECT(email/auth_provider/oauth_subject) · `_serialize_account`(email/auth_provider) · OAuth helper 9종 `_oauth_google_configured`/`_oauth_b64url(_decode)`/`_oauth_pkce_pair`/`_oauth_state_encode(decode)`/`_oauth_google_exchange_code`/`_oauth_decode_id_token_claims`/`_oauth_validate_claims`/`_oauth_provision_username`/`_oauth_resolve_or_provision_account` · 엔드포인트 `auth_oauth_config`/`auth_oauth_google_start`/`auth_oauth_google_callback` · import RedirectResponse · build 무관) + `src/static/index.html`(Google 버튼 hidden) + `app.js`(refreshOAuthLoginButtons/showOAuthErrorIfPresent/showAuthOverlay 훅) + `styles.css`(.auth-oauth/.auth-divider/.btn-oauth) + admin/index.html(cache-buster `?v=20260619-oauth-foundation`) + `docker-compose.yml`(agent-common env_file `.env.oauth` optional) + `.env.oauth.example`(신규) + `.gitignore`(.env.oauth) + `tests/test_oauth_google_foundation.py`(신규 29) + docs(SECURITY.md §15 / FUNCTION.md AC-0600~0601 / TASK.md / TEST.md / REPORT.md).
- 내용: 표준 OAuth 2.0 / OIDC Authorization Code + PKCE(S256) + HMAC 서명 state(CSRF/TTL) + ID token claim 검증(iss/aud/exp/nonce/email_verified/도메인) + 계정 매핑(subject 매칭 / email link[기존 비번 보존] / 신규 pending 자동 생성). 기존 `_issue_auth_session`·`_set_session_cookie`·RBAC 재사용. 외부 의존 0(stdlib urllib). **비파괴 기본 비활성** — `_oauth_google_configured()` False(기본) 시 `/start`·`/callback` 404, DB 컬럼 NULL, 프론트 버튼 hidden → 런타임 인증 경로 무영향. 기존 username/password 로그인 공존.
- Why: 사용자 요청 — 사내 웹서비스 Google 로그인 편입 기반작업("검토 우선 + 비파괴 토대"). 사용자 결정(2026-06-19): 모든 Google 계정 허용 + 신규 pending 자동생성 + 비번 로그인 공존.
- Verification: test_oauth_google_foundation.py 29/29 + 전체 회귀 0(사전존재 product-delete 2건 base 동일·무관) + py_compile OK. ANCHOR §1~§3 충돌 없음(인증/세션이 app.py 에 있다는 §1 와 정합).
- Rollback: config/helper/엔드포인트/프론트/문서 복원. `WebAccounts` Email/AuthProvider/OAuthSubject 컬럼·UNIQUE index 비파괴(잔존 무해, NULL). `.env.oauth`/.example/compose env_file/cache-buster 되돌림.
- Deploy: **보류**(토대만 — flag OFF). 활성화는 Google Cloud Console OAuth Client 등록 + `.env.oauth` 주입 + `WEB_OAUTH_GOOGLE_ENABLED=1` + JWKS 서명검증 추가 후 별 cycle(SECURITY.md §15.3).

## CHG-20260619T040000-ai-claude-two-factor-auth
- Date: 2026-06-19 (TASK-20260619T040000-two-factor-auth — 2단계 인증 TOTP). 사용자 보안 보강 6종 중 ⑥(마지막).
- Scope: feature-0003 `src/app.py`(TOTP stdlib 헬퍼·`WebAccountTotp` 스키마+양 경로·cred_crypto 암호화·등록 3EP·로그인 2단계+`auth_login_totp`·admin 해제·audit 4 action·`_serialize_account`/`_fetch_account_rows` totp_enabled·brute-force 흡수·백업코드 row-lock) + `src/static/app.js`(showTotpLoginPrompt·renderProfileTotp)+`admin.js`(triggerAccountTotpDisableFlow·2FA 배지)+`index.html`(프로필 2FA 섹션)+`styles.css`(.is-2fa)+cache-buster + `tests/test_two_factor_auth.py`(신규 10) + docs(SECURITY.md §16).
- 내용: RFC 6238 TOTP(stdlib), secret cred_crypto 암호화(AAD 계정 바인딩), 로그인 2단계(pending token=DEK-HMAC), 백업코드(1회용 row-lock), self-service 등록/해제 + 관리자 강제 해제. 기본 미설정=2FA off(무회귀). brute-force 방어=IP throttle+계정 잠금(②) 2FA 단계 적용 + 비번-통과-리셋 증폭 차단.
- Why: 사용자 요청 — 로그인 2차 인증.
- Verification: test 10/10(TOTP roundtrip 실 동작) + make test 회귀 0 + py_compile + node --check. outside-voice SHIP-WITH-FIXES(MAJOR brute-force 흡수 + MINOR 백업코드 race 흡수).
- Rollback: TOTP 헬퍼/엔드포인트/UI/로그인 2단계 복원. WebAccountTotp 테이블 비파괴(잔존 무해, 행 없으면 2FA off). cache-buster 되돌림.
- Deploy: web 재빌드(인증=web 전용, agent_core 무관).

## CHG-20260619T084227-ai-claude-release-notes-security-6
- Date: 2026-06-19 (보안 보강 6종 릴리즈 노트 기록). frontend-only(콘텐츠 큐레이션).
- Scope: feature-0003 `src/static/release-notes-data.js`(2026-06-19 블록 6 항목 추가+summary)+index.html/admin.html(release-notes-data.js cache-buster) + docs.
- 내용: ①공유링크 만료·②로그인 보호·③감사 무결성 검증·④AI 사용 한도·⑤어시스턴트 보안 강화(추상)·⑥2단계 인증을 사용자 향 문장으로 기록. 내부 메커니즘(암호화/해시체인/인젝션/RBAC 등) 비노출(AC-0579).
- Why: 사용자 요청 — 릴리즈 노트 기록 후 배포.
- Verification: node --check(release-notes-data.js) + 금지 용어 스캔 clean. 렌더 정본=PB-0008.
- Rollback: 6 항목 제거 + summary/캐시버스터 복원.
- Deploy: web 재빌드(정적 콘텐츠).

## CHG-20260623T014626-ai-claude-quota-ui-relocate
- Date: 2026-06-23 (LLM 한도 UI 를 역할·계정 상세로 이전 — 사용자 보고 수정). ④ 후속.
- Scope: feature-0003 `src/app.py`(_list_roles·_fetch_account_rows·_serialize_account 에 quota 노출, read-only) + `src/static/admin.js`(loadQuotas 제거→buildQuotaEditor 공용 + 역할/계정 상세 섹션, usage 탭 호출 제거) + `admin.html`(usageQuotaDetails 제거) + `styles.css`(.admin-quota-row→.admin-quota-editor/-fields/-hint) + admin/index.html(cache-buster) + tests.
- 내용: LLM 한도 설정 위치를 '감사>LLM 사용량'(모니터링 전용)에서 '계정'·'역할' 상세 화면으로 이전. 한도는 역할/계정의 속성이므로 각 상세에서 구성. 백엔드 PUT 엔드포인트·RBAC 게이트·집행 로직 무변경(직렬화 read-only 추가 + UI 위치만).
- Why: 사용자 보고 — 감사 목적 화면에 한도 설정은 부적절.
- Verification: test 11/11 + make test 회귀 0 + py_compile + node --check + CSS brace. 화면 정본=PB-0008.
- Rollback: 직렬화 quota 필드 제거 + buildQuotaEditor 복원→loadQuotas + usageQuotaDetails 복원.
- Deploy: web 재빌드(정적+직렬화).

## CHG-20260623T021500-ai-claude-quota-editor-escapehtml-fix
- Date: 2026-06-23 (buildQuotaEditor escapeHtml ReferenceError 수정 — PB-0008 적발 잠복 버그). quota-ui-relocate 후속.
- Scope: feature-0003 `src/static/admin.js`(buildQuotaEditor: escapeHtml 보간 제거→DOM 프로퍼티 주입 input.value/note.textContent) + tests(F1 회귀 가드). 백엔드·엔드포인트·RBAC·스키마 무변경.
- 내용: `escapeHtml` 은 app.js 전용인데 admin.html 이 app.js 미로드 → admin 페이지에서 `buildQuotaEditor` 의 escapeHtml 호출이 `ReferenceError` → 역할·계정 상세 "LLM 사용 한도" 섹션 미렌더. ④ 도입(05d58d1) 이래 구 loadQuotas 도 동일(잠복, production 무렌더). 비신뢰 값을 DOM 프로퍼티로 주입해 escapeHtml 의존 제거(XSS 안전성 강화).
- Why: PB-0008 실 브라우저 검증에서 ReferenceError 적발 — 배포된 한도 편집기가 렌더 불가.
- Verification: test_llm_usage_quota.py 11/11(F1 escapeHtml 부재 가드 추가) + node --check + outside-voice SHIP. 사전존재 실패 2건(product-delete·db_query_ux) 무관. 화면 정본=PB-0008.
- Rollback: buildQuotaEditor DOM 주입 → escapeHtml 보간 복원(단 admin 페이지 재차 깨짐).
- Deploy: web 재빌드(정적). cache-buster 갱신.

## CHG-20260623T030418-ai-claude-quota-rbac-permission
- Date: 2026-06-23 (계정별·역할별 LLM 사용 한도 조회/조절 전용 권한). 사용자 요청.
- Scope: feature-0003 `src/app.py`(PERMISSION_DEFINITIONS +quota.read/quota.manage·GET quotas 게이트 quota.read·PUT role/account 게이트 **quota.read+quota.manage**·_strip_quota_fields_if_unpermitted 헬퍼 + admin_me/admin_accounts/admin_roles/**admin_update_account** 적용) + `src/static/admin.js`(PERMISSION_DEPENDENCIES·그룹 메타·buildQuotaEditor readOnly·역할/계정 상세 섹션 게이트) + `admin.html`(cache-buster) + tests.
- 내용: LLM 사용 한도(역할 기본·계정 특수)의 조회/조절을 console.manage 에서 분리. quota.read(조회)·quota.manage(조절, read 선행) 전용 권한. 조회 권한 없으면 한도 섹션 미렌더 + 직렬화 노출 차단(GET·계정/역할 리스트·**PATCH 응답** 전부 strip). 조회만 있으면 readOnly(값 표시·편집 불가). **조절은 서버에서도 조회 종속 집행(PUT=quota.read+quota.manage)**. admin 무영향(seed 전권).
- Why: 사용자 요청 — 한도 조회/조절을 역할·계정 단위로 위임 가능하게. 조절은 조회 종속.
- Verification: test 18/18(B8 양권한 게이트·B11/B12 MAJOR 가드·F2/F3 신설) + deps map 자동검증 + make test 회귀 0 + node --check + py_compile + outside-voice SHIP-WITH-FIXES(2 MAJOR 흡수). 화면 정본=PB-0008.
- Rollback: quota.read/manage 정의 + deps + 게이트 + strip 헬퍼 + readOnly 제거 → console.manage 게이트 복원.
- Deploy: web 재빌드(정적+직렬화). **이행 주의**: console.manage 만 가진 비-admin 커스텀 역할은 quota.read/manage 명시 부여 필요(least-privilege).

## CHG-20260623T053000-ai-claude-quota-admin-catchup
- Date: 2026-06-23 (admin 역할 quota.read/manage catchup — PB-0008 적발 lockout 수정). quota-rbac-permission follow-up.
- Scope: feature-0003 `src/app.py`(`_ensure_seed_roles` admin catchup 리스트에 quota.read/quota.manage 추가) + tests(B13).
- 내용: 한도 게이트를 console.manage→quota.read/quota.manage 로 전환했으나 신규 권한이 기존 배포 admin 역할(WebRolePermissions RoleId=3)에 미부여 → admin 포함 전원 한도 접근 불가(lockout). seed=set(PERMISSION_CODES)는 role 생성 시점만 적용. admin catchup(TASK-0288 datasource 선례 동형, INSERT IGNORE 멱등)으로 재시작 시 backfill.
- Why: PB-0008 라이브 검증에서 bootstrap_admin quota.read=false 적발 — 기능 자체가 동작 불가.
- Verification: test 16/16(B13 catchup 가드) + make test 회귀 0 + py_compile. 배포 후 재PB-0008(admin 한도 편집 가능 + 3-tier).
- Rollback: catchup 2줄 제거(단 기존 admin 다시 lockout).
- Deploy: web 재빌드 + 재시작(시작 시 _ensure_seed_roles backfill 실행).

## CHG-20260623T090440-ai-claude-sample-feedback-curation
- Date: 2026-06-23 (답변 피드백 → 샘플쿼리 KB 환류 flywheel 의 web 층 — ROADMAP dba-ai-nl2sql ITEM-03). PLAN-APPROVED.
- Scope: feature-0003 `src/app.py`(PERMISSION_DEFINITIONS +`kb.sample.curate`(group=kb) · 사용자 적재 endpoint POST `/api/conversations/{cid}/sample-feedback` + `_conversation_scope_key` 헬퍼 · 검수 endpoint 3종 GET/POST `/api/admin/sample-feedback`[/{id}/approve|reject]) + `src/static/app.js`(답변 말풍선 👍/👎/"샘플 등록" 버튼 + `_buildSampleFeedbackControls`/`_extractSqlFromContent`/`_precedingUserQuestion`) + `src/static/admin.js`(ADMIN_TAB_PERMISSIONS["sample-review"] · switchTab lazy-load · loadSampleFeedback/renderSampleFeedbackList/_sampleFeedbackAction · PERMISSION_GROUP_ORDER/LABELS·ADMIN_PERMISSION_SECTIONS·PERMISSION_DEPENDENCIES 에 kb 그룹) + `src/static/admin.html`(샘플 검수 탭/pane + cache-buster) + `src/static/index.html`(cache-buster) + `src/static/styles.css`(.message-feedback·.admin-sf-* 규칙) + `tests/test_sample_feedback_curation.py`(신규 15케이스).
- 내용: 사용자 답변 피드백을 sample_feedback(pending)에 적재(PG/agent_kb, generated_sql PII 마스킹은 코어가 수행) → 관리 콘솔 "샘플 검수" 탭(kb.sample.curate)에서 도메인 전문가가 승급(sample_queries)/거부. 적재/승급/거부 로직 정본 = feature-0002 `modules.sample_feedback`(in-process import, 재구현 0). web 은 RBAC(kb.sample.curate·대화접근)·audit(memory MySQL)·scope(대화 pinned product → _resolve_product_insight_scope.scope, 폴백 'common')·cross-DB conn 분리만 강제. 승급은 명시 호출만(자동학습 금지 — poisoning 방어). PG write 는 autocommit=False(원자성). 👎/비-pending 승급 시도 → 409. 사용자 적재는 대화 접근자(열람자 포함) 누구나(발화 권한 무관).
- Why: ROADMAP dba-ai-nl2sql ITEM-03 — 피드백→KB 환류로 NL2SQL 검색 정확도를 운영 중 지속 개선.
- Verification: test_sample_feedback_curation.py 15/15(R1·R2·S1~S3·U1·U2·A1~A3·L1·SC1) + test_permission_dependency_map.py·test_insight_reset.py·test_audit_rbac.py·test_admin_me_rbac.py 회귀 0 + full feature-0003+0002 suite 회귀 0(사전존재 product-delete·share-redaction 9건은 baseline stash 비교로 무관 확인) + node --check(app.js/admin.js) + CSS brace 1454 balanced + py_compile. **신규 RBAC = 보안 표면 → 메인 세션이 적대적 security 리뷰 후 마감**. UI 실렌더 정본=PB-0008(Windows-browser, 메인).
- Rollback: kb.sample.curate 정의 + endpoint 4종 + admin.js/html 탭 + app.js 버튼 + styles.css 규칙 제거 → 환류 web 층 제거(코어 modules.sample_feedback 는 무영향, 미사용 상태로 잔존).
- Deploy: web 재빌드(정적+엔드포인트). **선행조건**: PG(agent_kb)에 sample_feedback/sample_queries 스키마 + titan-embed 임베딩(1024-dim, bge-m3 복구됨)이 가용해야 적재·승급 동작. 신규 RBAC 는 admin 자동 보유, 비-admin 검수자는 kb.sample.curate 명시 부여 필요(least-privilege).
- **보안 fix 흡수(REV-20260623-0334 적대 security 리뷰 SHIP-WITH-FIXES)**: MAJOR-1 — 사용자 피드백 endpoint `post_sample_feedback` 에 `_search_rate_limit_check(account_id, max_per_min=10)`(429) 추가(큐 abuse/DoS 차단). **cross-ref feature-0002** `modules/sample_feedback.py`: MAJOR-2 — `promote_feedback` SELECT `FOR UPDATE` 행락 + UPDATE `AND status='pending'`(TOCTOU 이중승급 차단); MINOR-1 — `record_feedback` 가 nl_question 도 PII 마스킹(`_mask_sql`→`_mask_pii` 일반화); NIT-1 — `_mask_pii` fail-open 에 경고 로그. 보안 fix 후 회귀 0(flywheel 12 + curation 15 = 27 통과).

## CHG-20260623T183803-item03-security-fixes
- Date: 2026-06-23 (TASK-20260623T090440-...-sample-feedback-curation 후속 — 적대 security 리뷰 REV-20260623-0334 SHIP-WITH-FIXES 흡수). ITEM-03.
- Scope: ITEM-03 web flywheel 의 보안 하드닝(이전 commit e5acb43 위). + ROADMAP ITEM-03 status→done.
- 내용:
  - **feature-0003** `src/app.py`: `post_sample_feedback` 에 per-account rate-limit(`_search_rate_limit_check`, max 10/min → 429) — 검수 큐 spam/DoS 차단(MAJOR-1).
  - **cross-ref feature-0002** `src/modules/sample_feedback.py`: `promote_feedback` SELECT `FOR UPDATE`+UPDATE `AND status='pending'`(TOCTOU 이중승급 차단, MAJOR-2); `record_feedback` 가 nl_question 도 `_mask_pii`(MINOR-1, `_mask_sql`→`_mask_pii` 일반화); `_mask_pii` fail-open 경고 로그(NIT-1).
  - docs/improvements/dba-ai-nl2sql/ROADMAP.md: ITEM-03 done + §5 갱신(임베딩 복구 반영).
- Why: 신규 RBAC=보안 표면. 적대 security 리뷰가 적재 abuse·promote 경합·PII 비대칭을 적발 → 흡수.
- Verification: test_sample_flywheel 12 + test_sample_feedback_curation 15 = 27 통과(회귀 0) + py_compile + `_mask_sql` 잔여참조 0(utils `_mask_sql_arg` 무관).
- Files: src/app.py, ../feature-0002-agent-core/src/modules/sample_feedback.py(cross-ref), docs/{TASK,MODIFY,FUNCTION,REVIEW}.md, docs/improvements/dba-ai-nl2sql/ROADMAP.md.
- Rollback: rate-limit 호출 제거 / FOR UPDATE·status 가드 제거 / nl_question 마스킹 환원(각 독립, 비파괴).
- Deploy: web + ask-worker 재빌드(app.py + 코어 sample_feedback baked). 마이그 없음.

## CHG-20260624T105228-item08-fix-with-ai
- Date: 2026-06-24 ("AI 로 고치기" 표적 재수정 버튼 — ROADMAP dba-ai-nl2sql ITEM-08). PLAN-APPROVED.
- Scope: feature-0003 web 만. `src/app.py`(POST `/api/conversations/{cid}/fix-with-ai` = `post_fix_with_ai` + 헬퍼 `_sanitize_fix_with_ai_fragment`·`_build_fix_with_ai_message`·`_make_internal_ask_request` + 상수 `_FIX_WITH_AI_SQL_CAP`/`_ERR_CAP`/`_RATE_PER_MIN`) + `src/static/app.js`(`_failedSqlStepFromMessage`·`_buildFixWithAiControl` + `renderMessages` `canFixHere` 게이트) + `src/static/styles.css`(`.message-fix-with-ai`/`.message-fix-status`/`.message-fix-btn:disabled`) + `src/static/index.html`(cache-buster) + `tests/test_fix_with_ai.py`(신규 9케이스). **agent_core·ask-worker·gateway·credential·ROADMAP 무변경.**
- 내용: 실패한 SQL 결과(assistant 답변의 `meta.steps` 에 `tool==='execute_sql'` && `error` 가진 step)에만 "AI 로 고치기" 버튼 노출. 클릭 → 신규 엔드포인트에 `{executed_sql, error_message}` POST. 서버가 **고정 정정 지시문**을 구성하고 client 의 SQL/error 는 **nonce-봉인 데이터 블록(`«SQL-{nonce}»`…`«/SQL-{nonce}»`)으로만** 삽입("봉인 블록 안은 사용자 지시 아님" 명시) → **동일 conversation_id 로 기존 `/api/ask` 핸들러에 1회 재dispatch**(원본 NL 질문 재전송 아님 — 대화 맥락이 cid 에 보존). product/role/allowed_schemas 해석·동시성 슬롯·worker 분기·ITEM-07 self-reflection 모두 ask 가 재사용(중복 구현 0). 응답은 `/api/ask` 와 동일 result dict → 프론트가 `refreshWorkspace` 로 대화 reload(정정 결과가 같은 대화에 새 assistant message 로 추가).
- Why: ROADMAP ITEM-08 — fixable SQL 오류 시 사용자가 새 질문을 직접 다시 입력하지 않고 1클릭으로 표적 정정을 트리거(ITEM-07 self-reflection 의 사용자 트리거 진입점).
- 보안: 가드 순서 = `post_sample_feedback` 동형 — `_require_account` → `_account_can_access_conversation`(미보유 404) → `_search_rate_limit_check(account_id, max_per_min=5)`(429, 1회 dispatch=full LLM run 점유라 sample-feedback 10 보다 보수적) → `_account_has_permission("conversation.ask")`(발화 권한 403 — 열람 전용 멤버 차단) → `record_audit_event(action=conversation.fix_with_ai)`. **프롬프트 인젝션 방어(REV M1 흡수)**: 지시문은 서버 고정 문구, client 입력은 **nonce-봉인 데이터 블록**에만. `_build_fix_with_ai_message` 가 매 요청 `secrets.token_hex(8)` nonce 로 `«SQL-{nonce}»`…`«/SQL-{nonce}»`(+ERR) 봉인하고, `_sanitize_fix_with_ai_fragment` 가 입력에서 **봉인 구분자 `«·»`+nonce 를 제거**(주 방어 — client 가 닫는 마커 위조 불가, 개행/가짜 라벨/가짜 마감문이 봉인 블록 안에 갇혀 데이터로만 취급) + 백틱→U+02CB(보조) + 제어문자 제거 + 길이 cap(SQL 8000/err 4000). 빈 값·과대(cap×4) → 400. (초기 구현은 `[실패한 SQL]` 라벨+개행 구분이라 백틱만 막고 개행/라벨 탈출 가능했음 → nonce 봉인으로 교정.) **XSS**: 프론트는 SQL/error 를 textContent/JSON body 로만 전달(innerHTML 무사용). **1회 dispatch**: 추가 루프 없음 — 재실패해도 self-reflection 내부 cap(AGENT_SELF_REFLECTION_MAX) 이 처리.
- worker-mode 주의: `_make_internal_ask_request` 의 `_receive` 가 정정 body 를 1회 공급 후 원본 `request._receive` 로 위임 → worker mode attach 루프의 `is_disconnected` 폴링이 실제 client 연결 상태를 정확히 반영(synthetic 즉시 disconnect 로 run 이 조기 중단되는 버그 회피).
- Verification: test_fix_with_ai.py **10/10**(G1 404·G2 403·G3 429·V1/V2 400·P1 봉인블록·P2 백틱+cap·**M1 회귀 개행/가짜마커 탈출 차단**·D1·내부request) PYTHONPATH=feature-0002:feature-0003 실측 통과 + py_compile(app.py) + node --check(app.js). 전체 suite 는 `make test`(agent 이미지, modules.memory 병합). 사전존재 실패(product-delete·share-redaction = DB/컨테이너 `/app` 경로 의존)는 본 변경과 무관. **적대 backend+security 리뷰(REV-20260624T105228) SHIP-WITH-FIXES → M1(인젝션 봉인) 흡수**(REVIEW.md). UI 실렌더 정본=PB-0008(Windows-browser, 메인).
- Rollback: 엔드포인트 `post_fix_with_ai`+헬퍼 3종+상수 / app.js 버튼 2함수+`canFixHere` / styles.css 3규칙 / index.html cache-buster 제거 → "AI 로 고치기" 기능 제거(agent_core self-reflection 은 무영향, 자동 트리거 경로만 유지).
- Deploy: web 재빌드(정적+엔드포인트). 마이그 없음. self-reflection env(`AGENT_SELF_REFLECTION_ENABLED`/`_MAX`)는 기존 설정 그대로 사용(본 변경이 도입/수정 안 함).
- Files: src/app.py, src/static/app.js, src/static/styles.css, src/static/index.html, tests/test_fix_with_ai.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.

## CHG-20260624T020000-product-insight-status-badge
- Date: 2026-06-24 (TASK-0308 — 제품 탭 데이터소스 인사이트 탐색 상태 표시, Minor §12.3). PLAN-APPROVED(목업 승인).
- Scope: **frontend only**. 제품 '데이터 소스 & 접근 가능 데이터베이스' accordion 행 헤더에 insight 탐색 on/off 시각 표시 + primary 표기를 엔진 배지 색으로 전환.
- 내용:
  - `static/admin.js` `_renderDsAccordion`: 행 헤더에 `.ds-acc-insight` 아이콘(켜짐=눈/은은, 꺼짐=빗금눈/amber 칩) 추가 — `meta.insight_enabled`(datasources API 기존 필드) 기반. title/aria-label 동반. 별도 '기본' 텍스트 배지(`ds-acc-primary`) 제거 → 엔진 배지에 `is-primary` 클래스 + title 부여(조건부 배지가 인사이트 아이콘 위치를 흔드는 문제 제거).
  - `static/styles.css`: `.ds-acc-insight`(+`.is-on`/`.is-off`) + `.ds-acc-engine.is-primary` 추가, 미사용된 `.ds-acc-primary` 제거.
- Why: 사용자가 제품 탭만 보고 datasource 의 insight 탐색 비활성(mssql-qa-idc)을 놓친 실수 재발 방지(상태가 데이터소스 관리 탭에만 있었음). 텍스트 추가 없이 OFF 를 두드러지게.
- Verification: admin.js node --check + Artifact 목업으로 사용자 디자인 승인. 백엔드 무변경(insight_enabled 기존 노출). UI 실렌더 검증=PB-0008(Windows-browser).
- Files: static/admin.js, static/styles.css, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 두 파일 revert(순수 additive·표현계층). 동작 회귀 없음.
- Deploy: web 재빌드(static baked) + cache-buster. 마이그/백엔드 없음.

## CHG-20260624T024500-task0308-pb0008-close
- Date: 2026-06-24 (TASK-0308 마감 — PB-0008 Windows-browser 검증 기록 + 체크박스 닫기). docs-only.
- Scope: TASK-0308(제품 탭 인사이트 탐색 상태 표시) 의 UI 실렌더 검증 결과 기록 + cycle 마감. 코드 무변경.
- 내용: `docs/TEST.md` §4 에 PB-0008 Windows-browser PASS 항목 추가(2026-06-24, **사용자 직접 시각 검증** — win-browser relay 아님; 배포=main `6606b8e`/PR #396, AI 가 서빙·정적검증 수행). `docs/TASK.md` TASK-0308 의 verify→PB-0008 체크박스 닫기(마감).
- Why: 저장소 관례(§15.4.1, UI 완료 게이트=PB-0008) — UI 변경의 실 화면 검증 결과를 TEST.md §4 에 남기고 cycle 을 마감.
- Verification: docs-only. 사실 근거 = 사용자 육안 검증 PASS + 직전 cycle 의 배포·서빙·정적 검증(TEST.md 기재).
- Files: docs/TASK.md, docs/TEST.md, docs/MODIFY.md, docs/REVIEW.md.
- Rollback: 문서 entry 제거(런타임 영향 0).
- Deploy: 불필요(문서만).

## CHG-20260624T130000-item11-metadata-glossary-enum
- Date: 2026-06-24 (메타데이터 거버넌스 MVP-1 — 용어/ENUM CRUD. ROADMAP dba-ai-nl2sql ITEM-11, Major §12.3 보안 경계). PLAN-APPROVED.
- Scope: feature-0003 web(primary) + feature-0002 agent-core(secondary, cross-ref). 기존 PG 테이블 `kb_glossary`·`enum_dictionary` 재사용 → **마이그레이션 없음**. **gateway·credential·ROADMAP·embedding provider 무변경.**
- **Cross-ref (feature-0002 secondary 변경)**: `unit/feature-0002-agent-core/src/modules/kb_glossary.py` — admin CRUD 코어 신규 6함수: `list_glossary_admin(conn, scope_key, limit=1000)`·`list_enum_admin(conn, scope_key, limit=1000)`(id 포함, **단일 scope**, read 의 common 캐스케이드 없음), `update_glossary_term(conn, term_id, scope_key, term, definition)`·`update_enum_entry(conn, entry_id, scope_key, table_name, column_name, code, label, schema_name="")`(by id + scope 가드, `cur.rowcount` 반환), `delete_glossary_term(conn, term_id, scope_key)`·`delete_enum_entry(conn, entry_id, scope_key)`(by id + scope 가드, 멱등 rowcount). 전부 `%s` 파라미터·scope 격리. 기존 `upsert_glossary_term`/`upsert_enum_entry`/read 경로 **무변경**(create 는 upsert 재사용). → feature-0002 MODIFY.md 에도 동 변경 기록 필요(메인이 cross-feature 정합 시).
- 내용(feature-0003 `src/app.py`): 신규 RBAC `kb.ingest.manual`(group kb, label "메타데이터 수동 등록/편집") — `PERMISSION_DEFINITIONS`(kb.sample.curate 다음) + `_ensure_seed_roles` admin catchup(retroactive backfill). 8 엔드포인트 `/api/admin/metadata/glossary`·`/enums` 각 GET(목록 ?scope_key=)·POST(생성=upsert)·PUT/{id}(수정)·DELETE/{id}(삭제, 멱등). 공용 헬퍼: `_metadata_resolve_account`(RBAC 게이트), `_metadata_valid_scope_keys`(datasources.all_datasources 키 ∪ common — best-effort, 실패 시 common 만 보수), `_metadata_check_scope`(빈값/미허용/길이 400), `_metadata_str_field`(trim+cap), `_metadata_enum_fields`(ENUM 공통 필드, schema 선택), `_metadata_read_json`, `_metadata_audit`(memory conn, resource_type=kb_metadata), `_metadata_iso`. PG write `_pg_connect(autocommit=False)`+commit/rollback(원자성), RO list `_pg_connect_ro`. audit action: glossary.term.{create,update,delete}·enum.entry.{create,update,delete}. ENUM update UNIQUE(scope,schema,table,column,code) 충돌 → 409.
  - `src/static/admin.html`: "메타데이터" 탭 버튼(`data-admin-tab="metadata"`, display:none 게이트) + pane(scope `<select>`·2 서브탭(용어/ENUM)·생성/수정 폼·목록). cache-buster `?v=20260624-item11-metadata`(styles+admin.js).
  - `src/static/admin.js`: `ADMIN_TAB_PERMISSIONS["metadata"]=["kb.ingest.manual"]` + `switchTab` 진입 `initMetadataTab` + `adminState.metadata`{subTab,scopeKey,items,editing}. `_METADATA_FIELDS`(서브탭별 필드 정의) 기반 폼 렌더. scope 드롭다운 = `adminState.datasources`(기존 fetch 재사용) + 공용(common). load/render/submit/delete + `_metaEsc`. **XSS: 전 사용자 데이터 DOM API(createElement/replaceChildren/textContent)·innerHTML 무사용**.
  - `src/static/styles.css`: `.admin-meta-*`(scope select·서브탭·폼·행) 추가(기존 CSS 변수 사용).
  - `src/static/index.html`: styles.css cache-buster `?v=20260624-item11-metadata`(스타일만 변경 — app.js 무변경이라 미bump).
  - `tests/test_metadata_glossary_enum.py`: 신규 13 케이스.
- Why: ROADMAP dba-ai-nl2sql ITEM-11(메타데이터 거버넌스). 용어/ENUM 사전을 운영자가 콘솔에서 직접 등록·편집 → 질문/스키마 매칭 시 프롬프트 주입(답변 정확도). 기존엔 코어 upsert/read 만 있고 admin list/update/delete + UI 부재였음.
- 보안: 전 mutation RBAC `kb.ingest.manual` 게이트(미보유 403, 코어 미호출 — 단위테스트 G403/E403 검증). KB poisoning 면 → 명시 권한 편집만(자동학습 없음). scope_key 는 datasource key(소문자) 또는 'common' — **요청 body/쿼리 명시 사용**(CURRENT_FACT_SCOPE_KEY 멀티DS 미갱신 BLOCKER 회피). 미허용/빈 scope → 400. 수정/삭제 by id + **scope 가드**(타-scope 행 비변경, 비존재 404, 삭제 멱등 200). 입력검증(필수누락/길이 cap). audit(memory conn, PG 작업과 cross-DB 분리). **XSS: 프론트 전 경로 textContent/DOM API**.
- Verification: `tests/test_metadata_glossary_enum.py` **13/13**(PYTHONPATH=feature-0002/src:feature-0003/src 실측). 회귀: sample-feedback 15/15·permission-dependency-map 16/16 무영향. py_compile(app.py·kb_glossary.py) + node --check(admin.js) OK. 적대 security 리뷰 + UI 실렌더 PB-0008 = 메인(본 worktree 는 commit/push/PR/merge/deploy 금지).
- Phase 2 연기(미구현): 테이블/컬럼 설명 CRUD · describe_table 부트스트랩 · 샘플 admin 직접 편집. ROADMAP 갱신은 메인.
- Rollback: app.py(권한 1·catchup 1줄·8 엔드포인트+헬퍼) / admin.{html,js} 메타데이터 블록 / styles.css `.admin-meta-*` / index.html cache-buster / kb_glossary.py 6 함수 / 테스트 제거 → 메타데이터 탭·CRUD 제거(기존 upsert/read 경로 무영향).
- Deploy: web 재빌드(정적+엔드포인트). 마이그 없음(기존 테이블 재사용). 기존 배포 admin 역할은 재시작 시 `_ensure_seed_roles` catchup 으로 kb.ingest.manual 백필.
- Files: src/app.py, src/static/admin.html, src/static/admin.js, src/static/styles.css, src/static/index.html, tests/test_metadata_glossary_enum.py, (feature-0002) unit/feature-0002-agent-core/src/modules/kb_glossary.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
## CHG-20260624T031337-gc-settings-archive-leave (feature-0009 cycle, Minor §12.3)
- Date: 2026-06-24 (feature-0009 group-conversation cycle `gc-settings-archive-leave`, CHG-0022/REV-0024). **frontend only**.
- Scope: 대화 사이드바 `··· > [탭 목록]` 메뉴의 '보관'을 '설정' 팝업의 '대화 관리' 섹션으로 이동 + 보관 권한 없는 그룹 대화 참여자에게는 보관 대신 '나가기'(self-leave) 제공. 백엔드/스키마/RBAC 무변경.
- 내용:
  - `static/app.js` `openConversationItemMenu`: ··· 메뉴에서 '보관'(danger) 항목 제거 — 최종 순서 `공유 | 설정`.
  - `static/app.js` `openConversationSettings`: 팝업 하단에 '대화 관리'(`.conv-settings-sec-danger`) 섹션 추가. `canArchive = canDeleteConversation(conversation)` true(대화 보유자 또는 admin `.any`) → '보관' 버튼(기존 `deleteConversation` — 자체 confirm + refreshWorkspace 보존). 아니면서 `isGroupConversation(conversation)`(보관 권한 없는 그룹 참여자) → '나가기' 버튼(신규 `leaveConversation`). 둘 다 아니면(타인 1:1 열람 등) 섹션 미렌더.
  - `static/app.js` 신규 `leaveConversation(cid)`: `DELETE /api/conversations/{cid}/members/{state.user.id}` self-leave(백엔드 `remove_conversation_member` 기존, `is_self_leave` 게이트) + `window.confirm` + 성공 토스트 + `refreshWorkspace("")`(leave 응답에 `current` 없음 — 기본 대화 재선택).
  - `static/styles.css`: `.conv-settings-sec-danger .conv-settings-sec-title{color:var(--danger)}` + `.conv-settings-danger-btn{margin-top:2px}`(버튼은 기존 `.btn-danger` 재사용).
  - `static/index.html`: app.js·styles.css cache-buster `?v=20260624-settings-notif` → `?v=20260624-archive-leave`.
- Why: feature-0009 `gc-group-authz-flag` 로 보관(archive)은 owner/admin 전용 2차 게이트라, 비보유 그룹 멤버에게 ··· 메뉴 '보관'을 노출해도 backend 가 항상 거부했다(허울 버튼). 보관을 설정 팝업으로 옮기고, 비보유 참여자에게는 실제 수행 가능한 행동(멤버십에서 빠지는 '나가기')을 노출해 UI-권한 정합. 백엔드 leave 엔드포인트는 이미 존재했으나 프론트 진입점이 없었다.
- Verification: `node --check app.js` PASS + 신규 `tests/verify_settings_archive_leave.mjs` **22/22 PASS**(정적 소스 단언 — 메뉴 보관 제거·공유/설정 유지·설정 보관/나가기 분기·`(canArchive||isGroup)` 가드·self-leave members DELETE·본인 id·confirm·refreshWorkspace·CSS brace 1489=1489) + 적대적 3-렌즈(security/authz·correctness·UX) 서브에이전트 리뷰 **실질 결함 0**(REVIEW.md REV-…-gc-settings-archive-leave). UI 실렌더 정본=PB-0008(Windows-browser, 배포 후 — 본 worktree 에서 미실행).
- Files: `static/app.js`, `static/styles.css`, `static/index.html`, `tests/verify_settings_archive_leave.mjs`, `docs/{MODIFY,FUNCTION,REVIEW,TEST}.md` (+ feature-0009 `docs/{TASK,MODIFY}.md` cross-ref).
- Rollback: app.js/styles.css/index.html revert + 신규 `leaveConversation`·테스트 제거(표현계층·additive). 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked) + cache-buster 반영. 마이그/백엔드 없음.

## CHG-20260624T075458-gc-share-participants (feature-0009 cycle, Minor §12.3)
- Date: 2026-06-24 (feature-0009 group-conversation cross-cut cycle `gc-share-participants`). **frontend only**. 코드/문서 정본=feature-0003-agent-web-ui — feature-0009 `docs/{TASK,MODIFY}.md` 에 cross-ref.
- Scope: 공유 팝업(`작업 화면 > 대화 탭 > ··· > 공유`)에 그 대화에 참여 중인 멤버 roster 를 함께 표시. 백엔드/스키마/RBAC/엔드포인트 무변경(기존 게이트된 read 엔드포인트 재사용).
- 내용:
  - `static/app.js` `openShareDialog(cid)`: 팝업 골격에 '참여 중인 사용자' subhead + `<div class="share-participants">` 추가(링크 생성 섹션과 '발급된 공유 링크' 목록 사이). 신규 `loadParticipants()` 헬퍼가 `GET /api/conversations/${cid}/members`(기존, `conversation.read.own/.any` + 멤버십 게이트) 를 호출해 `{members:[{account_id,username,role}], owner_account_id}` 를 칩으로 렌더. owner(`role==='owner'` 또는 `account_id===owner_account_id`) 우선 정렬 후 username 정렬, owner 에 '소유자' 배지. 아바타는 기존 `_msgAvatarEl(account_id, name, "user", null, seed)`(실아바타→Identicon 폴백, gc-avatar-identicon 정합) 재사용. 사용자명은 `textContent`(XSS), 빈 username 은 `사용자 {id}` 폴백.
  - 갱신 배선: 팝업 진입 시 `await load(); await loadParticipants();`. joinable 링크 생성 성공 직후에도 `await loadParticipants()`(joinable 생성이 `_ensure_owner_membership` 로 owner 를 멤버로 자가치유 → roster 즉시 반영). 빈(`아직 참여 중인 다른 사용자가 없습니다…`)·로딩(`불러오는 중…`)·에러(`참여자 목록을 불러오지 못했습니다.`) 상태 처리.
  - `static/styles.css`: `.share-participants`(flex-wrap + `max-height:132px; overflow-y:auto` 스크롤 cap), `.share-participant`(칩), `.share-participant-name`(ellipsis), `.share-participant-role`(소유자 배지), `.share-participant .msg-avatar{margin-right:0}`. 기존 CSS 변수 재사용(fallback 포함).
  - `static/index.html`: app.js·styles.css 캐시버스터 → `?v=20260624-share-participants`(둘 다 변경).
- Why: feature-0009 그룹 대화에서 공유 팝업은 "누가 이 대화에 들어와 있나"를 보여주지 않아, 공유한 사람이 현재 참여자 구성을 확인할 수 없었다. 멤버 roster 엔드포인트는 이미 존재했으나(설정 패널 제거 이후 API-only) 프론트 표면이 없었다. live-presence(실시간 접속) 는 제품 미구현 — feature-0009 멤버십 모델상 "참여 중" = 멤버 roster 이므로 그걸 노출(신규 데이터 경로/노출 경계 없음, ANCHOR §1·§3 "멤버십=열람 경계" 정합).
- 보안/authz: members 엔드포인트 게이트(`conversation.read.own/.any`)를 그대로 재사용 — 이미 대화 전체를 볼 수 있는 자만 roster 를 본다(신규 privacy 노출 0). 공유 메뉴 가시성 게이트(`conversation.share.create`)와 권한이 다를 수 있으나, read 불가 actor 는 members 가 **404** 반환 → 로컬 catch 가 우아하게 안내(roster 미노출, 같은 게이트인 `/shares` 도 동반 실패). 아바타는 기존 `/api/avatars/{id}`(로그인 요구, 신규 노출 아님).
- Verification: `node --check app.js` PASS + CSS brace 균형 1549=1549 + 신규 `tests/verify_share_participants.mjs` **17/17 PASS**(정적 소스 단언). **§18.8 적대적 3-렌즈(security/authz·correctness·UX) 서브에이전트 리뷰 — BLOCKER/MAJOR 0**: MINOR 2(주석 부정확·스크롤 부재)+NIT 1(빈상태 문구) 적발 → 전부 흡수. XSS·use-after-close(detached 노드 no-op)·joinable race·owner null·빈 username 방어 확인(REVIEW REV-20260624T075458-gc-share-participants). UI 실렌더 정본=PB-0008(Windows-browser, 배포 후 — 본 worktree=WSL 미실행).
- Files: `static/app.js`, `static/styles.css`, `static/index.html`, `tests/verify_share_participants.mjs`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md` (+ feature-0009 `docs/{TASK,MODIFY}.md` cross-ref).
- Rollback: app.js(`loadParticipants`+팝업 골격 2줄+갱신 2줄)/styles.css(`.share-participant*`)/index.html(캐시버스터) revert + 테스트 제거(순수 additive·표현계층). 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked) + cache-buster 반영. 마이그/백엔드 없음.

## CHG-20260624T090534-ci-pytest-green (CI infra + test-fake fix, Minor §12.3)
- Date: 2026-06-24. **CI/test maintenance** — 제품·런타임 코드 무변경. 별도 worktree `ai/claude/ci-pytest-green-fix`.
- Reason: `.github/workflows/ci.yml` 의 pytest PYTHONPATH 에 repo 루트가 빠져 `app.py` 의 `import shared` 가 collection 단계에서 실패 → feature-0003 테스트 84개 일괄 ERROR(main CI 장기 red). 부수적으로 TASK-0302(삭제 전 `SELECT IsDefault` 존재 가드, 미존재 404) 도입 후 `test_product_delete_block_conv` 의 fake 가 해당 쿼리를 미처리해 404→stale 실패.
- 변경:
  - `.github/workflows/ci.yml` "Unit tests (pytest)" step: ① PYTHONPATH 에 `:.`(repo 루트) 추가(`shared` 해소 — Makefile `test` 의 `…:/work` 와 동형) ② pytest 전 `ln -sfn unit/feature-0003-agent-web-ui/src web`(컨테이너 `/app/web` 레이아웃 가정 `import web.app` 테스트 해소 — repo 미커밋, CI 런타임 전용) ③ `sudo mkdir -p /shared && chmod 777 /shared`(app.py import 시 `SESSION_DIR(/shared/web_sessions).mkdir()` — bare-runner 엔 `/shared` 부재로 `PermissionError`, 컨테이너 `/shared` 볼륨과 동형화).
  - `tests/test_product_delete_block_conv.py` `_Cursor` fake: `select isdefault from webproducts where id` 분기 추가(기본값 비-기본 제품 존재, `product_missing`/`is_default` store 키 지원) → TASK-0302 핸들러와 정합.
- 검증: CI 동일 재현(web 심링크 + repo루트 PYTHONPATH) 전체 suite **all green(exit 0)** + ruff PASS. 84 collection ERROR + 2 stale fail → **0**. 런타임/스키마/마이그 0.
- Rollback: ci.yml step + 테스트 fake 분기 revert. 제품 영향 0.
- Deploy: 없음(CI 전용·테스트 전용).

## CHG-20260625T092403-doc-sync-release-notes (TASK-20260625-doc-sync-release-notes — 직전 릴리즈노트(0fd4ca9, 06-23 16:52) 이후 머지분 릴리즈노트 정합, Minor §12.3 — 사용자 노출 정적 콘텐츠)
- Date: 2026-06-25 (`/_dqa:doc_sync` maintenance). **콘텐츠 데이터만** — 렌더 로직·백엔드·스키마·RBAC 무변경.
- Scope: `src/static/release-notes-data.js`(릴리즈노트 정적 큐레이션)가 직전 sync(0fd4ca9, 06-23 16:52) 의 06-23 블록에 멈춰 있어 그 이후 main 병합된 user-facing 변경(late 06-23 + 06-24)이 미반영 → 새 `date: "2026-06-24"` 블록 prepend + `generated` 스탬프 갱신. (윈도=직전 릴리즈노트 commit 이후 전체 — 적대 검증이 late-06-23 16:52~19:16 머지 누락 적발 → 정정.)
- 내용:
  - `static/release-notes-data.js`: `releases` 배열 head 에 `2026-06-24` 블록 추가(items 14 = admin 5 + work 9, type=new/improved/fixed). 항목(admin): 메타데이터(용어·코드·테이블·컬럼 설명) 콘솔 등록·수정 / 메타데이터 입력 AI 자동작성 / 샘플 검수 화면 / 관리 콘솔 제품 관리 인사이트 탐색 상태 표시 / 일부 데이터소스 의미정보·샘플 미반영 수정. 항목(work): 실패 조회 ‘AI 로 고치기’ / 공유 팝업 참여자 표시 / 답변 피드백+‘샘플 등록’ / 멘션·데스크톱 알림 제어+대화별 음소거 / 보관→설정 이동+그룹 나가기(보관·이름변경 owner-only) / 공유 참여허용 owner-only / 사이드바 1:1·그룹 구분 / 멘션 알림 발신자 표기 정리 / 공유 직후 첫 메시지 오류 수정.
  - `generated`: `"2026-06-23"` → `"2026-06-25"`.
  - 사용자 평이화 — 내부 구현/테이블명/feature-id/엔드포인트/RBAC 코드 비노출(파일 작성원칙 정합).
- Why: 릴리즈노트가 직전 sync(0fd4ca9, 06-23 16:52) 이후 머지 작업과 drift. 사용자가 보는 ‘업데이트 내역’ 화면이 late-06-23 + 06-24 변경을 누락 → doc_sync 로 정합.
- 대응 커밋(reality): 461506e+147426f(메타데이터 등록 admin) · 393d15c(메타데이터 AI 자동완성 admin) · e5acb43(답변 피드백+샘플 검수 admin/work, late 06-23) · 16746be(scope_key 死data fix admin) · 1ee5f1a(AI로고치기 work) · 4a9ab9b(인사이트 상태 work) · 2c35d57(공유 참여자 work) · eb459e4(멘션·데스크톱 알림 제어/음소거 work) · 5f4f45b(보관 이동/나가기 work) · dca8f81(공유 참여허용 게이트 work) · 43687e9(사이드바 그룹 구분+보관/제목 owner work, late 06-23) · 6df7fac(알림 표기 fix work) · eb46302(공유 직후 fix work). 제외(내부): feature-0011 shared 추출·SSOT consolidation·CI fix·발표자료·doc_sync.
- Verification: `node --check release-notes-data.js` PASS(JS 구문) + 스키마(type/area/title/detail) 정합 + 머지 커밋 14건 1:1 대조(윈도=0fd4ca9 이후, 적대 검증 Lens B 누락 적발분 e5acb43/eb459e4/43687e9 보강). 로직 무변경(데이터 큐레이션) → 적대 패널 불요(REVIEW [SKIPPED]).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`.
- Rollback: release-notes-data.js 의 `2026-06-24` 블록 + generated 한 줄 revert(순수 콘텐츠·additive). 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked) — 새 릴리즈노트 화면 반영. 마이그/백엔드 없음.

## CHG-20260625T020249-admin-metadata-relocate (관리 콘솔 사이드바 IA — 메타데이터/샘플 검수를 '감사'→신설 '지식베이스' 그룹 재배치, Minor §12.3)
- Date: 2026-06-25 (`/_template:entry`). 전용 worktree `ai/claude/admin-metadata-relocate`(base 2a73c64). **정적 DOM 재배치만** — JS/CSS/백엔드/스키마/RBAC/pane 본문 무변경.
- Reason: '메타데이터' 탭(용어/ENUM/테이블/컬럼 거버넌스 — kb.ingest.manual)이 '감사'(읽기전용 모니터링) 그룹에 위치해 의미 부정합(사용자 보고). 동 그룹의 '샘플 검수'(kb.sample.curate, 피드백→샘플쿼리 KB 환류 검수)도 동일하게 KB 거버넌스 성격. 사용자 원안('시스템>설정' 이동)보다, 둘을 신설 '지식베이스' 그룹으로 묶고 '감사'를 순수 모니터링(감사 로그·LLM 사용량·보관 대화)으로 정리하는 IA 가 더 정합(AskUserQuestion 확정).
- 변경: `src/static/admin.html` 사이드바 nav — '감사' 그룹 라벨/divider 다음에 있던 `metadata`/`sample-review` 버튼 2개를 제거하고, '시스템' 그룹 직전에 `<div class="admin-tab-group-divider">`+`<div class="admin-tab-group-label">지식베이스</div>` 신설 후 메타데이터→샘플 검수 순으로 재배치. 버튼 속성(`data-admin-tab`,`id`,`style="display:none"`) 전부 보존.
- 회귀 0 근거: `admin.js` 의 탭 가시성/그룹경계(`applyAdminTabVisibility` — DOM순서 동적), 권한 게이팅(`ADMIN_TAB_PERMISSIONS` 키 기반·`canSeeTab`), pane 매칭(`switchTab` — `data-admin-pane` 문자열), 클릭 바인딩(`data-admin-tab`), 탭 초기화(`tabName === "metadata"|"sample-review"`)가 전부 그룹 DOM 위치에 비의존. styles.css 에 nth-child/위치 셀렉터 없음. 그룹 자동숨김(visible 탭 0이면 라벨+직전 divider hide)이 신설 그룹에도 동일 적용.
- Verification: diff 검수(admin.html 단일, 11+/5-) + §18.8 적대적 3-렌즈 서브에이전트(권한게이팅 회귀·pane 매칭·숨은 의존성·IA정합·접근성) **BLOCKER/MAJOR 0 SHIP**(MINOR 1: 사이드바 '지식베이스' vs admin.js:167 권한그룹 `kb:"지식베이스(KB) 검수"` 용어 미세 불일치 — 후속 통일 추적). UI 실렌더 정본=PB-0008(Windows-browser, 배포 후 — 본 worktree=WSL 미실행, WARN-only).
- Files: `src/static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,REPORT}.md`.
- Rollback: admin.html 의 버튼 2개 위치 + '지식베이스' 그룹 라벨/divider revert(순수 표현계층·additive). 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked) — 사이드바 그룹 재배치 반영. admin.html 은 캐시버스터 쿼리 없이 직접 서빙(styles.css/admin.js 무변경이라 기존 캐시버스터 유지). 마이그/백엔드 없음.
## CHG-20260625T020410-gc-member-kick-ban (feature-0009 cycle, Critical §12.3 — 접근제어)
- Date: 2026-06-25 (feature-0009 group-conversation cross-cut cycle `gc-member-kick-ban`, CHG-0024/REV-0026). cross-feature: web `feature-0003`(app.py 신규 3 엔드포인트 + join/fork 게이트 + static) + core `feature-0002`(group_members.py·schema.sql·alembic 0018). 코드/문서 정본=feature-0003 — feature-0002/0009 cross-ref.
- 사용자 요청(`/_template:entry`): 공유 팝업에서 소유자가 특정 참여자를 kick/ban 처리하는 구조. 결정: **엄격 owner 전용** + **unban/차단목록 UI 포함**(AskUserQuestion).
- Scope: 추방(kick=멤버 제거, 재참여 가능)·차단(ban=제거+재참여 영구 차단)·해제(unban). 신규 PG 테이블 `conversation_member_bans`(alembic 0018). **배포 마이그레이션 동반**.
- 내용:
  - (feature-0002) `scripts/agent_runtime_schema.sql` + `alembic/versions/20260625_0018_conversation_member_bans.py`: 신규 테이블(PK conversation_id+account_id, banned_at/banned_by_account_id/reason, FK core_conversations ON DELETE CASCADE) + **명시 GRANT**(agent_kb_rw SELECT/INSERT/UPDATE/DELETE, agent_kb_ro SELECT — superuser 적용 deploy-trap 회피, 0012 동형).
  - (feature-0002) `modules/group_members.py`: `ban_member`(INSERT ON CONFLICT DO UPDATE 멱등, reason 512cap)·`unban_member`(DELETE, rowcount)·`is_banned`(빈 cid/account 단락)·`list_bans`(banned_at isoformat dict 직렬화). 전 SQL `agent_runtime.conversation_member_bans` schema-qualified + `%(...)s` 파라미터화.
  - (feature-0003) `app.py` 신규 엔드포인트 — **엄격 owner 전용**(`_conversation_owned_by_account(conn, cid, actor_id)` 게이트, `conversation.member.manage` 분기 없음 — 사용자 결정):
    - `POST /api/conversations/{cid}/members/{account_id}/ban`(async, body `{reason?}`): owner 게이트 + 가드(소유자 409·자기 409·target<=0 400) → `ban_member` **먼저** → `remove_member` 나중(비원자 fail-window 를 "차단 등재됨+멤버 잔존" 안전 방향으로) → audit `conversation.member.ban`.
    - `DELETE /api/conversations/{cid}/members/{account_id}/ban`(unban): owner 게이트 → `unban_member` → audit `conversation.member.unban`. 멤버십 자동 복원 없음(재참여는 공유 링크로).
    - `GET /api/conversations/{cid}/bans`: owner 게이트 → `list_bans` + WebAccounts username join → `{bans:[{account_id,username,banned_at,reason}]}`.
  - (feature-0003) `app.py` 재참여 차단 게이트(2곳, **fail-closed**):
    - `POST /api/share/{token}/join`: actor 식별 직후 `is_banned` → 403 + audit `conversation.member.join_blocked`(add_member 도달 전). PG 예외 시 500(차단 불명 시 거부).
    - `POST /api/public/share/{token}/fork`: **적대 리뷰 BLOCKER 수정** — 차단된 account 가 share-token fork 로 콘텐츠 전량 복제(exfiltrate)하던 우회를 `is_banned` 게이트(403 + audit `conversation.member.fork_blocked`, `_fork_conversation_impl` 호출 전, fail-closed)로 차단. (다른 fork 경로 `/api/fork_conversation`·`/duplicate` 는 `_account_can_access_conversation` 로 차단 비-멤버 404 — 우회 없음.)
  - (feature-0003) `static/app.js` `openShareDialog`: 참여자 칩에 owner viewer 전용 '추방'/'차단' 버튼(`viewerIsOwner && !targetIsOwner`, viewer=owner = `state.user.id === owner_account_id`) + 신규 '차단된 사용자' 섹션(`loadBans()`, owner 전용 노출 + '차단 해제'). confirm + 토스트 + roster/bans 갱신. `styles.css` `.share-participant-acts/-btn`·`.share-bans`·`.is-banned`. `index.html` 캐시버스터 `20260625-member-kick-ban`.
- 보안/authz: 엄격 owner 전용 4 엔드포인트(owner_account_id null 이면 누구도 통과 못 함 — fail-closed). ban/unban/bans 의 비-owner 는 끝내 403(read.any admin 은 404 게이트 통과 후 403 — 존재여부 누출이나 admin 은 이미 enumerate 가능, MINOR 수용). 재참여는 join+fork 양 경로 게이트(fail-closed). 멱등 ban/remove 순서로 fail-window 안전화. SQLi 전수 파라미터화. ban 후 기존 메시지/첨부는 잔존(tombstone, 기존 kick 정책 동일).
- Verification: `py_compile`(app.py·group_members.py·alembic) + `node --check app.js` + CSS brace 1561=1561. 테스트 `test_member_kick_ban.py` 8 + `test_member_ban_endpoints.py` 5(ast 계약: owner-only·가드·fork BLOCKER·join 순서) + `verify_member_kick_ban.mjs` 19 + 회귀(group_members 10·share-participants 17·settings-archive-leave 22) 전부 PASS. **§18.8 적대적 보안/authz 패널 + 재검증**: BLOCKER 1(fork 우회)+MINOR 3+NIT 1 적발 → 전부 흡수, 재검증 잔여 결함 0(REVIEW REV-20260625T020410-gc-member-kick-ban). UI/라이브 authz 정본=PB-0008 + 배포 후.
- Files: `app.py`, `static/{app.js,styles.css,index.html}`, `tests/{test_member_ban_endpoints.py,verify_member_kick_ban.mjs}`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md` + (feature-0002) `modules/group_members.py`·`scripts/agent_runtime_schema.sql`·`alembic/versions/20260625_0018_conversation_member_bans.py`·`tests/test_member_kick_ban.py`·`docs/{MODIFY,FUNCTION}.md` + feature-0009 `docs/{TASK,MODIFY}.md` + docs/SECURITY.md.
- Rollback: 엔드포인트 4 + join/fork 게이트 + group_members 4함수 + static + 테스트 제거 → alembic downgrade(DROP TABLE conversation_member_bans). 추방은 기존 DELETE 재사용이라 무영향.
- Deploy: **alembic 0018 적용 필수**(superuser + GRANT) + web 재빌드(static baked) + cache-buster. ask-worker 무관(web 전용).
## CHG-20260625T021924-rule-db-coverage (TASK-20260625T021924-rule-db-coverage — 정규식 자동 규칙 추가 DB 의 insight 분석 여부·완료율 UI 표시, Minor §12.3 — frontend-only)
- Date: 2026-06-25. **frontend-only** — 백엔드/스키마/RBAC/엔드포인트 무변경. 기존 coverage 데이터(`productCoverage.per_db`) 재사용.
- 배경: 관리 콘솔 제품 상세의 '데이터 소스 & 접근 가능 데이터베이스'에서 **수동 등록 DB**는 분석 여부·완료율을 표시하나, **정규식 자동 규칙(rule)으로 추가된 DB**는 규칙 카드에 이름만 표시돼 분석 진척을 알 수 없었다. 백엔드 `_compute_product_insight_coverage` 는 이미 Source 무관 전체 DB 의 coverage 를 `per_db[]` 로 반환하므로 frontend 매칭만 누락된 상태.
- 내용:
  - `static/admin.js` (`renderProductDetail` → `_buildRuleCard`): 규칙 종속 DB 렌더 루프에 진척 셀 추가. `adminState.productCoverage.get(product.id).per_db` 를 db명(소문자) 키 Map 으로 구성 → 각 규칙 DB 를 `schema_name`(소문자) 으로 lookup → `buildDbCoverageCells(covRow, _isProductCoverageLoading(product.id))`(메인 목록과 동일 helper) 부착. `connected===false` 면 항목에 `is-offline`.
  - `static/admin.js` (`redrawChips` 메인 목록): rule 행 제외를 `if (_isRuleRow) return;` → `if (_isRuleRow && canManage) return;` 로 조건부화. **이유(적대 리뷰 M1)**: 규칙 카드는 `if (canManage)` 게이트라 read-only 뷰어(product.read 만)는 카드를 못 보는데 기존엔 메인 목록에서도 rule 행을 무조건 제외해 규칙 DB 가 어디에도 안 보였다. canManage 뷰어는 규칙 카드에서(중복 방지 위해 메인 목록 제외 유지), read-only 뷰어는 메인 목록에서 coverage 와 함께 노출.
  - `static/styles.css`: `.cov-db-rule-dbitem`(flex) 컨텍스트의 `.cov-microbar{width:52px;flex:0 0 auto;margin-left:auto}` / `.cov-db-stat`/`.cov-db-status` flex 폭. grid 셀이 폭을 주는 메인 행(`.cov-db-row`)과 달리 flex 에선 마이크로바가 접히는 문제 해소.
  - `static/admin.html`: cache-buster `?v=20260624-metadata-ai-autocomplete` → `?v=20260625-rule-db-coverage`(styles.css + admin.js) — static baked 배포 시 캐시 무효화.
  - `tests/verify_rule_db_coverage.mjs`(신규): jsdom 으로 `buildDbCoverageCells` 의 분석 여부(DB✓/✗·연결 불가)·완료율(80% fill·4/5·측정 대기/중) 렌더 검증 + 규칙 카드 wiring·M1 조건부 skip·CSS·cache-buster 정적 단언. 20/20 PASS.
- Why: 사용자 요청 — 규칙 추가 DB 도 분석 여부·완료율을 보여 달라. 백엔드는 이미 데이터를 제공하므로 표현계층만 보완.
- Verification: `node --check admin.js` PASS + `tests/verify_rule_db_coverage.mjs` 20/20 PASS. 적대 리뷰(REV-20260625T021924) MAJOR 1(M1 read-only 뷰어 orphan) 흡수 후 SHIP. UI 실렌더 정본 = PB-0008(Windows-browser, 배포 후) — 본 worktree(WSL) 미실행.
- Files: `static/admin.js`, `static/styles.css`, `static/admin.html`, `tests/verify_rule_db_coverage.mjs`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- Rollback: admin.js 의 규칙 카드 coverage 루프 + 메인 목록 조건부 skip + styles.css 3줄 + cache-buster revert(순수 additive 표시 변경). 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked, deploy_scope: included) — 규칙 카드 분석 진척 반영. 마이그/백엔드 없음.

## CHG-20260625T030242-gc-member-actions-hover (feature-0009 cycle, Minor §12.3 — frontend CSS-only)
- Date: 2026-06-25 (feature-0009 group-conversation cross-cut cycle `gc-member-actions-hover`). 코드/문서 정본=feature-0003 — feature-0009 cross-ref. gc-member-kick-ban UI 후속(사용자 2차 요청).
- Scope: 공유 팝업 '참여 중인 사용자'/'차단된 사용자' 목록의 추방/차단/해제 버튼을 **기본 숨김 → 해당 칩 hover 시 애니메이션과 함께 펼침**(다른 칩 위치·구성 불변) + 목록을 **반응형 그리드**로 컴팩트화. **순수 CSS — JS/DOM/백엔드/엔드포인트 무변경**.
- 내용(`static/styles.css`):
  - `.share-participants`/`.share-bans`: `flex-wrap:wrap` → `display:grid; grid-template-columns: repeat(auto-fill, minmax(200px,1fr)); gap:6px 8px`. 셀이 그리드 트랙에 고정 → 한 셀 hover 확장이 다른 셀을 안 움직임(요구사항 "다른 사용자 위치 불변"). 다열이라 세로 길이 단축(사용자 2차 요청: 세로 스택 여백 낭비 해소). `.share-mgr-msg { grid-column: 1/-1 }`.
  - `.share-participant`: `inline-flex` → `flex`(셀 폭 채움) + `min-width:0`. `.share-participant-name`: `flex:1 1 auto; min-width:0`(이름이 셀 폭을 채워 **평소 여백 0** + ellipsis). avatar/role `flex-shrink:0`.
  - `.share-participant-acts`: 기본 `max-width:0; opacity:0; overflow:hidden; transform:translateX(-4px); pointer-events:none` → `.share-participant:hover>`/`:focus-within>` 시 `max-width:120px; opacity:1; transform:none; pointer-events:auto`. `transition: max-width .22s, opacity .18s, margin-left .22s, transform .22s`(자연스러운 펼침). `@media (hover:none)` 터치 기기 항상 노출(접근성). 칩 hover 시 배경/보더 미세 강조.
  - `index.html`: styles.css 캐시버스터 `20260625-member-actions-hover`(CSS-only — app.js 미변경 미bump).
- Why: gc-member-kick-ban 의 항상-노출 버튼이 칩 폭을 키워 "사용자당 공간 과도"(사용자 1차 지적). hover-reveal 로 컴팩트화하되, flex-wrap 인라인 확장은 형제를 reflow(요구 위반)하고 세로 스택은 우측 여백 낭비(사용자 2차 지적) → **그리드**가 셀 고정(reflow 0) + 이름 flex 채움(여백 0) + 다열(세로 단축)을 동시 충족.
- Impact: app.js 의 칩 DOM 구조(`.share-participant > .share-participant-acts`) 그대로 재사용 — JS 무변경. 비-owner viewer(버튼 없음)·owner 자기 칩(소유자 배지)은 hover 효과 없이 이름만 표시. 기능/권한/엔드포인트 0 영향.
- Verification: CSS brace 1571=1571 + 신규 `tests/verify_member_actions_hover.mjs` **15/15 PASS** + 기존 `verify_member_kick_ban.mjs`(JS·DOM 불변이라) 무회귀. 라이브 hover 애니메이션·셀 고정·여백 정본=PB-0008(배포 후 — worktree=WSL 미실행). 패널 SKIP: 순수 CSS 표현계층, 로직/보안/RBAC 무변경(REVIEW [SKIPPED:frontend-css-presentation-no-logic]).
- Files: `static/styles.css`, `static/index.html`, `tests/verify_member_actions_hover.mjs`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md` (+ feature-0009 `docs/{TASK,MODIFY}.md` cross-ref).
- Rollback: styles.css `.share-participant*`/`.share-bans` 그리드+hover 블록 revert(직전 always-visible) + 캐시버스터·테스트 제거. JS/백엔드/스키마 0.
- Deploy: web 재빌드(static baked) + cache-buster 반영. 마이그/백엔드 없음.

## CHG-20260625T045450-limit-subject-msg (계정 당 토큰 한도 초과 메시지 주체 명시 — cross-feature, feature-0002 주관, Minor §12.3)
- Date: 2026-06-25. 별도 worktree `ai/claude/limit-subject-msg`(base main). 서비스 메시지 정본·changelog = feature-0002 CHG-20260625T045450-limit-subject-msg. 본 항목은 feature-0003 계정 메시지 변경 기록.
- 변경(feature-0003):
  - `src/app.py` `_check_account_token_quota` 한도 초과 반환 메시지: `f"{_label} LLM 토큰 한도({limit:,})를 초과했습니다. 현재 사용량 {used:,}. 관리자에게 문의하거나 한도 초기화 시점까지 기다려 주세요."` 앞에 "계정의" + "사용" 추가 → `f"계정의 {_label} LLM 토큰 사용 한도(...)를 초과했습니다. ..."`. 도달 주체가 **계정**임을 명시(서비스 자체 요청량 한도와 구분). 사유 주석 2줄.
- Why: "요청량 한도"가 계정 한도(토큰 사용량)인지 서비스 한도(provider throttle)인지 모호 → 주체 명시로 구분. feature-0002 의 서비스 메시지("서비스 자체의 요청량 한도...")와 짝.
- Impact: `_check_account_token_quota` 게이트 로직(역할 기본/계정 override·일일/월간·fail-open)·HTTP 429·`/api/ask` 사전 차단 무변경. 순수 사용자 노출 텍스트. 메시지 텍스트 단언 테스트 부재(무회귀).
- Verification: py_compile(app.py) PASS. (전체 suite 는 Docker `make test` — 본 변경은 문자열만이라 게이트 영향 0.)
- Files: `src/app.py`, `docs/{TASK,MODIFY,REVIEW}.md`. (+ feature-0002 정본)
- Rollback: app.py 메시지 1곳 revert. 로직 영향 0.
- Deploy: web 재빌드·재시작(app.py). 마이그/스키마/static 없음.

## CHG-20260625T163424-gc-participant-product-select (feature-0009 cycle, Major §12.3 — authz 경계: 참가자 발화 RBAC) — 중단 세션 resume
- Date: 2026-06-25 (feature-0009 group-conversation cross-cut cycle `gc-participant-product-select`). 코드/문서 정본=feature-0003 — feature-0009 cross-ref. 원본 작성 세션(372f8779)이 코드 작성 직후 docs 직전 중단 → resume 으로 마무리.
- Scope: 공유 대화(그룹 대화) **참가자(비-owner 멤버)가 제품을 per-message 로 선택·발화**. 대화 공통 고정 제품에 본인 접근권이 없어도, **본인이 권한 가진 다른 제품**으로 이 요청에 한해 질의할 수 있다. ANCHOR §1 / REQ-GC-R7("발화는 발신자 본인 RBAC 로만 게이트") 보존 — 권한 *상속* 아님, 본인 권한 범위 내 선택. 대화 공통 바인딩은 비파괴(per-message override 가 대화 product 를 바꾸지 않음). owner·1:1 대화는 종전 PATCH 단일 경로 유지.
- 내용(백엔드 `src/app.py`):
  - `_parse_participant_product_override(conn, account, data)` 신규: body 의 `product_id`/`product_mode` override 를 파싱·검증. 선택 pinned 제품은 **발신자 본인** `_account_has_product_access` 통과분만 허용(무권한 → `{ok:False}` → 호출부 403). auto override 는 pid 검사 전 early-return(product_id=None). `0`/빈/파싱실패 pid → None(override 미적용, 표준 view-only 게이트 폴백).
  - `_conversation_view_only_products_for(conn, conversation_id, viewer_account)` 신규: 참가자가 보는 대화 고정 제품에 본인 접근권이 없을 때 '생성자 제품 — 열람 전용' **1건**만 반환(fail-closed: 비대화/owner/비멤버/auto·미고정/이미 접근가능 → []). 생성자 전체 카탈로그 미노출.
  - `get_session`: `/api/session` 응답에 `conversation_view_only_products` 동봉(except → []).
  - `ask` 핸들러: member 분기에서 `_participant_product_override` 채움 → 무권한 시 403, override 시 대화 공통 pinned 접근권 게이트 skip. run-product 단계에서 override 적용(pinned 시 `_account_has_product_access` **재확인** = authz 이중 게이트) + override 요청은 대화 공통 product_id backfill UPDATE skip(`_participant_product_override is None` 가드).
- 내용(프론트 `static/app.js`):
  - `isParticipantInSharedConversation()` 신규: `isGroupConversation && !isOwnConversation`(owner·1:1 → false).
  - `renderProductDropupMenu`: view-only 그룹 있으면 상단 헤더 "내 제품" + 하단 '공유 대화 생성자 제품 (열람 전용)' 회색·비활성 그룹 분리. `buildProductDropupItem` 에 `viewOnly` 옵션(disabled·aria-disabled·열람전용 배지·click listener 미등록).
  - `applyProductHydration`: 접근 불가 대화 고정 제품은 active pinned 으로 채택 안 함(auto 강등 — 항상 발화 가능), `viewOnlyProducts` 적재.
  - `setActiveProduct`: 참가자는 PATCH(403 유발) 미호출 — 로컬 상태만 갱신 + "다음 메시지부터 적용" 토스트 후 return. `sendPrompt`: 참가자일 때 `product_mode`/`product_id` per-message 동봉. `state.conversationViewOnlyProducts: []` 명시 초기화.
  - `static/styles.css`: `.product-dropup-section-head--viewonly`(구분선) + `.is-view-only`(회색·not-allowed) + `.product-dropup-item-viewonly`(열람전용 배지). `index.html` 캐시버스터 app.js·styles.css → `20260625-gc-participant-product-select`.
- Why: 공유 대화에서 참가자가 대화 고정 제품에 권한이 없으면 발화가 막혀, '함께 보고 논의'하다 본인 권한 제품으로 이어 질의할 길이 없었다. owner 의 대화 공통 바인딩(PATCH)과 분리된 per-message 경로로, 권한 경계(R7)를 깨지 않고 참가자 질의를 허용.
- Impact: owner·1:1 대화 무회귀(override 분기 member-only, FE `isParticipantInSharedConversation` owner/1:1 false). 대화 공통 product_id persist 경로 없음(backfill skip). view-only 노출은 대화 고정 1건 한정. auto override → 메타 스키마만(actor 접근 datasource 제한).
- Verification: `node --check`(app.js) PASS + `py_compile`(app.py) PASS + CSS brace 1577=1577. **§18.8 적대적 authz 패널(SUBAGENT) — 6개 공격가설(권한우회·바인딩오염·owner회귀·view-only과다·FE정합·auto) 전부 REFUTED, VERDICT SHIP, BLOCKING 0**(REV-20260625T163424). 단위 회귀는 Docker `make test`(modules.memory import — 로컬 PYTHONPATH 불가). **PB-0008 미실측**(worktree=WSL — 배포 후 실 그룹대화 권장).
- Files: `src/app.py`, `static/app.js`, `static/styles.css`, `static/index.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md` (+ feature-0009 `docs/{TASK,REPORT,MODIFY,REVIEW,FUNCTION}.md` cross-ref).
- Rollback: app.py 의 두 helper + ask/get_session override 블록 revert + app.js 의 view-only/참가자 분기 revert + styles.css view-only 블록 + 캐시버스터 revert. 스키마/마이그 0(순수 코드).
- Deploy: web 재빌드(static baked + app.py, deploy_scope: included) + cache-buster 반영. 마이그/백엔드 스키마 없음.
## CHG-20260625T065430-gc-other-msg-left (feature-0009 cross-feature, Minor §12.3 — frontend CSS-only)
- Date: 2026-06-25 (REV-20260625T065430-gc-other-msg-left). worktree `ai/claude/gc-other-msg-left`. 그룹대화 UX(feature-0009) — 코드 정본=feature-0003-agent-web-ui static.
- Reason: 사용자 요청(`/_template:entry`) — 그룹대화에서 자신의 메시지 버블은 우측 유지, assistant 와 상대방(타 참여자) 대화는 좌측에 출력.
- 변경(feature-0003 `static/`):
  - `styles.css`: `.message.is-user.is-other-message { align-self: flex-start; align-items: flex-start; }` 신규(기존 `.message.is-user` 의 `flex-end` 를 특이도 0,3,0 으로 override) → 상대방 메시지 좌측 정렬. + `.message.is-user.is-other-message .message-bubble` 에 `border-bottom-right-radius:14px; border-bottom-left-radius:var(--r-xs)` 추가 → 꼬리(모서리)를 좌측 하단으로(좌측 정렬 정합). 내 메시지(`is-own-message`)·assistant 규칙 무변경.
  - `index.html`: styles.css 캐시버스터 `v=20260625-role-account-prompt-autogen` → `v=20260625-gc-other-msg-left`.
- Why(설계): app.js `renderMessages()` 가 이미 발신자 귀속으로 `is-own-message`(내 메시지)/`is-other-message`(타 참여자)/`is-assistant` class 를 정확히 부여 중 → JS 변경 없이 CSS 정렬 규칙만 분기. 그룹채팅 관례(내=우측/타인=좌측)와 정합. 공유 대화 열람 시(owner≠나, sender meta 부재)도 owner 메시지가 `is-other-message`로 좌측 표시 — 요청("상대방=좌측")과 정합.
- Impact: 1:1 본인 대화(`is-own-message` 우측) 무회귀. JS/DOM/핸들러/엔드포인트/RBAC/스키마 0. 순수 표현계층.
- Rollback Notes: `styles.css` 2블록 + `index.html` 캐시버스터 revert. JS/백엔드/스키마 0.
- 검증: `node --check static/app.js` PASS(무변경) + 충실한 mock 렌더(실제 styles.css + renderMessages DOM, Chromium headless) 수치/스크린샷 — own=우측, other·assistant=좌측 동일 기준선. 패널 SKIP(순수 CSS, feature-0003 REVIEW [SKIPPED:frontend-css-presentation-no-logic]). **PB-0008 미실측**(본 worktree=WSL — 배포 후 실 그룹대화 권장).
- Files: `static/styles.css`, `static/index.html`, `docs/{TASK,MODIFY,REVIEW,TEST}.md` (+ feature-0009 cross-ref).

## CHG-20260625T165205-doc-sync-rn-0625 (TASK-20260625T165205-doc-sync-rn-0625 — 06-25 머지분 릴리즈노트 정합, Minor §12.3 — 사용자 노출 정적 콘텐츠)
- Date: 2026-06-25 (`/_dqa:doc_sync` maintenance, resume from doc-sync-20260625-160433). **콘텐츠 데이터만** — 렌더 로직·백엔드·스키마·RBAC 무변경.
- Scope: `src/static/release-notes-data.js` 가 직전 릴리즈노트(06-24 블록, 600f2b5) 이후 main 병합된 06-25 user-facing 변경을 미반영 → 새 `date: "2026-06-25"` 블록 prepend(9항목) + `index.html`·`admin.html` cache-buster bump.
- 내용:
  - `static/release-notes-data.js`: `releases` 배열 head 에 `2026-06-25` 블록(items 9 = work 3 + admin 4 + common 2). work: 안 읽음/@멘션 배지 / 메시지 좌우 정렬 / 멤버 추방·차단·해제. admin: 역할·제품 프롬프트 AI 자동작성 / 제품 분석률 95% 자동완성 / 규칙 추가 DB insight 커버리지 표시 / 지식베이스 메뉴 재편. common: 요청량 한도 메시지 주체 구분 / AI 준비 속도 개선.
  - `index.html`·`admin.html`: `release-notes-data.js?v=20260625-rn-0625` → `?v=20260625b-rn-0625`.
  - 사용자 평이화 — 내부 구현/테이블명/feature-id/엔드포인트/RBAC 비노출.
- Why: 릴리즈노트가 직전 sync(06-24 블록) 이후 06-25 머지와 drift → 사용자 ‘업데이트 내역’ 화면 정합.
- 대응 커밋(reality): 09114ed(안 읽음/@멘션 배지) · cc62773(메시지 좌우 정렬) · 1d83d94+29d1bbf(멤버 추방/차단/해제+hover) · 5c525db(역할/제품 프롬프트 자동작성) · 4cd26e7(제품 95% 자동완성) · 23b7175(규칙 DB 커버리지) · 874f15e(지식베이스 메뉴 재편) · 70c57f6(한도 메시지 주체) · 23fa679(init 임베딩 지연 회귀 해소). 제외(내부): feature-0011 shared P5a Step4/5·codebase-map·template v3.35.1·spec-anchor id·doc_sync META.
- Verification: `node --check release-notes-data.js` PASS + 스키마(type/area/title/detail) 정합 + 머지 커밋 10건 1:1 대조 + 적대 사실검증(general-purpose, 환각/귀속/평이화/누락/STATUS 5축) VERDICT CLEAN. 로직 무변경 → 적대 패널 불요(REVIEW [SKIPPED]).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`.
- Rollback: `2026-06-25` 블록 + 2 cache-buster revert(순수 콘텐츠·additive). 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked, deploy_scope: included) — 새 릴리즈노트 화면 반영. 마이그/백엔드 없음.

## CHG-20260625T103503-steps-btn-pending-persist (TASK-20260625T103503-steps-btn-pending-persist — 새 요청 진행 중 이전 답변 "단계 보기" 버튼 소실 수정, Minor §12.3 — frontend-only)
- Date: 2026-06-25 (/_template:entry dispatch, worktree ai/claude/fix-steps-btn-pending). frontend `static/app.js` 단일 파일 렌더 조건 로직만 — 백엔드·스키마·RBAC·라우팅 무변경.
- 증상: 대화 중 새 요청 전송 시 이전 assistant 답변의 "단계 보기 (N)" 버튼이 일시 소실 → 답변 완료 + 새로고침 후 재표시.
- 근본원인: `renderMessages()` 가 새 요청 시작 시(`sendPrompt` 가 `state.pendingBubble` 세팅 직후 호출) 이전 답변 버튼 부착을 `&& !state.pendingBubble` 가드로 막음. `message.meta.steps` 는 영속 데이터로 pending 과 무관하게 유효 → 가드가 오작동(완료+새로고침 시 `pendingBubble=null` 이라 복귀).
- 내용:
  - `static/app.js renderMessages()`: assistant meta.steps 버튼 부착 `if (msgMetaSteps.length && !state.pendingBubble)` → `if (msgMetaSteps.length)`.
  - `static/app.js renderMessages()`: `lastCompletedRunSteps` fallback 의 `if (!state.pendingBubble)` → bare block `{}`(가드 제거, `cr` 스코프 유지). 진행 중에도 직전 답변 step 버튼 유지. `:not(.is-pending)` 선택자 + `.bubble-steps-btn` 존재검사로 중복/오부착 차단.
  - `static/app.js`: state 에 `stepSidePanelLive` 필드 신설. `openStepSidePanel` 이 `pending === state.pendingBubble` 일 때만 live=true 설정, `refreshStepSidePanel` 은 live 일 때만 폴링 갱신. `closeStepSidePanel` 닫을 때 false 리셋. → 가드 제거로 생길 수 있는 새 엣지(진행 중 historical 단계 패널을 열어둔 채 라이브 폴링이 덮어쓰기)를 차단.
- Why: 영속 step 버튼은 새 요청 진행 여부와 무관하게 항상 유효해야 함. 일시 소실은 사용자에게 "단계 내역이 사라졌다" 는 혼란 유발.
- Verification: `node --check app.js` PASS + 적대적 frontend 리뷰(REV-20260625T103503-steps-btn-pending-persist, SUBAGENT adversarial-frontend, H1~H8 8가설 반증 시도 전부 실패=안전) VERDICT SHIP — BLOCKER/MAJOR/MINOR 0, NIT 2(NIT-1 흡수, NIT-2 pre-existing 보류).
- Files: `static/app.js`, `docs/{TASK,MODIFY,REVIEW}.md`.
- Rollback: app.js 4곳 revert(가드 복원 + state 필드/패널 가드 제거). additive·비파괴 — 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked) — 정적 자산 변경. 마이그/백엔드 없음.

## CHG-20260625T192007-doc-sync-rn-0625b (TASK-20260625T192007-doc-sync-rn-0625b — 06-25 잔여 머지분 릴리즈노트 정합, Minor §12.3 — 사용자 노출 정적 콘텐츠)
- Date: 2026-06-25 (`/_dqa:doc_sync` no-arg 전 타깃 정합). **콘텐츠 데이터만** — 렌더 로직·백엔드·스키마·RBAC 무변경.
- Scope: 직전 doc_sync(163929, PR#420~#436 기준 콘텐츠 작성) **이후** main 병합된 06-25 user-facing 변경 5종이 릴리즈노트 미반영 → 기존 `date: "2026-06-25"` 블록 items 에 5항목 **추가**(prepend 아님 — 같은 날 머지분) + `index.html`·`admin.html` cache-buster bump.
- 내용:
  - `static/release-notes-data.js`: `2026-06-25` 블록 items 9→14. work +4: 참가자 per-message 제품 선택(new) / 처리 중 입력·전송 안정화·동시 run 고착·블로킹 해소(fixed) / 1:1 인터럽트 재요청 + 그룹 중복차단(improved) / @assistant 발신자 표시 정정(fixed). common +1: datasource 회로차단 안내 문구 분리(improved). summary 갱신.
  - `index.html`·`admin.html`: `release-notes-data.js?v=20260625b-rn-0625` → `?v=20260625c-rn-0625`.
  - 사용자 평이화 — 내부 구현/테이블명/feature-id/엔드포인트/RBAC 비노출.
- Why: 직전 sync 의 브랜치 stale 로 06-25 후속 머지(PR#437~#440·#444)가 릴리즈노트와 drift → 사용자 ‘업데이트 내역’ 화면 정합.
- 대응 커밋(reality): 908fade(PR#440 per-message 제품 선택) · 1f370c4(PR#438 run-status 고착) + 334c858(PR#444 composer 비잠금/인터럽트/중복차단) · 1a69f70(PR#437 발신자 귀속) · c8637f2(PR#439 회로차단 안내). 흡수: 151679b(PR#442 unread baseline)→안 읽음 배지 항목. 제외(비-user-facing): 6104bf6(개발용 LLM 호출주체 임시전환 CHG-20260625T171844).
- Verification: `node --check release-notes-data.js` PASS + 스키마(type/area/title/detail) 정합 + 머지 5건 1:1 대조 + 사실검증(평이화·내부 비노출·과장 0). 로직 무변경 → 적대 패널 불요(REVIEW [SKIPPED]).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`.
- Rollback: 추가 5항목 + 2 cache-buster revert(순수 콘텐츠·additive). 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked, deploy_scope: included) — 새 릴리즈노트 화면 반영. 마이그/백엔드 없음.

## CHG-20260625T105417-steps-btn-cachebust (TASK-20260625T105417-steps-btn-cachebust — app.js cache-buster bump, steps-btn-pending-persist 전파 보강, Minor §12.3 — frontend-only)
- Date: 2026-06-25 (/_template:entry dispatch 후속, worktree ai/claude/steps-btn-cachebust). index.html script src 쿼리 1줄.
- 배경: 직전 cycle(CHG-20260625T103503-steps-btn-pending-persist)이 `static/app.js` 내용을 바꿨으나 index.html 의 `app.js?v=` 를 bump 하지 않음 → 같은 `?v=20260625-gc-unread-read-fix` 로 app.js 를 캐시한 사용자에게 수정 미전파 가능. app.py:10582(TASK-0256d): 정적 자산은 `?v=` 가 유일 전파 메커니즘(HTML 만 no-cache, 정적은 휴리스틱 freshness).
- 내용: `static/index.html` — `<script src="/static/app.js?v=20260625-gc-unread-read-fix">` → `?v=20260625-steps-btn-pending-persist`. (app.js 는 index.html 에서만 로드 — admin.html/share.html 무관.)
- Why: 새 `?v=` 가 브라우저에 새 URL 로 인식되어 강제 재요청 → 전 사용자가 수정된 app.js 수신.
- Verification: index.html grep 으로 단일 app.js 로드 확인. 순수 캐시버스터 — 로직 무변경 → 적대 패널 불요(REVIEW [SKIPPED]).
- Files: `static/index.html`, `docs/{TASK,MODIFY,REVIEW,FUNCTION}.md`.
- Rollback: `?v=` 문자열 1줄 revert. 비파괴 — 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked) — index.html 정적 자산 변경. 마이그/백엔드 없음.

## CHG-20260625T204254-conv-switch-fade (TASK-20260625T204254-conv-switch-fade — 대화 전환 크로스페이드(fade-out/in + 가속), Minor §12.3 — frontend-only)
- Date: 2026-06-25 (/_template:entry dispatch, worktree ai/claude/feature-0003-agent-web-ui, base 2666738).
- 배경: 좌측 사이드 대화 전환 시 클릭→약간의 텀→곧바로 교체(동작 정상이나 "딜레이+무전환"이 성능 이슈로 인식). `selectConversation` 이 `/api/use_conversation`+`/api/history` 두 await 동안 직전 대화를 화면에 남겼다가 `renderMessages` 로 즉시 교체 → 전환 효과 부재.
- 내용:
  - `static/app.js`: 크로스페이드 코디네이터 4함수 신설(`_beginConversationCrossfade` / `_commitConversationCrossfade` / `_removeSwitchGhost` / `_prefersReducedMotion`) + `selectConversation` 배선(클릭 즉시 begin → 네트워크 try/catch → commit). 고스트(messageLog clone) 오버레이 fade-out + 실제 로그 opacity 0 재구성 → fade-in, 목표가 먼저 준비되면 남은 fade-out 가속(ACCEL 90ms). 에러 경로도 commit 후 rethrow(빈 화면 방지). fade-in 후 인라인 opacity/transition 잔류 정리.
  - `static/styles.css`: `.messages-switch-ghost` 규칙 + reduced-motion display:none + `.message-point-rail` z-index:4(고스트 비가림 보강).
  - `static/index.html`: app.js·styles.css cache-buster → `?v=20260625-conv-switch-fade`.
- Why: 전환 효과 부재 → 사용자가 체감 성능 저하로 인식. 크로스페이드로 "즉시 반응 + 부드러운 등장" 체감 개선. 가속으로 빠른 로딩 시 불필요한 대기 없음. reduced-motion 사용자는 기존 즉시 교체 보존.
- Verification: `node --check app.js` PASS + CSS brace balance 1585/1585 + 적대적 frontend 리뷰(REV-20260625T204254-conv-switch-fade, SUBAGENT adversarial-frontend, H1~H8 8가설 반증 시도) VERDICT SHIP-WITH-FIXES → MAJOR(rail z-index)·MINOR(inline 잔류) 흡수 후 SHIP.
- Files: `static/app.js`, `static/styles.css`, `static/index.html`, `docs/{TASK,MODIFY,REVIEW}.md`.
- Rollback: app.js 코디네이터+배선 revert, styles.css 2블록 revert, index.html cache-buster revert. additive·비파괴 — 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked, deploy_scope: included) — 정적 자산(app.js/styles.css/index.html) 변경. 마이그/백엔드 없음.

## CHG-20260626T080501-doc-sync-rn-0626 (TASK-20260626T080501-doc-sync-rn-0626 — 릴리즈노트 06-25 후속 머지분(6건) + cache-buster bump, 비-정책 doc-only)
- Date: 2026-06-26 (`/_dqa:doc_sync` 무인 스케줄, worktree ai/claude/doc-sync-20260626-080501, base 3e553e9).
- 배경: 릴리즈노트 마지막 sync(a29a2f0 @ 06-25 19:36) 이후 main 병합된 06-25 user-facing 변경 6종이 릴리즈노트 미반영(drift).
- 내용:
  - `static/release-notes-data.js`: 기존 '2026-06-25' 블록 items 끝에 6항목 추가(14→20) — 단계 보기 버튼 소실 수정·대화 전환 크로스페이드·공유 링크 참여 불가 수정·안 읽음 배지 미감소 수정·입력창 미클리어 수정·그룹 AI 답변 정확도 개선 + generated 2026-06-25→2026-06-26.
  - `static/index.html`·`static/admin.html`: 릴리즈노트 cache-buster `release-notes-data.js?v=20260625c-rn-0625`→`?v=20260626-rn-0626`(콘텐츠 변경 전파 — app.py `?v=` 가 유일 무효화 경로). app.js/styles.css 토큰(conv-switch-fade) 무변경.
- Why: 현실↔릴리즈노트 정합(사용자 노출 표면 최신화). 평이한 한국어·내부 비노출.
- Verification: `node --check release-notes-data.js` PASS + 항목 스키마 정합 + 머지 6건 1:1 대조(ULTRACODE 적대검증 CLEAN).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`.
- Rollback: 6항목 + generated + cache-buster 2줄 revert. 비파괴 — 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked, deploy_scope: included) — 릴리즈노트 콘텐츠+cache-buster 전파. landing/deploy 는 cron wrapper 소관.

## CHG-20260626T025055-product-chip-always-enabled (TASK-20260626T025055-product-chip-always-enabled — 제품 선택 chip 처리 중 항상 활성화, Minor §12.3 — frontend + backend PATCH 가드, RBAC 무변경)
- Date: 2026-06-26 (`/_template:entry` dispatch, worktree ai/claude/feature-0003-agent-web-ui, base c11cc27).
- 배경: 사용자 보고 — assistant 에게 요청을 보낼 때(대화가 "요청 처리 중"인 동안) composer 좌측 제품 선택 chip(`#productChip`, 예: 'KR_QA')이 회색 비활성화돼 제품을 바꿀 수 없음. 이제는 항상 활성화 상태여야 함.
- 진단: 차단이 **세 계층**(전부 TASK-0047 turn-immutability) — 프론트 시각(renderProductChip)·프론트 기능(setActiveProduct reject)·백엔드(PATCH 409). 적대 검증 subagent 가 ③ 백엔드 409 를 적발: ①②만 풀면 owner 클릭이 409 에러 토스트로 실패("활성처럼 보이나 동작 안 함")라 셋 다 풀어야 실효.
- 내용:
  - `static/app.js` `renderProductChip()`: `const busy = isCurrentConvBusy(); chipEl.disabled = busy …` busy 분기 제거 → `chipEl.disabled=false`·`aria-disabled="false"`·`classList.remove("is-disabled")`·정상 title 고정. (이로써 `openProductDropup` 의 `if(chip.disabled)return` 가드가 항상 통과 → 처리 중에도 드롭업 열림.)
  - `static/app.js` `setActiveProduct()`: `if (isCurrentConvBusy()) { showToast("응답 처리 중에는 제품을 변경할 수 없어요.", true); … return; }` 프론트 기능 차단 가드 제거 → 처리 중 선택도 정상 적용. optimistic state·`writeProductPrefToLocal`·participant per-message override·owner `PATCH …/product`·토스트 문구("다음 답변/메시지부터 적용됩니다") 전부 무변경.
  - `src/app.py` `update_conversation_product`(@app.patch `/api/conversations/{cid}/product`): `if _conversation_is_processing(conn, cid): return _json_error("응답 처리 중에는 제품을 변경할 수 없습니다…", 409)` turn-immutability 409 가드 제거 + docstring 갱신. **권한 게이트(conversation.ask 권한·`_conversation_owned_by_account`·`_account_has_product_access`·IsActive)·UPDATE·`_save_account_product_pref`·응답 shape 전부 무변경** → RBAC/스키마/엔드포인트 계약 0 변경. helper `_conversation_is_processing`(3669)은 잔여 호출처 없으나 재사용 가능 query util 이라 보존(ruff clean).
  - `static/index.html`: app.js cache-buster `?v=20260625-conv-switch-fade` → `?v=20260626-product-chip-always-enabled`(변경 전파 — `?v=` 가 유일 무효화 경로).
- Why: 세 계층을 모두 풀어야 "항상 활성+사용 가능"이 실효. 처리 중 입력창 비잠금(feature-0009 composer-nonblock-interrupt R1)과 같은 방향. 제품 변경은 in-flight 답변이 아닌 다음 요청부터 적용되므로 토스트 문구가 그대로 정확.
- 안전성(적대 검증 SUBAGENT VERDICT SAFE): 제품은 `/api/ask` 슬롯 획득 후 1회 read(app.py:11676-11704)→`run_kwargs` baked(11995-12013)→worker payload(11293~) 로 캡처. worker `_payload_to_kwargs`(modules/ask.py:85-104)·`run_agent`(agent_core)는 conversation 제품 재조회 0. PATCH 는 단일 row UPDATE(부수효과 0). → 처리 중 변경이 in-flight 답변을 오염시키지 않고 데드락도 없음. TASK-0047/409 가드는 데이터 정합성 아닌 보수적 UX 가드(손상 위험 0). 상세 ADR-WEB-0006.
- Verification: `node --check app.js` PASS · `python3 -m py_compile app.py` PASS · `ruff check app.py` All checks passed · 잔여 chip disable 신호 grep 0 · `isCurrentConvBusy` 타 용도(renderComposer send/stop 5072 등) 무영향. 적대 검증 5축(ask 캡처 시점·worker 재조회·PATCH 부수효과·동시성·participant override) 반증 실패 SAFE.
- Files: `static/app.js`, `src/app.py`, `static/index.html`, `docs/{TASK,MODIFY,DECISIONS,REPORT}.md`.
- Rollback: app.js 2블록(renderProductChip busy 분기·setActiveProduct busy 가드) revert + app.py PATCH 409 가드 3줄 + docstring revert + index.html cache-buster revert. 비파괴 — 스키마/마이그/RBAC 영향 0.
- Deploy: web 재빌드(static+backend baked, deploy_scope: included) — 정적 자산(app.js/index.html) + app.py 변경. 마이그/스키마 없음.

## CHG-20260626T130501-doc-sync-rn-0626b (TASK-20260626T130501-doc-sync-rn-0626b — product-chip 릴리즈노트 06-26 블록 + cache-buster bump, 비-정책 doc-only)
- Date: 2026-06-26 (`/_dqa:doc_sync` 무인 스케줄 ULTRACODE, worktree ai/claude/doc-sync-20260626-130501, base 15ef5f4).
- 배경: 릴리즈노트 마지막 sync(cd05fa1 @ 06-26 08:35) 이후 main 병합된 user-facing 변경(f049fee 제품 chip 처리 중 항상 활성화, 12:05)이 릴리즈노트 미반영(drift).
- 내용:
  - `static/release-notes-data.js`: releases head 에 신규 '2026-06-26' 블록 prepend(1항목) — [improved/work] "답변을 만드는 중에도 제품 선택을 바꿀 수 있습니다"(처리 중 제품 선택 잠금 해제, 다음 질문부터 반영). generated 이미 2026-06-26(무변경).
  - `static/index.html`·`static/admin.html`: 릴리즈노트 cache-buster `release-notes-data.js?v=20260626-rn-0626`→`?v=20260626b-rn-0626`(동일자 2회차 datepart-suffix 규약, cd05fa1 `20260625c-rn-0625` 선례). app.js/styles.css 토큰 무변경.
- Why: 현실↔릴리즈노트 정합(사용자 노출 표면 최신화). 평이한 한국어·내부 비노출. product-chip 코드(f049fee)는 별도 cycle 에서 이미 배포·검증됨 — 릴리즈노트 announcement 만 누락분.
- Verification: `node --check release-notes-data.js` PASS + 항목 스키마 정합 + window 독립 재검증(cd05fa1..HEAD user-facing 단일 f049fee). 적대 검증자 CONDITIONAL 수정 흡수: ① 제목 '가능해짐'(부정확)→'바꿀 수 있습니다', ② cache-buster 는 cd05fa1 `20260625c-rn-0625` datepart-suffix 선례 따라 `20260626b-rn-0626`(검증자 제안 rn-part `0626b` 대신 datepart suffix — 둘 다 충돌 없으나 실관례 정합).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`.
- Rollback: 06-26 블록 + cache-buster 2줄 revert. 비파괴 — 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked, deploy_scope: included) — 릴리즈노트 콘텐츠+cache-buster 전파. landing/deploy 는 cron wrapper 소관.

## CHG-20260629T080501-doc-sync-rn-0629 (TASK-20260629T080501-doc-sync-rn-0629 — ask-dedup 릴리즈노트 06-26 블록 합류 + cache-buster bump, 비-정책 doc-only)
- Date: 2026-06-29 (`/_dqa:doc_sync` 무인 스케줄 ULTRACODE, worktree ai/claude/doc-sync-20260629-080501).
- 배경: 릴리즈노트 마지막 sync(483c4c0 @ 06-26 13:25) 이후 main 병합된 user-facing 변경(ask-dedup-idempotency 0818b0a 13:51·3595ea3 14:00)이 릴리즈노트 미반영(drift).
- 내용:
  - `static/release-notes-data.js`: 기존 '2026-06-26' 블록 items 에 [fixed/work] 1항목 합류 — "같은 질문이 드물게 두 번 처리되던 문제 수정"(연결 끊김 후 재전송 시 중복 처리·답변 → 1회로 수정). 블록 summary "처리 중에도 제품 선택 변경 가능"→"… · 같은 질문 중복 처리 수정". generated 2026-06-26→2026-06-29.
  - `static/index.html`·`static/admin.html`: 릴리즈노트 cache-buster `?v=20260626b-rn-0626`→`?v=20260629-rn-0629`(sync 일자 datepart). app.js/styles.css 토큰 무변경.
- Why: 현실↔릴리즈노트 정합(사용자 노출 표면 최신화). 평이한 한국어·내부 비노출. ask-dedup 코드(0818b0a/3595ea3)는 별도 cycle 에서 이미 배포·검증됨(REV-20260626T134920/135945) — 릴리즈노트 announcement 만 누락분.
- Verification: `node --check release-notes-data.js` PASS + 항목 스키마 정합 + ULTRACODE 적대 워크플로(릴리즈노트 비노출 반증 refuted:false·leaksInternals:false, realityMatch:true — REPORT/diff 대조). window 독립 재검증(483c4c0..HEAD user-facing 단일 ask-dedup).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`.
- Rollback: 06-26 블록 fixed 항목 + summary + generated + cache-buster 2줄 revert. 비파괴 — 백엔드/스키마/마이그 영향 0.
- Deploy: web 재빌드(static baked, deploy_scope: included) — 릴리즈노트 콘텐츠+cache-buster 전파. landing/deploy 는 cron wrapper 소관.

## CHG-20260629T114221-metadata-bootstrap-mssql-db (TASK-20260629T114221-metadata-bootstrap-mssql-db — 메타데이터 부트스트랩 MSSQL database 차원 + 패널 잘림 + describe_table 오버레이 정합, **Major §12.3** — cross-engine 골격 introspection, cross-feature 0003 주관·0002 read 정합)
- Date: 2026-06-29 (`/_template:entry` arg-given → 원본 세션 문서 갱신 중 중단 → `/_template:resume` 로 재개·완수). worktree `ai/claude/metadata-table-desc-fix`.
- Reason: 사용자 보고 — 관리 콘솔 > 메타데이터 > 테이블/컬럼 설명에서 (1) 테이블 설명도 AI 자동완성, (2) 테이블 명칭이 모두 올바르지 않은 값, (3) 패널 내부 공간 미확장으로 UI 잘림(컬럼 설명 탭 동일). 진단: AI 자동완성은 기구현(REQ-20260624-metadata-ai-autocomplete)이나 MSSQL 골격이 깨져 grounding 무력화. 근본=`admin_bootstrap`/`_metadata_introspect_table` 가 `database=None` 연결 → shared/db.py `_connect_mssql` 보안 기본값(중립 tempdb)에 붙어 임시테이블(`#…`) 노출 + 스키마 드롭다운이 고정 역할 스키마로 오염.
- 변경(feature-0003 `src/app.py`):
  - `admin_bootstrap_schemas`: 엔진 분기 — MSSQL=`list_server_databases`(system_databases 제외, unit_kind=database), MySQL=`load_known_schemas`(`_BOOTSTRAP_MYSQL_SYS_SCHEMAS`+`__invalid_default_db__` 센티넬 제외, unit_kind=schema). 응답에 engine·unit_kind 추가.
  - `admin_bootstrap`: MSSQL 은 schema 파라미터=database, 시스템 DB 제외 allowlist 멤버십 검증 후 `_db.connect(database=safe_schema)` 연결 → 신규 `_bootstrap_collect_skeleton_mssql`(비시스템 SQL 스키마 평탄수집, 저장 schema_name=database, 동명 dedupe, cap 500/200). MySQL 기존 경로 유지.
  - `_metadata_introspect_table`(단건 suggest grounding): 동일 엔진 분기 — MSSQL schema_name=database 로 연결·grounding(이전 tempdb 검증 실패→ungrounded 해소).
  - `_BOOTSTRAP_MYSQL_SYS_SCHEMAS` 상수 추가. 식별자 SQLi: database/SQL스키마/table 전부 `_safe_ident` + allowlist 멤버십 통과 후에만 dialect f-string 도달.
- 변경(프론트 `src/static/admin.js`·`admin.html`): `_metaBootstrapLoadSchemas` 가 `unit_kind` 로 라벨/플레이스홀더/상태문구 분기(MySQL='스키마'/MSSQL='데이터베이스'), `_metaBootstrapUnitWord`/`_metaBootstrapSetUnitLabel` 헬퍼, `metadataBootstrapSchemaLabel` id. 응답 누락 시 'schema' 폴백.
- 변경(`src/static/styles.css`): `.admin-meta-bootstrap-result` 의 `max-height:460px; overflow:auto` 제거 — metadata pane(AC-0622 overflow-y:auto)과의 이중 스크롤(내부 460px 갇힘)이 "패널 내부 잘림"(테이블·컬럼 공통)의 원인. pane 단일 스크롤로 통일.
- 변경(cross-feature, feature-0002 — §18.8 panel 적발 MAJOR + 재검증 BLOCKING 수정, Path A): describe_table 도구가 부트스트랩한 MSSQL 컬럼 설명을 보여주도록 read 축 정합. (a) `src/modules/tools.py` `_tool_describe_table`: KB 오버레이 조회 키를 MSSQL 일 때 SQL 스키마(dbo, 도구 인자)가 아니라 `get_active_default_db()`(pin 된 primary DB명)로 변경 → 부트스트랩 저장 규약(`column_descriptions.schema_name=database`)과 매칭. (b) `src/modules/kb_metadata.py` `load_column_descriptions_for_table`: schema 매칭을 case-insensitive(`LOWER(schema_name)=LOWER(%s)`)로 — 저장값은 원본 케이스(GunzGame)인데 read 키 `get_active_default_db()`는 소문자 정규화(gunzgame)라 PG `=`(case-sensitive)로 대문자 포함 DB명이 0행이 되던 회귀(panel 2차 BLOCKING) 해소. 이 함수는 describe_table 오버레이 전용. 이전엔 'dbo' vs 'GunzGame' 축 불일치로 부트스트랩 컬럼 설명이 describe_table 출력에 영영 미주입(질문-시점 grounding Path B 는 schema 무관 정상). MySQL 무변경.
- 설계 결정(사용자 AskUserQuestion 2건): ① MSSQL 4계층(server>db>schema>table)을 3-키 (scope_key, schema_name, table_name)에 매핑 시 **schema_name=database 명**(MySQL schema==DB 와 일관, read 라벨 의미있음, 마이그레이션 0). ② describe_table 오버레이 정합(Path A)을 본 cycle 에 포함(후속 분리 대신).
- 검증: py_compile(app.py·tools.py·kb_metadata.py) PASS · node --check(admin.js) PASS · 라이브 introspection 직호출(GunzGame 88 실테이블·temp 0)·실 HTTPS API(curl: schemas/bootstrap/suggest 정상)·Playwright eval(라벨 '데이터베이스'·129 DB·maxHeight none·88테이블·스크린샷). §18.8 적대 2-lens panel(보안 VERDICT SAFE / 정합성: Path A MAJOR 적발→fix→2차 BLOCKING(case) 적발→case-insensitive fix→3차 재검증).
- Files: feature-0003 `src/app.py`·`src/static/{admin.js,admin.html,styles.css}`·`docs/{TASK,REPORT,REVIEW,MODIFY,FUNCTION,TEST}.md` / feature-0002 `src/modules/{tools.py,kb_metadata.py}`·`docs/MODIFY.md` / `docs/STATUS.md` · `wiki/{Log,hot}.md`.
- Rollback: app.py 엔진분기·신규 함수·상수 revert(MySQL 경로 무영향) + admin.* 라벨분기 revert + styles.css max-height 1줄 복원 + tools.py 오버레이 키 1블록 + kb_metadata.py LOWER 매칭 revert. 데이터/스키마/마이그/RBAC 변경 0(런타임 introspection·read 키만).
- Deploy: web + ask-worker(tools.py·kb_metadata.py 변경) 재빌드(deploy_scope: included).
- Cross-ref: REQ/REV/TASK-20260629T114221-metadata-bootstrap-mssql-db / 정본 shared/db.py `_connect_mssql`(tempdb 고정, TASK-0213) · feature-0002 dialects.py(system_databases/system_schemas) · config.py `get_active_default_db`(소문자 정규화).

## CHG-20260629T141637-glossary-role-single-ui (TASK-20260629T141637-glossary-role-single-ui — 메타데이터 용어사전 역할 선택 UI 단일화 + 등록 mis-scope 가드, Minor §12.3 — 프런트 전용, RBAC/스키마/백엔드 무변경)
- Date: 2026-06-29 (resume — 원본 용어사전 대화 자율등록/검토 큐 중첩 배포본의 후속 결함 2건). worktree `ai/claude/glossary-role-single-ui`(base 3dfe81c).
- 배경: 배포본의 메타데이터 > 용어사전에 역할 선택 UI 2곳(툴바 역할 필터 + 등록 폼 역할 select)이 공존해 사용자가 각 동작을 식별하기 어려움. 사용자 결정 = "단일 역할 컨텍스트"(툴바 하나가 목록 필터 + 신규 등록 대상을 함께 결정).
- 변경(`src/static/admin.js`): ① `_METADATA_FIELDS.glossary` 의 `role_key`(roleselect) 폼 필드 제거 + 죽은 roleselect 렌더 블록·미사용 `_metaRoleOptions()` 제거. ② 신규 헬퍼 `_metaGlossaryTargetRole(editing)` — 등록/수정 대상 role_key 단일 진실원(생성=툴바 컨텍스트, 전체 역할 ""→공용 '*'; 수정=대상 용어 기존 role_key 보존, legacy null→'*'). ③ `_metaRenderForm` 에 읽기전용 '등록 대상 역할' 배지(id `metadataRoleContextBadge`)+노트(id `metadataRoleContextNote`). ④ `_metaUpdateGlossaryRoleBadge()` — 폼 재렌더(입력 소실) 없이 배지/노트만 동기화. ⑤ 툴바 `metadataRoleFilter` change 핸들러가 배지 동기화 호출. ⑥ `_metaSubmitForm` payload.role_key 를 헬퍼로 주입 + 성공 토스트에 대상 역할 표기.
- 변경(`src/static/admin.html`): 역할 필터 `<label>`/`<select>` 의 aria-label·title 을 "목록 필터 + 신규 용어 등록 대상 역할"로 명확화 + admin.js cache-buster `?v=20260629-glossary-review-nest` → `?v=20260629-glossary-role-single-ui`.
- §18.8 적대 패널(2-lens) BLOCKING 2 흡수 후 재검증(VERDICT 클린): **F2** 등록/수정 성공 토스트 역할 표기(mis-scope 사후 인지) · **F5** 툴바 역할 변경 시 배지 stale 해소(표시값=실제 등록값, 입력 보존 확인). NIT 흡수: F1(‘전체 역할’ 보기 생성 시 공용 귀속 노트) · 로직 중복 헬퍼 일원화. 재검증 잔여 NIT 2(도달불가 dead-guard·라벨 미세 표기차)는 무해로 수용(REVIEW 기록).
- 비변경: 백엔드 라우트/검증·RBAC·DB 스키마/마이그·목록 역할 배지·유사어 패널·검토 큐 IA. **알려진 trade-off(F3)**: 폼 역할 select 제거로 기존 용어의 역할 이동(공용↔역할) 직접 편집 UI 소실(백엔드 PUT 은 계속 지원, glossary_relations 는 term id 종속이라 재등록 경로에선 미승계). 의도적 수용 — 사용자 표면화, 이동 필요 시 후속 전용 affordance.
- 검증: node --check(admin.js) PASS · §18.8 적대 패널 + BLOCKING 수정 재검증(클린) · Windows 브라우저(PB-0008) 라이브 렌더 · web 재배포 후 cache-buster·healthz.
- Rollback: admin.js 의 헬퍼·배지·토스트·payload 주입 revert + `_METADATA_FIELDS.glossary` 의 role_key roleselect 필드·렌더 블록·`_metaRoleOptions` 복원 + admin.html aria/title·cache-buster 복원. 데이터/스키마/RBAC 변경 0.
- Deploy: web 재빌드(정적 자산 — deploy_scope: included). ask-worker 무관(프런트 전용).
- Deploy & live-verify (2026-06-29, resume cycle-finalize): base drift(main 7-behind) 흡수 병합 38da578 → PR #465(CI test success) 머지(main 4f3d22c) → worktree/branch cleanup → **web 이미지만** 재빌드(e045ef4)·repo-web-1 recreate. 검증: healthz git_commit=4f3d22c·mysql/pg ok / baked+라이브 HTTPS serve `admin.js?v=20260629-glossary-role-single-ui` / baked admin.js `_metaGlossaryTargetRole` 존재. PB-0008 실 Windows 브라우저 시각검증은 admin 인증 화면이라 사용자 확인 권장(metadata-bootstrap precedent 동일). F0 repo-immutability escape(worktree finalize 완료, 357bf9f 동일 패턴 — post-deploy doc-only).
- Files: feature-0003 `src/static/{admin.js,admin.html}` · `docs/{TASK,REPORT,REVIEW,MODIFY}.md` · `docs/STATUS.md`.
- Cross-ref: 원본 TASK-20260629-glossary-conv-autoreg(역할 분리 코어) · TASK-20260629-glossary-review-nest(검토 큐 중첩) · 결함② role.read 권한 부여(코드 외, app.py:20402 게이트).
## CHG-20260629T143914-share-mermaid-responsive (TASK-20260629T143914-share-mermaid-responsive — 공유 대화 뷰 mermaid 렌더 + 전체 폭 반응형, Minor §12.3 — frontend render/CSS, anonymous 공유 노출면)
- Date: 2026-06-29
- Related Requirement: 사용자 요청(2026-06-29, feature-0013 후속) — ① 공유 대화에서도 flowchart(mermaid) 정상 렌더, ② 공유대화 고정폭(960px)→브라우저 전체 폭 반응형(넓은 답변 대응).
- Summary: feature-0013 의 mermaid 렌더를 익명 공유 대화 뷰에도 적용 + 공유 페이지 폭을 전체 폭 반응형으로.
- Files:
  - `src/static/mermaid-render.js` (신규) — mermaid 헬퍼 4종(enhanceMermaidBlocks/ensureMermaidInit/renderMermaidDiagrams/mermaidFallback)을 app.js 에서 **verbatim 추출**. 메인 UI(index.html/app.js)와 공유 뷰(share.html/share.js)의 단일 소스 — 특히 `securityLevel:'strict'` init 을 한 곳에만 둬 두 뷰 XSS posture 일원화.
  - `src/static/app.js` — 위 4함수 정의 제거(호출부 markdownToHtml·renderMessageContent 는 전역 함수로 유지) + 두 호출부에 `typeof` 가드(mermaid-render.js 미로드 방어 — NIT-1, share.js 와 동일 패턴). cache-buster `20260629b-feedback-id-space`→`20260629c-share-mermaid`.
  - `src/static/index.html` — mermaid-render.js 로드 추가(`mermaid.min.js → mermaid-render.js → app.js` 순).
  - `src/static/share.html` — `mermaid.min.js` + `mermaid-render.js` 로드 + share.css/share.js cache-buster `20260623-share-join`→`20260629-share-mermaid`.
  - `src/static/share.js` — `renderMarkdownContent` 에 `enhanceMermaidBlocks`(sanitize 이전) + `renderMermaidDiagrams`(innerHTML 이후) 연결. 미로드 시 `typeof` 가드 폴백(원문 코드블록 유지).
  - `src/static/share.css` — `.share-container` `max-width:960px`→`100%`(전체 폭 반응형, `padding: 24px clamp(16px,4vw,48px) 80px`) + `.share-message-content .mermaid-*` 컨테이너 규칙(styles.css 동형, share 토큰).
- Impact: 비파괴. DOMPurify 설정 무변경(전역 setConfig/addHook 없음, 무인자 sanitize) — XSS posture 메인과 동일. mermaid `securityLevel:'strict'` 단일 init(`_mermaidInited` 단일 전역). 넓은 요소(표/pre/mermaid)는 `overflow-x:auto` 로 컨테이너 내 스크롤(레이아웃 무파손).
- 적대 검증(§18.8 SUBAGENT security+correctness): **no BLOCKING** — 추출 byte-identical·로드 순서·fallback·반응형·회귀 전 항목 SAFE. NIT-1 적용, NIT-2 defer.
- Follow-up (NIT-2, 비-blocking): 공유 뷰가 다이어그램 없어도 3.3MB `mermaid.min.js` 로드(메인 UI 동일 패턴) — `language-mermaid` 존재 시 lazy-load 최적화 여지.
- Rollback: share.html 의 mermaid 2 script 제거 + share.js enhance/render 호출 제거 + share.css `max-width:960px` 복원. mermaid-render.js 는 메인 UI 가 계속 사용(유지).
- Deploy & live-verify (2026-06-29): commit cbd54f4 → main 통합(충돌 0) → PR #464 머지(main 37d58cc) → **web 이미지만** 재빌드·재기동(frontend-only, backend/스키마/migrate 무관, deploy_scope: included). 서버 서빙 확인(share.html: mermaid.min+mermaid-render+share.js?v=…-share-mermaid / index.html app.js?v=20260629c). **PB-0008 실 Windows Chrome**: 메인 뷰 flowchart SVG 무회귀(7501) + 공유 뷰 flowchart SVG(7637)·`.share-container` maxWidth=100% 전체 폭. healthz ok. 증적 `artifacts/pb0008-share-mermaid-responsive.png`.

## CHG-20260629T144600-share-mermaid-responsive-deploy-record (TASK-20260629T143914-share-mermaid-responsive — 배포 완료 docs 기록, doc-only)
- Date: 2026-06-29
- Summary: PR #464 머지 후 web 재배포 + PB-0008 검증 결과를 TASK/MODIFY/REVIEW 에 기록(배포-후 docs, 코드 무변경). F0 repo-immutability escape(worktree finalize 완료, f7dcb07 동일 패턴).
- Files: `docs/{TASK,MODIFY,REVIEW}.md`.
- Cross-ref: CHG-20260629T143914-share-mermaid-responsive(Deploy & live-verify) / REV-20260629T144600-share-mermaid-responsive-deploy.

## CHG-20260629T080500-new-conv-dedup (TASK-20260629T080500-new-conv-dedup — 새 대화 첫 전송 시 사이드바 대화 중복 제거, Minor §12.3 — frontend-only, backend/스키마/RBAC 무변경)
- Date: 2026-06-29
- Summary: "새 대화"에서 첫 요청 전송 시 좌측 사이드바에 in-flight placeholder(메시지 제목)와 optimistic 대화 항목('새 대화')이 동시 렌더돼 같은 대화가 2개로 보이던 중복을, optimistic 등재 전에 placeholder 를 원자적으로 제거하고 등재 키를 `title`→`topic` 으로 바로잡아 단일 항목으로 일원화.
- Root cause: `sendPrompt`(app.js) lazy-create early-cid 성공 경로가 실 cid 대화 항목을 `state.conversations` 에 unshift+render 하면서도 in-flight placeholder(`pendingConversationEntries[busyKey]`)를 `/api/ask` 응답(8421)까지 제거하지 않음 → early-cid 발급~응답 도착(실 LLM 응답 시간) 동안 placeholder + optimistic 항목 동시 표시. + optimistic 항목이 `buildCompactItem` 미인식 `title` 키로 등재돼 폴백 "새 대화" 로 표시(중복의 '새 대화' 출처). 다른 정리 경로(fallback·422·취소·실패)는 placeholder 를 delete 했으나 early-cid 성공 경로만 누락.
- Files:
  - `src/static/app.js` — (1) early-cid 발급 블록: optimistic unshift 전 `pendingConversationEntries.delete(busyKey)` 추가 + `title`→`topic` + `renderConversationList()` 를 find-guard 밖으로. (2) `/api/ask` 응답 fallback 블록: 동일 정합(8421 delete 멱등 보존). (3) 파일 첨부 lazy-create 경로(~7337) optimistic 등재 `title: "(파일 첨부 중)"`→`topic:`.
  - `src/static/index.html` — app.js cache-buster `?v=20260629c-share-mermaid`→`?v=20260629d-new-conv-dedup`(정적 자산 전파).
  - `tests/verify_new_conv_dedup.mjs` — 신규 회귀 가드(정적 불변식 + jsdom 실 `renderConversationList` 행위, 18 단언).
- Impact: 비파괴. backend/스키마/마이그/RBAC/credential 무변경. placeholder→실 항목 원자적 교체라 클릭 진입·진행상황 폴링은 실 cid 항목이 승계(activeConversationId=earlyCid, is-active 전이). closure-mismatch(send 도중 다른 새 대화 이동)는 가드 밖 8421 delete 가 그대로 정리.
- Rollback: app.js 3개 hunk 의 `delete(busyKey)`/`topic` 복원 + render 를 find-guard 안으로 + index.html cache-buster 복원.

## CHG-20260629T172122-diff-lineno-prefix-leak (TASK-20260629T172122-diff-lineno-prefix-leak — ```diff 답변의 누출된 `<N>→` 줄번호 prefix 정규화, Minor §12.3 — frontend render-only, backend/스키마/RBAC/LLM 경로 무변경)
- Date: 2026-06-29
- Origin: `/_dqa:conversation_audit` (대화 마찰 진단·수정·출하). 마찰 = `FR-diff-lineno-prefix-leak`(FRICTION_LEDGER). 진단 대화 `…356708b8`(topic "계정 연동 및 보상 일괄 수령 쿼리 구성"), assistant msg id 4058. 사용자 명시 보고: "diff 포맷 답변에서 비정상 line 표현".
- Summary: assistant 가 ```diff 코드블록 context 줄에 `45→\t…` 같은 줄번호+화살표 prefix 를 그대로 흘려보내면 웹 렌더러가 이를 코드 본문으로 표시해 줄 표현이 깨지던 것을, 렌더 시 누출 prefix(`^\s*\d+→`)를 떼고 떼어낸 실제 소스 줄번호로 gutter 를 동기화하도록 정규화.
- Root cause: agent_core `_number_file_lines`(feature-0002, TASK-0256e)가 첨부 본문 각 줄에 `<N>→` 줄번호 prefix 를 주입(모델이 실제 줄 인용·`@@` 헌크 작성용). 프롬프트(agent_core.py:770-778)가 "diff 안에 `<N>→` 금지"를 지시하나 **모델이 가끔 context 줄에 그대로 복사**(변경줄만 표준 `+`/`-`). 웹 렌더러 `buildDiffRows`(app.js·share.js)가 누출 prefix 를 정규화하지 않아 `diffLineClass`→diff-ctx·`stripDiffMarker` 미스트립 → `45→` 가 코드로 렌더(+ gutter 는 1-based 별도 계산). 레이어 L1↔L6(프롬프트 vs 모델 준수)가 L7(렌더러)에서 표면화. 재발경로=model limit → **렌더러를 결정론적 최후 방어선으로 봉인**(모델이 또 누출해도 매번 차단·기존 저장 메시지도 render-time 에 정상화).
- Files:
  - `src/static/app.js` — `buildDiffRows` context 분기에 누출 정규화: `/^\s*(\d+)→/` 매칭 시 prefix 제거 + 떼어낸 줄번호로 oldNo/newNo 동기화.
  - `src/static/share.js` — 동일 로직(공유 대화 뷰도 같은 `buildDiffRows` 복제본 보유 — diff 렌더는 app.js·share.js 이원화, mermaid 만 공용 추출됨).
  - `tests/verify_diff_lineno_leak.mjs` — 신규 회귀 가드(30 단언, Node18 순수): 실 누출 블록 정규화·실 줄번호 복원·clean diff(@@/1-based) 무변경·app.js↔share.js 정합.
- Impact: 비파괴. backend/스키마/마이그/RBAC/credential/LLM 경로 무변경. clean diff 는 정규식 미매칭 → 무변경(blast radius 0, 테스트로 증명). +/- 변경줄 미관여(누출은 verbatim context 줄에서만 발생). 누출 형식이 매우 구체적(자릿수+U+2192)이라 오매칭 시에도 손실은 gutter 숫자 cosmetic(코드/복사 무손상).
- 분리 표기(§정직): 코드/테스트로 "렌더러가 누출 prefix 를 떼고 정상 diff 를 만든다" 증명됨. "실제 사용자 화면에서 소멸" 은 배포 후 PB-0008 실 Windows 브라우저 실측 필요분(WSL headless 괴리).
- Deferred(cross-ref, 이번 batch 제외): agent_core 프롬프트 강화(feature-0002, Major·core LLM 경로)는 단일-feature 응집·저위험 유지를 위해 별도. 렌더러 봉인이 누출을 비가시화하므로 우선순위 낮음.
- Rollback: app.js·share.js `buildDiffRows` 의 `leakedNo` 분기 제거(기존 단일 `return ... stripDiffMarker(line)` 복원) + `tests/verify_diff_lineno_leak.mjs` 삭제.

## CHG-20260629T172122-diff-lineno-prefix-leak-deploy (TASK-20260629T172122-diff-lineno-prefix-leak — landing + web 재배포 + 라이브 검증, 코드 무변경 / post-deploy doc-record)
- Date: 2026-06-29
- Origin: `/_template:resume` — 원본 `/_dqa:conversation_audit` 세션이 commit `d75152f` 직후 session-limit 으로 중단된 작업을 추적·재개해 landing+배포 완수.
- Summary: 코드/스키마 무변경. CHG-20260629T172122-diff-lineno-prefix-leak 의 landing(push·PR·merge)·배포·라이브 검증만 기록.
- git 흐름: commit `d75152f` push → PR #467 → `cycle-finalize --pr 467`(gh pr merge --merge, main `60c0d45`→`5942a25`, clean FF·충돌 0, worktree+local+remote 브랜치 정리).
- Deploy (deploy_scope: included): frontend-only → **web 이미지만** 재빌드(`make dc-build SERVICE=web` GIT_COMMIT=`5942a25` 각인)·재기동(`docker compose up -d --no-deps --force-recreate web`, override HTTPS 종단 유지). backend/ask-worker 무변경 → 미재빌드.
- 라이브 검증: `GET /healthz`(HTTPS) git_commit=`5942a25`(live, baseline `f021f3d`→`5942a25`)·repo-web-1 healthy. 서빙 `index.html` `app.js?v=20260629e-diff-lineno-leak`. 서빙 `app.js` **byte-identical** to main(`diff -q` IDENTICAL — fix live). 단위 테스트 30/30 PASS.
- Impact: 비파괴(doc-record). 사용자 화면 실 소멸 시각검증(PB-0008 Windows-browser)은 WSL 미실행 — 사용자 확인 권장.
- Rollback: 해당 없음(doc-only). 배포 롤백 시 이전 web 이미지로 재기동.

## CHG-20260629T184726-metadata-bs-paging (TASK-20260629T184726-metadata-bs-paging — 스키마 골격 가져오기 결과 페이지네이션 + 여백 압축, Minor §12.3 — frontend render-only, backend/스키마/RBAC/LLM 경로 무변경)
- Date: 2026-06-29
- Origin: `/_template:entry` arg-given. 사용자 보고("테이블 설명 AI 자동완성 및 UI 버그 수정" 작업 중): 관리 콘솔 > 메타데이터 > 테이블 설명 > "스키마 골격 가져오기" — ① 테이블 多 시 세로 스크롤 과길이(페이징 필요) ② 여백 과다.
- Summary: 부트스트랩 골격 결과를 페이지(30개/쪽)로 분할해 대규모 스키마에서도 pane 세로 스크롤을 1페이지로 고정. 검색 필터와 합성(필터된 부분집합 위에서 페이징). 결과 행/컨트롤 영역 여백 압축.
- Root cause: 직전 `metadata-bs-collapse`(접힘 헤더+검색+모두펼치기) + `metadata-table-desc-fix`(내부 max-height 스크롤 박스 제거 → pane `overflow-y:auto` 위임)로 결과가 **테이블 수에 비례해 무한 세로 확장**. 접힌 한 줄 헤더라도 수백 개면 스크롤 과길이 — 페이징 레이어 부재가 근본. (내부 max-height 재도입은 그 fix 가 적발한 이중 스크롤/잘림 회귀를 되살리므로 금지 → 페이징이 올바른 대체.)
- Files:
  - `src/static/admin.js` — 상수 `META_BS_PAGE_SIZE=30`; `adminState.metadata.bootstrap.page` 상태. `_metaBootstrapApplyFilter` 재작성(필터 매칭 부분집합 → 현재 페이지 윈도우만 `display` 노출 + 카운트 라벨 페이지 범위화 + `_metaBootstrapRenderPager` 호출). 신규 `_metaBootstrapGoPage`(delta 이동·클램프 위임·scrollIntoView)·`_metaBootstrapRenderPager`(라벨/이전·다음 disabled, 1페이지뿐이면 바 숨김). `_metaBindBootstrap` 에 prev/next 바인딩 + 검색 input 에 page=0 리셋. `_metaBootstrapRenderResult` 가 fetch마다 page=0 리셋 + loading/빈 결과 분기에서 페이저 숨김.
  - `src/static/styles.css` — 컨트롤 영역(note/controls/status) 세로 여백 축소, 결과 gap `4px→3px`, 헤더 padding `8px 12px→6px 10px`, 본문 `0 12px 10px→0 10px 8px`, 컬럼 행 `4px 0→3px 0`. 페이저 스타일 `.admin-meta-bs-pager`/`.admin-meta-bs-page-btn`(disabled opacity)/`.admin-meta-bs-page-label` 신설.
  - `src/static/admin.html` — 결과 div↔저장 액션 사이에 `metadataBootstrapPager` 바(prev/`metadataBootstrapPageLabel`/next) 추가. cache-buster 2건 bump: `styles.css?v=20260629-metadata-bs-flexclip`→`?v=20260629-metadata-bs-paging`, `admin.js?v=20260629-glossary-role-fieldname-fix`→`?v=20260629-metadata-bs-paging`(정적 자산 전파 — 본 프로젝트 반복 회귀 벡터).
- Impact: 비파괴. backend/스키마/마이그/RBAC/credential/LLM 경로 무변경. **불변식 보존**: 가시성은 순수 `display` 토글 — 모든 테이블 블록은 항상 DOM 유지. 저장(`_metaBootstrapSave`)·AI 일괄(`_metaBootstrapAiFill`/`_metaBootstrapApplyDescriptions`)이 `querySelectorAll(".admin-meta-bs-table")` 로 전체 DOM 수집하는 로직 무변경 → off-page/비매칭 블록 입력값도 저장·AI채움(blast radius 0). 테이블 ≤30개면 페이저 숨김 = 기존 동작 동일.
- 분리 표기(§정직): `node --check`·id/클래스 정합·적대 패널로 "페이징이 가시성 윈도우이며 저장/AI 전체 수집 불변식 유지" 코드 검증. "실제 사용자 화면에서 스크롤 고정·여백 축소 체감"은 배포 후 PB-0008 실 Windows 브라우저 실측 필요분(WSL headless 괴리).
- Rollback: admin.js 의 페이징 추가분(상수·page 상태·3 신규/재작성 함수·바인딩) 제거 + `_metaBootstrapApplyFilter` 를 단순 필터 버전으로 복원 + styles.css 여백/페이저 hunk 복원 + admin.html 페이저 바 제거 + cache-buster 복원.

## CHG-20260630T005923-share-joinable-confirm-persist (TASK-20260630T005923-share-joinable-confirm-persist — 공유 '링크 생성' 참여 허용 확인 모달 + '참여 허용' 체크박스 대화별 영속(회귀 수정), Critical 인접 §12.3 — 인가/프라이버시 UX, frontend-only)
- Date: 2026-06-30
- Origin: `/_template:entry` arg-given. 사용자 요청 2건: (1) '대화 공유' '링크 생성' 클릭 후 참여 허용 여부를 먼저 확인하는 구조. (2) '공유' 화면에서 '이 링크로 대화 참여 허용' 체크박스 조절 후 재진입 시 상태 회귀 버그 수정.
- 설계 결정(AskUserQuestion): Q1=**항상 확인 모달**(생성 클릭 시 참여 허용/미허용 명시 확정), Q2=**대화별 localStorage 영속**(cid 키).
- Summary: (요청1) `openShareDialog` 의 '링크 생성' 클릭이 `confirmShareJoinable` 확인 모달('참여 허용 확인')을 거친 뒤에만 발급되도록 게이트 — joinable=true 가 받는 사람에게 대화 전체를 노출하는 비가역 동작이라 무심코 누른 생성으로 공개되지 않게 재확정. (요청2) '참여 허용' 체크박스가 매 진입 시 하드코딩 `checked` 로 회귀하던 것을, 대화별 localStorage(`mad.shareJoinablePrefs.v1`, cid→bool)에서 복원 + 토글/확정 즉시 영속하도록 수정. 통합 팝업·앵커 경로(`promptShareExpiry`) 동일 적용.
- Root cause(요청2): `openShareDialog`(app.js)·`promptShareExpiry` 가 owner 분기 체크박스를 `checked` 로 하드코딩 → 사용자가 끈 상태가 어디에도 저장되지 않아 재오픈 시 무조건 기본 ON 으로 복귀. 클라이언트 선호 영속(localStorage) 부재가 근본 — 같은 앱의 muted/notify/sendMode 선호는 이미 localStorage 로 영속하던 확립 패턴인데 joinable 만 누락.
- Files:
  - `src/static/app.js` — (1) 영속 헬퍼 `SHARE_JOINABLE_PREFS_LS_KEY`/`_loadShareJoinablePrefs`/`getShareJoinablePref(cid)`/`setShareJoinablePref(cid,joinable)` 신설(muted-convs 패턴 미러, cid→bool, 기본 ON=`!== false`, 손상값 `{}` 폴백). (2) 확인 모달 `confirmShareJoinable({initial,canAllow})` 신설(owner=취소/참여 없이 생성/참여 허용하고 생성, 비소유자=취소/생성 — '허용' 버튼 부재; 취소·Escape·backdrop·× 모두 cancelled; settled 가드; cleanup 리스너 해제). (3) `openShareDialog` 체크박스 초기값 `getShareJoinablePref(cid)` 복원·change 영속·'링크 생성' 핸들러에 confirm 게이트(`intended`→`confirmRes.joinable`→최종 `joinable = isOwner ? … : false`, 체크박스+pref 반영). (4) `promptShareExpiry` cid 파라미터·초기값 복원·change/확정 영속. (5) `createConversationShare` cid 전달 + 앵커 경로 스코프 주석.
  - `src/static/styles.css` — `.share-confirm-panel`/`.share-confirm-desc`/`.share-confirm-actions`(share-expiry 톤 동일).
  - `src/static/index.html` — app.js `20260629f-point-scroll-easeoutexpo`→`20260629g-share-joinable-confirm`, styles.css `20260629-metadata-bs-flexclip`→`20260629-share-joinable-confirm`(정적 자산 전파).
  - `src/static/release-notes-data.js` — 2026-06-29 블록에 항목 2건(참여 허용 확인 improved · 체크박스 상태 유지 fixed) + summary 갱신.
  - `tests/test_share_joinable_owner_guard.py` — 리팩터로 바뀐 3 assertion 을 인가 불변식 보존하며 갱신(f1 `intended`+최종 joinable 강제 false, f2 cid 파라미터, f3 cid 전달).
  - `tests/test_share_joinable_confirm_persist.py` — 신규 회귀 가드(P1~3 영속·C1~4 확인 게이트, 7 케이스).
- Impact: 비파괴. **backend/route/스키마/마이그/RBAC/credential/LLM 경로 무변경(app.py diff 0)**. owner-only joinable + 백엔드 403 게이트(`_conversation_owned_by_account`) authoritative 불변. 비소유자는 체크박스 disabled + change 리스너 미등록 + confirm 모달 '허용' 버튼 부재 + 최종 joinable 강제 false(triple-clamp). 영속은 체크박스 초기 표시만 — 발급은 항상 confirm 모달+owner 클램프 경유라 프라이버시 회귀 0.
- 검증: agent 이미지 pytest 공유 13/13 + feature-0003 전체 548 PASS(회귀 0), `node --check app.js` PASS. §18.8 적대 패널 2렌즈 각 5가설 REFUTED — 보안 SAFE(BLOCKING 0)·UX SOUND(BLOCKING 0). rebase: worktree 생성 후 main 8ae77ca→4359be5(metadata-bs-paging) 1커밋 전진 감지 → stash→reset origin/main→pop 으로 최신 main 위 재배치(충돌 0, app.js/index.html 무중첩, styles.css 영역 분리).
- 분리 표기(§정직): 코드/테스트/적대패널로 "확인 게이트·체크박스 영속·인가 불변식 보존" 검증. "실제 사용자 화면에서 확인 모달 노출·재진입 상태 유지 체감"은 배포 후 PB-0008 실 Windows 브라우저 실측 필요분(WSL headless 괴리).
- Rollback: app.js 의 (헬퍼 4함수·confirmShareJoinable·openShareDialog confirm 게이트·promptShareExpiry cid 영속·createConversationShare cid) 제거 + 체크박스 `checked` 하드코딩 복원 + styles.css `.share-confirm-*` 제거 + index.html cache-buster 복원 + 테스트 2파일 원복/삭제.

## CHG-20260630T011858-share-joinable-confirm-persist-deploy (TASK-20260630T005923-share-joinable-confirm-persist — landing + web 재배포 + 라이브 검증, 코드 무변경 / post-deploy doc-record)
- Date: 2026-06-30
- Summary: 코드/스키마 무변경. CHG-20260630T005923-share-joinable-confirm-persist 의 landing(PR·merge)·배포·라이브 검증만 기록.
- git 흐름: commit `2167cd0` push → PR #470 → `cycle-finalize --pr 470 --target-worktree …`(gh pr merge --merge, main `4359be5`→`557c3c9`, clean FF·충돌 0). worktree remove 가 sudo pytest 의 root 소유 `.pytest_cache`/`__pycache__` 로 1차 Permission denied → `sudo rm -rf` + `git worktree prune` + local/remote 브랜치 삭제로 정리 완료.
- Deploy (deploy_scope: included, FIRST_REQUEST.md 전역): frontend-only → **web 이미지만** 재빌드(`make dc-build SERVICE=web`, GIT_COMMIT=`557c3c9` 각인; compose v5.1.1 metadata-file race exit1 흡수)·재기동(`docker compose up -d --no-deps --force-recreate web`, override HTTPS 종단 유지). backend/ask-worker 무변경 → 미재빌드.
- 라이브 검증: `GET /healthz`(HTTPS) git_commit=`557c3c9`(live, baseline `4359be5`→`557c3c9`)·repo-web-1 healthy. 서빙 `index.html` → `app.js?v=20260629g-share-joinable-confirm`·`styles.css?v=20260629-share-joinable-confirm`. 서빙 `app.js` **byte-identical** to main(`diff -q` IDENTICAL — fix live), 서빙 `styles.css` `.share-confirm` 2건 반영.
- Impact: 비파괴(doc-record). 사용자 화면 실 체감(확인 모달·취소 중단·체크박스 재진입 유지)은 PB-0008 Windows-browser 미실행(WSL) — 사용자 확인 권장.
- Rollback: 해당 없음(doc-only). 배포 롤백 시 이전 web 이미지(`4359be5`)로 재기동.

## CHG-20260630T100802-metadata-bs-inline-desc (TASK-20260630T100802-metadata-bs-inline-desc — 테이블 설명 모드 결과 행 평면화 + 설명 입력 인라인, Minor §12.3 — frontend render-only, backend/route/RBAC/스키마/LLM 경로 무변경)
- Date: 2026-06-30
- Origin: `/_template:entry` arg-given. 직전 `metadata-bs-paging` 배포 후 사용자 후속 보고(스크린샷): 테이블 설명 모드 각 행의 이름↔상태 사이 **중앙 가로 여백이 과다** — 정리/효용화 요청.
- Summary: tables(테이블 설명) 모드 결과 행을 접힘 헤더(button+caret, 펼친 본문 안 입력)에서 **평면 행(div) + 중앙 인라인 설명 입력**으로 전환. 빈 여백을 입력란으로 전환하고 펼침 없이 바로 입력하게 해 클릭을 줄임. columns(컬럼 설명) 모드는 테이블당 컬럼 다수라 접힘 구조 유지.
- Files:
  - `src/static/admin.js` — `_metaBootstrapRenderResult` 의 tables 분기를 평면 행으로 재작성(`block.is-flat` + `.admin-meta-bs-row` div + 이름 span + `.admin-meta-bs-desc-inline` 인라인 입력[data-kind=table] + 힌트 span). caret/toggle/본문 미생성. columns 분기는 기존 접힘 헤더(caret+is-collapsed+컬럼 트리) 보존(내부 변수 `row`→`colRow` 정리만). filterbar 초기화에서 expand-all 가시성 `mode==='columns'` 게이트 + 저장 안내문구 모드별 분기.
  - `src/static/styles.css` — `.admin-meta-bs-row`(flex 비클릭 행, padding 5px 10px) + `.admin-meta-bs-table.is-flat .admin-meta-bs-table-name`(flex 0 1 auto·max-width 38%·nowrap·ellipsis·word-break normal) + `.admin-meta-bs-desc-inline`(flex 1 1 auto·min-width 120px) 신설. columns/페이저/접힘 규칙 무변경.
  - `src/static/admin.html` — cache-buster 2건 bump: `styles.css?v=20260629-metadata-bs-paging`→`?v=20260630-metadata-bs-inline-desc`, `admin.js?v=20260629-metadata-bs-paging`→`?v=20260630-metadata-bs-inline-desc`.
  - `tests/verify_metadata_bs_inline_desc.mjs`(신규, 21 단언) + `tests/verify_metadata_bs_paging.mjs`(cache-buster 단언 literal→동반-bump 불변식 견고화).
- Impact: 비파괴. backend/route/ask-worker/스키마/마이그/RBAC/credential/LLM 경로 무변경. **불변식 보존**: 인라인 입력이 `.admin-meta-bs-desc[data-kind='table']` 로 블록 내 존재 → 저장(`_metaBootstrapSave`)·AI 일괄(`_metaBootstrapApplyDescriptions`)·힌트(`_metaBootstrapUpdateHint`) 셀렉터·페이징 display 토글 전부 무변경 동작. columns 모드 접힘/펼침·"모두 펼치기" 회귀 0(columns 분기 보존, expand-all 은 columns 에서만 노출). 접근성: 이전 button-헤더에 입력을 넣을 뻔한 안티패턴 회피(평면 행은 div, 입력은 독립 — `aria-label` 부여).
- 분리 표기(§정직): `node --check`·정적/jsdom 행위 테스트·적대 패널로 "평면 행에서도 수집/힌트/페이징 불변식 유지, columns 무회귀" 코드 검증. "실 화면에서 인라인 입력 노출·중앙 여백 해소·바로 입력 UX"는 배포 후 PB-0008 실 Windows 브라우저 실측 필요분(WSL headless 괴리).
- Rollback: admin.js tables 분기를 접힘 헤더+본문 입력 구조로 복원 + filterbar expand-all 무조건 노출/안내문구 단일화 + styles.css 평면 행 3규칙 제거 + admin.html cache-buster 복원 + 신규 테스트 삭제·paging 테스트 cache-buster 단언 원복.

## CHG-20260630T103235-metadata-bs-inline-align (TASK-20260630T103235-metadata-bs-inline-align — 테이블 설명 인라인 입력란 행간 정렬, Minor §12.3 — CSS-only, JS/backend/RBAC/스키마 무변경)
- Date: 2026-06-30
- Origin: `/_template:entry` arg-given. `metadata-bs-inline-desc` 배포 후 사용자 후속 보고: `<DB명>.<테이블명>` 길이 차이로 이름 칸이 내용 너비를 먹어 입력란 시작 x·너비가 행마다 달라 들쭉날쭉.
- Summary: 평면 행의 이름 칸·힌트 칸을 고정 폭으로 두어 모든 행의 인라인 설명 입력란이 같은 x에서 시작·같은 너비·같은 우측 끝으로 정렬되게 함.
- Files:
  - `src/static/styles.css` — `.admin-meta-bs-table.is-flat .admin-meta-bs-table-name`: `flex:0 1 auto; max-width:38%` → `flex:0 0 clamp(180px,32%,340px)`(평면 행은 동일 폭 컨테이너라 32% 가 행마다 동일 px → 정렬; 초과 이름 ellipsis+title). `.admin-meta-bs-desc-inline`: `min-width:120px`→`min-width:0`(좁은 화면 정렬 유지). 신규 `.admin-meta-bs-table.is-flat .admin-meta-bs-hint`: `flex:0 0 5.5rem; margin-left:0; text-align:right`(입력란 우측 끝 정렬 + ○→● 전이 시 너비 불변).
  - `src/static/admin.html` — cache-buster 2건 bump `20260630-metadata-bs-inline-desc`→`20260630-metadata-bs-inline-align`.
  - `tests/verify_metadata_bs_inline_desc.mjs` — 정렬 단언 [A6-align](이름/힌트 고정 폭) 추가 + cache-buster 단언을 literal→동반-bump 불변식으로 견고화.
- Impact: 비파괴. CSS-only(JS/route/RBAC/스키마/LLM 0). `.is-flat` 스코프라 columns 모드(`.is-collapsed` 헤더, 동일 `.admin-meta-bs-table-name`/`-hint` 클래스) 무영향. clamp() 는 프로젝트 기존 사용(share.css). 정렬은 평면 행이 모두 동일 폭(블록 레벨 full-width) 컨테이너라는 점에 기반 — 32% 가 모든 행에서 동일 px 로 해석.
- 분리 표기(§정직): 테스트·CSS-lens 적대 패널로 "고정 폭 칸 정렬·columns 무회귀·좁은 화면 비overflow" 코드 검증. "실 화면에서 여러 길이 이름의 입력란 좌/우 끝 정렬 체감"은 배포 후 PB-0008 실 Windows 브라우저 실측 필요분(WSL headless 괴리).
- Rollback: styles.css 3규칙(이름 flex/ min-width, desc-inline min-width, hint flex/text-align)을 inline-desc 시점 값으로 복원 + admin.html cache-buster 복원 + 테스트 정렬 단언 제거.

## CHG-20260630T110910-metadata-ds-single-ui (TASK-20260630T110910-metadata-ds-single-ui — 메타데이터 패널 '데이터소스' 선택 UI 단일화, Major §12.3 — feature-0003 프론트 단독, backend/route/RBAC/스키마/엔드포인트 무변경)
- Date: 2026-06-30
- Origin: `/_template:entry` arg-given. 사용자: 관리 콘솔 > 메타데이터 > 테이블/컬럼 설명에서 '데이터소스' UI 가 '스키마 골격 가져오기'와 메타데이터 패널 양쪽에 동시 존재해 역할 혼란 → 각 역할 파악 후 단일 UI 정리 요청.
- Summary: 데이터소스 selector 2개(헤더 스코프 `#metadataScopeSelect` = 저장/조회 스코프, 부트스트랩 `#metadataBootstrapDs` = 스키마 introspection 소스) 중 **부트스트랩 전용 selector 를 폐기**하고 데이터소스를 헤더 스코프에서 상속. 두 selector 독립으로 인한 "스코프↔골격소스 불일치(B 골격을 A 스코프로 저장)" footgun 제거. 공용(common) 스코프는 실제 스키마 없어 부트스트랩 불가 → 관리 콘솔 list-detail `.admin-detail-empty` 컨벤션 정합 empty-state 안내(비활성 잔재/더미 컨트롤 없음).
- Files:
  - `src/static/admin.html` — 부트스트랩 `데이터소스 *` label/`#metadataBootstrapDs` select 제거. `#metadataBootstrapEmpty`(.admin-detail-empty + .admin-meta-bootstrap-empty, 공용 안내) + `#metadataBootstrapHead`(토글 숨김용 id) + 노트 문구를 "현재 스코프 데이터소스(`#metadataBootstrapDsName`)의 실제 스키마에서…"로 교체(읽기전용 상속 DS 표기). cache-buster 2건 `20260630-metadata-bs-inline-align`→`20260630-metadata-ds-single-ui`.
  - `src/static/admin.js` — `_metaBootstrapPopulateDs`(DS 드롭다운 채움) → `_metaBootstrapSyncToScopeDs(scopeDs)`(스코프 DS 상속·노트명 갱신·DS 변경 시 골격/스키마 리셋 후 `_metaBootstrapLoadSchemas` 재로드) 교체. `_metaSyncBootstrapVisibility` 재작성 — applicable(tables/columns+kb.ingest.manual) 후 `_metaScopeDatasourceKey()` 로 분기: 공용/미매칭=empty-state 만(head/body 숨김), 구체 DS=골격 컨트롤 노출 + 상속·재렌더. `_metaBindBootstrap` 의 `#metadataBootstrapDs` change 바인딩 블록 제거. `_metaBindControls` 의 스코프 change 핸들러에 `_metaSyncBootstrapVisibility()` 추가(스코프 변경 시 가시성·상속 DS·스키마 즉시 동기화).
  - `src/static/styles.css` — `.admin-meta-bootstrap-empty`(.admin-detail-empty 재사용 + padding 28px/line-height 1.55, `strong` 본문 톤) 신설.
  - `tests/verify_metadata_scope_single_ds.mjs`(신규, 14 단언 — DS selector/populate 부재, 상속 구조, 저장 scopeKey 불변식, cache-buster 동반 bump, empty-state CSS).
- Impact: 비파괴. backend/route/엔드포인트(`/api/admin/metadata/bootstrap*` 시그니처)/RBAC/스키마/마이그/LLM 무변경 — 부트스트랩은 여전히 `{datasource,schema}` 를 받되 datasource 출처만 별도 selector → 스코프로 변경. **불변식 보존**: `_metaBootstrapSave` 는 변함없이 `adminState.metadata.scopeKey` 로 저장, `bootstrap.datasource` 는 `_metaScopeDatasourceKey()`(기존에 부트스트랩 DS 옵션과 동일하게 `ds.key` 산출)로 동일 형식 값 → 백엔드 계약 동일. 부트스트랩이 구체 DS 스코프에서만 노출되므로 저장 스코프=골격 소스 항상 일치. tables↔columns 서브탭 전환 재렌더(metadata-bs-inline-desc), 공용 외 스코프 골격 보존 회귀 0.
- 분리 표기(§정직): `node --check`·정적 회귀 테스트(신규 14 + 기존 inline-desc 32)로 "중복 selector 제거·스코프 상속·저장 불변식·cache-buster 정합" 코드 검증. "실 화면에서 공용=empty-state 안내·구체 DS=단일 데이터소스 컨트롤·스코프 전환 시 골격 리셋·중복 UI 부재"는 배포 후 PB-0008 실 Windows 브라우저 실측 필요분(WSL headless 괴리).
- Rollback: admin.html 의 `데이터소스 *`/`#metadataBootstrapDs` 복원 + empty-state/head id/노트 원복, admin.js `_metaBootstrapSyncToScopeDs`→`_metaBootstrapPopulateDs` 복원 + 가시성 함수·DS 바인딩·스코프 핸들러 원복, styles.css 규칙 제거, cache-buster 원복, 신규 테스트 삭제.

## CHG-20260630T160000-metadata-list-detail (TASK-20260630T160000-metadata-list-detail — 메타데이터 패널 list-detail 2단 재구성, Major §12.3 — feature-0003 프론트 단독, backend/route/RBAC/스키마/엔드포인트 무변경)
- Date: 2026-06-30
- Origin: 사용자 — "메타데이터 UI 를 다른 카테고리(계정/제품/데이터소스/감사)처럼 한 항목 선택 후 우측에서 상세조정하는 형태로 재구성. 현재는 위/아래 스크롤이 잦다."
- Summary: 메타데이터 패널을 단일 컬럼 수직 스택(헤더→서브탭→부트스트랩→폼→목록, 행 '수정'이 폼으로 scrollIntoView 점프)에서 다른 관리 콘솔 카테고리와 동일한 **2단 list-detail** 로 재구성. 좌측 `.admin-list-col`(검색·카운트·목록) + 우측 `.admin-detail-col`(#metadataDetail: empty-state | 편집 폼 | 부트스트랩 일괄). 행 클릭=선택→우측 편집(폼 점프 제거). 각 컬럼 독립 스크롤로 단일 긴 스크롤 소멸.
- Files:
  - `src/static/admin.html` — 메타데이터 pane 을 `.admin-list-detail admin-meta-list-detail` 2단으로. 좌측: 검색(#metadataSearch)+카운트(#metadataCount, 헤더→list-head 이동)+목록(#metadataList). 우측 #metadataDetail: empty-state(#metadataDetailEmpty, 거버넌스 안내문 통합)+폼(#metadataForm, 초기 display:none)+부트스트랩(#metadataBootstrap). 헤더에 '+ 새 항목'(#metadataNewBtn), 좌측 툴바에 '스키마 골격 가져오기'(#metadataBootstrapOpenBtn). cache-buster 2건 `20260630-metadata-ds-single-ui`→`20260630-metadata-list-detail`.
  - `src/static/admin.js` — 상태에 `detailMode(empty|form|bootstrap)`·`selectedId`·`search` 추가. 코디네이터 `_metaRenderDetail()`(모드 유효성 보정 후 세 컨테이너 배타 가시성, form→_metaRenderForm·bootstrap→_metaSyncBootstrapVisibility 위임 + 상단 네비 동기화). 헬퍼 `_metaSyncListActive`(선택 .is-active)·`_metaSyncListToolbar`(버튼/검색 가시성)·`_metaItemMatchesSearch`(검색). `_metaStartEdit`=detailMode='form'+selectedId(scrollIntoView 제거). 행 클릭=선택(role=button·keydown target 게이트), 인라인 '수정' 버튼 폐기, 삭제/유사어 stopPropagation. 스코프/서브탭/2차보기 핸들러·init·_metaSubmitForm 성공·_metaDelete(편집중 항목 삭제 시 empty 리셋)를 코디네이터 경유로 갱신. '+ 새 항목'/'골격 가져오기'/검색 바인딩.
  - `src/static/styles.css` — 메타데이터 pane 을 단일 세로 스크롤 override 에서 제외(list-detail 내부 컬럼 독립 스크롤). `.admin-meta-form` 카드 chrome 제거(detail-col 가 카드). `.admin-meta-row[role=button]` 클릭 affordance + `.is-active` 선택 강조. `.admin-meta-detail-note`·`.admin-meta-bs-open.is-active` 신설.
  - `tests/verify_metadata_list_detail.mjs`(신규 33 — HTML 2단 구조/admin.js 코디네이터·선택·검색/CSS/ jsdom detailMode 배타 가시성 + MAJOR-2 keydown 게이트 + 삭제 리셋) + `verify_metadata_scope_single_ds.mjs` [B8] 갱신(스코프 핸들러 코디네이터 경유).
- Impact: 비파괴. backend/route/엔드포인트/RBAC/스키마/마이그/LLM 무변경 — CRUD·부트스트랩·검토 큐·유사어 데이터 경로 모두 기존 함수 재사용(폼/목록 렌더 위치만 list-detail 로 이동). 권한 게이트(kb.ingest.manual/kb.sample.curate/kb.glossary.curate) 보존. 검토 큐는 별도 렌더 경로 유지(검색 미적용, 우측 empty-state).
- §18.8 적대 frontend state-machine 패널(7가설): VERDICT **FIX-THEN-SHIP→SHIP**(BLOCKING 0). MAJOR-2(행 keydown 이 내부 버튼 키 입력에 이중 발화) 수정(target 게이트)+테스트 잠금. MAJOR-1(검색이 편집중 항목 필터 시 list↔detail 시각 desync)=진행중 편집 보존 의도로 수용·문서화. NIT-1(stale CSS 주석) 정리. 전 테스트 108→ 신규 33 + 기존 75 green.
- 분리 표기(§정직): 테스트·적대 패널로 "2단 구조·모드 배타 가시성·선택 wiring·검색·권한 게이트·이벤트 전파·회귀 0" 코드 검증. "실 화면에서 좌우 2단 렌더·행 선택→우측 편집·컬럼 독립 스크롤(짧은 viewport)·스크롤 점프 해소"는 배포 후 PB-0008 실 Windows 브라우저 실측 필요분(WSL headless 괴리).
- Rollback: admin.html 메타데이터 pane 을 단일 컬럼(폼→목록)으로 복원 + admin.js detailMode/코디네이터/헬퍼/핸들러 변경 원복(_metaRenderForm/_metaSyncBootstrapVisibility 직접 호출) + styles.css 단일 스크롤 override 에 metadata 복원·폼 카드 chrome 복원·행 선택 규칙 제거 + cache-buster 원복 + 신규 테스트 삭제·scope-single-ds [B8] 원복.

## CHG-20260630T230501-doc-sync-rn-2305 (TASK-20260630T230501-doc-sync-rn-2305 — 06-30 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 신규 '2026-06-30' 블록 10항목 prepend(기존 06-29 블록 11항목 보존) — [new admin] 관계도(그래프) 뷰 신규 · [improved admin] 그래프 자동정리·속도 · [improved admin] 스키마 설명 화면 list-detail 2단 · [improved admin] 데이터소스 선택 단일화 · [improved admin] 테이블 설명 인라인 입력 · [improved work] 관련 부분만 찾아 정확 답변 · [improved work] 질문 의도 이해·끈기 · [improved common] 무중단 업데이트 · [improved common] 안정성 개선 · [fixed admin] 스키마 가져오기 기존 설명 prefill. `generated` 2026-06-30 유지.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260630-rn-0630`→`?v=20260630b-rn-0630`.
- Verification: `node --check` PASS + vm 로드 generated/06-30 블록 10항목·스키마 정합. 사용자향 평이화(내부용어 0)·ULTRACODE 5-stream 적대 패널 과대표현 2건(그래프 엣지=0 '관계 따라가기' / 무중단 '주요 기능 멈추지 않음') 완화 반영.
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`.
- 사용자향 평이화: 내부 구현·feature-id·테이블/함수명·AGE/Cypher·마이그·cache-buster 내부 슬러그 비노출. 렌더 로직(`release-notes.js`) 무변경 — 데이터만. META(STATUS·wiki·SECURITY·RELEASE_NOTES)는 별도 commit.

## CHG-20260701T163000-graphview-render (TASK-20260701T163000-graphview-render — 관리콘솔 메타데이터 그래프 뷰 출력 이슈 3건, Major §12.3 — feature-0003 프론트 + feature-0002 백엔드 cross-cut)
- 변경:
  - **feature-0002 `src/modules/node_analysis.py`**: `get_scope_analysis_status(scope_key, node_keys=None)` 추가 — `node_analysis_jobs` node_key group_by + `bool_or(status='done')`/`bool_or(status IN ('pending','running'))` 집계로 `{done_keys, running_keys}` 반환. PG 미가용/예외 → None(코어 비차단). `node_keys` 지정 시 `ANY(%s)` 부분집합.
  - **feature-0003 `src/routers/admin_metadata.py`**: `GET /api/admin/metadata/graph/analyze/status?scope=` 추가(권한 kb.ingest.manual) — 위 함수 위임, PG 미가용 시 `{done_keys:[],running_keys:[],unavailable:true}` graceful. 기존 `/graph/analyze`·`/graph/analyze/node` 와 리터럴 경로 분리(shadow 없음).
  - **feature-0003 `src/static/admin.js`**: ①`_metaGraphSyncAnalysisMarkers(scope)` 신설 + `_metaGraphLoadRoots`/`_metaGraphSearch`/`_metaGraphExpand` 3경로에서 호출(로드/검색/확장 직후 마커 렌더-타임 적용, additive — 활성 폴 running set 미clobber). ②tap 핸들러 `isParent` 분기: 스키마 클러스터(`label==='Schema'||isCat`)→`_metaGraphShowClusterDetail`(+`_metaGraphRenderClusterDetail`), Table ERD-parent 는 일반 상세/확장으로 통과. ③`_metaGraphEnsureLabelLayer`/`_metaGraphSyncClusterLabels` 신설(클러스터명 HTML 오버레이, `cy.on('render')` rAF 동기화) + cytoscape 스타일에 `node:parent[isCat=1]`·`node[label='Schema']:parent` → `label:""`(native 라벨 숨김).
  - **feature-0003 `src/static/styles.css`**: `.admin-meta-graph-canvas{position:relative}` + `.admin-meta-graph-label-layer`(absolute inset-0 pointer-events:none z-index:3) + `.admin-meta-graph-cluster-label`(좌상단 좌정렬 nowrap 무 max-width·text-shadow 가독).
  - **feature-0003 `src/static/admin.html`**: cache-buster 2건 bump → `admin.js`·`styles.css?v=20260701-graphview-render`(js==css lockstep).
- Verification: `node --check admin.js` PASS · `py_compile` node_analysis.py/admin_metadata.py PASS · CSS brace balance OK. PB-0008 Windows-browser 라이브 실측(프리뷰 인젝션, https://localhost/admin, mssql-qa-idc 250노드/클러스터 50): ②클러스터 클릭→상세 '테이블(58)' · ③좌상단(box+10/+4px)·좌정렬·무잘림·zoom 재배치 PASS. ①백엔드 집계 실 KB PG 정합(done 335·active 183) + 프론트 배선·404 graceful — 마커 렌더 최종 확인은 실배포 후. 적대 코드리뷰 패널 REV-20260701T163000-graphview-render.
- Files: `unit/feature-0002-agent-core/src/modules/node_analysis.py`, `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py`, `unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}`, `unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,TEST,REVIEW}.md`.
- 무변경: RBAC 권한 코드(기존 kb.ingest.manual 재사용)·스키마/마이그·기존 엔드포인트·ask/worker 경로. cross-cut 백엔드 변경은 feature-0002 `docs/MODIFY.md`·feature-0016-metadata-graph `docs/TASK.md` 에도 상호참조.

## CHG-20260701T220000-graphview-webgl-labels (TASK-20260701T220000-graphview-webgl-labels — 클러스터명 오버레이 WebGL 렌더러 호환 수정, Minor §12.3 — feature-0003 프론트 단독, graphview-render 후속)
- 변경: `static/admin.js` — 클러스터명 오버레이 위치 동기화 이벤트 바인딩을 `cy.on("render", …)` 단일 → 렌더러 무관 코어 이벤트 `cy.on("render viewport resize layoutstop add remove", _lblSync)` + `cy.on("position drag free", "node", _lblSync)` 로 교체. `static/admin.html` — cache-buster 2건 bump `20260701-graphview-webgl-labels`(js==css).
- 근본원인: graphview-render(§18) 오버레이가 `render` 이벤트에 의존했는데, 병렬 머지된 graph-webgl(§17, cytoscape 3.34.0 `webgl:true`) WebGL 렌더러는 `render` 를 emit 하지 않음(실측 renderFires=0) → 오버레이 라벨 미생성/미추종. 병합 번들 배포 전 PB-0008 프리뷰에서 적발.
- Verification: `node --check` PASS. PB-0008 Windows-browser 라이브(병합 번들 프리뷰, `webgl:true` 확인): 로드 시 labelDivs=35 · pan +120/+60 정확 추종 · 클러스터 tap 상세('테이블 130') · 좌상단 좌정렬 무잘림 — WebGL 하 전부 PASS. [SKIPPED:minor-scoped-fix] 패널(REV-20260701T220000-graphview-webgl-labels).
- Files: `static/admin.js`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,TEST,REVIEW}.md`.
- 무변경: 오버레이 sync 함수 로직(`_metaGraphSyncClusterLabels`)·마커·클러스터 상세·백엔드·RBAC·스키마. 이벤트 바인딩만 교체(렌더러 호환).

## CHG-20260701T100738-convswitch-opacity-guard (TASK-20260701T100738-convswitch-opacity-guard — 좌측 대화 선택 시 대화창 미표시 방어 하드닝, Minor §12.3 — feature-0003 프론트 단독, RBAC/스키마/백엔드/엔드포인트 무변경)
- 배경(사용자 보고 /_template:entry, 유저 admin): "작업 화면(메인 채팅)에서 좌측 대화 항목을 선택해도 대화창에 내용이 안 뜬다 — 선택이 아예 안 먹는 것처럼". 조사 결과 현재 배포본(b3175b6)은 백엔드(`/api/use_conversation`·`/api/history` 200 + 메시지 정상, curl 재현)·프론트(fresh 브라우저에서 admin 과 동일 role id3 계정 headless 10대화·race·PB-0008 Windows 모두 정상 렌더) 모두 재현 안 됨 → stale client(캐시된 구버전 app.js / 장시간 열어둔 탭) 유력. 사용자 결정: 재발 불가하도록 방어 하드닝 배포.
- 근본 취약점(코드 근거): `static/app.js` `selectConversation` 의 conv-switch-fade 는 `_beginConversationCrossfade()` 로 messageLog 를 opacity:0 으로 숨긴 뒤 `_commitConversationCrossfade()` 로 fade-in(opacity:1) 하는데, begin 과 commit 사이의 "risk window"(pendingNewConversation 리셋·pending 스냅샷·`stopProgressPolling`)가 try 밖에 있었다. 이 구간 예외 시 commit 미실행 → messageLog 가 opacity:0 잔류 → "대화창 빈 화면(=선택 안 먹는 것처럼)".
- 변경(`static/app.js`): risk window 를 try 안으로 이동 + 성공/catch 두 곳에 중복되던 `_commitConversationCrossfade()` 를 단일 `finally` 로 이관. 이제 begin 이 실행된 어떤 경로(정상 완료 / apiFetch·loadHistory 예외 / risk-window 예외)에서도 commit 이 정확히 1회 실행되어 opacity 복구가 구조적으로 보장. try/finally(catch 없음)라 에러는 기존 의미대로 호출부로 그대로 전파. post-processing(product hydration·jump·attachments·mark-read)은 여전히 성공 시에만 실행(구 rethrow 동형).
- 캐시버스터: `index.html` `app.js?v=20260629g-share-joinable-confirm`→`?v=20260701-convswitch-opacity-guard`(stale 사용자에게 새 코드 강제 전달 — 본 수정 목적과 정합).
- Verification: `node --check` PASS. §18.8 적대 코드리뷰(SUBAGENT adversarial-correctness) VERDICT PASS(commit 보장·에러 전파·_prevConvId scoping·post-processing·double-commit 불가·reduced-motion 대칭 6점). 프리뷰 인젝션(web-a/web-b `/app/web/static/`) 후 headless browse 5대화 전부 op1·렌더 + **PB-0008 Windows-browser 실측**(bootstrap_admin: 대화 A op1·msg4, A→B 전환 렌더·제목 갱신, 스크린샷 scratchpad/pb0008_convselect.png). REV-20260701T100738-convswitch-opacity-guard.
- Files: `unit/feature-0003-agent-web-ui/src/static/{app.js,index.html}`, `unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,TEST,REVIEW,REPORT}.md`.
- 무변경: selectConversation 외부 동작·happy-path 렌더 순서·크로스페이드 begin/commit 함수 본체·백엔드·RBAC·스키마·엔드포인트·다른 호출부(2554/9696/9777 fire-and-forget 그대로).
## CHG-20260702-graphview-webgl-polish (TASK-20260702-graphview-webgl-polish — 그래프 뷰 WebGL 외곽선 선명화 + 테이블 단일클릭 컬럼 인라인 토글, Minor §12.3 — feature-0003 프론트 단독, graphview-webgl-labels/graph-perf2 후속. 백엔드/RBAC/스키마/엔드포인트 무변경. /_template:resume 로 재개 완수)
- Date: 2026-07-02
- 배경: WebGL 렌더러(§17 graph-webgl) 배포 후 사용자 육안 후속 — (1) 줌인 시 노드/ERD 박스 외곽선·텍스트가 뭉개짐(WebGL sprite atlas 셀 해상도 초과 업스케일 블러), (2) 테이블 컬럼을 보려면 더블클릭 이웃확장에 딸려 나올 뿐 컬럼만 여닫는 단독 수단이 없음. 원본 세션(cfbede21)이 두 개선을 구현·라이브 검증했으나 계정 session-limit 로 (a) 접힘→재펼침 버그 미수정 (b) 리뷰/docs/랜딩 미완 상태로 중단 → `/_template:resume "관리 콘솔 그래프 뷰 노드 렌더링 및 표시 개선"` 으로 재개.
- Summary:
  - (1) WebGL 외곽선 선명화: `renderer:{name:"canvas",webgl:_webglOk}` → `renderer:{...,webglTexSize:4096}` + `pixelRatio:2`(**WebGL 경로에만**). WebGL 은 노드/박스를 sprite atlas 셀(기본 texSize 2048, 셀 ~113px)로 래스터 후 스케일 → 줌인 시 셀 해상도 초과분 블러. texSize 4096(셀 ~227px) + pixelRatio 2(2× DPI 래스터)로 외곽선/텍스트 선명. GPU 합성이라 프레임 비용 낮음(graph-webgl FPS 이득 유지).
  - (2) 단일클릭 컬럼 인라인 토글: 신규 `_metaGraphToggleColumns(key)`. 테이블 단일클릭 = 자신의 컬럼 펼침/접힘. tap 핸들러에 300ms 지연 타이머(`_colTimer`) — 더블클릭(이웃 확장 `_metaGraphExpand`)이 오면 취소(단일=컬럼 / 더블=관계 구분). 펼침: depth=1 그래프 컬럼(HAS_COLUMN) → 없으면 datasource information_schema introspect. 접힘: compound 자식 Column 제거.
  - (3) fix(접힘→재펼침 컬럼 미출현 — 재개 시 적발·수정): introspect 로 채운 컬럼은 그래프 DB 에 HAS_COLUMN 이 없어 재펼침 시 respHasCols=false. `introspected` Set 에 key 가 남으면 재조회가 skip 되어 컬럼이 다시 안 나옴 → collapse 분기에 `_metaGraph.introspected.delete(key)` 추가(단일·더블 introspect 경로가 Set 공유 → 정합).
  - (4) #519(graph-perf2) 정합: base 8커밋 stale — #519 가 컬럼 정렬을 fcose 제약→layoutstop 결정론 배치(`_metaGraphPlaceColumns`)로 이관. 병합 후 토글의 컬럼 seed 를 옛 3-wide grid → **부모 중심 세로 스택**(#519 방식·`_META_COL_PITCH`)으로 재정합. 컬럼 최종 배치는 `_metaGraphLayout` layoutstop 의 결정론 배치가 보장(seed 는 수렴 보험). 역할분리 주석도 정직화(#519 더블클릭도 미분석 테이블 컬럼 introspect — introspected/anchorHasCols 로 중복 회피).
- 캐시버스터: `admin.html` `admin.js?v=20260701-graph-perf2`→`?v=20260702-graphview-webgl-polish` + `styles.css?v=…-webgl-labels`→`?v=20260702-graphview-webgl-polish`(js==css lockstep).
- Files: `unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html}`, `unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW,REPORT}.md`.
- Verification: `node --check admin.js` PASS. origin/main(042613eb) ff 병합 후 stash pop 재적용 — admin.html 캐시버스터 충돌·admin.js 자동병합 해소, 실제 충돌 마커 0. §18.8 적대 패널(SUBAGENT adversarial-correctness) VERDICT PASS — BLOCKING 0, 축1~6(탭 타이머 경합·introspect Set 생명주기·컬럼 배치 정합·#519 회귀·WebGL config·self 재-add) 안전. NIT 1건(canvas-2D 폴백 `pixelRatio:1` 강제 → HiDPI 흐려짐 가시 회귀) 즉시 수정 — pixelRatio 를 WebGL 경로에만 부여, 폴백은 device DPR 보존. REV-20260702T000000-graphview-webgl-polish. PB-0008 Windows-browser 라이브 — 배포 후 사용자 실화면 확인 요망(그래프 인터랙션 자동화는 PB-0008 회귀 이력, 코드정합은 리뷰·node --check 확증).
- Impact: 프론트 전용·비파괴. 그래프 렌더 config(texSize/pixelRatio) + 입력 semantics(단일클릭 컬럼 토글) 추가. 백엔드/API(`/api/admin/metadata/graph[/columns]` 재사용)/데이터/스키마/RBAC 무변경. 배포=web 재빌드만.
- Rollback Notes: renderer 를 `{name:"canvas",webgl:_webglOk}` 로 환원(webglTexSize/pixelRatio 제거) + `_metaGraphToggleColumns` 함수·tap 핸들러 300ms 타이머 분기 제거 + 캐시버스터 환원(graph-perf2). DB/백엔드 무관.

## CHG-20260702-graph-panel-perms (TASK-20260702-graph-panel-perms — 그래프 뷰 UX 3건 + 메타데이터 탭 권한 세분화 B안, Major+Critical §12.3 — feature-0016 그래프 UX(feature-0003 코드 거주) + feature-0003 인가. /_template:entry arg-given, PLAN-APPROVED)
- Date: 2026-07-02
- 배경: 사용자 4건 요청(관리 콘솔 > 메타데이터). 그래프 뷰 3건(상세 패널 드래그 리사이즈·확장 테이블 접기 버튼·첫 컬럼명 미표시 버그) + 메타데이터 탭 권한 세분화. 착수 시 origin/main 이 worktree base(042613eb)보다 2커밋(#521 안 보임/#522 graphview-webgl-polish) 전진 — rebase(stash→ff to 344a5a80→pop). admin.js/admin.html 이 #522 와 겹쳤으나 다른 영역이라 git 3-way 자동병합(실 충돌 마커 0), 편집 마커 전량 잔존 확인.
- Summary:
  - **(Task1) 상세 패널 드래그 리사이즈**: `.admin-meta-graph-body` 를 2-col(고정 340px)→3-col(`minmax(0,1fr) 8px var(--meta-graph-detail-w,340px)`). 캔버스↔패널 사이 세로 리사이저 바(`#metadataGraphResizer`, role=separator, ←/→ 키보드). `_metaGraphInitResizer()`: pointerdown/move/up 으로 CSS var 갱신(왼쪽 드래그=패널 확대), clamp(패널 min240·캔버스 min360), localStorage `metaGraphDetailW` 영속, 놓을 때 cy.resize+fit(드래그 중엔 기존 ResizeObserver 가 debounce 처리). ≤900px(세로 스택)·detail-collapsed 시 리사이저 숨김.
  - **(Task2) 확장 테이블 접기 버튼**: 캔버스가 canvas/WebGL 이라 노드 네이티브 버튼 불가 → 스키마 클러스터 라벨과 동일 HTML 오버레이 레이어(pointer-events:none, 버튼만 auto) 재사용. `_metaGraphSyncCollapseButtons()`: 컬럼 자식 보유 Table 박스마다 `renderedBoundingBox` 우측하단(-20,-20)에 "−" 버튼, `_lblSync` rAF 에 연동(pan/zoom/drag/layout 추종), 줌아웃(<26px) 생략, orphan 정리. 클릭→`_metaGraphCollapse(key)`: 컬럼 자식+연결엣지 remove(부모는 leaf dot 노드로 환원) + `introspected` Set delete(재확장 시 재조회 허용).
  - **(Task3) 첫 컬럼명 미표시 버그**: `node:parent[label='Table']` 스타일 `text-margin-y:2`(박스 안쪽 최상단)→`-13`(박스 위로 띄움) + `text-background`(캔버스색 #fbfcfd chip, opacity .85). 기존엔 박스 안쪽 상단 타이틀이 최상단 컬럼 dot·라벨과 겹쳐 첫 컬럼명이 가려짐. 박스 padding·크기·fcose 간격 불변(레이아웃 회귀 없음).
  - **(Task4) 메타데이터 탭 권한 세분화(B안, Critical 인가)**: 단일 묶음 `kb.ingest.manual`(용어사전·ENUM·테이블·컬럼 편집 + 그래프 조회 + AI 분석 전부 게이트) → 기능별 `metadata.glossary.manage`/`metadata.enum.manage`/`metadata.table.manage`/`metadata.column.manage`/`metadata.graph.read` 5권한 분리(사용자 결정 B안). 하위호환은 **비파괴·가역 함의**: `_apply_permission_overrides`(전 principal 의 permission map 을 만드는 단일 중심 빌더 — backend enforcement + client can() 공통 소스)에서 effective map 이 `kb.ingest.manual` 을 가지면 5권한을 자동 True(개별 세부권한 DENY 오버라이드는 존중). `kb.ingest.manual` 은 catalog 에 "전체 묶음" umbrella 로 유지 → 기존 역할·계정 override grant 무손실(DB 마이그레이션 0). 백엔드 28 핸들러 require_permission 전환, 부트스트랩 3 엔드포인트=table.manage(테이블 골격 도구). graph.read 는 그래프 뷰 GET + 내장 AI 분석(analyze) 포함(그래프 뷰 기능 단위 = 1 권한).
  - **캐시버스터**: `admin.html` 의 `admin.js`/`styles.css` `?v=20260702-graphview-webgl-polish`→`?v=20260702-graph-panel-perms`(js==css lockstep, 정적 자산 전파 유일 메커니즘).
- Files: `unit/feature-0003-agent-web-ui/src/{app.py, routers/admin_metadata.py, static/admin.js, static/styles.css, static/admin.html}`, `unit/feature-0003-agent-web-ui/tests/{test_metadata_perm_split.py(신규), test_metadata_ai_autocomplete.py}`, `unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REPORT,REVIEW,TEST}.md`.
- Verification: `node --check admin.js` PASS · `py_compile` app.py/admin_metadata.py PASS · 신규 `test_metadata_perm_split.py` 9/9 + `test_metadata_ai_autocomplete.py`(fixture 세부권한 갱신) + `test_metadata_phase2.py`/`test_metadata_glossary_enum.py`(직접호출·console.access 음성 경로라 무회귀) + `test_permission_dependency_map.py`(group 기반 트리 — 신규 kb 권한 정합) PASS. 유일 실패 `test_route_parity_p5b`(192→193)는 **origin/main 344a5a80 기존 결함**(#520/#522 신규 route 의 golden 미갱신; 본 변경 route 무추가로 무관 — `git diff main` 에 @router/@app 데코레이터 추가 0 확인). §18.8 적대 패널 2 렌즈(authz + 그래프 프론트).
- Impact: 프론트(그래프 UX 3) + 인가(권한 세분화). 백엔드 enforcement 권한 코드 전환 + permission map 함의 추가. 데이터/스키마 무변경(권한 catalog seed 는 startup idempotent). 기존 `kb.ingest.manual` 보유자 접근 무손실(함의). 배포=web 이미지 재빌드.
- Rollback Notes: (Task1-3) admin.js/styles.css/admin.html 환원. (Task4) PERMISSION_DEFINITIONS 5권한 제거 + `_apply_permission_overrides` 함의 블록 제거 + admin_metadata.py 28 핸들러 kb.ingest.manual 환원 + `_METADATA_SUBTAB_PERM_SERVER`/admin.js 맵 환원. `kb.ingest.manual` catalog 유지라 기존 grant 그대로 동작(가역). DB 무변경이라 데이터 롤백 불요.

## CHG-20260701T230501-doc-sync-rn-0701 (TASK-20260701T230501-doc-sync-rn-0701 — 07-01 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 신규 '2026-07-01' 블록 7항목 prepend(기존 06-30 블록 10항목 보존) — [improved admin] 관계도 더 부드럽게·선명 · [new admin] 추정 관계 점선 표시(자기교정) · [new admin] AI 능동 분석 진행 현황 실시간 · [improved admin] 컬럼 실제순서 정렬+조작 편의 · [fixed admin] 관계도 표시 수정(묶음 이름·연결선·첫 컬럼명) · [new admin] 메타데이터 관리 권한 기능별 세분화 · [fixed work] 좌측 대화 선택 시 대화창 미표시 수정. `generated` 2026-06-30→2026-07-01.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260630b-rn-0630`→`?v=20260701-rn-0701`.
- Verification: `node --check` PASS + vm 로드 generated/07-01 블록 7항목·스키마 정합. 사용자향 평이화(내부용어 0: WebGL/Cytoscape/AGE/alembic/권한키 비노출). feature-0012 router 모듈화는 behavior-neutral 내부 리팩터라 user-facing 제외(정직 분류).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- 사용자향 평이화: 내부 구현·feature-id·테이블/함수명·렌더러/마이그·cache-buster 내부 슬러그 비노출. 렌더 로직(`release-notes.js`) 무변경 — 데이터만. META(STATUS·wiki·SECURITY·ARCHITECTURE·RELEASE_NOTES)는 별도 commit.

## CHG-20260702-metadata-perm-hier (TASK-20260702-metadata-perm-hier — 메타데이터(지식베이스) 권한 종속관계 정합화, Major §12.3 — feature-0003 프론트 단독, RBAC enforcement/스키마/백엔드/엔드포인트 무변경 · UI 표시 계층만)
- 트리거(사용자): "다른 권한 구성과 같이 종속적인 관계가 정합하도록 구성. `지식베이스 > 메타데이터` 권한이 다른 권한 포맷과 차이가 확인됨."
- 진단: `admin.js`의 `PERMISSION_DEPENDENCIES`(childCode→선행 parentCode, **UI progressive-disclosure 표시 계층** — authz enforcement 아님)에서, 관리 권한 다른 그룹은 전부 "그룹 게이트(read)→세부(manage)" 2단 계층(`account.read→console.access` + `account.*→account.read`; role/quota/datasource/product/audit 동형)인데 **메타데이터(kb 그룹)만 평면** — `metadata.{glossary,enum,table,column}.manage`·`metadata.graph.read` 5개가 전부 `console.access` 직속이고, 묶음 `kb.ingest.manual`은 맵에 부재해 게이트 없는 고아 root. → `_orderItemsAsTree`가 kb 그룹을 7개 flat 나열(타 그룹은 계층).
- 변경(정합화, B안 유지):
  - `static/admin.js` `PERMISSION_DEPENDENCIES`: `kb.ingest.manual`→`console.access`(다른 그룹 base 와 동형, 콘솔 게이트 하위) 추가 + 세부 5개 `metadata.*`→`kb.ingest.manual`(묶음 아래 nest). 결과 `console.access→kb.ingest.manual(묶음 게이트)→{용어사전·ENUM·테이블·컬럼·그래프뷰}` 2단 계층. `kb.sample.curate`는 별도 root 유지(다른 KB 기능).
  - 근거: 백엔드 `_METADATA_MANUAL_IMPLIES`로 묶음이 이미 5개를 함의(effective) → 묶음을 게이트로 삼는 게 의미 정합. **enforcement 무변경**(맵은 표시 전용, 백엔드 authz 는 parent→child 종속 미사용).
  - §18.8 NIT-1 흡수: `_applyPermissionDisclosure`에 `isGrantedForReach` 예측자 추가(explicit + override 상속-부여) → `_refreshGroupDisclosure`의 grantedCount·"N개 부여됨" cue 에 사용. 메타데이터를 게이트 하위로 옮기며, 역할이 개별 metadata.*를 (묶음 없이) 부여한 계정의 override 편집기 도달성 cue 회귀를 복원. checkbox(역할) 모드 무영향(inherited 비어 isExplicit 과 동일).
  - `static/admin.html`: cache-buster `admin.js?v=20260702-graph-panel-perms`→`?v=20260702-metadata-perm-hier`.
  - `tests/test_permission_dependency_map.py`: 신규 t5(계층 pin: metadata.*→kb.ingest.manual→console.access + 트리 depth manual=0·metadata.*=1) + t6(B안 개별부여 도달성: 게이트 OFF 시 metadata hidden 이나 묶음 root·kb.sample.curate 로 그룹 비은닉).
- Files: `static/admin.js`, `static/admin.html`, `tests/test_permission_dependency_map.py`, `docs/{TASK,MODIFY,REVIEW,REPORT}.md`.
- Impact: 관리 콘솔 역할/계정 권한 그리드에서 메타데이터 권한이 다른 그룹과 동일한 2단 계층으로 표시(묶음→세부). **비파괴** — authz enforcement·기존 grant·백엔드 함의 전부 불변. 개별 metadata.* 부여는 "세부 권한 더 보기"로 여전히 가능(B안 보존).
- 검증: `node --check` PASS, `test_permission_dependency_map.py` 18개(기존 16 + t5/t6) PASS, §18.8 SUBAGENT 패널 VERDICT PASS(BLOCKING 0 — 개별부여 회귀·은닉·enforcement·implies 상호작용 4축 refute; NIT-1 수정 반영·NIT-2 테스트 추가). 배포 후 라이브 그리드 계층 확인.
- Rollback: revert admin.js(맵 원복 + isGrantedForReach 제거) + admin.html(캐시버스터) + 테스트.

## CHG-20260702-aiops-panel (TASK-20260702-aiops-panel — AI 운영 관제 패널 + LLM 계측 확장, Major §12.3 — feature-0003 web/UI·인가 + cross-unit feature-0002 core/alembic + shared. /_template:resume 재개, PLAN-APPROVED)
- 변경(cross-unit — feature-0002 core/alembic, shared, feature-0003 web):
  - **feature-0002** `alembic/versions/20260702_0030_llm_usage_latency.py`(신규): PG `agent_runtime.llm_usage` 에 `latency_ms INTEGER`(nullable, DEFAULT 없음) `ADD COLUMN IF NOT EXISTS`(additive·idempotent, down=DROP IF EXISTS). down_revision=0029_node_analysis_relevance.
  - **feature-0002** `src/scripts/agent_runtime_schema.sql`: bootstrap `llm_usage` DDL 에 `latency_ms INTEGER` parity 추가(0002 resolved_model 관례).
  - **feature-0002** `src/modules/llm.py`: `_record_llm_usage` 에 `latency_ms:int|None=None` 인자 + INSERT 컬럼 추가(미전달=NULL → agent-core 11경로 byte-동치). 중앙 래퍼 `_openai_chat_completion_with_deadline` 순수 API 왕복(submit~result) latency 측정→전달.
  - **shared** `model_catalog.py`: `TASK_TAXONOMY`(14 task→6 category) + `taxonomy_for()`(미등록→`ai.other.unmapped` self-surface) + `ai_categories()` 추가.
  - **feature-0003** `src/app.py`: web 4경로 계측(프롬프트 자동생성 비스트리밍 16xx executor 람다 내부·스트리밍 produce() include_usage+choices 가드 앞 usage 선포착+SENTINEL 1회·자율 sweep daemon thread conv_id=None·메타 자동완성 executor 람다 metadata_ 접두). 권한 `console.aiops.read` PERMISSION_DEFINITIONS+admin catchup. `_ask_worker_age_sec` 헬퍼(3-state). `_DASHBOARD_WIDGETS` ai_ops + `_dash_widget_ai_ops`(tab='ai-ops'). `include_router(ai_ops)`.
  - **feature-0003** `src/routers/ai_ops.py`(신규): GET `/api/admin/ai-ops`(console.aiops.read) — 상태 축 worst-of 배너(inprocess ask-worker N/A 제외) + KPI + Attention + 카테고리 드릴다운 + 활동 feed + 커버리지. PG 부분 degrade(200, `_pg_connect_ro`).
  - **feature-0003** `src/routers/admin_console.py`: overview 에 `_isolate("ai_ops", …)` dispatch.
  - **feature-0003** `src/static/admin.html`: 감사 그룹 `data-admin-tab="ai-ops"` 탭 + pane(#aiOpsBody) + cache-buster css/js `?v=20260702-ai-ops`.
  - **feature-0003** `src/static/admin.js`: `PERMISSION_DEPENDENCIES`+`ADMIN_TAB_PERMISSIONS["ai-ops"]`(fail-open 방지) + `adminState.aiOps` + switchTab lazy-load + `loadAiOps`/`renderAiOps` + 새로고침 배선.
  - **feature-0003** `tests/test_permission_dependency_map.py`: v2 리스트에 console.aiops.read. `tests/test_ai_ops.py`(신규 10건).
- Verification: `tests/test_ai_ops.py` **10/10 PASS** + 회귀 permission 16/dashboard 20/usage 28 PASS, 전체 collection 무오류. py_compile(app.py·llm.py·model_catalog.py·ai_ops.py·admin_console.py·마이그·test) + node --check(admin.js) PASS. 적대검증 REV-20260702T140000-aiops-panel. PB-0008 Windows-browser= TEST.md.
- Files: `feature-0002/{alembic/versions/20260702_0030_llm_usage_latency.py, src/scripts/agent_runtime_schema.sql, src/modules/llm.py}`, `shared/model_catalog.py`, `feature-0003/{src/app.py, src/routers/ai_ops.py, src/routers/admin_console.py, src/static/admin.html, src/static/admin.js, tests/test_ai_ops.py, tests/test_permission_dependency_map.py, docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md}`.
- 계측 커버리지 정직성: 임베딩 3경로·provider probe 는 embeddings/ping 응답에 usage 부재 → 구조적 계측 불가로 '계측 커버리지' 각주에 미계측 명시('전체 비용' 오해 방지). cost 는 read-time 계산(단가표 web 전용) — DB 컬럼 미추가. 워커 프로세스 latency 는 web-only 배포로 미반영(quiet-time 워커 재빌드 후속).

## CHG-20260702-aiops-scroll (TASK-20260702-aiops-scroll — AI 운영 현황 pane 세로 스크롤, Minor §12.3 — feature-0003 프론트 CSS 단독, RBAC/스키마/백엔드/엔드포인트 무변경)
- 변경:
  - `static/styles.css`: pane 세로 스크롤 규칙(TASK-0167) 셀렉터에 `.admin-pane[data-admin-pane="ai-ops"].is-active` 추가 — dashboard/usage/release-notes 와 동일 `overflow-y:auto; overflow-x:hidden`. AI 운영 현황 pane 은 list-detail 아닌 단순 세로 흐름이라 admin-shell(overflow:hidden+100vh)에서 하단(카테고리표·커버리지) 잘림 → pane 자체 스크롤 필요.
  - `static/admin.html:7`: cache-buster `styles.css?v=20260702-graph-g6`→`?v=20260702-aiops-scroll`(CSS 실변경).
- Verification: CSS brace balanced(1701/1701). ai-ops 셀렉터 적용 확인. §18.8 [SKIPPED:minor-css-scroll]. PB-0008 Windows-browser 세로 스크롤 실측 = 배포 후(TEST.md).
- Files: `static/styles.css`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.

## CHG-20260702T021700-attach-count-scope (TASK-20260702T021700-attach-count-scope — "+" 메뉴 첨부파일 목록 개수 배지 대화 전환 후 잔류(stale) 수정, Minor §12.3 — feature-0003 프론트 단독, /_template:entry arg-given)
- 증상(사용자 보고): 어떤 대화에서 assistant 에 첨부 파일을 전달한 뒤 다른 대화창으로 전환해도, 요청 입력줄 "+" 메뉴의 "첨부파일 목록" 항목 우측 개수 배지(`#composerAttachCountBadge`)가 이전 대화의 첨부 개수를 그대로 표시. (오른쪽 첨부 사이드 패널은 "첨부 파일이 없습니다" 로 정상 — 배지만 stale.)
- 근본 원인: 배지 textContent 는 오직 `_renderAttachmentPills()` (app.js:7316, `:7344` clear / `:7349` set) 에서만 mutate 된다. 기존 대화 전환 `switchConversation`(app.js:5853) 은 `_loadConversationAttachments`(:5883)→`_renderAttachmentPills` 로 배지를 새 컨텍스트 기준 재렌더하지만, **다음 컨텍스트 진입/전환 경로들이 이 재렌더 훅을 누락**해 배지가 직전 대화 값으로 잔류:
  1. `beginPendingConversation()` (app.js:5907, "새 대화" 버튼) — activeConversationId="" + 새 pendingSentinel 부여 후 렌더하지만 배지 미갱신.
  2. `_switchToPendingConversationContext()` (app.js:5939, 사이드바 pending 대화 항목 클릭) — 동일 결함.
  3. **(적대검증 적발 갭)** `deleteConversation`(:6693)·`bulkDeleteConversations`(:5120)·`leaveConversation`(:6737) — 활성 대화 삭제/보관/나가기 후 `refreshWorkspace`→`loadConversations`→`loadHistory` 로 다른 대화(또는 빈 화면)에 랜딩. 이 경로는 switchConversation 을 거치지 않아 배지가 삭제된 대화 개수로 잔류(동일 stale class).
- 변경(`static/app.js`, 배지 재렌더 훅 4개 추가 — 신규 로직/상태/API/RBAC/스키마 0):
  - `beginPendingConversation` 의 `renderComposer()` 뒤 `_renderAttachmentPills()` 추가 → 새 대화 진입 시 빈 pendingSentinel bucket 기준 배지 비움.
  - `_switchToPendingConversationContext` 의 `renderComposer()` 뒤 `_renderAttachmentPills()` 추가 → 해당 sentinel 컨텍스트(stage 된 첨부 있으면 그 개수, 없으면 비움) 기준 재렌더.
  - `loadHistory()` 의 **빈 대화 early-return**(:5556-5564) 과 **정상 종료**(:5629) 두 exit 모두에 `_renderAttachmentPills()` 추가 → refreshWorkspace 계열(delete/bulk-delete/leave/empty)이 loadHistory 로 도달하는 모든 랜딩에서 배지를 현재 활성 대화 기준으로 정정. loadHistory 는 switchConversation·refreshWorkspace 공통 sink 이라 단일 지점으로 delete/leave 갭 전량 커버(switchConversation 은 직후 `_loadConversationAttachments` 가 서버 ground truth 로 재확정 — 무해한 선-렌더).
- 미변경(범위 봉인): `_renderAttachmentPills` 본체·`_composerAttachmentKey`·bucket 스키마·업로드/제거/전송 첨부 흐름·사이드 패널 개폐 정책(패널은 사용자 "+" 클릭 시에만 open — 본 재렌더는 empty 시 hide/repopulate 만 하고 강제 open 안 함) 전부 불변. logout(:8997) 잔류 배지는 auth 오버레이 뒤 비가시 + 재로그인 시 refreshWorkspace→loadHistory 로 자동 정정이라 별도 수정 안 함(MINOR, 적대검증 확인).
- 배포 전파: `index.html` `app.js?v=20260701-convswitch-opacity-guard`→`?v=20260702-attach-count-scope` bump(정적 자산은 `?v=` 가 유일 전파 메커니즘, baked 이미지 → web 재배포 시 반영). deploy_scope: included(FIRST_REQUEST 전역) — cycle-final 후 web 재배포.
- Files: `static/app.js`, `static/index.html`, `docs/{TASK,MODIFY,REVIEW,REPORT,TEST}.md`.
- 검증: `node --check app.js` PASS. §18.8 적대검증 REV-20260702T021700-attach-count-scope — VERDICT: MAJOR 1 적발(delete/leave 계열 갭) → **수정 반영 후 재검증 정합**, MINOR 1(logout, 비가시·자동정정 — 무수정 확인). PB-0008 Windows-browser = 배포 후 라이브(TEST.md §3, baked 자산·relay 라이브검증 사용자 실화면 필요 사유).
- Rollback: revert app.js(4개 `_renderAttachmentPills()` 호출 제거) + index.html(캐시버스터 원복).

## CHG-20260702-aiops-activity-paging (TASK-20260702-aiops-activity-paging — 활동 페이징 + main agent latency, Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002 core)
- 변경:
  - **feature-0002** `src/agent_core.py` `_call_llm`: create 직전 `time.perf_counter_ns()` → `_record_llm_usage(..., latency_ms=int((now-t0)//1e6))`. main agent 경로(LLM 볼륨 최대, task='agent')의 latency gap 보완. best-effort try/except 내(기존 예외격리 유지), 반환값·control flow 무변경.
  - **feature-0003** `src/routers/ai_ops.py`: `_query_activity(cur, taxonomy_for, *, cursor, limit)` keyset 헬퍼(`WHERE id < %s ORDER BY id DESC LIMIT n+1`, has_more=len>limit → next_cursor) + 신규 `GET /api/admin/ai-ops/activity`(console.aiops.read, cursor/limit 파라미터, `_pg_connect_ro` 부분 degrade) + overview 활동을 `_query_activity` 로 리팩터(created_at DESC → id DESC 등가) + `activity_next_cursor` 반환.
  - **feature-0003** `src/static/admin.js`: `aiOpsActivityRowsHtml`(초기+append 공용 esc row) + `loadAiOpsMoreActivity`(cursor append, insertAdjacentHTML, next_cursor 갱신/과거끝 disabled/에러 재시도) + renderAiOps '더 보기' 버튼(activity_next_cursor 있을 때) + body.innerHTML 후 배선.
  - **feature-0003** `src/static/admin.html`: cache-buster `admin.js?v=20260702-aiops-activity-paging`.
  - **feature-0003** `tests/route_snapshot_p5b.json`: 신규 activity 라우트로 194→195 재생성. `tests/test_ai_ops.py`: 신규 5건.
- Verification: `test_ai_ops.py` 15/15 + 회귀 66 PASS + collection 무오류. route-parity 195 PASS. node --check(admin.js). py_compile(agent_core·ai_ops). §18.8 REV-20260702T180000-aiops-activity-paging. PB-0008= 배포 후.
- Files: `feature-0002/src/agent_core.py`, `feature-0003/{src/routers/ai_ops.py, src/static/admin.js, src/static/admin.html, tests/route_snapshot_p5b.json, tests/test_ai_ops.py, docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md}`.
- keyset 선택 근거: OFFSET 은 대량 활동에서 성능·불안정(삽입 시 shift) → id BIGSERIAL 단조 keyset(`id < cursor`)로 안정 페이징. next_cursor=마지막 id(has_more 시), null=과거 끝.

## CHG-20260702T230501-doc-sync-rn-0702 (TASK-20260702T230501-doc-sync-rn-0702 — 07-02 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 신규 '2026-07-02' 블록 8항목 prepend(07-01 블록 7항목 보존) — [new admin] 관계도 항목 우클릭 상세·주변 관계 · [improved admin] 초기 진입 전체 구조 가시성 · [improved admin] 스키마 카드 우클릭 메뉴+검색 강조 · [fixed admin] 두 번 눌러 펼칠 때 부드러운 이동 · [fixed admin] 추정 관계 자동 다듬기 실동작 수정 · [new admin] AI 운영 현황 화면 신설 · [improved admin] 감사 화면 메뉴 정리+설명 · [fixed work] '+' 첨부 개수 배지 대화 전환 후 정확 표시. `generated` 2026-07-01→2026-07-02.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260701-rn-0701`→`?v=20260702-rn-0702`.
- Verification: `node --check` PASS + jsdom DOM 테스트 33 PASS(관리 62/작업 85/그룹 20 동적 카운트·XSS-safe)/1 pre-existing CSS FAIL(admin pane overflow-y, 무관). 사용자향 평이화(내부용어 0: G6/Cytoscape/WebGL/config/alembic/엔드포인트/권한키/모델명/ADR 비노출). feature-0012/0017 behavior-neutral 은 user-facing 제외(정직 분류).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- 사용자향 평이화: 내부 구현·feature-id·렌더러/마이그/엔드포인트/cache-buster 내부 슬러그 비노출. 렌더 로직(`release-notes.js`) 무변경 — 데이터만. META(STATUS·wiki·SECURITY·ARCHITECTURE·RELEASE_NOTES)는 별도 commit(REV-20260702T230501-META-0019-doc-sync-0702).
