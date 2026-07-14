---
doc_type: MODIFY
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

> 이전 기록(102건): [MODIFY-archive-20260711T120531.md](./_archive/MODIFY-archive-20260711T120531.md)

## CHG-20260710T200000-ai-claude-feature-0016-catband-cull — §67 집계폐기+카테고리밴드규모+테이블뷰포트컬링 (2026-07-10)
- 대상: `admin.js`(_metaG6Build: aggActive 비활성·CATH 헤더·테이블/루틴/클러스터 컬링·팬훅) + `admin.html` 버스터 + headless `test_g6build_viewportcull.js`(테이블 컬링 반영)·`test_g6build_agglod.js`(집계비활성 잠금).
- 변경: (A1) 집계-카드 폐기(클러스터 펼침 유지) (A2) 카테고리 밴드 헤더 "N DB · M 테이블" (B) 화면 밖 테이블/클러스터 뷰포트 컬링.
- 근거: §65 배포 후 사용자 육안 피드백(집계=규모파악 어려움·줌인 perf 잔존, ADR-033). frontend-only.
- 검증: headless 6+8+회귀 = **150 PASS**·node --check. diff 2렌즈 적대 리뷰. win-browser 육안(TEST §67). 버스터 `admin.js?v=20260710-catband-cull`.


