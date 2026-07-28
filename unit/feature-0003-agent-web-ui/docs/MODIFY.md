---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---


# Modify Log

> 이전 기록(408건): [MODIFY-archive-20260711T115053.md](./_archive/MODIFY-archive-20260711T115053.md)

## CHG-20260728T114015-graph-edge-flow (TASK-20260728T114015-graph-edge-flow — 그래프 뷰 관계선 방향성 곡선 + 밀도 누적 + 부모 볼륨 다발, Major §12.3, frontend-only 3모듈)
- `src/static/graph/graph-renderer-pixi.js`: `PixiAdapterPure` 에 `edgeArc`(진행방향 왼쪽 고정 수직 오프셋 — 왕복 관계선 자동 분리)·`quadPoints`·`curveSegs`(화면 픽셀 기준 adaptive)·`dashPolyline`(폴리라인 전체 대시 위상 연속)·`strandOffsets` 신설, `hitTestEdge` 를 곡선 인지(zoom 인자 추가)로 확장. `_paintEdge` 재작성(실선=네이티브 `quadraticCurveTo`, 가닥별 개별 `stroke()` 로 겹침 alpha 누적, 끝 접선 화살촉+굵기 연동 크기, 곡선 중점 라벨), `_arrow` size 인자 추가, `_edgeStyleBetween` 신설 + `setHoverHighlight` 를 같은 호에 정합, `_lowFi`/`_lowFiTouched` 드래그 강등·`_flushEdgeRefresh` 고품질 복원, 모듈 상수 `EDGE_NO_STRAND`.
- `src/static/graph/graph-roleviz.js`: `_META_EDGE_CURVE/_MAX/_MIN` 상수 + `_metaEdgeStrands`(관계 수→가닥 log2 1~4) + `_metaEdgeFlow`(곡선·다발 키 주입 단일 축) 신설·export. `_metaEdgeStyleFor`(count 인자 추가, 굵기 1.4→0.85·1.8→1.05·3→1.5, `strokeOpacity` 0.32/0.5/0.62 신설, 기본색 `#cbd2db`→`#94a3b8`), `_metaRoutineEdgeStyle`(count 인자, 1.5→0.9/α0.42), `_metaSchemaRefEdgeStyle`(굵기 단독 → 다발 가닥 + 완만한 굵기·불투명도 + 가닥 수 비례 간격).
- `src/static/graph/graph-core.js`: ROUTINE_USES 집계 키에 `relation_type` 포함(`::RU::read|write`) + `agg.relType` 보존 → 읽기/쓰기 별개 관계선 방출·화살표 방향 유지(종전 `delete s.startArrow` 제거), 집계 굵기 가산(+0.8) 제거 후 `count`→가닥 위임, `data.relation_type` 노출, USES(제품→데이터소스) 사용선도 `_metaEdgeFlow` 로 통일, import 에 `_metaEdgeFlow` 추가.
- `tests/headless/test_graph_edge_flow.js` 신규(48건 — 곡선 기하 A1~A10 · 스타일 어휘 B1~B4/C0 · 빌드 계약 C1~C4).
- `tests/headless/test_g6build_edge_visibility.js` T1 계약 갱신(SCHEMA_REF 볼륨 인코딩: 굵기 단독 → 가닥 3 + 굵기·불투명도 동반 상승 + 곡률 부여).
- docs: TASK/REPORT/REVIEW/test-runs.d fragment.

## CHG-20260724T073848-conv-menu-order (TASK-20260724T073848-conv-menu-order — 대화 목록 '···' 확장 메뉴 항목 순서 변경, Minor §12.3, frontend-only)
- Date: 2026-07-24. `unit/feature-0003-agent-web-ui/src/static/app.js` `openConversationItemMenu` 단독 — '이동'(folder.manage.own 조건부) 블록을 '설정' append 앞으로 옮겨 렌더 순서를 `공유 → 설정 → 이동` 에서 `공유 → 이동 → 설정` 으로 변경. 헤더 주석 "최종 순서: 공유 | 설정" → "공유 | 이동 | 설정". 로직·권한·핸들러·action 인자 무변경 — 순수 순서.
- 영향: 대화 목록 각 항목의 '···' 확장 메뉴 항목 배열 순서만 변경. 백엔드·API·데이터·권한 무관. Cross-ref: TASK/REV-20260724T073848-conv-menu-order.

## CHG-20260724T033500-graph-emoji-color-postverify (TASK-20260724T031956-graph-emoji-color POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-24. 코드/자산 무변경 — TEST.md POST-DEPLOY 결과 append + TASK 체크박스 완료 + REVIEW postverify entry. 배포 PR #922 → main **c709ad3f**, `make deploy-web-only` 무중단 롤링(web-a/web-b·soak PASS·이미지 mysql-ai-web:c709ad3f·asset stamp 413567bad705).
- 라이브 실측(win-browser relay 실 Windows Chrome): 서빙 `/static/graph/graph-renderer-pixi.js` 에 `hasEmoji`·`!PixiAdapterPure.hasEmoji(text)` 게이트·emoji 폰트 스택 curl 확증. 버그 유발 조건(dark labelFill `#161b22` + emoji 폰트) canvas 2D fillText 프로브로 역할 아이콘 9종 chroma 측정: 📊217·💳255·📜75·📘177·📦214·🗂255 컬러 렌더, 👤·🔗·⚙️=0(Segoe UI Emoji 그레이스케일 디자인 이모지 — flat 실루엣 아닌 실 글리프). 9종 전부 flat 틴트 실루엣이 아닌 폰트 실 글리프 → "검은색 실루엣" 해소 확인. Cross-ref: REV-20260724T033500-graph-emoji-color-postverify · CHG/TASK-20260724T031956-graph-emoji-color · TEST Run(2026-07-24 graph-emoji-color POST-DEPLOY).

## CHG-20260724T031956-graph-emoji-color (TASK-20260724T031956-graph-emoji-color — 그래프 뷰 테이블 노드 역할 이모지가 검은색 실루엣으로만 렌더되던 버그 수정, Minor §12.3)
- Date: 2026-07-24. Files: `static/graph/graph-renderer-pixi.js`(수정) · `tests/headless/test_pixi_adapter.js`(T20b 추가). frontend-only, additive/비파괴(라벨 렌더 경로 분기만 추가, 데이터·API·RBAC·엔드포인트·레이아웃 0).
- 요청(사용자, `/_template:entry`): "그래프 뷰에서, 테이블 노드의 일부 이모지가 검은색 실루엣으로만 출력되는 이슈가 확인되어 수정이 필요합니다."
- 근본원인: 테이블 노드 라벨은 `graph-core.js` L700-703 에서 `_META_ROLE[role].icon + " " + name`(예 "📊 stats_daily") 로 조립. `graph-renderer-pixi.js` `_makeText` 가 기본 **BitmapText**(white-base glyph + `tint`=labelFill) 로 렌더 → BitmapText 는 dynamic font atlas 에 glyph 를 alpha 커버리지 단색 마스크로 래스터화 후 tint 를 곱하므로 **색 이모지의 색 채널이 소실**돼 labelFill 색의 단색 실루엣만 남음. `_META_ROLE` 의 `dark:true` 역할(stats/account/transaction/log/mapping)은 labelFill=`#161b22` → **검은색** 실루엣, `dark:false` 역할(master/config/etc)은 `#ffffff` → 흰색(옅게 비가시) — "일부만 검은색"의 원인.
- 변경: (1) `PixiAdapterPure.hasEmoji(text)` 순수 헬퍼 신설 — pictographic 블록(1F000-1FAFF)+Misc Symbols/Dingbats(2600-27BF, ⚙)+Misc Technical(2300-23FF)+Misc Symbols&Arrows(2B00-2BFF)+VS16(FE0F)+ZWJ(200D) 매칭. (2) `_makeText` BitmapText 게이트에 `&& !PixiAdapterPure.hasEmoji(text)` 추가 → 색 이모지 포함 라벨을 canvas `PIXI.Text` 로 강등(브라우저 색 이모지 폰트 네이티브 렌더). (3) Text 폴백 `fontFamily` 에 `'Segoe UI Emoji','Noto Color Emoji','Apple Color Emoji'` 명시 추가(per-glyph 폴백 확정).
- 설계 정합: 기존에도 tint 로 표현 불가한 색(비-hex rgb()/named)은 col.valid=false 로 Text 강등하는 seam(L189-190)이 존재 — 이모지도 "BitmapText 가 표현 못 하는 케이스"로 같은 seam에 편입(동형). 이모지 없는 대다수 라벨(컬럼·테이블명·−/+ 컨트롤)은 BitmapText 경로 유지 → §80 draw-call 최적화 보존(이모지는 분석 완료 테이블 칩에만 부착, bounded).
- 검증: `node --check --input-type=module` PASS · `tests/headless/test_pixi_adapter.js` **112 PASS / 0 FAIL**(기존 96 + T20b hasEmoji 16-assert) · §18.8 적대 리뷰 REV-20260724T031956-graph-emoji-color · CHECK#13 Windows-browser Run(PRE-COMMIT: PixiJS WebGL canvas 색 이모지 렌더는 headless 실측 정본 아님 — 배포 후 PB-0008 잔여, visual_verification_scope: always). Cross-ref: TASK/REV-20260724T031956-graph-emoji-color · TEST Run(2026-07-24 graph-emoji-color).

## CHG-20260724T140000-share-scroll-bottom-postverify (TASK-20260724T112446-share-scroll-bottom POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-24. 코드/자산 무변경 — test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료 + REPORT 갱신. 배포 PR #918 → main **94b4003a**, `make deploy-web-only` 무중단 롤링(web-a/web-b·90s soak PASS·이미지 mysql-ai-web:94b4003a).
- 라이브 실측(win-browser relay 실 Windows Chrome, 실 공유 링크 16-메시지 대화): **AC-SSB-1** 진입 `scrollY=53282==maxY`(scrollHeight 54118·innerHeight 836)·`atBottom=true` · **AC-SSB-3** `scrollTo(0,0)` 후 `stayedAtTop`(snap-back 없음, pin 정상 해제) · **AC-SSB-2** 최종 54118px 안착 · pageerror 0. 서빙 `/static/share.js`(47,901B) 신 심볼 5종 존재·dead window-load 리스너 소멸 curl 확증. Cross-ref: REV-20260724T140000-share-scroll-bottom-postverify · CHG-20260724T112446-share-scroll-bottom · TEST Run(2026-07-24 share-scroll-bottom POST-DEPLOY).

## CHG-20260724T112446-share-scroll-bottom (TASK-20260724T112446-share-scroll-bottom — 공유 대화 링크 화면 진입 시 문서 스크롤 맨 아래(최신 메시지) 고정, Minor §12.3)
- Date: 2026-07-24. Files: `static/share.js`(단일). frontend-only, additive/비파괴(진입 스크롤 위치 동작만 추가, 데이터·API·RBAC·엔드포인트 0).
- 요청(사용자, `/_template:entry`): "공유된 대화 링크 화면에 진입 시, 화면 스크롤이 가장 아래부터 위치하도록 구성해주세요."
- 변경: 초기 `fetchShare(token).then(render...)` 체인에 `engageInitialBottomPin()` 1회 호출 추가. 신설 함수 `scrollShareToBottom()`(문서 맨 아래로 `window.scrollTo(0, scrollHeight-innerHeight)`, 파일 내 기존 idiom L216-217/L388 과 동일 clamp), `engageInitialBottomPin()`(즉시 맨 아래 + 지연 콘텐츠 재고정 + 조작 시 해제), `releaseShareBottomPin()`(멱등 해제 — 리스너 remove + observer disconnect). 모듈 var `_shareBottomPinActive`/`_shareBottomPinObserver`.
- 지연 콘텐츠(마크다운 표·mermaid·이미지·point rail 비동기 렌더로 문서 높이 증가) 대응: `#shareMessages` `ResizeObserver` 재고정(미조작 동안), 미지원 시 `[150,400,1000,2500]ms`+`window load` 폴백(setupSharePointRail 동형 임계).
- 무회귀 보장: `pageBranchShare`(feature-0019 페이징 위치보존)·`scrollShareMessageIntoCenter`(rail 점프) 진입에서 `releaseShareBottomPin()` 선행 → 진입 pin 이 사용자/기존 로직 스크롤과 싸우지 않음. 3s 안전 타임아웃으로 이후 레이아웃 변화가 사용자를 끌어내리지 않게 자동 해제.
- 검증: `node --check` PASS · §18.8 적대 리뷰 REV-20260724T112446-share-scroll-bottom · CHECK#13 test-runs.d Windows-browser fragment(PRE-COMMIT PASS + POST-DEPLOY 라이브 계획, headless layout 부재로 스크롤 실측 불가 사유 기록). Cross-ref: TASK/REV-20260724T112446-share-scroll-bottom · TEST Run(2026-07-24 share-scroll-bottom).

## CHG-20260723T130200-conv-date-tree-postverify (TASK-20260723T034321-conv-date-tree POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-23. 코드/자산 무변경 — POST-DEPLOY 검증 원장 기록. 배포 PR #893 → main 0b15a0ea → `deploy-web.sh --web-only` 무중단(soak PASS·자산 스탬프 066695609710).
- 라이브 실측(win-browser Chrome 150, bootstrap_admin): 배포본 `_buildOwnDateTree` 합성 6/6(6월 단일·2025 연>월 중첩) + 실계정 사이드바 단일 "6월"[38]·"5월"[15]·중복 라벨 0(이전 ~10개 "6월" 소멸) + 6월 토글 4→42(배지 정확) + 스크린샷·pageerror 0. Cross-ref: REV-20260723T034321-conv-date-tree · TEST Run(conv-date-tree POST-DEPLOY).

## CHG-20260723T034321-conv-date-tree (TASK-20260723T034321-conv-date-tree — 좌측 대화목록 날짜 그룹핑 적응형 트리(월/년 집계)·"6월 중복" 시각 혼잡 해소, Major §12.3)
- Date: 2026-07-23. Files: `static/app.js`(+`_buildOwnDateTree` 신설·`_getDateGroupKey`/`_formatDateGroupLabel` 폐기·`renderConversationList` 재귀 트리 렌더러)·`static/styles.css`(`.conv-date-group-sub/-label/-count`). frontend-only, additive/비파괴(그룹핑 표현만 변경, 데이터·API·RBAC·엔드포인트 0).
- 변경: 오늘/어제·이번 달=일 노드, 올해 지난 달=월 노드(단일 — 이전엔 일 단위 키가 전부 "M월" 라벨로 중복 렌더돼 "6월/6월/6월" 혼잡), 지난 해=연 노드>월 서브노드(들여쓰기)>대화. 월/연 집계 노드에 대화 개수 배지. depth·collapse 모델(`state.collapsedDateGroups`)은 향후 대화 폴더 기능의 재사용 기반.
- 호환: collapse 키가 일 단위(YYYY-MM-DD, 매일 변경)→집계 단위(day:/month:YYYY-MM/year:YYYY, 안정)로 변경. localStorage 영속 키는 무해하게 stale(기존 값 미매칭 = 미접힘 = 기본 펼침, 회귀 아님). `_seedDateGroupsCollapsedOnce`가 매 로드 최근만 펼치는 기존 계약 유지.
- 검증: `node --check` PASS · 결정적 트리 단위테스트 4/4 PASS · POST-DEPLOY PB-0008 예정. Cross-ref: TASK-20260723T034321-conv-date-tree · REV-20260723T034321-conv-date-tree · TEST Run(2026-07-23 conv-date-tree).

## CHG-20260722T105320-share-menu-perm-wiring-postverify (TASK-20260722T103254-share-menu-perm-wiring POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-22. 코드/자산 무변경 — test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료 + evidence PNG. 배포 PR #885→main 066cec5e, `make deploy-web-only` 무중단(soak PASS).
- 라이브 실측(win-browser relay Chrome 150, bootstrap_admin 본인 대화 ☰): `여기까지 공유`·`여기부터 공유` 항목 `is-access-blocked` 없음(수정 전 항상 blocked 회귀 복구)·`여기부터 공유` 클릭 → onSelect 실행(비차단·오류토스트0)·floor arm 배너/마커 표시·pageerror 0. 서빙 app.js `action:"conversation.share.create"` 0매치. Cross-ref: REV-20260722T105320-share-menu-perm-wiring-postverify · CHG-20260722T103254-share-menu-perm-wiring.

