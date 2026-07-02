---
doc_type: MIGRATION_BLUEPRINT
feature_id: feature-0016-metadata-graph
status: validated
created_at: 2026-07-02
source_of_truth: true
---

# 그래프 뷰 렌더링 엔진 교체 — Cytoscape(WebGL) → AntV G6 v5

관리콘솔 `메타데이터 > 그래프 뷰`(cross-cut 코드 거주: feature-0003 `src/static/admin.js`)의
렌더링 엔진을 **AntV G6 v5.1.1(MIT)** 로 교체하는 마이그레이션의 **검증된 청사진**.

브라우저 반복 검증(Playwright headless + 스크린샷)으로 전 구간을 실증했다. POC 원본·스크린샷은
`./poc/`. 이 문서는 통합 단계(admin.js 포팅)의 정본 가이드다.

## 1. 배경 — 왜 교체하나 (사용자 요청 5건)

| # | 증상 | 근본 원인 | G6 해법 |
|---|---|---|---|
| ① | 펼친 테이블 클릭 시 접힘 | 단일탭이 `_metaGraphToggleColumns`(토글) 호출 | 클릭=펼침 전용, 접기는 "−" 컨트롤만 |
| ② | 다른 위치서 펼쳐지고 카메라 점프 | 컬럼 추가→`newAddsBox`→full-spread fcose + layoutstop fit-jump | 결정론적 제자리 배치(setData+draw, 레이아웃 재실행 없음) |
| ③ | 스크롤/줌 동기화 지연 | HTML 오버레이(클러스터명·닫힘버튼)를 rAF 로 캔버스에 뒤늦게 맞춤. **WebGL 은 render 이벤트 미emit** | **오버레이 제거** — 라벨/컨트롤을 G6 네이티브 요소로 렌더(동일 렌더틱 = 동기화 지연 소멸) |
| ④ | 유사 스키마 클러스터(dk_game_release_*) 뒤섞임 | fcose `randomize:true` 힘배치 | **결정론적 자연정렬 grid** 클러스터 배치 |
| ⑤ | 테두리가 크기에 따라 왜곡 | WebGL sprite-atlas 텍스처 업스케일 | Canvas 벡터 렌더(왜곡 없음, 2x DPR 선명) |

⑥ 보너스: WebGL 이 못 그리던 **점선 엣지(추정 관계)** 복원.

정식 ADR 은 feature `docs/DECISIONS.md` ADR-004 참조. WebGL 은 정식 ADR 이 아닌 코드 주석 결정이었다.

## 2. 검증된 모델 (Model B — 2단 combo + 결정론적 배치)

```
Schema  = G6 combo(type:'rect', 점선 남색 카드)  ← grid 배치(자연정렬)
  ├ Table  = rect 노드(teal 칩, 흰 볼드 라벨)     ← 스키마 안 세로 스택
  │   ├ "−" ctl = rect 노드(펼쳐졌을 때만)         ← 접기 컨트롤(네이티브·동기화)
  │   └ Column  = circle 노드(dot + 우측 라벨)     ← 테이블 아래 세로 스택(ordinal)
  └ ...
REFERENCES/RELATED_TERM = G6 edge(실선=trusted, 점선=candidate)
HAS_TABLE/HAS_COLUMN = combo containment(엣지 없음)
GlossaryTerm = 노드(앰버)
```

**핵심 아키텍처 패턴**: JS 에 전체 그래프 모델(`_metaGraph.model`) 유지 → 상태변경 시
`build()` 로 **위치 포함 전체 G6 데이터 재구성** → `graph.setData(data)` + `graph.draw()`.
증분 `addNodeData`/`translateElementTo` 을 쓰지 않는다(불안정). 이 패턴이 결정론(무-shuffle,
제자리)과 안정성을 동시에 보장한다.

- **roots 뷰**: 결정론적 grid 배치(각 요소 `style.x/y` 계산) → `setData` + **`draw()`**(레이아웃 없음).
- **검색/이웃확장 뷰**: 교차 스키마 관계 있음 → `setData` + **`render()`** with `layout:{type:'d3-force'}`(또는 combo-combined). setData+render+force 검증됨.
- **마커/선택/펼침 등 상태변경**: 모델 갱신 → `build()` → `setData` + `draw()`.

