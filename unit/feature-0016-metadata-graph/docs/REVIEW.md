---
doc_type: REVIEW
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

> 이전 기록(102건): [REVIEW-archive-20260711T120531.md](./_archive/REVIEW-archive-20260711T120531.md)

## REV-20260710T160000-ai-claude-feature-0016-graph-perf2 [SUBAGENT: PASS-WITH-FIXES] — §65 뷰포트 컬링 + 집계 supernode + 마커 제거 diff 적대 리뷰
- 2렌즈 적대 패널(컬링 정확성/엣지·팬 · combo/시각/스케일), G6 번들 역공학 + 코드 실측으로 반증 시도.
- **BLOCKING/MAJOR 0** — 핵심 주장 검증: (1) **combo-safe**: 테이블/루틴 칩은 화면 안팎 무관 항상 방출(realH 예약·band-invariant), 컬럼/파라미터만 게이트 → combo extent 는 col-LOD 와 동일 거동. renderEndpoint 가 미방출 컬럼 끝점을 항상-방출 테이블로 승격 → **dangling 0**. (2) 좌표계 정합(getCanvasByViewport=screen→world, style.x/y=world). (3) tableDeps 매 build 리셋 → stale 드래그 없음. (4) 팬 재-emit 무한루프 불가(fit=false→self-transform 없음, 260ms 디바운스, rebuild 가 _cullVp 재중심). (5) 집계 supernode 스케일은 L.w*0.94×L.h*0.7 클램프+슬롯 중앙 → 인접 카드 겹침·슬롯 넘침·폰트 넘침 없음(확장 슬롯 ≥256 > CARDW 210). (6) null/API 부재·products·resetModel 리셋 커버.
- CONFIRMED(MINOR 1, **수정**): cull-pan 분기의 early `return` 이 §57 col/edge 마커 갱신 + `_lodBand` 기준선 세팅을 건너뜀 → 줌+팬 복합 제스처가 밴드 교차 시 억제는 되나 마커 침묵·밴드 stale(다음 same-band aftertransform false-=== skip) 가능. **수정**: return 제거하고 밴드 로직으로 fall-through(순수 팬=밴드 로직 즉시 return·cull 타이머 유지, 줌+팬=밴드 로직이 타이머 대체+마커/밴드 세팅). self-healing 이었으나 근본 수정.
- CONFIRMED(NIT 1, **수정**): 집계 카드 폰트 클램프(3.2/2.6)가 깊은 줌서 화면 폰트 과소(카드는 커도 글자 작음) → **수정**: _sc 상한 6→8(카드 확장) + 폰트 클램프 4.5/3.5 + 카드 높이 안 클램프. 최종 가독은 win-browser 육안 확인.
- 검증: 수정 후 headless viewport-cull 6 + 회귀 134 = **140 PASS** · `node --check` PASS. win-browser 시각검증 TEST §65.


## REV-20260710T200000-ai-claude-feature-0016-catband-cull [SUBAGENT: PASS-WITH-FIXES] — §67 집계폐기+카테고리밴드규모+테이블/클러스터 뷰포트컬링 diff 적대 리뷰
- 2렌즈 적대 패널(컬링 정확성/combo/엣지 · 집계off/밴드/시각), G6 번들+코드 실측(1렌즈 StructuredOutput 에러, 남은 렌즈가 양축 커버).
- **BLOCKING/MAJOR 0** — 핵심 3축 검증: (A1) aggActive=false 상시화 잔여참조 무해(agg 밴드는 rebuild 구동하나 aggCut=false 로 마커 억제, _aggCard=false 로 supernode 완전 죽은코드) (A2) 카테고리 밴드 카운트 정합(cat.members=comboId=Schema key=schemaTotals key, 카드 badge 동일소스, 누락 ||0+>0 graceful) (B) 컬링 좌표 정확(clusterOffset 은 L.x0/y0 folded, per-table/routine 은 nodePos 반영 좌표). 줌아웃 col-LOD/edge-LOD 는 aggActive 독립(원시 줌 임계)이라 클러스터 펼침 유지에도 관계선 축약 정상.
- CONFIRMED(MINOR 1, **수정**): 전체-클러스터 컬링이 L.w/L.h(pre-offset masonry)로 판정해, free-place 드래그(nodePos/groupOffset)로 클러스터 bbox 밖 나간 가시 멤버를 오컬링 가능(per-table 경로는 정확). **수정**: free-place 존재 시 전체-클러스터 컬링 skip → per-table 컬링(정확)에만 위임.
- CONFIRMED(NIT 1, **수정**): CATH 헤더에 labelMaxWidth 부재 → '· M 테이블' 추가로 좁은 단일-DB 밴드에서 라벨 넘침 가능(한글 실폭>추정). **수정**: labelMaxWidth=hdW-8 로 ellipsis 흡수.
- 검증: 수정 후 headless viewport-cull 6 + agglod 8 + 회귀 = **150 PASS** · node --check. win-browser 육안 TEST §67.

## REV-20260710T210000-ai-claude-corp-feature-0016-reldedup [SUBAGENT: PASS] — §69 상세 패널 관계 중복 병합(AI 박스 '연결 관계 추적' 제거) diff 적대 리뷰
- 대상: CHG-20260710T210000-reldedup (admin.js `_metaGraphLoadNodeAnalysis` 의 '연결 관계 추적' flat 블록+no-op `_metaGraphBindTraceRows(box)` 제거·orphan `_metaGraphRelTraceRowsHTML` 삭제·esc 주석 정정 + styles.css dead `.admin-meta-graph-ai-rels` 제거 + admin.html 버스터 js/css).
- 방법: §18.8 적대 리뷰(general-purpose, 결함 적발 목적). 6개 결함 가설(dangling ref·behavior loss·syntax/dead code·CSS 안전·버스터 정합·AI 박스 잔여 렌더)을 코드 실측(file:line)·능동 반증으로 검증.
- 판정: **PASS** — BLOCKING/MAJOR/MINOR 0, 수정 불필요. 핵심: (H1) 제거 후 `_metaGraphRelTraceRowsHTML` 라이브 호출 0(주석/docs 만), `_metaGraphBindTraceRows` 는 컬럼 섹션(admin.js:7965)이 계속 사용 — 오제거 아님. (H2) **behavior loss 없음** — #1(컬럼 섹션)은 #2 의 strict superset. 게이트 `if(columns.length||selfIsColumn)` 가 false 인 경우(Routine·컬럼無 테이블)는 REFERENCES 끝점이 항상 Column 이라 #2 도 원래 count 0 → "#1 미렌더인데 #2 관계 표시" 시나리오 부재. (H3) `node --check` PASS·제거 함수 내부 심볼(`_metaEdgeTrustBadge`·`_metaColParent` 등) 타처 사용 유지. (H4) `.admin-meta-graph-ai-rels` 진짜 dead·형제 클래스(`.amgr-tracehint`·`.amgr-row.amgr-trace`) 컬럼 섹션이 계속 생산·미훼손. (H5) admin.html js+css 버스터 양쪽 bump. (H6) AI 박스 역할 칩+prose+빈-rows 폴백 정상.
- 비차단 관찰 2건(수정 불요·기록): ① index.html 의 독립 `styles.css` 버스터(20260706)는 stale 하나 무해 — 제거된 규칙이 admin-graph 전용이라 task/chat 화면 무영향. ② **기존** #1 의 `columns.slice(0,80)` 아코디언 cap → >80컬럼 분석 테이블의 81번째+ 컬럼 FK 는 #1 인라인 추적행 부재(요약 배지엔 계상). #2 는 무제한이었으나 flat·저정보였고, 해당 관계는 유지된 '🔗 관계 상세' 모달(`_metaGraphShowRelations`)로 도달 가능 → 정보 손실 아님. 본 diff 가 만든 결함 아닌 pre-existing #1 한계(트레이드오프로 수용).
- 검증: headless edge 71·collod 20·agglod 8·category 26·vpack 19·viewport-cull 6 = **150 PASS** 회귀 0 · `node --check` PASS. POST-DEPLOY PB-0008 육안(feature-0003 TEST §69).

## REV-20260710T063659-ai-claude-feature-0016-graph-focus-selected [SUBAGENT: PASS-WITH-FIXES] — 상세 패널 "🎯 이 노드로 이동" 카메라 버튼 diff 적대 리뷰
- 적대 diff 리뷰(레이아웃 파손 최우선 + 핸들러 정확성 + 회귀 + node --check), styles.css/admin.js/admin.html 코드 실측.
- **BLOCKING/MAJOR 0**. 핸들러 PASS: (1) `self.key` 3개 렌더 호출부(showDetail/expand/center) 모두 보장, empty 카드엔 헤더 없음, 핸들러 `!graph||!key` 재방어. (2) `_metaRenderedIdFor` null 가드가 접힌 스키마/미렌더에서 정확 → 안내만 후 return(`_metaGraphPanToRelation` 동일 가드). (3) `seq=_metaGraph._opSeq`(bump 없이 읽기 → 후속 op 가 팬 폐기) 기존 팬 래퍼와 바이트 동일 패턴. (4) id `metaGraphFocusSelBtn` 충돌 0. 회귀 PASS: 기존 `metaGraphRelBtn` 바인딩·동작 불변, `el.innerHTML` 교체가 구 리스너 GC → 리스너 누수 0.
- CONFIRMED(MINOR 1, **수정**): 카드 헤더 `.admin-meta-graph-card-head` 가 `flex-wrap` 미지정(nowrap) + `.amgr-link` 는 `flex:none;white-space:nowrap`. 버튼 2개가 되며 좁은 패널 폭(최소 240px)·유사도 배지 동시 존재 시 헤더가 가로 초과 → 페이지 구조는 detail 패널 overflow-x 로 **격리(세로 폭발·겹침·z-index 파손 없음)**되나, 맨 오른쪽 신규 버튼이 가로 스크롤 없이 안 보일 수 있음(diff 이전 1버튼은 최소폭에 맞았음). **수정**: `.admin-meta-graph-card-head { flex-wrap: wrap; }` 부여(sibling `.cov-db-rule-card-head` 동일 패턴) → 폭 부족 시 버튼이 다음 줄로 래핑, 가림·가로스크롤 해소. styles.css 캐시버스터 동반 bump.
- NIT(정보): `strong`(노드명) min-width:0/ellipsis 미처리는 기존 성질(diff 이전부터) — 이번 수정 범위 밖, flex-wrap 로 실질 완화. 
- 검증: 수정 후 `node --check admin.js` PASS. win-browser 시각검증은 POST-DEPLOY(정적 baked, TEST §3 / TASK T70.4).