## CHG-20260722T103254-share-menu-perm-wiring (TASK-20260722T103254-share-menu-perm-wiring — 말풍선 ☰ '여기까지/여기부터 공유' 권한 연결(action 매핑) 회귀 수정, Minor §12.3)
- Date: 2026-07-22. 사용자 신고: 대화 '여기부터/여기까지 분기'(말풍선 ☰ 여기서 분기·여기부터/여기까지 공유) 권한 연결 미작동.
- 근본원인: ☰ 메뉴 '여기까지 공유'/'여기부터 공유'(`openMessageBubbleMenu`)가 `make` 팩토리에 `action` 으로 **권한 코드** `"conversation.share.create"` 를 전달. `requiredPermissionsFor(action)`(app.js ~L589)는 **추상 action 이름**("conversation.share")만 switch 처리 → 미매칭 `default:{codes:[]}` → `markAccessBlocked` 가 `blocked=!hasAnyPermission([])=true` 로 두 항목을 **모든 로그인 사용자에게 항상 비활성**(is-access-blocked·클릭 시 onSelect 대신 오류 토스트) → ☰ 경로 공유(여기부터/여기까지) 완전 동작 불능.
- 변경: `static/app.js` **2줄** — 두 항목 `action: "conversation.share.create"` → `action: "conversation.share"`(conv-item '공유'가 이미 쓰는 정상 case). → codes `["conversation.share.create"]` 매핑 → `can()` display-permissive(로그인=true) → blocked=false → 정상 활성.
- 회귀 유입: `36ca1d4d`(2026-07-04 말풍선 ☰ 통합). 신규 항목이 conv-item '공유'의 추상 action 이름 대신 권한 코드 사용(ds-test-gate-fix `8e01cc24`/REV-20260716T051931 와 동형 프론트 게이트 배선 오류).
- 회귀 잠금: `tests/test_menu_action_permission_wiring.py` 신규 — 모든 메뉴 `action:` 이 requiredPermissionsFor 처리 case 인지 소스 파싱 검증(pre-fix FAIL·fixed PASS 실증).
- 비변경: 백엔드/스키마/RBAC/엔드포인트 shape 0(보안 posture 불변 — `create_conversation_share` 의 `conversation.share.create` 403·소유 IDOR 게이트 유지)·conv-item 메뉴·admin.js 무변경.
- **cache-buster 무변경**: 소스 `?v=dev` 고정(Dockerfile `inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트).
- 검증: `make test` 전체 GREEN(신규 3 PASS)·ruff PASS(첫 run 4 실패=`--no-deps` postgres-replica 레이스 flake·base main·재실행 RC=0 확증). 라이브=POST-DEPLOY PB-0008. Cross-ref: REV-20260722T103254-share-menu-perm-wiring · test-runs.d fragment 20260722T103254.
- Files: `static/app.js`, `tests/test_menu_action_permission_wiring.py`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md` + test-runs.d fragment.

## CHG-20260717T010501-doc-sync-rn-0717 (TASK-20260717T010501-doc-sync-rn-0717 — 07-16 후속 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 기존 releases[0] "2026-07-16" 블록 items 에 **fixed/work 항목 1개 추가**(작업 화면 데이터소스 ‘연결 테스트’ 버튼 미표시 회귀 복구) + summary 1문장 append. generated 07-16 유지·신규 dated 블록 미생성·releases 31 불변.
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0.
- 제외: redteam-rederive(PR #857, 내부·미배포)·ds-test-gate-fix POST-DEPLOY 기록(원천 cycle 소관).
- Verification: `node --check` PASS · vm 구조검증(31 releases·07-16 head 5항목[admin 4·work 1]·07-15 보존 7·스키마·누출0) · verify_release_notes.mjs 33/34(1 FAIL=styles.css pre-existing).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **무인 스케줄 run — landing/배포는 cron wrapper v3 소유(스킬 로컬 commit 만)**. META(SECURITY §22.4·wiki Log·meta/REVIEW)는 별도 commit.

## CHG-20260716T052500-ds-test-gate-fix-postverify (TASK-20260716T051931-ds-test-gate-fix POST-DEPLOY 회귀 복구 라이브 기록, 비-정책 doc-only)
- Date: 2026-07-16. 코드/자산 무변경 — test-runs.d POST-DEPLOY append + TASK 체크박스 완료. 배포 PR #855→main e6ca5e4b, `make deploy-web` 무중단(soak PASS).
- 라이브 실측(win-browser relay, bootstrap_admin): DS 테스트 버튼 14개 재렌더(수정 전 0)·클릭→"✓ 연결 성공 (13.6ms)" 상단 토스트·pageerror 0 → 사용자 신고 회귀 해소. Cross-ref: REV-20260716T052500-ds-test-gate-fix-postverify · CHG-20260716T051931-ds-test-gate-fix.

## CHG-20260716T051931-ds-test-gate-fix (TASK-20260716T051931-ds-test-gate-fix — 작업화면 데이터소스 '연결 테스트' 버튼 렌더 회귀 수정, Minor §12.3)
- Date: 2026-07-16. 사용자 신고(회귀): 07-13 출하 DS 테스트 버튼 미표시.
- 변경: `static/app.js` `buildProductDropupItem` `_dsTestable` 게이트 1줄 — `Boolean(state.user?.permissions?.["datasource.test"])` → `can("datasource.test")`. 근거: `state.user.permissions` 는 `/api/session` 미직렬화(TASK-0098 "표시 허용 + backend 403" 컨벤션)라 항상 undefined→false→버튼 미렌더. `can()` 은 display-permissive(로그인=true), 실제 거부는 백엔드 403(admin_test_datasource console.access+datasource.test). 순 게이트 = `!viewOnly && canOpenAdminConsole()`(07-13 동작 복구).
- 회귀 유입: perm-atomic-split `8e01cc24`(07-15 Critical) — datasource.test 원자 권한 신설 시 프론트 게이트를 부재 permissions 맵으로 작성.
- 비변경: 백엔드/스키마/RBAC/엔드포인트 shape 0(보안 posture 불변)·토스트·throttle·admin.js 무변경.
- 검증: `node --check` PASS · 회귀 하네스 short-circuit 무영향. 라이브=POST-DEPLOY PB-0008. Cross-ref: REV-20260716T051931-ds-test-gate-fix · test-runs.d fragment.
- 관련 flag: 동일 커밋 app.js ≈L2006 권한 표시 UI 도 `state.user.permissions` 의존(별도 feature 소유·본 scope 밖).

## CHG-20260716T120000-graph-search-groups-postverify (POST-DEPLOY 시각검증 정합 — docs-only, 코드 변경 0)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0003-graph-search-groups-postverify`(base main). CHG-20260716T114705-graph-search-panel-groups(PR #846 배포 89c1e7b0)의 POST-DEPLOY PB-0008 라이브 시각검증 결과를 원장에 정합.
- 변경: `docs/test-runs.d/20260716T1147-graph-search-panel-groups.md` Run 3 DEFERRED→**PASS**(라이브 실측 — 8 스키마→카테고리 2단 접기·모두 접기/펼치기 라벨 정합·검색 이력 뒤로/앞으로·verbose 부제 부재·pageerror 0) + verdict 갱신 + `docs/TASK.md` PB-0008 체크박스 [x]. **런타임 코드 무변경**.
- Rollback: 문서 revert. Deploy: 없음. Cross-ref: CHG-20260716T114705-graph-search-panel-groups / REV-20260716T120000-graph-search-groups-postverify.

## CHG-20260716T114705-graph-search-panel-groups (검색 결과 패널 3개선 — 2단 접기·검색 이력·설명문 간결화, Minor §12.3 프론트 단독·additive)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0003-graph-search-panel-groups`(base main). 사용자 요청(/_template:entry 후속): ①스키마 클러스터·컨텐츠 카테고리 단위 구분·정렬·접기/펼치기 ②뒤로/앞으로가 검색에도 유효 ③검색 설명문 TMI 간결화. TASK-20260716T013714(검색 결과 패널) 후속.
- **변경**: `src/static/graph/graph-ctxmenu.js`
  - **①2단 접기**: `_metaGraphRenderSearchResults` 전면 재작성 — 결과 노드를 `_metaSchemaComboOf`(스키마 클러스터)로 1차, `cluster_label`(컨텐츠 카테고리, 없으면 "카테고리 미분류")로 2차 그룹. 정렬: 스키마=매칭수↓→이름, 카테고리=수↓→이름(미분류 맨끝), 노드=유사도↓→이름. nested `.amgr-srch-sc`/`.amgr-srch-cat` 박스 + `is-collapsed` class(부모에 붙이면 CSS 가 body `display:none`). 각 헤딩(스키마·카테고리) role=button·caret·aria-expanded·Enter/Space 토글, 접힘 상태 `_metaGraph._searchGroupCollapsed`(Set, 키 `sc:<combo>`·`cat:<combo><label>` — `` 구분자로 경계 충돌 방지) 에 유지(재렌더·키스트로크 간 보존, 새 그룹 기본 펼침). "모두 접기/펼치기" 버튼(재렌더로 반영). 헤딩 시각은 기존 `.amgr-ct-group` 재사용. 행은 카테고리가 그룹 헤딩이 되어 per-row `카테고리:` meta 제거(중복 해소).
  - **②검색 이력**: 신규 `_metaGraphRecordSearch(q, nodes)` — 이력 top 이 `v:"search"` 면 in-place 갱신(키스트로크 항목 폭증 방지), 아니면 push(`{v:"search", k:q, nodes}`, 결과 캐시). `_metaGraphSearch` 가 렌더 직후 호출. 신규 `_metaGraphRestoreSearch(ent)` — 재fetch 없이 입력값만 세팅(input 이벤트 미발화=재검색 루프 없음) + 캐시 노드로 결과 재구성. `_metaGraphHistoryGo` 에 `ent.v==="search"` → `Promise.resolve(_metaGraphRestoreSearch)` 분기(search 의 `ent.k`=질의문자열이라 `_metaRenderedIdFor` 폴백·카메라 skip 자연 정합). **finding#5 해소**: 검색이 자기 이력 항목이 되어 스크롤 캡처(항상 현재 화면=현재 항목)가 정합 — 별도 마커 가드 불요.
  - **③설명문 간결화**: 상태줄을 `'${q}' — ${nRaw}건`(+ 상한/숨김필터 짧은 힌트만)으로 축약(기존 "카드 badge=매칭/전체… 앰버 글로우 확인" 제거), 결과 패널 부제 삭제, 행 `title`=fqn 만("클릭하면 이 노드 상세를 봅니다" 제거), 유사도 배지 title 제거.
  - `src/static/graph/graph.css`: `.amgr-srch-collapse-all`/`.amgr-srch-sc`/`.amgr-srch-cat` `is-collapsed` body 숨김/`.amgr-srch-subhead` 들여쓰기/`.amgr-srch-cat-none` 약화 표기/`.amgr-srch-cat-body` 노드 들여쓰기.
- Why: 대규모 검색 결과를 그래프 3층 구조 그대로 접어 훑고(스키마·카테고리 단위), 검색↔노드 상세를 이력으로 오가며, 설명문은 짧게 — 탐색 효율·일관성.
- Impact: 검색 결과 패널 렌더·검색 이력 항목만 확장. 노드/클러스터/관계 상세 이력·스크롤·캔버스 스키마 카드·글로우·백엔드/API 무변경. 캐시버스터 빌드 자동.
- Rollback: `_metaGraphRenderSearchResults` 재작성 revert + record/restore/Go 분기·상태줄·CSS revert. 다른 경로 영향 0.
- Deploy: web 재빌드(정적 자산 hash). alembic/백엔드 변경 없음.
- Cross-ref: CHG-20260716T013714-graph-search-detail-panel(원 기능·finding#5) · feature-0016(그래프 정본, graph-detail-scroll 이력·스크롤) · REV-20260716T114705-graph-search-panel-groups.

## CHG-20260716T015800-graph-search-detail-postverify (POST-DEPLOY 시각검증 정합 — docs-only, 코드 변경 0)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0003-graph-search-detail-postverify`(base main 03e8d1b0). CHG-20260716T013714-graph-search-detail-panel(PR #839 배포 완료) 의 POST-DEPLOY PB-0008 라이브 시각검증 결과를 원장에 정합.
- 변경: `docs/test-runs.d/20260716T0137-graph-search-detail-panel.md` Run 3 DEFERRED→**PASS**(win-browser.py 실 Windows Chrome 라이브 실측 — 코스튬 7건 AI 분석 배지·플루토스 28건 카테고리 배지+cluster_label+유사도 63%·행 클릭→노드 상세·클리어→뷰 해제·pageerror 0) + verdict 갱신 + `docs/TASK.md` PB-0008 체크박스 [x]. **런타임 코드·CSS·백엔드 무변경**(순수 검증 원장 정합).
- Rollback: 문서 revert. Deploy: 없음(docs-only). Cross-ref: CHG-20260716T013714-graph-search-detail-panel / REV-20260716T015800-graph-search-detail-postverify.

## CHG-20260716T013714-graph-search-detail-panel (그래프 뷰: 검색어 갱신 시 상세 패널에 검색 결과 리스트 구성, Minor §12.3 — 프론트 단독·additive; 그래프 정본 feature-0016)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0003-graph-search-detail-panel`(base main 0433efbb). 사용자 요청(/_template:entry 후속 turn): "검색어가 입력되었을 경우엔 상세 패널 내 검색 결과를 구성하도록 동작시켜주세요. 트리거는 '검색어 갱신 시'."
- **컨텍스트**: 직전 cycle(feature-0002 CHG-20260716-graph-search-content-match)로 `search_nodes` 가 이름/FQN 외 컨텐츠 카테고리(`semantic_cluster_label`)·AI 능동 분석(`node_analysis_jobs.analysis`)까지 매칭하고 노드에 `match_via`·`cluster_label`·`score` 를 실어 반환한다. 그래프 검색은 캔버스 앰버 글로우 + 스키마 카드 badge 로만 결과를 표기했는데, 검색 시 상세 패널에서 매칭 노드 목록을 바로 훑도록 결과 리스트를 상세 패널에 구성한다(프론트 렌더만 추가 — 백엔드 payload 이미 충분).
- **변경**: `src/static/graph/graph-ctxmenu.js`
  - 신규 `_metaGraphRenderSearchResults(nodes, q)`: `#metadataGraphDetailBody` 에 검색 결과 리스트 렌더. 행 = label 배지(`_META_GRAPH_COLOR`/`_META_LABEL_KO`) + 이름 + 유사도%(score>0) + **매칭 근거 배지**(match_via: 이름/카테고리/AI 분석) + 카테고리 라벨(category 매칭 시 cluster_label). 전 사용자/DB 유래 문자열 `esc()` HTML 이스케이프. 결과 0건 시 안내 메시지. 컨테이너 id `metaGraphSearchResults`(검색결과 뷰 판별 마커). 행 클릭/Enter/Space → `_metaGraphShowDetail(key)`(그 노드 상세 이동). role=button·tabindex 접근성.
  - `_metaGraphSearch` 2훅: (a) 비어있지 않은 q 는 `if (q !== _metaGraph.lastQuery) return` stale 가드 뒤에서 `_metaGraphRenderSearchResults(data.nodes, q)` 호출(검색어 갱신 트리거). (b) 클리어(빈 q) 시 상세 body 에 마커가 있으면(=검색결과 뷰) `_metaGraphRenderDetailEmpty()` 로 해제 — 사용자가 결과를 클릭해 노드 상세로 들어간 경우는 마커 부재라 보존.
  - `src/static/graph/graph.css`: `.amgr-searchlist`/`.amgr-searchres`/`.amgr-via`+`.amgr-via-{name,category,analysis}`/`.amgr-searchsub`/`.amgr-searchmeta` + `.amgr-row[data-goto]` cursor·hover. 카테고리 배지는 검색 글로우(#e8a400)와 동일 앰버 계열, 분석=블루, 이름=회색. 기존 `admin-meta-graph-card`/`amgr-row`/badge 토큰 재사용.
- Why: 검색 결과를 캔버스에서만 보던 것을 상세 패널에서 목록으로 훑고(매칭 근거·유사도 가시), 클릭으로 바로 상세 이동 — 검색→탐색 흐름 단축. 직전 백엔드 매칭 확장(카테고리·AI 분석)의 근거를 배지로 표면화해 "왜 매칭됐는지"도 노출.
- Impact: 검색 경로에만 상세 패널 렌더 1개 추가. 노드 상세/클러스터 상세/우클릭 메뉴·기존 글로우·카드 badge 무변경. 백엔드·API·스키마 무변경. 캐시버스터는 빌드 content-hash 자동 주입.
- Rollback: `_metaGraphRenderSearchResults` + 2훅 + graph.css 블록 revert. 다른 경로 영향 0.
- Deploy: web 재빌드(정적 자산 hash 재주입). alembic/백엔드 변경 없음.
- Cross-ref: feature-0002 CHG-20260716-graph-search-content-match(match_via/cluster_label/score 원천) · feature-0016-metadata-graph(그래프 뷰 정본) · REV-20260716T013714-graph-search-detail-panel · 병렬 세션 feature-0016-graph-detail-scroll(상세 패널 스크롤/history, 함수 영역 직교).

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
## CHG-20260715T231656-graph-edge-drag-perf (그래프 드래그 관계선 재그림 per-frame 부하 최적화 — 인접 인덱스 + in-place Graphics 재사용 + rAF 코얼레싱)
- Date: 2026-07-15. 계기: graph-edge-follow-drag(CHG-20260715T181939) 배포 후 사용자 실측 "관계선 추종은 정상이나 드래그 프레임당 재그림 부하 심함" → 후속 최적화.
- 병목(적대 리뷰 F1 확증): `_refreshIncidentEdges` 프레임마다 (a) `_built.edges` 전량 O(E) 스캔 (b) incident 엣지 `destroy({children})`+`new Graphics()` 재생성(GPU 지오메트리 재할당+GC). 허브/대형 스키마 드래그 시 프레임당 수백~수천 Graphics 폐기·재생성 + `_moveElement`↔`translateElementTo` 이중 호출.
- Changes(feature-0003, frontend-only 1파일 + 테스트):
  - `src/static/graph/graph-renderer-pixi.js`:
    - ① `_edgeIndex`(node→incident edge[]) `draw()` 구성(순수 `PixiAdapterPure.buildEdgeIndex` 추출)·`setData` 무효화 + `_incidentEdges(moved)` dedup 반환(O(incident), 폴백 O(E) filter). + **P3(적대 리뷰)**: 끝점 해소를 `_nodeById`(draw 구성·setData 무효화) 기반 `_resolvePos` O(1) 로 — `getElementPosition` O(N) `nodes.find` 제거(O(incident×N)→O(N+incident)).
    - ② `_paintEdge(g,e,a,b)`(clear+라벨자식 destroy 후 재-path) 신설, `_drawEdge`=`_paintEdge(new Graphics())` 위임(신규·full draw byte-동일). `_refreshIncidentEdges` 는 기존 엣지(`old.parent===world && typeof old.clear==='function'`) in-place 재사용, 신규만 `_drawEdge`+addChild.
    - ③ `_scheduleEdgeRefresh(movedIds)`(rAF 이동 id 누적→프레임당 1회 refresh+render, 비-rAF 동기 폴백) + `_flushEdgeRefresh`(dragend 즉시). `_moveElement`(양분기)·`translateElementTo` 가 `_refreshIncidentEdges`+`_render` 직접호출 대신 `_scheduleEdgeRefresh`. `_emitDrag` dragend flush, `destroy` rAF cancel. 노드 좌표·hit-grid 는 동기 유지.
  - `tests/headless/test_pixi_adapter.js`: T24 10종 + **T25 13종(적대 리뷰 C1~C4 실-경로 하드닝: 실 `_paintEdge` clear+stale라벨 destroy+재-path·순수 `buildEdgeIndex` 자기루프/null·재사용불가 else 분기·미해소 skip·`_resolvePos` O(1)/폴백)** + T23 회귀. ALL PASS 96/0.
- 정확성 불변: cross-category 추종(graph-edge-follow-drag OR 판정)·full draw() diff·_objSig 재사용 계약·zIndex 페인트 순서 유지. 라벨 엣지도 재사용 시 자식 destroy 후 재구성(stale 무).
- 비변경: 팬/줌·상태·미니맵·hover·우클릭·클릭·백엔드/RBAC/스키마 0.
- 검증: `node --check`(ESM) PASS · 헤드리스 96/0 · §18.8 적대 리뷰(결함 없음+지적 4건 반영) · POST-DEPLOY PB-0008 라이브(대형 스키마 드래그 프레임률·추종 정확성, 잔여).
- Cross-ref: TASK 20260715T2316 · REV/TEST-20260715T231656-graph-edge-drag-perf · test-runs.d/20260715T2316-graph-edge-drag-perf.md · 선행 CHG-20260715T181939-graph-edge-follow-drag · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## CHG-20260716T000000-graph-edge-drag-perf-postverify (그래프 드래그 관계선 재그림 최적화 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-16. CHG-20260715T231656-graph-edge-drag-perf(PR #832, main bfb1aa98) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- 실증(win-browser 실 Windows Chrome, 배포 bfb1aa98, PixiJS): P1(적대 리뷰) 반영해 pointerup 후 캡처. ① 추종 정확성 유지 — root 제품 카테고리 "건즈-개발·1" + gunzgame 409객체 dense-edge 테이블 드래그 모두 새 위치 관계선 추종·옛 위치 orphan 0. ② 부하 개선(정량) — gunzgame 40 pointermove 동기=30.4ms(0.76ms/move)·동기 burst 중 rAF 프레임 0(40 move 엣지 재그림이 단일 rAF 코얼레싱, 재사용-repaint). ③ dragend `_flushEdgeRefresh` 동기 반영·stale 0. ④ pageerror 0. 서빙 자산 baked(perf 함수 grep=11).
- Changes: `docs/test-runs.d/20260715T2316-graph-edge-drag-perf.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T231656-graph-edge-drag-perf · flake 선행수정 feature-0002 CHG-20260715T234757-probe-throttle-monotonic-flake(무관 CI red 해소) · ANCHOR 0003 무충돌.

## CHG-20260716T003901-graph-cluster-detail-collapse (스키마 클러스터 상세: 컨텐츠 카테고리별 접기/펼치기, Minor §12.3)
- Date: 2026-07-16. feature-0003 web/UI 프론트 단독(3파일). cluster-detail-fulllist(CHG-20260715T223744) 후속. 그래프 도메인 정본 feature-0016.
- 사용자 요청: 전체 출력 후속으로 상세 패널에서 컨텐츠 카테고리별 접기/펼치기 구성(긴 목록 탐색성).
- Changes:
  - `graph-state.js`: `_metaGraph.panelGroupCollapsed`(Set<sg.key>) 신설 — 접힌 컨텐츠 카테고리 유지(같은 클러스터 재렌더 간, 세션 한정).
  - `graph-ctxmenu.js` `_metaGraphRenderClusterDetail`: 그룹 헤딩=disclosure(`role=button`·`aria-expanded`·`data-group-key`·캐럿 ▾/▸, 초기 `panelGroupCollapsed` 반영) · `rowHTML(t,collapsed)`(행 `<li>` `amgr-ct-row-li`+접힘 시 `amgr-ct-collapsed`) · 섹션 헤더 '모두 접기/펼치기'(`#metaGraphCtCollapseAll`, 그룹 존재 시) · sgs 계산 h4 방출 전 이동 · 이벤트 위임 확장(`_toggleCtGroup` = 헤딩~다음 헤딩 전 멤버 행 토글+캐럿/aria/state 갱신; click 헤딩 분기 우선; keydown Enter/Space; 모두 접기/펼치기 로직).
  - `graph.css`: `.amgr-ct-group` cursor/hover/focus·`.amgr-ct-group-caret`·`li.amgr-ct-collapsed{display:none}`·`.amgr-ct-collapse-all`.
- 비변경: 전체 출력(캡)·집계/membership/hiddenKinds·행 클릭·hover·백엔드/RBAC/스키마 0. 순수 additive UI. cache-buster placeholder 수기편집 없음.
- 검증: `node --check`(2파일) PASS · CSS 균형(221:221·66:66) · §18.8 적대 리뷰 · POST-DEPLOY PB-0008(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260716T0039 · REV/TEST-20260716T003901-graph-cluster-detail-collapse · test-runs.d/20260716T0039-graph-cluster-detail-collapse.md · 선행 CHG-20260715T223744-graph-cluster-detail-fulllist · ANCHOR 0003 무충돌.

## CHG-20260716T005817-graph-cluster-detail-collapse-postverify (컨텐츠 카테고리 접기/펼치기 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-16. cluster-detail-collapse(CHG-20260716T003901, PR #835 main 00454608) 배포 후 win-browser PB-0008 라이브 실증. 코드 변경 0(문서 전용).
- 실증(실 Windows Chrome relay, 배포 00454608, 로그인 세션): 그래프 뷰 > mssql-dk-dev > dk_data_release_main(423항목·66 컨텐츠 카테고리) 상세에서 (1) 헤딩 클릭 접기/펼치기(NPC 콘텐츠 41행 표시↔display:none·캐럿 ▾↔▸·aria-expanded), (2) 모두 접기/펼치기 66그룹(라벨 "▾ 모두 접기"↔"▸ 모두 펼치기" 정합 — MINOR #1 수정 실증), (3) 재렌더 접힘 유지(접기→행 클릭 노드조회→뒤로→여전 접힘, panelGroupCollapsed sg.key 제어문자 포함 매칭), (4) 키보드 Enter/Space 토글, (5) 행 클릭 조회 불변·pageerror 0. 서빙 자산 baked(grep=10). evidence: collapse_evidence.png(▸ NPC 콘텐츠·▾ 퀘스트 시스템·▸ 성 시스템 공존 + 모두 접기 버튼).
- Changes: `docs/test-runs.d/20260716T0039-graph-cluster-detail-collapse.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260716T003901-graph-cluster-detail-collapse · ANCHOR 0003 무충돌.

## CHG-20260716T012805-graph-cluster-detail-group-hoverpan (스키마 클러스터 상세: 컨텐츠 카테고리 헤딩 hover 시 카메라 팬, Minor §12.3)
- Date: 2026-07-16. feature-0003 web/UI 프론트 단독(1파일). cluster-detail-collapse 후속. 그래프 도메인 정본 feature-0016.
- 사용자 요청: 상세 패널 다른 객체(행)처럼 컨텐츠 카테고리 헤딩 hover 시 해당 위치로 카메라 부드럽게 이동.
- Changes:
  - `src/static/graph/graph-ctxmenu.js` `_metaGraphRenderClusterDetail`:
    - 그룹 헤딩에 `data-pan-key = sg.tables[0].key`(그룹 **첫 멤버 노드 key**) — 행 hover-pan 과 동일하게 노드로 팬. 첫 멤버는 항상 실 노드라 진입경로(카드클릭 Local·콤보/히스토리 ById-API)·fam 정합에 무관하게 견고.
    - hover 이벤트 위임 확장: `_panTargetOf`(행 `data-node-key` **또는** 헤딩 `data-pan-key`) → `_metaGraphHoverPan`. mouseout/focusout 선택자에 `.amgr-ct-group[data-pan-key]` 추가.
- 설계 전환: 초판 타깃 = 캔버스 그룹 박스 `GB:comboId+SEP+fam`(fam 정합 확증). 단 §18.8 적대 리뷰가 콤보/히스토리-뒤로 경로(`ById`, API depth=1)의 API↔모델 집합 divergence 시 fam-불일치 caveat(graceful no-op) 지적 → **첫 멤버 노드 key 로 전환**해 근본 제거(노드 key 는 fam·경로 무관, 제어문자·String.fromCharCode 불필요).
- 비변경: 헤딩 클릭(접기/펼치기)·행 클릭 조회·행 hover-pan·collapse/전체출력·백엔드/RBAC/스키마 0. 순수 additive. cache-buster placeholder 수기편집 없음. 소스 리터럴 0x01 부재.
- 검증: `node --check` PASS · §18.8 적대 리뷰 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260716T0128 · REV/TEST-20260716T012805-graph-cluster-detail-group-hoverpan · test-runs.d/20260716T0128-graph-cluster-detail-group-hoverpan.md · 선행 CHG-20260716T003901-graph-cluster-detail-collapse · ANCHOR 0003 무충돌.

## CHG-20260716T015146-graph-cluster-detail-group-hoverpan-postverify (컨텐츠 카테고리 헤딩 hover-pan POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-16. cluster-detail-group-hoverpan(CHG-20260716T012805, PR #838 main d2c72fdc) 배포 후 win-browser PB-0008 라이브 실증. 코드 변경 0(문서 전용).
- 실증(실 Windows Chrome relay, 배포 d2c72fdc, 로그인 세션): DK dk_data_release_main(66 컨텐츠 카테고리) 상세에서 (1) 66 그룹 전부 `data-pan-key`=첫 멤버 노드 key("NPC 콘텐츠"→Combine 테이블·"게임 콘텐츠 조회"→P_CashItem_ReadBy_BackOffice 프로시저), (2) 헤딩 hover(200ms intent) → 카메라 부드럽게 팬: "NPC 콘텐츠"(TitleInfo·MerchantName 영역)↔"게임 콘텐츠 조회"(SetItem·spDeleteCollection 영역) 서로 다른 위치로 이동·미니맵 뷰포트 박스 이동, (3) 행 hover-pan·클릭 조회 불변·pageerror 0. 서빙 자산 baked(grep=8). evidence: hover_g0.png·hover_g45.png.
- Changes: `docs/test-runs.d/20260716T0128-graph-cluster-detail-group-hoverpan.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260716T012805-graph-cluster-detail-group-hoverpan · ANCHOR 0003 무충돌.

## CHG-20260716T010501-doc-sync-rn-0716 (TASK-20260716T010501-doc-sync-rn-0716 — 07-15~16 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases 배열 head 에 **date "2026-07-15" 새 블록 prepend**(7항목: admin 6·common 1)·summary 작성. generated 07-14→07-15. 기존 29 블록 보존(총 30).
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0. release-notes-data.js 내용 변경만으로 전역 content-hash 변화 → wrapper 재빌드 시 서빙 토큰 자동 갱신(수동 bump 부적용·해시 불변).
- 제외: 각 기능 *-postverify(배포 검증 기록)·#805 friction-ledger(내부)·probe/llm-probe 내부 안정성(⑥ 포괄)·feature-0021 red-team 백엔드(사용자 비가시 — 콘솔 'AI 추론' 표면만 노출).
- Verification: `node --check` PASS · vm 구조검증(30 releases·07-15 head 7항목[admin 6·common 1]·07-14 보존[10]·스키마·누출0). `verify_release_notes.mjs` 33/34 PASS(1 FAIL=styles.css scroll 정규식 brittleness·본 cycle 미변경·pristine HEAD 동일 재현·feature-0003 소관).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **landing/배포 소유=cron wrapper 위임**(로컬 commit 만·push/merge/deploy 미수행). META(wiki·SECURITY §23·meta/REVIEW)는 별도 commit(0cc64c2b, REV-20260716T010501-META-0037-doc-sync-0716).

## CHG-20260716T140735-doc-sync-rn-0716b (TASK-20260716T140735-doc-sync-rn-0716b — 07-16 낮 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases 배열 head 에 **date "2026-07-16" 새 블록 prepend**(4항목: admin 4)·summary 작성. generated 07-15→07-16. 기존 30 블록 보존(총 31).
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0.
- 제외: 각 *-postverify(배포 검증 기록)·guidance 권한 재배치 등 내부 권한 체계 변화(화면 체감은 ④ 서브탭 통합으로 포괄)·기본 프롬프트 fallback 목록 제외(내부 정리).
- Verification: `node --check` PASS · vm 구조검증(31 releases·07-16 head 4항목[admin 4]·07-15 보존[7]·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **attended run — landing/배포 스킬 소유**(분리 commit→PR→merge→deploy-web→서빙 검증). META(SECURITY §23 정정·wiki·meta/REVIEW)는 별도 commit. 직전 스케줄 잔재(0cc64c2b·eeabda19)는 rebase harvest.

## CHG-20260721T1758-realtime-progress-propagation (20260721T1758-realtime-progress-propagation — assistant 진행상황/답변 실시간 전파, Major §12.3, frontend-only)
- 계기: 사용자 신고 — 타 계정 대화 모니터링(또는 그룹 대화) 중 대화를 열어둔 관찰자에게 다른 사용자가 시작한 run 의 assistant 말풍선이 실시간으로 안 뜸(다른 대화 갔다 와야 표시).
- 근본원인: 진행상황 폴링(`pollProgress`)이 본인 `sendPrompt` / `loadHistory` 의 `last_status==processing` 감지 시에만 시작 → 유휴 관찰자에겐 새 run 을 감지할 배경 폴링 부재. 서버는 무결(`/api/progress`·`/api/history` 가 `conversation.read.any` 로 관찰자에게도 live 반환).
- 변경(`static/app.js`, +133): 유휴 run-감지 폴러 추가(활성 run 추적 없을 때 `/api/progress` client_run_id 없이 ~4s/숨김 15s 폴링 → 서버 run_id 가 baseline 과 달라지면 `loadHistory` 위임). `loadHistory`(유휴 arm/processing·no-conv stop, `!append`)·`selectConversation`·`handleLogout`·`visibilitychange` 배선. 감지 범위=모든 대화(사용자 선택). feature-0009 foreign-run 불변식 존중(활성 추적 중 dormant). 백엔드 무변경.
- 보안/인가 무영향: 감지·재로드는 기존 `/api/progress`·`/api/history`(read.own|read.any) 를 그대로 사용 — 새 권한 표면·데이터 노출 없음.
- Verification: `node --check` PASS · 유닛 `verify_run_detect_poll.mjs` 23/23 · feature-0003 pytest RC=0(무회귀) · 실 Windows 브라우저(Chrome 150) 유휴 탭 실시간 감지+"처리 중" 말풍선 렌더 실측+스크린샷(§16.6, TEST.md). 검증 후 라이브 배포본 원복.
- Files: `static/app.js`, `tests/verify_run_detect_poll.mjs`, `docs/{TASK,REPORT,TEST,FUNCTION,MODIFY,REVIEW}.md`.
- landing/배포: verify-completion(operational, feature-0003) → commit → push → PR/머지·배포는 자동 동기화 정책/wrapper 소유.

## CHG-20260722T010501-doc-sync-rn-0722 (TASK-20260722T010501-doc-sync-rn-0722 — 07-21 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` releases head 에 "2026-07-21" 블록 prepend(1항목 improved/work: 다른 참여자 질문에 대한 AI 답변 과정 실시간 표시·멀티탭 동기화) + generated 2026-07-16→2026-07-21. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + deploy-web.sh `asset_stamp_verify` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침).
- 근거 정본: feature-0003 TASK/REPORT realtime-progress-propagation(a999594e — 유휴 관찰자 run-감지) + git log 8f3dd00b..HEAD.
- Verification: `node --check` PASS · vm 구조검증(releases 수·07-21 head 1항목[improved/work]·07-16 보존·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260722T020408-msg-edit-textarea-contrast (20260722T020408-msg-edit-textarea-contrast — 메시지 '수정' 편집 UI 글자 비가시 수정 + 편집 폼 재구성, Minor §12.3, frontend-only 표시전용)
- 계기: 사용자 신고 — 보낸 요청 메시지를 '수정' 기능(단순 수정 / 요청사항 수정)으로 편집할 때 텍스트박스 배경색과 글자색이 같아 글자가 안 보임. "실제 사람이 사용할 수 있도록 UI 재구성" 요청.
- 근본원인: `.message-edit-textarea` 가 흰 배경(`var(--surface)`#fff)에 `color:inherit` — 편집 UI 가 삽입되는 파란 user 말풍선(`.message.is-user .message-bubble`, `color:#fff`)의 흰 글자색을 상속 → 흰 글자 on 흰 배경(대비 1:1) 비가시.
- 변경(`static/styles.css`): ① textarea `color:inherit`→`color:var(--text)`(#26251e) ② `.message-edit-box` `color:var(--text)` 상속 차단(방어) ③ `.message.is-user .message-bubble.message-bubble-editing`(특이도 0,4,0 — 파랑 0,3,0 을 이김) 신설로 편집 진입 시 파란 말풍선 → 중립 편집 패널(surface/border/shadow) 전환 ④ `::placeholder` 색·focus border 보강.
- 변경(`static/app.js` `_startInlineEdit`, +1행 +주석): `bubbleEl.classList.add("message-bubble-editing")`. 취소(renderMessages)/성공(refreshWorkspace) 재렌더 경로에서 말풍선 재생성되어 클래스 자동 소멸(제거 불필요).
- 보안/인가 무영향: 표시 계층만 — 편집 엔드포인트(`_submitMessageEdit`)·브랜치/IDOR 게이트·RBAC·스키마 0. `message-bubble-editing` 은 신규 unique 클래스(기존 `is-editing`(admin dashboard)·`.dashboard-widgets.is-editing` 와 선택자 분리·미충돌). feature-0019 ANCHOR §1-§3(브랜치 데이터 모델·INV-1~5) 무충돌.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — inject_asset_stamp.py 빌드 자동주입·deploy-web asset_stamp_verify 하드게이트, 수동 bump 폐지).
- Verification: `node --check` PASS · **headless Chromium 실측**(실 styles.css cascade) — 수정본 textarea 대비 15.38:1·편집 말풍선 파랑→중립전환·재답변버튼 5.17:1 / 수정 전 재현 1.0:1(버그 확인) · 스크린샷. **POST-DEPLOY PB-0008 Windows-browser 라이브 예정**(TEST.md CHECK#13, test-runs.d fragment).
- Files: `static/styles.css`, `static/app.js`, `docs/{TASK,REPORT,TEST,MODIFY,REVIEW}.md`, `docs/test-runs.d/20260722T020408-msg-edit-textarea-contrast.md`.
- landing/배포: verify-completion(feature-0003) → commit → push → PR/머지=자동 동기화 정책. **배포(`make deploy-web`)는 외부 영향 — 사용자 confirm**.

## CHG-20260722T024500-msg-edit-textarea-contrast-postverify (msg-edit-textarea-contrast POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY PB-0008 Windows-browser 라이브 실증 기록 append + TASK 체크박스 완료. 코드/자산 0 — test-runs.d fragment 20260722T020408 POST-DEPLOY 갱신 + TASK.md 박스.
- 배포본 main f7a14e9a(PR #866) — `deploy-web --web-only` 무중단(soak PASS). Windows Chrome 150 실측: textarea 대비 ~15.4:1(글자 판독)·편집 말풍선 중립 전환·재답변버튼 판독. 사용자 신고 해소 실증.
- Files: `docs/TASK.md`, `docs/test-runs.d/20260722T020408-msg-edit-textarea-contrast.md`, `docs/MODIFY.md`, `docs/REVIEW.md`.

## CHG-20260722T1252-point-rail-range-window (20260722T1252-point-rail-range-window — 대화 뷰 우측 미니맵 뱃지 범위화 + 클릭 위치 비례 스크롤 + 로그 윈도잉, Major §12.3, frontend-only additive)
- Files: `unit/feature-0003-agent-web-ui/src/static/app.js`, `unit/feature-0003-agent-web-ui/src/static/styles.css`.
- A(뱃지 범위화): `layoutMessagePointRail()` — `dot.style.top`(상단%) + `dot.style.height`(범위%) 막대 배치(logRect 루프 밖 1회 측정). CSS `.message-point-dot` 점(8×8 원)→막대(width 6px·min-height 4px·border-radius 3px·translateX만·is-active/hover 폭 11px).
- B(클릭 비례): rail 클릭 핸들러가 뱃지 내 클릭 y 비율 계산 → 신설 `scrollMessagePointToRatio(target, ratio)`(메시지 [top,bottom] 대응점을 뷰포트 중앙, EaseOutExpo). 기존 `scrollMessagePointIntoCenter`(항상 중앙) 유지 — 검색결과/앵커 점프 재사용.
- C(윈도잉): `loadHistory` conversation-generation 가드(`_loadGenConvId` — apiFetch 후 전환 시 bail, R1)·`_beginAppendScrollPreserve`/`_endAppendScrollPreserve`(prepend 후 scrollTop 보정, flag 無 — 예외 시 맨-아래 fallback)·`_fillInitialWindowSoon`(대화별 `_fillToken`·뷰포트 4배 목표·rAF·25p 상한, B1)·`_loadOlderGuarded`(자동/버튼 공용 단일 가드)·`_maybeAutoLoadOlder`(`_pointScrolling` 억제, R2)·`_animatePointScroll` `_pointScrolling` flag. `renderMessages` 맨-아래 스크롤 무변경(가드 flag 제거 재설계). scroll 리스너 + loadMoreBtn 배선.
- 검증: `node --check app.js` PASS · 적대 코드리뷰(REV subagent) R1/R2/B1 반영. 핵심 우려 preserveScroll leak = flag 제거로 moot 확인.
- landing/배포: verify-completion(feature-0003) → commit → push → PR/머지(자동 동기화) → `deploy-web`(deploy_scope: included, 외부영향 1줄 표면화) → POST-DEPLOY PB-0008.

## CHG-20260722T1355-point-rail-range-window-postverify (POST-DEPLOY 라이브 시각검증, 비-정책 doc-only)
- POST-DEPLOY PB-0008 Windows-browser 라이브 실증(배포본 22c3b9cb, PR #873). A(막대 범위화)·B(클릭 위치 비례) 라이브 PASS. C(윈도잉) 자동 페이징은 환경 대화 모두 20 메시지 미만(hasMoreHistory=false)이라 미트리거 — 코드/리뷰 검증 + 회귀 없음. gap: 20개 미만 대화 "4배 상한" 미적용(기존 서버 페이징 재사용 트레이드오프).
- Files: `docs/test-runs.d/20260722T125200-point-rail-range-window.md`(POST-DEPLOY append), `docs/test-runs.d/evidence/point-rail-range-window-live.png`, `docs/TASK.md`, `docs/MODIFY.md`.
- 코드/자산 변경 0.

## CHG-20260722T1420-point-rail-range-window-dom-windowing (윈도잉 강화 — 사용자 후속 요청, Major §12.3, frontend-only)
- Files: `unit/feature-0003-agent-web-ui/src/static/app.js`.
- C 강화: `state.renderCount` DOM 윈도잉. `_visibleMessages`·`_ensureMessageRendered`·`_applyRenderWindowSoon`(상한 렌더창 확대+하한 서버 페이징)·`_maybeExpandOrLoadOlder`(최상단 창 확장→서버 로드). `renderMessages`/`renderMessagePointRail` 이 최근 창만 렌더. `loadHistory` renderCount 관리(초기 8·floor 포함·append 확장). 검색/캘린더 점프 창 확장. `_windowBase` 절대 인덱스 복원.
- 적대리뷰(REV subagent) 발견1(절대idx)·2(floor 칩)·5(검색 optimistic id=null)·6(주석) 반영, 3(live-poll 슬라이딩)·4(연쇄 확장) known-limitation.
- 검증: `node --check app.js` PASS. POST-DEPLOY PB-0008 재검증 예정(conv[2] 일부만 로딩).

## CHG-20260722T1440-point-rail-window-initial-tuning (윈도잉 초기값 튜닝, frontend-only)
- Files: `unit/feature-0003-agent-web-ui/src/static/app.js` (`WINDOW_INITIAL_RENDER` 8→3).
- 라이브 실측(conv[2] 14개·개별 메시지 큼)에서 초기 8개가 높이 뷰포트 13배 → "4배만" 미달. 초기값을 낮춰 큰 메시지 대화도 4배 근처 유지. 짧은 메시지 대화는 상한 로직(`_applyRenderWindowSoon`)이 4배까지 채워 무손실. 로직 변경 없음(상수만).
- 검증: `node --check` PASS. POST-DEPLOY 재검증(conv[2] 초기 ~3개).

## CHG-20260722T1450-point-rail-windowing-postverify (POST-DEPLOY 윈도잉 재검증, 비-정책 doc-only)
- POST-DEPLOY PB-0008 라이브 재검증(배포본 66d1e735): conv[2](14개) 초기 3개 렌더·최상단 스크롤 확장(3→13→14)·뱃지 동기·A 막대 정상. 사용자 후속 요구 실증 완료. 코드/자산 0(스크린샷 evidence 추가).
- Files: `docs/test-runs.d/20260722T125200-point-rail-range-window.md`, `docs/test-runs.d/evidence/point-rail-windowing-live.png`, `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`.

## CHG-20260722T192736-history-top-indicator (대화 상단 '위에 더 있음' 페이드 신호, Minor §12.3, frontend-only 표시전용)
- Files: `unit/feature-0003-agent-web-ui/src/static/{index.html,styles.css,app.js}`.
- 위에 더 불러올 대화(윈도우 밖 renderCount<total 또는 서버 미로드 hasMoreHistory)가 있으면 messageLog 상단에 페이드 그라데이션만 표시(칩·텍스트·스피너 없음 — 사용자 결정: 최소 시각 신호). pointer-events:none(무방해)·rail 폭 제외. `_updateHistoryTopIndicator` 를 renderMessages 끝+empty 경로에서 호출.
- 백엔드/편집로직/RBAC/스키마 무영향. point-rail-range window(renderCount) 위에 얹은 순수 표시 레이어.
- 검증: `node --check` PASS. POST-DEPLOY PB-0008 예정.

## CHG-20260722T195000-history-top-indicator-postverify (POST-DEPLOY 라이브 검증, 비-정책 doc-only)
- POST-DEPLOY PB-0008 라이브 PASS(배포본 029927dc): 위에 더 있음→페이드 표시·전부 로드→숨김·짧은 대화→없음·pointer-events:none 무방해. 사용자 요구 실증. 코드 0(스크린샷 evidence 추가). 배포 초회 transient soak 롤백→재실행 remedy.
- Files: `docs/test-runs.d/20260722T192736-history-top-indicator.md`, `docs/test-runs.d/evidence/history-top-fade-live.png`, `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`.

## CHG-20260722T122635-shared-branch-readonly-paging (20260722T122635-shared-branch-readonly-paging — 공유/그룹·익명 공유-링크 뷰 편집 버전 읽기전용 페이징, Major §12.3, PLAN-APPROVED design-review C)
- 계기: 사용자 요청 — 공유 대화 + '링크 공유' 출력 화면에서도 편집 버전 `< n/m >` 페이징이 정합하게 동작하도록. 현재는 브랜치된 대화 공유 시 비활성 버전이 평면 노출됨(pager 없음).
- 방향(design-review C): 읽기전용 — active_leaf(공유 근거)를 바꾸지 않고 기존 브랜치 버전을 조회만. 새 재답변/영속 전환은 그룹에서 계속 잠금(INV-4 mutation lock 불변).
- 변경(`routers/_conv_store.py`, +189): `_branch_enrich_display`(두 로더 공용 active-path 필터+가시성-scoped 버전메타·읽기전용)·`_branch_version_groups(visible_pred)`·`_branch_window_pred`/`_branch_idrange_pred`(가시성 술어)·`_branch_resolve_readonly_leaf`(대상 검증+leaf, fail-closed)·`_branch_readonly_thread_ids`. `_get_history`/`_share_load_messages` 에 `override_active_leaf`(비영속). `_get_history` 그룹 enrich(이전 SEC MINOR-B skip 대체, window-scoped).
- 변경(`routers/conversations.py`,`routers/share.py`): `/api/history`·`public_share_view` 에 `branch_view` 파라미터 → resolver(멤버 window / 공유 [floor,anchor] 검증) → override. `app.py`: `_branch_resolve_readonly_leaf` re-export.
- 변경(프론트): `app.js`(그룹 `_pageBranch`→`loadHistory({branchView})` 읽기전용)·`share.js`(공유 뷰 pager+read-only nav)·`share.css`(pager 스타일).
- 보안(핵심): 가시 범위 밖 버전은 카운트·sibling_ids·존재·내용 모두 fail-closed 차단(window/id-범위 술어). active_leaf 불변(읽기전용).
- 비변경(회귀 0): has_branches=false 대화는 fast-path skip. 1:1 owner(window=None)는 `visible_pred=None`→전체(기존 페이징·`/branch/switch` 영속 불변). 백엔드 write/RBAC/스키마 0.
- Verification: `py_compile` 5 + `node --check` 2 · 보안 단위 10 PASS · §18.8 적대 보안 리뷰(REVIEW) · POST-DEPLOY 양 surface PB-0008.
- Files: `routers/{_conv_store,conversations,share}.py`, `app.py`, `static/{app.js,share.js,share.css}`, `tests/test_shared_branch_readonly_paging.py`, `docs/{TASK,MODIFY,FUNCTION,REPORT,TEST,REVIEW}.md`, `../feature-0019-message-editing/docs/ANCHOR.md`(INV-4 개정).
- landing/배포: verify-completion → commit → PR/머지=자동 동기화. 배포=외부 영향 confirm(이미 승인 범위).

## CHG-20260722T130000-shared-branch-readonly-paging-postverify (shared-branch-readonly-paging POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 배포·양 surface 라이브 검증 기록 + TASK 완료. 코드/자산 0.
- 배포: PR #887 → main 622b7434 → `deploy-web.sh --web-only`(soak PASS).
- 라이브(배포본 622b7434, 대화 20260722015229-79da15cb=group+active share): 공유-링크 익명 API — pager 메타·branch_view 읽기전용 전환·999999999 fail-closed. 인앱 그룹 인증 API — pager(window-scoped)·branch_view 전환·active_leaf 불변. Windows-browser 시각 미수행(브리지 다운, §15.4.1 escape — API 실측+단위 12 로 보완).
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/TEST.md`.

## CHG-20260723T010501-doc-sync-rn-0723 (TASK-20260723T010501-doc-sync-rn-0723 — 07-22 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` releases head 에 "2026-07-22" 블록 prepend(6항목 fixed/work 3·improved/work 3 — 재답변 후 내 메시지 소실 복구·'수정' 창 글자 비가시·말풍선 공유 회귀·상단 '위에 더 있음' 흐림 신호·오른쪽 위치 막대 클릭 이동·공유/그룹 편집 버전 읽기전용 페이징) + generated 2026-07-21→2026-07-22. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + deploy-web.sh `asset_stamp_verify` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침).
- 근거 정본: 각 항목 owning POST-DEPLOY 커밋(4edb7701/5dbe7992·0ebbac8e/a8fb33d1·7a5b092a/94e2cadd·0db6fc36/109befe1·a92492e6/a70f8382·f0a32980/20562ff9) + git log cfa647df..HEAD.
- Verification: `node --check` PASS · vm 구조검증(33 releases·07-22 head 6항목[fixed 3·improved 3·area work]·07-21 보존·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260723T024724-paging-scroll-preserve (20260723T024724-paging-scroll-preserve — 브랜치 페이징 스크롤 위치 보존, Minor §12.3, frontend-only UX)
- 계기: 사용자 신고 — 편집 버전 페이징 시 스크롤이 맨 아래로 튀어 연속 페이징 번거로움.
- 근본원인: `renderMessages()` 는 매 재렌더 `scrollTop=scrollHeight`; 비-append `loadHistory` 는 `_applyRenderWindowSoon`(rAF)로 재-스크롤; 공유 뷰 `render` 는 `#shareMessages` 교체로 문서 스크롤 튐.
- 변경(`static/app.js`): `loadHistory` 에 `preserveScroll` 옵션(저장 top 복원 + window-soon 생략, rAF). `refreshWorkspace(opts.preserveScroll)` 전달. `_pageBranch` 그룹/1:1 페이징에 preserveScroll 적용.
- 변경(`static/share.js`): `pageBranchShare` window.scrollY 저장→rAF 복원.
- 비변경(회귀 0): append(이전 이력 prepend)·일반 대화 로드·전송 후 스크롤은 기존(맨-아래/prepend 보존). preserveScroll 미지정 경로 전부 동일. 백엔드/스키마/RBAC 0.
- cache-buster: `?v=dev` 고정(빌드 자동주입).
- Verification: `node --check` 2 · POST-DEPLOY headless/Windows 실측(페이징 전후 scrollTop 보존).
- Files: `static/app.js`, `static/share.js`, `docs/{TASK,MODIFY,FUNCTION,REPORT,TEST,REVIEW}.md`.
- landing/배포: verify-completion → commit → PR/머지=자동 동기화. 배포=web-only(정적자산·백엔드 무관).

## CHG-20260723T033000-paging-scroll-preserve-postverify (paging-scroll-preserve POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 배포·양 surface 라이브 스크롤 실측 기록 + TASK 완료. 코드/자산 0.
- 배포: PR #889 → main 4ee7ea1d → deploy-web --web-only(soak PASS). 서빙 app.js `preserveScroll`·share.js `savedY` 반영.
- 라이브(Windows Chrome 4ee7ea1d): 인앱 그룹 브랜치 대화 페이징 후 scrollTop=0(scrollable maxTop 9538, 맨아래 안 튐)·스크린샷 육안. 공유-링크 짧은→긴(maxY 11535) 페이징 후 window.scrollY=0. 양 surface PRESERVED.
- Files: docs/{TASK,MODIFY,REVIEW,TEST}.md.

## CHG-20260723T033143-paging-scroll-longhistory (20260723T033143-paging-scroll-longhistory — 긴 이력 페이징 스크롤 보존 회귀 수정, Minor §12.3, frontend-only)
- 계기: 사용자 신고(admin '간단한 덧셈 계산' 3→4) — 이전 대화내역 길면 페이징 스크롤 보존 실패.
- 근본원인: preserveScroll 이 `_applyRenderWindowSoon` 생략 + loadHistory renderCount=WINDOW_INITIAL_RENDER(3) 리셋 → 긴 버전 스레드(브랜치 메시지 뒤 후속 턴)에서 브랜치 메시지(pager) 창 밖 → pager 소실·scrollHeight 급변.
- 변경(`static/app.js` loadHistory): preserveScroll 시 renderCount=messages.length(전체 렌더). 형제 버전 분기점-위 이력 동일 → 전체 렌더로 pager 유지 + scrollTop 정확 보존.
- 비변경: append/일반 로드 renderCount 무변경(회귀 0). 백엔드 0.
- Verification: node --check · POST-DEPLOY PB-0008(3→4 pager 유지+스크롤 보존).
- Files: `static/app.js`, docs.

## CHG-20260723T034500-paging-scroll-longhistory-postverify (paging-scroll-longhistory POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 라이브 실측 + TASK 완료. 코드 0. 배포 PR #891 → main 2cdb7907 → deploy-web --web-only(soak PASS).
- 라이브(Windows Chrome '간단한 덧셈 계산' 3→4): rendered 3→6(전체 렌더), pager '4/4' 유지, 브랜치 메시지 뷰포트 298px→298px 동일(scrollTop 4985, scrollable maxTop 11286, atBottom=false)·스크린샷 육안. verdict PRESERVED.
- Files: docs/{TASK,MODIFY,REVIEW}.md.
## CHG-20260723T071355-universal-ctxmenu (서비스 UI 우클릭 = 보편적 확장 메뉴 단축, Major §12.3, frontend-only)
- 계기: 사용자 요청(`/_template:entry`) — "각 요소 우클릭이 보편적 확장기능으로 동작. 대화·목록창='···', 대화 로그='☰'. 등과 같이."
- 변경(`static/app.js`, 2지점 additive):
  - `openFloatingMenu`: 모듈 전역 `_floatingMenuAnchorPoint`(우클릭 시 커서 좌표·1회 소비·finally 방어 해제) 도입, 위치 계산이 anchor 있으면 커서 기준·없으면 기존 trigger-rect 기준(**anchor=null byte-동치**·회귀 0).
  - 신규 `_CTX_MENU_TARGETS` 설정표 + `_hasSelectionWithin`(Range.intersectsNode) + `_onUniversalContextMenu`(document 위임 리스너) — 호스트(`.conv-item`/`.conv-folder-header`/`.message`) 매칭 시 기존 트리거 synthetic click 재발화(open 함수·권한·항목·토글 100% 재사용). input/link/미디어(img·svg·canvas·video)/contentEditable·호스트 내 텍스트 선택·키보드 contextmenu(0,0)는 기본 우클릭 양보.
- 비변경: 기존 '···'/'☰' 버튼 클릭 동작·위치, 대화 선택/폴더 토글(우클릭이 유발 안 함), admin.js, 그래프 우클릭(graph-ctxmenu.js), 백엔드/RBAC/스키마/엔드포인트 0.
- Verification: `node --check` PASS(2회) · §18.8 적대 리뷰 SHIP(MINOR 3 반영) · POST-DEPLOY PB-0008(AC-1~5).
- Files: `static/app.js`, docs/{TASK,FUNCTION,REPORT,REVIEW,TEST-runs}.md.

## CHG-20260723T075215-universal-ctxmenu-postverify (universal-ctxmenu 배포 + 라이브 실측 POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 라이브 실측 + TASK 완료. 코드 0. PR #897 → main **c6f7f98a** → `deploy-web.sh --web-only`(web-a/web-b 무중단 롤링·90s soak PASS·caddy no-op·자산 스탬프 e6d39fde416f). deploy_scope: included(FIRST_REQUEST.md 전역·§12.2 사전 승인).
- 라이브(win-browser Chrome 150, https://localhost/ 작업 화면, 실 contextmenu button2): AC-1 대화항목 우클릭→'···' 커서개방(공유/설정/폴더·aria=true)·AC-2 폴더헤더→폴더메뉴(하위/이름/지침/삭제)·AC-3 말풍선→'☰'(분기/공유·커서개방)·AC-4 텍스트 663자 선택 후 우클릭→native 보존(defaultPrevented=false·☰ 미개방)·AC-5 버튼 클릭 trigger-rect byte-동치(rightAligned·belowTrigger)·**errCount 0**. 서빙 app.js 신규 심볼 전부 hit.
- Files: docs/{TASK,MODIFY,REPORT,REVIEW,TEST-runs}.md.

## CHG-20260723T080415-floating-menu-close-fix (floating 메뉴 닫힘 결함 수정 — folderMenu 1급 승격, Minor §12.3, frontend-only)
- 계기: universal-ctxmenu 후속 사용자 신고 — 폴더 '···' 메뉴가 열린 뒤 바깥클릭/ESC 로 안 닫힘.
- 근본원인: `closeFloatingMenus()` 제거 id 하드코딩 `["convItemMenu","bubbleMsgMenu"]` → feature-0024 `id="folderMenu"` 누락(pre-existing drift). universal-ctxmenu 우클릭이 폴더 메뉴를 쉽게 열게 되며 표면화.
- 변경(`static/app.js`+`static/styles.css`): ① `openFloatingMenu` 생성 메뉴에 `menu.dataset.floatingMenu="1"` 마커. ② `closeFloatingMenus` 를 `[data-floating-menu]` id 무관 일괄 제거 + 트리거 리셋 selector 에 `.conv-folder-menu-trigger.is-open` 추가. ③ 정합: `_attachShareRangeEsc`(8383)·`_maybeSyncConversationListUnread`(11662) 열린-메뉴 가드에 folderMenu 포함 + `styles.css` `.conv-folder-menu-trigger.is-open{opacity:1}`.
- 비변경: conv-item '···'·말풍선 '☰' 닫힘(마커 제거=id 제거 superset), 백엔드/RBAC/스키마/엔드포인트 0.
- Verification: `node --check` PASS · §18.8 적대 리뷰 SHIP(NIT 3 fold-in) · POST-DEPLOY PB-0008(AC-1~5).
- Files: `static/app.js`, `static/styles.css`, docs/{TASK,FUNCTION,REPORT,REVIEW,TEST-runs}.md.

## CHG-20260723T081500-floating-menu-close-fix-postverify (floating-menu-close-fix 배포 + 라이브 실측 POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 라이브 실측 + TASK 완료. 코드 0. PR #902 → main **57ecc758** → `deploy-web.sh --web-only`(soak PASS·자산 스탬프 8373a9f479e2). deploy_scope: included(전역).
- 라이브(win-browser Chrome 150, https://localhost/, 테스트 폴더 API 생성 id=6 후 실 이벤트 dispatch, 검증 후 삭제·프로덕션 잔여 0): AC-1 폴더메뉴 바깥클릭 닫힘·AC-2 ESC 닫힘·AC-3 scroll 닫힘·AC-4 토글 닫힘+트리거 aria-expanded=false·is-open 제거·AC-5 conv-item 무회귀·errCount 0. 서빙 app.js `data-floating-menu` 2 hit·css `.conv-folder-menu-trigger.is-open` 1 hit.
- Files: docs/{TASK,MODIFY,REPORT,REVIEW,TEST-runs}.md.
## CHG-20260723T074530-reasoning-timeline (20260723T074530-reasoning-timeline — AI 운영 현황 > 추론 결함수정 전/후·답변개선 과정 가시화, Major §12.3, web/UI 프론트 + additive read-only API)
- 배경: 「AI 운영 현황 > 추론」이 리뷰 결함 수정 전/후 과정·답변 개선 과정을 드러내지 못해 관제 신뢰성 낮음(사용자 신고). 접근 A(기존 `redteam_reviews` 데이터 재구성 — 마이그레이션·계측·답변원문 저장 없음, AskUserQuestion 승인).
- `unit/feature-0003-agent-web-ui/src/routers/admin_reasoning.py`: `_query_reviews` 에 `include_rederive` 파라미터 + 0043 컬럼(`rederive_applied/rederive_tool_rounds/rederive_axis`) additive SELECT·응답 노출. 호출부 `admin_reasoning_redteam` 에 `information_schema` 컬럼 존재 감지 → 부재 시 `include_rederive=False` 폴백(stale agent 이미지, 회귀0). 모든 경로에서 rederive 3필드 기본값 보장.
- `unit/feature-0003-agent-web-ui/src/static/admin.js`: reasoning 탭 렌더 재구성 — 신규 `_reasoningConvLink`·`_reasoningStageTimeline`·`_reasoningFindingHtml`·`_reasoningAxisSummary` + 상수 `_REASONING_AXIS_LABELS`/`_REASONING_LEVEL_LABELS`. `_reasoningReviewRowHtml`·`renderReasoning` 개편(진행 5단계 타임라인·claim→fix_hint 전/후 대비·5축 집계·대화 딥링크·강도 한글화·힌트 문구). 통계 타일·페이징·메모리 노트 보존.
- `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.reasoning-timeline/-stage(-done/warn/skip/na/err)`·`.reasoning-finding(-block/warn)`·`.reasoning-ba(-col/-tag/-text/-arrow)`·`.reasoning-sev(-block/warn)`·`.reasoning-axis--{5축}`·`.reasoning-axis-summary/-badge`·`.reasoning-conv(-system)` 추가. 기존 `.reasoning-review-head` flex-wrap. 기존 `.reasoning-finding*` 3줄 재정의. CSS 변수 재사용·라이트/다크 대응.
- 검증: `node --check`(ESM) OK · `py_compile` OK · 실제 소스 추출 harness 단위 22/22 PASS. §18.8 panel(프론트/UX/보안 + 백엔드/QA) = REV-20260723T074530-reasoning-timeline.
- 불변: 백엔드 계측·스키마·RBAC·엔드포인트 무변경. cache-buster `?v=dev` 고정(빌드 자동 주입). POST-DEPLOY PB-0008(Environment: Windows-browser) 예정.

## CHG-20260723T084235-reasoning-timeline-postverify (reasoning-timeline 배포 + 라이브 실측 POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 라이브 실측 + TASK 완료. 코드 0. PR #901 → main **e4ef9384** → `deploy-web.sh --web-only`(web-a/web-b 무중단 롤링·soak PASS·자산 스탬프 d09bcdc34a46).
- 라이브(win-browser Chrome 150, https://localhost/admin, 리뷰 30건): 진행 타임라인 150 stages(30×5)·전후 대비 47·5축 집계(근거15/SQL6/완전성12/정직성14)·rederive "도구 재추론(SQL)"·대화 딥링크 30·통계 타일 6·pageerror 0. **W2 페이징 축 갱신** 47→93 재계산 확증. verdict pass 카드 **B1 정확**("결함 없음—통과"/"불필요(결함 없음)"). 서빙 admin.js 신규 심볼 8 hit.
- Files: docs/{test-runs.d/20260723T074530-reasoning-timeline.md, MODIFY.md, REVIEW.md}.

## CHG-20260724T010501-doc-sync-rn-0724 (TASK-20260724T010501-doc-sync-rn-0724 — 07-23 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` releases head 에 "2026-07-23" 블록 prepend(7항목 new/work 2·improved/work 2·fixed/work 1·improved/admin 2 — 대화 폴더·폴더별 AI 지침·대화목록 월·연 날짜 묶음·우클릭 메뉴·메시지 버전/긴 이전 대화 페이징 스크롤·AI 답변 다듬기 전·후 보기·DB 전체 AI 자동 분석 완결성) + generated 2026-07-22→2026-07-23. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + deploy-web.sh `asset_stamp_verify` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침).
- 근거 정본: owning POST-DEPLOY 커밋(폴더 9392cf51/e3fec503/0a1378f3/1a2f2595·날짜트리 8b384b8a·우클릭 b51f93e9·페이징 fce9ab2b/5d0f8467·추론타임라인 a17fd1a7·DB분석 6da5e621) + git log aac76889..HEAD.
- 제외: graph-node-reveal(feature-0016)은 자체 POST-DEPLOY PB-0008 미기록이라 보류(배포 게이트 미해소)·floating-menu-close-fix/share-list-window-fix 흡수/비노출.
- Verification: `node --check` PASS · vm 구조검증(34 releases·07-23 head 7항목·07-22 보존·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260724T012954-usage-model-canonical — LLM 사용량 '모델별 비중' 중복 명칭 분점 해소
- 문제: 관리 콘솔 > 감사 > AI 운영 현황 > **LLM 사용량** 서브탭의 '모델별 비중' 도넛이 같은 논리 모델을
  여러 조각으로 분점. 원인 = `by_model` 집계가 `COALESCE(resolved_model, model)` 로 GROUP BY 하는데
  이 값에 litellm 라우팅 변형 alias(`-interactive`/`-chat`/`-root`/`-interactive-root`/`-chat-root`)·실
  모델 ID(`claude-haiku-4-5-20251001`)·edge 폴백 실모델(`gemma4:e2b`)이 섞여 한 모델이 N 세그먼트로 쪼개짐.
- 수정: `shared/model_catalog.py` 에 canonical family 함수 2종 추가(SSOT):
  `canonical_usage_model(name)`(Python) + `canonical_usage_model_sql(col)`(PG `starts_with` CASE, LIKE '%' 회피
  → 파라미터 쿼리 이스케이프 불필요). 규칙: `claude-haiku-4*`→`claude-haiku-4`, `claude-sonnet-4*`→
  `claude-sonnet-4`, `gemma*`/`edge`/`edge-fallback`/`auto`/`core`/`code`→`edge`, 그 외 원본 유지(self-surface).
- 적용: `admin_usage.py` — by_model·by_account·by_day_model GROUP BY + `_query_usage_conversations` 모델
  필터·모델 분해를 canonical 로 통일. by_model row 는 `model==resolved_model==canonical` 로 채워 프론트
  (modelKeyOf/도넛 라벨/색맵/드릴다운) **무변경** 정합. `profile.py`(개인 사용량 도넛·드릴다운 일관성)·
  `admin_console.py`(대시보드 '모델별 토큰' 위젯) 동일 적용.
- 부수: `_estimate_llm_cost_usd` 단가 조회 키를 canonical 화 — 단가표(`_LLM_PRICE_USD_PER_1M`)가 base alias
  만 등록해 변형/실ID 가 비용 $0 로 오표시되던 gap 해소(모든 app.X 호출부에 중앙 반영). edge/gemma 는
  단가 미등록 → 0(로컬 무료) 정직 유지. gemma 폴백 호출도 실 서빙 모델 기준 집계라 haiku 단가 과대계상 정정.
- 실 PG 검증(90일): 기존 7 세그먼트 → 3 실제 모델 병합 — claude-haiku-4(64,552,777 tok)·edge(30,431,975)·
  claude-sonnet-4(785,900). run_id distinct 도 canonical 그룹 단위 dedup(요청 수 과대계상 없음).
- Files: `shared/model_catalog.py`, `unit/feature-0003-agent-web-ui/src/routers/{admin_usage,profile,admin_console}.py`,
  `unit/feature-0003-agent-web-ui/tests/test_usage_conversations.py`.
- Verification: 전체 pytest 2280 passed / 2 skipped(기존 baseline) · py ast 문법 · 실 PG canonical 쿼리 실측.
- Follow-up(§8.1 기록만): `ai_ops.py`(운영 현황 task×model, line 319) 는 동일 canonical 함수로 접을 수 있으나
  별도 축(task 우선)이라 이 cycle 범위 밖 — 미해소. TASK.md 1.2MB(§5.6 hygiene 임계 초과) 아카이빙 권고.

## CHG-20260724T020632-aiops-model-canonical — '운영 현황' 서브탭 잔존 raw 모델 표기 canonical 정합(usage-model-canonical 후속)
- 배경: PR#914(usage-model-canonical)이 'LLM 사용량' 도넛·집계를 canonical family 로 통일한 뒤, 같은 감사
  화면의 '운영 현황' 서브탭(`ai_ops.py`)에 남은 마지막 raw 모델 표기 2곳을 정합화(사용자 요청 "나머지 범위 또한 실제값과 정합").
- 변경 (`ai_ops.py` 단일 파일 + test):
  1. categories 집계 쿼리(admin_ai_ops): `COALESCE(resolved_model, model)` → `canonical_usage_model_sql(...)`.
     이 집계는 taxonomy 카테고리로 fold 되어 모델 차원 미노출 + 비용은 `_estimate_llm_cost_usd`(내부 canonical)
     이라 **출력 불변**이나, 마지막 raw 모델 그룹핑을 제거해 SSOT 일관성 확보 + 향후 모델 차원 노출 시 재분점 예방.
  2. `_query_activity`(최근 활동 feed) 주 모델 배지: `"model": served` → `canonical_usage_model(served)` — 활동
     목록 배지가 도넛과 동일한 canonical 실 모델명으로 표시. **`req_model`(r[2])·`resolved_model`(r[3])은 raw 보존**
     → 상세 펼침의 '요청 alias → 서빙 모델' 라우팅(계정 분기·gemma 폴백) audit 정보 손실 없음. 비용 무변경.
- 비변경: admin.js/스키마/RBAC/엔드포인트 계약, `_estimate_llm_cost_usd`, categories 출력(calls/tokens/cost), 활동
  상세의 req→resolved 표시. `shared/model_catalog.py` 는 PR#914 에서 이미 main.
- Files: `unit/feature-0003-agent-web-ui/src/routers/ai_ops.py`, `unit/feature-0003-agent-web-ui/tests/test_ai_ops.py`.
- Verification: 전체 pytest 2287 passed / 2 skipped(기존 baseline) · py ast · 신규 test_query_activity_model_canonical_preserves_routing(폴백행 배지=edge, req/resolved raw 보존).
- 잔여: 없음 — 전 코드베이스 raw `COALESCE(resolved_model, model)` 모델 그룹핑 0건(grep 확인).

### CHG-20260724T020632 리뷰 반영 addendum (적대 리뷰 SHIP-WITH-FIXES → 3건 반영)
- **M1(MAJOR) 수정**: `static/admin.js` 활동 상세 폴백 `srvM = r.resolved_model || r.model` → `|| r.req_model`.
  배지 canonical 화로 `r.model` 이 canonical 이 되어, resolved_model=NULL + 비-canonical req_model(auto 등) 행에서
  상세가 '가짜 라우팅 화살표'(auto→edge)를 날조하던 것을 차단(상세=100% raw). Windows-browser eval 4시나리오 확증.
- **m1 정정**: categories "출력 불변" → calls/total_tokens 불변(정수 sum), cost 는 round 재결합으로 최하위 4번째
  소수(≈$0.0001) 미세 변동 가능(단일 round 라 더 정확). ai_ops.py 주석 톤다운.
- **m2 반영**: NULL-resolved+비canonical req 백엔드 테스트 추가.
- Files(정정): `src/routers/ai_ops.py`, `src/static/admin.js`, `tests/test_ai_ops.py`, `docs/test-runs.d/20260724T020632-aiops-model-canonical.md`.
- admin.js 변경으로 check #13(visual_verification_scope=always) 활성 → test-runs.d fragment(Windows-browser Run) 동반, POST-DEPLOY 라이브 PB-0008 후속.

## CHG-20260724T123600-csv-download-wiring — assistant "CSV 다운로드 가능" 답변의 실제 다운로드 배선 누락 수정 (conv-audit csv-inline-no-download, Major cross-cut)
- **증상**: 대화 '킹스레이드 배틀 로그 차원별 집계'(515c0fd9, bootstrap_admin)에서 assistant 가 결과를 인라인 ```csv``` 텍스트로 붙이고 "다운로드하실 수 있습니다"라고 안내했으나 클릭할 다운로드 대상이 전무(8메시지 중 5개). `/api/file` 엔드포인트·권한 게이트·`/shared/out` 저장은 정상 — 링크 주입 책임이 LLM 즉흥에 의존.
- **근본원인**: 답변→링크 후처리기 `agent_core._collapse_large_tables` 가 Markdown 표(`|...|`)만 인식, ```csv``` fenced 블록은 blind spot. 모델이 (툴 가이던스 "전체 표를 삽입하지 말고"를) csv 블록으로 해석 → 링크 미주입 dead-end.
- **수정 (3계층, additive·behavior-neutral for non-csv)**:
  - `src/static/app.js`: `enhanceCsvBlockDownloads(target)` + `_csvDownloadFilename()` 추가, `renderMessageContent` assistant 분기에 배선(enhanceFilePreviewLinks 뒤). ```csv``` 블록마다 클라이언트 Blob(UTF-8 BOM) "📥 CSV 다운로드" 버튼. 바로 뒤에 `/api/file` 링크가 있으면(백엔드 절단-미리보기) 버튼 skip.
  - `src/static/share.js`: 공유 뷰 동일 미러(기존 `.share-csv-download-btn` 재사용, `renderMarkdownContent` 배선). 인라인 CSV 는 이미 가시 텍스트라 신규 노출 없음(서버 파일·step csv_paths 는 공유 redaction 유지).
  - `src/static/styles.css`: `.csv-block-actions`(flex bar)·`.csv-download-btn`(border+primary hover).
  - (cross-cut 코드 거주 feature-0002) `src/agent_core.py`: `_collapse_large_csv_blocks(answer, csv_paths)` — 대형 ```csv``` 블록을 값-토큰 매칭(`_match_csv_for_table`/`_csv_signatures` 재사용)으로 저장 CSV 찾아 헤더+미리보기 접기 + `📎 [전체 N행 미리보기](/api/file?path=)` 주입. 매칭 실패 시 원문 유지(데이터 손실 방지). 초안(3계층)·redteam 수정·redteam 최종 3경로에 `_collapse_large_tables` 뒤 체인.
  - (cross-cut 코드 거주 feature-0002) `src/modules/tools.py`: execute_sql·scratch_sql 툴 출력에 "저장 CSV 는 다운로드 버튼으로 자동 제공 — 링크 직접 생성 불필요, 전체 데이터 붙여넣기 금지" 항상(절단 무관) 안내. 기존 "CSV 다운로드 링크를 제공하세요"(모델이 URL 생성) 지시 폐기.
- **Files**: `src/static/app.js`, `src/static/share.js`, `src/static/styles.css`, `unit/feature-0002-agent-core/src/agent_core.py`, `unit/feature-0002-agent-core/src/modules/tools.py` + tests(`unit/feature-0002-agent-core/tests/test_collapse_csv_block_download.py`(신규), `unit/feature-0003-agent-web-ui/tests/verify_csv_block_download.mjs`(신규), `test_partial_evidence_grounding.py`·`test_scratch.py` 가이던스 문구 정합).
- **Verification**: 전체 pytest **2303 passed / 2 skipped**(무회귀) · jsdom 18 PASS · `node --check` app.js/share.js. check #13(visual_verification_scope=always) 활성 → test-runs.d Windows-browser fragment 동반, POST-DEPLOY 라이브 PB-0008.
- **잔여**: verify → commit → deploy(web+worker) → POST-DEPLOY PB-0008.

## CHG-20260724T133000-csv-download-wiring-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — csv-download-wiring 배포(dc316152) 후 라이브 검증 결과 기록만.
- test-runs.d/20260724T123600-csv-download-wiring.md 에 POST-DEPLOY 결과(Windows-browser PASS) append + REPORT 완결 표기 + TASK 최종 체크박스 + REVIEW REV-20260724T133000-csv-download-wiring-postverify.
- 실측: 대화 515c0fd9 인라인 ```csv``` 블록 아래 "📥 CSV 다운로드" 버튼 렌더·클릭 Blob text/csv size=2603 다운로드·콘솔 에러 0. 서빙 자산 curl 확증. 사용자 요청 해소.

## CHG-20260724T053457-metadata-review-ds-scope — 메타데이터 거버넌스 검토 큐 datasource 필터 + 자동승급 목록 정합 + 등록 시각 표시 (Major §12.3, frontend-only)
- **계기**: 사용자 신고(`/_template:entry`) — `관리 콘솔 > 지식베이스 > 메타데이터 > [용어사전/ENUM 코드사전/샘플쿼리]`: ① 출력 요소가 선택 데이터소스로 필터 안 됨(검토 큐) ② 검토 큐에서 자동 승급된 항목이 목록 내부에서 조회 안 됨 ③ 각 요소 등록 시점 알 수 없음.
- **RC**:
  - ①/② scope-decoupling — 목록(`loadMetadata`)은 상단 데이터소스 셀렉터 `adminState.metadata.scopeKey`(기본 'common')를 `?scope_key=` 로 전송하나, 검토·검수 큐 로더(`loadFeedbackQueue`/`loadSampleReview`)는 `scope_key` 미전송(=백엔드 전체 반환)이라 큐가 전 datasource 후보를 무필터 표시. 자동승급 항목은 대화 datasource scope 로 `kb_glossary`/`enum_dictionary` 에 기록되므로 목록(기본 common scope)에선 미조회 → "큐엔 보이는데 목록엔 없음". 백엔드 3개 큐 엔드포인트(glossary-feedback/enum-feedback/sample-feedback)는 이미 optional `scope_key` 지원(=프론트 결함).
  - ③ 목록 행(`_metaListRow`)이 `수정(updated_at)`만 표시하고 `created_at` 미표시. glossary/ENUM 검토 큐 행·상세, ENUM 묶음 행에도 등록 시각 없음(sample 상세엔 기존 존재). 백엔드는 세 목록·세 큐 모두 `created_at` 이미 반환.
- **수정(admin.js, additive·표시 계층 + 쿼리 파라미터, behavior-neutral for 목록 경로)**:
  - `_metaReviewScopeParam()` 신규 — `adminState.metadata.scopeKey` 기반, 특정 datasource 선택 시 URL-encoded scope_key, '공용(common)'=""(무필터=전 datasource triage, Option A: pending 배지 전-scope 집계와 정합·자동수집 후보 항상 ds-scoped 라 common 필터 시 영구 빈 큐 회피).
  - `loadFeedbackQueue`: `?status=…` 에 `&scope_key=` 추가(sp 있을 때). `loadSampleReview`: `/api/admin/sample-feedback` 에 `?scope_key=` 추가(sp 있을 때). 셀렉터 변경 핸들러(`_metaBindControls`)는 이미 review 보기에서 `loadMetadata`→큐 로더 재호출 → 즉시 재필터(배선 무변경).
  - `_metaListRow`: meta 줄 `등록 <created_at>` + 수정 시각 상이 시 `· 수정 <updated_at>` 병기(null 안전 폴백). `renderFeedbackQueue`(glossary/enum 행): tags 뒤 `등록 <created_at>` meta 줄. `_metaRenderReviewDetail`(glossary/enum else 분기): `등록 <created_at>` 태그. `_metaBuildEnumBundle`(묶음 코드 행): `등록 <created_at>` 태그. 모두 `_metaFmtDt` + `textContent`(XSS 안전).
- **§18.8 적대 리뷰 반영(SHIP-WITH-FIXES, 3건 전부)**:
  - **Finding 1 (MAJOR, backend additive)**: 큐 리스트는 scoped 됐으나 pending 배지가 unscoped(`count_glossary_feedback`/`count_enum_feedback` scope 미적용) → 특정 ds 선택 시 리스트 N건↔배지 전체 불일치. 수정: `unit/feature-0002-agent-core/src/modules/kb_glossary.py` 두 count 함수에 `scope_key=None` additive 파라미터(지정 시 `AND scope_key=%s`·`_normalize_scope_key`; 미지정=기존 전체 집계 byte-동치) + `admin_metadata.py` glossary-feedback/enum-feedback 이 `scope_filter` 전달 → 배지=scoped pending.
  - **Finding 2 (MINOR, frontend)**: `_metaPrimeReviewBadge` 가 `_metaReviewScopeParam` 로 scope 전송 + scope-change 핸들러가 변경 시 배지 재-prime(list 보기·타 서브탭 stale 해소).
  - **Finding 3 (MINOR, frontend)**: sample 큐 행·상세 날짜를 `등록 ${_metaFmtDt}` 로 통일(glossary/ENUM 와 라벨·포맷 정합).
- **무영향**: RBAC·스키마·마이그·인증 0. 백엔드 변경은 count 2함수의 additive `scope_key` 파라미터 + 엔드포인트 인자 전달뿐(미지정 시 byte-동치, 여타 호출자 없음 — admin 전용). 목록(`loadMetadata`) 경로 무변경. auto-promote write(`_insert_glossary_auto`)↔목록 read(`list_glossary_admin`) scope 정규화(`_normalize_scope_key`) 동일 — divergence 없음.
- **Files**: `src/static/admin.js`(feature-0003) · `unit/feature-0002-agent-core/src/modules/kb_glossary.py`(count 함수 scope, cross-cut) · `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py`(엔드포인트 scope_filter 전달) · 테스트 monkeypatch 시그니처 2건(`test_metadata_glossary_autoreg.py`·`test_metadata_enum_feedback.py`).
- **Verification**: `node --check`(ESM) PASS · `verify_metadata_list_detail.mjs` baseline 대조 신규 회귀 0(26 PASS/3 FAIL·[D] crash 는 pre-existing 하니스 노후화, clean main 동일) · `py_compile`(kb_glossary/admin_metadata) · pytest **116 PASS**(feature-0003 metadata glossary-autoreg/enum-feedback/sample-curation 44 + feature-0002 glossary/enum 72) · §18.8 적대 리뷰(SUBAGENT, SHIP-WITH-FIXES→3건 반영). 정적 자산 web 이미지 baked → 라이브 PB-0008 = POST-DEPLOY(visual_verification_scope=always).
- **잔여**: verify-completion → commit → PR → merge → deploy-web → POST-DEPLOY PB-0008.

## CHG-20260724T053457-metadata-review-ds-scope-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — metadata-review-ds-scope(PR #931·main 2b22b5ff) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260724T053457-metadata-review-ds-scope.md 에 POST-DEPLOY 결과(Windows-browser PASS) append + REPORT 완결 + TASK 최종 체크박스 + REVIEW REV-20260724T053457-metadata-review-ds-scope-postverify.
- 실측(실 Windows Chrome, https://localhost/admin): 검토 큐 공용 96건→mysql-kr-an1-auth 16건 필터·배지 96→16 정합(MAJOR Finding 1)·목록 84건 중 82 자동등록 가시(Fix 2)·전 행 `등록 <시각>`(Fix 3)·pageerror 0. 사용자 3결함 전부 해소 확인.
## CHG-20260724T181106-brandnew-script-attachment — assistant 신규 스크립트 첨부 전달 경로 (Major §12.3)
- **What**: source 없이 새로 생성한 스크립트/쿼리를 다운로드 첨부(root 첨부)로 전달하는 `attachment-new` 경로 신설. 기존 편집 경로(source_attachment_id 필수)와 별개.
- **Why(RC)**: FR-brandnew-script-attachment-delivery-gap — 첨부 생성 경로가 기존 첨부 편집만 지원해 "생성한 스크립트를 첨부로" 요청 시 assistant 거부(대화 …f1c535ec msg 1384). 재발경로=capability gap.
- **Files(feature-0003)**: `src/routers/_conv_store.py`(`_attachment_block_spans` 공통 헬퍼 리팩터 + `_attachment_new_block_spans`·`_parse_attachment_new_blocks`·`_materialize_assistant_attachment_new`), `src/routers/conversations.py`(ask 배선 + `_strip_attachment_new_blocks`), `src/app.py`(allowlist 상수 + import), `src/static/app.js`(배지 생성/수정 구분 + new_attachments 토스트).
- **Files(feature-0002 cross-ref)**: `src/agent_core.py` — CHG-20260724T181106-attach-new-directive(`_ATTACHMENT_NEW_DELIVERY_DIRECTIVE` 주입 + base 섹션 + inline 예외).
- **보안**: 확장자 allowlist(sql/txt/csv/md/markdown/json/yaml/yml/xml/log, 그 외→.txt), account/conv scope(IDOR 0), 크기 1MB·개수 캡 편집과 합산(remaining_count), **업로드 RBAC 게이트**(§18.8 MAJOR: `conversation.attachment.upload.own/any`). 보안 회귀 0.
- **Verification**: pytest 2369 PASS(신규 27) · py_compile 4파일 · node --check app.js · §18.8 AGENT-TEAM(security+backend) MAJOR/MINOR 전부 반영. 정적 자산 baked → 라이브 PB-0008 = POST-DEPLOY.
- **잔여**: verify-completion → commit → PR/deploy(별도 confirm) → POST-DEPLOY PB-0008.
## CHG-20260724T180649-share-point-rail-bars (공유링크 뷰 대화 뱃지 막대화 + 클릭 위치 비례, Minor §12.3, frontend-only 표시전용)
- Files: `unit/feature-0003-agent-web-ui/src/static/{share.js,share.css}`.
- A(막대화): `layoutSharePointRail` top%+height%(범위 비례) + CSS 점→막대. B(클릭 비례): 클릭 핸들러가 막대 내 y 비율 → 신설 `scrollShareMessageToRatio`(window.scrollTo EaseOutExpo). 메인 뷰(app.js scrollMessagePointToRatio·layoutMessagePointRail) 동형 이식 — 공유는 window/문서 좌표.
- `scrollShareMessageIntoCenter` 유지(항상 중앙 — 재사용 대비, dead 아님으로 보존). 백엔드·RBAC·스키마 무영향.
- 검증: `node --check` PASS. POST-DEPLOY PB-0008 예정.
## CHG-20260724T085937-sonnet-reasoning-budget-guide — 관리 콘솔 '모델별 추론 예산'의 adaptive(Sonnet 5) 죽은 budget 슬라이더 제거 + guide-note 전환 (Minor §12.3, cross-feature: 정본 feature-0003+shared, tests feature-0002)
> 계기(사용자): "추론 수준이 claude-code 내부 effort 를 따르면 `관리콘솔 > 설정 > 모델별 추론 예산`의 sonnet 구성을 제거하거나 가이드만 남긴 상태로 전환 검토". 확인 결과 adaptive(Sonnet 5)는 추론 강도가 output_config.effort(=Anthropic/Claude Code 내부 effort: 낮음→low·일반→기본 high·높음→high·매우높음→max)로 제어되고, `_call_llm` adaptive 분기는 reasoning_budget/model_thinking_budget override 를 **조회조차 안 함** → 해당 섹션의 sonnet budget_tokens 슬라이더 ②③은 저장해도 무효과인 죽은 컨트롤(이전 이연 H5). 사용자 선택 = "가이드 노트 전환".
- Changes(shared `shared/runtime_settings.py`): `_budget_thinking_models()`(= `_thinking_models()` 중 `model_thinking_style != "adaptive"`) + `_adaptive_thinking_models()` 신설. `_reasoning_budget_specs()`·`_model_budget_specs()` 가 `_budget_thinking_models()` 순회로 전환 → adaptive 모델은 ②③ 스펙 **미생성**(registry→API→UI 로 죽은 슬라이더 미노출). `agent_max_output` 스펙(①)은 `_thinking_models()` 전체 유지(adaptive 도 live max_tokens). `serialize_registry` 에 `adaptive_models: [...]` 추가(UI guide-note 대상 표면화).
- Changes(feature-0003 `src/static/admin.js` `renderModelThinkingBudgets`): `data.adaptive_models` set 로드. 모델 카드가 adaptive 면 ②(추론 강도별 예산)·③(일반 기본 budget) 슬라이더 대신 **guide-note**("adaptive thinking — 추론 강도는 대화 화면의 추론 강도 선택기가 effort 로 제어, 모델별 budget 미적용, 라운드당 출력만 유효") 렌더. budget 계열(haiku)은 기존 ②③ 그대로. ①(라운드당 출력)은 전 모델 유지. 가이드는 기존 CSS 클래스(`rs-subgroup-title`·`rs-readonly-note`) 재사용 — **신규 CSS 없음**(cache-buster 표면 admin.js 만).
- Behavior 불변: 실제 LLM 호출은 무변경(adaptive 는 이미 budget 미조회, effort 만 사용). 죽은 override 가 DB 에 있어도 무효(serializer 는 override 없는 spec 만 순회 — orphan override 는 live 미반영). agent_max_output(①)·haiku budget·effort 매핑·RBAC·마이그레이션 0.
- Tests: feature-0002 `test_runtime_settings.py`(sonnet budget 스펙 부재·override 항상 None·haiku clamp 62976·reasoning_budgets haiku-only 3행·adaptive_models 표면화), feature-0003 `test_runtime_settings_api.py`(sonnet 예산 키 PUT 400·adaptive_models 페이로드·agent_max_output sonnet 유지). 전체 pytest(0002+0003) RC=0.
- Verification: 배포 후 PB-0008 — 관리 콘솔 '모델별 추론 예산'에서 sonnet 카드가 ①+guide-note(②③ 슬라이더 없음), haiku 카드는 ①②③ 그대로.
- Rollback: `_reasoning_budget_specs`/`_model_budget_specs` 를 `_thinking_models()` 순회로 복원 + admin.js guide 분기 제거(죽은 슬라이더 재노출).
- Cross-ref: shared/feature-0002 MODIFY 동일 slug · REVIEW-20260724T085937-sonnet-reasoning-budget-guide · model_catalog.effort_for_reasoning_level/model_thinking_style · 선행 CHG-20260707T130000-reasoning-budgets · [[project-sonnet5-oauth-frontier-identity-gate]] H5 이연 해소 · ANCHOR 0003 무충돌.
## CHG-20260724T085937-sonnet-reasoning-budget-guide-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- Date: 2026-07-24. main 8f7b148f 배포(web+worker 재빌드) 후 실 Windows Chrome + https://localhost/admin PB-0008 **PASS**: sonnet 카드=①+guide-note(②③ 슬라이더 부재), haiku 카드=①②③, 라이브 API `adaptive_models=["claude-sonnet-4"]`(budget/reasoning 는 haiku만), 콘솔 에러 0. test-runs.d fragment 결과 기입.
- Cross-ref: CHG-20260724T085937-sonnet-reasoning-budget-guide(정본) · test-runs.d/20260724T085937-sonnet-reasoning-budget-guide.md.
## CHG-20260724T1830-share-point-rail-bars-postverify (POST-DEPLOY 공유링크 라이브 검증, 비-정책 doc-only)
- POST-DEPLOY PB-0008 공유링크 라이브 PASS(배포본 c1358190): 공유 뷰 rail 14 뱃지 막대(범위 비례)·클릭 위치 비례(상단 62/하단 1551). 메인 뷰와 동일 막대 형식. 사용자 요구 실증. 코드 0(스크린샷 evidence 추가).
- Files: `docs/test-runs.d/20260724T180649-share-point-rail-bars.md`, `docs/test-runs.d/evidence/share-rail-bars-live.png`, `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`.
## CHG-20260724T180458-sql-md-highlight — assistant markdown 답변 ```sql``` 코드블록 구문 하이라이트 (Minor §12.3, frontend-only)
- **요청(사용자, /_template:entry arg-given)**: assistant 가 md 로 쿼리를 전달할 때 SQL 하이라이트가 적용된 상태로 전달하도록 구성 (현재 plaintext 로 렌더되어 가독성 저하).
- **원인**: 렌더 파이프라인(`markdownToHtml`=`marked.parse`→`enhance*Blocks`→`DOMPurify.sanitize`)에 syntax highlighter(highlight.js/prism) 부재 → ```sql``` 블록이 `<pre><code class="language-sql">` 로만 렌더돼 색 없는 monospace(plaintext) 로 보임.
- **변경**: 경량 SQL 토크나이저 `enhanceSqlBlocks(html)` 신설(외부 vendor 무추가) — 기존 `enhanceDiffBlocks` 패턴 정합. comment/string/number/keyword/type/function(`(`휴리스틱)/variable 을 `<span class="sql-tok-*">` 로 감싸고(토큰 텍스트는 `textContent` 로만 주입 → XSS 무첨가·DOMPurify 통과), lang 필터(sql/mysql/tsql/postgresql 등)로 diff/mermaid/attachment 와 disjoint.
- **Files**: `src/static/app.js`(`enhanceSqlBlocks`/`highlightSqlInto`+`SQL_HL_LANGS/KEYWORDS/TYPES`, `markdownToHtml` 체인 배선) · `src/static/share.js`(공유 뷰 로컬 미러 + `renderMarkdownContent` 체인 배선 — diff/attachment 헬퍼와 동일하게 share 번들 로컬 복제) · `src/static/styles.css`(`.message-content pre.sql-block .sql-tok-*` Tokyo Night 팔레트 + 사용자 말풍선 sql-block 다크 배경 고정) · `src/static/share.css`(`.share-message-content pre.sql-block .sql-tok-*`).
- **Verification**: headless chromium(chromium-1208 via playwright) 실 vendor(marked+DOMPurify) 파이프라인 **23/23 PASS**(토큰화·텍스트 무손실·DOMPurify span/class 보존·XSS 라이브 DOM 무력화·비-SQL 블록 disjoint·getComputedStyle 색 실측) · `node --check` app.js·share.js PASS · 시각증거 `docs/evidence/sql-md-highlight-20260724.png`. 정적 자산 web 이미지 baked → 라이브 PB-0008 = POST-DEPLOY(visual_verification_scope: always).
- **잔여**: verify-completion → commit → PR → merge → deploy-web → POST-DEPLOY PB-0008(Windows-browser).

## CHG-20260724T184500-sql-md-highlight-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — sql-md-highlight(PR #946·main 0313b135) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260724T180458-sql-md-highlight.md 에 POST-DEPLOY 결과(Windows-browser PASS) append + REPORT 완결 + TASK 최종 체크박스 + REVIEW REV-20260724T184500-sql-md-highlight-postverify(§12.2 deploy 근거 포함) + evidence/pb0008-sql-highlight-live-20260724.png.
- 실측(실 Windows Chrome/150, https://localhost/ bootstrap_admin): 배포본 markdownToHtml → sql-tok 26토큰·Tokyo Night 색 정확·텍스트 무손실·script 0. 사용자 요청 라이브 해소 확인.

## CHG-20260727T010501-doc-sync-rn-0727 (TASK-20260727T010501-doc-sync-rn-0727 — 07-24 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` releases head 에 "2026-07-24" 블록 prepend(8항목 improved/work 4·fixed/work 2·improved/admin 1·fixed/admin 1) + generated 2026-07-23→2026-07-24. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py`(Dockerfile:39) + deploy-web.sh `asset_stamp_verify`(:788) 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침). wrapper 헤더의 수기 bump 지시는 07-12 이전 regime → 부적용(현행 코드로 재검증).
- 근거 정본: owning POST-DEPLOY 커밋(sql 35d6453f·csv 8bf643e0·reanswer 28ec78b3·newfolder f697eddf·share-scroll 5c9d5bf2·share-rail 6290ae1e·metadata-review c7e928c8·graph-emoji 791d5761) + git log 29ef0baf..HEAD.
- 제외: conv-menu-order/attachment-new(POST-DEPLOY 부재)·sonnet-reasoning-budget-guide(모델 튜닝 노브)·feature-0025(운영자 노브+PB-0008 미검증)·feature-0007(모델 라우팅)·feature-0021(내부)·feature-0023(개발자 API)·model-canonical/convaudit(내부).
- Verification: `node --check` PASS · vm 구조검증(releases +1·2026-07-24 head 8항목·2026-07-23 보존·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).
## CHG-20260727T105326-web-postprocess-gate — 첨부 후처리 web 게이팅(증거 기반) + worker 결과 전달 (Major §12.3, cross-ref feature-0002 primary)
- **What**: 첨부 후처리 소유자가 ask-worker 로 이전됨에 따라(primary CHG-20260727T105326-worker-attachment-postprocess) web `/api/ask` 의 후처리 4곳(materialize 2 + strip 2)을 **증거 기반 게이트**(`_raw_block_left`: 저장 답변에 블록이 남아 있을 때만 수행)로 감싸고, worker 가 만든 첨부 목록을 응답으로 forwarding. `_update_assistant_message_content` 는 성공 여부 bool 반환(§18.8 MINOR).
- **Why**: (a) worker 모드에서 web 이 빈 목록으로 strip 하면 블록만 지워 저장돼 첨부가 영영 생성되지 않고 본문 소실(§18.8 BLOCKER) (b) 모드-only 게이팅은 혼합 버전 배포 창에서 같은 결과(§18.8 MAJOR) → 증거 기반이면 정상 경로 no-op·비정상 경로 self-heal.
- **Files**: `src/routers/conversations.py`, `src/routers/_conv_store.py`(`_build_worker_agent_result` 첨부 키).
- **Verification**: pytest 2384 PASS(web 게이팅 계약 테스트 포함) · §18.8 2라운드. **배포는 워커 포함 전체 스코프**(`--web-only` 금지).
## CHG-20260727T102027-sql-diff-highlight — ```diff``` 코드블록 내 SQL 구문 하이라이트 (Minor §12.3, frontend-only, sql-md-highlight 후속)
- **요청(사용자, /_template:entry arg-given)**: "diff 구문을 나타내는 부분에서도 SQL 하이라이트가 적용되도록 구성해주세요."
- **원인**: 직전 sql-md-highlight 는 ```sql 블록만 처리. `enhanceDiffBlocks` 는 각 diff 라인 코드를 plain textContent 로만 넣어 diff 내 SQL 이 색 구분 안 됨(+/-/context 색만).
- **변경**: ① SQL 토크나이저 코어를 `sqlTokenizeToFragment(text)→DocumentFragment` 로 추출(```sql·diff 공용), `highlightSqlInto` 는 wrapper. ② `looksLikeSql(text)` 게이트(verb 핵심 DML/DDL ∧ clause SQL 구조 키워드, \b 경계로 camelCase 오탐 억제) — SQL diff 에만 적용해 비-SQL 파일 diff 오색칠 방지. ③ `enhanceDiffBlocks`: sqlMode 면 diff 라인 코드를 `sqlTokenizeToFragment` 로 토큰화(textContent-only, XSS 무첨가) + `pre.diff-sql` 마킹. add/del 은 배경 tint·좌측 border·gutter 마커로 유지, 라인 평문색은 기본색(토큰이 syntax색 — GitHub 식). 비-SQL diff 는 기존 그대로.
- **Files**: `src/static/app.js`(sqlTokenizeToFragment/highlightSqlInto/looksLikeSql/enhanceDiffBlocks) · `src/static/share.js`(동일 로컬 미러) · `src/static/styles.css`(`.sql-tok-*` 셀렉터 일반화 `pre.sql-block`→`.message-content .sql-tok-*` + `.diff-block.diff-sql .diff-line { color:#c0caf5 }`) · `src/static/share.css`(동일, `--share-code-fg`).
- **Verification**: headless chromium(chromium-1208, 실 vendor) **21/21 PASS**(회귀·SQL diff 하이라이트·add/del 보존·평문 기본색·배경 tint·텍스트 무손실·비-SQL diff 무영향·게이트 오탐억제·XSS 무력화) · `node --check` · §18.8 [SUBAGENT] 적대 패널 · 시각증거 evidence/sql-diff-highlight-20260727.png. 정적 자산 web baked → 라이브 PB-0008 = POST-DEPLOY(visual_verification_scope: always).
- **잔여**: verify-completion → commit → PR → merge → deploy-web-only → POST-DEPLOY PB-0008.

## CHG-20260727T110000-sql-diff-highlight-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — sql-diff-highlight(PR #948·main 8d69490c) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260727T102027-sql-diff-highlight.md POST-DEPLOY 결과(Windows-browser PASS) + REPORT 완결 + TASK 최종 체크박스 + REVIEW REV-20260727T110000-...(§12.2 deploy 근거) + evidence/pb0008-sql-diff-live-20260727.png.
- 실측(실 Windows Chrome/150, https://localhost/ bootstrap_admin): 배포본 SQL diff → diff-sql·sql-tok 9·Tokyo Night 색 정확·hunk 미토큰화·add/del 구분·script 0. 사용자 요청 라이브 해소.

## CHG-20260727T113640-model-persist — 대화별 "마지막 요청 모델" 보존 + '+ 새 대화'는 haiku 유지 (Minor §12.3, web/UI + backend additive)
- **요청(사용자, /_template:entry arg-given)**: "대화 중 assistant 에게 마지막으로 요청했던 모델을 기준으로, 새로고침이나 다른 대화에서 돌아왔을 때 그 선택을 보존. 다만 '+ 새 대화' 로 선택되는 모델은 haiku 그대로."
- **원인**: `state.selectedModel` 이 메모리 전용 전역이라 ① 새로고침 시 소실(기본값 복귀) ② 대화를 바꿔도 전역값이 남아 직전 대화 모델이 다른 대화로 누출 ③ 선택 후 '+ 새 대화' 를 눌러도 그대로 이어져 "새 대화는 haiku" 계약 파손. 추론 강도는 이미 대화별 KV 영속 + `/api/history` hydration 이 있었으나 모델엔 대응 경로 부재.
- **변경**:
  - `src/routers/conversations.py`: `_model_kv_key(account)` 신설(키 = `model:<account_id>` — 그룹 대화 계정별 격리). `ask()` 가 `model_explicit`(클라이언트 명시 여부) 일 때만 KV 저장하되 **세션 기본값과 같으면 빈 값으로 해제**(기본값 이탈만 저장 → 이후 기본 모델 상향이 기존 대화에 반영됨). `history()` 가 저장값을 payload `model` 로 반환(`_is_safe_model_name`+`_is_allowed_api_model` 재검증, `_display_window == "DENY"` 면 미반환).
  - `src/static/app.js`: `loadHistory` 비-append 로드에서 `payload.model` hydration(+`_updateComposerModelLabel`/`_renderComposerModelMenu`). `_modelHydrationShouldSkip(state, convId)`(미전송 선택 보존 판정)·`_resetComposerModelSelection(state)`(컨텍스트 이탈 리셋) 순수 함수 2종 신설. 리셋 호출 4곳 — `beginPendingConversation`·`selectConversation`(전환 즉시, 대기 창 오귀속 차단)·`loadHistory` 활성대화없음 분기·`handleLogout`. 모델 선택 핸들러가 `_modelPickedAt`/`_modelPickedForConvId` 기록. pending 대화 entry 에 요청 모델 캡처 + `_switchToPendingConversationContext` 복원.
  - `src/static/index.html`: composer 모델 라벨 초기 텍스트 하드코딩 `claude-sonnet-4` → 중립 placeholder(카탈로그 로드 실패 시 실제 사용 모델과 다른 값 노출 방지).
- **의도적 비대칭**: 추론 강도와 달리 모델은 localStorage 미러를 두지 않는다 — 미러가 있으면 새 대화가 직전 모델을 상속해 사용자 요구를 깬다. `verify_model_persist.mjs` S3/S3b 가 이 비대칭을 고정(대조군 포함).
- **Files**: `src/routers/conversations.py`, `src/static/app.js`, `src/static/index.html`, `tests/test_model_persist.py`(신규), `tests/verify_model_persist.mjs`(신규), `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260727T113640-model-persist.md`.
- **2R 적대 리뷰 반영(추가 변경)**: `loadHistory` 랜딩 분기 리셋을 미전송-선택 가드로 감쌈(B-B 자체 회귀) · `_shouldSendModelField` 신설 + `askBody.model` 조건부 동봉 + `_modelHydratedForConvId` 추적 + `moveConversationToFolder` 에 `loadHistory()` 추가(C-A clobber 차단) · `_composerCurrentModel` 최종 fallback `claude-sonnet-4`→`claude-haiku-4`(C-B) · 모델 메뉴 재렌더를 열린 상태로 한정(C-C) · `_model_kv_key` 식별불가 시 fail-closed 빈 키 + 저장·복원 skip(C-D).
- **Verification**: `test_model_persist.py` 14 PASS · `verify_model_persist.mjs` 32 PASS · `node --check`·`py_compile`·ruff PASS · `make test` 전체(신규 포함 PASS; 선존 FAIL 4건은 clean main 84f2e5ab 에서도 동일 재현 — 본 변경 무관) · §18.8 [SUBAGENT] 적대 패널 2라운드(1R BLOCK → B1/C1/C2/C3/C4 수정 후 재검증).
- **스키마/RBAC**: 0(기존 memory KV 재사용, 신규 엔드포인트 0, `/api/history` 응답 필드 1개 additive — 구 클라이언트 무시). cache-buster `?v=dev` 고정(빌드 자동주입 regime).
- **잔여**: verify-completion → commit → PR → merge → deploy-web → POST-DEPLOY PB-0008(AC-MP-1~3 라이브).

## CHG-20260727T124500-model-persist-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — model-persist(PR #953·main 8cfa00b0) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260727T113640-model-persist.md POST-DEPLOY 결과(Windows-browser PASS) + REPORT 완결 + TASK 최종 체크박스 + REVIEW REV-20260727T124500-postverify(§12.2 deploy 근거) + evidence/pb0008-model-persist-{restore,newconv}-20260727.png.
- 실측(실 Windows Chrome/150, https://localhost/ bootstrap_admin, 배포본 8cfa00b0): AC-MP-1 재로드 복원(`payload.model=claude-sonnet-4` + 라벨 `모델: claude-sonnet`)·AC-MP-2 대화 간 격리/복귀·AC-MP-3 '+ 새 대화'=`claude-haiku`. **AC-MP-9 라이브 미검증 — 유발 트리거가 파괴적/유발 불가, 단위검증만 커버(사유 명시)**. 사용자 요청 라이브 해소.

## CHG-20260727T160748-product-picker-scroll — 제품 선택 드롭업 열림 시 선택 제품 중앙 스크롤 (Minor §12.3, frontend-only)
- **요청(사용자, /_template:entry arg-given)**: "작업화면 내 제품(Product)를 선택하는 리스트에서, 현재 선택한 product 가 중앙에 위치하도록 스크롤을 위치시켜주세요. 현재는 항상 최상단에 위치하여 기존에 선택한 제품에서 상대적인 위치를 찾기 불편합니다."
- **원인**: `openProductDropup()` 은 열 때마다 `renderProductDropupMenu()` 로 항목 DOM 을 새로 만들어 `scrollTop` 이 0(최상단)으로 시작한다. `.product-dropup-menu` 는 `max-height:320px; overflow-y:auto`(styles.css) 라 제품이 많으면 선택 항목이 스크롤 밖에 남는다 — 선택 상태를 나타내는 `is-selected`(배경+체크)는 있으나 화면에 보이지 않는다.
- **변경(`src/static/app.js`)**:
  - `scrollProductDropupToSelected(menu)` 신설 — `menu.querySelector(".product-dropup-item.is-selected")` 의 `offsetTop - (menu.clientHeight - offsetHeight)/2` 를 `[0, scrollHeight-clientHeight]` 로 clamp 해 `menu.scrollTop` 에 설정. 선택 항목·menu 부재는 조기 return(무간섭).
  - `openProductDropup()`: 메뉴 표시 후 검색 입력 `focus()` → `focus({ preventScroll: true })` 로 변경하고, 그 뒤에 중앙 정렬 호출(포커스發 브라우저 자동 스크롤과의 충돌 차단 + preventScroll 미지원 폴백 순서).
  - `renderProductChip()`: 메뉴가 열린 상태의 재렌더 분기에서 `renderProductDropupMenu()` 직후 중앙 정렬 재호출(재렌더가 scrollTop 을 0 으로 리셋하므로 복원).
- **미채택**: `scrollIntoView({block:"center"})` — 조상 스크롤 컨테이너(페이지/messageLog)까지 스크롤해 컴포저 화면이 튄다. 메뉴 자신의 `scrollTop` 만 직접 계산·설정.
- **Files**: `src/static/app.js`, `tests/headless/verify_product_dropup_scroll.py`(신규), `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260727T160748-product-picker-scroll.md`, `docs/evidence/product-dropup-scroll-{before,after}-20260727.png`(신규).
- **Verification**: `tests/headless/verify_product_dropup_scroll.py` **11/11 PASS**(실 chromium 145 레이아웃 + 실 app.js 함수 원문 추출 + 실 styles.css — offsetParent 계약·중앙 정렬 ±1px·가시성·상/하단 clamp·무선택 무간섭·짧은 목록·menu 부재 무예외·검색칸 유무 양 경로) · `node --check app.js` PASS.
- **스키마/RBAC/백엔드**: 0 (프론트 표현계층 단독, 엔드포인트·응답 shape 무변경). cache-buster `?v=dev` 고정(빌드 `inject_asset_stamp.py` content-hash 자동주입 regime — 수기 bump 불요).
- **잔여**: verify-completion → commit → PR → merge → deploy-web → POST-DEPLOY PB-0008(AC-PPSC-1~3 라이브).

## CHG-20260727T163000-product-picker-scroll-ci-fix — 헤드리스 검증 스크립트 rename (CI pytest 수집 회피, 런타임 코드 0)
- **원인**: `tests/headless/test_product_dropup_scroll.py` 가 pytest 기본 수집 패턴(`test_*.py`)에 걸려 CI(`pytest -q unit/feature-0002-agent-core/tests unit/feature-0003-agent-web-ui/tests`)가 import → 러너에 playwright 미설치라 `ModuleNotFoundError: No module named 'playwright'` collection error(exit 2)로 전체 test job FAIL. 본 cycle 이 직접 유발한 red.
- **변경**: `tests/headless/test_product_dropup_scroll.py` → **`tests/headless/verify_product_dropup_scroll.py`** (`git mv`). 프로젝트의 브라우저 검증 스크립트 관례(`tests/verify_*.mjs`)와 동일한 `verify_` prefix — pytest 수집 대상에서 벗어나고, 헤드리스 실행은 명시 호출로 유지. 스크립트 본문·문서 내 경로 참조 동반 갱신(FUNCTION/TASK/REVIEW/REPORT/test-runs.d).
- **런타임 코드 변경 0** — `src/static/app.js` 무변경(제품 드롭업 동작 불변).
- **Verification**: rename 후 `PLAYWRIGHT_BROWSERS_PATH=… python3 tests/headless/verify_product_dropup_scroll.py` **11/11 PASS** 재확인 · `ruff check` PASS · pytest 수집 패턴 확인(pyproject 에 `python_files` 커스텀 없음 → 기본 `test_*.py`/`*_test.py` 만 수집).

## CHG-20260727T165500-product-picker-scroll-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — product-picker-scroll(PR #955·main b30bb45d) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260727T160748-product-picker-scroll.md POST-DEPLOY 결과(Windows-browser PASS) + TASK 최종 체크박스 + REPORT 완결 + REVIEW REV-20260727T165500-postverify(§12.2 deploy 근거) + evidence/pb0008-product-picker-scroll-live-20260727.png.
- 실측(실 Windows Chrome/150.0.7871.115, https://localhost/ bootstrap_admin, 배포본 b30bb45d): AC-PPSC-1 중앙 정렬(제품 17개 중 index 8 선택 → scrollTop 254 · **centerDelta 0** · fullyVisible)·AC-PPSC-2 양단 clamp(마지막 항목 선택 시 scrollTop 447 == maxScroll)·AC-PPSC-3 검색 입력 자동 포커스 유지·페이지 에러 0. 서빙 반영 확인(`typeof scrollProductDropupToSelected === "function"`, asset stamp `?v=c121d0831994`). 사용자 요청 라이브 해소.

## CHG-20260727T180036-share-bar-layout — 공유 대화 뷰: 액션 하단 바 우측 이동 + 조회수 상단 이동 + 바 hover 확장 (frontend-only)
- `src/static/share.html`: `.share-actions`(shareCopyLinkBtn·shareJoinBtn·shareForkBtn·shareLoginLink) 블록을 `<header class="share-header">` 에서 `<footer class="share-footer">` 안 `.share-footer-note` 뒤로 이동 · `#shareViewCount` 를 footer 에서 헤더 `.share-meta` 마지막 항목으로 이동(class `share-footer-stats` → `share-meta-item`). 요소 id·구성·조건부 `hidden` 불변.
- `src/static/share.css`: `.share-footer` 에 `align-items:center`·`flex-wrap:wrap`·`gap:6px 16px`·`transition(padding/background/box-shadow .18s ease)` 추가 + 세로 패딩 8→6px · `.share-footer-note{flex:1 1 auto;min-width:0}` 신설 · 액션 버튼 3종 + `.share-copy-link-btn` 기본 규격 축소(`padding:2px 10px`·`0.75rem`·`line-height:1.35`·`white-space:nowrap`) + 확장 transition · `@media (hover:hover)` 에 `.share-footer:hover, .share-footer:focus-within` 확장 규칙(패딩 10px·버튼 `6px 13px`/`0.8125rem`·배경 `#fff`·상단 그림자) · `@media (hover:none)` 터치 상시 확장 규격 · `prefers-reduced-motion` transition off · `.share-container` padding-bottom 유지(80px, 모바일 96px) · 반응형 600px 에서 안내문/액션 2줄 접힘 정합.
- `tests/test_share_bar_layout.py`(신규): 정적 구조 회귀 5 케이스(L1 액션 footer 소속·L2 조회수 헤더 meta 소속·L3 액션 4종 id 보존·L4 바 정렬 규칙·L5 기본 높이 유지 + hover/focus 확장 + transition + 터치/reduced-motion 분기).
- `tests/headless/verify_share_bar_layout.py`(신규): 실 share.html + 실 share.css 를 chromium 에 올려 좌표·높이 실측 8 케이스. **변경 전 기준값은 `git show main:...` 로 꺼낸 원본을 같은 방식으로 렌더해 비교**(바 높이 35.0 → 35.2px).
- 백엔드·엔드포인트·RBAC·스키마·마이그레이션·`share.js` 변경 0.

## CHG-20260727T182000-share-bar-layout-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — share-bar-layout(PR #958·main 486a587c) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260727T180036-share-bar-layout.md POST-DEPLOY 결과(Windows-browser PASS) + TASK 최종 체크박스 + REPORT 완결 + REVIEW REV-20260727T182000-share-bar-layout-postverify(§12.2 deploy 근거) + evidence/pb0008-share-bar-layout-live-{default,hover,header,copied}-20260727.png 4건.
- 실측(실 Windows Chrome/150.0.7871.115, relay 브리지 `http://172.26.144.1:9223`, 로그인 상태로 `https://localhost/share/<token>` — join/fork 노출 경로까지 커버, 서빙 배포본 **66575331**(⊇ 486a587c, 검증 중 다른 cycle 이 PR #959 를 배포), asset stamp `share.css?v=9e94270c8829`): **AC-SBL-1** 액션 4종(`링크 복사`·`대화에 참여`·`내 계정에서 fork`·로그인 링크[hidden]) 이 `.share-footer` 내부·`actions.x=956 > note.x=16`·바 우측 여백 **16px**, 헤더에 `.share-actions` **0** · **AC-SBL-2** `조회 16회` 가 헤더 `.share-meta` 4번째 항목(`소유자 admin`·`범위: 대화 전체`·`제품 국내 웹 - QA`·`조회 16회`), y=96 < 바 y=801 · **AC-SBL-3** 기본 바 높이 **35px**(pre-commit 헤드리스 35.2px 와 정합, 변경 전 35.0px) · **AC-SBL-4** hover 시 **53px**(패딩 6→10px·버튼 22→32px·배경 `rgba(255,255,255,.96)`→`rgb(255,255,255)`·상단 그림자 부여), `transition: padding/background/box-shadow 0.18s` · `링크 복사` 클릭 → 텍스트 `복사됨 ✓` + class `is-copied` · 최하단(`scrollY=maxY=8303`)에서 마지막 메시지 bottom **732** < 바 top **783**(hover 시)로 미가림 · `elementFromPoint` hit-test 가 `shareCopyLinkBtn`/`shareForkBtn` 반환(바 위 요소가 클릭 가로채지 않음) · 페이지 에러/`console.error` **0**.
- **검증 위생**: 라이브 부작용 최소 — 읽기 전용 조작만 수행하고 `내 계정에서 fork`(신규 대화 생성)·`대화에 참여`(그룹 멤버십 변경) 는 **클릭하지 않고** 노출·좌표·hit-test 로만 확인했다. `링크 복사` 는 클립보드 쓰기뿐이라 클릭. 공유 링크 조회수는 열람 자체로 10→16 증가(정상 계측).

## CHG-20260727T234439-model-picker-copy (모델 선택기 중복 문자열 제거 + 설명 축약 + 한국어 어절 줄바꿈, Minor §12.3)
- Date: 2026-07-27. 사용자 지적: "모델을 선택하는 화면에서 부자연스러운 줄바꿈이 나타나 가독성이 좋지 않습니다. 겹치는 문자열을 제거하고 의미 또한 간단명료하게 축약해주세요."
- 진단(실 Windows 브라우저 실측, 배포본 870e1496): 메뉴 폭 360/desc 326px 에서 opus desc 51자가 **2줄**로 감기고, 한국어 기본 줄바꿈이 음절 사이에서 끊겨 단어 중간("작|업")에서 갈라졌다(`word-break: normal`). 또 label(`claude-opus`)·group 배지(`Claude`)·desc(`Anthropic Claude Opus`) 가 **같은 단어를 3중 반복**하고, `frontier` 가 opus·sonnet 2행에 중복됐다.
- 변경 ①(`shared/model_catalog.py`): `API_MODEL_OPTIONS` 3개 `description` 을 label·배지와 겹치지 않는 **차별점만** 담아 축약 — `최상위 성능 · 장기 추론과 복잡한 분석`(22자) / `고성능 · 품질과 속도의 균형`(16자) / `빠르고 경제적 · 기본값`(13자). 세 tier 가 나란히 보이는 UI 라 **동일 축(성능 등급 · 용도)으로 병렬** 서술해 비교 가능하게 했다.
- 변경 ②(`unit/feature-0003-agent-web-ui/src/static/app.js` `_renderComposerModelMenu`): label 이 group 명으로 시작하면 group 배지를 **조건부 생략**. 무조건 제거가 아니라 중복일 때만 — Local LLM 등 provider 가 섞이는 카탈로그에서는 label 접두가 달라 배지가 그대로 살아 구분 기능을 유지한다.
- 변경 ③(`unit/feature-0003-agent-web-ui/src/static/styles.css` `.composer-model-item-desc`): `word-break: keep-all`. 문구 단축과 **별개의 근본 가드** — 폭이 더 좁아지거나 문구가 길어져도 어절 경계에서만 끊긴다.
- 비-변경(의도): 모델 `value`·라우팅·권한·저장 대화·단가 키 전부 무변경. 표시 문자열 3개 + JS 조건 1줄 + CSS 1속성뿐.
- Verification: **PRE-COMMIT Windows-browser 실측** — BEFORE 2줄/1줄/1줄 + 배지 3개 → AFTER **전부 1줄** + 배지 0, 메뉴 높이 209→192px (test-runs.d/20260727T234439-model-picker-copy.md, evidence `docs/evidence/model-picker-copy-after-sim-20260727.png`). feature-0002+0003 전체 pytest rc=0 · `node --check` OK.
- Rollback: 3파일 revert(표시만 원복, 동작 영향 0).
- Cross-ref: REVIEW REV-20260727T234439-model-picker-copy · test-runs.d/20260727T234439-model-picker-copy.md · 선행 CHG-20260727T184425-opus5-model(본 desc 문구를 도입한 cycle).

## CHG-20260728T010301-doc-sync-rn-0728 (TASK-20260728T010301-doc-sync-rn-0728 — 07-27 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` 기존 "2026-07-27" 블록에 3항목 append(new/work 답변 모델 'claude-opus' + improved/common 공유뷰 하단바 우측·조회수 상단 + improved/admin 관계도 상세 DB단위 접기·'…외 N건' 제거) + block summary 아울러-절 증강. generated 2026-07-27 불변. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py`(Dockerfile:39) + deploy-web.sh `asset_stamp_verify`(:788) 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침). wrapper 헤더의 수기 bump 지시(index/admin `?v=<new>`)는 07-12 이전 regime → 부적용(현행 코드로 재검증, 351ed406 동일 판정).
- 날짜 관례: 07-27 배포분(block date=배포일, 351ed406=doc_sync 07-27 이 07-24 블록 생성)이라 신규 07-28 블록 아닌 기존 07-27 블록 append(same-deploy-day append 선례 85da43d9). generated=top-block date=07-27 불변.
- 근거 정본: owning POST-DEPLOY 커밋(opus5 413703b9·share-bar 486a587c/2ec5e0aa·detail-db-groups 66575331/42ee04d0) + git log 238065ff..HEAD.
- 제외: model-picker-copy(미배포)·change-reanalysis(백엔드 postverify 부재)·false-truncation(unverified-live)·feature-0026(측정 전용·사용자 가시 0).
- Verification: `node --check` PASS · vm 구조검증(releases[0] 2026-07-27 items 4→7·releases[1] 2026-07-24 보존·스키마·enum·누출0). 릴리즈노트 render 테스트(verify_release_notes.mjs)는 jsdom 미설치로 미실행(render 로직 미변경·데이터 정적검증 대체).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260728T024258-model-access-rbac (계정/역할별 LLM 모델 사용 권한 — 동적 `model.access.<value>` RBAC, **Critical §12.3**)
- Date: 2026-07-28. 사용자 요청("R2도 계정/역할 별 권한 범위를 구성해주세요"). 배경 = feature-0007 opus5-model 의 잔여 R2: Opus 도입으로 모델 tier 단가 격차가 5배(haiku $1/$5 ↔ opus $5/$25)로 벌어졌는데 카탈로그는 `conversation.ask` 보유자 전원에게 동일 노출돼 **사전 차단 수단이 없었다**(사후 관측만).
- **설계 결정 — 기존 패턴 재사용**: `product.access.<key>`(IsDynamic=1) 가 이미 "리소스별 접근 제어" 를 정확히 같은 모양으로 풀어놨다. 모델도 같은 축이라 `model.access.<value>`(GroupName='model_access') 로 붙이면 역할 편집기·계정 override 그리드·감사·pending→'모두 적용' UI 가 전부 따라온다 → **신규 테이블 0 · 마이그레이션 0 · 신규 UI 0**. 대안(WebRoles 에 AllowedModels JSON 컬럼)은 기존 권한 체계(override·상속·progressive disclosure·감사) 밖의 별 축이 되어 UI·감사·§10.7 pending 흐름을 전부 새로 만들어야 해 미채택.
- **기본 부여 = 전 역할**(사용자 결정 2026-07-28): 배포 시점 동작이 현행과 byte-동치(무회귀). 관리자가 콘솔에서 필요한 역할의 모델을 해제하는 방향.
- 변경 ①(`shared/model_catalog.py`): `MODEL_ACCESS_PERMISSION_PREFIX`/`_GROUP` 상수 + `model_permission_code(value)`/`is_model_permission_code(code)` + `__all__`. 코드 namespace 를 카탈로그 SSOT 에 둬 모델 추가 시 자동 확장(별도 매핑 테이블 없음). `shared/` 는 web_context 를 import 하지 않으므로 단방향.
- 변경 ②(`routers/_bootstrap_schema.py`): `_ensure_model_access_permissions(conn)` 신설 + fast path/slow-path catchup **2지점 호출**(제품 권한과 동형). ⚠️ **grant 는 권한 row 가 "새로 생성된 순간"에만** — `INSERT IGNORE` 의 `rowcount>0` 을 one-time 마커로 쓴다. 제품 권한(`DefaultRoleAccess=1`)은 매 부트스트랩 무조건 re-grant 하는데 그 방식이면 **관리자의 해제를 재기동/재배포가 조용히 되살려** 본 통제가 무력화된다(의도적 divergence, 테스트 G7 이 고정).
- 변경 ③(`web_context.py`): `_account_has_model_access(account, model, *, conn)` 판정 함수 + `_filter_models_for_account_access`. **fail-closed 기본**(row 등록 + 미보유 → False), **fail-open 은 좁게·시끄럽게**(권한 row 미등록/DB 오류 → 통과 + WARNING — "게이트 미설치"를 전원 차단으로 해석하면 신규 배포 첫 요청부터 전 대화 403 이 되는 더 큰 사고). `conn=None` 은 우회 차단(미보유 거부).
- 변경 ④(`web_context._account_permissions`): API 토큰(feature-0023) scope 교집합에서 `model.access.*` **면제**. scope 는 "어떤 *동작*" 축, 모델 tier 는 "계정 역할" 축 — 면제하지 않으면 이미 발급된 토큰(`Scopes='conversation.'`)이 전부 `/api/ask` 403 으로 죽고 모델 추가마다 토큰 재발급이 필요하다. 통제는 계정 권한 + 절대 denylist + ask() 게이트로 유지.
- 변경 ⑤(`routers/conversations.py` ask): `_is_allowed_api_model`(400, 카탈로그 축) 직후에 `_account_has_model_access`(**403**, 인가 축) 추가 — **단일 choke-point**. 재답변·'AI 로 고치기' 등 내부 재dispatch 는 모두 `ask()` 를 다시 타 자동 커버.
- 변경 ⑥(`routers/system.py` `/api/api-vault/options`): 인증 계정이면 `_filter_models_for_account_access` 로 카탈로그 필터(제품 목록 필터와 동형) — 표시·집행 동시 닫힘. 비인증·조회 실패는 필터 전 목록(fail-soft, 로그인 화면 프리로드 보존).
- 변경 ⑦(프론트 `admin.js`/`app.js`): `model_access` 그룹을 ORDER·LABELS·**operate section** 에 추가, app.js 는 prefix 추론(head='model')이 라벨 맵에 없어 '기타'로 떨어지므로 명시 매핑. `groupedPermissions` 의 `excludeDynamic` 을 **`group === "product_access"` 로 좁힘** — 원래 의도는 "전용 embedded UI 가 따로 렌더하는 그룹 제외"였는데 조건이 `is_dynamic` 전체라 모델 row 까지 사라졌다(product 동작은 완전 동일).
- 변경 ⑧(정책문서): `docs/CONVENTIONS.md §10.6` 화면별 section·group 키·라벨·동적 권한 절 갱신 · `docs/SECURITY.md §28` 신설(권한 모델·기본 부여·집행 경계 표·fail-open/closed 비대칭·API 토큰 상호작용·검증).
- Verification: 신규 단위 **25 PASS**(G1~G8) · feature-0002+0003 전체 pytest **rc=0** · `ruff` All passed · `node --check` OK. **POST-DEPLOY PB-0008(부여·해제 양방향) 잔여** — 사유: 권한 grid 의 모델 row 는 부트스트랩이 seed 한 동적 권한을 받아 렌더하므로 배포 前 시각검증이 성립하지 않는다(test-runs.d 에 명시).
- Rollback: 8지점 revert. 권한 row/grant 는 남지만 게이트가 사라져 현행 동작으로 복귀(무해).
- Cross-ref: REVIEW REV-20260728T024258-model-access-rbac · test-runs.d/20260728T024258-model-access-rbac.md · SECURITY §28 · CONVENTIONS §10.6 · feature-0007 REPORT §7 의 R2(본 CHG 로 해소).

## CHG-20260728T025614-model-access-seed-fix (모델 권한 seed SQL arity 수정 + 컬럼 길이 클립 + blast-radius 격리)
- Date: 2026-07-28. 선행 CHG-20260728T024258-model-access-rbac 배포(28fcd71f) 후 라이브에서 `model.access.*` 권한 row **0개** 발견 — 기능 조용한 미적용.
- 근본 원인: `_ensure_model_access_permissions` 의 `INSERT IGNORE INTO WebPermissions` 가 **placeholder 5개에 파라미터 4개**(`IsDynamic` 미바인딩) → `ProgrammingError: Not enough parameters for the SQL statement`. 라이브 로그 `[web.startup] seed catchup skipped: …` 로 확정.
- **왜 단위 테스트를 통과했나(진짜 결함)**: 테스트 더블 `_SeedCur.execute` 가 SQL 문자열만 분기하고 **arity 를 검증하지 않았다** — 실 드라이버가 하는 검사를 더블이 생략해 통과. 더블의 충실도(fidelity) 부족이 근본 gap.
- 영향 범위(실측): 예외가 `_ensure_seed_catchup` **말미**에서 발생하고 caller 가 잡아 로깅 → 같은 함수의 다른 seed 단계는 모두 선행 완료. 라이브 교차확인 — RoleId NULL 계정 0 · bootstrap_admin 존재 · 역할 8 · 권한 118 · product.access 19 · runtime_settings 스냅샷 정상. 게이트가 **fail-open(권한 row 미등록=미설치)** 로 설계돼 요청 경로는 현행 유지(403 폭주 없음) — 설계된 안전망이 실제로 작동, 손실은 기능 미적용 뿐.
- 수정 ①: `IsDynamic` 파라미터 바인딩(`1`) — arity 정합.
- 수정 ②: `Label`/`Description` **컬럼 길이 방어 클립**(VARCHAR 128/255). `_ensure_permission_catalog` 가 graph-perm-split 배포에서 실측·경고로 남긴 1406(Data too long) fragility 와 동일 축 — 모델 label 이 길어져도 seed 가 죽지 않게 선제 차단.
- 수정 ③: **호출 2지점 try/except 격리**. seeder 실패가 slow path 의 후속 단계(`_migrate_legacy_accounts_to_rbac`·`_ensure_bootstrap_admin`·`_seed_legacy_conversations`)나 catchup 함수 전체를 끌고 내려가지 않게 한다. 권한 seed 실패는 게이트 미설치로 흡수되는 **국소 사건**이어야 한다. 실패는 stderr 로 loud(조용한 skip 금지).
- 재발 가드: 테스트 더블이 `sql.count("%s") == len(params)` 를 **단정**(이 버그를 되돌리면 단위가 깨진다) + **G9 신설**(label 400자 fake 카탈로그 → Label<=128 · Description<=255 · IsDynamic==1 계약 고정).
- Verification: 단위 **26 PASS**(G1~G9) · 전체 pytest **rc=0** · ruff All passed. POST-DEPLOY: seed 성공(권한 row 3 + 전 역할 grant) 확인 + 선행 cycle 에서 이관한 **PB-0008 부여·해제 양방향** 검증.
- Rollback: 3지점 revert(단 seed 가 다시 실패 상태로 복귀).
- Cross-ref: REVIEW REV-20260728T025614-model-access-seed-fix · test-runs.d/20260728T025614-model-access-seed-fix.md · 선행 CHG-20260728T024258-model-access-rbac · SECURITY §28.

## CHG-20260728T031500-model-access-postverify (모델 권한 라이브 부여·해제 양방향 검증 종결 + 자기 잠금 경로 명문화)
- Date: 2026-07-28. 코드 변경 **0** — 배포 `8db72012` 에 대한 POST-DEPLOY 관측 기록 + 정책문서 1절 신설.
- 검증 ①(렌더·무회귀): 역할 편집기에 `모델 사용 (작업 화면) 3/3 선택` 그룹이 `제품 사용` 다음에 렌더, 3행(haiku·opus·sonnet) 전부 체크 — 사용자 결정 "전부 기본 부여" 그대로. 계정 편집기는 tri-state(`상속`/`허용`/`거부`) override + 그룹 배지 집계(`거부 1 · 상속 2`) 정상.
- 검증 ②(해제 쓰기): 역할 opus 해제 → `모두 적용` → `PATCH /api/admin/roles/2 200` → DB `model.access.claude-opus-5 7/8`, haiku·sonnet `8/8` 유지 → **해제가 대상 모델에만 적용**(그룹 붕괴 없음).
- 검증 ③(집행): 계정 override `거부` 후 `/api/api-vault/options` 에서 opus **소멸**, `POST /api/ask{model:"claude-opus-5"}` → **403** `이 모델을 사용할 권한이 없습니다…`. **대조군** 같은 계정·같은 시점 sonnet → **200** → 게이트가 모델 단위로 동작(광역 차단 아님).
- 검증 ④(재부여·원복): 역할 재체크 → `1건 적용됨` → DB `8/8` ×3 · `model_access` override **0행** · 선택기 3종 복귀. **최종 상태 = 검증 착수 전과 동일**.
- **신규 발견(코드 변경 없음, 문서화)**: TASK-0300 권한상승 가드(`본인이 보유하지 않은 권한은 설정할 수 없습니다`)가 `model.access.*` 에도 동일 적용돼 **관리자 자기 잠금 경로**가 생긴다 — 자기 계정에서 모델을 `거부` 하면 그 모델을 어떤 역할에도·자신에게도 재부여할 수 없다(`PATCH … 403`). `product.access.*` 와 동일 성질이며 **의도된 보안 동작**이라 가드는 손대지 않고, `docs/SECURITY.md §28.6` 에 운영 규칙(자기 계정 해제는 해당 모델 보유 관리자 2인 이상 환경에서만 / 통제는 역할 단위로)으로 명문화. 본 검증에서는 override 행 DELETE 로 복구 후 UI 재부여 200 확인.
- 문서: `docs/SECURITY.md §28.6` 신설 + §28.6→§28.7 번호 이동(검증 절에 G9·라이브 결과 반영) · feature-0007 `REPORT.md §7` 의 **R1·R2 해소 표기** · TASK 체크박스 4건 종결.
- Verification: 라이브 실측(win-browser PB-0008 + `repo-mysql-1` 직접 질의 + web 컨테이너 액세스 로그). 코드 무변경이라 회귀 표면 0.
- Rollback: 문서 revert (동작 영향 없음).
- Cross-ref: REVIEW REV-20260728T031500-model-access-postverify · test-runs.d/20260728T031500-model-access-pb0008.md · 선행 CHG-20260728T024258-model-access-rbac · CHG-20260728T025614-model-access-seed-fix · SECURITY §28 · feature-0007 REPORT §7.

## CHG-20260728T113819-usage-records-system (LLM 사용량 드릴다운 '사용 기록' 개편 — 시스템 사용분 편입 + 화면 이동)

TASK-20260728T113819-usage-records-system. branch `ai/claude/feature-0003-usage-records`.

- `shared/model_catalog.py`
  - `TASK_TAXONOMY`: 라이브 존재·미등록이던 4 task 편입 — `redteam`(답변 적대 검증) ·
    `enum_suggest`(ENUM 코드 후보) · `cluster_label`(콘텐츠 그룹 라벨) ·
    `product_classify`(제품 분류 제안). 부수효과로 ai-ops '미분류 AI 활동' Attention 에서 4건 해소.
  - 신설 `USAGE_TASK_NAV`(task → `{screen, subtab, target_kind}` SSOT) ·
    `_USAGE_NAV_DEFAULT`(미등록 task → AI 운영 현황 > 운영 현황) ·
    `USAGE_NAV_SCREEN_LABELS` · `USAGE_NAV_SUBTAB_LABELS` ·
    `usage_task_nav()` · `usage_nav_path_label()`.
- `unit/feature-0003-agent-web-ui/src/routers/admin_usage.py`
  - 신설 `_query_usage_system_records()` — 대화 목록의 **정확한 여집합**
    (`c.conversation_id IS NULL OR c.owner_account_id IS NULL`) 을 `(task, target, actor)` 로 집계.
    모델/일자 필터는 대화 목록과 동일 규칙(canonical family · 차트 버킷) → 두 목록의 합 = 막대 수치.
    `bool_or(c.conversation_id IS NOT NULL)` 로 실재 대화 여부를 함께 뽑아 **깨진 대화 링크 차단**.
  - 신설 `_usage_target_parts()` — `schema` / `schema.table` / `schema.table.column` /
    `schema.routine()` 4형식 파싱.
  - 신설 `_resolve_usage_target_scopes()` — `table_descriptions`(scope_key) ∪
    `routine_objects` ∪ `rag_objects`(datasource_key) union 으로 target→데이터소스 해소.
    객체 단위 우선, 실패 시 스키마 단위. 후보 2+ 는 **추측하지 않고** `scope_ambiguous`.
    해소 질의 실패는 fail-soft(rollback 후 포기 — 목록 자체는 보존).
  - 신설 `_usage_system_nav()` — nav 서술자(`screen/subtab/scope_key/scope_ambiguous/scope_hint/
    search/path_label`). `target_kind` 는 내부 분기 키라 응답에서 제거.
  - `admin_usage_conversations` — 응답에 `system_items`·`system_truncated` **additive**
    (기존 `items` 무변경 → 소비자 회귀 0). `(시스템)` 역할은 시스템만, 계정/일반 역할은
    시스템 제외(귀속 오도 방지). 시스템 질의 실패는 대화 목록을 깨뜨리지 않게 격리.
  - 상수 `_USAGE_SYS_LIMIT = 200`.
- `unit/feature-0003-agent-web-ui/src/app.py` — 신규 헬퍼 4종을 `app.<name>` 으로 rebind
  (`_query_usage_system_records`·`_resolve_usage_target_scopes`·`_usage_system_nav`·`_usage_target_parts`).
- `unit/feature-0003-agent-web-ui/src/static/admin.js`
  - 모달 명칭 "대화 목록" → **"사용 기록"**(제목·aria·로딩·빈상태·안내문·차트 hover 문구).
  - 대화+시스템 **통합 표**(구분 배지 열, 토큰 큰 순 병합 정렬). 시스템 행 = 작업 라벨 + 대상 객체 +
    이동 경로 안내 + 모호 표기. 주체 3분기(실재 대화 링크 / '삭제된 대화' / 워커명).
  - 신설 `applyUsageNav()` · `_usageResolveScopeKey()` · `_usageActorLabel()` —
    데이터소스 스코프 → 탭 전환 → 서브탭 → 검색어 주입. 미지 screen/subtab 은 fail-soft.
  - `(시스템)` 계정 막대 클릭이 `role="(시스템)"` 으로 모달을 열도록 복구(종전 early-return 무동작).
- `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.usage-rec-*` 토큰 신설.
  모달 **반응형** `width: min(1240px, 96vw)` + `body max-height: min(74vh, 820px)`.
  부수 열 `width:1%`+nowrap 으로 본문 열이 잔여 폭 흡수(과도 줄바꿈 해소).
  대상 식별자 `word-break: break-all` → `overflow-wrap: anywhere`(단어 중간 절단 해소).
  보조문구는 `--text-muted`(대비 4.12, AA 미달) → `--text-2`(7.11).
- 테스트 `unit/feature-0003-agent-web-ui/tests/test_usage_records_system.py` 신규(14 케이스) ·
  `test_usage_conversations.py::test_a2_system_role_empty` 갱신(의도적 동작 변경 — 대화는 여전히 빈
  목록이되 `system_items` 가 채워짐).

검증: 단위 2,591 passed / 2 skipped · ruff clean · 라이브 SQL 여집합 정합(897+14,476=15,373=전체) ·
PB-0008 라이브(잔여 2건 POST-DEPLOY). 마이그레이션 없음 · 신규 RBAC 없음 · 스키마 변경 없음.