## 3. G6 v5 함정 (실증으로 확정 — 통합 시 필수 준수)

1. **element `type` 은 `style` 형제, `style` 안 아님**. `{id, type:'rect', style:{...}}`. `style` 안에 두면 전부 기본 circle 로 렌더.
2. **`render()` 는 초기 전체 렌더용**. 증분 `addNodeData`+`render()` 는 **크래시**. 증분/재적용은 **`draw()`**, 또는 `setData(full)`+`draw()`. force 레이아웃 재계산이 필요하면 `setData(full)`+`render()`.
3. **`lineDash: false` 금지 — G6 크래시**(`To()` 정규화가 `false.length` 접근). 실선 엣지는 lineDash 키 **생략**(또는 `0`). 점선은 `[6,4]`.
4. **위치**: 노드 `style.x`/`style.y`(모델 좌표). combo 는 자식 bounds 로 자동 fit. `graph.translateElementTo(id,[x,y],false)` 도 있으나 setData 방식이 견고.
5. **상태 마커**: 요소 데이터 `states:['analyzed'|'running'|'selected']` + Graph 옵션 `node:{state:{analyzed:{...},running:{...},selected:{...}}}`. `setElementState(id,[...])` 도 가능.
6. combo `collapsedMarker:false` 로 "0" 자식수 배지 끔(우리는 네이티브 collapse 미사용).
7. 그리기 메서드는 `render`/`draw`. `draw` 는 grep 상 함수 존재(내부명 아님).
8. UMD 전역 = `window.G6`. `const {Graph}=G6`.

## 4. 통합 계획 (admin.js — `_metaGraph*` 블록 2911–4198)

### 4.1 유지(DOM/API·엔진 무관 — `cy`→`graph` 소폭 수정만)
`_metaGraphStatus`, `_metaShowGraph`, `_metaHideGraph`, `_metaGraphRenderDetailEmpty`,
`_metaEdgeTrustBadge`, `_metaGraphRenderDetail`(선택강조 `cy.$(:selected)`→모델 selected),
`_metaGraphAnalyze`, `_metaGraphPollRun`, `_metaGraphRenderProgress`,
`_metaGraphLoadNodeAnalysis`, `_metaGraphRenderClusterDetail`, `_metaGraphInitResizer`
(`cy.resize/fit`→`graph.resize()/fitView()`).

### 4.2 재작성(엔진)
- `_metaGraph` 상태: `{graph, model, bound, lastQuery, lastDetailKey, activeRunId, introspected, ...}`.
  `model` = `{mode:'roots'|'search'|'neighbor', schemas, tables, columns(Map fqn→[]), expanded:Set, analyzed:Set, running:Set, selected, rel:Map, extraNodes(term/cross), edges}`.
- `_metaInitGraph`: `new G6.Graph({container, autoResize:true, node:{state:{...}}, behaviors:['drag-canvas','zoom-canvas','drag-element'], animation:false})` + 이벤트 바인딩(`node:click`/`node:dblclick`/`combo:click`/`canvas:click`). "−" ctl 클릭 → collapse. 단일=상세, 더블=이웃확장.
- `_metaG6Build()`: 모델→`{combos,nodes,edges}` 위치 포함(§2 배치 알고리즘). 인라인 per-element style(매퍼 금지 — undefined 위험). `_META_GRAPH_COLOR` 팔레트 재사용.
- `_metaG6Apply(fit)`: `graph.setData(build())` → roots=`draw()` / 검색·이웃=`render()`(force) → `fit?fitView`.
- `_metaGraphAddElements`(API nodes/edges→모델 반영), `_metaGraphLoadRoots`, `_metaGraphSearch`(rel→테이블 칩 size/강조), `_metaGraphShowDetail`(모델 selected), `_metaGraphExpand`(이웃→모델+force), `_metaGraphToggleColumns`→**펼침 전용**(이미 펼쳐졌으면 상세만), `_metaGraphCollapse`(ctl 클릭), `_metaGraphShowClusterDetail`(combo:click), 마커 3종(`Mark*`/`SyncAnalysisMarkers`).
- **제거**: `_metaGraphEnsureLabelLayer`, `_metaGraphSyncClusterLabels`, `_metaGraphSyncCollapseButtons`(오버레이 전량 삭제 → ③ 해소), `_metaGraphColCmp`/`OrderedColumns`/`PlaceColumns`/`Layout`(결정론 build 로 대체), `_metaNodeSize`(build 로 흡수).