## REV-20260710T223000-ai-claude-corp-feature-0016-reldedup-pd [SKIPPED: docs-only POST-DEPLOY 실측 기록 — 코드 변경 0] — §69 완수 기록
- 대상: feature-0003 TEST §69 POST-DEPLOY append + feature-0016 TASK T69.5 완료 + REPORT POST-DEPLOY 절. 코드/자산 변경 0(순수 문서).
- 근거: §69 병합(PR #659, main 5e235953)의 실 Windows Chrome POST-DEPLOY 실측(서빙 자산 curl + 런타임 assertion `typeof _metaGraphRelTraceRowsHTML==="undefined"`·`.admin-meta-graph-ai-rels` DOM 0·pageerror 0) 결과를 정본에 기록. 코드 diff 부재 → §18.8 적대 패널 불요(SKIPPED). 배포는 §69 cycle 에서 이미 완료(무중단 롤링·soak PASS).

## REV-20260710T163512-ai-claude-feature-0016-graph-rtuse-camera [SKIPPED: Minor frontend-only 2줄 핸들러 — shipped _metaGraphPanToRelation(graphux7#2) 재사용·신규 기계장치 0; §18.8 subagent 패널 사용자 중단 → inline 적대 검토 수행] — 상세 패널 사용관계 행 클릭 카메라 이동
- inline 적대 diff 리뷰(순서/race·미렌더 가드·selection·회귀·캐시버스터), admin.js `_metaGraphPanToRelation`(L7249)·`_metaGraphShowDetail`(L7197)·`[data-rtuse]` 핸들러(L7997) 실측.
- **BLOCKING/MAJOR 0**. PASS: (1) 순서 — pan 은 완전 동기(팬+선택+상태), 반환 후 ShowDetail(async)이 첫 await 전 동기로 `_metaGraphStatus("상세 조회 중…")` 세팅 → 캔버스 카메라 애니메이션은 상세 패널 재렌더와 독립, 팬 취소·race 없음. (2) 미렌더 대상 — pan 이 `_metaRenderedIdFor` null 가드로 안내 후 return(무throw), ShowDetail 은 key 로 fetch·전환 정상 → 기존 거동 보존. (3) selection — pan·ShowDetail 양쪽 동일 key `k` 로 `_metaGraphSetSelected` → idempotent, 대상 불일치 없음. (4) 캐시버스터 — admin.js 만 bump, CSS 미변경이라 styles.css 미bump 정확. (5) 회귀 — 상세 전환은 pan 성패 무관 항상 실행(순수 추가).
- NIT(수용): pan 의 transient 상태힌트 "(더블클릭 = 상세 패널 전환)" 가 rtuse 경로선 부정확(단일 클릭이 이미 전환)하나 ShowDetail 의 동기 "상세 조회 중…" 이 즉시 덮어써 **화면 미노출** → user-facing 회귀 0. 2줄 변경에 pan param 추가는 과설계 → 미수정.
- 검증: `node --check admin.js` PASS. win-browser 시각검증 POST-DEPLOY(정적 baked, feature-0003 TEST §71 / TASK T71.3).
## REV-20260710T065500-ai-claude-corp-feature-0016-graph-colnav [SUBAGENT: PASS-WITH-FIXES] — §72 상세 패널 관계행 단일클릭 미렌더 컬럼 카메라 이동 diff 적대 리뷰
- 대상: CHG-20260710T065500-graph-colnav (admin.js `_metaRenderedAncestorFor`·`_metaFocusKeyFor` 신설 + `_metaGraphPanToRelation` 재작성 + `_metaGraphSetSelected`/`_metaG6Build` focusAdj 산출 중앙화 + admin.html 버스터 + test_graph_colnav.js 신설).
- 방법: §18.8 적대 리뷰(general-purpose, 통과 아닌 결함 적발). BLOCKING/MAJOR/MINOR 가설을 코드 실측(파일:라인)·per-frame 재해소·`_opSeq` 레이스·엣지케이스로 반증 시도 + 테스트 타당성 평가.
- 판정: **PASS-WITH-FIXES** — BLOCKING 0. 크래시/dim-lock 없음(모든 selected/nodes 접근 `nodes.has` 가드). CONFIRMED PASS: `animateFocus(SC:…)` 재해소 안전(SC:SC: 이중접두 없음), `_opSeq` 레이스 없음(_metaG6Apply 는 seq 미증가), 기존 경로 보존(직접렌더 컬럼/테이블·접힌 스키마 카드 pan-only·오류 문자열 제거·260ms 단/더블 라우팅), 엣지케이스(no-`:`·2세그·self-FK·displayNode 폴백) 모두 graceful.
- 적발/반영:
  - **MAJOR(stale base) → 수정**: 리뷰 중 §67 catband-scale·§68 graph-rw-group 이 main 병렬 머지되어 base(00871661) 4커밋 stale. `git diff main` 이 §67 revert 로 오독될 위험 + admin.html:1043 버스터 3-way 충돌 확정. **현재 main(c0a3d70f)으로 rebase** 후 전량 재적용·재검증. §67 테이블 뷰포트 컬링과 정합 확인(화면 밖 대상 테이블은 SC:카드/안내로 graceful degrade — `_metaRenderedAncestorFor` 가 renderedIds 기준이라 구조적 정합).
  - **MINOR#3(미렌더 컬럼 선택 시 하이라이트 소실) → 수정**: 미펼침 컬럼은 사실상 항상 모델 밖이라 `_metaGraphSetSelected(column)`+`_metaG6Build` 재산출이 focusAdj=null → 전역 dim 해제·직전 하이라이트 소실·선택 링 없음. **사용자 결정(AskUserQuestion): 선택=컬럼·하이라이트=상위 종속 객체**. `_metaFocusKeyFor` 로 focusAdj 를 소속 테이블(모델의 Table 노드일 때만)로 폴백 — 두 경로(즉시/빌드) 중앙화로 일치. §57.5 F2(prune 선택=null) 는 부모-Table 가드로 보존.
  - **테스트 갭 → 보강**: 리뷰가 "선택 게이트(renderedSelf||!direct)·폴딩이 순수 해소 테스트에서 미검증" 지적 → stub 기반 선택게이트(G1~G4)·실호출 하이라이트폴딩(F1) 단언 추가(22 PASS).
- 검증: 최종 headless test_graph_colnav 22 + 회귀(edge_visibility 71·agglod 8·category 26·collod 20·vpack 19·viewportcull 6) = **172 PASS** · `node --check` OK.
- 미결(정상): 실 G6 카메라 팬·canvas 하이라이트 육안은 그래프뷰 인증/라우팅 무인 도달 차단 → POST-DEPLOY 사용자 육안 게이트(TEST §72 T72.5, 배포 후 자산 curl+육안).

## REV-20260710T165030-ai-claude-feature-0016-nodeanalysis-caveats [SUBAGENT: PASS-WITH-FIXES] — §69/ADR-034 AI 능동 분석 "주의" 계약 재설계 + 루틴 payload + 시드 커버리지 diff 적대 리뷰
- 대상: CHG-20260710T155200 (P1 `llm.py` NODE_ANALYSIS_PROMPT caveats 계약·analyze-from-visible·Input JSON returns/touches · P2 `node_analysis.py` _fetch_context routine_touches + 신규 `_fetch_routine_returns` + _build_payload touches/returns 투영 · P3 `shared/config.py` SCHEMA_CAP 200→1000·MAX 500→2000·RUN_BUDGET_MAX 2500→4000·BATCH 4→10).
- 방법: §18.8 적대 리뷰(general-purpose 단일 통합 렌즈, 통과 아닌 결함 적발). 6개 결함 가설(access 오라벨·_fetch_routine_returns SQL/키·config cap 하류·untrusted-data gap·caveats 빈값 하류·계약/과억제)을 코드 실측(file:line)으로 능동 반증 + sync/렌더 경로 교차확인.
- 판정: **PASS-WITH-FIXES** — BLOCKING/MAJOR 0.
  - 핵심 반증: ① **access 라벨 정확** — ROUTINE_USES `relation_type` = `sync_routine` 이 `kind`(parse_referenced_tables write동사 DELETE/MERGE/INSERT/UPDATE, write-wins 병합)로 세팅(`metadata_graph.py:388`, `routines.py:35,90,120`) → DELETE/write 프로시저 정확 라벨, `or "read"` 폴백 미발동(엣지 항상 read/write). ② **_fetch_routine_returns 견고** — `routine_objects(scope_key,schema_name,routine_name,returns)` alembic 0034 실존, node_key `scope:schema.name()` 역파싱 MATCH, 파라미터 바인딩(인젝션 안전), conn=None/예외→"" 비차단, autocommit conn 트랜잭션 무오염. ③ **config cap gated** — dry_run confirm 이 LLM 호출 수 명시(`admin.js:8442`), clamp(BATCH≤64)·node_budget 유지 → 하드가정 파손 0, "틱당 순차" 주석 정합(process_pending for-loop). ⑤ caveats 빈값 end-to-end 정상(`admin.js:8762` `if(a.caveats)` falsy 생략, 저장 `or ""`). ⑥ 출력 계약 불변·본문이 returns/touches 실제 참조·진짜 위험(DELETE/민감/현금성) 보존(과억제 아님).
- CONFIRMED(MINOR, **수정**): untrusted-data 규칙(`llm.py:917`)이 신설 top-level `touches`(테이블명)·`returns`(반환형)를 DATA 열거에서 누락 — DB 인트로스펙션 상류(신뢰불가) 유래라 프롬프트 인젝션 표면. **수정**: 열거에 `returns`/`touches` 추가(+ "table names, return types … or database introspection" 문구).
- CONFIRMED(MINOR, **수정**): P2(touches/returns 투영·dedup·access 매핑) 회귀 무방비(기존 `test_build_payload_routine_fields` 는 ctx={}) — 555노드 재생성 직전 조용한 파손 위험. **수정**: `test_build_payload_routine_touches_returns` 신설(dedup·빈테이블 skip·Table 미투영·빈 returns 키생략) → PASS.
- 수용(코드변경 없음): (MINOR) BATCH 4→10 은 틱당 순차 LLM ~2.5배→틱 지속↑, 설계 경계 내(clamp 64, lease 900s)+heartbeat(PR#567) 완화 — 인지. (NIT) schema 없는 루틴 returns skip(비차단)·returns 쿼리 routine_type 미필터 LIMIT 1(동명 fn/proc 희귀)·relationships '연결 정보 없음' vs analyze-from-visible 경미 긴장(사실진술, 실모순 아님).
- 검증: 수정 후 py_compile 3파일 PASS · `test_routine_dbanalysis.py` **23 PASS**(신규 2 포함) · 원 세션 make test PYTEST_RC=0 + 라이브 LLM(자기-불평 전멸)·라이브 payload(touches/returns) 유효. POST-DEPLOY cc_data_main 재생성 후 표본 caveats + 커버리지(555) 재확인(T69.5).

## REV-20260710T175412-ai-claude-feature-0016-rtuse-camera-pd [SKIPPED: docs-only POST-DEPLOY 실측 기록 — 코드 변경 0] — §71 완수 기록
- 대상: feature-0003 TEST §71 POST-DEPLOY append + feature-0016 TASK T71.3 완료 + REPORT POST-DEPLOY 절 + MODIFY CHG. 코드/자산 변경 0(순수 문서).
- 근거: §71(PR #662, main b7d7d871→라이브 a24415a5)의 실 Windows Chrome POST-DEPLOY 실측(win-browser relay, `shop_pt.T_ItemInfo` 상세 `[data-rtuse]` 18행 실클릭 → 카메라 팬 [3600,7092]→[2523,7871] + 상세 전환 동시, pageerror 0, 자산 curl 확증)을 정본에 기록. 코드 diff 부재 → §18.8 적대 패널 불요(SKIPPED). §71 코드 diff 의 적대 리뷰는 원 cycle inline REV-20260710T163512 + 본 세션 독립 subagent 리뷰(VERDICT PASS, BLOCKING/MAJOR 0)에서 완료.
- 배포: §71 cycle 에서 이미 완료(무중단 롤링·healthz PASS). 본 cycle 은 배포 없음(docs-only).
## REV-20260710T233000-ai-claude-feature-0016-layoutmemo [SUBAGENT: PASS-WITH-FIXES] — §73 배치-정렬 함수 위상-서명 메모이즈 캐시 staleness 적대 리뷰
- 단일 목적 적대 패널: "정렬 함수(_metaRelOrderAll·_metaSimGroups) 출력이 바뀌는데 `_metaTopoSig()`는 안 바뀌는 경로" = stale 캐시 버그류만 전수 탐색. 코드 실측(호출부·읽는 상태 전수 grep).
- **BLOCKING 0, MAJOR 0.** 리뷰가 확인한 **안전 항목**: ① simGroups side-effect(groupOrder/groupTableOrder) 는 simGroups 내부에서만 read/write·외부 소비자 0(drag/collapse/emission 무참조)·resetModel 만 clear → 적중 시 skip 안전 ② relOrder in-place 안정화 멱등 ③ category collapse 는 schemaIdx 불변(catInfo.ids 는 collapsed 무관 전량 push)이라 relOrder 캐시 유효 ④ 비-REFERENCES edges·weight·cardinality 는 relAdj 범위 밖이라 서명 제외 정당 ⑤ analyzed 는 state 마커(emission)라 layout 무관 ⑥ 노드 iteration order 무영향(name 정렬·key 배정).
- CONFIRMED **F1 [HIGH, 라이브 자동 트리거] — 수정**: `_metaSimGroups` Phase-3 역할 폴백 `roleFam=_metaRoleOf(t.key)`(→`_metaGraph.roles`)가 서명 밖. AI 분석 완료(2.5s 폴 `_metaGraphMarkAnalyzed`→`roles.set`+roleChanged rebuild)는 nodes/edges/schemaExpanded/mode 무변경 → 서명 무변경 → simGroups stale → 역할 블록 재그룹핑 미반영(칩 색만 갱신, 블록 구조 동결). **수정**: `_metaTopoSig` 에 `roles` Map 해시(rn+rh) 포함.
- CONFIRMED **F2 [MEDIUM, latent] — 수정**: 재-ingest(`_metaGraphIngest`)가 기존 키의 `name`/`fqn`/`cluster_id`/`cluster_label` 변경 — simGroups(be:클러스터 4437·cluster_label 4493·affix)·relOrder(name 정렬·fqn 스키마귀속) 소비. 키만 해시라 stale. 라이브 재현 경로 미확인이나 계약 결함. **수정**: 서명 노드 루프가 키+name+fqn+cluster_id+cluster_label 해시.
- NIT(하드닝, **수정**): `_metaGraphResetModel` 이 캐시 3필드 미클리어(schemaExpanded.clear 결합 의존) → 명시 클리어 추가.
- 근본원인(리뷰 지적): 서명이 노드 **키만** 해시하던 것 → 정렬 함수가 읽는 노드 **객체 속성+roles** 로 확장.
- 검증: 수정 후 신규 테스트 T6(roles·cluster_id·name 변경 시 서명 상이 + roles 변경 후 rebuild stale 아님) 추가 → `test_g6build_layoutmemo.js` **19 PASS** + 회귀 150 = **169 PASS** · node --check. 캐시적중==fresh 좌표동일 불변 유지.
## REV-20260710T233000-ai-claude-feature-0016-minimap-reuse [SUBAGENT: PASS-WITH-FIXES] — §74 미니맵 전체-이미지 재사용 diff 적대 리뷰 [머지 재번호 §70→§73→§74]
- 대상: CHG-20260710T230000-minimap-reuse (admin.js `_metaMinimapGeomSig`·`_metaPatchMinimapReuse` + 서명 배선 + minimap `key:"minimap"` + afterdraw 드래그 무효화 + 신규 test).
- 방법: §18.8 적대 리뷰. 초기 2렌즈(정확성/UX) user-interrupt 중단·렌즈1 이 linchpin(H1) 적발. 수정본 집중 확인 리뷰(H1~H5)에서 H2 신규 BLOCK 추가 적발. 둘 다 수정·테스트 커버.
- **BLOCK 2건→수정**: **H1(no-op)** G6 plugin 은 첫 draw 의 initRuntime 에서 lazy 생성 → init 직후 `getPluginInstance` 실패 → 패치 사멸 → `await g.draw()` 직후 이동. **H2(드래그 stale)** 드래그(`element.draw({stage:"translate"})`, `_metaG6Apply` 미경유)도 `AFTER_DRAW`(stage:"translate")를 발생 → stale 서명 skip → 미니맵 얼어붙음(원본 대비 회귀) → `afterdraw` stage 무효화. D 섹션 10 테스트 lock.
- 클리어: H1 타이밍(draw 직후 동기 설치·첫 렌더 blank 없음), H3 서명 필드 정합, H4 멱등·안전(no-op 폴백), H5 renderMask 독립.
- 검증: 수정 후 신규 **35 PASS** + 회귀 **150 PASS** · `node --check`. POST-DEPLOY PB-0008(feature-0003 TEST §74).


## REV-20260710T234500-ai-claude-feature-0016-layoutmemo-postdeploy [SKIPPED: docs-only POST-DEPLOY 실측 기록 — 코드 변경 0] — §73 POST-DEPLOY 완수 기록
- 대상: TEST.md/TASK.md/REPORT.md POST-DEPLOY 실측 결과 기록만 — 코드/자산 diff 0. §18.8 패널 비적용(SKIPPED).
- 근거: 배포·구현 자체는 §73 REV-20260710T233000 [SUBAGENT: PASS-WITH-FIXES] 에서 완료 검증. 본 cycle 은 라이브 실측 결과 문서화(main e6b7b68f, MISS 59→HIT 8ms 7.4× 급감, 위치 이동 0).

## REV-20260710T093000-ai-claude-feature-0016-minimap-reuse-postverify [SKIPPED: doc-only POST-DEPLOY 기록] — §74 미니맵 재사용 라이브 검증 결과 append
- 본 cycle 은 §74 minimap-reuse 의 POST-DEPLOY PB-0008 라이브 실측 결과(PASS)를 TEST.md §74 Run·TASK.md T74.5 에 기록하는 **비-정책 doc-only** 변경이다(코드·자산 변경 0). §18.4 에 따라 리뷰 패널 SKIP.
- 원천 코드 cycle 의 적대 리뷰는 REV-20260710T233000-ai-claude-feature-0016-minimap-reuse [SUBAGENT: PASS-WITH-FIXES](H1·H2 2건 BLOCK 적발→수정) 참조.
## REV-20260710T230000-ai-claude-corp-feature-0016-graph-detail-colsel [SUBAGENT: PASS] — §75 상세 패널에서도 컬럼 선택 배선 diff 적대 리뷰
- 대상: `unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css,admin.html}` (41삽입/10삭제·3파일) + 신규 헤드리스 테스트 `tests/headless/test_detail_colsel.js`. frontend-only·마이그 0·Minor(§12.3).
- 판정: general-purpose 적대 리뷰어 6축(정확성/회귀/이벤트/CSS/a11y/엣지케이스) 전수 검토 → **Critical/Major/Minor 결함 0, PASS**. 확인된 non-issue: ①`data-col`=`c.key`(컬럼 노드 키) 정확·`esc()` 이스케이프·getAttribute 라운드트립 무손실·`_metaGraphShowDetail` 은 캔버스 컬럼클릭과 동일 경로 → 오선택·인젝션 0. ②캐럿 restructure 후에도 `closest(".amgr-col-rel")` → `.amgr-col-body` 정상 해소·repo 전역 `data-colrel` 잔존 0·`.amgr-col-toggle` 은 의도적 legacy CSS만(JS 바인딩 0). ③캐럿·선택 버튼은 (중첩 아님) 형제 → 이중발화 0·`stopPropagation` 양쪽·셀렉터 disjoint. ④`.amgr-col-relcount margin-left:auto` 가 `.amgr-col-rel .amgr-col-select`(flex) 안 → 우측정렬 유지·specificity(block↔flex) 정합·plain padding 정합. ⑥컬럼 키 항상 존재·80컬럼 cap 보존·긴 설명 자연 줄바꿈 무회귀.
- 적용한 a11y nit 2건(리뷰 반영): ①캐럿 `aria-controls="amgr-colbody-<key>"`(body에 `id` 부여) + 상태중립 `aria-label="참조 관계 토글"`. ②선택 버튼 `aria-label="<name> 컬럼 선택"`(설명이 접근성 이름 오염 방지). 반영 후 `node --check` PASS + 격리 렌더 테스트 8/8 재확인.
- 근거: 코드 diff 존재(순수 프론트 추가) → §18.8 적대 패널 수행·PASS. main rebase(§71/§72/§73/§74 병렬 머지) 후 admin.js 자동병합·재검증 완료. POST-DEPLOY 실 Windows 육안은 T75.4(배포 후, `visual_verification_scope`).

## REV-20260710T222000-ai-claude-corp-feature-0016-cullrefkeep [SUBAGENT: PASS-WITH-FIXES] — §76 컬링 참조·상호작용 보존 + 뷰포트 내 노드 엣지 컬링무효 + rAF 실시간 드래그 컬링 diff 적대 리뷰
- 대상: 커밋 `82885c5d` — `admin.js`(_faKeep/_clusterHasFocus + nodePosAll/_inView/_edgeExempt pre-pass + 3 컬 지점 _keepFromCull/_clusterKeep 가드 + rAF 실시간 드래그 컬링, 68줄) + `admin.html` 버스터 + headless `test_g6build_cullrefkeep.js` + feature docs. frontend-only·마이그 0. **cross-session resume** — 원본 세션(ff7fb347, 세션 한도 중단)의 in_progress 적대 리뷰를 이어받아 완수.
- 패널: general-purpose 적대 리뷰어 5축(pre-pass 위치수학 / edgeExempt 정확성 / rAF 실시간 드래그 안전 / 성능 / 회귀) 전수 검토 + `node --check`·cullrefkeep 10/10·회귀 244 실측. **판정 PASS-WITH-FIXES — BLOCKING/MAJOR 0, MINOR 3 + NIT 1.**
- 실증된 PASS 축: ①위치수학 — pre-pass(5037)와 렌더 컬 판정(5223/5283)의 free-place 보정이 대수적 동일(`colLeftX=_fp[0]-TXOFF, ty=_fp[1]`), `_offView` bbox 3 컬 지점 일관, clusterOffset/groupOffset 양측 동일 소스. ②edgeExempt — `_foldTbl`(컬럼→부모테이블 폴딩)이 컬럼-끝점을 _inView(테이블 key) 기준과 정합, `a!==b` 자기루프 배제·HAS_*/SCHEMA_REF/용어 제외 타당, 오펀 방지(_clusterKeep combo 앵커). ③rAF 안전 — `if(!_cullRaf)` 재진입 가드 + 콜백 동기 null 리셋 + `_metaG6Apply` 직렬화(5656) + **피드백 루프 없음**(`_metaG6Apply(false)`→fit 미호출→카메라 transform 없음→aftertransform 재발화 없음, 무한루프 불가) + 밴드 로직 fall-through 유지. ④성능 — 레이아웃 메모이즈(§73) 재사용, 직렬화가 느린 프레임 자연 스킵.
- 결함 원장 및 처리:
  - **M1 [MINOR/문서] — 반영(수정)**: "무선택 시 예외 0 = 성능 무손실" 주장이 T76.4 in-view 확장(`_edgeExempt` 는 `_cullActive && _inView.size` 만으로 발동·선택 무관) 이후 거짓. DECISIONS ADR-037(트레이드오프 정정 단락 추가)·MODIFY CHG·REPORT §76 을 "무선택·무연결 시에만 예외 0; in-view 연결 상대는 선택 무관 예외(규모=in-view edge density 비례·유계)" 로 정정.
  - **M2 [MINOR/테스트] — 부분 반영(핵심 추가)**: 엣지 1개 seed 라 "컬링 유효(<100)" 가 자명 통과였던 갭에 **T4 dense off-view 케이스 추가**(신규 5 check) — 뷰포트 밖 노드끼리만 연결된 대량 B-B 엣지(35개)가 in-view 에 안 닿아 `_edgeExempt` 에 안 들어가고 계속 컬링됨을 실증(예외 팽창이 컬링 무력화 안 함 = 원 draw 폭발 회귀 재발 방지). cullrefkeep 10→**15 PASS**. 주의: 이 빌더는 관계-인지 레이아웃이라 dense 구성의 뷰포트를 재계산해야 정합. **수용(후속)**: rAF 드래그 경로·스코프 전환 `_cullRaf` 정리·free-place 좌표·ROUTINE_USES 예외의 헤드리스 커버리지는 코드 정독으로 확증됨(테스트 미구동) → §77/후속 사이클에서 보강.
  - **M3 [MINOR/성능] — 수용(기록)**: nodePosAll/_inView/_edgeExempt pre-pass 가 매 build O(N)+O(E) 상시 실행되고 nodePosAll 은 현재 소비처 없음(순수 forward-provisioning). **미수정 근거**: 소비처(§77 커스텀 미니맵)가 사용자 이미 요청한 즉시 후속이라 dead-code 아닌 provisioning 이고, 리뷰어 추정 비용 sub-ms(수백 노드), 드래그 성능 목적에 유의 회귀 미관측. 배포 직전 hot-path 변경은 재-리뷰 리스크 → §77 착수 시 nodePosAll 소비와 함께 게이팅 재검토. DECISIONS ADR-037 에 기록.
  - **N1 [NIT] — 수용**: rAF 스케줄러(`.bind(window)`) vs 캔슬러(언바운드 cAF) 페어링 비대칭. 리뷰어 분석대로 비-strict sloppy 모드 `this`→window 폴백 + 브라우저 rAF/cAF 상시 쌍존재 + try/catch fail-soft 로 **실무 무해**(유일 파손조건 rAF존재·cAF부재는 현실 미발생, no-op 시에도 리셋 모델 대상 잉여 1회 재빌드로 크래시 없음). 가시 회귀 아님 → 미수정.
- 반영 후 재검증: `node --check` PASS · cullrefkeep **15/15** · 그래프 회귀 11 스위트 **249 PASS / 0 FAIL**(agglod 8·category 26·collod 20·cullrefkeep 15·edge_visibility 71·layoutmemo 19·minimap_reuse 35·viewportcull 6·vpack 19·colnav 22·detail_colsel 8).
- **deploy_scope: included 근거 기록(§12.2/§16.3)**: FIRST_REQUEST.md 전역 `deploy_scope: included`(프로젝트 standing 값) + FUNCTION.md feature-level 정합 → cycle 종료 시 confirm 없이 자동 배포 승인. frontend 자산 baked(admin.js/admin.html) — 배포 후 실 Windows 브라우저 육안(PB-0008, T76.3)이 완료 게이트. 첫 배포 직전 "deploy_scope: included 활성" 1줄 표면화.
- 근거: 코드 diff 존재(핵심 렌더·컬 경로) → §18.8 적대 패널 수행. BLOCKING/MAJOR 0 → 랜딩 차단 없음. M1(문서)·M2(핵심 테스트) 반영·M3/N1 수용 기록 완료.

## REV-20260711T120531-docs-archive [SKIPPED:mechanical-archiving] — §5.5 아카이빙
- Related Change: CHG-20260711T120531-docs-archive. 재구성 md5==원본(assert)·verbatim·런타임 코드 0. 승인: 사용자 지시+§5.5.

## REV-20260710T170000-ai-claude-feature-0016-nodeanalysis-postdeploy [SKIPPED:doc-only-postdeploy] — §69 T69.5 POST-DEPLOY 완수 기록 (코드 무변경)
- Related Change: CHG-20260710T170000-nodeanalysis-postdeploy. 코드/자산 변경 0 — TASK(T69.5 [x])·REPORT(POST-DEPLOY 절)·MODIFY(CHG) doc-status 갱신뿐.
- Panel skip 사유(§18.8 — doc-only, 런타임 코드면 0): §69 코드 결함면은 원 cycle REV-20260710T165030 [SUBAGENT: PASS-WITH-FIXES] 에서 적대 패널 완료. 본 changeset 은 배포·재생성 실측 결과 기록. 배포 정합은 라이브 실증(config 값·프롬프트 계약·healthz·run 7c75ddcb 715 done/0 failed·caveats 자기-불평 사실상 0)으로 대체.
- Human Approval: deploy_scope: included(전역) + 사용자 "전부 진행" 승인 — §69 재개 cycle 의 완수 tail.
## REV-20260713T120500-ai-claude-feature-0016-content-cluster [SUBAGENT: PASS-WITH-FIXES] — 카테고리 밴드 컨텐츠 단위 그룹핑(semantic cluster 재작업) diff 적대 리뷰
- 대상: 커밋 4878fe20+a762abe5(+미커밋 문서) — `semantic_cluster.py` 재작업·`metadata_graph.py` Routine 투영·`llm.py` cluster_label·`shared/config.py`·requirements(numpy)·alembic 0040·신규 테스트. backend-only(프론트 0). §18.8 general-purpose 적대 리뷰어 8축(결정론/트랜잭션/키정합/AGE/LLM/성능/회귀/마이그레이션) + 라이브 프로브(트랜잭션 롤백) 교차.
- 패널 판정: **PASS-WITH-FIXES — BLOCKING 0 · MAJOR 1 · MINOR 5 · NIT 5.** 통과 축: legacy 시그니처 byte-동일성(테스트 잠금)·`_run_step` force-커밋으로 owned 폴백 rollback 안전·키 정합(`_effective_schema`≡`_rag_effective`, 루틴 store label lower 계약)·AGE 8컬럼/agtype null 안전(Table 동형)·`llm_cluster_label`=product_classify verbatim 동형·0040 expand-safe(migrate-lint 실측 PASS)·프론트 무변경 전제 성립(simgroups be:/ingest generic/Routine∈g.tables 코드 확증). pre-existing FAIL 1건(`test_sync_graph_rollback_on_error_restores_autocommit`)은 기준 커밋(37d45aea)에서도 동일 FAIL 실증 — 본 diff 무관.
- 결함 원장 및 처리 (전건 같은 cycle 반영, 커밋 3차):
  - **M1 [MAJOR/도달성] — 수정**: 분석 완료가 rag/routine 행 updated_at 을 전진시키지 않아, 백로그 0 정상 상태에서 top-500 창 밖의 분석-보유 행이 영구히 구 시그니처 유지(RC4 인과 실패, silent). → 백필에 **분석-신선 표적 선별**(EXISTS: 최신 done j.updated_at > 행.updated_at, 테이블·루틴 각각, cap=batch) 합류 + 처리 시 updated_at 명시 touch(시그니처 불변이어도 touch → 조건 해소·재선별 차단, 멱등). 회귀 테스트 추가.
  - **n4 [NIT→실결함 승격/키정합] — 수정 (라이브 확증)**: `_fetch_analysis_text` 가 rag scope('common')로 필터하나 node_analysis_jobs.scope_key 는 **datasource_key**(라이브 GROUP BY 실측 — scoped 매칭 0/255 vs unscoped 255/255) → RC4 분석문 주입이 전면 무효였음. → scope ANY(rag-scope, datasource) 2-probe 로 수정 + 테스트가 ANY 쿼리 형태 잠금. **리뷰 패널이 아니었으면 배포 후에도 조용히 죽어 있었을 결함.**
  - **m1 [MINOR/tx] — 수정**: `_step_routines` 폴백의 무조건 `c.rollback()` → `if owned:` 가드 + `_pending[0]=0`(_step_relationships 선례 정합 — 외부 주입 conn 미커밋 작업 보호).
  - **m2 [MINOR/성능] — 수정**: 게이트 OFF/전량 캐시 적중에도 라벨용 분석문 N+1 점조회 실행 → 캐시-미스 클러스터 한정 lazy 콜백(fetch_summaries)으로 이동.
  - **m3 [MINOR/캐시] — 수정**: kv 라벨 key `label:{ds}:{schema}:{h16}` 가 varchar(128) 초과 가능(초과 시 silent 캐시 부전 → 매 pass LLM 재호출 누수) → 네임스페이스 sha256[:12] 고정폭화(`label:{ns12}:{h16}`≈35자). 구 해시 행 잔존(TTL 없음)은 수용 — 규모 유계(클러스터 수), 청소는 후속.
  - **m4 [MINOR/메모리] — 수정**: 대형 ds fetch 의 Python float 리스트 ~230MB transient(1g cgroup headroom) → `_parse_embedding` 이 float32 ndarray 즉시 변환(~29MB) + 호출부 `is None` 판정(ndarray truthiness).
  - **m5 [MINOR/churn] — 수정**: pass-전역 순번 id 는 앞 스키마 증감이 뒤 전체 id 를 shift(대량 UPDATE·재투영·프론트 접힘상태 무효화) → **스키마-로컬 순번**(패널이 프론트 nsKey 스키마 네임스페이스로 전역 유일성 불필요 확증). 테스트 계약 갱신.
  - **n1·n2·n3 [NIT] — 수정**: natural-sort 표기→사전순 정정 / `_fetch_analysis_text` tie-break id DESC / SAVEPOINT 실패 경로 ROLLBACK TO 후 RELEASE(서브tx 잔존 방지).
  - **n5 [NIT] — 수용**: 커밋 메시지 테스트 카운트 오기(불변 이력 — 문서 카운트는 정정).
- 라이브 프로브(본 세션, 롤백·무변경) 추가 적발·수정 2건(리뷰와 독립): SAVEPOINT 미격리 연쇄 실패 / base-τ 단일연결 blob(254/255) → mutual-kNN+τ-상승 재분할(MODIFY CHG-20260713T113500). 반영 후 재프로브: cc_data_main **37 클러스터/199 편입** 유지·error 0.
- 반영 후 재검증: 신규 테스트 파일 **24 PASS** + 연관(category refine·routine crossdb) 스위트 PASS + 전체 스위트 컨테이너 pytest(재실행) + py_compile·migrate-lint PASS.
- **deploy_scope: included 근거 기록(§12.2/§16.3)**: FIRST_REQUEST.md 전역 `deploy_scope: included` — cycle 종료 시 confirm 없이 배포 진행(첫 배포 직전 1줄 표면화). numpy 실효는 insight-worker/ask-worker/agent 이미지 재빌드 필수(make up 은 worker 미재빌드 — 배포 노트).
## REV-20260713T105224-ai-root-feature-0016-minimap-fullview [SUBAGENT: SHIP] — §77 미니맵 전역 개요 유지(컬링 부분방출 재복제·카메라 재적합 금지) diff 적대 리뷰
- 대상: `unit/feature-0003-agent-web-ui/src/static/graph/graph-core.js`(_cullPartial 추적 4지점+리셋 2곳 + renderMinimap/setCamera 게이트) + `tests/headless/test_g6build_minimap_reuse.js`(Section E 16 신규). frontend-only·마이그 0·Minor(§12.3).
- 패널: general-purpose 적대 리뷰어 — diff 전문 + graph-core.js 전체 컨텍스트(컬링 지점·리셋·aftertransform·검색/스코프 전환 경로) + G6 vendor minimap 클래스 역어셈블 + 번들 레시피 재현으로 headless 51 PASS 독립 재실행. **판정 SHIP — BLOCKING/MAJOR 0, MINOR 2 + NIT 1(전부 미수정 수용).**
- 실증된 PASS 축: ①상태 타이밍 — `_cullPartial` 은 build 동기 세팅·onRender 는 trailing debounce(128ms)라 발화 시점 플래그·서명·캔버스가 항상 최종 build 로 coalesce(극단 왕복 포함), translate 끼어듦은 gate2 흡수. ②불변식 "hasFullImage ⇒ 캔버스=마지막 무컬링 렌더" — 덮어쓰기 경로 전수에서 위반 도달 불가(plugin canvas 1회 생성 유지 실측). ③스코프/검색 전환 stale 이미지 — 전 경로가 `_metaGraphResetModel`(partial=false) 경유 + 첫 build 가 카드/소형(<400) 또는 카드 게이팅으로 무컬링 → 서명 불일치 재복제로 즉시 교체. ④G6 내부 정합 — this. 동적 디스패치로 래퍼 확실 가로챔·createLandmark key-cache 무오염·onMaskDrag 팬 비율은 동결 카메라와 이미지 축척 일치·maskBBox 요소 bounds 비의존·마스크 드래그 중 plugin 자체 setCamera 억제. ⑤컬링 지점 전수 — `_offView` 방출 감소 4곳 전부 마킹, catHidden/hiddenKinds/col-lod/edge-lod 는 사용자·줌-LOD 사유라 미마킹이 올바름, 엣지 드롭은 노드 컬의 하류(플래그 선행 보장). ⑥테스트 정합 — E 16 단언 전부 래퍼 의미와 일치·51 PASS 독립 재현.
- 결함 원장 및 처리:
  - **M1 [MINOR/UX] — 수용(후속 후보)**: 컬링 지속 중 전체 이미지의 staleness 표식 부재 — 줌인 중 kind 필터/펼침 등 구조 조작 시 미니맵이 과거 개요를 무기한 표시할 수 있음(특히 "full 밴드 내 줌아웃 + 중심 불이동" 은 uncull rebuild 자체가 없는 기존 §65 gap). 코드 주석에 트레이드오프 명시·어떤 무컬링 build 로도 자가치유·pre-§77(부분집합 재복제)보다 엄격히 덜 틀림 → 미수정. 후속: skip 상태 시 미니맵 "개요 고정" 배지 1개.
  - **M2 [MINOR/과도기] — 수용**: 플래그 전환 창(스코프 전환 fetch 대기·draw in-flight)의 setCamera 통과가 과도기 bounds 재적합 가능 — 새 스코프 첫 렌더/다음 transform·renderMinimap 이 즉시 교정(자가치유), 관측 창 극소 → 미수정.
  - **N1 [NIT] — 수용**: `__hasFullImage` 마킹이 orig() 성공 전 선-대입 — §74 `__lastGeomSig` 와 동일한 기존 패턴·가정적 경로 → §74 정리 시 함께 성공-후 마킹으로.
- 검증: minimap_reuse **51 PASS** + 그래프 headless 11 스위트 **265 PASS / 0 FAIL** + `node --check --input-type=module` PASS(test-runs.d/20260713T105224-minimap-fullview.md).
- **deploy_scope: included 근거 기록(§12.2/§16.3)**: FIRST_REQUEST.md 전역 `deploy_scope: included` → cycle 종료 시 자동 배포(첫 배포 직전 1줄 표면화). frontend 자산 baked — 배포 후 실 Windows 육안(PB-0008, T77.5)이 완료 게이트.
- 근거: 코드 diff 존재(핵심 미니맵·컬링 경로) → §18.8 적대 패널 수행. BLOCKING/MAJOR 0 → 랜딩 차단 없음.

## REV-20260713T115500-ai-root-feature-0016-minimap-fullview-r2 [SELF: PASS] — §77 2차 델타(전체-기하 서명·시딩·경합 수렴) 적대 검토
- 배경: 1차 [SUBAGENT: SHIP](REV-20260713T105224) 이후 **PRE-LANDING 라이브 검증(PB-0008)이 결함 3건을 연쇄 적발**해 설계가 확장됨 — (적발①) fit-클램프 대형 모델은 무컬링 build 자연 미발생(1,249 노드 fit 방출 153)이라 전체 이미지 영영 미시딩 → 컬링-유예 시딩 build(`_metaMinimapSeedKick`) (적발②) boolean full-마킹이 접힘 카드 시점 이미지를 펼침 후 현재로 오인·시딩 억제 → 전체-기하 서명 `_miniFullSig`(nodePosAll+edges.size) 현재성 판정 (적발③) 시딩-마킹 debounce(128ms) 경합으로 마킹 무산 + seedRun latch 고착 → stale-skip 분기 force 재-kick + `_miniSeedTimer` 중복 방지.
- 패널 형태: 2차 델타 서브에이전트 리뷰가 **사용량 한도(session limit, 12:30 리셋)로 중단** → 인라인 셀프 적대 검토로 대체 수행(§18.8 패널 자체는 1차에서 수행 완료·본 델타는 headless 재현 + 라이브 e2e 이중 잠금). 후속 패널 재검이 필요하면 머지 후 diff 재리뷰 가능.
- 셀프 검토 원장(공격 지점별):
  - **시딩 진동(seed→cull→seed 교대)**: 시딩 후 `_miniFullSig` 는 컬링·뷰포트와 무관(F2 가 culled/seeded build 동일 서명 단언) → 기하 불변이면 stale 조건이 닫혀 재-kick 불가(F7 실증). 진동 없음 판정.
  - **force 재-kick 폭주**: 재-kick 은 debounce 발화(=128ms 상호작용 소강) 시에만 + 타이머 가드 → 연속 팬/줌 중 kick 0, 소강당 최대 1회(구조 변경당 시딩 1프레임 ≈ pre-§65 빌드 1회 비용). 유계 판정.
  - **시딩 build 부작용**: `_metaG6Apply(false)` — fit 미호출(카메라 불변)·상태는 model bake(선택/드래그 보존)·직후 대형 draw 잔존은 다음 상호작용 rebuild 가 재컬링(과도 상태). 무해 판정.
  - **서명 커버리지**: 컬럼 펼침=`h`(realH) 포착·카테고리 접힘=catHidden 제외 포착·kind 필터/그룹 접힘=place 변화 포착·엣지=count 만(타입-flip 미포착 — 168×112px 스케일 시각 무의미, 수용). 산정 비용 O(N) sub-ms(1.3k 엔트리).
  - **타이머 수명**: 리셋 2곳(clearTimeout+null)·발화 시 suspend 1회 소비 후 무해한 전량 build·그래프 재생성 시에도 안전(현재 graph 에 apply). leak 없음 판정.
  - **테스트 flake**: 타이머 350ms vs 대기 450/500ms(마진 100~150ms), node 단일스레드 타이머 — 낮음. 65 PASS 재현 3회.
- 검증: headless 11 스위트 **279 PASS / 0 FAIL**(라이브 적발 3건 각각 F8/F9/F1~7 로 재현·잠금) + **라이브 e2e PASS**(시딩 수렴 fullSigCurrent=true → 줌 2.0 컬링 rebuild 방출 1,573→153 에 미니맵 해시 완전 불변 → 팬 불변 → 스코프 전환 재렌더 → pageerror 0). 상세 test-runs.d/20260713T105224-minimap-fullview.md.
- 판정: **PASS — 랜딩 차단 없음.** 1차 리뷰의 M1(staleness 표식)은 시딩 도입으로 실질 해소(stale 창이 무기한→~0.5s), M2(과도기 창)·N1(선-마킹)은 수용 유지.
## REV-20260713T143000-ai-claude-feature-0016-content-cluster-h1 [SKIPPED:single-line-hotfix] — 루틴 fetch scope 비대칭 1줄 수정
- Related Change: CHG-20260713T143000-content-cluster-h1. WHERE 절 1건(스코프 필터 제거) + 테스트 assert — 본 cycle REV-20260713T120500 패널이 검증한 코드면의 국소 후속(같은 n4 비대칭 클래스, 라이브 실증으로 적발·확인). 인가·경계·마이그 0.
- Panel skip 사유(§18.8): diff 가 단일 WHERE 절 축소(필터 제거 — 반환 집합이 ds 파티션으로 유계)이고, 원 패널이 동일 클래스(n4)를 이미 적대 검증. 회귀는 테스트 assert 로 잠금. 라이브 재가동 실증이 완료 게이트.
## REV-20260713T023517-ai-root-feature-0016-graph-pixi [SKIPPED:docs-only-plan]
- §78 PixiJS v8 렌더러 교체 **계획 수립**(BLUEPRINT + TASK §78 plan-review) — 코드 diff 0, docs-only. §18.8 패널은 코드 산출물 부재로 SKIPPED. 계획 자체의 검증 게이트는 §7.1 human plan-review(PLAN-APPROVED 마커) + Phase A POC exit gate(디자인 D1~D6·성능 p95)로 이원화되어 있음. 구현 cycle(Phase A~C)에서 §18.8 적대 패널 정상 적용 예정.

## REV-20260713T042924-ai-root-feature-0016-graph-pixi-poc [SKIPPED:poc-only]
- §78 Phase A PixiJS POC — poc/ 격리 폴더(pixi-poc.html·shoot_pixi.py·vendored pixi.min.js) + docs 기록. **제품 코드/자산(graph/*·admin.js·admin.html) 변경 0**. verify-completion check#4 는 poc 의 .html/.js 를 코드로 감지하나 제품 표면 무변경이라 §18.8 적대 패널 SKIPPED. 실제 검증 게이트는 BLUEPRINT §4 Exit A(디자인 D1~D5 + 성능 p95) 로 실 Windows Chrome(PB-0008 relay) 실측 PASS. 제품 코드 통합(Phase B)에서 §18.8 정규 적용.

## REV-20260713T051139-ai-root-feature-0016-graph-pixi-adapter [SKIPPED:unwired-new-file]
- §78 Phase B-early SceneAdapter(graph-renderer-pixi.js) 신설 — **미배선 신규 파일**(admin.html·graph-core.js 무변경, 실 제품 렌더 경로에 아직 미연결). 어댑터 자체 검증은 순수테스트 28 PASS + 실 Windows Chrome PB-0008(디자인·성능·이벤트) 로 수행. §18.8 적대 패널은 B-late(graph-core 렌더러 seam 배선 = 실 사용자 표면 변경) 시 정규 적용. 신규 파일·미배선이라 현 커밋 SKIPPED.

## REV-20260713T060954-ai-root-feature-0016-graph-pixi-wire [SUBAGENT:graph-adversarial] — PASS-WITH-FIXES
§78 B-late graph-core seam 배선(G6→PixiJS) diff 적대 리뷰(Explore/opus, 실 코드 대조·추측 배제).
- **BLOCKING 1 수정**: B1 드래그/translateElementTo 후 hit-grid 미갱신 → 이동 요소 클릭 불가(dragend rebuild 없는 평범 노드/SC 카드). 수정: _moveElement·translateElementTo 종료 시 buildHitGrid 재구성(실증: 카드 200,150 이동 후 새 위치 _pick hit·옛 위치 miss).
- **MAJOR 4 수정**: M1 combo 드래그 시 배경 카드 미추종 → _moveElement combo 분기가 카드 객체도 동반 이동. M2 click-only 컨트롤(GX:/CATX:/접힌 CAT:·CATH:)이 pixi 에서 드래그돼 clusterOffset 오염 → graph-core 가 _metaElementDragEnable predicate 를 어댑터 cfg 로 주입, 드래그 진입 게이트. M3 미니맵 부분집합 표시 + M4 팬 GC churn → **pixi 모드 뷰포트 컬링 비활성**(GPU 상주라 §65/§67 CPU-raster 완화 불필요) 근본 해소 — _built 전량 방출로 미니맵 전역 + 팬 rebuild 소거.
- **MINOR 수정**: m1 destroy 시 window 리스너·ResizeObserver 정리. m2 노드 lineDash(그룹 배경 GB 점선) 소비. m4 드래그 중 미니맵 뷰포트 사각형만 갱신(콘텐츠 재그림 dragend 지연).
- **통과 확인(적대 검증)**: 좌표 API 방향(getCanvasByViewport=screen→model)은 이 diff 가 오히려 **수정**(graph-core 소비부 정합)·getElementRenderBounds min/max superset 정합·PIXI 전역 노출(UMD var)·미배선/reject 폴백(try/catch·null guard)·미니맵 재사용 패치 __reusePatched 조기 return — 전부 결함 아님 확인.
- 회귀: 어댑터 순수 33 PASS + 그래프 headless 279 PASS 무회귀. 남은 m3(seed/anchor 헛도는 무해 noise)는 정확성 무관 — POST-DEPLOY 후속.

## REV-20260713T062037-ai-root-feature-0016-graph-pixi-postdeploy [SKIPPED:docs-only-postdeploy]
- §78 Phase C POST-DEPLOY 라이브 PB-0008 결과 기록 — docs-only(코드/자산 0). 배선 코드 diff 는 선행 REV-…-graph-pixi-wire [SUBAGENT:PASS-WITH-FIXES] 에서 §18.8 적대 리뷰 완료. 본 커밋은 라이브 검증 기록이라 SKIPPED.

## REV-20260713T070223-ai-root-feature-0016-graph-pixi-polish [SUBAGENT:graph-adversarial] — PASS-WITH-FIXES
§79 PixiJS 후속(이슈 3건+오브젝트 풀) diff 적대 리뷰(Explore/opus, 실 코드 대조).
- **BLOCKING 1 수정**: B1 상태 halo 페인트 순서가 G6 역전(addChildAt(_,0))으로 analyzed/running halo 가 selected 테두리를 **완전히 가림**(분석된 노드 클릭 시 선택 피드백 소실 — 흔한 케이스). 수정: halo 를 states 순서대로 body 아래 **증가 인덱스** 삽입 + 상태별 2px 인셋(concentric 링) → selected(마지막) 최상위·다중 상태 동시 표기. 시각 실증: sel+analyzed 노드 보라(안)+진회색(밖) 링 동시 가시.
- **MAJOR 2 수정**: M1 running fill desaturate(G6 fillOpacity 0.45 — 앰버 역할색 위 주황 점선 위장 방지)가 어댑터에서 드롭 → _drawNode 가 running 상태 시 body fill alpha 0.45 적용(시각 실증: amber 노드 fill 흐려짐·주황 점선 선명). M2 오브젝트 풀·halo 무테스트 → 서명 로직을 PixiAdapterPure.nodeSig/edgeSig/comboSig/edgeId 순수함수로 추출·draw() 소비·**T17~19 테스트 10건 추가**(재사용/재생성 정합·type 변화·끝점 이동·bbox 변화).
- **MINOR 수정**: m1 node 서명에 n.type 추가(circle/rect 기하 방어). m4  빈 콘텐츠 시 (stale proj 엉뚱한 팬 방지). NIT 미니맵 드래그 로컬좌표 박스 클램프(박스 밖 극단 팬 방지).
- **수용(수정 불요)**: m3 풀 키 kind-네임스페이스(combo/node id 실무 분리 — 접두 SC:/GB:/fqn vs bare schema, 충돌 확률 낮음·pre-existing, 전 _objs 접근 재작성 과함). m2 node 서명 정밀도(재생성=안전, 재사용률 미세 손실). m5 cull-on JSON.stringify(pixi 모드 컬링 비활성이라 미실행 경로).
- 통과 확인(적대): 미니맵 좌표계 일치·edge/combo 재생성 정합·제거/재생성 루프 누수 0·순수함수 수학 정확 — 결함 아님 명시.
- 회귀: 어댑터 순수 **49 PASS**(T14~19 추가) + 그래프 headless **279 PASS 무회귀**. B1/M1 시각 실증·pageerror 0.

## REV-20260713T070819-ai-root-feature-0016-graph-pixi-polish-pd [SKIPPED:docs-only-postdeploy]
- §79 POST-DEPLOY 라이브 기록 — docs-only. 배선 코드는 선행 REV-...-graph-pixi-polish [SUBAGENT:PASS-WITH-FIXES] 적대 리뷰 완료. SKIPPED.

## REV-20260713T154500-ai-claude-feature-0016-content-cluster-postdeploy [SKIPPED:doc-only-postdeploy] — content-cluster TC.7/TC.8 POST-DEPLOY 완수 기록 (코드 무변경)
- Related Change: TASK TC.7/TC.8 [x] + REPORT POST-DEPLOY 절 + test-runs.d fragment. 코드/자산 변경 0 — 배포·라이브 실증(백필→임베딩→클러스터→AGE 수렴→PB-0008 PASS) 결과 기록.
- Panel skip 사유(§18.8): 코드면은 본 cycle REV-20260713T120500 [SUBAGENT: PASS-WITH-FIXES] + h1 REV-20260713T143000 에서 완료. 본 changeset 은 실측 기록. 검증용 QA 핸들은 서빙 사본 한정·원복 완료(repo·이미지 미포함).
- Human Approval: deploy_scope: included(전역, FIRST_REQUEST.md) — 사용자 원 요청("컨텐츠 단위로 묶이도록 개선")의 완수 tail.

## REV-20260713T081302-ai-root-feature-0016-graph-pixi-bitmaptext [SUBAGENT:graph-adversarial] — PASS-WITH-FIXES
§80 라벨 Text→BitmapText diff 적대 리뷰(Explore/opus, pixi.min.js BitmapFontManager/DynamicBitmapFont 내부까지 대조). BLOCKING 0.
- **MAJOR 2 수정**: M2 try/catch 폴백 무력 — dynamic-font glyph 래스터화는 지연(첫 width/render)이라 생성 try 밖 throw 시 폴백 안 되고 라벨 소실 → _makeText 에서 void b.width 강제 measure 로 실패를 생성 시점으로 당겨 catch→Text 폴백 실동작화. M1 CJK atlas 미회수(세션 전역 누적) — 실데이터는 대부분 **영문 테이블/컬럼명**(bounded ASCII glyph·고재사용)이고 한글은 UI chrome/용어 한정이라 실무 영향 제한적. bounded 트레이드오프로 문서화 + seam(labelEngine:'text') 탈출구 유지(내부 BitmapFontManager clear 는 미공개 API 라 미호출).
- **MINOR 수정**: m1 _hexNum→PixiAdapterPure.hexToTint(valid 플래그) — 비-hex(rgb()/named) fill 은 tint 표현 불가라 흰색화(비가시) 대신 **Text 엔진으로 강등**(실 fill 전량 hex 라 라이브 무트리거·잠재 방어). m2 T20 tautology → 순수 hexToTint 실경로 T20 7건(hex/3자리/number/rgb/named). m3 edge/combo 라벨 fontFamily 를 노드와 동일 system-ui 로 정규화(edge 는 기존 Pixi 기본 Arial → 일관성 개선, 문서화).
- **반증(적대 검증 결과 결함 아님)**: blur 우려 기각(dynamic font baseRenderedFontSize=100 texel/em > 구 Text 24~48 = 오히려 더 조밀·최대줌+dpr2 도 1:1 이상)·tint 색 정확(white base 곱셈)·풀 재사용 정합(nodeSig 에 labelText/Fill/Size 포함). anchor 수직 정렬 win-browser 육안 정합 확인(카드 중앙).
- 회귀: 어댑터 순수 **56 PASS**(hexToTint T20) + 그래프 **279 무회귀** + 통합(BitmapText 렌더·tint·anchor·pageerror 0).

## REV-20260713T081919-ai-root-feature-0016-graph-pixi-bitmaptext-pd [SKIPPED:docs-only-postdeploy]
- §80 POST-DEPLOY 라이브 기록 — docs-only. 배선 코드는 선행 REV-...-bitmaptext [SUBAGENT:PASS-WITH-FIXES] 완료. SKIPPED.
## REV-20260713T181300-detail-hover-fx — §81 상세 패널 hover 시각 효과
- 설계 선택: hover 효과를 **비커밋**(커밋 선택 bake·전체 rebuild 미접촉)으로 구현. 하이라이트는 PixiJS 어댑터의 world-space 전용 오버레이 레이어(`_hoverLayer`)에 위임 — `this.world` 자식이라 팬/줌 자동 정합, `setElementState`(노드-only, 커밋 상태)·엣지 상태 부재 문제를 우회하고 커밋 선택과 시각 충돌 없음. 카메라 이동은 기존 `_metaGraphAnimateFocus`(적응형 부드러운 팬) 재사용.
- 렌더러 무관: G6 폴백 seam(`window.__META_RENDERER`) 대비 하이라이트 메서드를 feature-detect(`typeof g.setHoverHighlight==="function"`)로 호출 — 폴백에선 graceful no-op, 카메라(focusElement)는 양쪽 동작. PixiJS 가 de-facto 렌더러라 실사용 경로 정상.
- 카메라 요동 방지: hover-intent 200ms 지연 + leave 취소(스윕 통과 무시). 클릭 팬(`_metaGraphPanToRelation`)과 동일하게 `_opSeq` 미bump — 진행 중 fetch/expand 를 폐기하지 않음(트레이드오프: 드문 동시 hover 팬 겹침 가능하나 intent 지연이 실질 완화).
- 미렌더 대상: 접힌 스키마/뷰포트 컬링으로 대상이 미렌더면 `_metaRenderedAncestorFor`(소속 테이블/카드)로 승격, 조상도 미렌더면 graceful skip(요동/오류 없음). 컬럼 단위 FK 연결선 정확도를 위해 참조/관계 행에 `data-edge-self`(방향별 self 끝점) 부여.
- a11y: mouseenter/leave 에 더해 focus/blur 도 동일 처리(키보드 탐색 파리티, 기존 `:focus-visible` CSS 관례 정합).
- XSS: 신규 `data-edge-self` 속성값 전부 기존 `esc()` 경유. 신규 파일 0·공개 barrel 표면 무변경.
- 검증: 정적(node --check 3모듈 PASS·export/import 정합·어댑터 메서드 존재·diff 4파일 스코프). PB-0008 라이브(visual_verification_scope=always 하드 게이트)는 배포 후 T81.6 — 미수행 상태로 완료 주장 안 함.

## REV-20260713T181300-detail-hover-fx-panel [SUBAGENT:PASS-WITH-FIXES]
§18.8 적대 검증 패널(general-purpose subagent, 정적 추론 — 라이브 브라우저 미가용). 판정 **PASS-WITH-FIXES**. 발견·조치:
- **MAJOR (수정됨)** 연속 hover-pan 루프 충돌: `_opSeq` 미bump(클릭 팬과 동일)이라 두 hover-pan `_metaGraphAnimateFocus` 루프가 서로 다른 앵커로 매 프레임 translateBy → ~1.2s 창에서 카메라 요동. **조치**: hover-pan 세대 토큰 `_metaHoverPanGen`(Cancel/새 Pan 이 bump) + `_metaGraphAnimateFocus(…, {abort})` 선점 종료 훅 추가 — 새 hover/leave 가 진행 중 루프를 즉시 abort(fetch `_opSeq` 는 미폐기 유지). NIT#5(leave 가 시작된 팬 못 멈춤)도 동일 수정으로 해소.
- **MINOR (수정됨)** mouseleave 미발화 재렌더(히스토리 back/forward·펼치기 버튼·폴 재렌더) 시 예약 팬 타이머가 사라진 대상으로 발화 / stale 강조 잔존: **조치**: 4개 상세 렌더 함수(RenderDetail·RenderRelations·ShowCategoryDetail·RenderClusterDetail) 진입부에 `_metaGraphHoverPanCancel()+_metaGraphClearHoverHighlight()` 추가.
- **MINOR (수정됨)** `_metaGraphSetHoverHighlight` 의 `!a && b`(self 미렌더·상대 렌더) 케이스 강조 누락: **조치**: `else if (b) addNode(b)` 추가.
- **반증(결함 아님 확인)**: XSS(`data-edge-self` 전부 `esc()` — &<>" 이스케이프) · G6 폴백 안전(feature-detect no-op, throw 경로 없음) · draw() 스래싱 없음(hover 는 `_hoverLayer`+`_render()` 만, `setData`/`draw` 무접촉) · 리스너 누수 없음(매 렌더 `el.innerHTML` 교체로 GC) · hit-test 간섭 없음(오버레이 eventMode none·자체 hit-grid) · 클릭/더블/캐럿 라우팅 무회귀(hover 는 mouseenter/leave/focus/blur 만, stopPropagation 없음).
- 재검증: 3개 모듈 `node --check` PASS(수정 후). 회귀: 그래프 헤드리스 하네스는 배포 파이프라인에서 실행(별도) — 본 변경은 additive·비커밋이라 기존 배치·선택 경로 무접촉.
## REV-20260713T170500-ai-claude-feature-0016-content-cluster-p2 [SUBAGENT: PASS-WITH-FIXES] — 잔여 affix 가짜 밴드 해소 + 연관 밴드 인접 배치 diff 적대 리뷰
- 대상: worktree p2 diff — `semantic_cluster.py`(soft-attach·centroid seriation)·`shared/config.py`(ATTACH_SIM)·`graph-simgroups.js`(일반 접두 strip·be: id 순 선두 배치)·신규 테스트(BE 2+1수정·FE 헤드리스 13→16). §18.8 general-purpose 적대 리뷰어 — **리뷰어 독립 재현**(BE 22·FE 13·헤드리스 12 스위트 전 PASS + 멱등 재실행 UPDATE 0 실증) + **적대 실험 2건으로 결함 재현**.
- 패널 판정: **PASS-WITH-FIXES — BLOCKING 0 · MAJOR 2 · MINOR 4 · NIT 2.** 통과 축: seriation·attach 결정론(tie-break 전거 확증)·멱등(재실행 UPDATE 0)·라벨 kv 캐시 코어-멤버 한정(attach 불간섭)·skip/미달 스키마와 attach 상호작용 안전·be: 이중 포함 없음·groupCollapsed/검색 강제펼침 보존·O(n²) 규모 무해.
- 결함 원장 및 처리:
  - **MAJOR-1 [BE/cap 우회] — 수정**: attach 에 클러스터별 수용량 가드 부재 — 리뷰어 실험에서 잔여 60 전원이 한 centroid 로 attach 되어 밴드 65 > cap 40(직전 cycle 이 해소한 거대 밴드의 재발 경로). → 후보 (‑sim, key) 정렬 후 **코어+attached < cap 동안만 배정**(도달 시 차선 재평가 없이 NULL — 결정·단순). 회귀 테스트 test_pass_attach_cap_guard(4D 구성) 추가.
  - **MAJOR-2 [FE/의미 접두 오검출] — 수정**: 접두 regex 2~4자+15% 임계가 user_/item_ 류 **4자 의미 접두**를 generic 판정(리뷰어 실험: user_ 25% → user 가족 해체 — AC-p2-3 자기위반) + TASK 계획(≥35%·2~4자)과 코드 drift. → regex **2~3자** 축소(dt_/ct_/sp_/usp_/tbl_ 커버 유지·4자 의미 접두 보호) + TASK.md 최종 구현값 정합 + FE 테스트 D1~D3(user_ 보존) 추가.
  - **MINOR-1 [FE] 수용**: gp 가 로드-상태 의존(이웃확장 시 nm: 그룹 키 변동 가능) — 기존 affix 지지도의 동류 리스크 확장, §49 안정화가 점프 억제. 관찰만.
  - **MINOR-2 [FE] 수용**: 세션 중 신규 be: 밴드는 §49 우선으로 후미 append(fresh load 시 정상 복귀) — 검증 절에 명시.
  - **MINOR-3 [BE] 이연**: `_label_cluster` affix 폴백의 generic strip 미적용(FE/BE 라벨 비대칭 — LLM 라벨 경로에선 무발현, 표시 품질만). 후속.
  - **MINOR-4 [BE] 수용**: ATTACH_SIM 이 τ 와 독립 상수 — config 주석에 관계 서술 존재, τ-파생 기본값은 후속 검토.
  - **NIT-1 — 수정(주석)**: rep["attached"] 의미를 "이번 pass attach 배정 총수(신규+유지)"로 명확화. **NIT-2 — 수용**: 방향 말줄임 라벨이 strip 정규화 기준(view_ strip 이래 기존 semantics 연장).
- 반영 후 재검증: FE simgroups_p2 **16/16** + category 26·vpack 19 무회귀, BE 파일 23 PASS, **전체 pytest EXIT=0/FAILED 0**. 라이브 프로브(롤백): attached 5,249·cc_data_main 잔여 114→26·리포트 3종(DT_CashPoint/DT_Castle/dt_CombineMaterial) 각기 다른 클러스터로 분리.
- **deploy_scope: included 근거 기록(§12.2/§16.3)**: FIRST_REQUEST.md 전역 선언 — cycle 종료 시 배포(web 롤링+worker 재빌드) 자동 진행, 프론트 변경이라 `visual_verification_scope: always` 에 따라 POST-DEPLOY PB-0008 이 완료 게이트.

## REV-20260713T175500-ai-claude-feature-0016-content-cluster-p2-postdeploy [SKIPPED:doc-only-postdeploy] — p2 TP.4 POST-DEPLOY 완수 기록 (코드 무변경)
- Related Change: TASK TP.4 [x] + test-runs.d fragment. 코드/자산 변경 0 — 배포(469fa20d)·클러스터 재가동(attached 4,843·cap 가드 실동작)·AGE 수렴·PB-0008 PASS(가짜 밴드 소멸·인접 배치·리포트 3종 분리) 실측 기록.

## REV-20260714T120000-graphsync-flock-guard [SUBAGENT: PASS-WITH-FIXES] — §82 metadata-graph-sync cron 겹침 실행 flock 가드 (서비스 장애 긴급 대응)
- 대상: `bin/metadata-graph-sync.sh`(flock -n 가드 신설)·`bin/routine-backfill.sh`(동일 lock 공유 가드 신설). §18.8 general-purpose 서브에이전트 — 정적 코드 리뷰(라이브 브라우저/컨테이너 미가용, 스크립트 자체 + repo 전역 `sync_graph()` 호출자 grep 기반 독립 조사).
- 배경: 사용자 장애 리포트("로그인 후 빈 화면, 작업 콘솔 미작동") 근본원인 = `metadata-graph-sync.sh` cron(30분 주기)이 동시성 가드 없이 겹쳐 쌓여 AGE 그래프 lock 경합 → pgbouncer 풀 고갈 → ask-worker/insight-worker 전역 장애. 최초 수정(flock 단일 스크립트 가드)에 대해 적대 리뷰 실시.
- 패널 판정: **PASS-WITH-FIXES — BLOCKING 0 · MAJOR 2 · MINOR 1 · NIT 1.**
- 결함 원장 및 처리:
  - **MAJOR-1 [동시성 범위 불충분] — 수정**: 리뷰어가 repo 전역 `grep -rn "sync_graph("` 로 `modules/routine_backfill.py:202`(경유 `bin/routine-backfill.sh`, 사용자가 직접 실행하는 정상 운영 명령)가 같은 AGE 그래프에 대해 동일 함수를 호출함을 발견 — 최초 수정은 cron 자기-겹침만 막을 뿐, cron 과 수동 backfill 의 동시 실행 시 **동일 장애 클래스가 다른 조합으로 재발**할 수 있었다. → `routine-backfill.sh` 에도 `metadata-graph-sync.sh` 와 **동일 lock 파일**을 사용하는 flock 가드를 추가해 자원(AGE 그래프) 단위로 직렬화. 라이브 재현으로 상호배제 확인(REPORT.md 검증 절).
  - **MAJOR-2 [lock 파일 TOCTOU] — 수정**: lock 경로가 world-writable `/tmp` 의 고정 파일명이라, 최초 생성 시점에 공격자가 심볼릭 링크를 먼저 심으면 root(cron) 프로세스가 그 대상(예: `/etc/passwd`)을 열어쓸 위험(symlink pre-plant TOCTOU) — 지적. → lock 을 root 전용 디렉터리 `/root/.locks/mysql-ai-delegated-dev/`(스크립트가 매 실행 `mkdir -p -m 700` 로 자기-provision)로 이동 + 대상이 심볼릭 링크면 fail-loud 로 즉시 거부하는 명시 검사를 두 스크립트에 동일 추가. 라이브 재현(`/etc/passwd` 심볼릭 링크 사전배치 → `exit 1` 즉시 거부, 대상 미접촉)으로 확인.
  - **MINOR (수용, 낮은 우선순위)**: lock 경로가 `COMPOSE_PROJECT_NAME` 로 스코프되지 않아 이론상 동일 호스트에 다른 compose 프로젝트가 있으면 오탐 가능 — 이 호스트는 단일 `repo` 프로젝트 고정 관행(기존 `kb-pg-healthcheck.sh` 주석과 동일 가정)이라 실 위험 낮음. 후속 검토 항목으로만 기록(TASK §82 T82.3 인접).
  - **NIT (정보 기록, 조치 불요)**: 기존 `exec docker exec ...` → `docker exec ...; exit $?` 변경으로 wrapper shell 프로세스가 별도 PID 로 생존 — `docker top <container>` 기반 기존 "잔존 프로세스 kill" quirk 절차는 컨테이너 **내부** 프로세스만 다루므로 영향 없음(host 측 수동 kill 시에만 참고).
  - **반증(결함 아님 확인)**: flock 해제는 exit 0/1/2/3 전 경로에서 정상(각 `exit` 문 도달 시 fd 9 close, `set -euo pipefail` 과 상충 없음) · lock-then-exec 사이 TOCTOU 없음(`flock -n` 원자적, `docker exec` 전체 구간 보유) · skip 이벤트는 고유 stderr 메시지로 cron.log 에서 실패와 구분 가능.
  - 미해결 관찰(비차단, 후속 이월): 스크립트 자체 timeout·연속-skip 알림 부재 — TASK §82 T82.3 (본 cycle 범위 밖, 후속 initiative)으로 이미 반영.
- 재검증: 두 스크립트 `bash -n` PASS + cross-script 상호배제 라이브 재현(1st 진행 중 2nd 즉시 exit 3) + symlink 가드 라이브 재현(exit 1, 대상 미접촉) + lock dir 권한(700 root:root, non-root 접근 거부) 실증. 상세는 TASK.md §82 T82.4/T82.5, REPORT.md 검증 절.
- Panel skip 사유(§18.8): 코드면은 REV-20260713T170500 [SUBAGENT: PASS-WITH-FIXES] 에서 완료. QA 핸들은 서빙 사본 한정·원복 완료.

## REV-20260714T090500-ai-claude-feature-0016-cluster-label-target [SKIPPED:minor-single-file] — cluster_label target 사용자 식별자화
- Related Change: CHG-20260714T090500. 단일 파일 표시-정확성 수정(마이그 0·인가 경계 0·LLM 계약 무변 — payload.datasource 는 프롬프트 문맥 필드).
- Panel skip 사유(§18.8 Minor+1파일): 위험면 = ①캐시 무효화(→ ns 해시 유지로 차단, 테스트 잠금) ②tx 오염(→ SAVEPOINT 격리, 기존 패턴 동형) ③폴백(스냅샷 부재 → key 그대로, 테스트 잠금). 데이터 정정 UPDATE 는 datasource_health join 멱등.
- Human Approval: deploy_scope: included(전역) — 사용자 리포트 직접 수정.

## REV-20260714T104500-ai-claude-feature-0016-cluster-label-target-close [SKIPPED:doc-only-postdeploy] — TL.3 완수 기록
- Related Change: CHG-20260714T104500. 코드 0 — 배포·데이터 정정·라이브 확증 기록. 코드면은 REV-20260714T090500 에서 처리.

## REV-20260715T161958-ai-claude-feature-0016-graph-detail-scroll [SUBAGENT: PASS-WITH-FIXES] — 상세 패널 [뒤로/앞으로] 스크롤 위치 보존 diff 적대 리뷰
- 대상: `graph-ctxmenu.js`(이력 스크롤 캡처/복원 + `_metaGraphHistoryGo` sync→async)·`graph-state.js`(`_histNavBusy`/`_pendingDetailScroll` 상태). §18.8 general-purpose 서브에이전트 — 정적 코드 리뷰(라이브 브라우저 미가용, diff + DOM(`admin.html`) + CSS(`graph.css:197` overflow 소유) + show 함수 3종·`_metaGraphOnNodeClick`·`_metaGraphLoadNodeAnalysis`·`_opSeq` 세대 가드 교차 검증).
- Related Change: CHG-20260715T161958. 위험면 = 표시 정확성(스크롤 좌표) + 이력 상태 정합. 인증/스키마/데이터/API 무변경.
- 패널 판정: **PASS-WITH-FIXES — BLOCKING 0 · MAJOR 1 · MINOR 3 · PASS 2.** 전 항목 반영(수정) 완료.
- 결함 원장 및 처리:
  - **MAJOR M1 [`_histNav` 억제창 확장 회귀] — 수정**: 리뷰어가 sync→async 전환으로 `_histNav`(재기록 억제) 유지 구간이 "show 동기 접두부"→"전체 fetch+render(await)"로 확장됨을 지적 — 네비 렌더 fetch 도중 사용자가 **다른 노드를 클릭**하면 그 클릭의 `_metaGraphHistoryRecord` 가 억제돼 **이력에서 누락**(패널 콘텐츠 vs `detailHistIdx` desync). → show 함수를 kick 해 promise 를 받은 **직후 `_histNav=false`** 로 되돌려 억제창을 동기 접두부로 한정(Record 는 3함수 모두 첫 await 이전 동기 구간 725/1651/2266 에서 호출·억제됨을 코드로 확증). `await` 는 유지(스크롤 복원 타이밍). 세대 가드 `seq` 도 await 이전 캡처로 복원(리뷰 M1-NIT).
  - **MINOR m2 [reject 시 tail 스킵 + 주석 부정확] — 수정**: 리뷰어가 show 함수의 try/catch 가 `apiFetch` 만 감싸고 이후 DOM 조립(`_metaGraphRenderDetail` 등)은 무방비라, 렌더 throw 시 await 가 reject → try/finally 밖 restore·focus·UpdateUI 가 스킵되고 클릭 핸들러에서 unhandled rejection 을 지적. → `await p` 를 `try/catch(_)` 로 감싸 tail(스크롤/카메라/UI)을 항상 실행 + 주석을 "fetch 만 흡수, 렌더 예외는 삼켜 tail 보장"으로 정정.
  - **MINOR m3 [AI 박스 async 성장으로 하단 복원 무력화] — 수정**: 노드 상세는 `_metaGraphRenderDetail` 이 `_metaGraphLoadNodeAnalysis`(fire-and-forget)를 킥해 AI 박스(`#metaGraphAiBox`)를 **복원(rAF) 이후** 채워 높이를 키우므로, 하단으로 스크롤해 저장한 값이 복원 시점(짧은 콘텐츠)에 clamp 되고 재적용되지 않음을 지적. → 복원 목표를 `_pendingDetailScroll{key,top}` 로 남기고 `_metaGraphLoadNodeAnalysis` 말미에 **key 일치 시 1회 재적용**(`_metaGraphReapplyPendingScroll`)하는 훅 추가(관계/클러스터 상세는 async 성장 없어 무영향).
  - **MINOR m4 [연타 캡처 오정합] — 수정**: 빠른 뒤로 연타 시 선행 네비 렌더가 미완인 동안 후행 `Go` 의 leave-capture 가 **현 항목(N-1)에 이전 화면(N)의 scrollTop** 을 기록하는 오염을 지적. → `_histNav` 과 분리된 캡처 전용 게이트 `_histNavBusy`(네비 렌더 in-flight True) 도입 — `_metaGraphHistoryCaptureScroll` 이 busy 면 스킵(억제=Record 는 그대로, 스크롤 캡처만 게이팅해 M1 회귀와 직교).
  - **PASS P1 (스크롤 대상 요소 정합)**: `graph.css:197` 이 `overflow-y:auto` 를 `<aside id="metadataGraphDetail">` 에 부여하고 `#metadataGraphDetailBody` 는 overflow 없는 flex 자식(`admin.html:861`) — 렌더가 body innerHTML 만 교체해도 스크롤 프레임은 aside 이므로 `_metaGraphDetailScrollEl()` 이 aside 를 캡처/복원하는 것이 정합(body 였으면 오답). 결함 없음 확인.
  - **PASS P2 (주경로 leave-capture 배치 정합)**: `_metaGraphHistoryRecord` 의 캡처가 두 early-return(억제·중복) 뒤·push 앞이라 실제 새 항목 기록 시에만 실행, Record 는 렌더 전 호출이라 캡처 시 aside 는 이전 콘텐츠(올바른 값). 결함 없음 확인.
- 재검증: `graph-ctxmenu.js`·`graph-state.js` `node --check`(ES module) PASS + 신규 심볼(`_histNavBusy`/`_pendingDetailScroll`/`_metaGraphReapplyPendingScroll`) 참조 정합 + 3함수 Record-before-await 순서 코드 확증. 최종 diff 2파일(graph-ctxmenu.js·graph-state.js).
- Human Approval: deploy_scope: included(FIRST_REQUEST.md 전역). visual_verification_scope: always → PB-0008 라이브(TS.6)가 배포 후 완료 게이트.