## CHG-20260710T210000-ai-claude-corp-feature-0016-reldedup — §69 상세 패널 관계 중복 병합 (2026-07-10)
- 대상: `unit/feature-0003-agent-web-ui/src/static/admin.js`(_metaGraphLoadNodeAnalysis: '연결 관계 추적' 블록+no-op bind 제거 · _metaGraphRelTraceRowsHTML 함수 삭제 · esc 주석 정정) + `styles.css`(dead `.admin-meta-graph-ai-rels` 제거) + `admin.html` 버스터(js+css).
- 변경: 상세 패널의 두 인라인 관계 섹션(#1 컬럼>참조함/참조받음, #2 AI 박스 '연결 관계 추적') 중 **#2 제거 → #1 로 일원화**. AI 박스는 역할 칩+prose 고유 가치만 유지.
- 근거: 사용자 요청("역할·작동 겹침 → 확인 후 병합") + 병합 방향 승인(AskUserQuestion 2026-07-10). #2 는 #1 과 동일 모델 REFERENCES 를 동일 동작으로 재렌더한 순수 중복. frontend-only·마이그 0·behavior: #2 제거 외 불변(우클릭 '관계 상세' 팝업 유지).
- 검증: `node --check` PASS · diff 13삽입/40삭제. POST-DEPLOY PB-0008 육안(feature-0003 TEST §69). 버스터 `admin.js?v=20260710-reldedup`·`styles.css?v=20260710-reldedup`.
## CHG-20260710T063659-ai-claude-feature-0016-graph-focus-selected — 상세 패널 "🎯 이 노드로 이동" 카메라 버튼 (2026-07-10)
- 대상: `unit/feature-0003-agent-web-ui/src/static/admin.js`(`_metaGraphRenderDetail` 상세 카드 헤더 마크업 + 렌더 직후 바인딩 블록) + `styles.css`(`.admin-meta-graph-card-head` `flex-wrap:wrap` — 리뷰 MINOR 반영) + `admin.html` 캐시버스터(admin.js·styles.css 2건).
- 변경: 상세 패널 카드 헤더의 `🔗 관계 상세` 옆에 `🎯 이 노드로 이동`(`id=metaGraphFocusSelBtn`) 버튼 추가. 클릭 시 현재 상세 노드(`self.key`)로 `_metaGraphAnimateFocus(key, _metaGraph._opSeq)` 호출 → 그래프 구조·선택 상태 불변, 카메라만 뷰포트 중앙으로 부드럽게 팬(+판독 줌 클램프). 미렌더 노드(접힌 스키마 등)면 `_metaRenderedIdFor` null 가드로 안내만 하고 팬 skip.
- 근거: 노드 단일클릭은 상세 패널만 갱신하고 카메라는 이동하지 않아(`_metaGraphShowDetail`), 큰 그래프에서 선택 노드를 화면에서 다시 찾기 어려웠음(빈틈). 기존 카메라-전용 팬 경로(`_metaGraphPanToRelation` §graphux7#2)를 재사용해 신규 기계장치 0. frontend-only·마이그 0·behavior 순수 추가(기존 관계 상세 버튼·동작 불변). 위험도 Minor(§12.3).
- UI 안전: 헤더 `.admin-meta-graph-card-head`(flex, gap:8px)에 `.amgr-link`(margin-left:auto) 버튼이 2개가 되어 auto 마진 2개가 여유공간을 분할하는 것을 방지 — 기존 `관계 상세`를 앞에 두어 그것만 우측 정렬시키고 신규 버튼은 `style="margin-left:0"`로 그 옆에 gap:8px 그룹화. **추가(리뷰 MINOR 반영)**: `.admin-meta-graph-card-head` 에 `flex-wrap:wrap` 부여(sibling `.cov-db-rule-card-head` 와 동일 패턴) — 좁은 패널 폭 + 유사도 배지 동시 존재 시 헤더가 가로로 넘쳐 신규 버튼이 가려지던 리스크를, 버튼이 다음 줄로 우아하게 래핑되도록 해소. `flex:none; white-space:nowrap` 유지로 버튼 자체는 잘리지 않음.
- 검증: `node --check admin.js` PASS · **diff 적대 리뷰 REV-20260710T063659 [SUBAGENT: PASS-WITH-FIXES]**(BLOCKING/MAJOR 0, MINOR 1=헤더 가로 넘침 → `flex-wrap:wrap` 로 수정, 핸들러·회귀 PASS) · **PB-0008 win-browser 시각검증은 POST-DEPLOY**(정적 자산 baked → merge + deploy-web 재배포 선행, §65·§66·§67 동일). 캐시버스터 `admin.js?v=20260710-graph-focus-selected` · `styles.css?v=20260710-graph-focus-selected`.


## CHG-20260710T223000-ai-claude-corp-feature-0016-reldedup-pd — §69 POST-DEPLOY 완수 기록 (docs-only, 코드 변경 0) (2026-07-10)
- 대상: `unit/feature-0003-agent-web-ui/docs/TEST.md`(§69 Run POST-DEPLOY append) + `unit/feature-0016-metadata-graph/docs/{TASK.md(T69.5 완료),REPORT.md(POST-DEPLOY 절),REVIEW.md([SKIPPED] 완수)}`. **코드/자산 변경 0**.
- 변경: §69 병합(PR #659 → main 5e235953)의 실 Windows Chrome POST-DEPLOY 실측 결과를 정본에 기록. 서빙 자산 curl(admin.js 실제 render producer 0·styles.css 실제 규칙 0) + 런타임 assertion(`typeof _metaGraphRelTraceRowsHTML==="undefined"`·유지 함수 3종 function·`.admin-meta-graph-ai-rels` DOM 0·버스터 20260710-reldedup·pageerror 0).
- 근거: `visual_verification_scope: always` 완료 게이트의 POST-DEPLOY 실측 기록 마감. 배포는 §69 cycle 에서 이미 완료(무중단 롤링·soak PASS). 코드 diff 부재 → §18.8 패널 SKIPPED(REVIEW 동일 기록).

## CHG-20260710T163512-ai-claude-feature-0016-graph-rtuse-camera — 상세 패널 사용관계 행 클릭 시 카메라 이동 (2026-07-10)
- 대상: `unit/feature-0003-agent-web-ui/src/static/admin.js`(`_metaGraphRenderDetail` 의 `[data-rtuse]` 클릭 핸들러 + 섹션 안내문) + `admin.html` 캐시버스터(admin.js 1건).
- 변경: 상세 패널 "사용 테이블/사용 함수·프로시저" 행(`[data-rtuse]` 버튼) 클릭 시 기존 `_metaGraphShowDetail(k)`(async 상세 전환)에 더해 `_metaGraphPanToRelation(k)`(동기 카메라 팬 + 대상 선택)를 **먼저** 호출. 안내문 "행 클릭 = 대상 상세." → "행 클릭 = 대상 상세 + 카메라 이동."
- 근거: §70(선택 노드 헤더 버튼)과 별개로, 관계 행 클릭이 상세만 바꾸고 카메라는 안 움직여 큰 그래프에서 대상 재탐색이 어려웠음. 기존 shipped 팬 래퍼(`_metaGraphPanToRelation`, graphux7#2) 재사용 → 신규 기계장치 0. frontend-only·마이그 0·behavior 순수 추가(상세 전환 불변, 미렌더 대상은 pan null 가드로 안내만·graceful). Minor(§12.3).
- 검증: `node --check admin.js` PASS · inline 적대 diff 리뷰 **REV-20260710T163512 [SKIPPED-panel/inline PASS]**(순서/race·미렌더 가드·selection idempotent·캐시버스터 확인, BLOCKING/MAJOR 0, NIT1 비가시 stale 힌트 수용) · **PB-0008 win-browser 시각검증은 POST-DEPLOY**(정적 자산 baked → merge + deploy-web 재배포 선행). 캐시버스터 `admin.js?v=20260710-graph-rtuse-camera`(CSS 미변경 → styles.css 미bump).
## CHG-20260710T065500-ai-claude-corp-feature-0016-graph-colnav — §72 상세 패널 관계행 단일클릭 미렌더 컬럼 카메라 이동 (2026-07-10)
- 대상: `unit/feature-0003-agent-web-ui/src/static/admin.js`(`_metaRenderedAncestorFor`·`_metaFocusKeyFor` 신설 + `_metaGraphPanToRelation` 재작성 + `_metaGraphSetSelected`·`_metaG6Build` 의 focusAdj 산출을 `_metaFocusKeyFor` 로 중앙화) + `admin.html` 캐시버스터 + headless `test_graph_colnav.js`(신설).
- 변경: `그래프 뷰 > 상세` 관계 행(컬럼) **단일클릭** 시, 소속 테이블 미펼침(컬럼 미렌더)이면 카메라가 이동하지 않고
  "대상 노드가 현재 화면에 없습니다" 안내만 떠 오류로 오인되던 결함 수정. (1) `_metaGraphPanToRelation` 이 대상을
  **화면상 가장 가까운 조상**(컬럼→소속 테이블→접힌 스키마 카드 `SC:`)으로 승격해 카메라 팬(펼치진 않음). (2) 선택 상태는
  대상 컬럼 키로 두되, **하이라이트 기준은 `_metaFocusKeyFor` 로 소속 테이블에 폴백**(선택=컬럼·하이라이트=상위 종속
  객체 — 사용자 결정 2026-07-10 AskUserQuestion). 폴딩은 부모가 모델의 Table 노드일 때만(§57.5 F2 'prune 선택 정리=null' 보존).
  더블클릭(`_metaGraphTraceRelation`=펼침+컬럼 선택) 불변. 접힌 스키마 카드로만 승격된 경우(대상=스키마)는 기존대로 팬만.
- 근거: 사용자 리포트(2026-07-10) — 단일클릭 시 미펼침 컬럼으로 이동 불가·오류성 메시지. frontend-only·마이그 0·behavior:
  미렌더 대상 승격 + 오류 톤 제거 + 하이라이트 폴딩만(렌더된 대상·스키마 카드 팬·일반 노드 선택 경로 불변).
- 검증: 신규 headless `test_graph_colnav.js` **22 PASS**(승격 5·키파싱 2·선택게이트 8·하이라이트폴딩 4·직접렌더) + 회귀 0
  (edge_visibility 71·agglod 8·category 26·collod 20·vpack 19·viewportcull 6 = 150 PASS)·`node --check` PASS. §18.8 적대 리뷰
  REV-20260710T065500(stale base 적발→rebase, MINOR#3→하이브리드 반영). POST-DEPLOY PB-0008 사용자 육안(TEST §72). 버스터 `admin.js?v=20260710-graph-colnav`.
## CHG-20260710T155200-ai-claude-feature-0016-nodeanalysis-caveats — §69 능동 분석 주의 계약 + 루틴 payload + 시드 커버리지 (2026-07-10)
- 대상(backend): `unit/feature-0002-agent-core/src/modules/llm.py`(NODE_ANALYSIS_PROMPT — caveats 계약/analyze-from-visible 규칙/Input JSON) · `unit/feature-0002-agent-core/src/modules/node_analysis.py`(_fetch_context routine_touches 수집 + 신규 `_fetch_routine_returns` + _build_payload touches/returns 투영) · **`shared/config.py`**(SCHEMA_CAP 200→1000·SCHEMA_MAX 500→2000·RUN_BUDGET_MAX 2500→4000·BATCH_PER_TICK 4→10).
- shared/ 단일 mutator(§13.2.2 F2): 본 cycle(브랜치 ai/claude/feature-0016-nodeanalysis-caveats)이 `shared/config.py` 의 AGENT_NODE_ANALYSIS_* 기본값 4건만 변경(다른 shared 심볼·타 세션 경합 없음). 순수 기본값 상향 — env 오버라이드 부재 소비자에만 영향.
- 변경: P1 caveats 자기-불평 제거(프롬프트) · P2 루틴 touches(read/write)+returns 투영 · P3 시드 캡 상향(대형 스키마 전량 시드).
- 근거: 사용자 전수 피드백(§69, ADR-034) — 주의가 "불명확" 자기-불평 대부분 + DB 단위 분석 미커버 tail.
- 검증: pytest PYTEST_RC=0(회귀 0) · 라이브 LLM(주의 자기-불평 전멸) · 라이브 payload(touches/returns). POST-DEPLOY cc_data_main 재생성(T69.5).
- §18.8 적대 리뷰(REV-20260710T165030 PASS-WITH-FIXES) 반영 2건: (a) `llm.py` NODE_ANALYSIS_PROMPT untrusted-data 규칙에 신설 top-level `touches`/`returns` 추가(DB 인트로스펙션 유래 식별자 프롬프트 인젝션 표면 봉인) (b) `unit/feature-0002-agent-core/tests/test_routine_dbanalysis.py` 에 `test_build_payload_routine_touches_returns` 신설(P2 투영·dedup·Table 미투영 회귀 가드) → 파일 23 PASS.

## CHG-20260710T175412-ai-claude-feature-0016-rtuse-camera-pd — §71 graph-rtuse-camera POST-DEPLOY 완수 기록 (docs-only, 코드 변경 0) (2026-07-10)
- 대상: `unit/feature-0016-metadata-graph/docs/{TASK.md(T71.3 완료),REPORT.md(POST-DEPLOY 절),REVIEW.md([SKIPPED] 완수)}` + `unit/feature-0003-agent-web-ui/docs/TEST.md`(§71 Run POST-DEPLOY append). **코드/자산 변경 0**.
- 변경: §71(PR #662 → main b7d7d871, 이후 라이브 a24415a5)의 실 Windows Chrome POST-DEPLOY 실측 결과를 정본에 기록. win-browser relay 로 mssql-web-qa `shop_pt.T_ItemInfo` 상세의 `[data-rtuse]` 행(18: 읽기 12·쓰기 6) 실클릭 → 카메라 중심 모델좌표 [3600,7092]→[2523,7871] 팬 + 상세 전환 동시, pageerror 0. 자산 curl(서빙 버스터·핸들러) 확증.
- 근거: `visual_verification_scope: always` 완료 게이트의 POST-DEPLOY 실측 기록 마감(T71.3). 배포는 §71 cycle 에서 이미 완료(병렬 Codex 세션 commit→PR#662→merge→deploy). 코드 diff 부재 → §18.8 패널 SKIPPED(REVIEW 동일 기록).
## CHG-20260710T233000-ai-claude-feature-0016-layoutmemo — §73 배치-정렬 함수 위상-서명 메모이즈 (2026-07-10)
- 대상: `admin.js`(_metaTopoSig 신규 · _metaG6Build 서명체크+relOrder/simGroups 캐시 · _META_CULL_MARGIN 0.6→0.3) + `admin.html` 버스터 + headless `test_g6build_layoutmemo.js`(신규 19).
- 변경: 근본원인(rebuild 마다 전체모델 배치계산 68~145ms — _metaRelOrderAll 55%+_metaSimGroups 45%) 해소. 위상(nodes/REFERENCES edges/schemaExpanded/mode) 무변경이면 순수 정렬 재사용 → 팬·줌·선택·컬럼토글·드래그 rebuild 를 방출 비용만 남김. cull 마진 축소로 고배율 방출 감축.
- 근거: §67 배포 후 사용자 피드백 "극단 줌인·비밀집인데도 느림 — 근본원인 해소"(win-browser 실측 함수분해, ADR-035). frontend-only, 결정론 불변(캐시 적중==fresh).
- 검증: headless 19(메모이즈)+150(회귀) = **169 PASS**·node --check. §18.8 적대 리뷰(REV §73 F1/F2 수정). POST-DEPLOY win-browser(TEST §73). 버스터 `admin.js?v=20260710-layoutmemo`.
## CHG-20260710T230000-ai-claude-feature-0016-minimap-reuse — §74 미니맵 전체-이미지 재사용 (2026-07-10) [머지 재번호 §70→§73→§74·ADR→ADR-036, §13.1]
- 대상: `unit/feature-0003-agent-web-ui/src/static/admin.js`(신규 `_metaMinimapGeomSig`·`_metaPatchMinimapReuse` + `_metaG6ApplyOnce` 서명 배선 + minimap `key:"minimap"` + `await g.draw()` 직후 patch + afterdraw 드래그 무효화) + `admin.html` 버스터 + 신규 `tests/headless/test_g6build_minimap_reuse.js`.
- 변경: G6 v5 minimap 전량 재복제 `renderMinimap()` 을 기하 서명 게이트로 감싸 상태-only rebuild 에서 미니맵 재복제 skip(전체-이미지 재사용). 구성 변경 시 정상 재복제. 팬/줌은 G6 가 마스크만 갱신(무영향). frontend-only·마이그 0.
- 적대 리뷰 2건 BLOCK→수정: H1(패치 init 시점 호출→plugin lazy-init 전 no-op)→draw 직후 이동, H2(드래그 stale 서명→미니맵 얼어붙음)→afterdraw stage 무효화.
- 검증: 신규 headless **35 PASS** + 회귀 150 PASS · `node --check` · 적대 리뷰(REVIEW REV-20260710T233000). POST-DEPLOY PB-0008(feature-0003 TEST §74). 머지 후 버스터 `admin.js?v=20260710-mmreuse-layoutmemo`.

## CHG-20260710T234500-ai-claude-feature-0016-layoutmemo-postdeploy — §73 layoutmemo POST-DEPLOY 완수 기록 (docs-only, 코드 변경 0) (2026-07-10)
- 대상: `unit/feature-0003-agent-web-ui/docs/TEST.md`(§73 Run POST-DEPLOY 라이브 PASS append) + `unit/feature-0016-metadata-graph/docs/{TASK.md(T69.4 완료),REPORT.md(POST-DEPLOY 절)}`. **코드/자산 변경 0**.
- 변경: §73(PR #667 → main e6b7b68f) 메모이즈의 실 Windows Chrome POST-DEPLOY 실측 결과를 정본에 기록. win-browser relay 로 mssql-qa-idc 882 노드 동일 위상 연속 build 함수분해 — MISS 59ms → HIT 8ms(relOrderAll/simGroups 0) 7.4× 급감, MISS↔HIT 좌표 이동 0(band-invariant), pageerror 0.
- 근거: `visual_verification_scope: always` 완료 게이트의 POST-DEPLOY 실측 기록 마감(T69.4). 배포는 §73 cycle 에서 완료. 코드 diff 부재 → §18.8 패널 SKIPPED.

## CHG-20260710T093000-minimap-reuse-postverify — §74 미니맵 재사용 POST-DEPLOY PB-0008 라이브 PASS 기록 (2026-07-10, 비-정책 doc-only)
- 배포 508fae50(web-a/web-b soak PASS) 후 win-browser.py relay(실 Windows Chrome 149, `https://localhost/admin` 로그인) 그래프 뷰 실측 결과를 TEST.md §74 Run + TASK.md T74.5 [x] 에 POST-DEPLOY 갱신.
- 실측 PASS: 미니맵 canvas 168×112+마스크 정상 렌더 · 줌 유지 · 스코프 전환(DK온라인 461테이블→건즈 173테이블) 시 미니맵 새 그래프로 재렌더(구성 변경 반영·얼어붙지 않음) · pageerror 0 · 서빙 자산 curl(버스터+함수) 확증. 상태-only skip·per-frame 드래그는 G6 canvas 합성이벤트 미등록으로 headless D 10테스트로 lock.
- Files: `feature-0016/docs/{TASK,MODIFY,REVIEW}.md` + `feature-0003/docs/TEST.md` (doc-only). 코드·자산 변경 0. 원천 cycle: CHG-20260710T230000-minimap-reuse(코드) / 배포 508fae50.
## CHG-20260710T230000-ai-claude-corp-feature-0016-graph-detail-colsel — §75 상세 패널에서도 테이블 노드 내 컬럼 선택 (2026-07-10) [머지 재번호 §71→§74→§75]
- 대상: `unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css,admin.html}` + `tests/headless/test_detail_colsel.js`(신규). frontend-only, 마이그레이션 0. main rebase(§71/§72/§73 병렬 머지 후 admin.js 자동병합·admin.html 버스터 충돌 해소).
- 변경: 그래프 상세 패널(`_metaGraphRenderDetail` 테이블 뷰)의 컬럼 목록 행을 캔버스 컬럼 노드 클릭과 **동일한 선택** 으로 배선. plain 컬럼은 `.amgr-col-select[data-col=colKey]` 버튼으로 래핑, 관계 컬럼은 `.amgr-col-head`(flex) 안에서 캐럿(`.amgr-col-caret[data-coltoggle]`, 인플레이스 아코디언 보존)과 선택 버튼(`.amgr-col-select[data-col]`)을 분리. 바인딩 블록에 `.amgr-col-select[data-col]` → `_metaGraphShowDetail(data-col)`(기존 canvas·`data-rtuse` 와 동일 선택 경로 재사용) 추가, 아코디언 토글 셀렉터를 `.amgr-col-toggle[data-colrel]` → `.amgr-col-caret[data-coltoggle]` 로 이관. CSS `.amgr-col-select`/`.amgr-col-head`/`.amgr-col-caret` 추가(plain=block·관계=flex relcount 우측정렬). 안내 문구 갱신. 캐시버스터 admin.js/styles.css → `20260710-graph-detail-colsel`.
- 근거: 사용자 요청(캔버스에서만 가능하던 컬럼 선택을 상세 패널에서도). §71 rtuse-camera(사용관계 행)·§72 reltrace-colnav(관계행→미렌더 컬럼 카메라)와 별개 — 본 항목은 컬럼 목록 자체의 선택 배선. 선택 상태 `_metaGraph.selected` 는 이미 컬럼을 1급 노드로 취급 → 새 상태변수 0, `_metaGraphShowDetail` 재사용으로 선택 의미론 무상속(history 기록 + 캔버스 강조 재베이크 + 상세 컬럼 뷰 전환). 기존 아코디언 기능 제거 없이 순수 추가. 검증: `node --check` PASS + 격리 렌더 8/8 + g6build headless 6종 무회귀 + 적대 diff 리뷰 [SUBAGENT: PASS](REV-20260710T230000). Minor(§12.3). POST-DEPLOY 실 Windows 육안은 T75.4(배포 후).

## CHG-20260710T2359-ai-claude-feature-0016-cullrefkeep — §76 컬링 참조·상호작용 보존(focusAdj 예외) (2026-07-10)
- 대상: `admin.js`(_faKeep/_clusterHasFocus + nodePosAll/_inView/_edgeExempt pre-pass + 3 컬 지점 _keepFromCull/_clusterKeep 가드 + rAF 실시간 드래그 컬링) + `admin.html` 버스터 + headless `test_g6build_cullrefkeep.js`(신규 15).
- 변경: 뷰포트 컬링(§65/§67)이 화면 밖 노드 미방출로 관계선 드롭 + 상세 네비 skip + 드래그 중 노드 pop 시키던 회귀 수정. (a) focusAdj 예외(선택 노드 관계 상대) + **뷰포트 내 노드 엣지 컬링무효**(in-view 노드에 연결된 REFERENCES/ROUTINE_USES 상대 끝점을 _edgeExempt 로 방출 예외) → renderEndpoint 가 엣지 렌더, _metaRenderedIdFor 가 네비 팬. (b) 팬 재-emit 260ms 디바운스→rAF 스로틀(실시간 드래그 컬링). **무선택·무연결 시 예외 0**(컬링 무손실); in-view 연결 상대는 선택 무관하게 예외(규모 = in-view edge density 비례·유계 — §76 적대리뷰 M1 정정).
- 근거: 사용자 피드백 "draw는 하지 않되 참조·상호작용은 가능하도록"·"뷰포트 내 노드 연결선 컬링무효"·"드래그 중 실시간 컬링"(ADR-037). frontend-only.
- 검증: headless cullrefkeep 15(§76 적대리뷰 M2 dense off-view 컬링유지 5 포함) + 그래프 회귀 = **249 PASS**(11 스위트)·node --check. §18.8 적대 리뷰 [SUBAGENT: PASS-WITH-FIXES](BLOCKING/MAJOR 0, MINOR 3+NIT 1 — M1/M2 반영, M3/N1 수용). POST-DEPLOY win-browser(TEST §76). 버스터 `admin.js?v=20260710-cullrefkeep`.

## CHG-20260710T2222-ai-claude-corp-feature-0016-cullrefkeep-review — §76 적대리뷰 반영(M1 문서정정 + M2 dense-edge 테스트) (2026-07-10, cross-session resume)
- 대상: `test_g6build_cullrefkeep.js`(T4 dense off-view 케이스 +5 check) + `DECISIONS.md`(ADR-037 트레이드오프 정정)·`MODIFY.md`(상단 CHG-2359 정확성 갱신)·`REPORT.md`·`TASK.md`(T76.2 count·T76.6 추가). 코드(admin.js) 변경 0 — 테스트·문서만.
- 변경: 원본 세션(ff7fb347, 세션 한도 중단)의 §76 in_progress 적대 리뷰를 이어받아 완수 → REVIEW.md `REV-20260710T222000` [SUBAGENT: PASS-WITH-FIXES]. (M1) "무선택 시 예외 0" 주장이 T76.4 in-view 확장 이후 거짓 → "무선택·무연결 시에만 예외 0" 로 3 문서 정정. (M2) 엣지 1개 seed 로 자명 통과였던 "컬링 유효" 갭에 dense off-view B-B 엣지(35개) 케이스 추가 — 예외 팽창이 컬링 무력화 안 함 실증(cullrefkeep 10→15).
- 근거: §18.8 적대 패널 BLOCKING/MAJOR 0. M3(nodePosAll 상시 pre-pass, §77 소비 예정)·N1(rAF 페어링 실무무해)·M2 잔여 커버리지는 REVIEW.md 수용 기록.
- 검증: cullrefkeep 15/15 + 그래프 회귀 11 스위트 249 PASS·node --check. 버스터 불변(admin.js 무변경).

## CHG-20260711T120531-docs-archive (MODIFY/REVIEW §5.5 아카이빙)
- Date: 2026-07-11. MODIFY 117건(102 이관)·REVIEW 117건(102 이관) — verbatim·무손실 md5·가역. 선례 동일 스크립트.

## CHG-20260710T170000-ai-claude-feature-0016-nodeanalysis-postdeploy — §69 T69.5 POST-DEPLOY 완수 기록 (docs-only, 코드 0)
- 대상: `unit/feature-0016-metadata-graph/docs/{TASK.md(T69.5 [ ]→[x]),REPORT.md(POST-DEPLOY 절),REVIEW.md([SKIPPED] entry)}`. **코드/자산 변경 0**.
- 변경: §69(ADR-034, PR #664 a24415a5) 배포 + cc_data_main 재생성(run 7c75ddcb, only_missing=false) 완수 결과를 정본에 기록 — planned 555·capped=false(P3 실증), 715 잡 전량 done·0 failed, caveats 빈값 400/715·자기-불평 사실상 0.
- 근거: 원 cycle 이 T69.5 를 POST-DEPLOY 항목으로 남긴 것을 배포·재생성 실측으로 마감. 코드 diff 부재 → §18.8 패널 SKIPPED(REVIEW 동일 기록).
## CHG-20260713T105932-ai-claude-feature-0016-content-cluster — 카테고리 밴드 '컨텐츠 단위' 그룹핑 실동작화 (2026-07-13)
- 대상: `unit/feature-0002-agent-core/src/modules/{semantic_cluster.py(재작업),metadata_graph.py,llm.py}` + `shared/config.py` + `src/requirements.txt`(numpy) + alembic `0040_routine_objects_semantic_cluster`(additive) + 신규 테스트 `tests/test_semantic_cluster_content.py`. **프론트 변경 0**(ingest·_metaSimGroups 가 generic — 백엔드 신호만으로 루틴 be: 그룹 성립).
- 변경(RC1~RC5, TASK 20260713T1059 진단): ① requirements 에 numpy 추가 + `_cluster_edges` 부재 시 1회 WARNING(종전 silent [] 가 "cadence 는 돌지만 전 시스템 클러스터 0건" 을 은폐) ② `run_semantic_cluster_pass` 를 datasource 전역 → **effective schema(DB) 단위 분할**(N 가드 국소화 — 7,055 테이블 ds 도 DB별 실동작, cluster id 는 pass-전역 순번·스키마 natural-sort·min-key 결정 배정) ③ **루틴 합동 편입** — routine_objects 시그니처(이름+type+params+returns+touches+분석문) 백필 + 테이블과 단일 id 공간 클러스터 + `sync_routine` cluster 투영(_UNSET 보존·None clear) + `_step_routines` 확장 SELECT(0040 미적용 폴백) + `schema_tables` Routine RETURN 8컬럼 ④ **분석문 시그니처 주입** — node_analysis 최신 done summary+usage 를 시그니처에 포함(비어있지 않을 때만 append — 미분석 해시 byte-불변·재임베딩 blast-radius 한정) ⑤ **LLM 컨텐츠 라벨** — `llm_cluster_label`(llm_product_classify 동형)+`_llm_content_labels`(kv 멤버셋-해시 캐시·배치 40·fail-soft affix 폴백·`AGENT_METADATA_CLUSTER_LABEL_LLM` 게이트).
- 근거: 사용자 리포트 "`mssql-qa-idc.cc_data_main` AI 능동 분석 후에도 카테고리 밴드 대부분(특히 함수·프로시저)이 단순 명칭 구분" — 라이브 실측: 전 시스템 semantic_cluster 0건(numpy 부재)·해당 ds N=7,055 전역 skip·루틴 300>테이블 255 인데 클러스터 대상 밖·분석문(Table 466/Routine 477 done) 미연결·라벨 affix. 상세 진단·AC 는 TASK 20260713T1059.
- 검증: 신규 테스트 16(시그니처 결정론/멱등·DB분할·N가드 국소화·합동 id·LLM 캐시/fail-soft·sync 투영) + 전체 스위트 컨테이너 pytest EXIT=0(전건 PASS). py_compile PASS. §18.8 적대 패널 → REVIEW.md. POST-DEPLOY: 마이그 0040 + worker/web 재빌드 + cc_data_main 표적 백필·클러스터 실증 + PB-0008 육안.

## CHG-20260713T113500-ai-claude-feature-0016-content-cluster-chaining — 클러스터 chaining 방어 + SAVEPOINT 격리 + lint 오탐 수정 (2026-07-13, 같은 cycle 후속)
- 대상: `semantic_cluster.py`(mutual-kNN `_cluster_edges`·`_adaptive_components` 신설·SAVEPOINT 격리 2곳) + `shared/config.py`(`AGENT_METADATA_CLUSTER_MAX_SIZE`=40) + `bin/migrate-lint.sh`(diff 모드 `.py` 필터) + 테스트 +3.
- 변경: **라이브 프로브(트랜잭션 롤백·무변경)가 적발한 결함 2건 수정** — ① non-autocommit conn 주입 시 0040-미적용 routine fetch 실패가 tx 를 aborted 로 남겨 pass 전체 InFailedSqlTransaction 연쇄(→ SAVEPOINT 격리, 백필 동형) ② base τ(0.82) 단일연결 union-find 가 같은 DB 테이블(시그니처 boilerplate 공유로 baseline 유사도 높음)을 **단일 254-멤버 blob** 으로 병합해 밴드로 무용(→ mutual-kNN 엣지 + cap 초과 컴포넌트 τ-상승(step 0.02, ceiling 0.98) divisive 재분할). ③ migrate-lint diff 모드가 MAX_MIGRATION.txt(비-py)를 AST 파싱해 오탐 FAIL 하던 lint 버그(.py 필터 — 마이그와 MAX_MIGRATION 동시 변경 cycle 의 첫 발현).
- 근거·실증: 수정 후 재프로브(롤백) — cc_data_main **37 클러스터**(sizes 39·24·13·11… 총 199/255, 'buff'·'monsterclass'·'monsterspawnpoint'·'achieve' 등 컨텐츠 응집), ds 전체 1,016 클러스터/74 스키마/skip 0. 수정 전엔 74 스키마가 각각 거대 blob(총 75 클러스터).
- 검증: test_semantic_cluster_content.py 16→**19**(adaptive split·mutual-kNN 허브차단·기존 유지) + migrate-lint 전체 PASS(+self-test PASS).

## CHG-20260713T121500-ai-claude-feature-0016-content-cluster-panel — §18.8 패널(PASS-WITH-FIXES) 반영 (2026-07-13, 같은 cycle 3차)
- 대상: `semantic_cluster.py`(M1 분석-신선 표적 백필+touch·n4 scope ANY·m2 lazy summaries·m3 kv key 고정폭·m4 float32 ndarray·m5 스키마-로컬 id·n1/n2/n3) + `metadata_graph.py`(m1 `_step_routines` 폴백 `if owned:` 가드+_pending 리셋) + 테스트 계약 갱신(+M1·scope-ANY 회귀 잠금, 파일 24 tests).
- 핵심: **n4 는 라이브 확증 결과 실결함** — node_analysis_jobs.scope_key 가 datasource_key 라 'common' 필터는 매칭 0(분석문 주입 전면 무효였음) → ANY(rag-scope, ds) 로 수정. **M1** — 분석 완료가 행 updated_at 을 안 올려 top-N 창 밖 분석-보유 행이 영구 미갱신 → EXISTS 표적 선별+명시 touch(멱등). 상세 원장: REVIEW.md REV-20260713T120500.
- 검증: 신규 파일 24 + 연관 스위트 PASS, 전체 스위트 컨테이너 pytest EXIT=0, 라이브 재프로브(롤백) cc_data_main 37 클러스터 유지·error 0.
## CHG-20260713T105224-ai-root-feature-0016-minimap-fullview — §77 미니맵 전역 개요 유지(컬링 부분방출 재복제·카메라 재적합 금지 + 시딩) (2026-07-13)
- 대상: `unit/feature-0003-agent-web-ui/src/static/graph/graph-core.js` + `tests/headless/test_g6build_minimap_reuse.js`(Section E/F 30 신규). frontend-only·마이그 0. 캐시버스터는 `?v=dev` placeholder + 빌드 주입(ITEM-09 what#3)이라 수기 bump 불요.
- 변경: 줌 인 뷰포트 컬링(§65/§67)이 미니맵(전역 개요)까지 컬링된 구성으로 바꾸던 결함 수정. ① `_metaGraph._cullPartial`(build 가 뷰포트 사유로 방출을 실제 누락했는지) 신설 — build 서두 초기화 + 4 컬 지점(클러스터·루틴·루틴 파라미터 `_rtOff`·테이블) 마킹 + products/스코프 전환 stale 소거 2곳. ② **전체-기하 서명** `_miniFullSig`(§76 nodePosAll — 컬링 무관 전 노드 — + edges.size FNV, build 마다 산정) 신설 — 미니맵 보유 이미지(`mm.__fullImageSig`)의 '현재성' 판정 기준. ③ `_metaPatchMinimapReuse` 확장: 부분방출 + 전체 이미지 보유 시 `renderMinimap` 재복제 skip(stale 여도 부분 재복제 금지 — 컬링 구성 노출 차단, `__lastGeomSig` 는 전체-build 서명 보존으로 줌아웃 복귀 시 재사용). 무컬링 렌더에서만 서명 마킹, 미보유 시 원본 폴백(빈 미니맵·동결 방지). ④ 같은 게이트로 plugin `setCamera` 래핑 — AFTER_TRANSFORM 재적합이 컬링 중 부분 bounds 로 미니맵 카메라를 줌인시키는 두 번째 기전 차단(`updateMask` 는 요소 bounds 비의존이라 마스크 정위치 유지). ⑤ **컬링-유예 시딩 build**(`_metaMinimapSeedKick` 350ms 지연·`_cullSuspendOnce` 1회 소비·`_miniSeedTimer` 중복 방지): fit 이 판독 하한으로 클램프되는 대형 모델은 무컬링 build 가 자연 미발생(라이브 실측 1,249 노드 fit 방출 153) → 전체 이미지를 1회 전량-방출 build 로 시딩, stale(줌인 중 펼침/필터) 시 재시딩. 시딩-마킹 debounce(128ms) 경합으로 마킹 무산 시 래퍼 stale-skip 분기가 force 재-kick(latch 관통) — 상호작용 소강 시점 수렴 보장.
- 근거: 사용자 리포트("전역적으로 보여야 할 미니맵 내 노드들의 출력 구성이 변경… 컬링된 그래프 뷰 이미지가 사용") — §74(전체-이미지 재사용, ADR-036)의 의미론을 컬링(§65/§67/§76) 이후에도 보존. §74 상태-only skip 무회귀(방출 서명 게이트 유지 + 컬링 차원 직교 게이트). 설계 3요소(②⑤ + force 재-kick)는 PRE-LANDING 라이브 검증이 적발한 결함 3건(fit-클램프 무컬링 미발생·카드 시점 이미지 오인·경합 latch 고착)의 대응.
- 검증: minimap_reuse **65 PASS**(Section E 서명 의미론 + F1~F9 시딩/stale 재시딩/경합 수렴 — 라이브 적발 3건 전부 headless 재현·잠금) + 그래프 headless 11 스위트 **279 PASS / 0 FAIL** + `node --check --input-type=module` PASS. graph-split 후 headless 번들 레시피 확립(7 모듈 sed 연결 + admin.js 심볼 stub). **PRE-LANDING PB-0008 win-browser 라이브 PASS**(qa-idc 1,249 노드: 시딩 수렴 → 줌 2.0 컬링 rebuild 방출 1,573→153 에 미니맵 toDataURL 해시 완전 불변 → 팬 불변 → 스코프 전환 재렌더 → pageerror 0, test-runs.d/20260713T105224). 적대 리뷰 2 라운드 → REVIEW.md(REV-20260713). POST-DEPLOY 재확인은 T77.5.
## CHG-20260713T143000-ai-claude-feature-0016-content-cluster-h1 — 클러스터 pass 루틴 fetch scope 비대칭 hotfix (2026-07-13)
- 대상: `semantic_cluster.py` 루틴 fetch WHERE 1건 + 회귀 테스트 잠금. POST-DEPLOY 라이브 실증에서 적발 — pass 리포트 objects=7055(테이블만)로 루틴 전량 미합류.
- 원인: `routine_objects.scope_key` 는 **datasource_key**(라이브 실측 — node_analysis_jobs 와 동일 비대칭 클래스, 패널 n4 계보). 'common' 스코프 필터가 0-match. datasource_key 등가가 실질 파티션이므로 scope 필터 제거(백필 쿼리와 동형 — 백필은 원래 무필터라 정상 동작했음).
- 검증: test_semantic_cluster_content.py 회귀 잠금(+scope 필터 부재 assert) 포함 전 파일 PASS. POST-DEPLOY 재가동으로 루틴 합류 실증(REPORT).
## CHG-20260713T-ai-root-feature-0016-graph-pixi-plan — §78 PixiJS v8 렌더러 교체 계획 수립 (docs-only, 코드 0)
- 대상: `unit/feature-0016-metadata-graph/pixi-migration/BLUEPRINT.md`(신설), `docs/{TASK.md(§78 신설),REPORT.md(2026-07-13 절),REVIEW.md([SKIPPED] entry)}`. **코드/자산 변경 0**.
- 변경: 팬 성능 잔존 병목(Canvas per-frame CPU 재래스터) 타당성 검토 결론 + PixiJS v8 이관 계획(디자인 보존 계약 D1~D6·Phase A/B/C·AC·리스크 R1~R7)을 plan-review 상태로 정착. 실행은 PLAN-APPROVED 후(§7.1 Major).
- 근거: 사용자 지시(2026-07-13) — 게임엔진 기각 검토 수용, G6 유지 경로 기각(과거 디자인 실패 이력), PixiJS v8 로 디자인 무붕괴+성능 확보 계획 요청. 코드 diff 부재 → §18.8 패널 SKIPPED(REVIEW 동일 기록).

## CHG-20260713T-ai-root-feature-0016-graph-pixi-poc — §78 Phase A POC (poc-only, 제품 코드 0)
- 대상: `unit/feature-0016-metadata-graph/pixi-migration/poc/{pixi-poc.html,shoot_pixi.py,pixi.min.js}`(신설), `docs/{TASK.md(T78.2),REPORT.md,MODIFY.md}`. **제품 코드/자산 변경 0** (poc 격리 폴더).
- 변경: PixiJS 8.19.0 POC — 디자인 보존 계약 D1~D5 검증 씬 + 성능 하네스. 실 Windows Chrome 실측 exit gate PASS(882 등가 vsync-perfect).
- 근거: TASK §78 T78.2 / BLUEPRINT §4 Phase A. 제품 diff 부재 — §18.8 패널은 Phase B 코드 통합 시 적용.

## CHG-20260713T-ai-root-feature-0016-graph-pixi-adapter — §78 Phase B-early SceneAdapter 신설 (신규 파일, graph-core 무변경)
- 대상: `unit/feature-0003-agent-web-ui/src/static/graph/{graph-renderer-pixi.js,SCENE_SPEC.md}`(신설) · `tests/headless/test_pixi_adapter.js`(신설) · `pixi-migration/poc/adapter-poc.html`(신설) · docs(TASK T78.3·REPORT·test-runs.d). **기존 graph/ 7모듈·admin.js·admin.html 무변경**(배선은 B-late).
- 변경: PixiJS v8 SceneAdapter(G6.Graph 호환 + 순수로직 분리) — scene-spec(=_metaG6Build 출력형태) setScene 렌더. 순수 28 PASS·그래프 회귀 279 무회귀·실 Chrome 60fps vsync + 디자인 D1~D5 보존.
- 근거: TASK §78 T78.3a / BLUEPRINT §4 Phase B. 신규 파일이라 §18.8 적대 패널은 B-late(graph-core 배선=실 제품 표면 변경) 시 정규 적용 — 본 커밋은 미배선 어댑터라 SKIPPED.

## CHG-20260713T-ai-root-feature-0016-graph-pixi-wire — §78 B-late seam 배선 + 적대리뷰 수정 (제품 코드 변경)
- 대상: `graph/graph-renderer-pixi.js`(gap 배선 + 적대리뷰 B1/M1/M2/m1/m2/m4)·`graph/graph-core.js`(seam _metaRendererKind·_metaInitGraph 분기 + pixi 컬링 비활성 M3/M4 + drag-enable predicate 주입)·`graph/SCENE_SPEC.md`(신규)·`admin.html`(pixi.min.js vendor)·`vendor/pixi.min.js`(신규)·`tests/headless/test_pixi_adapter.js`.
- 변경: 그래프 렌더러 G6→PixiJS 전환 배선. 어댑터가 G6.Graph 인터페이스 미러(모든 UI 버튼·상호작용 무변경 동작). render-on-demand. 적대 §18.8 BLOCKING1+MAJOR4+MINOR3 수정. 회귀 0(순수 33 + 그래프 279).
- 근거: 사용자 지시(실 배선 + 모든 UI 버튼 정합). REV-…-graph-pixi-wire [SUBAGENT:PASS-WITH-FIXES].

## CHG-20260713T-ai-root-feature-0016-graph-pixi-postdeploy — §78 Phase C POST-DEPLOY 라이브 검증 기록 (docs-only, 코드 0)
- 대상: `docs/{TASK.md(T78.3c/T78.4 완료),REPORT.md(Phase C 완결)}` + `unit/feature-0003-agent-web-ui/docs/test-runs.d/*-pixi-live-postdeploy.md`. **코드/자산 변경 0**.
- 변경: PR #752 배포(main d776f57b) + 라이브 admin 그래프 뷰 PixiJS 실데이터 PB-0008 결과 기록 — 409 객체 렌더·전 UI 버튼·팬 60fps vsync-perfect·pageerror 0. feature-0016 §78 완결.
- 근거: 배포·라이브 검증 완수. 코드 diff 부재 → §18.8 SKIPPED.

## CHG-20260713T-ai-root-feature-0016-graph-pixi-polish — §79 후속 이슈 3건 + 오브젝트 풀 + 적대리뷰 수정
- 대상: `graph/graph-renderer-pixi.js`(analyzed 테두리 복원·미니맵 클램프/드래그·오브젝트 풀·B1/M1/M2/m1/m4/NIT 수정)·`tests/headless/test_pixi_adapter.js`(T14~19).
- 변경: PixiJS 렌더러 후속 — analyzed/running 상태 dot→테두리(concentric halo, selected 미가림), running fill desaturate, 미니맵 뷰포트 클램프·드래그 상호작용, scene diff 오브젝트 풀(선택 리빌드 6배). §18.8 BLOCKING1+MAJOR2+MINOR 수정. 회귀 0(순수 49+그래프 279).
- 근거: 사용자 리포트 3건 + 후속 최적화. REV-…-graph-pixi-polish [SUBAGENT:PASS-WITH-FIXES]. BitmapText DEFER(측정 근거).

## CHG-20260713T070819-postdeploy — §79 POST-DEPLOY 라이브 검증 기록 (docs-only)
- 대상: docs(TASK T79.6·REPORT)+test-runs.d. 코드 0. PR #755 배포(8edfa3a8) + 라이브 미니맵 클램프/드래그·409 렌더·pageerror 0. §18.8 SKIPPED.

## CHG-20260713T-ai-root-feature-0016-graph-pixi-bitmaptext — §80 라벨 Text→BitmapText 렌더 최적화 + 적대리뷰 수정
- 대상: `graph/graph-renderer-pixi.js`(_makeText 라벨 팩토리·hexToTint·M2 폴백·노드/combo/edge 라벨 통일)·`tests/headless/test_pixi_adapter.js`(T20 hexToTint).
- 변경: 라벨 BitmapText(dynamic font white-base+tint) 기본/Text 폴백. 실 그래프 씬 렌더 Text 157ms→BitmapText 0.03ms(draw call 공유 atlas). §18.8 MAJOR2(폴백 무력·CJK atlas)+MINOR3 수정. 회귀 0(순수 56+그래프 279).
- 근거: 사용자 요청(§79 DEFER 항목 진행). POC 측정 후 채택. REV-…-bitmaptext [SUBAGENT:PASS-WITH-FIXES]. M1 atlas 는 bounded 트레이드오프(실데이터 영문 위주)+labelEngine seam.

## CHG-20260713T081919-postdeploy — §80 POST-DEPLOY 기록 (docs-only)
- docs(TASK T80.3·REPORT)+test-runs.d. 코드 0. PR #759 배포(b69e4111)+라이브 BitmapText 렌더·팬 60fps·pageerror 0. §18.8 SKIPPED.
## CHG-20260713T181300-detail-hover-fx — §81 상세 패널 hover 시각 효과
- 대상(cross-cut feature-0003 static/graph): `graph-renderer-pixi.js`(world-space `_hoverLayer`+`setHoverHighlight`/`clearHoverHighlight`, draw() stale clear)·`graph-core.js`(`_metaGraphHoverPan`/`HoverPanCancel`/`SetHoverHighlight`/`ClearHoverHighlight` 래퍼+export)·`graph-ctxmenu.js`(hover 바인더 `_metaBindHoverPan`/`_metaBindHoverHighlight`/`_metaGraphBindDetailHover`+5뷰 배선+`data-edge-self`)·`graph.css`(`[data-cid]` 커서/hover).
- 변경: 상세 패널 하위 항목 hover 시 비커밋 피드백 — 카테고리/클러스터 행=부드러운 카메라 팬(intent 200ms), 컬럼=노드 강조 링, 참조·ROUTINE_USES·관계 행=연결선(엣지)+양끝 노드 강조. 커밋 선택/rebuild 미접촉. 렌더러 무관(G6 폴백=하이라이트 no-op·카메라 동작).
- 근거: 사용자 요청(entry persona dispatch). 등급 Minor(additive UI). 정적 검증 PASS(node --check 3모듈·심볼 정합). PB-0008 라이브 검증(visual=always)은 배포 후 T81.6.
## CHG-20260713T163000-ai-claude-feature-0016-content-cluster-p2 — 잔여 affix 가짜 밴드 해소 + 연관 밴드 인접 배치 (2026-07-13)
- 대상: `semantic_cluster.py`(`_cluster_centroids`·`_seriate_by_centroid`·`_nearest_centroid` + pass 에 soft-attach·id seriation) + `shared/config.py`(`AGENT_METADATA_CLUSTER_ATTACH_SIM`=0.78) + `graph-simgroups.js`(`_metaGenericPrefixes`·`_metaStripGeneric` affix 정규화 + be: 밴드 id 순 선두 배치) + 신규 테스트(BE 2·FE 헤드리스 13).
- 변경(사용자 후속 리포트 — TASK 20260713T1620): **RC-A** 미클러스터 잔여가 "dt_c" 가짜 affix 가족(무관 테이블 동거: DT_CashPoint·DT_Castle·dt_CombineMaterial)으로 흐르던 것을 ①BE soft-attach(centroid 코사인 ≥0.78 최근접 편입·라벨 상속·코어 라벨/캐시 비오염) ②FE 스키마-공통 일반 접두(dt_/ct_ 류, max(4,15%) 임계) strip 으로 이중 해소. **RC-B** 밴드 순서가 FK seriation 뿐이던 것을 BE 가 cluster id 를 centroid 최근접-이웃 체인 순서로 배정 + FE 가 be: 밴드를 id 오름차순 선두 배치 — 의미 연관 밴드 인접.
- 근거·실증(라이브 프로브·롤백): attached **5,249**, cc_data_main 미클러스터 테이블 **114→26**, 리포트 3종이 각기 다른 컨텐츠 클러스터로 분리(cid 20/13/0 — 동거 해소). updated 23,324 는 id 재-seriation 1회성 churn(멱등 — 재실행 시 0).
- 검증: BE test_semantic_cluster_content.py 24(seriation 체인·attach 편입/미달 NULL) + FE test_g6build_simgroups_p2.js 13(접두 검출/strip/과절단 방지·dt_c 가족 소멸·실스템 보존·be: id 순 선두·결정론) + 그래프 헤드리스 전 스위트 무회귀(category 26·vpack 19 외) + 전체 pytest EXIT=0. §18.8 패널 → REVIEW.md.

## CHG-20260713T175800-ai-claude-feature-0016-content-cluster-p2-postdeploy — p2 TP.4 POST-DEPLOY 완수 기록 (2026-07-13, doc-only)
- 대상: TASK.md(TP.4 [x])·REVIEW.md([SKIPPED] entry)·test-runs.d fragment. **코드/자산 변경 0**.
- 변경: PR #763 배포(469fa20d) 후 실측 기록 — 클러스터 재가동(attached 4,843·cap 가드 실동작)·AGE 수렴(cc_data_main T225/R298)·PB-0008 PASS(nm:dt_* 가짜 가족 0·be: 95 id순 선두·길드4/퀘스트3/몬스터6+ 연속 인접·리포트 3종 각기 다른 컨텐츠 클러스터 분리·기능 오류 0).
- 근거: TP.4 완수 게이트(visual_verification_scope: always) 마감. 코드 diff 부재 → §18.8 패널 SKIPPED(REVIEW 동일 기록).
## CHG-20260714T090500-ai-claude-feature-0016-cluster-label-target — cluster_label 활동 target 사용자 식별자화 (2026-07-14)
- 대상: `semantic_cluster.py`(`_ds_display_label` 신설 + `_llm_content_labels` payload.datasource=사용자 식별자) + 테스트 2. 마이그 0·Minor(§12.3 — 단일 파일·표시 정확성).
- 변경: 'AI 운영 현황' cluster_label 활동의 target 이 scope_key 해시로 노출되던 것을 `agent_runtime.datasource_health` 스냅샷(scope_key→datasource_label)으로 해석해 기록. 미스 존재 시에만 1회 조회(전량 캐시 적중 시 추가 쿼리 0). kv 라벨 캐시 ns 는 해시 유지 — 캐시 무효화·재호출 없음. 랜딩 후 기존 546건 UPDATE 데이터 정정(멱등) 동반.
## CHG-20260714T-graphsync-flock-guard — §82 metadata-graph-sync cron 겹침 실행 flock 가드 (서비스 전역 장애 긴급 대응, 2026-07-14)
- 대상: `bin/metadata-graph-sync.sh`(flock -n 가드 + symlink 검사 신설)·`bin/routine-backfill.sh`(동일 lock 파일 공유 가드 + symlink 검사 신설, §18.8 리뷰 지적 반영).
- 변경(사용자 장애 리포트 — "로그인 후 빈 화면, 작업 콘솔 미작동"): root crontab(30분 주기) 로 호출되는 `metadata-graph-sync.sh` 에 동시성 가드가 없어, 이전 실행이 AGE 그래프(`metadata_kb`) lock 경합으로 멈추면 새 cron 이 계속 겹쳐 쌓이던 것을 `flock -n`(non-blocking) 으로 원천 차단. `sync_graph()` 의 또 다른 호출자 `routine-backfill.sh` 도 동일 lock 을 공유하도록 확장(리뷰 MAJOR-1). lock 파일을 world-writable `/tmp` 대신 root 전용 `/root/.locks/mysql-ai-delegated-dev/`(0700, 자기-provision)로 이동 + 심볼릭 링크 대상이면 fail-loud 거부(리뷰 MAJOR-2, TOCTOU 방지).
- 근거·실증: 라이브 인시던트(stray 프로세스 20개, 1h19m lock-wait 체인, pgbouncer 풀 30→14 커넥션 회복) → 즉시 복구(코드 변경 전 운영 조치) → 재발 방지 코드 수정 → §18.8 general-purpose 적대 리뷰 PASS-WITH-FIXES(MAJOR 2건 수정) → cross-script 상호배제 + symlink 가드 라이브 재현 검증. 상세는 TASK.md §82, REVIEW.md REV-20260714T120000-graphsync-flock-guard.