### 4.3 API→모델 매핑
- 응답 노드 `label`: Schema→combo, Table→rect, Column→circle(부모 테이블 fqn=`_metaColParent`), GlossaryTerm→term 노드, Datasource/Product→노드.
- 엣지 `type`: HAS_TABLE/HAS_COLUMN=containment(생략), REFERENCES(status candidate/trusted → 점선/실선), RELATED_TERM/DESCRIBES=엣지/상세.
- 엔드포인트 불변: `/graph?scope=`,`?node=&depth=`,`?q=`,`/graph/columns`,`/analyze*`.

### 4.4 admin.html / styles.css
- admin.html: `<script src=".../vendor/cytoscape*.js">`·`cytoscape-fcose`·`layout-base`·`cose-base` 제거, `<script src="/static/vendor/g6.min.js?v=5.1.1">` 추가. **cache-buster bump**(admin.js·styles.css `?v=`). 범례 텍스트 소폭 갱신(점선 복원 반영).
- styles.css: `.admin-meta-graph-label-layer`·`-cluster-label`·`-collapse-btn` 오버레이 CSS 제거. `#metadataGraphCanvas` position:relative 유지(불필요하면 정리). 나머지(툴바·상세·resizer·progress) 유지.

## 5. 검증 방법
- **dev-loop(오프라인)**: 그래프 모듈 + admin.html 그래프 마크업 + mock `apiFetch`(실제 응답 shape) harness → Playwright headless 스크린샷. 전 플로우(roots/검색/펼침/접기/이웃/마커/클러스터상세) 확인.
- **실앱**: web 컨테이너에 반영(배포)해 로그인 후 그래프탭 확인.
- **완료 게이트(hard)**: `visual_verification_scope: always` → **PB-0008 실 Windows 브라우저 시각검증** 필수(`bin/win-browser.py`), `verify-completion.sh --pre-commit feature-0016-metadata-graph` check #13.

## 6. 상태
- [x] 엔진 결정(G6 v5) + 사용자 승인(바로 마이그레이션)
- [x] G6 vendored(`vendor/g6.min.js` 5.1.1) — admin.html 미참조(inert)
- [x] 전 기술요소 POC 실증(`./poc/`): 중첩/2단 combo, 결정론 grid, 제자리 펼침, 접기 컨트롤, 점선+실선 엣지, 상태 마커, 선명 테두리, setData+draw/ render+force
- [x] G6 함정 전량 확정(§3)
- [x] admin.js 엔진 포팅(§4.2) — `_metaGraph` 모델 + `_metaG6Build`/`_metaG6Apply` + init/loadRoots/search/showDetail/
      toggleColumns(펼침전용)/collapse/expand/ingest/markers/clusterDetail. 오버레이 3함수 제거. DOM/API 함수 유지. node --check PASS.
- [x] admin.html(cytoscape·fcose 4종 제거 → g6.min.js) + styles.css(오버레이 CSS 제거) + cache-buster bump(admin.js·styles.css `?v=20260702-graph-g6`)
- [x] dev-loop 검증 — Playwright headless harness(실 admin.html 마크업 + mock apiFetch)로 전 플로우 PASS(에러 0):
      roots(자연정렬 grid·마커·엣지) / 제자리 컬럼 펼침 / 재클릭-무접힘(①) / "−"접기 / 검색(유사도 크기) / 클러스터. 스크린샷 `./poc/`
- [ ] 실앱 배포 + PB-0008 실 Windows 시각검증(hard gate) + `verify-completion.sh` + commit
- [x] docs: DECISIONS ADR-004 · (TASK/REPORT/TEST 갱신)
